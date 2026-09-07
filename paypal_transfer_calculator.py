"""
PayPal USD Withdrawal Calculator
Call this function with a USD amount to get a withdrawal recommendation.
"""
from datetime import datetime
import os

from dotenv import load_dotenv

from telegram_utils import send_telegram_message

load_dotenv()

# Configuration
AUTO_TRANSFER_DAY = 1  # Day of month for auto-transfer
MANUAL_WITHDRAWAL_FEE_PCT = float(
    os.getenv("PAYPAL_MANUAL_WITHDRAWAL_FEE_PCT", os.getenv("PAYPAL_CONVERSION_SPREAD_PCT", "0.03"))
)
AUTO_WITHDRAWAL_FEE_PCT = float(os.getenv("PAYPAL_AUTO_WITHDRAWAL_FEE_PCT", "0.0"))
TRANSFER_THRESHOLD_USD = float(os.getenv("PAYPAL_TRANSFER_THRESHOLD_USD", "0.01"))


def calculate_days_until_auto_transfer():
    """Calculate days until next auto-transfer (1st of month)"""
    today = datetime.now()
    
    if today.day < AUTO_TRANSFER_DAY:
        next_transfer = today.replace(day=AUTO_TRANSFER_DAY)
    else:
        if today.month == 12:
            next_transfer = today.replace(year=today.year + 1, month=1, day=AUTO_TRANSFER_DAY)
        else:
            next_transfer = today.replace(month=today.month + 1, day=AUTO_TRANSFER_DAY)
    
    days_until = (next_transfer - today).days
    return days_until, next_transfer


def calculate_paypal_transfer(usd_amount):
    """
    Calculate PayPal withdrawal decision for given USD amount.

    Args:
        usd_amount (float): USD amount to withdraw

    Returns:
        dict with decision and calculations, or None if error
    """
    if usd_amount <= 0:
        return None

    days_until, next_transfer_date = calculate_days_until_auto_transfer()

    manual_fee_amount = usd_amount * MANUAL_WITHDRAWAL_FEE_PCT
    auto_fee_amount = usd_amount * AUTO_WITHDRAWAL_FEE_PCT

    manual_net_amount = usd_amount - manual_fee_amount
    auto_net_amount = usd_amount - auto_fee_amount
    difference = manual_net_amount - auto_net_amount

    if difference > TRANSFER_THRESHOLD_USD:
        recommendation = "MANUAL_TRANSFER"
        reason = f"Manual withdrawal now gives you {difference:.2f} USD more than auto-transfer"
    elif difference < -TRANSFER_THRESHOLD_USD:
        recommendation = "WAIT_FOR_AUTO"
        reason = f"Waiting saves {abs(difference):.2f} USD versus manual withdrawal"
    else:
        recommendation = "EITHER"
        reason = f"Difference is small ({difference:.2f} USD), either option is fine"
    
    return {
        "recommendation": recommendation,
        "reason": reason,
        "usd_balance": usd_amount,
        "manual_fee_pct": MANUAL_WITHDRAWAL_FEE_PCT,
        "auto_fee_pct": AUTO_WITHDRAWAL_FEE_PCT,
        "manual_fee_amount": manual_fee_amount,
        "auto_fee_amount": auto_fee_amount,
        "manual_net_amount": manual_net_amount,
        "auto_net_amount": auto_net_amount,
        "difference": difference,
        "days_until_auto": days_until,
        "next_transfer_date": next_transfer_date.strftime("%Y-%m-%d")
    }


def format_paypal_transfer_message(decision_data):
    """Format PayPal withdrawal decision message."""
    rec = decision_data["recommendation"]
    
    if rec == "MANUAL_TRANSFER":
        emoji = "✅"
        title = "WITHDRAW NOW RECOMMENDED"
    elif rec == "WAIT_FOR_AUTO":
        emoji = "⏳"
        title = "WAIT FOR AUTO-TRANSFER"
    else:
        emoji = "🤷"
        title = "EITHER OPTION IS FINE"
    
    message = f"{emoji} <b>{title}</b>\n"
    message += "=" * 40 + "\n\n"
    
    message += f"💰 <b>USD Amount:</b> {decision_data['usd_balance']:.2f} USD\n\n"
    
    message += "📊 <b>CURRENT OPTION (Manual Withdrawal Now):</b>\n"
    message += f"   • Manual fee: {decision_data['manual_fee_pct']*100:.2f}%\n"
    message += f"   • Fee amount: -{decision_data['manual_fee_amount']:.2f} USD\n"
    message += f"   • <b>Net amount: {decision_data['manual_net_amount']:.2f} USD</b>\n\n"
    message += "📅 <b>AUTO-TRANSFER OPTION (Wait until {})</b>:\n".format(decision_data['next_transfer_date'])
    message += f"   • Auto fee: {decision_data['auto_fee_pct']*100:.2f}%\n"
    message += f"   • Fee amount: -{decision_data['auto_fee_amount']:.2f} USD\n"
    message += f"   • <b>Net amount: {decision_data['auto_net_amount']:.2f} USD</b>\n\n"
    
    message += "💡 <b>DECISION:</b>\n"
    message += f"   {decision_data['reason']}\n\n"
    
    if decision_data['difference'] > 0:
        message += f"   ✅ <b>Manual withdrawal is BETTER by {decision_data['difference']:.2f} USD</b>\n"
    elif decision_data['difference'] < 0:
        message += f"   ⏳ <b>Auto-transfer is BETTER by {abs(decision_data['difference']):.2f} USD</b>\n"
    else:
        message += f"   🤷 <b>Difference is minimal ({decision_data['difference']:.2f} USD)</b>\n"
    
    message += f"\n📆 <b>Days until auto-transfer:</b> {decision_data['days_until_auto']} days\n\n"
    
    message += "⚠️ <b>Note:</b> Manual withdrawal now uses a 3% fee by default.\n"
    message += "Auto-transfer is assumed to have no additional withdrawal fee."
    
    return message


def check_paypal_transfer(usd_amount, send_to_telegram=True):
    """
    Check PayPal transfer decision and optionally send to Telegram
    
    Args:
        usd_amount (float): USD amount to check
        send_to_telegram (bool): Whether to send result to Telegram
        
    Returns:
        dict with decision data, or None if error
    """
    decision = calculate_paypal_transfer(usd_amount)
    
    if not decision:
        if send_to_telegram:
            send_telegram_message("❌ Error: Could not calculate withdrawal decision. Check USD amount.")
        return None
    
    message = format_paypal_transfer_message(decision)
    
    if send_to_telegram:
        send_telegram_message(message)
    
    return decision

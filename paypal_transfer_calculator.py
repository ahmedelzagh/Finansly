"""
PayPal GBP to USD to EGP Withdrawal Calculator
Call this function with a GBP amount to estimate the USD withdrawal amount and final EGP payout.
"""
from datetime import datetime
import os

from dotenv import load_dotenv

from financial_utils import get_gbp_to_usd_rate, get_official_usd_rate
from telegram_utils import send_telegram_message

load_dotenv()

# Configuration
AUTO_TRANSFER_DAY = 1  # Day of month for auto-transfer
PAYPAL_CONVERSION_DISCOUNT_PCT = float(os.getenv("PAYPAL_CONVERSION_DISCOUNT_PCT", "0.03135"))
MANUAL_WITHDRAWAL_FEE_PCT = float(os.getenv("PAYPAL_MANUAL_WITHDRAWAL_FEE_PCT", "0.03"))
NSAVE_WITHDRAW_TO_EGP_FEE_PCT = float(
    os.getenv(
        "PAYPAL_NSAVE_WITHDRAW_TO_EGP_FEE_PCT",
        os.getenv("PAYPAL_INSTA_PAY_FEE_PCT", "0.01"),
    )
)
TRANSFER_THRESHOLD_EGP = float(os.getenv("PAYPAL_TRANSFER_THRESHOLD_EGP", os.getenv("PAYPAL_TRANSFER_THRESHOLD_USD", "1.0")))


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


def calculate_paypal_transfer(gbp_amount):
    """
    Calculate PayPal withdrawal decision for given GBP amount.

    Args:
        gbp_amount (float): GBP amount to withdraw

    Returns:
        dict with decision and calculations, or None if error
    """
    if gbp_amount <= 0:
        return None

    gbp_to_usd_market_rate = get_gbp_to_usd_rate()
    usd_to_egp_rate = get_official_usd_rate()
    if not gbp_to_usd_market_rate or not usd_to_egp_rate:
        return None

    paypal_gbp_to_usd_rate = gbp_to_usd_market_rate * (1 - PAYPAL_CONVERSION_DISCOUNT_PCT)
    gross_usd_amount = gbp_amount * paypal_gbp_to_usd_rate

    days_until, next_transfer_date = calculate_days_until_auto_transfer()

    manual_fee_amount = gross_usd_amount * MANUAL_WITHDRAWAL_FEE_PCT
    auto_fee_amount = 0.0

    manual_net_amount = gross_usd_amount - manual_fee_amount
    auto_net_amount = gross_usd_amount - auto_fee_amount
    manual_final_egp = manual_net_amount * usd_to_egp_rate * (1 - NSAVE_WITHDRAW_TO_EGP_FEE_PCT)
    auto_final_egp = auto_net_amount * usd_to_egp_rate * (1 - NSAVE_WITHDRAW_TO_EGP_FEE_PCT)
    difference = manual_final_egp - auto_final_egp

    if difference > TRANSFER_THRESHOLD_EGP:
        recommendation = "MANUAL_TRANSFER"
        reason = f"Manual withdrawal now gives you {difference:.2f} EGP more than auto-transfer"
    elif difference < -TRANSFER_THRESHOLD_EGP:
        recommendation = "WAIT_FOR_AUTO"
        reason = f"Waiting saves {abs(difference):.2f} EGP versus manual withdrawal"
    else:
        recommendation = "EITHER"
        reason = f"Difference is small ({difference:.2f} EGP), either option is fine"
    
    return {
        "recommendation": recommendation,
        "reason": reason,
        "gbp_amount": gbp_amount,
        "gross_usd_amount": gross_usd_amount,
        "gbp_to_usd_market_rate": gbp_to_usd_market_rate,
        "paypal_conversion_discount_pct": PAYPAL_CONVERSION_DISCOUNT_PCT,
        "paypal_gbp_to_usd_rate": paypal_gbp_to_usd_rate,
        "usd_to_egp_rate": usd_to_egp_rate,
        "manual_fee_pct": MANUAL_WITHDRAWAL_FEE_PCT,
        "nsave_withdraw_to_egp_fee_pct": NSAVE_WITHDRAW_TO_EGP_FEE_PCT,
        "manual_fee_amount": manual_fee_amount,
        "auto_fee_amount": auto_fee_amount,
        "manual_net_amount": manual_net_amount,
        "auto_net_amount": auto_net_amount,
        "manual_final_egp": manual_final_egp,
        "auto_final_egp": auto_final_egp,
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
    
    message += f"💰 <b>GBP Amount:</b> {decision_data['gbp_amount']:.2f} GBP\n"
    message += f"   <b>Market GBP/USD:</b> 1 GBP = {decision_data['gbp_to_usd_market_rate']:.6f} USD\n"
    message += f"   <b>PayPal GBP/USD:</b> 1 GBP = {decision_data['paypal_gbp_to_usd_rate']:.6f} USD\n"
    message += f"   <b>Gross USD:</b> {decision_data['gross_usd_amount']:.2f} USD\n\n"
    
    message += "📊 <b>CURRENT OPTION (Manual Withdrawal Now):</b>\n"
    message += f"   • Manual fee: {decision_data['manual_fee_pct']*100:.2f}%\n"
    message += f"   • Fee amount: -{decision_data['manual_fee_amount']:.2f} USD\n"
    message += f"   • nsave withdraw-to-EGP fee: {decision_data['nsave_withdraw_to_egp_fee_pct']*100:.2f}%\n"
    message += f"   • <b>Final amount: {decision_data['manual_final_egp']:.2f} EGP</b>\n\n"
    message += "📅 <b>AUTO-TRANSFER OPTION (Wait until {})</b>:\n".format(decision_data['next_transfer_date'])
    message += f"   • Manual fee: 0.00%\n"
    message += f"   • Fee amount: -{decision_data['auto_fee_amount']:.2f} USD\n"
    message += f"   • nsave withdraw-to-EGP fee: {decision_data['nsave_withdraw_to_egp_fee_pct']*100:.2f}%\n"
    message += f"   • <b>Final amount: {decision_data['auto_final_egp']:.2f} EGP</b>\n\n"
    
    message += "💡 <b>DECISION:</b>\n"
    message += f"   {decision_data['reason']}\n\n"
    
    if decision_data['difference'] > 0:
        message += f"   ✅ <b>Manual withdrawal is BETTER by {decision_data['difference']:.2f} EGP</b>\n"
    elif decision_data['difference'] < 0:
        message += f"   ⏳ <b>Auto-transfer is BETTER by {abs(decision_data['difference']):.2f} EGP</b>\n"
    else:
        message += f"   🤷 <b>Difference is minimal ({decision_data['difference']:.2f} EGP)</b>\n"
    
    message += f"\n📆 <b>Days until auto-transfer:</b> {decision_data['days_until_auto']} days\n\n"
    
    message += "⚠️ <b>Note:</b> PayPal conversion is discounted from the live GBP/USD market rate.\n"
    message += "USD -> EGP uses the nsave withdraw-to-EGP fee by default."
    
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
            send_telegram_message("❌ Error: Could not calculate withdrawal decision. Check GBP amount and rate availability.")
        return None
    
    message = format_paypal_transfer_message(decision)
    
    if send_to_telegram:
        send_telegram_message(message)
    
    return decision

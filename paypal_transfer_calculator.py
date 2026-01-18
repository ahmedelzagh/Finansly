"""
PayPal GBP Transfer Decision Calculator
Call this function with an amount to get transfer recommendation
"""
from datetime import datetime
from financial_utils import get_gbp_rate
from telegram_utils import send_telegram_message
from price_tracker import load_price_history

# Configuration
MANUAL_TRANSFER_TAX = 150  # EGP tax for manual transfer
AUTO_TRANSFER_DAY = 1  # Day of month for auto-transfer


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


def estimate_future_rate(current_rate, price_history, days_ahead):
    """Estimate future GBP rate based on historical trends"""
    if len(price_history) < 7:
        return current_rate
    
    recent_prices = price_history[-min(7, len(price_history)):]
    prices = [p["price"] for p in recent_prices]
    
    if len(prices) >= 2:
        daily_changes = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            daily_changes.append(change)
        
        avg_daily_change = sum(daily_changes) / len(daily_changes) if daily_changes else 0
        estimated_rate = current_rate + (avg_daily_change * days_ahead * 0.5)
        return max(estimated_rate, current_rate * 0.95)
    
    return current_rate


def calculate_paypal_transfer(gbp_amount):
    """
    Calculate PayPal transfer decision for given GBP amount
    
    Args:
        gbp_amount (float): GBP amount to transfer
        
    Returns:
        dict with decision and calculations, or None if error
    """
    if gbp_amount <= 0:
        return None
    
    current_rate = get_gbp_rate()
    if not current_rate:
        return None
    
    days_until, next_transfer_date = calculate_days_until_auto_transfer()
    
    # Calculate current value if transferred now
    current_value_egp = gbp_amount * current_rate
    current_value_after_tax = current_value_egp - MANUAL_TRANSFER_TAX
    
    # Estimate future rate
    history = load_price_history()
    gbp_history = history.get("gbp", []) if history else []
    
    if gbp_history:
        estimated_future_rate = estimate_future_rate(current_rate, gbp_history, days_until)
    else:
        estimated_future_rate = current_rate * 0.98  # Conservative estimate
    
    # Calculate future value if waiting
    future_value_egp = gbp_amount * estimated_future_rate
    future_value_after_tax = future_value_egp  # No tax on auto-transfer
    
    # Calculate difference
    difference = current_value_after_tax - future_value_after_tax
    
    # Decision logic
    if difference > 50:
        recommendation = "MANUAL_TRANSFER"
        reason = f"Manual transfer now saves {difference:.2f} EGP even after tax"
    elif difference < -50:
        recommendation = "WAIT_FOR_AUTO"
        reason = f"Waiting saves {abs(difference):.2f} EGP (better rate expected)"
    else:
        recommendation = "EITHER"
        reason = f"Difference is small ({difference:.2f} EGP), either option is fine"
    
    return {
        "recommendation": recommendation,
        "reason": reason,
        "gbp_balance": gbp_amount,
        "current_rate": current_rate,
        "estimated_future_rate": estimated_future_rate,
        "current_value_egp": current_value_egp,
        "current_value_after_tax": current_value_after_tax,
        "future_value_egp": future_value_egp,
        "future_value_after_tax": future_value_after_tax,
        "difference": difference,
        "days_until_auto": days_until,
        "next_transfer_date": next_transfer_date.strftime("%Y-%m-%d"),
        "manual_tax": MANUAL_TRANSFER_TAX
    }


def format_paypal_transfer_message(decision_data):
    """Format PayPal transfer decision message"""
    rec = decision_data["recommendation"]
    
    if rec == "MANUAL_TRANSFER":
        emoji = "✅"
        title = "TRANSFER NOW RECOMMENDED"
    elif rec == "WAIT_FOR_AUTO":
        emoji = "⏳"
        title = "WAIT FOR AUTO-TRANSFER"
    else:
        emoji = "🤷"
        title = "EITHER OPTION IS FINE"
    
    message = f"{emoji} <b>{title}</b>\n"
    message += "=" * 40 + "\n\n"
    
    message += f"💰 <b>GBP Amount:</b> {decision_data['gbp_balance']:.2f} GBP\n\n"
    
    message += "📊 <b>CURRENT OPTION (Manual Transfer Now):</b>\n"
    message += f"   • Current Rate: {decision_data['current_rate']:.2f} EGP/GBP\n"
    message += f"   • You'll receive: {decision_data['current_value_egp']:.2f} EGP\n"
    message += f"   • Tax (manual): -{decision_data['manual_tax']:.2f} EGP\n"
    message += f"   • <b>Net amount: {decision_data['current_value_after_tax']:.2f} EGP</b>\n\n"
    
    message += "📅 <b>AUTO-TRANSFER OPTION (Wait until {})</b>:\n".format(decision_data['next_transfer_date'])
    message += f"   • Estimated Rate: {decision_data['estimated_future_rate']:.2f} EGP/GBP\n"
    message += f"   • You'll receive: {decision_data['future_value_egp']:.2f} EGP\n"
    message += f"   • Tax: 0 EGP (no tax on auto-transfer)\n"
    message += f"   • <b>Net amount: {decision_data['future_value_after_tax']:.2f} EGP</b>\n\n"
    
    message += "💡 <b>DECISION:</b>\n"
    message += f"   {decision_data['reason']}\n\n"
    
    if decision_data['difference'] > 0:
        message += f"   ✅ <b>Manual transfer is BETTER by {decision_data['difference']:.2f} EGP</b>\n"
    elif decision_data['difference'] < 0:
        message += f"   ⏳ <b>Auto-transfer is BETTER by {abs(decision_data['difference']):.2f} EGP</b>\n"
    else:
        message += f"   🤷 <b>Difference is minimal ({decision_data['difference']:.2f} EGP)</b>\n"
    
    message += f"\n📆 <b>Days until auto-transfer:</b> {decision_data['days_until_auto']} days\n\n"
    
    message += "⚠️ <b>Note:</b> Future rate is an estimate based on recent trends.\n"
    message += "Actual rate on transfer day may vary."
    
    return message


def check_paypal_transfer(gbp_amount, send_to_telegram=True):
    """
    Check PayPal transfer decision and optionally send to Telegram
    
    Args:
        gbp_amount (float): GBP amount to check
        send_to_telegram (bool): Whether to send result to Telegram
        
    Returns:
        dict with decision data, or None if error
    """
    decision = calculate_paypal_transfer(gbp_amount)
    
    if not decision:
        if send_to_telegram:
            send_telegram_message("❌ Error: Could not calculate transfer decision. Check GBP rate availability.")
        return None
    
    message = format_paypal_transfer_message(decision)
    
    if send_to_telegram:
        send_telegram_message(message)
    
    return decision

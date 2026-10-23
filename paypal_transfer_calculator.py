"""
PayPal GBP to USD to EGP Withdrawal Calculator
Call this function with a GBP amount to estimate the USD withdrawal amount and final EGP payout.
"""
from datetime import datetime
import json
import math
import os
from statistics import median

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
PRICE_HISTORY_FILE = os.getenv("PAYPAL_PRICE_HISTORY_FILE", "price_history.json")
FORECAST_MIN_POINTS = int(os.getenv("PAYPAL_FORECAST_MIN_POINTS", "7"))
FORECAST_LOOKBACK_POINTS = int(os.getenv("PAYPAL_FORECAST_LOOKBACK_POINTS", "30"))
FORECAST_MAX_DAILY_CHANGE_PCT = float(os.getenv("PAYPAL_FORECAST_MAX_DAILY_CHANGE_PCT", "0.5"))


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
    
    days_until = (next_transfer.date() - today.date()).days
    return days_until, next_transfer


def forecast_gbp_egp_rate(current_rate, target_date):
    """Forecast the effective GBP/EGP rate using recent timestamped history."""
    try:
        with open(PRICE_HISTORY_FILE, "r") as history_file:
            history = json.load(history_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

    daily_points = {}
    for entry in history.get("gbp", []):
        try:
            timestamp = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
            rate = float(entry["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if rate > 0:
            day = timestamp.date()
            previous_point = daily_points.get(day)
            if previous_point is None or timestamp > previous_point[0]:
                daily_points[day] = (timestamp, rate)

    points = sorted(daily_points.values())[-FORECAST_LOOKBACK_POINTS:]
    if len(points) < FORECAST_MIN_POINTS:
        return None

    daily_returns = []
    for (previous_time, previous_rate), (current_time, current_rate) in zip(points, points[1:]):
        elapsed_days = (current_time - previous_time).total_seconds() / 86400
        if elapsed_days > 0:
            daily_returns.append(math.log(current_rate / previous_rate) / elapsed_days)

    if not daily_returns:
        return None

    max_daily_change = FORECAST_MAX_DAILY_CHANGE_PCT / 100
    daily_return = max(-max_daily_change, min(max_daily_change, median(daily_returns)))
    days_until = max(0, (target_date.date() - datetime.now().date()).days)
    predicted_rate = current_rate * math.exp(daily_return * days_until)
    change_pct = ((predicted_rate / current_rate) - 1) * 100

    return {
        "predicted_rate": predicted_rate,
        "change_pct": change_pct,
        "history_points": len(points),
        "daily_trend_pct": daily_return * 100,
    }


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

    forecast = forecast_gbp_egp_rate(
        gbp_to_usd_market_rate * usd_to_egp_rate,
        next_transfer_date,
    )
    if forecast:
        predicted_gbp_egp_rate = forecast["predicted_rate"]
        predicted_currency_change_pct = forecast["change_pct"]
        auto_final_egp = auto_net_amount * predicted_gbp_egp_rate * (1 - NSAVE_WITHDRAW_TO_EGP_FEE_PCT) / gbp_to_usd_market_rate
    else:
        predicted_gbp_egp_rate = gbp_to_usd_market_rate * usd_to_egp_rate
        predicted_currency_change_pct = 0.0
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
        "forecast_available": forecast is not None,
        "predicted_gbp_egp_rate": predicted_gbp_egp_rate,
        "predicted_currency_change_pct": predicted_currency_change_pct,
        "forecast_history_points": forecast["history_points"] if forecast else 0,
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
    message += f"   • nsave withdraw-to-EGP fee: {decision_data['nsave_withdraw_to_egp_fee_pct']*100:.2f}%\n"
    if decision_data['forecast_available']:
        message += f"   • Expected currency change: {decision_data['predicted_currency_change_pct']:+.2f}%\n"
        message += f"   • <b>Expected final amount: {decision_data['auto_final_egp']:.2f} EGP</b>\n\n"
    else:
        message += f"   • <b>Final amount at current rates: {decision_data['auto_final_egp']:.2f} EGP</b>\n"
        message += "   • Forecast unavailable: not enough FX history\n\n"
    
    message += "💡 <b>DECISION:</b>\n"
    message += f"   {decision_data['reason']}\n\n"
    
    if decision_data['difference'] > 0:
        message += f"   ✅ <b>Manual withdrawal is BETTER by {decision_data['difference']:.2f} EGP</b>\n"
    elif decision_data['difference'] < 0:
        message += f"   ⏳ <b>Auto-transfer is BETTER by {abs(decision_data['difference']):.2f} EGP</b>\n"
    else:
        message += f"   🤷 <b>Difference is minimal ({decision_data['difference']:.2f} EGP)</b>\n"
    
    message += f"\n📆 <b>Days until auto-transfer:</b> {decision_data['days_until_auto']} days\n"
    if decision_data['forecast_available']:
        message += f"📈 Forecast uses {decision_data['forecast_history_points']} recent GBP/EGP daily observations.\n\n"
    else:
        message += "\n"
    
    message += "⚠️ <b>Note:</b> PayPal conversion is discounted from the live GBP/USD market rate.\n"
    message += "USD -> EGP uses the nsave withdraw-to-EGP fee by default."
    
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
            send_telegram_message("❌ Error: Could not calculate withdrawal decision. Check GBP amount and rate availability.")
        return None
    
    message = format_paypal_transfer_message(decision)
    
    if send_to_telegram:
        send_telegram_message(message)
    
    return decision

"""
Price tracking and notification system for buy/sell signals
Uses real-world trading strategies: Moving Averages, RSI, Support/Resistance
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from financial_utils import get_gold_price, get_official_usd_rate, get_gbp_rate
from telegram_utils import send_telegram_message, format_price_alert
from trading_strategy import get_trading_signal, find_support_resistance

# Configuration
PRICE_HISTORY_FILE = "price_history.json"
DAILY_NOTIFICATION_FILE = "daily_notification.json"  # Track daily summary sends
MAX_HISTORY_ENTRIES = 200  # Keep more history for better analysis (need at least 30 for indicators)
MIN_HISTORY_FOR_SIGNALS = 30  # Minimum history required before sending signals
MIN_VOLATILITY_RATIO = 0.005  # Require at least 0.5% range over lookback to consider signal (avoid noise)
DAILY_NOTIFICATION_HOUR = 18  # 6pm Egypt time
DAILY_TIMEZONE = "Africa/Cairo"


def load_price_history():
    """Load price history from JSON file"""
    if os.path.exists(PRICE_HISTORY_FILE):
        try:
            with open(PRICE_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_price_history(history):
    """Save price history to JSON file"""
    try:
        with open(PRICE_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        print(f"Error saving price history: {e}")


def load_daily_notification():
    """Load daily notification tracking data."""
    if os.path.exists(DAILY_NOTIFICATION_FILE):
        try:
            with open(DAILY_NOTIFICATION_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_daily_notification(tracking):
    """Save daily notification tracking data."""
    try:
        with open(DAILY_NOTIFICATION_FILE, "w") as f:
            json.dump(tracking, f, indent=2)
    except IOError as e:
        print(f"Error saving daily notification: {e}")


def should_send_daily_notification(now_local):
    """Return True if daily summary should be sent (once per day after 6pm Cairo time)."""
    if now_local.hour < DAILY_NOTIFICATION_HOUR:
        return False

    tracking = load_daily_notification()
    last_sent_date = tracking.get("last_sent_date")
    today = now_local.strftime("%Y-%m-%d")

    return last_sent_date != today


def record_daily_notification(now_local):
    """Record that today's daily summary was sent."""
    tracking = {"last_sent_date": now_local.strftime("%Y-%m-%d")}
    save_daily_notification(tracking)


def _format_daily_summary_message(now_local, gold_price_24k, usd_rate, gbp_rate, gold_candidate, fx_candidates):
    """Build a concise daily summary message."""
    date_str = now_local.strftime("%Y-%m-%d")
    lines = [f"🕕 <b>DAILY SUMMARY</b> ({date_str})", "=" * 40]
    lines.append("")

    # Prices snapshot
    lines.append("💰 <b>Current Prices</b>")
    if gold_price_24k is not None:
        lines.append(f"• Gold 24k: {gold_price_24k:.2f} EGP/gm")
    if usd_rate is not None:
        lines.append(f"• USD/EGP: {usd_rate:.2f}")
    if gbp_rate is not None:
        lines.append(f"• GBP/EGP: {gbp_rate:.2f}")

    lines.append("")

    # Signals summary
    signals = []
    if gold_candidate:
        signals.append(_format_signal_short(gold_candidate))
    if fx_candidates:
        for c in fx_candidates:
            signals.append(_format_signal_short(c))

    if signals:
        lines.append("📊 <b>Signals</b>")
        lines.extend(signals)
    else:
        lines.append("📊 <b>Signals</b>")
        lines.append("• No strong signals today")

    return "\n".join(lines)


def _get_signal_candidate(asset_type, display_name, current_price):
    """
    Update history for an asset and (optionally) return a signal candidate.

    Returns:
        dict | None:
          {
            "asset_type": "usd",
            "display_name": "USD/EGP",
            "signal": "BUY"|"SELL",
            "current_price": float,
            "analysis": dict,
          }
    """
    if current_price is None:
        return None

    # Add current price to history (include it in analysis)
    add_price_entry(asset_type, current_price)

    price_history = get_price_history_list(asset_type)

    # Need sufficient history for reliable signals
    if len(price_history) < MIN_HISTORY_FOR_SIGNALS:
        return None

    # Volatility filter: ignore if price range is too small (flat market)
    support, resistance = find_support_resistance(price_history, lookback=20)
    if support is not None and resistance is not None and resistance > support:
        mid_price = (support + resistance) / 2.0
        price_range = resistance - support
        if mid_price > 0:
            volatility_ratio = price_range / mid_price
            if volatility_ratio < MIN_VOLATILITY_RATIO:
                # Market is too flat; treat as no meaningful signal
                return None

    signal, analysis = get_trading_signal(price_history, current_price, MIN_HISTORY_FOR_SIGNALS)
    if not signal:
        return None

    return {
        "asset_type": asset_type,
        "display_name": display_name,
        "signal": signal,
        "current_price": current_price,
        "analysis": analysis,
    }

def _format_signal_short(candidate):
    """
    Create a short/concise one-liner style message for a single asset signal.
    """
    action = candidate["signal"]
    emoji = "🟢" if action == "BUY" else "🔴"
    name = candidate["display_name"]
    price = candidate["current_price"]
    analysis = candidate.get("analysis", {})
    indicators = analysis.get("indicators", {}) if isinstance(analysis, dict) else {}
    signal_count = analysis.get("buy_signals", 0) if action == "BUY" else analysis.get("sell_signals", 0)

    rsi = indicators.get("rsi")
    trend = indicators.get("trend")

    bits = []
    if isinstance(rsi, (int, float)):
        bits.append(f"RSI {rsi:.1f}")
    if trend:
        bits.append(f"Trend {str(trend).title()}")
    bits.append(f"Conf {signal_count}")

    details = " | ".join(bits)
    return f"{emoji} <b>{action}</b> {name} @ {price:.2f} ({details})"

def _format_fx_combined_short(candidates):
    """
    Create a single short message containing USD and/or GBP signals.
    """
    lines = ["💱 <b>CURRENCIES SIGNALS</b>"]
    for c in candidates:
        lines.append(_format_signal_short(c))
    return "\n".join(lines)


def add_price_entry(asset_type, price):
    """
    Add a new price entry to history
    
    Args:
        asset_type (str): Type of asset (e.g., "gold_24k", "usd", "gbp")
        price (float): Current price
    """
    history = load_price_history()
    
    if asset_type not in history:
        history[asset_type] = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "price": price
    }
    
    history[asset_type].append(entry)
    
    # Keep only the last MAX_HISTORY_ENTRIES entries
    if len(history[asset_type]) > MAX_HISTORY_ENTRIES:
        history[asset_type] = history[asset_type][-MAX_HISTORY_ENTRIES:]
    
    save_price_history(history)
    return history[asset_type]


def get_price_history_list(asset_type):
    """Get list of prices for an asset type (for analysis)"""
    history = load_price_history()
    if asset_type in history and len(history[asset_type]) > 0:
        return [entry["price"] for entry in history[asset_type]]
    return []


def get_latest_price(asset_type):
    """Get the latest price for an asset type"""
    history = load_price_history()
    if asset_type in history and len(history[asset_type]) > 0:
        return history[asset_type][-1]["price"]
    return None


def check_and_notify(asset_type, display_name, current_price):
    """
    Check if trading indicators trigger a buy/sell signal and send notification
    Uses real-world trading strategies: Moving Averages, RSI, Support/Resistance
    
    Args:
        asset_type (str): Internal asset type (e.g., "gold_24k")
        display_name (str): Display name for notifications (e.g., "Gold 24k")
        current_price (float): Current price
    """
    candidate = _get_signal_candidate(asset_type, display_name, current_price)
    if not candidate:
        return

    # Short & concise message
    message = _format_signal_short(candidate)
    send_telegram_message(message)


def format_trading_alert(asset_type, action, current_price, analysis):
    """
    Format a trading alert message with detailed analysis and beginner-friendly explanations
    
    Args:
        asset_type (str): Asset name
        action (str): "BUY" or "SELL"
        current_price (float): Current price
        analysis (dict): Analysis results from trading strategy
        
    Returns:
        str: Formatted message
    """
    emoji = "🟢" if action == "BUY" else "🔴"
    signal_count = analysis.get('buy_signals', 0) if action == 'BUY' else analysis.get('sell_signals', 0)
    
    message = f"{emoji} <b>{action} SIGNAL: {asset_type}</b>\n"
    message += "=" * 40 + "\n\n"
    
    # Current Price
    message += f"💰 <b>Current Price:</b> {current_price:.2f}\n\n"
    
    # What to do section
    if action == "BUY":
        message += "📋 <b>WHAT THIS MEANS:</b>\n"
        message += "Multiple indicators suggest this is a good time to BUY.\n"
        message += "The price may be at a low point and could rise soon.\n\n"
        message += "✅ <b>RECOMMENDED ACTION:</b>\n"
        message += "• Consider buying now if you were planning to invest\n"
        message += "• This could be a good entry point\n"
        message += "• However, always do your own research before investing\n\n"
    else:  # SELL
        message += "📋 <b>WHAT THIS MEANS:</b>\n"
        message += "Multiple indicators suggest this is a good time to SELL.\n"
        message += "The price may be at a high point and could drop soon.\n\n"
        message += "✅ <b>RECOMMENDED ACTION:</b>\n"
        message += "• Consider selling if you want to take profits\n"
        message += "• This could be a good exit point\n"
        message += "• However, always do your own research before selling\n\n"
    
    indicators = analysis.get("indicators", {})
    reasons = analysis.get("reasons", [])
    
    message += "📊 <b>TECHNICAL ANALYSIS:</b>\n\n"
    
    # Moving Averages explanation
    if indicators.get("sma_10") and indicators.get("sma_30"):
        sma_10 = indicators['sma_10']
        sma_30 = indicators['sma_30']
        message += f"📈 <b>Moving Averages (Trend Indicator):</b>\n"
        message += f"   • Short-term average (10 periods): {sma_10:.2f}\n"
        message += f"   • Long-term average (30 periods): {sma_30:.2f}\n"
        if sma_10 > sma_30:
            message += f"   → <i>Short-term is ABOVE long-term = Upward trend (Good for buying)</i>\n\n"
        else:
            message += f"   → <i>Short-term is BELOW long-term = Downward trend (Good for selling)</i>\n\n"
    
    # RSI explanation
    if indicators.get("rsi"):
        rsi = indicators["rsi"]
        message += f"📉 <b>RSI - Relative Strength Index:</b> {rsi:.1f}/100\n"
        if rsi < 30:
            message += f"   → <i>RSI is VERY LOW (Oversold) = Asset may be undervalued, good BUY opportunity</i>\n\n"
        elif rsi > 70:
            message += f"   → <i>RSI is VERY HIGH (Overbought) = Asset may be overvalued, good SELL opportunity</i>\n\n"
        elif rsi < 40:
            message += f"   → <i>RSI is LOW (Approaching oversold) = Could be a good time to buy</i>\n\n"
        elif rsi > 60:
            message += f"   → <i>RSI is HIGH (Approaching overbought) = Could be a good time to sell</i>\n\n"
        else:
            message += f"   → <i>RSI is NEUTRAL (40-60) = No strong signal</i>\n\n"
    
    # Support/Resistance explanation
    if indicators.get("support") and indicators.get("resistance"):
        support = indicators['support']
        resistance = indicators['resistance']
        price_range = resistance - support
        price_position = ((current_price - support) / price_range * 100) if price_range > 0 else 50
        
        message += f"🎯 <b>Price Levels:</b>\n"
        message += f"   • Support (Low point): {support:.2f}\n"
        message += f"   • Resistance (High point): {resistance:.2f}\n"
        message += f"   • Current position: {price_position:.1f}% of the range\n"
        
        if price_position < 30:
            message += f"   → <i>Price is NEAR SUPPORT (bottom) = Good time to BUY</i>\n\n"
        elif price_position > 70:
            message += f"   → <i>Price is NEAR RESISTANCE (top) = Good time to SELL</i>\n\n"
        else:
            message += f"   → <i>Price is in the MIDDLE = Neutral</i>\n\n"
    
    # Trend explanation
    if indicators.get("trend"):
        trend = indicators["trend"]
        trend_emoji = "📈" if trend == "bullish" else "📉"
        message += f"{trend_emoji} <b>Overall Trend:</b> {trend.title()}\n"
        if trend == "bullish":
            message += f"   → <i>Prices are generally going UP = Positive momentum</i>\n\n"
        else:
            message += f"   → <i>Prices are generally going DOWN = Negative momentum</i>\n\n"
    
    # Signal strength
    message += "🔍 <b>WHY THIS SIGNAL:</b>\n"
    if reasons:
        for i, reason in enumerate(reasons, 1):
            message += f"   {i}. {reason}\n"
    message += "\n"
    
    # Confidence level
    message += "💪 <b>CONFIDENCE LEVEL:</b>\n"
    if signal_count >= 4:
        message += f"   ⭐⭐⭐ <b>VERY STRONG</b> ({signal_count} confirmations)\n"
        message += "   → Multiple indicators strongly agree\n"
    elif signal_count >= 3:
        message += f"   ⭐⭐ <b>STRONG</b> ({signal_count} confirmations)\n"
        message += "   → Several indicators agree\n"
    else:
        message += f"   ⭐ <b>MODERATE</b> ({signal_count} confirmations)\n"
        message += "   → Some indicators agree\n"
    
    message += "\n"
    message += "⚠️ <b>IMPORTANT REMINDER:</b>\n"
    message += "This is an automated signal based on technical analysis.\n"
    message += "Always do your own research and consider your financial situation\n"
    message += "before making any investment decisions.\n"
    message += "Past performance does not guarantee future results."
    
    return message


def check_all_prices():
    """
    Check all tracked prices and send notifications if needed.
    This is the main function to call periodically.
    """
    now_local = datetime.now(ZoneInfo(DAILY_TIMEZONE))

    # Gold: only track 24k (same signal direction as 21k for our purposes)
    gold_price_24k, _gold_price_21k = get_gold_price()
    gold_candidate = None
    if gold_price_24k:
        gold_candidate = _get_signal_candidate("gold_24k", "Gold 24k (EGP/gm)", gold_price_24k)

    # Currencies: compute candidates, but send ONE combined message (max)
    fx_candidates = []
    usd_rate = get_official_usd_rate()
    if usd_rate:
        c = _get_signal_candidate("usd", "USD/EGP", usd_rate)
        if c:
            fx_candidates.append(c)

    gbp_rate = get_gbp_rate()
    if gbp_rate:
        c = _get_signal_candidate("gbp", "GBP/EGP", gbp_rate)
        if c:
            fx_candidates.append(c)

    # Daily summary notification (once per day after 6pm Egypt time)
    if not should_send_daily_notification(now_local):
        return

    msg = _format_daily_summary_message(
        now_local,
        gold_price_24k,
        usd_rate,
        gbp_rate,
        gold_candidate,
        fx_candidates
    )

    if send_telegram_message(msg):
        record_daily_notification(now_local)

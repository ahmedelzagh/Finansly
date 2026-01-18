"""
Price tracking and notification system for buy/sell signals
Uses real-world trading strategies: Moving Averages, RSI, Support/Resistance
"""
import json
import os
from datetime import datetime
from financial_utils import get_gold_price, get_official_usd_rate, get_gbp_rate
from telegram_utils import send_telegram_message, format_price_alert
from trading_strategy import get_trading_signal

# Configuration
PRICE_HISTORY_FILE = "price_history.json"
SIGNAL_TRACKING_FILE = "signal_tracking.json"  # Track last signals to avoid duplicates
MAX_HISTORY_ENTRIES = 200  # Keep more history for better analysis (need at least 30 for indicators)
MIN_HISTORY_FOR_SIGNALS = 30  # Minimum history required before sending signals
SIGNAL_COOLDOWN_HOURS = 6  # Don't send same signal type within this many hours


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


def load_signal_tracking():
    """Load signal tracking data"""
    if os.path.exists(SIGNAL_TRACKING_FILE):
        try:
            with open(SIGNAL_TRACKING_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_signal_tracking(tracking):
    """Save signal tracking data"""
    try:
        with open(SIGNAL_TRACKING_FILE, 'w') as f:
            json.dump(tracking, f, indent=2)
    except IOError as e:
        print(f"Error saving signal tracking: {e}")


def should_send_signal(asset_type, signal_type):
    """
    Check if we should send a signal (avoid duplicates within cooldown period)
    
    Args:
        asset_type: Asset type
        signal_type: "BUY" or "SELL"
        
    Returns:
        bool: True if signal should be sent
    """
    tracking = load_signal_tracking()
    key = f"{asset_type}_{signal_type}"
    
    if key not in tracking:
        return True
    
    last_signal_time = tracking[key]
    from datetime import datetime, timedelta
    
    try:
        last_time = datetime.strptime(last_signal_time, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_time
        
        # Only send if cooldown period has passed
        if time_diff.total_seconds() < (SIGNAL_COOLDOWN_HOURS * 3600):
            return False
    except:
        # If parsing fails, allow signal
        pass
    
    return True


def record_signal(asset_type, signal_type):
    """Record that a signal was sent"""
    tracking = load_signal_tracking()
    key = f"{asset_type}_{signal_type}"
    tracking[key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_signal_tracking(tracking)


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
    if current_price is None:
        return
    
    # Get price history for analysis
    price_history = get_price_history_list(asset_type)
    
    # Add current price to history (before analysis to include it)
    add_price_entry(asset_type, current_price)
    
    # Get updated history with current price
    price_history = get_price_history_list(asset_type)
    
    # Need sufficient history for reliable signals
    if len(price_history) < MIN_HISTORY_FOR_SIGNALS:
        return
    
    # Get trading signal using multiple indicators
    signal, analysis = get_trading_signal(price_history, current_price, MIN_HISTORY_FOR_SIGNALS)
    
    if signal:
        # Check if we should send this signal (avoid duplicates)
        if should_send_signal(asset_type, signal):
            # Format detailed message with analysis
            message = format_trading_alert(display_name, signal, current_price, analysis)
            if send_telegram_message(message):
                # Record that signal was sent
                record_signal(asset_type, signal)


def format_trading_alert(asset_type, action, current_price, analysis):
    """
    Format a trading alert message with detailed analysis
    
    Args:
        asset_type (str): Asset name
        action (str): "BUY" or "SELL"
        current_price (float): Current price
        analysis (dict): Analysis results from trading strategy
        
    Returns:
        str: Formatted message
    """
    emoji = "🟢" if action == "BUY" else "🔴"
    
    message = f"{emoji} <b>{action} Signal: {asset_type}</b>\n\n"
    message += f"💰 Current Price: {current_price:.2f}\n\n"
    
    indicators = analysis.get("indicators", {})
    reasons = analysis.get("reasons", [])
    
    # Add indicator values
    if indicators.get("sma_10") and indicators.get("sma_30"):
        message += f"📊 Moving Averages:\n"
        message += f"   • SMA 10: {indicators['sma_10']:.2f}\n"
        message += f"   • SMA 30: {indicators['sma_30']:.2f}\n\n"
    
    if indicators.get("rsi"):
        rsi = indicators["rsi"]
        rsi_status = "🔴 Overbought" if rsi > 70 else "🟢 Oversold" if rsi < 30 else "🟡 Neutral"
        message += f"📈 RSI: {rsi:.1f} ({rsi_status})\n\n"
    
    if indicators.get("support") and indicators.get("resistance"):
        message += f"📉 Support: {indicators['support']:.2f}\n"
        message += f"📈 Resistance: {indicators['resistance']:.2f}\n\n"
    
    if indicators.get("trend"):
        trend_emoji = "📈" if indicators["trend"] == "bullish" else "📉"
        message += f"{trend_emoji} Trend: {indicators['trend'].title()}\n\n"
    
    # Add reasons for the signal
    if reasons:
        message += f"✅ <b>Signal Reasons:</b>\n"
        for reason in reasons:
            message += f"   • {reason}\n"
    
    message += f"\n💡 <i>Requires {analysis.get('buy_signals', 0) if action == 'BUY' else analysis.get('sell_signals', 0)} confirmations</i>"
    
    return message


def check_all_prices():
    """
    Check all tracked prices and send notifications if needed.
    This is the main function to call periodically.
    """
    # Check Gold prices
    gold_price_24k, gold_price_21k = get_gold_price()
    if gold_price_24k:
        check_and_notify("gold_24k", "Gold 24k (EGP/gm)", gold_price_24k)
    if gold_price_21k:
        check_and_notify("gold_21k", "Gold 21k (EGP/gm)", gold_price_21k)
    
    # Check USD rate
    usd_rate = get_official_usd_rate()
    if usd_rate:
        check_and_notify("usd", "USD/EGP", usd_rate)
    
    # Check GBP rate
    gbp_rate = get_gbp_rate()
    if gbp_rate:
        check_and_notify("gbp", "GBP/EGP", gbp_rate)

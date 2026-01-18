"""
Price tracking and notification system for buy/sell signals
"""
import json
import os
from datetime import datetime
from financial_utils import get_gold_price, get_official_usd_rate, get_gbp_rate
from telegram_utils import send_telegram_message, format_price_alert

# Configuration
PRICE_HISTORY_FILE = "price_history.json"
BUY_THRESHOLD_PERCENT = -2.0  # Buy when price drops 2% or more
SELL_THRESHOLD_PERCENT = 2.0   # Sell when price rises 2% or more
MAX_HISTORY_ENTRIES = 100  # Keep last 100 price entries


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


def get_latest_price(asset_type):
    """Get the latest price for an asset type"""
    history = load_price_history()
    if asset_type in history and len(history[asset_type]) > 0:
        return history[asset_type][-1]["price"]
    return None


def calculate_price_change(current_price, previous_price):
    """Calculate percentage change between two prices"""
    if previous_price is None or previous_price == 0:
        return None
    return ((current_price - previous_price) / previous_price) * 100


def check_and_notify(asset_type, display_name, current_price):
    """
    Check if price change triggers a buy/sell signal and send notification
    
    Args:
        asset_type (str): Internal asset type (e.g., "gold_24k")
        display_name (str): Display name for notifications (e.g., "Gold 24k")
        current_price (float): Current price
    """
    if current_price is None:
        return
    
    previous_price = get_latest_price(asset_type)
    change_percent = calculate_price_change(current_price, previous_price)
    
    # Add current price to history
    add_price_entry(asset_type, current_price)
    
    # If no previous price, just store and return (first time tracking)
    if previous_price is None:
        return
    
    # Check for buy signal (price dropped significantly)
    if change_percent <= BUY_THRESHOLD_PERCENT:
        message = format_price_alert(
            display_name, 
            "BUY", 
            current_price, 
            previous_price, 
            change_percent
        )
        send_telegram_message(message)
    
    # Check for sell signal (price rose significantly)
    elif change_percent >= SELL_THRESHOLD_PERCENT:
        message = format_price_alert(
            display_name, 
            "SELL", 
            current_price, 
            previous_price, 
            change_percent
        )
        send_telegram_message(message)


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

"""
Telegram notification utilities for price alerts
"""
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message, chat_id=None):
    """
    Send a message via Telegram bot.
    
    Args:
        message (str): The message to send
        chat_id (str/int, optional): Chat ID to send to. If None, uses TELEGRAM_CHAT_ID
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        print("Warning: Telegram bot token not configured. Skipping notification.")
        return False
    
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id:
        print("Warning: Telegram chat ID not configured. Skipping notification.")
        return False
    
    try:
        telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(telegram_api_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        # Get more details from the error response
        try:
            error_details = response.json()
            print(f"Error sending Telegram message: {e}")
            print(f"Telegram API response: {error_details}")
        except:
            print(f"Error sending Telegram message: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False


def format_price_alert(asset_type, action, current_price, previous_price=None, change_percent=None):
    """
    Format a price alert message for Telegram.
    
    Args:
        asset_type (str): Type of asset (e.g., "Gold 24k", "USD", "GBP")
        action (str): Action recommendation ("BUY" or "SELL")
        current_price (float): Current price
        previous_price (float, optional): Previous price for comparison
        change_percent (float, optional): Percentage change
        
    Returns:
        str: Formatted message
    """
    emoji = "🟢" if action == "BUY" else "🔴"
    
    message = f"{emoji} <b>{action} Signal: {asset_type}</b>\n\n"
    message += f"Current Price: {current_price}\n"
    
    if previous_price and change_percent:
        direction = "📉" if change_percent < 0 else "📈"
        message += f"{direction} Previous: {previous_price}\n"
        message += f"Change: {change_percent:+.2f}%\n"
    
    return message

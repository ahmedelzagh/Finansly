"""
Script to set up Telegram webhook
Run this once to configure your bot to receive commands
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com/telegram-webhook")

def set_webhook():
    """Set Telegram webhook URL"""
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {"url": WEBHOOK_URL}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Webhook set successfully!")
            print(f"URL: {WEBHOOK_URL}")
        else:
            print(f"❌ Error: {result.get('description')}")
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")

if __name__ == "__main__":
    print("Setting up Telegram webhook...")
    print(f"Make sure WEBHOOK_URL in .env points to your server")
    print(f"Example: https://your-domain.com/telegram-webhook")
    print()
    set_webhook()

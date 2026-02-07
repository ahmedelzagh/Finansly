"""
Telegram Bot Command Handler
Handles bot commands like /paypal <amount>
"""
import os
import json
import hmac
import hashlib
from flask import request, jsonify
from dotenv import load_dotenv
from telegram_utils import send_telegram_message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from paypal_transfer_calculator import check_paypal_transfer, format_paypal_transfer_message, calculate_paypal_transfer

load_dotenv()

# Webhook secret token from environment
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


def verify_telegram_webhook(data_bytes, secret_hash_header):
    """
    Verify Telegram webhook request using X-Telegram-Bot-API-Secret-Hash header.
    Returns True if signature is valid, False otherwise.
    
    If TELEGRAM_WEBHOOK_SECRET is not configured, returns True (no verification).
    """
    if not TELEGRAM_WEBHOOK_SECRET:
        # No secret configured, skip verification
        return True
    
    if not secret_hash_header:
        # No signature provided when secret is configured
        return False
    
    # Calculate expected hash: HMAC-SHA256(data, secret)
    expected_hash = hmac.new(
        TELEGRAM_WEBHOOK_SECRET.encode(),
        data_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Compare hashes (constant time to prevent timing attacks)
    return hmac.compare_digest(expected_hash, secret_hash_header)


def handle_telegram_webhook():
    """
    Handle incoming Telegram webhook messages.
    Verifies request signature before processing.
    Processes bot commands and sends responses.
    """
    try:
        # Get raw request data for signature verification
        data_bytes = request.get_data()
        secret_hash = request.headers.get("X-Telegram-Bot-API-Secret-Hash", "")
        
        # Verify webhook authenticity
        if not verify_telegram_webhook(data_bytes, secret_hash):
            return jsonify({"error": "Invalid signature"}), 403
        
        data = request.get_json()
        
        # Telegram sends updates in this format
        if "message" not in data:
            return jsonify({"ok": True})
        
        message = data["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        
        # Only process messages from authorized chat
        if str(chat_id) != str(TELEGRAM_CHAT_ID):
            return jsonify({"ok": True})
        
        # Handle /paypal command
        if text.startswith("/paypal") or text.startswith("/paypal@"):
            # Extract amount from command
            parts = text.split()
            if len(parts) < 2:
                send_telegram_message(
                    "❌ <b>Usage:</b> /paypal &lt;amount&gt;\n\n"
                    "Example: /paypal 1000\n"
                    "This will check if manual transfer (150 EGP tax) is worth it vs waiting for auto-transfer.",
                    chat_id=chat_id
                )
                return jsonify({"ok": True})
            
            try:
                amount = float(parts[1])
                if amount <= 0:
                    send_telegram_message("❌ Amount must be greater than 0", chat_id=chat_id)
                    return jsonify({"ok": True})
                
                # Send "calculating" message
                send_telegram_message("⏳ Calculating transfer decision...", chat_id=chat_id)
                
                # Calculate and send result
                decision = calculate_paypal_transfer(amount)
                if decision:
                    message_text = format_paypal_transfer_message(decision)
                    send_telegram_message(message_text, chat_id=chat_id)
                else:
                    send_telegram_message("❌ Error: Could not calculate transfer decision. Check GBP rate availability.", chat_id=chat_id)
                    
            except ValueError:
                send_telegram_message(f"❌ Invalid amount: '{parts[1]}'. Please provide a number.\n\nExample: /paypal 1000", chat_id=chat_id)
            except Exception as e:
                send_telegram_message(f"❌ Error: {str(e)}", chat_id=chat_id)
        
        # Handle /help command
        elif text.startswith("/help") or text.startswith("/start"):
            help_message = (
                "🤖 <b>Finansly Bot Commands</b>\n\n"
                "📊 <b>/paypal &lt;amount&gt;</b>\n"
                "Check if manual PayPal transfer is worth it\n"
                "Example: /paypal 1000\n\n"
                "This calculates whether to:\n"
                "• Transfer manually now (150 EGP tax)\n"
                "• OR wait for auto-transfer on 1st (no tax)\n\n"
                "The bot will compare current rate vs estimated future rate and tell you which option saves more money."
            )
            send_telegram_message(help_message, chat_id=chat_id)
        
        return jsonify({"ok": True})
        
    except Exception as e:
        print(f"Error handling Telegram webhook: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

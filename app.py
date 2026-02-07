from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
import os
import threading
import time
from functools import wraps
from openpyxl import load_workbook
from datetime import datetime
from dotenv import load_dotenv
import secrets
from financial_utils import (
    get_gold_price, get_official_usd_rate, save_to_excel,
    detect_excel_format, normalize_row_to_new_format, get_column_index,
    round_numeric_value, NEW_FORMAT_HEADERS, COL_TIMESTAMP, ensure_excel_format_migrated
)
from price_tracker import check_all_prices

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
Session(app)

# Ensure Excel file is properly migrated on startup
ensure_excel_format_migrated("financial_summary.xlsx")

# Authentication credentials from environment variables
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

if not APP_USERNAME or not APP_PASSWORD:
    raise RuntimeError("APP_USERNAME and APP_PASSWORD must be set in environment variables.")

def generate_csrf_token():
    """Generate a new CSRF token and store it in session"""
    token = secrets.token_urlsafe(32)
    session['csrf_token'] = token
    return token

def get_csrf_token():
    """Get existing CSRF token or generate a new one"""
    if 'csrf_token' not in session:
        return generate_csrf_token()
    return session['csrf_token']

def verify_csrf_token(token):
    """Verify CSRF token from form submission"""
    session_token = session.get('csrf_token')
    if not session_token or not token:
        return False
    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(session_token, token)

def login_required(f):
    """Decorator to protect routes that require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page"""
    if request.method == "POST":
        # Verify CSRF token
        csrf_token = request.form.get("csrf_token")
        if not verify_csrf_token(csrf_token):
            return render_template("login.html", error="Invalid security token. Please try again.", csrf_token=get_csrf_token())
        
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid username or password", csrf_token=get_csrf_token())
    
    # If already logged in, redirect to index
    if session.get("logged_in"):
        return redirect(url_for("index"))
    
    return render_template("login.html", csrf_token=get_csrf_token())

@app.route("/logout")
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        # Verify CSRF token
        csrf_token = request.form.get("csrf_token")
        if not verify_csrf_token(csrf_token):
            return render_template("index.html", error="Invalid security token. Please try again.", csrf_token=get_csrf_token())
        
        try:
            # Get 24k gold holdings (optional)
            gold_holdings_24k = None
            if request.form.get("gold_holdings_24k"):
                try:
                    value = float(request.form["gold_holdings_24k"])
                    if value < 0:
                        return render_template("index.html", error="Gold 24k holdings cannot be negative.", csrf_token=get_csrf_token())
                    gold_holdings_24k = round(value, 2)
                except ValueError:
                    return render_template("index.html", error="Gold 24k holdings must be a valid number.", csrf_token=get_csrf_token())
            
            # Get 21k gold holdings (optional)
            gold_holdings_21k = None
            if request.form.get("gold_holdings_21k"):
                try:
                    value = float(request.form["gold_holdings_21k"])
                    if value < 0:
                        return render_template("index.html", error="Gold 21k holdings cannot be negative.", csrf_token=get_csrf_token())
                    gold_holdings_21k = round(value, 2)
                except ValueError:
                    return render_template("index.html", error="Gold 21k holdings must be a valid number.", csrf_token=get_csrf_token())
            
            # USD balance is required
            if not request.form.get("usd_balance"):
                return render_template("index.html", error="USD Balance is required.", csrf_token=get_csrf_token())
            
            try:
                usd_value = float(request.form["usd_balance"])
                if usd_value < 0:
                    return render_template("index.html", error="USD Balance cannot be negative.", csrf_token=get_csrf_token())
                usd_balance = round(usd_value, 2)
            except ValueError:
                return render_template("index.html", error="USD Balance must be a valid number.", csrf_token=get_csrf_token())

            # Fetch both 24k and 21k gold prices
            gold_price_24k, gold_price_21k = get_gold_price()
            official_usd_rate = get_official_usd_rate()

            if (gold_price_24k or gold_price_21k) and official_usd_rate:
                # Calculate total gold value by combining both 24k and 21k holdings
                total_gold_value_egp = 0.0
                if gold_holdings_24k and gold_price_24k:
                    total_gold_value_egp += gold_holdings_24k * gold_price_24k
                if gold_holdings_21k and gold_price_21k:
                    total_gold_value_egp += gold_holdings_21k * gold_price_21k
                # Round the final total to avoid floating point precision issues
                total_gold_value_egp = round(total_gold_value_egp, 2)
                
                total_usd_value_egp = round(usd_balance * official_usd_rate, 2)
                total_wealth_egp = round(total_gold_value_egp + total_usd_value_egp, 2)

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_to_excel(
                current_timestamp, gold_holdings_24k, gold_holdings_21k, usd_balance,
                gold_price_24k, gold_price_21k, official_usd_rate,
                total_gold_value_egp, total_usd_value_egp, total_wealth_egp
            )

            # Store in session
            session["gold_holdings_24k"] = gold_holdings_24k
            session["gold_holdings_21k"] = gold_holdings_21k
            session["usd_balance"] = usd_balance
            session["gold_price_24k"] = gold_price_24k
            session["gold_price_21k"] = gold_price_21k
            session["official_usd_rate"] = official_usd_rate
            session["total_gold_value_egp"] = total_gold_value_egp
            session["total_usd_value_egp"] = total_usd_value_egp
            session["total_wealth_egp"] = total_wealth_egp

            return redirect(url_for("index"))
        except Exception as e:
            return render_template("index.html", error=f"An error occurred: {str(e)}", csrf_token=get_csrf_token())

    # Load data from Excel with backward compatibility
    file_path = "financial_summary.xlsx"
    headers = NEW_FORMAT_HEADERS  # Default to new format headers
    data = []
    timestamp_col_index = 0  # Default index for timestamp column
    
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
        existing_headers = [cell.value for cell in sheet[1]]
        
        # Normalize headers and data based on format
        file_format = detect_excel_format(file_path)
        if file_format == 'old':
            # Use new format headers for display, but normalize old data
            headers = NEW_FORMAT_HEADERS
        else:
            headers = existing_headers if len(existing_headers) == 10 else NEW_FORMAT_HEADERS
        
        # Get timestamp column index by name
        timestamp_col_index = get_column_index(headers, COL_TIMESTAMP)
        if timestamp_col_index is None:
            timestamp_col_index = 0  # Fallback to first column
        
        # Read and normalize rows
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row:  # Skip empty rows
                normalized_row = normalize_row_to_new_format(row, existing_headers)
                # Convert dictionary to list in header order and round numeric values
                data_row = []
                for header in headers:
                    value = normalized_row.get(header, None)
                    # Round numeric values to 2 decimal places (except timestamp)
                    if header != COL_TIMESTAMP:
                        value = round_numeric_value(value, 2)
                    data_row.append(value)
                # Extract timestamp for delete button (always at timestamp_col_index)
                timestamp_value = data_row[timestamp_col_index] if timestamp_col_index < len(data_row) else None
                data.append({
                    'row': data_row,
                    'timestamp': timestamp_value
                })
        
        data.reverse()  # Reverse the order to show latest details on top

    return render_template("index.html", headers=headers, data=data, csrf_token=get_csrf_token())

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    """Handle Telegram bot webhook"""
    from telegram_bot import handle_telegram_webhook
    return handle_telegram_webhook()

@app.route("/paypal-check", methods=["GET", "POST"])
@login_required
def paypal_check():
    """Check PayPal transfer decision for given GBP amount (web interface)"""
    from paypal_transfer_calculator import check_paypal_transfer
    
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
    else:
        try:
            amount = float(request.args.get("amount", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount. Use ?amount=1000"}), 400
    
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    
    # Calculate and send to Telegram
    decision = check_paypal_transfer(amount, send_to_telegram=True)
    
    if decision:
        return jsonify({
            "success": True,
            "message": "Check sent to Telegram",
            "recommendation": decision["recommendation"],
            "difference_egp": decision["difference"]
        })
    else:
        return jsonify({"error": "Could not calculate transfer decision"}), 500

@app.route("/delete/<timestamp>", methods=["DELETE"])
@login_required
def delete_entry(timestamp):
    try:
        if not timestamp or len(timestamp) == 0:
            return jsonify({"error": "Invalid timestamp"}), 400
        
        file_path = "financial_summary.xlsx"
        if not os.path.exists(file_path):
            return jsonify({"error": "No data file found"}), 404
        
        try:
            workbook = load_workbook(file_path)
            sheet = workbook.active
            headers = [cell.value for cell in sheet[1]]
            
            # Find timestamp column by name instead of index
            timestamp_col_index = get_column_index(headers, COL_TIMESTAMP)
            if timestamp_col_index is None:
                # Fallback: try to find by old column name
                timestamp_col_index = get_column_index(headers, "Date")
                if timestamp_col_index is None:
                    timestamp_col_index = 0  # Final fallback to first column
            
            # Search for matching timestamp
            found = False
            for row in sheet.iter_rows(min_row=2):  # Skip header row
                if row[timestamp_col_index].value == timestamp:
                    sheet.delete_rows(row[timestamp_col_index].row)
                    workbook.save(file_path)
                    found = True
                    break
            
            if not found:
                return jsonify({"error": "Entry not found"}), 404
            
            return jsonify(success=True)
        except Exception as e:
            return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred"}), 500

def background_price_checker():
    """Background thread to check prices periodically"""
    # Wait a bit before starting to let Flask app initialize
    time.sleep(30)
    
    # Check prices every 8 hours (to fit GoldAPI 100 req/month limit)
    CHECK_INTERVAL = 8 * 60 * 60
    
    while True:
        try:
            check_all_prices()
        except Exception as e:
            print(f"Error in background price checker: {e}")
        
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    # Start background price checking thread
    price_checker_thread = threading.Thread(target=background_price_checker, daemon=True)
    price_checker_thread.start()
    
    # Run Flask app - bind to all interfaces for Docker
    app.run(host='0.0.0.0', port=5000, debug=False)

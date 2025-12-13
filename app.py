from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
import os
from openpyxl import load_workbook
from datetime import datetime
from financial_utils import (
    get_gold_price, get_official_usd_rate, save_to_excel,
    detect_excel_format, normalize_row_to_new_format, get_column_index,
    NEW_FORMAT_HEADERS, COL_TIMESTAMP
)

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = os.urandom(24)
Session(app)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get 24k gold holdings (optional)
        gold_holdings_24k = None
        if request.form.get("gold_holdings_24k"):
            gold_holdings_24k = round(float(request.form["gold_holdings_24k"]), 2)
        
        # Get 21k gold holdings (optional)
        gold_holdings_21k = None
        if request.form.get("gold_holdings_21k"):
            gold_holdings_21k = round(float(request.form["gold_holdings_21k"]), 2)
        
        # USD balance is required
        usd_balance = round(float(request.form["usd_balance"]), 2)

        # Fetch both 24k and 21k gold prices
        gold_price_24k, gold_price_21k = get_gold_price()
        official_usd_rate = get_official_usd_rate()

        if (gold_price_24k or gold_price_21k) and official_usd_rate:
            # Calculate total gold value by combining both 24k and 21k holdings
            total_gold_value_egp = 0
            if gold_holdings_24k and gold_price_24k:
                total_gold_value_egp += round(gold_holdings_24k * gold_price_24k, 2)
            if gold_holdings_21k and gold_price_21k:
                total_gold_value_egp += round(gold_holdings_21k * gold_price_21k, 2)
            
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
                # Convert dictionary to list in header order
                data_row = [normalized_row.get(header, None) for header in headers]
                # Extract timestamp for delete button (always at timestamp_col_index)
                timestamp_value = data_row[timestamp_col_index] if timestamp_col_index < len(data_row) else None
                data.append({
                    'row': data_row,
                    'timestamp': timestamp_value
                })
        
        data.reverse()  # Reverse the order to show latest details on top

    return render_template("index.html", headers=headers, data=data)

@app.route("/delete/<timestamp>", methods=["DELETE"])
def delete_entry(timestamp):
    file_path = "financial_summary.xlsx"
    if os.path.exists(file_path):
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
        for row in sheet.iter_rows(min_row=2):  # Skip header row
            if row[timestamp_col_index].value == timestamp:
                sheet.delete_rows(row[timestamp_col_index].row)
                workbook.save(file_path)
                return jsonify(success=True)
    return jsonify(success=False), 404

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
import os
from openpyxl import load_workbook
from datetime import datetime
from financial_utils import get_gold_price, get_official_usd_rate, save_to_excel

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = os.urandom(24)
Session(app)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        gold_holdings = round(float(request.form["gold_holdings"]), 2)
        usd_balance = round(float(request.form["usd_balance"]), 2)

        gold_price_per_gram = get_gold_price()
        official_usd_rate = get_official_usd_rate()

        if gold_price_per_gram and official_usd_rate:
            total_gold_value_egp = round(gold_holdings * gold_price_per_gram, 2)
            total_usd_value_egp = round(usd_balance * official_usd_rate, 2)
            total_wealth_egp = round(total_gold_value_egp + total_usd_value_egp, 2)

            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_to_excel(current_date, gold_holdings, usd_balance, gold_price_per_gram, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp)

            session["gold_holdings"] = gold_holdings
            session["usd_balance"] = usd_balance
            session["gold_price_per_gram"] = gold_price_per_gram
            session["official_usd_rate"] = official_usd_rate
            session["total_gold_value_egp"] = total_gold_value_egp
            session["total_usd_value_egp"] = total_usd_value_egp
            session["total_wealth_egp"] = total_wealth_egp

            return redirect(url_for("index"))

    headers = ["Timestamp", "Gold Holdings (grams)", "USD Balance", "Gold Price (EGP/gm)", "Official USD Rate", "Total Gold Value (EGP)", "Total USD Value (EGP)", "Total Wealth (EGP)"]
    data = []
    file_path = "financial_summary.xlsx"
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        for row in sheet.iter_rows(values_only=True):
            data.append(row)
        data = data[1:]  # Exclude the first row (header names)
        data.reverse()  # Reverse the order to show latest details on top

    return render_template("index.html", headers=headers, data=data)

@app.route("/delete/<timestamp>", methods=["DELETE"])
def delete_entry(timestamp):
    file_path = "financial_summary.xlsx"
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
        for row in sheet.iter_rows(min_row=2):  # Skip header row
            if row[0].value == timestamp:
                sheet.delete_rows(row[0].row)
                workbook.save(file_path)
                return jsonify(success=True)
    return jsonify(success=False), 404

if __name__ == "__main__":
    app.run(debug=True)

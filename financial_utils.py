import requests
import os
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook
from datetime import datetime

# Load environment variables
load_dotenv()
GOLD_API_KEY = os.getenv("GOLD_API_KEY")

# API Endpoints
GOLD_API_URL = "https://www.goldapi.io/api/XAU/EGP"
CB_EGP_USD_URL = "https://api.exchangerate-api.com/v4/latest/USD"  # Central Bank Rate

# Constants
TROY_OUNCE_TO_GRAM = 31.1035  # 1 Troy Ounce = 31.1035 grams

# Column name constants for Excel file structure
COL_TIMESTAMP = "Timestamp"
COL_GOLD_24K_HOLDINGS = "Gold Holdings 24k (grams)"
COL_GOLD_21K_HOLDINGS = "Gold Holdings 21k (grams)"
COL_USD_BALANCE = "USD Balance"
COL_GOLD_24K_PRICE = "Gold Price 24k (EGP/gm)"
COL_GOLD_21K_PRICE = "Gold Price 21k (EGP/gm)"
COL_OFFICIAL_USD_RATE = "Official USD Rate"
COL_TOTAL_GOLD_VALUE = "Total Gold Value (EGP)"
COL_TOTAL_USD_VALUE = "Total USD Value (EGP)"
COL_TOTAL_WEALTH = "Total Wealth (EGP)"

# Old format column names (for backward compatibility)
COL_OLD_DATE = "Date"
COL_OLD_GOLD_HOLDINGS = "Gold Holdings (grams)"
COL_OLD_GOLD_PRICE = "Gold Price (EGP/gm)"

# New format headers (10 columns)
NEW_FORMAT_HEADERS = [
    COL_TIMESTAMP,
    COL_GOLD_24K_HOLDINGS,
    COL_GOLD_21K_HOLDINGS,
    COL_USD_BALANCE,
    COL_GOLD_24K_PRICE,
    COL_GOLD_21K_PRICE,
    COL_OFFICIAL_USD_RATE,
    COL_TOTAL_GOLD_VALUE,
    COL_TOTAL_USD_VALUE,
    COL_TOTAL_WEALTH
]

# Old format headers (8 columns)
OLD_FORMAT_HEADERS = [
    COL_OLD_DATE,
    COL_OLD_GOLD_HOLDINGS,
    COL_USD_BALANCE,
    COL_OLD_GOLD_PRICE,
    COL_OFFICIAL_USD_RATE,
    COL_TOTAL_GOLD_VALUE,
    COL_TOTAL_USD_VALUE,
    COL_TOTAL_WEALTH
]

# Function to fetch gold prices in EGP per gram (both 24k and 21k)
def get_gold_price():
    """
    Fetches both 24k and 21k gold prices from the API.
    Returns a tuple (price_24k, price_21k) or (None, None) on error.
    If 21k price is not available from API, calculates it as 21/24 of 24k price.
    """
    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(GOLD_API_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        price_gram_24k = data.get("price_gram_24k", None)
        price_gram_21k = data.get("price_gram_21k", None)

        if price_gram_24k:
            price_24k = round(price_gram_24k, 2)
            # If 21k price is not available from API, calculate it as 21/24 of 24k price
            if price_gram_21k:
                price_21k = round(price_gram_21k, 2)
            else:
                price_21k = round(price_gram_24k * (21 / 24), 2)
            return (price_24k, price_21k)
        return (None, None)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching gold price: {e}")
        return (None, None)

# Function to fetch official USD to EGP rate
def get_official_usd_rate():
    try:
        response = requests.get(CB_EGP_USD_URL)
        response.raise_for_status()
        return round(response.json()["rates"].get("EGP", 0), 2)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching official USD rate: {e}")
        return None

# Function to save data to Excel
def save_to_excel(date, gold_holdings, usd_balance, gold_price_per_gram, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp):
    file_path = "financial_summary.xlsx"
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Date", "Gold Holdings (grams)", "USD Balance", "Gold Price (EGP/gm)", "Official USD Rate", "Total Gold Value (EGP)", "Total USD Value (EGP)", "Total Wealth (EGP)"])

    sheet.append([date, gold_holdings, usd_balance, gold_price_per_gram, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp])
    workbook.save(file_path)

if __name__ == "__main__":
    # User assets
    GOLD = round(float(input("Enter your gold holdings (grams): ")), 2)  # Gold in grams
    USD = round(float(input("Enter your USD balance: ")), 2)  # Money in USD

    # Fetch prices
    gold_price_24k, gold_price_21k = get_gold_price()
    official_usd_rate = get_official_usd_rate()

    if gold_price_24k and official_usd_rate:
        total_gold_value_egp = round(GOLD * gold_price_24k, 2)
        total_usd_value_egp = round(USD * official_usd_rate, 2)
        total_wealth_egp = round(total_gold_value_egp + total_usd_value_egp, 2)

        print("\n--- Financial Summary ---")
        print(f"Gold Price 24k (EGP/gm): {gold_price_24k}")
        print(f"Gold Price 21k (EGP/gm): {gold_price_21k}")
        print(f"Official USD Rate: {official_usd_rate}")
        print(f"Total Gold Value (EGP): {total_gold_value_egp}")
        print(f"Total USD Value (EGP): {total_usd_value_egp}")
        print(f"Total Wealth (EGP): {total_wealth_egp}")

        # Note: save_to_excel will be updated in next step
        # save_to_excel(current_date, GOLD, USD, gold_price_24k, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp)
    else:
        print("Could not fetch one or more price values.")

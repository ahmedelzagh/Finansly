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
def save_to_excel(timestamp, gold_holdings_24k, gold_holdings_21k, usd_balance, gold_price_24k, gold_price_21k, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp):
    """
    Saves financial data to Excel file with new format (10 columns).
    If file exists with old format, updates headers to new format.
    """
    file_path = "financial_summary.xlsx"
    
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
        # Check if headers need to be updated (old format detection)
        existing_headers = [cell.value for cell in sheet[1]]
        if len(existing_headers) == 8 and existing_headers == OLD_FORMAT_HEADERS:
            # Update headers to new format
            for col_idx, new_header in enumerate(NEW_FORMAT_HEADERS, start=1):
                sheet.cell(row=1, column=col_idx, value=new_header)
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(NEW_FORMAT_HEADERS)

    # Append new row with all 10 columns
    sheet.append([
        timestamp,
        gold_holdings_24k if gold_holdings_24k is not None else None,
        gold_holdings_21k if gold_holdings_21k is not None else None,
        usd_balance,
        gold_price_24k if gold_price_24k is not None else None,
        gold_price_21k if gold_price_21k is not None else None,
        official_usd_rate,
        total_gold_value_egp,
        total_usd_value_egp,
        total_wealth_egp
    ])
    workbook.save(file_path)

# Function to detect Excel file format (old or new)
def detect_excel_format(file_path):
    """
    Detects whether Excel file uses old format (8 columns) or new format (10 columns).
    Returns 'old' or 'new'.
    """
    if not os.path.exists(file_path):
        return 'new'  # Default to new format for new files
    
    workbook = load_workbook(file_path)
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    
    if len(headers) == 8:
        return 'old'
    elif len(headers) == 10:
        return 'new'
    else:
        # Unknown format, default to new
        return 'new'

# Function to normalize old format row to new format
def normalize_row_to_new_format(row, headers):
    """
    Converts a row from old format (8 columns) to new format (10 columns).
    Returns a dictionary with column names as keys.
    """
    if len(headers) == 8 and len(row) == 8:
        # Old format detected
        return {
            COL_TIMESTAMP: row[0],  # Date -> Timestamp
            COL_GOLD_24K_HOLDINGS: row[1],  # Gold Holdings (grams) -> Gold Holdings 24k (grams)
            COL_GOLD_21K_HOLDINGS: None,  # Not in old format
            COL_USD_BALANCE: row[2],
            COL_GOLD_24K_PRICE: row[3],  # Gold Price (EGP/gm) -> Gold Price 24k (EGP/gm)
            COL_GOLD_21K_PRICE: None,  # Not in old format
            COL_OFFICIAL_USD_RATE: row[4],
            COL_TOTAL_GOLD_VALUE: row[5],
            COL_TOTAL_USD_VALUE: row[6],
            COL_TOTAL_WEALTH: row[7]
        }
    elif len(headers) == 10 and len(row) == 10:
        # New format - convert to dictionary
        return dict(zip(headers, row))
    else:
        # Unknown format, return as dictionary
        return dict(zip(headers, row))

# Function to get column index by name
def get_column_index(headers, column_name):
    """
    Returns the index of a column by its name.
    Returns None if column not found.
    """
    try:
        return headers.index(column_name)
    except ValueError:
        return None

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

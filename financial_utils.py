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
CB_EGP_GBP_URL = "https://api.exchangerate-api.com/v4/latest/GBP"  # GBP to EGP Rate

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

# Function to fetch GBP to EGP rate
def get_gbp_rate():
    """
    Fetches GBP to EGP exchange rate.
    Returns the rate as a float or None on error.
    """
    try:
        response = requests.get(CB_EGP_GBP_URL)
        response.raise_for_status()
        return round(response.json()["rates"].get("EGP", 0), 2)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching GBP rate: {e}")
        return None

# Function to save data to Excel
def save_to_excel(timestamp, gold_holdings_24k, gold_holdings_21k, usd_balance, gold_price_24k, gold_price_21k, official_usd_rate, total_gold_value_egp, total_usd_value_egp, total_wealth_egp):
    """
    Saves financial data to Excel file with new format (10 columns).
    If file exists with old format, migrates existing rows to new format.
    """
    file_path = "financial_summary.xlsx"
    
    if os.path.exists(file_path):
        workbook = load_workbook(file_path)
        sheet = workbook.active
        # Check if headers need to be updated (old format detection)
        existing_headers = [cell.value for cell in sheet[1]]
        if len(existing_headers) == 8 and existing_headers == OLD_FORMAT_HEADERS:
            # Migrate existing rows from old format to new format before header update
            old_rows = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row:
                    old_rows.append(row)
            
            # Clear existing data rows (keep header row)
            sheet.delete_rows(2, sheet.max_row)
            
            # Update headers to new format
            for col_idx, new_header in enumerate(NEW_FORMAT_HEADERS, start=1):
                sheet.cell(row=1, column=col_idx, value=new_header)
            
            # Re-insert migrated rows with new format structure
            for old_row in old_rows:
                migrated_row = _migrate_old_row_to_new_format(old_row)
                sheet.append(migrated_row)
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

def _migrate_old_row_to_new_format(old_row):
    """
    Converts an old format row (8 columns) to new format (10 columns).
    Returns a list with 10 values in correct order.
    """
    if len(old_row) == 8:
        # Mapping: old_row[0]=Date, [1]=Gold, [2]=USD, [3]=Gold Price, [4]=USD Rate, [5]=Gold Value, [6]=USD Value, [7]=Wealth
        return [
            old_row[0],      # Timestamp (Date)
            old_row[1],      # Gold Holdings 24k (was combined "Gold Holdings")
            None,            # Gold Holdings 21k (not in old format)
            old_row[2],      # USD Balance
            old_row[3],      # Gold Price 24k (was "Gold Price")
            None,            # Gold Price 21k (not in old format)
            old_row[4],      # Official USD Rate
            old_row[5],      # Total Gold Value
            old_row[6],      # Total USD Value
            old_row[7]       # Total Wealth
        ]
    else:
        # Row already has 10 or different column count, return as-is
        return list(old_row) + [None] * (10 - len(old_row))

def ensure_excel_format_migrated(file_path):
    """
    Ensures Excel file has been migrated from old format to new format.
    Checks if any rows still have 8 columns (old format) and migrates them if needed.
    This should be called on app startup to fix any files with old rows that weren't migrated.
    """
    if not os.path.exists(file_path):
        return
    
    workbook = load_workbook(file_path)
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    
    # If headers are already new format but some rows are still old format, migrate them
    if len(headers) == 10 and headers == NEW_FORMAT_HEADERS:
        needs_migration = False
        old_rows = []
        
        # Check if any rows need migration
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row and len(row) == 8:
                needs_migration = True
                old_rows.append(row)
        
        if needs_migration:
            # Clear and re-populate with migrated rows
            sheet.delete_rows(2, sheet.max_row)
            for old_row in old_rows:
                migrated_row = _migrate_old_row_to_new_format(old_row)
                sheet.append(migrated_row)
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

# Function to normalize rows to new format (all rows should now be 10 columns after migration)
def normalize_row_to_new_format(row, headers):
    """
    Converts a row to a dictionary with column names as keys.
    Since save_to_excel() migrates old rows, all rows should now have 10 columns.
    """
    if len(row) == 10:
        # All rows should be in new format after migration
        return dict(zip(headers, row))
    elif len(row) < 10:
        # Fallback for any edge cases: pad with None
        padded_row = list(row) + [None] * (10 - len(row))
        return dict(zip(headers, padded_row))
    else:
        # Row has more than expected columns, return as dictionary
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

# Function to round numeric values to 2 decimal places
def round_numeric_value(value, decimal_places=2):
    """
    Rounds numeric values to specified decimal places.
    Returns None if value is None, otherwise returns rounded float or original value if not numeric.
    """
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return round(float(value), decimal_places)
        return value
    except (ValueError, TypeError):
        return value

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

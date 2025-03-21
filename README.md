# Finansly

Finansly is a Python-based financial summary tool that helps users track their wealth by calculating the value of their gold holdings and USD balance in Egyptian Pounds (EGP). The tool fetches the latest gold price and official USD to EGP exchange rate from online APIs and saves the financial summary to an Excel file.

## Features

- Fetches the latest gold price in EGP per gram.
- Fetches the official USD to EGP exchange rate.
- Calculates the total value of gold holdings and USD balance in EGP.
- Saves the financial summary to an Excel file.
- Web interface to input data and view financial summaries.
- Ability to delete specific entries from the financial summary.

## Requirements

- Python 3.x
- `requests` library
- `openpyxl` library
- `python-dotenv` library
- `flask` library
- `flask-session` library

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/ahmedelzagh/Finansly.git
   cd Finansly
   ```

2. Install the required libraries:

   ```sh
   pip install requests openpyxl python-dotenv flask flask-session
   ```

3. Create a `.env` file in the project directory and add your Gold API key:
   ```env
   GOLD_API_KEY=your_gold_api_key
   ```

## Usage

1. Run the Flask web application:

   ```sh
   python app.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000`.

3. Enter your gold holdings (in grams) and USD balance in the form and submit.

4. The application will fetch the latest gold price and USD to EGP exchange rate, calculate the total values, and display the financial summary.

5. The financial summary will be saved to an Excel file named `financial_summary.xlsx` in the project directory.

## Example

```
Enter your gold holdings (grams): 50
Enter your USD balance: 1000

--- Financial Summary ---
Gold Price (EGP/gm): 900.50
Official USD Rate: 15.70
Total Gold Value (EGP): 45025.00
Total USD Value (EGP): 15700.00
Total Wealth (EGP): 60725.00
```

## License

This project is licensed under the MIT License.

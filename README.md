# Finansly

Finansly is a Python-based financial summary tool that helps users track their wealth by calculating the value of their gold holdings and USD balance in Egyptian Pounds (EGP). The tool fetches the latest gold price and official USD to EGP exchange rate from online APIs and saves the financial summary to an Excel file.

## Features

- Fetches the latest gold price in EGP per gram (24k and 21k).
- Fetches the official USD to EGP and GBP to EGP exchange rates.
- Calculates the total value of gold holdings and USD balance in EGP.
- Saves the financial summary to an Excel file.
- Web interface to input data and view financial summaries.
- Ability to delete specific entries from the financial summary.
- **Telegram notifications** with buy/sell signals based on real-world trading strategies (Moving Averages, RSI, Support/Resistance).
- **PayPal transfer calculator** - Telegram bot command to check if manual transfer (150 EGP tax) is worth it vs waiting for auto-transfer.

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

3. Create a `.env` file in the project directory and add your configuration:
   ```env
   GOLD_API_KEY=your_gold_api_key
   APP_USERNAME=admin
   APP_PASSWORD=your_secure_password
   SECRET_KEY=your_secret_key_here
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   WEBHOOK_URL=https://your-domain.com/telegram-webhook
   ```
   
   **Note:** 
   - The app uses simple authentication. Set `APP_USERNAME` and `APP_PASSWORD` to your desired login credentials.
   - The `SECRET_KEY` is used for session security - you can generate one using `python -c "import secrets; print(secrets.token_hex(24))"`.
   - For Telegram notifications: Get bot token from [@BotFather](https://t.me/BotFather) and chat ID from [@userinfobot](https://t.me/userinfobot).
   - For Telegram bot commands: Set `WEBHOOK_URL` to your server URL (e.g., `https://your-domain.com/telegram-webhook`).

## Usage

1. Run the Flask web application:

   ```sh
   python app.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000`.

3. You will be redirected to the login page. Enter your username and password (set in `.env` file).

4. After logging in, enter your gold holdings (in grams) and USD balance in the form and submit.

4. The application will fetch the latest gold price and USD to EGP exchange rate, calculate the total values, and display the financial summary.

5. The financial summary will be saved to an Excel file named `financial_summary.xlsx` in the project directory.

## Telegram Features

### Price Alerts
The app automatically monitors prices every 30 minutes and sends Telegram notifications when buy/sell signals are detected based on:
- Moving Averages (trend analysis)
- RSI (momentum indicator)
- Support/Resistance levels
- Multiple confirmation requirements for reliability

### PayPal Transfer Calculator
Use the Telegram bot command to check if manual PayPal transfer is worth it:

```
/paypal <amount>
```

Example: `/paypal 1000`

This calculates whether to:
- Transfer manually now (150 EGP tax)
- OR wait for auto-transfer on 1st of month (no tax)

**Setup Telegram Webhook:**
```bash
python setup_webhook.py
```

Make sure your Flask app is running and accessible at the `WEBHOOK_URL` you configured.

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

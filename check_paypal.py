"""
Simple command-line tool to check PayPal transfer decision
Usage: python check_paypal.py <amount>
Example: python check_paypal.py 1000
"""
import sys
from paypal_transfer_calculator import check_paypal_transfer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_paypal.py <GBP_amount>")
        print("Example: python check_paypal.py 1000")
        sys.exit(1)
    
    try:
        amount = float(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid number")
        sys.exit(1)
    
    if amount <= 0:
        print("Error: Amount must be greater than 0")
        sys.exit(1)
    
    print(f"Checking transfer decision for {amount} GBP...")
    decision = check_paypal_transfer(amount, send_to_telegram=True)
    
    if decision:
        print("\n✅ Decision sent to Telegram!")
        print(f"Recommendation: {decision['recommendation']}")
        print(f"Difference: {decision['difference']:.2f} EGP")
    else:
        print("❌ Error: Could not calculate transfer decision")

"""
APEX COINBASE CONNECTOR
Checks balance, converts to USDC, executes live trades.
Always asks Ty for approval before moving money.
"""

import os, json, time, requests, hmac, hashlib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")

# APEX Coinbase keys
API_KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME")
PRIVATE_KEY = os.getenv("APEX_COINBASE_PRIVATE_KEY")

CB_API = "https://api.coinbase.com/api/v3"

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_headers(method, path, body=""):
    """Generate Coinbase Advanced Trade API headers."""
    import time as t
    timestamp = str(int(t.time()))
    message = timestamp + method.upper() + path + body
    signature = hmac.new(
        PRIVATE_KEY.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    return {
        "CB-ACCESS-KEY": API_KEY_NAME,
        "CB-ACCESS-SIGN": signature,
        "CB-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }

def get_accounts():
    """Get all Coinbase accounts and balances."""
    try:
        path = "/brokerage/accounts"
        headers = get_headers("GET", path)
        r = requests.get(f"{CB_API}{path}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("accounts", [])
        else:
            print(f"Coinbase error: {r.status_code} {r.text}")
            return []
    except Exception as e:
        print(f"Get accounts error: {e}")
        return []

def format_balance_report(accounts):
    """Format a clean balance report for Telegram."""
    msg = "💰 COINBASE BALANCE REPORT\n━━━━━━━━━━━━━━━━━━━━━\n"
    total_usd = 0
    tradeable = []

    for acc in accounts:
        balance = float(acc.get("available_balance", {}).get("value", 0))
        currency = acc.get("available_balance", {}).get("currency", "")
        if balance > 0.01:
            msg += f"• {currency}: {balance:.4f}\n"
            tradeable.append({"currency": currency, "balance": balance})

    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Reply with which token to convert to USDC for APEX trading.\n"
    msg += f"Example: 'convert 50 SOL to USDC'"
    return msg, tradeable

def run():
    print("APEX COINBASE CONNECTOR")
    print("Checking your Coinbase balance...")

    if not API_KEY_NAME or not PRIVATE_KEY:
        send_telegram("❌ APEX Coinbase keys not found in .env")
        print("Missing Coinbase keys")
        return

    accounts = get_accounts()

    if not accounts:
        send_telegram(
            "❌ Could not connect to Coinbase.\n"
            "API keys may need to be re-entered.\n"
            "Check: coinbase.com/settings/api"
        )
        return

    report, tradeable = format_balance_report(accounts)
    send_telegram(report)
    print(report)
    print("\nBalance report sent to Telegram.")
    print("Waiting for Ty to choose which token to convert...")

if __name__ == "__main__":
    run()

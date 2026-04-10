"""
APEX COINBASE CONNECTOR — JWT Auth
Uses Coinbase CDP key format with EC private key.
"""

import os, json, time, requests, uuid
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
API_KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME")
PRIVATE_KEY_STR = os.getenv("APEX_COINBASE_PRIVATE_KEY", "")

CB_API = "https://api.coinbase.com/api/v3"

def send_telegram(msg, force=False):
    try:
        from silent_mode import should_send
        if not should_send(msg, force=force):
            print(f"[APEX-V2] SILENT_MODE suppressed: {msg[:80]}...")
            return
    except ImportError:
        if not force:
            print(f"[APEX-V2] SILENT_MODE (fallback block): {msg[:80]}...")
            return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def build_jwt(method, path):
    import jwt
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    private_key_pem = PRIVATE_KEY_STR.replace("\\n", "\n")
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    payload = {
        "sub": API_KEY_NAME,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
        "uri": f"{method} api.coinbase.com{path}",
    }
    token = jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": API_KEY_NAME, "nonce": str(uuid.uuid4())}
    )
    return token

def get_accounts():
    try:
        path = "/brokerage/accounts"
        token = build_jwt("GET", path)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.get(f"{CB_API}{path}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("accounts", [])
        else:
            print(f"Coinbase error: {r.status_code} {r.text[:300]}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def run():
    print("APEX COINBASE CONNECTOR")
    print("Checking balance...")

    accounts = get_accounts()

    if not accounts:
        send_telegram("❌ Could not connect to Coinbase. Check API keys.")
        return

    msg = "💰 YOUR COINBASE BALANCE\n━━━━━━━━━━━━━━━━━━━━━\n"
    for acc in accounts:
        balance = float(acc.get("available_balance", {}).get("value", 0))
        currency = acc.get("available_balance", {}).get("currency", "")
        if balance > 0.01:
            msg += f"• {currency}: {balance:.4f}\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "Tell me which token to convert to USDC for APEX.\nExample: convert 50 SOL to USDC"

    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    run()

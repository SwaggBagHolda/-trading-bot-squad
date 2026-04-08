"""
APEX LIVE TRADER — FINAL VERSION
"Every second the market is open is an opportunity I refuse to miss."

Uses market_scanner.py for real RSI/EMA/volume signals.
True scalping — rides same asset up AND down.
Scan → Report → Trade → Flip → Repeat.
"""

import os, sys, time, uuid, jwt, json, requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# Add project to path so we can import market_scanner
BASE = Path.home() / "trading-bot-squad"
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env")

import market_scanner as ms

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME")
PRIVATE_KEY_STR = os.getenv("APEX_COINBASE_PRIVATE_KEY", "").replace("\\n", "\n")
HIVE = BASE / "shared" / "hive_mind.json"

CB_API = "https://api.coinbase.com/api/v3"

# APEX Settings
RISK_PCT = 0.02       # 2% risk per trade
REWARD_RATIO = 3.0    # 3:1 target
TRAIL_PCT = 0.015     # 1.5% trailing stop
STOP_PCT = 0.01       # 1% hard stop
MAX_DAILY_LOSS = 0.05 # 5% kill switch
SCAN_INTERVAL = 30    # Seconds between scans
MIN_STRENGTH = 0.4    # Minimum signal strength to trade

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def build_jwt(method, path):
    private_key = load_pem_private_key(PRIVATE_KEY_STR.encode(), password=None)
    payload = {
        "sub": KEY_NAME, "iss": "cdp",
        "nbf": int(time.time()), "exp": int(time.time()) + 120,
        "uri": f"{method} api.coinbase.com{path}",
    }
    return jwt.encode(payload, private_key, algorithm="ES256",
                      headers={"kid": KEY_NAME, "nonce": str(uuid.uuid4())})

def cb_get(path):
    try:
        token = build_jwt("GET", path)
        r = requests.get(f"{CB_API}{path}",
                        headers={"Authorization": f"Bearer {token}"}, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def cb_post(path, body):
    try:
        token = build_jwt("POST", path)
        r = requests.post(f"{CB_API}{path}",
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"},
                         json=body, timeout=10)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def get_usd_balance():
    data = cb_get("/brokerage/accounts?limit=50")
    if not data:
        return 0
    for acc in data.get("accounts", []):
        if acc["available_balance"]["currency"] == "USD":
            return float(acc["available_balance"]["value"])
    return 0

def get_price(symbol):
    """Get current price using ccxt via market_scanner exchange."""
    try:
        exchange = ms.get_exchange("APEX")
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker["last"])
    except:
        return None

def get_best_signal():
    """Get best APEX signal from market scanner."""
    try:
        signals = ms.scan("APEX")
        if not signals:
            return None
        # Filter by minimum strength
        valid = [s for s in signals if s.get("strength", 0) >= MIN_STRENGTH and s.get("direction")]
        if not valid:
            return None
        # Return highest strength signal
        return max(valid, key=lambda x: x["strength"])
    except Exception as e:
        print(f"Scan error: {e}")
        return None

def get_exit_signal(symbol, current_direction):
    """Check if we should exit current position."""
    try:
        exchange = ms.get_exchange("APEX")
        df = ms.fetch_ohlcv(exchange, symbol, "1m", limit=30)
        df = ms.add_indicators(df)
        if df.empty:
            return False, "no data"

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Exit long if:
        if current_direction == "long":
            if last["rsi"] > 70:
                return True, f"RSI overbought {last['rsi']:.1f}"
            if last["vol_ratio"] < 0.7 and last["close"] < prev["close"]:
                return True, f"volume dying + price dropping"
            if last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]:
                return True, "EMA bearish cross"

        # Exit short if:
        elif current_direction == "short":
            if last["rsi"] < 30:
                return True, f"RSI oversold {last['rsi']:.1f}"
            if last["vol_ratio"] < 0.7 and last["close"] > prev["close"]:
                return True, "volume dying + price rising"
            if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]:
                return True, "EMA bullish cross"

        return False, ""
    except Exception as e:
        return False, str(e)

def place_order(product_id, side, usd_amount):
    order_id = str(uuid.uuid4())
    body = {
        "client_order_id": order_id,
        "product_id": product_id,
        "side": side,
        "order_configuration": {
            "market_market_ioc": {
                "quote_size": str(round(usd_amount, 2))
            }
        }
    }
    return cb_post("/brokerage/orders", body)

def update_hive(daily_pnl, trades, wins):
    try:
        hive = {}
        if HIVE.exists():
            with open(HIVE) as f:
                hive = json.load(f)
        if "bot_performance" not in hive:
            hive["bot_performance"] = {}
        hive["bot_performance"]["APEX"] = {
            "daily_pnl": round(daily_pnl, 2),
            "trades": trades,
            "wins": wins,
            "win_rate": round(wins/trades, 3) if trades > 0 else 0,
            "status": "LIVE",
            "mode": "live_scalping"
        }
        with open(HIVE, "w") as f:
            json.dump(hive, f, indent=2)
    except: pass

def run():
    print("=" * 55)
    print("APEX LIVE SCALPER — FINAL VERSION")
    print('"Ride it up. Flip it. Ride it down. Repeat."')
    print("=" * 55)

    balance = get_usd_balance()
    if balance < 10:
        tg(f"❌ APEX: Only ${balance:.2f} available. Need $10+.")
        return

    starting_balance = balance

    tg(f"⚡ APEX LIVE SCALPER ONLINE\n"
       f"━━━━━━━━━━━━━━━━━━━━━\n"
       f"💰 Balance: ${balance:.2f}\n"
       f"🎯 Risk: 2% = ${balance*RISK_PCT:.2f}/trade\n"
       f"📈 Target: 3:1 = ${balance*RISK_PCT*REWARD_RATIO:.2f}/win\n"
       f"🔄 Strategy: Ride up → flip → ride down\n"
       f"📊 Signals: RSI + EMA + Volume\n"
       f"━━━━━━━━━━━━━━━━━━━━━\n"
       f"🔍 Scanning markets now...")

    daily_pnl = 0.0
    trades = 0
    wins = 0
    active_trade = None
    trailing_best = None
    last_report = datetime.now()
    current_asset = None  # Lock to best asset for scalping

    while True:
        try:
            current_balance = get_usd_balance()
            daily_loss = (starting_balance - current_balance) + daily_pnl

            # Kill switch
            if daily_loss > starting_balance * MAX_DAILY_LOSS:
                tg(f"🛑 APEX KILL SWITCH\n"
                   f"Loss limit hit: ${daily_loss:.2f}\n"
                   f"Final: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
                update_hive(daily_pnl, trades, wins)
                break

            # No active trade — scan for best signal
            if not active_trade:
                signal = get_best_signal()

                if signal:
                    symbol = signal["symbol"]
                    direction = signal["direction"]
                    strength = signal["strength"]
                    reason = signal["reason"]
                    current_price = get_price(symbol)

                    if not current_price:
                        time.sleep(SCAN_INTERVAL)
                        continue

                    # Convert symbol to Coinbase product format
                    product_id = symbol.replace("/", "-")
                    cb_side = "BUY" if direction == "long" else "SELL"

                    trade_size = current_balance * RISK_PCT
                    target_pct = STOP_PCT * REWARD_RATIO
                    target_price = current_price * (1 + target_pct) if direction == "long" else current_price * (1 - target_pct)
                    stop_price = current_price * (1 - STOP_PCT) if direction == "long" else current_price * (1 + STOP_PCT)

                    # Report scan before entering
                    tg(f"🔍 APEX SIGNAL FOUND\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{'📈 LONG' if direction == 'long' else '📉 SHORT'} {symbol}\n"
                       f"💪 Strength: {strength:.0%}\n"
                       f"📊 Why: {reason}\n"
                       f"💰 Entry: ${current_price:,.4f}\n"
                       f"🎯 Target: ${target_price:,.4f} (+{target_pct*100:.1f}%)\n"
                       f"🛑 Stop: ${stop_price:,.4f} (-{STOP_PCT*100:.1f}%)\n"
                       f"💵 Size: ${trade_size:.2f}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"Entering now...")

                    result, status = place_order(product_id, cb_side, trade_size)

                    if status == 200 and result.get("success"):
                        trades += 1
                        active_trade = {
                            "symbol": symbol,
                            "product_id": product_id,
                            "direction": direction,
                            "entry_price": current_price,
                            "size_usd": trade_size,
                            "entry_time": datetime.now(),
                            "stop_price": stop_price,
                        }
                        trailing_best = current_price
                        current_asset = symbol
                        print(f"[APEX] Trade #{trades} opened: {cb_side} {product_id} @ ${current_price}")
                    else:
                        print(f"[APEX] Order failed: {status} {result}")
                        tg(f"⚠️ APEX order failed: {result.get('error_response', {}).get('message', 'unknown')}")
                else:
                    print(f"[APEX] No quality signal found, waiting...")

            # Active trade — manage exit
            elif active_trade:
                current_price = get_price(active_trade["symbol"])
                if not current_price:
                    time.sleep(5)
                    continue

                entry = active_trade["entry_price"]
                direction = active_trade["direction"]
                hold_seconds = (datetime.now() - active_trade["entry_time"]).seconds

                # Calculate P&L
                if direction == "long":
                    pnl_pct = (current_price - entry) / entry
                    # Update trailing high
                    if current_price > trailing_best:
                        trailing_best = current_price
                    trail_stop = trailing_best * (1 - TRAIL_PCT)
                else:
                    pnl_pct = (entry - current_price) / entry
                    # Update trailing low
                    if current_price < trailing_best:
                        trailing_best = current_price
                    trail_stop = trailing_best * (1 + TRAIL_PCT)

                # Check signal-based exit
                signal_exit, exit_reason = get_exit_signal(active_trade["symbol"], direction)

                # Check price-based exits
                price_exit = False
                if direction == "long":
                    price_exit = current_price <= trail_stop or pnl_pct <= -STOP_PCT
                else:
                    price_exit = current_price >= trail_stop or pnl_pct <= -STOP_PCT

                time_exit = hold_seconds >= 3600

                should_exit = signal_exit or price_exit or time_exit

                if should_exit:
                    pnl_usd = active_trade["size_usd"] * pnl_pct
                    daily_pnl += pnl_usd
                    if pnl_pct > 0:
                        wins += 1
                    win_rate = wins / trades if trades > 0 else 0

                    if signal_exit:
                        reason = exit_reason
                    elif time_exit:
                        reason = "1hr time limit"
                    else:
                        reason = "trailing stop" if pnl_pct > 0 else "stop loss"

                    emoji = "✅" if pnl_usd > 0 else "🔴"

                    tg(f"{emoji} APEX TRADE CLOSED #{trades}\n"
                       f"{'📈' if direction == 'long' else '📉'} {active_trade['symbol']}\n"
                       f"Entry: ${entry:,.4f} → Exit: ${current_price:,.4f}\n"
                       f"P&L: ${pnl_usd:+.2f} ({pnl_pct*100:+.2f}%)\n"
                       f"Exit: {reason}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"Daily: ${daily_pnl:+.2f} | WR: {win_rate*100:.0f}% ({wins}/{trades})\n"
                       f"Balance: ${current_balance:.2f}\n"
                       f"🔄 Scanning for flip opportunity...")

                    update_hive(daily_pnl, trades, wins)
                    prev_direction = active_trade["direction"]
                    active_trade = None
                    trailing_best = None

                    # Brief pause then look for flip on same asset
                    time.sleep(10)

            # 30 min report
            if (datetime.now() - last_report).seconds >= 1800:
                wr = (wins/trades*100) if trades > 0 else 0
                tg(f"📊 APEX 30-MIN REPORT\n"
                   f"💰 Daily P&L: ${daily_pnl:+.2f}\n"
                   f"📈 {trades} trades | {wins} wins | {wr:.0f}% WR\n"
                   f"💵 Balance: ${get_usd_balance():.2f}\n"
                   f"📈 Monthly pace: ${daily_pnl*30:+,.0f}/mo")
                last_report = datetime.now()

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            tg(f"⚠️ APEX stopped.\nFinal: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
            update_hive(daily_pnl, trades, wins)
            break
        except Exception as e:
            print(f"[APEX ERROR] {e}")
            time.sleep(10)

if __name__ == "__main__":
    run()

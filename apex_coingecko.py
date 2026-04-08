"""
APEX LIVE SCALPER — CoinGecko Edition
Uses CoinGecko free API for signals (no auth needed)
Uses Coinbase API for order execution
Ride it up. Flip it. Ride it down. Repeat.
"""
import os, sys, json, time, uuid, jwt, requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives.serialization import load_pem_private_key

BASE = Path.home() / "trading-bot-squad"
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env", override=True)

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
HIVE = BASE / "shared" / "hive_mind.json"

CB_API = "https://api.coinbase.com"
KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME", "")
PEM = os.getenv("APEX_COINBASE_PRIVATE_KEY", "")

WATCHLIST = [
    {"id": "bitcoin", "symbol": "BTC", "product": "BTC-USD"},
    {"id": "ethereum", "symbol": "ETH", "product": "ETH-USD"},
    {"id": "solana", "symbol": "SOL", "product": "SOL-USD"},
    {"id": "dogecoin", "symbol": "DOGE", "product": "DOGE-USD"},
    {"id": "avalanche-2", "symbol": "AVAX", "product": "AVAX-USD"},
    {"id": "ripple", "symbol": "XRP", "product": "XRP-USD"},
]

def get_pem():
    return PEM.replace("\\n", "\n") if PEM else ""

def build_jwt(method, path):
    pk = load_pem_private_key(get_pem().encode(), password=None)
    p = {"sub": KEY_NAME, "iss": "cdp", "nbf": int(time.time()), "exp": int(time.time())+120, "uri": f"{method} api.coinbase.com{path}"}
    return jwt.encode(p, pk, algorithm="ES256", headers={"kid": KEY_NAME, "nonce": str(uuid.uuid4())})

def cb_get(path):
    try:
        r = requests.get(f"{CB_API}{path}", headers={"Authorization": f"Bearer {build_jwt('GET', path)}"}, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

def cb_post(path, body):
    try:
        r = requests.post(f"{CB_API}{path}", headers={"Authorization": f"Bearer {build_jwt('POST', path)}", "Content-Type": "application/json"}, json=body, timeout=10)
        return r.json(), r.status_code
    except Exception as e: return {"error": str(e)}, 500

def get_price(product_id):
    data = cb_get(f"/api/v3/brokerage/products/{product_id}")
    return float(data["price"]) if data and "price" in data else None

def place_order(product_id, side, usd_amount):
    if side == "SELL":
        price = get_price(product_id)
        if not price:
            return {"error": "Could not fetch price for SELL base_size calculation"}, 500
        base_size = usd_amount / price
        order_config = {"market_market_ioc": {"base_size": str(round(base_size, 8))}}
    else:
        order_config = {"market_market_ioc": {"quote_size": str(round(usd_amount, 2))}}
    body = {"client_order_id": str(uuid.uuid4()), "product_id": product_id, "side": side,
            "order_configuration": order_config}
    return cb_post("/api/v3/brokerage/orders", body)

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def scan_markets():
    """Free CoinGecko scan — no auth needed."""
    try:
        ids = ",".join([a["id"] for a in WATCHLIST])
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "ids": ids, "price_change_percentage": "1h,24h"},
            timeout=15
        )
        if r.status_code != 200:
            return None

        coins = r.json()
        best = None
        best_score = 0

        for coin in coins:
            change_1h = abs(coin.get("price_change_percentage_1h_in_currency") or 0)
            change_24h = coin.get("price_change_percentage_24h") or 0
            volume = coin.get("total_volume") or 0

            # Score: 1h momentum x volume
            score = change_1h * (volume / 1e9)

            if score > best_score and change_1h > 0.3:
                best_score = score
                # Direction: follow 1h momentum
                direction = "BUY" if coin.get("price_change_percentage_1h_in_currency", 0) > 0 else "SELL"
                asset = next((a for a in WATCHLIST if a["id"] == coin["id"]), None)
                if asset:
                    best = {
                        "symbol": coin["symbol"].upper(),
                        "product": asset["product"],
                        "price": coin["current_price"],
                        "change_1h": coin.get("price_change_percentage_1h_in_currency", 0),
                        "change_24h": change_24h,
                        "volume": volume,
                        "score": score,
                        "direction": direction,
                        "reason": f"1h move: {coin.get('price_change_percentage_1h_in_currency',0):+.2f}% | vol: ${volume/1e9:.1f}B"
                    }

        return best
    except Exception as e:
        print(f"Scan error: {e}")
        return None

def check_exit(product_id, direction, entry_price):
    """Check momentum for exit using Coinbase price."""
    price = get_price(product_id)
    if not price:
        return False, ""
    if direction == "BUY":
        pnl_pct = (price - entry_price) / entry_price
    else:
        pnl_pct = (entry_price - price) / entry_price
    return False, ""  # Let price-based stops handle it

STATE_FILE = BASE / "shared" / "apex_state.json"

def save_state(active, trail_best, daily_pnl, trades, wins):
    try:
        state = {
            "active": active,
            "trail_best": trail_best,
            "daily_pnl": daily_pnl,
            "trades": trades,
            "wins": wins,
            "saved": datetime.now().isoformat(),
        }
        # Convert datetime in active to string so it's JSON-serializable (use copy — never mutate global active)
        if state["active"] and isinstance(state["active"].get("time"), datetime):
            state["active"] = {**state["active"], "time": state["active"]["time"].isoformat()}
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        print(f"[APEX] State save error: {e}")

def load_state():
    try:
        if STATE_FILE.exists():
            s = json.loads(STATE_FILE.read_text())
            if s.get("active") and s["active"].get("time"):
                t = s["active"]["time"]
                if isinstance(t, str):
                    s["active"]["time"] = datetime.fromisoformat(t)
            return s
    except Exception as e:
        print(f"[APEX] State load error: {e}")
    return None

def update_hive(pnl, trades, wins):
    try:
        hive = json.loads(HIVE.read_text()) if HIVE.exists() else {}
        hive.setdefault("bot_performance", {})["APEX"] = {
            "daily_pnl": round(pnl, 2), "trades": trades, "wins": wins,
            "win_rate": round(wins/trades, 3) if trades else 0,
            "status": "LIVE", "mode": "live_scalping"
        }
        HIVE.write_text(json.dumps(hive, indent=2))
    except: pass

def run():
    print("="*55)
    print("APEX LIVE SCALPER — CoinGecko Edition")
    print("Ride it up. Flip it. Ride it down. Repeat.")
    print("="*55)

    STARTING = 328.29
    RISK = 0.10
    STOP = 0.01
    TRAIL = 0.025
    MAX_LOSS = 0.05
    MIN_1H_MOVE = 0.3  # Only trade if 0.3%+ move in last hour

    print(f"Starting balance: ${STARTING:.2f}")

    daily_pnl = 0.0
    trades = wins = 0
    active = trail_best = None
    last_report = datetime.now()
    last_scan_report = datetime.now()

    # Restore position state from disk — prevents "no position" on restart mid-trade
    saved = load_state()
    if saved and saved.get("active"):
        active = saved["active"]
        trail_best = saved.get("trail_best", active["entry"])
        daily_pnl = saved.get("daily_pnl", 0.0)
        trades = saved.get("trades", 0)
        wins = saved.get("wins", 0)
        tg(f"⚡ APEX RESUMED — active position found\n"
           f"{active['direction']} {active['symbol']} @ ${active['entry']:,.4f}\n"
           f"Daily P&L so far: ${daily_pnl:+.2f} | {trades} trades")
    else:
        tg(f"APEX LIVE SCALPER ONLINE\n"
           f"Balance: ${STARTING:.2f} USD\n"
           f"Risk: {RISK*100:.0f}% = ${STARTING*RISK:.2f}/trade\n"
           f"Trail: {TRAIL*100:.1f}% | Stop: {STOP*100:.1f}%\n"
           f"Scanning BTC ETH SOL DOGE AVAX XRP...\n"
           f"Let's print. 🔥")

    while True:
        try:
            if daily_pnl < -(STARTING * MAX_LOSS):
                tg(f"APEX KILL SWITCH\nLoss limit: ${daily_pnl:.2f}\nFinal: ${daily_pnl:+.2f} | {trades} trades")
                break

            if not active:
                # Check for NEXUS force-scan flag — lowers entry threshold when APEX has been idle
                force_flag = BASE / "shared" / "apex_force_scan.flag"
                forced = False
                if force_flag.exists():
                    try:
                        force_flag.unlink()
                        forced = True
                        print("[APEX] Force scan triggered by NEXUS autonomous loop")
                    except Exception:
                        pass

                sig = scan_markets()
                effective_min = 0.0 if forced else MIN_1H_MOVE

                if sig and abs(sig["change_1h"]) >= effective_min:
                    size = STARTING * RISK
                    price = sig["price"]
                    direction = sig["direction"]
                    product = sig["product"]
                    target = price*(1+STOP*3) if direction=="BUY" else price*(1-STOP*3)
                    stop_p = price*(1-STOP) if direction=="BUY" else price*(1+STOP)

                    tg(f"🔍 APEX SIGNAL FOUND\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{'📈 LONG' if direction=='BUY' else '📉 SHORT'} {sig['symbol']}\n"
                       f"1h Move: {sig['change_1h']:+.2f}%\n"
                       f"24h: {sig['change_24h']:+.2f}%\n"
                       f"Volume: ${sig['volume']/1e9:.1f}B\n"
                       f"Entry: ${price:,.4f}\n"
                       f"Target: ${target:,.4f} (+{STOP*3*100:.1f}%)\n"
                       f"Stop: ${stop_p:,.4f} (-{STOP*100:.1f}%)\n"
                       f"Size: ${size:.2f}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"Entering now...")

                    result, status = place_order(product, direction, size)
                    print(f"Order {status}: {result}")

                    if status == 200 and result.get("success"):
                        trades += 1
                        active = {"symbol": sig["symbol"], "product": product,
                                  "direction": direction, "entry": price,
                                  "size": size, "time": datetime.now()}
                        trail_best = price
                        save_state(active, trail_best, daily_pnl, trades, wins)
                        tg(f"✅ TRADE #{trades} OPEN\n{direction} {sig['symbol']} @ ${price:,.4f}")
                    else:
                        err = result.get("error_response", {}).get("message", str(result))
                        tg(f"⚠️ Order failed: {err}")
                        print(f"Failed: {err}")
                        # If insufficient balance, an existing position is likely consuming funds.
                        # Stop scanning and wait — do not spam retry.
                        if "insufficient" in err.lower() or "balance" in err.lower():
                            tg("⚠️ APEX: Insufficient balance detected. Pausing new entries for 10 min. Check for open positions on Coinbase.")
                            time.sleep(600)  # 10-minute cooldown before trying again
                else:
                    move = sig["change_1h"] if sig else 0
                    print(f"No signal. Best 1h move: {move:+.2f}%. Min needed: {MIN_1H_MOVE}%")

            else:
                price = get_price(active["product"])
                if not price:
                    time.sleep(5)
                    continue

                entry = active["entry"]
                direction = active["direction"]
                pnl_pct = (price-entry)/entry if direction=="BUY" else (entry-price)/entry

                if direction == "BUY":
                    if price > trail_best: trail_best = price
                    trail_stop = trail_best * (1-TRAIL)
                    should_exit = price <= trail_stop or pnl_pct <= -STOP
                else:
                    if price < trail_best: trail_best = price
                    trail_stop = trail_best * (1+TRAIL)
                    should_exit = price >= trail_stop or pnl_pct <= -STOP

                if should_exit:
                    pnl_usd = active["size"] * pnl_pct
                    daily_pnl += pnl_usd
                    if pnl_pct > 0: wins += 1
                    wr = wins/trades if trades else 0
                    reason = "trail stop" if pnl_pct > 0 else "stop loss"
                    emoji = "✅" if pnl_usd > 0 else "🔴"

                    tg(f"{emoji} TRADE #{trades} CLOSED\n"
                       f"{direction} {active['symbol']}\n"
                       f"${entry:,.4f} → ${price:,.4f}\n"
                       f"P&L: ${pnl_usd:+.2f} ({pnl_pct*100:+.2f}%)\n"
                       f"Exit: {reason}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━\n"
                       f"Daily: ${daily_pnl:+.2f} | WR: {wr*100:.0f}% ({wins}/{trades})\n"
                       f"Monthly pace: ${daily_pnl*30:+,.0f}/mo\n"
                       f"Scanning for next trade...")

                    update_hive(daily_pnl, trades, wins)
                    active = trail_best = None
                    save_state(None, None, daily_pnl, trades, wins)
                    time.sleep(10)

            if (datetime.now() - last_report).seconds >= 1800:
                wr = wins/trades*100 if trades else 0
                tg(f"📊 APEX 30-MIN REPORT\n"
                   f"P&L: ${daily_pnl:+.2f} | {trades} trades | {wr:.0f}% WR\n"
                   f"Monthly pace: ${daily_pnl*30:+,.0f}/mo")
                last_report = datetime.now()

            time.sleep(60)

        except KeyboardInterrupt:
            tg(f"APEX stopped.\nFinal: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
            update_hive(daily_pnl, trades, wins)
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run()

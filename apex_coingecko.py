"""
APEX LIVE SCALPER — Micro-Momentum Edition
Signals: Coinbase price polling, 90-second rolling window
Execution: Coinbase Advanced Trade API
Target: 20-50 trades/day on volatile sessions
"""
import os, sys, json, time, uuid, jwt, requests
from collections import deque
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives.serialization import load_pem_private_key

BASE = Path.home() / "trading-bot-squad"
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env", override=True)

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID  = os.getenv("OWNER_TELEGRAM_CHAT_ID")
HIVE           = BASE / "shared" / "hive_mind.json"
STATE_FILE     = BASE / "shared" / "apex_state.json"

CB_API   = "https://api.coinbase.com"
KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME", "")
PEM      = os.getenv("APEX_COINBASE_PRIVATE_KEY", "")

# Assets to scan — ordered by liquidity
WATCHLIST = [
    {"symbol": "BTC",  "product": "BTC-USD"},
    {"symbol": "ETH",  "product": "ETH-USD"},
    {"symbol": "SOL",  "product": "SOL-USD"},
    {"symbol": "XRP",  "product": "XRP-USD"},
    {"symbol": "DOGE", "product": "DOGE-USD"},
    {"symbol": "AVAX", "product": "AVAX-USD"},
]

# ── Scalping parameters ───────────────────────────────────────────────────────
STARTING       = 328.29
RISK           = 0.10    # 10% of balance per trade
STOP           = 0.003   # 0.3% hard stop
TARGET         = 0.005   # 0.5% take profit
TRAIL          = 0.002   # 0.2% trailing stop (locks in gains fast)
MAX_LOSS       = 0.05    # 5% daily kill switch
MIN_MOMENTUM   = 0.0015  # 0.15% move in 90-second window to enter
POLL_INTERVAL  = 15      # seconds between price polls
WINDOW_TICKS   = 6       # 6 ticks × 15s = 90-second momentum window
COOLDOWN       = 30      # seconds between trades (avoid churn)
# ─────────────────────────────────────────────────────────────────────────────

def get_pem():
    return PEM.replace("\\n", "\n") if PEM else ""

def build_jwt(method, path):
    pk = load_pem_private_key(get_pem().encode(), password=None)
    p  = {"sub": KEY_NAME, "iss": "cdp", "nbf": int(time.time()),
          "exp": int(time.time()) + 120, "uri": f"{method} api.coinbase.com{path}"}
    return jwt.encode(p, pk, algorithm="ES256",
                      headers={"kid": KEY_NAME, "nonce": str(uuid.uuid4())})

def cb_get(path):
    try:
        r = requests.get(f"{CB_API}{path}",
                         headers={"Authorization": f"Bearer {build_jwt('GET', path)}"},
                         timeout=8)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def cb_post(path, body):
    try:
        r = requests.post(f"{CB_API}{path}",
                          headers={"Authorization": f"Bearer {build_jwt('POST', path)}",
                                   "Content-Type": "application/json"},
                          json=body, timeout=8)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def get_price(product_id):
    data = cb_get(f"/api/v3/brokerage/products/{product_id}")
    if data and "price" in data:
        return float(data["price"])
    # Fallback: unauthenticated Coinbase spot
    try:
        sym = product_id.replace("-USD", "")
        r   = requests.get(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot", timeout=5)
        if r.status_code == 200:
            return float(r.json()["data"]["amount"])
    except:
        pass
    return None

def place_order(product_id, side, usd_amount):
    if side == "SELL":
        price = get_price(product_id)
        if not price:
            return {"error": "Could not fetch price for SELL base_size"}, 500
        base_size    = usd_amount / price
        order_config = {"market_market_ioc": {"base_size": str(round(base_size, 8))}}
    else:
        order_config = {"market_market_ioc": {"quote_size": str(round(usd_amount, 2))}}
    body = {
        "client_order_id":   str(uuid.uuid4()),
        "product_id":        product_id,
        "side":              side,
        "order_configuration": order_config,
    }
    return cb_post("/api/v3/brokerage/orders", body)

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=8)
    except:
        pass

def poll_prices(price_history):
    """Poll all assets and append to rolling windows. Returns current prices dict."""
    current = {}
    for asset in WATCHLIST:
        p = get_price(asset["product"])
        if p:
            price_history[asset["product"]].append(p)
            current[asset["product"]] = p
    return current

def best_signal(price_history, current_prices):
    """
    Scan all assets for micro-momentum signal.
    Returns best signal dict or None.
    Signal: asset moved MIN_MOMENTUM% in the last WINDOW_TICKS × POLL_INTERVAL seconds.
    """
    best      = None
    best_move = 0.0

    for asset in WATCHLIST:
        product = asset["product"]
        history = price_history[product]

        if len(history) < WINDOW_TICKS:
            continue  # not enough data yet

        oldest = history[0]
        latest = current_prices.get(product)
        if not oldest or not latest:
            continue

        move = (latest - oldest) / oldest  # signed momentum

        if abs(move) > MIN_MOMENTUM and abs(move) > best_move:
            best_move = abs(move)
            direction = "BUY" if move > 0 else "SELL"
            best = {
                "symbol":    asset["symbol"],
                "product":   product,
                "price":     latest,
                "momentum":  move,
                "direction": direction,
            }

    return best

def save_state(active, trail_best, daily_pnl, trades, wins):
    try:
        state = {
            "active":     active,
            "trail_best": trail_best,
            "daily_pnl":  daily_pnl,
            "trades":     trades,
            "wins":       wins,
            "saved":      datetime.now().isoformat(),
        }
        if state["active"] and isinstance(state["active"].get("time"), datetime):
            state["active"] = {**state["active"],
                               "time": state["active"]["time"].isoformat()}
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
            "win_rate":  round(wins / trades, 3) if trades else 0,
            "mode":      "live_scalping",
        }
        HIVE.write_text(json.dumps(hive, indent=2))
    except:
        pass

def run():
    print("=" * 55)
    print("APEX LIVE SCALPER — Micro-Momentum Edition")
    print(f"Poll: {POLL_INTERVAL}s | Window: {WINDOW_TICKS * POLL_INTERVAL}s | Min move: {MIN_MOMENTUM*100:.2f}%")
    print(f"Stop: {STOP*100:.1f}% | Target: {TARGET*100:.1f}% | Trail: {TRAIL*100:.1f}%")
    print("=" * 55)

    daily_pnl  = 0.0
    trades     = wins = 0
    active     = trail_best = None
    last_close = datetime.now()
    last_report = datetime.now()

    # Rolling price windows per asset
    price_history = {a["product"]: deque(maxlen=WINDOW_TICKS) for a in WATCHLIST}

    # Restore open position from disk
    saved = load_state()
    if saved and saved.get("active"):
        active      = saved["active"]
        trail_best  = saved.get("trail_best", active["entry"])
        daily_pnl   = saved.get("daily_pnl", 0.0)
        trades      = saved.get("trades", 0)
        wins        = saved.get("wins", 0)
        tg(f"APEX RESUMED — {active['direction']} {active['symbol']} @ ${active['entry']:,.4f}\n"
           f"Daily P&L: ${daily_pnl:+.2f} | {trades} trades")
    else:
        tg(f"APEX SCALPER ONLINE — Micro-Momentum Edition\n"
           f"Balance: ${STARTING:.2f} | Risk: ${STARTING*RISK:.2f}/trade\n"
           f"Stop: {STOP*100:.1f}% | Target: {TARGET*100:.1f}% | Trail: {TRAIL*100:.1f}%\n"
           f"Scanning BTC ETH SOL XRP DOGE AVAX every {POLL_INTERVAL}s\n"
           f"Min move to enter: {MIN_MOMENTUM*100:.2f}% in {WINDOW_TICKS*POLL_INTERVAL}s window")

    while True:
        try:
            # ── Kill switch ───────────────────────────────────────────────────
            if daily_pnl < -(STARTING * MAX_LOSS):
                tg(f"APEX KILL SWITCH — loss limit hit\n"
                   f"Final: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
                update_hive(daily_pnl, trades, wins)
                break

            # ── Poll prices ───────────────────────────────────────────────────
            current = poll_prices(price_history)

            # ── Manage open position ──────────────────────────────────────────
            if active:
                product   = active["product"]
                price     = current.get(product) or get_price(product)
                if not price:
                    time.sleep(POLL_INTERVAL)
                    continue

                entry     = active["entry"]
                direction = active["direction"]
                pnl_pct   = (price - entry) / entry if direction == "BUY" \
                            else (entry - price) / entry

                # Update trailing stop
                if direction == "BUY":
                    if price > trail_best:
                        trail_best = price
                    trail_stop = trail_best * (1 - TRAIL)
                    should_exit = price <= trail_stop or pnl_pct <= -STOP or pnl_pct >= TARGET
                else:
                    if price < trail_best:
                        trail_best = price
                    trail_stop = trail_best * (1 + TRAIL)
                    should_exit = price >= trail_stop or pnl_pct <= -STOP or pnl_pct >= TARGET

                print(f"[APEX] {direction} {active['symbol']} {pnl_pct*100:+.3f}% "
                      f"| entry ${entry:,.4f} now ${price:,.4f} trail ${trail_stop:,.4f}")

                if should_exit:
                    exit_side  = "SELL" if direction == "BUY" else "BUY"
                    result, _  = place_order(product, exit_side, active["size"])

                    pnl_usd = active["size"] * pnl_pct
                    daily_pnl += pnl_usd
                    if pnl_pct > 0:
                        wins += 1
                    wr     = wins / trades if trades else 0
                    reason = "target" if pnl_pct >= TARGET else \
                             "trail"  if pnl_pct > 0 else "stop"
                    tag    = "WIN" if pnl_usd > 0 else "LOSS"

                    tg(f"{tag} #{trades} | {direction} {active['symbol']}\n"
                       f"${entry:,.4f} -> ${price:,.4f} ({pnl_pct*100:+.3f}%) [{reason}]\n"
                       f"P&L: ${pnl_usd:+.3f} | Day: ${daily_pnl:+.2f} | WR: {wr*100:.0f}% ({wins}/{trades})")

                    update_hive(daily_pnl, trades, wins)
                    active     = trail_best = None
                    last_close = datetime.now()
                    save_state(None, None, daily_pnl, trades, wins)

            # ── Look for next trade ───────────────────────────────────────────
            else:
                cooldown_elapsed = (datetime.now() - last_close).total_seconds()
                if cooldown_elapsed < COOLDOWN:
                    time.sleep(POLL_INTERVAL)
                    continue

                # Check NEXUS force-scan flag
                force_flag = BASE / "shared" / "apex_force_scan.flag"
                if force_flag.exists():
                    try:
                        force_flag.unlink()
                        print("[APEX] NEXUS force scan — entering immediately if any move exists")
                    except:
                        pass

                sig = best_signal(price_history, current)
                if sig:
                    size      = STARTING * RISK
                    price     = sig["price"]
                    direction = sig["direction"]
                    product   = sig["product"]
                    stop_p    = price * (1 - STOP) if direction == "BUY" else price * (1 + STOP)
                    target_p  = price * (1 + TARGET) if direction == "BUY" else price * (1 - TARGET)

                    print(f"[APEX] SIGNAL: {direction} {sig['symbol']} "
                          f"momentum={sig['momentum']*100:+.3f}% @ ${price:,.4f}")

                    result, status = place_order(product, direction, size)

                    if status == 200 and result.get("success"):
                        trades    += 1
                        active     = {"symbol": sig["symbol"], "product": product,
                                      "direction": direction, "entry": price,
                                      "size": size, "time": datetime.now()}
                        trail_best = price
                        save_state(active, trail_best, daily_pnl, trades, wins)

                        tg(f"ENTRY #{trades} | {'LONG' if direction=='BUY' else 'SHORT'} {sig['symbol']}\n"
                           f"@ ${price:,.4f} | momentum {sig['momentum']*100:+.3f}%\n"
                           f"Stop: ${stop_p:,.4f} | Target: ${target_p:,.4f} | Size: ${size:.2f}")
                    else:
                        err = result.get("error_response", {}).get("message", str(result))
                        print(f"[APEX] Order failed: {err}")
                        if "insufficient" in err.lower() or "balance" in err.lower():
                            tg(f"APEX: Insufficient balance. Pausing 10 min.")
                            time.sleep(600)
                else:
                    # Log scan result every 5 minutes so we can see what's happening
                    if not hasattr(run, "_last_log") or \
                       (datetime.now() - run._last_log).total_seconds() >= 300:
                        filled = {p: len(h) for p, h in price_history.items()}
                        print(f"[APEX] No signal | history: {filled} | "
                              f"need {WINDOW_TICKS} ticks per asset")
                        run._last_log = datetime.now()

            # ── 30-min performance report ─────────────────────────────────────
            if (datetime.now() - last_report).total_seconds() >= 1800:
                wr = wins / trades * 100 if trades else 0
                tg(f"APEX 30-MIN | ${daily_pnl:+.2f} | {trades} trades | {wr:.0f}% WR\n"
                   f"Pace: ${daily_pnl*30:+,.0f}/mo")
                last_report = datetime.now()

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            tg(f"APEX stopped. Final: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
            update_hive(daily_pnl, trades, wins)
            break
        except Exception as e:
            print(f"[APEX] Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run()

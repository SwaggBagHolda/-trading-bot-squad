"""
APEX LIVE SCALPER — LAUNCH VERSION
Ride it up. Flip it. Ride it down. Repeat.
Uses proven coinbase_auth2 for connectivity.
"""
import os, sys, json, time, uuid
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env")

# Import working auth
from coinbase_auth2 import get_usd_balance, get_price, place_market_order, cb_get

# Import market scanner
import market_scanner as ms

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
HIVE = BASE / "shared" / "hive_mind.json"

RISK_PCT = 0.02
TRAIL_PCT = 0.015
STOP_PCT = 0.01
MAX_DAILY_LOSS = 0.05
SCAN_INTERVAL = 30
MIN_STRENGTH = 0.35

def tg(msg, force=False):
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        return
    try:
        from silent_mode import should_send
        if not should_send(msg, force=force):
            print(f"[APEX] SILENT_MODE suppressed: {msg[:80]}...")
            return
    except ImportError:
        print(f"[APEX] SILENT_MODE (fallback block): {msg[:80]}...")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_signal():
    try:
        signals = ms.scan("APEX")
        valid = [s for s in signals if s.get("strength", 0) >= MIN_STRENGTH and s.get("direction")]
        return max(valid, key=lambda x: x["strength"]) if valid else None
    except Exception as e:
        print(f"Scan error: {e}")
        return None

def check_exit(symbol, direction):
    try:
        exchange = ms.get_exchange("APEX")
        df = ms.fetch_ohlcv(exchange, symbol, "1m", limit=30)
        df = ms.add_indicators(df)
        if df.empty: return False, ""
        last = df.iloc[-1]
        prev = df.iloc[-2]
        if direction == "long":
            if last["rsi"] > 72: return True, f"RSI overbought {last['rsi']:.0f}"
            if last["vol_ratio"] < 0.6 and last["close"] < prev["close"]: return True, "volume + price dropping"
            if last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]: return True, "EMA bearish cross"
        else:
            if last["rsi"] < 28: return True, f"RSI oversold {last['rsi']:.0f}"
            if last["vol_ratio"] < 0.6 and last["close"] > prev["close"]: return True, "volume + price rising"
            if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]: return True, "EMA bullish cross"
        return False, ""
    except: return False, ""

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
    print("=" * 55)
    print("APEX LIVE SCALPER LAUNCHING")
    print("=" * 55)

    balance = get_usd_balance()
    print(f"USD Balance: ${balance:.2f}")

    if balance < 10:
        tg(f"APEX: Insufficient balance ${balance:.2f}")
        print("Not enough balance")
        return

    starting = balance
    tg(f"APEX LIVE SCALPER ONLINE\n"
       f"Balance: ${balance:.2f}\n"
       f"Risk: 2% = ${balance*RISK_PCT:.2f}/trade\n"
       f"Target: 3:1 = ${balance*RISK_PCT*3:.2f}/win\n"
       f"Scanning markets now...")

    daily_pnl = 0.0
    trades = 0
    wins = 0
    active = None
    trail_best = None
    last_report = datetime.now()

    while True:
        try:
            bal = get_usd_balance()
            if (starting - bal) + daily_pnl > starting * MAX_DAILY_LOSS:
                tg(f"APEX KILL SWITCH — daily loss limit\nFinal: ${daily_pnl:+.2f} | {trades} trades")
                break

            if not active:
                sig = get_signal()
                if sig:
                    sym = sig["symbol"]
                    direction = sig["direction"]
                    strength = sig["strength"]
                    reason = sig["reason"]
                    price = get_price(sym.replace("/", "-"))
                    if not price:
                        time.sleep(SCAN_INTERVAL)
                        continue

                    size = bal * RISK_PCT
                    cb_side = "BUY" if direction == "long" else "SELL"
                    product = sym.replace("/", "-")
                    target = price * (1 + STOP_PCT*3) if direction == "long" else price * (1 - STOP_PCT*3)
                    stop = price * (1 - STOP_PCT) if direction == "long" else price * (1 + STOP_PCT)

                    tg(f"APEX SIGNAL\n"
                       f"{'LONG' if direction=='long' else 'SHORT'} {sym}\n"
                       f"Strength: {strength:.0%} | {reason}\n"
                       f"Entry: ${price:,.4f}\n"
                       f"Target: ${target:,.4f} | Stop: ${stop:,.4f}\n"
                       f"Size: ${size:.2f}\nEntering...")

                    result, status = place_market_order(product, cb_side, size)
                    print(f"Order: {status} {result}")

                    if status == 200 and result.get("success"):
                        trades += 1
                        active = {"symbol": sym, "product": product, "direction": direction,
                                  "entry": price, "size": size, "time": datetime.now()}
                        trail_best = price
                        tg(f"TRADE #{trades} OPEN: {cb_side} {sym} @ ${price:,.4f}")
                    else:
                        err = result.get("error_response", {}).get("message", str(result))
                        tg(f"Order failed: {err}")
                else:
                    print(f"No signal. Waiting {SCAN_INTERVAL}s...")

            else:
                price = get_price(active["product"])
                if not price:
                    time.sleep(5); continue

                entry = active["entry"]
                direction = active["direction"]
                secs = (datetime.now() - active["time"]).seconds

                pnl_pct = (price - entry)/entry if direction == "long" else (entry - price)/entry

                if direction == "long":
                    if price > trail_best: trail_best = price
                    trail_stop = trail_best * (1 - TRAIL_PCT)
                    price_exit = price <= trail_stop or pnl_pct <= -STOP_PCT
                else:
                    if price < trail_best: trail_best = price
                    trail_stop = trail_best * (1 + TRAIL_PCT)
                    price_exit = price >= trail_stop or pnl_pct <= -STOP_PCT

                sig_exit, exit_reason = check_exit(active["symbol"], direction)
                time_exit = secs >= 3600

                if price_exit or sig_exit or time_exit:
                    pnl_usd = active["size"] * pnl_pct
                    daily_pnl += pnl_usd
                    if pnl_pct > 0: wins += 1
                    wr = wins/trades if trades else 0
                    reason = exit_reason if sig_exit else ("time" if time_exit else ("trail stop" if pnl_pct > 0 else "stop loss"))
                    emoji = "✅" if pnl_usd > 0 else "🔴"
                    tg(f"{emoji} TRADE #{trades} CLOSED\n"
                       f"{direction.upper()} {active['symbol']}\n"
                       f"${entry:,.4f} → ${price:,.4f}\n"
                       f"P&L: ${pnl_usd:+.2f} ({pnl_pct*100:+.2f}%)\n"
                       f"Exit: {reason}\n"
                       f"Daily: ${daily_pnl:+.2f} | WR: {wr*100:.0f}% ({wins}/{trades})")
                    update_hive(daily_pnl, trades, wins)
                    active = None; trail_best = None
                    time.sleep(10)

            if (datetime.now() - last_report).seconds >= 1800:
                wr = wins/trades*100 if trades else 0
                tg(f"APEX 30-MIN\nP&L: ${daily_pnl:+.2f} | {trades} trades | {wr:.0f}% WR\nBalance: ${get_usd_balance():.2f}")
                last_report = datetime.now()

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            tg(f"APEX stopped. Final: ${daily_pnl:+.2f} | {trades} trades")
            update_hive(daily_pnl, trades, wins)
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run()

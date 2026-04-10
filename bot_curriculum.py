#!/usr/bin/env python3
"""
bot_curriculum.py — Graduation system for DRIFT, TITAN, SENTINEL
Forward-tests each bot on live CoinGecko market data.
Tracks trades in hive_mind.json graduation section.
Graduation path:
  backtesting → 100 trades + 70%+ WR + positive P&L → paper
  paper       → 200 trades + 70%+ WR + positive P&L → live (requires Ty approval)

  Bots are algorithms — no emotion, no fatigue. Bar is higher than a human trader.

Run: nohup python3 -u bot_curriculum.py >> logs/curriculum.log 2>&1 &
"""

import json
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
HIVE = BASE / "shared" / "hive_mind.json"

SCAN_INTERVAL  = 300   # 5 min between price scans
TRADE_TIMEOUT  = 3600  # max 1 hour in a simulated position (scalper/swing hybrid)

WIN_RATE_THRESHOLD = 0.70
MIN_TRADES_BACKTEST = 100
MIN_TRADES_PAPER    = 200

# Symbols each bot watches
BOT_SYMBOLS = {
    "DRIFT":    [("bitcoin", "BTC"), ("ethereum", "ETH"), ("solana", "SOL")],
    "TITAN":    [("bitcoin", "BTC"), ("ethereum", "ETH")],
    "SENTINEL": [("bitcoin", "BTC")],
}

# Active simulated positions: {bot: {symbol, direction, entry, entry_time, stop, target}}
_positions = {}


def read_hive():
    try:
        return json.loads(HIVE.read_text())
    except:
        return {}


def write_hive(hive):
    HIVE.write_text(json.dumps(hive, indent=2))


def get_price(coin_id):
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
            timeout=10
        )
        return r.json()[coin_id]["usd"]
    except:
        return None


def get_ohlcv_prices(coin_id, days=1):
    """Return list of hourly prices from CoinGecko market_chart."""
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=15
        )
        data = r.json()
        return [p[1] for p in data.get("prices", [])]
    except:
        return []


def compute_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_params(hive, bot):
    key = f"{bot.lower()}_best_params"
    return hive.get(key, {
        "stop_loss_pct": 0.02,
        "trailing_stop_pct": 0.025,
        "rsi_entry": 35.0,
        "rsi_exit": 65.0,
        "reward_ratio": 2.5,
    })


def check_entry_signal(prices, params):
    """Returns 'BUY', 'SELL', or None based on RSI."""
    rsi = compute_rsi(prices)
    if rsi <= params.get("rsi_entry", 35):
        return "BUY"
    if rsi >= params.get("rsi_exit", 65):
        return "SELL"
    return None


def record_trade(bot, symbol, direction, entry, exit_price, pnl_pct):
    """Record completed trade in hive_mind.json graduation tracking."""
    hive = read_hive()
    grad = hive.setdefault("graduation", {}).setdefault(bot, {
        "stage": "backtesting",
        "backtest_trades": 0, "backtest_wins": 0, "backtest_pnl": 0.0, "backtest_target": 100,
        "paper_trades": 0, "paper_wins": 0, "paper_pnl": 0.0, "paper_target": 200,
        "graduated_to_paper": None, "graduated_to_live": None
    })

    stage = grad["stage"]
    is_win = pnl_pct > 0

    if stage == "backtesting":
        grad["backtest_trades"] += 1
        if is_win:
            grad["backtest_wins"] += 1
        grad["backtest_pnl"] += pnl_pct
    elif stage == "paper":
        grad["paper_trades"] += 1
        if is_win:
            grad["paper_wins"] += 1
        grad["paper_pnl"] += pnl_pct

    # Update bot_performance summary
    perf = hive.setdefault("bot_performance", {}).setdefault(bot, {})
    perf["mode"]       = stage
    perf["trades"]     = grad["backtest_trades"] + grad["paper_trades"]
    total_wins         = grad["backtest_wins"] + grad["paper_wins"]
    perf["wins"]       = total_wins
    perf["win_rate"]   = total_wins / max(perf["trades"], 1)
    perf["daily_pnl"]  = perf.get("daily_pnl", 0) + pnl_pct * 100  # express in dollars (notional $100/trade)

    # Check graduation
    maybe_graduate(hive, bot, grad)

    write_hive(hive)

    t = grad["backtest_trades"] if stage == "backtesting" else grad["paper_trades"]
    tgt = grad["backtest_target"] if stage == "backtesting" else grad["paper_target"]
    wr = grad["backtest_wins"]/max(grad["backtest_trades"],1) if stage == "backtesting" else grad["paper_wins"]/max(grad["paper_trades"],1)
    print(f"[{bot}] {stage} trade {t}/{tgt} | {symbol} {direction} {pnl_pct:+.3f}% | WR {wr*100:.1f}%")


def maybe_graduate(hive, bot, grad):
    stage = grad["stage"]
    now = datetime.now().isoformat()

    if stage == "backtesting":
        t  = grad["backtest_trades"]
        wr = grad["backtest_wins"] / max(t, 1)
        pnl = grad["backtest_pnl"]
        if t >= grad["backtest_target"] and wr >= WIN_RATE_THRESHOLD and pnl > 0:
            grad["stage"] = "paper"
            grad["graduated_to_paper"] = now
            hive["bot_performance"][bot]["mode"] = "paper"
            print(f"[{bot}] *** GRADUATED TO PAPER *** {t} trades | {wr*100:.1f}% WR | {pnl:+.3f}% P&L")
            # Telegram alert via Telegram API direct (no nexus dependency)
            _notify(f"{bot} GRADUATED TO PAPER TRADING\n{t} trades | {wr*100:.1f}% WR | P&L {pnl:+.2f}%\nNext: {grad['paper_target']} paper trades at 70%+ WR to go live.")

    elif stage == "paper":
        t  = grad["paper_trades"]
        wr = grad["paper_wins"] / max(t, 1)
        pnl = grad["paper_pnl"]
        if t >= grad["paper_target"] and wr >= WIN_RATE_THRESHOLD and pnl > 0:
            grad["stage"] = "live_pending"
            grad["graduated_to_live"] = now
            print(f"[{bot}] *** READY FOR LIVE — PENDING TY APPROVAL *** {t} trades | {wr*100:.1f}% WR")
            _notify(f"{bot} READY FOR LIVE TRADING — AWAITING YOUR APPROVAL\n{t} paper trades | {wr*100:.1f}% WR | P&L {pnl:+.2f}%\nReply /approve_{bot.lower()} to go live.")


def _notify(msg, force=False):
    import os
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
    token   = os.getenv("NEXUS_TELEGRAM_TOKEN", "")
    chat_id = os.getenv("OWNER_TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        from silent_mode import should_send
        if not should_send(msg, force=force):
            print(f"[CURRICULUM] SILENT_MODE suppressed: {msg[:80]}...")
            return
    except ImportError:
        print(f"[CURRICULUM] SILENT_MODE (fallback block): {msg[:80]}...")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10
        )
    except:
        pass


def run_bot_scan(bot, coin_id, symbol):
    """One scan cycle for a single bot/symbol."""
    prices = get_ohlcv_prices(coin_id, days=1)
    if len(prices) < 20:
        return

    hive   = read_hive()
    params = get_params(hive, bot)
    key    = f"{bot}_{symbol}"

    # Check open position
    if key in _positions:
        pos   = _positions[key]
        price = get_price(coin_id)
        if not price:
            return

        entry     = pos["entry"]
        direction = pos["direction"]
        elapsed   = (datetime.now() - pos["entry_time"]).total_seconds()
        pnl_pct   = (price - entry) / entry if direction == "BUY" else (entry - price) / entry

        # Update trailing stop
        if direction == "BUY":
            pos["best"] = max(pos.get("best", entry), price)
            trail_stop  = pos["best"] * (1 - params.get("trailing_stop_pct", 0.025))
            hit_stop    = price <= trail_stop or pnl_pct <= -params.get("stop_loss_pct", 0.02)
        else:
            pos["best"] = min(pos.get("best", entry), price)
            trail_stop  = pos["best"] * (1 + params.get("trailing_stop_pct", 0.025))
            hit_stop    = price >= trail_stop or pnl_pct <= -params.get("stop_loss_pct", 0.02)

        hit_target = pnl_pct >= params.get("stop_loss_pct", 0.02) * params.get("reward_ratio", 2.5)
        timed_out  = elapsed > TRADE_TIMEOUT

        if hit_stop or hit_target or timed_out:
            record_trade(bot, symbol, direction, entry, price, pnl_pct)
            del _positions[key]
        return

    # No open position — check for entry
    signal = check_entry_signal(prices, params)
    if signal:
        price = get_price(coin_id)
        if price:
            _positions[key] = {
                "direction": signal,
                "entry": price,
                "entry_time": datetime.now(),
                "best": price
            }
            print(f"[{bot}] Opened {signal} {symbol} @ ${price:,.2f}")


def main():
    import os
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)

    print("=" * 55)
    print("BOT CURRICULUM RUNNER")
    print("DRIFT | TITAN | SENTINEL — Forward Test on Live Data")
    print(f"Graduation: 100 trades @ 70%+ WR → paper | 200 more → live")
    print("=" * 55)

    while True:
        try:
            hive = read_hive()
            for bot, symbols in BOT_SYMBOLS.items():
                stage = hive.get("graduation", {}).get(bot, {}).get("stage", "backtesting")
                if stage == "live_pending":
                    continue  # awaiting Ty approval — don't run
                for coin_id, symbol in symbols:
                    run_bot_scan(bot, coin_id, symbol)
                    time.sleep(2)  # don't hammer CoinGecko
        except Exception as e:
            print(f"[CURRICULUM] Error: {e}")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()

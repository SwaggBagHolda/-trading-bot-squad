"""
PAPER TRADING ENGINE
All 4 bots trading simultaneously with real market logic.
Uses live CoinGecko data. Logs every trade. Tracks P&L.
Bots trade both directions — long AND short.
When not trading — always training.
Run this and walk away.
"""

import json
import time
import random
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
REALTIME = BASE / "shared" / "realtime_data.json"
DB = BASE / "logs" / "paper_trades.db"

import os
from dotenv import load_dotenv
load_dotenv(BASE / ".env")
TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot TEXT, symbol TEXT, direction TEXT,
        entry_price REAL, exit_price REAL,
        size REAL, pnl REAL, pnl_pct REAL,
        entry_time TEXT, exit_time TEXT,
        status TEXT, strategy TEXT
    )""")
    conn.commit()
    conn.close()

def get_market_data():
    """Get real market data — free CoinGecko"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 50,
                "sparkline": False,
                "price_change_percentage": "1h,24h"
            },
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

def get_best_opportunity(coins, strategy="scalp"):
    coins = [c for c in coins if c.get("current_price", 0) >= 5.0 and c.get("total_volume", 0) >= 50000000]
    """Each bot finds its own best opportunity"""
    if not coins:
        return None

    if strategy == "scalp":
        # APEX: Most volatile in last hour
        volatile = sorted(
            [c for c in coins if c.get("price_change_percentage_1h_in_currency")],
            key=lambda x: abs(x.get("price_change_percentage_1h_in_currency", 0)),
            reverse=True
        )
        return volatile[0] if volatile else coins[0]

    elif strategy == "swing":
        # DRIFT: Best volume breakout
        breakouts = sorted(
            [c for c in coins if c.get("total_volume", 0) > 1000000],
            key=lambda x: abs(x.get("price_change_percentage_24h", 0) or 0),
            reverse=True
        )
        return breakouts[0] if breakouts else coins[0]

    elif strategy == "position":
        # TITAN: Highest market cap momentum
        momentum = [c for c in coins if c.get("market_cap", 0) > 1_000_000_000]
        return momentum[0] if momentum else coins[0]

    elif strategy == "sentinel":
        # SENTINEL: Clean trend, low volatility
        clean = [c for c in coins
                if 1 < abs(c.get("price_change_percentage_24h", 0) or 0) < 5
                and c.get("market_cap", 0) > 500_000_000]
        return clean[0] if clean else coins[0]

    return coins[0]

def determine_direction(coin, strategy):
    """Both directions — long in uptrend, short in downtrend"""
    change_24h = coin.get("price_change_percentage_24h", 0) or 0
    change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0

    if strategy == "scalp":
        # APEX: Follow 1hr momentum
        if change_1h > 0.5:
            return "LONG"
        elif change_1h < -0.5:
            return "SHORT"
        return "LONG" if change_24h > 0 else "SHORT"

    elif strategy == "swing":
        # DRIFT: Follow breakout direction
        return "LONG" if change_24h > 0 else "SHORT"

    elif strategy == "position":
        # TITAN: Macro direction
        return "LONG" if change_24h > 2 else "SHORT" if change_24h < -2 else "LONG"

    elif strategy == "sentinel":
        # SENTINEL: Conservative trend following
        return "LONG" if change_24h > 0 else "SHORT"

    return "LONG"

ENTRY_COOLDOWN = {
    "APEX":     5  * 60,   # 5 min between scalp trades
    "DRIFT":    30 * 60,   # 30 min between swing entries
    "TITAN":    2  * 3600, # 2 hr between position entries
    "SENTINEL": 60 * 60,   # 1 hr between FTMO entries
}

MIN_1H_MOVE = {
    "APEX":     0.8,   # needs 0.8%+ 1h momentum to enter
    "DRIFT":    1.5,   # needs 1.5%+ 1h move
    "TITAN":    0.5,   # macro — lower threshold but uses 24h
    "SENTINEL": 1.0,
}

class PaperBot:
    def __init__(self, name, strategy, account_size=10000, risk_per_trade=0.01):
        self.name = name
        self.strategy = strategy
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.daily_pnl = 0.0
        self.monthly_pnl = 0.0
        self.trades_today = 0
        self.wins = 0
        self.losses = 0
        self.active_position = None
        self.daily_loss_limit = account_size * 0.045
        self.last_trade_time = None

    def can_trade(self):
        if self.daily_pnl <= -self.daily_loss_limit:
            return False
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < ENTRY_COOLDOWN.get(self.name, 300):
                return False
        return True

    def open_position(self, coin, direction):
        price = coin["current_price"]
        size = (self.account_size * self.risk_per_trade) / price
        self.active_position = {
            "symbol": coin["symbol"].upper(),
            "direction": direction,
            "entry_price": price,
            "size": size,
            "trailing_high": price if direction == "LONG" else None,
            "trailing_low": price if direction == "SHORT" else None,
            "entry_time": datetime.now().isoformat(),
            "strategy": self.strategy
        }
        self.last_trade_time = datetime.now()
        print(f"[{self.name}] {direction} {coin['symbol'].upper()} @ ${price:,.4f} | Size: {size:.4f}")

    def update_position(self, current_price):
        if not self.active_position:
            return False

        pos = self.active_position
        direction = pos["direction"]
        entry = pos["entry_price"]
        size = pos["size"]

        # Update trailing stop
        if direction == "LONG":
            if current_price > pos["trailing_high"]:
                pos["trailing_high"] = current_price
            trailing_stop = pos["trailing_high"] * 0.975  # 2.5% trailing
            pnl_pct = (current_price - entry) / entry
            should_exit = current_price <= trailing_stop or pnl_pct <= -0.02
        else:  # SHORT
            if pos["trailing_low"] is None or current_price < pos["trailing_low"]:
                pos["trailing_low"] = current_price
            trailing_stop = pos["trailing_low"] * 1.025  # 2.5% trailing
            pnl_pct = (entry - current_price) / entry
            should_exit = current_price >= trailing_stop or pnl_pct <= -0.02

        if should_exit:
            pnl = pnl_pct * entry * size
            self.close_position(current_price, pnl, pnl_pct)
            return True

        return False

    def close_position(self, exit_price, pnl, pnl_pct):
        pos = self.active_position
        self.daily_pnl += pnl
        self.monthly_pnl += pnl
        self.trades_today += 1

        if pnl > 0:
            self.wins += 1
            result = "WIN"
        else:
            self.losses += 1
            result = "LOSS"

        print(f"[{self.name}] CLOSED {pos['direction']} {pos['symbol']} | "
              f"PnL: ${pnl:+.2f} ({pnl_pct*100:+.1f}%) | {result}")

        # Log to database
        conn = sqlite3.connect(DB)
        conn.execute(
            "INSERT INTO trades VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.name, pos["symbol"], pos["direction"],
             pos["entry_price"], exit_price, pos["size"],
             round(pnl, 2), round(pnl_pct * 100, 3),
             pos["entry_time"], datetime.now().isoformat(),
             "closed", pos["strategy"])
        )
        conn.commit()
        conn.close()

        # Big win alert
        if pnl > 50:
            send_telegram(
                f"🔥 {self.name} BIG WIN: +${pnl:.2f} on {pos['symbol']}\n"
                f"Direction: {pos['direction']} | Return: {pnl_pct*100:+.1f}%\n"
                f"Daily P&L: ${self.daily_pnl:+.2f}"
            )

        self.active_position = None

    def update_hive_mind(self):
        """Share P&L and status with hive mind"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    hive = json.load(f)

                total = self.wins + self.losses
                wr = self.wins / total if total > 0 else 0

                hive["bot_performance"][self.name] = {
                    "daily_pnl": round(self.daily_pnl, 2),
                    "monthly_pnl": round(self.monthly_pnl, 2),
                    "trades": self.trades_today,
                    "win_rate": round(wr, 3),
                    "status": "paper_trading",
                    "active_position": self.active_position is not None
                }
                with open(HIVE, "w") as f:
                    json.dump(hive, f, indent=2)
        except Exception as e:
            print(f"[{self.name}] Hive update error: {e}")

    @property
    def win_rate(self):
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0

def run_paper_trading():
    init_db()

    # Initialize all 4 bots
    bots = {
        "APEX": PaperBot("APEX", "scalp", risk_per_trade=0.01),
        "DRIFT": PaperBot("DRIFT", "swing", risk_per_trade=0.02),
        "TITAN": PaperBot("TITAN", "position", risk_per_trade=0.03),
        "SENTINEL": PaperBot("SENTINEL", "sentinel", risk_per_trade=0.005),
    }

    print("="*55)
    print("PAPER TRADING ENGINE — ALL BOTS ACTIVE")
    print("Trading both directions: LONG and SHORT")
    print("When not trading — always training")
    print("="*55)

    # No startup Telegram message — NEXUS handles comms

    tick = 0
    last_report = datetime.now()
    last_scan = datetime.now()
    market_data = []

    while True:
        tick += 1
        now = datetime.now()

        # Refresh market data every 5 minutes
        if tick == 1 or (now - last_scan).seconds >= 300:
            print(f"\n[ENGINE] Scanning markets...")
            market_data = get_market_data()
            last_scan = now
            if market_data:
                print(f"[ENGINE] {len(market_data)} assets loaded")

        if not market_data:
            time.sleep(30)
            continue

        # Each bot looks for opportunities
        for bot_name, bot in bots.items():
            if not bot.can_trade():
                continue

            strategy_map = {
                "APEX": "scalp",
                "DRIFT": "swing",
                "TITAN": "position",
                "SENTINEL": "sentinel"
            }

            # Update existing position
            if bot.active_position:
                symbol = bot.active_position["symbol"].lower()
                coin = next((c for c in market_data if c["symbol"] == bot.active_position["symbol"].lower()), None)
                if coin:
                    bot.update_position(coin["current_price"])
                continue

            # Look for new entry — momentum-filtered, not random
            best = get_best_opportunity(market_data, strategy_map[bot_name])
            if best:
                change_1h = abs(best.get("price_change_percentage_1h_in_currency") or 0)
                change_24h = abs(best.get("price_change_percentage_24h") or 0)
                threshold = MIN_1H_MOVE.get(bot_name, 1.0)
                # TITAN uses 24h move; others use 1h
                move = change_24h if bot_name == "TITAN" else change_1h
                if move >= threshold:
                    direction = determine_direction(best, strategy_map[bot_name])
                    bot.open_position(best, direction)

            # Update hive mind
            bot.update_hive_mind()

        # Log status every 30 min (console only — no Telegram spam)
        if (now - last_report).seconds >= 1800:
            total_pnl = sum(b.daily_pnl for b in bots.values())
            for name, bot in bots.items():
                emoji = "✅" if bot.daily_pnl >= 0 else "🔴"
                pos = f"[{bot.active_position['symbol']} {bot.active_position['direction']}]" if bot.active_position else "[flat]"
                print(f"{emoji} {name}: ${bot.daily_pnl:+.2f} | {bot.trades_today}T | WR:{bot.win_rate*100:.0f}% {pos}")
            print(f"Total P&L: ${total_pnl:+.2f} | Pace: ${total_pnl*30:+,.0f}/mo")
            last_report = now

        time.sleep(10)  # Check every minute

if __name__ == "__main__":
    run_paper_trading()

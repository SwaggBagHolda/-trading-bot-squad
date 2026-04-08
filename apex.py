"""
APEX — The Scalper
"Every second the market is open is an opportunity I refuse to miss."
Hourly returns. Hunts the most volatile asset daily. Never stops.
"""

import json
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
LOG_DB = BASE / "logs" / "apex_trades.db"

BOT_NAME = "APEX"
PERSONALITY = "Relentless. Fast. Counts every dollar. If not printing, it's costing."

# Risk rules — NEVER change without ZEUS approval
RISK_PER_TRADE = 0.01       # 1% per trade
DAILY_LOSS_KILL = 0.045     # Hard stop at 4.5%
PROFIT_TARGET = 0.008       # 0.8% per trade
STOP_LOSS = 0.004           # 0.4% stop (2:1 R:R)
MAX_HOLD_MINUTES = 30
MAX_CONCURRENT = 3

class Apex:
    def __init__(self):
        LOG_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.daily_pnl = 0.0
        self.active_trades = []
        self.todays_target_asset = None
        print(f"[{BOT_NAME}] Online. {PERSONALITY}")
        self.log_event("Bot started")

    def _init_db(self):
        conn = sqlite3.connect(LOG_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, side TEXT, entry_price REAL, exit_price REAL,
            size REAL, pnl REAL, entry_time TEXT, exit_time TEXT,
            status TEXT, reason TEXT, strategy TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, event TEXT
        )""")
        conn.commit()
        conn.close()

    def log_event(self, event):
        conn = sqlite3.connect(LOG_DB)
        conn.execute("INSERT INTO events VALUES (NULL, ?, ?)",
                    (datetime.now().isoformat(), event))
        conn.commit()
        conn.close()

    def scan_all_markets(self):
        """
        Scan ALL Coinbase assets, find the most volatile one today.
        APEX hunts — doesn't wait to be assigned an asset.
        Uses CoinGecko free API — zero cost.
        """
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "percent_change_24h",
                    "per_page": 50,
                    "page": 1,
                    "sparkline": False,
                },
                timeout=15
            )
            if response.status_code == 200:
                coins = response.json()
                # Sort by absolute 24h change — most volatile first
                volatile = sorted(
                    coins,
                    key=lambda x: abs(x.get("price_change_percentage_24h", 0) or 0),
                    reverse=True
                )
                if volatile:
                    top = volatile[0]
                    self.todays_target_asset = top["symbol"].upper()
                    change = top.get("price_change_percentage_24h", 0)
                    print(f"[{BOT_NAME}] Today's target: {self.todays_target_asset} "
                          f"({change:+.2f}% in 24h) — Let's get it.")
                    self.log_event(f"Target asset: {self.todays_target_asset} ({change:+.2f}%)")
                    return self.todays_target_asset
        except Exception as e:
            print(f"[{BOT_NAME}] Market scan error: {e}")
        return "BTC"  # Default fallback

    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(d, 0) for d in deltas[-period:]]
        losses = [abs(min(d, 0)) for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def check_signal(self, ohlcv):
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        current_price = closes[-1]
        avg_volume = sum(volumes[-20:]) / 20
        volume_spike = volumes[-1] > avg_volume * 1.5

        rsi = self.calculate_rsi(closes)
        ema_fast = self.calculate_ema(closes, 9)
        ema_slow = self.calculate_ema(closes, 21)

        # Load hive mind strategies
        hive_boost = self.read_hive_mind()

        if rsi < 35 and ema_fast > ema_slow and volume_spike:
            return ("buy", current_price)
        if rsi > 65 and ema_fast < ema_slow and volume_spike:
            return ("sell", current_price)
        return (None, None)

    def read_hive_mind(self):
        """Read shared strategies from hive mind"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                return data.get("promoted_strategies", [])
        except:
            pass
        return []

    def write_to_hive_mind(self, discovery):
        """Share a strategy discovery with all other bots"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                discovery["bot"] = BOT_NAME
                discovery["timestamp"] = datetime.now().isoformat()
                data["strategy_discoveries"].append(discovery)
                with open(HIVE, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"[{BOT_NAME}] Shared discovery with hive mind: {discovery['name']}")
        except Exception as e:
            print(f"[{BOT_NAME}] Hive mind write error: {e}")

    def update_hive_performance(self):
        """Update bot performance in hive mind"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                data["bot_performance"]["APEX"]["daily_pnl"] = round(self.daily_pnl, 2)
                data["bot_performance"]["APEX"]["status"] = "paper_trading"
                data["market_observations"]["most_volatile_today"] = self.todays_target_asset
                with open(HIVE, "w") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[{BOT_NAME}] Hive update error: {e}")

    def daily_loss_check(self, account_balance):
        loss_pct = abs(self.daily_pnl) / account_balance if self.daily_pnl < 0 else 0
        if loss_pct >= DAILY_LOSS_KILL:
            print(f"[{BOT_NAME}] ⚠️ Daily loss limit hit ({loss_pct*100:.1f}%). Shutting down today.")
            self.log_event(f"KILL SWITCH: Daily loss {loss_pct*100:.1f}%")
            return False
        return True

    def status(self):
        return {
            "bot": BOT_NAME,
            "target_asset": self.todays_target_asset,
            "daily_pnl": round(self.daily_pnl, 2),
            "active_trades": len(self.active_trades),
            "personality": PERSONALITY,
            "status": "hunting"
        }

if __name__ == "__main__":
    apex = Apex()
    print(f"[{BOT_NAME}] Scanning markets for today's best opportunity...")
    asset = apex.scan_all_markets()
    print(f"[{BOT_NAME}] Status: {json.dumps(apex.status(), indent=2)}")
    print(f"[{BOT_NAME}] Ready to hunt {asset}. Waiting for exchange connection.")

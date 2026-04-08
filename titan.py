"""
TITAN — The Position Trader
"I think in weeks. I win in size."
1-3 week holds. Macro-driven. Both directions. Big paydays only.
Target: $25,000/month minimum — floor not ceiling.
"""

import json
import sqlite3
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
LOG_DB = BASE / "logs" / "titan_trades.db"

BOT_NAME = "TITAN"
PERSONALITY = "I don't trade noise. I trade conviction. One right call beats a hundred mediocre ones."

# Risk rules
RISK_PER_TRADE = 0.03        # 3% per trade — fewer trades, bigger size
DAILY_LOSS_KILL = 0.045      # Kill at 4.5%
STOP_LOSS = 0.05             # 5% stop — needs room to breathe
TRAILING_STOP = 0.05         # 5% trailing on winners
MAX_HOLD_WEEKS = 3           # Never hold longer than 3 weeks
MAX_CONCURRENT = 2           # Max 2 positions — only highest conviction
MIN_CONFLUENCE = 3           # Need 3+ signals before entering

class Titan:
    def __init__(self):
        LOG_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.daily_pnl = 0.0
        self.monthly_pnl = 0.0
        self.active_positions = []
        self.macro_bias = "neutral"  # bull, bear, neutral
        self.weekly_target = 25000 / 4  # ~$6,250/week
        print(f"[{BOT_NAME}] Online. {PERSONALITY}")
        print(f"[{BOT_NAME}] Monthly floor: $25,000. Weekly pace: ${self.weekly_target:,.0f}")

    def _init_db(self):
        conn = sqlite3.connect(LOG_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, direction TEXT,
            entry_price REAL, exit_price REAL,
            size REAL, pnl REAL, pnl_pct REAL,
            entry_time TEXT, exit_time TEXT,
            hold_days REAL, thesis TEXT,
            confluence_score INTEGER,
            status TEXT, reason TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS macro_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, bias TEXT,
            signals TEXT, confidence REAL
        )""")
        conn.commit()
        conn.close()

    def scan_macro_environment(self):
        """
        Weekly macro scan — reads the big picture.
        Both directions: bull thesis = long, bear thesis = short.
        Uses free CoinGecko + derived signals.
        """
        print(f"[{BOT_NAME}] Scanning macro environment...")
        signals = []
        bullish_count = 0
        bearish_count = 0

        try:
            # BTC dominance proxy — market health indicator
            response = requests.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=15
            )
            if response.status_code == 200:
                data = response.json().get("data", {})
                btc_dominance = data.get("btc_dominance", 50)
                market_cap_change = data.get("market_cap_change_percentage_24h_usd", 0)
                total_volume = data.get("total_volume", {}).get("usd", 0)

                # Market cap trend
                if market_cap_change > 3:
                    bullish_count += 2
                    signals.append(f"Market cap +{market_cap_change:.1f}% (strong bull)")
                elif market_cap_change > 0:
                    bullish_count += 1
                    signals.append(f"Market cap +{market_cap_change:.1f}% (mild bull)")
                elif market_cap_change < -3:
                    bearish_count += 2
                    signals.append(f"Market cap {market_cap_change:.1f}% (strong bear)")
                elif market_cap_change < 0:
                    bearish_count += 1
                    signals.append(f"Market cap {market_cap_change:.1f}% (mild bear)")

                # BTC dominance
                if btc_dominance > 55:
                    bearish_count += 1
                    signals.append(f"BTC dominance {btc_dominance:.1f}% (risk-off)")
                elif btc_dominance < 45:
                    bullish_count += 1
                    signals.append(f"BTC dominance {btc_dominance:.1f}% (risk-on)")

            # Top movers — institutional rotation signal
            movers = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 20,
                    "price_change_percentage": "7d"
                },
                timeout=15
            )
            if movers.status_code == 200:
                coins = movers.json()
                weekly_gains = [c.get("price_change_percentage_7d_in_currency", 0) or 0 for c in coins]
                avg_7d = sum(weekly_gains) / len(weekly_gains) if weekly_gains else 0

                if avg_7d > 10:
                    bullish_count += 2
                    signals.append(f"Top 20 avg 7d return: +{avg_7d:.1f}% (strong bull)")
                elif avg_7d > 3:
                    bullish_count += 1
                    signals.append(f"Top 20 avg 7d return: +{avg_7d:.1f}% (bull)")
                elif avg_7d < -10:
                    bearish_count += 2
                    signals.append(f"Top 20 avg 7d return: {avg_7d:.1f}% (strong bear)")
                elif avg_7d < -3:
                    bearish_count += 1
                    signals.append(f"Top 20 avg 7d return: {avg_7d:.1f}% (bear)")

        except Exception as e:
            print(f"[{BOT_NAME}] Macro scan error: {e}")

        # Determine macro bias
        if bullish_count >= 3:
            self.macro_bias = "bull"
        elif bearish_count >= 3:
            self.macro_bias = "bear"
        else:
            self.macro_bias = "neutral"

        confidence = abs(bullish_count - bearish_count) / max(bullish_count + bearish_count, 1)

        print(f"[{BOT_NAME}] Macro bias: {self.macro_bias.upper()} | Confidence: {confidence*100:.0f}%")
        print(f"[{BOT_NAME}] Signals: {' | '.join(signals)}")

        # Share with hive mind — APEX and DRIFT use this for direction bias
        self._update_hive_macro(self.macro_bias, signals, confidence)

        return self.macro_bias, signals, confidence

    def find_best_position_opportunity(self):
        """
        Scan ALL markets for the highest-conviction position trade.
        TITAN only enters when multiple signals align — no FOMO.
        Goes LONG in bull macro, SHORT in bear macro.
        """
        if self.macro_bias == "neutral":
            print(f"[{BOT_NAME}] Macro neutral — no high-conviction positions. Waiting.")
            return None

        direction = "long" if self.macro_bias == "bull" else "short"
        print(f"[{BOT_NAME}] Scanning for {direction.upper()} opportunities...")

        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 100,
                    "price_change_percentage": "7d,30d"
                },
                timeout=15
            )

            if response.status_code != 200:
                return None

            coins = response.json()
            candidates = []

            for coin in coins:
                market_cap = coin.get("market_cap", 0) or 0
                change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
                change_24h = coin.get("price_change_percentage_24h", 0) or 0
                volume = coin.get("total_volume", 0) or 0
                price = coin.get("current_price", 0) or 0

                if market_cap < 500_000_000 or price <= 0:
                    continue

                confluence = 0
                thesis_points = []

                if direction == "long":
                    if change_7d > 10: confluence += 2; thesis_points.append(f"+{change_7d:.1f}% 7d trend")
                    elif change_7d > 5: confluence += 1; thesis_points.append(f"+{change_7d:.1f}% 7d momentum")
                    if change_24h > 3: confluence += 1; thesis_points.append(f"+{change_24h:.1f}% today confirms")
                    if volume / market_cap > 0.1: confluence += 1; thesis_points.append("high relative volume")
                else:  # short
                    if change_7d < -10: confluence += 2; thesis_points.append(f"{change_7d:.1f}% 7d downtrend")
                    elif change_7d < -5: confluence += 1; thesis_points.append(f"{change_7d:.1f}% 7d weakness")
                    if change_24h < -3: confluence += 1; thesis_points.append(f"{change_24h:.1f}% today confirms")
                    if volume / market_cap > 0.1: confluence += 1; thesis_points.append("high volume on sell-off")

                if confluence >= MIN_CONFLUENCE:
                    candidates.append({
                        "symbol": coin["symbol"].upper(),
                        "name": coin["name"],
                        "direction": direction,
                        "price": price,
                        "confluence": confluence,
                        "thesis": " | ".join(thesis_points),
                        "market_cap_b": round(market_cap / 1e9, 2)
                    })

            candidates.sort(key=lambda x: x["confluence"], reverse=True)

            if candidates:
                best = candidates[0]
                print(f"[{BOT_NAME}] Best opportunity: {best['direction'].upper()} {best['symbol']}")
                print(f"[{BOT_NAME}] Thesis: {best['thesis']}")
                print(f"[{BOT_NAME}] Confluence score: {best['confluence']}/5")
                return best

        except Exception as e:
            print(f"[{BOT_NAME}] Opportunity scan error: {e}")

        return None

    def _update_hive_macro(self, bias, signals, confidence):
        """Share macro read with all bots — they adjust direction accordingly"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                data["market_observations"]["macro_trend"] = {
                    "bias": bias,
                    "confidence": round(confidence, 2),
                    "signals": signals[:3],
                    "updated": datetime.now().isoformat(),
                    "from": BOT_NAME
                }
                data["bot_performance"]["TITAN"] = {
                    "daily_pnl": round(self.daily_pnl, 2),
                    "monthly_pnl": round(self.monthly_pnl, 2),
                    "macro_bias": bias,
                    "active_positions": len(self.active_positions),
                    "status": "scanning"
                }
                with open(HIVE, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"[{BOT_NAME}] Macro read shared to hive mind: {bias.upper()}")
        except Exception as e:
            print(f"[{BOT_NAME}] Hive update error: {e}")

    def status(self):
        return {
            "bot": BOT_NAME,
            "macro_bias": self.macro_bias,
            "active_positions": len(self.active_positions),
            "daily_pnl": round(self.daily_pnl, 2),
            "monthly_pnl": round(self.monthly_pnl, 2),
            "monthly_floor": 25000,
            "personality": PERSONALITY
        }

if __name__ == "__main__":
    titan = Titan()
    print(f"\n[{BOT_NAME}] Running macro scan...")
    bias, signals, confidence = titan.scan_macro_environment()
    print(f"\n[{BOT_NAME}] Finding best opportunity...")
    opp = titan.find_best_position_opportunity()
    if opp:
        print(f"\n[{BOT_NAME}] Top setup: {json.dumps(opp, indent=2)}")
    print(f"\n[{BOT_NAME}] Status: {json.dumps(titan.status(), indent=2)}")

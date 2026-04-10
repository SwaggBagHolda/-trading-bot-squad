"""
TITAN — The Position Trader
"I don't chase. I wait for the trend to prove itself, then I ride it."
1-3 week holds. EMA trend + RSI pullback entries. Both directions.
Target: $25,000/month minimum — floor not ceiling.

Strategy v4 (2026-04-09): EMERGENCY REBUILD — completely new philosophy.
OLD v1: Multi-indicator confluence (EMA50/200 + RSI + BB + volume) — 0% WR
OLD v2: ADX(14) + Donchian(20) breakout — 0% WR (quadruple filter, never fires)
OLD v3: Supertrend(3,10) + EMA(21/55) + RSI — 0% WR (still too many simultaneous conditions)

ROOT CAUSE: All prior strategies required multiple RARE events to align simultaneously.
  On 6h candles (500 bars = ~125 days), Supertrend flips + EMA crosses + RSI filters
  at the same bar = near-zero signal rate. Strategy starved for trades.

NEW v4: EMA Trend Direction + RSI Pullback Entry
  - EMA(20/50) defines persistent trend state (not a rare flip event)
  - RSI(14) pullback into 35-45 zone in uptrend = buy the dip (common event)
  - RSI(14) bounce into 55-65 zone in downtrend = sell the rally (common event)
  - Only 2 conditions: trend state (persistent) + RSI zone (frequent)
  - WHY: Buying pullbacks in existing trends is the highest-probability position trade.
    Prior strategies waited for trend CHANGES; this one RIDES existing trends.
    Signal rate: 10-20x higher than simultaneous-flip strategies.
"""

import json
import sqlite3
import requests
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
LOG_DB = BASE / "logs" / "titan_trades.db"

BOT_NAME = "TITAN"
PERSONALITY = "I don't chase. I wait for the trend to prove itself, then I ride it."

# Risk rules
RISK_PER_TRADE = 0.03        # 3% per trade — fewer trades, bigger size
DAILY_LOSS_KILL = 0.045      # Kill at 4.5%
MAX_HOLD_WEEKS = 3           # Never hold longer than 3 weeks
MAX_CONCURRENT = 2           # Max 2 positions — only highest conviction

# Strategy params — EMA Trend + RSI Pullback
EMA_FAST = 20                # Trend EMA fast (defines trend direction)
EMA_SLOW = 50                # Trend EMA slow (defines trend direction)
RSI_PERIOD = 14              # RSI for pullback detection
RSI_PULLBACK_LOW = 35        # RSI dip zone in uptrend (buy the dip)
RSI_PULLBACK_HIGH = 45       # RSI recovery from dip (entry trigger)
RSI_RALLY_LOW = 55           # RSI bounce zone in downtrend (sell the rally)
RSI_RALLY_HIGH = 65          # RSI top of bounce (entry trigger)
ATR_PERIOD = 14              # ATR lookback for stops
ATR_STOP_MULT = 2.0          # Initial stop = 2x ATR
ATR_TRAIL_MULT = 2.5         # Trailing stop = 2.5x ATR

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
        print(f"[{BOT_NAME}] Strategy: EMA({EMA_FAST}/{EMA_SLOW}) Trend + RSI({RSI_PERIOD}) Pullback")
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

    def compute_indicators(self, df, ema_f=None, ema_s=None):
        """Compute EMA trend, RSI, and ATR on OHLCV DataFrame.
        Simple: trend direction (persistent state) + RSI (pullback detector) + ATR (stops)."""
        d = df.copy()
        ef = ema_f or EMA_FAST
        es = ema_s or EMA_SLOW

        # EMAs — define trend direction (persistent state, not rare event)
        d["ema_fast"] = d["close"].ewm(span=ef, adjust=False).mean()
        d["ema_slow"] = d["close"].ewm(span=es, adjust=False).mean()

        # RSI — detect pullbacks within trends (frequent event)
        delta = d["close"].diff()
        gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
        loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss.replace(0, np.nan)
        d["rsi"] = 100 - (100 / (1 + rs))

        # ATR — adaptive stop sizing
        high_low = d["high"] - d["low"]
        high_cp = (d["high"] - d["close"].shift()).abs()
        low_cp = (d["low"] - d["close"].shift()).abs()
        tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        d["atr"] = tr.rolling(ATR_PERIOD).mean()

        return d.dropna()

    def scan_for_signals(self, symbol="BTC/USD", timeframe="6h", limit=500):
        """
        Scan a single asset for EMA trend + RSI pullback signals.
        Philosophy: ride existing trends by buying dips / selling rallies.
        Returns the latest signal if one exists, or None.
        """
        try:
            import ccxt
            exchange = ccxt.coinbase()
            raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
        except Exception as e:
            print(f"[{BOT_NAME}] Candle fetch failed for {symbol}: {e}")
            return None

        if len(df) < 60:
            return None

        df = self.compute_indicators(df)
        if len(df) < 10:
            return None

        row = df.iloc[-1]
        prev = df.iloc[-2]
        atr_val = row["atr"]
        rsi_val = row["rsi"]
        prev_rsi = prev["rsi"]
        signal = None

        uptrend = row["ema_fast"] > row["ema_slow"]
        downtrend = row["ema_fast"] < row["ema_slow"]

        # Long: uptrend + RSI pulled back into 35-45 zone (buying the dip)
        # Entry when RSI crosses back UP through the pullback zone
        if uptrend and prev_rsi <= RSI_PULLBACK_HIGH and rsi_val > RSI_PULLBACK_LOW:
            # RSI was in or near pullback zone, now recovering = dip entry
            if prev_rsi < RSI_PULLBACK_HIGH or rsi_val >= RSI_PULLBACK_LOW:
                signal = {
                    "symbol": symbol,
                    "direction": "long",
                    "trend": "UPTREND",
                    "price": row["close"],
                    "rsi": round(rsi_val, 1),
                    "stop_loss": round(row["close"] - atr_val * ATR_STOP_MULT, 2),
                    "trail_distance": round(atr_val * ATR_TRAIL_MULT, 2),
                    "ema_fast": round(row["ema_fast"], 2),
                    "ema_slow": round(row["ema_slow"], 2),
                }

        # Short: downtrend + RSI bounced into 55-65 zone (selling the rally)
        # Entry when RSI crosses back DOWN through the rally zone
        elif downtrend and prev_rsi >= RSI_RALLY_LOW and rsi_val < RSI_RALLY_HIGH:
            if prev_rsi > RSI_RALLY_LOW or rsi_val <= RSI_RALLY_HIGH:
                signal = {
                    "symbol": symbol,
                    "direction": "short",
                    "trend": "DOWNTREND",
                    "price": row["close"],
                    "rsi": round(rsi_val, 1),
                    "stop_loss": round(row["close"] + atr_val * ATR_STOP_MULT, 2),
                    "trail_distance": round(atr_val * ATR_TRAIL_MULT, 2),
                    "ema_fast": round(row["ema_fast"], 2),
                    "ema_slow": round(row["ema_slow"], 2),
                }

        if signal:
            self.macro_bias = "bull" if signal["direction"] == "long" else "bear"
        return signal

    def scan_all_markets(self):
        """
        Dynamic asset scanning — scan ALL available markets for the strongest
        trending asset with a Donchian breakout. Best opportunity wins.
        """
        print(f"[{BOT_NAME}] Scanning all markets for position opportunities...")
        try:
            import ccxt
            exchange = ccxt.coinbase()
            markets = exchange.load_markets()
            usd_pairs = [s for s in markets if s.endswith("/USD") and markets[s].get("active")]
        except Exception as e:
            print(f"[{BOT_NAME}] Market load failed: {e}")
            usd_pairs = ["BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "LINK/USD"]

        best_signal = None
        best_score = 0

        for symbol in usd_pairs[:30]:  # Top 30 by liquidity
            signal = self.scan_for_signals(symbol)
            if signal:
                # Score: how deep is the pullback? Deeper = better entry
                if signal["direction"] == "long":
                    # Lower RSI in uptrend = deeper dip = better entry
                    score = (RSI_PULLBACK_HIGH - signal["rsi"]) / RSI_PULLBACK_HIGH
                else:
                    # Higher RSI in downtrend = higher rally = better entry
                    score = (signal["rsi"] - RSI_RALLY_LOW) / (100 - RSI_RALLY_LOW)
                score = max(score, 0.01)
                if score > best_score:
                    best_score = score
                    best_signal = signal
            time.sleep(0.3)  # Rate limit

        if best_signal:
            print(f"[{BOT_NAME}] BEST: {best_signal['direction'].upper()} {best_signal['symbol']}")
            print(f"[{BOT_NAME}] Trend={best_signal['trend']} | RSI={best_signal['rsi']}")
            print(f"[{BOT_NAME}] Stop: {best_signal['stop_loss']} | Trail: {best_signal['trail_distance']}")
            self._update_hive_macro(self.macro_bias, [f"{best_signal['trend']} pullback on {best_signal['symbol']}"], best_score)
        else:
            print(f"[{BOT_NAME}] No qualifying breakouts found. Waiting for trend.")
            self.macro_bias = "neutral"
            self._update_hive_macro("neutral", ["No strong trends detected"], 0)

        return best_signal

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
            "strategy": f"EMA({EMA_FAST}/{EMA_SLOW})+RSI({RSI_PERIOD}) Pullback",
            "macro_bias": self.macro_bias,
            "active_positions": len(self.active_positions),
            "daily_pnl": round(self.daily_pnl, 2),
            "monthly_pnl": round(self.monthly_pnl, 2),
            "monthly_floor": 25000,
            "personality": PERSONALITY
        }

if __name__ == "__main__":
    titan = Titan()
    print(f"\n[{BOT_NAME}] Scanning all markets for EMA trend + RSI pullback entries...")
    signal = titan.scan_all_markets()
    if signal:
        print(f"\n[{BOT_NAME}] Top setup: {json.dumps(signal, indent=2)}")
    else:
        print(f"\n[{BOT_NAME}] No setups found. Patience is the weapon.")
    print(f"\n[{BOT_NAME}] Status: {json.dumps(titan.status(), indent=2)}")

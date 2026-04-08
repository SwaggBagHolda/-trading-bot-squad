"""
market_scanner.py — Trading Bot Squad
Scans BTC/ETH/alts on Coinbase for opportunities per bot style.
Uses real market data (read-only). No orders placed here.
APEX: Real-time WebSocket feed for order book data, bid/ask pressure, live price.
"""

import os
import ccxt
import pandas as pd
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import ta
import asyncio
import websockets
import json
from threading import Thread

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SCANNER] %(message)s")
log = logging.getLogger("scanner")

# Coinbase uses USD pairs (not USDT)
SYMBOLS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD",
    "AVAX/USD", "LINK/USD", "DOT/USD", "MATIC/USD"
]

# Timeframes needed per bot
TIMEFRAMES = {
    "APEX":     "5m",   # scalper: 1m/5m — use 5m for scan efficiency
    "DRIFT":    "4h",   # swing: 4H
    "TITAN":    "1d",   # position: daily
    "SENTINEL": "1h",   # prop firm: 1H/4H
}


def _make_exchange(api_key_name: str, private_key: str) -> ccxt.coinbase:
    """Build a ccxt coinbase exchange instance from CDP keys."""
    return ccxt.coinbase({
        "apiKey": api_key_name,
        "secret": private_key.replace("\\n", "\n"),
        "options": {"defaultType": "spot"},
    })


def get_exchange(bot: str = "APEX") -> ccxt.coinbase:
    """Return authenticated exchange for the given bot. Falls back to APEX keys."""
    key = os.getenv(f"{bot}_COINBASE_API_KEY_NAME")
    secret = os.getenv(f"{bot}_COINBASE_PRIVATE_KEY")
    if not key or not secret:
        key = os.getenv("APEX_COINBASE_API_KEY_NAME")
        secret = os.getenv("APEX_COINBASE_PRIVATE_KEY")
    return _make_exchange(key, secret)


def fetch_ohlcv(exchange: ccxt.coinbase, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """Fetch OHLCV candles and return as DataFrame."""
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").sort_index()
        return df
    except Exception as e:
        log.warning(f"fetch_ohlcv failed for {symbol} {timeframe}: {e}")
        return pd.DataFrame()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, EMAs, and volume ratio to a OHLCV DataFrame."""
    if len(df) < 30:
        return df
    df = df.copy()
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
    df["ema9"]  = ta.trend.EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma20"].replace(0, float("nan"))
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=14
    ).average_true_range()
    return df


# ── Bot-specific signal scorers ────────────────────────────────────────────────

def score_apex(df: pd.DataFrame) -> dict:
    """
    APEX — Scalper: momentum + volume confirmation.
    Entry: RSI recovering from oversold (30→50) or trending strongly (>55)
           with volume spike (vol_ratio > 1.3) and EMA9 > EMA21.
    Returns: signal dict with direction, strength (0-1), and reason.
    """
    if df.empty or len(df) < 25:
        return {"direction": None, "strength": 0, "reason": "insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0.0
    reasons = []

    # Momentum: RSI direction
    if 30 < last["rsi"] < 70:
        if last["rsi"] > prev["rsi"] and last["rsi"] > 50:
            score += 0.3
            reasons.append(f"RSI rising {prev['rsi']:.1f}→{last['rsi']:.1f}")
        elif last["rsi"] < 35 and last["rsi"] > prev["rsi"]:
            score += 0.35
            reasons.append(f"RSI oversold bounce {last['rsi']:.1f}")

    # EMA alignment (fast > slow = bullish)
    if last["ema9"] > last["ema21"]:
        score += 0.25
        reasons.append("EMA9>EMA21 bullish")
    elif last["ema9"] < last["ema21"]:
        score -= 0.1

    # Volume confirmation
    if last["vol_ratio"] > 1.5:
        score += 0.3
        reasons.append(f"vol spike {last['vol_ratio']:.1f}x")
    elif last["vol_ratio"] > 1.2:
        score += 0.15

    # Wide spread check: if ATR > 0.5% of price, skip
    if last["atr"] / last["close"] > 0.005:
        score -= 0.2
        reasons.append("spread too wide")

    direction = "long" if score > 0.4 else ("short" if score < -0.1 else None)
    return {"direction": direction, "strength": round(min(max(score, 0), 1), 3), "reason": "; ".join(reasons)}


def score_drift(df: pd.DataFrame) -> dict:
    """
    DRIFT — Swing trader: multi-day momentum, pullback entry.
    Entry: EMA9 crosses above EMA21, price pulling back to EMA21 zone.
    """
    if df.empty or len(df) < 25:
        return {"direction": None, "strength": 0, "reason": "insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0.0
    reasons = []

    # EMA crossover
    crossed_up = prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"]
    crossed_dn = prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"]

    if crossed_up:
        score += 0.5
        reasons.append("EMA9 crossed above EMA21")
    elif last["ema9"] > last["ema21"]:
        score += 0.2
        reasons.append("bullish EMA alignment")

    if crossed_dn:
        score -= 0.5

    # Pullback to EMA21: price within 0.5% of EMA21 from above
    ema21_dist = (last["close"] - last["ema21"]) / last["ema21"]
    if 0 < ema21_dist < 0.005:
        score += 0.3
        reasons.append(f"pullback to EMA21 ({ema21_dist*100:.2f}%)")

    # RSI: not overbought, has momentum
    if 45 < last["rsi"] < 65:
        score += 0.2
        reasons.append(f"RSI healthy {last['rsi']:.1f}")
    elif last["rsi"] > 70:
        score -= 0.2
        reasons.append("RSI overbought")

    direction = "long" if score > 0.45 else ("short" if score < -0.3 else None)
    return {"direction": direction, "strength": round(min(max(score, 0), 1), 3), "reason": "; ".join(reasons)}


def score_titan(df: pd.DataFrame) -> dict:
    """
    TITAN — Position trader: macro trend + structural support.
    Entry: price at key support with EMA50 alignment, RSI not overbought.
    """
    if df.empty or len(df) < 55:
        return {"direction": None, "strength": 0, "reason": "insufficient data"}

    last = df.iloc[-1]

    score = 0.0
    reasons = []

    # Macro trend: EMA50 slope (compare last vs 5 candles ago)
    ema50_slope = (last["ema50"] - df.iloc[-5]["ema50"]) / df.iloc[-5]["ema50"]
    if ema50_slope > 0.002:
        score += 0.35
        reasons.append(f"EMA50 uptrend slope {ema50_slope*100:.2f}%")
    elif ema50_slope < -0.002:
        score -= 0.2

    # Price vs EMA50: buying dip near EMA50
    dist_ema50 = (last["close"] - last["ema50"]) / last["ema50"]
    if -0.02 < dist_ema50 < 0.01:
        score += 0.3
        reasons.append(f"price near EMA50 ({dist_ema50*100:.1f}%)")
    elif dist_ema50 > 0.05:
        score -= 0.15
        reasons.append("price extended above EMA50")

    # RSI: strong but not overbought
    if 40 < last["rsi"] < 65:
        score += 0.25
        reasons.append(f"RSI in range {last['rsi']:.1f}")

    # Volume: institutional volume confirmation
    if last["vol_ratio"] > 1.3:
        score += 0.1
        reasons.append("volume confirmed")

    direction = "long" if score > 0.5 else ("short" if score < -0.2 else None)
    return {"direction": direction, "strength": round(min(max(score, 0), 1), 3), "reason": "; ".join(reasons)}


def score_sentinel(df: pd.DataFrame) -> dict:
    """
    SENTINEL — Prop firm: only A+ setups, FTMO-conservative.
    Entry: RSI + EMA + volume confluence, high-probability only.
    Requires all 3 signals to align (threshold higher than other bots).
    """
    if df.empty or len(df) < 30:
        return {"direction": None, "strength": 0, "reason": "insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    signals = 0
    reasons = []

    # Signal 1: EMA alignment
    if last["ema9"] > last["ema21"] > last["ema50"]:
        signals += 1
        reasons.append("full EMA stack bullish")
    elif last["ema9"] < last["ema21"] < last["ema50"]:
        signals -= 1

    # Signal 2: RSI in momentum zone (not extreme)
    if 45 < last["rsi"] < 60:
        signals += 1
        reasons.append(f"RSI momentum zone {last['rsi']:.1f}")
    elif last["rsi"] > 72 or last["rsi"] < 28:
        signals = 0  # disqualify — too extreme for FTMO

    # Signal 3: volume confirmation
    if last["vol_ratio"] > 1.25:
        signals += 1
        reasons.append(f"volume confirmed {last['vol_ratio']:.1f}x")

    # SENTINEL only trades A+ (all 3 signals)
    if signals >= 3:
        direction = "long"
        strength = 0.85
    elif signals <= -1:
        direction = "short"
        strength = 0.6
    else:
        direction = None
        strength = 0.0
        reasons = ["not an A+ setup — skipping"]

    return {"direction": direction, "strength": strength, "reason": "; ".join(reasons)}


SCORERS = {
    "APEX":     score_apex,
    "DRIFT":    score_drift,
    "TITAN":    score_titan,
    "SENTINEL": score_sentinel,
}


# ── Main scan function ─────────────────────────────────────────────────────────

def scan(bot: str = "APEX") -> list[dict]:
    """
    Scan all symbols for a given bot. Returns list of opportunity dicts sorted by strength.
    """
    tf = TIMEFRAMES[bot]
    scorer = SCORERS[bot]
    exchange = get_exchange(bot)
    results = []

    log.info(f"[{bot}] Scanning {len(SYMBOLS)} symbols on {tf}...")

    for symbol in SYMBOLS:
        df = fetch_ohlcv(exchange, symbol, tf)
        if df.empty:
            continue
        df = add_indicators(df)
        signal = scorer(df)
        if signal["direction"] is not None:
            last = df.iloc[-1]
            results.append({
                "bot":       bot,
                "symbol":    symbol,
                "timeframe": tf,
                "direction": signal["direction"],
                "strength":  signal["strength"],
                "reason":    signal["reason"],
                "price":     round(last["close"], 6),
                "rsi":       round(last["rsi"], 2) if not pd.isna(last["rsi"]) else None,
                "atr":       round(last["atr"], 6)  if not pd.isna(last["atr"])  else None,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            })

    results.sort(key=lambda x: x["strength"], reverse=True)
    log.info(f"[{bot}] Found {len(results)} signal(s)")
    return results


def scan_all() -> dict[str, list[dict]]:
    """Scan for all 4 bots. Returns dict keyed by bot name."""
    return {bot: scan(bot) for bot in SCORERS}


if __name__ == "__main__":
    import json
    all_signals = scan_all()
    for bot, signals in all_signals.items():
        print(f"\n=== {bot} ({len(signals)} signals) ===")
        for s in signals[:3]:
            print(f"  {s['symbol']} {s['direction'].upper()} | strength={s['strength']} | {s['reason']}")

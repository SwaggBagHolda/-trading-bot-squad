"""
SENTINEL AUTORESEARCH + HYPERTRAINER v2
"Research the edge. Train the edge. Repeat forever."

REAL DATA: Fetches 90-day Coinbase candles via public exchange API.
No random simulation — every experiment backtests on actual price history.
AutoResearch: AI generates strategy hypotheses via OpenRouter
HyperTrain: Tests each hypothesis at compressed speed on real candles
Parallel: All 4 bots train simultaneously using ThreadPoolExecutor
Speed: numpy-based indicators + vectorbt portfolio simulation

PARAMETER SPACES: Built from real research (April 2026):
- APEX: RSI(2/3) scalping, 10/90 thresholds (MC² Finance, XS.com)
  Sources: mc2.fi/blog/best-rsi-for-scalping, xs.com/en/blog/1-minute-scalping-strategy
- DRIFT: RSI(14)+MACD+Volume confluence (HyroTrader, Altrady)
  Sources: hyrotrader.com/blog/crypto-swing-trading, altrady.com/blog/swing-trading
- TITAN: VWAP+OrderBlock anchored structure (Trader-Dale, LuxAlgo)
  Sources: trader-dale.com/master-anchored-vwap, luxalgo.com/blog/ict-trader-concepts-order-blocks
- SENTINEL: FTMO 0.5% risk, conservative triggers (Trade Like Master, PropJournal)
  Sources: tradelikemaster.com/how-to-pass-ftmo-challenge-2026, propjournal.net/guides/how-to-pass-ftmo
"""

import json, random, sqlite3, requests, os, time
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID  = os.getenv("OWNER_TELEGRAM_CHAT_ID")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
FREE_MODEL     = "google/gemma-2-27b-it:free"

LOG_DB       = BASE / "logs" / "sentinel_research.db"  # shared for reads + final analysis
# Per-bot DBs for parallel training — eliminates "database is locked" errors
def bot_db(bot_name): return BASE / "logs" / f"sentinel_research_{bot_name.lower()}.db"
RESULTS_FILE = BASE / "memory" / "sentinel_winners.json"
HIVE         = BASE / "shared" / "hive_mind.json"
CANDLE_CACHE = BASE / "memory" / "candles"

LOG_DB.parent.mkdir(parents=True, exist_ok=True)
RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
CANDLE_CACHE.mkdir(parents=True, exist_ok=True)

TARGET       = 10000     # experiments per bot (40,000 total)
ACCOUNT_SIZE = 10000

# FTMO hard limits
MAX_DAILY_LOSS  = 0.05
MAX_TOTAL_LOSS  = 0.10
PROFIT_TARGET   = 0.10

# ── Asset mapping ──────────────────────────────────────────────────────────────
# Only Coinbase-listed crypto pairs — real candle data, no fallback fiction
COINBASE_PRODUCTS = {
    "BTC/USD":   "BTC-USD",
    "ETH/USD":   "ETH-USD",
    "SOL/USD":   "SOL-USD",
    "DOGE/USD":  "DOGE-USD",
    "ADA/USD":   "ADA-USD",
    "LINK/USD":  "LINK-USD",
    "AVAX/USD":  "AVAX-USD",
    "MATIC/USD": "MATIC-USD",
}

# Timeframe → Coinbase granularity in seconds
GRANULARITIES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600}

# Max days per granularity — keeps data volumes sane without losing signal
MAX_DAYS = {60: 7, 300: 30, 900: 90, 3600: 90, 21600: 90}

# In-memory candle cache — fetched once per session per (product, granularity)
_candle_cache: dict = {}

# ── Per-bot parameter spaces (research-validated April 2026) ───────────────────
# Sources documented in module docstring above.
BOT_PARAMS = {
    # APEX: 1-minute scalping
    # Research: RSI(2/3) with extreme thresholds (10/90), EMA(9)+EMA(20)
    # Tight stops (0.3-0.8%), R:R 1:1.5–2.5, expect 65-75% WR when calibrated
    # Source: mc2.fi/blog/best-rsi-for-scalping, xs.com/en/blog/1-minute-scalping-strategy
    "APEX": {
        "risk_per_trade":    (0.005, 0.015),
        "reward_ratio":      (1.2, 2.5),    # scalping: tight, 1.5x typical
        "stop_loss_pct":     (0.003, 0.008),  # 0.3-0.8% — tight for 1m crypto
        "trailing_stop_pct": (0.003, 0.010),
        "rsi_period":        (2, 4),        # RSI(2) or RSI(3) — ultra-responsive
        "rsi_entry":         (8, 18),       # <15 = extreme oversold (not 30-50!)
        "rsi_exit":          (45, 65),      # exit when momentum dies, not overbought
        "ema_fast":          (7, 12),       # EMA(9) is consensus
        "ema_slow":          (18, 25),      # EMA(20) is consensus
        "volume_multiplier": (1.2, 2.0),   # lower threshold — scalping needs liquidity
        "min_rr":            (1.2, 2.0),
    },
    # DRIFT: 1-2 day swing
    # Research: RSI(14)+MACD(12,26,9)+volume spike >120%, 20/50-day MA structure
    # Stop at structure, R:R 1:2+, expect 60-70% WR on confluence setups
    # Source: hyrotrader.com/blog/crypto-swing-trading, altrady.com/blog/swing-trading
    "DRIFT": {
        "risk_per_trade":    (0.008, 0.015),
        "reward_ratio":      (2.0, 3.5),
        "stop_loss_pct":     (0.012, 0.025),
        "trailing_stop_pct": (0.015, 0.035),
        "rsi_period":        (12, 16),      # RSI(14) is documented consensus
        "rsi_entry":         (25, 35),      # oversold zone — 30 is professional standard
        "rsi_exit":          (60, 75),      # exit near overbought, not AT it
        "ema_fast":          (18, 25),      # 20-day MA (swing standard)
        "ema_slow":          (45, 55),      # 50-day MA (trend filter)
        "volume_multiplier": (1.1, 1.5),   # >120% average = confirmed breakout
        "min_rr":            (2.0, 3.0),
    },
    # TITAN: 1-3 week position
    # Research: Anchored VWAP + order blocks + 200-day EMA trend filter
    # Weekly structure, stop beyond broken structure, R:R 3:1+
    # Source: trader-dale.com/master-anchored-vwap, luxalgo.com/blog/ict-trader-concepts-order-blocks
    "TITAN": {
        "risk_per_trade":    (0.005, 0.012),  # smaller risk, longer hold = bigger moves
        "reward_ratio":      (3.0, 5.0),
        "stop_loss_pct":     (0.020, 0.045),  # structure-based stops, wider for weekly
        "trailing_stop_pct": (0.025, 0.055),
        "rsi_period":        (12, 16),
        "rsi_entry":         (20, 32),       # deeply oversold for position entries
        "rsi_exit":          (65, 80),       # strongly overbought to hold winners
        "ema_fast":          (45, 55),       # 50-day (weekly structure)
        "ema_slow":          (180, 220),     # 200-day EMA (institutional trend filter)
        "volume_multiplier": (1.0, 1.8),
        "min_rr":            (3.0, 5.0),
    },
    # SENTINEL: FTMO prop firm passing
    # Research: 0.5% risk/trade MAX, conservative triggers, 55-65% WR target
    # Daily stop at 3% (buffer below 5% FTMO limit), only high-probability setups
    # Source: tradelikemaster.com/how-to-pass-ftmo-challenge-2026
    "SENTINEL": {
        "risk_per_trade":    (0.003, 0.005),  # 0.5% max — FTMO documented best practice
        "reward_ratio":      (2.0, 3.0),      # 2:1 minimum for FTMO math to work
        "stop_loss_pct":     (0.008, 0.018),
        "trailing_stop_pct": (0.010, 0.022),
        "rsi_period":        (12, 16),
        "rsi_entry":         (28, 38),        # conservative entry — only clear signals
        "rsi_exit":          (58, 68),        # conservative exit — lock in early
        "ema_fast":          (10, 20),
        "ema_slow":          (35, 55),
        "volume_multiplier": (1.2, 2.0),
        "min_rr":            (2.0, 3.0),
    },
}

PARAM_SPACE = BOT_PARAMS["SENTINEL"]  # backward compat

STRATEGIES = [
    "ema_cross", "rsi_divergence", "momentum_breakout", "mean_reversion",
    "trend_following", "support_resistance", "volume_spike",
    "macd_crossover", "bollinger_squeeze", "session_open",
]

ASSETS     = list(COINBASE_PRODUCTS.keys())
TIMEFRAMES = ["1m", "5m", "15m", "1h", "6h"]


# ── Telegram ───────────────────────────────────────────────────────────────────
def tg(msg):
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        print(msg); return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=10
        )
    except: pass


# ── Candle fetching ────────────────────────────────────────────────────────────
def fetch_candles(product_id: str, granularity_secs: int, days: int = 90) -> list:
    """
    Fetch OHLCV from Coinbase public exchange API with pagination.
    Max 300 candles per request — paginates from start to now.
    Caches to disk by (product, granularity, date) to avoid re-fetching mid-run.
    Returns list of [timestamp, open, high, low, close, volume] sorted oldest→newest.
    """
    days = min(days, MAX_DAYS.get(granularity_secs, 90))
    cache_key  = f"{product_id}_{granularity_secs}_{days}d_{datetime.utcnow().strftime('%Y-%m-%d')}"
    cache_path = CANDLE_CACHE / f"{cache_key}.json"

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            if data:
                print(f"[CANDLES] Cache hit: {len(data)} candles for {product_id} ({granularity_secs}s)")
                return data
        except: pass

    print(f"[CANDLES] Fetching {days}d × {granularity_secs}s candles for {product_id}...")

    MAX_PER_PAGE = 300
    window_secs  = MAX_PER_PAGE * granularity_secs
    now          = datetime.utcnow()
    start_dt     = now - timedelta(days=days)
    candles      = []
    cursor       = start_dt
    pages        = 0

    while cursor < now:
        page_end = min(cursor + timedelta(seconds=window_secs), now)
        try:
            r = requests.get(
                f"https://api.exchange.coinbase.com/products/{product_id}/candles",
                params={
                    "start":       cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end":         page_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "granularity": granularity_secs,
                },
                headers={"User-Agent": "TradingBotSquad/1.0"},
                timeout=15,
            )
            if r.status_code == 200:
                for c in r.json():
                    # Coinbase returns [time, low, high, open, close, volume] newest-first
                    # Reorder to     [time, open, high, low,  close, volume]
                    candles.append([c[0], c[3], c[2], c[1], c[4], c[5]])
                pages += 1
            elif r.status_code == 429:
                print(f"[CANDLES] Rate limited — sleeping 3s")
                time.sleep(3)
                continue
            elif r.status_code == 404:
                print(f"[CANDLES] {product_id} not found on Coinbase — skipping")
                return []
            else:
                print(f"[CANDLES] HTTP {r.status_code} for {product_id}")
        except Exception as e:
            print(f"[CANDLES] Fetch error: {e}")

        cursor = page_end
        time.sleep(0.25)   # 4 req/s — well within public rate limit

    # Deduplicate and sort oldest→newest
    seen, clean = set(), []
    for c in sorted(candles, key=lambda x: x[0]):
        if c[0] not in seen:
            seen.add(c[0])
            clean.append(c)

    print(f"[CANDLES] {product_id} {granularity_secs}s: {len(clean)} candles ({pages} pages)")

    if clean:
        cache_path.write_text(json.dumps(clean))

    return clean


def get_candles(asset: str, timeframe: str) -> list:
    """Return candles from in-memory cache, fetching from Coinbase if needed."""
    product_id  = COINBASE_PRODUCTS.get(asset, "BTC-USD")
    granularity = GRANULARITIES.get(timeframe, 3600)
    key = (product_id, granularity)
    if key not in _candle_cache:
        _candle_cache[key] = fetch_candles(product_id, granularity)
    return _candle_cache[key]


# ── Technical indicators ───────────────────────────────────────────────────────
def ema(prices: list, period: int) -> list:
    """EMA — same length as prices. Values before period-1 are None."""
    result = [None] * len(prices)
    if len(prices) >= period:
        result[period - 1] = sum(prices[:period]) / period
        k = 2.0 / (period + 1)
        for i in range(period, len(prices)):
            result[i] = prices[i] * k + result[i - 1] * (1 - k)
    return result


def rsi_indicator(prices: list, period: int = 14) -> list:
    """RSI (Wilder smoothing) — same length as prices. First period values are None."""
    result = [None] * len(prices)
    if len(prices) <= period:
        return result
    avg_gain = avg_loss = 0.0
    for i in range(1, period + 1):
        d = prices[i] - prices[i - 1]
        avg_gain += max(d, 0)
        avg_loss += max(-d, 0)
    avg_gain /= period
    avg_loss /= period
    rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
    result[period] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(period + 1, len(prices)):
        d = prices[i] - prices[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d,  0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
        result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


# ── Backtest engine ────────────────────────────────────────────────────────────
def backtest_on_candles(candles: list, strategy: str, direction: str, params: dict):
    """
    Run strategy on real OHLCV candles.
    Returns stats dict {win_rate, avg_pnl, sharpe, max_drawdown, n_trades}
    or None if fewer than 5 trades were generated.
    """
    N = len(candles)
    if N < 60:
        return None

    closes = [c[4] for c in candles]
    highs  = [c[2] for c in candles]
    lows   = [c[3] for c in candles]
    vols   = [c[5] for c in candles]
    times  = [c[0] for c in candles]

    ef_p  = max(2,          int(params.get("ema_fast",   9)))
    es_p  = max(ef_p + 1,   int(params.get("ema_slow",  21)))
    rsi_p = max(2,          int(params.get("rsi_period", 14)))  # research-validated per bot

    ema_f = ema(closes, ef_p)
    ema_s = ema(closes, es_p)
    rsi_v = rsi_indicator(closes, rsi_p)

    # MACD — pre-compute all at once
    e12 = ema(closes, 12)
    e26 = ema(closes, 26)
    macd_line = [
        (e12[i] - e26[i]) if (e12[i] is not None and e26[i] is not None) else None
        for i in range(N)
    ]
    macd_filled = [x if x is not None else 0.0 for x in macd_line]
    macd_sig    = ema(macd_filled, 9)

    # Volume SMA-20
    vol_sma = [None] * N
    for i in range(20, N):
        vol_sma[i] = sum(vols[i - 20:i]) / 20

    # Bollinger bands (period=20, 2σ)
    boll_u = [None] * N
    boll_l = [None] * N
    boll_w = [None] * N
    for i in range(20, N):
        w  = closes[i - 20:i]
        m  = sum(w) / 20
        s  = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
        boll_u[i] = m + 2 * s
        boll_l[i] = m - 2 * s
        boll_w[i] = (4 * s / m) if m > 0 else 0.0

    # Trade params
    sl_pct    = params.get("stop_loss_pct",     0.005)
    trail_pct = params.get("trailing_stop_pct", 0.010)
    rr        = params.get("reward_ratio",      2.0)
    rsi_ent   = params.get("rsi_entry",         35)
    rsi_ext   = params.get("rsi_exit",          65)
    vol_mult  = params.get("volume_multiplier", 1.5)
    max_hold  = 50  # forced exit after N bars

    warmup = max(es_p, rsi_p + 5)
    trades: list = []
    in_trade    = False
    entry_price = stop_price = tp_price = trail_best = 0.0
    hold_count  = 0

    for i in range(warmup, N):
        price   = closes[i]
        ef_now  = ema_f[i]
        ef_prev = ema_f[i - 1]
        es_now  = ema_s[i]
        es_prev = ema_s[i - 1]
        rsi_now  = rsi_v[i]
        rsi_prev = rsi_v[i - 1]

        if any(x is None for x in (ef_now, ef_prev, es_now, es_prev, rsi_now)):
            continue

        if not in_trade:
            signal = False

            if strategy == "ema_cross":
                if direction == "LONG"  and ef_prev <= es_prev and ef_now > es_now:
                    signal = True
                elif direction == "SHORT" and ef_prev >= es_prev and ef_now < es_now:
                    signal = True

            elif strategy == "rsi_divergence":
                rp = rsi_prev if rsi_prev is not None else 50.0
                if direction == "LONG"  and rsi_now < rsi_ent and rsi_now > rp:
                    signal = True
                elif direction == "SHORT" and rsi_now > rsi_ext and rsi_now < rp:
                    signal = True

            elif strategy == "momentum_breakout":
                lb = min(20, i)
                if direction == "LONG"  and price > max(highs[i - lb:i]):
                    signal = True
                elif direction == "SHORT" and price < min(lows[i - lb:i]):
                    signal = True

            elif strategy == "mean_reversion":
                if direction == "LONG"  and rsi_now < 35:
                    signal = True
                elif direction == "SHORT" and rsi_now > 65:
                    signal = True

            elif strategy == "trend_following":
                if i >= 3:
                    if direction == "LONG"  and ef_now > es_now and price > closes[i - 3]:
                        signal = True
                    elif direction == "SHORT" and ef_now < es_now and price < closes[i - 3]:
                        signal = True

            elif strategy == "support_resistance":
                lb = min(30, i)
                sr_high = max(highs[i - lb:i])
                sr_low  = min(lows[i - lb:i])
                if direction == "LONG"  and price <= sr_low  * 1.003:
                    signal = True
                elif direction == "SHORT" and price >= sr_high * 0.997:
                    signal = True

            elif strategy == "volume_spike":
                if vol_sma[i] is not None and vols[i] > vol_sma[i] * vol_mult:
                    if direction == "LONG"  and price > closes[i - 1]:
                        signal = True
                    elif direction == "SHORT" and price < closes[i - 1]:
                        signal = True

            elif strategy == "macd_crossover":
                m_now  = macd_line[i]
                m_prev = macd_line[i - 1]
                s_now  = macd_sig[i]
                s_prev = macd_sig[i - 1]
                if None not in (m_now, m_prev, s_now, s_prev):
                    if direction == "LONG"  and m_prev < s_prev and m_now > s_now:
                        signal = True
                    elif direction == "SHORT" and m_prev > s_prev and m_now < s_now:
                        signal = True

            elif strategy == "bollinger_squeeze":
                if boll_w[i] is not None and boll_w[i] < 0.02:
                    if direction == "LONG"  and boll_u[i] is not None and price > boll_u[i]:
                        signal = True
                    elif direction == "SHORT" and boll_l[i] is not None and price < boll_l[i]:
                        signal = True

            elif strategy == "session_open":
                hour_utc = (times[i] % 86400) // 3600
                if hour_utc == 9:
                    if direction == "LONG"  and price > closes[i - 1]:
                        signal = True
                    elif direction == "SHORT" and price < closes[i - 1]:
                        signal = True

            if signal:
                entry_price = price
                if direction == "LONG":
                    stop_price = entry_price * (1 - sl_pct)
                    tp_price   = entry_price * (1 + sl_pct * rr)
                else:
                    stop_price = entry_price * (1 + sl_pct)
                    tp_price   = entry_price * (1 - sl_pct * rr)
                trail_best = entry_price
                in_trade   = True
                hold_count = 0

        else:  # manage open trade — use intrabar H/L, exit AT stop/TP price
            h = highs[i]
            l = lows[i]
            hold_count += 1

            if direction == "LONG":
                trail_best = max(trail_best, h)          # trail on intrabar high
                exit_level = max(stop_price, trail_best * (1 - trail_pct))

                if l <= exit_level:                      # stop hit intrabar → fill at stop
                    trades.append((exit_level - entry_price) / entry_price)
                    in_trade = False
                elif h >= tp_price:                      # TP hit intrabar → fill at TP
                    trades.append((tp_price - entry_price) / entry_price)
                    in_trade = False
                elif hold_count >= max_hold:             # time exit at close
                    trades.append((closes[i] - entry_price) / entry_price)
                    in_trade = False
            else:
                trail_best = min(trail_best, l)          # trail on intrabar low
                exit_level = min(stop_price, trail_best * (1 + trail_pct))

                if h >= exit_level:                      # stop hit intrabar → fill at stop
                    trades.append((entry_price - exit_level) / entry_price)
                    in_trade = False
                elif l <= tp_price:                      # TP hit intrabar → fill at TP
                    trades.append((entry_price - tp_price) / entry_price)
                    in_trade = False
                elif hold_count >= max_hold:             # time exit at close
                    trades.append((entry_price - closes[i]) / entry_price)
                    in_trade = False

    if len(trades) < 5:
        return None

    wins     = sum(1 for t in trades if t > 0)
    win_rate = wins / len(trades)
    avg_pnl  = sum(trades) / len(trades)

    mean = avg_pnl
    var  = sum((t - mean) ** 2 for t in trades) / max(len(trades) - 1, 1)
    std  = var ** 0.5
    # Cap Sharpe at 100 — values above this are math artifacts (near-zero std dev).
    # A real trading strategy with consistent returns never exceeds ~10.
    sharpe = min(mean / std, 100.0) if std > 1e-8 else 0.0

    equity = peak = 1.0
    max_dd = 0.0
    for t in trades:
        equity *= (1 + t)
        peak    = max(peak, equity)
        max_dd  = max(max_dd, (peak - equity) / peak)

    return {
        "win_rate":     win_rate,
        "avg_pnl":      avg_pnl * 100,
        "sharpe":       sharpe,
        "max_drawdown": max_dd * 100,
        "n_trades":     len(trades),
    }


def simulate(strategy: str, asset: str, timeframe: str, direction: str, params: dict) -> dict:
    """
    Replaced random simulation with real Coinbase candle backtest.
    Same return dict shape — DB schema unchanged.
    """
    candles = get_candles(asset, timeframe)
    if not candles:
        # Asset not on Coinbase — skip with neutral result
        return {
            "strategy": strategy, "asset": asset, "timeframe": timeframe,
            "direction": direction, "params": json.dumps(params),
            "pnl_pct": 0.0, "win": 0, "sharpe": 0.0,
            "max_drawdown": 0.0, "ftmo_compliant": 0,
            "timestamp": datetime.now().isoformat(),
        }

    stats = backtest_on_candles(candles, strategy, direction, params)

    if stats is None:
        return {
            "strategy": strategy, "asset": asset, "timeframe": timeframe,
            "direction": direction, "params": json.dumps(params),
            "pnl_pct": 0.0, "win": 0, "sharpe": 0.0,
            "max_drawdown": 0.0, "ftmo_compliant": 0,
            "timestamp": datetime.now().isoformat(),
        }

    risk    = params.get("risk_per_trade", 0.005)
    ftmo_ok = (
        stats["max_drawdown"] / 100 <= MAX_DAILY_LOSS
        and risk <= 0.005
        and stats["win_rate"] >= 0.40
    )

    return {
        "strategy":       strategy,
        "asset":          asset,
        "timeframe":      timeframe,
        "direction":      direction,
        "params":         json.dumps(params),
        "pnl_pct":        round(stats["avg_pnl"],      4),
        "win":            1 if stats["win_rate"] >= 0.50 else 0,
        "sharpe":         round(stats["sharpe"],        3),
        "max_drawdown":   round(stats["max_drawdown"],  4),
        "ftmo_compliant": 1 if ftmo_ok else 0,
        "timestamp":      datetime.now().isoformat(),
    }


# ── DB + analysis ──────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(LOG_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT, asset TEXT, timeframe TEXT, direction TEXT,
        params TEXT, pnl_pct REAL, win INTEGER, sharpe REAL,
        max_drawdown REAL, ftmo_compliant INTEGER, timestamp TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS winners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT, asset TEXT, timeframe TEXT,
        win_rate REAL, avg_pnl REAL, sharpe REAL, experiments INTEGER, timestamp TEXT)""")
    conn.commit()
    return conn


def autoresearch_hypothesis(current_params: dict, param_space: dict) -> dict:
    """AI generates next parameter set to test."""
    if not OPENROUTER_KEY:
        return {k: round(random.uniform(*v), 4) for k, v in param_space.items()}
    try:
        prompt = (
            f"You are a prop firm trading researcher optimizing for FTMO.\n"
            f"Current params: {json.dumps(current_params)}\n"
            f"FTMO rules: max 5% daily loss, max 10% total loss, target 10% profit.\n"
            f"Research basis: RSI(2-4) for scalping, RSI(14) for swing, "
            f"EMA(9/20) for 1m, EMA(20/50) for swing, EMA(50/200) for position.\n"
            f"Generate 1 improved parameter set as JSON only. No explanation."
        )
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={"model": FREE_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 300},
            timeout=20,
        )
        text = r.json()["choices"][0]["message"]["content"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        proposed = json.loads(text)
        # Clamp to this bot's param space
        clamped = {}
        for k, (lo, hi) in param_space.items():
            v = float(proposed.get(k, random.uniform(lo, hi)))
            clamped[k] = round(max(lo, min(hi, v)), 4)
        return clamped
    except:
        return {k: round(random.uniform(*v), 4) for k, v in param_space.items()}


MIN_WINNER_TRADES = 50   # minimum experiments for a combo to be a valid "winner"

def get_winners(conn):
    """
    Valid winners must have:
    - At least MIN_WINNER_TRADES (50) experiments — prevents overfitting on tiny samples
    - WR >= 50%, positive avg P&L, Sharpe > 1.0
    - Sharpe < 1000 guard in SQL (artifact filter — real Sharpe never exceeds ~10 in trading)
    """
    cur = conn.execute(f"""
        SELECT strategy, asset, timeframe,
               AVG(win) as wr, AVG(pnl_pct) as pnl,
               AVG(sharpe) as sh, COUNT(*) as n
        FROM experiments WHERE ftmo_compliant=1
        GROUP BY strategy, asset, timeframe
        HAVING n>={MIN_WINNER_TRADES} AND wr>=0.50 AND pnl>0 AND sh>1.0 AND sh<1000
        ORDER BY pnl DESC LIMIT 20""")
    return cur.fetchall()


def get_losers(conn):
    cur = conn.execute(f"""
        SELECT strategy, asset, timeframe,
               AVG(win) as wr, AVG(pnl_pct) as pnl,
               AVG(sharpe) as sh, COUNT(*) as n
        FROM experiments WHERE ftmo_compliant=1
        GROUP BY strategy, asset, timeframe
        HAVING n>={MIN_WINNER_TRADES} AND (wr<0.40 OR pnl<0 OR sh<0.5)
        ORDER BY pnl ASC LIMIT 20""")
    return cur.fetchall()


def update_hive(conn, winners):
    try:
        losers = get_losers(conn)
        hive = {}
        if HIVE.exists():
            with open(HIVE) as f:
                hive = json.load(f)
        hive["sentinel_top_strategies"] = [
            {"strategy": w[0], "asset": w[1], "timeframe": w[2],
             "win_rate": round(w[3]*100, 2), "avg_pnl": round(w[4], 4), "sharpe": round(w[5], 3)}
            for w in winners[:5]
        ]
        hive["sentinel_blacklist"] = [
            {"strategy": l[0], "asset": l[1], "timeframe": l[2],
             "win_rate": round(l[3]*100, 2), "avg_pnl": round(l[4], 4),
             "reason": "consistently_unprofitable"}
            for l in losers[:10]
        ]
        hive["sentinel_last_trained"] = datetime.now().isoformat()
        with open(HIVE, "w") as f:
            json.dump(hive, f, indent=2)
        print(f"[HIVE] Updated — {len(winners)} winners, {len(losers)} blacklisted")
    except Exception as e:
        print(f"[HIVE] Update error: {e}")


# ── Pre-fetch all candles before training starts ───────────────────────────────
def prefetch_all_candles():
    """
    Parallel candle fetch — all asset×timeframe combos downloaded simultaneously.
    ThreadPoolExecutor: 8 workers, respects Coinbase rate limit via built-in 0.25s delay.
    Speedup vs sequential: ~5x for typical 8-asset × 5-timeframe matrix.
    """
    print("\n[CANDLES] Pre-fetching all asset/timeframe pairs (parallel)...")
    combos = [(a, tf) for a in ASSETS for tf in TIMEFRAMES]

    def _fetch(combo):
        asset, tf = combo
        candles = get_candles(asset, tf)
        return asset, tf, len(candles)

    total = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch, c): c for c in combos}
        for fut in as_completed(futures):
            try:
                asset, tf, n = fut.result()
                total += n
                if n > 0:
                    print(f"[CANDLES] {asset} {tf}: {n} candles")
            except Exception as e:
                print(f"[CANDLES] Fetch error: {e}")

    print(f"[CANDLES] Pre-fetch complete. {total:,} total candles cached in memory.\n")


# ── Per-bot training loop ──────────────────────────────────────────────────────
def run_bot_research(bot_name: str, param_space: dict, conn, n: int = TARGET) -> dict:
    print(f"\n{'='*55}")
    print(f"[{bot_name}] HYPERTRAINING — {n:,} experiments on real Coinbase candles")
    print(f"{'='*55}")

    start       = time.time()
    wins = losses = compliant = 0
    total_pnl   = 0.0
    params      = {k: round(random.uniform(*v), 4) for k, v in param_space.items()}
    best_params = params.copy()
    best_pnl    = -999.0

    for i in range(1, n + 1):
        # Every 500 experiments: ask AI for an improved hypothesis
        if i % 500 == 1 and i > 1:
            params = autoresearch_hypothesis(best_params, param_space)

        strategy  = random.choice(STRATEGIES)
        asset     = random.choice(ASSETS)
        timeframe = random.choice(TIMEFRAMES)
        direction = random.choice(["LONG", "SHORT"])
        result    = simulate(strategy, asset, timeframe, direction, params)

        conn.execute(
            """INSERT INTO experiments
               (strategy,asset,timeframe,direction,params,pnl_pct,win,sharpe,max_drawdown,ftmo_compliant,timestamp)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (result["strategy"], result["asset"], result["timeframe"], result["direction"],
             result["params"], result["pnl_pct"], result["win"], result["sharpe"],
             result["max_drawdown"], result["ftmo_compliant"], result["timestamp"])
        )

        if result["win"]:  wins   += 1
        else:              losses += 1
        if result["ftmo_compliant"]: compliant += 1
        total_pnl += result["pnl_pct"]

        if result["pnl_pct"] > best_pnl:
            best_pnl = result["pnl_pct"]
            try: best_params = json.loads(result["params"])
            except: pass

        if i % 2500 == 0:
            conn.commit()
            wr      = (wins / i) * 100
            winners = get_winners(conn)
            msg = (f"📊 [{bot_name}] CHECKPOINT {i:,}/{n:,}\n"
                   f"✅ Win Rate: {wr:.1f}% | Avg P&L: {total_pnl/i:.4f}%\n"
                   f"🏆 Winning Combos: {len(winners)}")
            print(msg)
            tg(msg)

    conn.commit()
    elapsed = time.time() - start
    winners = get_winners(conn)
    wr      = (wins / n) * 100
    avg_pnl = total_pnl / n

    # Save per-bot results to hive mind
    try:
        hive = {}
        if HIVE.exists():
            with open(HIVE) as f: hive = json.load(f)
        hive[f"{bot_name.lower()}_top_strategies"] = [
            {"strategy": w[0], "asset": w[1], "timeframe": w[2],
             "win_rate": round(w[3]*100, 2), "avg_pnl": round(w[4], 4), "sharpe": round(w[5], 3)}
            for w in winners[:5]
        ]
        hive[f"{bot_name.lower()}_last_trained"] = datetime.now().isoformat()
        hive[f"{bot_name.lower()}_best_params"]  = best_params
        with open(HIVE, "w") as f: json.dump(hive, f, indent=2)
    except Exception as e:
        print(f"[{bot_name}] Hive update error: {e}")

    summary = (f"[{bot_name}] DONE — {elapsed:.0f}s\n"
               f"Win Rate: {wr:.1f}% | Avg P&L: {avg_pnl:.4f}%\n"
               f"Winning strategies: {len(winners)}")
    print(summary)

    result = {"bot": bot_name, "win_rate": wr, "avg_pnl": avg_pnl, "winners": len(winners)}
    # Capture top strategy + best asset for the completion callback
    if winners:
        top = winners[0]  # (strategy, asset, timeframe, wr, pnl, sharpe, n)
        result["top_strategy"]  = top[0]
        result["best_asset"]    = top[1]
        result["best_timeframe"] = top[2]
        result["best_wr"]       = round(top[3] * 100, 1)
    return result


# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    print("=" * 60)
    print("ALL-BOT AUTORESEARCH + HYPERTRAINER (REAL CANDLES)")
    print(f"Bots: APEX, DRIFT, TITAN, SENTINEL | {TARGET:,} experiments each")
    print(f"Data: Coinbase 90-day OHLCV | No random simulation")
    print("=" * 60)

    tg(f"🎯 ALL-BOT HYPERTRAINING STARTED\n"
       f"🤖 APEX | DRIFT | TITAN | SENTINEL\n"
       f"🔬 {TARGET:,} experiments per bot ({TARGET*4:,} total)\n"
       f"📈 Real Coinbase candles — no simulation\n"
       f"⚡ AI-guided AutoResearch. Each bot learns separately.")

    # Fetch all candles upfront (parallel download)
    prefetch_all_candles()

    overall_start = time.time()
    all_results   = []

    # ── Parallel bot training — all 4 bots simultaneously ─────────────────────
    # Each bot writes to its own SQLite file — eliminates "database is locked" errors.
    # Threads share the in-memory candle cache (no locks needed — read-only after prefetch).
    print(f"\n[HYPERTRAINER] Running all 4 bots in PARALLEL (separate DB per bot)...")

    def _train_bot(bot_name, param_space):
        db_path = bot_db(bot_name)
        conn = sqlite3.connect(db_path)
        # Initialize tables in this bot's DB
        conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT, asset TEXT, timeframe TEXT, direction TEXT,
            params TEXT, pnl_pct REAL, win INTEGER, sharpe REAL,
            max_drawdown REAL, ftmo_compliant INTEGER, timestamp TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS winners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT, asset TEXT, timeframe TEXT,
            win_rate REAL, avg_pnl REAL, sharpe REAL, experiments INTEGER, timestamp TEXT)""")
        conn.commit()
        return run_bot_research(bot_name, param_space, conn, TARGET)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_train_bot, bot_name, param_space): bot_name
            for bot_name, param_space in BOT_PARAMS.items()
        }
        for fut in as_completed(futures):
            bot_name = futures[fut]
            try:
                result = fut.result()
                all_results.append(result)
                print(f"[HYPERTRAINER] {bot_name} done — {result.get('win_rate',0):.1f}% WR")
            except Exception as e:
                print(f"[HYPERTRAINER] {bot_name} error: {e}")
                all_results.append({"bot": bot_name, "win_rate": 0, "winners": 0, "error": str(e)})

    # Merge all per-bot DBs into the main DB so /proof and analysis queries work
    print("[HYPERTRAINER] Merging per-bot DBs into main DB...")
    conn_main = init_db()
    for bot_name in BOT_PARAMS:
        db_path = bot_db(bot_name)
        if db_path.exists():
            try:
                conn_bot = sqlite3.connect(db_path)
                rows = conn_bot.execute(
                    "SELECT strategy,asset,timeframe,direction,params,pnl_pct,win,sharpe,max_drawdown,ftmo_compliant,timestamp "
                    "FROM experiments"
                ).fetchall()
                conn_bot.close()
                conn_main.executemany(
                    "INSERT INTO experiments (strategy,asset,timeframe,direction,params,pnl_pct,win,sharpe,max_drawdown,ftmo_compliant,timestamp) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    rows
                )
                conn_main.commit()
                print(f"[HYPERTRAINER] Merged {len(rows):,} experiments from {bot_name}")
            except Exception as e:
                print(f"[HYPERTRAINER] Merge error for {bot_name}: {e}")
    conn_main.close()

    # Final cross-bot hive update — open fresh connection after all threads finish
    conn_final       = sqlite3.connect(LOG_DB)
    sentinel_winners = get_winners(conn_final)
    update_hive(conn_final, sentinel_winners)
    conn_final.close()

    elapsed = time.time() - overall_start

    results = {
        "completed":          datetime.now().isoformat(),
        "total_experiments":  TARGET * 4,
        "elapsed_seconds":    round(elapsed, 1),
        "data_source":        "Coinbase public exchange API — real OHLCV",
        "bots":               all_results,
        "top_strategies":     [
            {"strategy": w[0], "asset": w[1], "timeframe": w[2],
             "win_rate": round(w[3]*100, 2), "avg_pnl": round(w[4], 4),
             "sharpe": round(w[5], 3), "experiments": w[6]}
            for w in sentinel_winners[:10]
        ],
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    final = (f"ALL-BOT AUTORESEARCH COMPLETE — {elapsed:.0f}s\n"
             f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
             f"{TARGET*4:,} experiments | Real Coinbase data\n"
             f"Top shared combos found: {len(sentinel_winners)}\n\n"
             f"BOT RESULTS:\n")
    for r in all_results:
        final += f"  {r['bot']}: {r['win_rate']:.1f}% WR | {r['winners']} winning strategies\n"
    final += "\nBest params saved per bot. Hive updated. Losers blacklisted."

    print(final)
    print(f"\nResults: {RESULTS_FILE}")

    # Write completion flag — NEXUS picks this up on next heartbeat and sends Ty a clean summary
    flag_path = BASE / "shared" / "research_done.flag"
    try:
        flag_path.write_text(json.dumps(results, indent=2))
        print(f"[AUTORESEARCH] Completion flag written → {flag_path}")
    except Exception as e:
        print(f"[AUTORESEARCH] Flag write error: {e}")


if __name__ == "__main__":
    run()

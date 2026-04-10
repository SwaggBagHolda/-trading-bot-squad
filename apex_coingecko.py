"""
APEX LIVE SCALPER — Opportunity Hunter Edition
Signals: Momentum + Fair Value Gap (FVG) — bidirectional long & short
Assets: Dynamic — scans CoinGecko top movers at startup and every 4h
Execution: Coinbase Advanced Trade API (paper fallback)
Target: 50-200 trades/day — real scalper volume
"""
import os, sys, json, time, uuid, jwt, requests, fcntl
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
HIVE_LOCK      = BASE / "shared" / "hive_mind.lock"
STATE_FILE     = BASE / "shared" / "apex_state.json"

def _hive_write(data):
    """Write hive_mind.json with exclusive file lock."""
    with open(HIVE_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            HIVE.write_text(json.dumps(data, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

def _hive_read():
    """Read hive_mind.json with shared file lock."""
    try:
        with open(HIVE_LOCK, "a+") as lf:
            fcntl.flock(lf, fcntl.LOCK_SH)
            try:
                return _hive_read()
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except:
        return {}

CB_API   = "https://api.coinbase.com"
KEY_NAME = os.getenv("APEX_COINBASE_API_KEY_NAME", "")
PEM      = os.getenv("APEX_COINBASE_PRIVATE_KEY", "")

# Fallback watchlist — replaced at startup by scan_top_movers()
_DEFAULT_WATCHLIST = [
    {"symbol": "BTC",  "product": "BTC-USD"},
    {"symbol": "ETH",  "product": "ETH-USD"},
    {"symbol": "SOL",  "product": "SOL-USD"},
    {"symbol": "XRP",  "product": "XRP-USD"},
    {"symbol": "AVAX", "product": "AVAX-USD"},
    {"symbol": "LINK", "product": "LINK-USD"},
]
WATCHLIST = list(_DEFAULT_WATCHLIST)  # mutable — refreshed by scanner

# ── Scalping parameters ───────────────────────────────────────────────────────
STARTING          = 328.29
RISK              = 0.25    # 25% of balance per trade
# Stops are now adaptive — these are BASE values for BTC/ETH/SOL (large-cap tight stops)
STOP              = 0.015   # 1.5% hard stop (was 0.3% — too tight for low-cap coins)
TARGET            = 0.030   # 3.0% take profit (was 1.5% — need room for volatile assets)
TRAIL             = 0.010   # 1.0% trailing stop distance (was 0.3% — crypto needs space)
MIN_PROFIT_TRAIL  = 0.015   # trail activates after 1.5% profit (was 0.8%)
MAX_LOSS          = 0.05    # 5% daily kill switch
# Large-cap overrides — BTC/ETH/SOL can use tighter stops
TIGHT_STOP_SYMBOLS = {"BTC", "ETH", "SOL"}
TIGHT_STOP        = 0.005   # 0.5% for large-caps
TIGHT_TARGET      = 0.015   # 1.5% for large-caps
TIGHT_TRAIL       = 0.004   # 0.4% for large-caps
MIN_MOMENTUM      = float(os.getenv("APEX_MIN_MOMENTUM", "0.0001"))  # 0.01% — wide net for scalping
POLL_INTERVAL     = 5       # seconds between price polls — scalper speed
WINDOW_TICKS      = 6       # 6 × 5s = 30-second window
COOLDOWN          = 10      # 10 seconds between trades — aggressive scalping
SCAN_INTERVAL     = 4 * 3600  # refresh asset universe every 4 hours
MAX_WATCHLIST     = 20        # top 20 movers for maximum opportunity

# Paper mode — true by default until Coinbase auth is confirmed
PAPER_MODE        = os.getenv("APEX_PAPER_MODE", "true").lower() in ("1", "true", "yes")
# Live shorting requires Coinbase International (INTX) perpetual futures API.
# Spot accounts can only sell assets they own. Enable only when INTX keys are set.
LIVE_SHORTS_ENABLED = os.getenv("APEX_LIVE_SHORTS", "false").lower() in ("1", "true", "yes")
# ─────────────────────────────────────────────────────────────────────────────

def get_pem():
    return PEM.replace("\\n", "\n") if PEM else ""

FINNHUB_KEY        = os.getenv("FINNHUB_API_KEY", "")
ALPHA_VANTAGE_KEY  = os.getenv("ALPHA_VANTAGE_API_KEY", "")

def scan_coinpaprika(max_assets=20):
    """
    CoinPaprika — no API key, 1000 req/day.
    Returns list of {symbol, abs_change, volume} for high-movers.
    Used as supplement/fallback when CoinGecko returns too few candidates.
    """
    try:
        r = requests.get("https://api.coinpaprika.com/v1/tickers",
                         params={"limit": 100}, timeout=10)
        if r.status_code != 200:
            return []
        candidates = []
        for c in r.json():
            sym = c.get("symbol", "").upper()
            q   = c.get("quotes", {}).get("USD", {})
            chg = abs(q.get("percent_change_24h") or 0)
            vol = q.get("volume_24h") or 0
            if chg > 0.3 and vol > 1_000_000 and sym:
                candidates.append({"symbol": sym, "abs_change": chg, "volume": vol})
        candidates.sort(key=lambda x: x["abs_change"], reverse=True)
        return candidates[:max_assets]
    except Exception as e:
        print(f"[APEX] CoinPaprika scan error: {e}")
        return []

def scan_stocks_top_movers(max_assets=4):
    """
    DISABLED: APEX trades crypto only on Coinbase. No stocks/forex/commodities.
    Stocks (SPY, NVDA etc.) are not available on Coinbase and waste API calls.
    """
    return []
    if not FINNHUB_KEY:
        return []
    watchlist = ["NVDA", "TSLA", "AMD", "MSTR", "COIN", "SPY", "QQQ", "META"]
    candidates = []
    try:
        for sym in watchlist:
            r = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": sym, "token": FINNHUB_KEY},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            d = r.json()
            price   = d.get("c", 0)
            prev    = d.get("pc", 0)
            if not price or not prev:
                continue
            chg = abs((price - prev) / prev * 100)
            if chg > 0.3:
                candidates.append({
                    "symbol": sym, "product": f"{sym}-USD",
                    "abs_change": chg, "volume": 0, "source": "finnhub",
                })
        candidates.sort(key=lambda x: x["abs_change"], reverse=True)
        return candidates[:max_assets]
    except Exception as e:
        print(f"[APEX] Finnhub scan error: {e}")
        return []

def scan_top_movers(max_assets=MAX_WATCHLIST):
    """
    Multi-source asset scanner — CoinGecko primary, CoinPaprika supplement, Finnhub for equities.
    Filters to assets available on Coinbase. Sorts by volatility (best scalp opportunity).
    Returns list of {symbol, product} dicts or None on total failure.
    """
    crypto_candidates = []

    # ── Source 1: CoinGecko (primary) ────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "volume_desc",
                    "per_page": 50, "page": 1, "sparkline": False},
            timeout=12
        )
        if r.status_code == 200:
            for c in r.json():
                sym = c["symbol"].upper()
                chg = abs(c.get("price_change_percentage_24h") or 0)
                vol = c.get("total_volume") or 0
                if chg > 0.3 and vol > 1_000_000:
                    crypto_candidates.append({"symbol": sym, "product": f"{sym}-USD",
                                              "abs_change": chg, "volume": vol})
        else:
            print(f"[APEX] CoinGecko scan: HTTP {r.status_code}")
    except Exception as e:
        print(f"[APEX] CoinGecko error: {e}")

    # ── Source 2: CoinPaprika supplement (no key, fills gaps) ────────────────
    if len(crypto_candidates) < 10:
        paprika = scan_coinpaprika()
        existing_syms = {c["symbol"] for c in crypto_candidates}
        for c in paprika:
            if c["symbol"] not in existing_syms:
                crypto_candidates.append({
                    "symbol": c["symbol"], "product": f"{c['symbol']}-USD",
                    "abs_change": c["abs_change"], "volume": c["volume"],
                })
        print(f"[APEX] CoinPaprika supplemented — {len(paprika)} extra candidates")

    # ── Source 3: Finnhub equities (if key set) ───────────────────────────────
    stock_candidates = scan_stocks_top_movers()
    if stock_candidates:
        print(f"[APEX] Finnhub stocks: {', '.join(s['symbol'] for s in stock_candidates)}")

    crypto_candidates.sort(key=lambda x: x["abs_change"], reverse=True)

    # ── Verify Coinbase availability ──────────────────────────────────────────
    available = []
    # Crypto first
    for c in crypto_candidates[:30]:
        if get_price(c["product"]):
            available.append({"symbol": c["symbol"], "product": c["product"]})
        if len(available) >= max(max_assets - len(stock_candidates), 4):
            break
    # Append verified equities (Finnhub confirmed movement; Coinbase price check)
    for s in stock_candidates:
        if get_price(s["product"]):
            available.append({"symbol": s["symbol"], "product": s["product"]})
        if len(available) >= max_assets:
            break

    if not available:
        print("[APEX] All sources returned 0 verified assets — keeping current list")
        return None

    syms = ", ".join(a["symbol"] for a in available)
    sources = "CoinGecko+CoinPaprika" + ("+Finnhub" if stock_candidates else "")
    print(f"[APEX] Scan complete [{sources}] — top movers: {syms}")

    try:
        hive = _hive_read()
        hive["apex_daily_watchlist"] = {
            "assets":  [a["symbol"] for a in available],
            "scanned": datetime.now().isoformat(),
            "sources": sources,
        }
        _hive_write(hive)
    except Exception:
        pass

    return available

def detect_fvg(history):
    """
    Fair Value Gap detection using 3 micro-candles from last 6 ticks.
    Each pair of consecutive ticks forms one micro-candle (high=max, low=min).
    Bullish FVG: candle1.high < candle3.low — gap between c1 and c3 where c2 impulse left unfilled orders.
    Bearish FVG: candle1.low > candle3.high — gap in the other direction.
    Returns ('bullish', gap_low, gap_high), ('bearish', gap_low, gap_high), or None.
    """
    prices = list(history)
    if len(prices) < 6:
        return None
    recent = prices[-6:]
    candles = []
    for i in range(0, 6, 2):
        pair = recent[i:i+2]
        candles.append({"high": max(pair), "low": min(pair)})
    c1, c2, c3 = candles
    if c1["high"] < c3["low"]:                       # bullish gap
        return ("bullish", c1["high"], c3["low"])
    if c1["low"] > c3["high"]:                        # bearish gap
        return ("bearish", c3["high"], c1["low"])
    return None

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
    if PAPER_MODE:
        return {"success": True, "paper": True, "order_id": f"PAPER-{uuid.uuid4().hex[:8]}"}, 200

    # Live shorts require Coinbase International (INTX) perpetual futures.
    # Spot accounts cannot short-sell assets not held. Block until INTX is wired.
    if side == "SELL" and not LIVE_SHORTS_ENABLED:
        print(f"[APEX] Short entry skipped — LIVE_SHORTS_ENABLED=False (requires INTX)")
        return {"error": "live_shorts_disabled"}, 400

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
    result, status = cb_post("/api/v3/brokerage/orders", body)
    if status in (401, 403) or (status == 500 and "error" in result):
        print(f"[APEX] Order auth failed ({status}) — paper fallback")
        return {"success": True, "paper": True, "order_id": f"PAPER-{uuid.uuid4().hex[:8]}"}, 200
    return result, status

def tg(msg, force=False):
    """Send to Telegram — respects SILENT_MODE."""
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
                      json={"chat_id": OWNER_CHAT_ID, "text": msg}, timeout=8)
    except:
        pass

# ── Triple EMA + RSI Strategy (83% WR documented) ────────────────────────────
# Source: https://daviddtech.medium.com/83-win-rate-5-minute-ultimate-scalping-trading-strategy-89c4e89fb364
# Rules: EMA 9 > 55 > 200 alignment + RSI midline (>51 long, <49 short) on 5m candles
# Cached per asset, refreshed every 60s to avoid hammering Coinbase API

_ema_cache = {}  # product -> {"emas": {9:v, 55:v, 200:v}, "rsi": v, "ts": datetime}
EMA_CACHE_TTL = 60  # seconds

def _fetch_5m_candles(product, limit=210):
    """Fetch 5-minute candles from Coinbase public API (no auth needed)."""
    try:
        # Coinbase uses product_id like "BTC-USD" and granularity in seconds
        url = f"https://api.exchange.coinbase.com/products/{product}/candles"
        r = requests.get(url, params={"granularity": 300}, timeout=10)
        if r.status_code == 200:
            data = r.json()[:limit]  # [[time, low, high, open, close, volume], ...]
            closes = [float(c[4]) for c in reversed(data)]  # oldest first
            return closes
    except Exception as e:
        print(f"[APEX] Candle fetch error for {product}: {e}")
    return []

def _calc_ema(prices, period):
    """Calculate EMA for a price series."""
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # SMA seed
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema

def _calc_rsi(prices, period=14):
    """Calculate RSI from price series."""
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_ema_rsi_signal(product):
    """Check triple EMA alignment + RSI midline for a product.
    Returns: 'BUY', 'SELL', or None."""
    now = datetime.now()
    cached = _ema_cache.get(product)
    if cached and (now - cached["ts"]).total_seconds() < EMA_CACHE_TTL:
        emas = cached["emas"]
        rsi = cached["rsi"]
    else:
        closes = _fetch_5m_candles(product)
        if len(closes) < 200:
            return None
        emas = {9: _calc_ema(closes, 9), 55: _calc_ema(closes, 55), 200: _calc_ema(closes, 200)}
        rsi = _calc_rsi(closes)
        if any(v is None for v in emas.values()) or rsi is None:
            return None
        _ema_cache[product] = {"emas": emas, "rsi": rsi, "ts": now}

    # Triple EMA alignment + RSI midline filter
    if emas[9] > emas[55] > emas[200] and rsi > 51:
        return "BUY"
    if emas[9] < emas[55] < emas[200] and rsi < 49:
        return "SELL"
    return None


def poll_prices(price_history):
    """Poll all assets in current WATCHLIST, append to rolling windows."""
    current = {}
    for asset in WATCHLIST:
        p = get_price(asset["product"])
        if p:
            if asset["product"] not in price_history:
                price_history[asset["product"]] = deque(maxlen=WINDOW_TICKS)
            price_history[asset["product"]].append(p)
            current[asset["product"]] = p
    return current

def refresh_watchlist(price_history):
    """
    Replace WATCHLIST with today's top movers from CoinGecko.
    Initializes price_history entries for any new assets.
    """
    global WATCHLIST
    new_list = scan_top_movers()
    if not new_list:
        print("[APEX] Watchlist refresh failed — keeping current list")
        return
    WATCHLIST = new_list
    for asset in WATCHLIST:
        if asset["product"] not in price_history:
            price_history[asset["product"]] = deque(maxlen=WINDOW_TICKS)
    syms = ", ".join(a["symbol"] for a in WATCHLIST)
    tg(f"APEX watchlist updated — hunting: {syms}")

def best_signal(price_history, current_prices, min_momentum_override=None):
    """
    Scan all assets for entry signals — bidirectional long AND short.

    Signal 1 — Momentum: asset moved > min_momentum% in the 30-second window.
      BUY on positive momentum, SELL (short) on negative.

    Signal 2 — Fair Value Gap (FVG): 3-candle imbalance detected AND current
      price is inside the gap zone (retest entry for continuation trade).
      BUY on bullish gap retest, SELL on bearish gap retest.

    Returns the highest-scored signal across all assets, or None.
    Live short execution requires LIVE_SHORTS_ENABLED=true (needs Coinbase INTX).
    In PAPER_MODE both directions are always available.
    """
    min_mom    = min_momentum_override if min_momentum_override is not None else MIN_MOMENTUM
    best_sig   = None
    best_score = 0.0

    for asset in WATCHLIST:
        product = asset["product"]
        history = price_history.get(product)
        if not history or len(history) < WINDOW_TICKS:
            continue

        latest = current_prices.get(product)
        oldest = history[0]
        if not latest or not oldest:
            continue

        move = (latest - oldest) / oldest  # signed — positive=up, negative=down

        # ── Signal 1: Momentum ──────────────────────────────────────────────
        if abs(move) >= min_mom:
            direction = "BUY" if move > 0 else "SELL"
            # Skip live shorts unless INTX is enabled
            if direction == "SELL" and not PAPER_MODE and not LIVE_SHORTS_ENABLED:
                pass
            else:
                score = abs(move)
                if score > best_score:
                    best_score = score
                    best_sig = {
                        "symbol": asset["symbol"], "product": product,
                        "price": latest, "momentum": move,
                        "direction": direction, "signal_type": "momentum",
                    }

        # ── Signal 2: FVG retest ────────────────────────────────────────────
        fvg = detect_fvg(history)
        if fvg:
            fvg_type, fvg_low, fvg_high = fvg
            in_gap = fvg_low <= latest <= fvg_high
            if in_gap:
                direction = "BUY" if fvg_type == "bullish" else "SELL"
                if direction == "SELL" and not PAPER_MODE and not LIVE_SHORTS_ENABLED:
                    pass
                else:
                    gap_size = (fvg_high - fvg_low) / latest
                    score = gap_size * 0.8  # slightly lower weight than pure momentum
                    if score > best_score:
                        best_score = score
                        best_sig = {
                            "symbol": asset["symbol"], "product": product,
                            "price": latest, "momentum": move,
                            "direction": direction, "signal_type": "fvg",
                            "fvg_zone": f"${fvg_low:.4f}–${fvg_high:.4f}",
                        }

        # ── Signal 3: Triple EMA alignment + RSI midline (83% WR documented) ──
        # Source: https://daviddtech.medium.com/83-win-rate-5-minute-ultimate-scalping-trading-strategy-89c4e89fb364
        # Strongest signal — when 5m candle EMAs 9>55>200 align with RSI midline
        ema_direction = get_ema_rsi_signal(product)
        if ema_direction:
            if ema_direction == "SELL" and not PAPER_MODE and not LIVE_SHORTS_ENABLED:
                pass
            else:
                # EMA alignment is high-conviction — score it above momentum
                score = abs(move) + 0.005  # boost above raw momentum
                if score > best_score:
                    best_score = score
                    best_sig = {
                        "symbol": asset["symbol"], "product": product,
                        "price": latest, "momentum": move,
                        "direction": ema_direction, "signal_type": "ema_triple",
                    }

    return best_sig

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
        if state["active"]:
            t = state["active"].get("time")
            if isinstance(t, datetime):
                # Convert datetime → ISO string for JSON serialization
                state["active"] = {**state["active"], "time": t.isoformat()}
            elif not isinstance(t, str):
                # Defensive: unknown type — replace with current time string
                state["active"] = {**state["active"], "time": datetime.now().isoformat()}
            # If already a string, leave as-is — valid ISO format
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
        hive = _hive_read()
        apex = hive.setdefault("bot_performance", {}).get("APEX", {})
        # Preserve confidence_score across updates
        conf = apex.get("confidence_score", 0.50)
        hive["bot_performance"]["APEX"] = {
            "daily_pnl": round(pnl, 2), "trades": trades, "wins": wins,
            "win_rate":  round(wins / trades, 3) if trades else 0,
            "mode":      "live_scalping",
            "confidence_score": conf,
        }
        _hive_write(hive)
    except:
        pass


def update_confidence(won: bool):
    """Write confidence score back to hive_mind after each trade close."""
    try:
        hive = _hive_read()
        apex = hive.setdefault("bot_performance", {}).setdefault("APEX", {})
        conf = apex.get("confidence_score", 0.50)
        if won:
            conf = min(conf + 0.02, 1.0)
        else:
            conf = max(conf - 0.03, 0.1)
        apex["confidence_score"] = round(conf, 3)
        _hive_write(hive)
        print(f"[APEX] Confidence: {conf:.3f} ({'↑' if won else '↓'})")
    except Exception as e:
        print(f"[APEX] Confidence update failed: {e}")

def log_trade_lesson(trade_data):
    """
    Write a trade outcome lesson to hive_mind.json in real time.
    All bots can read apex_trade_lessons to learn from APEX's live results.
    """
    try:
        hive = _hive_read()
        lessons = hive.get("apex_trade_lessons", [])
        lessons.append({
            "ts":          datetime.now().isoformat(),
            "symbol":      trade_data.get("symbol"),
            "product":     trade_data.get("product"),
            "direction":   trade_data.get("direction"),
            "signal_type": trade_data.get("signal_type", "momentum"),
            "entry":       trade_data.get("entry"),
            "exit":        trade_data.get("exit"),
            "pnl_pct":     round(trade_data.get("pnl_pct", 0), 5),
            "pnl_usd":     round(trade_data.get("pnl_usd", 0), 3),
            "hold_secs":   trade_data.get("hold_secs", 0),
            "reason":      trade_data.get("reason"),
            "outcome":     "win" if trade_data.get("pnl_usd", 0) > 0 else "loss",
            "momentum":    round(trade_data.get("momentum", 0), 6),
            "fvg_zone":    trade_data.get("fvg_zone"),
        })
        # Keep last 500 lessons to prevent unbounded growth
        if len(lessons) > 500:
            lessons = lessons[-500:]
        hive["apex_trade_lessons"] = lessons
        hive["apex_lessons_updated"] = datetime.now().isoformat()
        _hive_write(hive)
    except Exception as e:
        print(f"[APEX] log_trade_lesson error: {e}")

def run():
    print("=" * 55)
    print("APEX LIVE SCALPER — Opportunity Hunter Edition")
    print(f"Signals: Momentum + FVG | Bidirectional: {'YES' if PAPER_MODE or LIVE_SHORTS_ENABLED else 'LONG ONLY (live)'}")
    print(f"Poll: {POLL_INTERVAL}s | Window: {WINDOW_TICKS * POLL_INTERVAL}s | Min move: {MIN_MOMENTUM*100:.2f}%")
    print(f"Stop: {STOP*100:.1f}% | Target: {TARGET*100:.1f}% | Trail: {TRAIL*100:.1f}%")
    print("=" * 55)

    daily_pnl   = 0.0
    trades      = wins = 0
    active      = trail_best = None
    last_close  = datetime.now()
    last_report = datetime.now()
    last_scan   = datetime.now() - __import__('datetime').timedelta(seconds=SCAN_INTERVAL)  # fire immediately
    last_trade_time = datetime.now()  # tracks last entry — auto-lower threshold if idle 10+ min
    current_min_momentum = MIN_MOMENTUM  # dynamic — lowers when idle, resets after trade

    # Initialize price history with defaults — refreshed after scan
    price_history = {a["product"]: deque(maxlen=WINDOW_TICKS) for a in WATCHLIST}

    # Write startup state immediately so autonomous loop won't spawn duplicates
    save_state(None, None, 0.0, 0, 0)

    # ── Startup asset scan ────────────────────────────────────────────────────
    print("[APEX] Scanning top movers for today's opportunity list...")
    refresh_watchlist(price_history)
    last_scan = datetime.now()

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
        mode_str = "PAPER" if PAPER_MODE else "LIVE"
        syms = " ".join(a["symbol"] for a in WATCHLIST)
        tg(f"APEX ONLINE [{mode_str}] — Opportunity Hunter\n"
           f"Signals: Momentum + FVG | Both directions\n"
           f"Hunting: {syms}\n"
           f"Min move: {MIN_MOMENTUM*100:.2f}% | Stop: {STOP*100:.1f}% | Target: {TARGET*100:.1f}%")

    while True:
        try:
            # ── Kill switch ───────────────────────────────────────────────────
            if daily_pnl < -(STARTING * MAX_LOSS):
                tg(f"APEX KILL SWITCH — loss limit hit\n"
                   f"Final: ${daily_pnl:+.2f} | {trades} trades | {wins} wins")
                update_hive(daily_pnl, trades, wins)
                break

            # ── Read NEXUS parameter overrides from hive_mind.json ────────────
            try:
                if HIVE.exists():
                    _hive = json.loads(HIVE.read_text())
                    _nexus_params = _hive.get("nexus_apex_overrides", {})
                    if _nexus_params:
                        if "min_momentum" in _nexus_params:
                            current_min_momentum = float(_nexus_params["min_momentum"])
                        if "cooldown" in _nexus_params:
                            global COOLDOWN
                            COOLDOWN = int(_nexus_params["cooldown"])
            except Exception:
                pass

            # ── Refresh asset universe every 4 hours (no-op if in trade) ────────
            if not active and (datetime.now() - last_scan).total_seconds() >= SCAN_INTERVAL:
                refresh_watchlist(price_history)
                last_scan = datetime.now()

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
                symbol    = active.get("symbol", "")
                pnl_pct   = (price - entry) / entry if direction == "BUY" \
                            else (entry - price) / entry

                # Adaptive stops: tight for BTC/ETH/SOL, wide for volatile low-caps
                if symbol in TIGHT_STOP_SYMBOLS:
                    a_stop, a_target, a_trail = TIGHT_STOP, TIGHT_TARGET, TIGHT_TRAIL
                else:
                    a_stop, a_target, a_trail = STOP, TARGET, TRAIL

                # Update trailing stop
                trail_active = pnl_pct >= MIN_PROFIT_TRAIL
                if direction == "BUY":
                    if price > trail_best:
                        trail_best = price
                    trail_stop = trail_best * (1 - a_trail)
                    should_exit = pnl_pct <= -a_stop or pnl_pct >= a_target or \
                                  (trail_active and price <= trail_stop)
                else:
                    if price < trail_best:
                        trail_best = price
                    trail_stop = trail_best * (1 + a_trail)
                    should_exit = pnl_pct <= -a_stop or pnl_pct >= a_target or \
                                  (trail_active and price >= trail_stop)

                print(f"[APEX] {direction} {active['symbol']} {pnl_pct*100:+.3f}% "
                      f"| entry ${entry:,.4f} now ${price:,.4f} trail ${trail_stop:,.4f}")

                # ── NEXUS force-close flag — NEXUS determined trade must exit ────
                force_close_flag = BASE / "shared" / "apex_force_close.flag"
                if force_close_flag.exists():
                    try:
                        force_close_flag.unlink()
                        should_exit = True
                        reason_override = "nexus_close"
                        print(f"[APEX] NEXUS force-close flag — exiting {direction} {active['symbol']}")
                    except Exception:
                        pass

                if should_exit:
                    exit_side  = "SELL" if direction == "BUY" else "BUY"
                    result, _  = place_order(product, exit_side, active["size"])

                    pnl_usd = active["size"] * pnl_pct
                    daily_pnl += pnl_usd
                    if pnl_pct > 0:
                        wins += 1
                    wr     = wins / trades if trades else 0
                    reason = locals().get("reason_override") or \
                             ("target" if pnl_pct >= TARGET else
                              "trail"  if pnl_pct > 0 else "stop")
                    tag    = "WIN" if pnl_usd > 0 else "LOSS"

                    # Hold time using total_seconds() — safe regardless of active["time"] type
                    hold_secs = 0
                    try:
                        t = active.get("time")
                        if isinstance(t, datetime):
                            hold_secs = (datetime.now() - t).total_seconds()
                        elif isinstance(t, str):
                            hold_secs = (datetime.now() - datetime.fromisoformat(t)).total_seconds()
                    except Exception:
                        pass
                    hold_str = f"{int(hold_secs//60)}m{int(hold_secs%60):02d}s" if hold_secs else "?s"

                    tg(f"{tag} #{trades} | {direction} {active['symbol']} [{hold_str}]\n"
                       f"${entry:,.4f} -> ${price:,.4f} ({pnl_pct*100:+.3f}%) [{reason}]\n"
                       f"P&L: ${pnl_usd:+.3f} | Day: ${daily_pnl:+.2f} | WR: {wr*100:.0f}% ({wins}/{trades})")

                    # Log lesson to hive_mind so all bots can learn in real time
                    log_trade_lesson({
                        "symbol":      active["symbol"], "product": product,
                        "direction":   direction, "signal_type": active.get("signal_type", "momentum"),
                        "entry":       entry, "exit": price,
                        "pnl_pct":     pnl_pct, "pnl_usd": pnl_usd,
                        "hold_secs":   hold_secs, "reason": reason,
                        "momentum":    active.get("momentum", 0),
                        "fvg_zone":    active.get("fvg_zone"),
                    })

                    update_confidence(won=(pnl_pct > 0))
                    update_hive(daily_pnl, trades, wins)
                    active     = trail_best = None
                    last_close = datetime.now()
                    save_state(None, None, daily_pnl, trades, wins)

                    # Apply any queued parameter changes now that trade is closed
                    try:
                        from nexus_agent import apply_queued_params
                        applied = apply_queued_params()
                        if applied:
                            print(f"[APEX] Applied queued params after trade close: {applied}")
                    except Exception as e:
                        print(f"[APEX] Queue drain error: {e}")

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

                # ── Auto-lower threshold if idle 10+ min — real scalpers are always active ──
                idle_secs = (datetime.now() - last_trade_time).total_seconds()
                if idle_secs > 600 and current_min_momentum > MIN_MOMENTUM * 0.1:
                    old_thresh = current_min_momentum
                    current_min_momentum = max(current_min_momentum * 0.5, MIN_MOMENTUM * 0.1)
                    print(f"[APEX] IDLE {int(idle_secs//60)}min — lowering threshold "
                          f"{old_thresh*100:.4f}% → {current_min_momentum*100:.4f}%")
                    last_trade_time = datetime.now()  # reset timer after lowering

                sig = best_signal(price_history, current, min_momentum_override=current_min_momentum)
                if sig:
                    # Confidence score from hive_mind affects position sizing
                    _conf = 0.50  # default
                    try:
                        if HIVE.exists():
                            _hd = json.loads(HIVE.read_text())
                            _conf = _hd.get("bot_performance", {}).get("APEX", {}).get("confidence_score", 0.50)
                    except Exception:
                        pass
                    size      = STARTING * RISK * max(_conf, 0.2)  # floor at 20% of base
                    price     = sig["price"]
                    direction = sig["direction"]
                    product   = sig["product"]
                    sym       = sig["symbol"]
                    # Adaptive stops per asset class
                    s_stop   = TIGHT_STOP if sym in TIGHT_STOP_SYMBOLS else STOP
                    s_target = TIGHT_TARGET if sym in TIGHT_STOP_SYMBOLS else TARGET
                    stop_p    = price * (1 - s_stop) if direction == "BUY" else price * (1 + s_stop)
                    target_p  = price * (1 + s_target) if direction == "BUY" else price * (1 - s_target)

                    sig_label = sig.get("signal_type", "momentum").upper()
                    fvg_info  = f" FVG:{sig['fvg_zone']}" if sig.get("fvg_zone") else ""
                    print(f"[APEX] SIGNAL [{sig_label}]: {direction} {sig['symbol']} "
                          f"momentum={sig['momentum']*100:+.3f}% @ ${price:,.4f}{fvg_info}")

                    result, status = place_order(product, direction, size)

                    if status == 200 and result.get("success"):
                        trades    += 1
                        last_trade_time = datetime.now()  # reset idle timer
                        current_min_momentum = MIN_MOMENTUM  # reset threshold after trade
                        active     = {"symbol": sig["symbol"], "product": product,
                                      "direction": direction, "entry": price,
                                      "size": size, "time": datetime.now(),
                                      "signal_type": sig.get("signal_type", "momentum"),
                                      "momentum": sig.get("momentum", 0),
                                      "fvg_zone": sig.get("fvg_zone")}
                        trail_best = price
                        save_state(active, trail_best, daily_pnl, trades, wins)

                        mode_tag = " [PAPER]" if result.get("paper") else ""
                        tg(f"ENTRY #{trades}{mode_tag} | {'LONG' if direction=='BUY' else 'SHORT'} {sig['symbol']}\n"
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

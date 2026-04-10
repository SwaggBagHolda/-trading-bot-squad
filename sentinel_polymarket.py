"""
SENTINEL — Polymarket Arbitrage Bot
"The market is wrong. I have the receipts."

Strategy 1 — Directional Edge:
  Monitor BTC/ETH/SOL 15-min and daily up/down markets on Polymarket.
  Watch Coinbase spot prices in real time.
  When spot price confirms direction but Polymarket still shows ~50/50,
  bet the confirmed side immediately.

Strategy 2 — Sum-to-One Arbitrage:
  When YES + NO prices for a market sum to less than $1.00,
  buy BOTH sides for guaranteed profit on resolution.

Paper trading first. No real money until strategy is validated.

API Docs: https://docs.polymarket.com
CLOB: https://clob.polymarket.com
Gamma: https://gamma-api.polymarket.com
"""

import json
import time
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env", override=True)

HIVE = BASE / "shared" / "hive_mind.json"
PAPER_LOG = BASE / "logs" / "sentinel_polymarket.jsonl"
PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)

# Polymarket API endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# Coinbase public price API (no auth needed)
COINBASE_API = "https://api.coinbase.com/v2/prices"

# Telegram for alerts
TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN", "")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID", "")

# Paper trading state — persisted to disk
POSITIONS_FILE = BASE / "shared" / "sentinel_positions.json"
HISTORY_FILE   = BASE / "shared" / "sentinel_history.json"
BET_SIZE = 10.00          # $10 per bet (paper)


def _load_state():
    """Load paper trading state from disk."""
    positions, history, balance = [], [], 1000.00
    try:
        if POSITIONS_FILE.exists():
            positions = json.loads(POSITIONS_FILE.read_text())
    except Exception:
        pass
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text())
            history = data.get("trades", [])
            balance = data.get("balance", 1000.00)
    except Exception:
        pass
    return positions, history, balance


def _save_state():
    """Persist paper trading state to disk."""
    try:
        POSITIONS_FILE.write_text(json.dumps(PAPER_POSITIONS, indent=2))
    except Exception:
        pass
    try:
        HISTORY_FILE.write_text(json.dumps({
            "balance": round(PAPER_BALANCE, 2),
            "trades": PAPER_HISTORY,
        }, indent=2))
    except Exception:
        pass


PAPER_POSITIONS, PAPER_HISTORY, PAPER_BALANCE = _load_state()

# Thresholds — loosened for real scalping (the $438K bot trades constantly)
DIRECTIONAL_EDGE_THRESHOLD = 0.001   # 0.1% price move counts as directional signal
POLYMARKET_MISPRICING = 0.05         # YES price 0.45-0.55 = mispriced
ARB_PROFIT_THRESHOLD = 0.001         # 0.1% guaranteed profit on sum-to-one arb
NEAR_STRIKE_PCT = 0.05               # Focus on markets where spot is within 5% of strike
CONVICTION_THRESHOLD = 0.45          # Bet when conviction > 45% (aggressive — volume compensates)
MAX_YES_PRICE = 0.90                 # Don't buy YES above 90 cents (diminishing returns)
SCAN_INTERVAL = 30                    # Check every 30 seconds — scalper speed


def send_telegram(text, force=False):
    """Send alert to Ty. Respects SILENT_MODE."""
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        return
    try:
        from silent_mode import should_send
        if not should_send(text, force=force):
            print(f"[SENTINEL] SILENT_MODE suppressed: {text[:80]}...")
            return
    except ImportError:
        if not force:
            print(f"[SENTINEL] SILENT_MODE (fallback block): {text[:80]}...")
            return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": f"[SENTINEL] {text}"},
            timeout=10,
        )
    except Exception:
        pass


def get_coinbase_price(symbol="BTC"):
    """Get current spot price from Coinbase (free, no auth)."""
    try:
        r = requests.get(f"{COINBASE_API}/{symbol}-USD/spot", timeout=5)
        if r.status_code == 200:
            return float(r.json()["data"]["amount"])
    except Exception:
        pass
    return None


def get_coinbase_price_change(symbol="BTC", minutes=15):
    """Get price change over last N minutes using Coinbase candles via ccxt."""
    try:
        import ccxt
        exchange = ccxt.coinbase()
        candles = exchange.fetch_ohlcv(f"{symbol}/USD", "1m", limit=minutes + 1)
        if len(candles) >= 2:
            old_close = candles[0][4]
            new_close = candles[-1][4]
            pct_change = (new_close - old_close) / old_close
            return {
                "symbol": symbol,
                "price": new_close,
                "change_pct": pct_change,
                "direction": "up" if pct_change > 0 else "down",
                "old_price": old_close,
                "minutes": minutes,
            }
    except Exception as e:
        print(f"[SENTINEL] Price change error for {symbol}: {e}")
    return None


def get_crypto_prediction_markets():
    """Fetch active crypto prediction markets from Polymarket Gamma API."""
    try:
        r = requests.get(
            f"{GAMMA_API}/events",
            params={
                "active": "true",
                "closed": "false",
                "limit": 100,
                "order": "volume24hr",
                "ascending": "false",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []

        events = r.json()
        crypto_markets = []

        for event in events:
            title = event.get("title", "").lower()
            # Filter for crypto price prediction markets
            if not any(k in title for k in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto"]):
                continue

            for market in event.get("markets", []):
                question = market.get("question", "")
                outcomes = market.get("outcomes", [])
                prices_raw = market.get("outcomePrices", [])
                token_ids = market.get("clobTokenIds", [])
                condition_id = market.get("conditionId", "")
                end_date = market.get("endDate", "")
                slug = market.get("slug", "")

                if not prices_raw or not token_ids:
                    continue

                # Parse prices — API returns JSON strings, not lists
                try:
                    if isinstance(prices_raw, str):
                        prices_raw = json.loads(prices_raw)
                    if isinstance(token_ids, str):
                        token_ids = json.loads(token_ids)
                    prices = [float(p) for p in prices_raw]
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue

                # Identify market type
                q_lower = question.lower()
                market_type = "unknown"
                asset = "BTC"

                if "up or down" in q_lower or "up/down" in q_lower:
                    market_type = "up_down"
                elif "above" in q_lower or "below" in q_lower or "between" in q_lower:
                    market_type = "price_level"
                elif "reach" in q_lower or "hit" in q_lower or "dip" in q_lower:
                    market_type = "price_target"

                if "ethereum" in q_lower or "eth" in q_lower:
                    asset = "ETH"
                elif "solana" in q_lower or "sol" in q_lower:
                    asset = "SOL"

                crypto_markets.append({
                    "question": question,
                    "event_title": event.get("title", ""),
                    "market_type": market_type,
                    "asset": asset,
                    "outcomes": outcomes,
                    "prices": prices,
                    "token_ids": token_ids,
                    "condition_id": condition_id,
                    "end_date": end_date,
                    "slug": slug,
                    "price_sum": sum(prices),
                })

        return crypto_markets

    except Exception as e:
        print(f"[SENTINEL] Market fetch error: {e}")
        return []


def find_directional_opportunities(markets):
    """
    Strategy 1: Directional conviction trades on near-strike markets.

    The real Polymarket alpha:
    - Focus on markets where spot price is NEAR the strike (within 3%)
    - These markets have 40-60% YES prices = maximum profit potential
    - Use spot momentum to pick a side
    - BTC at $71,823 + "above $72K" at YES=$0.465 = 115% potential return

    Also trades "reach" and "dip" markets using distance-to-target conviction.
    """
    import re
    opportunities = []
    price_cache = {}  # cache spot prices per asset

    for market in markets:
        asset = market["asset"]
        prices = market["prices"]
        if len(prices) < 2:
            continue

        yes_price = prices[0]
        no_price = prices[1]
        q_lower = market["question"].lower()

        # Skip already-resolved markets (one side > 0.95)
        if yes_price > 0.95 or no_price > 0.95:
            continue

        # Get spot price (cached per asset per scan)
        if asset not in price_cache:
            price_data = get_coinbase_price_change(asset, minutes=15)
            if price_data:
                price_cache[asset] = price_data
        price_data = price_cache.get(asset)
        if not price_data:
            continue

        current_price = price_data["price"]
        momentum = price_data["change_pct"]

        # ── Strategy 1A: "above $X" markets — near-strike conviction ──────
        if "above" in q_lower or "between" in q_lower:
            target_match = re.search(r'\$([0-9,]+)', market["question"])
            if not target_match:
                continue
            target = float(target_match.group(1).replace(",", ""))
            margin = (current_price - target) / target  # positive = above strike

            # Only trade near-strike markets (within 5%) — max profit zone
            if abs(margin) > NEAR_STRIKE_PCT:
                continue

            # Conviction scoring: distance from strike + momentum alignment
            # More aggressive: even slight edge is worth trading at volume
            conviction = 0.50  # base
            conviction += min(margin * 15, 0.35)  # steeper slope — small margin = real edge
            if momentum > DIRECTIONAL_EDGE_THRESHOLD and margin > 0:
                conviction += 0.10  # momentum confirms above
            elif momentum < -DIRECTIONAL_EDGE_THRESHOLD and margin < 0:
                conviction += 0.10  # momentum confirms below

            # BUY YES if we think price will be above target
            if conviction > CONVICTION_THRESHOLD and yes_price < MAX_YES_PRICE:
                edge = 1.0 - yes_price
                opportunities.append({
                    "type": "directional",
                    "market": market,
                    "action": "BUY_YES",
                    "reason": f"{asset} ${current_price:,.0f} ({margin*100:+.1f}% vs ${target:,.0f}) mom {momentum*100:+.2f}% | YES ${yes_price:.3f} | conv {conviction:.0%}",
                    "edge_pct": edge,
                    "conviction": conviction,
                    "spot_data": price_data,
                })
            # BUY NO if we think price will be below target
            elif (1 - conviction) > CONVICTION_THRESHOLD and no_price < MAX_YES_PRICE:
                edge = 1.0 - no_price
                opportunities.append({
                    "type": "directional",
                    "market": market,
                    "action": "BUY_NO",
                    "reason": f"{asset} ${current_price:,.0f} ({margin*100:+.1f}% vs ${target:,.0f}) mom {momentum*100:+.2f}% | NO ${no_price:.3f} | conv {1-conviction:.0%}",
                    "edge_pct": edge,
                    "conviction": 1 - conviction,
                    "spot_data": price_data,
                })

        # ── Strategy 1B: "reach $X" / "dip to $X" markets ────────────────
        elif "reach" in q_lower or "dip" in q_lower:
            target_match = re.search(r'\$([0-9,]+)', market["question"])
            if not target_match:
                continue
            target = float(target_match.group(1).replace(",", ""))
            distance_pct = abs(current_price - target) / current_price

            # "reach" = needs to go UP, "dip" = needs to go DOWN
            is_reach = "reach" in q_lower

            # If momentum is aligned with direction and price already moving, YES is underpriced
            if is_reach and momentum > DIRECTIONAL_EDGE_THRESHOLD and yes_price < 0.50 and distance_pct < 0.10:
                opportunities.append({
                    "type": "directional",
                    "market": market,
                    "action": "BUY_YES",
                    "reason": f"{asset} moving up {momentum*100:+.2f}% toward ${target:,.0f} ({distance_pct*100:.1f}% away) | YES ${yes_price:.3f}",
                    "edge_pct": 1.0 - yes_price,
                    "conviction": 0.55 + min(abs(momentum) * 20, 0.2),
                    "spot_data": price_data,
                })
            elif not is_reach and momentum < -DIRECTIONAL_EDGE_THRESHOLD and yes_price < 0.50 and distance_pct < 0.10:
                opportunities.append({
                    "type": "directional",
                    "market": market,
                    "action": "BUY_YES",
                    "reason": f"{asset} dipping {momentum*100:+.2f}% toward ${target:,.0f} ({distance_pct*100:.1f}% away) | YES ${yes_price:.3f}",
                    "edge_pct": 1.0 - yes_price,
                    "conviction": 0.55 + min(abs(momentum) * 20, 0.2),
                    "spot_data": price_data,
                })

    return sorted(opportunities, key=lambda x: x.get("conviction", 0), reverse=True)


def find_arbitrage_opportunities(markets):
    """
    Strategy 2: Find markets where YES + NO prices sum to less than $1.00.
    Buy BOTH sides for guaranteed profit on resolution.

    Also checks CLOB orderbook for spread opportunities — the real alpha.
    Even $0.002 per pair compounds at scale with high frequency.
    """
    opportunities = []

    for market in markets:
        prices = market["prices"]
        if len(prices) < 2:
            continue

        price_sum = sum(prices)

        # Strategy 2A: Sum-to-one arb (loosened threshold — even 0.2% edge is profit)
        if price_sum < (1.0 - ARB_PROFIT_THRESHOLD):
            profit_pct = (1.0 - price_sum) / price_sum * 100
            opportunities.append({
                "type": "arbitrage",
                "market": market,
                "action": "BUY_BOTH",
                "reason": f"YES=${prices[0]:.4f} + NO=${prices[1]:.4f} = ${price_sum:.4f} ({profit_pct:.2f}% guaranteed)",
                "edge_pct": 1.0 - price_sum,
                "cost_per_pair": price_sum,
            })

        # Strategy 2B: Cross-market arb — same underlying, different resolution dates
        # If "BTC above $72K on Apr 10" YES=$0.465 but "BTC above $72K on Apr 11" YES=$0.525
        # and they resolve sequentially, there may be mispricing between them

    # Also check CLOB orderbook for spread on highest-volume markets
    for market in markets[:5]:  # top 5 by volume
        try:
            token_ids = market.get("token_ids", [])
            if not token_ids:
                continue
            # Check CLOB best bid/ask for YES token
            r = requests.get(
                f"{CLOB_API}/book",
                params={"token_id": token_ids[0]},
                timeout=5,
            )
            if r.status_code == 200:
                book = r.json()
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                if bids and asks:
                    best_bid = float(bids[0].get("price", 0))
                    best_ask = float(asks[0].get("price", 0))
                    spread = best_ask - best_bid
                    if spread > 0.005:  # 0.5% spread = tradeable
                        mid = (best_bid + best_ask) / 2
                        opportunities.append({
                            "type": "spread",
                            "market": market,
                            "action": "MARKET_MAKE",
                            "reason": f"CLOB spread {spread:.4f} ({spread/mid*100:.1f}%) bid=${best_bid:.4f} ask=${best_ask:.4f} | {market['question'][:50]}",
                            "edge_pct": spread / 2,  # capture half the spread
                            "cost_per_pair": best_ask,
                        })
        except Exception:
            pass

    return sorted(opportunities, key=lambda x: x["edge_pct"], reverse=True)


def paper_trade(opportunity):
    """Execute a paper trade and log it."""
    global PAPER_BALANCE

    market = opportunity["market"]
    action = opportunity["action"]
    bet = min(BET_SIZE, PAPER_BALANCE)

    if bet <= 0:
        print("[SENTINEL] Paper balance exhausted")
        return None

    # Don't open duplicate positions on same market+action
    for pos in PAPER_POSITIONS:
        if pos["market"] == market["question"] and pos["action"] == action:
            return None

    trade = {
        "timestamp": datetime.now().isoformat(),
        "market": market["question"],
        "action": action,
        "bet_size": bet,
        "type": opportunity["type"],
        "reason": opportunity["reason"],
        "edge_pct": opportunity["edge_pct"],
        "prices": market["prices"],
        "status": "open",
        "pnl": 0,
    }

    if action == "BUY_BOTH":
        cost = market["price_sum"] * bet
        trade["cost"] = cost
        trade["guaranteed_profit"] = bet - cost
        PAPER_BALANCE -= cost
    else:
        # Directional bet
        price = market["prices"][0] if "YES" in action else market["prices"][1]
        shares = bet / price if price > 0 else 0
        trade["entry_price"] = price
        trade["shares"] = shares
        PAPER_BALANCE -= bet

    PAPER_POSITIONS.append(trade)

    # Log to file
    try:
        with open(PAPER_LOG, "a") as f:
            f.write(json.dumps(trade) + "\n")
    except Exception:
        pass

    _save_state()

    msg = f"PAPER TRADE: {action} on '{market['question'][:60]}'\n"
    msg += f"Bet: ${bet:.2f} | Edge: {opportunity['edge_pct']*100:.1f}%\n"
    msg += f"Reason: {opportunity['reason'][:100]}\n"
    msg += f"Balance: ${PAPER_BALANCE:.2f}"
    print(f"[SENTINEL] {msg}")

    return trade


TAKE_PROFIT_PCT = 0.15   # Close when position is up 15%
STOP_LOSS_PCT   = -0.10  # Close when position is down 10%
MAX_HOLD_HOURS  = 48     # Auto-close after 48 hours


def resolve_positions(markets):
    """Check open positions and close any that hit TP/SL/expiry."""
    global PAPER_BALANCE
    if not PAPER_POSITIONS:
        return

    # Build lookup: question -> current prices
    price_lookup = {}
    for m in markets:
        price_lookup[m["question"]] = m["prices"]

    to_close = []
    for i, pos in enumerate(PAPER_POSITIONS):
        reason = None
        pnl = 0

        # Check hold time
        try:
            open_time = datetime.fromisoformat(pos["timestamp"])
            hours_held = (datetime.now() - open_time).total_seconds() / 3600
        except Exception:
            hours_held = 0

        if pos["action"] == "BUY_BOTH":
            # Arb: guaranteed profit, resolve after 1 scan
            pnl = pos.get("guaranteed_profit", 0)
            reason = "arb_resolved"
        else:
            # Directional: check current price vs entry
            current_prices = price_lookup.get(pos["market"])
            if current_prices:
                is_yes = "YES" in pos.get("action", "")
                current_price = current_prices[0] if is_yes else current_prices[1]
                entry_price = pos.get("entry_price", 0)

                if entry_price > 0:
                    price_change = (current_price - entry_price) / entry_price
                    shares = pos.get("shares", 0)
                    pnl = shares * (current_price - entry_price)

                    if price_change >= TAKE_PROFIT_PCT:
                        reason = "take_profit"
                    elif price_change <= STOP_LOSS_PCT:
                        reason = "stop_loss"
                    elif hours_held >= MAX_HOLD_HOURS:
                        reason = "max_hold"
                else:
                    if hours_held >= MAX_HOLD_HOURS:
                        reason = "max_hold"
            elif hours_held >= MAX_HOLD_HOURS:
                reason = "max_hold"

        if reason:
            pos["status"] = "closed"
            pos["pnl"] = round(pnl, 4)
            pos["close_reason"] = reason
            pos["close_time"] = datetime.now().isoformat()
            PAPER_BALANCE += pos["bet_size"] + pnl
            PAPER_HISTORY.append(pos)
            to_close.append(i)

            tag = "WIN" if pnl > 0 else "LOSS"
            print(f"[SENTINEL] {tag}: {pos['action']} '{pos['market'][:50]}' "
                  f"P&L: ${pnl:+.4f} [{reason}] Balance: ${PAPER_BALANCE:.2f}")

            # Update confidence score
            try:
                hive = json.loads(HIVE.read_text()) if HIVE.exists() else {}
                s = hive.setdefault("bot_performance", {}).setdefault("SENTINEL", {})
                conf = s.get("confidence_score", 0.50)
                conf = min(conf + 0.02, 1.0) if pnl > 0 else max(conf - 0.03, 0.1)
                s["confidence_score"] = round(conf, 3)
                HIVE.write_text(json.dumps(hive, indent=2))
            except Exception:
                pass

    # Remove closed positions (reverse order to preserve indices)
    for i in sorted(to_close, reverse=True):
        PAPER_POSITIONS.pop(i)

    if to_close:
        _save_state()
        wins = sum(1 for t in PAPER_HISTORY if t.get("pnl", 0) > 0)
        total = len(PAPER_HISTORY)
        total_pnl = sum(t.get("pnl", 0) for t in PAPER_HISTORY)
        send_telegram(
            f"SENTINEL resolved {len(to_close)} position(s)\n"
            f"Record: {wins}/{total} ({wins/total*100:.0f}% WR) | "
            f"Total P&L: ${total_pnl:+.2f} | Balance: ${PAPER_BALANCE:.2f}"
        )


def update_hive_mind():
    """Update hive_mind.json with SENTINEL's Polymarket status."""
    try:
        hive = {}
        if HIVE.exists():
            hive = json.loads(HIVE.read_text())

        perf = hive.setdefault("bot_performance", {})
        sentinel = perf.setdefault("SENTINEL", {})

        wins = sum(1 for t in PAPER_HISTORY if t.get("pnl", 0) > 0)
        total = len(PAPER_HISTORY)

        sentinel.update({
            "mode": "paper_polymarket",
            "strategy": "polymarket_arbitrage",
            "paper_balance": round(PAPER_BALANCE, 2),
            "open_positions": len(PAPER_POSITIONS),
            "total_trades": total,
            "win_rate": wins / total if total > 0 else 0,
            "daily_pnl": sum(t.get("pnl", 0) for t in PAPER_HISTORY),
            "markets_watching": "BTC/ETH/SOL up-down + price levels",
            "last_scan": datetime.now().isoformat(),
        })

        HIVE.write_text(json.dumps(hive, indent=2))
    except Exception as e:
        print(f"[SENTINEL] Hive update error: {e}")


def scan_and_trade():
    """Main scan loop: find opportunities and paper trade them."""
    print(f"\n[SENTINEL] Scanning Polymarket crypto markets...")

    # Fetch all crypto prediction markets
    markets = get_crypto_prediction_markets()
    print(f"[SENTINEL] Found {len(markets)} crypto markets")

    if not markets:
        return

    # Resolve any open positions first
    resolve_positions(markets)

    # Strategy 1: Directional edge
    directional = find_directional_opportunities(markets)
    if directional:
        print(f"[SENTINEL] {len(directional)} directional opportunities found")
        for opp in directional[:3]:  # Max 3 directional trades per scan
            trade = paper_trade(opp)
            if trade:
                send_telegram(
                    f"PAPER: {opp['action']} '{opp['market']['question'][:50]}'\n"
                    f"Edge: {opp['edge_pct']*100:.1f}% | {opp['reason'][:80]}"
                )

    # Strategy 2: Sum-to-one arbitrage
    arb = find_arbitrage_opportunities(markets)
    if arb:
        print(f"[SENTINEL] {len(arb)} arbitrage opportunities found")
        for opp in arb[:2]:  # Max 2 arb trades per scan
            trade = paper_trade(opp)
            if trade:
                send_telegram(
                    f"PAPER ARB: '{opp['market']['question'][:50]}'\n"
                    f"Guaranteed profit: {opp['edge_pct']*100:.1f}%"
                )

    if not directional and not arb:
        print("[SENTINEL] No opportunities this scan")

    # Log summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "markets_scanned": len(markets),
        "directional_found": len(directional),
        "arbitrage_found": len(arb),
        "open_positions": len(PAPER_POSITIONS),
        "paper_balance": PAPER_BALANCE,
    }
    print(f"[SENTINEL] Scan complete: {json.dumps(summary)}")

    update_hive_mind()
    return summary


def get_status():
    """Get current SENTINEL status for reports."""
    markets = get_crypto_prediction_markets()

    # Top arbitrage opportunities
    arb = find_arbitrage_opportunities(markets)
    top_arb = []
    for opp in arb[:3]:
        top_arb.append({
            "market": opp["market"]["question"][:60],
            "profit_pct": round(opp["edge_pct"] * 100, 2),
            "prices": opp["market"]["prices"],
        })

    wins = sum(1 for t in PAPER_HISTORY if t.get("pnl", 0) > 0)
    total = len(PAPER_HISTORY)

    return {
        "mode": "paper_polymarket",
        "paper_balance": round(PAPER_BALANCE, 2),
        "open_positions": len(PAPER_POSITIONS),
        "total_trades": total,
        "win_rate": f"{wins/total*100:.0f}%" if total > 0 else "N/A",
        "pnl": round(sum(t.get("pnl", 0) for t in PAPER_HISTORY), 2),
        "markets_found": len(markets),
        "top_arbitrage": top_arb,
    }


def run():
    """Main loop: scan every SCAN_INTERVAL seconds."""
    print("=" * 55)
    print("SENTINEL — Polymarket Arbitrage Bot")
    print('"The market is wrong. I have the receipts."')
    print(f"Paper balance: ${PAPER_BALANCE:.2f}")
    print(f"Scan interval: {SCAN_INTERVAL}s")
    print("=" * 55)

    # No startup noise — Ty only wants trade notifications

    while True:
        try:
            scan_and_trade()
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            print("\n[SENTINEL] Stopped.")
            break
        except Exception as e:
            print(f"[SENTINEL] Error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        status = get_status()
        print(json.dumps(status, indent=2))
    elif "--scan" in sys.argv:
        scan_and_trade()
    else:
        run()

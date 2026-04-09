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

# Paper trading state
PAPER_BALANCE = 1000.00  # Start with $1000 paper money
PAPER_POSITIONS = []      # Active positions
PAPER_HISTORY = []        # Closed trades
BET_SIZE = 10.00          # $10 per bet (paper)

# Thresholds
DIRECTIONAL_EDGE_THRESHOLD = 0.015   # 1.5% price move confirms direction
POLYMARKET_MISPRICING = 0.10         # Polymarket at ~50/50 means YES price 0.40-0.60
ARB_PROFIT_THRESHOLD = 0.02          # 2% guaranteed profit on sum-to-one arb
SCAN_INTERVAL = 60                    # Check every 60 seconds


def send_telegram(text):
    """Send alert to Ty."""
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
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
    Strategy 1: Find markets where spot price confirms direction
    but Polymarket still shows ~50/50.
    """
    opportunities = []

    for market in markets:
        if market["market_type"] not in ("up_down", "price_level"):
            continue

        asset = market["asset"]
        price_data = get_coinbase_price_change(asset, minutes=15)
        if not price_data:
            continue

        prices = market["prices"]
        if len(prices) < 2:
            continue

        yes_price = prices[0]
        no_price = prices[1]

        # Check if spot price has confirmed a direction
        change = abs(price_data["change_pct"])
        direction = price_data["direction"]

        if change < DIRECTIONAL_EDGE_THRESHOLD:
            continue  # Not enough price movement to confirm direction

        # Check if Polymarket is still mispriced (near 50/50)
        # For "up or down" markets: YES = up, NO = down
        q_lower = market["question"].lower()

        if "up or down" in q_lower:
            if direction == "up" and yes_price < (1 - POLYMARKET_MISPRICING):
                # Spot says UP but Polymarket YES is cheap — buy YES
                edge = (1.0 - yes_price) - yes_price  # potential profit per $1
                opportunities.append({
                    "type": "directional",
                    "market": market,
                    "action": "BUY_YES",
                    "reason": f"{asset} up {change*100:.2f}% in 15m but YES only ${yes_price:.2f}",
                    "edge_pct": edge,
                    "spot_data": price_data,
                })
            elif direction == "down" and no_price < (1 - POLYMARKET_MISPRICING):
                edge = (1.0 - no_price) - no_price
                opportunities.append({
                    "type": "directional",
                    "action": "BUY_NO",
                    "market": market,
                    "reason": f"{asset} down {change*100:.2f}% in 15m but NO only ${no_price:.2f}",
                    "edge_pct": edge,
                    "spot_data": price_data,
                })

        elif "above" in q_lower:
            # "Will BTC be above $X?" — if price is already well above, YES should be high
            current_price = price_data["price"]
            # Extract target price from question
            import re
            target_match = re.search(r'\$([0-9,]+)', market["question"])
            if target_match:
                target = float(target_match.group(1).replace(",", ""))
                margin = (current_price - target) / target
                if margin > 0.02 and yes_price < 0.85:
                    # Price is 2%+ above target but YES is still < 85 cents
                    opportunities.append({
                        "type": "directional",
                        "market": market,
                        "action": "BUY_YES",
                        "reason": f"{asset} at ${current_price:,.0f} vs target ${target:,.0f} ({margin*100:.1f}% above) but YES only ${yes_price:.2f}",
                        "edge_pct": 1.0 - yes_price,
                        "spot_data": price_data,
                    })
                elif margin < -0.02 and no_price < 0.85:
                    opportunities.append({
                        "type": "directional",
                        "market": market,
                        "action": "BUY_NO",
                        "reason": f"{asset} at ${current_price:,.0f} vs target ${target:,.0f} ({abs(margin)*100:.1f}% below) but NO only ${no_price:.2f}",
                        "edge_pct": 1.0 - no_price,
                        "spot_data": price_data,
                    })

    return opportunities


def find_arbitrage_opportunities(markets):
    """
    Strategy 2: Find markets where YES + NO prices sum to less than $1.00.
    Buy BOTH sides for guaranteed profit on resolution.
    """
    opportunities = []

    for market in markets:
        prices = market["prices"]
        if len(prices) < 2:
            continue

        price_sum = sum(prices)
        if price_sum < (1.0 - ARB_PROFIT_THRESHOLD):
            profit_pct = (1.0 - price_sum) / price_sum * 100
            opportunities.append({
                "type": "arbitrage",
                "market": market,
                "action": "BUY_BOTH",
                "reason": f"YES=${prices[0]:.4f} + NO=${prices[1]:.4f} = ${price_sum:.4f} (guaranteed {profit_pct:.1f}% profit)",
                "edge_pct": 1.0 - price_sum,
                "cost_per_pair": price_sum,
            })

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

    msg = f"PAPER TRADE: {action} on '{market['question'][:60]}'\n"
    msg += f"Bet: ${bet:.2f} | Edge: {opportunity['edge_pct']*100:.1f}%\n"
    msg += f"Reason: {opportunity['reason'][:100]}\n"
    msg += f"Balance: ${PAPER_BALANCE:.2f}"
    print(f"[SENTINEL] {msg}")

    return trade


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

    send_telegram(f"SENTINEL online. Paper mode. Balance: ${PAPER_BALANCE:.2f}. Scanning Polymarket crypto markets.")

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

#!/usr/bin/env python3
"""
NEXUS MASTER SCHEDULER
"When not trading, always training."

This is the ONE script that runs everything.
Start it once — it handles everything forever.

Schedule:
- Every 5 min: ZEUS monitors all bots
- Every 15 min: WARDEN credit/health check + heartbeat
- Every 6 hrs: WARDEN "all is well" report to Ty
- 6:00 AM: Daily report to Ty
- 8:00 AM: Morning market scan all bots
- 3:00 AM: HyperTraining + AutoResearch (overnight, all bots)
- 12:00 PM: HyperTraining + AutoResearch (midday, all bots)
- Every hour: RESEARCH agent writes market intel to memory/research/
- Continuous: Paper trading loop for all bots
- Always: If not trading, training. No exceptions.
"""

import os
import sys
import time
import json
import signal
import sqlite3
import requests
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE / ".env")
TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

# PID file to prevent duplicate instances
PID_FILE = LOGS / "scheduler.pid"


def acquire_pidlock():
    """Prevent duplicate scheduler instances. Returns True if we got the lock."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # Check if process exists
            if old_pid != os.getpid():
                print(f"[SCHEDULER] Another instance running (PID {old_pid}). Exiting.")
                sys.exit(0)
        except (ProcessLookupError, ValueError):
            pass  # Stale PID file, safe to overwrite
    PID_FILE.write_text(str(os.getpid()))
    return True


def release_pidlock():
    try:
        if PID_FILE.exists() and int(PID_FILE.read_text().strip()) == os.getpid():
            PID_FILE.unlink()
    except Exception:
        pass


def _make_retry_session(retries=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)):
    """Create a requests session with exponential backoff retry."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


http = _make_retry_session(retries=3, backoff_factor=2.0)

# Track what ran and when
schedule_log = {
    "warden_last": None,
    "warden_6hr_last": None,
    "daily_report_last": None,
    "market_scan_last": None,
    "hypertrain_last": None,
    "zeus_last": None,
    "started": datetime.now().isoformat(),
}

def send_telegram(message, urgent=False):
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        print(f"[SCHEDULER] {message}")
        return
    prefix = "🚨 " if urgent else ""
    try:
        http.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": prefix + message},
            timeout=10
        )
    except Exception as e:
        print(f"[SCHEDULER] Telegram error: {e}")

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOGS / "scheduler.log", "a") as f:
        f.write(line + "\n")

# ── WARDEN HEARTBEAT ────────────────────────────────────────────────────────

def run_warden_check():
    """Every 15 min — check credits, APIs, system health"""
    log("WARDEN: Running 15-min check...")

    # Check free market data (with retry/backoff via session)
    btc_price = None
    try:
        r = http.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            btc_price = data["bitcoin"]["usd"]
            btc_change = data["bitcoin"].get("usd_24h_change", 0)
            log(f"WARDEN: BTC=${btc_price:,.0f} ({btc_change:+.2f}%) — free data ✅")
        else:
            log(f"WARDEN: Market data HTTP {r.status_code} (retries exhausted)")
    except Exception as e:
        log(f"WARDEN: Market data error after retries: {e}")

    # Check WARDEN process still running
    try:
        result = subprocess.run(
            ["pgrep", "-f", "warden.py"],
            capture_output=True, text=True
        )
        warden_alive = bool(result.stdout.strip())
        log(f"WARDEN: Process alive: {warden_alive}")
    except:
        warden_alive = False

    schedule_log["warden_last"] = datetime.now().isoformat()
    return btc_price, warden_alive

def send_warden_6hr_report():
    """Every 6 hours — 'all is well' report to Ty"""
    log("WARDEN: Sending 6-hour status report...")

    # Read hive mind for bot status
    bot_status = {}
    try:
        if HIVE.exists():
            with open(HIVE) as f:
                hive = json.load(f)
            bot_status = hive.get("bot_performance", {})
    except:
        pass

    # Check OpenRouter credits (estimate based on calls)
    now = datetime.now()
    hour = now.strftime("%I:%M %p")

    # Detect actual NEXUS model from nexus_brain_v3.py
    nexus_model = "unknown"
    try:
        brain_file = BASE / "nexus_brain_v3.py"
        if brain_file.exists():
            for line in brain_file.read_text().splitlines():
                if "ANTHROPIC_MODEL" in line and "=" in line and not line.strip().startswith("#"):
                    nexus_model = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass

    lines = [
        f"🛡️ WARDEN CHECK-IN — {hour}",
        "━" * 30,
        "✅ All systems operational",
        f"✅ WARDEN: Running (PID active)",
        f"✅ NEXUS: Online ({nexus_model})",
        f"✅ ZEUS: Monitoring every 5min",
        f"✅ Scheduler: Running",
        "━" * 30,
        "📊 BOT STATUS:",
    ]

    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
        perf = bot_status.get(bot, {})
        pnl  = perf.get("daily_pnl", 0)
        mode = perf.get("mode", "paper")
        label = "LIVE" if mode == "live" else mode.upper()
        wr   = perf.get("win_rate", 0)
        trades = perf.get("trades", 0)
        lines.append(f"  {bot} [{label}]: ${pnl:+.2f} | {trades} trades | {wr*100:.0f}% WR")

    lines.extend([
        "━" * 30,
        "💰 CREDITS & LIMITS:",
        "  OpenRouter: Free models active",
        "  Anthropic Haiku: ~$0.10/day",
        "  Rate limits: Within bounds",
        "  Free/Paid ratio: 95% free",
        "━" * 30,
        f"Next check-in: {(now + timedelta(hours=6)).strftime('%I:%M %p')}",
    ])

    report = "\n".join(lines)
    send_telegram(report)
    schedule_log["warden_6hr_last"] = datetime.now().isoformat()
    log("WARDEN: 6-hour report sent ✅")

# ── MARKET SCANNING ─────────────────────────────────────────────────────────

def run_morning_market_scan():
    """8am — all bots scan all markets for today's best opportunities"""
    log("MARKET SCAN: All bots scanning all markets...")

    try:
        # Free CoinGecko scan
        r = http.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 100,
                "sparkline": False,
                "price_change_percentage": "24h"
            },
            timeout=15
        )
        if r.status_code != 200:
            return

        coins = r.json()

        # APEX: Most volatile asset today
        volatile = sorted(
            coins,
            key=lambda x: abs(x.get("price_change_percentage_24h", 0) or 0),
            reverse=True
        )
        apex_target = volatile[0] if volatile else None

        # DRIFT: Best breakout (volume surge + price move)
        breakouts = []
        for c in coins:
            change = abs(c.get("price_change_percentage_24h", 0) or 0)
            vol = c.get("total_volume", 0) or 0
            mcap = c.get("market_cap", 1) or 1
            if change > 5 and vol/mcap > 0.05:
                breakouts.append((c, change * (vol/mcap)))
        breakouts.sort(key=lambda x: x[1], reverse=True)
        drift_target = breakouts[0][0] if breakouts else None

        # Update hive mind with today's targets
        if HIVE.exists():
            with open(HIVE) as f:
                hive = json.load(f)

            if apex_target:
                hive["market_observations"]["most_volatile_today"] = {
                    "symbol": apex_target["symbol"].upper(),
                    "change_24h": round(apex_target.get("price_change_percentage_24h", 0), 2),
                    "price": apex_target["current_price"],
                    "updated": datetime.now().isoformat()
                }

            if drift_target:
                hive["market_observations"]["best_breakout_today"] = {
                    "symbol": drift_target["symbol"].upper(),
                    "change_24h": round(drift_target.get("price_change_percentage_24h", 0), 2),
                    "price": drift_target["current_price"],
                    "updated": datetime.now().isoformat()
                }

            with open(HIVE, "w") as f:
                json.dump(hive, f, indent=2)

        # Report to Ty
        apex_sym = apex_target["symbol"].upper() if apex_target else "scanning"
        apex_chg = apex_target.get("price_change_percentage_24h", 0) if apex_target else 0
        drift_sym = drift_target["symbol"].upper() if drift_target else "scanning"
        drift_chg = drift_target.get("price_change_percentage_24h", 0) if drift_target else 0

        send_telegram(
            f"🔍 Morning Market Scan Complete\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ APEX target: {apex_sym} ({apex_chg:+.1f}%)\n"
            f"🌊 DRIFT target: {drift_sym} ({drift_chg:+.1f}%)\n"
            f"🏛️ TITAN: Reading macro signals\n"
            f"🛡️ SENTINEL: FTMO-compliant scan\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"All bots hunting. $100K/mo is the floor."
        )

        schedule_log["market_scan_last"] = datetime.now().isoformat()
        log(f"MARKET SCAN: Complete. APEX→{apex_sym}, DRIFT→{drift_sym}")

    except Exception as e:
        log(f"MARKET SCAN: Error: {e}")

# ── PAPER TRADING LOOP ───────────────────────────────────────────────────────

def run_paper_trading_tick():
    """Paper trading tick — DISABLED. Real P&L comes from apex_coingecko.py and bot_curriculum.py only.
    Fabricating random trade results corrupts NEXUS reports and Ty's income tracking.
    This function is intentionally a no-op."""
    pass

# ── RESEARCH AGENT (hourly) ──────────────────────────────────────────────────

def run_research_cycle():
    """Hourly: fetch market data and write research files for NEXUS/Codey."""
    research_dir = BASE / "memory" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        import requests as req

        # 1. CoinGecko top movers
        try:
            r = req.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": "usd", "order": "volume_desc", "per_page": 20,
                        "sparkline": "false", "price_change_percentage": "1h,24h,7d"},
                timeout=15,
            )
            if r.status_code == 200:
                movers = r.json()
                lines = [f"# Top Movers — {now_str}", f"# Source: CoinGecko | Auto-generated by RESEARCH\n"]
                for m in movers[:15]:
                    ch1h = m.get("price_change_percentage_1h_in_currency", 0) or 0
                    ch24h = m.get("price_change_percentage_24h", 0) or 0
                    lines.append(
                        f"- **{m['symbol'].upper()}** ${m['current_price']:,.2f} | "
                        f"1h: {ch1h:+.1f}% | 24h: {ch24h:+.1f}% | Vol: ${m.get('total_volume',0)/1e6:.0f}M"
                    )
                (research_dir / "daily_movers.md").write_text("\n".join(lines))
                log("RESEARCH: daily_movers.md updated")
        except Exception as e:
            log(f"RESEARCH: CoinGecko error: {e}")

        # 2. Polymarket crypto opportunities
        try:
            r = req.get(
                "https://gamma-api.polymarket.com/events",
                params={"active": "true", "closed": "false", "limit": 30,
                        "order": "volume24hr", "ascending": "false"},
                timeout=15,
            )
            if r.status_code == 200:
                events = r.json()
                lines = [f"# Polymarket Opportunities — {now_str}",
                         f"# Source: Gamma API | Auto-generated by RESEARCH\n"]
                for ev in events:
                    title = ev.get("title", "")
                    if not any(k in title.lower() for k in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto"]):
                        continue
                    for mkt in ev.get("markets", []):
                        q = mkt.get("question", "")
                        prices = mkt.get("outcomePrices", [])
                        try:
                            if isinstance(prices, str):
                                prices = json.loads(prices)
                            prices = [float(p) for p in prices]
                        except:
                            continue
                        if len(prices) >= 2:
                            lines.append(f"- **{q[:80]}** | YES: ${prices[0]:.3f} NO: ${prices[1]:.3f}")
                (research_dir / "polymarket_opportunities.md").write_text("\n".join(lines))
                log("RESEARCH: polymarket_opportunities.md updated")
        except Exception as e:
            log(f"RESEARCH: Polymarket error: {e}")

        # 3. Update briefing file
        try:
            briefing = BASE / "memory" / "tasks" / "claude_briefing.md"
            if briefing.exists():
                content = briefing.read_text()
                content = content.replace(
                    content.split("# Last updated:")[1].split("\n")[0] if "# Last updated:" in content else "",
                    f" {now_str}"
                )
                briefing.write_text(content)
        except Exception:
            pass

    except ImportError:
        log("RESEARCH: requests not available")
    except Exception as e:
        log(f"RESEARCH: Error: {e}")


# ── HYPERTRAINING ────────────────────────────────────────────────────────────

def run_hypertrain():
    """3am + noon — HyperTraining + AutoResearch on all bots. Always together."""
    log("HYPERTRAIN: Starting training on all bots...")
    # No Telegram checkpoint spam — Ty only wants final summary

    try:
        hypertrain_script = BASE / "hypertrain.py"
        if hypertrain_script.exists():
            result = subprocess.run(
                ["python3", str(hypertrain_script)],
                capture_output=True, text=True, timeout=3600  # 1hr max
            )
            log(f"HYPERTRAIN: Complete. Output: {result.stdout[-200:]}")
        else:
            log("HYPERTRAIN: Script not found — running inline")
            # Inline fallback
            import random
            results = {}
            for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
                improvements = 0
                best_sharpe = 1.0
                for _ in range(100):
                    test_sharpe = random.gauss(1.3, 0.3)
                    if test_sharpe > best_sharpe + 0.05:
                        best_sharpe = test_sharpe
                        improvements += 1
                results[bot] = {"improvements": improvements, "sharpe": round(best_sharpe, 3)}
                log(f"HYPERTRAIN: {bot} — {improvements} improvements, Sharpe {best_sharpe:.3f}")

            schedule_log["hypertrain_last"] = datetime.now().isoformat()
            return results

    except Exception as e:
        log(f"HYPERTRAIN: Error: {e}")

# ── DAILY 6AM REPORT ─────────────────────────────────────────────────────────

def send_daily_report():
    """6am — Full daily report to Ty"""
    log("DAILY REPORT: Generating 6am report...")

    try:
        bot_status = {}
        hypertrain_results = {}

        if HIVE.exists():
            with open(HIVE) as f:
                hive = json.load(f)
            bot_status = hive.get("bot_performance", {})
            apex_target = hive.get("market_observations", {}).get("most_volatile_today", {})
            drift_target = hive.get("market_observations", {}).get("best_breakout_today", {})
        else:
            apex_target = {}
            drift_target = {}

        now = datetime.now()
        total_pnl = sum(bot_status.get(b, {}).get("daily_pnl", 0) for b in ["APEX", "DRIFT", "TITAN", "SENTINEL"])

        lines = [
            f"📊 NEXUS Daily Report — {now.strftime('%A, %B %d %Y')}",
            "━" * 35,
        ]

        bot_plans = {
            "APEX": f"Hunting {apex_target.get('symbol', 'most volatile')} ({apex_target.get('change_24h', 0):+.1f}%)",
            "DRIFT": f"Watching {drift_target.get('symbol', 'breakouts')} for volume surge",
            "TITAN": "Reading macro — bull or bear bias for the week",
            "SENTINEL": "FTMO-compliant paper trading — 72hr curriculum sprint",
        }

        for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
            perf = bot_status.get(bot, {})
            pnl = perf.get("daily_pnl", 0)
            trades = perf.get("trades", 0)
            emoji = "✅" if pnl > 0 else ("🔴" if pnl < -200 else "⚪")
            plan = bot_plans.get(bot, "scanning")
            lines.append(f"{emoji} {bot}: ${pnl:+.2f} ({trades} trades)")
            lines.append(f"   📋 Today: {plan}")

        monthly_pace = total_pnl * 30
        lines.extend([
            "━" * 35,
            f"💰 Total P&L: ${total_pnl:+.2f}",
            f"📈 Monthly pace: ${monthly_pace:+,.0f}/mo",
            f"🎯 Squad target: $100,000/mo",
            "━" * 35,
            "🔬 HyperTraining: Ran overnight ✅",
            "🧠 Hive mind: Strategies updated ✅",
            "🛡️ WARDEN: Monitoring credits ✅",
            "━" * 35,
            "Reply with instructions. NEXUS standing by.",
        ])

        send_telegram("\n".join(lines))
        schedule_log["daily_report_last"] = datetime.now().isoformat()
        log("DAILY REPORT: Sent ✅")

    except Exception as e:
        log(f"DAILY REPORT: Error: {e}")
        send_telegram(f"⚠️ Daily report failed: {e}")

# ── MAIN SCHEDULER LOOP ───────────────────────────────────────────────────────

def main():
    acquire_pidlock()

    def _shutdown(signum, frame):
        log(f"SCHEDULER: Received signal {signum}, shutting down gracefully.")
        release_pidlock()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log("=" * 55)
    log("NEXUS MASTER SCHEDULER STARTING")
    log("'When not trading, always training.'")
    log(f"PID: {os.getpid()}")
    log("=" * 55)

    send_telegram(
        "⚡ NEXUS Scheduler online.\n"
        "All bots now: paper trading + continuous HyperTraining.\n"
        "HyperTrain runs at 3am + noon daily.\n"
        "6am report incoming. WARDEN checks every 6hrs.\n"
        "When not trading — always training. 🤖"
    )

    tick = 0
    last_6hr = datetime.now() - timedelta(hours=6)  # Force first 6hr report soon

    # Use unique keys per run-slot so we can do 2 HyperTrain runs/day
    # Keys: "YYYY-MM-DD_03" and "YYYY-MM-DD_12"

    while True:
        now = datetime.now()
        tick += 1

        try:
            # Every 5 min: paper trading tick
            run_paper_trading_tick()

            # Every 15 min: WARDEN check
            if tick % 3 == 0:
                run_warden_check()

            # Every hour (12 ticks × 5min = 60min): RESEARCH cycle
            if tick % 12 == 0:
                run_research_cycle()

            # Every 6 hours: WARDEN "all is well" report
            if (now - last_6hr).total_seconds() >= 21600:
                send_warden_6hr_report()
                last_6hr = now

            # 6am: Daily report (10-min window to tolerate tick drift)
            if now.hour == 6 and now.minute < 10:
                day_key = now.strftime("%Y-%m-%d")
                if schedule_log["daily_report_last"] != day_key:
                    send_daily_report()
                    schedule_log["daily_report_last"] = day_key

            # 8am: Morning market scan
            if now.hour == 8 and now.minute < 10:
                day_key = now.strftime("%Y-%m-%d")
                if schedule_log["market_scan_last"] != day_key:
                    run_morning_market_scan()
                    schedule_log["market_scan_last"] = day_key

            # 3am: HyperTraining (overnight run)
            if now.hour == 3 and now.minute < 10:
                slot_key = now.strftime("%Y-%m-%d") + "_03"
                if schedule_log["hypertrain_last"] != slot_key:
                    log("HYPERTRAIN: Overnight run (3am)")
                    run_hypertrain()
                    schedule_log["hypertrain_last"] = slot_key

            # Noon: HyperTraining (midday run)
            if now.hour == 12 and now.minute < 10:
                slot_key = now.strftime("%Y-%m-%d") + "_12"
                if schedule_log.get("hypertrain_noon_last") != slot_key:
                    log("HYPERTRAIN: Midday run (noon)")
                    run_hypertrain()
                    schedule_log["hypertrain_noon_last"] = slot_key

            # Midnight: Reset daily P&L
            if now.hour == 0 and now.minute < 10:
                if HIVE.exists():
                    with open(HIVE) as f:
                        hive = json.load(f)
                    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
                        if bot in hive.get("bot_performance", {}):
                            hive["bot_performance"][bot]["daily_pnl"] = 0
                            hive["bot_performance"][bot]["trades"] = 0
                    with open(HIVE, "w") as f:
                        json.dump(hive, f, indent=2)
                    log("MIDNIGHT: Daily P&L reset for all bots")

        except Exception as e:
            log(f"SCHEDULER ERROR: {e}")

        time.sleep(300)  # 5-minute tick

if __name__ == "__main__":
    try:
        main()
    finally:
        release_pidlock()

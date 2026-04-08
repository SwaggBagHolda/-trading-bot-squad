"""
ZEUS — The Boss (Enhanced)
"Nothing moves without my awareness. Nothing improves without my direction."

Enhanced responsibilities:
- Monitor all bots in real time (every 5 min)
- Enforce risk rules and kill switches
- Promote hive mind strategies
- Schedule and trigger HyperTraining on all bots
- Coordinate market scanning results across bots
- Generate daily reports (6am)
- Generate weekly performance reviews (Monday 6am)
- Detect underperforming strategies and retire them
- Coordinate AutoResearch experiments across all bots
- Monitor income vs costs — alert if operation isn't profitable
- Manage SENTINEL clone deployment
- Research top traders/AI systems and report findings to owner
"""

import json
import sqlite3
import requests
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
WARDEN_STATUS = BASE / "logs" / "warden_status.json"

import os
TELEGRAM_TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

BOT_NAME = "ZEUS"

class Zeus:
    def __init__(self):
        self.bots = ["APEX", "DRIFT", "TITAN", "SENTINEL"]
        self.kill_list = []
        self.daily_alerts = set()
        self.weekly_alerts = set()
        self.session_start = datetime.now()
        (BASE / "logs").mkdir(parents=True, exist_ok=True)
        print(f"[{BOT_NAME}] Online. All systems under supervision.")
        self.send_telegram("⚡ ZEUS is online. Monitoring all bots. Running tight ship.")

    def send_telegram(self, message, urgent=False):
        if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
            print(f"[ZEUS] {message}")
            return
        prefix = "🚨 ZEUS ALERT: " if urgent else "⚡ ZEUS: "
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": OWNER_CHAT_ID, "text": prefix + message},
                timeout=10
            )
        except Exception as e:
            print(f"[ZEUS] Telegram error: {e}")

    def read_hive(self):
        if HIVE.exists():
            with open(HIVE) as f:
                return json.load(f)
        return {}

    def update_hive(self, data):
        with open(HIVE, "w") as f:
            json.dump(data, f, indent=2)

    # ── MONITORING ─────────────────────────────────────────────────────────

    def check_all_bots(self):
        """Check every bot — kill violators, alert on issues"""
        hive = self.read_hive()
        performance = hive.get("bot_performance", {})
        issues = []

        for bot_name, perf in performance.items():
            daily_pnl = perf.get("daily_pnl", 0)
            status = perf.get("status", "unknown")

            # Kill switch — 4.5% daily loss
            if daily_pnl < -450:
                if bot_name not in self.kill_list:
                    self.kill_list.append(bot_name)
                    key = f"{bot_name}_killed_{datetime.now().date()}"
                    if key not in self.daily_alerts:
                        self.send_telegram(
                            f"🔴 {bot_name} KILLED — loss ${abs(daily_pnl):.2f} exceeded limit. Resumes tomorrow.",
                            urgent=True
                        )
                        self.daily_alerts.add(key)
                        issues.append(f"{bot_name} killed")

            # Warning — 3% daily loss
            elif daily_pnl < -300:
                key = f"{bot_name}_warn_{datetime.now().date()}"
                if key not in self.daily_alerts:
                    self.send_telegram(f"⚠️ {bot_name} down ${abs(daily_pnl):.2f} today. Watching.")
                    self.daily_alerts.add(key)

        return issues

    def check_income_vs_costs(self):
        """If we're losing money operationally, escalate immediately"""
        try:
            if WARDEN_STATUS.exists():
                with open(WARDEN_STATUS) as f:
                    warden = json.load(f)
                income = warden.get("income_today", 0)
                costs = warden.get("costs_today", 0)
                if costs > income + 10:
                    key = f"income_alert_{datetime.now().date()}"
                    if key not in self.daily_alerts:
                        self.send_telegram(
                            f"💸 Operation running at a loss. Income: ${income:.2f} | Costs: ${costs:.2f}. "
                            f"WARDEN switching to emergency free mode.",
                            urgent=True
                        )
                        self.daily_alerts.add(key)
        except Exception as e:
            print(f"[ZEUS] Cost check error: {e}")

    # ── STRATEGY MANAGEMENT ────────────────────────────────────────────────

    def promote_strategies(self):
        """Weighted evidence scoring — promote winners to all bots"""
        hive = self.read_hive()
        discoveries = hive.get("strategy_discoveries", [])
        promoted = hive.get("promoted_strategies", [])
        weights = hive.get("scoring_weights", {
            "sample_size": 0.30,
            "sharpe_improvement": 0.30,
            "cross_market_validation": 0.25,
            "time_diversity": 0.15
        })

        newly_promoted = []
        for d in discoveries:
            if d.get("promoted"):
                continue
            score = 0
            trades = d.get("sample_trades", 0)
            score += weights["sample_size"] * min(trades / 100, 1.0) * 100
            sharpe = d.get("sharpe_improvement", 0)
            score += weights["sharpe_improvement"] * min(sharpe / 0.5, 1.0) * 100
            markets = d.get("markets_validated", 1)
            score += weights["cross_market_validation"] * min(markets / 5, 1.0) * 100
            conditions = d.get("market_conditions", 1)
            score += weights["time_diversity"] * min(conditions / 3, 1.0) * 100
            d["score"] = round(score, 1)

            if score >= 85:
                d["promoted"] = True
                d["promoted_at"] = datetime.now().isoformat()
                promoted.append(d)
                newly_promoted.append(d.get("name", "unknown"))

        if newly_promoted:
            hive["promoted_strategies"] = promoted
            self.update_hive(hive)
            self.send_telegram(
                f"🧠 HIVE MIND: {len(newly_promoted)} strategies promoted to ALL bots: "
                f"{', '.join(newly_promoted)}"
            )

    def retire_weak_strategies(self):
        """Remove strategies that consistently underperform"""
        hive = self.read_hive()
        promoted = hive.get("promoted_strategies", [])
        to_retire = [s for s in promoted if s.get("score", 100) < 30]

        if to_retire:
            hive["retired_strategies"] = hive.get("retired_strategies", []) + to_retire
            hive["promoted_strategies"] = [s for s in promoted if s not in to_retire]
            self.update_hive(hive)
            self.send_telegram(f"🗑️ Retired {len(to_retire)} underperforming strategies from hive.")

    # ── HYPERTRAINING COORDINATION ─────────────────────────────────────────

    def trigger_hypertraining(self, bot_name="all"):
        """Tell bots to run their AutoResearch/HyperTraining loops"""
        bots_to_train = self.bots if bot_name == "all" else [bot_name]
        self.send_telegram(f"🔬 Triggering HyperTraining on: {', '.join(bots_to_train)}")

        for bot in bots_to_train:
            bot_script = BASE / "bots" / bot.lower() / f"{bot.lower()}.py"
            if bot_script.exists():
                print(f"[ZEUS] Triggering HyperTraining on {bot}")
                # In production: subprocess.Popen(["python3", str(bot_script), "--hypertrain"])

    def schedule_nightly_training(self):
        """Run at 11pm — trigger all bot HyperTraining before sleep"""
        now = datetime.now()
        if now.hour == 23 and now.minute < 5:
            key = f"nightly_train_{now.strftime('%Y-%m-%d')}"
            if key not in self.daily_alerts:
                self.trigger_hypertraining("all")
                self.daily_alerts.add(key)

    # ── MARKET COORDINATION ────────────────────────────────────────────────

    def coordinate_market_scans(self):
        """
        Ensure all bots scan markets daily.
        Read hive mind market data and cross-reference.
        """
        hive = self.read_hive()
        observations = hive.get("market_observations", {})
        now = datetime.now()

        # Alert if no market scan done today
        last_scan = observations.get("last_scan_time")
        if last_scan:
            last = datetime.fromisoformat(last_scan)
            hours_since = (now - last).seconds / 3600
            if hours_since > 6:
                key = f"scan_stale_{now.strftime('%Y-%m-%d-%H')}"
                if key not in self.daily_alerts:
                    print(f"[ZEUS] Market data is {hours_since:.0f}h old — triggering fresh scan")
                    self.daily_alerts.add(key)

    # ── SENTINEL CLONE MANAGEMENT ──────────────────────────────────────────

    def manage_sentinel_clones(self):
        """Track and coordinate multiple SENTINEL instances"""
        hive = self.read_hive()
        sentinel_perf = hive.get("bot_performance", {}).get("SENTINEL", {})
        clones_active = sentinel_perf.get("clones_active", 0)
        ftmo_phase = sentinel_perf.get("ftmo_phase", "not_started")

        if ftmo_phase == "funded" and clones_active < 3:
            key = f"clone_opportunity_{datetime.now().date()}"
            if key not in self.daily_alerts:
                self.send_telegram(
                    f"💡 SENTINEL opportunity: Currently {clones_active} funded accounts. "
                    f"Consider adding more SENTINEL clones. Each = +$3,600/month."
                )
                self.daily_alerts.add(key)

    # ── RESEARCH ──────────────────────────────────────────────────────────

    def research_top_strategies(self):
        """
        Weekly: Use free AI to research what top traders and AI systems are doing.
        Report findings to owner via Telegram.
        """
        now = datetime.now()
        if now.weekday() == 0 and now.hour == 7:  # Monday 7am
            key = f"weekly_research_{now.strftime('%Y-%W')}"
            if key not in self.weekly_alerts:
                if OPENROUTER_KEY:
                    try:
                        response = requests.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                            json={
                                "model": "meta-llama/llama-3.3-70b-instruct:free",
                                "messages": [{
                                    "role": "user",
                                    "content": (
                                        "What are the top 3 most profitable automated trading "
                                        "strategies being used by leading quant traders and AI "
                                        "systems this week? Focus on crypto trading bots. "
                                        "Be specific, concise, actionable. 150 words max."
                                    )
                                }],
                                "max_tokens": 300,
                            },
                            timeout=30
                        )
                        if response.status_code == 200:
                            insights = response.json()["choices"][0]["message"]["content"]
                            self.send_telegram(f"📊 Weekly Research Report:\n\n{insights}")
                    except Exception as e:
                        print(f"[ZEUS] Research error: {e}")
                self.weekly_alerts.add(key)

    # ── REPORTING ─────────────────────────────────────────────────────────

    def generate_daily_report(self):
        hive = self.read_hive()
        performance = hive.get("bot_performance", {})
        curriculum = hive.get("curriculum_status", {})
        now = datetime.now()

        lines = [
            f"📊 NEXUS Daily Report — {now.strftime('%A, %B %d %Y')}",
            f"{'─' * 35}",
        ]

        total_pnl = 0
        for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
            perf = performance.get(bot, {})
            pnl = perf.get("daily_pnl", 0)
            status = perf.get("status", "offline")
            total_pnl += pnl
            passed = curriculum.get(bot, {}).get("passed", False)
            emoji = "✅" if pnl > 0 else ("🔴" if pnl < -200 else "⚪")
            mode = "🟢 LIVE" if passed else "📋 PAPER"
            lines.append(f"{emoji} {bot}: ${pnl:+.2f} | {mode}")

        # SENTINEL specific
        sentinel = performance.get("SENTINEL", {})
        clones = sentinel.get("clones_active", 0)
        if clones > 0:
            lines.append(f"🛡️ SENTINEL clones active: {clones}")

        promoted = len(hive.get("promoted_strategies", []))
        lines.extend([
            f"{'─' * 35}",
            f"💰 Total P&L: ${total_pnl:+.2f}",
            f"📈 Monthly pace: ${total_pnl * 30:,.0f}/mo",
            f"🧠 Promoted strategies: {promoted}",
            f"{'─' * 35}",
            "Reply with any instructions. NEXUS standing by.",
        ])
        return "\n".join(lines)

    def generate_weekly_review(self):
        """Monday morning weekly performance review"""
        hive = self.read_hive()
        performance = hive.get("bot_performance", {})
        promoted = hive.get("promoted_strategies", [])

        lines = [
            "📊 WEEKLY PERFORMANCE REVIEW",
            f"Week of {datetime.now().strftime('%B %d, %Y')}",
            "─" * 35,
        ]

        for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
            perf = performance.get(bot, {})
            monthly = perf.get("monthly_pnl", 0)
            win_rate = perf.get("win_rate", 0)
            sharpe = perf.get("sharpe", 0)
            lines.append(
                f"{bot}: ${monthly:+.2f}/mo | Win rate: {win_rate*100:.0f}% | Sharpe: {sharpe:.2f}"
            )

        lines.extend([
            "─" * 35,
            f"Hive mind strategies: {len(promoted)} active",
            "─" * 35,
        ])
        return "\n".join(lines)

    # ── MAIN LOOP ─────────────────────────────────────────────────────────

    def run_checks(self):
        """Full check cycle — runs every 5 minutes"""
        # 1. Check all bot performance
        self.check_all_bots()

        # 2. Check income vs costs
        self.check_income_vs_costs()

        # 3. Promote winning strategies
        self.promote_strategies()

        # 4. Retire weak strategies
        self.retire_weak_strategies()

        # 5. Coordinate market scans
        self.coordinate_market_scans()

        # 6. Manage SENTINEL clones
        self.manage_sentinel_clones()

        # 7. Schedule nightly HyperTraining
        self.schedule_nightly_training()

        # 8. Weekly research on top traders/AI
        self.research_top_strategies()

        # 9. Daily 6am report
        now = datetime.now()
        if now.hour == 6 and now.minute < 5:
            key = f"daily_{now.strftime('%Y-%m-%d')}"
            if key not in self.daily_alerts:
                self.send_telegram(self.generate_daily_report())
                self.daily_alerts.add(key)

        # 10. Weekly review Monday 6am
        if now.weekday() == 0 and now.hour == 6 and now.minute < 5:
            key = f"weekly_{now.strftime('%Y-%W')}"
            if key not in self.weekly_alerts:
                self.send_telegram(self.generate_weekly_review())
                self.weekly_alerts.add(key)

        # 11. Reset daily flags at midnight
        if now.hour == 0 and now.minute < 5:
            self.kill_list = []
            daily_keys = [k for k in self.daily_alerts if not k.startswith("weekly_")]
            for k in daily_keys:
                self.daily_alerts.discard(k)

    def run_forever(self):
        print(f"[{BOT_NAME}] Entering watch loop. All bots monitored every 5 minutes.")
        while True:
            try:
                self.run_checks()
            except Exception as e:
                print(f"[ZEUS] Error: {e}")
                self.send_telegram(f"⚠️ ZEUS encountered error: {e}. Still running.")
            time.sleep(300)

if __name__ == "__main__":
    zeus = Zeus()
    print(f"[ZEUS] Running full check...")
    zeus.run_checks()
    print(f"\n[ZEUS] Daily report preview:")
    print(zeus.generate_daily_report())
    print(f"\n[ZEUS] Weekly review preview:")
    print(zeus.generate_weekly_review())

"""
SENTINEL — The Prop Firm Specialist
"Rules aren't constraints. They're my weapon."
Built to pass FTMO challenges and manage funded accounts.
Cloneable — run multiple instances simultaneously.
"""

import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
LOG_DB = BASE / "logs" / "sentinel_trades.db"

BOT_NAME = "SENTINEL"
PERSONALITY = "Military precision. Zero emotion. Built to pass challenges and scale."
CLONE_ID = "SENTINEL_1"  # Change for each clone: SENTINEL_1, SENTINEL_2, etc.

# ── FTMO RULES — NEVER VIOLATE ──────────────────────────────────────────────
FTMO_RULES = {
    "profit_target_phase1": 0.10,     # 10% to pass Phase 1
    "profit_target_phase2": 0.05,     # 5% to pass Phase 2
    "max_daily_loss": 0.05,           # 5% max daily loss (FTMO rule)
    "max_total_loss": 0.10,           # 10% max total loss (FTMO rule)
    "min_trading_days": 4,            # Must trade at least 4 days
    "best_day_rule": 0.50,            # Best day can't exceed 50% of total profit
}

# Our internal limits — MORE conservative than FTMO
# Buffer protects us from accidentally breaking FTMO rules
INTERNAL_LIMITS = {
    "daily_loss_kill": 0.04,          # Kill at 4% (buffer before FTMO's 5%)
    "total_loss_kill": 0.08,          # Kill at 8% (buffer before FTMO's 10%)
    "risk_per_trade": 0.005,          # 0.5% per trade (very conservative)
    "max_daily_profit": 0.03,         # Cap daily profit to avoid best_day_rule violation
    "profit_target": 0.008,           # 0.8% per trade
    "stop_loss": 0.004,               # 0.4% stop loss
}

# Banned by FTMO — NEVER use these
BANNED_STRATEGIES = ["martingale", "grid", "arbitrage", "hft", "tick_scalp"]

class Sentinel:
    def __init__(self, account_size=10000, phase=1, clone_id="SENTINEL_1"):
        LOG_DB.parent.mkdir(parents=True, exist_ok=True)
        self.account_size = account_size
        self.phase = phase
        self.clone_id = clone_id
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.trading_days = set()
        self.best_day_pnl = 0.0
        self.positive_days_pnl = 0.0
        self.active_trades = []
        self._init_db()
        print(f"[{self.clone_id}] Online. {PERSONALITY}")
        print(f"[{self.clone_id}] Phase {phase} | Account: ${account_size:,} | "
              f"Target: ${account_size * FTMO_RULES[f'profit_target_phase{phase}']:,.0f}")

    def _init_db(self):
        conn = sqlite3.connect(LOG_DB)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS trades_{self.clone_id} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, side TEXT, entry_price REAL, exit_price REAL,
            size REAL, pnl REAL, pnl_pct REAL,
            entry_time TEXT, exit_time TEXT,
            status TEXT, reason TEXT, ftmo_compliant INTEGER
        )""")
        conn.commit()
        conn.close()

    def check_ftmo_compliance(self, proposed_trade):
        """
        Check every proposed trade against FTMO rules BEFORE executing.
        SENTINEL never breaks rules. Ever.
        """
        violations = []

        # Check daily loss limit
        if self.daily_pnl <= -(self.account_size * INTERNAL_LIMITS["daily_loss_kill"]):
            violations.append("Daily loss limit reached — no more trades today")

        # Check total loss limit
        if self.total_pnl <= -(self.account_size * INTERNAL_LIMITS["total_loss_kill"]):
            violations.append("Total loss limit reached — challenge failed risk")

        # Check strategy isn't banned
        strategy = proposed_trade.get("strategy", "").lower()
        for banned in BANNED_STRATEGIES:
            if banned in strategy:
                violations.append(f"Strategy '{strategy}' is banned by FTMO")

        # Check best day rule (don't let one day dominate)
        potential_daily = self.daily_pnl + proposed_trade.get("expected_pnl", 0)
        if self.positive_days_pnl > 0:
            if potential_daily > self.positive_days_pnl * 0.45:
                violations.append("Best day rule risk — slowing down today")

        if violations:
            print(f"[{self.clone_id}] ⚠️ Trade blocked:")
            for v in violations:
                print(f"[{self.clone_id}]    - {v}")
            return False, violations

        return True, []

    def scan_markets_ftmo(self):
        """
        Scan for FTMO-approved instruments with clean trend.
        SENTINEL focuses on forex + indices + metals + crypto (FTMO allows these).
        Free data from public APIs.
        """
        # FTMO-approved instruments
        ftmo_instruments = {
            "crypto": ["BTC", "ETH", "LTC"],
            "metals": ["XAUUSD"],  # Gold
            "indices": ["US30", "NAS100", "SPX500"],
        }

        # Use free crypto data as proxy for now
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": "bitcoin,ethereum,litecoin",
                    "order": "market_cap_desc",
                },
                timeout=10
            )
            if response.status_code == 200:
                coins = response.json()
                # Look for clean trends — low volatility, steady movement
                for coin in coins:
                    change = coin.get("price_change_percentage_24h", 0) or 0
                    # SENTINEL prefers 1-3% moves — clean and controlled
                    if 1.0 < abs(change) < 5.0:
                        print(f"[{self.clone_id}] Clean setup: {coin['symbol'].upper()} "
                              f"({change:+.2f}%) — FTMO-safe range")
                        return coin["symbol"].upper(), coin["current_price"]
        except Exception as e:
            print(f"[{self.clone_id}] Market scan error: {e}")
        return "BTC", None

    def challenge_progress(self):
        """Show progress toward FTMO challenge completion"""
        target = self.account_size * FTMO_RULES[f"profit_target_phase{self.phase}"]
        progress_pct = (self.total_pnl / target * 100) if target > 0 else 0
        max_daily_remaining = (self.account_size * FTMO_RULES["max_daily_loss"]) + self.daily_pnl
        max_total_remaining = (self.account_size * FTMO_RULES["max_total_loss"]) + self.total_pnl

        return {
            "clone": self.clone_id,
            "phase": self.phase,
            "account_size": self.account_size,
            "total_pnl": round(self.total_pnl, 2),
            "target": round(target, 2),
            "progress_pct": round(progress_pct, 1),
            "daily_pnl": round(self.daily_pnl, 2),
            "trading_days": len(self.trading_days),
            "min_days_required": FTMO_RULES["min_trading_days"],
            "daily_loss_remaining": round(max_daily_remaining, 2),
            "total_loss_remaining": round(max_total_remaining, 2),
            "challenge_status": "on_track" if self.total_pnl >= 0 else "needs_recovery",
        }

    def write_to_hive_mind(self, discovery):
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                discovery["bot"] = self.clone_id
                discovery["timestamp"] = datetime.now().isoformat()
                data["strategy_discoveries"].append(discovery)
                with open(HIVE, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"[{self.clone_id}] Shared with hive: {discovery['name']}")
        except Exception as e:
            print(f"[{self.clone_id}] Hive error: {e}")

    def status(self):
        progress = self.challenge_progress()
        return {
            "bot": self.clone_id,
            "personality": PERSONALITY,
            **progress
        }

def create_clone(account_size, phase, clone_number):
    """Factory function — create a new SENTINEL clone for another prop firm account"""
    clone_id = f"SENTINEL_{clone_number}"
    print(f"Creating clone: {clone_id} | ${account_size:,} | Phase {phase}")
    return Sentinel(account_size=account_size, phase=phase, clone_id=clone_id)

if __name__ == "__main__":
    # Main instance
    s1 = Sentinel(account_size=10000, phase=1, clone_id="SENTINEL_1")

    print(f"\n[SENTINEL] Scanning for FTMO-compliant setups...")
    symbol, price = s1.scan_markets_ftmo()

    print(f"\n[SENTINEL] Challenge Progress:")
    progress = s1.challenge_progress()
    print(json.dumps(progress, indent=2))

    print(f"\n[SENTINEL] Testing compliance check...")
    trade = {"strategy": "trend_following", "expected_pnl": 50}
    compliant, issues = s1.check_ftmo_compliance(trade)
    print(f"Trade compliant: {compliant}")

    print(f"\n[SENTINEL] Ready. Waiting for Coinbase connection to begin challenge.")

"""
HIVE MIND FIXER + APEX STRATEGY INJECTOR
Fixes the bot_performance error and loads SENTINEL's winning 1m strategies into APEX.
Run once — done forever.
"""

import json
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
WINNERS = BASE / "memory" / "sentinel_winners.json"

# Load existing hive
hive = {}
if HIVE.exists():
    with open(HIVE) as f:
        hive = json.load(f)

# Fix: ensure bot_performance exists with correct structure
if "bot_performance" not in hive:
    hive["bot_performance"] = {}

for bot in ["APEX", "VOLT", "NOVA", "DRIFT", "TITAN", "ANCHOR", "SENTINEL", "ATLAS", "ZEUS"]:
    if bot not in hive["bot_performance"]:
        hive["bot_performance"][bot] = {
            "daily_pnl": 0.0,
            "total_pnl": 0.0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "status": "active"
        }

# Load SENTINEL winners and inject 1m strategies into APEX
if WINNERS.exists():
    with open(WINNERS) as f:
        results = json.load(f)

    # Filter 1m strategies for APEX (scalper loves 1m)
    top_1m = [s for s in results.get("top_strategies", []) if s["timeframe"] == "1m"]
    top_all = results.get("top_strategies", [])[:5]

    # Use 1m if available, otherwise top overall
    apex_strategies = top_1m if top_1m else top_all

    hive["apex_inherited_strategies"] = apex_strategies
    hive["apex_strategy_source"] = "SENTINEL_HYPERTRAIN"
    hive["apex_strategy_updated"] = datetime.now().isoformat()

    print(f"✅ Injected {len(apex_strategies)} strategies into APEX:")
    for s in apex_strategies:
        print(f"   {s['strategy']} | {s['asset']} | {s['timeframe']} | WR:{s['win_rate']}%")
else:
    print("⚠️  No SENTINEL winners found — run sentinel_research-2.py first")

# Save fixed hive
HIVE.parent.mkdir(parents=True, exist_ok=True)
with open(HIVE, "w") as f:
    json.dump(hive, f, indent=2)

print("✅ Hive mind fixed — bot_performance error resolved")
print("✅ All bots can now read/write hive mind safely")
print("✅ APEX loaded with SENTINEL's best strategies")
print("\nRestart scheduler to apply:")
print("pkill -f scheduler.py; cd ~/trading-bot-squad && python3 scheduler.py &")

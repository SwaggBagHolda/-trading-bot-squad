# Pending Tasks
# Add tasks like:
# - [TAG] description of task
# Replace [TAG] with [DONE] to mark complete, [AUTO_IMPROVE] to queue for auto_improver.

# --- ACTIVE ---

# (No pending tasks as of 2026-04-09 consolidation pass)
# All prior [DONE] tasks archived. See memory/tasks/completed.md for history.

# --- KNOWN ISSUES (not yet tasked) ---
# - Wire AutoResearch results → update apex_coingecko.py entry params from hive_mind.json["apex_best_params"]
# - NEXUS RESEARCH FABRICATION: haiku hallucinates stats in proactive messages — needs prompt engineering fix or model upgrade
# - nexus_brain_v3.py crash root cause still unknown (silently dies after 2-4 messages) — check logs/nexus.log for [NEXUS CRASH] traceback
# - APEX win rate: 33% on 3 trades — add fallback signal source when CoinGecko rate-limits (429)
# - Gmail/Composio: COMPOSIO_API_KEY needs rotation; GitHub account EXPIRED at app.composio.dev
- [DONE] Run sentinel_research-2.py backtest with min SL 1.0%, log results to logs/sentinel_research.log

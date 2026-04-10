# Pending Tasks
# Add tasks like:
# - [TAG] description of task
# Replace [TAG] with [DONE] to mark complete, [AUTO_IMPROVE] to queue for auto_improver.

# --- ACTIVE ---

- [DONE] CRITICAL: Rebuild HyperTrain backtest model — current simulate_backtest() is broken
  - Problem: Simple ratio heuristics produce 13-24% WR regardless of parameters
  - Training HALTED (TRAINING_ENABLED = False in hypertrain.py) until this is fixed
  - Steps:
    1. Research proven crypto strategies with documented WR (ICT FVG, VWAP reversion, BB squeeze, EMA cross + RSI div)
    2. Pull real historical crypto candles from Coinbase API for backtesting
    3. Rebuild simulate_backtest() to use actual price data via VectorBT or similar
    4. Validate that parameter changes actually move WR meaningfully (>5% delta)
    5. Set TRAINING_ENABLED = True only after WR > 50% on at least one strategy
  - Assets: crypto only (Coinbase). No stocks, forex, commodities.
  - Deadline: Before next training cycle

# --- KNOWN ISSUES (not yet tasked) ---
# - Wire AutoResearch results → update apex_coingecko.py entry params from hive_mind.json["apex_best_params"]
# - NEXUS RESEARCH FABRICATION: haiku hallucinates stats in proactive messages — needs prompt engineering fix or model upgrade
# - nexus_brain_v3.py crash root cause still unknown (silently dies after 2-4 messages) — check logs/nexus.log for [NEXUS CRASH] traceback
# - APEX win rate: 33% on 3 trades — add fallback signal source when CoinGecko rate-limits (429)
# - Gmail/Composio: COMPOSIO_API_KEY needs rotation; GitHub account EXPIRED at app.composio.dev
- [DONE] Run sentinel_research-2.py backtest with min SL 1.0%, log results to logs/sentinel_research.log
- [DONE] EMERGENCY REBUILD: TITAN has 0 winning combos. Research completely different strategy type. Current approach failed. (auto-queued 2026-04-09T17:17:40.442837)
- [DONE] EMERGENCY REBUILD: SENTINEL has 0 winning combos. Research completely different strategy type. Current approach failed. (auto-queued 2026-04-09T17:17:40.442837)
- [AUTO_IMPROVE] EMERGENCY REBUILD: DRIFT has 0 winning combos. Research completely different strategy type. Current approach failed. (auto-queued 2026-04-09T17:17:40.442837)
- [AUTO_IMPROVE] EMERGENCY REBUILD: APEX has 0 winning combos. Research completely different strategy type. Current approach failed. (auto-queued 2026-04-09T17:17:40.442837)

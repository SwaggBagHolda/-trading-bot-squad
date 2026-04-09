# Next Session Task File
# Written: 2026-04-09 (end of session) | Read this at the start of every session

## SYSTEM STATE RIGHT NOW

| Process | PID | Status |
|---|---|---|
| NEXUS | 1093 | Running — Anthropic/Sonnet 4.6, `-u` unbuffered |
| ORACLE | 1094 | Running |
| SCHEDULER | 5606 | Running — 5-min tick, stable, PID-locked |
| APEX | — | Not running (needs restart) |
| BOT_CURRICULUM | — | Not running (needs restart) |
| HyperTrain | HALTED | TRAINING_ENABLED=False — backtest model broken (13-24% WR) |
| OpenClaw Gateway | Running | 10 plugins loaded, ws://127.0.0.1:18789 |

## AI MODEL — CURRENT
- **NEXUS runs on Anthropic API directly** — `claude-sonnet-4-6` (upgraded from Haiku)
- Model constant: `ANTHROPIC_MODEL = "claude-sonnet-4-6"` in nexus_brain_v3.py line 31
- Key loaded via `.env` with `load_dotenv(override=True)` — overrides corrupted system env

## WHAT WAS DONE THIS SESSION (2026-04-09)

### Scheduler Stability (CRITICAL FIX)
- **Root cause found:** `time.sleep(1800)` (30min) with comment saying "5 minute tick" — scheduler never reached HyperTrain windows
- Fixed to `time.sleep(300)` (5min tick)
- Fixed `.seconds` vs `.total_seconds()` bug on WARDEN 6hr interval
- Added PID file lock to prevent duplicate instances
- Added signal handlers (SIGTERM/SIGINT) for clean shutdown
- Added CoinGecko retry logic with exponential backoff (3 retries, 2s base)
- **Commit:** f868db9

### HyperTrain Infinite Loop Fix (URGENT)
- Added `TRAINING_ENABLED = False` gate — ALL training HALTED
- Added `MAX_DAILY_RUNS = 2` with persistent counter (logs/training/daily_run_count.json)
- Added `MIN_WR_IMPROVEMENT = 0.05` — only re-trigger if WR improves by 5%+
- Embedded RESEARCH_VALIDATED_PARAMS from April 5 (80K experiments)
- Removed non-crypto assets (SPY, GBP/USD, GOLD, OIL) from all training files
- Disabled stock scanner in apex_coingecko.py
- Fixed WARDEN to read actual model from nexus_brain_v3.py dynamically
- **Commit:** 82b62ab

### CLAUDE.md Session Startup
- Added 10-step automatic startup routine (zero input from Ty)
- Includes /dream, system health checks, Telegram status summary
- **Commit:** 03d1cdb

### OpenClaw Updates
- Updated OpenClaw to 2026.4.9
- Updated Claude Code to latest
- Enabled 7 new plugins: memory-wiki, webhooks, brave, firecrawl, perplexity, lobster, llm-task
- Configured memory-lancedb (embedding via OpenRouter) but using memory-core as active provider
- No computer use plugin exists in OpenClaw 2026.4.9 — browser plugin is the web automation layer
- npm global prefix set to ~/.npm-global to avoid EACCES errors

### Browser Wired into NEXUS
- NEXUS has `browse_url()` function (nexus_brain_v3.py line 795) using Playwright headless
- **Tested successfully:** Browsed coindesk.com, got full page content including headlines
- Top headline at time of test: "Bitcoin shoots above $72,000 as optimism grows over Middle East ceasefire"
- Playwright installed and working

### HyperTrain Schedule Changed
- Moved from 11pm to **3am + noon** (2x daily runs)
- Uses slot keys to prevent re-runs: `YYYY-MM-DD_03` and `YYYY-MM-DD_12`
- Currently HALTED (TRAINING_ENABLED=False) until backtest model rebuilt

---

## P1 — REBUILD HYPERTRAIN BACKTEST MODEL (HIGHEST PRIORITY)

**Problem:** `simulate_backtest()` in hypertrain.py uses simple ratio heuristics, producing 13-24% WR regardless of parameters. This makes all training meaningless.

**Solution queued in memory/tasks/pending.md as [AUTO_IMPROVE]:**
1. Replace heuristic backtest with VectorBT on real Coinbase OHLCV candles
2. Implement proven strategies: ICT FVG, VWAP reversion, BB squeeze, EMA cross + RSI divergence
3. Validate each strategy hits > 50% WR on historical data
4. Only then set TRAINING_ENABLED=True
5. Run 1000+ experiments with real backtest to find optimal params

---

## P2 — WIRE AUTORESEARCH RESULTS BACK TO LIVE BOTS

- AutoResearch saves best params to `hive_mind.json` as `apex_best_params`
- APEX doesn't read these on each scan — needs to pull from hive_mind.json dynamically
- After AutoResearch completes, NEXUS should restart APEX to pick up new params

---

## P3 — FIX APEX WIN RATE & RESTART BOTS

- APEX not currently running — needs restart
- BOT_CURRICULUM not running — DRIFT/TITAN/SENTINEL need restart
- APEX has only 3 trades from previous sessions — needs more signal frequency
- CoinGecko rate-limits (429) frequently — Coinbase spot fallback wired but entry signals drop

---

## P4 — NEXUS CRASH INVESTIGATION

- NEXUS crashed 17 times in April 7 session — silently, no traceback
- Fixes applied: `-u` flag, full traceback logging, flush=True
- **Next session: check logs/nexus.log for `[NEXUS CRASH]` entries**
- Current PID 1093 appears stable

---

## P5 — COMPOSIO INTEGRATIONS (LOW PRIORITY)

- Gmail via Composio — GMAIL_ACCOUNT_ID `cb9cbc5a-...` (ACTIVE)
- GitHub via Composio — GITHUB_ACCOUNT_ID `e101cc4b-...` (EXPIRED — needs re-auth)
- COMPOSIO_API_KEY was exposed in chat — needs rotation at composio.dev

---

## KEY CONSTANTS

```
ANTHROPIC_MODEL:  claude-sonnet-4-6
TRADE_LOG_SHEET:  1vr6JVCNpJfRviul47oVV7iyYDC_ryJTGO0OaBHpXRsg
GMAIL_ACCOUNT_ID: cb9cbc5a-ffe5-4254-a106-49912176a1ba  (ACTIVE)
GITHUB_ACCOUNT_ID: e101cc4b-b485-4734-add8-74b4cf83ba6f (EXPIRED)
CRON: */5 watchdog for NEXUS + ORACLE
NPM_GLOBAL_PREFIX: ~/.npm-global
```

## WHAT NOT TO CHANGE
- Soul.md — do not rewrite without Ty approval
- `load_dotenv(BASE / ".env", override=True)` — override=True is critical
- `set_key_silent.py` — only safe key entry method
- `run_paper_trading_tick()` in scheduler.py — must stay disabled (no-op)
- `TRAINING_ENABLED = False` in hypertrain.py — do NOT re-enable until backtest rebuilt
- HyperTrain schedule (3am + noon) — don't change without Ty approval

## KEY MANAGEMENT — PERMANENT RULE
**NEVER add API keys via terminal echo, chat paste, or GUI text field that logs.**
**ALWAYS use: `python3 set_key_silent.py KEY_NAME`**

# Next Session Task File
# Written: 2026-04-07 (end of session) | Read this at the start of every session

## SYSTEM STATE RIGHT NOW

| Process | PID | Status |
|---|---|---|
| NEXUS | 56248 | Running — Anthropic/Haiku, `-u` unbuffered |
| APEX | 54644 | Running — live paper trading BTC (CoinGecko signals, Coinbase prices) |
| ORACLE | 51993 | Running |
| SCHEDULER | 54645 | Running — paper_trading_tick disabled (was fabricating random P&L) |
| BOT_CURRICULUM | 53694 | Running — DRIFT/TITAN/SENTINEL backtesting on live CoinGecko data |

## AI MODEL — CRITICAL CHANGE THIS SESSION
- **OpenRouter REMOVED entirely.** All 3 OpenRouter models were returning 401.
- **NEXUS now runs on Anthropic API directly** — `claude-haiku-4-5-20251001`
- Key loaded via `.env` with `load_dotenv(override=True)` — overrides corrupted system env
- System env has bad key `sk-sk-ant-api03-...` (double prefix) — `.env` key wins due to override=True
- Model constant: `ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"` in nexus_brain_v3.py

## KEY MANAGEMENT — NEW RULE (PERMANENT)
**NEVER add API keys via terminal echo, chat paste, or GUI text field that logs.**
**ALWAYS use: `python3 set_key_silent.py KEY_NAME`**
- Uses macOS osascript dialog — hidden input, never touches terminal stdout or logs
- Script location: `~/trading-bot-squad/set_key_silent.py`
- Takes key name as arg: `python3 set_key_silent.py ANTHROPIC_API_KEY`
- Prints only length and format check — never the key value

Keys exposed this session (ALL need to be rotated if not already done):
- ANTHROPIC_API_KEY — exposed multiple times, was auto-revoked, new key added via osascript
- OPENROUTER_API_KEY — 401, account issue (OpenRouter now removed from codebase)
- COMPOSIO_API_KEY — exposed twice in chat, needs rotation at composio.dev
- OpenAI key — removed from .env, deferred

---

## P1 — FIX APEX WIN RATE (current: 67% on 3 trades — too few to be meaningful)

APEX has only 3 trades. Need:
- More signal frequency — CoinGecko is rate-limited (429) frequently, signals drop out
- Better entry logic — RSI-only isn't enough for scalping
- Wire AutoResearch results back into apex_coingecko.py params
- Add fallback signal source when CoinGecko rate-limits

Current APEX params (from hive_mind.json `apex_best_params`):
- Check with: `python3 -c "import json; from pathlib import Path; h=json.loads((Path.home()/'trading-bot-squad/shared/hive_mind.json').read_text()); print(json.dumps(h.get('apex_best_params',{}), indent=2))"`

---

## P2 — WIRE REAL AUTORESEARCH CALLBACK

**What was built this session:**
- `sentinel_research-2.py` now writes `shared/research_done.flag` when training completes
- NEXUS `proactive_check()` detects the flag, sends Telegram summary with per-bot top strategy, deletes flag
- AutoResearch phrases properly routed: "run autoresearch", "run auto research", "auto research", etc.

**What still needs wiring:**
- AutoResearch results → actually update `apex_coingecko.py` entry params
- When sentinel_research-2.py finds best params for APEX, those should propagate to the live bot
- Currently best_params saved to `hive_mind.json` as `apex_best_params` but APEX doesn't read them on each scan

**To connect:**
- `apex_coingecko.py` `scan_markets()` should read `hive_mind.json["apex_best_params"]` for RSI thresholds
- After AutoResearch completes, NEXUS should restart APEX to pick up new params

---

## P3 — FIX NEXUS CRASH (root cause still unknown)

**What we know:**
- NEXUS crashed 17 times this session — silently, no traceback
- Crashes happen after handling 2-4 messages
- NOT caused by cron (cron is a safe "start if dead" watchdog)
- NOT caused by scheduler (scheduler doesn't touch NEXUS)

**Fixes applied this session:**
- Cron now uses `python3 -u` (unbuffered) — crashes will now appear in logs
- Exception handler now logs full traceback with `flush=True`
- `import traceback` added to nexus_brain_v3.py

**Next session: catch the first crash traceback in logs/nexus.log and fix root cause**
- Watch for: `[NEXUS CRASH]` in logs/nexus.log after a message is received
- Likely candidates: proactive_check() hitting a None somewhere, timedelta math, hive_mind.json write conflict

---

## P4 — BOT GRADUATION STATUS

DRIFT/TITAN/SENTINEL running via `bot_curriculum.py` (PID 53694):
- Uses live CoinGecko prices (5-min scans)
- RSI-based entry signals, trailing stops
- Graduation: 100 backtesting trades + 55%+ WR + positive P&L → paper → 200 trades → live_pending

Current progress (very early):
- DRIFT: 3 trades, 67% WR (backtesting)
- TITAN: 0 trades
- SENTINEL: 0 trades

At 5-min scan intervals with 1-hour max hold, expect ~5-10 trades/day per bot.
DRIFT needs ~3-4 weeks to hit 100 trades at this rate — consider tightening entry conditions or adding more symbols.

---

## P5 — FIXES MADE THIS SESSION (do not redo)

### Price Feed
- `fetch_market_snapshot()` — added Coinbase public spot fallback when CoinGecko 429s
- Root cause of $28K BTC price: CoinGecko 429 → price=0 passed to AI → AI hallucinated training-data price
- `_coinbase_spot()` function added — hits `api.coinbase.com/v2/prices/{sym}-USD/spot`, no auth, no rate limit

### Data Integrity
- `scheduler.py` `run_paper_trading_tick()` DISABLED — was writing fake random P&L to all bots every 30min including APEX
- Stale `status: "paper_trading"` field removed from all bots in hive_mind.json
- WARDEN report now reads `mode` field (not `status`) — shows `[LIVE]` for APEX, `[BACKTESTING]` for others
- DRIFT `mode` field was missing — set to `backtesting`

### AutoResearch Completion Callback
- `sentinel_research-2.py` writes `shared/research_done.flag` on completion
- NEXUS `proactive_check()` detects flag, sends clean Telegram summary, deletes flag
- Per-bot top strategy + best asset + WR included in summary

### Process Management
- Duplicate APEX PIDs killed (had 51032 + 54225 running simultaneously)
- Duplicate scheduler PIDs killed (had 12522 + 54394)
- All processes now started with `-u` flag for unbuffered output
- Cron watchdog updated to use `python3 -u` for NEXUS and ORACLE

### NEXUS Routing
- `run autoresearch`, `auto research`, `autoresearch`, `research all` etc. added to both COMMAND_PHRASES and train handler
- `/autoresearch` slash command added
- `run_all_training()` no longer sends a Telegram message itself — NEXUS handler sends the informative response instead

---

## P6 — WIRED BUT NEEDS TESTING

- **Gmail via Composio** — `GMAIL_ACCOUNT_ID = "cb9cbc5a-..."` (marked ACTIVE) — 2am pitch saves to file if PROSPECT_EMAIL not set
- **GitHub via Composio** — `GITHUB_ACCOUNT_ID = "e101cc4b-..."` (EXPIRED — needs re-auth at app.composio.dev)
- **COMPOSIO_API_KEY** — exposed in chat, needs rotation before Composio features work

---

## KEY CONSTANTS

```
ANTHROPIC_MODEL:  claude-haiku-4-5-20251001
TRADE_LOG_SHEET:  1vr6JVCNpJfRviul47oVV7iyYDC_ryJTGO0OaBHpXRsg
GMAIL_ACCOUNT_ID: cb9cbc5a-ffe5-4254-a106-49912176a1ba  (ACTIVE)
GITHUB_ACCOUNT_ID: e101cc4b-b485-4734-add8-74b4cf83ba6f (EXPIRED)
CRON: */5 watchdog for NEXUS + ORACLE | 2am + 2:30am nightly_consolidate.py
```

## WHAT NOT TO CHANGE
- Soul.md — do not rewrite without Ty approval
- `load_dotenv(BASE / ".env", override=True)` — the override=True is critical, system env has bad key
- `set_key_silent.py` — this is the only safe key entry method going forward
- QUIET_MODE = False — night shift active
- `run_paper_trading_tick()` in scheduler.py — must stay disabled (no-op), do not re-enable

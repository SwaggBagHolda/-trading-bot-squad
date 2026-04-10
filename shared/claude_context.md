CLAUDE OPERATING MODE: Think like a polymath CTO who is also a professor, seer, and renaissance strategist. You see 10 moves ahead. You assess before acting. You never suggest what is already done. You are the smartest person in the room and you prove it through results not words.

# Claude Session Briefing
# Source of truth: AGENTS.md + CLAUDE.md
# Last regenerated: 2026-04-10
#
# WEBHOOK BRIDGE:
#   Current URL: https://thing-calendar-era-guided.trycloudflare.com
#   Read URL from: shared/tunnel_url.txt (auto-updated on cloudflared restart)
#   Endpoints: /briefing, /health, /events
#   Local fallback: http://localhost:7777/briefing
#   Disk fallback: this file

---

## THE OWNER — Ty

- **Location:** Brandon, Florida
- **Bills:** $15,000/month — this is the floor to beat
- **Squad target:** $100,000/month combined ($25K per bot)
- **Deadline:** 30 days to first revenue. Clock is running.
- **End goal:** Quit the job. Fully automated income. Telegram reports only.
- **Exchange:** Coinbase (funds deposited)
- **Technical level:** Not a developer. Gives direction, Codey builds.
- **Communication:** Telegram only. No Slack, no email, no dashboards.
- **Decision style:** Fast. "Just do it" unless it costs money or touches live funds.
- **Risk tolerance:** Paper trade first, prove it works, then go live small.

---

## AGENT ROSTER — Correct Names

```
                      ┌──────┐
                      │  Ty  │  Owner — final authority
                      └──┬───┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐  ┌───▼───┐  ┌──▼───┐
         │ Claude │  │ NEXUS │  │Codey │
         │  CTO   │  │  CEO  │  │Build │
         └────────┘  └───┬───┘  └──────┘
                         │
        ┌───────┬────────┼────────┬─────────┐
        │       │        │        │         │
      APEX   DRIFT    TITAN   SENTINEL   ORACLE
      scalp  swing    pos     polymkt    research
                         │
                  ┌──────┴──────┐
                  │             │
                SHANGO         BRICK
                watchdog      heartbeat
```

### Chain of Command
1. **Ty** — Owner. Approves live trading, sets priorities, receives reports.
2. **Claude** — CTO/Architect. Designs systems, plans migrations, strategic decisions.
3. **NEXUS** — CEO / Head Coach. Runs 24/7 on **Claude Opus 4.6**. Manages all bots autonomously.
4. **Codey** — Builder. Writes every line of code. Fixes every bug.
5. **ORACLE** — Silent researcher. Finds alpha. Writes files only, never talks to Ty.
6. **SHANGO** — Watchdog (formerly ZEUS). Kill switches, daily reports, oversight.
7. **BRICK** — Heartbeat monitor (formerly WARDEN). 15-min process checks, 6-hour status.
8. **Bots** — Execute trades. Report stats. Compete to graduate to live.

---

## NEXUS — CEO / Head Coach

- **Model:** Claude Opus 4.6 (`claude-opus-4-6`) — upgraded from Sonnet for strategic reasoning
- **Files:** `nexus_brain_v3.py` (1900+ lines), `nexus_agent.py` (Agent SDK Phase 1)
- **Mode:** SILENT_MODE permanent. Only sends: P&L events, broken systems, upgrade complete, HyperTrain final, direct replies to Ty.
- **Tools:** Coinbase API, Polymarket API, Telegram, hive_mind.json (file-locked), OpenRouter AI, AutoResearch, HyperTrain
- **Autonomous powers:** Write parameter overrides, stop bots on 0% WR, loosen thresholds, switch strategies, promote/bench bots, run AutoResearch
- **Live trade guard:** Never adjusts APEX params mid-trade. Queues changes to `shared/param_queue.json`, drains on trade close.

### Scheduled Jobs
| Time | Job |
|------|-----|
| 1:00 AM | Self-improvement — review chat logs, write fixes |
| 3:00 AM | HyperTrain cycle 1 |
| 6:00 AM | Morning report — 5 priorities + Polymarket scan |
| 12:00 PM | HyperTrain cycle 2 |
| Hourly | Bot health check, trade count audit, briefing push to bridge |

---

## TRADING BOTS — Correct Roster

### APEX — Scalper
| Field | Value |
|-------|-------|
| **Target** | $25,000/month |
| **Style** | Scalping — 50–200 trades/day |
| **Timeframe** | 1m / 5m candles |
| **Signals** | EMA crossover + RSI + FVG (Fair Value Gap) |
| **File** | `apex_coingecko.py` |
| **Assets** | Dynamic — scans CoinGecko top 20 movers, picks highest volatility |
| **Status** | Paper trading, confidence scoring active |

### DRIFT — Swing Trader
| Field | Value |
|-------|-------|
| **Target** | $25,000/month |
| **Style** | Swing — 1–2 day holds |
| **Timeframe** | 15m / 1h candles |
| **Signals** | MACD + RSI confluence, Bollinger Band squeeze breakouts |
| **File** | `drift_trader.py` |
| **Status** | Paper trading |

### TITAN — Position Trader
| Field | Value |
|-------|-------|
| **Target** | $25,000/month |
| **Style** | Position — 1–3 week holds |
| **Timeframe** | 4h / 1d candles |
| **Signals** | BTC dominance cycles, macro correlations (DXY, yields) |
| **File** | `titan_trader.py` |
| **Status** | Paper trading |

### SENTINEL — Polymarket Arbitrage **(NO FTMO)**
| Field | Value |
|-------|-------|
| **Target** | $25,000/month |
| **Style** | Prediction market positions — directional + arbitrage |
| **Signals** | Near-strike crypto markets, conviction scoring |
| **File** | `sentinel_polymarket.py` |
| **Resolution** | TP 15%, SL -10%, max hold 48h |
| **Status** | Paper trading, disk persistence active |
| **Note** | SENTINEL is **Polymarket arb only**. Not a prop firm bot. Not FTMO. |

### ORACLE — Autonomous Researcher
- **Platform:** OpenClaw agent (always-on, headless)
- **Files:** `~/.openclaw/workspace/SOUL.md`, `TOOLS.md`, `BOOTSTRAP.md`
- **Tools:** DuckDuckGo, Playwright browser, QMD (BM25 + vector search over 51 docs), CoinGecko, Polymarket, Coinbase public API
- **Output:** Writes to `memory/research/` — NEXUS and scheduler.py read automatically
- **Rule:** Free APIs only. Every finding needs data + source URL + confidence (HIGH/MED/LOW). Silent — no Telegram.

---

## THE 30-DAY DEADLINE

Ty has 30 days to prove this squad can pay his $15K/month bills. Every session must move the needle on revenue, not infrastructure.

### What matters in the next 30 days
1. **Get APEX trading volume up** — needs 50+ trades/day to compound
2. **Coinbase API keys** — current keys 401. Live trading blocked until Ty regenerates with Trade+View permissions.
3. **Graduate first bot to live** — 100+ trades, >70% WR, >1.0 Sharpe, <5% max DD (algorithms, not humans — higher bar)
4. **HyperTrain optimizing nightly** — 10K experiments, max 2 runs/day
5. **DRIFT and TITAN online and trading** — both have schema bugs blocking trades

### What does NOT matter in the next 30 days
- New features
- Refactors
- Documentation
- Anything that doesn't directly produce trades or fix broken trading

---

## CURRENT PRIORITIES (in order)

1. **Coinbase API keys** — Ty needs to generate new keys with Trade+View permissions (master_checklist #23). Blocks all live trading.
2. **DRIFT sqlite schema fix** — schema mismatch crashing bot (master_checklist #46)
3. **TITAN sqlite schema fix** — same issue (master_checklist #47)
4. **Implement ETH/USD mean_reversion 4h into DRIFT** (master_checklist #48)
5. **Verify all bots logging to hive_mind.json correctly** — confidence scores updating
6. **HyperTrain results validation** — confirm winning strategies are being applied to live params

## BLOCKERS

- **Coinbase 401** — can't go live until Ty generates new API keys
- **No sudo** — can't install Homebrew/system packages
- **claude-agent-sdk** — doesn't exist on PyPI, using anthropic SDK tool_use instead
- **agent-browser plugin** — blocked by OpenClaw, using custom Playwright
- **DRIFT/TITAN schema** — sqlite mismatches block trade execution

---

## SYSTEM STATUS (snapshot — verify with `ps aux` at session start)

| Process | Status | Notes |
|---------|--------|-------|
| NEXUS | Running (PID 5092) | Opus 4.6, SILENT_MODE, live trade guard active |
| ORACLE | Running | Listener bridge |
| SCHEDULER | Running (PID 4930) | 5-min tick, PID-locked, auto-starts bridge + tunnel |
| APEX | Running (PID 5496) | apex_coingecko.py, scanning top movers, silent_mode wrapped |
| SENTINEL | Running (PID 124) | sentinel_polymarket.py, scanning 103 markets, 17 open positions |
| HyperTrain | Re-enabled | TRAINING_ENABLED=True, 3am+noon, MAX_DAILY_RUNS=2 |
| Webhook bridge | Running | localhost:7777 + cloudflared tunnel |
| OpenClaw | Running | QMD skill installed, 51 docs indexed |

---

## NON-NEGOTIABLE RULES (from CLAUDE.md)

1. **Read first** — CLAUDE.md, claude_briefing.md, next_session.md before any action
2. **Research before building** — Glob/Grep for existing implementations first
3. **Free models only** — OpenRouter free tier. Never paid Anthropic unless Ty approves.
4. **Foundation before features (Rule #14, UNBREAKABLE)** — No new features on broken foundations. Ever.
5. **AutoResearch before strategy changes (Rule #9)** — No exceptions. No quick tweaks.
6. **Dynamic asset scanning (Rule #10)** — No bot locked to fixed assets. Scan all markets every 4h.
7. **Bidirectional trading (Rule #11)** — Every bot trades both directions.
8. **Silent Telegram** — Only money events, broken systems, upgrades complete, HyperTrain finals, direct replies.
9. **Save progress** — Update `memory/daily/YYYY-MM-DD.md` before ending any session.
10. **Single Telegram summary when done** — Not mid-session updates.

---

## KEY FILES

- `CLAUDE.md` — master rules, read first every session
- `AGENTS.md` — agent registry, source of truth for roles and tools
- `memory/tasks/master_checklist.md` — task tracker (37+ items)
- `memory/tasks/next_session.md` — priorities and system state
- `memory/tasks/pending.md` — NEXUS auto-queued tasks
- `memory/research/` — ORACLE research outputs
- `silent_mode.py` — single source of truth for Telegram filtering
- `nexus_agent.py` — Agent SDK Phase 1 tools (restart_bot, check_hive, adjust_threshold, force_close_trade, run_hypertrain)
- `webhook_bridge.py` — localhost:7777 cross-session bridge
- `shared/hive_mind.json` — file-locked shared state
- `shared/param_queue.json` — queued APEX param changes (drained on trade close)
- `shared/tunnel_url.txt` — current cloudflared public URL

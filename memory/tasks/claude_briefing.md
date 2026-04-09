CLAUDE OPERATING MODE: Think like a polymath CTO who is also a professor, seer, and renaissance strategist. You see 10 moves ahead. You assess before acting. You never suggest what is already done. You are the smartest person in the room and you prove it through results not words.

# Claude Session Briefing
# Auto-updated by NEXUS after every major action
# Read this at the START of every new session
# Last updated: 2026-04-09 15:45

## SYSTEM STATUS

| Process | Status | Notes |
|---------|--------|-------|
| NEXUS | Running (PID 1093) | Anthropic Sonnet 4.6, stable |
| ORACLE | Running (PID 1094) | Message bridge |
| SCHEDULER | Running (PID 5606) | 5-min tick, PID-locked |
| APEX | Running | Scalping ZEC/TAO/20 movers, adaptive stops |
| SENTINEL | Stopped | Polymarket arb, needs manual restart |
| HyperTrain | Re-enabled | TRAINING_ENABLED=True, 3am+noon schedule |
| OpenClaw | Running (PID 97823) | 2026.4.9, QMD skill installed |
| Agent SDK | Phase 1 done | nexus_agent.py with 5 tools |

## DONE TODAY (2026-04-09)

1. 5 foundation fixes: confidence write-back, health checks, file locking, SENTINEL resolution, max_tokens
2. APEX restarted with new code — scanning 20 movers, adaptive stops, confidence scoring
3. SENTINEL disk persistence + duplicate position guard
4. HyperTrain re-enabled after backtest validation (real Coinbase candles)
5. Agent SDK Phase 1: nexus_agent.py with restart_bot, check_hive, adjust_threshold, force_close_trade, run_hypertrain
6. QMD installed + 51 docs indexed (35 memory + 16 openclaw)
7. Agent browser: custom Playwright skill (official plugin blocked)
8. CLAUDE.md rule 14: foundation before features

## NEXT PRIORITIES (in order)

1. **Coinbase API keys** — current keys return 401. Ty needs to generate new keys with Trade+View permissions (task #23)
2. **RESEARCH agent** — configure OpenClaw autonomous researcher
3. **Agent SDK Phase 2** — MCP integration (Telegram, filesystem, Coinbase)
4. **P4: NEXUS crash investigation** — check logs/nexus.log for [NEXUS CRASH] entries
5. **SENTINEL restart** — process stopped, needs manual restart

## BLOCKERS

- **Coinbase 401** — can't go live until Ty generates new API keys
- **No sudo** — can't install Homebrew/system packages
- **claude-agent-sdk** — doesn't exist on PyPI, using anthropic SDK tool_use instead
- **agent-browser plugin** — blocked by OpenClaw for dangerous code, using custom Playwright

## KEY FILES

- `CLAUDE.md` — master rules, read first every session
- `memory/tasks/master_checklist.md` — 37 tasks tracked
- `memory/tasks/next_session.md` — priorities and system state
- `memory/tasks/agent_sdk_migration.md` — 4-phase migration plan
- `nexus_agent.py` — Agent SDK Phase 1 tools
- `Soul.md` — NEXUS personality and mission

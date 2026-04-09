# Master Checklist — Trading Bot Squad
# Auto-populated by NEXUS | Verified by Claude | Updated: 2026-04-09
# Format: | Task | Owner | Status | Added | Completed |

## Legend
- **Owner:** NEXUS = autonomous action, Codey = Claude Code, Ty = manual
- **Status:** pending | in_progress | done | verified | blocked

---

## 2026-04-09 — Session Tasks

| # | Task | Owner | Status | Added | Completed |
|---|------|-------|--------|-------|-----------|
| 1 | Fix HyperTrain — rebuild real backtest engine with Coinbase OHLCV candles | Codey | done | 2026-04-09 | 2026-04-09 |
| 2 | Wire ElevenLabs voice into NEXUS Telegram replies | Codey | done | 2026-04-09 | 2026-04-09 |
| 3 | Fix Coinbase 401 auth — move keys to .env | Codey | done | 2026-04-09 | 2026-04-09 |
| 4 | Research proven crypto strategies from real sources (QuantifiedStrategies, ICT, TradingView) | Codey | done | 2026-04-09 | 2026-04-09 |
| 5 | Build /proof Telegram command | Codey | done | 2026-04-09 | 2026-04-09 |
| 6 | Build NEXUS↔Claude Code JSON bridge | Codey | done | 2026-04-09 | 2026-04-09 |
| 7 | Wire Playwright browser + Mac automation into NEXUS | Codey | done | 2026-04-09 | 2026-04-09 |
| 8 | Add Felix nightly self-improvement loop (1am chat review) | Codey | done | 2026-04-09 | 2026-04-09 |
| 9 | Add 6am morning 5-priority report | Codey | done | 2026-04-09 | 2026-04-09 |
| 10 | Pivot SENTINEL to Polymarket arbitrage bot | Codey | done | 2026-04-09 | 2026-04-09 |
| 11 | Wire Polymarket into NEXUS morning report | Codey | done | 2026-04-09 | 2026-04-09 |
| 12 | APEX real scalper — lower thresholds, 5s poll, 10s cooldown, 20 CoinGecko movers | Codey | done | 2026-04-09 | 2026-04-09 |
| 13 | APEX idle auto-lower threshold (halves every 10min, floor 0.001%) | Codey | done | 2026-04-09 | 2026-04-09 |
| 14 | NEXUS noise reduction — QUIET_MODE, only trades/breaks/money | Codey | done | 2026-04-09 | 2026-04-09 |
| 15 | NEXUS autonomous consequences — stop bot on 0 WR, auto-loosen, auto-switch strategy | Codey | done | 2026-04-09 | 2026-04-09 |
| 16 | NEXUS Phase 2 autonomy — write hive_mind params, APEX reads overrides | Codey | done | 2026-04-09 | 2026-04-09 |
| 17 | Soul.md — add noise filter rule + Phase 2 autonomy section | Codey | done | 2026-04-09 | 2026-04-09 |
| 18 | Build master checklist system + /checklist command | Codey | done | 2026-04-09 | 2026-04-09 |
| 19 | APEX trade count in WARDEN hourly reports + <5/hr auto-investigate | Codey | done | 2026-04-09 | 2026-04-09 |
| 20a | Tail APEX logs and confirm trades firing | Codey | done | 2026-04-09 | 2026-04-09 |
| 20 | APEX target 50-200 trades/day | Codey | done | 2026-04-09 | 2026-04-09 |
| 21 | Install claude-mem plugin for OpenClaw | Codey | blocked | 2026-04-09 | — |
| 22 | Ty set ELEVENLABS_API_KEY in .env | Ty | pending | 2026-04-09 | — |
| 23 | Ty set COINBASE_API_KEY_NAME + COINBASE_PRIVATE_KEY in .env | Ty | pending | 2026-04-09 | — |

---

## Ongoing / Recurring

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| R1 | Nightly self-improvement review (1am) | NEXUS | active | Reads chat JSONL, writes fixes to self_improve.md |
| R2 | Morning 5-priority report (6am) | NEXUS | active | Includes Polymarket scan |
| R3 | AutoResearch/HyperTrain (3am + noon) | NEXUS | active | TRAINING_ENABLED=True, real backtests |
| R4 | APEX hourly trade count check | NEXUS | active | < 5/hr triggers investigation |
| R5 | Phase 2 parameter tuning | NEXUS | active | Writes overrides to hive_mind.json |

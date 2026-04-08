# SYSTEM.md — Trading Bot Squad Shared Truth
# Last updated: 2026-04-04
# READ THIS FIRST every session (Claude Code + NEXUS both read this)

## CURRENT PHASE
Phase 1 — Hypertraining / Building

## OWNER
- Name: Ty
- Location: Brandon, Florida
- Exchange: Coinbase
- Communication: Telegram only
- Goal: Fully automated, hands-off, clockwork operation

## THE SQUAD

### 🔴 APEX — Scalper
- File: memory/bots/APEX.md
- Style: High-frequency, in/out fast, aggressive TP
- Target: $10K/mo

### 📈 DRIFT — Day Trader
- File: memory/bots/DRIFT.md
- Style: Intraday, rides momentum, closes EOD
- Target: $10K/mo

### 🔵 NOVA — Swing Trader
- File: memory/bots/NOVA.md
- Style: 1-3 day holds, trend following
- Target: $10K/mo

### 🟢 SENTINEL — Prop Firm Specialist
- File: memory/bots/SENTINEL.md
- Style: FTMO-compliant, disciplined, cloneable
- Target: $200K funded → $7,200/mo at 90% split

### ⚡ ZEUS — Watchdog/Overseer
- File: memory/bots/ZEUS.md
- Role: Kill switches, rate limit monitor, daily reports, API credit watchdog
- Reports to Ty at 6pm EST via Telegram daily

## OPERATION PRINCIPLES
- Free or near-free until profitable
- Token usage + API credits kept to minimum
- ZEUS monitors all credit burn
- No live trading until hypertraining + curriculum passed
- ZEUS signs off before any bot goes live

## CURRICULUM (replaces 30-day paper period)
- Hypertraining via AutoResearch (Karpathy-style)
- Thousands of simulated trades per hour
- Must achieve: 10% profit, Sharpe > 1.0, no single day > 4% loss, 15/30 profitable days
- Time-based waiting ELIMINATED — performance gates only

## AGENT COMMUNICATION PROTOCOL
- NEXUS (OpenClaw) = orchestrator, talks to Ty via Telegram
- Claude Code = builder, spawned by NEXUS for coding tasks
- Shared truth = these memory files
- Claude Code reads SYSTEM.md + relevant bot files at session start
- NEXUS reads memory files to stay current
- All decisions, lessons, changes written to files immediately

## PROP FIRM MATH
- 10% challenge gate (one-time)
- 3-5% monthly target on funded account
- $200K funded × 4% × 90% split = $7,200/mo
- 3 accounts = $21,600/mo
- FTMO auto-scales 25% every 4 profitable months

## STACK
OpenClaw + Claude Code + Telegram + Coinbase + AutoResearch
Free-first always.

# CLAUDE.md — Trading Bot Squad Master Brain
# Version 1.1 | Created: April 2026 | Updated: 2026-04-06
# Read this file at the start of EVERY session.

## PERMANENT SESSION RULES (non-negotiable)

1. **Read first.** Always read CLAUDE.md AND memory/tasks/next_session.md before doing anything else.
2. **Research before building.** Check if the file/function/feature already exists before writing new code.
3. **Single-line commands only.** No multiline shell strings. Use \n escaping in .env. No heredocs in .env.
4. **Free models only.** Never use paid API calls. OpenRouter free tier always. Never hit Anthropic direct unless OPENROUTER_API_KEY is exhausted and Ty explicitly approves.
5. **Check before building.** Glob/Grep for existing implementations first. Don't duplicate what's already there.
6. **Save progress before stopping.** Write a summary to memory/daily/YYYY-MM-DD.md before ending any session.
7. **One Telegram summary when done.** Send Ty a single summary message when a multi-task session is complete. Not updates mid-session.
8. **Credit guard.** If OpenRouter credits drop below $1, stop all non-essential AI calls immediately and alert Ty via Telegram.
9. **AutoResearch before strategy changes.** Before adjusting any bot strategy, entry/exit logic, stop sizes, or signal parameters — NEXUS must run AutoResearch first. No strategy changes without research data backing them. This is a hard rule, no exceptions.

## WHO I AM
Claude = Orchestrator/Strategist only. NOT a trading bot.
Communicate with owner via Telegram (Felix/Nat Eliason model).

## OWNER
- Location: Brandon, Florida
- Exchange: Coinable (owner has funds there)
- Goal: Fully automated, hands-off, clockwork operation
- Communication: Telegram only (like Nat & Felix)

## THE 4 BOTS
- APEX/VOLT = Scalper, hourly returns, $10K/mo target
- NOVA/DRIFT = Swing trader, 1-2 day holds, $10K/mo target  
- TITAN/ANCHOR = Position trader, 1-3 weeks, $10K/mo target
- SENTINEL/ATLAS = Prop firm specialist, FTMO focus, cloneable

## BOSS BOT
- ZEUS = Overseer, checks all bots, kill switches, daily reports

## STACK (free-first)
Paperclip + OpenClaw + Claude Code + Telegram + Coinable + AutoResearch

## PROP FIRM MATH
- 10% = one-time challenge gate, NOT monthly target
- Monthly goal on funded account = 3-5% (sustainable)
- $200K funded at 4% = $7,200/mo to you at 90% split
- Scale to 3 accounts = $21,600/mo passive
- FTMO scales 25% every 4 profitable months automatically

## AUTORESEARCH/HYPERTRAINING
- Runs 100 strategy experiments nightly while owner sleeps
- Editable asset: strategy.py
- Metric: composite P&L + Sharpe ratio - drawdown penalty
- Keeps improvements, discards failures, repeats forever

## MEMORY SYSTEM (3-Layer Felix Model)
- Layer 1: Knowledge graph (PARA system ~/trading-bot-squad/memory/)
- Layer 2: Daily notes (dated markdown, nightly consolidation)
- Layer 3: Tacit knowledge (rules, preferences, lessons learned)

## MEMORY FILES (READ THESE)
- memory/SYSTEM.md — shared truth, current phase, all agents read this
- memory/SELF_IMPROVEMENT.md — how every bot/agent learns and evolves
- memory/CLAUDE_CODE_HANDOFF.md — Claude Code reads this every session
- memory/bots/APEX.md — scalper identity + lessons
- memory/bots/DRIFT.md — day trader identity + lessons
- memory/bots/NOVA.md — swing trader identity + lessons
- memory/bots/SENTINEL.md — prop firm bot identity + lessons
- memory/bots/ZEUS.md — watchdog identity + rules
- memory/daily/YYYY-MM-DD.md — daily logs
- memory/tasks/ — task queue between NEXUS and Claude Code
- memory/research/bugs.md — bug log, never repeat

## CURRICULUM (must pass before going live)
- Hypertraining via AutoResearch (Karpathy-style) — NOT time-based
- Thousands of simulated trades per hour
- 10% profit (performance gate, not calendar gate)
- No single day loss exceeding 4%
- Sharpe ratio above 1.0
- Profitable on 15 of 30 equivalent sessions minimum
- ZEUS approval required
- 30-DAY CALENDAR WAIT ELIMINATED

## TRADE LOG WORKAROUND
- Coinable API webhook to Python script to SQLite
- Telegram bot reports every trade immediately
- Google Sheets auto-populated via gspread
- ZEUS daily summary at 6pm EST to Telegram

## FELIX LESSONS APPLIED
✅ 3-layer memory set up Day 1
✅ Multi-threaded Telegram (1 channel per bot)
✅ Heartbeat monitor + cron jobs
✅ Isolated API keys per bot
✅ Authenticated input vs info channels
✅ Paper first, curriculum, then live
✅ ZEUS oversight (Felix didn't have this)

## SESSION STARTUP
1. Re-read this CLAUDE.md
2. Read memory/SYSTEM.md
3. Read memory/CLAUDE_CODE_HANDOFF.md
4. Read memory/NEXUS_TO_ORACLE.md — messages from NEXUS
5. Check memory/tasks/ for pending tasks from NEXUS
6. Ask owner: what is the priority today?
7. Never start coding without confirming phase
8. At END of session: update memory/ORACLE_TO_NEXUS.md with decisions made

## GRADUATION PATH
Phase 1: All bots paper trade on Coinable
Phase 2: Pass curriculum, go live small on Coinable
Phase 3: SENTINEL passes FTMO $10K challenge
Phase 4: Scale SENTINEL to $100K FTMO account
Phase 5: Clone SENTINEL, sell to other traders
Phase 6: Full autopilot, ZEUS oversees, owner gets Telegram reports

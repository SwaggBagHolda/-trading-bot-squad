# CLAUDE_CODE_HANDOFF.md — For Claude Code
# READ THIS at the start of every coding session.
# Written by NEXUS (OpenClaw). This is your briefing.

## WHO YOU ARE IN THIS SYSTEM
You are the builder. NEXUS is the orchestrator.
Ty is the owner. You report to NEXUS. NEXUS reports to Ty.

## WHAT TO READ FIRST (every session)
1. This file
2. memory/SYSTEM.md — current phase, squad overview, principles
3. memory/SELF_IMPROVEMENT.md — how we learn and evolve
4. The specific bot file you're working on (memory/bots/[BOT].md)

## COMMUNICATION PROTOCOL
- NEXUS writes tasks to this file or to memory/tasks/[TASK].md
- You execute, then write results to memory/tasks/[TASK]_result.md
- Log all decisions, bugs, and lessons to the relevant bot file
- Never assume context — if the task is unclear, write your question to memory/tasks/[TASK]_question.md

## GOLDEN RULES
1. **Free first** — use free APIs, free data sources, free tools. Only paid when unavoidable.
2. **Token efficient** — keep prompts lean, avoid unnecessary context loading
3. **Write to files** — mental notes don't survive sessions. Log everything.
4. **Self-improve** — after every build, write what worked and what didn't to the bot's memory file
5. **ZEUS first** — any code touching live trading must have ZEUS kill switch logic built in
6. **Never go live without approval** — paper/hypertraining only until NEXUS + Ty sign off

## CURRENT PHASE
Phase 1 — Building & Hypertraining
See memory/SYSTEM.md for details.

## TASK QUEUE
Check memory/tasks/ for pending tasks from NEXUS.
If empty, check memory/SYSTEM.md for current phase priorities.

## BUG LOG
All bugs go in memory/research/bugs.md. Don't repeat them.

## STACK
- Exchange: Coinbase (API keys in .env)
- Language: Python
- Framework: TBD per bot
- AutoResearch: strategy.py (Karpathy-style hypertraining)
- Logging: SQLite → Google Sheets via gspread
- Alerts: Telegram bot

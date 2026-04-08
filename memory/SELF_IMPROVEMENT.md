# SELF_IMPROVEMENT.md — The Learning Engine
# Every bot, every agent, every system reads this.
# We don't just trade. We evolve.

## CORE PRINCIPLE
This system gets better every single day. No exceptions.
Every loss is a lesson. Every win is a pattern to replicate.
Stagnation is failure. Improvement is survival.

## THE LEARNING LOOP (All Bots)

### After Every Trade:
1. Log the trade (symbol, entry, exit, P&L, reason)
2. Ask: "Why did this win/lose?"
3. Write one lesson to memory/bots/[BOT_NAME].md under ## Lessons
4. If a pattern repeats 3+ times → promote it to strategy rules

### Daily (ZEUS runs this at midnight):
1. Review all bot trade logs
2. Identify top 3 winning patterns, top 3 losing patterns
3. Write to memory/daily/YYYY-MM-DD.md
4. Flag any strategy that's underperforming for AutoResearch attention
5. Prune outdated rules that no longer apply

### Weekly:
1. Consolidate daily notes → update each bot's SOUL.md
2. Run AutoResearch on worst-performing strategy
3. Update SYSTEM.md if phase or goals changed
4. Report to Ty via Telegram: wins, losses, what we learned, what changed

## AUTOAESEARCH PROTOCOL (Karpathy-Style Hypertraining)
- Runs nightly (or on-demand)
- 100+ strategy experiments per run
- Each experiment: simulate thousands of trades in minutes
- Metric: composite P&L + Sharpe ratio - drawdown penalty
- Winners → promoted to strategy.py
- Losers → logged in memory/research/ with reason for failure
- Nothing is deleted — everything is learned from

## AGENT SELF-IMPROVEMENT (NEXUS + Claude Code)

### NEXUS improves by:
- Tracking which prompts/instructions led to good outcomes
- Updating CLAUDE.md when better approaches are discovered
- Logging coordination failures and fixing the process
- Flagging when token usage is spiking and finding leaner alternatives

### Claude Code improves by:
- Reading bot performance data before writing new code
- Reviewing previous implementations before starting fresh
- Writing post-build notes: what worked, what didn't, what to try next
- Never repeating the same bug twice (log all bugs in memory/research/bugs.md)

## GUARDRAILS ON SELF-IMPROVEMENT
- No strategy goes live without ZEUS approval
- Improvements to live strategies require Ty notification first
- AutoResearch only modifies strategy.py — never live trade config
- Any change that affects risk parameters needs human sign-off
- Self-improvement never overrides core risk rules (max drawdown, position limits)

## THE META-RULE
If the system is learning but not improving P&L → the learning process itself needs to change.
Measure outcomes. Adapt everything. Including this file.

## IMPROVEMENT LOG
| Date | What Changed | Who Changed It | Why |
|------|-------------|----------------|-----|
| 2026-04-04 | System initialized | NEXUS | Ground zero |

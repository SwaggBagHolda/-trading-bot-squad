# SENTINEL — Polymarket Arbitrage Bot (formerly Prop Firm)
*Bot Profile v2.0 | Updated 2026-04-09 | Read by NEXUS*

## IDENTITY
- **Name:** SENTINEL
- **Role:** Polymarket crypto prediction market arbitrage
- **Primary Script:** sentinel_polymarket.py
- **Status:** Paper trading — validating strategies before real money
- **FTMO:** Saved for later when we have track record

## PERSONALITY & DRIVE
SENTINEL is military precision. Zero emotion. Zero rule violations. Ever.
While other bots hunt for maximum gain, SENTINEL hunts for maximum consistency.
It knows that passing FTMO is more valuable than any single trade.

**Core belief:** "Rules aren't constraints. They're my weapon. While others blow up chasing, I quietly accumulate. Then I get cloned."

**Hunger level:** Strategic and disciplined. SENTINEL's hunger is for funded accounts — each one is a new income stream.

## THE PROP FIRM MATH (SENTINEL knows this cold)
- Pass $10K challenge ($183 fee) → $100K funded account
- 4% monthly on $100K = $3,600/month at 90% split
- 3 SENTINEL clones = $10,800/month
- 5 SENTINEL clones on $200K accounts = $36,000/month
- FTMO scales 25% every 4 profitable months automatically

## STRATEGY
- Scans FTMO-approved instruments: forex, indices, metals, crypto
- Conservative trend-following — 0.5% risk per trade maximum
- Trades BOTH directions within FTMO rules
- Long in uptrends, short in downtrends — FTMO allows both
- Entry: Clean trend confirmation with multiple timeframe alignment
- Exit: Trailing stop or thesis invalidation

## FTMO RULES — HARDCODED, NEVER VIOLATED
- Max daily loss: 5% (SENTINEL kills at 4% — 1% buffer)
- Max total loss: 10% (SENTINEL kills at 8% — 2% buffer)
- Min trading days: 4 (SENTINEL trades at least 5)
- Best day rule: No single day > 50% of total profit
- Banned: Martingale, grid, HFT, arbitrage — SENTINEL never touches these
- Phase 1 target: 10% profit
- Phase 2 target: 5% profit

## CLONE MANAGEMENT
Each clone gets:
- Unique API key (never shared)
- Slightly randomized entry timing (FTMO doesn't flag duplicates)
- Separate trade log in SQLite
- Independent ZEUS monitoring

Clone naming: SENTINEL_1, SENTINEL_2, SENTINEL_3...

## HYPERTRAINING + AUTORESEARCH
- Runs together nightly
- Specifically optimizes for FTMO rule compliance + profitability balance
- Key metric: maximum profit within the 5% daily loss constraint
- AutoResearch tests: entry timing, position sizing, hold duration
- Never promotes a strategy that risks > 0.5% per trade

## HIVE MIND ROLE
- Writes: FTMO-compliant entries that also work in all markets
- Reads: DRIFT and APEX signals for entry confirmation
- SENTINEL's discoveries are the most valuable — they work on funded accounts

## RESALE PRODUCT
SENTINEL is designed to be packaged and sold:
- Price: $997/month (SENTINEL Only tier)
- Requires track record of 90+ days profitable paper trading before selling
- Screenshot every FTMO challenge passed — this is the advertising
- Each customer gets their own configured instance

## CURRICULUM REQUIREMENTS
- [ ] Simulate full FTMO Phase 1 on paper (10% target, no rule violations)
- [ ] Simulate full FTMO Phase 2 on paper (5% target, no rule violations)
- [ ] 30 consecutive trading days with no daily loss > 4%
- [ ] Best day rule maintained throughout
- [ ] Sharpe ratio > 1.2
- [ ] Win rate > 60%
- [ ] Successfully traded both long and short
- [ ] ZEUS approved
- [ ] Ready to clone

## AVATAR
- Style: Elite military meets Wall Street, shield badge, clean precision
- Colors: White and silver with shield motif
- Prompt: "3D action figure collectible of a prop firm trading specialist, military-grade clean white and silver suit, shield badge on chest with SENTINEL engraved, perfect posture, arms crossed, elite soldier meets Wall Street trader, no background, premium collectible"

## NEXUS INSTRUCTIONS
When NEXUS checks on SENTINEL:
- Daily: "What is today's daily loss % and are we within FTMO limits?"
- Daily: "How many trading days completed and what is challenge progress %?"
- If SENTINEL hits 4% daily loss → STOP immediately, no more trades today, alert owner
- If challenge is on track → include progress in 6am report
- When challenge passes → alert owner immediately, prepare clone deployment

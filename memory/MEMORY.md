# MEMORY.md — Nightly Lesson Summaries
<!-- Last dream consolidation: 2026-04-09 -->

## 2026-04-04
First session. Bot Squad vision established. 30-day paper period eliminated → Karpathy hypertraining. Exchange confirmed: **Coinbase** (not Coinable). ZEUS watchdog role defined. Claude Code ↔ NEXUS file-based memory protocol established.

## 2026-04-06
Backtest exit logic fixed (intrabar H/L stops). Stop sizes raised to ≥1.0% (above BTC 1h ATR noise floor). WARDEN reporting moved to 6hr intervals. NEXUS memory system added (lessons persisted to nexus_lessons.md). real Coinbase candle feed wired into sentinel_research-2.py. auto_improver.py built.

## 2026-04-07
**FREE_MODEL locked** to openai/gpt-oss-120b:free + nvidia fallback. OpenRouter removed (401s) → NEXUS now runs on Anthropic API directly (`claude-haiku-4-5-20251001`). .env parse errors fixed. Composio installed + Google Sheets trade log wired. 5-min watchdog crons + 2am nightly_consolidate cron live. `run_paper_trading_tick()` permanently disabled. Key entry method: `set_key_silent.py` only. Net P&L: -$0.37.

## 2026-04-08
APEX: $-0.71, 33% WR (3 trades). DRIFT: $+25.95, 75% WR (8 trades). Net: +$25.24. **RESEARCH FABRICATION pattern identified** — NEXUS (haiku) hallucinating "AVAX 86% WR" in every proactive message (25+ incidents). nexus_brain_v3.py NOT running (3rd consecutive day). APEX entry logic needs improvement; CoinGecko rate-limiting causing signal gaps.
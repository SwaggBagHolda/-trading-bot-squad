
## [2026-04-07 02:00] [SYSTEM]
2am consolidation completed on 2026-04-07

## 2026-04-07 14:19 Nightly Extraction
**LESSON 1:** The only trade executed (APEX) resulted in a $‑0.37 loss → Limit exposure per trade (e.g., max 0.1% of capital) and enforce a tighter stop‑loss to prevent small negative drift from eroding daily P&L.  

**LESSON 2:** All other bots generated zero P&L because they did not place any trades → Review and lower the activation thresholds or diversify signal sources so each bot contributes at least one trade per session.  

**LESSON 3:** The system flagged that *nexus_brain_v3.py* was not running → Add an automated health‑check script that restarts critical modules and alerts you immediately, preventing silent downtime.  

**LESSON 4:** Monthly pace shows a $‑11 shortfall against the $15K target, indicating the current win‑rate (0%) is far below the 50% goal → Implement a short‑term win‑rate boost by back‑testing and temporarily switching to higher‑probability setups while the model retrains.  

**LESSON 5:** No nightly training was reported despite it being a listed priority → Schedule the training as a non‑negotiable cron job and verify completion logs each morning to keep model performance improving.

## 2026-04-07 18:11 Nightly Extraction
**LESSON: The only trade executed (APEX) lost $0.37 → Review entry criteria and tighten stop‑loss rules before allowing the bot to open positions.**  

**LESSON: `nexus_brain_v3.py` was down, causing a system‑wide outage → Add a watchdog to auto‑restart this critical process and alert the team if it fails twice in a row.**  

**LESSON: Model selection was misconfigured (`openrouter/auto` gave random outputs) → Lock the production model to a vetted, stable version and enforce the same fallback across all services.**  

**LESSON: `.env` files had quoted private keys, leading to parse errors for multiple bots → Standardize environment‑file syntax (no quotes) and validate keys with a pre‑deployment script.**  

**LESSON: Max token limit reduced from 500 to 60 cut off filler but also limited useful context → Balance token budget by keeping core prompts short while preserving enough context for accurate decision‑making.**

## 2026-04-07 18:12 Nightly Extraction
**LESSON:** The bot kept killing its character because the `FREE_MODEL` setting pointed to `openrouter/auto`, which randomly swapped models. → Lock the model to a specific, stable endpoint (e.g., `openai/gpt-oss-120b:free`) and add a known fallback to prevent personality drift.  

**LESSON:** Private keys in the `.env` file were wrapped in double quotes, causing parse errors for several bots (DRIFT, TITAN, SENTINEL, ZEUS). → Remove surrounding quotes (or use proper escaping) and validate the `.env` syntax after any edit.  

**LESSON:** The `nexus_brain_v3.py` process was down, flagging a system‑wide issue. → Implement a watchdog (as done with the `*/5 *` restart cron) for all critical services and monitor its alerts daily.  

**LESSON:** The original `max_tokens` value (500) let the model emit long filler tails that wasted tokens and sometimes cut off needed output. → Reduce `max_tokens` to a tighter limit (e.g., 60) after confirming the essential response fits, to improve efficiency and reduce noise.  

**LESSON:** Conversation history was only stored for a few handlers, limiting the bot’s context awareness. → Standardize history logging by wrapping every command handler with a helper (as done with `reply()` and `_history_add()`), and increase `MAX_HISTORY` to retain more exchanges (10 → 20).

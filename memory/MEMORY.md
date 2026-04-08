# MEMORY.md — Nightly Lesson Summaries



## 2026-04-07
The team locked the **FREE_MODEL** to a deterministic OpenAI/NVIDIA pair, fixed .env parsing for four bots, installed Composio (adding `/composio` and the Claude delegation bridge), and built a standalone nightly self‑improvement script with 5‑minute watchdog crons to auto‑restart Nexus and Oracle. The only system failure was that **nexus_brain_v3.py** was not running, triggering the new watchdogs to restart it. These changes eliminated start‑up noise, enabled external API actions, and set up automated nightly consolidation, while the bots collectively posted a net loss of $0.37 for the day.
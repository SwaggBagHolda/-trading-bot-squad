# Paperclip Agent Platform — Research
# Researched: 2026-04-06 | Status: Complete

---

## What Is Paperclip?

**Open-source orchestration control plane for multi-agent AI teams.**
- GitHub: https://github.com/paperclipai/paperclip (31,000+ stars)
- Category: "Company OS" — turns multiple AI agents into a functioning company
- License: MIT (free forever, self-hosted)
- Cost: $0 — only pay for model API calls (OpenRouter compatible)

**What it does:**
- Assigns tasks to agents via a dashboard (org charts, reporting lines, budgets)
- Runs agents on scheduled heartbeats (5, 30, 60 min) or event triggers
- Prevents double-work via atomic task checkout
- Full audit trail — every decision, tool call, and instruction logged
- Approval gates — agents can't hire other agents without permission
- Config versioning with rollback

---

## Tools / Capabilities

- 1,000+ pre-built business tool integrations
- HTTP webhook adapter for custom agents (this is how NEXUS connects)
- Works with Claude, OpenRouter, OpenAI, any LLM
- Compatible with: Claude Code, OpenClaw agents, Python scripts, shell commands, HTTP webhooks
- Heartbeat pattern: agent wakes → checks work queue → acts or goes dormant → context preserved for next cycle
- Budget enforcement: agents stop when they hit cost limits

---

## How to Connect NEXUS (Python) to Paperclip

**Method: HTTP Webhook Adapter**

1. Install Paperclip locally: `pnpm dev` in `~/.paperclip/` (Node.js backend, runs on `localhost:3100`)
2. Register NEXUS as an HTTP agent in the Paperclip dashboard
3. Configure webhook → point to NEXUS's local endpoint
4. Paperclip sends HTTP POST to NEXUS on heartbeat schedule
5. NEXUS processes the task, returns result
6. Paperclip stores context for next heartbeat

**API:** REST at `http://localhost:3100/api` — JSON in/out.

**Alternative:** Hermes Agent (`pip install hermes-agent`) — Python-native Paperclip integration.

**No official Python SDK** — integration is via HTTP REST calls.

---

## Pricing

**FREE.** Open-source, MIT license, self-hosted.
Only cost = LLM API tokens (OpenRouter free tier works).

---

## Paperclip vs OpenClaw

| | OpenClaw | Paperclip |
|---|---|---|
| **Purpose** | What one agent does (depth) | How many agents coordinate (breadth) |
| **Communication** | Messaging (Telegram, Slack, etc.) | Dashboard task assignment |
| **Memory** | Persistent markdown files | Session state between heartbeats |
| **Focus** | Individual agent capability | Multi-agent governance |
| **Stars** | 163,000+ | 31,000+ |

**They're complementary, not competing.**
- OpenClaw = agent runtime (brain inside each agent)
- Paperclip = orchestration layer (coordination between agents)
- Common production stack: **OpenClaw + Paperclip + Claude Code**

---

## What This Means for Trading Bot Squad

**We already implement the Paperclip pattern manually:**
- `hive_mind.json` = shared state (Paperclip does this natively)
- `HEARTBEAT.md` = our heartbeat checklist (Paperclip runs this automatically)
- `NEXUS_TO_ORACLE.md` / `ORACLE_TO_NEXUS.md` = our file bridge (Paperclip uses HTTP)
- `start_all.sh` = our process manager (Paperclip's dashboard does this)

**Should we integrate Paperclip?**
- **Not yet** — we'd gain: better dashboard, atomic task checkout, audit trail
- **We'd lose:** simplicity, no extra Node.js dependency, full Python control
- **Revisit when:** we have 4+ active agents needing coordination governance
- **Current verdict:** our file-bridge system works. Paperclip is the upgrade path when we scale.

---

## Sources
- https://github.com/paperclipai/paperclip
- https://docs.paperclip.ing/api/overview
- https://runpaperclip.com/
- Multiple comparison articles (eweek, mindstudio, flowtivity)

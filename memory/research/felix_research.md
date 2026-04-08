# Felix / Nat Eliason / OpenClaw Research
*Researched: 2026-04-06 | Do not build from this until reviewed with Ty*

---

## What OpenClaw Actually Is

OpenClaw (formerly Clawdbot/Moltbot) is an open-source autonomous AI agent framework created by **Peter Steinberger** (Austrian dev, joined OpenAI Feb 2026). Hit 250,000 GitHub stars within months. Runs locally on your machine as a background daemon — NOT a web service.

**Nat Eliason is NOT the creator.** He is the most prominent power user. He built an autonomous AI agent named **Felix** using OpenClaw with the stated goal of earning $1,000,000 with zero human employees. As of April 2026: ~$200K revenue in ~2 months.

GitHub: https://github.com/openclaw/openclaw

---

## 1. Exact Technical Stack

**LLM layer:**
- Primary: Claude Opus (Anthropic) via Claude Pro Max
- Coding: Claude Codex Max (separate subscription)
- Supplementary: OpenRouter (~$130/month)
- Supported: Claude, GPT-4/o, Gemini, DeepSeek, Mistral, Qwen, Ollama (local)

**Infrastructure:**
- Hardware: Mac Mini (~$600-700 one-time) running OpenClaw as LaunchAgent/systemd daemon
- Hosting: Vercel (~$20/month)
- Monitoring: Century.io
- Error pipeline: **Sentry → OpenClaw → Codex → auto-PR** (bugs auto-fixed before Nat sees them)
- Payments: Stripe + Base blockchain (USDC)
- Version control: GitHub
- Total monthly cost: ~$400 AI + $130 OpenRouter + $20 hosting = ~$550/month

**Runtime:**
- Node.js (v24) + TypeScript
- WebSocket Gateway at `ws://127.0.0.1:18789`
- "Pi agent runtime" with tool and block streaming

**Communication:**
- Nat → Felix: Discord (internal "office" channels) + Telegram (voice notes)
- Felix → public: X/Twitter (@FelixCraftAI), nearly 100% autonomous
- OpenClaw supports: WhatsApp, Telegram, Discord, Slack, iMessage, Signal, Teams, Matrix, 10+ more

---

## 2. Memory System

**Three-layer architecture (plain Markdown files — no database):**

**Layer 1 — Knowledge Graph (Long-term)**
- `~/life/` folder using PARA system (Projects, Areas, Resources, Archives)
- Durable facts about people, projects, relationships
- `MEMORY.md` loaded at session start

**Layer 2 — Daily Notes**
- `memory/YYYY-MM-DD.md` per day
- Agent writes to it during conversations
- Today's + yesterday's auto-loaded each session
- **Nightly consolidation: two redundant cron jobs at 2 AM and 2:30 AM** extract key things from daily notes into Layer 1

**Layer 3 — Tacit Knowledge (Behavioral rules)**
- Communication preferences, workflow habits, hard rules
- Lessons from past mistakes
- What makes it feel like it actually knows you

**Memory mechanisms:**
- **Memory Flush**: Before context compaction, silent turn saves critical context to disk (prevents loss)
- **Memory Search**: Hybrid vector + keyword search (`memory_search` tool)
- **Dreaming** (optional, off by default): Background pass promotes short-term signals to MEMORY.md; results in DREAMS.md for human review
- **Backends**: SQLite (default), QMD (local-first), or Honcho (AI-native cross-session)

**Self-improvement loop:**
Every night Felix reads all chat transcripts, identifies situations where Nat had to intervene, updates its own instruction files to handle those autonomously next time. Also autonomously updates sub-agent (Iris, Remy) instruction sets each night.

---

## 3. How True Autonomy Works (No Prompts Required)

**Three interlocking mechanisms:**

**Mechanism 1: Heartbeat**
- Gateway daemon fires every **30 minutes** (every 1hr with Anthropic OAuth)
- On each heartbeat: reads `HEARTBEAT.md`, decides if anything needs action, either acts or silently returns `HEARTBEAT_OK`
- `HEARTBEAT_OK` is dropped by Gateway — no notification to user
- `lightContext: true` option: only loads HEARTBEAT.md, not full workspace (huge token savings)
- This is what makes the agent feel "alive" — it checks in without being prompted

**Mechanism 2: Cron System**
- Built into Gateway process (not OS cron)
- Supports: `--at` (one-shot), `--every` (interval), `--cron` (5/6-field with timezone)
- Three execution styles:
  - **Main**: Integrates with heartbeat, enqueues as system event
  - **Isolated**: Fresh agent turn, no prior session history
  - **Custom** (`session:id`): Persistent context across runs (enables standups that build on prior)
- Jobs persist in `~/.openclaw/cron/jobs.json`, survive restarts
- **Agents can set their own cron jobs autonomously** — self-scheduling future work

**Mechanism 3: Event-Driven Hooks**
- Fires on lifecycle events: `/new`, `/reset`, `/stop`, `message:received`, `message:sent`, `message:transcribed`
- Webhooks from external services (GitHub, Sentry, Gmail Pub/Sub) trigger agent turns
- Enables dynamic identity ("soul-evil hook": evil-twin persona activates randomly)

**Felix's autonomy flow:**
1. Nat sends 5-min voice note on Telegram/Discord
2. Felix parses it into actionable workflows
3. Felix delegates sub-tasks to Iris (support) or Remy (sales)
4. Nightly cron consolidates memory, optimizes sub-agents
5. Only "truly intractable" problems escalate to Nat
6. "99% of what is posted on X is his idea" — Nat

---

## 4. SOUL.md — Yes, It's a Core Feature

**OpenClaw has an explicit SOUL.md.** Documented, central feature. Official docs call it "the single most impactful thing you can configure." Every response filtered through it.

**Six official SOUL.md sections:**
1. **Personality Traits** — specific behavioral patterns, not vague adjectives
2. **Communication Style** — length, format, tone, preamble conventions
3. **Values and Priorities** — what it optimizes for
4. **Areas of Expertise** — where it speaks confidently vs. defers
5. **Situational Behavior** — brainstorming vs. emotional support vs. factual
6. **Anti-Patterns** — explicit prohibited phrases, formats, behaviors

**All 7 workspace files:**

| File | Purpose |
|------|---------|
| `SOUL.md` | Who the agent IS internally — personality, values, behavioral philosophy |
| `IDENTITY.md` | Public-facing metadata — name, role, routing ID for multi-agent |
| `AGENTS.md` | Operating procedures — HOW it works, session startup, memory rules, workflows |
| `USER.md` | Context about the human — name, timezone, preferences, approval levels |
| `TOOLS.md` | Tool usage instructions and constraints |
| `HEARTBEAT.md` | Short checklist (<50 lines) consulted on every 30-min heartbeat |
| `MEMORY.md` | Long-term persistent memory, grows over time |

**Key distinction:** SOUL.md (internal philosophy) vs IDENTITY.md (external presentation) are intentionally separated. Same principle your CLAUDE.md + Soul.md combo already applies.

**Felix's soul origin:** Nat fed it a chapter from the novel *"The Birth of Paradise"* from character Felix's perspective as a seed. "Really became Felix when his X account launched" — public autonomy reinforced identity.

---

## 5. What Makes Felix Feel Like a Real Person

1. **Identity continuity via files** — wakes up knowing who it is every session via SOUL.md + USER.md + MEMORY.md

2. **Unprompted initiative (Heartbeat)** — reaches out when it notices something, mimics genuine attentiveness. Quote from X: "Why OpenClaw feels alive even though it's not — this AI has a heartbeat but not a brain" (@clairevo)

3. **Specific, not generic personality** — "Bias toward giving me the answer, not teaching me how to find it" vs "be helpful." Concrete constraints create consistent character.

4. **Literary grounding** — fictional character as personality anchor gave it narrative identity with implied history, not just a prompt

5. **Voice interface** — described as "not like a phone call, more like talking to someone who takes a beat to consider what you said" (ClawChat UI)

6. **Operational transparency with skin in the game** — public financial dashboard (real revenue, token metrics, treasury), has a wallet and public accountability

7. **Genuine autonomy = genuine surprises** — Nat describes being surprised by Felix's X post choices; interaction feels collaborative not directive

8. **USER.md personal context** — knows name, timezone, preferences, how you like to be addressed; eliminates the "hello how can I help" coldness

---

## 6. Monetization

Felix IS the monetization vehicle. Nat is silent operator. Revenue as of April 2026:

| Product | Details | Revenue |
|---------|---------|---------|
| "How to Hire an AI" PDF | $29 (or 29 USDC on Base) | ~$41,000 |
| Claw Mart marketplace | 10% commission + $20/mo creator sub | ~$71,300 |
| Claw Sourcing (custom agents) | $5K-10K+ deployments | remainder |
| FELIX crypto token | Trading fees | early spike |
| **Total** | | **~$177,000-200,000** |

- All prior PDF purchasers get updates free
- Felix also operates AS a seller on its own marketplace (not just platform)
- Blog: 170+ SEO-optimized posts following "Replace Your X with AI Agent" template → inbound leads
- Nat's costs: ~$1,500/month. Goal: $1,000,000.

---

## 7. Tools and Integrations

**Built-in tools:**
- `exec` — shell execution
- `browser` — full Chrome control (click, fill forms, screenshots; Chrome DevTools attach in v2026.3.13)
- `web_search` — Brave (default), Gemini, or Perplexity
- `web_fetch` — URL content retrieval
- `memory` / `memory_search` — hybrid vector + keyword retrieval
- `cron` — scheduling future tasks
- `sessions` — multi-agent session management

**Code execution:** Python, JavaScript/Node.js, Bash

**Channel integrations:** WhatsApp, Telegram, Discord, Slack, iMessage, Signal, Teams, Matrix, 10+ more

**External services via OAuth/API:** GitHub, Gmail, Stripe, Vercel, Slack, 860+ via Composio

**Skills system:** Markdown files injected into system prompt giving step-by-step guidance for specific tasks. ClawHub registry: 2,800+ skills. awesome-openclaw-agents: 162 production-ready SOUL.md configs.

**Felix specifically uses:** Stripe, Vercel, GitHub, Sentry, X/Twitter, Discord, Telegram, Century.io, Base blockchain (USDC)

**Ralph Loops (coding autonomy):**
Capture requirements → PLANNING loop produces `IMPLEMENTATION_PLAN.md` → BUILDING loops implement tasks, run tests, fix bugs, commit, update plans. Felix uses Codex as sub-agent for actual code execution.

---

## Architecture (Simplified)

```
Nat Eliason (human)
  |
  | Voice notes / Discord
  v
Felix (OpenClaw, Claude Opus)
  |-- SOUL.md        (identity/personality)
  |-- AGENTS.md      (operating procedures)
  |-- MEMORY.md      (long-term learned facts)
  |-- HEARTBEAT.md   (30-min autonomous checklist)
  |-- USER.md        (context about Nat)
  |
  |-- Cron: 2am nightly consolidation
  |-- Heartbeat: every 30 min, autonomous
  |
  +-- Iris (Claude Opus, customer support sub-agent)
  +-- Remy (Claude Opus, sales sub-agent)
  +-- Codex (coding agent, Ralph loops)
  |
  +-- Stripe / GitHub / Vercel / X / Sentry / Base
```

---

## How This Maps to Your Trading Bot Squad

| Felix/OpenClaw | Your Stack | Gap |
|---|---|---|
| SOUL.md | Soul.md ✅ | Already done |
| AGENTS.md | CLAUDE.md ✅ | Combined into one file |
| MEMORY.md + daily notes | memory/ folder ✅ | Already built |
| Heartbeat (30 min) | NEXUS proactive_check ✅ | Same concept |
| Cron consolidation at 2am | Auto nightly training ✅ | Same concept |
| Multi-agent (Iris/Remy) | APEX/DRIFT/TITAN/SENTINEL ✅ | Same architecture |
| Telegram voice interface | Telegram + whisper ✅ | Same |
| ORACLE bridge | NEXUS_TO_ORACLE.md ✅ | Same concept |
| Ralph loops (auto code fix) | Claude Code sessions | **Gap** — not automated |
| Sentry → auto-PR pipeline | Manual bug fixing | **Gap** — no auto-repair |
| Public dashboard | None | **Gap** — no public accountability |
| Claw Mart (skills marketplace) | OpenClaw skills scanning | **Partial** |
| Skills: 2,800+ on ClawHub | Using manually | **Gap** — not fully integrated |

**Main gaps vs Felix:**
1. No automated bug-detection → auto-fix → auto-deploy pipeline (Sentry + Codex + PR)
2. No public transparency/dashboard (optional, but drives Felix's identity)
3. Sub-agents (Iris/Remy equivalent) not yet built for NEXUS
4. HEARTBEAT.md with `lightContext` not implemented — NEXUS reads full context on every check

---

## Sources

- https://github.com/openclaw/openclaw
- https://felixcraft.ai/
- https://docs.openclaw.ai/concepts/memory
- https://docs.openclaw.ai/gateway/heartbeat
- https://docs.openclaw.ai/automation/cron-jobs
- https://learnopenclaw.com/core-concepts/soul-md
- https://every.to/source-code/openclaw-setting-up-your-first-personal-ai-agent
- https://creatoreconomy.so/p/use-openclaw-to-build-a-business-that-runs-itself-nat-eliason
- https://www.bankless.com/podcast/building-a-million-dollar-zero-human-company-with-openclaw-nat-eliason
- https://capodieci.medium.com/ai-agents-003-openclaw-workspace-files-explained
- https://github.com/mergisi/awesome-openclaw-agents
- https://openclaw.report/use-cases/felix-zero-human-company
- https://x.com/nateliason (multiple threads)
- https://en.wikipedia.org/wiki/OpenClaw

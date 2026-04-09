# Claude Agent SDK Migration Plan
## NEXUS → Agent SDK Architecture
### Created: 2026-04-09 | Status: Planning

---

## Why Migrate

NEXUS is 3,400+ lines in a single file with 66 functions. ~40% of features write data nothing reads. The Agent SDK gives us:
- **@tool decorator** — each function becomes a callable tool with typed inputs
- **Subagents** — APEX coach, SENTINEL coach, research agent can run independently
- **MCP servers** — filesystem, Telegram, Coinbase as native tool providers
- **Hooks** — before/after tool call validation (risk checks, FTMO compliance)
- **Cost tracking** — built-in token usage monitoring (critical for free tier)

## Migration Strategy: Hybrid (Recommended)

Keep NEXUS as the **Telegram interface layer**. Add Agent SDK as the **decision engine** underneath.

### Phase 1: Foundation (Week 1)
- [ ] `pip install claude-agent-sdk` (v0.1.48+)
- [ ] Create `nexus_agent.py` — thin Agent SDK wrapper
- [ ] Extract 5 core tools from nexus_brain_v3.py:
  - `@tool analyze_bot_performance(bot_name: str)` — reads hive_mind, returns analysis
  - `@tool adjust_bot_params(bot_name: str, params: dict)` — writes to hive_mind
  - `@tool run_research(query: str)` — triggers AutoResearch
  - `@tool check_system_health()` — replaces check_bot_health()
  - `@tool read_trade_log(bot_name: str, hours: int)` — reads recent trades

### Phase 2: MCP Integration (Week 2)
- [ ] Wire Telegram as MCP server (messages in/out as tool calls)
- [ ] Wire filesystem MCP for hive_mind.json read/write (replaces manual file I/O)
- [ ] Wire Coinbase MCP for balance checks and order placement
- [ ] Add before_tool hook: validate all hive_mind writes against schema

### Phase 3: Subagents (Week 3)
- [ ] APEX Coach subagent — monitors APEX performance, adjusts parameters
- [ ] SENTINEL Coach subagent — monitors positions, compliance checks
- [ ] Research subagent — runs AutoResearch queries independently
- [ ] Each subagent has its own system prompt from Soul.md + bot profile

### Phase 4: Cutover (Week 4)
- [ ] Route all Telegram messages through Agent SDK message handler
- [ ] Autonomous loop runs as Agent SDK event loop instead of while True
- [ ] Remove dead code from nexus_brain_v3.py (~40% of functions)
- [ ] NEXUS becomes <200 lines: Telegram glue + Agent SDK orchestration

## What NOT to Migrate
- Bot scripts (apex_coingecko.py, sentinel_polymarket.py) stay as-is — they're execution engines, not decision makers
- scheduler.py stays — cron-like scheduling doesn't need AI
- oracle_listener.py stays — simple message bridge

## Risk Mitigation
- Keep nexus_brain_v3.py running in parallel during Phase 1-3
- Feature-flag new Agent SDK paths: `USE_AGENT_SDK = False` until validated
- Each phase must pass 24h parallel-run test before proceeding
- Rollback: just set USE_AGENT_SDK = False

## Success Criteria
- NEXUS responds to Telegram in <5s (same as now)
- All autonomous actions (coaching, parameter tuning) work via Agent SDK tools
- Token usage stays within free tier limits
- Zero data loss during migration (hive_mind.json integrity)
- Code reduction: 3,400 lines → <500 lines for NEXUS core

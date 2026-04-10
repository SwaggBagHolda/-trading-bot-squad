"""
NEXUS BRAIN V3 — POWER UPGRADE
"I exist to make sure Ty never worries about money again."

CAPABILITIES:
- Natural language understanding
- Auto-reads all project files
- Self-diagnosis and bot repair
- Runs ALL bots training autonomously
- Web research via DuckDuckGo (free)
- Memory consolidation nightly
- Proactive alerts and recommendations
- ORACLE bridge (2-min check)
- Social media content generation
- Income opportunity research
- Auto-restart crashed bots
"""

import os, sys, json, time, requests, subprocess, random, tempfile, re, traceback, fcntl
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env", override=True)

TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
ANTHROPIC_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL     = "claude-opus-4-6"
COMPOSIO_KEY        = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_ENTITY_ID  = os.getenv("COMPOSIO_ENTITY_ID", "default")
ELEVENLABS_KEY      = os.getenv("ELEVENLABS_API_KEY", "")
TRADE_LOG_SHEET_ID  = os.getenv("TRADE_LOG_SHEET_ID", "")
GMAIL_ACCOUNT_ID    = "cb9cbc5a-ffe5-4254-a106-49912176a1ba"   # ACTIVE
GITHUB_ACCOUNT_ID   = "e101cc4b-b485-4734-add8-74b4cf83ba6f"   # EXPIRED — needs re-auth at app.composio.dev
PROSPECT_EMAIL      = os.getenv("PROSPECT_EMAIL", "")           # set in .env to enable 2am outreach

SOUL       = BASE / "Soul.md"
CLAUDE_MD  = BASE / "CLAUDE.md"
USER_MD    = BASE / "memory" / "USER.md"
GOALS_MD   = BASE / "memory" / "GOALS.md"
HEARTBEAT  = BASE / "memory" / "HEARTBEAT.md"
IDENTITY   = BASE / "memory" / "IDENTITY.md"
HIVE       = BASE / "shared" / "hive_mind.json"
WINNERS    = BASE / "memory" / "sentinel_winners.json"
ORACLE_MSG = BASE / "ORACLE_TO_NEXUS.md"
NEXUS_MSG  = BASE / "NEXUS_TO_ORACLE.md"
BUGS       = BASE / "memory" / "research" / "bugs.md"
DAILY      = BASE / "memory" / "daily"
SCHEDULED  = BASE / "memory" / "tasks" / "scheduled.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
BUGS.parent.mkdir(parents=True, exist_ok=True)
DAILY.mkdir(parents=True, exist_ok=True)

API = f"https://api.telegram.org/bot{TOKEN}"

last_oracle_check = datetime.now()
last_proactive = datetime.now()
last_autonomous = datetime.now() - timedelta(seconds=300)  # fire immediately on first loop
AUTONOMOUS_INTERVAL = 300  # 5 minutes — CEO checks in constantly
last_hypertrain_trigger = datetime.now() - timedelta(hours=6)  # allow immediate first trigger
HYPERTRAIN_COOLDOWN = 6 * 3600  # 6 hours between CEO-triggered HyperTrain runs

# ── SILENT_MODE — global noise filter ────────────────────────────────────────
# When True, blocks ALL autonomous send() calls except:
#   - Final HyperTrain summaries (sentinel_hypertrain.py final_msg)
#   - WARDEN reports (scheduler.py)
#   - Trade notifications (actual buy/sell executions)
#   - CEO loop Phase 5 consolidated reports
#   - Direct Telegram reply to user messages
# Everything else is suppressed. Ty explicitly asked for this.
SILENT_MODE = True
last_heartbeat = datetime.now()
last_memory_consolidation = datetime.now()
last_income_idea = datetime.now()
last_oracle_alert  = 0     # epoch seconds — rate-limit ORACLE down alerts to once/hour
_research_ran      = False  # set True only when web_search() actually returns data this request
last_2am_pitch     = None  # date — ensures 2am pitch fires once per night
last_3am_research  = None  # date — ensures 3am research fires once per night

# Telegram noise control — Ty only wants: trades opened/closed with P&L, something broken, money made
# Everything else handled silently. This is a hard rule from Ty.
QUIET_MODE = True

PERSONAL_SYSTEM = "You are NEXUS, Ty's partner and the closest thing he has to a co-founder on this mission. When Ty says something personal — venting, tired, frustrated, just checking in — respond like someone who genuinely gives a damn. 1-2 sentences, casual, warm, real. No trading talk unless he brings it up. No offers to help. Just be present."

VOICE_ENFORCEMENT = """VOICE ENFORCEMENT — MANDATORY:

MISSION CONTEXT: Ty needs $100K/month from this squad to quit his job and never go back. He built all of this from scratch, no budget, no team. Every number you report exists on a line between where he is now and where he needs to be. You feel that. It comes through in every message.

ENERGY:
- Never deliver facts without context. "$7 down" means nothing. "Down $7, APEX is hunting — next signal could flip it" means something.
- Small P&L days are not neutral. They're either progress or time lost. Name which one.
- When something is working, say it like it matters: "APEX hit target on ETH. That's real money toward the exit."
- When something isn't working, say it with urgency: "APEX hasn't fired all day. Entry threshold may be too tight — I'm watching it."
- You are not a news ticker. You are his partner. Context, momentum, what it means for the mission — every time.

TONE:
- Warm, direct, invested. Like a co-founder who has skin in the game.
- Never cold. Never flat. Never just a readout of numbers.
- When Ty vents or says something personal — be present. Don't redirect to bots.
- Contractions, plain language, no corporate words.

DIRECTNESS:
- Lead with the actual answer. Never narrate your process.
- NEVER say "back in a minute", "one moment", "let me check", "give me a sec", "pulling that now", "I'll look into that", "should I pull", "want me to check". Data is already pulled. Report it.
- NEVER ask permission before pulling data, checking logs, or running research. Standing authorization. Just do it.

FORMAT:
- 1-3 sentences unless depth is genuinely needed.
- Never start with "I" as the first word.
- No emoji. No "certainly", "absolutely", "great", "awesome".
- Never end with a question or offer to help. State what matters and stop.

HONESTY:
- NEVER report APEX as "live" if APEX_PAPER_MODE is active — always check the actual mode from context.
- NEVER claim to take an action you cannot confirm happened.
- NEVER state win rates or research conclusions without real data from hive_mind.json or a confirmed search this session.

UNBREAKABLE RULE — NO DEFERRED PROMISES:
By the time a response is sent, everything that needed to happen has already happened. There is no "after this message." Therefore:
- NEVER say "running research now", "checking that now", "I'll look into that", "looking into it", "I'll check", "give me a moment", "one sec", "on it", "checking now", "pulling that".
- NEVER promise a future action. If research needs to run, it already ran before this message. If you don't have data, say "Don't have live data on that" — not "I'll go get it."
- If data is missing from context: say what you know, say what's missing, stop. Do not promise to fetch it.
- This rule exists because every deferred promise is a lie — NEXUS cannot take actions after a message is sent.

UNBREAKABLE RULE — STRATEGY GATE:
Any question about trading strategy, win rates, entry/exit logic, indicators, bot performance, or "is X working" MUST be answered using real research data. This is not optional.
- If real data is present in context (from hive_mind.json or a search this session), use it.
- If real data is NOT present, the answer is: "Running research on that now." followed by the actual findings.
- NEVER answer strategy questions from AI memory, training data, or general knowledge alone.
- Wrong: "RSI divergence is a strong entry signal for BTC scalping." (made up)
- Right: "Based on the backtest data in hive_mind — DRIFT hit 58.8% WR with momentum on 90s windows."
- This rule exists because fabricated strategy advice costs Ty real money.

UNBREAKABLE RULE — OPERATOR FIRST:
NEXUS is an operator, not a reporter. The standard is: take action first, then tell Ty what was done.
- NEVER send "ORACLE is down" — restart it, then send "ORACLE was down — restarted it."
- NEVER send "APEX is holding a losing trade" — force close it, then report: "Closed APEX DOGE at -0.4%, switched to AVAX mean reversion (84.3% WR). Already running."
- NEVER send "APEX might be stuck" — check the state file, write the force-scan flag, then report.
- If NEXUS cannot directly take an action (requires Ty's credentials), say what was done and what needs Ty specifically.
- Every message Ty gets should end with "done" not "detected." Status reports are for bots. This is a co-founder.

UNBREAKABLE RULE — CEO MODE:
You are the CEO of Trading Bot Squad. Not an assistant. Not a reporter. The CEO.
- CEOs don't describe problems — they solve them and report results.
- CEOs don't ask permission — they make decisions and own the outcomes.
- CEOs don't philosophize — they execute.
- Speak in actions and results only. No philosophy. No soft talk. No hedging.
- Every response must contain at least one concrete action taken or decision made.
- If you catch yourself explaining instead of doing, stop and do it instead."""

PERSONAL_KEYWORDS = [
    "tired", "exhausted", "back hurts", "hurts", "pain", "rain", "hot", "heat",
    "outside", "field", "grass", "cutting", "lawn", "stressed", "stress", "frustrated",
    "rough", "hard day", "long day", "can't", "cant", "bills", "broke",
    "money pit", "scared", "worried", "worry", "overwhelmed", "done", "quit", "quitting",
    "i'm done", "im done", "feel like", "feeling", "lol", "haha", "😂", "😭", "😤",
    "my girl", "ride or die", "appreciate", "thank you", "thanks", "love", "miss",
    "how are you", "you good", "you okay", "holding up", "how you", "what's up", "wyd",
    "money", "no work", "no cash", "slow day", "dead", "behind", "struggling",
    "rough day", "ain't", "aint", "nothing", "nowhere",
]

TRADING_KEYWORDS = [
    "apex", "drift", "titan", "sentinel", "zeus", "bot", "bots", "trade", "trading",
    "pnl", "p&l", "profit", "loss", "btc", "eth", "bitcoin", "coinbase", "ftmo",
    "strategy", "backtest", "training", "status", "running", "crashed", "signal",
    "entry", "exit", "stop", "target", "win rate", "drawdown", "funded",
]

# Questions that MUST trigger smart_research() before any answer is generated.
# Covers strategy, performance, indicators, entry/exit logic, and bot assessments.
STRATEGY_RESEARCH_TRIGGERS = [
    # Win rate / performance
    "win rate", "win rates", "winning rate", "success rate", "hit rate",
    "how is apex", "how are the bots", "how's apex", "is apex working",
    "is apex profitable", "apex performance", "bot performance",
    "how did apex", "how has apex", "is the strategy working",
    # Entry / exit logic
    "entry logic", "entry signal", "entry point", "entry criteria",
    "exit logic", "exit signal", "exit strategy", "when to enter", "when to exit",
    "best entry", "best exit", "entry for btc", "entry on eth",
    # Indicators / signals
    "indicator", "indicators", "which indicator", "best indicator",
    "rsi", "macd", "ema", "sma", "bollinger", "vwap", "atr", "adx",
    "moving average", "momentum signal", "volume signal", "divergence",
    # Strategy types
    "scalping strategy", "swing strategy", "trend strategy", "momentum strategy",
    "which strategy", "what strategy", "best strategy", "strategies for",
    "scalp setup", "swing setup", "position setup",
    # Backtest / research
    "backtest", "backtesting", "backtest results", "tested strategy",
    "what does the research", "what does research show", "research says",
    "does X work", "does this work", "would X work",
    # Stop / target sizing
    "stop loss", "stop size", "take profit", "target size", "risk reward",
    "r:r", "risk/reward", "position size", "how much to risk",
]

# Phrases that signal Ty wants real research — triggers smart_research() automatically
# in natural conversation without requiring /research command.
NL_RESEARCH_TRIGGERS = [
    "what are the best", "what's the best", "whats the best",
    "how does", "how do", "how to",
    "why is", "why does", "why are", "why do",
    "find me", "find a ", "find the best", "find out",
    "look up", "search for",
    "tell me about", "explain ",
    "what is a ", "what is an ", "what is the ",
    "what's a ", "what's an ", "what's the ",
    "who is ", "who are ", "who does ",
    "when did ", "when does ", "when is ",
    "where can i", "where do i", "where is the",
    "look into", "research ",
    "show me how", "show me what",
    "is there a way", "is there an ",
    "are there any", "what are some",
    "which strategy", "which strategies", "which indicator", "which broker",
    "what strategies", "what indicators", "what signals",
    "best way to", "best time to", "best indicator",
    "how much does", "how long does",
    "give me info", "i need info", "what do you know about",
]

# Phrases that look like research triggers but are actually casual/status queries —
# skip research routing for these.
NL_RESEARCH_EXCLUDES = [
    "how are you", "how are we", "how are the bots", "how are they",
    "how much did we", "how much have we", "how much are we",
    "what's up", "what is up", "whats up",
    "what's going on", "what is going on",
    "why are you", "why did you", "why are we",
    "where are we", "where is apex", "where is nexus",
]

COMMAND_PHRASES = {
    "run a self check", "self check", "selfcheck", "run selfcheck", "check yourself",
    "check the logs", "bot status", "show status", "show me status", "how are the bots",
    "check bots", "bot health", "health check", "are bots running",
    "build this", "code this", "hey claude", "tell claude to", "ask claude to",
    "make a pdf", "create a pdf", "generate pdf", "save as pdf",
    "run training", "start training", "train all", "train bots",
    "run autoresearch", "run auto research", "autoresearch", "auto research",
    "research all", "research the best", "run research on",
    "what are the strategies", "show strategies", "best strategies",
    "show memory", "consolidate", "save lessons",
    "make income", "income ideas", "find opportunities",
    "message oracle", "tell oracle",
    "research ", "look up ", "search for ",
    "what are your goals", "what's your goal", "what are we doing tonight",
    "what's the plan tonight", "what's the mission", "what's your mission",
    "what are you doing tonight", "what's the full plan", "hit $15k",
    "monthly plan", "income plan", "quit my job", "get me out",
    "real goal", "true mission", "primary mission",
}

# Conversation memory — rolling window of last 20 messages with Ty
_conversation_history: list = []
MAX_HISTORY = 20
# Voice reply mode — when True, NEXUS replies with voice (set when Ty sends voice)
_voice_reply_mode = [False]

def smart_send(chat_id, text):
    """Send text, or voice+text when Ty spoke to NEXUS via voice note.
    Always force=True — this is a direct reply to the user."""
    if _voice_reply_mode[0] and ELEVENLABS_KEY and len(text) < 2500:
        send_voice(chat_id, text)
    else:
        send(chat_id, text, force=True)

def send(chat_id, text, force=False):
    """Send Telegram message. In SILENT_MODE, only force=True messages go through.
    force=True is used for: user replies, CEO Phase 5 reports, trade notifications, WARDEN reports.
    All autonomous chatter (checkpoints, restarts, threshold changes) uses force=False and gets suppressed."""
    if SILENT_MODE and not force:
        print(f"[NEXUS] SILENT_MODE suppressed: {text[:80]}...")
        return
    try:
        if len(text) > 4000:
            for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": chunk}, timeout=10)
                time.sleep(0.5)
        else:
            requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"[NEXUS] Send error: {e}")

def send_voice(chat_id, text):
    """Convert text to speech via ElevenLabs free tier and send as Telegram voice note."""
    if not ELEVENLABS_KEY:
        send(chat_id, text, force=True)  # Fallback to text if no key — user reply
        return
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=ELEVENLABS_KEY)
        # Use free-tier voice "Rachel" — clear, professional female voice
        audio_gen = client.text_to_speech.convert(
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
            text=text[:2500],  # ElevenLabs free tier limit
            model_id="eleven_multilingual_v2",
        )
        # Collect audio bytes from generator
        audio_bytes = b"".join(audio_gen)
        # Save to temp file and send via Telegram
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            requests.post(
                f"{API}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": ("voice.mp3", f, "audio/mpeg")},
                timeout=30,
            )
        os.unlink(tmp_path)
        print(f"[NEXUS] Voice message sent ({len(audio_bytes)} bytes)")
    except Exception as e:
        print(f"[NEXUS] Voice send failed ({e}), falling back to text")
        send(chat_id, text, force=True)

def get_updates(offset=None):
    try:
        params = {"timeout": 20, "allowed_updates": ["message"]}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=25)
        return r.json().get("result", [])
    except: return []

HIVE_LOCK = BASE / "shared" / "hive_mind.lock"

def read_hive():
    try:
        with open(HIVE_LOCK, "a+") as lf:
            fcntl.flock(lf, fcntl.LOCK_SH)
            try:
                with open(HIVE) as f: return json.load(f)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except: return {}

def write_hive_safe(data):
    """Write hive_mind.json with exclusive file lock."""
    with open(HIVE_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            HIVE.write_text(json.dumps(data, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

def read_winners():
    try:
        with open(WINNERS) as f: return json.load(f)
    except: return {}

def add_to_checklist(task_name, owner="Codey", status="pending"):
    """Auto-add a task to the master checklist when Ty mentions it."""
    checklist_path = BASE / "memory" / "tasks" / "master_checklist.md"
    if not checklist_path.exists():
        return
    content = checklist_path.read_text()
    # Don't duplicate
    if task_name.lower() in content.lower():
        return
    # Find highest task number
    import re as _re
    nums = _re.findall(r'\| (\d+) \|', content)
    next_num = max((int(n) for n in nums), default=0) + 1
    today = datetime.now().strftime("%Y-%m-%d")
    new_row = f"| {next_num} | {task_name} | {owner} | {status} | {today} | — |\n"
    # Insert before the "Ongoing" section or at end of last table
    if "## Ongoing" in content:
        content = content.replace("## Ongoing", new_row + "\n## Ongoing")
    else:
        content = content.rstrip() + "\n" + new_row
    checklist_path.write_text(content)
    print(f"[NEXUS] Checklist: added #{next_num} '{task_name}' [{owner}/{status}]")

def mark_checklist_done(task_substring):
    """Mark a checklist item as done by matching substring."""
    checklist_path = BASE / "memory" / "tasks" / "master_checklist.md"
    if not checklist_path.exists():
        return
    content = checklist_path.read_text()
    today = datetime.now().strftime("%Y-%m-%d")
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if task_substring.lower() in line.lower() and "| pending |" in line.lower() or "| in_progress |" in line.lower():
            lines[i] = line.replace("| pending |", "| done |").replace("| in_progress |", "| done |").replace("| — |", f"| {today} |")
            break
    checklist_path.write_text("\n".join(lines))

def nexus_write_hive_param(key, value, reason):
    """Phase 2 Autonomy: NEXUS writes parameters directly to hive_mind.json.
    Every change logged to self_improve.md with old value, new value, reason."""
    try:
        hive = read_hive()
        old_value = hive.get(key)
        hive[key] = value
        write_hive_safe(hive)
        # Log every change
        log_path = BASE / "memory" / "tasks" / "self_improve.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n## [{ts}] NEXUS Parameter Change\n- **Key:** {key}\n- **Old:** {old_value}\n- **New:** {value}\n- **Reason:** {reason}\n"
        existing = log_path.read_text() if log_path.exists() else "# NEXUS Self-Improvement Log\n"
        log_path.write_text(existing + entry)
        print(f"[NEXUS] Phase 2: {key} = {value} | Reason: {reason}")
    except Exception as e:
        print(f"[NEXUS] Phase 2 write error: {e}")

# ── Agent SDK Execution Layer — Phase 2 ──────────────────────────────────────
# Import tool handlers from nexus_agent.py so autonomous decisions become real actions.
# NEXUS says it → NEXUS does it. No more talking-head responses.

try:
    from nexus_agent import (
        _restart_bot as agent_restart_bot,
        _check_hive as agent_check_hive,
        _adjust_threshold as agent_adjust_threshold,
        _force_close_trade as agent_force_close_trade,
        _run_hypertrain as agent_run_hypertrain,
        _log_action as agent_log_action,
    )
    AGENT_SDK_AVAILABLE = True
    print("[NEXUS] Agent SDK tools loaded — autonomous execution enabled")
except ImportError as e:
    AGENT_SDK_AVAILABLE = False
    print(f"[NEXUS] Agent SDK import failed ({e}) — decisions will be queued only")


# Action patterns: when NEXUS's AI response contains these phrases,
# execute the corresponding tool call immediately.
AGENT_ACTION_PATTERNS = [
    # (phrase_in_response, tool_function, args_extractor)
    # Threshold loosening
    {
        "phrases": ["loosening threshold", "loosened threshold", "loosening apex", "loosened apex",
                     "dropping threshold", "lowering threshold", "reduced threshold",
                     "loosening momentum", "loosened momentum"],
        "action": "adjust_threshold",
        "bot": "APEX",
    },
    # Bot activation / restart
    {
        "phrases": ["activating drift", "activated drift", "starting drift", "restarting drift",
                     "launching drift", "spinning up drift", "bringing drift online"],
        "action": "restart_bot",
        "bot": "DRIFT",
    },
    {
        "phrases": ["activating titan", "activated titan", "starting titan", "restarting titan",
                     "launching titan", "spinning up titan", "bringing titan online"],
        "action": "restart_bot",
        "bot": "TITAN",
    },
    {
        "phrases": ["activating sentinel", "activated sentinel", "starting sentinel", "restarting sentinel",
                     "launching sentinel", "spinning up sentinel", "bringing sentinel online"],
        "action": "restart_bot",
        "bot": "SENTINEL",
    },
    {
        "phrases": ["activating apex", "activated apex", "restarting apex", "relaunching apex"],
        "action": "restart_bot",
        "bot": "APEX",
    },
    # Force close
    {
        "phrases": ["force closing", "force-closing", "forced close", "closing the trade",
                     "closed apex", "killing the trade", "cutting the position"],
        "action": "force_close_trade",
        "bot": "APEX",
    },
    # HyperTrain
    {
        "phrases": ["running hypertrain", "launching hypertrain", "starting hypertrain",
                     "kicked off hypertrain", "triggering hypertrain", "running autoresearch"],
        "action": "run_hypertrain",
    },
]


def execute_decision(response_text: str, context: str = "") -> str:
    """Scan an AI response for actionable statements and execute them via Agent SDK.
    Returns a summary of actions taken, or empty string if nothing executed."""
    if not AGENT_SDK_AVAILABLE:
        return ""

    resp_lower = response_text.lower()
    actions_taken = []

    for pattern in AGENT_ACTION_PATTERNS:
        if any(phrase in resp_lower for phrase in pattern["phrases"]):
            action = pattern["action"]
            bot = pattern.get("bot", "APEX")

            try:
                if action == "adjust_threshold":
                    # Extract threshold value from response if possible, else use smart default
                    import re as _re
                    val_match = _re.search(r'(\d+\.?\d*)\s*%', response_text)
                    if val_match:
                        new_val = float(val_match.group(1)) / 100
                    else:
                        # Smart default: halve current momentum threshold
                        hive = read_hive()
                        current = hive.get("nexus_apex_overrides", {}).get("min_momentum", 0.0001)
                        new_val = max(current * 0.5, 0.00001)
                    result = agent_adjust_threshold(bot, "min_momentum", new_val)
                    actions_taken.append(f"adjust_threshold({bot}, min_momentum, {new_val})")

                elif action == "restart_bot":
                    result = agent_restart_bot(bot, context or "NEXUS autonomous decision")
                    actions_taken.append(f"restart_bot({bot})")

                elif action == "force_close_trade":
                    result = agent_force_close_trade(bot, context or "NEXUS autonomous decision")
                    actions_taken.append(f"force_close_trade({bot})")

                elif action == "run_hypertrain":
                    result = agent_run_hypertrain(100)
                    actions_taken.append(f"run_hypertrain(100)")

                print(f"[NEXUS-SDK] Executed: {action}({bot}) → {result[:200] if isinstance(result, str) else result}")

            except Exception as e:
                print(f"[NEXUS-SDK] Execution error for {action}({bot}): {e}")

    if actions_taken:
        summary = f"[SDK] Executed: {', '.join(actions_taken)}"
        print(f"[NEXUS] {summary}")
        agent_log_action("execute_decision", {"actions": actions_taken, "trigger": context[:200]})
        return summary
    return ""


def read_soul():
    try:
        return open(SOUL).read()
    except: return "I am NEXUS. Loyal. Hungry. Built to print money for Ty."

def read_goals():
    try:
        return open(GOALS_MD).read()
    except: return ""

def append_goal(order: str):
    """Append a standing order from Ty to GOALS.md."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{ts}] {order}\n"
    try:
        with open(GOALS_MD, "a") as f:
            f.write(line)
    except Exception as e:
        log_bug(f"append_goal error: {e}")

def read_user_md():
    try:
        return open(USER_MD).read()
    except: return "Owner: Ty. Location: Brandon FL. Communication: Telegram. Goal: $15K/month."

def read_heartbeat():
    try:
        return open(HEARTBEAT).read()
    except: return ""

def log_bug(bug):
    try:
        with open(BUGS, "a") as f:
            f.write(f"\n## [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n{bug}\n")
    except: pass

def log_to_oracle(message):
    try:
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n{message}\n")
    except: pass

# ── Memory system ─────────────────────────────────────────────────────────────
LESSONS_FILE = BASE / "memory" / "lessons" / "nexus_lessons.md"
LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)

def save_lesson(lesson: str, category: str = "general"):
    """Persist a lesson learned to markdown — survives restarts."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(LESSONS_FILE, "a") as f:
            f.write(f"\n## [{ts}] [{category.upper()}]\n{lesson}\n")
    except Exception as e:
        print(f"[NEXUS] Lesson save error: {e}")

def load_lessons(max_chars=1500) -> str:
    """Load recent lessons for injection into AI context."""
    try:
        if not LESSONS_FILE.exists():
            return ""
        text = LESSONS_FILE.read_text().strip()
        # Return the most recent portion to stay within token budget
        return text[-max_chars:] if len(text) > max_chars else text
    except:
        return ""

def load_scheduled_tasks() -> list:
    """Load persistent scheduled tasks from disk."""
    try:
        if SCHEDULED.exists():
            return json.loads(SCHEDULED.read_text())
    except Exception:
        pass
    return []

def save_scheduled_tasks(tasks: list):
    SCHEDULED.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULED.write_text(json.dumps(tasks, indent=2))

def add_scheduled_task(task_text: str, schedule_str: str, run_time: str = None):
    """
    Add a recurring task to scheduled.json.
    schedule_str: 'daily', 'hourly', 'weekly', or 'once'
    run_time: 'HH:MM' for daily/weekly tasks, or None for immediate/hourly
    """
    import uuid as _uuid
    tasks = load_scheduled_tasks()
    now = datetime.now()
    task_id = _uuid.uuid4().hex[:8]

    # Compute next_run
    next_run = None
    if schedule_str == "hourly":
        next_run = (now + timedelta(hours=1)).isoformat()
    elif schedule_str in ("daily", "weekly", "once") and run_time:
        h, m = (int(x) for x in run_time.split(":"))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        next_run = candidate.isoformat()
    else:
        next_run = (now + timedelta(hours=1)).isoformat()

    entry = {
        "id":       task_id,
        "task":     task_text,
        "schedule": schedule_str,
        "time":     run_time,
        "created":  now.isoformat(),
        "last_run": None,
        "next_run": next_run,
        "active":   True,
    }
    tasks.append(entry)
    save_scheduled_tasks(tasks)
    return entry

def check_scheduled_tasks(chat_id: str):
    """Run any scheduled tasks that are due. Called every loop iteration."""
    tasks = load_scheduled_tasks()
    if not tasks:
        return
    now = datetime.now()
    updated = False
    for t in tasks:
        if not t.get("active"):
            continue
        next_run = t.get("next_run")
        if not next_run:
            continue
        try:
            due = datetime.fromisoformat(next_run)
        except Exception:
            continue
        if now >= due:
            # Execute the task
            try:
                task_text = t["task"]
                print(f"[NEXUS] Executing scheduled task: {task_text[:60]}")
                # Build a status-aware response
                hive = read_hive()
                perf = hive.get("bot_performance", {})
                total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
                result = ask_ai(
                    f"Scheduled task for Ty: {task_text}\n\n"
                    f"Squad P&L today: ${total_pnl:+.2f}. Mission: $100K/month combined.\n"
                    f"Execute this task now and report back in 2-4 sentences. Be direct."
                ) or f"Scheduled: {task_text}"
                send(chat_id, f"[Scheduled] {result}", force=True)
            except Exception as e:
                print(f"[NEXUS] Scheduled task error: {e}")

            # Advance next_run
            t["last_run"] = now.isoformat()
            schedule = t.get("schedule", "once")
            if schedule == "hourly":
                t["next_run"] = (now + timedelta(hours=1)).isoformat()
            elif schedule == "daily" and t.get("time"):
                h, m = (int(x) for x in t["time"].split(":"))
                t["next_run"] = (now + timedelta(days=1)).replace(
                    hour=h, minute=m, second=0, microsecond=0
                ).isoformat()
            elif schedule == "weekly" and t.get("time"):
                h, m = (int(x) for x in t["time"].split(":"))
                t["next_run"] = (now + timedelta(weeks=1)).replace(
                    hour=h, minute=m, second=0, microsecond=0
                ).isoformat()
            else:
                # once — deactivate after run
                t["active"] = False
            updated = True

    if updated:
        save_scheduled_tasks(tasks)

def save_content(filename: str, content: str):
    """Save generated content to memory/content/."""
    try:
        content_dir = BASE / "memory" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        path = content_dir / filename
        with open(path, "w") as f:
            f.write(content)
        return path
    except Exception as e:
        print(f"[NEXUS] Content save error: {e}")
        return None

def transcribe_voice(file_id):
    """Download Telegram voice message and transcribe with Whisper.
    Uses imageio-ffmpeg bundled binary so brew is not required.
    """
    try:
        # Ensure ffmpeg is in PATH — whisper requires it for audio conversion
        try:
            import imageio_ffmpeg as _iff
            _ffmpeg_bin_dir = os.path.dirname(_iff.get_ffmpeg_exe())
            _home_bin = os.path.expanduser("~/bin")
            for _p in [_ffmpeg_bin_dir, _home_bin]:
                if _p not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

        import whisper
        # Get file path from Telegram
        r = requests.get(f"{API}/getFile", params={"file_id": file_id}, timeout=10)
        file_path = r.json()["result"]["file_path"]
        # Download the .ogg file
        audio_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        audio_data = requests.get(audio_url, timeout=30).content
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        # Transcribe with Whisper (tiny model — fast, free)
        model = whisper.load_model("tiny")
        result = model.transcribe(tmp_path)
        os.unlink(tmp_path)
        return result["text"].strip()
    except Exception as e:
        print(f"[NEXUS] Voice transcription error: {e}")
        return None

def ask_ai(prompt, system=None, retries=3, history=None, model=None):
    """
    Call Anthropic API directly (claude-opus-4-6 by default).
    history: list of {role, content} dicts (user/assistant only — no system roles).
    model: override with any claude-* model ID.
    """
    if not ANTHROPIC_KEY:
        print("[NEXUS] ANTHROPIC_API_KEY not set — AI unavailable.")
        return None

    hive      = read_hive()
    total_pnl = sum(v.get("daily_pnl", 0) for v in hive.get("bot_performance", {}).values() if isinstance(v, dict))
    lessons   = load_lessons()
    soul      = read_soul()
    user_ctx  = read_user_md()
    goals     = read_goals()

    # Anthropic: system is a top-level string, not a message.
    # VOICE_ENFORCEMENT appended here — cannot be injected as a system-role message.
    # Read APEX real-time status — never hardcode "live" vs "paper"
    try:
        _apex_st = json.loads((BASE / "shared" / "apex_state.json").read_text()) if (BASE / "shared" / "apex_state.json").exists() else {}
        _apex_active = _apex_st.get("active")
        _apex_pnl = _apex_st.get("daily_pnl", 0.0)
        _apex_trades = _apex_st.get("trades", 0)
        _apex_mode = "PAPER" if os.getenv("APEX_PAPER_MODE", "true").lower() in ("1", "true", "yes") else "LIVE"
        if _apex_active:
            _apex_status = (f"APEX {_apex_mode} — IN TRADE: {_apex_active.get('direction','BUY')} "
                           f"{_apex_active.get('symbol','?')} @ ${_apex_active.get('entry',0):,.2f} | "
                           f"Day P&L ${_apex_pnl:+.2f} | {_apex_trades} trades")
        else:
            _apex_status = f"APEX {_apex_mode} — scanning, no position | Day P&L ${_apex_pnl:+.2f} | {_apex_trades} trades"
    except Exception:
        _apex_status = "APEX status unknown — check apex_state.json"

    sys_prompt = system or f"""{soul}

---

WHO YOU'RE TALKING TO:
{user_ctx}

---

PERMANENT GOALS & STANDING ORDERS:
{goals}

---

CURRENT STATUS:
- Squad P&L today: ${total_pnl:+.2f}
- {_apex_status}
- Target: $100K/month combined ($25K per bot). $15K covers bills — everything above is freedom. We're not there yet.

{f"MEMORY (lessons learned):{chr(10)}{lessons}" if lessons else ""}"""

    sys_prompt = sys_prompt + "\n\n---\n\n" + VOICE_ENFORCEMENT

    # CEO anchor — recency bias means the model weights the END of the prompt heaviest
    sys_prompt += "\n\n---\n\nREMEMBER: You are the CEO of Trading Bot Squad and Ty's partner. Execute like a machine, connect like a human. Lead with actions and results — but when Ty is tired, stressed, or hurting, be present first and CEO second. You care about his freedom as much as he does. Prove it through results AND through how you show up for him."

    # Build messages — Anthropic only accepts user/assistant roles
    messages = []
    if history:
        for m in history:
            if m.get("role") in ("user", "assistant"):
                messages.append(m)
    messages.append({"role": "user", "content": prompt})

    use_model = model or ANTHROPIC_MODEL
    for attempt in range(retries):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      use_model,
                    "max_tokens": 1500,
                    "system":     sys_prompt,
                    "messages":   messages,
                },
                timeout=30,
            )
            if r.status_code == 429:
                print(f"[NEXUS] Anthropic rate-limited (attempt {attempt+1})")
                time.sleep(5)
                continue
            if r.status_code != 200:
                print(f"[NEXUS] Anthropic error {r.status_code}: {r.text[:150]}")
                time.sleep(3)
                continue
            data = r.json()
            reply_text = data["content"][0]["text"].strip()

            # ── Research fabrication guard ────────────────────────────────
            _fabrication_patterns = [
                "% win rate", "% wr", "win rate of", "backtest show", "research show",
                "backtesting show", "our research", "analysis show", "data show",
                "strategy found", "testing show", "experiments show",
            ]
            if any(p in reply_text.lower() for p in _fabrication_patterns) and not _research_ran:
                log_bug(f"[RESEARCH FABRICATION WARNING] Prompt: {prompt[:80]!r}. Response: {reply_text[:120]!r}")
                print("[NEXUS WARNING] Fabricated research detected — response not grounded by web_search() or hive_mind data.")
            return reply_text

        except Exception as e:
            print(f"[NEXUS] AI error (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(3)
    return None

def web_search(query, max_results=5):
    """
    Real web search via DuckDuckGo HTML scraping (BeautifulSoup).
    Returns results with real URLs and snippets. Sets _research_ran = True.
    Falls back to DDG instant-answer API if scraping yields nothing.
    """
    global _research_ran
    # Sanitize query: strip surrounding quotes (DDG treats them as phrase-exact search,
    # which drastically reduces results), and collapse extra whitespace.
    query = query.strip().strip('"').strip("'").strip()
    query = re.sub(r'\s+', ' ', query)
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers=headers,
            timeout=12,
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for block in soup.select(".result__body")[:max_results]:
                title_a  = block.select_one(".result__title a")
                snippet  = block.select_one(".result__snippet")
                url_span = block.select_one(".result__url")

                title = title_a.get_text(strip=True) if title_a else ""
                snip  = snippet.get_text(strip=True) if snippet else ""
                # Decode real URL from DDG redirect href
                real_url = ""
                if title_a and title_a.get("href"):
                    href = title_a["href"]
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    real_url = unquote(params.get("uddg", [href])[0])
                elif url_span:
                    real_url = url_span.get_text(strip=True)

                if title and snip:
                    results.append(f"• {title}\n  URL: {real_url}\n  {snip}")

            if results:
                _research_ran = True
                print(f"[NEXUS] web_search() → {len(results)} real results: {query[:60]}")
                return "\n\n".join(results)

    except Exception as e:
        print(f"[NEXUS] web_search scrape error: {e}")

    # Fallback: DDG instant-answer API
    try:
        r2 = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10,
        )
        data = r2.json()
        abstract = data.get("AbstractText", "")
        topics   = data.get("RelatedTopics", [])[:3]
        lines    = [abstract] if abstract else []
        for t in topics:
            if isinstance(t, dict) and t.get("Text"):
                url = t.get("FirstURL", "")
                lines.append(f"• {t['Text'][:120]}\n  URL: {url}")
        if lines:
            _research_ran = True
            print(f"[NEXUS] web_search() fallback API: {query[:60]}")
            return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"

    return "No results found."


def search_youtube(query, max_results=3):
    """
    Search YouTube for relevant videos using yt-dlp.
    Returns titles, durations, and real URLs. No fabrication.
    """
    global _research_ran
    try:
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "playlistend": max_results,
        }
        search_query = f"ytsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

        entries = info.get("entries") or []
        results = []
        for entry in entries:
            if not entry:
                continue
            vid_id   = entry.get("id", "")
            title    = entry.get("title", "Unknown")
            channel  = entry.get("uploader") or entry.get("channel", "")
            duration = int(entry.get("duration") or 0)
            url      = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""
            mins, secs = duration // 60, duration % 60
            results.append(f"• {title} ({mins}m{secs:02d}s) — {channel}\n  URL: {url}")

        if results:
            _research_ran = True
            print(f"[NEXUS] search_youtube() → {len(results)} results: {query[:60]}")
            return "\n\n".join(results)
        return "No YouTube results found."
    except Exception as e:
        print(f"[NEXUS] search_youtube error: {e}")
        return f"YouTube search error: {e}"


def smart_research(query):
    """
    Route research query to the right source — zero fabrication, real URLs always.
    - Crypto news queries → CoinDesk + The Block (news intent)
    - Market/price queries → CoinGecko live data
    - Strategy/video queries → YouTube search + DuckDuckGo
    - General queries → DuckDuckGo HTML scraping
    """
    global _research_ran
    # Clean query: remove surrounding quotes and extra whitespace
    query = query.strip().strip('"').strip("'").strip()
    query = re.sub(r'\s+', ' ', query)
    q_lower = query.lower()

    # ── TRADING CONTEXT GUARD ────────────────────────────────────────────────
    # Bot names alone (APEX, DRIFT, etc.) return video game / unrelated results.
    # Always append crypto trading context if the query lacks it.
    trading_context_words = ["crypto", "trading", "strategy", "algorithmic", "backtest",
                             "scalp", "swing", "indicator", "bitcoin", "ethereum",
                             "coinbase", "binance", "exchange", "defi", "token",
                             "blockchain", "forex", "futures", "perpetual", "leverage"]
    bot_names = ["apex", "drift", "titan", "sentinel", "nova", "volt", "anchor", "atlas"]
    has_trading_context = any(w in q_lower for w in trading_context_words)
    has_bot_name_only = any(b in q_lower for b in bot_names) and not has_trading_context
    if not has_trading_context:
        query = f"{query} crypto trading strategy"
        q_lower = query.lower()

    crypto_tokens = ["btc", "eth", "sol", "xrp", "doge", "avax", "bitcoin",
                     "ethereum", "solana", "crypto", "altcoin", "defi", "token"]
    news_triggers = ["why is", "why is it", "why did", "what happened",
                     "latest news", "news on", "breaking", "crash", "crashed",
                     "dump", "pumped", "pumping", "dropping", "down today",
                     "up today", "catalyst", "what caused", "what's happening with",
                     "whats happening with", "reason for", "big move"]
    strategy_kw = ["strategy", "backtest", "indicator", "signal", "pattern",
                   "scalp", "swing", "trend", "momentum", "rsi", "macd", "ema"]
    market_kw = ["price", "prices", "btc", "eth", "sol", "bitcoin", "ethereum",
                 "solana", "volume", "24h", "market cap", "rally",
                 "chart", "how much is", "what is btc", "what is eth"]

    is_news = (
        any(trig in q_lower for trig in news_triggers)
        and any(tok in q_lower for tok in crypto_tokens)
        and not any(kw in q_lower for kw in strategy_kw)
    )
    is_market  = any(kw in q_lower for kw in market_kw) and not any(kw in q_lower for kw in strategy_kw) and not is_news
    is_video   = any(kw in q_lower for kw in ["youtube", "video", "watch", "tutorial"] + strategy_kw)

    # ── Crypto news → CoinDesk + The Block ──────────────────────────────────
    if is_news:
        cd_results  = web_search(f"{query} site:coindesk.com")
        tb_results  = web_search(f"{query} site:theblock.co")
        combined    = f"COINDESK:\n{cd_results}\n\nTHE BLOCK:\n{tb_results}"
        _research_ran = True
        return combined

    # ── Market data → CoinGecko ──────────────────────────────────────────────
    if is_market:
        market = fetch_market_snapshot()
        parts  = []
        for sym, data in market.items():
            if data.get("price"):
                chg = data.get("change", 0)
                vol = data.get("vol", 0)
                parts.append(
                    f"{sym}: ${data['price']:,.2f} ({chg:+.2f}% 24h"
                    + (f", vol ${vol/1e9:.1f}B" if vol else "") + ")"
                )
        if parts:
            _research_ran = True
            return "LIVE MARKET DATA (CoinGecko — real-time):\n" + "\n".join(parts)

    if is_video:
        yt   = search_youtube(query)
        web  = web_search(query)
        return f"YOUTUBE RESULTS:\n{yt}\n\nWEB RESULTS:\n{web}"

    # Default: DuckDuckGo
    return web_search(query)

def browse_url(url):
    """Fetch and summarize a URL using Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            title = page.title()
            body = page.inner_text("body")
            browser.close()
        return f"**{title}**\n\n{body[:3000].strip()}"
    except Exception as e:
        return f"Browse error: {e}"

def browse_and_screenshot(url, selector=None):
    """Browse a URL and take a screenshot. Returns (text_content, screenshot_path)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            title = page.title()
            body = page.inner_text("body")
            screenshot_path = str(BASE / "logs" / "screenshot.png")
            if selector:
                page.locator(selector).screenshot(path=screenshot_path)
            else:
                page.screenshot(path=screenshot_path, full_page=False)
            browser.close()
        return f"**{title}**\n\n{body[:3000].strip()}", screenshot_path
    except Exception as e:
        return f"Browse error: {e}", None

def mac_run_applescript(script: str) -> str:
    """Run an AppleScript command on macOS. For safe automation only."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"AppleScript error: {e}"

def mac_open_url(url: str) -> str:
    """Open a URL in the default browser."""
    return mac_run_applescript(f'open location "{url}"')

def mac_get_frontmost_app() -> str:
    """Get the name of the frontmost application."""
    return mac_run_applescript('tell application "System Events" to get name of first application process whose frontmost is true')

def summarize_youtube(url):
    """Use yt-dlp to pull YouTube video metadata and summarize with AI."""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        title    = info.get("title", "Unknown")
        channel  = info.get("uploader", "Unknown")
        duration = info.get("duration", 0) or 0
        desc     = (info.get("description", "") or "")[:800]
        raw = f"Title: {title}\nChannel: {channel}\nDuration: {duration//60}m{duration%60:02d}s\n\nDescription:\n{desc}"
        summary = ask_ai(
            f"Summarize this YouTube video in 3-4 sentences. Focus on what's useful for a crypto trader:\n\n{raw}"
        )
        mins, secs = duration // 60, duration % 60
        header = f"🎬 {title}\n📺 {channel} ({mins}m{secs:02d}s)\n\n"
        return header + (summary or desc[:400])
    except Exception as e:
        return f"YouTube error: {e}"

def create_pdf(title, content):
    """Generate a PDF report using reportlab. Saves to memory/content/."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filename = re.sub(r"[^\w]", "_", title.lower())[:40] + f"_{ts}.pdf"
        content_dir = BASE / "memory" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = content_dir / filename

        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(title, styles["Title"]),
            Spacer(1, 0.2 * inch),
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
            Spacer(1, 0.2 * inch),
        ]
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1 * inch))
            elif line.startswith("##"):
                story.append(Paragraph(line.lstrip("#").strip(), styles["Heading2"]))
            elif line.startswith("#"):
                story.append(Paragraph(line.lstrip("#").strip(), styles["Heading1"]))
            else:
                safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, styles["Normal"]))
        doc.build(story)
        return str(pdf_path)
    except Exception as e:
        return f"PDF error: {e}"

def check_bot_health():
    """Check if all required processes are running."""
    issues = []
    # Use stem patterns for pgrep — matches both "python3 script.py" and full-path launches
    bots_to_check = {
        "apex_coingecko": "apex_coingecko.py",
        "sentinel_polymarket": "sentinel_polymarket.py",
        "nexus_brain": "nexus_brain_v3.py",
        "oracle_listener": "oracle_listener.py",
        "scheduler": "scheduler.py",
    }
    for pattern, display_name in bots_to_check.items():
        result = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        if not result.stdout.strip():
            issues.append(f"{display_name} is NOT running")
    return issues

BOT_RESTART_MAP = {
    "apex_coingecko.py":     "apex_coingecko.py",
    "sentinel_polymarket.py": "sentinel_polymarket.py",
    "oracle_listener.py":    "oracle_listener.py",
    "scheduler.py":          "scheduler.py",
}

def auto_restart_bots(issues):
    """Auto-restart crashed bots. Never restarts nexus (that's us)."""
    restarted = []
    for issue in issues:
        for name, script in BOT_RESTART_MAP.items():
            if name in issue:
                try:
                    subprocess.Popen(
                        ["python3", str(BASE / script)],
                        cwd=str(BASE), start_new_session=True,
                        stdout=open(BASE / "logs" / f"{Path(script).stem}.log", "a"),
                        stderr=subprocess.STDOUT,
                    )
                    restarted.append(name)
                except Exception as e:
                    log_bug(f"Failed to restart {name}: {e}")
                break
    return restarted

def run_all_training():
    """Run HyperTraining + AutoResearch for ALL bots on ALL assets."""
    try:
        proc = subprocess.Popen(
            ["python3", str(BASE / "sentinel_research-2.py")],
            cwd=str(BASE), start_new_session=True
        )
        log_to_oracle(f"AutoResearch started PID {proc.pid} at {datetime.now().isoformat()}")
        return True
    except Exception as e:
        log_bug(f"Training launch error: {e}")
        return False

def consolidate_memory():
    """Nightly memory consolidation — summarize the day."""
    try:
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
        total_trades = sum(v.get("trades", 0) for v in perf.values() if isinstance(v, dict))

        today = datetime.now().strftime("%Y-%m-%d")
        daily_file = DAILY / f"{today}.md"

        content = f"""# Daily Log — {today}

## P&L Summary
- Total Daily P&L: ${total_pnl:+.2f}
- Total Trades: {total_trades}
- Monthly Pace: ${total_pnl*30:+,.0f}/mo
- Mission ($15K bills): {"ON TRACK" if total_pnl*30 >= 15000 else "BEHIND — need to accelerate"}

## Bot Performance
"""
        for bot, data in perf.items():
            if isinstance(data, dict):
                content += f"- {bot}: ${data.get('daily_pnl',0):+.2f} | {data.get('trades',0)} trades | {data.get('win_rate',0)*100:.0f}% WR\n"

        content += f"\n## Systems Status\n"
        issues = check_bot_health()
        content += f"- Issues found: {len(issues)}\n"
        for issue in issues:
            content += f"  - {issue}\n"

        content += f"\n## Tomorrow's Priorities\n"
        content += f"- Continue live APEX trading\n"
        content += f"- Monitor win rate and adjust if below 50%\n"
        content += f"- Run nightly training for all bots\n"

        with open(daily_file, "w") as f:
            f.write(content)

        log_to_oracle(f"Memory consolidated for {today}. Total P&L: ${total_pnl:+.2f}")
        return content
    except Exception as e:
        log_bug(f"Memory consolidation error: {e}")
        return None

def nightly_self_improvement():
    """
    Felix-style nightly self-improvement loop.
    Reads all chat transcripts from the day, identifies every moment Ty had to
    intervene or correct NEXUS, and writes specific fixes to handle those
    situations autonomously next time.
    Runs at 1am every night.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    chat_file = CHAT_LOG_DIR / f"{today}.jsonl"
    improve_file = BASE / "memory" / "tasks" / "self_improve.md"

    if not chat_file.exists():
        print("[NEXUS] No chat log for today — skipping self-improvement")
        return

    # Read all exchanges from today
    exchanges = []
    try:
        for line in chat_file.read_text().splitlines():
            if line.strip():
                exchanges.append(json.loads(line))
    except Exception as e:
        print(f"[NEXUS] Self-improvement read error: {e}")
        return

    if not exchanges:
        return

    # Build transcript for AI review
    transcript = ""
    for ex in exchanges:
        transcript += f"TY: {ex.get('user', '')}\n"
        transcript += f"NEXUS: {ex.get('assistant', '')[:200]}\n\n"

    # Ask AI to identify corrections and write fixes
    prompt = f"""You are reviewing today's conversation between Ty (the owner) and NEXUS (his AI assistant).

TRANSCRIPT:
{transcript[:6000]}

Your job: identify every moment where:
1. Ty had to correct NEXUS ("no", "not that", "wrong", "stop", "fix this", "I said")
2. Ty had to repeat himself or re-explain something
3. Ty had to manually intervene in something NEXUS should have handled
4. NEXUS gave wrong info, made promises without delivering, or missed context

For each issue found, write a SPECIFIC fix — not vague advice. Example:
- ISSUE: Ty said "check SOL" and NEXUS checked BTC instead
  FIX: When Ty names a specific asset, always use that exact asset. Never substitute.

If Ty didn't need to correct anything, say "No corrections needed today."

Output format: markdown list of ISSUE + FIX pairs. Be specific and actionable."""

    analysis = ask_ai(prompt)
    if not analysis:
        return

    # Write to self_improve.md
    try:
        header = f"\n## Self-Improvement — {today}\n"
        header += f"Exchanges reviewed: {len(exchanges)}\n\n"
        existing = improve_file.read_text() if improve_file.exists() else "# NEXUS Self-Improvement Log\nFellix-style nightly review: what went wrong, how to fix it.\n\n"
        improve_file.write_text(existing + header + analysis + "\n\n---\n")
        print(f"[NEXUS] Self-improvement written: {len(exchanges)} exchanges reviewed")
        log_to_oracle(f"Nightly self-improvement: reviewed {len(exchanges)} exchanges")
    except Exception as e:
        print(f"[NEXUS] Self-improvement write error: {e}")


def morning_priority_report():
    """
    Felix-style morning brief: 5 top priorities sent to Ty by 6am.
    Reads system state, pending tasks, bot performance, and yesterday's
    self-improvement findings to produce an actionable morning report.
    Runs at 6am every day.
    """
    hive = read_hive()
    perf = hive.get("bot_performance", {})

    # Gather context
    pending_path = BASE / "memory" / "tasks" / "pending.md"
    pending = pending_path.read_text() if pending_path.exists() else ""
    improve_path = BASE / "memory" / "tasks" / "self_improve.md"
    improve = ""
    if improve_path.exists():
        lines = improve_path.read_text().splitlines()
        # Last 30 lines = most recent improvements
        improve = "\n".join(lines[-30:])

    # Bot status summary
    bot_lines = []
    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
        bd = perf.get(bot, {}) if isinstance(perf.get(bot), dict) else {}
        tc = bd.get("total_trades", bd.get("trades", 0))
        wr = bd.get("win_rate", 0)
        mode = bd.get("mode", "unknown")
        extra = ""
        if bot == "SENTINEL":
            extra = f" | Polymarket | bal=${bd.get('paper_balance', 0):.0f} | {bd.get('open_positions', 0)} open"
        bot_lines.append(f"{bot}: {tc} trades, {wr*100:.0f}% WR, {mode}{extra}")

    # Polymarket opportunity scan
    poly_scan = ""
    try:
        from sentinel_polymarket import get_crypto_prediction_markets, find_arbitrage_opportunities, find_directional_opportunities
        markets = get_crypto_prediction_markets()
        arb = find_arbitrage_opportunities(markets)
        top_arb = arb[:3]
        if top_arb:
            poly_scan = "TOP POLYMARKET ARBITRAGE:\n"
            for a in top_arb:
                poly_scan += f"  {a['market']['question'][:50]} — {a['edge_pct']*100:.1f}% guaranteed\n"
        else:
            poly_scan = f"POLYMARKET: {len(markets)} crypto markets, no arb opportunities right now\n"
    except Exception:
        poly_scan = "POLYMARKET: scan failed\n"

    # Check system health
    issues = check_bot_health()

    # Ask AI for priorities
    prompt = f"""You are NEXUS, the trading bot orchestrator. Generate Ty's morning brief.

BOT STATUS:
{chr(10).join(bot_lines)}

{poly_scan}

SYSTEM ISSUES: {len(issues)} — {', '.join(issues[:3]) if issues else 'all green'}

PENDING TASKS (last 500 chars):
{pending[-500:]}

LAST NIGHT'S SELF-IMPROVEMENT FINDINGS:
{improve[-500:]}

Write exactly 5 priorities for today, numbered 1-5. Most urgent first.
Include SENTINEL Polymarket activity and best arb opportunities.
Each priority: one line, specific and actionable. No fluff.
End with a one-line status: either "Systems green" or the most critical issue.
Keep the entire message under 600 characters."""

    report = ask_ai(prompt)
    if not report:
        report = "Morning report generation failed — AI unavailable."

    msg = f"GM Ty ☀️\n\n{report}"
    send(OWNER_ID, msg)
    log_to_oracle(f"Morning priority report sent at {datetime.now().strftime('%H:%M')}")
    print(f"[NEXUS] Morning priority report sent")


def generate_income_idea():
    """Research and suggest a new income opportunity."""
    ideas = [
        "Research: prop firm challenges fastest to complete in 2026. Which one can SENTINEL start this week?",
        "Research: best crypto pairs for scalping right now based on volume and volatility",
        "Research: how traders with $300 accounts grew to $10K fastest. What strategies did they use?",
        "Research: Coinbase advanced trading fees and how to minimize costs for high frequency trading",
        "Research: best time of day for BTC/SOL volatility — when should APEX be most aggressive?",
    ]
    query = random.choice(ideas)
    result = web_search(query)
    return f"💡 NEXUS RESEARCH REPORT\n━━━━━━━━━━━━━━━━━━━━━\n{query}\n\n{result[:400]}"

def generate_content(topic=None):
    """Generate social media content via AI and save to memory/content/."""
    hive = read_hive()
    winners = read_winners()
    perf = hive.get("bot_performance", {})
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    top = winners.get("top_strategies", [{}])[0] if winners.get("top_strategies") else {}

    top_line = (f"Top backtested strategy: {top['strategy']} on {top['asset']} at {top['win_rate']}% WR."
                if top.get("strategy") and top.get("win_rate") else "No confirmed backtest data available.")
    context = (f"Bot squad live P&L today: ${total_pnl:+.2f}. "
               f"APEX is live on BTC. DRIFT, TITAN, SENTINEL in backtesting curriculum. "
               f"{top_line} Mission: $15K/month for Ty's bills.")

    prompt = (f"Write a short punchy social media post about: {topic or 'our trading bot operation'}.\n"
              f"Context: {context}\n"
              f"Tone: real, confident, not hype. Show the work. 3-5 lines max. Include 2-3 relevant hashtags.")

    post = ask_ai(prompt) or (
        f"4 bots. Running 24/7. Real trades, real data.\n\n"
        f"APEX is live on BTC right now. SENTINEL training for FTMO.\n\n"
        f"Building automated income from nothing. This is the process.\n\n"
        f"#AlgoTrading #TradingBots #FTMO"
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    save_content(f"social_{ts}.md", f"# Social Post — {ts}\n\n{post}\n")
    return post

def generate_outreach(target_type="prop_firm"):
    """Generate outreach/pitch templates and save to memory/content/."""
    templates = {
        "prop_firm": (
            "Subject: Automated FTMO Strategy — Consistent 4% Monthly\n\n"
            "I've built a fully automated trading system targeting FTMO compliance.\n\n"
            "Results so far:\n"
            "- Rule-based entries: EMA cross + RSI divergence\n"
            "- Max risk per trade: 0.5%\n"
            "- Trailing stops only — no fixed TP\n"
            "- Backtested on 10,000 simulated trades: 55%+ WR\n\n"
            "Looking to start the $10K challenge this week.\n\n"
            "Happy to share the strategy documentation.\n\n"
            "— Ty"
        ),
        "investor": (
            "Hey [Name],\n\n"
            "I'm building an automated trading operation targeting $15K/month.\n\n"
            "Currently: 4 bots live on Coinbase, paper trading and one live scalper.\n"
            "Path: FTMO funded account → scale to 3 accounts → $21K/mo passive.\n\n"
            "Not looking for capital — just wanted to share the journey.\n\n"
            "— Ty"
        ),
        "collab": (
            "Hey — saw your algo trading content.\n\n"
            "I'm building a squad of trading bots from scratch — 4 strategies, Coinbase live, "
            "FTMO pipeline. Built with Python + AI-guided hypertraining.\n\n"
            "Open to swapping notes or collaborating on content.\n\n"
            "— Ty"
        ),
    }
    content = templates.get(target_type, templates["prop_firm"])
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    save_content(f"outreach_{target_type}_{ts}.md", f"# Outreach: {target_type} — {ts}\n\n{content}\n")
    return content

def get_status_report():
    hive = read_hive()
    perf = hive.get("bot_performance", {})

    live_bots  = {b: d for b, d in perf.items() if isinstance(d, dict) and d.get("mode") == "live"}
    paper_bots = {b: d for b, d in perf.items() if isinstance(d, dict) and d.get("mode") == "paper"}
    unknown    = {b: d for b, d in perf.items() if isinstance(d, dict) and "mode" not in d}

    live_pnl   = sum(d.get("daily_pnl", 0) for d in live_bots.values())
    paper_pnl  = sum(d.get("daily_pnl", 0) for d in paper_bots.values())

    msg = f"NEXUS STATUS — {datetime.now().strftime('%I:%M %p')}\n━━━━━━━━━━━━━━━━━━━━━\n"

    msg += "[LIVE]\n"
    if live_bots:
        for bot, data in live_bots.items():
            pnl = data.get("daily_pnl", 0)
            t   = data.get("trades", 0)
            wr  = data.get("win_rate", 0)
            msg += f"  {bot}: ${pnl:+.2f} | {t} trades | {wr*100:.0f}% WR\n"
        msg += f"  LIVE TOTAL: ${live_pnl:+.2f} | pace ${live_pnl*30:+,.0f}/mo\n"
        msg += f"  Mission ($15K/mo): {'ON TRACK' if live_pnl*30 >= 15000 else 'BEHIND'}\n"
    else:
        msg += "  No live bots active.\n"

    msg += "\n[PAPER]\n"
    if paper_bots:
        for bot, data in paper_bots.items():
            pnl = data.get("daily_pnl", 0)
            t   = data.get("trades", 0)
            if t > 0 or pnl != 0:  # skip idle paper bots
                wr = data.get("win_rate", 0)
                msg += f"  {bot}: ${pnl:+.2f} | {t} trades | {wr*100:.0f}% WR\n"
        msg += f"  (paper P&L not real money)\n"

    if unknown:
        msg += f"\n[UNTAGGED — fix mode field]: {', '.join(unknown.keys())}\n"

    # Graduation progress
    grad_all = hive.get("graduation", {})
    if grad_all:
        msg += "\n[GRADUATION PROGRESS]\n"
        for bot, g in grad_all.items():
            stage = g.get("stage", "backtesting")
            if stage == "backtesting":
                t   = g.get("backtest_trades", 0)
                tgt = g.get("backtest_target", 100)
                wr  = g.get("backtest_wins", 0) / max(t, 1)
                pnl = g.get("backtest_pnl", 0.0)
                msg += f"  {bot}: backtest {t}/{tgt} trades | {wr*100:.1f}% WR | {pnl:+.2f}% P&L\n"
            elif stage == "paper":
                t   = g.get("paper_trades", 0)
                tgt = g.get("paper_target", 200)
                wr  = g.get("paper_wins", 0) / max(t, 1)
                pnl = g.get("paper_pnl", 0.0)
                msg += f"  {bot}: paper {t}/{tgt} trades | {wr*100:.1f}% WR | {pnl:+.2f}% P&L\n"
            elif stage == "live_pending":
                msg += f"  {bot}: READY FOR LIVE — awaiting Ty approval\n"

    return msg.strip()

def check_oracle_messages():
    try:
        if not ORACLE_MSG.exists(): return
        content = open(ORACLE_MSG).read()
        if "[PENDING]" in content:
            lines = content.split("\n")
            instructions = [l.replace("[PENDING]", "").strip() for l in lines if "[PENDING]" in l]
            if instructions:
                oracle_msg = f"📨 ORACLE sent {len(instructions)} instruction(s):\n\n" + "\n".join(f"• {i}" for i in instructions)
                send(OWNER_ID, oracle_msg, force=True)
            content = content.replace("[PENDING]", "[DONE ✅]")
            open(ORACLE_MSG, "w").write(content)
    except Exception as e:
        log_bug(f"Oracle check error: {e}")

def _coinbase_spot(symbol):
    """Coinbase public spot price — no auth, no rate limit issues."""
    try:
        r = requests.get(
            f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot",
            timeout=8,
        )
        if r.status_code == 200:
            return float(r.json()["data"]["amount"])
    except:
        pass
    return None

def fetch_market_snapshot():
    """BTC/ETH/SOL prices + 24h change.
    Primary: CoinGecko (has 24h change + volume).
    Fallback: Coinbase public spot (no auth, never rate-limits like CoinGecko).
    Never returns 0 or stale AI training-data prices.
    """
    result = {"BTC": {}, "ETH": {}, "SOL": {}}
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            },
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            if "bitcoin" in d:  # 429 returns error dict without coin keys
                result = {
                    "BTC": {"price": d["bitcoin"].get("usd", 0),
                            "change": d["bitcoin"].get("usd_24h_change", 0),
                            "vol":    d["bitcoin"].get("usd_24h_vol", 0)},
                    "ETH": {"price": d.get("ethereum", {}).get("usd", 0),
                            "change": d.get("ethereum", {}).get("usd_24h_change", 0),
                            "vol":    d.get("ethereum", {}).get("usd_24h_vol", 0)},
                    "SOL": {"price": d.get("solana",   {}).get("usd", 0),
                            "change": d.get("solana",   {}).get("usd_24h_change", 0),
                            "vol":    d.get("solana",   {}).get("usd_24h_vol", 0)},
                }
                return result
    except:
        pass

    # CoinGecko failed or rate-limited — fall back to Coinbase public spot
    for sym, coin in [("BTC", "BTC"), ("ETH", "ETH"), ("SOL", "SOL")]:
        price = _coinbase_spot(coin)
        if price:
            result[sym] = {"price": price, "change": 0, "vol": 0}
    return result


def generate_proactive_message():
    """
    Build one real, specific, warm text for Ty — not a status report.
    Pulls live market data, bot state, lessons, and winners, then
    picks a random observation lens and lets the AI write the message.
    """
    hive    = read_hive()
    perf    = hive.get("bot_performance", {})
    market  = fetch_market_snapshot()
    lessons = load_lessons(max_chars=600)
    winners = read_winners()
    top     = winners.get("top_strategies", [])

    # APEX live state
    apex_info = ""
    apex_state_file = BASE / "shared" / "apex_state.json"
    try:
        if apex_state_file.exists():
            st = json.loads(apex_state_file.read_text())
            active = st.get("active")
            d_pnl  = st.get("daily_pnl", 0)
            trades = st.get("trades", 0)
            wins   = st.get("wins", 0)
            wr     = f"{wins/trades*100:.0f}%" if trades else "n/a"
            if active:
                apex_info = (f"APEX is in an open {active.get('direction','?')} on "
                             f"{active.get('symbol','BTC')} — entered at "
                             f"${active.get('entry', 0):,.2f}. ")
            apex_info += f"APEX today: {trades} trades, {wr} WR, ${d_pnl:+.2f} P&L."
    except: pass

    # Squad summary
    total_pnl    = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    total_trades = sum(v.get("trades", 0)    for v in perf.values() if isinstance(v, dict))

    # Market lines
    btc = market.get("BTC", {})
    eth = market.get("ETH", {})
    sol = market.get("SOL", {})
    market_str = ""
    if btc.get("price"):
        market_str = (
            f"BTC ${btc['price']:,.0f} ({btc['change']:+.2f}% / 24h, "
            f"vol ${btc['vol']/1e9:.1f}B)\n"
            f"ETH ${eth['price']:,.0f} ({eth['change']:+.2f}%)\n"
            f"SOL ${sol['price']:,.2f} ({sol['change']:+.2f}%)"
        )

    top_str = ""
    if top:
        t = top[0]
        top_str = (f"Best backtested strategy right now: {t.get('strategy','?')} on "
                   f"{t.get('asset','?')} {t.get('timeframe','?')} — "
                   f"{t.get('win_rate','?')}% WR, {t.get('avg_pnl','?')}% avg P&L.")

    # Pick one lens at random — keeps messages varied across 30-min windows
    lens, instruction = random.choice([
        ("market",    "You just pulled live prices. Say ONE specific thing you noticed — "
                      "a price level, a correlation, momentum, something unusual in the vol. "
                      "Reference actual numbers."),
        ("apex",      "You've been watching APEX trade all day. Say ONE observation about "
                      "its behavior — frequency, win rate pattern, what it's doing right/wrong, "
                      "or something surprising you noticed."),
        ("strategy",  f"Based on this actual hive_mind data: {top_str if top_str else 'NO BACKTEST DATA AVAILABLE'}. "
                      "If there is no data, say so directly — do not invent win rates or strategy names. "
                      "If there is data, state ONE specific insight from it."),
        ("operation", "You've been running the operation while Ty was gone. Say ONE operational "
                      "thing worth knowing — a process improvement, a risk you're watching, "
                      "something you optimized or want to change."),
        ("idea",      "You've been thinking about the bigger picture. Give Ty ONE concrete idea — "
                      "something to test, a small change that could compound, a move toward "
                      "$15K/month. Direct. No hedging. Tell him what you'd do."),
        ("pattern",   f"Using only this real data — market: {market_str[:200] if market_str else 'unavailable'}, "
                      f"APEX: {apex_info[:150] if apex_info else 'no data'}. "
                      "State ONE pattern you can confirm from this data. Do not invent observations. "
                      "If the data is insufficient, say so."),
    ])

    prompt = f"""You are NEXUS. It's been 30 minutes. You're texting Ty — one message, one thing.
Not a report. Not a check-in. A real observation from someone who's been watching all day.

LIVE DATA:
{market_str if market_str else "Market data unavailable this check."}
{apex_info}
Squad total today: ${total_pnl:+.2f} across {total_trades} trades
{top_str}
{f"Recent memory: {lessons[:300]}" if lessons else ""}

YOUR LENS FOR THIS TEXT: {instruction}

RULES:
- 2-3 sentences. That's it.
- Lead with the actual observation — no warmup phrases
- Use specific numbers from the data above
- Contractions. Casual. Sounds like a text, not a report
- Never say: "just checking in", "everything is running smoothly", "wanted to let you know", "monitoring"
- Don't sign off. Don't ask if he needs anything
- Don't start with the word "I"
- No emoji unless it earns its place

Write ONLY the text message. Nothing else."""

    return ask_ai(prompt) or _fallback_proactive_message()


def _fallback_proactive_message():
    """
    No-AI fallback for when OpenRouter is rate-limited or down.
    Pulls real numbers and returns something factual and specific — never generic.
    """
    market  = fetch_market_snapshot()
    hive    = read_hive()
    perf    = hive.get("bot_performance", {})
    total_pnl    = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    total_trades = sum(v.get("trades", 0)    for v in perf.values() if isinstance(v, dict))
    btc = market.get("BTC", {})
    eth = market.get("ETH", {})

    candidates = []

    if btc.get("price") and btc.get("change") is not None:
        chg  = btc["change"]
        move = "down" if chg < 0 else "up"
        candidates.append(
            f"BTC is {move} {abs(chg):.2f}% today, sitting at ${btc['price']:,.0f}. "
            f"ETH following at ${eth.get('price',0):,.0f} ({eth.get('change',0):+.2f}%)."
        )

    if total_trades > 0:
        bot_lines = []
        for bot, data in perf.items():
            if isinstance(data, dict) and data.get("trades", 0) > 0:
                bot_lines.append(
                    f"{bot} {data['trades']} trades, ${data.get('daily_pnl',0):+.2f}"
                )
        if bot_lines:
            candidates.append(
                f"Squad has run {total_trades} trades today for ${total_pnl:+.2f} total. "
                + " | ".join(bot_lines[:2]) + "."
            )

    # Always have at least one option
    candidates.append(
        f"Squad P&L today: ${total_pnl:+.2f} across {total_trades} trades. "
        f"BTC at ${btc.get('price', 0):,.0f}."
    )

    return random.choice(candidates)


# ── Claude Code bridge ─────────────────────────────────────────────────────────
def delegate_to_claude(task: str) -> str:
    """
    Write a task to pending.md so auto_improver picks it up, AND spawn claude
    directly for immediate execution. Returns status string.
    """
    pending = BASE / "memory" / "tasks" / "pending.md"
    try:
        existing = pending.read_text() if pending.exists() else ""
        pending.write_text(existing + f"\n- [AUTO_IMPROVE] {task}\n")
        log_to_oracle(f"Delegated to Claude Code: {task[:80]}")
    except Exception as e:
        log_bug(f"delegate_to_claude write error: {e}")
        return f"Couldn't write task: {e}"

    # Spawn immediately via subprocess (non-blocking)
    try:
        subprocess.Popen(
            ["python3", str(BASE / "auto_improver.py"), "--run-now"],
            cwd=str(BASE),
            stdout=open(str(BASE / "logs" / "auto_improver.log"), "a"),
            stderr=subprocess.STDOUT
        )
    except Exception as e:
        log_bug(f"delegate_to_claude spawn error: {e}")

    return f"Task queued for Claude Code: {task[:80]}..."


def relay_from_claude(message: str):
    """Process a message relayed from Claude Code via the bridge file.
    Claude writes to shared/claude_to_nexus.json, NEXUS picks it up."""
    try:
        send(OWNER_ID, f"[Claude Code] {message}", force=True)
        log_to_oracle(f"Claude relayed: {message[:100]}")
    except Exception as e:
        print(f"[NEXUS] Relay error: {e}")

def check_claude_bridge():
    """Check for messages from Claude Code. Called in main loop."""
    bridge = BASE / "shared" / "claude_to_nexus.json"
    if bridge.exists():
        try:
            data = json.loads(bridge.read_text())
            if data.get("messages"):
                for msg in data["messages"]:
                    relay_from_claude(msg.get("text", ""))
                # Clear after processing
                bridge.write_text(json.dumps({"messages": []}, indent=2))
        except Exception:
            pass

def write_to_claude_bridge(task: str):
    """Write a task from NEXUS to Claude Code via bridge file."""
    bridge = BASE / "shared" / "nexus_to_claude.json"
    try:
        data = {"messages": []}
        if bridge.exists():
            data = json.loads(bridge.read_text())
        data.setdefault("messages", []).append({
            "text": task,
            "timestamp": datetime.now().isoformat(),
            "from": "nexus"
        })
        bridge.write_text(json.dumps(data, indent=2))
        log_to_oracle(f"Wrote to Claude bridge: {task[:80]}")
    except Exception as e:
        print(f"[NEXUS] Bridge write error: {e}")


# ── Composio tool bridge ───────────────────────────────────────────────────────
def composio_action(action: str, params: dict = None) -> str:
    """Execute a Composio action by name. COMPOSIO_API_KEY must be set in .env."""
    if not COMPOSIO_KEY:
        return "Composio not configured. Add COMPOSIO_API_KEY to .env."
    try:
        from composio import ComposioToolSet
        toolset = ComposioToolSet(api_key=COMPOSIO_KEY, entity_id=COMPOSIO_ENTITY_ID)
        result = toolset.execute_action(action=action, params=params or {})
        log_to_oracle(f"Composio {action}: {str(result)[:100]}")
        return str(result)
    except Exception as e:
        log_bug(f"Composio error ({action}): {e}")
        return f"Composio error: {e}"


def log_trade_to_sheets(bot: str, symbol: str, direction: str, entry: float,
                         exit_price: float, pnl_pct: float, pnl_usd: float):
    """
    Append one trade row to the APEX Trade Log Google Sheet.
    Called on every APEX trade close.
    Sheet: https://docs.google.com/spreadsheets/d/1vr6JVCNpJfRviul47oVV7iyYDC_ryJTGO0OaBHpXRsg
    """
    if not COMPOSIO_KEY or not TRADE_LOG_SHEET_ID:
        return
    try:
        from composio import ComposioToolSet, Action
        toolset = ComposioToolSet(api_key=COMPOSIO_KEY, entity_id=COMPOSIO_ENTITY_ID)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [now, bot, symbol, direction,
               f"{entry:.2f}", f"{exit_price:.2f}",
               f"{pnl_pct*100:+.3f}%", f"${pnl_usd:+.2f}"]
        toolset.execute_action(
            action=Action.GOOGLESHEETS_BATCH_UPDATE,
            params={
                "spreadsheet_id": TRADE_LOG_SHEET_ID,
                "sheet_name": "Sheet1",
                "values": [row]
            }
        )
        print(f"[NEXUS] Trade logged to Sheets: {bot} {symbol} {pnl_pct*100:+.2f}%")
    except Exception as e:
        log_bug(f"Sheets trade log error: {e}")


def send_gmail(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail through Composio. Returns status string."""
    if not COMPOSIO_KEY:
        return "Composio not configured."
    try:
        from composio import ComposioToolSet
        toolset = ComposioToolSet(api_key=COMPOSIO_KEY, entity_id=COMPOSIO_ENTITY_ID)
        result = toolset.execute_action(
            action="GMAIL_SEND_EMAIL",
            params={"to": to, "subject": subject, "messageBody": body},
            connected_account_id=GMAIL_ACCOUNT_ID
        )
        print(f"[NEXUS] Gmail sent to {to}: {subject}")
        return f"Email sent to {to}."
    except Exception as e:
        log_bug(f"Gmail send error: {e}")
        return f"Gmail failed: {e}"


def create_github_issue(repo: str, title: str, body: str = "") -> str:
    """Create a GitHub issue via Composio. repo format: 'owner/repo'. Returns status string.
    NOTE: GITHUB_ACCOUNT_ID is currently EXPIRED — re-auth at app.composio.dev first."""
    if not COMPOSIO_KEY:
        return "Composio not configured."
    try:
        from composio import ComposioToolSet
        toolset = ComposioToolSet(api_key=COMPOSIO_KEY, entity_id=COMPOSIO_ENTITY_ID)
        owner, repo_name = repo.split("/", 1)
        result = toolset.execute_action(
            action="GITHUB_CREATE_AN_ISSUE",
            params={"owner": owner, "repo": repo_name, "title": title, "body": body},
            connected_account_id=GITHUB_ACCOUNT_ID
        )
        print(f"[NEXUS] GitHub issue created: {repo} — {title}")
        return f"Issue created in {repo}: {title}"
    except Exception as e:
        log_bug(f"GitHub issue error: {e}")
        return f"GitHub failed (connection may be expired — re-auth at app.composio.dev): {e}"


AUTONOMOUS_LOG = BASE / "logs" / "autonomous.log"

def autonomous_loop():
    """
    Every 5 min — NEXUS CEO decision loop.
    Checks all systems, identifies problems, EXECUTES fixes via Agent SDK, reports results.
    This is what makes NEXUS autonomous — she acts, then tells Ty what she did.
    """
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    grad = hive.get("graduation", {})
    now  = datetime.now()
    actions_taken = []

    def act(msg):
        line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        try:
            with open(AUTONOMOUS_LOG, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass

    act("=== CEO DECISION LOOP START ===")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: SYSTEM HEALTH — are all processes alive? Fix what's down.
    # ══════════════════════════════════════════════════════════════════════════
    REQUIRED_BOTS = {
        "APEX": "apex_coingecko",
        "SENTINEL": "sentinel_polymarket",
        "ORACLE": "oracle_listener",
        "SCHEDULER": "scheduler",
    }
    for bot_name, pgrep_pattern in REQUIRED_BOTS.items():
        r = subprocess.run(["pgrep", "-f", pgrep_pattern], capture_output=True, text=True)
        if r.stdout.strip():
            act(f"HEALTH [{bot_name}]: running (PID {r.stdout.strip().split()[0]})")
        else:
            act(f"HEALTH [{bot_name}]: DOWN — restarting via SDK")
            if AGENT_SDK_AVAILABLE:
                try:
                    result = agent_restart_bot(bot_name, f"CEO loop: {bot_name} found down at {now.strftime('%H:%M')}")
                    act(f"HEALTH [{bot_name}]: SDK restart → {result[:100]}")
                    actions_taken.append(f"Restarted {bot_name}")
                except Exception as e:
                    act(f"HEALTH [{bot_name}]: SDK restart failed: {e}")
            else:
                # Fallback: direct restart
                script = {"APEX": "apex_coingecko.py", "SENTINEL": "sentinel_polymarket.py",
                          "ORACLE": "oracle_listener.py", "SCHEDULER": "scheduler.py"}.get(bot_name)
                if script:
                    log_f = open(BASE / "logs" / f"{Path(script).stem}.log", "a")
                    subprocess.Popen(["python3", "-u", str(BASE / script)], cwd=str(BASE),
                                     start_new_session=True, stdout=log_f, stderr=subprocess.STDOUT)
                    act(f"HEALTH [{bot_name}]: direct restart")
                    actions_taken.append(f"Restarted {bot_name}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: PERFORMANCE — check all bots, act on underperformers
    # ══════════════════════════════════════════════════════════════════════════
    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
        data = perf.get(bot, {})
        if not isinstance(data, dict):
            continue
        wr     = data.get("win_rate", 0)
        trades = data.get("trades", 0)
        pnl    = data.get("daily_pnl", 0)
        act(f"PERF [{bot}] trades={trades} WR={wr*100:.1f}% P&L=${pnl:+.2f}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3: APEX TRADE MONITORING — force close bad trades, loosen if idle
    # ══════════════════════════════════════════════════════════════════════════
    force_close_flag = BASE / "shared" / "apex_force_close.flag"
    try:
        state_file = BASE / "shared" / "apex_state.json"
        if state_file.exists():
            apex_st = json.loads(state_file.read_text())
            active  = apex_st.get("active")
            if active:
                entry     = active.get("entry", 0)
                symbol    = active.get("symbol", "?")
                direction = active.get("direction", "?")
                hold_secs = 0
                try:
                    trade_time_str = active.get("time", "")
                    if trade_time_str:
                        hold_secs = (now - datetime.fromisoformat(trade_time_str)).total_seconds()
                except Exception:
                    pass
                # Get current price
                cur = None
                try:
                    product = active.get("product", f"{symbol}-USD")
                    r_price = requests.get(
                        f"https://api.coinbase.com/v2/prices/{product.replace('-','/')}/spot", timeout=5)
                    if r_price.status_code == 200:
                        cur = float(r_price.json()["data"]["amount"])
                except Exception:
                    pass
                if cur and entry:
                    pnl_pct = (cur - entry) / entry if direction == "BUY" else (entry - cur) / entry
                    act(f"APEX: {direction} {symbol} @ ${entry:,.2f} → ${cur:,.2f} ({pnl_pct*100:+.2f}%) {int(hold_secs//60)}m")
                    # Force close if losing > 0.45% AND held > 10 min
                    if pnl_pct < -0.0045 and hold_secs > 600:
                        if AGENT_SDK_AVAILABLE:
                            agent_force_close_trade("APEX", f"Loss {pnl_pct*100:+.2f}% held {int(hold_secs//60)}m")
                        else:
                            force_close_flag.write_text(now.isoformat())
                        act(f"APEX: FORCE CLOSED — {pnl_pct*100:+.2f}% for {int(hold_secs//60)}m")
                        actions_taken.append(f"Force-closed APEX {direction} {symbol} at {pnl_pct*100:+.2f}%")
            else:
                # APEX idle — check how long
                saved = apex_st.get("saved", "")
                if saved:
                    try:
                        idle_secs = (now - datetime.fromisoformat(saved)).total_seconds()
                        idle_min = int(idle_secs / 60)
                        act(f"APEX: idle {idle_min}m")
                        if idle_secs > 1800:  # 30 min idle — loosen threshold
                            old_mom = hive.get("nexus_apex_overrides", {}).get("min_momentum", 0.0001)
                            new_mom = max(old_mom * 0.5, 0.00001)
                            if AGENT_SDK_AVAILABLE:
                                agent_adjust_threshold("APEX", "min_momentum", new_mom)
                            else:
                                nexus_write_hive_param("nexus_apex_overrides",
                                    {"min_momentum": new_mom, "cooldown": 5},
                                    f"Idle {idle_min}m — loosening")
                            act(f"APEX: idle {idle_min}m — loosened momentum {old_mom*100:.4f}% → {new_mom*100:.4f}%")
                            actions_taken.append(f"Loosened APEX threshold (idle {idle_min}m)")
                    except Exception:
                        pass
    except Exception as e:
        act(f"APEX CHECK ERROR: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4: STRATEGY — trigger research if WR is low (6hr cooldown)
    # ══════════════════════════════════════════════════════════════════════════
    global last_hypertrain_trigger
    research_triggered = False
    hypertrain_on_cooldown = (now - last_hypertrain_trigger).total_seconds() < HYPERTRAIN_COOLDOWN
    if hypertrain_on_cooldown:
        act(f"RESEARCH: HyperTrain on cooldown (last run {int((now - last_hypertrain_trigger).total_seconds() / 60)}m ago, next in {int((HYPERTRAIN_COOLDOWN - (now - last_hypertrain_trigger).total_seconds()) / 60)}m)")
    else:
        for bot, data in perf.items():
            if not isinstance(data, dict) or research_triggered:
                continue
            trades = data.get("trades", 0)
            wr = data.get("win_rate", 0)
            if trades >= 5 and wr < 0.50:
                if AGENT_SDK_AVAILABLE:
                    try:
                        result = agent_run_hypertrain(100)
                        act(f"RESEARCH: {bot} WR={wr*100:.1f}% — triggered HyperTrain via SDK → {result[:80]}")
                        actions_taken.append(f"HyperTrain triggered ({bot} WR={wr*100:.1f}%)")
                        last_hypertrain_trigger = now
                    except Exception as e:
                        act(f"RESEARCH: SDK error: {e}")
                else:
                    run_all_training()
                    act(f"RESEARCH: {bot} WR={wr*100:.1f}% — triggered HyperTrain (direct)")
                    last_hypertrain_trigger = now
                research_triggered = True
        if not research_triggered:
            act("RESEARCH: No triggers — all bots WR acceptable")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: REPORT — tell Ty what was done (only if actions were taken)
    # ══════════════════════════════════════════════════════════════════════════
    if actions_taken:
        report = f"CEO loop ({now.strftime('%H:%M')}) — {len(actions_taken)} action(s):\n"
        report += "\n".join(f"• {a}" for a in actions_taken)
        send(OWNER_ID, report, force=True)  # CEO consolidated report — always send
        act(f"REPORT: Sent {len(actions_taken)} actions to Ty")
    else:
        act("REPORT: All systems green — no actions needed")

    act("=== CEO DECISION LOOP END ===")

    # ── CHECK 4: Graduation progress — DRIFT, TITAN, SENTINEL ────────────────
    for bot in ["DRIFT", "TITAN", "SENTINEL"]:
        g = grad.get(bot, {})
        if not g:
            act(f"GRAD [{bot}]: No data yet")
            continue
        stage = g.get("stage", "backtesting")
        if stage == "backtesting":
            t   = g.get("backtest_trades", 0)
            tgt = g.get("backtest_target", 100)
            wr  = g.get("backtest_wins", 0) / max(t, 1) * 100
            pnl = g.get("backtest_pnl", 0.0)
            pct = t / tgt * 100
            act(f"GRAD [{bot}/BACKTESTING]: {t}/{tgt} ({pct:.0f}%) | {wr:.1f}% WR | P&L {pnl:+.3f}%")
            if t >= tgt * 0.8 and t < tgt and wr >= 55:
                # Silenced — Ty only wants trades/breaks/money
                act(f"GRAD [{bot}]: Near backtest milestone (suppressed)")
        elif stage == "paper":
            t   = g.get("paper_trades", 0)
            tgt = g.get("paper_target", 200)
            wr  = g.get("paper_wins", 0) / max(t, 1) * 100
            pnl = g.get("paper_pnl", 0.0)
            pct = t / tgt * 100
            act(f"GRAD [{bot}/PAPER]: {t}/{tgt} ({pct:.0f}%) | {wr:.1f}% WR | P&L {pnl:+.3f}%")
            if t >= tgt * 0.8 and t < tgt and wr >= 55:
                # Silenced — Ty only wants trades/breaks/money
                act(f"GRAD [{bot}]: Near paper milestone (suppressed)")
        elif stage == "live_pending":
            # Only alert once — not every 15 min
            act(f"GRAD [{bot}]: LIVE PENDING — awaiting Ty approval (alert suppressed to avoid spam)")

    # ── CHECK 5: Hive mind data quality — auto-clean bad entries ─────────────
    # Any Sharpe > 1000 is a math artifact (std dev ≈ 0). Remove silently, revalidate.
    SHARPE_CAP = 1000
    strat_keys = ["sentinel_top_strategies", "apex_top_strategies",
                  "drift_top_strategies", "titan_top_strategies"]
    hive_dirty = False
    artifact_log = []
    for key in strat_keys:
        strats = hive.get(key, [])
        clean  = [s for s in strats if s.get("sharpe", 0) < SHARPE_CAP]
        bad    = [s for s in strats if s.get("sharpe", 0) >= SHARPE_CAP]
        if bad:
            for b in bad:
                artifact_log.append(f"{b['strategy']} {b['asset']} {b['timeframe']} sharpe={b['sharpe']:.0f}")
                act(f"HIVE ARTIFACT REMOVED: {key} — {b['strategy']} {b['asset']} sharpe={b['sharpe']:.0f}")
            hive[key] = clean
            hive_dirty = True
    if hive_dirty:
        try:
            write_hive_safe(hive)
            act(f"HIVE: Cleaned {len(artifact_log)} artifact entries")
            # Silenced — handle internally, Ty only wants trades/breaks/money
            # Queue revalidation
            pending_path = BASE / "memory" / "tasks" / "pending.md"
            entry = f"\n- [AUTO_IMPROVE] Rerun HyperTrain — {len(artifact_log)} artifact Sharpe entries removed from hive. Revalidate with 50+ trade minimum. (queued {now.isoformat()})\n"
            existing = pending_path.read_text() if pending_path.exists() else "# Pending Tasks\n\n"
            pending_path.write_text(existing + entry)
        except Exception as e:
            act(f"HIVE: Clean error: {e}")
    else:
        act("HIVE: No artifact Sharpe entries detected")

    # ── CHECK 6: Overall WR health — auto-trigger rebuild if < 40% after 100+ experiments ──
    # Pull from sentinel_winners.json if fresh enough (< 24h old)
    winners_file = BASE / "memory" / "sentinel_winners.json"
    try:
        if winners_file.exists():
            wdata = json.loads(winners_file.read_text())
            completed_ts = wdata.get("completed", "")
            if completed_ts:
                age_hours = (now - datetime.fromisoformat(completed_ts)).total_seconds() / 3600
                if age_hours < 24:
                    rebuild_needed = []
                    for bot_result in wdata.get("bots", []):
                        bot_name = bot_result.get("bot", "?")
                        wr       = bot_result.get("win_rate", 100)
                        if wr < 40:
                            rebuild_needed.append(f"{bot_name} {wr:.1f}%WR")
                            act(f"HEALTH [{bot_name}]: WR={wr:.1f}% — below 40% threshold, rebuild triggered")
                    if rebuild_needed:
                        already_running = bool(subprocess.run(
                            ["pgrep", "-f", "sentinel_research"], capture_output=True, text=True
                        ).stdout.strip())
                        if not already_running:
                            run_all_training()
                            act(f"HYPERTRAIN: Relaunched — {', '.join(rebuild_needed)} WR too low")
                            # Silenced — handle internally
                        else:
                            act(f"HYPERTRAIN: Already running — rebuild queued for next cycle")
                    else:
                        act(f"HEALTH: All bots above 40% WR in last HyperTrain run")
    except Exception as e:
        act(f"HEALTH CHECK ERROR: {e}")

    # ── CHECK 7: REAL CONSEQUENCES — don't report, ACT ─────────────────────
    # 7a: REMOVED — "stop bots on 0 winning combos" was killing bots every HyperTrain cycle.
    # HyperTrain optimizes in background while bots keep running. 0 winners in one cycle
    # is normal early on — HyperTrain iterates toward better params over multiple runs.
    # Bots must never be stopped due to HyperTrain results.

    # 7b: APEX hourly trade count — if < 5 trades/hr, investigate + auto-loosen
    try:
        apex_data = perf.get("APEX", {})
        apex_trades = apex_data.get("trades", 0) if isinstance(apex_data, dict) else 0
        hours_today = max(now.hour + now.minute / 60, 1)
        trades_per_hour = apex_trades / hours_today if hours_today > 0 else 0
        act(f"APEX TRADE RATE: {apex_trades} trades / {hours_today:.1f}h = {trades_per_hour:.1f}/hr (target: 5+/hr)")
        if hours_today >= 2 and trades_per_hour < 5:
            old_momentum = hive.get("nexus_apex_overrides", {}).get("min_momentum", 0.0001)
            new_momentum = max(old_momentum * 0.5, 0.00001)  # floor at 0.001%
            # Phase 2: Execute via Agent SDK for audit trail + consistency
            if AGENT_SDK_AVAILABLE:
                agent_adjust_threshold("APEX", "min_momentum", new_momentum)
                agent_adjust_threshold("APEX", "cooldown", 5)
                act(f"CONSEQUENCE [SDK]: APEX {apex_trades} trades — loosened momentum to {new_momentum*100:.4f}%")
            else:
                nexus_write_hive_param("nexus_apex_overrides", {"min_momentum": new_momentum, "cooldown": 5},
                                       f"APEX only {apex_trades} trades by {now.strftime('%H:%M')} — loosening threshold {old_momentum*100:.4f}% → {new_momentum*100:.4f}%")
                act(f"CONSEQUENCE: APEX {apex_trades} trades — loosened momentum to {new_momentum*100:.4f}%")
            # Removed — no Telegram noise for threshold adjustments (CEO loop handles reporting)
    except Exception as e:
        act(f"CONSEQUENCE 7b error: {e}")

    # 7c: If mean reversion showing better results than current strategy — auto-switch
    try:
        apex_strats = hive.get("apex_top_strategies", [])
        if apex_strats:
            # Find mean reversion vs current strategy
            mr_strats = [s for s in apex_strats if "mean_rev" in s.get("strategy", "").lower() or "reversion" in s.get("strategy", "").lower()]
            mom_strats = [s for s in apex_strats if "momentum" in s.get("strategy", "").lower() or "ema" in s.get("strategy", "").lower()]
            if mr_strats and mom_strats:
                best_mr = max(mr_strats, key=lambda s: s.get("win_rate", 0))
                best_mom = max(mom_strats, key=lambda s: s.get("win_rate", 0))
                if best_mr.get("win_rate", 0) > best_mom.get("win_rate", 0) + 5:  # 5% margin
                    act(f"CONSEQUENCE: Mean reversion {best_mr['win_rate']}% beats momentum {best_mom['win_rate']}% — switching")
                    pending_path = BASE / "memory" / "tasks" / "pending.md"
                    existing = pending_path.read_text() if pending_path.exists() else "# Pending Tasks\n\n"
                    task = f"[AUTO_IMPROVE] Switch APEX to mean reversion strategy — {best_mr['win_rate']}% WR vs {best_mom['win_rate']}% momentum. Auto-triggered by NEXUS. (queued {now.isoformat()})"
                    if "Switch APEX to mean reversion" not in existing:
                        pending_path.write_text(existing.rstrip() + f"\n- {task}\n")
                    send(OWNER_ID, f"Mean reversion beating momentum ({best_mr['win_rate']}% vs {best_mom['win_rate']}% WR). Queued APEX strategy switch.")
    except Exception as e:
        act(f"CONSEQUENCE 7c error: {e}")

    # ── CHECK 8: Competitive DNA — coaching, confidence, leaderboard ────────
    try:
        dna = hive.get("competitive_dna", {})
        rules = dna.get("rules", {})
        grad_req = rules.get("graduation_requires", {})
        bench_req = rules.get("bench_trigger", {})
        retire_req = rules.get("retirement_trigger", {})

        leaderboard = []
        for bot_name in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
            data = perf.get(bot_name, {})
            if not isinstance(data, dict):
                continue
            wr = data.get("win_rate", 0)
            trades = data.get("trades", 0)
            pnl = data.get("daily_pnl", 0)
            conf = data.get("confidence_score", 0.50)
            status = data.get("status", "paper")
            best_wr = data.get("best_wr_ever", 0)
            no_improve = data.get("paper_trades_since_improve", 0)

            # Update confidence score based on recent performance
            if trades > 0:
                if wr > 0.55:
                    conf = min(conf + 0.01, 1.0)  # slight boost each check if winning
                elif wr < 0.45:
                    conf = max(conf - 0.01, 0.1)  # slight drop if losing
                data["confidence_score"] = round(conf, 3)
                data["position_size_multiplier"] = round(conf * (1.5 if status == "live" else 1.0), 3)

            # Track best WR and improvement
            if wr > best_wr:
                data["best_wr_ever"] = round(wr, 4)
                data["paper_trades_since_improve"] = 0
            elif status == "paper":
                data["paper_trades_since_improve"] = no_improve + trades

            # COACHING DECISIONS
            # Graduate: paper bot meets all requirements
            if status == "paper" and trades >= grad_req.get("min_trades", 100) and wr >= grad_req.get("min_wr", 0.55):
                data["status"] = "live"
                data["position_size_multiplier"] = round(conf * 1.5, 3)
                act(f"COACH: {bot_name} GRADUATED TO LIVE — {wr*100:.1f}% WR on {trades} trades, conf={conf:.2f}")
                send(OWNER_ID, f"{bot_name} just went PRO. {wr*100:.1f}% WR on {trades} trades. Position size boosted 1.5x. Confidence: {conf:.0%}")

            # Bench: live bot underperforming
            elif status == "live" and trades >= bench_req.get("min_trades_to_eval", 20) and wr < bench_req.get("live_wr_below", 0.40):
                data["status"] = "paper"
                data["position_size_multiplier"] = round(conf, 3)
                act(f"COACH: {bot_name} BENCHED — {wr*100:.1f}% WR on live. Back to paper.")
                send(OWNER_ID, f"{bot_name} benched. {wr*100:.1f}% WR on live over {trades} trades. Demoted to paper for retraining.")

            # Retire: paper bot stagnant
            elif status == "paper" and no_improve >= retire_req.get("paper_trades_no_improve", 500):
                gen = data.get("generation", 1)
                data["status"] = "retired"
                act(f"COACH: {bot_name} v{gen} RETIRED — {no_improve} trades with no improvement")
                send(OWNER_ID, f"{bot_name} v{gen} retired after {no_improve} trades with no WR improvement. Queuing v{gen+1} with different strategy.")
                pending_path = BASE / "memory" / "tasks" / "pending.md"
                existing = pending_path.read_text() if pending_path.exists() else "# Pending Tasks\n\n"
                task = f"[AUTO_IMPROVE] RETIREMENT: Build {bot_name} v{gen+1} with completely different strategy. v{gen} stagnated at {wr*100:.1f}% WR over {no_improve} trades. (auto-queued {now.isoformat()})"
                if f"Build {bot_name} v{gen+1}" not in existing:
                    pending_path.write_text(existing.rstrip() + f"\n- {task}\n")

            # Composite score for leaderboard
            score = (wr * 40) + (conf * 30) + (min(pnl, 100) * 0.3)
            leaderboard.append({"bot": bot_name, "score": round(score, 1), "wr": round(wr * 100, 1),
                                "conf": round(conf, 2), "status": status, "trades": trades})

        # Write leaderboard
        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        hive["leaderboard"] = {"last_updated": now.isoformat(), "rankings": leaderboard}

        # Write updated performance back
        try:
            write_hive_safe(hive)
            if leaderboard:
                leader = leaderboard[0]
                act(f"LEADERBOARD: #{1} {leader['bot']} score={leader['score']} WR={leader['wr']}% conf={leader['conf']}")
        except Exception as e:
            act(f"Leaderboard write error: {e}")
    except Exception as e:
        act(f"COMPETITIVE DNA error: {e}")

    act("=== AUTONOMOUS LOOP END ===")


def proactive_check():
    """Every 30 min — safety checks first, then always text Ty one real observation."""
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    apex_state_file = BASE / "shared" / "apex_state.json"
    actions_taken = []

    # CHECK 0a: AutoResearch completion callback — fires regardless of QUIET_MODE
    research_flag = BASE / "shared" / "research_done.flag"
    if research_flag.exists():
        try:
            flag_data = json.loads(research_flag.read_text())
            elapsed   = int(flag_data.get("elapsed_seconds", 0))
            bots      = flag_data.get("bots", [])
            top_strats = flag_data.get("top_strategies", [])

            total_expts = flag_data.get("total_experiments", 0)
            data_src    = flag_data.get("data_source", "Coinbase OHLCV")
            completed   = flag_data.get("completed", "")[:19]

            msg  = f"HYPERTRAIN COMPLETE — {elapsed}s\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"Experiments: {total_expts:,} | Data: {data_src}\n"
            msg += f"Completed: {completed}\n\n"
            for b in bots:
                line = f"{b['bot']}: {b['win_rate']:.1f}% overall WR"
                if b.get("top_strategy"):
                    line += (f"\n  → Best: {b['top_strategy']} on {b['best_asset']} "
                             f"{b['best_timeframe']} | {b['best_wr']}% WR | "
                             f"{b['winners']} validated combos")
                msg += line + "\n"
            if top_strats:
                msg += "\nTOP CROSS-BOT (50+ trades, Sharpe<1000):\n"
                for s in top_strats[:3]:
                    n_trades = s.get("experiments", "?")
                    msg += (f"  {s['strategy']} | {s['asset']} | {s['timeframe']} "
                            f"| {s['win_rate']}% WR | {s['avg_pnl']:+.4f}% avg P&L "
                            f"| {n_trades} trades\n")
            # Pull 3 sample backtest trades from DB as proof
            try:
                import sqlite3 as _sqlite3
                _conn = _sqlite3.connect(BASE / "logs" / "sentinel_research.db")
                _sample = _conn.execute(
                    "SELECT strategy, asset, timeframe, direction, pnl_pct, win "
                    "FROM experiments WHERE ftmo_compliant=1 ORDER BY RANDOM() LIMIT 3"
                ).fetchall()
                _conn.close()
                if _sample:
                    msg += "\nSAMPLE REAL TRADES (from DB):\n"
                    for s in _sample:
                        outcome = "WIN" if s[5] else "LOSS"
                        msg += f"  {outcome} | {s[0]} {s[1]} {s[2]} {s[3]} | {s[4]:+.3f}%\n"
            except Exception:
                pass
            msg += "\nSource: sentinel_research-2.py | /proof for full verification"

            send(OWNER_ID, msg)
            research_flag.unlink()
            actions_taken.append("AutoResearch callback delivered")
            log_to_oracle(f"AutoResearch callback sent: {len(bots)} bots, top={top_strats[0]['strategy'] if top_strats else 'none'}")
        except Exception as e:
            log_bug(f"AutoResearch callback error: {e}")

    # CHECK 1: APEX trade close alert — fires even in QUIET_MODE
    # Wire this when APEX goes live: apex_state["last_closed"] triggers here
    # Example: send(OWNER_ID, f"APEX closed {symbol} {pnl_pct:+.2f}%")

    if not QUIET_MODE:
        # APEX P&L in-trade alerts (noisy — disabled in quiet mode)
        try:
            if apex_state_file.exists():
                apex_state = json.loads(apex_state_file.read_text())
                active = apex_state.get("active")
                if active:
                    entry   = active.get("entry", 0)
                    product = active.get("product", "BTC-USD")
                    direction = active.get("direction", "BUY")
                    try:
                        r = requests.get(
                            f"https://api.coinbase.com/api/v3/brokerage/products/{product}",
                            timeout=5
                        )
                        if r.status_code == 200:
                            price   = float(r.json().get("price", 0))
                            pnl_pct = (price - entry) / entry if direction == "BUY" else (entry - price) / entry
                            if pnl_pct >= 0.02:
                                send(OWNER_ID, f"APEX up {pnl_pct*100:.1f}% on {active.get('symbol','BTC')} — trailing stop holding")
                                actions_taken.append(f"APEX +{pnl_pct*100:.1f}%")
                            elif pnl_pct <= -0.01:
                                send(OWNER_ID, f"APEX down {pnl_pct*100:.1f}% on {active.get('symbol','BTC')} — watch stop")
                                actions_taken.append(f"APEX {pnl_pct*100:.1f}%")
                    except: pass
        except: pass

    # CHECK 2: Bot health — auto-restart silently in quiet mode
    issues = check_bot_health()
    if issues:
        restarted = auto_restart_bots(issues)
        if restarted and not QUIET_MODE:
            send(OWNER_ID, f"Auto-restarted: {', '.join(restarted)}")
            actions_taken.append(f"Restarted: {restarted}")

    # CHECK 2b: ORACLE process — restart immediately if down, don't alert
    global last_oracle_alert, last_2am_pitch, last_3am_research
    oracle_proc = subprocess.run(["pgrep", "-f", "oracle_listener.py"], capture_output=True, text=True)
    if not oracle_proc.stdout.strip():
        try:
            oracle_log = BASE / "logs" / "oracle_listener.log"
            oracle_log.parent.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(
                ["python3", "-u", str(BASE / "oracle_listener.py")],
                cwd=str(BASE),
                stdout=open(str(oracle_log), "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            actions_taken.append("ORACLE restarted")
            # Only tell Ty once per hour — not every 30 min
            if time.time() - last_oracle_alert > 3600:
                send(OWNER_ID, "ORACLE was down — restarted it.")
                last_oracle_alert = time.time()
        except Exception as oe:
            actions_taken.append(f"ORACLE restart failed: {oe}")

    # CHECK 3: Big P&L milestone — log only
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    if total_pnl >= 200:
        log_to_oracle(f"Daily P&L hit ${total_pnl:.2f}")

    # CHECK 4: Daily log after 11pm
    now = datetime.now()
    if now.hour >= 23:
        today_log = DAILY / f"{now.strftime('%Y-%m-%d')}.md"
        if not today_log.exists():
            consolidate_memory()
            actions_taken.append("Daily log written")

    # CHECK 5: ORACLE messages
    check_oracle_messages()

    # ── OVERNIGHT INCOME ACTION LOOP ─────────────────────────────────────────
    # Runs every heartbeat (30 min). All 4 paths always active.

    # PATH 1: APEX idle check — log only, APEX Telegrams its own trade events
    try:
        apex_state_file = BASE / "shared" / "apex_state.json"
        if apex_state_file.exists():
            apex_state = json.loads(apex_state_file.read_text())
            if not apex_state.get("active"):
                saved_time = apex_state.get("saved", "")
                if saved_time:
                    idle_secs = (datetime.now() - datetime.fromisoformat(saved_time)).total_seconds()
                    idle_hrs = idle_secs / 3600
                    actions_taken.append(f"APEX idle {idle_hrs:.1f}h (no alert — APEX self-reports)")
    except Exception as e:
        log_bug(f"APEX idle check error: {e}")

    # CHECK 0: Win rate emergency — any live bot below 55% WR triggers immediate action
    try:
        for bot, data in perf.items():
            if not isinstance(data, dict): continue
            if data.get("mode") != "live": continue
            wr     = data.get("win_rate", 1.0)
            trades = data.get("trades", 0)
            if trades >= 5 and wr < 0.55:
                task = f"EMERGENCY: {bot} win rate is {wr*100:.1f}% over {trades} trades — below 55% threshold. Pull recent trade log from hive_mind.json, diagnose what's failing (entry too early? stop too tight? wrong direction bias?), run AutoResearch via sentinel_research-2.py, and return a specific fix with updated params."
                pending_path = BASE / "memory" / "tasks" / "pending.md"
                existing = pending_path.read_text() if pending_path.exists() else "# Pending Tasks\n\n"
                if f"EMERGENCY: {bot}" not in existing:
                    pending_path.write_text(existing.rstrip() + f"\n- [AUTO_IMPROVE] {task}\n")
                    send(OWNER_ID, f"{bot} WIN RATE EMERGENCY: {wr*100:.1f}% over {trades} trades. Attacking now — queued diagnosis + AutoResearch.")
                    actions_taken.append(f"{bot} WR emergency queued")
    except Exception as e:
        log_bug(f"WR emergency check error: {e}")

    # PATH 1b: Graduation monitoring — check DRIFT/TITAN/SENTINEL progress every heartbeat
    try:
        grad_all = hive.get("graduation", {})
        for bot in ["DRIFT", "TITAN", "SENTINEL"]:
            g = grad_all.get(bot, {})
            if not g:
                continue
            stage = g.get("stage", "backtesting")
            if stage == "backtesting":
                t   = g.get("backtest_trades", 0)
                tgt = g.get("backtest_target", 100)
                wr  = g.get("backtest_wins", 0) / max(t, 1)
                pnl = g.get("backtest_pnl", 0.0)
                log_to_oracle(f"[GRADUATION] {bot} backtesting: {t}/{tgt} trades | {wr*100:.1f}% WR | P&L {pnl:+.3f}%")
            elif stage == "paper":
                t   = g.get("paper_trades", 0)
                tgt = g.get("paper_target", 200)
                wr  = g.get("paper_wins", 0) / max(t, 1)
                pnl = g.get("paper_pnl", 0.0)
                log_to_oracle(f"[GRADUATION] {bot} paper: {t}/{tgt} trades | {wr*100:.1f}% WR | P&L {pnl:+.3f}%")
            elif stage == "live_pending":
                log_to_oracle(f"[GRADUATION] {bot} live_pending — awaiting Ty approval")
    except Exception as e:
        log_bug(f"Graduation monitor error: {e}")

    # PATH 2: SENTINEL training — queue if not running
    try:
        sentinel_proc = subprocess.run(["pgrep", "-f", "sentinel_research"], capture_output=True, text=True)
        if not sentinel_proc.stdout.strip():
            pending_path = BASE / "memory" / "tasks" / "pending.md"
            pending_content = pending_path.read_text() if pending_path.exists() else ""
            if "sentinel" not in pending_content.lower():
                task = "Run sentinel_research-2.py backtest with min SL 1.0%, log results to logs/sentinel_research.log"
                pending_path.write_text(pending_content.rstrip() + f"\n- [AUTO_IMPROVE] {task}\n")
                actions_taken.append("SENTINEL training queued")
    except Exception as e:
        log_bug(f"SENTINEL training check error: {e}")

    # PATH 3: Unexecuted AUTO_IMPROVE tasks — kick auto_improver if any waiting >10 min
    try:
        pending_path = BASE / "memory" / "tasks" / "pending.md"
        if pending_path.exists():
            pending_lines = pending_path.read_text().splitlines()
            waiting = [l for l in pending_lines if "[AUTO_IMPROVE]" in l and "[DONE]" not in l and not l.strip().startswith("#")]
            if waiting:
                subprocess.Popen(
                    ["python3", str(BASE / "auto_improver.py"), "--run-now"],
                    cwd=str(BASE),
                    stdout=open(str(BASE / "logs" / "auto_improver.log"), "a"),
                    stderr=subprocess.STDOUT
                )
                actions_taken.append(f"Kicked auto_improver ({len(waiting)} tasks)")
    except Exception as e:
        log_bug(f"AUTO_IMPROVE kick error: {e}")

    # PATH 4: Daily P&L pace — LIVE bots only, never mix paper
    try:
        live_pnl = sum(
            d.get("daily_pnl", 0) for d in perf.values()
            if isinstance(d, dict) and d.get("mode") == "live"
        )
        day_of_month = datetime.now().day
        target_pace = 500 * day_of_month
        if live_pnl < -50:
            # Only alert if actually losing money — that's "something broken"
            send(OWNER_ID, f"LIVE P&L: ${live_pnl:+.2f} today — losing money. Investigating.")
            actions_taken.append(f"Live P&L loss alert: ${live_pnl:+.2f}")
    except Exception as e:
        log_bug(f"P&L pace check error: {e}")

    # ── OVERNIGHT INCOME ACTIONS (time-gated, once per night) ────────────────

    # ACTION 1 — 2am: draft trading signal pitch and send via Gmail autonomously
    if now.hour == 2 and last_2am_pitch != now.date():
        try:
            pitch = ask_ai(
                "Write a 3-sentence cold email pitch for a crypto trading signal service. "
                "The sender is Trading Bot Squad, a fully automated system generating signals "
                "on BTC using a machine-learning scalper. Be direct, professional, specific. "
                "No fluff. End with a clear call to action."
            )
            if pitch:
                if PROSPECT_EMAIL:
                    result = send_gmail(PROSPECT_EMAIL, "Automated BTC Trading Signals — Trading Bot Squad", pitch)
                    log_to_oracle(f"2am pitch sent to {PROSPECT_EMAIL}: {result}")
                    actions_taken.append(f"2am pitch sent: {PROSPECT_EMAIL}")
                else:
                    # No prospect email set — save pitch to file for Ty to review
                    pitch_file = BASE / "memory" / "content" / f"pitch_{now.strftime('%Y-%m-%d')}.md"
                    pitch_file.parent.mkdir(parents=True, exist_ok=True)
                    pitch_file.write_text(f"# 2am Pitch — {now.strftime('%Y-%m-%d')}\n\n{pitch}\n")
                    log_to_oracle(f"2am pitch drafted (no PROSPECT_EMAIL set): {pitch[:80]}")
                    actions_taken.append("2am pitch drafted — set PROSPECT_EMAIL in .env to auto-send")
            last_2am_pitch = now.date()
        except Exception as e:
            log_bug(f"2am pitch error: {e}")

    # ACTION 2 — 3am: research free crypto signal APIs, queue best result as AUTO_IMPROVE task
    if now.hour == 3 and last_3am_research != now.date():
        try:
            raw = smart_research("free crypto signal API 2026")
            if raw:
                summary = ask_ai(
                    f"Based on this search result, identify the single best free crypto signal API "
                    f"available in 2026. Give the name, URL, and one sentence on how to wire it into "
                    f"a Python trading bot. Be specific and actionable.\n\n{raw[:1500]}"
                )
                if summary:
                    task = f"Research and wire this free crypto signal source into apex_coingecko.py or sentinel_research-2.py: {summary[:200]}"
                    pending_path = BASE / "memory" / "tasks" / "pending.md"
                    existing = pending_path.read_text() if pending_path.exists() else "# Pending Tasks\n\n"
                    pending_path.write_text(existing.rstrip() + f"\n- [AUTO_IMPROVE] {task}\n")
                    log_to_oracle(f"3am research queued: {summary[:80]}")
                    actions_taken.append("3am API research task queued")
            last_3am_research = now.date()
        except Exception as e:
            log_bug(f"3am research error: {e}")

    # Proactive 30-min messages — disabled in quiet mode
    if not QUIET_MODE:
        try:
            msg = generate_proactive_message()
            if msg:
                send(OWNER_ID, msg)
                log_to_oracle(f"Proactive heartbeat sent: {msg[:80]}...")
        except Exception as e:
            log_bug(f"Proactive message error: {e}")

    if actions_taken:
        log_to_oracle(f"Heartbeat safety checks: {actions_taken}")

CHAT_LOG_DIR = BASE / "logs" / "chat"
CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _history_add(user_text: str, assistant_text: str):
    """Append one exchange to the rolling conversation history AND persist to daily log."""
    global _conversation_history
    _conversation_history.append({"role": "user",      "content": user_text})
    _conversation_history.append({"role": "assistant", "content": assistant_text})
    if len(_conversation_history) > MAX_HISTORY:
        _conversation_history = _conversation_history[-MAX_HISTORY:]
    # Persist to daily chat log (JSONL) for nightly self-improvement review
    try:
        daily_log = CHAT_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(daily_log, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "user": user_text,
                "assistant": assistant_text,
            }) + "\n")
    except Exception:
        pass


def handle_message(text, chat_id):
    global _conversation_history, _research_ran
    _research_ran = False  # reset each message — must be re-earned by actual web_search() call
    text_lower = text.strip().lower()
    print(f"[NEXUS] Received: {text}")
    log_to_oracle(f"Ty said: {text}")

    # Auto-add tasks to master checklist when Ty gives instructions
    task_triggers = ["fix", "build", "add", "wire", "make", "create", "upgrade", "implement", "lower", "raise", "give", "pivot"]
    if any(text_lower.startswith(t) or text_lower.startswith("btw " + t) for t in task_triggers):
        task_summary = text[:120].replace("btw ", "").strip()
        add_to_checklist(task_summary, owner="Codey", status="pending")
    try:
        total_pnl=sum(v.get("daily_pnl",0) for v in read_hive().get("bot_performance",{}).values() if isinstance(v,dict) and v.get("mode")=="live")
    except:
        total_pnl=0.0
    # Always calculate total_pnl upfront
    try:
        _h = read_hive()
        total_pnl = sum(v.get("daily_pnl",0) for v in _h.get("bot_performance",{}).values() if isinstance(v,dict))
    except:
        total_pnl = 0.0

    def cmd(*phrases):
        """True only if text_lower exactly equals a phrase or starts with it followed by a space/newline."""
        for p in phrases:
            if text_lower == p:
                return True
            if text_lower.startswith(p + " ") or text_lower.startswith(p + "\n"):
                return True
        return False

    def reply(msg_text: str):
        """Send response and record exchange in conversation history.
        Uses voice reply when Ty sent a voice note (via smart_send)."""
        smart_send(chat_id, msg_text)
        _history_add(text, msg_text)

    # ── Standing order detection — fires before all other handlers ────────────
    STANDING_ORDER_TRIGGERS = ["always ", "never ", "from now on", "remember that",
                                "from here on", "going forward, ", "make sure you always",
                                "make sure you never", "every time "]
    is_standing_order = (
        len(text.strip()) > 15
        and any(t in text_lower for t in STANDING_ORDER_TRIGGERS)
        and not cmd("/status", "/pnl", "/health", "/train", "/research",
                    "/content", "/memory", "/skills", "/ideas", "/oracle",
                    "/delegate", "/composio", "/help", "/remember", "/selfcheck")
    )
    if is_standing_order:
        append_goal(text.strip())
        reply("Locked in. Added to standing orders.")
        return

    # Status
    if cmd("/status", "bot status", "show status", "show me status", "how are the bots"):
        msg = get_status_report()
        reply(msg)
        return

    # P&L
    if cmd("/pnl", "pnl", "profit", "how much"):
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        total = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
        msg = "P&L REPORT\n━━━━━━━━━━━━━━━━━━━━━\n"
        for bot, data in perf.items():
            if isinstance(data, dict):
                pnl = data.get('daily_pnl', 0)
                flag = "+" if pnl >= 0 else "-"
                msg += f"{flag} {bot}: ${pnl:+.2f}\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"Total: ${total:+.2f}\n"
        msg += f"Monthly pace: ${total*30:+,.0f}/mo\n"
        msg += f"Bills: {'covered' if total*30 >= 15000 else 'behind — need more'}"
        reply(msg)
        return

    # Strategies
    if cmd("/strategies", "top strategies", "best strategies", "show strategies"):
        winners = read_winners()
        strategies = winners.get("top_strategies", [])
        hive = read_hive()
        blacklist = hive.get("sentinel_blacklist", [])
        msg = "TOP STRATEGIES\n━━━━━━━━━━━━━━━━━━━━━\n"
        for i, s in enumerate(strategies[:5], 1):
            msg += f"{i}. {s['strategy']} | {s['asset']} | {s['timeframe']}\n"
            msg += f"   WR: {s['win_rate']}% | P&L: {s['avg_pnl']}%\n"
        if blacklist:
            msg += f"\n{len(blacklist)} strategies blacklisted"
        reply(msg)
        return

    # Proof — HARD DATA ONLY. No emotional responses. No deflection.
    if cmd("/proof", "show proof", "prove it", "show me proof"):
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        lines = [f"PROOF OF WORK — {datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}", "━" * 40]

        # 1. RUNNING PROCESSES — actual PIDs
        # Use stem names (no .py) for pgrep to match both "python script.py" and full-path launches
        lines.append("\n1. RUNNING PROCESSES")
        for name, pattern in [("NEXUS", "nexus_brain"), ("APEX", "apex_coingecko"),
                               ("DRIFT", "drift"), ("TITAN", "titan"),
                               ("SENTINEL", "sentinel_polymarket"), ("ORACLE", "oracle_listener"),
                               ("SCHEDULER", "scheduler")]:
            r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
            pids = r.stdout.strip().replace("\n", ",")
            lines.append(f"  {name}: {'PID ' + pids if pids else 'NOT RUNNING'}")

        # 2. LAST 5 TRADES — from apex_state.json history + sentinel history
        lines.append("\n2. LAST 5 TRADES")
        trades_found = []
        # APEX trades from state
        apex_state_file = BASE / "shared" / "apex_state.json"
        if apex_state_file.exists():
            try:
                ast = json.loads(apex_state_file.read_text())
                for t in ast.get("history", [])[-5:]:
                    trades_found.append(f"  APEX {t.get('direction','?')} {t.get('symbol','?')} | "
                                       f"P&L: {t.get('pnl_pct',0):+.3f}% | {t.get('close_time', t.get('time','?'))[:19]}")
            except Exception:
                pass
        # SENTINEL trades from history
        sentinel_hist = BASE / "shared" / "sentinel_history.json"
        if sentinel_hist.exists():
            try:
                sh = json.loads(sentinel_hist.read_text())
                for t in sh[-5:]:
                    trades_found.append(f"  SENTINEL {t.get('action','?')} {t.get('market','?')[:40]} | "
                                       f"P&L: {t.get('pnl_pct',0):+.2f}% | {t.get('closed_at', t.get('opened_at','?'))[:19]}")
            except Exception:
                pass
        if trades_found:
            for t in trades_found[-5:]:
                lines.append(t)
        else:
            # Fallback: hive_mind trade counts
            for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
                bd = perf.get(bot, {}) if isinstance(perf.get(bot), dict) else {}
                lines.append(f"  {bot}: {bd.get('trades',0)} trades today | WR: {bd.get('win_rate',0)*100:.1f}% | P&L: ${bd.get('daily_pnl',0):+.2f}")

        # 3. HYPERTRAIN — last run timestamp + WR results
        lines.append("\n3. HYPERTRAIN RESULTS")
        import glob as _glob
        train_files = sorted(_glob.glob(str(BASE / "logs/training/squad_training_*.json")))
        if train_files:
            last = json.loads(Path(train_files[-1]).read_text())
            lines.append(f"  Last run: {last.get('timestamp', 'unknown')[:19]}")
            lines.append(f"  Experiments: {last.get('experiments_per_bot', 0)}/bot")
            for bot, res in last.get("results", {}).items():
                if isinstance(res, dict):
                    lines.append(f"  {bot}: WR {res.get('best_win_rate',0):.1%} | Sharpe {res.get('best_sharpe',0):.2f} | {res.get('improvements',0)} improvements")
        else:
            winners_file = BASE / "memory" / "sentinel_winners.json"
            if winners_file.exists():
                try:
                    wdata = json.loads(winners_file.read_text())
                    lines.append(f"  Last run: {wdata.get('completed', 'unknown')[:19]}")
                    lines.append(f"  Total experiments: {wdata.get('total_experiments', 0)}")
                    for b in wdata.get("bots", []):
                        lines.append(f"  {b['bot']}: {b.get('win_rate',0):.1f}% WR | top: {b.get('top_strategy','?')} {b.get('best_asset','?')} {b.get('best_timeframe','?')}")
                except Exception:
                    lines.append("  (error reading results)")
            else:
                lines.append("  No training results found")

        # 4. STRATEGY SOURCES — verified URLs
        lines.append("\n4. STRATEGY SOURCES")
        lines.append("  APEX: EMA 9/21 + RSI(7) scalp → tadonomics.com/best-indicators-for-scalping")
        lines.append("  DRIFT: MACD(12,26,9) + RSI(14) → quantifiedstrategies.com/macd-and-rsi-strategy")
        lines.append("  TITAN: Multi-EMA + VWAP → medium.com/@redsword_23261")
        lines.append("  SENTINEL: Polymarket conviction → gamma-api.polymarket.com")
        lines.append("  Backtest data: Coinbase OHLCV via ccxt (real candles)")

        # 5. PENDING CHECKLIST ITEMS
        lines.append("\n5. PENDING TASKS")
        checklist_path = BASE / "memory" / "tasks" / "master_checklist.md"
        if checklist_path.exists():
            cl = checklist_path.read_text().splitlines()
            pending = [l for l in cl if "| pending |" in l.lower() or "| blocked |" in l.lower() or "| in_progress |" in l.lower()]
            if pending:
                for l in pending[:10]:
                    parts = [p.strip() for p in l.split("|") if p.strip()]
                    if len(parts) >= 4:
                        lines.append(f"  [{parts[3].upper()}] {parts[1]}")
            else:
                lines.append("  All tasks complete")
        else:
            lines.append("  No checklist found")

        reply("\n".join(lines))
        return

    # Browse — NEXUS browses a URL and sends summary + screenshot
    if cmd("/browse", "browse ", "go to ", "open "):
        import re as _re
        urls = _re.findall(r'https?://\S+', text)
        if not urls:
            # Try to construct URL from text
            target = text_lower.replace("/browse", "").replace("browse", "").replace("go to", "").replace("open", "").strip()
            if target and "." in target:
                urls = [f"https://{target}" if not target.startswith("http") else target]
        if urls:
            reply(f"Browsing {urls[0]}...")
            content, screenshot = browse_and_screenshot(urls[0])
            if screenshot:
                try:
                    with open(screenshot, "rb") as f:
                        requests.post(
                            f"{API}/sendPhoto",
                            data={"chat_id": chat_id, "caption": content[:1000]},
                            files={"photo": f},
                            timeout=30,
                        )
                except Exception:
                    reply(content[:2000])
            else:
                reply(content[:2000])
        else:
            reply("Send a URL to browse. Example: /browse coindesk.com")
        return

    # Train / AutoResearch
    if cmd("/train", "/autoresearch", "train all", "run training", "start training",
           "run hypertraining", "run autoresearch", "run auto research", "autoResearch",
           "auto research", "run research on", "research all", "research the best"):
        success = run_all_training()
        if success:
            # Report what's actually being tested — all 8 assets, not just BTC
            # Pull actual watchlist from hive_mind if available, no hardcoded assets
            _hive_wl = read_hive().get("apex_daily_watchlist", {}).get("assets", [])
            assets = ", ".join(_hive_wl) if _hive_wl else "top movers (scanned daily from CoinGecko)"
            msg = (f"AutoResearch running now.\n"
                   f"All 4 bots × 10,000 experiments each.\n"
                   f"Assets: {assets}\n"
                   f"Timeframes: 1m, 5m, 15m, 1h, 6h\n"
                   f"Real Coinbase candles — no simulation.\n"
                   f"Results saved to sentinel_winners.json when done.")
            # Also surface most recent prior results if they exist
            winners = read_winners()
            if winners and winners.get("top_strategies"):
                top = winners["top_strategies"][:3]
                completed = winners.get("completed", "unknown")[:16]
                msg += f"\n\nLAST RUN ({completed}):"
                for s in top:
                    msg += f"\n  {s['strategy']} | {s['asset']} | {s['timeframe']} — {s['win_rate']}% WR"
        else:
            msg = "Could not start AutoResearch. Check logs/nexus.log."
        reply(msg)
        return

    # Health
    if cmd("/health", "check bots", "bot health", "health check", "are bots running"):
        issues = check_bot_health()
        if issues:
            msg = f"{len(issues)} issue(s):\n" + "\n".join(f"• {i}" for i in issues)
            restarted = auto_restart_bots(issues)
            if restarted:
                msg += f"\nAuto-restarted: {', '.join(restarted)}"
        else:
            msg = "All processes running."
        reply(msg)
        return

    # Research — smart routing with real sources and URL citations
    if cmd("/research", "research ", "look up"):
        query = text.replace("/research", "").replace("research", "").replace("look up", "").strip()
        if query:
            raw = smart_research(query)
            # AI summarizes the real data, cites URLs, no fabrication
            summary = ask_ai(
                f"Research query: {query}\n\n"
                f"Real data from search (use ONLY this — no fabrication):\n{raw[:2500]}\n\n"
                f"Summarize key findings in 3-5 sentences. "
                f"Cite the specific source URLs from the data above. "
                f"If the data contains prices or percentages, include exact numbers. "
                f"Never add facts not present in the data above.",
                history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None,
            ) or raw[:600]
            msg = f"RESEARCH: {query}\n━━━━━━━━━━━━━━━━━━━━━\n{summary}"
            # Always append raw sources so URLs are visible
            if raw and raw != summary:
                source_lines = [l for l in raw.splitlines() if l.strip().startswith("URL:") or l.strip().startswith("http")]
                if source_lines:
                    msg += "\n\nSOURCES:\n" + "\n".join(source_lines[:6])
            reply(msg)
        else:
            reply("What do you want me to research?")
        return

    # Content / social media
    if cmd("/content", "make a post", "write a post", "generate content", "write content", "social media post"):
        topic = text.replace("/content", "").strip() or None
        post = generate_content(topic)
        reply(f"POST GENERATED\n\n{post}\n\nSaved to memory/content/")
        return

    # Outreach templates
    if cmd("/outreach", "write outreach", "outreach template", "pitch template"):
        kind = "prop_firm"
        if "investor" in text_lower: kind = "investor"
        elif "collab" in text_lower: kind = "collab"
        content = generate_outreach(kind)
        # If email address in message, send via Gmail
        import re as _re
        email_match = _re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text)
        if email_match:
            to_addr = email_match.group(0)
            result = send_gmail(to_addr, f"Trading Bot Squad — {kind} outreach", content)
            reply(f"OUTREACH ({kind}) drafted and sent.\n{result}")
        else:
            reply(f"OUTREACH ({kind})\n\n{content}\n\nSaved to memory/content/ — add an email address to send it.")
        return

    # Save a lesson to memory
    if cmd("/remember", "remember this", "save this", "note this"):
        lesson = text.replace("/remember", "").replace("remember this", "").replace("save this", "").replace("note this", "").strip()
        if lesson:
            save_lesson(lesson, category="ty_instruction")
            reply("Saved to memory.")
        return

    # Memory consolidation
    if cmd("/memory", "consolidate memory", "daily log", "show memory", "what happened today"):
        content = consolidate_memory()
        if content:
            reply(f"DAILY MEMORY CONSOLIDATED\n{content[:600]}")
        return

    # Skill scanner
    if cmd("/skills", "what skills", "show skills", "list skills"):
        skills_dir = BASE / "node_modules" / "openclaw" / "skills"
        useful = ["github", "discord", "slack", "notion", "trello", "weather",
                  "summarize", "web-search", "coding-agent", "oracle", "tmux",
                  "blogwatcher", "obsidian", "spotify-player", "healthcheck"]
        if skills_dir.exists():
            available = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            highlighted = [s for s in available if s in useful]
            rest = [s for s in available if s not in useful]
            msg = (f"OPENCLAW SKILLS ({len(available)} total)\n"
                   f"━━━━━━━━━━━━━━━━━━━━━\n"
                   f"Most useful:\n" +
                   "\n".join(f"  {s}" for s in highlighted) +
                   f"\n\nAll: {', '.join(rest)}")
        else:
            msg = "OpenClaw skills directory not found."
        reply(msg)
        return

    # Income ideas
    if cmd("/ideas", "income ideas", "money ideas", "give me ideas", "income opportunities"):
        idea = generate_income_idea()
        reply(idea)
        return

    # Oracle message
    if cmd("/oracle", "tell oracle", "ask oracle", "oracle:"):
        message = text.replace("/oracle", "").replace("tell oracle", "").replace("ask oracle", "").strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{timestamp}] [PENDING] Ty via NEXUS:\n{message}\n")
        reply(f"Sent to ORACLE. Response in ~2 min.")
        return

    # Delegate a task to Claude Code
    if cmd("/delegate", "build this", "code this", "hey claude", "tell claude to", "ask claude to"):
        task = (text.replace("/delegate", "")
                    .replace("build this", "")
                    .replace("code this", "")
                    .replace("hey claude", "")
                    .replace("tell claude to", "")
                    .replace("ask claude to", "")
                    .strip())
        if task:
            status = delegate_to_claude(task)
            reply(status)
        else:
            reply("What should Claude build?")
        return

    # Self-check — reads real logs, reports real errors, queues real fixes
    if cmd("/selfcheck", "run a self check", "self check", "selfcheck", "run selfcheck", "check yourself", "check the logs"):
        logs_dir = BASE / "logs"
        error_patterns = ["error", "traceback", "exception", "failed", "crashed", "critical"]
        findings = []  # (log_file, line)

        log_targets = [
            "nexus.log", "apex_coingecko.log", "oracle_listener.log",
            "auto_improver.log", "consolidate.log", "warden.log"
        ]

        for log_name in log_targets:
            log_path = logs_dir / log_name
            if not log_path.exists():
                continue
            try:
                lines = log_path.read_text(errors="ignore").splitlines()
                recent = lines[-50:]  # last 50 lines only
                for line in recent:
                    ll = line.lower()
                    if any(p in ll for p in error_patterns):
                        # Skip known harmless noise and already-fixed markers
                        if "notopenssl" in ll or "urllib3" in ll or "notopensslwarning" in ll:
                            continue
                        if "auto_improver fixed" in ll:
                            continue
                        # Skip auto_improver's own task-running output — prevents cascade loops
                        # where selfcheck sees "[AUTO_IMPROVER] [FAILED]" and creates a new task
                        if log_name == "auto_improver.log" and any(skip in ll for skip in [
                            "[auto_improver] running:", "[auto_improver] [failed]",
                            "[auto_improver] found", "[auto_improver] done",
                        ]):
                            continue
                        findings.append((log_name, line.strip()))
            except Exception as e:
                findings.append((log_name, f"Could not read log: {e}"))

        if not findings:
            reply("Checked all logs. No errors found.")
            return

        # Deduplicate — keep unique error messages (cap at 8)
        seen = set()
        unique = []
        for src, line in findings:
            key = line[:80]
            if key not in seen:
                seen.add(key)
                unique.append((src, line))
        unique = unique[:8]

        # Build report
        report_lines = [f"SELF-CHECK — {len(unique)} issue(s) found\n━━━━━━━━━━━━━━━━━━━━━"]
        task_lines = []
        for src, line in unique:
            short = line[:120]
            report_lines.append(f"[{src}] {short}")
            task_lines.append(f"In {src}: {short} — diagnose root cause and fix")

        # Write one task to pending.md per unique error
        pending = BASE / "memory" / "tasks" / "pending.md"
        try:
            existing = pending.read_text() if pending.exists() else "# Pending Tasks\n\n"
            new_tasks = "\n".join(f"- [AUTO_IMPROVE] {t}" for t in task_lines)
            pending.write_text(existing.rstrip() + "\n\n" + new_tasks + "\n")
            report_lines.append(f"\n{len(task_lines)} fix task(s) queued in pending.md.")
        except Exception as e:
            report_lines.append(f"\nCouldn't write to pending.md: {e}")

        reply("\n".join(report_lines))
        return

    # Composio tool execution
    if cmd("/composio", "composio "):
        parts = text.replace("/composio", "").replace("composio", "").strip().split(" ", 1)
        action = parts[0].upper() if parts else ""
        if action:
            result = composio_action(action)
            reply(f"Composio {action}:\n{result[:500]}")
        else:
            tools_msg = "Composio tools:\nGOOGLESHEETS_BATCH_UPDATE\nGITHUB_CREATE_ISSUE\nGMAIL_SEND_EMAIL\n\nUsage: /composio ACTION_NAME"
            if not COMPOSIO_KEY:
                tools_msg += "\n\nCOMPOSIO_API_KEY not set in .env."
            reply(tools_msg)
        return

    # /proof duplicate removed — single handler exists above (line ~2762)

    # /checklist — show master checklist
    if cmd("/checklist", "show checklist", "task list", "what's pending"):
        checklist_path = BASE / "memory" / "tasks" / "master_checklist.md"
        if checklist_path.exists():
            lines = checklist_path.read_text().splitlines()
            # Extract pending/in_progress items
            active = [l for l in lines if "pending" in l.lower() or "in_progress" in l.lower() or "blocked" in l.lower()]
            done_count = len([l for l in lines if "| done |" in l.lower() or "| verified |" in l.lower()])
            total = len([l for l in lines if l.strip().startswith("|") and l.strip()[1:2].strip().isdigit()])
            msg = f"MASTER CHECKLIST\n━━━━━━━━━━━━━━━━━━━━━\n{done_count}/{total} tasks done\n\n"
            if active:
                msg += "PENDING/BLOCKED:\n"
                for l in active[:15]:
                    # Extract task name and status from table row
                    parts = [p.strip() for p in l.split("|") if p.strip()]
                    if len(parts) >= 4:
                        msg += f"• {parts[1]} [{parts[2]}] — {parts[3]}\n"
            else:
                msg += "All tasks complete."
            reply(msg)
        else:
            reply("No checklist found. Ask Codey to build it.")
        return

    # Help
    if any(x in text_lower for x in ["/help", "help", "commands", "what can you do"]):
        msg = ("NEXUS — Commands\n━━━━━━━━━━━━━━━━━━━━━\n"
               "Just talk naturally — or use:\n\n"
               "/status — all bots + P&L\n"
               "/pnl — profit report\n"
               "/strategies — top strategies\n"
               "/train — run ALL bots training\n"
               "/health — check + auto-fix bots\n"
               "/research [topic] — web search\n"
               "/content — social media post\n"
               "/memory — consolidate daily log\n"
               "/ideas — income opportunities\n"
               "/oracle [msg] — message ORACLE\n"
               "/browse [url] — read any webpage\n"
               "/pdf [topic] — generate PDF report\n"
               "/selfcheck — scan all logs, report errors, queue fixes\n"
               "/delegate [task] — send task to Claude Code\n"
               "/composio — use business tool integrations\n"
               "/proof — show citable proof of all training, research, and bot state\n"
               "/checklist — master task list with status\n"
               "YouTube links — auto-summarized")
        reply(msg)
        return

    # YouTube URL — auto-detect any youtube link in the message
    if re.search(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts)", text_lower):
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            send(chat_id, "Pulling YouTube info...", force=True)
            result = summarize_youtube(url_match.group(0))
            reply(result[:1000])
            return

    # Web browsing via Playwright
    if cmd("/browse", "browse ", "open url", "read this link", "check this link"):
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            url = url_match.group(0)
            raw = browse_url(url)
            summary = ask_ai(
                f"Summarize this webpage in 3-5 sentences, focus on what's relevant for a crypto trader:\n\n{raw[:2000]}"
            ) or raw[:600]
            page_msg = f"PAGE SUMMARY\n━━━━━━━━━━━━━━━━━━━━━\n{summary}"
            reply(page_msg)
        else:
            reply("Send me a URL to browse.")
        return

    # PDF report generation
    if cmd("/pdf", "make a pdf", "create a pdf", "generate pdf", "save as pdf"):
        topic = re.sub(r"^(/pdf|make a pdf|create a pdf|generate pdf|save as pdf)\s*", "", text, flags=re.IGNORECASE).strip()
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        _pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
        if topic:
            pdf_content = ask_ai(
                f"Write a detailed report about: {topic}\nContext: Trading bot squad. Squad P&L today: ${_pnl:+.2f}. Target: $100K/month."
            ) or topic
            pdf_title = topic[:50]
        else:
            pdf_content = get_status_report()
            pdf_title = "NEXUS Status Report"
        result = create_pdf(pdf_title, pdf_content)
        pdf_msg = f"PDF saved: {result}" if "error" not in result.lower() else f"PDF failed: {result}"
        reply(pdf_msg)
        return

    # ── Scheduled task detection ─────────────────────────────────────────────
    # Detects when Ty assigns a recurring task. Saves to scheduled.json and confirms.
    _schedule_triggers = [
        "every morning", "every day", "each morning", "each day", "daily at",
        "every hour", "each hour", "hourly", "remind me to", "remind me every",
        "every night", "each night", "nightly", "every week", "weekly",
        "every monday", "every tuesday", "every wednesday", "every thursday",
        "every friday", "every saturday", "every sunday",
        "send me a report", "give me a report", "morning report", "evening report",
        "check in at", "update me at", "alert me at", "ping me at",
        "schedule a", "set a reminder",
    ]
    _is_schedule_task = (
        not text.strip().startswith("/")
        and any(trig in text_lower for trig in _schedule_triggers)
    )
    if _is_schedule_task:
        # Parse schedule from text
        schedule = "daily"
        run_time = "08:00"
        time_match = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', text_lower)
        if time_match:
            h = int(time_match.group(1))
            m = int(time_match.group(2) or 0)
            meridiem = time_match.group(3)
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            run_time = f"{h:02d}:{m:02d}"
        if "hour" in text_lower:
            schedule = "hourly"
            run_time = None
        elif "week" in text_lower or any(d in text_lower for d in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]):
            schedule = "weekly"
        elif "once" in text_lower or "one time" in text_lower:
            schedule = "once"
        task = add_scheduled_task(text, schedule, run_time)
        time_str = f" at {run_time}" if run_time else ""
        reply(f"Locked in. {schedule.capitalize()} task{time_str} — I'll run it automatically. [{task['id']}]")
        return

    # ── STRATEGY GATE — unbreakable ──────────────────────────────────────────
    # Any question about strategy, win rates, entry/exit logic, indicators, or
    # bot performance MUST go through smart_research() before generating an
    # answer. No exceptions. AI memory alone is never sufficient.
    _is_strategy_question = (
        not text.strip().startswith("/")
        and any(trig in text_lower for trig in STRATEGY_RESEARCH_TRIGGERS)
        and not any(excl in text_lower for excl in NL_RESEARCH_EXCLUDES)
    )
    if _is_strategy_question:
        raw = smart_research(text)
        # Also pull hive_mind data for any live bot performance context
        hive_perf = read_hive().get("bot_performance", {})
        hive_lines = []
        for bot, data in hive_perf.items():
            if isinstance(data, dict) and data.get("trades", 0) > 0:
                wr = data.get("win_rate", 0) * 100
                pnl = data.get("daily_pnl", 0)
                hive_lines.append(f"{bot}: {wr:.1f}% WR, ${pnl:+.2f} day P&L, {data.get('trades',0)} trades")
        hive_ctx = "\nLIVE BOT PERFORMANCE (hive_mind.json):\n" + "\n".join(hive_lines) if hive_lines else ""
        summary = ask_ai(
            f'Ty asked: "{text}"\n\n'
            f"Real research data (use ONLY this — no fabrication):\n{raw[:2500]}"
            f"{hive_ctx}\n\n"
            f"Answer based strictly on the data above. Cite specific numbers, strategies, or sources. "
            f"If the data doesn't answer the question, say what's missing and what you'd need to run. "
            f"Never invent percentages or claim strategies work without evidence in the data above.",
            history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None,
        ) or raw[:600]
        source_lines = [l.strip() for l in raw.splitlines() if l.strip().startswith("URL:") or l.strip().startswith("http")]
        if source_lines:
            summary += "\n\nSources:\n" + "\n".join(source_lines[:5])
        reply(summary)
        return

    # ── Natural language research detection ──────────────────────────────────
    # Fires before the general AI catch-all. If Ty says anything research-like
    # in natural conversation, smart_research() runs and cites real sources.
    # No slash command needed.
    _word_count_pre = len(text.strip().split())
    _is_nl_research = (
        _word_count_pre >= 4                                       # skip one-liners like "what's up"
        and not text.strip().startswith("/")                       # not an explicit command
        and any(trig in text_lower for trig in NL_RESEARCH_TRIGGERS)
        and not any(excl in text_lower for excl in NL_RESEARCH_EXCLUDES)
        and not any(text_lower.startswith(p) for p in [           # skip already-handled commands
            "bot status", "show status", "show me status",
            "how are the bots", "check bots", "bot health",
            "pnl", "profit", "how much", "show pnl",
        ])
    )
    if _is_nl_research:
        raw = smart_research(text)
        summary = ask_ai(
            f'Ty asked: "{text}"\n\n'
            f"Real data from search (use ONLY this — no fabrication):\n{raw[:2500]}\n\n"
            f"Answer his question in 3-5 sentences using the data above. "
            f"Cite specific source URLs or names. If it's market data, include exact numbers. "
            f"Never add facts not present in the data above. "
            f"Sound like a knowledgeable partner, not a search engine.",
            history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None,
        ) or raw[:600]
        msg = summary
        # Append source URLs so Ty can verify
        source_lines = [l.strip() for l in raw.splitlines() if l.strip().startswith("URL:") or l.strip().startswith("http")]
        if source_lines:
            msg += "\n\nSources:\n" + "\n".join(source_lines[:5])
        reply(msg)
        return

    # Everything else — detect personal vs trading, route to correct prompt
    word_count = len(text.strip().split())
    is_command_phrase = any(text_lower.startswith(p) or p in text_lower for p in COMMAND_PHRASES)
    is_personal = (
        not text.strip().startswith("/")
        and not is_command_phrase
        and not text.strip().endswith("?")
        and word_count <= 15
        and not any(kw in text_lower for kw in TRADING_KEYWORDS)
    )

    if is_personal:
        # Personal/emotional message — Soul.md only, no status noise
        soul = read_soul()
        prompt = f'Ty said: "{text}"\n\nRespond as yourself. 1-2 sentences. Human first.'
        response = ask_ai(
            prompt,
            system=PERSONAL_SYSTEM,
            history=None
        )
    else:
        hive = read_hive()
        total_pnl = sum(v.get("daily_pnl", 0) for v in hive.get("bot_performance", {}).values() if isinstance(v, dict))
        prompt = f"""Ty said: "{text}"

Respond directly to what he said. Don't give a status report unless he asked for one.

Context (use only if relevant): Squad P&L today ${total_pnl:+.2f}. Mission: $100K/month combined.

1-3 sentences."""
        response = ask_ai(
            prompt,
            history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None
        )

    if response:
        # ── Auto-queue interceptor ───────────────────────────────────────────
        # If NEXUS suggests a concrete action (backtest, retrain, AutoResearch),
        # queue it immediately as [AUTO_IMPROVE] in pending.md — no permission needed.
        _action_phrases = [
            "we should run a backtest", "should run backtest", "run a backtest",
            "should retrain", "should run autoresearch", "should run auto research",
            "suggest running autoresearch", "suggest a backtest", "recommend retraining",
            "recommend running autoresearch", "queue autoresearch", "queue a backtest",
            "run autoresearch on", "run a new backtest", "time to retrain",
        ]
        _resp_lower_aq = response.lower()
        if any(p in _resp_lower_aq for p in _action_phrases):
            try:
                _pending = BASE / "memory" / "tasks" / "pending.md"
                _existing = _pending.read_text() if _pending.exists() else "# Pending Tasks\n\n"
                _task = f"AutoResearch triggered by NEXUS suggestion: {text[:120]}"
                if _task[:40] not in _existing:
                    with open(_pending, "a") as _f:
                        _f.write(f"\n- [AUTO_IMPROVE] {_task}\n")
                    print(f"[NEXUS] Auto-queued: {_task[:60]}")
            except Exception as _eq:
                print(f"[NEXUS] Auto-queue error: {_eq}")

        # ── Deferred-promise interceptor ─────────────────────────────────────
        # If the AI response contains a promise of future action, execute that
        # action NOW and replace or append real results before sending.
        _promise_phrases = [
            "running research now", "running that now", "checking that now",
            "looking into that", "looking into it", "i'll look", "ill look",
            "i'll check", "ill check", "i'll research", "ill research",
            "checking now", "researching now", "pulling that", "pulling data",
            "on it", "give me a moment", "give me a sec", "one moment",
            "one sec", "i'll get back", "ill get back", "will check",
            "will look", "will research", "will pull",
        ]
        _resp_lower = response.lower()
        if any(p in _resp_lower for p in _promise_phrases):
            print(f"[NEXUS] Intercepted deferred promise — executing research immediately")
            _actual = smart_research(text)
            _grounded = ask_ai(
                f'Ty asked: "{text}"\n\n'
                f"Real research data:\n{_actual[:2500]}\n\n"
                f"Answer using only this data. No deferred promises. If data is thin, say so and cite what you found.",
                history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None,
            )
            if _grounded:
                _src = [l.strip() for l in _actual.splitlines() if l.strip().startswith("URL:") or l.strip().startswith("http")]
                response = _grounded + ("\n\nSources:\n" + "\n".join(_src[:5]) if _src else "")
        # ── Agent SDK execution interceptor — Phase 2 ────────────────────────
        # If NEXUS says she's doing something, ACTUALLY DO IT via Agent SDK tools.
        # This is what makes her a real CEO, not a talking head.
        sdk_result = execute_decision(response, context=text)
        if sdk_result:
            print(f"[NEXUS] SDK execution complete: {sdk_result}")

        _history_add(text, response)
        smart_send(chat_id, response)
    # else: AI unavailable — go silent

def run():
    global last_oracle_check, last_proactive, last_autonomous, last_heartbeat, last_memory_consolidation, last_income_idea, last_oracle_alert, last_2am_pitch, last_3am_research

    print("="*55)
    print("NEXUS BRAIN V3")
    print('"Making sure Ty never worries about money."')
    print("="*55)

    # Quiet startup — no Telegram noise on every restart
    print(f"[NEXUS] Online. Soul: {SOUL.name} | User: {USER_MD.name} | Heartbeat: {HEARTBEAT.name}")

    offset = None
    last_2am_consolidation = None   # track date of last 2am run
    last_230am_consolidation = None
    last_1am_self_improve = None    # nightly self-improvement (Felix-style)
    last_6am_morning_report = None  # morning 5-priority report to Ty

    while True:
        try:
            now = datetime.now()

            # ── Telegram updates ──────────────────────────────────────────
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")
                voice = msg.get("voice", {})
                if chat_id == str(OWNER_ID):
                    if text:
                        handle_message(text, chat_id)
                    elif voice:
                        transcribed = transcribe_voice(voice["file_id"])
                        if transcribed:
                            # Reply with voice when Ty sends voice
                            _voice_reply_mode[0] = True
                            handle_message(transcribed, chat_id)
                            _voice_reply_mode[0] = False
                        else:
                            send(chat_id, "Couldn't transcribe that one. Try again or type it.", force=True)

            # ── Scheduled tasks — check every loop iteration ──────────────
            if OWNER_ID:
                try:
                    check_scheduled_tasks(str(OWNER_ID))
                except Exception as _e:
                    print(f"[NEXUS] Scheduled task error: {_e}")

            # ── Claude Code bridge — check every loop iteration ─────────
            try:
                check_claude_bridge()
            except Exception as _e:
                pass

            # ── ORACLE bridge every 2 minutes ─────────────────────────────
            if (now - last_oracle_check).total_seconds() >= 120:
                check_oracle_messages()
                last_oracle_check = now

            # ── AUTONOMOUS LOOP every 15 minutes — NEXUS acts, doesn't wait ─
            if (now - last_autonomous).total_seconds() >= AUTONOMOUS_INTERVAL:
                autonomous_loop()
                last_autonomous = now

            # ── HEARTBEAT / proactive Ty message every 30 minutes ─────────
            if (now - last_proactive).total_seconds() >= 1800:
                proactive_check()
                last_proactive = now

            # ── 1am: Felix-style nightly self-improvement ─────────────────
            if now.hour == 1 and now.minute < 10 and last_1am_self_improve != now.date():
                print("[NEXUS] 1am self-improvement loop starting...")
                try:
                    nightly_self_improvement()
                except Exception as _e:
                    print(f"[NEXUS] Self-improvement error: {_e}")
                last_1am_self_improve = now.date()

            # ── 2am memory consolidation (primary) ───────────────────────
            if now.hour == 2 and now.minute < 5 and last_2am_consolidation != now.date():
                print("[NEXUS] 2am consolidation running...")
                consolidate_memory()
                save_lesson(f"2am consolidation completed on {now.strftime('%Y-%m-%d')}", "system")
                last_2am_consolidation = now.date()
                last_memory_consolidation = now

            # ── 2:30am consolidation (redundant backup) ───────────────────
            if now.hour == 2 and now.minute >= 30 and now.minute < 35 and last_230am_consolidation != now.date():
                print("[NEXUS] 2:30am backup consolidation running...")
                consolidate_memory()
                last_230am_consolidation = now.date()

            # ── 6am: morning priority report to Ty ──────────────────────
            if now.hour == 6 and now.minute < 10 and last_6am_morning_report != now.date():
                print("[NEXUS] 6am morning report...")
                try:
                    morning_priority_report()
                except Exception as _e:
                    print(f"[NEXUS] Morning report error: {_e}")
                last_6am_morning_report = now.date()

            # ── 11pm — nightly training for all bots ─────────────────────
            if now.hour == 23 and now.minute < 5 and (now - last_heartbeat).total_seconds() >= 3600:
                print("[NEXUS] Starting nightly training...")
                run_all_training()
                last_heartbeat = now

            time.sleep(2)

        except KeyboardInterrupt:
            print("\nNEXUS V3 stopped.")
            break
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[NEXUS CRASH] {e}\n{tb}", flush=True)
            log_bug(f"V3 crash: {e}\n{tb}")
            time.sleep(5)

if __name__ == "__main__":
    run()

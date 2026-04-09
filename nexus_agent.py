"""
NEXUS Agent — Phase 1: Tool-Use Decision Engine
Uses Anthropic SDK tool_use to make NEXUS's decisions structured and auditable.
Runs alongside existing nexus_brain_v3.py — feature-flagged, not a replacement yet.

Tools defined: restart_apex, check_hive, adjust_threshold, force_close_trade, run_hypertrain
"""

import os, json, subprocess, fcntl, time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env", override=True)

HIVE = BASE / "shared" / "hive_mind.json"
HIVE_LOCK = BASE / "shared" / "hive_mind.lock"
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"

# ── File-locked hive access ──────────────────────────────────────────────────

def _hive_read():
    try:
        with open(HIVE_LOCK, "a+") as lf:
            fcntl.flock(lf, fcntl.LOCK_SH)
            try:
                return json.loads(HIVE.read_text()) if HIVE.exists() else {}
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except:
        return {}

def _hive_write(data):
    with open(HIVE_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            HIVE.write_text(json.dumps(data, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS — the actual work behind each tool call
# ═══════════════════════════════════════════════════════════════════════════════

BOT_SCRIPTS = {
    "APEX": "apex_coingecko.py",
    "DRIFT": "drift.py",
    "TITAN": "titan.py",
    "SENTINEL": "sentinel_polymarket.py",
    "ORACLE": "oracle_listener.py",
    "SCHEDULER": "scheduler.py",
}

def _restart_bot(bot_name: str, reason: str = "") -> str:
    """Kill and restart any bot process."""
    script = BOT_SCRIPTS.get(bot_name.upper())
    if not script:
        return json.dumps({"status": "error", "message": f"Unknown bot: {bot_name}. Valid: {list(BOT_SCRIPTS.keys())}"})

    subprocess.run(["pkill", "-f", script], capture_output=True)
    time.sleep(1)

    log_name = Path(script).stem + ".log"
    log = open(BASE / "logs" / log_name, "a")
    proc = subprocess.Popen(
        ["python3", "-u", str(BASE / script)],
        cwd=str(BASE), start_new_session=True,
        stdout=log, stderr=subprocess.STDOUT,
    )

    _log_action("restart_bot", {"bot": bot_name, "script": script, "reason": reason, "new_pid": proc.pid})
    return json.dumps({"status": "restarted", "bot": bot_name, "pid": proc.pid, "reason": reason})


def _check_hive() -> str:
    """Read current bot performance and system state from hive_mind.json."""
    hive = _hive_read()
    perf = hive.get("bot_performance", {})
    result = {}
    for bot, data in perf.items():
        if isinstance(data, dict):
            result[bot] = {
                "daily_pnl": data.get("daily_pnl", 0),
                "trades": data.get("trades", 0),
                "win_rate": data.get("win_rate", 0),
                "confidence_score": data.get("confidence_score", 0.5),
                "mode": data.get("mode", "unknown"),
            }

    # Check running processes — use stem patterns for reliable pgrep matching
    procs = {}
    for display, pattern in [("apex_coingecko.py", "apex_coingecko"),
                              ("drift.py", "drift"),
                              ("titan.py", "titan"),
                              ("sentinel_polymarket.py", "sentinel_polymarket"),
                              ("nexus_brain_v3.py", "nexus_brain"),
                              ("oracle_listener.py", "oracle_listener"),
                              ("scheduler.py", "scheduler")]:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        procs[display] = "running" if r.stdout.strip() else "stopped"

    return json.dumps({"bot_performance": result, "processes": procs}, indent=2)


def _adjust_threshold(bot_name: str, param_name: str, new_value: float) -> str:
    """Adjust a bot parameter in hive_mind.json via nexus_apex_overrides."""
    hive = _hive_read()
    override_key = f"nexus_{bot_name.lower()}_overrides"
    overrides = hive.get(override_key, {})
    old_value = overrides.get(param_name, "not_set")
    overrides[param_name] = new_value
    hive[override_key] = overrides
    _hive_write(hive)

    _log_action("adjust_threshold", {
        "bot": bot_name, "param": param_name,
        "old": old_value, "new": new_value,
    })
    return json.dumps({
        "status": "updated", "bot": bot_name,
        "param": param_name, "old_value": old_value, "new_value": new_value,
    })


def _force_close_trade(bot_name: str, reason: str = "agent_decision") -> str:
    """Write a force-close flag for the specified bot."""
    if bot_name.upper() == "APEX":
        flag = BASE / "shared" / "apex_force_close.flag"
        flag.write_text(json.dumps({"reason": reason, "time": datetime.now().isoformat()}))
        _log_action("force_close_trade", {"bot": "APEX", "reason": reason})
        return json.dumps({"status": "close_flag_written", "bot": "APEX", "reason": reason})
    return json.dumps({"status": "error", "message": f"Force close not implemented for {bot_name}"})


def _run_hypertrain(experiments: int = 100) -> str:
    """Start a HyperTrain cycle in the background."""
    # Check if already running
    r = subprocess.run(["pgrep", "-f", "hypertrain.py"], capture_output=True, text=True)
    if r.stdout.strip():
        return json.dumps({"status": "already_running", "pids": r.stdout.strip().split()})

    log_name = f"hypertrain_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
    log = open(BASE / "logs" / log_name, "w")
    proc = subprocess.Popen(
        ["python3", "-u", str(BASE / "hypertrain.py")],
        cwd=str(BASE), start_new_session=True,
        stdout=log, stderr=subprocess.STDOUT,
    )
    _log_action("run_hypertrain", {"pid": proc.pid, "experiments": experiments})
    return json.dumps({"status": "started", "pid": proc.pid, "log": log_name})


# ── Action log ────────────────────────────────────────────────────────────────

def _log_action(tool_name: str, details: dict):
    """Append every tool call to an audit log."""
    log_file = BASE / "logs" / "agent_actions.jsonl"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool_name,
        "details": details,
    }
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL SCHEMAS — Anthropic tool_use format
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "restart_bot",
        "description": "Kill and restart any bot process. Use when a bot is crashed, stuck, or needs to reload new parameters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_name": {"type": "string", "enum": ["APEX", "SENTINEL", "ORACLE", "SCHEDULER"], "description": "Which bot to restart"},
                "reason": {"type": "string", "description": "Why the bot is being restarted"},
            },
            "required": ["bot_name", "reason"],
        },
    },
    {
        "name": "check_hive",
        "description": "Read current bot performance (P&L, trades, win rate, confidence) and process status from hive_mind.json. Use this to assess squad health before making decisions.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "adjust_threshold",
        "description": "Adjust a bot parameter in hive_mind.json. APEX reads these overrides every tick. Use for min_momentum, stop_loss, trailing_stop, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_name": {"type": "string", "enum": ["APEX", "DRIFT", "TITAN", "SENTINEL"]},
                "param_name": {"type": "string", "description": "Parameter to adjust (e.g. min_momentum, stop_loss_pct)"},
                "new_value": {"type": "number", "description": "New value for the parameter"},
            },
            "required": ["bot_name", "param_name", "new_value"],
        },
    },
    {
        "name": "force_close_trade",
        "description": "Force-close a bot's current open trade by writing a flag file. The bot reads this flag on its next tick and exits the position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bot_name": {"type": "string", "enum": ["APEX", "DRIFT", "TITAN", "SENTINEL"]},
                "reason": {"type": "string", "description": "Why the trade is being force-closed"},
            },
            "required": ["bot_name", "reason"],
        },
    },
    {
        "name": "run_hypertrain",
        "description": "Start a HyperTrain optimization cycle in the background. Tests 100 parameter variations per bot using real Coinbase candle backtests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "experiments": {"type": "integer", "description": "Experiments per bot (default 100)", "default": 100},
            },
        },
    },
]

# Map tool names to implementations
TOOL_HANDLERS = {
    "restart_bot": lambda args: _restart_bot(args["bot_name"], args.get("reason", "")),
    "check_hive": lambda args: _check_hive(),
    "adjust_threshold": lambda args: _adjust_threshold(args["bot_name"], args["param_name"], args["new_value"]),
    "force_close_trade": lambda args: _force_close_trade(args["bot_name"], args.get("reason", "agent_decision")),
    "run_hypertrain": lambda args: _run_hypertrain(args.get("experiments", 100)),
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT LOOP — send message to Claude, execute tool calls, return final answer
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are NEXUS, the head coach of a crypto trading bot squad.
You have 5 tools to manage the squad. Use them to take action — don't just describe what you'd do.

Squad: APEX (scalper), DRIFT (swing), TITAN (position), SENTINEL (Polymarket arb).
All paper trading. Goal: $100K/month combined.

Rules:
- Check hive_mind before making decisions (use check_hive)
- If a bot is crashed, restart it immediately
- If win rate drops below 40%, investigate and adjust thresholds
- Never adjust parameters without checking current state first
- Log every action with a reason
"""


def run_agent(user_message: str, max_turns: int = 5) -> str:
    """Run the NEXUS agent loop: message → tool calls → final response."""
    try:
        import anthropic
    except ImportError:
        return "Error: anthropic SDK not installed"

    if not ANTHROPIC_KEY:
        return "Error: ANTHROPIC_API_KEY not set"

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    messages = [{"role": "user", "content": user_message}]

    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text and tool calls
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        if not tool_calls:
            # No tools called — return final text
            return "\n".join(text_parts)

        # Execute tool calls and build tool_result messages
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            handler = TOOL_HANDLERS.get(tc.name)
            if handler:
                result = handler(tc.input)
                print(f"[AGENT] Tool: {tc.name} → {result[:200]}")
            else:
                result = json.dumps({"error": f"Unknown tool: {tc.name}"})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            return "\n".join(text_parts) if text_parts else "Agent completed with tool calls only."

    return "Agent reached max turns without final response."


# ═══════════════════════════════════════════════════════════════════════════════
# CLI interface for testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Check the squad health and tell me what needs attention."

    print(f"[NEXUS AGENT] Query: {query}")
    print("=" * 60)
    result = run_agent(query)
    print("=" * 60)
    print(result)

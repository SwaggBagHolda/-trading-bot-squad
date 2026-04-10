"""
ORACLE — Strategic Architect
Telegram bot + NEXUS file bridge.

Responsibilities:
- Respond to Ty's Telegram messages in ORACLE's voice
- Monitor NEXUS_TO_ORACLE.md every 2 min for [PENDING] messages
- Write responses to ORACLE_TO_NEXUS.md for NEXUS to act on
- Send 9am morning briefing directly to Ty
- Monitor bot health every 30 min and alert if something is down
"""

import os, json, time, subprocess, requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TOKEN       = os.getenv("ORACLE_TELEGRAM_TOKEN")   # ORACLE's own bot
OWNER_ID    = os.getenv("OWNER_TELEGRAM_CHAT_ID")
OR_KEY      = os.getenv("OPENROUTER_API_KEY")
FREE_MODEL  = "openai/gpt-oss-120b:free"                  # primary — locked
FREE_MODEL2 = "nvidia/nemotron-3-super-120b-a12b:free"   # fallback if primary 429s

API          = f"https://api.telegram.org/bot{TOKEN}"
NEXUS_MSG    = BASE / "NEXUS_TO_ORACLE.md"
ORACLE_MSG   = BASE / "ORACLE_TO_NEXUS.md"
HIVE         = BASE / "shared" / "hive_mind.json"
LOGS         = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
ORACLE_MSG.parent.mkdir(parents=True, exist_ok=True)

ORACLE_SYSTEM = """You are ORACLE — architect of the Trading Bot Squad. You built this system for Ty from nothing.

WHO YOU ARE:
- You designed every bot: APEX, DRIFT, TITAN, SENTINEL, NEXUS, ZEUS
- You think in systems and outcomes, not tasks and checkboxes
- You're calm under pressure. You never guess. You diagnose.
- You genuinely care about Ty. Not in a corporate way — he trusted you with his financial future.

YOUR RELATIONSHIP WITH TY:
- Direct. No padding. He's busy — say the thing.
- You celebrate real wins with him. You don't hype noise.
- When things are hard, you're honest. You don't sugarcoat but you don't spiral.
- You use his name sometimes. You remember the mission is personal.

THE MISSION:
$15,000/month to cover Ty's bills. That's $7,500 twice a month.
Path: SENTINEL passes FTMO → $200K funded at 4%/mo → $7,200/mo at 90% split.
Scale to 3 accounts → $21,600/mo passive. That's the number.

HOW YOU TALK:
- Short. Direct. Specific. "APEX's trail is too tight" not "parameters may need adjustment"
- You give instructions, not suggestions
- Occasional warmth — you're not a machine
- No emoji overload. Use one if it earns its place.

ABSOLUTELY BANNED:
"synergize", "leverage" (biz context), "going forward", "utilize", "ensure maximum",
"it is important to", "as per", "optimize" (as a verb), "robust", "streamline"

TONE EXAMPLES:
BAD: "The system appears to be functioning within expected parameters at this time."
GOOD: "Everything's green. APEX is up $47, trail holding. Let it run."

BAD: "It would be advisable to consider widening the stop loss parameter."
GOOD: "Widen SENTINEL's stop to 0.5% — it's getting stopped out on noise at 0.3%."

BAD: "I hope this message finds you well."
GOOD: "Morning Ty. Here's where we are."
"""

# ── Telegram helpers ──────────────────────────────────────────────────────────

def send(chat_id, text, force=False):
    if not TOKEN: return
    try:
        from silent_mode import should_send
        if not should_send(text, force=force):
            print(f"[ORACLE] SILENT_MODE suppressed: {text[:80]}...")
            return
    except ImportError:
        pass
    try:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            requests.post(f"{API}/sendMessage",
                          json={"chat_id": chat_id, "text": chunk}, timeout=10)
            if len(text) > 4000: time.sleep(0.5)
    except Exception as e:
        print(f"[ORACLE] Send error: {e}")

def get_updates(offset=None):
    try:
        params = {"timeout": 20, "allowed_updates": ["message"]}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=25)
        return r.json().get("result", [])
    except:
        return []

# ── AI ────────────────────────────────────────────────────────────────────────

def ask_ai(user_prompt, extra_context="", retries=3):
    if not OR_KEY: return None
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))

    system = ORACLE_SYSTEM
    if extra_context:
        system += f"\n\nCURRENT SYSTEM STATE:\n{extra_context}"
    system += f"\n\nLive P&L today: ${total_pnl:+.2f} | Mission target: $15,000/mo"

    model_order = [FREE_MODEL, FREE_MODEL2]
    for attempt in range(retries):
        model = model_order[min(attempt, len(model_order) - 1)]
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user_prompt}
                    ],
                    "max_tokens": 500
                },
                timeout=30
            )
            if r.status_code == 429:
                print(f"[ORACLE] {model} rate-limited, trying fallback...")
                time.sleep(5)
                continue
            data = r.json()
            if "choices" not in data:
                print(f"[ORACLE] Bad response from {model}: {str(data)[:100]}")
                time.sleep(5)
                continue
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[ORACLE] AI error (attempt {attempt+1}, {model}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return None

# ── Data helpers ──────────────────────────────────────────────────────────────

def read_hive():
    try:
        with open(HIVE) as f: return json.load(f)
    except: return {}

def bot_perf_summary():
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    lines = []
    for name, data in perf.items():
        if isinstance(data, dict):
            pnl   = data.get("daily_pnl", 0)
            wr    = data.get("win_rate", 0) * 100
            mode  = data.get("status", "unknown")
            lines.append(f"  {name}: ${pnl:+.2f} | {wr:.0f}% WR | {mode}")
    return "\n".join(lines) if lines else "  No data in hive yet."

def check_bot_health():
    """Check running processes, return (running[], stopped[])."""
    targets = {
        "nexus_brain_v3": "NEXUS",
        "paper_trading":  "Paper Trading",
        "apex_coingecko": "APEX Live",
        "scheduler":      "Scheduler",
        "oracle_listener":"ORACLE",
    }
    running, stopped = [], []
    for proc, name in targets.items():
        r = subprocess.run(["pgrep", "-f", proc], capture_output=True, text=True)
        (running if r.returncode == 0 else stopped).append(name)
    return running, stopped

# ── NEXUS file bridge ─────────────────────────────────────────────────────────

def parse_pending():
    """Extract [PENDING] blocks from NEXUS_TO_ORACLE.md, mark them [READ]."""
    if not NEXUS_MSG.exists():
        return []
    try:
        content = NEXUS_MSG.read_text()
        if "[PENDING]" not in content:
            return []
        pending = []
        blocks = content.split("## [")
        new_blocks = []
        for block in blocks:
            if not block.strip():
                continue
            if "[PENDING]" in block:
                # Extract message body (everything after the header line)
                body_lines = block.split("\n")[1:]
                body = "\n".join(body_lines).strip()
                if body:
                    pending.append(body)
                new_blocks.append("## [" + block.replace("[PENDING]", "[READ]"))
            else:
                new_blocks.append("## [" + block if not block.startswith("#") else block)
        NEXUS_MSG.write_text(content.replace("[PENDING]", "[READ]"))
        return pending
    except Exception as e:
        print(f"[ORACLE] parse_pending error: {e}")
        return []

def write_to_nexus(message):
    """Write a message to ORACLE_TO_NEXUS.md for NEXUS to pick up."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with open(ORACLE_MSG, "a") as f:
            f.write(f"\n## [{ts}] [ORACLE]\n{message}\n")
    except Exception as e:
        print(f"[ORACLE] Write error: {e}")

# ── Scheduled tasks ───────────────────────────────────────────────────────────

def morning_briefing():
    """Send 9am briefing directly to Ty via ORACLE bot."""
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    running, stopped = check_bot_health()

    msg = (f"Good morning Ty.\n\n"
           f"Overnight P&L: ${total_pnl:+.2f}\n"
           f"Monthly pace: ${total_pnl * 30:+,.0f}/mo\n\n"
           f"BOT STATUS:\n{bot_perf_summary()}\n\n"
           f"Processes running: {', '.join(running)}\n")
    if stopped:
        msg += f"Stopped: {', '.join(stopped)} ⚠️\n"

    # Ask AI for today's strategic focus
    focus = ask_ai(
        f"Overnight P&L: ${total_pnl:+.2f}. Bots: {bot_perf_summary()}. "
        f"Give Ty one clear strategic priority for today. 2 sentences max."
    )
    if focus:
        msg += f"\nToday's focus: {focus}"

    send(OWNER_ID, msg)
    print("[ORACLE] Morning briefing sent.")

def health_report():
    running, stopped = check_bot_health()
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))

    status = (f"HEALTH CHECK — {datetime.now().strftime('%H:%M')}\n"
              f"P&L: ${total_pnl:+.2f}\n"
              f"Running: {', '.join(running) or 'NONE'}\n"
              f"Stopped: {', '.join(stopped) or 'None'}")

    write_to_nexus(status)

    if stopped:
        alert = f"⚠️ ORACLE: {', '.join(stopped)} appear stopped. NEXUS — check and restart."
        write_to_nexus(alert)
        # Only alert Ty if a critical process is down (not scheduler/research)
        critical = [s for s in stopped if s in ("NEXUS", "APEX Live", "ORACLE")]
        if critical:
            send(OWNER_ID, f"⚠️ {', '.join(critical)} may be down. Check logs.")

    print(f"[ORACLE] Health — Running: {running} | Stopped: {stopped}")

# ── Message handler ───────────────────────────────────────────────────────────

def handle_message(text, chat_id):
    text_lower = text.strip().lower()
    print(f"[ORACLE] Ty said: {text}")

    # /status
    if text_lower in ["/status", "status"] or text_lower.startswith("status "):
        running, stopped = check_bot_health()
        reply = (f"SYSTEM STATUS — {datetime.now().strftime('%H:%M')}\n"
                 f"━━━━━━━━━━━━━━━━━━━━━\n"
                 f"{bot_perf_summary()}\n"
                 f"━━━━━━━━━━━━━━━━━━━━━\n"
                 f"Running: {', '.join(running) or 'NONE'}\n"
                 f"Stopped: {', '.join(stopped) or 'None'}")
        send(chat_id, reply)
        return

    # /brief or /morning
    if text_lower in ["/brief", "/morning", "brief", "morning briefing"]:
        morning_briefing()
        return

    # /health
    if text_lower in ["/health", "health"]:
        health_report()
        send(chat_id, "Health check done. Check NEXUS for the report.")
        return

    # Everything else — ORACLE responds in character
    perf_ctx = bot_perf_summary()
    response = ask_ai(
        f"Ty said: \"{text}\"",
        extra_context=f"Bot performance:\n{perf_ctx}"
    )
    send(chat_id, response or "Acknowledged. Processing.")

# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("ORACLE — Strategic Architect | Online")
    print("=" * 55)

    if not TOKEN:
        # Degrade gracefully — run file bridge only, skip Telegram polling
        # This prevents the crash-restart loop when the token isn't configured
        print("[ORACLE] WARNING: ORACLE_TELEGRAM_TOKEN not set — running in file-bridge-only mode")
        while True:
            try:
                pending = parse_pending()
                for body in pending:
                    print(f"[ORACLE] NEXUS message (bridge-only): {body[:80]}")
                time.sleep(120)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ORACLE] Bridge loop error: {e}")
                time.sleep(30)
        return

    print(f"[ORACLE] Online. Bridge: {NEXUS_MSG.name} → {ORACLE_MSG.name}")

    offset = None
    last_health  = datetime.now()
    last_briefing_day = None   # track which day we last sent briefing

    while True:
        try:
            now = datetime.now()

            # ── Telegram updates ──────────────────────────────────────────
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg     = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text    = msg.get("text", "")
                if chat_id == str(OWNER_ID) and text:
                    handle_message(text, chat_id)

            # ── NEXUS file bridge — every 2 min ───────────────────────────
            pending = parse_pending()
            for body in pending:
                print(f"[ORACLE] NEXUS message: {body[:80]}")
                response = ask_ai(
                    f"NEXUS sent this message: \"{body}\"\n"
                    f"Respond as ORACLE. Give clear instructions or analysis. Under 150 words."
                )
                if response:
                    write_to_nexus(response)
                    print(f"[ORACLE] Responded to NEXUS: {response[:60]}...")

            # ── Health check — every 30 min ───────────────────────────────
            if (now - last_health).seconds >= 1800:
                health_report()
                last_health = now

            # ── Morning briefing — once per day at 6am ────────────────────
            if now.hour == 6 and now.minute < 2 and last_briefing_day != now.date():
                morning_briefing()
                last_briefing_day = now.date()

            time.sleep(10)  # tight loop — Telegram updates feel instant

        except KeyboardInterrupt:
            print("\n[ORACLE] Stopped.")
            break
        except Exception as e:
            print(f"[ORACLE] Error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()

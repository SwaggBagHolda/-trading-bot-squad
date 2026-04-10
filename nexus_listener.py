"""
NEXUS LISTENER — Gives NEXUS ears.
Listens to Telegram, acts on commands, relays to ORACLE.
Run alongside scheduler.py — never stop.
"""

import os, json, time, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
ORACLE_MSG = BASE / "ORACLE_TO_NEXUS.md"
NEXUS_MSG = BASE / "NEXUS_TO_ORACLE.md"
HIVE = BASE / "shared" / "hive_mind.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

API = f"https://api.telegram.org/bot{TOKEN}"

def send(chat_id, text, force=False):
    try:
        from silent_mode import should_send
        if not should_send(text, force=force):
            print(f"[NEXUS-L] SILENT_MODE suppressed: {text[:80]}...")
            return
    except ImportError:
        if not force:
            print(f"[NEXUS-L] SILENT_MODE (fallback block): {text[:80]}...")
            return
    try:
        requests.post(f"{API}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=10)
    except: pass

def get_updates(offset=None):
    try:
        params = {"timeout": 20, "allowed_updates": ["message"]}
        if offset:
            params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=25)
        return r.json().get("result", [])
    except:
        return []

def read_hive():
    try:
        with open(HIVE) as f:
            return json.load(f)
    except:
        return {}

def handle_command(text, chat_id):
    """Handle commands from Ty or ORACLE."""
    text = text.strip().lower()

    # STATUS — full system report
    if any(x in text for x in ["/status", "status", "how are the bots"]):
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        msg = "📊 NEXUS STATUS REPORT\n━━━━━━━━━━━━━━━━━━━━━\n"
        for bot, data in perf.items():
            if isinstance(data, dict):
                pnl = data.get('daily_pnl', 0)
                trades = data.get('trades', 0)
                emoji = "✅" if pnl >= 0 else "🔴"
                msg += f"{emoji} {bot}: ${pnl:+.2f} | {trades} trades\n"
        msg += f"\n🕐 {datetime.now().strftime('%I:%M %p')}"
        send(chat_id, msg)

    # TOP STRATEGIES
    elif any(x in text for x in ["/strategies", "best strategy", "top strategies", "what's working"]):
        hive = read_hive()
        strategies = hive.get("sentinel_top_strategies", [])
        if strategies:
            msg = "🏆 TOP STRATEGIES (from SENTINEL training)\n━━━━━━━━━━━━━━━━━━━━━\n"
            for i, s in enumerate(strategies[:5], 1):
                msg += f"{i}. {s['strategy']} | {s['asset']} | {s['timeframe']}\n"
                msg += f"   WR: {s['win_rate']}% | P&L: {s['avg_pnl']}%\n"
        else:
            msg = "No strategies yet. Run SENTINEL training first."
        send(chat_id, msg)

    # P&L REPORT
    elif any(x in text for x in ["/pnl", "pnl", "profit", "how much", "money"]):
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        total = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
        msg = f"💰 DAILY P&L REPORT\n━━━━━━━━━━━━━━━━━━\n"
        for bot, data in perf.items():
            if isinstance(data, dict):
                pnl = data.get('daily_pnl', 0)
                msg += f"{bot}: ${pnl:+.2f}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\nTOTAL: ${total:+.2f}"
        send(chat_id, msg)

    # TRAIN SENTINEL
    elif any(x in text for x in ["/train", "train sentinel", "run training", "10000"]):
        send(chat_id, "🎯 Starting SENTINEL training... will update you every 2,500 experiments.")
        import subprocess
        subprocess.Popen(["python3", str(BASE / "sentinel_research-2.py")])

    # BLACKLIST
    elif any(x in text for x in ["/blacklist", "blacklist", "what to avoid"]):
        hive = read_hive()
        blacklist = hive.get("sentinel_blacklist", [])
        if blacklist:
            msg = "❌ BLACKLISTED STRATEGIES\n━━━━━━━━━━━━━━━━━━━━━\n"
            for s in blacklist[:5]:
                msg += f"• {s['strategy']} | {s['asset']} | WR:{s['win_rate']}%\n"
        else:
            msg = "No blacklisted strategies yet."
        send(chat_id, msg)

    # MESSAGE TO ORACLE
    elif any(x in text for x in ["/oracle", "tell oracle", "ask oracle", "oracle:"]):
        # Strip the command prefix and save to NEXUS_TO_ORACLE.md
        message = text.replace("/oracle", "").replace("tell oracle", "").replace("ask oracle", "").replace("oracle:", "").strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{timestamp}] Message from Ty via NEXUS\n{message}\n")
        send(chat_id, f"✅ Message sent to ORACLE:\n\"{message}\"\n\nORACLE will respond next session.")

    # HELP
    elif any(x in text for x in ["/help", "help", "commands", "what can you do"]):
        msg = ("🤖 NEXUS COMMANDS\n━━━━━━━━━━━━━━━━\n"
               "/status — all bots status\n"
               "/pnl — today's profit/loss\n"
               "/strategies — top winning strategies\n"
               "/blacklist — strategies to avoid\n"
               "/train — run SENTINEL training\n"
               "/oracle [message] — send message to ORACLE\n"
               "/help — this menu\n\n"
               "Or just talk naturally — I understand plain English! 💬")
        send(chat_id, msg)

    # NATURAL LANGUAGE FALLBACK
    else:
        # Save unknown messages to NEXUS_TO_ORACLE for ORACLE to see
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{timestamp}] Ty said:\n{text}\n")
        send(chat_id, "Got it. I'll pass that to ORACLE. 🤖\n\nTry /help to see what I can do right now.")

def check_oracle_messages():
    """Check if ORACLE left new instructions and act on them."""
    try:
        if not ORACLE_MSG.exists():
            return
        with open(ORACLE_MSG) as f:
            content = f.read()
        # Look for unprocessed instructions marked with [PENDING]
        if "[PENDING]" in content:
            lines = content.split("\n")
            for line in lines:
                if "[PENDING]" in line:
                    instruction = line.replace("[PENDING]", "").strip()
                    send(OWNER_ID, f"📨 ORACLE instruction received:\n{instruction}")
            # Mark as processed
            content = content.replace("[PENDING]", "[DONE]")
            with open(ORACLE_MSG, "w") as f:
                f.write(content)
    except:
        pass

def run():
    print("=" * 50)
    print("NEXUS LISTENER — Online and listening")
    print("Waiting for messages on Telegram...")
    print("=" * 50)

    send(OWNER_ID, "👂 NEXUS is now listening!\n\nSend /help to see all commands.\nI understand plain English too — just talk to me!")

    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                # Only respond to owner
                if chat_id == str(OWNER_ID) and text:
                    print(f"[NEXUS] Received: {text}")
                    handle_command(text, chat_id)

            # Check for ORACLE messages every 30 seconds
            check_oracle_messages()
            time.sleep(2)

        except KeyboardInterrupt:
            print("\nNEXUS Listener stopped.")
            break
        except Exception as e:
            print(f"[NEXUS ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()

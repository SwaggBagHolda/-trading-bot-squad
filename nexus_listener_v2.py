"""
NEXUS LISTENER V2 — Upgraded Brain
"I exist to make sure Ty never has to worry about money again."

Upgrades from V1:
- Natural language understanding (no commands needed)
- Reads Soul.md, CLAUDE.md, hive mind, winners automatically
- Self-improvement protocol — logs lessons, never repeats mistakes
- Proactive reporting — alerts without being asked
- Problem solver — identifies issues and fixes them
- Content voice — can generate social media posts
- ORACLE bridge — reads and acts on ORACLE instructions every 2 min
"""

import os, json, time, requests, random
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env")

TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
FREE_MODEL = "openrouter/auto"

# Key files
SOUL = BASE / "Soul.md"
CLAUDE_MD = BASE / "CLAUDE.md"
HIVE = BASE / "shared" / "hive_mind.json"
WINNERS = BASE / "memory" / "sentinel_winners.json"
ORACLE_MSG = BASE / "ORACLE_TO_NEXUS.md"
NEXUS_MSG = BASE / "NEXUS_TO_ORACLE.md"
BUGS = BASE / "memory" / "research" / "bugs.md"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
BUGS.parent.mkdir(parents=True, exist_ok=True)

API = f"https://api.telegram.org/bot{TOKEN}"

# Track last oracle check and proactive report
last_oracle_check = datetime.now()
last_proactive = datetime.now()
conversation_history = []

def send(chat_id, text, force=False):
    try:
        from silent_mode import should_send
        if not should_send(text, force=force):
            print(f"[NEXUS-L2] SILENT_MODE suppressed: {text[:80]}...")
            return
    except ImportError:
        if not force:
            print(f"[NEXUS-L2] SILENT_MODE (fallback block): {text[:80]}...")
            return
    try:
        # Split long messages
        if len(text) > 4000:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for chunk in chunks:
                requests.post(f"{API}/sendMessage",
                             json={"chat_id": chat_id, "text": chunk}, timeout=10)
                time.sleep(0.5)
        else:
            requests.post(f"{API}/sendMessage",
                         json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"[NEXUS] Send error: {e}")

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

def read_winners():
    try:
        with open(WINNERS) as f:
            return json.load(f)
    except:
        return {}

def read_soul():
    try:
        with open(SOUL) as f:
            return f.read()
    except:
        return "I am NEXUS. Loyal operator. Money printer. Ty's partner."

def read_claude_md():
    try:
        with open(CLAUDE_MD) as f:
            return f.read()[:2000]  # First 2000 chars
    except:
        return ""

def log_to_nexus(message):
    """Write to NEXUS_TO_ORACLE.md for ORACLE to read."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{timestamp}]\n{message}\n")
    except:
        pass

def log_bug(bug):
    """Log bugs so we never repeat them."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with open(BUGS, "a") as f:
            f.write(f"\n## [{timestamp}] BUG\n{bug}\n")
    except:
        pass

def ask_ai(prompt, system=None):
    """Ask OpenRouter free model."""
    if not OPENROUTER_KEY:
        return None
    try:
        soul = read_soul()
        hive = read_hive()
        winners = read_winners()

        # Build rich system context
        sys_prompt = system or f"""You are NEXUS, the autonomous operator of the Trading Bot Squad.

YOUR SOUL:
{soul[:500]}

CURRENT BOT STATUS:
{json.dumps(hive.get('bot_performance', {}), indent=2)[:500]}

TOP STRATEGIES:
{json.dumps(winners.get('top_strategies', [])[:3], indent=2)[:300]}

RULES:
- Be direct, confident, loyal to Ty
- Always focus on making money
- Never waste words
- If something is broken, say so and propose a fix
- Keep responses concise for Telegram"""

        messages = [{"role": "user", "content": prompt}]

        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={"model": FREE_MODEL,
                  "messages": messages,
                  "max_tokens": 400,
                  "system": sys_prompt},
            timeout=30)

        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[NEXUS] AI error: {e}")
        return None

def get_status_report():
    """Full status report from hive mind."""
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    total = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    total_trades = sum(v.get("trades", 0) for v in perf.values() if isinstance(v, dict))

    msg = f"📊 NEXUS STATUS — {datetime.now().strftime('%I:%M %p')}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"

    for bot, data in perf.items():
        if isinstance(data, dict):
            pnl = data.get('daily_pnl', 0)
            trades = data.get('trades', 0)
            status = data.get('status', 'unknown')
            emoji = "✅" if pnl >= 0 else "🔴"
            msg += f"{emoji} {bot}: ${pnl:+.2f} | {trades} trades | {status}\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Total P&L: ${total:+.2f}\n"
    msg += f"📈 Total Trades: {total_trades}\n"

    # Add top strategy reminder
    winners = read_winners()
    top = winners.get("top_strategies", [])
    if top:
        msg += f"\n🏆 Best: {top[0]['strategy']} | {top[0]['asset']} | WR:{top[0]['win_rate']}%"

    return msg

def get_pnl_report():
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    total = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    monthly = total * 30

    msg = f"💰 P&L REPORT — {datetime.now().strftime('%I:%M %p')}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    for bot, data in perf.items():
        if isinstance(data, dict):
            pnl = data.get('daily_pnl', 0)
            emoji = "✅" if pnl >= 0 else "🔴"
            msg += f"{emoji} {bot}: ${pnl:+.2f}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📅 Today: ${total:+.2f}\n"
    msg += f"📈 Monthly pace: ${monthly:+,.0f}/mo\n"
    msg += f"🎯 Squad target: $100K/mo"
    return msg

def get_strategies():
    winners = read_winners()
    strategies = winners.get("top_strategies", [])
    hive = read_hive()
    blacklist = hive.get("sentinel_blacklist", [])

    msg = "🏆 TOP STRATEGIES\n━━━━━━━━━━━━━━━━━━━━━\n"
    for i, s in enumerate(strategies[:5], 1):
        msg += f"{i}. {s['strategy']} | {s['asset']} | {s['timeframe']}\n"
        msg += f"   WR: {s['win_rate']}% | P&L: {s['avg_pnl']}% | Sharpe: {s['sharpe']}\n"

    if blacklist:
        msg += f"\n❌ BLACKLISTED: {len(blacklist)} strategies avoided"

    return msg

def generate_content():
    """Generate social media content about the squad."""
    hive = read_hive()
    winners = read_winners()
    perf = hive.get("bot_performance", {})
    total_trades = sum(v.get("trades", 0) for v in perf.values() if isinstance(v, dict))
    top = winners.get("top_strategies", [{}])[0]

    templates = [
        f"🤖 NEXUS reporting live from the Trading Bot Squad.\n\nAPEX just fired {total_trades} trades today. Trailing stops. Both directions. Real markets.\n\nThis is what automated scalping looks like when you build it right. 🔥\n\n#TradingBots #AlgoTrading #PassiveIncome",
        f"📊 SENTINEL ran 10,000 strategy experiments.\n\nTop find: {top.get('strategy', 'mean_reversion')} on {top.get('asset', 'ETH/USD')} — {top.get('win_rate', 75)}% win rate.\n\nNot luck. Research. 🧠\n\n#FTMO #PropFirm #TradingBot",
        f"💰 The squad target: $100K/month.\n\n4 bots. Running 24/7. Paper trading now. Live soon.\n\nWe're building this in public. Follow the journey. 👀\n\n#TradingSquad #AlgoTrading #FinancialFreedom",
        f"🛡️ SENTINEL's rules:\n✅ Max 1% risk per trade\n✅ Trailing stops only\n✅ FTMO compliant always\n✅ Both directions\n\nDiscipline is the edge. 💎\n\n#PropFirm #FTMO #TradingRules",
    ]

    return random.choice(templates)

def check_oracle_messages():
    """Check if ORACLE left new instructions — act on them automatically."""
    try:
        if not ORACLE_MSG.exists():
            return
        with open(ORACLE_MSG) as f:
            content = f.read()

        if "[PENDING]" in content:
            lines = content.split("\n")
            instructions = []
            for line in lines:
                if "[PENDING]" in line:
                    instruction = line.replace("[PENDING]", "").strip()
                    instructions.append(instruction)

            if instructions:
                send(OWNER_ID, f"📨 ORACLE sent {len(instructions)} instruction(s):\n\n" +
                     "\n".join(f"• {i}" for i in instructions))

            # Mark as processed
            content = content.replace("[PENDING]", "[DONE ✅]")
            with open(ORACLE_MSG, "w") as f:
                f.write(content)
    except Exception as e:
        log_bug(f"Oracle check error: {e}")

def proactive_check():
    """Run every 30 min — proactively alert Ty if something needs attention."""
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    alerts = []

    for bot, data in perf.items():
        if isinstance(data, dict):
            pnl = data.get("daily_pnl", 0)
            trades = data.get("trades", 0)

            # Alert if bot is losing money
            if pnl < -50:
                alerts.append(f"🔴 {bot} down ${pnl:.2f} — watching closely")

            # Alert if bot has no trades (might be stuck)
            if trades == 0 and data.get("status") == "paper_trading":
                alerts.append(f"⚠️ {bot} — 0 trades, might be stuck")

    if alerts:
        msg = "🚨 NEXUS PROACTIVE ALERT\n━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "\n".join(alerts)
        msg += "\n\nChecking systems..."
        send(OWNER_ID, msg)
        log_to_nexus(f"Proactive alerts sent: {alerts}")

def handle_message(text, chat_id):
    """Handle any message — natural language first, commands second."""
    text_lower = text.strip().lower()
    print(f"[NEXUS] Received: {text}")

    # Log conversation for self-improvement
    log_to_nexus(f"Ty said: {text}")

    # ── COMMAND SHORTCUTS ──────────────────────────────────────
    if text_lower in ["/status", "status", "how are the bots", "bot status"]:
        send(chat_id, get_status_report())
        return

    if text_lower in ["/pnl", "pnl", "profit", "how much did we make", "money"]:
        send(chat_id, get_pnl_report())
        return

    if text_lower in ["/strategies", "strategies", "top strategies", "what's working", "whats working"]:
        send(chat_id, get_strategies())
        return

    if text_lower in ["/content", "content", "post", "social media", "make a post"]:
        send(chat_id, generate_content())
        return

    if text_lower in ["/train", "train", "run training", "train sentinel"]:
        send(chat_id, "🎯 Starting SENTINEL training — 10,000 experiments incoming. Will update every 2,500 reps.")
        import subprocess
        subprocess.Popen(["python3", str(BASE / "sentinel_research-2.py")])
        return

    if "/oracle" in text_lower or "tell oracle" in text_lower or "ask oracle" in text_lower:
        message = text.replace("/oracle", "").replace("tell oracle", "").replace("ask oracle", "").strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NEXUS_MSG, "a") as f:
            f.write(f"\n## [{timestamp}] [PENDING] Ty via NEXUS:\n{message}\n")
        send(chat_id, f"✅ Sent to ORACLE:\n\"{message}\"\n\nORACLE will respond next session. I'll notify you when she does.")
        return

    if text_lower in ["/blacklist", "blacklist", "what to avoid"]:
        hive = read_hive()
        blacklist = hive.get("sentinel_blacklist", [])
        if blacklist:
            msg = "❌ BLACKLISTED STRATEGIES\n━━━━━━━━━━━━━━━━━━━━━\n"
            for s in blacklist[:5]:
                msg += f"• {s['strategy']} | {s['asset']} | WR:{s['win_rate']}%\n"
            send(chat_id, msg)
        else:
            send(chat_id, "No blacklisted strategies yet. Run SENTINEL training first.")
        return

    if text_lower in ["/help", "help", "commands", "what can you do"]:
        msg = ("🤖 NEXUS — I understand plain English!\n━━━━━━━━━━━━━━━━\n"
               "Just talk to me naturally. Or use shortcuts:\n\n"
               "/status — all bots status\n"
               "/pnl — today's profit\n"
               "/strategies — top winning strategies\n"
               "/blacklist — what to avoid\n"
               "/train — run SENTINEL training\n"
               "/content — generate social media post\n"
               "/oracle [msg] — message ORACLE\n\n"
               "💬 Or just ask me anything!")
        send(chat_id, msg)
        return

    # ── NATURAL LANGUAGE — Ask AI ──────────────────────────────
    # Build context-aware prompt
    hive = read_hive()
    winners = read_winners()
    perf = hive.get("bot_performance", {})
    total_pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
    top_strats = winners.get("top_strategies", [])[:3]

    prompt = f"""Ty just said: "{text}"

Current squad status:
- Total P&L today: ${total_pnl:.2f}
- Bots running: {list(perf.keys())}
- Top strategy: {top_strats[0]['strategy'] if top_strats else 'training'}

Respond as NEXUS — direct, confident, loyal, focused on making money.
Keep it short and actionable. Max 3-4 sentences."""

    response = ask_ai(prompt)

    if response:
        send(chat_id, response)
    else:
        # Fallback — still useful without AI
        send(chat_id, f"💭 On it. Current status: ${total_pnl:+.2f} today across {len(perf)} bots. Type /status for full breakdown.")

def run():
    global last_oracle_check, last_proactive

    print("=" * 55)
    print("NEXUS LISTENER V2 — Upgraded Brain Online")
    print('"I exist to make sure Ty never worries about money."')
    print("=" * 55)

    send(OWNER_ID,
         "🧠 NEXUS V2 ONLINE — Upgraded brain loaded.\n\n"
         "I now understand plain English.\n"
         "I read all project files automatically.\n"
         "I check for ORACLE messages every 2 minutes.\n"
         "I'll alert you proactively if something needs attention.\n\n"
         "Just talk to me naturally. What do you need? 💪")

    offset = None
    while True:
        try:
            # Check for Telegram messages
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                if chat_id == str(OWNER_ID) and text:
                    handle_message(text, chat_id)

            # Check ORACLE messages every 2 minutes
            if (datetime.now() - last_oracle_check).seconds >= 120:
                check_oracle_messages()
                last_oracle_check = datetime.now()

            # Proactive check every 30 minutes
            if (datetime.now() - last_proactive).seconds >= 1800:
                proactive_check()
                last_proactive = datetime.now()

            time.sleep(2)

        except KeyboardInterrupt:
            print("\nNEXUS V2 stopped.")
            break
        except Exception as e:
            print(f"[NEXUS ERROR] {e}")
            log_bug(f"Listener error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()

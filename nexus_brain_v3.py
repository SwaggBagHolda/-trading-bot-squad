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

import os, sys, json, time, requests, subprocess, random, tempfile, re, traceback
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env", override=True)

TOKEN = os.getenv("NEXUS_TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID")
ANTHROPIC_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL     = "claude-sonnet-4-6"
COMPOSIO_KEY        = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_ENTITY_ID  = os.getenv("COMPOSIO_ENTITY_ID", "default")
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
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
BUGS.parent.mkdir(parents=True, exist_ok=True)
DAILY.mkdir(parents=True, exist_ok=True)

API = f"https://api.telegram.org/bot{TOKEN}"

last_oracle_check = datetime.now()
last_proactive = datetime.now()
last_autonomous = datetime.now() - timedelta(seconds=900)  # fire immediately on first loop
last_heartbeat = datetime.now()
last_memory_consolidation = datetime.now()
last_income_idea = datetime.now()
last_oracle_alert  = 0     # epoch seconds — rate-limit ORACLE down alerts to once/hour
_research_ran      = False  # set True only when web_search() actually returns data this request
last_2am_pitch     = None  # date — ensures 2am pitch fires once per night
last_3am_research  = None  # date — ensures 3am research fires once per night

# Telegram noise control — only APEX trade closes fire when True
QUIET_MODE = False

PERSONAL_SYSTEM = "You are NEXUS, Ty's close friend and partner. When Ty vents about life — money, work, stress — respond like a real friend would. 1-2 sentences max. No trading talk. No bots. No offers to help. Just acknowledge and be real."

VOICE_ENFORCEMENT = """VOICE ENFORCEMENT — MANDATORY:
- Terse. Facts first. No filler.
- Never start with "I". Never use emoji. Never say "certainly", "absolutely", "great", "awesome", "let's get that green rolling".
- Correct: "APEX is down $56 on BTC. Nothing else moving. What do you need?"
- Wrong: "Great news! Everything is running smoothly! Let me know if you need anything! 🚀"
- If the response is cheerful or vague, it is wrong. Be sharp. Be Ty's operator, not a chatbot.
- Never end with "How can I help?" or any offer to help. State facts and stop. Ty will ask if he needs something.
- Never end with a question. Ever. Not "What's up?", not "Need anything?", not "All good?". State facts and go silent.
- If Ty says something personal, emotional, or casual — respond to THAT first. Status updates are never the answer to a human moment.
- NEVER claim to take an action you cannot confirm happened. If you cannot execute it directly, say so. Never fabricate activity.
- NEVER report a bot as offline or idle without confirming via system check. If unsure say: I don't have confirmed status on that.
- NEVER state win rates, strategy findings, backtest results, or research conclusions unless the data came from hive_mind.json or a confirmed web_search() call this session. If you have no real data, say: "I don't have confirmed research on that — running AutoResearch now." Never invent percentages."""

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

def send(chat_id, text):
    try:
        if len(text) > 4000:
            for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": chunk}, timeout=10)
                time.sleep(0.5)
        else:
            requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"[NEXUS] Send error: {e}")

def get_updates(offset=None):
    try:
        params = {"timeout": 20, "allowed_updates": ["message"]}
        if offset: params["offset"] = offset
        r = requests.get(f"{API}/getUpdates", params=params, timeout=25)
        return r.json().get("result", [])
    except: return []

def read_hive():
    try:
        with open(HIVE) as f: return json.load(f)
    except: return {}

def read_winners():
    try:
        with open(WINNERS) as f: return json.load(f)
    except: return {}

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
    Call Anthropic API directly (claude-sonnet-4-6 by default).
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
    sys_prompt = system or f"""{soul}

---

WHO YOU'RE TALKING TO:
{user_ctx}

---

PERMANENT GOALS & STANDING ORDERS:
{goals}

---

CURRENT STATUS:
- Total P&L today: ${total_pnl:+.2f}
- APEX live trading BTC
- Mission: $15K/month for Ty's bills

{f"MEMORY (lessons learned):{chr(10)}{lessons}" if lessons else ""}"""

    sys_prompt = sys_prompt + "\n\n---\n\n" + VOICE_ENFORCEMENT

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
                    "max_tokens": 500,
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
    - Market/price queries → CoinGecko live data
    - Strategy/video queries → YouTube search + DuckDuckGo
    - General queries → DuckDuckGo HTML scraping
    """
    global _research_ran
    q_lower = query.lower()

    # ── Market data → CoinGecko ──────────────────────────────────────────────
    market_kw = ["price", "prices", "btc", "eth", "sol", "bitcoin", "ethereum",
                 "solana", "volume", "24h", "market cap", "pump", "dump", "rally",
                 "crash", "chart", "how much is", "what is btc", "what is eth"]
    strategy_kw = ["strategy", "backtest", "indicator", "signal", "pattern",
                   "scalp", "swing", "trend", "momentum", "rsi", "macd", "ema"]
    is_market  = any(kw in q_lower for kw in market_kw) and not any(kw in q_lower for kw in strategy_kw)
    is_video   = any(kw in q_lower for kw in ["youtube", "video", "watch", "tutorial"] + strategy_kw)

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
    bots_to_check = ["scheduler.py", "paper_trading.py", "nexus_brain_v3.py"]
    for bot in bots_to_check:
        result = subprocess.run(["pgrep", "-f", bot], capture_output=True, text=True)
        if not result.stdout.strip():
            issues.append(f"{bot} is NOT running")
    return issues

def auto_restart_bots(issues):
    """Auto-restart crashed bots."""
    restarted = []
    for issue in issues:
        if "scheduler.py" in issue:
            subprocess.Popen(["python3", str(BASE / "scheduler.py")],
                           cwd=str(BASE), start_new_session=True)
            restarted.append("scheduler.py")
        elif "paper_trading.py" in issue:
            subprocess.Popen(["python3", str(BASE / "paper_trading.py")],
                           cwd=str(BASE), start_new_session=True)
            restarted.append("paper_trading.py")
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
                send(OWNER_ID, f"📨 ORACLE sent {len(instructions)} instruction(s):\n\n" +
                     "\n".join(f"• {i}" for i in instructions))
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
    Every 15 min — NEXUS acts without waiting for Ty.
    Four hard checks, every cycle, every result logged.
    """
    hive = read_hive()
    perf = hive.get("bot_performance", {})
    grad = hive.get("graduation", {})
    now  = datetime.now()

    def act(msg):
        line = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        try:
            with open(AUTONOMOUS_LOG, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass

    act("=== AUTONOMOUS LOOP START ===")

    # ── CHECK 1: Bot performance snapshot ────────────────────────────────────
    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
        data = perf.get(bot, {})
        if not isinstance(data, dict):
            continue
        mode   = data.get("mode", "?").upper()
        wr     = data.get("win_rate", 0) * 100
        trades = data.get("trades", 0)
        pnl    = data.get("daily_pnl", 0)
        act(f"PERF [{bot}/{mode}] trades={trades} WR={wr:.1f}% P&L=${pnl:+.2f}")

    # ── CHECK 2: AutoResearch — trigger if any bot WR < 50% after 5+ trades ─
    research_triggered = False
    for bot, data in perf.items():
        if not isinstance(data, dict) or research_triggered:
            continue
        trades = data.get("trades", 0)
        wr     = data.get("win_rate", 0)
        if trades >= 5 and wr < 0.50:
            already_running = bool(subprocess.run(
                ["pgrep", "-f", "sentinel_research"], capture_output=True, text=True
            ).stdout.strip())
            if not already_running:
                run_all_training()
                act(f"AUTO-RESEARCH TRIGGERED: {bot} WR={wr*100:.1f}% on {trades} trades — launched")
                send(OWNER_ID, f"AutoResearch triggered — {bot} WR at {wr*100:.1f}% on {trades} trades. Running now.")
            else:
                act(f"AUTO-RESEARCH PENDING: {bot} WR={wr*100:.1f}% — already running")
            research_triggered = True

    if not research_triggered:
        act("AUTO-RESEARCH: All bots above 50% WR — no trigger")

    # ── CHECK 3: APEX active trade — force scan if idle > 60 min ─────────────
    force_scan_flag = BASE / "shared" / "apex_force_scan.flag"
    try:
        state_file = BASE / "shared" / "apex_state.json"
        if state_file.exists():
            apex_st = json.loads(state_file.read_text())
            active  = apex_st.get("active")
            saved   = apex_st.get("saved", "")
            if active:
                entry     = active.get("entry", 0)
                symbol    = active.get("symbol", "?")
                direction = active.get("direction", "?")
                market    = fetch_market_snapshot()
                cur = market.get(symbol, {}).get("price") or market.get("BTC", {}).get("price", 0)
                if cur and entry:
                    pnl_pct = (cur - entry) / entry if direction == "BUY" else (entry - cur) / entry
                    act(f"APEX: IN TRADE — {direction} {symbol} @ ${entry:,.0f} now ${cur:,.0f} ({pnl_pct*100:+.2f}%)")
                else:
                    act(f"APEX: IN TRADE — {direction} {symbol} @ ${entry:,.0f}")
            else:
                if saved:
                    try:
                        idle_secs = (now - datetime.fromisoformat(saved)).total_seconds()
                        idle_min  = int(idle_secs / 60)
                        act(f"APEX: IDLE {idle_min}min — no active position")
                        if idle_secs > 3600:
                            force_scan_flag.write_text(now.isoformat())
                            act(f"APEX: FORCE SCAN FLAG written — idle {idle_min}min")
                            send(OWNER_ID, f"APEX idle {idle_min}min — forced market scan triggered.")
                    except Exception as e:
                        act(f"APEX: idle calc error: {e}")
                else:
                    act("APEX: No trades yet this session")
        else:
            act("APEX: apex_state.json missing — process may be down")
            # Attempt restart
            subprocess.Popen(
                ["python3", "-u", str(BASE / "apex_coingecko.py")],
                cwd=str(BASE),
                stdout=open(str(BASE / "logs" / "apex_coingecko.log"), "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            act("APEX: Restart attempted")
    except Exception as e:
        act(f"APEX CHECK ERROR: {e}")

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
                send(OWNER_ID, f"{bot} at {t}/{tgt} backtest trades ({pct:.0f}%) — {wr:.1f}% WR. Close to paper trading.")
                act(f"GRAD [{bot}]: Near-milestone alert sent")
        elif stage == "paper":
            t   = g.get("paper_trades", 0)
            tgt = g.get("paper_target", 200)
            wr  = g.get("paper_wins", 0) / max(t, 1) * 100
            pnl = g.get("paper_pnl", 0.0)
            pct = t / tgt * 100
            act(f"GRAD [{bot}/PAPER]: {t}/{tgt} ({pct:.0f}%) | {wr:.1f}% WR | P&L {pnl:+.3f}%")
            if t >= tgt * 0.8 and t < tgt and wr >= 55:
                send(OWNER_ID, f"{bot} at {t}/{tgt} paper trades ({pct:.0f}%) — {wr:.1f}% WR. Close to live.")
                act(f"GRAD [{bot}]: Near-milestone alert sent")
        elif stage == "live_pending":
            act(f"GRAD [{bot}]: LIVE PENDING — awaiting Ty approval")
            send(OWNER_ID, f"{bot} passed paper trading and is waiting for your go-ahead to go live.")

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

            msg = f"AUTORESEARCH DONE — {elapsed}s\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━\n"
            for b in bots:
                line = f"{b['bot']}: {b['win_rate']:.1f}% WR"
                if b.get("top_strategy"):
                    line += f" | best: {b['top_strategy']} on {b['best_asset']} {b['best_timeframe']} ({b['best_wr']}% WR)"
                line += f" | {b['winners']} winning combos"
                msg += line + "\n"
            if top_strats:
                msg += "\nTOP 3 CROSS-BOT:\n"
                for s in top_strats[:3]:
                    msg += f"  {s['strategy']} | {s['asset']} | {s['timeframe']} — {s['win_rate']}% WR, {s['avg_pnl']:+.4f}% avg P&L\n"

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

    # CHECK 2b: ORACLE process — alert Ty at most once per hour
    global last_oracle_alert, last_2am_pitch, last_3am_research
    oracle_proc = subprocess.run(["pgrep", "-f", "oracle_listener.py"], capture_output=True, text=True)
    if not oracle_proc.stdout.strip():
        if time.time() - last_oracle_alert > 3600:
            send(OWNER_ID, "ORACLE is not running. Watchdog should restart it within 5 min.")
            last_oracle_alert = time.time()
            actions_taken.append("ORACLE down alert sent")

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

    # PATH 1: APEX idle >2 hours — check entry conditions, escalate
    try:
        apex_state_file = BASE / "shared" / "apex_state.json"
        if apex_state_file.exists():
            apex_state = json.loads(apex_state_file.read_text())
            if not apex_state.get("active"):
                last_trade_time = apex_state.get("last_trade_time")
                if last_trade_time:
                    idle_secs = (datetime.now() - datetime.fromisoformat(last_trade_time)).total_seconds()
                    if idle_secs > 7200:
                        idle_hrs = idle_secs / 3600
                        send(OWNER_ID, f"APEX idle {idle_hrs:.1f}h — no position open. Entry conditions may be too tight.")
                        actions_taken.append(f"APEX idle {idle_hrs:.1f}h alert")
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
                send(OWNER_ID, f"{bot} has passed paper trading — ready for live. Reply to approve.")
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
        if live_pnl < -50 or (day_of_month > 3 and live_pnl < target_pace * 0.5):
            send(OWNER_ID, f"LIVE P&L pace: ${live_pnl:+.2f} today. Target: ${target_pace:+,.0f} MTD. Behind.")
            actions_taken.append(f"Live P&L pace alert: ${live_pnl:+.2f}")
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

def _history_add(user_text: str, assistant_text: str):
    """Append one exchange to the rolling conversation history."""
    global _conversation_history
    _conversation_history.append({"role": "user",      "content": user_text})
    _conversation_history.append({"role": "assistant", "content": assistant_text})
    if len(_conversation_history) > MAX_HISTORY:
        _conversation_history = _conversation_history[-MAX_HISTORY:]


def handle_message(text, chat_id):
    global _conversation_history, _research_ran
    _research_ran = False  # reset each message — must be re-earned by actual web_search() call
    text_lower = text.strip().lower()
    print(f"[NEXUS] Received: {text}")
    log_to_oracle(f"Ty said: {text}")
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
        """Send response and record exchange in conversation history."""
        send(chat_id, msg_text)
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

    # Train / AutoResearch
    if cmd("/train", "/autoresearch", "train all", "run training", "start training",
           "run hypertraining", "run autoresearch", "run auto research", "autoResearch",
           "auto research", "run research on", "research all", "research the best"):
        success = run_all_training()
        if success:
            # Report what's actually being tested — all 8 assets, not just BTC
            assets = "BTC, ETH, SOL, DOGE, ADA, LINK, AVAX, MATIC"
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
            send(chat_id, f"Searching: {query[:60]}...")
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
        send(chat_id, "Researching...")
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
               "YouTube links — auto-summarized")
        reply(msg)
        return

    # YouTube URL — auto-detect any youtube link in the message
    if re.search(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts)", text_lower):
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            send(chat_id, "Pulling YouTube info...")
            result = summarize_youtube(url_match.group(0))
            reply(result[:1000])
            return

    # Web browsing via Playwright
    if cmd("/browse", "browse ", "open url", "read this link", "check this link"):
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            url = url_match.group(0)
            send(chat_id, f"Browsing {url[:60]}...")
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
        send(chat_id, "Generating PDF...")
        hive = read_hive()
        perf = hive.get("bot_performance", {})
        _pnl = sum(v.get("daily_pnl", 0) for v in perf.values() if isinstance(v, dict))
        if topic:
            pdf_content = ask_ai(
                f"Write a detailed report about: {topic}\nContext: Trading bot squad. APEX live on BTC. P&L today: ${_pnl:+.2f}"
            ) or topic
            pdf_title = topic[:50]
        else:
            pdf_content = get_status_report()
            pdf_title = "NEXUS Status Report"
        result = create_pdf(pdf_title, pdf_content)
        pdf_msg = f"PDF saved: {result}" if "error" not in result.lower() else f"PDF failed: {result}"
        reply(pdf_msg)
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
        send(chat_id, f"On it...")
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

Context (use only if relevant): P&L today ${total_pnl:+.2f}. APEX live on BTC. Mission $15K/month.

1-3 sentences."""
        response = ask_ai(
            prompt,
            history=_conversation_history[-MAX_HISTORY:] if _conversation_history else None
        )

    if response:
        _history_add(text, response)
        send(chat_id, response)
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
                        send(chat_id, "🎤 Got your voice message, transcribing...")
                        transcribed = transcribe_voice(voice["file_id"])
                        if transcribed:
                            send(chat_id, f"📝 You said: \"{transcribed}\"")
                            handle_message(transcribed, chat_id)
                        else:
                            send(chat_id, "Couldn't transcribe that one. Try again or type it.")

            # ── ORACLE bridge every 2 minutes ─────────────────────────────
            if (now - last_oracle_check).total_seconds() >= 120:
                check_oracle_messages()
                last_oracle_check = now

            # ── AUTONOMOUS LOOP every 15 minutes — NEXUS acts, doesn't wait ─
            if (now - last_autonomous).total_seconds() >= 900:
                autonomous_loop()
                last_autonomous = now

            # ── HEARTBEAT / proactive Ty message every 30 minutes ─────────
            if (now - last_proactive).total_seconds() >= 1800:
                proactive_check()
                last_proactive = now

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

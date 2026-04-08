"""
NIGHTLY CONSOLIDATION — runs at 2am via cron as backup to NEXUS's in-process loop.
Extracts lessons from today's daily log → updates MEMORY.md → updates HEARTBEAT.md.
Standalone so it works even if nexus_brain_v3.py is down.
"""
import os, json, requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE = Path.home() / "trading-bot-squad"
load_dotenv(BASE / ".env", override=True)

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
FREE_MODEL  = "openai/gpt-oss-120b:free"
FREE_MODEL2 = "nvidia/nemotron-3-super-120b-a12b:free"
DAILY = BASE / "memory" / "daily"
MEMORY_MD = BASE / "memory" / "MEMORY.md"
HEARTBEAT = BASE / "memory" / "HEARTBEAT.md"
LESSONS = BASE / "memory" / "lessons" / "nexus_lessons.md"
LOGS = BASE / "logs"
LESSONS.parent.mkdir(parents=True, exist_ok=True)


def ask_ai(prompt: str) -> str:
    if not OPENROUTER_KEY:
        return ""
    for model in [FREE_MODEL, FREE_MODEL2]:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800},
                timeout=30
            )
            data = r.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            print(f"[CONSOLIDATE] {model} failed: {str(data)[:80]}")
        except Exception as e:
            print(f"[CONSOLIDATE] AI error ({model}): {e}")
    return ""


def run():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    log_file = DAILY / f"{today}.md"
    if not log_file.exists():
        log_file = DAILY / f"{yesterday}.md"
    if not log_file.exists():
        print(f"[CONSOLIDATE] No daily log found for {today} or {yesterday}")
        return

    daily_content = log_file.read_text()
    print(f"[CONSOLIDATE] Processing {log_file.name} ({len(daily_content)} chars)")

    # Extract lessons via AI
    lessons_prompt = f"""Read this daily trading bot log and extract 3-5 concrete lessons learned.
Format each lesson as: "LESSON: [what happened] → [what to do differently / what worked]"
Keep each lesson under 2 sentences. Focus on technical facts, not vague observations.

DAILY LOG:
{daily_content[:3000]}"""

    lessons = ask_ai(lessons_prompt)

    if lessons:
        ts = now.strftime("%Y-%m-%d %H:%M")
        with open(LESSONS, "a") as f:
            f.write(f"\n## {ts} Nightly Extraction\n{lessons}\n")
        print(f"[CONSOLIDATE] Lessons saved ({len(lessons)} chars)")
    else:
        print("[CONSOLIDATE] AI unavailable — skipping lesson extraction")

    # Update MEMORY.md summary
    memory_prompt = f"""Based on this daily log, write a 3-sentence summary of the most important things
that happened today with the trading bot squad. Focus on: what was built, what broke, what improved.
Keep it factual and under 100 words.

DAILY LOG:
{daily_content[:2000]}"""

    summary = ask_ai(memory_prompt)
    if not MEMORY_MD.exists():
        MEMORY_MD.write_text("# MEMORY.md — Nightly Lesson Summaries\n\n")
    if summary:
        existing = MEMORY_MD.read_text()
        # Insert after the first H1 heading
        if "\n## " in existing:
            insert_point = existing.index("\n## ")
            updated = existing[:insert_point] + f"\n\n## {today}\n{summary}" + existing[insert_point:]
        else:
            updated = existing + f"\n\n## {today}\n{summary}"
        MEMORY_MD.write_text(updated)
        print(f"[CONSOLIDATE] MEMORY.md updated")

    # Append to log
    with open(LOGS / "consolidate.log", "a") as f:
        f.write(f"[{now.strftime('%Y-%m-%d %H:%M')}] Consolidation complete. Log: {log_file.name}, Lessons extracted: {bool(lessons)}\n")

    print(f"[CONSOLIDATE] Done — {today}")


if __name__ == "__main__":
    run()

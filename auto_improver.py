#!/usr/bin/env python3
"""
auto_improver.py — Autonomous task executor for Trading Bot Squad
Watches memory/tasks/pending.md every 5 minutes for [AUTO_IMPROVE] tagged lines.
Executes each via: claude --dangerously-skip-permissions -p "task"
Saves result to memory/tasks/completed.md, marks [DONE] in pending.md.

Usage:
  python3 auto_improver.py            — start watch loop (every 5 min)
  python3 auto_improver.py --run-now  — check and run once, then exit
"""

import os
import subprocess
import sys
import time
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE        = Path(__file__).parent
PENDING_MD  = BASE / "memory" / "tasks" / "pending.md"
COMPLETED_MD = BASE / "memory" / "tasks" / "completed.md"

load_dotenv(BASE / ".env", override=True)

CHECK_INTERVAL = 5 * 60  # 5 minutes
MAX_RETRIES    = 3        # max attempts per task before permanently marking failed


def read_pending():
    if not PENDING_MD.exists():
        PENDING_MD.parent.mkdir(parents=True, exist_ok=True)
        PENDING_MD.write_text("# Pending Tasks\n\n")
    return PENDING_MD.read_text()


def get_auto_improve_tasks(content):
    """Return list of (line_index, task_text) for all [AUTO_IMPROVE] lines not yet [DONE]."""
    tasks = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "[AUTO_IMPROVE]" in line and "[DONE]" not in line:
            task = re.sub(r"\[AUTO_IMPROVE\]", "", line).strip()
            task = re.sub(r"^[-*\s]+", "", task).strip()
            if task:
                tasks.append((i, task))
    return tasks


def run_claude(task):
    """Execute task via claude CLI. Returns (success, output)."""
    print(f"[AUTO_IMPROVER] Running: {task[:80]}...")
    # Exclude ANTHROPIC_API_KEY from subprocess env — let claude CLI use its own
    # stored OAuth credentials (~/.claude/). The .env key is for OpenRouter/bots,
    # not for Claude Code CLI auth. Passing it overrides stored auth → "Invalid API key".
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", task],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=BASE,
            env=env
        )
        output = result.stdout.strip() or result.stderr.strip()
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Task timed out after 5 minutes."
    except FileNotFoundError:
        return False, "claude CLI not found. Is it installed and in PATH?"
    except Exception as e:
        return False, f"Error: {e}"


def save_completed(task, success, output):
    """Append result to completed.md."""
    if not COMPLETED_MD.exists():
        COMPLETED_MD.write_text("# Completed Tasks\n\n")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "SUCCESS" if success else "FAILED"
    entry = f"""---
## {timestamp} | {status}
**Task:** {task}

**Output:**
{output[:2000]}

"""
    with open(COMPLETED_MD, "a") as f:
        f.write(entry)


def mark_done(line_index, task):
    """Replace [AUTO_IMPROVE] with [DONE] on the given line."""
    lines = read_pending().splitlines(keepends=True)
    if line_index < len(lines):
        lines[line_index] = lines[line_index].replace("[AUTO_IMPROVE]", "[DONE]", 1)
        PENDING_MD.write_text("".join(lines))


def write_fixed_marker(task):
    """Write [AUTO_IMPROVER FIXED] marker to the source log so /selfcheck skips the error next time."""
    # Task format: "In {src}: {line} — diagnose root cause and fix"
    if not task.startswith("In "):
        return
    try:
        src = task[3:task.index(":")]  # text between "In " and first ":"
        log_path = BASE / "logs" / src
        if log_path.exists():
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(log_path, "a") as f:
                f.write(f"[AUTO_IMPROVER FIXED] {ts} — above error resolved\n")
    except Exception:
        pass


def check_and_run():
    content = read_pending()
    tasks = get_auto_improve_tasks(content)

    if not tasks:
        return

    print(f"[AUTO_IMPROVER] Found {len(tasks)} pending task(s) at {datetime.now().strftime('%H:%M')}")

    for line_index, task in tasks:
        success = False
        output  = ""
        for attempt in range(1, MAX_RETRIES + 1):
            success, output = run_claude(task)
            if success:
                break
            print(f"[AUTO_IMPROVER] Attempt {attempt}/{MAX_RETRIES} failed: {task[:50]}...")
            if attempt < MAX_RETRIES:
                time.sleep(10)  # brief pause between retries

        save_completed(task, success, output)
        mark_done(line_index, task)  # always mark done after max retries — no infinite loops
        if success:
            write_fixed_marker(task)
        status = "done" if success else f"FAILED after {MAX_RETRIES} retries"
        print(f"[AUTO_IMPROVER] [{status.upper()}] {task[:60]}")
        time.sleep(2)


def main():
    run_once = "--run-now" in sys.argv

    PENDING_MD.parent.mkdir(parents=True, exist_ok=True)
    if not PENDING_MD.exists():
        PENDING_MD.write_text("# Pending Tasks\n\n")
    if not COMPLETED_MD.exists():
        COMPLETED_MD.write_text("# Completed Tasks\n\n")

    if run_once:
        print(f"[AUTO_IMPROVER] --run-now mode. Checking once.")
        check_and_run()
        return

    print(f"[AUTO_IMPROVER] Started. Watching {PENDING_MD} every {CHECK_INTERVAL // 60} min.")
    while True:
        try:
            check_and_run()
        except Exception as e:
            print(f"[AUTO_IMPROVER] Error in check loop: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""set_key_silent.py — prompt for key via macOS dialog, write to .env, never print key."""
import subprocess, sys
from pathlib import Path

ENV = Path.home() / "trading-bot-squad" / ".env"

def prompt_key(key_name):
    script = f'display dialog "Enter {key_name}:" default answer "" with hidden answer buttons {{"Cancel","Save"}} default button "Save"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print("Cancelled.")
        sys.exit(0)
    # extract text after "text returned:"
    for part in r.stdout.strip().split(","):
        if "text returned:" in part:
            return part.split("text returned:")[1].strip()
    return ""

key_name = sys.argv[1] if len(sys.argv) > 1 else "ANTHROPIC_API_KEY"
value = prompt_key(key_name)

if not value:
    print("No value entered. Exiting.")
    sys.exit(1)

existing = ENV.read_text() if ENV.exists() else ""
lines = [l for l in existing.splitlines() if not l.startswith(f"{key_name}=")]
lines.append(f"{key_name}={value}")
ENV.write_text("\n".join(lines) + "\n")

# Confirm without revealing the key
print(f"Saved. Length: {len(value)} | Starts correctly: {value.startswith('sk-ant-')}")

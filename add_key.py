#!/usr/bin/env python3
"""add_key.py — Safely add a key to .env without exposing it in chat."""
import getpass
from pathlib import Path

ENV = Path.home() / "trading-bot-squad" / ".env"

key_name = input("Key name (e.g. COMPOSIO_API_KEY): ").strip()
if not key_name:
    print("No key name provided. Exiting.")
    exit(1)

key_value = getpass.getpass(f"Value for {key_name} (hidden): ").strip()
if not key_value:
    print("No value provided. Exiting.")
    exit(1)

# Read existing .env
existing = ENV.read_text() if ENV.exists() else ""

# Remove any existing line for this key
lines = [l for l in existing.splitlines() if not l.startswith(f"{key_name}=")]
lines.append(f"{key_name}={key_value}")

ENV.write_text("\n".join(lines) + "\n")
print(f"Done. {key_name} written to .env (first 8 chars: {key_value[:8]}...)")

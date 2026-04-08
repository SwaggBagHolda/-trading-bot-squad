#!/bin/bash
# NEXUS Model Fix — Switch to Claude Haiku
# Haiku = cheapest paid model, ~$0.10/day, zero compatibility issues
# WARDEN and bots use free OpenRouter. NEXUS gets Haiku.
# Run this once to fix the model permanently.

echo "Fixing NEXUS model to Claude Haiku..."

sed -i '' 's|"primary": ".*"|"primary": "claude-haiku-4-5-20251001"|' ~/.openclaw/openclaw.json

echo "Model set to claude-haiku-4-5-20251001"
echo "Restarting OpenClaw gateway..."

pkill -f "openclaw gateway" 2>/dev/null
sleep 2
~/.local/bin/openclaw gateway --force &

echo "Done. Send /start to HeadNexusBot on Telegram."
echo "Cost estimate: ~$0.10/day for NEXUS conversations."
echo "All bots and WARDEN still use free OpenRouter models."

#!/bin/bash
# Auto-commit and push to GitHub every hour
# Reads GITHUB_TOKEN from .env — never hardcoded

BASE="$HOME/trading-bot-squad"
LOG="$BASE/logs/autopush.log"
ENV_FILE="$BASE/.env"

cd "$BASE" || exit 1

# Load GITHUB_TOKEN from .env
GITHUB_TOKEN=$(grep '^GITHUB_TOKEN=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '\r\n')
if [ -z "$GITHUB_TOKEN" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: GITHUB_TOKEN not found in .env" >> "$LOG"
    exit 1
fi

# Set authenticated remote URL (stripped after push)
git remote set-url origin "https://SwaggBagHolda:${GITHUB_TOKEN}@github.com/SwaggBagHolda/-trading-bot-squad.git"

# Stage everything (respects .gitignore — no secrets committed)
git add -A

# Only commit if there's something new
if git diff --cached --quiet; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No changes — skipping push" >> "$LOG"
else
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    git commit -m "auto: hourly snapshot $TIMESTAMP"
    git push origin main >> "$LOG" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pushed" >> "$LOG"
fi

# Strip token from remote URL
git remote set-url origin "https://github.com/SwaggBagHolda/-trading-bot-squad.git"

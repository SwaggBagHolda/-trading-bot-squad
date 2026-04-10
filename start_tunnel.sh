#!/bin/bash
# Start cloudflared tunnel and save the public URL
# Called by scheduler.py on boot or manually

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$SCRIPT_DIR/bin/cloudflared"
LOG="$SCRIPT_DIR/logs/cloudflared.log"
URL_FILE="$SCRIPT_DIR/shared/tunnel_url.txt"

# Kill any existing tunnel
pkill -f cloudflared 2>/dev/null
sleep 1

# Start tunnel
nohup "$BIN" tunnel --url http://localhost:7777 > "$LOG" 2>&1 &
echo "Tunnel PID: $!"

# Wait for URL to appear in logs
for i in {1..10}; do
    sleep 2
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
    if [ -n "$URL" ]; then
        echo "$URL" > "$URL_FILE"
        echo "Tunnel URL: $URL"
        echo "Saved to: $URL_FILE"
        exit 0
    fi
done

echo "ERROR: Tunnel URL not found after 20s. Check $LOG"
exit 1

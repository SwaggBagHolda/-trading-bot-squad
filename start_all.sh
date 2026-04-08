#!/bin/bash
# start_all.sh — Trading Bot Squad
# Starts all 5 processes in order, logs each to logs/

set -e
cd "$(dirname "$0")"

LOGS="logs"
mkdir -p "$LOGS"

echo "========================================"
echo "  TRADING BOT SQUAD — STARTING UP"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

start_proc() {
    local name="$1"
    local script="$2"
    local logfile="$LOGS/$3"
    local flags="${4:-}"

    if pgrep -f "$script" > /dev/null 2>&1; then
        echo "  [$name] already running — skipping"
    else
        nohup python3 $flags "$script" >> "$logfile" 2>&1 &
        sleep 1
        if pgrep -f "$script" > /dev/null 2>&1; then
            echo "  [$name] started ✅  (log: $logfile)"
        else
            echo "  [$name] FAILED TO START ❌  (check $logfile)"
        fi
    fi
}

# Start in dependency order
start_proc "SCHEDULER"      "scheduler.py"        "scheduler.log"
start_proc "PAPER TRADING"  "paper_trading.py"    "paper_trading.log"
start_proc "APEX LIVE"      "apex_coingecko.py"   "apex_coingecko.log"
start_proc "NEXUS"          "nexus_brain_v3.py"   "nexus_v3.log"
start_proc "ORACLE"         "oracle_listener.py"  "oracle_listener.log"
start_proc "AUTO IMPROVER" "auto_improver.py"    "auto_improver.log" "-u"

echo ""
echo "========================================"
echo "  FINAL STATUS"
echo "========================================"
for script in scheduler.py paper_trading.py apex_coingecko.py nexus_brain_v3.py oracle_listener.py auto_improver.py; do
    if pgrep -f "$script" > /dev/null 2>&1; then
        echo "  $script — RUNNING ✅"
    else
        echo "  $script — STOPPED ❌"
    fi
done
echo "========================================"
echo "  Done. Tail logs with:"
echo "  tail -f logs/nexus_v3.log"
echo "  tail -f logs/oracle_listener.log"
echo "========================================"

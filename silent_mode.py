"""
SILENT_MODE — Global Telegram noise filter for ALL bot processes.
Import this in any file that has send_telegram() to enforce silence.

Ty's FINAL rules (2026-04-09) — ONLY these messages reach Telegram:
  1. Money made or lost (trades with real P&L)
  2. Something broke and needs attention
  3. System upgrade completed
  4. HyperTrain final results after 10K rounds — plain English, dollars and cents
  5. Direct replies when Ty asks something

EVERYTHING else is permanently silenced. No CEO loop reports, no threshold
changes, no restarts, no checkpoints, no startup messages, no research updates.
"""

# Master switch — set to False to disable all filtering
SILENT_MODE = True

# Messages must match at least one pattern to get through
ALLOWED_PATTERNS = [
    # 1. Money made or lost
    "P&L",
    "profit",
    "loss",
    "closed",
    "filled",
    "+$",
    "-$",
    "won",
    "lost",
    # 2. Something broke
    "EMERGENCY",
    "ERROR",
    "CRASH",
    "down",
    "broke",
    "failed",
    "⚠️",
    "🚨",
    # 3. System upgrade completed
    "upgrade complete",
    "migration complete",
    "deployed",
    # 4. HyperTrain final results (10K rounds)
    "HYPERTRAIN COMPLETE",
    "10,000 experiments",
    "Top Strategies Found",
]


def should_send(message, force=False, urgent=False):
    """Return True if this message should be sent to Telegram.
    force=True: direct reply to Ty — always sends.
    urgent=True: something broke — always sends.
    Otherwise: only sends if message matches allowed patterns."""
    if not SILENT_MODE:
        return True
    if force or urgent:
        return True
    msg_lower = (message or "").lower()
    for pattern in ALLOWED_PATTERNS:
        if pattern.lower() in msg_lower:
            return True
    return False

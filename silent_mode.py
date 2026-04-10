"""
SILENT_MODE — Global Telegram noise filter for ALL bot processes.
Import this in any file that has send_telegram() to enforce silence.

Ty's FINAL rules (2026-04-09) — ONLY these messages reach Telegram:
  1. Money made or lost (trades with real P&L)
  2. Something broke and needs Ty's attention
  3. System upgrade completed
  4. HyperTrain final results after 10K rounds — plain English, dollars and cents
  5. Direct replies when Ty asks something (force=True)

EVERYTHING else is permanently silenced. No CEO loop reports, no threshold
changes, no restarts, no checkpoints, no startup messages, no research updates,
no position updates, no "ORACLE was down", no "auto-restarted".
"""

import re

# Master switch — set to False to disable all filtering
SILENT_MODE = True

# Exact substring patterns that allow a message through
_ALLOW_EXACT = [
    # 1. Money made or lost (real P&L only)
    "P&L",
    "profit",
    "closed for",       # "closed for +$12.50"
    "filled",
    "+$",
    "-$",
    # 2. Something genuinely broke (not routine restarts)
    "CRASH",
    # 3. System upgrade completed
    "upgrade complete",
    "migration complete",
    # 4. HyperTrain final results
    "HYPERTRAIN COMPLETE",
    "10,000 experiments",
    "Top Strategies Found",
]

# Regex patterns for more precise matching
_ALLOW_REGEX = [
    r"\$[\d,]+\.?\d*\s*(profit|loss|won|lost|made|down)",  # "$45.20 profit"
    r"(won|lost|made|earned)\s*\$",                         # "won $12"
]

# Patterns that should NEVER send even if they match above
_BLOCK_ALWAYS = [
    "auto-restarted",
    "was down",
    "restarted it",
    "trailing stop",
    "watch stop",
    "loosened",
    "threshold",
    "cooldown",
    "CEO loop",
    "queued",
    "strategy switch",
    "went PRO",
    "benched",
    "retired",
    "checkpoint",
]


def should_send(message, force=False, urgent=False):
    """Return True if this message should be sent to Telegram.
    force=True: direct reply to Ty — always sends.
    urgent=True: something broke — always sends.
    Otherwise: only if message matches Ty's strict whitelist."""
    if not SILENT_MODE:
        return True
    if force:
        return True
    if not message:
        return False

    msg_lower = message.lower()

    # Block list takes priority — these NEVER send
    for block in _BLOCK_ALWAYS:
        if block.lower() in msg_lower:
            return False

    # Check exact substring matches
    for pattern in _ALLOW_EXACT:
        if pattern.lower() in msg_lower:
            return True

    # Check regex matches
    for rx in _ALLOW_REGEX:
        if re.search(rx, message, re.IGNORECASE):
            return True

    # urgent flag allows through (real errors from code)
    if urgent:
        return True

    return False

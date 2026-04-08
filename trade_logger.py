"""
trade_logger.py — Trading Bot Squad
Logs all paper trades to SQLite + trades.log.
Single source of truth for all bot trade history.
"""

import sqlite3
import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "logs" / "trades.db"
LOG_PATH = BASE_DIR / "logs" / "trades.log"
DB_PATH.parent.mkdir(exist_ok=True)

# ── File logger ────────────────────────────────────────────────────────────────

file_handler = logging.FileHandler(LOG_PATH)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s [LOGGER] %(message)s"))

trade_log = logging.getLogger("trade_logger")
trade_log.setLevel(logging.INFO)
trade_log.addHandler(file_handler)
trade_log.addHandler(stream_handler)


# ── Database setup ─────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot             TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,          -- 'long' | 'short'
    entry_price     REAL NOT NULL,
    exit_price      REAL,
    quantity        REAL NOT NULL,          -- units of base asset
    stop_loss       REAL NOT NULL,
    take_profit     REAL,                   -- NULL = trailing stop only
    trailing_stop   REAL,                   -- current trailing stop price
    status          TEXT DEFAULT 'open',    -- 'open' | 'closed' | 'stopped'
    pnl_usd         REAL,                   -- realised P&L in USD
    pnl_pct         REAL,                   -- percentage
    reason_open     TEXT,                   -- signal reason from scanner
    reason_close    TEXT,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    timeframe       TEXT,
    extra           TEXT                    -- JSON blob for any extra data
);

CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot             TEXT NOT NULL,
    date            TEXT NOT NULL,          -- YYYY-MM-DD
    trades          INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    gross_pnl       REAL DEFAULT 0,
    net_pnl         REAL DEFAULT 0,
    win_rate        REAL DEFAULT 0,
    starting_balance REAL,
    ending_balance   REAL,
    UNIQUE(bot, date)
);

CREATE TABLE IF NOT EXISTS bot_accounts (
    bot             TEXT PRIMARY KEY,
    balance         REAL NOT NULL,          -- paper USD balance
    starting_balance REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and seed paper accounts if they don't exist."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        # Seed paper accounts at $10,000 each if not already set
        for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
            conn.execute("""
                INSERT OR IGNORE INTO bot_accounts (bot, balance, starting_balance, updated_at)
                VALUES (?, 10000.0, 10000.0, ?)
            """, (bot, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    trade_log.info("Database initialised at %s", DB_PATH)


# ── Trade CRUD ─────────────────────────────────────────────────────────────────

def log_trade_open(
    bot: str,
    symbol: str,
    direction: str,
    entry_price: float,
    quantity: float,
    stop_loss: float,
    take_profit: float | None = None,
    trailing_stop: float | None = None,
    reason: str = "",
    timeframe: str = "",
    extra: dict | None = None,
) -> int:
    """Insert an open trade. Returns the new trade ID."""
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO trades
                (bot, symbol, direction, entry_price, quantity,
                 stop_loss, take_profit, trailing_stop,
                 status, reason_open, opened_at, timeframe, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
        """, (
            bot, symbol, direction, entry_price, quantity,
            stop_loss, take_profit, trailing_stop,
            reason, now, timeframe,
            json.dumps(extra) if extra else None,
        ))
        trade_id = cur.lastrowid
        # Deduct position cost from paper balance
        cost = entry_price * quantity
        conn.execute("""
            UPDATE bot_accounts SET balance = balance - ?, updated_at = ? WHERE bot = ?
        """, (cost, now, bot))
        conn.commit()

    trade_log.info(
        "OPEN  | id=%d bot=%-8s %s %s @ %.4f qty=%.6f sl=%.4f tp=%s | %s",
        trade_id, bot, direction.upper(), symbol, entry_price, quantity,
        stop_loss, f"{take_profit:.4f}" if take_profit else "trailing", reason
    )
    return trade_id


def log_trade_close(
    trade_id: int,
    exit_price: float,
    reason_close: str = "",
) -> dict:
    """
    Close a trade. Calculates P&L, updates balance, returns summary dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not row:
            raise ValueError(f"Trade {trade_id} not found")
        if row["status"] != "open":
            raise ValueError(f"Trade {trade_id} is already {row['status']}")

        entry  = row["entry_price"]
        qty    = row["quantity"]
        cost   = entry * qty
        proceeds = exit_price * qty

        if row["direction"] == "long":
            pnl_usd = proceeds - cost
        else:
            pnl_usd = cost - proceeds

        pnl_pct = (pnl_usd / cost) * 100
        status  = "closed" if pnl_usd >= 0 else "stopped"

        conn.execute("""
            UPDATE trades
            SET exit_price=?, status=?, pnl_usd=?, pnl_pct=?, reason_close=?, closed_at=?
            WHERE id=?
        """, (exit_price, status, round(pnl_usd, 6), round(pnl_pct, 4), reason_close, now, trade_id))

        # Return proceeds to paper balance
        conn.execute("""
            UPDATE bot_accounts SET balance = balance + ?, updated_at = ? WHERE bot = ?
        """, (proceeds + max(pnl_usd, 0), now, row["bot"]))

        conn.commit()

    summary = {
        "trade_id":  trade_id,
        "bot":       row["bot"],
        "symbol":    row["symbol"],
        "direction": row["direction"],
        "entry":     entry,
        "exit":      exit_price,
        "pnl_usd":   round(pnl_usd, 4),
        "pnl_pct":   round(pnl_pct, 4),
        "status":    status,
    }

    emoji = "✓" if pnl_usd >= 0 else "✗"
    trade_log.info(
        "CLOSE %s | id=%d bot=%-8s %s @ %.4f → %.4f | P&L $%.2f (%.2f%%) | %s",
        emoji, trade_id, row["bot"], row["symbol"],
        entry, exit_price, pnl_usd, pnl_pct, reason_close
    )
    return summary


def update_trailing_stop(trade_id: int, new_trailing_stop: float):
    """Update the trailing stop price for an open trade."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE trades SET trailing_stop = ? WHERE id = ? AND status = 'open'",
            (new_trailing_stop, trade_id)
        )
        conn.commit()


def get_open_trades(bot: str | None = None) -> list[dict]:
    """Return all open trades, optionally filtered by bot."""
    with get_conn() as conn:
        if bot:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='open' AND bot=? ORDER BY opened_at",
                (bot,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='open' ORDER BY bot, opened_at"
            ).fetchall()
    return [dict(r) for r in rows]


def get_balance(bot: str) -> float:
    """Return current paper balance for a bot."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT balance FROM bot_accounts WHERE bot = ?", (bot,)
        ).fetchone()
    return row["balance"] if row else 10000.0


def get_daily_pnl(bot: str, date: str | None = None) -> float:
    """Return total realised P&L for a bot on a given date (defaults to today)."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COALESCE(SUM(pnl_usd), 0) as total
            FROM trades
            WHERE bot=? AND status != 'open' AND DATE(closed_at) = ?
        """, (bot, date)).fetchone()
    return row["total"] if row else 0.0


def get_performance(bot: str, days: int = 30) -> dict:
    """Return performance summary for a bot over N days."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT pnl_usd, pnl_pct, direction, status
            FROM trades
            WHERE bot=? AND status != 'open'
              AND opened_at >= datetime('now', ?)
        """, (bot, f"-{days} days")).fetchall()

        account = conn.execute(
            "SELECT balance, starting_balance FROM bot_accounts WHERE bot=?", (bot,)
        ).fetchone()

    trades = [dict(r) for r in rows]
    total  = len(trades)
    wins   = sum(1 for t in trades if t["pnl_usd"] >= 0)
    total_pnl = sum(t["pnl_usd"] for t in trades)
    starting  = account["starting_balance"] if account else 10000.0
    balance   = account["balance"] if account else 10000.0

    return {
        "bot":          bot,
        "days":         days,
        "trades":       total,
        "wins":         wins,
        "losses":       total - wins,
        "win_rate":     round(wins / total * 100, 1) if total else 0,
        "total_pnl":    round(total_pnl, 2),
        "balance":      round(balance, 2),
        "return_pct":   round((balance - starting) / starting * 100, 2),
    }


def print_performance_table():
    """Print a formatted performance table for all bots."""
    print("\n" + "="*65)
    print(f"{'BOT':<10} {'TRADES':>7} {'WIN%':>6} {'P&L':>9} {'BALANCE':>10} {'RETURN':>8}")
    print("-"*65)
    for bot in ["APEX", "DRIFT", "TITAN", "SENTINEL"]:
        p = get_performance(bot)
        print(
            f"{p['bot']:<10} {p['trades']:>7} {p['win_rate']:>5.1f}% "
            f"${p['total_pnl']:>8.2f} ${p['balance']:>9.2f} {p['return_pct']:>7.2f}%"
        )
    print("="*65 + "\n")


# Auto-init on import
init_db()

if __name__ == "__main__":
    print_performance_table()

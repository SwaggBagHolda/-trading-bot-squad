"""
File-locked read/write for hive_mind.json.
All bots and NEXUS should use these functions to prevent corruption.
"""
import json, fcntl
from pathlib import Path

HIVE = Path(__file__).parent / "hive_mind.json"
_LOCK = Path(__file__).parent / "hive_mind.lock"


def read_hive() -> dict:
    """Read hive_mind.json with shared (read) lock."""
    try:
        with open(_LOCK, "a+") as lf:
            fcntl.flock(lf, fcntl.LOCK_SH)
            try:
                return json.loads(HIVE.read_text()) if HIVE.exists() else {}
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except Exception:
        # Fallback: unlocked read
        try:
            return json.loads(HIVE.read_text()) if HIVE.exists() else {}
        except Exception:
            return {}


def write_hive(data: dict):
    """Write hive_mind.json with exclusive (write) lock."""
    with open(_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            HIVE.write_text(json.dumps(data, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def update_hive(fn):
    """Read-modify-write hive_mind.json atomically. fn(hive_dict) -> None (mutates in place)."""
    with open(_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            hive = json.loads(HIVE.read_text()) if HIVE.exists() else {}
            fn(hive)
            HIVE.write_text(json.dumps(hive, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

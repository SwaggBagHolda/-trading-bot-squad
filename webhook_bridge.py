#!/usr/bin/env python3
"""
NEXUS <-> Claude Code Webhook Bridge
=====================================
Tiny HTTP server on localhost:7777. Zero dependencies beyond stdlib.

POST /briefing          — NEXUS pushes updated briefing (JSON body: {"content": "..."})
GET  /briefing          — Claude Code reads latest briefing (returns markdown text)
GET  /briefing?format=json — Returns JSON with content + metadata
GET  /health            — Health check
POST /event             — NEXUS pushes arbitrary events (JSON body: {"type": "...", "data": "..."})
GET  /events            — Claude Code reads recent events (last 50)

Usage:
    python3 webhook_bridge.py              # Start on port 7777
    python3 webhook_bridge.py --port 8888  # Custom port

Push from Python:
    requests.post("http://localhost:7777/briefing", json={"content": "# Briefing..."})

Read from curl:
    curl http://localhost:7777/briefing
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE = Path(__file__).parent
BRIEFING_FILE = BASE / "shared" / "claude_context.md"
EVENTS_FILE = BASE / "shared" / "bridge_events.json"
PORT = 7777
MAX_EVENTS = 50

# In-memory state
_state = {
    "briefing": "",
    "briefing_updated": None,
    "briefing_push_count": 0,
    "events": [],
    "started": datetime.now().isoformat(),
}
_lock = threading.Lock()


def _load_initial_state():
    """Load briefing from disk on startup."""
    if BRIEFING_FILE.exists():
        _state["briefing"] = BRIEFING_FILE.read_text()
        _state["briefing_updated"] = datetime.fromtimestamp(
            BRIEFING_FILE.stat().st_mtime
        ).isoformat()
    if EVENTS_FILE.exists():
        try:
            _state["events"] = json.loads(EVENTS_FILE.read_text())[-MAX_EVENTS:]
        except Exception:
            _state["events"] = []


def _save_briefing(content):
    """Write briefing to disk and update in-memory state."""
    with _lock:
        _state["briefing"] = content
        _state["briefing_updated"] = datetime.now().isoformat()
        _state["briefing_push_count"] += 1
    BRIEFING_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRIEFING_FILE.write_text(content)


def _add_event(event_type, data):
    """Add an event to the log."""
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }
    with _lock:
        _state["events"].append(event)
        _state["events"] = _state["events"][-MAX_EVENTS:]
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        EVENTS_FILE.write_text(json.dumps(_state["events"], indent=2))
    except Exception:
        pass
    return event


class BridgeHandler(BaseHTTPRequestHandler):
    """Handle GET/POST for the webhook bridge."""

    def log_message(self, format, *args):
        """Suppress default logging — use our own."""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        query = self.path.split("?")[1] if "?" in self.path else ""

        if path == "/briefing":
            if "format=json" in query:
                self._send_json({
                    "content": _state["briefing"],
                    "updated": _state["briefing_updated"],
                    "push_count": _state["briefing_push_count"],
                })
            else:
                self._send_text(_state["briefing"] or "# No briefing pushed yet\n")

        elif path == "/events":
            self._send_json(_state["events"])

        elif path == "/health":
            self._send_json({
                "status": "ok",
                "started": _state["started"],
                "briefing_updated": _state["briefing_updated"],
                "push_count": _state["briefing_push_count"],
                "event_count": len(_state["events"]),
                "uptime_seconds": int(time.time() - time.mktime(
                    datetime.fromisoformat(_state["started"]).timetuple()
                )),
            })

        else:
            self._send_json({"error": "not found", "endpoints": [
                "GET /briefing", "GET /events", "GET /health",
                "POST /briefing", "POST /event",
            ]}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/briefing":
            try:
                body = self._read_body()
                content = body.get("content", "")
                if not content:
                    self._send_json({"error": "missing 'content' field"}, 400)
                    return
                _save_briefing(content)
                _add_event("briefing_push", f"Updated ({len(content)} chars)")
                print(f"[BRIDGE] Briefing updated ({len(content)} chars) at {_state['briefing_updated']}")
                self._send_json({
                    "status": "ok",
                    "updated": _state["briefing_updated"],
                    "chars": len(content),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/event":
            try:
                body = self._read_body()
                event_type = body.get("type", "unknown")
                data = body.get("data", "")
                event = _add_event(event_type, data)
                print(f"[BRIDGE] Event: {event_type} — {str(data)[:80]}")
                self._send_json({"status": "ok", "event": event})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self._send_json({"error": "not found"}, 404)


def start_bridge(port=PORT):
    """Start the webhook bridge server."""
    _load_initial_state()
    server = HTTPServer(("127.0.0.1", port), BridgeHandler)
    print(f"[BRIDGE] NEXUS<->Claude webhook bridge running on http://localhost:{port}")
    print(f"[BRIDGE] Endpoints: GET/POST /briefing, GET /events, POST /event, GET /health")
    if _state["briefing"]:
        print(f"[BRIDGE] Loaded existing briefing ({len(_state['briefing'])} chars)")
    server.serve_forever()


# ── Client helper (import from other scripts) ────────────────────────────────

def push_briefing(content, port=PORT):
    """Push briefing content to the bridge. Call from NEXUS or scheduler."""
    import requests
    try:
        r = requests.post(
            f"http://localhost:{port}/briefing",
            json={"content": content},
            timeout=5,
        )
        return r.json()
    except Exception as e:
        print(f"[BRIDGE] Push failed (bridge down?): {e}")
        # Fallback: write directly to disk
        BRIEFING_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRIEFING_FILE.write_text(content)
        return {"status": "fallback_disk", "error": str(e)}


def push_event(event_type, data, port=PORT):
    """Push an event to the bridge. Call from NEXUS or scheduler."""
    import requests
    try:
        r = requests.post(
            f"http://localhost:{port}/event",
            json={"type": event_type, "data": data},
            timeout=5,
        )
        return r.json()
    except Exception:
        return None


def read_briefing(port=PORT):
    """Read latest briefing from the bridge. Call from Claude Code startup."""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/briefing", timeout=5)
        return r.text
    except Exception:
        # Fallback: read from disk
        if BRIEFING_FILE.exists():
            return BRIEFING_FILE.read_text()
        return None


if __name__ == "__main__":
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])
    start_bridge(port)

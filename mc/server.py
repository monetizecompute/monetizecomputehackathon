"""Dashboard server. Stdlib only, zero dependencies.

GET  /            the dashboard
GET  /api/status  wallet stats, hunger, liveness
GET  /api/feed    recent events, ledger entries, and the graveyard
POST /api/bank    confirm real cash in: {"amount_usd": 12.5, "memo": "...", "proof_url": "..."}
                  Human-confirmed on purpose. The agent books revenue itself,
                  but only a verified payout banks it. Banking a dead agent
                  starts the next generation.

Money in requires application/json (browsers cannot send that cross-origin
without a preflight this server never grants) and, if MC_BANK_TOKEN is set,
a matching X-MC-Token header.
"""

import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"
MAX_BODY = 4096


def make_handler(agent):
    class Handler(BaseHTTPRequestHandler):
        timeout = 10

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                try:
                    body = DASH.read_bytes()
                except OSError:
                    self._json({"error": "dashboard missing"}, 500)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/status":
                self._json(agent.status())
            elif path == "/api/feed":
                self._json({"events": list(agent.events)[::-1],
                            "ledger": agent.ledger.recent(30),
                            "graveyard": agent.ledger.lives()})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/api/bank":
                self._json({"error": "not found"}, 404)
                return
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                self._json({"error": "Content-Type must be application/json"}, 415)
                return
            expected_token = os.environ.get("MC_BANK_TOKEN")
            if expected_token and self.headers.get("X-MC-Token") != expected_token:
                self._json({"error": "bad or missing X-MC-Token"}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= MAX_BODY:
                    self._json({"error": "body required, 4KB max"}, 413)
                    return
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("body must be a JSON object")
                amount = float(data.get("amount_usd", 0))
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "bad request"}, 400)
                return
            if not math.isfinite(amount) or amount <= 0:
                self._json({"error": "amount_usd must be a positive finite number"}, 400)
                return
            source = data.get("source", "earned")
            if source not in ("earned", "donation"):
                self._json({"error": "source must be 'earned' or 'donation'"}, 400)
                return
            agent.revive(amount, str(data.get("memo", "confirmed payout"))[:300],
                         data.get("proof_url"), source)
            self._json(agent.status())

        def log_message(self, *args):
            pass

    return Handler


def serve(agent, port=8901):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(agent))
    print(f"dashboard: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

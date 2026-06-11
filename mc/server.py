"""Dashboard server. Stdlib only, zero dependencies.

GET  /            the dashboard
GET  /api/status  wallet stats and liveness
GET  /api/feed    recent events and ledger entries
POST /api/bank    confirm real cash in: {"amount_usd": 12.5, "memo": "...", "proof_url": "..."}
                  Human-confirmed on purpose. The agent books revenue itself,
                  but only a verified payout banks it.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DASH = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


def make_handler(agent):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = DASH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/status":
                self._json(agent.status())
            elif self.path == "/api/feed":
                self._json({"events": list(agent.events)[::-1],
                            "ledger": agent.ledger.recent(30)})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path == "/api/bank":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length) or b"{}")
                amount = float(data.get("amount_usd", 0))
                if amount <= 0:
                    self._json({"error": "amount_usd must be positive"}, 400)
                    return
                agent.ledger.bank(amount, data.get("memo", "confirmed payout"),
                                  data.get("proof_url"))
                agent.emit("banked", f"${amount:.2f} banked: {data.get('memo', '')}")
                if not agent.alive and agent.ledger.balance() > 0:
                    agent.alive = True
                    agent.start_background()
                    agent.emit("revival", "balance restored. back to work.")
                self._json(agent.status())
            else:
                self._json({"error": "not found"}, 404)

        def log_message(self, *args):
            pass

    return Handler


def serve(agent, port=8901):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(agent))
    print(f"dashboard: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()

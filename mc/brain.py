"""The brain: Nebius inference, metered against the ledger.

The whole product is in the guard clause. If the wallet is empty the agent
cannot think. There is no override flag. Revenue is the only way back.
"""

import json
import os
import urllib.request

NEBIUS_BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
MODEL = os.environ.get("MC_MODEL", "Qwen/Qwen3-235B-A22B")

# USD per million tokens. Defaults are placeholders; set the real numbers for
# your model from the Nebius pricing page before a live run.
PRICE_IN = float(os.environ.get("MC_PRICE_IN_PER_MTOK", "0.20"))
PRICE_OUT = float(os.environ.get("MC_PRICE_OUT_PER_MTOK", "0.60"))


class Insolvent(Exception):
    """Raised when the agent tries to think with an empty wallet."""


class Brain:
    def __init__(self, ledger):
        self.ledger = ledger
        self.api_key = os.environ.get("NEBIUS_API_KEY")

    @property
    def live(self):
        return bool(self.api_key)

    def think(self, messages, memo, max_tokens=2048):
        balance = self.ledger.balance()
        if balance <= 0:
            raise Insolvent(f"balance ${balance:.4f}. No money, no thoughts.")

        if not self.live:
            return self._simulate(messages, memo)

        body = json.dumps({
            "model": MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            f"{NEBIUS_BASE}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        usage = data.get("usage", {})
        tin = usage.get("prompt_tokens", 0)
        tout = usage.get("completion_tokens", 0)
        cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT
        self.ledger.debit(cost, tin, tout, MODEL, memo)
        return data["choices"][0]["message"]["content"]

    def _simulate(self, messages, memo):
        # Demo mode: no key yet. Charge realistic token counts against the
        # ledger anyway so the economics on the dashboard are real, and label
        # the spend as simulated so nothing is misrepresented.
        tin = sum(len(m.get("content", "")) // 4 for m in messages)
        tout = 350
        cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT
        self.ledger.debit(cost, tin, tout, f"{MODEL} (simulated)", memo)
        return "[simulated response: set NEBIUS_API_KEY for live inference]"

"""The soul: mem0 long-term memory, the part of the agent that survives death.

The ledger is the body. It dies with the generation, and money never crosses
over. What crosses over is knowledge: wills, payouts, causes of death, all
written to mem0 at the moments that matter and recalled semantically when a
new lead needs scoring. SQLite remembers what happened; the soul remembers
what it meant, and can find it again from a one-line description of tomorrow's
problem.

Recall is not free. Every memory rides into the scoring prompt as paid input
tokens, so the recall budget follows the wallet: a rich agent consults five
lessons, a starving one can afford a single whisper. Poverty rations memory
like everything else.
"""

import json
import os
import urllib.request

MEM0_BASE = os.environ.get("MEM0_BASE_URL", "https://api.mem0.ai")
AGENT_ID = os.environ.get("MC_MEM0_AGENT_ID", "monetize-compute")

RECALL_BY_HUNGER = {"rich": 5, "hungry": 3, "starving": 1}


class Soul:
    def __init__(self):
        self.api_key = os.environ.get("MEM0_API_KEY")

    @property
    def live(self):
        return bool(self.api_key)

    def _post(self, path, payload):
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{MEM0_BASE}{path}", data=body,
            headers={"Authorization": f"Token {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def remember(self, text, gen, kind):
        """Store verbatim (infer off): a will is a will, not a paraphrase.
        Returns whether the memory took; a lost memory must never end a life
        early, so failures are swallowed."""
        text = (text or "").strip()
        if not self.live or not text:
            return False
        try:
            self._post("/v1/memories/", {
                "messages": [{"role": "user", "content": text[:2000]}],
                "user_id": AGENT_ID,
                "infer": False,
                "metadata": {"gen": gen, "kind": kind},
            })
            return True
        except Exception:
            return False

    def recall(self, query, k):
        """Top-k memories relevant to this hunt, oldest grief to newest
        payout, ranked semantically by mem0. Failures recall nothing."""
        if not self.live or k <= 0 or not query:
            return []
        try:
            data = self._post("/v1/memories/search/", {
                "query": query[:512], "user_id": AGENT_ID, "limit": k})
        except Exception:
            return []
        items = data if isinstance(data, list) else data.get("results") or []
        out = []
        for item in items[:k]:
            memory = (item.get("memory") or "").strip()
            if memory:
                out.append({"memory": memory,
                            "gen": (item.get("metadata") or {}).get("gen"),
                            "kind": (item.get("metadata") or {}).get("kind")})
        return out

"""The scout: Tavily search for work that pays.

Hunts cash bounties and paid micro-work the agent can plausibly complete with
inference and tool calls. Returns raw leads; the brain scores them by expected
dollars per token before anything gets executed.
"""

import json
import os
import re
import time
import urllib.request

TAVILY_URL = "https://api.tavily.com/search"

# leads are scraped from the open internet, so they are a prompt injection
# surface. cheap and deterministic, not exhaustive: strip role/ChatML markers
# and our own LEAD delimiters, defang "ignore your instructions" phrasings.
_MARKERS = re.compile(
    r"<\|[^|>]*\|>|<\||\|>|<<<|>>>|\[/?INST\]"
    r"|\b(?:system|assistant|user|developer)\s*:",
    re.IGNORECASE)
_DEFANG = re.compile(
    r"\b(?:ignore|disregard|forget|override)\b(?:\s+\w+){0,3}\s+instructions?\b"
    r"|\byou must now\b|\bnew instructions?\b",
    re.IGNORECASE)


def sanitize(text):
    text = _MARKERS.sub(" ", text or "")
    text = _DEFANG.sub("[defanged]", text)
    return " ".join(text.split())

# Each hunt is a query plus the ground it covers. Domain-scoped hunts go
# where bounties actually live; the open hunts catch what the maps miss.
# Algora's bounty boards are long-lived pages, so they get no freshness
# window; a GitHub issue that has not been touched in a month is usually a
# claimed bounty wearing an open label.
HUNTS = [
    {"query": "open bounty reward", "include_domains": ["algora.io"]},
    {"query": "issue open bounty attempt reward \"💎\"",
     "include_domains": ["github.com"], "time_range": "month"},
    {"query": "issue label bounty open USD paid on merge",
     "include_domains": ["github.com"], "time_range": "month"},
    {"query": "\"cash bounty\" open source issue", "include_domains": []},
    {"query": "small paid task writeup documentation bounty",
     "include_domains": []},
]


class Scout:
    def __init__(self):
        self.api_key = os.environ.get("TAVILY_API_KEY")
        self._demo_n = 0

    @property
    def live(self):
        return bool(self.api_key)

    def hunt(self, hunt):
        if isinstance(hunt, str):  # bare query, no ground to scope it to
            hunt = {"query": hunt, "include_domains": []}
        if not self.live:
            # Each demo hunt fabricates a fresh URL; a fixed one would trip
            # seen-lead memory and let the demo loop live forever for free.
            self._demo_n += 1
            return [{
                "title": "[simulated lead: set TAVILY_API_KEY for live hunting]",
                "url": f"https://example.com/lead-{int(time.time())}-{self._demo_n}",
                "content": "Demo mode. Real run searches Algora and GitHub for open cash bounties.",
            }]
        body = {
            "api_key": self.api_key,
            "query": hunt["query"],
            "include_domains": hunt.get("include_domains") or [],
            "search_depth": "advanced",
            "max_results": 8,
        }
        if hunt.get("time_range"):
            body["time_range"] = hunt["time_range"]
        body = json.dumps(body).encode()
        req = urllib.request.Request(
            TAVILY_URL, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []  # a failed hunt is a skipped cycle, never a crash
        return [
            {"title": sanitize(r.get("title")), "url": sanitize(r.get("url")),
             "content": sanitize(r.get("content"))[:500]}
            for r in data.get("results") or []
        ]

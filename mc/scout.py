"""The scout: Tavily search for work that pays.

Hunts cash bounties and paid micro-work the agent can plausibly complete with
inference and tool calls. Returns raw leads; the brain scores them by expected
dollars per token before anything gets executed.
"""

import json
import os
import re
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

HUNTS = [
    "site:algora.io open bounty",
    "github issue \"bounty\" label open reward USD",
    "\"cash bounty\" open source issue 2026",
    "paid task agent automation small bounty",
]


class Scout:
    def __init__(self):
        self.api_key = os.environ.get("TAVILY_API_KEY")

    @property
    def live(self):
        return bool(self.api_key)

    def hunt(self, query):
        if not self.live:
            return [{
                "title": "[simulated lead: set TAVILY_API_KEY for live hunting]",
                "url": "https://example.com",
                "content": "Demo mode. Real run searches Algora and GitHub for open cash bounties.",
            }]
        body = json.dumps({
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 8,
        }).encode()
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

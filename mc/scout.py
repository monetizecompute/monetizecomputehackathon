"""The scout: Tavily search for work that pays.

Hunts cash bounties and paid micro-work the agent can plausibly complete with
inference and tool calls. Returns raw leads; the brain scores them by expected
dollars per token before anything gets executed.
"""

import json
import os
import urllib.request

TAVILY_URL = "https://api.tavily.com/search"

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return [
            {"title": r.get("title") or "", "url": r.get("url") or "",
             "content": (r.get("content") or "")[:500]}
            for r in data.get("results") or []
        ]

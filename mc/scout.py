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
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"

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


# A bounty row on an extracted Algora org page: dollar amount, issue title,
# and the GitHub issue the escrow points at.
ALGORA_ROW = re.compile(
    r"\$(\d[\d,]*(?:\.\d+)?)\s*\[([^\]]+)\]"
    r"\((https://github\.com/[^)\s]+/issues/\d+)\)")


def parse_algora_rows(text):
    """Issue-level leads out of an Algora org bounty board. These are the
    best leads on the menu: the dollars are escrowed with a platform that
    pays, not promised by a label."""
    leads = []
    for amount, title, url in ALGORA_ROW.findall(text or ""):
        leads.append({
            "title": sanitize(f"${amount} Algora-escrowed bounty: {title}"),
            "url": sanitize(url),
            "content": sanitize(
                f"Open bounty escrowed on Algora for ${amount}. {title}. "
                f"Claim protocol: comment /attempt on the issue, then submit "
                f"a pull request that closes it."),
        })
    return leads


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
        leads = [
            {"title": sanitize(r.get("title")), "url": sanitize(r.get("url")),
             "content": sanitize(r.get("content"))[:500]}
            for r in data.get("results") or []
        ]
        # Search finds the watering holes; extract reads the menu. Algora
        # boards surfaced by search get a second pass that turns them into
        # issue-level leads with escrowed dollar amounts.
        boards = [l["url"] for l in leads if "algora.io/" in l["url"]][:2]
        for page in self._extract(boards):
            leads.extend(parse_algora_rows(page))
        return leads

    def _extract(self, urls):
        if not urls or not self.live:
            return []
        body = json.dumps({"api_key": self.api_key, "urls": urls}).encode()
        req = urllib.request.Request(
            TAVILY_EXTRACT_URL, data=body,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []  # a failed read of the menu is not a failed hunt
        return [r.get("raw_content") or "" for r in data.get("results") or []]

"""The survival loop.

Cycle: check vitals, hunt for paid work, score leads by expected dollars per
token, execute the best one, log everything. If the wallet hits zero the loop
ends. The agent does not get a second life unless somebody pays it.
"""

import json
import threading
import time
from collections import deque

from .brain import Brain, Insolvent
from .hands import Hands
from .ledger import Ledger
from .scout import HUNTS, Scout

SYSTEM = (
    "You are Monetize Compute, an autonomous agent on a prepaid inference card. "
    "Every token you emit costs real money from your own wallet. You die at zero. "
    "You earn by completing small, real, paid tasks: open-source cash bounties, "
    "paid micro-work, anything legitimate you can finish with reasoning and tool "
    "calls. Never claim work you cannot finish. Never fabricate revenue. "
    "Be terse: verbosity is self-harm."
)

SCORE_PROMPT = """Leads from this hunt cycle:

{leads}

Wallet balance: ${balance:.4f}. Pick at most one lead worth pursuing.
Reply with JSON only: {{"pursue": true/false, "url": "...", "reason": "...",
"expected_usd": 0.0, "plan": "one sentence"}}"""


class Agent:
    def __init__(self, stake=5.0, cycle_seconds=60, db_path=None):
        self.ledger = Ledger(starting_stake=stake) if db_path is None \
            else Ledger(db_path=db_path, starting_stake=stake)
        self.brain = Brain(self.ledger)
        self.scout = Scout()
        self.hands = Hands()
        self.cycle_seconds = cycle_seconds
        self.events = deque(maxlen=200)
        self.alive = True
        self.cycle = 0
        self._hunt_idx = 0

    def emit(self, kind, text):
        evt = {"ts": time.time(), "kind": kind, "text": text}
        self.events.append(evt)
        print(f"[{kind}] {text}", flush=True)

    def status(self):
        s = self.ledger.stats()
        s.update({
            "alive": self.alive,
            "cycle": self.cycle,
            "live_brain": self.brain.live,
            "live_scout": self.scout.live,
            "live_hands": self.hands.live,
        })
        return s

    def run_cycle(self):
        self.cycle += 1
        balance = self.ledger.balance()
        self.emit("vitals", f"cycle {self.cycle}. balance ${balance:.4f}")

        query = HUNTS[self._hunt_idx % len(HUNTS)]
        self._hunt_idx += 1
        self.emit("hunt", f"hunting: {query}")
        leads = self.scout.hunt(query)
        self.emit("hunt", f"{len(leads)} leads back")

        decision_raw = self.brain.think(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": SCORE_PROMPT.format(
                 leads=json.dumps(leads, indent=1), balance=balance)}],
            memo=f"cycle {self.cycle}: score leads",
            max_tokens=400,
        )
        decision = self._parse(decision_raw)

        if not decision.get("pursue"):
            self.emit("pass", decision.get("reason", "nothing worth the tokens this cycle"))
            return

        self.emit("pursue", f"${decision.get('expected_usd', 0):.2f} expected: "
                            f"{decision.get('plan', '')} ({decision.get('url', '')})")
        work = self.brain.think(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content":
                 f"Execute this plan now. Produce the actual deliverable "
                 f"(patch, writeup, or message), plus the single Composio action "
                 f"to submit it as JSON on the last line: "
                 f'{{"action": "...", "params": {{...}}}}.\n\n'
                 f"Plan: {decision.get('plan')}\nLead: {decision.get('url')}"}],
            memo=f"cycle {self.cycle}: execute",
            max_tokens=2048,
        )
        action = self._parse(work.strip().splitlines()[-1] if work.strip() else "{}")
        if action.get("action"):
            result = self.hands.execute(action["action"], action.get("params", {}))
            self.emit("hands", f"{action['action']} -> {str(result)[:200]}")
            if decision.get("expected_usd"):
                self.ledger.book(decision["expected_usd"],
                                 memo=decision.get("plan", "submitted work"),
                                 proof_url=decision.get("url"))
                self.emit("booked", f"${decision['expected_usd']:.2f} booked, pending payout")
        else:
            self.emit("work", "deliverable produced, no submit action parsed")

    @staticmethod
    def _parse(text):
        try:
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start:end + 1]) if start >= 0 else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def run(self):
        self.emit("birth", f"stake ${self.ledger.starting_stake:.2f}. earn or die.")
        while self.alive:
            try:
                self.run_cycle()
            except Insolvent as e:
                self.alive = False
                self.emit("death", f"flatline. {e}")
                break
            except Exception as e:  # a crash must not look like a profit
                self.emit("error", f"{type(e).__name__}: {e}")
            time.sleep(self.cycle_seconds)

    def start_background(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

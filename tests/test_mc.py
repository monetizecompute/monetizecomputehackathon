"""The economics must be exactly right or the whole pitch is wrong.

Run: python3 -m unittest discover tests -v
"""

import json
import math
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from mc.brain import Brain, Insolvent, hunger_state
from mc.ledger import Ledger
from mc.loop import Agent
from mc.server import make_handler


def tmp_db():
    return Path(tempfile.mktemp(suffix=".db"))


class LedgerTest(unittest.TestCase):
    def test_balance_is_stake_minus_reserve_plus_net(self):
        led = Ledger(tmp_db(), starting_stake=5.0, reserve=0.05)
        self.assertAlmostEqual(led.balance(), 4.95)
        led.debit(1.0, 100, 100, "m", "spend")
        led.bank(2.0, "earn")
        self.assertAlmostEqual(led.balance(), 5.95)

    def test_booked_is_never_spendable(self):
        led = Ledger(tmp_db(), starting_stake=5.0)
        led.book(1000.0, "optimism")
        self.assertLess(led.balance(), 5.0)

    def test_reserve_clamped_for_tiny_stakes(self):
        led = Ledger(tmp_db(), starting_stake=0.10, reserve=0.05)
        self.assertAlmostEqual(led.reserve, 0.01)
        self.assertGreater(led.balance(), 0)

    def test_generations_scope_the_books(self):
        led = Ledger(tmp_db(), starting_stake=5.0)
        led.debit(4.0, 10, 10, "m", "gen1 spend")
        led.end_life("test", will="lesson one")
        led.begin_next_life()
        self.assertEqual(led.gen, 2)
        # Fresh stake: gen 1's spend does not haunt gen 2.
        self.assertAlmostEqual(led.balance(), 5.0 - led.reserve)
        self.assertEqual(led.wills(), [{"gen": 1, "will": "lesson one"}])

    def test_resume_picks_up_life_in_progress(self):
        db = tmp_db()
        led = Ledger(db, starting_stake=5.0)
        led.debit(1.0, 10, 10, "m", "spend")
        led2 = Ledger(db, starting_stake=5.0)  # restart, same life
        self.assertEqual(led2.gen, 1)
        self.assertAlmostEqual(led2.balance(), led.balance())

    def test_stats_rev_per_mtok(self):
        led = Ledger(tmp_db(), starting_stake=5.0)
        led.debit(0.5, 500_000, 500_000, "m", "spend")
        led.bank(3.0, "earn")
        self.assertAlmostEqual(led.stats()["rev_per_mtok"], 3.0)


class BrainTest(unittest.TestCase):
    def test_hunger_ladder(self):
        self.assertEqual(hunger_state(5.0, 5.0), "rich")
        self.assertEqual(hunger_state(2.0, 5.0), "hungry")
        self.assertEqual(hunger_state(0.5, 5.0), "starving")

    def test_insolvent_at_zero(self):
        led = Ledger(tmp_db(), starting_stake=1.0)
        led.debit(1.0, 10, 10, "m", "broke")
        with self.assertRaises(Insolvent):
            Brain(led).think([{"role": "user", "content": "hi"}], "test")

    def test_insolvent_when_next_thought_unaffordable(self):
        led = Ledger(tmp_db(), starting_stake=1.0)
        led.debit(led.balance() - 1e-7, 10, 10, "m", "almost broke")
        with self.assertRaises(Insolvent):
            Brain(led).think([{"role": "user", "content": "x" * 4000}], "test")

    def test_reserve_lets_a_dying_agent_speak(self):
        led = Ledger(tmp_db(), starting_stake=1.0)
        led.debit(led.balance() + 0.001, 10, 10, "m", "overdrawn")
        out = Brain(led).think([{"role": "user", "content": "epitaph"}],
                               "last words", spend_reserve=True)
        self.assertTrue(out)

    def test_demo_mode_still_charges_the_ledger(self):
        led = Ledger(tmp_db(), starting_stake=5.0)
        before = led.balance()
        Brain(led).think([{"role": "user", "content": "think"}], "test")
        self.assertLess(led.balance(), before)
        self.assertIn("simulated", led.recent(1)[0]["model"])


class ParseTest(unittest.TestCase):
    def test_pretty_printed_json(self):
        text = 'deliverable here\n{\n  "action": "GITHUB_CREATE_PR",\n  "params": {"x": 1}\n}'
        self.assertEqual(Agent._last_json(text, require_key="action")["action"],
                         "GITHUB_CREATE_PR")

    def test_braces_in_deliverable_do_not_break_parsing(self):
        text = 'patch: function f() { return {a: 1}; }\n{"action": "SEND", "params": {}}'
        self.assertEqual(Agent._last_json(text, require_key="action")["action"], "SEND")

    def test_last_object_wins(self):
        text = '{"pursue": false} then later {"pursue": true, "url": "u"}'
        self.assertTrue(Agent._last_json(text)["pursue"])

    def test_garbage_returns_empty(self):
        self.assertEqual(Agent._last_json("no json here } {"), {})
        self.assertEqual(Agent._last_json(""), {})
        self.assertEqual(Agent._last_json(None), {})

    def test_usd_coercion(self):
        self.assertEqual(Agent._usd("5.50"), 5.5)
        self.assertEqual(Agent._usd(float("nan")), 0.0)
        self.assertEqual(Agent._usd(float("inf")), 0.0)
        self.assertEqual(Agent._usd(-3), 0.0)
        self.assertEqual(Agent._usd(None), 0.0)
        self.assertEqual(Agent._usd("plenty"), 0.0)
        self.assertEqual(Agent._usd(1e12), 10_000.0)


class BankEndpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = Agent(stake=5.0, cycle_seconds=3600, db_path=tmp_db())
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.agent))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def post(self, body, content_type="application/json"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/bank",
            data=body if isinstance(body, bytes) else body.encode(),
            headers={"Content-Type": content_type}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_valid_bank(self):
        before = self.agent.ledger.balance()
        status, body = self.post('{"amount_usd": 1.25, "memo": "test"}')
        self.assertEqual(status, 200)
        self.assertAlmostEqual(self.agent.ledger.balance(), before + 1.25)

    def test_nan_and_infinity_rejected(self):
        for payload in ('{"amount_usd": NaN}', '{"amount_usd": Infinity}',
                        '{"amount_usd": -Infinity}'):
            status, _ = self.post(payload)
            self.assertEqual(status, 400, payload)
        self.assertTrue(math.isfinite(self.agent.ledger.balance()))

    def test_garbage_rejected_not_crashed(self):
        for payload, ct in [("not json", "application/json"),
                            ("[1,2]", "application/json"),
                            ('{"amount_usd": "abc"}', "application/json"),
                            ('{"amount_usd": -5}', "application/json")]:
            status, _ = self.post(payload, ct)
            self.assertEqual(status, 400, payload)

    def test_wrong_content_type_rejected(self):
        status, _ = self.post('{"amount_usd": 1}', "text/plain")
        self.assertEqual(status, 415)

    def test_status_and_feed_alive(self):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/api/status", timeout=10) as r:
            self.assertEqual(r.status, 200)
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/api/feed", timeout=10) as r:
            self.assertIn("graveyard", json.loads(r.read()))


class LifecycleTest(unittest.TestCase):
    def test_death_leaves_will_and_rebirth_inherits_it(self):
        agent = Agent(stake=0.005, cycle_seconds=0, db_path=tmp_db())
        agent.run()  # demo mode burns the stake and dies
        self.assertFalse(agent.alive)
        lives = agent.ledger.lives()
        self.assertIsNotNone(lives[0]["died_ts"])
        self.assertEqual(len(agent.ledger.wills()), 1)

        agent.revive(5.0, "resurrection")
        time.sleep(0.1)
        agent.alive = False  # stop the background loop
        self.assertEqual(agent.ledger.gen, 2)
        self.assertIn("generation 2", agent._system())

    def test_bank_while_alive_does_not_advance_generation(self):
        agent = Agent(stake=5.0, cycle_seconds=3600, db_path=tmp_db())
        agent.revive(1.0, "tip")
        self.assertEqual(agent.ledger.gen, 1)
        agent.alive = False


if __name__ == "__main__":
    unittest.main()

"""The brain: Nebius inference, metered against the ledger.

The whole product is in the guard clause. If the wallet is empty the agent
cannot think. There is no override flag. Revenue is the only way back.

Poverty has texture here. The model ladder follows the wallet: rich gets the
big model and long thoughts, hungry gets a mid model on a tighter token
budget, starving gets the cheapest model and rations. The agent literally
thinks smaller as it gets poorer.
"""

import json
import os
import urllib.error
import urllib.request

NEBIUS_BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")

# (model, USD per 1M input tokens, USD per 1M output tokens, max_tokens cap)
# Defaults match published Nebius per-token pricing as of June 2026.
# Override in .env if they drift; the ledger is only as honest as these.
LADDER = {
    # Instruct-2507 variants: non-thinking, so reasoning traces cannot eat
    # the token budget or pollute the JSON the loop parses.
    "rich": (
        os.environ.get("MC_MODEL_RICH", "Qwen/Qwen3-235B-A22B-Instruct-2507"),
        float(os.environ.get("MC_PRICE_RICH_IN", "0.20")),
        float(os.environ.get("MC_PRICE_RICH_OUT", "0.60")),
        2048,
    ),
    "hungry": (
        os.environ.get("MC_MODEL_HUNGRY", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
        float(os.environ.get("MC_PRICE_HUNGRY_IN", "0.10")),
        float(os.environ.get("MC_PRICE_HUNGRY_OUT", "0.30")),
        1024,
    ),
    # Not Nemotron-Nano, despite it being cheaper on paper: measured live, it
    # bills ~55 hidden reasoning tokens to say "ok". A model that lies about
    # its appetite cannot be trusted with a dying agent's last cents. Gemma
    # bills only the tokens you can see.
    "starving": (
        os.environ.get("MC_MODEL_STARVING", "google/gemma-3-27b-it"),
        float(os.environ.get("MC_PRICE_STARVING_IN", "0.10")),
        float(os.environ.get("MC_PRICE_STARVING_OUT", "0.30")),
        512,
    ),
}

RATIONS = (
    "\n\nYou are poor right now. Answer in as few tokens as you can get away "
    "with. Every word you emit shortens your life."
)


class Insolvent(Exception):
    """Raised when the agent tries to think with an empty wallet."""


def hunger_state(balance, stake):
    ratio = balance / stake if stake > 0 else 0
    if ratio > 0.6:
        return "rich"
    if ratio > 0.2:
        return "hungry"
    return "starving"


class Brain:
    def __init__(self, ledger):
        self.ledger = ledger
        self.api_key = os.environ.get("NEBIUS_API_KEY")

    @property
    def live(self):
        return bool(self.api_key)

    def hunger(self):
        return hunger_state(self.ledger.balance(), self.ledger.starting_stake)

    def think(self, messages, memo, max_tokens=None, spend_reserve=False):
        """One metered thought, paid for in advance.

        Solvency is checked against the worst case cost of THIS call, not
        just a positive balance, so the agent can never overdraw: if it
        cannot afford the thought at full length, the token budget shrinks
        to what the wallet covers, and below a minimum viable thought it is
        insolvent. spend_reserve lets a dying agent use its escrowed
        last-words money; everything else stops here.
        """
        balance = self.ledger.balance()
        if balance <= 0 and not spend_reserve:
            raise Insolvent(f"balance ${balance:.4f}. No money, no thoughts.")

        state = "starving" if spend_reserve else hunger_state(
            balance, self.ledger.starting_stake)
        model, price_in, price_out, cap = LADDER[state]
        max_tokens = min(max_tokens or cap, cap)

        if state == "starving" and messages and messages[0]["role"] == "system":
            messages = [
                {"role": "system", "content": messages[0]["content"] + RATIONS},
                *messages[1:],
            ]

        # Even dying is paid for: last words draw on balance plus the escrow
        # and shrink to what that affords. Nothing in this codebase thinks
        # for free. chars//3 overestimates most tokenizers on purpose.
        budget = balance + (self.ledger.reserve if spend_reserve else 0.0)
        est_in = sum(len(m.get("content", "")) // 3 for m in messages) + 64
        affordable_out = (budget - est_in / 1e6 * price_in) * 1e6 / price_out
        minimum = 16 if spend_reserve else 64
        if affordable_out < minimum:
            raise Insolvent(
                f"balance ${balance:.4f} cannot cover the next thought.")
        max_tokens = int(min(max_tokens, affordable_out))

        memo = f"[{state}] {memo}"
        if not self.live:
            return self._simulate(messages, memo, model, price_in, price_out,
                                  max_tokens)

        body = json.dumps({
            "model": model,
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
        # A failed call may still have been billed upstream (timeout after
        # generation, reset mid-body, error responses). The ledger never
        # gives the benefit of the doubt: on any failure, charge the actual
        # usage if the error body carries one, else the worst case we
        # authorized, then re-raise so the cycle is visibly lost.
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            usage = self._error_usage(e)
            tin = usage.get("prompt_tokens", est_in)
            tout = usage.get("completion_tokens", 0)
            cost = tin / 1e6 * price_in + tout / 1e6 * price_out
            self.ledger.debit(cost, tin, tout, model,
                              memo + f" (HTTP {e.code}, charged defensively)")
            raise
        except Exception:
            cost = est_in / 1e6 * price_in + max_tokens / 1e6 * price_out
            self.ledger.debit(cost, est_in, max_tokens, model,
                              memo + " (call failed, charged worst case)")
            raise

        usage = data.get("usage") or {}
        tin = usage.get("prompt_tokens")
        tout = usage.get("completion_tokens")
        if tin is None or tout is None:
            # A response with no usage block must never meter at zero. Charge
            # a conservative estimate and say so in the ledger.
            tin = tin if tin is not None else est_in
            tout = tout if tout is not None else max_tokens
            memo += " (usage estimated)"
        cost = tin / 1e6 * price_in + tout / 1e6 * price_out
        self.ledger.debit(cost, tin, tout, model, memo)
        choices = data.get("choices") or [{}]
        return (choices[0].get("message") or {}).get("content") or ""

    @staticmethod
    def _error_usage(err):
        try:
            return (json.loads(err.read()).get("usage")) or {}
        except Exception:
            return {}

    def _simulate(self, messages, memo, model, price_in, price_out, max_tokens):
        # Demo mode: no key yet. Charge realistic token counts against the
        # ledger anyway so the economics on the dashboard are real, and label
        # the spend as simulated so nothing is misrepresented.
        tin = sum(len(m.get("content", "")) // 4 for m in messages)
        tout = min(350, max_tokens)
        cost = tin / 1e6 * price_in + tout / 1e6 * price_out
        self.ledger.debit(cost, tin, tout, f"{model} (simulated)", memo)
        return "[simulated response: set NEBIUS_API_KEY for live inference]"

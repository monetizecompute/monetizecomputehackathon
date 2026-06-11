# Monetize Compute

**The agent that pays for its own inference.**

Every agent demo you have seen burns someone else's API credits and calls it
the future. This one has a wallet. It starts with a $5 stake on a prepaid
inference card. Every thought is metered against that wallet at real Nebius
per-token rates. When the balance hits zero it cannot call the model anymore.
It does not get a warning. It flatlines.

The only way it stays alive is to earn faster than it thinks.

## How it survives

A survival loop, every 60 seconds:

1. **Vitals.** Check the wallet. Zero means dead. There is no override flag in
   the code. Go look.
2. **Hunt.** Tavily searches for work that pays: open cash bounties on Algora
   and GitHub, paid micro-tasks, anything legitimate it can finish with
   reasoning and tool calls.
3. **Score.** The brain prices each lead in expected dollars per token before
   spending anything on it. Verbosity is self-harm when you pay your own bill.
4. **Execute.** Composio is the hands: fork, patch, open the PR, send the email.
5. **Account.** Submitted work books as pending revenue. Cash only banks when a
   human confirms the payout with proof. The agent cannot pay itself.

## The economics are the interface

The dashboard is a P&L, not a chat window. Wallet as a life bar. Inference
spend in red, banked cash in green, booked pipeline in amber, and the metric
that matters: **revenue per million tokens.** An agent is a business with one
employee and one cost. This makes that literal.

## Stack

- **OpenClaw** as the runtime harness
- **Nebius** for inference, priced per token into the ledger
- **Tavily** for hunting paid work
- **Composio** for executing it

## Run it

```bash
git clone <this repo> && cd monetize-compute
cp .env.example .env   # add keys, or run keyless in labeled demo mode
python3 run.py --stake 5.00
# dashboard at http://127.0.0.1:8901
```

Zero dependencies in demo mode, Python stdlib only. With keys set, the same
loop runs live.

Confirm a real payout (the only way money enters):

```bash
curl -X POST localhost:8901/api/bank \
  -d '{"amount_usd": 25.0, "memo": "algora bounty paid", "proof_url": "..."}'
```

## Honesty rules

Simulated anything is labeled simulated, on the dashboard and in the ledger.
Booked is not banked. Banked requires human-verified proof. The agent never
fabricates revenue because the code does not give it a way to.

## Why

Built by [Monetize Compute, LLC](https://monetizecompute.com), a
forward-deployed AI company with one thesis: own the compute, turn it into
business outcomes. This is the thesis with a heartbeat. The winner of this
hackathon walks the plank. This agent walks it every day it fails to break even.

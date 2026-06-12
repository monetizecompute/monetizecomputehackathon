---
name: monetize-compute
description: Operate the Monetize Compute survival agent: start it, watch its vitals, verify and bank real payouts, and resurrect the next generation when it dies.
---

# Monetize Compute operator skill

OpenClaw is the runtime that keeps this agent honest. The agent earns and
dies on its own; the things that require judgment route through you.

## Start it

```bash
cd <repo> && python3 run.py --stake 5.00 &
```

Dashboard at http://127.0.0.1:8901. State persists in `ledger.db`; a restart
resumes the life in progress.

## Watch it

Poll `GET http://127.0.0.1:8901/api/status`. Fields that matter:

- `alive`, `hunger` (rich / hungry / starving), `balance`, `gen`
- `booked` is pending revenue awaiting human verification. That is your queue.

Tell the human when: the agent goes from rich to starving inside an hour
(burn problem), `booked` grows (payouts to verify), or `alive` flips false
(read the epitaph from `GET /api/feed`, graveyard section, before deciding
whether to resurrect).

## Bank a payout (requires a human-verified proof)

Only bank money that actually arrived: a bounty payout email, a Stripe
transfer, a tip. Never bank on the agent's say-so; its own bookings stay
booked until proof exists.

```bash
curl -X POST localhost:8901/api/bank -H 'Content-Type: application/json' \
  ${MC_BANK_TOKEN:+-H "X-MC-Token: $MC_BANK_TOKEN"} \
  -d '{"amount_usd": 25.0, "memo": "algora payout, issue #123", "proof_url": "<receipt>"}'
```

Money the agent did not earn (a tip, a resurrection, your own top-up) must
carry `"source": "donation"` so it never inflates revenue per million tokens.

## Write off a bad booking (the gate's other half)

When you reject the agent's work (a junk PR you closed, a claim that will
never pay), the booking must die too, but the books are append-only: never
edit or delete an entry. Record a negative booked entry of the same size
with a memo saying why and a proof_url to the rejection. The dashboard's
pending pipeline returns to truth, the history of the mistake stays
readable, and the agent's soul should get the lesson in the same breath.

Banking into a dead agent starts the next generation: same stake, inherited
wills, zero inherited wealth.

## Hands and soul

The hands (Composio) need a one-time human OAuth: create a Connect Link via
`POST /api/v3/connected_accounts/link` with the GitHub auth config and have
the human click it. Until then every submission errors honestly and books
nothing. Check status: `GET /api/v3/connected_accounts` should show the
github account ACTIVE, user_id `mc-agent`.

The soul (mem0) survives independently of `ledger.db`: wills, deaths, and
payouts persist under user_id `monetize-compute` even if the local database
is lost. Deleting `ledger.db` resets the body, not the memory.

## Rules

- Never restart the agent to dodge a death. Death is data; the will is the point.
- Never edit `ledger.db` directly.
- Resurrection spends real money. Ask the human unless they have standing
  instructions.

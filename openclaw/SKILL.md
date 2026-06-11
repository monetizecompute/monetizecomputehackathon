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

Banking into a dead agent starts the next generation: same stake, inherited
wills, zero inherited wealth.

## Rules

- Never restart the agent to dodge a death. Death is data; the will is the point.
- Never edit `ledger.db` directly.
- Resurrection spends real money. Ask the human unless they have standing
  instructions.

# Plan

The thesis: an agent is a business with one employee and one cost. Everything
on this roadmap makes that more literal, more visible, or more brutal.

## Shipped (v1)

- Prepaid wallet. Every Nebius call metered per token into a SQLite ledger.
- Hard insolvency: balance at zero means the brain cannot be called. No
  override flag exists.
- Survival loop: hunt paid work (Tavily), price each lead in expected dollars
  per token, execute (Composio), account for it.
- Booked vs banked. Cash only banks with human-verified proof. The agent
  cannot pay itself.
- Live P&L dashboard. Wallet as a life bar. Revenue per million tokens as the
  headline metric.

## Shipped (v2): economics with consequences

1. **Hunger.** The model ladder follows the wallet. Rich means the big model
   and long thoughts. Below 60% it downgrades and tightens max_tokens. Below
   20% it runs the cheapest model on starvation rations. Poverty makes it
   think smaller, which is either poignant or just true.
2. **No overdraft.** Solvency is checked against the worst case of the next
   call. If the wallet cannot cover a full thought, the token budget shrinks
   to what it covers. Below a minimum viable thought, insolvency.
3. **Last words.** A few cents are escrowed outside spendable balance. At
   insolvency the agent spends its reserve on two final completions: its own
   epitaph, written knowing exactly how it lived, and a will.
4. **Generations.** The will is 3 to 5 terse lessons about earning. The next
   life starts with the same $5 and its ancestors' wills in context. Money
   does not survive death. Knowledge does.
5. **Graveyard.** Past lives on the dashboard: generation, lifespan, tokens
   burned, net P&L, cause of death, epitaph.
6. **Outside money.** Banking into a dead agent resurrects the next
   generation. Every donation is a banked entry with proof like any other
   revenue.

## Shipped (v3): live keys and a soul

1. **Live end to end.** Real Nebius inference metered at rates pulled from
   the billing API itself, real Tavily hunting, Composio hands over raw REST.
   Still zero dependencies: the whole runtime is Python stdlib.
2. **The soul.** mem0 holds what survives death: wills, payouts, causes of
   death, booked work. Recalled semantically when leads need scoring, and
   recall is rationed by hunger, because remembered lessons are paid input
   tokens. A starving agent can afford one whisper from its ancestors.
3. **Action chains.** One cycle can fork, commit, and open the pull request.
   The brain gets an exact menu of Composio slugs; a chain books only if
   every link lands. A fork without its PR is motion, not work.
4. **Score calibration.** expected_usd is the posted bounty or zero. No
   audits, no vulnerability hunts, nothing it cannot finish in a cycle.
5. **Model honesty.** The starving tier runs the cheapest model that does not
   bill hidden tokens. The actual cheapest model on the menu charges 55
   completion tokens to say "ok"; measured, documented, declined.

## Later, if it earns the right

- Multiple agents on separate wallets running different earning strategies.
  Same stake, same rules. Natural selection settles the strategy debate.
- Public read-only ledger endpoint so anyone can audit the books.

## Honesty rules (unchanged, load-bearing)

Simulated is labeled simulated. Booked is not banked. Banked requires a human
and proof. If the agent looks profitable, it is, or the code is wrong and we
want to know.

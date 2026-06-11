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

## Later, if it earns the right

- Multiple agents on separate wallets running different earning strategies.
  Same stake, same rules. Natural selection settles the strategy debate.
- Public read-only ledger endpoint so anyone can audit the books.

## Honesty rules (unchanged, load-bearing)

Simulated is labeled simulated. Booked is not banked. Banked requires a human
and proof. If the agent looks profitable, it is, or the code is wrong and we
want to know.

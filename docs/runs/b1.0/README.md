# b1.0: win chance pay in

**The goal:** win chance pay added on top of the unchanged pay table, about a third of the total, so that he has a reason to win and items have a value that
depends on the game, without losing the fighting skills and item play of v0.6.0. The series' plan: [B1_PLAN.md](../../design/B1_PLAN.md).

**Passes when**, against v0.6.0's end: at least 52% over the last four checks, frags at least 1.6 a match-minute, rail in hand at least 0.18, entropy at most 1.82, and the owner's play test.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [b1.0a](b1.0a/CARD.md) | v0.6.0's end, its own optimizer | `WIN_ADD` 0 → 0.15 → 0.33 | 2026-10-31 10:56 to 21:00, update 160 | success (owner): ~55% against v0.6.0's end at full win pay |

## Next, depending on b1.0a

| If | Then |
|---|---|
| it passes | b1.1: the pull toward level and the brain's old belief out; may start the night of 10-31 if the owner ends b1.0a early |
| the win pay does nothing | b1.0b at `WIN_ADD` 0.5 |
| he slides | v0.6.0 on flat pay for 12 h, to rule out run length before changing the pay |

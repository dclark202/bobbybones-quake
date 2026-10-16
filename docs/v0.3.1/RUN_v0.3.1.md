# v0.3.1 on one page (the training manifest)

*Rewritten 2026-10-15 20:45 on the owner's word: "update the v0.3.1 manifest to include only the new python memory stuff
together with the pay changes". v0.3.1 is v0.3 resumed from its 18:00 stop with two changes: the new pay and the faster
learning step. Everything else planned for v0.3.1 (the believed stack, hunt, the legs inside the network, rocket jumps,
the rail) is built beside it and comes in a later run: [MANIFEST_v0.3.1.md](MANIFEST_v0.3.1.md) sections 6 and 6b.
Status: **started 2026-10-15 20:53 on the owner's go** ("Start the run"), to 16:00 Friday. Folder: `duel_gru_v0_3_1`. The plans in full: [PROPOSAL_v0.3.1.md](PROPOSAL_v0.3.1.md).*

## Why

The owner's play test of v0.3 (2026-10-15): "a bot that doesn't want to fight ... he runs away from me." Keeping a stack
and holding the big weapons paid him up to two frags a minute while alive; the speed pay on his item trips another 0.7.
Fleeing kept that income; a fight risked it.

## The pay (the owner's table, 2026-10-15 evening, adjusted after a look at its equilibrium: the owner, "I like your changes")

| What | Pay | Was in v0.3 |
|---|---|---|
| Frag / death | +1 / −1 | the same |
| Damage dealt / taken | +0.0055 / −0.0045 a point, 1.2:1 (armor's soak at full cost) | +0.005 / −0.005, armor's soak a third |
| Stack differential (his health+armor − the enemy's) | up to ±0.7 a minute, clamped at ±200, zero-sum | none |
| Mega, red armor / yellow armor picked up | +0.25 / +0.12 flat, the enemy −0.25 / −0.12 | 0.0075 a point gained; the enemy's mega or red −half |
| Other items (bubbles, shards, green armor, small weapons) | nothing | 0.0075 a point; a new weapon 0.19 |
| First big weapon of a life (rockets, lightning, rail) | +0.10 once | 0.19 each new weapon |
| Without a big weapon | −0.25 a minute, capped | −0.5 a minute, growing to −2 |
| Keeping a stack / holding big weapons / being low | nothing | up to +1, +1, −1 a minute |
| Speed on his item trips, in games | nothing | up to 0.5 a second at 480 (0.7 a minute in v0.3) |
| Travel toward his chosen item | nothing | worth the item, paid along the way |
| The item lesson (the item rule) | fades 2.0 → 0.1 over the first 6 hours, then holds | 2.0, never faded |

Knowing where the enemy is: 0.25 a minute (was 0.5). Unchanged: the hop bonus, the shot price, the blind-fire costs, the pay in
movement practice (speed pay 0.3 there), the openings, the guessing game, the entropy bonus.

## The faster learning step (B-237)

His memory in the learning step by the library's GRU over whole sequences (`--fast-gru 1`): the same loss and gradients
to rounding (proven on v0.3's network), about 20% faster an update. Its first real run: the first updates are watched.

## What it starts from, and the control

v0.3's 18:00 save (update 218; 59.2% against v0.2 in the final evaluation). Aim level 3 from now on. His league: v0.3's
last eight snapshots. **The control is v0.3's end**: in a quarter of his games and in every check.

## How it is judged and watched

- Every tenth update (about an hour): 160 ten-minute whole games against v0.3's end on ten maps, at aim level 3.
- **Collapse watch** at every save, against v0.3's last ten updates: rockets, rail or lightning in hand under half; mega
  and red pickups under 60%; frags a minute under 60%; mega and red intentions under half; a stall of 15 minutes.
- **Stop rules**: under 47% at the first check, two checks under 45%, or three falling. Written down by the watcher;
  Claude stops the run and tells the owner.
- Runs to **16:00 Friday 2026-10-16**. A line a check at night, reports at **06:30** and **12:00**, the report at the end.
- Promoted only on the owner's word and only if it beats the control.

## Built beside it, proposed at the 06:30 report (the owner, 2026-10-15 20:50)

His legs learning from games (B-253 stage b, at a quarter of the rate) and the rocket jumps (B-252: the check against the
real game, then the runs) are built and proven tonight beside the run; at 06:30 each is proposed to join at a restart
from a save if the pay change looks healthy, its ten-update test against the control first. Pay is read as the
equilibrium it settles to in self-play (the owner, 2026-10-15): the zero-sum parts beside the parts both copies gain from.

# Proposal: v0.5.1 pays by win chance only (before the strategy head)

*2026-10-26 night. For review. The owner's idea: "a lot of his current behavior is pathological. he does what gives him reward,
and ends up not fighting when he should be and doing weird things. would drifting to pay by win chance BEFORE opening the
strategy layer be useful?" Agreed with the owner: yes; the head moves to v0.5.2. Numbers are from the running v0.5.0 unless
marked.*

## 1. Why, and why before the head

- The strategy head optimises whatever pay he is given. In v0.4.4 it took the shaped pay at its word and turned it into spawn
  camping (lightning gun as his target 19% -> 43% as the head opened; post-mortem: `docs/v0.5.0/POSTMORTEM_v0.4.3_v0.4.4.md`).
  Opening it on win-chance pay means it learns strategy for winning, not for collecting bribes.
- What he is paid now, in games, per player-minute (v0.5.0, the last update's pay terms):

| Pay | Per player-minute | What it rewards |
|---|---|---|
| Damage dealt / taken | +0.80 / -0.86 | trading damage, whether or not it wins the fight |
| Frag / death | +0.42 / -0.43 | the only part the built `WIN_PAY` switch replaces |
| Speed | +0.50 | running about (phased out at v0.5.0's end, 04:00-06:05 Tue) |
| View jerk (cost) | -0.23 | a smooth mouse command (redundant: see 5) |
| Target switch (cost) | -0.13 | keeping a target: works against variety |
| Shot price (cost) | -0.13 | ammunition sense |
| Weapon switch (cost) | -0.09 | keeping a weapon: works against weapon variety |
| Fire toggle (cost) | -0.03 | holding fire |
| Items (mega, red, yellow; zero-sum) | about +0.05 | taking them |
| About a dozen more | 0 to 0.03 each | stack lead and keep, big weapons in order, knowledge, watching the right spot, far rail, height, pre-aim, blind fire, drops, way claw |

  Frags are only about a quarter of what he is paid in a fight. The damage trade, the speed pay and the costs dominate:
  the likely cause of "not fighting when he should and doing weird things".

## 2. The mechanism (branch `v051`, being built; every part live and off by default, off = v0.5.0 bit for bit)

| Setting | What it does |
|---|---|
| `WIN_W` 0 -> 1 | In whole games, late rounds and pro mid-game starts: a frame pays (1 - w) x (frag/death + damage) + w x `WIN_GAIN` x (the change in his chance of winning). The chance comes from `sim/win_chance.json` (the pros' 257 games, by lead and time left); zero-sum between the seats. |
| `WIN_GAIN` | Scales the win part so his total pay keeps its size. The shadow measure says the win part is about 0.53x the combat pay it replaces, so about 1.9 (to be confirmed by the build's measurement). The owner: keep the total about what it is now. |
| `FADE_V` 0 -> 1 | Every other pay in those rounds x (1 - v): items (both sides and the long value), weapon and target switch, shot price, view jerk, fire toggle and every small term above. |
| Fix | The last frame of an overtime period read 120 s left instead of 0 (known bug, never run). |

At `WIN_W` = 1 and `FADE_V` = 1 a game's frame pays **only** the change in his chance of winning (a test asserts every other
part is exactly 0).

**Equilibrium:** each frame pays the change in one function of the game's state, so a game's pay sums to `WIN_GAIN` x
`WIN_SCALE` x (result - chance at the start) whatever happened on the way. It is zero-sum and nothing can be pumped. The
self-play optimum is to win. On the way, the blended pays are all zero-sum too (damage at 1.0, frags, items) except the self
costs, which fade.

## 3. Schedule (Tuesday, from v0.5.0's end)

| Time | `WIN_W` (combat -> win chance) | `FADE_V` (everything else) |
|---|---|---|
| 07:00 | 0 (identical to v0.5.0) | 0 |
| 07:40 -> 10:20 | 0.1 -> 0.5, +0.1 every 40 min | 0 |
| 11:00 | 0.6 | 0.125 |
| 11:40 -> 13:40 | 0.7 -> 1.0 | 0.25 -> 0.625 |
| 14:20 -> 15:40 | 1.0 | 0.75 -> 1.0 |
| **15:40 on** | **win chance only** | **all other game pay gone** |
| Evening, overnight | the owner's play test; trains on it to Wed noon; then v0.5.2 (the head) | |

- The owner chose two overlapping fades over one-at-a-time ("fade damage and frags together then start to fade items and
  swaps during that fade").
- 40-minute steps (owner: "we can slow it down further if that seems safer"): the biggest pay change he has had. A step is
  about 9 updates; with the behaviour panel every 10 updates each step is seen before the next one, and the checks every 20
  updates see every second step. 25-minute steps would let a problem run three or four steps deep before a check saw it.

## 4. Gates and monitoring

- **The behaviour panel every 10 updates during the fades** (every 20 otherwise), side by side with v0.4.2b's end (fixed
  control). A red holds the ramp; the same red twice steps it back one step. Its triggers: targets, camping near spawns,
  roaming, hunting the spot-holder, mega and red share, rockets in hand at mid range, passive (self-play frags a minute).
- **Added for v0.5.1:** weapon in hand against the pros (the owner: "the biggest thing to watch for is that he's using weapons
  with the right overall frequency"); weapon switches a minute (they will rise as the switch cost goes); his hand against the
  pros (view acceleration rms, reversals a second, power above 4 Hz: pros 2,455 / 4.6 / 0.29).
- **Checks:** 160 games every 20 updates against v0.4.2b's end, reported, not a gate (the owner: how he feels to play matters
  more than the win rate). The collapse guard stays: a check under 15%, or two in a row under 25%, stops the run.

## 5. The view-jerk cost

A human limit belongs in his ability, not in his pay (owner). The ability already exists: `HAND_BAND` (on in the run), a filter
from his mouse command to his view, sized on 2026-10-20 to the pros' demos while firing lightning (view acceleration rms 4,600 ->
2,610 deg/s2 against the pros' 2,455; reversals 8.3 -> 4.8 a second against 4.6; power above 4 Hz 0.43 -> 0.27 against 0.29),
with the flick cap (1,200 deg/s), mouse inertia, a reversal delay and hand noise that grows with turn speed. The jerk cost acts on
his command, not on what his view can do: redundant. It fades with `FADE_V`. If the hand numbers then pass the pros', the filter
is tightened (an ability limit), not a cost brought back.

## 6. Risks

1. **Credit for items and stack.** The win table knows only score and time, not stack: a mega pays only through the frags it
   leads to, so item control may sag while his value learns it. Mitigations: the item rule (a lesson for which item to go for,
   not a pay) stays on through v0.5.1; the items fade only from the midpoint; the panel's mega and red share gate the ramp.
2. **The learned win-value readout is not calibrated yet** (shadow: correlation about 0). Nothing relies on it: the PPO critic
   learns the returns of whatever is paid.
3. **The signal changes shape**: most of the win part comes at frags, with a trickle as the clock runs; a lead late is worth
   more than early. Expect a dip; bounded dips are the standing rule (20-30 updates).
4. **Self costs gone**: switching becomes free. The finger limits (key rate, switch time) bound it; the panel watches switches
   a minute.
5. **Practice rounds keep their own pay** (no game to win there): the 10% jump runs (the owner's jump focus: Aerowalk's red
   armor, Campgrounds b2r). The owner asked whether to drop them; proposal: keep them through v0.5.1 (one change at a time),
   then check whether he still takes those jumps in games on win pay alone; drop them in v0.5.2 if he does.

## 7. What is still not win chance at the end of v0.5.1

- Practice rounds' own pay (above), outside games.
- Lessons that are not pay: the item rule's suggestion of a target (faded with the head in v0.5.2), the brain's predictions
  and its people lesson. They shape what he notices and chooses, not what he is paid.

## 8. Before the start (Tue 07:00)

- The build on branch `v051`: identity off = v0.5.0 bit for bit (both simulator modules); a game's win part sums to its result;
  the blends scale exactly; at full fade a game frame pays only the win part; live settings accepted and range-checked; the
  overtime fix; the size measurement for `WIN_GAIN`.
- The standing rule for a new setup: the exact command on a scratch copy for 10 updates, then a check against the control and
  the behaviour panel.
- The ramp script (the steps above, by time; holds and step-backs on the panel's reds).

## 9. Questions for the review

1. Is 40 minutes a step enough (the owner is happy to go slower), or should the win blend go slower still?
2. Should `WIN_GAIN` match the total pay size (about 1.9), or the frag pay only (about 1.2), leaving the entropy bonus
   relatively larger?
3. Any pay term in games that the fade misses? (The build lists every term in `PAY_TERMS` and what it does with it.)
4. Is a win table by score and time alone enough, or should the chance include the stack (a learned or tabled stack term)
   before the item pay goes?

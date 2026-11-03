# 1.4b: every hand-written piece on his target choice out, one after the other, in one run of about 24 hours

*2026-11-03 (owner): the schedule of 1.3b and 1.4 ("Please sketch out the schedule for B1.3 and B1.4 under the proposed changes"; "Make sure 1.3b and 1.4b,c are written up in cards"); then "Can we combine 1.4b & c into 'one run'"; "1.3b starts this evening and runs overnight, then 1.4b starts early in the morning and probably runs for 24 hrs". The family's goal stands: "B1.4 - fade OLD rules out"; combat, item and win pay stay ("I view the win pay as the correction factor on top of those"). Five fades, opened one after the other, each tied to the checks. Starts only if [1.3b](../../b1.3/1.3b/CARD.md) passes. 1.4c's card is merged into this one ([1.4c](../1.4c/CARD.md)). The family: [README](../README.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In plain words

The network does not change: the same three GRUs, the same target layer (the hands' rows on the fast memory plus the head's part on the slow memory). What comes out are the hand-written pieces around his target choice: a rule it is taught to copy, two pay terms that tilt it toward item runs, a rule that rewrites one kind of choice, and the lock that holds a choice for 8 s whatever the scores say. At the end his target choice is one learned layer, taught only by what wins games.

## The owner's page

| | |
|---|---|
| Started from | **not started** · 1.3b's end with its optimizer (`keep/policy_end_13b.pt`), if it passes its card's marks |
| Run | `duel_gru_1_4b` |
| Length | **about 24 hours** (`--minutes 1440`; owner, 11-03); about 290 updates at 5 minutes an update |
| How his target is chosen | as at 1.3b's end: one set of scores, the hands' rows plus the head's part, one lesson, the head's credit; the L2 on the head's part and the cap on the hands' stay |
| Combat, item and win pay | unchanged |
| League, checks | anchors: 1.3b's end, b1.2d's end, b1.1, v0.6.0's end. 200 games every 20 updates against 1.3b's end, every fourth against b1.2d's end (the servers' network); read against the zero point. The head blanked at each step's end. The panel. Never stopped |
| Cores | as 1.3b |
| Kept | the save at each step's end with its optimizer (`keep/policy_step<n>_14b.pt`), the end (`keep/policy_end_14b.pt`) |

## The schedule (one ramp; a step opens only after the one before has held a check)

| Updates | Step | Dial | Where it stands |
|---|---|---|---|
| 0 to 10 | nothing (as 1.3b's end) | | |
| 10 to 50 | **1. the item rule's lesson out** | `INTENT_TEACH_W` 1 → 0 (live; a factor on the rule's weight, its floor included) | ✅ live already |
| 60 to 100 | **2. the speed pay the same for every target** (the enemy and the holding places too), and no claw-back when he abandons a trip | a new live dial, 0 → 1, between today's rule and the new one | ⏳ `duel_env.py`: the trip mask (`:12955`, `:12983`, `:13000`) and the claw-back (`:12958`) behind the dial |
| 110 to 140 | **3. the switch cost** 0.02 → 0 | `INTENT_SWITCH` made live | ⏳ (a constant at `duel_env.py:458` today) |
| 150 to 180 | **4. the weapon rule out**: a rocket launcher, railgun or lightning gun he holds with ammunition is no longer turned into "nothing" when he chooses it | `WEAPON_FREE` as a live share 1 → 0 | ⏳ (a `PLAY_VAR` today: set at the start, not live) |
| 190 to 270 | **5. the lock outside contact**, 8 s → 0 (slowest: in b1.1a freedom without a chooser became flicker) | `INTENT_HOLD` (live) | ✅ live; the owner's lock review of 11-03 evening ❓ |
| 270 to the end | settles | | |

Gates for each step: hold while a check reads under 50%; step back 10 updates if under 45% or two checks under 50% (read against the zero point); a dip lasts 20 to 30 updates at most. A hold delays every later step: the end slips about 1.5 hours a hold.

**Not on this card:** the way pay (`INTENT_SEEK_W`) is already zero (`intent_seek × INTENT_VALUE × item_reward`, `--item-reward` 0; the review, finding 8). The dead rule code (the silencers, the weight-0 teachers) can go at the start once proven bit-identical ⏳.

## Before the start

| Step | Where it stands |
|---|---|
| 1.3b passed its marks | ❓ (the morning of 11-04) |
| The three new live dials (speed pay for every target, the switch cost, the weapon rule), each with an identity check (the dial at today's value: inputs and pay the same to the bit). Built in a worktree of their own while 1.3b runs (its checks re-import `duel_env.py` every hour), merged after 1.3b ends | ⏳ |
| `make_files.py` (1.3b's command), settings check against 1.3b's; `ramp_14b.py` (the five steps, the gates); `start.ps1` | ⏳ |
| 10 updates on a scratch copy | ⏳ |
| The owner's lock review; his go | ❓ |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.3b's end | level or better at each step's end and at the end (against the zero point) |
| Against b1.2d's end | better at the end |
| The enemy's share of his targets | up after step 2 ("he needs to fight more") |
| Items a minute, stack at fights, the mega and the red armor taken | hold after step 1 (the rule carried item timing) |
| Weapons fetched that he already had | about 0 by itself after step 4 |
| Target changes a minute, targets reached, trips abandoned | no flicker after steps 3 and 5 |
| The two parts' sizes (`head2.hands`, `raw`) | bounded |
| No spawn camping, no holding a spot all game | the panel |
| The owner's play test | |

## The equilibrium

1. **The rule's lesson out.** The choice is learnt from pay alone; both copies are paid the same way in self-play, so an item is chosen when its pay (the table, the stack it gives in fights, the win part) beats a fight. The head's part was correcting the rule; with the rule gone the rows move toward the pay themselves and the head's correction shrinks (its L2 pulls it back as the need goes).
2. **Speed pay the same for every target.** Today speed is paid only on the way to an item (+0.32 a player-minute, a third of the frag pay; the review, finding 2). Paid alike, it no longer tilts the choice; both copies gain it alike. On the way: more hunting when nobody is in view.
3. **No switch cost.** Outside contact the lock still limits changes; inside contact the cost was the price of re-deciding. The risk is flicker, which the counters show.
4. **The weapon rule out.** Fetching a weapon he holds pays nothing and costs time, for both copies alike: the chooser learns not to.
5. **The lock out of fights' gaps.** A choice holds as long as the head keeps choosing it; the equilibrium is his own rhythm of re-deciding, paid by what the choices lead to.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The order (rule, speed pay, switch cost, weapon rule, lock) | assumed: the rule first (the head's correction depends on it), the lock last (it decides when a choice counts) | the lock first (b1.1a's order) | each step's checks |
| 30 to 80 updates a step | assumed pace; the owner: "too timid" (11-02) | shorter steps | checks |
| The switch cost (step 3) and the lock (step 5) both limit flicker | two steps on one risk | one of them kept | target changes a minute |
| The rule carried item timing | | the head's slow memory and the item timers are its inputs | the mega and red armor shares |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |
| The checks' zero point | from 1.3b's measure | | every gate |

## Changes on the fly

| Time | Change | Why |
|---|---|---|

## The result

Not started.

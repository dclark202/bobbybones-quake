# 1.7a postmortem

Ended on the owner's word 2026-11-06 19:15 at update 246. **1.7a's result is the save of update 90** (owner, 11-06: "save that as 1.7a;
update 90. That has JUST the choice redesign and no rule redesign. We can build from there"): the keep choice alone (its share 0.975), the
order never asked; 63.0% against 1.6a's end. It is `keep/policy_end_17a.pt` with `keep/opt_end_17a.pt`; the last save (update 240, 18:35)
is kept as `keep/policy_u240_17a.pt` with `opt_u240_17a.pt`. Every save from update 10 on is in `keep/` (`policy_110.pt`,
`policy_130.pt`, ...). Numbers from `watch/watch.log`, `watch/ramp.log` and `watch/behaviour.jsonl`, averaged over five updates.

## In short

| Part | Worked? | The evidence |
|---|---|---|
| The live-file fix | ✅ | the file applied on every read, no firing cost, the ramp's dials played as written, all run |
| The keep choice (updates 10 to 90) | ✅ for games, ❌ for flicker | 50.5% → **63–64%** against 1.6a's end by updates 90 to 130; the decision became the head's; but trips 25 → 58 a player-minute and targets reached 24% → 11% by update 90, the card's own sign of flicker |
| The brain's pass odds | ✅ | Brier 0.080 against the base rate's 0.186 from update 90 to the end |
| The order (kinds, pointer, token) | ❌ | an order other than the target: 2.1% of readings at update 100, 0.02% at the end: learnt away |
| The pointer on his targets (`PADD` 0.3) | ❓ likely harmful | its weights on his state grew 0 → 4.1; the slide began as it opened |
| The fire push | ❓ no effect seen | the head's scores on the trigger 0.42, its step tiny; rockets at mid range stayed under the control's (0.20 against 0.28) all run, as before it opened |
| Rule 11 (the sums regularized) | ✅ | no part over 40 (the largest 16.8); no blow-up |
| Against b1.2d's end | ✅ held | 91.5% (update 70), 94.5% (150), 93.5% (230) |

**The run's net result: level with 1.6a's end at its end (49.5% at update 210).** Its best saves are updates 110 to 130 (64%, 63%).

## The checks

| Update | Against | Record | Win rate | What was open |
|---|---|---|---|---|
| 10 | 1.6a's end | 101-99 | 50.5% | nothing (the trial) |
| 30 | 1.6a's end | 103-97 | 51.5% | keep choice 0.25 |
| 50 | 1.6a's end | 107-93 | 53.5% | keep choice 0.5 |
| 70 | b1.2d's end | 183-17 | 91.5% | keep choice 0.75 |
| 90 | 1.6a's end | 126-74 | **63.0%** | keep choice 1 |
| 110 | 1.6a's end | 128-72 | **64.0%** | + order 0.25 (its token's weight ×0.0001) |
| 130 | 1.6a's end | 126-74 | **63.0%** | + order 0.5 (×0.003) |
| 150 | b1.2d's end | 189-11 | 94.5% | + order 0.75 (×0.05) |
| 170 | 1.6a's end | 113-87 | 56.5% | everything open |
| 190 | 1.6a's end | 104-96 | 52.0% | held |
| 210 | 1.6a's end | 99-101 | 49.5% | held |
| 230 | b1.2d's end | 187-13 | 93.5% | held |

The checks against 1.6a's end rose while the keep choice opened and fell while the order, the pointer and the fire push opened and
after. A check of 200 games moves about ±7 points by chance, so 63 → 49.5 is real; one map's number is not (the weakest at the end:
Blood Run 7-13, Campgrounds and Hektik 6-14).

## The keep choice

| Update | Trips a player-minute | Reached | Re-decide a reading: contact | quiet | arrived | Its pull: head's state | hands | own numbers |
|---|---|---|---|---|---|---|---|---|
| 10 | 23.9 | 24% | (the lock) | | | | | |
| 30 | 26.9 | 22% | 0.48 | 0.030 | 0.45 | 0.44 | 0.41 | 4.84 |
| 50 | 35.6 | 17% | 0.71 | 0.042 | 0.72 | 0.94 | 0.72 | 4.85 |
| 90 | 58.3 | 11% | 0.80 | 0.054 | 0.87 | 1.39 | 0.86 | 4.85 |
| 130 | 61.1 | 10% | 0.82 | 0.054 | 0.90 | 1.70 | 1.02 | 4.94 |
| 170 | 68.3 | 10% | 0.91 | 0.088 | 0.95 | 2.43 | 1.20 | 4.86 |
| 210 | 76.4 | 9% | 0.92 | 0.086 | 0.97 | 2.73 | 1.25 | 4.96 |
| 240 | 80.8 | 8% | 0.96 | 0.125 | 0.99 | 3.40 | 1.61 | 5.07 |

- **What worked:** the decision became the head's (its pull from the head's memory 0.2 → 3.4, wanted by the card), and the games won
  rose with it, to 63% at full share. Keeping a target through a fight and leaving it when the fight changes is worth games.
- **What did not:** a trip counts only a change to a different target (`sim/duel_env.py:7452`), so 81 a player-minute is a new target
  every 0.75 s, and 92% of targets are left before they are reached. The card asked for "no slide" on exactly these numbers (b1.1a's sign:
  12.6 → 20 trips, reached 40% → 21%); this went further. Re-deciding at nearly every reading in contact (0.96, five a second) is what
  the choice is for; **re-deciding out of contact with nothing heard rose 0.030 → 0.125 a reading, 14% → 49% a second**: that is drift,
  not a reaction to the fight. Until update 130 it did not cost games; after it, the slide and the quiet re-decisions grew together.
- **My mistake:** on 11-06 at 07:00 I told the owner the rising trips were expected of the keep choice. The card's own measure said
  otherwise. The quiet re-decisions were in the ramp's log every update; I did not split them out until now.

## The order

| Update | p(an order) | Chosen in 5 updates: cut off, spam, break off | Arrived | Damage a frame on the order: cut, spam, break, target |
|---|---|---|---|---|
| 100 | 2.1% | 249, 224, 550 | 51, 109, 50 | 0.13, 0.06, 0.41, 0.15 |
| 120 | 0.79% | 685, 531, 915 | 150, 238, 55 | 0.34, 0.20, 0.40, 0.15 |
| 140 | 0.28% | 339, 275, 635 | 57, 114, 47 | 0.15, 0.28, 0.42, 0.15 |
| 170 | 0.09% | 105, 297, 202 | 20, 124, 6 | 0.37, 0.29, 0.49, 0.14 |
| 200 | 0.06% | 65, 404, 151 | 9, 171, 5 | 0.48, 0.24, 0.40, 0.14 |
| 240 | 0.02% | 30, 88, 17 | 4, 44, 1 | 0.24, 0.39, 0.28, 0.15 |

(The damage a frame is not a fair comparison: an order is chosen in a fight, the target mostly out of one.)

**Why it was learnt away (most likely first):**

1. **The order was judged before the hands could carry it out.** The order's share and its token's gate opened together over updates
   90 to 170, so the hands read the order at ×0.00001 at update 90, ×0.003 at 130 and ×0.12 at 156. In those 60 updates an order moved
   his legs and his way (to the spot, looking at the point) but the hands did not know to shoot it. The build's own level check had shown
   it: "on a spam order he goes to the spot and does not fire" (HISTORY, 1.7a). The head's lesson saw orders that did not pay and pushed
   them down: p(an order) fell fastest (2.1% → 0.43%) between updates 100 and 130, while the gate was −10.8 to −7. When the hands could read
   the token there were a few hundred orders an update left to learn from, and fewer each update.
2. **No entropy bonus on the order and a start 4.5 times rarer than the pros.** A rare choice whose advantage is noisy, with nothing
   keeping it explored, drifts to zero under PPO: each time the target is drawn and pays, the others go down a little. Both were the
   design (the entropy spreads a choice over new equal choices whatever they pay: CLAUDE.md), but together they left the order nothing
   to hold it up while it could not yet pay.
3. **Break off ended at an item and its arrivals fell to 0 or 1 in five updates** from update 170: the kind that did the most damage
   a frame was the first to die.

**From AlphaStar:** AlphaStar kept a KL term to its supervised (human) policy through the whole of its reinforcement learning, not only
as a start; that is what kept rare human strategies played while the value learnt whether they paid. 1.7a used the pros' fit only as the
start. The pass odds and the pointer show the parts can learn (Brier 0.080 against 0.186); the kinds never got a fair test.

## The pointer on his targets (`PADD` 0.3) and the fire push

- The pointer's weights on his state (`op_s`) grew 0 → 4.1 and kept growing at the end; its scores, times 0.3, are added to every one
  of his 17 target scores and his ways at every reading. They change with his state each tick, so they add a moving part to the target's
  choice: a plausible cause of the quiet re-decisions that rose after update 140 (0.058 → 0.125). At `PADD` 1 the start lost 61-139;
  0.3 passed a level check at the start, before those weights grew. **Not separated from the order and the fire push**: all three opened
  together over updates 90 to 170.
- The fire push: the head's scores on the trigger rose to 0.42 with its credit at 0.5; his rockets at mid range were 0.16 to 0.21 all run
  (the control 0.28), the same before and after it opened. Nothing measured shows it doing anything, good or bad.

## What held

Big weapons owned 1.62 → 1.64; lightning in hand 0.61 → 0.67, rockets 0.23 → 0.19, rail 1%; mega and red armor 1.92 → 1.82 a minute;
speed on trips 336 → 333; weapon switches 12 to 16 a minute (the control 14.6); Aerowalk's red armor 2 to 14% of the checks' takes
(noisy, small); no part of a sum over 40; no firing cost; the settings file applied on every read.

## What to do with it (for the owner)

| | Proposal | From |
|---|---|---|
| The network to keep | ✅ the save of update 90 (owner, 11-06): the keep choice alone; 110 and 130 (64%, 63%) add only a trace of the order | the checks |
| The keep choice | keep it; hold the quiet re-decisions down: a level check of the update-130 save with `PADD` 0 against 0.3 tells whether the pointer is the cause (a side job: no run trains now) | the flicker table |
| The order, next attempt | open the hands' token **before** the order's share (the hands learn to carry out an order while the head still asks it at the start's rate), and keep the pros' fit as a KL term through the run, not only the start | AlphaStar; cause 1 and 2 above |
| One new thing per round | the order, the pointer on the targets and the fire push opened together, so the slide cannot be pinned on one | the owner's rule of 10-24 |

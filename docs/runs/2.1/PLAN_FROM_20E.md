# 2.1 from 2.0e's end: the lock out, map sense in, the head ready for more decisions

**A plan for the owner's review (2026-11-14). Nothing here is built or started.** The owner, 11-14: "I want 2.1 to handle getting the
end of 2.0e to be ready for the expanded strategy decisions, map sense, and without the 8s lock"; "build the decision network out of the
one he already has, instead of trying to copy or transfer it over"; "the 8s lock cannot come out without something that is built already
to replace it"; "the new thing has to come in before the old one can go out".

This replaces [PLAN_FROM_17A.md](PLAN_FROM_17A.md) and the 2.1a cards (the instruction as a separate chooser: 1.9a, 2.1a). What ran is in
[RUNS.md](../../RUNS.md) (#48 to #51).

## What 2.1 hands to 2.2

| | At 2.0e's end | At 2.1's end |
|---|---|---|
| Who chooses the target | the head's scores added to the hands' rows (1.3b), as now | the same sum: **nothing new chooses** |
| How long a target stands | the 8-second lock: a new draw counts only when the target is reached, gone, 8 s old, or the enemy was seen or heard in the last 2 s; one reading a second | **a learned keep choice at the head's tick (five a second)**, held by a stay value; the lock deleted |
| An arrival (the enemy in view, a place stood at) | forces a new draw every second: "hold this angle" cannot be kept | keepable: how long he holds is learnt |
| The map | nothing | the map sense learnt on his own games (what his place is worth against where he believes the enemy), read by the head |
| New decisions (cut off, spam, hold, break off) | none | none: 2.2 adds them **as rows of this same target choice**, one at a time, each after the hands can carry it out |

## Why the lock failed three times, and what is different here

| Attempt | What replaced the lock | What happened | The cause |
|---|---|---|---|
| b1.1a (#27) | nothing (the lock faded to 1 s) | trips 12.6 → 20, reached 40 → 21% | freedom with no chooser |
| 1.7a, 1.7b (#40-41) | the keep choice, learning from the head's 5-second credit | won games (63%), then drifted: quiet re-decisions 0.03 → 0.125, reached 24 → 8% | it cannot see what leaving a trip costs (a trip to the mega is 10 to 15 s); nothing prices a re-decision ([BOTS.md](../../research/BOTS.md) section 9: a learned stop with no cost stops every step) |
| 1.9a (#49) | a new chooser re-choosing every 0.2 s | 2.5% | untrained when it took the seats |

The lock does two jobs. **In contact it is already off** (one reading a second). **In quiet it is the only thing that makes him finish a
trip.** 1.7a's gain came from the first (five readings a second in a fight, keepable arrivals); its drift came from the second. So they
are handed over separately, the safe one first, and the quiet hold only to a part that has been shown to hold.

## The parts (what exists, what is new)

| Part | State | Its job in 2.1 |
|---|---|---|
| The keep choice (`sim/head2.py` `keep`, `tools/keep_init.py`, the simulator's arrivals, the share `KEEP_G`) | built and run (1.7a) | the replacement. Added at share 0 (the start plays as 2.0e's end to the bit) |
| The frozen moments (`sim/branch.py`: a moment copied into other matches, his first target forced for 1 s, what the next 8 s or 30 s brought) | built; ran in 2.1a | the stay value's lesson: the same moment played with the target **kept** and with a **new draw** |
| The appraisals (`sim/appraise.py`: for a target from a moment, the damage dealt and taken, who dies, the big item, the change of his standing) | built; in 2.1a they learnt nothing from 9,104 forks (R2 about 0, 240 forks an update) | the stay value is one question of theirs: keep against redraw. **This is the plan's weakest part: measured first (M1)** |
| The map sense (`sim/mapsense.py`: a shared network over a pair of places, a correction a place of each map) | built; a lesson only, nothing reads it | learns from update 0; then the head reads it |
| **New: the keep choice limited to contact and arrivals** (quiet readings stay with the lock rule) | to build (a mask in the simulator's reading) | step B: flicker is impossible by construction |
| **New: the keep choice's quiet reading from the stay value and the change signals only** (an item's clock crossing his time to get there, the belief's shift since he chose, the age; not the head's whole memory) | to build | step C: in quiet, with nothing new, there is nothing to react to |
| **New: the map sense as head inputs** (its outputs at his place and at each target's place, measured statistics, behind a shut gate) | to build | step D |

## Before any training: three measurements (no run; recorded games and forks on 2.0e's end)

| # | What | It decides |
|---|---|---|
| M1 | **The fork, keep against redraw**, on 2.0e's end and on 1.7a's update 90: at quiet moments, in contact, at arrivals, by the target's age. How often a redraw beats keeping, by how much, and how many forks it takes to tell | whether a stay value can be learnt at all, and how many forks an update it needs. It should also show 1.7a's quiet re-decisions losing win chance: if it does not, the instrument is wrong |
| M2 | **A level check with no learning**: 2.0e's end with five readings a second in contact and keepable arrivals (the keep choice's fitted start, quiet left to the lock) against 2.0e's end, 200 games | what step B is worth before it learns, and whether it moves the weapon in hand (the owner's finding on 1.7a: lightning only) |
| M3 | The map sense's skill on 2.0e's recorded games, its start file re-fitted | whether it starts from something or from zero |

## The run, in steps that open one after the other

Lengths are not set here: each step ends on its measure, reported; the owner decides when the next opens (nothing holds or steps back on
its own). A mark is kept with its optimizer at each step's end.

| Step | What opens | What plays | Its measure (reported every update) |
|---|---|---|---|
| A. Silent | the forks (keep against redraw), the stay value's lesson, the map sense's lesson | 2.0e's end with the lock; nothing new plays | the stay value's skill on held-out forks (the sign right more often than a set mark); the map sense's skill; the checks level |
| B. Contact | the keep choice's share 0 → 1, **in contact and at arrivals only** | five readings a second in a fight; holds are kept; quiet = the lock | trips and reached out of contact unchanged; the weapon in hand by range; megas and reds head to head; **a play test at its end** |
| C. Quiet | the quiet readings pass from the lock rule to the keep choice reading the stay value and the change signals; share 0 → 1 | the lock's hold fades out of his seats | quiet re-decisions a reading at or under the start's; reached not down; a check under 40% flagged at once |
| D. The lock deleted; the map | the lock's last share out; the map sense's inputs to the head, gate shut → open | everything his own | the same guards; the map inputs' health report; at the end 200 games with them blanked |

**The stay value's lesson runs to the run's end**, not only as a start: it is what holds the keep choice against the drift (AlphaStar kept
its reference through all of its learning; 1.7a used its fitted start only as a start).

## Decisions for the owner

1. **The keep choice's start is the lock made soft** (1.7a's `keep_init`: a logistic fitted to the lock's own timing). It is a start, not a
   lesson, and it is what makes share 0 identical. Rule 13 forbids a copy *lesson*; say if a fitted start is also out.
2. **If M1 shows no usable signal** (as 2.1a's appraisals): (a) more forks an update at the cost of speed; (b) a deliberation cost, a
   hand-set margin a new draw must beat (BOTS.md section 9; your call, it is a price); (c) stop at step B: contact handed over, the quiet
   hold stays the lock until something better is built.
3. **One run or two.** A to D is long (A alone needs enough forks to teach the stay value). A and B as 2.1, C and D as its second half
   after your play test of B, is the split I would make.
4. **The map sense into the head in 2.1 (step D) or as 2.2's first step.** 2.0b's lesson: 59 fast-moving inputs to the head made the target
   unstable. Here they are 2 numbers a target and enter behind a shut gate, but it is a second new thing in the same run.

## Red team

| Part | Assumed | What is known against it | Watch |
|---|---|---|---|
| The stay value can be learnt from forks | the keep-or-redraw question is simpler than ranking 17 targets | 2.1a: no skill after 9,104 forks; `branch_test.py`: one moment's branches are too noisy to rank its options | M1, before anything is built on it |
| Step B is the part of 1.7a that won | five readings in contact | 1.7a's 63% was in self-play; the owner found it lightning only. 2.0e's dodge inputs may change what a fight is worth | M2; the weapon readouts; the play test at B's end |
| The quiet hold needs no price | the stay value is the price, measured | option-critic without a cost collapses (BOTS.md 9) | quiet re-decisions every update, from update 1 of step C |
| The judge scores a fork fairly | the win chance over the trip | the judge is fitted on v0.6.0's games; an item's worth in it is by hand in part | the forks' outcomes beside the pay table's |
| The map sense helps as inputs | 2 numbers a target | 2.0b fell to 27% on per-target inputs | gate opened slowly; the blank test |
| Forks cost training speed | small | 2.1a ran about 7.8 minutes an update with them | minutes an update, from step A |
| The self-play checks | a win over 2.0e's end means better | they reward the lightning equilibrium | the owner's play test at B and at the end |

## Research check (hard rule 14)

1. **The game.** No mechanic changes. The keep choice's signals (an item's clock against his time to get there) rest on the respawn times
   (mega 35 s, red 25 s: MECHANICS.md, items), which the simulator has.
2. **What wins.** Control is owning the next mega and red ([README](../../research/README.md) core 3): that needs trips that finish (the
   quiet hold) and leaving a trip when the item is lost (the change signals). Holding an angle with the rail (DUEL_STRATEGY.md, positions;
   the owner's standing ask) needs keepable arrivals. "Position, then weapon, then aim" (core 2) is what the map sense gives the head.
3. **The player's view.** The change signals are what a player has: his own timers from pickups seen or heard, a sound, where he
   believes the enemy is. The map sense's features take the enemy's place from the brain's belief; only its label is the truth, in
   hindsight.
4. **In and out of control.** A keepable hold can become camping (v0.4.3: a weapon target became "hold here"): the panel's camping and
   spawn-camping measures are read at every check. Out of control, breaking off a lost trip is the point of step C.
5. **Self-play equilibrium.** Two copies that finish trips contest the big items by timing, not by who stops flickering first. No league
   seat punishes a camper yet (2.0b's postmortem: the holder seat): named, not in 2.1.
6. **Bot precedent.** No system put an untrained chooser over trained hands; they taught it from predicted outcomes of each choice
   (BOTS.md sections 0, 13): the stay value. FTW's slow prior and FiGAR's "keep for k ticks" are the learned commitments (section 9, 13.2);
   option termination needs a cost or a reference: here the measured stay value.
7. **Rule 12.** No pro outcome is a target. The map sense's start may come from the pros' fit of the seeds (a measured fact of the maps);
   his own games adjust it.
8. **Not covered by the notes:** how long a strong player commits to a trip before giving it up.

# From 1.7a: AIM3, then the full 2.1 (draft for the owner, 2026-11-13)

A plan, not a card. Nothing is built for it, nothing runs. The owner (11-13, after 1.9a): "go back to starting from 1.7a ... the aim3
changes are good and worth continuing with, probably the first step is getting that network retrained on aim3", then "bringing in the
full plan for 2.1". Read with: [1.7a's card](../1.7/1.7a/CARD.md) and [postmortem](../1.7/1.7a/POSTMORTEM.md); 2.1's
[DESIGN.md](DESIGN.md), [RUNDOWN.md](RUNDOWN.md) and its built, never-started card [2.1a/CARD.md](2.1a/CARD.md);
[1.9a's postmortem](../1.9/1.9a/POSTMORTEM.md).

**The lightning comparison** ([../../design/LG_REAL_VS_SIM.md](../../design/LG_REAL_VS_SIM.md)): the simulator does not give him a
better lightning than the game (33.8% real, 37.5% simulated, close at every distance). The gap is the opponent: people hit him 43% at
200-600 units against his 29-39%, and his self-play copies are as easy to track as he is. Nothing in the simulator's lightning to fix
before step 1; how hard he and his copies are to hit is a separate lever (proposals there).

## What 1.7a's update 90 is (from its card)

| | |
|---|---|
| His target | one choice of 17 (nothing, the items, the weapons, the enemy, the holding places): the hands' rows plus the head's scores (1.3b's), learnt by the head's own lesson (`H2_PG` 1) |
| Keeping it | **the keep choice**, five times a second at the head's tick: keep, or re-decide; an arrival (the enemy in view, a holding place) keepable. It replaced the 8-second lock over updates 10 to 90; at the update-90 save its share was 0.975, so the lock rule still owned about 2.5% of seconds |
| The combat order (kind, pointer over cut-off places, spam points and ways out, its token for the hands, the head's fire push) | built in and **never asked** at update 90 (`CMB_G` 0, `PADD` 0, `FADD` 0, its token shut). It opened from update 90 and was learnt away (2.1% to 0.02% of readings) while the checks fell 63% to 49.5% |
| The brain's pass odds | trained: the odds the enemy passes a place in 1, 2, 4 s, Brier 0.080 against a base rate of 0.186 |
| Hand-built rules on his target | none left: the item teacher and the speed pay went out in 1.6a, the lock in 1.7a itself. No firing cost |
| Pay | the table (damage 0.0055 dealt, 0.8 taken, items, frags) + the win part (`WIN_ADD` 0.33); far-rail pay 0.25 at the time |
| Aim, inputs | AIM2 (the pros' mean); the old input list, 990 columns. **It plays on a server**: it was play-tested locally on 11-06 (image `qlbot:17a`) |
| Result | 63.0% against 1.6a's end; 91.5% against b1.2d's end; 1.8a under AIM3 reached only 40.5% against it (both seats under AIM3) |

**Its faults, measured:**
- **The keep choice was already drifting at update 90:** trips (target changes) rose from 24 to 58 a player-minute, targets reached fell
  from 24% to 11%, and quiet re-decisions (no contact, nothing heard) were 0.054 a reading, about 24% a second. Training on, it went to
  81 trips and 0.125 (1.7a by update 240), and 1.7b drifted the same way. The games held until update 130.
- The lightning in his hand most of his time in view.
- His rockets point behind a crossing enemy (2.1's rundown, finding 4).

## Step 1: 1.7a's update 90 under AIM3

| | |
|---|---|
| The one change | AIM3, ramped over updates 0 to 30 to its end values (as 1.8a's first 30) |
| Kept | everything else as update 90 has it: the pay table, the win part, the head's target choice and its lesson, the keep choice, the combat order shut |
| Set at the start | the keep choice's share to 1: the lock's last 2.5% out, so it never returns (rule 13). The far-rail pay at 0.1 (your 11-12 order: "set it to there from the beginning") |
| Checks | every 20 updates, 200 games, against 1.7a's update 90, both seats under AIM3; every fourth against 1.8a's end |
| Done when | level with or above update 90 under AIM3 over two checks in a row. That network is the control for step 2 |
| Read every check | the keep choice's trips, targets reached and quiet re-decisions (the 1.7a flicker); the lightning in hand and in view by range; the rail owned; the aim error tables against the pros' (readouts, rule 12) |

**Why it can still fail: 2.0c was this step with the damage pay also lowered** (0.0055 to 0.002) and fell to 35.5% / 39.5% at updates
50 / 90. Leaving the damage pay alone tells the two apart. If it falls the same way, AIM3 costs him under 1.7a's head, and we stop
and look before step 2.

**Open for you (step 1):**
1. **The keep choice while AIM3 trains:** frozen (as 1.7c froze it: the flicker can't grow, AIM3 is the only thing that moves), or
   training on with its drift flagged at each check? My recommendation is frozen. It goes back to learning in step 2, under the
   instruction.
2. **Stay on 1.7a's own input list (990) for step 1?** Then step 1's network goes on a server for you to play as it is, with no
   plugin work. It's converted to list 21 at step 2's start (the converters are proved identity). Converting first means no server
   until the plugins read list 21. My recommendation is to stay on 990.
3. **The damage pay:** 1.7a's (0.0055 dealt, 0.8 taken), or 1.8a's 0.005 zero-sum? The second is a second change.
4. The length: 30 updates of ramp, then until two checks are level, about 60 to 100 updates.

## Step 2: 2.1 in full, from step 1's end

2.1a's card ([2.1a/CARD.md](2.1a/CARD.md)), built and tested on 1.8a's update 50, moved to step 1's end. **The difference from 1.9a:**
1.9a was 2.1 with the parts that teach the head's choice before it plays left out (`--branch-p 0`, `--ins-teach 0`, no drills).
Those parts are the "learn silently" for the choosing itself. 2.1a has all of them.

| Stage | Updates (2.1a's) | What | Opens |
|---|---|---|---|
| 0, the start | 0 | list 21; the instruction's parts at zero; **1.7a's combat order removed** (never used, superseded by the instruction's cut off, spam and break off: dead weight); the pass odds kept as a readout the instruction's candidates can read | `same`: 0 actions differ |
| I, silent | 0 to 60 | the drills (each verb from a state where it can pay); the frozen moments (a moment copied, each option played out, the outcome kept); the appraisals learn what each instruction brings; **the head's choice learns on every seat from those outcomes, playing none**; the instruction's token opens in the hands | `DRILL_INS_P`, `DRILL_INS_RATE`, `BRANCH_P`, `INS_GATE` 0-30 |
| II, blend in | 60 to 110 | the head's share of his seats, 0 to 1: its instruction every 0.2 s (verb, place, point, weapon) | `INS_G` |
| III, its own pay | 110 to 160 | the pay on its own played choices, by the win chance alone | `H2_INS_PG` |
| IV | 160 to 200, held to 220 | the strategy inputs out of the hands | `SFADE` |

The pay: the hands keep the table and their share of the win pay (zoning shots; your 11-12 word). The head is paid by the win chance
alone, never the table.

**From 1.9a:**
- **The share opens on a measure, not just the clock.** You set the marks at the go (for example, the head's choice under an entropy
  mark, order changes under 1 a second, bound-weapon changes under 20 a minute on the shadow seats). The ramp reports when they are
  met. It never holds by itself (rule 6): if they are not met by update 60, it's your call.
- **The items' race does not pay the head** until its noise is measured below the judge's own part on recorded games.
- **The flag code is tested on a real record with played seats.** A crashed flag thread stops the ramp loudly, and every check line
  carries its own MAJOR mark. My monitor runs to the end of the run with no gap.

**To build for this start:** 2.1's converter (`tools/head21_init.py`) was built for 1.8a, which has no combat order. It needs the
order's removal and a `same` test on a 1.7a-line network. The rest of 2.1a's parts are built and tested.

**Open for you (step 2):**
5. **Commitment under the instruction.** 2.1a redraws a standing instruction after one second (`ins_redo`): a fixed, hand-set hold. 1.7a
   has the learned alternative already: the keep choice, re-read as "keep or drop the head's instruction" instead of its target. That
   is not built for instructions, and it is the part that flickered. Which one?
6. **The head's lesson in stage I is "toward the appraisals' order".** The appraisals are its own forecasts from its own frozen moments,
   not an old rule. But it is a teaching target, so I'm putting it to you under rule 13. The alternative, the pay on its shadow choices
   alone, is what 1.9a showed to be too weak.
7. **The binding weapon** (`INS_BIND`): binding from stage II, or opened later than the share? In 1.9a it flipped his weapon up to 107
   times a minute on a choice that hadn't learnt.

## Not in either step

- **A server for a list-21 network:** the plugins and `sim/export_duel.py` don't read list 21 yet. That's wanted before step 2's head
  plays people.
- The map sense as a part of the network, the yellows in "who takes it next", the latency by input group: as 2.1a has them.
- Opponent adaptation (later, your 11-11 word).

## The controls

| Step | Checked against | The long-term control |
|---|---|---|
| 1 | 1.7a u90 (both seats under AIM3) | 1.8a end |
| 2 | step 1's end | 1.7a u90 |

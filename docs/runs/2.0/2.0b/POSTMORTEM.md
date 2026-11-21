# 2.0b: postmortem, with 2.0a's, and how to come at control again (2026-11-10)

**Run**: `duel_gru_2_0b`, from 2.0a's end, 2026-11-09 21:09 to 2026-11-10 07:21, 107 updates. Stopped on the owner's word ("You can
terminate the run. Do a postmortem on it though, because I believe this is the right way forward"). The end kept is the update-100
save: `keep/policy_end_20b.pt` with `keep/opt_end_20b.pt`. No stall; every dial played as written. The card: [CARD.md](CARD.md).

## What happened

| Update | Against | Record | Win rate | Open at that save |
|---|---|---|---|---|
| 10 | 1.7a's update 90 | 81-119 | 40.5% | the readout only |
| 30 | 1.7a's update 90 | 70-130 | 35.0% | the readout only |
| 50 | 1.7a's update 90 | 81-119 | 40.5% | the inputs 60% |
| 70 | 1.6a's end | 73-127 | 36.5% | the inputs full, the pay 0.0001 |
| 70 (postmortem arm) | 1.7a's update 90 | 60-140 | **30.0%** | the same save, played after the stop |
| 90 | 1.7a's update 90 | 54-146 | **27.0%** | the inputs full, the pay 0.00036 |
| 90, the inputs shut in play (arm) | 1.7a's update 90 | 66-134 | 33.0% | `SPACE_GATE=0` in the games only |

2.0a's end read 42% against the same control. A check's noise is about 3.5 points.

| Training games, every seat | Update 20 | 60 | 100 | 107 | The pros |
|---|---|---|---|---|---|
| under a threat over 20 damage a second | 16.7% | 16.4% | 15.8% | 15.2% | 8% |
| the edge under −10 | 7.5% | 7.1% | 6.9% | 6.7% | |
| frags a match-minute | 2.28 | 2.00 | 1.83 | 1.87 | |
| the keep choice's quiet re-decisions a reading | 0.055 | 0.060 | 0.107 | 0.111 | |
| re-decisions on a heard enemy | 0.13 | 0.17 | 0.27 | 0.28 | |
| trips a player-minute / reached | 80 / 0.078 | 85 / 0.085 | 91 / 0.067 | 90 / 0.067 | |

The readout's skill at the end: the threat on him 0.77, what he puts 0.75, the map's cover 0.74, the zones 0.66.

## The findings

1. **He lost by the big items, not by where he stood.** The checks' games, head to head (200 games, he / the control):

   | | megas | reds | fights he enters outstacked / the control |
   |---|---|---|---|
   | 2.0a update 10 | 1314 / 1327 | 1751 / 1672 | 1899 / 1851 |
   | 2.0a update 90 | 1231 / 1364 | 1451 / 1781 | 2187 / 1704 |
   | 2.0b update 10 | 1291 / 1419 | 1571 / 1690 | 2146 / 1796 |
   | 2.0b update 50 | 1186 / 1492 | 1464 / 1881 | 2269 / 1651 |
   | 2.0b update 90 | **980 / 1713** | **1361 / 2033** | **2424 / 1388** |

   The stack decides a fight (measured: 88% of his decided fights by the stack alone), and across both runs he gave the stack away.
   Self-play cannot see this: there somebody always takes the item, so the pickups a player-minute never moved (mega 0.8, red 1.0).
2. **The inputs did it, not the pay.** The fall is between updates 50 and 70 (40.5% to 30.0% against the same control), while the inputs
   went from 60% to fully open and the pay was 0.2% of the pay's size. So **the pay by the place was never tested**: it was at its end
   value for seven updates, on a network that was already losing.
3. **Most of the harm is in the weights.** Update 90 with the inputs shut in play reads 33.0% against 27.0% open: six points come back,
   about seven do not.
4. **How the inputs hurt: his target became unstable.** The 51 per-target numbers change on every frame with his belief of the enemy,
   and they feed the head and the keep choice. Out of contact he re-decided twice as often, on a sound two and a half times as often;
   he started more trips and finished fewer. A network that drops its item run when the belief twitches loses the item to one that
   does not. This is 1.7a's lesson again (the order was learnt away the same way), and I did not red-team it.
5. **What the inputs bought: under two points** of his time under a heavy threat (16.7 to 15.2%; the pros 8%), and fewer frags a
   minute (2.28 to 1.87). He did not hold ground better; he fought a little less.
6. **The readout works**, and is the one part to keep: the brain reads the threat and each zone's cover from his senses with a skill
   of 0.66 to 0.77. Whether it is free is open: update 30 (the readout only) read 35.0% between two readings of 40.5%.
7. **2.0a** (its [report](../2.0a/REPORT.md)): taking the damage pay out changed nothing he does (the lightning, dying when outstacked)
   and cost eight points and the first tenth of his megas. Taking a pay away does not put a behaviour in its place.

## What was wrong in the design (mine)

| The mistake | What it cost | The rule it breaks |
|---|---|---|
| Three parts in 100 updates, one check a part | no part can be read alone; the pay cannot be judged at all | one new thing a round; a new part gets its own checks |
| 59 inputs into the hands, the head and the keep choice at once | the unstable target, the items lost | 1.7a's postmortem: a choice fed a fast-moving number is learnt away |
| The start was 2.0a's end, 42% and already sliding on the items | no clean baseline; two regressions on top of each other | the control should be the start |
| The dry run's 37.0% with everything open was passed as "the worst case" | it was the forecast, and it was right | a new lesson under the control at its dry run is not started |
| The table is the pros' damage, and nobody in his games deals it | the place has no consequence in the game he plays (below) | a pay must agree with the game's own outcome |
| No guard on the item game | the loss was found in the postmortem, not in the run | never let the pickups collapse (owner, 10-08) |

**The one that matters most.** A place is dangerous because of what the enemy does to you there. In the pros' games that is a rail down
the corridor or rockets on the doorway. In his games the opponent holds the rail 0.35% of the time and the lightning 65%, and does
not hold an angle. Sight is the same in both directions, so with the same weapon on both sides the edge is near nothing, and "under a
threat" just means "in a lightning fight". The only way he could lower it was to fight less. So the table told him a place was bad, and
the frags, the deaths and the judge told him nothing happened there. He believed the game. The idea is right; **his world has no
one in it who punishes a bad place**, which is the owner's own first answer of 11-09 ("the other one not punishing").

## How to come at it differently

Control is real in the game because a player who holds ground makes the other one pay for entering it. So the first job is to put
that player into his games, and let the frags and the wins teach the place. That is AlphaStar's answer to a weakness self-play does
not find: exploiters in the league, built to punish it. A pay by the place then has something true to agree with.

| Step | What | Why first | Trains? |
|---|---|---|---|
| 1 | **The holder test.** A seat that plays 1.7a's update 90 with three rules on top: the pros' weapon for the range (the play dial `!weapons pros` exists), its target the holding place with the best edge against where it believes the enemy (the holding places and the table exist), and it does not leave that ground while its stack is ahead. 200 games against update 90, and the same seat with the weapon rule only | if the holder wins, space has a price in his simulator and we have the punisher; if it does not, holding is weak there (the rail under his aim limits, most likely) and that is fixed before any space run. Either answer is worth more than another night | no |
| 2 | **2.0c: the holder in the league**, a quarter of the seats, from 1.7a's update 90 with 1.7a's pay. One new thing. No new inputs, no new pay | the frag and the win now cost him for walking into held ground; the control is the start, so the checks read 50% at update 0 | yes |
| 3 | **The readout into the hands through the brain's token**, not 59 raw inputs, and nothing new into the keep choice. First an arm: the readout's lesson alone for 30 updates against the control | the brain already reads the map; its token is an open, slow path the hands know. The arm settles finding 6 | arm, then a run |
| 4 | **The pay by the place, alone**, only if 2 and 3 leave a gap to the pros. From a clean start, at a size that can register (5% of the pay's size, not 0.8%), held 60 updates with three checks, on his own damage table once the holders give it a rail row | finding 2: it has not been tried. Flat first, the judge's variant after (owner, 11-09) | yes |

Guards on every one of these runs, flagged by the ramp from update 1:
- **The big items head to head** in each check (megas and reds, he against the control): a tenth under the control is a FLAG, a fifth a MAJOR line.
- **The keep choice's quiet re-decisions** over 0.08.
- **The space measures on each check's games** (not built for 2.0b): his time under a heavy threat and the edge, against the control's.

**The start: 1.7a's update 90, with 1.7a's pay.** 2.0a's pay took eight points and changed nothing, and 2.0b's end is 27%. Both ends
stay kept. The damage pay coming back is the owner's call: the case for it is that 2.0a measured no gain from its going.

**What stays from 2.0b**: the map's table and `sim/space.py`, the weapon table, the readout (`sim/spaceread.py`, `--space-read`), the
inputs and the pay behind their switches (off), the measurements ([MEASURED.md](MEASURED.md)), the tests. Nothing is thrown away.

## Weaknesses of this proposal

- A rule-made holder is a hand-built opponent. He may learn to beat the rule and not the idea; the remedy later is a trained
  exploiter (AlphaStar's), which needs the rule one first to have something to start from.
- The holder plays the pros' weapon table. 1.7c trained him under that table and gained nothing; here the table is on the
  opponent's seat only, and his own weapon stays untouched.
- If step 1 shows holding does not win in the simulator, the work moves to why (the rail, the aim limits at range, rockets on a
  doorway), and the space runs wait.
- The postmortem arms are single checks of 200 games: the split between the inputs live (six points) and the weights (seven) is
  rough; the timing of the fall (updates 50 to 70) is the firmer evidence.

## State

Stopped 07:21: the trainer, its command shell, the watcher, the ramp and the self-play logger, each matched by its own command line;
nothing of the run is running. The arms' files: the scratchpad's `pm/`. Nothing committed (branch `b20b`).

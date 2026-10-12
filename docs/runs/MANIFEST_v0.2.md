# v0.2: the manifest (2026-10-11; started 21:49:59, to 19:00 on 2026-10-12; changes during the run in section 9)

**The names** (the owner, 2026-10-11): "The v15c bot that exists on the server is now: v0.1. We're building v0.2
currently, any exploration phases will get a further index e.g., v0.2.1, etc." and "v1.0 starts when he can beat me."

| Name | What it is | Its folder |
|---|---|---|
| **v0.1** | the network on the public server since 2026-10-11 13:01; the control | `duel_gru_v15c` (`policy_end_v15c.pt`) |
| **v0.2** | this run: games on all ten maps, the rocket changes, the enemy as a target, stage A of the attention model, a value estimate that counts two minutes ahead, a tiny pay for speed gained from hop to hop, a first step of his aim toward the pros' | `duel_gru_v0_2` |
| v0.2.1, ... | trials on the way. (The ten-map run without attention, written up as `duel_gru_v15e`, is not run: the owner chose to build everything first) | |
| **v1.0** | the first network that beats the owner | |

**The owner's go** (2026-10-11 evening): "I would prefer to just build everything and start when it's ready ... I do not
need the computer tomorrow during the day"; "begin building everything ... You can start it whenever it is ready. let it
run until 7pm tomorrow, with a midway report around 12noon and brief checkup at 7am. Monitor it while running every 30
minutes, you can make changes if you think something has gone wrong, but stop if things look really bad." At 20:00:
"Add another short repot at 4pm. Add delirium to the held out map ... I don't know either of those two maps so they're
held out for me too. This check is purely to make sure he's not 'overfitting'. Build everything for attention A first,
then build the rest (B and C) once the run has started and you have downtime. monitor the memory usage and computer/gpu
usage, optimize it accordingly".

## 0. What it is judged by

The owner: "Short reports should have convergence to pros metrics included. Remember these are metrics not necessarily
goals, but I think it's the right point to be guiding towards. The things I really want to see":

| He wants to see | The measure | v0.1 | The pros |
|---|---|---|---|
| Building and maintaining speed | his time at 400 or more while travelling; speed at hops 1 to 3; the share of his game time his legs carry him | 9.4%; 332, 389, 384; 46% | 17.5%; 366, 421, 422 |
| Weapon usage (rockets) | rockets a minute; rockets in hand with the enemy in view; a rocket hit then a beam hit, per ten minutes | 2.1; 19%; 0.02 | 10.8; 40%; 2.0 |
| Not fighting from the low ground | higher than the enemy in view; his time in the lowest third of the map | 17.5%; 40% | 26%; 28% |
| Not picking fights when weak or understacked | fights he commits to with a stack under 60; what taking a fight pays him then; his closing speed when weak | 3.2%; -0.06; +33 | 1.2%; +0.04; -12 |
| Maintaining his strong item timings | back at the mega within 2 s of its return (the red and the yellow armors beside it) | 49% | 47% |
| Being aggressive when it will pay | fights he commits to against an enemy spawned under 10 s ago, less against one alive over 25 s; closing just after his frag, less otherwise | -5.6 points; +2 | +2.4 points; +32 |
| Not falling for spam, using spam for zoning | rockets, grenades and plasma fired with nobody in view, a minute; the damage he takes from shots fired at him unseen (the scripted lobber's grenades; a counter added to the checks) | 0.01; to be measured | 4.5, 1.8, 1.8 |

Beside these: the duel against v0.1 map by map (seats swapped), the stand-in on the ten maps and on House of Decay, his
flick curve and where he looks before the enemy appears, and at the end real games against the game's Nightmare bot.

## 1. What changes from v0.1

| # | | v0.1 | v0.2 | State at 20:00 |
|---|---|---|---|---|
| 1 | Games on all ten maps (Campgrounds "in") | games on six, movement only on four | thirty simulators, three a map | ready (a dry run without attention passed at 18:38) |
| 2 | The three rocket changes ("in"): half the shot's price, free at the pros' places, half the cost of a wasted one | off | on | ready; in a trial of 165 minutes harmless and without effect on his rocket use |
| 3 | The enemy as a target, seeded by the narrow rule ("in") | none | **not in the run as started** (section 9) | its start lost the level check |
| 4 | **Attention, stage A** (section 2) | a flat list of 577 inputs | 720 inputs (143 new) cut into 38 tokens and a summary, two attention blocks, a door into his memory that starts closed; 1,719,471 weights (1,435,981) | in |
| 5 | **A value estimate that counts two minutes ahead** ("yes") | one estimate, 25 s | the pay for items and stack is also counted at two minutes (`--long-gamma 0.9998`); fights stay at 25 s. It fades in over the first hour (`--long-ramp 60`) and is cut if it would add more than half the size of today's credit (`--long-cap 0.5`); in the dry run it added 1.5 to 3.5% | in |
| 6 | **A tiny pay for speed gained from hop to hop** ("pay him a tiny amount for it") | none | `HOP_PAY=0.001`: at a take-off while travelling with nobody in view, 0.001 for each unit of speed above the best take-off of this chain so far, between 320 and 480. A chain's first take-off sets the mark and is not paid (paid, it could be farmed by starting chains again and again); a chain ends after 0.4 s on the ground, with an enemy in view or under 250. The movement network's pupil earns 0.49 a minute from it, a walker nothing; in the dry run he earned 0.16 to 0.19 | in |
| 7 | **His aim, a first step toward the pros' flick curve** ("let's slowly tune it down, using pros as a goal") | `AIM_LEVEL=3` | `AIM_LEVEL=1.5`: his sight error, the delay before he notices an enemy off his crosshair, his flinch and his hand's noise up by 1.4. Measured on v0.1 (19 settings tried): first hit 0.29, 0.33, 0.41, 0.63 s at 0 to 5, 5 to 10, 10 to 20, 20 to 40 degrees off (before 0.29, 0.32, 0.38, 0.59; the pros 0.32, 0.44, 0.55, 0.76); lightning 43% of its cells (47%; the pros 32%); rail unchanged at 45% (the pros 43%). Both sides of every check play under the same limits | in |
| 8 | Held-out check: two maps he never trains on and the owner does not know, "purely to make sure he's not 'overfitting'" | the stand-in on ten maps | also House of Decay and Dismemberment (the owner, on Delirium's faults: "don't know delerium it can go. dismemberment works instead"); the control with seats swapped | both ready, with their own places and cells from their demos |

Unchanged: his legs, the pay for speed in games (0.5), the weapon rounds, item runs and jump runs, the item rule, the
game's weapon change on an empty weapon, the league of his last eight selves with the older networks (v0.1 among them)
as standing opponents in a quarter of the rollouts, the control in every check.

Not in v0.2, as answered: a target that is never "nothing", several ways to a target, whole games with a frag paid by
what it moves his chance of winning, late-game rounds ("up to 25%"), the pros' choices as a standing pull, sounds on
stairs, legs that run and look, the judge, rounds from real moments, the exploiter (left out).

## 2. Stage A in full

**The model.** The inputs are cut into tokens inside the network. Each kind of token has its own first layer to 96
numbers and every token a learned mark of its own; one attention block over all tokens (4 heads, feed-forward 96 to 192
to 96); a second block read out for two rows only (a summary token and his own); those 192 numbers go through a last
layer into the input of his memory, added to what today's encoder gives. That last layer starts at zero: at its first
update the network is v0.1 exactly. Today's encoder also gets the new inputs, at zero weight.

| Token | How many | From today's inputs | New in stage A |
|---|---|---|---|
| Himself | 1 | health, armor, weapons, ammunition, his speed, his hands, his legs' switch, his style, his hits, the lead for a rocket, a grenade's arc | |
| The game | 1 | the clock and the score | the share of the round left; how loud he has been in the last 3 s; whether an enemy heard him |
| Around him | 1 | walls, floor, hazards, what he sees, the map reader's numbers for his cell | his height against where he believes the enemy is and on the map; how the pros fare in this cell and with which weapon (rockets, rail, lightning); how many of the map's places he has in sight |
| The enemy as seen | 1 (and one for the others in a group) | where, how fast, facing, weapon, his shots, his pain | |
| **The enemy as believed** | 1 | where he was last seen and how long ago; what he heard | where and when he last heard him; how far the enemy can have got; the way in seconds to that place, and from it to the mega and the red armor; his strength as far as it can be known: the damage dealt to him this life, how long he has lived (if he saw the frag), the mega and armors he was seen or heard taking, the big weapons seen in his hands |
| Projectile | 8 (six of the enemy's, two of his own) | all of it | |
| Item | 13, and one for a dropped weapon | where, up or not as he believes | when he last took it himself |
| **Place** | 8 | | the nearest of the map's 24 places where the pros' shots land with nobody in view: where, in sight or not, how far from where he believes the enemy is, how much the pros fire there, how often they meet and hit the enemy there, how a pro standing there fares |
| His target and way | 1 | his target, the way to it, the jump ahead | |
| Sounds | 1 | the sounds heard and where | |
| Summary | 1 | | a learned token |

Campgrounds has no places yet (its 220 older demos are being fetched on the owner's "yes"); its place tokens are empty
until its list is made.

**The value estimate at two minutes.** Three outputs instead of one: the first is today's (all pay, 25 s) and is left
as it is; the second and third estimate the pay for items and stack at 25 s and at two minutes. What he is credited
with is the first, plus a share of the difference between the third and the second. The share rises from nothing to
all of it over the first hour, while the two new outputs learn. So nothing jolts at the start, and after the hour items
and stack count two minutes ahead while fights count as today.

## 3. Rounds, pay, opponents

Games of two minutes, the weapon rounds, item runs and jump runs on all ten maps; the scripted lobber, watcher, holder
and runner; his last eight selves; v0.1 and the network before it as standing opponents. The pay is today's with rows
2, 5 and 6 of section 1.

## 4. Start, checks, reports, stopping, promotion

- **From v0.1**, widened to the new inputs and outputs, with the attention parts added by a converter and the enemy as
  a target fitted by the narrow rule.
- **It starts when these pass**, at whatever hour: the simulator is unchanged in fixed runs with the new switches off;
  the converted network gives v0.1's outputs on the same inputs; a ten-minute dry run fits the card, updates come, and
  his step per output is normal; its first check against v0.1 is level (48 to 52% with the seats swapped). If one fails
  it does not start and the owner has the reason at 07:00.
- **Until 19:00 on 2026-10-12.**
- **Size and speed**: set by a full-size dry run: the stored inputs at half precision, the number of pieces an update is
  cut into chosen so that the card stays under 90% of its memory. The card's memory, its load and the PC's load are read
  at every 30-minute check and the run's size or the side jobs are changed if one is out of line (the PC at 80 to 85%).
- **Every 30 minutes** a line to the owner ("checked <time> ..."): updates coming, his step, the door (how much of his
  memory's input comes through it), and from the trainer's own counters: his legs' share and speed, rockets in hand and
  rockets with nobody in view, his closing speed when weak and when stacked, his height against the enemy, the hop pay.
- **Checks from every save**: against v0.1 on the ten maps with the seats swapped; his speed profile; every third time
  the stand-in on the ten maps and on House of Decay.
- **07:00 a brief checkup, 12:00 a midway report, 16:00 a short report, 19:00 the end**: each with the scorecard beside
  the pros (a replay of 25 minutes at low priority) and the table of section 0. At the end also his flick curve, where he looks, real games
  against the game's Nightmare bot on the quiet PC, and a video.
- **Changes during the run** (the owner: "you can make changes if you think something has gone wrong, but stop if things
  look really bad"): written into this file's section 9 with the hour and the reason. Stopped: under 45% against v0.1
  at two checks in a row, a map ten points under at two checks, or a stall that a restart from the last save does not cure.
- **Promotion to the public server as v0.2**: it beats v0.1 and falls back in no group of the scorecard by more than
  three points ("within an amount of noise"), the plugins play it (section 5, last row), and the owner has played it.

## 5. The build

| | Work | Who | State at 20:00 |
|---|---|---|---|
| a | The new inputs in the simulator (always there, at the end; today's simulator frozen as a copy; the group module regenerated; fixed runs unchanged; speed measured) | a helper | started 19:50 |
| b | The pay split (which part of each frame's pay is for items and stack) and the hop-gain pay, in a copy, as a patch | a helper | started 19:50 |
| c | The network with attention in the trainer, the three value outputs, the stored inputs at half precision, the door's size written with every update | the main session | started |
| d | A converter that adds the attention parts to v0.1 with the door closed (outputs equal on a batch) and the same forward pass in plain numbers for the checks | the main session | next |
| e | The aim step: three replays to set it | a helper, after its demo pulls | queued |
| f | The check loop and the 30-minute watch for the new run; a counter for damage taken from shots fired at him unseen | the main session | next |
| g | Dry run, the card's memory, the first level check | the main session | last |
| h | For the real server (not needed to train): the plugins and the export build the tokens with the simulator's own function; four Bobbys timed on a private server | | before promotion |

A crude estimate: ready between 02:00 and 05:00 if nothing fails its checks. Stages B and C (a target that is never
"nothing", several ways, whole games, legs that run and look) are built in copies once the run is going.

## 6. What could go wrong

- The door stays closed: he ignores the tokens. The door's size is in every 30-minute line. The answer, if it has not
  moved by noon: a short lesson that makes him foretell from the tokens where the unseen enemy is (stage B's belief,
  brought forward as v0.2.1).
- The two-minute estimate makes the pay for items louder than the pay for fights. It fades in over an hour and his
  step per output is read at every check; if his fights suffer its share is cut.
- The aim step changes what wins. Both sides of every check play under the same limits; the owner expects rockets to
  gain as lightning and rail lose their edge, and his weapon in hand is in every line.
- Five things change at once (maps, attention, the long estimate, the hop pay, the aim). The scorecard and the per-map
  duels separate most of it; what they cannot separate is said plainly in the report.
- The card: more work a step and more stored inputs. If it does not fit at full size the run is three quarters of its
  players.

## 7. The public server

v0.1 stays on it and Toxicity stays in its map list (the owner's "no"). Nothing is pushed by this run. At the next push
with new code v0.1 needs `--env duel_env_ffa_v15` (the frozen 576-input simulator).

## 8. To raise with the owner when this run ends

His list ("remind me of these after this run ends"): rocket jumps and plasma climbs; the gauntlet. From earlier: the
judge of pro-like movement ("remind me of it after tonight's run"); sounds on stairs, to be measured in the game.

## 9. Changes during the run

- **Before the start (21:45): the enemy as a target is out.** The start network with the narrow fit took 45.9% of the
  frags against v0.1 over eight maps with the seats swapped (45 games won, 8 drawn, 75 lost) before the check was
  stopped: not level. The afternoon's probe that read level was 48 games. The run starts as v0.1 exactly (the converted
  network differs from v0.1 in 0 of 15,360 choices); `FIGHT_TARGET` is not set.
- **As started**: `duel_gru_v0_2`, 21:49:59, 1,270 minutes; thirty simulators of 168 games; an update cut into 240
  pieces (the dry run with 200 came within 0.3 GB of the card's limit); stored inputs at half precision.
- **The dry runs** (on the way to the start): the first try filled the card in the update; the attention part was made
  lean (4.7 GB a piece of 63 players, at half precision on the card) and the update reworked so that only his memory
  steps frame by frame: 15,400 frames a second against 22,800 without attention. His step in the first updates 0.023
  falling to 0.019 (the afternoon's trial: 0.010); the door at 3% of his memory's input after four updates.

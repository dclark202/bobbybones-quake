# v0.2: the midway report (2026-10-12, 06:30; numbers to 05:00)

**Which run is which.** v0.2 is `duel_gru_v0_2`: v0.1 (v15c's end, on the public server) with attention stage A, 143
new inputs, the two-minute value estimate, the hop-gain pay, the first aim step and games on all ten maps
([MANIFEST_v0.2.md](MANIFEST_v0.2.md)). Started 2026-10-11 21:50; it ends at noon on the owner's word of 22:10. The
control in every check is v0.1.

## In short

- **The run is healthy**: 97 updates in seven hours, one every 4.3 minutes, no stall, nothing changed in it.
- **He is stronger than v0.1, and all of it is on the four maps v0.1 never played games on.** 56.7% of the frags at the
  last check (90 games won, 14 drawn, 56 lost). On Cure, Hektik, Campgrounds and Toxicity 62%; on the six maps both
  know 53%, which is inside the checks' noise.
- **No sign of overfitting**: against the stand-in 72% to 75% over twelve maps, the two maps he never trains on level
  (House of Decay 77% to 75%, Dismemberment 58% to 60%).
- **His way of playing has not moved yet.** The scorecard beside the pros reads 47% as it did at the start (49%, v0.1
  47%). Of the seven things the owner wants to see, none has moved beyond noise in seven hours; three small moves
  point the right way (below).
- **Built beside it**: v0.2 plays on a real server (for the noon game), and all of stages B and C exist as tested patch
  scripts that apply together. None of B and C has run on the graphics card.

## 1. The run

| | Start | Now (update 97, 05:00) |
|---|---|---|
| Frames a second | 14,230 | 14,580 |
| His step in an update | 0.021 | 0.017 |
| The door: share of his memory's input that comes through the attention part | 1.7% | 33% |
| The two-minute count: what it adds to his credit | 1.5% | 30% |
| The hop-gain pay, a player-minute | 0.175 | 0.18 |
| The card | 13.4 GB of 16 | 13.6 GB |

The PC read 88 to 100% for half an hour before midnight with four helpers testing beside the checks (the trainer 3%
slower); the check loop went from six processes to four single-threaded ones and it has been 70 to 85% since.

## 2. Strength

Against v0.1, seats swapped, 160 ten-minute games a check, his share of the frags by map:

| Check | Blood Run | Aerowalk | Lost World | Sinister | Furious H. | Battleforged | Campgrounds | Hektik | Toxicity | Cure | Mean | Games |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| the start (the same network: the noise) | 48 | 51 | 56 | 48 | 41 | 46 | 50 | 45 | 50 | 53 | 48.8 | 70-8-82 |
| 00:18 | 47 | 47 | 51 | 41 | 48 | 47 | 49 | 54 | 49 | 71 | 50.5 | 73-12-75 |
| 01:19 | 54 | 49 | 54 | 50 | 51 | 50 | 61 | 57 | 51 | 71 | 54.8 | 97-8-55 |
| 02:17 | 52 | 54 | 51 | 54 | 47 | 54 | 56 | 59 | 55 | 81 | 56.1 | 96-12-52 |
| 04:15 | 54 | 48 | 56 | 47 | 60 | 51 | 55 | 60 | 55 | 80 | 56.7 | 90-14-56 |

The six maps v0.1 was trained on: 48.3, 46.8, 51.3, 52.0, 52.7. The four it only had movement practice on: 49.5, 55.8,
60.0, 62.8, 62.5. So far v0.2 has learnt four maps; on the other six it is level with v0.1. In the same games he keeps
his stack better than v0.1 does (150 or more 53% of his time, at the start 43%; bare 8%, at the start 11%) and dies by
his own hand less (0.9 a game against 1.2).

Against the stand-in (16 games a map): 72.0% at the start, 75.0% at 03:20; Hektik 52 to 64, Cure 69 to 82; the held-out
House of Decay 77 to 75, Dismemberment 58 to 60.

## 3. The owner's seven points

The start is v0.1 at the run's aim level; "now" is the save of 04:27 replayed through the pros' yardsticks.

| He wants to see | The measure | Start | Now | The pros | Moved? |
|---|---|---|---|---|---|
| Building and maintaining speed | time at 400 or more while travelling; second hop; his legs carry him | 10.1%; 396; 44% | 9.0%; 385; 50% | 17.5%; 421 | no (his legs carry him more) |
| Weapon usage (rockets) | rockets a minute; rockets in hand with the enemy in view; a rocket then a beam, per ten minutes | 2.17; 18.4%; 0.07 | 2.33; 19.5%; 0.05 | 10.8; 39.5%; 3.6 | no |
| Not fighting from the low ground | higher than the enemy in view; time in the lowest third | 17.2%; 40.9% | 16.6%; 40.8% | 26.4%; 27.8% | no |
| Not picking fights when weak | commits with a stack under 60; what such a fight pays; closing speed when weak | 4.0%; -0.40; +26 | 5.0%; -0.39; +24 | 1.2%; +0.04; -12 | no |
| Strong item timings | back at the mega within 2 s of its return | 48.2% | 53.0% | 47.2% | held |
| Aggressive when it pays | commits against an enemy spawned under 10 s ago, less against one alive over 25 s | -4.1 points | -2.9 points | +2.4 points | within noise |
| Spam, his and the enemy's | rockets with nobody in view, of his rockets; hits he takes unseen, a minute (v0.1 in the same games 1.81) | 0.3%; 1.70 | 0.4%; 1.64 | 49.7% | no |

Three small moves toward the pros, each a few points and not yet beyond doubt: the humming weapons (rail, lightning)
in hand while travelling 64.5% to 60.9% (the pros 28% falling to 9% as the enemy goes unseen; he 78% to 73% after 15 s
unseen); rockets in hand while holding a spot 12.5% to 14.6% (the pros 82%); his trips on the commonest way 57.6% to
54.5% (the pros 42%). His aim sits where the aim step put it (first hit at 20 to 40 degrees off 0.61 s, v0.1 0.56, the
pros 0.76; hits of the first half second 41 to 46%, the pros 36%).

## 4. The scorecard: how near the pros (100% = their value)

| Group | v0.1 | The start | Now (04:27) |
|---|---|---|---|
| Position | 62% | 61% | 63% |
| Speed | 82% | 84% | 81% |
| Weapons | 17% | 17% | 18% |
| Aggression | 3% | 10% | 0% |
| Control | 95% | 98% | 88% |
| **All fourteen measures** | **47%** | **49%** | **47%** |

Aggression is two measures of closing speed and swings ten points between replays of one network; control fell because
he is at the mega more often than the pros (53% against 47%), which the index counts as distance.

## 5. What this says, plainly

Stage A shows him more; in seven hours he has used it to play four more maps as well as he plays the six, not to play
differently. That is what the plan said of it ("it passes if it is level with the control at the first check and
ahead after a night, and the door has opened": both true), and why the plan had stages B and C: his targets, his ways
and his legs are what hold speed, rockets, height and the choice of fights where they are, and stage A changes none of
them. Whether the remaining hours move the seven points I cannot say; the trend of the three small moves is the thing
to watch at noon.

## 6. Built overnight

| What | State | What it found |
|---|---|---|
| v0.2 on a real server (the export, both plugins, the tables of ways) | proven on a private server, pushed | the plugins' network gives the checks' choices exactly; 6 to 9 ms a frame; beside a training run any server stutters; not yet tested with a person |
| B1: things he foretells (the unseen enemy's place, where he next appears, how a fight ends, item returns) | built, checked alone and merged | in a tiny run he learnt the enemy's place (501 to 419 units) and the mega's return (7.3 to 3.7 s); a fight's window is 7.2 s, not 10 |
| B2: places as targets, a target that is never "nothing" | built, checked, merged | eight holding places a map from the pros; "the nearest place when no item is due" read level in 48 games and took his idle time from 14.6% to 1.9%; far places cost; his legs cannot stop at a ledge |
| B3: several ways | built, checked, merged | a small lever: his legs make 130 second ways and 4 third ways on ten maps; the pros' other ways are mostly drops, jumps and rocket jumps the walking map lacks |
| B4: whole games, late rounds, a frag paid by the game | built, checked, merged | the pay must be per frame or it can be pumped; the table from 3,355 pro games; a whole game is 4.8 hours of a run |
| C1: his own movement taught by his legs, the switch weaned | built, checked, merged | on the frames his legs carry him his own turn is the label's 6% of the time (ceiling 71%): the whole of strafe jumping is missing on his own feet; the lesson needs a warm-up |
| C2: legs that run and look, and that arrive and stand | built, checked, merged; needs an hour or more of the card | standing is learnt in minutes; looking did not move in a sixteen-minute run |
| The six together | one script, tested in a copy | with every switch off bit for bit today's simulator and trainer; everything on runs; v0.2 converted answers exactly as before |

Specifications and results: [../design/V02_STAGE_B.md](../design/V02_STAGE_B.md),
[../design/V02_STAGE_C.md](../design/V02_STAGE_C.md); the log: RESULTS 2026-10-11 23:40.

## 7. For the owner to decide

1. **The noon game.** v0.2 can be played on the local server as soon as the run is stopped (recommended: beside the
   trainer it stutters), or pushed to the public server on his word. Which, and whether the run goes on afterwards.
2. **The next run.** My suggestion: from v0.2's end, B1 and B2 and C1 (with a warm-up), each after its ten-minute dry
   run on the card and, for the place choice, a level check of 128 games. B3 waits (small lever), B4 waits for
   decisions 3 and 4 and for checks that know whole games, C2 waits for its legs to be trained.
3. **The table a frag is paid by**: the pros' as counted (one ahead with ten minutes left: 61%) or the same for equal
   players (58%; the late level-breaking frag worth 4 opening frags instead of 2.9). I would take equal players: his
   own games are between near-equals.
4. **Whole games fill slowly** (4.8 hours each, lost at a restart): start some matches in the middle of a game at a
   run's start? It goes beyond what was approved.
5. **Who chooses where his legs look**: always his belief of the enemy (a rule), or an output of his own. I would
   decide after the legs' training shows that looking can be learnt at all.

## 8. Faults and what did not work

- A helper's tiny trainer reached the graphics card for a moment at 22:17 (an empty `CUDA_VISIBLE_DEVICES` does not
  hide the card on Windows); the run kept its pace; `-1` since.
- The check loop ran with the enemy as a target switched on though the run has it off: harmless (he never chooses
  it), set right at 23:21.
- Two usage windows closed during the night (about 22:15 and 02:10 to 03:10): the six-part merge was cut twice and
  resumed, the scorecard replay came an hour later than planned; the run and its checks were never touched by it.
- `sim/test_suite.py`'s rooms have not run on any simulator since v12 (a name defined twice): found by the merge
  (B-232).

At the run's end: the reminders the owner asked for (rocket jumps and plasma climbs, the gauntlet, the judge of
pro-like movement, sounds on stairs), real games against the game's Nightmare bot on the quiet PC, a video, the report.

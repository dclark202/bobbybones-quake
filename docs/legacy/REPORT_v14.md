# `duel_gru_v14`: full report (2026-10-10)

Three starts between 2026-10-09 20:15 and 2026-10-10 11:52 ([MANIFEST_v14.md](MANIFEST_v14.md); mid-run reports
[MIDRUN_v14.md](MIDRUN_v14.md) and [MIDRUN_v14c.md](MIDRUN_v14c.md)). The owner ended it at 11:51: "end the v14 run now,
saving the best checkpoint 10:57 and calling the run mixed in success". Numbers are from the log entries of
[2026-10-09](../results/2026-10-09.md) and [2026-10-10](../results/2026-10-10.md). What comes next:
[MANIFEST_v15.md](MANIFEST_v15.md).

## In short

- **v14 is the save of 10:57 of the third start** (`data/sim_runs/duel_gru_v14/policy_end_v14.pt`): v13 and 164 minutes
  of training in the simulator set right against the game's maps, with v13 as the control in the league and in every
  check, before the strafe-jumping teacher came on.
- **Against v13 head to head it is level on the three maps v13 trained on and ahead on the three that are new.** The
  end save, 32 ten-minute duels a map: Blood Run 53% of the frags, Aerowalk 49%, Lost World 53%; Sinister 56%, Furious
  Heights 79% (32 games of 32 won), Battleforged 71%.
- **Against the Nightmare stand-in it is the best network so far**: 77.2% of the frags on the six trained maps (v13:
  69.7%) and 59.7% on the four he never trained on (49.2%). The gain is where the simulator was most wrong: Furious
  Heights 42% -> 60%, Battleforged 62% -> 87%, Campgrounds 35% -> 63%.
- **None of the three things the run was for came.** No strafe jumping (282 units a second in games, v13 275), rockets
  no more in hand (18%, v13 19%), grenades and plasma never in hand (0.0%).
- **The strafe-jumping teacher cost duel strength in all three starts.** The cause was found after the run: its hands
  are not his (below).

## The three starts

| Start | What was different | What happened |
|---|---|---|
| 1: 2026-10-09 20:15 to 22:50 | every teacher held back from the shared layers | half his duel strength gone in 90 minutes, no strafe jumping; kept as `duel_gru_v14_try1` |
| 2: 22:53 to 2026-10-10 07:42 | the movement teacher alone let into the shared layers; a weapon teacher; rockets at a fifth of the price | faster in item runs, weaker than v13 as a duelist ([MIDRUN_v14.md](MIDRUN_v14.md)); kept as `duel_gru_v14_try2` |
| 3: 08:06 to 11:52 | v13 in a quarter of the league's rollouts and first in every check; weapons as v13 had them; the teacher off for the first hours | below |

The third start, check by check (v14 against v13, 32 ten-minute duels a map, his share of the frags):

| Save | Blood Run | Aerowalk | Lost World | |
|---|---|---|---|---|
| 08:33 | 50% | 12% | - | the item rule named Aerowalk's red armor, which only a circle jump reaches |
| 09:14 | 51% | 12% | - | |
| 09:54 | 48% | 17% | - | `RULE_WALK=1` from 09:32: the rule names what a walker reaches |
| 10:24 | 53% | 50% | - | |
| **10:37** | **52%** (19 games won, 12 lost) | **47%** (14, 18) | **48%** (11, 18) | the last check before the teacher |
| 11:23, the teacher at 0.11 | 50% | 48% | 40% (7, 24) | from 10:57: the teacher on, grenade and plasma shots free |
| 11:46, the teacher at 0.23 | 44% (10, 18) | 45% (8, 22) | 44% (10, 22) | ended at 11:52 on the save of 10:57 |

The end save itself (10:57) against v13 on all six maps (checked 2026-10-10 14:21, 32 ten-minute duels a map):

| | Blood Run | Aerowalk | Lost World | Sinister | Furious Heights | Battleforged |
|---|---|---|---|---|---|---|
| His share of the frags | 53% | 49% | 53% | 56% | **79%** | **71%** |
| Mean score | 10.3 : 9.0 | 19.1 : 19.8 | 6.9 : 5.8 | 8.6 : 6.6 | 11.0 : 2.2 | 12.4 : 5.0 |
| Games won, drawn, lost | 19, 0, 13 | 12, 0, 20 | 16, 5, 11 | 22, 4, 6 | 32, 0, 0 | 28, 2, 2 |

v13 trained on Blood Run, Aerowalk and Lost World only; the other three are new in v14.

## Against the Nightmare stand-in (simulator, 32 ten-minute duels a map)

| Map | v13 (the start) | v14 (the save of 10:37) | Games won, drawn, lost: v13 | v14 |
|---|---|---|---|---|
| Blood Run | 71% | 70% | 32, 0, 0 | 28, 2, 2 |
| Aerowalk | 80% | 84% | 32, 0, 0 | 32, 0, 0 |
| Lost World | 90% | 89% | 32, 0, 0 | 32, 0, 0 |
| Sinister | 74% | 73% | 32, 0, 0 | 32, 0, 0 |
| Furious Heights | 42% | **60%** | 8, 4, 20 | 22, 1, 9 |
| Battleforged | 62% | **87%** | 24, 2, 6 | 31, 1, 0 |
| **The six trained maps** | **69.7%** | **77.2%** | | |
| Campgrounds | 35% | **63%** | 9, 2, 21 | 22, 1, 9 |
| Hektik | 51% | 60% | 16, 2, 14 | 21, 0, 11 |
| Toxicity | 64% | 65% | 17, 6, 9 | 26, 0, 6 |
| Cure | 47% | 51% | 16, 3, 13 | 22, 2, 8 |
| **The four never trained on** | **49.2%** | **59.7%** | | |

In those games, the six trained maps: time with 150 health and armor or more 64% -> 71%, his share of the red armors that came
up 17% -> 24%, of the megas 46% -> 51%, his own deaths 0.19 -> 0.16 a game, the first weapon after 4.9 -> 4.6 seconds, speed 275 ->
282. On the four others his own deaths stay high (1.13 -> 1.25 a game: lava, slime and falls on maps he does not know).

## Self-play at the end (the last 25 minutes before 10:57, beside the run's first updates)

| | The start | The end |
|---|---|---|
| In hand: rockets, rail, lightning gun, machine gun | 19%, 17%, 24%, 40% | 18%, 22%, 35%, 25% |
| Hit rate: rockets, rail, lightning gun | 41%, 47%, 44% | 45%, 47%, 45% |
| Grenades, plasma, shotgun in hand | 0.0% | 0.0% |
| Item runs: items a minute, speed, time fast in the air | 6.2, 293, 8% | 7.5, 301, 10% |
| Lava damage a player-minute | 5.4 | 6.0 |

## What worked

- **The control.** v13 in the league and in every check showed within half an hour that Aerowalk was lost (12%), and
  what brought it back (`RULE_WALK`). The owner: "this should be standard going forward".
- **The simulator set right** (the map audit of 2026-10-09: lava and slime, the game's step height, shots through
  grates, items that drop to the floor, solid pieces, the walker's map): the stand-in numbers above.
- **Red armor and stack**: more of both on every map.

## What did not work

- **The strafe-jumping teacher, three times.** With it on, his own deaths rose (Lost World 1.25 -> 1.72 a game), item
  runs gave fewer items (8.0 -> 5.1 a minute at a weight of 0.16), and speed only began to move (301, 12% of the time
  fast in the air at 0.23). **Why** (found at noon, B-201): the movement network was trained with any key on any frame;
  it changes keys 16.9 times a second, the strafe key alone 12.1 times. His left hand reads the keys ten times a second,
  a finger acts at most every 150 ms, the hand has 8 key actions a second. A player who presses exactly its labels with
  his hands on Lost World takes 46 points of lava damage a minute and his hand refuses 64% of the key requests. He was
  taught presses he cannot make, along the lava.
- **Rockets**: 18% of the time in hand, as v13. The low rocket price of the second start was not in the third.
- **Grenades and plasma**: never in hand; the free shots came only for the last hour.
- **What he saw of enemy projectiles was wrong** (found at noon): the two nearest, through walls inside his view cone,
  and anything within 400 units in any direction. v15 has the six nearest that a player sees.

## Two side arms (2026-10-10 12:10 to 14:30)

While v15 was prepared (owner at noon: the teacher "left on"; rockets "if possible try parallel arms ... if nothing is
obviously working we'll delay it for now"), each at half size (12 simulators of 210 games). Each one's last save
against v13, 32 ten-minute duels a map:

| Arm | Trained | Blood Run | Aerowalk | Lost World | What moved |
|---|---|---|---|---|---|
| T: the teacher of v14 left on at 0.3, from the save of 11:46 | 52 minutes (stopped 13:15, to free the PC for v15's own teacher) | 46% (11 won, 18 lost) | 42% (5, 26) | 37% (6, 25) | item runs: speed 302 -> 310, fast in the air 13% -> 15%, items a minute 5.9 -> 6.1 |
| R: rockets at a fifth of the shot's price and 5% of his time in rocket-only rounds, from v14's end | 128 minutes | 48% (13, 17) | 47% (10, 18) | 50% (14, 16) | rockets in hand 19.5% (v14's end: 18%) |
| *v14's end* | | 53% | 49% | 53% | |

The old teacher at full weight goes on costing duels and buys little speed. The rocket arm did not raise rocket use and
did not cost much: nothing obviously working, so rockets are not in v15. Both arms are kept
(`data/sim_runs/duel_gru_v14_armT`, `_armR`).

## Against Nightmare, real games (2026-10-10 14:55 to 15:17, ten minutes, three servers side by side on a quiet PC)

| Map | v14's end, two games | Damage dealt / taken | His speed | The weapon in his hand | v13 on 2026-10-09 | v14's second start, this morning |
|---|---|---|---|---|---|---|
| Blood Run | **11-4**, **17-8** | 2,835 / 3,304; 3,718 / 3,824 | 283, 283 | rail 39%, lightning 30%, rockets 22%; lightning 76%, rail 19% | 14-4, 11-6, 10-3 | 10-10, 9-11 |
| Aerowalk | 1-0, 5-1 | 208 / 104; 1,100 / 565 | 256, 260 | lightning 85%, 88% | 0-0, 3-1, 12-12 | 8-21, 5-22 |
| Lost World | **4-4**, **7-2** | 2,267 / 2,851; 2,442 / 2,668 | 281, 285 | lightning 53%, rockets 29%; lightning 66%, rockets 29% | 8-5, 6-4, 9-5 | 5-7, 6-1 |

On Aerowalk Nightmare was in his view 3% and 5% of the time: the game's bot stands still there for most of a game, as
it did against v13 (two of three games). Blood Run and Lost World are games: he wins three and draws one, as v13 did
and the second start did not. He is no faster than v13 (283) and holds the lightning gun most of the time. The servers
ran yesterday evening's image: its rebuild failed on a file Docker held locked, and nothing a v14 network plays with
has changed in it since (this morning's games used the same).

## What to try next

- **v15** ([MANIFEST_v15.md](MANIFEST_v15.md)): strafe jumping from a teacher that has his hands, on the pros' jumps, with
  jump runs of its own; enemy projectiles as a player sees them; grenades and plasma in his hand and against him.
- **Rockets** (B-210): a low price for the shot (the second start) made him use them and lose; a low price with
  rocket-only rounds (the side arm) changed nothing. Not in v15. For v16: set what the pros hold by distance and height
  beside his own first, and look for where a rocket is the better shot and he does not take it.
- **Lost World's lava with a teacher** (B-208): not cured; v15 keeps the teacher out of that map's item runs.
- **Game awareness** (B-188, B-190, B-191): v16, with attention; the offline test on the pros' demos comes first.

## Verdict

v14 is v13's equal on v13's own three maps, well ahead of it on the three new ones, and better against the stand-in,
most on the maps where the simulator was wrong. It is
the start and the control of v15. Strafe jumping, rockets, grenades and plasma are still to do; the teacher's fault is
found and its replacement is tested in [MANIFEST_v15.md](MANIFEST_v15.md).

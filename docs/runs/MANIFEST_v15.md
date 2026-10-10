# `duel_gru_v15`: the manifest (draft of 2026-10-10 noon, for the owner's review; not started, on his go)

What v15 would have in its rounds, what he is shown and paid, what is new, what is built and tested today and what
is not yet. The owner's words of 10:38: "I agree with all of those changes. Start on anything you can with preparing
for v15 now while v14 is running ... Ideally I would like v15 to start tonight." Scope:
[../design/SCOPE_v15.md](../design/SCOPE_v15.md) parts 1 and 2 (jumps; grenades and plasma). Part 3 (decisions,
attention) is for v16. Everything below lives on the branch `v15`, in a separate working copy: nothing that the
running v14 loads is touched before it stops.

## 0. Decided by the owner (2026-10-10)

| | Decision |
|---|---|
| Jumps | "Definite yes." A gap course and the named jumps of the real maps; the teacher may train on Campgrounds' and Toxicity's jumps |
| Grenades and plasma | "Definite yes." Free shots and the blind-fire rule (in v14 since 10:57), opponents that use them, rounds with them in hand |
| Attention | "I really want, but it seems there needs to be more build out": v16; the offline test on the pros' demos first |
| The shares of his rounds | as proposed at 10:35 (section 1): "I agree with all of those changes" |
| The control | v13 stays in the league and first in every check ("standard going forward") |
| Priorities | strafe jumping and keeping speed; rockets; plasma and grenades, the shotgun less; then game awareness |

## 1. His rounds

Shares of his playing time.

| Kind of round | v14 (third start) | v15 | Switch |
|---|---|---|---|
| Games (self-play; duels 60%, threes 20%, fours 20%) | 70% | 62% | |
| ... against a scripted opponent | 25%: the item runner | 30%: runner 10, lobber 8, watcher 6, holder 6 | `RUNNER_P=0.30`, `TRICKS=1`, `TRICK_P=lobber:0.267,watcher:0.2,holder:0.2` |
| ... a race for a big item | 15% | 15% | `CONTEST_P=0.15` |
| ... lives that begin with grenades or plasma in hand | 0 | 5% of his lives | `START_GUN_P=0.05` (new) |
| Item runs (alone; half end in a fight) | 30% | 20% | `ITEM_RUN_P=0.20` |
| Jump runs (alone; from before a take-off to the item behind it) | 0 | 10% | `JUMPS=1`, `JUMP_RUN_P=0.10` (new) |
| One-weapon rounds (15 seconds, both with the same weapon, close) | 0 | 8%: grenades 3, plasma 3, shotgun 2 | `--kind-p 0.886,0,0.114,0`, `--drill-weapons gl,gl,gl,pg,pg,pg,sg,sg` |
| League | a quarter of the seats old selves; the control (v13) a quarter of those | the same; v14's end beside v13 if it holds against v13 | `--anchor-p 0.25` |

## 2. Jumps

**The list** (`tools/pro_gaps.py`, new): from 250 pro duels a map (150 on the three new maps), every jump over a
hole of 40 units or more, or up a ledge, set beside the walking map: "cannot" (a walker has no way from the take-off
to the landing), "slower" (his way takes a second or more longer than the flight), "just makes it" (the walking map
has the jump itself, from the very edge). Per entry: where from, where to, length, rise, the speed it needs (length
over seconds in the air of the slowest tenth of the pros who made it), how often, which item it brings nearer.
Pictures and tables per map: [../design/jumps/](../design/jumps/).

| Map | Jumps in use | A walker cannot / is slower / just makes it | The pros make them | Speed needed (least, middle, most) |
|---|---|---|---|---|
| Blood Run | 10 | 0 / 3 / 7 | 55 times an hour | 329, 392, 451 |
| Aerowalk | 15 | 1 / 8 / 6 | 102 | 322, 368, 479 |
| Lost World | 19 | 0 / 3 / 16 | 53 | 329, 371, 528 |
| Sinister | 24 | 0 / 10 / 14 | 105 | 342, 379, 505 |
| Furious Heights | 20 | 0 / 4 / 16 | 96 | 310, 362, 514 |
| Battleforged | 5 | 0 / 4 / 1 | 20 | 356, 420, 564 |
| Campgrounds (the teacher only; not one of his maps) | 12, marked by hand | 0 / 4 / 8 | few demos | 388, 416, 608 |

In use: seen 20 times or more ("cannot", "slower") or 30 times ("just makes it"). The owner strikes from and adds to
the list (a `"use": true/false` on an entry). His named jumps: Aerowalk's red armor is entry 1 there (32 times an
hour, 269 units long and 38 up, needs about 425; the only way to that armor); Blood Run's red armor is entry 1 there
(27 an hour; 226 units edge to edge at one height: a walker's jump just makes it, the pros take it at 446); the red
armor to the health bubbles on Sinister (316 long, needs 435); the upper floor of Furious Heights (16 entries); the
stairs to the yellow armor on Blood Run are probably entry 26 there (a jump of 240 units and 50 up beside the stairs,
the pros at 426): listed as "up a ledge" and not in use until the owner says it is the one. Campgrounds has only 46
player-minutes of demos, but its named jumps are in them: the bridge to the rail is entry 9 (403 units, needs 528; a
walker's way round takes 11 seconds) and the pillars are entries 1 to 18; twelve are marked for the teacher by hand.
Toxicity has no demos. The whole list as one file: [../design/jumps/pro_jumps.csv](../design/jumps/pro_jumps.csv).

| | What is built | Switch | Tested |
|---|---|---|---|
| The jumps as links | from the standing spots at the take-off to the spot at the landing, at the flight's seconds, in the teacher's walking map and in a second set of his ways | `sim/jump_links.py`; `MoveEnv(jumps=True)`; `JUMPS=1` | Aerowalk: 15 links, 11 to 12 with start points for tries |
| The teacher | the strafe-jumping network of v14, five more inputs (a jump ahead, the speed it needs, the way to its take-off, its length, its rise), half of its tries begin 250 to 1,100 units of way before a take-off; over: +1, fallen short: the try ends at -1 | `sim/train_move.py --jumps` | before any training on them it gets over 42% of Aerowalk's tries: the red armor's gap 7%, the rail to the rockets 58%, the easy drops 92 to 99%. A first session of seven minutes on all maps (11:35 to 11:42) is too short to show anything |
| Jump runs | he is alone, begins a second or two before a take-off facing along his way, the item behind the jump is his target and is there; paid as an item run; a try ends with the item, with a fall under the gap, or after twice the way's seconds and four; every jump as often as any other | `JUMP_RUN_P` | today's v14 (the save before the teacher, 10:57) alone in jump runs on Aerowalk (`tools/jump_check.py`, 818 tries): over 13%, fallen short 63%; the red armor's gap 0 of 73, the rail to the rockets 0 of 93, the long drops 1 to 28% |
| The teacher's labels in jump runs | keys, jump and view from the retrained teacher, at the weight it has in item runs; no walker's keys | `RUN_TEACHER=1`, `--teacher move_v15a` | not yet (after the teacher's session) |
| Five inputs | the jump ahead on his way: in a jump run; zero in games | the first five of `N_V15` | values present in 74% of jump-run frames |
| In games | his ways stay a walker's and the item rule names what a walker reaches (as since 09:32 today). A jump is opened in games when he is measured to make it: not built | - | - |
| The check | per jump and map: tries, over, fallen short, in every update's log; the teacher's own rate beside it | trainer `v15.jumps` | - |

Not in v15 as it stands: a gap course on the test map (the real maps give 93 graded jumps: needs 310 to 564); stairs
with jump held and the jump that hooks a ledge (to measure in the game first).

## 3. Grenades and plasma

| | What is built | Switch | Tested |
|---|---|---|---|
| Free shots, blind fire | grenade and plasma shots cost nothing; rockets with no enemy in view by where they land | `SHOT_W=gl:0,pg:0`, `BLIND_RULE=1` | in v14 since 10:57 today |
| Lives that begin with one in hand | 5% of his lives in games: the launcher or the plasma gun with a pickup's ammunition, in his hand | `START_GUN_P` | counted (13 lives in a short run at 20%) |
| One-weapon rounds | 8% of his time: both players with the same one weapon, 15 seconds, close; seven in ten with the machine gun beside it | the trainer's `--kind-p`, `--drill-weapons` (as in v9 to v12) | old code, in use before |
| Opponents that use them | the lobber fires plasma and grenades into the far end of a teleporter or pad on his way and where he was last seen; the watcher holds a post with the rail; the holder keeps mega and red armor and comes for him after a frag | `TRICKS=1`, `TRICK_P` | built and measured against v13 on 2026-10-10 night; switched off the simulator is v14's in fixed runs. The lobber's grenades and plasma make 2 to 17% of its frags: its timing is not sharpened |
| Six inputs | with the launcher in hand and the enemy seen in the last 3 seconds: how far his view is from the one that lands a grenade at the enemy's feet (yaw and pitch, coarse and fine), the seconds of flight, that it reaches | the last six of `N_V15` | values present; not yet beside a real grenade's landing |
| No teacher on the weapon key | his choice (v14's second start lost to v13 by that key) | `--weapon-teach 0` | - |

Not in v15 as it stands: grenades measured again on a real server (bounce, fuse, the push at his own feet); the
pros' table of when they fire them.

## 4. What he is shown and paid

520 inputs (509 and the eleven of `N_V15`: five for a jump ahead, six for a grenade's arc), the new ones at zero
weight. The pay is v14's: nothing new is paid. A jump run pays as an item run does (the way gained against the
clock on a running best, the pickup).

## 5. The control and the checks

- From v14's last save that holds against v13 (or v13's own, the owner's choice at the stop). v13 stays a standing
  opponent in the league and is played first in every check; under 45% of the frags against it at two checks in a
  row: stop and tell the owner.
- New in the hourly brief: jumps over per map, grenades and plasma in hand and their frags, his frags against the
  lobber, the watcher and the holder.
- Real games against Nightmare before (with v14's end) and after, on a quiet PC.

## 6. Before the start

| | State (11:15) |
|---|---|
| The jump list for the owner | done for six maps and Campgrounds ([pro_jumps.csv](../design/jumps/pro_jumps.csv)); pictures being drawn |
| The teacher trained on the jumps and checked jump by jump | its code runs; seven minutes trained; it needs an hour or two of the PC's processors |
| **The teacher checked map by map** (new at 11:45) | v14's first check with the present teacher on, at a third of its weight: Lost World 40% against v13 (48% before), his own deaths up by a third: it strafe-jumps along the lava and he copies it. Before v15 uses a teacher's labels on a map, its pupil is tested there alone (lava and fall damage, items a minute); labels by its best choice, not a sample; no labels on a map that fails |
| His side (jump runs, inputs, grenade lives) | built; switched off identical to v14 in fixed runs of both modules; jump runs tried with random players |
| The scripted opponents in the simulator | merged on the branch, identical when off |
| The network widened to 520 inputs, v14's simulator kept as a frozen copy | at v14's stop |
| A dry run of ten minutes (the step per output), GPU needed | at v14's stop |
| The servers' side (520 inputs through the same code) | to check with a recording after the start |
| The lobber's timing; grenades measured in the game | not done; open whether v15 waits for them |

## 7. For the owner to decide

1. The teacher in v14, and with it when v14 stops (the mid-run report has my advice).
2. The jump list: strike or add.
3. Whether v15 starts from v14's end or from v13.
4. Toxicity has no demos and Campgrounds few: may I fetch about 150 duels of each from the demo site, or do you give
   me Toxicity's places by hand.
5. Whether v15 waits for the lobber's timing and the grenade measurement, or starts without.

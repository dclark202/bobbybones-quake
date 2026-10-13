# `duel_gru_v15`: the manifest (2026-10-10; started 17:10 on the owner's go; **stopped 18:54**, see section 0)

What v15 has in its rounds, what he is shown and paid, what changes from v14, how each new thing was tested, what is
known not to be right yet, and what is the owner's to decide. The run starts only on his word. The network it starts
from: [REPORT_v14.md](REPORT_v14.md). The day's log: [2026-10-10](../results/2026-10-10.md). Jump pictures and tables:
[../design/jumps/](../design/jumps/).

**Which run is which.** v14's end is on the public server (since 15:39). v14 is the run of last night and this morning (three starts; the
third began at 08:06 and was ended at 11:52); "v14" or "v14's end" is its save of 10:57. **v15 is the run that began on 2026-10-10 at
17:10** from v14's end with everything below.

## 0. The owner's decisions (2026-10-10)

**Stopped at 18:54 (the first start; its saves are kept, to be `duel_gru_v15_try1` before the next one).** In 104 minutes his runs fell from 5.7 to 3.7 items a
minute, he took the teacher's jumping and its view zig-zag and none of its speed, and the first check lost Lost World to
v14's end (40%; the stop rule). Changed during the run: from 18:24, on the owner's word, 10% of his lives in games begin
with a weapon in hand (rockets 50, plasma 25, grenades 25: `START_GUN_W`) and the one-weapon rounds have rockets. Found
since (the log of 2026-10-10 20:45): the teacher's mouse was not his (retrained: `move_v15n`, which moves like the pros);
with that teacher a trial still failed at two strengths; a copy of the teacher from his inputs cannot strafe jump at all.
The teacher's lesson (section 4) is therefore not how v15 will be started again: what takes its place is the owner's
decision (BACKLOG B-211), and this manifest is rewritten before he is asked for a go.

| When | Decision |
|---|---|
| 10:38 | jumps and grenades/plasma: "definite yes"; attention for strategy: v16; the shares of his rounds as proposed |
| 11:51 | v14 ends on its save of 10:57; then v15 "with the new jump trainer and projectile work". He must "see all projectiles that he should be able to: rockets, plasma, grenades, within his field of vision", not be "cheating by wallhacks on projectiles", "distinguish projectiles and [understand] their splash damage, timer (grenades)", and be "*slightly* encouraged to use plasma and grenades. It should be ~5-10% max". "Audit the jump trainer as well; it seems there are key request mismatches." "Make sure it's ALL GOOD then give me a full v15 manifest" |
| 12:05 | Blood Run's stairs to the yellow armor (26): "we will add this". Demos of Toxicity and Campgrounds: yes. Rockets: "try parallel arms while getting everything else ready ... if nothing is obviously working we'll delay it for now". The lobber's timing and a fresh grenade measurement: "wait for it. include in v15" |
| 12:30 | Hektik and Cure: demos and jump maps too. "It might contaminate the purity of the held out map, but it's important that he understands how to move around these maps efficiently" |
| 13:08 | "He should get movement only practice on all 10 maps" |
| 15:38 | the answers to section 12: start from "v14 end"; the teacher's maps "OK"; movement-only time "OK - but monitor"; the one-weapon rounds "should be temporary just to introduce him to these weapons, monitor and turn them down once he starts to understand them"; the 36 jumps without tries: "Build first"; length and reports "TBD - ask me after we've settled the rest"; projectiles: "he should only know what's in view or what he can hear. He's allowed to \"suspect\" rockets, but that maybe is learned behavior instead" |
| 15:52 | "the jumps don't need to be 'exact' for repeating, he should be taught the general path, there's many ways to execute them" |
| 17:05 | **the go**: "you can start it now. Let it run until noon tomorrow. With mid way reports delivered at 10pm and 7am. Monitor and flag anything that doesn't look right, you can stop early if the metrics stop increasing, at your discretion. No need to send hourly reports between 10 and 7; just one summary of the night run from that period and a very brief \"Check <hour>: <changes>\"". "Keep the jumps without tries." Attention for v16 is begun in downtime |
| 17:17 | what the run is judged by: "maintaining speed/strafe jumping/circle jumping"; "rockets/plasma/grenades usage"; "decision making" ("really should be targeted for v16"). "If either of the first two don't succeed for this run we'll really need to reassess". (v15 has nothing new for rockets: told him at once) |
| standing | the last best network is in the league and first in every check; under 45% of the frags against it at two checks in a row: stop and tell him. Priorities: strafe jumping and keeping speed; rockets; plasma and grenades, the shotgun less; game awareness |

## 1. What changes from v14

v14 here is the third start as it ran to 10:57 (no teacher; every shot at its full price).

| # | | v14 | v15 | Switch |
|---|---|---|---|---|
| 1 | **The strafe-jumping teacher** | `move_v14d`: trained with any key on any frame (17 key changes a second); labels in item runs. It cost him Lost World within an hour | `move_v15i`: trained under his finger limits (keys read ten times a second, a finger at most every 150 ms, 8 key actions a second), on the pros' jumps of ten maps, a try that ends in lava priced at three arrivals. Labels in item runs and jump runs, **only on maps where a player who presses exactly its labels passes** (section 4): everywhere but Toxicity and Lost World's item runs | `--teacher`, `--teacher-skip`, `RUN_TEACHER=1` |
| 2 | **Jump runs** | none | 10% of his time on the six maps: alone, he begins a second or two of way before the take-off of one of the pros' jumps, the item behind it is his target. Tries at 137 of the 144 jumps in use | `JUMPS=1`, `JUMP_RUN_P=0.10`, `JUMP_ALL=1` |
| 3 | **Movement-only practice on the four other maps** | none | Campgrounds, Hektik, Toxicity, Cure: a simulator each of item runs and jump runs, no games; 7.6% of his time | `--move-maps`, `--move-matches 105` |
| 4 | **Enemy projectiles as a player sees them** | the two nearest; shown through walls if inside his view cone; anything within 400 units in any direction | the six nearest inside his view cone with a clear line from his eyes; each with its kind, a grenade's fuse left, the seconds until it passes closest and how close in its splash radii | `PROJ_SEE=1` |
| 5 | **Grenades and splash as measured in the game** | a grenade lost the rest of a frame at every bounce and came to rest 5 to 10% short; splash reached a player by one line to his middle | a bounce keeps its frame; splash tries his middle and four points beside it, as the game does (rockets too) | `GL_QL=1` |
| 6 | **Opponents that use what he does not** | the item runner in 25% of his games | scripted opponents in 30%: the runner 10, the lobber 8 (plasma in a fight, grenades and plasma at the exits on his way), the watcher 6 (holds a post with the rail), the holder 6 (keeps mega and red armor, comes for him after a frag) | `RUNNER_P=0.30`, `TRICKS=1`, `TRICK_P` |
| 7 | **Lives that begin with grenades or plasma in hand** | none | 5% of his lives in games (only a weapon the map has) | `START_GUN_P=0.05` |
| 8 | **One-weapon rounds** | none | 3.4% of his time (duels only): 15 seconds, both with the same weapon: grenades 3 in 8, plasma 3, shotgun 2 | `--kind-p 0.886,0,0.114,0` |
| 9 | **Grenade and plasma shots free; blind-fire rule** | every shot at its price | grenade and plasma shots cost nothing; rockets at the full price; a rocket with no enemy in view is judged by where it lands | `SHOT_W=gl:0,pg:0`, `BLIND_RULE=1` |
| 10 | **Item runs** | 30% of his time | 20% (jump runs take 10) | `ITEM_RUN_P=0.20` |
| 11 | **The control** | v13 in a quarter of the league's rollouts; checks against v13 | v13 and v14's end in a quarter of the rollouts; every check against v14's end first | `--anchor-p 0.25` |
| 12 | **Inputs** | 509 | 574: five for a jump ahead on his way, six for a grenade's arc with the launcher in hand, 54 for projectiles | |

Unchanged: the six maps of his games, the pay (nothing new is paid; a jump run pays as an item run), his aim and hand
limits, no teacher on the weapon key, the pay for speed (0.3), the league of his last eight selves.

## 2. His time

| | Share of all his playing time |
|---|---|
| Games on the six maps (duels 58%, threes 21%, fours 21%; a quarter of the seats old selves or a control; 30% of the ordinary rounds against a scripted opponent; 15% begin as a race for a big item) | 61.3% |
| One-weapon rounds (duels) | 3.4% |
| Item runs on the six maps (alone; half end in a fight) | 18.5% |
| Jump runs on the six maps | 9.2% |
| Item runs and jump runs on the four other maps (two to one) | 7.6% |

Movement-only practice a map: 4.6% of his time on each of the six, 1.9% on each of the four (208 players a map).

## 3. Maps and jumps

Games: Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged. Movement only: Campgrounds, Hektik,
Toxicity, Cure (they stay in the checks against the stand-in, where he has never played a game).

The pros' jumps, from their duels (`tools/pro_gaps.py`): every jump over a hole or up a ledge that a walker cannot
make, is a second or more slower at, or just makes from the very edge. In use: seen 20 times or more (30 for "just makes
it"), or marked by hand.

| Map | Demos | Jumps in use | A walker cannot / is slower / just makes it | Speed needed (least, middle, most) | He gets tries at | The teacher labels | Its pupil over, at those | v14's end over, himself |
|---|---|---|---|---|---|---|---|---|
| Blood Run | 250 | 11 | 0 / 3 / 7, and the stairs to yellow by hand | 329, 392, 451 | 11 | 10 | 86% | 42% |
| Aerowalk | 250 | 15 | 1 / 8 / 6 | 322, 368, 479 | 15 | 13 | 61% | 14% |
| Lost World | 250 | 19 | 0 / 3 / 16 | 329, 371, 528 | 19 | 19 | 74% | 37% |
| Sinister | 147 | 24 | 0 / 10 / 14 | 342, 378, 505 | 22 | 15 | 72% | 28% |
| Furious Heights | 150 | 20 | 0 / 4 / 16 | 310, 362, 514 | 20 | 19 | 53% | 21% |
| Battleforged | 149 | 5 | 0 / 4 / 1 | 356, 420, 564 | 5 | 4 | 64% | 15% |
| Campgrounds | 6 | 12, by hand | 0 / 4 / 8 | 388, 416, 608 | 12 | 9 | 38% | 19% |
| Hektik | 144 | 14 | 0 / 4 / 10 | 340, 378, 425 | 14 | 11 | 70% | 44% |
| Toxicity | 87 | 11 | 0 / 9 / 2 | 320, 386, 416 | 8 | 6 | 65% | 6% |
| Cure | 129 | 13 | 0 / 8 / 5 | 374, 432, 515 | 11 | 11 | 48% | 8% |
| **All** | | **144** | | | **137** | **117** | | **23%** |

- Campgrounds has six demos on the site; its twelve jumps are marked by hand (the bridge to the rail is entry 9).
  Blood Run's stairs to the yellow armor (26) is in.
- **He gets tries at 137 of the 144** (owner, 15:38: "Build first"). A try begins a run-up of way before the take-off and
  its target is an item behind the landing. 82 jumps lie on an item's fastest way. For 55 more his ways are made to take
  the jump: first by making the jump free on the way to the two items behind its landing; where that finds no start, by
  leading him to the landing first and from there to the nearest item, beginning as far back as the map allows. Seven
  have none: the walking map has no standing place at their take-off or their landing (ledges and boxes only a jump
  reaches: Sinister 11 and 12, Toxicity 5, 12 and 13, Cure 11 and 15). Every jump is tried as often as any other.
- **The path, not the execution** (owner, 15:52: "the jumps don't need to be 'exact' for repeating, he should be taught
  the general path, there's many ways to execute them"). He is paid for the way gained toward the item, never for a
  spot; the circles round the pros' take-off (120 units) and landing (110) count "over" for the log and tell when a try has
  ended in the gap.
- **The teacher's labels in jump runs** (`tools/jump_labels.py`, `sim/jump_labels.json`): asked for the landing, the
  teacher's own way goes round 20 of the jumps from where his tries begin (a player pressing its labels alone comes to
  the take-off in under half of the tries). There it gives no labels and he learns the try by the pay alone. At the other
  117 its labels stay, also where its pupil goes for the jump and seldom lands it (16 jumps under 15%, Aerowalk's
  red-armor gap among them: 8%): they show the way.
- Not opened in his games yet: in games his ways stay a walker's. A jump is opened (`JUMP_OPEN`, built) when he is
  measured to make it in jump runs.

## 4. The teacher (the audit the owner asked for)

**What was wrong.** The movement network of v14 was trained with free hands: it changes keys 16.9 times a second, the
strafe key alone 12.1 times. His hand reads the keys ten times a second, a finger acts at most every 150 ms, the hand
has 8 key actions a second. A player pressing exactly its labels with his hands on Lost World: 46 points of lava damage
a minute, 64% of the key requests refused by his own hand.

**A second fault, found today in the jump runs.** Asked for the item behind a jump, the teacher's own ways went round
some jumps (Blood Run 7: over 0 of 89 tries with its labels alone). In every jump run it is now asked for the jump's
landing until he is over it, as in its own tries, then for the item: Blood Run's jumps 72% -> 88% over with its labels
alone, Aerowalk's 48% -> 59%.

**The new teacher.** `move_v15i`: v14's movement network trained on for 90 minutes (72 million steps) under his finger limits, with the
pros' jumps as links of its walking map and their landings as goals (half of its tries begin before a take-off): 45
minutes on seven maps, 45 on all ten with a try that ends in lava priced at three arrivals. In its own task 83% of its
tries arrive, in 0.91 of a walker's time; 1.3% end in lava; 69% of its jump tries get over.

**Its pupil, map by map** (`tools/label_check.py`: a player alone who presses exactly its labels with his hands):

| Map | Item runs: items a minute | Speed | Fast in the air | Lava or slime damage a minute | Jump runs: over, at the jumps it labels | Lava | Its labels in v15 |
|---|---|---|---|---|---|---|---|
| Blood Run | 8.9 | 374 | 44% | 0 | 86% | 0 | item runs, jump runs |
| Aerowalk | 13.3 | 326 | 26% | 0 | 61% (the red armor's gap: 8%) | 0 | item runs, jump runs |
| Lost World | 7.4 | 340 | 32% | **63** | 74% | 4 to 10 | **jump runs only** |
| Sinister | 9.4 | 338 | 32% | 0 | 72% | 0 | item runs, jump runs |
| Furious Heights | 6.6 | 345 | 39% | 0 | 53% | 0 | item runs, jump runs |
| Battleforged | 9.2 | 364 | 37% | 0 | 64% | 0 | item runs, jump runs |
| Campgrounds | 4.8 | 370 | 44% | 0 | 38% (the bridge to the rail: 0%) | 0 | item runs, jump runs |
| Hektik | 10.9 | 354 | 39% | 0 | 70% | 0 | item runs, jump runs |
| Toxicity | 9.7 | 295 | 31% | **204** | 65% | **127** | **none** |
| Cure | 8.6 | 309 | 30% | 0 | 48% | 0 | item runs, jump runs |
| *v14's end himself, the six maps* | 7.5 | 301 | 10% | | | | |
| *v14's end himself, Lost World* | 6.8 | 306 | 9% | 22 | 41% | 8 | |
| *v14's teacher, Lost World* | 7.3 | 327 | | 46 | | | |

Of the key presses its labels ask for, his hand refuses 41 to 59% (v14's teacher: 64%): it asks more often than a
hand can act, and what gets through is what the table measures.

**Where it gives labels.** Everywhere but Toxicity (no key labels in its runs: he learns that map by the pay alone)
and Lost World's item runs (three times his own lava damage; in its jump runs the labels stay: 76% over against his
41%, lava as his own). A map without the teacher's labels gets no walking labels either: until today the walking
teacher's keys ("forward along the way") would have come back there (`--teacher-skip toxicity,lostworld:item`).
The lava on Lost World is on the way to the rockets: a fifth of its pupil's trips there end in it. Pricing lava higher
in the teacher's training did not cure it, and his aim limits are not the cause (without them: 53). Open (B-208).

Its weight is 0.3, rising from nothing over the first two hours (section 9: with one hour the first updates moved him
more than v14's teacher start did), into the shared layers, as decided for v14.

## 5. What he sees of projectiles

| The owner's point | v15 | Tested |
|---|---|---|
| "see all projectiles that he should be able to ... within his field of vision" | the six nearest enemy rockets, grenades and plasma balls inside his view cone, within 1,500 units | Aerowalk, six plasma balls in view: all six (v14's rule: two) |
| "isn't cheating by wallhacks" | a projectile is shown only with a clear line from his eyes; nothing behind his back | a rocket behind a wall and a grenade 200 units behind him: neither shown (v14's rule: both) |
| "distinguish projectiles" | each has its kind (rocket, grenade, plasma), where it is and how it moves | - |
| "understands their splash damage, timer" | a grenade's fuse left; the seconds until it passes closest to him; how close, in its own splash radii (rocket 120 units, grenade 150, plasma 20) | a grenade 1.5 seconds old: fuse 0.4 |

What it costs v14's end at once (24 games a map against the stand-in, the new sight and the grenade fixes off and on):
Blood Run 69% and 71% of the frags, Aerowalk 84% and 81%, Sinister 74% and 73%: nothing.

Grenades measured in the game (`plugins/weaponlab.py` set 4): launch 700 units a second with the loft, fuse 2.50 s, a
bounce keeps 0.65: as the simulator has them. Where a grenade ends, units from the shooter (the game / v14's simulator /
v15's): level 824 / 730 / 864; 20 degrees down 552 / 507 / 528; 45 down 583 / 533 / 572; 70 down 366 / 409 / 425.

## 6. Grenades and plasma: how much

Nothing pays him for holding or firing them. What v15 does: their shots are free, 5% of his lives begin with one in
hand, 3.4% of his time is one-weapon rounds, and the lobber fights him with plasma and grenades. Against the lobber
v14's end takes 70 to 87% of the frags; 58 to 100% of the lobber's own frags are now by plasma (it was 0 to 25% before
it fought with it).

The owner's ceiling ("~5-10% max") is read as: his time with grenades or plasma in hand in games (not in one-weapon
rounds). It is in every update's log (`v15.in_hand_games`) and in the hourly brief. v14's end: 0.0%.

## 7. What he is shown and paid

574 inputs (the 65 new ones at zero weight at the start). The pay is v14's. A jump run pays as an item run does: the
way gained on a running best, the pickup. A try that ends without the item gives back what its way paid, so walking to
the edge and falling earns nothing.

## 8. Start, league, checks

- **Start**: v14's end (the save of 10:57), widened to 574 inputs; prepared in `data/sim_runs/duel_gru_v15`.
- **League**: his last eight selves; in a quarter of the rollouts v13 or v14's end.
- **Checks** (`eval_loop_v15.py`, beside the run): every checked save plays v14's end on Blood Run, Aerowalk and Lost
  World (32 ten-minute duels a map), then the stand-in on all ten maps. Under 45% against v14's end at two checks in a
  row: the run stops and the owner is told.
- **Hourly brief**: items and weapons first; rockets; grenades and plasma in hand and the ceiling; jumps over, per map
  and jump; item runs by map (items a minute, speed, lava) on all ten maps; his frags against the lobber, the watcher,
  the holder.
- **Real games against Nightmare**: before (v14's end, section 9) and after, on a quiet PC.

## 9. What was checked

| | Result |
|---|---|
| The simulator with every v15 switch off against main's (fixed runs, both modules) | identical, after every change (the last at 13:29) |
| The group module against the duel module at two players | identical over 3,000 frames |
| A second reader's review of the v15 code | nine findings; all that mattered fixed (a jump try's end rules, a shared item ending other seats' tries, links from dead spots, stale state after a new try, a plasma gun on a map without one, walking to the edge paid) |
| The trainer end to end at a fiftieth of its size, everything on | updates come; every counter fills; the scripted opponents are drawn (they were not: `TRICK_P` was read only in the old yard rounds) |
| The trainer at full size, ten minutes | 14:45 to 14:55, from the branch's working copy, everything on: four updates in ten minutes, 27,400 frames a second (v14: 26,400), the card at 12.1 of its 13.1 GB, no stall. Jump runs 11 to 13% of all frames, about 1,100 tries an update, 18 to 21% over; grenades or plasma in hand 1 to 3% of his time in games (the lives that begin with one). The policy's step per update: 0.04, 0.27, 0.14, 0.05 with the teacher rising over one hour, most of it on the view (v14's teacher start: 0.17, 0.17, 0.06, 0.04, and his aim held). **So the teacher rises over two hours**; so set, and run again from the merged repo itself (15:20, five minutes): the steps were 0.04 and 0.05, 26,400 frames a second |
| Projectile sight | section 5 |
| Grenades | section 5 |
| The teacher | section 4 |
| The tries built on the owner's "Build first" (16:00) | his own rate over all 137 jumps before any training: 23% (Toxicity 6%, Hektik 44%); the teacher's pupil 38 to 86% at the jumps it labels; switched off the simulator is still main's of the morning in fixed runs; the trainer at full size from the repo: three updates in six minutes, 27,400 frames a second, tries at all 137 jumps in every update, the policy's step 0.04, 0.05 and 0.10 with the teacher rising over two hours (v14's teacher start: 0.17 twice) |
| v14's end against Nightmare in real games | 14:55 to 15:17, two ten-minute games a map on a quiet PC: Blood Run 11-4 and 17-8, Lost World 4-4 and 7-2, Aerowalk 1-0 and 5-1 (the game's bot stands still there). v13 had 14-4, 11-6, 10-3; 8-5, 6-4, 9-5. [REPORT_v14.md](REPORT_v14.md) |

## 10. Known, not right yet

- **7 of the 144 jumps have no tries for him**, and the teacher gives no labels at 20 (section 3); a way with two of the
  pros' jumps is judged by the first.
- **His view stops at 85 degrees down, the game's at 87.9** (B-207): a grenade at his own feet lands 107 units away in
  the simulator, 42 in the game.
- **One-weapon rounds exist in duels only**: 3.4% of his time, not the 8% first proposed.
- **The servers' side**: the plugins build the 574 inputs with the simulator's own code (they keep a missile's age for
  the fuse); to be set beside the simulator with a recording before any v15 network goes on a server.
- **Jumps are not opened in his games** at the start (section 3).
- **The teacher fails on Toxicity and in Lost World's item runs** (section 4): no labels there.
- **Rockets**: nothing in v15 works on them (section 12).

## 11. The run as it would be started

`launch_v15.py start <end hour>` (the trainer detached, saving every ten updates; `eval_loop_v15.py` beside it). The
simulator's switches, then the trainer's line:

```
ARENA_ROOMS=yard ARENA_SETS=mg ARENA_STACK=0 RUNNER_P=0.30 ITEM_RUN_P=0.20 COLLECT_FIGHT_P=0.5 DRILL_MIX_P=0.7
INTENT_HOLD=8 STACK_PAY=1.0 STACK_WPN=1.0 STACK_BARE=0.5 STACK_LOW=1.0 STACK_TEACH=1 STYLE_P=0.75 STYLE_DMG=0.5
STYLE_BAND=0 PRO_WEAPON=1 PRO_ITEMS=1 SPAWN_TEACH=1 ITEM_BELIEF=1 SHOT_COST=0.10 AMMO_PACKS=0 ARMOR_COST=0.33
CONTEST_P=0.15 AIM_LEVEL=3 PRO_JUMP=1 KEY_RATE=8 GROUND_SENSE=1 KNOW_PAY=0.5 PACE_PAY=0 TEACH_KEYS_ONLY=1 DROPS=1
SHOT_MASK=1 LAVA=1 WALK_FIX=1 QL_MOVE=1 ITEM_DROP=1 SOLIDS=1 PRO_WAYS=1 NEAREST=1 SPEED_PAY=0.3 SPEED_PAY_RUN=0.3
RUN_TEACHER=1 STACK_KEYS=0 SHOT_W=gl:0,pg:0 TEACH_FREE=0 BLIND_RULE=1 HIGH_PAY=0 RULE_WALK=1 JUMPS=1 JUMP_ALL=1
JUMP_RUN_P=0.10 START_GUN_P=0.05 TRICKS=1 TRICK_P=lobber:0.267,watcher:0.2,holder:0.2 PROJ_SEE=1 GL_QL=1 TEACH_BEST=0

sim\train_duel_rnn.py --env duel_env_ffa --group 2,3,2,4,2 --map
bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged --workers 24 --matches 210 --steps 384 --run
duel_gru_v15 --resume --minutes <minutes> --gamma 0.999 --react-ms 100 --acquire-ms 200 --kind-p 0.886,0,0.114,0
--drill-weapons gl,gl,gl,pg,pg,pg,sg,sg --lab-p 0,0,1 --arena-len 180 --bot-p 0 --teacher move_v15i --teach 0.3
--teach-minutes 100000 --teach-warm 120 --weapon-teach 0 --weapon-teach-minutes 1000000 --minibatches 70 --lr 1e-4
--lr-minutes 1440 --lr-end 1.0 --lam 0.98 --close-floor 0 --loadout-p 0,1,0,0 --close-minutes 1 --intent-teach 2.0
--intent-teach-minutes 1000000 --dmg-taken-w 1.0 --ent-coef 0.005 --ent-heads 0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1
--dmg-reward 0.005 --item-reward 0.75 --item-loss 0.5 --intent-seek 1.0 --intent-seek-minutes 0 --stack-p 0
--near-item-p 0 --kl-heads 10 --teach-trunk 0.05 --teach-trunk-move 1.0 --anchor-p 0.25 --teacher-skip
toxicity,lostworld:item --move-maps campgrounds,hektik,toxicity,cure --move-matches 105 --fade-start <the lineage's
minute at the start>
```

24 simulators of the six maps (10,060 players) and four movement-only ones (832): 10,892 players, 384 steps a
rollout, 70 minibatches (156 sequences each, as v14's 157). `--fade-start` is the lineage's minute at the start
(5,839), kept in `fade_start.txt` for every resume.

## 12. For you to decide (answered 15:38 and 17:05: section 0; point 6 is built: section 3)

1. **The start**: v14's end (my advice at 14:15: level with v13 on v13's three maps, ahead on the three new ones, and
   trained in the corrected simulator), with v13 kept in the league. The folder is prepared so.
2. **The teacher's maps** as in section 4: no labels on Toxicity nor in Lost World's item runs.
3. **Movement-only time on the four maps**: 7.6% of his time (1.9% a map, against 4.6% a map on the six). Doubling it
   takes four points from his games.
4. **The ceiling for grenades and plasma**: I read "~5-10% max" as his time with either in hand in games. If it is
   over 10% at two hourly briefs in a row I would take the lives that begin with one in hand to nothing and the
   one-weapon rounds out, at a save, and tell you. Say if you want to be asked first.
5. **Rockets** (your second priority): the side arm with rockets at a fifth of the price and rocket-only rounds ran 128
   minutes at half size: rockets in hand 19.5% (v14's end 18%), 48%, 47% and 50% against v13. Nothing obviously
   working, so by your rule they are not in v15. To think about for v16.
6. **36 jumps without tries for him** (section 3): start so, or wait for tries with the landing as their goal (about two
   hours to build and test).
7. **Length and reports**: as v14 unless you say otherwise: an hourly brief, a mid-run report, to the next afternoon.
8. Which of Toxicity's entries is your "red to mega, two boxes" (1, 4 and 8 are at the mega; he gets tries at 1 and 8).
9. With the fair sight he sees nothing behind his back. v14's rule also showed anything within 400 units in any
   direction; I dropped it as not a player's sight. His hearing is unchanged.

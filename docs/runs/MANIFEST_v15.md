# `duel_gru_v15`: the manifest (2026-10-10, for the owner's go; not started)

What v15 has in its rounds, what he is shown and paid, what changes from v14, how each new thing was tested, what is
known not to be right yet, and what is the owner's to decide. The run starts only on his word. The network it starts
from: [REPORT_v14.md](REPORT_v14.md). The day's log: [2026-10-10](../results/2026-10-10.md). Jump pictures and tables:
[../design/jumps/](../design/jumps/).

**Which run is which.** v13 is on the public server. v14 is the run of last night and this morning (three starts; the
third began at 08:06 and was ended at 11:52); "v14" or "v14's end" is its save of 10:57. **v15 is the next run and has
not started**: it begins from v14's end with everything below.

## 0. The owner's decisions (2026-10-10)

| When | Decision |
|---|---|
| 10:38 | jumps and grenades/plasma: "definite yes"; attention for strategy: v16; the shares of his rounds as proposed |
| 11:51 | v14 ends on its save of 10:57; then v15 "with the new jump trainer and projectile work". He must "see all projectiles that he should be able to: rockets, plasma, grenades, within his field of vision", not be "cheating by wallhacks on projectiles", "distinguish projectiles and [understand] their splash damage, timer (grenades)", and be "*slightly* encouraged to use plasma and grenades. It should be ~5-10% max". "Audit the jump trainer as well; it seems there are key request mismatches." "Make sure it's ALL GOOD then give me a full v15 manifest" |
| 12:05 | Blood Run's stairs to the yellow armor (26): "we will add this". Demos of Toxicity and Campgrounds: yes. Rockets: "try parallel arms while getting everything else ready ... if nothing is obviously working we'll delay it for now". The lobber's timing and a fresh grenade measurement: "wait for it. include in v15" |
| 12:30 | Hektik and Cure: demos and jump maps too. "It might contaminate the purity of the held out map, but it's important that he understands how to move around these maps efficiently" |
| 13:08 | "He should get movement only practice on all 10 maps" |
| standing | the last best network is in the league and first in every check; under 45% of the frags against it at two checks in a row: stop and tell him. Priorities: strafe jumping and keeping speed; rockets; plasma and grenades, the shotgun less; game awareness |

## 1. What changes from v14

v14 here is the third start as it ran to 10:57 (no teacher; every shot at its full price).

| # | | v14 | v15 | Switch |
|---|---|---|---|---|
| 1 | **The strafe-jumping teacher** | `move_v14d`: trained with any key on any frame (17 key changes a second); labels in item runs. It cost him Lost World within an hour | `move_v15i`: trained under his finger limits (keys read ten times a second, a finger at most every 150 ms, 8 key actions a second), on the pros' jumps of ten maps, a try that ends in lava priced at three arrivals. Labels in item runs and jump runs, **only on maps where a player who presses exactly its labels passes** (section 4): everywhere but Toxicity and Lost World's item runs | `--teacher`, `--teacher-skip`, `RUN_TEACHER=1` |
| 2 | **Jump runs** | none | 10% of his time on the six maps: alone, he begins a second or two of way before the take-off of one of the pros' jumps, the item behind it is his target. Tries at 108 of the 144 jumps in use | `JUMPS=1`, `JUMP_RUN_P=0.10`, `JUMP_ALL=1` |
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

| Map | Demos | Jumps in use | A walker cannot / is slower / just makes it | The pros make them, an hour | Speed needed (least, middle, most) | He gets tries at |
|---|---|---|---|---|---|---|
| Blood Run | 250 | 11 | 0 / 3 / 7, and the stairs to yellow by hand | 57 | 329, 392, 451 | 8 |
| Aerowalk | 250 | 15 | 1 / 8 / 6 | 102 | 322, 368, 479 | 13 |
| Lost World | 250 | 19 | 0 / 3 / 16 | 53 | 329, 371, 528 | 16 |
| Sinister | 147 | 24 | 0 / 10 / 14 | 105 | 342, 378, 505 | 20 |
| Furious Heights | 150 | 20 | 0 / 4 / 16 | 96 | 310, 362, 514 | 16 |
| Battleforged | 149 | 5 | 0 / 4 / 1 | 20 | 356, 420, 564 | 4 |
| Campgrounds | 6 | 12, by hand | 0 / 4 / 8 | - | 388, 416, 608 | 4 |
| Hektik | 144 | 14 | 0 / 4 / 10 | 118 | 340, 378, 425 | 13 |
| Toxicity | 87 | 11 | 0 / 9 / 2 | 85 | 320, 386, 416 | 6 |
| Cure | 129 | 13 | 0 / 8 / 5 | 104 | 374, 432, 515 | 8 |
| **All** | | **144** | | | | **108** |

- Campgrounds has six demos on the site; its twelve jumps are marked by hand (the bridge to the rail is entry 9).
  Blood Run's stairs to the yellow armor (26) is in.
- **He gets tries at 108 of the 144.** A try needs a way to an item that takes the jump, with a run-up before it. 82
  had one; for 26 more the jump is made free in a second set of his ways so that the way to the item behind its landing
  takes it (`JUMP_ALL`). The 36 left lead away from every item or have no room for a run-up; the teacher practises all
  of them (in its task a landing is a goal).
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

| Map | Item runs: items a minute | Speed | Fast in the air | Lava or slime damage a minute | Jump runs: over | Lava | Its labels in v15 |
|---|---|---|---|---|---|---|---|
| Blood Run | 8.9 | 374 | 44% | 0 | 91% | 0 | item runs, jump runs |
| Aerowalk | 13.3 | 326 | 26% | 0 | 58% (the red armor's gap: 18%) | 0 | item runs, jump runs |
| Lost World | 7.4 | 340 | 32% | **63** | 76% | 10 | **jump runs only** |
| Sinister | 9.4 | 338 | 32% | 0 | 60% | 0 | item runs, jump runs |
| Furious Heights | 6.6 | 345 | 39% | 0 | 53% | 0 | item runs, jump runs |
| Battleforged | 9.2 | 364 | 37% | 0 | 64% | 0 | item runs, jump runs |
| Campgrounds | 4.8 | 370 | 44% | 0 | 22% (the bridge to the rail: 0 of 80) | 0 | item runs, jump runs |
| Hektik | 10.9 | 354 | 39% | 0 | 66% | 0 | item runs, jump runs |
| Toxicity | 9.7 | 295 | 31% | **204** | 53% | **127** | **none** |
| Cure | 8.6 | 309 | 30% | 0 | 62% | 0 | item runs, jump runs |
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
| The trainer at full size, ten minutes | 14:45 to 14:55, from the branch's working copy, everything on: four updates in ten minutes, 27,400 frames a second (v14: 26,400), the card at 12.1 of its 13.1 GB, no stall. Jump runs 11 to 13% of all frames, about 1,100 tries an update, 18 to 21% over; grenades or plasma in hand 1 to 3% of his time in games (the lives that begin with one). The policy's step per update: 0.04, 0.27, 0.14, 0.05 with the teacher rising over one hour, most of it on the view (v14's teacher start: 0.17, 0.17, 0.06, 0.04, and his aim held). **So the teacher rises over two hours** |
| Projectile sight | section 5 |
| Grenades | section 5 |
| The teacher | section 4 |
| v14's end against Nightmare in real games | 14:55 to 15:17, two ten-minute games a map on a quiet PC: Blood Run 11-4 and 17-8, Lost World 4-4 and 7-2, Aerowalk 1-0 and 5-1 (the game's bot stands still there). v13 had 14-4, 11-6, 10-3; 8-5, 6-4, 9-5. [REPORT_v14.md](REPORT_v14.md) |

## 10. Known, not right yet

- **36 of the 144 jumps have no tries for him** (section 3); a way with two of the pros' jumps is judged by the first.
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

## 12. For you to decide

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

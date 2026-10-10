# `duel_gru_v14`: the manifest, decided by the owner on 2026-10-09 (not started: "later tonight", on his go)

What the owner called on 2026-10-09, what is built and how it was tested, the run as it would be started, and what is
his to decide. The run starts only on his go, after his duel against v13.
Sources: [RESULTS.md](RESULTS.md) entries of 2026-10-09 (09:05 the calls; 10:15 the map audit; 12:20 v13's end; 15:30 the
preparation and the real games), [REPORT_v13.md](REPORT_v13.md), [BACKLOG.md](BACKLOG.md) B-163 to B-182.

## 0. The owner's decisions (2026-10-09, after his review)

**The third start (2026-10-10 08:06, the owner's go at 07:46)**. The second start made him weaker than v13 as a duelist
([MIDRUN_v14.md](MIDRUN_v14.md)) and was stopped at 07:42 (kept as `duel_gru_v14_try2`). The third begins from the same
starting network and differs from what is written below in four things:

1. **The control.** v13 (the starting network) plays the league's players in a quarter of the rollouts (`--anchor-p 0.25`,
   `snapshots/anchor_v13.pt`) and every checked save plays it head to head on Blood Run and Aerowalk before the
   stand-in's maps. Under 45% of the frags against it at two checks in a row: the run stops and the owner is told. The
   owner: "this should be standard going forward, continue to check against the last best version + new iterations".
2. **Weapons as v13 had them at its end** (rows of section 3 and 4 do not apply): no weapon teacher (`--weapon-teach 0`),
   every shot at its full price (`SHOT_W` unset), no rule for rockets with no enemy in view (`BLIND_RULE=0`). The owner:
   "acceptable for now, he does need to learn how to use rockets more though. so let's continue to monitor this".
3. **The strafe-jumping teacher in two phases**: off for the first two checks (about 90 minutes), then as in the second
   start (0.3 in item runs, rising over an hour, into the shared layers). The owner: "he needs to learn to strafe jump
   to get places though".
4. **The pay for speed** is 0.3 in games as in item runs (raised in the second start).

Everything else as below: the six maps, the simulator set right, item runs 30% of the rounds, no key labels in games.

**Changed in the run (2026-10-09 22:53, RESULTS 23:15)**: the first try, with every teacher held back from the shared
layers (`--teach-trunk 0.05`), lost half his duel strength in 90 minutes and taught no strafe jumping; it is kept as
`duel_gru_v14_try1`. The run was started again from the same start with the movement teacher alone let into the shared
layers (`--teach-trunk-move 1.0`), everything else as below.

**Changed in the run, 2026-10-10** (the two settings the owner left to be adjusted, each right after a save, the save
kept): at 01:18 the teacher's weight held at 0.3 to the end (it was set to fade to nothing over eight hours; RESULTS
01:30); at 02:50 the teacher's weight 0.3 -> 0.5 and the pay for speed in games 0.1 -> 0.3 (RESULTS 03:00).

"1. 0.3 is good  2. 30% is good  3. no key labels good  4. yes  5. yes  6. tbd: We will start the run later tonight."
So rows 1 to 5 stood as proposed; that evening he raised row 4 (".1/.3? And if it's too high/low you can adjust as the
training progresses"). The run's length and report hours are set at the start.

| # | Decision | Decided | What the tests say |
|---|---|---|---|
| 1 | **How hard the strafe-jumping teacher pushes** | weight 0.3, rising from nothing over the first hour, gone after eight hours | At 0.5 from the first frame his policy moves 0.60 in one update, nearly all of it on the view (v13 started at 0.021). Rising over an hour, every update stays at 0.012 to 0.029, about the size of an update with no teacher at all (two runs of it, 25 and 12 minutes). His aim was the same in every test (on target 31 to 32% of the time in view). His item runs dip while his keys change (6.2 -> 4.5 -> 5.3 items a minute in 25 minutes) and his time fast in the air starts to rise (9% -> 11%). The other ways: 0.05 flat (slower), 0.5 flat (yesterday's trial: 188 -> 320 units a second in 21 minutes, with the big first step) |
| 2 | **Share of item runs** | 30% of his time (v13: 20%) | more of them is more movement practice and less fighting |
| 3 | **No key labels in games** | none | v13 had the walking teacher's keys in games for four hours ("forward along the way"); strafe jumping has to replace exactly that. His view and fire in games stay his own either way |
| 4 | **Size of the pay for speed** | 0.1 in games, 0.3 in item runs (per second at 480 straight along the way); first decided 0.06 and 0.15, raised by the owner in the evening | at 0.3 a strafe-jumping player earns about 2.0 to 2.8 a minute in item runs beside about 7 from the runs themselves. He allows a change during the run if it proves too high or too low: watched every hour (pay per player-minute, the item runs' items a minute and speed, lava and fall damage, pickups and weapons in games); a change is made right after a save and logged in RESULTS |
| 5 | **Rocket numbers** | price a fifth of today's; free within 600 units of where he thinks the enemy is or on the enemy's likely way; a wasted blind rocket 6 damage points; hitscan pre-fire 150 units for 1.5 s; weapon teacher 0.2 to the end | section 3 |
| 6 | **Run length, report hours** | to be set at the start (proposed as v13: to the next afternoon, an hourly brief, a mid-run report) | - |
| 7 | **Standing higher (B-160)**, new that evening | no pay: `HIGH_PAY` stays off. An hourly check, reported as something to watch. Owner: "Keep the height as an hourly check, don't act on it yet, but report it as something to monitor. I don't think we need to reward/penalize him for it quite yet, this seems to be the most possible behavior to be learned through practice." | the owner against v13 on Aerowalk: "fights from the low ground" (Bobby lower 61% of the time, higher 15%; the same against the game's Nightmare bot there, 67% and 15%; against the stand-in he is the higher one more often on seven of the ten maps, the lower one on Cure, Toxicity and Aerowalk). In self-play the damage dealt from above (11 to 15%) is about that dealt from below: with rail and lightning height earns nothing; rockets and Aerowalk's red armor, both in v14, are what should bring him up. Watched: the trainer's `v14.height` and `lower` / `higher` per map in the evaluation loop. The switch is built and tested should he want it later |

Decided today and built in: the maps and the validation maps (section 1), the teacher, the pay for speed, lead reading,
the shot rules, the map fixes; real games against Nightmare before and after the run, none in the middle.

## 1. Maps

Owner: train on Blood Run, Aerowalk, Lost World, Sinister, Furious Heights and Battleforged; validate on Campgrounds,
Hektik, Toxicity and Cure ("Yep do it"; "let's add silence, toxicity, cure and dismemberment as additional validation
maps", then Silence out for its door and Dismemberment because he does not know it). arena1 is dropped.

Why Battleforged in and Campgrounds out: the demo archive has 283 Battleforged duels in today's format and 10 of
Campgrounds.

The starting line: v13's network in v14's simulator against the stand-in, 32 ten-minute duels a map.

| Map | Role | Share of the frags (95%) | Won / drawn / lost | Pro duels used | The stand-in there: speed, stuck |
|---|---|---|---|---|---|
| Blood Run | train | 71% (67%-75%) | 30 / 1 / 1 | 1,066 | 285, 4% |
| Aerowalk | train | 82% (79%-84%) | 32 / 0 / 0 | 978 | 270, 3% |
| Lost World | train | 92% (89%-94%) | 32 / 0 / 0 | 1,222 | 249, 8% |
| Sinister | train, new | 73% (69%-77%) | 31 / 1 / 0 | 147 (new) | 242, 14% |
| Furious Heights | train, new | 46% (42%-51%) | 12 / 4 / 16 | 150 (new) | 276, 5% |
| Battleforged | train, new | 63% (56%-69%) | 24 / 2 / 6 | 149 (new) | 261, 4% |
| Campgrounds | validation | 33% (26%-42%) | 9 / 2 / 21 | none in today's format | 262, 5% |
| Hektik | validation | 48% (43%-52%) | 14 / 3 / 15 | not fetched | 255, 8% |
| Toxicity | validation | 66% (63%-70%) | 21 / 1 / 10 | not fetched | 216, 19% |
| Cure | validation | 45% (42%-48%) | 12 / 4 / 16 | not fetched | 257, 7% |

- He holds his own on maps he never saw, loses on the largest, and where the stand-in is not sound (Toxicity) the number
  flatters him. On Lost World the stand-in still dies in the lava.
- **The duel check beside the run**: these ten maps, 32 games each per check, about every 45 minutes from the first hour;
  64 a map at the end. A check puts a map within 3 to 5 points; three pooled within 2.7. Nothing in it feeds the
  training. On the six trained maps the stand-in is the same scripted walker he meets in a quarter of his training
  games; the four validation maps are the cleaner test.
- Every big item on the ten maps has a way from every live point of its walking map. None of the ten has a door on a
  walked way. Toxicity has acid and deep water, Cure a pool with waist-deep water: he has never had to swim.
- The pros on the three new training maps are in the air 44 to 45% of their moving time at 408 to 418 units a second.

## 2. Speed and strafe jumping

Owner: "strafe jumping is absolutely crucial to the game, he needs to learn it asap"; movement rounds "on the duel maps
not the testlab ... figuring out routes between items, practicing jumps"; "320 -- 480 pay for speed bonus (flat above
480), it can be aggressive at first"; "yes to additional inputs".

**The teacher** is a separate small network (48 inputs, about 80,000 weights) that knows one thing: getting from one item
to the next as fast as possible. It is paid for nothing but time saved, and it strafe-jumps. In his item runs (alone on
the map, from item to item) it is asked every frame what it would press to reach his target; its movement keys, jump and
mouse turn are shown to him as the right answer, and an extra term in his training pulls his own outputs toward them,
with a weight that fades to nothing. It never plays for him and is not consulted in games. It learned with free hands;
he has to do it through his own.

| | What is built | Switch | Tested |
|---|---|---|---|
| The teacher network | `move_v14d`: the strafe-jumping network of 2026-10-03, trained on in the corrected simulator on the six maps and Campgrounds (the game's step height and wading, solid pieces, lava ends a try and reads as a pit, a far fall costs half a second, a teleporter is shown as its entrance). A network from scratch was dropped: after half an hour it was where the old one had been after five minutes | `sim/train_move.py --v14` | it reaches 98% of its trips and is above running speed 84% of its moving time: Blood Run, Aerowalk, Battleforged 99%, Furious Heights 99%, Sinister 98%, Lost World 94% |
| Its labels in item runs | keys, jump and view; where it has no way (Aerowalk's red armor: the pros' jump) the walking teacher's keys stay | `RUN_TEACHER=1`, trainer `--teacher`, `--teach 0.3`, `--teach-warm 60`, `--teach-minutes 480` | a pupil pressing only the labels through today's hands: Blood Run 357 units a second and 8.4 items a minute (the walking teacher alone: 304 and 6.8), Battleforged 349 and 8.7, Furious Heights 330, Sinister 323, Lost World 323. On Lost World the pupil clips the lava about once a minute |
| No key labels in games | the walking teacher's keys for a bare or low player are off | `STACK_KEYS=0` | - |
| Pay for speed | for every stretch of new ground on the way to his chosen item, by the speed he covers it at: nothing at 320, full from 480, flat above. In item runs, and in games with nobody seen for 1.5 s (there it is part of the trip's pay: a dropped trip gives it back). Paid per stretch of ground, not per second: a zigzag or a detour at speed earns nothing more. Replaces the pace pay | `SPEED_PAY=0.1`, `SPEED_PAY_RUN=0.3` (owner, evening; first 0.06 and 0.15) | the pupil above earns 2.0 to 2.8 a player-minute in item runs (scaled from the 1.0 to 1.4 measured at 0.15) |
| Four inputs | his speed; the angle from his view to the way he moves (sine and cosine); speed gained in the last 100 ms | the first four of `N_V14` | exact against the simulator's state |

**The dry runs** (v14's settings on scratch copies of the starting network, ten to thirty minutes each):

| Teacher's weight | Policy step of the first update (the view's part) | Largest later step | On target in view | Item runs at the end |
|---|---|---|---|---|
| none | 0.020 (0.008) | 0.014 | 31% | 5.9 items a minute |
| 0.03 | 0.032 (0.015) | 0.022 | 32% | 4.9 |
| 0.05 | 0.038 (0.019) | 0.027 | 31% | 4.8 |
| 0.5 | **0.601 (0.439)** | 0.095 | 32% | 3.7 after 9 minutes |
| rising to 0.3 in 20 minutes | 0.021 | 0.087 | 31% | 4.2 after 29 minutes |
| **rising to 0.3 in 60 minutes (proposed)** | 0.020 | 0.029 | 32 to 33% | 6.2 -> 4.5 -> 5.3 after 25 minutes; fast in the air 9% -> 11%. Again with the final teacher and code: 6.3 -> 5.2 -> 5.7 after 12 minutes |

Read: the rise avoids the big first step; his aim did not move in any of them; the dip in item runs comes with every
weight and is the price of changing how he moves; half an hour is too short to see the speed come. While he imitates,
the left hand asks for more key changes than it is allowed (refused 45% -> 65%): the teacher's own pupil is refused as
often and still moves at 357.

Watched in the run: weapons and items picked up in games first of all; speed on his way and in item runs, time fast in
the air, items a minute in item runs (it must come back above 6), fall and lava damage.

## 3. Rockets

Owner: "He needs to have lead reading. This is a major part of the game"; the shot price "to a point ... the cost can be
very low"; "Weapon teaching at low weight"; shots with no enemy in view "should be *not* penalized ... that's totally how
rockets should be used", but "fire them 'where he thinks the enemy is'. So firing them at nonsense (or not rocket
jumping) should be discouraged"; "Expand the radius ... The 'likely path' problem ... is a larger deal"; "a small radius
for allowance of prefire for hitscan weapons".

What v13 does: against the stand-in his rockets hit 52 to 57% and he fires 0.9 to 1.9 a minute (the owner 9.2); in the
real games he held rockets 11 to 18% of the time on Blood Run and the rail 38 to 43%. Until v13 a rocket held down with
no enemy in view cost 19 points of damage on top of its price: he fires blind in 0.0% of his frames.

| | What is built | Switch | Tested |
|---|---|---|---|
| Lead reading | with rockets or plasma in hand and an enemy in view: how far the crosshair is from the point where the shot would meet him (left-right on 30 degrees and on 2, up-down on 15 and 2), the flight time, and how far below that point the floor lies (a rocket at his feet). From what he knows of the enemy (a reaction time old, the movement 200 ms old): a straight line on the ground, a thrown body's arc in the air | the last six of `N_V14` | a target crossing at 320: plasma 9.9 degrees (by the book 9.2); rockets need 18.7 at any distance, hence the 30; zero with the rail in hand |
| Shot price | rockets a fifth, plasma and grenades none, the others as now | `SHOT_W=rl:0.2,gl:0,pg:0` | 32 rockets: 0.53 before, 0.11 now; 205 plasma balls: 1.49 before, nothing now |
| Shots with no enemy in view | plasma and grenades: free. A rocket: free as a rocket jump, within 600 units of where he thinks the enemy is (the last place seen or heard, moved on by the last movement seen for up to a second), or on a way the enemy is likely to take from there, toward him or toward a big item, at a point he can have reached by the time it lands; any other costs 6 points of damage. Machine gun, shotgun, lightning, rail: 0.003 a frame as before, except in the first 1.5 s with the crosshair within 150 units of where the enemy must be | `BLIND_RULE=1` | constructed cases on Aerowalk: at his feet, near, on the enemy's way to the lightning gun with news 4 s old: free; the same shot with news 1.2 s old: wasted; lightning on the spot at 1.2 s: free, at 2.5 s or 600 units off: charged |
| Weapon teacher | on to the end at 0.2, on the pros' table of each map (3,712 duels; Lost World has no rail and uses the maps together); silent while he holds shotgun, plasma or grenades, and where its answer would be the machine gun while he owns one of them | `TEACH_FREE=1`, trainer `--weapon-teach 0.2` | nine hands checked |
| After the owner's duel | whether the simulator flatters the beam: his lightning hit rate against the owner, rockets a minute, the weapon in hand close up | - | - |

## 4. Shotgun, plasma, grenades

Owner: "No lives start with these ... plasma and grenades should be given no opportunity cost ... I would like to see him
slowly incorporate plasma for spamming tp exits or hallways for zoning"; the weapon teacher "neutral *if* he switches to
sg/plasma/grenade ... he can experiment with them".

He has 0.0% of his frags with them because the weapon teacher's label with one in hand was "switch" in every run since
v10. Built: the price, the teacher and the blind-fire rule of section 3. New in the training log: the share of his time
with each weapon in hand, the share of that time he fires it with no enemy in view, blind rockets by how the rule judged
them. The pros: plasma 5.3%, grenades 4.9%, shotgun 2.4% of the time in hand.

## 5. The simulator set right against the game's maps (done)

Owner: "Fix all 12". In `sim/`; v14 trains with all on. With every switch off the simulator replays v13's fixed-seed runs
exactly, and v13's own simulator is frozen beside it (`duel_env_v13.py`, `duel_env_ffa_v13.py`).

| # | Fix | Switch | Tested |
|---|---|---|---|
| 1 | Shots, missiles, splash and sight stop at solid brushes only: bars, grates and railings let them through | `SHOT_MASK` | 0.6 to 4.8% of a map's clear lines were closed |
| 2 | Lava and slime hurt; the hazard inputs name it; no way leads through it or jumps over it | `LAVA` | Lost World: 100 health gone in 1.5 to 2 s (the game 1.55 s) |
| 3 | The old Quake 3 key `notfree` is read | always | Campgrounds 33 items, as the game (it was 44) |
| 4 | The walker at teleporters and at drops; in water it swims and dives; a teleporter link costs the walk to its entrance | `WALK_FIX` | the stand-in stuck 46% -> 8% on Lost World, 47% -> 14% on Sinister, 25% -> 7% on Cure |
| 5 | The pros' way where the walking map has none | `PRO_WAYS` | Aerowalk's red armor: a way from 1.7% -> 100% of the live points |
| 6 | The nearest item of a kind is the goal | `NEAREST` | Aerowalk: seconds to a rocket launcher 3.8 -> 2.2 |
| 7 | Wading as in Quake Live | `QL_MOVE` | 299.0 units a second with the feet in water (the game 298.7) |
| 8 | Items rest on the floor as the game drops them | `ITEM_DROP` | every item within 2 units of where it rests in the game |
| 9 | Solid pieces that are brush models of their own; automatic doors are open | `SOLIDS` | Battleforged: the platform beside the mega; Toxicity's stone in the acid |
| 10 | Points nobody reaches, and points in lava, take no part | `WALK_FIX` | Aerowalk 28% of its points, Battleforged 24%, Sinister 16% |
| 11 | Step height 22, the game's | `QL_MOVE` | from the game's own setting |
| 12 | No powerups; a map's duel items in free-for-all | servers | live |

Still open: the walking maps of the six training maps built again with the simulator as it now is (B-173; done for
Toxicity and Cure); Toxicity's stand-in (B-181); step height and wading to the waist measured in the game (B-175).

## 6. Servers and real games

- Public server: `duel_gru_v13` since 2026-10-09 11:40, free-for-all on Aerowalk, two Bobbys, no powerups, a map's duel
  items in every mode. From the next deploy with new code on, v13 is exported with `duel_env_ffa_v13`.
- v13 against the game's Nightmare bot, real ten-minute games on local servers (2026-10-09): Blood Run 14-4, 11-6, 10-3;
  Lost World 8-5, 6-4, 9-5; Aerowalk 12-12 and two games in which Nightmare stood still ([REPORT_v13.md](REPORT_v13.md)).
  The same again after v14. That was also the first real-server run of the new plugin code: no frame errors.

## 7. The run as it would be started (`launch_v14.py show`)

| | v13 | v14 |
|---|---|---|
| From | v12b, 491 -> 499 inputs | v13's end network and its league, 499 -> 509 inputs (the ten new ones at zero weight), input statistics measured afresh on v14's maps and settings |
| Maps | Blood Run, Aerowalk, Lost World | those and Sinister, Furious Heights, Battleforged; four simulators a map |
| Groups | duels 62% of the players, threes and fours 19% each | the same |
| Rounds | normal games (15% a race for a big item, 25% against the scripted runner), item runs 20% of his time, half of them ending in a fight | the same, item runs 30% |
| Teachers | walking keys 0.5 and weapon 1.0, gone after four hours; the item rule 2.0 | the movement network in item runs: rising to 0.3 in the first hour, gone after eight; weapon 0.2 to the end; the item rule 2.0; no key labels in games |
| Pay | v13's manifest | the same, with the pay for speed in place of the pace pay, the shot price by weapon, the blind-fire rule |
| Shown | 499 inputs | 509: his movement (4), the lead of a shot (6) |
| The simulator | v13's | the twelve fixes on |
| Learning rate, entropy, the gate on the teachers | 1e-4; `--teach-trunk 0.05` | the same |
| Duel check | 48 games on three maps every 18 minutes | 32 games on ten maps (four never trained on) about every 45 minutes |
| Real games against Nightmare | after | before (done) and after |
| Size | 21 simulators, 5,040 games at once | 24 simulators, 5,040 games at once |

Ready: the starting network and its statistics, the teacher, the pros' tables, the duel curve's starting line, the
launcher, the evaluation loop for ten maps, a last dry run with the final code (section 2). Left: the owner's duel, his
decisions above, his go.

## 8. Not in this run, for later

- He does not hunt an opponent he neither sees nor hears (Aerowalk's 0-0 against a Nightmare that stood still, B-179);
  the pay for knowing where the enemy is did not move its measure in v13 and stays as it is.
- Position (he fights from below, B-160) and backing away when weak (B-161).
- Grenade lead (arc and bounces); the heavy machine gun.
- The teacher under today's hand rules (its labels ask for more key changes than a hand makes).
- The aim test on a duel map (B-176: the room on the test map does not measure v13).
- More validation maps (B-182), real games faster than real time (B-180), the walking maps rebuilt (B-173).

# `duel_gru_v13`: full report (2026-10-09)

The run of 2026-10-08 21:26 to 2026-10-09 11:35 ([MANIFEST_v13.md](MANIFEST_v13.md); mid-run: [MIDRUN_v13.md](MIDRUN_v13.md)),
stopped on the owner's word after fourteen hours ("end v13 at the next decent checkpoint"). Numbers are from
[RESULTS.md](../RESULTS.md) (entries of 2026-10-08 21:26 and 2026-10-09). What comes next is in [MANIFEST_v14.md](MANIFEST_v14.md).

## In short

- **Items and weapons, which the owner put first, held and grew.** Time without a big weapon 37% -> 18%, red armor 0.21
  -> 0.63 a player-minute, weapons 2.43 -> 3.95, the machine gun's share of his frags 23% -> 7%. Nothing collapsed when
  the teachers went.
- **He beats the Nightmare stand-in on the maps he trained on.** Blood Run 30% of the frags and no game won -> 72% and 97
  of 100 games; Aerowalk 52% -> 80%, 100 of 100. On arena1, which he did not train on, 38% -> 39% (25 of 100 won).
  v12 had 25%, 47% and 35%, and won 37 games of 300.
- **He beats the game's Nightmare bot in real games** on Blood Run (14-4, 11-6, 10-3) and Lost World (8-5, 6-4, 9-5);
  v12 lost 7-18 on Blood Run. On Aerowalk one game was a 12-12 draw and in two Nightmare stood still.
- **Not delivered: rockets and speed.** Rockets fell from 34% of his frags under the weapon teacher to 19%; he moves at
  294 units a second and is fast in the air 9% of the time. Both have a cause that is now known (below) and a plan.
- **The aim room no longer measures him**: on the test map he tracks a strafing target 27% of the time where v12 did
  47%, while in his games his hit rates rose. The cause is the room, not his aim: twelve of his inputs sit 5 to 88
  deviations outside anything he trained on there (below). The test has to move onto a duel map.
- **The first four hours were a dip**: with the teachers on he got worse in the duels while every training number rose.
- **Found on the way**: twelve places where the simulator differs from the game's maps (lava that does not hurt, shots
  stopped by bars, a stand-in that hops on the spot at teleporters). Some of them flatter or distort this run's numbers.

## What it is

| | |
|---|---|
| From | `duel_gru_v12b` (v12 plus two hours), widened from 491 to 499 inputs, fresh input statistics |
| Trained | 2026-10-08 21:26 to 2026-10-09 11:35: 846 minutes; the network is the save of update 450 (11:28), 1.74 billion player-frames (about 12,100 hours of play) at 34,400 frames a second |
| Network | 499 inputs -> 256 -> 256 -> memory of 512 (GRU) -> 11 outputs |
| Maps, groups | Blood Run, Aerowalk, Lost World, a third each; arena1 held out as the check map; duels 62% of the players, groups of three and four 19% each |
| Rounds | the game's own start (125 health, machine gun); normal games 76% of his time (15% of them a race for a big item, 25% against the scripted item runner), item runs alone 11%, the fight after a run 13% |
| New in v13 | dropped weapons (eight inputs); the ground round his feet known in every direction; the left hand at 8 key actions a second; pay for knowing where the enemy is, for pace on his way; a shot's price; damage taken at full price, armor's part at a third; the yellow armors as intentions; the item rule, the weapon teacher and the jump label from the pro demos |
| Teachers | keys-only walking teacher (0.5) and weapon teacher (1.0), both gone after four hours (01:26); the item rule on the intention (2.0, constant); all held back from the shared layers (`--teach-trunk 0.05`) |
| Learning rate | 1e-4; policy step 0.008 an update from hour 4 on |
| File | `data/sim_runs/duel_gru_v13/policy_end_v13.pt`; inputs in `docs/INPUTS.csv`; simulator module `duel_env_ffa` (frozen as `duel_env_ffa_v13` before v14 changes the inputs) |

## Training, hour by hour (self-play, all three maps)

| | Start | 2 h | 4 h (teachers gone) | 6 h | 8 h | 10 h | 12 h | 14 h |
|---|---|---|---|---|---|---|---|---|
| Time bare | 37% | 29% | 24% | 18% | 17% | 17% | 17% | 18% |
| Big weapons held | 0.87 | 0.99 | 1.09 | 1.30 | 1.35 | 1.39 | 1.38 | 1.38 |
| Weapons picked up a player-minute | 2.43 | 2.52 | 2.77 | 3.50 | 3.74 | 3.81 | 3.90 | 3.95 |
| Mega a player-minute | 0.50 | 0.55 | 0.60 | 0.68 | 0.70 | 0.70 | 0.70 | 0.70 |
| Red armor a player-minute | 0.21 | 0.26 | 0.33 | 0.50 | 0.58 | 0.61 | 0.62 | 0.63 |
| Other armor a player-minute | 1.57 | 1.81 | 1.96 | 2.28 | 2.39 | 2.46 | 2.48 | 2.49 |
| Stack of 150 or more | 14% | 18% | 20% | 23% | 24% | 24% | 24% | 24% |
| Trips reached | 36% | 39% | 44% | 50% | 51% | 52% | 52% | 53% |
| Frags by rockets / lightning / rail / machine gun | 25 / 34 / 18 / 23% | 31 / 35 / 19 / 15% | 34 / 34 / 20 / 12% | 26 / 48 / 20 / 6% | 22 / 49 / 23 / 6% | 20 / 51 / 23 / 7% | 19 / 52 / 22 / 7% | 19 / 52 / 22 / 7% |
| Frags a match-minute | 2.66 | 2.50 | 2.56 | 2.94 | 3.09 | 3.14 | 3.28 | 3.36 |
| On target, enemy in view | 31% | 31% | 31% | 32% | 33% | 33% | 34% | 34% |
| Against the scripted runner: frags / deaths a minute | 0.59 / 2.04 | 0.72 / 1.91 | 0.92 / 1.81 | 1.25 / 1.65 | 1.46 / 1.62 | 1.55 / 1.58 | 1.59 / 1.57 | 1.64 / 1.45 |
| Share of frags against his older selves | 44% | 50% | 54% | 57% | 57% | 55% | 55% | 56% |
| Speed on his way | 265 | 265 | 271 | 285 | 290 | 293 | 294 | 294 |
| Fast in the air | 21% | 26% | 25% | 11% | 9% | 9% | 9% | 9% |
| Key actions a second, made (8 allowed) | 6.7 | 7.4 | 7.4 | 6.1 | 5.6 | 5.4 | 5.2 | 5.0 |

By map at the end: Blood Run time bare 19%, 1.29 big weapons, 1.36 frags a player-minute; Aerowalk 15%, 1.80, 1.78;
Lost World 19%, 1.07, 0.85. From hour 11 on the self-play numbers move by a percent an hour or less.

## Against the Nightmare stand-in (simulator)

`tools/eval_loop.py` played 48 ten-minute duels a map from the latest save every 18 minutes, all run long (45 checks);
the last row is the end check, 100 duels a map from the final network (`docs/eval_v13_nightmare.json`). The stand-in is
our scripted item runner with Nightmare's aim, for checks only.

| Hour of the run | Blood Run: share of the frags (games won of 48) | Aerowalk | arena1 (not trained) |
|---|---|---|---|
| Start | 30% (0) | 52% (27) | 38% (0) |
| 1 to 4, teachers on | 20 to 24% (0 to 1) | 42 to 47% (5 to 14) | 31 to 33% (1 to 2) |
| 5 | 32% (3) | 57% (34) | 33% (2) |
| 6 | 45% (15) | 66% (46) | 37% (11) |
| 8 | 58% (31) | 70% (47) | 38% (11) |
| 10 | 65% (39) | 74% (48) | 38% (12) |
| 12 | 68% (42) | 75% (48) | 38% (9) |
| 14 | 70% (44) | 77% (48) | 39% (9) |
| **End, 100 duels** | **72%, 70 to 75 (97 won, 2 drawn, 1 lost)** | **80%, 78 to 81 (100 won)** | **39%, 38 to 41 (25 won, 4 drawn, 71 lost)** |
| v12's end, 100 duels | 25% (0 won) | 47% (37 won) | 35% (0 won) |

| The end check | Blood Run | Aerowalk | arena1 |
|---|---|---|---|
| Score a game, he : it | 11.8 : 4.0 | 23.2 : 5.7 | 9.8 : 14.5 |
| Time bare, he (it) | 5% (17%) | 4% (23%) | 23% (28%) |
| Stack of 150 or more, he (it) | 68% (32%) | 57% (16%) | 5% (19%) |
| Mega: his share of its spawns (its) | 50% (40%) | 65% (23%) | 22% (2%) |
| Red armor: his share (its) | 30% (31%) | 3% (14%) | 1% (46%) |
| Yellow armors a minute, he (it) | 2.9 (0.2) | 2.2 (0.0) | none on the map |
| Damage a kill of his takes / a kill of its | 237 / 606 | 173 / 526 | 205 / 164 |
| Frags by rail / lightning / rockets / machine gun | 36 / 39 / 21 / 4% | 38 / 54 / 8 / 1% | 34 / 34 / 10 / 22% |
| Hit rate rail / lightning / rockets | 45 / 45 / 52% | 53 / 52 / 57% | 39 / 30 / 19% |
| Shots a minute: rockets / rail / lightning | 1.9 / 3.3 / 36 | 0.9 / 4.0 / 63 | 3.0 / 3.3 / 45 |
| In hand close up: rail / lightning / rockets | 46 / 26 / 22% | 53 / 39 / 8% | 34 / 21 / 22% |
| Toward a visible enemy, weak / even / strong (units a second) | -26 / +22 / +68 | -3 / +20 / +32 | -1 / +39 / +3 |
| Speed, standing still | 286, 5% | 278, 5% | 241, 15% |
| His own deaths by the map a game | 0.2 | 0.1 | 3.8 (start 14.7) |

How the duels turned: at the start it took 173 damage to kill him on Blood Run and 340 to kill the stand-in; now 606 and
237. He wins on the stack, the thing Nightmare beat v12 with: he is at 150 or more two thirds of the time on Blood Run
and takes the yellow armors fifteen times as often as the stand-in. When he is the stronger he is in view 59 to 73% of
the time they see each other; when weak he backs off on Blood Run (-26) and hardly anywhere else.

**Read these with three cautions, all from the map audit of 2026-10-09:**
- On Aerowalk the walking map has no way to the red armor: the stand-in names it 64% of the time, takes it at 14% of
  its spawns (he at 3%) and spends half its time unable to go anywhere. His 80% there is against an opponent half asleep.
- Lost World has no duel check: the stand-in is stuck 46% of the time there (it hops on the spot at the teleporter).
- The real games against Nightmare (below) are the numbers to trust most.

## The first four hours: the teachers' dip

With the walking and weapon teachers on, every training number rose and the duels fell below the starting network:
Blood Run 30% -> 20 to 24%, Aerowalk 52% -> 42 to 47%. He had stopped hunting the stand-in: his speed toward it when
stronger fell from +108 to +57 units a second on Blood Run and from +63 to +14 on Aerowalk, with half the lightning and
machine-gun shots, and it stacked up unopposed. From the hour the teachers were gone (01:26) the stack turned into
kills: +10 points an hour for three hours. A duel check beside the training numbers showed this; the training numbers
alone did not. For the next run: teachers lighter or shorter, and the duel check from the first hour.

## What worked

| | |
|---|---|
| Dropped weapons | two thirds are picked up, from the first hour; 43% give the taker a weapon he did not have |
| The ground round his feet | arena1's falls gone at the first save: his own deaths there 14.7 -> 3.4 a game, on a map he never trained on |
| Teachers held back from the shared layers | his aim never dipped (on target 31% -> 34%); without the gate the first update moved the policy 1.1 nats |
| The item rule in the pros' order, yellow armors as goals | other armor 1.57 -> 2.48 a player-minute; trips reached 36% -> 53% |
| The left hand at 8 | he makes 5.0 key actions a second and asks for 4.7: no longer at its limit |
| Armor at a third, damage taken at full price | the stack of 150 or more 14% -> 24%; a kill of his costs 630 damage on Blood Run |
| The evaluation loop | the duel curve, hour by hour; it caught the dip and the late creep that self-play did not show |

## What did not work

- **Rockets.** 34% of his frags under the weapon teacher, 18% ten hours after it. In the duels he fires 0.9 to 1.7 a
  minute (the owner fired 9.2 on Aerowalk) and holds the rail close up (52 to 55%) where the pros hold rockets (55 to
  63%). Causes found: in the simulator his lightning hits 44 to 51%, where v12 hit 22 to 25% against the owner, so
  there it is the better weapon; every shot with no enemy in view costs 0.003 a frame and the shot's price on top (he
  fires blind in 0.0% of his frames; the pros with the launcher fire 22 to 40% of the time and see the enemy 6 to 16%);
  and shots stopped at bars and railings that the game lets them through.
- **Speed and strafe jumping.** 294 on his way, fast in the air 21 to 26% under the jump label and 9% after. The pace
  pay amounted to 0.02 a player-minute. He has had item runs paid for time all run long (3 a minute at 400 units a
  second) and runs them at 308: pay alone does not get him there. Today's hands can do it (the movement network of
  2026-10-03 played through them: 365 and 356); in a 21-minute trial with that network as teacher a copy of him went
  from 188 to 320 with 17% fast in the air.
- **Shotgun, plasma, grenades**: 0.0% of his frags. The weapon teacher knew four weapons and labelled "switch" whenever
  he held another.
- **The pay for knowing where the enemy is** did not move its measure (0.37 -> 0.39).
- **arena1** did not improve in the duels (38% -> 39%; its red armor never taken). It is out of v14 (owner).
- **Position and backing away** (B-160, B-161): not addressed in this run; toward a visible enemy when weak he still
  backs off (-4 to -6 units a second in self-play).
- **The trainer leaves most of the CPU idle** (its simulators wait on the network half the time): 27% of the CPU for
  34,400 frames a second.

## The simulator against the game's maps (found on 2026-10-09; RESULTS 10:15)

| Mismatch | What it did to v13 |
|---|---|
| Lava does not hurt (Lost World: 4.6% of the walking map stands in it) | he learned on Lost World that lava costs nothing |
| Shots and sight stop at player-clip brushes (bars, grates, railings) | 1 to 5% of a map's lines of fire were closed, the wall between Aerowalk's grenade launcher and mega among them |
| The walker hops on the spot at some teleporters and never takes some drops | the walking teacher's labels there were wrong for four hours; the scripted runner and the stand-in are stuck 46% of the time on Lost World |
| No way to Aerowalk's red armor in the walking map | his way there, its seconds and its pay did not exist: 4% of its spawns taken |
| Only the first rocket launcher of a map is a goal | Aerowalk's second launcher was never one |
| Wading, floating items, a missing platform, places nobody reaches, step height, 11 items too many on Campgrounds | none of these on v13's three maps matters much; they matter for v14's |

All twelve are fixed (switches, off by default, so that v13 plays as it trained); v14 trains with them on.

## Beside the pros (self-play, the game's own spawn; `tools/stack_probe.py`, `docs/stack_v13.json`)

| | Blood Run: he (pros) | Aerowalk | Lost World |
|---|---|---|---|
| Time without a big weapon | 13% (6%) | 12% (7%) | 16% (10%) |
| First big weapon after, median | 4.5 s (2.3 s) | 2.9 s (1.8 s) | 5.3 s (4.9 s) |
| Health plus armor under 100 | 21% (16%) | 30% (28%) | 13% (15%) |
| ... 150 or more | 45% (62%) | 24% (42%) | 49% (62%) |
| Weapon in hand is the pros' choice for the distance | 65% | 83% | 80% |
| His time on the ground that holds 90% of the pros' time | 87% | 80% | 83% |
| The pros' time on the ground that holds 90% of his | 67% | 71% | 72% |

v12 was bare 54% of the time. What still separates him from the pros here is the first weapon on Blood Run (4.5 s
against 2.3) and the stack on Aerowalk (24% at 150 or more against 42%).

## The big items, alone on the map (`tools/solo_item_check.py`: told to fetch it, 30 seconds, machine gun)

| | Mega | Red armor | Rockets | Rail | Lightning | Left to himself: mega, red in a round |
|---|---|---|---|---|---|---|
| Blood Run | 100% in 4.5 s | **100% in 8.3 s** (v12: 3%) | 100% | 100% | 100% | 100%, 71% |
| Aerowalk | 100% in 3.7 s | 18% (v12: 28%; no way in the walking map) | 100% | 100% | 100% | 100%, 17% |
| Lost World | 100% in 5.5 s | 100% in 5.0 s (v12: 94%) | 100% | - | 100% | 83%, 97% |
| arena1 (not trained) | 97% | 68% | 100% | 100% | 100% | 56%, 0% |

He takes 0.5 to 1.8 seconds longer than the walking map's time for the way: he walks it, he does not run it. The jump to
Blood Run's red armor, which v12 fell from 97 times in 100, he makes every time.

## Aim (reflex room on the test map; the owner's run beside it)

| | v13 | v12 (measured again today) | Owner |
|---|---|---|---|
| On a slow target | 30% of the time | 65% | 67% |
| On a strafing target | 27% | 47% | 40% |
| Lightning, damage a second | 35 | 68 | 58 |
| On a jumping target after | 381 ms | 369 ms | 350 ms |
| First rail shot hits | 57% | 25% | 88% |
| A rocket does | 16 damage | 36 | 54 |
| Rockets that hurt the target | 22% | 47% | 83% |
| Hand jitter on a slow target, degrees a frame | 2.0 | (not kept) | 0.6 |

**These numbers do not measure his aim.** In training his crosshair was on a visible enemy 31% -> 34% of the time, and
against the stand-in his lightning hits 45 to 52% and his rockets 52 to 57%. In the room he shakes (2 degrees a frame on
a slow target; the owner 0.6). The reason, checked: v13's input statistics were measured afresh on the duel maps before
the run, and the test map is nothing like them. In the room twelve of his inputs sit more than 5 deviations from their
training mean, seven more than 10 (the network cuts them off there): where the nearest red armor, mega, teleporter and
jump pad are (the test map is so large that they read 30 to 43 where a duel map gives 0 to 2; 47 to 88 deviations) and
his own cell's map reading (zero in the room, 23 deviations). v12's statistics came from generations that trained in
the room: one input out of range. So the room compares v12 at home with v13 abroad. The reflex test has to be run on a
duel map from now on (B-176); until then his aim is read from his games. The owner's duel is the first real reading.

## Heat maps and videos

`videos/duel_gru_v13_5675/`: `heat_bloodrun.png`, `heat_aerowalk.png`, `heat_lostworld.png`, `heat_arena1.png` (four
minutes of 1v1 against himself, eight games each; half of his time is spent on 16 to 17% of the cells he visits) and a
45-second first-person fight on each of the three trained maps.

## Against Nightmare, real games (2026-10-09 14:36 to 15:09)

Ten minutes a game, the game's own spawn, three local servers side by side on an otherwise quiet PC, three rounds.

| Map | Game 1 | Game 2 | Game 3 | Damage dealt / taken | Red armors: he / Nightmare | Megas: he / Nightmare |
|---|---|---|---|---|---|---|
| Blood Run | **14-4** | **11-6** | **10-3** | 3,605 / 3,188; 3,238 / 3,312; 2,696 / 2,899 | 15 / 1; 14 / 0; 12 / 1 | 11 / 3; 11 / 5; 14 / 1 |
| Lost World | **8-5** | **6-4** | **9-5** | 2,662 / 2,845; 2,326 / 3,015; 2,646 / 3,301 | 10 / 8; 12 / 7; 15 / 6 | 13 / 0; 11 / 1; 14 / 0 |
| Aerowalk | 0-0 | 3-1 | 12-12 | 0 / 15; 624 / 307; 3,819 / 2,738 | 0 / 24; 0 / 1; 1 / 0 | 17 / 0; 17 / 0; 9 / 7 |

v12 on the same servers the day before: Blood Run 7-18, Aerowalk 6-13.

- **Blood Run and Lost World: six games, six wins.** The damage is about even or against him; he wins on the stack. He
  takes nearly every red armor on Blood Run (41 of 43) and nearly every mega on both maps.
- **Aerowalk is not a test yet.** In the first game Nightmare went to the red armor after ten seconds and stood on its
  spot for the rest of the game (it took all 24 of them, its speed was zero); in the second it stood still most of the
  time (26 units a second). He never went up there, saw it 1 to 2% of the time and did not go looking: he does not hunt
  an opponent he neither sees nor hears, and he does not take Aerowalk's red armor (the walking map has no way to it;
  1 of 72 in three games). In the one game Nightmare played, the score was 12-12 with the damage his way.
- The stand-in was the pessimist on Blood Run (72% of the frags there, 76% in these games) and no guide on Aerowalk.
- His weapons in these games: the rail 38 to 43% of the time on Blood Run with lightning 26 to 36% and rockets 11 to 18%;
  lightning 53 to 78% on Lost World; his speed 263 to 298.

## Verdict

The first network that plays the item game: he keeps a stack, takes the red armor a third of the time against a
scripted opponent that wants it, and wins his trained maps against the Nightmare stand-in. He does it at a walk and with
the beam and the rail. Speed and rockets are the next run's work, and the reasons he lacks both are now specific.

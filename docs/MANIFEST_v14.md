# `duel_gru_v14`: what is agreed, what is built, what is still open (2026-10-09 12:30; not a run yet)

Everything the owner called on 2026-10-09 while `duel_gru_v13` finished, in one place: where each change is, how it was
tested, and what is still his to set. He duels v13 first and adds to this; the run starts only on his go.
Sources: [RESULTS.md](RESULTS.md) entries of 2026-10-09 (09:05 the calls, the hand check, the movement trial; 10:15 the
map audit; 12:20 v13's end and what was built), [REPORT_v13.md](REPORT_v13.md), [BACKLOG.md](BACKLOG.md) B-163 to B-178.

## 0. In short

| | Change | State |
|---|---|---|
| Maps | six of the game's duel maps to train on, two held out, arena1 dropped | decided; data checked (section 1) |
| Speed | a teacher that strafe-jumps in his item runs, a pay for speed from 320 to 480, four inputs | built and tested; **the six-map teacher is training and is not good enough yet** (section 2) |
| Rockets | lead reading (six inputs), a very low shot price, shots at where the enemy is or is about to be are free, the weapon teacher on at a low weight | built and tested (section 3) |
| Shotgun, plasma, grenades | no price on plasma and grenades, the weapon teacher silent while he holds one, counters | built and tested (section 4) |
| The simulator against the game | the audit's twelve mismatches | fixed, in `sim/` behind switches (section 5) |
| Servers | no powerups anywhere; a map's duel items in every mode | live on the public server since 11:40 with v13 (section 6) |

Every change is a switch that is off by default. With all of them off the simulator replays v13's fixed-seed runs
exactly (inputs, pay, positions), and v13's own simulator is frozen beside it (`duel_env_v13.py`, `duel_env_ffa_v13.py`).

## 1. Maps

Owner: "Maps trained on for v14: blood run, aerowalk, lost world, sinister, furious heights, campgrounds. Held out maps:
battleforged, hektik"; "we're dropping arena1 entirely and just focusing on the in game duel maps".

| Map | Walking-map points (live after the fixes) | Spawn points | Pads, teleporters | Water or lava | In the game's file that differs from a duel in free-for-all |
|---|---|---|---|---|---|
| Blood Run | 1,185 (94%) | 10 | 2, 2 | a strip of lava nobody reaches | quad, two ammo boxes elsewhere |
| Aerowalk | 906 (72%) | 8 | 1, 5 | none | nothing |
| Lost World | 1,272 (93%) | 18 | 2, 1 | lava: 59 points stood in it | quad, a health elsewhere |
| Campgrounds | 1,643 (94%) | 17 | 3, 0 | four small lava pools nobody reaches | quad where the mega is |
| Sinister | 1,827 (84%) | 11 | 3, 4 | shallow water (6% of the points) | nothing |
| Furious Heights | 1,703 (94%) | 16 | 2, 3 | shallow water (5%) | quad, a rocket launcher elsewhere, an ammo box |
| Battleforged (held out) | 1,667 (76%) | 9 | 3, 3 | lava: 30 points | quad, invisibility, no grenade launcher |
| Hektik (held out) | 1,095 (93%) | 10 | 2, 2 | shallow water (2%) | 18 of its 37 items |

- All eight have the map file, a walking map and the map reader's table. None has a door, a lift or a hurt trigger.
- Six maps share the experience: each gets a sixth where v13's three got a third.
- **The duel check**: 32 ten-minute games a map per check (one check within 4.6 points on the noisiest map, 2.9 on the
  others; an hour's three checks pooled within 2.7), 64 a map at the run's end (two networks told apart from 6.5 points).
  Eight maps at 32 games are 1.8 times the work of v13's three at 48: a check about every half hour.
- **The stand-in has to play on a map before its numbers count.** With the fixes of section 5 it moves at 244 to 277
  units a second on all eight and is stuck 3 to 11% of the time (it was 105 and 139 on Lost World and Sinister, stuck
  46% and 47%). Still open (B-174): its item rule leaves it with nothing to go for 14 to 45% of the time once it holds
  what it can reach, and Sinister's 11%.
- Not there yet for Sinister and Furious Heights: the pros' tables (weapons by distance, item order, where they jump,
  their ways). Their demos are not fetched; until then those two maps run on the plain item rule and the walking map.

## 2. Speed and strafe jumping

Owner: "strafe jumping is absolutely crucial to the game, he needs to learn it asap"; movement rounds "on the duel maps
not the testlab ... figuring out routes between items, practicing jumps"; "320 -- 480 pay for speed bonus (flat above
480), it can be aggressive at first"; "yes to additional inputs".

What was found: today's hands can do it (the movement network of 2026-10-03 played through them moves at 356 to 365
units a second on Blood Run; the owner 348 to 355, v13 308 in his item runs). v13 has had item runs paid for time all
along and walks them: what is missing is somebody to show him. In a 21-minute trial a copy of v13 with that network as
teacher went from 188 to 320 with 17% of its time fast in the air, still rising.

| | What is built | Switch | Tested | To set |
|---|---|---|---|---|
| The teacher's labels | in his **item runs** (alone on the map, from item to item) the movement network's keys, jump and view are the labels; where it has no way the walking teacher's keys stay; in games no key labels at all and his view is his own | `RUN_TEACHER=1`, `STACK_KEYS=0`, trainer `--teacher` | a pupil pressing only the labels, through today's hands, Blood Run: the walking teacher alone 304 units a second and 6.8 items a minute; the old movement network 356, 30% of the time fast in the air, 8.3 items a minute | weight and fade (proposed 0.5 over eight hours, through `--teach-trunk 0.05`; the dry run's step per output decides); the share of item runs (proposed 30% of rounds; v13 20%); **no key labels in games** (v13 had the walking teacher's for four hours) |
| The teacher itself | a movement network for the six maps, `move_v14a`: the game's step height and wading, the maps' solid pieces, lava ends a try and reads as a pit, fall damage costs half a second per far fall, tries start where the spawn points lead. Free hands, like the old one | `sim/train_move.py --v14` | training since 11:56 for 150 minutes. At 20 minutes: 88% of trips reached, 48% of its moving time above running speed; as a teacher still slower than the walking teacher (255 on Blood Run; 28 lava damage a minute on Lost World). **Measured again at its end; if it is not clearly better than walking it does not teach** (B-177) | - |
| Pay for speed | for every stretch of new ground on the way to his chosen item, by the speed he covers it at: nothing at 320, full from 480, flat above. In item runs, and in games with nobody seen for 1.5 s (there it is part of the trip's pay: a dropped trip gives it back). Replaces the pace pay | `SPEED_PAY` (games), `SPEED_PAY_RUN` (item runs) | the old movement network at 355 in item runs earns 0.53 a player-minute at 0.06, beside 7.3 from the runs themselves | proposed 0.06 in games and 0.15 in item runs (a second at 480 straight along the way); halved after six hours |
| Four inputs | his speed; the angle from his view to the way he moves (sine and cosine); speed gained in the last 100 ms | the first four of `N_V14` | exact against the simulator's state | - |

**Changed from the draft, with the reason:**
- The pay is per stretch of ground, not per second. Per second, a player gaining ground at 60% of running pace while fast
  would collect two thirds more for the same trip than one going straight; per stretch a detour or a zigzag earns nothing.
- The teacher has free hands (no finger or mouse rules in its own training). Porting those rules is a second copy of that
  code; the old network's labels pressed through today's hands already give 356.
- A new teacher at all: the old one, on the three maps it never saw, is on the move only 42 to 61% of the time.

Watched: speed while moving 335 to 350, in the air 35 to 50% of that time, above 400 for 20% or more (the pros 304 on the
ground and 377 to 406 in the air; the owner 348 to 355 with 27% above 400); item pickups and weapon use must not fall;
fall and lava damage a minute.

## 3. Rockets

Owner: "He needs to have lead reading. This is a major part of the game"; the shot price "to a point ... the cost can be
very low"; "a natural progression as his speed gets better ... but I think we need to give him a nudge on the way. Weapon
teaching at low weight"; shots with no enemy in view "should be *not* penalized ... that's totally how rockets should be
used", but "fire them 'where he thinks the enemy is'. So firing them at nonsense (or not rocket jumping) should be
discouraged"; "Expand the radius ... The 'likely path' problem ... is a larger deal"; "a small radius for allowance of
prefire for hitscan weapons".

What v13 does: against the stand-in his rockets hit 52 to 57% and he fires 0.9 to 1.9 a minute (the owner 9.2); close up
he holds the rail 46 to 53% of the time where the pros hold rockets. Until v13 a rocket held down with no enemy in view
cost 19 points of damage (0.003 a frame for 0.8 s) on top of its price: he fires blind in 0.0% of his frames.

| | What is built | Switch | Tested | To set |
|---|---|---|---|---|
| Lead reading | with rockets or plasma in hand and an enemy in view: how far the crosshair is from the point where the shot would meet him (left-right on a scale of 30 degrees and of 2, up-down on 15 and 2), the flight time, and how far below that point the floor lies (a rocket at his feet). From what he knows of the enemy (a reaction time old, the movement 200 ms old): a straight line on the ground, a thrown body's arc in the air | the last six of `N_V14` | a target crossing at 320: plasma 9.9 degrees (by the book 9.2), rockets 18.7 by the book at any distance, which is why the coarse scale is 30; zero with the rail in hand | grenades later (arc, bounces) |
| Shot price | by weapon: rockets a fifth, plasma and grenades none, the others as now | `SHOT_W=rl:0.2,gl:0,pg:0` | 32 rockets: 0.53 before, 0.11 now; 205 plasma balls: 1.49 before, nothing now | the fifth |
| Shots with no enemy in view | plasma and grenades: free. A rocket: free as a rocket jump, within 600 units of where he thinks the enemy is (the last place seen or heard, moved on by the last movement seen for up to a second), or on a way the enemy is likely to take from there, toward him or toward a big item, at a point he can have reached by the time it lands; any other costs 6 points of damage. Machine gun, shotgun, lightning, rail: 0.003 a frame as before, except in the first 1.5 s with the crosshair within 150 units of where the enemy must be | `BLIND_RULE=1` | constructed cases on Aerowalk: at his feet, near, on the enemy's way to the lightning gun with news 4 s old: free; the same shot with news 1.2 s old: wasted; lightning on the spot at 1.2 s: free, at 2.5 s or 600 units off: charged | 600 units, 6 points, 150 units and 1.5 s |
| Weapon teacher | on to the end at a low weight, on the pros' table; silent while he holds shotgun, plasma or grenades, and where its answer would be the machine gun while he owns one of them | `TEACH_FREE=1`, trainer `--weapon-teach` | nine hands checked (plasma in hand: silent; machine gun in hand owning plasma and rockets: "rockets") | weight: proposed 0.2 to the end, through `--teach-trunk` |
| After the owner's duel | whether the simulator flatters the beam: his lightning hit rate against the owner, rockets a minute, the weapon in hand close up. If so: opponents that dodge, and the aim error for a target crossing fast (zero since v13) | - | - | - |

## 4. Shotgun, plasma, grenades (no heavy machine gun)

Owner: "No lives start with these. I'm less concerned with them for now, but plasma and grenades should be given no
opportunity cost ... I would like to see him slowly incorporate plasma for spamming tp exits or hallways for zoning,
similarly with grenades, but it's not a priority right now"; the weapon teacher "neutral *if* he switches to
sg/plasma/grenade ... he can experiment with them".

He has 0.0% of his frags with them because the weapon teacher's label with one in hand was "switch" in every run since
v10. Built: section 3's shot price, weapon teacher and blind-fire rule. New counters in the training log (`v14`): the share
of his time with each weapon in hand, the share of that time he fires it with no enemy in view, blind rockets by how the
rule judged them. The pros: plasma 5.3%, grenades 4.9%, shotgun 2.4% of the time in hand.

## 5. The simulator set right against the game's maps (done)

Owner: "Fix all 12". In `sim/` since 12:16, the library rebuilt; v14 trains with all on.

| # | Fix | Switch | Tested |
|---|---|---|---|
| 1 | Shots, missiles, splash and sight stop at solid brushes only: bars, grates and railings let them through as in the game | `SHOT_MASK` | 0.6 to 4.8% of a map's clear lines were closed; what he sees where he looks changes from the first frame |
| 2 | Lava and slime hurt: 30 (10) times how deep he stands, twice a second; the hazard inputs name it; no way leads through it | `LAVA` | Lost World: 100 health gone in 1.5 to 2 s (the game 1.55 s) |
| 3 | The old Quake 3 key `notfree` is read | always | Campgrounds 33 items, as the game (it was 44, with a second red and a second yellow armor) |
| 4 | The walker (scripted runner, walking teacher) at teleporters and at drops | `WALK_FIX` | the stand-in stuck 46% -> 5% on Lost World, 47% -> 11% on Sinister, 22% -> 6% on Furious Heights, 13% -> 4% on Battleforged |
| 5 | The pros' way where the walking map has none | `PRO_WAYS` | Aerowalk's red armor: a way from 1.7% -> 100% of the live points |
| 6 | The nearest item of a kind is the goal | `NEAREST` | Aerowalk: seconds to a rocket launcher 3.8 -> 2.2 (median); both launchers taken equally |
| 7 | Wading as in Quake Live | `QL_MOVE` | 299.0 units a second with the feet in water (the game 298.7; it was 267) |
| 8 | Items rest on the floor as the game drops them | `ITEM_DROP` | on all eight maps every item within 2 units of where it rests in the game (Sinister's were 43 high) |
| 9 | Solid pieces that are brush models of their own are in the collision | `SOLIDS` | Battleforged: the platform beside the mega |
| 10 | Points of the walking map nobody reaches, and points in lava, take no part | `WALK_FIX` | Aerowalk 28% of its points, Battleforged 24%, Sinister 16% |
| 11 | Step height 22, the game's | `QL_MOVE` | from the game's own setting; not measured on a step |
| 12 | No powerups; a map's duel items in free-for-all | servers | section 6 |

Checked after the move: v13's frozen modules and the new ones with the switches off replay v13's fixed-seed runs exactly;
the group simulator at two players is the plain one, switches off and on; the server image builds and the new
simulator runs in it. Still to do: the walking maps built again with the simulator as it now is (B-173); the stand-in's
stuck spots (B-174); the step height and wading to the waist measured in the game (B-175).

## 6. Servers (done)

- The game's own powerup switch is off at every map load; the plugins remove any powerup they see all the same. A
  free-for-all game gets the map's duel items (`plugins/duel_items.json`); Campgrounds so has its mega.
- Live on the public server since 2026-10-09 11:40 with `duel_gru_v13`: free-for-all on Aerowalk, two Bobbys. Its log
  after the start: no powerup found, 29 items, the mega there; no frame errors.
- From the next deploy with new code on, v13 is exported with `duel_env_ffa_v13`.

## 7. The run as it would be started (proposed; `launch_v14.py show`)

| | v13 | v14 |
|---|---|---|
| From | v12b, 491 -> 499 inputs | v13's end network and league, 499 -> 509 inputs (the ten new ones at zero weight), input statistics measured afresh on v14's maps and settings |
| Maps | Blood Run, Aerowalk, Lost World | those and Sinister, Furious Heights, Campgrounds; four simulators a map |
| Groups | duels 62% of the players, threes and fours 19% each | the same |
| Rounds | normal games, 15% of them a race for a big item, 25% against the scripted runner; item runs 20% of rounds, half of them ending in a fight | the same, item runs 30% |
| Teachers | walking keys 0.5 and weapon 1.0, both gone after four hours; the item rule 2.0 | the movement network in item runs 0.5 over eight hours; weapon 0.2 to the end; the item rule 2.0; no key labels in games |
| Pay | as v13's manifest | the same, with the pay for speed in place of the pace pay, the shot price by weapon, the blind-fire rule |
| The simulator | v13's | the twelve fixes on |
| Learning rate, entropy, the gate on the teachers | 1e-4; `--teach-trunk 0.05` | the same |
| Duel check | 48 games on three maps every 18 minutes | 32 games on eight maps (two never trained on) about every half hour, from the first hour |

Before the start, in this order: (1) the teacher measured (B-177); (2) `prep`: the network widened; (3) `sample`: fresh
input statistics, the inputs that the new settings bring to life from zero weight; (4) a ten-minute dry run on a scratch
copy with the step per output read; (5) this manifest in full with the dry run's numbers; (6) the owner's go.

## 8. Open, for the owner

- **The sizes marked "proposed"**: the speed pay (0.06 in games, 0.15 in item runs, halved after six hours), the share of
  item runs (30%), the movement teacher's weight and fade (0.5 over eight hours), the rocket shot price (a fifth), the
  radius (600 units), the wasted rocket (6 damage points), the pre-fire allowance (150 units, 1.5 s), the weapon teacher's
  weight (0.2).
- **No key labels in games** (the walking teacher's keys there taught "forward along the way", which is what strafe jumping
  has to replace). The other way: keep them for the first hours as v13 did.
- **If the six-map teacher is not good enough by the start**: start without it and with the old network as the teacher on
  Blood Run, Aerowalk and Campgrounds only; or wait for a longer training of the new one.
- The pay for knowing where the enemy is: it did not move its measure in v13 (0.37 -> 0.39). Kept as it is unless he says.
- After his duel against v13: the aim question of section 3, and whatever he sees.
- From v13's report: position (he fights from below, B-160), backing away when weak (B-161).
- Not done yet and his to rank: the reflex test on a duel map (B-176: the room on the test map does not measure v13),
  real games against Nightmare (B-178), the pros' demos for Sinister and Furious Heights.
- Run length and the hours he wants reports at.

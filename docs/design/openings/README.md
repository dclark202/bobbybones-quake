# The pros' spawn openings

Written by `tools/pro_openings.py` from the light demo sets; the data is `sim/pro_spawn_openings/<map>.json` (per spawn point: its openings with shares, median times, a real route at 0.25 s steps for 10 s, and the first pickup set beside the enemy's place at the frag). An opening is the first one, two or three big pickups (mega MH, red RA, yellow YA, green GA, the weapons) within 15 s of a spawn, kept at 5 lives and 10% of the spawn's lives; a row under an opening is what followed it. Shares are of the spawn's lives. Times are medians from the spawn.

<!-- notes -->
## What stands out (2026-10-13)

| map | demos | spawn lives | of them a game's start | spawn points | openings at one pickup | spawns with one standard opening (75% or more) | spawns with a real choice (a second opening at 20% or more) |
|---|---|---|---|---|---|---|---|
| bloodrun | 1066 | 6751 | 1044 | 13 | 23 | 5 | 6 |
| aerowalk | 978 | 10898 | 952 | 8 | 13 | 4 | 4 |
| lostworld | 1222 | 7468 | 1185 | 17 | 39 | 1 | 8 |
| sinister | 147 | 184 | 135 | 11 | 14 | 8 | 3 |
| furiousheights | 150 | 202 | 141 | 16 | 9 | 9 | 0 |
| battleforged | 149 | 276 | 138 | 10 | 14 | 7 | 2 |
| campgrounds | 5 | 49 | 5 | 3 | 0 | 0 | 0 |
| hektik | 144 | 749 | 138 | 10 | 16 | 6 | 3 |
| toxicity | 87 | 582 | 87 | 8 | 15 | 4 | 4 |
| cure | 129 | 424 | 124 | 11 | 25 | 3 | 7 |

- **One standard opening**: where a weapon lies within about a second and a half of the spawn the pros take it nine times in ten and the choice comes after it (Blood Run: the rocket spawns S1 and S6, lightning S2, rail S12 and S13; Aerowalk: rockets S3, rail S4, the shotgun S8; Lost World's shotgun spawn S3 at 99%; Hektik S2 to S4). The first pickup is nearly always the nearest weapon; the armor or the mega is the second step (Blood Run S1: rockets, then the yellow armor at 3.0 s, then the mega at 4.7 s).
- **A real choice**: spawns between two things. Blood Run S3 (the yellow armor at 0.9 s in 37% of lives, lightning 19%, rockets 17%), S4 (yellow armor then plasma, or plasma alone), the three spawns on the grenade side (S5, S7, S8: grenades at about 2 s or rockets at 4 to 4.5 s). Aerowalk S1 (grenades or the yellow armor), S2 (lightning or rockets), S6 (green armor or rockets), S7 (lightning 81%, red armor 16%). Lost World is the map of choices: 8 of its 17 spawns have a second opening at 20% or more and only one has a standard one.
- **The enemy** (the three maps with enough lives; his place is the one the server last sent in the last second before the death, distances are straight lines). Taking the first pickup farthest from him is no more common than chance: Blood Run 43.3% against 43.3% in 2,316 lives, Aerowalk 54.0% against 51.4% in 4,826, Lost World 38.4% against 39.6% in 3,285. What does show: with him within 500 units of an armor or the mega that is one of the spawn's first pickups, the pros take it less often than otherwise (Blood Run 22% against 50%, 59 lives; Aerowalk 25% against 37%, 354; Lost World 29% against 35%, 469); a weapon he stands at they take as often as ever (Blood Run 47% against 46%, Lost World 43% against 37%; Aerowalk 51% against 57%). So: the weapon first whatever he does, the armor only when he is not on it. Per spawn and item the numbers are in the JSON (`enemy.by_item`).
- **Too little data**: Campgrounds (5 demos, 49 lives, no opening reaches five lives). Sinister, Furious Heights and Battleforged have about 150 demos each but these are spectator recordings: the camera goes to the other player at a frag, so the spawn after a death is rarely seen and about two lives in three are the game's first spawn (7 to 46 lives a spawn point; shares there are of a dozen lives, and nothing about the enemy can be said). Hektik, Toxicity and Cure have 18 to 129 lives a spawn: the first pickups are sound, the second and third steps thin.
- **Doubtful**: the map files have fewer spawn entities than the pros' starts show on Blood Run (13 places for 10 entities: S7 and S13 lie 66 and 72 units from an entity that has a start of its own, S10 and S11 450 and 631 units from any), and one each on Furious Heights (S4, 151 units) and Battleforged (S10, 98): older versions of the maps in the archive, most likely; the positions written are the pros'. Jumps on the routes are read off the height (the light sets hold no keys or speeds). Ammunition boxes cannot be seen. A weapon gained far from every item of its kind (a dropped one; 14 to 2,043 a map) defines no opening. The time between a death and the spawn is not recorded, so "where the enemy was" is some seconds old.
- **Beside what was there**: `sim/pro_openings/<map>.json` (written by `tools/pro_yardsticks.py`, read by `tools/bobby_yardsticks.py`; B-231) already counts the pros' plans by spawn point from the full yardstick data. These files are a different cut of the same question and live in `sim/pro_spawn_openings/`: openings as a tree of one, two and three pickups with a threshold, a real route for each, and the first pickup set beside the enemy's place. The item names here are numbered by the order of `plugins/duel_items.json` (`items` in each file gives the positions), not as there.
<!-- tables -->

### bloodrun

1066 demos (9946 minutes of play), 6751 spawn lives (1044 of them a game's start), 13 spawn points, 347 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (1230, -1312, 286; by RL) | 1060 | RL | 93% | 1.6 |
|  |  | RL > YA2 | 37% | 1.6 / 3.0 |
|  |  | RL > YA2 > MH | 11% | 1.5 / 3.0 / 4.7 |
| S2 (1119, 225, 94; by LG) | 1018 | LG | 92% | 1.3 |
|  |  | LG > MH | 21% | 1.3 / 3.3 |
|  |  | LG > MH > RG | 10% | 1.3 / 3.1 / 7.0 |
|  |  | LG > RG | 16% | 1.3 / 6.3 |
|  |  | LG > YA2 | 11% | 1.3 / 4.6 |
| S3 (863, -802, 94; by YA2) | 847 | YA2 | 37% | 0.9 |
|  |  | YA2 > MH | 11% | 0.8 / 2.6 |
|  |  | LG | 19% | 3.5 |
|  |  | RL | 17% | 4.5 |
| S4 (354, 480, 446; by PG) | 839 | YA | 49% | 2.1 |
|  |  | YA > PG | 48% | 2.1 / 2.5 |
|  |  | YA > PG > RA | 13% | 2.1 / 2.4 / 6.1 |
|  |  | YA > PG > SG | 11% | 2.2 / 2.5 / 5.9 |
|  |  | PG | 26% | 2.4 |
| S5 (-640, -846, 414; by GL) | 484 | GL | 39% | 2.2 |
|  |  | GL > RG | 18% | 2.2 / 5.2 |
|  |  | RL | 27% | 4.5 |
| S6 (241, -1137, 280; by RL) | 435 | RL | 90% | 1.4 |
|  |  | RL > YA2 | 27% | 1.4 / 3.3 |
| S7 (-703, -831, 414; by GL) | 430 | RL | 44% | 4.3 |
|  |  | RL > YA2 | 11% | 4.4 / 6.8 |
|  |  | GL | 28% | 2.2 |
|  |  | GL > RG | 13% | 2.1 / 4.6 |
| S8 (-193, -847, 414; by GL) | 344 | GL | 56% | 1.6 |
|  |  | GL > RG | 26% | 1.6 / 4.2 |
|  |  | RL | 24% | 4.0 |
| S9 (496, -720, 447; by YA2) | 342 | RL | 52% | 2.0 |
|  |  | RL > YA2 | 28% | 2.0 / 3.5 |
|  |  | SG | 28% | 2.5 |
|  |  | SG > RA | 20% | 2.5 / 3.9 |
| S10 (735, -352, 543; by MH) | 208 | SG | 58% | 1.6 |
|  |  | SG > RA | 24% | 1.6 / 2.9 |
|  |  | RL | 28% | 3.0 |
| S11 (-735, -224, 415; by GL) | 162 | GL | 52% | 1.4 |
|  |  | GL > RG | 25% | 1.4 / 4.2 |
|  |  | PG | 17% | 4.3 |
|  |  | PG > YA | 13% | 4.3 / 4.8 |
|  |  | RG | 15% | 2.8 |
| S12 (95, -41, 30; by RG) | 123 | RG | 95% | 1.1 |
|  |  | RG > YA | 19% | 1.1 / 6.0 |
|  |  | RG > YA > PG | 15% | 1.1 / 6.8 / 7.0 |
|  |  | RG > RA | 13% | 1.1 / 5.5 |
|  |  | RG > SG | 12% | 1.1 / 7.4 |
| S13 (31, -9, 30; by RG) | 112 | RG | 96% | 1.0 |
|  |  | RG > RA | 21% | 1.0 / 5.7 |
|  |  | RG > SG | 14% | 1.1 / 5.5 |
|  |  | RG > YA | 13% | 0.9 / 7.2 |
|  |  | RG > YA > PG | 12% | 0.9 / 6.9 / 7.2 |

The enemy: in 2316 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 43% of the time; 43% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (59 lives) they took it 22% of the time; 50% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (520 lives) they took it 47% of the time; 46% at the rate of the lives without him there.

### aerowalk

978 demos (8814 minutes of play), 10898 spawn lives (952 of them a game's start), 8 spawn points, 158 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (959, -159, 150; by YA) | 2231 | GL | 42% | 1.6 |
|  |  | GL > RG | 17% | 1.6 / 4.7 |
|  |  | YA | 35% | 0.7 |
|  |  | YA > GL | 19% | 0.7 / 2.0 |
| S2 (407, 559, 382; by RL) | 1975 | LG | 49% | 2.1 |
|  |  | LG > RA | 12% | 2.1 / 4.1 |
|  |  | RL | 40% | 1.7 |
|  |  | RL > RG | 11% | 1.7 / 5.1 |
| S3 (775, 11, 382; by YA) | 1786 | RL | 93% | 1.2 |
|  |  | RL > RG | 22% | 1.2 / 4.3 |
|  |  | RL > LG | 22% | 1.2 / 5.4 |
| S4 (544, -666, 382; by GA2) | 1773 | RG | 77% | 1.5 |
|  |  | RG > RL2 | 22% | 1.4 / 2.9 |
| S5 (-131, 363, 150; by LG) | 1021 | RL | 23% | 3.7 |
|  |  | LG | 21% | 4.1 |
| S6 (-606, -304, 150; by GA) | 974 | GA | 49% | 0.2 |
|  |  | GA > RL2 | 43% | 0.2 / 0.9 |
|  |  | GA > RL2 > RG | 20% | 0.2 / 0.9 / 2.4 |
|  |  | GA > RL2 > MH | 11% | 0.2 / 0.9 / 2.1 |
|  |  | RL2 | 43% | 0.9 |
|  |  | RL2 > RG | 21% | 0.9 / 2.2 |
| S7 (-384, -104, 366; by RA) | 519 | LG | 80% | 1.4 |
|  |  | LG > RL2 | 12% | 1.4 / 4.2 |
|  |  | RA | 16% | 0.0 |
|  |  | RA > LG | 16% | 0.0 / 1.4 |
| S8 (160, -351, -42; by MH) | 461 | SG | 82% | 1.1 |
|  |  | SG > MH | 19% | 1.1 / 2.7 |
|  |  | SG > GL | 11% | 1.1 / 4.0 |

The enemy: in 4826 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 54% of the time; 51% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (354 lives) they took it 25% of the time; 36% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (1326 lives) they took it 51% of the time; 57% at the rate of the lives without him there.

### lostworld

1222 demos (11514 minutes of play), 7468 spawn lives (1185 of them a game's start), 17 spawn points, 326 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (553, 1239, 182; by PG) | 697 | PG | 65% | 2.7 |
|  |  | PG > YA | 22% | 2.7 / 5.0 |
| S2 (912, 1059, 350; by PG) | 677 | YA | 36% | 2.0 |
|  |  | YA > RL | 16% | 2.0 / 5.4 |
|  |  | PG | 29% | 4.0 |
|  |  | RL | 11% | 5.2 |
| S3 (1379, 467, 222; by SG) | 613 | SG | 99% | 0.5 |
|  |  | SG > MH | 25% | 0.5 / 3.0 |
|  |  | SG > RL | 11% | 0.5 / 6.6 |
| S4 (80, 1007, 478; by YA2) | 599 | RL | 43% | 2.9 |
|  |  | YA2 | 20% | 2.6 |
|  |  | YA2 > LG | 18% | 2.6 / 3.7 |
|  |  | LG | 16% | 3.4 |
| S5 (-390, 784, 478; by YA2) | 567 | LG | 38% | 2.5 |
|  |  | LG > YA2 | 16% | 2.5 / 4.0 |
|  |  | YA2 | 34% | 1.9 |
|  |  | YA2 > LG | 32% | 1.9 / 3.0 |
|  |  | RL | 17% | 3.5 |
| S6 (-368, 287, 222; by YA2) | 487 | LG | 66% | 3.8 |
|  |  | LG > YA2 | 40% | 3.8 / 4.8 |
| S7 (1142, 479, 414; by YA) | 474 | SG | 35% | 2.5 |
|  |  | RL | 30% | 4.4 |
|  |  | MH | 22% | 1.9 |
|  |  | MH > SG | 12% | 1.9 / 4.4 |
| S8 (976, 659, 350; by YA) | 416 | YA | 38% | 2.0 |
|  |  | YA > RL | 19% | 1.9 / 5.3 |
|  |  | PG | 23% | 4.6 |
|  |  | RL | 11% | 5.2 |
| S9 (926, -192, 478; by MH) | 410 | RL | 70% | 2.4 |
|  |  | RL > YA | 13% | 2.2 / 7.7 |
|  |  | RL > MH | 12% | 2.5 / 7.6 |
|  |  | RL > RA | 12% | 2.3 / 8.6 |
|  |  | SG | 12% | 4.9 |
| S10 (967, 328, 350; by YA) | 371 | RL | 32% | 3.5 |
|  |  | YA | 23% | 1.1 |
|  |  | PG | 12% | 6.0 |
| S11 (-32, 41, 222; by RL) | 360 | LG | 34% | 5.1 |
|  |  | LG > YA2 | 19% | 5.0 / 6.2 |
|  |  | RA | 25% | 1.9 |
| S12 (-95, 575, 478; by YA2) | 345 | RL | 59% | 2.1 |
|  |  | RL > YA | 11% | 2.1 / 7.4 |
|  |  | YA2 | 12% | 3.6 |
| S13 (241, 804, 478; by YA2) | 343 | PG | 44% | 3.1 |
|  |  | PG > YA | 14% | 3.1 / 5.5 |
|  |  | RL | 20% | 3.8 |
|  |  | YA2 | 16% | 3.8 |
|  |  | YA2 > LG | 14% | 3.8 / 4.9 |
| S14 (744, 1, 414; by YA) | 295 | RL | 54% | 2.7 |
|  |  | RL > MH | 14% | 2.8 / 6.9 |
|  |  | RL > RA | 12% | 2.7 / 8.1 |
|  |  | SG | 11% | 6.0 |
| S15 (101, 336, 30; by GL) | 212 | RA | 52% | 1.1 |
|  |  | RA > SG | 18% | 1.1 / 5.8 |
|  |  | RA > GL | 13% | 1.1 / 2.6 |
|  |  | SG | 15% | 5.7 |
|  |  | GL | 10% | 2.7 |
| S16 (512, -63, 30; by RA) | 175 | RA | 58% | 1.0 |
|  |  | RA > SG | 14% | 1.0 / 5.2 |
|  |  | RA > GL | 13% | 1.0 / 2.9 |
|  |  | RA > PG | 11% | 1.1 / 6.8 |
|  |  | SG | 17% | 5.3 |
| S17 (648, 488, 414; by YA) | 101 | RL | 44% | 3.0 |
|  |  | YA | 33% | 1.5 |
|  |  | YA > RL | 15% | 1.6 / 9.2 |

The enemy: in 3285 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 38% of the time; 40% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (469 lives) they took it 29% of the time; 35% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (615 lives) they took it 43% of the time; 37% at the rate of the lives without him there.

### sinister

147 demos (1278 minutes of play), 184 spawn lives (135 of them a game's start), 11 spawn points, 18 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (1096, 1256, 536; by RA) | 24 | RA | 75% | 1.5 |
|  |  | RA > LG | 58% | 1.5 / 3.4 |
|  |  | RA > LG > GL | 25% | 1.5 / 3.4 / 6.8 |
|  |  | LG | 21% | 3.0 |
| S2 (-304, -208, 280; by RL) | 21 | RL | 57% | 1.3 |
|  |  | RL > MH | 29% | 1.3 / 3.9 |
|  |  | MH | 29% | 2.2 |
| S3 (-304, 688, 312; by RL) | 20 | RL | 75% | 1.4 |
|  |  | RA | 25% | 3.5 |
| S4 (1272, 488, 88; by RL2) | 19 | RL2 | 100% | 0.6 |
|  |  | RL2 > MH | 47% | 0.6 / 3.2 |
| S5 (1192, -384, 280; by YA2) | 18 | RG | 78% | 1.5 |
|  |  | RG > MH | 39% | 1.4 / 3.2 |
| S6 (1344, -424, 472; by YA2) | 16 | YA2 | 75% | 1.0 |
|  |  | YA2 > RG | 62% | 1.0 / 2.7 |
|  |  | YA2 > RG > MH | 31% | 1.1 / 2.7 / 4.7 |
| S7 (680, 352, 536; by SG) | 13 | RA | 77% | 2.0 |
|  |  | RA > LG | 46% | 2.0 / 3.9 |
| S8 (160, 384, 312; by SG) | 11 | SG | 100% | 0.7 |
|  |  | SG > RA | 46% | 0.8 / 3.3 |
| S9 (-584, 352, 16; by YA) | 10 | YA | 60% | 0.8 |
|  |  | YA > RL | 50% | 0.8 / 2.1 |
| S10 (408, 280, 0; by PG) | 7 | MH | 86% | 1.3 |
|  |  | MH > RA | 71% | 1.3 / 5.0 |
| S11 (56, 504, 0; by SG) | 7 | LG | 71% | 1.6 |

### furiousheights

150 demos (1338 minutes of play), 202 spawn lives (141 of them a game's start), 16 spawn points, 33 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (-1952, -160, 88; by SG) | 16 | SG | 88% | 1.0 |
|  |  | SG > RA | 69% | 1.1 / 2.5 |
|  |  | SG > RA > YA2 | 38% | 1.0 / 2.4 / 4.8 |
| S2 (96, 736, 24; by RL) | 14 | RL | 100% | 1.0 |
|  |  | RL > MH | 64% | 1.0 / 3.1 |
|  |  | RL > MH > LG | 36% | 1.0 / 3.1 / 5.6 |
| S3 (-1688, 608, 0; by RA) | 14 | RA | 93% | 1.1 |
|  |  | RA > PG | 57% | 1.1 / 2.2 |
| S4 (16, 352, 27; by RL) | 12 | RL | 100% | 0.6 |
|  |  | RL > MH | 50% | 0.6 / 2.8 |
|  |  | RL > MH > LG | 50% | 0.6 / 2.8 / 5.1 |
| S5 (-928, 424, 24; by PG) | 12 | PG | 100% | 0.7 |
|  |  | PG > RA | 83% | 0.7 / 1.8 |
|  |  | PG > RA > RG | 42% | 0.6 / 1.7 / 4.2 |
| S6 (-864, 1440, 440; by GL) | 11 | GL | 100% | 0.3 |
| S7 (96, 480, 24; by RL) | 11 | RL | 100% | 0.6 |
|  |  | RL > MH | 64% | 0.6 / 2.8 |
| S8 (-1312, 800, 440; by YA2) | 10 | none kept (0% of lives took nothing big in 15 s) | | |
| S9 (-1264, 448, 30; by PG) | 10 | PG | 80% | 0.7 |
| S10 (-616, 920, 344; by YA2) | 10 | none kept (20% of lives took nothing big in 15 s) | | |
| S11 (-528, 104, 472; by LG) | 10 | none kept (0% of lives took nothing big in 15 s) | | |
| S12 (-336, 960, 219; by YA) | 8 | none kept (0% of lives took nothing big in 15 s) | | |
| S13 (-1631, 801, 27; by RA) | 8 | none kept (0% of lives took nothing big in 15 s) | | |
| S14 (-544, 112, 24; by LG) | 8 | none kept (25% of lives took nothing big in 15 s) | | |
| S15 (288, -160, 472; by LG) | 8 | LG | 75% | 1.6 |
| S16 (-416, 864, 30; by RL) | 7 | none kept (0% of lives took nothing big in 15 s) | | |

### battleforged

149 demos (1347 minutes of play), 276 spawn lives (138 of them a game's start), 10 spawn points, 34 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (352, -16, -72; by RL) | 46 | RL | 85% | 1.3 |
|  |  | RL > MH | 28% | 1.3 / 3.4 |
|  |  | RL > MH > SG | 11% | 1.4 / 3.4 / 5.0 |
|  |  | RL > RA | 20% | 1.4 / 7.4 |
|  |  | RL > GA | 15% | 1.3 / 5.6 |
|  |  | RA | 11% | 2.6 |
| S2 (-976, -152, 24; by GA) | 41 | RG | 100% | 1.6 |
|  |  | RG > GA | 20% | 1.7 / 4.8 |
|  |  | RG > GA > RL | 12% | 1.6 / 4.8 / 7.6 |
| S3 (-352, -600, -200; by RL2) | 38 | RL2 | 100% | 0.5 |
|  |  | RL2 > MH | 37% | 0.5 / 3.4 |
|  |  | RL2 > MH > SG | 16% | 0.5 / 3.3 / 4.9 |
|  |  | RL2 > YA | 26% | 0.5 / 2.1 |
| S4 (392, -16, -296; by LG) | 32 | LG | 100% | 1.0 |
|  |  | LG > MH | 34% | 1.1 / 4.5 |
|  |  | LG > MH > SG | 16% | 1.2 / 4.5 / 6.5 |
|  |  | LG > RA | 28% | 1.0 / 5.5 |
| S5 (1039, 472, -130; by RA) | 18 | RA | 33% | 1.0 |
|  |  | RL | 28% | 3.7 |
|  |  | PG | 28% | 2.8 |
| S6 (-864, 431, -66; by GA) | 17 | RG | 76% | 2.6 |
| S7 (232, -1199, -130; by YA) | 17 | LG | 59% | 2.9 |
| S8 (1055, -152, -322; by LG) | 15 | LG | 47% | 2.1 |
|  |  | PG | 40% | 2.5 |
| S9 (103, -256, -465; by SG) | 12 | SG | 83% | 1.0 |
| S10 (392, -114, -296; by LG) | 6 | LG | 100% | 0.6 |

### campgrounds

5 demos (46 minutes of play), 49 spawn lives (5 of them a game's start), 3 spawn points, 34 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (-576, 1087, 161; by LG) | 5 | none kept (60% of lives took nothing big in 15 s) | | |
| S2 (447, -161, 289; by RG) | 5 | none kept (80% of lives took nothing big in 15 s) | | |
| S3 (887, -512, 417; by RG) | 5 | none kept (80% of lives took nothing big in 15 s) | | |

### hektik

144 demos (1232 minutes of play), 749 spawn lives (138 of them a game's start), 10 spawn points, 28 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (-975, 321, 167; by RG) | 129 | RG | 81% | 1.7 |
|  |  | RG > LG | 26% | 1.6 / 4.4 |
|  |  | RG > MH | 14% | 1.6 / 6.2 |
| S2 (599, 945, 262; by PG) | 101 | RL | 93% | 1.3 |
|  |  | RL > RA | 29% | 1.4 / 3.8 |
|  |  | RL > RG | 21% | 1.3 / 4.9 |
|  |  | RL > MH | 12% | 1.3 / 5.0 |
| S3 (-527, -519, 231; by RL2) | 88 | RL2 | 99% | 0.6 |
|  |  | RL2 > GL | 24% | 0.7 / 3.5 |
|  |  | RL2 > YA | 19% | 0.6 / 4.4 |
|  |  | RL2 > RG | 10% | 0.7 / 7.9 |
| S4 (-9, -543, 271; by YA) | 87 | RL2 | 91% | 1.3 |
|  |  | RL2 > GL | 22% | 1.3 / 4.7 |
|  |  | RL2 > YA | 16% | 1.3 / 3.7 |
|  |  | RL2 > RA | 13% | 1.3 / 6.8 |
| S5 (-615, 55, 63; by RL2) | 86 | YA | 44% | 1.7 |
|  |  | YA > RL2 | 34% | 1.7 / 3.4 |
|  |  | RG | 43% | 2.3 |
| S6 (288, -351, -1; by MH) | 83 | LG | 53% | 2.2 |
|  |  | LG > MH | 14% | 2.1 / 4.8 |
|  |  | YA | 20% | 2.2 |
| S7 (-103, 1031, 63; by RL) | 77 | RG | 62% | 2.4 |
|  |  | GA | 14% | 1.9 |
|  |  | LG | 12% | 2.9 |
| S8 (-496, 399, 263; by RG) | 30 | RL2 | 40% | 2.2 |
|  |  | RG | 23% | 3.4 |
|  |  | RA | 17% | 2.7 |
| S9 (-160, -159, -145; by SG) | 22 | SG | 91% | 0.2 |
|  |  | SG > MH | 27% | 0.2 / 1.9 |
| S10 (-472, 369, 63; by RG) | 18 | RG | 89% | 0.7 |
|  |  | RG > LG | 28% | 0.7 / 3.1 |

The enemy: in 171 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 33% of the time; 36% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (29 lives) they took it 31% of the time; 29% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (75 lives) they took it 51% of the time; 52% at the rate of the lives without him there.

### toxicity

87 demos (755 minutes of play), 582 spawn lives (87 of them a game's start), 8 spawn points, 12 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (79, 2256, 1215; by YA) | 115 | YA | 36% | 0.8 |
|  |  | YA > LG | 19% | 0.8 / 2.1 |
|  |  | YA > RL | 12% | 0.9 / 2.6 |
|  |  | LG | 33% | 1.9 |
|  |  | LG > RL | 17% | 1.9 / 3.9 |
|  |  | RL | 24% | 2.3 |
| S2 (96, 1904, 1119; by GL) | 99 | RL | 80% | 1.3 |
|  |  | RL > LG | 12% | 1.4 / 7.3 |
|  |  | RL > YA | 10% | 1.5 / 5.5 |
| S3 (-193, 928, 1215; by MH) | 80 | RL2 | 75% | 1.3 |
|  |  | RL2 > MH | 21% | 1.4 / 4.5 |
|  |  | RL2 > YA2 | 18% | 1.3 / 3.0 |
|  |  | RL2 > LG | 10% | 1.4 / 5.1 |
| S4 (-1312, 2072, 1007; by RA) | 78 | PG | 91% | 0.8 |
|  |  | PG > RG | 32% | 0.9 / 3.3 |
|  |  | PG > RA | 31% | 0.8 / 1.9 |
|  |  | PG > RA > RG | 13% | 0.8 / 1.7 / 6.9 |
| S5 (-1344, 1409, 1119; by RG) | 75 | RG | 83% | 1.7 |
|  |  | RG > RA | 24% | 1.7 / 3.3 |
|  |  | RG > RA > PG | 13% | 1.6 / 3.1 / 4.0 |
|  |  | RG > PG | 13% | 1.6 / 4.6 |
|  |  | RG > PG > RA | 11% | 1.6 / 2.8 / 5.6 |
|  |  | RG > LG | 11% | 1.7 / 6.0 |
|  |  | RL2 | 11% | 3.1 |
| S6 (-184, 1489, 1247; by MH) | 66 | RL | 27% | 1.6 |
|  |  | RL > MH | 14% | 1.7 / 4.6 |
|  |  | RL2 | 26% | 3.1 |
|  |  | RL2 > MH | 11% | 2.9 / 5.1 |
|  |  | YA | 12% | 2.9 |
| S7 (-976, 1777, 1248; by PG) | 39 | RG | 54% | 1.8 |
|  |  | RG > RA | 18% | 1.8 / 3.8 |
|  |  | RG > RA > PG | 13% | 1.7 / 3.8 / 5.2 |
|  |  | LG | 26% | 1.9 |
| S8 (-512, 1240, 1038; by RL2) | 18 | YA2 | 50% | 1.3 |
|  |  | YA2 > RL2 | 39% | 1.3 / 2.9 |
|  |  | RL2 | 28% | 2.7 |

The enemy: in 209 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 44% of the time; 43% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (9 lives) they took it 0% of the time; 35% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (68 lives) they took it 37% of the time; 36% at the rate of the lives without him there.

### cure

129 demos (1106 minutes of play), 424 spawn lives (124 of them a game's start), 11 spawn points, 28 starts at no spawn point left out.

| spawn | lives | opening (items in order) | share | seconds to first / second / third |
|---|---|---|---|---|
| S1 (-355, 32, -34; by GA) | 53 | RA | 32% | 2.5 |
|  |  | RA > RG | 24% | 2.5 / 6.2 |
|  |  | RA > RG > RL2 | 21% | 2.5 / 6.1 / 7.8 |
|  |  | RL2 | 26% | 3.0 |
|  |  | RL2 > GA | 13% | 2.9 / 6.2 |
|  |  | RG | 13% | 4.8 |
|  |  | RG > RL2 | 11% | 4.7 / 7.1 |
|  |  | RL | 13% | 3.5 |
| S2 (-355, -96, -34; by GA) | 50 | RL2 | 36% | 3.1 |
|  |  | RL2 > RA | 18% | 3.2 / 8.0 |
|  |  | RA | 26% | 2.5 |
|  |  | RA > RG | 14% | 2.5 / 6.1 |
|  |  | RL | 10% | 3.9 |
|  |  | RG | 10% | 4.7 |
| S3 (799, 543, -98; by RL) | 40 | RL | 98% | 0.7 |
|  |  | RL > YA | 28% | 0.7 / 3.8 |
|  |  | RL > LG | 15% | 0.7 / 5.8 |
|  |  | RL > PG | 12% | 0.7 / 3.8 |
| S4 (1696, -160, -2; by SG) | 40 | SG | 42% | 2.2 |
|  |  | SG > YA | 12% | 2.2 / 4.7 |
|  |  | SG > MH | 12% | 2.1 / 4.7 |
|  |  | LG | 22% | 3.2 |
|  |  | LG > GA2 | 20% | 3.2 / 5.2 |
|  |  | LG > GA2 > MH | 15% | 3.2 / 5.5 / 7.5 |
|  |  | RL | 15% | 3.5 |
|  |  | RL > YA | 12% | 3.7 / 7.1 |
|  |  | GA2 | 12% | 3.3 |
| S5 (1344, 32, -98; by SG) | 40 | LG | 62% | 2.4 |
|  |  | LG > GA2 | 38% | 2.4 / 4.4 |
|  |  | LG > GA2 > MH | 22% | 2.4 / 4.4 / 6.5 |
|  |  | GA2 | 20% | 2.9 |
|  |  | GA2 > MH | 15% | 2.9 / 4.7 |
|  |  | GA2 > MH > LG | 12% | 2.9 / 4.7 / 6.3 |
| S6 (1168, 464, 222; by SG) | 34 | SG | 79% | 1.4 |
|  |  | SG > MH | 44% | 1.4 / 3.4 |
|  |  | SG > MH > LG | 41% | 1.3 / 3.4 / 5.3 |
| S7 (-24, 91, -34; by PG) | 34 | RA | 41% | 2.2 |
|  |  | RA > RG | 29% | 2.2 / 5.9 |
|  |  | RA > RG > RL2 | 21% | 2.2 / 5.8 / 7.5 |
|  |  | RL2 | 24% | 3.0 |
|  |  | RG | 18% | 4.2 |
|  |  | RG > RL2 | 15% | 4.2 / 8.0 |
| S8 (-359, 487, 350; by GA) | 33 | GA | 48% | 0.3 |
|  |  | GA > PG | 46% | 0.3 / 1.6 |
|  |  | GA > PG > YA | 21% | 0.3 / 1.6 / 3.1 |
|  |  | PG | 39% | 1.6 |
|  |  | PG > YA | 15% | 1.6 / 2.7 |
| S9 (153, 871, 286; by PG) | 31 | PG | 81% | 1.4 |
|  |  | PG > GA | 29% | 1.6 / 2.8 |
|  |  | PG > GA > YA | 16% | 1.4 / 2.8 / 5.1 |
|  |  | PG > RL2 | 23% | 1.4 / 5.0 |
|  |  | PG > YA | 23% | 1.4 / 2.7 |
|  |  | PG > YA > RL | 16% | 1.4 / 2.7 / 3.9 |
| S10 (1024, -862, -98; by LG) | 26 | LG | 62% | 1.8 |
|  |  | LG > GA2 | 19% | 1.8 / 5.3 |
|  |  | GA2 | 23% | 1.5 |
| S11 (416, -542, 414; by RL2) | 15 | RL2 | 53% | 2.2 |
|  |  | RL2 > RA | 33% | 2.1 / 4.4 |

The enemy: in 125 lives with his place at the frag known and a choice of first pickup, the pros took the one farthest from him 36% of the time; 34% if the choice did not depend on him.
With him within 500 units of an armor or the mega that is one of the spawn's first pickups (13 lives) they took it 8% of the time; 8% at the rate of the lives without him there.
With him within 500 units of a weapon that is one of the spawn's first pickups (31 lives) they took it 29% of the time; 44% at the rate of the lives without him there.

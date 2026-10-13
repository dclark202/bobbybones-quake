# His openings beside the pros': v0.2

Written by `tools/opening_check.py report` from games the network played against itself in the simulator (`play`: the set-up of `tools/duel_eval.py`, ten-minute games, both seats the same network, every life of either seat counted) and the pros' lives of the demo sets (`pros`; the openings themselves: [README.md](README.md), `sim/pro_spawn_openings/<map>.json`). The definitions are the pros' (`tools/pro_openings.py`): a spawn life, a big pickup (mega MH, red RA, yellow YA, green GA, the weapons; a dropped weapon is none), the first pickups within 15 s. A spawn is the pros' spawn point nearest to his start (within 100 units). Shares are of the spawn's lives; times are medians in seconds from the spawn. "He takes the pros' first": the share of his lives whose first big pickup is the pros' commonest first pickup at that spawn; "one of the pros' openings": ... is the first pickup of any opening the pros' file keeps for the spawn (5 lives and 10% of the spawn's lives). "To the pros' item, taken first": the median time to that item in the lives that took it first, his and theirs (like for like: a route's speed). "His first intention": the first target his intention output names in the life. "On his legs": the share of the first ten seconds' frames the movement network moved him.

<!-- notes -->
## What stands out (2026-10-13)

The network: v0.2's end in today's input shape (`data/sim_runs/duel_gru_v0_2_1/policy_control.pt`), against itself, with the settings of today's checks against the control (aim level 1.5, his legs on with `move_v15n`, `TARGETS=1`, `STYLE_P=0.75`, and the rest of that list). 64 ten-minute games a map on Blood Run, Aerowalk, Lost World and Hektik; both seats' lives are counted (1,220 to 2,285 lives a map). Toxicity and Cure were not played: the PC filled up with another job and the games, at the lowest priority, stood still; they were stopped.

- **His opening is a weapon, always one of three.** In every life on every map (all but two or three in a thousand) the first target his intention names after a spawn is the rocket launcher, the railgun or lightning; never an armor, the mega or a holding place. His first big pickup is that weapon in 93% of lives on Blood Run, 96% on Lost World, 85% on Hektik, 66% on Aerowalk (where spawns lie on an armor). The pros open the same way where one of those three lies at the spawn, and there his general lives match them: Blood Run S1, S2, S6, S12 (94 to 98% against the pros' 90 to 95%), Aerowalk S3 (98% against 93%), Lost World S4, S5, S6, S9, S11, S12, S14, Hektik S2, S3, S4.
- **Three lives in four the style decides, not the spawn.** In a styled life (rockets, rail, lightning: `STYLE_P`) he goes to the style's weapon wherever he stands: Blood Run, rail lives RG first in 89%, lightning lives LG 84%, rocket lives RL 81%. So from Blood Run's rocket spawn S1 he walks to lightning (5.3 s, 59 lives) or to the railgun (6.5 s, 47 lives), which no pro does (0 and 2 of 1,060 lives), and "he takes the pros' first pickup" is 24% on Blood Run over all lives against 42% in general lives (Aerowalk 29% / 27%, Lost World 39% / 52%, Hektik 41% / 58%). This is the largest single cause of his slower first pickup (Blood Run 3.5 s against 2.3 s, Lost World 5.1 against 3.0, Hektik 2.4 against 1.6, Aerowalk 2.1 against 1.9).
- **What he cannot name he does not open with.** Shotgun, grenades, plasma and the green armor are no intentions, and the armors and mega are never his first: Lost World S3 (the pros: shotgun 99% at 0.5 s; he 32%, and only by running over it, on his way to rockets at 9.8 s), S1 (plasma 65%; he 0%, rockets at 7.0 s), S15 and S16 (the red armor 53% and 58% at about 1.1 s; he 0%: 75% of his lives there have NO big pickup in ten seconds, his median first pickup is lightning after 10 to 11 s, against the pros' 13 to 16% and 1.2 to 1.9 s), Blood Run S3 (the yellow armor 0.9 s away: pros 37%, he 1%), S4 (yellow armor and plasma: pros 75%, he 0%: lightning after 4.8 s), S5 and S8 (grenades 39% and 56%; he 3% and 0%), Aerowalk S8 (shotgun 82%; he 0%, rockets after 4.3 s), S1 (grenades or the yellow armor), S4 (rail at the spawn 77%; his general lives go to rockets, 0%), Hektik S1 (rail 82%; his general lives rockets 88%), S7 (rail 62%; general lives 3%), S5 (yellow armor 46%; he 1%). Where he spawns ON an armor he takes it (Aerowalk S7 red 92% at 0.1 s, S6 green 77%).
- **His ways are as fast as theirs.** Like for like (the same spawn, the same item taken first) he is within half a second of the pros nearly everywhere (see each map's "ways" table: 67 of 83 pairs within 0.6 s, ten faster by 0.5 s or more). The exceptions, a route problem each: Blood Run S3 to rockets 8.1 s against 4.5 (60 lives; +3.6) and S9 to rockets 4.0 against 2.0 (13 lives); Blood Run S8 to lightning 5.7 against 4.6; Aerowalk S1 to RL2 5.6 against 4.4, S8 to RL2 4.3 against 3.0; Hektik S5 to RL2 5.0 against 3.4, S6 to RL2 and to rail +0.9 each (the pros' side of these is 5 to 44 lives but for Blood Run S3 and S9). The slow first pickup is a matter of what he goes for, not of his legs.
- **Lives with nothing in ten seconds**: about the pros' share on Blood Run (8% against 9%), Aerowalk (4% / 9%) and Hektik (4% / 3%); more on Lost World (19% against 14%), all of it at the spawns named above (S15, S16, S17 about 75%, S3 30%, S8 31%, S14 34%) and in rocket lives (30%). Blood Run S2: 21% against 1%, none of it in general lives (lightning is there; a rail or a rocket life leaves it lying).
- **The enemy at an armor.** For the first pickup it cannot be measured for him: he does not open on armors, and the simulator's spawn rule puts him far from the enemy (5% of respawns nearer than 720 to 880 units, the median 1,000 to 1,260). For the second pickup, counted the same way for both (an armor or the mega that is a usual second pickup of the spawn, the enemy within 500 units of it at the spawn; pros: at the frag): he takes it 4% of the time against 16% without the enemy there on Blood Run (pros 6% against 12%), 5% against 13% on Lost World (pros 9% / 10%), 6% against 12% on Hektik (pros 8% / 11%), 4% against 3% on Aerowalk (pros 8% / 8%). He holds back from a watched armor at least as much as they do. (The pros' 22 to 29% against 35 to 50% in [README.md](README.md) is the first pickup among the lives that took one of the spawn's openings; by this page's count, over all lives with his place known, their first-pickup numbers are 13% against 36%, 18% against 32%, 20% against 25%.) When his second pickup is an armor or the mega, the enemy truly stands within 500 units of it at that moment in 20% (Blood Run), 23% (Lost World), 41% (Hektik), 42% (Aerowalk) of the lives, and he nearly always knows (seen or heard within three seconds).
- **His legs** carried him 63% of the first ten seconds on Blood Run, 77% on Lost World, 47% on Hektik, 39% on Aerowalk.
- **Doubtful.** (1) The spawn points: the simulator spawns at the map file's entities and prefers one away from the enemy, so his lives are spread unlike the pros' (Blood Run: 279 at S1, 36 at S9) and four of the pros' thirteen Blood Run places never occur (S7, S10, S11, S13: not in the map file, see the README's note); one entity on Blood Run and one on Lost World are at no place of the pros' (16 and 35 lives, left out). (2) Both seats are the same network: what the enemy does to his opening is what a copy of himself does. (3) The pros' lives come from stretches of a demo (a cut ends one): 27% of theirs end within ten seconds against 13% of his, which raises their "none in ten seconds" a little. (4) A spawn with fewer than about 30 lives of his (Blood Run S9, Aerowalk S8, Lost World S15 to S17, Hektik S9) moves by ten points by chance; the general-lives table has a quarter of the lives. (5) A game's first spawn is counted like any other (128 lives a map), as in the pros' file. (6) The enemy's place is the true one at the spawn frame for him and up to a second before the death for the pros.
- **What follows from it** (for B-244 / B-245, not done here): an opening taught per spawn would have to cover what he cannot name today (shotgun, grenades, plasma, the green armor as targets; an armor as a first target), and a styled life would have to take the spawn's weapon first and the style's after.
<!-- tables -->

## The maps in one table

| map | games | his lives at the pros' spawns | first pickup = the pros' commonest | ... in his general lives | ... = one of the pros' openings | s to first pickup: he | pros | none in 10 s: he | pros | armor or mega as FIRST pickup with the enemy at it: he (without him) | pros (without him) | ... as SECOND pickup: he (without him) | pros (without him) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bloodrun | 64 | 1580 | 24% | 42% | 42% | 3.5 | 2.3 | 8% | 9% | - | 13% (36%), 109 lives | 4% (16%), 327 lives | 6% (12%), 1579 lives |
| aerowalk | 64 | 2285 | 29% | 27% | 59% | 2.1 | 1.9 | 4% | 9% | 67% (61%), 3 lives | 18% (32%), 477 lives | 4% (3%), 523 lives | 8% (8%), 2791 lives |
| lostworld | 64 | 1185 | 39% | 52% | 60% | 5.1 | 3.0 | 19% | 14% | 0% (0%), 61 lives | 20% (25%), 691 lives | 5% (13%), 605 lives | 9% (10%), 3057 lives |
| hektik | 64 | 1880 | 41% | 58% | 51% | 2.4 | 1.6 | 4% | 3% | 0% (1%), 48 lives | 24% (22%), 37 lives | 6% (12%), 982 lives | 8% (11%), 268 lives |

The seconds and the pros' "none" in this table are means over the spawns weighted by his lives there (so that the two columns are of the same mix of spawns).

### bloodrun

64 games of 10 minutes, 1596 lives of his (12.5 a player a game; 128 of them a game's start); 16 at a spawn entity the pros' sets do not show (left out). The pros: 6751 lives in 1066 demos.

| spawn | his lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | to the pros' item, taken first: he | pros | none in 10 s: he | pros | his first intention | on his legs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 (1230, -1312, 286; by RL) | 279 | RL 48% | RL 93% | 48% | 48% | RL > YA2 20% | 2.6 | 1.6 | 1.9 | 1.6 | 11% | 5% | RL 48% | 61% |
| S2 (1119, 225, 94; by LG) | 151 | LG 46% | LG 92% | 46% | 46% | LG > MH 14% | 2.4 | 1.4 | 1.5 | 1.3 | 21% | 1% | LG 46% | 53% |
| S3 (863, -802, 94; by YA2) | 139 | RL 43% | YA2 37% | 1% | 65% | RL > YA2 21% | 5.3 | 3.4 | 7.8 | 0.9 | 9% | 13% | RL 46% | 66% |
| S4 (354, 480, 446; by PG) | 166 | LG 48% | YA 49% | 0% | 0% | SG > RL 19% | 4.7 | 2.4 | - | 2.1 | 3% | 4% | LG 50% | 71% |
| S5 (-640, -846, 414; by GL) | 276 | RG 48% | GL 39% | 3% | 26% | RL > YA2 9% | 4.5 | 4.1 | 2.1 | 2.2 | 7% | 22% | RG 50% | 65% |
| S6 (241, -1137, 280; by RL) | 216 | RL 52% | RL 90% | 52% | 52% | RL > YA2 20% | 1.6 | 1.4 | 1.5 | 1.4 | 6% | 4% | RL 52% | 63% |
| S7 (-703, -831, 414; by GL) | 0 | (he never spawned here) | RL 44% | | | | | 4.2 | | 4.3 | | 19% | | |
| S8 (-193, -847, 414; by GL) | 250 | RL 52% | GL 56% | 0% | 52% | RL > YA2 18% | 4.0 | 2.1 | - | 1.6 | 3% | 11% | RL 52% | 66% |
| S9 (496, -720, 447; by YA2) | 36 | RL 36% | RL 51% | 36% | 36% | RL > YA2 11% | 4.6 | 2.2 | 4.0 | 2.0 | 11% | 4% | RL 42% | 63% |
| S10 (735, -352, 543; by MH) | 0 | (he never spawned here) | SG 58% | | | | | 1.9 | | 1.6 | | 6% | | |
| S11 (-735, -224, 415; by GL) | 0 | (he never spawned here) | GL 52% | | | | | 1.9 | | 1.4 | | 14% | | |
| S12 (95, -41, 30; by RG) | 67 | RG 58% | RG 95% | 58% | 58% | RG > MH 19% | 1.2 | 1.1 | 1.1 | 1.1 | 1% | 2% | RG 58% | 57% |
| S13 (31, -9, 30; by RG) | 0 | (he never spawned here) | RG 96% | | | | | 1.0 | | 1.0 | | 4% | | |

His general lives alone (in the others his style this life, rockets, rail or lightning, names his weapon):

| spawn | his general lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | none in 10 s: he | pros |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 65 | RL 98% | RL 93% | 98% | 98% | RL > YA2 38% | 1.9 | 1.6 | 0% | 5% |
| S2 | 31 | LG 94% | LG 92% | 94% | 94% | LG > YA2 32% | 1.5 | 1.4 | 0% | 1% |
| S3 | 33 | RL 88% | YA2 37% | 0% | 91% | RL > YA2 42% | 7.7 | 3.4 | 6% | 13% |
| S4 | 52 | LG 83% | YA 49% | 0% | 0% | LG > MH 25% | 4.8 | 2.4 | 2% | 4% |
| S5 | 74 | RG 89% | GL 39% | 0% | 9% | RG > MH 12% | 4.1 | 4.1 | 1% | 22% |
| S6 | 54 | RL 96% | RL 90% | 96% | 96% | RL > YA2 43% | 1.5 | 1.4 | 0% | 4% |
| S8 | 68 | RL 94% | GL 56% | 0% | 94% | RL > YA2 34% | 3.9 | 2.1 | 0% | 11% |
| S9 | 8 | RL 75% | RL 51% | 75% | 75% | RL > YA2 25% | 9.0 | 2.2 | 25% | 4% |
| S12 | 21 | RG 95% | RG 95% | 95% | 95% | RG > MH 33% | 1.1 | 1.1 | 0% | 2% |

His ways beside theirs: the median seconds from a spawn to a first pickup, where he took it first in 8 lives or more and the pros in 5 or more.

| spawn | first pickup | his lives | his seconds | the pros' lives | the pros' seconds | he is slower by |
|---|---|---|---|---|---|---|
| S1 | RL | 133 | 1.9 | 994 | 1.6 | +0.3 |
| S1 | LG | 59 | 5.3 | 0 | - | (the pros do not open so) |
| S1 | RG | 47 | 6.5 | 2 | - | (the pros do not open so) |
| S1 | YA2 | 9 | 2.1 | 13 | 2.4 | -0.3 |
| S2 | LG | 70 | 1.5 | 947 | 1.3 | +0.2 |
| S2 | RG | 37 | 5.0 | 1 | - | (the pros do not open so) |
| S2 | RL | 22 | 11.0 | 0 | - | (the pros do not open so) |
| S3 | RL | 60 | 8.1 | 146 | 4.5 | +3.6 |
| S3 | RG | 38 | 4.3 | 30 | 4.7 | -0.4 |
| S3 | LG | 30 | 3.4 | 158 | 3.5 | -0.1 |
| S4 | LG | 80 | 4.8 | 4 | - | (the pros do not open so) |
| S4 | RG | 41 | 5.0 | 17 | 4.2 | +0.8 |
| S4 | SG | 40 | 3.6 | 79 | 3.2 | +0.4 |
| S5 | RG | 132 | 4.1 | 19 | 3.8 | +0.3 |
| S5 | RL | 64 | 4.6 | 132 | 4.5 | +0.0 |
| S5 | LG | 57 | 6.1 | 2 | - | (the pros do not open so) |
| S5 | GL | 9 | 2.1 | 190 | 2.2 | -0.1 |
| S6 | RL | 113 | 1.5 | 394 | 1.4 | +0.1 |
| S6 | RG | 48 | 5.4 | 5 | 7.0 | -1.6 |
| S6 | LG | 33 | 5.0 | 1 | - | (the pros do not open so) |
| S6 | YA2 | 9 | 1.6 | 6 | 2.0 | -0.4 |
| S8 | RL | 131 | 3.9 | 83 | 4.0 | -0.1 |
| S8 | LG | 63 | 5.7 | 5 | 4.6 | +1.1 |
| S8 | RG | 50 | 3.4 | 25 | 3.3 | +0.1 |
| S9 | RL | 13 | 4.0 | 179 | 2.0 | +2.0 |
| S9 | LG | 10 | 5.5 | 2 | - | (the pros do not open so) |
| S9 | RG | 10 | 4.0 | 9 | 4.0 | +0.1 |
| S12 | RG | 39 | 1.1 | 117 | 1.1 | +0.0 |
| S12 | LG | 15 | 3.5 | 1 | - | (the pros do not open so) |
| S12 | SG | 12 | 4.1 | 1 | - | (the pros do not open so) |

The enemy within 500 units of an armor or the mega that is one of the spawn's usual first pickups: he takes it as his first pickup - of the time (0 lives; - at the rate of his lives without the enemy there); the pros 13% (109 lives; 36% without him there).
The enemy within 500 units of an armor or the mega that is one of the spawn's usual second pickups: he takes it as his second pickup 4% of the time (327 lives; 16% at the rate of his lives without the enemy there); the pros 6% (1579 lives; 12% without him there).
His second pickup is an armor or the mega in 664 lives; in 20% of them the enemy stood within 500 units of it at the moment he took it, and in 100% of those he had seen or heard him in the three seconds before.
By the kind of life: lightning (407 lives): none in 10 s 12%, first pickup LG 84%, YA 3%, GL 2%; general (406 lives): none in 10 s 1%, first pickup RL 55%, RG 25%, LG 18%; rockets (387 lives): none in 10 s 9%, first pickup RL 81%, SG 13%, MH 1%; rail (380 lives): none in 10 s 9%, first pickup RG 89%, YA 2%, RA 0%.

### aerowalk

64 games of 10 minutes, 2285 lives of his (17.9 a player a game; 128 of them a game's start). The pros: 10898 lives in 978 demos.

| spawn | his lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | to the pros' item, taken first: he | pros | none in 10 s: he | pros | his first intention | on his legs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 (959, -159, 150; by YA) | 270 | GL 23% | GL 42% | 23% | 25% | GL > RG 16% | 3.7 | 1.5 | 0.8 | 1.6 | 19% | 7% | RL 44% | 34% |
| S2 (407, 559, 382; by RL) | 479 | RL 46% | LG 49% | 31% | 77% | RL > RG 19% | 2.0 | 2.0 | 2.1 | 2.1 | 1% | 7% | RL 46% | 41% |
| S3 (775, 11, 382; by YA) | 231 | RL 58% | RL 93% | 58% | 58% | RL > RG 24% | 1.7 | 1.2 | 1.4 | 1.2 | 1% | 2% | RL 49% | 35% |
| S4 (544, -666, 382; by GA2) | 126 | RL 54% | RG 77% | 34% | 34% | RL > RG 20% | 2.6 | 1.6 | 1.7 | 1.5 | 3% | 9% | RL 56% | 37% |
| S5 (-131, 363, 150; by LG) | 488 | RL2 43% | RL 23% | 0% | 30% | RL2 > RG 20% | 3.4 | 3.8 | 4.1 | 3.7 | 3% | 24% | RL 48% | 39% |
| S6 (-606, -304, 150; by GA) | 350 | GA 77% | GA 49% | 77% | 87% | GA > RL2 37% | 0.3 | 0.8 | 0.3 | 0.2 | 0% | 2% | RL 47% | 39% |
| S7 (-384, -104, 366; by RA) | 298 | RA 92% | LG 81% | 2% | 94% | RA > RL2 45% | 0.1 | 1.4 | 1.6 | 1.4 | 0% | 3% | RL 48% | 49% |
| S8 (160, -351, -42; by MH) | 43 | RL2 42% | SG 82% | 0% | 0% | RL2 > RG 14% | 5.2 | 1.1 | - | 1.1 | 9% | 2% | RL 49% | 31% |

His general lives alone (in the others his style this life, rockets, rail or lightning, names his weapon):

| spawn | his general lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | none in 10 s: he | pros |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 61 | GA2 28% | GL 42% | 18% | 20% | GL > RL 18% | 3.3 | 1.5 | 10% | 7% |
| S2 | 106 | RL 92% | LG 49% | 7% | 99% | RL > RG 38% | 1.8 | 2.0 | 1% | 7% |
| S3 | 57 | RL 98% | RL 93% | 98% | 98% | RL > RG 49% | 1.4 | 1.2 | 0% | 2% |
| S4 | 39 | RL 95% | RG 77% | 0% | 0% | RL > RG 33% | 2.8 | 1.6 | 5% | 9% |
| S5 | 122 | RL2 90% | RL 23% | 0% | 1% | RL2 > RG 40% | 3.1 | 3.8 | 6% | 24% |
| S6 | 104 | GA 80% | GA 49% | 80% | 99% | GA > RL2 70% | 0.3 | 0.8 | 0% | 2% |
| S7 | 80 | RA 98% | LG 81% | 0% | 98% | RA > RL2 88% | 0.1 | 1.4 | 0% | 3% |
| S8 | 12 | RL2 75% | SG 82% | 0% | 0% | MH > RL2 17% | 4.5 | 1.1 | 8% | 2% |

His ways beside theirs: the median seconds from a spawn to a first pickup, where he took it first in 8 lives or more and the pros in 5 or more.

| spawn | first pickup | his lives | his seconds | the pros' lives | the pros' seconds | he is slower by |
|---|---|---|---|---|---|---|
| S1 | GL | 61 | 0.8 | 932 | 1.6 | -0.7 |
| S1 | RL2 | 39 | 5.6 | 44 | 4.4 | +1.1 |
| S1 | LG | 34 | 8.4 | 10 | 8.1 | +0.3 |
| S1 | GA2 | 26 | 2.3 | 118 | 2.5 | -0.2 |
| S1 | RG | 25 | 3.8 | 71 | 4.9 | -1.1 |
| S1 | SG | 20 | 3.8 | 72 | 3.7 | +0.1 |
| S1 | RL | 12 | 4.9 | 29 | 6.0 | -1.1 |
| S1 | MH | 10 | 3.1 | 37 | 3.4 | -0.3 |
| S2 | RL | 220 | 1.8 | 795 | 1.7 | +0.0 |
| S2 | LG | 147 | 2.1 | 962 | 2.1 | -0.0 |
| S2 | RG | 106 | 5.1 | 18 | 5.6 | -0.5 |
| S3 | RL | 133 | 1.4 | 1663 | 1.2 | +0.2 |
| S3 | RG | 66 | 2.9 | 53 | 2.9 | +0.0 |
| S3 | LG | 31 | 4.3 | 2 | - | (the pros do not open so) |
| S4 | RL | 68 | 2.8 | 121 | 3.4 | -0.6 |
| S4 | RG | 43 | 1.7 | 1362 | 1.5 | +0.2 |
| S4 | LG | 11 | 4.8 | 4 | - | (the pros do not open so) |
| S5 | RL2 | 212 | 3.1 | 56 | 3.4 | -0.2 |
| S5 | LG | 145 | 3.6 | 213 | 4.1 | -0.5 |
| S5 | RG | 106 | 3.2 | 93 | 3.4 | -0.2 |
| S5 | GA | 8 | 3.5 | 19 | 3.6 | -0.1 |
| S6 | GA | 271 | 0.3 | 474 | 0.2 | +0.1 |
| S6 | RL2 | 34 | 1.1 | 421 | 0.9 | +0.2 |
| S6 | LG | 24 | 2.3 | 4 | - | (the pros do not open so) |
| S6 | RG | 20 | 1.5 | 44 | 1.5 | +0.0 |
| S7 | RA | 273 | 0.1 | 85 | 0.0 | +0.0 |
| S7 | RG | 10 | 3.4 | 1 | - | (the pros do not open so) |
| S8 | RL2 | 18 | 4.3 | 8 | 3.0 | +1.3 |
| S8 | LG | 8 | 5.6 | 0 | - | (the pros do not open so) |
| S8 | RG | 8 | 5.2 | 15 | 4.5 | +0.8 |

The enemy within 500 units of an armor or the mega that is one of the spawn's usual first pickups: he takes it as his first pickup 67% of the time (3 lives; 61% at the rate of his lives without the enemy there); the pros 18% (477 lives; 32% without him there).
The enemy within 500 units of an armor or the mega that is one of the spawn's usual second pickups: he takes it as his second pickup 4% of the time (523 lives; 3% at the rate of his lives without the enemy there); the pros 8% (2791 lives; 8% without him there).
His second pickup is an armor or the mega in 322 lives; in 42% of them the enemy stood within 500 units of it at the moment he took it, and in 100% of those he had seen or heard him in the three seconds before.
By the kind of life: lightning (628 lives): none in 10 s 7%, first pickup LG 61%, RA 12%, GA 12%; general (581 lives): none in 10 s 3%, first pickup RL 61%, GA 18%, RA 13%; rail (544 lives): none in 10 s 2%, first pickup RG 66%, GA 11%, RA 10%; rockets (532 lives): none in 10 s 4%, first pickup RL 69%, GA 13%, RA 12%.

### lostworld

64 games of 10 minutes, 1220 lives of his (9.5 a player a game; 128 of them a game's start); 35 at a spawn entity the pros' sets do not show (left out). The pros: 7468 lives in 1222 demos.

| spawn | his lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | to the pros' item, taken first: he | pros | none in 10 s: he | pros | his first intention | on his legs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 (553, 1239, 182; by PG) | 117 | RL 67% | PG 65% | 0% | 0% | LG > YA2 12% | 7.1 | 2.8 | - | 2.7 | 10% | 12% | RL 73% | 82% |
| S2 (912, 1059, 350; by PG) | 111 | RL 55% | YA 36% | 0% | 55% | RL > RA 9% | 5.9 | 3.8 | - | 2.0 | 25% | 13% | RL 75% | 79% |
| S3 (1379, 467, 222; by SG) | 76 | RL 39% | SG 99% | 32% | 32% | SG > RL 28% | 8.9 | 0.5 | 0.5 | 0.5 | 30% | 1% | RL 75% | 79% |
| S4 (80, 1007, 478; by YA2) | 99 | RL 63% | RL 43% | 63% | 91% | RL > RA 13% | 3.2 | 3.1 | 3.0 | 2.9 | 12% | 11% | RL 74% | 73% |
| S5 (-390, 784, 478; by YA2) | 120 | LG 66% | LG 38% | 66% | 95% | LG > YA2 32% | 2.0 | 2.5 | 2.0 | 2.5 | 5% | 7% | LG 67% | 75% |
| S6 (-368, 287, 222; by YA2) | 108 | LG 73% | LG 67% | 73% | 73% | LG > YA2 41% | 4.0 | 3.8 | 3.9 | 3.8 | 9% | 21% | LG 71% | 88% |
| S7 (1142, 479, 414; by YA) | 62 | RL 60% | SG 35% | 2% | 63% | RL > RA 11% | 5.1 | 3.5 | 4.9 | 2.5 | 26% | 12% | RL 63% | 83% |
| S8 (976, 659, 350; by YA) | 45 | RL 58% | YA 38% | 2% | 60% | RL > RA 9% | 6.7 | 4.2 | 6.1 | 2.0 | 31% | 17% | RL 78% | 73% |
| S9 (926, -192, 478; by MH) | 74 | RL 80% | RL 70% | 80% | 80% | RL > RA 15% | 2.6 | 2.6 | 2.5 | 2.4 | 4% | 12% | RL 80% | 71% |
| S10 (967, 328, 350; by YA) | 41 | RL 59% | RL 32% | 59% | 59% | RL > MH 12% | 4.6 | 3.7 | 4.0 | 3.5 | 29% | 22% | RL 73% | 73% |
| S11 (-32, 41, 222; by RL) | 65 | LG 69% | LG 34% | 69% | 71% | LG > YA2 46% | 5.2 | 4.7 | 5.0 | 5.1 | 25% | 33% | LG 69% | 90% |
| S12 (-95, 575, 478; by YA2) | 76 | RL 78% | RL 59% | 78% | 78% | RL > RA 17% | 2.3 | 2.6 | 2.2 | 2.1 | 1% | 15% | RL 79% | 61% |
| S13 (241, 804, 478; by YA2) | 77 | RL 77% | PG 44% | 0% | 77% | RL > RA 14% | 3.8 | 3.6 | - | 3.1 | 4% | 10% | RL 81% | 71% |
| S14 (744, 1, 414; by YA) | 44 | RL 68% | RL 54% | 68% | 68% | RL > RA 20% | 7.0 | 3.0 | 3.0 | 2.7 | 34% | 24% | RL 73% | 73% |
| S15 (101, 336, 30; by GL) | 24 | LG 58% | RA 53% | 0% | 0% | LG > YA2 33% | 10.5 | 1.9 | - | 1.1 | 75% | 16% | LG 71% | 90% |
| S16 (512, -63, 30; by RA) | 35 | LG 49% | RA 58% | 0% | 0% | LG > YA2 29% | 10.9 | 1.2 | - | 1.0 | 74% | 13% | LG 51% | 88% |
| S17 (648, 488, 414; by YA) | 11 | RL 36% | RL 44% | 36% | 36% | SG > RL 9% | 11.1 | 2.9 | 11.6 | 3.0 | 73% | 15% | RL 73% | 83% |

His general lives alone (in the others his style this life, rockets, rail or lightning, names his weapon):

| spawn | his general lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | none in 10 s: he | pros |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 64 | RL 83% | PG 65% | 0% | 0% | RL > RA 16% | 7.1 | 2.8 | 14% | 12% |
| S2 | 50 | RL 68% | YA 36% | 0% | 68% | RL > RA 14% | 5.5 | 3.8 | 26% | 13% |
| S3 | 47 | RL 49% | SG 99% | 43% | 43% | SG > RL 38% | 7.5 | 0.5 | 26% | 1% |
| S4 | 57 | RL 81% | RL 43% | 81% | 89% | RL > RA 19% | 3.0 | 3.1 | 16% | 11% |
| S5 | 57 | LG 91% | LG 38% | 91% | 95% | LG > YA2 44% | 2.0 | 2.5 | 5% | 7% |
| S6 | 54 | LG 94% | LG 67% | 94% | 94% | LG > YA2 48% | 4.0 | 3.8 | 0% | 21% |
| S7 | 30 | RL 73% | SG 35% | 0% | 73% | RL > RA 20% | 4.9 | 3.5 | 17% | 12% |
| S8 | 26 | RL 69% | YA 38% | 4% | 73% | RL > MH 8% | 5.0 | 4.2 | 38% | 17% |
| S9 | 47 | RL 100% | RL 70% | 100% | 100% | RL > RA 21% | 2.5 | 2.6 | 0% | 12% |
| S10 | 22 | RL 77% | RL 32% | 77% | 77% | RL > MH 23% | 4.0 | 3.7 | 41% | 22% |
| S11 | 29 | LG 93% | LG 34% | 93% | 97% | LG > YA2 66% | 5.0 | 4.7 | 3% | 33% |
| S12 | 45 | RL 93% | RL 59% | 93% | 93% | RL > RA 18% | 2.2 | 2.6 | 2% | 15% |
| S13 | 43 | RL 88% | PG 44% | 0% | 88% | RL > RA 16% | 3.7 | 3.6 | 5% | 10% |
| S14 | 22 | RL 91% | RL 54% | 91% | 91% | RL > RA 27% | 2.9 | 3.0 | 36% | 24% |
| S15 | 14 | LG 64% | RA 53% | 0% | 0% | LG > YA2 36% | 10.4 | 1.9 | 86% | 16% |
| S16 | 16 | LG 62% | RA 58% | 0% | 0% | LG > YA2 31% | 10.9 | 1.2 | 69% | 13% |
| S17 | 7 | RL 43% | RL 44% | 43% | 43% | SG > RL 14% | 11.1 | 2.9 | 86% | 15% |

His ways beside theirs: the median seconds from a spawn to a first pickup, where he took it first in 8 lives or more and the pros in 5 or more.

| spawn | first pickup | his lives | his seconds | the pros' lives | the pros' seconds | he is slower by |
|---|---|---|---|---|---|---|
| S1 | RL | 78 | 7.0 | 12 | 7.3 | -0.3 |
| S1 | LG | 31 | 7.6 | 7 | 8.2 | -0.6 |
| S2 | RL | 61 | 5.6 | 76 | 5.2 | +0.4 |
| S2 | LG | 28 | 6.4 | 32 | 5.8 | +0.6 |
| S3 | RL | 30 | 9.8 | 0 | - | (the pros do not open so) |
| S3 | SG | 24 | 0.5 | 608 | 0.5 | +0.1 |
| S3 | LG | 13 | 9.4 | 0 | - | (the pros do not open so) |
| S4 | RL | 62 | 3.0 | 256 | 2.9 | +0.1 |
| S4 | LG | 28 | 3.6 | 98 | 3.4 | +0.2 |
| S5 | LG | 79 | 2.0 | 215 | 2.5 | -0.5 |
| S5 | RL | 35 | 3.7 | 96 | 3.5 | +0.2 |
| S6 | LG | 79 | 3.9 | 324 | 3.8 | +0.1 |
| S6 | RL | 22 | 9.2 | 0 | - | (the pros do not open so) |
| S7 | RL | 37 | 4.8 | 142 | 4.4 | +0.4 |
| S7 | LG | 13 | 10.6 | 2 | - | (the pros do not open so) |
| S8 | RL | 26 | 4.9 | 47 | 5.2 | -0.3 |
| S8 | LG | 11 | 7.3 | 17 | 6.9 | +0.4 |
| S9 | RL | 59 | 2.5 | 288 | 2.4 | +0.1 |
| S9 | LG | 14 | 8.9 | 0 | - | (the pros do not open so) |
| S10 | RL | 24 | 4.0 | 118 | 3.5 | +0.5 |
| S10 | LG | 11 | 7.2 | 13 | 8.6 | -1.5 |
| S11 | LG | 45 | 5.0 | 123 | 5.1 | -0.1 |
| S11 | RL | 16 | 10.2 | 0 | - | (the pros do not open so) |
| S12 | RL | 59 | 2.2 | 205 | 2.1 | +0.0 |
| S12 | LG | 16 | 4.0 | 29 | 4.2 | -0.2 |
| S13 | RL | 59 | 3.6 | 69 | 3.8 | -0.1 |
| S13 | LG | 16 | 4.2 | 27 | 4.7 | -0.5 |
| S14 | RL | 30 | 3.0 | 158 | 2.7 | +0.3 |
| S14 | LG | 12 | 7.4 | 2 | - | (the pros do not open so) |
| S15 | LG | 14 | 10.1 | 4 | - | (the pros do not open so) |
| S16 | LG | 17 | 10.0 | 1 | - | (the pros do not open so) |
| S16 | RL | 14 | 11.6 | 0 | - | (the pros do not open so) |

The enemy within 500 units of an armor or the mega that is one of the spawn's usual first pickups: he takes it as his first pickup 0% of the time (61 lives; 0% at the rate of his lives without the enemy there); the pros 20% (691 lives; 25% without him there).
The enemy within 500 units of an armor or the mega that is one of the spawn's usual second pickups: he takes it as his second pickup 5% of the time (605 lives; 13% at the rate of his lives without the enemy there); the pros 9% (3057 lives; 10% without him there).
His second pickup is an armor or the mega in 508 lives; in 23% of them the enemy stood within 500 units of it at the moment he took it, and in 100% of those he had seen or heard him in the three seconds before.
By the kind of life: general (630 lives): none in 10 s 18%, first pickup RL 59%, LG 28%, SG 3%; rockets (290 lives): none in 10 s 30%, first pickup RL 85%, SG 1%, LG 1%; lightning (265 lives): none in 10 s 9%, first pickup LG 95%, GL 2%, MH 0%.

### hektik

64 games of 10 minutes, 1880 lives of his (14.7 a player a game; 128 of them a game's start). The pros: 749 lives in 144 demos.

| spawn | his lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | to the pros' item, taken first: he | pros | none in 10 s: he | pros | his first intention | on his legs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 (-975, 321, 167; by RG) | 312 | RL2 48% | RG 82% | 25% | 25% | GL > LG 19% | 3.2 | 1.7 | 1.9 | 1.7 | 4% | 5% | RL 50% | 45% |
| S2 (599, 945, 262; by PG) | 334 | RL 49% | RL 93% | 49% | 49% | RL > RG 10% | 1.7 | 1.4 | 1.4 | 1.3 | 2% | 0% | RL 49% | 53% |
| S3 (-527, -519, 231; by RL2) | 236 | RL2 71% | RL2 99% | 71% | 71% | RL2 > RG 22% | 0.8 | 0.6 | 0.8 | 0.6 | 2% | 0% | RL 51% | 50% |
| S4 (-9, -543, 271; by YA) | 168 | RL2 49% | RL2 91% | 49% | 49% | RL2 > YA 16% | 3.0 | 1.3 | 1.4 | 1.3 | 5% | 3% | RL 49% | 51% |
| S5 (-615, 55, 63; by RL2) | 88 | RG 42% | YA 46% | 1% | 43% | RG > YA 12% | 3.6 | 2.0 | 1.6 | 1.7 | 9% | 6% | RG 41% | 38% |
| S6 (288, -351, -1; by MH) | 115 | LG 47% | LG 55% | 47% | 48% | LG > MH 11% | 4.2 | 2.2 | 2.3 | 2.1 | 7% | 6% | LG 43% | 40% |
| S7 (-103, 1031, 63; by RL) | 306 | RL 34% | RG 62% | 25% | 50% | PG > RL 11% | 2.6 | 2.4 | 2.2 | 2.4 | 7% | 3% | RL 46% | 49% |
| S8 (-496, 399, 263; by RG) | 186 | RL2 40% | RL2 40% | 40% | 71% | GL > LG 23% | 2.6 | 2.7 | 2.7 | 2.2 | 3% | 3% | RL 42% | 41% |
| S9 (-160, -159, -145; by SG) | 29 | SG 100% | SG 91% | 100% | 100% | SG > LG 55% | 0.3 | 0.2 | 0.3 | 0.2 | 0% | 9% | LG 55% | 47% |
| S10 (-472, 369, 63; by RG) | 106 | RG 50% | RG 89% | 50% | 50% | RG > YA 11% | 0.9 | 0.7 | 0.8 | 0.7 | 6% | 6% | RG 50% | 45% |

His general lives alone (in the others his style this life, rockets, rail or lightning, names his weapon):

| spawn | his general lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | none in 10 s: he | pros |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 76 | RL2 88% | RG 82% | 8% | 8% | RL2 > YA 24% | 3.3 | 1.7 | 4% | 5% |
| S2 | 86 | RL 99% | RL 93% | 99% | 99% | RL > RG 19% | 1.4 | 1.4 | 0% | 0% |
| S3 | 62 | RL2 95% | RL2 99% | 95% | 95% | RL2 > YA 31% | 0.8 | 0.6 | 2% | 0% |
| S4 | 34 | RL2 100% | RL2 91% | 100% | 100% | RL2 > YA 35% | 1.4 | 1.3 | 0% | 3% |
| S5 | 19 | RG 63% | YA 46% | 5% | 68% | RG > YA 16% | 1.9 | 2.0 | 0% | 6% |
| S6 | 33 | LG 79% | LG 55% | 79% | 79% | LG > MH 21% | 2.4 | 2.2 | 0% | 6% |
| S7 | 79 | RL 66% | RG 62% | 3% | 5% | PG > RL 29% | 3.4 | 2.4 | 3% | 3% |
| S8 | 47 | RL2 70% | RL2 40% | 70% | 94% | RL2 > RG 17% | 2.8 | 2.7 | 4% | 3% |
| S9 | 11 | SG 100% | SG 91% | 100% | 100% | SG > LG 82% | 0.3 | 0.2 | 0% | 9% |
| S10 | 26 | RG 65% | RG 89% | 65% | 65% | RG > MH 15% | 0.8 | 0.7 | 0% | 6% |

His ways beside theirs: the median seconds from a spawn to a first pickup, where he took it first in 8 lives or more and the pros in 5 or more.

| spawn | first pickup | his lives | his seconds | the pros' lives | the pros' seconds | he is slower by |
|---|---|---|---|---|---|---|
| S1 | RL2 | 151 | 3.4 | 10 | 2.9 | +0.5 |
| S1 | RG | 79 | 1.9 | 107 | 1.7 | +0.2 |
| S1 | GL | 64 | 3.2 | 1 | - | (the pros do not open so) |
| S1 | LG | 10 | 6.6 | 0 | - | (the pros do not open so) |
| S2 | RL | 162 | 1.4 | 95 | 1.3 | +0.1 |
| S2 | LG | 83 | 2.8 | 1 | - | (the pros do not open so) |
| S2 | RG | 76 | 3.5 | 2 | - | (the pros do not open so) |
| S3 | RL2 | 167 | 0.8 | 87 | 0.6 | +0.1 |
| S3 | GL | 28 | 2.8 | 0 | - | (the pros do not open so) |
| S3 | RG | 18 | 3.8 | 0 | - | (the pros do not open so) |
| S3 | LG | 17 | 6.5 | 0 | - | (the pros do not open so) |
| S4 | RL2 | 83 | 1.4 | 79 | 1.3 | +0.1 |
| S4 | RG | 39 | 3.5 | 2 | - | (the pros do not open so) |
| S4 | LG | 39 | 3.9 | 0 | - | (the pros do not open so) |
| S5 | RG | 37 | 1.9 | 38 | 2.3 | -0.5 |
| S5 | RL2 | 20 | 5.0 | 5 | 3.4 | +1.6 |
| S5 | LG | 20 | 4.0 | 1 | - | (the pros do not open so) |
| S6 | LG | 54 | 2.3 | 47 | 2.1 | +0.1 |
| S6 | RL2 | 33 | 5.0 | 8 | 4.0 | +0.9 |
| S6 | RG | 22 | 5.6 | 8 | 4.7 | +0.9 |
| S7 | RL | 103 | 2.5 | 2 | - | (the pros do not open so) |
| S7 | LG | 76 | 3.1 | 9 | 2.9 | +0.3 |
| S7 | RG | 76 | 2.2 | 48 | 2.4 | -0.1 |
| S7 | PG | 35 | 4.2 | 0 | - | (the pros do not open so) |
| S8 | RL2 | 75 | 2.7 | 12 | 2.2 | +0.5 |
| S8 | RG | 57 | 2.9 | 7 | 3.4 | -0.6 |
| S8 | GL | 48 | 2.3 | 3 | - | (the pros do not open so) |
| S9 | SG | 29 | 0.3 | 20 | 0.2 | +0.1 |
| S10 | RG | 53 | 0.8 | 16 | 0.7 | +0.1 |
| S10 | LG | 33 | 2.6 | 0 | - | (the pros do not open so) |

The enemy within 500 units of an armor or the mega that is one of the spawn's usual first pickups: he takes it as his first pickup 0% of the time (48 lives; 1% at the rate of his lives without the enemy there); the pros 24% (37 lives; 22% without him there).
The enemy within 500 units of an armor or the mega that is one of the spawn's usual second pickups: he takes it as his second pickup 6% of the time (982 lives; 12% at the rate of his lives without the enemy there); the pros 8% (268 lives; 11% without him there).
His second pickup is an armor or the mega in 626 lives; in 41% of them the enemy stood within 500 units of it at the moment he took it, and in 100% of those he had seen or heard him in the three seconds before.
By the kind of life: lightning (497 lives): none in 10 s 9%, first pickup LG 58%, GL 28%, RL 4%; general (473 lives): none in 10 s 2%, first pickup RL 72%, RG 10%, LG 8%; rail (455 lives): none in 10 s 2%, first pickup RG 89%, RL 7%, SG 1%; rockets (455 lives): none in 10 s 4%, first pickup RL 91%, PG 3%, SG 1%.

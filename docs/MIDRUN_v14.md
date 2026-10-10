# `duel_gru_v14`: mid-run report (2026-10-10, data to 06:39, seven and a half hours into the second start)

The run of [MANIFEST_v14.md](MANIFEST_v14.md). First start 2026-10-09 20:14, stopped at 22:52 and kept as
`duel_gru_v14_try1` (it went wrong, see below); second start 22:53 from the same starting network,
still training (it ends itself at 19:00). Numbers are the mean of ten updates; the duels are 32 ten-minute games a map from a save, against the Nightmare
stand-in every 45 minutes and, since this morning, against v13 itself. "Start" and "v13" are the starting network (v13
with v14's ten new inputs) under v14's settings. The night's log: [RESULTS.md](RESULTS.md), 2026-10-09 23:15 to
2026-10-10 06:30.

## In short

- **To be told at once: as a duelist v14 is weaker than v13, by a wide margin.** Head to head he takes 36% of
  the frags from v13 on the six maps and wins 41 games of 192. He loses on the three maps v13 knows (Blood Run
  33%, Aerowalk 14% and not one game, Lost World 26%) and holds his own on two it never trained on (Furious Heights
  57%, Battleforged 48%). Against the stand-in he went from 70% of the frags to 59%. Training did not show it: all
  night he took 53% of the frags from his own last eight snapshots. It happened in the first three hours; the save
  of 02:05 loses to v13 exactly as the save of 03:59 does.
- **Two causes, both in how this run is set up; neither is his aim or his movement.**
  1. *The weapon in his hand.* The same v14 network with v13's network pressing only the weapon key takes 72% from the
     stand-in (v13: 70%); v13 with v14 on that key 51%. v14 holds the weapons as the weapon teacher says (the pros'
     table, and in three lives of four the style's weapon at every distance); v13, whose teacher was gone after four
     hours, fights with the rail at any distance, point-blank too, and that wins in the simulator (its rail hits 57%
     within 400 units, however fast the target crosses his view).
  2. *The league.* His old selves are the last eight snapshots, two hours and forty minutes of himself. v13 was out of
     it by 01:35. Since then he has met only players who hold their weapons as he does. With v13's weapon key he
     still loses to v13 (45% of the frags on Blood Run, 25% on Aerowalk, where v13 keeps him off the items).
- **Rockets: yes.** 35% of his frags in training (27% at the start), 39% against the stand-in (17%). **Shotgun,
  grenades, plasma: no.** In his hand 0.0% of the time all night.
- **Strafe jumping: half of the lesson, almost only where it is taught.** In item runs he is fast in the air 18% of the
  time (9% at the start; the teacher 18 to 31% by map) at 313 units a second (298). In his games time fast in the air
  rose by 3 to 5 points. On a real server he moves as v13 did.
- **Against the stand-in the rest of him is better than v13**: with v13's weapon key he beats v13's own result on
  Furious Heights (58% against 42%) and Battleforged (82% against 62%).
- **Aim**: the lightning gun lost 4 points against the stand-in (50% -> 46%); rail and rockets hold.
- **Items did not collapse**: megas 0.59 -> 0.65 and red armors 0.58 -> 0.64 a player-minute.
- **The first try failed, by my setup**, and cost two hours and forty minutes (below).
- **My recommendation**, yours to decide: one restart with two changes, both built and checked in a copy and neither
  in the run: v13 kept in the league as a standing opponent, and the style's weapon only inside its own distances.
  Then train to about 11:00 and judge by the duel against v13, which is now part of every check. As he stands I
  would not put v14 on your server in v13's place.

## Where the run stands

| | |
|---|---|
| From | v13's final network, widened from 499 to 509 inputs (his speed, the way he moves against his view, speed gained in 100 ms; six for the lead of a rocket or a plasma ball) |
| Trained | second start 2026-10-09 22:53, 455 minutes of training by 06:39, about 713 million player-frames (5,000 hours of play) at 26,000 frames a second |
| Maps, groups | Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged; duels three matches in five, groups of three and four one in five each; Campgrounds, Hektik, Toxicity, Cure never trained on |
| Rounds | normal games 70% (a quarter of them against the scripted item runner), item runs 30% (half of them end in a fight) |
| League | a quarter of the players are a frozen snapshot of himself: a new one every 20 minutes, the last eight kept |
| New in v14 | the simulator set right against the game's maps (lava, the game's movement, the pros' ways); rockets at a fifth of a shot's price, grenades and plasma free; the weapon teacher silent on shotgun, grenades, plasma; pay for speed on his way; the strafe-jumping teacher in item runs; no key labels in games; the rule for rockets with no enemy in view |
| Teachers | strafe-jumping network on keys, jump and view in item runs, into the shared layers (weight 0.3; 0.5 from 02:50 to 04:48); weapon teacher 0.2 to the end; the item rule on the intention 2.0 |
| Changed in the run | 01:18 the strafe-jumping teacher held at 0.3 (it was set to fade); 02:50 its weight 0.5 and the pay for speed in games 0.1 -> 0.3; 04:48 its weight back to 0.3. Each right after a save, the save kept |
| Learning rate, step | 1e-4; the policy moves 0.010 an update |

## Self-play, every two hours

| | start | 2 h | 4 h | 6 h | now (7.6 h) |
|---|---|---|---|---|---|
| the teacher's weight | 0.06 | 0.23 | 0.46 | 0.30 | 0.30 |
| the teacher's loss | 4.64 | 2.03 | 1.84 | 1.63 | 1.72 |
| hit rate: lightning | 45% | 44% | 44% | 44% | 44% |
| hit rate: rail | 48% | 46% | 46% | 47% | 46% |
| hit rate: rockets | 45% | 45% | 44% | 44% | 45% |
| on target, enemy in view | 33% | 33% | 32% | 32% | 32% |
| frags against old selves | 49% | 51% | 52% | 53% | 54% |
| frags by rockets | 27% | 32% | 34% | 34% | 35% |
| rockets in hand | 26% | 30% | 30% | 32% | 32% |
| shotgun in hand | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| grenades in hand | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| plasma in hand | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| blind rockets a player-minute | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| item runs: units a second | 298 | 304 | 309 | 311 | 315 |
| item runs: fast in the air | 9% | 15% | 17% | 18% | 18% |
| item runs: items a minute | 6.5 | 5.2 | 5.4 | 5.8 | 6.1 |
| key actions asked a second | 6.0 | 6.4 | 6.4 | 6.3 | 6.2 |
| key actions refused | 58% | 64% | 63% | 63% | 63% |
| the view's jerk | 3.8 | 4.5 | 4.8 | 4.3 | 4.0 |
| megas a player-minute | 0.59 | 0.64 | 0.68 | 0.61 | 0.66 |
| red armors a player-minute | 0.58 | 0.60 | 0.62 | 0.65 | 0.66 |
| time without a big weapon | 18% | 18% | 21% | 17% | 17% |
| frags a match-minute | 2.71 | 2.61 | 2.40 | 2.50 | 2.55 |
| damage dealt from above | 14% | 14% | 14% | 15% | 15% |
| damage dealt from below | 13% | 13% | 13% | 13% | 13% |
| lava damage a player-minute | 7.4 | 8.9 | 8.3 | 7.7 | 7.7 |
| the policy's step an update | 0.049 | 0.009 | 0.011 | 0.010 | 0.010 |

Items a minute in item runs fell from 6.5 to 4.2 in the first quarter of an hour under the new teacher and have come
back to about 6: he runs faster there and still reaches fewer items than the starting network did.

## The duels

**Against the Nightmare stand-in** (a script with the game bot's weapons and aim; the same seeds every time, so two
checks of one network give the same numbers). His share of the frags, games won and lost of 32.

| Map | start (18:01) | 47 min in (00:18) | 91 min in (01:08) | 142 min in (01:52) | 182 min in (02:36) | 228 min in (03:19) | 267 min in (04:03) | 311 min in (04:51) | 404 min in (06:24) |
|---|---|---|---|---|---|---|---|---|---|
| Blood Run | 71% (32-0) | 44% (8-18) | 47% (11-17) | 50% (15-12) | 46% (12-16) | 51% (15-13) | 50% (14-13) | 44% (9-18) | 52% (16-14) |
| Aerowalk | 80% (32-0) | 52% (16-11) | 52% (15-11) | 53% (20-9) | 54% (15-13) | 53% (19-10) | 53% (20-7) | 58% (25-4) | 58% (23-5) |
| Lost World | 90% (32-0) | 67% (31-0) | 75% (31-0) | 71% (30-2) | 65% (29-2) | 70% (29-2) | 70% (30-1) | 76% (31-0) | 72% (31-0) |
| Sinister | 74% (32-0) | 54% (18-11) | 56% (19-7) | 60% (25-5) | 56% (20-8) | 58% (22-5) | 57% (22-5) | 63% (26-3) | 62% (26-5) |
| Furious Heights | 42% (8-20) | 41% (7-18) | 45% (10-19) | 44% (8-19) | 41% (9-21) | 40% (6-22) | 40% (4-27) | 45% (13-18) | 44% (9-21) |
| Battleforged | 62% (24-6) | 47% (13-16) | 59% (19-8) | 55% (18-13) | 60% (20-10) | 55% (19-9) | 57% (20-9) | 63% (22-5) | 65% (25-5) |
| Campgrounds* | 35% (9-21) | 44% (7-23) | 48% (12-17) | 52% (14-18) | 46% (13-17) | 44% (6-23) | 45% (7-21) | 48% (17-14) | 45% (9-18) |
| Hektik* | 51% (16-14) | 35% (2-30) | 35% (0-30) | 33% (2-29) | 37% (1-29) | 33% (0-32) | 32% (1-30) | 33% (1-31) | 35% (1-29) |
| Toxicity* | 64% (17-9) | 65% (24-6) | 66% (24-8) | 65% (17-11) | 64% (19-11) | 65% (15-16) | 63% (21-8) | 62% (16-13) | 63% (17-12) |
| Cure* | 47% (16-13) | 42% (18-9) | 43% (17-14) | 41% (10-14) | 40% (17-11) | 39% (10-19) | 40% (14-15) | 43% (18-9) | 42% (17-10) |
| the six trained | 69.7% | 50.9% | 55.7% | 55.5% | 53.7% | 54.4% | 54.7% | 58.2% | 58.9% |
| the four held out (*) | 49.2% | 46.7% | 48.1% | 47.5% | 46.5% | 45.3% | 44.9% | 46.4% | 46.1% |

It fell to 51% within the first 47 minutes and has moved between 54% and 59% since.

**One output costs these duels.** The same check played by two networks at once: one decides everything, the other only
presses the weapon key (each sees the same inputs and keeps its own memory). v14 is the save of 03:59, the last column
above.

| Map | v13 | v14 | v14, v13 on the weapon key | v13, v14 on the weapon key |
|---|---|---|---|---|
| Blood Run | 71% (32-0) | 44% (9-18) | 68% (29-1) | 55% (25-6) |
| Aerowalk | 80% (32-0) | 58% (25-4) | 64% (29-3) | 63% (30-1) |
| Lost World | 90% (32-0) | 76% (31-0) | 82% (32-0) | 79% (31-1) |
| Sinister | 74% (32-0) | 63% (26-3) | 75% (32-0) | 55% (17-10) |
| Furious Heights | 42% (8-20) | 45% (13-18) | 58% (22-9) | 27% (4-26) |
| Battleforged | 62% (24-6) | 63% (22-5) | 82% (30-2) | 26% (2-29) |
| the six maps | 69.7% | 58.2% | 71.6% | 50.9% |

v14's weapon key costs 13 points with his own body and 19 with v13's. With v13's key his frags are by rockets 23% (v13
17%, v14 39%), he deals 2,470 damage a game (v13 2,600, v14 2,080) and takes 2,150 (2,230; 2,380).

**The styles are not the whole of it.** With no playing style given (every life "general") v13 takes 70.5% on the six
maps and v14 56.7%:

| Map | v13 | v14 |
|---|---|---|
| Blood Run | 66% (28-3) | 51% (13-11) |
| Aerowalk | 83% (32-0) | 54% (19-10) |
| Lost World | 93% (32-0) | 64% (29-3) |
| Sinister | 76% (32-0) | 64% (26-3) |
| Furious Heights | 42% (9-22) | 46% (10-16) |
| Battleforged | 63% (26-4) | 61% (22-6) |

**Head to head against v13** (32 ten-minute duels a map, both with playing styles as in training; v13 against itself
on Aerowalk, to check the method: 49% of the frags, 14 games to 18).

| Map | v14 (03:59) | Games won, lost | v14 with v13 on the weapon key | v14 at 02:05 |
|---|---|---|---|---|
| Blood Run | 33% | 2, 29 | 45% (9-21) | 34% (2-29) |
| Aerowalk | 14% | 0, 32 | 25% (0-32) | 13% (0-32) |
| Lost World | 26% | 0, 30 | not played | not played |
| Sinister | 41% | 7, 20 | not played | not played |
| Furious Heights | 57% | 20, 9 | not played | not played |
| Battleforged | 48% | 12, 17 | not played | not played |
| the six maps | 36% | 41, 137 | | |

He loses on the three maps v13 trained on and on Sinister, holds his own on Battleforged and wins on Furious
Heights, two maps v13 never saw. On Aerowalk v13 keeps him off the items: v14 holds 150 or more 8% of the time, v13
77%; megas 13% against 60%. He dies by his own hand or the map more often than v13 (Blood Run 1.2 times a game against
0.5). The save of 02:05 does what the save of 03:59 does: the ground was lost in the first three hours, not since. And
the weapon key is half of it at most: with v13 on that key he comes from 33% to 45% on Blood Run and from 14% to 25% on
Aerowalk. The check loop now plays every save against v13 on these two maps; the save of
05:48: Blood Run 34% (3-28), Aerowalk 15% (0-32).

## The weapon in his hand

Which of the three big weapons he holds when he owns all three with ammunition and the enemy is in view, against the
stand-in, by the style of his life and the distance. Each cell: rockets, rail, lightning.

| Blood Run | under 400 units | 400 to 700 | over 700 |
|---|---|---|---|
| v13, general life | 2%, 70%, 28% | 3%, 79%, 17% | 16%, 54%, 30% |
| v13, rockets life | 38%, 21%, 41% | 22%, 47%, 31% | 10%, 69%, 21% |
| v13, lightning life | 0%, 100%, 0% | 0%, 66%, 34% | 0%, 85%, 15% |
| v14, general life | 37%, 30%, 31% | 31%, 45%, 24% | 11%, 43%, 46% |
| v14, rockets life | 58%, 12%, 29% | 56%, 20%, 17% | 39%, 20%, 41% |
| v14, rail life | 33%, 51%, 15% | 33%, 53%, 12% | 0%, 71%, 0% |
| v14, lightning life | 25%, 17%, 51% | 24%, 14%, 62% | 24%, 41%, 35% |
| the weapon teacher, general life | 91%, 0%, 9% | 2%, 4%, 94% | 6%, 71%, 22% |
| the weapon teacher, a styled life | the style's weapon | the style's weapon | the style's weapon |

On Aerowalk the same: v13 holds the rail 49 to 89% of the time in every style at every distance and rockets never; v14
holds rockets 66%, 50%, 26% in a rockets life and the lightning gun 60%, 60%, 75% in a lightning life.

- **v13 is a rail player who ignores his styles**: the rail in hand at point-blank range seven times in ten. That wins
  in the simulator, against the script and against v14, and it is the play the owner did not want ("13 rockets against
  my 155").
- **v14 does what the weapon teacher says, about six times in ten.** In a general life that is the pros' table: rockets
  under 400 units, lightning from 400 to 700, rail beyond. In a styled life it is the style's weapon at every
  distance: the owner's design of 2026-10-08 ("some people do genuinely have a preference for weapons"), made for a
  teacher that was gone after four hours. Kept to the end of a run it makes three one-weapon players: rockets beyond
  700 units a quarter to four tenths of the time, the lightning gun beyond its reach. The servers draw a style for each life in the
  same way.
- Rockets at a fifth of the price at every distance add to it.

**A correction.** At 01:30 I wrote that in the pros' table the rocket launcher is the weapon in hand at most distances.
It is not: over all maps rockets lead under 400 units (53% to 46%), lightning from 400 to 700, the rail beyond (45% at
700, 65% at 800, 87 to 95% from 1,000). And I put the lost duels down to rockets far off alone; the tables above are
the fuller answer.

**v13's rail, measured** (against the stand-in, 12 eight-minute games a map; a hit is 60 points off the enemy or a
frag in that frame or the next):

| | Under 200 units | 200 to 400 | 400 to 700 | 700 to 1,000 | The enemy crossing his view at under 30 degrees a second | 30 to 90 | 90 to 180 |
|---|---|---|---|---|---|---|---|
| Aerowalk: share of his rail shots | 22% | 43% | 28% | 6% | 40% | 42% | 14% |
| Aerowalk: hit | 57% | 57% | 48% | 41% | 48% | 58% | 57% |
| Blood Run: share of his rail shots | 21% | 29% | 40% | 8% | 52% | 34% | 8% |
| Blood Run: hit | 57% | 53% | 44% | 33% | 46% | 50% | 56% |

Half to two thirds of v13's rail shots are fired within 400 units and more than half of those hit; and the rail does
not get harder for him when the target crosses his view faster. v14 hits the same with it (61% and 49% under 400 units
on Aerowalk) and fires it a third as often.

**What the simulator cannot say**: whether the pros' way with the weapons is weaker play, or whether rail at every
distance wins here only because that rail is better up close than a hand's. The owner knows what a rail does at
point-blank range in a person's hand; if it is not 57% on a target crossing at 90 degrees a second, the aim limits do
not bite on a flick, and the project's own method ("tighten the human limits until the right play appears") says where
to look (B-199). Real games will say the rest: the game's Nightmare bot after the run, and people.

## Strafe jumping

The network itself in item runs, map by map (64 player-minutes a map), beside a player who presses only the teacher's
labels. Each cell: units a second, time fast in the air, items reached a minute.

| Map | The start network | The save of 02:05 | The save of 04:48 | The teacher's labels alone |
|---|---|---|---|---|
| Blood Run | 316, 12%, 8.3 | 336, 24%, 5.7 | 339, 25%, 6.7 | 359, 31%, 8.2 |
| Aerowalk | 264, 5%, 4.4 | 267, 16%, 4.3 | 269, 17%, 4.5 | (it labels 36% of his frames there) |
| Lost World | 306, 7%, 7.2 | 306, 13%, 5.4 | 311, 15%, 5.9 | 328, 20%, 7.0 |
| Sinister | 260, 5%, 4.7 | 304, 12%, 7.1 | 315, 15%, 7.6 | 320, 18%, 8.6 |
| Furious Heights | 285, 11%, 3.9 | 313, 21%, 4.1 | 317, 22%, 5.0 | 339, 28%, 6.1 |
| Battleforged | 308, 8%, 9.3 | 334, 16%, 7.9 | 338, 19%, 8.0 | 352, 23%, 9.1 |

- **Most of it came in the first three hours; since then it creeps.** How far his choices are from the teacher's on
  the frames it labels: 20 nats at the start, 2.0 at 02:05, 1.85 at 04:48; the teacher's own spread, under which no
  pupil of sampled labels can get, is 1.0. Of the 0.85 left the view is 0.45 and the side keys 0.25. His first choice
  is the teacher's for forward 93% of the time, side 86%, jump 98%, the view 59%.
- **He is faster and misses more**: on Blood Run, Lost World and Battleforged he still reaches fewer items a minute
  than the starting network did.
- **Two faults of the teacher itself**: on Lost World it runs through lava and he has taken that over (lava damage in
  item runs 18 -> 38 a player-minute; the teacher's labels alone 43); on Aerowalk it has no way in its own walking map
  for most goals and labels a third of his frames.
- **In his games** (the frames where he is on his way to the item he chose with nobody seen or heard for 1.5 s: 40 to
  60% of his time; the teacher never labels these). Each cell: units a second, time fast in the air.

| Map | The start network | The save of 02:05 | The save of 04:48 | In item runs, 04:48 |
|---|---|---|---|---|
| Blood Run | 300, 9.7% | 307, 12.6% | 308, 13.7% | 339, 25% |
| Sinister | 283, 7.7% | 288, 9.1% | 292, 11.1% | 315, 15% |
| Battleforged | 296, 5.8% | 310, 10.6% | 309, 11.1% | 338, 19% |

  His choices there are 6 to 7 nats from the teacher's (21 at the start; 1.85 where it labels him).
- **On a real server** (a private one, two v14 Bobbys against each other on Blood Run, 03:35): 292 units a second, 298
  with nobody about, fast in the air 12% of the time. v13 in the night's two public Blood Run sessions: 294 and 299,
  290 and 293, 11%. Someone playing him today would not see strafe jumping.
- **What was tried in the run** (both settings were left to me): the teacher's weight held at 0.3 instead of fading
  (01:18), then 0.5 for two hours (02:50 to 04:48): in the trainer's numbers no faster learning, map by map he kept
  gaining slowly; back to 0.3. The pay for speed in games tripled to 0.3 (02:50): it comes to 0.11 a player-minute
  now; his speed on a trip in games stays at 291, the share of that time over 320 went from 42% to 44%.

## The other things asked for or watched

- **Shotgun, grenades, plasma**: 0.0% in hand from the first update to the last, with the teacher silent on them and
  grenades and plasma free. Nothing draws him to them. As the owner said: after v14.
- **Aim**: against the stand-in lightning 49.9% -> 45.9% (46.7% with v13 pressing the weapon key, so it is his aim or
  how he moves in a fight, not which fights he picks); rail 40.3% -> 40.0%, rockets 50.1% -> 50.9%, machine gun 41.8%
  -> 39.6%. In self-play lightning 44% -> 44%, rail 48% -> 47%, on target 33% -> 32%.
- **Who stands higher** (monitor only): damage dealt from above 14%, from below 13%, all night. Against the stand-in he
  is the lower one 28% of the time and the higher one 44% (31% and 43% at the start).
- **An empty weapon in his hand** (the owner's and a visitor's note, B-192): against the stand-in 4% of his time at
  00:18, 7% at 03:59; 10% on Blood Run, Lost World and Furious Heights.
- **Dying by his own hand or the map**: 0.19 a game at the start, 0.4 now (rockets at his feet, lava).
- **Items**: megas 0.65 and red armors 0.64 a player-minute in training; against the stand-in he takes 23% of the red
  armors (17% at the start) and 44% of the megas (46%), and holds 150 or more 59% of his time (64%).

## What went wrong in the night

- **The first try (20:14 to 22:52), my setup.** Every teacher was held back from the shared layers, a rule made for
  the walking teacher. The strafe-jumping teacher's labels for the view then reached only the output layer, which
  every situation shares: his view bent in fights too. In 90 minutes: hit rates down by a third, Blood Run 32-0 ->
  0-32 against the stand-in, no strafe jumping learned. My dry runs before the start were 10 to 25 minutes; the damage
  came with the teacher's weight, after half an hour. The duel check that would have shown it at 45 minutes had died
  at its start without a word. Stopped, kept, restarted from the clean start with the movement teacher let into the
  shared layers; the check loop is now looked at every hour.
- **The control was not in the checks.** I measured him against the stand-in and against his own snapshots, and took
  "53% against his old selves" for health. The duel against v13 itself was played at 05:17 for the first time.
- **Three statements of mine that were wrong and are set right**: items a minute in item runs "up from 4.9" (the
  start was 6.5: he is still under it); "none of the item-run skill shows in his games" (a quarter to a half does);
  the pros' weapon table (above).
- **Two hours at a teacher weight of 0.5** bought nothing that 0.3 would not have.

## Around the run

- **v14's ten new inputs on a real server**: set beside the simulator's (12,000 frames from the private server): the
  same. Nothing in the plugin stands in the way of v14 on the public server.
- **Warmup**: with no game on, every player holds every weapon with full ammunition, a state he has never trained in
  (B-196). On the public server 6 of 149 counted frags so far.
- **The scripted opponents** (holder, watcher, lobber: [SCOPE_v15.md](SCOPE_v15.md) A1) are built in a copy of the
  simulator and measured against v13 (RESULTS 01:30): he takes 51% of the frags from the holder, 59% from the watcher,
  65% from the lobber, 70% from the stand-in. They go into the simulator after v14.
- **The leaderboard** (public server, v13, since 19:50): 149 counted frags with three people; Bobby made 19 and took
  130 (13%); his rating 1157, theirs 1749, 1525 and 1519. A third player came at 02:10 for half an hour on Aerowalk:
  79 frags to 12.
- **Waiting for a restart of the public server on the owner's word**: the bots' four names, bodies and voices.
- The duel checks were stopped from 05:02 to 05:49 to free the processors for the tests above, and the trainer
  ran a fifth slower while they played.

## Your decisions

**1. The league.** `--anchor-p 0.25`: in a quarter of the rollouts the league's players are v13 (the starting network,
kept as `snapshots/anchor_v13.pt`) and not one of his last eight snapshots; his share of the frags against it is
logged by itself. A small change to the trainer, built in a copy; with it off nothing changes. He then has to hold
his own against the rail player for the rest of the run, with the weapons he is taught or by finding out where they do
not work. **I recommend it.**

**2. The weapon in his hand.** The styles are your design and the rocket numbers yours.

| | What it does | What to expect |
|---|---|---|
| a | Leave it | A one-weapon player in three lives of four, rockets and the lightning gun at any distance |
| b | `STYLE_RANGE=1`: in a styled life the style's weapon is the teacher's label only inside its own distances (rockets 60 to 300 units, rail from 500, lightning 150 to 700); elsewhere the pros' first choice, as in a general life | The oddest of it gone within the hour (the weapon in his hand moved within 47 minutes when the run began). Against the stand-in little: he loses as much in general lives |
| c | b, and the low rocket price only with the enemy within 500 units (`SHOT_NEAR=rl:500`) | Fewer rockets far off in general lives too |
| d | The weapon teacher off, as in v13 | He goes back to the rail at every distance: the strongest in the simulator, and the bot play you did not want |

Both switches are built in a copy of the simulator, and with them off that copy repeats the run's fixed games exactly.
**I recommend b**, in the same restart as 1 (your rule: batch the changes, restart once). It takes away what no player
would do and leaves what you asked for. It will not bring the points back by itself.

**3. Strafe jumping.** It is half-learned where it is taught, and the teacher never speaks in his games.

| | What it does | Risk |
|---|---|---|
| a | Leave it as it is | Slow gains in item runs; little in games |
| b | The strafe-jumping teacher on his quiet trips in games too (nobody seen or heard for 1.5 s), at low weight | On 2026-10-08 a teacher of the view in games all but stopped his shooting within an hour (fire 31% -> 7% of frames). It needs a trial on a copy first, which needs the graphics card: an hour of the run |
| c | Take it out of v14 and make it v15's first phase: movement rounds of their own, the teacher's faults mended (lava on Lost World, Aerowalk), labels by its best choice and not a sample | Nothing in v14 |

**I recommend a for this morning**, and the choice between b and c after you have played him.

**4. Noon.** With 1 and 2b at 7:00: about three and a half hours of training, the run stopped at about 10:45, real
games against the game's Nightmare bot on a free PC, and the numbers against v13 and the stand-in in front of you
before anything goes on the public server. If you want to play v14 as he is, to see the rockets with your own eyes,
that takes a quarter of an hour on your word: he will be weaker than what is there now.

**5. Stopping early.** Your rule (three duel checks without progress and flat measures otherwise) was met by the duel
checks at 04:03. I did not stop: the other measures were not flat, the check of 04:51 was the best since the start, and
against v13 the save of 03:59 stands where the save of 02:05 stood, so the hours since have cost nothing. The run is
going; it can be stopped or changed at the next save on your word.

## What to try next

1. The control in the league and in every check (1 above): "promote only if it beats the control" needs the control
   in the loop, not only at a run's end.
2. Why the rail at point-blank range wins in the simulator: his rail hits 53 to 57% within 400 units, whatever the
   target's speed across his view; the pros' numbers beside it, and the aim limits tightened where no hand does that. If rail at any distance stops being the best play, the
   weapons sort themselves and no teacher has to hold them in place.
3. The style's weapon inside its own distances (2b).
4. Strafe jumping as its own phase (3c), with this night's measurements: where the teacher is silent, where it is
   wrong, and how far a pupil of sampled labels gets (half the way).
5. The grenade launcher and the plasma gun: no price and no silence of a teacher has put them in his hand; they need
   rounds of their own, or the opponents that make them pay (the lobber).
6. The scripted opponents into the simulator, and the slower deciding head ([SCOPE_v15.md](SCOPE_v15.md)).
7. An empty weapon in his hand 7 to 10% of the time (B-192), and the warmup's full weapon set (B-196).
8. The stand-in beside the game's own Nightmare bot once more after this run: if real games do not punish rockets
   the way the script does, the script needs mending, not he.

## Heat maps and videos

None this time: the processors went to the tests above. They come with the full report.

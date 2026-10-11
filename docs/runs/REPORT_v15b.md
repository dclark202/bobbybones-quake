# `duel_gru_v15b`, the legs run: the report (2026-10-11 07:00)

**Which run is which.** v14's end (the save of 10:57 on 2026-10-10) is on the public server and is the control here.
v15's first start (`duel_gru_v15`, the teacher's lesson) was stopped on the evening of 2026-10-10. **v15b is the run of
this report**: v14's end with the movement network built into him as his legs, 22:01 to 07:00
([MANIFEST_v15b.md](MANIFEST_v15b.md)). The day's logs: [2026-10-10](../results/2026-10-10.md),
[2026-10-11](../results/2026-10-11.md).

## 1. In short

- **He strafe jumps now, on his legs.** Travelling in games his hops gain speed (328, 377, 373 at the first three; v14's
  end 279, 249, 221; the pros 366, 421, 422), 67% of his hops gain speed (v14's end 45%, the pros 70%), and he is at
  400 or more 9.2% of his travelling time (v14's end 1.3%, the pros 17.5%). Where his legs stay on for three seconds
  or more he reaches 440 to 510 units a second.
- **It did not cost him his duels, and the night made him better at them.** Against v14's end he rose from 49% of the
  frags at the start to 56 to 57% in the last three checks (89 to 92 games won of 144, 43 to 48 lost); against the
  stand-in he is at 80 to 82% (v14's end: 79%). The teacher's lesson had
  taken him to 13 to 42% within 40 minutes.
- **He is half way to the pros' speed, and the night's training did not close that gap.** It made him a better duelist
  with his legs, not a faster traveller: his time at speed stayed at 8 to 9% and the switch is still close to the rule it
  started as. Most of his stretches on his legs last under a second,
  and a quarter to a half of his time without an enemy in view he moves himself, slowly.
- **Not in this run**: rockets, plasma and grenades (the weapon changes wait), and the real game: the server plugins
  cannot run his legs yet (B-213), so there are no Nightmare games and nothing for the public server from this run.

## 2. Speed and strafe jumping (the owner's first priority)

How his speed is built and kept while he travels in games against the stand-in (`tools/speed_profile.py`: no enemy in
view; six ten-minute games a map on Blood Run, Aerowalk, Lost World):

| Travelling in games against the stand-in | Standing, slow, running, fast, very fast | Take-offs a minute | Speed at hop 1, 2, 3 | Hops that gained speed | Time at 400 or more |
|---|---|---|---|---|---|
| The pros (787 player-minutes) | 6, 20, 40, 20, 14% | 19.9 | 366, 421, 422 | 70% | 17.5% |
| v14's end | 2, 17, 69, 11, 0% | 18.8 | 279, 249, 221 | 45% | 1.3% |
| v15b, the start | 2, 17, 57, 18, 5% | 18.4 | 305, 323, 277 | 57% | 7.5% |
| v15b, 71 min | 2, 15, 56, 20, 6% | 17.0 | 317, 346, 320 | 64% | 8.4% |
| v15b, 103 min | 2, 16, 56, 20, 6% | 17.2 | 314, 341, 297 | 60% | 8.4% |
| v15b, 137 min | 2, 15, 57, 20, 6% | 16.5 | 319, 357, 340 | 65% | 8.5% |
| v15b, 201 min | 2, 15, 57, 20, 6% | 16.3 | 323, 350, 321 | 59% | 8.4% |
| v15b, 233 min | 2, 15, 57, 20, 6% | 16.2 | 323, 355, 316 | 64% | 8.4% |
| v15b, 275 min | 2, 15, 57, 20, 6% | 16.2 | 323, 359, 340 | 64% | 8.8% |
| v15b, 307 min | 2, 14, 57, 20, 7% | 16.9 | 323, 360, 320 | 64% | 9.2% |
| v15b, 371 min | 2, 14, 57, 20, 6% | 16.0 | 322, 374, 332 | 64% | 8.7% |
| v15b, 403 min | 2, 14, 58, 19, 6% | 14.8 | 324, 370, 345 | 68% | 8.3% |
| v15b, 434 min | 2, 13, 58, 20, 7% | 15.5 | 328, 377, 373 | 67% | 9.2% |

His legs in a duel against v14's end, the save of 390 minutes (`legs_stretches.py`, eight five-minute duels a map):

| | Blood Run | Aerowalk | Lost World | Furious Heights |
|---|---|---|---|---|
| His time: on his legs / moving himself with an enemy in view / moving himself with none | 59 / 17 / 24% | 26 / 19 / 55% | 63 / 11 / 25% | 73 / 10 / 17% |
| His speed in the three | 329 / 303 / 274 | 311 / 289 / 281 | 312 / 291 / 277 | 327 / 300 / 270 |
| Time at 400 or more while on his legs | 20% | 12% | 15% | 21% |
| Stretches on his legs a minute; their middle length | 20; 0.4 s | 19; 0.3 s | 22; 0.3 s | 13; 0.6 s |
| Stretches under a second: share of the stretches, of his legs' time | 62%, 9% | 76%, 25% | 67%, 10% | 56%, 5% |
| Stretches over six seconds: share of his legs' time, top speed | 48%, 501 | 8%, 476 | 52%, 491 | 72%, 512 |
| Top speed in stretches of three to six seconds | 478 | 443 | 459 | 473 |
| What ended a stretch: he took over with no enemy in view / an enemy came into view / arrived or a new target / no way | 71 / 17 / 7 / 3% | 68 / 10 / 14 / 8% | 73 / 12 / 5 / 9% | 62 / 21 / 7 / 10% |
| Why he moves himself with no enemy in view: an enemy seen under 1.5 s ago / no target / the switch says no | 67 / 27 / 6% | 59 / 36 / 5% | 76 / 20 / 4% | 45 / 52 / 3% |

The legs do what the movement network does alone once they are left on: the long stretches are the pros' speed. What
keeps his overall numbers at half the pros' is how the switch is used. It goes off for a moment and on again many times
a minute, and every enemy sighting keeps it off for the rule's second and a half; with no target (no intention) his
legs have nowhere to go.

In his practice rounds: 7.8 to 8.1 items a minute in item runs (v14's end alone: 5.8), 34% of the time fast in the air
(11%), and over 58 to 63% of his tries at the pros' jumps (v14's end alone: 23%). Lost World's lava still takes 41 points
a minute in his runs there and Toxicity's slime more: he has not learnt where not to trust his legs.

Video (first person, his long stretches on his legs, Blood Run and Furious Heights):
`videos/duel_gru_v15b_6229/v15b_legs.mp4`.

## 3. His duels

Against the control (v14's end, no legs), 24 ten-minute duels a map in the run's simulator (legs on for him, the game's
weapon change on an empty weapon for both):

| His save | Blood Run | Aerowalk | Lost World | Sinister | Furious Heights | Battleforged | Mean | Games won, drawn, lost | Time on his legs | Time at 400 or more (the control's) | His own deaths a game |
|---|---|---|---|---|---|---|---|---|---|---|---|
| the start | 48% | 49% | 43% | 49% | 53% | 50% | 49% | 56, 12, 76 | 49% | 9.5% (1.9%) | 0.84 |
| 71 min | 48% | 46% | 47% | 56% | 55% | 49% | 50% | 59, 16, 69 | 49% | 9.9% (1.8%) | 0.78 |
| 103 min | 52% | 49% | 48% | 54% | 59% | 56% | 53% | 72, 11, 61 | 49% | 10.1% (1.9%) | 0.68 |
| 137 min | 49% | 47% | 49% | 54% | 56% | 52% | 51% | 67, 17, 60 | 48% | 9.9% (1.9%) | 0.67 |
| 202 min | 51% | 52% | 47% | 55% | 60% | 51% | 52% | 80, 11, 53 | 48% | 10.0% (1.9%) | 0.64 |
| 234 min | 53% | 50% | 50% | 60% | 62% | 52% | 55% | 83, 7, 54 | 48% | 10.0% (1.9%) | 0.56 |
| 276 min | 55% | 52% | 51% | 56% | 60% | 54% | 55% | 89, 9, 46 | 50% | 10.4% (1.9%) | 0.64 |
| 308 min | 50% | 51% | 46% | 53% | 65% | 50% | 52% | 74, 11, 59 | 52% | 10.8% (1.9%) | 0.77 |
| 371 min | 56% | 52% | 49% | 57% | 66% | 58% | 56% | 89, 9, 46 | 50% | 10.4% (1.9%) | 0.57 |
| 404 min | 57% | 51% | 52% | 58% | 66% | 58% | 57% | 92, 9, 43 | 48% | 10.2% (1.9%) | 0.62 |
| 434 min | 58% | 51% | 46% | 57% | 64% | 58% | 56% | 89, 7, 48 | 49% | 10.4% (1.9%) | 0.65 |

Against the Nightmare stand-in, 16 ten-minute duels a map (the last four maps are movement-only practice: no games there):

| Against the stand-in | Blood Run | Aerowalk | Lost World | Sinister | Furious Heights | Battleforged | Campgrounds | Hektik | Toxicity | Cure | Mean of the six | Games won, drawn, lost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v14's end | 71% | 84% | 93% | 75% | 68% | 82% | 71% | 54% | 68% | 52% | 79% | 139, 4, 17 |
| 137 min | 73% | 85% | 88% | 82% | 72% | 88% | 64% | 59% | 79% | 64% | 82% | 148, 3, 9 |
| 234 min | 75% | 89% | 91% | 77% | 75% | 85% | 64% | 57% | 75% | 68% | 82% | 145, 5, 10 |
| 308 min | 77% | 84% | 89% | 79% | 70% | 82% | 69% | 54% | 78% | 72% | 80% | 151, 2, 7 |

The start network (the switch as fitted, no training) is a little under the control: 56 games won, 76 lost. From the
second hour he wins more than he loses, and in the last three checks about two games for every one he loses. Lost
World, the map the teacher's lesson lost first, went from 43% to 46 to 52%. One check is 144 games: three points up or
down between checks is noise.

## 4. What the training changed, and what it did not

- The share of his time on his legs in games rose from 30% in the first minutes to 43 to 46% (Furious Heights 68%,
  Aerowalk 17%) and stayed there. With an enemy in view he is on his legs 1.5% of his legs' time.
- His hops improved slowly: the second and third 323 and 277 at the start, 377 and 373 at 434 minutes. His time at 400 or
  more did not (8 to 9% throughout).
- The policy moved 0.008 to 0.009 an update, the switch itself 0.0005: nothing in the run pushed it. The pay for speed
  (0.3) and for items is what it was for v14.
- The game's weapon change on an empty weapon acted 0.25 times a player-minute. He still holds an empty weapon 4 to 5% of
  his time in duels: the change comes only when he pulls the trigger.

## 5. Rockets, plasma, grenades (the second priority): not in this run

In hand in games: rockets 19%, lightning 37%, rail 22%, machine gun 21%, plasma 0.6%, grenades 0.1%: as v14. The weapon
changes of v15's first start (lives that begin with rockets, plasma or grenades in hand, one-weapon rounds, the lobber)
were left out so that this run changes movement alone. A side arm of 44 minutes with those rounds and without the
teacher's lesson held his runs (5.9 to 6.0 items a minute) and he got over more of the pros' jumps by himself (18%, then
26 to 30%); against the control it stood at 47%, 48% and 47% on Blood Run, Aerowalk and Lost World (32 duels a map; games 35 won, 7 drawn, 54 lost): a little under even after 44 minutes, where the lesson had him at 26 to 42%.

## 6. What did not work, and my own faults

- **The trainer crashed at 02:25** (the graphics card full after 89 updates) and I found it at 03:01: 26 minutes of
  training after the last save were lost and 37 minutes nothing trained. Resumed at 03:02 with smaller minibatches (80
  for 70). My wake-ups did not watch for a stall until then.
- The first fit of the switch (softer, read four times a second) was weaker than the control on Aerowalk and Lost World
  (42%, 40%); the run starts from a firmer one read ten times a second.
- For some minutes at 21:50 and 22:13 the PC stood at 96 to 97% of its load (a side arm, a dry run and duels at once).
- The trainer's "share of his time on his legs" counts every seat, the league's older selves too, who have none: it
  reads 43% or 56% by the opponent of the update. His own is the higher.
- A test of the starting rule with a shorter wait after a sighting (0.3 and 0.8 seconds for 1.5) gave nothing clear
  (Blood Run 64% and 54%, Lost World 41% and 38%): no reason to restart, and none was made.
- The real game cannot play this network yet (B-213).

## 7. What to try next

In the order I would take them; each is the owner's to decide.

1. **Put his legs on a server** (B-213): the plugins run them, the export packs the movement network, the game's weapon
   change in the plugin; then the movement network's jumping measured in the real game and his inputs set beside the
   simulator's. About half a day, on a quiet PC. Until then nobody can play him or see him strafe jump in the game, and
   that is the test that counts.
2. **Keep his legs on.** Three things that hold his speed back are in how the switch works, not in him:
   (a) a stretch is cut by a single "no" (62 to 73% of the endings, with no enemy in view): let it take two readings in
   a row to switch off, or give his own movement outputs a say only after the legs have been off for a moment;
   (b) with no target his legs have nowhere to go (20 to 52% of his slow time): let them take the way of the item rule's
   choice, or let "nothing" not be an intention he may hold while nobody is in view;
   (c) the rule's wait of a second and a half after any sighting is where most of his slow time is: it is his to
   unlearn, and one night did not do it. A stronger pay for speed in games (0.3 today) or pay for the speed gained from
   hop to hop would push on it; that is a reward, so only on the owner's word.
3. **The weapon changes** (rockets first, then plasma and grenades): the next run, on top of the legs, once the side
   arm's duels say its rounds do no harm. The owner's notes of the evening belong here too: the gauntlet he never
   holds, the weapon change when ammunition is low before it is gone (B-215).
4. **v16, decisions**: what he is paid for at 9:10 with a minute left (B-216: offense or defense by score, control and
   time), the noise he makes as an input and walking to be quiet (B-214), attention.

# v0.2: the report (2026-10-12)

**Which run is which.** v0.2 is `duel_gru_v0_2`: v0.1 (v15c's end, the network on the public server) with attention stage
A, 143 new inputs, the two-minute value estimate, the hop-gain pay, the first aim step and games on all ten maps
([MANIFEST_v0.2.md](MANIFEST_v0.2.md)). It ran from 2026-10-11 21:50 to 2026-10-12 08:43: 150 updates, 10.8 hours, no
stall, nothing changed in it. Stopped early on the owner's word ("you can stop earlier if it seems fully baked"): its
checks against v0.1 had read 56.7, 56.9, 57.9, 55.6% over four hours. Its end: `policy_end_v0_2.pt` (the lineage's
minute 7215). The control in every check was v0.1. The midway report: [MIDRUN_v0.2.md](MIDRUN_v0.2.md).

## In short

- **Not a clear improvement as a player.** Against v0.1 with the seats swapped, 32 ten-minute games a map: 48.7% of
  the frags on the six maps both know (79 games won, 15 drawn, 98 lost), 59, 58, 59 and 75% on Campgrounds, Hektik,
  Toxicity and Cure, which v0.1 never played games on. Over the ten maps 54.3% (173-26-121).
- **A sound base.** The attention part is in use (41% of his memory's input comes through it), nothing broke, the
  held-out maps did not suffer (the stand-in on House of Decay 77% at the start, 80% at the end; Dismemberment 58, 54),
  his item timing held.
- **His way of playing is where it was.** The scorecard beside the pros: 48% (v0.1 47%).
- **One slow drift, still going when it stopped**: rockets in hand with the enemy in view 18.4% to 22.1%, rail or
  lightning in hand while travelling 64.5% to 56.3%, rockets in hand while holding a spot 12.5% to 20.3%.

## 1. Strength

Against v0.1, his share of the frags (the end: 32 games a map; the night's checks: 16):

| Check | Blood Run | Aerowalk | Lost World | Sinister | Furious H. | Battleforged | Campgrounds | Hektik | Toxicity | Cure | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| the start (the same network: the noise) | 48 | 51 | 56 | 48 | 41 | 46 | 50 | 45 | 50 | 53 | 48.8 |
| 02:17 | 52 | 54 | 51 | 54 | 47 | 54 | 56 | 59 | 55 | 81 | 56.1 |
| 06:14 | 55 | 50 | 51 | 52 | 52 | 50 | 64 | 65 | 60 | 80 | 57.9 |
| 08:09 | | | | | | | | | | | 55.6 |
| **the end, 32 games a map** | 49 | 46 | 50 | 52 | 48 | 47 | 59 | 58 | 59 | 75 | **54.3** |

Against the stand-in (16 games a map): 72.0% at the start, 77.0% at the end (179-3-10): Blood Run 72, Aerowalk 78,
Lost World 88, Sinister 84, Furious Heights 72, Battleforged 90, Campgrounds 76, Hektik 65, Toxicity 79, Cure 86,
House of Decay 80, Dismemberment 54.

One caveat for the server: every check had both networks at the run's aim level (1.5). v0.1 plays on the server at
level 3, a sharper hand; "v0.2 as it would play against v0.1 as it plays today" was not measured.

## 2. The owner's seven points

The start is v0.1 at the run's aim level; the end is the end save through the pros' yardsticks
(`docs/bobby_yardsticks_v02start.json`, `_v02end.json`).

| He wants to see | The measure | Start | End | The pros |
|---|---|---|---|---|
| Building and maintaining speed | time at 400 or more; the second hop | 10.1%; 396 | 8.6%; 383 | 17.5%; 421 |
| Weapon usage (rockets) | rockets a minute; in hand with the enemy in view; a rocket then a beam, per ten minutes | 2.17; 18.4%; 0.07 | 2.69; 22.1%; 0.04 | 10.8; 39.5%; 3.6 |
| Not fighting from the low ground | higher than the enemy in view; the lowest third | 17.2%; 40.9% | 16.7%; 41.2% | 26.4%; 27.8% |
| Not picking fights when weak | commits with a stack under 60; what such a fight pays; closing when weak | 4.0%; -0.40; +26 | 4.4%; -0.42; +30 | 1.2%; +0.04; -12 |
| Strong item timings | back at the mega within 2 s of its return | 48.2% | 47.8% | 47.2% |
| Aggressive when it pays | commits against a fresh spawn, less against one alive over 25 s | -4.1 points | -4.1 points | +2.4 points |
| Spam, his and the enemy's | rockets with nobody in view, of his rockets; hits taken unseen a minute (v0.1 in the same games 1.8) | 0.3%; 1.70 | 1.5%; 1.6 | 49.7% |

The scorecard by group (how near the pros): position 62%, speed 79%, weapons 21% (17% at the start), aggression 1%,
control 99%; all fourteen measures 48%.

## 3. What the run taught

1. **Stage A works as a part and does not by itself change how he plays.**
2. **His weapon follows the draw of his style.** Three lives in four have a drawn weapon (a quarter each for rockets,
   rail, lightning) and damage with it pays half as much again. In a rockets life rockets are in his hand 48% of the
   time, in his other lives about one time in seven; by distance his hand hardly changes (rockets 27% close, 22% far).
3. **With rockets he is the weaker player**: frags per death 0.82 in a rockets life, 0.75 in a rail life, 1.17 in a
   lightning life, 0.90 in a general one.
4. **On his own feet he does not strafe jump**: on the frames his legs carry him his own turn is their choice 6% of
   the time (the ceiling 71%), and he is on his own feet half of every game.
5. The first aim step did what it was sized for (first hit at 20 to 40 degrees off 0.56 to 0.69 s; the pros 0.76;
   hits of the first half second 36 to 44%, the pros 36) and did not move his weapon mix by itself.
6. The hop-gain pay (0.18 a player-minute) is too small to show.
7. The two-minute value estimate adds a third to his credit and did no harm.
8. The checks' noise: the same network against itself read 48.8%, single maps 41 to 56%. And the eight-hour check
   read 57.9% where the end's larger check reads 54.3%: a single check is worth about three points.

## 4. Against people

From the public server's logs to 2026-10-12 08:00 (`people_scale.py`; every person a random id, the owner not yet
marked): nine persons, 678 frags. v0.2 has not met a person.

| Network | Frags | His share | In real games | Rating | Ahead of |
|---|---|---|---|---|---|
| v13 | 149 | 13% | 11% of 143 | 1157 | 0 of 8 |
| v14's end | 344 | 31% | 27% of 309 | 1251 | 2 of 8 |
| v0.1 | 185 | 32% | 14% of 119 | 1269 | 2 of 8 |

The two persons who met both v14's end and v0.1: his share 17% then 15%. On the server v0.1 is at 400 or more 6.2% of
the time (v14's end 1.7%, the people 17%), fires 4.8 rockets a minute (the people 10), stands in the lowest third 45%
of the time (the people 22%) and holds the machine gun 20% of the time someone is in view (8% in the simulator: he dies
and starts again that often). His simulator strength rose from v14 to v0.1; his results against strong people did
not.

## 5. Built beside it

- v0.2 plays on a real server (the export, both plugins); proven on a private one. Not on the public server: the
  owner's "Do not promote the live server yet".
- The owner's server remarks went live on 2026-10-12 09:59 with v0.1 unchanged (RESULTS 2026-10-12 09:45).
- Stages B and C of the attention model, the pre-start pieces and the weapon-in-hand lesson: built, tested alone and
  together, and merged into the repo on 2026-10-12 with every switch off ([../v0.2.1/V02_STAGE_B.md](../v0.2.1/V02_STAGE_B.md),
  [../v0.2.1/V02_STAGE_C.md](../v0.2.1/V02_STAGE_C.md)).
- A 90-second video of selected moments (`videos/v0_2/`).

## 6. Faults and what did not work

- Stopping at 08:43 was right for strength and early for the weapon drift, which was still moving.
- The night's last check before the end (55.6%) and the one before it (57.9%) are the same network within noise; I
  reported 57.9% as "not flat after all".
- A helper's dry run touched the graphics card for a moment at 22:17 (an empty `CUDA_VISIBLE_DEVICES` on Windows); the
  check loop ran with the enemy as a target switched on (harmless); the PC read 88 to 100% for half an hour
  during the night's builds.
- Not done: real games against the game's Nightmare bot after the run (the PC has not been quiet since).

## 7. What to try next

[PROPOSAL_v0.2.1.md](../v0.2.1/PROPOSAL_v0.2.1.md) and the owner's decision doc: from v0.2's end, one night in two legs.
Leg 1, movement and targets: his own movement taught by his legs, places as targets, the things he foretells, legs
that stand at a place. Leg 2, weapons and height: more rocket lives, the second aim step calibrated from the pros and
from the players on his server, the pull toward the pros' weapon in hand, a hit from above worth more. Held: whole
games (they need games that begin in their middle), several ways, legs that look. And for the owner, as he asked at
the run's start: rocket jumps and plasma climbs, the gauntlet, the judge of pro-like movement, sounds on stairs.

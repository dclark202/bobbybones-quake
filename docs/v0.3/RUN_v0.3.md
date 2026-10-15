# v0.3 on one page (the training manifest)

*Written 2026-10-14 15:40 on the owner's word ("Let's call this v0.3, it's a substantial revision"; it was planned as v0.2.2,
[../v0.2.2/RUN_v0.2.2.md](../v0.2.2/RUN_v0.2.2.md); the test runs behind it: [../v0.2.2/NIGHT_1013.md](../v0.2.2/NIGHT_1013.md)).
Revised 18:40: v0.3 is **the new baseline**, only the changes that tested well or fix what was wrong; the judge and the slow
memory were tested today and left out. A Pluto-shaped design is built beside it ([PLUTO.md](PLUTO.md)).
Status: **started 2026-10-14 20:17 on the owner's go after his play test.** Folder: `duel_gru_v0_3`.*

**Schedule (the owner, 2026-10-14 18:45):** runs to noon on Thursday 2026-10-15; goes on to 18:00 only if the hourly checks
keep improving (the last three rising beyond the checks' noise of about two points), else it stops at noon on its last save.
Hard stop at 18:00 (the trainer's time limit is set at the start to end then). Then the test and evaluation suite (about an
hour), results to the owner by 19:00 Thursday.

## What he trains on

One against one only, on all ten maps. Shares of his training time (measured in the test runs of this setting):

| Session | Share | What it is |
|---|---|---|
| Whole games | about 80% | ten-minute duels from the start, with the real clock and score; **overtime**: two more minutes while level at 10:00, again and again (at most ten periods), shown to him as the game's last two minutes again, as on the servers |
| Mid-game starts | about 15% | a game begun from a saved moment of an earlier game (score, clock, stacks and items as they were) |
| Item and jump runs | about 5% | movement practice on all ten maps: reach an item, take a pro's jump |

His opponents: his own last eight saves (one every 20 minutes) and **the control** (v0.2, the network on the public server) in a
quarter of his games.

## What changes from v0.2 (the network on the public server), and how sure we are

| | v0.2 | v0.3 | How sure |
|---|---|---|---|
| Rounds | two-minute rounds from a fresh start, groups of three and four, weapon drills | **whole ten-minute games, mid-game starts**, one against one only | tested together (test run V, below) |
| Openings | none | **the pros' opening from each spawn point** in a life's first ten seconds | tested together (V) |
| Item rule | names the nearest item, always | silent where nothing is left and where the enemy is nearer the item | tested together (V) |
| Places as targets (the map's holding places as things to go to) | not there | on (v0.2.1's parts, 791 inputs) | tested together (V) |
| The clock he sees | resets every two minutes | **the real game's clock and score**, in training, in the checks and on the servers | a fix: on the servers he played on a clock he never trained with; cannot be measured in the simulator |
| Overtime | none | two more minutes while level, as the servers play it | a fix; proven to change nothing else; only tied games |
| Styles | three lives in four a preferred weapon (rockets, rail, lightning) | **none**: every life he plays as himself | not tested; his weapon choice is watched at every check (below) |
| The guessing game | none | where the unseen enemy is, as a side question | no pull on his play by design |
| Memory | one memory, about 10 to 30 s of reach | the same | unchanged |

**The evidence.** Test run V (the first four rows together, from the same start) read 53.6, 53.9 and 53.5% against v0.2 at
updates 10, 20 and 30 (160 games each; one check swings about ±3 points by chance). Three checks in a row above 53 is a real
but modest lead, measured in the simulator only. The other rows are fixes (the clock and overtime make training match the
servers) or untested but watched (styles). So: the direction is right with fair confidence; how much it shows against people is
what the night and the next play tests tell.

Unchanged: human limits (reaction, flick speed, hand noise), sight and sound only, the pay, the ten maps, no powerups.

## What it starts from

v0.2's end network with v0.2.1's parts added and shut (the start of every test run since 2026-10-13), the same start as V.

## Tested today and left out

- **The judge that sees the truth** (Pluto's lesson, 17:10 to 18:26). His training was given a judge that sees the game's truth
  (the enemy's place, stack, weapon and target, the items' timers). Three test runs and a direct fit on saved frames: it
  explained the outcomes no better than the plain value (0.906 against 0.910 at update 4); the noise in his lessons comes from
  the next seconds (hits, misses, the enemy's next choices), not from what he cannot see. Left out ("kill the judge"); kept for
  the Pluto-shaped design, where the pay leans on winning.
- **The slow memory** (test run S, a second memory ticking every 1.2 s). Fell at every check (53.2, 51.8, 51.5, 50.1%) and lost
  to V head to head (47.6%). Four design faults: it fed every output (aim and keys too), its training pulled on the rest of
  the network, it learnt at the full rate on a weak signal, the guessing game did not reach it. To be rebuilt Pluto's way
  (a store of his past states read by attention, 2 to 3 minutes), with lessons that reach minutes ahead.

## How it is judged and stopped

- Every tenth update (about an hour) the newest save plays the control in 160 ten-minute games on ten maps. Level is 50%;
  the bar to beat is V's 53.5%.
- The start network is checked the same way first: the run's own level line.
- **Weapon watch** (styles are gone): rockets, rail and lightning in his hand and frags by weapon at every check; a fall under
  half of the test runs' share is reported at once.
- Stops by itself: two checks under 45%, or three checks falling in a row.
- Reports: one line a check at night, a summary at 07:00.
- Promoted to the public server only on the owner's word, and only if it beats the control.

## What to expect

- An update takes about 5.6 minutes; a check every hour.
- The first whole game ends about update 63 (about 6 hours in); overtime and the end of a game are learnt only from then.

## Before the start

1. Done: S stopped (17:09); the game server image rebuilt; a network of v0.3's shape checked on a private server (two Bobbys,
   five minutes: no errors, his movement network driving 48% of the time as in training); the plugin's error with the places as
   targets found there and fixed.
2. Done 20:10: the owner's play test (V30, S40, v0.2 on three local servers): V30 "definitely better than the control"; S40 much the same style, fought worse, spammed the lightning gun, died often in the poison on Hektik.
3. Overtime, the styles fix and the plugin fix go into the repo (each proven: unchanged with it off).
4. The owner's go.

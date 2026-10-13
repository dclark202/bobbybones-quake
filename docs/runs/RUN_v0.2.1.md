# v0.2.1 on one page

*Updated 2026-10-13 08:40. The run's folder is `duel_gru_v0_2_1`. The long write-up with every setting and pretest is
[MANIFEST_v0.2.1.md](MANIFEST_v0.2.1.md); this page is the one to read.*

## Status

**Training, first half, until 19:00 today.** Second start (06:43). Last check against the control: 48% of frags
(update 10). Nothing follows by itself: the second half starts overnight only on the owner's word.

## What the run is for

It starts from v0.2 (the network on the public server) and is judged against it ("the control").

| Goal | How this run works on it | Which half |
|---|---|---|
| 1. Know where the enemy is and act on it | The guessing game; the item rule stays quiet where the enemy is nearer to the item | first |
| 2. Keep speed | The movement autopilot, as in v0.2. The new lesson for it failed and is out | first |
| 3. Rockets | More of his lives are rocket lives; the pros' weapon in hand when nobody is in view | second |
| 4. Position, high ground | Holding places as targets (first); a hit from above pays more (second) | both |

## What is switched on now (first half)

| Part | What it does | State |
|---|---|---|
| The guessing game | Eight questions about an enemy he cannot see (where, what he holds, how strong, who gets the mega next), corrected afterwards by the truth. No pay for it | on |
| New inputs opened | Nine groups of inputs about places and what he believes, let in over the first hour | on |
| Holding places as targets | He can choose a place on the map as a target, like an item | on |
| Item rule quiet in a contest | The teacher that names an item says nothing where he believes the enemy is nearer to it | on |
| Autopilot held back | On a tenth of his stretches he moves himself, to keep in practice | on |
| **Autopilot lesson** | His own keys graded against the autopilot's | **off: it broke him** |
| Aim | Unchanged from v0.2 | unchanged |

## How he trains

- Two-minute rounds, each a fresh start. No whole games and no score to defend or chase.
- About five in six rounds are fights on the ten maps (one against one, and three or four players all against
  all); the rest are weapon drills.
- Opponents: his own recent saves, with v0.2 and v0.1 in a quarter of the rounds.
- 5,040 matches side by side; about 130 updates and 52,000 rounds in the twelve hours.

## How it is judged

- **The check:** about every 40 minutes the newest save plays v0.2 in 160 full ten-minute games on ten maps.
  Level is 50%.
- **Stops by itself:** two checks in a row under 40%.
- **Passes the first half:** the last two checks at 45% or more, and hits in view no lower than at the start (28%).
- **At the end:** 32 games a map against v0.2, the Nightmare stand-in on the ten maps and two maps he has
  never trained on, the speed profile, and how much he depends on knowing where the enemy is.

## What has happened

| When | What |
|---|---|
| Oct 12, 20:31 | First start, everything on |
| Oct 12, 23:30 | Stopped by its own rule: 52% at the start, 36% after ten updates, 25% after twenty |
| Night | Seven short test runs, one part on at a time. The autopilot lesson alone gave 36%; every other part held 46 to 55% |
| Oct 13, 06:43 | Second start without the autopilot lesson, first half only |
| Oct 13, 08:12 | First check: 48% |

## What comes next

| When | What | Whose call |
|---|---|---|
| 12:00 and 16:00 | Mid-run reports | |
| 19:00 | The run ends; the end's checks; a recommendation on the second half | |
| Overnight | The second half (rockets, weapon in hand, height) | the owner's word |
| The next run | Whole ten-minute games and mid-game starts with a score spread (B-244) | the owner, 2026-10-13: "we should begin incorporating those" |

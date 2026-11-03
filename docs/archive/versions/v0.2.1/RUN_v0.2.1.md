# v0.2.1 on one page

*Updated 2026-10-13 16:40. The run's folder is `duel_gru_v0_2_1`. The long write-up with every setting and pretest is
[MANIFEST_v0.2.1.md](MANIFEST_v0.2.1.md); this page is the one to read. The review of what went wrong:
[AUDIT_v0.2.1.md](AUDIT_v0.2.1.md).*

## Status

**Stopped, twice.** The first start (Oct 12, 20:31) was stopped by its own rule after twenty updates at 25% against
the control; the second (Oct 13, 06:43, without the autopilot lesson) by hand after thirty updates at 39%. Since then
the graphics card runs short test runs, one part at a time, to find what cost him. No second half. The next run is
being planned (section "What comes next").

## What the run was for

It started from v0.2 (the network on the public server) and was judged against it ("the control").

| Goal | How this run worked on it | Which half |
|---|---|---|
| 1. Know where the enemy is and act on it | The guessing game; the item rule stays quiet where the enemy is nearer to the item | first |
| 2. Keep speed | The movement autopilot, as in v0.2, with a lesson to grade his own keys against it | first |
| 3. Rockets | More of his lives are rocket lives; the pros' weapon in hand when nobody is in view | second (never reached) |
| 4. Position, high ground | Holding places as targets (first); a hit from above pays more (second) | both |

## What was switched on, and what each part cost

Each part was also run alone from the same start, in a test run of ten or twenty updates, and checked against the
control (level is 50%; the same network against itself reads about 49%).

| Part | What it does | Alone |
|---|---|---|
| The guessing game | Eight questions about an enemy he cannot see, corrected afterwards by the truth. No pay for it | **44%, then 42%**: the slow slide |
| **Autopilot lesson** | His own keys and view turn graded against the autopilot's | **36%; 30%** held out of the shared layers: the collapse |
| Autopilot held back | On a tenth of his stretches he moves himself | 55% |
| New inputs opened | Nine groups of inputs about places and what he believes, let in over the first hour | 50% |
| Item rule quiet in a contest | The teacher that names an item says nothing where he believes the enemy is nearer to it | 52% |
| Holding places as targets | He can choose a place on the map as a target, like an item | in the base: 52%, 52% |
| None of the new parts | | 52%, 52% |

## How he trained

- Two-minute rounds, each a fresh start. No whole games and no score to defend or chase.
- About five in six rounds were fights on the ten maps (one against one, and three or four players all against
  all); the rest weapon drills.
- Opponents: his own recent saves, with v0.2 in a quarter of the rounds.
- 5,040 matches side by side, an update every six minutes.

## How it was judged

- **The check:** about every 40 minutes the newest save played v0.2 in 160 full ten-minute games on ten maps.
- **Stopped by itself:** two checks in a row under 40%.
- Training's own number against v0.2 read 55% the whole time and was no warning: it is made of short slices of
  two-minute rounds, drills and group fights, and is not a check.

## What has happened

| When | What |
|---|---|
| Oct 12, 20:31 | First start, everything on |
| Oct 12, 23:30 | Stopped by its own rule: 52% at the start, 36% after ten updates, 25% after twenty |
| Night | Seven test runs of ten updates, one part at a time: the autopilot lesson alone 36% |
| Oct 13, 06:43 | Second start without the autopilot lesson |
| Oct 13, 10:10 | Stopped by hand: 48%, 41%, 39% at updates 10, 20, 30 |
| Oct 13, day | Test runs of twenty updates on ten maps: none of the new parts 52%, 52%; the guessing game alone 44%, 42% |
| Oct 13, 13:50 | The slid save loses in two-minute games too (39%): the checks' game length is not the gap |
| Oct 13, 16:30 | The review: the guessing game moves the shared layers outside PPO's limits (every output's step doubled); the autopilot lesson trained his aim output on the autopilot's frames ([AUDIT_v0.2.1.md](AUDIT_v0.2.1.md)) |
| Oct 13, 16:12 on | Three test runs one against one: the guessing game at a tenth of its pull (P), none of the parts (E), the guessing game with no pull on the shared layers (Q) |

## What comes next

| When | What | Whose call |
|---|---|---|
| 19:00 | The report of the day's findings | |
| Tonight | P, E, Q end about 23:15; results in the morning | |
| Then | The next run's pretest: one against one, whole games, mid-game starts, spawn starts with the openings, a movement slice (B-244, B-245), twenty updates and the check | the owner's twelve answers in the audit, then his go |

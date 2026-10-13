# v0.2.2 on one page

*Written 2026-10-13 16:45 from the owner's answers to [AUDIT_v0.2.1.md](../v0.2.1/AUDIT_v0.2.1.md), section 5. Status:
**planned; the pretest runs tonight; the run starts only on the owner's go.** The run's folder will be `duel_gru_v0_2_2`.*

## What changes from v0.2.1, in one list

| | v0.2.1 | v0.2.2 |
|---|---|---|
| Players | one against one, and groups of three and four | **one against one only** |
| Rounds | two-minute rounds from a fresh start, weapon drills, item and jump runs | **whole ten-minute games (about 70% of the time), mid-game starts from saved moments of real games (about 20%), item and jump runs on all ten maps (about 10%)** |
| Openings | none: the item rule named the nearest item, the style its weapon | **the pros' opening from each spawn point is what the item teacher names in a life's first ten seconds**; the second pickup is passed over where he believes the enemy within 500 units; where nothing is left the teacher is silent |
| The guessing game | eight questions at full pull on the shared layers | **where the enemy is (`place`, `near`) only, at a tenth of the pull or none, by tonight's test runs** |
| Autopilot lesson | on, then off | **gone**; the withholding stays (one stretch in ten he moves himself) |
| New inputs opened, item rule quiet in a contest, holding places as targets | on | on, unchanged |
| Win-chance pay | off | off (its own test later) |
| Styles | three lives in four styled | unchanged; the opening overrides the style's weapon for ten seconds |

## What it starts from

v0.2.1's start network (v0.2's end converted), the same control. The slid saves of v0.2.1 are not used.

## How it is judged and stopped

- The check: every tenth update the newest save plays the control in 160 ten-minute games on ten maps. Level is 50%.
- Stops by itself: two checks under 45%, or three checks falling in a row.
- Promoted only if it beats the control at the end.

## Before the start

1. Tonight: the three test runs of the guessing game's pull (P, E, Q) end about 23:15.
2. Then the spawn openings and the new rounds go into the repo (built and tested in a staging copy; the simulator with
   every new switch off is unchanged, proven), with two small fixes: the movement drills' share counted right beside
   the new rounds, and training's own reading against the control counted in 1v1 games only (a hint, not a check).
3. The pretest: the run's exact setting from the start network, twenty updates, the check at ten and twenty. Ends about
   02:30; results in the morning.
4. The owner's go.

## Still to build (not needed for the pretest)

| What | Why | When |
|---|---|---|
| The watcher with the new stopping rule and the check loop for the run | the run stops itself | before the run, half an hour |
| The bank of saved moments written to a file and loaded at a start | without it the first ten game-minutes of every process have no mid-game starts | if the run goes ahead; half a day |
| The guessing game's losses scaled per question | only if neither a tenth of the pull nor none holds level tonight | if needed |

## The owner's answers (2026-10-13)

Guessing game: "I will defer to you here ... believe including this is the right thing to do". Autopilot lesson: dropped.
Movement drill: item runs and jump runs. Weapon drills: gone. Spawn starts: the label inside the games, no separate
round. Mid-game bank: accept for the test, build the file if the run goes ahead. Styles: the opening overrides for ten
seconds. Win-chance pay: off. The PC: overnight for test runs. Stopping: both rules.

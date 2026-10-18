# v0.3.6: rockets and grenades before the head (the owner's go, 2026-10-17)

A run between the one movement network (v0.3.5, step 6 of [UNIFIED_MOVEMENT.md](UNIFIED_MOVEMENT.md)) and v0.4's head. It
goes ahead only if the movement work holds: Sunday's play test and v0.3.5's checks against the control. It changes nothing
of the head's plan, except that the head is built and pretrained on v0.3.6's inputs.

## Why

He aims rockets at the enemy's body. Rockets are 20% of his time in hand and 13% of his frags (lightning 69%), and he fires
0.0 blind rockets a minute where the pros fire about 4.5. The owner, 2026-10-17: rockets are aimed at *things* (the floor
under the enemy, a wall, around a door), and splash is what to expect. His inputs give him only the enemy to aim at: a
lead point on the enemy's body and the floor's angle under it. Splash is already paid like direct damage, point for point.

## What goes in

| # | Change | Kind |
|---|---|---|
| 1 | Floor aim point: yaw and pitch from his crosshair to the floor under the enemy's predicted position (rockets) | input |
| 2 | Backstop: where a rocket fired now would explode, against the enemy's distance | input |
| 3 | The nearest wall near the predicted spot: its direction and distance (if 1 and 2 test cleanly) | input |
| 4 | Pre-fire points: the pros' blind-shot spots (`sim/pro_places`) nearest the enemy's believed route: yaw, pitch, distance, when the enemy could be there (rockets and grenades) | input token |
| 5 | Blind rockets free (`BLIND_RL_DMG=0`). Equilibrium: both sides pre-fire more where it lands damage, approaches through doors get more dangerous for both. Goals: weapon use, counterplay | pay |
| 6 | Rocket-jump runs (`RJ_RUN_P`, built: B-252; `RJ_CLEARED=1`) at **10% of his time, out of the 20% solo share**: item runs 5%, jump runs 5%, rocket-jump runs 10% (the owner, 2026-10-17) | solo runs |

New inputs start at zero weight and the new token with its door shut: he plays the same on the first frame (proved by
fixed-seed replays). Ten updates and the check against the control before the run continues.

## Held back

Tried only if 1 to 6 do not bring pre-fire or the rocket share up within about a day:
- a pay for knocking the enemy into the air
- a pay for a miss that lands near him
- a pay for a pre-fire into a valid spot (if tried: about a quarter of the proposed +0.012)
- the weapon teacher out of sight (the pros'-hand lesson, `HAND_TEACH`, at a low weight, tested on its own)
- cheaper rockets in view: lightning is already taxed about twice as hard per second of firing

## First

The rocket measurement (postponed by the owner to Sunday noon or later, so that it does not slow the run): direct
against splash, where his rockets explode, how well he dodges, the pros' and his games against people. Its scripts
are ready. It decides how hard to push inputs 1 to 3.

# BobbyBones: backlog

Every work item, with an ID. Status: `next` (planned for the coming iteration), `open`, `doing`, `done`,
`dropped`. Results are in [RESULTS.md](RESULTS.md); the current "Now" list is in [PLAN.md](PLAN.md).
Priority: P1 = blocks beating Nightmare, P2 = needed for good play, P3 = later.

## Training (duel simulator)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-01 | P1 | next | Aim-only rounds: close, facing, against a scripted strafing/jumping target, weighted toward LG | LG hit rate flat at 4-5% all run; owner's pick |
| B-02 | P1 | next | Tracking fixes: turn bins below 0.1 deg/frame, lighter smoothing on small corrections, pitch pull (x0.95 per frame) replaced by a small cost | Smoothing and the pitch pull fight fine tracking |
| B-03 | P1 | next | Reaction delay 25 ms (one frame) for now; pare back toward human values once he plays well (owner, 2026-10-03) | 150 ms on all enemy info = 48 units of stale position at strafe speed; humans predict smooth motion |
| B-04 | P1 | next | Single-weapon drills 75% -> ~35% of rounds | Live: he holds each weapon ~25% of the time (random choice); 0-10 normal vs 2-6 in LG-only |
| B-05 | P2 | next | Small cost per shot with no enemy in view | Fires 50% of frames with the enemy visible 6-20% |
| B-06 | P1 | next | Scripted Nightmare-like opponents in the league | The bar is Nightmare; self-play alone never meets one |
| B-07 | P1 | next | Train on the nine-weapon simulator (`sim/duel_env.py`, 164 inputs), fresh network | v2 policy is blind to plasma, grenades, shotgun, HMG |
| B-08 | P1 | next | Re-rank this list from the owner's play-test notes and session logs | First human session 2026-10-03 evening |
| B-11 | P2 | open | Start duel training from the movement policy (strafe jumping) | Fast-air share in duels is 2% |
| B-12 | P2 | open | Full-length duels with a score and clock; item timing reward only through winning | Megas 0.24, red armors 0.15 per player-minute; short rounds hide item control |
| B-13 | P2 | open | Memory aid or longer training sequences for item timers | Sequences are 3.2 s; item respawns are 25-35 s |
| B-15 | P3 | open | Ammo as a scarce resource (no endless ammo in drills, real pickup counts) | Owner: later, after he stops sucking |
| B-16 | P3 | open | Robustness training (sensor noise, late commands) | In code for movement, untested for duels |
| B-17 | P3 | open | Shared-memory worker communication for more steps per second | ~150k steps/s now |

## Learning from people

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-09 | P2 | open | Rebuild fair inputs from parsed pro demos; infer movement keys with the simulator | 374 demos parsed (Blood Run, Aerowalk) |
| B-10 | P2 | open | Imitation training, then self-play on top | Expected to fix crosshair placement and weapon choice |
| B-18 | P2 | open | Use play-test sessions as imitation data (the human's keys are logged per frame) | `frames.csv` has `o_fwd/o_right/o_up/o_fire` |

## Simulator accuracy

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-14 | P2 | open | Measure on the real server: pickup amounts, ammo caps, weapon switch time, damage through armor | Marked unverified in `sim/duel_env.py` |
| B-19 | P3 | open | Grenade at own feet: lift is 650 u/s in the simulator vs 277 measured | RESULTS 2026-10-03 afternoon |
| B-20 | P3 | open | Nav builder: running-start jumps (Aerowalk Red Armor reachable) | Owner: on the list |
| B-21 | P3 | open | Sound model: footsteps, jumps, pickups, weapon fire (now only "moving fast within 800 units") | |
| B-22 | P3 | open | Hitbox details, crouching, fall damage, spawn selection, respawn delay | |

## Live server and tooling

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-23 | P2 | open | Session report script: per-session accuracy by weapon, aim error while visible, time-to-damage, notes with context | Reads the LOGS.md session schema |
| B-24 | P2 | open | Trainer metrics: accuracy while the enemy is visible, crosshair error while visible | Hit rate now counts shots at nothing |
| B-25 | P3 | open | Exact per-shot attribution in session logs (now inferred from health drops) | minqlx has no damage event |
| B-26 | P3 | open | Opponent profiles and player reports | Stage 6 |
| B-27 | P3 | open | Rewrite CLAUDE.md around the simulator approach (it still describes the retired coach) | |

## Done

| ID | Item | Result |
|---|---|---|
| B-101 | Movement simulator validated against the real game | RESULTS "simulator fidelity" |
| B-102 | Strafe jumping learned and transferred live | RESULTS "learned strafe jumping transfers" |
| B-103 | Simulator-built nav graphs, three-map movement policy | RESULTS 2026-10-03 morning |
| B-104 | Nine weapons measured on a real server and simulated | RESULTS 2026-10-03 afternoon |
| B-105 | Aim input fix (delay only on enemy state, crosshair-to-enemy inputs), weapon drills | RESULTS 2026-10-03 afternoon |
| B-106 | GRU self-play pipeline on the GPU, league of snapshots | RESULTS `duel_gru_v2` |
| B-107 | Pro demo download and parser (374 demos) | RESULTS "Data sources" |
| B-108 | Live port of a duel policy, play-test server, session logs, notes and drills | RESULTS 2026-10-03 evening |

## Dropped

| Item | Why |
|---|---|
| Settings search (coach) on top of Nightmare | Did not move win rate (6% vs control 69%); RESULTS 2026-10-02 |
| Accuracy tuner that loosened aim | Owner: never miss on purpose |
| 25 ms bot physics | Ground-strafing exploit; owner chose human physics |
| Rewriting duel logic in C | Profiling showed little gain; bigger batches gave 2.4x |

# BobbyBones: backlog

Every work item, with an ID. Status: `next` (planned for the coming iteration), `open`, `doing`, `done`,
`dropped`. Results are in [RESULTS.md](RESULTS.md); the current "Now" list is in [PLAN.md](PLAN.md).
Priority: P1 = blocks beating Nightmare, P2 = needed for good play, P3 = later.

## Training (duel simulator)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-01 | P1 | doing (`duel_gru_v3`) | Aim-only rounds: close, facing, against a scripted strafing/jumping target, weighted toward LG | LG hit rate flat at 4-5% all run; owner's pick |
| B-02 | P1 | doing (`duel_gru_v3`) | Tracking fixes: turn bins below 0.1 deg/frame, lighter smoothing on small corrections, pitch pull (x0.95 per frame) replaced by a small cost | Smoothing and the pitch pull fight fine tracking |
| B-03 | P1 | doing (`duel_gru_v3`) | Reaction delay 25 ms (one frame) for now; pare back toward human values once he plays well (owner, 2026-10-03) | 150 ms on all enemy info = 48 units of stale position at strafe speed; humans predict smooth motion |
| B-04 | P1 | doing (`duel_gru_v3`) | Single-weapon drills 75% -> ~35% of rounds | Live: he holds each weapon ~25% of the time (random choice); 0-10 normal vs 2-6 in LG-only |
| B-05 | P2 | doing (`duel_gru_v3`) | Small cost per shot with no enemy in view | Fires 50% of frames with the enemy visible 6-20% |
| B-06 | P1 | doing (`duel_gru_v3`) | Scripted Nightmare-like opponents in the league | The bar is Nightmare; self-play alone never meets one |
| B-07 | P1 | doing (`duel_gru_v3`) | Train on the nine-weapon simulator (`sim/duel_env.py`, 164 inputs), fresh network | v2 policy is blind to plasma, grenades, shotgun, HMG |
| B-08 | P1 | doing (`duel_gru_v3`) | Re-rank this list from the owner's play-test notes and session logs | First human session 2026-10-03 evening |
| B-11 | P2 | doing (`duel_gru_v3`) | Movement rounds inside duel training (run to mega / red / yellow armor, reward = time gained) | Play test: jump key 30% of frames, above 330 u/s 5% of the time (owner 37-46%) |
| B-12 | P2 | open | Full-length duels with a score and clock; item timing reward only through winning | Megas 0.24, red armors 0.15 per player-minute; short rounds hide item control |
| B-13 | P2 | open | Memory aid or longer training sequences for item timers | Sequences are 3.2 s; item respawns are 25-35 s |
| B-15 | P1 | doing (`duel_gru_v3`) | Ammo finite in every round kind; real pickup counts still unmeasured (B-14) | Play test: spams, runs dry, then will not shoot |
| B-16 | P3 | open | Robustness training (sensor noise, late commands) | In code for movement, untested for duels |
| B-17 | P3 | open | Shared-memory worker communication for more steps per second | ~150k steps/s now |

| B-28 | P1 | doing (`duel_gru_v3`) | Real weapon-switch time in the simulator (0.425 s measured) plus a tiny switch cost | Play test: 33-75 switches per minute |
| B-29 | P1 | doing (`duel_gru_v3`) | Bigger health/armor bonus (0.3 per 100 points), to be faded later | Play test: owner took ~75 big items, Bobby 14 |
| B-30 | P2 | open | Positioning: high ground, where people stand, not lingering at teleporters | Play test notes; needs full duels (B-12) or demos (B-10) |
| B-31 | P2 | open | Rockets aimed at surfaces near the enemy, not only at the body | Play test note |
| B-32 | P2 | done (dry run vs Nightmare; human test pending) | Mirror the new simulator rules (view smoothing, pitch rule, nine weapons, goal inputs) in `plugins/duelbot.py` so `duel_gru_v3` can be played | Needed for the morning play test |

## Beyond aim (owner priority 2026-10-04: smooth, fast movement; positioning; weapon choice)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-42 | P1 | open | Full-length duels with clock and score as the main round type, so speed, items and position pay through winning | Short rounds reward only aim; B-12 |
| B-43 | P1 | built, for the next run | Movement teacher: copy the strafe-jumping movement policy's actions in movement rounds (extra loss), plus longer item circuits and a bonus for arriving with speed | Movement rounds sit at 302 u/s (run speed); the movement-only policy strafe-jumps |
| B-44 | P1 | built, for the next run (8 styles: allround, sniper, rusher, tracker, dodger, and the bad ones stander, jumper, spammer) | Opponents that punish bad choices: scripted styles (keeps range with rail, rushes with rockets, LG tracker, retreats when hurt, dodges) in the league and the test rooms | Every weapon gives the same kills per minute against the current target |
| B-45 | P2 | open | Pro-demo position prior: where pros stand and which weapon they hold by distance, from the 374 parsed demos (positions need no key inference); use as a benchmark first, as a small reward only if needed | B-30, B-09 |
| B-46 | P2 | open | Suite rooms for these: route times against a reference, speed in normal rounds, share of fights from higher ground, big-item share over a full duel, weapon by distance against opponents that fight back | B-35 |

## New inputs and rules (owner 2026-10-04: all high and medium inputs, round-level memory, crouch, walk, fall damage, true hitbox)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-47 | P1 | built in the simulator, not yet trained | New inputs (311 total): clock and score, all item types (several per kind), sounds (pickups, weapon fire, jumps, teleports), map position and identity, view / up / long rays, enemy weapon and facing, damage dealt estimate, hit feedback, nearest teleporter and jump pad | He could not see these; positioning and decisions depend on them |
| B-48 | P1 | built in the simulator, not yet trained | Memory kept across deaths for the whole round; longer training sequences (6.4 s) and horizon (gamma 0.998) | Stack and item timers must survive a death |
| B-49 | P1 | built in the simulator, not yet trained | Crouch and walk (walking is silent), fall damage (Quake 3 rule: 5 / 10 by landing speed) | Owner request |
| B-50 | P1 | open | Widen the `duel_gru_v3` network to the new inputs and actions without losing its skills (new inputs start at zero weight); verify on a copy | So aim is kept |
| B-51 | P1 | open | Mirror B-47 to B-49 in `plugins/duelbot.py` (sounds, clock, score, crouch, walk) so the next Bobby can be played | |
| B-52 | P2 | open | True hitbox check on the real server: rail shots at the edges of the box, standing and crouched (the simulator uses the game's 30 x 30 x 56 box, 40 high crouched; Keel's model matches it) | Owner: hitbox must be true |
| B-53 | P2 | open | Measure on the real server: how far pickups, weapon fire, jumps and teleporters are heard (simulator: 1200 units, a guess); fall damage values | New rules are unmeasured |
| B-54 | P1 | open | Simulator speed: the new rays and item inputs halve steps per second; profile and speed up | Smoke test 9.5k vs 18.9k steps/s in one process |
| B-55 | P2 | open | Test rooms for the new abilities: item timing (back at mega when it respawns), sound (enemy takes an item out of sight: does he react), memory across a death (returns to the fight or the item), fall damage per minute, crouch and walk use, high-ground fights | Owner request |
| B-56 | P3 | flagged | Not true to the game yet: short rounds, items reset at round start, spawning with every weapon, close respawns. Kept for now to coax out the behavior; move to real duel rules later (B-42) | Owner 2026-10-04 |

| B-57 | P1 | open | Lab-map rooms in the simulator suite (same 41 rooms for Bobby), and the human-aim limits and new inputs mirrored in `plugins/duelbot.py` (acquisition delay, hand noise, reload jitter, sounds, clock, crouch, walk) | Needed to compare cards and to play the next Bobby |
| B-58 | P1 | built, not trained | Human aim limits: 200 ms acquisition, 50 ms tracking, flick cap, hand noise, reload jitter, fire-button cost | Owner play test 2026-10-04: aim superhuman |
| B-59 | P1 | built, not trained | Random 1-2 weapon loadouts per player (60%), real duel spawn (20%), all weapons (20%); two-sided damage reward | Owner play test: shotgun only, takes every fight |
| B-60 | P2 | open | Tune the aim limits from the owner's test-suite card (human baseline per room) | Owner 2026-10-04 |
| B-61 | P2 | open | Community release: public test server (rooms + play), opt-in baseline cards, feedback channel | Owner wants to share on Reddit |

## Test suite

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-33 | P1 | done (v1: `sim/test_suite.py`) | Standard test rooms run on any checkpoint: aim per weapon and target, weapon choice by range, movement, solo (items, firing at nothing), scripted-fighter ladder; one scorecard with changes against an earlier card | Owner request 2026-10-03 |
| B-35 | P2 | open | Test suite v2: dodge room, awareness room (enemy leaves view), frozen past checkpoints and Nightmare on the ladder, run automatically at every league snapshot | Left out of v1 |
| B-34 | P1 | built, waiting for the owner's runs | The same rooms on the play-test server (`!room ...`, `!room suite`), human baseline card in `data/duellive/suite/` | Dry run with a Nightmare bot as the subject worked |
| B-36 | P2 | open | Run Bobby himself through the live rooms (needs a second controlled bot as the target) | Now only the simulator scores Bobby |

| B-37 | P2 | open | Measure on the real server: weapon switch started during a reload (simulator now waits for the reload, Quake 3 rule) | RESULTS 2026-10-03 23:15 |
| B-38 | P1 | done (spawn = one measured pickup per weapon; shotgun use explained in RESULTS 2026-10-04 08:30) | Spawn loadout ammo: shotgun dominates (10 shells vs 60 cells, 5 slugs). Decide amounts, ideally from measured pickups (B-14) | `duel_gru_v3`: shotgun held 88-95%, 84% of frags |

| B-39 | P2 | open | Shaping costs must be sized against the entropy bonus (or lower the entropy weight on the weapon and fire choices) | RESULTS 2026-10-04 morning |
| B-40 | P2 | open | Far-range aim: he loses sight of targets at 800-1200 units (in view 12-16% of the time) | Test suite card at 231 min |
| B-41 | P3 | open | Training survives a PC crash: auto-resume on boot, test suite at each snapshot | Crash 2026-10-04 00:40 lost six hours |

## Learning from people

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-09 | P2 | open | Rebuild fair inputs from parsed pro demos; infer movement keys with the simulator | 374 demos parsed (Blood Run, Aerowalk) |
| B-10 | P2 | open | Imitation training, then self-play on top | Expected to fix crosshair placement and weapon choice |
| B-18 | P2 | open | Use play-test sessions as imitation data (the human's keys are logged per frame) | `frames.csv` has `o_fwd/o_right/o_up/o_fire` |

## Simulator accuracy

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-14 | P2 | open | Measure on the real server: ammo caps, weapon picked up when already owned, damage through armor, HMG (pickup amounts and switch time done) | Marked unverified in `sim/duel_env.py` |
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
| B-27 | P3 | done | Rewrite CLAUDE.md around the simulator approach; old bot moved to `legacy/` | 2026-10-04 |

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

# BobbyBones: backlog

Every work item, with an ID. Status: `next` (planned for the coming iteration), `open`, `doing`, `done`,
`dropped`. Results are in [RESULTS.md](RESULTS.md); the current "Now" list is in [PLAN.md](PLAN.md).
Priority: P1 = blocks beating Nightmare, P2 = needed for good play, P3 = later.

## Training (duel simulator)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-01 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Aim-only rounds: close, facing, against a scripted strafing/jumping target, weighted toward LG | LG hit rate flat at 4-5% all run; owner's pick |
| B-02 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Tracking fixes: turn bins below 0.1 deg/frame, lighter smoothing on small corrections, pitch pull (x0.95 per frame) replaced by a small cost | Smoothing and the pitch pull fight fine tracking |
| B-03 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Reaction delay 25 ms (one frame) for now; pare back toward human values once he plays well (owner, 2026-10-03) | 150 ms on all enemy info = 48 units of stale position at strafe speed; humans predict smooth motion |
| B-04 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Single-weapon drills 75% -> ~35% of rounds | Live: he holds each weapon ~25% of the time (random choice); 0-10 normal vs 2-6 in LG-only |
| B-05 | P2 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Small cost per shot with no enemy in view | Fires 50% of frames with the enemy visible 6-20% |
| B-06 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Scripted Nightmare-like opponents in the league | The bar is Nightmare; self-play alone never meets one |
| B-07 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Train on the nine-weapon simulator (`sim/duel_env.py`, 164 inputs), fresh network | v2 policy is blind to plasma, grenades, shotgun, HMG |
| B-08 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Re-rank this list from the owner's play-test notes and session logs | First human session 2026-10-03 evening |
| B-11 | P2 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Movement rounds inside duel training (run to mega / red / yellow armor, reward = time gained) | Play test: jump key 30% of frames, above 330 u/s 5% of the time (owner 37-46%) |
| B-12 | P2 | open | Full-length duels with a score and clock; item timing reward only through winning | Megas 0.24, red armors 0.15 per player-minute; short rounds hide item control |
| B-13 | P2 | open | Memory aid or longer training sequences for item timers | Sequences are 3.2 s; item respawns are 25-35 s |
| B-15 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Ammo finite in every round kind; real pickup counts still unmeasured (B-14) | Play test: spams, runs dry, then will not shoot |
| B-16 | P3 | open | Robustness training (sensor noise, late commands) | In code for movement, untested for duels |
| B-17 | P3 | open | Shared-memory worker communication for more steps per second | ~150k steps/s now |

| B-28 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Real weapon-switch time in the simulator (0.425 s measured) plus a tiny switch cost | Play test: 33-75 switches per minute |
| B-29 | P1 | done (`duel_gru_v3`, RESULTS 2026-10-04) | Bigger health/armor bonus (0.3 per 100 points), to be faded later | Play test: owner took ~75 big items, Bobby 14 |
| B-30 | P2 | open | Positioning: high ground, where people stand, not lingering at teleporters | Play test notes; needs full duels (B-12) or demos (B-10) |
| B-31 | P2 | open | Rockets aimed at surfaces near the enemy, not only at the body | Play test note |
| B-32 | P2 | done (dry run vs Nightmare; human test pending) | Mirror the new simulator rules (view smoothing, pitch rule, nine weapons, goal inputs) in `plugins/duelbot.py` so `duel_gru_v3` can be played | Needed for the morning play test |

## Beyond aim (owner priority 2026-10-04: smooth, fast movement; positioning; weapon choice)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-42 | P1 | open | Full-length duels with clock and score as the main round type, so speed, items and position pay through winning | Short rounds reward only aim; B-12 |
| B-43 | P1 | used for 80 minutes in `duel_gru_v4`, then removed by the owner (fast-air in item runs 8% -> 33%) | Movement teacher: copy the strafe-jumping movement policy's actions in movement rounds (extra loss), plus longer item circuits and a bonus for arriving with speed | Movement rounds sit at 302 u/s (run speed); the movement-only policy strafe-jumps |
| B-44 | P1 | in training (`duel_gru_v4`) (8 styles: allround, sniper, rusher, tracker, dodger, and the bad ones stander, jumper, spammer) | Opponents that punish bad choices: scripted styles (keeps range with rail, rushes with rockets, LG tracker, retreats when hurt, dodges) in the league and the test rooms | Every weapon gives the same kills per minute against the current target |
| B-45 | P2 | open | Pro-demo position prior: where pros stand and which weapon they hold by distance, from the 374 parsed demos (positions need no key inference); use as a benchmark first, as a small reward only if needed | B-30, B-09 |
| B-46 | P2 | open | Suite rooms for these: route times against a reference, speed in normal rounds, share of fights from higher ground, big-item share over a full duel, weapon by distance against opponents that fight back | B-35 |

## New inputs and rules (owner 2026-10-04: all high and medium inputs, round-level memory, crouch, walk, fall damage, true hitbox)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-47 | P1 | in training (`duel_gru_v4`) | New inputs (311 total): clock and score, all item types (several per kind), sounds (pickups, weapon fire, jumps, teleports), map position and identity, view / up / long rays, enemy weapon and facing, damage dealt estimate, hit feedback, nearest teleporter and jump pad | He could not see these; positioning and decisions depend on them |
| B-48 | P1 | in training (`duel_gru_v4`) | Memory kept across deaths for the whole round; longer training sequences (6.4 s) and horizon (gamma 0.998) | Stack and item timers must survive a death |
| B-49 | P1 | in training (`duel_gru_v4`) | Crouch and walk (walking is silent), fall damage (Quake 3 rule: 5 / 10 by landing speed) | Owner request |
| B-50 | P1 | done (outputs identical to 2e-6 before training) | Widen the `duel_gru_v3` network to the new inputs and actions without losing its skills (new inputs start at zero weight); verify on a copy | So aim is kept |
| B-51 | P1 | open | Mirror B-47 to B-49 in `plugins/duelbot.py` (sounds, clock, score, crouch, walk) so the next Bobby can be played | |
| B-52 | P2 | open | True hitbox check on the real server: rail shots at the edges of the box, standing and crouched (the simulator uses the game's 30 x 30 x 56 box, 40 high crouched; Keel's model matches it) | Owner: hitbox must be true |
| B-53 | P2 | open | Measure on the real server: how far pickups, weapon fire, jumps and teleporters are heard (simulator: 1200 units, a guess); fall damage values | New rules are unmeasured |
| B-54 | P2 | open (61-66k steps/s against 135k before the new inputs) | Simulator speed: the new rays and item inputs halve steps per second; profile and speed up | Smoke test 9.5k vs 18.9k steps/s in one process |
| B-55 | P2 | open | Test rooms for the new abilities: item timing (back at mega when it respawns), sound (enemy takes an item out of sight: does he react), memory across a death (returns to the fight or the item), fall damage per minute, crouch and walk use, high-ground fights | Owner request |
| B-56 | P3 | flagged | Not true to the game yet: short rounds, items reset at round start, spawning with every weapon, close respawns. Kept for now to coax out the behavior; move to real duel rules later (B-42) | Owner 2026-10-04 |

| B-57 | P1 | done (RESULTS 2026-10-04 16:30) | Lab-map rooms in the simulator suite, and the human-aim limits and new inputs mirrored in `plugins/duelbot.py` (acquisition delay, hand noise, reload jitter, sounds, clock, crouch, walk) | Needed to compare cards and to play the next Bobby |
| B-58 | P1 | in training (`duel_gru_v4`) | Human aim limits: 200 ms acquisition, 50 ms tracking, flick cap, hand noise, reload jitter, fire-button cost | Owner play test 2026-10-04: aim superhuman |
| B-59 | P1 | in training (`duel_gru_v4`): 40% random weapons, 20% duel spawn, 20% all, 20% same single weapon; damage taken weighs double | Random 1-2 weapon loadouts per player (60%), real duel spawn (20%), all weapons (20%); two-sided damage reward | Owner play test: shotgun only, takes every fight |
| B-60 | P2 | open | Tune the aim limits from the owner's test-suite card (human baseline per room) | Owner 2026-10-04 |
| B-61 | P2 | open | Community release, after the next run: two rented servers (play Bobby / test chamber), hardened for strangers (restart policy, queue, command limits, privacy notice) | Owner 2026-10-04: hold until Bobby is decent |
| B-62 | P2 | open | Videos for the post: first-person clip of Bobby playing, and of the strafe jumping he learned | Owner 2026-10-04 |
| B-63 | P2 | open | "How to help" page: connect, play, run the test chamber, leave notes; what is recorded | Owner 2026-10-04 |
| B-64 | P1 | open | Results for players: after the test chamber a player sees their own card, Bobby's, and the average of all players, in game (`!card`) and on a results page updated per run | Owner 2026-10-04 |
| B-65 | P3 | open | Check whether a Quake Live client downloads `testlab` from the server; if not, publish it on the Steam Workshop | Owner believes clients can download it |

| B-66 | P3 | dropped | Trick-jump stations on the test map (copies of four spots from the real maps) | Owner 2026-10-04: not clear what they test. Removed from the map and the suite; the copy tool stays in `tools/make_lab_map.py` |

| B-67 | P1 | open | Aim style, not only hit rate: time from reload to the next shot, crosshair angle at the shot, trigger holding, flick speed; from the per-frame logs for humans and from the simulator for Bobby | Owner 2026-10-04 |
| B-68 | P1 | partly in training (`duel_gru_v4`: speed, slalom, ramps and the lab aim rooms; the other courses wait for the owner's review) | Lab rooms in training: courses and lab aim rooms as round types (after the owner has reviewed the rooms); aim box distances that suit LG | Owner 2026-10-04; first lab card |
| B-69 | P2 | scoped (HOSTING.md) | Hosting: start with one machine in central US, dedicated core (the game locks the tick rate at 40, so quality comes from hardware and network); Europe and US west later | Owner 2026-10-04: public sooner |

## Next training batch (owner 2026-10-04: all of these go in together, with one widening of the network)

| ID | P | Status | Item | Why / evidence |
|---|---|---|---|---|
| B-70 | P1 | next | Beam inputs: the last rail trail seen (start, end, fading over a second) and the enemy's LG beam direction while in view | A trail shows where a shot came from; he sees neither |
| B-71 | P1 | next | Heard weapon fire says which weapon it was | People tell a rail from a rocket launcher by ear |
| B-72 | P1 | next (the atlas it reads from is built: ATLAS.md) | Map atlas inputs, computed per map from the route graph: route time and first-step direction to each big item (for him and from the enemy's last known position), how exposed his spot is, direction to cover, height relative to the enemy, direction to higher ground | The map lives only in the weights: slow to learn, not inspectable, does not carry to a new map (lab card: aim 3-5% on an unseen map) |
| B-75 | P1 | atlas files built with pro-seeded routes (ATLAS.md, 2026-10-04); learning the preferences is next | Atlas routes: for each big item, several distinct viable routes (not only the shortest), each with its time, first step, exposure along the way and a preference that is **learned**: seeded from how often pro demos take it, then updated from Bobby's own results (arrived, time, damage taken on the way). Stored per map in the atlas file, so it can be inspected | Owner 2026-10-04: there are usually many viable routes; they should be learned, even if seeded from pro play |
| B-73 | P2 | open | Value map per map stored outside the network (how good each spot is in a given situation), filled from pro demos and public sessions, with a planner on top of the current network | The durable answer to "know the map inside out"; after B-72 |
| B-74 | P3 | open | Local top-down picture of the surroundings read by a small image network | Only if B-72 and B-73 leave a gap |

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
| B-76 | P1 | in training (`duel_gru_v4`, 2026-10-04 night) | Pro demos as training data: converter (inputs + inferred keys and mouse), imitation loss in the trainer, all demos of the three maps downloaded to the demo drive | Movement in fights is his weakest point; full-weight imitation of every head destroys aim (RESULTS 2026-10-04 21:12), so: movement heads only until the demo inputs carry enemy health, sounds and hit feedback |
| B-77 | P2 | open | Test room: air control on a speed booster pad and on large jump pads (steer in the air to land on a chosen spot) | Owner 2026-10-04; common on duel maps, not covered by `pads` |
| B-78 | P1 | in training (2026-10-04 night) | Items room, 1-health drops and the newer courses in the simulator's lab mode; spawn weapons only from the map; real duel spawn in half of the duels; no shotgun at spawn | Owner 2026-10-04 |
| B-79 | P2 | open | Demo data: add enemy health (from damage events), sounds and hit feedback to the converted inputs, then try imitating mouse and trigger again | The reason the mouse cannot be imitated today |
| B-80 | P2 | open | Test map cleanup at the next rebuild: remove the unused peek room; `dodge` turret in the simulator | |
| B-81 | P1 | built in the simulator, not in training, no server room yet (RESULTS 2026-10-04 night, 01:50) | Run-and-gun: a test room and a training round where aiming only counts while moving (for example targets along a course, or an aim room where damage is scored by the shooter's own speed), so that speed and aim are learned together | Owner 2026-10-04: after the demo loss he moves fast but his aim error in view doubled; aim alone is cheap to get back, aim while moving is the skill |
| B-82 | P1 | done (2026-10-05 10:27) | Damage pays 0.005 per point (`--dmg-reward 0.005`; it had faded to 0.001) | Owner 2026-10-05 |
| B-83 | P1 | done, in training (2026-10-05 10:27) | The right hand: fire on the index finger and zoom on the middle finger, with the same kind of finger limits as the left hand | Owner 2026-10-05 |
| B-84 | P1 | done, in training (2026-10-05 10:27); the scorecard does not record zoom state yet | Zoom as an action: narrower view (with the sight limits that means tunnel vision), finer mouse and less hand shake per degree, slower turning; aim measurements have to account for it | Owner 2026-10-05: zoom should be a feature; it is not one today |
| B-85 | P1 | done (2026-10-05) | Left-hand finger model, sight limited to the field of view, fight inputs (enemy shots, reload, trails, own hand), arena self-play, `!arena` on the server | See RESULTS 2026-10-05 |
| B-86 | P1 | built and checked, not in training (2026-10-05); the owner decides at the 19:00 review | Groups of 2 to 6 players, all against all (`sim/duel_env_ffa.py`, written by `tools/make_ffa_env.py`; trainer `--env duel_env_ffa --group N`). Every player sees, hears and can hit every other; the enemy inputs describe the one he attends to; 18 more inputs for two more enemies in view | Owner 2026-10-05; RESULTS 2026-10-05 15:45 |
| B-87 | P1 | built and checked, not in training (2026-10-05) | Train in the yard with items (map `arena1`: mega, red armor, rockets, lightning, rail, healths, shards): `--map arena1`, `ARENA_ROOMS=yard`; items respawn on their timers and reset each round | Owner 2026-10-05 |
| B-88 | P1 | done (2026-10-05): the trainer, videos, Nightmare benchmark and reflex test run on the group simulator and `arena1`; `tools/push_bobby.sh <run>` puts a network (and with CODE=1 the code and maps) on the public server | The play-test server, the fight videos and the benchmarks still use `duel_env.py`: at the switch, freeze it as `duel_env_v5.py` and make `duel_env_ffa.py` the current one (widen the network 348 -> 366) | Follows B-86 |
| B-89 | P1 | done (2026-10-05): in the training log and `tools/hourly_arena1.sh`; not yet: whether he is at an item before it appears, jump pad and teleporter use | Map-knowledge numbers for the yard, in the training log and the hourly report: share of mega and red armor spawns taken and seconds after they appear, share of spawns where he is within 3 s of the item when it appears, speed between fights, jump pad and teleporter uses a minute, seconds until a weapon is picked up after a machine-gun spawn | Goal 1, point 3 |
| B-90 | P1 | (a), (b), (c) and his own focus built and in training (`duel_gru_v6`, 2026-10-05 21:03), also in the server plugin; (d), (e) held back (they hand him map knowledge) | New inputs for map knowledge (each is something a player knows or keeps in his head): (a) seconds since he last knew mega / red armor to be taken (he took it, saw it gone, or heard the pickup), kept for the full timer instead of fading after 5 s; (b) what the enemy is known to have picked up since his last death (mega, red armor, which weapons seen in his hands); (c) seconds since his own respawn and since the enemy's last known death; (d) travel time along the floor to mega, red armor and each weapon, in place of the straight-line direction only; (e) which part of the map he is in and where the enemy was last known to be (named areas: tunnel, tower, balconies, open ground) | Owner asked 2026-10-05 |
| B-91 | P1 | done (2026-10-05): run twice by the owner; RESULTS 2026-10-05 20:10 | Aim reflex test: `!reflex` on the play-test server (four rooms: lightning on a slow and on a strafing target, rail flicks, rockets) and `tools/reflex_report.py`, which works out steadiness, tracking lag, reaction to a turn, reaction and flick speed, rocket lead, for people and for Bobby in the same rooms. Purpose: set his aim limits from measured players, not by guessing | Owner 2026-10-05 |
| B-92 | P1 | started: benchmark = 20% better than the first player's last run, moving as he aims, calm and under fire (`docs/reflex_benchmark.json`); limits: direction error 1.0 deg, flinch 0.2 deg per point of damage, delay 75 ms with focus bursts (the 150 ms delay was based on a bad measure and is withdrawn); open: train under them, measure with more repeats, adjust; more players | Follows B-91; RESULTS 2026-10-05 21:45 |
| B-93 | P1 | built (2026-10-05), not trained with yet: 2 s of focus, delay 50 ms quicker while it lasts and 25 ms slower after, back at a quarter of a second a second; no input for it yet (goes in with B-90) | The aim limits are averages: he should be able to do better in short bursts, not sustained. Proposal: a focus budget like the hand's stamina: the tracking delay drops (say 150 -> 100 ms) while he spends it and it refills slowly, so the average stays at the benchmark | Owner 2026-10-05 |
| B-94 | P1 | built (2026-10-05), first values, not trained with yet: 0.06 deg of error per point of damage, at most 2.5, fading over 0.3 s; the reflex test now has a half under fire per aim type to set it from players | Being shot at costs aim: today a hit only pushes him (knockback), his view and his read of the enemy are untouched. Proposal: for about 300 ms after taking damage the error on the seen direction to the enemy grows with the damage taken (the flinch a player gets from the screen kick and flash); measurable on people with a reflex room where the target shoots back | Owner 2026-10-05 |
| B-95 | P2 | open | Watch the key budget against measured players (the owner: 4 to 7 movement-key changes a second on the courses, 7 to 19 in his busiest second; Bobby: 10 in a burst, 4 a second sustained): raise his limits if they turn out tighter than people's | Owner 2026-10-05 |
| B-96 | P1 | `duel_gru_v7` did not work for items (RESULTS 2026-10-06 07:00, ended 12:09); followed by B-100 | Out of the hiding habit of `duel_gru_v6`: pickup reward (to be faded out), damage taken at half weight, groups of 2, 3 and 4, mostly machine-gun spawns, route inputs to the big items | RESULTS 2026-10-06 07:00 |
| B-97 | P1 | done, in training (`duel_gru_v7`, 2026-10-06 07:29): pad 240 degrees wide, 125 ms lift, set from the owner's sessions; with it the hearing inputs (direction, above or below, loudness, coming or going) | A mouse pad that runs out: after about one full turn in one direction the mouse has to be lifted and set back (about 150 ms without turning). Against spinning on the spot to look around | Owner's question 2026-10-06 |
| B-98 | P2 | done (2026-10-06 08:29): the pad is linked from the floor round it | The walking map of `arena1` does not contain the jump pad to the tower (the flight is longer than the 1.2 s the builder simulates): the route input to the mega goes round by the stairs | Found 2026-10-06 |
| B-99 | P1 | 1 to 5 done (2026-10-06 08:29); 6 built behind a switch (`DENSE_VIEW=1`), untested; 7 and 8 open | Audit of the inputs: (1) walk key back, (2) lava and deadly drops in sight, (3) the enemy's last known heading, (4) where a jump pad lands, (5) his own projectiles, (6) a denser picture of the view (45 readings where there are 15), (7) the sound an item makes when it comes back, (8) spawn points | Owner 2026-10-06 |
| B-100 | P1 | in training (`duel_gru_v8`, 2026-10-06 12:16) | An explicit intention: a sixth action head (nothing / mega / red / rockets / rail / lightning), read once a second and held, fed back as an input with the way to the chosen item; the chosen way pays as he goes, the pickup pays 0.75 (never more than a frag), an enemy's mega or red costs the others half of that; a learned table of 16 numbers per 64-unit map cell (his own cell and the enemy's last known one). Logged: share of time per intention, trips reached / abandoned / ended by death | Owner 2026-10-06 ("try a model change") |
| B-101 | P3 | open; done when the duel maps return. Shotgun, grenade launcher, plasma gun put back 12:52 (owner: the main weapons must be known on every map) | Put back the inputs retired on 2026-10-06 (yellow and green armor, heavy machine gun everywhere they appeared, third health, ammo boxes, map name, 60 s clock, route directions): `sim/reshape_policy.py` carries a network over by input name, `--also` takes weights from an older network | RESULTS 2026-10-06 12:16, 12:52 |
| B-104 | P2 | design agreed with the owner 2026-10-06; after v8 shows the table matters | A map reader (stage B of map knowledge): a top-down raster of the map (walkable, heights, hazards, pads, teleporters, items, spawns; optional atlas channels from pro demos) through a small conv -> the 16 numbers per cell that the v8 table stores, computed instead of learned per map, plus a global map summary; trained end to end on many generated variants of the arena (`make_lab_map.py` parameterised: rooms, walls, item places) and the duel maps, tested on held-out maps with nothing fine-tuned. Stage C later: a live minimap (items up/down, positions, sounds) through the same conv | Owner 2026-10-06 |
| B-105 | P1 | built and tested with three Bobbys (2026-10-06 13:30); the owner reviews the plugin and plays it tonight; not on the public server yet | Free-for-all on the public server: `plugins/ffabot.py` (one six-seat group simulator built once, a seat per client, batched inputs and one network pass for all Bobbys, each driven with the training hand rules), `!bots <1-4>`, people take the seats the bots leave (6 - n), `FFA=<n>` in `tools/duel_server.sh`, the `ffa` factory | Owner 2026-10-06 |
| B-102 | P2 | option, not used | A scripted "runner" in the league: takes the mega and the red armor by the routes and fights with the stack, so that not stacking costs something in self-play. The owner wants pure self-play first; use if the intention head collapses to "nothing" | 2026-10-06 |
| B-103 | P2 | done (2026-10-06) | Where he spends his time: `tools/heatmap.py` (top view, items, deaths, how many cells hold half of his time) and the share of the time the mega and red lie untaken in the training numbers; the owner wants hot spots (held positions), not a smear | Owner 2026-10-06 |

## Dropped

| Item | Why |
|---|---|
| Settings search (coach) on top of Nightmare | Did not move win rate (6% vs control 69%); RESULTS 2026-10-02 |
| Accuracy tuner that loosened aim | Owner: never miss on purpose |
| 25 ms bot physics | Ground-strafing exploit; owner chose human physics |
| Rewriting duel logic in C | Profiling showed little gain; bigger batches gave 2.4x |

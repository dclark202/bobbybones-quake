# BobbyBones: results log

What we tried, what we measured, and what it means, **including what did not work**. Newest first. Each
entry names the backlog items it settles or raises ([BACKLOG.md](BACKLOG.md), `B-nn`); the plan is in
[PLAN.md](PLAN.md); log formats are in [LOGS.md](LOGS.md). Numbers are from local runs; raw data lives in
the git-ignored `data/` folder (paths given so results can be re-checked).

## At a glance

| Worked | Did not work |
|---

## 2026-10-03 (23:15): `duel_gru_v3` at 149 minutes, two simulator defects fixed mid-run

Raises B-37, B-38. The run was stopped and resumed from its checkpoint twice (about 10 minutes lost);
`policy_before_switchfix.pt` is the checkpoint from before the fixes.

At 149 minutes: crosshair error in view 8.7 degrees (38 at the start), on target 66% of the time in view,
LG 28% and rail 29% hit rate, 2.4 frags to 1.3 deaths per minute against the scripted fighter, 70% kill share
against older snapshots, movement rounds 293 u/s. But: shotgun held 88-95% of the time at every range and
84% of frags, and switches back up to 144 per minute.

Defects found:
1. **Switching during a reload was free.** In the game a weapon change only starts once the reload from the
   last shot is over; the simulator let the 0.425 s switch run inside the reload, so flicking weapons after a
   shotgun or rail shot cost nothing. Fixed: the switch now waits for the reload (`fire_cd`). Not yet
   measured on the real server for the firing case (B-37); it follows the Quake 3 rule.
2. **The round mix was a share of round starts, not of playing time.** Normal rounds last about 100 s and the
   others 10-15 s, so about 86% of playing time was normal rounds and aim rounds got about 6%, not 25%.
   Fixed: `kind_p` is now the share of time.

Not changed (decision for the owner, B-38): the spawn loadout gives 10 shells but only 60 cells and 5 slugs,
so the shotgun carries the most damage per spawn (about 1000 potential against 360 for LG). The shotgun
preference may be a rational answer to those arbitrary amounts. Real pickup amounts are still unmeasured (B-14).

---

## 2026-10-03 (night): test suite v1 and live rooms

Settles B-32, B-33; B-34 built. Raises B-35, B-36.

- `sim/test_suite.py`: fixed rooms and seeds for any checkpoint (aim per weapon against still / slow / fast /
  jumping targets and at three distances, weapon choice by range, movement, solo, scripted-fighter ladder).
  First card: `duel_gru_v3` at 5 minutes of training (near-random; the baseline to improve on).
- The same rooms run on the play-test server with a person as the subject (`!room ...`, `!room suite`).
  Dry run with a Nightmare bot standing in as the subject: LG 76% on a still target and 30% on a fast strafe,
  rail 14% of slugs on a still target, rockets 90% still / 62% fast (direct or splash).
- Bugs found and fixed in the dry run: target damage was dropped on the frame it was healed; healing a dead
  target left it stuck; aborting the match with two bots looped (warmup is now only held for a human).
- New hook function `minqlx.set_view()` turns a player's view (used to face the subject toward the target).
- `duel_gru_v3` at 31 minutes: 133k steps/s; switches 28 per minute (387 at the start); movement rounds
  271 u/s with 10.7% fast-air and 6.8 arrivals per minute; crosshair error in view 27 degrees (38 at start);
  megas 0.34 and red armors 0.51 per player-minute. Watch item: he holds the shotgun 87-97% of the time in
  normal rounds (it forgives bad aim).

---

## 2026-10-03 (night): first human play test, and what changed for `duel_gru_v3`

Settles B-08. Raises B-28 to B-34.

**Play test** (owner vs `duel_gru_v2`, 28 minutes, three maps; `data/duellive/sessions/*_human`): owner 54,
Bobby 14.

| Owner's note | Measured in the session logs | Cause in training |
|---|---|---|
| Switches weapons constantly | 33-75 switches per minute (normal loadout) | Switch cost was a guessed 0.1 s |
| Spams, runs dry, then does not shoot | Fire held 74-80% of frames with the enemy in view, 38-42% with nobody in view | Endless ammo in drills, endless machine gun |
| Odd weapon priority | Under 300 units: rail 50-56%, rockets 13-25% | 75% single-weapon rounds |
| Cannot track a slow strafe | Median crosshair error 6 degrees while in view; within 3 degrees 20-25% of frames | 150 ms delay, coarse smoothed turns |
| Jumps constantly, no speed | Jump key 30% of frames (owner 7%); above 330 u/s 5% (owner 37-46%) | Nothing rewards speed; nobody punishes jumping |
| Low ground, odd spots, stuck at a teleporter | Below the owner ~50% of the time | 15 s rounds |
| Rarely picks up health or armor | Big items: owner ~75, Bobby 14 | Tiny item bonus, short rounds |

His crosshair was within 3 degrees more often than the owner's (20-25% vs 5-18%): aim is undersold by the
spam, as the owner noted. Play-test bugs seen: a real match could start and the map then rotated out of the
pool; session folders could carry the wrong map label.

**Weapon switch time measured** (`plugins/weaponlab.py` set 3, `data/weaponlab4/`): from the switch command
to the first shot is 17 frames = 0.425 s for every pair tested (the held weapon changes after 10 frames).
The simulator had 0.1 s.

**Changes in the simulator for `duel_gru_v3`** (`sim/duel_env.py`, 171 inputs):
- Switch time 0.425 s and a 0.002 cost per switch; ammo finite in every round; 0.0005 per frame for holding
  fire when no enemy was seen for over a second; item bonus 0.3 per 100 points; reaction delay 25 ms.
- Aim: turn steps down to 0.03 degrees per frame, lighter smoothing for commands up to 1 degree, and the
  pull toward level only applies when no enemy is in view (a pure cost was not tried: 0.99 collapsed before).
- Round kinds: 45% normal (all weapons at spawn), 25% aim rounds against a scripted strafing target
  (LG-weighted), 15% one-weapon rounds, 15% movement rounds (run to mega / red / yellow armor).
- 20% of normal rounds are against a scripted fighter (turns onto the enemy, rockets close / LG mid / rail far).
- Scripted players are not trained on and not counted in the accuracy numbers.
- New metrics: accuracy and crosshair error while the enemy is in view, switches per minute, blind fire,
  weapon held by distance, movement-round speed and arrivals, results against the scripted fighter.
- Smoke run (7 minutes): 134k steps per second; switches, blind fire and crosshair error falling, movement
  arrivals and speed rising. Results of the full run go in the next entry.

---|---|
| Simulator physics match the real game; learned movement transfers (time ratio 1.01) | Settings search (coach) on top of Nightmare: 6% win rate vs control 69% |
| Strafe jumping emerged from reward alone (human physics) | Our own routing/movement on top of Nightmare: 0/108 |
| Nine weapons measured on a real server and reproduced | Recorded nav graphs (17% junk nodes) |
| Rail flicks and three-weapon use after the aim-input fix and drills | 25 ms bot physics (learned a ground-strafing exploit) |
| A simulator-trained duel policy runs on the real server | Self-play before the aim-input fix: rockets only |
| | `duel_gru_v2` vs Nightmare: 0-10; LG tracking stuck at 4-5%; weapon choice random |

---

## 2026-10-03 (evening): first GRU self-play run with memory (`duel_gru_v2`) and first live duel

Settles B-106, B-108. Raises B-01 to B-07.

**Training** (`data/sim_runs/duel_gru_v2/`, 272 minutes, 2.48 billion steps, ~152k steps/s, three maps,
RL/RG/LG/MG, 75% single-weapon drill rounds, 150 ms reaction delay, simulator `sim/duel_env_v2.py`):

| | 102 min | 219 min | 272 min (end) |
|---|---|---|---|
| Rail hit rate | 8-9% | 20% | 17-20% |
| Rocket hit rate | 4% | 6-7% | 8-10% |
| LG hit rate | 4% | 5% | 4-5% |
| Frags by weapon (RL / RG / LG) | 26 / 41 / 33% | 22 / 48 / 30% | 21 / 46 / 33% |
| Enemy visible | 6% | 8% | 7% |
| Megas / red armors per player-minute | 0.13 / 0.16 | 0.27 / 0.20 | 0.24 / 0.15 |
| Suicides per match-minute | 0.1-0.2 | 0.06-0.07 | 0.05-0.06 |
| Kill share vs older snapshots | 55-71% | 56-63% | 49-57% |
| Fast-air share (strafe jumping) | ~2% | 2% | 2% |

- Worked: rail flicks learned on their own; all three main weapons score frags; fewer suicides.
- Did not work: LG tracking never moved; no strafe jumping; item control low; improvement against its own
  past versions had nearly stopped by the end.

**Live port** (`plugins/duelbot.py`, `sim/export_duel.py`, `tools/duel_server.sh`): the policy's inputs are
rebuilt on the real server by the simulator's own `observe()` (positions, health, weapons, ammo, the
opponent's rockets, item states), the network runs in numpy, and Bobby is driven with human physics.
- A server crash was found and fixed: with human physics the bot flag was dropped for good, and the server
  crashed ("netchan queue is not properly initialized") as soon as a second player joined. The flag is now
  restored after every game frame (`Botctl_AfterFrame`).
- New hook function `minqlx.missiles()` lists projectiles in flight.

**Live vs Nightmare, Blood Run** (`data/duellive/duel_live_test2.jsonl`, `data/duellive/spar/`):

| Setting | Minutes | Frags Bobby - Nightmare | Damage dealt / taken |
|---|---|---|---|
| Normal loadout | 5 | 0 - 10 | 560 / 1162 |
| LG-only drill | 2 | 2 - 6 (cumulative with ~1 min normal) | 750 / 638 |

- All 560 damage in the normal loadout was rail hits (7 x 80). LG and rockets did nothing.
- He holds each of the four weapons about 25% of the time, the machine gun included: weapon choice was
  never learned, because in 75% of training rounds there was only one weapon (B-04).
- He holds fire about half the time with the enemy on screen 6-20% of the time (B-05).
- In LG-only rounds he out-damaged Nightmare, so the simulator's aim does carry over; the normal-loadout
  loss is mostly weapon choice.
- Not measured yet: a human opponent (first play-test session planned the same evening, B-08).

**Read on the 150 ms reaction delay** (B-03): fair for reacting to something new, but it is applied to all
enemy information, including smooth tracking, where people predict and show almost no lag. At strafing speed
the target moves ~48 units in 150 ms, more than a body width. Plan: curriculum from 50 ms to 125 ms.

---

## 2026-10-03 (afternoon): aiming fixed, weapon drills, all nine weapons measured and simulated

**Why self-play only ever used rockets** (`duel_v1`, `duel_v2`, first GRU run: 98-100% of frags):
1. A structural defect in the inputs: the 150 ms reaction delay was applied to the whole "angle from crosshair to
   enemy" reading, so the player saw the effect of its own mouse movement 6 frames late. Fixed: only the
   opponent's state (position, velocity, visible or not) is delayed; the player's own view is current.
2. No direct reading of the reticle-to-enemy distance. Added: coarse (+-15 deg) and fine (+-2 deg) offsets on both
   axes, a "crosshair is on the enemy" flag, and the target's apparent size.
3. Nothing forced practice with rail/LG. Added: weapon drill rounds (both players have exactly one weapon).
Result (`duel_gru_v2`, 75% drill rounds over RL/RG/LG, 19 minutes in): rail hit rate 0.3% -> 12%, LG 0.2% -> 9%,
frags by weapon rockets 47% / LG 31% / rail 22%, 5.3 frags per match-minute.
Also learned the hard way: weakening the view's pull toward level from 5% to 1% per frame made the pitch drift to
floor/sky again and players stopped seeing each other (3% visible); reverted.

**Remaining weapons measured on a real server** (`plugins/weaponlab.py`, WEAPONLAB_SET=2, `data/weaponlab3/`):

| Weapon | Real Quake Live | Simulator |
|---|---|---|
| Machine gun (starting weapon) | 5 per 100 ms, 10 u/s knockback per hit | same |
| Heavy machine gun | 8 per 75 ms, 25 u/s per hit | same |
| Shotgun | 100 at 100 units, 60 at 300, 25 at 600; knockback 415 / 254 / 106 | 20 pellets x 5, gaussian spread 3 deg (expected 100 / 61 / 23) |
| Plasma | 20 per hit every 100 ms, 2000 u/s (first hit frame 9 at 400 units, 17 at 800), 110 u/s knockback; splash 16 / 16 / 10 / 3 at 0 / 10 / 20 / 30 units; at own feet 7-9 damage, 95 u/s lift | same timing; splash 16 / 16 / 10 / 3; own feet 8, 98 u/s |
| Grenades | 100 direct at 150 units (frame 9, 542 u/s knockback), 2.5 s fuse, own feet 44 damage / 277 u/s lift | direct 100, frame 9, 544; own feet 53 / 650 (NOT matched: bounce before the fuse) |
| Gauntlet | 50 per ~425 ms, hits at 40 units, not at 70; 219 u/s | same |

Model changes from these: plasma moves on the frame it appears (rockets and grenades do not); grenades get Quake's
loft (+0.2 on the forward z); splash knockback = 5 u/s x splash damage x 1.07 on others, x 1.3 on yourself (fits
rockets 450 / 549 and plasma 80 / 95); refire timer rounding fixed (machine guns were firing 20% slow).
Bug found by a smoke test: a projectile at rest (grenade on the floor) counted as a direct hit on the opponent
anywhere (zero-length segment in the hit test). Fixed in `sim/duel_env.py`; the frozen `duel_env_v2.py` used by
the running job only has it for exactly axis-parallel or zero-length shots.

## 2026-10-03 (afternoon): weapons checked against real Quake Live

Method: `plugins/weaponlab.py` puts two fully controlled bots on a 1,408-unit flat stretch of Campgrounds and
fires controlled setups (4 repetitions; the first of each is discarded as a setup glitch), logging health and
velocity every frame. `sim/validate_weapons.py` replays the identical setup in the duel simulator.
Data: `data/weaponlab/`, `data/weaponlab2/`. Real damage includes ~1 point of health decay (tests start at 200 hp).

| Test | Real: damage / hit frame / knockback (horizontal, vertical) | Simulator after fixes |
|---|---|---|
| Rocket at the body, 400 units | 100 / 17 / 449, -24 | 100 / 17 / 449, -25 |
| Rocket at the body, 800 units | 101 / 33 / 450, -12 | 100 / 33 / 450, -12 |
| Rocket at own feet (rocket jump) | 42-43 self damage, 549 u/s up | 42, 550 |
| Rocket at the floor 0 / 20 / 40 / 60 / 80 / 100 / 120 / 140 units in front | 85 / 81 / 64 / 46 / 38 / 23 / 8 / 0 | 84 / 78 / 63 / 47 / 37 / 23 / 10 / 0 |
| ...same, knockback (h, v) at 20 / 60 / 100 | (167, 391) / (196, 138) / (104, 49) | (181, 382) / (208, 145) / (116, 54) |
| Railgun, 1000 units | 80 / frame 2 / 340, 0 | 80 / 2 / 340, -7 |
| Lightning gun | 6 per 50 ms (120/s), 35 u/s per tick, hits at 700, misses at 800+ | same (range 768) |

What the real game does (now in `sim/duel_env.py`):
- A shot leaves one frame (25 ms) after the fire command; a rocket does not move on the frame it appears.
- Rocket speed 1000 u/s. Direct hit 100 damage. Splash: 84 damage and "100 points" of knockback, both falling
  off linearly to zero at 120 units; the falloff sits ~20 units closer to the target than the plain
  distance-to-hitbox (calibrated constant).
- Knockback = 5 u/s per point, times 0.9 on other players (direct hit: 450 u/s), times 1.1 on yourself (rocket
  at your feet: 550 u/s up); splash pushes upward (Quake 3's +24 on the direction). Own splash damage is halved.
- Railgun 80 damage, knockback factor 0.85 (340 u/s). Lightning gun 6 damage per 50 ms, range 768, ~35 u/s per tick.

Wrong in the first-pass simulator (and so in the `duel_v1` run): no firing delay, rockets moved on the spawn
frame, splash knockback mostly sideways instead of up, one knockback factor (1.1) for everything, splash ~20
units too short, LG knockback too weak. `duel_v1` should be retrained on the corrected simulator.

Not yet measured: weapon switch time, damage through armor, shotgun/grenades/plasma/MG/HMG, air targets.

## 2026-10-03: duel simulator, first self-play run (`duel_v1`)

Setup: `sim/duel_env.py` (2 players per match, RL/RG/LG with infinite ammo, QL damage/splash/knockback,
half self-damage, 125 hp, no items), 150 ms reaction delay on everything a player knows about the opponent,
110° field of view + hearing within 800 units. One policy plays both sides. 117 min, 284 million steps,
3,072 players on Blood Run. Curriculum: respawn near the opponent (100% → 20% over 60 min), short rounds
(15 s → 120 s).

Problems fixed on the way (short runs): view pitch drifted to ±89° so players never saw each other (fix: the
view eases back toward level); players learned to hide because being seen = being shot (fix: reward damage
dealt, not penalize damage taken, as curriculum shaping); players drifted apart with no respawns (fix: short
rounds that restart both players near each other).

Results (eval at normal spawns, 90 s x 64 matches, `sim/eval_duel.py`):

| | Self-play | vs random policy | vs standing dummy |
|---|---|---|---|
| Kills per match-minute | 0.61 | 0.73 (0 deaths) | 0.54 |
| Rocket hit rate (direct + splash) | 21% | 9% | 14% |
| Rail / LG hit rate | ~0 (unused) | ~0 | ~0 |
| Sideways speed with a rocket incoming vs otherwise | 201 vs 128 u/s | 179 vs 103 | — |
| Shots fired just after losing sight (prefire) | 7% | 4% | 1% |
| Rocket jumps per player-minute | 0.18 | 0.07 | 0.03 |
| Fast airborne (strafe jumping) share | 3.7% | 2.3% | 1.5% |

Training curve: rocket hit rate 7% → 28% while players spawned close, ~20% at normal spawns; suicides fell to
~0.1 per match-minute.

What it means:
- It learned to aim and lead rockets (splash-heavy), to dodge sideways under fire, some prefire and occasional
  rocket jumps. It beats a random policy without dying.
- It is weak at finding the opponent (0.54 kills/min against a dummy that never moves): no memory, no map
  knowledge in its inputs.
- It never learned rail or LG (coarse turn steps can't aim them; rockets always available) and doesn't strafe
  jump in fights (trained from scratch, not from the movement policy).
- Weapons/damage in the simulator are not yet checked against the real game, and no live duel test yet.

## 2026-10-03 (morning): simulator-built nav graphs, one policy on three maps, live on all three

**Nav graphs built by the simulator** (`sim/build_nav.py`, ~10 s per map): standing spots found by dropping
a player box on a 48-unit grid; walk links and run/jump/drop/jump-pad/teleport links all verified by
simulated movement (human physics).

| Map | Spots | Walk / jump-drop / teleport links | Spots that can reach the goal items |
|---|---|---|---|
| Blood Run | 1,185 | 6,857 / 11,633 / 49 | 97% |
| Aerowalk | 906 | 5,259 / 7,871 / 174 | 65% (platforms over the void; some need jumps a standing start can't make) |
| Campgrounds | 1,643 | 9,950 / 15,120 / 0 | 92% |

Blood Run route estimates are 13% longer than the recorded graph's (no rocket-jump shortcuts, standing starts).

**One movement policy, three maps** (`multimap_v1`, started from the Blood Run policy, 90 min, 4 workers per map,
simulator nav graphs): success 74% → 96% (Blood Run 99.7%, Campgrounds 97%, Aerowalk 94%), trip time vs a
perfect runner 0.86 → 0.83 (faster than the single-map policy). No falls on any map.

**Live (real QL server, human physics, `plugins/movetest.py`, 3 servers in parallel):**

| Map | Live arrived | Simulator success | Live / simulator time |
|---|---|---|---|
| Blood Run | 72/72 | 100% | 1.01 (p10 0.95, p90 1.10) |
| Campgrounds | ~26/30 | 82% | 1.07 |
| Aerowalk | 28/42 (67%) | 82% | 1.05 (p90 1.35) |

- Aerowalk live failures (14/42) were all 20 s timeouts, no deaths. 7 of those trips also fail in the
  simulator (mostly to the Red Armor, which the simulator-built graph can't reach from a standing start: needs
  a running jump or rocket jump). The other 7 fail only live (stuck/wandering): a real but smaller transfer gap
  (~17% of Aerowalk trips). Aerowalk has no hurt triggers; falling into the void ends a trip in both.
- A test server once loaded the map but ran no game frames until restarted (no players yet). Same symptom as
  the public server's "hang" on 2026-10-02. Workaround: restart; to investigate (QL idle behaviour?).

## 2026-10-03: learned strafe jumping transfers to real Quake Live

**Result.** A movement policy trained only in the simulator (`sim/`) completes item-to-item trips on a
real Quake Live server as fast as it does in the simulator.

| Live test, Blood Run, 1 run per trip | Human physics (8/8/9 ms) | Bot physics (25 ms) |
|---|---|---|
| Trips arrived | 73/73 | 72/72 |
| Live time / simulator time (median) | **1.01** (p10 0.97, p90 1.13) | 1.09 |
| Faster than Nightmare's real median trip | 24/24 | 24/24 |
| Median top speed | 534 u/s | 507 u/s |

Examples (live vs Nightmare's real median): MH→LG 1.45 s vs 8.7 s, MH→RG 2.3 s vs 7.0 s, SG→RA 1.25 s vs 2.5 s.
Nightmare's numbers come from training-server trips and include its detours, so the true gap is smaller.

- How: `plugins/movetest.py` drives Bobby with the exported policy (`sim/export_policy.py`), using the same
  observation code as training (simulator compiled into the server image for wall/floor rays).
  Comparison: `sim/compare_live.py`. Data: `data/movetest/`.
- Human physics on the server: the C hook (`minqlx/botctl.c`, `set_bot_substeps`) splits each 25 ms
  command into 8/8/9 ms moves and clears the bot flag so the game moves each one (Q3/QL move bots once per
  frame otherwise). Live velocities match the simulator's human physics (p90 error 1.3 u/s vs 13.8 for
  25 ms physics).
- Harness bugs found on the way: the plugin kept commanding the old view after teleporters (the game turns
  the view; fixed by reading `view_angles` every frame); numpy booleans broke the JSON log.

## 2026-10-03: overnight training, human physics: strafe jumping emerged

- Run `bloodrun_human_v1`: 10 h, 1.93 billion steps, PPO, 3,072 players, human (125 fps) physics.
- Nothing about strafe jumping is coded. Reward = time saved toward the goal item.
- Signature in the policy: forward + strafe, view held 8-15° off the velocity, sides alternating, short
  jump taps on landing; speed grows while airborne (e.g. 380 → 530 u/s in one hop sequence).
- Eval vs 1-hour run: chained hops above 330 u/s 0 → 804, fast airborne time 17% → 47%, vmax 510 → 855.
- Learning curve: trip time vs a perfect runner 0.97 → 0.90 by hour 2, then ~1%/h, 0.86 at hour 10.
  Plateau on this setup.

## 2026-10-02/03: frame-rate exploit found by the first policy (and ruled out)

- The first policy (`bloodrun_v1`, 1 h, 25 ms physics) learned **ground strafing** at 370-385 u/s without
  jumping: forward + strafe with the view ~40° off the velocity, so acceleration beats friction each frame.
- It only works with 25 ms physics frames (bots at 40 Hz). A 125 fps human gets a sliver of it.
- Owner decision: train with human physics only (`substeps=(8,8,9)`), so Bobby can't use bot-only physics.

## 2026-10-02/03: simulator fidelity

- Simulator = ioquake3 Pmove + collision (vendored in `sim/q3/`) with Quake Live's settings (jump 275,
  auto-hop; chain jump off), real map files (IBSP 47), jump pads and teleporters. ~740k player steps/s per core.
- Checked against ~20,000 recorded frames of two Nightmare bots on a real QL server (`sim/validate.py`):
  one-step error 0 units (p95), velocity 0.6 u/s (= recording rounding); 0.5 s open-loop replays within
  0.5 units for 90%; 2 s within 8.4 units for 90%.
- `pmove_ChainJump 1` does **not** mean "+110 within 500 ms": real jumps 200 ms apart got 275.
- The engine's `lastUsercmd` is stale for bots; `minqlx.ran_usercmd` (new) returns the command a think
  actually ran. Recordings now log exact inputs (`inputs_<map>.txt`), also for humans (last command of the
  frame).

## 2026-10-03: recorded nav graphs are partly junk

- 389 of 2,320 points in Blood Run's recorded graph (17%) are outside the playable map (a whole phantom
  corridor north of the map, from old recordings); 196 more are mid-air jump points.
- Spawning players there caused all "falls off the map" (17% of training trips) and many stalls.
- Filtering with the map's own data (leaf cluster = -1 outside the map; floor under spawn points):
  success 82% → 100%, falls 17% → 0%. Speed unchanged (0.866 of run-speed time).

## 2026-10-02: settings search (coach) on Nightmare + fair aim: no needle moved

- Since 09:30, 572 matches: Bobby (old aim) 6% win rate vs control (plain Nightmare) 69%.
- The coach (cross-entropy method over ~14 settings) found nothing real: most generations had ~3 matches
  per candidate (best-of-N luck); with 5 trainers per candidate the best had a 6% win rate at n >= 10.
- Root causes: the old accuracy tuner deliberately loosened LG aim up to 3x when Bobby hit > 40% (removed);
  weapon choice used rockets very little (120 rockets vs ~12,900 LG cells across trainers).
- After the aim fix, 4 aerowalk test matches were all wins (20-4, 11-8, 8-4, 7-3). Too small to call.
- Nightly settings-search runs paused in favor of learning (this log's newer entries).

## Earlier (2026-10-01/02, see git history and CLAUDE.md)

- Item-route-first design lost 108/108 vs Nightmare. Split test: our movement and our decisions lost
  badly; Nightmare movement + our fair aim was the best of our variants but still far below control.

## Data sources

- Demos: 380 recent (.dm_91, 2024-2026) duel demos from demos.quakelive.ru: Blood Run 226, Aerowalk 148,
  Campgrounds 6 (`tools/fetch_demos.py`, `data/demos/`). Older eras (dm_73, 2009-2013) and
  quakehistory.com (292 curated 2012-13 POV duels; robots.txt blocks its download folder) not used yet.

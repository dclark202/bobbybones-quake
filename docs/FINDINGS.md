# BobbyBones: findings log

What we tried, what we measured, and what it means. Newest first. Numbers are from local runs; raw data
lives in the git-ignored `data/` folder (paths given so results can be re-checked).

---

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

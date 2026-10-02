# ql-bot: feasibility report (step 1 probe)

**Bottom line:** controlling a bot on a real Quake Live dedicated server works. A small patch to minqlx lets Python set a bot's movement, aim, jump, fire and weapon on every server frame. The physics are exactly what a human gets: the bot strafe-jumps to 600+ ups and hits 8/8 rails on a stationary target. Everything below runs in Docker on this PC.

## What was built

| Piece | Where | What it does |
|---|---|---|
| Docker image | `Dockerfile`, `entrypoint.sh` | QL dedicated server (Steam app 349090) + minqlx built from source, private lab config |
| minqlx patch | `minqlx/botctl.c` (+ small hooks in `dllmain.c`, `hooks.c`, `python_embed.c`) | Hooks the engine's `SV_ClientThink` so a bot's per-frame input (usercmd) can be overridden from Python. Adds `set_bot_input`, `clear_bot_input`, `view_angles`, `last_usercmd`, `item_states` |
| Probe plugin | `plugins/botctl.py` | `!probe`, `!drive <id> test/strafe/aim/air*`, `!range`, `!items`, `!record` |
| Self-training plugin | `plugins/jumplab.py` | Bot learns the campgrounds bridge-to-rail jump by trial and error (cross-entropy method) |
| Tools | `tools/rcon.py`, `tools/stats.py`, `tools/plotmap.py`, `tools/plotjump.py`, `tools/animate.py` | Remote console, stats feed, map/attempt plots, progress video |

## Probe results

| Capability | Result | Evidence |
|---|---|---|
| Server + minqlx in Docker | ✅ Works | Starts in ~10 s; minqlx finds all engine functions |
| Read state (position, velocity, health, armor, weapons, ammo, view angles) | ✅ Works | Built-in minqlx, plus `view_angles` added |
| **Drive a bot's inputs** | ✅ Works | Stand, turn to an exact yaw, run at 320 ups, jump, strafe, fire, all from Python |
| Strafe jumping | ✅ Works | Air acceleration identical to a human: 320 → 356 ups within one jump, 605 ups peak in training |
| Aim + fire | ✅ Works | Railgun at a stationary target 258 units away: 8 shots, 8 hits (80 dmg each) |
| Item timing | ✅ Works | `item_states()` gives every item, whether it's up, and exact respawn time ("RA back in 21.9 s") |
| Stats feed (for coaching) | ✅ Works | Kill events include both players' position, view angles, HP/armor, weapon, speed, airborne flag |
| Map knowledge | ✅ Workable | Built a floor map of campgrounds from 22k recorded bot positions (`data/campgrounds_map.png`) |
| Self-learning a movement trick | 🟡 In progress | See below |

## Gotchas found along the way
- **Holding jump in the air kills air acceleration.** Quake's movement math counts the jump key, which caps wish speed at about 261 ups. Only press jump on the ground (that's why real players hop rather than hold).
- **Input latency:** commands set in the frame hook reach the bot about 2 server frames (50 ms) later. Fine for strategy, slightly costly for frame-perfect strafing. Fix: run the low-level controller inside the C hook, or predict ahead (being tested as the `lead` parameter).
- **Bots think at 40 Hz** (`sv_fps 40`), humans send input at up to 125 Hz. That's coarser aim and strafe steps than a human, but it's the same rate the server simulates at.
- Ground detection must tolerate tiny non-zero vertical speeds on some floors.
- Plain minqlx has no damage event; hits were measured from health deltas (a `G_Damage` hook would be easy to add).
- Server output is block-buffered, so `docker logs` lags; read the plugin's own log files instead.

## How doable is the rest?

| Goal | Verdict | Notes |
|---|---|---|
| Strafe jumping around a map | **Doable now** | Physics solved. Needs a route planner on the recorded floor map plus wall avoidance. A trace/collision call into the engine would make it robust (moderate C work) |
| Rocket use (feet aim, prediction, splash) | **Doable** | Aim pipeline proven. Prediction is maths on positions/velocities we already read |
| Rail/LG aim with human-like error | **Doable** | Perfect aim is trivial; the work is making it *believable* (reaction time, tracking error) |
| Item timing | **Doable now** | Exact timers available. For fairness, only let the bot "know" pickups it saw or heard |
| Map control / positioning | **Doable, mostly authoring** | Per-map area graph (6–8 duel maps). Can be bootstrapped from recorded paths, as done for campgrounds |
| Learning tricks by itself | **Doable for specific tricks** | Real-time trial-and-error is about 20 attempts/min. Fine for single tricks (this jump), too slow for learning whole duels from scratch |
| Adapting to the opponent | **Doable** | Stats feed + per-frame tracking of the human (position, inputs via `last_usercmd`) give rich opponent data |
| Post-match AI coach report | **Doable now** | All the data is there; send a match summary to Claude after each game |
| Line-of-sight / "can I see them" | **Needs work** | No trace function exposed yet. Requires finding the engine's trace function (same pattern-search technique minqlx uses) |

**Main remaining risk:** minqlx is unmaintained (last commit 2023) and relies on byte patterns in the 2016 QL server binary. That binary won't change (QL is no longer updated), so this is stable in practice.

## Running it
```
docker build -t qlbot <path-to-repo>
docker run -d --name ql -p 27960:27960/udp qlbot
docker exec ql python3 /tools/rcon.py "map campgrounds ffa" "addbot sarge 4" "addbot anarki 4"
docker exec ql python3 /tools/rcon.py "qlx !jl load" "qlx !jl start 0 1 40 keep"
```
Watch in game: QL console → `connect 127.0.0.1:27960`, then spectate (`team s`, `follow Sarge`).

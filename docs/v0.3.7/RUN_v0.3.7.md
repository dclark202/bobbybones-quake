# v0.3.7 on one page: what changes from v0.3.6

*Working document, started 2026-10-19 10:15, filled in as tonight's tests report. Folder `duel_gru_v0_3_7`. Starts on the
owner's go after the ~19:30 play test, from v0.3.6's save of about 16:00 (optimizer kept: a safe restart). Naming (owner,
2026-10-19): every stop for a play test bumps the last digit. Status: **planned**.*

**Marks:** ✅ built and proven identical with its switch off · 🧪 to be tested tonight · ❓ owner's decision · ⏸ not in v0.3.7

## Where v0.3.6 ended (from its checks)

| | Before v0.3.6 (v0.3.5's best) | v0.3.6 |
|---|---|---|
| Against v0.3.1's end | 47.8% | 52 to 54% from update 50 on (best 53.9%) |
| Against v0.3.4's end | – | 47 to 51% |
| Take-offs a minute, enemy unseen near / far | 12 / 17 | 20 / 26 |
| Speed in games, enemy unseen | ~300 | 311 |
| Rail shots past 600 units | – | 4 of 538 |
| Jump runs made | 59% | 35% (now weighted to the hard ones) |

(Filled at the stop: the last checks, the play test.)

## 1. Simulator fixes (closer to Quake Live)

| Change | Switch | State |
|---|---|---|
| Respawn waits 2.1 s after a death, as the game does (was instant) | `RESPAWN_QL=1` | ✅ ❓ |
| The maps' start points used as spawns too (Furious Heights 7% of pro respawns) | `SPAWN_QL=1` | ✅ ❓ |
| Jump key read every frame (his other keys stay on the four-frame grid; the finger limit stays) | `JUMP_EVERY=1` | being built 🧪 |
| Auto-hop (holding jump re-jumps on landing) set to what the game does, the same in training and on the servers | `AUTO_HOP=0/1` | being built; the setting from tonight's measurement 🧪 ❓ |
| Stairs, ledges, splash on steps; Blood Run's stairs-to-yellow jump (the game's step jump is missing in the simulator) | B-267 | measured tonight 🧪; fixes later ⏸ |
| Missiles as a point, not a small box (rockets hit step edges early: 39 of 216 on stairs) | `MISSILE_POINT=1` | being built 🧪 ❓ |
| Hearing through the map's visibility data | `HEAR_QL` | ⏸ until measured in the game |
| Rockets left a frame late on the servers (a plugin bug) | B-268 | servers only, before he plays there |

## 2. Speed (the same training, faster)

| Change | Switch | State |
|---|---|---|
| Simulator 12 to 21% faster a frame, every number unchanged | always on | ✅ |
| Learning step without its ~130 waits a piece (estimate 117 to 70-90 s an update) | `--learn-nosync 1` | ✅ 🧪 |
| Learn while the next games play (decoupled PPO) | `--overlap 1` | ✅ 🧪 |
| Fewer learning pieces (180 with the overlap) | `--minibatches 180` | 🧪 |
| Workers on 18 of the 20 cores, checks on the E cores | | ✅ (in v0.3.6) |

## 3. Run composition

| Round kind | v0.3.6 | v0.3.7 (proposed) |
|---|---|---|
| Whole games | 70% | 66% |
| Mid-game starts (moments of his own games) | 10% | 0% (replaced) |
| Pro starts (real moments of pro duels: positions, stacks, weapons, items, score, clock) | – | 10% (being built 🧪 ❓) |
| Rail range starts (15 s, at pro rail spots, rail in hand) | – | 4% |
| Item runs | 10% | 10% |
| Jump runs (weighted to his misses, half from far back) | 10% | 10% |
| Rocket-jump runs | – | share ❓ |
| **Reminder (owner, 2026-10-19): balance these shares together before the start** | | ❓ |

## 4. Training and pay changes

| Change | Switch | State |
|---|---|---|
| Rail range starts (far rail is viable at his aim limits: 44% at 900 units against a strafer, the pros 40%) | `RAIL_START_P=0.05`, `RAIL_START_LEN=15` | ✅ ❓ |
| Rocket-jump runs | `RJ_RUN_P` | built in v0.3.6 ❓ |
| Chain-hop bonus: each hop that keeps or gains speed, a growing multiplier, reset on a loss | `HOP_CHAIN` | being built; size 🧪 ❓ |
| Pay kept from v0.3.6: items 0.35/0.35/0.18, damage taken 0.75, speed pay 0.25 games / 0.4 runs, long-range rail 0.12, blind rockets free | | ❓ keep |

## 5. Tonight's tests (results filled in)

| Test | Result |
|---|---|
| Stairs, ledges, splash, auto-hop on/off in the real game | |
| Settings dump of the game (`g_*`, `weapon_*`) | |
| Learner arms (today / nosync / overlap / overlap+nosync / +180 pieces) | |
| Full dry run of v0.3.7's file, ten updates, step per output | |
| Check of that save against the control | |

## Files

Code: branch `v036-day2` (+ `v037-hop`). The full write-up for tonight: the v0.3.7 report (sent at the play test).
Audit of the simulator against the game: [../v0.4/FIDELITY_AUDIT.md](../v0.4/FIDELITY_AUDIT.md).

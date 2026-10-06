# BobbyBones: log formats

All logs live under `data/` (git-ignored, never committed). No Steam IDs or player names of humans are
written to the session logs; the human is always `opp` / `"human"`.

## Play-test sessions (`plugins/duelbot.py`, schema 1)

One folder per session: `data/duellive/sessions/<UTC date-time>_<map>_<human|spar>/`. A session starts when
an opponent is in the game with Bobby and ends when they leave or the map changes. `human` = a person,
`spar` = a Nightmare bot (`SPAR=1`).

### `meta.json`
| Field | Meaning |
|---|---|
| `schema` | Schema version (1) |
| `started` | Unix time |
| `map` | Map name |
| `opponent`, `opponent_name` | `human` or `spar`; the bot's name for spar, `"human"` otherwise |
| `policy`, `train_minutes`, `env` | Training run name, its training time, simulator module it was trained in |
| `react_ms`, `frame_ms` | Bobby's reaction delay on enemy information; server frame length (25) |
| `frame_columns` | Column names of `frames.csv` |

### `frames.csv` (one row per server frame, 40 per second, both players)
`b_` = Bobby, `o_` = opponent. Rows continue while Bobby is dead (his keys are then 0).

| Column | Meaning |
|---|---|
| `t`, `server_ms` | Unix time; game clock in ms |
| `drill` | `-`, `rl`, `rg` or `lg` |
| `*_x,y,z` / `*_vx,vy,vz` | Position and velocity (game units, units/s) |
| `*_pitch`, `*_yaw` | View angles in degrees (pitch positive = down) |
| `*_health`, `*_armor` | |
| `*_weapon` | Weapon held, game numbering: 1 gauntlet, 2 MG, 3 SG, 4 GL, 5 RL, 6 LG, 7 RG, 8 PG, 14 HMG |
| `*_ammo_rl`, `*_ammo_rg`, `*_ammo_lg` | Ammo, or -1 if the weapon is not owned |
| `*_fwd`, `*_right`, `*_up`, `*_fire` | Keys this frame (-127..127; fire 0/1). For the opponent these are the real inputs the server ran, so a human's sessions double as imitation data |
| `b_sees` | 1 if Bobby's fair senses see the opponent (line of sight inside his field of view) |
| `b_seen_ago` | Seconds since Bobby last saw or heard the opponent |
| `los` | 1 if there is a clear line between the two players (any view direction) |
| `b_aim_err`, `o_aim_err` | Degrees between that player's crosshair and the true direction to the other's body |
| `missiles` | Projectiles in flight |

### `events.jsonl` (one JSON object per line; every event has `t` and `map`)
| `event` | Fields | Notes |
|---|---|---|
| `hit` | `victim`, `dmg`, `killed`, `attacker_weapon`, `victim_weapon`, `dist`, `los`, `drill` | Inferred from a drop in health + armor of 3 or more in one frame. Self-damage (own rockets, falls) shows up as a hit on yourself with the other player's weapon listed; `los` false is the hint. Exact attribution is backlog B-25 |
| `death` | `who`, `drill`, `state`, `bobby`, `opp` | `state` = snapshot (positions, health/armor, Bobby's weapon, `visible`, `seen_ago`); `bobby`/`opp` = running score. A death counts as a frag for the other player (suicides included) |
| `pickup` | `item`, `by` | Item class name; taken by the nearer player (`?` if nobody within 120 units) |
| `note` | `text`, `drill`, `state`, score | The play-tester's `!note`, with the same snapshot as a death |
| `drill` | `drill`, score | `!drill` changed the mode (`null` = normal loadout) |
| `minute` | `visible`, `fire`, `fast_air`, `weapon_share`, `dmg_dealt`, `dmg_taken`, score | Per-minute summary for Bobby: share of frames he saw the opponent, held fire, was airborne above 330 u/s; share of frames per weapon (RL, RG, LG, MG); cumulative damage |
| `end` | score | Session closed |

Suggested note tags (first word of the text): `aim`, `move`, `weapon`, `items`, `stuck`, `weird`, `good`.

### Test rooms (schema 2 additions)
- `frames.csv` column `drill` holds `room:<room name>` while a room runs; in rooms the `o_` player is the
  subject (the human) and `b_` is the scripted target or fighter.
- `events.jsonl`: `room_start` (`room`), `room_result` (`room`, `result` = the room's metrics); `note` and
  `death` carry `room`.

## Free-for-all sessions (`plugins/ffabot.py`, schema 4)

One session per map load, in `data/<server data>/sessions/<date>_<map>_ffa/`. `meta.json` as the 1v1 sessions with
`kind: ffa`, `seats: 6`. `frames.csv`: one row per Bobby per server frame (25 ms): `t, server_ms, bot, seat`, his own
state (`b_*`, the same 18 columns as the 1v1 rows: position, velocity, view, health, armor, weapon, ammo, keys),
`foe_seat` (the enemy he attends to), `foe_bot`, `b_sees`, `b_seen_ago`, `b_aim_err` (to that enemy; -1 with none),
`intent` (none / MH / RA / RL / RG / LG), `people`, `bots`. `events.jsonl`: `join` / `leave` (seat, bot), `death`
(seat, bot, the game's kill and death counts), `pickup` (item, seat, bot), `bots` (n set by a player), `note`,
`minute` per Bobby (share of frames with an enemy in sight, firing, weapon shares, the game's kills, deaths, damage
dealt and taken, how many people and bots), `end`. No names or Steam IDs.

## Test suite cards
One JSON per card: `{suite, run, subject, minutes, maps, rooms: {<room name>: {<metric>: value}}}`.
- Policy cards: `data/sim_runs/<run>/suite/card_<minutes>.json` and `.md` (`sim/test_suite.py`).
- Human cards: `data/duellive/suite/human_<UTC time>.json` (play-test server, `!room ...`); repeated rooms are
  averaged and `runs` counts them.

| Room | Metrics |
|---|---|
| `aim/<weapon>/<still,slow,fast,jump>[@close,@far]` | `hit_rate`, `damage_per_s`, `kills_per_min`, `aim_err_deg` and `on_target` (while the target is in view), `sees_target` |
| `choice/<close,mid,far>` | `held` (weapon share while the target is in view), `switches_per_min`, `damage_per_s`, `kills_per_min` |
| `move` | `arrivals_per_min`, `speed`, `fast_air` (share of frames airborne above 330 u/s) |
| `solo` | `mega_per_min`, `red_armor_per_min`, `armor_per_min`, `health_per_min`, `fire`, `blind_fire`, `switches_per_min` |
| `ladder/fighter` | `frags_per_min`, `deaths_per_min`, `damage_dealt_per_min`, `damage_taken_per_min`, `switches_per_min`, `blind_fire` |

Lab-map rooms (`testlab`):

| Room | Metrics |
|---|---|
| `aim/<weapon>/<walk,jump,env>` | Same as the aim rooms above |
| `move/<course>` | `finished` (1 if the end was reached), `time` (s to the end, -1 if not), `distance` (along the course's path), `top_speed`, `mean_speed`, `falls`, `height` (highest point above the start) |
| `fight/<style>` | Same as `ladder/<style>` |

Differences between the simulator rooms and the live rooms: live targets have endless health and kills are
counted as damage / 125; a human's hits are derived from damage and ammo used; live aim rooms re-place both
players every 10 s; the simulator runs 32 subjects per map at once.

## Training runs (`data/sim_runs/<run>/`)
- `metrics.jsonl`: one line per report: `update`, `steps`, `minutes`, `sps`, `frags_per_match_min`,
  `suicides_per_match_min`, per-weapon hit rates and frag shares, `pickups_per_player_min`, `visible`,
  `air_fast`, `jerk`, `vs_snapshot_kill_share`, `league_size`, `entropy`, `close_p`.
- `policy.pt` (weights, input normalization, action layout, training minutes), `snapshots/` (league).
- `data/sim_runs/<run>.log`: the same lines as text.

## Other
- `data/weaponlab*/weaponlab.jsonl`: real-server weapon measurements (`plugins/weaponlab.py`): per test, per
  frame health, armor, position and velocity of shooter and target.
- `data/movetest*/movetest.jsonl`, `movetest_frames.jsonl`: live movement trips of a simulator policy.
- `data/demos_parsed/<map>/`: pro demos as float32 records (format in `tools/demodump/demodump.cpp`,
  reader `sim/demo_reader.py`).
- `data/practice/`: public-server logs from the retired Nightmare-based bot (`human_results.jsonl`, recordings).

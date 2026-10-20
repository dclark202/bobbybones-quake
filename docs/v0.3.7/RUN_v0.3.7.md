# v0.3.7 on one page: what changes from v0.3.6

*Working document, started 2026-10-19 10:15, filled in as tonight's tests report. Folder `duel_gru_v0_3_7`. Starts on the
owner's go after the ~19:30 play test (about 21:00 Mon), from v0.3.6's save 260 of 15:46 (optimizer kept: a safe restart);
runs to **16:00 Tue** (about 19 h; the owner's default stop from now on), play test about 19:30 Tue; the rocket-jump
specialist trains on the card in the gap. Naming (owner,
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
| Respawn waits 2.1 s after a death, as the game does (was instant) | `RESPAWN_QL=1` | ✅ in (owner, 2026-10-19) |
| The maps' start points used as spawns too (Furious Heights 7% of pro respawns) | `SPAWN_QL=1` | ✅ in (owner, 2026-10-19) |
| Jump key read every frame (other keys stay on the four-frame grid; finger limit stays). A jump 1 frame late after landing: 456 → 598 u/s after 4 s. v0.3.6 was never asked between readings: at 1 from the start it jumps 44/min (24 now) and runs 6% slower, so start at a share and raise it live | `JUMP_EVERY=0.25` → 0.5 → 1 | ✅ yes: 25% at the start, stepped up live to 50% and 100% over the first hours (owner) |
| Duel movement: no speed from the forward key alone (`pmove_BunnyHop 0` in the game's duel preset; measured 2026-10-19: the simulator matches duel 1,362 of 1,372 with it, 1,202 without) | `QL_FWD=0` | ✅ yes (owner: "make it match the duel mode, that's his eventual final place") |
| Auto-hop (holding jump re-jumps on landing) set to what the game does; the export carries it and the servers' bot follows it | `AUTO_HOP=0/1` | ✅; setting from tonight's measurement 🧪 ❓ |
| Stairs, ledges, splash on steps; Blood Run's stairs-to-yellow jump (the game's step jump is missing in the simulator) | B-267 | measured tonight 🧪; fixes later ⏸ |
| Missiles as a point, not a small box: rocket blasts on stairs at the game's point 214 of 216 (was 0; 50 were early); grenade rest error 67 → 12 units | `MISSILE_POINT=1` | ✅ in (owner, 2026-10-19) |
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

Set by the owner, 2026-10-19 (shares of all his playing time):

| Round kind | v0.3.6 | v0.3.7 | Switch |
|---|---|---|---|
| Whole games (self-play, the league) | 70% | 70% | `GAME_P=0.7778` (of the games' time) |
| Mid-game starts (moments of his own games) | 10% | 0% (replaced) | `MID_START_P=0` |
| Pro starts (real moments of pro duels) | – | 10% | `PRO_START_P=0.1111` |
| Rail range starts (15 s, at pro rail spots, rail in hand) | – | 10% (the rocket jumps' 5% too: owner) | `RAIL_START_P=0.1111`, `RAIL_START_LEN=15` |
| Item runs (movement) | 10% | 5% | `ITEM_RUN_P=0.05` |
| Jump runs (weighted to his misses, half from far back) | 10% | 5% | `JUMP_RUN_P=0.05` |
| Rocket-jump runs | – | 0% ⏸ (owner, 2026-10-19: needs more work: a rocket-jump teacher first) | `RJ_RUN_P=0` |
| League: the last 3 best models, 8% each of his games (v0.3.4's, v0.3.5's, v0.3.6's ends) | v0.3.1's end 25% | 24% | `--anchor-p 0.24` |
| End-of-day check: 80 games against the previous best, 80 against v0.3.1's end (control); in-day checks alternate the two; a day-end joins the league only at ≥50% against the previous best | | ✅ agreed |

## 4. Training and pay changes

| Change | Switch | State |
|---|---|---|
| Rail range starts (far rail is viable at his aim limits: 44% at 900 units against a strafer, the pros 40%) | `RAIL_START_P=0.05`, `RAIL_START_LEN=15` | ✅ ❓ |
| Rocket-jump runs: not in v0.3.7 (owner). In the dry run he fired a rocket in under 1 of 200 tries and made 0.1-0.3%: nothing to learn from yet. Next: a rocket-jump specialist trained on its own, used as a teacher | | ⏸ |
| Chain-hop bonus: each hop that keeps speed (within 15) pays more, ×1 to ×3; a loss, 150 ms on the ground or the enemy in view ends the chain; nothing paid in view. A good hopper unseen ~0.4–0.75 a minute, below a frag | `HOP_CHAIN=0.005` (HOP_PAY 0.003 kept) | ✅ yes (owner, 2026-10-19) |
| Item pay kept at 0.35/0.35/0.18 (owner, 2026-10-19: "leave the pay weights as is") | `ITEM_FLAT` | ✅ |
| **Rail backup (owner's standing OK for v0.3.7, flagged when used):** if stalled at about update 80 (first shot within 10 s under 40%, hits past 900 under 20%, far rail in games not up): (1) long-range rail pay 0.12 → 0.25 live; (2) rail shot price ×0.5 and (3) rail starts facing within 15°, 30 s, at the next save; (4) rail starts 10 → 15%. A rail teacher (5) only with his go | | ✅ |
| Pay kept from v0.3.6: items 0.35/0.35/0.18, damage taken 0.75, speed pay 0.25 games / 0.4 runs, long-range rail 0.12, blind rockets free | | ✅ kept (owner) |

## 5. Tonight's tests (results filled in)

| Test | Result |
|---|---|
| Stairs, ledges, splash, auto-hop on/off in the real game | |
| Settings dump of the game (`g_*`, `weapon_*`) | |
| Learner arms (today / nosync / overlap / overlap+nosync / +180 pieces) | |
| Full dry run of v0.3.7's file, ten updates, step per output | |
| Check of that save against the control | |

## Files

Code: branch `v037` (v036-day2 + v037-hop + v037-missile + v037-prostart). The full write-up for tonight: the v0.3.7 report (sent at the play test).
Audit of the simulator against the game: [../v0.4/FIDELITY_AUDIT.md](../v0.4/FIDELITY_AUDIT.md).

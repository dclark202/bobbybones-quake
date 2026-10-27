# BobbyBones' human limits on aim, view and reaction (as of v0.5.1, 2026-10-27)

A reference for a reviewer: every limit the simulator and the real-game plugin put between what Bobby's network wants and
what his crosshair does, what each models, the exact code, its value at `!aim default` (and at worse / better / max), where
it applies, and how its value was chosen. Then the owner's two concerns, answered from the code.

**Sources (read only).**

| What | Where |
|---|---|
| The running simulator (v0.5.1, branch `v051`, commit 120c086) | `sim/duel_env.py` in the worktree `ql-bot-v051` beside the repo (cited as `duel_env.py:<line>`). The run plays the generated group module `duel_env_ffa.py` (`--env duel_env_ffa --group 2`), made from `duel_env.py` by `tools/make_ffa_env.py`: the same code at shifted lines (for example the cap by weapon is `duel_env_ffa.py:6937`). |
| The trainer | `ql-bot-v051\sim\train_duel_rnn.py` |
| The run's command | `ql-bot-v051\scratch\run_duel_gru_v0_5_1.cmd` (environment variables and trainer flags) |
| The run's live settings | `ql-bot\data\sim_runs\duel_gru_v0_5_1\live.json`: `PERCEPT_SPEED 0.075`, `PERCEPT_SPEED_MAX_RG 0.001`, `PERCEPT_SPEED_MAX_LG 1.5` (in force from v0.5.1's update 1, trainer log) |
| The real-game plugin (play build) | `plugins/duelbot.py` in the worktree `ql-bot-play05` (branch `play-v05`) (cited as `duelbot.py:<line>`), which imports the play build's `sim/duel_env.py` (its `observe()` is identical to v0.5.1's) |
| The `!aim` table actually served | `ql-bot\data\duellive_play05\policy_{worse,default,better,max}.npz` (`env_vars`, `react_ms`, `acquire_ms`); v0.5.0's end network; `policy.npz` = default |

Frames are 25 ms (`DT = 0.025`, `duel_env.py:42`), as Quake Live's `sv_fps 40`. "Per axis" means yaw and pitch separately.

---

## 1. The settings at a glance

### 1.1 The `!aim` table (the play build's files, 2026-10-27)

Read from each file's `env_vars`, `react_ms`, `acquire_ms`. All four are the same network (v0.5.0's end), trained at `default`
only; worse / better / max are applied at play time and never trained on.

| Setting | worse | **default** (= training) | better | max |
|---|---|---|---|---|
| `AIM_LEVEL` | 3 | **3** | 3 | 40 |
| Tracking delay `react_ms` | 150 | **100** | 75 | 25 |
| Notice delay `acquire_ms` | 300 | **200** | 150 | 25 |
| `SURPRISE_MS` | 300 | **200** | 150 | ~0 (level 40) |
| `PERCEPT_SIGMA` (deg) | 1.0 | **0.6** | 0.3 | ~0 |
| `PERCEPT_TAU` (s) | 0.15 | **0.15** | 0.15 | 0.15 |
| `PERCEPT_SPEED` (deg per deg/s) | 0.125 | **0.075** | 0.05 | 0 (unset: the level's 0) |
| Cap with the rail `PERCEPT_SPEED_MAX_RG` (deg) | 1.0 | **0.001** | 0.001 | (unused: slope 0) |
| Cap with the lightning gun `PERCEPT_SPEED_MAX_LG` (deg) | 3.0 | **1.5** | 0.5 | (unused) |
| Cap with any other weapon `PERCEPT_SPEED_MAX` (deg) | 3.0 | **1.5** | 0.5 | (unused) |
| `MOTOR_NOISE` / `MOTOR_BASE` | 0.15 / 0.075 | **0.10 / 0.05** | 0.075 / 0.0375 | ~0 |
| Flinch `FLINCH_PER_DMG` / `_MAX` / `_TAU` | 0.25 / 6 / 0.5 | **0.25 / 6 / 0.5** | 0.25 / 6 / 0.5 | ~0 |
| Everything else in this document | same | same | same | same |

The values at max come from `AIM_LEVEL=40`: every level-scaled value is multiplied by `1.25^(3-40)` ≈ 2.6e-4
(`aim_settings`, `duel_env.py:198-209`). The table that wrote these files is the scratchpad script `play05/aim05.py`
(not in the repo; `SOURCE.txt` in the data folder names it): "the owner's !aim table of 2026-10-26 ... with the change of
2026-10-27: only the rail cap (PERCEPT_SPEED_MAX_RG) worse 1.0, default 0.001, better 0.001 (0 would fall back to
PERCEPT_SPEED_MAX)". `SURPRISE_MS` and `MOTOR_BASE` are scaled with the delays and the hand noise; the flinch stays the
default's (as `docs/v0.5.0/RUN_v0.5.0.md:54-60` says).

### 1.2 Where each value of the training run comes from

| Value | Source in the run |
|---|---|
| `AIM_LEVEL=3` (sight error 0.6 / 0.15 s, surprise 200 ms, flinch 0.25 / 6 / 0.5, hand 0.10 / 0.05) | `.cmd` `set AIM_LEVEL=3`; values from `aim_settings` |
| Tracking / notice delay 100 / 200 ms | trainer flags `--react-ms 100 --acquire-ms 200` (`train_duel_rnn.py:1441-1442`, set on each simulator at `:57-58`) |
| `PERCEPT_SPEED_MAX=1.5` | `.cmd` (`set PERCEPT_SPEED_MAX=1.5`; the code default is 3.0, `duel_env.py:247`) |
| `PERCEPT_SPEED`, `_MAX_RG`, `_MAX_LG` | `live.json` (live names, `LIVE_VARS`, `duel_env.py:1982-1993`; checked by `live_values`, `:2013-2020`) |
| `KEY_RATE=8`, `HAND_BAND=1` (`HB_FC 4.0`, `HB_BETA 0.5`), `FIRE_QL=1`, `ZOOM_PERCEPT=1`, `PROJ_SEE=1`, `PROJ_FIX=1` (100 / 100 ms), `VEL_FIX=1` (200 ms, 0.2, 0.3 s, 30), `RANGE_FIX=1` (0.15, 0.5 s), `SENSE_MINOR=1` | `.cmd` |
| Everything else (inertia, flick cap, pad, finger holds, field of view, focus) | constants in `duel_env.py` |

A checkpoint carries the switches as `env_vars` (live values included: the trainer sets them in its own environment,
`train_duel_rnn.py:2753`, `:3088`); `sim/export_duel.py` writes them into `policy.npz`, and the plugin puts them into its
environment before importing the simulator (`duelbot.py:2363`). So the server runs the same module-level values.

---

## 2. Every limit, one by one

Order: what he sees (2.1-2.6), how late (2.7-2.10), how well he judges where the enemy is (2.11-2.15), his hand on the
mouse (2.16-2.21), his fingers (2.22-2.24), the shot (2.25-2.26), pays that touch aim (2.27). For each: the mechanism,
values, weapons, where it applies, and its history.

### What he sees

**2.1 The enemy in view: field of view and line of sight.**
- *Models:* an enemy is seen only inside the screen and with a clear line.
- *Mechanism:* `step()` `duel_env.py:12784-12796`: in view if the angle between his view and the line to the enemy is under
  a cone of 55° half-angle (`fov()`, `:6632-6635`: `cos(55° × z)`, z = 0.4 zoomed, else 1), the enemy within 4,000 units,
  and the line from his eye to the enemy's origin + 8 units (one point, about chest height) clear (`_los`, the map's sight
  mask). Not seen while waiting to respawn, in movement or solo rounds.
- *Value:* 55° cone (110° wide, a circle, not the screen's rectangle); zoomed 22°.
- *Weapons:* all. *Where:* both (the plugin's `senses()`, `duelbot.py:1383-1395`, same test; a dead enemy is not seen).
- *History:* the field of view since 2026-10-05; RESULTS 2026-10-20 17:10: "our visibility test agrees with the server's on
  98.99% of frames" (against 232 pro demos' snapshots).

**2.2 What else the eyes cover (walls, floor).** `FOV_H, FOV_V = 50°, 37.5°` half-angles (`duel_env.py:149`): wall and
floor distances outside that box read UNSEEN (`observe()` `:6817-6833`; `GROUND_SENSE=1` in the run gives the floor all
round, `:6828`). Not an aim limit; listed for completeness. Both (shared `observe()`).

**2.3 Enemy projectiles (`PROJ_SEE`, `PROJ_FIX`).**
- *Models:* he knows only the rockets, grenades and plasma he can see (owner, 2026-10-10: "he should only know what's in view
  or what he can hear").
- *Mechanism:* `_proj()` `duel_env.py:7118-7135`: the six nearest enemy projectiles inside the 55° cone, within
  `PROJ_FAR` 1,500 units (`:678`), with a clear line from his eyes. With `PROJ_FIX` (`:2565-2573`): noticed only after
  `PROJ_NOTICE_MS` 100 ms on end in sight; what he reads (place, speed, closest pass) is `PROJ_READ_MS` 100 ms old; a
  grenade's fuse only if followed since it left.
- *Where:* both (shared `observe()`; the plugin keeps each projectile in one slot).
- *History:* `PROJ_SEE` 2026-10-10 (owner); `PROJ_FIX` 2026-10-20 senses audit ("projectiles ... exact" before: RESULTS
  2026-10-20 17:10); 100 / 100 ms are first values, not measured.

**2.4 The enemy's velocity (`VEL_REACT_FRAMES`, `VEL_FIX`).**
- *Mechanism:* the velocity inputs (and every input made of it: the rocket/plasma lead, the believed place) take the enemy's
  velocity `VEL_DELAY_MS` 200 ms old (`duel_env.py:2546-2560`, frames set at `:3969-3971`, read at `:6867`), times
  (1 + e), e a drifting error, AR(1) with std `VEL_WEBER` 0.2 and correlation time `VEL_TAU` 0.3 s, and a speed under
  `VEL_MIN` 30 u/s read as 0 (`_vel_percept`, `:7083-7094`).
- *Weapons:* all; matters mostly for leading projectiles. *Where:* both.
- *History:* the 200 ms delay since 2026-10-05 ("a person ... needs about 200 ms to pick up a change of direction",
  `:6839-6840`); `VEL_FIX` from the senses audit of 2026-10-20 (RESULTS 2026-10-20 17:10: the enemy's velocity had been
  exact); 0.2 / 0.3 s / 30 are the values written then, not since measured against people.

**2.5 The enemy's distance (`RANGE_FIX`).** His perceived enemy place is moved along the line from his eye by a drifting share
of the distance: AR(1) std `RANGE_WEBER` 0.15, `RANGE_TAU` 0.5 s, at most ±50% (`_range_percept`, `duel_env.py:7096-7105`,
applied in `observe()` `:6904-6906`, after the angular error). Affects every input built on the place: apparent size, the
lead's flight time, the grenade arc, the rocket aim point, the believed place. Both. From the senses audit of 2026-10-20; values not since measured against people.

**2.6 Small senses (`SENSE_MINOR`).** The enemy's facing (error 15°, 0.5 s), crouch, in-air and weapon are read as old as his
place; only rail and lightning lines are seen as trails (`duel_env.py:2575-2589`). Both. Not aim; listed for completeness.

### How late

**2.7 The tracking delay (`react_ms`, `REACT_FRAMES`).**
- *Models:* what he knows of the enemy (place, in view or not, time since seen) is this old when he decides; his own view is
  current, so the crosshair-to-enemy angles move at once with his mouse ("as on a real screen", `duel_env.py:6836-6838`).
- *Mechanism:* `observe()` keeps a history `opp_hist` of (`known`, `acquired`, velocity, `seen_t`) and reads the entry
  `react_frames` back (`:6839-6847`). `react_frames = round(react_ms / 25)`.
- *Value:* 100 ms = 4 frames at default (trainer flag; the module constant `REACT_FRAMES = 2` at `:219` and the trainer's
  own default `--react-ms 50` are not used by the run). worse 150, better 75, max 25 ms.
- *Not set by `AIM_LEVEL`:* `aim_settings` lists `react_ms` / `acquire_ms` (`:200-201`) and the comment at `:186` says a level
  sets them, but nothing in the simulator reads those two keys: the delays come only from the trainer's flags, the
  checkpoint's `react_ms` / `acquire_ms` (checks), or the play file's (`duelbot.py:975-980`).
- *Weapons:* all. *Where:* both (shared `observe()`; the plugin sets `env.react_frames` from the file).
- *History:* 50 ms in `duel_gru_v4` (B-58, owner's play test 2026-10-04: "aim superhuman"), 150 ms up to `duel_gru_v2`,
  75 ms in v10-v12, 100 ms from the aim audit (RESULTS 2026-10-08 13:15). 2026-10-20 sweep (RESULTS 2026-10-20 17:10,
  `docs/v0.3.8/RUN_v0.3.8.md:110-127`): with every fix on, lightning 41% at 125 ms, 38% at 150, 33.5% at 175 against the
  pros' 31%; rail 42 / 35 / 33% against 42%; the owner chose 125 ms for v0.3.8. v0.3.9 went to "aim 4" (100 / 160 ms,
  `docs/v0.3.9/RUN_v0.3.9.md:44`); v0.5.0 to level 3 at 100 / 200 ms (`docs/v0.5.0/RUN_v0.5.0.md:50`).

**2.8 Focus (the delay is an average, not a floor).**
- *Mechanism:* `observe()` `duel_env.py:6853-6863`, constants `:273`: `focus` starts each life at `FOCUS_SECS` 2 s, runs down
  1 s a second while the enemy is noticed, refills 0.25 s a second otherwise, kept within -0.5..2. The read delay is
  `react_frames - FOCUS_GAIN` (2 frames) while focus > 0, `react_frames + FOCUS_LOSS` (1 frame) after; never under 1 frame.
- *Value at default:* **50 ms for the first 2 s of continuous sight, then 125 ms**; back above 0 after up to 2 s unseen, full
  after 8-10 s. So the "100 ms" tracking delay is in practice 50 ms at the start of most fights.
- *Weapons:* all. *Where:* both (shared `observe()`; the plugin resets focus at his spawn, `duelbot.py:1980-1981`). His
  focus is also an input to him (`duel_env.py:6374`).
- *History:* B-93, owner 2026-10-05 ("he should be able to do better in short bursts, not sustained"); built 2026-10-05,
  "50 ms quicker while it lasts and 25 ms slower after" (`docs/archive/BACKLOG_closed.md:128`). Its values were never
  measured against people.

**2.9 The notice delay (`acquire_ms`, `ACQUIRE_FRAMES`).**
- *Models:* an enemy who has just come into view is not reacted to at once.
- *Mechanism:* `step()` `duel_env.py:12823-12826`: `vis_run` counts the frames the enemy has been in view without a break; he
  is "acquired" (and `known` set to his true place) once `vis_run >= _acq_need() + acq_extra`, where
  `_acq_need() = max(1, acquire_frames - react_frames)` (`:4247-4253`); the acquired flag then reaches him through the
  tracking delay above. Total at default: 4 frames in view, then the read delay.
- *Value:* with the first frame in view at t = 0, he first "sees" the enemy at t = 75 ms + the read delay: **125 ms with
  focus left, 175 ms nominal, 200 ms with focus used up**, plus the surprise delay. worse 300, better 150, max 25 ms.
- *Weapons:* all. *Where:* both (`duelbot.py:1407-1415`, same rule).
- *History:* 200 ms since B-58 (2026-10-04). The per-seat setting in checks is B-226 (2026-10-12).

**2.10 The surprise delay (`SURPRISE_MS`).**
- *Models:* an enemy who appears off the crosshair and unexpectedly is noticed later (people fire 0.5 s after an enemy
  appears in real games, he fired after 0.2 s: RESULTS 2026-10-08 13:15).
- *Mechanism:* `surprise_frames()` `duel_env.py:266-269`, applied at `:12820-12822`: on the first frame in view,
  `extra = round(SURPRISE_MS × clip((ecc - 10°)/30°, 0, 1) × (0.5 if seen or heard in the last 2 s else 1) / 25)` frames,
  ecc = the angle off his crosshair then; held while the enemy stays in view.
- *Value:* 0 within 10°, linear to the full 200 ms (8 frames) at 40° and beyond; half if seen or heard within 2 s. worse 300,
  better 150, max ~0.
- *Weapons:* all (no weapon test in the code). *Where:* both (`duelbot.py:1409-1412`).
- *History:* 2026-10-08 aim audit (new with level 3). B-255 (RESULTS 2026-10-15 16:50, commit 8530b86) looked at
  calibrating it for the rail by the pros' demos (4,662): where Bobby fires the rail he is "as quick as the pros or
  quicker" up to 80°; what he lacked was the shot at wide angles (55% of appearances 40-80° off against the pros' 89%).
  The commit changed docs only: there is no rail-specific surprise delay in the code.

### How well he judges where the enemy is

**2.11 The sight error (`PERCEPT_SIGMA`, `PERCEPT_TAU`).**
- *Models:* he judges the gap between crosshair and target by eye, with a slowly wandering error, not to a hundredth of a
  degree (`duel_env.py:234-246`).
- *Mechanism:* `observe()` `:6879-6903`. Per player and axis an AR(1) error in degrees:
  `percept ← ρ·percept + sqrt(1 - ρ²)·σ·N(0,1)`, `ρ = exp(-DT / PERCEPT_TAU)`, with
  `σ = PERCEPT_SIGMA (× ZOOM if zoomed) + flinch + min(PERCEPT_SPEED × ω, cap)` (the last two terms below). The error moves
  his perceived enemy place `known` sideways by `tan(percept_yaw) × d` (horizontal, perpendicular to the line) and up by
  `tan(percept_pitch) × d`, d the 3-D distance, only while the enemy is noticed and only for policy players
  (`:6899-6903`). **It changes his inputs only**, not his view and not the shot (section 3.2).
- *Value:* σ 0.6°, τ 0.15 s at default; stationary std per axis = σ.
- *Weapons:* all. *Where:* both (shared `observe()`).
- *History:* 1.0° → 0.6° on 2026-10-06 after the reflex room (he was wider than the owner); 1.2° / 0.5 s in v11-v12 (owner
  2026-10-07: "nudge hitscan aim down"; `:255-258` records the reflex-room effects); back to 0.6 / 0.15 with level 3 in the
  aim audit (RESULTS 2026-10-08 13:15: level 3 tracked a strafing target 44.8% of the time, the owner 40.1%; first rail
  shot 68% against the owner's 88%).

**2.12 The fast-target error (`PERCEPT_SPEED`) and its caps (`PERCEPT_SPEED_MAX`, `_RG`, `_LG`).**
- *Models:* a target that crosses the view fast is judged worse ("a slow, wandering offset ... that grows with how fast the
  target crosses his view", `duel_env.py:241-246`).
- *Mechanism:* `observe()` `:6885-6897`:
  - `ω` = the change from last frame of the true bearing (yaw and pitch, degrees) from his current eye to the enemy's
    reaction-delayed place, divided by DT, in deg/s; 0 on the first frame of a sighting (`bearing_ok`). It is a bearing in
    the world, not on his screen: his own movement adds to it, his own view turn does not, and it is the same whether or not
    he is following the target well.
  - The term added to σ is `min(PERCEPT_SPEED × ω, cap)` with
    `cap = PERCEPT_SPEED_MAX_RG if the weapon in hand is the railgun, PERCEPT_SPEED_MAX_LG if the lightning gun, else
    PERCEPT_SPEED_MAX` (`:6891-6895`; a per-weapon cap of 0 falls back to `PERCEPT_SPEED_MAX`, hence 0.001 for "none").
  - "The weapon in hand" is `self.weapon`, which in the simulator changes on the frame of the switch command (before the new
    weapon can fire, `SWITCH` 0.425 s, `:73`); on the server the plugin shows the chosen weapon the same way
    (`duelbot.py:2163`).
- *Values at default:* slope 0.075° per deg/s; caps rail 0.001°, lightning 1.5°, **every other weapon 1.5°** (machine gun,
  heavy machine gun, shotgun, rockets, grenades, plasma, gauntlet). The cap is reached at ω = 1.5 / 0.075 = 20 deg/s, for
  example a 320 u/s sideways run at 920 units; at duel ranges the cap usually binds, so the term is in practice a flat
  +1.5° whenever the target moves. Total σ per axis at default: lightning or any non-rail weapon up to 2.1° (+ flinch); rail
  0.6° (+ flinch).
- *Where:* both (shared `observe()`; the values come in `env_vars`).
- *History (all dated):*
  - v11-v12: `PERCEPT_SPEED 0.012` (2026-10-07, the "first click"); 0 at every aim level from 2026-10-08 (`:200`).
  - 2026-10-12 (RESULTS 16:00; `docs/archive/BACKLOG_closed.md:133`): at 0.012 lightning -2.5 points with rail unchanged;
    at 0.025 lightning reached the pros' 31.6%, rail 4.5 points down.
  - 2026-10-26 10:15 (RESULTS; commit 2792ad7): the same network hit LG 0.50 / RG 0.60 / RL 0.52 in the simulator, LG
    0.38-0.39 / RG 0.40-0.45 / RL 0.45 on the real servers (end-of-game stats, 94 games). `PERCEPT_SPEED` made live and
    calibrated in self-play (8 maps × 8 games): 0.05 gave LG 0.415, RG 0.466, RL 0.455 (LG/RL 1.07 → 0.91; real ~0.85). The
    cap was then the code's 3° for every weapon.
  - 2026-10-26 16:30 (v0.5.0's start; `docs/v0.5.0/RUN_v0.5.0.md:62-69`): `!aim default` = 0.075 with one cap of 5°: LG
    37.4%, rail 38.2%, rockets 52.4% against the pros' 32.7 / 43.5 / 31.2% (4,166 demos). One cap "moved lightning and rail
    together"; the pros' gap is wider.
  - 2026-10-26 evening (commit 33804d3, `v050aim`): the cap by weapon. v0.5.0's trainer log: rail/LG 4 / 6.5, then 3 / 8,
    then 3 / 10. Self-play calibration (`RUN_v0.5.0.md:56-57`): rail 3 / LG 5 → LG 37.3, rail 43.8; 3 / 8 → 34.3 / 41.9;
    3 / 12 → 34.0 / 45.0; 2.5 / 10 → 34.5 / 44.6; at 3 / 10 LG 34%, rail 43.6% (RESULTS 2026-10-26 21:10).
  - 2026-10-26 night (RESULTS 21:10): "the calibration misled": against the owner's strafe (32-36°/s at 340 units) his
    lightning was on target 15-20% of firing time with a 5° aim error ("way too weak on lg", "better is still far too weak");
    "self-play opponents rarely strafe across the line of fire". The owner's play tests set one cap of 1.5° for every
    weapon, the rail 1.0° (trainer log: both 1.5, then the rail 1.0, after the restart at update 50).
  - 2026-10-27 (no results entry yet): the rail cap 0.001 (none), the owner's call that morning after seeing the training hit rates under the 1.0 cap ("can we drop the additional error on the rail only?"); then !aim worse 1.0 / better 0.001 (owner). Trainer log of v0.5.0's last process, "from update 161 ...
    changed {'PERCEPT_SPEED_MAX_RG': '0.001'}" (v0.5.0's `live.json` written 07:13); the play files of the same day; v0.5.1
    from its update 1. I found no written reason for this step in the repo.

**2.13 The zoom (`ZOOM_PERCEPT`).** Zoomed (`ZOOM` 0.4, `duel_env.py:146`: 100 × 75° → 40 × 30°, the owner's cg_zoomfov 42
against cg_fov 103), the sight error's base σ is × 0.4 (`:6883-6884`); **the flinch and the fast-target term are not
scaled**. The hand is also scaled (2.16-2.19). Any weapon can zoom; the zoom finger has its own 150 ms hold (2.24). Both.
v0.3.8, the zoom check of 2026-10-19 (`:1966-1973`).

**2.14 The flinch (`FLINCH_PER_DMG`, `FLINCH_MAX`, `FLINCH_TAU`).**
- *Models:* being shot throws his read of the enemy's direction off (screen kick and flash).
- *Mechanism (simulator):* on a frame he takes damage from an enemy (`hitby`: attacker another player,
  `duel_env.py:12066-12070`): `add = min(FLINCH_MAX, FLINCH_PER_DMG × damage)`; `flinch ← min(FLINCH_MAX, flinch + add)`
  (added to σ, decaying by `exp(-DT/FLINCH_TAU)` a frame, `:6881`); and the error itself jumps by `add × N(0,1)` per axis.
- *Value:* 0.25° per point, at most 6°, fading over 0.5 s; the same at worse, default and better. A rail hit (80) or a rocket
  gives the full 6°; each lightning hit (6) adds 1.5°. My arithmetic, not a measurement: under steady lightning fire at about
  6 hits a second the flinch sits near 5°, so his sight error is about 0.6 + 5 + 1.5 ≈ 7° per axis.
- *Weapons:* all, whatever he holds and whatever hit him. *Where:* both, with a difference (section 5).
- *History:* B-94 (2026-10-05; first values 0.06 / 2.5 / 0.3; 0.12 / 3 / 0.3 until v12); 0.25 / 6 / 0.5 from the aim audit
  (RESULTS 2026-10-08 13:15: he kept 78% of his tracking under fire, the owner 51%; at level 3 "under fire still above him").
  B-215 (owner, 2026-10-10): he "maybe flinches a *bit* too much" (seen on the server; not measured since).

**2.15 What the error reaches.** Everything `observe()` builds from the perceived place `known` after `:6903`: his relative
place of the enemy, the crosshair-to-enemy angles (coarse ±15°, fine ±2°, both axes), the "on target" flag (computed against
the perceived place, `:6919-6920`), the apparent size, the lead of a rocket or plasma ball (`_v14`, `:8114-8148`), the rocket
aim inputs (`_raim`, `:7424-7450`), the believed place and its tokens (`_v02`), the drift inputs (off in the run). The
velocity inputs are not moved by it (they have `VEL_FIX`).

### His hand on the mouse

The order in a frame (`step()` `duel_env.py:11500-11530`; the plugin `drive()` `duelbot.py:1448-1511`, same order):
the turn and pitch commands (discrete, `TURN` ±0.03 … 60°/frame, `PITCH` ±0.03 … 20°/frame, `:43-46`; × 0.4 zoomed) →
inertia → flick cap (yaw) → hand bandwidth → hand noise → mouse pad → the view.

**2.16 View inertia (`MOUSE_SMOOTH`, `MOUSE_SMOOTH_FINE`).** `mv ← s·mv + (1 - s)·cmd` per axis, s = 0.75 for a command over
1° a frame, 0.2 for smaller ones (`duel_env.py:77`, `:274`, `:11515-11518`; with `ZOOM_PERCEPT` "small" is in hand
degrees). A big command reaches 25% of itself in the first frame, 68% after four. All weapons. Both. Since B-58 (2026-10-04);
RESULTS 2026-10-15 16:50 names it as a likely cause of his missing wide-angle rail shots.

**2.17 The flick cap (`TURN_CAP`).** The yaw velocity is clipped to ±30°/frame (1,200°/s), × 0.4 zoomed
(`duel_env.py:228`, `:11521`). Pitch has no cap beyond the 20°/frame largest command. All weapons. Both (`duelbot.py:1501`).
B-58 (2026-10-04); not since re-measured.

**2.18 The hand's bandwidth (`HAND_BAND`).**
- *Models:* a hand cannot correct at high frequency (owner, 2026-10-20: "some kind of low pass filter on his LG aim").
- *Mechanism:* `_hand_band()` `duel_env.py:5474-5482`: per axis, `hb ← hb + k·(mv - hb)`,
  `k = 1 - exp(-2π·fc·DT)`, `fc = HB_FC + HB_BETA·|hb|` Hz (|hb| in degrees a frame): a one-euro rule, small corrections
  smoothed, a flick let through. At rest fc = 4 Hz (k = 0.47 a frame); at 20°/frame fc = 14 Hz (k = 0.89).
- *Value:* 4.0 Hz, 0.5 Hz per deg/frame. *Weapons:* all ("every weapon, the hand is the same"). Policy players only.
  *Where:* both (`duelbot.py:1502`).
- *History:* sized on save 220's own commands while firing lightning against the pros (`:2591-2600`): yaw acceleration rms
  4,600 → 2,610 deg/s² (pros 2,455), reversals 8.3 → 4.8 a second (4.6), view-rate power above 4 Hz 0.43 → 0.27 (0.29). The
  owner chose 4 Hz ("Let's just do 4Hz", `docs/v0.3.8/RUN_v0.3.8.md:105`). In v0.3.8 from 2026-10-20.

**2.19 Hand noise (`MOTOR_NOISE`, `MOTOR_BASE`).** After the filter, each axis gets
`N(0, MOTOR_NOISE·|v| + MOTOR_BASE·z)` degrees this frame, v the filtered view velocity, z the zoom scale
(`duel_env.py:229`, `:11524-11526`). Default 0.10 and 0.05° (worse 0.15 / 0.075, better 0.075 / 0.0375): a still hand
wanders 0.05° a frame, a 20°/frame flick carries 2° of noise on that frame. Policy players only. Both (`duelbot.py:1503`).
0.14 until 2026-10-06 (owner: "tune up"); 0.10 / 0.05 from the aim audit (level 3).

**2.20 The mouse pad (`PAD_DEG`, `PAD_LIFT`).** 240° of turning crosses the pad; at an edge the view cannot turn further that
way until he lifts the mouse (5 frames with no movement; he can lift on purpose) (`duel_env.py:2178-2184`, `pad_turn`
`:5484-5505`). Set from the owner's sessions (2026-10-06: longest one-way turn 219°, pauses in long turns 125 ms). Both.

**2.21 The pull to level (`LEVEL_PULL`).** With no enemy seen for 0.5 s his pitch is multiplied by 0.95 a frame
(`duel_env.py:1129-1137`, `:11548-11551`); off while an enemy is in view. Both (`duelbot.py:1511`). B-275 (v0.4.3), live.

### His fingers

**2.22 The left hand (`FINGER_HOLD`, `KEY_RATE`, `KEY_BURST`, `KEY_EVERY`).** Movement keys and the weapon key: decided
every 4th frame (10 a second); a finger that has acted waits 150 ms (thumb/jump 100 ms, little finger/crouch 500 ms); the hand
has a budget of 10 actions refilled at `KEY_RATE` a second (8 in the run, `.cmd`; code default 4) (`duel_env.py:123-139`,
`limit_keys` `:11064-11150`). A weapon switch is one action of the index finger (which also strafes right). Both
(`duelbot.py:1474`). Owner 2026-10-05 / 2026-10-08 (5 a second from v13; `KEY_RATE=8` since v13).

**2.23 The fire finger (`MOUSE_HOLD[0]`, `FIRE_HOLD`).** The fire button can change state at most every 7 frames (175 ms):
holding is free, clicking is at most ~2.9 a second (`duel_env.py:140-143`, `limit_keys` `:11128-11133`). All weapons. Both.
Owner 2026-10-07 ("he is spamming the lightning fire button") and 2026-10-08 ("up the clicks to 3").

**2.24 The zoom finger (`MOUSE_HOLD[1]`).** 150 ms between zoom changes (`:143`, `:11134-11139`). Both.

### The shot

**2.25 Fire timing (`FIRE_QL`).** Not a human limit but part of the flick: as Quake Live fires a driven bot's command, an
instant shot (rail, lightning, machine guns, shotgun, gauntlet) leaves on the frame of the command, from the eye after the
frame's first 8 ms substep, along the yaw of that substep (the start yaw + 8/25 of the frame's turn) and the final pitch, at
the enemy where he stood at the frame's start (`duel_env.py:2495-2523`, `:11826-11834`, `:11855-11858`); rockets,
plasma and grenades launch on the command frame too. All weapons. Both (the server is the game itself; the plugin sends the
press at once). 2026-10-20 (RESULTS 17:10: every shot had left one frame after the press; rail hits 35 → 56% on Blood Run
before training).

**2.26 The reload jitter (`RELOAD_JITTER`).** After a shot of a weapon with a refire of 0.4 s or more (rail 1.5 s, rockets
0.8, grenades 0.8, shotgun 1.0, gauntlet 0.4; `W_REFIRE` `duel_env.py:54`), the next shot is ready an extra
`min(Exp(mean 0.05 s), 0.12 s)` later (`:230`, `:11780-11782`): "nobody fires on the exact frame the reload ends".
Lightning and machine guns: none. Both (`duelbot.py:1552-1553`). B-58 (2026-10-04).

The hit itself (`step()` `:11920-11959`; the instant trace `:11937-11959`) uses his true view direction and the enemy's true box (no error added at the shot);
the machine guns' scatter (`MG_SPREAD` 1.4°, `:71`) and the shotgun's pattern are the game's, not limits.

### Pays that touch aim (being faded in v0.5.1)

**2.27** `JERK_COST` 0.00002 per degree a frame of change in the turn command (`duel_env.py:275`, `:11507`, `:11563`),
`FIRE_TOGGLE_COST` 0.003 per change of the fire button (`:232`, `:11784-11787`), the shot price (`SHOT_COST 0.10`, rail 0.2,
`.cmd`), `PREAIM_PAY` 0.05 and `WATCH_PAY` 0.03 at sightings. In v0.5.1 all of them are in the "other" part of a game frame's
pay, paid × (1 - `FADE_V`) (`duel_env.py:1510-1533`); `FADE_V` is 0.0 in `live.json` today, so they are still paid in full.
They are pay, not limits: nothing stops a jerky turn, it only costs. Simulator only.

---

## 3. The owner's concerns

### 3.1 "We're still treating tracking hitscan (LG/MG) the same as flicking hitscan (rail)"

**Which limits differ by weapon today, and which do not:**

| Limit | Rail | Lightning | Machine guns | Rockets / plasma / grenades / shotgun |
|---|---|---|---|---|
| Field of view, line of sight (2.1) | same | same | same | same |
| Tracking delay and focus (2.7-2.8) | same | same | same | same |
| Notice and surprise delays (2.9-2.10) | same | same | same | same |
| Sight error σ 0.6°, τ 0.15 s (2.11) | same | same | same | same |
| **Fast-target error cap (2.12)** | **0.001° (none)** | **1.5°** | 1.5° (the "other" cap) | 1.5° (the "other" cap) |
| Zoom (2.13) | any weapon, if zoomed | same | same | same |
| Flinch (2.14) | same | same | same | same |
| Inertia, flick cap, bandwidth, hand noise, pad (2.16-2.20) | same | same | same | same |
| Fire finger 175 ms (2.23) | same | same | same | same |
| Fire timing (2.25) | instant-shot rule | instant-shot rule | instant-shot rule | launch rule |
| Reload jitter (2.26) | yes | no | no | yes (shotgun, rockets, grenades) |

So the only *human* limit that tells a flick from a track is the fast-target cap, and it does so by the weapon in hand:
the lightning gun and the machine guns are treated alike at every `!aim` level (the "other" cap equals the lightning cap in
all three play files), and the rail alone is exempt. Everything else (delays, sight error, flinch, the whole hand chain) is
one model for every weapon. The reload jitter differs only by reload length.

**How a rail flick is limited (acquire, settle, one shot):**
1. Notice: the enemy must be in the 55° cone with a clear line to one point; he first "sees" him 125 ms after the first frame
   in view if he has focus (usually so at the start of a fight), 175-200 ms otherwise, plus up to 200 ms if the enemy came in
   more than 10° off the crosshair unexpected (2.9-2.10).
2. Turn: the command passes through the inertia (0.75 a frame for big commands), the 1,200°/s cap, the 4 Hz bandwidth that
   opens with speed, and hand noise of 10% of the view speed per frame (2.16-2.19). The "settle" is the inertia and the
   bandwidth slowing the last degrees; the noise at the moment of the click is set by how fast the view is still moving.
3. Judge: his read of where the enemy is carries 0.6° (0.24° zoomed) of slowly wandering error, plus any flinch; with the rail
   in hand no fast-target error, however fast the enemy crosses.
4. Shoot: the shot leaves on the command frame along the first substep's yaw at the enemy's frame-start place (2.25); the
   next rail 1.5 s later plus 0-120 ms jitter.

**How lightning tracking is limited (continuous):** the same chain every frame, with three differences in effect:
(a) the error is not one judgment but a continuous AR(1) wander with 0.15 s memory that the tracking has to live with;
(b) the fast-target term adds up to 1.5° whenever the enemy's bearing moves more than 20°/s, so in most fights his σ is
2.1° per axis against a target 2.5° wide at 340 units (half-width atan(15/340)); because ω is the bearing's speed in the
world, a perfect tracker pays it as much as a poor one; (c) the read delay is 50 ms for the first 2 s of a fight and 125 ms
after (focus), which matters for following a strafe reversal more than for a single flick. The hit is checked every 50 ms
tick against the true box along his true view.

**The calibration data behind today's numbers:**

| Date | Data | Result |
|---|---|---|
| 2026-10-08 (aim audit) | The owner in the reflex room; free-for-all logs of people | Level 3: tracking 44.8% (owner 40.1%), lightning 65.8 damage/s (57.7), first rail shot 68% (87.5%) |
| 2026-10-12 | v0.2's end, self-play | The level a weak lever; 125 ms delay brings LG to 33.4% and takes rail 40.0 → 33.4%; `PERCEPT_SPEED` 0.025 brings LG to the pros' 31.6%, rail -4.5 |
| 2026-10-15 | 4,662 pro demos, first rail shot by angle | He is not slower to the rail than the pros where he fires; he fires less at wide angles |
| 2026-10-20 | Delay sweep, every fix on | LG 41 / 38 / 33.5% at 125 / 150 / 175 ms vs the pros' 31%; rail 42 / 35 / 33% vs 42% |
| 2026-10-26 10:15 | Simulator vs real servers (94 games) | Sim LG 0.50 / RG 0.60 / RL 0.52, servers 0.38-0.39 / 0.40-0.45 / 0.45; `PERCEPT_SPEED` 0.05 in self-play |
| 2026-10-26 16:30-21:10 | Self-play, v0.4.2b's end, 8 maps × 8 games, against the pros' 32.7 (LG) / 43.5 (rail) | One cap 5°: 37.4 / 38.2; by weapon rail 3 / LG 10: 34 / 43.6 |
| 2026-10-26 night | The owner's play tests (his strafe 32-36°/s at 340 u) | LG on target 15-20% of firing time, 5° error: "way too weak on lg"; one cap 1.5°, rail 1.0° |
| 2026-10-27 | (no entry yet) | Rail cap 0.001 at default and better, 1.0 at worse |

The pros' figures are hit rates in duels between pros, who dodge well; the owner's rail yardstick is 50-60% and the people on
his server hit 53.9% (B-228, 2026-10-12). Self-play numbers measure him against himself, whose movement is not people's
(RESULTS 2026-10-26 21:10: "calibrate the aim against people's movement, not self-play").

### 3.2 "The hitscan limits are affecting projectiles"

**Yes, at the code level.** The cap is chosen by the weapon in hand (`duel_env.py:6891-6895`): railgun → `_RG`, lightning gun
→ `_LG`, **anything else → `PERCEPT_SPEED_MAX`**. With rockets, plasma or grenades in hand at `!aim default` the fast-target
term is the same as with the lightning gun (cap 1.5°, slope 0.075), and the base error (0.6°), the flinch, the delays and the
hand are the same for every weapon. This was partly intended: the 2026-10-26 10:15 calibration set `PERCEPT_SPEED` by the
lightning-to-rocket hit ratio (1.07 → 0.91, real ~0.85) with one cap for all weapons; the per-weapon caps that came later
(rail, lightning) left the projectiles on the shared cap.

**Where the error goes, precisely.** The error is added to the *perceived enemy place* (`known`) in `observe()`
(`:6899-6903`): it changes his **inputs** only. It is not applied to his view (the view moves only by his own commands
through the hand chain), and not to the shot (an instant shot is traced along his true view at the enemy's true box; a
projectile is launched along his true view and flies with the game's physics; damage and splash use true places). He aims
off because he believes the enemy is a little off.

**How it meets the lead.** With a rocket launcher or the plasma gun in hand, the lead inputs (`_v14`, `duel_env.py:8114-8148`,
`LEAD_SPEED` for RL and PG only, `:798-799`) solve for where a projectile fired now meets the enemy: from the perceived place
(sight error + fast-target term + flinch, then `RANGE_FIX`'s distance error) and the perceived velocity (200 ms old, ±20%
drifting scale, `VEL_FIX`), with the floor under the meeting point; they give the meeting point's angles to his crosshair
(coarse ±30° / fine ±2° yaw, ±15° / ±2° pitch), the flight time and the floor's angle. `RL_AIM`'s inputs (`_raim`,
`:7424-7450`) give the backstop of a rocket fired along his view, its distance against the perceived enemy distance and how
close the burst would be to the perceived enemy, and the floor aim point by the same perceived place and velocity. So a
projectile's lead carries the fast-target error on the *place* and, separately, `VEL_FIX`'s error on the *velocity*: the
target's speed is penalised twice, once as a blurred place and once as a misread velocity. The grenade's arc inputs (with the
launcher in hand) are built from the same perceived place.

**Size, for a sense of scale (my arithmetic).** At 500 units, 1.5° is about 13 units sideways; a rocket's splash radius is
120 (`P_RADIUS`, `duel_env.py:60`), plasma's 20, a player box 30 wide. So the fast-target term is small against a rocket's
splash and comparable to a plasma ball's direct-hit margin. No calibration has looked at the projectiles under the per-weapon
caps; in the 2026-10-26 self-play calibration rockets read 52-54% at every setting (the pros 31.2%), "high overall because he
fires them close" (`RUN_v0.5.0.md:71-72`).

---

## 4. The checks' tools

- `tools/duel_eval.py --react-ms / --acquire-ms` (default: his checkpoint's `react_ms` / `acquire_ms`) and
  `--opp-react-ms / --opp-acquire-ms` (default: the opponent checkpoint's) (`duel_eval.py:401-406`, `:453-455`) go through
  `sim/test_suite.py`'s `set_delays()` (`test_suite.py:362-392`, B-226): one number for all seats where they agree, else one a
  seat (`env.react_seat`, `env.acquire_seat`; `SEAT_DELAYS`, `duel_env.py:221-227`; the history kept is sized by the
  largest). Scripted seats keep his tracking delay and the simulator's own 200 ms notice delay. Since v0.3.8 the run's checks
  give both seats his delay (owner, `docs/v0.3.8/RUN_v0.3.8.md:103`).
- Only the two delays are per seat. Everything else here (sight error, fast-target term and caps, flinch, hand, fingers) is a
  module-level value read from the check process's environment at import: both seats of a check play under the same values,
  whatever the opponent was trained with. The checkpoint's `env_vars` are not read by `duel_eval.py` for these.
- The run's checks play each save at its own rule fade (`--rule-fade-g`), unrelated to aim.

---

## 5. Simulator and server: what differs

Everything in section 2 runs in both, through the shared `observe()` and the plugin's copies of `step()`'s sight, hand and
finger code, with the values from `env_vars`. The differences I found:

1. **The flinch's trigger.** Simulator: damage from another player only (`hitby`, `duel_env.py:12066`). Server: any drop of
   health + armor of 3 or more in a frame (`duelbot.py:428-436`, `:2227-2228`), so his own rocket splash, falls and lava
   flinch him on the server and not in training.
2. **No network latency on his side.** The plugin reads the server's state every frame in-process; a person sees him through
   their ping and the client's interpolation. Not a limit in the code; an asymmetry the limits do not model.
3. **Scripted opponents** (training's tricks, the Nightmare stand-in) have none of these limits; on the server the opponent is
   a person.

---

## 6. Inconsistencies found while reading

1. **The rail cap in the docs is out of date.** `docs/v0.5.1/RUN_v0.5.1.md:18` and RESULTS 2026-10-26 21:10 say rail 1.0°
   (and `!aim` rail 2 / 1 / 0.33°); the run (`live.json`) and the play files use 0.001 at default and better, 1.0 at worse,
   since 2026-10-27. `docs/v0.5.0/RUN_v0.5.0.md:47-52` still shows the caps of the afternoon (rail 5 / 3 / 2, LG 15 / 10 / 5).
2. **`AIM_LEVEL` does not set the delays**, though `aim_settings` lists them and the comment says it does (`duel_env.py:186`,
   `:200-201`). The trainer's own default `--react-ms` is 50 (`train_duel_rnn.py:1441`), the module's `REACT_FRAMES` 2 (50 ms),
   the run's 100: anything that builds a simulator without the flags gets 50 ms.
3. **The effective delays are not the nominal ones**: with focus, 50 ms tracking and about 125 ms to notice at the start of a
   fight, 125 ms and about 200 ms after 2 s of sight (2.8-2.9). The 2026-10-20 sweep measured "tracking 50 ms late" at every
   setting from 100 to 175 ms, which fits a floor of this kind.
4. **`!aim max` is not "every human limit off"**: the level-scaled values go to ~0 and the delays to 25 ms, but the inertia,
   the flick cap, the 4 Hz bandwidth, the pad, the finger limits, the fire hold, the reload jitter, the field of view, focus,
   and `VEL_FIX` / `RANGE_FIX` / `PROJ_FIX` / `SENSE_MINOR` all stay.
5. **Perception depends on the weapon in hand.** Switching to the rail removes the fast-target term at once (the error then
   relaxes over ~0.15 s); a person's eyes do not change with the gun. A policy could learn to hold the rail to see better.
6. **The zoom scales only part of the sight error** (the base, not the fast-target term or the flinch).
7. **The code default of `PERCEPT_SPEED_MAX` is 3.0** (`duel_env.py:247`); a tool or check started without the run's
   environment uses 3°, and without `live.json` uses `PERCEPT_SPEED` 0 (the level's).

---

## 7. Open questions and possible changes (for later; nothing to act on now)

- **Per weapon class, not per weapon:** separate limit sets for tracking (lightning, machine guns), flicking (rail, shotgun?)
  and projectiles (rockets, plasma, grenades), each calibrated on its own measure (time on target / damage per second for
  tracking; first-shot hit by angle and time for flicks; direct and splash hits by distance for projectiles).
- **Perception by what he does, not by what he holds:** for example the fast-target term on the target's speed *relative to
  his view* (retinal slip: small when he tracks well) instead of the world bearing, which would make it a limit on tracking
  quality rather than a flat tax on lightning; and no switch-dependent eyesight.
- **The projectiles' lead:** whether the place error and `VEL_FIX` together double-count the target's speed for rockets and
  plasma; whether projectiles want their own cap (or none).
- **Calibration against people:** the self-play numbers misled on 2026-10-26; the owner's ~5,000 public free-for-all games
  (B-251) and the servers' duel logs could give people's reaction, flick speed, tracking error and hit rates by weapon and
  distance, and the `!aim` levels could be placed among them.
- **Focus:** measure whether the 50 / 125 ms swing matches people's bursts, or replace it with one delay.
- **The flinch:** its size (6° from one rail hit, about 7° σ under steady lightning fire) and the server's trigger (own splash,
  falls) against B-215's "a bit too much".
- **The rail's exemption:** with no fast-target term, the rail's remaining limits are the delays, 0.6° of sight error, the
  hand and the reload; whether the rail now outruns the pros' first-shot curve (B-255's yardstick) has not been checked.
- **Checks:** per-seat sight and hand limits, so a check between two networks trained under different limits plays each under
  its own.

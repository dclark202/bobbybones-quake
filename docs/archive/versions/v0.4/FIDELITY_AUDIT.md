# The simulator against Quake Live: fidelity audit and measurement plan (2026-10-19)

The owner, 2026-10-19: "please take some time to make sure the simulator is as exact a replica of quake live as possible".
This is a reading job. No server, no Docker, no training, no repo file changed. What I read:
- `ql-bot-v036/sim/duel_env.py`, which v0.3.6 trains from. Its run file is `ql-bot-v036/scratch/run_duel_gru_v0_3_6_r2.cmd`.
- `sim/sim_api.c`, `sim/q3/bg_pmove.c`, `sim/qsim.py`, `minqlx/botctl.c`, `plugins/duelbot.py`.
- Every game-against-simulator entry in the results log: `docs/results/` and `data/docs_old/docs/results/`.
- `docs/BACKLOG.md`.

**Switches on in today's run (v0.3.6).** `QL_FLOAT QL_FWD QL_LAND QL_JUMP QL_MOVE RL_QL GL_QL SHOT_MASK LAVA SOLIDS
ITEM_DROP WALK_FIX PRO_WAYS NEAREST DROPS AUTO_SWITCH PROJ_SEE OVERTIME`, with `AIM_LEVEL=3`. The verdicts below are
for the simulator with these switches on.

**Verdicts.** **match**: measured in the game and within a few percent. **switch**: a known difference, fixed behind a
switch (on today). **never**: never measured in the game. **wrong**: known or very likely wrong. **design**: a
fairness choice, not fidelity.

**Out of scope here.** B-267 (branch `v036-stairs`, another helper) covers stairs, step-up on real stairs, the stair
"slide", ledge grabs and ledge jumps, and splash on step edges. I only point to it.

---

## 1. Every mechanic, one row each

### 1a. Movement

| Mechanic | How the simulator does it | Measured against the game | Verdict |
|---|---|---|---|
| Ground acceleration, friction, stopping | ioquake3 `PM_WalkMove`/`PM_Friction` (`sim/q3/bg_pmove.c`); `g_speed 320`, accel 10, friction 6 | physlab B-258 (RESULTS 2026-10-16 01:25): from a stand, friction, circle strafe, crouch: 120/120 within 5% | match |
| Air acceleration, strafe curve, no air control | Q3 `PM_AirMove`, accel 1, no air control (cvars `AirAccel 1`, `AirControl 0`, `StrafeAccel 1`, `WishSpeed 400`) | physlab: forward+strafe 408/408, strafe alone 216/216, with turning 36/36 | match |
| Forward key alone above 320 (QL's own push) | `QL_FWD`: 0.2059 x (640 - speed) a second (`PM_QLForward`) | physlab: 180/180 with forward held at 0 to 700; fitted to 0.0001 u/s a frame | switch (on) |
| Velocity snapping | `QL_FLOAT` turns Q3's `SnapVector` off (`qsim_snap(0)`) | rjlab: gravity exactly 20 a frame, plain jump 47.25 high, lands on frame 28 | switch (on) |
| Landing (the fall speed is not turned into speed along the floor) | `QL_LAND` (`QL_LAND_STAT` in `bg_pmove.c`) | physlab: launched up at 400 with 320 along: the game 320, Q3 447 | switch (on) |
| Jump, auto-hop, chain jump (+110 within 500 ms, none within 100 ms) | `qsim_params`, then `QL_JUMP` (`qsim_params4`) | physlab: chains 360/360, landings with jump pressed 0 to 6 frames late 288/288 | switch (on) |
| Bobby's own auto-hop on the servers | the game re-jumps only for a client whose userinfo carries `cg_autoHop 1`; `BOBBY_AUTOHOP=1` in `duelbot.py` / `ffabot.py`, **off by default** | physlab found it. No server script I read sets it (`tools/duel_server.sh` does not; I did not check the public server's env) | **wrong unless set: check the servers** |
| "Double jump" (jump held when a move lands on a higher floor), air steps | `QL_JUMP` (b), (c); `AirStepFriction 0.03` | physlab: climb on 40-unit ledges 56/56, ramps course 84/84 | switch (on) |
| Step height 22 | `QL_MOVE` -> `pm_stepSize 22` | the cvar is read (`pmove_StepHeight 22`); the climb course; real stairs not measured | switch (on); real stairs are B-267 |
| `StepJump 1`, `StepJumpVelocity 48` | not modelled | "no case needed them" (B-258) | never; B-267 |
| Circle jump | Q3 physics with the `QL_*` switches | physlab: from a stand, circle strafing | match |
| Crouch: speed 0.25, box top 16, eye 12 | Q3 `pm_duckScale`; `TOP_DUCK`, `VIEW_H_DUCK` | physlab crouch case (speed only) | match (speed); box not measured |
| Crouch slide, ramp jump, QL double jump | not modelled | cvars `CrouchSlide 0`, `RampJump 0`, `DoubleJump 0` on our servers | match (off in the game too) |
| Overbounce | whatever Q3's code does without snapping | never | never (rare in duels) |
| Jump pads | `qsim_add_trigger` type 0 (Q3 `AimAtTarget`), touched after each move | physlab pads course: 24/24 within 5%; the push lands about 10 ms late in the frame | match |
| Teleporters: exit, speed, view | origin +1, velocity 400 along the exit angle, `pm_time 160` with knockback, view turned to the exit angle (`touch_triggers` in `sim_api.c`) | physlab, one teleporter case; Blood Run 30 cases 520/520 | match (one case) |
| Telefrag | **not modelled** (no player-to-player overlap test) | never | never (rare) |
| Players colliding with each other | **not modelled**: `sim_trace` traces the world only, so players pass through each other | never | **wrong** (the game: solid bodies) |
| Fall damage | in Python: `delta = (vz of the frame before landing)^2 x 0.0001`, 5 above 40, 10 above 60 (`step()`, `FALL_MED/FAR`) | never; open in B-53, B-22, B-258 | **wrong in detail** (section 2, gap 8) |
| Water: wading | `QL_MOVE`: `pm_wadeScale 0.8` in `PM_WalkMove` (`1 - 0.2 x waterlevel/3`) | wading 298.7 measured with the feet in water (2026-10-09); not measured at waist depth | switch (on) for feet; waist depth never |
| Water: swimming | Q3 `PM_WaterMove` with `pm_swimScale 0.5` | never. The game's cvar `WaterSwimScale` reads 0.6 (physlab, 2026-10-16); the 2026-10-09 reading said 0.5. `QL_FWD` is off in water | **likely wrong** (160 against 192 u/s) |
| Lava, slime | `LAVA`: 30 x depth (slime 10) at once, then every `LAVA_TICK` | poollab (2026-10-09): feet 30 every 0.7 to 0.8 s, waist 60 | match (lava); slime never (not on the ten maps' ways) |
| Server frames against Bobby's moves | `DT=0.025`, three moves of 8/8/9 ms; `botctl.c` `set_bot_substeps` does the same on the server | validate.py (2026-10-02): one-step error 0; physlab per frame: 1 frame in 9,390 over 0.05 u/s | match |
| View turning inside a frame | the simulator spreads **pitch and yaw** over the three moves | `botctl.c` spreads **yaw only**: the substeps carry the frame's final pitch from the first move | small difference (pitch moves nothing on the floor; it sets the shot's direction, gap 1) |
| Pitch limit | Python clamps to +-89; the library's Q3 `PM_UpdateViewAngles` clamps itself | the game holds 87.89 (rjlab) | small; check that the library clamps (B-252 note) |
| 125 fps people against Bobby's 3 moves per 25 ms (120 fps) | design | not a fidelity question | design note: 8 ms against 8.33 ms moves |

### 1b. Weapons

| Mechanic | How the simulator does it | Measured against the game | Verdict |
|---|---|---|---|
| **When a shot leaves, and with which view** | RL with `RL_QL`: on the command's frame, muzzle after the first move, **view at the frame's end**. Every other weapon: one frame after the command (`fire_q`), from the eye after the whole frame, with the view at that frame's end | weaponlab's frame counts (2026-10-03) set the one-frame rule. rjlab (2026-10-15) then showed that harness's convention was 3 frames off for rockets | **known wrong for rockets on the server; never re-measured for the others** (gap 1) |
| The plugin's fire delay | `duelbot.py:1414`: whenever the env has `fire_q`, **every** press goes to the game one frame late, rockets included | not checked against `RL_QL` | **wrong since v0.3.1** (gap 1) |
| Rocket: speed, direct hit, splash, push, prestep | `RL_QL` (`_explode_ql`): 1000 u/s, 41 units on its first frame, 100 direct, 84 x (1 - d/120) to a box grown by 0.5, whole points, push 5/pt x 100 falloff x 1.1 self / 0.9 others | rjlab: 486 test-map jumps, rise within 5% 480, damage within 1 point 486; at others 0 to 140 units within 2 to 6 points | match |
| Rocket push on a player standing, or holding forward from a stand | same | 5 to 15 units short (B-252 note) | small known difference |
| Rocket jump, running | same + `QL_FWD` | running rocket jumps 30/30 within 5% | match |
| Grenade: launch, loft, bounce, fuse | 700 u/s, +0.2 loft, bounce keeps 0.65, 2.5 s fuse; `GL_QL` keeps the rest of the frame at a bounce | weaponlab set 4 (2026-10-10): path frame by frame; rest points 864/528/572/425 against the game's 824/552/583/366 | switch (on); within 5 to 15% |
| Grenade splash on others (falloff, push) | the old path: `SPLASH_NEAR` 20 shift, `SPLASH_KNOCK` 1.07 / self 1.3, radius 150, 100 damage; `GL_QL` CanDamage with 5 points | direct hit only (100, push 542). **Splash against distance never measured.** The 20-unit shift came from weaponlab's aim error (rjlab proved it for rockets) | **likely wrong** (gap 6) |
| Grenade at own feet | same | the game 43 damage / 277 lift with the blast 42 units away. Not re-run since `GL_QL` | never with `GL_QL` |
| Plasma: speed, rate, damage | 2000 u/s, 20 per hit, 100 ms; moves on its first frame; one frame after the command | weaponlab set 2: first hits on frames 9 and 17 (the old harness's convention) | match by that harness; timing as gap 1 |
| Plasma splash, push, climbing | `SPLASH_NEAR` 20 on a radius of 20 (it doubles the reach), 15 damage, push 1.07 / self 1.3 | splash 16/16/10/3 at 0/10/20/30 units and own feet 8 / 95 matched, with the shift fitted to the same biased aim. **Wall climbs never measured** | **suspect** (gap 6) |
| Rail | 80, 1.5 s, push 0.85 (340 u/s), point trace from the eye with a 2-unit box (`qsim_rays_each_m`) | weaponlab: 80 / 340 / frame 2 | match (damage, push); timing as gap 1 |
| Rail through bodies | stops at the first box | duel-irrelevant | n/a |
| Lightning gun | 6 per 50 ms, range 768, push 1.167 | weaponlab: 120/s, hits at 700, misses at 800 | match |
| Machine gun, HMG damage and rate | MG 5 / 100 ms, HMG 8 / 75 ms | weaponlab set 2 | match |
| MG / HMG spread | `MG_SPREAD` 1.4 degrees uniform disc (the Q3 source) | never (B-107b) | never |
| Shotgun | 20 pellets x 5, **gaussian 3 degrees, random**; expected-hits model on one line of sight | mean damage at 100/300/600 matched (100/61/25). The owner: "SG has a pattern" (B-107b) | **wrong in spread** (mean right, variance and close-edge hits wrong) |
| Gauntlet | 50 / 400 ms, reach 52 | weaponlab: 50 per ~425 ms, hits at 40, not at 70 | match |
| Knockback scale | 5 u/s per point (`g_knockback 1000`, mass 200), per-weapon factors `W_KNOCK` | rockets, rail, LG, MG, HMG, SG, PG, gauntlet measured direct | match (direct hits) |
| Own splash damage halved | `SELF_FACTOR 0.5` | rockets (rjlab), plasma, grenade | match |
| Weapon switch time | `SWITCH` 0.425 s; starts only after the reload ends | 17 frames (weaponlab set 3), with the old harness's frame convention; switching during a reload never measured | match (time, ±1 frame); never (during a reload) |
| Empty-weapon auto switch | `AUTO_SWITCH`: 0.5 s empty click (Q3 source), then the game's order | the order is QL's; the 0.5 s never measured | never |
| Hit boxes | 30 x 30 x 56 (`MINS/MAXS`), crouched top 16; no head zone | Q3 values; never measured. QL has no headshots in duel, but `g_headShotDamage_*`-type cvars should be read | never (likely right) |
| Projectile against a body | segment-box test per frame, positions at the frame's end | never | likely right |
| Hitscan against a body: when | traced after both players moved this frame | never (the game: Bobby's command runs at its own moment in the frame) | small |
| People's lag compensation (unlagged) | not modelled (self-play) | n/a: a server-side matter for people's shots at Bobby | design note |

### 1c. Items, health, armor, spawns

| Mechanic | How the simulator does it | Measured against the game | Verdict |
|---|---|---|---|
| Pickup amounts (first pickup, empty) | `ITEM_DEFS`, `LOADOUTS` | itemlab (2026-10-04): every weapon, ammo box, health and armor | match |
| Pickup reach | horizontal circle under 36, height under 56 | 7,767 pickups from the public server's logs (2026-10-12): the game's reach is a 36-unit box at any jump height; the simulator's lies inside it | match (a bit stricter) |
| Item positions | `ITEM_DROP`: dropped to the floor like the game | maplab: every item within 2 units on eight maps | switch (on) |
| Item lists per map (duel) | the map file's items, `notfree` read | maplab: identical on the maps checked | match |
| **A weapon picked up when already owned** | adds a full pickup up to `AMMO_MAX` | never (B-14). In Q3 you get "up to the pickup amount, else +1" | **likely wrong** (gap 7) |
| **Ammo caps** | `AMMO_MAX` 25 rockets/slugs/shells/grenades, 150 LG/MG/PG/HMG | never (B-14) | never |
| Health and armor caps | small health and mega to 200, +25/+50 to 100, armor to 200 | Q3 rule; never measured above the first pickup | likely right |
| Armor absorption | `ceil(0.66 x damage)`, one tier for all armors | rjlab: 100/100 and 50/25 exact | match (red/yellow tiers not separated; read the tier cvar) |
| Decay above 100 | 1 a second, health and armor | seen indirectly (rjlab: handicap 50 decayed above 50) | match (indirect) |
| Item respawn times | health 35 s, armor 25 s, weapons 5 s, ammo 40 s, mega 35 s from the pickup | weapon 5 s and ammo 40 s are cvars; the mega's 35 s was seen on a plugin-placed item (Campgrounds, 2026-10-09). Native mega, armor and health never | never (except the cvars) |
| Spawn stack | 125 health, 0 armor, machine gun with 100 rounds | the plugins' belief uses 125/0; never measured as such | never (likely right) |
| **Respawn delay after a death** | **none: he is back at a spawn point on the same frame** | never (B-22) | **wrong** (gap 3) |
| **Spawn point choice** | random among the half of the spawn points farther from the **enemy** (`_spawn`) | never (B-22). Q3: random among the furthest half from **where he died**, skipping occupied points. QL's duel rule unknown | **never; likely wrong** (gap 4) |
| Dropped weapons | `DROPS`: only on a kill by another, only the weapon in hand with ammo, never MG or gauntlet, 30 s | droplab (2026-10-08): 64 cases | match |
| Powerups | none | none on our servers (`plugins/powerups.py`) | match |
| Overtime | `OVERTIME`: +2 minutes while level, up to 10 periods | the servers' settings | match |

### 1d. Senses (fidelity of what can be seen and heard; the human limits are design)

| Mechanic | How the simulator does it | Measured against the game | Verdict |
|---|---|---|---|
| What blocks sight and shots | `SHOT_MASK`: solid brushes only (player clip lets them through) | maplab (2026-10-09): the game's clear lines | switch (on) |
| Things that block **sight** but not shots (non-solid detail, banners, trims) | nothing blocks sight that does not block shots | never | never (small; an offline map count tells) |
| **Seeing the enemy** | one line from his eye to the enemy's origin + 8 (the chest), inside a **circular** cone of 110 degrees (`FOV_COS`), under 4,000 units | never. The game shows any part of the body, on a 16:9 screen. At `cg_fov 100` that is about 115 x 84 degrees | **known difference** (gap 5) |
| Wall and floor sensing rays | 100 x 75 degrees (`FOV_H`, `FOV_V`): not the 110 cone of the enemy test | design inputs | design (the two cones disagree) |
| **Hearing** | spheres by distance only: running steps, shots, jumps 1,000 (`EAR_RANGE`); events 1,200 (`HEAR_EVT`); "heard moving" 800 (`HEAR`); rail and LG hum 500; no walls | never (B-53, "a guess") | **likely wrong** (gap 9) |
| Footsteps | running over 200 u/s on the floor, not crouched or walking | Q3 rule: no steps at the walk key; never measured in QL | likely right |
| Item respawn and pickup sounds | heard within 1,200 | never | as hearing |
| Enemy projectiles seen | `PROJ_SEE`: in the view cone with a clear line | design | design |
| Reaction, flick cap, hand noise, finger limits, key rate | `AIM_LEVEL=3` and the rest | the owner's reflex rooms and logged play | design (not fidelity) |

---

## 2. The gaps, ranked by what they could cost him

The scale: what each gap does to his movement speed, rockets, rail, and positioning. Each gap gets a concrete
measurement. The method is the one physlab and rjlab proved:
1. A scripted bot runs through `set_bot_input` with three moves a frame, as the plugins play.
2. Every frame is recorded, and each case is run twice (the game was deterministic in 288 and 134 pairs).
3. The case is replayed in the simulator with the same inputs from the same start (`tools/phys_sim.py`,
   `tools/rj_compare.py`).
4. Every difference becomes a switch, off by default, and is proven identical when off by fixed runs (ident16) and
   `tools/ffa_check.py`.

### Gap 1. The shot's frame and direction: the simulator, the plugin and the game disagree (rockets, rail, LG)
- **What is wrong.** Since v0.3.1, `RL_QL` fires a rocket on the command's frame. The plugin (`duelbot.py:1414`) still
  holds every press one frame, rockets included. So on the servers **every rocket leaves 25 ms later than he learned**.
- **What that does to rocket jumps.** A jump with the shot on the jump's frame becomes a jump with the shot one frame
  after. By rjlab's table that is a rise of 264 against 319: a sixth lower. v0.3.6's rocket-jump runs will not carry over
  as trained.
- **Which view fires.** In the game the weapon fires inside the frame's first move. `botctl.c` gives that move the
  frame's final pitch but only a third of the frame's yaw turn. The simulator fires with the view at the frame's end.
  On a flick of 30 degrees a frame, the shot leaves 20 degrees away from where it would in the game: rail and rockets on
  flicks are wrong. On slow tracking (LG) the effect is small.
- **The one-frame rule for the other weapons** (rail, LG, MG, SG, plasma, grenades) comes from weaponlab's frame count.
  rjlab showed that harness was 3 frames off for rockets. So the one-frame delay may be an artifact too.
- **Is the delay right?** The plugin's delay matches the simulator's for those weapons, so sim and server agree today.
  But if the game fires them on the command's frame, Bobby pays an extra 25 ms on every rail and LG shot, against the
  game and against people.
- **Measure** ("firelab": rjlab's harness, a new test set; about 45 minutes on a private server, test map):
  - each of the nine weapons fired from a stand, then while turning at 0, 5, 15 and 30 degrees a frame;
  - pitch changes of 0, 10 and 30 degrees in the fire frame;
  - every case twice.
- **Record:**
  - the missile's first frame, position and velocity (botctl `missiles`): its direction says which move's view fired
    it;
  - for hitscan, a target bot placed at yaw offsets 0 to 25 degrees from the frame's start view (damage on it says which
    view fired; rail at 1,000 units, a 1-degree grid).
- **Simulator side:** replay with `RL_QL` and the hitscan path; per weapon the frame offset and view rule.
- **Likely fix:**
  - in the simulator, `FIRE_QL=1`: every shot on the command's frame, with the first move's position, the final pitch
    and a third of the yaw turn;
  - in the plugins, stop holding the press for any weapon the simulator fires on the command's frame. Today that means
    the rocket at least, a one-line change.
- **Proof on the server:** `OBSDUMP=1` and a rocket-jump run of Bobby with the session log.

### Gap 2. The game's own numbers are in cvars, and only the movement ones were ever read
- **What is missing.** Quake Live exposes its weapon and rule constants as server cvars (the `g_*`, `weapon_*`, `pmove_*`
  families: per-weapon damage, splash radius and damage, velocities, reload times, knockback factors (self ones too),
  LG range, starting health, armor and ammo, respawn delays, armor tiers, item timers).
- **What was read.** The audit of 2026-10-09 and physlab read only movement and a few rule cvars.
- **Measure:** on a private server, dump every cvar. Use rcon `cvarlist` with a prefix per family, or the plugin's
  `minqlx.get_cvar` over a name list. Write it to a file, and use `tools/rcon.py --wait 30`: big output plus an rcon
  client that leaves can freeze the game.
- **Cost:** 15 minutes. It settles or narrows a dozen rows above: grenade and plasma splash radius and damage,
  per-weapon knockback, switch, raise and drop times, ammo caps, respawn delay, armor tiers, health and armor respawn,
  starting stack. It also says which of gaps 3, 6 and 7 need a real-game measurement at all.
- **Simulator side:** a table of cvar name, game value and simulator constant. Every disagreement goes into the
  measurement list.

### Gap 3. No respawn delay (positioning and item control after a frag)
- **What is wrong.** In the simulator a dead player is back at a spawn point on the same frame. In Quake Live a dead
  player waits: Q3 allows a respawn after 1.7 s, and QL forces one after a delay that a cvar sets.
- **Why it matters.** The seconds after a frag are when the winner takes the mega or the red armor, or sets up on the
  spawns. In the simulator those seconds do not exist. That understates what a frag is worth in time, and what item
  control after a frag is worth.
- **Measure (no server).** From the session archive (`data/duellive/sessions/*/events.jsonl` deaths plus `frames.csv`
  health and positions) and the pro demos' obituaries in `T:/quake-demos`, take the time from each death to the next
  frame alive at a spawn point. Bobby taps fire (`duelbot.py:1623`), so his delay is the least the game allows. People's
  and the pros' delays show what is normal.
- **Cost:** an hour of light scripting, one process.
- **Simulator side:** `RESPAWN_QL=<min,max>`: the dead player is out of play (not seen, not heard, takes nothing) for
  that long.

### Gap 4. The spawn point rule (spawn control, openings, believed enemy place)
- **What the simulator does.** A random point among the half of the map's spawn points farther from the enemy's
  current place.
- **What the game might do.** Q3 takes a random point among the half farthest from where the player died, and skips
  occupied points. QL's duel rule may differ, for example by keeping clear of the enemy's line of sight.
- **Why it matters.** The rule decides spawn kills and the pros' "spawn control". It also decides the believed enemy
  place after a frag (`v02_bel`, `EN_STACK` spawn reset).
- **Measure (no server).** For every respawn in the pro demos (thousands of duels) and in our sessions, record:
  - the chosen point and the other candidates;
  - the victim's death place;
  - the killer's place.

  Then fit the candidate rules: farthest from the death, from the killer, out of the killer's sight, random.
- **Cost:** about an hour.
- **If unclear:** 30 scripted deaths on a private duel server (scripted death place, scripted enemy place), about
  20 minutes.
- **Simulator side:** `SPAWN_QL=1` with the fitted rule; the stand-in check again.

### Gap 5. Seeing the enemy: one point and a round cone
- **What the simulator does.** He sees the enemy only when the line from his eye to the enemy's chest is clear. A head
  over a ledge, or a shoulder past a corner, is unseen. Yet his rail can hit it: the hit test uses the whole box.
- **The cone.** The view is a circle of 110 degrees. A 16:9 screen at `cg_fov 100` is about 115 degrees wide and 84
  high. So he sees enemies far above or below that a player would not, and misses some at the screen's wide corners.
  The wall rays use yet another frame (100 x 75).
- **Why it matters.** High ground, peeking, holding angles: positioning, the owner's priority 4. It is also fairness:
  "he should only know what's in view".
- **Measure:**
  - Offline (no server): on recorded session frames, compare the one-point test with a 9-point test (eye, head top,
    shoulders, knees, feet) and a 16:9 frustum. Count the frames where they differ, per map. This needs the library's
    lines (`qsim_lines_m`) in one low-priority process.
  - The FOV number: ask the owner his `cg_fov` and aspect ratio (his client's settings are never read or changed).
- **Simulator side:** `SEE_QL=1`: several points and a rectangular frustum. A design decision for the owner, since it
  makes him see more.

### Gap 6. Grenade and plasma splash were fitted to a biased aim (grenades and plasma: priority 3)
- **What rjlab found.** `SPLASH_NEAR` (splash acts 20 units closer) came from weaponlab aiming from 2 units above
  where the bot stood. `RL_QL` dropped it for rockets.
- **What still uses it.** Grenades and plasma still use the shift and the 1.07 / 1.3 push factors fitted on the same
  data. For plasma, whose radius is 20, the shift doubles its reach.
- **Never measured at all:**
  - grenade splash against distance;
  - grenade jumps since `GL_QL`;
  - plasma climbing up a wall.
- **Measure** (rjlab and weaponlab harness; about 50 minutes, test map plus Blood Run):
  - grenades onto the floor 0 to 160 units in front of a standing target, every 20;
  - grenades at own feet, pitch 60 to 87.89;
  - plasma at the floor in front of a target, 0 to 40 units, every 5;
  - plasma climbing: facing a wall, pitch 60 to 85, jump plus fire held for 1 s;
  - plasma at own feet.

  Record damage, armor, velocity and the blast point (botctl `missiles`) every frame.
- **Simulator side:** `GL_QL` and `PG_QL` take `_explode_ql`'s exact geometry (box grown by 0.5, whole points, per-weapon
  push factors from gap 2's cvars, no `SPLASH_NEAR`).

### Gap 7. Weapon and ammo pickups when already stocked (rockets economy, priority 2)
- **What the simulator does.** Standing on a launcher he owns adds a full pickup (10 rockets) every 5 s, up to 25.
- **What the game might do.** In Q3 a weapon pickup only tops up to the pickup amount, or adds one shot if he already has
  that many. The caps are unknown (B-14).
- **Why it matters.** It decides how much a held weapon spot is worth and how many rockets a stack carries, which feeds
  rockets, the owner's priority 2.
- **Measure:**
  - Offline first: `frames.csv` has every player's ammo per frame and `events.jsonl` every pickup. Compare ammo before
    and after each weapon pickup by people and Bobby: about 30 minutes.
  - Then itemlab on a private server for the caps (20 minutes): pick up the RL with 0, 5, 9, 10, 15 and 24 rockets,
    then ammo boxes until it stops rising, for every weapon. Also red armor at 150 and 190, and mega at 150.

### Gap 8. Fall damage (the legs take 11 to 24 points a minute)
- **What the simulator does.** Damage from the vertical speed of the frame before the landing (up to 20 u/s below the
  impact speed). It ignores what the vendored `PM_CrashLand` does:
  - the exact impact speed;
  - double damage crouched;
  - a quarter or a half in water;
  - none on `SURF_NODAMAGE` surfaces, such as some pad tops.
- **What the game does.** Its values (5 and 10 in Q3) were never measured (B-53).
- **Why it matters.** label_check counts 11.6 to 13.8 points a minute for the legs, and up to 24 on Campgrounds. That
  prices his ways, his drops and his jump choices.
- **Measure** (physlab drop course; 30 minutes): step off ledges of 64 to 512 units (the test map has the climb and
  ledges; add or reuse drops); standing, crouched, into water, onto a pad; every case twice. Record health per frame.
  Session logs also hold self-hits with no line of sight (falls).
- **Simulator side:** `FALL_QL=1` passes the library's own `EV_FALL_*` result out of `PM_CrashLand` instead of the Python
  estimate.

### Gap 9. Hearing (knowing where the enemy is; counterplay, B-214, B-241)
- **What the simulator does.** Spheres by distance, walls ignored.
- **What the game does.**
  - A client only gets the events of entities the server sends it, which means inside the potentially-visible set (PVS)
    of its cluster. A shot two rooms away across the map's vis is silent, however near.
  - Within the PVS, Q3's client volume falls linearly to nothing at about 1,330 units (80 at full volume, 0.0008 a unit).
    QL's client is closed, so its number is to be confirmed.
- **Why it matters.** His belief of the enemy (`v02_bel`, `en_heard`, `HOP_QUIET`) is built on these sounds.
- **Measure:**
  - (a) Offline, no server: the map files carry the vis data the library already loads (`qsim_cluster` exists;
    `CM_ClusterPVS` is in `sim/q3/cm_test.c`). Add a PVS test, then count on session frames how often the spheres say
    "heard" while the PVS says "not sent", and the reverse.
  - (b) Demos: in a pro's own demo the enemy's entity disappears when he leaves the PVS. Check that its gaps fit the PVS
    test.
  - (c) Optional, needs the owner (20 minutes on a private server): a bot fires, jumps and takes an item at 600 to 1,500
    units, in and out of sight, and he says heard or not.
- **Simulator side:** `HEAR_QL=1`: PVS gating plus a volume rule.

### Gap 10. Shotgun pattern, machine-gun spread (B-107b)
- **What the simulator does.** The shotgun's mean damage is right but its pellets are random (gaussian 3 degrees).
  The game fires a set pattern (the owner). `MG_SPREAD` 1.4 is a guess.
- **Why it matters.** The game's Nightmare bot fires the shotgun 36% of the time, and people use it close.
- **Measure** (weaponlab; 30 minutes, Campgrounds' flat run):
  - shotgun at a target bot at 300 and 600 units, moved sideways in 5-unit steps out to 60, 10 shots per step; damage
    per shot gives the pattern's profile, and shot-to-shot variance says fixed or random;
  - MG and HMG the same, at 600 and 1,000 units, 40 rounds per step.
- **Simulator side:** the pattern as a fixed table of pellet directions; `MG_SPREAD` and `HMG_SPREAD` from the fit.

### Smaller gaps, ranked lower
11. **Swimming**: `pm_swimScale` 0.5 against the game's cvar 0.6, and wading at waist depth. physlab in Cure's or Lost
    World's pool; 15 minutes.
12. **Players pass through each other**: corridor blocking, landing on a head, close gauntlet and shotgun fights. A
    body-box test in `sim_trace` against the other players (a library change). Measure: one bot walks into another
    standing still, and one jumps onto another; 10 minutes.
13. **Weapon switch during a reload, and the 0.5 s empty click**: fire the rail, then order a switch to RL at +1 to
    +40 frames, then fire. In the gap 1 session (the same harness); 10 minutes.
14. **Item respawn times, spawn stack, decay**: offline from `frames.csv` and `pickup` events (the gap 3 script).
15. **Rocket push on a player standing or holding forward**, 5 to 15 units short (B-252's own note); rjlab cases exist.
16. **Pitch limit 89 against 87.89** for rocket and grenade jumps at full look-down; plus the substeps' pitch
    (`botctl.c` moves pitch at once, the simulator spreads it). A check of the library's clamp; no server.
17. **Hitscan and sight rays are traced with a 2-unit box**, not a point (`qsim_rays_each_m`). Grazing shots past
    corners and grates by a unit are refused. One line per weapon in the gap 1 session, a shot along a wall.
18. **Telefrag** at a teleporter exit or spawn point. Rare in duels; not worth an evening.
19. **`BOBBY_AUTOHOP`**: check that the public and private server scripts set it (`docker exec <name> env`). If not,
    Bobby still does not auto-hop on the servers while every network is trained with it. A deploy check, not a
    measurement.
20. **Stairs, ledges, splash on steps**: B-267 (branch `v036-stairs`), not repeated here.

### Already well matched
These need no more work:
- The whole movement model: 1,892 of 1,892 measures within 5%, one frame in 9,390 off by more than 0.05 u/s.
- Jump pads and the teleporter's exit.
- Rocket jumps: rise within 5% in 480 of 486 cases, damage within a point.
- Rockets at others with `RL_QL`.
- LG range and rate, rail and MG damage and push.
- Armor absorption, exact to the point.
- Pickup amounts and the pickup reach: the simulator's reach is inside the game's.
- Item positions and lists, lava damage, wading speed, dropped-weapon rules.
- The grenade's path frame by frame.

The game was deterministic in every repeated case, which is what makes these replays exact.

---

## 3. Order for the evening windows (16:00 to 19:30, no training; about an hour each)

**Before each evening:**
- `docker ps`, `docker stats --no-stream`; a private container only (`NAME=qltest`), never the public server.
- Plugins mounted read-only so no image build is needed. One `docker build -t qlbot .` only if `botctl.c` must change.
- Share the window with B-267's helper: one private server, tests in turn.
- After each evening, nothing changes in training until the owner's go. Each finding is a switch, off by default,
  proven identical when off.

| Evening | What | Plugin | Time |
|---|---|---|---|
| 1 | Gap 2: dump every game cvar to a file (`cvarlist` by family, `--wait 30`) | rcon / a tiny plugin | 15 min |
| 1 | Gap 1: firelab, the nine weapons from a stand and turning, missile first frames and directions, rail against offset targets | rjlab harness, new set | 45 min |
| 1, after | Owner's call: the plugin's one-frame hold for rockets (live since v0.3.1); `BOBBY_AUTOHOP` on the servers (gap 19) | `duelbot.py` | his go |
| 2 | Gap 6: grenades at others 0 to 160 and at own feet; plasma at others, at feet, wall climbs | weaponlab or rjlab | 50 min |
| 2 | Gap 13: switch during a reload, empty click (same harness, same session) | weaponlab set 3 | 10 min |
| 3 | Gap 7: weapon and ammo pickups at every count, caps; red armor and mega above 100 | itemlab | 25 min |
| 3 | Gap 8: falls of 64 to 512, crouched, into water, onto a pad | physlab | 30 min |
| 4 | Gap 10: shotgun pattern and MG/HMG spread against an offset target | weaponlab set 2 | 30 min |
| 4 | Gaps 11, 12: swimming and waist-deep wading; two bots colliding | physlab | 25 min |
| 5 (optional, with the owner) | Gap 9c: what he hears at 600 to 1,500 units through walls; gap 5: his `cg_fov` and screen | a private server, his client | 20 min |
| 5 | Gap 4 check, if the offline fit is unclear: 30 scripted deaths on a duel server | a small duel plugin | 20 min |

**In the daytime, no server, one low-priority process at a time** (gaps 3, 4, 5, 7 offline, 9a/b, 14):
- the respawn delay, the spawn rule, the item timers and the spawn stack from the session archive and the pro demos;
- the PVS and the 9-point sight counts on session frames.

These need no evening and decide how much of gaps 3 to 5 is real before anything is built.

**Ranking of the fixes, once measured.**
1. Gap 1: on the servers today, and the reason v0.3.6's rocket jumps would not carry over.
2. Gaps 3 and 4: what a frag is worth in time and in place.
3. Gap 6: grenades and plasma.
4. Gap 7: the rockets' ammunition.
5. Gaps 5 and 9: what he knows; each needs the owner's word, since it changes his senses.
6. Then 8, 10 and the rest.

# BobbyBones: project notes for Claude

A Quake Live duel bot that plays real people on a real QL dedicated server, learns from them, and (later) gives players reports. Repo: `dclark202/bobbybones-quake` (public, GPL-3.0 because of the bundled minqlx). Local path: the `ql-bot` folder in the owner's home directory (rename to `bobbybones-quake` only when no containers are mounted from it).

## The owner's goals (read first)
- **Winning = win rate.** Items and routes are only a means. Judge every change by match WIN RATE (frag diff only breaks ties) against a control group of plain built-in Nightmare bots, never by route metrics alone. Promote only what beats the control group.
- **Nightmare bot is the base for every layer**, and **every layer is trainable**: routing, item desire, fight/stack/push, movement style, aim, weapon choice, then opponent adaptation. Our code only overrides Nightmare where it's proven better.
- Aim must be **fair**: human-like reaction and error, no wallhacks (knowledge only from sight or sound), and as strong as possible within human-like limits (reaction, turn speed, drift). **Never miss on purpose** to hit an accuracy number (the old accuracy tuner that loosened aim was removed). Adapt to opponents through decisions or human-like limits, not injected misses.
- Human games on the public server are the real target data: **keep everything** (public logs are archived, never deleted).
- Everything is collected: all health (incl. 5hp bubbles), armor shards, ammo, weapons, mega, armors.
- BobbyBones persona: rainbow name `^1B^3o^2b^5b^4y^6B^1o^3n^2e^5s`, Bones model, obnoxious (not hateful) chat taunts when he frags a human.
- Public server must stay up. Never auto-promote training output unless it beats the previous version and the control group.
- Never change the owner's Quake Live client configs (binds etc.) in `C:\Program Files (x86)\Steam\steamapps\common\Quake Live`.
- No personal data in the repo (Steam IDs, home IP, Windows usernames). The repo is public.
- The owner prefers concise answers and doable batches.

## Architecture
- **Image `qlbot`** (`Dockerfile`): QL dedicated server (Steam app 349090) + minqlx built from `minqlx/` (vendored, patched; see `minqlx/UPSTREAM.md`) + plugins + tools + `maps/`.
- **C hook** `minqlx/botctl.c` hooks `SV_ClientThink`. Python API: `set_bot_input` (full control), `set_bot_move(id, yaw, up, speed)` (hybrid: AI aims, we steer; `speed < 0` = keep AI movement), `set_bot_aim(id, pitch, yaw, weapon, allow_fire)` (aim/weapon override when the AI fires; `allow_fire` 0 = suppress, 2 = hold fire + track for spray weapons), `ai_wants_fire` (AI's line-of-sight fire intent = our "can see" signal), `view_angles`, `last_usercmd`, `item_states`, `clear_bot_input`.
- **Plugins** (`plugins/`):
  - `lab.py` is the supervisor: map pool (`LAB_MAPS`; public = bloodrun, aerowalk, campgrounds; owner `!map <name>`; map votes only within the pool), per-human frag log on the public server (`human_results.jsonl`), bot presence, training-match results, all-weapon spawn loadout in spar mode, candidate tagging. Public = Blood Run duel in permanent warmup. Training = real 10-min matches.
  - `itemrun.py` is BobbyBones' brain on top of the AI. Trainable layers (`LAYER_KNOBS`, off by default, the coach switches them on): duel weapon defaults (W_*), rocket prefire after losing sight (PF_*), item timing takeover (T_*), score-aware play (S_LEAD/S_TRAIL), holding big items when ahead (P_*). Our routing only takes the wheel from Nightmare for those (or the routing arm); fights stay Nightmare's. Runs aim-only on maps without a nav graph. Also: item valuation for all items with fair timers, nav-graph routing, fight/stack/push decisions with an enemy-stack estimate, fair senses and aim, learned weapon table, routing arm (AI vs our routes per trip), experiments/exploration in training, experience/trip/leg logs.
  - `bobby.py` (name + taunts), `botctl.py` (recording per map with Steam ID, `!follow`, probes), `practice.py`/`jumplab.py` (older skill-practice experiments).
  - All admin commands are permission 5 (console/rcon only).
- **Variants** (`LAB_VARIANT`): `aimonly` = **current design (v2)**: Nightmare movement and decisions + our fair aim + routing arm. `full` = our movement + our aim (lost badly). `moveonly` = our movement + AI aim (lost badly).
- **Tools** (`tools/`): `rcon.py` (ZMQ rcon, inside containers), `bootstrap.sh`, `learner.sh` (10-min learning loop; public: weapons from humans + nav merge; train: pull shared knowledge, trainer 1 aggregates), `watchdog.sh` (kills a server whose CPU time stops advancing, or on `restart.flag`), `train_cluster.sh`, `train_aggregate.py`, `tune_coach.py`, `navgraph.py`, `learn_weapons.py`, `promote_training.sh`, `analyze_session.py`, renderers.

## Running things (Git Bash; always `export MSYS_NO_PATHCONV=1` before docker commands)
```bash
docker build -t qlbot .
# public server (UDP 27970): always via this script (map pool, CPU priority over trainers, promoted bot files,
# owner Steam ID from the git-ignored data/owner.env)
bash tools/public.sh
docker exec ql python3 /tools/rcon.py "mapname" --wait 2      # ("status" prints nothing over rcon)
# nightly training 22:00-08:00 from the editable template tools/nightly.conf; archives to data/runs/<date>/
bash tools/nightly.sh start|stop
# training cluster: N trainers, last CONTROLS are plain Nightmare; TUNE=1 mounts per-trainer bot files for the coach
TUNE=1 VARIANT=aimonly LAB_SPAR=1 TRAIN_DEADLINE=<unix> TRAIN_SINCE=<unix> bash tools/train_cluster.sh start <N> <CONTROLS>
bash tools/train_cluster.sh coach <N - CONTROLS>     # the tuning coach (needs Bobby trainers to be c1..cK)
bash tools/train_cluster.sh stop                      # removes qltrain* and qlcoach
```
- Data: `data/practice/` (public), `data/train/c<i>/` (per trainer: results.jsonl, trips.jsonl, legs.jsonl, experience.jsonl, lab.log, watchdog.log, botfiles/, candidate.json), `data/train/shared/` (aggregated report, policies), `data/train/tune/` (coach.log, log.jsonl, state.json, best.json). `data/` is git-ignored.
- `data/train/since.txt` / `deadline.txt` hold the current run's start and end.
- A one-time scheduled task `bobbybones-overnight-report` (Claude app, Scheduled) writes the end-of-run report to `docs/` and only promotes if the rule is met.

## What the coach tunes (cross-entropy method, candidate 0 = unmodified Nightmare Bones + every layer off)
Fitness = win rate (+0.001 x frag diff). With more trainers than candidates (POP), trainer i plays candidate (i-1) % POP and blocks of POP rotate maps, so each candidate is scored on every map. Restarts are staggered (BATCH every GAP s). COACH_GROUPS picks the knob groups searched: character, items, aim, weapons, prefire, timing, score, position.
Bot character skill-4+ block in `bones_c.c` (AGGRESSION, SELFPRESERVATION, CAMPER, ALERTNESS, JUMPER, WEAPONJUMPING, EASY_FRAGGER), item desire in `bones_i.c` (FS_HEALTH, FS_ARMOR multipliers), and fair aim knobs (AIM_REACT 120-300 ms, AIM_GAIN_X, AIM_DRIFT_X, AIM_SETTLE, AIM_DPS). Loose bot files in `/ql/home/baseq3/botfiles/bots/` override the pak (confirmed). The game caches bot files, so each candidate needs a server restart (via `restart.flag`). Public use of tuned knobs: `data/practice/botfiles/bots/*.c` mounted to `/ql/home/baseq3/botfiles`, plus `data/practice/aim_knobs.json`.

## Results so far (2026-10-02)
- Item-route-first design: 0/108 vs Nightmare. Split test: full 0.9 frags/match, moveonly 1.6, aimonly 5.7, control (plain Nightmare) 13.2.
- v2 (aimonly), 259 matches: 4.6 vs 17.5 frags; control 13.8 vs 10.8. Coach gens 1-3: best tuned candidate beat in-generation baseline every gen (+2.0 vs -11.2, -2.8 vs -9.0, -4.5 vs -10.2). Beware best-of-N selection noise.
- Routing arm: our routes faster on 4 of 16 compared trips (e.g. RL->MH 9.3s -> 5.8s).
- Fair aim is the biggest remaining gap; aim knobs were added to the coach at ~14:30 CDT, scaled to 32 trainers (ramping to 64, then 100).

## Capacity (measured 2026-10-02)
Each trainer ~2.5-5% of one core and ~71 MB; 208 trainers = ~550% CPU of 2000%, 15 GB of 31 GB. Starting or restarting ~200 servers at once lagged the public server 15-17 s per frame, hence staggering and `--cpu-shares 16384` on ql. Scheduled Claude tasks: `bobbybones-nightly-start` (22:00), `bobbybones-nightly-report` (08:00).

## Hard-won gotchas
- Old chat sessions can leave background scripts driving the cluster (one tore down a fresh cluster). Check for stray `train_cluster.sh` processes before scaling.
- Rocket prefire at sound-only positions spammed walls (aerowalk test: -2 frags, likely suicides); prefire now needs a real sighting, distance > 300 and health > 40.
- Aborting a QL warmup countdown (`abort`) in a loop **hangs the server**. Bots auto-ready; `sv_warmupReadyPercentage 2` does not stop the countdown. Training uses real matches + spawn loadout instead.
- Duel factory resets `timelimit`; `lab.py` enforces cvars. Map pool must contain the lab map or QL rotates away.
- The QL client binds UDP 27960, which is why the server uses 27970. `sv_serverType 1` (LAN) rejects clients through Docker NAT, so public uses 2. Trainers use `sv_master 0 sv_serverType 0`.
- Frequent rcon connects plus minqlx's console hook caused heap corruption once. Don't poll rcon often from many processes.
- minqlx `player_loaded` doesn't fire for bots. This minqlx has no damage event. Warmup emits no kill stats.
- Docker on Windows: line endings must be LF (`.gitattributes`), Git Bash mangles `\\` inside python heredocs (write patch scripts with the Write tool), use `MSYS_NO_PATHCONV=1`.
- Nav graph: drop knockback flights (fast air edges seen once), split recordings at frame-counter resets, detect teleporters as repeated source->destination jumps, don't merge trainers' fight traces into routes.
- The PC crashed once (Windows bugcheck 0xD1 driver fault) during a 24-trainer run. Docker Desktop only restarts after login. Scale carefully and check stability.

## Next steps
1. Finish the scale-up (64 -> 100 trainers) if stable. Read the end-of-run report. Promote only what beats baseline and control.
2. Opponent adaptation: per-Steam-ID profiles (item habits, routes, aggression, accuracy) that shift Bobby's aggression/item focus/prefire.
3. Player reports after matches (heatmap, item timing, weapon use), per Steam ID.
4. Go-live hardening: `docs/go-live-checklist.md`.

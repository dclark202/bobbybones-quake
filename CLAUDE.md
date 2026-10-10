# BobbyBones: project notes for Claude

A Quake Live duel bot that learns to play from scratch: a recurrent network trained by self-play in a fast
simulator of the game, checked on a real Quake Live server, play-tested by people. Repo:
`dclark202/bobbybones-quake` (public, GPL-3.0 because of the bundled minqlx and ioquake3 code). Local path: the
`ql-bot` folder in the owner's home directory.

## The owner's goals (read first)
- He wants genuine learned behavior (strafe jumping, weapon choice, item control, positioning), not hand-coded
  rules or knob tuning. Long-term focus: smooth, fast movement and good position and weapon choices, not just aim.
- **Fair**: human physics (125 fps), human senses (sight with line of sight, sound), mouse-like aim with
  human limits (reaction, flick speed, hand noise). Never miss on purpose to hit a number.
- Judge by results: the test suite scorecard, sparring against Nightmare, and human play tests. Say plainly what
  did not work.
- Log as much as possible from human-played rounds. Keep everything.
- **Goal 1 (2026-10-05)**: human-like play in one small arena, the yard (`arena1`, with items), showing
  knowledge of the map and efficient movement on it, one against one or all against all up to four players, and
  beating Nightmare there. See `docs/PLAN.md`. Method: tighten the human limits until the right play appears;
  do not add rewards for single behaviors without asking.
- Maps (owner, 2026-10-09): from v14 on the game's own duel maps only. Trained: Blood Run, Aerowalk, Lost World,
  Sinister, Furious Heights, Battleforged. Held out for checks: Campgrounds (the demo archive has 10 duels of it in
  today's format), Hektik, Toxicity, Cure. Maps with a door stay out (Silence); he does not know Dismemberment. The yard
  (`arena1`) is dropped entirely. Test map: `testlab`. Real games against the game's Nightmare bot: before and after a
  run, never a pause in the middle of one.
- Never change the owner's Quake Live client settings or configs in the Steam `Quake Live` folder. Copying the
  test map pk3 into its `baseq3` is allowed (he asked for it); nothing else.
- No powerups anywhere (owner, 2026-10-09: no quad, no "protection", on any server or in training) and a map's
  **duel** items in every mode, free-for-all too: `plugins/powerups.py` does both on the servers; the simulator has
  always had a map's duel items and no powerups.
- No personal data in the repo (Steam IDs, home IP, Windows usernames, passwords). The repo is public.
- The owner prefers concise answers and doable batches. Do not start a training run without his go-ahead when he
  has asked to test first.

## Docs (keep in sync, one commit)
- `docs/PLAN.md`: approach, status, the "Now" list (backlog IDs only), owner decisions.
- `docs/BACKLOG.md`: every work item with an ID (`B-nn`), priority and status.
- `docs/RESULTS.md`: dated log of every run, live test and measurement, including what did not work.
- `docs/LOGS.md`: schemas of recorded data. `docs/PLAYTEST.md`: the play-test routine and the test suite.
- `docs/REPORT_v<n>.md`, `docs/MANIFEST_v<n>.md`: the full report of a network and the full list of the next run (what is
  in its rounds, what it is paid for and shown, what changed), written for the owner's approval before a run starts.
- `README.md`: the public page (goal, fairness rules, how it works, what he can do, in progress, planned; no dated
  status table: owner, 2026-10-08). The owner wants it kept current
  with the docs (2026-10-08).
After any run, test or decision: add a RESULTS entry, update BACKLOG statuses, update PLAN if needed.

## Architecture
- **Simulator** (`sim/`): `sim_api.c` + vendored ioquake3 movement and collision (`sim/q3`) -> `qsim.dll`
  (`sim/build.bat`, MSVC) or `libqsim.so` (built in the Docker image). `qsim.py` wraps it. One `World` per
  process: worlds share buffers sized by player count, never create a second one with a different size.
- **Groups**: `duel_env_ffa.py` is written from `duel_env.py` by `tools/make_ffa_env.py` (2 to 6 players, all
  against all; 18 more inputs); `tools/ffa_check.py` proves it identical at two players. Change `duel_env.py`,
  then regenerate and re-check; do not edit the generated file. Trainer: `--env duel_env_ffa --group N`. The
  generator matches exact lines of `duel_env.py` (the `OBS_DIM` line, the `observe()` concatenation, `pkind = ...`,
  `return [i ^ 1]`): update its anchors when those lines change.
- **Intention and map cells (v8, 2026-10-06)**: the last action head is the intention (`INTENTS`: nothing, mega, red,
  RL, RG, LG), read every `INTENT_EVERY` frames by `env.intend()` (the plugin calls it too); the trainer masks that
  head's loss to the frames it was read on (`intent_live`). The last two inputs (`CELL_COLS`) are map-cell numbers
  looked up in a learned table (`cell` in the policy, `nn.Embedding`), not values: every policy loader (trainer,
  `test_suite.Policy`, the plugin's `act`, `export_duel.py`) handles them. Inputs that were always zero on `arena1`
  were retired (B-101); `sim/reshape_policy.py` carries a network over by input name (old and new `docs/INPUTS.csv`).
- **v9 (2026-10-06 evening)**: the learned cell table is gone; the last 32 inputs are the **map reader's** numbers for
  his cell and the enemy's (`sim/map_reader.py`, trained on the rasters of `tools/map_raster.py` for the 62 maps of
  `docs/MAPS.md`; tables in `data/maps/cells_<map>.npy`, loaded by the simulator next to the nav file; zeros without
  the file). `sim/duel_env_v8.py` / `duel_env_ffa_v8.py` are the frozen v8 simulator (the public server's network
  needs them: export with `--env duel_env_ffa_v8`). Older policies in the reflex report: `REFLEX_ENV=duel_env_v8`.
  `sim/render_replay.py` renders a video from a server session log.
- **v12 (2026-10-08)**: four more inputs at the end, his playing style this life (`STYLES` in `duel_env.py`; `env.style`, zero = general). `sim/duel_env_v11.py` / `duel_env_ffa_v11.py` are the frozen 483-input simulator of v10 and v11 (the public server's v10: export with `--env duel_env_ffa_v11`).
- **v13 (2026-10-08)**: the yellow armors are intentions (`INTENTS` has 8, `ROUTE_ITEMS` 7; 491 inputs); seeds from the pro demos behind switches (`PRO_WEAPON`, `PRO_ITEMS`, `SPAWN_TEACH`; tables in `sim/pro_seed.json`, written from `docs/pro_tables.json` of `tools/pro_tables.py`). `sim/duel_env_v12.py` / `duel_env_ffa_v12.py` are the frozen 487-input simulator of v12.
- **v13 as started (2026-10-08 night)**: 499 inputs (the last eight: the nearest dropped weapon in view). New switches in
  `duel_env.py`: `DROPS` (dead players leave their weapon, rules measured with `plugins/droplab.py`), `GROUND_SENSE` (a
  `PLAY_VAR`: floor and hazards round him in every direction), `KNOW_PAY`, `PACE_PAY`, `TEACH_KEYS_ONLY`, `KEY_RATE=8`.
  `docs/INPUTS_v12b.csv` is the 491-input list (v12a, v12b). Trainer: `--teach-trunk` (the teachers' losses into the
  shared layers), `--kl-heads N`, `--lr-warm`, `--fade-start` (pass it on every resume). `sim/renorm_policy.py --woke`
  starts inputs that a setting brings to life from zero weight. `sim/widen_obs.py` appends new inputs.
  `tools/eval_loop.py` (started detached beside a run) plays ten-minute duels against the Nightmare stand-in from the latest
  save over and over, at low priority, into `<run>/evals.jsonl`: the duel curve of a run. One trainer uses about 27% of the
  CPU (its simulators wait on the network half the time); more simulator processes do not make it faster.
- **Who stands higher (B-160, 2026-10-09)**: counters always on (trainer `v14.height`; `tools/duel_eval.py` `lower`, `higher`);
  `HIGH_PAY` (off by default) makes a hit from above worth more to both sides. Whatever is paid by the damage must not be
  added to `dealt`: his feedback inputs (`self.fb`) are made of it.
- **v14 (2026-10-09; built, not trained yet)**: 509 inputs (the last ten, `N_V14`: his speed, the angle from his view to
  the way he moves, speed gained in 100 ms; six for the lead of a rocket or a plasma ball). `sim/duel_env_v13.py` /
  `duel_env_ffa_v13.py` are the frozen 499-input simulator of v13 (the public server's v13: export with
  `--env duel_env_ffa_v13` from the next deploy with new code on). Switches, all off by default (with all off the simulator
  is v13's, checked by fixed-seed replays): the map fixes `SHOT_MASK`, `LAVA`, `WALK_FIX`, `PRO_WAYS`, `NEAREST`, `QL_MOVE`,
  `ITEM_DROP`, `SOLIDS`; `SHOT_W` (shot price by weapon), `TEACH_FREE` (weapon teacher silent on shotgun, grenades, plasma),
  `SPEED_PAY` / `SPEED_PAY_RUN` (per stretch of new ground by speed, 320 to 480), `RUN_TEACHER` (the movement network's
  labels in item runs; the trainer's `--teacher <run>`), `STACK_KEYS=0` (no key labels in games), `BLIND_RULE` (shots with
  no enemy in view). `sim/train_move.py --v14` trains the strafe-jumping teacher (lava, the game's step height, fall
  damage priced); `sim/export_policy.py` writes its flag. The plugins keep `env.sp_hist` themselves (`fill_player`).
  The reflex room on the test map does not measure a network whose input statistics were taken on the duel maps (B-176).
  The teacher is `move_v14d` (continued from the network of 2026-10-03 on seven maps; in v14 mode its walking map leaves
  out teleporter links that start far from the entrance, and a teleporter step is shown as its entrance); the trainer's
  `--teach-warm` lets a teacher's weight rise from nothing (a new teacher at full weight moved the policy 0.60 in one
  update). A new map: `python sim/build_nav.py --map <m> --v14` (system Python: it needs scipy), then
  `tools/nav_prune.py --map <m>` with the v14 switches set, then the stand-in check; pro demos with
  `tools/fetch_demos.py --maps <site id> --limit 150`, `sim/demo_dataset.py --lite`, `tools/pro_routes.py`,
  `pro_positions.py`, `pro_jumps.py`, `pro_tables.py` (all training maps at once) and `tools/pro_seed.py`. Under
  `WALK_FIX` the walker swims and dives, a teleporter link costs the walk to its entrance, and jump links over lava or
  slime are left out; automatic doors count as open (`qsim.add_solids`).
- **After the wiring review (2026-10-08)**: the trainer credits the left hand's outputs (movement keys, weapon key) only on the frames the simulator reads them (`env.key_dec`, one in four) and keeps the input statistics frozen; `sim/renorm_policy.py` gives a network fresh input statistics without changing its output (run it when the maps or inputs change; sample from `train_duel_rnn.py --obs-dump`). Checkpoints carry `env_vars` (the simulator switches of `PLAY_VARS`) and the round lengths; `sim/export_duel.py` writes them into `policy.npz` (`--set NAME=VALUE` for runs before v13, e.g. `EXPORT_ARGS="--set INTENT_HOLD=8"` for the server scripts) and the plugins set them before loading the simulator. Checks: `tools/input_check.py` (dead inputs; the real game's inputs beside the simulator's), `tools/teacher_check.py` (can the walking teacher's own pupil reach every item), `tools/nav_prune.py` (takes the jump and drop links the walker cannot take out of a map's graph), `tools/shot_prices.py`.
- **The map audit (2026-10-09)**: the game's maps set beside the simulator (RESULTS that day): `plugins/maplab.py` lists the
  real game's items per map and mode (`data/maplab/`; `tools/duel_items.py` -> `plugins/duel_items.json`), `plugins/poollab.py`
  measures lava and water, `plugins/itemwatch.py` writes a running game's items down. The fixes are switches in `duel_env.py`,
  all off by default (`SHOT_MASK`, `LAVA`, `WALK_FIX`, `PRO_WAYS`, `QL_MOVE`, `ITEM_DROP`, `SOLIDS`; the `notfree` key in
  `qsim.py`); the library (`sim_api.c`) has traces with a mask, many point contents, solid pieces. Until they are in `sim/`
  (BACKLOG B-171) they live in the scratchpad's staging copy with the patch scripts that make them.
- **Environments**: `duel_env.py` (current: nine weapons, items, sounds, clock, crouch, walk, fall damage,
  human-aim limits, round kinds NORMAL / AIM / DRILL / MOVE / SOLO / COURSE, scripted opponents with eight styles, lab
  mode on the test map: aim rooms and movement courses read from `maps/testlab/rooms.json`). `duel_env_v3.py` and `duel_env_v2.py` are frozen copies for older runs (freeze a copy before changing the
  inputs or actions of a simulator that a run still needs); a policy must be played and
  evaluated with the module it was trained in. `movement_env.py` is the movement-only task.
- **Training**: `train_duel_rnn.py` (PPO, GRU 512, league of snapshots, `--resume`). `upgrade_policy.py` widens an
  older network to new inputs and actions (new inputs are appended at the end, zero weights). GPU PyTorch lives
  in the Anaconda Python (`C:\Users\<user>\anaconda3\python.exe`); do not import torch inside simulator workers
  (it crashed numpy). Long runs are launched detached (`Start-Process cmd.exe`) from a `.cmd` file written with
  the Write tool.
- **Test suite**: `test_suite.py` scores a checkpoint in fixed rooms; cards go to `data/sim_runs/<run>/suite/`.
- **Real game**: image `qlbot` (`Dockerfile`): Quake Live dedicated server + minqlx (`minqlx/`, patched, see
  `minqlx/UPSTREAM.md`) + `plugins/` + `sim/`. `minqlx/botctl.c` hooks `SV_ClientThink`: `set_bot_input`,
  `set_bot_substeps` (human physics), `ran_usercmd`, `view_angles`, `set_view`, `item_states`, `missiles`.
- **Plugins**: `duelbot.py` plays a trained network (inputs rebuilt with the simulator's own `observe()`), runs
  the test rooms with a human as the subject, hot-reloads `policy.npz`, logs sessions. `weaponlab.py`,
  `itemlab.py`, `movetest.py` are measurement tools. `botctl.py` records inputs. `botmode.py` switches mode and map
  (`!map` offers the ten duel maps of v14 and `testlab`; they come up in free-for-all with a map's duel items: a new map
  needs its list in `plugins/duel_items.json`, from `plugins/maplab.py` and `tools/duel_items.py`). `banlist.py`: the
  owner's `!kick` and `!ban` (bans by Steam ID in the server's data folder, never in the repo). `ladder.py`: the
  leaderboard, local to a server (every frag between a person and Bobby, warmup included; Glicko-1 per frag in
  `ratings.py`; who made a frag is read from the kills and deaths counters each frame; `tools/elo.py` reads its files).
  A chat line must not have a percent sign before a letter: the game takes it for a printf format.
- **Test map**: `tools/make_lab_map.py` -> `maps/testlab/` (pk3 + `rooms.json`), compiled with q3map2 and
  mbspc from `data/tools` (NetRadiant-custom; mbspc needs `-forcesidesvisible`). Bots cannot join a map
  without an `.aas` file.
- **Map atlas**: `tools/build_atlas.py` -> `maps/atlas/<map>.json` + `.png` (areas, items, several routes per item
  seeded from pro demos; `docs/ATLAS.md`). Matplotlib is broken in the Anaconda Python: draw with `--picture` in the system Python.
- **Pro demos**: `tools/fetch_demos.py` downloads, `sim/demo_dataset.py` converts (inputs + inferred keys), the trainer
  imitates with `--demo-dir/--demo-coef/--demo-heads`. Demos and sets live in the folder named in `data/demo_root.txt`.
  Imitating mouse or trigger at full weight destroys aim (RESULTS 2026-10-04 21:12): movement heads only.
- **Videos**: `sim/render_course.py` renders first-person videos from the simulator (flat-shaded, with keys, mouse,
  speed): every movement course, or `--fight aim|env` for a self-play fight in a box. Output in `videos/<run>_<minutes>/`
  (git-ignored). The owner finds these useful: render them after a run without being asked and send the files.
- `legacy/`: the first approach (Nightmare bot + routes + coach + cluster). Not used.

## Running things (Git Bash; `export MSYS_NO_PATHCONV=1` before docker commands)
```bash
python sim/train_duel_rnn.py --run <run> --resume --minutes <n>      # Anaconda Python; see RESULTS for settings
python sim/test_suite.py --run <run> [--env duel_env_v3] [--compare card.json]
docker build -t qlbot .
bash tools/duel_server.sh <run> <map> <env module>                   # play-test server, UDP 27970 (no password unless PASSWORD=<word>)
NAME=qltest DATA=data/labtest SPAR=1 bash tools/duel_server.sh ...   # second private server, Bobby vs the game's bot (Nightmare; SKILL=4 Hardcore). Benchmark only: never train against the game's bots
docker exec <name> python3 /tools/rcon.py "qlx !room suite" --wait 2  # rcon ("status" prints nothing)
```
`data/` is git-ignored (maps from the game, runs, sessions, tools, `owner.env`).

## Hard-won gotchas
- Git Bash heredocs mangle backslashes: write patch scripts and `.cmd` files with the Write tool.
- The PC has blue-screened twice under load; long runs should save often (they do, every 10 updates) and be resumed.
- Write `.cmd` run files to the scratchpad and copy them over: writing over an existing one can fail silently in a chain,
  and the old settings then run (it happened).
- Long sequences fill GPU memory (256 steps needs `--minibatches 24` on 16 GB; with 416 inputs and about 8,600 players `--minibatches 36`); a stalled first or second update is the sign. After every widening, check that updates keep coming (`metrics.jsonl` grows about once a minute).
- Restart a run only right after a checkpoint save (every 10 updates) and keep a copy of it. The teachers' fades count
  from the process start unless `--fade-start <minute>` is given: without it a resume puts them back at full weight.
- A teacher with new labels moves the whole network in its first updates and costs aim that does not come back
  (RESULTS 2026-10-08 18:45; `--teach-trunk` holds the teachers' losses back from the shared layers): dry-run a new
  setup for ten minutes on a scratch copy with `--kl-heads 1` and read the step per output before the real start.
- A background shell is capped at two hours; chain waiters or launch detached.
- Aborting a warmup countdown in a loop hangs the server; the plugin aborts at most every 30 s and only with a human.
- Quake Live locks `sv_fps` at 40; a higher tick rate is not possible.
- The QL client uses UDP 27960, so servers use 27970. An idle server runs no frames until someone joins.
- minqlx has no damage event; hits are inferred from health drops. Warmup emits no kill stats.
- Docker on Windows: LF line endings (`.gitattributes`).
- An rcon client that leaves while the server prints (a map load) can freeze the game server for good (2026-10-09: the
  console goes to every rcon client with a blocking send). `tools/rcon.py` leaves only in a quiet moment; give a map
  change `--wait 30`; on the public server use rcon only when it is needed. The watchdog now watches the main thread.
- Plugin changes can be tried without an image build: mount `plugins/` over `/ql/minqlx-plugins` and `tools/` over
  `/tools` (read-only) in a private container. Events are written only with people in the game (`FFA_LOG_ALWAYS=1`
  writes the frames without them).
- PPO's entropy bonus drowns small shaping costs: size any cost against it (see RESULTS 2026-10-04).
- Do not restart the play-test server while the owner is on it; use a second container for tests.
- Before any real-server check or run: `docker ps`, `docker stats --no-stream`. A game server with Bobbys on a map works
  whether or not a person is on it, and until 2026-10-08 its numeric library spun a helper thread per core: a forgotten
  local server held 7 to 8 of the PC's 20 threads for a day (RESULTS 2026-10-08 19:30). `tools/duel_server.sh` and the
  image now set `OPENBLAS_NUM_THREADS=1`; stop servers nobody uses (`docker stop`, not `rm`: `docker start` restores).
- Real-server checks (Nightmare sparring) only while no training runs: a server that falls behind distorts everything (until 2026-10-08 it even dropped the bot's commands: RESULTS 2026-10-08 13:00). `DUEL_AIMDUMP=1` (`AIMDUMP=1` for `tools/bench_arena.sh`) records what became of his mouse output per frame. The local image `qlbot` must be rebuilt (`docker build -t qlbot .`) after any change to `sim/`, `plugins/` or `minqlx/`: the sparring scripts do not do it.
- The plugins feed the network through the simulator's own `observe()` but never call `step()`: whatever only `step()` keeps up to date is stale on a real server unless the plugin sets it (2026-10-08: the 1v1 plugin had no walking graph, no plugin set `item_t`, the 1v1 plugin sets no style). After any change to the inputs, record them in a real game (`OBSDUMP=1` with `tools/bench_arena.sh`) and set them beside the simulator's. With the PC busy it is now the game's Nightmare bot that plays badly (he won 6-0 under load).
- In a free-for-all plugin everything per-seat that the simulator does in one call for all players must be one call there too: `limit_keys` was called once per Bobby and each call overwrote the other seats' hands (2026-10-08: every Bobby on the public server moved on another Bobby's keys).
- A scratch test script must import the repo's `sim/`, not a staging copy: on 2026-10-09 half an hour of stand-in checks
  ran old code and "confirmed" that two fixes did nothing. A write to a file in `sim/` failed once with "Invalid argument"
  (Errno 22) and left the file as it was: check after a patch that the change is there.
- A reviewer's eye on the reward: anything paid per frame for progress must be paid on a running best, or a setback and its recovery is a pump (the trip pay, 2026-10-08).
- Joining a pure server: its pak list must be exactly what a client gets (pak00, bin, the Workshop item); any extra mounted
  pk3 drops every player who lacks it, silently ("connected" then "disconnected"). `sv_pure` is write-protected,
  `sv_warmupReadyPercentage` and `sv_maxclients` are latched (a map change applies them); `allready` cannot start a game
  when the percentage is above 1; the game's bots never ready up. The server's stdout is block-buffered through `tee`:
  `docker logs` lags, rcon answers do not.

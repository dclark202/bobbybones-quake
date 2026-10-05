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
- Maps: Blood Run (ZTN), Aerowalk, Lost World (replaced Campgrounds on 2026-10-04), plus the test map `bobbylab`.
- Never change the owner's Quake Live client settings or configs in the Steam `Quake Live` folder. Copying the
  test map pk3 into its `baseq3` is allowed (he asked for it); nothing else.
- No personal data in the repo (Steam IDs, home IP, Windows usernames, passwords). The repo is public.
- The owner prefers concise answers and doable batches. Do not start a training run without his go-ahead when he
  has asked to test first.

## Docs (keep in sync, one commit)
- `docs/PLAN.md`: approach, status, the "Now" list (backlog IDs only), owner decisions.
- `docs/BACKLOG.md`: every work item with an ID (`B-nn`), priority and status.
- `docs/RESULTS.md`: dated log of every run, live test and measurement, including what did not work.
- `docs/LOGS.md`: schemas of recorded data. `docs/PLAYTEST.md`: the play-test routine and the test suite.
After any run, test or decision: add a RESULTS entry, update BACKLOG statuses, update PLAN if needed.

## Architecture
- **Simulator** (`sim/`): `sim_api.c` + vendored ioquake3 movement and collision (`sim/q3`) -> `qsim.dll`
  (`sim/build.bat`, MSVC) or `libqsim.so` (built in the Docker image). `qsim.py` wraps it. One `World` per
  process: worlds share buffers sized by player count, never create a second one with a different size.
- **Environments**: `duel_env.py` (current: nine weapons, items, sounds, clock, crouch, walk, fall damage,
  human-aim limits, round kinds NORMAL / AIM / DRILL / MOVE / SOLO / COURSE, scripted opponents with eight styles, lab
  mode on the test map: aim rooms and movement courses read from `maps/bobbylab/rooms.json`). `duel_env_v3.py` and `duel_env_v2.py` are frozen copies for older runs (freeze a copy before changing the
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
  `itemlab.py`, `movetest.py` are measurement tools. `botctl.py` records inputs.
- **Test map**: `tools/make_lab_map.py` -> `maps/bobbylab/` (pk3 + `rooms.json`), compiled with q3map2 and
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
- Long sequences fill GPU memory (256 steps needs `--minibatches 24` on 16 GB); a stalled first update is the sign.
- Restart a run only right after a checkpoint save (every 10 updates) and keep a copy of it.
- A background shell is capped at two hours; chain waiters or launch detached.
- Aborting a warmup countdown in a loop hangs the server; the plugin aborts at most every 30 s and only with a human.
- Quake Live locks `sv_fps` at 40; a higher tick rate is not possible.
- The QL client uses UDP 27960, so servers use 27970. An idle server runs no frames until someone joins.
- minqlx has no damage event; hits are inferred from health drops. Warmup emits no kill stats.
- Docker on Windows: LF line endings (`.gitattributes`).
- PPO's entropy bonus drowns small shaping costs: size any cost against it (see RESULTS 2026-10-04).
- Do not restart the play-test server while the owner is on it; use a second container for tests.

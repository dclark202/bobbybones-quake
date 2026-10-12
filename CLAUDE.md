# BobbyBones: project notes for Claude

A Quake Live duel bot that learns to play from scratch: a recurrent network trained by self-play in a fast
simulator of the game, checked on a real Quake Live server, play-tested by people. Repo:
`dclark202/bobbybones-quake` (public, GPL-3.0 because of the bundled minqlx and ioquake3 code). Local path: the
`ql-bot` folder in the owner's home directory.

## The owner's goals (read first)
- He wants genuine learned behavior (strafe jumping, weapon choice, item control, positioning), not hand-coded
  rules or knob tuning. Long-term focus: smooth, fast movement and good position and weapon choices, not just aim.
- **Fair**: human physics (125 fps), human senses (sight with line of sight, sound), mouse-like aim with
  human limits (reaction, flick speed, hand noise). Never miss on purpose to hit a number. Enemy projectiles too (owner,
  2026-10-10): "he should only know what's in view or what he can hear"; suspecting a rocket is for him to learn.
- Jumps (owner, 2026-10-10): "the jumps don't need to be 'exact' for repeating, he should be taught the general path,
  there's many ways to execute them": pay and labels are for the way, the pros' take-off and landing places only count.
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
  (`arena1`) is dropped entirely. Test map: `testlab`. From v0.2 (owner, 2026-10-11) the ten maps are all in training and two
  maps he never trains on and the owner does not know are the held-out check, "purely to make sure he's not
  'overfitting'": House of Decay and Dismemberment (prepared with places and cells from their own demos; Delirium was
  looked at and dropped: a ladder, lifts and a blown-up map box). Real games against the game's Nightmare bot: before and after a
  run, never a pause in the middle of one.
  From v15 (owner, 2026-10-10: "He should get movement only practice on all 10 maps"; "it's important that he understands how
  to move around these maps efficiently") the four held-out maps have movement-only practice (item runs and jump runs, no games:
  the trainer's `--move-maps`); they stay in the checks against the stand-in.
- Never change the owner's Quake Live client settings or configs in the Steam `Quake Live` folder. Copying the
  test map pk3 into its `baseq3` is allowed (he asked for it); nothing else.
- No powerups anywhere (owner, 2026-10-09: no quad, no "protection", on any server or in training) and a map's
  **duel** items in every mode, free-for-all too: `plugins/powerups.py` does both on the servers; the simulator has
  always had a map's duel items and no powerups.
- **His priority list for the next models (2026-10-10)**: strafe jumping and keeping speed; rockets; plasma and
  grenades, the shotgun less; then game awareness (not through a teleporter the enemy watches, not always the same
  path: it needs more model build-out and comes when the first two or three are there). Every plan addresses these
  and any odd behaviour seen in a run or in duels.
- **The control in every run (2026-10-10)**: the last best network stays in the league (`--anchor-p`) and every
  checked save plays it head to head, beside the stand-in; a network is promoted only if it beats the control.
- **Names (owner, 2026-10-11)**: "The v15c bot that exists on the server is now: v0.1. We're building v0.2 currently, any
  exploration phases will get a further index e.g., v0.2.1, etc."; "v1.0 starts when he can beat me." v0.2 = ten maps, the
  rocket changes, the enemy as a target and stage A of the attention model (`docs/runs/MANIFEST_v0.2.md`); the part ready
  on 2026-10-11 is v0.2.1 (written up as `duel_gru_v15e`). Use these names in every report and give the old run name
  once where a folder carries it.
- No personal data in the repo (Steam IDs, home IP, Windows usernames, passwords). The repo is public.
- The owner prefers concise answers and doable batches. Do not start a training run without his go-ahead when he
  has asked to test first.

## Docs (keep in sync, one commit; the routine is `docs/README.md`)
- `docs/PLAN.md`: the goal, the approach, today's status table, the "Now" list (the owner's priority list and backlog
  numbers only), owner decisions. History does not go into it: the plan as it stood is in `docs/archive/`.
- `docs/BACKLOG.md`: the open work by number (`B-nn`), grouped by the owner's priority list; a closed item moves with
  its row to `docs/archive/BACKLOG_closed.md`. A new item takes the highest number in both files plus one.
- `docs/RESULTS.md` is the index of the results log; the log is one file a day in `docs/results/<date>.md`, newest
  first, what did not work included. Add an entry with `python tools/add_result.py entry.md` (first line
  `## <date> <time> — <the finding>`; links written as from `docs/results/`). "RESULTS 2026-10-08 18:45" anywhere
  means the entry of that time in `docs/results/2026-10-08.md`.
- `docs/runs/`: a run's own documents, `MANIFEST_v<n>.md` (the run in full, for the owner's go before a start; changes
  during the run go into its section 0), `MIDRUN_v<n>.md`, `REPORT_v<n>.md` (the full report, ending with what to try next).
- `docs/guides/` (PLAYTEST, COMMANDS, HOSTING, COMMUNITY, LOGS: the schemas of recorded data, ATLAS), `docs/design/`
  (proposals not tied to a run: SCOPE_v15, ATTENTION_POC), `docs/archive/`.
- `docs/INPUTS*.csv`, `docs/*.json`, `docs/MAPS.md`: data that tools and the Dockerfile read by path; they stay there
  until every path moves with them (B-203).
- `README.md`: the public page (goal, fairness rules, how it works, what he can do, in progress, planned; no dated
  status table: owner, 2026-10-08). The owner wants it kept current
  with the docs (2026-10-08).
After any run, test or decision: an entry in the log, the backlog, the plan if its status or "Now" changed, then
`python tools/docs_check.py` (links, the log's index, backlog numbers) before the commit.

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
- **v14 (2026-10-09; ended 2026-10-10 on its save of 10:57, `policy_end_v14.pt`: `docs/runs/REPORT_v14.md`)**: 509 inputs (the last ten, `N_V14`: his speed, the angle from his view to
  the way he moves, speed gained in 100 ms; six for the lead of a rocket or a plasma ball). `sim/duel_env_v13.py` /
  `duel_env_ffa_v13.py` are the frozen 499-input simulator of v13 (the public server's v13: export with
  `--env duel_env_ffa_v13` from the next deploy with new code on). Switches, all off by default (with all off the simulator
  is v13's, checked by fixed-seed replays): the map fixes `SHOT_MASK`, `LAVA`, `WALK_FIX`, `PRO_WAYS`, `NEAREST`, `QL_MOVE`,
  `ITEM_DROP`, `SOLIDS`; `RULE_WALK` (2026-10-10: the item rule and item runs count a walker's ways only); `SHOT_W` (shot price by weapon), `TEACH_FREE` (weapon teacher silent on shotgun, grenades, plasma),
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
- **v15 (2026-10-10; built, started on the owner's go)**: 574 inputs (the last 65, `N_V15`: five for a jump ahead on his
  way, six for a grenade's arc with the launcher in hand, 36 for four more enemy projectiles, 18 for the six projectiles'
  fuse, closest pass and closeness in splash radii). `sim/duel_env_v14.py` / `duel_env_ffa_v14.py` are the frozen 509-input
  simulator of v14 (resume or check a v14 network with `--env duel_env_ffa_v14`, `tools/duel_eval.py --inputs
  docs/INPUTS_v14.csv`). Switches, all off by default (with all off the simulator is v14's in fixed runs): `JUMPS` +
  `JUMP_RUN_P` (jump runs on the pros' jumps: `sim/jump_links.py`, the lists `sim/pro_gaps/<map>.json` from
  `tools/pro_gaps.py`, pictures by `tools/draw_gaps.py` in the system Python; a `"use": true/false` on an entry is the
  owner's), `JUMP_ALL` (tries at the jumps on no item's way: his ways made to take the jump, or to its landing first; the teacher is
  silent at the jumps named in `sim/jump_labels.json`, written by `tools/jump_labels.py`: where its own way goes round),
  `JUMP_OPEN` (a `PLAY_VAR`: jumps his ways take in games), `PROJ_SEE` (a `PLAY_VAR`: enemy projectiles as a player sees
  them), `GL_QL` (a grenade's bounce and splash as measured in the game), `TRICKS` / `TRICK_P` (the holder, the lobber,
  the watcher among the scripted opponents), `START_GUN_P`, `TEACH_BEST`. Trainer: `--teacher-skip` (maps without the
  movement teacher's labels), `--move-maps` / `--move-matches` (a simulator a map of item runs and jump runs only: no
  games, no league seats; its counters by map only, `v15.runs_by_map`). The movement teacher is trained under his finger
  limits (`sim/train_move.py --v14 --jumps --hand`; `MOVE_LAVA_COST` prices a try that ends in lava) and gives labels on
  a map only after its pupil test there (`tools/label_check.py`: a player who presses exactly its labels with his
  hands; lava damage, items a minute, jumps over). `tools/jump_check.py`: him alone in jump runs.
- **v15b, the legs (2026-10-10 night; `duel_gru_v15b`, `docs/runs/MANIFEST_v15b.md`)**: the movement network is a part of him, not a teacher. `LEGS=1` (a `PLAY_VAR`, with `LEGS_EVERY`): a twelfth output (`LEGS_HEAD`; the intention stays the eleventh, `INTENT_HEAD`) read every `LEGS_EVERY` frames; while it is on and he has a target, `_legs_step` (before the finger limits) puts the movement network's choices in place of his keys, view turn, walk and zoom (`LEGS_TAKES`); 576 inputs (the last two of `N_V15`: the switch, his legs carried him). The network comes by the trainer's `--teacher <run>` (with `--teach 0`, `RUN_TEACHER=0`) or, in checks, by `LEGS_NET=<policy.npz>`. The trainer's `head_masks`: an output counts on the frames its choice was read and what the legs take only on the frames he moved himself. `tools/legs_init.py` (`collect`, `fit` with `LEGS_SHARP`, `off`): the switch's start is a fit to a plain rule (a switch that starts at "never" is not found by trying), the control and the league get a switch that is never on. `AUTO_SWITCH=1` (a `PLAY_VAR`): the game's weapon change on an empty weapon. `docs/INPUTS_v15.csv` is the 574-input list (v15's first start, `policy_start_v15.pt`, the trial arms). The plugins and `sim/export_duel.py` do not know the legs yet (B-213): no real game with such a network.
- **v0.2 (2026-10-11 night; `duel_gru_v0_2`, `docs/runs/MANIFEST_v0.2.md`)**: attention, stage A. 720 inputs in the group module (696 in `duel_env`): the last 143 (`N_V02`: the game 3, his position 10, the enemy as he believes him 21, when he last took each item 13, the eight nearest of the pros' places 96; groups `v02 ...` in `docs/INPUTS.csv`) are always there and say nothing of an unseen enemy that he could not know; they read `sim/pro_places/<map>.json` and `<map>_cells.json` (twelve maps) and a table of ways cached in `data/maps`. `sim/duel_env_v15f.py` / `duel_env_ffa_v15f.py` are the frozen 577-input simulator (v0.1 and every older 577-input network: `--env duel_env_ffa_v15f`, `--inputs docs/INPUTS_v15f.csv`; `test_suite.Policy` also lets a network with fewer inputs take the first columns). `sim/attn.py`: the inputs cut into tokens by those groups, two attention blocks (the second for two rows), a last layer ("the door") that starts at zero; the layout is kept in the checkpoint (`attn`), the trainer builds the part from it, `forward_np` is the same in numpy. `sim/add_attention.py <in> <out>` gives a network the part with the door shut (`--same a b` proves two networks answer alike): league files and the control need the same shape. Trainer: `--long-gamma 0.9998 --long-ramp 60 --long-cap 0.5` (two more value outputs for `info["r_long"]`, the part of the pay that is for items and stack, at the fight's count and two minutes ahead), `--obs-half`; in an update the encoder, the attention part and the outputs are worked out for whole sequences and only the GRU steps frame by frame; `door` and `long` and `hop` are written with every update. `HOP_PAY` (off by default): speed gained from hop to hop above a chain's best take-off. On a server (2026-10-11 night, proven on a private one): `sim/export_duel.py` writes the layout and the part's weights, `plugins/netpass.py` is the forward pass of both plugins, and the plugins keep what `step()` keeps for the new inputs (`note_noise` beside `hear()`, `note_take`, `v02_left` from his own round clock, the resets at a respawn and at a game's start, `seen2` / `acq2` / `known2` at two players); `tools/prep_ways.py` makes the tables of ways before a server takes players (`tools/duel_server.sh` runs it; `PREP=0` skips). Export a copy of a running save with `EXPORT_ARGS="--policy <full Windows path> --legs move_v15n"`. Stages B and C: `docs/design/V02_STAGE_B.md`, `V02_STAGE_C.md`, built as patch scripts in the scratchpad while v0.2 trained.
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
- **Training**: `train_duel_rnn.py` (PPO, GRU 512, league of snapshots, `--resume`; `--anchor-p X` with
  `snapshots/anchor_*.pt`: networks that never leave the league, the owner's standing rule of 2026-10-10: the last best
  network in every run's league and in every check). `upgrade_policy.py` widens an
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
  A chat line must not have a percent sign before a letter: the game takes it for a printf format. `banter.py`: what
  the bots say (a line at a game's end, a few during a game); the four bots' names are `duelbot.BOT_NAMES`, and a Bobby
  is known by `duelbot.is_bobby`, not by "Bones" in a name.
- **Test map**: `tools/make_lab_map.py` -> `maps/testlab/` (pk3 + `rooms.json`), compiled with q3map2 and
  mbspc from `data/tools` (NetRadiant-custom; mbspc needs `-forcesidesvisible`). Bots cannot join a map
  without an `.aas` file.
- **Map atlas**: `tools/build_atlas.py` -> `maps/atlas/<map>.json` + `.png` (areas, items, several routes per item
  seeded from pro demos; `docs/guides/ATLAS.md`). Matplotlib is broken in the Anaconda Python: draw with `--picture` in the system Python.
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
- The plugins feed the network through the simulator's own `observe()` but never call `step()`: whatever only `step()` keeps up to date is stale on a real server unless the plugin sets it (2026-10-08: the 1v1 plugin had no walking graph, no plugin set `item_t`, the 1v1 plugin sets no style). After any change to the inputs, record them in a real game (`OBSDUMP=1` with `tools/bench_arena.sh`; in the free-for-all plugin `FFA_OBSDUMP=1`, two Bobbys alone on a private server: with no person it stays in warmup, where everyone holds every weapon with full ammunition) and set them beside the simulator's. With the PC busy it is now the game's Nightmare bot that plays badly (he won 6-0 under load).
- In a free-for-all plugin everything per-seat that the simulator does in one call for all players must be one call there too: `limit_keys` was called once per Bobby and each call overwrote the other seats' hands (2026-10-08: every Bobby on the public server moved on another Bobby's keys).
- A scratch test script must import the repo's `sim/`, not a staging copy: on 2026-10-09 half an hour of stand-in checks
  ran old code and "confirmed" that two fixes did nothing. A write to a file in `sim/` failed once with "Invalid argument"
  (Errno 22) and left the file as it was: check after a patch that the change is there.
- The control belongs in a run's checks from its first hour: the league is the last eight snapshots at one every 20
  minutes (two hours and forty minutes of himself), so "53% against his old selves" says nothing about the network he
  started from. v14 beat its snapshots all night, held 55 to 58% against the stand-in, and lost to v13 head to head 137
  games to 41 (2026-10-10). `tools/duel_eval.py --opp policy:<file>` plays two networks against each other.
- The weapon teacher's label in a styled life (`STYLE_P`, three lives in four, drawn on the servers too) is the style's
  weapon at every distance; only a general life gets the pros' table. A teacher kept to a run's end makes him hold it so.
- A teacher must not name what he cannot reach: with the pros' ways in the walking graph (`PRO_WAYS`) the item rule
  (weight 2.0 to a run's end) named Aerowalk's red armor, which only a circle jump reaches; he went a quarter of the
  time, did not arrive, and lost the map to v13 12% to 88% within 17 minutes of every start of v14. `RULE_WALK=1`: the
  rule and the item runs count a walker's ways only (`tools`: scratch probes of 2026-10-10; B-204 teaches the jump).
  A map's numbers must be read per map: the six-map mean against the stand-in did not move while Aerowalk fell 24 points.
- A teacher must have the pupil's hands (2026-10-10): the movement network of v14 was trained with any key on any frame
  (17 key changes a second against his 8) and cost him a map within an hour. Test a teacher's labels alone before a run
  (`tools/label_check.py`), map by map. In a jump run the teacher is asked for the jump's landing until he is over it:
  asked for the item behind it, its own ways went round some jumps.
- A fitted start for a new choice must pass a full level check before a run, not a probe: the enemy as a target by the narrow rule read level in 48 games and 45.9% in 128 (2026-10-11): it was left out of v0.2.
- The attention part's graph for whole sequences fills the card: with 10,080 players the update is cut into 240 pieces (`--minibatches 240`), the part runs at half precision on the card (`ATTN_AMP`), and a first update that does not come within about six minutes means the card is full.
- `ctypes.windll.kernel32.SetPriorityClass(GetCurrentProcess(), ...)` with default types fails silently on 64-bit Python (the handle is cut): set `restype`/`argtypes` (done in the tools on 2026-10-11); `subprocess` `creationflags=0x4000` works.
- `CUDA_VISIBLE_DEVICES=""` does not hide the graphics card on Windows (an empty variable is dropped and torch still finds the card): beside a run use `CUDA_VISIBLE_DEVICES=-1` and see that a trainer reports `device cpu` (2026-10-11: a helper's dry run reached the full card for a moment). A trainer on the CPU takes six threads unless `OMP_NUM_THREADS=1`.
- The checks' noise: the same network against itself in a check of 160 ten-minute games (ten maps of 16, seats swapped) read 48.8%, single maps 41 to 56% (2026-10-11): a single map's number moves ten points by chance.
- Two tools that import the same module while it is being edited mix versions (a pool re-imports the file): tell helpers which files stand still, and use the frozen simulator copies for anything long.
- The PC's load as Windows reports it (`Win32_Processor.LoadPercentage`, the number the owner's 80 to 85% is about) reads
  far above the share of processor time: two half-size trainers were 35% of the time and 86 to 90% of the load. Size
  side jobs by the load.
- `tools/list_inputs.py` writes `docs/INPUTS.csv` whatever its arguments.
- A fixed-run identity check after a new output: random actions for the old outputs only (the scratch `ident16.py`, `IDENT_HEADS=11`), or the random stream shifts and nothing matches.
- Two half-size trainers, a set of duels and a dry run together were 97% of the load (2026-10-10 21:50): stop a side arm before a dry run.
- A run's wake-ups must watch for a stall (no new line in `metrics.jsonl` for ten minutes): `duel_gru_v15b` died at 02:25 with the graphics card full after 89 updates at `--minibatches 70` (576 inputs, 10,892 players; 80 held) and stood 37 minutes before it was seen. A check loop that outlives a crash checks the old save again under a new label.
- The trainer's `legs.share` counts every seat, the league's older selves too: read the updates whose opponents have legs, or the duel checks' own number.
- After merging a branch, push plainly: `git pull --rebase` on a merge commit replays the branch and conflicts (2026-10-10;
  `git rebase --abort` put everything back, the owner's uncommitted files too). Fetch and look first.
- A reviewer's eye on the reward: anything paid per frame for progress must be paid on a running best, or a setback and its recovery is a pump (the trip pay, 2026-10-08).
- Joining a pure server: its pak list must be exactly what a client gets (pak00, bin, the Workshop item); any extra mounted
  pk3 drops every player who lacks it, silently ("connected" then "disconnected"). `sv_pure` is write-protected,
  `sv_warmupReadyPercentage` and `sv_maxclients` are latched (a map change applies them); `allready` cannot start a game
  when the percentage is above 1; the game's bots never ready up. The server's stdout is block-buffered through `tee`:
  `docker logs` lags, rcon answers do not.

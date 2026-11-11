# BobbyBones: project notes for Claude

A Quake Live duel bot that learns to play from scratch: a recurrent network trained by self-play in a fast
simulator of the game, checked on a real Quake Live server, play-tested by people. Repo:
`dclark202/bobbybones-quake` (public, GPL-3.0 because of the bundled minqlx and ioquake3 code). Local path:
`Documents\gh\BobbyBones` in the owner's home directory (moved there 2026-10-28; older notes say `ql-bot`).

The version of this file before the trim of 2026-11-11 (with the switch-by-switch record of every input generation, v8 to
v0.4.x) is kept whole in [docs/archive/CLAUDE_2026-11-11.md](docs/archive/CLAUDE_2026-11-11.md).

## HARD RULES (read before doing anything)

1. **Never delete anything outside git's tracked files.** No `rm -rf`, `Remove-Item -Recurse`, `rmdir /s`, or
   `git worktree remove --force` on any folder. On 2026-10-28 a cleanup did that near links into `data/` and wiped the whole
   data folder (every run's checkpoints). A link (junction) is removed only with `cmd /c rmdir "<link>"` (no `/s`) after checking
   with `(Get-Item <path>).LinkType`, and the target is checked after. Any delete of data needs the owner's word for that exact
   delete and a backup first (`python tools/run/backup.py`). `tools/hooks/no_delete.py` (a hook in `.claude/settings.json`) asks
   him before any delete command runs.
2. **Do only what the owner asks.** A question is not a go. Ask before starting runs, servers, agents, or anything that
   changes something outside this session; before renaming or restarting fresh. Public servers only on his word.
3. **Settings check before every run, check and calibration, and before using its numbers:**
   `python tools/run/check_settings.py <train.cmd> --ref <reference.cmd>` (and `--ck <checkpoint>` for a run's own saves).
   Any difference not deliberately allowed = the data is not used. Never build a run tool from an older copy.
4. **Correctness over speed.** Never skip or approximate a calibration to meet a start time; say what is missing and when.
5. **Red-team before a go.** Every run card lists each hand-built or assumed part of the pay and design, its measured
   alternative, and the ledger's pathology check (negative frags, sign flips, lopsided games). Volunteer weaknesses unasked.
6. **Never stop a run** unless the owner says so. **Ramps never hold or step back on their own** (owner, 2026-11-04: "All you do
   is report, not hold. You report with urgency when things look bad and we decide together"). Every check's win rate is
   reported; one **under 40%** is flagged in the chat at once as a major problem. He decides hold or stop.
7. **No personal data** in the repo (Steam IDs, IPs, usernames, passwords); public-server details stay in `private/`.
8. **Git**: explicit `git add <files>`; never rebase; commits end with the Co-Authored-By line; push `main` at most 1-2
   times a day; one working tree (the repo) plus at most one worktree per active run, made without links into `data/`.
9. **The running run gets full priority** (owner, 2026-11-04: "The run that is going gets full priority. Period."). No side job
   (a smoke run, a dry run, a level check, a measurement, a server) is started on my own while a run trains: it goes to him first,
   naming its cores (by mask), its length, and what it shares with the run (the graphics card, the trainer's cores, the watcher's
   check cores). To stop a job's processes, match each one's own command line: Windows reuses process IDs.
10. **Build the approved design, never a simplified one** (owner, 2026-11-05: "I approve the design and that's what you build. You
   do not manage time, I manage that."). Every part of an approved design is built; an unspecified detail is decided from the
   design's intent and recorded; a real structural fork goes to him. No start times, schedules or time estimates drive what is
   built: when it is ready (built and tested), he decides.
11. **A decision made from the sum of two learned outputs is always regularized** (owner, 2026-11-05: "That sum just seems like a
   prime spot ... to get some opposite sign blowup"). Where a choice's logits are the hands' rows plus a head's scores (the target
   since 1.3b, the weapon key since 1.5a, the fire key and the order's pointer since 1.7), both parts get the decay (`H2_L2`: the
   decoupled weight decay in `sim/train_duel_rnn.py` after `opt.step()`) from the moment the sum is live, and each part's size
   is recorded and flagged over 40 by the run's ramp. A new sum is not built without both.
12. **The pro demos are for measuring things, never for setting Bobby's behaviour** (owner, 2026-11-10: "it's mistreating a
   metric as a goal"). What may be taken from them: measurable facts of the game and of human limits (what a place on a map is
   worth, reaction and notice times, the sight and hand errors and how they grow). What may NOT be made a target, a pay, a lesson,
   a pull or a pass mark: any outcome of a player's choices (a hit rate by weapon, how often a weapon is held or fired, how often
   they hold, spam or contest, where they stand); every attempt to set him to one collapsed him (the weapon teacher, the pros'
   weapon table of 1.7c, the pull of the head to the pros). Such numbers may be shown beside his as a labelled readout; a
   proposal never says "bring him to the pros' X%". Aim: each parameter is set from the pros' own measured value of that
   parameter (default = the average pro, better = p90, max = all off); what hit rate comes out is not tuned. Do not suggest
   otherwise again.

## Where things are

| | |
|---|---|
| `docs/RUNS.md` | **the table of every run**: number, name, started from, start, stop, duration, updates, the change, outcome, kept file. The source of truth for what ran |
| `docs/PLAN.md` | the goal, where things stand, what's next |
| `docs/HISTORY.md` | notes beyond the table: design ideas tried that did not work or were abandoned, open problems, measurements without training, incidents, lessons that are now rules. Read it before proposing anything |
| `docs/BACKLOG.md` | open work and ideas, numbered `B-nn` |
| `docs/runs/<family>/` | one folder per family (`1.7/`, `2.0/`; older `b1.N/`, `v0.6.x/`): a `README.md` (the goal, the attempts) and a folder per attempt (`2.0/2.0c/`) with `CARD.md` (the owner's page + the checklist), `train.cmd`, `start.ps1`, the reference command, reports |
| `docs/design/` | current designs · `docs/guides/` how-tos · `docs/archive/` old versions, the old daily log, old CLAUDE.md (frozen) |
| `tools/run/` | the run tools: `check_settings`, `make_train_cmd`, `watch` (checks), `panel` (behaviour), `selfplay_loop` / `selfplay_log`, `live_accept`, `backup` |
| `data/` (git-ignored) | `sim_runs/<run>/{keep,snapshots,live.json,watch,...}`, `maps/`, `sim_runs/brainppl/`, `owner.env`. Backed up nightly to `T:\BobbyBones_backup` |
| `private/` (git-ignored) | the public servers' notes and scripts (`private/PUBLIC_SERVER.md` first; machine details in `data/SERVER.md`) |

## Starting and watching a run

**No dry run for small changes** (owner, 2026-11-04): "that's just the first 10 updates of the run." A dry run is only for changes
we are not sure of (a new lesson, a new part of the network, a new pay whose step is unknown). Small, identity-checked changes start
the real run directly; its first 10 updates and the extra check at update 10 are the trial.

1. The owner's go on the run's `CARD.md` (both parts filled in). **Ask him the length before starting**; 12 hours (`--minutes 720`)
   if he says the default.
2. `powershell -ExecutionPolicy Bypass -File docs\runs\<family>\<run>\start.ps1`: it runs the settings check and `live_accept`,
   refuses on any difference, checks the files are there and no trainer runs, then starts the trainer, the watcher and the
   self-play logger.
3. Its row in `docs/RUNS.md` at once (see Docs).
4. Monitoring from update 1, unasked: every FLAG and MAJOR line of `watch/watch.log`, `live_status.json` applied, dials played as
   written, a stall (no new line in `metrics.jsonl` for ten minutes). One line an hour; the 06:30 report after a night. Both carry
   the league table (frag share and win chance gained against each league network; [BACKLOG B-300](docs/BACKLOG.md)) beside the checks.
5. Cores (from b1.2d): the trainer alone on the 8 performance cores (`0xC03C3`); watcher, checks and logger on 8 efficiency cores
   (`0x3C3C`, `CHECK_BATCH=4`); 14-17 left for the owner. Checks every 20 updates, 200 games (`CHECK_EVERY=20`, `CHECK_GAMES=20`),
   against the control; every fourth against the long-term control.

## The owner's goals (read first)

- **One goal: win games** (owner, 2026-10-24). Goals are set per generation: the current one is in `docs/PLAN.md` (2.x, from
  2026-11-08: pay the stack and the control, not the damage; then the strategy layer, 2.1). Every change is stated by the
  equilibrium it leads to in self-play and the behaviour it brings out on the way.
- **Names**: N.Nx (owner, 2026-11-03): N.N is a family of runs with a goal of its own, x = a, b, c the attempts (2.0a, 2.0b);
  folders `docs/runs/2.0/2.0a/` and `data/sim_runs/duel_gru_2_0a`. What ran as b1.0a to b1.4a and v0.x keeps its name and folders.
- **Design from AlphaStar and Pluto** (owner, 2026-11-03) for anything strategic (the head, target and plan choices, memory, the
  league, the value and pay, handing a choice from rules to a learner): name which part a proposal takes from them, where it differs
  and why (one PC, our data, fairness). Pluto: [docs/archive/versions/v0.3/PLUTO.md](docs/archive/versions/v0.3/PLUTO.md). The rules
  taken so far: [docs/HISTORY.md](docs/HISTORY.md) (lessons that are now rules).
- **One new thing per round**, shut at the start, opened slowly with the checks reported; two new things open one after the other.
- **Genuine learned behaviour** (movement, weapon choice, item control, positioning), not hand-coded rules or knob tuning; the
  hard-wired rules and teachers are retired over time. **Fair**: human physics (125 fps), human senses (sight with line of sight,
  sound; enemy projectiles only as seen or heard), mouse-like aim with human limits. Never miss on purpose to hit a number.
- Jumps: "he should be taught the general path, there's many ways to execute them": pay and labels are for the way.
- **The control in every run**: the last best network stays in the league (`--anchor-p`) and every checked save plays it head to
  head; a network is promoted only if it beats the control. Judge checks by games won and lost; say plainly what did not work.
- **Maps**: the ten duel maps all in training (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds,
  Hektik, Toxicity, Cure); House of Decay and Dismemberment held out, never trained. No maps with doors. Test map `testlab`. Real
  games against the game's Nightmare bot: before and after a run, never in the middle; never train against the game's bots.
- No powerups anywhere, a map's **duel** items in every mode (`plugins/powerups.py`). Servers are 1v1 only (since 2026-10-23).
- Never change the owner's Quake Live client settings or configs in the Steam `Quake Live` folder (copying the test map pk3 into
  its `baseq3` is allowed).
- **The public servers**: a utility kept apart from the repo, all their details in `private/`; never move them, or an address,
  account, server name, Discord or config value, into a tracked file. A network goes on them only on the owner's call (and only
  if it beats the control); never restart one while he is on it; rcon there only when needed.
- Log as much as possible from human-played rounds. Keep everything. Render videos after a run unasked (`sim/render_course.py`).
- The owner prefers concise answers and doable batches.

## Inputs (owner, 2026-11-11; `docs/design/INPUTS_CLEANUP.md`)

- **By role.** "The brain makes predictions for what it believes is the truth. The head decides based on that what strategy to execute. And the
  hands execute the strategy." An input goes to the network whose job needs it; when it is rerouted it is faded in the old reader and then
  **removed** from it ("they're just dead weight"). Each network reads its own list by name, never "the first N columns".
- **Never cut a part of the game because he does not use it yet** (the ways, the heavy machine gun, the gauntlet, the grenade arc: "they are
  still part of the game that need to be in his networks"). Cut what is off for good (free-for-all, courses, styles, the legs switch).
- **A new input comes with its measured average and spread** (a sample of real play; by design where it is off), never the default "0 and
  1": every input since v0.2 was appended that way and 291 live columns arrived under 30% of their size.
- **Proved used, not only harmless**: an input health report before every run and at every check (constant columns, size outside 0.5 to 2,
  over 1% of rows at the clip, each group's share at each reader), and at a run's end 200 games with a new group blanked. No drop = it does
  not stay. The list's length is on every card.

## Docs (keep in sync, one commit)

- **`docs/RUNS.md` is the run table and the source of truth (owner, 2026-11-11).** Every run gets a row at its start (number,
  name, started from, start time, the change, card link): a false start, a side arm, a stopped or void run too. At its stop the row
  is finished: stop time, duration, updates, outcome (the checks' numbers and who stopped it), the kept file. A run's card's first
  row is "Started from". Run results live only there, never repeated elsewhere.
- **`docs/HISTORY.md` is for notes beyond the table**: an idea that was tried and did not work or was abandoned (what happened,
  why dropped, the lesson, the `#` of its runs), an open problem, a measurement without training, an incident, a lesson that
  becomes a rule.
- After a run, test or decision: the run's folder (card, report), its `RUNS.md` row, `HISTORY.md` if an idea was dropped or a
  lesson learnt, the backlog,
  `docs/PLAN.md` if its status changed, then `python tools/docs_check.py` (links, backlog numbers) before the commit.
- `docs/archive/` is frozen (the old daily log: "RESULTS 2026-10-08 18:45" = that entry; older text that says `docs/v<n>/...` means
  `docs/archive/versions/v<n>/`).
- `docs/INPUTS*.csv`, `docs/*.json`, `docs/MAPS.md`: data that tools read by path; they stay at `docs/` (B-203).
- `README.md` is the public page; keep it current with the docs.

## Architecture

- **Simulator** (`sim/`): `sim_api.c` + vendored ioquake3 movement and collision (`sim/q3`) -> `qsim.dll` (`sim/build.bat`, MSVC)
  or `libqsim.so` (Docker image). `qsim.py` wraps it. One `World` per process: never create a second one with a different size.
- **Environment**: `duel_env.py` (weapons, items, sounds, clock, human-aim limits, round kinds, scripted opponents, lab mode on the
  test map). `duel_env_ffa.py` is generated from it by `tools/make_ffa_env.py` (it matches exact lines of `duel_env.py`: the
  `OBS_DIM` line, the `observe()` concatenation, `pkind = ...`, `return [i ^ 1]`); `tools/ffa_check.py` proves it identical at two
  players. Change `duel_env.py`, then regenerate and re-check; never edit the generated file. New features go in behind switches,
  off = bit-identical (checked by fixed-seed replays).
- **Frozen simulators**: `sim/duel_env_<ver>.py` / `duel_env_ffa_<ver>.py` (v8 to v02, 20a, ...) are the simulators older networks
  were trained in; a policy is played and evaluated with its own module and inputs list (`--env`, `--inputs docs/INPUTS_<ver>.csv`).
  Freeze a copy before changing the inputs or actions of a simulator a run still needs.
- **The network**: GRU 512 with an attention part (`sim/attn.py`: the inputs cut into tokens by `docs/INPUTS.csv`'s groups; a
  token's gate starts shut, `--gate-open`); the brain (a separate memory predicting the enemy from his senses only, its answer
  into the hands as a token); the strategy head (target, keep choice, weapon scores); the hands. Widening keeps answers identical:
  new inputs at the end with zero weights (`tools/b17b_init.py widen-league`, `tools/b20b_init.py`, `sim/add_attention.py --same`).
- **Training**: `sim/train_duel_rnn.py` (PPO, league of snapshots + anchors, `--resume`, `--fade-start` on every resume). GPU
  PyTorch is in the Anaconda Python (`C:\Users\<user>\anaconda3\python.exe`); never import torch inside simulator workers.
  **Live settings**: `<run>/live.json` and `live_settings.env`, read between rollouts; ranges in `LIVE_RANGE`; every read in
  `live_status.json`. Checkpoints carry `env_vars` and round lengths; keep every run's end as `keep/policy_end_<run>.pt` with
  its optimizer (`opt_end_<run>.pt`).
- **Pay**: the pay table (items by the point, damage, frags) plus the win-chance judge (`sim/win_judge.py`, `WIN_ADD`), logged as
  a ledger every update.
- **Real game**: image `qlbot` (`Dockerfile`): Quake Live dedicated server + minqlx (`minqlx/`, patched, see `minqlx/UPSTREAM.md`)
  + `plugins/` + `sim/`. `minqlx/botctl.c` hooks `SV_ClientThink` (bot input, human physics substeps, view, items, missiles).
  `sim/export_duel.py` writes `policy.npz` (layout, weights, `env_vars`); `plugins/netpass.py` is the forward pass.
- **Plugins**: `duelbot.py` plays a network (inputs from the simulator's own `observe()`), hot-reloads `policy.npz`, logs sessions;
  `botmode.py` (`!map`, the ten duel maps; a new map needs its items in `plugins/duel_items.json`); `banlist.py`; `ladder.py` (the
  leaderboard by games won and lost, Glicko-1 in `ratings.py`); `banter.py`; lab plugins (`weaponlab`, `itemlab`, `maplab`,
  `droplab`, `movetest`). A Bobby is known by `duelbot.is_bobby`, not by a name.
- **Pro demos**: `tools/fetch_demos.py`, `sim/demo_dataset.py`; demos live in the folder named in `data/demo_root.txt`. Measuring
  only (hard rule 12).
- **Maps**: a new map: `python sim/build_nav.py --map <m> --v14` (system Python: scipy), `tools/nav_prune.py`, the map reader's
  tables in `data/maps/`. Atlas: `tools/build_atlas.py`. Test map: `tools/make_lab_map.py` (q3map2 + mbspc `-forcesidesvisible`
  from `data/tools`; bots need an `.aas`). Matplotlib is broken in the Anaconda Python: draw in the system Python.
- `legacy/`: the first approach (Nightmare bot + routes + coach). Not used.

## Running things (Git Bash; `export MSYS_NO_PATHCONV=1` before docker commands)
```bash
python sim/train_duel_rnn.py --run <run> --resume --minutes <n>      # Anaconda Python; runs start from start.ps1
python tools/duel_eval.py ... --opp policy:<file>                    # two networks head to head
docker build -t qlbot .                                              # after any change to sim/, plugins/ or minqlx/
bash tools/duel_server.sh <run> <map> <env module>                   # play-test server, UDP 27970 (no password unless PASSWORD=<word>)
NAME=qltest DATA=data/labtest SPAR=1 bash tools/duel_server.sh ...   # Bobby vs Nightmare (SKILL=4 Hardcore): benchmark only
docker exec <name> python3 /tools/rcon.py "qlx !room suite" --wait 2  # rcon ("status" prints nothing)
```

## Hard-won gotchas

**Runs and the trainer**
- **A refused live.json is refused whole, and the run then trains on its command's start values** (1.7a's false start): every
  live name that may be negative is in `LIVE_RANGE`; a refusal before the first rollout stops the trainer; `live_accept.py` in
  `start.ps1` reads the start's file and every one the ramp will write; every new live name gets its range and a `tests.py live` test.
- A wiring bug can look like a bad idea: 1.7c's false start (PPO's reference pass without the weapon key's mask) read as a slow
  collapse. When a check falls, look at the KL and the trainer's own pieces before the design.
- Restart only right after a save (every 10 updates), keep a copy; pass `--fade-start <minute>` on every resume.
- Write `.cmd` run files with the Write tool to the scratchpad and copy them over (Git Bash heredocs mangle backslashes; writing
  over an existing `.cmd` in a chain once failed silently and the old settings ran). After a patch to `sim/`, check the change is
  there (a write once failed with Errno 22 and left the file as it was).
- A scratch test must import the repo's `sim/`, not a staging copy. Two tools that import a module being edited mix versions.
- GPU memory: long sequences and many players fill the 16 GB card (`--minibatches`, `ATTN_AMP`); a first update that does not come
  within about six minutes means the card is full. After every widening, check `metrics.jsonl` keeps growing.
- `OPENBLAS_NUM_THREADS=1` in every `.cmd` and pool (else each worker commits 0.7 GB; Windows ran out of commit with 36 GB free).
  `CUDA_VISIBLE_DEVICES=-1` (not `""`) hides the card on Windows; a CPU trainer needs `OMP_NUM_THREADS=1`.
- Where an update's time goes: 40% rollout, 60% the learning step (Python steps the GRU per piece: time goes with the number of
  pieces, B-237). More simulator cores help the rollout only.
- `SetPriorityClass` via ctypes needs `restype`/`argtypes` on 64-bit Python; `subprocess` `creationflags=0x4000` works.
- The PC's load as Windows reports it reads far above the share of processor time: size side jobs by the load. The PC has
  blue-screened under load: runs save every 10 updates. Keep `PYTHONFAULTHANDLER=1` and the exit codes.
- A background shell is capped at two hours; chain waiters or launch detached.
- `tools/list_inputs.py` writes `docs/INPUTS.csv` whatever its arguments.
- An identity check after a new output: random actions for the old outputs only, or the random stream shifts.

**Design lessons (each cost a run)**
- The checks' noise: the same network against itself reads 48.8% over 160 games, single maps 41 to 56%. Read maps one by one too
  (v14 lost Aerowalk 24 points while the mean did not move). The control belongs in the checks from the first hour: "53% against
  his old selves" says nothing.
- A new lesson must pass ten updates and a check against the control before a start; a fitted start for a new choice must pass a
  full level check, not a probe.
- A teacher must have the pupil's hands and must not name what he cannot reach (v14: the item rule sent him over Aerowalk's circle
  jump; `RULE_WALK=1`). A teacher with new labels moves the whole network at once (`--teach-trunk`, `--teach-warm`).
- A new choice opened by a bias costs what it displaces: open it out of the one it stands in for (`targets_init.py open
  --from-nothing`); the entropy bonus spreads his choice over new equal choices whatever they pay, and drowns small shaping costs.
- Anything paid per frame for progress is paid on a running best, or a setback and its recovery is a pump.
- Whatever is paid by the damage must not be added to `dealt` (his feedback inputs are made of it).

**The real game and servers**
- The plugins call `observe()` but never `step()`: anything only `step()` updates is stale on a server unless the plugin sets it.
  After any input change, record the inputs in a real game (`OBSDUMP=1` with `tools/bench_arena.sh`) and set them beside the
  simulator's. Rebuild `qlbot` after any change to `sim/`, `plugins/` or `minqlx/`.
- Real-server checks only while no training runs. Before one: `docker ps`, `docker stats --no-stream`; stop servers nobody uses
  (`docker stop`, not `rm`).
- An rcon client that leaves while the server prints (a map load) can freeze the server: `tools/rcon.py` leaves only in a quiet
  moment; a map change gets `--wait 30`.
- Quake Live locks `sv_fps` at 40. The client uses UDP 27960, servers 27970. An idle server runs no frames until someone joins.
  minqlx has no damage event (hits from health drops); warmup emits no kill stats. Aborting a warmup countdown in a loop hangs the
  server. A chat line must not have a percent sign before a letter.
- A pure server's pak list must be exactly a client's (pak00, bin, the Workshop item), or players drop silently. `sv_pure` is
  write-protected; `sv_warmupReadyPercentage` and `sv_maxclients` are latched. The server's stdout lags through `tee`.
- Plugin changes can be tried without an image build: mount `plugins/` over `/ql/minqlx-plugins` and `tools/` over `/tools`.
- The game's pickup reach (7,767 pickups): 36 units each horizontal axis, any jump height; the simulator's (`dxy < 36`,
  `dz < 56`) lies inside it.
- Docker on Windows: LF line endings (`.gitattributes`).
- After merging a branch, push plainly: `git pull --rebase` on a merge commit replays the branch. Fetch and look first.

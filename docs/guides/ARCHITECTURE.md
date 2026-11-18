# How Bobby is built (moved out of CLAUDE.md on 2026-11-17)

What the parts are and where their code is. **This changes as we build**: the code's own notes at the top of each file are the
truth; when this page and the code disagree, fix this page. For where the design is going: [PLAN.md](../PLAN.md).

Known to be out of date on 2026-11-17: "the strategy head (target, keep choice, weapon scores)" (the keep choice went in 2.1c; from
2.2b the decision layer is an item picker and a fight network: [2.2b's card](../runs/2.2/2.2b/CARD.md); from 2.2c (2026-11-18) the
fight network is an aggression lever, one number added to the item picker's score of "the enemy", and the four fight options are out:
[2.2c's card](../runs/2.2/2.2c/CARD.md), [its build record](../runs/2.2/2.2c/BUILD.md)).

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
- **How he moves**: since v0.3.5 (`--no-switch 1`) **his own network always drives**. "His legs" are a branch of his network that
  suggests the keys for the way to his destination (`--legs-feat`, `--legs-gate`, `--legs-learn`); there is no separate walker and no
  switch. Never describe, or build, something that carries him (the session did, twice, on 2026-11-17, from the simulator's older notes).
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

- **The cleaned list 18 (2026-11-11; `docs/design/INPUTS_CLEANUP.md` "As built")**: `sim/input_list.py` + `sim/input_list_18.json` (804 of the
  simulator's 1,053 columns by name: the brain reads the first 691, the hands' encoder the first 796, a tail of 8 is read by no first
  layer: the guessing lesson's four marks and the yellows' timers; the other 72 rule-made columns of v0.2 to v0.3.6, the pre-fire and
  emergence among them, were cut the same day on the owner's word); `sim/duel_env_ffa18.py` is the group module giving that list (the trainer's `--env`; the simulator's own code is unchanged and
  `duel_env_ffa` stays the full list for every older network); `tools/inputs18.py convert` brings a 1,053-input network to it (cut and
  folded, resized, the optimizer's moments too; `same` proves it on real rows); a checkpoint of a list carries `inputs` and `input_names`,
  and the check tools give each network its columns by name. `tools/run/input_health.py <policy> <sample>` is the health report.
  **The plugins and `sim/export_duel.py` do not know a list yet: no server with such a network.**


## Running things (Git Bash; `export MSYS_NO_PATHCONV=1` before docker commands)
```bash
python sim/train_duel_rnn.py --run <run> --resume --minutes <n>      # Anaconda Python; runs start from start.ps1
python tools/duel_eval.py ... --opp policy:<file>                    # two networks head to head
docker build -t qlbot .                                              # after any change to sim/, plugins/ or minqlx/
bash tools/duel_server.sh <run> <map> <env module>                   # play-test server, UDP 27970 (no password unless PASSWORD=<word>)
NAME=qltest DATA=data/labtest SPAR=1 bash tools/duel_server.sh ...   # Bobby vs Nightmare (SKILL=4 Hardcore): benchmark only
docker exec <name> python3 /tools/rcon.py "qlx !room suite" --wait 2  # rcon ("status" prints nothing)
```


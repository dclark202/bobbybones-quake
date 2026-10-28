# Running training, checks and backups

## A run

Each model run has a folder `docs/runs/<version>/` with:

| file | what |
|---|---|
| `CARD.md` | the owner's page and the checklist (see [../README.md](../README.md)) |
| `train.cmd` | the trainer's command; every path relative to the repo (it computes ROOT from its own place) |
| `aim2_env.cmd` | the aim settings it calls (!aim default = the pros' mean) |
| `reference_*.cmd` | the command a restart must match (for the settings check) |
| `start.ps1` | the start: the settings check (refuses on any difference), the files and "no trainer running" checks, then the trainer, the watcher and the self-play logger |

A new run's `train.cmd` is made from the last one with `python tools/run/make_train_cmd.py <source.cmd> <version> [aim.cmd]`,
then its changes are made and listed on the card, and `tools/run/check_settings.py` shows exactly what differs.

## While it runs (`data/sim_runs/<run>/`)

| | |
|---|---|
| `metrics.jsonl` | one line an update (a stall: no new line in 15 minutes) |
| `keep/policy_<update>.pt` | a save every 10 updates, kept; `keep/policy_end_<version>.pt` + `opt_end_<version>.pt` at the end (always) |
| `watch/` | the watcher's checks against the control (`checks_prev.jsonl`), the behaviour panel, `watch.log` |
| `selfplay/u<update>/` | the self-play games logged once a second for the win-chance fit (B) |
| `live.json`, `live_settings.env` | settings changed while it runs (read between rollouts) |

## Stopping

Only on the owner's word: wait for the next save (policy.pt and opt.pt newer), then stop the trainer, then keep the end as
`keep/policy_end_<version>.pt` + `opt_end_<version>.pt`.

## Backups

`python tools/run/backup.py` copies what cannot be remade (every run's `keep/` and `snapshots/`, live settings, `data/maps`,
the brain packs, the movement network, `owner.env`) to `T:\BobbyBones_backup`, never deleting there. The Windows scheduled
task "BobbyBones backup" runs it nightly. Restore = copy back from `T:\BobbyBones_backup\data`.

## After a fresh clone or a move of the repo

- `sim/qsim.dll` is built, not tracked: build it with `simuild.bat` (MSVC), or copy the one from the last run's folder. An old
  build refuses to load ("always cuts velocity to whole units"): the check is in `sim/qsim.py`.
- `data/` moves with the repo (it is a real folder, never a link). `data/demo_root.txt` names the demos' folder (`T:\quake-demos`).
- The scheduled tasks name the repo's path: "BobbyBones backup" (`tools/run/backup.py`) and "BobbyBones session pull"
  (`tools/pull_sessions.sh`): update them after a move.

## Rebuilding data (what was learned on 2026-10-28)

| | from |
|---|---|
| map geometry `data/maps/<map>.bsp` | the game's own `baseq3/pak00.pk3` (a zip) |
| nav `nav_<map>_sim.json`, `cells_<map>.npy` | a public server's `data/maps` (training's own nav is not reproducible by `sim/build_nav.py` + `tools/nav_prune.py`: later edits) |
| the movement network `move_v17_look/policy.npz` | any `legs.npz` (the same file: `sha256` ab864265bb6dd000…) |
| the brain's pro pack `brainppl/pack_demo` | `sim/brain_data.py demo` on the demos named in its meta.json (`T:\quake-demos`), then `sim/brain_fit.py --save-pack` |

# docs/

| | |
|---|---|
| [PLAN.md](PLAN.md) | the goal, where things stand, what's next, the owner's standing decisions |
| [HISTORY.md](HISTORY.md) | every version and experiment: what it tried, what happened, the lesson |
| [BACKLOG.md](BACKLOG.md) | open work and ideas, numbered `B-nn` (closed items: [archive/BACKLOG_closed.md](archive/BACKLOG_closed.md)) |
| [runs/](runs/) | one folder per model run (from v0.6.0): `CARD.md`, its `train.cmd` and `start.ps1`, reports |
| [design/](design/) | current designs: [AIM2_MODEL.md](design/AIM2_MODEL.md) (the aim), places, zones, jumps, openings, QLStats |
| [guides/](guides/) | [RUNNING.md](guides/RUNNING.md) (runs and backups), [PLAYTEST.md](guides/PLAYTEST.md), [COMMANDS.md](guides/COMMANDS.md), [LOGS.md](guides/LOGS.md), [ATLAS.md](guides/ATLAS.md) |
| [archive/](archive/) | frozen: the per-version folders v0.2 … v0.5.3 (`versions/`), the daily results log ([RESULTS.md](archive/RESULTS.md)), old plans |
| `INPUTS*.csv`, `*.json`, `MAPS.md` | data that tools read by path (they stay here until the tools' paths move: B-203) |

## A run's card (`runs/<version>/CARD.md`)

Two parts, both filled in before the owner's go:

1. **The owner's page**: start, aim, pay, mix, length, checks, stop rule, schedule, in plain words.
2. **The checklist**: every hand-built or assumed part of the pay and design with its measured alternative; the pay ledger's
   pathology check (negative frags, sign flips, lopsided games) at the planned values; where each calibration number comes
   from; what is logged for the next run; the settings check (`tools/run/check_settings.py`) passed.

## The routine

After a run, test or decision: the run's folder, a line in HISTORY.md, the backlog, PLAN.md if its status changed, then
`python tools/docs_check.py` before the commit.

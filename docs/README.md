# The docs: what is where, and how it is kept

Put in order on 2026-10-10 and cleaned up on 2026-10-15: everything from before v0.1 (the first approach, the numbered models v1 to v15b, their log and old plans) is kept locally, out of the repo.

## What is where

| Place | Holds | Changes when |
|---|---|---|
| [PLAN.md](PLAN.md) | The goal, the approach, a status table of today, the "Now" list (the owner's priority list and backlog numbers only), the owner's decisions | The status, the priorities or a decision of the owner's changes |
| [BACKLOG.md](BACKLOG.md) | The open work, each item with a number (`B-nn`), grouped by the owner's priority list | An item is added, started or closed |
| [RESULTS.md](RESULTS.md) | The index of the results log: one line an entry, by day | Every entry |
| [results/](results/) | The results log itself, one file a day, newest entry first: what was tried and measured, what did **not** work included | Every run, live test, measurement or decision |
| `v<model>/` ([v0.4.3/](v0.4.3/), [v0.4.2/](v0.4.2/), [v0.4.1/](v0.4.1/), [v0.4.0/](v0.4.0/), [v0.4/](v0.4/), [v0.3.11/](v0.3.11/), [v0.3.10/](v0.3.10/), [v0.3.9/](v0.3.9/), [v0.3.8/](v0.3.8/), [v0.3.7/](v0.3.7/), [v0.3.5/](v0.3.5/), [v0.3.4/](v0.3.4/), [v0.3.3/](v0.3.3/), [v0.3.2/](v0.3.2/), [v0.3.1/](v0.3.1/), [v0.3/](v0.3/), [v0.2.2/](v0.2.2/), [v0.2.1/](v0.2.1/), [v0.2/](v0.2/)) | **A folder a model** (owner, 2026-10-13): its run sheet (`RUN_v<n>.md`), manifest, mid-run report, full report and design proposals. From v0.4.0 on, one folder per main run (owner, 2026-10-24): its restarts and trials go in the same folder; `v0.4/` keeps the design papers from before v0.4.0, and the generation's path is in `v0.4.0/` (PATH_v0.4.md) | A run is planned, started, reported |
| [guides/](guides/) | How to use and read things: the play-test routine and the test suite (PLAYTEST), the server's chat commands (COMMANDS), the formats of recorded data (LOGS), the map atlas (ATLAS) | The thing they describe changes |
| [design/](design/) | What belongs to no one model (QLSTATS); `jumps/`: the pros' jumps a walker cannot make, a picture and a table per map (`tools/pro_gaps.py`, `tools/draw_gaps.py`) | A proposal is written or decided |
| [archive/](archive/) | The closed backlog items | An item is closed |
| `INPUTS*.csv`, `*.json`, [MAPS.md](MAPS.md) | Data that tools write and read by path: the network's inputs (today's and those of older networks), the pros' tables, measured values, the list of maps | A tool writes them. They stay in `docs/` until the tools' paths are moved with them (B-203) |

The public page is the [README](../README.md) of the repository; `CLAUDE.md` there holds the project notes for the
assistant.

## The routine

**After a run, a live test, a measurement or a decision of the owner's**, in one commit:

1. **An entry in the results log.** Write it as a Markdown file whose first line is `## <date> <time> — <the finding>`,
   then `python tools/add_result.py entry.md`: it goes to the top of `results/<date>.md` and gets its line in the
   index. An entry says what was done, the numbers, what did not work, and names the backlog items it settles or
   raises. Entries are not rewritten later; a correction is a new entry that names the old one.
2. **The backlog.** A new item gets the next free number and goes into the section it serves. An item that is done,
   dropped or overtaken moves with its row to [archive/BACKLOG_closed.md](archive/BACKLOG_closed.md).
3. **The plan**, if the status table, the "Now" list or a decision changed. The "Now" list holds backlog numbers, not
   prose; history does not go into the plan (it is in the log).
4. **A run's documents** in the model's folder (`v0.2.1/`): the one page (`RUN_v<n>.md`), the manifest before a start (changes during the run are added to its section 0),
   a mid-run report when the owner asks for one, the full report at the end with what to try next.
5. **`python tools/docs_check.py`**: every link leads somewhere, every entry of the log is in the index, no backlog
   number is used twice, the plan's "Now" names items that exist.
6. The public README and `CLAUDE.md` when what they say has changed.

**Names.** A run's documents carry its version (`MANIFEST_v0.2.md`); a day's log is `results/<date>.md`; a proposal
is named for what it proposes. No dates in file names except in `results/`.

**When the plan gets long**: what is over (a run that ended, a decision that was replaced) is cut out of `PLAN.md`; the
log keeps the history.

**What does not belong here**: personal data (names of visitors, addresses, Steam IDs), raw data (it lives in the
git-ignored `data/` folder; an entry gives the path), and the public server's setup: its address, accounts, configuration and deploy routine are kept outside
the repo (owner, 2026-10-19).

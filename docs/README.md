# The docs: what is where, and how it is kept

Put in order on 2026-10-10 (owner: "take a pass at cleaning up the docs ... create a better organization routine").

## What is where

| Place | Holds | Changes when |
|---|---|---|
| [PLAN.md](PLAN.md) | The goal, the approach, a status table of today, the "Now" list (the owner's priority list and backlog numbers only), the owner's decisions | The status, the priorities or a decision of the owner's changes |
| [BACKLOG.md](BACKLOG.md) | The open work, each item with a number (`B-nn`), grouped by the owner's priority list | An item is added, started or closed |
| [RESULTS.md](RESULTS.md) | The index of the results log: one line an entry, by day | Every entry |
| [results/](results/) | The results log itself, one file a day, newest entry first: what was tried and measured, what did **not** work included | Every run, live test, measurement or decision |
| [runs/](runs/) | A run's own documents: `MANIFEST_v<n>.md` (the run in full, for the owner's go), `MIDRUN_v<n>.md` (a report while it trains), `REPORT_v<n>.md` (the full report of its network) | Before, during and after a run |
| [guides/](guides/) | How to use and read things: the play-test routine and the test suite (PLAYTEST), the server's chat commands (COMMANDS), renting and starting a server (HOSTING), the community page (COMMUNITY), the formats of recorded data (LOGS), the map atlas (ATLAS) | The thing they describe changes |
| [design/](design/) | Proposals not tied to one run: what is scoped for later (SCOPE_v15, ATTENTION_POC); `jumps/`: the pros' jumps a walker cannot make, a picture and a table per map (`tools/pro_gaps.py`, `tools/draw_gaps.py`) | A proposal is written or decided |
| [archive/](archive/) | What is no longer in force, kept whole: closed backlog items, the plan as it stood | Something is closed or replaced |
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
4. **A run's documents** in `runs/`: the manifest before a start (changes during the run are added to its section 0),
   a mid-run report when the owner asks for one, the full report at the end with what to try next.
5. **`python tools/docs_check.py`**: every link leads somewhere, every entry of the log is in the index, no backlog
   number is used twice, the plan's "Now" names items that exist.
6. The public README and `CLAUDE.md` when what they say has changed.

**Names.** A run's documents carry its version (`MANIFEST_v14.md`); a day's log is `results/<date>.md`; a proposal
is named for what it proposes. No dates in file names except in `results/` and `archive/`.

**When the plan gets long**: what is over (a run that ended, a decision that was replaced) is cut out of
`PLAN.md`; the plan as it stood then is kept whole in `archive/PLAN_<date>.md`.

**What does not belong here**: personal data (names of visitors, addresses, Steam IDs), raw data (it lives in the
git-ignored `data/` folder; an entry gives the path), and anything about the public server's address or accounts.

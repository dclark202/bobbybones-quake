# 2.1f: handoff (2026-11-16, 15:30)

For the agent who picks 2.1f up (owner, 11-16: "I'll have another agent pick up with 2.1f"). Read [CARD.md](CARD.md) first, then this.
The hard rules of `CLAUDE.md` apply; rules 15 and 16 were added on 11-15 and matter here.

## Where things stand

| | |
|---|---|
| Training | **nothing trains.** 2.1e was stopped by the owner at 15:17 |
| The network 2.1f starts from | **2.1d's end**: `data/sim_runs/duel_gru_2_1d/keep/policy_end_21d.pt` + `opt_end_21d.pt` (update 158; the lock out, the pull 2.0; on T: with its SHA-256 read back) |
| 2.1e's end | `data/sim_runs/duel_gru_2_1e/keep/policy_end_21e.pt` + `opt_end_21e.pt` (update 50; a slow-half network that plays about as 2.1d's end). The owner keeps it for a play test |
| main | everything of 2.1c, 2.1d, 2.1e, half precision everywhere (`bhalf`), the slow halves (`b21e`) and the readouts of his changes of mind (`b22r`) is merged. **Not pushed** |
| The worktree | `C:\Users\dacla\Documents\gh\BobbyBones-21d`, branch **`b21f`** (on `b22r`). No `data/` there: tools read data through `QLBOT_ROOT=<the main checkout>` |
| **The 2.1f build** | **in flight when this was written**: an Opus 5.5 subagent of the session that wrote this note is building on `b21f` (uncommitted files seen at 15:19: `sim/outlook.py`, `tools/out_init.py`, `docs/runs/2.1/2.1f/` run files, edits to the trainer, `head2.py`, `test_suite.py`, `netpass.py`, `export_duel.py`). **Do not edit the worktree until its commits are there**; its report is appended below under "The build's report" when it lands. If that section is still empty, look at `git -C ..\\BobbyBones-21d log` and `status` before doing anything |
| Processes that may still run | 2.1e's watcher (`tools/run/watch.py duel_gru_2_1e`) finishing its update-50 check (to about 15:55); it is idle after and can be stopped (match its own command line; `docker stop` never `rm`; nothing is deleted) |

## What the build was asked for

The card's design as changed at midday ("Changed after thinking it through"), in three messages to the build:

1. The first brief: the outlook inside the head (`head2.out.*`), four label kinds, a goal-blind yardstick beside each, the term in the target
   choice (stored as played, in the proof), its own Adam and rule 11's decay, trial trips (`OUT_TRIAL`, default 0, left out of his
   policy's learning), every reader of a network file, `tools/out_init.py`, `tools/run/out_playtest.py`, the run folder, the tests.
2. The redesign: a fifth label **`seg`** (the pay until he lets go of the goal, plus the head's value there) which plays by default;
   the lesson on **every keep reading** with the goal he is on (skill reported for decision and stay readings apart); the term **at its
   true size** (the label's standardised units, no rescaling by its own spread; `OUT_G` 0 to 20); **the ramp never opens `OUT_G` by
   itself**: it waits for `<run>/watch/out_mark.json` (`{"mark": x, "from": u, "to": u}`), written on the owner's word at update 30;
   readouts to choose the mark (the share of his choices the term would change at 0.5, 1, 2, 4, 8).
3. A readout that names the proof's worst frame (where it fell, how unlikely the target was, how many frames exceed 0.003 and 0.01).

## What is left before a start (in order)

1. The build's report read against the card; its diff reviewed; merged into main (plain `git merge`, never a rebase).
2. **A full-size update on the graphics card** (the run's first two updates are that test: the trainer's memory and the card's; the
   first update should come within about six minutes).
3. The card finished from the build (what was built, the tests, the decisions it took) and the owner's go on it. **Ask him the length.**
4. `powershell -ExecutionPolicy Bypass -File docs\\runs\\2.1\\2.1f\\start.ps1 -Minutes <n> -Updates <n>`; its row in `docs/RUNS.md` (#58) at once.
5. Monitoring from update 1 (every FLAG and MAJOR line, the dials played as written, a stall), one line an hour, the 06:30 report.
6. **At update 30: the silent stage's numbers to the owner**, who sets the strength (the mark) or leaves it shut: each outlook's skill
   and the yardstick's, on decision and on stay readings; how far apart the goals' outlooks are; the share of choices the term would
   change at each strength; which pay and which window predict best.

## Decisions that are the owner's (not taken)

| | |
|---|---|
| **Commitment trials** | whether a small share of trial trips may be held to their end with his mid-trip changes shut, to learn what real commitment is worth ("if I commit to X"). It is the lock on a small share of trips, for measuring. His rule: the lock never returns. Asked 11-16, not answered. **Not built** |
| Trial trips (`OUT_TRIAL`) | built, at 0; not opened without his word |
| The strength at update 30 | his, from the silent readouts |
| The length; tonight or not | his |
| Which network he play-tests | 2.1e's end (kept for it) or 2.1d's end; **the `qlbot` image must be rebuilt first** (half precision in the plugins, the slow halves' pass); only while nothing trains, or with his word |

## How to read the numbers (the owner's corrections of 11-15 and 11-16; do not repeat my mistakes)

- **A count of re-decisions is never a measure.** Fewer trips, fewer changes of mind, fewer interrupts are not progress and more are not
  a fault. "Interrupt because responding to something is what should be happening. Interrupt for no good reason is what shouldn't." No
  flag or threshold on any such count.
- The readout of his changes of mind (in `rec["plan"]["changes"]`, one ramp line an update): after news or quiet, stuck or back within
  2 s. Only "no news and back" is plainly bad. News is present at about 60% of all moments, so "after news" is a weak label; a "back" is
  typically away for 0.2 s. **A sharper version (a back counts as a response only if he was away long enough to act) is not built.**
- What decides: he fights (frags and damage a match-minute), the checks' games won and lost, and against the two failures the owner
  named: camping one item, wandering with no purpose (their readouts are not built).
- Single maps in a check swing by more than they tell (Campgrounds read 6-14, 6-14, then 14-6).
- The pull's proof sits at 0.0002 to 0.003 on the card and spikes on a single update now and then (0.0441 once) with no trend; untraced.
- Say plainly, with odds, whether a plan will work. Mine for 2.1f: skill above the yardstick about 60%; a visible gain in one night 20 to 25%.

## Also open

- The league table by opponent was not written by 2.1d or 2.1e (`data/sim_runs/league_table.json` dates from 11-04): find out why.
- Aerowalk was under level in 2.1d's last three readings (8-12, 7-13, 6-14): not looked at.
- `docs_check` reports 3 problems, all old broken links in 2.1a's files.
- The ramp of 2.1e raised a flag on the count of interrupts; it is removed on main. The same thinking must not come back in `ramp_21f.py`.
- 2.2 and 2.3 were rewritten from how 2.1 ended ([2.2](../../2.2/README.md), [2.3](../../2.3/README.md), the reasons in
  [the review](../../2.2/REVIEW_2026-11-16.md)); the owner has not reviewed them yet. If the outlook works it is the part 2.2's plays
  are judged by, and those documents should then be revised to hang off it.

## The build's report

(appended when the subagent reports)

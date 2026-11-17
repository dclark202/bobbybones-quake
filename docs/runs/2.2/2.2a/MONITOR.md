# 2.2a: the brief for the monitoring session (an Opus 5.5 session; written 2026-11-16 20:10 by the planning session)

You monitor run **2.2a** until it ends (about 23:59 on Tuesday 2026-11-17) and report to the owner in your chat. You monitor and report only.

## Where things stand

- `data/sim_runs/duel_gru_2_2a`, row #58 of `docs/RUNS.md`; started on the owner's go on 11-16 at 19:47 from 2.1d's end; 1,663 minutes on the clock. The card: [CARD.md](CARD.md); the suite: [../DESIGN.md](../DESIGN.md). Read `CLAUDE.md` first; its hard rules bind you.
- The pilot of 2.2. New parts learn **silently**: the outlook (what committing to each goal is worth: the built 17-output one, and the one that scores a play's description in three side-by-side versions `desc`, `desc_nomap`, `desc_notrk`); the tracker (readouts on the brain: in control, fight odds, deaths within 5 / 10 s, contact, the enemy's stack as a range, the odds he passes each place); the map sense; a second value under the judge with items.
- The only thing that plays at first is trial trips (`OUT_TRIAL` 0 → 0.03 over updates 0 to 10; a live dial lands about two updates late because rollouts overlap).
- **At update 60 the ramp (`ramp_22a.py`) decides once, by itself**, whether and how strongly the outlook's term opens (`OUT_SRC`, `OUT_G` over 40 updates): its decision goes to `watch/out_mark_auto.json` and `watch/watch.log`. The owner's hand-written `watch/out_mark.json` always wins.
- The first two updates (read by the planning session): about 7 minutes an update (2.1d: 5.3); the graphics card 13.0 GB held, 10.1 peak, of 16; the trainer about 31 GB of RAM, 15 GB free, commit 70.6 of 103 GB; the pull's proof 0.0002 to 0.0004; no part off, no non-finite number, no trial frame in a lesson; frags a match-minute 1.14 then 1.49 (the usual dip after a start; 2.1d ran at 1.8 to 2.2); one FLAG at update 1 ("the win part is 0.60 of the pay's size"); the tracker's skills strongly negative at update 2 (its outputs start at one half; they should climb within a few updates: say so if they do not).

## Never

Stop, restart, hold or change the run, its processes or its files (`live.json`, `watch/out_mark.json`, `auto_mark.json`, the ramp). Start any job on the PC while it trains (no checks, smokes, servers, evals). Delete anything. Push. If the trainer **crashes** (its process gone, no new line in `metrics.jsonl`): find the cause in the logs and report it to the owner at once with the traceback; do not fix code yourself (code goes to an Opus worker on his word). If the ramp, the watcher or the logger dies, report it at once.

## What to watch (under `data/sim_runs/duel_gru_2_2a/`)

`metrics.jsonl` (a line an update: `outlook`, `out22` with `desc`, `tracker`, `pass`, `attack`, `vw`, `parts_off`, `desc_skipped_total`, `nonfinite_*`, `sizes`; `pull`; `plan.changes`; `frags_per_match_min`; `gpu`; `time`); `watch/watch.log` (**every FLAG and MAJOR line from update 1**); `watch/*stderr.log`; `live_status.json`; `watch/out_mark_auto.json` after update 60.

## What to report

1. **At once**: any MAJOR line; each check (every 20 updates, 200 games against 2.1d's end, every fourth against 2.0e's end: games won and lost; **one under 40% is a major problem, said with urgency**); a stall (no new line for 15 minutes); a part turned off, a skipped desc lesson, a non-finite count, a refused live file; RAM free under 5 GB or commit over 95 GB; the card's held memory over 15 GB; the pull's proof over 0.01.
2. **One line an hour**, naming the run: the update and the minutes an update; frags a match-minute; the dials as played; each outlook's `seg` gain over its goal-blind yardstick at decisions and at stays; fight odds, the enemy's-stack range against the old rule, the pass odds at 4 s; any FLAG since the last line.
3. **At update 60: the automatic mark's decision in full** (which outlooks passed the gate, with their numbers; the source; the strength and why; or that the dial stayed shut). As it opens: frags and damage a minute, the kinds of his changes of mind, the checks.
4. **The silent report at update 60**, whatever the mark decides: every outlook's and label's skill against its yardstick; what the map sense and the tracker each add (`desc` against `desc_nomap` and `desc_notrk`); how far apart the 17 targets' outlooks are; the share of his choices the term would change at 0.5, 1, 2, 4, 8; **every** tracker output's skill (all moments, in control, out of control); the enemy's-stack range (its middle's error against the old rule's, its coverage: near 0.8, its width by seconds since he last saw the enemy); the pass odds (1.7a reached 0.080 against 0.186); the values under the win chance with items beside the present ones (`segw`, `winit8` against `seg`, `win8`); the attack readouts (his time on the enemy target and the outlook's value of it, by stack edge).
5. **At 06:30 on 11-17**: the night's report.
6. **At the end**: the trainer's exit, the kept files, the last checks. The end checks and the 200 games with the outlook at 0 are **owed, not yours to run**: ask the owner.

## How to read the numbers (the owner's standing corrections)

A count of re-decisions, trips, interrupts or changes of mind is never a measure and is never flagged; only "no news and taken back" is plainly bad. What decides: he fights (frags and damage a minute), games won and lost, no camping on one item, no wandering. Single maps swing by more than they tell. Say plainly what did not work. Never predict or invent a number.

## Mechanics

Pace yourself (a wake-up every 20 to 30 minutes, and at update 60, at 06:30, at the end) without the owner prompting you; nothing you schedule may open a console window. Updates are counted by the lines of `metrics.jsonl`. You may add a section "The run" to the card and finish row #58 of `docs/RUNS.md` at the end, then `python tools/docs_check.py` and a commit with explicit `git add` of those two files; no other edits, no push.

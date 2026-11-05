# 1.6a: the item teacher out and the lock handed to the keep choice, from 1.5a's end

*2026-11-04 evening (owner): "Before anything is faded out, let us introduce having the head contribute to weapon choices. That way we can
then fade it out concurrently (or in succession) with the hard coded teacher, and other fades in 1.4b/c"; "1.6 is really then about
dropping the item teacher and the handing over the lock. We'll review that further in a different session." Starts from
[1.5a](../../1.5/1.5a/CARD.md)'s end, if it passes. The family: [README](../README.md). **A proposal for the next session to plan: nothing
built for 1.6 itself, nothing run; the code for both changes exists (below).** The run starts only on the owner's command.*

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In short

| | What | Where it was built and tried |
|---|---|---|
| **The item teacher out** | the item rule's lesson on his target choice (live `INTENT_TEACH_W`, 1 at 1.5a) faded 1 → 0: his target (which item, which place) is then learnt from pay alone, by the hands' rows and the head's scores together | [1.4b](../../b1.4/1.4b/CARD.md): 1 → 0 over updates 10 to 70 (`ramp_14b.py`) |
| **The lock handed to the keep choice** | today a target holds 8 s (really 9) whatever happens, unless taken, gone, or the enemy was seen in the last 2 s ("blinders"). The keep choice: at each reading, keep the target or re-decide; the lock rule's readings handed to it by a share `KEEP_G` 0 → 1. AlphaStar's no-op, Pluto's "no new order" | [1.4c](../../b1.4/1.4c/CARD.md): built and tested, never run (owner, 11-04: not continued); code in branch `b14c`, which is under `b15a` |
| Still to place ❓ | the speed pay out (1.4b: `SPEED_PAY` 0.125 → 0 over 70 to 90); matchmaking by difficulty (1.4b: `--pfsp`, live `PFSP` 0 → 1 over 0 to 10; the varied anchors then at a fixed share, `--pfsp-fixed`) | both in 1.4b |
| Already out (in 1.5a from update 0) | the switch cost, the weapon override, the blind-fire cost | 1.4b, 1.4c |

**Why now and not before:** in 1.5a the head learns to use the rail and rockets while the item teacher still keeps his pickups of them up.
1.6 takes the teacher away once owning a rail is worth something to him; the watch is whether his big weapons owned and his weapon by
distance hold through the fade.

## What 1.4b and 1.4c showed ✅

| | |
|---|---|
| 1.4b (from 1.3b's end; scrapped by the owner at update 113, 11-04 evening; its end kept at update 110) | the teacher 1 → 0 over 10 to 70, the speed pay out over 70 to 90, matchmaking by difficulty from update 0. Checks against its start: 105-95, 112-88, 109-91, 107-93 at updates 10, 30, 50, 90 (52.5 to 56.0%); against b1.2d's end 181-19 (90.5%) at update 70. No collapse in games, but a drift: big weapons owned 1.78 (u10) → 1.70 (u90) → 1.67 (u107), still falling after the fade ended; his time in games with the lightning gun 0.56 → 0.60, rockets 0.23 to 0.26, the rail 0.02 |
| 1.4c (built, not run) | the keep choice: a choice of two at each reading (keep / re-decide), its start the lock made soft (`tools/keep_init.py add`: out of contact the chance to re-decide σ(0.75 × (age − 8.5 s)), in contact 0.9); credited on the head's clock, no entropy bonus, no pay of its own; `KEEP_G` 0 → 1 over updates 10 to 90, each league network at the share in its own file. Its level check (the fitted-start rule) passed on a 1.4b save: 112-88 (56.0%); its tests (`ident.py`, `smoke.py`, `ramp_test.py`) passed 11-04. It found the blinders still there at the start: a sound out of contact left his target kept 92% of the time |
| Found 11-04 (1.5a's build) | a reached holding place is a forced re-decision under the keep choice (`forced_` includes `intent_done`, set by `note_holds`): at a hold his target is drawn again every reading and the keep choice never decides there. ❓ leave it, or make a reached hold keepable (a simulator change) |

## The proposal (for the session that plans it)

| Step | Updates | What | Dial |
|---|---|---|---|
| 0 | 0 | 1.5a's end given the keep choice at share 0 (`keep_init.py add`; `same`: 0 actions differ against 1.5a's end) | `--keep-g 0` |
| 1 | 0 to 10 | as 1.5a's end: the trial, a check at update 10 | |
| 2 | 10 to 70 | **the item teacher out** | live `INTENT_TEACH_W` 1 → 0 |
| 3 | 70 to 150 ❓ | **the lock handed to the keep choice** | live `KEEP_G` 0 → 1 |
| | | the speed pay, matchmaking by difficulty ❓ | |

❓ **One run in succession (above, about 13 hours) or two runs** (1.6a the teacher, 1.6b the lock, each 12 hours with a report between).
Two runs read cleaner (one change a run, the owner's rule of 10-24) and give a decision point after the teacher; one run is faster. The
owner said "concurrently (or in succession)". Nothing holds or steps back on its own (CLAUDE.md rule 6): every check reported, under 40%
flagged at once; the owner decides.

## Before the start ⏳

| | |
|---|---|
| The code | ✅ both changes exist in branch `b15a` (1.5a's; `b14c` under it): the trainer's keep choice (`--keep-g`, live `KEEP_G`), `tools/keep_init.py`, the simulator's keep column (`sim/duel_env.py`), the checks' per-seat share (`sim/test_suite.py`, `tools/duel_eval.py`, `ws_eval.py`, `dump_eval.py`); the teacher's dial (live `INTENT_TEACH_W`) |
| **The optimizer's groups with both new parts** ⏳ (must be built and tested) | 1.5a's end has the head's weapon part and no keep choice; its saved optimizer's last groups are [the head's, the weapon part's]. The trainer's resume branches (`sim/train_duel_rnn.py`, the `len(os_["param_groups"])` chain) make the groups in the order head, keep, weapon for a network with both; 1.5a's optimizer (head, weapon) then matches the branch for a 1.4c save (head, keep), fails to load (the weapon part's group is not the keep choice's size) and the trainer goes on with a **cold optimizer**, saying so in one log line only (`optimizer: opt.pt does not fit ...`). Needed: a branch for "saved with head + weapon, now head + weapon + keep" (load head, weapon; add keep after) and the same order on every later resume, checked by a smoke that restarts from a save |
| Run files | from 1.5a's command (`docs/runs/1.5/1.5a/make_files.py`'s `train.cmd`): `--keep-g 0`, the run name, the length; the settings check against 1.5a's command and its end; a ramp with the teacher's and the keep choice's dials (1.4b's `ramp_14b.py` and 1.4c's `ramp_14c.py` as models; `--free`); `start.ps1` from 1.5a's end (its anchors, 1.5a's end as the control and an anchor) |
| The level check of the start 🧪 | the keep choice's start is a fitted start (the soft lock): the standing rule (2026-10-11) asks a full level check, 200 games, the start at share 1 against 1.5a's end (1.4c's `level.py`) |
| Identity | `keep_init.py same` (share 0 = 1.5a's end to the bit); the trainer at a fixed seed with the keep choice at share 0 against 1.5a's code (1.5a's `tests.py ident` as a model) |
| The checks | 200 games every 20 updates against 1.5a's end, every fourth against b1.2d's end, an extra one at update 10; the head's weapon scores switched off at the end (1.5a's `blank_check.py`); the keep counters (`stats["keep"]`: who decided, re-decisions, the blinders) |
| No dry run | (owner, 11-04) for small, identity-checked changes; the first 10 updates and the check at update 10 are the trial |

## Watched and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.5a's end; against b1.2d's end | level or better (the checks' zero point: the same network against itself, about 50%) |
| **Big weapons owned** | holds at 1.5a's level through the teacher's fade (1.4b: 1.78 → 1.67) |
| **His weapon in hand by distance, rail and rockets in hand** | holds or keeps bending toward the pros' (1.5a's measures) |
| The head's weapon scores | keep their size and their worth (the check with them switched off) |
| The mega and red armor taken first, stack at fights | hold |
| The blinders (1.4c): his target kept after a sound or a hit from out of view | down |
| No flicker (b1.1a's sign): trips a minute, targets reached | no slide |
| Speed on trips, air time | hold (owner: "speed is the thing to watch") |
| The holding places' share of his time | no rise like 10-12's |

## Red team (to complete when planned)

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The teacher's fade over 60 updates | 1.4b's pace | slower | big weapons owned, update by update |
| The keep choice's soft-lock start | assumed (1.4c) | a flat chance; the hard lock | the level check |
| A reached hold forced to re-decide | the simulator's rule | a hold keepable | time at holds, re-decisions there |
| The speed pay and `RAIL_FAR_PAY` 0.25 still on | single-behaviour pays | out, one at a time | speed; rail in hand |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## The owner's decisions ❓

| | |
|---|---|
| 1 | One run in succession, or two runs (the teacher, then the lock) |
| 2 | Where the speed pay's fade and matchmaking by difficulty go |
| 3 | A reached holding place: keep the forced re-decision, or make it keepable |
| 4 | The length, and the start (on his command) |

## The result

Not started.

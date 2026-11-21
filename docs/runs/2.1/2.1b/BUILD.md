# 2.1b: what was built (2026-11-14), and how it was tested

The family's design: [../README.md](../README.md) (decided 11-14). Owner's answers of 11-14: **one run** A to D (it may run on Sunday by
day); **the map sense as head inputs is 2.2's first step** (not built here; it learns silently, as in 2.1a, only if `--map-sense` is
given); **the side jobs on cores 14-17 at idle**; on the keep choice's start the owner asked for help ("fitting has proven to be a shit
move"): the recommendation built as the default is below (decision 1). Branch `b21b` in the worktree `BobbyBones-21` (the main checkout
was left alone while 2.0e trains: its watcher starts fresh processes that import `sim/`).

## Decisions made while building (for the owner's review)

| # | Decision | Why | The alternative, if the owner prefers |
|---|---|---|---|
| 1 | **The keep choice starts at zero, not fitted** (`tools/keep_init.py add --start zero --quiet 1`): every weight and the bias 0 | Rule 13 and the owner's experience with fits. At share 0 it plays nothing (identical to the bit); in step A it learns silently from its own lesson toward the stay value's sign (measured forks), so it is never a copy of the lock. Cost: step B now depends on the stay value having learnt something (M2 moves to the end of step A) | `--start fitted` (1.7a's soft lock) is still there |
| 2 | **The stay value is a module of its own** (`sim/stay.py`), not a seventh question of the appraisals | M1 decides "appraisals or a head of its own"; 2.1a's appraisals learnt nothing, and this question is narrower. It reads the same situation (brain, hands' memory, head) + the keep choice's own 7 numbers + the 5 change signals; its output is "keep beats a new draw by", in the head's value units | the appraisals' `dv` asked twice |
| 3 | **The label**: the same moment forked twice, his held target forced in one, a target **drawn from his own scores** in the other (it may be the held one: that is what a re-decision is); keep less new over 8 s in contact / at an arrival, **30 s in quiet** (a trip); the head's pay and value as 2.1a's appraisals (V at the moment cancels) | A re-decision is a draw, not "the best other target" | the best other target by his scores |
| 4 | **The keep lesson**: both layers taught p(re-decide) = sigmoid(-stay / scale) at every keep reading of his seats, whoever decided it, all run (`--keep-teach`, live `KEEP_TEACH`); its own layers only (state, memory, stay value detached) | the design: "taught toward the stay value's sign all run"; the soft form (scale = the labels' running mean size, measured, not set) | a hard sign |
| 5 | **The quiet layer reads only** the stay value, the age and the 5 change signals; it is not summed with any learned output (rule 11 does not apply; recorded) | "in quiet, with nothing new, there is nothing to react to" | |
| 6 | **The change signals for the target** (KEEP_SIG): an item target there or back in time by what he knows; an item target; the belief of the enemy's place moved since the choice; a pain sound within the tick; the believed stack fallen since the choice. Made at the head's tick (every 8 frames), held between | taken out of the instruction's code (2.1a) for the target, as the design says | |
| 7 | **League networks play quiet with the lock** (they carry no stay value and no quiet layer) | a league file is a frozen opponent; the stay value lives beside the network, not in it | the learner's stay value on the league's states |
| 8 | Steps open **only on the owner's word**: `steps.json` in the run folder; the ramp then opens the share slowly; nothing holds or steps back on its own | rule 6, decision 7 | |

## What is where

| Part | Files | Off = |
|---|---|---|
| KEEP_ZONE: the keep choice split by zone (zone layer in contact and arrived; quiet: the quiet layer where its coin says, else the lock rule); `keep_live` 1 / 2; `stats["keep3"]` | `sim/duel_env.py` (`intend()`, the block at "2.1 (owner 2026-11-14"), `sim/duel_env_ffa.py` regenerated | bit-identical (test 1) |
| KEEP_SIG: the target's change signals, `keep_feat()` 7 + 5 | `sim/duel_env.py` `keep_sig()`, `_ks_belief()` | bit-identical |
| The quiet layer (`keepq`, `keepq_g`) | `sim/head2.py`; `tools/keep_init.py add --quiet 1` | not in a file without it |
| The stay value | `sim/stay.py`; the trainer's `--stay`, `--stay-lr`, `--stay-hid` (live `STAY_W`); the checkpoint's top-level `stay` (with its Adam) | absent |
| The keep forks | `sim/branch.py` `start_keep`, `keep_labels`, `log_keep`; the trainer's `--branch-keep`, `--branch-zone-p` (live `BRANCH_ZONE_P`), `<run>/stay_forks.jsonl` | the branches as before |
| The keep lesson | the trainer's `--keep-teach` (live `KEEP_TEACH`), `keep_teach()` | off |
| The quiet layer in PPO, its share | the trainer's `--keepq-g` (live `KEEPQ_G`), `keep_lp()` (both layers), the optimizer group `keepq` | |
| Records | `metrics.jsonl`: `stay` (labels, by kind: new_wins, mean, sd, the held-out sign; `held_out`), `keep.zone` (the guards), `keep.teach`, `keep.quiet`, `branch.keep` | |
| M1's report | `tools/run/m1_report.py <run>` | |
| The simulator's tests | `tools/run/keep21_simtest.py all --ref <the main checkout>` | |
| Run files, ramp | `docs/runs/2.1/2.1b/` (`make_files.py`, `start.ps1`, `start_live.py`, `ramp_21b.py`, `smoke.py`, `CARD.md`) | |
| The checks' and the servers' player | `sim/test_suite.py`, `sim/export_duel.py`, `plugins/netpass.py`, `plugins/duelbot.py`; `tools/run/keep21_playtest.py` | |

## Tests (logs in `tests/`; all on the CPU at idle on cores 14-17, beside 2.0e's training)

| Test | Result |
|---|---|
| `keep21_simtest.py` 1: the switches off against the main checkout's simulator (2.0e's code), 2.0e's switches, the same seed and actions | **identical to the bit** over 3,000 frames (inputs, pay, ends, target, keep_live, keep_feat) |
| 2: duel_env against the generated duel_env_ffa, switches on | identical |
| 3: the signals' ranges; keep_live 1 only in contact or arrived, 2 only in quiet; `keep3` adds up | PASS |
| 4: no quiet coin: the quiet layer decides nothing; every quiet change forced or let by the lock rule | PASS (0 unexplained) |
| 5: with the coin: every quiet change on a frame with a reading is forced, the lock's or the quiet layer's | PASS (0 unexplained). Target changes on a frame with no reading at all (outside `intend()`) exist in 2.0e's own simulator too: 18 of 1,867 changes in both trees (1b), not 2.1's doing; left as they are |
| `keep_init.py same` on 2.0e's update 10 (zero start, quiet layer) | share 0: **identical to the bit** (0 of 3,200 actions); at share 1 every band near 0.5 a reading |
| Trainer smokes (`smoke.py`, scratch runs `scratch_21b_*`) | 19 of 19 PASS: the optimizer's groups `keep` and `keepq`, forks made and held, the stay value scored held out then taught, the long window across rollouts, the keep lesson, the save's `stay` entry; with both shares open (a debugging run): both layers decide in their zones, learn, KL 0.002 to 0.004 |
| `live_test.py` | ALL PASSED: the new live names applied by update 4; `KEEPQ_G 1.5`, `KEEP_ZONE 2` refused by `live_accept` |
| `keep21_playtest.py` (the checks' and the server's player) | the server's forward pass = the checks' to the bit over 800 frames; shares 0 = the source file to the bit |

**Not built:** build 7 (the map sense into the head's inputs: owner, 2.2's first step). **Not tried:** a real server with the new
parts (an image build and a local server, before B's play test).

**First sign for M1** (the debugging smokes, a handful of forks): two branches that drew the SAME target differed by up to 1.09 in dv over
1.6 s: a single fork is mostly noise, as 2.1a found. The stay value will need many forks; M1's report gives the count per kind.

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
| **The 2.1f build** | **done and tested on `b21f` (commits `f183db2`, `520dbb6`), not merged**: see "The build's report" below. Not yet done: the diff review, the merge, a full-size update on the graphics card |
| Processes | **none of any run is alive** (2.1e's watcher finished its update-50 check at 15:57 and ended itself: 106-94 = 53.0% against 2.1d's end) |

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

**Landed 11-16 15:40. Built and tested on `b21f`, commits `f183db2` (the build) and `520dbb6` (a ramp log line, the test record). Not merged,
not pushed. The worktree is clean: it may be worked in now.** I have read the report but not reviewed the diff line by line: that review
is step 1 of "What is left".

### What is there

| | |
|---|---|
| The outlook | `sim/outlook.py` (new), `head2.out.*`: the head's state (detached) → 128 → 128 → for each label kind 17 numbers (one a goal) + 1 goal-blind number. Last layer at zero. Buffers `out_g` (0), `out_pick` (0) |
| The five kinds, in this order | `seg`, `ret`, `all8`, `win8`, `win5`. `seg` is index 0 and plays by default |
| The rows | every keep reading of his seats on a held trip while alive, with the goal he is on after that reading; each marked decision or stay, trial or own, in control or not. About 240,000 rows an update at full size |
| `seg` | the head's whole pay from the reading to the first later reading at which his goal differs or a new draw fell, at the head's gamma, plus gamma^k x the head's stored value there; a death or a round's end cuts it with no bootstrap; past the rollout's end the head's own last bootstrap |
| `ret` | the head value's own target (`head2_.gae` with `--head2-lam`) |
| `all8`, `win8`, `win5` | fixed windows (320, 320, 200 frames) over the whole pay or the win stream. **Kept only when the window fits in the rollout**, so `all8` and `win8` have rows from about the first 64 frames of each rollout only: far fewer rows than `seg` and `ret` |
| The win stream | what `--head2-pay win` would pay (`win_raw x HW_G`). Under `--outlook 1` the trainer sets `OUT_WINRAW=1` and each worker sends it in its step reply; what the head is paid is unchanged |
| The term | `out_g` x clip(the picked kind's outlook less its mean over the goals, ±5), in the label's standardised units, rounded to half precision at its source; added after the pull, stored as played (`b_out`), in every learner pass and the proof. Computed only when a strength above 0 plays. Rule 11's decay on its last layer |
| The lesson | smooth L1, its own Adam (`out_opt`), 2 epochs, minibatch 4,096, on the learner's copy. Labels standardised by a running mean and spread kept in the checkpoint (`out_stats`) |
| Skill, read before each lesson | per kind, overall and at decision and stay readings, in and out of control, trial and own rows: R² of the goal's number, R² of the goal-blind number, the gain, the correlation; the share of readings where the outlook's top goal is his goal; rows per goal; the spread between goals; the size of the term; the share of his choices the term would change at 0.5, 1, 2, 4, 8 |
| Trial trips | live `OUT_TRIAL` (0 to 0.2, default 0): at a new draw the goal is drawn evenly among the targets his map has (**"nothing" among them**), then the trip runs as any held trip, his mid-trip changes included. Every frame of a trial trip is left out of all target lessons; its rows teach the outlook |
| The proof's worst frame | in `rec["pull"]` as `worst` and `worst_half`: the step, the seat's marks on that frame and the one before (reset, new draw, change, plan refresh, slow-half tick), the played and learnt log-probabilities, the target, the largest pull and outlook values, a sequence edge or not, the 99.9th percentile, the counts over 0.003 and 0.01. The ramp prints it only above 0.003 |
| Live names | `OUT_G` (0 to 20), `OUT_PICK` (0 to 4, whole numbers), `OUT_TRIAL` |
| Readers and tools | `sim/test_suite.py` (`set_out_g`, `set_out_pick`), `plugins/netpass.py` (`NET_OUT_G`, `NET_OUT_PICK`), `sim/export_duel.py`; `tools/out_init.py` (`add`, `widen-league --like`, `same`), `tools/run/out_playtest.py` |
| The run folder (worktree) | `docs/runs/2.1/2.1f/`: `make_files.py`, `start_live.py`, `ramp_21f.py`, `start.ps1`, `restart.ps1`, `smoke.py`, `live_test.py`, `train.cmd` (720 minutes and 1,000 updates as placeholders; `start.ps1` rebuilds it with the owner's length), `aim2_env.cmd`. The ramp keeps saves at updates 30 and 70 and writes `OUT_G` only from `watch/out_mark.json` |

### Decisions the build took where the brief was silent

1. `--outlook` needs `--pull 1` (the term rides in the pull's place and its proof).
2. The term is not shut after a death: the outlook reads the cleared state there, and those rows are in the lesson.
3. Windowed labels are dropped when the window passes the rollout's end, even if a death comes first (keeping them would lean them negative).
4. A trial goal can be any target his map has, "nothing" included.
5. Skill is scored with the label statistics from before the rollout; the lesson uses the updated ones.

### Tests (CPU, check cores, one at a time; all passed)

| Test | Result |
|---|---|
| `out_init add`, then `same` | 0 of 48,000 actions differ, at strength 0 and at 1.0 |
| The trainer with the outlook at strength 0 (its last layer made non-zero) against the same save without it | 0 of 43,008 actions differ; log-probabilities, values and pay identical |
| The smoke, with trial trips at 0.1 and strength 1.0, and with trial trips at 0 | ALL PASSED both; the proof 0.00001; the term changed 1.3 to 3.1% of his readings; 0 trial frames left in a target lesson; the resume works |
| The live test; `live_accept` on the start file and every file the ramp can write (marks 0.5, 2, 20) | ALL PASSED; out-of-range values refused |
| The ramp's mark file | absent: nothing written; a mark ramps; a smaller mark later is held; a mark of 25 refused with a flag |
| The export and the server's pass against the checks' player | 0 of 1,200 frames differ; at strength 0 identical to the source |
| The labels by brute force; the trial draw | ALL PASSED |
| `check_settings` against 2.1d's command; the two scripts | PASS with the allowed arguments; 0 parser errors |

In the smokes a `seg` segment was 3 to 6 readings at the median (0.6 to 1.2 s), 12 to 25 at the 90th percentile; 5 to 30% of rows ran
past the rollout's end. Skill after three updates is noise, as expected.

### Not done, uncertain

- **No full-size update on the graphics card.** New stored data is estimated at about 300 MB (the term as played 132 MB on the card, the
  rows about 135 MB on the host); the lesson's time over 240,000 rows twice was not measured. The run's first two updates are that test.
- The record and the ramp's lines were seen on smoke-sized data only.
- `all8` and `win8` have few rows (decision 3), so their skill will be noisier than `seg`'s and `ret`'s; the 8-second question the owner
  raised is best read on `seg` and `ret` first.
- "The term is not shut after a death" (decision 2) and "nothing" as a trial goal (decision 4) are worth a second look in the diff review.
- Scratch folders `data\sim_runs\scratch_21f_*` are left in place (nothing is deleted).

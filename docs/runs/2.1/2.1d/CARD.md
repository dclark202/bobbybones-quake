# 2.1d: the pull (his plan weighs on every choice)

**Status (2026-11-15): the owner's go given** ("Yes that looks fine"; "Get the build ready for 2.1d"; it runs until 08:00 tomorrow; 2.1c may
be ended early for it). Built on branch `b21d` by Opus agents; merged into main once 2.1c has stopped.

## The owner's page

| | |
|---|---|
| Started from | **2.1c's end** (the save of update 50: its network, its optimizer, its slow plan after 50 updates of silent learning) |
| The one new thing | **The pull**: the slow plan's odds, times a strength, are added to his goal scores. A goal his plan favours needs less to stay; a rival needs a real spike to win |
| The owner's words | He makes a decision, sticks to that decision, unless something appears that really calls for a change |
| What it is not | No network decides "should I switch". No timer, no margin we set. A change of goal still falls out of one comparison of totals |
| The pull's strength (`PULL_G`) | 0 to update 10, **0 → 1.0** over updates 10 to 30, **1.0 → 2.0** over 30 to 50, then held |
| Which horizon pulls | The plan's **2-second** odds (every pull number measured in 2.1c used it; both horizons predicted equally well) |
| The held draw (`HELD_G`) | Stays at **0.25** (2.1c's end) to update 50, then **→ 1.0 by update 110**. At 1 the lock decides nothing |
| The head's credit | 12 s (`--head2-lam` 0.998), as 2.1c: its forecast error settled (0.45 → 0.27) and the checks stayed level |
| Pay | As 2.1c (damage taken at 0.9 of damage dealt) |
| Length | **Until 08:00 on 11-16** (the trainer's time limit ends it) |
| Control | 2.1c's end in the league and in every check; every fourth check against 2.0e's end |

## What happens every 200 ms

1. Each of the 17 goals gets a total: its fresh score, plus its fixed dice for this trip (2.1c), plus the plan's boost (new).
2. His goal is whichever total is highest.
3. The dice are rolled once at a trip's start and kept, also after a change mid-trip; rolled anew only when the trip ends.
4. The plan is read when he sets a goal and once a second, and held between. It usually favours the goal he is on; when it expects him
   to move on (the mega nearly reached, the red next) it favours the next goal, and the pull then helps him leave.
5. Two learned sources of stickiness sit inside that one sum: his scores see the goal he holds and its age (2.1c, playing); the plan's
   boost (this run).

## Why this run: what 2.1c showed (the trial of 11-15, 50 updates)

| | |
|---|---|
| The held draw alone did not teach him to hold a goal | With the share constant at 0.25 (updates 33 to 43) his mid-trip changes on held trips stayed at 43 to 48 a seat-minute |
| More than half of those changes are dithering | 55 to 58% were taken back within 2 seconds |
| He did not collapse | Checks against 2.0e's end: 52.0% at update 10 (all lock), 48.0% at update 30; frags steady at 2.0 a match-minute; targets reached 23% → 20% |
| The plan is steadier than his scores | It predicts his next 2 seconds with an error of 0.47 against 1.2 for his fast scores of the moment |
| What the pull would have removed (first order) | 18% of mid-trip changes at strength 0.5, 28% at 1.0, 40% at 2.0, stable all afternoon |

More trips than on the lock is **not** a fault (owner 11-15: "he's supposed to have more trips per minute than on the lock. that's kind
of the point"). The measures of harm are the share of changes taken straight back, targets reached, and the checks.

## The schedule (`ramp_21d.py`; never holds or steps back on its own)

| Updates | `PULL_G` | `HELD_G` | What it shows |
|---|---|---|---|
| 0 to 10 | 0 | 0.25 | The start plays as 2.1c's end; the first ten updates are the trial of the build at full size |
| 10 to 30 | 0 → 1.0 | 0.25 | The share of changes taken back, and targets reached, as the pull opens |
| 30 to 50 | 1.0 → 2.0 | 0.25 | The same at the stronger pull; a check at each level |
| 50 to 110 | 2.0 | 0.25 → 1.0 | The lock's share shrinks to nothing under the pull |
| 110 to the end | 2.0 | 1.0 | No lock anywhere |

Checks every 20 updates, 200 games. Marks with their optimizers at 10, 30, 50, 80, 110 and the end. Every check reported; one under 40%
flagged at once. Logged every update: the held draw's, the plan's and the pull's records, trips, targets reached, the ledger.

## What was built (branch `b21d`)

| Part | What | Where |
|---|---|---|
| The plan inside the head | 2.1c's side module becomes layers of the head, so the checks, the servers and every league file read it by the existing paths; the strength and the horizon are in the file | `sim/head2.py` (`head2.plan.*`, `pull_g`, `pull_h`, `plan_odds`, `pull_vec` and their numpy twins); `tools/plan_init.py add / widen-league / same` |
| The pull in play | Added to his goal scores right after the network's pass, before the draw, the held draw's comparison and every log-probability; on lock trips too; each league network with its own file's plan and pull | `sim/train_duel_rnn.py` (`--pull`, `--pull-g`, `--pull-h`, `--pull-floor`, live `PULL_G`, range 0 to 5) |
| The pull in the learner | The pull as played is stored per frame and added wherever the learner re-forms his goal's distribution: the main PPO pass, the decoupled reference pass, the KL readouts, the head's own term | `seq_pass` (one place all passes go through) and the head's term |
| The proof of the wiring | Every update: the learner's log-probability of his goal against the played one, before any weight moves (`pull_first_err`); over 0.001 is a MAJOR PROBLEM line | the record `pull` |
| The plan's lesson | On the learner's copy, its own Adam, from his odds **before** the pull; the main optimizer never steps it | |
| Rule 11 | The plan's last layer gets the head's decay from update 0; the pull's size as added is recorded beside the other parts; over 40 flagged | |
| The checks' player, the plugin, the export | The plan and the pull exactly as the trainer plays them | `sim/test_suite.py`, `plugins/netpass.py`, `sim/export_duel.py` |
| The run's files | `make_files.py`, `start_live.py`, `ramp_21d.py`, `start.ps1`, `smoke.py`, `live_test.py`; `tools/run/pull_playtest.py` | `docs/runs/2.1/2.1d/` |

## Decisions taken for the build

| # | Decision | Why |
|---|---|---|
| 1 | The plan moves inside the head | Once it plays, every program that plays him must compute it the same way |
| 2 | The pull is added before anything reads the scores, on lock trips too | One definition: a new roll is exactly a draw from "scores + plan" |
| 3 | The plan keeps learning from his fast odds before the pull | Learning from the pulled choice would feed on itself and freeze |
| 4 | **A floor of 0.01 on the plan's odds** inside the pull (`--pull-floor`) | Without one, a goal the plan gives almost nothing could never be picked. A hand-set safety bound, not a behaviour; the owner's to change |
| 5 | The plan's odds reset to even at a death | A new life is a new plan |
| 6 | The item rule's lesson is refused with the pull | It is 0 in this line; it is not wired through the pull |
| 7 | A failure in the plan's readouts or lesson turns those off and the run goes on; a failure in the plan's odds once it plays stops the run | In shadow it could not hurt play; now it is part of play |
| 8 | The long-term control is 2.0e's end | The owner: no checks against 1.7a; 2.0e's end is the last network that played wholly on the lock |

## Tests (CPU, scratch folders, nothing deleted)

| Test | Result |
|---|---|
| The start answers as 2.1c's save with the pull at 0 (`plan_init same`, real rows) | 0 of 48,000 actions differ |
| The plugin against the checks' player with the pull at 1.0 (actions, keep column, memory, the plan's held odds) | 0 differences over 2,400 frames, Blood Run and Aerowalk |
| Pull 0 against the source file in the real simulator | 0 frames differ |
| The wiring's proof in the trainer (`pull_first_err`) | 5e-6 to 1.1e-5 with the pull at 1.0 and at 0 |
| The smoke at pull 1.0 and at pull 0; a resume from its save | ALL PASSED; "from the checkpoint" |
| `PULL_G` live: 0 at update 1, written to 1.0, played by the last update; 6.0 refused before the first rollout | ALL PASSED |
| `live_accept` on the ramp's files, `check_settings` against 2.1c's command and save | PASS |
| In the real simulator, same seeds, 2.1c's update-10 plan: mid-trip changes a seat-minute on held trips, pull 0 → 1.0 | Blood Run 41.0 → 34.8; Aerowalk 54.4 → 41.3 |
| My rerun of the proofs on 2.1c's update-40 save (a plan with 40 updates of learning) | `plan_init same`: 0 of 48,000 actions differ. Plugin against the checks' player at pull 1.0: 0 differences on both maps. Pull 0 against the source: 0 frames differ |
| The same rerun, in the real simulator with the game replayed: mid-trip changes a seat-minute on held trips, pull 0 → 1.0 | **Blood Run 46.3 → 30.4 (34% fewer); Aerowalk 68.8 → 43.9 (36% fewer)**. Better than the first-order readout's 28%; lock trips for comparison: 4 to 7 |

**An existing trait the build found, not changed:** the learner re-reads its inputs at half precision (`--obs-half`, in 1.6a's and 2.0e's
commands too), so its recomputed log-probabilities differ from the played ones by about 0.005. Every recent run has had it. The proof
above is measured on full-precision inputs; the half-precision number is recorded beside it. Left alone for this run; a question for later.

## Red team

| Assumed or hand-built | Weakness | Measured alternative / check |
|---|---|---|
| The pull is enough | 2.1c's readout says it removes a quarter to two fifths of his mid-trip changes, not most. The plan is mostly a smoothed copy of his fast scores: half his changes go toward what it favours | Tonight tests whether he does better once he plays and learns under it. If not: a slow memory of its own for the plan (FTW's form) |
| A stronger pull is better | A strong pull toward a wrong plan freezes him on bad goals | Targets reached falls first; two steps with a check at each; marks to go back to |
| The readout "what the pull would have done" | First order: the game is not replayed, so it cannot show what he learns under the pull | The real share of changes taken back, every update |
| The floor 0.01 | A hand-set number | Recorded; the owner's to change |
| The plan learned on a player three quarters on the lock | Its "next seconds" come from that player | Its labels are his fast odds, not the held goal; its skill is re-read as the held share rises |
| The build has never run at full size | The smokes are 16 seats; the run is 10,080 on the graphics card | The first update is the trial: `pull_first_err`, the plan's and the pull's records, the memory used, read at once |
| Half-precision inputs in the learner | A standing staleness of about 0.005 in every log-probability | Recorded each update (`first_err_half`) |

Pathology check of the ledger: at the run's first updates.

## Research check (rule 14)

| # | Question | Answer |
|---|---|---|
| 1 | The game | No mechanic and no simulator value is touched |
| 2 | What wins | Commitment to an item and its timing (DUEL_STRATEGY.md, "Principles distilled"); "overcommitting throws games" is why the commitment stays breakable: any spike in his scores still breaks it |
| 3 | The player's view | The plan reads only the head's own memory; no truth input |
| 4 | In and out of control | No pay changes. A plan that favours staying could become camping (v0.4.3): the panel's camping and spawn-camping measures in every check |
| 5 | Self-play equilibrium | Two flickering copies lose items to neither; the punishing opponents are 2.1c's end, 2.0e's end and the anchors, who commit |
| 6 | Bot precedent | BOTS.md section 2 (FTW: a slow prior the fast choice is pulled toward) and 13.2 (ranked idea 2): this is that idea, with the pull added to the scores at play instead of a KL term in the loss, because the held draw compares totals. Its named risk there: "a strong KL can freeze a bad prior". Compatible with rule 13 per the notes: the prior is learned by the head itself, not an old network. **Difference from FTW**: our plan is a layer on the head's memory, not a slow recurrent core of its own |
| 7 | Rule 12 | No pro number anywhere in it |

## The start (11-15 17:08) and its first updates

Started 17:08 from 2.1c's update-50 save, 884 minutes (to about 07:52). Both settings checks pass; the start answers as 2.1c's end with
the pull at 0 (0 of 48,000 actions differ); the live file applied before the first rollout; the held share played is 0.25.

**The proof's bar was wrong for the graphics card.** Updates 1 and 2 logged "THE PULL'S PROOF FAILED: first_err 0.00142 / 0.00106 over
0.001". The pull's strength was 0 and the pull as added was exactly zero on those updates, so nothing of the pull could be mis-wired: at
full size with mixed precision the measurement's own floor is about 0.001 to 0.0015 (the CPU tests gave 0.00001, and the bar was set
from them). A real wiring fault would scale with the pull, whose added values reach about 4.6 at strength 1: errors far above 0.01. The
ramp's bar is now 0.01, with a plain FLAG above 0.003, and the ramp restarted with `--resume`. **What to read from update 10 on: the
proof staying at this floor as the pull opens.** The half-precision readout beside it (`first_err_half`) is 0.08 to 0.12 at its worst
frame at full size: the existing `--obs-half` trait, larger on the card than in the CPU tests; a question for after this run.

Updates 1 and 2 otherwise: frags 1.25 and 1.5 a match-minute (the fresh-start dip, as 2.1c's 1.1 and 1.4), the graphics card at 12.5 GB
held, an update in about 5.3 minutes.

## Before the go

| | |
|---|---|
| ☑ | The owner's go and settings (strength to 2.0 in two steps, the 2-second horizon, the held share to 1 by update 110, credit 12 s, until 08:00) |
| ☐ | 2.1c stopped at its update-50 save, its end kept as `keep/policy_end_21c.pt` + `opt_end_21c.pt` |
| ☐ | The ramp set to this schedule (an Opus agent), my rerun of the proofs read |
| ☐ | 2.1c's work committed on main, `b21d` merged (the owner's yes, 11-15) |
| ☐ | `start.ps1`, its row in `docs/RUNS.md`, the first update read |

# 2.1: the trainer's three new parts, as built on branch `b21` (2026-11-11)

*Built in the worktree `BobbyBones-21` while 1.8a trains; **nothing of it has run in a simulator or on the card**. Only the new modules'
unit tests ran (made-up arrays, CPU, seconds). The design: [DESIGN.md](DESIGN.md) (gate 0: "the map sense and the appraisals learn; the
frozen moments run; nothing reads them"). Details the design left open are marked **(decided here)** for the owner's review.*

## What exists

| Part | File | Flag (default off) | Live dial | In `metrics.jsonl` | In the checkpoint |
|---|---|---|---|---|---|
| Map sense (S8) | `sim/mapsense.py` | `--map-sense <weight>`; `--map-sense-lr 1e-3`, `-hid 64`, `-every 5`, `-pull 1.0`, `-init <file>` | `MAP_SENSE_W` (a factor on its lesson), `MAP_SENSE_PULL` | `map_sense` | top-level `map_sense` (layout, weights) |
| Appraisals (A1 to A6) | `sim/appraise.py` | `--appraise <weight>`; `--appraise-lr 5e-4`, `-hid 256` | `APPRAISE_W` | `appraise` | top-level `appraise` |
| Frozen-moment rounds | `sim/branch.py` | `--branch 1` and / or `--branch-p <share>`; `--branch-top 5`, `-rand 3`, `-hold 40`, `-win 320`, `-log 1` | `BRANCH_P` (0 .. 1, in `LIVE_RANGE`) | `branch` | none (a plan lives one rollout) |
| The map sense's start from the pros' fit | `tools/run/mapsense_init.py` (`rows` in the system Python, `fit` in the Anaconda one) | | | | `data/sim_runs/space/mapsense_start.pt` |
| Unit tests | `tools/run/test_21_parts.py` | | | | |

All three follow the shadow win value's pattern: a module of its own outside the policy, its own Adam (cold at a start), its own
random streams (made under `fork_rng`, seeds 4061 to 4065), learnt after the PPO epochs, saved as a top-level entry and never in
`model`. So the export, the checks, the league's files and the anchors do not see them, and the main optimizer, the policy and the PPO
loop are untouched. `tools/run/live_accept.py` reads the trainer's own list, so the four live names are accepted by it (tested).

**Rule 11 does not apply yet:** nothing here is summed into a choice. It will when the head's choice reads the appraisals (gate 3).

## Map sense

| | |
|---|---|
| Reads | the 15 seeds of a pair of places (`mapsense.feats`, copied to the letter from `tools/run/seed_calib.py`), scaled, the two weapons as one-hots: 31 numbers |
| Gives | damage dealt and taken in the next 5 s (200 frames), each for four weapon classes in his hand: rockets, rail, lightning, other. 8 numbers, / 100 |
| Shared part | 31 → 64 → 64 → 8, the same on every map; starts at zero, or from the pros' fit with `--map-sense-init` |
| Correction | one row of 8 a walking point of each map (`data/maps/space_<map>.npz`), added for HIS place; starts at zero; after every step of its optimizer multiplied by 1 − rate × `MAP_SENSE_PULL` |
| The enemy's place and weapon in the seeds | the brain's belief (the token's believed place and hand at each tick), kept in a small buffer during the rollout. No believed place = no sample |
| The label | the truth: the damage of the next 200 steps from the simulator's books, cut at the round's end or his death (that step still counts) |
| A sample | every fifth tick of the brain (1 s) with a second behind it and 5 s ahead inside the rollout (frames 79, 119, 159 of 384), both alive, the believed enemy within 1,500 units |
| A map without a table | skipped and named in the start's print and in `map_sense.maps_without_table`; never an error |
| Record | samples by class; R² of dealt, taken and the exchange before the step, with the corrections and for the shared part alone; the corrections' mean and largest size |

**(decided here)**
- The fourth class is "any other weapon", not DESIGN's "passing through": how far he moved in the last second is one of the seeds, so
  a passage is read by setting it, not by a class of its own.
- The label is also cut at his own death (the pros' fit cut at the end of a life's stretch).
- Only the head for the weapon class in his hand gets a label; the other three learn from the frames he holds those weapons.
- The pull's default 1.0 with the rate 1e-3 takes a correction to a third in about a thousand steps of its optimizer if nothing
  holds it up. It is a live number and 0 is allowed (owner, 11-10).

## Appraisals

| | |
|---|---|
| Reads | the brain's state (256), the hands' memory (512), the head's state (256), and the candidate: verb (8, all zero for now), target (17), weapon (9 and "none"), map sense at its place (8, zero for now) |
| Gives | dealt, taken (/ 100); the enemy dies, he dies, he takes the mega or red (chances); dV |
| dV | the head's own value as an n-step advantage over the 320 frames: the discounted pay + γ³²⁰ × the head's value then − its value now, γ 0.9998; cut at a round's end with no bootstrap (RUNDOWN decision 1, option a) |
| The judge beside it | the win judge's shadow pay summed over the same window is written to each branch's line (`judge`), so option b can be compared. It needs `--win-value` (`WIN_SHADOW=1`); without it the field is empty |
| Learns from | the frozen moments only (decision 2: no pro games) |
| Record | rows; for each output its mean and, before the step, R² (regressions) or the Brier score beside the best constant's |

**(decided here)** Each source is also an example: his own target at the hold's end with what free play brought. It is on-policy and
costs nothing; the forced branches are the off-policy ones.

## Frozen-moment rounds

1. Before a rollout (`pre_rollout`, main thread, no rollout playing), with `BRANCH_P` above 0: in each simulator a share `BRANCH_P`
   of the self-play matches become destinations, 8 for each source. A source is a self-play match with both seats alive in a game.
2. The candidates of a source: his 5 best targets by his own scores now and 3 drawn from the rest ("none" never; an item the map
   lacks never).
3. The simulator copies the source's moment into each destination (`_moment_take`, `_moment_set`) and sets `force_intent` on the
   destination's even seat. The trainer copies the same seats' rows of everything it carries: the last inputs and truth, the hands'
   memories of both networks, the brain's state and its gathering sums, the token, both heads' states, the win value's stream, the
   keep choice's numbers, COMBAT's candidates.
4. For 40 frames the forced seat's target is the candidate; the simulator's worker reports that seat's intention and keep choice as
   not read and its rule label as none, so the PPO terms skip them. Then the force is lifted and he plays on.
5. After the rollout the outcomes over frames 0 to 319 are read from its buffers for every destination and source, taught to the
   appraisals, and written to `<run>/branches.jsonl`.

A destination whose target at the hold's end is not the forced one (a holding place the map does not have) is dropped.

**Where it departs from the mapping report, and why**

| Report | As built | Why |
|---|---|---|
| The worker replies with the destinations' rows of inputs, truth, legs' inputs and keep numbers | the worker replies only "done"; the trainer copies its own source rows onto the destination rows | a copied match's rows are its source's by construction; one path, no new reply format |
| `--branch-p` alone | `--branch 1` beside it | a new thing starts shut and is opened live: the rounds must be able to be on at share 0 |
| Candidates from the hands' rows plus the head's part | (1 − mix) × the hands' + (mix + add) × the head's target scores × valid | the same sum `mix_in` plays with, without its per-frame bias |

**The report's risks**

| Risk | Handling |
|---|---|
| The simulator's hindsight books a seat-and-frame (fight odds, "in control") are not copied | the worker shuts those books' queries for the destination seats (`fo_okq`, `ctl_q_ok`), so the frames before the copy give no label. Checked on a stand-in only |
| WIN_PAY's per-seat arrays | they are copied by the simulator if their first dimension is the seats' or the matches'. **Not verified**: to be read off a real copy |
| COMBAT's candidates | `CARRY["ox"]` is among the copied rows |

**Known and left as they are**
- A destination's own game is replaced without a round's end. The rollout before it bootstrapped from the value of the state that
  was there, which is a valid truncation. The simulator's game counters see two matches finish "the same" game.
- `force_intent` is itself a per-seat array, so a mid-game start's copy at a round's end inside the 40 frames could move a force to
  another match. 1.8a has `MID_START_P=0`.
- A source must be alive in a game; whether the truth's `trk_on` column is exactly "in a whole game" is not checked.

## Tested (`tools/run/test_21_parts.py`, 59 checks, all passed; made-up arrays, CPU)

| | |
|---|---|
| Map sense | a missing table is skipped; the sample frames; a new one forecasts 0 and draws nothing from the global stream; 200 steps summed, cut at a round's end and at his death with that step counted; no sample without a believed place; the class is the weapon in his own hand; rate 0 scores without learning; the lesson lowers its error (323 → 10); the pull multiplies the corrections by exactly 1 − rate × pull |
| Appraisals | the candidate's layout; a new one forecasts 0, a half, 0; the lesson lowers the labelled outputs' error (51 → 0.5); an output without a label is not taught |
| Frozen moments | the plan's shares, sources never destinations, share 0 sends nothing; the candidates; every simulator gets its plan; the trainer's seats; the copy of rows for tensors, arrays, histories and objects with every other seat untouched; the worker's copy, force, shut books, masks and release on a stand-in simulator; damage, frag, item, target, dV's arithmetic, the cut, the judge's sum; the rows for the appraisals; the log; the record |
| Off and live | the four flags default to off; the modules are made only under their flags; the four live names are read by the trainer's own reader; a share above 1 is refused |

## NOT verified (needs the simulator and the card, after 1.8)

1. **Identity with the three parts off**: a fixed-seed trainer run before and after this branch. By reading: off, nothing is made
   but three unused generators; the worker's reply holds the same values; the rollout's result gains two empty entries.
2. The worker's copy on a real simulator: that `_moment_take` / `_moment_set` between two rollouts leave it consistent, with the
   cleaned list's module (`duel_env_ffa18` / `21`) too.
3. The trainer's copied rows against the simulator's: after a copy, the destination's first inputs must equal its source's.
4. That the forced target holds for 40 frames under the keep choice, and the share of forced targets that do.
5. A rollout and an update with all three on at full size: the time they add, the card's memory, `--overlap`.
6. The map sense on real tables (`data/maps/space_<map>.npz` are not in this worktree) and the distilled start's R² against the fit.
7. Whether the map sense's and the appraisals' skill rises over updates (tests 6 and 7 of DESIGN.md).


---

# The second build (2026-11-11 evening): the head's choice of an instruction, its lesson, the branches on instructions

*Owner, 2026-11-11: "the point of 2.1 is to train the action decisions and incorporate them into the model. So they need to be actively
trained and the build for the run needs to make sure that everything is good to go." Built the same day in the same worktree. **Nothing
of it has run in a simulator or on the card.** The unit tests (`tools/run/test_21_parts.py`, now 107 checks, made-up arrays, CPU) all
pass. The simulator's side: [SIM_PARTS.md](SIM_PARTS.md). The run's draft card: [CARD.md](CARD.md). Where a section above says "six
outputs" or "targets only", this section replaces it.*

## What exists now

| Part | Where | Flag (default off) | Live dial | In `metrics.jsonl` | In the checkpoint |
|---|---|---|---|---|---|
| The scorer over the simulator's candidate rows, the weapon's scores, the quiet logit | `sim/head2.py` (`make_ins`, `ins_scores`, `ins_wscores`, `ins_qlogit`) | `--ins 1`; `--ins-lr`, `--ins-seats 2048`, `--ins-warm 20000`; `--ins-quiet 1` | `INS_G` (0 to 1) | `ins` | top-level `ins` (layout, model, branches seen, the warm-up, the row "none") |
| The head's input part "ins" (the row he is on, its forecast then and now, the six change signals, how long, on one) | `sim/head2.py` (`PARTS`, `ins_u`, `feats(ins=)`) | comes with the layout (`tools/head21_init.py add`) | | | `head2` (the layout), `head2.inp.weight` widened |
| The lesson: toward the appraisals' order; the game's pay on the choice | `sim/head2.py` `ins_learn`; the trainer after the PPO epochs | `--ins-teach 1`, `--ins-pg 0`, `--ins-temp 0.05`, `--ins-ent 0` | `INS_TEACH`, `H2_INS_PG` (0 to 1), `INS_TEMP` (0.01 to 100), `INS_ENT` (0 to 1) | `ins`: rows kept, taught, entropy, KL to the appraisals' order, how often the best row agrees, verbs, weapons, rows by block, quiet by verb, changes a second, the chosen rows' forecast against what the head's value says they brought | |
| The branches force INSTRUCTIONS (a row, the weapon the head scores best for it, quiet in a share) | `sim/branch.py` (`start(wbest=, quiet_p=)`, `worker_start`, `rows_ins`, `rows_q`) | `--branch-ins 1` (with `--ins`), `--branch-quiet-p 0.25` | `BRANCH_P` as before | `branch` | |
| The long window (the score and the clock) | `sim/branch.py` (`long_new`, `long_step`, `long_busy`); the appraisals' seventh output `dv_long` | `--branch-long 1`, `--branch-long-p 0.25`, `--branch-long-secs 30`, `--ins-long-w 0.5`, `--ins-long-warm 5000` | `BRANCH_LONG_P` (0 to 1), `INS_LONG_W` (0 to 1) | `branch`: `long_reading`, `long_learnt`, `long_seen`; `ins.long_w` | (the records being read are not saved: a restart drops them) |
| The appraisals read a row's numbers and the quiet bit | `sim/appraise.py` (`layout(xf=, quiet=)`, `cand(x=, quiet=)`, `cand_rows`, `forecast_rows`, numpy the same) | with `--appraise` | | | `appraise` |
| The checks' player and loop give instructions | `sim/test_suite.py` (`Policy.act(ix=)`, `ins_due`, `ins_pick`, `set_ins_g`), `tools/duel_eval.py` | by the file | | | |
| The export carries the scorer and the appraisals | `sim/export_duel.py` (`ins`, `ins.*`, `appraise`, `appraise.*`) | by the file | | | |
| The start at zero effect | `tools/head21_init.py add / widen-league / same` | | | | |

Everything is off by default. With `--ins 0` nothing of it is made, sent, drawn or kept; the simulator's worker masks nothing unless a
seat is under an instruction. Rule 12: no pro rate, share or choice is read anywhere here.

## How a tick goes (the trainer's rollout; the checks' player does the same sums in numpy)

1. On the frame the brain and the head tick, the trainer asks every simulator for the next reading's candidates (`("instr", {want})`
   before the step; the answer is the last field of the step's reply): the rows `X`, which may be chosen, the weapons he can use, the
   change signals, who is in a drill, the row he is on, who is forced.
2. On the next frame (the reading; it is the keep choice's reading too): the appraisals forecast every offered row (no weapon named:
   "this row with the weapon he would choose"); the scorer scores the rows on the head's state, the row's numbers and its forecast; a
   row is drawn, then its weapon, then quiet or not, from the scorer's own stream.
3. A seat takes the new row only if its coin is the head's (`INS_G`), it is not in a drill or a forced branch, and it is under none, or
   its instruction is done or failed, or **the keep choice of this reading says re-decide** (the keep choice gates a change of
   instruction exactly as it gates a change of target).
4. The picks go to the simulators (`("instr", {c, w, q, who})`, then the step). `instr_pick` is called only for the seats whose
   instruction changes; a seat whose coin is off and that is under one is cleared.
5. At the head's next tick its input carries the instruction he is on (the part "ins").

## Decided here, for the owner's review

- **The scorer is a module beside the network with its own Adam, learnt after the PPO epochs; it reads the head's state as a number.**
  The alternative is the way 1.7's order was built: inside the PPO loop, its gradient into the head's memory. That is about thirty
  touch points in the trainer and is where 1.7c's false start came from (a wiring bug in exactly that code), and none of it can be run
  today. As built, the head's memory learns of his instructions through its inputs (the part "ins"), by its value and its target choice.
  **A question for the owner** (below).
- **One learned output decides** (rule 11 does not apply): the appraisals' forecast is an input of the scorer and the target of its
  lesson, never a logit added to its scores.
- **The keep choice reads the change signals through the head's state** (which carries them from the part "ins"), not through new
  inputs of its own: no new weight in the network, so the optimizer resumes as it is. Its own terms are masked for a seat in a drill
  or a forced branch.
- **A seat under an instruction did not play the target its network drew**: the simulator's worker reports that intention as "not
  read" (no PPO term, no rule's label). So as `INS_G` rises, the old target choice (the hands' rows and the head's target scores)
  stops being trained on those seats and is superseded by the instruction.
- **The coin**: a seat's coin is drawn at a round's end and, for a seat under no instruction, anew at every rollout's start at the
  share in force, so a raised `INS_G` acts within one rollout and never cuts an instruction short. (The checks' player redraws it at
  every reading of a seat under none.)
- **League seats are under no instruction** (the league's older networks have no scorer; a snapshot of this run saves the network
  alone). The checks' player does give instructions, for both seats if both files have the part.
- **The lesson needs the appraisals warm**: until they have learnt from `--ins-warm` branches on instructions their forecasts are
  read as zeros and nothing is taught toward them. The scorer's lesson runs on every kept reading whether the seat played the choice
  or not, so the scorer can be taught before `INS_G` opens.
- **The weapon**: the appraisals forecast the chosen row under each weapon he can use; the weapon's lesson is toward that order. Each
  forced branch teaches twice: with its weapon, and with none named.
- **Quiet**: at the start the logit is −6 (asked about once in 400 picks: "at zero" as a probability, not as a logit, because a logit
  of 0 would have him walk half the time). A quarter of the forced branches are forced quiet so the appraisals see both.
- **The long window**: the seats of a long branch (and their enemies) are left alone by later plans until it is read; a record is
  the discounted pay from the copy on, cut at a round's end with no bootstrap, else the head's value at the window's end, less its
  value at the copy. The lesson's target is `(1 − INS_LONG_W) × dV8 + INS_LONG_W × dV30`, the long part only once `--ins-long-warm`
  long branches have been learnt from. **The 8 s dV already ends on the head's own two-minute value, which reads the score and the
  clock; the long window is a check on that value's reading, played out, not the only place they enter.**
- **Kept readings**: 2,048 of his seats a rollout (`--ins-seats`), every reading; about 0.4 GB on the host at 41 rows of 37 numbers.

## Questions for the owner

1. **CLOSED (the owner, 2026-11-11: inside; "The fourth build" at the end).** ~~The scorer beside the network (built) or inside the PPO
   loop. My recommendation: as built for the first run.~~
2. **League seats without instructions.** As built his older selves in the league play under none. If the run's own snapshots should
   give instructions, the snapshot has to carry the scorer and the appraisals. My recommendation: leave it for the first run; the
   control is judged in the checks, where both seats do.
3. **The share of the game's pay on the choice** (`H2_INS_PG`, built, default 0): RUNDOWN decision 3 said "start at today's". Today's
   head is paid on its target; the instruction's own share starts at 0 and the frozen moments' lesson teaches it. Open it in the card's
   last gate, or from the start?

## NOT built (asked for on 2026-11-11 evening) -- BUILT SINCE: see "The third build" at the end; this table is kept as it was written

| Piece | What is missing | Where it would go |
|---|---|---|
| 1. "Does the enemy know where I am" | the brain's readout (label: the truth column `en_knows`, with `KNOWN_TRUTH=1`), its answer among the head's inputs and written into the rows' column `INS_FILL["known"]` | a readout as the fight odds' (`sim/fightodds.py`, the trainer's FOD blocks: its ring, batch, lesson after the PPO epochs, record); filled into `Xi_` at the reading before the scorer and the appraisals read it |
| 2. How sure the brain is | the entropy of its zone odds and the spread of its places ahead, among the head's inputs and written into `INS_FILL["unsure"]` | computed from `net.trackz` / `net.ahead` at the tick; the same fill |
| 4. Where he respawns | the brain's readout over the map's spawn points (labels `en_spawn`, `en_dead_t`, with `SPAWN_TRUTH=1`), written into `INS_FILL["spawn_odds"]` for the spawn rows (`env.ins_cspawn`, which the worker does not return yet) | as piece 1; the worker's reply (`sim/branch.py worker_feat`) gets `ins_cspawn` |

Until they are built those three columns of a row read zero for the scorer and the appraisals. The new verb "check" and the spawn rows
are ordinary rows and are scored, forced in branches and logged (by block) as the others. Piece 5 (this opponent's habits) is not in 2.1.

- **`plugins/netpass.py` does not give instructions.** The export carries the weights; on a game server he plays under none (the
  head's part "ins" reads zeros). What a plugin must do when it is built: every frame `env._ins_clock()` then `env._ins_step()`; at
  the head's tick `env.instr_feat()` (and `instr_state()`, `ins_cur`), the sums of `Policy.act`'s reading (`sim/test_suite.py`),
  then `env.instr_pick(c, w, who, q)`; the seat's held numbers kept beside its memories.
- **The map sense at a row's place** is not among the scorer's or the appraisals' inputs (the eight numbers stay zero).
- **The run's `train.cmd`, `start.ps1`, ramp and watcher lines**: made from the reference command after 1.8a ends.

## NOT verified (needs the simulator and the card)

1. Fixed-seed identity of the trainer with `--ins 0` against the trainer before this build.
2. A rollout with `--ins 1`: the "instr" messages and the reply's last field through 30 simulators; the time a reading adds (the
   appraisals' forecast of every offered row of every seat: about 400,000 rows a reading at 1.8a's size); the card's memory.
3. `tools/head21_init.py add` then `same`: 0 actions differ at share 0. The optimizer's resume with the widened `head2.inp.weight`
   (`--opt-small-items`, the file's `head2_inp_map`).
4. That a forced instruction holds for the 40 frames, that the keep choice's re-decide is what changes an instruction, that the
   masked seats are out of the PPO terms.
5. The long window across rollouts on real buffers, with `--overlap 1` (a plan for the next rollout is made before this rollout's
   long branches are recorded: `long_busy` reads the pending plans for that).
6. The checks' player against the trainer on the same rows (it is the same arithmetic in numpy; the unit tests compare the scorer and
   the appraisals, not a whole game).

---

# The third build (2026-11-11 night): the brain's two new questions, how sure it is, the map sense at a row's place, the plugin

*The owner, 2026-11-11: pieces 1, 2 and 4 "are a definite include into the build". Built the same night in the same worktree.
**Nothing of it has run in a simulator or on the card.** The unit tests (`tools/run/test_21_parts.py`, now 143 checks, made-up arrays,
CPU) all pass. Where the second build's section says "NOT built" for pieces 1, 2 and 4, the map sense at a row's place, or the
plugin giving instructions, this section replaces it.*

## What exists now

| Part | Where | Flag (default off) | Live dial | In `metrics.jsonl` | In the checkpoint |
|---|---|---|---|---|---|
| "Does the enemy know where I am" (piece 1): a readout on the brain's state and the hands' memory -> two chances (knows, heard) | `sim/knownodds.py` | `--known-odds <weight>`; `--known-lr 1e-3`, `-hid 64`, `-every 6`; the simulator's `KNOWN_TRUTH=1` | `KNOWN_W` (0 to 100) | `known`: frames, how often the truth says yes, Brier beside a half's and the best constant's, skill, AUC, for both outputs | top-level `known` (layout, weights) |
| "Where does he respawn" (piece 4): a readout -> odds over the map's spawn points (padded to `SPAWN_MAX`, masked to the map's count) | `sim/spawnodds.py` | `--spawn-odds <weight>`; `--spawn-lr 1e-3`, `-hid 128`; `SPAWN_TRUTH=1` with `RESPAWN_QL` | `SPAWN_W` (0 to 100) | `spawn`: samples, cross-entropy beside the uniform guess's, top-1 and top-3 beside the uniform guess's and the rule's prior (the far half from where he stands), how often the truth is in that half | top-level `spawn` |
| How sure the brain is (piece 2): the entropy of its zone odds over its largest (0 to 1); the mean distance between its places 1, 2, 4 s ahead (thousands of units, at most 2). No lesson: read off its own readouts | `sim/head2.py np_brain_unsure` | comes with `--ins` | | `ins.brain_q` (their means on his seats, with the known chance) | |
| The brain's answers written into the candidates' rows: `INS_FILL["known"]` and `["unsure"]` in every offered row, `["spawn_odds"]` in the spawn rows (each row's point: the worker's `ins_cspawn`) | the trainer's `ins_prep`; `sim/head2.py np_ins_fill`, `np_ins_prep` | with `--ins` | | | the columns' numbers under `ins.fill` |
| Three numbers among the head's inputs, for every seat whether under an instruction or not: the known chance minus 0.5, the two "unsure" numbers | `sim/head2.py` (`INS_BQ`, the end of the part "ins"; `InsState.bq`) | a head made with `tools/head21_init.py add --bq 1` (the default) | | | `head2.ins.bq` |
| The map sense at each row's place: its eight numbers (dealt and taken x rockets, rail, lightning, other; standing there; against the brain's believed place and weapon of the enemy) after the row's own numbers; the scorer and the appraisals read rows of 37 + 8 | `sim/mapsense.py rows_at`, `np_forward`; `sim/head2.py` (`INS_MS`, the layout's `ms`, `fx`) | `--ins-ms 1` with `--map-sense`; a head made with `--ms 1` (the default) | | `ins.brain_q.map_sense_rows` | `head2.ins.ms`; the rows' width `xf` = the simulator's `fx` + 8 |
| The worker's reply: five more fields (each row's spawn point, its place, whether it has one, the weapon in his hand, the map's spawn points' count); once: the map's spawn points | `sim/branch.py worker_feat`, `worker_spawns`; the trainer's worker command `"spawns"` | | | | |
| The reading in numpy, ONE definition for the checks' player and the plugin | `sim/head2.py np_ins_prep`, `np_ins_read`, `np_ins_held_u`, `ins_held_width` | | | | |
| The plugin's pass gives instructions | `plugins/netpass.py` (`load`: `P["_ins"]`; `ins_due(P)`; `step(..., ix=, mapname=)`; `P["_ins_pick"]`) | by the file; `NET_INS_G` overrides the share | | | the export carries `known`, `spawn`, `map_sense` (where the rows read it) and `ins.fill` |

All of it is off by default: with `--known-odds 0`, `--spawn-odds 0`, `--ins-ms 0` nothing is made, no simulator is asked for its
spawn points, and a head made without `bq` / `ms` reads rows as the simulator gives them. The two readouts follow the shadow win
value's pattern (their own module beside the network, their own Adam, cold at a start, top-level in the checkpoint, learnt after
the PPO epochs); they can learn with `--ins` off (nothing reads them then). Rule 11 does not apply: nothing here is a logit.
Rule 12: no pro number is read.

## How each is taught and read

**Known.** A sample: every sixth tick of the head (`--known-every`), every seat whose enemy is alive; the input is that tick's kept
head input (its parts "brain" and "hands": the same numbers the readout reads in play, at half precision); the label is the truth
of the same frame (`en_knows`, `en_heard`). About 80,000 samples a rollout at 1.8a's size. Scored before it is learnt from.

**Spawn.** A sample: every tick of the head at which the enemy is dead, up to `RESPAWN_QL_FRAMES + 16` frames before the row that
shows him back, with no round's end between; the label is the spawn point's number (`en_spawn`). **(decided here)** every such tick,
not one frame: the head decides at each of them, and the odds should move as he moves. The record's prior is the simulator's own
rule read by someone who knows only where he stands: uniform over the points farther than the median.

**The fill and the reading.** At a reading (the frame after the head's tick) the trainer takes the simulators' rows as they came,
asks the two readouts and the brain's own zone odds and places ahead on THAT frame's memories, writes the answers in, appends the
map sense, and only then scores. The checks' player and the plugin do the same sums in numpy at the same frame
(`np_ins_prep`). The frozen moments' candidates are filled the same way before a rollout. The rows kept for the lesson and for the
appraisals are the filled ones.

## Decided here, for the owner's review

- **The readouts sit beside the network** (as the scorer), not among the brain's own readouts in the policy: no change to the
  policy, its optimizer or the league's files. The price: the league's older selves and a file exported before them have none.
- **The head reads the known chance minus 0.5** (0 = no idea), as it reads the fight odds.
- **The map sense at a row's place is "standing there"** (the seed "moved in the last second" at 0), with the weapon in his hand
  now, not the row's weapon: the row's weapon is the head's second choice, made after the row.
- **A row without a place, a seat without a believed place of the enemy, a map without a table: zeros.**
- **The known lesson samples every seat**, the league's too (the head's input is kept for all of them): more data, the same network.
- **On a game server the map sense's table** is looked for at `<QLBOT_ROOT or />/data/maps/space_<map>.npz`; not there: zeros.
- **The instruction's held numbers on a server** are kept beside the seats' arrays (`P["_ist"]`), not inside them: the packed layout
  of a seat's memory is unchanged; `netpass.clear` clears them with the seat.

## What `plugins/duelbot.py` must do (NOT built: the file is not edited)

Every frame, after `env.intend(...)`:
1. `env._ins_clock()` then `env._ins_step()`.

At the frame a reading is due (`netpass.ins_due(P)` is true before the call):
2. `ix = branch.worker_feat(env)` (`sim/branch.py`; its rows for the bot's seat), then
   `netpass.step(P, A, obs, h, rng, ..., ix=tuple(v[rows] for v in ix), mapname=<the map>)`;
3. after it, `pk = P["_ins_pick"]`; if not None: `rows, c, w, who, q = pk` and, with full-size arrays for the simulator's seats,
   `env.instr_pick(c_all, w_all, who_all, q_all)`.

At a death, a new game or a new opponent: `netpass.clear(P, h, rows)` as today (it clears the held instruction too), and the
simulator's own `_fresh` ends the instruction. No drills on a server (`DRILL_INS_P` stays 0). The image must hold
`sim/knownodds.py`, `sim/spawnodds.py`, `sim/mapsense.py`, `sim/appraise.py`, `sim/branch.py` (all numpy at the top) and
`sim/order_maps/`.

## The review pass: mismatches found and fixed

| # | Found | Fixed |
|---|---|---|
| 1 | The checks' player unpacked the worker's reply as exactly seven fields; with the five new ones it would have failed at the first reading | it now reads the fields by position (`ixs_[:7]` and on) through the shared reading |
| 2 | The trainer read the reply's fields with a literal count of seven | `range(len(...))` |
| 3 | Two readings of the same sums existed (the checks' player's inline code; none in the plugin) | one definition (`np_ins_read`), called by both |
| 4 | The rows' width was the simulator's `INS_F` in three places of the trainer (the appraisals' layout, the scorer's check, the kept readings) | the layout's own `xf` (= the simulator's + the map sense's eight where the head was made with it) |
| 5 | The scorer's checkpoint entry did not say which columns are filled (a checks' player or a plugin could not know) | `ins.fill`, written by `head21_init.py add` and by the trainer's save; the export carries it |
| 6 | `sim/knownodds.py` and `sim/spawnodds.py` as first written imported torch at the top (a game server has none) | numpy alone at the top; a unit test reads the five modules the plugin imports |
| 7 | The fill was first placed where the reply arrives (the tick's frame), the checks' player can only fill at the reading (one frame later, another hands' memory) | both fill at the reading |
| 8 | `tools/head21_init.py widen-league` widened a league head without the brain's three numbers and the map sense's eight: its input would have been narrower than the learner's | it takes the same `--ms`, `--bq` (and `--quiet`) as `add` |

Read and found consistent (not changed): the step tuple and the reply's last field between the worker and the trainer; the drill's
and the forced seats' masks (`ins_drill`, `force_instr`, `worker_mask`); the picks' format `(rows, c, w, who, q)` in
`tools/duel_eval.py`; the list's widths (no literal 845 / 837 / 691 in the code: all read from the lists); `tools/inputs21.py`'s
verb count.

## Open questions for the owner

| | Question | As built | Recommendation |
|---|---|---|---|
| a | **CLOSED: moved inside on the owner's word, 2026-11-11 (see "The fourth build" at the end).** ~~The scorer beside the network or inside it.~~ As built THEN its lesson's gradient did not reach the head's memory: the head "reads all of it and picks" only in that its STATE is read by the scorer. Moving it inside means: the scorer's layers as parameters of `pol.head2` (zero-initialised by `head21_init.py`, a new optimizer group, `--opt-small-items`' carry-over, `load_net` filling them for older files); the rows, forecasts, masks and picks kept for ALL of his seats and frames (`b_x`-like buffers on the card: 41 x 45 numbers a seat a tick); the head re-run over the sequence in the learning step with the rows (`head2_.seq`), its row, weapon and quiet log-probabilities recomputed inside the PPO minibatch loop, the ratio and the clipped surrogate on the head's advantage, the teach term's cross-entropy there too, the head's gradients held aside as its target's are (`H2GR_`), an entropy term, a KL read; the league's snapshots then carry it; the checks' player, the export and the plugin read it from `model` instead of `ins` | beside (fork T's and mine) | as built for the first run. It is the same change that carried 1.7c's false start, about thirty places, and none can be run today. Decide after a real rollout shows the rest works |
| b | **League seats under no instruction** | his older selves in the league play under none; the checks' player gives instructions for both seats | leave for the first run |
| c | **The game's pay on the choice** (`H2_INS_PG`) | built, default 0; the frozen moments' lesson teaches the choice | open it as the card's last gate |
| d | **Any death of the enemy opens the spawn rows** (the owner asked for his own frag) | the simulator's `ins_dead_t` starts at any death of the enemy | the simulator can tell cheaply: the kill loop in `step()` has the victim and the killer of each death (`events`: `killer`, `victim`); `_ins_clock` would start the clock only where the killer is the seat. One condition; not changed here (the simulator's interface is fork S2's). In a duel the difference is a suicide or lava, which he usually sees or hears |

## NOT verified (needs the simulator or the card), in the order to run

| # | What | Command |
|---|---|---|
| 1 | The unit tests in the repo's tree | `set CUDA_VISIBLE_DEVICES=-1 & set OMP_NUM_THREADS=1 & <anaconda python> tools/run/test_21_parts.py` (ALL PASSED, 143) |
| 2 | The simulator's cases, the labels among them (`en_knows`, `en_heard`, `en_spawn`, `en_dead_t` present and sane) | `<anaconda python> docs/runs/2.1/tests_instr.py` |
| 3 | The start: list 21, then the head's part, each at zero effect | `python tools/inputs21.py convert <1.8a end> <a.pt>`; `python tools/inputs21.py same <1.8a end> <a.pt> --sample <obs.npy>`; `python tools/head21_init.py add <a.pt> <b.pt>`; `python tools/head21_init.py same <a.pt> <b.pt> --sample <obs.npy>` |
| 4 | The trainer with every new flag off against the trainer before the build, a fixed seed: the same to the bit | the run's `tests.py ident` (to be written from 1.8a's) |
| 5 | Ten small updates with `--known-odds 1 --spawn-odds 1` alone (`KNOWN_TRUTH=1 SPAWN_TRUTH=1`): the `"spawns"` message through every simulator, the batches' sizes, `known` and `spawn` in `metrics.jsonl`, the prior's top-1 near the rule's | a scratch run |
| 6 | Ten small updates with everything on (`--ins 1 --ins-ms 1 --map-sense 1 --appraise 1 --branch 1 ...`): the reply's twelve fields, the fill's time a reading (the map sense's table lookups for every offered row of every seat are the unmeasured cost), `ins.brain_q` | a scratch run |
| 7 | The checks' player against the trainer on a network with the parts: a game of `tools/duel_eval.py` with `ins_g` set, both seats | `tools/duel_eval.py ... ` on the scratch run's save |
| 8 | The export and the plugin's pass against the checks' player | `python sim/export_duel.py ...`; `tools/netpass_check.py` (it does not give `ix=` yet: to extend) |
| 9 | Whether the brain's zone odds as the token keeps them are what the trainer's `trackz` gives at the same tick (the "unsure" number reads the token's) | read off step 6's record against a direct read |

---

# The fourth build (2026-11-11 night): the instruction's choice moved INSIDE the head

*The owner, 2026-11-11, on open question (a): "yeah of course that should be moved inside. the point is that the head learns how to
make decisions. I don't see any other way that a 'head' makes sense. It has to learn from its decisions what works and doesn't work".
**Question (a) is closed: moved inside on the owner's word, 2026-11-11.** Where the second and third builds' sections say the scorer
is "a module beside the network with its own Adam", "learnt after the PPO epochs", "reads the head's state as a number", or that the
checkpoint's entry `ins` holds its weights, this section replaces them. **Nothing of it has run in a simulator or on the card.** The
unit tests (`tools/run/test_21_parts.py`, now 162 checks, made-up arrays, CPU) all pass.*

## What changed

| | Before (the second and third builds) | Now |
|---|---|---|
| Where the scorer's weights are | a module beside the network, `ins.model` at the top of a checkpoint | **layers of the head itself**: `head2.ins_is`, `ins_ix`, `ins_ia`, `ins_iv` (the rows), `ins_ws`, `ins_wx`, `ins_wv` (the weapon), `ins_qv` (quiet), the share `head2.ins_g`: in the network's own weights (`model`), so the league's snapshots, the export and the checks carry them as any other layer |
| Its optimizer | its own Adam (`--ins-lr`), cold at every start | the main optimizer, a group **`ins`** at the head's rate (`--head2-lr-scale`), saved with `opt.pt` by name; a saved optimizer without it (1.8's end) loads into the groups before it and Adam starts these fresh. `--ins-lr` is read and not used |
| Where it learns | after the PPO epochs, on the head's state stored as a number | **inside the PPO epochs, in the head's own loss**: the head is re-run over the rollout (`head2_.seq`, as for his target) and each kept reading is scored again from the re-run state |
| What its lesson reaches | the scorer alone | the scorer **and, through the state, the head's memory (its GRU) and its input layer** (the part "ins": the row he is on, its forecast then and now, the change signals, the brain's three numbers) |
| The gradient's handling | its own clip (1.0) | clipped and held aside with the head's other gradients (0.5, `H2GR_`), put back for the step, exactly as his target's |
| The checkpoint's entry `ins` | layout, weights, counters | **no weights**: the branches seen, the warm-up, the row "none", the filled columns. The layout is `head2.ins` |

## The three terms (sim/head2.py `ins_loss`, added to the head's loss where his target's term is)

| Term | On which readings | Weight (live) |
|---|---|---|
| The lesson: cross-entropy of the rows toward softmax(the appraisals' mixed dV / `INS_TEMP`) over the offered rows; the same for the weapon of the drawn row; quiet toward the chance the two forecasts (asked, not asked) give | every kept reading of a live seat that is not a drill's nor a forced one's, once the appraisals are warm | `INS_TEACH` |
| The game's pay: the PPO-clipped surrogate of the drawn row, weapon and quiet with the head's own advantage at the reading's frame (normalised over his own readings in the piece; the second clip as his target's: a bad choice's ratio counts at most 3) | his own readings only (the coin on, he re-decided, not a drill, not forced) | `H2_INS_PG` |
| The rows' entropy bonus | the same seats as the lesson | `INS_ENT` |

The appraisals' forecasts and the map sense are INPUTS (numbers kept with the reading); they, the brain's readouts and the map sense
keep their own modules and optimizers beside the network. **Rule 11 does not apply: ONE learned output decides** (the head's row
scores; nothing is added to its logits).

## One definition of the masked log-probabilities (1.7c's lesson)

1.7c's false start was PPO's reference log-probability computed without a mask the play used. Here:
- `sim/head2.py` `ins_row_logp`, `ins_wq_logp`, `ins_joint_logp` are the ONLY torch definition. The rollout draws from them on the
  network that plays (`net.head2`) and stores the drawn choice's log-probability; the learning step (`ins_piece`, `ins_loss`) and the
  decoupled pass call the same functions on the re-run head.
- The forecasts are rounded to half precision BEFORE the rollout scores them, so the numbers kept for the lesson are the numbers
  played (the rows already are).
- The checks' player and the plugin use the numpy twin (`np_ins_row_logp`, `np_ins_wq_logp`) through the one shared reading
  (`np_ins_read`); a unit test proves numpy = torch.
- **The unit test that guards it** (`test_inside`): a made-up rollout (the head ticking every 8 frames, a round's end in the middle)
  draws from the definition; the head is then re-run with `seq` and every kept reading's log-probability recomputed: the largest
  difference is 0.0, for rows, weapon and quiet, with masked rows, a seat offered the row "none" alone, a seat offered nothing, a
  seat without a usable weapon, a drill's seat and a forced one. In the run: `ins.kl.played_to_before` every update (near 0 without
  `--overlap`; with it, the staleness of the network that played).

## Decoupled PPO (`--overlap 1`, 1.8a's setting)

The rollout is played by a copy one update behind. As for his target, the pay's term clips around **the learner's own
log-probability before any step of the update** (`INS_PX`, filled in the proximal pass with the same functions), weighted by the
capped importance weight exp(that - as played); without `--overlap` the reference is the stored one.

## Kept readings: what is stored, and its size

Per rollout, for `--ins-seats` of his seats (2,048) at every reading (48 a rollout of 384 frames), on the host at half precision:
the rows as read with the filled columns and the map sense (41 x 45), their forecasts (41 x 7), the offered rows, the usable
weapons, the drawn row's numbers, the drawn row / weapon / quiet, their log-probability, own, teachable, the weapon's forecasts.
**About 0.43 GB on the host at 1.8a's size** (the rows 0.36 GB, the forecasts 0.06 GB). The head's state is no longer kept (it is
re-run). **On the card, a piece of the learning step** (2,048 seats / 8 minibatches = 256 seats x 48 readings x 41 rows): the rows
as float32 0.18 GB, the scorer's hidden layer (128 wide) and its gradient about 0.8 GB. *(decided here)* That is unmeasured on a
card that long sequences already fill: `--ins-seats` is the dial (1,024 halves it).

## What the record adds (`metrics.jsonl` `ins`)

`terms` (the three terms' values, a piece's mean in the first epoch), `kl.played_to_before` and `kl.played_to_after` (log p as
played less log p now on his own readings: before any step, and after the update), `head_grad` (the norm of the gradient on the
head's memory's own weights from the instruction's terms and from his target's term, once an update), `scorer` (the sizes of the
last layers, the quiet logit's bias). What it had stays (rows, own, taught, entropy, the distance to the appraisals' order, picks by
verb / weapon / block, quiet, changes a second, the forecast against what it brought, `brain_q`).

## Decided here, for the owner's review

- **The scorer's layers are in a group of their own (`ins`), not in the head's group**: an optimizer saved before them then loads
  unchanged (the head's group keeps its size), and the group is added by name on a later resume.
- **A file without the layers (a league file not widened, an anchor) gets the network's own layers and share 0 on load**; league
  seats stay under no instruction (question b, unchanged). `head21_init.py widen-league` writes the layers too.
- **The counters of the record are taken in the first epoch, piece by piece** (the weights move a little within it), as the keep
  choice's are.
- **At the start the head's memory gets no gradient from the instruction**: the scorer's last layers are zero, so nothing flows
  through them until the lesson has moved them (the same as his target's layer at zero in 1.3b).
- **With the head's layout carrying the part and `--ins 0`** the layers exist and are in the optimizer's group, with no gradient
  (Adam leaves them); nothing reads them. A head without the part has no such layer, parameter or group: the trainer is as before.

## Could not be moved, or left as it was

- Nothing asked for was left outside. The appraisals, the map sense and the two brain readouts stay beside the network on purpose.
- The keep choice still reads the change signals through the head's state (now trained by the instruction's terms too).
- `plugins/duelbot.py` is still not edited.

## NOT verified (needs the simulator or the card), in the order to run (this replaces the third build's list where they overlap)

| # | What | Command |
|---|---|---|
| 1 | The unit tests in the repo's tree | `set CUDA_VISIBLE_DEVICES=-1 & set OMP_NUM_THREADS=1 & <anaconda python> tools/run/test_21_parts.py` (ALL PASSED, 162) |
| 2 | The simulator's cases | `<anaconda python> docs/runs/2.1/tests_instr.py` |
| 3 | The start at zero effect, now with the scorer's layers in the network's weights | `python tools/inputs21.py convert <1.8a end> <a.pt>`; `python tools/inputs21.py same <1.8a end> <a.pt> --sample <obs.npy>`; `python tools/head21_init.py add <a.pt> <b.pt>`; `python tools/head21_init.py same <a.pt> <b.pt> --sample <obs.npy>` (0 actions differ) |
| 4 | The trainer at a fixed seed with every new flag off, on a file WITHOUT the part, against the trainer before the build: to the bit | the run's `tests.py ident` (to be written from 1.8a's) |
| 5 | A resume of the start with `--opt-small-items`: the saved optimizer loads, `head2.inp.weight` carried over, the group `ins` added after the load ("names" in the next `opt.pt` end with `ins`), and a second resume adds it by name | two scratch resumes of ten small updates; read the trainer's "optimizer:" lines and `opt.pt`'s names |
| 6 | Ten small updates with `--ins 1` and `INS_TEACH` 1, `H2_INS_PG` 0.5, `INS_ENT` 0.01: `ins.kl.played_to_before` near 0 without `--overlap` (the wiring's proof on real buffers), the three terms finite, `head_grad.ins` above 0 once the last layers have moved, the card's memory with 2,048 seats | a scratch run; then the same with `--overlap 1` (the proximal reference) |
| 7 | With `INS_TEACH`, `H2_INS_PG` and `INS_ENT` at 0 and `--ins 1`: the head's learning is as without the instruction's terms (no gradient from them) | a scratch run at a fixed seed against the same with `--ins 0` on the same file (the play differs only by the draws' own stream: compare the first update's head terms) |
| 8 | The checks' player against the trainer on a network with the part; the export and the plugin's pass | `tools/duel_eval.py` with both seats; `python sim/export_duel.py ...`; `tools/netpass_check.py` (to extend with `ix=`) |

# The fifth build (2026-11-11 night): the finish time, the wake, the pattern's moments, and the head paid by the win chance alone

*The owner, 2026-11-11 night: the lightning gun "is for cleanup"; "land a disruption rocket or perhaps multiple; oh the enemy is
weak (i heard them scream e.g.); let me switch to lg and finish them off"; and: "the strategy head should be paid for improving the
things that lead it to think it has a higher win chance ... it should absolutely not be paid for doing damage. The hands get paid
for doing that"; "the head must be paid by making decisions that improve its readout of the game". The simulator's side:
[SIM_PARTS.md](SIM_PARTS.md), "Third pass".*

## Which pay each network learns from (every update's record: `metrics.jsonl` `pay_of`)

| Network | Learns from | Flag |
|---|---|---|
| The hands | the pay table (frags and deaths, items by the point, damage) + the win part, as today. Their dial of the win part: the simulator's live `WIN_ADD` (0 to 100; not new) | unchanged |
| The head's side of 2.1: its value of the instruction (`head2.ins_vv`), the frozen moments' dv over 8 s and over the long window (so the appraisals' dv and the lesson's target softmax(dV / `INS_TEMP`)), the advantage of the pay on his instruction choices (`H2_INS_PG`), the forecast's calibration | **the win chance only**: the judge's change in win chance of each frame (`win_raw`, the simulator's `HEAD_PAY_TRUTH=1`) times a fixed gain. No entry of the pay table: frags, stacks and weapons reach it through the judge's readout | `--ins-pay-win 1` (default 0: as before), `--ins-pay-gain` (0: `WIN_ADD` at the start, 1 if that is 0) |
| The head's OLDER parts (1.7's): its value `head2.v`, and from its advantage the target scores, the keep choice, its weapon scores and its fire push | **today: his whole pay, the damage in it** (1.8a's command has no `--head2-pay`: the default `all`) | `--head2-pay win` moves them to the same stream ❓ the owner's call; default unchanged |

What the code said before this build (the answer to "does the flat damage pay enter the head's value?": yes):

    sim/train_duel_rnn.py   B_HR = R.get("b_hr") if R.get("b_hr") is not None else b_rew
                            ADV_H, RET_H = head2_.gae(B_HR, B_VH, b_done, float(H2L["gamma"]), ...)
                            vl2_ = (0.5 * (vh_ - RET_H[:, chunk]).pow(2) * wgt).sum() / wsum
                            b_hr = torch.zeros(T, N, device=dev) if a.head2_pay != "all" else None
    (the branches' dv)      kw_ = dict(aux=R["b_aux"], done=R["b_done"], hr=R.get("b_hr") if R.get("b_hr") is not None else R["b_rew"], vh=R.get("b_vh"), ...)
    sim/branch.py           out["dv"] = g + np.where(out["cut"], 0.0, float(gamma) ** W * _np(vh[W][...])) - _np(vh[0][...])

`b_rew` is his whole pay of the frame; `--head2-pay combat_win` (never used since b1.2a) is frags, deaths and damage plus the win
part. So the head's value, its advantage, and through them the frozen moments' dv, the appraisals and the instruction's lesson all
counted the flat damage pay.

**How it is built.** The simulator gives `win_raw` as a label (never an input, never paid). The rollout keeps it at full precision
(`b_hw`, times the gain) and the head's value of it at every frame (`b_vw`, from `head2.ins_vv`: a layer on the state the older
value reads, at zero at the start, made after every older layer, in the optimizer's group `ins`). The learning step makes
`ADV_W, RET_W = gae(b_hw, b_vw)` at the head's own discount, teaches `ins_vv` toward `RET_W` at the older value's weight, and gives
`ADV_W` to the instruction's terms; the branches' outcomes and the long window read `b_hw` and `b_vw`.

**The readout** (`metrics.jsonl` `branch.best_by_win_vs_full`): over a rollout's moments with two branches or more, how often the
best option by the win-chance dv is another than the best by the whole pay's dv (moments, differ, share).

## The pattern's moments in the frozen moments (`--branch-wpn-p`, live `BRANCH_WPN_P`, 0 to 1, default 0)

With the branches on instructions: that share of a rollout's sources is taken among the matches whose even seat is at a pattern's
moment now (the simulator's `instr_pattern()`: just after a chunk hit or a pain sound; a fight's start with both stacks high; the
worker's reply carries it as its thirteenth field). Their branches keep ONE row (the row he is on if it is an instruction the map
still offers, else the row the head scores best; never "none", which asks for no weapon) and differ only in the weapon: each weapon
he owns with ammunition, up to the branches a moment has, in a random order; quiet is never forced in them. The appraisals learn
them as every instruction branch (the row with its weapon, and with none named), so the weapon's lesson of the scorer (the chosen
row under each weapon) is taught where the pattern happens. The record: `branch.wpn` (how many, of which kind, and by weapon what
each brought: dealt less taken, dv). At 0 the plan's draws are as before, to the draw.

## The wake in the readers

`sim/head2.py` `ins_end(sg)`: done, failed, or a wake. The trainer's rollout (`end_i`), the checks' player and the plugin's pass
(`np_ins_read`) all call it; the head's inputs carry the eight change signals (`INS_SIG` 6 -> 8), so the keep choice reads the
wake and the fallen stack through the head's state as well. A head made before this build would have six: none exists.

## The table's way (`FIN_RATE`)

`tools/run/fin_rate.py measure <records>` -> the table and the line `FIN_RATE=...`; the records are `tools/run/cypher_measure.py
sim`'s, which now keep each frame's damage by the weapon that did it (the simulator's own books), the weapon a shot left and the
weapon asked for. In the run's command it is a play variable: the trainer's saves and the export carry it in `env_vars`, so the
checks and a server read the same table. It is a live name too (`live.json`: the string).
**NOT built: the re-measurement at every check.** The tool is there; the watcher does not call it and nothing writes the new table
into `live.json` on its own. Until that is built the table is the one measured before the start.

## The readout "does he fire the weapon he was asked to"

`tools/run/goal_readout.py`, the line `asked`: of his shots under an instruction that asks for a weapon, the share fired with
another, by the weapon asked for (needs records made with this build).

## Decided here, for the owner's review

- **The head's stream is the judge's change in win chance of each frame, a game's end in it** (what `WIN_ADD` multiplies for the
  hands), times a gain fixed at the start. So turning the hands' `WIN_ADD` up or down does not change what the head learns from.
- **The head's older parts are left as they are** (flag `--head2-pay win`): they are what 1.8a trains, and moving them is a change
  of its own with its own identity check.
- **The scale of dV changes with the stream** (no table entries in it): `INS_TEMP` (the lesson's temperature) was set for the
  whole pay's dV and must be looked at again on the first updates' record (`ins`' spread of dv, the target's entropy).
- **A weapon-only moment needs two usable weapons and an instruction row**; otherwise the source is an ordinary moment.
- **Outside whole games and late rounds `win_raw` is 0** (as the win part of the pay is): frozen moments there bring the head
  nothing to learn from. The share of such frames in 1.8a's mix is what the record's `pay_of.win_abs` will show.

## Tested (2026-11-11 night; CPU only, cores 14 to 17, below-normal priority, at most two processes; 1.8a trained throughout)

| What | Result |
|---|---|
| `tools/run/test_21_parts.py` (made-up arrays) | **ALL PASSED, 216 checks** (162 before; 54 new: the table and its string, the finish time's arithmetic and that nothing of it reads the enemy's true stack or place, the wake's one rule and a kept seat drawing anew on it, the weapon-only plan and the plan's draws unchanged at a share of 0, the worker's thirteenth field, `ins_vv` at zero and made last, another pay table moving no head-side advantage, return or dv while the whole-pay ones move, the readout, the trainer's wiring by its lines, the live names accepted and refused, the measuring tool and the `asked` readout on a made-up record) |
| `python -m py_compile` on every changed file | clean |
| `sim/train_duel_rnn.py --help` (CPU) | parses; it caught a clash: `--head-win` was already the old head's win lesson, so the new flag is `--ins-pay-win` |
| `docs/runs/2.1/tests_instr.py --map bloodrun --frames 2000 --cmd docs/runs/1.8/1.8a/train.cmd` (the simulator under 1.8a's own settings, the maps from a scratch copy) | **ALL PASSED** (12 minutes). Case 1: `INSTR=0` = the simulator of `c99cc02` to the bit over 2,000 frames (the inputs both have, the pay, the rounds' ends), the 48 new columns zero. Case 2: on with nothing given = off to the bit but the four always-live finish inputs. Case 3: zeros under none, one verb, every number in range, a moment carries the instruction. Case 5: a read changes nothing; the picks land, the force holds and lifts. Case 6: a drill begun (hold), 81 frames. Case 7: the labels change nothing; check rows valid 18,189 seat-ticks, spawn rows 1,119. **Case 8** (new): with `EN_STACK=1` on with nothing given = off; `HEAD_PAY_TRUTH=1` changes nothing of the game; the finish columns and the rows' numbers within 0 to 2 and equal to `_fin()`, 0 bad frames in 6,000; a belief on 95,328 of 96,000 seat-frames; wakes on 49 of 5,860 seat-ticks under an instruction; pattern moments: after a hit 2,854 seat-frames, a fight's start with both stacks high 238; a moment carries the wake's books; a booked chunk hit marks the attacker alone. **Case 4b** (new): `sim/duel_env.py` and the generated group module at two players, under instructions with every 2.1 switch on: alike to the bit |
| The same without `--cmd` (the simulator's default settings), before the walking map was given to the test | two cases FAILED for the test's own reason (no walking map: no candidate row but "none", so no drill began and no check or spawn row opened); fixed (`nav=`), and passed in the run above. Not run again at the default settings |
| `tools/ffa_check.py` | NOT RUN: no `testlab.bsp` |
| 1.8a | `metrics.jsonl` grew through every test (update 75 at 20:46, 79 at 21:08; about 5.6 minutes an update, as before); the repo's tree: 0 tracked changes |

## NOT run, and why

- Any trainer update, the fixed-seed identity of the trainer with the flags off, the converters on 1.8a's saves, the card's memory:
  they need the card or 1.8a's end (the owner: no trainer tonight; measurements on 1.8a's saves wait for its end and the settings check).
- The table on real records: `FIN_RATE_DEFAULT` is still the placeholder.
- `tools/ffa_check.py`: no `testlab.bsp` in the repo's `data/maps` (case 4b stands in for it on Blood Run).
- `plugins/duelbot.py`: not edited (no new call is needed for this build; the earlier ones are still not built).

## Added to the ordered list for after 1.8a (before step 3 of the fourth build's table)

| # | What | Command |
|---|---|---|
| 0a | The table measured on 1.8a's end | `python tools/run/cypher_measure.py check ...`, `... sim --run duel_gru_1_8a --policy <end> --out <dir>`, `python tools/run/fin_rate.py measure <dir> --out docs/runs/2.1/fin_rate_18a.json` |
| 0b | The readouts' baseline with the new line `asked` (none under 1.8a: no instructions) | `python tools/run/goal_readout.py <dir> --side -1` |
| 6a | In the ten small updates: `--ins-pay-win 1` with `HEAD_PAY_TRUTH=1`: `pay_of` in the record, `v_win_loss` finite and falling, `branch.best_by_win_vs_full`; `BRANCH_WPN_P` 0.3: `branch.wpn` counts above 0 | the same scratch run |
| 6b | The trainer with `--ins-pay-win 0` and `BRANCH_WPN_P` 0 against the fourth build's: the same to the bit (the new layer `ins_vv` is at zero and unread) | the run's `tests.py ident` |

## The sixth build (2026-11-12, for 2.1a: [2.1a/CARD.md](2.1a/CARD.md))

| Part | Where | State |
|---|---|---|
| `--ins-bind 1` (it refuses a start where the simulator's `INS_BIND` disagrees). The action the instruction set comes back with each step (`delta["ins_bind"]`), is stored as `b_wd` (1.7c's buffer) and every `head_masks` call of the rollout and the learning step drops the weapon key on those frames through ONE definition, `head2.bound_mask`. Record: `ins_bind` (the share of hand readings bound, of those not his own pick, weapon changes a player-minute) | `sim/train_duel_rnn.py`, `sim/head2.py` | unit checks: the recomputed log-probability equals the stored one with bound rows; without the mask they differ |
| `INS_GATE` (live, -30 to 0, never lowered): the gate of the token "instr" alone; `--gate-open` leaves it, and it leaves the other shut tokens | `sim/train_duel_rnn.py` | `2.1a/tests.py smoke`, `live` |
| `head2.ins_redo`: a standing instruction is drawn anew one second after its last draw; with `ins_end` (done, failed, a wake) the whole rule of when the head re-decides, in the trainer, the checks' player and the server pass. It replaces 1.7a's keep choice as the gate (untrained under an instruction) | `sim/head2.py`, `sim/train_duel_rnn.py` | unit checks |
| `--branch-dump <folder>`: each rollout's instruction-branch rows as the appraisals read them; `tools/run/branch_record.py` runs the trainer frozen (every rate 0) on a scratch copy of a save to record them; `tools/run/prune_inputs.py` fits the appraisals' model with and without a named group of inputs on held-out moments | `sim/branch.py dump_rows`, the two tools | unit checks on made-up branches; the first real case: 2.1a/TESTS.md |
| `plugins/netpass.bind_weapon(env, act, rows)`: the server pass's call (the simulator's own definition) | `plugins/netpass.py` | unit check; `plugins/duelbot.py` does not call it yet |
| `tools/inputs21.py convert` refused a save whose `track["cols"]` holds the labels' NAMES: fixed (a column list is one of numbers). `tools/head21_init.py same` read past a sample recorded before the list's last columns: fixed | the two tools | `2.1a/tests.py start` |

The run's files: `docs/runs/2.1/2.1a/` (`make_files.py` from 1.8a's CURRENT command, `start_live.py` from update 50's own record, `ramp_21a.py`,
`start.ps1`, `stop_21a.ps1`, `tests.py`, `ramp_test.py`). The ordered tests and their results: [2.1a/TESTS.md](2.1a/TESTS.md).

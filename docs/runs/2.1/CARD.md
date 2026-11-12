# 2.1a: the head chooses an instruction, taught by frozen moments (DRAFT)

**SUPERSEDED 2026-11-12 by [2.1a/CARD.md](2.1a/CARD.md)** (from 1.8a's update 50, five stages with update numbers, the binding weapon). Kept for its tables.

*2026-11-11 (owner): "the point of 2.1 is to train the action decisions and incorporate them into the model. So they need to be
actively trained and the build for the run needs to make sure that everything is good to go." The design: [DESIGN.md](DESIGN.md),
[../../design/STRATEGY_2.md](../../design/STRATEGY_2.md). What is built: [INSTRUCTION.md](INSTRUCTION.md) (the instruction),
[SIM_PARTS.md](SIM_PARTS.md) (the simulator), [TRAINER_PARTS.md](TRAINER_PARTS.md) (the trainer).*

**A DRAFT. NOT STARTED, NOT TESTED IN A SIMULATOR. No go is asked.** Written while 1.8a trained, on branch `b21` (worktree
`BobbyBones-21`). The run's `train.cmd`, `start.ps1`, ramp and reference command are **not written**: they are made from 1.8a's
command by `tools/run/make_train_cmd.py` once 1.8a has ended and its end is read. The length is the owner's to say before a start.

**Marks:** ✅ built and unit-tested on made-up arrays · 🔧 built, never run · ⏳ not built · 🧪 measured in the run · ❓ the owner's to decide

**Started from:** 1.8a's end (list 18), brought to list 21 (`tools/inputs21.py convert`: the 41 instruction inputs of the hands at
zero weights, the token "instr" shut), then given the head's part (`tools/head21_init.py add`: the head's input part "ins" at zero
weights, the scorer INSIDE the head (`head2.ins_*` of the network's own weights) with its last layers at zero and its share 0, the
appraisals new). Each step proved by its `same` (0 actions
differ) before anything else. The league's files and the control: `inputs21.py convert` and `head21_init.py widen-league`.

**The start, step by step (each on the owner's go; none run):**
1. `python tools/inputs21.py convert <1.8a's end> <a.pt>`, then `python tools/inputs21.py same <1.8a's end> <a.pt> --sample <obs.npy>` (0 actions differ).
2. `python tools/head21_init.py add <a.pt> <start.pt>` (defaults: `--quiet 1 --ms 1 --bq 1`), then `python tools/head21_init.py same <a.pt> <start.pt> --sample <obs.npy>`.
3. Every league file, anchor and the control: `inputs21.py convert`, then `head21_init.py widen-league` with the SAME `--quiet --ms --bq`.
4. The map sense's start: `python tools/run/mapsense_init.py rows` (system Python), then `fit` (Anaconda): `data/sim_runs/space/mapsense_start.pt`.
5. After the first drills: `python tools/inputs21.py stats <start.pt> <rows.npy> <out.pt>` (the 41 columns' measured statistics; refused once a weight on them has moved, so it is done on a scratch run's rows before the real start).
6. The trainer: `--env duel_env_ffa21 --opt-small-items` and the flags and settings below.

**Settings the run needs beside 1.8a's:** `INSTR=1`, `KNOWN_TRUTH=1`, `SPAWN_TRUTH=1` (with `RESPAWN_QL` as 1.8a has it), `TRACK_TRUTH=1` as
1.8a; `--map-sense 1 --map-sense-init <mapsense_start.pt> --appraise 1 --branch 1 --branch-ins 1 --branch-long 1 --ins 1 --ins-quiet 1
--ins-ms 1 --known-odds 1 --spawn-odds 1`; every share (`BRANCH_P`, `DRILL_INS_P`, `INS_G`, `INS_LONG_W`, `H2_INS_PG`) at 0 in the
start's `live.json` and opened by the ramp.

## The owner's page

| | |
|---|---|
| The goal | the head's choice becomes an **instruction** (a verb, a place, a point, a weapon, quiet or not), chosen every 0.2 s from the simulator's 41 candidate rows, carried out by the hands, and **taught by frozen moments**: the same moment played out under several instructions, the appraisals learning what each brought, the head taught toward the appraisals' order |
| What it should bring (readouts, never targets: rule 12) | less time under heavy threat; rockets, the rail and grenades in his hand where they pay; fire on a point with nobody in view; held angles. Read by `tools/run/goal_readout.py` on each check's games beside 1.8a's end |
| What is new in play | at the start: nothing (every share 0, every new weight zero). Then, one after the other: the drills (the hands under scripted instructions), the instruction token's gate, the head's own instructions |
| Pay | **the hands:** the game's, as 1.8a ends: the pay table (frags and deaths, the items, damage 0.005 zero-sum) and the judge's win part (their dial of it: the simulator's live `WIN_ADD`). **The head's side of 2.1** (`--ins-pay-win 1`, `HEAD_PAY_TRUTH=1`; the owner, 2026-11-11: "the head must be paid by making decisions that improve its readout of the game"; "it should absolutely not be paid for doing damage. The hands get paid for doing that"): **the win chance only**, no entry of the pay table: its own value (`head2.ins_vv`), the frozen moments' dv over 8 s and 30 s, the appraisals' dv, the lesson's target and the pay on his instruction choices. The head's OLDER parts (its target scores, the keep choice, its weapon and fire parts) learn from his whole pay as in 1.8a unless `--head2-pay win` ❓. Nothing is paid for a verb, a state or a place. Every update's record says which pay each network learns from (`pay_of`) |
| Checks | every 20 updates, 200 games against 1.8a's end (the control), every fourth against 1.7a's update 90; both seats give instructions if their files have the part. Never held: every check reported, one under 40% flagged at once |
| Length | ❓ the owner's, asked before the start |

## What is in, and where it comes from

| Part | State | In 2.1a |
|---|---|---|
| The instruction in the simulator: 9 verbs (go, contest, hold, spam, push, cut off, break off, check; none), the state doing / done / failed, 41 inputs of the hands with the firing solution on an unseen point, quiet as its sixth field | 🔧 | `INSTR=1` from update 0 (no instruction given: the simulator as before) |
| The candidates a tick: 41 rows of 37 numbers (items, holding places, spam points, push, cut off, ways out, check, the enemy's spawn points after a frag, none) | 🔧 | from update 0 |
| The map sense (what a place brings, by weapon; the pros' fit as its start, his games' corrections pulled toward zero) | ✅ lesson; 🔧 in the trainer | learns from update 0; nothing reads it |
| The appraisals: for any candidate, damage both ways, who dies, the item, dV over 8 s and over 30 s | ✅ lesson; 🔧 in the trainer | learn from the frozen moments from update 0 |
| Frozen moments: a share of the self-play matches are copies of a moment, each forced one candidate for a second, then free play; the source is the free-play reference | ✅ plan, masks, outcomes; 🔧 in the trainer and the simulator | from update 0 on TARGETS (the head has no instructions yet); on INSTRUCTIONS from the first rollout the candidates exist |
| The long window: a quarter of the branches read over 30 s, across rollouts | ✅ arithmetic; 🔧 in the trainer | with the branches |
| The drills: after a game's start one seat is given a scripted instruction for 8 s (a valid row, a weapon he owns), paid by the game alone | 🔧 | `DRILL_INS_P` 0 → its share, gate 1 |
| The instruction token of the hands' attention | 🔧 | its gate, gate 1 |
| The head's choice of an instruction: the scorer over the rows, the weapon's scores, the quiet logit **inside the head** (its layers, the optimizer's group `ins`; the owner, 2026-11-11: "the point is that the head learns how to make decisions"); its own last tick fed back | ✅ the layers, the one definition of the log-probabilities, the three terms and their gradient into the head's memory (unit-tested); 🔧 in the rollout, the learning step and the decoupled pass | taught from when the appraisals are warm; played from gate 3 |
| "Does the enemy know where I am" (the brain's readout; its chance in every row and among the head's inputs) | ✅ readout, lesson, fill; 🔧 in the trainer; 🔧 the simulator's label | learns from update 0 (`--known-odds`); read by the scorer and the head as soon as they are |
| How sure the brain is (the spread of its zone odds, of its places ahead; in every row and among the head's inputs) | ✅ arithmetic and fill; 🔧 in the trainer | no lesson of its own; from update 0 |
| "Where does he respawn" (the brain's readout over the map's spawn points; its odds in the spawn rows) | ✅ readout, lesson, prior, fill; 🔧 in the trainer; 🔧 the simulator's label | learns from update 0 (`--spawn-odds`) |
| The map sense at each row's place (eight numbers after the row's own; the scorer and the appraisals read 45 a row) | ✅ numpy as torch; 🔧 in the trainer | from update 0 (`--ins-ms`); zeros where a map has no table |
| The checks' player and the plugin's pass give instructions by ONE definition of the reading | ✅ the reading on made-up rows; 🔧 in a game | by the file |
| `plugins/duelbot.py` calling it (the clock, the step, the candidates, the picks) | ⏳ (the calls are listed in TRAINER_PARTS.md) | no 2.1 network on a server before it |
| **The finish time** (the owner, 2026-11-11 night: the lightning gun is for clean-up): his own measured damage a second by weapon and distance (`FIN_RATE`, `tools/run/fin_rate.py`) against his belief of the enemy's stack: seconds to finish, the cautious seconds, seconds of fire, per weapon in every candidate row (64 numbers a row), and for the weapon asked for and the weapon in hand among the hands' inputs (48 columns) | ✅ arithmetic, the simulator's cases; ⏳ the table measured on 1.8a's end (a placeholder until then) | from update 0 (`FIN_RATE` in the command) |
| **The wake**: a pain sound heard, or the believed stack fallen by 25, makes the head draw anew at its next reading | ✅ the rule in one place for the trainer, the checks and the plugin; the simulator's cases | with the head's own instructions |
| **The pattern's moments**: a share of the frozen moments taken just after a chunk hit or a pain sound, or at a fight's start with both stacks high; their branches keep one row and differ only in the weapon | ✅ the plan on made-up seats; 🔧 in the trainer | `BRANCH_WPN_P` 0 → its share, with the branches on instructions |
| **The head paid by the win chance alone** | ✅ arithmetic (another pay table moves no head-side target); 🔧 in the trainer | `--ins-pay-win 1` from update 0 |

## The gates (updates; every dial live and straight; nothing holds or steps back on its own)

No update numbers are set: each gate's width is decided when the one before is read.

| Gate | Opens | Live names | Read before the next opens (reported; the owner decides) |
|---|---|---|---|
| 0 | the map sense, the appraisals, the brain's two new questions and the frozen moments learn; nothing plays from them; the scorer's lesson toward the appraisals begins once they are warm | `MAP_SENSE_W`, `MAP_SENSE_PULL`, `APPRAISE_W`, `KNOWN_W`, `SPAWN_W`, `BRANCH_P`, `BRANCH_LONG_P`, `INS_TEACH`, `INS_TEMP` | level with the control (nothing plays differently but a share of matches being copies); the appraisals' skill by output (R², Brier against the constant); "known": skill above 0 and AUC over 0.5; "spawn": top-1 above the rule's prior, or said plainly that it is not; branches held; the scorer's KL to the appraisals' order falling |
| 1 | the hands under scripted instructions: the drills' share, the token's gate | `DRILL_INS_P`, `INS_DRILL_SECS`, `DRILL_INS_VERBS`, `DRILL_INS_QUIET`; the trainer's gate line for the token "instr" | level; the input health of the 41 instruction columns at each reader; the drills' ledger by verb (what a drilled seat's 8 s brought beside an undrilled one's); the instruction's states reached (doing, done, failed) by verb |
| 2 | the long window's share of the lesson's target | `INS_LONG_W` | the appraisals' seventh output's R²; the scorer's order with and without it |
| 3 | the head's own instructions, from none | `INS_G` 0 → 1 | games against the control at each step; the picks by block, weapon and quiet; changes a second; the chosen rows' forecast against what they brought; megas and reds head to head; quiet re-decisions |
| 4 | the game's pay on the choice ❓ | `H2_INS_PG` | the same |

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Assumed | The alternative, and what is known |
|---|---|---|
| The verbs' definitions (doing, done, failed) and the candidate rows | my definitions from the design; the map's own tables (holding places, spam points, ways out) from 1.7 | never run. The scripted probes (`tools/run/verb_test.py`: hold, spam) say whether a perfect hold or spam pays at all with 1.8a's hands; a verb whose perfect script loses to free play is not drilled until that is fixed |
| A drill follows a game's start | a start is often a moment where a verb can pay (35% are pro starts) | not measured. The alternative: drills from frozen moments of his own games. The drills' ledger at gate 1 says which |
| The appraisals can tell candidates apart | test 4 of DESIGN.md: the first choice is 9 to 12% of one branch's outcome; about 10 branches a target make the order half signal | the forecast is a regression over many moments. Its skill by output is logged every update; the scorer is not taught toward it before `--ins-warm` branches, and a forecast with R² at 0 teaches nothing but noise: read it before gate 3 |
| dV by the head's own value (RUNDOWN decision 1, option a) | the head's value reads the items' clocks; the judge does not | his own bias is taught back to him. Beside it in every branch record: the judge's shadow pay over the window, and the real damage, deaths and items. The long window is a second check on the value's reading |
| The instruction's choice is learnt inside the PPO epochs from the re-run head (moved inside 2026-11-11) | the learning step's log-probability of a kept reading is the play's: the same rows, forecasts, masks, drawn row / weapon / quiet | **1.7c's false start was this kind of wiring** (a reference log-probability without a mask the play used). Guarded by: ONE definition of the masked log-probabilities used by the rollout, the learning step and the decoupled pass (`sim/head2.py ins_row_logp / ins_wq_logp / ins_joint_logp`; numpy twin for the checks and the plugin); the unit test `test_inside` (a made-up rollout re-run: largest difference 0.0 on every kept reading, masked rows, "none" alone, nothing offered, a drill's, a forced one's); in the run `ins.kl.played_to_before` every update: near 0 without `--overlap`, and a MAJOR line if it is not on the first scratch update |
| The pay's term under `--overlap` clips around the learner's own log-probability before the update | as his target's (decoupled PPO) | plain PPO around the stored one is what runs without `--overlap`; the two are compared on the scratch runs (TRAINER_PARTS.md, the fourth build, test 6) |
| The kept readings' cost on the card (about 1 GB a piece at 2,048 seats) | it fits beside the sequences | unmeasured; `--ins-seats` halves it; the first scratch update at full size is the measure |
| A seat under an instruction does not train its old target choice | the instruction supersedes the target | as `INS_G` rises the head's target scores and the hands' target rows go quiet on those seats. If the instruction fails, `INS_G` back to 0 leaves a target choice that has not been trained for that long |
| The keep choice gates a change of instruction | 1.7a's keep choice won games and flickered | watched: changes a second, quiet re-decisions over 0.08 |
| Branches against himself | nobody in his games holds an angle or spams yet | the drills put such seats in his games at gate 1; DESIGN.md's weakness stands until he learns to |
| "The enemy knows where I am" = he has him noticed in view, or his belief of him is within 300 units and under 3 s old | both numbers are hand-set (the simulator's `KNOWN_R`, `KNOWN_T`) | the measured alternative: the distance and age at which an enemy's belief still lets him hit first, read off his own games (how far his belief was from the truth when he pre-fired and hit). Not measured. The label only teaches a readout; if its skill is near 0 the head reads noise: gate 0 reads it |
| The spawn readout against the simulator's rule | the rule is known (a random one of the far half from the enemy when the wait ends); a learner can at best find which half | the record gives the prior (uniform over the far half from where he stands) beside the readout every update. If the readout is not above it, the spawn rows' odds add nothing over the rule and the column is dropped for the rule's own number |
| The check verb's place: the nearest walking point by his way with a line to where the brain expects him | nearest, not safest: exposure from other sides is not read (SIM_PARTS.md) | the map sense at that row's place is the measured number for it, and is in the row. Watched: what check rows brought in the branches (`branches.jsonl` by block) |
| The map sense at a row's place is "standing there with the weapon in his hand now" | the row's weapon is chosen after the row | the alternative (one read a weapon) is nine times the lookups. The appraisals see the row's weapon separately |
| The brain's zone odds are read from the token (what the hands' token carries) | the same numbers as the readout's at the tick | to check on a real rollout (TRAINER_PARTS.md, not verified 9) |

**Pathologies watched from update 1** (every FLAG and MAJOR line read): a refused or unapplied `live.json` (MAJOR); a check under 40%
(MAJOR, told at once); any firing cost above zero (MAJOR); one block of rows taking over 80% of the picks (reported at once); the
scorer's entropy under 0.3 while `INS_G` is under 1; changes of instruction over 2 a second; the appraisals' R² of dV under 0 for 20
updates; megas or reds head to head 20% under the control's; frags a match-minute under 1.5; quiet re-decisions over 0.08; a part of
the target's sum over 40 (rule 11: the target's sum stays live for seats under none). Negative frags and lopsided games: Cypher's
measures of each check.

**Weaknesses, volunteered:**
- It is the largest build so far and none of it has run. Every part has its own flag and its own unit tests; the first rollout with
  everything on is itself a test and should be a scratch run, not the start.
- The time a reading adds is unmeasured (the appraisals forecast every offered row of every seat five times a second of game).
- The checks give instructions; a game server does not yet. A play test of a 2.1 network needs the plugin's side first.
- The league's older selves play under no instruction, so in the league he meets nobody who holds or spams by instruction.
- The fill at every reading adds work on the host (the map sense's table lookups for every offered row of every seat): unmeasured.
- The two new readouts sit beside the network: the league's older selves have none, and a file exported before them reads zeros there.
- Walking may not be silent in the simulator (SIM_PARTS.md, finding 2): quiet movement cannot pay until that is measured and decided.

## Later (not in 2.1)

This opponent's habits (the owner, 2026-11-11: adapting within a game to how this opponent plays, and remembering earlier games
against him: "keep it out for now, but do keep in mind that this will be something later"); the
league's snapshots giving instructions; drills from his own frozen moments; the spawn rows opened by his own frag only.

## Every new live name, with its range

| Name | Range | Whose |
|---|---|---|
| `MAP_SENSE_W`, `APPRAISE_W`, `INS_TEACH` | 0 and up (`INS_TEACH` to 100) | the trainer |
| `KNOWN_W`, `SPAWN_W` | 0 to 100 | the trainer |
| `MAP_SENSE_PULL` | 0 and up | the trainer |
| `BRANCH_P`, `BRANCH_LONG_P`, `INS_G`, `H2_INS_PG`, `INS_LONG_W`, `INS_ENT` | 0 to 1 | the trainer |
| `INS_TEMP` | 0.01 to 100 | the trainer |
| `DRILL_INS_P`, `DRILL_INS_QUIET` | 0 to 1 | the simulator |
| `INS_DRILL_SECS` | 1 to 60 | the simulator |
| `DRILL_INS_VERBS` | "verb:share,..." of go, contest, hold, spam, push, cut, out, check | the simulator |
| `BRANCH_WPN_P` | 0 to 1 | the trainer (the share of the frozen moments that are the pattern's: weapon-only branches) |
| `FIN_RATE` | 27 numbers, each 0 to 250 (`tools/run/fin_rate.py` prints the string) | the simulator (the finish time's table) |
| `WIN_ADD` (not new) | 0 to 100 | the simulator: the HANDS' share of the win-chance pay; the head's stream does not move with it (`--ins-pay-gain` is fixed at the start) |

Each is accepted by the trainer's reader in `tools/run/test_21_parts.py` (and a value outside its range refused). `tools/run/live_accept.py`
uses that reader. A new name the ramp will write is checked by `live_accept` in `start.ps1` as every run's.

## Before a go (none of it done)

0. **The finish time's table measured on 1.8a's end** (after the settings check): `python tools/run/cypher_measure.py sim --run duel_gru_1_8a --policy <end> --out <dir>`, then `python tools/run/fin_rate.py measure <dir> --out docs/runs/2.1/fin_rate_18a.json`; its `FIN_RATE=...` line goes into the run's command. The new columns' statistics measured from a drill's rows (`tools/inputs21.py stats`).
1. 1.8a's end read; the tests of INSTRUCTION.md's table (the simulator's identity, the converter's `same`, the probes).
2. `python docs/runs/2.1/tests_instr.py --cmd docs/runs/1.8/1.8a/train.cmd` (eight cases; run on 2026-11-11 night, see TRAINER_PARTS.md "The fifth build") and `tools/run/test_21_parts.py` (214 checks) in the repo's tree.
3. The trainer at a fixed seed with every new flag off (a file without the part) against the trainer before the build: the same to the bit.
4. The start's two converters and their `same` (0 actions differ); a resume with `--opt-small-items`: the optimizer loads, the group `ins` is added after the load and by name on the next resume.
5. A scratch run of ten small updates with everything on, every dial stepped, WITHOUT `--overlap`: `ins.kl.played_to_before` near 0 (the instruction's wiring on real buffers), the three terms finite, `ins.head_grad`; then the same with `--overlap 1`; then ten updates at full size (the card's memory with the kept readings) and a check against the control.
6. The settings check against 1.8a's command; `train.cmd`, `start.ps1`, the ramp; this card's gates given their updates.
7a. The owner's calls of the third pass: whether the head's older parts move to the win chance too (`--head2-pay win`); whether the hands keep their win-chance pay (`WIN_ADD`); a finer stack answer of the brain for the finish time (today: four bands); `--ins-pay-gain` (default: `WIN_ADD` at the start).
7. The owner's calls: TRAINER_PARTS.md's open questions (a is CLOSED: inside the head, 2026-11-11; b: league seats under no
   instruction; c: the game's pay on the choice as the last gate; d: the spawn rows opened by any death of the enemy or by his own
   frag only); whether walking is to be made silent (SIM_PARTS.md, finding 2); the length.
8. `plugins/duelbot.py`'s calls (TRAINER_PARTS.md) before any 2.1 network goes on a server.

The ordered test list with the command for each: TRAINER_PARTS.md, "The fourth build", its last table (eight steps).

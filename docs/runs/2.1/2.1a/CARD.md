# 2.1a: the clean-up and the head's silent instruction in one run, the head's decisions frozen (the blend)

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_u90_17a.pt` + `opt_u90_17a.pt`).

*Owner, 2026-11-13, after 2.0d was stopped at update 57 (RUNS.md #50; 44 / 45 / 43% against 1.7a u90 at updates 10 / 30 / 50, the keep
choice's trips rising): "We need to freeze the decisions for 2.0 and 2.1"; "freeze decisions; blend 2.0 and 2.1 into one ... call it 2.1a";
"that plan looks good. Build the code, and make sure it agrees with your understanding of quake from the research. Also verify for me that
you're using the sim fixes done by the other agent." Earlier forms of this card: [CARD_from_18a.md](CARD_from_18a.md) (built on 1.8a's
update 50, never started; its parts are this run's instruction), [CARD_sketch_from_20d.md](CARD_sketch_from_20d.md) (the sketch from
2.0d's end, superseded by the blend). 2.0d's own card: [../../2.0/2.0d/CARD.md](../../2.0/2.0d/CARD.md). The design:
[../DESIGN.md](../DESIGN.md), [../INSTRUCTION.md](../INSTRUCTION.md), [../SIM_PARTS.md](../SIM_PARTS.md), [../TRAINER_PARTS.md](../TRAINER_PARTS.md).*

**Marks:** ✅ built and tested · ⏳ not built or not run · 🧪 measured in the run · ❓ the owner's to decide

## The owner's page

| | |
|---|---|
| The goal | **(1) the clean-up:** onto AIM3, the corrected knockback, the clean input list and the dodge inputs, with only the hands and the brain adapting: the strategy stays exactly 1.7a u90's. Success: games level with 1.7a u90. **(2) the instruction, silent:** the head learns to choose an instruction (verb, place, point, weapon) on every seat while playing none, taught by drills and frozen moments. Success: the readiness marks read at the end; they decide whether 2.2 gives it seats |
| Frozen the whole run | **the head's decisions**: his target (the hands' rows and the head's scores), the weapon key (the hands' rows and the head's weapon scores), the keep choice. They play as at update 90 and learn nothing (`--freeze-choice 1`: out of every policy term and the exploration bonus, the head's policy term off, their weights put back after every step). They still read the head's memory, which keeps learning (the instruction learns through it): their weights are fixed, their inputs move a little |
| Length | **until noon 2026-11-14** (owner, 11-13: "Start it now and run until noon tomorrow. You can let an individual segment of the run go for longer if the timeframe permits it"): the trainer's `--minutes`; about 145 updates at ~6.5 minutes. The opening segments stretched to fit (below) |
| Checks | every 20 updates, 200 games, against **1.7a's update 90**; every fourth against **1.8a's end**; the extra one at update 10. Both seats under AIM3's end values and `KNOCK_QL=1 KNOCK_NOW=1`. Never held; one under 40% flagged at once |
| Kept file | `keep/policy_end_21a.pt` + `opt_end_21a.pt`; marks 10, 30, 50, 75, 95, 115, 130, 145, 160 |

## What trains when (every dial live and straight; nothing holds or steps back on its own: `ramp_21a.py`)

| Updates | Comes in | What learns |
|---|---|---|
| 0 (steps) | the list 21d; the corrected knockback; damage 0.005 zero-sum; far rail 0.1; keep share 1; no habits; the pass-odds lesson off | the hands, the brain |
| 0 to 30 | **AIM3** to its end values (`AIM3_W` 0 → 1, `AIM3_SIZE_A` 1 → 0.39, `AIM3_SIZE_B` 0 → 0.355, `AIM3_LEAD` 0 → 1, `AIM3_RELOAD` 1 → 0) | the hands adapt to the aim |
| 0 onward | the appraisals, the map sense, the brain's two questions: lessons nothing plays from | silently |
| 30 to 75 | **the dodge inputs** (`DODGE_G` 0 → 1); **the frozen moments** (`BRANCH_P` 0 → 0.15); **the drills** (`DRILL_INS_P` 0 → 0.25, `DRILL_INS_RATE` 0 → 0.02); **the instruction's token in the hands** (`INS_GATE` −12 → 0) | the hands learn to dodge and each verb in drills; the appraisals learn from the branches |
| 30 onward | the head's choice of an instruction, taught in shadow on every seat toward the appraisals' order, scored by the win chance alone (`INS_G` 0 the whole run: it plays no game seat) | the instruction chooser, silently |
| 75 to 115 | the weapon-only moments (`BRANCH_WPN_P` 0 → 0.3) | the instruction's weapon scorer |
| 115 to the end | held | |

AIM3 comes in alone first: in 2.0d it cost a few points while the hands adapted, so a dip from 30 to 60 can be traced to the group that
opened then. The two opening segments are stretched (30 to 75, 75 to 115) to fill the night (owner, 11-13). Drills bind the weapon on drill seats only (`INS_BIND=1`); no game seat is under an instruction.

## What goes in

| # | Part | Built | State |
|---|---|---|---|
| 1 | **The input list 21d** (869: 2.0d's list 20d, its cut, the order's ten kept, the dodge group; the instruction's 48 columns) | `sim/input_list_21d.json`, `docs/INPUTS_21d.csv`, `sim/duel_env_ffa21d.py` | ✅ |
| 2 | The start in three proved steps: `tools/inputs20d.py convert` (+ its optimizer), `tools/inputs21.py --old 20d --new 21d convert`, `tools/head21_init.py add` | the converters (inputs21 and head21_init given the 20d/21d lists) | ✅ each `same`: 1 / 0 / 0 actions differ (the first is rounding, rounding off) |
| 3 | **`--freeze-choice`** (`sim/train_duel_rnn.py`): the head's decisions held; the weights' sizes logged each update (`frozen_choice`); the ramp's MAJOR line if they move | | ✅ `tests.py ident` (every arm, 2 updates) and `smoke` (10 updates): the frozen weights the same to the bit, the rest learning |
| 4 | **The corrected knockback** (`KNOCK_QL=1`, `KNOCK_NOW=1`; the other session's 85bdc48 and 8eb42c5; `qsim.dll` has `qsim_knockback_t` and the step-one functions) | 2.0d's command, carried over | ✅ verified in the command and the checks' settings |
| 5 | **The dodge inputs** (`DODGE_IN=1`, `DODGE_G` live, the token following it) | 2.0d's | ✅ (2.0d's tests) |
| 6 | The instruction's parts (drills, frozen moments, appraisals, map sense, the brain's two questions, the shadow lesson, the binding weapon in drills) | 2.1's build (the other session), run on this line | ✅ `tests.py smoke`: drills, frozen moments, the instruction's records on every update; `ident`: they reach play |
| 7 | **The map sense's start** (the pros' fit distilled: `tools/run/mapsense_init.py`; held-out R² 0.95 dealt, 0.93 taken) | `data/sim_runs/space/mapsense_start.pt` | ✅ |
| 8 | **`FIN_RATE`**: his own damage a second by weapon and range, measured on 1.7a u90 under AIM3's end values and the corrected knockback | `fin_rate_17a_u90.json` (20 games, 80 seats; rockets 46.7 / 12.2 / 2.6, lightning 54.5 / 36.0 / 2.0, rail 23.9 / 11.8 / 0.0 a second of trigger under 400 / 400-768 / over 768; thin cells keep the placeholder) | ✅ |
| 9 | Run files: `make_files.py` (2.0d's command + the instruction's settings + `--freeze-choice 1`), `start_live.py`, `ramp_21a.py`, `start.ps1`, `stop_21a.ps1`, `tests.py` | | ✅ settings check against 1.7a's command and update 90 PASS; `live_accept` PASS (the start's file and the ramp's 92) |

**Kept as update 90 has it:** the head's target choice, its weapon part and the keep choice (frozen), the order's parts (never asked:
`CMB_G`, `PADD`, `FADD` 0, its token shut; `COMBAT=1` for its ten inputs), `WIN_ADD` 0.33, the item table, no firing cost.

## The readiness marks (read at the end; the owner sets the numbers at the go; reported every check, never held on)

| Mark | What it says | 1.9a's value when it failed |
|---|---|---|
| The appraisals' skill on the change in win chance, on held-out branches | the lesson's target is not noise | not measured |
| The shadow choice's entropy | the scorer has learnt something | 3.29 of 3.26 uniform |
| How long a shadow order would stand | re-choosing every 0.2 s is not a random walk | 0.21 s |
| Shadow weapon changes a minute | the bound weapon would not flip | 107 |
| The shadow choice among the appraisals' best three | the choice follows its lesson | not measured |
| Drills: "doing" by verb, and what each weapon brings in them | the hands can carry each out | 6 to 10% doing |
| The shadow choice by block of rows; one block over 80% | no collapse to one verb | |

## Which pay each network learns from

| Network | Learns from |
|---|---|
| The hands | the pay table (damage 0.005 zero-sum, items, frags) + their share of the win pay; in a drill the same game pay |
| The head's decisions (target, weapon part, keep) | nothing (frozen); the head's value still learns |
| The instruction's value, the frozen moments' change, the lesson's target | the win judge's change in win chance alone (`HEAD_PAY_TRUTH=1`, `--ins-pay-win 1`) |
| The appraisals, the map sense, the brain | outcomes; the pros' fit as the map sense's start only |

## ❓ Decisions for the owner at the go

1. ✅ **The length**: until noon 11-14. **The marks' numbers**: ❓ read at the end.
2. ✅ **Yes** (owner, 11-13). **The head's lesson toward the appraisals' order (rule 13)**: his own forecasts of his own branches, not an old rule; the alternative
   (the pay on shadow choices alone) is what 1.9a showed too weak. In the plan you approved; confirm.

## Red team

| Part | Assumed | The alternative, and what is known | Watch |
|---|---|---|---|
| Several changes at the start (the cut, the knockback, the pay step, keep share 1, no habits) | each small or exact | 2.0d took them together and sat at 44% from update 10: their cost is not known one by one | the check at 10; if under 45%, a level check of the start under each (a side job, your go) |
| Frozen decisions under moving inputs | their weights fixed, the head's memory and the hands' trunk move | freezing the inputs too would freeze the instruction's learning | the keep choice's quiet re-decisions (alarm 0.075 for three updates), his target's trips, megas and reds head to head |
| No learning-rate-zero warm-up after the surgery ([BOTS.md](../../../research/BOTS.md), OpenAI Five) | the converter carries the optimizer's moments, rescaled; the new parts start fresh | a few updates at rate 0 | the KL of updates 1 to 5 |
| Drills (about 14% of seat time from update 60) cost no games | 2.1a's trial on 1.8a's line | the hands forced onto rockets and the rail lose exchanges; the pay table teaches them away | the drills' ledger by weapon; the checks at 70 and 90 |
| The appraisals learn from branches against himself | his own play is the truth to forecast | nobody in his games holds, times or steals: "hold" and "spam" forecast poorly | the appraisals' forecast by verb |
| The judge scores a branch | score, time, stacks, weapons | it cannot see an item up: "the mega is up, I do this first" reads as a loss over 8 s | the shadow choice's share of item rows |
| "Quiet" drills | walking is silent | the footstep rule is speed, not the walk key, and unmeasured here (MECHANICS.md 7.1) | the drills' doing rate for quiet |
| Dodging pays in self-play | reversals cost the shooter | the calibration (AIM3.md section 3): a reversal costs a pro's lightning about twice what it costs his; no hand-lag limit (owner: "keep aim3 as it is") | the dodge blank test at the end |

**Weaknesses, volunteered:** the run delivers no stronger strategy by itself (the strategy is frozen); its instruction is silent, so its
result is the marks, not games; no game server can play a list-20d or 21d network (plugins, `sim/export_duel.py`), so no play test.

## Research check (hard rule 14; [docs/research/README.md](../../../research/README.md))

1. **The game.** The knockback of the lightning, the machine guns and the shotgun now as the game's (MECHANICS.md 7.1: fixed under
   `KNOCK_QL`, the hit frame's order under `KNOCK_NOW`). AIM3's parameters are the pros' measured aim (AIM3.md). The instruction rests on
   respawn times, the spawn rule and hearing (MECHANICS.md 3.1, 6). Still off the game: the hit cylinder against our box, players passing
   through each other, the footstep rule (7.1). The dodge inputs read only what a person sees and feels.
2. **What wins.** Position, then weapon, then aim (README core 2, 7; DUEL_STRATEGY.md principle 1): the instruction's verbs are the
   guides' plays (go, contest, hold, spam, push, cut off, break off). Zero-sum damage serves "die less than the opponent" (core 1).
   Nothing here works against a principle; nothing yet pays control itself (core 3): that needs a pay that sees the next spawns (2.4).
3. **The player's view.** Every instruction candidate's numbers come from his belief and senses (SIM_PARTS.md); the truth only labels
   lessons (`KNOWN_TRUTH`, `SPAWN_TRUTH`, `HEAD_PAY_TRUTH`). Missing against DUEL_STRATEGY.md 5.1: the gap between the next mega and red,
   effective stacks, his own noise as a head input.
4. **In and out of control.** No pay change beyond 2.0d's symmetric steps, so no new exploit. The drills give the out-of-control plays
   (break off, spam an item, hold) practice they never get in free play (core 4).
5. **Self-play equilibrium.** In games unchanged in strategy (frozen); the hands' equilibrium moves under AIM3 and the corrected knockback
   (the lightning's push 1.4 times harder, dodging possible). The risk is in the silent lesson: forecasts made against copies who never
   time or trap (core 9; PRO_INTERVIEWS.md 5.5).
6. **Bot precedent.** The silent chooser taught from predicted outcomes of each order on every tick is BOTS.md section 13, idea 1
   (IntelAct, JueWu's value heads); "no system put an untrained strategy layer over trained hands" is honoured: the trained strategy stays
   frozen and the new one plays nothing. OpenAI Five's surgery rules: the same surgery on the league's snapshots (done), the rate-zero
   warm-up (not done: red team).
7. **Rule 12.** No pro outcome is a target. The pros' fit seeds the map sense (a place's worth), AIM3 is the pros' measured limits;
   hit rates, weapon shares and the panel are readouts.

## Before the go

| # | What | State |
|---|---|---|
| 1 | List 21d, the converters, each `same` on update 90; the anchors converted (heads widened) | ✅ `tests.py start` ALL PASSED |
| 2 | `--freeze-choice` built; the frozen weights the same to the bit after training | ✅ |
| 3 | The instruction's parts on this line: `tests.py ident / smoke / live` (`tests_*2.log`) | ✅ ALL PASSED |
| 4 | The map sense's start | ✅ |
| 5 | `FIN_RATE` measured on update 90 | ✅ |
| 6 | The run's files; the settings check against 1.7a's command and update 90; `live_accept` on the start's file and the ramp's | ✅ |
| 7 | The full-size trial: the run's own first updates (the owner, 11-12: 1-2 updates, the run's first ten are the trial) | at the start |
| 8 | The owner's length, marks, and go | ✅ go 11-13 ~20:00, until noon 11-14 |

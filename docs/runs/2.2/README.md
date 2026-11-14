# 2.2: new decisions, one at a time, and the head asking "should I do X?" of each

**The family's design (owner, 2026-11-14). No run is carded; nothing here is built beyond what is listed as built.** After
[2.1](../2.1/README.md) (the lock out, map sense learning, the method proven on keep-or-change); before [2.3](../2.3/README.md) (the head
sets the weapon). The owner's design of 11-10 ("It decides between a suite of questions, recurrently, with instructions that feed to
hand for execution": [2.1/DESIGN.md](../2.1/DESIGN.md), "The questions, explicitly") is what this round builds, in the order the failures
taught.

## The goal

His list of goals grows from 17 targets to include **cut him off, fire at where he will be, hold a place watching a point, break off**,
each added as **a new row of the same choice he already makes**, and each with its own forecast ("if I commit to this, what does it
bring?"). The head reads its own last answers on the next tick (the question loop).

## Decided (owner, 11-14)

| # | Decision | From |
|---|---|---|
| 1 | Starts from **2.1's end** (no lock, the keep choice holding, map sense learnt) | the round order |
| 2 | A new decision is **a row added to the target choice** (the hands' row + the head's score, both regularized: rule 11), opened out of the one it stands in for. **No second chooser** | 1.3b and 1.5a worked this way; b1.3a, b1.4a, 1.7a's order, 1.9a and 2.1a did not |
| 3 | **One new decision a step.** 1.7a opened the order, the pointer and the fire push together and could not tell which cost games | rule "one new thing per round" |
| 4 | For each new decision, in this order: **(i) the hands learn to carry it out** in drills while it is never chosen in games; **(ii) its forecast learns** from frozen moments where it is forced as his first choice; **(iii) its row opens** in games, slowly, on a measure; **(iv) its forecast's lesson runs on** so a rare decision is not learnt away | 1.7a: "an order the hands cannot carry out is judged and learnt away"; AlphaStar kept its reference all run |
| 5 | The verbs are **a toolkit, not a quota**: no share, rate or weapon mix of the pros is a target or a pass mark | rule 12; DESIGN.md "The verbs are a toolkit" |
| 6 | The weapon stays the hands' key plus the head's scores, as now. The head setting it is 2.3 | 1.9a: the weapon handed over alone flipped up to 107 times a minute |
| 7 | The head's pay is not changed here | one thing at a time |

## The order of the new decisions (proposal; the owner sets it)

| Step | The decision | Why here | What exists for it |
|---|---|---|---|
| 0 | (if not done in 2.1) the map sense as head inputs | every later decision is about a place | `sim/mapsense.py`; the head's input to build |
| 1 | **Hold a place watching a point** (with any weapon) | after 2.1 an arrival is keepable and the holding places H1 to H8 are already targets: the smallest step. The new part is the point to watch | `sim/duel_env.py` `note_holds`; the instruction's "hold" verb, place and point (`_ins`, `_ins_step`) |
| 2 | **Cut him off** (go where the brain predicts him in 1, 2, 4 s) | uses the brain's forecast that exists; needs no new firing skill | 1.7's cut-off candidates (`COMBAT=1`, `tools/order_init.py`, `sim/head2.py` `order_scores`); the instruction's "cut" |
| 3 | **Break off** (a way out) | the out-of-control player's first need | 1.7's ways out; the instruction's "out" |
| 4 | **Fire at where he will be** (a corridor, an item at its time) | needs the hands to shoot at a point with no enemy in view: the hardest for the hands, so last | the brain's pass odds (`--pass-odds`), 1.7's spam points and fire push (`fadd`), the instruction's "spam" and its drills |

## Where the code is

| Part | Built | Files |
|---|---|---|
| The verbs, a place, a point, the 41 candidate rows, their inputs to the hands (48 columns, the group "b21 instruction") | yes (2.1's build; ran in 2.1a behind a shut gate) | `sim/duel_env.py` `INSTR`, `INS_VERBS`, `INS_BLOCKS`, `_ins_step`, `_ins_clock`, `_ins_bel`, `_instr_feat`, `_ins`; `sim/input_list_21d.json`, `sim/duel_env_ffa21d.py`, `tools/inputs21.py` |
| Drills: a verb given to a seat for a few seconds so the hands learn it | yes; in 2.1a 7.8% "doing" | `sim/duel_env.py` `_ins_drill_step`, `_ins_drill_end`, `DRILL_INS_P`, `DRILL_INS_RATE`, `DRILL_INS_VERBS` |
| The forecast for any candidate (damage both ways, who dies, the item, the change of his standing) | yes; no skill yet (2.1a) | `sim/appraise.py`; `--appraise`; frozen moments with a forced first choice `sim/branch.py`, `--branch-ins` |
| The head reading its own last answers (what he is on, since when, the forecast then and now, the change signals) | yes, for the instruction | `sim/head2.py` `ins_u`, `np_ins_u`, `ins_held_width`, `np_ins_held_u`, `InsState` |
| Teaching a choice toward the forecasts' best | yes, for the instruction's scorer | `sim/head2.py` `ins_dv`, `ins_target`, `ins_loss`, `ins_learn`; `--ins-teach`, `--ins-temp` |
| The questions about the situation (S1 to S9) | yes, but for "where he next comes into view" (a rule-made input, cut in list 18) and "who takes each yellow" | the brain (`sim/btoken.py`, the belief); `--pass-odds`; fight odds; "in control"; `sim/knownodds.py`, `sim/spawnodds.py`; `sim/win_judge.py` |
| The separate instruction scorer (41 rows, its own optimizer group) | yes: **not used** (decision 2) | `sim/head2.py` `add_ins`, `ins_scores`, `ins_wscores`, `np_ins_read`; `tools/head21_init.py`; `--ins`, `--ins-g`, `INS_GATE` |
| 1.7's combat order (a kind, a pointer over candidates, a token to the hands) | yes: **not used as a chooser**; its candidates and `order_scores` may be reused | `sim/head2.py` `order_scores`, `has_cmb`; `tools/order_init.py`, `order_maps.py`; `COMBAT`, `--cmb-g`, `--padd` |
| Opening a new target out of another | yes | `tools/targets_init.py open --from-nothing` |

## To build

| # | What | Notes |
|---|---|---|
| 1 | **The target choice with more rows**: the simulator's intention output and the head's `n_target` widened by a row (or a block) a decision; a frozen simulator copy before the action list changes; widening tools with `same` | `sim/duel_env.py` `INTENTS`, `ACTION_DIMS`; `sim/head2.py` `layout(n_target=...)`; the league's files widened the same way |
| 2 | A new row **carried out by the instruction's machinery**: choosing the row sets the verb, place and point the hands already read as the instruction's columns | joins `intend()` to `_ins_step`; the hands' columns come in at zero behind a shut gate (list 21e = list 20e + "b21 instruction") |
| 3 | The forecast asked of **target rows** and of the keep choice's "stay", not of the 41 instruction rows | `sim/appraise.py` takes a verb, a target, a weapon, the map sense: the candidate encoding stays |
| 4 | The head's **last answers as inputs** for target rows (the question loop): what he is on, since when, its forecast then and now, the change signals | reuse `ins_u`; at zero weights, a shut gate |
| 5 | The choice **taught toward the forecasts' best** on every tick he does not play the row (the lesson that needs no played seats), beside the game's pay on the rows he does play | 1.9a's lesson: learning silently must include the choosing |
| 6 | Per step: its drill, its readouts (chosen, arrived, carried out, what it brought beside the target it stands in for), its flags | the ramp of 2.1 |
| 7 | "Where he next comes into view" and "who takes each yellow" as learned questions | DESIGN.md S4, S7 |
| 8 | The server side for each new row | `plugins/duelbot.py` calls `observe()`, never `step()`: whatever `_ins_step` updates must be set by the plugin |

## Measured before each step

- The drill alone: do the hands carry the verb out when told (the share "doing", the damage it brings), before its row may be chosen.
- The forecast alone: on held-out frozen moments, does it rank the new decision against the target it stands in for better than chance.
- A level check of the opened start at full share (200 games), as 1.7a's "rarer start" was checked.

## Weaknesses to carry into each card

- The forecasts learnt nothing in 2.1a; 2.1's M1 and step A are the first proof they can.
- A decision that pays only against a person (a rail angle, fire at a corridor) may not pay against his copies: no league seat punishes or
  rewards it yet (2.0b's postmortem: the holder seat). Named here, to decide before step 1.
- More rows spread his choice (the entropy bonus spreads over new equal choices whatever they pay: CLAUDE.md, design lessons).
- Research check (rule 14) is owed on each step's card; the notes to read: DUEL_STRATEGY.md (control, out-of-control play, the maps'
  positions), PRO_INTERVIEWS.md (the fight decision), BOTS.md sections 9 and 13.

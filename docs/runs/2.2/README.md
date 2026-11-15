# 2.2: the head's decisions, each with the weapon and the trigger it calls for

**The family's design (owner, 2026-11-14 evening: 2.2 and 2.3 consolidated into one). No run is carded; nothing here is built beyond
what is listed as built.** After [2.1](../2.1/README.md) (the lock out, map sense learning, the "should I do X?" method proven on
keep-or-change). What was 2.3 is folded in here ([2.3/README.md](../2.3/README.md) is a pointer).

## The idea (the owner's words, 11-14)

- "His mechanical hands are reactionary, they see the enemy and fight when he's in sight. The head makes a decision saying 'you better
  shoot a rocket there to deny him' and then he acts on it when the hands have no idea to do that."
- "The head making weapon and trigger decisions will really be for the types of shots he isn't taking now: the ones that the hands
  network wouldn't know anything about, because they only know 'i see the enemy and I shoot'."
- "The head recommends weapons and then there is a sum with the hands (which of course gets regularized) which creates the final
  decision. Same with actually firing."

So there are two kinds of shot, and each has its owner:

| | The enemy in view | Nobody in view |
|---|---|---|
| Who knows to shoot | the hands: they see him and fight, as now | **the head**: it decided to deny an item, fire down a corridor, hold a weapon ready on an angle |
| The weapon key and the trigger | the hands' scores carry them; the head's recommendation should be near nothing | the head's scores carry them, added to the hands' |
| Aiming | the hands at the enemy | the hands at the point the decision names (they are drilled to look where they are told) |

A new decision therefore comes **with** its weapon and its trigger: they are not a later round.

## The goal

His list of goals grows from 17 targets to include **hold a spot watching a point, deny (fire at a point he must pass or an item at its
time), cut him off, break off**. Each is a new row of the choice he already makes. With each row the head recommends a weapon and,
where the decision is a shot, the trigger. The head reads a forecast for every option and its own last answers (the question loop).

## Decided (owner, 11-14)

| # | Decision | From |
|---|---|---|
| 1 | Starts from **2.1's end** (no lock, the keep choice holding, map sense learnt) | the round order |
| 2 | A new decision is **a row added to the target choice** (the hands' row + the head's score). **No second chooser** | 1.3b and 1.5a worked this way; b1.3a, b1.4a, 1.7a's order, 1.9a, 2.1a did not |
| 3 | **The weapon and the trigger are sums**: the hands' scores plus the head's, the head's given the decision he is on. **Nothing binds; the hands can always disagree; no dial shrinks the hands' part** | owner 11-14; the weapon has been this sum since 1.5a, the trigger since 1.7a; 1.9a's bound weapon changed up to 107 times a minute |
| 4 | **Every sum is regularized from its first update** (the target, the weapon key, the fire key: `H2_L2` on both parts), each part's size recorded and flagged over 40 | rule 11 |
| 5 | **One new decision a step.** Its weapon and trigger recommendation open with it, not before and not after | 1.7a opened the order, the pointer and the fire push together and could not tell which cost games |
| 6 | For each decision, in this order: **(i) the hands are drilled** to carry it out (go there, look at the point) while it is never chosen in games; **(ii) its forecast learns** from frozen moments where it is forced, the weapon-only moments among them; **(iii) its row opens** in games with its weapon and trigger recommendation, slowly, on a measure; **(iv) its forecast's lesson runs on** | 1.7a: an order the hands cannot carry out is learnt away; AlphaStar kept its reference all run |
| 7 | **The hands stay reactive and stay paid by the pay table.** Timid (not firing with the enemy in view) is never right; playing to not die is. The share of in-view time he fires is a guard at every step | owner 11-14; 2.0e's play test (60% in training, 53% and 35% against the owner) |
| 8 | No table, no pro target, no weapon or shot share as a pass mark; no cost for firing, switching or holding | rule 12; owner 11-04 |
| 9 | ❓ **The head paid by the win chance only** ("ideally the 2.2 should start paying the head by win chance. I'll have to think more about it when we get there"). Proposed as step 1 below | owner 11-11, 11-14; not decided |

## The steps (one after the other; each ends on its measure, reported; nothing holds or steps back on its own)

| Step | What comes in | What is new for the hands | What the head recommends with it |
|---|---|---|---|
| 0 | **The map sense as head inputs** (his place and each target's place, by weapon), gate shut → open | nothing | nothing |
| 1 | ❓ The head's pay to the win chance only; the hands keep the pay table | nothing | nothing |
| 2 | **Hold a spot watching a point**; the head's last answers as inputs (the question loop) | go there, look at the point | the weapon for that spot (the map sense rates a spot by weapon). No trigger: when he shows, the hands react |
| 3 | **Deny**: fire at a point he must pass, or at an item at its time | look at the point (learnt in step 2) | **the weapon and the trigger**: the shot the hands know nothing about |
| 4 | **Cut him off** (where the brain predicts him in 1, 2, 4 s) | go there | the weapon to arrive with |
| 5 | **Break off** (a way out) | take the way | none needed |

Why this order: holding needs only what 2.1 gives (an arrival he can keep) plus looking at a point; denying reuses that look and adds the
head's trigger, which is the owner's central case; cutting off and breaking off are movement and come after.

## Where the code is

| Part | Built | Files |
|---|---|---|
| The head's weapon scores added to the weapon key; its credit | yes (1.5a; in every network since) | `sim/head2.py` `add_weapon`, `has_weapon`, `wsc`, `wadd`, `np_wadd`; the trainer's `--head2-wpg` (live `H2_WPG`), `wpn_group` |
| The head's scores added to the fire key; its credit | yes (1.7a); it showed no measurable effect there (its scores 0.42) | `sim/head2.py` `has_fire`, `np_fadd`; live `FADD`, `--head2-fpg` (live `H2_FPG`); `tools/order_init.py` |
| Weapon scores that depend on the chosen row | yes, for the instruction's scorer | `sim/head2.py` `ins_wscores`, `ins_wq_logp`, `ins_joint_logp` |
| The verbs, a place, a point, the candidate rows, their inputs to the hands (48 columns, "b21 instruction") | yes (2.1's first build; ran behind a shut gate in 2.1a) | `sim/duel_env.py` `INSTR`, `INS_VERBS`, `INS_BLOCKS`, `INS_SPAM_W`, `_ins_step`, `_ins_clock`, `_ins_bel`, `_instr_feat`, `_ins`; `sim/input_list_21d.json`, `tools/inputs21.py` |
| Drills (a verb given to a seat for a few seconds) | yes; 7.8% "doing" in 2.1a | `sim/duel_env.py` `_ins_drill_step`, `_ins_drill_end`, `DRILL_INS_P`, `DRILL_INS_RATE`, `DRILL_INS_VERBS` |
| Points to fire at, places to cut off, ways out | yes (1.7's candidates) | `COMBAT=1`, `tools/order_init.py`, `order_maps.py`, `sim/head2.py` `order_scores` |
| "Will he pass this point within 3 s", who takes the next mega and red | yes | the brain's pass odds (`--pass-odds`), "in control" |
| The forecast for any candidate, with a weapon in it | yes; no skill yet (2.1a); 2.1 is its first proof | `sim/appraise.py` (`N_WEAPON` 10); `--appraise`; `sim/branch.py`; `--branch-ins` |
| Frozen moments where only the weapon differs | yes; never opened | `--branch-wpn-p` (live `BRANCH_WPN_P`) |
| The head reading its own last answers | yes, for the instruction | `sim/head2.py` `ins_u`, `np_ins_u`, `ins_held_width`, `np_ins_held_u`, `InsState` |
| Teaching a choice toward the forecasts' best | yes, for the instruction's scorer | `sim/head2.py` `ins_dv`, `ins_target`, `ins_loss`, `ins_learn`; `--ins-teach` |
| The head paid by the win chance only | yes | `--head2-pay win`, `--ins-pay-win`, the simulator's `HEAD_PAY_TRUTH`; `sim/win_judge.py` |
| Map sense | yes; learning in 2.1 | `sim/mapsense.py`; `--map-sense*` |
| Opening a new target out of another | yes | `tools/targets_init.py open --from-nothing` |
| **Not used** (built, deliberately left out) | | the separate instruction scorer (`add_ins`, `ins_scores`, `np_ins_read`, `--ins`, `--ins-g`); 1.7's order as a chooser (`--cmb-g`, `--padd`); the binding weapon (`INS_BIND`, `bound_mask`, `--ins-bind`); the pros' weapon table and the play-time dial (1.7c) |

## To build

| # | What | Notes |
|---|---|---|
| 1 | The map sense as head inputs: measured statistics, zero weights, a shut gate; a widening tool with `same` | `sim/head2.py` `PARTS`, `layout`, `feats`; 2.0b's lesson: slow gate, a blank test |
| 2 | **The target choice with more rows**: the simulator's intention output and the head's `n_target` widened a decision at a time; a frozen simulator copy before the action list changes; the league's files widened the same way | `sim/duel_env.py` `INTENTS`, `ACTION_DIMS`; `sim/head2.py` `layout(n_target=...)` |
| 3 | A chosen row **carried out by the instruction's machinery**: it sets the verb, place and point the hands read; the hands' columns in at zero behind a shut gate (a list 21e = 20e + "b21 instruction") | joins `intend()` to `_ins_step` |
| 4 | **The head's weapon and trigger scores given the row he is on**, added to the hands' keys (reuse `ins_wscores` for the weapon; the same form on the fire key), zero at the start, `same` | the head's part must be free to be near nothing with the enemy in view: recorded separately in view and out of view |
| 5 | The lesson for the trigger part: frozen moments of "fire at this point now" against "do not", scored by what the next seconds brought; the game's pay on the shots he does take | in 1.7a the fire push had no lesson of its own and did nothing |
| 6 | The forecast asked of target rows (and their weapon), not of the 41 instruction rows | the candidate encoding of `sim/appraise.py` stays |
| 7 | The head's last answers as inputs for target rows; the choice taught toward the forecasts' best on ticks he does not play the row | reuse `ins_u`, `ins_target` |
| 8 | Per step: its drill, its readouts, its flags; the ramp | from 2.1's ramp |
| 9 | If decision 9 is taken: the win judge re-fitted on 2.1's games; the win-chance signal's size measured on recorded games before the switch | 1.9a: the signal was about a tenth of the head's other lessons |
| 10 | The server side of each row, and of the head's trigger | `plugins/duelbot.py` calls `observe()`, never `step()`: whatever `_ins_step` updates must be set by the plugin |

## Guards from update 1 of every step (reported; the owner decides)

| Guard | Line |
|---|---|
| **He fires with the enemy in view** (timid) | must not fall from the step's start (training about 60%) |
| The head's weapon and trigger scores **with the enemy in view** | stay small against the hands': the hands fight |
| Weapon changes a minute | flag over 20 (1.9a: 107) |
| Shots with nobody in view: how many a minute, what they hit, the ammunition they use | a readout; rising with no damage is waste (no cost is added for it) |
| Each part of each sum | flag over 40 (rule 11) |
| Quiet re-decisions, trips, targets reached (2.1's) | no slide |
| Camping and spawn camping (the panel) | a kept hold must not become it |
| Every check against the step's start | one under 40% flagged at once |

## Weaknesses to carry into the card

- The forecasts learnt nothing in 2.1a; 2.1 is the first proof they can, and 2.2 waits on it.
- **Denial shots do pay against his copies** (a copy must go to the mega at its time), so that step can be learnt in self-play. **A held
  rail angle may not**: nobody in his league walks into one the way a person does (2.0b's postmortem: the holder seat). To decide before step 2.
- The head's trigger did nothing in 1.7a; its lesson is new work, not plumbing.
- A head that learns "hold fire" too widely is the timidity of 2.0e's play test: guard 1.
- More rows spread his choice (the entropy bonus spreads over new equal choices whatever they pay).
- The lightning habit against his copies (about 60% in hand) is unchanged; the head's weapon recommendation is learnt in that equilibrium.
- A Research check (rule 14) is owed on each step's card: DUEL_STRATEGY.md (control, out-of-control play, each map's positions),
  MECHANICS.md (weapons by range, splash, switch time), PRO_INTERVIEWS.md (the fight decision, spam), BOTS.md sections 9 and 13.

## After 2.2 (parked)

| | |
|---|---|
| Opponents | league seats that play what his copies do not (a holder, a dodger); small exploiters (AlphaStar, GT Sophy) |
| Information | a decision made to learn where the enemy is (the "check" verb exists in `INS_VERBS`) |
| This opponent | adapting in a game and across games to one opponent (owner 11-11: after the strategy layer works) |

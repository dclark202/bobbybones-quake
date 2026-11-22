# 2.1a: the head learns to choose an instruction, silently, from 2.0d's end

**Started from:** 2.0d's end (`data/sim_runs/duel_gru_2_0d/keep/policy_end_20d.pt` + `opt_end_20d.pt`), once 2.0d has ended and been
read. 2.0d is running (RUNS.md #50); **this card is a sketch for the owner's review, not a go request.** Nothing is built for the
2.0d start yet.

*Rewritten 2026-11-13 (owner: "start by getting the card for 2.1 up to date ... letters are for different ATTEMPTS at the run number").
The card built on 1.8a's update 50 and never started: [CARD_from_18a.md](CARD_from_18a.md) (its tests, command and logs in this folder
are that build's). The design: [../DESIGN.md](../DESIGN.md), [../INSTRUCTION.md](../INSTRUCTION.md), [../SIM_PARTS.md](../SIM_PARTS.md),
[../TRAINER_PARTS.md](../TRAINER_PARTS.md). What 2.0d did and left to 2.1: [../PLAN_FROM_17A.md](../PLAN_FROM_17A.md). Why the
split: [1.9a's postmortem](../../1.9/1.9a/POSTMORTEM.md), [2.0b's](../../2.0/2.0b/POSTMORTEM.md).*

**Marks:** ✅ built and tested · 🔧 built for 1.8a's line, to redo on 2.0d's · ⏳ not built · 🧪 measured in the run · ❓ the owner's to decide

## The 2.n series (owner, 11-13)

The goal of 2.n is **understanding control**, reached "by adding features and design changes in an incremental and targeted way".
2.1 is the family "the head learns to choose"; 2.1a is its first attempt (a failed attempt is 2.1b). Each later step is its own
family (2.2, 2.3, ...), listed under "Later rounds".

## The owner's page

| | |
|---|---|
| The goal | The head's choice of an **instruction** (a verb, a place, a point, a weapon) is built in and **taught on every seat while it plays none**; the hands learn to carry each verb out with each weapon in drills. At the end the head's choice can be read against marks before it is given a seat (2.2) |
| The one new thing | the instruction, silent. Nothing he plays in a game changes: every game seat is chosen as 2.0d's end chooses (its head's target, the keep choice, its weapon part), all still learning |
| Length | ❓ one night proposed (90 updates, as 2.0d); the minutes an update from the two-update trial |
| Checks | every 20 updates, 200 games, against **2.0d's end**; every fourth against **1.7a's update 90**; the extra one at update 10. Both seats under AIM3's end values, `KNOCK_QL=1 KNOCK_NOW=1`, the dodge inputs as 2.0d leaves them. Never held; one under 40% flagged at once |
| Done when | (a) the checks are level with 2.0d's end (the silent parts cost no games), and (b) the readiness marks below are read. Whether they are met is the owner's call for 2.2 |
| Kept file | `keep/policy_end_21a.pt` + `opt_end_21a.pt`; marks at 10, 30, 60, 90 |

## What goes in

| # | Change | When | State |
|---|---|---|---|
| 1 | **List 21d**: list 20d (821) + the instruction's 48 columns (869), at zero weights, the token "instr" shut. The order's ten inputs stay (they carry his target's look point on seats under no instruction: every game seat here) | the start, exact (`same`) | ⏳ `input_list.py extend` from 20d; a converter for a 2.0d network, its head, optimizer and anchors |
| 2 | **1.7a's combat order's unused parts removed** (kind, pointer, fire push, `CMB_G`/`PADD`/`FADD`): never asked since update 90, superseded by the instruction. Its ten inputs are NOT removed here (2.2) | the start, exact | ⏳ in `tools/head21_init.py`, with `same` on a 2.0d save |
| 3 | **The head's choice of an instruction** inside the head (the candidates' rows, the scorer with its last layers at zero, its weapon scorer, its value), share 0 | the start, exact | 🔧 `tools/head21_init.py add` |
| 4 | **The appraisals, the map sense, the brain's two questions** as lessons nothing plays from | from update 0 | 🔧 |
| 5 | **The frozen moments** (`BRANCH_P` 0 → 0.15): a moment copied, each option played out for a second then on, the outcomes kept; the appraisals learn them | updates 0 to 30 | 🔧 |
| 6 | **The drills** (`DRILL_INS_P` 0 → 0.25, `DRILL_INS_RATE` 0 → 0.02): each verb with each weapon he owns, from a state where it can be given, the weapon **bound in the drill only** (`INS_BIND` acts only on a seat under an instruction; no game seat is) | updates 0 to 30 | 🔧 |
| 7 | **The instruction's token opens in the hands** (`INS_GATE` −12 → 0): read in drills and frozen moments only | updates 0 to 30 | 🔧 |
| 8 | **The head's choice taught in shadow on every seat** (`INS_G` 0 the whole run): toward the appraisals' order once they have seen 20,000 branches; scored by the win chance alone (`HEAD_PAY_TRUTH=1`, no entry of the pay table) | from update 0 | 🔧; ❓ rule 13 (below) |
| 9 | **Weapon-only moments** (`BRANCH_WPN_P` 0 → 0.3): the same moment under each weapon he owns, so the weapon scorer has its own lesson | updates 30 to 60 | 🔧; ❓ in this run or 2.3 |
| 10 | ❓ **proposed: frozen moments drawn by situation**, a fixed share each: a mega or red due within 5 s with both players in reach; the first 5 s after a frag; a fight entered outstacked; the rest as they come | from update 0 | ⏳ |
| 12 | ❓ **proposed (the 2.0d session, 11-13; [KEEP_FLICKER.md](../../2.0/2.0d/KEEP_FLICKER.md)): the keep choice frozen** (`--keep-freeze 1`: it plays at its share, learns nothing). Another 90 learning updates would put it over 150 updates past 1.7a's update 90, where 1.7a's drift cost games (quiet re-decisions 0.054 at u130, 0.088 at u170, 0.125 at u240); frozen, that drift is out of 2.1a's read, and the part is replaced in 2.2 | the start | ✅ the flag exists (1.7c); the owner decides at 2.0d's end |
| 13 | **A new readout each update: the mean chance of a re-decision on quiet readings** (no contact, nothing heard), beside the sampled rate: it shows the weights drifting before the sampling noise does | from update 0 | ⏳ the keep record in `metrics.jsonl` |
| 11 | ❓ **proposed: the control panel in every check** (readouts only): both big items to one player in a cycle; his arrival before a big spawn; effective stack lead (`min(H + A, 3H)`); fights entered outstacked; seconds alive after a respawn; frags within 10 s of the enemy's respawn | every check | ⏳ |

**Kept exactly as 2.0d's end has it, all learning:** the head's target choice and its credit (`H2_PG` 1), its weapon part (`wadd` 1),
the keep choice (share 1; learning unless item 12 freezes it), `H2_L2` on both parts of each sum, the pay table (damage 0.005 zero-sum, far rail 0.1),
`WIN_ADD` 0.33, the dodge inputs (unless 2.0d's blank test drops them), AIM3, the corrected knockback, no habits in the league.
**The lock is gone and does not come back** (rule 13): the 1.8a-line card's `INTENT_HOLD` 8, item teacher, speed pay and switch cost
do not exist on this line.

## The schedule (every dial live and straight; nothing holds or steps back on its own)

| Updates | Dial | From → to | Mark kept |
|---|---|---|---|
| 0 | items 1 to 4, 8 at zero effect | `same`: no action differs | start |
| 0 to 30 | `BRANCH_P`, `DRILL_INS_P`, `DRILL_INS_RATE`, `INS_GATE` | 0 → 0.15, 0 → 0.25, 0 → 0.02, −12 → 0 | 10, 30 |
| 30 to 60 | `BRANCH_WPN_P` (if item 9 is in) | 0 → 0.3 | 60 |
| 60 to 90 | | held | 90 = the end |

## The readiness marks (read at the end; the owner sets the numbers at the go)

Reported at every check, never held on (rule 6). They decide whether 2.2 opens the head's share.

| Mark | What it says | 1.9a's value when it failed |
|---|---|---|
| The appraisals' skill on the change in win chance, on held-out branches | the lesson's target is not noise | not measured |
| The shadow choice's entropy | the scorer has learnt something | 3.29 of 3.26 uniform |
| How long a shadow order would stand | re-choosing every 0.2 s is not a random walk | 0.21 s |
| Shadow weapon changes a minute | the bound weapon would not flip | 107 |
| The shadow choice among the appraisals' best three | the choice follows its lesson | not measured |
| Drills: "doing" by verb, and what each weapon brings in them | the hands can carry each out | 6 to 10% doing |
| The shadow choice by block of rows; one block over 80% | no collapse to one verb | |

**The keep choice's alarms** (the ramp's, from update 1; reported, never held on): **quiet re-decisions over 0.075 a reading for three
updates in a row** is the flicker alarm; "targets reached under 9%" only confirms it (noisy: 2.0d crossed it at updates 8 and 11 with
quiet re-decisions at 0.046); trips are a symptom, read last. Where games start to fall is not measured: 1.7a held at 0.054 and fell
somewhere past it.

## Which pay each network learns from

| Network | Learns from |
|---|---|
| The hands | the pay table + their share of the win pay, as 2.0d; in a drill the same game pay, nothing for the verb itself |
| The head's older parts (target, weapon part, keep choice) | as 2.0d (`--head2-pay all`) |
| The instruction's value, the frozen moments' change, the lesson's target | the win judge's change in win chance alone; **the items' race term off** until its noise is measured under the judge's own part (1.9a) |
| The appraisals, the map sense, the brain | outcomes; the pros' fit as the map sense's start only |

## ❓ Decisions for the owner

1. **Item 8 under rule 13.** The head's choice is taught toward the appraisals' order. The appraisals are his own forecasts of his own
   branches, not an old rule or network. The alternative (the pay on shadow choices alone) is what 1.9a showed too weak. My
   recommendation: yes.
2. **Item 9:** weapon-only moments here (your word: 2.1's goal includes the weapon decision), or with the binding weapon in 2.3.
   My recommendation: here; it is silent.
3. **Items 10 and 11:** in, or left out of the first attempt.
4. **The marks' numbers** and the length, at the go.
5. **Item 12:** the keep choice frozen or learning, decided at 2.0d's end. My recommendation: frozen. It also limits the shared-memory
   risk in the red team (the silent lesson moving the head's memory under a learning keep choice).
6. **A side job before 2.2 is designed** (rule 9: yours to allow; pure inference on the processor, cores 14 to 17 while 2.0d trains or
   after it ends): 1.7a's saves of updates 130 and 240 with the keep choice's weights on the head's memory zeroed, 200 games each,
   quiet re-decisions measured. It says whether the drift lives in the memory's inputs or in the lesson
   ([KEEP_FLICKER.md](../../2.0/2.0d/KEEP_FLICKER.md), open question 1). Not run.

## Red team

| Part | Assumed | The alternative, and what is known | Watch |
|---|---|---|---|
| A silent run shows nothing in the checks | level games = no cost | the marks are the result; they are shadow measures, and a shadow choice can look ready and still fail when played (1.9a's 51% at a quarter share said nothing) | 2.2 opens slowly whatever the marks say |
| Drills on a share of seat time (about 14%) cost no games | 2.1a's two-update trial on 1.8a's line | the hands forced onto rockets and the rail lose exchanges (the hold probe: 6 points behind free play) and the pay table teaches them away from it | the drills' ledger by weapon; the checks at 10 and 30 |
| The appraisals learn from branches against himself | his own play is the truth to forecast | nobody in his games holds, times or steals, so "hold" and "spam" forecast poorly and the head learns to leave them (2.0b: a place has no price there). 2.4's habit seats are the answer; not in this run | the appraisals' forecast by verb |
| The judge scores a branch | score, time, stacks, weapons | it cannot see an item up (test 5d), so "the mega is up, I do this first" reads as a loss over 8 s. The refit with next-spawn ownership is a daytime measurement, proposed before 2.3 | the shadow choice's share of item rows |
| The order's ten inputs stay | exact; the hands read them a little | removed now (not exact) | 2.2 |
| Walking is silent | the comment at `WALK` | not measured: 161 units a second against a footstep threshold of 150 (SIM_PARTS.md). "Quiet" in a drill may teach nothing | measure before the go |
| The old head keeps its credit beside a new chooser's lesson | they share the head's memory | the new lesson's gradient moves the old target (1.9a: gradient into the scorer 10 to 20 times under the target lesson's, so the risk is the other way) | the target sum's parts (rule 11), the keep choice's three flags, megas and reds head to head |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

**Weaknesses, volunteered:** the run delivers no stronger network by itself; the instruction's form has never trained from this
line; no game server can play a list-20d or 21d network (plugins, `sim/export_duel.py`), so no play test until that is written.

## Research check (hard rule 14)

1. **The game.** The instruction's rows rest on respawn times, the spawn rule and hearing (MECHANICS.md 3.1, 6). Off the game: the
   footstep rule (speed, not the walk key; 7.1), players pass through each other, the hit box. Walking's silence is unmeasured.
2. **What wins.** Position, then weapon, then aim (DUEL_STRATEGY.md 1.9, principle 1); weapon by range and stack (principle 12 of
   PRO_INTERVIEWS.md section 4). The verbs are the guides' plays (DUEL_STRATEGY.md 5.2). Nothing here works against a principle; nothing
   yet serves control itself (principle 2): that needs an opponent who punishes and a pay that sees the next spawns.
3. **The player's view.** Every candidate's number comes from his belief and senses (SIM_PARTS.md); the truth only labels lessons.
   Missing against DUEL_STRATEGY.md 5.1: the gap between the next mega and red, effective stacks, his own noise as a head input.
4. **In and out of control.** No pay changes, so no new exploit. The drills give the out-of-control plays (break off, spam an
   item, hold) practice they never get in free play.
5. **Self-play equilibrium.** Unchanged in games. The risk is in the lesson: forecasts made against copies who never time or trap
   (DUEL_STRATEGY.md 5.3; PRO_INTERVIEWS.md 5.5, practice-partner syndrome).
6. **Bot precedent.** BOTS.md section 13, idea 1 (teach the head on every tick from predicted outcomes, open seats on a readiness
   mark) and idea 6 (pivotal moments at fixed shares: item 10); section 9.2: no system put an untrained chooser over trained hands.
7. **Rule 12.** No pro outcome is a target. The pros' fit seeds the map sense (a place's worth) and pro moments are starting
   states. The panel's and the weapon numbers are readouts.

## Later rounds (the order is the owner's; each is one new thing)

| Round | The one new thing | Control |
|---|---|---|
| **2.2** | the head takes seats: `INS_G` 0 → 1, opened against the marks; the order's ten inputs faded out and removed; **commitment inside the chooser, replacing the separate keep choice**: one decision every 0.2 s, the held instruction's score raised by a small learned "stay" term that reads only the change signals (the enemy came into view, a sound, the belief's shift since he committed, an item's clock crossing his time to it), its age and "arrived". No timer, no lock (rule 13). It is a sum of two learned outputs: both parts decayed and their sizes flagged over 40 from the moment it is live (rule 11). It has no price on switching and can drift as the keep choice did: its own drift readout (the stay term out of contact, over time), and the lesson decided after decision 6's diagnostic. A learned slow prior stays the fallback if its orders do not stand | he chooses what to do |
| **2.3** | the binding weapon on game seats (`INS_BIND` on its own dial); 2.0d's weapon part beside it decided | the weapon follows the plan |
| **2.4** | the head's own pay on its played choices, by the win chance alone (`H2_INS_PG`), with the judge refit to see who owns the next mega and red (measured first) | choices priced by the next spawns |
| **2.5** | habit seats in a quarter of the league: copies of him under a scripted instruction (a timer, a holder, a thief), each first tested over 200 games | timing and position cost something |
| **2.6** | information: the strategy inputs out of the hands (`SFADE`), quiet, the enemy's stack from his pickups, the spawn odds | the hidden stack |
| **2.7** | a trained exploiter in the league | his own habits priced |
| later | adapting to this opponent (owner, 11-11) | |

## Before the go

| # | What | State |
|---|---|---|
| 1 | 2.0d ended and read: its checks, the keep choice's flags, the dodge blank test | running |
| 2 | List 21d, the converters, `same` on 2.0d's end and its anchors | ⏳ |
| 3 | The run's files from `make_files.py` on 2.0d's command; the settings check against 2.0d's command and end; `live_accept` | ⏳ |
| 4 | `tests_instr.py`, the unit checks, `tests.py start / old / ident / live / smoke` on the new line | 🔧 passed on 1.8a's line |
| 5 | `FIN_RATE` and the hold and spam probes on 2.0d's end | 🔧 measured on 1.8a u50 |
| 6 | The ramp's flag code run on a real record with drills and branches; a crashed flag thread stops the ramp loudly (1.9a) | ⏳ |
| 7 | Walking's speed and footsteps measured | ⏳ |
| 8 | Items 10 and 11, if in | ⏳ |
| 9 | The two-update trial at full size | ⏳ |
| 10 | The owner's decisions, the marks, the length, the go | ❓ |

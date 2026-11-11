# 1.8a: the 1.n series redone in one run from b1.2d's end, under AIM3

*2026-11-11 (owner): "the fast track aim3 in at b1.2d, which covers all the parts of the 1.n series that worked after and gets us to the
same ending point as roughly 1.7a, all weapon fire costs out, speed pay out, win chance pay in (same portion), updated item pay table,
strategy head, etc."; "We do not need to adhere to the 'order of operations' of the 1.n that existed, simply aggregate the most successful
parts with hindsight in mind"; "the big change in performance was seen with the strategy layer opening, this I want to make sure we
retain"; "Call this model 1.8". Why from b1.2d: the lightning took his hand inside 1.3b, in step with the head's credit (in hand 40% at
update 10, 53% at 50, 56% at the end; rockets 37% to 26%), under an aim model whose error was largest where the rail and rockets need it
smallest. The family: [README](../README.md). The aim: [design/AIM3.md](../../../design/AIM3.md). What comes after:
[2.1](../../2.1/DESIGN.md).*

**NOT STARTED, AND NOT READY TO START (2026-11-11 afternoon).** The owner's order of work: "fix the inputs + tune aim3; redo from 1.2d on; then
get to 2.1"; "I will start 1.8 from a new session." Everything below was built and tested this morning on the UNCLEANED start (b1.2d's end
widened to 1,053 inputs). The input clean-up ([design/INPUTS_CLEANUP.md](../../../design/INPUTS_CLEANUP.md), its "Final" table) changes the
start network and every list, so **before a go these are redone on the cleaned start**: the start and its proofs (`tests.py start`), the
identity, live, smoke and dry tests, the zero point; and **built new**: the last stage (the strategy inputs fading out of the hands). What
carries over unchanged: the design, the schedule, the command's settings, the ramp, the restart, the scripts' logic.

**Marks:** ✅ exists and was tested in its own run · ⏳ to build and test before a go · 🧪 measured in the run · ❓ the owner's to decide

**Started from:** b1.2d's end (`data/sim_runs/duel_gru_b1_2d/keep/policy_end_b12d.pt` + `opt_end_b12d.pt`; 980 inputs), widened with
zero weights to today's 1,053 inputs, the strategy head (1.3b's form) and the keep choice (1.7a's form) added at zero effect.

## The owner's page

| | |
|---|---|
| The goal | one network at roughly 1.7a's update 90 (the head choosing his target, the keep choice, no hand-written rule on his target, no firing cost, no speed pay in games), whose hands and head both learnt under AIM3, in the shape 2.1 builds on |
| Length | **330 updates in one run, with one planned restart** at the save of update 150 (two simulator switches that are not live). The owner, 11-11, on the condensed schedule: "keep the head at 80. The rest looks fine." At 5.3 minutes an update (the dry run's and 2.0c's): about 29 hours of training |
| What b1.2d's end already has (nothing to do) | win chance pay at the same portion (`WIN_ADD` 0.33); the item table by the point (`ITEM_PT_*`, `ITEM_FLAT` MH 0.35 / RA 0.30 / YA 0.15, the decay above 100); the stack lead at 0; the far-rail pay 0.25; the firing and jerk costs' weight at 0 (`COST_FIRE_W`, `COST_JERK_W`) |
| Damage pay | **0.005 a point and zero-sum from update 0** (owner, 11-11: "Change the damage pay to 0.005 at the start"; "damage should be zero sum from the start"): `DMG_REWARD` 0.0055 → 0.005, `DMG_TAKEN_W` 0.8 → 1.0, both as a step at the start, not a ramp. A trade of equal damage pays neither side; a 100-damage hit pays 0.50 where it paid 0.55, and taking one costs 0.50 where it cost 0.44. Between the two players only (`DMG_ENEMY_ONLY=1`): his own splash and falls cost the full price, as before |
| Checks | every 20 updates, 200 games, against b1.2d's end (the start); every fourth against **1.7a's update 90** (the point we are re-reaching; it beat b1.2d's end 91.5%); the extra one at update 10. Both seats under AIM3's end values, as in 2.0c. Never held: every check reported, one under 40% flagged at once |
| Read at every check | games won; megas and reds head to head; **the weapon in his hand in view by range** (rockets, rail, lightning: a readout, not a target, rule 12); big weapons owned; the head's part and the hands' part of the target's sum (rule 11); quiet re-decisions; frags a match-minute |

## What is in, and where it comes from

| Part | From | In 1.8a |
|---|---|---|
| AIM3 at the default level (the average pro's parameters) | 2.0c's build ✅ | live, 0 → end values over updates 0 to 30 |
| No firing cost of any kind: `SHOT_COST=0`, `BLIND_FIRE_W=0`, `COST_FIRE_W` 0, refused at the start if above zero | 1.5a, 1.6a ✅ | from update 0 |
| The strategy head's target scores added to the hands' (`--head2-add`, memory speeds spread, λ 0.995, the item rule teaching the hands' rows alone, decoupled weight decay 0.01 on both parts) | 1.3b ✅ (89% against b1.2d's end; 25% with the head blanked) | attached at zero from update 0; its credit (`H2_PG`) 0 → 1 over updates 50 to 130, 1.3b's 80 updates |
| The switch cost out, a weapon he holds choosable (`INTENT_SWITCH=0`, `WEAPON_OWN=1`) | 1.4b ✅ | at the restart, update 150 (as in 1.4b: after the head has the credit) |
| The item rule's lesson out (`INTENT_TEACH_W` 1 → 0) and the speed pay in games out (`SPEED_PAY` 0.125 → 0) | 1.6a ✅ (level; the speed held) | together over updates 160 to 190, as 1.6a did (its 40 updates were level throughout) |
| The keep choice in place of the 8-second lock (`KEEP_G` 0 → 0.975) | 1.7a's updates 10 to 90 ✅ (63% against 1.6a's end) | attached at share 0 from update 0; over updates 210 to 250, then held |
| **The strategy inputs out of the hands** (owner, 11-11: "Once we get the head back in, those inputs can go from the hands. Put that at the end of this 1.8 run"): the clock and score (8), the mega's and red's timers and who has them, when he last took each item (12), the game's three: faded in the hands, the head keeps them | the input clean-up ⏳ to build (a second fade group, as v0.4.2's rule fade) | over updates 270 to 310, held to 330; removed from the hands' list after the run |
| The 1,053 inputs of today's simulator; the tokens order, timers, space and targets shut (`--gate-open 0`) | 2.0c's start ✅ | all run; so 2.1 needs no widening |
| Kept as b1.2d has them | | the win pay, the item table, the far-rail pay, the speed pay in item runs, the league's anchors, every delay and every other aim number |

## What is scrapped from the 1.n suite

| Part | Why |
|---|---|
| b1.3a's copy lesson, b1.4a's blend | failed (the head alone 37%; the blend ran away from the rules) |
| 1.4b's matchmaking by difficulty (PFSP) | scrapped with its run; not in 1.7a either |
| 1.5a's head scores on the weapon key (`H2_WPG`) | never shown to win games (off at update 50: 100-100); his weapon did not move; 2.1 makes the weapon part of the instruction |
| 1.5a's weapon habits on 30% of the league seats | did not move his weapon; a third of them play the pros' weapon by range (rule 12 in spirit). ❓ 2.0b's lesson asks for a holder seat in the league: that is 2.1's to design |
| 1.7a's combat order, the pointer on his targets, the fire push, the brain's pass odds (`COMBAT`, `CMB_G`, `PADD`, `FADD`, `H2_FPG`, `--pass-odds`) | learnt away or likely harmful; 2.1's instruction replaces them. Not added to the network at all; the simulator's side is off (`COMBAT=0`). **Found in the build:** with `COMBAT` on, the hands' ten "order" inputs carry the look point of his chosen target even when no order is asked, and 1.7a's update 90 had learnt to read them a little (those columns' weights 8% the size of an ordinary input's). In 1.8a they read zeros and his weights on them stay zero; they open with 2.1's instruction. The checks are played with `COMBAT` on so that 1.7a's update 90 keeps them (it changes nothing for 1.8a's network) |
| 1.7b (timers, fight odds), 1.7c (the weapon table), 2.0a and 2.0c (the damage pay), 2.0b (the map's inputs and pay) | no gain or a loss. Their inputs exist at zero weight and stay shut |
| The order of the old runs' settling time | 1.3b ran 80 updates after its dial was full, 1.5a 133, 1.7a's result was taken as its dial reached the top: about 160 updates saved |

**So 1.8a's end differs from 1.7a's update 90 in five ways, on purpose:** AIM3; the damage pay 0.005, zero-sum; no head part on the weapon key; no weapon habits in the league; the hands do not read the look point of his target (the order's inputs).

## The schedule (updates; every dial live and straight; nothing holds or steps back on its own)

| Updates | Opens | The mark kept (with its optimizer) | Passes when (reported, the owner decides) |
|---|---|---|---|
| 0 | fire costs out; the head and the keep choice attached at zero | start | the start answers as b1.2d's end (0 actions differ with the costs as b1.2d's) |
| 0 to 30, held to 50 | AIM3 | **50: "b1.2d under AIM3"**, the control for the rest | level with b1.2d's end at 10, 30, 50 |
| 50 to 130, held to 150 | the head's credit (1.3b's 80 updates: owner, "keep the head at 80") | **150: "1.3b under AIM3"** | the checks rise as 1.3b's did (60, 70, 77, 88% at its updates 10 to 90); the head blanked at 150 plays far worse; 🧪 the weapon in hand |
| 150 (restart at the save) | the switch cost out, a held weapon choosable: the trainer alone is stopped right after the save of update 150 (`stop_18a.ps1 -Update 150`) and started again from it (`start.ps1 -Restart`); the watcher, the ramp and the logger keep running | | the update-170 check |
| 160 to 190, held to 210 | the item rule's lesson and the speed pay in games out | **210: "1.6a under AIM3"** | level; megas and reds a minute, big weapons owned |
| 210 to 250, held to 270 | the keep choice | **270: "1.7a under AIM3"** | games up; quiet re-decisions under 0.08; against 1.7a's update 90 level or better |
| 270 to 310, held to 330 | the strategy inputs fade out of the hands ⏳ | **330 (the end)** | level; megas and reds head to head; the hands' part of his target scores |

Each stage ends on an update the watcher checks (10, 30, 50, ...), so it is read at its end values before the next opens. As first written the
run was 310 updates (AIM3 over 40, the teacher over 40, the keep choice over 80, no last stage). Condensing, volunteered: fewer checks a
stage (two or three), and the keep choice's flicker, which rose with its share in 1.7a, arrives sooner.

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Assumed | The alternative, and what is known |
|---|---|---|
| The lightning slide was the aim model's doing | the head learnt which fights pay with hands whose far and still aim was worst | **not proven.** The other candidate is the head's five-second credit on damage paid as it lands. This run tells them apart: if the lightning climbs with the credit again under AIM3 (updates 50 to 130), it is the credit, and the save of update 50 is where the damage pay or 2.1's lesson is tried instead |
| The damage pay 0.005, taken at 1.0, as a step at update 0 (owner) | b1.2d itself moved taken 1.0 → 0.8 (one of five pay changes) and the owner's play test then read "clearly engaging more in fights"; 2.0a and 2.0c went zero-sum together with a much lower pay and fell | here the pay a point barely moves, so this run reads zero-sum nearly alone, but in the same updates as AIM3's ramp: a fall in the first 50 updates cannot be pinned on one of the two. Watched: frags a match-minute (the dry run at 0.8: 1.7) and the ledger's dealt and taken cancelling. `tests_ident2.log`: the ledger pays exactly these weights |
| AIM3 holds level alone at full strength | 2.0c was level at updates 10 and 30 with the blend at 0.18 to 0.68 | never trained at full blend with the old pay. Updates 40 to 50 and the check of 50 are that test, before the head gets any credit |
| 1.3b's recipe behaves the same in today's trainer | the head's code has since gained the weapon, keep and order parts | ✅ the dry run at full size: his step, both parts' sizes and their cosine as 1.3b's fifth dry run (the table below) |
| The teacher and the speed pay can go together | 1.6a did it, level, with the head's weapon part present | here without that part; item control slid 5% in 1.6a and is watched (megas and reds head to head) |
| The keep choice opens with the item rule's lesson already out | as in 1.7a | its flicker (trips 24 → 58 a player-minute by its update 90) comes with it; quiet re-decisions were 0.054 there, under the 0.08 alarm |
| Six things in one run | each opens alone, with a kept save and a check between | a fall is pinned to the stage it came in; any stage can be re-run from the mark before it |
| The checks under AIM3's end values from update 10 | he is checked on the aim he is moved to | as 2.0c |

**Pathologies watched from update 1** (every FLAG and MAJOR line read): a refused or unapplied `live.json` (MAJOR); any firing cost above
zero (MAJOR); a check under 40% (MAJOR, told at once); a part of the target's sum over 40 (rule 11); his step over 0.1; megas or reds head
to head 20% under the control's; frags a match-minute under 1.5; quiet re-decisions over 0.08; targets reached 30% under the start;
lightning in hand over 50% (reported, not acted on). Negative frags and lopsided games: Cypher's measures of each check.

**Weaknesses, volunteered:**
- It is a new network, not 1.7a with better aim. The checks against 1.7a's update 90 say how near it lands; 91.5% against b1.2d's end
  took 1.7a 470 updates, and this run has 310.
- The rail is not addressed. b1.2d already holds it 5% of the time (v0.6.0: 22%); nothing in 1.8a puts him where a rail shot is the right
  one. That is 2.1's work, and AIM3 only makes sure his hands can then learn it.
- Without the head's weapon part his weapon is the hands' alone, as in 1.3b. If 2.1's instruction is late, he has no slow reason for a weapon.
- One planned restart. A restart right after a save, with the optimizer, has been done many times; it is still the run's one seam.

## Built and tested before the go (2026-11-11; scratch folders only, nothing of a real run touched)

| | State |
|---|---|
| The start: b1.2d's end widened 980 → 1,053 (zero weights; `tools/b18_init.py widen`, new), the head added (`tools/head2_init.py add --add 1 --chrono-lo 1 --gate 0 --ctrl-src belief`), the keep choice added (`tools/keep_init.py add`); 1.3b's three anchors widened | ✅ `tests_start.log`: every weight of b1.2d's end unchanged, the 73 new input columns zero, the four new tokens shut, the head's target layer zero, no weapon part, no order; **0 actions differ** from b1.2d's end (400 frames, 8 seats, the new inputs random too) |
| `train.cmd` from 2.0c's by `make_files.py` (phase 1 and 2); the settings check against 1.7a's command | ✅ only these differ: the run, the minutes, the seven AIM3 names, `--gate-open`, `--head2-wpg 0`, `--pass-odds 0`, `--habit-p 0`, `COMBAT=0`, and until the restart `INTENT_SWITCH=0.02`, `WEAPON_OWN=0`. `start.ps1` runs it again and refuses on any other |
| The start's `live.json` (`start_live.py`: b1.2d's own file, checked against its end save's record, plus the head's, the keep choice's and AIM3's names at their start and `DMG_REWARD` 0.005); the trainer's own reader on it and on all 292 files the ramp will write | ✅ `LIVE ACCEPT: PASS` |
| The trainer at a fixed seed (six small runs; run again with the zero-sum start) | ✅ `tests_ident2.log` (`tests_ident.log`: the same at taken 0.8): damage taken weighs as dealt; it repeats itself to the bit; the damage pay changes nothing before the first learning step and the ledger pays exactly 0.005 against 0.0055; AIM3's end dials change the first update's actions (6%); the head's credit changes nothing before the first learning step and is played as written; no firing cost in the ledger; the optimizer's moments carried over the widened inputs |
| The real trainer applies the start's `live.json` before its first rollout; mid values of all seven dials written after update 1 are applied and are in the save's record | ✅ `tests_live2.log` (the zero-sum start) |
| Ten small updates with every dial stepped, then **the restart** (phase 2's two switches, the teacher and the speed pay out, the keep choice at 0.975), three more updates, a one-map check against b1.2d's end and against 1.7a's update 90 | ✅ `tests_smoke.log`. **Found and fixed:** the trainer's own update number starts at 1 again after a restart; the ramp read it, so every dial would have frozen at update 150. The ramp's clock is now the number of lines in `metrics.jsonl` (as the watcher counts). Also read there: the hands' weights on the order's and the map's inputs stay exactly zero |
| `ramp_18a.py` on fake files, through the restart (`ramp_test.py`; run again on the condensed schedule, 11-11 afternoon; the last stage is not in it yet) | ✅ `ramp_test.log`: each dial on its stage, the marks kept once, the clock on from 150 after the restart with the trainer's number at 1, a check under 40% a MAJOR PROBLEM with the clock not held, the lightning over half and a firing cost flagged |
| **The dry run of the head's opening at full size** (the graphics card, 10 updates, the credit 0 → 0.5 → 1 as 1.3b's fifth dry run, AIM3 at its start values; run before the owner's zero-sum word, so with damage taken at 0.8) | ✅ `tests_dry.log`: his step 0.032 to 0.041 (1.3b's dry run: 0.031 to 0.041); the hands' part of his target scores 21.6 to 22.6 (21.6 to 22.7); the head's part 0.07 → 2.0 (0.06 → 2.9); their cosine −0.06 to −0.18 (−0.16 to 0); the clip share under 0.10; **5.3 minutes an update**; in hand in games rockets 36%, lightning 39%, rail 4% |
| The zero point against 1.7a's update 90 (`zero_point.py`: the start, 200 games, the checks' settings, both seats under AIM3's end values) | ✅ `zero_point.log`: **11-189, 5.5%**, frag share 20.3%; the start owns the rail 32% of its time alive there. Against b1.2d's end no games are needed: the two answer alike |
| `start.ps1` (the start and `-Restart`), `stop_18a.ps1` (the trainer alone, by its own command line, only when the kept save of that update is the run's `policy.pt`) | ✅ written, parsed; their checks are the ones above. They run for the first time at the start |
| `tools/aim2_levels.py` with AIM3's columns | not done (a play setting; not needed for the run) |

**How it is run:** `start.ps1 -Minutes <n>`; at update 150 `stop_18a.ps1 -Update 150`, then `start.ps1 -Restart -Minutes <n>`; at the end `stop_18a.ps1 -Update 330 -All`. I do the restart and the end by hand while monitoring, on the card's word.

## After the run

The aim error tables of AIM3.md and the held-angle probe on the marks 50, 150 and the end, beside b1.2d's end; the report; then 2.1's
gates open on the end.

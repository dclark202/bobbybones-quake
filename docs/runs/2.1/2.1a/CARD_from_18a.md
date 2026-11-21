# 2.1a: the head opened once, in 2.1's form, from 1.8a's update 50

> **2026-11-13: 2.1 will start from 2.0d's end (list 20d), not from 1.8a.** What 2.0d does, what is deferred to 2.1 and what this
> build must change: [../PLAN_FROM_17A.md](../PLAN_FROM_17A.md), "Status 2026-11-13".

*2026-11-12 (owner, on 1.8a's progress: "the strategy head needs to be 'correct' when it opens otherwise it just strangles other weapons
but LG"; on the plan: "That looks reasonable, but I need to see the exact details"; "begin the build and give me an update when it is
ready to start"). The design: [../DESIGN.md](../DESIGN.md); what is built: [../INSTRUCTION.md](../INSTRUCTION.md),
[../SIM_PARTS.md](../SIM_PARTS.md), [../TRAINER_PARTS.md](../TRAINER_PARTS.md). The earlier draft of this card (gates without update
numbers, from 1.8a's end): [../CARD.md](../CARD.md).*

**NOT STARTED. No go is asked here.** Built on branch `b21` (worktree `BobbyBones-21`, uncommitted); the run starts from the repo's own
tree after the branch is merged (the data is there).

**Marks:** ✅ built and tested (the test named) · 🔧 built, not run · ⏳ not built · 🧪 measured in the run · ❓ the owner's to decide

**Started from:** 1.8a's save of update 50, "b1.2d under AIM3" (`data/sim_runs/duel_gru_1_8a/keep/policy_u50_18a.pt` + `opt_u50_18a.pt`;
list 18, 804 inputs; AIM3 at its end values, the head's credit never opened, the item teacher and the speed pay in place), brought to
**the input list 21** (`tools/inputs21.py convert`: 852 inputs, the hands' encoder the first 844, the brain the first 691; the 48
instruction columns at zero weights, the token "instr" shut) and given **the head's choice of an instruction** (`tools/head21_init.py
add`: the head's input part at zero weights, the scorer inside the head with its last layers at zero, its share 0), both at zero
effect, with update 50's optimizer. The league: 1.8a's three anchors (b1.2d's end, b1.1, v0.6.0's end) on list 21, and the start
itself as a fourth anchor, under no instruction **(decided here)**. The simulator: `sim/duel_env_ffa21.py`.

## The owner's page

| | |
|---|---|
| The goal | the head's choice becomes an instruction (a verb, a place, a point, a weapon), **taught by frozen moments and paid by the win chance alone**, opened once and in this form; nothing it replaces is taken away before it is shown to carry the weight |
| Length | 220 updates (the owner's schedule). The two-update trial: about 6.2 minutes an update at stage 1's dials (1.8a 5.4), so about 23 hours; ❓ the minutes to give `start.ps1` |
| What update 50 already has (nothing to do) | AIM3 at its end values; damage pay 0.005, zero-sum; win pay 0.33 for the hands; the item table; no firing cost |
| The hands' pay | unchanged: the pay table and their share of the win pay (the owner, 11-11: fading the hands' win pay is for after 2.1) |
| The head's pay | **the win chance alone** (`--ins-pay-win 1`, `HEAD_PAY_TRUTH=1`): its value for the instruction, the frozen moments' dV, the lesson's target and the pay on its own choices. No entry of the pay table reaches it. The OLD head's parts (1.3b's target scores) never get credit in this run (`H2_PG` 0 for the whole run): the instruction's rows do that job |
| The weapon asked for is binding | `INS_BIND=1` (owner, 11-12: "I think that makes sense"): while an instruction names a weapon he owns with ammunition, that is the weapon in his hand; "no weapon" leaves it to the hands. For as long as the instruction stands |
| Checks | every 20 updates, 200 games, against **the start (1.8a's update 50)**; every fourth against **1.8a's end (its update 190: the head in 1.3b's form, 85.5 to 88% against b1.2d's end)**; the extra one at update 10. Both seats under AIM3's end values. Never held: every check reported, one under 40% flagged at once |
| Read at every check | games won; megas and reds head to head; the weapon in his hand in view by range and weapon changes a minute (readouts, rule 12); how often the binding was not the hands' own pick; the head's picks by block of rows; the appraisals' skill; `best_by_win_vs_full` |

## The schedule (the owner's, 2026-11-12; 220 updates; every dial live and straight; nothing holds or steps back on its own)

| Part | Updates | Dial | From → to | The mark kept |
|---|---|---|---|---|
| **I, the stem** | 0 to 30 | `DRILL_INS_P`: a drill after a game's start (every verb, each with a weapon) | 0 → 0.25 (my proposal) | |
| | 0 to 30 | `DRILL_INS_RATE`: drills begun in the middle of a game, a second a seat (found by the two-update trial: drills after a start alone were 0.15% of a seat's time; 0.02 with 8-second drills is about 14%) | 0 → 0.02 (my proposal) | |
| | 0 to 30 | `BRANCH_P`: the frozen-moment rounds' share of the self-play matches | 0 → 0.15 (my proposal) | |
| | 0 to 30 | `INS_GATE`: the instruction's attention token | −12 → 0 (shut at −30 before) | |
| | 0 to 40 | `SPEED_PAY` (in games) | 0.125 → 0 | |
| | 0 to 60 | the lessons nothing plays from; **the head taught in shadow on every seat** (`INS_G` 0; the tick readouts every update) | on | **60** |
| **II** | 60 to 110 | `INS_G`: the seat's coin. On = the head's order every 0.2 s, never "none", the weapon named and bound | 0 → 1 | **110** |
| | 60 to 110 | `BRANCH_WPN_P` (weapon-only moments), `BRANCH_LONG_P`, `INS_LONG_W` (the 30-second window; a spam branch is always read over it) | 0 → 0.3, 0 → 0.2, 0 → 0.5 (my proposals) | |
| | 110 to 160 | `H2_INS_PG`: the game's pay on his own choices, by the win chance alone | 0 → 1 | **160** |
| **III** | 160 to 200, held to 220 | `SFADE`: the strategy inputs out of the hands | 0 → 1 | **220 = the end** |

**No dial of their own** (as update 50 played them, the whole run): the 8-second lock (`INTENT_HOLD` 8; it is in the ramp as a dial that
does not move, for the owner's schedule), the switch cost (`INTENT_SWITCH` 0.02), the item rule's lesson (`INTENT_TEACH_W` 1), "a held
weapon is choosable" (`WEAPON_OWN` 0). None acts on a seat whose coin is on (the audit in [TESTS.md](TESTS.md)); they act on a seat whose
coin is off (all of them in Part I, a falling share over 60 to 110) and on the league's seats. **No restart.**

Checks every 20 updates, 200 games, against the start and every fourth against 1.8a's end. **Reported, never held on:** at 60 the shadow
readouts (changes a second, "continue", how long an order would stand, entropy, agreement with the appraisals: settled or not); at 160
the head blanked against not (200 games); megas and reds against the control throughout. Kept with their optimizers: 60, 110, 160, 220
and every 20 between. The full-size trial before the go was **two updates** (owner: "1 or 2 is fine"); the run's own first ten updates
and its extra check at update 10 are the trial.

## The two questions (answered from the code)

**1. The 8-second lock. It does not act on a seat under an instruction; it needs no fade.**
- `sim/duel_env.py:7848`: `may = (self.intent == 0) | self.intent_done | (self.intent_t >= INTENT_HOLD ...) | self.intent_gone`: the lock.
- `sim/duel_env.py:7892-7896`: `f_ = who & (self.ins_v[:n] > 0) & (self.ins_tg[:n] >= 0)` ... `live, may = live | f_, may | f_`: a seat
  under an instruction with a target is read at once and the lock is bypassed. Every instruction with a place or a target has one
  (`:8534`: a place with no target becomes "the enemy's believed place").
- **The owner's ruling (11-12): "the head makes a decision every 200ms, that's its design and what should be built".** A seat whose
  coin is on draws anew at EVERY head tick (`sim/head2.py:960 ins_redo`, the one rule of the trainer `sim/train_duel_rnn.py:5181`, the
  checks' player `sim/head2.py:1417` and through it the server pass); "continue" is drawing the row he is on. Nothing holds an order
  between ticks: not the lock, not 1.7a's keep choice (it gated the redraw as built last night: removed), not a timer (my "one second"
  of this morning: removed). `ins_end` (done, failed, a wake) is now only a record.
- **"None" is not offered** (the owner, 11-12; `INS_NO_NONE=1`, `sim/duel_env.py:8842`): the row "none" is never valid, so every reader's
  one mask leaves it out; the head's weapon choice has no "none" entry at all (nine weapons masked to those owned with ammunition, the
  gauntlet always: `sim/head2.py:1062 ins_wq_logp`, `sim/duel_env.py` `wok`).
- The lock still acts on a seat under **no** instruction (the row "none", or a seat whose coin is off while `INS_G` is under 1), as
  in 1.8a: `INTENT_HOLD` stays 8 for the whole run. `KEEP_G` stays 0 (1.7a's keep choice is never opened).

**2. The switch cost and "a held weapon is choosable". Both act only on a seat under no instruction; both are live now; no restart.**
- The switch cost, `sim/duel_env.py:15101`: `reward += pay_now - INTENT_SWITCH * (sw_chg & (prev_int > 0) & ~in_run)`. As built last
  night it was charged on **every** change of target, the instruction's too: the hands would have paid 0.02 for a decision of the
  head's. That is a cost on the head's choice paid by the hands, and noise to them. **Changed (decided here):** `sw_chg` leaves out a
  change made by an instruction (`:15098-15100`); with no instruction it is the simulator as before (the suite's case 2). The head's
  own stream (the win chance) never saw it.
- "A held weapon is choosable", `sim/duel_env.py:7836-7837`: it only stops the OLD target choice from naming a weapon he holds
  (`choice` turned into "nothing"), and the instruction's override comes after it (`:7892`). The candidate rows do not read it: under
  an instruction he may be sent to a weapon he holds whatever it says.
- So neither matters once every seat is under an instruction, and both still shape a seat under "none". They stay as update 50
  played them (0.02; off) for the whole run (the owner's schedule gives them no dial: they act on no coin-on seat). Both are read only in `intend()` and in the pay,
  so both are **live names** now (`LIVE_VARS`; range 0 to 0.1; 0 or 1) and the ramp moves them: the restart is gone.
- The watcher's "A FIRING COST ABOVE ZERO ... intent_switch" line of 1.8a: in 2.1a's ramp the target-switch cost is its own line (it
  is not a firing cost), flagged only if it is still there after update 250.

## What is in, and where it comes from

| Part | State | In 2.1a |
|---|---|---|
| The instruction in the simulator, its 41 candidate rows of 64 numbers, the drills, the truth labels, the finish time, the wake, the pattern's moments | ✅ `tests_instr.py` under 1.8a's phase-1 settings: ALL PASSED (27 lines; off = the simulator of `c99cc02` to the bit) | `INSTR=1` from update 0 |
| **The binding weapon** (`INS_BIND`): one definition (`duel_env.ins_bind_act`) for the simulator's step, so for the trainer, the checks' player and the drills; `plugins/netpass.bind_weapon` for a server; the weapon key gets no policy gradient and no entropy bonus on a bound frame (1.7c's path `b_wd`, the one mask `head2.bound_mask`) | ✅ `tests_instr.py` case 9; `test_21_parts.py` (the recompute-equals-stored check with bound rows) | from update 0; it binds only where an instruction names a weapon |
| The switch cost not charged on an instruction's change; `INTENT_SWITCH`, `WEAPON_OWN` live | ✅ unit checks; `tests.py live`, `ramp_test.py` | from update 0; out at 220 to 250 |
| The instruction's token with its own live gate (`INS_GATE`); `--gate-open` leaves it and it leaves the other shut tokens (timers, space, targets stay shut: 2.0b) | ✅ `tests.py smoke` | 0 to 30 |
| One rule for redrawing a standing instruction (`head2.ins_redo`) | ✅ unit checks (the trainer's reading against the numpy one) | with the head's share |
| The map sense, the appraisals, the brain's two questions, the frozen moments, the long window | ✅ unit checks; `tests.py ident`, `smoke` | from update 0 as lessons |
| The head's choice inside the head, its lesson, the pay on its choice, the win-chance stream | ✅ unit checks; `tests.py ident`, `smoke` (the played-to-before KL) | `INS_G` 50 to 130, `H2_INS_PG` 150 to 190 |
| The start's two converters | ✅ `tests.py start` (0 of 44,800 actions differ, twice) | the start |
| Today's trainer with every 2.1 flag off = the trainer before the build | ✅ `tests.py old`: two updates' dumps equal to the bit | |
| His damage-rate table (`FIN_RATE`) measured on update 50 | see "Before the go" | the command's `FIN_RATE` line; ❓ re-measured at every kept mark: not wired |
| The pruning of the owner's ideas (`tools/run/branch_record.py`, `tools/run/prune_inputs.py`) | see "Before the go" | before the go |
| `plugins/duelbot.py` calling the instruction (the clock, the step, the candidates, the picks, `bind_weapon`) | ⏳ | no 2.1 network on a server before it |

## Which pay each network learns from

| Network | Learns from |
|---|---|
| The hands | the pay table (damage 0.005 zero-sum, items by the point, frags and deaths) + the win part (`WIN_ADD` 0.33), as update 50 |
| The brain | its own lessons (the enemy's place, stack and weapons; the two new questions): no pay |
| The head: the instruction's value, the frozen moments' dV (8 s and 30 s), the lesson's target, the pay on its own choices | **the win judge's change in win chance alone** |
| The head's older parts (1.3b's target scores, its own value) | his whole pay (`--head2-pay all`), **but they get no credit in this run** (`H2_PG` 0): they stay as update 50 has them. ❓ the owner's: `--head2-pay win` moves that value to the win chance too; it changes nothing that plays here |
| The appraisals, the map sense | the frozen moments' outcomes; the pros' fit as the map sense's start (what a place is worth: rule 12 allows it) |

Written into `metrics.jsonl` every update (`pay_of`) and into the watch log.

## Red team: what is hand-built or assumed, its measured alternative, the pathology checks

| Part | Assumed | The alternative, and what is known |
|---|---|---|
| Update 50 is the right start | the hands have AIM3; the head has learnt nothing | the lightning is already in his hand 55% of his time there (38% at 1.8a's start): 16 of 1.8a's 23 points came before any credit. The alternative is 1.8a's start (50 more updates, AIM3 and the instruction on the hands at once). The drills ask for every weapon in turn and the binding makes him hold it: whether that restores the others is read at the mark of 50 (weapon in hand, the drills' ledger by weapon) |
| The head's choice opens from uniform over the offered rows | its last layers are zero; the lesson (toward the appraisals' order) teaches every seat's readings from update 0, played or not, once the appraisals have seen 20,000 branches | at 240 branches a rollout and 3 rows a branch that is about 30 updates: before `INS_G` opens at 50 the scorer has had about 20 updates of lesson. If the appraisals' skill on dV is not above 0 at the mark of 50, the lesson teaches noise: read it before 50 |
| The binding weapon | the head's weapon is what he holds | never trained. A random weapon every second for the share of seats under the head early in stage 2. Watched: weapon changes a player-minute (the smallest run read 52 with the head's share forced to 1 on an untaught scorer), how often the binding was not the hands' pick |
| A standing instruction is redrawn after one second | my number | 1.7a's keep choice was the built alternative: untrained under an instruction. A learnt keep under instructions needs its own lesson: not built |
| The 80 updates of the head's opening | 1.3b's width | the lesson is steadier than a policy gradient; 80 is the cautious copy |
| The pay on his own choice after the lesson | the least stable term last, alone | PPO around the played log-probability; the 1.7c guard is one definition of the masked log-probabilities and the played-to-before KL in every update's record |
| The lock, the switch cost, the item rule's lesson and `WEAPON_OWN` stay as update 50 played them | they act on no seat whose coin is on | they do act on coin-off seats (all of Part I, a falling share over 60 to 110) and on the league's seats; the audit lists the remaining back doors |
| The strategy inputs out of the hands | built in 1.8a, never trained at full size (1.8a was stopped before it) | alone and last, 40 updates |
| The checks against update 50 under AIM3's end values | both networks were trained under them | as 1.8a's |
| His damage-rate table from update 50's games, fixed for the run | his aim under AIM3 does not move much | re-measuring at each kept mark is a tool call, not wired into the watcher: ❓ |
| The brain's stack belief has four bands | "seconds to finish" moves in steps | the pruning test on the finish-time group says whether it carries anything as it is |
| The league's seats play under no instruction | as 1.8a's league | he meets nobody who holds or spams by instruction but his own copies |

**Pathologies watched from update 1** (every FLAG and MAJOR line read): a refused or unapplied `live.json` (MAJOR); a check under 40%
(MAJOR, told at once); any firing cost above zero (MAJOR); the old head's credit above 0 (MAJOR); megas or reds head to head 20% under
the control's; frags a match-minute under 1.5; weapon changes a player-minute over 20; one block of rows over 80% of the head's picks;
the appraisals' skill on dV under 0 for 20 updates; a part of the target's sum over 40 (rule 11: the target's sum stays live for seats
under none); the lightning in his hand over half of his time (reported, not acted on). Negative frags and lopsided games: Cypher's
measures of each check.

**Weaknesses, volunteered:**
- 2.1's form has never trained. 1.3b's form is the one known gain (1.8a: 88% against b1.2d's end at its update 130) and this run
  sets it aside; the check against 1.8a's end every fourth check says whether the new form matches it.
- A game server cannot play a 2.1 network yet (`plugins/duelbot.py`), so there is no play test before that is written.
- Walking may not be silent in the simulator (SIM_PARTS.md): quiet movement cannot pay until that is measured and decided.
- The two-update trial (stage 1's dials at their end, the mid-game drills not yet in it): 13.3 GB of the card's 16 at the peak; update 2
  took 252 s of rollout and 370 s of learning (1.8a: 191 and 323); the rollout plays while the step learns, so an update is about
  6.2 minutes (the two updates' lines were 6.2 minutes apart; 1.8a 5.4); his step's KL 0.035 and 0.033 with a clip share of 0.35,
  as 1.8a's (0.033, 0.34). The mid-game drills have not run at full size.

## Before the go

| # | What | State |
|---|---|---|
| 1 | The simulator suite with the binding weapon, under 1.8a's phase-1 settings | ✅ `tests_instr_bind.log`: ALL PASSED |
| 2 | Unit checks (`tools/run/test_21_parts.py`) | ✅ 230 checks |
| 3 | `tests.py start`, `old`, `ident`, `live`, `smoke`; `ramp_test.py` | see `tests_*.log`, `ramp_test.log` and the report below |
| 4 | The export and `tools/netpass_check.py` on the start | see the report below |
| 5 | `FIN_RATE` measured on update 50 (the settings check first) | see the report below |
| 6 | The hold and spam probes on update 50 | see the report below |
| 7 | Branches recorded from update 50; the pruning on the finish-time group as its first case; then the owner's ideas | see the report below |
| 8 | The two-update trial at full size on the card: his step, KL, card memory, minutes an update, the drills' "doing" rate, the appraisals' first numbers | see the report below |
| 9 | Branch `b21` merged into the repo's tree | ❓ the owner's word |
| 10 | The owner's calls: the length; the mid-game drills and their rate (`DRILL_INS_RATE` 0.02); one second between redraws; the league's fourth anchor; `--head2-pay`; re-measuring `FIN_RATE` at the marks | ❓ |
| 11 | `start.ps1` (the settings check against 1.8a's command, `live_accept`, the start's `same`), `stop_21a.ps1` | 🔧 written and parsed; they run for the first time at the start |

## The report of the tests (2026-11-12)

See [TESTS.md](TESTS.md).

**How it is run:** `powershell -ExecutionPolicy Bypass -File docs\runs\2.1\2.1a\start.ps1 -Minutes <n>`; at the end
`stop_21a.ps1 -Update 220 -All`. Its row in `docs/RUNS.md` at the start.

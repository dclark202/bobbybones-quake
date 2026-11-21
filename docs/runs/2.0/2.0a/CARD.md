# 2.0a: the damage pay out, the stack priced by the judge

*2026-11-08 (owner): "paying for damage that only improves his win chance, or improves his control ... Or dropping pay by damage entirely.
Making deaths count for more, based on how much stack you're giving up, or what item control you give up"; "you don't need to follow my ideas
exactly ... Either test them or refine them to something more useful." The design: [design/PLAN_2.md](../../../design/PLAN_2.md); the family:
[README](../README.md). **Written 2026-11-08; nothing built, nothing started.** The owner's decisions: the last section.*

**Marks:** ✅ measured or already built · 🧪 to measure before the go · ⏳ to build · ❓ owner's decision

**Started from:** 1.7a's update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_end_17a.pt` + `opt_end_17a.pt`), the best network, widened to
today's 994 inputs with zero weights on 1.7b's four timer inputs (`tools/b17b_init.py widen-league`, as 1.7c: it answers as update 90).
Nothing of 1.7b's or 1.7c's training.

## The owner's page

| | |
|---|---|
| The one new thing | **damage is no longer paid by the point; what a hit does to his chance of winning is paid instead.** Live `DMG_REWARD` 0.0055 → **0.001** (a floor, owner 11-08; dealt and taken one price), `DMG_TAKEN_W` 0.8 → **1.0** (the floor zero-sum) and the judge's weight `WIN_ADD` 0.33 → **0.6** ❓ (sized by the two chip rules below), faded together in straight lines over updates 10 to 70 (`ramp_20a.py`), reported every update, never held or stepped back (rule 6) |
| What the judge pays (`sim/win_judge.py`, v0.6.0's fit) | the change in his chance of winning the game, every frame, from the true lead, clock, both stacks (a lasting part up to 100 each, a decaying part above) and the big three owned, times `WIN_SCALE` (19.4: a frag at 0:0 with ten minutes left = 1). Zero-sum between the seats; telescoping (a game's sum is its result less the chance at its start: nothing on the way can be pumped) |
| Stays | the flat frag +1 and death −1; the item table by the point (b1.2d's); the keep choice at 0.975 (learning, flagged: below ❓); the order shut as at update 90; the habit seats (`HABIT_P` 0.3); no firing cost; the fairness limits; `!aim default`; every input and lesson as 1.7a's command. **The weapon untouched** (owner): read as an outcome |
| Length | **the run window is 21:00 to 07:00 (owner, 11-08: "I'm getting tired of hearing my computer run all day"), for now the standing rule**: `--minutes 600` or what is left of the window at the start, about 130 updates at 4.5 min; the trainer ends itself at 07:00. The last check (about an hour on the check cores) runs past 07:00 unless it is skipped ❓ |
| Checks | every 20 updates, 200 games: against update 90 (the start and the last best: the control); every fourth against the long-term control (❓ 1.6a's end proposed: b1.2d's end is swept at 93%); Cypher's measures of every check (`tools/run/cypher_measure.py`); the ledger every update (`dmg_dealt`, `dmg_taken` must read 0 after update 70); the panel; the extra check at update 10 (the trial) |
| Expected | against update 90 near 50% through the fade, possibly under it for a while: a copy that plays for the stack beats one that plays for damage only once it can also leave a fight, and leaving a lightning gun is a skill he has never had to learn. What should appear: fewer fights ending in his death when out-stacked, more fights nobody finishes, first hits from a way out, the stack held after a red and a mega, the yellows taken when behind. His weapon may or may not move: against his own copy at equal aim the lightning gun is the best weapon inside 768 units whatever the pay |
| Not in this run | the death priced at the death itself (2.0b); position in the judge (2.0c); break off and the order (after); any weapon work |

## Why: what the pay says now, and after (1.7a's judge, ten minutes left, in frags of win chance)

The ledger at 1.7a's end: damage dealt +1.84 a player-minute, taken −1.55, frags +1.18, deaths −1.06, the win part net 0.01 (size 4.35),
items net 0. Damage is the largest pay he gets, 1.6 times the frags, paid as it happens; a trade of 100 for 100 pays **both** copies +0.11.

| Scenario | The judge at weight 1 | at 0.33 (today) | **at 0.6 with the floor (proposed)** | Flat damage today (0.0055 a point) |
|---|---|---|---|---|
| 100 damage on an enemy at 100/50 (he is at 50/0 after) | 1.62 | 0.54 | **1.07** | 0.55 |
| 100 damage on an enemy at 200/200 | 0.99 | 0.33 | **0.69** | 0.55 |
| 50 chip on an enemy at 125/0 | 0.32 | 0.10 | **0.24** | 0.27 |
| 50 chip on an enemy at 200/0 (the decaying part) | 0.96 | 0.32 | **0.63** | 0.27 |
| **His death at 125/0** (beside the flat -1) | -1.00 | -0.33 | **-0.60** |  |
| **His death at 200/200** (beside the flat -1) | -5.26 | -1.73 | **-3.15** |  |
| His death at 60/0 to an enemy at 150/100 | -0.53 | -0.17 | **-0.32** |  |
| He takes the red at 100/0 (beside the table's 0.40) | 1.86 | 0.61 | **1.12** |  |
| He takes the mega at 100/0 (beside 0.28) | 1.56 | 0.51 | **0.93** |  |
| He takes a yellow at 100/0 (beside 0.20) | 1.21 | 0.40 | **0.72** |  |
| He takes a yellow at 100/100 (beside 0.15) | 0.57 | 0.19 | **0.34** |  |
| He owns the rail (against not), both at 125/0 | 0.26 | 0.09 | **0.16** |  |
| A frag at 0:0 with 2:00 left (beside the flat 1) | 4.51 | 1.49 | **2.71** |  |
| A frag when 3 behind with 2:00 left | 1.37 | 0.45 | **0.82** |  |
| A frag when 3 ahead with 2:00 left | 0.56 | 0.18 | **0.33** |  |
| The leader's trickle, one ahead, 5:00 to 4:00 | 0.53 | 0.17 | **0.32** |  |

(`tools/run/judge_prices.py` ⏳ prints this table, the chip table and the losing fight from any judge file at any weight: the card's sizing and the refit's check.)

### Chip damage (the owner, 11-08: "if we want to encourage chip damage doesn't lowering damage on 200/200 enemies do the opposite?")

Yes at a weight of 0.5 and below, for the **first** chip on a full stack only; not at 0.6 and above. The judge's price of a chip rises as the
enemy's stack falls (the first 50 off a 200/200 is worth the least, the 50 that brings him near 100/100 the most), where the flat pay paid
every 50 the same. With the floor of 0.001 a point (owner, 11-08) every chip pays at least 0.05 whatever the judge says. By weight (the floor
included):

| Chip | Today | w 0.33 | w 0.5 | w 0.6 | w 0.7 | w 1 |
|---|---|---|---|---|---|---|
| 50 chip, enemy 200/200 to 183/167 | 0.27 | 0.17 | 0.23 | 0.27 | 0.31 | 0.42 |
| 100 chip, enemy 200/200 to 167/133 | 0.55 | 0.43 | 0.59 | 0.69 | 0.79 | 1.09 |
| the next 50, enemy 150/100 to 133/67 | 0.27 | 0.29 | 0.41 | 0.48 | 0.55 | 0.76 |
| the next 50, enemy 133/67 to 117/33 | 0.27 | 0.33 | 0.47 | 0.55 | 0.63 | 0.88 |
| 50 chip, enemy 200/0 to 150/0 (a mega holder) | 0.27 | 0.37 | 0.53 | 0.63 | 0.72 | 1.01 |
| 50 chip, enemy 100/100 to 83/67 | 0.27 | 0.27 | 0.38 | 0.44 | 0.51 | 0.70 |
| 50 chip, enemy 125/0 to 75/0 (a fresh spawn) | 0.27 | 0.15 | 0.21 | 0.24 | 0.27 | 0.37 |
| 50 chip by a 60/0 Bobby on a 200/200 enemy | 0.27 | 0.17 | 0.23 | 0.26 | 0.30 | 0.41 |
| the red at 100/0, table included (must stay under a spawn kill) | 0.40 | 1.01 | 1.33 | 1.52 | 1.70 | 2.26 |
| a spawn kill, the flat 1 included | 1.00 | 1.33 | 1.50 | 1.60 | 1.70 | 2.00 |

So the weight is sized by two rules on the judge in use: **(1) the first 50 off a 200/200 pays at least what it pays today (0.275), floor
included; (2) the red at 100/0, table included, pays less than a kill of a fresh spawn.** On v0.6.0's judge that is **0.6** (0.27 against
0.275; 1.52 against 1.60); 0.7 breaks rule 2 (1.70 against 1.70), 0.5 breaks rule 1 (0.235). After the refit (decision 3) the two rules are
applied again and the table is shown to the owner before the go: the number follows the rules, not the other way round. What the judge adds
that no flat price can: chipping a mega holder at 200/0 pays 0.63 (today 0.275), and each further chip on a stacked enemy pays more than the
last (0.27, 0.48, 0.55): Cypher's "the enemy at -50 changes the math".

### The losing fight (the owner, 11-08: "The problem is blindly committing to fights that he knows he will lose, just to juice the damage numbers")

**Measured, and 2.0a does not fix this one by itself.** He fights to the death at equal aim (he deals about his own effective stack before he
dies) against chipping 50 from a doorway and leaving; the margin is how much leaving beats fighting on:

| Bobby vs the enemy | Today: fight on | chip and leave | margin | 2.0a at 0.6: fight on | chip and leave | margin |
|---|---|---|---|---|---|---|
| 100/0 vs 200/200 (the weak side) | −0.83 | +0.40 | 1.23 | −0.90 | +0.27 | **1.17** |
| 125/0 vs 200/200 | −0.69 | +0.40 | 1.09 | −0.69 | +0.27 | **0.96** |
| 150/100 vs 200/200 | −0.63 | +0.42 | 1.05 | −0.83 | +0.31 | 1.14 |
| 200/200 vs 200/200 | −0.71 | +0.42 | 1.14 | −1.28 | +0.32 | **1.60** |
| 200/200 vs 125/0 (he loses the fight he should win) | −3.63 | +0.36 | 3.99 | −4.10 | +0.20 | 4.31 |
| An even trade of 200 for 200, nobody dies | **+0.22 each** | | | **0.00 each** | | |

What it says: **the judge prices a weak Bobby's death cheaply, and by game outcomes it is right to**: a 100/0 who dies loses the frag and
respawns at 125/0, better off than he was; what the enemy lost to his chip is credited to him. So on the weak side the new pay moves the
decision almost nothing (1.23 → 1.17), and at 125/0 slightly the wrong way (the chip's flat 0.275 was worth more than the judge's 0.22). What
2.0a does change: **the even trade pays nobody** (+0.22 each today: the pay that made two copies stand and trade), and **the stacked side's
death costs 1.5 times more** (a 200/200 who fights a 200/200 and loses: −0.71 → −1.28; the stack given up for damage, the owner's first point).

The weak side's losing fight is not a stack question: he has nothing to lose but the frag, and the pay says the frag is −1 whether or not he
did damage first. Two levers reach it, neither in 2.0a (one new thing a round):

| Lever | What it is | Why it reaches the weak side | Its risk |
|---|---|---|---|
| **The death counts more than the frag** (the owner's "making deaths count for more", taken literally) | the death's flat −1 → **−1.5** (a new live `DEATH_W` ⏳: today the ±1 are written into the simulator at two places, `sim/duel_env.py:13878` and `:13947`), the frag's +1 unchanged | at 100/0 vs 200/200 the fight-on row becomes −1.40 and the margin 1.67 (from 1.17): the one pay that makes *his own* death dearer than the enemy's frag whatever his stack. Negative-sum: in self-play every fight is bad on average unless won cleanly: Cypher's "the goal is not to lose" | passivity (v0.5.1's shape: both copies decline fights); sized by frags a match-minute. Not telescoping, so a game's pay sum depends on the path: the deaths are counted, not the result |
| **The fight odds into the head, and break off** (1.7b's parts) | the brain's P(he wins the fight that is on) (Brier 0.12 against 0.21 in 1.7b) read by the head; an order to leave | "knows he will lose" is a number he does not have at update 90; the pay only makes leaving worth it | 1.7b's own history: the order's kinds never moved under a pay that gave break off nothing |

**My recommendation:** 2.0a as written answers the first point (damage as the pay that made the lightning gun's trade the game) and is the
necessary floor for the second: with the trade bonus gone, a fight at level pays 0 and a death −1, so leaving is already the better answer
and the fight odds have something to act on. **2.0b is the death at −1.5 (decision 10), alone, from 2.0a's end**, judged by the weak side's
deaths and the margin above; the fight odds into the head after. If the owner would rather hit the weak side's fight first, 2.0a can be the
death at −1.5 alone on today's pay (a one-line dial, no judge work) and the damage swap becomes 2.0b: the two are separable and I would not
run them together.

## Why it addresses what the owner brought up

| The owner's point | The mechanism in 2.0a | Measured by |
|---|---|---|
| "paying damage far too much"; "the LG only behavior is likely because he gets the most pay for using it directly" | damage by the point is down to a floor (0.001: a fifth of today, zero-sum). A hit is worth what it does to the odds, so the steadiest stream earns almost nothing of its own; the trade bonus that paid both copies is gone | the ledger (damage terms at the floor); his weapon in view read as an outcome |
| "blindly committing to fights that he knows he will lose, just to juice the damage numbers" | **only partly, measured** (the losing fight, above): 2.0a takes away the trade bonus (+0.22 each for an even trade → 0) and makes the stacked side's losing fight 1.5 times dearer, but on the weak side (100/0 against 200/200) it moves the decision almost nothing: the judge rightly says a 100/0 has only the frag to lose. The lever for that is the death at −1.5 (decision 10, 2.0b) and the fight odds into the head | out-stacked fights taken (56% die now); deaths a minute while behind; the margin table re-read on the refit |
| "He doesn't value his own life" | a death costs the frag **and** the stack he had, by the judge: 4.15 at 200/200 against 1.6 at the spawn (at 0.6) | deaths a minute while behind in stack; out-stacked deaths 56% → toward the pros' 30% |
| "or the positions he holds" | the stack he holds pays nothing until it is spent, and costs when it is lost: holding a spawn he has timed is worth exactly the item it yields minus the risk. **Position itself is 2.0c**: the race into the judge | stack at the start of his fights; "in control" (his share of the next spawns) when ahead |
| "a fight in the open is probably 50/50 if both are using LG" | a 50/50 fight at level stacks now pays about zero in expectation; the pay says: change the odds first (a chip from range, an item) or do not take it | fights nobody finishes 38 to 49% → toward 64 to 71%; the weaker side hitting first 22% → toward 47% |
| "above ... running cycles to maintain item dominance, and deny the items" | the items' points are already zero-sum (denial pays twice); with the judge's weight up the red at 100/0 pays 1.5 in all, a yellow 0.9: the cycle is worth running when ahead, and a death that gives it away costs 4.15 | mega and red timing (0.8 s, 1.2 s) held; the enemy's share of the big spawns when Bobby is ahead in stack |
| "behind ... the yellows, or greens, and MAYBE a stolen mega"; "chip damage to cut away at your opponents stack" | a yellow at 100/0 pays 0.9 in all; a chip of 50 off a 200/0 pays 0.63 and each chip on a stacked enemy pays more than the last (the chip table); dying for it costs 1.6 | yellows taken by the player behind (53% at u90); first hits when weaker |
| "Not revealing your position for no reason. Not barreling past chokepoints" | not paid for directly (that would be shaping); they follow from a death that costs up to 4.15 and a fight that pays only when the odds say so. The fight odds and break off (1.7b's parts) come after, on this pay | deaths within 3 s of a sighting; the panel's damage from unseen |
| "making deaths count for more, based on how much stack you're giving up" | yes: the judge's stack part, which the flat death never had. The alternative form (a flat death term scaled by the stack, 2.0b) prices the same thing once more | the table above |
| "or what item control you give up" | partly: a dead player's items are the enemy's, and the judge sees the enemy's stack rise; the race itself (who is first to the next spawn) is 2.0c | 2.0c |
| "push the boundaries" | the weight ❓: 0.6 is the smallest that does not pay chip less than today and keeps a red under a spawn kill; 1.0 makes the game's result worth as much as all the frags of a game (9.7 against about 10), where v0.6.1 went passive, and pays a red at 100/0 more than a spawn kill | frags a match-minute as the alarm |

## The equilibrium

Every combat pay is now zero-sum between the two copies: frags, deaths, the judge's stack term, the items. A fight is worth only what it does to
the game: take it with the stack edge, turn a losing one into an escape (a break off that lives costs the enemy his frag and keeps the stack),
chip from safety when behind, hold the spawns when ahead. On the way: fewer even trades, fewer deaths out-stacked, a stacked Bobby pushing
harder, a slower game at first (frags a match-minute down from 2.32; the alarm is under 1.5, v0.5.1's 1.42). Nothing pays the lightning gun
for being steady any more; what pays rockets and the rail is the chip at range that changes the odds of the fight to come, and a fight at
range that nobody finishes. Whether that moves his weapon against a copy with equal aim is the open question, read, not steered.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The judge is v0.6.0's fit of 2026-10-28, frozen (300 self-play games, log loss 0.378) | it prices the stack as v0.6.0's lightning game valued it, eleven days and seven runs ago; the stack above 100 very high (50 off a 200/0 pays 0.96, 50 off a 100/0 0.42); rockets and the rail set to the lightning gun's worth by hand | ❓ a refit before the go on 1.7a u90's 80 recorded games (`cypher/`) with the pros' rows (`data/sim_runs/judge/pro_rows`) in the fit: `tools/run/fit_b.py`; kept only if the axioms hold and the held-out log loss is no worse | the prices table, before and after; the critic's EV and calibration during the run |
| The weight 0.6 | sized by the two chip rules on a frozen judge: the number moves with the refit | 0.33 (the minimal arm); 1.0 (the bold one); the rules re-applied after the refit | the ledger's sizes; the KL and entropy (a noisier pay raises both); frags a match-minute |
| b1.2d's rule "no pickup above 40% of a kill" | under the judge a kill's worth depends on the victim's stack (a 200/200 kill pays about 3.6 at 0.5, a spawn kill 1.5) and so does a pickup's; the rule is restated: **no pickup worth more than a kill of a fresh spawn** (the red at 100/0: 1.52 against 1.6 ✅ at 0.6; at weight 1.0 it would be 2.26 against 2.0 ❌) | | the ledger: items against frags by size |
| `DMG_REWARD` 0 | **a trap in the trainer** ✅ found: `if a.dmg_reward > 0` else the curriculum's 0.004 × max(0.25, close_p), so a live 0 means 0.001 to 0.004, not zero. **Not hit in this run**: the floor is 0.001 | the fix (0 means 0, unset −1) before any run that goes to 0 (2.0b) | `tests.py live`: the ledger's `dmg_dealt` at 0.001 a point exactly |
| What else `dmg_reward` scales | `STYLE_DMG` 0.5 (styled lives' extra damage pay), `BLIND_RL_DMG` 0, `SHOT_COST` 0, `HIGH_PAY` 0: all go to 0 with it; only the first was alive | none needed | the ledger's `style` term |
| Passivity | v0.5.1 and v0.6.1 on win-weighted pay: frags 1.65 → 1.42 a match-minute, the rail out of his hands; here the flat frag and death, the table and the damage floor (0.001 a point, zero-sum: owner, 11-08) stay | none | frags a match-minute under 1.5; nobody-dead fights over 75% |
| The late-game shape | a frag with 2:00 left pays 2.26 at 0.5, one when 3 ahead 0.28: a leader late is paid to protect the lead (v0.5.1's lesson); the flat frag keeps every frag worth at least 1 | | checks by game phase; frags in the last two minutes |
| The pay knows the truth | both stacks and places, by design (the pay is the owner's view); his inputs do not: the enemy's stack as he believes it (`EN_STACK`) | none needed | the brain's stack band Brier: he must estimate what the pay knows |
| The keep choice learning | it drifted into flicker twice when it learnt (1.7a after update 130, 1.7b); frozen (1.7c), it cannot adapt to a pay that changes what a fight is worth | ❓ learning, flagged at 0.08 quiet re-decisions a reading (1.7b's decision 8), or frozen | trips a player-minute, targets reached, quiet re-decisions every update |
| Variance | the judge's part already moves 4.35 a player-minute of size at 0.33; at 0.6 about 7.9 | 2.0b (the stack priced at the death only) | the advantage's spread; the updates' step |
| The self-play optimum | the lightning gun may stay the right weapon against a copy at equal aim whatever the pay (cause 1 of 1.7c's design) | the weapon is an outcome here; B-305 later | his weapon by distance and phase |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## Reevaluated, not inherited (owner, 11-08: "I have no allegiance to anything we've done before ... We shouldn't just use something because it exists")

What a pay for "the stack is the score" would be, built from nothing: **a potential**. A number V(s) for the true state of the game (lead,
clock, both stacks, both places against the items' clocks, weapons owned) that estimates his chance of winning, and a frame's pay = V(after) −
V(before). Any such pay is zero-sum, cannot be pumped, and does not change what the best play is, only how soon it is seen (Ng, Harada and
Russell 1999: potential-based shaping is policy-invariant for any potential of the state). The question is only **which V**. Each part below is
kept or dropped by that test, not because it exists.

| Part | Kept because it exists? | From nothing | My pick for 2.0a, and why |
|---|---|---|---|
| **The judge** as V (stack, lead, clock, weapons; hand-shaped axioms, fitted once on v0.6.0) | partly: it is the potential we have | a **learned V of the true state**, fitted on his games and the pros' with the axioms as monotonic constraints, position included (the race): the judge is a special case of it over the stack alone | **the judge for 2.0a, refitted (decision 3); the learned V is 2.0c.** Not for comfort: 2.0a tests the thesis (is damage the hindrance?) in 12 hours on dials, and the learned V takes a build; a thesis test on one dial set first is also the one-new-thing rule. If 2.0a says the thesis holds, the learned V replaces the judge, not extends it |
| **The flat frag +1 and death −1** | yes, from b1 | nothing: a frag is the potential's step (the lead changes; the victim to the anchor), so the flat pay counts it twice. v0.6.1 did without and went level, not worse | **kept at 0.5 as a floor, not a principle**: v0.5.1 and v0.6.1 are the evidence that the potential alone trains slower on one PC. Candidate for 2.0b: the flat frag down to 0.5 as the judge's weight goes up, so a kill's total stays about 1.5 and more of it is the stack |
| **The item table by the point** | yes, from b1.2d | nothing: the potential prices a pickup by its effect (a red at 100/0: 1.86 at weight 1) and the decay charges itself back through V | **kept in 2.0a** (one new thing; b1.2d's play test said the table did what was wanted); **a candidate to go in 2.0b** once the judge's weight carries the items. With both on, the red at 100/0 pays 1.33 at 0.5: within the restated rule (under a spawn kill) |
| **The hands' horizon** (`--gamma` 0.999, 25 s) | yes | 50 s (0.9995) to see an item cycle; or leave the cycle to the head's two-minute value | **unchanged in 2.0a**: the potential pays the stack *when it changes*, so the horizon matters less than before (a death's cost lands at the death, the item's at the pickup). Reevaluate after 2.0a on the ledger: if his value still misreads the cycle, 0.9995 is 2.0b's dial |
| **Damage taken 0.8** (`DMG_TAKEN_W`) | moot: with damage at 0 it prices nothing | | gone with the damage |
| **The checks' measure**: win rate against the start | yes, the standing rule | the owner's own standing note (B-280): "in control" for more of the game should replace frag share beside games | games won stay the gate (the one goal); **"in control" is added as a primary measure of every check in 2.0a**, from the control truth: his share of the mega and red spawns taken, by map. Frag share is dropped from the headline |
| **Pay from the truth, inputs from his senses** | yes | the same: a critic may know what the actor cannot (asymmetric actor-critic); fairness is about what *he* knows | kept, on principle |
| **Self-play against his own copy** as the opponent | yes | the league with the pros' habits in it (B-309), opponents under the pros' weapon table (1.7c's machinery): if the lightning gun is self-play's true optimum at equal aim, no pay moves it | **unchanged in 2.0a** (one new thing); the first thing to change if 2.0a fixes the fight decision and the weapon still does not move |
| **The judge's weight as a dial on top of the table** (`WIN_ADD`) | yes | one knob: how much of the pay is the potential, how much flat events | this is that knob; the card sizes it (decision 1) |

## The steps

| | Step | What it is | Done when |
|---|---|---|---|
| 1 | the trainer: no change for the damage swap | the floor 0.001 never reaches the trap; `tests.py live` runs the real trainer at the end dials and reads the ledger: `dmg_dealt` at 0.001 a point, the judge's part at 0.6. (If decision 10 puts the death cost first: live `DEATH_W` ⏳ at the two death sites, its range 0 .. 5, the ledger's `death` term at −1.5 a death) | the ledger matches the dials |
| 2 | the prices tool ⏳ | `tools/run/judge_prices.py <judge.npz> [--weight w]`: the table above | its numbers match this card's |
| 3 | the judge ❓ | keep v0.6.0's, or refit on 1.7a's games with the pros' rows (a measurement job: about an hour on the check cores; nothing runs now) | the axioms hold; held-out log loss no worse; the prices table read by the owner |
| 4 | the run files ⏳ | `make_files.py` (1.7a's command with `--run duel_gru_2_0a`, `--minutes`, `--keep-g 0.975`, the start's live values), `ramp_20a.py` (`DMG_REWARD` 0.0055 → 0.001, `DMG_TAKEN_W` 0.8 → 1.0, `WIN_ADD` 0.33 → the weight, updates 10 to 70, straight lines), `start.ps1` (the settings check against 1.7a's command, `live_accept.py` on the start's file and every file the ramp writes, the watcher with `CHECK_EVERY=20`, `CHECK_GAMES=20`, the trainer on `0xC03C3`, everything else on `0x3C3C`), `tests.py` (`start`, `ident`, `live`, `smoke`) | every test passes; logs beside this card |
| 5 | the start's identity ⏳ | the widened update 90 with the dials at their start values plays as update 90 (`tests.py start`, `ident`) | 0 actions differ |
| 6 | the owner's go | the decisions below, then `start.ps1 -Minutes <what is left of the window>` at 21:00 or after the refit | |
| 7 | the run | the ramp's lines every update; the extra check at update 10; checks every 20; one line an hour; flags at once (under 40%, frags under 1.5, a refused live file, `dmg_dealt` not 0 after 70); the 06:30 report | |
| 8 | after | the report with Cypher's measures and the prices table against what he did; 2.0b or 2.0c by the result ([PLAN_2.md](../../../design/PLAN_2.md)) | |

## The checklist

| | |
|---|---|
| built | `tools/run/judge_prices.py`; `make_files.py` (1.7a's command with `--run duel_gru_2_0a`, `--minutes`, `--keep-g 0.975`), `start_live.py`, `ramp_20a.py`, `start.ps1` (the length defaults to what is left until 07:00), `tests.py`; no trainer or simulator code changed |
| tests | `start` (the widened start answers as update 90), `ident` (the start's live file repeats the plain trainer to the bit; the END dials change nothing before the first learning step and the ledger is exactly the dials' arithmetic), `live` (the start file applied; dials written after update 1 applied by update 4), `smoke` (10 small updates at the END dials: no NaN, the floor in the ledger, a restart loads the optimizer, a one-map check finishes): their logs beside this card (`tests_*.log`) |
| level check of the start | the start is update 90 as it is (the dials at their start values): `ident` proves it |
| start | **`start.ps1` 2026-11-08 21:29**, 565 minutes (owner: "If you think you have something to try tonight try it"); the settings check against 1.7a's command: only `--run`, `--minutes`, `--keep-g` differ; `start.log` beside this card |

## The owner's decisions

*Taken for the start of 2026-11-08 21:29 (owner: "If you think you have something to try tonight try it. I want the report after it's done at 7, then we'll change things from there"): 1 the weight 0.6; 2 the floor 0.001 (owner); 3 **v0.6.0's judge, no refit tonight**: the last refit with the pros' rows (2026-10-29, `judge_v061_pro50r`) priced owning the rail below nothing (-0.21 to -1.25 frags) and had to be corrected by hand, which is why v0.6.0's judge has its weapons set by hand; a refit under time pressure would need the same correction unread. The refit is a daytime measurement for 2.0b, its prices table and weapon values read first; 4 the keep choice learning, flagged; 5 the fade 10 to 70; 6 1.6a's end; 7 the window to 07:00; 8 21:29; 9 the judge now; 10 the death at -1.5 as 2.0b.*

| | Decision | Where it stands |
|---|---|---|
| 1 | **The judge's end weight** | **0.6 recommended**, by the two chip rules (the first 50 off a 200/200 not paid less than today; a red at 100/0 under a spawn kill); at 0.5 the owner's objection holds (chip on a full stack 0.235 against 0.275), at 1.0 a red outpays a spawn kill and the game's result outweighs the frags (v0.6.1's shape). Re-sized by the same rules after the refit; the table shown before the go |
| 2 | Damage: zero or a floor | ✅ **a floor of 0.001 a point** (owner, 11-08), zero-sum (`DMG_TAKEN_W` 1.0): every chip pays at least 0.05; the trainer's 0-trap is not touched |
| 3 | The judge: v0.6.0's frozen fit, or a refit | **refit recommended**, on 1.7a u90's 80 recorded games with the pros' rows, kept only if the axioms hold and the held-out log loss is no worse; about an hour on the check cores. **In the window**: 21:00 the refit, about 22:00 the start (`--minutes 540`). The alternative is the full ten hours on v0.6.0's judge tonight and the refit another evening |
| 4 | The keep choice | **learning recommended**, flagged at 0.08 quiet re-decisions a reading; frozen is the fallback at a restart |
| 5 | The fade | **updates 10 to 70 recommended** (about 4.5 h; the checks at 10, 30, 50, 70 see it at a quarter, a half, three quarters, done); 60 updates to settle before 07:00 |
| 6 | The long-term control | **1.6a's end recommended** every fourth check (b1.2d's end is swept at 93%) |
| 7 | Length | ✅ **the window 21:00 to 07:00** (owner, 11-08): about 130 updates; the last check runs to about 08:00 on the check cores unless skipped ❓ (recommended: let it run; it is the run's final number) |
| 8 | The start time | yours, inside the window, once steps 2 to 5 are built and tested (the tests run the trainer for a few minutes: daytime noise, short) |
| 9 | The instrument | **the judge now recommended**, the learned potential of the true state built by day as 2.0c: ten hours on dials answers whether damage was the hindrance before a two-day build commits to its replacement's form |
| 10 | **The death at −1.5** (the frag +1): in 2.0a with the damage swap, as 2.0b alone from 2.0a's end, or as 2.0a alone first | **2.0b, alone, recommended**: it is the one lever measured to reach the weak side's losing fight (margin 1.17 → 1.67 at 100/0), and it is negative-sum, so it must be seen on its own (frags a match-minute is its alarm). Running it with the damage swap would leave a slide unattributable. If the weak side's fight is the first thing you want moved, swap the order: the death cost tonight (a one-line dial ⏳ `DEATH_W`, no judge work), the damage swap as 2.0b |

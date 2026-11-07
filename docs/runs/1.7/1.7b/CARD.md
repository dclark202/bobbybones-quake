# 1.7b: the combat order again, rebuilt around Cypher's fight decision, from 1.7a's result (update 90)

*2026-11-06 evening (owner): "what would you propose differently for 1.7b? It can be rough at first and then refined once the checks
are all in. Cypher is arguably one of the top 3 quake players ever and has been consistently top tier in this game for more than 20
years. So if there's a person to model bobby's behavior after, it's him. We can take his word as gold"; "write up a start of a card for
1.7b"; "zero sum damage is good"; on the yellow armors' timers: "he actually is already very good at timing yellows I've found. but it
can't hurt, as long as it doesn't increase the latency too much I don't see why not to add it." 1.7a's result is its update 90 (owner,
11-06: "That has JUST the choice redesign and no rule redesign. We can build from there"). The sources: [Cypher set against Bobby](../../../design/CYPHER.md),
[1.7a's postmortem](../1.7a/POSTMORTEM.md). **A start, to refine once the checks are in. Nothing built, nothing run; the run starts only
on the owner's command.***

**Started from:** ❓ 1.7a's result, the save of update 90 (`data/sim_runs/duel_gru_1_7a/keep/policy_end_17a.pt`, the same file as
`policy_90.pt`) with its optimizer (`opt_end_17a.pt`): the keep choice at full share, the order never asked (share 0, its token shut).

**Marks:** ✅ known or decided · ⏳ to build · 🧪 to measure · ❓ owner's decision

## In short

1.7a's keep choice won games (63% against 1.6a's end); its order was learnt away before the hands could carry it out. 1.7b asks the order
again, built around what Cypher says decides a duel: **who wins a fight is known before it starts, from the two stacks; ahead, take the
fight; behind, do not lose it.** The order gets the brain's honest guess of that (the fight odds); the hands learn to carry orders out
before the head is judged on them; a KL to the pros' order keeps the rare kinds alive through the run (AlphaStar). Two dials Cypher
argues for open first: the damage pay zero-sum, and the yellow armors' timers.

The schedule as recommended (11-06 evening; ❓ the owner's decisions below):

| Updates (1.7a: 5.7 min an update) | What | Dial |
|---|---|---|
| 0 | 1.7a's update 90 given the yellow timers (inputs at zero weight), the fight odds readout (a lesson only) and the order's new parts at zero effect: it plays as 1.7a's update 90 (an identity check) | ⏳ |
| 0 to 20, held to 30 | **the damage pay zero-sum** ✅ (owner): damage taken from the enemy weighs as much as damage dealt; seen alone at the checks of 10, 20 and 30 | live `DMG_TAKEN_W` 0.8 → 1.0 |
| 0 to the end | the fight odds lesson (its own layers; nothing else moves by it); the yellow timers learnt from zero | |
| 10 | the trial: the first check | |
| 30 to 60 | **the hands learn the order**: the order asked at the rarer start's rates (the pros' fit, the new kinds 4.5 times rarer: 47% at full share in 1.7a's level check), the head's order part frozen (not learning), the hands' order token opened | live `CMB_G` 0 → 1, `ORD_GATE` −12 → 0; ⏳ `H2_OPG` 0 |
| 60 to 120 | **the head learns the order**, with a KL to the pros' fit held all the way | ⏳ `H2_OPG` 0 → 1; ⏳ `ORD_KL` ❓ |
| 120 to the end | every dial held | |
| Out (1.7a had them) | the pointer's scores on his targets and way (likely the flicker's source after update 140); the fire push (nothing measured) | `PADD` 0, `FADD` 0, `H2_FPG` 0 |
| Length | ❓ about 150 updates (about 14 h at 1.7a's 5.7 min): 30 updates of the whole order held; the 12 h default (about 125) ends as the last phase does | `--minutes` |

## Why: what Cypher says, what 1.7a showed, what the checks found

| Cypher | 1.7a (postmortem) | The checks (2026-11-06: 1.7a's update 90, 80 games, ten maps; [CYPHER.md](../../../design/CYPHER.md), "The checks") |
|---|---|---|
| Stack math decides fights: fight with 30 to 50% more, avoid otherwise | the order kinds read their context alone; nothing tells the head who would win a fight | the bigger stack wins the fights where someone dies: pros 78%, Bobby 85% (read once a second, as the pros' rows) |
| Out of control, try not to lose; never give away a frag; corridors with a way out; damage while backing off | break off ended at an item and died first (arrivals 0 or 1 in five updates from update 170) | **out-stacked (under 0.67), Bobby dies in 56% of his fights and gets away from 38%; the pros die in 30% and get away from 64%**. The weaker side hits first in 47% of the pros' fights, 22% of his |
| Where and when to hit, not how; plan ahead | the brain's pass odds learnt (Brier 0.080 against 0.186); cut off and spam judged before the hands could do them (on a spam order he went to the spot and did not fire) | |
| Fights for damage, not kills, is the strong aimer's trap | the damage pay pays both players for a trade (`DMG_TAKEN_W` 0.8) | the trade bonus: 0.37 a player-minute, about a third of what his frags pay; in fights where he takes 30+ damage his lightning hits 56% (the pros 37%): both copies stand and trade |
| Rotations, timing out of control | | the mega taken a median 0.8 s after its spawn; the red armor 1.2 s, the yellows 6.3 s (53% by the player behind in stack); there: the mega 5% of the time (pros 7%), the red 17% (11%), the yellows 29% (15%): the yellows partly by choice (a yellow does little for a full stack) |
| | | the game's switch waits for the reload as the simulator does (rail then lightning 1.95 s in the game, 1.925 s simulated): not why he holds the lightning gun (B-302); his rockets hit 49% (pros 36%), his lightning as the pros', the rail unused (40 shots in 36 games) (B-303) |
| | | 45% of the pros' start moments have one player 100 or more ahead: practice from behind is there already (B-310 dropped) |

## The parts

| Part | The problem | What 1.7b does | Build |
|---|---|---|---|
| **1. The fight odds** (the brain predicts) | the head decides engage or avoid with no number for who would win | a readout on the brain's state and his own stack and weapons, like the pass odds: at each head tick, the chance that the next fight (damage both ways within a few seconds, as B-304 counts it) ends with the enemy dead first, him dead first, or neither; labelled in hindsight from the rollout, never pay, never a truth input. Read by the order's kinds (their context) and the keep choice | ⏳ (`sim/passodds.py`'s pattern; its truth from the simulator's damage and deaths) |
| **2. Break off as "try not to lose"** | break off ended at an item, so it competed with the item plan and its arrivals fell to nothing | break off's candidates as 1.7a's (ways out, a teleporter, a health or armor item away from the enemy's predicted places); **it is reached when for 1.5 s neither has seen the other and no damage has gone either way** (his senses only: the arrival is one of the keep choice's inputs), keepable (an arrival, 1.7a's kind), so living through the fight is the order done | ⏳ ❓ the 1.5 s |
| **3. The hands before the head** (postmortem cause 1) | the head saw orders fail while the hands read them at ×0.00001 | 30 to 60: orders drawn from the frozen start (the pros' fit, rarer) with the token opening; the head's order part does not learn (a new dial, `H2_OPG`, the order's share of the head's term); 60 on: it learns | ⏳ `H2_OPG` |
| **4. A KL to the pros' order through the run** (postmortem cause 2; AlphaStar) | no entropy and a rare start: nothing held the rare kinds up | a KL from the head's kind and pointer odds to the fitted start's (a frozen copy of `order_fit.json`'s layers), on the frames the order is read, at a live coefficient; the head can leave the pros' shape where it pays, but not drift to zero by noise | ⏳ `ORD_KL` ❓ its size |
| **5. The damage pay zero-sum** ✅ (owner) | a trade nobody wins pays both, and a break off forgoes it | `DMG_TAKEN_W` 0.8 → 1.0 over updates 0 to 20 (live) | ✅ a dial |
| **6. The yellow armors' timers** ✅ (owner: if the latency allows) | the mega and the red armor have "known taken" and "how long ago" (since v6); the yellows have none, and the head reads only his own pickups' clocks | for each yellow (two on Blood Run): known taken (he took it, heard it taken, saw its place empty) and the seconds since, against its 25 s (`it_t` from 2 to 4 columns, the heard error of `SENSE_MINOR` as for the mega); 4 inputs at the end (`sim/widen_obs.py`, zero weight); the head's inputs also take the four "memory" timers (heard, not only his own). The plugins keep them (`note_take` already hears the pickup) | ⏳ ❓ the brain's race and "in control" for the yellows too (more build, B-307) |
| **7. The keep choice's quiet flicker** | re-decisions out of contact with nothing heard rose 0.030 → 0.054 a reading by update 90 (0.125 by the end) | 🧪 watched from update 0; ❓ a KL to its start (the soft lock) on quiet readings only, if it climbs | ❓ |

**What stays from 1.7a:** the keep choice as at update 90; the order's kinds (the target as chosen, cut off, spam, break off), its
candidates and pointer, the pass odds, the hands' 10 order inputs and token, his weapon part reading the order; rule 11's decay on
every sum. **Not in 1.7b:** the weapon as a held choice (B-305: 1.7c, the order's argument); the ways (B-301: 1.8).

## The latency (the owner's condition for the timers)

The servers' frame is about 14 ms of 25 ([guides/FRAME_BUDGET.md](../../../guides/FRAME_BUDGET.md)). The timers are four numbers from
arrays the plugin keeps already (the pickups it hears): a few array operations a frame, and the network's first layer 4 columns wider
(990 → 994, under 1%). The fight odds and the KL are the trainer's only: the servers' forward pass does not run the readouts (🧪 to confirm
for the head's input). 🧪 Measured before any deploy: `DUEL_TIMING` on a private server, the frame's median and late share against 1.6a's.

## The checks

200 games every 20 updates against 1.7a's update 90 (the control), every fourth against b1.2d's end, an extra one at update 10; each
seat at its own settings. **Cypher's measures in every check** (`tools/run/cypher_measure.py`, the same rule as for the pros): his
fights by the stack ratio (deaths and escapes when out-stacked; who hits first when weaker), deaths a minute while behind, the big items'
times after a spawn, his weapon by the fight's phase. Every win rate reported; under 40% flagged at once; never held or stopped (rule 6).

## Watched and judged by

| Measure | Wanted |
|---|---|
| Win rate against 1.7a's update 90; against b1.2d's end | level or better through 30 to 60 (the hands learning); better after |
| **Out-stacked fights: he dies / gets away** (56% / 38% at u90; the pros 30% / 64%) | toward the pros |
| The weaker side hits first (22% now; the pros 47%), and how those end | toward the pros |
| The fight odds' Brier against its base rate | well under (the pass odds: 0.080 against 0.186) |
| p by kind against the pros' shares (87.7 / 3.6 / 4.7 / 4.1%), arrivals by kind | no kind at zero; break off arrivals up |
| A spam order fires; a cut off makes the first hit | up through 20 to 50 |
| The trade bonus gone; frags a match-minute (2.32 at u90); the enemy's share of his targets | no slide into passivity (v0.5.1's sign) |
| Quiet re-decisions (0.054 a reading at update 90), trips, targets reached | no climb |
| Big weapons owned; his weapon by phase and distance; the mega and red first | hold |

## The equilibrium

With the damage pay zero-sum every combat pay is zero-sum: a frag, a death, damage, items, and the win pay on top. In self-play a fight is
then worth only what it does to the frags and the game: a trade nobody wins pays nobody, so the best answer is Cypher's: take the fights
the stacks say you win, turn the ones they say you lose into an escape (a break off that lives costs the enemy his frag), chip from
safety when behind. The fight odds make that cheap to learn (the brain's number, honest by its lesson); the KL keeps the pros' kinds tried
while the value learns which pay. On the way: fewer even trades, more breaks off when out-stacked, a stacked Bobby pushing harder.

## Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The fight odds' "fight" (damage both ways within a few seconds) and its horizon | hand-set, as B-304's rule | the next frag or death alone | its Brier; its pull in the kinds |
| The fight odds learn P(win given a fight happened), not P(win if he engages) | a selection effect: his own choices shape the label | the head's value alone | engage rates by the odds against the pros' |
| Break off reached at 1.5 s with no sight and no damage either way | hand-set | at a way out or an item (1.7a) | break off's arrivals and the deaths after |
| The hands' phase with the head frozen (30 to 60) | assumed: the hands learn faster than the head judges | 1.7a's together | the checks 30 and 50 (the rarer start read 47% untrained) |
| The KL to the pros' fit, its size | AlphaStar's; the size a guess until measured | none (1.7a) | p by kind; the KL's own size; the checks |
| The pros' fit itself (part 9's labels, rarer start) | measured on the pros (held-out log loss 0.442 against 0.477) | refit with the fight odds as a context number | the level check |
| Zero-sum damage | the owner's ✅ | 0.8 (b1.2d's, to make him fight) | frags a match-minute; the enemy as his target |
| The yellow timers' error (heard: `SENSE_MINOR`'s) | as the mega's since v6 | exact | none: perceived |
| `PADD` and the fire push out | from the postmortem (not separated) | 0.3 / 1 | quiet re-decisions; mid-range rockets |
| Rule 11: every sum of two learned outputs decayed (`H2_L2`) | the owner's rule | | each part's size; a flag over 40 |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## The owner's decisions

| | Decision | Recommended (11-06 evening), and why | |
|---|---|---|---|
| 1 | the start | ✅ 1.7a's update 90 ("We can build from there") | owner, 11-06 |
| 2 | the damage pay zero-sum | ✅ ("zero sum damage is good"); ✅ over updates 0 to 20, held alone to the check at 30 (owner: "yes"): it changes what every fight is worth, so it is seen on its own before the order learns on top of it (the slow-openings rule) | owner, 11-06 evening |
| 3 | the yellow timers | ✅ if the latency allows (four inputs: the head cannot see a yellow's timer today); ✅ the brain's race and "in control" for the yellows later (owner: "yes"): half the yellows are taken by the player behind in stack, so their wait is partly by choice, and he times them well already (owner) | owner, 11-06 evening |
| 4 | the fight odds (part 1) | ✅ **yes** (owner: "yes"): out-stacked he dies in 56% of his fights, the pros in 30%; the head has the raw stacks but no number for who wins. A lesson only, read from zero weight (the start plays as u90); the pass odds showed the pattern works (Brier 0.080 against 0.186). Its weakness (the chance of a win given a fight, not given a choice) is the head's value's to judge | owner, 11-06 evening |
| 5 | break off reached by living through it (part 2) | ✅ **yes, at 1.5 s** (owner: "I'm mostly there, a bit skeptical about the exact set time, but I suppose we need one"; the time a red-team row) with no sight and no damage either way: the order's success is the frag not given; from his senses only, so the arrival is fair as an input; the exact number matters little, the keep choice decides what follows | owner, 11-06 evening |
| 6 | the hands first, the head frozen 30 to 60 (part 3) | ✅ **yes** (owner: "yes"): the postmortem's main cause (the head judged orders the hands could not read; the chance of an order fell fastest then, 2.1% → 0.43%). Cost: some games in that phase (the rarer start read 47% untrained); judged by spam orders firing and cut offs making the first hit | owner, 11-06 evening |
| 7 | the KL to the pros' order (part 4) | ✅ **yes, through the whole run** (owner: "yes"; his question: does it bring more rockets and rail? Not directly: it is on the order's kinds and points, not his weapon; see B-305); its size from the first updates (the weight where its pull equals the pay's at a small divergence), a live dial logged every update; a fade only in a later run, once the order has won games | owner, 11-06 evening |
| 8 | the keep choice's quiet KL (part 7) | ✅ **not now** (the owner left it to the recommendation: "no idea"): 0.054 a reading at u90, the save that won 63%; the climb came after u140 with `PADD` and the order, both out. Flagged at once if it passes 0.08 a reading (where 1.7a's slide began) | owner, 11-06 evening |
| 9 | the length and the start | ✅ about 150 updates (about 14 h) (owner: "That's fine"); the start on the owner's command once built and tested | owner, 11-06 evening |
| 10 | the weapon as a held choice (B-305: the head picks the weapon to hold five times a second, the simulator presses the key, a KL to the pros' weapon by situation) | ❓ **1.7c, from 1.7b's end** (recommended): one new thing a round (1.7a's lesson); 1.7b's zero-sum damage alone may move his weapon (the trade bonus pays the lightning gun's steady stream), and its checks will show how much; the order's hands phase must work first. The alternative: a phase of 1.7b after update 120 (a longer run, the two not told apart) | |

## The result

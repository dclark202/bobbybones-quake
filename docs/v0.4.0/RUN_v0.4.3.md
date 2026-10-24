# v0.4.3 on one page: the strategy head (DRAFT)

*2026-10-22: **proposed**, after v0.4.1 works (names, the owner, 2026-10-22 night: v0.4.0 the brain's pretraining, v0.4.1 the brain
connected, v0.4.2 "the blending out of the old belief network while inserting the brain network", with what was called v0.4.1
before: the strategy head). Before it: [RUN_v0.4.2.md](RUN_v0.4.2.md) (the old belief faded out) (numbers, the owner, 2026-10-23: "Can we just make these separate numbers: v0.4.2a -> v0.4.2; v0.4.2b -> v0.4.3"; what was v0.4.3 and on is v0.4.4 and on). Design: [BELIEF_LOOP.md](BELIEF_LOOP.md).*

*2026-10-23 evening: the old belief's fade is v0.4.2, [RUN_v0.4.2.md](RUN_v0.4.2.md) (built and tested on the CPU; start Sat on the owner's go). This card, the head, is v0.4.3: build Sat-Sun, start Sun afternoon if v0.4.2 passes. The goal of v0.4.x (owner, 2026-10-23): **pay by win chance** as the only game pay ("there is no tuning, you just pay for the win it figures out the rest"); the brain and the head are what make it possible; the shaping pays are scaffolds, recalibrated if badly off and then faded (below).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The two versions, each started and checked on its own (one change at a time)

| Step | What | Pass before the next |
|---|---|---|
| **v0.4.2: the old belief out** ([RUN_v0.4.2.md](RUN_v0.4.2.md)) | the cross-fade: the old rule-made inputs (the extrapolated belief, ~20, and the stack filter, 6) times (1 − g) as a gate g opens over hours; **the raw sensed facts stay** (where and when he last saw or heard the enemy: the owner, 2026-10-22, "yes that seems right to me"); the brain's new outputs from v0.4.1 (zones, where he will be in 1/2/4 s, what he is going for, when he appears, the item race) join the `belief` token once they pass their own readiness test; the old rule's readers inside the simulator (the legs' look point, the hunt's target) move to the brain | games ≥ level against v0.4.1's end; the decision report's reading rows moving |
| **v0.4.3: the strategy head** (this card) | below | the decision report's item rows moving |

## The strategy head

| Part | Detail | State |
|---|---|---|
| **The brain's new outputs, read by the head** (owner, 2026-10-23: "The hands handle what to do *now*, the predictions drive strategy") | where the enemy will be in 1/2/4 s, what he is going for, when he appears, the item race: inputs of the head, not the hands' token; each joins after its readiness bar | ❓ |
| **"In control" (B-280; the owner, 2026-10-23: "It's a very common way of talking about quake and would resonate well with anyone looking deeper into his structure")** | a brain readout 0..1: his share of the next two mega/red-armor spawns, labelled after the fact (who took them; like the brain's other readouts, learnt from the truth, read from his senses only, never a pay); read by the head; beside it, control from the value: his win chance beyond what the score and clock give. Shown in the decision report (does he fight when in control, back off when not) and as a timeline in play-test reports | ❓ |
| **The small slow head** | reads the brain (its memory and its answers), his own stack, item timers, score and clock, the hands' memory (no gradient); a GRU of 256 ticking every 0.2 s with the brain; acts by a plan (64) into the hands' memory and a bias on the intention head's choice, both starting at zero (an exact start, proven by a test) | ❓ |
| Size | ~0.6 M weights (v0.4's earlier candidate head: ~7 M); grows only on a measured need | – |
| On a server | well under 1 ms a tick; the head added to the plugins' forward pass | ❓ |
| The head's horizon | a goal choice pays off 30–60 s later: the head learns from the two-minute value output (γ 0.9998), not the main ~25 s one, or it undervalues timing plays | ❓ |
| The blind-fire exemption on "will be" (owner, 2026-10-23: "it probably should be 'will be'") | v0.4.2 waives the out-of-view shot cost where the brain believes the enemy *is*; v0.4.3 extends it to where the brain predicts he *will be* in 1–4 s (the ahead outputs), with its equilibrium stated: still a cost waived, never a pay | ❓ |
| A start from the pros (only if needed) | the pros' next goal by situation (mega when the enemy is far, back off when weak) as a light prior on the head's bias, fading like the item rule; added only if the head is slow to find these by winning. The owner is wary of copying the pros' choices (HAND_TEACH): measure first | ⏸ |

## Rule-made strategy the head takes over (the owner, 2026-10-22: "Is there any other parts of him like this that might need revisiting?")

*Timing (the owner, 2026-10-22): "those should be included eventually, that's probably at least v0.4.1 probably later" (said when the head was called v0.4.1): with the head at the earliest, more likely a later v0.4.x once it has shown it chooses well.*

| Part | Now | With the head |
|---|---|---|
| The item rule (the intention teacher, never under 10%) | a hand rule nudges which item he goes for, forever | its floor faded to zero as the decision report shows the head choosing well |
| The hunt (`HUNT`) | a rule sends his way toward where he believes the enemy (reads the readout from v0.4.0) | whether to hunt is the head's choice |
| Item pays (pickups, the big-item order, item loss) | hand-shaped values of items whatever the situation | lowered step by step as the head learns their value from winning (the item-pay review of 2026-10-17 belongs here) |
| The view's pull toward level (B-275) | with no enemy in view his pitch eases back to level (0.95 a frame): a crutch of 2026-10-03 that stops him holding a look up or down out of sight | phased out regardless of the drift measure (owner, 2026-10-23: "I think it's done its part"; "Let's just plan to phase it out regardless"): measured (RESULTS 2026-10-23 15:30), then a live factor 0.95 -> 0.98 -> 0.99 -> 0.995 -> 1.0, about 2 h a step, the control checks as usual, the plugins in the same batch |
| Item timers (his own pickups) | rule-kept clocks: fair, a person keeps them too | kept; the enemy's side ("when is mega back after he took it") into the readout only if the report shows timing mistakes |

## What it should do

| Situation | The head's bias |
|---|---|
| Strong, the enemy weak and predicted near | toward "the enemy" as his target |
| Weak, the enemy strong | toward the items the enemy is not going for, away from his predicted path |
| The enemy going for mega, he is strong | contest it; weak: take the red armor across the map |
| An item about to spawn, the enemy far | be there on time |

## Targets: the decision report (the owner, 2026-10-22: "whatever we start doing in v0.4.x needs to target these findings")

| Row (v0.3.10's end against v0.3.9's end, 80 whole games, `data/decision/v0310_end.txt`) | Baseline |
|---|---|
| Presses in when far behind (gap < −75) / dies within 10 s | 36% / 61% |
| Presses in when far ahead (gap > 75) / the enemy dies within 10 s | 61% / 60% |
| Closing against the gap (slope, u/s per 100 points) | 30.9 (v0.3.9: 26.7) |
| Mega and red respawns: waiting / on time / late / **the enemy took it** / unused | 19 / 8 / 26 / **42** / 5% |
| ... when the enemy is weak (< 100) | 20 / 9 / 30 / 35 / 6% (hardly different) |
| Enemy within 600 u at his pickups: when he is weak / strong | 32% / 26% (he does not avoid contests when weak) |
| Lost contests a game | 4.2 |
| Deaths while weak (his stack < 100, the enemy's > 150) a game / share of his deaths | 4.4 / 38% |
| After losing sight: toward the enemy when ahead / away when behind | 40% / 42% |

What v0.4.3 must move (the head chooses):

| Row | Target |
|---|---|
| Mega and red respawns: waiting (19%; the pros 12%) | down toward the pros. **Not** "the enemy took it" (42%): the pros' is 42% too (`data/decision/pros.txt`, 2026-10-23: in a duel each takes about half) |
| Enemy near his pickups when he is weak (32%) | down: when weak, take the item the enemy is not going for |
| Lost contests (4.2 a game) | down |
| Presses in when far behind (36%; the pros 24%), deaths while weak (4.4 a game; the pros 3.3) | down toward the pros |
| After losing sight, the gap slope (17.3; the pros 21.2) | up toward the pros |
| Closing against the gap (30.9) | steeper: press when ahead, back off when behind |

v0.4.3 passes when these move toward the pros' (the same report on the pros' demos, to be filled in).

## Measure: the decision report

Fight or back off by the stack gap; items against the enemy's distance; timing; deaths while weak; where he goes after losing
sight; split by what he believes as well as by the truth. v0.4.3 passes when these move toward the pros' (`tools/decision_report.py`).

## Play tests aimed at it

The owner stays weak, or stacked, on purpose: does he press or back off; does he contest the item the owner goes for. The quick
human check of "he changes his intention by the enemy's state" that no single number holds.

## Growing the head (the owner, 2026-10-22: "slowly build out the size of the head to incorporate new pathologies that appear in practice")

Each pathology seen in play tests or the people review becomes a **measured row** in the decision report first; the head grows
(or gets a new intention) only to move that row, and the row says whether it worked.

## Toward pay by win chance (v0.4.4 on; the owner, 2026-10-23)

| Step | What | When |
|---|---|---|
| Measure (now, CPU; branch `winpay`) | his own win table beside the pros'; the pay ledger (each pay's share); each shaping pay's alignment with winning 30–120 s later; value readiness (does his value predict the result; does it rise at a mega by the mega's worth); a shadow win-chance counter | 2026-10-23 → |
| Recalibrate | a shaping pay far from its measured worth set to it (a bridge before its fade, not an end) | before its fade |
| Frag pay → win chance (`WIN_PAY`, built) | a cross-fade of the flat ±1 into the change of his win chance, check-tied; the head's long value rewired to include it | v0.4.4 |
| Scaffolds faded | one or two a version: items, the item rule's floor, speed/hop, watching/pre-aim, stack difference, damage last | v0.4.4 on |
| Stays | the fairness limits (aim, senses, his own item timers); movement practice's own pays (no score there) | – |

## Then (v0.4.4 and on, each on a measured need)

| Step | When |
|---|---|
| More intentions: contest, wait at an item, stack up, ambush the predicted opening (opened out of the choices they stand in for, never by a bias over all) | the head's bias cannot express the choice the report wants |
| A wider slow memory | the head's value or the report stalls |
| A store of the last minutes | he forgets the enemy's habits or item timings beyond a minute |
| Rail angles held on purpose (B-273) | through a holding place chosen by the head |

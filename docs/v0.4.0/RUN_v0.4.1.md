# v0.4.1 on one page: the picture steers his intention (DRAFT)

*2026-10-22: **proposed**, after v0.4.0 works. Design: [BELIEF_LOOP.md](BELIEF_LOOP.md). Before it: [RUN_v0.4.0.md](RUN_v0.4.0.md).*

**Marks:** ✅ built and proven identical with its switch off · ⏳ building · 🧪 from the calibration · ❓ owner's decision · ⏸ later

## The idea

One picture of the enemy (v0.3.11 now, v0.4.0 ahead), read two ways: the hands use it every frame (pre-aim, turn to the
opening, the quiet weapon), and a small slow head uses it to choose what he is doing (which item, which place, whether to go
for the enemy). Both are parts of the same network, trained together; the head ticks slower.

## What changes

| Part | Detail | State |
|---|---|---|
| **The picture as an input** | (the "now" part moved into v0.4.0 by the owner, 2026-10-22): here the prediction-ahead answers join it in the `belief` token | ❓ |
| **The small slow head** | reads the belief token, his own stack, item timers, score and clock, the fast state (no gradient); a GRU of 256 ticking every 0.2 s; acts by a plan (64) into the fast memory and a bias on the intention head's choice, both starting at zero (an exact start) | ❓ |
| Size | ~0.6 M weights (v0.4's earlier candidate head: ~7 M); grows only on a measured need | – |
| On a server | well under 1 ms a tick; the head added to the plugins' forward pass (the readout is already there from v0.4.0) | ❓ |
| The head's horizon | a goal choice pays off 30–60 s later: the head learns from the two-minute value output (γ 0.9998), not the main ~25 s one, or it undervalues timing plays | ❓ |
| A start from the pros (only if needed) | the pros' next goal by situation (mega when the enemy is far, back off when weak) as a light prior on the head's bias, fading like the item rule; added only if the head is slow to find these by winning. The owner is wary of copying the pros' choices (HAND_TEACH): measure first | ⏸ |

## Rule-made strategy the head takes over (the owner, 2026-10-22: "Is there any other parts of him like this that might need revisiting?")

| Part | Now | With the head |
|---|---|---|
| The item rule (the intention teacher, never under 10%) | a hand rule nudges which item he goes for, forever | its floor faded to zero as the decision report shows the head choosing well |
| The hunt (`HUNT`) | a rule sends his way toward where he believes the enemy (reads the readout from v0.4.0) | whether to hunt is the head's choice |
| Item pays (pickups, the big-item order, item loss) | hand-shaped values of items whatever the situation | lowered step by step as the head learns their value from winning (the item-pay review of 2026-10-17 belongs here) |
| Item timers (his own pickups) | rule-kept clocks: fair, a person keeps them too | kept; the enemy's side ("when is mega back after he took it") into the readout only if the report shows timing mistakes |

## Arms before the start (ten updates each and a check against the control)

| Arm | What | Pass |
|---|---|---|
| A | the prediction-ahead answers into the belief token | step per update and aim unchanged; check ≥ level against v0.4.0's end |
| B | the token + the small head | the same, and the decision report moves |

## What it should do

| Situation | The head's bias |
|---|---|
| Strong, the enemy weak and predicted near | toward "the enemy" as his target |
| Weak, the enemy strong | toward the items the enemy is not going for, away from his predicted path |
| The enemy going for mega, he is strong | contest it; weak: take the red armor across the map |
| An item about to spawn, the enemy far | be there on time |

## Measure: the decision report

Fight or back off by the stack gap; items against the enemy's distance; timing; deaths while weak; where he goes after losing
sight; split by what he believes as well as by the truth. v0.4.1 passes when these move toward the pros' (`tools/decision_report.py`).

## Play tests aimed at it

The owner stays weak, or stacked, on purpose: does he press or back off; does he contest the item the owner goes for. The quick
human check of "he changes his intention by the enemy's state" that no single number holds.

## Growing the head (the owner, 2026-10-22: "slowly build out the size of the head to incorporate new pathologies that appear in practice")

Each pathology seen in play tests or the people review becomes a **measured row** in the decision report first; the head grows
(or gets a new intention) only to move that row, and the row says whether it worked.

## Then (v0.4.2 and on, each on a measured need)

| Step | When |
|---|---|
| More intentions: contest, wait at an item, stack up, ambush the predicted opening (opened out of the choices they stand in for, never by a bias over all) | the head's bias cannot express the choice the report wants |
| A wider slow memory | the head's value or the report stalls |
| A store of the last minutes | he forgets the enemy's habits or item timings beyond a minute |
| Rail angles held on purpose (B-273) | through a holding place chosen by the head |

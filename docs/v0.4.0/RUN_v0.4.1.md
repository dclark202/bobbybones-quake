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
| **The picture as an input** | the readout's answers (now and ahead, ~60 numbers, no gradient back) as one more attention token (`belief`), its gate shut at the start, opening over hours | ❓ |
| **The small slow head** | reads the belief token, his own stack, item timers, score and clock, the fast state (no gradient); a GRU of 256 ticking every 0.2 s; acts by a plan (64) into the fast memory and a bias on the intention head's choice, both starting at zero (an exact start) | ❓ |
| Size | ~0.6 M weights (v0.4's earlier candidate head: ~7 M); grows only on a measured need | – |
| On a server | well under 1 ms a tick; the plugins need the readout and the head (not dropped at export, unlike v0.3.11 and v0.4.0) | ❓ |

## Arms before the start (ten updates each and a check against the control)

| Arm | What | Pass |
|---|---|---|
| A | the belief token only | step per update and aim unchanged; check ≥ level against v0.4.0's end |
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

## Then (v0.4.2 and on, each on a measured need)

| Step | When |
|---|---|
| More intentions: contest, wait at an item, stack up, ambush the predicted opening (opened out of the choices they stand in for, never by a bias over all) | the head's bias cannot express the choice the report wants |
| A wider slow memory | the head's value or the report stalls |
| A store of the last minutes | he forgets the enemy's habits or item timings beyond a minute |
| Rail angles held on purpose (B-273) | through a holding place chosen by the head |

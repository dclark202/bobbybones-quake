# v0.3.12 on one page: predict ahead, and the first small strategy head (DRAFT)

*2026-10-22: **proposed**, not built. v0.3.11 trains first, long enough to take in its new knowledge (to 16:00 Fri). Design
and reasons: [BELIEF_LOOP.md](BELIEF_LOOP.md).*

**Marks:** ✅ built and proven identical with its switch off · ⏳ building · 🧪 from the calibration · ❓ owner's decision · ⏸ later

## The idea (the owner, 2026-10-22)

> "the fast mechanical network and the strategy network need to share the same representation of the enemy, but act on it in
> different ways."

v0.3.11 builds that representation (where the enemy is now, how stacked, what he holds). v0.3.12 makes it **predict** and
makes it **shared**: the hands and a small slow head both read it.

## What changes

| Part | Detail | State |
|---|---|---|
| **1. Predict ahead** | new readout outputs: the enemy's place in 1, 2, 4 s (each with a spread), what he is going for next (mega, red, yellow, a big weapon, a holding place, "me", none), when he comes into view (bands) | ❓ |
| Graded and paid | as v0.3.11: a proper score against the truth once the future has played out; zero-sum pay, credited when the prediction was made | ❓ |
| Calibration | from the pros' demos: how predictable a pro is 1/2/4 s ahead; how guessable "what he goes for" is | 🧪 to do |
| **2. The picture as an input** | the readout's answers (~60 numbers, no gradient back) as one more attention token (`belief`), its gate shut at the start and opening over hours | ❓ |
| **3. A small slow head** (arm B) | reads the belief token, his stack, item timers, score and clock, the fast state (no gradient); a GRU of 256 ticking every 0.2 s; acts by a plan (64) into the fast memory and a bias on the intention head, both starting at zero | ❓ |
| Size | +~0.6 M weights for the head (v0.4's candidate head was ~7 M); the readout and head dropped or kept at export as the plugins need | – |

## Arms before the start (the rule since 2026-10-13: ten updates and a check against the control)

| Arm | What | Pass |
|---|---|---|
| A | prediction ahead only | step per update and aim unchanged; check ≥ level against v0.3.11's end |
| B | A + the belief token + the small head | the same, and the decision report moves |

## What it should do (the equilibrium)

| Situation | What the pay and the head push toward |
|---|---|
| He reads the enemy's route | he gains: contest the item the enemy goes for, take the one he skips, set up where he will appear |
| He is predictable (same path, same timing) | the enemy reads him: he loses. Varied routes pay |
| Strong against a weak enemy he expects | the head's bias toward "the enemy" as a target; the hands pre-aim at the predicted opening |
| Weak against a strong enemy | toward the items he is not going for; away from his predicted path |

Goals moved: counterplay and positioning (reading the other side and hiding your own plan), item control (timing against the
enemy), then beating people.

## Measures

| What | Where |
|---|---|
| The prediction's error at 1/2/4 s against the pros' predictability; "going for" right; appearance band right | metrics.jsonl, the watcher's line |
| **The decision report** (fight or avoid by the stack gap; items against the enemy's distance; timing; deaths while weak; path after losing sight) against v0.3.10, v0.3.11 and the pros | `tools/decision_report.py` |
| Gate at update 10 and checks every 20 updates: **record, win rate, frag share** in whole ten-minute games with overtime | the watcher |

## Later (only on a measured need)

| Step | When |
|---|---|
| Wider slow memory (512, 1024) | the head's value or the decision report stalls |
| A store of the last minutes (v0.4's 224 slots) | he forgets item timings or the enemy's habits beyond a minute |
| Target and way heads from the head (v0.4) | the intention bias is not enough to change routes |
| Rail angles held on purpose (B-273) | through the head's choice of a holding place |

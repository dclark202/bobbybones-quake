# v0.4.1 on one page: the brain connected to the hands

*2026-10-22 night: **planned** for Fri ~10:00–noon, from v0.4.0's end once the brain passes its readiness test
([RUN_v0.4.0.md](RUN_v0.4.0.md)). Next: [RUN_v0.4.2.md](RUN_v0.4.2.md) (the old belief faded out, the strategy head).
Design: [BELIEF_LOOP.md](BELIEF_LOOP.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The step

The hands start reading the brain. The brain's answers come in as **one new input** (a token in the hands' attention), behind a
gate that is shut at the start and opens over hours. **The old rule-made belief stays in for now** (it fades out in v0.4.2): one
change at a time. This is the first time the brain can change how he plays.

## What changes

| Part | Detail | State |
|---|---|---|
| The brain's answers as an input | a new token (`belief`) in the hands' attention: the readout's place (± spread), velocity, stack band, weapon in hand, weapons owned | ❓ |
| **Turned with him every frame** | the readout gives the enemy's place relative to his view at its 0.2 s tick; between ticks he turns and moves. The answer is kept in map coordinates and re-turned into his current view every frame | ❓ |
| **The gate** | shut for the first hour (play exactly v0.4.0's), then opening over ~4 h; live (pause, slow down, close). Gate 0 must mean the token is not there at all (to verify: the existing token gate starts at a large negative bias, tiny but not zero) | ❓ |
| What the hands learnt from | the answers they actually saw in play are recorded with the games and used in learning (the brain keeps learning, so recomputing them would train the hands on inputs they never saw) | ❓ |
| The brain stays honest | no game reward flows back into it: it learns from the truth only (a test proves the gradient is zero) | ❓ |
| The brain learns more slowly once connected | so the hands are not chasing a moving input; its learning rate live | ❓ |
| **New readout outputs, added untrained** (not inputs yet) | the zones (odds over ~16–24 map zones + the top two places: a split belief can't be one point); where the enemy will be in 1, 2, 4 s; what he is going for; when he appears; the item race for mega and red (his walking-time lead, the chance the enemy is there at the spawn). Lesson only, **no pay on the future** | ❓ |
| The check tools run the brain too | the checks, the decision report and the drift check must play the same network as training once the gate opens, or every number is wrong | ❓ |

## Tests before the start

| Test | Pass |
|---|---|
| Identity at gate 0 | his actions bit-identical to v0.4.0's end, in the trainer's play and in the check tools |
| Gate at 1, short trial | runs; the token reaches his outputs |
| The brain's gradient from the game | exactly zero |
| Speed and the card's memory | – |
| Ten updates and a check against the control | the rule since 2026-10-13 |

## Targets: the decision report (the owner: "whatever we start doing in v0.4.x needs to target these findings")

Baseline (v0.3.10's end against v0.3.9's end, 80 whole games): presses in far behind 36% (then dies 61%); mega and red respawns
the enemy took 42%, on time 8%, no better when the enemy is weak; the enemy within 600 u at 32% of his pickups when he is weak;
deaths while weak 4.4 a game (38% of his deaths). v0.4.1 should move:

| Row | Why | Direction |
|---|---|---|
| Presses in when far behind; deaths while weak | the brain's stack of the enemy, sharper than the old filter | down |
| After losing sight, by the stack gap | the brain's place of the enemy | toward when ahead, away when behind, more clearly |
| Pre-aim at 0–2 s unseen | the brain's place | up |

The item rows are v0.4.2's (the strategy head); here measured.

## Watch, and the way back

| Every ~1.5 h | – |
|---|---|
| Record, win rate, frag share against v0.3.10's end and v0.4.0's end | the headline |
| The decision report; the drift check; the hands' attention on the new token; aim and hit rates | is he reading it, does he play better, is anything breaking |
| **Way back** | close the gate live: he is v0.4.0's hands again, no restart |

# v0.4.0 on one page: predict where the enemy is going, and the readout in place of the old belief rule (DRAFT)

*2026-10-22: **proposed**, not built. The first step of v0.4 (the owner, 2026-10-22: "let's not call it v0.3.12 but v0.4.0
instead. The goal now is to expand this network step by step until we have the type of truly reactive play (i.e., he seems
to actually change his intention based on the enemy state)"). After v0.3.11 (to 16:00 Fri), a quick run. Design:
[BELIEF_LOOP.md](BELIEF_LOOP.md). Next step: [RUN_v0.4.1.md](RUN_v0.4.1.md).*

**Marks:** ✅ built and proven identical with its switch off · ⏳ building · 🧪 from the calibration · ❓ owner's decision · ⏸ later

## The steps of v0.4 (the owner, 2026-10-22)

| Version | Step | Reactive play it aims at |
|---|---|---|
| v0.3.11 (running) | the picture now: where the enemy is, how stacked, what he holds; taught and paid | – (the knowledge in his memory) |
| **v0.4.0** | **the picture ahead: where he is going, what for, when he appears; and the readout's picture of now replaces the hand-built belief in his inputs** | reading the enemy |
| v0.4.1 | the prediction ahead fed back too; a small slow head reads the picture and steers his intention | changing his intention by the enemy's state |
| v0.4.2+ | more intentions (contest, wait, stack up, ambush), a wider head, a store of the last minutes: each on a measured need | the strategy layer grown step by step |

Held for now (the owner): rocket jumps and other movement work.

## What changes in v0.4.0

| Part | Detail | State |
|---|---|---|
| **Predict ahead** | new readout outputs: the enemy's place in 1, 2, 4 s (each with a spread), what he is going for next (mega, red, yellow, a big weapon, a holding place, "me", none; within 10 s), when he comes into view (bands: <1, 1–3, 3–6, >6 s, not within 10 s) | ❓ |
| Graded and paid | as v0.3.11: a proper score once the future has played out in the rollout; zero-sum pay credited to the frame the prediction was made | ❓ |
| Into his memory | the same small share as v0.3.11's lesson (10%), a warm-up | ❓ |
| The prediction ahead is not an input yet | (that is v0.4.1): v0.4.0 tests that he **can** read the enemy ahead without costing the hands | – |
| **The swap: readout in, the old rule out** | the owner, 2026-10-22: "We're training his network for making enemy location predictions now. Once it's trained sufficiently, we'll delete the old crappy rule and insert this in its place in the inputs" ("It shouldn't be a part of him, that didn't work"). v0.2's hand-built belief inputs (last seen or heard place + 1 s of velocity, kept 20 s; ~20 inputs) go to zero; the readout's picture of now (place, spread, velocity, stack band, weapon, weapons owned; no gradient back) comes in as a new attention token (`belief`) whose gate starts shut and opens over hours: an exact start, no jolt. The old rule's readers (the legs' look point, the hunt's target) move to the readout | ❓ |
| When the readout is good enough | already better than the rule from 2 s unseen on (update 40: 2–5 s 399 u against 499); at 0–2 s still worse (190 against 142), which pre-aim needs: match the rule there by v0.3.11's end before the swap. With the enemy in view his sight inputs stay as they are | 🧪 |
| **On a server** | the readout is no longer dropped at export: it runs every frame in the plugins' forward pass; plugin work and an input check in a real game (`OBSDUMP`, as after every input change), a build step of its own | ❓ |
| Calibration | from the pros' demos: how predictable a pro is 1/2/4 s ahead; how guessable "what he goes for" is | 🧪 to do |
| Size | +~0.05 M weights in the readout (kept at export now: see the server row) | – |
| **Graded on the pros' games too** | the demo pipeline rebuilds a pro's inputs from his recording: the same readout graded on "from what this pro saw and heard, where was his opponent, where will he be", a small share into memory, a fading weight. Grounds the picture in how people move (self-play alone teaches him to predict Bobby) | ❓ behind a switch |

## Arms (ten updates each and a check against the control, from v0.3.11's end)

| Arm | What |
|---|---|
| A | prediction ahead only |
| B | the swap only (readout in, the old rule out) |
| A + B | both: the run, if each passes alone |

## The equilibrium

| Situation | What the zero-sum pay pushes toward |
|---|---|
| He reads the enemy's route | he gains |
| He is predictable (same path, same timing, the item he always goes for) | the enemy reads him: he loses. Varied routes pay |
| Both in view | little to predict either way |

Goals moved: counterplay and positioning, item control against the enemy.

## The pros' demos and real players (owner, 2026-10-22: "how do we use the pro demos here?")

| Use | How | When |
|---|---|---|
| Calibration | how predictable a pro is 1/2/4 s ahead; how guessable "what he goes for" is | before the start |
| Teach the picture on human opponents | the switch above | in v0.4.0's run |
| The decision report's target | both players' stacks and places are in the demos: the report's rows filled in for the pros (measurement only) | before v0.4.1 |
| A second check on real people | the public server's logs of people against Bobby: how well he predicts real players (a stable random id per person, no names) | once v0.4.0 runs |

## Pass (a quick run, a few hours)

| What | Pass |
|---|---|
| Step per update, aim, hit rates | unchanged against v0.3.11's last updates |
| Gate at update 10, checks every 20: **record, win rate, frag share**, whole ten-minute games with overtime | ≥ level against v0.3.11's end |
| The prediction's error at 1/2/4 s | better than "he stays where he was" and approaching the pros' predictability |
| "Going for" right | above the pattern-alone baseline from the demos |
| The decision report (`tools/decision_report.py`) | measured against v0.3.10 and v0.3.11; v0.4.1 is where it should move |

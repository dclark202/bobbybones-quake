# v0.3.11 on one page: the knowledge pay (DRAFT)

*Draft, 2026-10-22. Being built beside v0.3.10 (branch `v0311` from `v0310`); the numbers marked 🧪 are filled in from the pro-demo
calibration. Starts overnight from v0.3.10 **only if** v0.3.10's look-back pay is helping (the owner's evening call), behind a gate at
update 10. If it flops: back to v0.3.10 in the morning.*

**Marks:** ✅ built and proven identical with its switch off · ⏳ building · 🧪 from the calibration · ❓ owner's decision · ⏸ later

## The idea (the owner, 2026-10-22)

> "Have Bobby keep a running estimate of position, stack, ownership of weapons, direction, speed, etc of the enemy in memory, with
> some estimate of uncertainty. Every few ticks he gets paid proportional to how accurate this is, perhaps weighted by uncertainty as
> well. The pay can be zero sum."

## What we tried before, and why this is different

| | The guessing game (v0.2.1, 2026-10-12 → today) | The knowledge pay (v0.3.11) |
|---|---|---|
| What it is | extra outputs that guess things about the enemy (his place, where he will appear, a fight coming, items; later his landmark, target, stack, weapon, who takes the big items), graded against the truth like a quiz | the same kind of guesses, **plus a pay for guessing well** |
| What it changed | it learnt to answer (his place 762 → 347 u off; landmark right 16 → 49%; enemy weapon 40 → 76%), but nothing made knowing matter to how he plays | knowing becomes something his **actions** earn: scouting, listening, checking where the enemy would go, keeping him in earshot |
| In play | no measurable gain: 46% against the control with it (51% without, 4 maps × 16 games); with a slow memory, level | – (to measure) |
| Its guess | 683 u off, worse than his hand-built belief inputs (445 u) | must beat 445 u before the pay means anything |
| Since 2026-10-14 | runs at a small weight, two questions, **cut off from shaping his memory** (it measures, it does not teach) | allowed into his memory at a small weight, with a gentle start |

## How it works

| Part | Detail | State |
|---|---|---|
| **1. His running estimate** (new outputs: guesses, not actions) | the enemy's **position** with an **uncertainty** (a spread: how sure he is), his **speed and direction**, his **stack** (health + armor in bands), the **weapons he owns**, the **weapon in his hand** | ⏳ |
| **2. Taught directly** | each guess is graded against the truth every frame (the guessing game's machinery, revived): this is what makes his memory keep the record. Small weight into the shared layers, rising over the first hour (in 2026-10-12's test eight questions pulled ~5× as hard as four: the warm-up and a small weight guard against it) | ⏳ |
| **3. The knowledge pay** (zero-sum, every 0.5 s) | each side's estimate scored against the truth with a score that grades the uncertainty too: **confidently right scores best, confidently wrong worst, honestly unsure in between** (the "weighted by uncertainty" part). Pay = k × (his score − the enemy's score) | ⏳ |
| Size k | set so that tracking clearly better than the enemy is worth about as much as the pre-aim pay over a minute (~0.1–0.3 a player-minute) | 🧪 |
| The score's spread scale | from the pros' demos: how far an unseen opponent moves in t seconds (the honest uncertainty a good tracker should hold) | 🧪 |
| Where it's computed | in the trainer, from his estimate outputs and the truth columns the simulator writes (the simulator never sees his guesses) | ⏳ |
| Fairness | the truth is used only to grade and pay; his inputs stay what he perceives | – |

## What the zero-sum makes him learn (the equilibrium)

| Situation | What the pay does |
|---|---|
| Both in plain view | both know everything: the difference is ~0. Nothing to farm by staring at each other |
| Enemy hidden, he tracks well | he gains: so listening, item timing, checking likely spots, keeping in earshot pay |
| He is hidden and quiet | the enemy tracks him worse: he gains. **Stealth pays**: no jump spam, the lightning gun's hum put away (it's heard, and it muffles his own hearing: v0.3.10's `LG_DEAF`) — the principled version of the "LG noise cost" the owner rejected as a bandaid |
| He is noisy (hum, jumps, pickups heard) | the enemy tracks him better: he loses |

Goals moved: counterplay and positioning (knowing where the enemy is and denying him the same), weapon use (the quiet weapon between
fights).

## Measures and checks

| What | Where |
|---|---|
| His estimate's error by time unseen (position median, the score, stack band right, weapon right), against his hand-built belief inputs (the bar: 445 u in 2026-10-14's test) and the pros' simple trackers | metrics.jsonl, the watcher's line |
| The knowledge pay a player-minute; the share decided while hidden | metrics.jsonl |
| Lightning carried out of contact (pros 14%), jump presses (pros ~24 a minute) | the watcher's line |
| **Gate**: update 10 against v0.3.10's end (fair: both at aim 4) | the watcher; if under 45%: back to v0.3.10 (❓ automatic on the owner's yes before he sleeps) |
| Every 20 updates: v0.3.10's end and the control (v0.3.6's end, the public server's network) in turn | the watcher |

## Calibration from the pro demos (filled in when the build reports)

| | |
|---|---|
| An unseen opponent's displacement against time unseen | 🧪 |
| Simple trackers' error (last seen; last seen + heading; heading to the nearest likely item) | 🧪 |
| His hand-built belief inputs' error now (v0.3.9) | 🧪 |
| What the demos show of an unseen opponent's stack and weapons changing | 🧪 |

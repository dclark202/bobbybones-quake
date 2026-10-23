# v0.4.2a on one page: the old belief faded out of the hands

*2026-10-23 17:30: **built and tested on the CPU** (branch `v042a`, `c93617f` on v041-server `9c8651b`; all off by default: bit-identical to v0.4.1 off and at g = 0; the faded columns read their mean at g = 1, the brain's input unchanged, the readers on the brain on 100% of lives; server vs checks 0 differences at every gate and fade; 0 of 18 brain weights reached). The fade is **76 columns** (the list below adds up to 76, not 78). 17:00: building (owner, 2026-10-23: "v0.4.2a is the right start"; "from v0.4.2 we should be moving to use the brain to control the things that we previously hardwired"); draft 16:30 for the owner's review (tonight / Sat noon). Build Sat morning on the CPU while v0.4.1 finishes; start
Sat ~12:30 from v0.4.1's end on the owner's go; 18–24 h. Before it: [RUN_v0.4.1.md](RUN_v0.4.1.md). After it: v0.4.2b, the strategy
head ([RUN_v0.4.2.md](RUN_v0.4.2.md)). Design: [BELIEF_LOOP.md](BELIEF_LOOP.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The step

The hands stop reading the old hand-built belief of the unseen enemy (the owner, 2026-10-22: a failed baseline, retired in v0.4)
and rely on the brain's answer, which v0.4.1 connected. A fade gate takes the rule-made inputs down over hours; **the raw sensed
facts stay** (where and when he last saw or heard the enemy: the owner, 2026-10-22, "yes that seems right to me"). Everything the
simulator itself did with the old belief moves to the brain's answer on the same gate. One change: the brain's new outputs
(1/2/4 s ahead, target, appear, item race) do not join here (below).

## What fades (76 input columns; audit of 2026-10-23, `duel_env.py` in branch `v041`)

| Group | Fades (rule-made) | Stays (raw) |
|---|---|---|
| The enemy as he believes him (21) | the believed place (3: last known + his last velocity carried forward), "believed" flag (1), the ways from the believed place to him, mega, red (3) | time since seen / heard, where heard, damage, life clock, death known, pickups and weapons seen (14) |
| His position (10) | height above the believed enemy (1) | the other 9 |
| The pros' places near him (96) | per place: distance from the believed enemy, nearest to him (16) | the other 80 |
| The enemy's stack filter (6) | expected health, armor, sum, spread, weak (5) | time since pinned (a known spawn, a pain sound) (1) |
| Pre-fire spots (39) | all: chosen by the believed way | – |
| Where he may appear (8) | all: made from the believed place | – |

## What changes

| Part | Detail | State |
|---|---|---|
| **The fade gate** | the 78 columns times (1 − g) **after** input scaling, so a faded column reads its average (raw "nothing" codes are not zero: a raw ×0 would mean "right here"); g recorded with each rollout and replayed in learning, as the token's gate is; exact at g = 0 (bit-identical, a test); live: pause, slow, close | ❓ |
| **The ramp tied to the checks** (the owner, 2026-10-23: a dip "shouldn't persist for more than 20-30 updates") | shut 1 h, then +0.1 every ~25 min; a check under 50% holds it, a second in a row or one under 45% sends it back to the last passing level | ❓ |
| **What the brain reads** ❓ | the brain itself reads the same inputs, these 78 among them. **Proposed:** the brain keeps the unfaded inputs in v0.4.2a (only the hands lose them), so its answers do not shift under the hands mid-fade; the brain's own fade is a later, measured step (its errors by time since seen as the bar) | ❓ |
| **The brain's answer sent to the simulators** | the brain runs on the trainer, not in the simulators; its answer (place, odds, stack band) goes back with each frame's actions, so the simulator's readers below can use it (one frame late; it ticks every 0.2 s anyway) | ❓ |
| The legs' look point (`LEGS_LOOK`), the hunt's target (`HUNT`) | from the brain's likeliest place, a life drawn with chance g; the old point otherwise | ❓ |
| The item lesson's silences (`RULE_CONTEST`: the enemy believed nearer; `RULE_HUNT`: his stack beats the believed stack by 50) | the brain's place and stack band, same draw | ❓ |
| Openings (where a fresh life heads: away from items near the believed enemy) | the brain's place, same draw | ❓ |
| **The blind-fire cost's pre-fire exemption** (a pay ❓) | today: no cost for a shot at the rule's believed place out of view. Proposed: the brain's likeliest place, same draw. Equilibrium: unchanged in kind — he is never paid to fire, only spared the 0.003 cost where his own belief says the enemy is; with the brain's belief the exemption follows what he knows, not a rule (goal: counterplay, pre-fire on real reads) | ❓ |
| Kept on the rule (not his knowledge) | spawn-moment choice for practice starts, the metrics and the brain's yardstick (the old rule's error beside the brain's in every report) | – |
| On a server | the same fade in the plugins' forward pass (g and the column list in the export), the readers on the brain's answer (branch `v041-server` already runs the brain and token); a check of 0 differences server vs checks at g = 0, 0.5, 1 | ❓ |
| Metrics | g; per reader, the share of lives on the brain; the brain's error beside the old rule's by time since seen | ❓ |

## Not in this step

| Part | Where |
|---|---|
| The brain's new outputs (1/2/4 s ahead, target, appear, item race) as inputs | proposed: into the strategy head (v0.4.2b) which needs them most, not the hands' token; each with its readiness bar |
| The brain stops reading the rule's columns | after A, measured |
| The view's pull toward level (B-275) | after B's head |

## Before the start

| Test | Pass |
|---|---|
| g = 0 is exactly v0.4.1's end (fixed-seed replay) | bit-identical |
| 10 updates on a scratch copy at g = 0.5 (the new-lesson rule) | normal step per output; a check against v0.4.1's end ≥ 45% |
| Server vs checks at g = 0, 0.5, 1 | 0 differences |

## Pass (to v0.4.2b)

| Measure | Bar |
|---|---|
| Games against v0.4.1's end at g = 1 | level or better in 3+ checks |
| The same save at g = 1 against g = 0 | g = 1 not worse |
| The decision report's reading rows (after losing sight: the gap slope; pressing in when behind) | not worse; toward the pros |
| The brain's errors | no rise above ~5% |

## Owner's decisions (❓)

| # | Decision | Proposed |
|---|---|---|
| 1 | The brain keeps the rule's columns as its own input during A | **yes** (owner, 2026-10-23: "remove the hardcoded recommendation from the mechanical layer, keep them as inputs for the brain"); the brain's own fade later, after a measure of its error with them at their mean |
| 2 | The blind-fire exemption on the brain's place | **yes** (owner, 2026-10-23: "no cost to spam/prefire where he expects the enemy is"): faded onto the brain on the same gate |
| 3 | The brain's new outputs into the head (v0.4.2b), not the hands' token | **yes** (owner, 2026-10-23: "The hands handle what to do *now*, the predictions drive strategy") |

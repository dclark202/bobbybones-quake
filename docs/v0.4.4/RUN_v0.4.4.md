# v0.4.4 on one page: the strategy head opened (DRAFT)

*2026-10-25 evening (owner: "When we open the strategy head let's call that model v0.4.4 ... the strategy head opening is its own
model number"; what was called v0.4.4 is now [v0.4.5](../v0.4.5/RUN_v0.4.5.md), pay by win chance). From v0.4.3's last save
(the item rule faded out, weapon variety: [../v0.4.3/RUN_v0.4.3.md](../v0.4.3/RUN_v0.4.3.md)). Start: Sunday ~22:00 if the
evening review passes; trains through Monday. The head's design: [../v0.4.3/ARCHITECTURE_v0.4.3.md](../v0.4.3/ARCHITECTURE_v0.4.3.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## What it is

| | |
|---|---|
| The one new thing | **The strategy head** (attached shut since v0.4.3's start): a small slow network (~0.67 M weights, ticks every 0.2 s with the brain) that reads the brain's answers (where the enemy is and will be, what he is going for, "in control"), his stack, item timers, score and clock, and sets his plan: a bias on his item / target choice and a plan vector into the hands. Opened by its gate 0 -> 1 |
| Later steps in the same run (Monday) | the "will be" blind-fire exemption and the level pull phased out, together (owner) |
| Equilibrium it aims at | plans pay through what they win (items, frags); a plan the enemy reads is beaten; no new pay |
| Pass | level or better against v0.4.3's end; the decision report moving toward the pros' (below); the behaviour check per map not worse |
| Fallbacks | v0.4.3's end (kept as `keep/policy_end_v043.pt` + optimizer at the switch); v0.4.3's update 70 (`data/fallbacks/v043_u70_prehead`, 66.2% against v0.4.2's end) |

## The mix (of all training)

| | v0.4.3 (now) | v0.4.4 |
|---|---|---|
| Whole games from 0:00 | 40% | 50% |
| Mid-game starts (pros' moments) | 40% | 40% |
| Practice runs (jump runs; targeted item runs to the weapons he skips) | 20% (10 + 10) | 10% (5 + 5) ❓ the split |
| Per-map item floor (2%) | 0.005 | kept (it reads the hands' choice only, not the head's bias: watch the head's own choice shares) |
| Equal big-weapon pay (0.10 x3) | on | on |

## Schedule

| When (approx.; a held step moves the rest) | What | How |
|---|---|---|
| Sun ~21:30 | the review (owner): Campgrounds' rail, Hektik's lightning, rocket in hand, the behaviour alarms, games | go / plan B |
| Sun ~22:00 | v0.4.3 ends at a save; **v0.4.4 starts** from it (run `duel_gru_v0_4_4`, the same code as v0.4.3's end: branch `starts`) | the mix above |
| Sun 22:00 -> ~02:15 | **the head opens**: its gate cap 0 -> 1, +0.1 every 25 min on passing checks | live `H2_GATE_CAP` (the guard: hold under 50%, back under 45% or two checks under 50%) |
| ~02:30-04:30 | two checks at full head | |
| Mon 06:30 | report | |
| Mon 07:00 -> 10:00 | **the "will be" exemption**: no shot cost where the brain predicts the enemy in 1-4 s; a chance per life 0 -> 1 | live `BLIND_AHEAD_P` |
| Mon 07:00 -> ~11:30 | **the level pull phased out**: 0.95 -> 0.98 -> 0.99 -> 0.995 -> 1.0, 1.5 h a step | live `LEVEL_PULL`; if a check fails in the overlap both hold; the level pull steps back first |
| Mon 13:00-19:30 | everything in; v0.4.5 merged and its fresh-games calibration on v0.4.4's newest save | |
| Mon 19:30 | play test | |
| Tue morning | v0.4.5 starts from v0.4.4's last save (the owner's go) | |

## Measures

| What | Where | Target |
|---|---|---|
| Games, frag share | the checks every 20 updates: against v0.4.3's end; every 4th against the long-term control (v0.3.10's end) | level or better |
| The decision report | `tools/decision_report.py` at the end, beside v0.4.3's end and the pros' | waiting at mega/red down toward the pros' 12% (19%); enemy near his pickups when weak down (32%); lost contests down (4.2 a game); deaths while weak down (4.4 a game; pros 3.3); presses in when far behind down (36%; pros 24%) |
| The behaviour check per map against the pros | `v043w/behaviour.log` style, every check | no new alarms; rocket in hand, standing still and deaths a minute moving toward the pros' |
| The head's own choices | its bias per item and map in the metrics | no item collapsing on a map |
| **The win-pay shadow for v0.4.5** | the trainer's `win_shadow` and `win_value.cal` every update; a calibration watch (scratchpad `v044w/calib_watch.py`: every 3 h fresh whole games of the newest save on all ten maps, `tools/win_calib.py` for the pros' table, the pros' refit and his own) | the critic "ready" (slope 0.8-1.2, corr >= 0.25, beyond >= 0.25) and his own table calibrated on fresh games, before v0.4.5's weight passes 0.2 |

## Decisions for the owner

| # | Question | Recommendation |
|---|---|---|
| 1 | The 10% practice: jump runs / targeted item runs | 5 / 5 while Campgrounds' rail is under the pros'; then the jump runs back to 10 |
| 2 | Plan B if the rail has not moved by tonight | a temporary low-weight teacher for the neglected weapons (rail, rocket) only, faded once he takes them |
| 3 | The rocket in fights (3-24% in hand against the pros' 33-43%) | **decided (owner, 2026-10-25): judged at v0.4.5's end**; "probably same with the rail pickups honestly. I'll have to see how much they move" |

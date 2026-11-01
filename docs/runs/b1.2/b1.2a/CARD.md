# b1.2a: the strategy head faded in, learning from combat plus win pay

*2026-10-31 (owner): head on "combat plus win"; no help trying the enemy as a target; item rule stays on; "Set it for 24 hours, likely we'll start it around 8-9am tomorrow". The family: [README](../README.md). From v0.6.2a's draft ([card](../../v0.6.2a/CARD.md)), which was for win-only pay.*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | b1.1a's end with its optimizer, or the save the morning's checks choose ❓; given the head with its gate shut (`tools/head2_init.py add --gate 0`) ⏳ |
| Run | `duel_gru_b1_2a` |
| The head | `sim/head2.py`, ~0.65 M weights: a slow GRU (256) ticking every 0.2 s, reading the brain's memory and readouts, its "in control" readout, his stack, timers, score, clock and the hands' memory. It adds a bias to his target choice and a plan into the hands' memory, both times its gate ✅ |
| What it learns from | **combat plus win** (owner): frags, deaths, damage and the win part, not the item pay. Its value looks about 2 minutes ahead ✅ |
| What he's paid | unchanged: the table + `WIN_ADD` 0.33. The hands still earn the item pay |
| Its start | from nothing: links at zero, gate 0. No pro-demo fit (owner, 10-30) |
| Help trying the enemy as a target | none (owner). He picks it 1.2% of the time today |
| Item rule | stays at full weight (`INTENT_TEACH_W` 1) |
| Target lock | as b1.1a leaves it: 1 s if that held; else 8 s, and looked at after the head ❓ decided in the morning |
| Ramp | shut for 10 updates, its value learning the pay; then `H2_GATE_CAP` +0.1 a step, ten steps, one right after each save (`tools/run/ramp_head.py`, `RAMP_HEAD_ONLY=1`), ~6.3 h; the head-open save kept 10 updates after (`keep/policy_head_open_b12a.pt`) |
| Hold rule | as b1.0a: goes on above 40%; a check under 50% flagged in the chat; 40% or less holds the next step |
| Length | `--minutes 1440` (24 h, owner) |
| League, checks | the start and v0.6.0's end as anchors; 160 games, about every 20 updates, against the start; every fourth against v0.6.0's end; the panel. Never stopped |
| Kept | the head-open save, the saves every 10 updates, `keep/policy_end_b12a.pt` + `opt_end_b12a.pt` |

## The schedule (from an 08:30 start on 11-01)

| Time | What |
|---|---|
| 08:30 to ~09:10 | gate shut |
| ~09:10 to ~15:30 | gate 0 → 1 |
| ~12:30 | possible play test at about half open |
| ~16:10 | head-open save; play test |
| to ~08:30 on 11-02 | settles open, ~16 h |

Why this ramp: no measurement sets the speed. A check reads about every 75 minutes, so ten steps give ~5 readings, and its value needs a start. The opening in v0.4.4 was 25-minute steps, and its spawn camping came from the rule's earlier fade.

## Judged by

The enemy's share of his targets (1.2%), and with the owner in sight: aim off by over 30 degrees (25-30% in the b1.0a games), firing (32-42%), moving toward him (-17 to -34 u/s). The stack gap at the start of fights. Win rate against the start and v0.6.0's end, items a minute, roaming, time at spawns, frags a match-minute, the owner's play tests. A check with the head blanked, at the end.

## The equilibrium

The head plans for frags and winning; the hands keep their item pay and the rule. In self-play the head's part is zero-sum, and both copies gain from a plan that wins fights and games. Items pay the head only through what they add to his chance of winning and to fights. Expected behaviour: fewer trips for items that don't matter to the game's state, more fights when he's level or ahead on stack. The danger on the way: holding a spot (v0.4.4), or fighting from behind on stack more often than is good, which the win part should price.

## Red team

| | |
|---|---|
| May not make him fight | the hands still earn item pay and follow the rule, and the rule keeps teaching items at each reading; both pull against the head. Measured alternative: fade the item pay's size, or b1.2b's help |
| It learns little from what he doesn't try | at 1.2% of choices, the enemy as a target is rarely sampled and the head starts from nothing. Its share moving is the first thing to read, ~2 h after the gate is half open. b1.2b if it doesn't |
| A new reward path | the head's pay being only part of his is new: its value and his will disagree, and its plan into the hands' memory is judged by neither fully. Its size against the hands' is unmeasured |
| Spawn camping | v0.4.4, with the rule faded first. The rule stays on here, and the panel flags it |
| Weapon target | v0.4.4 pushed the lightning gun to 82%. `WEAPON_FREE` is on; watched |
| The lock | at 1 s he may flick between targets, and the head's bias works on every reading; at 8 s the head can't react when a fight starts |
| Never run on this pay | v0.6.2a's smoke ran on win-only pay. Everything is untested on additive pay |
| A long settle at the head's full gate | 16 h with no scheduled test, by day only one play test; the checks run on |
| Judged from a young start | b1.1a may have only ~1 h to settle after the lock |
| Win pay's item prices | a red armor x4, a frag x2.2, level at 5 min. His targets did not move with it in b1.0a, so it stays, but the head reads the win part directly, so it may still learn that items are worth a lot |
| Hand-built / assumed | the head's size and inputs, its 2-minute value, its rate, its lesson's weight (1), the ramp's schedule, the pay it learns from |
| Pay pathologies (ledger) | none new in his pay. Watched: lopsided games, sign flips, negative scores |
| Rocket jumps, movement jumps | important, not in this run: the head can only choose what he can do |

## Before the start

| Step | Where it stands |
|---|---|
| The head's pay ✅ | `--head2-pay combat_win`: its value and advantage on combat plus the win part. The default (`all`) takes the path it always did. Smoke: a frame's mean pay 0.0032 for the head, 0.0047 for him |
| Command ✅ | `train.cmd`, from b1.1a's: only `--run`, `--minutes` 1440 and the head's arguments differ (settings check PASS) |
| The ramp ✅ | `ramp_head.py` with `RAMP_HEAD_ONLY`, `RAMP_OPEN_NAME`, `RAMP_HOLD_AT` 0.40: on a fake run it stepped, flagged a check under 50%, and held at 37.5%. The head-open save's copy was not reached in that test |
| Smoke run ✅ | `smoke.log` ALL PASSED: the head with its gate forced open, on b1.0a's end with the dials at brain 1, pull 1, lock 1 s; its links rose from zero, its bias 12% of his target choice |
| Start script ✅ | `start.ps1`, parsed, not run. It proves the head changes none of his answers on the real start, and refuses otherwise. It takes the dials from the start save |
| Item prices ✅ | no sign win pay moved his targets: b1.0a's shares at update 160 match v0.6.0's end within a point (the enemy 0.5% to 1.2%), trips 12.3 to 12.7 a minute. So `WIN_ADD` stays. It doesn't measure how he plays once there |
| Reading a play test ✅ | `tools/run/play_read.py <data folder>`: stacks, items, fights by who is ahead, tunnel vision |
| The start save ⏳ morning | **b1.1a must be stopped and its end kept first:** `python tools/run/stop_run.py duel_gru_b1_1a b11a` (the next save, then it stops; the owner's word). From another save: `start.ps1 -Save policy_nopull_b11a.pt -Opt opt_end_b11a.pt` (a borrowed optimizer, from up to a few hours later) |
| A server ⏳ | the head open on a private server, before the first play test: not done |
| The owner's go ❓ | morning of 11-01 |

Then: `powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2a\start.ps1`

## Changes on the fly

| Time | Change | Why |
|---|---|---|

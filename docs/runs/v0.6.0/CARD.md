# v0.6.0: v0.5.0's setup from v0.4.2b's end, with Bobby's aim measured from the pros

*First run 2026-10-27 19:42 → 10-28 07:21 (170 updates; 52-64% against v0.4.2b's end at the same aim; the owner: "He's a
success"). Its saves were lost in the data loss of 2026-10-28 ([../../HISTORY.md](../../HISTORY.md)); **retrained** the same
way for 6 hours (owner: "restart the v0.6.0 training exactly as it was last night").*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.4.2b's end with its optimizer (`data/sim_runs/duel_gru_v0_4_2/keep/policy_end_v042.pt`, `opt_end_v042.pt`; recovered, byte-identical to a second copy) ✅ |
| League | **v0.4.2b's end only** (anchor) + the run's own new snapshots (owner, 2026-10-28: "Just get rid of the league then. I only need v0.4.2b"). The recovered league held 9 corrupt networks (anchors v0.3.8, v0.3.9 and 7 of v0.4.2's snapshots: weights up to 1e38 or NaN); drawn as an opponent, one made the trainer crash (CUDA assert in sampling) at 12:25 and 12:32. All 99 moved to `snapshots_aside_20261028/` (not deleted) ✅ |
| Code | `main` (the training code of branch v061 = aim2 + the v0.5.0 loophole fixes; the win-pay parts off) ✅ |
| Aim | `!aim default` = the pros' mean, twelve knobs measured on 781 pro demos (`aim2_env.cmd`; 125 / 225 ms) ✅ |
| Pay | v0.5.0's: flat frag, damage, item pay (mega 0.35, red 0.30, yellow 0.15), speed pay 0.25; win chance recorded only ✅ |
| Mix | 65% whole games / 35% the pros' mid-game starts; no movement practice ✅ |
| The brain's people lesson | **changed for the retrain**: from the pro demos only (the same 115 demos as before; the people's sessions pack is gone; owner: "Build on the pros") ✅ |
| Maps | the game's own geometry; nav and cell tables from the public server (87-99% identical to training's lost copy, mean way difference ≤ 0.08 s) ✅ |
| Length | started 2026-10-28 12:00, to ~21:00 (`--minutes 535`; owner: "running until 9pm") |
| Checks | every 20 updates, 160 games against v0.4.2b's end (both at the new default); the behaviour panel. No guard: never stopped automatically; under 30% posted to the owner |
| Logged for v0.6.1 | self-play games of saves 40 to 120, every 20th, 6 games a map (300 games; fitted after the run), once a second (score, stacks, weapons owned, deaths, his win value): the data for fitting his chance of winning on game results ("B") |

## The checklist

| | |
|---|---|
| Settings check | `train.cmd` against `reference_20261027.cmd` (last night's): **PASS** with only `--minutes`, `--brain-human`, `--brain-human-mix` different ✅ |
| Hand-built / assumed parts | the flat pay (v0.5.0's weights, set by hand); the item rule (the intention's lesson); the speed pay. All known, all to fade in v0.6.1-v0.6.2 |
| Pay pathologies | none new (v0.5.0's pay, as in last night's run, which did not collapse) |
| Calibration numbers | the aim: measured on the pros ([../../design/AIM2_MODEL.md](../../design/AIM2_MODEL.md), the twelve-knob table) |
| Not identical to last night | the brain lesson's data (pros only), the nav (server copy), 5 league snapshots, the run's 6 h length |
| Logged for the next run | the B self-play rows (above); the trainer's metrics (pay by term, win shadow, rule agreement) |

## Start

`powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.0\start.ps1` (on the owner's go, after the move to
`Documents\gh\BobbyBones` and the restart).

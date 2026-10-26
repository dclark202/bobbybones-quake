# v0.4.4 on one page: generated mid-game starts, then the strategy head opened

*Started 2026-10-25 ~19:40 (owner's go) from v0.4.3's end = its update 80 (121-39, 75.6% against v0.4.2's end: the best check
of v0.4.3; "a solid bot, but pathological in its choices"). Its weapon-variety restart of 17:04 (targeted item runs + the per-map
item floor) collapsed to 24-136 at its update 90 and was rolled back ([../v0.4.3/RUN_v0.4.3.md](../v0.4.3/RUN_v0.4.3.md)). Pay by
win chance is [v0.4.5](../v0.4.5/RUN_v0.4.5.md). Code: branch `starts` (dae9909, 0750932), run `duel_gru_v0_4_4`.*

**Marks:** ✅ built and tested · ⏳ running · 🧪 to measure · ❓ owner's decision · ⏸ later

## What it is

| | |
|---|---|
| First (from the start) | ✅ **Generated mid-game starts** (owner: "a generative way of putting people in random positions, stacks, ammo, weapons in possession ... all the in game timers in a random state ... biased towards the things we want to encourage"): half of the mid-game starts, drawn fresh at every start (unlimited). The other half: the pros' moments as before |
| Then (Monday 07:00, owner: after a night of the generated starts alone) | **The strategy head** opened: its gate cap 0 -> 1, +0.1 a step on passing checks (live `H2_GATE_CAP`) |
| Later in the run (Monday) | the "will be" blind-fire exemption and the level pull phased out, together (owner) |
| Equilibrium | no new pay: the starts change what he practises, not what pays; plans pay through what they win |
| Pass | update 10 level or better against v0.4.3's end (u80), then every check; his weapon gaps to the pros closing (below) |
| Fallback | v0.4.3's end (`duel_gru_v0_4_3/keep/policy_end_v043.pt` + optimizer; `data/fallbacks/v043_pre_starts`) |

## The generated starts (`GEN_START_SHARE`, `tools/gen_places.py`, `tools/gen_bias.py`)

| Part | How |
|---|---|
| Safe places | every point of the walking map reachable from a spawn, tried in the simulator: the player's box free, no lava / slime / water, stood a second he stays on the ground (640-1,520 places a map; `sim/gen_places/`). Tested: no start in a hazard; moving off a start as often as from the pros' own moments |
| Where | drawn by the pros' heatmap on those places (their positions in the demos, smoothed), 10% uniform; the enemy at least 300 units away |
| The rest | the clock 20-580 s, a score drawn for it, health, armor, weapons owned (half of the map's each), ammunition, weapon in hand, life, speed, every item's timer; a big item that is back: one of the two took it and knows when |
| The bias (live, `<run>/gen_bias.json`) | per map: start **near** an item's spawn (a weapon: half the time not owned, so he takes it; half owned, so he uses it), **own** a weapon more often, a weapon more often **in hand** |
| Automatic | after every weapon-watch line (each save, a few short games a map against v0.4.3's end), `tools/gen_bias.py` sets the bias from his gaps to the pros (1 - his / theirs): pickups -> near, in hand -> own and hand; half a step at a time, capped |
| At the start (from u80's numbers) | Campgrounds: 20% of its generated starts near the rail, the rail owned more and in hand more; the rocket in hand more on every map. Aerowalk's red armor held out (owner: he cannot get there yet; to fix later) |

## The mix (of all training)

| | v0.4.3's end | v0.4.4 |
|---|---|---|
| Whole games from 0:00 | 50% | 40% |
| Mid-game starts | 40% (pros' moments) | **50%** (25% pros' moments + 25% generated) |
| Practice runs | 10% jump runs | 10% jump runs (weighted to the jumps he misses) |
| Targeted item runs, item floor | off | off |
| Equal big-weapon pay (0.10 x3) | on | on |

## Schedule (owner, 2026-10-25 ~20:00: the generated starts alone overnight, the head in the morning)

| When (approx.; a held step moves the rest) | What | Gate |
|---|---|---|
| Sun 19:40 -> Mon 07:00 | the generated starts only, the head shut (the start mix fills in over ~60 updates) | checks u10 (~21:30), u30, u50, u70 (v0.3.10's end), u90 |
| Mon 06:30 | report: games, frag share, the weapon gaps per map against u80 and the pros, the bias's moves | every check 50%+ against v0.4.3's end; the gaps closing |
| Mon 07:00 -> ~11:10 | **the head opens**: live `H2_GATE_CAP` +0.1 every 25 min | hold under 50%, back under 45% or two checks under 50% |
| Mon ~11:10 -> 14:00 | two checks at full head | |
| Mon 14:00 -> ~20:00 | the "will be" exemption (`BLIND_AHEAD_P` 0 -> 1, to ~17:00) and the level pull (`LEVEL_PULL` 0.95 -> 1.0, 1.5 h a step), together | a failed check in the overlap: both hold, the level pull steps back first |
| Mon afternoon | v0.4.5's code merged with `starts`; its calibration on v0.4.4's newest save | the critic "ready" bar |
| Mon 19:30 | play test | |
| Tue 07:00 -> ~18:30 | v0.4.5 from v0.4.4's last save (owner's go): w 0 -> 0.2 by ~08:40, -> 0.5 by ~11:15 (critic ready), two checks, -> 1.0 by ~18:30 | as v0.4.5's card |
| Tue 19:30 | play test; v0.4.5 done | |

## Measures

| What | Where | Target |
|---|---|---|
| Games, frag share | checks: update 10, then every 20, against v0.4.3's end; every 4th against v0.3.10's end | level or better |
| His weapon gaps to the pros, per map | the weapon watch every save (`v044w/weapon_watch.jsonl`), the behaviour check (`v044w/behaviour.log`), the bias log (`gen_bias.log`) | Campgrounds rail picked up (0 now; pros 0.36/min); the rocket in hand in fights toward the pros' 33-43% |
| The generated starts | the trainer's `gen_start` (begun, near, owned and in hand per seat) | about a quarter of all training |
| The win-pay shadow for v0.4.5 | `win_shadow`, `win_value.cal` every update; `v044w/calib_watch.py` every 3 h on fresh whole games | the critic "ready" (slope 0.8-1.2, corr >= 0.25, beyond >= 0.25) before v0.4.5's weight passes 0.2 |
| The decision report | `tools/decision_report.py` at the end beside v0.4.3's end and the pros' | as in v0.4.3's card |

## Decisions (owner, 2026-10-25)

| # | Decision |
|---|---|
| 1 | v0.4.4 starts from u80 (v0.4.3's end) with the generated starts in from the beginning; the head opens Monday 07:00 after a night of them alone (the update-10 check a reading only) |
| 2 | no rail bar for opening the head; plan B (a temporary teacher) shelved to v0.4.5's end |
| 3 | the rocket in fights (and probably the rail pickups) judged at v0.4.5's end |
| 4 | Aerowalk's red armor out of the bias for now |

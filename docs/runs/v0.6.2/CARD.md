# v0.6.2: the strategy head replaces the item rule, on win chance only, from v0.6.1's end

*2026-10-29 (owner): one new thing, a replacement: "the strategy head fades in and then after the item rule fades out, that to
me is 'one thing'"; "the judge is refit to stay 'most appropriate'". The head starts from nothing behind its gate (the owner's
choice of the recommendation, 2026-10-29: no pro-demo fit at the start; the pros' targets are watched instead). First drafted
2026-10-27 from [RUN_v0.5.3.md](../../archive/versions/v0.5.3/RUN_v0.5.3.md); the lesson of v0.4.3/v0.4.4 (rule faded before
any head: spawn camping) sets the order.*

> **Changed 2026-10-29 (owner): v0.6.1b runs between v0.6.1 and this run.** v0.6.1 ends as planned (~18:00). Then
> [v0.6.1b](../v0.6.1b/CARD.md) runs overnight from v0.6.1's end: the old hand-built belief faded out of the brain, with
> the game-end pay fix ([WINPAY_END.md](../v0.6.1/WINPAY_END.md)). **This run starts tomorrow morning from v0.6.1b's end**
> (`keep/policy_end_v061b.pt`), not v0.6.1's. To update before its start, on the owner's go:
> - the network row;
> - the checks (against v0.6.1b's end, every fourth against v0.6.0's);
> - the settings check reference (v0.6.1b's `train.cmd`), plus the brain's dial at 1 and held;
> - the identity check and `start.ps1` on the new start;
> - the judge's refit, on v0.6.1's and v0.6.1b's games ❓.
>
> The rows below still describe the old start until then.

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The owner's page

| | |
|---|---|
| Network | v0.6.1's end with its optimizer (`keep/policy_end_v061.pt`, kept by `start.ps1`), given the strategy head shut (`tools/head2_init.py add --gate 0`) |
| The head | `sim/head2.py` (v0.4.3): a slow GRU (256) ticking with the brain every 0.2 s, reading the brain's memory and readouts, the "in control" readout of the brain (`--head2-ctrl-src belief`), his stack, timers, score and clock, and the hands' memory; it adds a bias to his target choice and a plan into the hands' memory, both times its gate. It learns from its own value (two minutes) and its own policy-gradient term on the target choice; nothing of the hands moves it. ~0.65 M weights ✅ |
| Its start | from nothing: its links at zero, the gate at 0 (owner, 2026-10-29) ✅ |
| Pay | win chance only, as v0.6.1's end (`WIN_W` 1, `FADE_V` 1), **and a game's result paid on its last frame** (`WIN_END=1`, owner 2026-10-29): an audit found that the judge's chance on a game's last frame is not 1 / 0.5 / 0 (its spread at 0 s is 0.14 frags and the stacks still count), so in v0.6.1 a game paid its last-frame chance minus its start, not its result; measured on v0.6.1's 250 self-play games: 4.8% of games off by more than 0.1, the error 0.14 a game on average against 3.19 for a whole game (worst 6.2: a won game paid as a loss). With `WIN_END` a game pays exactly `scale x (result - start chance)`, zero-sum; and a level limit frame that goes on into overtime reads the next period's start (no swing). Branch `v062pay` (off = v0.6.1's simulator to the bit), merged into `main` after v0.6.1 ends |
| The pull toward level | off (`LEVEL_PULL` 1.0), as v0.6.1's end: faded out in v0.6.1 from noon on 10-29 (owner); it comes with v0.6.1's `live.json`, so a `--ck` settings check of v0.6.2's saves shows `LEVEL_PULL` 1.0 against the command's unset (allowed: `--allow LEVEL_PULL`) |
| The judge | refitted on v0.6.1's own self-play games (`tools/run/fit_b.py`, updates 40 to ~240, ~300 games) and frozen for the run; the hand-set weapons: **the rail only** (owner, 2026-10-29: "Rail only") ✅. On v0.6.1's first 150 games the fit prices the rocket launcher on its own (+4.7 points at 5:00, above the lightning gun's +2.1) and the rail still near 0. Recommended: **set the rail only** to the lightning gun's worth (`tools/run/judge_weapons.py ... --set rg`) and let the rocket launcher keep its fitted worth; setting both as in v0.6.1 would now lower the rocket launcher's |
| Ramp | `tools/run/ramp_head.py`, on the clock (owner: "keep going unless a collapse"): shut for 10 updates (the head's value learns the pay, it changes nothing), then `H2_GATE_CAP` +0.1 a step to 1 (the gate follows within a minute: `--head2-open 1`), then **the head-open save kept** (`keep/policy_head_open_v062.pt`, the first save 10 updates after the gate reached 1; training goes on), then the item rule `INTENT_TEACH_W` −0.1 a step to 0. A step every 10 updates and at least 25 min ✅ |
| Timing | ~4 min an update: shut ~40 min, the head open ~7 h, the save ~1 h, the rule out ~7 h: **~15 h**. `--minutes 1440` as v0.6.1 ❓ |
| Aim, mix, maps | as v0.6.1 (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps) |
| League | v0.6.1's end and v0.6.0's end as anchors, then his own snapshots ❓ (v0.4.2b's end leaves the league; it stays in no check) |
| Checks | every 10 updates, 160 games against v0.6.1's end, every fourth against v0.6.0's end (owner); the behaviour panel. Under 40% flagged, under 30% posted. Never stopped |
| Play tests | the owner plays the head-open save and the end ✅ (owner) |
| Logged | self-play games of every 40th save (the judge's data for the next refit) |

## The checklist

| | |
|---|---|
| Settings check | `train.cmd` against v0.6.1's: only `--run`, `WIN_JUDGE`, `WIN_END` and the head's six arguments (`--head2`, `--head2-cap`, `--head2-ctrl-src`, `--head2-gate`, `--head2-open`, `--head2-start`) differ ✅ (`start.ps1` refuses otherwise) |
| Identity | the start network answers exactly as v0.6.1's end: `tools/head2_init.py same`, on a v0.6.1 save, with the gate at 1 (the head's whole path run, its links at zero) and at 0 (the start file); `start.ps1` runs both on the real end and refuses on any difference. On v0.6.1's save of update 150: both 0 difference in his memory, 0 actions differ in 400 frames x 8 seats ✅ |
| The ramp | tested on a fake run folder (an update every 0.05 s): shut 10 updates, the cap 0.1 → 1.0 in ten steps, the head-open save at the first save 10 updates on, the rule 0.9 → 0 in ten steps, done ✅ |
| The judge's weapons edit | `tools/run/judge_weapons.py` reproduces `judge_v060_wpn.npz` from `judge_v060.npz` to the bit (and its log loss on all of v0.6.0's games: fitted 0.3747, edited 0.3753) ✅ |
| The judge's refit | after v0.6.1 ends: `fit_b.py duel_gru_v0_6_1 --boot 30`, acceptance as v0.6.1's (held-out log loss no worse than B2's interval and better than A; no axiom failure; the value table sensible; drift between saves within the intervals), then the weapons edit, then `tools/judge_ident.py judge` (the simulator's chance = the judge's) 🧪. **Tried on v0.6.1's first 150 games** (updates 40, 80, 120; 3 refits, 13 min on the four free cores): it runs; held-out log loss judge 0.3917, B2 0.3891 (−0.003, interval [−0.011, +0.004]), A +0.006 ([−0.008, +0.017]: not yet clearly worse with 150 games), axioms hold; a 100-damage hit +6.5 points at 5:00 level, a frag of a 20-hp enemy +12.1, a mega +19.3, a red armor +11.1; **the rocket launcher now priced on its own at +4.7 (wide interval), above the lightning gun's +2.1; the rail still near 0 (+0.3)**. The full refit (~300+ games, 30 refits) takes about an hour on a free PC |
| Not tested | the trainer with a head under today's code (the overlapped learner, the win pay, the brain's people lesson): the head was last trained in v0.4.4. No run on the graphics card while v0.6.1 holds it; a short CPU run of v0.6.2's command made small (2 workers, 8 matches, 96 steps; v0.6.1's judge; from v0.6.1's save of update 150), the head's gate forced open so its whole learning path runs: 103 updates in 12 min, no error, exit 0; the head's value and its own lesson learnt, its links rose from zero (plan 0.41, target 0.33), its bias' share of his target choice 0 → 9% (`data/sim_runs/scratch_v062_smoke`, kept). A learning check of the real size waits for the graphics card ✅ |
| Hand-built / assumed parts | the head's size, its inputs (all seven parts; the ctrl slot reads the brain's "in control" readout, not the one on the hands' memory), its two-minute value, its learning rate (as the hands'), its lesson's weight (1) and the plan's gradient (none); the ramp's schedule (ten steps each way, on the clock); the item rule's fade by its weight (its floor faded with it); the judge's form and the hand-set weapons |
| Weaknesses | the head starts knowing nothing, so in phase 1 it learns only where the rule's choice can be bettered; once the rule is gone his targets stand on the win pay and the head alone (v0.4.4's spawn camping came there); the head reads the brain's readouts, which are trained on self-play and the pro demos only; the checks are against v0.6.1's end, a network with the rule, so a loss there in phase 2 may be the rule's absence, not the head |
| Pay pathologies (ledger) | as v0.6.1's (the judge's axioms by construction); watched: lopsided games and negative scores in the self-play games |
| Watched (v0.6.1's logs the baseline) | his targets per map and their agreement with the item rule (`intent_rule_agree`, 0.71 at v0.6.1's end) and with the pros'; time camping and at spawns, roaming (20 to 27 cells a minute), hunting the watcher; the lightning gun's share (v0.4.4's head pushed it to 82%; 0.44 now); items (mega 0.8, red armor 0.95 a player-minute) |

## Start (after v0.6.1 ends, on the owner's go)

1. `python tools/run/fit_b.py duel_gru_v0_6_1 --boot 30 --out data/sim_runs/judge/judge_v061.npz --json data/sim_runs/judge/judge_v061.json`: the report to the owner.
2. `python tools/run/judge_weapons.py data/sim_runs/judge/judge_v061.npz data/sim_runs/judge/judge_v061_wpn.npz --set rg --run duel_gru_v0_6_1` (the rail only: owner, 2026-10-29). `WIN_JUDGE` names `judge_v061_wpn.npz`.
3. `powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.2\start.ps1`

## Later (reminder, not in this run)

The pro-demo fit of the head (the demo converter brought to 868 inputs, ~1 day): the fix if his targets drift once the rule is
gone. Rocket jumps and the failed movement jumps (Aerowalk's red armor): the full-route copies are built and kept off.

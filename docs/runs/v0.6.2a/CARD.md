# v0.6.2a: the strategy head faded in, on win chance only, from v0.6.1c's end

*2026-10-30 (owner): "We'll do v0.6.2a without them for now" (the pro demos); any run on win-chance pay carries the rescaling to
~10 a player-minute, "that is a given"; "Likely it will start from v0.6.1c, I'm expecting b to be a dead end"; hold judgement until
it has finished. **The line (owner, 2026-10-30): "v0.6.2 fades in v0.6.3 fades out. That's it"**: this run only fades the head in; the
item rule stays on and its fade moves to [v0.6.3](../v0.6.3/CARD.md). Earlier draft, from v0.6.1b's end: [v0.6.2](../../archive/versions/v0.6.2/CARD.md).*

**Marks:** ✅ built and tested · ⏳ waiting for v0.6.1c's end · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.6.1c's end with its optimizer (`keep/policy_end_v061c.pt`, kept by `start.ps1`), given the strategy head shut (`tools/head2_init.py add --gate 0`); the brain's dial stays at 1, the pull toward level off. **Unless it clearly loses** to v0.6.1b's end (see the comparison below) ⏳ |
| The head | `sim/head2.py`: a slow GRU (256) ticking with the brain every 0.2 s, reading the brain's memory and readouts, its "in control" readout, his stack, timers, score and clock, and the hands' memory; it adds a bias to his target choice and a plan into the hands' memory, both times its gate. It learns from its own value (two minutes) and its own lesson on the target choice; nothing of the hands moves it. ~0.65 M weights ✅ |
| Its start | from nothing: its links at zero, the gate at 0. **No pro-demo fit** (owner, 2026-10-30) ✅ |
| Pay | win chance only (`WIN_W` 1, `FADE_V` 1, `WIN_GAIN` as v0.6.1c's end), a game's result paid on its last frame (`WIN_END=1`) |
| The rescale | `--adv-pay-ref 10` (live `ADV_PAY_REF`), tau 5, cap 4, **no opening** (`--adv-pay-warm 0`): he is already at a factor of ~3, and opening from 1 would cut the pay's pull by two-thirds for 30 min. Benchmark: v0.6.0's pay only ✅ |
| The judge | `judge_v061_wpn.npz`, kept and frozen (owner, 2026-10-30: no refit in this run, one new thing at a time). Refit only if v0.6.1c's end numbers show the rail underpriced ✅ |
| Ramp | `tools/run/ramp_head.py`, on the clock: shut for 10 updates (the head's value learns the pay, it changes nothing), then `H2_GATE_CAP` +0.1 a step to 1, then **the head-open save kept** (`keep/policy_head_open_v062.pt`, 10 updates after the gate reaches 1), and the ramp is done (`RAMP_HEAD_ONLY=1`, tested on a fake run). The item rule stays at full weight (`INTENT_TEACH_W` 1). A step every 10 updates and at least 25 min ✅ |
| Timing | ~4 min an update: shut ~40 min, the head open ~7 h, the save ~40 min, then the rest with the head fully open: `--minutes 720` (**12 h**, the default; about 4 h with the head fully open) ❓ the owner sets the length before the start |
| Aim, mix, maps | as v0.6.1c (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps) |
| League | v0.6.1c's end and v0.6.0's end as anchors, then his own snapshots |
| Checks | every 10 updates, 160 games against v0.6.1c's end, every fourth against v0.6.0's end; the behaviour panel. The steps go on through a dip; **only a collapse (a check under 40%) is raised with the owner** (owner, 2026-10-30, for the fades). Never stopped |
| Judged | at the end, not along the way (owner, 2026-10-30). Play tests: the head-open save and the end |
| Logged | self-play games of every 40th save |

## Before the start

| Step | Where it stands |
|---|---|
| Files ✅ | `make_files.py` makes `train.cmd`, `start.ps1`, `smoke.py` from v0.6.2's: every pointer to v0.6.1c, the rescale added. `start.ps1` parses; no mention of v0.6.1b left in `start.ps1` or `smoke.py` |
| Settings check ✅ | `train.cmd` against v0.6.1c's: PASS, only `--run`, `--minutes`, `--adv-pay-ref` (8.5 → 10), `--adv-pay-warm` (30 → 0) and the head's six arguments differ. `aim2_env.cmd` identical. `start.ps1` refuses otherwise |
| v0.6.1c's end ⏳ | ~20:54. `start.ps1` refuses until its log ends in `exit` and keeps its end + optimizer |
| The comparison ⏳ | v0.6.1c's end, 160 games each against v0.6.1b's end, update 250 and v0.6.0's end, settings checked first. **Rule agreed in advance: start from v0.6.1c unless it is under ~45% against v0.6.1b** |
| Smoke run ⏳ | `smoke.py > smoke.log` (~12 min on the CPU; needs no trainer running): the head on the real faded end with its gate forced open: its value and lesson finite, its links up from zero, its bias a share of his target choice, the dial at 1, the rescale's factor above 1 from the first update and the target at 10. This command has never run on a faded brain. `start.ps1` refuses until `smoke.log` ends ALL PASSED |
| Identity ⏳ | `start.ps1` proves on the real end, gate at 1 and at 0, that adding the head changes none of his answers, and that the end carries the dial at 1 (`brain_fade_check`); it refuses otherwise. Passed on v0.6.1b's smoke save ✅ |
| The owner's go ❓ | after the comparison and the smoke run |

Then: `powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.2a\start.ps1`

## Red team

| | |
|---|---|
| What this run cannot show | whether the head can stand without the item rule: the rule stays on throughout, so spawn camping (v0.4.4) is v0.6.3's risk. The rule may also hide a head that adds little |
| Starts from nothing | with no pro fit the head can only reinforce what he does at first; it may be slow to find plans he never tries, and self-play may settle into habits people can exploit. Measured alternative: the pro-demo fit (the demo converter to 868 inputs, ~1 day), the fix if his targets drift or the head stops helping |
| The start's own state | v0.6.1c dipped during its fades (41.9% at u60, 46.9% at u70 against its start) and the recovery is not shown at the time of writing. If it ends bad, the comparison decides the start |
| Judging only at the end | a bad end alone cannot separate the head from the start. The checks against v0.6.1c's end and v0.6.0's end are there for this |
| The rail | no pay of its own; the judge's rail value is set by hand. Rail in hand slipped 0.17 → 0.145 in v0.6.1c with entropy flat. Pros hold it 14% with the enemy in view. The rescale cannot fix a low price |
| The head and the rescale | the rescale does not reach the head: it normalizes its own advantages and has no entropy term (read in the trainer), so the shrinking pay cannot drive it the same way. Its pull relative to the hands' is unmeasured |
| Hand-built / assumed | the head's size and inputs, its two-minute value, its learning rate, its lesson's weight (1), the ramp's schedule (ten steps, on the clock), the judge's form and rail value, the rescale's target (10) |
| Pay pathologies (ledger) | the judge's axioms by construction; watched: lopsided games and negative scores in the self-play games |
| Rocket jumps, movement jumps | important, not in this run: the full-route copies stay built and off |

## Watched

His targets per map and their agreement with the item rule (`intent_rule_agree`) and with the pros'; time camping and at spawns,
roaming (20 to 27 cells a minute); the lightning gun's share (v0.4.4's head pushed it to 82%); rail in hand; items (mega, red armor);
entropy, `adv_pay.k`, KL, clip share.

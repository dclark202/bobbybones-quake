# v0.6.1e: from v0.6.1's update 90, the original pay table to half and win chance to half over 40 updates, then the pull and the brain's old belief faded together

*2026-10-31 (owner): "go back further in the v0.6.1 where combat was 50% and then fade to the final proportions from there"; "extend the fade to longer, 40 updates"; "Old pay table 50%, win chance 50%", the table's proportions unchanged, total ~10; 12 h; "go with this plan". Why: [v0.6.1d](../v0.6.1d/CARD.md)
kept only 20% of the combat pay; it did not test half the table.*

| | |
|---|---|
| Network | v0.6.1's save of update 90 (`duel_gru_v0_6_1/keep/policy_90.pt`): combat already at 50% (`WIN_W` 0.5, `FADE_V` 0.125, `WIN_GAIN` 0.33), 1.62 frags a match-minute, rail in hand 0.21 |
| Optimizer | v0.6.1's end's, borrowed (from 250 updates later): that save kept none |
| Pay | every term of the original table unchanged. `WIN_W` stays **0.5** (half of combat). Over updates 1-40, twenty steps, one every 2 updates (`ramp_fades.py`): `FADE_V` 0.125 -> **0.5** (half of the other pays), `WIN_GAIN` 0.33 -> **0.87**. Old / win paid: ~5.6 / 1.6 -> ~4.1 / 4.1. Judge `judge_v061_wpn` + `WIN_END` as c and d |
| The gain | set so win pay matches the old part: other 3.97 x 0.5 + combat 4.2 x 0.5 = ~4.1 = 0.5 x G x ~9.4. Kept level live: once the pay's fade is done (from update 50), at each hourly check, if they are over 20% apart, `WIN_GAIN` x old / win, at most 25% a change, logged below |
| The rescale | `--adv-pay-ref 10`, opened over 30 min (factor ~1.4, ~1.2 at the end) |
| The fades | from update 40, as c and d: `LEVEL_PULL` 0.95 → 1 and `BRAIN_FADE` 0 → 1 in the same write, eight steps after saves, to ~update 120 (~8 h), then ~4 h to settle. Only a check under 40% is raised with the owner |
| Length | `--minutes 720` (owner: 12 h) |
| League, checks | as d: this start and v0.6.0's end as anchors; 160 games every 10 updates against the start, every fourth against v0.6.0's end; the panel |
| Kept | `keep/policy_prefade_v061e.pt`, the saves every 10 updates; at the end `keep/policy_end_v061e.pt` + `opt_end_v061e.pt` |

**Judged by:** at least 50% against the start and v0.6.0's end in the last checks, frags and time in fights up on d's, the panel, and the owner's play test.
Under ~45% after 30 settling updates fails: then isolate the fades.

## Before the start

The settings check against d's command passes with only `--run` and `--minutes` different. The owner's go: "Ok do it". `go.py` runs the
smoke test and then `start.ps1`, which refuses on any failed check.

## Red team

| | |
|---|---|
| The pay's move | win pay rises ~2.6 × over 40 updates, against ~2.7 h; combat never moves, so he should not have to relearn it. Only ~4 h after the fades to settle: a late recovery may not show |
| Three things at once | the pay, the pull and the brain: a dip cannot be traced to one. The owner's choice; isolate if it fails |
| Speed | stays in the table at half; d's speed-over-fighting idea is untested and `SPEED_LOS=1` pays it only with the enemy out of sight |
| Judge | the refit judge and `WIN_END`, not what that save trained on (win at gain 1 ~9.4 against 12.8): untested alone |
| Evidence | that combat pay is the cause of the passivity is a guess from d's numbers. The rail's fall has no confirmed cause and this may not touch it |
| Old pay | a later fade to less old pay may bring back the slide |
| Borrowed optimizer | from 250 updates later, Adam's step sizes only |

## Stopped 2026-10-31 at update 30 (owner)

Owner: "At the next save, stop v0.6.1e and save the optimizer. Might resume if my other idea doesn't work." Stopped during the pay's fade, before the pull and brain fades began. Kept: `keep/policy_end_v061e.pt`, `opt_end_v061e.pt`, `live_end_v061e.json`. To resume: restore the live settings and the rest of `ramp_fades.py`'s schedule from where it stopped.

## Stopped 2026-10-31 ~10:17 at about update 30 (owner)

The owner replaced the v0.6.1 line with b1 ([b1.0a](../b1.0a/CARD.md)). Its checks against the start: 44.4% at update 10, 52.5% at update 20. `FADE_V` had reached 0.39 and `WIN_GAIN` 0.71, and the fades had not begun, so it answers nothing it set out to test. Its end: `keep/policy_end_v061e.pt`.

## Changes on the fly

| Time | Change | Why |
|---|---|---|

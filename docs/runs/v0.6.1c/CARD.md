# v0.6.1c: back to v0.6.1's update 250, the advantages rescaled, the pull and the brain's old belief faded together

*2026-10-30 (owner): "reverting to v0.6.1 u250 is the right call ... fade level pull out, fade brain hard code out, both
concurrently over the first 5-6 hrs, let it train for 12 hrs total, use rescaled advantages to keep the entropy down ... The
creeping entropy and lowering rail has me concerned." Why: [the drift](../v0.6.1b/DRIFT.md). v0.6.1b ended a no-go
([REPORT_0630.md](../v0.6.1b/REPORT_0630.md)) and was stopped at update 181.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.6.1's save of update 250 (`duel_gru_v0_6_1/keep/policy_prelevel_v061.pt` = `policy_250.pt`): the win pay faded in, the pull toward level still on (0.95) |
| Optimizer | that save kept none. v0.6.1's end's (`opt_end_v061.pt`, 90 updates later, same weights' shapes) as the nearest estimate of Adam's step sizes, rather than a cold start ❓ |
| New 1: rescaled advantages | `--adv-pay-ref 8.5`: his advantages (not the value targets) × 8.5 / the pay's size a player-minute in games (a running mean over 5 updates), so the pay's pull on his choices against the fixed entropy bonus is v0.6.0's whatever the judge or `WIN_GAIN`. With today's judge the factor is ~2.6. Opened from 1 over the first **30 min** (`--adv-pay-warm 30`; owner: "Open the rescaling faster"), kept within 1/4 .. 4. The target is **live** (`ADV_PAY_REF` in live.json, from the next update) |
| New 2 + 3: the fades | `LEVEL_PULL` 0.95 → 1 and `BRAIN_FADE` 0 → 1 (`--brain-fade 1`), in the same write, eight steps, one right after each save (every 10 updates, at least 25 min apart): from ~40 min to ~5.3 h (update 80) (`tools/run/ramp_live.py --also`) |
| Pay | win chance only, as v0.6.1 (`WIN_W` 1, `FADE_V` 1, `WIN_GAIN` 0.33); the judge `judge_v061_wpn.npz` (refitted on v0.6.1's games, the rail set by hand, as v0.6.1b); the game-end fix `WIN_END=1` |
| Length | 12 h (`--minutes 720`) |
| League | the start (update 250) and v0.6.0's end as anchors, then his own snapshots |
| Checks | every 10 updates, 160 games against the start; every fourth against v0.6.0's end; each save at its own pull and dial; the behaviour panel. Under 40% flagged, under 30% posted. Never stopped |
| Kept | `keep/policy_prefade_v061c.pt` (the first save, before the first step); the end as `keep/policy_end_v061c.pt` |

## The pay against the entropy bonus

| | Pay size a player-minute | Bonus per unit of pay | Entropy |
|---|---|---|---|
| v0.6.0 (flat pay) | 8.5 | 0.0006 | flat (1.73 → 1.76) |
| v0.6.1 win chance only | 4.3 | 0.0012 | 1.83 → 1.92 |
| v0.6.1b | 3.3 | 0.0015 | 1.93 → 1.99 |
| v0.6.1c (rescaled) | 3.3 × ~2.6 | 0.0006 | 🧪 |

## Before the start

| Step | Where it stands |
|---|---|
| The rescaling ✅ | `sim/train_duel_rnn.py`: `--adv-pay-ref` (0 = off: no line of the old path runs differently), `--adv-pay-tau`, `--adv-pay-max`, `--adv-pay-warm`, live `ADV_PAY_REF`; the factor from the rollout's `win_blend` counters before the advantages are made, applied right after `gae_()` in both paths (decoupled and not); `adv_pay` in `metrics.jsonl` (k, the size, its running mean) |
| The paired ramp ✅ | `tools/run/ramp_live.py --also NAME:FROM:TO:STEP`: tested on a fake run (eight saves: both reached 1 together, the first save kept) |
| Settings check ✅ | `train.cmd` (made by `make_cmd.py` from v0.6.1b's) against v0.6.1b's: only `--run` and the four `--adv-pay-*` differ |
| Smoke run ⏳ | `smoke.py` (CPU, ~15 min): the factor 1 at the start, above 1 after its opening; both fades stepped to 1 live; `ADV_PAY_REF` 8.5 -> 12 taken live; the save carries the dial; `brain_fade_check`; `test_suite.Policy`. `start.ps1` refuses until `smoke.log` ends ALL PASSED |

## Red team

- **Three new things at once** (the rescale, the pull's fade, the brain's fade). The owner chose this. A dip cannot be traced to
  one of them; the brain's fade alone cost nothing in v0.6.1b, and the pull's fade alone cost a little in v0.6.1.
- **The factor is 2.6 against what update 250 was trained at** (2× the pay it had seen since ~update 150). The policy's steps on
  the pay grow by that much, while the other lessons on his shared layers (the item rule's floor, the aux questions) count
  relatively less. It opens over 2 h. KL and the clip share are watched in the first updates.
- **8.5 is a pay size, not an advantage size.** Win pay is smoother than flat pay, so the right target may be higher. The test
  is entropy flat or falling; the target is live (`ADV_PAY_REF`) and moved by the rules below.
- **The optimizer is borrowed** from 90 updates later. Adam's step sizes for the same weights, close but not this network's.
- **The rail** may also be down because its own pay is gone (`RAIL_FAR_PAY`, faded with every other pay). The rescale does not
  bring that back; if the rail keeps falling with entropy flat, the judge's price of the rail is next.
- **Pay pathologies (ledger):** as v0.6.1: the judge's axioms by construction; watched for negative scores, sign flips,
  lopsided games in the self-play games.

## Watched

Entropy, `adv_pay.k`, rail in hand and shots, lightning gun and rocket shares, megas and red armors (the panel's red share),
frags a minute, the brain's scores, KL and clip share in the first 20 updates, the checks.

## On the fly (owner, 2026-10-30: "make sure the win chance pay is not fading in time like before. I'm fine with more aggressive
scaling"; updates at 30, 60 and 90 minutes)

Rules set before the start, each change logged in the card and `watch/watch.log`:
- **The pay's pull holds**: `adv_pay.k` × the pay's size (`win_blend.paid_size`) stays near `ADV_PAY_REF`. If the size keeps
  falling and k reaches its cap (4), it is reported (the cap is not live).
- **Entropy** (from update 250's ~1.87): after the opening (30 min), if the mean over 5 updates is still rising across 10
  updates, `ADV_PAY_REF` 8.5 → 11; again → 14. If it falls by more than 0.15 in 10 updates, or KL goes over 0.05, or the clip
  share over 0.45, it steps back one notch.
- **The checks** (owner, 10-30 11:45: "just go through the fade without stopping unless the win rate collapses. I do not want
  you to fold the fade from stepping though for something like 79-81"): the fades step through to the end; they hold only if
  the win rate collapses (a check under 40% against the start), then the owner is asked. The rescale stays.
- Nothing stops the run.

| Time | Change | Why |
|---|---|---|
| 10-30 09:19 | `ADV_PAY_REF` 8.5 → **8.63** (live) | owner: "Use the pay size from v0.6.0 as a benchmark. Do not benchmark on the pay from anything with win chance". v0.6.0's `win_blend.paid_size` over its 80 updates: mean 8.63, median 8.64, 8.07-9.30 |
| 10-30 09:21 | `ADV_PAY_REF` 8.63 → **10** (live) | owner: "Round it up to 10, that's a good target to aim for". The rules' ladder from here: entropy still rising → 12 → 14; a notch back → 8.63 |
| 10-30 10:24 | none (90-min review) | entropy u13-22 mean 1.86 (u250 1.87): no rise; kl 0.031, clip 0.334. Raw pay sliding 4.25 -> 3.64 (k 2.75): cap 4 reached at ~2.5 if it goes on; asked the owner about a live WIN_GAIN step then |
| 10-30 11:45 | the fades' hold rule: only a collapse (a check under 40%) holds them | owner: "just go through the fade without stopping unless the win rate collapses". Was: under 45% or two under 50% |

## Stopped 2026-10-30 17:28 at update 130 (owner)

Owner: "Save this as v0.6.1c end with the optimizer and then start v0.6.1d when it's ready". Stopped right after the save of update 130 (the log's `exit 1` is the stop). At the stop: 43.1% against the start (u90) and against v0.6.0's end (u110), entropy ~1.94 (start 1.87), rail in hand 0.125. No-go as it stands.

## At the end (owner, 2026-10-30)

- Keep the end as `keep/policy_end_v061c.pt` + `opt_end_v061c.pt` (`v0.6.2a`'s `start.ps1` does it if not done).
- Measure it, 160 games each, settings checked first: against v0.6.1b's end (`keep/policy_end_v061b.pt`), update 250
  (`policy_prelevel_v061.pt`) and v0.6.0's end. Start v0.6.2a from v0.6.1c unless it is under ~45% against v0.6.1b.
- Rail: is it a real loss? In hand with the enemy in view against the pros' 14%, and games lost at long range. If so, refit the
  judge's rail value before v0.6.2a; otherwise the judge stays.
- Next: [v0.6.2a](../v0.6.2a/CARD.md). Judged when it has finished, not before.

# v0.6.1d: the pull and the brain's old belief faded out, on a blend of the old pay and the win pay

*2026-10-30 (owner): "Prepare the 50/50 blend to run overnight after this one is done. Call it v0.6.1d ... Ideally the PAY for the
original item rules and the win chance should be roughly equal." Why: v0.6.1c's checks fell to ~44% against its start once the pay was
win chance only and the fades ran; in v0.6.1 his best stretch was while the pay was still a blend (below).*

**Marks:** ✅ built and tested · ⏳ waiting · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Network | v0.6.1's save of update 110 (`duel_gru_v0_6_1/keep/policy_110.pt`), just after `FADE_V` reached 0.5; the pull on, the brain's old belief on |
| Optimizer | that save kept none: v0.6.1's end's (`opt_end_v061.pt`), borrowed as in v0.6.1c |
| Pay | held: `WIN_W` 0.8, `FADE_V` 0.5, `WIN_GAIN` 0.35: the save's own dials, the gain set for equal pay with today's judge (below) (the card's defaults, the owner's go) |
| Same as v0.6.1c | owner, 2026-10-30: identical to v0.6.1c except the start, slightly earlier in v0.6.1 where the two pays are about equal, and the gain kept matching them. The settings check allows only `--run` and `--adv-pay-ref` |
| The gain, on the fly | **`WIN_GAIN` keeps the two pays about equal as the run goes** (owner): from update 30 (the win pay settles over the first 20 to 30), at each hourly check, if the win paid and the old paid (means over 10 updates) are more than 20% apart, `WIN_GAIN` x old / win, at most 25% a change, live, logged here and in `watch/watch.log` |
| The rescale | `--adv-pay-ref 10`, opened over 30 min (his factor was 1 at that save, ~1.8 here), tau 5, cap 4 |
| The judge | `judge_v061_wpn.npz` and `WIN_END=1`, as v0.6.1c. That save trained on `judge_v060_wpn` without `WIN_END` |
| **What it trains** | **the point of the run (owner, 2026-10-30): fade out the pull and the brain's hard-coded belief while part of the pay stays rule-based beside the win pay** |
| The fades | together, as v0.6.1c (owner, 2026-10-30: "Just keep them together. We'll isolate if v0.6.1d fails again"): `LEVEL_PULL` 0.95 → 1 and `BRAIN_FADE` 0 → 1 in the same write, eight steps, one right after each save, at least 25 min apart (`ramp_fades.py`): ~40 min to ~5.3 h, then ~10 h to settle. Only a check under 40% is raised with the owner |
| Length | to noon on 10-31 (extended, below); first `--minutes 915`: until ~9:00 on 10-31 from a start ~17:45 (owner, 2026-10-30: "let it run until 9am tomorrow"; v0.6.1c stopped early at his word) |
| League | the start and v0.6.0's end as anchors, then his own snapshots |
| Checks | every 10 updates, 160 games against the start, every fourth against v0.6.0's end; the panel. Under 40% flagged. Never stopped |
| Kept | `keep/policy_prefade_v061d.pt`; the end as `keep/policy_end_v061d.pt` + `opt_end_v061d.pt` |

## The pay at equal sizes

A frame in a game pays `(1 - FADE_V) x other + (1 - WIN_W) x combat + WIN_W x WIN_GAIN x win`. `other` is the item flats and the rest of
the hand-built pays; `combat` is the flat frag, death and damage pay. Sizes a player-minute, measured:

| | Combat | Other | Win at gain 1 | Old paid | Win paid | Win share |
|---|---|---|---|---|---|---|
| v0.6.1 u110 (judge v060, gain 0.33) | 4.22 | 3.96 | 12.49 | 2.82 | 3.30 | 54% |
| v0.6.1d (judge v061, gain 0.35) | ~4.2 | ~3.9 | ~10 (v0.6.1c) 🧪 | ~2.8 | ~2.8 | ~50% |

The gain is set from v0.6.1c's settled pay and is measured again by the smoke run and in the run's first 30 updates (the win pay starts
high in every run and settles over 20 to 30 updates). With the rescale the total feels like 10, about 5 and 5.

## Why this point: v0.6.1 against v0.6.0's end

| Updates | Pay | Average | Entropy | Rail in hand |
|---|---|---|---|---|
| 30-70 | mostly old | 52.7% | ~1.80 | 0.22 → 0.20 |
| 90-140 | blend | 56.4% | ~1.78 | 0.20 → 0.19 |
| 160-250 | win chance only | 50.6% | 1.83 → 1.87 | 0.18 → 0.15 |

## Before the start

| Step | Where it stands |
|---|---|
| Files ✅ | `make_files.py` makes `train.cmd`, `start.ps1` from v0.6.1c's |
| Settings check ✅ | against v0.6.1c's command: only `--run` and `--adv-pay-ref` (8.5 → 10). `start.ps1` refuses otherwise |
| v0.6.1c's end ⏳ | ~20:54. `start.ps1` refuses while a trainer runs |
| Smoke run ⏳ | `smoke.py > smoke.log` (~12 min on the CPU), after v0.6.1c ends: the blend taken live, the rescale, both fades stepped to 1, the sizes printed. `start.ps1` refuses until it ends ALL PASSED |
| The owner's go ✅ | 2026-10-30: "Schedule this to run starting after c finishes, for 12 hours". `after_c.py` (running) waits for v0.6.1c's end, keeps it, runs the smoke run and then `start.ps1`; a failure stops it there (`after_c.log`) |

## At the end

The candidates for v0.6.2a, 160 games each with settings checked: v0.6.1b's, v0.6.1c's and v0.6.1d's ends, and v0.6.1's update 250. If it fails too: isolate the fades one at a time (owner).

## Red team

| | |
|---|---|
| The evidence | the 56.4% is a stretch picked after seeing the numbers, about 2.4 times the noise, and u10 read 59.4% before any win pay. It was also a moving mix over a few hours: a held blend is untested |
| Not the same pay | the judge is newer and the game-end fix is in, so the win part is not what that save saw. Measured alternative: `judge_v060_wpn` and no `WIN_END`, closest to the evidence but with the known last-frame error |
| The old pays stay | they can be pumped or steer him (the item flats, `RAIL_FAR_PAY`, `WATCH_PAY`, speed); the blend's equilibrium is win most games plus collect the old pay, not win most games alone. A later fade to win chance only may bring back the same drop |
| The rescale is new here | v0.6.1's blend ran at factor 1; here ~1.8. Pay's pull against the entropy bonus is higher than in the evidence, and against the other lessons too. KL and clip watched |
| The rail | was already slipping during the blend. `RAIL_FAR_PAY` returns at half weight, which may slow it |
| Three things at once | the held blend (untested), the pull and the brain, as in v0.6.1c: a dip cannot be traced to one. The owner chose this; if it fails, they are isolated next |
| The optimizer is borrowed | from 230 updates later, Adam's step sizes only |
| Hand-built / assumed | the blend's dials, equal sizes as the target, the gain, the rescale's target |
| Pay pathologies (ledger) | negative scores, sign flips, lopsided games in the self-play games; the item flats' farming: time at spawns in the panel |

## Watched

Which fade each check falls in; old and win paid sizes (`win_blend`), entropy, `adv_pay.k`, rail in hand, the lightning gun and rocket shares, megas and red armors, the
panel, KL and clip share, the checks against the start and v0.6.0's end.

## Stopped 2026-10-31 07:5x at about update 219 (owner)

Owner: "Stop v0.6.1d now". Its end is its last save, 07:18 (`keep/policy_end_v061d.pt` + `opt_end_v061d.pt`); `extend_noon.py` was stopped too, so no resume and no c/d comparison ran. **The setting was not what was asked:** the old pay was meant to be half of each part, but `WIN_W` 0.8 kept only 20% of `combat` (`FADE_V` 0.5 kept half of `other`); only the totals were equal. v0.6.1e replaces it.

## The owner's play test (2026-10-31, the end, on a local server)

"He was better than the numbers gave him credit for." The biggest part: "he lost his aggression a bit". Behaviour changes were visible when down by a lot with about a minute left. Logs: `data/duellive_v061d/`.

Two games at `!aim better`, the owner won 23-3 (Aerowalk) and 30-2 (Toxicity, forfeited). Read from the logs: he lost on stack, not aim. Mean stack alive 107 and 117 against the owner's 214 and 223; he began 131 of 167 sight-fights 25 or more behind, with 1 kill and 36 deaths in them, and 12 to 13% of fights ahead. Lightning accuracy 34% against 35%, rockets 42% against 46% (Toxicity). Red armor on Aerowalk 0 of 15, mega on Toxicity 1 of 11, the rocket launcher in hand 17 to 32% against 63 to 72%, the machine gun 14 to 24%. Median life 13 to 17 s. One person, two games.

## Changes on the fly

| Time | Change | Why |
|---|---|---|
| 10-31 07:25 | run extended to noon (`extend_noon.py`): at the ~08:56 end, saved, resumed from that save and optimizer to 12:00 with `--adv-pay-warm 0`; then 160 games, d's end against c's end | owner: "extend this run v0.6.1d to noon to watch the performance. And then run the comparison c/d afterwards" |

# b1.0a: win chance pay added on top of the pay table, from v0.6.0's end

*2026-10-31 (owner): win chance pay is "purely additive (or subtractive)" on the table we have, about a third of the total, changeable on the
fly. It answers two concerns: "He is not incentivized to win (under v0.6.0 pay)" and "Items have no conditional value to them".
The plan: [B1_PLAN.md](../../../design/B1_PLAN.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | v0.6.0's end with its own optimizer (`duel_gru_v0_6_0/keep/policy_end_v060.pt`, `opt_end_v060.pt`) ✅ |
| Run | `duel_gru_b1_0a` |
| Pay | `paid = other + combat + A x win`. The table is untouched (`WIN_W` 0, `FADE_V` 0). A is the new live dial `WIN_ADD` ⏳ |
| The win part | scale x the change in his chance of winning, each frame. Can be negative, zero-sum between the seats; a game's total is scale x (result - start chance), so it cannot be pumped |
| Target | A = **0.33**: win ~4.3 a player-minute beside the table's ~8.45, about a third of the total. Live in `live.json`, read between rollouts |
| Ramp | shut to update 10; 0 → 0.15 over updates 10 to 40; held through update 50's check; 0.15 → 0.33 over updates 50 to 80; held to the end. Steps every 2 to 3 updates |
| Hold rule | (owner, 2026-10-31: "Dont stop the ramp for anything >40%, but flag them here") the ramp goes on above 40%, and any check under 50% is flagged in the chat. A check of 40% or less holds the ramp and is raised with the owner |
| The judge | `judge_v060_wpn.npz`, fitted on this start's own games, rocket and rail at the lightning gun's worth by hand, frozen. `WIN_END=1` ✅ |
| The rescale | off (`--adv-pay-ref 0`), as v0.6.0: it was built for a pay that shrank, and this one grows. An exception to the rule of 10-30 ❓ |
| Everything else | v0.6.0's command exactly: pull on, brain's old belief on, item rule on, no head; 65% games, 35% pro starts; `!aim default` |
| Length | to ~9:00 on 11-01 by default (owner, 2026-10-31; `--minutes` set at the start, about 22 h, ~330 updates). If it looks reasonable this evening, the owner may end it early and start the level pull fade overnight |
| League | v0.6.0's end and v0.4.2b's end as anchors, then his own snapshots |
| Checks | every 10 updates, 160 games against v0.6.0's end only (owner, 2026-10-31); the panel. Never stopped |
| Kept | `keep/policy_end_b10a.pt` + `opt_end_b10a.pt`, the saves every 10 updates |
| Logged | self-play games of every 40th save |

## Judged by

| | v0.6.0's end | v0.6.1d's end | b1.0a's last checks |
|---|---|---|---|
| Frags a match-minute | 1.75 | 1.32 | at least 1.6 |
| Rail in hand | 0.22 | 0.09 | at least 0.18 |
| Entropy | 1.76 | 1.87 | at most 1.82 |
| Against v0.6.0's end | | 50 to 67.5% | at least 52%, mean of the last four |
| The win pay's own effect | | | win rate above frag share; frags while leading hold |

Then the owner's play test. The floors are proposals, set by hand from these two runs.

## What it pays at A = 0.33 (computed from this judge)

The total for a frag (both 125/50 before it) and the win pay added to an item's flat pay (he 100/0, the enemy 100/50):

| Lead, time left | Frag total | Red armor: 0.30 + | Mega: 0.35 + | Yellow: 0.15 + | Big weapon: 0 + |
|---|---|---|---|---|---|
| level, 10 min | 1.72 | 0.62 | 0.52 | 0.40 | 0.09 |
| level, 5 min | 2.22 | 0.91 | 0.64 | 0.59 | 0.18 |
| level, 1 min | 3.53 | 1.32 | 1.25 | 0.85 | 0.65 |
| +1, 1 min | 1.92 | 0.82 | 0.78 | 0.57 | 0.46 |
| -1, 1 min | 3.97 | 0.70 | 0.65 | 0.40 | 0.30 |
| +3, 1 min | 1.05 | 0.05 | 0.05 | 0.04 | 0.03 |
| -3, 1 min | 1.37 | 0.04 | 0.04 | 0.02 | 0.02 |
| +6, 2 min | 1.01 | 0.01 | 0.01 | 0.01 | 0.01 |

## The equilibrium

- **Combat and damage:** zero-sum, unchanged. Fighting keeps paying at every score, so a decided game still teaches aim.
- **Item pay:** positive-sum, unchanged. Both copies gain from collecting, as in v0.6.0.
- **Win part:** zero-sum, unpumpable. Its fixed point is winning more often.
- **Together:** v0.6.0's play, with fights and items priced up when the game is close and down to the table's flat pay when it's decided. Expected on the way: more contest of items and more risk when close and late.
- **Wins more games long-term?** That's what this run tests: only if close games convert better with base skill intact.

## Red team

| | |
|---|---|
| The theory may be wrong | v0.6.1d looked worse (frags 1.32, rail 0.09) and still read 59.4 / 67.5 / 60.0 / 50.0% against v0.6.0's end. The run's checks do not play d (owner: v0.6.0's end only), so this stays open unless a head-to-head is asked for at the end |
| "Incentive to win" is the judge's | the hands look ~25 s ahead, so the game-end pay barely reaches them. Their incentive is the judge's prediction by score and clock, and it is only as good as the judge. The head (2 min) is the next step for that |
| Conditional, not complete | items are priced by score, clock and stacks. **Denial is not priced:** taking the armor so that he doesn't get it pays only through his own stack. Nor is timing or position. Those wait for the head |
| Item prices are the judge's | fitted on one run's self-play; level at 1 min pays a red armor 1.32, and items that late may be worth less than that. Big weapons are hand-set, equal and low early (0.09) with no flat pay: nothing new lifts the rail |
| Sitting on a lead | the clock alone pays the leader a little each frame, unmeasured. The table should offset it. Watched: frags while leading |
| Late over-trading | up to ~4 for a kill when behind late |
| Run length | no flat run has gone past 170 updates; a slide may be length rather than pay. Then the next arm is v0.6.0 flat for 12 h |
| Total pay rises | ~8.45 → ~12.7 raises the pay's pull against the entropy bonus and the fixed lessons (item rule, aux), and the critic has a new part to learn. Watched: KL, clip share, value loss |
| Win may do nothing | at a third, the effect may be lost in the noise. Then A 0.5 as b1.0b, not a new design |
| Self-play is not people | the play test is the only other signal |
| Hand-built / assumed | the target, the ramp, the hold rule, the judge's form and hand-set weapons, the anchors, the floors |
| Pay pathologies (ledger) | no negative frags by the judge's axioms (lowest total 1.0). Watched: lopsided games, sign flips, armor hoarding |
| Rocket jumps, movement jumps | important, not in this run |

## Before the start

| Step | Passes when |
|---|---|
| The dial ⏳ | `WIN_ADD` in `sim/duel_env.py`, a live name; `tools/make_ffa_env.py`, `tools/ffa_check.py` |
| Identity ⏳ | A = 0: a fixed-seed run matches today's to the bit. A > 0: paid - A x win is the old pay exactly |
| The ramp ⏳ | `ramp_win.py` with the hold rule, tested on a fake run folder |
| Files ⏳ | `train.cmd`, `start.ps1`, `smoke.py`, from v0.6.0's command |
| Settings check ⏳ | against `docs/runs/v0.6.0/train.cmd`: only `--run`, `--minutes`, `WIN_JUDGE`, `WIN_END` and the readouts' start minutes differ |
| Smoke run ⏳ | ~12 min on the CPU: the dial taken live, sizes printed, the save loads |
| v0.6.1e ✅ | ended at its save of 10:17 (update ~30); no trainer running |
| The owner's go ❓ | |

Then: `powershell -ExecutionPolicy Bypass -File docs\runs\b1.0a\start.ps1`

## Stopped 2026-10-31 21:00 at update 160 (owner)

"Calling b1.0a a success." Against v0.6.0's end 61.9 / 53.8 / 55.6 / 58.8 / 49.4 / 56.2 / 55.6 / 55.0% at updates 10 to 150 (a save every 20; `WIN_ADD` 0.33 from update 80). End: frags 1.61 a match-minute, rail in hand 0.14, entropy 1.84. The owner: "he's better than any of the v0.6.1x bots"; his biggest weakness, tunnel vision on items. Its end: `keep/policy_end_b10a.pt` + `opt_end_b10a.pt`. Gates missed: rail (floor 0.18) and entropy (ceiling 1.82); both were set by hand, and the entropy comparison showed it is a poor gate.

## The owner's play test (2026-10-31 ~20:00, the save of update 140, on a local server)

"This bot is good ... he's better than any of the v0.6.1x bots." "His biggest weakness is that he's getting tunnel vision on getting items instead of fighting." The owner won 21-0 (Blood Run, `!aim default`) and 12-0 (Furious Heights, `!aim better`, forfeited). Read from the logs: mean stack alive 133 and 166 against 231 and 198; with the owner in sight within 800 units he aims more than 30 degrees off 25 to 30% of the time (the owner 15 to 18%), fires 32 to 42%, and moves away at 17 to 34 u/s. Logs: `data/duellive_b10a/`. Different maps from v0.6.1d's games, so not directly comparable.

## Changes on the fly

| Time | Change | Why |
|---|---|---|

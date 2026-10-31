# Why win-chance training drifts (2026-10-30 morning)

*The owner, 2026-10-30: "This seems to be a problem with win chance training then, because he has started this drift before
now. Can you look into that this morning." Read-only: the metrics of v0.6.0 (`duel_gru_v0_6_0`), v0.6.1 (`duel_gru_v0_6_1`) and
v0.6.1b (`duel_gru_v0_6_1b`). Nothing was run or changed.*

## Finding: the pay got smaller and the exploration bonus did not

The trainer does not normalize advantages (`sim/train_duel_rnn.py`, `gae_()`; the loss is `pg + 0.5 vl - ent_coef * en`). So
the pull of the pay on his choices scales with the size of the pay, while the entropy bonus (`--ent-coef 0.005`) stays fixed.
Win-chance training cut the size of the pay in half, and v0.6.1b's judge cut it again:

| | Pay after the blend, size a player-minute (`win_blend.paid_size`) | Entropy | Rail in hand (games) | Rail shots a minute | Frags a match-minute |
|---|---|---|---|---|---|
| v0.6.0 (flat pay) | 8.4-8.8 | 1.73 → 1.76 | 0.23 → 0.22 | 2.3 → 2.1 | 1.87 → 1.77 |
| v0.6.1 u1-120 (the win pay fading in) | 8.3 → 6.0 | 1.78 → 1.79 | 0.21 → 0.19 | 2.0 → 1.8 | 1.63 → 1.57 |
| v0.6.1 u160-340 (win chance only) | **4.2-4.4** | 1.83 → 1.92 | 0.19 → 0.12 | 1.8 → 0.9 | 1.49 → 1.37 |
| v0.6.1b (the refitted judge, `WIN_GAIN` 0.33 kept) | **3.3** | 1.93 → 1.99 | 0.10 → 0.07 | 0.8 → 0.5 | 1.32 → 1.38 |

- `WIN_GAIN` was sized in v0.6.1 so the win part matches the **combat pay** (frags, deaths, damage: size ~4.1). The old total was
  combat plus the **other pays** (items, speed, rail, watching: size ~3.9), which `FADE_V` 1 removed. So the total halved.
- The refitted judge (`judge_v061_wpn.npz`) moves less per event: the win part at gain 1 is 10.2 in size against 13.0 with
  v0.6.0's judge. `WIN_GAIN` stayed at 0.33, so the pay fell another 22%. Nobody resized it.
- Relative to the pay, the exploration bonus is now about **2.6 times** as strong as in v0.6.0. The drift fits that: entropy
  rises steadily from the point where the pay halved (v0.6.1 ~u150), and the skills that need fine credit (the rail: aim and
  timing) go first. The skills with big, fast pay (megas and red armors picked up, 0.80 and 0.94 a player-minute) do not move.

## What was ruled out or does not explain it

- **The brain:** its scores held or improved through v0.6.1b (REPORT_0630.md).
- **The critic:** the judge's value explains 0.84-0.86 of the variance throughout; `win_value` is steady.
- **PPO's step:** the clip share (0.32-0.34) and KL (0.031) are the same in v0.6.0 as now.
- **The game-end fix:** the drift began in v0.6.1, before it.
- **Self-play cycling:** he beats his recent snapshots (0.52 kill share) while losing to the fixed anchors. That fits a slow
  drift shared by every snapshot. It is a symptom, not a separate cause.

## Not settled

- The total pay size measures the reward, not the advantage. Win pay is smoother than flat pay, so its advantages may be
  smaller still (the effect stronger) or less noisy (weaker). Only an arm can tell.
- **The rail's own price:** under flat pay the rail had its own pay (`RAIL_FAR_PAY` 0.12, faded by `FADE_V`). The judge prices
  owning it by hand and its use only through damage. Part of the rail's fall may be the real worth of the rail in the judge's
  eyes, not the entropy. If the rail keeps falling once the exploration bonus is back in scale, it is the price.

## The fix, and what each choice leads to

All three leave the equilibrium unchanged: win chance only. A positive scale does not change which policy wins. Only the
balance between exploring and exploiting moves back toward v0.6.0's.

1. **Lower `--ent-coef` in proportion to the pay:** 0.005 × 3.3 / 8.6 ≈ **0.002** (0.0025 for v0.6.1's judge). This is one
   argument, a restart at a save. It leaves the value loss's scale as it is. **Recommended.**
2. **Raise `WIN_GAIN` to restore the pay's size:** 0.33 → ~0.85. This is live, but it multiplies the value loss by ~6 in the
   shared layers, and the critic must relearn its scale. A shift of its own.
3. **Normalize advantages:** scale-free from then on, so no judge refit can shift the balance again. It is the principled fix,
   but it changes the balance of every head and lesson at once. A later version, not a patch.

Whichever is chosen, `WIN_GAIN` (or the coefficient) should be re-sized at every judge refit. Today nothing checks it.

## The test before v0.6.2 (on the owner's go; the graphics card is free after v0.6.1b ends ~08:00)

Two arms from the same save, ~30 updates each (~2 h each), with checks against the start every 10 updates:
- (a) as v0.6.1b;
- (b) `--ent-coef 0.002`.

What decides it:
- entropy (falls back toward 1.8 in arm b?);
- rail in hand and shots;
- the checks against the start;
- the behaviour panel.

The start: v0.6.1b's end (where v0.6.2 is prepared to start) or v0.6.1's save of update 250 (the strongest win-pay network).
That choice is the owner's.

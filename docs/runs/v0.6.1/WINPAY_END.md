# The win-chance pay does not pay a game's result (found 2026-10-29; nothing changed)

**For the session running v0.6.1.** This was found in a read-only audit of v0.6.2's end state. v0.6.1 runs the same code:
`WIN_JUDGE=judge_v060_wpn.npz`, live `WIN_W` 1, `FADE_V` 1, `WIN_GAIN` 0.33, `OVERTIME=1`. **It affects v0.6.1 now and
v0.6.2 as it is set up.** Nothing has been changed, stopped or started. Any change needs the owner's go, under the hard
rules: never stop a run; change only at a save, with the optimizer kept; the settings check before any start.

## What the code does

**Every frame of a game** (`sim/duel_env.py:9360-9372`):

```
pay = WIN_GAIN x wb_scale x (chance now - chance last frame)
```

- `wb_scale` = 1 / (p(lead 1, 600 s, both at a spawn) - 0.5), about 19.4.
- The chance comes from the judge: `win_judge.chance` (`sim/win_judge.py:96-101`).
- At w = v = 1, `_wb_blend` (`:9195`) makes this the whole reward of a game frame. All other pay is multiplied by 0.

**At the game's end**, `_game_end` (`:9462`) pays nothing more. So the whole game's pay comes to:

```
WIN_GAIN x wb_scale x (the judge's chance on the last frame - its chance at the start)
```

**That is the result only if the judge reads 1 / 0.5 / 0 on the last frame.** The old table (`win_chance.json`) was built to
do that: its loader asserts "1 / 0.5 / 0 at the limit" (`:9082`), and `_ot_left` relies on it ("a game decided in overtime
pays its outcome... on its last frame", `:9410-9413`). When `WIN_JUDGE` took the table's place, it kept the time-left
logic but not that property:
- `chance = sigmoid((d + mu) / s)`, with `s = sqrt(0.02 + left x ...)`. At 0 s left, `s` = 0.141, not 0.
- `mu`, the stack and weapon difference, is not zero at 0 s left.

## Measured on `judge_v060_wpn.npz` (v0.6.1's judge), 0 s left

| Last frame | Judge's chance for him | True result | Pay error (G = 0.33) |
|---|---|---|---|
| 1-0, equal stacks 100/0 | 0.999 | 1 | ~0 |
| 1-0, him 100/0 against 200/100 | 0.80 | 1 | -1.3 |
| 1-0, him on 10 hp bare against 200/200 with RL, LG, RG | 0.0001 | 1 | **-6.4: a won game paid as a loss** |
| 0-0, him 200/200 against 125/0 (a draw at the overtime cap) | 1.0 | 0.5 | +3.2 |

The pay error = 0.33 × 19.4 × (chance - result). Reproduce it with `win_judge.load` / `chance` / `parts` on the judge file.

## What this brings out

**In the last seconds a bigger stack pays far more than it matters.** The stack's worth is not scaled down by the time
left: it is divided by a spread that shrinks toward 0.141. So near the end a mega or red armor moves the chance more than
at any other time, though it can no longer change the result. Expected behaviour near the end of a game:
- The leader goes for items instead of holding the lead.
- The trailer is paid for stacking up instead of chasing the frag.
- Damage taken near the end weighs more than it should.

This is zero-sum (seat b gets minus seat a), so self-play stays balanced. But the equilibrium is "stack at the buzzer",
not "win". The error falls on the last frames of each game, and from there reaches the value estimates of the late game.

**A second, smaller fault: the frame when regulation ends level.** The last regulation frame reads 0 s left (`lb_ =
GAME_LEN - g_tick x DT`). If the score is level the game goes on into overtime, and the next frame reads about 120 s. The
chance jumps to near 0 or near 1 by the stacks, then back, which is a swing of up to about ±3 that undoes itself a frame
later. The same happens at the end of every overtime period that is still level (`_ot_left` reads 0 there whether or not
the game ends). This is noise in the advantage, not a bias.

**Not measured:** how often it matters. It needs the share of games whose last-frame chance is more than 0.1 off the
result, and the mean error per game. They can be counted from v0.6.1's self-play games (`selfplay/`, every 40th save) by
running the judge on the last frame of each. That is about an hour of work, read-only.

## Ways to fix it (proposals, for the owner)

1. **Pay the result on the last frame (recommended).** In `_game_end`, or on the frame a game ends, add
   `WIN_GAIN x wb_scale x (result - chance last frame)`, with result 1 / 0.5 / 0, to seat a, and minus that to seat b. The
   whole game then pays exactly `scale x (result - start chance)` whatever the judge does at 0 s. Zero-sum, and it doesn't
   touch the judge. The shared step is set after `_game_end`, so the term must reach that step's reward.
2. **Read 0 s only on the frame a game really ends.** Read the next period's 120 s on a level last frame of regulation or
   of an overtime period that goes on. This removes the swing.
3. **Add an axiom to the judge:** chance = result at 0 s, checked in `fit_b.py`'s acceptance, so v0.6.2's refit cannot
   bring the fault back. Fix 1 makes the pay right anyway; this keeps the judge's readouts honest.

**Checks for any fix:**
- **Identity:** a fixed-seed run where no game ends, or ends level on equal stacks, pays the same as before, bit for bit.
- **Each game:** its summed pay equals `scale x (result - start chance)`.
- **Settings:** `tools/run/check_settings.py` as always; the change is a code change, so the settings check alone won't
  show it.
- **v0.6.2's card:** `train.cmd` and the refit acceptance must carry the fix before v0.6.2 starts.

## Code references
- `sim/duel_env.py:9086-9092`: the judge's loader and `wb_scale`.
- `:9102-9119`: `_wb_chance`.
- `:9360-9372`: the pay each frame, and 0 s at the end of regulation and of each period.
- `:9182-9199`: `_wb_blend`.
- `:9405-9413`: `_ot_left`.
- `:9462-9488`: `_game_end`.
- `sim/win_judge.py:96-101`: `chance`.

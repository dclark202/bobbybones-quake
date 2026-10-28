# v0.6.1 on one page: pay by win chance only, second try, from v0.6.0's end

*2026-10-27 (owner): v0.5.1's fade again (25-min steps), from v0.6.0's end, with the four changes the owner approved (the
shaping, the critic's warm-up, the pay ledger, one change at a time). Full design: `docs/v0.6.1/WINPAY_v0.6.1.md` (branch `v061`).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## Start

| | |
|---|---|
| Network | v0.6.0's end (`keep/policy_end_v060.pt` + optimizer), saved at its stop ~07:00 ⏳ |
| Code | branch `v061` (aim2 + the shaping + the warm-up; with every new switch off it is v0.6.0's simulator to the bit) ✅ |
| Aim | `!aim default` (the pros' mean, 125 / 225 ms), as in v0.6.0 ✅ |
| Mix | as v0.6.0: 65% whole games / 35% the pros' mid-game starts, no movement practice ✅ |
| Start | ~07:00 10-28, after the 06:30 report, unless it shows something badly wrong ❓ |
| Run | `duel_gru_v0_6_1`; start script (stop v0.6.0 at a save, keep its end, prep, ramp, watcher) ⏳ |

## Pay: what fades in, what fades out

| Step k | Win part `WIN_W` | Every other pay `FADE_V` | Shaping `WIN_SHAPE_K` |
|---|---|---|---|
| 0 (v0.6.0) | 0 | 0 (flat pay in full) | 0 |
| 1 (+ critic warm-up, 10 updates) | 0.1 | 0 | 0.1 |
| 2 to 4 | 0.2 to 0.4 | 0 | = WIN_W |
| 5 to 9 | 0.5 to 0.9 | 0.125 to 0.625 | = WIN_W |
| 10 | 1.0 (win part in full) | 0.75 | 1.0 |
| 12 (done) | 1.0 | 1.0 (flat pay gone) | 1.0 |

- **Win part**: the change in his chance of winning, sized by `WIN_GAIN` from v0.6.0's settled counters (the calibration) 🧪.
- **Shaping**: potential-based (`k x (g PSI' - PSI)`, PSI = the stack term's next-frag edge, zero at the game's end): pays a hit or
  an item when it happens, keeps a 100-damage hit at ~0.53 of a frag (0.55 under the flat pay), zero-sum, and leaves the
  self-play equilibrium unchanged (only winning counts in the end) ✅.
- **Critic warm-up**: 10 updates at step 1 that train only the value outputs; the policy stands still to the bit ✅.
- **Ledger**: what each event pays under each pay, by lead and time left (`tools/winpay_ledger.py`) ✅.

## The fade and the checks (owner, 2026-10-27 evening)

| | |
|---|---|
| Steps | one every 10 updates and at least 25 min (warm-up updates not counted), **whatever the checks say**: the fade keeps going unless performance collapses |
| Checks | every 10 updates, 160 games against **v0.6.0's end** (two models trained natively on the new aim) |
| Flag | games won-lost **< 40%**: a message to the owner, the fade goes on |
| Serious | **< 30%**: posted in the chat; the owner decides. **The run is never stopped automatically** (owner, 10-27: "just don't ever stop the run") |
| Logged every check | weapon use (time in hand, frags by weapon), items (mega, red, yellow a minute), accuracy by weapon (LG, rail, rockets, plasma), with the behaviour panel |

## Schedule

| Time | What |
|---|---|
| Wed 10-28 05:00 | calibration on v0.6.0's latest save: `WIN_GAIN`, pay by term, stack-term refit, the K for the 0.55 ratio, close-game behaviour |
| 06:30 | report: v0.6.0's night, the calibration, go / no-go |
| ~07:00 | v0.6.0 stops at a save (its end kept); v0.6.1 starts at step 1 with the warm-up |
| ~07:40 | warm-up over, step 1's clock starts |
| ~45 min a step | 10 updates (~40 min at ~4 min an update) |
| **~17:00** | **step 12: the fade done** (win pay only) |
| ~19:00 | the owner's play test of the faded model (local server: the public build + v0.6.1's save) |
| to **Thu 10-29 12:00** | trains on win pay only (`--minutes 1740`); may end early if it looks good (owner's call) |

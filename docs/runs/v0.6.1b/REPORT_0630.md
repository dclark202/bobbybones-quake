# v0.6.1b: the 06:30 report (2026-10-30)

**Run:** v0.6.1b = `duel_gru_v0_6_1b`, from v0.6.1's end (`duel_gru_v0_6_1`, update 340). Started 2026-10-29 19:59, `--minutes 720`,
ends ~08:00. At 06:28: update 167, no stall, no crash. The old hand-built belief faded out of the brain (`BRAIN_FADE` 0 -> 1,
reached 1 at 02:18, update ~100), with the game-end pay fix (`WIN_END`) from the start.

## Verdict: no-go on the go list as it stands

The checks against v0.6.1's end have slid from 53.8% to 43.8%, and against v0.6.0's end from 55.0% to 40.6%. The behaviour
panel has been RED since update 120 (red armors). By the go list, v0.6.2 starts from v0.6.1's end, not this one.

**But the brain is not what got worse.** Its scores held or improved through the fade (below). The likely cause is the same
slide v0.6.1 showed in its last 90 updates (its end 45.0% against its own save of update 250): win-chance-only training is
making him a little worse with time, with or without the fade. If so, v0.6.1's end is also not a clean start for v0.6.2. That
choice is yours (end of this report).

## Games won-lost

| Update | g | Against | Won-lost | Win rate | Frag share |
|---|---|---|---|---|---|
| 10 | 0 → 0.1 | v0.6.1's end | 86-74 | 53.8% | 49.3% |
| 30 | 0.2 → 0.3 | v0.6.1's end | 81-79 | 50.6% | 50.0% |
| 50 | 0.4 → 0.5 | v0.6.1's end | 72-88 | 45.0% | 47.3% |
| 70 | 0.6 → 0.7 | **v0.6.0's end** | 88-72 | 55.0% | 49.5% |
| 90 | 0.8 → 0.9 | v0.6.1's end | 75-85 | 46.9% | 48.6% |
| 110 | 1 | v0.6.1's end | 72-88 | 45.0% | 45.0% |
| 130 | 1 | v0.6.1's end | 70-90 | **43.8%** | 45.5% |
| 150 | 1 | **v0.6.0's end** | 65-95 | **40.6%** | 45.1% |

Checks take ~70 min, so every other save is checked. No check was under 40%. The watcher wrote "STOP RULE" at u110 and u130.
That is a note only: the ramp had already finished, `BRAIN_FADE` is still 1, and the run was not stopped.

## The go list

| # | Test | Measured | Result |
|---|---|---|---|
| 1 | Ran clean | update 167 at 06:28, ~4 min an update, no stall or crash; the end save comes ~08:00 | NOT YET (needs `exit 0` and the end kept) |
| 2 | The fade complete | g 1 from update ~100 (02:18), held ~67 updates and 3 checks so far; the end save's g and `brain_fade_check`: at the end (v0.6.2's `start.ps1` checks both) | PASS so far |
| 3 | Level against v0.6.1's end | at g 1: u110 45.0%, u130 43.8%; pooled 142-178, **44.4%**. Not two checks in a row under 45% (45.0 is not under), but the pooled number is in the no-go band and the trend is down | **FAIL** (the u170 check, if it comes before the end, can move it ~±4 points) |
| 4 | The control | against v0.6.0's end: u70 55.0% → u150 **40.6%** (v0.6.1 ended 51-57% against it) | **FAIL** |
| 5 | The brain back | never dipped (table below): his estimate of where the enemy is 10 s+ after losing him 329 → 311 units, 1/2/4 s ahead 3-8 units better, the next-item race better; the stack band 3-4 points worse (0.74 → 0.71 right), "in control" skill a little lower | PASS |
| 6 | The game-end fix | u10 check 53.8% (no drop); 121 games paid their result, the correction 0.058 a game on average, 0.8% of games over 0.1. Self-play scores per map all positive, the lowest 1.2 (u40) | PASS |
| 7 | No behaviour collapse | **panel RED from u120 to u160**: red armors' share of item control 0.43-0.50 against the control's 0.60. Rail shots 0.87 → 0.53 a minute, rail in hand 0.13 → 0.06. Megas 0.80 and red armors 0.90 a player-minute (v0.6.1 0.78, 0.93), frags 1.38 a match-minute (1.37) | **FAIL** (the red armor share and the rail) |
| 8 | The data | self-play games at u40, u80, u120 (10 maps each) and u160 (in progress) | PASS |

## The brain's scores (means over 20 updates)

| | v0.6.1's last 20 | v0.6.1b u1-10 | u41-60 | u91-110 | last 20 (g 1) |
|---|---|---|---|---|---|
| Place error, enemy in view | 42.0 | 41.1 | 40.5 | 41.3 | 41.1 |
| Place error, 2-5 s unseen | 197.0 | 195.8 | 192.5 | 191.6 | 191.3 |
| Place error, 10 s+ unseen | 329.1 | 326.1 | 321.9 | 315.5 | **310.7** |
| 1 / 2 / 4 s ahead (units) | 356 / 428 / 526 | 357 / 429 / 527 | 352 / 425 / 523 | 351 / 423 / 521 | 349 / 421 / 518 |
| Next-item race (loss) | 1.080 | 1.096 | 1.070 | 1.062 | 1.052 |
| Stack band right, 2-5 s | 0.727 | 0.687 | 0.725 | 0.693 | 0.687 |
| "In control" skill (two items) | 0.145 | 0.100 | 0.134 | 0.138 | 0.131 |
| The judge's value (explained) | 0.857 | 0.823 | 0.850 | 0.839 | 0.838 |
| Policy entropy | 1.915 | 1.932 | 1.950 | 1.976 | **1.993** |

## Rail

Shots 0.53 a minute (v0.6.1's end 0.87); hit rate near 40% (35%), mid 22% (23%), far 14% (19%). In hand: 0.06 in the watcher's
count (0.13 at u90). He keeps taking the rail less. This continues v0.6.1's trend (0.21 → 0.13 there).

## Red team: what this does and does not show

- **The fade and the slide cannot be told apart in this run.** Training time and g rose together. The brain's own scores say
  the fade cost little. The level fell anyway, as it did in v0.6.1's last 90 updates without a fade.
- **Entropy keeps rising** (1.915 → 1.993), and the pay a player-minute is small (the win part's per-minute total is ±0.05).
  This fits the old lesson that the entropy bonus drowns a small pay: his choices are spreading. This is a guess, not measured.
  The way to check it is the ratio of the win pay to the entropy bonus per update, against v0.6.0's flat pay.
- The rail fading and the red armor share falling both look like the same drift, not like the brain.
- The checks are 160 games; one check moves ±4 points by chance. The trend over five checks, and the control's 14-point fall,
  are not chance.
- My hourly lines missed the panel's RED lines (I searched for "panel" in lower case only; the RED lines say "BEHAVIOUR").
  They began at 03:42.

## v0.6.2

- **Prepared** for v0.6.1b's end: `train.cmd`, `start.ps1`, the card. The settings check passes, and the head's identity
  check passes on a faded brain.
- **The smoke run** (the head on a brain faded to 1, your word last night) runs after this run ends, ~08:09, on its own.
- **If no-go:** the go list says v0.6.2 starts from v0.6.1's end with the git-HEAD files (57f1b9c). v0.6.1's end is itself
  ~5 points weaker than its update-250 save, by its own comparison.

**Your call, before v0.6.2 starts** (my recommendation first):

1. Find out why win-only training drifts (entropy against pay size, a short measurement on the saves we have) before adding
   the head. A head added on a drifting base will drift too.
2. Start v0.6.2 from v0.6.1's end, as the go list says.
3. Start v0.6.2 from v0.6.1b's end anyway: the brain is cleaner, and the level is ~1 point below option 2's start.

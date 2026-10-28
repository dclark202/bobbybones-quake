# v0.6.1: the win-pay fade, second try (the pay ledger, the shaping, the critic's warm-up)

v0.6.1 runs v0.5.1's fade again (the fight's pay replaced by the change in his chance of winning, then every other pay faded
out), this time from v0.6.0's end (the new aim model, branch `aim2`). v0.5.1 was stopped (2026-10-27): the checks fell from 47%
to 37% by step 4, and he played more passively (fewer frags in self-play). The owner approved four changes for the second try.
None of them is on in v0.6.0. Code: branch `v061` (from `aim2` at 0cc33c6, aim2's 3742130 merged in), worktree `ql-bot-v061`.

| # | change | where | off = before |
|---|---|---|---|
| 1 | a dense shaping pay beside the win part that leaves the equilibrium alone (`WIN_SHAPE_K`, live) | `sim/duel_env.py` (`_wsh_*`), the generated `duel_env_ffa.py` | `WIN_SHAPE_K=0` (default): v0.5.1's simulator to the bit |
| 2 | the critic's warm-up: N updates that train only the value outputs (`--value-warm N`, live `VALUE_WARM`) | `sim/train_duel_rnn.py` | 0 (default): no change |
| 3 | the pay ledger: what typical events pay under each pay | `tools/winpay_ledger.py` | (a tool) |
| 4 | the ramp and the watcher: the warm-up before step 1, a step every 10 updates and 25 min, panels and checks side by side | scratchpad `v061/ramp_v061.py`, `v061/watch_v061.py`, `v061/panel_v061.py` | (scripts) |

## 1. The shaping (`WIN_SHAPE_K`)

In every frame of a game under way the first seat of a match gets

    k x (g x PSI(now) - PSI(the frame before)),     PSI = (p_next - 0.5) x (1 - exp(-left / WIN_SHAPE_TAU))

and the second seat exactly the opposite. `p_next` is the stack term's chance that he scores the next frag (the fit of
2026-10-26, the same coefficients `WIN_PA` .. `WIN_PRG`: his health and armor against the enemy's through `tanh(d / 300)`, and
the rocket launcher, lightning gun and railgun each owns); a dead player counts as his respawn will have him (125 health, no
armor, no big weapon). `left` is the seconds left as the blend reads them (in overtime the period's, 0 on its last frame).

- **Zero-sum**: the second seat's PSI is minus the first's, so their shaping is exactly opposite (tested to the bit).
- **Zero at the end**: PSI is 0 when no time is left. A round cut before its game's end (a spawn start, a moment's limit) is
  terminal for the trainer (its `done` stops the value there), so its last frame is paid as if PSI were 0 there:
  `k x (0 - PSI before)` (the "cut" correction, counted in `stats["win_shape"]`).
- **Not faded**: it is added after the blend, so neither `FADE_V` nor `WIN_W` scales it, and it is not in `r_long`.
- **Live**: `WIN_SHAPE_K`, `WIN_SHAPE_TAU` (32.5 s, the stack term's) and `WIN_SHAPE_G` in `live.json`. Opened in the middle of a
  game it pays from the next frame on (nothing on the frame it opens). Set to 0 it forgets PSI.
- **The discount** `WIN_SHAPE_G` must be the trainer's `--gamma` (0.999 a frame in v0.5.x and v0.6.x). The trainer now sets
  `WIN_SHAPE_G` to its own `--gamma` when the run's environment does not name it, so the two cannot drift apart by accident.
- Counters: `stats["win_shape"]` and the trainer's `win_shape` record (minutes, the pay and its size a player-minute, cuts);
  `info["win_shape"]`; with `PAY_SPLIT` it is booked in the term `win_part`.

### The equilibrium

This is potential-based shaping (Ng, Harada and Russell, 1999). Over one game with frames 1..T the shaping, discounted at
g = 0.999 as PPO discounts the pay, sums to

    sum_t g^(t-1) k (g PSI_t - PSI_(t-1)) = k (g^T PSI_T - PSI_0) = -k PSI_0,

because PSI_T = 0 (at the clock's end, or by the cut). It adds a constant to the value of the game's first state and nothing
to the value of any choice after it: the policy that maximises the discounted win part is exactly the policy that maximises
the win part plus the shaping. In self-play the fixed point (the policy that wins most against the league) is unchanged:
only winning counts in the long run, as before. Tested: in fixed-seed games the discounted sum of each game's shaping equals
-k PSI(start) to float precision (section 5).

The residual from discounting, undiscounted: a game's shaping sums to `-k PSI_0 - k (1 - g) x (PSI_1 + ... + PSI_T)`. Holding a
stack lead costs 0.1% of its PSI a frame. Because the shaping is zero-sum, this residual is opposite for the two seats and
cancels between equal players. PPO optimises the discounted sum, and in that sum the residual is not there.

What changes on the way: a hit, a pickup or a big weapon taken pays on the frame it happens. Without the shaping it pays only
through the stack term, whose size goes with how much one more frag would move the win chance: large at a level score, small
with a lead of three or more, or in the last minute. The shaping's size does not depend on the score (dPSI of a 100-damage hit
is about 0.21 at any lead until the last half minute). A frag resets the dead player to the spawn's stack, so the shaping
built up by damage is taken back at the frag. The respawn moves nothing.

### An item-control potential: left out

A potential for "who holds the mega and the red armor next" would need a fixed function of the state. The simulator has one
for the truth (`CONTROL_TRUTH`, known only in hindsight, so not a function of the state). The brain's guess is a learned
network that changes as he learns, and a potential that changes during training is no longer exactly neutral. Left out: the
item pickups already move PSI through the stack (mega +100 health, red armor +100 armor), and the weapons through `p_next`.

### Note on the stack term itself (WIN_STACK, v0.5.1)

The stack term is also a potential (W~ = W + PHI, with PHI 0 at the end). But it is paid as an undiscounted difference
(PHI_t - PHI_(t-1)). In PPO's discounted sum, such a difference adds a level pay of `(1 - g) PHI` a frame: about the value of
holding the stack lead over the next ~25 s. For the table W this is the intended objective (its differences sum to the
result). For PHI it is a small pull towards holding a stack lead. Not changed here (v0.5.1's code stays bit for bit). If it
matters, the fix is to pay PHI in the shaping's g-form.

## 2. The critic's warm-up (`--value-warm N`, live `VALUE_WARM`)

For N updates the trainer learns the value outputs only (`v.*` and `v2.*`):

- the loss is the value loss alone, and its gradient is clipped on its own at 0.5;
- every other tensor's gradient is set to None before Adam's step, so Adam skips it. Its moments, its step count and its
  weights stand still: there is no drift of the moments from zero gradients;
- so the policy, the shared trunk, the brain, the head and every lesson are bit-identical through the warm-up. The separate
  readouts (`--control`, `--win-value`) keep their own optimizers and do not feed the policy.

`--value-warm N` covers the first N updates of the process. `VALUE_WARM=N` in `live.json` starts a warm-up of N updates from
the rollout read after the change. In `--overlap` mode, the update that learns from a rollout played with the old pay is not
counted. Set it back to 0 afterwards (the ramp does this), or a restart that reads the file starts it again. The metrics line
`value_warm` gives: on, start, n, left, and the value loss on the update's first and last pass over the same frames.

Limitation: the value outputs are linear readouts of the frozen trunk. The warm-up re-centres and re-scales the value to the
new pay as far as today's features carry it. Then the full update takes over.

## 3. The pay ledger

`python tools/winpay_ledger.py --gain 1.75 --k 0,0.5,1,1.15,2` (the simulator's own functions on a stand-in duel: both at 100
health and 50 armor, both owning the rocket launcher and the lightning gun, nobody the rail). These are his amounts. Every
column is zero-sum (the enemy gets minus it). The flat pay is v0.5.0's: 0.0055 a damage point, dealt and taken, a frag ±1,
mega 0.35, red armor 0.30. "Win" is the full win pay at WIN_W 1, FADE_V 1, WIN_GAIN 1.75 (one frag at 0:0 with ten minutes
left = 1.75). A frag row is the frag alone: the damage before it is in the hit rows.

| event | flat (v0.5.0) | win, table only | win + stack term (G 1.75) | dPSI | + shaping k=0.5 | + shaping k=1 | + shaping k=1.15 | + shaping k=2 |
|---|---|---|---|---|---|---|---|---|
| 100-damage rail hit, level, 5:00 left | 0.55 | 0.0 | 0.796 | 0.2078 | 0.9 | 1.003 | 1.035 | 1.211 |
| 50 damage of LG, level, 5:00 left | 0.275 | 0.0 | 0.428 | 0.1117 | 0.484 | 0.539 | 0.556 | 0.651 |
| 100-damage hit, level, 9:50 left | 0.55 | 0.0 | 0.728 | 0.2078 | 0.832 | 0.936 | 0.967 | 1.144 |
| 100-damage hit, 3 up, 1:00 left | 0.55 | 0.0 | 0.234 | 0.175 | 0.322 | 0.409 | 0.436 | 0.584 |
| 100-damage hit, 3 down, 1:00 left | 0.55 | 0.0 | 0.234 | 0.175 | 0.322 | 0.409 | 0.436 | 0.584 |
| mega health, level, 5:00 (100+50 -> 200+50) | 0.35 | 0.0 | 0.796 | 0.2078 | 0.9 | 1.003 | 1.035 | 1.211 |
| red armor, level, 5:00 (100+50 -> 100+150) | 0.3 | 0.0 | 0.796 | 0.2078 | 0.9 | 1.003 | 1.035 | 1.211 |
| rocket launcher taken (neither had one), level, 5:00 | 0.1 | 0.0 | 0.403 | 0.1052 | 0.456 | 0.508 | 0.524 | 0.613 |
| frag, level, 9:50 left (he 100+50, the enemy at 20) | 1.0 | 1.75 | 1.666 | -0.0038 | 1.664 | 1.662 | 1.662 | 1.658 |
| frag, level, 5:00 left | 1.0 | 1.913 | 1.884 | -0.0038 | 1.882 | 1.88 | 1.88 | 1.877 |
| frag, 3 up, 1:00 left | 1.0 | 0.278 | 0.063 | -0.0032 | 0.062 | 0.06 | 0.06 | 0.057 |
| frag, 3 down, 1:00 left | 1.0 | 1.06 | 1.531 | -0.0032 | 1.529 | 1.527 | 1.527 | 1.524 |
| death, 3 up, 1:00 left (he at 20) | -1.0 | -1.06 | -1.531 | 0.0032 | -1.529 | -1.527 | -1.527 | -1.524 |
| death, level, 5:00 left (he at 20) | -1.0 | -1.913 | -1.884 | 0.0038 | -1.882 | -1.88 | -1.88 | -1.877 |
| rocket jump, 50 self damage, level, 5:00 | -0.275 | 0.0 | -0.428 | -0.1117 | -0.484 | -0.539 | -0.556 | -0.651 |
| even trade at 5:00 (each takes 130 and frags once), net | 0.0 | 0.0 | 0.0 | | -0.0 | -0.001 | -0.001 | -0.001 |

The 100-damage hit by lead and time left (`scratchpad v061/grid_v061.py`; the win part with the stack term at G 1.75 / dPSI):

| lead | 9:00 left | 5:00 | 2:00 | 1:00 |
|---|---|---|---|---|
| 0 | 0.796 / 0.208 | 0.796 / 0.208 | 1.072 / 0.203 | 1.141 / 0.175 |
| 1 | 0.705 / 0.208 | 0.783 / 0.208 | 0.967 / 0.203 | 1.012 / 0.175 |
| 2 | 0.559 / 0.208 | 0.648 / 0.208 | 0.681 / 0.203 | 0.627 / 0.175 |
| 3 | 0.442 / 0.208 | 0.427 / 0.208 | 0.398 / 0.203 | 0.234 / 0.175 |
| 4 | 0.347 / 0.208 | 0.301 / 0.208 | 0.216 / 0.203 | 0.060 / 0.175 |
| 5 | 0.249 / 0.208 | 0.209 / 0.208 | 0.087 / 0.203 | 0.010 / 0.175 |

What the ledger says:

- **At a level score, the stack term is not weak.** At G 1.75 a 100-damage hit pays 0.80 (flat 0.55), and a mega or a red
  armor pays 0.80 (flat 0.35 / 0.30). What is weak is the stack term **with a lead of three or more, or late**: 0.23 for the hit
  3 up or 3 down with a minute left, 0.06 with 4 up. In v0.5.1's update-60 games against v0.4.2b's end
  (winsense, 80 games) 80% ended 5 or more apart: a large part of his frames are in that weak region. Self-play margins of
  v0.6.0 come from the calibration window (`calib_v061.py behave`).
- **The win part changes the ratio of a hit to a frag.** PPO normalises the advantages in every piece of the update, so only
  ratios matter. Under the flat pay a 100-damage hit is worth 0.55 of a frag. Under the full win pay at a level score with 5:00
  left it is 0.42 (0.796 / 1.884). Frags and deaths near a level score are worth more against everything else, and the frag of
  a leader late is worth almost nothing (0.06) while his death costs 1.53. Protecting a lead is the right play by the table
  itself, which may be part of the "passive" reading.
- **The even trade is exactly 0** under every column but the flat damage, as it should be.

## 4. The recommended settings

| name | value | why |
|---|---|---|
| `WIN_SHAPE_K` (full) | **1.0** (1.15 restores the flat ratio exactly) | brings a 100-damage hit back to ~0.53 of a frag at a level score (0.55 under the flat pay) and gives chip damage a floor of ~0.2 a 100 damage wherever the score is (0.41 at 3 up with a minute left instead of 0.23). Items rise with it (a mega 1.0 against a frag 1.88: 0.53 of a frag against 0.35 flat). That is the stack model's own valuation (100 of stack is 100 of stack), and it is neutral in the end anyway. `calib_v061.py fit` re-derives the K for the 0.55 ratio from v0.6.0's own self-play (the refit) in the calibration window. |
| ramp of K | `WIN_SHAPE_K = 1.0 x WIN_W` at every step | keeps the hit/frag ratio near 0.55 all through the cross-fade (at WIN_W 0.5: 0.54 with K 0.5, 0.47 with K 0) |
| `WIN_SHAPE_TAU` | 32.5 s | the stack term's |
| `WIN_SHAPE_G` | 0.999 (= `--gamma`) | set by the trainer from `--gamma` unless named |
| `WIN_GAIN` | from v0.6.0's settled counters (`calib_v061.py gain duel_gru_v0_6_0`, the last 20 updates); v0.5.1's settled reading was **1.725 -> 1.75** (updates 114-133; its first 10 updates were a start-up transient, 5.1 -> 3.1) | "keep the total about what he gets paid now"; sized from settled updates, never from the first ones |
| `VALUE_WARM` | 10 updates, set together with step 1 | the value learns the new pay before the policy moves |
| the ramp's step | every 10 updates and at least 25 min | the owner's original 25 min |

## 5. Tests (all CPU, at low priority on the performance cores)

| test | result |
|---|---|
| identity, `duel_env`, 4,000 frames x 16 matches, Blood Run (games, pro starts, overtime): aim2's head (0cc33c6) against v061 with the new names absent, `WIN_SHAPE_K=0`, and `K=0` with `TAU` and `G` set | identical: rewards, `r_long`, dones, inputs, clocks, frags, pay split, every info value |
| identity with the blend on (WIN_W 0.5, FADE_V 0.25, G 1.75, WIN_LONG, WIN_STACK; K 0): the stack term's refactor (`_wb_pnext`) | identical (the win part `wb_raw` too) |
| the same for `duel_env_ffa` (all four comparisons) | identical |
| `tools/ffa_check.py` (the generated module at two players) | identical to `duel_env` over 3,000 frames |
| the shaping on (K 2, G 0.999), `t_shape.py`: `duel_env` 6,000 frames Blood Run, `duel_env_ffa` 3,000 frames Aerowalk, and `duel_env` with pro starts cut after 20 s (`PRO_START_LEN=20`: the cut path, 41 games cut, 1 to the clock) | all pass: zero-sum to the bit; the pay = the K=0 pay + the shaping (float32 rounding, 7e-8); frames with no game unchanged; the same games, clocks and frags as K=0; the pay split sums to the pay and its `win_part` moves by the shaping exactly; every game's discounted shaping = -K PSI(start) to 2e-8 (|K PSI(start)| ~0.45); PSI 0 on every frame with 0 s left; opened live at a frame it pays nothing on it and then as a run with K from the start |
| after merging aim2's 3742130 (per-seat aim): the generated `duel_env_ffa` regenerated = the merged one; a smoke run with K 1 | the same file; zero-sum |
| the warm-up, CPU trainer (v0.5.1's command, tiny sizes) from a save with a new pay (WIN_W 1, FADE_V 1, K 1): 4 warm-up updates against 1 ordinary update | warm-up: 4 of 98 tensors changed (v.weight, v.bias, v2.weight, v2.bias), 4 of 83 Adam states (the same four; every other state's step count unchanged), the value loss falls within each update (first pass -> last pass on the same frames: 0.081 -> 0.068, 0.109 -> 0.098, 0.087 -> 0.079, 0.625 -> 0.612); ordinary update: 79 of 98 tensors and all 83 Adam states moved. The trainer applied the live K and wrote `win_shape` into the metrics |
| the ramp against a fake run (`t_ramp_v061.py`) | gain preset, step 1 with the warm-up, VALUE_WARM back to 0 at its end, a check at 44% steps back, steps to 12 |

## 6. The ramp and the watcher (scratchpad `v061/`)

`ramp_v061.py` (from `ramp_v051.py`): step k: WIN_W = min(1, 0.1 k), FADE_V = clip(0.125 (k - 4), 0, 1), WIN_SHAPE_K = 1.0 x WIN_W.

- WIN_GAIN: `RAMP_GAIN` (from v0.6.0's counters, before the start) or, unset, sized from the run's own counters after
  `RAMP_SKIP` (20) updates, the mean of the next 10.
- Step 1 sets `VALUE_WARM=10` together with the new pay. The ramp waits until the metrics say the warm-up is over, writes
  `VALUE_WARM` back to 0, and only then starts the step's clock.
- The gate: 10 updates and 25 min since the step, a behaviour panel of a later save, and the games against the previous best of
  a later save (the owner's rule of 2026-10-24): green and >= 50% steps up; red once or under 50% holds; red twice of the same
  kind, the last check under 45%, or two checks under 50% steps back. The rockets flag does not hold the ramp (owner,
  2026-10-27 12:50). `RAMP_PANEL_ONLY=1` lets a panel step up alone when no check has come yet.

`watch_v061.py` (from `watch_v051.py`), the fix for "panels skipped while a check ran": the games and the panel run in
threads of their own, each skipped only while one of its own kind still runs. A panel that starts while a check plays runs 3
games at once instead of 6. `panel_v061.py` plays the fixed control's panel once per PERCEPT_SPEED and keeps it, which halves
a panel's cost. Checks at update 10 and then every 10 updates when none still runs (`CHECK_EVERY`), against v0.6.0's end, every
fourth against v0.4.2b's end. `PANEL_SETS` gives the games v0.6.0's aim switches.

## 7. The calibration window (scratchpad `v061/calib/`, 23:30-01:30 while v0.6.0 trains)

`window_v061.py [--policy <save>] [--games 6]`, started with `start "" /b /low /affinity C03C3`. Four game processes at idle
priority. It runs:

- (a) `calib_v061.py gain`: WIN_GAIN from the last 20 settled updates;
- (b) `calib_v061.py terms`: the pay split by group and what becomes of each group;
- self-play games of the latest kept save (`run_ws061.py`), logged once a second;
- (c) `calib_v061.py fit`: who scores the next frag by stack lead and big weapons, the coefficients refitted against the fit of
  2026-10-26 (held-out log loss), and the K that restores the 0.55 ratio under each;
- (d) `calib_v061.py behave`: the final margins and, in the last two minutes, frags and damage a minute ahead, level and behind;
- (e) `score_ws061.py`: the win value's scoring.

All of it goes into `calib/out/window_<tag>.txt`.

# v0.4.5 on one page: pay by win chance, first step (DRAFT)

*2026-10-25 (draft for the owner's review): the generation's goal (the owner, 2026-10-23: pay by win chance as the only game
pay; [../v0.4.0/PATH_v0.4.md](../v0.4.0/PATH_v0.4.md)). Renamed from v0.4.4 on 2026-10-25 (the owner: the strategy head's
opening is v0.4.4). From v0.4.4's last save (the strategy head). Start: on the owner's go after v0.4.4. Before it:
v0.4.4 (`../v0.4.4/`).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## What it is

| | |
|---|---|
| The one new thing | **Win-chance pay** cross-faded in: a frame's pay = the change in his chance of winning (from the score and the clock), at weight w; w rises 0 -> target slowly, live, tied to the checks |
| What goes out with it | three shaping pays that do nothing for winning (below), faded as w rises |
| Second thing (after the first is in) | ❓ mid-game starts from people's games and moments before pickups (built 2026-10-25, off) |
| Equilibrium it aims at | the same play as v0.4.4 minus what the three pays bought (firing less, looking at doorways, pre-aiming for pay); everything else priced by what it wins. In self-play: zero-sum, "win the game" |
| Pass | level or better against v0.4.4's end; the win pay's share of his pay rising, the win rate not falling; the behaviour check (per map, against the pros) not worse |

## The parts

| Part | Detail | State |
|---|---|---|
| Win-chance pay | `WIN_PAY` in the simulator (frame pay = change in win chance, `sim/win_chance.json`) | ✅ built (on/off only) |
| Overtime | the last overtime frame reads 0 s left, not 120 (commit 4e52053) | ✅ fixed |
| The cross-fade weight | live `WIN_PAY_W` (0..1), `WIN_PAY_K` (scale, 1 = a frag at 0:0 with 10 min left), `WIN_RETIRE` (default the three below): win pay x w x K added, the retired pays x (1 - w) where they are paid. Zero-sum: +x to one seat, -x to the other, every frame. Branch `v045` (2f6e8a4) | ✅ built and tested: at w 0 the same to the bit as v0.4.3's code (`v043b`) (`tools/winx_ident.py`, 2 maps, every counter; the trainer's rollouts over 3 updates); at w 0.3 the pay is exactly w0's - w x retired + w x the win pay |
| The critic's start | `--win-adv 1`: the win pay gets its own advantage, with the shadow win value (trained since v0.4.3 started) as its critic (gamma 1 to the game's end); the main value's targets stay without it | ✅ built and tested (below) |
| His own win table | `sim/win_chance_bobby.json` (120 whole self-play games of save 70, all ten maps; `WIN_CHANCE=` picks a table) beside the pros' | ✅ made; differs from the pros' far beyond noise, and is the calibrated one on his games (the calibration check below): his own at K 0.22 if it holds on fresh games |
| The guard | as every round: a check under 50% holds w; under 45% (frag share under 48.5%) or two checks under 50% steps it back | ✅ (the watcher) |
| Measures | per check: games, frag share, the behaviour check per map, the pay ledger (each pay's share of the total), the decision report at the end | ✅ / ⏳ the ledger in the check line |

## The pays that go out first (the path's list)

| Pay | What it pays now | Why it goes | Equilibrium without it | State |
|---|---|---|---|---|
| Shot price (`SHOT_W`, `RG_FAR_PRICE`) | a cost per shot by weapon (-0.33 a player-minute) | firing well is priced by what it wins; the price makes him fire less | fires when the shot's expected damage pays for the exposure; not zero-sum (each pays alone) | ✅ in `WIN_RETIRE` |
| Watching the right spot before a sighting (`WATCH_PAY`) | pay for having the doorway in view when the enemy appears (0.04 a minute in size, zero-sum) | the win value prices a good read itself | watches where the enemy is likely, when it helps win | ✅ in `WIN_RETIRE` |
| Pre-aim pay (`PREAIM_PAY`) | pay for the crosshair near where he appears (0.09 a minute, zero-sum) | as above | pre-aims when it wins fights | ✅ in `WIN_RETIRE` |
| The big-weapon pay (`BIG_PICK_SEQ`, equal 0.10 since 2026-10-25) | 0.10 for each of RL, RG, LG once a life (+0.24 a minute) | today it is the weapon-variety scaffold (B-286) | recommended: keep it in v0.4.5, retire it in v0.4.6 once the weapon numbers hold | ✅ can be named in `WIN_RETIRE`; out by default |

**The win pay's own equilibrium** (zero-sum, a difference of one function, so a game's win pay sums to K x 8.2 x (result - the
chance at its start) whatever the path: nothing in it can be pumped): "win the game". On the way: a frag is worth more when
it moves the chance more (level and late: 1.5 a frag at 2:00, 2.5 at 0:30 by the pros' table; 3 ahead with 1:00 left 0.16), the
leader earns a trickle as the clock runs and the trailer loses it, so the trailer must take risks and the leader may play safe.
The flat frag pay stays in v0.4.5, so a blow-out still pays (it goes in the cross-fade's last step). Whatever table is used, the sum over a game
is the same; the table only decides when inside the game the credit comes. The critic's start changes no pay and no
equilibrium, only how well the credit is assigned.

## Measured (2026-10-25, CPU, beside v0.4.3)

**Pay sizes** (`tools/winx_sizes.py`, `pay_ledger.py`; 120 whole ten-minute self-play games of v0.4.3's save 70, 10 maps x 12,
2.9 M frames, both seats; per seat and frame):

| Part | mean / frame | variance / frame | size a player-minute | sd of a seat's game sum |
|---|---|---|---|---|
| shot price | -1.4e-4 | 7.8e-7 | 0.33 | 0.80 |
| watching | 0 | 1.8e-7 | 0.04 | 0.07 |
| pre-aim | 0 | 1.1e-6 | 0.09 | 0.18 |
| **the three together** | -1.4e-4 | 2.6e-6 | **0.45 (4.5% of his pay)** | **0.80** |
| big-weapon order | +1.0e-4 | 1.0e-5 | 0.24 | 1.27 |
| flat frag pay (stays) | 0 | 1.2e-3 | 2.90 | 10.1 |
| **win pay at K = 1** | 0 | 6.7e-4 | **1.65** | **4.11** (= 8.2 x 1/2: every game decided) |
| all his pay | +1.7e-4 | 1.9e-3 | 9.98 | 16.9 |

A win pay matched to what it displaces would need K = 0.27 (by size), 0.06 (frame sd) or 0.20 (game sd): at w 0.5 it would be
0.2 to 2% of his pay, under the entropy bonus's noise. **Recommendation: K = 1** (a frag at 0:0 = a flat frag, WIN_PAY's own
scale): the win pay is then 1.6% of his pay's size at w 0.1, 4.8% at 0.3, **7.8% at 0.5** (target, as decision 2), 15% at 1;
its game-sum spread at w 0.5 (2.1) is about 2.5 times the three pays it replaces (0.80).

**The critic's start** (`--win-adv 1`; the trainer on the CPU from save 70, one map, 32 matches, `--seed 1`, 4 updates; the
first update learns from the same rollout in every arm): the main value's loss in its first pass on that rollout:

| arm | w 0 | w 0.1 | w 0.5 |
|---|---|---|---|
| the win pay in the main value (plain) | 0.3840 | 0.3846 (+0.2%) | 0.3877 (+1.0%) |
| `--win-adv 1` | 0.3840 | 0.3840 | 0.3839 |

With `--win-adv` the win critic explains 0.91 of its own returns on his game frames at the first update, 0.95 to 0.96 after;
the win pay's advantage is 3% (w 0.1) and 16 to 19% (w 0.5) of the main advantage's size. Neither way spikes; `--win-adv` keeps
the main value exactly as it was and uses the critic trained for a day, so it is the start recommended.

**His own win table** (`tools/win_table.py --boot 200`, the same 120 games; 90% intervals by resampling games, the pros' from
the 3,355 games now in the archive):

| | his self-play | the pros' (in use, 257 games) | the pros' (refit on 3,355) |
|---|---|---|---|
| frag-difference variance a minute | 9.5 (7.2 to 14.7) | 2.6 | 3.3 (2.8 to 3.7) |
| strength-difference sd (frags in 10 min) | 0 (0 to 15) | 6.3 | 7.2 (4.7 to 10.2) |
| chance 1 ahead, 5:00 left | 55% (54 to 57) | 63% | 64% (63 to 66) |
| chance 3 ahead, 5:00 left | 66% (64 to 70) | 85% | 82% (81 to 84) |
| chance 1 ahead, 1:00 left | 62% (59 to 64) | 73% | 76% (74 to 78) |
| a frag's pay, level at 0:30 | 6.7 (3.2 to 10.4) | 2.5 | 2.9 (2.5 to 3.4) |
| a frag's pay, 3 ahead at 1:00 | 2.5 (1.3 to 4.6) | 0.16 | 0.24 (0.14 to 0.34) |

Every one of 17 cells checked differs from the pros' by 8 to 17 points, all clear of noise. His games are wilder (3.6 times the
frag-difference variance; 29 frags a game against 19) and, in self-play, the two seats are the same network, so a lead says
nothing of who is better (strength spread 0). His table's scale is 38 (pros 8.2): a decided game would be +-19 at K = 1, more
than all his other pay's game spread (16.9), and 92% of his frags would be paid differently by more than half. So his table
needs `WIN_PAY_K` 0.22 (below: the same game totals as the pros' at K 1). Which table: decision 1, after the calibration
check; the table never changes the equilibrium, only when inside a game the credit comes.
Option: the pros' table refit on all 3,355 games (`win_chance_pros_all.json`, scale 9.1): within 1 to 3 points of the one in
use, a later choice.

## The calibration check (before the cross-fade opens)

**(a) The win table on his own whole games** (`tools/win_calib.py`: at every whole minute of each game, both seats, the
table's chance against the result after overtime; 90% intervals by resampling games). Run once on the 120 games of v0.4.3's
save 70 (the checks' files keep only results, not the score by minute, so the frame-by-frame games of `winpay_games.py`
are used):

| time left | lead | sightings | the pros' (in use) predicted -> observed | his own predicted -> observed |
|---|---|---|---|---|
| 9-7 min | 1-2 ahead | 167 | 68% -> 53% (-15, -22 to -7) | 56% -> 53% (-3, -10 to +5) |
| 9-7 min | 3-5 ahead | 119 | 87% -> 69% (-18, -28 to -9) | 67% -> 69% (+2) |
| 6-4 min | 1-2 ahead | 74 | 69% -> 51% (-18, -28 to -9) | 58% -> 51% (-7, -16 to +3) |
| 6-4 min | 3-5 ahead | 125 | 90% -> 66% (-24, -33 to -15) | 71% -> 66% (-5) |
| 6-4 min | 6+ ahead | 137 | 99% -> 89% (-10) | 88% -> 89% (+1) |
| 3-1 min | 1-2 ahead | 61 | 76% -> 57% (-19, -29 to -7) | 64% -> 57% (-6) |
| 3-1 min | 3-5 ahead | 76 | 96% -> 78% (-18, -26 to -9) | 82% -> 78% (-4) |
| 3-1 min | 6+ ahead | 206 | 99.9% -> 96.6% (-3) | 96.6% -> 96.6% (0) |
| all | | 2,880 | Brier 0.194, log loss 0.626 | Brier 0.171, log loss 0.498 |

The pros' table (and the pros' refit on 3,355 games, the same within 2 points) is over-confident on his games in every
bucket with a lead, 10 to 24 points, all clear of noise: his leads are worth much less than a pro's. His own table is
calibrated within noise, but it was fitted on these same games (in sample). Before the start: run `win_calib.py` on fresh
whole games of v0.4.4's last save (`winpay_games.py`, 12 a map, about an hour on three cores); "ready" = no bucket with 50+
sightings off by more than 8 points outside its interval. Whichever table is used, a game's win pay sums to the same (K x
scale x (result - start chance)); the table only moves the credit inside the game. With his table, `WIN_PAY_K` = 8.22 /
37.8 = **0.22** keeps every game's total what the pros' table pays at K 1 (+-4.1 a decided game).

**(b) The shadow critic against results** (`metrics.jsonl` `win_value.cal`, pooled over v0.4.3's 87 updates with a
calibration: 1.68 M states, 12,148 seat-games): explained variance of the realised return 0.02, slope 0.74, correlation 0.16,
the two seats' difference against the result 0.16 (the last 30 updates: 0.01, 0.57, 0.14, 0.14). Its TD fit is good (0.7 to
0.95 against its own targets), but against how games really end it adds little to the table yet. "Ready" (to carry the
win pay's advantage alone): pooled over the last 20 updates, slope 0.8 to 1.2, correlation 0.25 or more, the seats'
difference 0.25 or more (`tools/value_ready.py`'s section (a) on fresh games as the second look). Not ready today, which
does not block the start: with `--win-adv` the critic is only the win pay's baseline (a weak baseline costs variance, not
bias), and at w 0.05 to 0.2 the win pay is 1 to 3% of his pay. Read `win_value.cal` at each step of w; hold w at 0.2 until it
reaches the bar.

## How to start (on the owner's go; nothing has been started)

From v0.4.4's last save, code: branch `v045` merged with the code v0.4.4 ran (it merges cleanly with `starts`: `git
merge-tree` clean; the worktree is `ql-bot-v044`). The run's `.cmd` as v0.4.4's last, and:
- `set WIN_PAY_W=0`, `set WIN_PAY_K=1` (and leave `WIN_RETIRE` unset: shot price, watching, pre-aim); `PAY_SPLIT=1`,
  `WIN_SHADOW=1` stay; `WIN_PAY` unset (0); `WIN_CHANCE` unset (the pros' table).
- trainer: add `--win-adv 1`; keep `--win-value 1` and every start minute of the run (`--win-value-start` as before: its warm-up is
  long over). At w 0 the run is v0.4.4's to the bit.
- the opening, live in `live.json`: `"WIN_PAY_W": 0.05`, then +0.05 every 25 min on passing checks to 0.5; the guard as every
  round (under 50% holds, under 45% or two under 50% steps back 0.05). `"WIN_PAY_W": 0` shuts it at once.
- read per update in `metrics.jsonl`: `win_adv` (wk = w x K, `a_win` / `a_main`, the critic's `ev`), `value` (the main value's
  loss by pass, `ev`), `pay_terms` (the retired terms shrinking), `win_shadow`.

## Decisions for the owner

| # | Question | Recommendation |
|---|---|---|
| 1 | The win table: the pros' or his own | **decided (owner, 2026-10-25): his own at K 0.22** if it holds on fresh v0.4.4 games (the calibration watch); else the pros' at K 1 |
| 2 | The target w for v0.4.5 | **decided (owner, 2026-10-25): 1.0 within v0.4.5**: 0.5, two passing checks there, then on to 1.0 at the same pace (w cross-fades only the three retired pays, 4.5% of his pay; the rest fades in the later rounds) |
| 3 | How fast w opens | **decided (owner)**: +0.05 every 25 min on passing checks; held at 0.2 until the critic is ready |
| 4 | Who he trains against under win pay | **decided (owner)**: the long-term control in the league; the mid-game starts as v0.4.4 runs them (50%, half generated) |
| 5 | The big-weapon pay | **decided (owner)**: kept; faded out when the pay becomes win chance only |
| 6 | The people's mid-game starts | **decided (owner, 2026-10-25): dropped** while the generated starts work ("I don't think we need the people mid game starts if the generated ones work"); kept built and off |

## Reminders for this round's planning
- The pros' jump-pad landings (`PAD_PRO`, branch `pads`, B-287): built and off; a later round's one new thing.
- The brain widened 256 -> 512: on the table, the test not yet run.
- Rocket jumps and the tricky movement jumps (B-284, B-212): important, not this round.
- The hindsight review of games against people before any network goes on the public servers.

## Schedule (draft)

| When | What |
|---|---|
| 2026-10-25 | the cross-fade weight, the critic's start, his own win table, the calibration check: built and tested on the CPU beside v0.4.3 |
| before the start | the calibration check on v0.4.4's last save (fresh games); the owner's go on this card |
| after v0.4.4 | v0.4.5 starts from v0.4.4's last save, w 0; opens on passing checks |
| Tue afternoon | w at its target; two checks; then the second thing if decided |

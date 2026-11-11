# AIM3: the eye, not the crosshair; the error by how big he looks (proposal, 2026-11-10)

For 2.0c, in from its start (owner, 2026-11-10: "He needs to be able to make flick shots ... We set up the structure to enable him
to have flick shots and use the rail, we need to make sure he actually can take advantage of it by fixing the aim. Same with
rockets"). Built as switches, **off by default: the simulator before, bit for bit** (section 6). Nothing has trained under it.

**What this is for (owner, 2026-11-10; CLAUDE.md hard rule 12):** "We are not tuning to get a certain hit % out, we are tuning to
provide structural fairness and calibration parameters to make his aim feel human like"; "the same rough type of intrinsic error a
well-trained human would have". Every number below is a parameter read from the pros' own aim error; no hit rate is a target, and
whatever hit rates come out are a readout.

## 1. In one table

| | AIM2 (today) | AIM3 |
|---|---|---|
| The slip term (a target that moves across his sight is seen worse) | against his **crosshair**: a view that follows the target sees it sharp; a still crosshair with an enemy crossing it sees it worst (up to 2.1 degrees) | against his **eye**, which follows the target whatever the hand does: a steady crosser is sharp; a change of direction blurs him for about the eye's lag |
| The eccentricity term (a target far from where he looks is seen worse) | against the crosshair, as long as it is off him (up to 2.8 degrees at a flick's start) | the eye goes to him once he is noticed: the term fades in about 0.1 s |
| The base error | a fixed angle (0.9 degrees) at any distance | a share of how big he looks: the same 0.9 at 500 units, less beyond, more nearer |
| Everything else (delays, flinch, hand noise, the velocity and distance reads, the hand chain) | | unchanged |

Why it matters for the rail: a held angle is a still crosshair with an enemy crossing it, and a flick starts far off the crosshair.
AIM2 gave exactly those two moments its largest errors (about 3 degrees on a body 1 degree wide), and gave the lightning's
moment, a view that follows, its smallest.

## 2. What was measured (the pros: 5,265 player-games, 4,222 demos, nine maps; `tools/run/pro_knobs.py`)

The **aim error**: the angle left-right between where the view points and where the enemy is, on the frame a rail shot is aimed
and while the lightning fires. A demo holds the server's state, so the enemy's place is taken back by the demo's own delay first
(found per player-game on the lightning's hit frames: 2 frames in 79% of them, 3 in 14%). The check of the measure: with it, 81 to
83% of the pros' hits lie within the body and 11 to 16% of their misses.

| The question | The pros (median error) | What it says |
|---|---|---|
| Does the error depend on distance? | Lightning, settled: 3.1 / 1.95 / 1.48 / 1.11 / 0.98 degrees at 200 / 325 / 500 / 750 / 1,150 units = 0.75 / 0.77 / 0.88 / 0.92 / 1.07 half body widths. Rail: 1.69 / 1.54 / 1.05 / 0.86 degrees from 325 to 1,150 units | **About one half body width at every distance**: in degrees the error falls as he gets smaller. A straight line through it: 0.55 + 0.5 x his half width in degrees |
| Does a STILL view see a crossing enemy worse than a view that follows him (the rail: a deliberate shot)? | crossing 0-20 deg/s: still 0.93, following 0.86 half bodies; 20-50: 0.89, 0.96; 50-100: 0.98, 1.16 | **No.** AIM2's premise does not hold for people |
| Does the error grow with his crossing speed at all (rail, settled)? | 0.95 / 0.92 / 0.97 half bodies at 0-20 / 20-50 / 50-100 deg/s (1.73 above 100, 44 shots) | **Not up to 100 degrees a second**: the eye keeps up (a pursuit gain of 1 in that range) |
| How long after the enemy turns round is the error raised? | Rail: 1.27 in the first 75 ms, 1.07 to 150 ms, 1.00 after. Lightning: 1.26, 1.40 (75-150 ms), 1.08 from 150 ms | Raised by a third for **about 150 ms**: the eye's and hand's lag |
| How long after he comes into view is the error raised? | Lightning: 1.32 to 250 ms, 1.11 at 250-400 ms, 1.05 after | Settled **250 to 400 ms** after he appears (the notice at about 200 ms, then about 0.1 s) |
| The held shot: from the enemy in view to the shot | median 275 ms, the fast end (p90) 200 ms (12,996 shots) | the notice delay as it stands (225 / 200 ms) fits |
| How does the error grow with the flick (the view's travel in 250 ms)? | 1.14 / 1.34 / 1.68 / 2.36 / 3.92 / 6.58 degrees at 0-3 / 3-8 / 8-15 / 15-30 / 30-60 / over 60 degrees | about **7% of the travel** on top of a degree: the hand's endpoint noise |

Not measurable this way: the tracking delay (the view's turn against the bearing's reads 0 ms: a tracker predicts), the eye's gain
above 100 degrees a second (too few shots).

## 3. Him beside it (1.7a's update 90 against itself, 43 player-hours, the same measure; a readout)

| | The pros | Him (AIM2) |
|---|---|---|
| Lightning error by distance, half bodies: 200 / 325 / 500 / 750 / 1,150 units | 0.75 / 0.77 / 0.88 / 0.92 / 1.07 | 0.54 / 0.58 / 0.83 / **1.23 / 1.78** |
| ... in degrees | 3.1 / 1.95 / 1.48 / 1.11 / 0.98 | 2.3 / 1.5 / 1.4 / **1.4 / 1.3** |
| Lightning error in his first 250 ms in view / 250-400 ms / after 750 ms | 1.32 / 1.11 / 1.09 | **2.36 / 1.59** / 0.87 |
| Lightning error by the enemy's crossing speed 0-20 / 20-50 / 50-100 deg/s | 0.89 / 1.16 / 1.81 | 0.89 / 0.84 / 1.01 |
| Lightning error 75-150 ms after a turn-round | 1.40 | 0.98 |
| Rail error after a flick of 15-30 / 30-60 degrees (54, 25 shots) | 2.36 / 3.92 degrees | **4.91 / 6.39** |

- **The owner's point about far vision is right** (2026-11-10: "probably aim2 has too poor of far vision"). His error stops falling
  at 1.4 degrees from 400 units on; the pros' keeps falling to 1.0. Closer than 400 units he is tighter than they are.
- **He is slow onto a new target**: nearly twice the pros' error in the first 250 ms, level with them only after 400 ms.
- **His flicks land wide**: twice the pros' endpoint error on the larger ones.
- **His tracking of a fast or turning enemy is tighter than the pros'** (1.01 against 1.81 at 50-100 deg/s; almost no dip after a
  turn-round). Not changed here (owner: "keeping tracking roughly as it is"); it is a likely part of why the lightning dominates,
  and AIM2's notes already had the shallow dip. A lever if wanted later: the eye's gain below 1, or its lag longer.

With the slip and the eccentricity terms against the eye (AIM3) or off, **without any training**, his flicks' endpoints come to the
pros': 2.66 / 4.19 degrees (AIM3), 2.71 / 4.32 (both terms off) at 15-30 / 30-60 degrees.

## 4. The parameters

| Parameter | What it is | default (the average pro) | better (p90) | max | Where the number is from |
|---|---|---|---|---|---|
| `AIM3` | the switch (with `AIM2` and its other switches as today) | 1 | 1 | 1 | |
| `AIM3_W` | the blend from AIM2's two terms to these (live: a run can open it slowly) | 1 | 1 | 1 | |
| `AIM3_PURSUIT_GAIN` | how much of the target's turn the eye follows | 1.0 | 1.0 | - | measured: no growth of the rail's error up to 100 deg/s |
| `AIM3_PURSUIT_TAU` | the eye's lag behind a change of the target's motion, seconds | 0.125 | 0.10 | - | measured: the error raised for about 150 ms after a turn-round; the fast end from the delays' ratio (below) |
| `AIM3_FIX_TAU` | how fast the eccentricity term fades once he is noticed, seconds | 0.10 | 0.10 | - | measured: settled 250-400 ms after he appears, the notice at about 200 |
| `AIM3_SIZE_A`, `AIM3_SIZE_B` | the base error = `PERCEPT_SIGMA` x (A + B x his half width in degrees) | 0.39, 0.355 | 0.39, 0.355 | - | measured: the pros' line 0.55 + 0.5 x half width, scaled to 1 at 500 units so `PERCEPT_SIGMA` keeps its meaning there |
| `PERCEPT_SIGMA` | the base error at 500 units, degrees | 0.9 | 0.64 | 0 | as today at default. Better: the pros' p90 of the settled lightning error is 0.71 of their average (0.77 against 1.08 half bodies, 1,202 player-games); today's better is 0.65 |
| `react_ms` / `acquire_ms` | the tracking delay / the notice delay | 125 / 225 | 100 / 175 | 25 / 25 | default as today. Better: the held shot's fast end is 200 ms against 269 (0.74) |
| `AIM2_C_SLIP` / `S0` / `CAP_SLIP` | the slip's size, now on the eye's slip only | 0.023 / 5 / 2.1 | 0.007 / 5 / 1.1 | 0 | as today (the 781-demo knob table of 2026-10-27); under AIM3 it acts on turn-rounds only |
| `AIM2_C_ECC` / `E0` / `CAP_ECC` | the eccentricity's size, now fading | 0.06 / 0 / 2.8 | 0.01 / 0 / 2.8 | 0 | as today |
| Hand noise `MOTOR_NOISE` / `MOTOR_BASE` | | 0.10 / 0.05 | 0.08 / 0.038 | as trained | as today: under AIM3 his flicks' endpoint error is at the pros' (12% of the travel against their 10 to 12%) |
| Flinch, the velocity and distance reads, the focus | | as today | as today | off | unchanged |

`worse` is on hold (owner). `max`: every perception and reaction limit off, the hand as trained, as today.

**Not from a measurement, and marked so:** better's `AIM3_PURSUIT_TAU` (taken from the delays' ratio) and the split of the measured
error between sight and hand (the pros' error is what their eyes AND hands leave; the size law's shape is theirs, its level is
today's `PERCEPT_SIGMA` at 500 units, where his error already equals theirs).

## 5. Rockets (owner: "think about anything structural that can help his rockets")

A readout of the same recordings (`tools/run/pro_aim.py`), then what is structural in it:

| | The pros | Him |
|---|---|---|
| Rockets fired an hour | about 640 | about 130 |
| ... with nobody in view | 66% | 9% |
| Where the view points on the shot, below the enemy's middle | 23 units (the floor under him) | 23 units |
| ... ahead of him, as a share of the full lead (his crossing speed x the rocket's flight) | +0.02 | **-0.17** |

1. **He aims behind a crossing enemy.** His picture of the enemy is a reaction time old (125 ms) and his read of the enemy's speed
   200 ms old with a +-20% error; the pros' rockets point at where the enemy IS (0.02), which means they make up their own delay.
   He does not fully (-0.17 of the lead: about 70 ms of flight behind). Structural candidates, to be measured before any is built:
   the rocket lead inputs (`RL_AIM`) are made from the delayed place and the late speed (do they include his own delay?); the size
   law and the eye (AIM3) reduce the error on the place they start from.
2. **He almost never fires where nobody is in view**, two thirds of what the pros do with the launcher. Nothing prices it any more
   (1.7a: the blind costs are 0), but nothing gives him a place to fire at or a reason either. This is a decision, not aim: the
   "spam" instruction of 2.0c (a corridor, a point from the brain's belief, the pass odds).
3. The reload's random extra delay (`RELOAD_JITTER`, mean 50 ms, the slow weapons only) is a small tax the lightning does not pay.
   A person's click is not on the exact frame either; to be measured on the pros (the gap between two rail shots against the reload)
   before it is touched.

## 6. Built, and proven

- `sim/duel_env.py`: `AIM3` (a `PLAY_VAR`), the live numbers `AIM3_W`, `AIM3_PURSUIT_TAU`, `AIM3_PURSUIT_GAIN`, `AIM3_FIX_TAU`,
  `AIM3_SIZE_A`, `AIM3_SIZE_B` (in `AIM2_LIVE`, so in `live.json`, the checkpoints, the exports; one a seat in a check:
  `SEAT_AIM`). The eye is kept a frame with his view (`_aim2_note`), read at his read delay (`_aim2_err`), cleared with it
  (`aim2_clear`). `sim/duel_env_ffa.py` regenerated.
- **Identity** (a fixed-seed game of 1,500 frames, six matches, AIM2's switches on, the sight error exercised on 1,576 player-frames;
  the inputs and the pay hashed): `AIM3` unset = before the change, in both modules; `AIM3=1` with `AIM3_W=0` and the size law at
  its defaults = the same hash; `AIM3=1` = AIM2's two terms about halved under random hands.
- `tools/ffa_check.py` cannot run here (it loads `testlab`, whose map file is missing): not a result of this change.
- **Not built:** the plugins need nothing new (they call `observe()`), but `tools/aim2_levels.py`'s table is not yet rewritten
  with the columns above, and no server has it. Nothing has trained under it.

## 7. Weaknesses

- **He has never trained under it.** His rail and rocket numbers under AIM3 understate what it allows (owner: "they will be
  skewed"); the first checks of a run are where the levels are confirmed, with every number live.
- **The pros' error is eyes and hands together.** The demos cannot split them; the shape of each law is measured, the level is
  anchored where his error already equals theirs (the lightning at 500 units).
- **Closer than 400 units the size law makes his sight error larger than today** (1.2 degrees at 325 units, 1.7 at 200, against
  0.9). That is what the pros' line says (they are no more exact than they need to be up close), but part of theirs is choice, not
  limit. His close lightning is the part of "tracking as it is" this could move; section 8: it did not (0.54 to 0.53 half bodies under 250 units).
- **Self-play opponents do not dodge as people do**: his small dip after a turn-round may be the opponent, not his eye.
- The tracking delay could not be read from the demos.

## 8. Him under the proposed default, untrained (a readout; nothing here is a target)

1.7a's update 90 against itself with section 4's default (`data/sim_runs/space/aimrec/aim3d`, 43 player-hours) and the held-angle
probe with and without it (`tools/run/hold_test.py`, tags h2 and h3: 292 and 293 frozen moments at the pros' holding places).

| | The pros | Him, AIM2 | Him, AIM3 default |
|---|---|---|---|
| Rail error after a flick of 15-30 / 30-60 degrees (56, 30 shots) | 2.36 / 3.92 | 4.91 / 6.39 | 3.90 / 3.96 |
| Lightning error in his first 250 ms in view / 250-400 ms | 1.32 / 1.11 | 2.36 / 1.59 | 2.37, 2.02 / 1.48 |
| Lightning error at 600-900 / 900-1,400 units, half bodies | 0.92 / 1.07 | 1.23 / 1.78 | 1.12 / 1.62 |
| Lightning error closer than 250 / 250-400 units | 0.75 / 0.77 | 0.54 / 0.58 | 0.53 / 0.62 |
| Lightning cells that hit, all / under 300 / 300-500 / 500-768 units | 44 / 48 / 46 / 44% | 43 / 53 / 42 / 29% | 46 / 54 / 47 / 35% |
| Held angle with the rail, his own aim, 8 s: dealt less taken (free play beside it) | | -9.4 +- 2.2 (-3.2) | -9.2 +- 2.2 (-1.0) |
| ... handed back 1.5 s after contact | | -6.4 +- 1.7 | -3.7 +- 1.8 |
| ... the first shot after the enemy is in view / it hits | 275 ms | 425 ms / 47% | 375 ms / 43% |

- **The flicks' endpoints move to the pros' at once**; the far lightning and the first 400 ms on a new target move a little. He was
  trained to aim under AIM2's errors and still plays that way: slow onto a target, never asked to be exact far away.
- **Tracking moves by about 3 points of hit share overall** (43 to 46%), from the far end; close in it is as it was. If that is
  more than "roughly as it is", `PERCEPT_SIGMA` is the one number to raise.
- **The held angle does not pay yet under either model** (the earlier small sample that read 38% against 46% was noise: 340 shots
  an arm). It is about 6 points behind free play over 8 s with his present hands. This is what the drills are for; the probe is
  the measure to repeat once he has trained under AIM3.

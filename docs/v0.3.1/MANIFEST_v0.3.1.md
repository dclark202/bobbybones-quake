# v0.3.1: the training manifest

*Written 2026-10-15 17:10 on the owner's word ("give me a training manifest of v0.3.1 including what needs to be built
still"). The one-page sheet is [RUN_v0.3.1.md](RUN_v0.3.1.md); the plans in full are [PROPOSAL_v0.3.1.md](PROPOSAL_v0.3.1.md).
Nothing below is started without the owner's go. Folder: `duel_gru_v0_3_1`. Changes during the run go into section 0.*

## 0. Changes during the run

None yet.

## 1. What it is

A fine-tuning of his mechanics after v0.3 (the owner: "a fine tuning of his weapon usage. An experiment post major
model version"): the hands of the v0.4 candidate.

**Build everything first, then resume training** (the owner, 2026-10-15 17:25: "for v0.3.1 we'll build everything first,
then resume training. No time set for starting yet"). One start, from v0.3's 18:00 stop point, with every part of
section 6 built and each proven alone (ten updates and a check against the control) before it joins. **No start time
is set**; the owner names it.

## 2. The start and the control

- **Start**: v0.3's last save, where it stops at 18:00 on 2026-10-15 (the owner, 17:20: "We'll pick up v0.3.1 from the 6pm stop point"; kept as `keep/policy_end.pt`).
- **Control**: v0.3's best save by its evaluation tonight (the standing rule: the last best network; it may be the same save). It stays in his league (`--anchor-p 0.25`: a quarter of his games) and every check plays it.
  v0.2 is checked once at the end.
- **Promotion**: only on the owner's word, and only if it beats the control.

## 3. What he trains on

| Session | Share of his time | Same as v0.3? |
|---|---|---|
| Whole ten-minute games with overtime, against the league | v0.3: 70% of game time, less by the new shares | yes |
| Mid-game starts | v0.3: 22% | yes |
| Movement practice: item runs and jump runs on the ten maps | as in v0.3 | yes |
| **Rocket drills**: short rounds on the ten maps, both players with the rocket launcher only (15 rockets) | **10%** | new (the owner, 2026-10-15) |
| **Rocket jump runs**: a pro's take-off to its landing, a ladder of three starts, a fading nudge on the look-down and the shot's moment | **2%**, only if ready | new |

The shares are read in a two-update dry run before the start and set right there.

## 4. His senses and his aim

- **Aim level 3** (the owner, 2026-10-15: "Set it to 3 going forward"). v0.2, v0.2.1 and v0.3 trained at level 1.5.
  At level 3: sight error 0.6 degrees, tracking delay 100 ms, noticing delay 200 ms, surprise up to 200 ms, flinch 0.25
  a point of damage up to 6 degrees, hand noise 0.10 and 0.05. The view inertia (0.75) and the flick cap (30 degrees a
  frame) do not move with the level.
- **The rail: the plan after the rail test and the pros' demos** (B-255; RESULTS 2026-10-15 16:50; for the owner's
  review, 2026-10-15 evening). What was found:
  - **No one limit brings the rail back.** v0.3's save 180 against the control, each limit eased to its level-3 value
    alone (Blood Run and Aerowalk, 8 games each, noisy): his rail hits rise 2 to 6 points (40% at level 1.5; 43 to 46%
    with less hand noise, no surprise delay, less flinch, or all of level 3), his rail shots a minute do not (4.1; 3.1 to
    4.5), his rail time in hand does not (18%; 15 to 20%). The noticing delay at 100 ms changed nothing.
  - **He is not slow to fire.** Where he fires the rail after an enemy appears he is as quick as the pros or quicker up
    to 80 degrees off the crosshair (20 to 40 degrees: 0.49 s against 0.71). The surprise delay stays as level 3 has it
    (up to 200 ms); cutting it would put him ahead of people.
  - **He does not take the shot.** An enemy who appears 40 to 80 degrees off gets a rail shot within 3 s in 55% of his
    sightings and 89% of the pros'; beyond 80 degrees 44% against 83%. In v0.3 the rail in hand fell from 18% to 9% while
    lightning took the time (half his time, 61% of his frags).

  So the rail is a matter of his choices, not his limits. The plan, in order, nothing a reward for one behaviour:
  1. **Aim level 3** (decided): his rail hits a few points up at once.
  2. **Measure why the wide shots are not taken**: after a sighting 40 degrees or more off, does he turn to the enemy
     (his turn in 0.3 s and its peak speed beside the pros': 10.5 degrees and 130 a second median), is the rail in his
     hand, does he switch to it, does the enemy leave his view first. The view inertia (`MOUSE_SMOOTH` 0.75, the same at
     every level) is read here: if his wide turns are slower than the pros', it is the one limit left to calibrate, from
     the pros' turn speeds, never past them.
  3. **The rail in hand**: the pros' weapon by distance (the weapon teacher's table)
     read beside his: if he holds lightning where the pros hold the rail (beyond 500 units: the pros 82% of their rail
     shots, he 18%), the weapon lesson from the pros' table at the start, fading, as the owner's rule for teachers has it
     (what stays must hold without it). The owner's call before it goes in.
  4. **Where to start from** (the owner asked, 2026-10-15: how far back to go for the rail). In v0.3 the rail in hand was
     18% at update 20, 16 to 17% to update 60, 15% at 70, then fell steadily to 9% by 180, while his checks against v0.2
     rose (57.5% at 70; 59.4 to 59.8% at 190 to 210). Going back to update 60 or 70 buys about 6 points of rail time
     and costs about 2 points against v0.2, and the same pressure (lightning pays more under his limits) would drain it
     again. The proposal: start from the 18:00 stop point as decided, and fix the cause; save 70 is re-checked in the
     evaluation beside the last, rail by rail, so the owner can choose.
  5. **Judged by**: his rail curve after a sighting (shots by 0.3 to 1 s, by angle) on the pros' and never ahead of it;
     the rail in hand and the rail's share of his frags; the check against the control.
- Unchanged: sight with line of sight and sound only, enemy projectiles only as a player sees them, no powerups.

## 5. The pay and the teachers

Unchanged from v0.3: the game's own pay (damage, frags, items, stack), no pay for a near miss, no styles
(`STYLE_P=0`), the ten maps, overtime. `WIN_PAY` (pay by the change in his chance of winning) is built and waits for
v0.4. No new single-behaviour reward.

## 6. What is built, and what still needs building

| # | Part | State | Work left | Order |
|---|---|---|---|---|
| 1 | Aim level 3 in training | **built** (a setting) | the run's `.cmd`; the checks' settings (diag5 and the night watcher still carry `AIM_LEVEL=1.5`) set to 3 | any time |
| 2 | Rocket drills | **built** (`--drill-p`, `--drill-weapons rl`) | check that a drill round is on the real maps and not in a box; that it does not break the whole-game clock; the share in a dry run | any time |
| 3 | The rail (section 4) | **the limits measured**: none brings it back; the surprise delay stays as level 3 has it | his rail curve at level 3 (`tools/bobby_yardsticks.py`); why wide sightings get no shot (his turn, the weapon in hand, the enemy gone); the view inertia calibrated from the pros' turns if his are slower; the pros' weapon table beside his, and a fading weapon lesson only on the owner's word | after 4 |
| 4 | The rail test (which limit costs the rail) | **6 of 7 arms done** (all of level 3: two maps of four) | the last two maps; the summary's parser fixed; more games on the arms that moved the hits (hand, flinch, level 3) if the owner wants them firmer | now |
| 5 | Rocket jump check: the game against the simulator | **not built** | a measuring plugin beside `plugins/weaponlab.py` (about 200 scripted jumps on a private server), the same jumps in the simulator, compared (rise and distance within 5%, damage exact); about a day | before 6 |
| 6 | Rocket jump runs | **not built**; the pros' rocket jumps are found (`docs/pro_rocket_jumps.json`) | the runs' code in a staging copy, the ladder of starts, the fading nudge, proven to change nothing when off; the links drawn for the owner's keep or drop; in only if 5 passes | after 5 and 8 (the runs train the legs) |
| 7 | The learning step rebuilt (B-237) | **not built** | the library's GRU over whole sequences, proven to give the same loss and gradients on a saved update; about a day; every run after it about twice as fast | first |
| 8 | His legs inside the network (B-253) | **not built** | the movement network as a branch of his, in the trainer, the checks' tools, the export and both plugins; stage (a) frozen and proven to play exactly as today, (b) learning at a quarter of the rate, (c) links from his memory; one to two days | after 7 |
| 9 | Rocket and projectile aim (B-254) | **measured** (his first rocket as soon as the pros', the first hit far later, 2.1 rockets a minute against 10.8) | his lead inputs checked against what a player aims at (the floor under the enemy's predicted place); the drills read by whole games | before the start |
| 10 | The checks' tools at level 3, round length fixed | **not done** | `round_secs` 600 in `bobby_yardsticks.py`, `opening_check.py`, `memory_reach.py` | tonight, for v0.3's evaluation |

## 7. How it is judged

- **Every tenth update**: 160 ten-minute whole games against the control on ten maps (level 50%, one check moves about ±3).
- **His rockets at every check, in whole games only**: rockets a minute, damage a rocket, direct hits, share of the frags,
  time in hand. The drills stay only if these rise and the check holds.
- **His rail at every check**: hit rate by distance, shots a minute, time in hand (v0.3: 9%; the pros: 18% and more),
  and his curve of rail shots after a sighting against the pros'.
- **Rocket jumps** (if in): arrivals per link in the runs; rocket jumps a game in whole games beside the pros' table;
  none at low health.
- The weapon watch as in v0.3.

## 8. When it stops

- **By itself**: under 47% at update 10, two checks under 45%, or three checks falling.
- At its time limit (set by the owner with the start).
- A line an hour at night, a mid-run report at 07:00, a report at the end.

## 9. Before the start (no time set)

1. v0.3 ends at 18:00; its evaluation; the owner's play test.
2. Section 6 built in its order, each part proven alone: ten updates and a check against the control.
3. The `.cmd` written; two updates of a dry run read for the sessions' shares and the step a part.
4. The owner's go and the start time.

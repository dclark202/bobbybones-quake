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
- **The rail's surprise delay, calibrated by the pros' demos** (B-255; RESULTS 2026-10-15 16:50): his share of
  sightings with a rail shot by 0.3, 0.5, 0.75 and 1 s, by angle off the crosshair, set on the pros' curve and never
  ahead of it. The first read says he is not slower than the pros where he fires, and fires far less often at wide angles.
  So the value may stay as it is; the fix may be elsewhere (see the rail test, section 6).
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
| 3 | The rail's surprise delay | **measured for the pros**; not set | his curve at level 3 from `tools/bobby_yardsticks.py` (scheduled after the rail test), a value set for the rail or by where he held his crosshair, behind a switch, proven to change nothing when off | after 4 |
| 4 | The rail test (which limit costs the rail) | **running**: 3 of 7 arms done, a fourth half done | flinch, the noticing delay at 100 ms, all of level 3; the summary's parser fixed | now |
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

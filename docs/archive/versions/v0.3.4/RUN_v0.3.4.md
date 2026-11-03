# v0.3.4 on one page: the legs blended into him

*Written 2026-10-18 after the run, from the noon report of that day. Folder `duel_gru_v0_3_4`. The plan it serves: one
movement network ([../v0.4/UNIFIED_MOVEMENT.md](../v0.4/UNIFIED_MOVEMENT.md), B-259). Status: **over** (Sat 2026-10-17 about
09:00 to Sun 06:49); its end, save 283, is where v0.3.5 began. Its best check: save 223, 57.5% against v0.3.1's end.*

## What ran

From v0.3.2's update 140. His legs still drive while a switch output is on; the run's job was to make him able to drive
himself so that the switch could go.

| Part | What it is | State |
|---|---|---|
| A | a gate on the legs' output and a motor line from the legs' inner layer into his own movement outputs | in |
| Step 3 | `legs_door`: the legs' layer into his fast memory | in |
| B | a turn-down dial and a residual on the frames the legs drive | **removed** Sat 18:30 (the owner) |
| C | `--solo-self-drive` (in item and jump runs he drives himself); the switch fade (a bias against the switch while his solo speed is at the gate or above) | in; the fade from stage 2 |

Kept from v0.3.2 and v0.3.3: `LEGS_TURN_ADD`, `WALK_NO_JUMP`, `HOP_QUIET`.

**Settings:** v0.3.1's pay (frag ±1, damage 0.0055 a point, taken at 0.82 of it, mega and red armor 0.25, yellow 0.12, shot
price 0.10 with rockets at half and grenades and plasma free, blind rockets 3 points, speed pay 0 in games and 0.3 in solo
runs, hop pay 0.001, 0.003 from stage 2). Solo runs 20% of his time (item runs 10, jump runs 10). The blend's learning rate
0.25 of the run's (0.5 from Sat 11:42 to the stop at 18:20, then 0.25 again). Aim level 3. Control: v0.3.1's end.

## What happened

| When | What |
|---|---|
| Sat ~09:00 to 16:00 | first stretch: checks 49.3 to 53.3% (most 52 to 53) |
| Sat 16:00 to 18:00 | **unstable**: kl 0.027 to 0.54, clip 0.23 to 0.63, B's dial went to its full weight, the blend's kl to 0.2; save 110 read 47.0%, save 120 27.3%. Stopped 18:20 |
| Sat 18:41 | **stage 1**: restart from save 90 with B's weights stripped from him and the league, blend at 0.25 |
| Sun 03:43 | **stage 2** (the owner's 03:00 deadline): the fade gate at 308 u/s (his solo speed was 318 to 320), hop pay 0.003 |
| Sun 06:49 | stopped at save 283 for v0.3.5 (the owner's go) |

**Checks against v0.3.1's end** (160 ten-minute games on ten maps; the same network against itself reads 48.8%):

| Saves | Stage | Score |
|---|---|---|
| 133 to 203 | stage 1 | 53.1, 52.9, 53.6, 54.3, 54.8, 55.6, 55.8, 55.6% |
| 213, **223**, 233 | stage 1 | 56.9, **57.5% (106 won, 49 lost)**, 56.6% |
| 243 to 283 | stage 2 | 55.2, 56.2, 50.8, 50.9, 53.0% |

Stage 1 was steady (kl about 0.023, the blend's 0.0004), his solo speed when he drives himself rose from 310 to about 320,
frags 2.3 to 2.8 a match-minute.

## What did not work

- **The dial B** took the run off its rails in two hours, and it was seen two hours late (the hourly checks did not fire;
  the alarm needed a check drop beside the kl rise).
- **The switch fade did not retire the switch.** Its bias reached its maximum of 8, and the switch was still on 35 to 39% of
  his game time: he learned to push the switch output up against the bias, because the legs paid (348 u/s in games against
  291 on his own feet). The checks lost about 5 points while the fade fought the switch.

## Files

`data/sim_runs/duel_gru_v0_3_4/keep/`: `policy_90_noB.pt` (stage 1's start), `policy_unstable_123.pt`,
`policy_223.pt` (the best check), `policy_stage1_end_243.pt`, `policy_stage2_end_283.pt`; every tenth save beside them. The results log: RESULTS 2026-10-17 18:20, 2026-10-18 03:43 and 06:49.
Next: [../v0.3.5/RUN_v0.3.5.md](../v0.3.5/RUN_v0.3.5.md).

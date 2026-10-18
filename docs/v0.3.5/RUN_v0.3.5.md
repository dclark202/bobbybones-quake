# v0.3.5 on one page: the switch removed

*Written 2026-10-18 12:35 from the noon report of that day and the run's checks. Folder `duel_gru_v0_3_5`. Step 6 of
[../v0.4/UNIFIED_MOVEMENT.md](../v0.4/UNIFIED_MOVEMENT.md) (B-259). Status: **training** since Sun 2026-10-18 06:55, to 19:00
Sunday; the owner, 2026-10-18: "Giving up on removing the switch is not an option." A clumsier v0.3.1 with one movement
network is an acceptable result; fewer items are acceptable, judge by frags and wins.*

## What runs

From v0.3.4's save 283 with `--no-switch 1`: the legs switch output is gone, he drives himself on every frame, the legs' layer
inside him feeds his movement through the motor line and the door. The league's v0.3.4 snapshots and the control keep their
switches. Everything else as in v0.3.4's stage 2: solo runs 20%, hop pay 0.003, B off, the blend at 0.25, `LEGS_TURN_ADD`,
`WALK_NO_JUMP`, `HOP_QUIET`, aim level 3. Control: v0.3.1's end (the network on the public server).

**Restarts**, each right after a save, each start kept in `keep/`:

| When | From | Change | Why |
|---|---|---|---|
| 06:55 | v0.3.4's 283 | the start | |
| 07:41 | save 10 | `--solo-self-drive 1` | brings back the solo-speed reading; nothing changes in play with the switch gone |
| 09:17 | save 30 | the legs part's learning rate 0.25 to **1.0** (its design value) | checks flat at about 43% (the owner's go) |
| 10:53 | save 50 | **speed pay 0.05 in games** (`SPEED_PAY`) | his trip speed in games stuck at about 300 (the owner's go) |

## Checks against v0.3.1's end (160 ten-minute games on ten maps)

| Save | Setting | Score |
|---|---|---|
| 10, 20, 30 | legs learning 0.25 | 43.5, 43.7, 43.7% |
| 40 | legs learning 1.0, 10 updates in | 42.8% |
| **50** | legs learning 1.0, 20 updates in | **45.7% (66 won, 85 lost): the first rise** |
| 60 | speed pay 0.05, 10 updates in | 45.0% (65 won, 90 lost) |

The loss follows how much a map leaned on the legs: Blood Run (the legs drove 45% of v0.3.4's time there) 31% at save 40 and
41% at 50; Aerowalk (21%) and Toxicity (28%) about level. Against v0.3.4's best (save 223), at update 20: his aim is the
same (rockets 50.5%, lightning 47.3%, rail 44%), his mean speed 292 against 319, time at 400 u/s or more 4% against 19%, megas
taken 38% against 49%, his kills a minute 1.27 against 1.71, his deaths 1.54 against 1.33. **He loses on speed in games**:
items come later, the stack is weaker, fights are lost.

## The run at noon

Steady (kl 0.024 to 0.026, clip 0.25 to 0.27). Solo-run speed 332 to 334, his best; trip speed in games 300 to 310, not up yet.
The speed pay earns 0.01 to 0.03 a player-minute, 2 to 3% of the frag pay: smaller than estimated. Mega and red pickups 2.0 to
2.5 a minute; holding places 3 to 4% of his choices. The legs part has moved 3% since the restart (the guard: 5% in ten
updates means back to 0.5).

## What did not work

- Thirty updates at the legs' old learning rate (0.25) stayed flat at 43 to 44%.
- The speed pay at 0.05 did not move his trip speed in its first ten updates; it is 2 to 3% of the frag pay.
- Five restarts in one morning: each costs a warm-up of 10 to 15 updates (frags start near 0.3). Changes are to be batched.

## Next (the owner's, 2026-10-18)

- The noon play test of v0.3.4's end and v0.3.5; then a restart at a save with speed pay 0.15 in games, `HOP_QUIET_HEARD 1`,
  `HOP_QUIET_NEAR 300`, the optimizer's state kept across restarts (B-263) and the awareness counters with the emergence point
  (`AWARE_LOG`, B-261). The code is in v0.3.5's working copy, not yet committed.
- **19:00**: v0.3.5 stops at a save (kept) for the play test, whatever happens before; afterwards it resumes unless the owner
  decides otherwise. While nothing trains: the awareness check, the emergence-point baseline on the pros' demos, the rocket
  measurement, v0.3.6's fixed-seed replays.
- v0.3.6 ([../v0.4/ROCKETS_v0.3.6.md](../v0.4/ROCKETS_v0.3.6.md)) starts only on the owner's call, from how v0.3.5 goes.

## Files

`data/sim_runs/duel_gru_v0_3_5/keep/`: `policy_start.pt`, `policy_30_ll025_end.pt`, `policy_50_before_speedpay.pt`. The results
log: RESULTS 2026-10-18 06:49, 11:30 and 12:20.

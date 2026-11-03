# BobbyBones: plan

**Goal:** a Quake Live bot that learns to play (movement, aim, items, position, tactics) and beats people fairly: human
physics, human limits, knowledge only from sight and sound. "v1.0 starts when he can beat me" (the owner). He plays the
game's ten duel maps (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds, Hektik,
Toxicity, Cure), all in training; House of Decay and Dismemberment are held out for checks.

**One goal: win games** (the owner, 2026-10-24: "There is only one goal: win games"). Each generation has its own goals; **b1** (2026-10-31,
replaces v0.6.x's pay by win chance only): win chance pay is an addition on top of the pay table, which stays; then the hard-coded rules come
out and the strategy head comes in, one step at a time. Open items beside them: rocket jumps and failed movement jumps (built, off).

## The b1 series (BobbyBones 1; runs are bN.Nx, the names from here on)

| Run | One new thing | State |
|---|---|---|
| b1.0a | win chance pay in, on top of the unchanged table (`WIN_ADD` to 0.33, about a third of the total), from v0.6.0's end | done 2026-10-31 21:00, a success ([card](runs/b1.0/b1.0a/CARD.md)) |
| b1.1a | ready for strategy: the brain's old belief, the pull toward level and the target lock out | done 11-01 ([card](runs/b1.1/b1.1a/CARD.md)). **b1.1** = its save before the lock's fade: brain and pull out, lock 8 s |
| b1.2a | the strategy head in, learning from combat plus win pay | **unusable:** crashed 11-01 15:18 at update 82; the head and the hands fought over his target logits ([card](runs/b1.2/b1.2a/CARD.md)) |
| b1.2b | every health and armor item priced, zero-sum, per point gained; then the firing costs out; then free target choice in contact; then the jerk cost out | stopped 11-01 17:40 at update 20 ([card](runs/b1.2/b1.2b/CARD.md)) |
| b1.2c | b1.2b's plan, with every small health and armor item as an input: what it is, where, the way, its state by what he knows | stopped 11-02 12:52 at update 250 for b1.2d; 55.6% against b1.1 ([card](runs/b1.2/b1.2c/CARD.md), [design](design/SMALL_ITEMS.md)) |
| b1.2d | the pay table by the point (0.004 up to 100, 0.002 above, decay charged back), speed pay halved, damage taken 0.8, the stack lead out, long rail 0.25, all faded in over updates 10 to 70; the table the baseline, win pay the correction | done 2026-11-02 13:33 to 19:41, ended at update 80: **a success** (owner) ([card](runs/b1.2/b1.2d/CARD.md)) |
| b1.3a | the strategy head in, **shut in play**, learning to copy his target choice (the rules as he plays them); the hands train on as b1.2d (owner, 11-02 evening) | ended 11-03 07:17 at update 130 (owner): the copy 86.8%, play about level with b1.2d's end; the head alone 37% against b1.2d's end (a hard swap fails: b1.4a blends) ([card](runs/b1.3/b1.3a/CARD.md)) |
| b1.4a | the head blended in: half his target choice from the head, half from the rules' frozen imprint (mix 0 → 0.5 over updates 10 to 90), the head learning from his whole pay; the lock (owner's review 11-03 evening) and the way pay stay (owner, 11-03) | **stopped 11-03 11:12 at update 21** (owner): b1.3 to be redesigned and started over ([card](runs/b1.4/b1.4a/CARD.md)) |
| 1.3b | b1.3 redone (owner, 11-03: b1.3a's copy and b1.4a's blend scrapped): from b1.2d's end, his target choice gets the strategy head's slow memory: the head's own scores added to the hands' (at zero at the start: he plays exactly as b1.2d), one learner, the credit moved to the head's advantage (λ 0.995) over updates 10 to 90 | **built, not started** ([card](runs/b1.3/1.3b/CARD.md); the review: [reviews/REVIEW_b1.2-b1.4.md](reviews/REVIEW_b1.2-b1.4.md)) |
| 1.4b | from 1.3b's end, about 24 h (owner, 11-03; 1.4c merged into it): the item rule's lesson out, the speed pay the same for every target, the switch cost out, the weapon rule out, the target lock outside contact 8 s → 0, one after the other | planned ([card](runs/b1.4/1.4b/CARD.md)) |
| later | the pros' tables, rocket jumps and movement mechanics, in an order not yet set | planned |

**Names (owner, 2026-10-31):** bN is the series; bN.N a family of runs with a specific goal; bN.Nx a run in it, the attempts x = a, b, c, ... A failed attempt gets the next letter (b1.1b), not a new number. **From 2026-11-03 (owner) the b is dropped:** new runs are 1.3b, 1.4b, 1.4c, ...; b1.0a to b1.4a keep their names. Yardstick: v0.6.0's end. The reasons, gates and open points: [design/B1_PLAN.md](design/B1_PLAN.md).

**Judged by** duels against the last best network (the control), how near his play comes to the pros' measures, the
owner's play tests and what people do to him on the public server; the game's Nightmare bot is a floor.

What lives where in `docs/` and the routine that keeps it: [README.md](README.md).

## Approach

1. **Learn in a fast simulator, check in the real game.** The simulator (`sim/`) runs the game's own movement thousands
   of times faster than real time; every skill gets a check on a real server before it is trusted.
2. **Self-play reinforcement learning**, seeded where needed by fading lessons from the pros' demos.
3. **Measure against people**: play tests, the public server's logs, the pros' demos.

## Status (2026-10-28)

| | |
|---|---|
| Best network | v0.4.2b's end (`data/sim_runs/duel_gru_v0_4_2/keep/policy_end_v042.pt`; backup `T:\BobbyBones_backup`) |
| Public servers | v0.4.2b's end with `!aim` worse / default / better / max (aim2, measured on the pros), branch `pub-aim2` = `main`'s server code |
| Now (2026-10-31) | v0.6.0 (update 80) on both public servers and released as open weights; b1.1 done ([runs/b1.1/README.md](runs/b1.1/README.md)); the v0.6.1 line (b, c, d, e) ended ([runs/v0.6.1d/REVIEW_v0.6.1.md](runs/v0.6.1d/REVIEW_v0.6.1.md)) |
| Now (2026-11-01) | b1.1 on both public servers (network files only, about 13:00; v0.6.0 before it); b1.2a running from b1.1, started 09:08, 24 h |

What has been tried and what it taught: [HISTORY.md](HISTORY.md). Open work: [BACKLOG.md](BACKLOG.md).

## Standing decisions of the owner

- **Fairness**: human physics (125 fps); sight with line of sight and sound only, enemy projectiles too; human reaction,
  flick speed and hand noise; never miss on purpose; no wallhacks.
- **Method**: limit what he can do until the right play appears; do not add rewards for single behaviors without asking;
  the reward is the owner's call. Fading lessons from the pros are fine; what stays must hold without them.
- **Pay is judged by its equilibrium** (the owner, 2026-10-15; 2026-10-24): whenever pay weights are discussed, the equilibrium they lead to in self-play (the zero-sum parts beside the parts both copies gain from), the behaviour it makes emerge on the way to the generation's goals, and whether it ends up winning more games, the one goal.
- **Aim level 3 from v0.3.1 on** (the owner, 2026-10-15: "Set it to 3 going forward"): level 1.5 (v0.2 and v0.3, B-228's step one)
  cost the rail most; training, the checks and the servers use 3.
- **One movement network before v0.4's head** (the owner, 2026-10-16 and 2026-10-18): his legs and his own network become one driver; "Giving up on removing the switch is not an option." A clumsier v0.3.1 with one movement network is an acceptable result; fewer items are acceptable, judge by frags and wins.
- **Duel is the main mode** (2026-10-16): changes that limit or break free-for-all are fine.
- **Training partners**: himself, his league and the control; the game's bots are a benchmark only.
- **Promotion**: a network goes on the public server only on the owner's word and only if it beats the control.
- **Rounds**: whole ten-minute games and mid-game starts only, one against one (2026-10-13).
- **No powerups** anywhere, and each map's duel items in every mode (2026-10-09).
- **Runs**: one batch of changes, then wait; no changes mid-run unless the data is clearly bad. Before a start: the report
  of the last network, the one-page run sheet of the next, the public server's state; the owner gives the go.
- **Reports**: one line an hour at night, a mid-run report in the morning, a full report at the end with what to try next.
- **Names**: from 2026-10-31 b1.n.x (BobbyBones 1; b1.0a); before that v0.1 was v15c, trials of a version got a further index (v0.2.1); v1.0 when he beats the owner.
- **No personal data** in the repo; logs from the public server keep people as random ids only.

The plan and the log before v0.1 (the numbered models v1 to v15b and the first approach) are kept locally, out of the repo.

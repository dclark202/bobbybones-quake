# BobbyBones: plan

**Goal:** a Quake Live bot that learns to play (movement, aim, items, position, tactics) and beats people fairly: human
physics, human limits, knowledge only from sight and sound. "v1.0 starts when he can beat me" (the owner). He plays the
game's ten duel maps (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds, Hektik,
Toxicity, Cure), all in training; House of Decay and Dismemberment are held out for checks.

**One goal: win games** (the owner, 2026-10-24: "There is only one goal: win games"; the five goals of 2026-10-13 are retired). Each generation has its own goals; **v0.4.x**: fade out every hard-wired rule, the brain manages the game state and the strategy, pay by win chance only. Open items beside them: rocket jumps, failed movement jumps, grenades less so. The path: [v0.4.0/PATH_v0.4.md](v0.4.0/PATH_v0.4.md).

**Judged by** duels against the last best network (the control), how near his play comes to the pros' measures, the
owner's play tests and what people do to him on the public server; the game's Nightmare bot is a floor.

What lives where in `docs/` and the routine that keeps it: [README.md](README.md).

## Approach

1. **Learn in a fast simulator, check in the real game.** The simulator (`sim/`) runs the game's own movement thousands
   of times faster than real time; every skill gets a check on a real server before it is trusted.
2. **Self-play reinforcement learning**, seeded where needed by fading lessons from the pros' demos.
3. **Measure against people**: play tests, the public server's logs, the pros' demos.

## Status (2026-10-18, noon)

| What | Where it stands |
|---|---|
| On the public server | **v0.3.1** since 2026-10-16 evening (the end of v0.3.1's restart, `duel_gru_v0_3_1b`: his legs learning, the game's physics, the hunt, the believed stack; 63.8% against v0.3's end). It is the control of every run since. [results/2026-10-16.md](results/2026-10-16.md), [v0.3.1/RUN_v0.3.1.md](v0.3.1/RUN_v0.3.1.md) |
| The run now | **v0.3.5** (`duel_gru_v0_3_5`), since 2026-10-18 06:55: one movement network, the legs switch removed (B-259). 43 to 44% against v0.3.1's end for 40 updates, 45.7% at save 50 after the legs' learning rate went to 1.0, 45.0% at 60; he loses on speed in games. Trains to 19:00 Sunday, then the owner's play test; it resumes afterwards unless he decides otherwise. [v0.3.5/RUN_v0.3.5.md](v0.3.5/RUN_v0.3.5.md) |
| Behind it | v0.3.2 (the turn correction): level; v0.3.3: stopped after five updates; v0.3.4 (the legs blended in): 57.5% at its best (save 223), the switch fade failed. [v0.3.2/RUN_v0.3.2.md](v0.3.2/RUN_v0.3.2.md), [v0.3.4/RUN_v0.3.4.md](v0.3.4/RUN_v0.3.4.md) |
| Ready | **v0.3.6**, rockets and grenades (branch `v036`, not merged): the rocket aim inputs, the pre-fire token, the emergence point, blind rockets free, the long-range rail pay, the hot reload (B-265); no rocket-jump runs at its start. Starts the night of 2026-10-18 from v0.3.5's save, after the play test and the BIOS update, for several days (the owner). [v0.4/ROCKETS_v0.3.6.md](v0.4/ROCKETS_v0.3.6.md); what is left before strategy: [v0.4/MECHANICS_BEFORE_STRATEGY.md](v0.4/MECHANICS_BEFORE_STRATEGY.md) |
| Then | **v0.4**: the movement bridge's clean-up (step 6b of [v0.4/UNIFIED_MOVEMENT.md](v0.4/UNIFIED_MOVEMENT.md)), then the head (strategy, five times a second, a store of three minutes) on one movement network: [v0.4/CANDIDATE_v0.4.md](v0.4/CANDIDATE_v0.4.md), [v0.4/PROPOSAL_v0.4.md](v0.4/PROPOSAL_v0.4.md) |
| Checks of a run | every tenth save plays the control in 160 ten-minute games on ten maps, aim level 3 (the same network against itself reads 48.8%, a single map moves about ±10 points); the weapon in his hand at every check |

## Now

The generation's goals and rounds: [v0.4.0/PATH_v0.4.md](v0.4.0/PATH_v0.4.md) (the owner, 2026-10-24). The run now: **v0.4.2** ([v0.4.0/RUN_v0.4.2.md](v0.4.0/RUN_v0.4.2.md)).

The backlog items in work or next ([BACKLOG.md](BACKLOG.md)):

- One movement network: B-259 (v0.3.5 now), B-263 (the optimizer's state at restarts), B-261 (the emergence-point baseline, while nothing trains).
- v0.3.6, rockets: B-252 (rocket jumps), B-254 (rocket aim, the pre-fire token), B-262 (the emergence point as an input), B-264 (its inputs in a real game).
- v0.4: B-250, B-240 (the enemy in his head), B-248 (slower memory), B-256 (the hunt in the head).
- 1, speed: B-213, B-204, B-258.
- 2, rockets: B-210.
- 3, plasma, grenades: B-189.
- 4, game awareness: B-217 (predictable routes), B-216, B-221, B-191.
- The checks and the demos: B-218, B-219, B-220, B-225, B-226.
- Aim and the fights he takes: B-229, B-230, B-231.
- The simulator and the maps: B-224, B-227.
- Odd behaviour seen in runs and duels: B-214, B-215, B-192.

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
- **Names**: v0.1 was v15c; trials of a version get a further index (v0.2.1); v1.0 when he beats the owner.
- **No personal data** in the repo; logs from the public server keep people as random ids only.

The plan and the log before v0.1 (the numbered models v1 to v15b and the first approach) are kept locally, out of the repo.

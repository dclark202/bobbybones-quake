# BobbyBones: plan

**Goal:** a Quake Live bot that learns to play (movement, aim, items, position, tactics) and beats people fairly: human
physics, human limits, knowledge only from sight and sound. "v1.0 starts when he can beat me" (the owner). He plays the
game's ten duel maps (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds, Hektik,
Toxicity, Cure), all in training; House of Decay and Dismemberment are held out for checks.

**One goal: win games** (the owner, 2026-10-24: "There is only one goal: win games"). Each generation has its own goals; **v0.6.x**:
pay by win chance only (fitted directly on game results, "B"), then the strategy head and the item rule's fade (v0.6.2). Open items
beside them: rocket jumps and failed movement jumps (built, off).

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
| Now | v0.6.0 (update 80) on both public servers and released as open weights; v0.6.1 ready to start: pay by win chance from the frozen judge, 24 h ([runs/v0.6.1/CARD.md](runs/v0.6.1/CARD.md)) |
| Next | v0.6.1's run; v0.6.2 = the judge learning on his new games (more inputs; the weapons' hand-set worth removed at its refit) and the strategy head ([runs/v0.6.2/CARD.md](runs/v0.6.2/CARD.md)) |

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
- **Names**: v0.1 was v15c; trials of a version get a further index (v0.2.1); v1.0 when he beats the owner.
- **No personal data** in the repo; logs from the public server keep people as random ids only.

The plan and the log before v0.1 (the numbered models v1 to v15b and the first approach) are kept locally, out of the repo.

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

## Status (2026-10-24)

| What | Where it stands |
|---|---|
| On the public servers | **v0.3.10** (US and EU, duel only; plugins updated 2026-10-24: the name, the banter, the quit rule). The next push is the owner's call (before it: the hindsight review of games against people, the name `^6BOT ^5B^7o^5bbyB^7o^5nes`); the shared-board deploy waits for his go |
| Behind us | v0.3.2 to v0.3.11: one movement network (the legs switch retired), rockets and pre-fire, the doorway watching; **v0.4.0/0.4.0b** the brain; **v0.4.1** the brain's token in the hands: 64 to 71% against v0.4.0b's end, 159-1 against v0.3.6 (ended 2026-10-24 07:12, update 320, `keep/policy_end_v041.pt`) |
| The run now | **v0.4.2** (`duel_gru_v0_4_2`, since 2026-10-24 07:14): the old belief faded out of the hands; mega flat pay 0.35 (owner). The checks at the fade still shut read 42.5% (updates 10 and 30) against v0.4.1's end; a diagnostic of the checks is running; the fade is held shut until a check passes. Officially to Sunday noon, ended early on a good night. [v0.4.2/RUN_v0.4.2.md](v0.4.2/RUN_v0.4.2.md) |
| Next | **v0.4.3**, the strategy head (card for the owner's review: [v0.4.3/RUN_v0.4.3.md](v0.4.3/RUN_v0.4.3.md)), then the win-chance rounds: [v0.4.0/PATH_v0.4.md](v0.4.0/PATH_v0.4.md) |
| Checks of a run | every 20 updates 160 ten-minute games on ten maps at aim level 4 against the previous best; every fourth against the long-term control (v0.3.10's end from v0.4.2); the same network against itself reads about 49%, ±4 points a check, a single map about ±10 |

## Now

The generation's goals and rounds: [v0.4.0/PATH_v0.4.md](v0.4.0/PATH_v0.4.md) (the owner, 2026-10-24). The run now: **v0.4.2** ([v0.4.2/RUN_v0.4.2.md](v0.4.2/RUN_v0.4.2.md)).

- v0.4.2: the fade (the rule columns out of the hands); B-275 (the level pull, out in v0.4.3).
- v0.4.3: the head; B-280 ("in control" as a brain readout), B-279 (grenades and plasma as area denial), B-278 (items' worth in fights).
- Win-chance pay (v0.4.4 on): the overtime fix, his own win table, the cross-fade.
- Open items: rocket jumps (B-252; the full-route copy built, off), failed movement jumps (the Aerowalk red-armor two-hop route copy, built), B-277 (too much jumping at times), B-276 (stuck behind the teleporter on Cure).
- The full open list: [BACKLOG.md](BACKLOG.md).

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

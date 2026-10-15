# BobbyBones: plan

**Goal:** a Quake Live bot that learns to play (movement, aim, items, position, tactics) and beats people fairly: human
physics, human limits, knowledge only from sight and sound. "v1.0 starts when he can beat me" (the owner). He plays the
game's ten duel maps (Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds, Hektik,
Toxicity, Cure), all in training; House of Decay and Dismemberment are held out for checks.

**Judged by** duels against the last best network (the control), how near his play comes to the pros' measures, the
owner's play tests and what people do to him on the public server; the game's Nightmare bot is a floor.

What lives where in `docs/` and the routine that keeps it: [README.md](README.md).

## Approach

1. **Learn in a fast simulator, check in the real game.** The simulator (`sim/`) runs the game's own movement thousands
   of times faster than real time; every skill gets a check on a real server before it is trusted.
2. **Self-play reinforcement learning**, seeded where needed by fading lessons from the pros' demos.
3. **Measure against people**: play tests, the public server's logs, the pros' demos.

## Status (2026-10-15)

| What | Where it stands |
|---|---|
| On the public server | **v0.2** since 2026-10-12: free-for-all, two Bobbys, the ten duel maps in the vote, a leaderboard. [v0.2/REPORT_v0.2.md](v0.2/REPORT_v0.2.md) |
| The run now | **v0.3** (`duel_gru_v0_3`), the new baseline: whole ten-minute games with overtime, mid-game starts, the pros' openings, places as targets, the real clock, no styles. Started 2026-10-14 20:17, runs to 18:00 on 2026-10-15 (the owner: so he plays enough whole games); evaluation by 19:00. [v0.3/RUN_v0.3.md](v0.3/RUN_v0.3.md), [v0.3/MIDRUN_v0.3.md](v0.3/MIDRUN_v0.3.md) |
| Next | **v0.3.1**, the mechanical side (the owner, 2026-10-15): the learning step rebuilt, his legs inside the network, rocket jumps, rocket and projectile aim: [v0.3.1/PROPOSAL_v0.3.1.md](v0.3.1/PROPOSAL_v0.3.1.md). Then **v0.4**, the candidate (2026-10-15): the hands (v0.3, every frame, his legs inside) and the head (strategy, five times a second, a store of three minutes), about 9 M weights: [v0.4/CANDIDATE_v0.4.md](v0.4/CANDIDATE_v0.4.md). From the proposal: a bigger network (about 13.7 M weights), a store of his past read by attention, a judge of the game's result, the pay leaning on winning (B-250). [v0.4/PROPOSAL_v0.4.md](v0.4/PROPOSAL_v0.4.md), [v0.3/PLUTO.md](v0.3/PLUTO.md) |
| Trials between | v0.2.1 stopped twice ([v0.2.1/AUDIT_v0.2.1.md](v0.2.1/AUDIT_v0.2.1.md)); the test runs of 2026-10-13 and 14 that led to v0.3 ([v0.2.2/NIGHT_1013.md](v0.2.2/NIGHT_1013.md)) |
| Checks of a run | every tenth save plays the control in 160 ten-minute games on ten maps (level 50%, one check moves about ±3 points); the weapon in his hand at every check |

## Now

The owner's priority list (2026-10-10): (1) strafe jumping and keeping speed; (2) rockets; (3) plasma and grenades, the
shotgun less; (4) game awareness. The five goals (2026-10-13): speed and movement, weapon use, positioning,
counterplay, beating people.

The backlog items in work or next ([BACKLOG.md](BACKLOG.md)):

- v0.3.1: B-237 (the learning step, first), B-253 (the legs inside), B-252 (rocket jumps), B-254 (rocket and projectile aim), B-251 (aim from the free-for-all games).
- v0.4: B-250, B-240 (the enemy in his head), B-248 (slower memory).
- 1, speed: B-211 (his legs in games), B-213, B-204.
- 2, rockets: B-210.
- 3, plasma, grenades: B-189.
- 4, game awareness: B-217 (predictable routes), B-216, B-221, B-191.
- The checks and the demos: B-218, B-219, B-220, B-225, B-226.
- Aim and the fights he takes: B-228, B-229, B-230, B-231.
- The simulator and the maps: B-224, B-227.
- Odd behaviour seen in runs and duels: B-214, B-215, B-192.

## Standing decisions of the owner

- **Fairness**: human physics (125 fps); sight with line of sight and sound only, enemy projectiles too; human reaction,
  flick speed and hand noise; never miss on purpose; no wallhacks.
- **Method**: limit what he can do until the right play appears; do not add rewards for single behaviors without asking;
  the reward is the owner's call. Fading lessons from the pros are fine; what stays must hold without them.
- **Aim level 3 from v0.3.1 on** (the owner, 2026-10-15: "Set it to 3 going forward"): level 1.5 (v0.2 and v0.3, B-228's step one)
  cost the rail most; training, the checks and the servers use 3.
- **v0.3.1: build everything first, then train** (the owner, 2026-10-15: "No time set for starting yet"): one start from v0.3's 18:00 stop point once every part is built and proven alone ([v0.3.1/MANIFEST_v0.3.1.md](v0.3.1/MANIFEST_v0.3.1.md)).
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

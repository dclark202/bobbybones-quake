# BobbyBones: plan

Goal: a Quake Live duel bot that **learns** to play (movement, aim, tactics) and beats people fairly:
human physics, human-like limits, knowledge only from sight and sound. Judge everything by match win
rate against a control group of plain Nightmare bots, and by live tests on a real QL server.

## How the docs fit together (keep them in sync)

| File | Holds | Updated when |
|---|---|---|
| [PLAN.md](PLAN.md) (this) | Approach, where we are, what is being worked on now, owner decisions | The approach, status or "Now" list changes |
| [BACKLOG.md](BACKLOG.md) | Every open, planned and finished work item, with an ID (`B-nn`) and priority | An item is added, started, finished or dropped |
| [RESULTS.md](RESULTS.md) | Dated log of what was tried and what happened, including what did **not** work | Every training run, live test or measurement |
| [PLAYTEST.md](PLAYTEST.md) | The play-test routine and how to run the test suite | The routine or the rooms change |
| [LOGS.md](LOGS.md) | Schema of the recorded data (play-test sessions, training metrics, weapon lab) | A log format changes |

Rules: a result entry names the backlog items it settles (`B-nn`); a backlog item marked done links to the
result that showed it; the "Now" list below only contains backlog IDs. One change = all three touched in the
same commit.

## Approach

1. **Learn in a fast simulator, verify in the real game.** The simulator (`sim/`) runs the same physics
   thousands of times faster than real time. Every learned skill gets a live check before it is trusted.
2. **Learn from people.** Pro duel demos and the owner's play-test sessions teach what good players do
   (imitation). Self-play reinforcement learning then improves on it.
3. **Nightmare is the bar.** Nothing goes to the public server until it beats the Nightmare control group.

## Status (2026-10-03 evening)

| Stage | What | Status |
|---|---|---|
| 1 | Movement simulator (Q3 Pmove + collision, QL settings, jump pads, teleporters) | done, validated |
| 1 | Movement policy: strafe jumping emerged, transfers live (time ratio 1.01) | done |
| 2 | Simulator-built nav graphs, one movement policy on three maps | done (live 67-100% of trips) |
| 3 | Duel simulator: nine weapons measured on a real server, items, armor, reaction delay, mouse-like aim | done; some values unverified (B-14) |
| 3 | Self-play with memory (GRU, league of past versions, GPU) | first full run done (`duel_gru_v2`) |
| 3 | Live port of a duel policy + play-test server with session logs | done (`plugins/duelbot.py`) |
| 3 | A duel policy that beats Nightmare | **not yet: 0-10 in 5 minutes** |
| 4 | Pro-demo imitation | demos parsed (374); inputs and training not built (B-09, B-10) |
| 5 | Reinforcement learning in real QL on top of 3/4 | later |
| 6 | Opponent profiles, player reports | later |

## Now (next training iteration)

In order. Details in [BACKLOG.md](BACKLOG.md).

Running overnight as `duel_gru_v3` (2026-10-03 20:43 to 07:00), fresh network, nine weapons:

1. B-01 aim-only rounds (scripted strafing target, LG-weighted)
2. B-02 tracking fixes (finer small turns, lighter smoothing, no pitch pull while an enemy is in view)
3. B-03 reaction delay 25 ms for now (owner: learn first, pare back later if it feels unfair)
4. B-04 fewer single-weapon drills so weapon choice is learned
5. B-05 small cost for firing with no enemy in view
6. B-06 scripted Nightmare-like opponents in the league
7. B-07 train on the nine-weapon simulator (fresh start)
8. B-08 owner's play-test notes applied: B-28 real switch time, B-15 finite ammo, B-29 item bonus, B-11 movement rounds

Next after the run: B-32 (play `duel_gru_v3` live), B-33/B-34 (test suite with a human baseline).

## Owner decisions

- Maps: Blood Run (ZTN), Aerowalk, Campgrounds only, until told otherwise.
- Human physics only (125 fps); no bot-only frame-rate tricks.
- Human-like reaction and aim limits; never miss on purpose; no wallhacks. Reaction delay is 25 ms while he
  learns (2026-10-03); it goes back up toward human values if he feels unfair.
- Aim should be smooth like a mouse but allow flicks.
- Spawning with the full weapon set is fine while learning to aim; items must be picked up. Ammo as a scarce
  resource comes later ("getting him to not suck first").
- Weapons were validated against the real game before training was trusted; keep doing that for new mechanics.
- Pro demos: Blood Run and Aerowalk first; fetch more only if needed.
- Public server stays off until a model beats Nightmare reliably. Play-testing happens on the private,
  password-protected server (`tools/duel_server.sh`).
- Log as much as possible from human-played rounds.
- Long-term focus (2026-10-04): smooth, efficient movement that keeps speed, and good choices of position and
  weapon, not just good aim (BACKLOG B-42 to B-46).
- No personal data in the repo.

## How to run (short)

```bash
sim\build.bat                                              # Windows: build sim\qsim.dll (MSVC)
python sim/train_duel_rnn.py --run <name> --minutes 600    # self-play with memory (GPU if available)
python sim/test_suite.py --run <name> [--compare card.json]   # standard test rooms, one scorecard
bash tools/duel_server.sh <run> bloodrun <env module>      # private play-test server, port 27970
SPAR=1 bash tools/duel_server.sh <run> bloodrun <env module>   # same policy against a Nightmare bot, no port
python sim/validate_weapons.py                             # simulator weapons vs real-server measurements
python sim/train_move.py / eval_move.py / export_policy.py # movement-only policies (stage 1-2)
```
In the play-test server chat: `!note <text>`, `!drill rl|rg|lg|off`, `!map <name>`.
Maps are extracted from the game's pak into `data/maps/` (never committed). `data/` is git-ignored.

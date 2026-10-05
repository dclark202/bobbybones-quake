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
| [COMMANDS.md](COMMANDS.md) | Every server chat command | A command is added or changed |
| [HOSTING.md](HOSTING.md) | How to rent and start a public server | The hosting setup changes |
| [LOGS.md](LOGS.md) | Schema of the recorded data (play-test sessions, training metrics, weapon lab) | A log format changes |

Rules: a result entry names the backlog items it settles (`B-nn`); a backlog item marked done links to the
result that showed it; the "Now" list below only contains backlog IDs. One change = all three touched in the
same commit.

## Approach

1. **Learn in a fast simulator, verify in the real game.** The simulator (`sim/`) runs the same physics
   thousands of times faster than real time. Every learned skill gets a live check before it is trusted.
2. **Learn from people.** Pro duel demos and the owner's play-test sessions teach what good players do
   (imitation). Self-play reinforcement learning then improves on it.
3. **Measure against people.** A fixed test chamber scores Bobby and human players in the same rooms; play tests
   and (soon) a public server give the human side. Nightmare is a milestone, not the gate.

## Status (2026-10-04 afternoon)

| Stage | What | Status |
|---|---|---|
| 1 | Movement simulator (Q3 Pmove + collision, QL settings, jump pads, teleporters) | done, validated |
| 1 | Movement policy: strafe jumping emerged, transfers live (time ratio 1.01) | done |
| 2 | Simulator-built nav graphs, one movement policy on three maps | done (live 67-100% of trips) |
| 3 | Duel simulator: nine weapons, items and pickups, switch time measured on a real server; sounds, clock, crouch, walk, fall damage; human aim limits | done; unmeasured values listed in B-14, B-37, B-53 |
| 3 | Self-play with memory (GRU, league, scripted opponent styles) | `duel_gru_v3` done (489 min); `duel_gru_v4` done (775 min, self-play only since 650 min) |
| 3 | Play-test server: plays a trained network, session logs, notes, test rooms with a human as the subject | done, including networks trained under the newer rules |
| 3 | Test suite: fixed rooms and scorecards, in the simulator and on the server; test map `bobbylab` | done (aim rooms, nine movement courses, Nightmare fight); first human card recorded |
| 3 | A duel network that beats Nightmare | not yet: `duel_gru_v4` 6-21 in ten minutes; `duel_gru_v3` 2-2 then 5-11 in mixed live minutes |
| 4 | Pro demos | 374 parsed; planned use: routes and positions for the map atlas (B-75, B-73) |
| 5 | Public servers and community play tests | scoped (HOSTING.md); waits for a decent Bobby and the plugin update |
| 6 | Opponent profiles, player reports | later |

## Now

Nothing is training. The night of 2026-10-04 (`duel_gru_v4` to 1361 min) made the courses much faster, left the
duels where they were and cost a lot of aim (RESULTS 2026-10-04 21:12, "Result of the night").

Proposed next run, waiting for the owner: arena self-play in the aim box and the environment box (his idea: no
room to avoid each other), run-and-gun (B-81, built), Blood Run duels with the demo movement loss, courses with
more time on the three unfinished ones, aim rooms back to 15%, items room with a random start. Open decisions:
weight of damage taken, removing the walk key, a network-size test on the demos.

Alongside: B-64 results for players; B-61 / B-69 public server.

## Owner decisions

- Maps: Blood Run (ZTN), Aerowalk, Campgrounds only, until told otherwise.
- Human physics only (125 fps); no bot-only frame-rate tricks.
- Human-like reaction and aim limits; never miss on purpose; no wallhacks. Since 2026-10-04: 200 ms to notice
  an enemy who comes into view, 50 ms tracking delay, flick speed cap, hand noise that grows with turn speed,
  a random delay after slow-weapon reloads. His aim may sit a bit above a decent human's, not far above.
- Aim should be smooth like a mouse but allow flicks.
- Rounds and spawn weapons are not true to the game yet (short rounds, random or full loadouts); accepted for
  now to coax out behavior, flagged as B-56.
- Spawning with the full weapon set is fine while learning to aim; items must be picked up. Ammo as a scarce
  resource comes later ("getting him to not suck first").
- Weapons were validated against the real game before training was trusted; keep doing that for new mechanics.
- Pro demos: Blood Run and Aerowalk first; fetch more only if needed.
- Sharing (2026-10-04): post to the Quake community once Bobby is decent (after the next run), with a video,
  a public server for playing him and one for the test chamber, a how-to-help page and a results page
  (B-61 to B-65). This replaces the earlier rule "no public server until he beats Nightmare".
- Log as much as possible from human-played rounds.
- Long-term focus (2026-10-04): smooth, efficient movement that keeps speed, and good choices of position and
  weapon, not just good aim (BACKLOG B-42 to B-46).
- The test chamber is the yardstick (2026-10-04): the owner, a novice friend and later the public run the same
  rooms; Bobby's aim limits are tuned against those cards. New rooms are tried by the owner before they go into
  training.
- Map knowledge should not live only in the network's weights: an atlas per map with several learned routes per
  item, seeded from pro play (B-72, B-75), then a value map (B-73).
- Pro demos come after self-play has gone as far as it can; first use is routes and positions.
- Third map is Lost World, not Campgrounds (2026-10-04): more played, and it has elements he has not seen.
- The game's bots are a benchmark only (Nightmare, ten minutes per checkpoint); he trains against himself.
- Spawn weapons are only those that lie on the map.
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

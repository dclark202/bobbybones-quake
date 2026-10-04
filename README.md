# bobbybones-quake

**BobbyBones** is a Quake Live duel bot that learns to play from scratch. Nothing about how to aim, move or
fight is hand-coded: a neural network plays millions of duels against itself in a fast simulator of the game,
is checked on a real Quake Live server, and is play-tested by people. The goal is a bot that can beat strong
players fairly and shows learned behavior such as strafe jumping, weapon choice and item control. Down the road, 
BobbyBones can be tuned to help new players learn the game by adapting to the skill level of his opponent. 

## Fairness rules

- **Human physics.** He moves with the same 125 fps physics a human client gets. No bot-only frame-rate tricks.
- **Human senses.** He knows where you are only when you are in his field of view with a clear line of sight,
  or roughly when you are heard nearby. No wallhacks.
- **Mouse-like aim.** He turns his view like a mouse (fine tracking and flicks), with a reaction delay.

## How it works

1. **Simulator** (`sim/`). Quake 3's movement and collision code (ioquake3 `bg_pmove`, `cm_*`) compiled into a
   library with Quake Live's settings, plus a duel layer in Python: nine weapons, items, armor, respawns,
   senses. Movement was validated frame by frame against the real game; weapon damage, timing, knockback,
   switch time and pickup amounts were measured on a real server and reproduced.
2. **Training** (`sim/train_duel_rnn.py`). Self-play reinforcement learning (PPO) with a recurrent network
   (GRU) against a league of its own past versions and scripted opponents of
   several styles. Rounds are mixed: normal duels, aim rounds, single-weapon rounds and movement rounds.
   A movement-only network (`sim/train_move.py`), in which strafe jumping emerged from reward alone, serves
   as a teacher for movement.
3. **Real game** (`minqlx/`, `plugins/`). A Quake Live dedicated server in Docker with
   [minqlx](https://github.com/MinoMino/minqlx). A C hook on the engine's `SV_ClientThink`
   (`minqlx/botctl.c`) lets a plugin drive a bot's keys and view each frame. `plugins/duelbot.py` rebuilds
   the network's inputs from the live game with the simulator's own code and plays the trained network.
4. **Testing.** `sim/test_suite.py` scores any checkpoint in fixed test rooms (aim per weapon and target,
   weapon choice by range, movement, items, a ladder of scripted opponents). The same rooms run on the
   play-test server with a person as the subject, for a human baseline. Every play-test session is logged
   per frame, with the player's notes.

## Where it stands

| | |
|---|---|
| Movement simulator matches the real game; learned movement transfers (time ratio 1.01) | done |
| Strafe jumping learned from reward alone | done |
| Nine weapons, items and pickups measured on a real server and simulated | done |
| Self-play duel training with memory | running; aim is strong, movement, positioning and weapon choice are the current work |
| Playing the trained network on a real server | done (private play-test server) |
| Beating the Nightmare bots | not yet |
| Learning from pro demos (374 parsed), player reports, opponent profiles | later |

Details, including what did not work: [docs/RESULTS.md](docs/RESULTS.md). Plan and open work:
[docs/PLAN.md](docs/PLAN.md), [docs/BACKLOG.md](docs/BACKLOG.md). Log formats: [docs/LOGS.md](docs/LOGS.md).

## Running it

You need a Quake Live install for the map files (extracted to `data/maps/`, never committed), Python with
PyTorch, a C compiler for the simulator, and Docker for the game server.

```bash
sim/build.bat                                             # Windows: build the simulator library
python sim/train_duel_rnn.py --run my_run --minutes 600    # self-play training (GPU if available)
python sim/test_suite.py --run my_run                      # scorecard in the test rooms
docker build -t qlbot .                                    # game server image
bash tools/duel_server.sh my_run bloodrun                  # private play-test server on UDP 27970
SPAR=1 bash tools/duel_server.sh my_run bloodrun           # the same network against a Nightmare bot
```

On the play-test server (chat): `!note <text>` saves feedback with the game state, `!drill <weapon>` gives both
players one weapon, `!room suite` runs the test rooms on you, `!map <bloodrun|aerowalk|campgrounds>`.

## Repo layout

```
sim/                 simulator (vendored ioquake3 physics in sim/q3), environments, trainers, test suite
plugins/             minqlx plugins: duelbot (plays the network, test rooms, logs), weapon and item labs
minqlx/              vendored minqlx + the input hook (see minqlx/UPSTREAM.md)
tools/               server script, test-map builder, demo downloader and parser
maps/bobbylab/       the test map (aim box, environment box, trick-jump stations)
legacy/              the first approach (a layer on the Nightmare bot); not used
docs/                PLAN, BACKLOG, RESULTS, LOGS
Dockerfile           Quake Live dedicated server image
data/                (git-ignored) maps, training runs, recordings, play-test sessions
```

## License

GPL-3.0 (see `LICENSE`). The bundled minqlx and ioquake3 code are GPL, so the project follows it.

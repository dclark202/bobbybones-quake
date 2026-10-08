# bobbybones-quake

## Play against him in Quake Live
Join server `doppz's bot arena | duel & FFA | chicago` (or `connect 64.177.125.38:27970` in terminal).

**BobbyBones** is a Quake Live bot that learns to play from scratch. Nothing about how to aim, move or
fight is hand-coded: a neural network plays millions of fights against itself in a fast simulator of the game,
is checked on a real Quake Live server, and is play-tested by people. The long-term goal is a bot that can beat
strong players fairly and shows learned behavior such as strafe jumping, weapon choice and item control. Down the
road, BobbyBones can be tuned to help new players learn the game by adapting to the skill level of his opponent.

## The current goal

The first target is deliberately small: **one arena, played like a person would play it.**

1. Human-like play: no key spam, steady aim, looking where it matters.
2. One small custom arena, the yard (two levels, a tunnel, a jump pad, a teleporter, mega health, red armor and
   three weapons to fight over).
3. He shows that he knows the map and moves on it efficiently: where the items are, when they come back, how to
   get there.
4. One against one, or all against all with up to four players, whichever brings out that behavior better.
5. He beats the game's Nightmare bot there (reached in the plain fighting room on 2026-10-05).

The popular duel maps (Blood Run, Aerowalk, Lost World) come back once he meets these consistently.

## Fairness rules

- **Human physics.** He moves with the same 125 fps physics a human client gets. No bot-only frame-rate tricks.
- **Human senses.** He knows where you are only when you are in his field of view with a clear line of sight,
  or roughly when you are heard nearby. No wallhacks.
- **Human sight.** Walls, floors and items are only seen inside his field of view. He gets no readout of your
  health: only the pain sounds a player hears, and the damage he knows he dealt.
- **Mouse-like aim.** He turns his view like a mouse (fine tracking and flicks), with a reaction delay, a cap on
  flick speed, hand shake, and a later read on changes in your movement than on your position.
- **Human hands.** The left hand is five fingers on the keys: each finger does one thing at a time and needs
  time between presses, and the hand as a whole tires (short bursts, then about four key changes a second). The
  right hand fires and zooms at no more than five clicks a second.
- **No bot habits.** He trains only against himself. The game's bots are a yardstick, never a teacher.

## How it works

1. **Simulator** (`sim/`). Quake 3's movement and collision code (ioquake3 `bg_pmove`, `cm_*`) compiled into a
   library with Quake Live's settings, plus a duel layer in Python: nine weapons, items, armor, respawns,
   senses. Movement was validated frame by frame against the real game; weapon damage, timing, knockback,
   switch time and pickup amounts were measured on a real server and reproduced.
2. **Training** (`sim/train_duel_rnn.py`). Self-play reinforcement learning (PPO) with a recurrent network
   (GRU) against a league of its own past versions. The reward is plain: a frag, a death, damage dealt against
   damage taken. The approach since 2026-10-05: put him in a small arena and tighten the human limits until the
   right kind of play appears, instead of rewarding each behavior. The simulator also runs groups of up to six
   players, all against all (`sim/duel_env_ffa.py`).
3. **Real game** (`minqlx/`, `plugins/`). A Quake Live dedicated server in Docker with
   [minqlx](https://github.com/MinoMino/minqlx). A C hook on the engine's `SV_ClientThink`
   (`minqlx/botctl.c`) lets a plugin drive a bot's keys and view each frame. `plugins/duelbot.py` rebuilds
   the network's inputs from the live game with the simulator's own code and plays the trained network.
4. **Testing.** `sim/test_suite.py` scores any checkpoint in fixed test rooms (aim per weapon and target,
   weapon choice by range, movement, items, a ladder of scripted opponents). The same rooms run on the
   play-test server with a person as the subject, for a human baseline. Every play-test session is logged
   per frame, with the player's notes. `sim/render_course.py` renders first-person videos of his fights
   straight from the simulator, with the keys he pressed, for judging how the play looks.

## Where it stands

| | |
|---|---|
| Movement simulator matches the real game; learned movement transfers (time ratio 1.01) | done |
| Strafe jumping learned from reward alone | done |
| Nine weapons, items and pickups measured on a real server and simulated | done |
| Self-play training with memory | running: arena fights under finger, sight and aim limits; the play now looks like Quake |
| Playing the trained network on a real server | done (private play-test server) |
| Test chamber: the same rooms for the bot and for people, on a custom map | done; first human scorecard recorded |
| Beating the Nightmare bot in the fighting room | done (23-11 to 32-10 in five minutes, 2026-10-05) |
| Human-like hands and eyes (five fingers, field of view, click limits) | done; he still asks for more key changes than his fingers make |
| Knowing a map: items, their timers, efficient routes (the yard) | in progress: an explicit intention ("go for the mega"), a map reader trained on 62 maps, item sounds; he takes weapons, not yet the mega and the red armor |
| Three or four players, all against all | training in groups of 2, 3 and 4 since 2026-10-06; on the public server with up to four Bobbys |
| Beating Nightmare on the yard, ten minutes | 18-30 at the end of v8 (2026-10-06), the first run to trade frags with it |
| The duel maps (Blood Run, Aerowalk, Lost World, Furious Heights, Campgrounds, Sinister) | in training alongside the yard since 2026-10-06 evening; a night on Blood Run with pro demos (3,700 downloaded) made movement faster but not duels better |
| Public server | up: "doppz's bot arena | duel & FFA | chicago", free-for-all with three Bobbys, `!map` for the eight trained maps, ready up (F3) for a real game |
| Player reports, opponent profiles | later |

Details, including what did not work: [docs/RESULTS.md](docs/RESULTS.md). Plan and open work:
[docs/PLAN.md](docs/PLAN.md), [docs/BACKLOG.md](docs/BACKLOG.md). Log formats: [docs/LOGS.md](docs/LOGS.md).
Play him and help set his limits: [docs/COMMUNITY.md](docs/COMMUNITY.md). What the network is given: [docs/INPUTS.csv](docs/INPUTS.csv). Server commands: [docs/COMMANDS.md](docs/COMMANDS.md). Play-test routine: [docs/PLAYTEST.md](docs/PLAYTEST.md).

## Running it

You need a Quake Live install for the map files (extracted to `data/maps/`, never committed), Python with
PyTorch, a C compiler for the simulator, and Docker for the game server.

```bash
sim/build.bat                                             # Windows: build the simulator library
python sim/train_duel_rnn.py --run my_run --minutes 600    # self-play training (GPU if available)
python sim/test_suite.py --run my_run                      # scorecard in the test rooms
docker build -t qlbot .                                    # game server image
bash tools/duel_server.sh my_run                           # private play-test server on UDP 27970 (map arena1, 1v1)
FFA=3 bash tools/duel_server.sh my_run arena1 duel_env_ffa  # free-for-all with three Bobbys (up to four; six seats)
SPAR=1 bash tools/duel_server.sh my_run                    # the same network against a Nightmare bot
```

On the play-test server, chat commands switch the mode and the map (`!mode ffa|duel`, `!map <name>`, `!bots <0-4>`),
save feedback (`!note`), run the test chamber on you (`!map testlab`, `!room suite`) and let you watch him play a
Nightmare bot (`!spar`). In free-for-all a real game starts when more than half of the people ready up (F3).
Full list: [docs/COMMANDS.md](docs/COMMANDS.md). Hosting a public one: [docs/HOSTING.md](docs/HOSTING.md).

## Repo layout

```
sim/                 simulator (vendored ioquake3 physics in sim/q3), environments, trainers, test suite
plugins/             minqlx plugins: duelbot (plays the network, test rooms, logs), weapon and item labs
minqlx/              vendored minqlx + the input hook (see minqlx/UPSTREAM.md)
tools/               server script, test-map builder, demo downloader and parser
maps/testlab/       the test map (aim box, environment box, movement courses, the yard without items)
maps/arena1/      the yard with items: the arena of the current goal
maps/atlas/          per duel map: areas, items and routes seeded from pro demos
legacy/              the first approach (a layer on the Nightmare bot); not used
docs/                PLAN, BACKLOG, RESULTS, LOGS
Dockerfile           Quake Live dedicated server image
data/                (git-ignored) maps, training runs, recordings, play-test sessions
```

## License

GPL-3.0 (see `LICENSE`). The bundled minqlx and ioquake3 code are GPL, so the project follows it.

## Play against him in Quake Live
Join server `doppz's bot arena | duel & FFA | chicago` (or `connect 64.177.125.38:27970` in terminal).

**BobbyBones** is a Quake Live bot that learns to play from scratch. Nothing about how to aim, move or
fight is hand-coded: a neural network plays millions of fights against itself in a fast simulator of the game,
is checked on a real Quake Live server, and is play-tested by people. The long-term goal is a bot that can beat
strong players fairly and shows learned behavior such as strafe jumping, weapon choice and item control. Down the
road, BobbyBones can be tuned to help new players learn the game by adapting to the skill level of his opponent.

## The current goal

**Play the real duel maps the way a good player does.** Blood Run, Aerowalk and Lost World, one against one and
all against all with up to four to six players:

1. Human-like play: no key spam, steady aim, looking where it matters.
2. He uses the weapons the way good players do: rockets close, lightning in the middle, the rail at range.
3. He controls the items: a weapon first after a spawn, then the armors and the mega, on time and against an
   opponent who wants them too.
4. He moves like a player: knows the ways, and jumps to keep his speed.
5. He beats the game's Nightmare bot on these maps.

The first target (2026-10-05) was one small custom arena, the yard: two levels, a tunnel, a jump pad, a
teleporter, a mega health, a red armor and three weapons. Since 2026-10-08 he trains on the three duel maps and the
yard is the map he is checked on without having trained there.

## Fairness rules

- **Human physics.** He moves with the same 125 fps physics a human client gets. No bot-only frame-rate tricks.
- **Human senses.** He knows where you are only when you are in his field of view with a clear line of sight,
  or roughly when you are heard nearby. No wallhacks.
- **Human sight.** Walls, floors and items are only seen inside his field of view. He gets no readout of your
  health: only the pain sounds a player hears, and the damage he knows he dealt.
- **Mouse-like aim.** He turns his view like a mouse (fine tracking and flicks), with a reaction delay, a cap on
  flick speed, hand shake, a flinch when hit, and a later read on changes in your movement than on your position.
  The limits are one setting, calibrated on a real player's reflex tests: "a good aimer, not a bot".
- **Human knowledge of the map.** He knows an item is gone or back only if he took it, saw its place or heard it
  (from the next network on; until then he is told).
- **Human hands.** The left hand is five fingers on the keys: each finger does one thing at a time and needs
  time between presses, and the hand as a whole tires (short bursts, then four key changes a second, five from the
  next network on: people in our logs do about seven in their busy stretches). The right hand fires and zooms at
  no more than three clicks a second.
- **No bot habits.** He trains only against himself and our own scripted runner. The game's bots are a yardstick,
  never a teacher.

## How it works

1. **Simulator** (`sim/`). Quake 3's movement and collision code (ioquake3 `bg_pmove`, `cm_*`) compiled into a
   library with Quake Live's settings, plus a duel layer in Python: nine weapons, items, armor, respawns,
   senses. Movement was validated frame by frame against the real game; weapon damage, timing, knockback,
   switch time and pickup amounts were measured on a real server and reproduced.
2. **Training** (`sim/train_duel_rnn.py`). Self-play reinforcement learning (PPO) with a recurrent network
   (GRU) against a league of its own past versions, in groups of two to four. The reward is plain at its core: a
   frag, a death, damage dealt against damage taken, the items picked up. Self-play alone did not find the habits
   of the game (fetching a weapon, using rockets, taking the armor), so since 2026-10-07 he is also **shown** them
   for the first hours of a run and then left alone: a walking teacher along the ways of the map, a weapon for the
   distance and an order for the items taken from 3,266 pro duels (505 hours), a playing style per life (rockets,
   rail, lightning or general). The teachers only ever press keys; where he looks and when he fires stay his own.
   The simulator also runs groups of up to six players, all against all (`sim/duel_env_ffa.py`).
3. **Real game** (`minqlx/`, `plugins/`). A Quake Live dedicated server in Docker with
   [minqlx](https://github.com/MinoMino/minqlx). A C hook on the engine's `SV_ClientThink`
   (`minqlx/botctl.c`) lets a plugin drive a bot's keys and view each frame. `plugins/duelbot.py` rebuilds
   the network's inputs from the live game with the simulator's own code and plays the trained network.
4. **Checking.** Ten-minute duels against the game's Nightmare bot on a real server; a hundred ten-minute duels a
   map in the simulator against a stand-in for it, with error bars (`tools/duel_eval.py`); his inputs on a real
   server set beside the simulator's (`tools/input_check.py`); whether the walking teacher can walk its own ways
   (`tools/teacher_check.py`). `sim/test_suite.py` scores any checkpoint in fixed test rooms (aim per weapon and target,
   weapon choice by range, movement, items, a ladder of scripted opponents). The same rooms run on the
   play-test server with a person as the subject, for a human baseline. Every play-test session is logged
   per frame, with the player's notes. `sim/render_course.py` renders first-person videos of his fights
   straight from the simulator, with the keys he pressed, for judging how the play looks.

## Where it stands (2026-10-08)

| | |
|---|---|
| Movement simulator matches the real game; learned movement transfers (time ratio 1.01) | done |
| Nine weapons, items and pickups measured on a real server and simulated | done (on 2026-10-08: the simulator had ammo packs the real game does not spawn; removed from the next network on) |
| Self-play training with memory, groups of two to four | running since 2026-10-06; the latest network is v12 (79 hours of training in all) |
| Human-like hands, eyes and aim (five fingers, field of view, click limits, one aim setting) | done; his tracking is about a real good player's, his first rail shot and his rockets below it |
| Weapons | better since v12: time without a big weapon 74% -> 54%, the machine gun's share of his frags 73% -> 45%, rockets, rail and lightning each 15 to 23% |
| Item control | **the open problem.** Alone he fetches what he wants in 84 to 100% of tries; with an opponent on the map he takes about half as many red armors and megas as our scripted runner and a third to a half of what Nightmare takes |
| Jumping | lost: he walks (jumps in 1 to 2% of frames; pros are in the air for a third of their moving time). The teacher that showed him the ways had been labelling "no jump"; corrected for the next network |
| Against the Nightmare bot, ten minutes, the game's own spawn | the yard 14-27, Blood Run 7-18, Aerowalk 6-13 (v12, 2026-10-08): he deals more damage than Nightmare on all three and loses on armor and health |
| A review of the whole pipeline (2026-10-08) | the learning loop is right; found and fixed around it: the plugin for one-on-one games had never been given the map's walking graph, the Bobbys on the public server moved on each other's keys, the direction to the mega and the red armor reached the network at a twentieth of its size, and the pay for walking to an item could be collected by falling short of it |
| The duel maps (Blood Run, Aerowalk, Lost World) | in training since 2026-10-06; the only training maps from the next network on |
| Three or four players, all against all | in training since 2026-10-06; on the public server with three Bobbys |
| Public server | up: "doppz's bot arena | duel & FFA | chicago", free-for-all with three Bobbys (v12), `!map` for the trained maps, ready up (F3) for a real game |
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

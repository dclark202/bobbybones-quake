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
- **Human sight.** Walls and items are only seen inside his field of view; the ground at his own feet he knows without
  looking, as a player who knows the map does. He gets no readout of your
  health: only the pain sounds a player hears, and the damage he knows he dealt.
- **Mouse-like aim.** He turns his view like a mouse (fine tracking and flicks), with a reaction delay, a cap on
  flick speed, hand shake, a flinch when hit, and a later read on changes in your movement than on your position.
  The limits are one setting, calibrated on a real player's reflex tests: "a good aimer, not a bot".
- **Human knowledge of the map.** He knows an item is gone or back only if he took it, saw its place or heard it
  (from the next network on; until then he is told).
- **Human hands.** The left hand is five fingers on the keys: each finger does one thing at a time and needs
  time between presses, and the hand as a whole tires (short bursts, then four key actions a second; eight from the
  next network on, measured on a player's own hand: 6.6 to 7.1 a second over a whole game). The right hand fires and zooms at
  no more than three clicks a second.
- **No bot habits.** He trains only against himself and our own scripted runner. The game's bots are a yardstick,
  never a teacher.

## How it works

1. **Simulator** (`sim/`). Quake 3's movement and collision code (ioquake3 `bg_pmove`, `cm_*`) compiled into a
   library with Quake Live's settings, plus a duel layer in Python: nine weapons, items, dropped weapons, armor, respawns,
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

## What he can do

- **Plays real Quake Live.** He joins a server like any player: duels, or free-for-all with several of him and you,
  on Blood Run, Aerowalk, Lost World and a custom arena.
- **Aims like a strong player, under a player's limits.** He tracks a dodging target about as well as a good human
  does, with a reaction time, a flick limit, hand shake and a flinch when hit. Nothing about aiming was coded.
- **Uses the arsenal.** He goes for a weapon after a spawn and fights with rockets, lightning and the rail; each
  life he has a preferred weapon or none, as people do.
- **Knows the maps.** Alone he finds his way to nearly every weapon, armor and mega on them, through jump pads and
  teleporters.
- **Plays the item game.** He keeps health and armor stacked, takes the mega and the armors on time, picks up the
  weapons the dead leave behind, and wins his trained maps against a scripted opponent with the hardest bot's aim.
- **Out-damages the game's hardest bot.** In ten-minute duels against Nightmare he deals more damage than he takes on
  every map tested.
- **Moves with a hand, not a script.** Five fingers on the keys, a few key presses a second, three clicks a second.

## In progress

- **Strafe jumping on the duel maps.** It emerged by itself in the movement simulator and carried over to the real
  game; in full games he still walks. The next training shows it to him in item runs and pays for speed.
- **Rockets**: leading a moving target, and firing where the enemy is about to be. He fires far fewer than a good
  player and leans on the lightning gun and the rail.
- **More of the game's duel maps**: Campgrounds, Sinister and Furious Heights next to Blood Run, Aerowalk and Lost
  World, with two more held back to test him on maps he has never seen.
- **The simulator set right against the game's maps**: lava that hurts, shots through bars and grates, items where the
  game puts them.

## Planned

- More maps, and free-for-all with up to six players.
- An opponent that adapts to your level, to help new players learn the game.
- Player reports and profiles of how opponents play.

The measurements behind all of this, including what did not work: [docs/RESULTS.md](docs/RESULTS.md). Plan and open work:
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

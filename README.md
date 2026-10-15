## Play against him in Quake Live
Join server `doppz's bot arena | duel & FFA | chicago` (or `connect 64.177.125.38:27970` in terminal). 

Join the discord server https://discord.gg/dH2mfzbMa

The server runs free-for-all on the game's duel maps with each map's duel items and no powerups; six play at a time,
Bobbys included, the rest watch. Chat commands: `!bots <0-4>` sets how many Bobbys play, `!map <name>` changes the map
(`!maps` lists them: Blood Run, Aerowalk, Lost World, Sinister, Furious Heights, Battleforged, Campgrounds, Hektik,
Toxicity, Cure), `!mode duel` makes it one against one, F3 readies you up for a timed ten-minute game, `!note <text>`
leaves a comment for the log. A leaderboard local to the server counts every frag between a person and Bobby, warmup
included: `!bobby` shows his rating and rank, `!top` the board, `!elo` yours. All commands:
[docs/guides/COMMANDS.md](docs/guides/COMMANDS.md).

## What it is

BobbyBones is a Quake Live duel bot trained from scratch by reinforcement learning. A neural network plays millions of
games against copies of itself in a fast simulator built on Quake 3's own movement and collision code, then plays people
on a real Quake Live server through a server plugin. Nothing about aiming, moving or fighting is scripted.

## Architecture

- **Simulator** (`sim/`): ioquake3's player movement and collision compiled into one library (`qsim.dll` / `libqsim.so`)
  with Quake Live's settings, loading the game's own maps. A numpy game layer (`sim/duel_env.py`) adds the weapons, items,
  sounds, clock and score as measured on a real server. It runs thousands of players at once on one PC.
- **Network**: about 1.75 million weights. 791 inputs every 25 ms (what he sees, hears and remembers; [docs/INPUTS.csv](docs/INPUTS.csv)),
  an encoder and attention over groups of inputs (the enemy, the items, the map's places), a GRU memory of 512, and
  outputs for keys, mouse, fire, weapon and the item or place he is heading for.
- **Training** (`sim/train_duel_rnn.py`): PPO on whole ten-minute duels on ten of the game's duel maps, against a league
  of his own past snapshots and the previous best network.
- **Game server**: a Docker image with the Quake Live dedicated server and [minqlx](https://github.com/MinoMino/minqlx).
  A small C patch (`minqlx/botctl.c`) lets a plugin set a bot's keys and view each frame; `plugins/duelbot.py` and
  `plugins/ffabot.py` rebuild the network's inputs from the live game and run it.

```
sim/       simulator, game layer, trainer, export
plugins/   minqlx plugins (the bots, logging, server rules)
minqlx/    vendored minqlx with the input hook
tools/     server scripts, evaluation, map and demo tools
docs/      plan, backlog, results log, run reports
```

## Fairness

He plays under a person's limits:

- **Physics**: the same 125 fps movement as a human client.
- **Senses**: he knows where the enemy is only when in his field of view with a clear line of sight, or roughly from
  sound. No wallhack, no health readout, item timers only from what he saw or heard.
- **Reaction and aim**: he sees the enemy 100 ms late; the view turns like a mouse, with a capped flick speed, inertia and
  hand noise.
- **Hands**: a limited number of key presses and clicks a second, as measured on a player.

The game's own bots are used only as a yardstick, never as a teacher.

## Run it

You need a Quake Live install (for the map files), Python with PyTorch, a C compiler and Docker.

```bash
sim/build.bat                                              # build the simulator (Windows)
python sim/train_duel_rnn.py --run my_run --minutes 600    # train
python tools/duel_eval.py --run my_run --opp nightmare --map bloodrun --games 32   # evaluate in the simulator
docker build -t qlbot .                                    # game server image
bash tools/duel_server.sh my_run bloodrun                  # private server on UDP 27970
```

Chat commands: [docs/guides/COMMANDS.md](docs/guides/COMMANDS.md). Hosting: [docs/guides/HOSTING.md](docs/guides/HOSTING.md).
Every run and result, including what did not work: [docs/RESULTS.md](docs/RESULTS.md).

## License

GPL-3.0 (see `LICENSE`), as the bundled minqlx and ioquake3 code require.

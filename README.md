## What it is

BobbyBones is a Quake Live duel bot trained from scratch by reinforcement learning. A neural network plays millions of
games against copies of itself in a fast simulator built on Quake 3's own movement and collision code, then plays people
on a real Quake Live server through a server plugin. All learning is from playing himself, human game demos are used for calibration.

## Play against

Join server `Duel BobbyBones the self taught Quake bot | US Chicago` in Quake Live (or `connect 64.177.125.38:27970` in the game's console)


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

He plays under a human's limits:
- **Physics**: the same 125 fps movement as a human client.
- **Senses**: he knows where the enemy is only when in his field of view with a clear line of sight, or roughly from
  sound. No wallhack, no health readout, item timers only from what he saw or heard.
- **Reaction, aim, and inputs**: human-like reflexes, aim limitation, and keypresses per second 

## Run it

You need a Quake Live install (for the map files), Python with PyTorch, a C compiler and Docker.

```bash
sim/build.bat                                              # build the simulator (Windows)
python sim/train_duel_rnn.py --run my_run --minutes 600    # train
python tools/duel_eval.py --run my_run --opp nightmare --map bloodrun --games 32   # evaluate in the simulator
docker build -t qlbot .                                    # game server image
bash tools/duel_server.sh my_run bloodrun                  # private server on UDP 27970
```

## License

GPL-3.0 (see `LICENSE`), as the bundled minqlx and ioquake3 code require.

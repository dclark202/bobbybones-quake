# What it is

BobbyBones is a Quake Live duel bot trained from scratch by reinforcement learning. A neural network plays millions of
games against copies of itself in a fast simulator built on Quake 3's own movement and collision code, then plays people
on a real Quake Live server through a server plugin. All learning is from playing himself, human game demos are used for calibration.

# Play against him

## Online

Quake Live servers:
- `Duel BobbyBones the self taught Quake bot | US Chicago` (`193.239.237.127:27970`)
- `Duel BobbyBones the self taught Quake bot | EU Frankfurt` (`45.140.42.214:27970`)

We keep a local elo rating to track the bot's skill. See the [leaderboard](https://dclark202.github.io/bobbybones-leaderboard/) 

## Via a local install

The networks that have played on the public server are released as open weights, one
[GitHub Release](https://github.com/dclark202/bobbybones-quake/releases) per model, tagged at the code the server ran it with
(each network needs its own version of the simulator and plugins).

You need Docker (on Windows, Docker Desktop and Git Bash) and Quake Live from Steam to join. The image build downloads the
Quake Live dedicated server with steamcmd (the image is about 3.4 GB). From a release, download the model's
`bobbybones-<version>-weights.zip` and `bobbybones-duel-maps.zip` and unpack both at the top of the repository:

```bash
git clone https://github.com/dclark202/bobbybones-quake && cd bobbybones-quake
git checkout v0.3.10                               # the model's tag
unzip ~/Downloads/bobbybones-v0.3.10-weights.zip   # data/duellive/policy*.npz, legs.npz
unzip ~/Downloads/bobbybones-duel-maps.zip         # data/maps/nav_<map>_sim.json, cells_<map>.npy (the ten duel maps)
docker build -t qlbot .
bash tools/duel_server.sh - bloodrun               # "-": the network already in data/duellive; the map is any of the ten
```

The weights and the map files are under CC-BY-4.0 ([WEIGHTS_LICENSE.md](WEIGHTS_LICENSE.md)): use, change and retrain them
as you like, with credit to "BobbyBones by Duncan Clark (github.com/dclark202/bobbybones-quake)".

# Architecture

- **Simulator** (`sim/`): ioquake3's player movement and collision compiled into one library (`qsim.dll` / `libqsim.so`)
  with Quake Live's settings, loading the game's own maps. A numpy game layer (`sim/duel_env.py`) adds the weapons, items,
  sounds, clock and score as measured on a real server. It runs thousands of players at once on one PC.
- **Network**: about 1.75 million weights. 791 inputs every 25 ms (what he sees, hears and remembers; [docs/INPUTS.csv](docs/INPUTS.csv)),
  an encoder and attention over groups of inputs (the enemy, the items, the map's places), a GRU memory of 512, and
  outputs for keys, mouse, fire, weapon and the item or place he is heading for.
- **Training** (`sim/train_duel_rnn.py`): PPO on whole ten-minute duels on ten of the game's duel maps, against a league
  of his own past snapshots and the previous best network.
- **Game server**: a Docker image with the Quake Live dedicated server and [minqlx](https://github.com/MinoMino/minqlx).
  A small C patch (`minqlx/botctl.c`) lets a plugin set a bot's keys and view each frame; `plugins/duelbot.py` rebuilds
  the network's inputs from the live game and runs it. The server plays 1v1 only, on the ten duel maps.

```
sim/       simulator, game layer, trainer, export
plugins/   minqlx plugins (the bots, logging, server rules)
minqlx/    vendored minqlx with the input hook
tools/     server scripts, evaluation, map and demo tools
docs/      plan, backlog, results log, run reports
```

# Fairness

He plays under a human's limits:
- **Physics**: the same 125 fps movement as a human client.
- **Senses**: he knows where the enemy is only when in his field of view with a clear line of sight, or roughly from
  sound. No wallhack, no health readout, item timers only from what he saw or heard.
- **Reaction, aim, and inputs**: human-like reflexes, aim limitation, and keypresses per second 


# License

GPL-3.0 (see `LICENSE`), as the bundled minqlx and ioquake3 code require. The released networks and map files: CC-BY-4.0
(see `WEIGHTS_LICENSE.md`).

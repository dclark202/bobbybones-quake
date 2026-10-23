## What it is

BobbyBones is a Quake Live duel bot trained from scratch by reinforcement learning. A neural network plays millions of
games against copies of itself in a fast simulator built on Quake 3's own movement and collision code, then plays people
on a real Quake Live server through a server plugin. All learning is from playing himself, human game demos are used for calibration.

## Play against

Join server `Duel BobbyBones the self taught Quake bot | US Chicago` in Quake Live (or `connect 64.177.125.38:27970` in the game's console)

## Play him locally

The networks that have played on the public server are released as open weights, one
[GitHub Release](https://github.com/dclark202/bobbybones-quake/releases) per model, tagged at the code the server ran it with
(each network needs its own version of the simulator and plugins).

| Version | On the public server | What it added | Aim levels | Tag |
|---|---|---|---|---|
| v0.3.6 | 2026-10-19 to 2026-10-22 | Rockets: inputs for a rocket's lead, a pre-fire token, the point where an unseen enemy would come into view | one (100 ms reaction, 200 ms to find a target) | `v0.3.6` |
| v0.3.10 | from 2026-10-22 | Pre-aiming at a fresh sighting and watching the opening before it; his own lightning gun masks his hearing as in the game | `!aim 1` to `5`, `max` | `v0.3.10` |

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

The server is not listed in the server browser and loads only the game's own duel maps. Join with `connect 127.0.0.1:27970` in the game's console (from another machine: its address). At
the first start the map tables are worked out before the server comes up (a minute or two). `PORT=<udp port>` picks another
port, `PASSWORD=<word>` sets a password, `bash tools/duel_server.sh stop` stops it.

In the game: `!map <name>` (`!maps` lists them), `!note <text>`, and with v0.3.10 `!aim 1|2|3|4|5|max` for the next game
(4 is the default and comes back at every map change):

| `!aim` | 1 | 2 | 3 | 4 | 5 | max |
|---|---|---|---|---|---|---|
| reaction / to find a target, ms | 195 / 313 | 156 / 250 | 125 / 200 | 100 / 160 | 80 / 128 | 25 / 25, no human aim limits |

The weights and the map files are under CC-BY-4.0 ([WEIGHTS_LICENSE.md](WEIGHTS_LICENSE.md)): use, change and retrain them
as you like, with credit to "BobbyBones by Duncan Clark (github.com/dclark202/bobbybones-quake)".

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

GPL-3.0 (see `LICENSE`), as the bundled minqlx and ioquake3 code require. The released networks and map files: CC-BY-4.0
(see `WEIGHTS_LICENSE.md`).

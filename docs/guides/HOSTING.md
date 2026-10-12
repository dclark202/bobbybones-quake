# Hosting a public BobbyBones server

One rented machine near Chicago running **one** Quake Live server that does both jobs: people duel Bobby on the
stock maps, and run the test chamber on the `testlab` map (`!map testlab`, `!room suite`). More machines and a
second server per machine can be added later the same way.

## What to rent

| | |
|---|---|
| Provider and region | Vultr, Chicago. (Linode / Akamai also has Chicago at similar prices. Hetzner is cheaper but only has Virginia and Oregon in the US.) |
| Plan | Cloud Compute, 2 vCPU / 4 GB / 80 GB: about $20 a month (the "High Frequency" 2 vCPU / 4 GB is about $24) |
| Cheaper option | 1 vCPU / 2 GB, about $10-12 a month. Probably enough for one server; **not tested**. The image build needs about 8 GB of disk and is slow on 1 vCPU |
| System | Ubuntu 24.04 LTS, with your SSH key |
| Needs | One CPU core with good single-thread speed, about 1 GB of memory, no GPU. Bobby's network runs on the CPU, 40 decisions a second |

Prices are from third-party listings in 2026; check the provider's own page before buying.

## Server quality

Quake Live locks the tick rate at 40 per second (`sv_fps` cannot be raised; measured: frames 25.0 ms apart).
A server that feels better than others has to get there through hardware and network:
- a plan with a **dedicated CPU core** (Vultr "CPU Optimized", 2 cores / 4 GB, about $40 a month), so no other
  customer can take time from the game;
- one game server per core and nothing else on the machine;
- a provider with good routes into Chicago.
Rent by the hour for a first week, play on it, and compare before committing.

## What you do (accounts and payment)

1. Create the provider account and add a payment method.
2. Deploy the machine (region Chicago, plan above, Ubuntu 24.04, your SSH public key).
3. In the provider's firewall (or `ufw` on the machine) allow **UDP 27970** and TCP 22 (SSH) only.
4. Note the machine's IP address.

## Set up the machine (once)

```bash
ssh root@<ip>
apt-get update && apt-get install -y docker.io git
git clone https://github.com/dclark202/bobbybones-quake.git
cd bobbybones-quake
docker build -t qlbot .          # downloads the Quake Live dedicated server (about 1 GB); 10-20 minutes
mkdir -p data/duellive data/maps
```

Two things are not in the repository and are copied from the training PC (run these on the PC, in the repo folder):

```bash
python sim/export_duel.py --run duel_gru_v3 --env duel_env_v3 --out data/duellive/policy.npz   # the Bobby to serve
scp data/duellive/policy.npz root@<ip>:bobbybones-quake/data/duellive/
scp data/maps/nav_*_sim.json root@<ip>:bobbybones-quake/data/maps/     # only for the movement rooms on the stock maps
```

## Start the server

On the machine:

```bash
cd bobbybones-quake
PUBLIC=1 RESTART=1 FFA=2 HOSTNAME_QL="doppz's bot arena | duel & FFA | chicago" bash tools/duel_server.sh - bloodrun
```

- `-` means "use the `policy.npz` already in `data/duellive`" (no PyTorch needed on the machine).
- `RESTART=1` brings the server back after a crash or a reboot.
- No password by default. `PASSWORD=<word>` in front sets one (useful for a private first test).
- Players connect with `connect <ip>:27970` in the game console; the server also appears in the server browser.
- Check it: `docker ps`, `tail data/duellive/duelbot.log`.

One server holds one duel at a time; other players spectate and queue (the game's own duel queue).

## Free-for-all instead of 1v1

The public server runs free-for-all by default: since 2026-10-09 with two Bobbys, on Blood Run from 2026-10-11 (owner, 2026-10-10: there are things about Aerowalk he does not understand yet; it was Aerowalk; from 2026-10-06 it was three on `arena1`). `CODE=1 bash tools/push_bobby.sh <run>` restarts it that way; `FFA=<n>` and a third argument change the number and the map, and it copies the walking maps and map tables of every map the server offers (they are not in git). Players change the map with `!map <name>` (the ten duel maps he trained on or is checked on, in free-for-all with the items of a duel; `!map testlab` is 1v1) and the mode with `!mode ffa|duel`, see `docs/COMMANDS.md`. The owner kicks and bans from the game chat (`!kick`, `!ban`; `plugins/banlist.py`, the bans in `data/duellive/bans.txt` on the server). A leaderboard local to the server counts every frag between a person and Bobby (`!bobby`, `!top`, `!elo`; `plugins/ladder.py`, its files `ratings.json` and `frags.jsonl` beside the bans).

```bash
FFA=3 bash tools/duel_server.sh duel_gru_v13 aerowalk duel_env_ffa_v13     # three Bobbys, three seats for people
```
`FFA=<n>` starts in free-for-all; `!mode ffa|duel` and `!map` switch a running server (`plugins/botmode.py`, always
loaded). `FFA=<n>` loads `plugins/ffabot.py` instead of the duel plugin and the `ffa` factory: one six-seat group simulator
(the one he trained in), every client gets a seat on joining, all Bobbys think in one network pass per frame. `!bots <n>`
changes the number of Bobbys while the server runs. Free-for-all rules (owner, 2026-10-06): eight client slots as in 1v1 but six seats in the game
(the seventh and eighth person spectate until a seat frees up), `!bots 0` to `4`, no quad (`minqlx.replace_items("item_quad", 0)` after each map load), no spawn timers on the armors and the
mega (`g_itemTimers 0`), weapons back in 5 s as in a duel (`g_weaponRespawn 5` in both modes since 2026-10-12, owner: "5 sec weapon respawns (just like duel) even for FFA"; it was 2 s in free-for-all from 2026-10-06. It is also what he is trained with: the simulator's `ITEM_DEFS` give every weapon 5 s in every group size. Measured on a private server: 4,975 to 5,000 ms in both modes, also after `!mode` and after a map change). Cost per Bobby per frame is about 70 ray casts and one pass of a
1.5 M-weight network in numpy: four Bobbys fit inside the 25 ms server frame on one core. `PORT=<udp port>` runs a second
container beside the 1v1 one. Logs: `docs/LOGS.md`, schema 4.

## The end of a game and the vote for the next map

A real game (started with F3) ends with the game's own sequence, in both modes (since 2026-10-12; before, the plugins
said `abort` in the frame of the game's end and the server fell straight back to warmup): the scoreboard, the vote
among three maps for 20 seconds, the chosen map about 23 seconds after the end, in warmup, with the Bobbys and the
map's duel items. The pool of the vote is exactly the ten duel maps he trains on, in the mode's own factory:
`server/mappool_lab.txt` (`<map>|ffa`) and `server/mappool_lab_duel.txt` (`<map>|duel`). `entrypoint.sh` names the
file on the command line by `FACTORY` (the game reads its pool before any config file); at a mode switch the playing
plugin sets `sv_mapPoolFile` and says `reload_mappool` (`plugins/powerups.py`, `map_pool`); "loaded 10 maps into the
map pool" in `server.log` each time. The plugins keep their hands off for 90 seconds after a game's end or until the
next map is up; a server on which no map came out of the vote goes back to warmup then. A map that comes up in the
other mode's factory is loaded again in the right one.

Who decides (measured with stand-ins on a private server): a person votes with a click or `vote 1|2|3` and may change
it; the Bobbys do not vote; one vote decides; with no vote the game draws one of the three (three samples: the first,
the third, the second); with a tie it took one of the tied maps. The map just played can be among the three.

## The QLStats lookup (off unless `QLSTATS=1`)

`docs/design/QLSTATS.md` has the research. With `QLSTATS=1` in front of the start (`tools/duel_server.sh`, and
`tools/push_bobby.sh` hands it to the server's start; without it the feature does not exist on the server: no hook, no
command, no thread, no line in the welcome) `plugins/ladder.py` asks qlstats.net for a person's public rating at his
first join of a day:
- **What leaves the server:** two HTTPS requests, `/glicko/<Steam id>` and `/elo/<Steam id>`, with a User-Agent that
  names this project; QLStats sees the server's address, the time and the id. One person at a time, 3 s to connect and
  5 s to answer, one try, in a background thread: the game's frames are not held up (measured: 40.0 a second across a
  request that timed out). No new request for a key for 24 hours after an answer, 1 hour after a failure, 30 days for an
  account QLStats does not track.
- **What is stored**, in the data folder beside `ratings.json`, by the leaderboard's anonymous key and never by Steam
  id: `qlstats.json` (the latest answer per key), `qlstats.jsonl` (every answer), `qlstats_off.json` (the keys of
  those who switched it off). A rating with 0 games is no rating (QLStats answers 900 with 0 games for a player it does
  not know). An error is stored by its class name only: its text and the address hold the Steam id, and the raw logs
  are taken off the server every day. A row of ratings and game counts is nearly a fingerprint: the files are as
  private as `salt.txt`.
- **What a person sees:** a line in the welcome ("Ratings: I look up your public QLStats rating (your Steam id goes to
  qlstats.net) to see how strong my opponents are. !qlstats off stops it."), a second line under his own `!elo`, and
  `!qlstats off|on`. Off deletes what was stored of him and stops the lookups. The request for a person who joins for
  the first time leaves as he reads that line: the switch stops the next ones.
- `QLSTATS_URL=<address>` points the lookup at another address (the tests use a fake of their own inside the container:
  no test ever asks qlstats.net).
- After a start, `minqlx.log` has `[ladder] qlstats: on (<n> answers stored, <m> people switched it off)` or
  `[ladder] qlstats: off`, and one line per answer with its status (`ok`, `none`, `untracked`, `deactivated`, `error`
  and the error's class), never a key or an id.

## Our own maps and the Steam Workshop

Quake Live clients get custom maps only from the Steam Workshop: the old downloads from the server (HTTP, UDP)
were removed from the game. A player who joins while the server is on `arena1` or `testlab` without having the
map is not sent it. So:

The maps are Workshop item **3814411166** (uploaded 2026-10-05). Its ID is in `server/workshop.txt`, which the
image copies into the server's `baseq3`: the server fetches the item at start and joining players download it
automatically.

After a map rebuild:
1. Copy the new pk3 files into `data/workshop/content/`, put the item's ID in `data/workshop/item.vdf`
   (`"publishedfileid" "3814411166"`), and upload with SteamCMD: `workshop_build_item <path to item.vdf>`.
2. On the machine: `git pull && docker build -t qlbot . && RESTART=1 bash tools/duel_server.sh -`.
The server also mounts the pk3 files from the repo, so the repo and the Workshop item must hold the same build.


## Day to day

A network is put on the server with `tools/push_bobby.sh <run> <simulator module> [map]` (`CODE=1` also pulls the code,
rebuilds the image and restarts). The simulator switches a network was trained with travel in its file: checkpoints
written since 2026-10-08 carry them, for older runs give them by hand, e.g.
`CODE=1 FFA=3 EXPORT_ARGS="--set INTENT_HOLD=8" bash tools/push_bobby.sh duel_gru_v12 duel_env_ffa_v12 arena1`.
v0.1 as it has been on the server since 2026-10-11 (`duel_gru_v15c`'s end with his legs; 576 inputs, so the frozen
module `duel_env_ffa_v15`), with new code and the QLStats lookup on:
`QLSTATS=1 CODE=1 EXPORT_ARGS="--policy policy_end_v15c.pt --legs move_v15n --set LEGS_OFF=2" bash tools/push_bobby.sh duel_gru_v15c duel_env_ffa_v15 bloodrun`
(the export needs PyTorch: `PYTHON=<the Anaconda python>` in front, and `CUDA_VISIBLE_DEVICES=-1` while a training run
holds the graphics card). `QLSTATS=1` must be named at every `CODE=1` push, like `FFA` and `HOSTNAME_QL`: a restart
without it switches the lookup off.

| Task | Command |
|---|---|
| New Bobby | On the PC: export as above, then `scp data/duellive/policy.npz root@<ip>:bobbybones-quake/data/duellive/`. The running server loads it by itself between rooms and says so in chat |
| New code or map | On the PC: `CODE=1 bash tools/push_bobby.sh <run> <simulator module>` (git pull, image build and restart on the machine, the walking maps and map tables of the ten maps copied) |
| A hung server | `tools/watchdog.sh` (started in the container) kills the game when its main thread has used no CPU time for 90 s; with `RESTART=1` the container comes back by itself |
| Get the data | On the PC: `bash tools/pull_sessions.sh` (the daily task does it at 09:30; see "Logs" below). The archive is `T:\quake-sessions\public` |
| Stop | `bash tools/duel_server.sh stop` |
| Send a chat command from outside | `docker exec qlduel python3 /tools/rcon.py "qlx !room off" --wait 2` |

## Before strangers arrive (not built yet, backlog B-61, B-69)

- **The test map on the players' side.** Quake Live clients need `testlab.pk3`. Whether they download it from
  the server is untested (B-65); if not, it has to be published on the Steam Workshop, or the chamber is offered
  on the stock maps only.
- **Commands are open to everyone.** Anyone can change the map, start rooms or `!spar`. Fine for a first
  weekend; later, room and map commands should need a vote or be limited to the player in the duel.
- **Privacy notice.** Sessions record positions, view angles and key presses per frame, without names or Steam
  IDs. This should be shown on join and stated in the README.
- **Which Bobby can be served.** The server plugin plays networks trained up to `duel_gru_v3`. Networks trained
  with the newer rules (`duel_gru_v4` and later) need the plugin update in B-57 first.
- **Results for players.** Their card next to Bobby's and the average of all players (B-64).
- **Data collection.** Pulling logs by hand works for one machine; several machines want an automatic upload.

## Cost

| Setup | Per month |
|---|---|
| One machine in Chicago, one server (this document) | about $20 (possibly $10-12 on the smaller plan) |
| Later: Chicago + Europe + US west, two servers each | about $45-50 |

## Logs: what is written, and where it goes

- The server writes game data only while a person is playing: frame rows for every Bobby and every person (`docs/LOGS.md`), and
  since 2026-10-07 the events too (deaths, pickups, the minute summaries were written for the bots alone before). With under
  5 GB free on the disk nothing is written.
- `tools/pull_sessions.sh`, run every day at 09:30 by the Windows scheduled task "BobbyBones session pull" on the owner's PC
  (and on the next start if the PC was off), brings a day's data to `T:\quake-sessions\public` (the routine of 2026-10-11):
  - **Sessions**: every finished one is packed on the server (`tar.gz`, about a fifth of the size), copied, compared by
    checksum and test-read. Its folder is then removed from the server; its archive stays there for seven days as a
    second copy (owner: 7) and is removed after. The newest session is the live one and is left alone; in free-for-all
    a new session folder begins a minute after the last person has gone, so a visit is a finished session by the next pull.
  - **Raw logs** (`server.log`, `duelbot.log`, `minqlx.log`, `duel_live.jsonl`): packed, copied to `logs\`, checked, and
    removed from the server the same day. They hold visitors' Steam IDs and addresses and stay out of the repo.
    `minqlx.log` (every event with its time) is written to the data folder since this routine (`QLX_LOG_DIR`); inside
    the container it was lost at every rebuild.
  - **Leaderboard and bans**: copied every day, never removed from the server: `ratings.json`, `frags.jsonl`,
    `duels.jsonl` (finished duels), the QLStats files where the lookup is on, `bans.txt`, and `salt.txt`.
  - **The salt** (`salt.txt` in the server's data folder) makes a person's anonymous key: the first ten signs of
    sha1(salt + Steam id). The pull keeps a copy in the archive (never in the repo); if the server's salt ever differs
    from the archive's, the old one is kept beside it and `pull.log` says so (every person would have a new key from
    that day). A local play-test server gives a person the same key as the public one only with the same `salt.txt`
    in its own data folder (`data/duellive/`); with its own salt his games there are another person's.
  - **Index**: `sessions.csv`, a row per session (`tools/session_index.py`: start, end, minutes, map, mode, people at
    once, different persons by the leaderboard's keys, frags). `python tools/session_index.py --since "2026-10-10 21:00"`
    answers "who played since".
  - **Second copy**: the whole folder is copied to `E:\quake-sessions\public`, another disk (`SESSION_MIRROR`).
  It also clears the server images no container uses. A few lines per run go to `pull.log`. Everything played by people is kept on the PC.


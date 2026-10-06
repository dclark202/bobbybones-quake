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
scp data/maps/arena1.bsp data/maps/testlab.bsp root@<ip>:bobbybones-quake/data/maps/   # our own maps, for his senses (again after every map rebuild)
```

## Start the server

On the machine:

```bash
cd bobbybones-quake
RESTART=1 HOSTNAME_QL="BobbyBones | duel the learning bot | !rooms" bash tools/duel_server.sh - arena1
```

- `-` means "use the `policy.npz` already in `data/duellive`" (no PyTorch needed on the machine).
- `RESTART=1` brings the server back after a crash or a reboot.
- No password by default. `PASSWORD=<word>` in front sets one (useful for a private first test).
- Players connect with `connect <ip>:27970` in the game console; the server also appears in the server browser.
- Check it: `docker ps`, `tail data/duellive/duelbot.log`.

One server holds one duel at a time; other players spectate and queue (the game's own duel queue).

## Our own maps and the Steam Workshop

Quake Live clients get custom maps only from the Steam Workshop: the old downloads from the server (HTTP, UDP)
were removed from the game. A player who joins while the server is on `arena1` or `testlab` without having the
map is not sent it. So:

1. Upload `maps/arena1/arena1.pk3` and `maps/testlab/testlab.pk3` as Workshop items (the owner's Steam account;
   one item with both files is fine).
2. Put the item's ID in the server's `baseq3/workshop.txt`, one ID per line. The server then fetches the item
   itself and tells joining clients to download it, which they do automatically.
3. After a map rebuild: update the Workshop item, then restart the server.

Until that is done, only players who were handed the pk3 files can join those two maps.

## Day to day

| Task | Command |
|---|---|
| New Bobby | On the PC: export as above, then `scp data/duellive/policy.npz root@<ip>:bobbybones-quake/data/duellive/`. The running server loads it by itself between rooms and says so in chat |
| New code or map | On the machine: `git pull && docker build -t qlbot . && RESTART=1 bash tools/duel_server.sh - arena1` |
| Get the data | On the PC: `rsync -av root@<ip>:bobbybones-quake/data/duellive/sessions/ data/public/sessions/` and the same for `suite/` |
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

# Server commands

Typed in the game chat on the play-test server (`plugins/duelbot.py`). Anyone on the server can use them.

## Playing and feedback

| Command | What it does |
|---|---|
| `!note <text>` | Saves your comment with the game state at that moment (both positions, health, his weapon, whether he could see you, the room if one is running). Start with a tag: `aim`, `move`, `weapon`, `items`, `position`, `stuck`, `unfair`, `weird`, `good` |
| `!map <name>` | Changes the map: `bloodrun`, `aerowalk`, `campgrounds`, or `bobbylab` (the test map) |
| `!drill <weapon>` / `!drill off` | Both players get only that weapon (`rl`, `rg`, `lg`, `mg`, `sg`, `gl`, `pg`, `hmg`); `off` returns to the normal spawn weapons |
| `!spar` / `!spar off` | You become a spectator and BobbyBones plays a Nightmare bot in a real match. `!spar off`, or joining the game, ends it |

## Test rooms

BobbyBones' body becomes the scripted target or opponent and you are measured. Each room counts down 5 s, runs,
and prints your result in chat. `!rooms` lists the rooms for the current map; `!room off` stops.

**On the test map** (`!map bobbylab` first):

| Command | Room | Length |
|---|---|---|
| `!room suite` | All 26 rooms below, back to back | about 10 min |
| `!room aim <weapon> walk` | Aim box: the target moves left, right, forward and back at random. Weapons: `mg`, `sg`, `rl`, `lg`, `rg`, `pg`, `hmg` | 15 s |
| `!room aim <weapon> jump` | Aim box: the same movement, with jumping | 15 s |
| `!room aim <weapon> env` | Environment box (pillars, cover): the target moves at random | 15 s |
| `!room speed` | Speed straight: 20,000 units, one way; you are put back at the start after each run | 30 s |
| `!room fight <style>` | A fight in the environment box against a scripted style: `allround`, `sniper`, `rusher`, `tracker` (these four are in the suite), `dodger`, `stander`, `jumper`, `spammer` | 30 s |

Aim rooms: endless ammo, the target never shoots or dies. Speed room: gauntlet only. You hold no weapon during
the 5 s countdown, and you cannot die in a test room except in the fights.

**On the stock maps** (Blood Run, Aerowalk, Campgrounds):

| Command | Room | Length |
|---|---|---|
| `!room suite` | The stock-map set: aim, weapon choice, movement, solo, four ladder opponents | about 25 min |
| `!room aim <weapon> <target> [range]` | Aim at a scripted target (`still`, `slow`, `fast`, `jump`) at `close`, `mid` or `far`; you are moved to a new spot every 10 s | 60 s |
| `!room choice <range>` | Every weapon in hand: which one do you use at that distance | 40 s |
| `!room move` | Run to the item named on screen, goal after goal | 90 s |
| `!room solo` | Alone on the map: collect what you would in a real game | 120 s |
| `!room ladder [style]` | A fight against a scripted style | 120 s |

What each room measures: [LOGS.md](LOGS.md). The play-test routine: [PLAYTEST.md](PLAYTEST.md).

## Admin (server console or rcon only)

```bash
docker exec <container> python3 /tools/rcon.py "qlx !room suite" --wait 2    # any chat command, from outside the game
docker exec <container> python3 /tools/rcon.py "map bloodrun duel" --wait 2
bash tools/duel_server.sh <run> <map> <env module>                           # start or restart the server
bash tools/duel_server.sh stop
```

A new `data/duellive/policy.npz` (written by `sim/export_duel.py`) is loaded by the running server on its own,
between rooms, and announced in chat.

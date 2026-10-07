# Server commands

Typed in the game chat on the play-test server (`plugins/duelbot.py`). Anyone on the server can use them.

## Playing and feedback

| Command | What it does |
|---|---|
| `!note <text>` | Saves your comment with the game state at that moment (both positions, health, his weapon, whether he could see you, the room if one is running). Start with a tag: `aim`, `move`, `weapon`, `items`, `position`, `stuck`, `unfair`, `weird`, `good` |
| `!map <name>` | Changes the map: `bloodrun`, `aerowalk`, `lostworld`, `campgrounds`, `testlab` (the test map) or `arena1` (the yard as a small duel map with a mega health, a red armor, rocket launcher, lightning gun and railgun to pick up; duel spawn) |
| `!drill <weapon>` / `!drill off` | Both players get only that weapon (`rl`, `rg`, `lg`, `mg`, `sg`, `gl`, `pg`, `hmg`); `off` returns to the normal spawn weapons |
| `!nosg` / `!nosg off` | Nobody spawns with a shotgun (it can still be picked up on the map); `off` returns to every weapon |
| `!reflex` (or `!room reflex`) | On the test map: the aim reflex test. Four short aim rooms, about three and a half minutes; in three of them the target shoots back for the second half (you cannot die); move as you normally would: lightning gun on a target that walks slowly from side to side, lightning gun on a target that strafes and turns at random, railgun on a target that jumps to a new place every few seconds, rockets on the strafing target. Stand still. Results are saved under an anonymous id; `tools/reflex_report.py` compares people with Bobby. Single rooms: `!room reflex slow|track|flick|rocket` |
| `!arena box` / `!arena env` / `!arena yard` `[minutes]` / `!arena off` | On the test map: fight BobbyBones in the aim box, the environment box or the yard (a small two-level duel arena: balconies, stairs, a ramp, a tower with a catwalk, a jump pad, a teleporter, a tunnel; not in his training yet) under the rules he trains with: full weapon set at spawn, 125 health, nobody leaves the room, five minutes (or the number given). The score and damage are announced at the end |
| `!duel [minutes]` (or `!match`) | A timed, scored duel: on `testlab` in the environment box, on `arena1` and the duel maps across the whole map as it is (10 minutes by default on the duel maps). `!duel off` stops it |
| `!spar` / `!spar off` | You become a spectator and BobbyBones plays a Nightmare bot in a real match. `!spar off`, or joining the game, ends it |

## Free-for-all servers (`plugins/ffabot.py`)

A server started with `FFA=<n>` runs up to four Bobbys and people together, six seats in all, everybody against
everybody, in permanent warmup.

| Command | Who | What it does |
|---|---|---|
| `!bots <0-4>` | anyone | how many Bobbys play; people get the other seats (6 - n; the server holds 8 clients, the rest spectate). Raising it is refused while more people than that are playing; lowering it frees seats. Nobody can push a bot out. |
| `!match [minutes]` (or `!duel`) | anyone | a scored match for everybody in the game, 10 minutes by default: normal spawn, the items on the map; a table of kills, deaths and damage at the end. `!match off` stops it |
| `!help`, `!note <text>` | anyone | as on the 1v1 server |

The 1v1 rooms (`!reflex`, `!movement`, `!room`) are not in free-for-all mode.

## Switching modes (`plugins/botmode.py`, loaded on every server)

| Command | Who | What it does |
|---|---|---|
| `!mode ffa [bots]` / `!mode duel` | anyone | switch the running server between free-for-all and 1v1 (the plugin and the game factory change, the map restarts, the bots are replaced) |
| `!map <name>` | anyone | change the map and take its mode: `arena1` is free-for-all by design; `testlab` and the duel maps are 1v1 (the duel factory keeps two players active) |

## Test rooms

BobbyBones' body becomes the scripted target or opponent and you are measured. Each room counts down 5 s, runs,
and prints your result in chat. `!rooms` lists the rooms for the current map; `!room off` stops.

**On the test map** (`!map testlab` first):

| Command | Room | Length |
|---|---|---|
| `!room suite` | Every aim room and every movement course, back to back | about 22 min |
| `!room aim <weapon> walk` | Aim box: the target moves left, right, forward and back at random. Weapons: `mg`, `sg`, `rl`, `lg`, `rg`, `pg`, `hmg` | 25 s |
| `!room aim <weapon> jump` | Aim box: the same movement, with jumping | 25 s |
| `!room aim <weapon> env` | Environment box (pillars, cover): the target moves at random | 45 s |
| `!room move <course>` | Movement course, 30 s or until you reach the end. Courses: `speed` (flat 20,000-unit straight), `circle` (gaps that each need one circle jump from a standing start), `twohop` (gaps that need a circle jump plus one strafe jump), `ramps` (ramps and stairs), `slalom` (walls from alternating sides), `turns` (45, 90, 135 degree turns and a hairpin), `narrow` (a beam over a pit, 96 down to 32 wide), `pillars` (hop from pillar to pillar), `rocket` (rocket-jump up four ledges, the last needs a double rocket jump; rocket launcher). A fall puts you back at the last checkpoint | up to 30 s |
| `!room moves` | Every movement course in a row, then a table of your times and the total (30 s counted for each one not finished) | about 8 min |
| `!room move bends` | A track with no walls over a pit, with 45-degree bends: carry speed by air-steering | 30 s |
| `!room move pads` | Jump pad up to a ledge, a teleporter at its end, a jump pad over a wall | 30 s |
| `!room move drops` | Get down 1200 units fast on 1 health: any fall damage kills and ends the run (drops of 200, 240, 320, 440; side ledges split the big ones) | 30 s |
| `!room move climb` | Eighteen ledges, each 40 high (a jump each) | 30 s |
| `!room move dodge` | A rocket turret fires at you from the far end of a corridor with a little cover: reach the line in front of it. Reports damage taken | 30 s |
| `!room items` | A ring corridor with a mega health (35 s) and a red armor (25 s) in opposite corners, gauntlet only: how many of the possible pickups you get (not in the suite: meant for Bobby) | 120 s |
| `!room fight` | A fight in the environment box against the game's own Nightmare bot (not in the suite) | 60 s |

Aim rooms: endless ammo, the target never shoots or dies. Movement courses: gauntlet only. You hold no weapon during
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

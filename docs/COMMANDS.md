# Server commands

Typed in the game chat on the play-test server (`plugins/duelbot.py`). Anyone on the server can use them.

## Playing and feedback

| Command | What it does |
|---|---|
| `!note <text>` | Saves your comment with the game state at that moment (both positions, health, his weapon, whether he could see you, the room if one is running). Start with a tag: `aim`, `move`, `weapon`, `items`, `position`, `stuck`, `unfair`, `weird`, `good` |
| `!map <name>` | Changes the map, limited to the duel maps he has trained on or is checked on: `bloodrun`, `aerowalk`, `lostworld`, `sinister`, `furiousheights`, `battleforged`, `campgrounds`, `hektik`, `toxicity`, `cure`, and `testlab` (the test map). `!maps` lists them |
| `!drill <weapon>` / `!drill off` | Both players get only that weapon (`rl`, `rg`, `lg`, `mg`, `sg`, `gl`, `pg`, `hmg`); `off` returns to the normal spawn weapons |
| `!nosg` / `!nosg off` | Nobody spawns with a shotgun (it can still be picked up on the map); `off` returns to every weapon |
| `!reflex` (or `!room reflex`) | On the test map: the aim reflex test. Four short aim rooms, about three and a half minutes; in three of them the target shoots back for the second half (you cannot die); move as you normally would: lightning gun on a target that walks slowly from side to side, lightning gun on a target that strafes and turns at random, railgun on a target that jumps to a new place every few seconds, rockets on the strafing target. Stand still. Results are saved under an anonymous id; `tools/reflex_report.py` compares people with Bobby. Single rooms: `!room reflex slow|track|flick|rocket` |
| `!arena box` / `!arena env` / `!arena yard` `[minutes]` / `!arena off` | On the test map: fight BobbyBones in the aim box, the environment box or the yard (a small two-level duel arena: balconies, stairs, a ramp, a tower with a catwalk, a jump pad, a teleporter, a tunnel; not in his training yet) under the rules he trains with: full weapon set at spawn, 125 health, nobody leaves the room, five minutes (or the number given). The score and damage are announced at the end |
| `!duel [minutes]` (or `!match`) | In 1v1 mode, a timed, scored duel: on `testlab` in the environment box, on the duel maps across the whole map as it is (10 minutes by default). `!duel off` stops it |
| `!spar` / `!spar off` | You become a spectator and BobbyBones plays a Nightmare bot in a real match. `!spar off`, or joining the game, ends it |

## Free-for-all servers (`plugins/ffabot.py`)

A server started with `FFA=<n>` runs up to four Bobbys and people together, six seats in all, everybody against
everybody. It waits in warmup (every weapon at spawn) until more than half of the people in the game have readied up
(F3; the Bobbys never ready up and are not counted): then a real 10-minute game runs, machine gun at spawn, the game's
own table at the end, and warmup again. No quad, no spawn timers on the armors and the mega, weapons back in 2 s (2026-10-06).

| Command | Who | What it does |
|---|---|---|
| `!bots <0-4>` | anyone | how many Bobbys play; people get the other seats (6 - n; the server holds 8 clients, the rest spectate). Raising it is refused while more people than that are playing; lowering it frees seats. Nobody can push a bot out. |
| F3 (ready up) | people | when more than half of the people in the game are ready, a real 10-minute game starts (no frag limit, machine gun at spawn, the items on the map); the game's own table of kills, deaths and damage at the end, then warmup again. There is no `!match` in free-for-all (2026-10-06) |
| `!help`, `!maps`, `!note <text>` | anyone | as on the 1v1 server |

The 1v1 rooms (`!reflex`, `!movement`, `!room`) are not in free-for-all mode.

## Switching modes (`plugins/botmode.py`, loaded on every server)

| Command | Who | What it does |
|---|---|---|
| `!mode ffa [bots]` / `!mode duel` | anyone | switch the running server between free-for-all and 1v1 (the plugin and the game factory change, the map restarts, the bots are replaced) |
| `!map <name>` | anyone | change the map and take its mode: the duel maps come up in free-for-all with the items of a duel (`!mode duel` then makes it 1v1); `testlab` is always 1v1 (the duel factory keeps two players active) |

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

## The leaderboard (`plugins/ladder.py`, loaded on every play-test server)

Every frag between a person and BobbyBones counts, either way, in warmup and in games, in free-for-all and in 1v1.
Frags between two people, between two Bobbys, by the game's own bots, deaths by one's own hand or the map, and the test
rooms (where Bobby's body is a scripted target) do not. It is local to the server.

| Command | What it does |
|---|---|
| `!bobby` | BobbyBones' rating and rank, his frags made and taken against people, and the ratings of his earlier networks |
| `!top` | the board: the first eight, and always Bobby's line and your own |
| `!elo` / `!elo <name>` | your rating and rank, or how many frags are missing until you are ranked; somebody else's by a part of his name |
| `!ladder` | (the owner) what the plugin has read since it was loaded: deaths seen, paired with a killer, counted, left out |

The rating is Glicko-1 with one update per frag (`plugins/ratings.py`): a number and how unsure it is. Everybody starts
at 1500. A difference of 100 points means 64% of the frags between the two, 200 points 76%, 400 points 91%. A frag
counts as a quarter of a game, because frags come in streaks. A person is ranked from 20 frags with Bobby. Every
person meets only Bobby here, so a person's number says how he does against Bobby, and Bobby's says how he does against
the people who come. A new network of Bobby has its own row and starts at the last one's number, unsure enough that it
is his number that moves, not the people's, when he has got better or worse.

On the PC: `python tools/elo.py` prints the board and, per network and person, the frags made and taken with a 95%
range (the files come with the daily `tools/pull_sessions.sh`).

## The bots' names and what they say (`plugins/banter.py`)

A free-for-all server's bots are BobbyBones, Mr Skeleton, THE JUGGERNAUT and Dr Evil, each with (BOT) after the name;
they join in that order and leave in the reverse. BobbyBones and Mr Skeleton wear the skeleton, THE JUGGERNAUT the big
TankJr body, Dr Evil the bald Xaero (the game's box for a player is the same for every body).
All four are the same network and share one row on the leaderboard. Each has a voice of its own in chat: a line at a
game's end by where it finished, and now and then one during a game, only with a person playing: after three frags
without dying, after dying by its own hand or the map, after the same person has fragged it three times without an
answer (by name), after a rail frag from far away. A bot speaks at most once in 75 seconds, the bots together at most
once in 20. `!banter` (the owner) makes each say a line now.

## The owner's commands (`plugins/banlist.py`, loaded on every play-test server)

Only for the server's owner: the Steam ID in `data/owner.env` (`QLX_OWNER=<SteamID64>`, git-ignored) on the machine the
server is started from. Typed in the game chat, or sent through rcon (below). Anyone else gets no answer.

| Command | What it does |
|---|---|
| `!players` | everyone connected: number and name |
| `!kick <number or part of a name>` | off the server now; the player can come back |
| `!ban <number or part of a name> [why]` | off the server and refused from then on ("You are banned from this server.") |
| `!bans` | the bans: a number each, when and why |
| `!unban <number from !bans>` | lifts a ban |

Bans are kept by Steam ID in `bans.txt` in the server's data folder (`data/duellive/`), outside the image and the repo:
they survive a restart and a new image. A name that fits two players is refused (use the number). Bots cannot be
kicked this way (`!bots <n>`).

## Admin (server console or rcon only)

```bash
docker exec <container> python3 /tools/rcon.py "qlx !room suite" --wait 2    # any chat command, from outside the game
docker exec <container> python3 /tools/rcon.py "map bloodrun duel" --wait 30   # a map change: a wait that covers the load
bash tools/duel_server.sh <run> <map> <env module>                           # start or restart the server
bash tools/duel_server.sh stop
```

The game sends its whole console to every rcon client and that send blocks: a client that leaves while the server is
printing a map load can freeze the server (2026-10-09). `tools/rcon.py` therefore leaves only once nothing has come for
a second; do not cut it off, and do not use another rcon client on a server people are playing on.

A new `data/duellive/policy.npz` (written by `sim/export_duel.py`) is loaded by the running server on its own,
between rooms, and announced in chat.

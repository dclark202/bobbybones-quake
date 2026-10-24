#!/bin/bash
# Private play-test server: the owner against a simulator-trained duel policy (plugins/duelbot.py).
# Container qlduel, UDP 27970. No password by default (PASSWORD=<word> sets one). The owner's Steam ID lives in
# data/owner.env (git-ignored): QLX_OWNER=<SteamID64>
#   bash tools/duel_server.sh <run> [map] [env module]     e.g. bash tools/duel_server.sh duel_gru_v2 bloodrun duel_env_v2
#   bash tools/duel_server.sh -                             use the policy.npz already in data/duellive (no PyTorch needed)
# The map defaults to bloodrun. The server is 1v1 only, on the ten duel maps he trains on (owner, 2026-10-23: "we can remove
# ffa entirely from the server, and remove the two custom maps"): players pick among those ten with !map. The test maps
# (testlab, arena1) are not loaded unless TESTMAPS=1, on a local server only and as its start map (bash tools/duel_server.sh
# <run> testlab with TESTMAPS=1: the test rooms); !map never offers them (a client without their pk3 files is dropped on
# joining a pure server).
#   bash tools/duel_server.sh stop
# Options: PASSWORD=<word>, RESTART=1 (restart after a crash or reboot), HOSTNAME_QL="<name in the server list>"
# With SPAR=1 no port is opened and a Nightmare bot is the opponent (for measuring); SKILL=4 makes it Hardcore.
# FFA=<n> is no longer read (until 2026-10-23 it ran the free-for-all plugin, plugins/ffabot.py); the server starts in 1v1.
# PORT=<udp port> for a second container (default 27970). PUBLIC=1 lists the server in the game's server browser (off by default).
# A network with legs: EXPORT_ARGS="--legs <the movement network's run>" (v0.1, v0.2: move_v15n). A copy of a running
# trainer's save: EXPORT_ARGS="--policy <full path of the copy> --legs move_v15n".
# Before the server starts, the map tables the simulator caches (tools/prep_ways.py: since v0.2 also the ways between any
# two points, up to ten seconds a map at its first load) are made for the start map and the maps of !map; PREP=0 skips it,
# PREP_MAPS="a b" names other maps. For checks: TIMING=1 (the plugin's time a frame, to timing.txt in the data folder),
# OBSDUMP=1 / FFA_OBSDUMP=1 (his inputs, to obs_dump.npy there; with a v0.4.1 brain in the 1v1 plugin also brain_dump.npy: his
# pose, the enemy's true place and the brain's answer). BTOKEN_GATE=<g>: play the brain's token at this gate in place of the
# file's (0: shut; plugins/netpass.py NET_BTOKEN_GATE).
# QLSTATS=1 switches the leaderboard's QLStats lookup on (plugins/ladder.py; off by default: a person's Steam id then goes
# to qlstats.net once a day, he is told so on joining and "!qlstats off" stops it); QLSTATS_URL=<address> another service
# address (tests: a fake of one's own).
# For tests of the server's own routines on a private server (never on one people play on): IMAGE=<image> (default qlbot),
# PLUGINS_EXTRA="testkit" (more plugins, loaded after the others), DOCKER_EXTRA="<options of docker run>", e.g. the working
# tree's plugins and tools in place of the image's and the test plugin's switch:
#   DOCKER_EXTRA="-v $PWD/plugins:/ql/minqlx-plugins:ro -v $PWD/tools:/tools:ro -e TESTKIT=1"   (plugins/testkit.py)
set -e
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
ROOT="$(pwd -W 2>/dev/null || pwd)"
NAME="${NAME:-qlduel}"                 # container name (use another one for a second, private test server)
DATA="${DATA:-data/duellive}"          # where the policy and the logs go
docker rm -f "$NAME" >/dev/null 2>&1 || true
[ "$1" = "stop" ] && { echo "duel server stopped"; exit 0; }
RUN="${1:?run name}"; MAP="${2:-bloodrun}"; ENVMOD="${3:-duel_env}"
PY="${PYTHON:-python}"
IMAGE="${IMAGE:-qlbot}"
mkdir -p $DATA
if [ "$RUN" = "-" ]; then                # "-" = use the policy.npz already in $DATA (a machine without PyTorch)
    [ -f "$DATA/policy.npz" ] || { echo "no $DATA/policy.npz"; exit 1; }
else
    "$PY" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out $DATA/policy.npz $EXPORT_ARGS   # EXPORT_ARGS="--set INTENT_HOLD=8": the switches a run before v13 was trained with
fi
RESTART_OPT=""; [ -n "$RESTART" ] && RESTART_OPT="--restart unless-stopped"   # RESTART=1: come back after a crash or reboot
# One thread for the numeric library: its helpers spin between the network's matrix products (40 a second), one per core.
# A local server with three Bobbys held 7 to 8 of the PC's 20 threads for a day with nobody on it (2026-10-08, B-153).
ONE_THREAD="-e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1"
# The map tables, made before the server takes players (a game server stands still while the simulator works one out at a
# map's first load). A sparring server stays on its map; a play-test server offers the ten duel maps (and starts on the test map with TESTMAPS=1).
if [ "${PREP:-1}" != "0" ]; then
    ALL_MAPS="bloodrun aerowalk lostworld sinister furiousheights battleforged campgrounds hektik toxicity cure"
    [ "$TESTMAPS" = "1" ] && ALL_MAPS="$ALL_MAPS testlab"
    [ -n "$SPAR" ] && ALL_MAPS=""
    docker run --rm $ONE_THREAD --entrypoint python3 -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" \
        -v "$ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro" "$IMAGE" /tools/prep_ways.py "$MAP" ${PREP_MAPS:-$ALL_MAPS} \
        || echo "map tables: not prepared (the server makes them at a map's first load)"
fi
if [ -n "$SPAR" ]; then
    docker run -d --name "$NAME" $ONE_THREAD -e QLX_PLUGINS="botctl, duelbot" -e LAB_MAP="$MAP" -e DUEL_OPP=bot -e DUEL_ROOMTEST="$ROOMTEST" -e DUEL_OBSDUMP="$OBSDUMP" -e DUEL_AIMDUMP="$AIMDUMP" -e DUEL_BOT_SKILL="${SKILL:-5}" -e DUEL_ARENA="$ARENA" -e DUEL_ARENA_MIN="$ARENA_MIN" -e DUEL_TIMING="${TIMING:-}" -e NET_BTOKEN_GATE="${BTOKEN_GATE:-}" \
        -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" -v "$ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro" -v "$ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro" "$IMAGE" +set sv_master 0 +set sv_serverType 0 >/dev/null
    echo "sparring server up (Bobby vs the game bot, skill ${SKILL:-5}, on $MAP)"; exit 0
fi
QLX_OWNER=""
[ -f data/owner.env ] && QLX_OWNER="$(grep '^QLX_OWNER=' data/owner.env | cut -d= -f2)"
PW="${PASSWORD:-}"                     # no password by default; PASSWORD=<word> sets one
PORT="${PORT:-27970}"
# the test maps only on a local server with TESTMAPS=1 (2026-10-06: players without the files in baseq3 were dropped on joining a
# pure server; since 2026-10-23 no Workshop item either: server/workshop.txt is empty, the pak list is the game's own)
MAP_MOUNTS=""
[ "$TESTMAPS" = "1" ] && [ "$PUBLIC" != "1" ] && MAP_MOUNTS="-v $ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro -v $ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro"
LISTED="+set sv_master 0"; [ "$PUBLIC" = "1" ] && LISTED="+set sv_master 1"   # PUBLIC=1: show in the server list (the rented server); local servers stay unlisted (Windows sets PUBLIC to a folder: an exact 1 is required)
# EARLY_BOBBY (default 1 on a play-test server, 0 with PUBLIC=1): Bobby is added at a map's load, so that a person's game
# loads his model with the map (plugins/duelbot.py, DUEL_EARLY_BOBBY: after a map change he was drawn with the person's own model)
EARLY="${EARLY_BOBBY:-$([ "$PUBLIC" = "1" ] && echo 0 || echo 1)}"
PLUGINS="botctl, banlist, ladder, banter, botmode, duelbot"; MODE="1v1"     # botmode: !map (the ten duel maps; !mode says 1v1 only); banlist: the owner's !kick and !ban; ladder: the leaderboard
[ -n "$FFA" ] && echo "FFA=$FFA ignored: the server is 1v1 only (owner, 2026-10-23)"
[ -n "$PLUGINS_EXTRA" ] && PLUGINS="$PLUGINS, $PLUGINS_EXTRA"
docker run -d $RESTART_OPT --name "$NAME" $ONE_THREAD -e QLX_PLUGINS="$PLUGINS" -e LAB_MAP="$MAP" -e QLX_OWNER="$QLX_OWNER" -e DUEL_OBSDUMP="${OBSDUMP:-}" -e DUEL_TIMING="${TIMING:-}" -e QLSTATS="${QLSTATS:-}" -e QLSTATS_URL="${QLSTATS_URL:-}" -e BOBBY_AUTOHOP="${BOBBY_AUTOHOP:-1}" -e NET_BTOKEN_GATE="${BTOKEN_GATE:-}" -e DUEL_EARLY_BOBBY="$EARLY" \
    -p "$PORT:$PORT/udp" -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" $MAP_MOUNTS $DOCKER_EXTRA "$IMAGE" +set net_port "$PORT" $LISTED \
    +set sv_hostname "${HOSTNAME_QL:-BobbyBones playtest}" +set g_password "$PW" >/dev/null
echo "play-test server up on port $PORT, map $MAP, $MODE ($([ -n "$PW" ] && echo "password set" || echo "no password"), $([ "$PUBLIC" = "1" ] && echo "listed publicly" || echo "unlisted"))"

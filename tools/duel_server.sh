#!/bin/bash
# Private play-test server: the owner against a simulator-trained duel policy (plugins/duelbot.py).
# Container qlduel, UDP 27970. No password by default (PASSWORD=<word> sets one). The owner's Steam ID lives in
# data/owner.env (git-ignored): QLX_OWNER=<SteamID64>
#   bash tools/duel_server.sh <run> [map] [env module]     e.g. bash tools/duel_server.sh duel_gru_v2 bloodrun duel_env_v2
#   bash tools/duel_server.sh -                             use the policy.npz already in data/duellive (no PyTorch needed)
# The map defaults to arena1 (his training arena); testlab has the aim and movement tests.
#   bash tools/duel_server.sh stop
# Options: PASSWORD=<word>, RESTART=1 (restart after a crash or reboot), HOSTNAME_QL="<name in the server list>"
# With SPAR=1 no port is opened and a Nightmare bot is the opponent (for measuring); SKILL=4 makes it Hardcore.
# FFA=<n> runs the free-for-all plugin instead (plugins/ffabot.py): n Bobbys (1 to 4), six seats, !bots changes n.
# PORT=<udp port> for a second container (default 27970). PUBLIC=1 lists the server in the game's server browser (off by default).
set -e
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
ROOT="$(pwd -W 2>/dev/null || pwd)"
NAME="${NAME:-qlduel}"                 # container name (use another one for a second, private test server)
DATA="${DATA:-data/duellive}"          # where the policy and the logs go
docker rm -f "$NAME" >/dev/null 2>&1 || true
[ "$1" = "stop" ] && { echo "duel server stopped"; exit 0; }
RUN="${1:?run name}"; MAP="${2:-arena1}"; ENVMOD="${3:-duel_env}"
PY="${PYTHON:-python}"
mkdir -p $DATA
if [ "$RUN" = "-" ]; then                # "-" = use the policy.npz already in $DATA (a machine without PyTorch)
    [ -f "$DATA/policy.npz" ] || { echo "no $DATA/policy.npz"; exit 1; }
else
    "$PY" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out $DATA/policy.npz $EXPORT_ARGS   # EXPORT_ARGS="--set INTENT_HOLD=8": the switches a run before v13 was trained with
fi
RESTART_OPT=""; [ -n "$RESTART" ] && RESTART_OPT="--restart unless-stopped"   # RESTART=1: come back after a crash or reboot
if [ -n "$SPAR" ]; then
    docker run -d --name "$NAME" -e QLX_PLUGINS="botctl, duelbot" -e LAB_MAP="$MAP" -e DUEL_OPP=bot -e DUEL_ROOMTEST="$ROOMTEST" -e DUEL_OBSDUMP="$OBSDUMP" -e DUEL_AIMDUMP="$AIMDUMP" -e DUEL_BOT_SKILL="${SKILL:-5}" -e DUEL_ARENA="$ARENA" -e DUEL_ARENA_MIN="$ARENA_MIN" \
        -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" -v "$ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro" -v "$ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro" -v "$ROOT/maps/lockout/lockout.pk3:/ql/baseq3/lockout.pk3:ro" qlbot +set sv_master 0 +set sv_serverType 0 >/dev/null
    echo "sparring server up (Bobby vs the game bot, skill ${SKILL:-5}, on $MAP)"; exit 0
fi
QLX_OWNER=""
[ -f data/owner.env ] && QLX_OWNER="$(grep '^QLX_OWNER=' data/owner.env | cut -d= -f2)"
PW="${PASSWORD:-}"                     # no password by default; PASSWORD=<word> sets one
PORT="${PORT:-27970}"
LOCKOUT_MOUNT=""; [ "$PUBLIC" = "1" ] || LOCKOUT_MOUNT="-v $ROOT/maps/lockout/lockout.pk3:/ql/baseq3/lockout.pk3:ro"   # the lockout map is not in the Workshop item: a pure server with it would shut out players who lack it
# the public server takes arena1 and testlab from the Workshop item alone (server/workshop.txt), so that its pak list is exactly
# what a joining client downloads (2026-10-06: players without the files in baseq3 were dropped on joining); local servers mount the repo's copies
MAP_MOUNTS="-v $ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro -v $ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro"
[ "$PUBLIC" = "1" ] && MAP_MOUNTS=""
LISTED="+set sv_master 0"; [ "$PUBLIC" = "1" ] && LISTED="+set sv_master 1"   # PUBLIC=1: show in the server list (the rented server); local servers stay unlisted (Windows sets PUBLIC to a folder: an exact 1 is required)
PLUGINS="botctl, botmode, duelbot"; FACTORY=duel; MODE="1v1"     # botmode: !mode ffa|duel and !map switch the mode live
if [ -n "$FFA" ]; then PLUGINS="botctl, botmode, ffabot"; FACTORY=ffa; MODE="free-for-all with $FFA Bobbys"; fi
docker run -d $RESTART_OPT --name "$NAME" -e QLX_PLUGINS="$PLUGINS" -e LAB_MAP="$MAP" -e QLX_OWNER="$QLX_OWNER" -e FACTORY="$FACTORY" -e BOBBYS="${FFA:-}" -e FFA_LOG_ALWAYS="${FFA_LOG_ALWAYS:-}" \
    -p "$PORT:$PORT/udp" -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" $MAP_MOUNTS $LOCKOUT_MOUNT qlbot +set net_port "$PORT" $LISTED \
    +set sv_hostname "${HOSTNAME_QL:-BobbyBones playtest}" +set g_password "$PW" >/dev/null
echo "play-test server up on port $PORT, map $MAP, $MODE ($([ -n "$PW" ] && echo "password set" || echo "no password"), $([ "$PUBLIC" = "1" ] && echo "listed publicly" || echo "unlisted"))"

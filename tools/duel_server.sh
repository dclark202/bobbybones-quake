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
    "$PY" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out $DATA/policy.npz
fi
RESTART_OPT=""; [ -n "$RESTART" ] && RESTART_OPT="--restart unless-stopped"   # RESTART=1: come back after a crash or reboot
if [ -n "$SPAR" ]; then
    docker run -d --name "$NAME" -e QLX_PLUGINS="botctl, duelbot" -e LAB_MAP="$MAP" -e DUEL_OPP=bot -e DUEL_ROOMTEST="$ROOMTEST" -e DUEL_OBSDUMP="$OBSDUMP" -e DUEL_BOT_SKILL="${SKILL:-5}" -e DUEL_ARENA="$ARENA" -e DUEL_ARENA_MIN="$ARENA_MIN" \
        -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" -v "$ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro" -v "$ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro" qlbot +set sv_master 0 +set sv_serverType 0 >/dev/null
    echo "sparring server up (Bobby vs the game bot, skill ${SKILL:-5}, on $MAP)"; exit 0
fi
QLX_OWNER=""
[ -f data/owner.env ] && QLX_OWNER="$(grep '^QLX_OWNER=' data/owner.env | cut -d= -f2)"
PW="${PASSWORD:-}"                     # no password by default; PASSWORD=<word> sets one
docker run -d $RESTART_OPT --name "$NAME" -e QLX_PLUGINS="botctl, duelbot" -e LAB_MAP="$MAP" -e QLX_OWNER="$QLX_OWNER" \
    -p 27970:27970/udp -v "$ROOT/$DATA:/tmp/practice" -v "$ROOT/data/maps:/maps:ro" -v "$ROOT/maps/testlab/testlab.pk3:/ql/baseq3/testlab.pk3:ro" -v "$ROOT/maps/arena1/arena1.pk3:/ql/baseq3/arena1.pk3:ro" qlbot +set net_port 27970 \
    +set sv_hostname "${HOSTNAME_QL:-BobbyBones playtest}" +set g_password "$PW" >/dev/null
echo "play-test server up on port 27970, map $MAP ($([ -n "$PW" ] && echo "password set" || echo "no password"))"

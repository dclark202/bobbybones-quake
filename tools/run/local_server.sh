#!/bin/bash
# A local play test of one checkpoint (owner, 2026-10-31): the export, the !aim files, the private server, the mind viewer and the local games site.
#   bash tools/run/local_server.sh <run> <save> <version> [map]
#   e.g. bash tools/run/local_server.sh duel_gru_v0_6_1d keep/policy_end_v061d.pt v0.6.1d
# <save>: a file in the run's folder, or a full path. Never public: the server is unlisted and its games stay out of the public site.
# It refuses if the save is missing, or another container holds the port (it never stops a server: someone may be on it).
# Options: PORT (27970), MAP, IMAGE (qlbot:playaim2), ENVMOD (duel_env_ffa), LEGS (move_v17_look), CARD_CMD (the run's train.cmd, for the settings check),
# AIM3=1 (a network trained under AIM3: the AIM3 aim table), AIM4=1 (a network trained under aim4, 2.2e on: aim4's default and aim3's max; no
# better, no worse), DATA (data/duellive_<version without dots>), EXPORT_ONLY=1 (stop after the !aim files), WEAPONS (off, light, strong or pros: the !weapons
# dial's setting at a map's start, plugins/duelbot.py DUEL_WEAPONS; default off; pros: the table chooses his weapon).
set -e
export MSYS_NO_PATHCONV=1
RUN="${1:?run}"; SAVE="${2:?save}"; VER="${3:?version}"; MAP="${4:-${MAP:-bloodrun}}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="${PY:-$USERPROFILE/anaconda3/python.exe}"
IMAGE="${IMAGE:-qlbot:playaim2}"; ENVMOD="${ENVMOD:-duel_env_ffa}"; LEGS="${LEGS:-move_v17_look}"; PORT="${PORT:-27970}"
S="$(echo "$VER" | tr -d .)"; NAME="qlduel_$S"; DATA="${DATA:-data/duellive_$S}"
CK="$SAVE"; [ -f "$CK" ] || CK="data/sim_runs/$RUN/$SAVE"
[ -f "$CK" ] || { echo "REFUSED: no save at $CK"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "REFUSED: no image $IMAGE"; exit 1; }
BUSY="$(docker ps --format '{{.Names}} {{.Ports}}' | grep ":$PORT->" || true)"
if [ -z "$EXPORT_ONLY" ]; then
    [ -z "$BUSY" ] || { echo "REFUSED: port $PORT is held by: $BUSY"; exit 1; }
    [ -z "$(docker ps -aq -f "name=^${NAME}$")" ] || { echo "REFUSED: container $NAME exists; look at it first (docker start $NAME brings it back)"; exit 1; }
fi
# The settings check: a difference in a live dial (LEVEL_PULL, ...) is expected; read each one
if [ -n "$CARD_CMD" ]; then "$PY" tools/run/check_settings.py "$CARD_CMD" --ck "$CK" || echo "settings check: READ THE DIFFERENCES ABOVE"; fi
mkdir -p "$DATA"
CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=1 "$PY" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --policy "$SAVE" --out "$DATA/policy_trained.npz" --legs "$LEGS" --version "$VER" | tail -1 | cut -c1-120
# (2.0e) AIM3=1: a network trained under AIM3 gets the AIM3 table (default, better, max; "worse" is on hold: tools/aim2_levels.py --aim3)
# (2.2e) AIM4=1: a network trained under aim4 gets aim4's default and aim3's max (tools/aim2_levels.py --aim4)
[ -n "$AIM3" ] && [ -n "$AIM4" ] && { echo "REFUSED: AIM3=1 and AIM4=1: one or the other"; exit 1; }
CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=1 "$PY" tools/aim2_levels.py "$DATA" ${AIM3:+--aim3} ${AIM4:+--aim4} | cut -c1-30
if [ -n "$AIM4" ]; then NEED="policy.npz policy_default.npz policy_max.npz legs.npz"
elif [ -n "$AIM3" ]; then NEED="policy.npz policy_default.npz policy_better.npz policy_max.npz legs.npz"
else NEED="policy.npz policy_worse.npz policy_default.npz policy_better.npz policy_max.npz legs.npz"; fi
for f in $NEED; do [ -f "$DATA/$f" ] || { echo "MISSING $DATA/$f"; exit 1; }; done
[ -n "$EXPORT_ONLY" ] && { echo "exported to $DATA"; exit 0; }
# (playaim2 predates sim/btoken.py's current form: the server of v0.6.1c mounted it too. EARLY_BOBBY=0 as the public servers)
RW="$(pwd -W)"
MIND=1 EARLY_BOBBY=0 NAME="$NAME" DATA="$DATA" IMAGE="$IMAGE" PORT="$PORT" DOCKER_EXTRA="-v $RW/sim/btoken.py:/sim/btoken.py:ro${WEAPONS:+ -e DUEL_WEAPONS=$WEAPONS}" bash tools/duel_server.sh - "$MAP" | tail -1
free_port() {
    p=$1; while netstat -an | grep -qE "[:.]$p +.*LISTENING"; do p=$((p + 2)); done; echo "$p"
}
MV=$(free_port 8765); LG=$(free_port 8766)
DIRS=""; for d in data/duellive_*; do [ -d "$d" ] && DIRS="$DIRS,'--data','$(cygpath -w "$d")'"; done
PYW="$(cygpath -w "$PY")"; DW="$(cygpath -w "$DATA")"
powershell -NoProfile -Command "Start-Process '$PYW' -ArgumentList 'tools\\mind_view.py','--data','$DW','--port','$MV' -WindowStyle Hidden -RedirectStandardOutput '$DW\\mind_view.log' -RedirectStandardError '$DW\\mind_view.err'" </dev/null >/dev/null 2>&1
powershell -NoProfile -Command "Start-Process '$PYW' -ArgumentList 'tools\\local_games.py'$DIRS,'--port','$LG','--watch','60' -WindowStyle Hidden -RedirectStandardOutput '$DW\\local_games.log' -RedirectStandardError '$DW\\local_games.err'" </dev/null >/dev/null 2>&1
sleep 40
docker logs "$NAME" 2>&1 | grep -E "duelbot\] ready" | tail -1 | cut -c1-110
READY="$(docker logs "$NAME" 2>&1 | grep -c "duelbot\] ready" || true)"
[ "$READY" -gt 0 ] || echo "NOT READY: read docker logs $NAME"
for u in "http://localhost:$MV/" "http://localhost:$LG/history/"; do echo "$u $(curl -s -o /dev/null -m 5 -w '%{http_code}' "$u")"; done
echo "connect 127.0.0.1:$PORT | stop: docker stop $NAME"

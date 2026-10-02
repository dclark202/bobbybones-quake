#!/bin/bash
# Start N training BobbyBones servers (private, not published), each playing real 10-minute duels
# against rotating Nightmare bots on Blood Run. Trainer 1 also aggregates everyone's experience.
#   tools/train_cluster.sh start 12     tools/train_cluster.sh stop     tools/train_cluster.sh status
set -e
N=${2:-12}
CONTROLS=${3:-0}            # the last CONTROLS trainers run the plain built-in bot (control group)
ROOT="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
case "$1" in
  start)
    mkdir -p "data/train/shared"
    [ -f data/practice/weapon_policy.json ] && cp data/practice/weapon_policy.json data/train/seed_weapon_policy.json
    for i in $(seq 1 "$N"); do
      docker ps -a --format '{{.Names}}' | grep -qx "qltrain$i" && continue   # already running
      mkdir -p "data/train/c$i"
      AGG=0; [ "$i" = "1" ] && AGG=1
      CTRL=0; [ "$i" -gt $((N - CONTROLS)) ] && CTRL=1
      VAR=$(echo "${SPLIT:-}" | cut -d, -f$i); [ -z "$VAR" ] && VAR=${VARIANT:-full}   # SPLIT = per-trainer variant list
      BOTMOUNT=""
      if [ "$CTRL" = "0" ] && [ -n "$TUNE" ]; then        # tuned bot files for BobbyBones (not the control group)
          mkdir -p "data/train/c$i/botfiles/bots"
          BOTMOUNT="-v $ROOT/data/train/c$i/botfiles:/ql/home/baseq3/botfiles"
      fi
      MSYS_NO_PATHCONV=1 docker run -d --name "qltrain$i" --restart unless-stopped \
        -e LAB_MODE=train -e TRAIN_AGGREGATOR=$AGG -e LAB_OPPONENT_START=$((i - 1)) \
        -e TRAIN_DEADLINE="${TRAIN_DEADLINE:-0}" -e TRAIN_SINCE="${TRAIN_SINCE:-0}" -e LAB_CONTROL=$CTRL -e LAB_SPAR="${LAB_SPAR:-0}" -e LAB_VARIANT=$VAR \
        -v "$ROOT/data/train/c$i:/tmp/practice" -v "$ROOT/data/train:/tmp/train" $BOTMOUNT \
        qlbot +set sv_master 0 +set sv_serverType 0 +set sv_hostname "bobby-train-$i" >/dev/null
      echo "started qltrain$i"
    done ;;
  coach)
    MSYS_NO_PATHCONV=1 docker run -d --name qlcoach --restart unless-stopped -v "$ROOT/data/train:/tmp/train" \
        --entrypoint python3 qlbot /tools/tune_coach.py "$N" >/dev/null && echo "coach started for $N trainers" ;;
  stop)
    docker ps -a --format '{{.Names}}' | grep -E '^(qltrain|qlcoach)' | xargs -r docker rm -f ;;
  status)
    docker ps --format '{{.Names}} {{.Status}}' | grep '^qltrain' || true
    [ -f data/train/shared/report.txt ] && cat data/train/shared/report.txt ;;
esac

#!/bin/bash
# Start N training BobbyBones servers (private, not published), each playing real 10-minute duels
# against rotating Nightmare bots on Blood Run. Trainer 1 also aggregates everyone's experience.
#   tools/train_cluster.sh start 12     tools/train_cluster.sh stop     tools/train_cluster.sh status
set -e
N=${2:-12}
ROOT="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
case "$1" in
  start)
    mkdir -p "data/train/shared"
    [ -f data/practice/weapon_policy.json ] && cp data/practice/weapon_policy.json data/train/seed_weapon_policy.json
    for i in $(seq 1 "$N"); do
      docker ps -a --format '{{.Names}}' | grep -qx "qltrain$i" && continue   # already running
      mkdir -p "data/train/c$i"
      AGG=0; [ "$i" = "1" ] && AGG=1
      MSYS_NO_PATHCONV=1 docker run -d --name "qltrain$i" --restart unless-stopped \
        -e LAB_MODE=train -e TRAIN_AGGREGATOR=$AGG -e LAB_OPPONENT_START=$((i - 1)) \
        -v "$ROOT/data/train/c$i:/tmp/practice" -v "$ROOT/data/train:/tmp/train" \
        qlbot +set sv_master 0 +set sv_serverType 0 +set sv_hostname "bobby-train-$i" >/dev/null
      echo "started qltrain$i"
    done ;;
  stop)
    docker ps -a --format '{{.Names}}' | grep '^qltrain' | xargs -r docker rm -f ;;
  status)
    docker ps --format '{{.Names}} {{.Status}}' | grep '^qltrain' || true
    [ -f data/train/shared/report.txt ] && cat data/train/shared/report.txt ;;
esac

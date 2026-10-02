#!/bin/bash
# After an overnight training run: final aggregation, stop the trainers, and move what they learned onto
# the public BobbyBones (routes incl. pruned failures, movement styles per trip, weapon table).
# The public server keeps learning from humans on top of the promoted knowledge (see tools/learner.sh).
#   bash tools/promote_training.sh            (run from the repo root)
set -e
export MSYS_NO_PATHCONV=1
ROOT="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
MAP=${LAB_MAP:-bloodrun}

echo "== final aggregation"
docker exec qltrain1 sh -c "LAB_MAP=$MAP python3 /tools/train_aggregate.py" > data/train/shared/final_report.txt 2>&1 || true
cat data/train/shared/final_report.txt

echo "== stopping trainers"
bash tools/train_cluster.sh stop >/dev/null || true

echo "== promoting to the public server"
mkdir -p data/practice/promoted
for f in nav_$MAP.json weapon_policy.json movement_policy.json decision_policy.json route_policy.json banned_moves_pruned.txt; do
    [ -f "data/train/shared/$f" ] && cp "data/train/shared/$f" "data/practice/promoted/$f"
done
cp data/practice/promoted/nav_$MAP.json "data/practice/nav_$MAP.json"
cp data/practice/promoted/weapon_policy.json data/practice/weapon_policy.json
cp data/practice/promoted/movement_policy.json data/practice/movement_policy.json
[ -f data/practice/promoted/decision_policy.json ] && cp data/practice/promoted/decision_policy.json data/practice/decision_policy.json
date -u > data/practice/promoted/promoted_at.txt

echo "== restarting the public server on the current image"
docker build -q -t qlbot . >/dev/null
docker rm -f ql >/dev/null 2>&1 || true
docker run -d --name ql --restart unless-stopped -p 27970:27970/udp \
    -v "$ROOT/data/practice:/tmp/practice" qlbot +set net_port 27970 >/dev/null
echo "public BobbyBones restarted with promoted knowledge"

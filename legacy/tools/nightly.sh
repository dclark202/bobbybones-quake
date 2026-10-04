#!/bin/bash
# Nightly training run from tools/nightly.conf.
#   bash tools/nightly.sh start     stop any cluster, start TRAINERS (staggered) + the coach until END_HOUR
#   bash tools/nightly.sh stop      final aggregation, stop the cluster, archive everything to data/runs/<run>/
# The public server (container ql) is never touched.
set -e
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
. tools/nightly.conf

case "$1" in
  start)
    today=$(date +%F)
    if [[ "$today" < "$FIRST_NIGHT" || "$today" > "$LAST_NIGHT" ]]; then
        echo "$today is outside $FIRST_NIGHT..$LAST_NIGHT - not starting"; exit 0
    fi
    bash tools/train_cluster.sh stop >/dev/null 2>&1 || true
    since=$(date +%s)
    deadline=$(date -d "tomorrow $(printf %02d "$END_HOUR"):00" +%s)
    [ "$(date +%H)" -lt "$END_HOUR" ] && deadline=$(date -d "today $(printf %02d "$END_HOUR"):00" +%s)
    run="$(date +%F)"
    mkdir -p "data/runs/$run"
    cp tools/nightly.conf "data/runs/$run/nightly.conf"
    echo "$since" > data/train/since.txt
    echo "$deadline" > data/train/deadline.txt
    echo "$run" > data/train/run.txt
    for i in $(seq 1 "$TRAINERS"); do
        mkdir -p "data/train/c$i"
        rm -f "data/train/c$i/restart.flag" "data/train/c$i/candidate.json"
    done
    for i in $(seq $((TRAINERS - CONTROLS + 1)) "$TRAINERS"); do rm -rf "data/train/c$i/botfiles"; done
    docker build -q -t qlbot . >/dev/null
    echo "$(date) nightly start $run: $TRAINERS trainers ($CONTROLS controls), pop $POP, maps $MAPS, groups $COACH_GROUPS" \
        | tee -a data/train/ramp.log "data/runs/$run/run.log"
    TUNE=1 VARIANT=$VARIANT LAB_SPAR=1 TRAIN_DEADLINE=$deadline TRAIN_SINCE=$since MAPS=$MAPS POP=$POP BATCH=$BATCH GAP=$GAP \
        bash tools/train_cluster.sh start "$TRAINERS" "$CONTROLS" >/dev/null
    docker rm -f qlcoach >/dev/null 2>&1 || true
    MSYS_NO_PATHCONV=1 docker run -d --name qlcoach --restart unless-stopped \
        -e COACH_BATCH=$BATCH -e COACH_GAP=$GAP -e COACH_GROUPS=$COACH_GROUPS \
        -v "$(pwd -W 2>/dev/null || pwd)/data/train:/tmp/train" \
        --entrypoint python3 qlbot /tools/tune_coach.py $((TRAINERS - CONTROLS)) "$POP" >/dev/null
    echo "$(date) cluster and coach up" | tee -a "data/runs/$run/run.log" ;;
  stop)
    run=$(cat data/train/run.txt 2>/dev/null || date -d yesterday +%F)
    out="data/runs/$run"
    mkdir -p "$out"
    for m in ${MAPS//,/ }; do                                    # final report per map
        docker exec qltrain1 sh -c "LAB_MAP=$m python3 /tools/train_aggregate.py" > "$out/final_report_$m.txt" 2>&1 || true
    done
    bash tools/train_cluster.sh stop >/dev/null 2>&1 || true
    cp -r data/train/shared data/train/tune "$out/" 2>/dev/null || true
    cp data/train/since.txt data/train/deadline.txt data/train/ramp.log "$out/" 2>/dev/null || true
    # everything each trainer logged (results, trips, legs, experience, recordings, server/lab logs, candidates)
    tar --exclude='botfiles' -czf "$out/trainers.tgz" -C data/train $(cd data/train && ls -d c[0-9]* 2>/dev/null)
    # recordings and server logs are now in the archive: start the next night small
    rm -f data/train/c*/trace_live_*.txt data/train/c*/server.log
    du -sh "$out" | tee -a "$out/run.log"
    echo "$(date) nightly stop $run: archived" | tee -a "$out/run.log" ;;
  *)
    echo "usage: $0 start|stop"; exit 1 ;;
esac

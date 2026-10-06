#!/bin/bash
# One check of a run on arena1: training numbers (with the map-knowledge ones), five minutes against Nightmare on the
# map, the reflex test against the benchmark, and (VIDEO=1) a fight video.   bash tools/hourly_arena1.sh <run>
cd "$(dirname "$0")/.."
RUN="${1:-duel_gru_v6}"
PY="${PYTHON:-python}"
date +%H:%M
python tools/arena_report.py "$RUN" | tail -5
PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard 5 arena1 duel_env_ffa 2>&1 | tail -1
"$PY" tools/reflex_report.py --last --bobby "$RUN" 2>&1 | grep -v "shot after\|size of\|fastest\|aims \|own speed\|jitter\|^runs\|Slow target" | cut -c1-132
if [ -n "$VIDEO" ]; then
  ARENA_SETS=mg ARENA_STACK=0 "$PY" sim/render_course.py --run "$RUN" --env duel_env_ffa --map arena1 --fight yard --secs 90 --round 90 2>&1 | grep "^fight\|Error" | cut -c1-220
fi
tasklist | grep -ci python

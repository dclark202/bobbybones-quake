#!/bin/bash
# One check of a run on arena1: training numbers (with the map-knowledge ones), ten minutes against Nightmare on the
# map, the reflex test against the benchmark, and (VIDEO=1) a fight video.   bash tools/hourly_arena1.sh <run>
cd "$(dirname "$0")/.."
RUN="${1:-duel_gru_v6}"
PY="${PYTHON:-python}"
date +%H:%M
python tools/arena_report.py "$RUN" | tail -5
tail -1 "data/sim_runs/$RUN/metrics.jsonl" | python -c "import sys,json; r=json.loads(sys.stdin.read()); print('   intent', r.get('intent'))"
PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${BENCH_MIN:-10}" arena1 duel_env_ffa 2>&1 | tail -1
# two duel maps beside arena1 (owner, 2026-10-07: three maps in all): five minutes against Nightmare on each, side by side; DUEL_MAPS="..." for others
if [ -n "${DUEL_MAPS-bloodrun aerowalk}" ]; then
  set -- ${DUEL_MAPS-bloodrun aerowalk}
  while [ $# -gt 0 ]; do
    BENCH_NAME=qlbench1 BENCH_DATA=data/bench1 PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${DUEL_MIN:-5}" "$1" duel_env_ffa 2>&1 | tail -1 &
    if [ -n "$2" ]; then
      BENCH_NAME=qlbench2 BENCH_DATA=data/bench2 PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${DUEL_MIN:-5}" "$2" duel_env_ffa 2>&1 | tail -1 &
    fi
    wait
    shift; [ $# -gt 0 ] && shift
  done
fi
"$PY" tools/reflex_report.py --last --bobby "$RUN" 2>&1 | grep -v "shot after\|size of\|fastest\|aims \|own speed\|jitter\|^runs\|Slow target" | cut -c1-132
# a video every other hour (the odd ones), 30 seconds on arena1 (owner, 2026-10-07: rendering takes long); FORCE_VIDEO=1 forces one, NOVIDEO=1 none; the loops' older VIDEO flag is ignored
if [ -z "$NOVIDEO" ] && { [ -n "$FORCE_VIDEO" ] || [ $(( 10#$(date +%H) % 2 )) -eq 1 ]; }; then
  ARENA_SETS="mg;rl;rg;lg;rl,rg;rl,lg;rg,lg;rl,rg,lg" ARENA_STACK=0 "$PY" sim/render_course.py --run "$RUN" --env duel_env_ffa --group "${VGROUP:-2}" --map arena1 --fight yard --secs "${VIDEO_SECS:-30}" --round "${VIDEO_SECS:-30}" --width 640 2>&1 | grep "^fight\|Error" | cut -c1-220
fi
"$PY" tools/heatmap.py --run "$RUN" --group 3 --minutes 4 2>&1 | grep -v "^  [0-9] min" | cut -c1-160
tasklist | grep -ci python

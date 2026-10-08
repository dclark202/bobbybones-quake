#!/bin/bash
# One check of a run on arena1: training numbers (with the map-knowledge ones), ten minutes against Nightmare on the
# map, the reflex test against the benchmark, and (VIDEO=1) a fight video.   bash tools/hourly_arena1.sh <run>
cd "$(dirname "$0")/.."
RUN="${1:-duel_gru_v6}"
PY="${PYTHON:-python}"
ENVMOD="${ENVMOD:-duel_env_ffa}"   # the simulator module the run was trained in (a frozen copy for older runs: duel_env_ffa_v12, with REFLEX_ENV=duel_env_v12)
date +%H:%M
python tools/arena_report.py "$RUN" | tail -5
tail -1 "data/sim_runs/$RUN/metrics.jsonl" | python -c "import sys,json; r=json.loads(sys.stdin.read()); print('   intent', r.get('intent'))"
# the measured part (Nightmare on three maps, the reflex test, the heat map, the video) every other hour, at the odd ones
# (owner, 2026-10-07); the even hours print the training numbers only. FULL=1 forces it.
if [ -z "$FULL" ] && [ $(( 10#$(date +%H) % 2 )) -eq 0 ]; then echo "(training numbers only this hour)"; exit 0; fi
PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${BENCH_MIN:-10}" arena1 "$ENVMOD" 2>&1 | tail -1
# two duel maps beside arena1 (owner, 2026-10-07: three maps in all): five minutes against Nightmare on each, side by side; DUEL_MAPS="..." for others
if [ -n "${DUEL_MAPS-bloodrun aerowalk}" ]; then
  set -- ${DUEL_MAPS-bloodrun aerowalk}
  while [ $# -gt 0 ]; do
    BENCH_NAME=qlbench1 BENCH_DATA=data/bench1 PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${DUEL_MIN:-5}" "$1" "$ENVMOD" 2>&1 | tail -1 &
    if [ -n "$2" ]; then
      BENCH_NAME=qlbench2 BENCH_DATA=data/bench2 PYTHON="$PY" bash tools/bench_arena.sh "$RUN" yard "${DUEL_MIN:-5}" "$2" "$ENVMOD" 2>&1 | tail -1 &
    fi
    wait
    shift; [ $# -gt 0 ] && shift
  done
fi
"$PY" tools/reflex_report.py --last --bobby "$RUN" 2>&1 | grep -v "shot after\|size of\|fastest\|aims \|own speed\|jitter\|^runs\|Slow target" | cut -c1-132
# a video every other hour (the odd ones), 30 seconds on arena1 (owner, 2026-10-07: rendering takes long); FORCE_VIDEO=1 forces one, NOVIDEO=1 none; the loops' older VIDEO flag is ignored
if [ -z "$NOVIDEO" ] && { [ -n "$FORCE_VIDEO" ] || [ $(( 10#$(date +%H) % 2 )) -eq 1 ]; }; then
  ARENA_SETS="mg;rl;rg;lg;rl,rg;rl,lg;rg,lg;rl,rg,lg" ARENA_STACK=0 "$PY" sim/render_course.py --run "$RUN" --env "$ENVMOD" --group "${VGROUP:-2}" --map arena1 --fight yard --secs "${VIDEO_SECS:-30}" --round "${VIDEO_SECS:-30}" --width 640 2>&1 | grep "^fight\|Error" | cut -c1-220
fi
# alone on the map, does he go and get the item he is told to (RESULTS 2026-10-07 09:15: 0 to 29% of the rounds)
"$PY" tools/solo_item_check.py --run "$RUN" --env "$ENVMOD" --map arena1 --rounds 2 2>&1 | tail -7 | cut -c1-150
"$PY" tools/heatmap.py --run "$RUN" --env "$ENVMOD" --group 3 --minutes 4 2>&1 | grep -v "^  [0-9] min" | cut -c1-160
tasklist | grep -ci python

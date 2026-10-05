#!/bin/bash
# One hourly check of an arena run: training numbers, five minutes against Nightmare in the environment box,
# the dodge check, and a fight video.   bash tools/hourly_arena.sh <run>
cd "$(dirname "$0")/.."
RUN="${1:-duel_gru_v5}"
date +%H:%M
python tools/arena_report.py "$RUN" | tail -8
PYTHON="${PYTHON:-python}" bash tools/bench_arena.sh "$RUN" env 5 2>&1 | tail -1
"${PYTHON:-python}" tools/dodge_check.py "$RUN" 2>&1 | grep "^DODGE"
ARENA_SETS="${ARENA_SETS-rl;rl,lg;rl,rg;rl,rg,lg}" "${PYTHON:-python}" sim/render_course.py --run "$RUN" --fight env --secs 60 --round 20 2>&1 | grep "^fight\|Error" | cut -c1-200
ARENA_SETS="${ARENA_SETS-rl;rl,lg;rl,rg;rl,rg,lg}" "${PYTHON:-python}" tools/weapon_use.py "$RUN" 2>&1 | grep "^WEAPONS"

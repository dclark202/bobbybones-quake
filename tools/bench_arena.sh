#!/bin/bash
# Benchmark a run's current checkpoint against the game's Nightmare bot in an arena of the test map, under the
# rules of !arena (full weapons at spawn, nobody leaves the room).   bash tools/bench_arena.sh <run> [env|box] [minutes=5]
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MSYS_NO_PATHCONV=1
RUN="$1"; WHERE="${2:-env}"; MINS="${3:-5}"
docker rm -f qltest >/dev/null 2>&1
TAG=$(NAME=qltest DATA=data/labtest SPAR=1 SKILL=5 ARENA="$WHERE" ARENA_MIN="$MINS" PYTHON="${PYTHON:-python}" bash tools/duel_server.sh "$RUN" bobbylab duel_env 2>&1 | grep -o "minutes [0-9]*")
sleep 45
S=$(ls -d data/labtest/sessions/* | tail -1)
for i in $(seq 1 $(( MINS * 6 + 30 ))); do
  grep -q "arena_result" "$S/events.jsonl" 2>/dev/null && break
  sleep 10
  S=$(ls -d data/labtest/sessions/* | tail -1)
done
python - "$S" "$TAG" "$WHERE" <<'PY'
import sys, csv, json, collections
import numpy as np
s, tag, where = sys.argv[1:4]
res = [json.loads(l) for l in open(s + "/events.jsonl", encoding="utf-8", errors="replace") if '"arena_result"' in l]
r = list(csv.DictReader(open(s + "/frames.csv")))
g = lambda k: np.array([float(x[k] or 0) for x in r])
n = {"1": "g", "2": "mg", "3": "sg", "4": "gl", "5": "rl", "6": "lg", "7": "rg", "8": "pg", "14": "hmg", "0": "dead"}
c = collections.Counter(n.get(x["b_weapon"], x["b_weapon"]) for x in r)
see = g("b_sees") > 0
a = res[-1] if res else dict(bobby="?", opp="?", dmg_dealt=0, dmg_taken=0, minutes=0)
print("ARENA {} | {} box, {:g} min vs Nightmare | score {}-{} | dmg {}/{} | speed {:.0f} | in view {:.0%} | aim error in view {:.1f} | held {}".format(
    tag, where, a["minutes"], a["bobby"], a["opp"], a["dmg_dealt"], a["dmg_taken"], np.hypot(g("b_vx"), g("b_vy")).mean(), see.mean(),
    g("b_aim_err")[see].mean() if see.any() else -1, {k: round(v / len(r), 2) for k, v in c.most_common(4)}))
PY
docker rm -f qltest >/dev/null 2>&1

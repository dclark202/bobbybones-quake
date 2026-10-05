#!/bin/bash
# Benchmark the current checkpoint of a run against the game's Nightmare bot on a second, private server.
#   bash tools/bench_nightmare.sh <run> [minutes=10] [map=bloodrun]
# Prints one line: training minutes, score, damage dealt / taken, mean speed, enemy in view, weapons held.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MSYS_NO_PATHCONV=1
RUN="$1"; MINS="${2:-10}"; MAP="${3:-bloodrun}"
docker rm -f qltest >/dev/null 2>&1
OUT=$(NAME=qltest DATA=data/labtest SPAR=1 SKILL=5 PYTHON="${PYTHON:-python}" bash tools/duel_server.sh "$RUN" "$MAP" duel_env 2>&1 | grep -o "minutes [0-9]*")
sleep 60
S=$(ls -d data/labtest/sessions/* | tail -1)
for i in $(seq 1 120); do
  [ "$(grep -c '"minute"' "$S/events.jsonl" 2>/dev/null)" -ge "$MINS" ] && break
  sleep 10
  S=$(ls -d data/labtest/sessions/* | tail -1)
done
python - "$S" "$MINS" "$OUT" <<'EOF'
import sys, csv, json, collections
import numpy as np
s, mins, tag = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ev = [json.loads(l) for l in open(s + "/events.jsonl", encoding="utf-8", errors="replace") if l.strip()]
m = [e for e in ev if e.get("event") == "minute"][:mins]
r = list(csv.DictReader(open(s + "/frames.csv")))
g = lambda k: np.array([float(x[k] or 0) for x in r])
sp = np.hypot(g("b_vx"), g("b_vy"))
n = {"1": "g", "2": "mg", "3": "sg", "4": "gl", "5": "rl", "6": "lg", "7": "rg", "8": "pg", "14": "hmg", "0": "dead"}
c = collections.Counter(n.get(x["b_weapon"], x["b_weapon"]) for x in r)
last = m[-1] if m else dict(bobby=0, opp=0, dmg_dealt=0, dmg_taken=0)
print("BENCH {} | {} min vs Nightmare | score {}-{} | dmg {}/{} | speed mean {:.0f} | in view {:.0%} | held {}".format(
    tag, len(m), last["bobby"], last["opp"], last["dmg_dealt"], last["dmg_taken"], sp.mean(), g("b_sees").mean(),
    {k: round(v / len(r), 2) for k, v in c.most_common(4)}))
EOF
docker rm -f qltest >/dev/null 2>&1

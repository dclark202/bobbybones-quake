#!/bin/bash
# Benchmark a run's current checkpoint against the game's Nightmare bot in an arena of the test map, under the
# rules of !arena (full weapons at spawn, nobody leaves the room), or on arena1 (the whole map, duel spawn, items).
#   bash tools/bench_arena.sh <run> [env|box|yard] [minutes=5] [map=testlab] [simulator module=duel_env]
#   bash tools/bench_arena.sh duel_gru_v6 yard 5 arena1 duel_env_ffa
# BENCH_NAME / BENCH_DATA (default qltest, data/labtest): another container and data folder, for games side by side.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MSYS_NO_PATHCONV=1
RUN="$1"; WHERE="${2:-env}"; MINS="${3:-5}"; MAP="${4:-testlab}"; ENVMOD="${5:-duel_env}"
BN="${BENCH_NAME:-qltest}"; BD="${BENCH_DATA:-data/labtest}"
mkdir -p "$BD/sessions"
docker rm -f "$BN" >/dev/null 2>&1
OLD=$(ls -d "$BD"/sessions/* 2>/dev/null | tail -1)      # a result must come from a session made by this game, not the last one
TAG=$(NAME="$BN" DATA="$BD" SPAR=1 SKILL=5 ARENA="$WHERE" ARENA_MIN="$MINS" PYTHON="${PYTHON:-python}" bash tools/duel_server.sh "$RUN" "$MAP" "$ENVMOD" 2>&1 | grep -o "minutes [0-9]*")
sleep 45
S=$(ls -d "$BD"/sessions/* | tail -1)
for i in $(seq 1 $(( MINS * 6 + 30 ))); do
  [ "$S" != "$OLD" ] && grep -q "arena_result" "$S/events.jsonl" 2>/dev/null && break
  sleep 10
  S=$(ls -d "$BD"/sessions/* | tail -1)
done
[ "$S" = "$OLD" ] && { echo "ARENA $TAG | $MAP: no game was played (the server made no session)"; docker rm -f "$BN" >/dev/null 2>&1; exit 1; }
python - "$S" "$TAG" "$MAP" <<'PY'
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
docker rm -f "$BN" >/dev/null 2>&1

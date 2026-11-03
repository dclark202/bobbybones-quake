"""The pros' games as the judge's rows (owner, 2026-10-29: the judge partly fitted on the pro demos, so that what a weapon
is worth comes from games played by people who know how to use it): every pro demo of a map that holds its game to 10:00,
one row a second (the score, both players' health, armor, dead and big weapons owned; the followed player's exact, the
other's worked out by tools/pro_moments.py from his pickups, the hits on him and his pain sounds), the result = the score
at 10:00 (no overtime in these demos: level is a draw). Two recordings of one game are kept once (the score and the deaths'
times on the game's clock). Written as tools/run/selfplay_log.py's rows (<out>/<map>/rows_<map>.json), so that
tools/run/fit_b.py reads them as it reads his games. No names: a demo is a number.

    python tools/run/pro_judge_rows.py --map bloodrun [--demos 0 (all)] [--old 0] [--out data/sim_runs/judge/pro_rows]
    (one map a process: one simulator World a process; low priority)"""
import argparse
import glob
import json
import os
import sys
import tempfile
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pro_moments as PM                                     # noqa: E402  (sets its own switches before the simulator loads)
import numpy as np                                           # noqa: E402

COLS = ["seed", "match", "t", "my_score", "op_score", "my_hp", "my_ar", "op_hp", "op_ar", "my_dead", "op_dead",
        "my_rl", "my_lg", "my_rg", "op_rl", "op_lg", "op_rg", "v_raw", "frags_d"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--demos", type=int, default=0, help="at most this many demos of today's format (0: all)")
    ap.add_argument("--old", type=int, default=0, help="also up to this many of the old format (.dm_73)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sim_runs", "judge", "pro_rows"))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    PM.low_priority()
    rng = np.random.default_rng(a.seed)
    dd = os.path.join(PM.demo_root(), "demos", a.map)
    new = sorted(glob.glob(os.path.join(dd, "*.dm_91"))) + sorted(glob.glob(os.path.join(dd, "*.dm_90")))
    pick = list(rng.permutation(new))
    if a.demos:
        pick = pick[:a.demos]
    if a.old:
        pick += list(rng.permutation(sorted(glob.glob(os.path.join(dd, "*.dm_73")))))[:a.old]
    MI = PM.MapInfo(a.map)
    counts = Counter()
    tmp = tempfile.mkdtemp(prefix="pjr_")
    games, seen = [], set()
    t0 = time.time()
    for nd, demo in enumerate(pick):
        j = {}
        try:
            PM.one_demo(MI, demo, tmp, 4.0, 2.0, rng, counts, judge=j)
        except Exception as e:                               # noqa: BLE001 (a broken demo must not stop the map)
            counts["error"] += 1
            print("error", nd, repr(e)[:160], flush=True)
        counts["demos"] += 1
        if j.get("rows"):
            if j["sig"] in seen:
                counts["judge: a second recording of a game"] += 1
            else:
                seen.add(j["sig"])
                games.append(j)
        if nd % 10 == 0:
            print("{} {}/{} games {} {:.0f}s".format(a.map, nd + 1, len(pick), len(games), time.time() - t0), flush=True)
    rows, seeds, final = [], [], []
    for g, j in enumerate(games):
        for r in j["rows"]:
            rows.append([float(g)] + [float(x) for x in r[1:]])
        seeds.append(g)
        final.append([list(j["final"])])
    od = os.path.join(a.out, a.map)
    os.makedirs(od, exist_ok=True)
    json.dump(dict(map=a.map, cols=COLS, rows=rows, final=final, seeds=seeds, source="pro demos", counts=dict(counts),
                   demos=len(pick), games=len(games), seconds=round(time.time() - t0)), open(os.path.join(od, "rows_{}.json".format(a.map)), "w"))
    res = Counter("level" if f[0][0] == f[0][1] else "decided" for f in final)
    print(json.dumps(dict(map=a.map, demos=len(pick), games=len(games), results=dict(res), counts=dict(counts),
                          seconds=round(time.time() - t0)), indent=1), flush=True)


if __name__ == "__main__":
    main()

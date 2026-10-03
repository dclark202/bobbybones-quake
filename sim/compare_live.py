"""Compare live Quake Live trip times (plugins/movetest.py) with the simulator eval and Nightmare's real trips.

    python sim/compare_live.py --live data/movetest/movetest.jsonl --run bloodrun_human_v1
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from eval_move import nightmare_baselines  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--live", default=os.path.join(ROOT, "data", "movetest", "movetest.jsonl"))
ap.add_argument("--run", default="bloodrun_human_v1")
ap.add_argument("--map", default="bloodrun")
a = ap.parse_args()
live = [json.loads(l) for l in open(a.live)]
ev = os.path.join(ROOT, "data", "sim_runs", a.run, "eval_{}.json".format(a.map))
if not os.path.exists(ev):
    ev = os.path.join(ROOT, "data", "sim_runs", a.run, "eval.json")
sim = {t["trip"]: t for t in json.load(open(ev))["trips"]}
nm = nightmare_baselines(a.map)
for mode in ("human", "bot"):
    rs = [r for r in live if r["mode"] == mode]
    if not rs:
        continue
    arrived = [r for r in rs if r["arrived"]]
    ratios, vs_nm, rows = [], [], []
    for r in arrived:
        s = sim.get(r["trip"], {}).get("policy_median")
        x, y = r["trip"].split(">")
        n = nm.get((x, y))
        if s:
            ratios.append(r["secs"] / s)
        if n:
            vs_nm.append(r["secs"] < n[0])
            rows.append((r["trip"], r["secs"], s, n[0], n[1]))
    print("== {} physics: {}/{} trips arrived, median vmax {:.0f}, fast airborne {:.0%} of moving time".format(
        mode, len(arrived), len(rs), np.median([r["vmax"] for r in rs]), np.mean([r["fast_air"] for r in rs])))
    if ratios:
        print("   live / simulator time: median {:.2f} (1.00 = identical), p10 {:.2f}, p90 {:.2f}".format(
            np.median(ratios), np.percentile(ratios, 10), np.percentile(ratios, 90)))
    if vs_nm:
        print("   faster than Nightmare's real median on {}/{} trips".format(sum(vs_nm), len(vs_nm)))
    if mode == "human":
        print("   {:8} {:>6} {:>6} {:>10}".format("trip", "live", "sim", "Nightmare"))
        for t, l, s, n, k in sorted(rows, key=lambda r: -r[4])[:12]:
            print("   {:8} {:5.2f}s {:5.2f}s {:6.2f}s (n={})".format(t, l, s or float("nan"), n, k))

"""(brainppl) the domain-leak check: can one input column alone tell a rebuilt frame (a server session, a pro demo) from a
simulator frame? Per column the AUC of the column's value between the two sets (symmetric: max(AUC, 1 - AUC)), on frames
of the brain's lesson (trk_on), the same maps on both sides, an even number of frames per map.

    python tools/brainppl_leak.py [--n 2000] [--thr 0.65] [--out <json>]

Columns above --thr are listed (docs/INPUTS.csv names): a 256-unit GRU would learn "this is not the simulator" from them.
"""
import argparse
import csv
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "sim_runs", "brainppl", "data")


def auc(a, b):
    """AUC of a against b (average ranks for ties) -> [columns]"""
    x = np.concatenate([a, b], 0)
    n1, n0 = len(a), len(b)
    out = np.zeros(x.shape[1])
    for j in range(x.shape[1]):
        u, inv, cnt = np.unique(x[:, j], return_inverse=True, return_counts=True)
        r = np.cumsum(cnt) - (cnt - 1) / 2.0
        rk = r[inv]
        out[j] = (rk[:n1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return np.maximum(out, 1 - out)


def sample(files, n, rng, stream_axis):
    """trk_on frames of these shards, about n in all, spread over the files"""
    rows, maps = [], []
    per = max(1, n // max(1, len(files)))
    for f in files:
        try:
            z = np.load(f)
            m = json.loads(str(z["meta"]))
        except Exception:                                    # noqa: BLE001
            continue
        C = {k: i for i, k in enumerate(m["cols"])}
        ob, ax = z["obs"], z["aux"]
        if stream_axis:
            S = ob.shape[1]
            for s in range(S):
                on = np.nonzero(ax[:-1, s, C["trk_on"]] > 0.5)[0]
                if len(on):
                    k = rng.choice(on, min(len(on), max(1, per // S)), replace=False)
                    rows.append(ob[k, s].astype(np.float32))
                    maps += [m["map"]] * len(k)
        else:
            on = np.nonzero(ax[:-1, 0, C["trk_on"]] > 0.5)[0]
            if len(on):
                k = rng.choice(on, min(len(on), per), replace=False)
                rows.append(ob[k, 0].astype(np.float32))
                maps += [m["map"]] * len(k)
    return (np.concatenate(rows) if rows else np.zeros((0, 868), np.float32)), np.array(maps)


def matched(a, ma, b, mb, rng):
    """the same maps, as many frames of each map on both sides"""
    ia, ib = [], []
    for mp in sorted(set(ma) & set(mb)):
        xa, xb = np.nonzero(ma == mp)[0], np.nonzero(mb == mp)[0]
        k = min(len(xa), len(xb))
        ia += list(rng.choice(xa, k, replace=False))
        ib += list(rng.choice(xb, k, replace=False))
    return a[ia], b[ib]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--thr", type=float, default=0.65)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "leak.json"))
    a = ap.parse_args()
    rng = np.random.default_rng(5)
    names = [r["group"] + ": " + r["input"] for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    sim, ms = sample(sorted(glob.glob(os.path.join(D, "sim", "sim_*.npz"))), 4 * a.n, rng, True)
    rep = {}
    for k, pat in (("session", "ppl/ppl_*.npz"), ("demo", "demo/demo_*.npz")):
        fs = sorted(glob.glob(os.path.join(D, pat)))
        if not fs:
            continue
        x, mx = sample(fs[:: max(1, len(fs) // 60)], a.n, rng, False)
        xa, xb = matched(x, mx, sim, ms, rng)
        if len(xa) < 200:
            continue
        au = auc(xa, xb)
        bad = [(int(j), names[j], round(float(au[j]), 3), round(float(xa[:, j].mean()), 3), round(float(xb[:, j].mean()), 3))
               for j in np.argsort(-au) if au[j] > a.thr]
        rep[k] = dict(frames=int(len(xa)), over=len(bad), cols=bad, auc_all=[round(float(v), 3) for v in au])
        print("== {} vs simulator: {} frames a side; {} columns over {}".format(k, len(xa), len(bad), a.thr))
        for j, nm, v, ma_, mb_ in bad[:60]:
            print("  {:4d} {:60s} AUC {:.3f}  mean {} vs sim {}".format(j, nm[:60], v, ma_, mb_))
    json.dump(rep, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()

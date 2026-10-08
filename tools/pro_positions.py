"""Where the pros stand, per duel map: their time per cell of 32 units (top view) over every converted demo, in all,
without a big weapon, and with one. For the scorecard (tools/stack_probe.py: his overlap with them) and, later, a mild
pull toward their ground (docs/PLAN.md, positioning).

    python tools/pro_positions.py --map bloodrun,aerowalk,lostworld        -> sim/pro_positions/<map>.npz

Reads the light demo sets (sim/demo_dataset.py --lite). The grid is the simulator's own for that map (its bounds), so a
probe's map of positions lies on the same cells. No player names are read or written.
"""
import argparse
import glob
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
CELL = 32


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def build(mp):
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=0,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    lo, hi = env.lo.copy(), env.hi.copy()
    dims = (np.ceil((hi[:2] - lo[:2]) / CELL).astype(int) + 1)
    H = {k: np.zeros((dims[1], dims[0]), np.float64) for k in ("all", "bare", "armed")}
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
    for f in files:
        try:
            q = np.load(f)["lite"]
        except Exception:                                       # noqa: BLE001
            continue
        alive = q[:, 0] > 0
        cx = np.clip(((q[:, 5] - lo[0]) / CELL).astype(int), 0, dims[0] - 1)
        cy = np.clip(((q[:, 6] - lo[1]) / CELL).astype(int), 0, dims[1] - 1)
        bare = (q[:, 12:15] > 0.5).sum(1) == 0
        for key, m in (("all", alive), ("bare", alive & bare), ("armed", alive & ~bare)):
            np.add.at(H[key], (cy[m], cx[m]), 1.0)
    out = os.path.join(ROOT, "sim", "pro_positions", mp + ".npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, lo=lo[:2], cell=CELL, **{"heat_" + k: v.astype(np.float32) for k, v in H.items()})
    tot = H["all"].sum()
    flat = np.sort(H["all"].ravel())[::-1]
    k50 = int(np.searchsorted(np.cumsum(flat), 0.5 * tot)) + 1
    print("{}: {} demos, {:.0f} minutes alive ({:.0%} without a big weapon); half of their time in {} cells of {} visited".format(
        mp, len(files), tot / 2400.0, H["bare"].sum() / max(1.0, tot), k50, int((H["all"] > 0).sum())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    a = ap.parse_args()
    for mp in a.map.split(","):
        build(mp)


if __name__ == "__main__":
    main()

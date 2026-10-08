"""The pros' ways to the items, for the walking teacher (docs/PLAN.md, seed S5): for each thing he can go for (the
simulator's route goals: mega, red armor, the big weapons, the yellow armors) the step the pros took next from each
place, counted over their trips that ended in picking it up.

    python tools/pro_routes.py --map bloodrun,aerowalk,lostworld        -> sim/pro_routes/<map>.npz

A trip = the up to ten seconds before a pickup in the light demo sets (sim/demo_dataset.py --lite), cut at a spawn or an
earlier pickup. Its positions are laid on the walking graph (the node he stands on); every change of node a -> b counts
for (goal, a). pro_next[goal, a] = the b most often taken, where at least MIN_TRIPS trips passed, the two nodes are a
walkable step apart, and following the steps from a arrives at the goal; elsewhere -1 (the simulator then takes the
shortest way). One process on purpose. No player names are read or written.
"""
import argparse
import glob
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
MIN_TRIPS = 20
STEP_MAX = 320.0                                               # a change of node farther than this is a teleporter or a gap in the demo (a jump across a gap is up to about 300)
NEAR = 120.0                                                   # a pickup counts for a goal when it happened this near to it


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def build(mp, limit):
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=0,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    R, labels = env.route, list(env.route_goal)
    goal_pos = np.array([env.item_pos[k] for k in env.route_item], np.float32)
    G, N = len(labels), len(R.nodes)
    kind = dict(RL=0, RG=1, LG=2, MH=3, RA=4, YA=5, YA2=5)       # the pickup kinds found in a demo
    by_kind = {k: [g for g, lab in enumerate(labels) if kind[lab] == k] for k in range(6)}
    count = {}                                                  # (goal, a) -> {b: n}
    trips = np.zeros(G, np.int64)
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
    if limit:
        files = files[::max(1, len(files) // limit)][:limit]
    for fi, f in enumerate(files):
        try:
            d = np.load(f)
            q, first = d["lite"], d["first"]
        except Exception:                                       # noqa: BLE001
            continue
        hp, ar, pos, owns = q[:, 0], q[:, 1], q[:, 5:8], q[:, 12:15] > 0.5
        alive = hp > 0
        same = ~first[1:] & alive[1:] & alive[:-1]
        ev = []
        for k in range(3):
            ev += [(int(t) + 1, k) for t in np.nonzero(same & owns[1:, k] & ~owns[:-1, k])[0]]
        dh, da = hp[1:] - hp[:-1], ar[1:] - ar[:-1]
        ev += [(int(t) + 1, 3) for t in np.nonzero(same & (dh >= 60))[0]]
        ev += [(int(t) + 1, 4) for t in np.nonzero(same & (da >= 75))[0]]
        ev += [(int(t) + 1, 5) for t in np.nonzero(same & (da >= 40) & (da < 75))[0]]
        ev.sort()
        starts = np.nonzero(first)[0]
        prev_t = 0
        for t, k in ev:
            gs = by_kind[k]
            t0 = max(t - 400, prev_t + 1, int(starts[np.searchsorted(starts, t, side="right") - 1]) if len(starts) else 0)
            prev_t = t
            if not gs or t - t0 < 20:
                continue
            dg = np.linalg.norm(goal_pos[gs] - pos[t], axis=1)
            if dg.min() > NEAR:
                continue
            g = gs[int(dg.argmin())]
            nodes = R.locate(pos[t0:t + 1])
            ch = np.nonzero(nodes[1:] != nodes[:-1])[0]
            trips[g] += 1
            for c in ch:
                a, b = int(nodes[c]), int(nodes[c + 1])
                dct = count.setdefault((g, a), {})
                dct[b] = dct.get(b, 0) + 1
        if fi % 200 == 0:
            print("  {} {}/{} demos, trips {}".format(mp, fi, len(files), dict(zip(labels, trips.tolist()))), flush=True)
    nxt = np.full((G, N), -1, np.int32)
    for (g, a), dct in count.items():
        if sum(dct.values()) < MIN_TRIPS:
            continue
        b = max(dct, key=dct.get)
        if np.linalg.norm(R.nodes[a] - R.nodes[b]) <= STEP_MAX:
            nxt[g, a] = b
    # keep only steps whose chain arrives: follow the pros' step where there is one, the shortest way elsewhere
    kept = np.zeros(G, np.int64)
    for g in range(G):
        nxt[g, R.T[g] < 1.0] = -1                               # the last second is the shortest way's (the pros wait and circle there)
        good = np.zeros(N, np.int8)                             # 0 unknown, 1 arrives, -1 does not
        for a0 in np.nonzero(nxt[g] >= 0)[0]:
            path, a = [], int(a0)
            while True:
                if good[a]:
                    res = good[a]
                    break
                if R.T[g, a] < 1.0:
                    res = 1
                    break
                if a in path or len(path) > 400:
                    res = -1
                    break
                path.append(a)
                b = int(nxt[g, a]) if nxt[g, a] >= 0 else int(R.next[g, a])
                if b < 0:                                       # the shortest way ends here: at the goal, or nowhere
                    res = 1 if R.T[g, a] < 2.0 else -1
                    break
                a = b
            for a in path:
                good[a] = res
        nxt[g, good < 0] = -1
        kept[g] = int((nxt[g] >= 0).sum())
    # seconds along the pros' way (at running speed), for places the walking graph has no way from (a jump it lacks)
    tm = np.full((G, N), 1e9, np.float32)
    for g in range(G):
        for a0 in np.nonzero(nxt[g] >= 0)[0]:
            path, a, acc = [], int(a0), 0.0
            while nxt[g, a] >= 0 and tm[g, a] >= 1e9 and len(path) < 500:
                path.append(a)
                a = int(nxt[g, a])
            tail = float(tm[g, a]) if tm[g, a] < 1e9 else float(R.T[g, a])
            for a_ in reversed(path):
                tail += float(np.linalg.norm(R.nodes[a_] - R.nodes[int(nxt[g, a_])])) / 320.0
                tm[g, a_] = tail
    opened = [int(((tm[g] < 1e8) & (R.T[g] >= 1e8)).sum()) for g in range(G)]
    differs = [(int(((nxt[g] >= 0) & (nxt[g] != R.next[g])).sum())) for g in range(G)]
    out = os.path.join(ROOT, "sim", "pro_routes", mp + ".npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, labels=np.array(labels), next=nxt, time=tm, nodes=N, trips=trips)
    print("{}: {} nodes; per goal: trips, nodes with a pro step, of those not the shortest way's step".format(mp, N))
    for g, lab in enumerate(labels):
        print("  {:4s} {:6d} trips, {:4d} nodes ({:.0%} of the map), {:4d} differ, {:4d} places the walking graph had no way from".format(
            lab, int(trips[g]), int(kept[g]), kept[g] / N, differs[g], opened[g]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--step-max", type=float, default=STEP_MAX, help="the longest change of node that counts as a step (a jump across a gap needs more than a walk)")
    a = ap.parse_args()
    globals()["STEP_MAX"] = a.step_max
    for mp in a.map.split(","):                                 # (one world a process holds one player count: the same on every map)
        build(mp, a.limit)


if __name__ == "__main__":
    main()

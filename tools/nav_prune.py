"""Take out of a map's walking graph the jump and drop links that the walker cannot take the way it takes them.

The graph's move links were made by sim/build_nav.py from a standing start, in one of twelve directions, with or without
a jump. The walker (the walking teacher, the scripted item runner, and the "next step" arrow in his inputs) takes a link
by running at full speed straight at its far point, with a jump when that point is more than 150 units off and not much
lower, or a step up. Where the two differ he falls: the link before Blood Run's red armor is a 290-unit run along a
walkway, taken as a diagonal jump into the pit (RESULTS 2026-10-08, the wiring review).

This tries every such link that lies on a shortest way to a big item the walker's way, takes out the ones that fail, and
repeats until the shortest ways hold none. A link is kept, failing or not, if without it some point of the map loses its
way to an item. The points do not change, so the grid file, the pros' tables and the map reader's table stay valid.

    python tools/nav_prune.py --map bloodrun [--out <folder>]      (default: in place; the old file is kept as nav_<map>_sim.before_prune.json)
    python tools/teacher_check.py --map bloodrun [--nav-dir <folder>]     the test of the result
Anaconda Python.
"""
import argparse
import heapq
import json
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
B, SUB = 1024, (8, 8, 9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", default="", help="write the new graph to this folder instead of over the map's own")
    ap.add_argument("--teleporters", action="store_true", help="try the teleporter links the same way (a straight run at the far point) "
                    "and take the failing ones out: the ways then go round the teleporters (Aerowalk, 2026-10-08)")
    a = ap.parse_args()
    import duel_env as E
    src = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    g = json.load(open(src))
    N = np.array(g["nodes"], np.float32)
    edges = [list(e[:4]) for e in g["edges"]]
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=B // 2, seed=0, nav=src)
    w, R = env.w, env.route
    goals = [int(R.locate(gp[None])[0]) for gp in R.goals]
    spawn_nodes = R.locate(env.spawns)
    pads = []                                                # jump pads, as RouteField links them
    for c_, d_ in zip(env.pads, env.pad_dest) if len(env.pads) else []:
        dx = np.hypot(N[:, 0] - c_[0], N[:, 1] - c_[1])
        on = np.nonzero((dx < 130) & (np.abs(N[:, 2] - c_[2]) < 48))[0]
        land = int(np.linalg.norm(N - np.asarray(d_, np.float32) + np.array([0, 0, 100.0], np.float32), axis=1).argmin())
        pads += [(int(a_), land, 1.2 + float(dx[a_]) / 320.0) for a_ in on]

    def routes(ed):
        """seconds to each goal and the next point, as RouteField computes them"""
        radj, have = [[] for _ in N], set()
        for a_, b_, t, k in ed:
            d = float(np.linalg.norm(N[a_] - N[b_]))
            radj[b_].append((a_, 0.1 if k == "tele" else (d / 320.0 if k == "walk" else max(t, d / 900.0))))
            have.add((a_, b_))
        for a_, b_, t, k in ed:
            if k == "walk" and (b_, a_) not in have and abs(N[a_][2] - N[b_][2]) < 18:
                radj[a_].append((b_, float(np.linalg.norm(N[a_] - N[b_])) / 320.0))
        for a_, land, c in pads:
            radj[land].append((a_, c))
        T = np.full((len(goals), len(N)), 1e9, np.float32)
        nxt = np.full((len(goals), len(N)), -1, np.int64)
        for gi, b0 in enumerate(goals):
            dist, pq = {b0: 0.0}, [(0.0, b0)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c in radj[u]:
                    if d + c < dist.get(v, 1e18):
                        dist[v] = d + c
                        nxt[gi, v] = u
                        heapq.heappush(pq, (d + c, v))
            for v, d in dist.items():
                T[gi, v] = d
        return T, nxt

    def fails(links):
        """the links the walker's way does not arrive on"""
        bad = []
        for b0 in range(0, len(links), B):
            lb = links[b0:b0 + B]
            st, en = N[[x for x, y in lb]], N[[y for x, y in lb]]
            d = en - st
            hd = np.hypot(d[:, 0], d[:, 1])
            yaw = np.degrees(np.arctan2(d[:, 1], d[:, 0])).astype(np.float32)
            u = d[:, :2] / np.maximum(hd, 1e-6)[:, None]
            jump = ((hd > 150) & (d[:, 2] > -40)) | ((d[:, 2] > 18) & (hd < 260))
            n = len(lb)
            for i in range(n):
                w.reset(i, (float(st[i][0]), float(st[i][1]), float(st[i][2])), (float(u[i][0] * 320), float(u[i][1] * 320), 0.0), float(yaw[i]))
            ok = np.zeros(n, bool)
            for f in range(64):
                mv = np.zeros((w.n, 3), np.int8)
                mv[:n, 0] = 127
                mv[:n, 2] = np.where(jump & (f <= 2), 127, 0)
                ang = np.zeros((w.n, 2), np.float32)
                ang[:n, 1] = yaw
                for ms in SUB:
                    w.step(mv, ang, ms)
                s = w.state()[:n]
                ok |= (np.linalg.norm(s[:, :2] - en[:, :2], axis=1) < 40) & (np.abs(s[:, 2] - en[:, 2]) < 40) & (s[:, 6] > 0.5)
            bad += [lk for lk, o in zip(lb, ok) if not o]
        return bad

    T0, _ = routes(edges)
    reach0 = T0 < 1e8
    keep, removed = set(), 0
    for it in range(20):
        T, nxt = routes(edges)
        kind = {(e[0], e[1]): e[3] for e in edges}
        links = sorted({(int(a_), int(nxt[gi, a_])) for gi in range(len(goals)) for a_ in np.nonzero(T[gi] < 1e8)[0]
                        if nxt[gi, a_] >= 0 and kind.get((int(a_), int(nxt[gi, a_])), "pad") in (("air", "tele") if a.teleporters else ("air",))} - keep)   # (pads and teleporters: the walker heads for the plate or the entrance)
        bad = set(fails(links)) if links else set()
        # a link without which some point loses its way to an item stays
        while bad:
            T2, _ = routes([e for e in edges if (e[0], e[1]) not in bad])
            lost = reach0 & (T2 >= 1e8)
            back = {lk for lk in bad if lost[:, lk[0]].any()}
            if not back:
                break
            keep |= back
            bad -= back
        print("pass {}: {} jump or drop links on the shortest ways; {} the walker cannot take; {} kept so far because a place "
              "would lose its way".format(it, len(links), len(bad), len(keep)), flush=True)
        if not bad:
            break
        edges = [e for e in edges if (e[0], e[1]) not in bad]
        removed += len(bad)
    T, _ = routes(edges)
    out_dir = a.out or os.path.dirname(src)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "nav_{}_sim.json".format(a.map))
    if os.path.abspath(dst) == os.path.abspath(src):
        bak = src.replace("_sim.json", "_sim.before_prune.json")
        if not os.path.exists(bak):
            shutil.copy(src, bak)
    elif os.path.exists(src + ".grid.npz"):
        shutil.copy(src + ".grid.npz", dst + ".grid.npz")
    json.dump(dict(nodes=g["nodes"], edges=edges, pruned=dict(removed=removed, kept_failing=sorted(map(list, keep)))), open(dst, "w"))
    print("{}: {} links taken out, {} failing links kept; places with a way to each item before -> after: {}; median way from the spawn "
          "points before -> after: {}".format(
              a.map, removed, len(keep),
              {lab: "{} -> {}".format(int(reach0[gi].sum()), int((T[gi] < 1e8).sum())) for gi, lab in enumerate(env.route_goal)},
              {lab: "{:.1f} -> {:.1f}".format(float(np.median(T0[gi, spawn_nodes][T0[gi, spawn_nodes] < 1e8])) if (T0[gi, spawn_nodes] < 1e8).any() else -1,
                                             float(np.median(T[gi, spawn_nodes][T[gi, spawn_nodes] < 1e8])) if (T[gi, spawn_nodes] < 1e8).any() else -1)
               for gi, lab in enumerate(env.route_goal)}))


if __name__ == "__main__":
    main()

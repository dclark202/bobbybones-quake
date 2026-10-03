"""Build a map's nav graph with the simulator instead of recordings.

    python sim/build_nav.py --map aerowalk            -> data/maps/nav_aerowalk_sim.json

1. Standing spots: drop a player-sized box onto the map on a grid at every height; keep spots on walkable
   floor (normal z >= 0.7) inside the playable map.
2. Walk links: simulate walking between neighbouring spots (human physics); keep the ones that arrive.
3. Move links: from every spot, simulate running (and run + jump) in 12 directions for 1.2 s; the first
   landing far from the start (drops, jumps, jump pads) and teleporter exits become links, timed.
Same format as the recorded graphs: {"nodes": [[x,y,z]...], "edges": [[a, b, seconds, kind]...]}.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from qsim import World  # noqa: E402

SUB = (8, 8, 9)       # human physics


def step(w, moves, yaws):
    for ms in SUB:
        w.step(moves, np.stack([np.zeros(len(yaws), np.float32), yaws.astype(np.float32)], 1), ms)


def spots(w, grid):
    lo, hi = w.bounds()
    out = []
    for x in np.arange(lo[0] + 16, hi[0] - 16, grid):
        for y in np.arange(lo[1] + 16, hi[1] - 16, grid):
            z = hi[2] - 40
            while z > lo[2] + 40:
                tr = w.trace((x, y, z), (x, y, z - 2000), w.PLAYER_MINS, w.PLAYER_MAXS)
                if tr["startsolid"]:
                    z -= 24
                    continue
                if tr["fraction"] >= 1:
                    break
                p = tr["endpos"]
                if tr["normal"][2] >= 0.7 and w.cluster(p) >= 0:
                    out.append((float(p[0]), float(p[1]), float(p[2])))
                z = p[2] - 80                                  # look for the next floor below this one
    pts = np.unique(np.round(np.array(out, np.float32), 1), axis=0)
    return pts


def rollout(w, starts, yaws, moves_fn, frames):
    """starts n x 3, yaws n -> positions/velocities/ground over time (frames x n x ...)"""
    n = len(starts)
    for i in range(n):
        w.reset(i, starts[i], (0, 0, 0), float(yaws[i]))
    P = np.zeros((frames + 1, n, 3), np.float32)
    G = np.zeros((frames + 1, n), np.float32)
    s = w.state()[:n]
    P[0], G[0] = s[:, :3], s[:, 6]
    for f in range(frames):
        mv = moves_fn(f, n)
        full = np.zeros((w.n, 3), np.int8)
        full[:n] = mv
        y = np.zeros(w.n, np.float32)
        y[:n] = yaws
        step(w, full, y)
        s = w.state()[:n]
        P[f + 1], G[f + 1] = s[:, :3], s[:, 6]
    return P, G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="aerowalk")
    ap.add_argument("--grid", type=float, default=48.0)
    ap.add_argument("--batch", type=int, default=4096)
    a = ap.parse_args()
    t0 = time.time()
    w = World(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n=a.batch)
    nodes = spots(w, a.grid)
    kd = cKDTree(nodes)
    print("{}: {} standing spots ({:.0f}s)".format(a.map, len(nodes), time.time() - t0), flush=True)
    edges = {}

    def add(i, j, t, kind):
        if i != j and ((i, j) not in edges or edges[(i, j)][0] > t):
            edges[(i, j)] = (t, kind)

    # walk links between neighbours
    pairs = [(i, j) for i, js in enumerate(kd.query_ball_point(nodes, a.grid * 1.5)) for j in js
             if i != j and abs(nodes[i][2] - nodes[j][2]) < 48]
    for b0 in range(0, len(pairs), a.batch):
        pb = pairs[b0:b0 + a.batch]
        st = nodes[[p[0] for p in pb]]
        en = nodes[[p[1] for p in pb]]
        yaw = np.degrees(np.arctan2(en[:, 1] - st[:, 1], en[:, 0] - st[:, 0]))
        P, G = rollout(w, st, yaw, lambda f, n: np.tile(np.array([[127, 0, 0]], np.int8), (n, 1)), 16)
        d = np.linalg.norm(P[:, :, :2] - en[None, :, :2], axis=2)
        ok = (d < 16) & (np.abs(P[:, :, 2] - en[None, :, 2]) < 20)
        first = np.where(ok.any(0), ok.argmax(0), -1)
        for k, (i, j) in enumerate(pb):
            if first[k] > 0:
                add(i, j, first[k] * 0.025, "walk")
    n_walk = len(edges)
    print("  walk links {} ({:.0f}s)".format(n_walk, time.time() - t0), flush=True)

    # run / run+jump in 12 directions: drops, jumps, jump pads, teleporters
    dirs = np.arange(0, 360, 30, dtype=np.float32)
    jobs = [(i, y, mode) for i in range(len(nodes)) for y in dirs for mode in (0, 1)]
    F = 48
    for b0 in range(0, len(jobs), a.batch):
        jb = jobs[b0:b0 + a.batch]
        st = nodes[[j[0] for j in jb]]
        yaw = np.array([j[1] for j in jb], np.float32)
        jump = np.array([j[2] for j in jb])

        def moves(f, n, jump=jump):
            m = np.zeros((n, 3), np.int8)
            m[:, 0] = 127
            m[:, 2] = np.where((jump == 1) & (f >= 4) & (f <= 6), 127, 0)
            return m
        P, G = rollout(w, st, yaw, moves, F)
        for k, (i, y, mode) in enumerate(jb):
            p0 = P[0, k]
            airborne = False
            for f in range(1, F + 1):
                jumpd = np.linalg.norm(P[f, k] - P[f - 1, k])
                if jumpd > 100:                                # teleported
                    jn = kd.query(P[f, k])[1]
                    add(i, int(jn), f * 0.025, "tele")
                    break
                if G[f, k] < 0.5:
                    airborne = True
                elif airborne:                                 # landed
                    d, jn = kd.query(P[f, k])
                    far = np.linalg.norm(P[f, k, :2] - p0[:2]) > a.grid * 1.5 or P[f, k, 2] - p0[2] < -40 or \
                        P[f, k, 2] - p0[2] > 30
                    if d < a.grid and far:
                        add(i, int(jn), f * 0.025, "air")
                    break
    print("  move links {} ({:.0f}s)".format(len(edges) - n_walk, time.time() - t0), flush=True)
    kinds = {}
    for t, k in edges.values():
        kinds[k] = kinds.get(k, 0) + 1
    out = dict(nodes=[[round(float(v), 1) for v in p] for p in nodes],
               edges=[[i, j, round(t, 3), k] for (i, j), (t, k) in edges.items()], source="sim/build_nav.py")
    path = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    json.dump(out, open(path, "w"))
    print("wrote {}: {} nodes, links {} ({:.0f}s)".format(path, len(nodes), kinds, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()

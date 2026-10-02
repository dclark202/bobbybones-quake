"""Build a navigation graph for a map from recorded bot traces.

input : trace file lines "frame id x y z vx vy vz" (from botctl !record)
output: JSON {nodes: [[x,y,z],...], edges: [[a,b,seconds,kind],...]}  kind: "walk" | "air"

Nodes are 40-unit floor cells (separate per floor height). An edge A->B is added whenever a bot
went from standing in A to standing in B (with only airborne frames in between), so drops,
jump pads and jumps are included and are directional.
"""
import json
import math
import sys
from collections import defaultdict

CELL = 40.0
src, out = sys.argv[1], sys.argv[2]

tracks = defaultdict(list)
for line in open(src):
    f = line.split()
    if len(f) != 8:
        continue
    fr, cid = int(f[0]), int(f[1])
    x, y, z, vx, vy, vz = map(float, f[2:])
    tracks[cid].append((fr, x, y, z, vz))


def cell_of(x, y, z):
    return (int(math.floor(x / CELL)), int(math.floor(y / CELL)), int(round(z / 24.0)))


node_pts = defaultdict(list)
edge_t = {}
edge_kind = {}
for cid, tr in tracks.items():
    tr.sort()
    prev_ground = None  # (frame, cell)
    last = None
    for fr, x, y, z, vz in tr:
        if last is not None and (fr - last[0] > 3 or math.dist((x, y, z), last[1:4]) > 80 * (fr - last[0])):
            prev_ground = None  # respawn / teleport / gap: break the chain
        last = (fr, x, y, z)
        ground = abs(vz) < 1
        if not ground:
            continue
        c = cell_of(x, y, z)
        node_pts[c].append((x, y, z))
        if prev_ground is not None and prev_ground[1] != c:
            dt = (fr - prev_ground[0]) * 0.025
            kind = "air" if fr - prev_ground[0] > 1 and dt > 0.05 else "walk"
            key = (prev_ground[1], c)
            # ignore implausibly slow transitions (bot stood around, fought, etc.)
            d = math.dist(prev_ground[2], (x, y, z))
            if dt < 3.0 and (kind == "air" or d / max(dt, 0.025) > 150):
                if key not in edge_t or dt < edge_t[key]:
                    edge_t[key], edge_kind[key] = dt, kind
        prev_ground = (fr, c, (x, y, z))

cells = [c for c, pts in node_pts.items() if len(pts) >= 2]
index = {c: i for i, c in enumerate(cells)}
nodes = []
for c in cells:
    pts = node_pts[c]
    nodes.append([round(sum(p[i] for p in pts) / len(pts), 1) for i in range(3)])
edges = [[index[a], index[b], round(t, 3), edge_kind[(a, b)]] for (a, b), t in edge_t.items()
         if a in index and b in index]
json.dump(dict(nodes=nodes, edges=edges), open(out, "w"))
print("nodes", len(nodes), "edges", len(edges), "air", sum(1 for e in edges if e[3] == "air"))

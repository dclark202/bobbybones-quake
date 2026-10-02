"""Build a navigation graph for a map from recorded bot traces.

input : trace file lines "frame id x y z vx vy vz" (from botctl !record)
output: JSON {nodes: [[x,y,z],...], edges: [[a,b,seconds,kind],...]}  kind: "walk" | "air"

Nodes are 40-unit floor cells (separate per floor height). An edge A->B is added whenever a bot
went from standing in A to standing in B (with only airborne frames in between), so drops,
jump pads and jumps are included and are directional.
"""
import json
import math
import os
import sys
from collections import defaultdict

CELL = 40.0
srcs, out = sys.argv[1:-1], sys.argv[-1]   # several recordings (bots + humans) -> one graph

tracks = defaultdict(list)
for i, src in enumerate(srcs):
    seg, last_fr = 0, -1
    for line in open(src):
        f = line.split()
        if len(f) < 8:
            continue
        fr, cid = int(f[0]), int(f[1])
        if fr < last_fr - 5:
            seg += 1                       # frame counter reset (server/plugin restart): new recording
        last_fr = max(last_fr, fr) if fr >= last_fr - 5 else fr
        x, y, z, vx, vy, vz = map(float, f[2:8])
        tracks[(i, seg, cid)].append((fr, x, y, z, vz))


def cell_of(x, y, z):
    return (int(math.floor(x / CELL)), int(math.floor(y / CELL)), int(round(z / 24.0)))


node_pts = defaultdict(list)
edge_t = {}
edge_kind = {}
edge_n = defaultdict(int)  # how often each move was seen
tele = defaultdict(int)   # (src cell, dst cell) -> times seen; repeated = a teleporter, one-offs = respawns
for cid, tr in tracks.items():
    tr.sort()
    prev_ground = None  # (frame, cell)
    last = None
    pending_tele = None
    for fr, x, y, z, vz in tr:
        if last is not None and (fr - last[0] > 3 or math.dist((x, y, z), last[1:4]) > 80 * (fr - last[0])):
            # respawn / teleport / gap: break the chain, but remember where we left from
            jumped = fr - last[0] <= 2 and math.dist((x, y, z), last[1:4]) > 200
            pending_tele = (prev_ground[1], fr) if (jumped and prev_ground is not None and fr - prev_ground[0] <= 8) else None
            prev_ground = None
        last = (fr, x, y, z)
        ground = abs(vz) < 1
        if not ground:
            continue
        c = cell_of(x, y, z)
        node_pts[c].append((x, y, z))
        if pending_tele is not None:
            if fr - pending_tele[1] <= 20:
                tele[(pending_tele[0], c)] += 1
            pending_tele = None
        if prev_ground is not None and prev_ground[1] != c:
            dt = (fr - prev_ground[0]) * 0.025
            kind = "air" if fr - prev_ground[0] > 1 and dt > 0.05 else "walk"
            key = (prev_ground[1], c)
            # ignore implausibly slow transitions (bot stood around, fought, etc.)
            d = math.dist(prev_ground[2], (x, y, z))
            if dt < 3.0 and (kind == "air" or d / max(dt, 0.025) > 150):
                edge_n[key] += 1
                if key not in edge_t or dt < edge_t[key]:
                    edge_t[key], edge_kind[key] = dt, kind
        prev_ground = (fr, c, (x, y, z))

# merge a previously learned graph (e.g. promoted from training): union of moves, fastest wins
merge = os.environ.get("NAV_MERGE")
if merge and os.path.exists(merge):
    g = json.load(open(merge))
    if g.get("cells"):
        mc = [tuple(c) for c in g["cells"]]
        for i, c in enumerate(mc):
            if len(node_pts[c]) < 2:
                node_pts[c] += [tuple(g["nodes"][i])] * 2
        for a, b, t, kind in g["edges"]:
            key = (mc[a], mc[b])
            if kind == "tele":
                tele[key] += 2
                continue
            edge_n[key] += 2
            if key not in edge_t or t < edge_t[key]:
                edge_t[key], edge_kind[key] = t, kind
cells = [c for c, pts in node_pts.items() if len(pts) >= 2]
index = {c: i for i, c in enumerate(cells)}
nodes = []
for c in cells:
    pts = node_pts[c]
    nodes.append([round(sum(p[i] for p in pts) / len(pts), 1) for i in range(3)])
def plausible(a, b, t):
    # very fast/long flights are usually knockback from hits, not a move: require seeing them twice
    if edge_kind[(a, b)] != "air":
        return True
    pa, pb = node_pts[a][0], node_pts[b][0]
    speed = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) / max(t, 0.025)
    return speed < 450 or edge_n[(a, b)] >= 2


banned = set()
if os.environ.get("NAV_BANNED") and os.path.exists(os.environ["NAV_BANNED"]):
    # moves that failed repeatedly in practice (cells as "x,y,z>x,y,z" lines)
    for line in open(os.environ["NAV_BANNED"]):
        a, b = line.strip().split(">")
        banned.add((tuple(map(int, a.split(","))), tuple(map(int, b.split(",")))))
edges = [[index[a], index[b], round(t, 3), edge_kind[(a, b)]] for (a, b), t in edge_t.items()
         if a in index and b in index and plausible(a, b, t) and (a, b) not in banned]
cell_of_node = {index[c]: c for c in cells}
# teleporters: the same source -> destination seen at least twice (respawns land at random-ish spots)
def coarse(c):
    return (c[0] // 2, c[1] // 2, c[2])
groups = defaultdict(list)
for (a, b), n in tele.items():
    groups[(coarse(a), coarse(b))].append((n, a, b))
n_tele = 0
for key, items in groups.items():
    if sum(n for n, a, b in items) >= 2:
        n, a, b = max(items)
        if a in index and b in index:
            edges.append([index[a], index[b], 0.1, "tele"])
            n_tele += 1
print("teleporters", n_tele)
json.dump(dict(nodes=nodes, edges=edges, cells=[list(cell_of_node[i]) for i in range(len(nodes))]), open(out, "w"))
print("nodes", len(nodes), "edges", len(edges), "air", sum(1 for e in edges if e[3] == "air"))

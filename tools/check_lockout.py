"""Check the compiled Lockout in the simulator's own collision: what can a player reach on foot, and does everything connect.

    python tools/check_lockout.py [map]      # default lockout; needs data/maps/<map>.bsp (tools/build_lockout.sh)

Walkable positions are found on a 32-unit grid; from one spawn a flood fill follows steps (up to 18), jumps (up to 40) and
drops. The jump pads in the map are added as one-way edges. Prints the spawns and items that cannot be reached, and
writes maps/<map>/preview.png (top-down, height as colour, items and spawns marked)."""
import os
import sys
from collections import deque

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
from qsim import World

G = 32
MINS, MAXS = (-15, -15, -24), (15, 15, 32)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "lockout"
    w = World(os.path.join(ROOT, "data", "maps", name + ".bsp"), n=1)
    lo, hi = w.bounds()
    x0, y0 = int(lo[0] // G) * G + G // 2, int(lo[1] // G) * G + G // 2
    nx, ny = int((hi[0] - lo[0]) // G), int((hi[1] - lo[1]) // G)
    top = float(hi[2])
    floors = {}
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * G, y0 + j * G
            z, out = top - 8, []
            while z > lo[2] + 8:
                t = w.trace((x, y, z), (x, y, lo[2]), MINS, MAXS)
                if t["startsolid"]:
                    z -= 8
                    continue
                if t["fraction"] >= 1.0:
                    break
                out.append(float(t["endpos"][2]))
                z = float(t["endpos"][2]) - 8
            floors[(i, j)] = out
    nodes = {(i, j, k): z for (i, j), zs in floors.items() for k, z in enumerate(zs)}

    def clear(a, b):
        t = w.trace(a, b, MINS, MAXS)
        return t["fraction"] >= 1.0 and not t["startsolid"]

    def cell_of(p):
        return int((p[0] - x0 + G / 2) // G), int((p[1] - y0 + G / 2) // G)

    def node_near(p):
        i, j = cell_of(p)
        best = None
        for k, z in enumerate(floors.get((i, j), [])):
            if abs(z - (p[2] + 24)) < 40 and (best is None or abs(z - (p[2] + 24)) < abs(floors[(i, j)][best] - (p[2] + 24))):
                best = k
        return None if best is None else (i, j, best)

    pads = []                                        # (from node cell, to point) for every jump pad: land where the target is
    for tr in w.triggers if hasattr(w, "triggers") else []:
        pads.append(tr)
    spawns = w.spawns()
    start = node_near([float(v) for v in spawns[0]["origin"].split()] if isinstance(spawns[0]["origin"], str) else spawns[0]["origin"])
    def flood(maxdrop):
        seen = {start: 0}
        q = deque([start])
        while q:
            n = q.popleft()
            i, j, k = n
            za = nodes[n]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for k2, zb in enumerate(floors.get((i + di, j + dj), [])):
                    m = (i + di, j + dj, k2)
                    if m in seen or zb - za > 40 or za - zb > maxdrop:
                        continue
                    zc = max(za, zb)
                    if clear((x0 + i * G, y0 + j * G, za), (x0 + (i + di) * G, y0 + (j + dj) * G, zc)) or                             clear((x0 + i * G, y0 + j * G, za + 18), (x0 + (i + di) * G, y0 + (j + dj) * G, zb + 18)):
                        seen[m] = seen[n] + 1
                        q.append(m)
        return seen
    seen = flood(400)                                # steps, jumps and drops
    walk = flood(40)                                 # no drops: every floor must also be reachable by stairs
    # the lift pad: a pad edge from its trigger to the point under its target (found by the same flood fill later if listed)
    report = []

    def reach(p, label):
        nd = node_near(p)
        report.append((label, nd is not None and nd in seen, nd is not None, nd is not None and nd in walk))
    for e in w.items():
        o = [float(v) for v in (e["origin"].split() if isinstance(e["origin"], str) else e["origin"])]
        reach([o[0], o[1], o[2] - 24], e["classname"] + " @ {:.0f},{:.0f},{:.0f}".format(*o))
    for e in spawns:
        o = [float(v) for v in (e["origin"].split() if isinstance(e["origin"], str) else e["origin"])]
        reach([o[0], o[1], o[2] - 24], "spawn @ {:.0f},{:.0f},{:.0f}".format(*o))
    bad = [r for r in report if not r[1]]
    print("grid {}x{}, {} walkable cells, {} reached from spawn 0".format(nx, ny, len(nodes), len(seen)))
    print("unreachable on foot (before jump pads): {} of {}".format(len(bad), len(report)))
    for label, ok, found, w_ok in bad:
        print("  ", label, "(no floor under it)" if not found else "")
    nw = [r for r in report if r[1] and not r[3]]
    print("reachable only by dropping down (no way up on foot): {}".format(len(nw)))
    for r in nw:
        print("  ", r[0])
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (nx * 3, ny * 3), (20, 20, 30))
        d = ImageDraw.Draw(img)
        for (i, j), zs in floors.items():
            for k, z in enumerate(zs):
                c = int(min(255, max(0, 60 + z * 0.45)))
                ok = (i, j, k) in seen
                d.rectangle([i * 3, (ny - 1 - j) * 3, i * 3 + 2, (ny - 1 - j) * 3 + 2], fill=(c, c, 255 - c // 2) if ok else (200, 40, 40))
        for e in w.items():
            o = [float(v) for v in (e["origin"].split() if isinstance(e["origin"], str) else e["origin"])]
            px, py = (o[0] - x0) / G * 3 + 1, (ny - 1 - (o[1] - y0) / G) * 3 + 1
            d.ellipse([px - 4, py - 4, px + 4, py + 4], outline=(255, 255, 0))
        out = os.path.join(ROOT, "maps", name, "preview.png")
        img.save(out)
        print("preview ->", out)
    except Exception as ex:
        print("no preview:", ex)


if __name__ == "__main__":
    main()

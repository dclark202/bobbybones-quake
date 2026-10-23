"""v0.4.0 brain: a map cut into zones (the owner, 2026-10-23: "let's replace the 10+s range with the distribution over
locations"). The brain's readout gives odds over a map's zones (sim/track_z.py); its truth is the zone the enemy stands in
(sim/zonemap.py, the simulator's TRACK_Z columns). Run in the system Python (it needs scipy; matplotlib for --picture):

    python tools/make_zones.py [--maps bloodrun,aerowalk,...] [--picture]

How a map is cut (from the walking map data/maps/nav_<map>_sim.json only):
  1. the walking map's "walk" and "air" links (steps, jumps, drops; not teleporters), both ways, cost = the distance with height counted three times (so floors part);
     points no walk link reaches are tied to their nearest point;
  2. K seeds (K = the points / 75, kept within 16 .. 24) by farthest-point sampling on that graph (the first: the point
     nearest the middle), then 20 rounds of Lloyd: every point to its nearest seed along the graph, every zone's new seed
     the point of the zone nearest its mean place;
  3. a zone is connected along the graph by construction (a graph Voronoi cell); numbered from the highest floor down
     (by the zone's mean height, then x, then y), so the numbers read the same every time it is built.
Written: sim/zones/<map>.json = {map, k, cell, lo, dims, z_w, centres [k, 3], size [k] (points), names [k] (the nearest of
the map's duel items within 400 units, else ""), node_zone [points] (by the walking map's point numbers), nodes (the
walking map's point count), grid (zlib + base64 of int8 [dims], the zone of every 32-unit cell: the nearest walking point,
height counted double: the convention of the simulator's RouteField)}; --picture: docs/design/zones/<map>.png.
"""
import argparse
import base64
import json
import os
import zlib

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure,houseofdecay,dismemberment"
CELL = 32.0
Z_W_GRAPH = 3.0          # height in the graph's link costs
Z_W_GRID = 2.0           # height in the grid's nearest point (RouteField's w)
ITEM_ABBR = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA",
             "weapon_rocketlauncher": "RL", "weapon_railgun": "RG", "weapon_lightning": "LG", "weapon_plasmagun": "PG",
             "weapon_grenadelauncher": "GL", "weapon_shotgun": "SG", "weapon_hmg": "HMG"}


def graph(nodes, edges):
    n = len(nodes)
    wz = np.array([1.0, 1.0, Z_W_GRAPH])
    ok = [e for e in edges if e[3] in ("walk", "air")]
    a = np.array([e[0] for e in ok], np.int64)
    b = np.array([e[1] for e in ok], np.int64)
    c = np.linalg.norm((nodes[a] - nodes[b]) * wz, axis=1) + 1.0
    A = coo_matrix((np.r_[c, c], (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
    nc, lab = connected_components(A, directed=False)
    big = np.bincount(lab).argmax()
    extra = 0
    if nc > 1:                                              # the points the main part does not reach: tied to their nearest point of it
        main = np.nonzero(lab == big)[0]
        tr = cKDTree(nodes[main] * wz)
        rest = np.nonzero(lab != big)[0]
        d, j = tr.query(nodes[rest] * wz)
        a2, b2, c2 = rest, main[j], d + 1.0
        A = (A + coo_matrix((np.r_[c2, c2], (np.r_[a2, b2], np.r_[b2, a2])), shape=(n, n)).tocsr()).tocsr()
        extra = len(rest)
    return A, extra


def cut(nodes, A, k, rounds=20, seeds=None):
    wz = np.array([1.0, 1.0, Z_W_GRAPH])
    mid = nodes.mean(0)
    if seeds is None:
        seeds = [int(np.linalg.norm((nodes - mid) * wz, axis=1).argmin())]
        dmin = dijkstra(A, indices=seeds[0])
    for _ in range(k - len(seeds)):
        s = int(np.argmax(np.where(np.isfinite(dmin), dmin, -1)))
        seeds.append(s)
        dmin = np.minimum(dmin, dijkstra(A, indices=s))
    lab = None
    for _ in range(rounds):
        D, _, src = dijkstra(A, indices=seeds, min_only=True, return_predecessors=True)
        lab = np.searchsorted(np.array(sorted(seeds)), src)          # (src: the seed reached; map to its order in the sorted list)
        order = np.array(sorted(seeds))
        new = []
        for z in range(k):
            mem = np.nonzero(lab == z)[0]
            if not len(mem):
                new.append(int(order[z]))
                continue
            c = nodes[mem].mean(0)
            new.append(int(mem[np.linalg.norm((nodes[mem] - c) * wz, axis=1).argmin()]))
        if sorted(new) == sorted(seeds):
            break
        seeds = new
    D, _, src = dijkstra(A, indices=seeds, min_only=True, return_predecessors=True)
    order = np.array(sorted(seeds))
    lab = np.searchsorted(order, src)
    return lab, [int(x) for x in order]


def cut_even(nodes, A, k, tries=40):
    """cut() and then, while a zone holds under 35% of the mean (an outlier the farthest-point start picked), its seed is
    moved into the largest zone (that zone's point at the 80th percentile of the distance from its seed along the graph) and Lloyd runs again"""
    lab, seeds = cut(nodes, A, k)
    for _ in range(tries):
        size = np.bincount(lab, minlength=k)
        if size.min() >= 0.35 * len(nodes) / k:
            break
        small, large = int(size.argmin()), int(size.argmax())
        mem = np.nonzero(lab == large)[0]
        d = dijkstra(A, indices=seeds[large])[mem]
        d = np.where(np.isfinite(d), d, -1)
        far = int(mem[np.argsort(d)[int(0.8 * (len(d) - 1))]])         # (the 80th percentile: not an outlier again)
        seeds = [s for z, s in enumerate(seeds) if z != small] + [far]
        lab, seeds = cut(nodes, A, k, seeds=seeds)
    size = np.bincount(lab, minlength=k)
    wz = np.array([1.0, 1.0, Z_W_GRAPH])
    for z in np.nonzero(size < 12)[0]:                     # what is still tiny joins the zone of its nearest point outside it
        mem = np.nonzero(lab == z)[0]
        rest = np.nonzero(lab != z)[0]
        d, j = cKDTree(nodes[rest] * wz).query(nodes[mem] * wz)
        lab[mem] = lab[rest[j[np.argmin(d)]]]
    used = np.unique(lab)
    return np.searchsorted(used, lab), len(used)


def renumber(nodes, lab, k):
    cen = np.array([nodes[lab == z].mean(0) for z in range(k)])
    order = sorted(range(k), key=lambda z: (-round(cen[z, 2] / 64.0), cen[z, 0], cen[z, 1]))
    new_of = np.empty(k, np.int64)
    new_of[order] = np.arange(k)
    return new_of[lab]


def build(m, picture):
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m))
    if not os.path.exists(nav):
        print(m, "no walking map: skipped")
        return None
    g = json.load(open(nav))
    nodes = np.array(g["nodes"], np.float64)
    n = len(nodes)
    k = int(np.clip(round(n / 75.0), 16, 24))
    A, extra = graph(nodes, g["edges"])
    lab, k = cut_even(nodes, A, k)
    lab = renumber(nodes, lab, k)
    size = np.bincount(lab, minlength=k)
    cen = np.array([nodes[lab == z].mean(0) for z in range(k)])
    # the grid: the zone of every cell, by the nearest walking point (height counted double)
    lo = nodes.min(0) - 64.0
    dims = np.ceil((nodes.max(0) + 64.0 - lo) / CELL).astype(int)
    w = np.array([1.0, 1.0, Z_W_GRID])
    tr = cKDTree(nodes * w)
    cx = [lo[i] + (np.arange(dims[i]) + 0.5) * CELL for i in range(3)]
    P = np.stack(np.meshgrid(*cx, indexing="ij"), -1).reshape(-1, 3)
    _, j = tr.query(P * w)
    grid = lab[j].astype(np.int8).reshape(tuple(dims))
    names = [""] * k
    it_ = json.load(open(os.path.join(ROOT, "plugins", "duel_items.json"))).get(m)
    if it_:
        big = [(ITEM_ABBR[c], np.array(p, np.float64)) for c, *p in it_ if c in ITEM_ABBR]
        for z in range(k):
            best = sorted(((np.linalg.norm((p - cen[z]) * [1, 1, Z_W_GRAPH]), a) for a, p in big if lab[tr.query(p * w)[1]] == z))
            names[z] = "+".join(sorted({a for d, a in best}, key=lambda s: list(ITEM_ABBR.values()).index(s)))
    out = dict(map=m, version=1, k=k, cell=CELL, lo=[round(float(x), 3) for x in lo], dims=[int(x) for x in dims], z_w=Z_W_GRID,
               nodes=n, tied=int(extra), centres=[[round(float(x), 1) for x in c] for c in cen], size=[int(s) for s in size],
               names=names, node_zone=[int(x) for x in lab],
               grid=base64.b64encode(zlib.compress(grid.tobytes(), 9)).decode("ascii"))
    d = os.path.join(ROOT, "sim", "zones")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, m + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print("{:15s} points {:5d} (tied {:3d}) zones {:2d} points a zone {:3d}..{:3d} grid {} ({} KB) items: {}".format(
        m, n, extra, k, size.min(), size.max(), "x".join(map(str, dims)), os.path.getsize(os.path.join(d, m + ".json")) // 1024,
        " ".join("{}:{}".format(z, nm) for z, nm in enumerate(names) if nm)))
    if picture:
        draw(m, nodes, lab, k, cen, names)
    return out


def draw(m, nodes, lab, k, cen, names):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = os.path.join(ROOT, "docs", "design", "zones")
    os.makedirs(d, exist_ok=True)
    cm = plt.get_cmap("tab20")
    col = np.array([cm(i) if i < 20 else plt.get_cmap("Dark2")(i - 20) for i in range(k)])
    fig, ax = plt.subplots(1, 2, figsize=(16, 8), gridspec_kw=dict(width_ratios=[1, 1]))
    o = np.argsort(nodes[:, 2])
    ax[0].scatter(nodes[o, 0], nodes[o, 1], c=col[lab[o]], s=6)
    ax[1].scatter(nodes[:, 0], nodes[:, 2], c=col[lab], s=4)
    for z in range(k):
        t = str(z) + (" " + names[z] if names[z] else "")
        ax[0].text(cen[z, 0], cen[z, 1], t, fontsize=9, weight="bold", ha="center", va="center",
                   bbox=dict(facecolor="white", alpha=0.7, lw=0, pad=1))
        ax[1].text(cen[z, 0], cen[z, 2], str(z), fontsize=8, ha="center", va="center")
    ax[0].set_title("{}: {} zones, from above (higher points drawn last)".format(m, k))
    ax[1].set_title("from the side (x, height)")
    for a in ax:
        a.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(os.path.join(d, m + ".png"), dpi=80)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=MAPS)
    ap.add_argument("--picture", action="store_true")
    a = ap.parse_args()
    for m in a.maps.split(","):
        build(m, a.picture)


if __name__ == "__main__":
    main()

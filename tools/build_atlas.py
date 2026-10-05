"""Build the map atlas: one inspectable file per map with what a good player knows about it.

    python tools/build_atlas.py --maps bloodrun,aerowalk,campgrounds      (Anaconda Python; needs sim/qsim)

Output: maps/atlas/<map>.json and maps/atlas/<map>.png

What is in it
  areas    the map cut into named areas (clusters of route-graph nodes): centre, height, how exposed the area
           is (share of nearby spots that can see it), neighbours, share of time pro players spend there
  items    every big item (armors, mega health, weapons): position, respawn time, area
  routes   for every (area, big item): several distinct routes, not only the fastest. Each has the areas it
           passes, its time on the route graph, exposure along the way, how often pro demos took it, and a
           preference. The preference is seeded from the pro counts and is meant to be updated from Bobby's own
           results later (the "bobby" block: tries, arrivals, time, damage taken; empty for now).
  Routes that pros take but the graph search did not propose are added with source "pro".

Pro demos: data/demos_parsed/<map>/*.bin (tools/demodump). A "trip" ends when the followed player arrives at a big
item's spot (whether or not the item was up) and starts at his previous arrival, death, or 15 s earlier.
No player names are stored.
"""
import argparse
import collections
import glob
import heapq
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

Z_W = 2.5            # height counts this much more than horizontal distance when cutting the map into areas
ALT_TIME = 1.6       # an alternative route may take up to this many times the fastest one (plus a second)
ALT_OVERLAP = 0.6    # ... and must share less than this share of its spots with every route already kept
MAX_ROUTES = 4
ARRIVE_XY, ARRIVE_Z, LEAVE = 48.0, 64.0, 200.0
TRIP_MAX = 15.0


def kmeans(x, k, rng, iters=40):
    c = x[rng.choice(len(x), k, replace=False)].copy()
    for _ in range(iters):
        lab = np.linalg.norm(x[:, None] - c[None], axis=2).argmin(1)
        for j in range(k):
            if (lab == j).any():
                c[j] = x[lab == j].mean(0)
    return lab


def dijkstra(adj, src, w=None):
    """adj[a] = [(b, edge index)], w = time per edge. Returns (time per node, previous node)."""
    n = len(adj)
    dist = np.full(n, np.inf)
    prev = np.full(n, -1, np.int64)
    dist[src] = 0.0
    pq = [(0.0, src)]
    while pq:
        d, a = heapq.heappop(pq)
        if d > dist[a]:
            continue
        for b, e in adj[a]:
            nd = d + w[e]
            if nd < dist[b]:
                dist[b], prev[b] = nd, a
                heapq.heappush(pq, (nd, b))
    return dist, prev


def path_to(prev, dst):
    p = [int(dst)]
    while prev[p[-1]] >= 0:
        p.append(int(prev[p[-1]]))
    return p[::-1]


def dedup(seq):
    out = []
    for v in seq:
        if not out or out[-1] != v:
            out.append(int(v))
    return out


def nearest(nodes, pts, chunk=4000):
    out = np.zeros(len(pts), np.int64)
    sc = np.array([1, 1, Z_W], np.float32)
    for i in range(0, len(pts), chunk):
        out[i:i + chunk] = np.linalg.norm((pts[i:i + chunk, None] - nodes[None]) * sc, axis=2).argmin(1)
    return out


def build(mp, demos_dir, out_dir, seed=0):
    import demo_reader as D
    import duel_env as E
    rng = np.random.default_rng(seed)
    nav = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))))
    nodes = np.array(nav["nodes"], np.float32)
    edges = nav["edges"]
    N = len(nodes)
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=seed,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    adj = [[] for _ in range(N)]
    wt = np.array([e[2] for e in edges], np.float64)
    for k, (a, b, t, kind) in enumerate(edges):
        adj[a].append((b, k))

    # ---- areas
    K = int(np.clip(round(N / 45), 12, 32))
    lab = kmeans(nodes * np.array([1, 1, Z_W], np.float32), K, rng)
    order = np.argsort([-(lab == j).sum() for j in range(K)])           # stable ids: biggest area first
    remap = np.zeros(K, np.int64)
    remap[order] = np.arange(K)
    lab = remap[lab]

    # ---- exposure: share of nearby spots (within 1800 units) that can see each spot
    eye = nodes + np.array([0, 0, 26.0], np.float32)
    chest = nodes + np.array([0, 0, 8.0], np.float32)
    expo = np.zeros(N, np.float32)
    for i in range(N):
        d = np.linalg.norm(nodes - nodes[i], axis=1)
        cand = np.nonzero((d > 150) & (d < 1800))[0]
        if len(cand) > 100:
            cand = rng.choice(cand, 100, replace=False)
        if len(cand):
            expo[i] = env._los(eye[cand], np.repeat(chest[i:i + 1], len(cand), 0)).mean()

    # ---- items
    count = collections.Counter()
    items = []
    for k, d in enumerate(env.item_def):
        if d[4] is None:
            continue
        count[d[4]] += 1
        items.append(dict(k=k, label=d[4], pos=[round(float(v), 1) for v in env.item_pos[k]], respawn=d[2]))
    seen = collections.Counter()
    for it in items:
        seen[it["label"]] += 1
        it["name"] = it["label"] if count[it["label"]] == 1 else "{}{}".format(it["label"], seen[it["label"]])
        it["node"] = int(nearest(nodes, np.array([it["pos"]], np.float32))[0])
        it["area"] = int(lab[it["node"]])
    ipos = np.array([it["pos"] for it in items], np.float32)

    areas = []
    for j in range(K):
        idx = np.nonzero(lab == j)[0]
        c = nodes[idx].mean(0)
        centre = int(idx[np.linalg.norm(nodes[idx] - c, axis=1).argmin()])
        here = [it["name"] for it in items if it["area"] == j]
        near = int(np.linalg.norm(ipos - c, axis=1).argmin()) if len(items) else -1
        name = " + ".join(here) if here else "near {}".format(items[near]["name"]) if near >= 0 else "area"
        areas.append(dict(id=j, name=name, centre=[round(float(v)) for v in c], node=centre, spots=int(len(idx)),
                          height=round(float(c[2])), exposure=round(float(expo[idx].mean()), 3), items=here))
    nb = collections.defaultdict(set)
    for a, b, t, kind in edges:
        if lab[a] != lab[b]:
            nb[int(lab[a])].add(int(lab[b]))
    for a in areas:
        a["to"] = sorted(nb[a["id"]])
        a["reachable"] = bool(a["to"])

    # ---- routes on the graph: the fastest and distinct alternatives (edges of kept routes are made slower)
    eidx = {(a, b): k for k, (a, b, t, kind) in enumerate(edges)}
    routes = collections.defaultdict(list)                  # (area, item name) -> routes
    for a in areas:
        if not a["reachable"]:
            continue
        base, bprev = dijkstra(adj, a["node"], wt)
        for it in items:
            if it["area"] == a["id"] or not np.isfinite(base[it["node"]]):
                continue
            kept = []
            w = wt.copy()
            path = path_to(bprev, it["node"])
            for attempt in range(12):
                t = float(sum(wt[eidx[(p, q)]] for p, q in zip(path[:-1], path[1:])))
                ok = t <= ALT_TIME * base[it["node"]] + 1.0 and all(
                    len(set(path) & set(r["nodes"])) / max(1, min(len(path), len(r["nodes"]))) < ALT_OVERLAP
                    and dedup(lab[path]) != r["areas"] for r in kept)
                if ok:
                    kept.append(dict(areas=dedup(lab[path]), nodes=path, time=round(t, 2),
                                     exposure=round(float(expo[path].mean()), 3), source="graph"))
                if len(kept) >= MAX_ROUTES:
                    break
                for p, q in zip(path[:-1], path[1:]):
                    w[eidx[(p, q)]] *= 2.0
                _, pv = dijkstra(adj, a["node"], w)
                path = path_to(pv, it["node"])
            routes[(a["id"], it["name"])] = kept

    # ---- pro demos: trips to big items as area sequences, and where pros spend their time
    trips = collections.defaultdict(list)                   # (area, item name) -> [(areas tuple, seconds)]
    heat = np.zeros(K)
    files = sorted(glob.glob(os.path.join(demos_dir, mp, "*.bin")))
    used = 0
    for f in files:
        try:
            d = D.load(f)
        except Exception:
            continue
        pos, t = d["origin"], d["time"] / 1000.0
        if len(pos) < 400:
            continue
        used += 1
        normal = collections.Counter(d["pm_type"].tolist()).most_common(1)[0][0]
        alive = (d["pm_type"] == normal) & (d["stats"][:, 0] > 0)
        brk = np.ones(len(pos), bool)                        # True where a new stretch starts
        brk[1:] = (d["clientNum"][1:] != d["clientNum"][:-1]) | ~alive[1:] | ~alive[:-1] | (np.diff(t) > 0.5) | (np.diff(t) <= 0)
        area_t = lab[nearest(nodes, pos[::4])].repeat(4)[:len(pos)]
        heat += np.bincount(area_t[alive], minlength=K)
        dxy = np.linalg.norm(pos[:, None, :2] - ipos[None, :, :2], axis=2)
        dz = np.abs(pos[:, None, 2] - ipos[None, :, 2])
        at = (dxy < ARRIVE_XY) & (dz < ARRIVE_Z)
        away = np.linalg.norm(pos[:, None] - ipos[None], axis=2) > LEAVE
        start = 0
        armed = np.ones(len(items), bool)
        for i in range(len(pos)):
            if brk[i]:
                start = i
                armed[:] = True
            armed |= away[i]
            hit = np.nonzero(at[i] & armed)[0]
            if len(hit):
                k = int(hit[0])
                armed[k] = False
                s0 = max(start, int(np.searchsorted(t, t[i] - TRIP_MAX)))
                seq = area_t[s0:i + 1]
                # drop flicker: areas visited for fewer than 3 snapshots
                runs, j = [], s0
                for v, grp in ((v, list(g)) for v, g in __import__("itertools").groupby(seq.tolist())):
                    if len(grp) >= 3 or j == s0:
                        runs.append((v, j))
                    j += len(grp)
                ded = []
                for v, j in runs:
                    if not ded or ded[-1][0] != v:
                        ded.append((v, j))
                if ded and ded[-1][0] != items[k]["area"]:
                    ded.append((items[k]["area"], i))
                for q in range(len(ded) - 1):                # every area on the way is also a start of a route
                    key = (int(ded[q][0]), items[k]["name"])
                    trips[key].append((tuple(int(v) for v, _ in ded[q:]), float(t[i] - t[ded[q][1]])))
                start = i
    heat = heat / max(1.0, heat.sum())
    for a in areas:
        a["pro_time_share"] = round(float(heat[a["id"]]), 4)

    # ---- seed the preferences from the pro counts; add routes pros take that the search did not propose
    aexpo = np.array([a["exposure"] for a in areas])
    out_routes = {}
    n_pro_added = 0
    for (aid, name), kept in routes.items():
        tr = trips.get((aid, name), [])
        cnt = collections.Counter(s for s, _ in tr)
        for r in kept:
            r["pro_n"], r["pro_times"] = 0, []
        extra = collections.defaultdict(list)
        for seq, secs in tr:
            best, bj = None, 0.0
            for r in kept:
                jac = len(set(seq) & set(r["areas"])) / len(set(seq) | set(r["areas"]))
                if jac > bj:
                    best, bj = r, jac
            if best is not None and bj >= 0.6:
                best["pro_n"] += 1
                best["pro_times"].append(secs)
            else:
                extra[seq].append(secs)
        for seq, secs in extra.items():
            if len(secs) >= max(3, 0.05 * len(tr)) and len(kept) < MAX_ROUTES + 3:
                kept.append(dict(areas=list(seq), nodes=None, time=None, exposure=round(float(aexpo[list(seq)].mean()), 3),
                                 source="pro", pro_n=len(secs), pro_times=secs))
                n_pro_added += 1
        tot = sum(r["pro_n"] for r in kept)
        for r in kept:
            pt = r.pop("pro_times")
            r["pro_time"] = round(float(np.median(pt)), 2) if pt else None
            r["pref"] = round((r["pro_n"] + 1.0) / (tot + len(kept)), 3)        # seeded from pro play; to be learned
            r["bobby"] = dict(tries=0, arrived=0, time=None, damage=None)
        kept.sort(key=lambda r: -r["pref"])
        out_routes["{}>{}".format(aid, name)] = kept

    atlas = dict(map=mp, version=1, spots=N, demos=used, pro_trips=int(sum(len(v) for v in trips.values())),
                 areas=areas, items=[{k: v for k, v in it.items() if k != "k"} for it in items],
                 node_area=lab.tolist(), node_exposure=[round(float(v), 3) for v in expo],
                 teleporters=[dict(entrance=[round(float(v)) for v in a], exit=[round(float(v)) for v in b])
                              for a, b in zip(getattr(env, "tele_in", []), getattr(env, "tele_out", []))],
                 jump_pads=[[round(float(v)) for v in p] for p in getattr(env, "pads", [])],
                 routes=out_routes)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(atlas, open(os.path.join(out_dir, mp + ".json"), "w"), separators=(",", ":"))
    try:
        picture(atlas, nodes, os.path.join(out_dir, mp + ".png"))
    except Exception as e:                                   # a Python without a working matplotlib: use --picture
        print("picture not drawn ({}); run again with --picture".format(type(e).__name__))
    nr = [len(v) for v in out_routes.values()]
    print("{}: {} spots, {} areas, {} big items, {} demos, {} pro trips, {} (area, item) pairs, {:.1f} routes each, "
          "{} routes added from pro play".format(mp, N, K, len(items), used, atlas["pro_trips"], len(nr),
                                                 float(np.mean(nr)) if nr else 0, n_pro_added), flush=True)
    return atlas


def picture(atlas, nodes, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    lab = np.array(atlas["node_area"])
    fig, ax = plt.subplots(1, 3, figsize=(27, 9))
    cm = plt.get_cmap("tab20")
    ax[0].scatter(nodes[:, 0], nodes[:, 1], c=[cm(v % 20) for v in lab], s=14)
    ax[0].set_title("{}: areas (number = id, size of the text = nothing; see the JSON for names)".format(atlas["map"]))
    sh = np.array([a["pro_time_share"] for a in atlas["areas"]])
    ax[1].scatter(nodes[:, 0], nodes[:, 1], c=sh[lab], s=14, cmap="inferno")
    ax[1].set_title("share of time pro players spend in each area ({} demos)".format(atlas["demos"]))
    ax[2].scatter(nodes[:, 0], nodes[:, 1], c=nodes[:, 2], s=14, cmap="viridis")
    ax[2].set_title("height, and the route pros take most often to each big item (from the area they start in most)")
    by_item = collections.defaultdict(list)
    for key, rs in atlas["routes"].items():
        for r in rs:
            if r["nodes"] and r["pro_n"]:
                by_item[key.split(">")[1]].append(r)
    for name, rs in by_item.items():
        r = max(rs, key=lambda r: r["pro_n"] * len(r["areas"]))
        p = nodes[r["nodes"]]
        ax[2].plot(p[:, 0], p[:, 1], lw=2)
    for a in atlas["areas"]:
        ax[0].text(a["centre"][0], a["centre"][1], str(a["id"]), fontsize=11, weight="bold", ha="center")
    for k in range(3):
        for it in atlas["items"]:
            ax[k].text(it["pos"][0], it["pos"][1], it["name"], fontsize=9, color="red", weight="bold",
                       bbox=dict(facecolor="white", alpha=0.7, pad=1, lw=0))
        ax[k].set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default="bloodrun,aerowalk,campgrounds")
    ap.add_argument("--demos", default=os.path.join(ROOT, "data", "demos_parsed"))
    ap.add_argument("--out", default=os.path.join(ROOT, "maps", "atlas"))
    ap.add_argument("--picture", action="store_true", help="only redraw the pictures from the JSON files")
    a = ap.parse_args()
    if a.picture:
        for mp in a.maps.split(","):
            nav = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))))
            picture(json.load(open(os.path.join(a.out, mp + ".json"))), np.array(nav["nodes"], np.float32),
                    os.path.join(a.out, mp + ".png"))
        sys.exit(0)
    for mp in a.maps.split(","):                             # one map per process: simulator worlds share buffers
        if len(a.maps.split(",")) > 1:
            __import__("subprocess").run([sys.executable, os.path.abspath(__file__), "--maps", mp, "--demos", a.demos, "--out", a.out])
        else:
            build(mp, a.demos, a.out)

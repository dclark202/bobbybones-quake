"""A top-down picture of a map for the map reader (sim/map_reader.py), on the simulator's own cell grid (64 units,
two height layers, as duel_env._cell numbers them), with the facts the reader learns to predict from it.

    python tools/map_raster.py [--maps arena1,bloodrun] [--all]          (Anaconda Python; needs data/maps/nav_<map>_sim.json)

Per map -> data/maps/raster_<map>.npz:
  x      (2 layers, CH channels, ny, nx)  the picture: walkable floor, floor height, solid, hazard (trigger_hurt), jump
         pad, where a pad lands, teleporter in, teleporter out, spawn point, and one channel per item kind
  y      (2, LAB, ny, nx)  the facts, where known (mask): seconds of travel to the mega, the red armor, rockets, rail,
         lightning; openness (share of 24 walkable cells in sight); height above the lowest floor; distance to the
         nearest hazard; distance to the nearest spawn point
  mask   (2, ny, nx)  cells with walkable floor
  lo, cell_n, zmid   the grid, so the reader's output can be written back as the per-map cell table
"""
import argparse
import ctypes
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

CHANNELS = ["walkable", "height", "solid", "hazard", "pad", "pad_landing", "tele_in", "tele_out", "spawn",
            "MH", "RA", "YA", "GA", "RL", "RG", "LG", "SG", "GL", "PG", "HMG", "health_small", "shard_bubble", "ammo", "other"]
LABELS = ["t_MH", "t_RA", "t_RL", "t_RG", "t_LG", "openness", "height_above_floor", "d_hazard", "d_spawn"]


def build(E, name):
    bsp = os.path.join(ROOT, "data", "maps", name + ".bsp")
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(name))
    if not (os.path.exists(bsp) and os.path.exists(nav)):
        return None
    env = E.DuelEnv(bsp, n_matches=1, seed=1, nav=nav)
    nx, ny = int(env.cell_n[0]), int(env.cell_n[1])
    lo, cell, zmid = env.lo.astype(np.float32), float(E.CELL_SIZE), env.cell_zmid
    x = np.zeros((2, len(CHANNELS), ny, nx), np.float32)
    y = np.zeros((2, len(LABELS), ny, nx), np.float32)
    mask = np.zeros((2, ny, nx), bool)
    ch = {c: i for i, c in enumerate(CHANNELS)}
    w = env.w

    def cell_of(p):
        c = np.clip(((np.asarray(p, np.float32)[:2] - lo[:2]) / cell).astype(int), 0, [nx - 1, ny - 1])
        return (1 if p[2] > zmid else 0), int(c[1]), int(c[0])

    # walkable floor and its height, from the nav nodes
    nodes = env.route.nodes if env.route is not None else np.array(env.spots, np.float32)
    zfloor = np.full((2, ny, nx), np.nan, np.float32)
    for p in nodes:
        L, cy, cx = cell_of(p)
        mask[L, cy, cx] = True
        zfloor[L, cy, cx] = p[2] if np.isnan(zfloor[L, cy, cx]) else min(zfloor[L, cy, cx], p[2])
    zlow = float(np.nanmin(zfloor)) if mask.any() else float(lo[2])
    x[:, ch["walkable"]] = mask
    x[:, ch["height"]] = np.where(mask, (np.nan_to_num(zfloor, nan=zlow) - zlow) / 512.0, 0.0)
    # solid at the cell centre of each layer (the walls as the player meets them)
    if hasattr(w.lib, "qsim_contents"):
        w.lib.qsim_contents.argtypes = [np.ctypeslib.ndpointer(np.float32, flags="C")]
        w.lib.qsim_contents.restype = ctypes.c_int
        zc = (lo[2] + zmid) / 2.0, (zmid + env.hi[2]) / 2.0
        for L in range(2):
            for cy in range(ny):
                for cx in range(nx):
                    pt = np.array([lo[0] + (cx + 0.5) * cell, lo[1] + (cy + 0.5) * cell, zc[L]], np.float32)
                    x[L, ch["solid"], cy, cx] = 1.0 if (w.lib.qsim_contents(pt) & 1) else 0.0
    # hazards: trigger_hurt brushes (their bounds), plus the rooms file of our own maps
    hz = []
    if hasattr(w.lib, "qsim_model_bounds"):
        w.lib.qsim_model_bounds.argtypes = [ctypes.c_int, np.ctypeslib.ndpointer(np.float32, flags="C")]
        for e in w.entities:
            if e.get("classname") == "trigger_hurt" and e.get("model", "").startswith("*"):
                b = np.zeros(6, np.float32)
                w.lib.qsim_model_bounds(int(e["model"][1:]), b)
                hz.append(b)
    for b in list(hz) + [np.asarray(z[:6], np.float32) for z in getattr(env, "hurt_zones", [])]:
        c0 = np.clip(((b[:2] - lo[:2]) / cell).astype(int), 0, [nx - 1, ny - 1])
        c1 = np.clip(((b[3:5] - lo[:2]) / cell).astype(int), 0, [nx - 1, ny - 1])
        for L in range(2):
            zr = (lo[2], zmid) if L == 0 else (zmid, env.hi[2])
            if b[5] >= zr[0] and b[2] <= zr[1]:
                x[L, ch["hazard"], c0[1]:c1[1] + 1, c0[0]:c1[0] + 1] = 1.0
    # pads, teleporters, spawns
    for kind, c, d in (w.trigger_spots() if hasattr(w, "trigger_spots") else []):
        L, cy, cx = cell_of(c)
        x[L, ch["pad" if kind == 0 else "tele_in"], cy, cx] = 1.0
        L, cy, cx = cell_of(d)
        x[L, ch["pad_landing" if kind == 0 else "tele_out"], cy, cx] = 1.0
    for p in env.spawns:
        L, cy, cx = cell_of(p)
        x[L, ch["spawn"], cy, cx] = 1.0
    # items
    for k, (kind, val, resp, cap, lab) in enumerate(env.item_def):
        p = env.item_pos[k]
        L, cy, cx = cell_of(p)
        if lab in ch:
            name_ = lab
        elif kind == "wp":
            name_ = E.WEAPONS[int(val)].upper()
            name_ = name_ if name_ in ch else "other"
        elif kind in ("hp", "ar") and val == 5:
            name_ = "shard_bubble"
        elif kind == "hp":
            name_ = "health_small"
        elif kind in ("am", "pack"):
            name_ = "ammo"
        else:
            name_ = "other"
        x[L, ch[name_], cy, cx] = 1.0
    # ---- the facts
    R = env.route
    centres = []
    for L in range(2):
        for cy in range(ny):
            for cx in range(nx):
                if mask[L, cy, cx]:
                    centres.append((L, cy, cx, np.array([lo[0] + (cx + 0.5) * cell, lo[1] + (cy + 0.5) * cell, zfloor[L, cy, cx] + 26.0], np.float32)))
    P = np.array([c[3] for c in centres], np.float32)
    if R is not None and len(P):
        node = R.locate(P)
        for gi, lab in enumerate(env.route_goal):
            if lab in ("MH", "RA", "RL", "RG", "LG"):
                t = R.T[gi, node]
                col = LABELS.index("t_" + lab)
                for (L, cy, cx, _), tv in zip(centres, t):
                    y[L, col, cy, cx] = min(tv, 30.0) / 10.0 if tv < 1e8 else -1.0
    for col in range(5):                                       # goals the map does not have: unknown
        if not np.any(y[:, col]):
            y[:, col] = -1.0
    rng = np.random.default_rng(3)
    if len(P) > 1:
        samp = P[rng.choice(len(P), min(24, len(P)), replace=False)]
        for (L, cy, cx, p) in centres:
            seen = sum(1 for q in samp if w.trace(p, q)["fraction"] >= 0.999)
            y[L, LABELS.index("openness"), cy, cx] = seen / len(samp)
            y[L, LABELS.index("height_above_floor"), cy, cx] = (p[2] - 26.0 - zlow) / 512.0
    hzc = np.argwhere(x[:, ch["hazard"]] > 0)
    spc = np.argwhere(x[:, ch["spawn"]] > 0)
    for (L, cy, cx, p) in centres:
        if len(hzc):
            d = np.sqrt(((hzc[:, 1:] - np.array([cy, cx])) ** 2).sum(1)).min() * cell
            y[L, LABELS.index("d_hazard"), cy, cx] = min(d, 1024.0) / 512.0
        else:
            y[L, LABELS.index("d_hazard"), cy, cx] = 2.0
        if len(spc):
            d = np.sqrt(((spc[:, 1:] - np.array([cy, cx])) ** 2).sum(1)).min() * cell
            y[L, LABELS.index("d_spawn"), cy, cx] = min(d, 2000.0) / 1000.0
    return dict(x=x, y=y, mask=mask, lo=lo, cell_n=env.cell_n.astype(np.int64), zmid=np.float32(zmid), zlow=np.float32(zlow),
                channels=np.array(CHANNELS), labels=np.array(LABELS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default="")
    ap.add_argument("--all", action="store_true", help="every map in docs/MAPS.md plus arena1")
    a = ap.parse_args()
    E = importlib.import_module("duel_env")
    names = [m for m in a.maps.split(",") if m]
    if a.all:
        names = ["arena1"] + [l[2:].strip() for l in open(os.path.join(ROOT, "docs", "MAPS.md")) if l.startswith("- ")]
    for name in names:
        out = os.path.join(ROOT, "data", "maps", "raster_{}.npz".format(name))
        try:
            r = build(E, name)
        except Exception as e:                                 # noqa: BLE001
            print("{}: failed: {!r}".format(name, e), flush=True)
            continue
        if r is None:
            print("{}: no map or walking map".format(name), flush=True)
            continue
        np.savez_compressed(out, **r)
        print("{}: {} x {} cells, {} walkable, items {}, hazards {}".format(
            name, r["cell_n"][0], r["cell_n"][1], int(r["mask"].sum()), int(r["x"][:, 9:].sum()), int(r["x"][:, 3].sum())), flush=True)


if __name__ == "__main__":
    main()

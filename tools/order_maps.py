"""1.7, the combat order (docs/runs/1.7/BUILD.md, part 2): a map's numbers for the order's candidates, from the simulator's own collision
(qsim, with the solid pieces as SOLIDS=1 and the shots' and the eye's mask as SHOT_MASK=1: CONTENTS_SOLID), written to
sim/order_maps/<map>.npz:

  vis        [points, ceil(points / 8)] uint8  line of sight between every two points of the walking map (nav_<map>_sim.json), both
                                               standing (eye VIEW_H above the point): row i, bit j (np.packbits, big end first)
  door_*     the doorways: the walking map's links (walk, air) that join two zones (sim/zones/<map>.json), gathered by zone pair
             and place (links whose middles lie within DOOR_JOIN units of a doorway's first are that doorway): pos [k, 3], node
             [k], zones [k, 2], dir [k, 2] (across it, on the floor), width [k] (traces across it at eye height, each side up to
             WIDTH_MAX), corridor [k] (under CORRIDOR units wide)
  tele_*     the teleporters (the map's triggers): in [k, 3], out [k, 3], in_node, out_node
  spam_*     the spam points: the doorways, the teleporter exits and the pros' blind-shot spots (sim/pro_places/<map>_rl, _gl, _pg:
             where they fired from most and its share, their shots there by weapon): pos [k, 3], node, kind [k] (0 doorway, 1
             teleporter exit, 2 the pros' spot), corridor, width, pro_w [k, 3] (rockets, grenades, plasma: the share of the
             map's blind shots of that weapon at it, percent), from_pos [k, 3] (where the pros fired from most; the point
             itself otherwise), fire [k, ceil(points / 8)] (the points of the walking map with a line of fire to it, body high,
             within SPAM_RANGE units)
  out_*      the ways out: the zones' middles (the zone's point nearest its centre), the doorways, the holding places
             (sim/pro_holds/<map>.json), the teleporter entrances: pos [k, 3], node [k], kind [k] (0 zone, 1 doorway, 2 holding
             place, 3 teleporter entrance)
  hold_node  [8] the holding places' points (their lanes: those rows of vis)
  walk_t     [points, points] float16: the seconds of way from point j to point i (row i, column j) on the simulator's own walking map
             (the RouteField of a DuelEnv made with the run's settings: its links, lava, drops, teleporters as the run has them;
             the same search as RouteField.add_goals), WALK_NONE where there is no way
  nodes      the walking map's points (a check: the simulator refuses a table made for another walking map)

    python tools/order_maps.py --map bloodrun [--map aerowalk ...] [--all] [--cmd <the run's train.cmd> --run-dir <its folder>]
    (CPU; the cores it is started on. --cmd/--run-dir: whose settings the walking map is made with; default 1.6a's)
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
OUT = os.path.join(ROOT, "sim", "order_maps")
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure",
        "houseofdecay", "dismemberment")
VIEW_H = 26.0                    # (duel_env.VIEW_H)
BODY_H = 16.0                    # a spam point's height above the floor point: where a body is hit
SOLID = 1                        # CONTENTS_SOLID (duel_env.SOLID_ONLY: SHOT_MASK=1)
DOOR_JOIN = 192.0
WIDTH_MAX = 800.0
CORRIDOR = 192.0
SPAM_RANGE = 1500.0
CHUNK = 400000
WALK_NONE = 60000.0
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")


def eye(p):
    e = np.asarray(p, np.float32).copy()
    e[..., 2] += VIEW_H
    return e


def nearest(nodes, p, live=None):
    d = np.linalg.norm(nodes[None, :, :] - np.asarray(p, np.float32).reshape(-1, 1, 3), axis=2)
    if live is not None:
        d = np.where(live[None, :], d, 1e9)
    return d.argmin(1)


def vis_table(w, nodes):
    """line of sight between every two points (the upper triangle traced, mirrored)"""
    n = len(nodes)
    E = eye(nodes)
    V = np.zeros((n, n), bool)
    iu, ju = np.triu_indices(n, 1)
    for k in range(0, len(iu), CHUNK):
        a, b = iu[k:k + CHUNK], ju[k:k + CHUNK]
        f = w.lines(E[a], E[b], SOLID)
        ok = f >= 0.999
        V[a[ok], b[ok]] = True
    V = V | V.T
    V[np.arange(n), np.arange(n)] = True
    return V


def doorways(w, nodes, edges, nz):
    """the links that join two zones, gathered by zone pair and place"""
    by = {}
    for a, b, t, kind in edges:
        if kind == "tele" or nz[a] < 0 or nz[b] < 0 or nz[a] == nz[b]:
            continue
        za, zb = sorted((int(nz[a]), int(nz[b])))
        mid = (nodes[a] + nodes[b]) / 2.0
        d = nodes[b] - nodes[a] if nz[a] == za else nodes[a] - nodes[b]          # (from the lower zone to the higher)
        by.setdefault((za, zb), []).append((mid, d[:2]))
    pos, zones, dirs = [], [], []
    for (za, zb), L in sorted(by.items()):
        left = list(L)
        while left:
            m0 = left[0][0]
            grp = [x for x in left if np.linalg.norm(x[0] - m0) < DOOR_JOIN]
            left = [x for x in left if np.linalg.norm(x[0] - m0) >= DOOR_JOIN]
            pos.append(np.mean([x[0] for x in grp], 0))
            d = np.sum([x[1] / max(1e-6, np.linalg.norm(x[1])) for x in grp], 0)
            dirs.append(d / max(1e-6, np.linalg.norm(d)))
            zones.append((za, zb))
    if not pos:
        return (np.zeros((0, 3), np.float32), np.zeros(0, np.int64), np.zeros((0, 2), np.int64), np.zeros((0, 2), np.float32),
                np.zeros(0, np.float32))
    pos, dirs = np.array(pos, np.float32), np.array(dirs, np.float32)
    node = nearest(nodes, pos)
    E = eye(nodes[node])
    perp = np.stack([-dirs[:, 1], dirs[:, 0], np.zeros(len(dirs), np.float32)], 1)
    fl = w.lines(E, E + perp * WIDTH_MAX, SOLID) * WIDTH_MAX
    fr = w.lines(E, E - perp * WIDTH_MAX, SOLID) * WIDTH_MAX
    return pos, node, np.array(zones, np.int64), dirs, (fl + fr).astype(np.float32)


def fire_rows(w, nodes, pts):
    """for each point, the walking map's points with a line of fire to it (body high) within SPAM_RANGE"""
    E = eye(nodes)
    out = np.zeros((len(pts), len(nodes)), bool)
    for i, p in enumerate(pts):
        tg = np.asarray(p, np.float32) + np.array([0, 0, BODY_H], np.float32)
        near = np.nonzero(np.linalg.norm(E - tg[None, :], axis=1) < SPAM_RANGE)[0]
        if len(near):
            f = w.lines(E[near], np.repeat(tg[None, :], len(near), 0), SOLID)
            out[i, near[f >= 0.999]] = True
    return out


def pro_spots(name):
    """the pros' blind-shot spots of every weapon: place, where they fired from most, their share of the map's blind shots of
    that weapon there (percent)"""
    pos, frm, pw = [], [], []
    for j, w_ in enumerate(("rl", "gl", "pg")):
        p_ = os.path.join(ROOT, "sim", "pro_places", "{}_{}.json".format(name, w_))
        if not os.path.exists(p_):
            continue
        for pl in json.load(open(p_, encoding="utf-8")).get("places") or []:
            if pl.get("pos") is None:
                continue
            ff = sorted(pl.get("fired_from") or [], key=lambda x: -float(x.get("share") or 0.0))
            row = np.zeros(3, np.float32)
            row[j] = float(pl.get("share") or 0.0)
            pos.append(pl["pos"])
            frm.append(ff[0]["pos"] if ff else pl["pos"])
            pw.append(row)
    if not pos:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    return np.array(pos, np.float32), np.array(frm, np.float32), np.array(pw, np.float32)


def walk_table(name, cmd, run_dir):
    """the seconds of way between every two points, on the walking map a DuelEnv with the run's settings makes"""
    import heapq
    import importlib
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(cmd, run_dir)
    os.environ.update(envv)
    E = importlib.import_module("duel_env")
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(name))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", name + ".bsp"), n_matches=1, seed=7, loadout="all", nav=nav)
    R = env.route
    n = len(R.nodes)
    T = np.full((n, n), WALK_NONE, np.float32)
    for b in range(n):
        if R.dead[b]:
            continue
        dist, pq = {b: 0.0}, [(0.0, b)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            for v, c in R.radj[u]:
                if d + c < dist.get(v, 1e18):
                    dist[v] = d + c
                    heapq.heappush(pq, (d + c, v))
        for v, d in dist.items():
            T[b, v] = min(d, WALK_NONE)
    return R.nodes, T.astype(np.float16)


def build(name, cmd, run_dir):
    import qsim
    t0 = time.time()
    bsp = os.path.join(ROOT, "data", "maps", name + ".bsp")
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(name))
    zf = os.path.join(ROOT, "sim", "zones", name + ".json")
    if not (os.path.exists(bsp) and os.path.exists(nav) and os.path.exists(zf)):
        print("{}: no map, walking map or zones: skipped".format(name), flush=True)
        return None
    g = json.load(open(nav))
    nodes = np.array(g["nodes"], np.float32)
    zd = json.load(open(zf, encoding="utf-8"))
    nz = np.array(zd.get("node_zone") or [], np.int64)
    assert len(nz) == len(nodes), "{}: the zones' points ({}) are not the walking map's ({})".format(name, len(nz), len(nodes))
    w = qsim.World(bsp)
    if hasattr(w, "add_solids"):
        w.add_solids()                                       # (SOLIDS=1: the map's solid pieces, the automatic doors open)
    V = vis_table(w, nodes)
    dp, dn, dz, dd, dw = doorways(w, nodes, g["edges"], nz)
    spots = w.trigger_spots() if hasattr(w, "trigger_spots") else []
    tin = np.array([c for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
    tout = np.array([d for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
    tin_n, tout_n = (nearest(nodes, tin) if len(tin) else np.zeros(0, np.int64)), (nearest(nodes, tout) if len(tout) else np.zeros(0, np.int64))
    pp, pf, pw = pro_spots(name)
    sp_pos = np.concatenate([dp, nodes[tout_n] if len(tout_n) else np.zeros((0, 3), np.float32), pp]).astype(np.float32)
    sp_kind = np.concatenate([np.zeros(len(dp)), np.ones(len(tout_n)), np.full(len(pp), 2)]).astype(np.int64)
    sp_corr = np.concatenate([dw < CORRIDOR, np.zeros(len(tout_n) + len(pp), bool)])
    sp_width = np.concatenate([dw, np.zeros(len(tout_n) + len(pp), np.float32)]).astype(np.float32)
    sp_pw = np.concatenate([np.zeros((len(dp) + len(tout_n), 3), np.float32), pw]).astype(np.float32)
    sp_from = np.concatenate([sp_pos[:len(dp) + len(tout_n)], pf]).astype(np.float32)
    sp_node = nearest(nodes, sp_pos) if len(sp_pos) else np.zeros(0, np.int64)
    fire = fire_rows(w, nodes, sp_pos)
    cen = np.array(zd["centres"], np.float32).reshape(-1, 3)
    zn = []
    for z_ in range(len(cen)):                               # (the zone's point nearest its centre)
        m_ = nz == z_
        zn.append(int(np.nonzero(m_)[0][np.linalg.norm(nodes[m_] - cen[z_], axis=1).argmin()]) if m_.any() else int(nearest(nodes, cen[z_:z_ + 1])[0]))
    hf = os.path.join(ROOT, "sim", "pro_holds", name + ".json")
    hn = np.array([int(p["node"]) for p in (json.load(open(hf, encoding="utf-8")).get("places") or [])[:8]], np.int64) if os.path.exists(hf) else np.zeros(0, np.int64)
    out_node = np.concatenate([np.array(zn, np.int64), dn, hn, tin_n]).astype(np.int64)
    out_kind = np.concatenate([np.zeros(len(zn)), np.ones(len(dn)), np.full(len(hn), 2), np.full(len(tin_n), 3)]).astype(np.int64)
    wn_, WT = walk_table(name, cmd, run_dir)
    assert len(wn_) == len(nodes) and np.allclose(wn_, nodes), "{}: the simulator's walking map is not nav_{}_sim.json's".format(name, name)
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(os.path.join(OUT, name + ".npz"), nodes=nodes, vis=np.packbits(V, axis=1), walk_t=WT,
                        door_pos=dp, door_node=dn, door_zones=dz, door_dir=dd, door_width=dw, door_corridor=dw < CORRIDOR,
                        tele_in=tin, tele_out=tout, tele_in_node=tin_n, tele_out_node=tout_n,
                        spam_pos=sp_pos, spam_node=sp_node, spam_kind=sp_kind, spam_corridor=sp_corr, spam_width=sp_width, spam_pro_w=sp_pw,
                        spam_from=sp_from, spam_fire=np.packbits(fire, axis=1),
                        out_pos=nodes[out_node], out_node=out_node, out_kind=out_kind, hold_node=hn)
    print("{}: {} points, {:.1%} of pairs in sight; {} doorways ({} corridors), {} teleporters, {} spam points ({} the pros'), "
          "{} ways out, {} holding places; walking: {:.1%} of pairs with a way, median {:.1f} s; {:.0f} s".format(
              name, len(nodes), float(V.mean()), len(dp), int((dw < CORRIDOR).sum()), len(tin), len(sp_pos), len(pp), len(out_node), len(hn),
              float((WT < WALK_NONE).mean()), float(np.median(WT[WT < WALK_NONE].astype(np.float32))), time.time() - t0), flush=True)
    return V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cmd", default=os.path.join(MAIN, "docs", "runs", "1.6", "1.6a", "train.cmd"))
    ap.add_argument("--run-dir", default=os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_6a"))
    a = ap.parse_args()
    for m in (MAPS if a.all else a.map):
        build(m, a.cmd, a.run_dir)


if __name__ == "__main__":
    main()

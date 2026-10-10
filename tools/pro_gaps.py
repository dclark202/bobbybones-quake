"""The pros' jumps that a walker cannot make, per duel map (BACKLOG B-204): the list the jump training of v15 is built on.

    python tools/pro_gaps.py --map bloodrun,aerowalk,lostworld [--limit 250]   -> sim/pro_gaps/<map>.json, docs/pro_gaps.json

From the light demo sets (sim/demo_dataset.py --lite): every jump (his height begins to rise at a jump's speed) and
where it lands (his feet on a floor again). A jump is kept when its straight line passes over a hole of 40 units or
more, or it lands 40 or more higher than it began, and the walking map (sim/build_nav.py: a run and a jump from
standing) has no way from its take-off to its landing, or one that takes a second longer than the flight ("cannot",
"slower"); and, seen 30 times or more, the gaps of 200 units or more over a hole of 100 that the walking map crosses
nearly as fast: by a jump of its own from the very edge ("just makes it": Blood Run's red armor) or by "a way beside
it"; and the jumps "up a ledge" of 30 units or more where the walking map has stairs or a way round (not in use unless
an entry says "use": true: Blood Run's stairs to the yellow armor). Jumps with
the same take-off and landing places are one entry: where from, where to, how long and how high, the speed over the
ground at take-off (a tenth, the middle, nine tenths of the pros'), the speed it needs (length over seconds in the air
of the slowest tenth that made it), the seconds in the air, the walker's seconds for the same, how often, and how many
seconds sooner each big item is reached by it. An entry's "use" (true or false, set by hand in the file: it overrides
sim/jump_links.py's rule of how often a jump must be seen) is kept when the list is written again. Jump pads, rocket jumps and two hops read as one are left out.
No player names are read or written.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
DT = 0.025                                                     # the demos' frames (40 a second)
V14 = dict(SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1",
           PRO_ITEMS="1", AMMO_PACKS="0")                      # the walking map as v14 has it
HOLE, RISE, SAVES = 40.0, 40.0, 1.0
CELL = 96.0


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def floor_under(w, pts, reach=400.0):
    """how far under each point the floor is (reach where there is none within it)"""
    down = np.array([[[0.0, 0.0, -1.0]]], np.float32)
    out = np.zeros(len(pts), np.float32)
    for c in range(0, len(pts), 4096):
        p = np.ascontiguousarray(pts[c:c + 4096], np.float32)
        out[c:c + 4096] = w.rays_each(p, np.repeat(down, len(p), 0), reach)[:, 0] * reach
    return out


MIN_SEEN = [5, 30]                                             # an entry is listed when seen this often: a walker cannot or is slower; the rest


def build(mp, limit):
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=0,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    R, w = env.route, env.w
    labels = list(env.route_goal)
    names = []
    for d_ in env.item_def:                                     # a short name per item, for "near what"
        names.append(E.WEAPONS[int(d_[1])].upper() if d_[0] == "wp" else (d_[4] if d_[4] else str(d_[0])))
    big = [k for k, nm in enumerate(names) if nm in ("MH", "RA", "YA", "YA2", "RL", "RG", "LG", "GL", "PG", "SG")]
    pads = np.array([c for k, c, d in w.trigger_spots() if k == 0], np.float32).reshape(-1, 3)
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
    if limit and len(files) > limit:
        files = files[::max(1, len(files) // limit)][:limit]
    rows, minutes, jumps_all = [], 0.0, 0
    for fi, f in enumerate(files):
        try:
            d = np.load(f)
            L, first = d["lite"], d["first"]
        except Exception:                                       # noqa: BLE001
            continue
        if len(L) < 400:
            continue
        pos, hp = L[:, 5:8].astype(np.float32), L[:, 0]
        minutes += len(L) * DT / 60.0
        dp = np.diff(pos, axis=0)
        hstep = np.hypot(dp[:, 0], dp[:, 1])
        cut = first[1:] | (hp[1:] <= 0) | (hp[:-1] <= 0) | (hstep > 60.0) | (np.abs(dp[:, 2]) > 60.0)   # a respawn, a teleporter
        vz, sp = dp[:, 2] / DT, hstep / DT                      # from frame t to t + 1
        fl = floor_under(w, pos)                                # his origin is 24 above his feet
        for ox, oy in ((14.0, 14.0), (14.0, -14.0), (-14.0, 14.0), (-14.0, -14.0)):    # his box stands on a ledge's edge
            fl = np.minimum(fl, floor_under(w, pos + np.array([ox, oy, 0.0], np.float32)))   # where the middle is past it
        start = np.zeros(len(pos), bool)
        start[1:-1] = (vz[1:] > 180.0) & (vz[1:] < 400.0) & (vz[:-1] < 100.0) & ~cut[1:] & ~cut[:-1]
        down_ = np.zeros(len(pos), bool)                        # frames at which he stands or has just touched down
        down_[1:] = (fl[1:] <= 27.0) | ((fl[1:] <= 34.0) & (np.concatenate([vz[1:], [0.0]]) > -60.0))
        cand = np.nonzero(down_)[0]
        cuts = np.nonzero(cut)[0]
        t0s = np.nonzero(start)[0]
        jumps_all += len(t0s)
        if not len(t0s) or not len(cand):
            continue
        k = np.searchsorted(cand, t0s + 4)
        ok = k < len(cand)
        t0s, t1s = t0s[ok], cand[k[ok]]
        ok = (t1s - t0s <= int(2.5 / DT))
        nc = np.searchsorted(cuts, t1s) - np.searchsorted(cuts, t0s - 2)       # no cut between
        ok &= nc == 0
        t0s, t1s = t0s[ok], t1s[ok]
        if not len(t0s):
            continue
        if len(pads):                                           # a jump pad's throw is not a jump
            dpad = np.linalg.norm(pos[t0s][:, None, :] - pads[None, :, :], axis=2).min(1)
            keep = dpad > 110.0
            t0s, t1s = t0s[keep], t1s[keep]
        p0, p1 = pos[t0s], pos[t1s]
        dist = np.hypot(p1[:, 0] - p0[:, 0], p1[:, 1] - p0[:, 1])
        rise = p1[:, 2] - p0[:, 2]
        keep = dist > 96.0
        t0s, t1s, p0, p1, dist, rise = t0s[keep], t1s[keep], p0[keep], p1[keep], dist[keep], rise[keep]
        if not len(t0s):
            continue
        # the floor under the straight line: a hole when it lies 40 or more under the lower end's floor
        fr = np.linspace(0.15, 0.85, 6, dtype=np.float32)
        P = p0[:, None, :] + (p1 - p0)[:, None, :] * fr[None, :, None]
        P[:, :, 2] = np.maximum(p0[:, 2], p1[:, 2])[:, None]
        under = floor_under(w, P.reshape(-1, 3), 600.0).reshape(len(t0s), 6)
        floor_z = P[:, :, 2] - under                            # the floor's height under each point of the line
        low_end = np.minimum(p0[:, 2], p1[:, 2]) - 24.0
        hole = low_end - floor_z.min(1)                         # how deep the deepest place is under the lower end
        keep = (hole >= HOLE) | (rise >= RISE)
        for j in np.nonzero(keep)[0]:
            t0 = int(t0s[j])
            v0 = float(sp[max(0, t0 - 1):t0 + 1].mean())
            rows.append((p0[j, 0], p0[j, 1], p0[j, 2], p1[j, 0], p1[j, 1], p1[j, 2], dist[j], rise[j], v0,
                         (int(t1s[j]) - t0) * DT, hole[j], fi))
        if fi % 50 == 0:
            print("  {} {}/{} demos, {} jumps over a hole or up".format(mp, fi, len(files), len(rows)), flush=True)
    A = np.array(rows, np.float32).reshape(-1, 12)
    A = A[A[:, 7] <= 56.0]                                      # higher than a jump lifts him: a pad or a rocket jump
    # one flight: no longer in the air than a jump lasts to that height (the game lets his feet step 18 up onto the far
    # edge while he falls); longer is two hops whose touch between was missed
    t_one = (275.0 + np.sqrt(np.maximum(0.0, 275.0 ** 2 - 1600.0 * (A[:, 7] - 18.0)))) / 800.0
    A = A[A[:, 9] <= t_one + 0.12]
    if os.environ.get("GAPS_DUMP"):
        np.save(os.path.join(os.environ["GAPS_DUMP"], "gaps_{}.npy".format(mp)), A)
    res = dict(map=mp, demos=len(files), player_minutes=round(minutes), jumps_seen=int(jumps_all), over_a_hole_or_up=int(len(A)), jumps=[])
    if not len(A):
        return res
    na, nb = R.locate(A[:, 0:3]), R.locate(A[:, 3:6])
    tw = np.array([float(R.from_node(int(a))[int(b)]) for a, b in zip(na, nb)], np.float32)   # the walker's seconds for the same
    hard = (tw - A[:, 9] >= SAVES)
    edge = ~hard & (A[:, 10] >= 100.0) & (A[:, 6] >= 200.0)     # a real gap that a walker's jump just makes (from the very edge)
    res["a_walker_cannot_or_a_second_slower"] = int(hard.sum())
    res["a_walker_just_makes"] = int(edge.sum())
    up = ~hard & ~edge & (A[:, 7] >= 30.0)                       # up a ledge or onto stairs where a walker's way is nearly as fast
    res["up_a_ledge_beside_a_way"] = int(up.sum())
    keep = hard | edge | up
    A, na, nb, tw, hard, up = A[keep], na[keep], nb[keep], tw[keep], hard[keep], up[keep]
    # one entry per take-off and landing place
    key = [tuple(int(v) for v in np.concatenate([np.floor(r[0:2] / CELL), [np.floor(r[2] / 64.0)], np.floor(r[3:5] / CELL), [np.floor(r[5] / 64.0)]])) + (2 if h else (0 if u else 1),)
           for r, h, u in zip(A, hard, up)]
    groups = {}
    for i, k_ in enumerate(key):
        groups.setdefault(k_, []).append(i)
    cl = [dict(idx=v, a=np.median(A[v, 0:3], axis=0), b=np.median(A[v, 3:6], axis=0), hard=k_[-1]) for k_, v in groups.items()]
    cl.sort(key=lambda c: -len(c["idx"]))
    merged = []
    for c in cl:                                                # neighbouring cells of one jump: to the bigger entry
        for m in merged:
            if m["hard"] == c["hard"] and np.linalg.norm(m["a"] - c["a"]) < 110.0 and np.linalg.norm(m["b"] - c["b"]) < 110.0:
                m["idx"] += c["idx"]
                break
        else:
            merged.append(c)
    merged.sort(key=lambda c: (c["hard"] == 0, -len(c["idx"])))   # (the jumps up a ledge after the others: the others keep their numbers)
    ipos = np.asarray(env.item_pos, np.float32).reshape(-1, 3)
    g_ = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))))
    air_e = np.array([(e[0], e[1]) for e in g_["edges"] if e[3] == "air"], np.int64).reshape(-1, 2)   # the walker's own jumps and drops

    def near(p):
        if not len(big):
            return ""
        dd = np.linalg.norm(ipos[big] - p, axis=1)
        return "{} ({:.0f})".format(names[big[int(dd.argmin())]], float(dd.min())) if dd.min() < 500 else ""
    for c in merged:
        v = np.array(c["idx"])
        if len(v) < (MIN_SEEN[0] if c["hard"] == 2 else MIN_SEEN[1]):
            continue
        a_med, b_med = np.median(A[v, 0:3], axis=0), np.median(A[v, 3:6], axis=0)
        an, bn = np.bincount(na[v]).argmax(), np.bincount(nb[v]).argmax()
        ta = float(np.median(A[v, 9]))
        twm = float(np.median(tw[v]))
        direct = bool(len(air_e)) and bool(((np.linalg.norm(R.nodes[air_e[:, 0]] - a_med, axis=1) < 70.0)
                                            & (np.linalg.norm(R.nodes[air_e[:, 1]] - b_med, axis=1) < 90.0)).any())
        serves = {}
        for g, lab in enumerate(labels):
            gain = float(R.T_walk[g, an]) - (ta + float(R.T_walk[g, bn]))
            if R.T_walk[g, bn] < 1e8 and gain >= 1.0:
                serves[lab] = "no other way" if R.T_walk[g, an] >= 1e8 else round(gain, 1)
        res["jumps"].append(dict(
            id=len(res["jumps"]) + 1, n=int(len(v)), per_hour=round(len(v) / max(1e-9, minutes / 60.0), 1), demos=int(len(set(A[v, 11].astype(int).tolist()))),
            take_off=[round(float(x)) for x in a_med], landing=[round(float(x)) for x in b_med],
            near_take_off=near(a_med), near_landing=near(b_med),
            length=round(float(np.median(A[v, 6]))), rise=round(float(np.median(A[v, 7]))), hole=round(float(np.median(A[v, 10]))),
            speed=[round(float(x)) for x in np.percentile(A[v, 8], (10, 50, 90))], air_s=round(ta, 2),
            speed_needed=round(float(np.percentile(A[v, 6] / np.maximum(A[v, 9], 0.2), 10))),      # length over time in the air: the slowest tenth that made it
            walker_s=None if twm >= 1e8 else round(twm, 1), serves=serves,
            walker="cannot" if twm >= 1e8 else ("slower" if c["hard"] == 2 else "up a ledge" if c["hard"] == 0 else ("just makes it" if direct else "a way beside it")),
            nodes_from=[int(x) for x in np.unique(na[v])[:40]], nodes_to=[int(x) for x in np.unique(nb[v])[:40]],
            node_a=int(an), node_b=int(bn)))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--limit", type=int, default=250, help="demos a map (spread evenly over the set)")
    ap.add_argument("--low", action="store_true", help="run at low priority")
    ap.add_argument("--min-seen", default="5,30", help="list an entry seen this often: one a walker cannot make or is slower at, "
                                                       "and the others (a map with few demos: 2,3)")
    a = ap.parse_args()
    if a.low and os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    MIN_SEEN[:] = [int(x) for x in a.min_seen.split(",")]
    for k_, v_ in V14.items():
        os.environ.setdefault(k_, v_)
    js = os.path.join(ROOT, "docs", "pro_gaps.json")
    summary = json.load(open(js)) if os.path.exists(js) else {}
    for mp in a.map.split(","):                                 # (one world a process holds one player count: the same on every map)
        res = build(mp, a.limit)
        out = os.path.join(ROOT, "sim", "pro_gaps", mp + ".json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):                                 # an entry's "use", set by hand, stays with its jump
            for o in json.load(open(out)).get("jumps", []):
                for j in res["jumps"] if "use" in o else ():
                    if (np.linalg.norm(np.array(o["take_off"]) - np.array(j["take_off"])) < 110.0
                            and np.linalg.norm(np.array(o["landing"]) - np.array(j["landing"])) < 110.0 and o.get("walker") == j["walker"]):
                        j["use"] = o["use"]
                        break
        json.dump(res, open(out, "w"), indent=1)
        summary[mp] = dict(demos=res["demos"], player_minutes=res["player_minutes"], jumps_seen=res["jumps_seen"],
                           over_a_hole_or_up=res["over_a_hole_or_up"], kept=res.get("a_walker_cannot_or_a_second_slower", 0),
                           just_made=res.get("a_walker_just_makes", 0), entries=len(res["jumps"]))
        json.dump(summary, open(js, "w"), indent=1)
        print(mp, summary[mp], flush=True)
        for j in res["jumps"][:40]:
            print("  {id:3d} {n:5d} ({per_hour:5.1f}/h) {walker:15s} from {take_off} [{near_take_off}] to {landing} [{near_landing}] length {length} rise {rise} hole {hole} speed {speed} needs {speed_needed} air {air_s}s walker {walker_s} serves {serves}".format(**j), flush=True)


if __name__ == "__main__":
    main()

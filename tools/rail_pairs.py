"""Where the pros fire the rail at long range: pairs of places (the shooter's and the enemy's) for the rail range starts
of sim/duel_env.py (RAIL_START_P), written to sim/rail_pairs/<map>.json.

From the light demo sets (sim/demo_dataset.py --lite, the folder named in data/demo_root.txt): every frame where the
demo's player holds the rail, presses fire, has the enemy noticed in view and the enemy is in the demo, with 1.5 s or
more since the last frame taken in that demo (one a rail shot at most). Each place is then checked in the simulator
(with the map's solid pieces, as SOLIDS=1 and the game have them):
let down onto the floor with the player's box (at most 160 units; a walkable floor), not in a solid, not in lava or
slime, inside the playable map; the line from each player's eyes to the other's body clear both for the eye (solid
brushes) and for the player's mask; the distance between the two origins, after the drop, within --lo .. --hi. The
horizontal speed of each (the demo's step from the frame before, at most 320) is kept. At most --cap pairs a map (an
even sample of the demos' order, fixed).

A map with fewer than --min pairs so (Campgrounds: 5 light sets) is filled up from the yardsticks' view rows
(<demo root>/yardsticks/view_<map>.npy of tools/pro_yardsticks.py: a row every eight frames with the enemy in view, his
place, weapon, fired, the distance to the enemy, from every demo of the map): the shooter is a row with the rail fired
at a distance in the band, the enemy a place where the pros stood with an enemy in view (any row) at that distance
(within 60 units of it) with the lines clear, checked as above; such a pair has no speeds (0) and src 1 (a demo's
pair: src 0).

    python tools/rail_pairs.py [--maps bloodrun,aerowalk,...] [--lo 600] [--hi 1100] [--cap 3000] [--min 500]

One process a map (one simulator World a process); at most --procs at once.
"""
import argparse
import glob
import json
import multiprocessing as mp
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik",
        "toxicity", "cure")
RG = 1
MINS, MAXS = np.array([-15, -15, -24], np.float32), np.array([15, 15, 32], np.float32)
VIEW_H = 26.0
C_LAVA, C_SLIME = 8, 16
SOLID = 1


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def candidates(mp_, lo, hi):
    """(shooter xyz, enemy xyz, shooter vxy, enemy vxy) of the pros' long rail shots in the map's light sets"""
    out, demos, shots = [], 0, 0
    for f in sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp_, "*.npz"))):
        try:
            d = np.load(f)
            q, first = d["lite"], d["first"]
        except Exception:                                    # noqa: BLE001
            continue
        demos += 1
        alive = q[:, 0] > 0
        ok = alive & (q[:, 2].astype(np.int64) == RG) & (q[:, 3] > 0) & (q[:, 4] > 0.5) & (q[:, 31] > 0.5)
        last = -10 ** 9
        for k in np.nonzero(ok)[0]:
            if k - last < 60:                                # (one a rail shot: the rail reloads in 1.5 s)
                continue
            last = k
            shots += 1
            a, b = q[k, 5:8], q[k, 8:11]
            dd = float(np.linalg.norm(b - a))
            if dd < lo - 150.0 or dd > hi + 150.0:           # (checked again after the drop)
                continue
            va = vb = np.zeros(2, np.float32)
            if k > 0 and not first[k]:
                da, db = (q[k, 5:7] - q[k - 1, 5:7]) / 0.025, (q[k, 8:10] - q[k - 1, 8:10]) / 0.025
                va = da if np.hypot(*da) < 900 else va
                vb = db if np.hypot(*db) < 900 else vb
            out.append((a.copy(), b.copy(), va.copy(), vb.copy()))
    return out, demos, shots


def settle(w, p):
    """the place on the floor under p (the player's box let down at most 160 units), or None"""
    p = np.asarray(p, np.float32)
    t0 = w.trace(p + np.array([0, 0, 4], np.float32), p + np.array([0, 0, 4], np.float32), MINS, MAXS)
    if t0["startsolid"]:
        t0 = w.trace(p + np.array([0, 0, 20], np.float32), p + np.array([0, 0, 20], np.float32), MINS, MAXS)
        if t0["startsolid"]:
            return None
        p = p + np.array([0, 0, 16], np.float32)
    t = w.trace(p + np.array([0, 0, 4], np.float32), p - np.array([0, 0, 160], np.float32), MINS, MAXS)
    if t["startsolid"] or t["allsolid"] or t["fraction"] >= 1.0 or t["normal"][2] < 0.7:
        return None
    e = t["endpos"].astype(np.float32) + np.array([0, 0, 0.5], np.float32)
    if w.cluster(e) < 0:
        return None
    cc = w.contents_n(np.stack([e + np.array([0, 0, MINS[2] + 1.0], np.float32), e, e + np.array([0, 0, 26.0], np.float32)]))
    if ((cc & (C_LAVA | C_SLIME)) != 0).any():
        return None
    return e


def clear(w, a, b):
    """the line from a's eyes to b's body (8 up) and back, for the eye (solid brushes) and the player's mask"""
    for s_, e_ in ((a, b), (b, a)):
        p0, p1 = s_ + np.array([0, 0, VIEW_H], np.float32), e_ + np.array([0, 0, 8.0], np.float32)
        if w.trace(p0, p1, mask=SOLID)["fraction"] < 0.999 or w.trace(p0, p1)["fraction"] < 0.999:
            return False
    return True


def derived(w, mp_, lo, hi, need, rng):
    """pairs from the view rows (see the docstring): (pair rows, rail rows in the band)"""
    f = os.path.join(demo_root(), "yardsticks", "view_{}.npy".format(mp_))
    if not os.path.exists(f):
        return [], 0
    v = np.load(f)
    pos, wpn, fired, dist = v[:, 0:3].astype(np.float32), v[:, 3], v[:, 4] > 0, v[:, 6].astype(np.float32)
    sh = np.nonzero((wpn == RG) & fired & (dist >= lo) & (dist <= hi))[0]
    out = []
    for k in rng.permutation(sh):
        if len(out) >= need:
            break
        a_ = settle(w, pos[k])                                # (the rows hold the origin)
        if a_ is None:
            continue
        dd = np.linalg.norm(pos - a_, axis=1)
        cand = np.nonzero(np.abs(dd - dist[k]) < 60.0)[0]
        for j in rng.permutation(cand)[:30]:
            b_ = settle(w, pos[j])
            if b_ is None:
                continue
            d = float(np.linalg.norm(b_ - a_))
            if lo <= d <= hi and clear(w, a_, b_):
                out.append([round(float(x), 1) for x in (*a_, *b_, 0.0, 0.0, 0.0, 0.0)] + [round(d, 1), 1])
                break
    return out, len(sh)


def one(job):
    mp_, lo, hi, cap, need = job
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    from qsim import World
    w = World(os.path.join(ROOT, "data", "maps", mp_ + ".bsp"), n=2)
    w.add_solids()                                           # (the map's solid pieces, as the game has them: the simulator's SOLIDS=1)
    cand, demos, shots = candidates(mp_, lo, hi)
    rng = np.random.default_rng(7)
    if len(cand) > 4 * cap:                                  # (enough to check: an even sample)
        cand = [cand[int(k)] for k in np.sort(rng.choice(len(cand), 4 * cap, replace=False))]
    keep, why = [], dict(floor=0, line=0, band=0)
    for a, b, va, vb in cand:
        a_, b_ = settle(w, a), settle(w, b)
        if a_ is None or b_ is None:
            why["floor"] += 1
            continue
        d = float(np.linalg.norm(b_ - a_))
        if not lo <= d <= hi:
            why["band"] += 1
            continue
        if not clear(w, a_, b_):
            why["line"] += 1
            continue
        sa, sb = np.hypot(*va), np.hypot(*vb)
        va = va * min(1.0, 320.0 / max(sa, 1e-6))
        vb = vb * min(1.0, 320.0 / max(sb, 1e-6))
        keep.append([round(float(x), 1) for x in (*a_, *b_, *va, *vb)] + [round(d, 1), 0])
    if len(keep) > cap:
        keep = [keep[int(k)] for k in np.sort(rng.choice(len(keep), cap, replace=False))]
    n_demo, view_rows = len(keep), 0
    if len(keep) < need:
        more, view_rows = derived(w, mp_, lo, hi, min(cap, 4 * need) - len(keep), rng)
        keep += more
    ds = np.array([k_[10] for k_ in keep]) if keep else np.zeros(0)
    res = dict(map=mp_, about=__doc__.split("\n\n")[0], lo=lo, hi=hi, demos=demos, rail_shots=shots,
               candidates=len(cand), dropped=why, pairs_n=len(keep), pairs_from_demo_pairs=n_demo,
               pairs_derived=len(keep) - n_demo, view_rail_rows_in_band=view_rows,
               distance_quartiles=[round(float(x)) for x in np.percentile(ds, [25, 50, 75])] if len(ds) else [],
               cols=["ax", "ay", "az", "bx", "by", "bz", "avx", "avy", "bvx", "bvy", "d", "src"], pairs=keep)
    od = os.path.join(ROOT, "sim", "rail_pairs")
    os.makedirs(od, exist_ok=True)
    with open(os.path.join(od, mp_ + ".json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    return mp_, demos, shots, len(cand), why, n_demo, len(keep) - n_demo, res["distance_quartiles"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--lo", type=float, default=600.0)
    ap.add_argument("--hi", type=float, default=1100.0)
    ap.add_argument("--cap", type=int, default=3000)
    ap.add_argument("--min", type=int, default=500, help="fewer demo pairs than this: filled up from the view rows")
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    jobs = [(m, a.lo, a.hi, a.cap, a.min) for m in a.maps.split(",")]
    with mp.get_context("spawn").Pool(a.procs, maxtasksperchild=1) as pool:
        for r in pool.imap_unordered(one, jobs):
            print("{}: demos {}, rail shots {}, candidates in the band {}, dropped {}, pairs {} (+ {} derived), distance quartiles {}".format(*r), flush=True)


if __name__ == "__main__":
    main()

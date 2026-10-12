"""The holding places of a map: the eight places where the pros hold longest and fare best, for the intentions "place 1"
to "place 8" (sim/duel_env.py: TARGETS) and the inputs of N_B2.

    python tools/pro_holds.py                      every map with sim/pro_places/<map>_cells.json -> sim/pro_holds/<map>.json
    python tools/pro_holds.py --map bloodrun,cure  these maps
    python tools/pro_holds.py --check              nothing is written: the lists as they would be

Reads (nothing from the demos themselves):
  docs/pro_yardsticks.json     per map, holds.top_cells: the ten cells (256 x 256 x 128 units) with the most of the pros'
                               holds (a hold: 2 s or more within 150 units, alive, no enemy in view, rockets, lightning
                               or rail in hand), each with its share of the map's holds and the weapon in hand
  sim/pro_places/<map>_cells.json   per cell: how a pro seen standing there fares (frags less deaths in the 10 s after a
                               sighting, less what his stack and the weapons would give anywhere: outcome_over_expected),
                               the sightings it rests on, the weapons in hand
  data/maps/<map>.bsp, nav_<map>_sim.json   the walking map, as the simulator has it under the map fixes of v14

The order (a place's score):  share of the holds  x  (1 + RAISE x outcome_over_expected, shrunk toward nothing where the
sightings are few: x n / (n + SHRINK)), the factor held to 0.5 .. 1.5. A cell that fares clearly badly is left out: its
outcome under -BAD and two of its own standard errors below nothing. A cell that is not among the ten (or a map the
yardsticks have no holds of: Dismemberment, House of Decay) gets a share put from its sightings: the cell's share of the
map's sightings x the middle ratio of holds share to sightings share over the cells that have both (and never more than
the tenth cell's share); `share_from` says which.

The place of a cell: its middle, moved to the nearest live point of the walking map that lies in the cell (in any, when
the cell has none), with that point's height; a point counts only if a walker has a way to it from every spawn point,
and, where the cell has such points, only if the ground round it is floor at its own height (FLOOR_OK of 16 spots at 64
and 128 units: he arrives at speed, and from a ledge's edge or a stair he is carried on and off it; `floor_round`).
No two places within APART (200) units of each other: the better one stays. Eight a map, best first: the file's order
is the order of the intentions and of the inputs.

A process a map (the simulator has one world a process). QLBOT_ROOT: the repo, when this file is run from a copy."""
import argparse
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
KEEP, APART = 8, 200.0
RAISE, SHRINK, BAD = 5.0, 200.0, 0.05
FLOOR_OK, FLOOR_STEP = 0.9, 40.0                               # the ground round a place: this share of it floor within this height of the point's own
BIG = (("rockets", "rl"), ("lightning", "lg"), ("rail", "rg"))
FIXES = dict(SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1", AMMO_PACKS="0", TARGETS="0")


def maps_with_cells():
    d = os.path.join(SIM, "pro_places")
    return sorted(f[:-len("_cells.json")] for f in os.listdir(d) if f.endswith("_cells.json"))


def candidates(mp):
    """every cell of the map that has numbers, with its share of the holds (true or put from its sightings) and its score"""
    cells = json.load(open(os.path.join(SIM, "pro_places", mp + "_cells.json"), encoding="utf-8"))
    size = [float(x) for x in cells["cell"]]
    by = {tuple(c["cell"]): c for c in cells["cells"]}
    total = float(sum(c["sightings"] for c in cells["cells"])) or 1.0
    top = []
    yf = os.path.join(ROOT, "docs", "pro_yardsticks.json")
    if os.path.exists(yf):
        y = json.load(open(yf, encoding="utf-8"))["maps"]
        top = ((y.get(mp) or {}).get("holds") or {}).get("top_cells", {}).get(mp, [])
        ratios = [t["share"] / (100.0 * by_[tuple(t["cell"])]["sightings"] / tot_)
                  for m_ in y if m_ not in ("all", "all_ten", "all_given")
                  for by_, tot_ in [_cells_of(m_)] if by_
                  for t in ((y[m_].get("holds") or {}).get("top_cells", {}).get(m_, [])) if tuple(t["cell"]) in by_]
    else:
        ratios = []
    ratio = sorted(ratios)[len(ratios) // 2] if ratios else 1.3
    held = {tuple(t["cell"]): t for t in top}
    cap = min((t["share"] for t in top), default=1e9)
    out = []
    for key, c in by.items():
        t = held.get(key)
        if t is not None:
            share, src, n_holds = float(t["share"]), "holds", int(t["holds"])
            tot_w = float(sum(t["weapons"].values())) or 1.0
            wp = {nm: round(100.0 * t["weapons"].get(k, 0) / tot_w, 1) for nm, k in BIG}
        else:
            share, src, n_holds = min(cap, ratio * 100.0 * c["sightings"] / total), "sightings", None
            ws = c.get("weapon_shares") or {}
            tot_w = float(sum(ws.get(nm, 0.0) for nm, _ in BIG)) or 1.0
            wp = {nm: round(100.0 * ws.get(nm, 0.0) / tot_w, 1) for nm, _ in BIG}
        n = float(c["sightings"])
        ooe = c.get("outcome_over_expected")
        f_, d_ = float(c.get("frags_a_sighting") or 0.0), float(c.get("deaths_a_sighting") or 0.0)
        se = math.sqrt(max(1e-6, f_ + d_ - (f_ - d_) ** 2) / max(1.0, n))
        factor = 1.0 if ooe is None else min(1.5, max(0.5, 1.0 + RAISE * float(ooe) * n / (n + SHRINK)))
        bad = ooe is not None and float(ooe) < -BAD and float(ooe) < -2.0 * se
        out.append(dict(cell=list(key), middle=[float(x) for x in c["middle"]], share=round(share, 2), share_from=src, holds=n_holds,
                        sightings=int(n), outcome_over_expected=ooe, se=round(se, 3), factor=round(factor, 3), score=round(share * factor, 3),
                        bad=bool(bad), weapons=wp, weapon=max(wp, key=wp.get), near=c.get("near")))
    for t in top:                                            # (a cell of the ten with too few sightings for numbers of its own)
        if tuple(t["cell"]) not in by:
            tot_w = float(sum(t["weapons"].values())) or 1.0
            wp = {nm: round(100.0 * t["weapons"].get(k, 0) / tot_w, 1) for nm, k in BIG}
            out.append(dict(cell=list(t["cell"]), middle=[float(x) for x in t["middle"]], share=float(t["share"]), share_from="holds", holds=int(t["holds"]),
                            sightings=0, outcome_over_expected=None, se=None, factor=1.0, score=float(t["share"]), bad=False, weapons=wp,
                            weapon=max(wp, key=wp.get), near=dict(item=t.get("near"), units=t.get("near_units"))))
    out.sort(key=lambda c_: -c_["score"])
    return out, size, dict(holds_cells=len(top), ratio=round(ratio, 3), cells=len(by))


def _cells_of(mp):
    f = os.path.join(SIM, "pro_places", mp + "_cells.json")
    if not os.path.exists(f):
        return None, 1.0
    cs = json.load(open(f, encoding="utf-8"))["cells"]
    return {tuple(c["cell"]): c for c in cs}, float(sum(c["sightings"] for c in cs)) or 1.0


def floor_round(env, pts):
    """for each point: the share of 16 spots round it (8 directions at 64 and at 128 units) that he can stand on at about
    its height: a wall on the line to the spot counts as ground (nobody falls through it), a spot with no floor within
    FLOOR_STEP units of the point's own, or with lava or slime under it, does not"""
    import numpy as np
    import duel_env as E
    pts = np.asarray(pts, np.float32)
    down = np.array([[0, 0, -1.0]], np.float32)
    own = env.w.rays(pts, down, 256.0)[:, 0] * 256.0         # how far under the point its own floor is
    good = np.zeros(len(pts), np.float32)
    ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    for r_ in (64.0, 128.0):
        for a_ in ang:
            sp = (pts + np.array([np.cos(a_) * r_, np.sin(a_) * r_, 0.0], np.float32)).astype(np.float32)
            wall = np.array([env.w.trace(p_, s_)["fraction"] < 0.999 for p_, s_ in zip(pts, sp)])
            fr = env.w.rays(sp, down, 256.0)[:, 0]
            end = sp.copy()
            end[:, 2] -= fr * 256.0 - 4.0
            bad = (env.w.contents_n(end) & (E.C_LAVA | E.C_SLIME)) != 0 if hasattr(E, "C_LAVA") else np.zeros(len(pts), bool)
            good += wall | ((np.abs(fr * 256.0 - own) < FLOOR_STEP) & ~bad)
    return good / 16.0


def one(mp, check):
    """a map's list (this process holds the simulator's world of that map)"""
    os.environ.update(FIXES)
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=2, seed=0, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    R = env.route
    assert R is not None, mp + ": no walking map"
    live = ~R.dead
    sp_nodes = sorted({int(x) for x in R.locate(np.asarray(env.spawns, np.float32))})
    from_sp = np.stack([R.from_node(a) for a in sp_nodes])           # seconds from every spawn point to every point
    ok = live & (from_sp < 1e8).all(0)
    cand, size, src = candidates(mp)
    half = np.array(size, np.float32) / 2.0
    places, left_out = [], []
    for c in cand:
        if len(places) >= KEEP:
            break
        if c["bad"]:
            left_out.append((c, "fares clearly badly"))
            continue
        mid = np.array(c["middle"], np.float32)
        d = R.nodes - mid
        inside = ok & (np.abs(d) <= half + 1e-3).all(1)
        pool = np.nonzero(inside)[0] if inside.any() else np.nonzero(ok)[0]
        if not len(pool):
            left_out.append((c, "no point a walker reaches from every spawn"))
            continue
        dd = np.hypot(d[pool, 0], d[pool, 1]) + (0.01 if inside.any() else 2.0) * np.abs(d[pool, 2])
        fl = floor_round(env, R.nodes[pool])                 # the share of the ground round each point that is floor at its height
        best = fl >= min(FLOOR_OK, float(fl.max()))          # (a place to stand, not a ledge's edge or a stair: he arrives at speed)
        q = int(pool[best][int(dd[best].argmin())])
        q2 = int(R.locate(R.nodes[q][None])[0])              # (the point the simulator's own look-up gives for that place)
        if q2 != q and ok[q2] and (not inside.any() or inside[q2]) and int(R.locate(R.nodes[q2][None])[0]) == q2                 and float(floor_round(env, R.nodes[[q2]])[0]) >= min(FLOOR_OK, float(fl.max())):
            q = q2
        pos = R.nodes[q]
        if any(np.linalg.norm(pos - np.array(p_["pos"], np.float32)) < APART for p_ in places):
            left_out.append((c, "within {:.0f} units of a better place".format(APART)))
            continue
        node = int(R.locate(pos[None])[0])
        t_sp = from_sp[:, node]
        places.append(dict(id=len(places) + 1, pos=[round(float(x), 1) for x in pos], node=node, cell=c["cell"], cell_middle=c["middle"],
                           in_cell=bool(inside.any()), moved=round(float(np.linalg.norm(pos - mid)), 1),
                           floor_round=round(float(floor_round(env, pos[None])[0]), 2),
                           share=c["share"], share_from=c["share_from"], holds=c["holds"], sightings=c["sightings"],
                           outcome_over_expected=c["outcome_over_expected"], factor=c["factor"], score=c["score"],
                           weapon=c["weapon"], weapons=c["weapons"], near=c["near"],
                           from_spawns_s=dict(worst=round(float(t_sp.max()), 1), mean=round(float(t_sp.mean()), 1))))
    res = dict(map=mp, cell=size, keep=KEEP, apart=APART, source=src, spawns=len(sp_nodes),
               about="the map's holding places, best first (tools/pro_holds.py): pos is a point of the walking map; share: the pros' share of holds in its cell, per cent "
                     "(share_from sightings: put from the pros' sightings there); outcome_over_expected: how a pro seen standing in the cell fares against what his "
                     "stack would give anywhere; from_spawns_s: a walker's way from the spawn points, seconds",
               places=places)
    out = os.path.join(SIM, "pro_holds", mp + ".json")
    if not check:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
    print("\n{}: {} places{} (holds known for {} cells; {} cells with numbers; {} spawn points)".format(
        mp, len(places), "" if check else " -> sim/pro_holds/{}.json".format(mp), src["holds_cells"], src["cells"], len(sp_nodes)))
    print("  #  position                 share of holds   fares    sightings  score  weapon in hand            near        way from a spawn, s (worst / mean)   floor round it")
    for p_ in places:
        nr = p_["near"] or {}
        print("  {}  ({:6.0f},{:6.0f},{:5.0f})   {:5.1f}%{}   {}   {:6d}   {:5.2f}  {:9s} {:14s}  {:4s} {:>4}   {:5.1f} / {:4.1f}                        {:.2f}".format(
            p_["id"], p_["pos"][0], p_["pos"][1], p_["pos"][2], p_["share"], " " if p_["share_from"] == "holds" else "*",
            "  n/a " if p_["outcome_over_expected"] is None else "{:+.3f}".format(p_["outcome_over_expected"]), p_["sightings"], p_["score"], p_["weapon"],
            "({})".format("/".join("{:.0f}".format(p_["weapons"][nm]) for nm, _ in BIG)), str(nr.get("item") or ""), str(nr.get("units") or ""),
            p_["from_spawns_s"]["worst"], p_["from_spawns_s"]["mean"], p_["floor_round"]))
    for c, why in left_out[:6]:
        print("  left out: cell {} ({:.1f}%{}, fares {}): {}".format(c["cell"], c["share"], "" if c["share_from"] == "holds" else "*", c["outcome_over_expected"], why))
    if any(p_["share_from"] != "holds" for p_ in places):
        print("  * put from the pros' sightings there (x {:.2f}): the demos' holds do not reach this cell".format(src["ratio"]))
    worst = max((p_["from_spawns_s"]["worst"] for p_ in places), default=0.0)
    print("  every place has a walker's way from every spawn point: {} (the longest {:.1f} s)".format("yes" if places and worst < 1e8 else "NO", worst), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--one", default="", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.one:
        return one(a.one, a.check)
    rc = 0
    for mp in ([m_ for m_ in a.map.split(",") if m_] or maps_with_cells()):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", mp] + (["--check"] if a.check else []),
                           creationflags=0x4000 if os.name == "nt" else 0)
        rc = rc or r.returncode
    sys.exit(rc)


if __name__ == "__main__":
    main()

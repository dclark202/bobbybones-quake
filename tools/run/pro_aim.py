"""aim3, the benchmarks (owner, 2026-11-10): the pros' aim by style, measured from the demos; "default" = the average pro,
"better" = the 90th percentile. Measurement only; system Python.

    python tools/run/pro_aim.py [--maps ...] [--src pros|<folder of his games in the same columns>] [--json out.json]

The data: sets_lite3 (sim/demo_dataset.py --lite3), a row a 25 ms frame of the recording player:
    0 health 1 armor 2 weapon 3 trigger 4 the enemy truly in view (field of view, clear line, sent by the server) 5-7 his place
    8-10 the enemy's place 11-13 the enemy's speed 14 yaw 15 pitch (down is positive) 16 the enemy sent 17 his hit counter
    18 the player's number 19-27 his ammunition by weapon 28 weapon time 29 crouched 30-32 his speed

A shot: the ammunition of the weapon in hand falls. A hit: the hit counter rises on that frame or the next two (the rail, the
shotgun, a lightning cell); a rocket: within its flight time to where the enemy was, less 150 ms to plus 400 ms.

The measures, per player-game (a unit) and over all:
  FLICK (rail; shotgun beside it)
    hit rate, all shots with the enemy in view on the frame before
    ... by the view's travel in the 250 ms before the shot (how big the flick was) and by how fast the enemy crossed
    the held shot: the enemy unseen for a second, his view within HELD_DEG in the 250 ms before the enemy came into view, the
      first shot within a second of it: the time from in view to the shot, its hit rate
    the crosshair's distance from the enemy on the shot's frame (degrees, and in half body widths)
  TRACK (lightning): cells that hit of cells fired with the enemy in view; by the enemy's crossing speed; the crosshair's distance
    while firing
  ROCKETS: rockets that hit of rockets fired, by distance, the enemy in view or not; where the view points at the shot: below
    the enemy (the feet) and ahead of him as a share of the full lead (his crossing speed times the rocket's flight)

"average": the mean over the units with enough shots. "p90": the mean plus 1.28 times the spread BETWEEN units after the chance
spread of a unit's own shot count is taken out (a game with 15 rail shots reads 60% by luck: the raw 90th percentile of games would
flatter). Times: the median of a unit; "p90" is the fast end (the 10th percentile of the units' medians).
"""
import argparse
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RL, RG, LG, MG, SG, GL, PG = 0, 1, 2, 3, 4, 5, 6
DT, VIEW_H, HELD_DEG = 0.025, 26.0, 4.0
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity,cure"


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def unit(L, first):
    """the per-frame quantities of one player-game"""
    n = len(L)
    seg = np.cumsum(first)
    same = np.zeros(n, bool)
    same[1:] = seg[1:] == seg[:-1]
    w = L[:, 2].astype(int).clip(0, 8)
    am = L[np.arange(n), 19 + w]
    shot = np.zeros(n, bool)
    shot[1:] = same[1:] & (w[1:] == w[:-1]) & (am[1:] < am[:-1])
    dh = np.zeros(n)
    dh[1:] = np.where(same[1:], L[1:, 17] - L[:-1, 17], 0.0)
    dh[(dh < 0) | (dh > 4)] = 0
    eye = L[:, 5:8] + np.array([0, 0, VIEW_H]) - np.array([0, 0, 14.0]) * L[:, 29:30]
    to = L[:, 8:11] - eye
    hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
    d = np.linalg.norm(to, axis=1) + 1e-6
    brg, bpt = np.degrees(np.arctan2(to[:, 1], to[:, 0])), -np.degrees(np.arctan2(to[:, 2], hd))
    ey, ep = wrap(brg - L[:, 14]), bpt - L[:, 15]
    yr, pr = np.radians(L[:, 14]), np.radians(L[:, 15])
    fd = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
    off = np.degrees(np.arccos(np.clip((to * fd).sum(1) / d, -1, 1)))          # the crosshair's distance from the enemy's middle
    vis = L[:, 4] > 0
    run = np.zeros(n, int)                                                     # frames the enemy has been in view / out of view
    out = np.zeros(n, int)
    for k in range(1, n):
        if same[k]:
            run[k] = run[k - 1] + 1 if vis[k] else 0
            out[k] = 0 if vis[k] else out[k - 1] + 1
        else:
            run[k], out[k] = int(vis[k]), 0 if vis[k] else 40
    def back(x, m):                                                            # x of m frames ago within the stretch (else nan)
        y = np.full(x.shape, np.nan)
        y[m:] = np.where((seg[m:] == seg[:-m])[(...,) + (None,) * (x.ndim - 1)], x[:-m], np.nan)
        return y
    f10 = back(fd, 10)
    trav = np.degrees(np.arccos(np.clip((fd * f10).sum(1), -1, 1)))            # the view's travel in the last 250 ms
    b4 = back(np.stack([brg, bpt], 1), 4)
    cross = np.hypot(wrap(brg - b4[:, 0]) * np.cos(np.radians(bpt)), bpt - b4[:, 1]) / (4 * DT)   # the enemy's bearing: degrees a second
    return dict(n=n, seg=seg, same=same, w=w, shot=shot, dh=dh, d=d, hd=hd, ey=ey, ep=ep, off=off, vis=vis, run=run, out=out, trav=trav,
                cross=cross, L=L, fd=fd, to=to, back=back)


def hitscan_hit(u, k):
    dh = u["dh"]
    j = np.minimum(k[:, None] + np.arange(3)[None], u["n"] - 1)
    return (dh[j] * (u["seg"][j] == u["seg"][k][:, None])).sum(1) > 0


def measure(u):
    """the counts of one player-game: {name: (hits, shots)} for rates, {name: [values]} for times and angles"""
    R, V = {}, {}
    def rate(nm, hit, m=None):
        if m is not None:
            hit = hit[m]
        R[nm] = (float(hit.sum()), float(len(hit)))
    w, shot, vis = u["w"], u["shot"], u["vis"]
    prev = np.zeros(u["n"], bool)
    prev[1:] = vis[:-1] & u["same"][1:]
    for W, nm in ((RG, "rail"), (SG, "shotgun")):
        k = np.nonzero(shot & (w == W))[0]
        if len(k):
            rate(nm + " every shot (in view or not)", hitscan_hit(u, k))
        k = np.nonzero(shot & (w == W) & prev)[0]
        if not len(k):
            continue
        h = hitscan_hit(u, k)
        rate(nm + " all", h)
        tr, cr, d = u["trav"][k], u["cross"][k], u["d"][k]
        for lo, hi in ((0, 3), (3, 10), (10, 30), (30, 181)):
            rate("{} flick {}-{} deg".format(nm, lo, hi), h, (tr >= lo) & (tr < hi))
        for lo, hi in ((0, 15), (15, 40), (40, 90), (90, 1e9)):
            rate("{} enemy crossing {}-{} deg/s".format(nm, lo, "up" if hi > 1e8 else hi), h, (cr >= lo) & (cr < hi))
        for lo, hi in ((0, 400), (400, 800), (800, 1300), (1300, 1e9)):
            rate("{} at {}-{} units".format(nm, lo, "up" if hi > 1e8 else hi), h, (d >= lo) & (d < hi))
        j = np.maximum(k - 1, 0)                                              # the frame the shot was aimed on
        V[nm + " crosshair off (deg)"] = list(u["off"][j])
        V[nm + " crosshair off (half bodies)"] = list(u["off"][j] / np.degrees(np.arctan2(15.0, u["d"][j])))
        # the held shot: the first shot of a sighting that began with the view still
        run = u["run"][j]
        st = j - run + 1                                                      # the frame he came into view
        ok = (run >= 1) & (run <= 40) & (st >= 1)
        st = np.maximum(st, 1)
        ok &= (u["out"][st - 1] >= 40) & (np.nan_to_num(u["trav"][st - 1], nan=99.0) < HELD_DEG) & (u["seg"][st] == u["seg"][k])
        firstshot = np.ones(len(k), bool)
        firstshot[1:] = (k[1:] - k[:-1]) > run[1:]                            # no earlier shot in this sighting
        ok &= firstshot
        if ok.any():
            rate(nm + " held shot", h, ok)
            V[nm + " held shot: in view to shot (ms)"] = list(run[ok] * 25.0)
        ok2 = (run >= 1) & (run <= 40) & firstshot & (u["out"][np.maximum(j - run, 0)] >= 40)
        if ok2.any():                                                         # any first shot of a new sighting (held or flicked)
            rate(nm + " first shot of a sighting", h, ok2)
            V[nm + " first shot: in view to shot (ms)"] = list(run[ok2] * 25.0)
    k = np.nonzero(shot & (w == LG))[0]
    if len(k):
        rate("lightning every cell (in view or not)", u["dh"][k] > 0)
    k = np.nonzero(shot & (w == LG) & prev)[0]
    if len(k):
        h = u["dh"][k] > 0                                                     # (a cell's hit is counted on its own frame: the next frame's is the next cell's)
        rate("lightning all", h)
        cr, d = u["cross"][k], u["d"][k]
        for lo, hi in ((0, 15), (15, 40), (40, 90), (90, 1e9)):
            rate("lightning enemy crossing {}-{} deg/s".format(lo, "up" if hi > 1e8 else hi), h, (cr >= lo) & (cr < hi))
        for lo, hi in ((0, 300), (300, 500), (500, 768)):
            rate("lightning at {}-{} units".format(lo, hi), h, (d >= lo) & (d < hi))
        V["lightning crosshair off (deg)"] = list(u["off"][np.maximum(k - 1, 0)])
    k = np.nonzero(shot & (w == RL))[0]
    if len(k):
        L = u["L"]
        pres = L[k, 16] > 0
        fl = np.clip(np.rint(u["d"][k] / 1000.0 / DT).astype(int), 1, 100)
        h = np.zeros(len(k), bool)
        for a_, kk in enumerate(k):
            lo, hi = kk + max(1, fl[a_] - 6), min(u["n"] - 1, kk + fl[a_] + 16)
            if lo <= hi:
                h[a_] = (u["dh"][lo:hi + 1] * (u["seg"][lo:hi + 1] == u["seg"][kk])).sum() > 0
        j = np.maximum(k - 1, 0)
        v_ = u["vis"][j]
        rate("rockets all", h)
        rate("rockets, enemy in view", h, v_)
        rate("rockets, enemy not in view", h, ~v_)
        R["rockets fired with nobody in view"] = (float((~v_).sum()), float(len(k)))
        for lo, hi in ((0, 250), (250, 500), (500, 800), (800, 1e9)):
            rate("rockets in view at {}-{} units".format(lo, "up" if hi > 1e8 else hi), h, v_ & (u["d"][k] >= lo) & (u["d"][k] < hi))
        if v_.any():                                                          # where the view points on the shot
            jj = j[v_]
            V["rockets: view below the enemy's middle (units at his distance)"] = list(-np.tan(np.radians(u["ep"][jj])) * u["hd"][jj])
            ev = L[jj, 11:14]
            to = u["to"][jj]
            side = np.stack([-to[:, 1], to[:, 0]], 1) / u["hd"][jj][:, None]                   # to the left of the line to him
            vp = (ev[:, :2] * side).sum(1)                                                     # his speed across the line
            full = np.degrees(np.arctan2(np.abs(vp) * (u["d"][jj] / 1000.0), u["hd"][jj]))     # the full lead, degrees
            lead = -u["ey"][jj] * np.sign(vp)                                                  # the view ahead of him (+)
            m = full > 3.0
            if m.any():
                V["rockets: lead as a share of the full lead"] = list(lead[m] / full[m])
    return R, V


def load_units(src, maps):
    if src == "pros":
        root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
        files = [f for mp in maps for f in sorted(glob.glob(os.path.join(root, "sets_lite3", mp, "*.npz")))]
    else:
        files = [f for mp in maps for f in sorted(glob.glob(os.path.join(src, "*{}*.npz".format(mp))))]
    for f in files:
        z = np.load(f)
        L, first = z["lite"].astype(np.float64), z["first"]
        if len(L) < 2000:
            continue
        for c in np.unique(L[:, 18]):                        # a unit: one player of one game
            m = L[:, 18] == c
            if m.sum() >= 2000:
                fi = first[m].copy()
                fi[0] = True
                idx = np.nonzero(m)[0]
                fi[1:] |= np.diff(idx) > 1
                yield os.path.basename(f), unit(L[m], fi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=MAPS)
    ap.add_argument("--src", default="pros")
    ap.add_argument("--json", default="")
    ap.add_argument("--min", type=int, default=12, help="a unit counts for a rate with this many shots")
    a = ap.parse_args()
    RR, VV, n_units = {}, {}, 0
    for nm, u in load_units(a.src, a.maps.split(",")):
        R, V = measure(u)
        n_units += 1
        for k, v in R.items():
            RR.setdefault(k, []).append(v)
        for k, v in V.items():
            VV.setdefault(k, []).append(np.asarray(v, float))
    out = {}
    print("{}: {} player-games".format(a.src, n_units))
    print("\n{:<52} {:>9} {:>8} | {:>7} {:>7} {:>7} | {:>6}".format("rate", "shots", "pooled", "average", "p90", "raw p90", "units"))
    for k, v in RR.items():
        v = np.array(v)
        H, N = v[:, 0].sum(), v[:, 1].sum()
        big = v[v[:, 1] >= a.min]
        row = dict(shots=float(N), pooled=float(H / max(N, 1)))
        if len(big) >= 8:
            p = big[:, 0] / big[:, 1]
            mu = p.mean()
            chance = np.mean(mu * (1 - mu) / big[:, 1])                       # a unit's own shot count's spread
            sd = max(0.0, p.var(ddof=1) - chance) ** 0.5
            row.update(average=float(mu), p90=float(min(1.0, mu + 1.2816 * sd)), raw_p90=float(np.percentile(p, 90)), units=len(big))
        out[k] = row
        print("{:<52} {:>9.0f} {:>7.1%} | {} | {:>6}".format(k, N, row["pooled"], "{:>7.1%} {:>7.1%} {:>7.1%}".format(
            row["average"], row["p90"], row["raw_p90"]) if "average" in row else "{:>7} {:>7} {:>7}".format("-", "-", "-"), row.get("units", 0)))
    print("\n{:<64} {:>8} | {:>8} {:>8} {:>8} | {:>8} {:>8}".format("value", "n", "p25", "median", "p75", "average*", "good end*"))
    for k, v in VV.items():
        allv = np.concatenate(v)
        allv = allv[np.isfinite(allv)]
        med = np.array([np.median(x[np.isfinite(x)]) for x in v if np.isfinite(x).sum() >= 5])
        row = dict(n=int(len(allv)), p25=float(np.percentile(allv, 25)), median=float(np.median(allv)), p75=float(np.percentile(allv, 75)))
        if len(med) >= 8:
            row.update(units_median=float(np.mean(med)), units_p10=float(np.percentile(med, 10)), units_p90=float(np.percentile(med, 90)), units=len(med))
        out[k] = row
        good = row.get("units_p90" if "lead" in k or "below" in k else "units_p10", float("nan"))
        print("{:<64} {:>8} | {:>8.2f} {:>8.2f} {:>8.2f} | {:>8.2f} {:>8.2f}".format(k, row["n"], row["p25"], row["median"], row["p75"],
                                                                                 row.get("units_median", float("nan")), good))
    print("\n* average: the mean of the units' medians; good end: the 10th percentile of the units' medians (the 90th for the rockets' aim point)")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

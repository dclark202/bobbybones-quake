"""aim3: the aim model's parameters read from human play (CLAUDE.md hard rule 12: the demos measure things; no hit rate is a target).
Measurement only; system Python.

    python tools/run/pro_knobs.py collect [--src pros|<folder>] [--maps ...] --out shots.npz     every rail shot, a sample of lightning frames
    python tools/run/pro_knobs.py read shots.npz [--json out.json]                               the parameters, a player-game and over all

WHAT IS MEASURED: the AIM ERROR, the angle left-right between where the view points and where the enemy is, on the frame a shot is aimed
(the rail: a deliberate, single shot) and while tracking (the lightning). How that error grows with each condition is the
precursor of a hit, and is what the model's parameters describe:
    with distance                        -> is the base sight error a fixed angle, or a share of how big the enemy looks?
    with the enemy's crossing speed      -> the slip term; and whether a STILL view sees a crosser worse than a following one
                                            (AIM2 says yes; AIM3: the eye follows him either way)
    after the enemy turns round          -> how long the error stays raised: the eye's (and hand's) lag
    with the time he has been in view    -> the notice / fixation fade (the eccentricity term)
    with the size of the flick           -> the hand's endpoint noise (MOTOR_NOISE: a share of the movement)
    the response lag when tracking       -> the tracking delay (the view's turn rate against the bearing's, best lag)

THE DEMO'S OWN DELAY: a demo holds the server's state. The player aimed at the picture his client drew (a snapshot or two old)
and the game's lag compensation moved the enemy back by his ping for the hit test. So in the demo's frames a perfect shot points
where the enemy WAS some frames ago. Per player-game that delay is found first: the shift (0 to 6 frames) of the enemy's place
at which the lightning frames that HIT have the smallest median error; every error below is taken at that shift. His own games
(the simulator: no such delay) must come out at 0: the method's check.

Per player-game values where it has enough shots; "average" = the mean over player-games, "p90" = the good end (the 10th
percentile of an error or a delay), taken on the player-games' own values.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pro_aim as PA  # noqa: E402

RL, RG, LG = 0, 1, 2
DT = 0.025


def shifted(u, tau):
    """the aim error (degrees: total, left-right, up-down), the enemy's bearing and distance with his place tau frames back"""
    L = u["L"]
    n = u["n"]
    ep = L[:, 8:11].copy()
    if tau:
        ok = np.zeros(n, bool)
        ok[tau:] = u["seg"][tau:] == u["seg"][:-tau]
        ep[tau:] = np.where(ok[tau:, None], L[:-tau, 8:11], L[tau:, 8:11])
    eye = L[:, 5:8] + np.array([0, 0, PA.VIEW_H]) - np.array([0, 0, 14.0]) * L[:, 29:30]
    to = ep - eye
    hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
    d = np.linalg.norm(to, axis=1) + 1e-6
    brg, bpt = np.degrees(np.arctan2(to[:, 1], to[:, 0])), -np.degrees(np.arctan2(to[:, 2], hd))
    off = np.degrees(np.arccos(np.clip((to * u["fd"]).sum(1) / d, -1, 1)))
    return off, PA.wrap(brg - L[:, 14]), bpt - L[:, 15], brg, bpt, d


def one(u, uid, tau0=2):
    """a player-game: its delay, its rail shots and a sample of its lightning frames (rows), its tracking lag"""
    w, shot, vis, seg, n = u["w"], u["shot"], u["vis"], u["seg"], u["n"]
    prev = np.zeros(n, bool)
    prev[1:] = vis[:-1] & u["same"][1:]
    lgf = np.nonzero(shot & (w == LG) & prev)[0]
    hitf = lgf[u["dh"][lgf] > 0]
    tau = tau0                                               # (too few lightning hits to find it: the usual one, --tau0)
    if len(hitf) >= 150:
        meds = []
        for t in range(7):
            off = shifted(u, t)[0]
            meds.append(np.median(off[hitf] / np.degrees(np.arctan2(15.0, u["d"][hitf]))))     # (the view of the shot's frame against his place t frames back)
        tau = int(np.argmin(meds))
    off, ey, ep, brg, bpt, d = shifted(u, tau)
    back = u["back"]
    b4 = back(np.stack([brg, bpt], 1), 4)
    cx = PA.wrap(brg - b4[:, 0]) * np.cos(np.radians(bpt)) / (4 * DT)          # the enemy's bearing, degrees a second, signed (left +)
    cross = np.hypot(cx, (bpt - b4[:, 1]) / (4 * DT))
    f4 = back(u["fd"], 4)
    vsp = np.degrees(np.arccos(np.clip((u["fd"] * f4).sum(1), -1, 1))) / (4 * DT)   # the view's own turn, degrees a second
    sg = np.sign(np.where(np.abs(cx) > 8.0, cx, 0.0))
    rev = np.full(n, 400)                                                      # frames since the enemy's crossing changed side
    last = 0
    for k in range(1, n):
        if seg[k] != seg[k - 1] or not vis[k]:
            last, rev[k] = 0, 400
            continue
        if sg[k] != 0:
            if last != 0 and sg[k] != last:
                rev[k] = 0
            else:
                rev[k] = min(rev[k - 1] + 1, 400)
            last = sg[k]
        else:
            rev[k] = min(rev[k - 1] + 1, 400)
    rows = []
    for W in (RG,):
        k = np.nonzero(shot & (w == W) & prev)[0]
        if len(k):
            j = np.maximum(k - 1, 0)
            h = PA.hitscan_hit(u, k)
            # the view at the instant of the shot: between the frame before and this one, by the reload's clock (1500 ms at the shot)
            L = u["L"]
            fr_ = np.clip((1500.0 - L[k, 28]) / 25.0, 0.0, 1.0)
            fr_ = np.where(L[k, 28] > 1400.0, fr_, 0.0)
            yv = L[k, 14] - fr_ * PA.wrap(L[k, 14] - L[j, 14])
            pv = L[k, 15] - fr_ * (L[k, 15] - L[j, 15])
            ey_s, ep_s = PA.wrap(brg[k] - yv), bpt[k] - pv   # (brg, bpt: his place tau frames back, from the shooter's eye of frame k)
            off_s = np.degrees(np.arccos(np.clip(np.cos(np.radians(pv)) * np.cos(np.radians(bpt[k])) * np.cos(np.radians(brg[k] - yv))
                                                 + np.sin(np.radians(pv)) * np.sin(np.radians(bpt[k])), -1, 1)))
            off, ey, ep = off.copy(), ey.copy(), ep.copy()
            off[j], ey[j], ep[j] = off_s, ey_s, ep_s
            rows.append(np.stack([np.full(len(k), uid), np.full(len(k), W), d[j], off[j], ey[j], ep[j], cross[j], np.nan_to_num(vsp[j], nan=-1),
                                  np.nan_to_num(u["trav"][j], nan=-1), u["run"][j], rev[j], h, np.full(len(k), tau),
                                  -ey[j] * np.sign(cx[j])], 1))                # (last: the view ahead (+) or behind (-) the way he moves)
    if len(lgf):
        k = lgf[::4]
        j = k                                                # (the lightning: the view of the cell's own frame)
        rows.append(np.stack([np.full(len(k), uid), np.full(len(k), LG), d[j], off[j], ey[j], ep[j], cross[j], np.nan_to_num(vsp[j], nan=-1),
                              np.nan_to_num(u["trav"][j], nan=-1), u["run"][j], rev[j], u["dh"][k] > 0, np.full(len(k), tau),
                              -ey[j] * np.sign(cx[j])], 1))
    lag = np.nan
    fr = np.zeros(n, bool)
    fr[lgf] = True                                           # tracking: the view's yaw rate against the bearing's, the best lag
    if fr.sum() >= 400:
        vy = np.zeros(n)
        vy[1:] = PA.wrap(u["L"][1:, 14] - u["L"][:-1, 14])
        by = np.zeros(n)
        by[1:] = PA.wrap(brg[1:] - brg[:-1])
        by = np.where(np.abs(by) < 6.0, by, 0.0)             # (a jump of the bearing: a teleport, a new stretch)
        on = np.convolve(fr.astype(float), np.ones(9), "same") > 0
        best, bl = -1.0, np.nan
        for lg_ in range(0, 13):
            a_, b_ = vy[lg_:][on[lg_:]], by[:n - lg_][on[lg_:]]
            if len(a_) > 300 and a_.std() > 0 and b_.std() > 0:
                c_ = float(np.corrcoef(a_, b_)[0, 1])
                if c_ > best:
                    best, bl = c_, lg_
        lag = (bl - tau) * 25.0 if best > 0.15 else np.nan    # (less the demo's own delay)
    return (np.concatenate(rows) if rows else np.zeros((0, 14))), tau, lag


def collect(a):
    rows, taus, lags = [], [], []
    for uid, (nm, u) in enumerate(PA.load_units(a.src, a.maps.split(","))):
        r, tau, lag = one(u, uid, a.tau0)
        rows.append(r)
        taus.append(tau)
        lags.append(lag)
    np.savez_compressed(a.out, rows=np.concatenate(rows).astype(np.float32), tau=np.array(taus), lag=np.array(lags))
    print("{}: {} player-games, {} rows -> {}".format(a.src, len(taus), sum(len(r) for r in rows), a.out))


COLS = dict(uid=0, w=1, d=2, off=3, ey=4, ep=5, cross=6, vsp=7, trav=8, run=9, rev=10, hit=11, tau=12, ahead=13)


def by_unit(R, mask, val, min_n):
    """per player-game the median of val over its rows in mask -> the array of those medians"""
    u = R[mask, 0].astype(int)
    v = val[mask]
    out = []
    if len(u):
        order = np.argsort(u, kind="stable")
        u, v = u[order], v[order]
        cut = np.nonzero(np.diff(u))[0] + 1
        for g in np.split(v, cut):
            if len(g) >= min_n:
                out.append(np.median(g))
    return np.array(out)


def line(nm, R, mask, val, min_n, out, fmt="{:>7.2f}"):
    m = by_unit(R, mask, val, min_n)
    allv = val[mask]
    row = dict(n=int(mask.sum()), pooled_median=float(np.median(allv)) if len(allv) else float("nan"))
    if len(m) >= 8:
        row.update(average=float(m.mean()), p90=float(np.percentile(m, 10)), p10=float(np.percentile(m, 90)), units=int(len(m)))
    out[nm] = row
    print("  {:<58} {:>8} | {} | {} {} {} | {:>5}".format(nm, row["n"], fmt.format(row["pooled_median"]),
          fmt.format(row.get("average", float("nan"))), fmt.format(row.get("p90", float("nan"))), fmt.format(row.get("p10", float("nan"))), row.get("units", 0)))


def read(a):
    z = np.load(a.file)
    R, tau, lag = z["rows"].astype(np.float64), z["tau"], z["lag"]
    c = COLS
    out = {}
    print("{}: {} player-games, {} rows".format(a.file, len(tau), len(R)))
    print("\nthe demo's own delay (frames of 25 ms; found on player-games with 150 lightning hit frames): " +
          ", ".join("{}: {:.0%}".format(t, np.mean(tau == t)) for t in range(7)))
    lg_ = lag[np.isfinite(lag)]
    if len(lg_) >= 8:
        out["tracking lag ms"] = dict(average=float(lg_.mean()), p90=float(np.percentile(lg_, 10)), median=float(np.median(lg_)), units=int(len(lg_)))
        print("the tracking lag (the view's turn behind the bearing's, less the demo's delay): median {:.0f} ms, average {:.0f}, the fast end (p90) {:.0f}, {} player-games".format(
            np.median(lg_), lg_.mean(), np.percentile(lg_, 10), len(lg_)))
    size = np.degrees(np.arctan2(15.0, R[:, c["d"]]))                           # his half width from here, degrees
    R[:, c["off"]] = np.abs(R[:, c["ey"]])                                      # the error left-right (his width is what a shot must find;
    offb = R[:, c["off"]] / size                                                # up-down his body is twice as tall, and the feet are a choice)
    hdr = "  {:<58} {:>8} | {:>7} | {:>7} {:>7} {:>7} | {:>5}".format("", "rows", "pooled", "average", "p90", "p10", "units")
    for W, nm, mn in ((RG, "RAIL (the error on the frame the shot is aimed)", 4), (LG, "LIGHTNING (the error while firing)", 40)):
        w = R[:, c["w"]] == W
        print("\n" + nm + ": the median error, degrees [and in half body widths]\n" + hdr)
        settled = w & (R[:, c["trav"]] >= 0) & (R[:, c["trav"]] < 6) & (R[:, c["run"]] >= 16) & (R[:, c["rev"]] >= 12)
        print(" by distance (settled: in view 0.4 s or more, the view moved under 6 degrees in 250 ms, no turn-round in 0.3 s; the enemy crossing under 20 deg/s)")
        for lo, hi in ((0, 250), (250, 400), (400, 600), (600, 900), (900, 1400)):
            m = settled & (R[:, c["cross"]] < 20) & (R[:, c["d"]] >= lo) & (R[:, c["d"]] < hi)
            line("{} {}-{} units: degrees".format("rail" if W == RG else "lg", lo, hi), R, m, R[:, c["off"]], mn, out)
            line("{} {}-{} units: half bodies".format("rail" if W == RG else "lg", lo, hi), R, m, offb, mn, out)
        print(" by the enemy's crossing speed (settled as above), the view STILL (under 15 deg/s) or FOLLOWING (within a third of his speed); half bodies")
        for lo, hi in ((0, 20), (20, 50), (50, 100), (100, 400)):
            m0 = settled & (R[:, c["cross"]] >= lo) & (R[:, c["cross"]] < hi)
            line("{} crossing {}-{} deg/s, any view".format("rail" if W == RG else "lg", lo, hi), R, m0, offb, mn, out)
            line("{} crossing {}-{} deg/s, view still".format("rail" if W == RG else "lg", lo, hi), R, m0 & (R[:, c["vsp"]] >= 0) & (R[:, c["vsp"]] < 15), offb, mn, out)
            line("{} crossing {}-{} deg/s, view following".format("rail" if W == RG else "lg", lo, hi), R,
                 m0 & (np.abs(R[:, c["vsp"]] - R[:, c["cross"]]) < np.maximum(R[:, c["cross"]] / 3.0, 8.0)) & (R[:, c["vsp"]] >= 15), offb, mn, out)
        print(" after the enemy turns round (frames of 25 ms since his crossing changed side); half bodies; and the view behind him (-) or ahead (+), degrees")
        for lo, hi in ((0, 3), (3, 6), (6, 10), (10, 16), (16, 30), (30, 400)):
            m = w & (R[:, c["run"]] >= 16) & (R[:, c["rev"]] >= lo) & (R[:, c["rev"]] < hi) & (R[:, c["cross"]] >= 20)
            line("{} {}-{} ms after a turn-round".format("rail" if W == RG else "lg", lo * 25, hi * 25), R, m, offb, mn, out)
            line("{} {}-{} ms after a turn-round: ahead".format("rail" if W == RG else "lg", lo * 25, hi * 25), R, m, R[:, c["ahead"]], mn, out)
        print(" by the time he has been in view; half bodies")
        for lo, hi in ((1, 6), (6, 10), (10, 16), (16, 30), (30, 80), (80, 100000)):
            m = w & (R[:, c["run"]] >= lo) & (R[:, c["run"]] < hi)
            line("{} in view {}-{} ms".format("rail" if W == RG else "lg", lo * 25, "up" if hi > 10000 else hi * 25), R, m, offb, mn, out)
        if W == RG:
            print(" by the size of the flick (the view's travel in the 250 ms before the shot; in view 0.4 s or more); degrees, and as a share of the travel")
            for lo, hi in ((0, 3), (3, 8), (8, 15), (15, 30), (30, 60), (60, 181)):
                m = w & (R[:, c["run"]] >= 16) & (R[:, c["trav"]] >= lo) & (R[:, c["trav"]] < hi)
                line("rail flick {}-{} deg: degrees".format(lo, hi), R, m, R[:, c["off"]], mn, out)
                if lo >= 8:
                    line("rail flick {}-{} deg: share of the travel".format(lo, hi), R, m, R[:, c["off"]] / np.maximum(R[:, c["trav"]], 1e-6), mn, out, "{:>7.3f}")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("collect", "read"))
    ap.add_argument("file", nargs="?", default="")
    ap.add_argument("--src", default="pros")
    ap.add_argument("--maps", default=PA.MAPS)
    ap.add_argument("--out", default="shots.npz")
    ap.add_argument("--json", default="")
    ap.add_argument("--tau0", type=int, default=2, help="the delay (frames) of a player-game with too few lightning hits to find its own: the pros' usual 2; his games 1")
    a_ = ap.parse_args()
    {"collect": collect, "read": read}[a_.cmd](a_)

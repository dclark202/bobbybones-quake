"""AIM2 on a real server: the slip, eccentricity and error the plugin's observe() read (DUEL_AIM2DUMP=1: /tmp/practice/
aim2_dump.npy, one row a server frame) worked out again here from the same frames' raw values (his view, his eye, the enemy's
acquired place, the acquired flag, focus, the delay) by the simulator's own rule (_aim2_err): what the plugin keeps (the
history of his view and the bearing, its clearing at a respawn) must give the simulator's numbers.

    python tools/aim2_srvcheck.py <aim2_dump.npy> [--c-slip 0.02 --s0 15 --cap-slip 2 --c-ecc 0.04 --e0 2 --cap-ecc 2]

Columns of a row (plugins/duelbot.py): time, yaw, pitch, eye (3), known (3), the enemy's true place (3), acquired, focus,
flinch, react_frames, percept (2), slip, ecc, err (as observe() read them), zoom, weapon.
"""
import argparse

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--c-slip", type=float, default=0.02)
    ap.add_argument("--s0", type=float, default=15.0)
    ap.add_argument("--cap-slip", type=float, default=2.0)
    ap.add_argument("--c-ecc", type=float, default=0.04)
    ap.add_argument("--e0", type=float, default=2.0)
    ap.add_argument("--cap-ecc", type=float, default=2.0)
    ap.add_argument("--focus-gain", type=int, default=0)
    a = ap.parse_args()
    D = np.load(a.dump)
    t, yaw, pit = D[:, 0], D[:, 1], D[:, 2]
    eye, kn, acq, focus, rf = D[:, 3:6], D[:, 6:9], D[:, 12] > 0.5, D[:, 13], D[:, 15].astype(int)
    slip_s, ecc_s, err_s = D[:, 18], D[:, 19], D[:, 20]
    n = len(D)
    tb = kn + np.array([0, 0, 4.0]) - eye
    by = np.degrees(np.arctan2(tb[:, 1], tb[:, 0]))
    bp = np.degrees(np.arctan2(tb[:, 2], np.hypot(tb[:, 0], tb[:, 1]) + 1e-6))
    vy, vp = yaw, -pit
    w = lambda x: (x + 180.0) % 360.0 - 180.0
    gap = np.concatenate([[True], np.diff(t) > 0.06])            # a hole in the frames (a map change, a pause): the history begins again
    slip = np.full(n, np.nan)
    ecc = np.full(n, np.nan)
    for i in range(n):
        back = rf[i] - a.focus_gain if focus[i] > 0 else rf[i] + 1
        back = max(back, 1)
        i1, i0 = i - back, i - back - 1
        if i0 < 0 or gap[i0 + 1:i + 1].any():
            continue
        if acq[i1] and acq[i0]:
            sy = w(by[i1] - by[i0]) - w(vy[i1] - vy[i0])
            sp = (bp[i1] - bp[i0]) - (vp[i1] - vp[i0])
            slip[i] = np.hypot(sy * np.cos(np.radians(bp[i1])), sp) / 0.025
        else:
            slip[i] = 0.0
        if acq[i1]:
            y1, e1, b1, p1 = (np.radians(x) for x in (vy[i1], vp[i1], by[i1], bp[i1]))
            c = np.cos(e1) * np.cos(p1) * np.cos(b1 - y1) + np.sin(e1) * np.sin(p1)
            ecc[i] = np.degrees(np.arccos(np.clip(c, -1, 1)))
        else:
            ecc[i] = 0.0
    err = np.minimum(a.c_slip * np.maximum(0, slip - a.s0), a.cap_slip) + np.minimum(a.c_ecc * np.maximum(0, ecc - a.e0), a.cap_ecc)
    ok = np.isfinite(slip) & np.isfinite(ecc) & (slip_s >= 0)
    live = ok & (acq | (slip_s > 0))
    print("{} frames, {} compared, {} with the enemy acquired".format(n, int(ok.sum()), int((ok & acq).sum())))
    for nm, x, y in (("slip deg/s", slip, slip_s), ("ecc deg", ecc, ecc_s), ("error deg", err, err_s)):
        d = np.abs(x[ok] - y[ok])
        print("  {:<11} server mean {:.3f} (acquired frames {:.3f}); recomputed {:.3f}; |diff| median {:.4f}, p99 {:.4f}, max {:.4f}, "
              "frames off by more than 1% + 0.01: {}".format(nm, y[ok].mean(), y[live].mean() if live.any() else 0.0, x[ok].mean(),
                                                            np.median(d), np.percentile(d, 99), d.max(),
                                                            int((d > 0.01 + 0.01 * np.abs(y[ok])).sum())))


if __name__ == "__main__":
    main()

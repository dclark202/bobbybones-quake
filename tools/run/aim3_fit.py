"""AIM3's two time constants fitted to the pros' aim error, frame by frame (owner, 2026-11-11: "fix the inputs + tune aim3";
docs/design/AIM3.md section 4: the first values were read off three-bin medians by eye). Rule 12: parameters of a human limit from the pros'
own measured value of that parameter; no hit rate is fitted.

  the eye's lag (AIM3_PURSUIT_TAU): after the enemy's crossing changes side, the pros' error (in half body widths, the median of each 25 ms
      frame since the turn-round) against e_inf * (1 + A * exp(-t / tau)), least squares weighted by the frames' counts
  the fixation time (AIM3_FIX_TAU): after he comes into view, the same from the notice on: e_inf * (1 + A * exp(-(t - t0) / tau))

    python tools/run/aim3_fit.py data/sim_runs/space/aim3/knobs_pros.npz [--json out.json]
(the rows of tools/run/pro_knobs.py collect: one a rail shot's aiming frame and one a lightning cell)."""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fit(ts, es, ns, t0, base):
    ts, es, ns = np.array(ts, float), np.array(es, float), np.array(ns, float)
    ok = np.isfinite(es) & (ts >= t0 - 1e-9)
    t, e, w = ts[ok] - t0, es[ok] / base - 1.0, ns[ok]
    best = (1e30, 0.0, 0.0)
    for tau in np.arange(0.010, 1.0001, 0.005):
        x = np.exp(-t / tau)
        A = max(0.0, float((w * x * e).sum() / (w * x * x).sum()))        # the best amplitude for this tau
        r = float((w * (A * x - e) ** 2).sum() / w.sum())
        if r < best[0]:
            best = (r, A, tau)
    r0 = float((w * e ** 2).sum() / w.sum())                              # no excess at all
    return best[1], best[2], best[0] ** 0.5, r0 ** 0.5, int(ok.sum())


def main():
    import pro_knobs as PK
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    R = np.load(a.file)["rows"].astype(np.float64)
    c, RG, LG = PK.COLS, PK.RG, PK.LG
    offb = np.abs(R[:, c["ey"]]) / np.degrees(np.arctan2(15.0, R[:, c["d"]]))
    out = {}

    def curve(mask, col, frames):
        return [(f, int((mask & (R[:, c[col]] == f)).sum()), float(np.median(offb[mask & (R[:, c[col]] == f)])) if (mask & (R[:, c[col]] == f)).sum() >= 40 else float("nan"))
                for f in frames]

    for W, nm in ((RG, "rail"), (LG, "lightning")):
        w = R[:, c["w"]] == W
        m = w & (R[:, c["run"]] >= 16) & (R[:, c["cross"]] >= 20)
        base = float(np.median(offb[m & (R[:, c["rev"]] >= 16) & (R[:, c["rev"]] < 400)]))
        cv = curve(m, "rev", range(0, 16))
        print("\n{}: after the enemy turns round (in view 0.4 s or more, crossing 20 deg/s or more); settled {:.3f} half bodies".format(nm, base))
        print("  ms: rows, error / settled   " + "  ".join("{}: {}, {}".format(f * 25, n, "-" if e != e else "{:.2f}".format(e / base)) for f, n, e in cv))
        for t0 in (0.0, 0.025, 0.05, 0.075):
            A, tau, r, r0, k = fit([f * 0.025 for f, _, _ in cv], [e for _, _, e in cv], [n for _, n, _ in cv], t0, base)
            print("  from {:3.0f} ms on ({} frames): excess {:.2f} x exp(-t / {:.0f} ms); rms left {:.3f} (no excess: {:.3f})".format(t0 * 1000, k, A, tau * 1000, r, r0))
            out["{} turn t0 {:.0f}".format(nm, t0 * 1000)] = dict(A=A, tau_ms=tau * 1000, rms=r, rms0=r0)
        base2 = float(np.median(offb[w & (R[:, c["run"]] >= 30)]))
        cv2 = curve(w, "run", range(1, 30))
        print("{}: after he comes into view; settled {:.3f} half bodies".format(nm, base2))
        print("  ms: rows, error / settled   " + "  ".join("{}: {}, {}".format(f * 25, n, "-" if e != e else "{:.2f}".format(e / base2)) for f, n, e in cv2))
        for t0 in (0.150, 0.175, 0.200, 0.225, 0.250):
            A, tau, r, r0, k = fit([f * 0.025 for f, _, _ in cv2], [e for _, _, e in cv2], [n for _, n, _ in cv2], t0, base2)
            print("  from {:3.0f} ms on ({} frames): excess {:.2f} x exp(-(t - t0) / {:.0f} ms); rms left {:.3f} (no excess: {:.3f})".format(t0 * 1000, k, A, tau * 1000, r, r0))
            out["{} appear t0 {:.0f}".format(nm, t0 * 1000)] = dict(A=A, tau_ms=tau * 1000, rms=r, rms0=r0)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

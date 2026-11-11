"""AIM3's third open point (docs/design/AIM3.md section 5.3): the slow weapons' reload delay. The simulator adds a random extra wait after
every shot of a slow weapon (RELOAD_JITTER: an exponential of mean 50 ms, at most 120 ms: "nobody fires on the exact frame the reload ends").
What do the pros do? The gap between two shots of the same weapon fired back to back, less the weapon's own reload, in the demos
(sets_lite3: a row a 25 ms frame; a shot = the ammunition of the weapon in hand falls). Rule 12: a human limit's parameter, measured.

    python tools/run/pro_refire.py [--files 400] [--json out.json]"""
import argparse
import glob
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RL, RG, LG, MG, SG, GL, PG = 0, 1, 2, 3, 4, 5, 6
REFIRE = {RL: 0.8, RG: 1.5, SG: 1.0, GL: 0.8}
NAMES = {RL: "rockets", RG: "rail", SG: "shotgun", GL: "grenades"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=400)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    files = sorted(glob.glob(os.path.join(root, "sets_lite3", "*", "*.npz")))
    rng = np.random.default_rng(1)
    files = [files[i] for i in sorted(rng.permutation(len(files))[:a.files])]
    gaps = {w: [] for w in REFIRE}
    for f in files:
        L = np.load(f)["lite"].astype(np.float64)
        for c in np.unique(L[:, 18]):
            U = L[L[:, 18] == c]
            if len(U) < 2000:
                continue
            w = U[:, 2].astype(int)
            for W, rf in REFIRE.items():
                am = U[:, 19 + W]
                shot = np.zeros(len(U), bool)
                shot[1:] = (am[1:] < am[:-1]) & (w[1:] == W) & (w[:-1] == W) & (U[1:, 0] > 0)
                t = np.nonzero(shot)[0] * 0.025
                if len(t) > 1:
                    g = np.diff(t)
                    gaps[W] += [float(x) for x in g[(g >= rf - 0.05) & (g <= rf + 0.5)]]
    out = {}
    print("{} demos. The gap between two shots of the same weapon, less its reload (frames of 25 ms; only gaps within 0.5 s of the reload: fired back to back)".format(len(files)))
    for W, rf in REFIRE.items():
        g = np.array(gaps[W]) - rf
        if len(g) < 50:
            continue
        on = float((g <= 0.0125).mean())
        one = float(((g > 0.0125) & (g <= 0.0375)).mean())
        print("  {:9s} {:6d} pairs: on the reload's own frame {:.0%}, one frame late {:.0%}, later {:.0%}; the extra wait: median {:.0f} ms, mean {:.0f} ms, mean of those within 150 ms {:.0f} ms".format(
            NAMES[W], len(g), on, one, 1 - on - one, 1000 * float(np.median(g)), 1000 * float(g.mean()), 1000 * float(g[g <= 0.15].mean())))
        out[NAMES[W]] = dict(n=int(len(g)), on_frame=on, one_late=one, median_ms=1000 * float(np.median(g)), mean_ms=1000 * float(g.mean()),
                             mean_within_150_ms=1000 * float(g[g <= 0.15].mean()), share_within_150=float((g <= 0.15).mean()))
    print("the simulator: an exponential of mean 50 ms capped at 120 ms on every such shot: mean about 43 ms, none on the frame")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

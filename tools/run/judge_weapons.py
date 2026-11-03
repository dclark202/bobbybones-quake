"""The judge's weapons set by hand (owner, 2026-10-28: "set rl and rg taken ... in line with LG"): owning the named weapons is
worth what owning the lightning gun is worth, at every time left (sim/win_judge.py's weapons network: its last layer's columns
RL, LG, RG; the named columns take LG's). Everything else of the fitted judge stays as it is.

    python tools/run/judge_weapons.py <judge.npz> <out.npz> [--like lg] [--set rl,rg] [--run <run> [tags]]
      --run: the log loss of both on every row of that run's self-play games (fit_b.py's rows), written into the meta

judge_v060_wpn.npz was made this way from judge_v060.npz (this tool reproduces it to the bit)."""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win_judge as WJ                                       # noqa: E402

COLS = ("rl", "lg", "rg")


def edit(P, like, names):
    P = {k: np.array(v, np.float64) for k, v in P.items()}
    j = COLS.index(like)
    for n in names:
        i = COLS.index(n)
        P["w_w2"][:, i] = P["w_w2"][:, j]
        P["w_b2"][i] = P["w_b2"][j]
    return P


def logloss(P, X):
    p = WJ.chance(P, X["d"], X["left"], X["sm"], X["wm"], X["so"], X["wo"])
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(X["y"] * np.log(p) + (1 - X["y"]) * np.log(1 - p)).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--like", default="lg")
    ap.add_argument("--set", default="rl,rg")
    ap.add_argument("--run", default="")
    ap.add_argument("tags", nargs="?", default="")
    a = ap.parse_args()
    P, meta = WJ.load(a.inp)
    names = [n for n in a.set.split(",") if n]
    Q = edit(P, a.like, names)
    meta = dict(meta, weapons="{} set to {}'s worth by hand (owner)".format(", ".join(n.upper() for n in names), a.like.upper()),
                made_from=os.path.basename(a.inp))
    if a.run:
        import fit_b as FB
        base = os.path.join(FB.SR, a.run, "selfplay")
        tags = a.tags.split(",") if a.tags else sorted((t for t in os.listdir(base) if t[:1] == "u" and t[1:].isdigit()), key=lambda t: int(t[1:]))
        X, cnt = FB.data([os.path.join(base, t) for t in tags])
        meta.update(logloss_all_original=logloss(P, X), logloss_all_edited=logloss(Q, X))
        print("log loss on all {} rows of {} games: fitted {:.4f}, edited {:.4f}".format(cnt["rows"], cnt["games"],
                                                                                         meta["logloss_all_original"], meta["logloss_all_edited"]))
    WJ.save(a.out, Q, meta)
    print("wrote", a.out, "|", meta["weapons"])


if __name__ == "__main__":
    main()

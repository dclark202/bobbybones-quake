"""The judge's weapons partly from the pros (owner, 2026-10-29: "Item 2 is the one"): a judge fitted on his own games
(tools/run/fit_b.py --out) keeps everything but the weapons' worth; that part (sim/win_judge.py's w_* network: owning the
rocket launcher, the lightning gun and the rail by the time left) is refitted on his games and the pros' together
(tools/run/pro_judge_rows.py), the pros' games given a share of the weight (--share: 0.5 = his and theirs count alike in
all). His stack's worth, the spread and the clock stay his: the pay goes on measuring his own game; what a weapon is worth
when it is used well is what his self-play cannot show. The axioms hold whatever the weapons are (their floor, W_FLOOR).

Reported, for each share: log loss on all his rows (in sample, as tools/run/judge_weapons.py), on the pros' games held out
(--folds by game: the weapons refitted without that fold), the weapons' value table (owning each, at the value table's
moments; 95% from --boot refits on the pros' games resampled), the axioms. --out writes the judge of the last share.

    python tools/run/fit_pro_weapons.py <judge.npz> <run> --pro data/sim_runs/judge/pro_rows [--maps all] [--share 0.25,0.5]
        [--tags u40,...] [--folds 5] [--boot 10] [--out judge_pro.npz] [--json report.json]"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import fit_b as FB                                           # noqa: E402
import win_judge as WJ                                       # noqa: E402

WEAPON_KEYS = ("w_w1", "w_b1", "w_w2", "w_b2")
EV_W = ("rail taken", "rocket launcher taken", "lightning gun taken")


def cat(A, B):
    return {k: np.concatenate([A[k], B[k]]) for k in A}


def fit_weapons(P0, X, wt, adam=300, lbfgs=150, l2=1e-4):
    """the judge P0 with only its weapons refitted on X, the rows weighted wt (a weighted mean log loss)"""
    torch.manual_seed(0)
    m = FB.Judge(P0)
    for k, p in m.P.items():
        p.requires_grad_(k in WEAPON_KEYS)
    ps = [m.P[k] for k in WEAPON_KEYS]
    Xt = {k: FB.T(v) for k, v in X.items()}
    W = FB.T(wt / wt.sum())

    def loss():
        p = torch.clamp(m(Xt), 1e-6, 1 - 1e-6)
        ll = -(Xt["y"] * torch.log(p) + (1 - Xt["y"]) * torch.log(1 - p))
        return (W * ll).sum() + l2 * sum((m.P[k] ** 2).sum() for k in ("w_w1", "w_w2"))
    opt = torch.optim.Adam(ps, lr=0.02)
    for _ in range(adam):
        opt.zero_grad()
        L = loss()
        L.backward()
        opt.step()
    opt2 = torch.optim.LBFGS(ps, lr=0.5, max_iter=lbfgs, line_search_fn="strong_wolfe")

    def closure():
        opt2.zero_grad()
        L = loss()
        L.backward()
        return L
    opt2.step(closure)
    return m


def weights(Xs, Xp, share):
    """per-row weights: his rows 1 each, the pros' so that they carry `share` of the whole"""
    ns, np_ = len(Xs["y"]), len(Xp["y"])
    return np.concatenate([np.ones(ns), np.full(np_, (share / max(1e-9, 1.0 - share)) * ns / max(1, np_))])


def ll(P, X):
    p = np.clip(FB.predict(P, X), 1e-6, 1 - 1e-6)
    y = X["y"]
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def wtable(m):
    led = FB.ledger_of(m)
    return {k: led[k] for k in EV_W}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("judge")
    ap.add_argument("run")
    ap.add_argument("--pro", required=True, help="the folder of tools/run/pro_judge_rows.py (a sub-folder a map)")
    ap.add_argument("--maps", default="all")
    ap.add_argument("--tags", default="", help="his self-play folders (default: every complete u<N>)")
    ap.add_argument("--share", default="0.25,0.5")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=10)
    ap.add_argument("--reinit", action="store_true", help="start the weapons' part from sim/win_judge.init() (a judge whose weapon sits at "
                    "its floor cannot leave it from there: the gradient through the floor's softplus is nearly nothing)")
    ap.add_argument("--pro-every", type=int, default=1, help="keep the pros' rows every this many seconds (1: all; they hardly change "
                    "from one second to the next, and the fit's time goes with the rows)")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    t0 = time.time()
    P0, meta0 = WJ.load(a.judge)
    if a.reinit:
        I0 = WJ.init()
        P0 = dict(P0, **{k: I0[k] for k in WEAPON_KEYS})
    J0 = FB.Judge(P0)
    base = os.path.join(FB.SR, a.run, "selfplay")
    tags = a.tags.split(",") if a.tags else sorted((t for t in os.listdir(base) if t[:1] == "u" and t[1:].isdigit()
                                                    and len(glob.glob(os.path.join(base, t, "rows_*.json"))) >= 10), key=lambda t: int(t[1:]))
    Xs, cs = FB.data([os.path.join(base, t) for t in tags])
    pmaps = sorted(m for m in os.listdir(a.pro) if os.path.isdir(os.path.join(a.pro, m))) if a.maps == "all" else a.maps.split(",")
    Xp, cp = FB.data([os.path.join(a.pro, m) for m in pmaps if glob.glob(os.path.join(a.pro, m, "rows_*.json"))])
    Xp["g"] = Xp["g"] + 1e6                                  # (the pros' games apart from his)
    if a.pro_every > 1:                                      # (every n-th second of each pro game: 600 - left on whole seconds)
        Xp = FB.sub(Xp, np.round(FB.GAME_LEN - Xp["left"]).astype(int) % a.pro_every == 0)
        cp = dict(cp, rows=len(Xp["y"]), every=a.pro_every)
    gp = np.unique(Xp["g"])
    print("his games: {} ({}), the pros' games: {} on {} maps ({} rows); the judge {} (made {})".format(
        cs["games"], ",".join(tags), cp["games"], len(pmaps), cp["rows"], os.path.basename(a.judge), meta0.get("made")))
    out = dict(judge=a.judge, run=a.run, tags=tags, pro_maps=pmaps, his=cs, pros=cp, shares={})
    base_ll = dict(his=ll(J0, Xs), pros=ll(J0, Xp))
    print("\nthe judge as fitted: log loss on his games {:.4f}, on the pros' {:.4f}".format(base_ll["his"], base_ll["pros"]))
    t_base = wtable(J0)
    out["base"] = dict(ll=base_ll, weapons=t_base)
    rng = np.random.default_rng(0)
    fold = dict(zip(gp, rng.permutation(len(gp)) % a.folds))
    fo = np.array([fold[g] for g in Xp["g"]])
    for share in [float(s) for s in a.share.split(",")]:
        X = cat(Xs, Xp)
        m = fit_weapons(P0, X, weights(Xs, Xp, share))
        held = np.zeros(len(Xp["y"]))
        for k in range(a.folds):
            tr = fo != k
            Xp_tr = FB.sub(Xp, tr)
            mk = fit_weapons(P0, cat(Xs, Xp_tr), weights(Xs, Xp_tr, share))
            held[~tr] = FB.predict(mk, FB.sub(Xp, ~tr))
        y = Xp["y"]
        hp = np.clip(held, 1e-6, 1 - 1e-6)
        ll_held = float(-(y * np.log(hp) + (1 - y) * np.log(1 - hp)).mean())
        tb = wtable(m)
        B = []
        gi = {g: np.nonzero(Xp["g"] == g)[0] for g in gp}
        for _ in range(a.boot):
            pick = rng.choice(gp, len(gp))
            Xb = {k: np.concatenate([v[gi[g]] for g in pick]) for k, v in Xp.items()}
            B.append(wtable(fit_weapons(P0, cat(Xs, Xb), weights(Xs, Xb, share), adam=150, lbfgs=80)))
        bad, n_s, sym = FB.axioms(m)
        r = dict(ll_his=ll(m, Xs), ll_pros_in=ll(m, Xp), ll_pros_held=ll_held, weapons=tb, axioms_ok=not bad, axioms_failures=len(bad))
        out["shares"][str(share)] = r
        print("\nshare {:.2f} of the weight on the pros' games: log loss his {:.4f} ({:+.4f}), the pros' held out {:.4f} ({:+.4f} against the judge "
              "as fitted); axioms: {}".format(share, r["ll_his"], r["ll_his"] - base_ll["his"], ll_held, ll_held - base_ll["pros"],
                                               "all hold" if not bad else "{} FAILURES".format(len(bad))))
        print("| owning | " + " | ".join("lead {:+d}, {}:{:02d} left".format(L, int(t) // 60, int(t) % 60) for L, t in FB.CELLS) + " |")
        print("|---|" + "---|" * len(FB.CELLS))
        for k in EV_W:
            cells = []
            for j in range(len(FB.CELLS)):
                lo, hi = np.percentile([b[k][j] for b in B], [2.5, 97.5]) if B else (np.nan, np.nan)
                cells.append("{:+.2f} [{:+.2f}, {:+.2f}] (was {:+.2f})".format(tb[k][j], lo, hi, t_base[k][j]))
            print("| {} | ".format(k) + " | ".join(cells) + " |")
        if a.out:
            WJ.save(a.out, m.numpy(), dict(meta0, weapons="refitted on his games and the pros' (share {:.2f}, {} pro games, maps {})".format(
                share, cp["games"], ",".join(pmaps)), made_from=os.path.basename(a.judge), pro_share=share, logloss_his=r["ll_his"],
                logloss_pros_held=ll_held, axioms_ok=not bad, made=time.strftime("%Y-%m-%d %H:%M")))
    if a.out:
        print("\nwritten", a.out, "(the last share)")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    print("({:.0f} s)".format(time.time() - t0))


if __name__ == "__main__":
    main()

"""2.0c, test 1, version 2 (docs/design/STRATEGY_2.md; docs/runs/2.1/DESIGN.md): the map sense's seeds scored by what a stay
brings. Measurement only; system Python.

    python tools/run/seed_calib2.py fit
    python tools/run/seed_calib2.py draw --map lostworld --zone 1 [--enemy-weapon 2]

Version 1 (seed_calib.py) scored 2-second slices with the enemy in view, which undersells a weapon that lands one big hit after a
wait: it rated the rail worst everywhere. Version 2 takes every moment with the enemy near and sent by the server (in view or not)
and scores the next WIN seconds: what he takes (the drop of his stack), what he deals (the pros: the hits he lands, the hit counter
of sets_lite2, times a nominal damage for the weapon in his hand at the hit; Bobby: the simulator's own damage dealt), and the one
less the other. The seeds of a pair of places are version 1's.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import seed_calib as C1  # noqa: E402

SS, ROOT, OUT, FEATS, CAT, BASE, NAMES, feats = C1.SS, C1.ROOT, C1.OUT, C1.FEATS, C1.CAT, C1.BASE, C1.NAMES, C1.feats
WIN = 5.0
NOM = np.array([65.0, 80.0, 6.0, 5.0, 20.0, 60.0, 20.0, 8.0, 50.0])   # a hit's damage by weapon (rockets, grenades: between splash and direct)


def pro_samples(files, step=10, back=40):
    F = int(round(WIN / 0.025))
    for f in files:
        d = np.load(f)
        L, first = d["lite"], d["first"]
        if len(L) < 400 or L.shape[1] < 33:
            continue
        seg = np.cumsum(first)
        pos, en, stack = L[:, 5:8], L[:, 8:11], L[:, 0] + L[:, 1]
        w = L[:, 2].astype(int).clip(0, 8)
        d1 = np.zeros(len(L))
        d1[1:] = np.where(seg[1:] == seg[:-1], np.maximum(0.0, stack[:-1] - stack[1:]), 0.0)
        d1[d1 < 2.0] = 0.0
        dh = np.diff(L[:, 32], prepend=L[0, 32])
        dh[first] = 0
        dh[(dh < 0) | (dh > 4)] = 0
        ct, cd = np.concatenate([[0.0], np.cumsum(d1)]), np.concatenate([[0.0], np.cumsum(dh * NOM[w])])
        idx = np.arange(back, len(L) - 1, step)
        idx = idx[(seg[idx] == seg[idx - back]) & (L[idx, 31] > 0)]
        idx = idx[np.linalg.norm(pos[idx] - en[idx], axis=1) < SS.NEAR]
        if not len(idx):
            continue
        last = np.searchsorted(seg, seg[idx], side="right") - 1
        e = np.minimum(idx + F, last)
        yield dict(pos=pos[idx], en=en[idx], wme=w[idx], wen=L[idx, 11].astype(int), moved=np.linalg.norm(pos[idx] - pos[idx - back], axis=1),
                   taken=ct[e + 1] - ct[idx + 1], dealt=cd[e + 1] - cd[idx + 1])


def bobby_samples(rec, mp, step=10, back=40):
    F = int(round(WIN / 0.025))
    for f in sorted(glob.glob(os.path.join(rec, "rec_{}_*.npz".format(mp)))):
        d = np.load(f, allow_pickle=True)
        pos, alive, wp = d["pos"].astype(np.float32), d["alive"], d["weapon"].astype(int)
        stack, dealt = d["hp"].astype(np.float32) + d["ar"].astype(np.float32), d["dealt"].astype(np.float64)
        T, n = alive.shape
        idx = np.arange(back, T - 1, step)
        for s in range(n):
            o = s ^ 1
            ii = idx[alive[idx, s] & alive[idx - back, s] & alive[idx, o]]
            ii = ii[np.linalg.norm(pos[ii, s] - pos[ii, o], axis=1) < SS.NEAR]
            d1 = np.zeros(T)
            d1[1:] = np.where(alive[:-1, s], np.maximum(0.0, stack[:-1, s] - np.maximum(stack[1:, s], 0.0)), 0.0)
            d1[d1 < 2.0] = 0.0
            ct, cd = np.concatenate([[0.0], np.cumsum(d1)]), np.concatenate([[0.0], np.cumsum(dealt[:, s])])
            e = np.minimum(ii + F, T - 1)
            yield dict(pos=pos[ii, s], en=pos[ii, o], wme=wp[ii, s], wen=wp[ii, o], moved=np.linalg.norm(pos[ii, s] - pos[ii - back, s], axis=1),
                       taken=ct[e + 1] - ct[ii + 1], dealt=cd[e + 1] - cd[ii + 1])


def rows(S, gen, cap):
    X, T, D = [], [], []
    for s in gen:
        if not len(s["pos"]):
            continue
        i, j = S.at(s["pos"]), S.at(s["en"])
        X.append(feats(S, i, j, s["pos"], s["en"], s["wme"], s["wen"], s["moved"]))
        T.append(s["taken"].astype(np.float32))
        D.append(s["dealt"].astype(np.float32))
    if not X:
        return np.zeros((0, len(FEATS)), np.float32), np.zeros(0, np.float32), np.zeros(0, np.float32)
    X, T, D = np.concatenate(X), np.concatenate(T), np.concatenate(D)
    if cap and len(T) > cap:
        k = np.random.default_rng(3).choice(len(T), cap, replace=False)
        X, T, D = X[k], T[k], D[k]
    return X, T, D


def r2(y, p):
    return float(1 - ((y - p) ** 2).mean() / max(float(y.var()), 1e-9))


def fit(a):
    from sklearn.ensemble import HistGradientBoostingRegressor as HGB
    import joblib
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    A, B, C = [], [], []
    for mp in a.maps.split(","):
        S = SS.Score(mp)
        files = list(np.random.default_rng(1).permutation(sorted(glob.glob(os.path.join(root, "sets_lite2", mp, "*.npz")))))
        h = len(files) // 2
        A.append(rows(S, pro_samples(files[:h]), a.cap))
        B.append(rows(S, pro_samples(files[h:]), a.cap))
        C.append(rows(S, bobby_samples(a.rec, mp), a.cap))
        print("{}: fit {} test {} Bobby {}".format(mp, len(A[-1][1]), len(B[-1][1]), len(C[-1][1])), flush=True)
    cat = lambda L: tuple(np.concatenate([x[k] for x in L]) for k in range(3))  # noqa: E731
    (Xa, Ta, Da), (Xb, Tb, Db), (Xc, Tc, Dc) = cat(A), cat(B), cat(C)
    kw = dict(max_iter=300, learning_rate=0.08, max_leaf_nodes=48, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    M = dict(take=HGB(categorical_features=CAT, **kw).fit(Xa, Ta), put=HGB(categorical_features=CAT, **kw).fit(Xa, Da))
    M0 = dict(take=HGB(categorical_features=[1, 2], **kw).fit(Xa[:, BASE], Ta), put=HGB(categorical_features=[1, 2], **kw).fit(Xa[:, BASE], Da))
    res = {}
    print("\nthe next {:.0f} s, on games the fit never saw (R2): takes, deals, deals less takes".format(WIN))
    for nm, X, T, D in (("the pros (the other half)", Xb, Tb, Db), ("Bobby ({})".format(os.path.basename(a.rec)), Xc, Tc, Dc)):
        if not len(T):
            continue
        res[nm] = {}
        for lab, m, x in (("the distance and the weapons alone", M0, X[:, BASE]), ("the seeds", M, X)):
            pt, pd = m["take"].predict(x), m["put"].predict(x)
            res[nm][lab] = dict(take=round(r2(T, pt), 4), put=round(r2(D, pd), 4), exchange=round(r2(D - T, pd - pt), 4))
            print("  {:<28} {:<36} {:.4f}  {:.4f}  {:.4f}".format(nm, lab, *res[nm][lab].values()))
        print("  {:<28} samples {}, mean taken {:.1f}, dealt {:.1f}".format(nm, len(T), T.mean(), D.mean()))
    for nm, X, T, D in (("the pros' other half", Xb, Tb, Db), ("Bobby", Xc, Tc, Dc)):
        print("\n{}, by the weapon in his hand: samples, takes, deals (measured), deals less takes; standing still only: the same".format(nm))
        for w_ in (0, 1, 2):
            m_ = X[:, 13] == w_
            s_ = m_ & (X[:, 12] < 60)
            print("  {:<10} {:>8} {:>6.1f} {:>6.1f} {:>+6.1f}   | {:>8} {:>6.1f} {:>6.1f} {:>+6.1f}".format(
                NAMES[w_], int(m_.sum()), T[m_].mean(), D[m_].mean(), (D[m_] - T[m_]).mean(),
                int(s_.sum()), T[s_].mean() if s_.any() else 0, D[s_].mean() if s_.any() else 0, (D[s_] - T[s_]).mean() if s_.any() else 0))
    joblib.dump(dict(models=M, feats=FEATS, maps=a.maps, win=WIN), os.path.join(OUT, "seed_v2.joblib"))
    json.dump(dict(results=res, n=dict(fit=len(Ta), test=len(Tb), bobby=len(Tc))), open(os.path.join(OUT, "seed_v2.json"), "w"), indent=1)
    print("\nsaved " + os.path.join(OUT, "seed_v2.joblib"))


def draw(a):
    import joblib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import zonemap as ZM
    M = joblib.load(os.path.join(OUT, "seed_v2.joblib"))["models"]
    S, Z = SS.Score(a.map), ZM.load(a.map)
    z = Z.locate(S.P)
    mem = np.nonzero(z == a.zone)[0]
    j = int(mem[np.linalg.norm((S.P[mem] - S.P[mem].mean(0)) * SS.WZ, axis=1).argmin()])
    n = len(S.P)
    I, J = np.arange(n), np.full(n, j)
    en = np.repeat(S.P[j][None], n, 0)
    fig, ax = plt.subplots(3, 3, figsize=(24, 22))
    o = np.argsort(S.P[:, 2])
    for c, (w, wn) in enumerate(((0, "rockets"), (1, "rail"), (2, "lightning"))):
        X = feats(S, I, J, S.P, en, np.full(n, w), np.full(n, a.enemy_weapon), np.zeros(n, np.float32))
        take, put = M["take"].predict(X), M["put"].predict(X)
        for r, (v, lab, cm, lo, hi) in enumerate(((take, "he takes", "RdYlGn_r", 0, 60), (put, "he deals", "RdYlGn", 0, 60),
                                                  (put - take, "deals less takes", "RdYlGn", -30, 30))):
            x = ax[r, c]
            sc = x.scatter(S.P[o, 0], S.P[o, 1], c=v[o], s=16, cmap=cm, vmin=lo, vmax=hi)
            x.plot(S.P[j, 0], S.P[j, 1], "k*", ms=24, mec="white")
            for k in range(Z.k):
                if (z == k).any() and Z.names[k]:
                    p_ = S.P[z == k].mean(0)
                    x.text(p_[0], p_[1], Z.names[k], fontsize=9, weight="bold", ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, lw=0, pad=1))
            fig.colorbar(sc, ax=x, shrink=0.6)
            x.set_title("he holds {}: {} in the next {:.0f} s".format(wn, lab, WIN), fontsize=13)
            x.set_aspect("equal")
    fig.suptitle("{}: the enemy (star) in zone {} {} with {}; he stays at each place (seeds version 2, the pros)".format(
        a.map, a.zone, Z.names[a.zone], NAMES[a.enemy_weapon]), fontsize=16)
    fig.tight_layout()
    f = os.path.join(ROOT, "docs", "design", "space", "seed2_{}_z{}_w{}.png".format(a.map, a.zone, a.enemy_weapon))
    fig.savefig(f, dpi=70)
    print("drawn " + f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fit", "draw"))
    ap.add_argument("--maps", default=SS.MAPS)
    ap.add_argument("--map", default="lostworld")
    ap.add_argument("--zone", type=int, default=1)
    ap.add_argument("--enemy-weapon", type=int, default=2)
    ap.add_argument("--cap", type=int, default=400000)
    ap.add_argument("--rec", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "cypher", "u90"))
    a_ = ap.parse_args()
    {"fit": fit, "draw": draw}[a_.cmd](a_)

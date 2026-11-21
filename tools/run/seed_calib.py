"""2.0c, test 1 (docs/design/STRATEGY_2.md): the calibration of the map sense's seeds. Measurement only: reads the pros' demo sets
(data/demo_root.txt, sets_lite), recorded games of Bobby (--rec) and the maps' tables (data/maps/space_<map>.npz); trains nothing of his.

    python tools/run/seed_calib.py fit  [--maps ...] [--demos 150]     fit on half the pros' games, test on the other half and on Bobby's
    python tools/run/seed_calib.py draw --map lostworld --zone 1 [--enemy-weapon 2]   the pictures: every place, the enemy in a zone

The question the seed answers: he is at place P, the enemy at place X, each with a weapon in hand; how much damage does he take in the
next 2 seconds (and, with the two swapped, how much does he put on the enemy)? The seeds of a pair of places, from the map alone: how
much of the ground the enemy can reach in 1.5 s sees P, by the length of the line (3), the same the other way (3), his seconds to cover
from the enemy and the enemy's from him (0 = not in sight), how open each place is to the whole map (B), the distance, the height
between them. Beside them the two weapons and how far he moved in the last second (0 = he hangs out there).

Three forecasts are set side by side on games the fit never saw: the distance and the weapons alone (no map); 2.0b's formula (the
weapon table times the share that sees him: one number); the seeds. System Python (scikit-learn, scipy, matplotlib).
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import space_score as SS  # noqa: E402

OUT = os.path.join(ROOT, "data", "sim_runs", "space")
FEATS = ("see_on_me_near", "see_on_me_mid", "see_on_me_far", "see_on_him_near", "see_on_him_mid", "see_on_him_far", "my_cover_s", "his_cover_s",
         "open_me", "open_him", "dist", "dz", "moved", "w_me", "w_him")
CAT = [13, 14]
BASE = [10, 13, 14]                                           # the distance and the two weapons: no map
NAMES = ("rockets", "rail", "lightning", "machine gun", "shotgun", "grenades", "plasma", "hmg", "gauntlet")


def feats(S, i, j, pos, en, wme, wen, moved):
    X = np.zeros((len(i), len(FEATS)), np.float32)
    for q in range(3):
        X[:, q] = S.seeb[q][j, i] / 255.0
        X[:, 3 + q] = S.seeb[q][i, j] / 255.0
    X[:, 6], X[:, 7] = S.cov[j, i] / 80.0, S.cov[i, j] / 80.0
    X[:, 8], X[:, 9] = S.B[i], S.B[j]
    X[:, 10] = np.linalg.norm(pos - en, axis=1)
    X[:, 11] = pos[:, 2] - en[:, 2]
    X[:, 12] = moved
    X[:, 13], X[:, 14] = np.clip(wme, 0, 8), np.clip(wen, 0, 8)
    return X


def rows(S, gen, W, cap=None):
    X, y, t = [], [], []
    for s in gen:
        if not len(s["pos"]):
            continue
        i, j = S.at(s["pos"]), S.at(s["en"])
        X.append(feats(S, i, j, s["pos"], s["en"], s["wme"], s["wen"], s["moved"]))
        y.append(s["fwd"].astype(np.float32))
        t.append(SS._threat(S, W, j, i, s["wen"]).astype(np.float32))
    if not X:
        return np.zeros((0, len(FEATS)), np.float32), np.zeros(0, np.float32), np.zeros(0, np.float32)
    X, y, t = np.concatenate(X), np.concatenate(y), np.concatenate(t)
    if cap and len(y) > cap:
        k = np.random.default_rng(3).choice(len(y), cap, replace=False)
        X, y, t = X[k], y[k], t[k]
    return X, y, t


def fit(a):
    from sklearn.ensemble import HistGradientBoostingRegressor as HGB
    from sklearn.metrics import roc_auc_score
    import joblib
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    W = np.array(json.load(open(os.path.join(OUT, "weapon_threat.json")))["dmg_s"])
    A, B, C = [], [], []
    for mp in a.maps.split(","):
        S = SS.Score(mp)
        files = list(np.random.default_rng(1).permutation(sorted(glob.glob(os.path.join(root, "sets_lite", mp, "*.npz")))))[:a.demos]
        h = len(files) // 2
        A.append(rows(S, SS._pro_samples(root, mp, files[:h]), W, a.cap))
        B.append(rows(S, SS._pro_samples(root, mp, files[h:]), W, a.cap))
        C.append(rows(S, SS._bobby_samples(a.rec, mp), W, a.cap))
        print("{}: fit {} test {} Bobby {}".format(mp, len(A[-1][1]), len(B[-1][1]), len(C[-1][1])), flush=True)
    cat = lambda L: tuple(np.concatenate([x[k] for x in L]) for k in range(3))  # noqa: E731
    (Xa, ya, ta), (Xb, yb, tb), (Xc, yc, tc) = cat(A), cat(B), cat(C)
    kw = dict(max_iter=300, learning_rate=0.08, max_leaf_nodes=48, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    seed = HGB(categorical_features=CAT, **kw).fit(Xa, ya)
    base = HGB(categorical_features=[1, 2], **kw).fit(Xa[:, BASE], ya)
    old = HGB(**kw).fit(ta[:, None], ya)                      # 2.0b's one number, given its best curve
    res = {}
    print("\ndamage taken in the next 2 s, on games the fit never saw (R2; AUC of 'hit for 20 or more'):")
    for nm, X, y, t in (("the pros (the other half)", Xb, yb, tb), ("Bobby ({})".format(os.path.basename(a.rec)), Xc, yc, tc)):
        if not len(y):
            continue
        res[nm] = {}
        for lab, p in (("the distance and the weapons alone", base.predict(X[:, BASE])), ("2.0b's threat (one number)", old.predict(t[:, None])),
                       ("the seeds", seed.predict(X))):
            r2 = 1 - ((y - p) ** 2).mean() / y.var()
            auc = roc_auc_score(y >= 20, p)
            res[nm][lab] = dict(r2=round(float(r2), 4), auc=round(float(auc), 4))
            print("  {:<28} {:<36} R2 {:.4f}  AUC {:.4f}".format(nm, lab, r2, auc))
        print("  {:<28} samples {}, mean taken {:.1f}, hit for 20 or more {:.1%}".format(nm, len(y), y.mean(), (y >= 20).mean()))
    # what the seeds lean on: the loss of skill on the pros' other half with one seed shuffled
    rng = np.random.default_rng(5)
    p0 = ((yb - seed.predict(Xb)) ** 2).mean()
    imp = {}
    for k, f in enumerate(FEATS):
        Xs = Xb.copy()
        Xs[:, k] = Xs[rng.permutation(len(Xs)), k]
        imp[f] = float((((yb - seed.predict(Xs)) ** 2).mean() - p0) / yb.var())
    print("\nwhat the seeds lean on (R2 lost with that one shuffled):")
    for f, v in sorted(imp.items(), key=lambda x: -x[1]):
        print("  {:<18} {:.4f}".format(f, v))
    joblib.dump(dict(model=seed, feats=FEATS, maps=a.maps), os.path.join(OUT, "seed_v1.joblib"))
    json.dump(dict(results=res, leans_on=imp, n=dict(fit=len(ya), test=len(yb), bobby=len(yc))), open(os.path.join(OUT, "seed_v1.json"), "w"), indent=1)
    print("\nsaved " + os.path.join(OUT, "seed_v1.joblib"))


def draw(a):
    """for the enemy in a zone (its middle point) with a weapon: every place of the map, standing still there, by the weapon in his
    hand: what he takes in 2 s, what he puts on the enemy (the same seed with the two swapped), and the one less the other"""
    import joblib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import zonemap as ZM
    m = joblib.load(os.path.join(OUT, "seed_v1.joblib"))["model"]
    S, Z = SS.Score(a.map), ZM.load(a.map)
    z = Z.locate(S.P)
    mem = np.nonzero(z == a.zone)[0]
    j = int(mem[np.linalg.norm((S.P[mem] - S.P[mem].mean(0)) * SS.WZ, axis=1).argmin()])
    n = len(S.P)
    I, J = np.arange(n), np.full(n, j)
    en = np.repeat(S.P[j][None], n, 0)
    still = np.zeros(n, np.float32)
    fig, ax = plt.subplots(3, 3, figsize=(24, 22))
    for c, (w, wn) in enumerate(((0, "rockets"), (1, "rail"), (2, "lightning"))):
        take = m.predict(feats(S, I, J, S.P, en, np.full(n, w), np.full(n, a.enemy_weapon), still))
        put = m.predict(feats(S, J, I, en, S.P, np.full(n, a.enemy_weapon), np.full(n, w), still))
        o = np.argsort(S.P[:, 2])
        for r, (v, lab, cm, lo, hi) in enumerate(((take, "he takes in 2 s", "RdYlGn_r", 0, 40), (put, "he puts on the enemy in 2 s", "RdYlGn", 0, 40),
                                                  (put - take, "the exchange (puts less takes)", "RdYlGn", -25, 25))):
            x = ax[r, c]
            sc = x.scatter(S.P[o, 0], S.P[o, 1], c=v[o], s=16, cmap=cm, vmin=lo, vmax=hi)
            x.plot(S.P[j, 0], S.P[j, 1], "k*", ms=24, mec="white")
            for k in range(Z.k):
                if (z == k).any() and Z.names[k]:
                    p = S.P[z == k].mean(0)
                    x.text(p[0], p[1], Z.names[k], fontsize=9, weight="bold", ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, lw=0, pad=1))
            fig.colorbar(sc, ax=x, shrink=0.6)
            x.set_title("he holds {}: {}".format(wn, lab), fontsize=13)
            x.set_aspect("equal")
    fig.suptitle("{}: the enemy (star) in zone {} {} with {}; he stands still at each place (the seeds, fitted on the pros)".format(
        a.map, a.zone, Z.names[a.zone], NAMES[a.enemy_weapon]), fontsize=16)
    fig.tight_layout()
    d = os.path.join(ROOT, "docs", "design", "space")
    f = os.path.join(d, "seed_{}_z{}_w{}.png".format(a.map, a.zone, a.enemy_weapon))
    fig.savefig(f, dpi=70)
    print("drawn " + f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fit", "draw"))
    ap.add_argument("--maps", default=SS.MAPS)
    ap.add_argument("--map", default="lostworld")
    ap.add_argument("--zone", type=int, default=1)
    ap.add_argument("--enemy-weapon", type=int, default=2)
    ap.add_argument("--demos", type=int, default=150)
    ap.add_argument("--cap", type=int, default=400000)
    ap.add_argument("--rec", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "cypher", "u90"))
    a_ = ap.parse_args()
    {"fit": fit, "draw": draw}[a_.cmd](a_)

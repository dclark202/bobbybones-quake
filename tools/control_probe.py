"""The "in control" probe (v0.4.3, B-280): is his share of the next two mega / red armor spawns already readable from what is
in his head? Reads the games of tools/control_games.py, fits a linear and a small MLP probe from the frozen states (the
brain's state, the hands' memory, both) to the hindsight label on part of the games and scores them on the rest, beside
baselines from plain numbers (the score lead, the clock, his stack minus the believed enemy stack, the item timers, all of
these together; and, as a ceiling of what positions alone tell, the true walking-time race to both items).

    python tools/control_probe.py --games "<dir>/ctl_*.npz" [--test-share 0.3] [--seed 0] [--timelines 3]
    (Anaconda Python, CPU)

offline_labels() is also tools/control_ident.py's independent count of the label.
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np

INF = np.iinfo(np.int64).max


def offline_labels(aux, cols, done, D):
    """the label by hindsight, counted afresh from a replay's rows (row r: info["aux"] of the step that made frame r):
    aux [T, n, C], done [T, n] -> (two, one, mh, ra), each [T, n], for each row as a query frame (-1: none). Duels (seats 2m, 2m + 1)."""
    C = {c: i for i, c in enumerate(cols)}
    T, n = aux.shape[:2]
    two = np.full((T, n), -1.0, np.float32)
    one = np.full((T, n), -1.0, np.float32)
    per = [np.full((T, n), -1.0, np.float32), np.full((T, n), -1.0, np.float32)]
    for m in range(n // 2):
        q2 = (2 * m, 2 * m + 1)
        inst = []                                            # [spawn, take, by, round, item]
        opn = [None, None]
        rnd = 0
        rnd_at = np.zeros(T, np.int64)
        for r in range(T):
            for k in (0, 1):
                tk_ = aux[r, list(q2), C["mega_take"] + k]
                if (tk_ == 1).any() and opn[k] is not None:
                    opn[k][1], opn[k][2] = r, q2[int(np.nonzero(tk_ == 1)[0][0])]
                    opn[k] = None
            if done[r, list(q2)].any():
                rnd += 1
                opn = [None, None]
            for k in (0, 1):
                if aux[r, q2[0], C["mega_s"] + k] == 0 and opn[k] is None:
                    opn[k] = [r, INF, -1, rnd, k]
                    inst.append(opn[k])
            rnd_at[r] = rnd
        if not inst:
            continue
        I = np.array(inst, dtype=np.int64).reshape(-1, 5)
        for q in range(T):
            F = q + D
            if F >= T or aux[q, q2[0], C["ctl_ok"]] < 0.5:
                continue
            c_ = I[(I[:, 3] == rnd_at[q]) & (I[:, 1] > q) & (I[:, 0] <= F)]
            c_ = c_[np.lexsort((c_[:, 4], c_[:, 0]))][:2]
            live = rnd_at[F] == rnd_at[q]
            for j, s in enumerate(q2):
                v, okk = [], []
                for x in c_:
                    tk = x[1] <= F
                    okk.append(tk or live)
                    v.append((1.0 if x[2] == s else 0.0) if tk else 0.5)
                if len(c_) >= 1 and okk[0]:
                    one[q, s] = v[0]
                if len(c_) >= 2 and okk[0] and okk[1]:
                    two[q, s] = 0.5 * (v[0] + v[1])
            for k in (0, 1):                                 # each item alone
                ck = I[(I[:, 3] == rnd_at[q]) & (I[:, 1] > q) & (I[:, 0] <= F) & (I[:, 4] == k)]
                if not len(ck):
                    continue
                x = ck[np.argmin(ck[:, 0])]
                tk = x[1] <= F
                if tk or live:
                    for s in q2:
                        per[k][q, s] = (1.0 if x[2] == s else 0.0) if tk else 0.5
    return two, one, per[0], per[1]


def load(paths):
    """per sample row (a state row of a kept game, both seats): features and label; games' ids for the split"""
    rows = []
    for p in sorted({x for g in paths for x in glob.glob(g)}):
        d = np.load(p, allow_pickle=False)
        meta = json.loads(str(d["meta"]))
        cols = [str(c) for c in d["cols"]]
        C = {c: i for i, c in enumerate(cols)}
        A, D = d["aux"], int(meta["control_d"])
        sf = d["sf"]
        gs = json.loads(str(d["games"]))
        for g in gs:
            m = g["match"]
            sel = np.nonzero((sf >= g["start"] + 1) & (sf <= g["end"]))[0]
            if not len(sel):
                continue
            f = sf[sel]
            r = f - 1                                        # the aux row of the frame his head had seen at sample f
            rl = r + D                                       # ... whose label comes D rows later
            keep = rl < len(A)
            sel, f, r, rl = sel[keep], f[keep], r[keep], rl[keep]
            for j, s in enumerate((2 * m, 2 * m + 1)):
                e = 2 * m + 1 - j
                lab = A[rl, s, C["ctl_lab"]]
                one = A[rl, s, C["ctl_one"]]
                fr = d["frags"][r]
                rows.append(dict(
                    map=meta["map"], game="{}:{}".format(os.path.basename(p), g["gid"]), seat=j, f=f, tick=d["tick"][r, m],
                    lab=lab, one=one, lead=(fr[:, s] - fr[:, e]).astype(np.float32),
                    stack=(np.maximum(d["hp"][r, s], 0) + d["armor"][r, s]).astype(np.float32),
                    es=A[r, s, C["es_stack"]], en_stack=(np.maximum(d["hp"][r, e], 0) + d["armor"][r, e]).astype(np.float32),
                    mega_s=A[r, s, C["mega_s"]], red_s=A[r, s, C["red_s"]],
                    race=np.stack([A[r, s, C["race_en_mh"]] - A[r, s, C["race_me_mh"]], A[r, s, C["race_en_ra"]] - A[r, s, C["race_me_ra"]],
                                   A[r, s, C["race_me_mh"]], A[r, s, C["race_me_ra"]]], 1),
                    bel=d["bel"][sel, s].astype(np.float32), mem=d["mem"][sel, s].astype(np.float32),
                    ahead=d["ahead"][sel, s].astype(np.float32) if "ahead" in d.files else np.zeros((len(sel), 0), np.float32),
                    final=g["final"][j] - g["final"][1 - j], ahead_L=meta.get("ahead")))
    return rows


def cat(rows, key):
    return np.concatenate([r_[key] for r_ in rows])


def basefeat(rows, which):
    tick = cat(rows, "tick").astype(np.float32)
    clock = np.minimum(tick, 24000) / 24000.0
    lead = cat(rows, "lead")
    st = cat(rows, "stack") / 200.0
    es = cat(rows, "es") / 200.0
    ms, rs = cat(rows, "mega_s") / 40.0, cat(rows, "red_s") / 40.0
    tm = np.stack([ms, rs, ms == 0, rs == 0], 1).astype(np.float32)
    F = dict(lead=np.stack([np.tanh(lead / 3.0), lead / 10.0], 1), clock=np.stack([clock, clock ** 2], 1),
             stack=np.stack([st, es, st - es], 1), timers=tm)
    if which == "plain":
        X = np.concatenate([F[k] for k in ("lead", "clock", "stack", "timers")], 1)
        lc = np.stack([np.tanh(lead / 3.0) * clock], 1)
        return np.concatenate([X, lc, (st - es)[:, None] * tm[:, :2]], 1)
    if which == "race":
        rc = np.clip(cat(rows, "race") / 30.0, -1, 1)
        return np.concatenate([rc, tm, rc[:, :2] * tm[:, 2:4]], 1)
    if which == "plain+race":
        return np.concatenate([basefeat(rows, "plain"), basefeat(rows, "race")], 1)
    return F[which]


def fit(Xtr, ytr, Xte, kind, seed=0, epochs=60, wd=1e-4):
    import torch
    torch.manual_seed(seed)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    xt = torch.tensor((Xtr - mu) / sd, dtype=torch.float32)
    yt = torch.tensor(ytr, dtype=torch.float32)
    xe = torch.tensor((Xte - mu) / sd, dtype=torch.float32)
    d = xt.shape[1]
    if kind == "linear":
        net = torch.nn.Linear(d, 1)
    else:
        net = torch.nn.Sequential(torch.nn.Linear(d, 64), torch.nn.ReLU(), torch.nn.Linear(64, 1))
    opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=wd)
    nv = max(1, len(xt) // 10)                               # the last tenth of the training rows for early stopping
    perm = torch.randperm(len(xt))
    vi, ti = perm[:nv], perm[nv:]
    best, bst, bad = 1e9, None, 0
    lossf = torch.nn.BCEWithLogitsLoss()
    for ep in range(epochs):
        p2 = ti[torch.randperm(len(ti))]
        for b in range(0, len(p2), 512):
            ix = p2[b:b + 512]
            opt.zero_grad()
            lossf(net(xt[ix])[:, 0], yt[ix]).backward()
            opt.step()
        with torch.no_grad():
            vl = float(lossf(net(xt[vi])[:, 0], yt[vi]))
        if vl < best - 1e-4:
            best, bad = vl, 0
            bst = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= 6:
                break
    net.load_state_dict(bst)
    with torch.no_grad():
        return torch.sigmoid(net(xe)[:, 0]).numpy()


def auc(y, p):
    """AUC of p for the decided labels (y > 0.5 against y < 0.5)"""
    pos, neg = p[y > 0.5], p[y < 0.5]
    if not len(pos) or not len(neg):
        return float("nan")
    allp = np.concatenate([pos, neg])
    rk = np.argsort(np.argsort(allp, kind="stable"), kind="stable").astype(np.float64) + 1
    return float((rk[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def score(y, p, base):
    eps = 1e-6
    br = float(np.mean((p - y) ** 2))
    bce = float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    acc = float(np.mean(((p > 0.5) == (y > 0.5))[y != 0.5]))
    return dict(brier=round(br, 4), skill=round(1 - br / base, 3), bce=round(bce, 4), auc=round(auc(y, p), 3), acc=round(acc, 3))


def calib(y, p, k=5):
    e = np.linspace(0, 1, k + 1)
    out = []
    for i in range(k):
        m = (p >= e[i]) & (p < e[i + 1] if i < k - 1 else p <= 1)
        if m.sum() > 50:
            out.append("{:.1f}-{:.1f}: {:.2f} ({})".format(e[i], e[i + 1], float(y[m].mean()), int(m.sum())))
    return "; ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True)
    ap.add_argument("--test-share", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timelines", type=int, default=3)
    ap.add_argument("--label", default="lab", choices=("lab", "one"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rows = load([a.games])
    games = sorted({r_["game"] for r_ in rows})
    rng = np.random.default_rng(a.seed)
    test_g = set(rng.choice(games, max(1, int(round(a.test_share * len(games)))), replace=False).tolist())
    # (both seats of a game go to the same side; the split is by game)
    y_all = cat(rows, a.label)
    tick = cat(rows, "tick")
    ing = tick >= 0
    defined = (y_all >= 0) & ing
    print("games {} on {} maps ({} test); state rows in games {}; label defined {:.1%} of them (two spawns within {} s)".format(
        len(games), len({r_["map"] for r_ in rows}), len(test_g), int(ing.sum()), float(defined[ing].mean()),
        "the run's horizon"))
    vals, cnt = np.unique(y_all[defined], return_counts=True)
    print("label values: " + ", ".join("{:.2f}: {:.1%}".format(v, c / cnt.sum()) for v, c in zip(vals, cnt)))
    by_map = {}
    for r_ in rows:
        m_ = (r_[a.label] >= 0) & (r_["tick"] >= 0)
        by_map.setdefault(r_["map"], [0, 0])
        by_map[r_["map"]][0] += int(m_.sum())
        by_map[r_["map"]][1] += int((r_["tick"] >= 0).sum())
    print("defined by map: " + ", ".join("{} {:.0%}".format(k, v[0] / max(1, v[1])) for k, v in sorted(by_map.items())))
    te = np.concatenate([np.full(len(r_["f"]), r_["game"] in test_g) for r_ in rows])
    mp = np.concatenate([np.full(len(r_["f"]), r_["map"]) for r_ in rows])
    tr_m, te_m = defined & ~te, defined & te
    y_tr, y_te = y_all[tr_m], y_all[te_m]
    base = float(np.mean((y_te - y_tr.mean()) ** 2))
    print("train rows {}, test rows {}; the constant guess's Brier {:.4f}".format(int(tr_m.sum()), int(te_m.sum()), base))
    feats = {}
    for k in ("lead", "clock", "stack", "timers", "plain", "race", "plain+race"):
        feats["base:" + k] = basefeat(rows, k)
    bel, mem = cat(rows, "bel"), cat(rows, "mem")
    feats["brain"] = bel
    feats["memory"] = mem
    feats["brain+memory"] = np.concatenate([bel, mem], 1)
    feats["brain+plain"] = np.concatenate([bel, feats["base:plain"]], 1)
    feats["brain+memory+plain"] = np.concatenate([bel, mem, feats["base:plain"]], 1)
    ahd = cat(rows, "ahead")
    L = rows[0]["ahead_L"]
    if ahd.shape[1] and L and L.get("race"):
        r0 = 5 * len(L["horiz"]) + int(L["n_target"]) + len(L["appear"]) + 1
        feats["brain's race readout"] = ahd[:, r0:r0 + 6]
    res = {}
    preds = {}
    print("\n{:<26} {:>7} {:>7} {:>7} {:>6} {:>6}".format("features / probe", "Brier", "skill", "BCE", "AUC", "acc"))
    for name, X in feats.items():
        kinds = ("linear", "mlp") if (name.startswith(("brain", "memory")) or name in ("base:plain", "base:plain+race")) else ("linear",)
        for kd in kinds:
            p = fit(X[tr_m], y_tr, X[te_m], kd, seed=a.seed)
            s = score(y_te, p, base)
            res["{} / {}".format(name, kd)] = s
            preds["{} / {}".format(name, kd)] = p
            print("{:<26} {:>7} {:>7} {:>7} {:>6} {:>6}".format("{} / {}".format(name, kd)[:26], s["brier"], s["skill"], s["bce"], s["auc"], s["acc"]))
    for k in ("brain+memory / mlp", "brain / linear", "base:plain / mlp", "brain+memory+plain / mlp"):
        if k in preds:
            print("calibration {}: {}".format(k, calib(y_te, preds[k])))
    print("\nby map (test rows; skill = 1 - Brier / constant guess's):")
    mte = mp[te_m]
    for m_ in sorted(set(mte)):
        sel = mte == m_
        if sel.sum() < 200:
            continue
        b_ = float(np.mean((y_te[sel] - y_tr.mean()) ** 2))
        line = []
        for k in ("base:plain / mlp", "base:plain+race / mlp", "brain+memory / mlp", "brain+memory+plain / mlp"):
            if k in preds:
                line.append("{} {:.3f} (AUC {:.2f})".format(k.split(" / ")[0], 1 - float(np.mean((preds[k][sel] - y_te[sel]) ** 2)) / b_,
                                                            auc(y_te[sel], preds[k][sel])))
        print("  {:<15} rows {:>6} | {}".format(m_, int(sel.sum()), " | ".join(line)))
    k_best = "brain+memory / mlp"
    if a.timelines and k_best in preds:
        print("\ntimelines (test games, seat 0; every 30 s: clock, score lead, his predicted control (brain+memory), the label):")
        pr_full = np.full(len(y_all), np.nan)
        pr_full[te_m] = preds[k_best]
        off = 0
        shown = 0
        for r_ in rows:
            n_ = len(r_["f"])
            if r_["game"] in test_g and r_["seat"] == 0 and shown < a.timelines:
                tk = r_["tick"]
                pts = []
                for t0 in range(0, int(tk.max()) + 1, 1200):
                    i_ = np.nonzero((tk >= t0) & (tk < t0 + 1200))[0]
                    if not len(i_):
                        continue
                    pv = pr_full[off + i_]
                    lv = r_[a.label][i_]
                    pts.append("{}:{:02d} {:+d} {} {}".format(t0 // 2400, (t0 % 2400) // 40, int(r_["lead"][i_[-1]]),
                                                         "{:.2f}".format(np.nanmean(pv)) if np.isfinite(pv).any() else " -- ",
                                                         "{:.2f}".format(lv[lv >= 0].mean()) if (lv >= 0).any() else " -- "))
                print("  {} {} (final {:+d}):\n    ".format(r_["map"], r_["game"], int(r_["final"])) + " | ".join(pts))
                shown += 1
            off += n_
    if a.out:
        json.dump(dict(results=res, games=len(games), test_games=len(test_g)), open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()

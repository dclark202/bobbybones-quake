"""The "in control" probe (v0.4.3, B-280): is his share of the next two mega / red armor spawns already readable from what is
in his head? Reads the games of tools/control_games.py, fits a linear and a small MLP probe from the frozen states (the
brain's state, the hands' memory, both) to the hindsight label on part of the games and scores them on the rest, beside
baselines from plain numbers (the score lead, the clock, his stack minus the believed enemy stack, the item timers, all of
these together; and, as a ceiling of what positions alone tell, the true walking-time race to both items).

    python tools/control_probe.py --games "<dir>/ctl_*.npz" [--folds 5] [--seed 0] [--timelines 3]
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
                ext_ = {k_: A[rl, s, C["ctl_" + k_]] for k_ in ("mh", "ra") if "ctl_" + k_ in C}
                fr = d["frags"][r]
                g0_, g1_ = g["start"], g["end"] + 1          # his last two takes' outcomes (1 he, 0 the enemy) up to each row: "control so far"
                tk_ = np.maximum(A[g0_:g1_, s, C["mega_take"]], A[g0_:g1_, s, C["red_take"]])
                fs_ = np.nonzero(tk_ > 0)[0] + g0_
                oc_ = (np.maximum(np.where(A[fs_, s, C["mega_take"]] > 0, A[fs_, s, C["mega_take"]], 0),
                                  A[fs_, s, C["red_take"]]) == 1).astype(np.float32)
                k_ = np.searchsorted(fs_, r, side="right")   # takes at rows <= r
                l1_ = np.where(k_ >= 1, oc_[np.maximum(k_ - 1, 0)] if len(oc_) else 0.5, 0.5)
                l2_ = np.where(k_ >= 2, oc_[np.maximum(k_ - 2, 0)] if len(oc_) else 0.5, 0.5)
                rows.append(dict(**ext_, past=np.stack([l1_, 0.5 * (l1_ + l2_)], 1).astype(np.float32),
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
             stack=np.stack([st, es, st - es], 1), timers=tm, past=cat(rows, "past"))
    if which == "plain":
        X = np.concatenate([F[k] for k in ("lead", "clock", "stack", "timers", "past")], 1)
        lc = np.stack([np.tanh(lead / 3.0) * clock], 1)
        return np.concatenate([X, lc, (st - es)[:, None] * tm[:, :2]], 1)
    if which == "race":
        rc = np.clip(cat(rows, "race") / 30.0, -1, 1)
        return np.concatenate([rc, tm, rc[:, :2] * tm[:, 2:4]], 1)
    if which == "plain+race":
        return np.concatenate([basefeat(rows, "plain"), basefeat(rows, "race")], 1)
    return F[which]


def fit(Xtr, ytr, Xte, kind, seed=0, epochs=60, wd=1e-4, groups=None):
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
        net = torch.nn.Sequential(torch.nn.Dropout(0.2), torch.nn.Linear(d, 32), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(32, 1))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=wd)
    if groups is not None:                                   # early stopping on a fifth of the training GAMES (rows of a game are alike)
        ug_ = np.unique(groups)
        rs_ = np.random.default_rng(seed + 1)
        vg_ = set(rs_.choice(ug_, max(1, len(ug_) // 5), replace=False).tolist())
        vm_ = np.array([g_ in vg_ for g_ in groups])
        vi, ti = torch.tensor(np.nonzero(vm_)[0]), torch.tensor(np.nonzero(~vm_)[0])
    else:
        nv = max(1, len(xt) // 10)
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
        net.eval()
        with torch.no_grad():
            vl = float(lossf(net(xt[vi])[:, 0], yt[vi]))
        if vl < best - 1e-4:
            best, bad = vl, 0
            bst = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= 4:
                break
        net.train()
    net.load_state_dict(bst)
    net.eval()
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
    ap.add_argument("--folds", type=int, default=5, help="folds by game: every game is scored once, by probes fitted on the others")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stride", type=int, default=2, help="training rows: every this many (rows 0.4 s apart are alike)")
    ap.add_argument("--timelines", type=int, default=3)
    ap.add_argument("--label", default="lab", choices=("lab", "one"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rows = load([a.games])
    games = sorted({r_["game"] for r_ in rows})
    rng = np.random.default_rng(a.seed)
    gperm = list(rng.permutation(games))
    fold_of = {g_: i_ % a.folds for i_, g_ in enumerate(gperm)}        # (both seats of a game in the same fold)
    y_all = cat(rows, a.label)
    tick = cat(rows, "tick")
    ing = tick >= 0
    defined = (y_all >= 0) & ing
    print("games {} on {} maps; state rows in games {} (every 0.4 s, both seats); label defined on {:.1%} of them".format(
        len(games), len({r_["map"] for r_ in rows}), int(ing.sum()), float(defined[ing].mean())))
    vals, cnt = np.unique(y_all[defined], return_counts=True)
    print("label values: " + ", ".join("{:.2f}: {:.1%}".format(v, c / cnt.sum()) for v, c in zip(vals, cnt)))
    for k_ in ("one",) + (("mh", "ra") if "mh" in rows[0] else ()):
        v_ = cat(rows, k_)
        print("  the {} label defined on {:.1%}".format(k_, float(((v_ >= 0) & ing)[ing].mean())))
    by_map = {}
    for r_ in rows:
        m_ = (r_[a.label] >= 0) & (r_["tick"] >= 0)
        by_map.setdefault(r_["map"], [0, 0, 0])
        by_map[r_["map"]][0] += int(m_.sum())
        by_map[r_["map"]][1] += int((r_["tick"] >= 0).sum())
    print("defined by map: " + ", ".join("{} {:.0%}".format(k, v[0] / max(1, v[1])) for k, v in sorted(by_map.items())))
    mp = np.concatenate([np.full(len(r_["f"]), r_["map"]) for r_ in rows])
    gid = np.concatenate([np.full(len(r_["f"]), r_["game"]) for r_ in rows])
    fo = np.array([fold_of[g_] for g_ in gid])
    sub = np.zeros(len(gid), bool)
    sub[::max(1, a.stride)] = True
    feats = {}
    for k in ("lead", "clock", "stack", "timers", "past", "plain", "race", "plain+race"):
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
    yd = y_all[defined]
    base = float(np.mean((yd - yd.mean()) ** 2))
    print("folds {} by game; the constant guess's Brier {:.4f} (the label's own spread)".format(a.folds, base))
    res, preds = {}, {}
    print("\n{:<28} {:>7} {:>7} {:>7} {:>6} {:>6}".format("features / probe (out of fold)", "Brier", "skill", "BCE", "AUC", "acc"))
    for name, X in feats.items():
        kinds = ("linear", "mlp") if (name.startswith(("brain", "memory")) or name in ("base:plain", "base:plain+race")) else ("linear",)
        if name == "brain's race readout":
            kinds = ("linear",)
        for kd in kinds:
            p = np.full(len(y_all), np.nan)
            for k_ in range(a.folds):
                tr_ = defined & (fo != k_) & sub
                te_ = defined & (fo == k_)
                p[te_] = fit(X[tr_], y_all[tr_], X[te_], kd, seed=a.seed + k_, wd=1e-3, groups=gid[tr_])
            pd_ = p[defined]
            s = score(yd, pd_, base)
            key = "{} / {}".format(name, kd)
            res[key], preds[key] = s, p
            print("{:<28} {:>7} {:>7} {:>7} {:>6} {:>6}".format(key[:28], s["brier"], s["skill"], s["bce"], s["auc"], s["acc"]), flush=True)
    for k in ("base:plain / mlp", "brain / linear", "brain+memory / mlp", "brain+memory+plain / mlp"):
        if k in preds:
            print("calibration {} (predicted band: mean label (rows)): {}".format(k, calib(yd, preds[k][defined])))
    print("\nby map (out of fold; skill = 1 - Brier / the map's own constant guess's; AUC)")
    ks_ = ("base:plain / mlp", "base:plain+race / mlp", "brain / linear", "brain+memory / mlp", "brain+memory+plain / mlp")
    print("  {:<15} {:>6} {:>5} ".format("map", "rows", "games") + " ".join("{:>17}".format(k.split(" / ")[0][:17]) for k in ks_))
    by = {}
    for m_ in sorted(set(mp)):
        sel = defined & (mp == m_)
        if sel.sum() < 200:
            continue
        b_ = float(np.mean((y_all[sel] - y_all[sel].mean()) ** 2))
        cells = []
        for k in ks_:
            pk_ = preds[k][sel]
            cells.append("{:>8.3f} ({:.2f})".format(1 - float(np.mean((pk_ - y_all[sel]) ** 2)) / b_, auc(y_all[sel], pk_)))
            by.setdefault(m_, {})[k] = cells[-1].strip()
        print("  {:<15} {:>6} {:>5} ".format(m_, int(sel.sum()), len({g_ for g_ in gid[sel]})) + " ".join(cells))
    k_best = "brain+memory / mlp"
    if a.timelines and k_best in preds:
        print("\ntimelines (seat 0; every 30 s: clock, score lead then, his control as the probe reads it from his head, the label):")
        off, shown, seen = 0, 0, set()
        for r_ in rows:
            n_ = len(r_["f"])
            mp_ok = r_["map"] not in seen
            if r_["seat"] == 0 and shown < a.timelines and mp_ok:
                seen.add(r_["map"])
                tk = r_["tick"]
                pts = []
                for t0 in range(0, int(tk.max()) + 1, 1200):
                    i_ = np.nonzero((tk >= t0) & (tk < t0 + 1200))[0]
                    if not len(i_):
                        continue
                    pv = preds[k_best][off + i_]
                    lv = r_[a.label][i_]
                    pts.append("{}:{:02d} {:+d} {} {}".format(t0 // 2400, (t0 % 2400) // 40, int(r_["lead"][i_[-1]]),
                                                         "{:.2f}".format(np.nanmean(pv)) if np.isfinite(pv).any() else "--",
                                                         "{:.2f}".format(lv[lv >= 0].mean()) if (lv >= 0).any() else "--"))
                print("  {} {} (final {:+d}):\n    ".format(r_["map"], r_["game"], int(r_["final"])) + " | ".join(pts))
                shown += 1
            off += n_
    if a.out:
        json.dump(dict(results=res, by_map=by, games=len(games), folds=a.folds), open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()

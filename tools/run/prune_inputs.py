"""2.1: which inputs help the appraisals forecast what a choice brings? (owner, 2026-11-11: "before doing any of the training we should
run this appraisal and prune my ideas down"). The appraisals are a supervised model (sim/appraise.py): from the situation and a
candidate instruction they forecast the damage both ways, who dies, the item and dV. This tool fits that same model on recorded
frozen-moment branches (tools/run/branch_record.py's dumps: the trainer's own rows, labels and masks) with every input, and again with
one named group of inputs blanked (set to its mean over the training rows, in training and in the test), and reports what the group
adds to the forecast on branches it has not seen:
    skill of an output = 1 - (squared error) / (squared error of the best constant): R2 for dealt, taken, dv; the Brier skill for the chances
    gain of a group    = skill with every input - skill with the group blanked, by output
The split is by MOMENT (every branch of one frozen moment is in the same fold), k folds x several seeds; the gain's mean and its standard
error over the folds x seeds. THE NOISE: the same fit repeated with nothing blanked but another seed: the spread of the skill between
seeds on the same fold. A group PASSES when its gain on dV is above 2 standard errors AND above that noise. A readout for a decision
(what goes into a run), never a pay or a target. Measurement only: CPU by default, reads dumps, trains nothing that plays.

    <anaconda python> tools/run/prune_inputs.py <dump dir or npz ...> --groups finish,known,unsure,spawn_odds [--folds 4] [--seeds 3]
                      [--epochs 30] [--hid 256] [--device cpu] [--out <json>]
    a group: a name of GROUPS below, or name=<prefix>|<prefix> of the row's own numbers (sim/duel_env.py INS_FEAT, then the map sense's
    eight "ms_0" .. "ms_7"), or one of the blocks: row (every number of the row), weapon (which weapon is asked), brain, memory, head
    (the three parts of the situation)."""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
GROUPS = {"finish": ("fin_", "fin_hi_", "fire_"),               # the finish time: seconds to finish him, the cautious ones, seconds of fire, per weapon
          "known": ("known",), "unsure": ("unsure",), "spawn_odds": ("spawn_odds",), "when": ("when_ok", "when"),
          "sees": ("sees_1", "sees_2", "sees_4", "seen_me"), "lead": ("t_me", "t_en", "lead"), "mapsense": ("ms_",),
          "point": ("pt_given", "pt_range", "pt_line"), "item": ("item_up", "item_back")}
PRIMARY = "dv"


def load(paths):
    """the dumps -> S [R, sit] float32, C [R, cand], Y [R, d], M [R, d], grp [R] (the moment), meta (the layout, the row block, its names)"""
    fs = []
    for p in paths:
        fs += sorted(glob.glob(os.path.join(p, "br_*.npz"))) if os.path.isdir(p) else [p]
    assert fs, "no dump (br_*.npz)"
    S, C, Y, M, G, meta = [], [], [], [], [], None
    for i, f in enumerate(fs):
        z = np.load(f, allow_pickle=False)
        m = json.loads(str(z["meta"]))
        if meta is None:
            meta = m
        assert m["names"] == meta["names"] and m["row0"] == meta["row0"] and m["layout"]["cand"] == meta["layout"]["cand"], "the dumps are of different layouts"
        S.append(np.asarray(z["S"], np.float32)), C.append(np.asarray(z["C"], np.float32)), Y.append(np.asarray(z["Y"], np.float32)), M.append(np.asarray(z["M"], np.float32))
        G.append(np.asarray(z["grp"], np.int64) + (i << 40))
    return np.concatenate(S), np.concatenate(C), np.concatenate(Y), np.concatenate(M), np.concatenate(G), meta


def group_cols(spec, meta):
    """a group -> the columns of [S | C] it blanks"""
    L = meta["layout"]
    sit, row0, names = int(L["sit"]), int(meta["row0"]), list(meta["names"])
    name, _, pre = spec.partition("=")
    if name in ("brain", "memory", "head") and not pre:
        a = {"brain": 0, "memory": int(L["bel"]), "head": int(L["bel"]) + int(L["mem"])}[name]
        return name, list(range(a, a + {"brain": int(L["bel"]), "memory": int(L["mem"]), "head": int(L["head"])}[name]))
    if name == "row" and not pre:
        return name, [sit + row0 + j for j in range(len(names))]
    if name == "weapon" and not pre:
        return name, [sit + j for j in range(row0 - int(L["weapons"]), row0)]
    pres = tuple(pre.split("|")) if pre else GROUPS.get(name)
    assert pres, "no group {!r}: one of {}, a block (row, weapon, brain, memory, head) or name=prefix|prefix".format(name, sorted(GROUPS))
    js = [j for j, n in enumerate(names) if any(n == p or (p.endswith("_") and n.startswith(p)) for p in pres)]
    assert js, "the group {!r} matches no number of the row ({})".format(spec, pres)
    return name, [sit + row0 + j for j in js]


def folds_of(grp, k, seed):
    u = np.unique(grp)
    rng = np.random.default_rng(seed)
    f = dict(zip(u.tolist(), rng.permutation(len(u)) % k))
    return np.array([f[g] for g in grp.tolist()], np.int64)


def fit_score(X, Y, M, tr, te, L, seed, epochs, hid, dev, lr=1e-3, mb=256):
    """the appraisals' own model and loss (sim/appraise.py) fitted on the rows tr, scored on te -> the skill by output [d] (nan: no label)"""
    import torch
    import torch.nn.functional as F
    import appraise as AP
    torch.manual_seed(seed)
    d = int(L["d"])
    mod = torch.nn.Sequential(torch.nn.Linear(X.shape[1], hid), torch.nn.ReLU(), torch.nn.Linear(hid, hid), torch.nn.ReLU(), torch.nn.Linear(hid, d)).to(dev)
    with torch.no_grad():
        mod[4].weight.zero_()
        mod[4].bias.zero_()
    opt = torch.optim.Adam(mod.parameters(), lr=lr)
    Xt, Yt, Mt = (torch.from_numpy(a_[tr]).to(dev) for a_ in (X, Y, M))
    reg, ch = list(AP.REG), list(AP.CH)
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        pm = torch.randperm(len(Xt), generator=g).to(dev)
        for b in range(0, len(Xt), mb):
            i_ = pm[b:b + mb]
            z = mod(Xt[i_])
            l_ = ((F.smooth_l1_loss(z[:, reg], Yt[i_][:, reg], reduction="none") * Mt[i_][:, reg]).sum()
                  + (F.binary_cross_entropy_with_logits(z[:, ch], Yt[i_][:, ch], reduction="none") * Mt[i_][:, ch]).sum()) / Mt[i_].sum().clamp(min=1.0)
            opt.zero_grad(set_to_none=True)
            l_.backward()
            torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
            opt.step()
    with torch.no_grad():
        z = mod(torch.from_numpy(X[te]).to(dev)).double().cpu().numpy()
    z[:, ch] = 1.0 / (1.0 + np.exp(-z[:, ch]))
    y, m = Y[te].astype(np.float64), M[te].astype(np.float64)
    ytr, mtr = Y[tr].astype(np.float64), M[tr].astype(np.float64)
    const = (ytr * mtr).sum(0) / np.maximum(mtr.sum(0), 1.0)                 # the best constant, from the training rows
    se, s0 = ((z - y) ** 2 * m).sum(0), ((const[None] - y) ** 2 * m).sum(0)
    return np.where((m.sum(0) > 0) & (s0 > 0), 1.0 - se / np.maximum(s0, 1e-12), np.nan)


def prune(S, C, Y, M, grp, meta, groups, folds=4, seeds=3, epochs=30, hid=256, dev="cpu", say=print, lr=1e-3, mb=256):
    L = meta["layout"]
    outs = list(L["outs"])
    X = np.concatenate([S, C], 1).astype(np.float32)
    mu_, sd_ = X.mean(0, keepdims=True), X.std(0, keepdims=True)
    X = (X - mu_) / np.where(sd_ > 1e-6, sd_, 1.0)                           # (the fit's own scaling; a blanked column is then 0: its mean)
    cols = [group_cols(g_, meta) for g_ in groups]
    base, base2, abl = [], [], {n_: [] for n_, _ in cols}
    for sd in range(seeds):
        fo = folds_of(grp, folds, 100 + sd)
        for k in range(folds):
            tr, te = np.nonzero(fo != k)[0], np.nonzero(fo == k)[0]
            b_ = fit_score(X, Y, M, tr, te, L, 1000 + 17 * sd + k, epochs, hid, dev, lr, mb)
            base.append(b_)
            base2.append(fit_score(X, Y, M, tr, te, L, 5000 + 17 * sd + k, epochs, hid, dev, lr, mb))      # (the same fold, another seed: the noise)
            for n_, cj in cols:
                Xa = X.copy()
                Xa[:, cj] = 0.0
                abl[n_].append(b_ - fit_score(Xa, Y, M, tr, te, L, 1000 + 17 * sd + k, epochs, hid, dev, lr, mb))
            say("  seed {} fold {}: skill with every input {}".format(sd, k, {o: round(float(v), 4) for o, v in zip(outs, b_) if np.isfinite(v)}))
    base, base2 = np.array(base), np.array(base2)
    n = len(base)
    noise = np.nanstd(base - base2, 0) / np.sqrt(2.0)                        # the spread of one fit's skill between seeds, by output
    res = dict(rows=int(len(X)), moments=int(len(np.unique(grp))), fits=n, outs=outs, skill={o: float(np.nanmean(base[:, j])) for j, o in enumerate(outs)},
               noise={o: float(noise[j]) for j, o in enumerate(outs)}, groups={})
    jp = outs.index(PRIMARY)
    for n_, cj in cols:
        g_ = np.array(abl[n_])
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mean, se = np.nanmean(g_, 0), np.nanstd(g_, 0) / np.sqrt(max(n, 1))
        ok = bool(np.isfinite(mean[jp]) and mean[jp] > 2.0 * se[jp] and mean[jp] > noise[jp])
        res["groups"][n_] = dict(columns=len(cj), gain={o: float(mean[j]) for j, o in enumerate(outs)}, se={o: float(se[j]) for j, o in enumerate(outs)}, passes=ok)
    return res


def show(res, say=print):
    say("{} branch rows of {} moments; {} fits. Skill with every input (held-out): {}".format(
        res["rows"], res["moments"], res["fits"], ", ".join("{} {:+.3f}".format(o, v) for o, v in res["skill"].items() if np.isfinite(v))))
    say("the noise (one fit's skill between seeds): " + ", ".join("{} {:.4f}".format(o, v) for o, v in res["noise"].items() if np.isfinite(v)))
    for n_, g in res["groups"].items():
        say("{:<12} {:>4} columns  gain on dV {:+.4f} (se {:.4f}, noise {:.4f})  {}   | {}".format(
            n_, g["columns"], g["gain"][PRIMARY], g["se"][PRIMARY], res["noise"][PRIMARY], "PASSES" if g["passes"] else "does not pass",
            ", ".join("{} {:+.4f}".format(o, v) for o, v in g["gain"].items() if o != PRIMARY and np.isfinite(v))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--groups", required=True)
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--hid", type=int, default=256)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--mb", type=int, default=256)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    S, C, Y, M, grp, meta = load(a.dumps)
    res = prune(S, C, Y, M, grp, meta, a.groups.split(","), a.folds, a.seeds, a.epochs, a.hid, a.device, lr=a.lr, mb=a.mb)
    show(res)
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()

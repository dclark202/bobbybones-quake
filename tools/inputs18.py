"""The input clean-up's converter (owner, 2026-11-11; docs/design/INPUTS_CLEANUP.md; sim/input_list.py): a network of the simulator's
full list (1,053 inputs, no strategy head yet) brought to the cleaned list 18, answering as before:

  cut      the columns that are dead by construction leave every first layer; a column that never changes contributes a fixed number,
           which is folded into the layer's bias (the hands' encoder, the brain's input layer) or into its token's mark (attention)
  routed   the hands' encoder reads the list's first n_hands columns, the brain its first n_brain; the 76 columns that were faded out
           of both (rule_fade and the brain's fade, both at 1) and the yellows' timers are in the list's tail, read by no first layer
           (their attention cells read a column of zeros, as the fade made them)
  resized  every remaining column's average and spread measured on a sample of real play, the first layers rescaled so that the sums
           are the same: z_old(x) = a * z_new(x) + b for every column (a column that was at the +-10 clip: exact if it has two values,
           left with its old statistics otherwise; a feature that several tokens share: one a for all its rows)

    python tools/inputs18.py convert <in.pt> <out.pt> --sample <obs.npy, 1,053 wide> [--opt <in opt.pt> <out opt.pt>] [--report out.json]
    python tools/inputs18.py same <full-list.pt> <list-18.pt> --sample <obs.npy> [--rows 3200] [--seats 8]
          both networks' whole numpy pass (tools: test_suite.Policy) on the SAME real rows, each through its own list, the same draws:
          the actions that differ and the largest difference of his memory
CPU only (CUDA_VISIBLE_DEVICES=-1)."""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
VERSION = 18
STRATEGY = (("clock and score", None), ("v02 game", None), ("v02 items", None), ("memory", "mega health: known to be taken"),
            ("memory", "mega health: how long ago"), ("memory", "red armor: known to be taken"), ("memory", "red armor: how long ago"),
            ("memory", "enemy has the mega health"), ("memory", "enemy has the red armor"))   # (change 7: out of the hands at the end of 1.8; the head has them)
EPS = 1e-8


def zclip(x, m, sd):
    return np.clip((x - m) / sd, -10.0, 10.0)


def plan(X, m, sd, cols):
    """for each of the simulator's columns in cols: its old effective function g(x) = c0 + slope * (x - x0) on the sample (the clipped
    normalizer), its kind, its target spread -> dict col -> dict(kind, slope, x0, c0, mu, sd_t, maxdev)"""
    P = {}
    for o in cols:
        x = np.asarray(X[:, o], np.float64)
        mu, s = float(x.mean()), float(x.std())
        maxdev = float(np.abs(x - mu).max())
        z = (x - m[o]) / sd[o]
        clipped = bool((np.abs(z) > 10.0).any())
        d = dict(mu=mu, sd_t=max(s, maxdev / 8.0, 1e-6), maxdev=maxdev)
        if maxdev < 1e-12:                                   # constant in the sample (kept: a rare event, or a part that is off)
            c = float(x[0])
            c0 = float(np.clip((c - m[o]) / sd[o], -10, 10))
            d.update(kind="const", slope=(1.0 / sd[o]) if sd[o] >= 1e-3 else 1.0, x0=c, c0=c0, mu=c, sd_t=1.0)
        elif not clipped:
            d.update(kind="plain", slope=1.0 / sd[o], x0=mu, c0=float((mu - m[o]) / sd[o]))
        else:
            v = np.unique(x)
            if len(v) == 2:
                c = np.clip((v - m[o]) / sd[o], -10, 10)
                d.update(kind="two", slope=float((c[1] - c[0]) / (v[1] - v[0])), x0=float(v[0]), c0=float(c[0]))
            else:
                d.update(kind="old", slope=1.0 / sd[o], x0=float(m[o]), c0=0.0)
        P[o] = d
    return P


def convert(a):
    import torch
    import input_list as IL
    L = IL.load(VERSION)
    src, nb, nh, n = [int(c) for c in L["src"]], int(L["n_brain"]), int(L["n_hands"]), int(L["n"])
    new_of = {o: j for j, o in enumerate(src)}
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd_ = ck["model"]
    assert int(sd_["enc.0.weight"].shape[1]) == L["full"] == int(ck["obs_dim"]), "the network has {} inputs, the list was made for {}".format(sd_["enc.0.weight"].shape[1], L["full"])
    assert ck.get("head2") is None and not any(k.startswith("head2.") for k in sd_), "convert before the strategy head is added"
    assert not ck.get("inputs"), "the network is of a list already"
    RF, BL = ck.get("rule_fade") or {}, ck.get("belief") or {}
    fade = sorted(int(c) for c in RF.get("cols", ()))
    assert fade and float(RF.get("g", 0.0)) == 1.0, "the rule fade is not at 1: its columns are still read by the hands"
    bfd = BL.get("fade") or {}
    if a.league and not bfd.get("cols"):                     # (a league file made before the brain's fade, v0.6.0's end: the trainer plays every league
        print("a league file without the brain's fade: its brain is given the list as the learner's (the trainer has played the league at the "
              "learner's fade, 1, since b1.1: these columns read zero there)")       # file in the learner's shape, at the learner's brain fade)
    else:
        assert sorted(int(c) for c in bfd.get("cols", ())) == fade and float(bfd.get("g", 0.0)) == 1.0, "the brain's fade is not the rule fade's at 1"
    nb0 = int(BL["obs_dim"])
    tail = src[nh:]
    assert set(fade) <= set(tail), "a faded column is not in the list's tail"
    timers = [o for o in tail if o not in set(fade)]
    assert float(sd_["enc.0.weight"][:, timers].abs().max()) == 0.0, "the hands have weights on the timers"
    cut = [o for o in range(L["full"]) if o not in new_of]
    X = np.load(a.sample, mmap_mode="r")
    assert X.shape[1] == L["full"], X.shape
    X = np.asarray(X, np.float64)
    m = np.asarray(ck["obs_mean"], np.float64)
    sd = np.sqrt(np.asarray(ck["obs_var"], np.float64) + EPS)
    for o in cut:
        assert float(X[:, o].max() - X[:, o].min()) == 0.0, "a cut column changes in the sample: {}".format(o)
    zc = {o: float(np.clip((X[0, o] - m[o]) / sd[o], -10, 10)) for o in cut}     # a cut column's fixed number after the normalizer
    live = src[:nh] + timers                                # (the faded tail keeps its old statistics: nothing reads it)
    P = plan(X, m, sd, live)
    # ---- a (z_old = a * z_new + b) per column; one a for every row of a feature that several tokens share
    alpha = {}
    lay = ck["attn"]
    shared = []
    for k in lay["kinds"]:
        if len(k["idx"]) > 1:
            for f in range(len(k["idx"][0])):
                cs = [int(r[f]) for r in k["idx"] if int(r[f]) >= 0 and int(r[f]) in new_of and new_of[int(r[f])] < nh]
                if len(cs) > 1:
                    shared.append((k["name"], f, cs))
    in_shared = {c for _, _, cs in shared for c in cs}
    for o in live:
        if o in in_shared:
            continue
        d = P[o]
        alpha[o] = 1.0 if d["kind"] in ("old", "const") else d["slope"] * d["sd_t"]
    n_old_feat = 0
    for name, f, cs in shared:
        kinds_ = [P[c]["kind"] for c in cs]
        if "old" in kinds_:
            af = 1.0
            n_old_feat += 1
        else:
            t = [P[c]["slope"] * P[c]["sd_t"] for c in cs if P[c]["kind"] in ("plain", "two")]
            af = float(np.median(t)) if t else 1.0
            af = max([af] + [P[c]["slope"] * P[c]["maxdev"] / 9.9 for c in cs if P[c]["kind"] in ("plain", "two")])
        for c in cs:
            alpha[c] = af
    m2, sd2, beta = m.copy(), sd.copy(), {}
    kinds_n = {"plain": 0, "two": 0, "old": 0, "const": 0}
    for o in live:
        d, a_ = P[o], alpha[o]
        kinds_n[d["kind"]] += 1
        if d["kind"] == "old" or (a_ == 1.0 and d["kind"] == "plain" and o in in_shared):   # left as it was
            beta[o] = 0.0
            continue
        if a_ <= 0.0 or d["slope"] <= 0.0:                   # (a column whose two values were both at the clip: no effect before, none after)
            alpha[o], beta[o], m2[o], sd2[o] = 0.0, d["c0"], d["mu"], d["sd_t"]
            continue
        sd2[o] = a_ / d["slope"]
        m2[o] = d["mu"]
        beta[o] = d["c0"] + d["slope"] * (d["mu"] - d["x0"])       # g(mu): z_new(mu) = 0
    A = np.array([alpha.get(o, 1.0) for o in range(L["full"])])
    Bt = np.array([beta.get(o, 0.0) for o in range(L["full"])])
    # ---- the old sums on the sample (for the check below)
    Zo = zclip(X, m, sd)
    Zh = Zo.copy()
    Zh[:, fade] = 0.0                                        # (the hands' and the brain's faded columns, both at g 1)
    We, be = sd_["enc.0.weight"].double().numpy(), sd_["enc.0.bias"].double().numpy()
    Wb, bb = sd_["belief.inp.weight"].double().numpy(), sd_["belief.inp.bias"].double().numpy()
    pre_e0, pre_b0 = Zh @ We.T + be, Zh[:, :nb0] @ Wb.T + bb    # (the brain at the fade 1: a league file without the entry as the trainer plays it)
    mark0 = sd_["attn.mark"].double().numpy()
    tok0, r0 = [], 0
    xp0 = np.concatenate([Zh, np.zeros((len(X), 1))], 1)
    for i, k in enumerate(lay["kinds"]):
        E = sd_["attn.emb.{}.weight".format(i)].double().numpy()
        idx = np.asarray(k["idx"], np.int64) % (L["full"] + 1)
        tok0.append(xp0[:, idx] @ E.T + mark0[r0:r0 + len(k["idx"])])
        r0 += len(k["idx"])
    # ---- the encoder and the brain's input layer
    hs, bs = src[:nh], src[:nb]
    assert all(o < nb0 for o in bs)
    We2 = We[:, hs] * A[hs]
    be2 = be + We[:, hs] @ Bt[hs] + sum(We[:, o] * zc[o] for o in cut)
    Wb2 = Wb[:, bs] * A[bs]
    cb = [o for o in cut if o < nb0]
    bb2 = bb + Wb[:, bs] @ Bt[bs] + sum(Wb[:, o] * zc[o] for o in cb)
    # ---- the attention tokens: the cells remapped; a cut cell's fixed number and every column's b into the token's mark
    mark2 = mark0.copy()
    kinds2, embs2, r0 = [], [], 0
    for i, k in enumerate(lay["kinds"]):
        E = sd_["attn.emb.{}.weight".format(i)].double().numpy().copy()
        idx2 = []
        fa = np.ones(E.shape[1])
        for r, row in enumerate(k["idx"]):
            new_row = []
            for f, o in enumerate(row):
                o = int(o)
                if o < 0:
                    new_row.append(-1)
                elif o in zc:
                    mark2[r0 + r] += E[:, f] * zc[o]
                    new_row.append(-1)
                elif new_of[o] >= nh:                        # the tail: a faded column read zeros; the timers' token is shut
                    new_row.append(-1)
                else:
                    mark2[r0 + r] += E[:, f] * Bt[o]
                    fa[f] = A[o]
                    new_row.append(new_of[o])
            idx2.append(new_row)
        for f in range(E.shape[1]):                          # (one a a feature: every row of it has the same by construction)
            rows_a = {A[int(row[f])] for row in k["idx"] if int(row[f]) >= 0 and int(row[f]) in new_of and new_of[int(row[f])] < nh}
            assert len(rows_a) <= 1, (k["name"], f, rows_a)
        E = E * fa
        keepf = [f for f in range(E.shape[1]) if any(row[f] >= 0 for row in idx2)]
        if not keepf:                                        # a token with no input left: its mark alone (one column of zeros)
            E, idx2 = np.zeros((E.shape[0], 1)), [[-1] for _ in idx2]
        else:
            E, idx2 = E[:, keepf], [[row[f] for f in keepf] for row in idx2]
        kk = dict(k, idx=idx2)
        kinds2.append(kk)
        embs2.append(E)
        r0 += len(k["idx"])
    # ---- the check on the sample: every first layer's sums as before
    Xn = X[:, src]
    Zn = zclip(Xn, m2[src], sd2[src])
    pre_e1, pre_b1 = Zn[:, :nh] @ We2.T + be2, Zn[:, :nb] @ Wb2.T + bb2
    xp1 = np.concatenate([Zn, np.zeros((len(X), 1))], 1)
    dt, r0 = 0.0, 0
    for i, k in enumerate(kinds2):
        idx = np.asarray(k["idx"], np.int64) % (n + 1)
        t1 = xp1[:, idx] @ embs2[i].T + mark2[r0:r0 + len(k["idx"])]
        dt = max(dt, float(np.abs(t1 - tok0[i]).max()))
        r0 += len(k["idx"])
    de, db = float(np.abs(pre_e1 - pre_e0).max()), float(np.abs(pre_b1 - pre_b0).max())
    newclip = float((np.abs((Xn[:, :nh] - m2[hs]) / sd2[hs]) > 10.0).mean())
    zs0, zs1 = Zo[:, hs].std(0), Zn[:, :nh].std(0)
    lv = zs0 > 1e-9
    print("the first layers' sums on {} rows of real play, the largest difference: the hands' encoder {:.2e}, the brain's input layer {:.2e}, "
          "the attention tokens {:.2e}".format(len(X), de, db, dt))
    print("columns: {} plain, {} two-valued at the old clip (exact), {} left with their old statistics (at the old clip, not two-valued), {} constant "
          "in the sample (kept); {} shared features left as they were; rows at the new clip {:.4%}".format(
              kinds_n["plain"], kinds_n["two"], kinds_n["old"], kinds_n["const"], n_old_feat, newclip))
    print("the size of the live columns after the normalizer (median, share under 0.3, share over 1.5): before {:.2f}, {:.1%}, {:.1%}; after {:.2f}, {:.1%}, {:.1%}".format(
        float(np.median(zs0[lv])), float((zs0[lv] < 0.3).mean()), float((zs0[lv] > 1.5).mean()),
        float(np.median(zs1[lv])), float((zs1[lv] < 0.3).mean()), float((zs1[lv] > 1.5).mean())))
    assert max(de, db, dt) < 1e-6, "a first layer's sums changed"
    # ---- written
    f32 = lambda v: torch.tensor(np.asarray(v), dtype=torch.float32)   # noqa: E731
    sd_["enc.0.weight"], sd_["enc.0.bias"] = f32(We2), f32(be2)
    sd_["belief.inp.weight"], sd_["belief.inp.bias"] = f32(Wb2), f32(bb2)
    sd_["attn.mark"] = f32(mark2)
    for i in range(len(kinds2)):
        sd_["attn.emb.{}.weight".format(i)] = f32(embs2[i])
    ck["attn"] = dict(lay, obs_dim=n, kinds=kinds2)
    ck["obs_mean"] = m2[src].astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.maximum(sd2[src] ** 2 - EPS, 0.0).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = n
    ck["belief"] = {k_: v_ for k_, v_ in dict(BL, obs_dim=nb).items() if k_ != "fade"}
    sc = [j for j, (g_, n_) in enumerate(L["names"]) if "believed" not in n_ and any(g_ == sg and (sn is None or sn == n_) for sg, sn in STRATEGY)]   # (as the head's own: nothing made from the old rule belief)
    assert sc and max(sc) < nh, "a strategy input is not among the hands' columns"
    ck["rule_fade"] = dict(RF, cols=[new_of[o] for o in fade], more=dict(name="strategy", cols=sc, names=[list(L["names"][j]) for j in sc], g=0.0))
    if ck.get("btoken") is not None:
        ck["btoken"] = dict(ck["btoken"], seen_col=new_of[int(ck["btoken"]["seen_col"])])
    ck["inputs"] = dict(list=VERSION, n=n, n_brain=nb, n_hands=nh, full=L["full"])
    ck["input_names"] = [list(x) for x in L["names"]]
    torch.save(ck, a.out)
    print("wrote {}: list {} ({} inputs; the brain the first {}, the hands the first {}, the tail {}); {} columns cut and folded".format(
        a.out, VERSION, n, nb, nh, n - nh, len(cut)))
    rep = dict(columns=[dict(col=o, new=new_of[o], name=L["names"][new_of[o]], kind=P[o]["kind"], a=float(A[o]), sd_old=float(sd[o]), sd_new=float(sd2[o]),
                             m_old=float(m[o]), m_new=float(m2[o])) for o in live],
               diff=dict(enc=de, brain=db, tokens=dt), kinds=kinds_n)
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=0)
    if a.opt:                                                # ---- the optimizer's kept moments: the same columns, scaled with the weights
        os_ = torch.load(a.opt[0], weights_only=False, map_location="cpu")
        st = os_["state"]
        done = []

        def scale(i_, cols_, al_):
            for k2, p in (("exp_avg", 1.0), ("exp_avg_sq", 2.0)):
                v = st[i_][k2].double().numpy()
                s_ = np.where(al_ > 0, al_, 1.0) ** p
                st[i_][k2] = torch.tensor(v[:, cols_] / s_, dtype=st[i_][k2].dtype)

        by_shape = {}
        for i_, s_ in st.items():
            by_shape.setdefault(tuple(s_["exp_avg"].shape), []).append(i_)
        old_w = int(max(w_ for (h_, w_) in [sh for sh in by_shape if len(sh) == 2 and sh[0] == 256] if w_ > 512))
        ie = [i_ for i_ in by_shape.get((256, old_w), [])]
        ib = [i_ for i_ in by_shape.get((256, nb0), [])]
        assert len(ie) == 1 and len(ib) == 1 and all(o < old_w for o in hs), (ie, ib, old_w)
        scale(ie[0], hs, A[hs])
        scale(ib[0], bs, A[bs])
        done += ["enc.0.weight {} -> {}".format((256, old_w), (256, nh)), "belief.inp.weight {} -> {}".format((256, nb0), (256, nb))]
        im = [i_ for sh, v_ in by_shape.items() if len(sh) == 2 and sh[1] == lay["D"] and sh[0] < 100 and sh[0] != lay["D"] for i_ in v_]
        assert len(im) == 1, im                              # the tokens' marks: the first layers follow it, a kind each, in order
        for j in range(len(lay["kinds"])):
            i_ = im[0] + 1 + j
            if i_ not in st or tuple(st[i_]["exp_avg"].shape) != (lay["D"], len(lay["kinds"][j]["idx"][0])):
                break                                        # (a kind added after the optimizer was saved: the trainer starts it fresh)
            k, k2 = lay["kinds"][j], kinds2[j]
            keepf = [f for f in range(len(k["idx"][0])) if any(int(row[f]) >= 0 and int(row[f]) in new_of and new_of[int(row[f])] < nh for row in k["idx"])]
            if not keepf:
                for kk_ in ("exp_avg", "exp_avg_sq"):
                    st[i_][kk_] = torch.zeros((lay["D"], 1), dtype=st[i_][kk_].dtype)
            else:
                fa = np.array([[A[int(row[f])] for row in k["idx"] if int(row[f]) >= 0 and int(row[f]) in new_of and new_of[int(row[f])] < nh][0] for f in keepf])
                scale(i_, keepf, fa)
            assert tuple(st[i_]["exp_avg"].shape) == tuple(embs2[j].shape), (j, st[i_]["exp_avg"].shape, embs2[j].shape)
            done.append("attn.emb.{}".format(j))
        torch.save(os_, a.opt[1])
        print("the optimizer's moments converted {} -> {}: {}".format(a.opt[0], a.opt[1], "; ".join(done[:2]) + "; {} token kinds' first layers".format(len(done) - 2)))


def same(a):
    """twice: as the checks play (the brain reads its inputs rounded to half precision, as the trainer stores them: the two networks'
    inputs are on different grids there, so their brains differ by the rounding and a few actions with them), and with that rounding
    off (the networks' own sums: 0 actions may differ)"""
    r1 = same1(a, True)
    r2 = same1(a, False)
    # (the proof that the sums are the same is convert's own check, in double precision: 1e-13. Here both networks run in single
    #  precision with differently scaled weights, so their memories differ by rounding (about 3e-4) and a draw that sits on an edge can
    #  fall the other way: at most 5 of the 44,800 choices are let through)
    print("ALL PASSED" if r2 <= 5 else "FAILED: {} actions differ with the brain's rounding off".format(r2))
    return 0 if r2 <= 5 else 1


def same1(a, half):
    import btoken as btoken_
    import test_suite as T
    import input_list as IL
    cls = [c for c in vars(btoken_).values() if isinstance(c, type) and hasattr(c, "frame") and hasattr(c, "readouts")][0]
    if not hasattr(cls, "_init0"):
        cls._init0 = cls.__init__
    cls.__init__ = (lambda self, B, n, half=True: cls._init0(self, B, n, True)) if half else (lambda self, B, n, half=True: cls._init0(self, B, n, False))
    L = IL.load(VERSION)
    src = np.asarray(L["src"], np.int64)
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == L["full"] and len(pb.mean) == L["n"], (len(pa.mean), len(pb.mean))
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
            p.h2_live = True
    assert pa.brain_on and pb.brain_on
    X = np.load(a.sample, mmap_mode="r")
    rng = np.random.default_rng(3)
    B, F = a.seats, a.rows // a.seats
    rows = rng.permutation(len(X))[:B * F].reshape(F, B)
    ha, hb = pa.zeros(B), pb.zeros(B)
    dh, dact, n = 0.0, 0, 0
    W0 = pa.W if pa.h2 is None else pa.h2_at
    W1 = pb.W if pb.h2 is None else pb.h2_at
    pose = np.zeros((B, 4), np.float32)
    zmap = np.full(B, 0, np.int64)
    for t in range(F):
        raw = np.asarray(X[np.sort(rows[t])], np.float32)
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        oa, ha = pa.act(raw, ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw[:, src], hb, pose=pose, zmap=zmap, **kw)
        dh = max(dh, float(np.abs(ha[:, :min(W0, pa.H)] - hb[:, :min(W1, pb.H)]).max()))
        dact += int((oa != ob).sum())
        n += oa.size
        if t % 97 == 96:
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same ({}): {} real rows x {} seats, each network through its own list: largest |h a - h b| = {:.3g}; actions that differ: {} of {}".format(
        "as played: the brain's inputs at half precision" if half else "the brain's rounding off", F, B, dh, dact, n))
    return dact


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("convert")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--sample", required=True)
    p.add_argument("--opt", nargs=2)
    p.add_argument("--report", default="")
    p.add_argument("--league", action="store_true", help="a league file (an anchor): its brain may lack the fade entry")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--sample", required=True)
    p.add_argument("--rows", type=int, default=3200)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    sys.exit(int((convert(a) if a.cmd == "convert" else same(a)) or 0))


if __name__ == "__main__":
    main()

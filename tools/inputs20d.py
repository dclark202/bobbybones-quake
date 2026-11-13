"""2.0d (owner, 2026-11-13; docs/runs/2.0/2.0d/CARD.md): 1.7a's update 90 brought to the input list 20d, answering as before.

1.7a's networks read the simulator's first 990 columns, and have the strategy head (its own input columns), the keep choice, the
weapon part and the combat order's parts (never asked at update 90). List 20d (sim/input_list.py extend: list 18, the order's ten
columns taken back (owner, 11-13: "keep them"), the dodge group "b20d dodge" added) is reached in one step:

  cut      as tools/inputs18.py: a column the list does not have leaves every first layer; a cut column that never changes
           contributes a fixed number, folded into the layer's bias (the hands' encoder, the brain's input layer, the head's input
           layer, the weapon part's) or its token's mark; the 76 rule-made columns read zero in the hands and the brain (both fades at 1)
  resized  every kept column's average and spread measured on a sample of 1.7a's own play (2.0d's settings), the first layers rescaled
           so that the sums are the same: z_old(x) = a * z_new(x) + b. The head's columns and the weapon part's are the same columns: the
           same a and b
  added    the dodge group's 7 columns at the hands' end at zero weights, their statistics measured on the same sample; one attention token
           "dodge" after every older kind, its first layer at zero and its gate shut (left out altogether: sim/attn.py DROP_SHUT; the
           trainer sets it from live DODGE_G); the yellow armors' timers in the tail (read by no first layer; 1.7a had none)
  head     left as update 90 has it: its 81 columns less the two cut ("exists", always 1 on the ten maps), every weight as it was
           (rescaled with its columns), the keep choice, the weapon part, the combat order's parts

    python tools/inputs20d.py convert <1.7a.pt> <out.pt> --sample <obs.npy, the simulator's full rows> [--opt <in opt.pt> <out opt.pt>]
           [--report out.json] [--league]
        --opt: the optimizer's moments brought to the cut and rescaled columns (the dodge columns, the new token's first layer and its
        mark row are left for the trainer's --opt-small-items: end-appended columns, a last kind, a mark before the summary's)
    python tools/inputs20d.py same <1.7a.pt> <20d.pt> --sample <obs.npy> [--rows 3200] [--seats 8]
        both networks' whole numpy pass (sim/test_suite.Policy) on the SAME real rows, each through its own columns, the new columns
        random: the actions that differ (twice: the brain's half-precision rounding on, as played, and off)
CPU only (CUDA_VISIBLE_DEVICES=-1)."""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import inputs18 as I18  # noqa: E402  (plan, zclip, STRATEGY: the same rules)

VERSION, GROUP, TOKEN, OLD_W = "20d", "b20d dodge", "dodge", 990
EPS = I18.EPS
TOKEN_SEED = 2004


def _f32(v):
    import torch
    return torch.tensor(np.asarray(v), dtype=torch.float32)


def convert(a):
    import torch
    import attn as A_
    import head2 as head2_
    import input_list as IL
    L = IL.load(VERSION)
    src, nb, nh, n = [int(c) for c in L["src"]], int(L["n_brain"]), int(L["n_hands"]), int(L["n"])
    new_of = {o: j for j, o in enumerate(src)}
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd_ = ck["model"]
    W0 = int(ck["obs_dim"])
    assert W0 == OLD_W == int(sd_["enc.0.weight"].shape[1]) and not ck.get("inputs"), "not a network of the simulator's first {} columns".format(OLD_W)
    names_full = [(r["group"], r["input"]) for r in IL.full_rows()]
    # ---- the list's columns the network does not have: the dodge group at the hands' end, the timers in the tail
    newc = [j for j, o in enumerate(src) if o >= W0]
    dg = [j for j in newc if L["names"][j][0] == GROUP]
    K = len(dg)
    assert K == 7 and dg == list(range(nh - K, nh)), "the dodge columns are not the hands' last"
    tail_new = [j for j in newc if j >= nh]
    assert sorted(dg + tail_new) == newc and all(L["names"][j][0] == "b17b timers" for j in tail_new)
    nh0 = nh - K                                             # the hands' columns the network has
    RF, BL = ck.get("rule_fade") or {}, ck.get("belief") or {}
    fade = sorted(int(c) for c in RF.get("cols", ()))
    assert fade and float(RF.get("g", 0.0)) == 1.0, "the rule fade is not at 1"
    bfd = BL.get("fade") or {}
    if a.league and not bfd.get("cols"):
        print("a league file without the brain's fade: its brain is given the list as the learner's")
    else:
        assert sorted(int(c) for c in bfd.get("cols", ())) == fade and float(bfd.get("g", 0.0)) == 1.0, "the brain's fade is not the rule fade's at 1"
    nb0 = int(BL["obs_dim"])
    fs = set(fade)
    assert all(new_of[o] >= nh for o in fade if o in new_of), "a faded column is among the columns a first layer reads"
    cut = [o for o in range(W0) if o not in new_of]
    H2L = ck.get("head2")                                    # (a league file may have no head, or a head without the weapon part)
    oc = [int(c) for c in H2L["obs_cols"]] if H2L is not None else []
    wc = [int(c) for c in (H2L or {}).get("wobs_cols") or []]
    assert not (set(oc) | set(wc)) & fs, "the head reads a faded column"
    assert all(o in cut or new_of[o] < nh0 for o in oc + wc), "the head reads a column outside the hands' part"
    # ---- the sample
    X = np.load(a.sample, mmap_mode="r")
    assert X.shape[1] >= max(src) + 1, X.shape
    XD = np.asarray(X[:, [src[j] for j in dg + tail_new]], np.float64)
    X = np.asarray(X[:, :W0], np.float64)
    m = np.asarray(ck["obs_mean"], np.float64)
    sd = np.sqrt(np.asarray(ck["obs_var"], np.float64) + EPS)
    for o in cut:
        assert o in fs or float(X[:, o].max() - X[:, o].min()) == 0.0, "a cut column changes in the sample: {} {}".format(o, names_full[o])
    zc = {o: 0.0 if o in fs else float(np.clip((X[0, o] - m[o]) / sd[o], -10, 10)) for o in cut}
    live = src[:nh0]
    P = I18.plan(X, m, sd, live)
    # ---- a (z_old = a * z_new + b) per column; one a for every row of a feature that several tokens share (inputs18's rule)
    alpha = {}
    lay = ck["attn"]
    shared = []
    for k in lay["kinds"]:
        if len(k["idx"]) > 1:
            for f in range(len(k["idx"][0])):
                cs = [int(r[f]) for r in k["idx"] if int(r[f]) >= 0 and int(r[f]) in new_of and new_of[int(r[f])] < nh0]
                if len(cs) > 1:
                    shared.append((k["name"], f, cs))
    in_shared = {c for _, _, cs in shared for c in cs}
    for o in live:
        if o not in in_shared:
            d = P[o]
            alpha[o] = 1.0 if d["kind"] in ("old", "const") else d["slope"] * d["sd_t"]
    for name, f, cs in shared:
        kinds_ = [P[c]["kind"] for c in cs]
        if "old" in kinds_:
            af = 1.0
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
        if d["kind"] == "old" or (a_ == 1.0 and d["kind"] == "plain" and o in in_shared):
            beta[o] = 0.0
            continue
        if a_ <= 0.0 or d["slope"] <= 0.0:
            alpha[o], beta[o], m2[o], sd2[o] = 0.0, d["c0"], d["mu"], d["sd_t"]
            continue
        sd2[o] = a_ / d["slope"]
        m2[o] = d["mu"]
        beta[o] = d["c0"] + d["slope"] * (d["mu"] - d["x0"])
    Aa = np.array([alpha.get(o, 1.0) for o in range(W0)])
    Bt = np.array([beta.get(o, 0.0) for o in range(W0)])
    # ---- the old sums on the sample
    Zo = I18.zclip(X, m, sd)
    Zh = Zo.copy()
    Zh[:, fade] = 0.0
    We, be = sd_["enc.0.weight"].double().numpy(), sd_["enc.0.bias"].double().numpy()
    Wb, bb = sd_["belief.inp.weight"].double().numpy(), sd_["belief.inp.bias"].double().numpy()
    pre_e0, pre_b0 = Zh @ We.T + be, Zh[:, :nb0] @ Wb.T + bb
    if H2L is not None:
        o0, o1 = head2_._offs(H2L)["obs"]
        assert o1 - o0 == len(oc)
        Wi, bi = sd_["head2.inp.weight"].double().numpy(), sd_["head2.inp.bias"].double().numpy()
    else:
        o0, o1, Wi, bi = 0, 0, np.zeros((1, 0)), np.zeros(1)
    if wc:
        Ww, bw = sd_["head2.winp.weight"].double().numpy(), sd_["head2.winp.bias"].double().numpy()
        assert Ww.shape[1] == len(wc)
    else:
        Ww, bw = np.zeros((1, 0)), np.zeros(1)
    pre_h0 = Zo[:, oc] @ Wi[:, o0:o1].T + bi                 # (the head's obs part: its other parts are not inputs)
    pre_w0 = Zo[:, wc] @ Ww.T + bw
    mark0 = sd_["attn.mark"].double().numpy()
    tok0, r0 = [], 0
    xp0 = np.concatenate([Zh, np.zeros((len(X), 1))], 1)
    for i, k in enumerate(lay["kinds"]):
        E = sd_["attn.emb.{}.weight".format(i)].double().numpy()
        idx = np.asarray(k["idx"], np.int64) % (W0 + 1)
        tok0.append(xp0[:, idx] @ E.T + mark0[r0:r0 + len(k["idx"])])
        r0 += len(k["idx"])
    # ---- the encoder (the dodge columns at zero) and the brain's input layer
    hs, bs = src[:nh0], src[:nb]
    assert all(o < nb0 for o in bs)
    We2 = np.zeros((We.shape[0], nh))
    We2[:, :nh0] = We[:, hs] * Aa[hs]
    be2 = be + We[:, hs] @ Bt[hs] + sum(We[:, o] * zc[o] for o in cut)
    Wb2 = Wb[:, bs] * Aa[bs]
    cb = [o for o in cut if o < nb0]
    bb2 = bb + Wb[:, bs] @ Bt[bs] + sum(Wb[:, o] * zc[o] for o in cb)
    # ---- the head's input layer (its obs part) and the weapon part's
    keep_h = [k_ for k_, o in enumerate(oc) if o in new_of]
    Wio = Wi[:, o0:o1]
    bi2 = bi + sum(Wio[:, k_] * zc[o] for k_, o in enumerate(oc) if o not in new_of) + sum(Wio[:, k_] * Bt[oc[k_]] for k_ in keep_h)
    Wio2 = np.stack([Wio[:, k_] * Aa[oc[k_]] for k_ in keep_h], 1) if keep_h else np.zeros((Wi.shape[0], 0))
    Wi2 = np.concatenate([Wi[:, :o0], Wio2, Wi[:, o1:]], 1)
    Ww2 = Ww * Aa[wc]
    bw2 = bw + Ww @ Bt[wc]
    oc2, wc2 = [new_of[oc[k_]] for k_ in keep_h], [new_of[o] for o in wc]
    # ---- the attention tokens (inputs18's remap), then the dodge token
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
                elif new_of[o] >= nh:
                    new_row.append(-1)
                else:
                    mark2[r0 + r] += E[:, f] * Bt[o]
                    fa[f] = Aa[o]
                    new_row.append(new_of[o])
            idx2.append(new_row)
        for f in range(E.shape[1]):
            rows_a = {Aa[int(row[f])] for row in k["idx"] if int(row[f]) >= 0 and int(row[f]) in new_of and new_of[int(row[f])] < nh}
            assert len(rows_a) <= 1, (k["name"], f, rows_a)
        E = E * fa
        keepf = [f for f in range(E.shape[1]) if any(row[f] >= 0 for row in idx2)]
        if not keepf:
            E, idx2 = np.zeros((E.shape[0], 1)), [[-1] for _ in idx2]
        else:
            E, idx2 = E[:, keepf], [[row[f] for f in keepf] for row in idx2]
        kinds2.append(dict(k, idx=idx2))
        embs2.append(E)
        r0 += len(k["idx"])
    # ---- the check on the sample: every first layer's sums as before (the new columns random: their weights are zero)
    Xn = np.zeros((len(X), n))
    for j, o in enumerate(src):
        if o < W0:
            Xn[:, j] = X[:, o]
    rng = np.random.default_rng(5)
    Xn[:, newc] = rng.uniform(-2, 2, (len(X), len(newc)))
    mn, sn = np.zeros(n), np.ones(n)
    for j, o in enumerate(src):
        if o < W0:
            mn[j], sn[j] = m2[o], sd2[o]
    Zn = I18.zclip(Xn, mn, sn)
    pre_e1, pre_b1 = Zn[:, :nh] @ We2.T + be2, Zn[:, :nb] @ Wb2.T + bb2
    pre_h1, pre_w1 = Zn[:, oc2] @ Wio2.T + bi2, Zn[:, wc2] @ Ww2.T + bw2
    xp1 = np.concatenate([Zn, np.zeros((len(X), 1))], 1)
    dt, r0 = 0.0, 0
    for i, k in enumerate(kinds2):
        idx = np.asarray(k["idx"], np.int64) % (n + 1)
        t1 = xp1[:, idx] @ embs2[i].T + mark2[r0:r0 + len(k["idx"])]
        dt = max(dt, float(np.abs(t1 - tok0[i]).max()))
        r0 += len(k["idx"])
    de, db = float(np.abs(pre_e1 - pre_e0).max()), float(np.abs(pre_b1 - pre_b0).max())
    dh, dw = float(np.abs(pre_h1 - pre_h0).max()), float(np.abs(pre_w1 - pre_w0).max())
    newclip = float((np.abs((Xn[:, :nh0] - mn[:nh0]) / sn[:nh0]) > 10.0).mean())
    zs0, zs1 = Zo[:, hs].std(0), Zn[:, :nh0].std(0)
    lv = zs0 > 1e-9
    print("the first layers' sums on {} rows of real play, the largest difference: the hands' encoder {:.2e}, the brain's input layer {:.2e}, "
          "the head's {:.2e}, the weapon part's {:.2e}, the attention tokens {:.2e}".format(len(X), de, db, dh, dw, dt))
    print("columns: {} plain, {} two-valued at the old clip (exact), {} left with their old statistics, {} constant in the sample (kept); "
          "rows at the new clip {:.4%}".format(kinds_n["plain"], kinds_n["two"], kinds_n["old"], kinds_n["const"], newclip))
    print("the size of the hands' columns after the normalizer (median, share under 0.3, share over 1.5): before {:.2f}, {:.1%}, {:.1%}; after {:.2f}, {:.1%}, {:.1%}".format(
        float(np.median(zs0[lv])), float((zs0[lv] < 0.3).mean()), float((zs0[lv] > 1.5).mean()),
        float(np.median(zs1[lv])), float((zs1[lv] < 0.3).mean()), float((zs1[lv] > 1.5).mean())))
    assert max(de, db, dh, dw, dt) < 1e-6, "a first layer's sums changed"
    # ---- the new columns' statistics: measured on the same sample
    dm, dv = XD.mean(0), XD.var(0)
    dv = np.where(dv > 1e-6, dv, 1.0)
    mean_n, var_n = mn.copy(), sn ** 2 - EPS
    for q, j in enumerate(dg + tail_new):
        mean_n[j], var_n[j] = dm[q], dv[q]
    print("the dodge columns (mean, spread) measured on the sample: " + "; ".join(
        "{} {:.4f} {:.3f}".format(L["names"][j][1].replace("dodge: ", ""), dm[q], dv[q] ** 0.5) for q, j in enumerate(dg)))
    # ---- written
    sd_["enc.0.weight"], sd_["enc.0.bias"] = _f32(We2), _f32(be2)
    sd_["belief.inp.weight"], sd_["belief.inp.bias"] = _f32(Wb2), _f32(bb2)
    if H2L is not None:
        sd_["head2.inp.weight"], sd_["head2.inp.bias"] = _f32(Wi2), _f32(bi2)
    if wc:
        sd_["head2.winp.weight"], sd_["head2.winp.bias"] = _f32(Ww2), _f32(bw2)
    D = int(lay["D"])
    g = torch.Generator().manual_seed(TOKEN_SEED)
    mrow = (torch.randn((1, D), generator=g) * 0.1).double().numpy()
    mark3 = np.concatenate([mark2[:-1], mrow, mark2[-1:]], 0)                    # (the summary token's mark stays the last)
    gate = sd_["attn.gate"]
    assert int(lay["read"][0]) == int(lay["tokens"]) - 1 and len(gate) == int(lay["tokens"])
    sd_["attn.mark"] = _f32(mark3)
    sd_["attn.gate"] = torch.cat([gate[:-1], torch.full((1,), A_.GATE_SHUT, dtype=gate.dtype), gate[-1:]], 0)
    for i in range(len(kinds2)):
        sd_["attn.emb.{}.weight".format(i)] = _f32(embs2[i])
    kinds2.append(dict(name=TOKEN, idx=[dg]))
    sd_["attn.emb.{}.weight".format(len(kinds2) - 1)] = torch.zeros((D, K), dtype=torch.float32)
    nt = int(lay["tokens"]) + 1
    ck["attn"] = dict(lay, obs_dim=n, kinds=kinds2, tokens=nt, read=[nt - 1] + [int(x) for x in lay["read"][1:]])
    ck["obs_mean"] = mean_n.astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.maximum(var_n, 0.0).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = n
    ck["belief"] = {k_: v_ for k_, v_ in dict(BL, obs_dim=nb).items() if k_ != "fade"}
    if H2L is not None:
        ck["head2"] = dict(H2L, obs_cols=oc2, widths=dict(H2L["widths"], obs=len(oc2)), **({"wobs_cols": wc2} if wc else {}))
    sc = [j for j, (g_, n_) in enumerate(L["names"]) if "believed" not in n_ and any(g_ == sg and (sn_ is None or sn_ == n_) for sg, sn_ in I18.STRATEGY)]
    assert sc and max(sc) < nh0
    kept = [o for o in fade if o in new_of]
    ck["rule_fade"] = dict(RF, cols=[new_of[o] for o in kept], names=[list(L["names"][new_of[o]]) for o in kept], n=len(kept),
                           more=dict(name="strategy", cols=sc, names=[list(L["names"][j]) for j in sc], g=0.0))
    if ck.get("btoken") is not None:
        ck["btoken"] = dict(ck["btoken"], seen_col=new_of[int(ck["btoken"]["seen_col"])])
    for key in ("track", "track_z", "ahead", "control", "fightodds", "spaceread", "passodds", "aux_heads", "legs_unify"):
        d = ck.get(key)
        if isinstance(d, dict):
            for k2, v2 in d.items():
                nums_ = isinstance(v2, (int, np.integer)) or (isinstance(v2, (list, tuple, np.ndarray)) and len(v2) > 0
                                                               and all(isinstance(x_, (int, np.integer)) for x_ in np.asarray(v2, object).ravel()))
                if (k2.endswith("cols") or k2.endswith("_col")) and nums_:
                    raise SystemExit("{}['{}'] holds column numbers this converter does not move: add it".format(key, k2))
    ck["inputs"] = dict(list=VERSION, n=n, n_brain=nb, n_hands=nh, full=int(L["full"]), dodge=[dg[0], dg[-1] + 1])
    ck["input_names"] = [list(x) for x in L["names"]]
    ck["env_module"] = "duel_env_ffa" + VERSION
    ck["env_vars"] = dict(ck.get("env_vars") or {}, DODGE_IN="1", DODGE_G="0")    # (a check of this file plays it as update 0 is played)
    torch.save(ck, a.out)
    print("wrote {}: list {} ({} inputs; the brain the first {}, the hands the first {}, the tail {}); {} columns cut and folded; the head's "
          "{} columns ({} cut), the weapon part's {}; the dodge columns at zero, the token '{}' last, shut".format(
              a.out, VERSION, n, nb, nh, n - nh, len(cut), len(oc2), len(oc) - len(oc2), len(wc2), TOKEN))
    if a.report:
        rep = dict(columns=[dict(col=o, new=new_of[o], name=L["names"][new_of[o]], kind=P[o]["kind"], a=float(Aa[o]), sd_old=float(sd[o]),
                                 sd_new=float(sd2[o]), m_old=float(m[o]), m_new=float(m2[o])) for o in live],
                   new=[dict(new=j, name=L["names"][j], mean=float(dm[q]), sd=float(dv[q] ** 0.5)) for q, j in enumerate(dg + tail_new)],
                   diff=dict(enc=de, brain=db, head=dh, wobs=dw, tokens=dt), kinds=kinds_n, rows=len(X), sample=os.path.abspath(a.sample))
        json.dump(rep, open(a.report, "w"), indent=0)
    if a.opt:
        opt_convert(a, lay, kinds2[:-1], hs, bs, Aa, nb0, keep_h, oc, Wi.shape, o0, o1, wc, new_of, nh0)


def opt_convert(a, lay, kinds2, hs, bs, Aa, nb0, keep_h, oc, wi_shape, o0, o1, wc, new_of, nh0):
    """the optimizer's moments on the cut and rescaled columns (Adam: exp_avg / a, exp_avg_sq / a^2). Found by shape: the encoder, the
    brain's input layer, the head's and the weapon part's input layers each unique; the tokens' first layers as the one run of the
    kinds' shapes in order. The new columns, token and mark row: the trainer's --opt-small-items"""
    import torch
    os_ = torch.load(a.opt[0], weights_only=False, map_location="cpu")
    st = os_["state"]

    def scale(i_, cols_, al_):
        for k2, p in (("exp_avg", 1.0), ("exp_avg_sq", 2.0)):
            v = st[i_][k2].double().numpy()
            s_ = np.where(al_ > 0, al_, 1.0) ** p
            st[i_][k2] = torch.tensor(v[:, cols_] / s_, dtype=st[i_][k2].dtype)

    def one(shape):
        f = [i_ for i_, s_ in st.items() if tuple(s_["exp_avg"].shape) == tuple(shape)]
        assert len(f) == 1, ("not one moment of shape", shape, f)
        return f[0]
    ie, ib = one((256, OLD_W)), one((256, nb0))
    scale(ie, hs, Aa[hs])
    scale(ib, bs, Aa[bs])
    ih = one(wi_shape) if oc else None
    for k2, p in (("exp_avg", 1.0), ("exp_avg_sq", 2.0)) if oc else ():   # (the head: its obs part's kept columns scaled, the cut ones out)
        v = st[ih][k2].double().numpy()
        vo = v[:, o0:o1]
        vo2 = np.stack([vo[:, k_] / (Aa[oc[k_]] if Aa[oc[k_]] > 0 else 1.0) ** p for k_ in keep_h], 1)
        st[ih][k2] = torch.tensor(np.concatenate([v[:, :o0], vo2, v[:, o1:]], 1), dtype=st[ih][k2].dtype)
    if wc:
        scale(one((wi_shape[0], len(wc))), list(range(len(wc))), Aa[wc])
    D = int(lay["D"])
    shapes = [(D, len(k["idx"][0])) for k in lay["kinds"]]
    keys = sorted(st)
    run = [s for s in range(len(keys) - len(shapes) + 1)
           if all(keys[s + j] == keys[s] + j and tuple(st[keys[s + j]]["exp_avg"].shape) == shapes[j] for j in range(len(shapes)))]
    assert len(run) == 1, ("the tokens' first layers: not one run of their shapes", run)
    for j, k in enumerate(lay["kinds"]):
        i_ = keys[run[0] + j]
        ok_ = lambda o: o >= 0 and new_of.get(o, 10 ** 9) < nh0     # noqa: E731
        kf = [f for f in range(len(k["idx"][0])) if any(ok_(int(row[f])) for row in k["idx"])]
        if not kf:
            for kk_ in ("exp_avg", "exp_avg_sq"):
                st[i_][kk_] = torch.zeros((D, 1), dtype=st[i_][kk_].dtype)
        else:
            fa = np.array([[Aa[int(row[f])] for row in k["idx"] if ok_(int(row[f]))][0] for f in kf])
            scale(i_, kf, fa)
        assert tuple(st[i_]["exp_avg"].shape) == (D, len(kinds2[j]["idx"][0])), (k["name"], st[i_]["exp_avg"].shape)
    torch.save(os_, a.opt[1])
    print("the optimizer's moments converted {} -> {}: enc.0.weight, belief.inp.weight, head2.inp.weight, head2.winp.weight, {} token kinds' "
          "first layers (the dodge columns, token and mark row: --opt-small-items)".format(a.opt[0], a.opt[1], len(shapes)))


def same(a):
    r1 = same1(a, True)
    r2 = same1(a, False)
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
    newc = np.where(src >= OLD_W)[0]
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == OLD_W and len(pb.mean) == L["n"], (len(pa.mean), len(pb.mean))
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
            p.h2_live = True
    assert pa.brain_on and pb.brain_on
    X = np.load(a.sample, mmap_mode="r")
    assert X.shape[1] > int(src.max()), X.shape
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
        rb = raw[:, src].copy()
        rb[:, newc] = rng.uniform(-2, 2, (B, len(newc))).astype(np.float32)
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        oa, ha = pa.act(raw[:, :OLD_W], ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(rb, hb, pose=pose, zmap=zmap, **kw)
        dh = max(dh, float(np.abs(ha[:, :min(W0, pa.H)] - hb[:, :min(W1, pb.H)]).max()))
        dact += int((oa != ob).sum())
        n += oa.size
        if t % 97 == 96:
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same ({}): {} real rows x {} seats, each network through its own columns, the new ones random: largest |h a - h b| = {:.3g}; "
          "actions that differ: {} of {}".format("as played: the brain's inputs at half precision" if half else "the brain's rounding off", F, B, dh, dact, n))
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

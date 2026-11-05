"""1.7: give a network with the strategy head and 1.7's keep choice (tools/keep_init.py add) every other part of the combat order
(docs/runs/1.7/BUILD.md), all at exactly zero effect: it answers as before.

  python tools/order_init.py add <in policy.pt> <out policy.pt> [--fit <tools/order_pros.py's fit.json> | --new-p 0.1] [--stats <obs.npy>]
                                 [--opt <in opt.pt> <out opt.pt>] [--env duel_env_ffa]
      - the hands' inputs of "b17 order" (part 6): appended with zero weights; their statistics mean 0 spread 1 (or from --stats, a
        sample of raw inputs taken with COMBAT=1); the attention part's token "order", its gate shut (tools/targets_init.py widen_attn)
      - the head (parts 4, 7, 8): the order's kind (ok_s zero, ok_c), its pointer (op_s zero, op_x, op_v), cmb_g 0 and padd 0; the fire
        push (fsc zero, fadd 0); its own inputs and its weapon part's read "b17 order" too (inp's and winp's new columns zero)
      - the brain's pass readout (part 5, sim/passodds.py), its last layer at zero
      The order's start where it is asked: --fit (the pros' fit: ok_c, op_x, op_v; part 9) or, without one, --new-p of orders other
      than the target as chosen (evenly by kind; within a kind evenly: op_v zero). --opt copies the optimizer's state (the trainer adds
      the new groups after the load).
  python tools/order_init.py widen-league <in.pt> <out.pt> [--env duel_env_ffa]
      a league file (an anchor, a snapshot): its inputs and attention token only (the trainer gives it the head's parts shut)
  python tools/order_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass of both on the same random inputs and draws: 0 actions differ at share 0 and add 0 (b's new
      inputs random too: their weights are zero); then b at share 1 with random candidates: the column's order fields asked where the
      head has a state, its kinds near the start's

CPU only (CUDA_VISIBLE_DEVICES=-1).
"""
import argparse
import json
import math
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
INPUTS = os.path.join(ROOT, "docs", "INPUTS.csv")


def _env(name):
    import importlib
    os.environ["COMBAT"] = "1"
    return importlib.import_module(name)


def widen_inputs(ck, E, stats=None):
    """the hands' inputs to the simulator's (the new ones at the end, zero weights) and the attention part's new token, its gate shut"""
    import torch
    import targets_init as TI
    sd = ck["model"]
    old = int(sd["enc.0.weight"].shape[1])
    extra = E.OBS_DIM - old
    assert extra in (0, E.N_ORD), "the network has {} inputs, the simulator {} (this converter adds the {} of b17 order)".format(old, E.OBS_DIM, E.N_ORD)
    if extra:
        W = sd["enc.0.weight"]
        sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
        m_, v_ = np.zeros(extra), np.ones(extra)
        if stats:
            X = np.load(stats).astype(np.float64)
            assert X.shape[1] == E.OBS_DIM, (X.shape, E.OBS_DIM)
            m_ = X[:, -extra:].mean(0)
            v_ = np.maximum(X[:, -extra:].std(0), 0.02) ** 2
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), m_]).astype(np.asarray(ck["obs_mean"]).dtype)
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), v_]).astype(np.asarray(ck["obs_var"]).dtype)
        ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None and ck["attn"]["obs_dim"] != E.OBS_DIM:
        old_lay = dict(ck["attn"])
        fresh = TI.widen_attn(ck, INPUTS)
        for k_, v_ in old_lay.items():                        # (what the list does not say: the brain's token, the memory's query)
            ck["attn"].setdefault(k_, v_)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == ["order"], (ck["attn"]["obs_dim"], fresh)
    return extra, fresh


def widen_head(ck, E):
    """(part 7) the strategy head's own inputs and its weapon part's read the order's: inp's new columns (at the end of its obs part)
    and winp's (at the end) at zero; the layout's columns and widths. A head that has them already: as it is. -> the layout"""
    import torch
    import head2 as head2_
    sd, L = ck["model"], ck.get("head2")
    if L is None or "head2.inp.weight" not in sd:
        return L
    oc = [int(c) for c in head2_.obs_cols(INPUTS, (("b17 order", None),))]
    assert len(oc) == E.N_ORD, oc
    if set(oc) <= set(int(c) for c in L["obs_cols"]):
        return L
    o1 = head2_._offs(L)["obs"][1]
    W = sd["head2.inp.weight"]
    assert W.shape[1] == head2_.u0_width(L), (W.shape, head2_.u0_width(L))
    sd["head2.inp.weight"] = torch.cat([W[:, :o1], torch.zeros(W.shape[0], len(oc), dtype=W.dtype), W[:, o1:]], 1)
    L = dict(L, obs_cols=list(L["obs_cols"]) + oc, widths=dict(L["widths"], obs=int(L["widths"]["obs"]) + len(oc)))
    if L.get("weapon"):
        Wn = sd["head2.winp.weight"]
        sd["head2.winp.weight"] = torch.cat([Wn, torch.zeros(Wn.shape[0], len(oc), dtype=Wn.dtype)], 1)
        L = dict(L, wobs_cols=list(L["wobs_cols"]) + oc, widths=dict(L["widths"], wobs=int(L["widths"]["wobs"]) + len(oc)))
    ck["head2"] = L
    return L


def add(a):
    import torch
    import head2 as head2_
    import passodds as passodds_
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    L = ck.get("head2")
    assert L is not None and "head2.gate" in sd, "the order belongs to the strategy head"
    assert int(L.get("keep") or 0) == 2, "the order rides on 1.7's keep choice: tools/keep_init.py add first"
    assert not L.get("cmb") and "head2.op_v.weight" not in sd, "the network already has the order"
    extra, fresh = widen_inputs(ck, E, a.stats)
    L = widen_head(ck, E)
    # ---- the order and the fire push
    L = dict(L, cmb=1, fire=1)
    m = head2_.make_module(L)
    msd = m.state_dict()
    for k_, v_ in msd.items():
        if k_.startswith(("ok_", "op_", "fsc.", "cmb_g", "padd", "fadd")):
            sd["head2." + k_] = v_.clone()
    K = head2_.CMB_NK
    if a.fit:
        f = json.load(open(a.fit, encoding="utf-8"))
        sd["head2.ok_c.weight"] = torch.tensor(f["ok_c.weight"], dtype=torch.float32).reshape(K, head2_.CMB_NCTX)
        sd["head2.ok_c.bias"] = torch.tensor(f["ok_c.bias"], dtype=torch.float32).reshape(K)
        sd["head2.op_x.weight"] = torch.tensor(f["op_x.weight"], dtype=torch.float32).reshape(head2_.CMB_HID, head2_.CMB_F)
        sd["head2.op_x.bias"] = torch.tensor(f["op_x.bias"], dtype=torch.float32).reshape(head2_.CMB_HID)
        sd["head2.op_v.weight"] = torch.tensor(f["op_v.weight"], dtype=torch.float32).reshape(1, head2_.CMB_HID)
        sd["head2.op_v.bias"] = torch.tensor(f["op_v.bias"], dtype=torch.float32).reshape(1)
        how = "fitted to the pros ({})".format(a.fit)
        if a.kind_shift:                                    # (a start with the new kinds rarer than the pros' by e^-shift; the pointer the fit's)
            b_ = sd["head2.ok_c.bias"].clone()
            b_[1:] -= float(a.kind_shift)
            sd["head2.ok_c.bias"] = b_
            how += ", the new kinds' odds x e^-{:g}".format(a.kind_shift)
    else:
        b = torch.zeros(K)
        b[1:] = math.log(a.new_p / (K - 1)) - math.log(1.0 - a.new_p)
        sd["head2.ok_c.bias"] = b
        how = "a flat start: orders {} where asked, evenly by kind and candidate".format(a.new_p)
    ck["head2"] = L
    # ---- the brain's pass readout
    BL = ck.get("belief")
    hid = int(BL["hid"]) if BL else 256
    PL = passodds_.layout(E.CMB_FEAT, inp=hid)
    pm = passodds_.make_module(PL)
    for k_, v_ in pm.state_dict().items():
        sd["passr." + k_] = v_.clone()
    ck["passodds"] = PL
    mm = head2_.make_module(L)                               # (every key in place)
    mm.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    torch.save(ck, a.out)
    print(head2_.describe(L))
    print("wrote {}: {} new inputs (b17 order), new tokens {}; the order (share 0, adds 0), the fire push (add 0), the pass readout; "
          "the order's start: {}".format(a.out, extra, fresh, how))
    if a.opt:
        shutil.copyfile(a.opt[0], a.opt[1])
        print("copied the optimizer's state {} -> {} (the new groups are added by the trainer)".format(*a.opt))


def widen_league(a):
    import torch
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    extra, fresh = widen_inputs(ck, E)
    L0 = ck.get("head2")
    L = widen_head(ck, E)
    torch.save(ck, a.out)
    print("wrote {}: {} new inputs, new tokens {}{}".format(a.out, extra, fresh, "; its strategy head reads the order's inputs (at zero)"
                                                              if L is not None and L is not L0 else ""))


def same(a):
    import test_suite as T
    import head2 as head2_
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
            p.h2_live = True
    rng = np.random.default_rng(3)
    B, F = a.seats, a.frames
    ha, hb = pa.zeros(B), pb.zeros(B)
    nb = len(pb.mean)
    raw = rng.normal(pb.mean, np.sqrt(pb.var) + 1e-3, size=(F, B, nb)).astype(np.float32)
    pose = np.zeros((B, 4), np.float32)
    zmap = np.full(B, 0, np.int64)
    dact = 0
    for t in range(F):
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {"xl": rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)} if pa.needs_xl else {}
        oa, ha = pa.act(raw[t][:, :len(pa.mean)], ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, **kw)
        dact += int((oa[:, :len(pa.dims)] != ob[:, :len(pb.dims)]).sum())
        if t % 97 == 96:
            ha[:2], hb[:2] = 0.0, 0.0
    ok = dact == 0
    print("share 0, adds 0: {} frames x {} seats, actions that differ: {} -> {}".format(F, B, dact, "PASS" if ok else "FAIL"))
    # share 1: the order's fields of the column, on random candidates
    pb = T.Policy(a.b, seed=7)
    pb.h2_live = True
    pb.set_keep_g(1.0)
    pb.set_cmb_g(1.0)
    hb = pb.zeros(B)
    kinds = np.zeros(head2_.CMB_NK)
    expect = np.zeros(head2_.CMB_NK)                         # (the start's kind odds on the same situations: ok_s on the state is zero)
    Wc, bc = np.asarray(pb.h2W["ok_c.weight"], np.float64), np.asarray(pb.h2W["ok_c.bias"], np.float64)
    asked = 0
    rng = np.random.default_rng(5)
    for t in range(F):
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        X = rng.normal(0, 0.5, (B, head2_.CMB_ROWS, head2_.CMB_F)).astype(np.float32)
        X[..., head2_.CMB_VALID] = (rng.random((B, head2_.CMB_ROWS)) < 0.8)
        Cx = rng.normal(0, 0.5, (B, head2_.CMB_NCTX)).astype(np.float32)
        kf = np.stack([rng.uniform(0, 16, B), (rng.random(B) < 0.3), rng.integers(0, pb.dims[10], B), np.zeros(B), np.zeros(B),
                       np.full(B, 20.0), np.full(B, 20.0)], 1).astype(np.float32)
        kw = {"xl": rng.normal(0, 1, (B, pb.legsP[0].shape[1])).astype(np.float32)} if pb.needs_xl else {}
        ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, kf=kf, ox=(X, Cx), **kw)
        col = ob[:, -1]
        q_ = (col & 256) > 0
        asked += int(q_.sum())
        np.add.at(kinds, (col[q_] >> 3) & 3, 1)
        if q_.any():
            z_ = Cx[q_].astype(np.float64) @ Wc.T + bc
            p_ = np.exp(z_ - z_.max(1, keepdims=True))
            expect += (p_ / p_.sum(1, keepdims=True)).sum(0)
    sh, pk = kinds / max(1, asked), expect / max(1, asked)
    print("share 1: asked {} times; kinds drawn {} (the start's odds on the same situations: {})".format(asked, sh.round(3), pk.round(3)))
    good = asked > 0 and float(np.abs(sh - pk).max()) < 0.06
    print("ALL PASSED" if (ok and good) else "FAILED")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--fit", default="")
    p.add_argument("--new-p", type=float, default=0.1)
    p.add_argument("--kind-shift", type=float, default=0.0, help="(with --fit) the new kinds' logits lowered by this: rarer at the start")
    p.add_argument("--stats", default="")
    p.add_argument("--opt", nargs=2, default=None)
    p.add_argument("--env", default="duel_env_ffa")
    p = sp.add_parser("widen-league")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--env", default="duel_env_ffa")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--frames", type=int, default=400)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    {"add": add, "widen-league": widen_league, "same": same}[a.cmd](a)


if __name__ == "__main__":
    main()

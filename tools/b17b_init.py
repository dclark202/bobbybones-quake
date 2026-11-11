"""1.7b (docs/runs/1.7/1.7b/BUILD.md part 5): give 1.7a's result (its save of update 90) 1.7b's new parts, all at exactly zero effect: it
answers as before.

  python tools/b17b_init.py add <in policy.pt> <out policy.pt> [--ref <a save before the order was ever asked, e.g. 1.7a's policy_10.pt>]
                                [--env duel_env_ffa]
      - the hands' inputs of "b17b timers" (part 6 of the card: the yellow armors' timers): appended with zero weights, their statistics
        mean 0 spread 1; the attention part's token "timers", its gate shut (left out while shut: sim/attn.py DROP_SHUT)
      - the strategy head's inputs: the heard mega and red armor timers (memory) and the yellows' (b17b timers) at the end of its obs part,
        and its part "fight" (the brain's fight odds, two numbers, after ctrl): inp's new columns zero; the old columns' places written
        into the file ("head2_inp_map") for the trainer's carry-over of the optimizer's moments
      - the brain's fight odds readout (sim/fightodds.py, "fight.both"), its last layer at zero (its chances 0.5: the head reads 0)
      - the order's reference for the KL (--ord-kl): the order's own layers as the file has them (ok_c, op_x, op_v: the pros' fit of
        1.7a's start; ok_s, op_s zero), as "order_ref"; --ref checks them equal to those of a save before the order was asked
  python tools/b17b_init.py widen-league <in.pt> <out.pt> [--env duel_env_ffa]
      a league file (an anchor, a snapshot): its inputs, attention token and strategy head's inputs as above (no readout: its part
      "fight" reads zeros)
  python tools/b17b_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass of both on the same random inputs and draws, at the files' own shares and then at the keep choice's
      and the order's share 1 with random keep numbers and candidates: 0 actions differ (b's new inputs random too: their weights are zero)

CPU only (CUDA_VISIBLE_DEVICES=-1).
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
INPUTS = os.path.join(ROOT, "docs", "INPUTS.csv")
NEW_SEL = (("memory", "mega health: "), ("memory", "red armor: "), ("b17b timers", None))
REF_KEYS = ("ok_c.weight", "ok_c.bias", "op_x.weight", "op_x.bias", "op_v.weight", "op_v.bias")


def _env(name):
    import importlib
    os.environ.update(COMBAT="1", ITEM_BELIEF="1", FIGHT_TRUTH="1")
    return importlib.import_module(name)


def widen_inputs(ck, E):
    """the hands' inputs to the simulator's (the 4 timers at the end, zero weights) and the attention part's token "timers", shut"""
    import torch
    import targets_init as TI
    sd = ck["model"]
    old = int(sd["enc.0.weight"].shape[1])
    extra = E.OBS_DIM - old
    assert extra in (0, E.N_YT), "the network has {} inputs, the simulator {} (this converter adds the {} of b17b timers)".format(old, E.OBS_DIM, E.N_YT)
    if extra:
        W = sd["enc.0.weight"]
        sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)]).astype(np.asarray(ck["obs_mean"]).dtype)
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)]).astype(np.asarray(ck["obs_var"]).dtype)
        ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None and ck["attn"]["obs_dim"] != E.OBS_DIM:
        old_lay = dict(ck["attn"])
        fresh = TI.widen_attn(ck, INPUTS)
        for k_, v_ in old_lay.items():                        # (what the list does not say: the brain's token, the memory's query)
            ck["attn"].setdefault(k_, v_)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == ["timers"], (ck["attn"]["obs_dim"], fresh)
    return extra, fresh


def widen_head(ck):
    """the strategy head's inp: the new obs columns at the end of its obs part, the part "fight" (2) after ctrl, all at zero; the old
    columns kept, their new places -> (layout, the map old column -> new column) or (layout, None) for a head that has them already"""
    import torch
    import head2 as head2_
    sd, L0 = ck["model"], ck.get("head2")
    if L0 is None or "head2.inp.weight" not in sd:
        return L0, None
    oc = [c for c in head2_.obs_cols(INPUTS, NEW_SEL) if c not in set(int(x) for x in L0["obs_cols"])]
    if not oc and int(L0["widths"].get("fight", 0)) == 2:
        return L0, None
    assert int(L0["widths"].get("fight", 0)) == 0, "a head with another fight part: not built"
    L1 = dict(L0, obs_cols=list(L0["obs_cols"]) + oc, widths=dict(L0["widths"], obs=int(L0["widths"]["obs"]) + len(oc), fight=2))
    W = sd["head2.inp.weight"]
    assert W.shape[1] == head2_.u0_width(L0), (W.shape, head2_.u0_width(L0))
    o0, o1 = head2_._offs(L0), head2_._offs(L1)
    Wn = torch.zeros(W.shape[0], head2_.u0_width(L1), dtype=W.dtype)
    mp = np.full(W.shape[1], -1, np.int64)
    for p in head2_.PARTS:
        if p == "wobs":
            continue
        a0, b0 = o0[p]
        if b0 > a0:
            n0 = o1[p][0]
            Wn[:, n0:n0 + (b0 - a0)] = W[:, a0:b0]
            mp[a0:b0] = np.arange(n0, n0 + (b0 - a0))
    assert (mp >= 0).all() and len(set(mp.tolist())) == len(mp)
    sd["head2.inp.weight"] = Wn
    ck["head2"] = L1
    return L1, mp


def add(a):
    import torch
    import fightodds as fightodds_
    import head2 as head2_
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    L = ck.get("head2")
    assert L is not None and head2_.has_cmb(type("M", (), {"op_v": 1})) and "head2.op_v.weight" in sd, "1.7b rides on 1.7's order"
    assert "fight.both.0.weight" not in sd and "order_ref" not in ck, "the network already has 1.7b's parts"
    # ---- the order's reference: the order's own layers as they are (the pros' fit of 1.7a's start)
    ref = {k_: sd["head2." + k_].detach().cpu().numpy().astype(np.float32).copy() for k_ in REF_KEYS}
    for k_ in ("ok_s.weight", "op_s.weight"):
        assert float(sd["head2." + k_].abs().max()) == 0.0, "the order's state layer {} is not zero: the order has learnt (not 1.7a's start)".format(k_)
    if a.ref:
        r0 = torch.load(a.ref, weights_only=False, map_location="cpu")["model"]
        dif = {k_: float(np.abs(ref[k_] - r0["head2." + k_].cpu().numpy()).max()) for k_ in REF_KEYS}
        assert max(dif.values()) == 0.0, "the order's layers differ from {}'s: {}".format(a.ref, dif)
        print("the order's layers are those of {} to the bit (the order never learnt before)".format(a.ref))
    extra, fresh = widen_inputs(ck, E)
    L1, mp = widen_head(ck)
    BL = ck.get("belief")
    FL = fightodds_.layout(bel=int(BL["hid"]), mem=int(ck.get("hidden") or 512), every=1, horizon_frames=int(E.FIGHT_D), tick=int(BL["every"]))
    fm = fightodds_.make_module(FL)
    for k_, v_ in fm.state_dict().items():
        sd["fight." + k_] = v_.clone()
    ck["fightodds"] = FL
    ck["order_ref"] = ref
    if mp is not None:
        ck["head2_inp_map"] = mp.tolist()
    mm = head2_.make_module(L1)                               # (every key in place)
    mm.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    torch.save(ck, a.out)
    print(head2_.describe(L1))
    print("wrote {}: {} new inputs (b17b timers), new tokens {} (shut); the head's inp {} -> {} columns (obs +{}, fight 2, at zero); the fight odds "
          "readout (last layer at zero; horizon {} frames); the order's reference ({})".format(
              a.out, extra, fresh, len(mp) if mp is not None else "-", head2_.u0_width(L1), len(L1["obs_cols"]) - len(L["obs_cols"]),
              FL["horizon"], ", ".join(REF_KEYS)))


def widen_league(a):
    import torch
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    extra, fresh = widen_inputs(ck, E)
    L1, mp = widen_head(ck)
    ck.pop("head2_inp_map", None)
    torch.save(ck, a.out)
    print("wrote {}: {} new inputs, new tokens {}{}".format(a.out, extra, fresh, "; its strategy head's inputs widened (at zero)" if mp is not None else ""))


def same(a):
    import test_suite as T
    import head2 as head2_
    _env("duel_env_ffa")
    rng = np.random.default_rng(3)
    B, F = a.seats, a.frames
    ok = True
    for share in (None, 1.0):
        pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
        for p in (pa, pb):
            if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
                p.h2_live = True
            if share is not None:
                p.set_keep_g(share)
                p.set_cmb_g(share)
        ha, hb = pa.zeros(B), pb.zeros(B)
        nb, na = len(pb.mean), len(pa.mean)
        assert nb - na in (0, 4, 59, 63), (na, nb)             # (2.0b's 59 inputs after the timers: tools/b20b_init.py same)
        r2 = np.random.default_rng(5)
        dact = 0
        cols = 0
        pose = np.zeros((B, 4), np.float32)
        zmap = np.zeros(B, np.int64)
        for t in range(F):
            raw = r2.normal(pb.mean, np.sqrt(pb.var) + 1e-3, size=(B, nb)).astype(np.float32)
            pose[:, :3] += r2.normal(0, 10, (B, 3)).astype(np.float32)
            pose[:, 3] = r2.uniform(-180, 180, B)
            kw = {"xl": r2.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)} if pa.needs_xl else {}
            X = r2.normal(0, 0.5, (B, head2_.CMB_ROWS, head2_.CMB_F)).astype(np.float32)
            X[..., head2_.CMB_VALID] = (r2.random((B, head2_.CMB_ROWS)) < 0.8)
            Cx = r2.normal(0, 0.5, (B, head2_.CMB_NCTX)).astype(np.float32)
            kf = np.stack([r2.uniform(0, 16, B), (r2.random(B) < 0.3), r2.integers(0, pb.dims[10], B), (r2.random(B) < 0.2),
                           r2.uniform(0, 10, B), r2.uniform(0, 20, B), r2.uniform(0, 20, B)], 1).astype(np.float32)
            ex = dict(kf=kf, ox=(X, Cx)) if share is not None else {}
            oa, ha = pa.act(raw[:, :na], ha, pose=pose, zmap=zmap, **kw, **ex)
            ob, hb = pb.act(raw, hb, pose=pose, zmap=zmap, **kw, **ex)
            w_ = min(oa.shape[1], ob.shape[1])
            dact += int((oa[:, :w_] != ob[:, :w_]).sum())
            cols = w_
            if t % 97 == 96:
                ha[:2], hb[:2] = 0.0, 0.0
        good = dact == 0
        ok = ok and good
        print("{}: {} frames x {} seats, {} output columns, actions that differ: {} -> {}".format(
            "the files' own shares" if share is None else "keep choice and order at share 1, random keep numbers and candidates",
            F, B, cols, dact, "PASS" if good else "FAIL"))
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--ref", default="")
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
    r = {"add": add, "widen-league": widen_league, "same": same}[a.cmd](a)
    sys.exit(r or 0)


if __name__ == "__main__":
    main()

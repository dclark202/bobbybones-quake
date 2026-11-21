"""2.0b (docs/runs/2.0/2.0b/CARD.md): a network of 2.0a's shape (994 inputs in the group module) given 2.0b's parts with nothing of
them in effect, so that it answers as before (`same`):
      - the hands' inputs of "b20b space" (8) and "b20b targets" (51): appended with zero weights, their statistics 0 and 1; the
        attention part's tokens "space" and "targets", shut;
      - the strategy head's inputs: the same 59 columns at the end of its obs part, at zero; where each old column of its inp went is
        written into the file ("head2_inp_map") for the trainer's carry-over of the optimizer's moments;
      - `add` only: the brain's readout "space" (sim/spaceread.py), its last layer at zero.

    python tools/b20b_init.py add <in.pt> <out.pt>             the run's start
    python tools/b20b_init.py widen-league <in.pt> <out.pt>    a league file, an anchor, the control: the inputs and the head's, no readout
    python tools/b20b_init.py same <a.pt> <b.pt>               the two answer alike on random inputs (tools/b17b_init.py's check)
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
INPUTS = os.path.join(ROOT, "docs", "INPUTS.csv")
NEW_SEL = (("b20b space", None), ("b20b targets", None))
NEW_TOKENS = ["space", "targets"]


def _env(name):
    import importlib
    os.environ.update(COMBAT="1", ITEM_BELIEF="1", FIGHT_TRUTH="1", SPACE_TRUTH="1", SPACE_IN="1")
    return importlib.import_module(name)


def widen_inputs(ck, E):
    import torch
    import targets_init as TI
    sd = ck["model"]
    old = int(sd["enc.0.weight"].shape[1])
    new = E.N_SP + E.N_SPT
    extra = E.OBS_DIM - old
    assert extra in (0, new), "the network has {} inputs, the simulator {} (this converter adds the {} of 2.0b)".format(old, E.OBS_DIM, new)
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
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and sorted(fresh) == sorted(NEW_TOKENS), (ck["attn"]["obs_dim"], fresh)
        for i_, k_ in enumerate(ck["attn"]["kinds"]):         # the new tokens' first layer at zero: whatever their inputs read, the token is
            if k_["name"] in fresh:                           # its mark alone until the layer has learnt (the trainer opens a new token's
                sd["attn.emb.{}.weight".format(i_)].zero_()   # gate by its own clock, --gate-start; widen_attn draws the layer at random)
    return extra, fresh


def widen_head(ck):
    """the strategy head's inp: the new obs columns at the end of its obs part, at zero; the old columns kept, their new places ->
    (layout, the map old column -> new column) or (layout, None) for a file without the head or with the columns already"""
    import torch
    import head2 as head2_
    sd, L0 = ck["model"], ck.get("head2")
    if L0 is None or "head2.inp.weight" not in sd:
        return L0, None
    have = set(int(x) for x in L0["obs_cols"])
    oc = [c for c in head2_.obs_cols(INPUTS, NEW_SEL) if c not in have]
    if not oc:
        return L0, None
    L1 = dict(L0, obs_cols=list(L0["obs_cols"]) + oc, widths=dict(L0["widths"], obs=int(L0["widths"]["obs"]) + len(oc)))
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
    mm = head2_.make_module(L1)                               # (every key in place)
    mm.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    return L1, mp


def add(a):
    import torch
    import spaceread as spaceread_
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    assert not any(k_.startswith("space.") for k_ in sd), "the network already has 2.0b's readout"
    L = ck.get("head2")
    extra, fresh = widen_inputs(ck, E)
    L1, mp = widen_head(ck)
    BL = ck.get("belief")
    assert BL is not None, "2.0b's readout reads the belief's state: the network has none"
    SL = spaceread_.layout(bel=int(BL["hid"]), mem=int(ck.get("hidden") or 512), hid=a.hid, every=a.every, tick=int(BL["every"]))
    for k_, v_ in spaceread_.make_module(SL).state_dict().items():
        sd["space." + k_] = v_.clone()
    ck["spaceread"] = SL
    if mp is not None:
        ck["head2_inp_map"] = mp.tolist()
    else:
        ck.pop("head2_inp_map", None)
    torch.save(ck, a.out)
    print("wrote {}: {} new inputs (b20b space, b20b targets), new tokens {} (shut); the head's inp {} -> {} columns (obs +{}, at zero); the "
          "readout 'space' ({} -> {} -> {}, its last layer at zero, every {} tick(s))".format(
              a.out, extra, fresh, len(mp) if mp is not None else "-", sd["head2.inp.weight"].shape[1] if "head2.inp.weight" in sd else "-",
              (len(L1["obs_cols"]) - len(L["obs_cols"])) if L is not None else 0, SL["width"], SL["readouts"][0]["hid"], SL["d"], SL["every"]))


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
    import b17b_init as B17
    os.environ.update(SPACE_TRUTH="1", SPACE_IN="1")
    return B17.same(a)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--env", default="duel_env_ffa")
    p.add_argument("--hid", type=int, default=128)
    p.add_argument("--every", type=int, default=2)
    p = sp.add_parser("widen-league")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--env", default="duel_env_ffa")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--frames", type=int, default=400)
    p.add_argument("--seats", type=int, default=64)
    a = ap.parse_args()
    r = dict(add=add, same=same)[a.cmd](a) if a.cmd != "widen-league" else widen_league(a)
    sys.exit(int(r or 0))


if __name__ == "__main__":
    main()

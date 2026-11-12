"""1.9a (owner, 2026-11-12: "add fight odds and win chance"): give the start (1.8a's end on list 21 with the head's instruction part, made by
tools/head21_init.py add) the head's two new inputs, at exactly zero effect:
  - the part "fight" (2): the brain's fight odds (sim/fightodds.py, "fight.both": how a fight that is on ends, his enemy dead first, he dead
    first), the readout made new with its last layer at zero (its chances 0.5: the head reads 0) and learnt from update 0 (--fight-odds)
  - the part "wv" (1): his shadow win value (sim/win_value.py: what he reads of his chance of winning beyond the score and the clock, in frags;
    the module beside the network that 1.8a trained all run, carried in the file's top-level "win_value")
  The head's inp gets the new columns at zero (after ctrl, in sim/head2.py's PARTS order); the old columns' places go into "head2_inp_map" for
  the trainer's carry-over of the optimizer's moments.

  python tools/b19_init.py add <in.pt> <out.pt> [--env duel_env_ffa21]
  python tools/b19_init.py widen-league <in.pt> <out.pt>      a league file: the head's inp only (no readout: its parts read zeros)
  (the proof: tools/head21_init.py same <in.pt> <out.pt> --sample <obs.npy>: 0 actions differ)
CPU only (CUDA_VISIBLE_DEVICES=-1)."""
import argparse
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def widen_head(ck):
    import torch
    import head2 as head2_
    sd, L0 = ck["model"], ck.get("head2")
    assert L0 is not None and "head2.inp.weight" in sd, "no strategy head"
    assert int(L0["widths"].get("fight", 0)) == 0 and int(L0["widths"].get("wv", 0)) == 0, "the head has a fight or wv part already"
    L1 = dict(L0, widths=dict(L0["widths"], fight=2, wv=1), on=dict(L0["on"], fight=1, wv=1))
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
    if ck.get("head2_inp_map") is not None:                  # (a map from an earlier widening in this same start: composed)
        m0 = np.asarray(ck["head2_inp_map"], np.int64)
        mp = mp[m0]
    sd["head2.inp.weight"] = Wn
    ck["head2"] = L1
    ck["head2_inp_map"] = mp.tolist()
    mm = head2_.make_module(L1)                              # (every key in place)
    mm.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    return L1, mp


def add(a):
    import torch
    import fightodds as fightodds_
    import head2 as head2_
    os.environ.setdefault("FIGHT_TRUTH", "1")
    E = importlib.import_module(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    assert "fight.both.0.weight" not in sd and not ck.get("fightodds"), "the network has a fight odds readout already"
    assert ck.get("win_value") and ck["win_value"].get("model"), "the network has no shadow win value (1.8a trained one): not built"
    L1, mp = widen_head(ck)
    BL = ck.get("belief")
    FL = fightodds_.layout(bel=int(BL["hid"]), mem=int(ck.get("hidden") or 512), every=1, horizon_frames=int(E.FIGHT_D), tick=int(BL["every"]))
    fm = fightodds_.make_module(FL)
    for k_, v_ in fm.state_dict().items():
        sd["fight." + k_] = v_.clone()
    ck["fightodds"] = FL
    torch.save(ck, a.out)
    print(head2_.describe(L1))
    print("wrote {}: the head's inp {} -> {} columns (fight 2, wv 1, at zero); the fight odds readout new (last layer at zero; horizon {} frames); "
          "the shadow win value as the file has it ({} -> {} -> 1)".format(a.out, len(mp), head2_.u0_width(L1), FL["horizon"],
                                                                         ck["win_value"]["layout"]["width"], ck["win_value"]["layout"]["hid"]))


def widen_league(a):
    import torch
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    if ck.get("head2") is None:
        torch.save(ck, a.out)
        print("wrote {}: no strategy head, as it was".format(a.out))
        return
    L1, mp = widen_head(ck)
    torch.save(ck, a.out)
    print("wrote {}: the head's inp widened (fight 2, wv 1 at zero; no readout here: they read zeros)".format(a.out))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--env", default="duel_env_ffa21")
    p = sp.add_parser("widen-league")
    p.add_argument("inp")
    p.add_argument("out")
    a = ap.parse_args()
    (add if a.cmd == "add" else widen_league)(a)


if __name__ == "__main__":
    main()

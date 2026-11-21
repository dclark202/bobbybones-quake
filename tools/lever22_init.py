"""2.2c (docs/runs/2.2/2.2c/CARD.md change 2): the start's fight network made the aggression lever (sim/fightnet.py VERSION_LEVER).

    python tools/lever22_init.py layout <in.pt> <out.pt>
        in.pt: 2.2b's start (tools/fight22_init.py layout, then norm: its fight network of the four options with its inputs' norm MEASURED on the
        start's play), brought to list 22c (tools/inputs22c.py convert). Out: the fight network replaced by the lever: its layout (the same
        inputs without the options' numbers and without "the fight option he is on"; the tracker's pass scorer's norm kept for the tracker's
        own rows), a new network from its own random stream with the last layer at zero (the lever 0, the forecasts 0), its inputs' norm the
        measured norm of the same inputs (taken by name from the four options' network's: the same numbers on the same keep readings), no
        optimizer, the dial LEV_G 0. Nothing of 2.2b's training is in it (2.2b's start file never trained).
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def layout_cmd(a):
    import torch
    import fightnet as FN
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    assert str((ck.get("inputs") or {}).get("list")) == "22c", "not a network of list 22c (tools/inputs22c.py convert first)"
    F = ck.get("fight22")
    assert F is not None and not FN.is_lever(F["layout"]) and F["layout"].get("norm") is not None, \
        "2.2b's fight network with its measured norm expected (tools/fight22_init.py layout, then norm)"
    L1 = F["layout"]
    L2h = ck["head2"]
    assert [int(c_) for c_ in L1["obs_cols"]] == [int(c_) for c_ in L2h["obs_cols"]], "the fight network's obs columns are not the item picker's"
    TL = L2h["trk22"]
    w_ = dict((k_, w2_) for k_, w2_ in L1["parts"])
    L2 = FN.layout_lever(brain=int(TL["bel"]), trk=int(w_["trk"]), obs_cols=L1["obs_cols"], obs_names=L1["obs_names"], n_target=int(L1["n_target"]),
                         head=int(w_["head"]), hands=int(w_["hands"]), pass_norm=L1["pass_norm"], hid=int(L1["hid"]))
    n1, n2 = FN.names(L1), FN.names(L2)
    ix = {k_: i_ for i_, k_ in enumerate(n1)}
    miss = [k_ for k_ in n2 if k_ not in ix]
    assert not miss, "inputs of the lever not in the four options' network: {}".format(miss[:8])
    sel = np.array([ix[k_] for k_ in n2], np.int64)
    N1 = L1["norm"]
    L2["norm"] = dict(mean=[float(N1["mean"][i_]) for i_ in sel], sd=[float(N1["sd"][i_]) for i_ in sel],
                      measured=dict(N1.get("measured") or {}, taken_by_name_from="2.2b's start: the four options' network's norm (the same inputs, the same keep readings)"),
                      const=[k_ for k_ in (N1.get("const") or []) if k_ in set(n2)])
    mod = FN.make_module(L2)
    ck["fight22"] = dict(layout=L2, model={k_: v_.detach().clone() for k_, v_ in mod.state_dict().items()}, opt=None, applied_bias=None,
                         dials=dict(LEV_G=0.0), note="tools/lever22_init.py layout: the aggression lever, its last layer at zero")
    torch.save(ck, a.out)
    dropped = [k_ for k_ in n1 if k_ not in set(n2)]
    print("wrote {}: the lever: {} inputs ({}), {} -> {} -> 3 outputs (the lever, 2 forecasts), the last layer at zero; its norm taken by name "
          "from the four options' network's measured norm ({} of its {} inputs; left out {}: the options' numbers and 'the fight option he is on'); "
          "{} constant inputs at spread 1".format(a.out, L2["width"], ", ".join("{} {}".format(k_, w2_) for k_, w2_ in L2["parts"]), L2["hid"], L2["hid"],
                                                  len(n2), len(n1), len(dropped), len(L2["norm"]["const"])))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("layout")
    p.add_argument("inp")
    p.add_argument("out")
    a = ap.parse_args()
    {"layout": layout_cmd}[a.cmd](a)


if __name__ == "__main__":
    main()

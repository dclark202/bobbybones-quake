"""v0.3.11: give a network the belief readout (sim/track.py; docs/v0.3.11/INFO_PAY.md), or take it out.

    python tools/track_init.py widen <in.pt> <out.pt> [--hid 256] [--parts pos:1,vel:0.25,band:0.5,hand:0.25,own:0.25]
    python tools/track_init.py strip <in.pt> <out.pt>
    python tools/track_init.py show <file.pt>

widen: the network gets the readout's layers (track.0: his memory -> 256, track.2: 256 -> 27, its last layer at zero: the
       readout starts by saying the prior spreads around his own place, every category even) and the layout ("track").
       Nothing else is touched: the readout reads his memory and feeds nothing, so every output answers as before
       (`python sim/add_attention.py --same <in.pt> <out.pt>` prints 0). The optimizer's state needs nothing: the trainer
       puts the readout in a group of its own after the saved ones (sim/train_duel_rnn.py trk_group).
strip: the readout's layers and layout taken out (a file for a tool that wants exactly the old keys).
The league's files and the control do not need it: the trainer reads every seat with the learner's own readout.
"""
import argparse
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sim"))
import track as track_                                         # noqa: E402


def widen(src, dst, hid, parts):
    ck = torch.load(src, weights_only=False, map_location="cpu")
    if any(k.startswith("track.") for k in ck["model"]):
        raise SystemExit("{} has the readout already".format(src))
    H = int(ck.get("hidden") or ck["model"]["gru.weight_hh"].shape[1])
    L = track_.layout(hid=hid, weights=track_.parse_weights(parts))
    m = track_.make_module(H, L)
    ck["model"] = dict(ck["model"])
    for k, v in m.state_dict().items():
        ck["model"]["track." + k] = v.clone()
    ck["track"] = L
    torch.save(ck, dst)
    print("widened {} -> {}: the readout {} -> {} -> {} ({} weights), its last layer at zero".format(
        src, dst, H, hid, L["d"], sum(v.numel() for v in m.state_dict().values())))


def strip(src, dst):
    ck = torch.load(src, weights_only=False, map_location="cpu")
    ck["model"] = {k: v for k, v in ck["model"].items() if not k.startswith("track.")}
    ck.pop("track", None)
    torch.save(ck, dst)
    print("stripped {} -> {}".format(src, dst))


def show(path):
    ck = torch.load(path, weights_only=False, map_location="cpu")
    ks = [k for k in ck["model"] if k.startswith("track.")]
    print(path, "track layout:", ck.get("track"))
    for k in ks:
        print("  {} {} |w| {:.4g}".format(k, tuple(ck["model"][k].shape), float(ck["model"][k].abs().sum())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("widen", "strip", "show"))
    ap.add_argument("files", nargs="+")
    ap.add_argument("--hid", type=int, default=256)
    ap.add_argument("--parts", default="pos:1,vel:0.25,band:0.5,hand:0.25,own:0.25")
    a = ap.parse_args()
    if a.what == "widen":
        widen(a.files[0], a.files[1], a.hid, a.parts)
    elif a.what == "strip":
        strip(a.files[0], a.files[1])
    else:
        for f in a.files:
            show(f)


if __name__ == "__main__":
    main()

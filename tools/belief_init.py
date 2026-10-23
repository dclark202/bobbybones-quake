"""v0.4.0 stage A: give a network the belief memory (sim/belief.py) and a fresh readout that reads it (sim/track.py).

    python tools/belief_init.py add <in.pt> <out.pt> [--hid 256] [--every 8] [--replace-track]
                                    [--parts pos:1,vel:0.25,band:0.5,hand:0.25,own:0.25]
    python tools/belief_init.py add-zones <in.pt> <out.pt> [--zhid 256] [--zparts zone:0.5,spd:0.25,dir:0.25]
    python tools/belief_init.py show <file.pt> ...

add:  the network gets the belief's layers (belief.inp: the normalised inputs -> hid, belief.gru: GRUCell 2 hid -> hid;
      PyTorch's own start from a random stream of its own) and the layout ("belief"), and a readout reading the belief's state
      (track.0: hid -> 256, track.2: 256 -> 27, its last layer at zero, the bias the prior spreads: as tools/track_init.py
      widen) with the layout ("track", "src": "belief"). Nothing of the policy is touched and nothing of it reads either part:
      every output answers as before (`python sim/add_attention.py --same <in.pt> <out.pt>`). A network that has a readout on
      his memory (v0.3.11) is refused unless --replace-track (that readout is dropped). The optimizer's state needs nothing:
      the trainer puts the readout and the belief in groups of their own after the saved ones (sim/train_duel_rnn.py
      trk_group).
add-zones: (2026-10-23) a network with the belief and its readout (v0.4.0's) gets the readout's second part (sim/track_z.py:
      trackz.0: the belief's state -> zhid, trackz.2: zhid -> 28: the zones' odds, the speed, the direction; its last layer at
      zero, the bias the speed's prior: even zones, the prior speed, every direction alike) and its layout ("track_z"). Every
      weight already there is kept as it is (checked); the optimizer's state needs nothing: the trainer puts the part in a
      group of its own after the belief's (sim/train_duel_rnn.py trz_group), so v0.4.0's opt.pt loads as saved.
show: the layouts and the parts' weights.
The league's files and the control do not need it: the trainer reads every seat with the learner's own belief and readout.
"""
import argparse
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sim"))
import belief as belief_                                       # noqa: E402
import track as track_                                         # noqa: E402
import track_z as trz_                                         # noqa: E402


def add(src, dst, hid, every, parts, replace):
    ck = torch.load(src, weights_only=False, map_location="cpu")
    m = dict(ck["model"])
    if any(k.startswith("belief.") for k in m):
        raise SystemExit("{} has a belief memory already".format(src))
    if any(k.startswith("track.") for k in m):
        if not replace:
            raise SystemExit("{} has a readout (on {}): --replace-track drops it for a fresh one on the belief".format(
                src, (ck.get("track") or {}).get("src", "his memory")))
        m = {k: v for k, v in m.items() if not k.startswith("track.")}
    obs_dim = int(ck.get("obs_dim") or m["enc.0.weight"].shape[1])
    assert int(m["enc.0.weight"].shape[1]) == obs_dim, "the encoder reads {} inputs, the file says {}".format(m["enc.0.weight"].shape[1], obs_dim)
    BL = belief_.layout(obs_dim, hid=hid, every=every)
    bm = belief_.make_module(BL)
    TL = dict(track_.layout(weights=track_.parse_weights(parts)), src="belief", inp=int(hid))
    tm = track_.make_module(int(hid), TL)
    for k, v in bm.state_dict().items():
        m["belief." + k] = v.clone()
    for k, v in tm.state_dict().items():
        m["track." + k] = v.clone()
    ck["model"] = m
    ck["belief"] = BL
    ck["track"] = TL
    torch.save(ck, dst)
    print("added to {} -> {}: {}; the readout {} -> {} -> {} on the belief ({} + {} weights), its last layer at zero".format(
        src, dst, belief_.describe(BL), hid, TL["hid"], TL["d"], sum(v.numel() for v in bm.state_dict().values()),
        sum(v.numel() for v in tm.state_dict().values())))


def add_zones(src, dst, zhid, zparts):
    ck = torch.load(src, weights_only=False, map_location="cpu")
    m = dict(ck["model"])
    assert any(k.startswith("belief.") for k in m) and (ck.get("track") or {}).get("src") == "belief",         "{}: no belief memory with its readout (tools/belief_init.py add first)".format(src)
    if any(k.startswith("trackz.") for k in m):
        raise SystemExit("{} has the readout's second part already".format(src))
    hid = int(ck["belief"]["hid"])
    ZL = trz_.layout(hid=zhid, weights=trz_.parse_weights(zparts), inp=hid)
    zm = trz_.make_module(hid, ZL)
    for k, v in zm.state_dict().items():
        m["trackz." + k] = v.clone()
    old = ck["model"]
    assert all(torch.equal(old[k], m[k]) for k in old) and set(m) - set(old) == {"trackz." + k for k in zm.state_dict()}
    ck["model"] = m
    ck["track_z"] = ZL
    torch.save(ck, dst)
    print("added to {} -> {}: the readout's second part {} -> {} -> {} ({} weights; zones up to {}, speed, direction), its last layer at "
          "zero; the {} tensors already there unchanged".format(src, dst, hid, zhid, ZL["d"], sum(v.numel() for v in zm.state_dict().values()),
                                                               trz_.MAX_Z, len(old)))


def show(path):
    ck = torch.load(path, weights_only=False, map_location="cpu")
    print(path)
    print("  belief layout:", ck.get("belief"))
    print("  track layout:", ck.get("track"))
    print("  track_z layout:", ck.get("track_z"))
    for k in [k for k in ck["model"] if k.startswith(("belief.", "track.", "trackz."))]:
        print("  {} {} |w| {:.4g}".format(k, tuple(ck["model"][k].shape), float(ck["model"][k].abs().sum())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("add", "add-zones", "show"))
    ap.add_argument("files", nargs="+")
    ap.add_argument("--hid", type=int, default=256)
    ap.add_argument("--every", type=int, default=8)
    ap.add_argument("--parts", default="pos:1,vel:0.25,band:0.5,hand:0.25,own:0.25")
    ap.add_argument("--replace-track", action="store_true")
    ap.add_argument("--zhid", type=int, default=256)
    ap.add_argument("--zparts", default="zone:0.5,spd:0.25,dir:0.25")
    a = ap.parse_args()
    if a.what == "add":
        assert len(a.files) == 2, "add <in.pt> <out.pt>"
        add(a.files[0], a.files[1], a.hid, a.every, a.parts, a.replace_track)
    elif a.what == "add-zones":
        assert len(a.files) == 2, "add-zones <in.pt> <out.pt>"
        add_zones(a.files[0], a.files[1], a.zhid, a.zparts)
    else:
        for f in a.files:
            show(f)


if __name__ == "__main__":
    main()

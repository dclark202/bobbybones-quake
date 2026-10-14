"""Gives a network the slow memory (sim/slowmem.py; v0.3 candidate, 2026-10-14) with its door shut: it plays exactly as before.

    python sim/add_slow_mem.py <in.pt> <out.pt> [--size 256] [--inp 128] [--every 48] [--ring 320] [--seed 0]
    python sim/add_slow_mem.py --same <a.pt> <b.pt>          (do two networks answer alike? prints the largest difference)

The part (inp, gru, door: the door all zeros) goes into the state dict under "slow.", its layout into the file ("slow").
League files (snapshots, anchors) and the control need not be converted for the trainer (it gives a file without the part
one with its door shut as it loads it) but the checks' tools and the export read only what is in the file. A network that
has the part already is refused."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def convert(src, dst, size=256, inp=128, every=48, ring=320, seed=0):
    import torch
    import slowmem as S
    ck = torch.load(src, weights_only=False, map_location="cpu")
    assert ck.get("slow") is None, "{} has a slow memory already".format(src)
    sd = ck["model"]
    fast, enc = sd["gru.weight_hh"].shape[1], sd["gru.weight_ih"].shape[1]
    lay = S.layout(size=size, inp=inp, every=every, ring=ring, fast=fast, enc=enc)
    for k, v in S.make_module(lay, seed).state_dict().items():
        sd["slow." + k] = v
    ck["slow"] = lay
    torch.save(ck, dst)
    print("{} -> {}: {}; weights {}".format(os.path.basename(src), os.path.basename(dst), S.describe(lay),
                                           sum(int(np.prod(v.shape)) for k, v in sd.items() if k.startswith("slow."))))


def same(a, b, frames=200, players=32):
    """the two networks on the same random inputs and the same draws: the largest difference of their fast memories and of
    their outputs' choices (frames: past several of the slow memory's ticks)"""
    import test_suite as T_
    pa, pb = T_.Policy(a, seed=5), T_.Policy(b, seed=5)
    n = max(len(pa.mean), len(pb.mean))
    rng = np.random.default_rng(1)
    ha, hb = pa.zeros(players), pb.zeros(players)
    H = min(pa.H, pb.H)
    worst, acts, k = 0.0, 0, 0
    for f_ in range(frames):
        pa.rng, pb.rng = np.random.default_rng(1000 + f_), np.random.default_rng(1000 + f_)
        obs = (rng.standard_normal((players, n)) * 2.0).astype(np.float32)
        aa, ha = pa.act(obs, ha)
        ab, hb = pb.act(obs, hb)
        k = min(aa.shape[1], ab.shape[1])
        acts += int((aa[:, :k] != ab[:, :k]).sum())
        worst = max(worst, float(np.abs(ha[:, :H] - hb[:, :H]).max()))
    print("{} and {}: largest difference of their memories {:.2e}, choices that differ {} of {}".format(
        os.path.basename(a), os.path.basename(b), worst, acts, frames * players * k))
    return worst, acts


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--same":
        w_, a_ = same(args[1], args[2])
        sys.exit(0 if w_ < 1e-6 and a_ == 0 else 1)

    def opt(name, d):
        return type(d)(args[args.index(name) + 1]) if name in args else d
    convert(args[0], args[1], size=opt("--size", 256), inp=opt("--inp", 128), every=opt("--every", 48), ring=opt("--ring", 320),
            seed=opt("--seed", 0))

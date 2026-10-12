"""Gives a network the attention part of v0.2 with its door shut: the network plays exactly as before.

    python sim/add_attention.py <in.pt> <out.pt> [--inputs docs/INPUTS.csv] [--seed 0]
    python sim/add_attention.py --same <a.pt> <b.pt>          (do two networks answer alike? prints the largest difference)

The inputs are widened to the list's length (new inputs are the list's last rows: zero weight in the old encoder, mean
0 and spread 1 in the input statistics, so a new input reaches the tokens as the simulator gives it); the attention
part (sim/attn.py) is added with fresh weights and a last layer of zeros; two value outputs for the pay of items and
stack are added at zero (the trainer's --long-gamma). The layout of the tokens is kept in the file ("attn"). League
files (snapshots, anchors) and the control must be given the same parts: the trainer loads them into one shape."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def convert(src, dst, inputs, seed=0):
    import torch
    import attn as A
    lay = A.layout_from_csv(inputs)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    w = sd["enc.0.weight"]
    extra = lay["obs_dim"] - w.shape[1]
    assert extra >= 0, "the network has {} inputs, the list {}".format(w.shape[1], lay["obs_dim"])
    if extra:
        sd["enc.0.weight"] = torch.cat([w, torch.zeros(w.shape[0], extra, dtype=w.dtype)], 1)
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)])
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)])
    for k in [k for k in sd if k.startswith("attn.")]:
        del sd[k]
    for k, v in A.make_module(lay, sd["gru.weight_ih"].shape[1], seed).state_dict().items():
        sd["attn." + k] = v
    hdim = sd["gru.weight_hh"].shape[1]
    sd.setdefault("v2.weight", torch.zeros(2, hdim))
    sd.setdefault("v2.bias", torch.zeros(2))
    ck.update(attn=lay, arch="gru+attn", obs_dim=lay["obs_dim"])
    torch.save(ck, dst)
    print("{} -> {}: {} inputs ({} new), {}; attention weights {}".format(
        os.path.basename(src), os.path.basename(dst), lay["obs_dim"], extra, A.describe(lay).split(": ", 1)[1],
        sum(int(np.prod(v.shape)) for k, v in sd.items() if k.startswith("attn."))))


def same(a, b, frames=40, players=32):
    """the two networks on the same random inputs and the same draws: the largest difference of their memories"""
    import test_suite as T_
    pa, pb = T_.Policy(a, seed=5), T_.Policy(b, seed=5)
    n = max(len(pa.mean), len(pb.mean))
    rng = np.random.default_rng(1)
    ha, hb = pa.zeros(players), pb.zeros(players)
    worst, acts = 0.0, 0
    for _ in range(frames):
        obs = (rng.standard_normal((players, n)) * 2.0).astype(np.float32)
        aa, ha = pa.act(obs, ha)
        ab, hb = pb.act(obs, hb)
        k = min(aa.shape[1], ab.shape[1])
        acts += int((aa[:, :k] != ab[:, :k]).sum())
        worst = max(worst, float(np.abs(ha - hb).max()))
    print("{} and {}: largest difference of their memories {:.2e}, choices that differ {} of {}".format(
        os.path.basename(a), os.path.basename(b), worst, acts, frames * players * k))
    return worst, acts


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--same":
        w_, a_ = same(args[1], args[2])
        sys.exit(0 if w_ < 1e-4 and a_ == 0 else 1)
    inputs = os.path.join(ROOT, "docs", "INPUTS.csv")
    seed = 0
    if "--inputs" in args:
        inputs = args[args.index("--inputs") + 1]
    if "--seed" in args:
        seed = int(args[args.index("--seed") + 1])
    convert(args[0], args[1], inputs, seed)

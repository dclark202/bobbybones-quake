"""1.8a (docs/runs/1.8/1.8a/CARD.md): a network of b1.2d's shape (980 inputs in the group module, no strategy head) brought to today's
simulator with nothing of the newer inputs in effect, so that it answers as before:
      - the hands' inputs after its own (b17 order 10, b17b timers 4, b20b space 8, b20b targets 51): appended with zero weights, their
        statistics 0 and 1; the attention part's tokens "order", "timers", "space", "targets": their first layer at zero, shut
        (the run keeps them shut: --gate-open 0; COMBAT and SPACE_IN are off in 1.8a, so the order's and the map's inputs read zeros).
    A file that has a strategy head already (1.3b's and later league files) gets its head's inputs widened as tools/order_init.py,
    b17b_init.py and b20b_init.py do, in that order, where it lacks them.

    python tools/b18_init.py widen <in.pt> <out.pt>     the start (before tools/head2_init.py add and tools/keep_init.py add), a league file
    python tools/b18_init.py same <a.pt> <b.pt>         the two answer alike on random inputs (tools/head2_init.py's check: the new inputs
                                                         random too, so a weight on them or an open token would show)
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
NEW_TOKENS = ["order", "timers", "space", "targets"]


def _env(name):
    import importlib
    return importlib.import_module(name)


def widen(a):
    import torch
    import targets_init as TI
    E = _env(a.env)
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    old = int(sd["enc.0.weight"].shape[1])
    new = E.N_ORD + E.N_YT + E.N_SP + E.N_SPT
    extra = E.OBS_DIM - old
    assert extra == new, "the network has {} inputs, the simulator {}: this converter adds exactly the {} after b1.2d's".format(old, E.OBS_DIM, new)
    assert ck.get("head2") is None and not any(k.startswith("head2.") for k in sd), "a file with a strategy head: use the converters of its own run"
    W = sd["enc.0.weight"]
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
    ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)]).astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)]).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None:
        old_lay = dict(ck["attn"])
        fresh = TI.widen_attn(ck, INPUTS)
        for k_, v_ in old_lay.items():                        # (what the list does not say: the brain's token, the memory's query)
            ck["attn"].setdefault(k_, v_)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and sorted(fresh) == sorted(NEW_TOKENS), (ck["attn"]["obs_dim"], fresh)
        for i_, k_ in enumerate(ck["attn"]["kinds"]):         # the new tokens' first layer at zero (as tools/b20b_init.py): a token is its
            if k_["name"] in fresh:                           # mark alone, and shut
                sd["attn.emb.{}.weight".format(i_)].zero_()
    torch.save(ck, a.out)
    print("wrote {}: {} -> {} inputs ({} new, zero weights), new tokens {} (first layer zero, shut)".format(a.out, old, E.OBS_DIM, extra, fresh))


def same(a):
    import head2_init as H
    wa = int(__import__("torch").load(a.a, weights_only=False, map_location="cpu")["obs_dim"])
    wb = int(__import__("torch").load(a.b, weights_only=False, map_location="cpu")["obs_dim"])
    if wb > wa:                                               # (the random inputs are drawn at the first file's width: the wider one first)
        a.a, a.b = a.b, a.a
    dh, dact = H.same(a)
    print("ALL PASSED" if dact == 0 else "FAILED: {} actions differ".format(dact))
    return 0 if dact == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("widen")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--env", default="duel_env_ffa")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--frames", type=int, default=400)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    r = widen(a) if a.cmd == "widen" else same(a)
    sys.exit(int(r or 0))


if __name__ == "__main__":
    main()

"""A network of 868 inputs made a network of the simulator with SM_ITEMS (b1.2c, owner 2026-11-01; sim/duel_env.py): the N_ITEMS new inputs get zero weight in the encoder, mean 0 and spread 1 in the input statistics, and a token a small item whose gate is shut. The brain keeps the inputs it was made with. With the gate shut the network answers as before: `same` proves it.
    python tools/items_init.py widen <in.pt> <out.pt>
    python tools/items_init.py same <a.pt> <b.pt>          (actions and logits on random inputs, the new columns random too; 0 differing is the pass)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
INPUTS = os.path.join(os.path.dirname(HERE), "docs", "INPUTS.csv")


def _env():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    for p_ in (SIM, HERE):
        if p_ not in sys.path:
            sys.path.insert(0, p_)
    import duel_env_ffa as E
    return E


def widen(src, dst):
    E = _env()
    import numpy as np
    import torch
    import targets_init as TI
    torch.set_num_threads(1)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    old_n = int(sd["enc.0.weight"].shape[1])
    extra = E.OBS_DIM - old_n
    assert extra == E.N_ITEMS, "the network has {} inputs, the simulator {}: this adds the {} of N_ITEMS only".format(old_n, E.OBS_DIM, E.N_ITEMS)
    W = sd["enc.0.weight"]
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
    ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)]).astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)]).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = E.OBS_DIM
    old_lay = dict(ck["attn"])
    fresh = TI.widen_attn(ck, INPUTS)
    for k_, v_ in old_lay.items():                            # (what the list does not say: the brain's token, the memory's query)
        ck["attn"].setdefault(k_, v_)
    assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == ["small"], (ck["attn"]["obs_dim"], fresh)
    ck["items_init"] = dict(inputs_added=int(extra), tokens_added=fresh)
    torch.save(ck, dst)
    print("widened: {} ({} inputs, {} new, attention tokens {}, new and shut: {})".format(dst, sd["enc.0.weight"].shape[1], extra, ck["attn"]["tokens"] - 1, fresh))


def same(pa, pb):
    _env()
    import numpy as np
    import test_suite as T
    a, b = T.Policy(pa, seed=7), T.Policy(pb, seed=7)
    rng = np.random.default_rng(3)
    B, F = 16, 300
    na, nb = len(a.mean), len(b.mean)
    ha, hb = a.zeros(B), b.zeros(B)
    pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
    diff, big = 0, 0.0
    for _ in range(F):
        x = rng.normal(b.mean, np.sqrt(b.var) + 1e-3, size=(B, nb)).astype(np.float32)
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if a.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, a.legsP[0].shape[1])).astype(np.float32)
        A, ha = a.act(x[:, :na], ha, pose=pose, zmap=zmap, **kw)
        C, hb = b.act(x, hb, pose=pose, zmap=zmap, **kw)
        diff += int((A != C).sum())
        big = max(big, float(np.abs(ha - hb).max()))
    print("frames {}, seats {}: memory's largest difference {:.2e}; actions that differ: {}".format(F, B, big, diff))
    return 0 if diff == 0 else 1


if __name__ == "__main__":
    if sys.argv[1] == "widen":
        widen(sys.argv[2], sys.argv[3])
    else:
        sys.exit(same(sys.argv[2], sys.argv[3]))

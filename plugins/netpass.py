"""The network's forward pass in plain numpy, for both plugins (no torch on a game server).

The same sums as sim/test_suite.py's Policy.act, the reference: inputs normalised and cut at +-10, two layers, the
attention part of v0.2 added to what they give (sim/attn.py's forward_np; skipped while its last layer, the door, is
all zeros), one step of his memory, one sampled choice per output. Not a plugin: plugins/duelbot.py and
plugins/ffabot.py import it; a test outside a server can too (it does not need minqlx).

    P, A = load("/tmp/practice/policy.npz")      # the arrays of sim/export_duel.py; A = (layout, weights) or None
    acts, h = step(P, A, obs, h, rng)             # obs [B, inputs], h [B, memory] -> choices [B, outputs], the new memory
"""
import json
import os
import sys

import numpy as np


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def load(path):
    """policy.npz -> (its arrays as a dict, the attention part or None). The attention part is (the token layout, its
    weights by the names sim/attn.py gives them); None for a network without one or with its door still shut."""
    z = np.load(path)
    P = {k: z[k] for k in z.files}
    A = None
    if "attn" in P:
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import attn as attn_                                 # sim/attn.py: numpy only (torch is imported inside make_module alone)
        lay = json.loads(str(P["attn"]))
        W = {k[len("attn."):]: v for k, v in P.items() if k.startswith("attn.")}
        assert int(lay["obs_dim"]) == P["w0"].shape[1], "the tokens are cut from {} inputs, the network has {}".format(lay["obs_dim"], P["w0"].shape[1])
        if np.abs(W["door.weight"]).sum() > 0:
            # (the index lists as arrays once, not at every frame: forward_np takes either)
            lay = dict(lay, kinds=[dict(k_, idx=np.asarray(k_["idx"], np.int64)) for k_ in lay["kinds"]])
            A = (lay, W, attn_.forward_np)
    if "slow" in P:                                          # (--slow-mem) the slow memory: kept beside the arrays as (layout, weights, step)
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import slowmem as slowmem_                           # sim/slowmem.py: numpy only at the top
        lay = json.loads(str(P["slow"]))
        P["_slow"] = (lay, {k[len("slow."):]: np.asarray(v, np.float32) for k, v in P.items() if k.startswith("slow.")}, slowmem_.np_step,
                      slowmem_.width(lay))
    return P, A


def width(P):
    """the width of a seat's memory array: the fast memory, or the whole state with the slow memory (sim/slowmem.py)"""
    return P["_slow"][3] if "_slow" in P else P["whh"].shape[1]


def describe(P, A):
    """a line for the server's log: what was loaded"""
    if "attn" not in P:
        return "no attention part"
    lay = json.loads(str(P["attn"]))
    if A is None:
        return "attention part of {} tokens with its door shut (skipped)".format(lay["tokens"])
    return "attention part of {} tokens, door open (mean size of its weights {:.5f})".format(lay["tokens"], float(np.abs(A[1]["door.weight"]).mean()))


def step(P, A, obs, h, rng):
    """one frame for B players: obs [B, inputs] as the simulator's observe() gives them, h [B, memory]. Returns the
    choices [B, outputs] (sampled, as in training; one random number per player and output from rng, a numpy Generator)
    and the new memory."""
    hf = h                                                   # (--slow-mem) the whole state; h its fast part
    if "_slow" in P:
        h = hf[:, :P["whh"].shape[1]]
    mean = P["obs_mean"]
    if obs.shape[1] > len(mean):                             # an older network in a simulator with more inputs: they are appended at the end
        obs = obs[:, :len(mean)]
    x = np.clip((obs - mean) / np.sqrt(P["obs_var"] + 1e-8), -10, 10).astype(np.float32)
    xa = x
    if "cell" in P:                                          # the learned map (v8): the last two inputs are cell numbers
        ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(P["cell"]) - 1)
        x = np.concatenate([x[:, :-2], P["cell"][ids[:, 0]], P["cell"][ids[:, 1]]], 1)
    x = np.tanh(x @ P["w0"].T + P["b0"])
    x = np.tanh(x @ P["w1"].T + P["b1"])
    if A is not None:                                        # (v0.2) what the door lets through of the tokens
        x = x + A[2](A[0], A[1], xa)
    gi = x @ P["wih"].T + P["bih"]
    gh = h @ P["whh"].T + P["bhh"]
    H = h.shape[1]
    r = sig(gi[:, :H] + gh[:, :H])
    z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
    nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    h = ((1 - z) * nn_ + z * h).astype(np.float32)
    zo = h
    if "_slow" in P:                                         # (--slow-mem) the outputs read h + door(s); the slow GRU ticks on its frames
        zo, h = P["_slow"][2](P["_slow"][1], P["_slow"][0], x, h, hf)
    logits = zo @ P["wp"].T + P["bp"]
    dims = [int(d) for d in P["action_dims"]]
    out = np.zeros((len(obs), len(dims)), np.int64)
    i = 0
    for j, d in enumerate(dims):
        l = logits[:, i:i + d]
        p = np.exp(l - l.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        out[:, j] = (p.cumsum(1) > rng.random((len(p), 1))).argmax(1)
        i += d
    return out, h

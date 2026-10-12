"""A network of an older simulator made a network of the simulator with WAYS (stage B part 3, sim/duel_env.py: a
thirteenth output, his way to his target, and the 7 inputs of N_B3), and where the new choice starts.

    python tools/ways_init.py never <file.pt> [<file.pt> ...]      (in place: the control, the league's files)
    python tools/ways_init.py open <in.pt> <out.pt> [--share 0.1]  (the learner)

What both do first (widen): the inputs are widened to the simulator's (new inputs are its last: zero weight in the old
encoder, mean 0 and spread 1 in the input statistics); a network with an attention part gets the token the new inputs
make (kind "ways": tools/targets_init.py's widen_attn, the layout cut anew from the input list, --inputs, default
docs/INPUTS.csv; its gate shut: `python tools/targets_init.py gate <file> 0 kind=ways` opens it); the output layer gets
three more rows at its end, the way: zero weight, so the choice does not depend on anything yet, and a bias.
The network must have the simulator's other outputs already (the seventeen intentions of TARGETS:
tools/targets_init.py first; it also widens the inputs, this tool then only adds the output).

never:  the second and the third way with a bias that is never taken: the network answers as before
        (`python sim/add_attention.py --same old.pt new.pt` proves it) and always goes the shortest way.
open:   the second and the third way each get --share of the readings (0.1: the shortest 80%), in every state: a bias
        alone, log(share / (1 - 2 share)) against the shortest's 0. Which way where is his to find.
Every file of a run must be converted (the trainer builds the league's networks in the learner's shape).

WAYS_ENV: the simulator's module (default duel_env_ffa). QLBOT_ROOT: the repo, when this file is run from a copy."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
NEVER = -20.0
MODULE = os.environ.get("WAYS_ENV") or os.environ.get("TARGETS_ENV") or "duel_env_ffa"


def _env():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"               # (no graphics card: an empty value does not hide it on Windows)
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    for d_ in (SIM, HERE):
        if d_ not in sys.path:
            sys.path.insert(0, d_)
    import importlib
    return importlib.import_module(MODULE)


def widen(ck, E, bias, inputs=None, seed=0):
    """the checkpoint with the simulator's inputs (new ones at zero weight), the tokens they make (their gate shut) and
    the way among its outputs: zero weight, the shortest at 0, the second and the third at `bias`.
    -> (new inputs, new kinds of token, the output was added)"""
    import numpy as np
    import torch
    sd = ck["model"]
    W = E.WAY_HEAD
    old, new = [int(x) for x in ck["action_dims"]], [int(x) for x in E.ACTION_DIMS]
    assert old[:W] == new[:W], "its outputs {} are not the simulator's first {} (the intentions of TARGETS: tools/targets_init.py first)".format(old, new[:W])
    assert len(old) in (W, W + 1) and (len(old) == W or old == new), (old, new)
    extra = E.OBS_DIM - sd["enc.0.weight"].shape[1]
    assert extra >= 0, "the network has {} inputs, the simulator {}".format(sd["enc.0.weight"].shape[1], E.OBS_DIM)
    if extra:
        sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], extra, dtype=sd["enc.0.weight"].dtype)], 1)
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)])
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)])
        ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None and ck["attn"]["obs_dim"] != E.OBS_DIM:
        import targets_init as TI
        inputs = inputs or os.path.join(os.path.dirname(HERE), "docs", "INPUTS.csv")
        fresh = TI.widen_attn(ck, inputs, seed)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM, "the input list {} has {} inputs, the simulator {}".format(inputs, ck["attn"]["obs_dim"], E.OBS_DIM)
    added = len(old) == W
    if added:
        w, b = sd["pi.weight"], sd["pi.bias"]
        assert w.shape[0] == sum(old), (w.shape, old)
        sd["pi.weight"] = torch.cat([w, torch.zeros(E.N_WAYS, w.shape[1], dtype=w.dtype)], 0)
        sd["pi.bias"] = torch.cat([b, torch.zeros(E.N_WAYS, dtype=b.dtype)])
        ck["action_dims"] = tuple(new)
    o = sum(new[:W])
    assert sd["pi.weight"].shape[0] == o + E.N_WAYS
    with torch.no_grad():
        sd["pi.weight"][o:] = 0.0
        sd["pi.bias"][o] = 0.0
        sd["pi.bias"][o + 1:] = float(bias)
    return extra, fresh, added


def say(what, f, ck, extra, fresh, added):
    at = ck.get("attn")
    print("{}: {} ({} inputs, {} new; outputs {}{}{})".format(
        what, f, ck["model"]["enc.0.weight"].shape[1], extra, tuple(ck["action_dims"]), ", the way added" if added else "",
        "" if at is None else "; {} tokens{}".format(at["tokens"] - 1, ", new and shut: " + ", ".join(fresh) if fresh else "")))


def never(files, inputs):
    E = _env()
    import torch
    torch.set_num_threads(1)
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        extra, fresh, added = widen(ck, E, NEVER, inputs)
        ck["ways_init"] = dict(share=0.0, bias=NEVER)
        torch.save(ck, f)
        say("always the shortest way", f, ck, extra, fresh, added)


def open_(policy, out, share, inputs):
    assert 0.0 < share < 0.5, share
    E = _env()
    import torch
    torch.set_num_threads(1)
    ck = torch.load(policy, weights_only=False, map_location="cpu")
    bias = math.log(share / (1.0 - (E.N_WAYS - 1) * share))
    extra, fresh, added = widen(ck, E, bias, inputs)
    ck["ways_init"] = dict(share=share, bias=bias)
    torch.save(ck, out)
    say("the ways opened", out, ck, extra, fresh, added)
    z = [1.0] + [math.exp(bias)] * (E.N_WAYS - 1)
    print("  the second and the third way: a bias of {:.3f} each, the shortest 0: {} of the readings in every state".format(
        bias, " / ".join("{:.1%}".format(x / sum(z)) for x in z)))


if __name__ == "__main__":
    args = sys.argv[1:]
    inputs = None
    if "--inputs" in args:
        i = args.index("--inputs")
        inputs = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    if args[0] == "never":
        never(args[1:], inputs)
    elif args[0] == "open":
        share = 0.1
        if "--share" in args:
            i = args.index("--share")
            share = float(args[i + 1])
            del args[i:i + 2]
        open_(args[1], args[2], share, inputs)
    else:
        sys.exit(__doc__)

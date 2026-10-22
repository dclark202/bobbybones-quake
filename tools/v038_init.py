"""v0.3.8 (DRIFT_IN, sim/duel_env.py): a network of v0.3.7's shape (864 inputs in the group module) made a network of the
simulator with the drift inputs (868), the new part closed: it answers as before.

    python tools/v038_init.py widen <in.pt> <out.pt>                 (a new file)
    python tools/v038_init.py league <file.pt> [<file.pt> ...]       (in place: the control, the league's files)
    python tools/v038_init.py same <old.pt> <new.pt>                 the two answer alike (numpy, random inputs; exit 1 if not)
    python tools/v038_init.py opt <old.pt> <old opt.pt> <new.pt> <new opt.pt> [--fill median|zero]

widen / league: the N_DRIFT (4) new inputs (the group "v038 drift", at the end) get zero weight in the old encoder and mean 0,
spread 1 in the input statistics; the attention part gets their token (the kind "drift", one token, after every older kind:
sim/attn.py's LATE2; tools/targets_init.py's widen_attn) with its gate shut (attn.GATE_SHUT): nothing looks at it and the
encoder does not read it. Nothing else is touched. A file already of the new shape is left as it is. `same` and `opt` are
tools/v036_init.py's (the same numpy check; the optimizer's state laid out by name and token kind).
Run it with the Anaconda Python; V036_ENV: the simulator module (default duel_env_ffa, the run's)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v036_init as V6                                       # noqa: E402  (its _env, say, main_same, main_opt)

NEW_KINDS = ["drift"]


def widen(ck, E):
    """the checkpoint (in place) with the drift inputs and their token shut; returns (inputs added, kinds added)"""
    import numpy as np
    import torch
    import targets_init as TI
    sd = ck["model"]
    old_n = int(sd["enc.0.weight"].shape[1])
    extra = E.OBS_DIM - old_n
    assert extra in (0, E.N_DRIFT), "the network has {} inputs, the simulator {} (this converter adds the {} of N_DRIFT only)".format(
        old_n, E.OBS_DIM, E.N_DRIFT)
    if extra == 0:
        assert ck.get("attn") is None or ck["attn"]["obs_dim"] == E.OBS_DIM
        return 0, []
    W = sd["enc.0.weight"]
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
    ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)]).astype(np.asarray(ck["obs_mean"]).dtype)
    ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)]).astype(np.asarray(ck["obs_var"]).dtype)
    ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None:
        assert ck["attn"]["obs_dim"] == old_n, (ck["attn"]["obs_dim"], old_n)
        fresh = TI.widen_attn(ck, V6.INPUTS)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == NEW_KINDS, (ck["attn"]["obs_dim"], fresh)
    ck["v038_init"] = dict(inputs_added=int(extra), tokens_added=fresh, gate="shut ({})".format(-30.0))
    return extra, fresh


def main_widen(src, dst):
    E = V6._env()
    import torch
    torch.set_num_threads(1)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    r = widen(ck, E)
    torch.save(ck, dst)
    V6.say("widened", dst, ck, *r)


def main_league(files):
    E = V6._env()
    import torch
    torch.set_num_threads(1)
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        r = widen(ck, E)
        if r[0]:
            torch.save(ck, f)
        V6.say("league" if r[0] else "left as it is", f, ck, *r)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "widen":
        main_widen(args[1], args[2])
    elif args[0] == "league":
        main_league(args[1:])
    elif args[0] == "same":
        sys.exit(0 if V6.main_same(args[1], args[2]) else 1)
    elif args[0] == "opt":
        fl_ = args[args.index("--fill") + 1] if "--fill" in args else "median"
        V6.main_opt(args[1], args[2], args[3], args[4], fill=fl_)
    else:
        sys.exit(__doc__)

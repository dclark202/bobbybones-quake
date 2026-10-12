"""A network of an older simulator made a network of the simulator with TARGETS (sim/duel_env.py: eight more intentions,
"place 1" to "place 8", and the 64 inputs of N_B2), and where the new choices start.

    python tools/targets_init.py never <file.pt> [<file.pt> ...]       (in place: the control, the league's files)
    python tools/targets_init.py collect <policy.pt> <map> <out.npz>   (a map a process; Anaconda Python)
    python tools/targets_init.py open <in.pt> <out.pt> [--share 0.05] [<npz> ...]
    python tools/targets_init.py gate <file.pt> <value> [kind=hold]    (in place: an attention network's new tokens)

What every one of them does first (widen): the inputs are widened to the simulator's (new inputs are its last: zero
weight in the old encoder, mean 0 and spread 1 in the input statistics), the intention gets its new choices (zero
weight, a bias), and a network with an attention part (v0.2: sim/attn.py) gets the tokens the new inputs make: the
layout is cut anew from the input list (--inputs, default docs/INPUTS.csv), a kind of token the network has keeps its
first layer and its marks, a new kind gets a fresh first layer and fresh marks, and the network gets a "gate" (a number
a token among its weights, sim/attn.py) that is shut for the new tokens (attn.GATE_SHUT: nothing looks at them, so the
attention part gives what it gave). With the new choices at "never" the network answers as before:
`python sim/add_attention.py --same old.pt new.pt` proves it. Every file of a run must be converted (the trainer
builds the league's networks in the learner's shape); each keeps its own gate.

never:   the eight places with a bias that is never taken.
open:    the eight places share about --share of the intention's probability in an average state, evenly: only a bias
         (no fit: where he goes is his to find; the item rule's lesson leaves the places alone). The bias is solved so
         that the mean share over the states of `collect` is --share; without such files, from the old choices' biases
         alone (said so: it is then right only where his memory says little).
collect: the network plays itself in games; at one frame in TARGETS_KEEP (12) a living player's memory gives what his
         old choices weigh together (the log of the sum of their exponentials). TARGETS_GAMES (24), TARGETS_MINUTES (6).
gate:    the gate of a kind's tokens (0: looked at as any token). Opening it changes his answers a little at once: do it
         at a run's start, or let the trainer raise it step by step.

TARGETS_ENV: the simulator's module (default duel_env_ffa). QLBOT_ROOT: the repo, when this file is run from a copy."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
NEVER = -20.0
MODULE = os.environ.get("TARGETS_ENV") or "duel_env_ffa"


def _env():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"               # (no graphics card: an empty value does not hide it on Windows)
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    if SIM not in sys.path:
        sys.path.insert(0, SIM)
    import importlib
    return importlib.import_module(MODULE)


def widen_attn(ck, inputs, seed=0):
    """the attention part's tokens cut anew from the input list; returns the names of the kinds that are new"""
    import numpy as np
    import torch
    import attn as A
    old = ck["attn"]
    new = A.layout_from_csv(inputs)
    assert new["D"] == old["D"] and new["heads"] == old["heads"]
    sd = ck["model"]
    names_old = [k["name"] for k in old["kinds"]]
    row_old, r = {}, 0                                        # a kind's first row among the old tokens
    for k in old["kinds"]:
        row_old[k["name"]] = r
        r += len(k["idx"])
    assert r == old["tokens"] - 1 and tuple(sd["attn.mark"].shape) == (old["tokens"], old["D"])
    g = torch.Generator().manual_seed(1000 + seed)
    emb, marks, gate, fresh = {}, [], [], []
    gate_old = [float(x) for x in sd["attn.gate"]] if old.get("gated") else None
    for i, k in enumerate(new["kinds"]):
        if k["name"] in names_old:
            j = names_old.index(k["name"])
            assert old["kinds"][j]["idx"] == k["idx"], "the tokens of kind '{}' are not the network's: {} -> {}".format(
                k["name"], np.shape(old["kinds"][j]["idx"]), np.shape(k["idx"]))
            emb[i] = sd["attn.emb.{}.weight".format(j)]
            r0 = row_old[k["name"]]
            marks.append(sd["attn.mark"][r0:r0 + len(k["idx"])])
            gate += [0.0] * len(k["idx"]) if gate_old is None else [float(x) for x in gate_old[r0:r0 + len(k["idx"])]]
        else:                                                 # a new kind: a first layer and marks as sim/attn.py starts them, its gate shut
            w = len(k["idx"][0])
            emb[i] = (torch.randn((old["D"], w), generator=g) / max(1.0, w) ** 0.5).to(sd["attn.mark"].dtype)
            marks.append((torch.randn((len(k["idx"]), old["D"]), generator=g) * 0.1).to(sd["attn.mark"].dtype))
            gate += [A.GATE_SHUT] * len(k["idx"])
            fresh.append(k["name"])
    assert set(names_old) <= {k["name"] for k in new["kinds"]}, "a kind of token is gone"
    marks.append(sd["attn.mark"][-1:])                        # the summary token
    gate.append(0.0 if gate_old is None else float(gate_old[-1]))
    for key in [key for key in sd if key.startswith("attn.emb.")]:
        del sd[key]
    for i in sorted(emb):
        sd["attn.emb.{}.weight".format(i)] = emb[i]
    sd["attn.mark"] = torch.cat(marks, 0)
    assert tuple(sd["attn.mark"].shape) == (new["tokens"], new["D"]) and len(gate) == new["tokens"]
    new["gated"] = True
    sd["attn.gate"] = torch.tensor(gate, dtype=sd["attn.mark"].dtype)
    ck["attn"] = new
    return fresh


def widen(ck, E, bias=NEVER, inputs=None, seed=0):
    """the checkpoint with the simulator's inputs (new ones at zero weight), the intention's new choices (zero weight,
    the bias given) and, where it has an attention part, the new inputs' tokens (their gate shut)"""
    import numpy as np
    import torch
    sd = ck["model"]
    extra = E.OBS_DIM - sd["enc.0.weight"].shape[1]
    assert extra >= 0, "the network has {} inputs, the simulator {}".format(sd["enc.0.weight"].shape[1], E.OBS_DIM)
    if extra:
        sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], extra, dtype=sd["enc.0.weight"].dtype)], 1)
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), np.zeros(extra)])
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), np.ones(extra)])
        ck["obs_dim"] = E.OBS_DIM
    old = [int(x) for x in ck["action_dims"]]
    new = [int(x) for x in E.ACTION_DIMS][:len(old)]         # (the simulator's outputs after his own, the way of stage B part 3: tools/ways_init.py)
    I = E.INTENT_HEAD
    if old != new:
        assert len(old) == len(new) and old[:I] == new[:I] and old[I + 1:] == new[I + 1:] and old[I] < new[I], (old, new)
        o, more = sum(old[:I]) + old[I], new[I] - old[I]      # where the new choices' rows go
        w, b = sd["pi.weight"], sd["pi.bias"]
        sd["pi.weight"] = torch.cat([w[:o], torch.zeros(more, w.shape[1], dtype=w.dtype), w[o:]], 0)
        sd["pi.bias"] = torch.cat([b[:o], torch.full((more,), NEVER, dtype=b.dtype), b[o:]])
        ck["action_dims"] = tuple(new)
    o = sum(new[:I]) + E.HOLD_INTENT
    with torch.no_grad():
        sd["pi.weight"][o:o + E.HOLD_SLOTS] = 0.0
        sd["pi.bias"][o:o + E.HOLD_SLOTS] = float(bias)
    fresh = []
    if ck.get("attn") is not None and ck["attn"]["obs_dim"] != E.OBS_DIM:
        inputs = inputs or os.path.join(os.path.dirname(HERE), "docs", "INPUTS.csv")
        fresh = widen_attn(ck, inputs, seed)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM, "the input list {} has {} inputs, the simulator {}".format(inputs, ck["attn"]["obs_dim"], E.OBS_DIM)
    return extra, fresh


def say(what, f, ck, extra, fresh):
    at = ck.get("attn")
    print("{}: {} ({} inputs, {} new; outputs {}{})".format(
        what, f, ck["model"]["enc.0.weight"].shape[1], extra, tuple(ck["action_dims"]),
        "" if at is None else "; {} tokens{}".format(at["tokens"] - 1, ", new and shut: " + ", ".join(fresh) if fresh else "")))


def never(files, inputs):
    E = _env()
    import torch
    torch.set_num_threads(1)
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        extra, fresh = widen(ck, E, NEVER, inputs)
        torch.save(ck, f)
        say("never a holding place", f, ck, extra, fresh)


def collect(policy, mapname, out):
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    E = _env()
    import numpy as np
    import test_suite as T_
    pol = T_.Policy(policy, seed=3)
    n_in = len(pol.mean)
    o10 = sum(pol.dims[:E.INTENT_HEAD])
    d10 = min(pol.dims[E.INTENT_HEAD], E.HOLD_INTENT)        # his choices before the places
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"), n_matches=int(os.environ.get("TARGETS_GAMES", "24")), seed=33, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)), close_p=0.0)
    env.react_frames = round(pol.react_ms / 25)
    env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.item_run_p = env.jump_run_p = 0.0                    # games only
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    frames = int(float(os.environ.get("TARGETS_MINUTES", "6")) * 60 / E.DT)
    every = int(os.environ.get("TARGETS_KEEP", "12"))
    C, N0 = [], []
    for t in range(frames):
        al, h = pol.act(obs[:, :n_in], h)
        keep = ((t + np.arange(n)) % every == 0) & (env.script == 0) & (env.hp > 0)
        lg = h[keep] @ pol.wp[o10:o10 + d10].T + pol.bp[o10:o10 + d10]
        C.append((lg.max(1) + np.log(np.exp(lg - lg.max(1, keepdims=True)).sum(1))).astype(np.float32))    # what his old choices weigh together
        N0.append(lg[:, 0].astype(np.float32))                # ... and "nothing" alone
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a[:, :al.shape[1]] = al
        obs, r, d, info = env.step(a)
        h[np.asarray(d) > 0] = 0.0
    c, n0 = np.concatenate(C), np.concatenate(N0)
    np.savez_compressed(out, c=c, nothing=n0)
    print("{}: {} states kept; his old choices weigh {:.2f} together on average (from {:.2f} to {:.2f}); 'nothing' has {:.1%} of it".format(
        mapname, len(c), float(c.mean()), float(c.min()), float(c.max()), float(np.exp(n0 - c).mean())), flush=True)


def open_(policy, out, share, files, inputs):
    E = _env()
    import numpy as np
    import torch
    torch.set_num_threads(1)
    ck = torch.load(policy, weights_only=False, map_location="cpu")
    extra, fresh = widen(ck, E, NEVER, inputs)
    sd = ck["model"]
    I = E.INTENT_HEAD
    o = sum(E.ACTION_DIMS[:I])
    if files:
        c = np.concatenate([np.load(f)["c"] for f in files]).astype(np.float64)
        src = "{} states of {} files".format(len(c), len(files))
    else:
        b_ = sd["pi.bias"][o:o + E.HOLD_INTENT].double().numpy()
        c = np.array([b_.max() + np.log(np.exp(b_ - b_.max()).sum())])
        src = "the old choices' biases alone (no states given: right only where his memory says little)"
    lo, hi = -40.0, 40.0                                      # the bias at which the eight places' mean share is the one asked for
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float((1.0 / (1.0 + np.exp(c - mid - np.log(E.HOLD_SLOTS)))).mean()) < share:
            lo = mid
        else:
            hi = mid
    bias = 0.5 * (lo + hi)
    got = 1.0 / (1.0 + np.exp(c - bias - np.log(E.HOLD_SLOTS)))
    with torch.no_grad():
        sd["pi.bias"][o + E.HOLD_INTENT:o + E.HOLD_INTENT + E.HOLD_SLOTS] = float(bias)
    ck["targets_init"] = dict(share=share, bias=float(bias), states=int(len(c)), source=src)
    torch.save(ck, out)
    say("the holding places opened", out, ck, extra, fresh)
    print("  each place's bias {:.3f}: the eight together have {:.1%} of his intention on average over {} (a tenth of the states under {:.1%}, a tenth over {:.1%})".format(
        bias, float(got.mean()), src, float(np.percentile(got, 10)), float(np.percentile(got, 90))))


def gate(f, value, kind):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import torch
    torch.set_num_threads(1)
    ck = torch.load(f, weights_only=False, map_location="cpu")
    at = ck.get("attn")
    assert at is not None and at.get("gated"), f + " has no attention part with a gate (tools/targets_init.py never / open make one)"
    r, hit = 0, 0
    for k in at["kinds"]:
        if k["name"] == kind:
            ck["model"]["attn.gate"][r:r + len(k["idx"])] = float(value)
            hit = len(k["idx"])
        r += len(k["idx"])
    assert hit, "no tokens of kind " + kind
    torch.save(ck, f)
    print("{}: the gate of the {} '{}' tokens is {:g}".format(f, hit, kind, float(value)))


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
    elif args[0] == "collect":
        collect(args[1], args[2], args[3])
    elif args[0] == "open":
        share = 0.05
        if "--share" in args:
            i = args.index("--share")
            share = float(args[i + 1])
            del args[i:i + 2]
        open_(args[1], args[2], share, args[3:], inputs)
    elif args[0] == "gate":
        gate(args[1], float(args[2]), dict(x.split("=", 1) for x in args[3:]).get("kind", "hold"))
    else:
        sys.exit(__doc__)

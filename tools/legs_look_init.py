"""v0.3.2: carry a network of v0.3.1's shape over to legs with the inputs of a look point (duel_env's LEGS_LOOK, the movement
network's three inputs of stage C part 2: movement_env.N_C2) and to his turn correction on his legs (LEGS_TURN_ADD).

    python tools/legs_look_init.py <in.pt> <out.pt> --legs move_v17_look [--own-legs] [--old-legs move_v15n_ql] [--set NAME=VALUE ...]

Nothing but these two parts is touched (every other tensor and every other key of the checkpoint is copied as it is):
  - his turn correction: the fourteenth output (13 choices, the first of them 0) is added shut: its weights 0, the bias
    of "0" at duel_env's TA_SHUT over the others, so another choice is drawn with the chance e^-20 (action_dims gets it).
    A network that has it already keeps its own.
  - his legs' branch (legs.0, legs.2, legs.4):
      without --own-legs: the weights of --legs's policy.npz (the start of a run: the new legs inside him);
      with --own-legs: his own branch, widened to the new legs' inputs (the three new ones at zero weight), with the change
      of the input statistics folded into its first layer: the simulator normalises the legs' inputs by the new legs'
      statistics (their policy.npz), and his branch learnt on --old-legs's; w x_old + b = (w s_new/s_old) x_new +
      w (m_new - m_old)/s_old + b, exact up to the cut at +-10 (the control and the league's files: their own legs).
The input file is only read. `same` proves what it says on recorded inputs:

    python tools/legs_look_init.py same <a.pt> <b.pt> --obs <npz: obs [frames, players, inputs]> [--legs-x <npz: legs_x [.., 64]>]
        (b against a: his own outputs, the value, the correction's chance of not 0; with --legs-x and --own-legs as above,
        the branch's logits of b on the new legs' inputs against a's on the same inputs in the old statistics)
"""
import argparse
import math
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
N_TA = 13                                                    # (duel_env's TA_BINS: 0, then -0.5 .. 15; not imported: that module loads the simulator)
TA_SHUT = 20.0 + math.log(N_TA - 1)                          # (duel_env's TA_SHUT)
OLD_DIMS = (3, 3, 3, 23, 15, 2, 10, 2, 2, 2, 17, 2, 3)       # v0.3.1's thirteen outputs
LEGS_KEYS = ("legs.0.weight", "legs.0.bias", "legs.2.weight", "legs.2.bias", "legs.4.weight", "legs.4.bias")


def legs_npz(run):
    return np.load(os.path.join(ROOT, "data", "sim_runs", run, "policy.npz"))


def convert(a):
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = dict(ck["model"])
    dims = tuple(int(d) for d in ck["action_dims"])
    said = []
    if len(dims) == len(OLD_DIMS):                            # his turn correction, shut
        assert dims == OLD_DIMS, "not v0.3.1's outputs: {}".format(dims)
        w, b = sd["pi.weight"], sd["pi.bias"]
        assert w.shape[0] == sum(dims)
        bt = torch.zeros(N_TA, dtype=b.dtype)
        bt[0] = TA_SHUT
        sd["pi.weight"] = torch.cat([w, w.new_zeros(N_TA, w.shape[1])], 0)
        sd["pi.bias"] = torch.cat([b, bt], 0)
        ck["action_dims"] = dims + (N_TA,)
        said.append("turn correction added shut (bias of 0 {:.3f} over the others, weights 0)".format(TA_SHUT))
    else:
        assert len(dims) == len(OLD_DIMS) + 1 and dims[-1] == N_TA, "outputs {}".format(dims)
        said.append("turn correction kept as it is")
    z = legs_npz(a.legs)
    d_new = int(z["w0"].shape[1])
    if not a.own_legs:                                        # the new legs inside him
        for k_, n_ in zip(LEGS_KEYS, ("w0", "b0", "w1", "b1", "wp", "bp")):
            assert k_ in sd, "no legs branch in the input ({}): LEGS_IN networks only".format(k_)
            assert tuple(sd[k_].shape)[1:] == tuple(z[n_].shape)[1:] or k_ == "legs.0.weight", (k_, sd[k_].shape, z[n_].shape)
            sd[k_] = torch.from_numpy(np.ascontiguousarray(z[n_])).to(sd[k_].dtype)
        said.append("legs branch = {}'s weights ({} inputs)".format(a.legs, d_new))
    else:                                                     # his own legs, in the new legs' statistics
        zo = legs_npz(a.old_legs)
        w0 = sd["legs.0.weight"].double().numpy()
        b0 = sd["legs.0.bias"].double().numpy()
        d_old = w0.shape[1]
        assert d_old <= d_new and d_old == int(zo["w0"].shape[1]), (d_old, d_new, zo["w0"].shape)
        m1, s1 = zo["obs_mean"].astype(np.float64), np.sqrt(zo["obs_var"].astype(np.float64) + 1e-8)
        m2, s2 = z["obs_mean"][:d_old].astype(np.float64), np.sqrt(z["obs_var"][:d_old].astype(np.float64) + 1e-8)
        w_ = w0 * (s2 / s1)[None, :]
        b_ = b0 + w0 @ ((m2 - m1) / s1)
        w_ = np.concatenate([w_, np.zeros((w_.shape[0], d_new - d_old))], 1)
        sd["legs.0.weight"] = torch.from_numpy(w_).to(sd["legs.0.weight"].dtype)
        sd["legs.0.bias"] = torch.from_numpy(b_).to(sd["legs.0.bias"].dtype)
        said.append("own legs kept: {} -> {} inputs, statistics of {} folded into the first layer (largest change of a scale "
                    "{:.4f}, of a mean {:.4f} in sd)".format(d_old, d_new, a.legs, float(np.abs(s2 / s1 - 1).max()),
                                                             float(np.abs((m2 - m1) / s1).max())))
    ck["model"] = sd
    ev = dict(ck.get("env_vars") or {})
    ev.update(dict(x.split("=", 1) for x in a.set))
    ck["env_vars"] = ev
    ck["legs_look_init"] = dict(src=os.path.basename(a.inp), legs=a.legs, own=bool(a.own_legs), old_legs=a.old_legs if a.own_legs else None)
    assert not os.path.exists(a.out), "there is a file at " + a.out
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    torch.save(ck, a.out)
    print("{} -> {}: {}".format(a.inp, a.out, "; ".join(said)))


def same(a):
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    from test_suite import Policy                            # (numpy: the checks' own forward pass)
    pa, pb = Policy(a.a, seed=7), Policy(a.b, seed=7)
    n_old = len(pa.dims)
    pb.dims = pb.dims[:n_old]                                # (b drawn on a's outputs alone: the same random numbers frame by frame)
    obs = np.load(a.obs)["obs"].astype(np.float32)           # [frames, players, inputs]: his own inputs, frame by frame
    ha, hb = pa.zeros(obs.shape[1]), pb.zeros(obs.shape[1])
    diff = 0
    for t in range(len(obs)):
        aa, ha = pa.act(obs[t], ha)
        ab, hb = pb.act(obs[t], hb)
        diff += int((aa != ab).sum())
    out = dict(frames=len(obs), players=obs.shape[1], choices_differ=diff, memory_max_diff=float(np.abs(ha - hb).max()))
    o_ = int(sum(pa.dims))
    if pb.wp.shape[0] > o_:                                  # the correction's logits: its bias alone while its weights are 0
        b_ = pb.bp[o_:].astype(np.float64)
        p_ = np.exp(b_ - b_.max())
        p_ /= p_.sum()
        out.update(correction_weights_max=float(np.abs(pb.wp[o_:]).max()), correction_not0=float(1.0 - p_[0]))
    if a.legs_x:
        zx_ = np.load(a.legs_x)
        x2 = zx_["legs_x" if "legs_x" in zx_.files else "x"].astype(np.float32).reshape(-1, pb.legsP[0].shape[1])   # the legs' inputs (new statistics)
        x2 = x2[np.abs(x2).sum(1) > 0]                       # (rows with a way)
        z, zo = legs_npz(a.legs), legs_npz(a.old_legs)
        d_old = pa.legsP[0].shape[1]
        m1, s1 = zo["obs_mean"], np.sqrt(zo["obs_var"] + 1e-8)
        m2, s2 = z["obs_mean"][:d_old], np.sqrt(z["obs_var"][:d_old] + 1e-8)
        x1 = np.clip((x2[:, :d_old] * s2 + m2 - m1) / s1, -10, 10).astype(np.float32)      # the same inputs in the old statistics
        g_a, g_b = pa.legs_logits(x1), pb.legs_logits(x2)
        out.update(legs_rows=len(x2), legs_logits_max_diff=float(np.abs(g_a - g_b).max()),
                   legs_best_same=float(np.mean([(g_a[:, o:o + k].argmax(1) == g_b[:, o:o + k].argmax(1)).mean()
                                                 for o, k in ((0, 3), (3, 3), (6, 2), (8, 9))])))
    print(out)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "same":
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd")
        ap.add_argument("a")
        ap.add_argument("b")
        ap.add_argument("--obs", required=True)
        ap.add_argument("--legs-x", default="")
        ap.add_argument("--legs", default="move_v17_look")
        ap.add_argument("--old-legs", default="move_v15n_ql")
        same(ap.parse_args())
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--legs", required=True, help="the new legs' run (its policy.npz: weights and input statistics)")
    ap.add_argument("--own-legs", action="store_true", help="keep his own branch (widened, the statistics folded in)")
    ap.add_argument("--old-legs", default="move_v15n_ql", help="the legs whose input statistics his own branch learnt with")
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE into the checkpoint's env_vars")
    convert(ap.parse_args())


if __name__ == "__main__":
    main()

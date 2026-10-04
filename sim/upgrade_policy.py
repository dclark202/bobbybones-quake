"""Widen a duel_gru_v3 network (171 inputs, 7 action heads) to the current simulator without losing its skills.

    python sim/upgrade_policy.py --src duel_gru_v3 --dst duel_gru_v4

New inputs are appended at the end of the observation and get zero weights, so the widened network behaves
exactly as before until training starts using them. New actions: the jump choice becomes none / jump / crouch
(crouch starts very unlikely) and a walk choice is added (starts mostly off). The league snapshots are widened
the same way. Then train with:  python sim/train_duel_rnn.py --run <dst> --resume ...
"""
import argparse
import glob
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OLD_DIMS = (3, 3, 2, 23, 15, 2, 10)


def widen(ck, obs_dim, action_dims):
    sd = ck["model"]
    old_obs = sd["enc.0.weight"].shape[1]
    assert tuple(ck["action_dims"]) == OLD_DIMS and old_obs <= obs_dim, (ck["action_dims"], old_obs)
    extra = obs_dim - old_obs
    sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], extra)], 1)
    w, b = sd["pi.weight"], sd["pi.bias"]
    H = w.shape[1]
    j1 = sum(OLD_DIMS[:3])                                   # end of the jump head
    zero = torch.zeros(1, H, dtype=w.dtype)
    # crouch: a new option in the vertical head; walk: a new head at the end (off / on)
    sd["pi.weight"] = torch.cat([w[:j1], zero, w[j1:], zero, zero], 0)
    sd["pi.bias"] = torch.cat([b[:j1], (b[j1 - 2:j1].min() - 3.0).reshape(1), b[j1:],
                               torch.tensor([1.5, -1.5], dtype=b.dtype)])
    assert sd["pi.weight"].shape[0] == sum(action_dims)
    ck["obs_mean"] = np.concatenate([ck["obs_mean"], np.zeros(extra)])
    ck["obs_var"] = np.concatenate([ck["obs_var"], np.ones(extra)])
    ck["obs_count"] = 1e6                                    # let the statistics of the new inputs settle quickly
    ck["obs_dim"], ck["action_dims"], ck["widened_from"] = obs_dim, tuple(action_dims), old_obs
    return ck


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    a = ap.parse_args()
    import duel_env as E
    src = os.path.join(ROOT, "data", "sim_runs", a.src)
    dst = os.path.join(ROOT, "data", "sim_runs", a.dst)
    os.makedirs(os.path.join(dst, "snapshots"), exist_ok=True)
    files = [("policy.pt", "policy.pt")] + [(os.path.join("snapshots", os.path.basename(f)),) * 2
                                            for f in sorted(glob.glob(os.path.join(src, "snapshots", "snap_*.pt")))[-8:]]
    for f_in, f_out in files:
        ck = torch.load(os.path.join(src, f_in), weights_only=False, map_location="cpu")
        torch.save(widen(ck, E.OBS_DIM, E.ACTION_DIMS), os.path.join(dst, f_out))
    print("widened {} file(s): {} -> {} inputs, actions {} -> {}".format(len(files), ck["widened_from"], E.OBS_DIM,
                                                                        OLD_DIMS, E.ACTION_DIMS))


if __name__ == "__main__":
    main()

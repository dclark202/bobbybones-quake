"""Widen a run's network in place to the simulator's current number of inputs. New inputs are appended at the end
and get zero weights, so the network behaves exactly as before until training starts using them. The policy and
the league snapshots are widened; the originals are kept as *.before_widen.

    python sim/widen_obs.py --run duel_gru_v5
"""
import argparse
import glob
import os
import shutil
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    import duel_env as E
    d = os.path.join(ROOT, "data", "sim_runs", a.run)
    files = [os.path.join(d, "policy.pt")] + sorted(glob.glob(os.path.join(d, "snapshots", "snap_*.pt")))
    n = 0
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        sd = ck["model"] if "model" in ck else ck
        old = sd["enc.0.weight"].shape[1]
        extra = E.OBS_DIM - old
        if extra <= 0 and sd["pi.weight"].shape[0] >= sum(E.ACTION_DIMS):
            continue
        shutil.copy(f, f + ".before_widen")
        sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], extra,
                                                                         dtype=sd["enc.0.weight"].dtype)], 1)
        # new action heads (appended): zero weights, and a bias that starts them almost always "off"
        have = sd["pi.weight"].shape[0]
        need = sum(E.ACTION_DIMS)
        if need > have:
            assert (need - have) % 2 == 0, "only on/off heads can be added"
            k = (need - have) // 2
            sd["pi.weight"] = torch.cat([sd["pi.weight"], torch.zeros(need - have, sd["pi.weight"].shape[1], dtype=sd["pi.weight"].dtype)], 0)
            sd["pi.bias"] = torch.cat([sd["pi.bias"], torch.tensor([2.5, -2.5] * k, dtype=sd["pi.bias"].dtype)])
            if "action_dims" in ck:
                ck["action_dims"] = tuple(E.ACTION_DIMS)
        if "obs_mean" in ck:
            ck["obs_mean"] = np.concatenate([ck["obs_mean"], np.zeros(extra)])
            ck["obs_var"] = np.concatenate([ck["obs_var"], np.ones(extra)])
            ck["obs_dim"], ck["widened_from"] = E.OBS_DIM, old
        torch.save(ck, f)
        n += 1
        print("{}: {} -> {} inputs".format(os.path.relpath(f, d), old, E.OBS_DIM))
    print("widened {} file(s)".format(n))


if __name__ == "__main__":
    main()

"""Carry a movement network over to the three inputs of stage C part 2 (movement_env.N_C2: where to look, that a look
direction is given, that he is to stand at the goal). They are appended at the end with zero weights, so the network
chooses exactly as before whatever they say, until training gives them a use; the statistics of the old inputs are kept
as they are and the new ones start at mean 0, variance 1 (they are scaled already: nothing is changed by it).

    python sim/widen_move.py --run move_v15n --out move_v16 [--runs-dir <folder>] [--out-dir <folder>]

The new run's policy.pt is written (never over one that is there); the old run is not touched. Then:
    python sim/export_policy.py --run move_v16 --out data/sim_runs/move_v16/policy.npz
    python sim/train_move.py --run move_v16 --resume --look 0.5 --arrive 0.3 ... (the old run's options)
"""
import argparse
import os

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
N_C2 = 3                                                     # (movement_env.N_C2; not imported: that module loads the simulator)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="the movement run to carry over")
    ap.add_argument("--out", required=True, help="the new run's name")
    ap.add_argument("--runs-dir", default=None, help="the folder of the runs (default: data/sim_runs of the repo)")
    ap.add_argument("--out-dir", default=None, help="the folder the new run goes to (default: the same)")
    a = ap.parse_args()
    runs = a.runs_dir or os.path.join(ROOT, "data", "sim_runs")
    dst = os.path.join(a.out_dir or runs, a.out)
    assert not os.path.exists(os.path.join(dst, "policy.pt")), "there is a policy.pt in " + dst
    ck = torch.load(os.path.join(runs, a.run, "policy.pt"), weights_only=False, map_location="cpu")
    assert not ck.get("c2"), "this network has the inputs already"
    sd = ck["model"]
    old = sd["body.0.weight"].shape[1]
    assert old == ck["obs_dim"] == len(ck["obs_mean"]) == len(ck["obs_var"]), (old, ck["obs_dim"])
    for k_ in ("body.0.weight", "v.0.weight"):               # the policy's first layer and the value's
        sd[k_] = torch.cat([sd[k_], torch.zeros(sd[k_].shape[0], N_C2, dtype=sd[k_].dtype)], 1)
    ck["obs_mean"] = np.concatenate([ck["obs_mean"], np.zeros(N_C2)])
    ck["obs_var"] = np.concatenate([ck["obs_var"], np.ones(N_C2)])
    ck["obs_dim"], ck["c2"], ck["widened_from"] = old + N_C2, N_C2, a.run
    os.makedirs(dst, exist_ok=True)
    torch.save(ck, os.path.join(dst, "policy.pt"))
    print("{}: {} -> {} inputs, written to {}".format(a.run, old, old + N_C2, os.path.join(dst, "policy.pt")))


if __name__ == "__main__":
    main()

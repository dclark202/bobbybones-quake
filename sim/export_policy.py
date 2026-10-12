"""Export a trained movement policy (policy.pt) to plain numpy arrays for the game server (no torch there).

    python sim/export_policy.py --run bloodrun_human_v2 --out data/movetest/policy.npz
"""
import argparse
import os

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--runs-dir", default=None, help="the folder of the runs (default: data/sim_runs of the repo)")
a = ap.parse_args()
ck = torch.load(os.path.join(a.runs_dir or os.path.join(ROOT, "data", "sim_runs"), a.run, "policy.pt"), weights_only=False, map_location="cpu")
sd = {k: v.numpy() for k, v in ck["model"].items()}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
np.savez(a.out, w0=sd["body.0.weight"], b0=sd["body.0.bias"], w1=sd["body.2.weight"], b1=sd["body.2.bias"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         action_dims=np.array(ck["action_dims"]), substeps=np.array([int(x) for x in str(ck.get("substeps", "25")).split(",")]),
         run=np.array(a.run), v14=np.array(bool(ck.get("v14", False))),     # (v14: trained with lava and the game's step height)
         jumps=np.array(bool(ck.get("jumps", False))), hand=np.array(bool(ck.get("hand", False))),
         mouse=np.array(bool(ck.get("mouse", False))), mouse_rev=np.array(float(ck.get("mouse_rev", 8))),
         c2=np.array(int(ck.get("c2", 0) or 0)))        # (stage C part 2: how many inputs it has for a look direction and "stand at the goal": 0 or 3)
#   # (hand: under his finger limits, five inputs of the hand)                      # (v15: with the pros' jumps and the five inputs of a jump ahead)
print("wrote", a.out)

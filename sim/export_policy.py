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
a = ap.parse_args()
ck = torch.load(os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), weights_only=False)
sd = {k: v.numpy() for k, v in ck["model"].items()}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
np.savez(a.out, w0=sd["body.0.weight"], b0=sd["body.0.bias"], w1=sd["body.2.weight"], b1=sd["body.2.bias"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         action_dims=np.array(ck["action_dims"]), substeps=np.array([int(x) for x in str(ck.get("substeps", "25")).split(",")]),
         run=np.array(a.run), v14=np.array(bool(ck.get("v14", False))))     # (v14: trained with lava and the game's step height)
print("wrote", a.out)

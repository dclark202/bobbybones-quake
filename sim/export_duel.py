"""Export a trained GRU duel policy (policy.pt) to plain numpy arrays for the game server (no torch there).

    python sim/export_duel.py --run duel_gru_v2 --out data/duellive/policy.npz
"""
import argparse
import os

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--env", default="duel_env_v2", help="simulator module the policy was trained in")
a = ap.parse_args()
ck = torch.load(os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), weights_only=False, map_location="cpu")
sd = {k: v.cpu().numpy() for k, v in ck["model"].items()}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
np.savez(a.out, w0=sd["enc.0.weight"], b0=sd["enc.0.bias"], w1=sd["enc.2.weight"], b1=sd["enc.2.bias"],
         wih=sd["gru.weight_ih"], whh=sd["gru.weight_hh"], bih=sd["gru.bias_ih"], bhh=sd["gru.bias_hh"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         action_dims=np.array(ck["action_dims"]), run=np.array(a.run), env=np.array(a.env),
         minutes=np.array(ck.get("minutes", 0.0)), react_ms=np.array(ck.get("react_ms", 150.0)), acquire_ms=np.array(ck.get("acquire_ms", 0.0)), no_walk=np.array(bool(ck.get("no_walk", False))))
print("wrote", a.out, "obs", ck["obs_dim"], "actions", ck["action_dims"], "minutes", round(ck.get("minutes", 0.0)))

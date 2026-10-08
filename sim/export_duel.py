"""Export a trained GRU duel policy (policy.pt) to plain numpy arrays for the game server (no torch there).

    python sim/export_duel.py --run duel_gru_v2 --out data/duellive/policy.npz
    python sim/export_duel.py --run duel_gru_v12 --env duel_env_ffa_v12 --set INTENT_HOLD=8 --out ...

The simulator's switches the network was trained with and that change how it is fed or driven (INTENT_HOLD, ITEM_BELIEF,
AIM_LEVEL, ...) go into the file as "env_vars", and the length of a training round as "round_secs": the plugins set them
before they load the simulator (none of them reached a server until 2026-10-08). Newer checkpoints carry both; --set
and --round-secs give or override them (the runs up to v12: --set INTENT_HOLD=8).
"""
import argparse
import json
import os

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--env", default="duel_env_v2", help="simulator module the policy was trained in")
ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator switch the network was trained with")
ap.add_argument("--round-secs", type=float, default=0.0, help="the length of a training round on the server's map (0: from the checkpoint, else the plugin's default)")
a = ap.parse_args()
ck = torch.load(os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), weights_only=False, map_location="cpu")
sd = {k: v.cpu().numpy() for k, v in ck["model"].items()}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
env_vars = dict(ck.get("env_vars") or {})
env_vars.update(dict(x.split("=", 1) for x in a.set))
round_secs = a.round_secs or float(ck.get("round_secs") or 0.0)
np.savez(a.out, w0=sd["enc.0.weight"], b0=sd["enc.0.bias"], w1=sd["enc.2.weight"], b1=sd["enc.2.bias"],
         wih=sd["gru.weight_ih"], whh=sd["gru.weight_hh"], bih=sd["gru.bias_ih"], bhh=sd["gru.bias_hh"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         **({"cell": sd["cell.weight"]} if "cell.weight" in sd else {}),
         action_dims=np.array(ck["action_dims"]), run=np.array(a.run), env=np.array(a.env),
         minutes=np.array(ck.get("minutes", 0.0)), react_ms=np.array(ck.get("react_ms", 150.0)), acquire_ms=np.array(ck.get("acquire_ms", 0.0)), no_walk=np.array(bool(ck.get("no_walk", False))),
         env_vars=np.array(json.dumps(env_vars)), **({"round_secs": np.array(round_secs)} if round_secs > 0 else {}))
print("wrote", a.out, "obs", ck["obs_dim"], "actions", ck["action_dims"], "minutes", round(ck.get("minutes", 0.0)), "switches", env_vars,
      "round", round_secs or "plugin default")

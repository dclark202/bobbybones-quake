"""Export a trained GRU duel policy (policy.pt) to plain numpy arrays for the game server (no torch there).

    python sim/export_duel.py --run duel_gru_v2 --out data/duellive/policy.npz
    python sim/export_duel.py --run duel_gru_v12 --env duel_env_ffa_v12 --set INTENT_HOLD=8 --out ...

The simulator's switches the network was trained with and that change how it is fed or driven (INTENT_HOLD, ITEM_BELIEF,
AIM_LEVEL, ...) go into the file as "env_vars", and the length of a training round as "round_secs": the plugins set them
before they load the simulator (none of them reached a server until 2026-10-08). Newer checkpoints carry both; --set
and --round-secs give or override them (the runs up to v12: --set INTENT_HOLD=8).
"""
import argparse
import datetime
import json
import os
import re

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--env", default="duel_env_v2", help="simulator module the policy was trained in")
ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator switch the network was trained with")
ap.add_argument("--policy", default="policy.pt", help="the save of the run to export: a file in its folder, or a full path (a copy of a running trainer's save: it is rewritten while the run goes on)")
ap.add_argument("--legs", default="", help="the movement network's run (duel_env's LEGS): its policy.npz goes beside the output as legs.npz")
ap.add_argument("--version", default="", help="the version name the server's welcome shows (default: from the run's name, duel_gru_v0_3_1b -> v0.3.1)")
ap.add_argument("--updated", default="", help="the date the welcome shows as last updated (default: today, the day of the export and upload)")
ap.add_argument("--round-secs", type=float, default=0.0, help="the length of a training round on the server's map (0: from the checkpoint, else the plugin's default)")
a = ap.parse_args()


def version_name(run):
    """the docs' version name of a run (owner, 2026-10-11: v0.1 is duel_gru_v15c; duel_gru_v0_3 -> v0.3, a restart's letter
    dropped: duel_gru_v0_3_1b -> v0.3.1)"""
    m = re.match(r"duel_gru_v(\d+(?:_\d+)+)[a-z]?$", run)
    return "v" + m.group(1).replace("_", ".") if m else "v0.1" if run == "duel_gru_v15c" else run


ck = torch.load(os.path.join(ROOT, "data", "sim_runs", a.run, a.policy), weights_only=False, map_location="cpu")
sd = {k: v.cpu().numpy() for k, v in ck["model"].items()}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
env_vars = dict(ck.get("env_vars") or {})
if "STYLE_P" in (ck.get("game_vars") or {}):                # (v0.3 on) trained with no styles, or with this share: the plugins draw by it
    env_vars["STYLE_P"] = str(ck["game_vars"]["STYLE_P"])
env_vars.update(dict(x.split("=", 1) for x in a.set))
round_secs = a.round_secs or float(ck.get("round_secs") or 0.0)
legs = {}
if str(env_vars.get("LEGS", "0")) not in ("0", "", "0.0"):   # a network with legs is nothing without their network
    assert a.legs, "this network has legs (LEGS=1): give --legs <the movement network's run>"
    import shutil
    shutil.copy(os.path.join(ROOT, "data", "sim_runs", a.legs, "policy.npz"), os.path.join(os.path.dirname(os.path.abspath(a.out)), "legs.npz"))
    legs = {"legs": np.array("legs.npz"), "legs_run": np.array(a.legs)}
# (v0.2) the attention part: the layout of the tokens as text ("attn") and its weights under "attn.<name>", as the
# checkpoint has them. The plugins give both to sim/attn.py's forward_np (plugins/netpass.py); the two value outputs
# for the long count (v2) are the trainer's alone and stay behind.
attn = {}
if ck.get("attn") is not None:
    attn = {"attn": np.array(json.dumps(ck["attn"]))}
    attn.update({k: v for k, v in sd.items() if k.startswith("attn.")})
    assert "attn.door.weight" in attn, "the checkpoint names an attention part and has no weights for it"
    assert int(ck["attn"]["obs_dim"]) == sd["enc.0.weight"].shape[1], "the tokens are cut from {} inputs, the network has {}".format(
        ck["attn"]["obs_dim"], sd["enc.0.weight"].shape[1])
legs_in = {}                                                 # (LEGS_IN, B-253) his legs' branch: its weights as legs_w0 ... legs_bp
if "legs.0.weight" in sd:                                    # (the movement network's file goes beside it all the same: the simulator
    assert legs, "this network has its legs inside (LEGS_IN): give --legs <the movement network's run> as well"   # finds his ways with it)
    legs_in = {"legs_w0": sd["legs.0.weight"], "legs_b0": sd["legs.0.bias"], "legs_w1": sd["legs.2.weight"], "legs_b1": sd["legs.2.bias"],
               "legs_wp": sd["legs.4.weight"], "legs_bp": sd["legs.4.bias"]}
slow = {}                                                    # (--slow-mem) the slow memory: its layout as text and its weights
if ck.get("slow") is not None:
    slow = {"slow": np.array(json.dumps(ck["slow"]))}
    slow.update({k: v for k, v in sd.items() if k.startswith("slow.")})
    assert "slow.door.weight" in slow, "the checkpoint names a slow memory and has no weights for it"
order = {}                                                   # (v0.4, --ordered-heads) the order as text, the tables under "order.t<output>.weight"
if ck.get("ordered"):
    order = {"ordered": np.array(json.dumps(ck["ordered"]))}
    order.update({k: v for k, v in sd.items() if k.startswith("order.")})
head = {}                                                    # (v0.4) the head (sim/head.py): its layout as text and its weights under "head.<name>"
if ck.get("head") is not None:                               # (plugins/netpass.py gives both to head.np_tick; its values, win bands and
    head = {"head": np.array(json.dumps(ck["head"]))}        # guesses are the trainer's alone and stay behind, as the aux layers)
    head.update({k: v for k, v in sd.items() if k.startswith("head.") and not k.startswith(("head.v_short.", "head.v_long.", "head.win.", "head.aux."))})
    assert "head.plan_in.weight" in head and "head.target.weight" in head, "the checkpoint names a head and has no weights for it"
np.savez(a.out, w0=sd["enc.0.weight"], b0=sd["enc.0.bias"], w1=sd["enc.2.weight"], b1=sd["enc.2.bias"],
         wih=sd["gru.weight_ih"], whh=sd["gru.weight_hh"], bih=sd["gru.bias_ih"], bhh=sd["gru.bias_hh"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         **({"cell": sd["cell.weight"]} if "cell.weight" in sd else {}),
         action_dims=np.array(ck["action_dims"]), run=np.array(a.run), env=np.array(a.env),
         minutes=np.array(ck.get("minutes", 0.0)), react_ms=np.array(ck.get("react_ms", 150.0)), acquire_ms=np.array(ck.get("acquire_ms", 0.0)), no_walk=np.array(bool(ck.get("no_walk", False))),
         env_vars=np.array(json.dumps(env_vars)), version=np.array(a.version or version_name(a.run)),
         updated=np.array(a.updated or datetime.date.today().isoformat()), **attn, **slow, **head, **order, **legs, **legs_in, **({"round_secs": np.array(round_secs)} if round_secs > 0 else {}))
print("wrote", a.out, "obs", ck["obs_dim"], "actions", ck["action_dims"], "minutes", round(ck.get("minutes", 0.0)), "switches", env_vars,
      "round", round_secs or "plugin default",
      "| attention: {} tokens, door {}".format(ck["attn"]["tokens"], "open" if np.abs(attn["attn.door.weight"]).sum() > 0 else "shut (the part is skipped)") if attn else "",
      "| head: a tick every {} frames, plan_in {}".format(ck["head"]["every"], "open" if np.abs(head["head.plan_in.weight"]).sum() > 0 else "at zero") if head else "")

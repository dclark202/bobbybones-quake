"""Export a trained GRU duel policy (policy.pt) to plain numpy arrays for the game server (no torch there).

    python sim/export_duel.py --run duel_gru_v2 --out data/duellive/policy.npz
    python sim/export_duel.py --run duel_gru_v12 --env duel_env_ffa_v12 --set INTENT_HOLD=8 --out ...

The simulator's switches the network was trained with and that change how it is fed or driven (INTENT_HOLD, ITEM_BELIEF,
AIM_LEVEL, ...) go into the file as "env_vars", and the length of a training round as "round_secs": the plugins set them
before they load the simulator (none of them reached a server until 2026-10-08). Newer checkpoints carry both; --set
and --round-secs give or override them (the runs up to v12: --set INTENT_HOLD=8).

(v0.4.1) A network with the brain's token (the checkpoint's "btoken", "belief", "track", "track_z" and the attention part's
btok_emb, btok_mark) also gets the brain (belief.*), the two readouts the token is made of (track.*, trackz.*; not the readout
ahead, which the token does not read), the layouts as text, and the token's layout with its gate: the checkpoint's gate as it
was at that save, or --btoken-gate. plugins/netpass.py steps the brain while the gate is above zero. A network without the
token is written exactly as before.
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
ap.add_argument("--btoken-gate", type=float, default=-1.0, help="(v0.4.1) the brain token's gate in the file (-1: the checkpoint's own; 0: shut, the network as without it)")
ap.add_argument("--rule-fade-g", type=float, default=-1.0, help="(v0.4.2a) the rule fade's gate in the file (-1: the checkpoint's own; 0: none)")
ap.add_argument("--no-readouts", action="store_true", help="(B-283) leave the brain's readouts ahead and 'in control' out (by default they go in when the "
                "checkpoint has them: nothing plays from them, the plugin's mind view (!mind on) shows them)")
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
env_vars.setdefault("AUTO_HOP", "1")                         # (v0.3.7) always said: the plugins put the bot's cg_autoHop to it (a checkpoint
#                                                              that does not say was trained with the simulator's auto-hop, 1)
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
    lz_ = np.load(os.path.join(ROOT, "data", "sim_runs", a.legs, "policy.npz"))     # (v0.3.2) the branch reads the inputs the legs' file makes:
    assert int(lz_["w0"].shape[1]) == int(sd["legs.0.weight"].shape[1]), \
        "the branch has {} inputs, the legs' network {} {} (the three of a look point: LEGS_LOOK, movement_env.N_C2)".format(  # 61, or 64
            sd["legs.0.weight"].shape[1], a.legs, lz_["w0"].shape[1])
def on_(k_):
    return str(env_vars.get(k_, "0")) not in ("0", "", "0.0")


if on_("LEGS_TURN_ADD") or on_("LEGS_KEYS_ADD"):              # (v0.3.2) his turn correction on his legs is the fourteenth output; (v0.3.3,
    n_ = 13 + int(on_("LEGS_TURN_ADD")) + 5 * int(on_("LEGS_KEYS_ADD"))       # LEGS_KEYS_ADD) the five "my legs' / mine" follow
    assert len(ck["action_dims"]) == n_, "LEGS_TURN_ADD / LEGS_KEYS_ADD and {} outputs ({} expected)".format(len(ck["action_dims"]), n_)
uni = {}                                                     # (--legs-feat, --legs-guide) the layout as text, legs_door, the guide's weights
if ck.get("legs_unify") is not None:
    assert legs_in, "a network with legs_unify has the legs' branch inside"
    uni = {"legs_unify": np.array(json.dumps(ck["legs_unify"]))}
    if "legs_door.weight" in sd:
        uni.update(legs_door_w=sd["legs_door.weight"], legs_door_b=sd["legs_door.bias"])
    if "legs_guide" in sd:
        uni["legs_guide"] = sd["legs_guide"]
    for n_ in ("legs_gate", "legs_motor", "legs_res_a", "legs_res"):     # (v0.3.4 A, B)
        if n_ + ".weight" in sd:
            uni.update({n_ + "_w": sd[n_ + ".weight"], n_ + "_b": sd[n_ + ".bias"]})
if "switch_fade" in ck:                                      # (v0.3.4 C, --switch-fade) the bias taken off the switch's "legs" choice
    uni["switch_fade"] = np.array(float(ck["switch_fade"]))
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
brain = {}                                                   # (v0.4.1) the brain, its two readouts and the token (sim/btoken.py); plugins/netpass.py
if ck.get("btoken") is not None:                             # steps them as test_suite.Policy does (the readout ahead and the aux layers stay behind)
    assert ck.get("belief") is not None and attn and "attn.btok_emb.weight" in attn, "the checkpoint names a brain token without its brain or its first layer"
    bt_ = dict(ck["btoken"])
    if a.btoken_gate >= 0:
        bt_["gate"] = float(a.btoken_gate)
    brain = {"btoken": np.array(json.dumps(bt_)), "belief": np.array(json.dumps(ck["belief"]))}
    for k_ in ("track", "track_z"):
        if ck.get(k_) is not None:
            brain[k_] = np.array(json.dumps(ck[k_]))
    brain.update({k: v for k, v in sd.items() if k.startswith(("belief.", "track.", "trackz."))})
    assert "belief.gru.weight_ih" in brain and ("track.0.weight" in brain or "trackz.0.weight" in brain), "the brain's or its readouts' weights are missing"
else:
    assert a.btoken_gate < 0, "--btoken-gate: this network has no brain token"
mind = {}                                                    # (B-283) the brain's readouts the mind view shows (plugins/mindlog.py): ahead
if brain and not a.no_readouts:                              # (sim/ahead.py) and v0.4.3's "in control" (sim/control.py); nothing plays from them
    for k_ in ("ahead", "control"):
        if ck.get(k_) is not None and "{}.0.weight".format(k_) in sd:
            mind[k_] = np.array(json.dumps(ck[k_]))
            mind.update({k: v for k, v in sd.items() if k.startswith(k_ + ".")})
rfade = {}                                                   # (v0.4.2a, sim/rule_fade.py) the faded columns and the gate g; plugins/netpass.py
if ck.get("rule_fade") is not None:                          # fades them as test_suite.Policy does (and with "readers", the simulator's
    rf_ = dict(ck["rule_fade"])                              # readers take the brain's answer: BRAIN_READ in env_vars)
    if a.rule_fade_g >= 0:
        rf_["g"] = float(a.rule_fade_g)
    assert not (rf_.get("readers") and float(rf_.get("g", 0.0)) > 0) or brain, "the rule fade's readers need the brain in the file"
    rfade = {"rule_fade": np.array(json.dumps(rf_))}
else:
    assert a.rule_fade_g < 0, "--rule-fade-g: this network has no rule fade"
np.savez(a.out, w0=sd["enc.0.weight"], b0=sd["enc.0.bias"], w1=sd["enc.2.weight"], b1=sd["enc.2.bias"],
         wih=sd["gru.weight_ih"], whh=sd["gru.weight_hh"], bih=sd["gru.bias_ih"], bhh=sd["gru.bias_hh"],
         wp=sd["pi.weight"], bp=sd["pi.bias"], obs_mean=ck["obs_mean"], obs_var=ck["obs_var"],
         **({"cell": sd["cell.weight"]} if "cell.weight" in sd else {}),
         action_dims=np.array(ck["action_dims"]), run=np.array(a.run), env=np.array(a.env),
         minutes=np.array(ck.get("minutes", 0.0)), react_ms=np.array(ck.get("react_ms", 150.0)), acquire_ms=np.array(ck.get("acquire_ms", 0.0)), no_walk=np.array(bool(ck.get("no_walk", False))),
         env_vars=np.array(json.dumps(env_vars)), version=np.array(a.version or version_name(a.run)),
         updated=np.array(a.updated or datetime.date.today().isoformat()), **attn, **slow, **head, **order, **legs, **legs_in, **uni, **brain, **mind, **rfade, **({"round_secs": np.array(round_secs)} if round_secs > 0 else {}))
print("wrote", a.out, "obs", ck["obs_dim"], "actions", ck["action_dims"], "minutes", round(ck.get("minutes", 0.0)), "switches", env_vars,
      "round", round_secs or "plugin default",
      "| attention: {} tokens, door {}".format(ck["attn"]["tokens"], "open" if np.abs(attn["attn.door.weight"]).sum() > 0 else "shut (the part is skipped)") if attn else "",
      "| head: a tick every {} frames, plan_in {}".format(ck["head"]["every"], "open" if np.abs(head["head.plan_in.weight"]).sum() > 0 else "at zero") if head else "",
      "| brain: {} numbers in its token, gate {:.4f}".format(json.loads(str(brain["btoken"]))["dim"], json.loads(str(brain["btoken"]))["gate"]) if brain else "",
      "| readouts for the mind view: {}".format(", ".join(k for k in ("ahead", "control") if k in mind) or "none") if brain else "",
      "| rule fade: {} columns, g {:.4f}, readers {}".format(len(json.loads(str(rfade["rule_fade"]))["cols"]), json.loads(str(rfade["rule_fade"]))["g"],
                                                            bool(json.loads(str(rfade["rule_fade"])).get("readers"))) if rfade else "")

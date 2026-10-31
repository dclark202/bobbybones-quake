"""The entropy arms (owner, 2026-10-30: "Run the experiment"; docs/runs/v0.6.1b/DRIFT.md): two short runs from v0.6.1b's end
(update 180, keep/policy_end_v061b.pt + its optimizer), each v0.6.1b's own command with only --run, --minutes and --ent-coef
changed: arm B --ent-coef 0.002 (the exploration bonus in v0.6.0's proportion to the pay), arm A --ent-coef 0.005 (as v0.6.1b).
Each arm's folder: the start network and optimizer, v0.6.1b's league (its snapshots and both anchors), its live.json
(BRAIN_FADE 1) and live_settings.env. Writes docs/runs/v0.6.1b/arms/train_<arm>.cmd and the folders; refuses on an existing one.
    python docs/runs/v0.6.1b/arms/make_arms.py"""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_v0_6_1b")
MINUTES = 130                                      # ~33 updates at ~3.8 min: saves 10, 20, 30
ARMS = {"arm_v061b_ent002": "0.002", "arm_v061b_ent005": "0.005"}
src = open(os.path.join(R0, "..", "..", "..", "docs", "runs", "v0.6.1b", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(t, a, b):
    assert t.count(a) == 1, (a, t.count(a))
    return t.replace(a, b)


for run, ent in ARMS.items():
    R = os.path.join(SR, run)
    assert not os.path.exists(R), R + " is there already: look at it first"
    t = src
    t = sub(t, "rem the repo root: this file lives in docs\\runs\\v0.6.1b\\\nset ROOT=%~dp0..\\..\\..\n",
            "rem ==== the entropy arm {} (owner, 2026-10-30; docs/runs/v0.6.1b/DRIFT.md): v0.6.1b's command from its end with\n"
            "rem  --run {}, --minutes {}, --ent-coef {}. Made by docs/runs/v0.6.1b/arms/make_arms.py.\n"
            "rem the repo root: this file lives in docs\\runs\\v0.6.1b\\arms\\\nset ROOT=%~dp0..\\..\\..\\..\n".format(run, run, MINUTES, ent))
    t = sub(t, "call %~dp0aim2_env.cmd", "call %~dp0..\\aim2_env.cmd")
    t = sub(t, "--run duel_gru_v0_6_1b ", "--run {} ".format(run))
    t = sub(t, "--minutes 720 --gamma", "--minutes {} --gamma".format(MINUTES))
    t = sub(t, "--ent-coef 0.005 ", "--ent-coef {} ".format(ent))
    t = t.replace("data\\sim_runs\\duel_gru_v0_6_1b.log", "data\\sim_runs\\{}.log".format(run))
    assert "duel_gru_v0_6_1b" not in t.split("start \"\" /b")[1]
    open(os.path.join(HERE, "train_{}.cmd".format(run)), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    os.makedirs(os.path.join(R, "keep"))
    shutil.copytree(os.path.join(R0, "snapshots"), os.path.join(R, "snapshots"))
    shutil.copy2(os.path.join(R0, "keep", "policy_end_v061b.pt"), os.path.join(R, "policy.pt"))
    shutil.copy2(os.path.join(R0, "keep", "opt_end_v061b.pt"), os.path.join(R, "opt.pt"))
    shutil.copy2(os.path.join(R0, "keep", "policy_end_v061b.pt"), os.path.join(R, "keep", "policy_start.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(R, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    assert lv.get("BRAIN_FADE") == 1.0, lv
    json.dump(lv, open(os.path.join(R, "live.json"), "w", encoding="utf-8"))
    print(run, "ent", ent, "| live", lv)

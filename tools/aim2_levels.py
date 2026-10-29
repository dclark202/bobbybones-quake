"""The !aim table under the AIM2 model: one exported network (policy_trained.npz, sim/export_duel.py) -> policy_worse.npz,
policy_default.npz, policy_better.npz, policy_max.npz (the same weights, the levels' settings in env_vars, react_ms,
acquire_ms) and policy.npz = default. docs/v0.5.2/AIM_MODEL.md explains every value.

    python tools/aim2_levels.py <data folder>              (policy_trained.npz in it)
    python tools/aim2_levels.py --show                     the table

default = the pros' typical values, worse and better around their 75th and 25th percentiles (knob by knob; see the table's
comment and docs/runs/v0.6.0's notes for where a value departs from that); max = every perception and reaction limit the server can switch
off turned off, the hand as trained.
"""
import json
import os
import shutil
import sys

import numpy as np

COMMON = dict(AIM2="1", AIM2_SPLIT="1", AIM2_FOCUS="1", AIM2_FLINCH="1", AIM2_W="1", AIM2_SPLIT_W="1", AIM2_FOCUS_GAIN="0",
              PERCEPT_SPEED="0", PERCEPT_TAU="0.15", AIM_LEVEL="3")
# name: react_ms, acquire_ms, then the env_vars
TABLE = {   # FINAL 2026-10-27 evening (owner): the twelve knobs measured on the pros (781 pooled demos, the scratchpad's knobs/
            # write_aim.py), the table on the public servers from 2026-10-28 (v0.4.2b, then v0.6.0) and v0.6.0's training
            # default (docs/runs/v0.6.0/aim2_env.cmd); it replaced the 18:20 table of docs/v0.5.2/AIM_MODEL.md
    "worse": (150, 275, dict(SURPRISE_MS="0", PERCEPT_SIGMA="1.1", AIM2_C_SLIP="0.039", AIM2_S0="5", AIM2_CAP_SLIP="3.1",
                             AIM2_C_ECC="0.12", AIM2_E0="0", AIM2_CAP_ECC="2.8", AIM2_FOCUS_SIG="1.0",   # (owner: 1.0, the range's top; measured 1.1)
                             FLINCH_PER_DMG="0.033", FLINCH_MAX="1.9", FLINCH_TAU="0.3", MOTOR_NOISE="0.116", MOTOR_BASE="0.059",
                             VEL_DELAY_MS="300", VEL_WEBER="0.45", RANGE_WEBER="0.26")),
    "default": (125, 225, dict(SURPRISE_MS="0", PERCEPT_SIGMA="0.9", AIM2_C_SLIP="0.023", AIM2_S0="5", AIM2_CAP_SLIP="2.1",
                               AIM2_C_ECC="0.06", AIM2_E0="0", AIM2_CAP_ECC="2.8", AIM2_FOCUS_SIG="1.0",
                               FLINCH_PER_DMG="0.012", FLINCH_MAX="0.7", FLINCH_TAU="0.3", MOTOR_NOISE="0.10", MOTOR_BASE="0.05",
                               VEL_DELAY_MS="200", VEL_WEBER="0.2", RANGE_WEBER="0.19")),
    "better": (100, 200, dict(SURPRISE_MS="0", PERCEPT_SIGMA="0.65", AIM2_C_SLIP="0.007", AIM2_S0="5", AIM2_CAP_SLIP="1.1",   # (owner: p75, not p90)
                              AIM2_C_ECC="0.01", AIM2_E0="0", AIM2_CAP_ECC="2.8", AIM2_FOCUS_SIG="0.7",
                              FLINCH_PER_DMG="0", FLINCH_MAX="0", FLINCH_TAU="0.3", MOTOR_NOISE="0.080", MOTOR_BASE="0.038",
                              VEL_DELAY_MS="175", VEL_WEBER="0.15", RANGE_WEBER="0.17")),
    # max: AIM_LEVEL 40 takes the sight error, surprise and flinch to ~0; written out as well. The hand AS TRAINED.
    "max": (25, 25, dict(AIM_LEVEL="40", SURPRISE_MS="0", PERCEPT_SIGMA="0", AIM2_C_SLIP="0", AIM2_CAP_SLIP="0", AIM2_C_ECC="0",
                         AIM2_CAP_ECC="0", AIM2_FOCUS_SIG="1", FLINCH_PER_DMG="0", MOTOR_NOISE="0.10", MOTOR_BASE="0.05",
                         VEL_DELAY_MS="25", VEL_WEBER="0", VEL_MIN="0", RANGE_WEBER="0", PROJ_NOTICE_MS="25", PROJ_READ_MS="25",
                         SM_FACE_DEG="0")),
}
DROP = ("AIM_LEVEL", "AIM_NAME", "PERCEPT_SPEED", "PERCEPT_SPEED_MAX", "PERCEPT_SPEED_MAX_RG", "PERCEPT_SPEED_MAX_LG",
        "PERCEPT_SIGMA", "PERCEPT_TAU", "MOTOR_NOISE", "MOTOR_BASE", "SURPRISE_MS", "FLINCH_PER_DMG", "FLINCH_MAX", "FLINCH_TAU")


def level_vars(name, ev0):
    rm, am, ex = TABLE[name]
    ev = {k: v for k, v in ev0.items() if k not in DROP and not k.startswith("AIM2")}
    ev.update(COMMON)
    ev.update(ex)
    ev["AIM_NAME"] = name
    return rm, am, ev


def main():
    if sys.argv[1:] == ["--show"]:
        for k, (rm, am, ex) in TABLE.items():
            print(k, rm, am, ex)
        return
    D = sys.argv[1]
    base = dict(np.load(os.path.join(D, "policy_trained.npz"), allow_pickle=False))
    ev0 = json.loads(str(base["env_vars"]))
    for name in TABLE:
        rm, am, ev = level_vars(name, ev0)
        P = dict(base)
        P["env_vars"] = np.array(json.dumps(ev))
        P["react_ms"], P["acquire_ms"] = np.array(float(rm)), np.array(float(am))
        P["round_secs"] = np.array(600.0)
        np.savez(os.path.join(D, "policy_{}.npz".format(name)), **P)
        print(name, rm, am, {k: ev[k] for k in sorted(ev) if k.startswith(("AIM", "PERCEPT", "FLINCH", "MOTOR", "SURPRISE", "VEL_",
                                                                            "RANGE_", "PROJ_", "SM_"))})
    shutil.copyfile(os.path.join(D, "policy_default.npz"), os.path.join(D, "policy.npz"))


if __name__ == "__main__":
    main()

"""The !aim table under the AIM2 model: one exported network (policy_trained.npz, sim/export_duel.py) -> policy_worse.npz,
policy_default.npz, policy_better.npz, policy_max.npz (the same weights, the levels' settings in env_vars, react_ms,
acquire_ms) and policy.npz = default. docs/v0.5.2/AIM_MODEL.md explains every value.

    python tools/aim2_levels.py <data folder>              (policy_trained.npz in it)
    python tools/aim2_levels.py --show                     the table

default = the pros (the trance tournament demos and the demo archive), per weapon style; worse = about 25-50% below
them; better = their top decile or 25% above their mean; max = every perception and reaction limit the server can switch
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
TABLE = {   # FINAL 2026-10-27 18:20: fitted on the pooled pro sample (968 demos, the pros' per-demo distributions), docs/v0.5.2/AIM_MODEL.md
    "worse": (150, 300, dict(SURPRISE_MS="300", PERCEPT_SIGMA="1.0", AIM2_C_SLIP="0.07", AIM2_S0="0", AIM2_CAP_SLIP="4",
                             AIM2_C_ECC="0.035", AIM2_E0="2", AIM2_CAP_ECC="2", AIM2_FOCUS_SIG="0.85",
                             FLINCH_PER_DMG="0.15", FLINCH_MAX="4", FLINCH_TAU="0.4", MOTOR_NOISE="0.15", MOTOR_BASE="0.075",
                             VEL_DELAY_MS="300", VEL_WEBER="0.45", RANGE_WEBER="0.25")),
    "default": (100, 200, dict(SURPRISE_MS="200", PERCEPT_SIGMA="0.6", AIM2_C_SLIP="0.035", AIM2_S0="10", AIM2_CAP_SLIP="2.5",
                               AIM2_C_ECC="0.02", AIM2_E0="2", AIM2_CAP_ECC="1", AIM2_FOCUS_SIG="0.75",
                               FLINCH_PER_DMG="0.05", FLINCH_MAX="1.5", FLINCH_TAU="0.3", MOTOR_NOISE="0.10", MOTOR_BASE="0.05")),
    "better": (100, 150, dict(SURPRISE_MS="150", PERCEPT_SIGMA="0.35", AIM2_C_SLIP="0.02", AIM2_S0="15", AIM2_CAP_SLIP="1.5",
                              AIM2_C_ECC="0.005", AIM2_E0="3", AIM2_CAP_ECC="0.3", AIM2_FOCUS_SIG="0.7", AIM2_FOCUS_GAIN="1",
                              FLINCH_PER_DMG="0.02", FLINCH_MAX="0.75", FLINCH_TAU="0.25", MOTOR_NOISE="0.075", MOTOR_BASE="0.0375",
                              VEL_DELAY_MS="150", VEL_WEBER="0.1")),
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

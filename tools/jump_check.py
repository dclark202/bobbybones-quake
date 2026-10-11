"""His own rate at the pros' jumps, per jump of a map (v15, BACKLOG B-204): a saved network alone in jump runs.

    python tools/jump_check.py --map aerowalk --policy data/sim_runs/<run>/policy.pt [--steps 2400] [--teacher <run>]

Every round is a jump run (sim/duel_env.py, JUMPS): he begins a second or two before a take-off and goes for the item
behind it. Per jump of sim/pro_gaps/<map>.json that is in use: tries, the share that got over, the share that fell
short; with --teacher (a movement network trained with train_move.py --jumps, exported with sim/export_policy.py) also
how often his keys are its labels. A network with fewer inputs than the simulator is widened for the check (the new
inputs at zero weight). One JSON line a map; low priority, one process.
"""
import argparse
import ctypes
import json
import os
import sys
import tempfile

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "2")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
RUN_VARS = dict(RUNNER_P="0", ITEM_RUN_P="0", JUMP_RUN_P="1.0", JUMPS="1", COLLECT_FIGHT_P="0", INTENT_HOLD="8", STYLE_P="0.75",
                PRO_ITEMS="1", ITEM_BELIEF="1", AMMO_PACKS="0", AIM_LEVEL="3", KEY_RATE="8", GROUND_SENSE="1", DROPS="1",
                SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1",
                RULE_WALK="1", SPEED_PAY="0.3", SPEED_PAY_RUN="0.3", RUN_TEACHER="1", STACK_KEYS="0", TEACH_KEYS_ONLY="1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="aerowalk")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--steps", type=int, default=2400, help="frames (40 a second) for 96 players")
    ap.add_argument("--teacher", default="", help="a movement run whose policy.npz gives the labels")
    a = ap.parse_args()
    if os.name == "nt":
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    os.environ.update(RUN_VARS)
    sys.path.insert(0, SIM)
    import numpy as np
    import torch
    import duel_env_ffa as E
    import test_suite as T
    ck = torch.load(a.policy, weights_only=False, map_location="cpu")
    sd = ck["model"]
    more = E.OBS_DIM - sd["enc.0.weight"].shape[1]
    path = a.policy
    if more > 0:                                              # (as sim/widen_obs.py: the new inputs at zero weight)
        sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], more, dtype=sd["enc.0.weight"].dtype)], 1)
        ck["obs_mean"], ck["obs_var"] = np.concatenate([ck["obs_mean"], np.zeros(more)]), np.concatenate([ck["obs_var"], np.ones(more)])
        ck["obs_dim"] = E.OBS_DIM
        path = os.path.join(tempfile.mkdtemp(), "widened.pt")
        torch.save(ck, path)
    pol = T.Policy(path, seed=1)
    teacher = os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz") if a.teacher else None
    for mp in a.map.split(","):                               # (one map a process is the rule for the simulator: give one map)
        env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=32, seed=1,
                        nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)), close_p=1.0, loadout="all", teacher=teacher)
        env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
        env.react_frames, env.acquire_frames = round(pol.react_ms / 25), 8
        env.kind_p, env.bot_p, env.runner_p = (1.0, 0.0, 0.0, 0.0), 0.0, 0.0
        env.loadout_p = (0.0, 1.0, 0.0, 0.0)
        env.round_t[:] = 1e9
        n = env.n
        obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
        h = pol.zeros(n)
        agree, lab_n, sp, fr = np.zeros(3), np.zeros(3), 0.0, 0
        for _ in range(a.steps):
            act, h = pol.act(obs, h)
            on = env.jrun & (env.hp > 0)
            lab = env.teach[:, :3]
            for j in range(3):
                m = on & (lab[:, j] >= 0)
                agree[j] += int((act[m, j] == lab[m, j]).sum())
                lab_n[j] += int(m.sum())
            sp += float(np.hypot(env.state[on, 3], env.state[on, 4]).sum())
            fr += int(on.sum())
            obs, r, d, info = env.step(act)
            h[np.asarray(d) > 0] = 0.0
        K = len(env.jumps)
        tr, ov, sh = (env.stats[k][:K] for k in ("jump_tries", "jump_over", "jump_short"))
        print(json.dumps(dict(map=mp, policy=os.path.basename(os.path.dirname(a.policy)) + "/" + os.path.basename(a.policy), teacher=a.teacher or None,
                              player_min=round(fr * E.DT / 60.0, 1), speed=round(sp / max(1, fr)), tries=int(tr.sum()),
                              over=round(float(ov.sum() / max(1.0, tr.sum())), 3), short=round(float(sh.sum() / max(1.0, tr.sum())), 3),
                              items_per_min=round(float(env.stats["move_arrive"]) / max(1e-9, fr * E.DT / 60.0), 2),
                              labelled=round(float(lab_n[0] / max(1, fr)), 3),
                              same_as_label=dict(zip(("forward", "side", "jump"), [round(float(x), 3) for x in agree / np.maximum(1, lab_n)])),
                              jumps=[dict(id=j["id"], need=int(j["need"]), length=int(j["length"]), rise=int(j["rise"]), tries=int(t_),
                                          over=round(float(o_ / max(1.0, t_)), 2), short=round(float(s_ / max(1.0, t_)), 2))
                                     for j, t_, o_, s_ in zip(env.jumps, tr, ov, sh)])), flush=True)


if __name__ == "__main__":
    main()

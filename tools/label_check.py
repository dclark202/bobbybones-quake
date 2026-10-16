"""The teacher's pupil test (v15, BACKLOG B-201): a player who presses exactly what the movement teacher's labels say,
with his hands (the finger limits, the mouse), alone in item runs or in jump runs on a map.

    python tools/label_check.py --map lostworld --teacher move_v15h [--runs item|jump] [--steps 2400] [--best]

Every frame his forward, strafe and jump keys and the turn of his view are the label's (no label: no key, no turn); he
never fires. Out comes what the labels alone are worth where he would be taught by them: items a minute, speed, the
share of time fast in the air, lava and fall damage a minute, deaths; the share of key requests his hand refused; in jump
runs per jump tries, over, fallen short. A teacher's labels are used on a map only if this player does well there
(the walking teacher's keys give about 6 to 7 items a minute). --best: the labels are the teacher's likeliest choice,
not a sample (needs TEACH_BEST in the simulator). One JSON line; low priority, one process, one map.
"""
import argparse
import ctypes
import json
import os
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "2")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
VARS = dict(RUNNER_P="0", COLLECT_FIGHT_P="0", INTENT_HOLD="8", STYLE_P="0", PRO_ITEMS="1", ITEM_BELIEF="1", AMMO_PACKS="0",
            AIM_LEVEL="3", KEY_RATE="8", GROUND_SENSE="1", DROPS="1", SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1",
            ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1", RULE_WALK="1", RUN_TEACHER="1", STACK_KEYS="0",
            TEACH_KEYS_ONLY="0", JUMPS="1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="lostworld")
    ap.add_argument("--teacher", required=True, help="a movement run with a policy.npz (sim/export_policy.py)")
    ap.add_argument("--runs", default="item", choices=("item", "jump"))
    ap.add_argument("--steps", type=int, default=2400)
    ap.add_argument("--best", action="store_true")
    ap.add_argument("--seed", type=int, default=1, help="the simulator's seed (another seed: a second sample of the same test)")
    a = ap.parse_args()
    if os.name == "nt":
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    os.environ.update(VARS)
    os.environ.update(ITEM_RUN_P="1.0" if a.runs == "item" else "0", JUMP_RUN_P="1.0" if a.runs == "jump" else "0")
    if a.best:
        os.environ["TEACH_BEST"] = "1"
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env_ffa as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=32, seed=a.seed,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map)), close_p=1.0, loadout="all",
                    teacher=os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz"))
    env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
    env.kind_p, env.bot_p, env.runner_p = (1.0, 0.0, 0.0, 0.0), 0.0, 0.0
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.round_t[:] = 1e9
    n = env.n
    base = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    base[:, 0], base[:, 1] = 1, 1                             # no forward or strafe key
    base[:, 3], base[:, 4] = len(E.TURN) // 2, len(E.PITCH) // 2
    env.step(base.copy())
    keys = ("move_frames", "move_speed", "move_fast", "move_arrive", "move_teach_frames", "fall_dmg", "hurt_dmg", "key_asked", "key_blocked", "suicides")
    k0 = {k: float(env.stats[k]) for k in keys}
    lab_n, fr = 0, 0
    for _ in range(a.steps):
        act = base.copy()
        lab = env.teach[:, :4]
        on = (env.run_k > 0) & (env.hp > 0)
        for j in range(4):
            act[:, j] = np.where(on & (lab[:, j] >= 0), lab[:, j], act[:, j])
        lab_n += int((on & (lab[:, 0] >= 0)).sum())
        fr += int(on.sum())
        env.step(act)
    d = {k: float(env.stats[k]) - k0[k] for k in keys}
    mins = max(1e-9, d["move_frames"] * E.DT / 60.0)
    out = dict(map=a.map, teacher=a.teacher, runs=a.runs, labels="best" if a.best else "sampled", player_min=round(mins, 1),
               labelled=round(lab_n / max(1, fr), 3), items_per_min=round(d["move_arrive"] / mins, 2),
               speed=round(d["move_speed"] / max(1.0, d["move_frames"])), fast_air=round(d["move_fast"] / max(1.0, d["move_frames"]), 3),
               lava_dmg_per_min=round(d["hurt_dmg"] / mins, 1), fall_dmg_per_min=round(d["fall_dmg"] / mins, 1),
               deaths_per_min=round(d["suicides"] / mins, 2), keys_refused=round(d["key_blocked"] / max(1.0, d["key_asked"] + d["key_blocked"]), 3))
    if a.runs == "jump":
        K = len(env.jumps)
        tr, ov, sh = (env.stats[k][:K] for k in ("jump_tries", "jump_over", "jump_short"))
        out.update(tries=int(tr.sum()), over=round(float(ov.sum() / max(1.0, tr.sum())), 3), short=round(float(sh.sum() / max(1.0, tr.sum())), 3),
                   jumps=[dict(id=j["id"], need=int(j["need"]), tries=int(t_), over=round(float(o_ / max(1.0, t_)), 2)) for j, t_, o_ in zip(env.jumps, tr, ov)])
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()

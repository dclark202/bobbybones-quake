"""The pupil test of RJ_COPY (2026-10-23): a player who presses exactly the scripted runner's labels (sim/duel_env.py
RJ_COPY), with his hands (the finger limits, the key rate, the mouse with its smoothing, low-pass and noise), in rocket
jump practice tries on a map (Aerowalk's red armor: RJ_ONLY=aerowalk:1).

    python tools/rj_copy_check.py [--cmd scratch/dry_v042a.cmd] [--map aerowalk] [--steps 4000] [--solo] [--set NAME=VALUE ...]
    python tools/rj_copy_check.py --route circle|hop2 [...]      # ROUTE_COPY=aerowalk_ra:<route> in jump runs at its jump

--route: the jump runs only (JUMP_RUN_P=1, RJ_RUN_P=0), every try at the route's jump (JUMP_FOCUS_W huge, no cap, no drop),
the starts as the run file has them (PRO_JSTART_P, JUMP_VARY, JUMP_FAR_P); out comes per try: over the gap, at the armor (the
run's arrival: the item taken), fallen short.

The simulator's switches are a run file's (`set NAME=VALUE` lines of --cmd; --set wins), then RJ_COPY=1 and RJ_RUN_P=1 (every
round a rocket jump run). Every frame each seat's outputs are the label where there is one (no label: no key, no turn, no
shot, keep the weapon). --solo: the second seat of each match presses nothing (standing in his own try). Out comes, over his
counted seats (the first of each match): tries ended, the share that arrived (the run's own rule: down within 110 units of
the landing from a flight of 8 frames or more past the take-off), died, health and armor lost per try, the share losing
RJ_COPY_BIG or more, the share of try frames labelled, the share of key requests his hand refused. One JSON line; low
priority, one process.
"""
import argparse
import ctypes
import json
import os
import re
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
SKIP = {"GPU_MEM_FRACTION", "LEARN", "LEGS_NET", "PYTHONFAULTHANDLER", "AWARE_LOG", "OPENBLAS_NUM_THREADS", "CUDA_VISIBLE_DEVICES"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default=os.path.join(ROOT, "scratch", "dry_v042a.cmd"))
    ap.add_argument("--map", default="aerowalk")
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--solo", action="store_true")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--trace", type=int, default=0, help="print seat 0's first N frames")
    ap.add_argument("--route", default="", help="ROUTE_COPY's route (circle, hop2) in jump runs instead of RJ_COPY")
    ap.add_argument("--route-file", default="aerowalk_ra")
    a = ap.parse_args()
    if os.name == "nt":
        k32_ = ctypes.windll.kernel32
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    for line in open(a.cmd):
        m = re.match(r"^set ([A-Z0-9_]+)=(.*)$", line.strip())
        if m and m.group(1) not in SKIP:
            os.environ[m.group(1)] = m.group(2)
    if a.route:
        os.environ.update(ROUTE_COPY="{}:{}".format(a.route_file, a.route), RJ_COPY="0", RJ_RUN_P="0", JUMP_RUN_P="1.0",
                          JUMP_FOCUS="{}:1".format(a.map), JUMP_FOCUS_W="1000000", JUMP_W_CAP="0", JUMP_W_DROP="0")
    else:
        os.environ.update(RJ_COPY="1", RJ_RUN_P="1.0")
    for kv in a.set:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env_ffa as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.matches, seed=a.seed,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map)), close_p=1.0, loadout="all")
    env.kind_p, env.bot_p, env.runner_p = (1.0, 0.0, 0.0, 0.0), 0.0, 0.0
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.round_t[:] = 1e9
    n = env.n
    base = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    base[:, 0], base[:, 1] = 1, 1
    base[:, 3], base[:, 4] = len(E.TURN) // 2, len(E.PITCH) // 2
    _, _, _, info = env.step(base.copy())
    lab = info.get("rj_copy", np.full((n, E.RJC_HEADS), -1, np.int8))
    keys = ("key_asked", "key_blocked", "rj_frames")
    k0 = {k: float(env.stats[k]) for k in keys}
    rc0 = np.array(env.stats.get("rj_copy", np.zeros(6)), np.float64).copy()
    ro0 = np.array(env.stats.get("route_copy", np.zeros((1, 5))), np.float64).copy()
    jt0 = float(np.sum(env.stats["jump_frames"])) if "jump_frames" in env.stats else 0.0
    ov0, tr0 = float(np.sum(env.stats["rj_over"])), float(np.sum(env.stats["rj_tries"]))
    for f in range(a.steps):
        act = base.copy()
        on = lab[:, 0] >= 0
        if a.solo:
            on = on & (np.arange(n) % 2 == 0)
        for j in range(E.RJC_HEADS):
            act[:, j] = np.where(on & (lab[:, j] >= 0), lab[:, j], act[:, j])
        if a.trace and f < a.trace:
            s = env.state[0]
            print("f{:4d} jr={} ph={} i={} try={} p=({:.0f},{:.0f},{:.0f}) v={:.0f} vz={:.0f} g={:.0f} yaw={:.1f} pit={:.1f} hp={:.0f}+{:.0f} rl={:.0f} cool={:.2f} lab={}".format(
                f, int(env.jrun[0]), int(env.rc_ph[0]), int(env.rc_i[0]), int(env.rjrun[0]), s[0], s[1], s[2], float(np.hypot(s[3], s[4])), s[5], s[6], float(env.yaw[0]), float(env.pitch[0]),
                float(env.hp[0]), float(env.armor[0]), float(env.ammo[0, E.RL]), float(env.cool[0]), lab[0].tolist()), flush=True)
        _, _, _, info = env.step(act)
        lab = info["rj_copy"]
    d = {k: float(env.stats[k]) - k0[k] for k in keys}
    if a.route:
        ro = np.array(env.stats.get("route_copy", np.zeros((1, 5))), np.float64)
        ro = ro - (ro0 if ro0.shape == ro.shape else 0.0)
        e_ = max(1.0, ro[0, 1])
        jf_ = float(np.sum(env.stats["jump_frames"])) - jt0
        out = dict(map=a.map, route=a.route, steps=a.steps, seats=n, solo=a.solo, sets=a.set, tries_ended=int(ro[0, 1]),
                   over=round(ro[0, 2] / e_, 3), arrived=round(ro[0, 3] / e_, 3), fell_short=round(ro[0, 4] / e_, 3),
                   labelled=round(ro[0, 0] / max(1.0, jf_ / (2.0 if getattr(env, "count_even", False) else 1.0)), 3),
                   keys_refused=round(d["key_blocked"] / max(1.0, d["key_asked"] + d["key_blocked"]), 3))
        print("RESULT " + json.dumps(out), flush=True)
        return
    rc = np.array(env.stats.get("rj_copy", np.zeros(6)), np.float64) - rc0
    ended = max(1.0, rc[1])
    out = dict(map=a.map, steps=a.steps, seats=n, solo=a.solo, sets=a.set,
               tries_ended=int(rc[1]), arrived=round(rc[2] / ended, 3), died=round(rc[3] / ended, 3),
               lost_per_try=round(rc[4] / ended, 1), lost_big=round(rc[5] / ended, 3),
               run_rule=dict(tries=int(np.sum(env.stats["rj_tries"]) - tr0), over=int(np.sum(env.stats["rj_over"]) - ov0)),
               labelled=round(rc[0] / max(1.0, d["rj_frames"]), 3),
               keys_refused=round(d["key_blocked"] / max(1.0, d["key_asked"] + d["key_blocked"]), 3))
    print("RESULT " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()

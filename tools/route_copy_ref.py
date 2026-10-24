"""The scripted runner's references for ROUTE_COPY (sim/duel_env.py; the owner, 2026-10-23: "one route that works that he has
to use when he wants to get there"): Aerowalk's red armor over the pros' gap jump (sim/pro_gaps/aerowalk.json id 1, the
jump runs' jump index 0) by a CIRCLE JUMP from a standing start, and by a TWO-HOP strafe jump (a circle-jump hop, then the
gap jump on its landing).

    python tools/route_copy_ref.py [--cmd scratch/dry_v042a.cmd] [--out sim/route_copy_aerowalk_ra.json]

A grid of open-loop executions (the keys pressed by the script, the view put where it should be, no hand limits: the
search's job is to find the maneuver, the pupil test, tools/rj_copy_check.py --route, checks it with his hands), each made
from its start and from 8 starts moved by 12 units and the view by 6 degrees; per route the execution that clears the gap
from the most of its 9 starts (then the nearest landing) is kept: its staging spot and view, and its frames from the start
to the gap jump's take-off (place, velocity, on the floor, view yaw, keys). duel_env reads the file under ROUTE_COPY.
The simulator's switches are the run file's. One process, low priority.
"""
import argparse
import ctypes
import json
import math
import os
import re
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
SKIP = {"GPU_MEM_FRACTION", "LEARN", "LEGS_NET", "PYTHONFAULTHANDLER", "AWARE_LOG", "OPENBLAS_NUM_THREADS", "CUDA_VISIBLE_DEVICES"}
WISH, AIRACC, DTS = 320.0, 1.0, 0.008
LAND_R = 110.0


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def steer_yaw(vel, target_heading, side, ground, extra=0.0):
    """view yaw for W + side (side +1 = D, -1 = A): the wish direction at the angle to the velocity that gains most, turned
    toward the side; extra degrees beyond it turn the velocity faster (as duel_env's ROUTE_COPY air steering)"""
    v = math.hypot(vel[0], vel[1])
    h = math.degrees(math.atan2(vel[1], vel[0])) if v > 30 else target_heading
    acc = (10.0 if ground else AIRACC) * WISH * DTS
    th = math.degrees(math.acos(max(-1.0, min(1.0, (WISH - acc) / v)))) if v > WISH - acc else 0.0
    th = min(88.0, th + extra)
    return h - side * th + side * 45.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default=os.path.join(ROOT, "scratch", "dry_v042a.cmd"))
    ap.add_argument("--out", default=os.path.join(SIM, "route_copy_aerowalk_ra.json"))
    ap.add_argument("--map", default="aerowalk")
    ap.add_argument("--jump", type=int, default=1, help="the gap jump's id in sim/pro_gaps/<map>.json")
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
    os.environ.update(RUNNER_P="0", ITEM_RUN_P="0", JUMP_RUN_P="0", RJ_RUN_P="0", GAME_P="0", PRO_START_P="0", ROUTE_COPY="")
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env_ffa as E
    gaps = json.load(open(os.path.join(SIM, "pro_gaps", a.map + ".json")))["jumps"]
    g = [j for j in gaps if int(j["id"]) == a.jump][0]
    A, B = np.array(g["take_off"], np.float64), np.array(g["landing"], np.float64)
    U = (B - A)[:2] / np.linalg.norm((B - A)[:2])
    YAW_U = math.degrees(math.atan2(U[1], U[0]))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=7, loadout="mg",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map)))
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.round_t[:] = -1e9
    env.key_limits, env.human_aim, env.level = False, False, 1.0
    ra_i = [i for i, p in enumerate(env.item_pos) if np.linalg.norm(p[:2] - B[:2]) < 200 and abs(p[2] - B[2]) < 80][0]
    RA = np.asarray(env.item_pos[ra_i], np.float64)

    def idle():
        x = np.zeros((env.n, len(E.ACTION_DIMS)), np.int64)
        x[:, 0], x[:, 1], x[:, 3], x[:, 4] = 1, 1, len(E.TURN) // 2, len(E.PITCH) // 2
        return x

    def reset(start, yaw):
        env.ra[:] = False
        sp = np.asarray(env.spawns, np.float32)[:, :3]
        q = sp[int(np.linalg.norm(sp - A, axis=1).argmax())]
        env.w.reset(1, (float(q[0]), float(q[1]), float(q[2]) + 9.0), (0, 0, 0), 0.0)
        env._fresh(1, 0.0)
        env.w.reset(0, (float(start[0]), float(start[1]), float(A[2]) + 9.0), (0, 0, 0), float(yaw))
        env._fresh(0, float(yaw))
        env.state = env.w.state()
        env.hp[0], env.armor[0] = 125.0, 0.0
        env.item_up[0, :], env.item_t[0, :] = True, 0.0
        env.run_k[:] = -1

    def one(start, P, yaw_jit=0.0, rec=False, max_f=260, pre=14):
        """the aerovid runner's circle jump (hops=1) or two hops (hops=2), as its open loop; -> (made, frames, out)"""
        side, hops = P["side"], P["hops"]
        H = YAW_U + P["h"]
        view_end = H + side * (45.0 - 22.0)
        yaw_start = view_end + side * P["sweep"] + yaw_jit
        reset(start, yaw_start)
        frames = []
        land_f, gap_jf, hop_jf, first_land, took, top = -1, -1, -1, None, False, -1e9
        jf_plan = pre + P["nc"]
        cur_side = side
        hop_ask = gap_ask = -1
        hop_sp = take_sp = take_p = None
        act = idle()
        for f in range(max_f):
            env.round_t[:] = -1e9
            s = env.state[0]
            p, v, gr = s[:3].copy(), s[3:6].copy(), s[6] > 0.5
            act[:] = idle()
            hv = math.degrees(math.atan2(v[1], v[0])) if math.hypot(v[0], v[1]) > 30 else H
            if f < pre:
                yaw = yaw_start
            elif f < jf_plan:
                yaw = yaw_start - side * P["sweep"] * (f - pre + 1) / P["nc"]
                act[0, 0], act[0, 1] = 2, 1 + side
            elif land_f >= 0:
                yaw = math.degrees(math.atan2(RA[1] - p[1], RA[0] - p[0]))
                act[0, 0] = 2
            else:
                if gap_jf < 0 and hops == 2 and hop_jf >= 0:
                    tgt = math.degrees(math.atan2(*(A[:2] + U * 60 - p[:2])[::-1]))
                else:
                    tgt = math.degrees(math.atan2(*(B[:2] - p[:2])[::-1]))
                err = wrap(tgt - hv)
                if not gr and abs(err) > 4.0:
                    cur_side = 1 if err < 0 else -1
                yaw = steer_yaw(v, tgt, cur_side, gr, extra=0.3 * abs(err))
                act[0, 0], act[0, 1] = 2, 1 + cur_side
            if gr and f >= jf_plan and land_f < 0:            # (the jump held on the floor until he is up: a jump just after a
                if hop_jf < 0 and hops == 2:                  # landing may not be taken at once, DUEL_QL)
                    act[0, 2], hop_ask = 1, f
                elif gap_jf < 0 and (hops == 1 or hop_jf >= 0):
                    act[0, 2], gap_ask = 1, f
            env.yaw[0], env.pitch[0] = yaw, 0.0
            env.mv[0] = 0.0
            if rec and gap_jf < 0:
                frames.append(dict(p=p.round(2).tolist(), v=v.round(2).tolist(), g=int(gr), yaw=round(float(yaw), 3),
                                   k=[int(act[0, 0]), int(act[0, 1]), int(act[0, 2])], hop=int(hop_jf >= 0)))
            env.step(act)
            s = env.state[0]
            if act[0, 2] == 1 and s[6] < 0.5 and s[5] > 100:   # up: the take-off of the hop or of the gap jump
                if hops == 2 and hop_jf < 0:
                    hop_jf, cur_side, hop_sp = f, -side, float(math.hypot(s[3], s[4]))
                elif gap_jf < 0 and (hops == 1 or hop_jf >= 0) and f > hop_jf + 3:
                    gap_jf, take_sp, take_p = f, float(math.hypot(s[3], s[4])), s[:3].round().tolist()
            if env.armor[0] > 50:
                took = True
            if gap_jf >= 0 and f > gap_jf + 2:
                top = max(top, float(s[2] - A[2]))
                if land_f < 0 and s[6] > 0.5:
                    land_f, first_land = f, s[:3].copy()
            if s[2] < A[2] - 220 and f > max(gap_jf, 0) + 45:
                break
            if land_f >= 0 and ((took and f > land_f + 10) or f > land_f + 40):
                break
            if gap_jf < 0 and f > 200:
                break
        ok = first_land is not None and np.linalg.norm(first_land[:2] - B[:2]) < LAND_R and first_land[2] > B[2] - 30
        tk = None if gap_jf < 0 else dict(f=gap_jf)
        return bool(ok), frames, dict(took=took, land_d=None if first_land is None else float(np.linalg.norm(first_land[:2] - B[:2])),
                                       gap_jf=gap_jf, hop_jf=hop_jf, take=tk, hop_sp=hop_sp, take_sp=take_sp, take_p=take_p,
                                       land=None if first_land is None else first_land.round().tolist())

    def place(P):
        """the start moved so that the gap jump (hops=1) or the first hop's landing (hops=2) is at the pros' take-off"""
        st = A[:2] - U * (200.0 if P["hops"] == 1 else 330.0)
        for _ in range(4):
            ok, fr, out = one(st, P, rec=True)
            if not fr:
                return st
            if P["hops"] == 1:
                at = fr[-1]["p"] if out["gap_jf"] >= 0 else None
            else:
                hl = [x for x in fr if x["hop"] and x["g"]]
                at = hl[0]["p"] if hl else None
            if at is None:
                return st
            sh = A[:2] - np.array(at[:2])
            if np.hypot(*sh) < 6:
                break
            if np.hypot(*sh) > 60:                            # (no wild moves: a start moved far off its way is junk)
                sh = sh * 60.0 / np.hypot(*sh)
            st = st + sh
        return st

    rows = []
    V = np.array([-U[1], U[0]])
    for hops in ((2,) if os.environ.get("RCR_ONLY2") else (1, 2)):
        for sweep in (70.0, 100.0):
            for nc in ((14, 20) if hops == 1 else (14,)):
                for h in ((-30.0, -15.0, 0.0, 15.0) if hops == 1 else (-20.0, 0.0, 20.0)):
                    for side in (1, -1):
                        P = dict(hops=hops, sweep=sweep, nc=nc, h=h, side=side)
                        st = place(P)
                        ok0, _, out0 = one(st, P)
                        if not ok0:
                            rows.append(dict(P=P, start=st.tolist(), made=0, out=out0))
                            print(json.dumps(rows[-1]), flush=True)
                            continue
                        made = 1
                        for du, dv, yj in ((12, 0, 0), (-12, 0, 0), (0, 12, 0), (0, -12, 0), (0, 0, 6), (0, 0, -6), (8, 8, 3), (-8, -8, -3)):
                            ok_, _, _ = one(st + du * U + dv * V, P, yaw_jit=yj)
                            made += int(ok_)
                        rows.append(dict(P=P, start=st.tolist(), made=made, land_d=out0["land_d"]))
                        print(json.dumps(rows[-1]), flush=True)
    res = dict(what=__doc__.strip().splitlines()[0], map=a.map, jump_id=a.jump, A=A.tolist(), B=B.tolist(), RA=RA.tolist(),
               routes={})
    for name, hops in (("circle", 1), ("hop2", 2)):
        cand = [r for r in rows if r["P"]["hops"] == hops and r["made"] > 0]
        if not cand:
            print("no {} execution clears the gap".format(name), flush=True)
            continue
        best = max(cand, key=lambda r: (r["made"], -(r.get("land_d") or 1e9)))
        P, st = best["P"], np.array(best["start"])
        ok, fr, out = one(st, P, rec=True)
        H = YAW_U + P["h"]
        res["routes"][name] = dict(P=P, made_of_9=best["made"], land_d=out["land_d"], start=[float(st[0]), float(st[1]), float(A[2])],
                                   start_yaw=float(H + P["side"] * (45.0 - 22.0) + P["side"] * P["sweep"]), frames=fr)
        print("{}: {} made {} of 9, {} frames to the take-off".format(name, P, best["made"], len(fr)), flush=True)
    json.dump(res, open(a.out, "w"), indent=0)
    print("wrote", a.out, flush=True)


if __name__ == "__main__":
    main()

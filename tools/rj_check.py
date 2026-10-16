"""The pros' rocket jumps in the simulator (B-252, 2026-10-16): can a player who presses the right keys clear them, and do
his hands allow the jump and the shot together?

    python tools/rj_check.py clear --map bloodrun [--out data/rj_check/bloodrun.json]
    python tools/rj_check.py hand [--map bloodrun]

clear: per rocket jump of docs/pro_rocket_jumps.json that the walking map has (sim/rocket_jumps.py; the ones duel_env's
rocket jump runs use, RJ_RUN_P), a scripted player with the rocket launcher and the pros' stack at that take-off tries a
grid of plain executions (until the first that clears it): standing at the take-off, running at it from 150 units back, or
coming in the air at 350, 450 or 550 u/s (a strafe jump's arrival) and firing over it; the view toward the landing (then
10 degrees either side) and down at 55, 70 or 88 degrees; jump and fire on the same frame or the shot 1 frame after; in
the air forward held or no key. No finger limits, no aim limits, the view held where it is put: the keys only.
A try clears the link when its first landing after a flight of 8 frames or more is within 110 units of the pros' landing
(the run's own rule). Prints per link the tries that cleared and the best; one JSON line a map at the end.

hand: his own limits (finger limits, KEY_RATE, the view's inertia and its ease back toward level, the flick cap and the
hand noise at AIM_LEVEL): from a level view at rest, the frames to bring the view down to 50, 60, 70, 80 and 88 degrees
with the strongest pitch command and the angle it holds while he presses on; then the jump on the first frame his left
hand reads the keys and the shot 0 to 4 frames after: the frames between the jump and the rocket's leaving, and the view
at the shot.

The simulator switches: v0.3.1's set with RL_QL and the physics (QL_FLOAT, QL_FWD, QL_LAND, QL_JUMP); any NAME=VALUE in
the environment wins. Low priority, one process (a map a process).
"""
import argparse
import ctypes
import json
import math
import os
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
VARS = dict(SHOT_MASK="1", LAVA="1", WALK_FIX="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1", PROJ_SEE="1",
            AUTO_SWITCH="1", AIM_LEVEL="3", AMMO_PACKS="0", STYLE_P="0", QL_MOVE="1", RULE_WALK="1", KEY_RATE="8",
            GROUND_SENSE="1", INTENT_HOLD="8", ITEM_BELIEF="1", GL_QL="1", RUNNER_P="0", ITEM_RUN_P="0", JUMP_RUN_P="0",
            RL_QL="1", QL_FLOAT="1", QL_FWD="1", QL_LAND="1", QL_JUMP="1", RJ_RUN_P="0.000001")


def low_priority():
    if os.name == "nt":
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)


def make_env(mp):
    for k, v in VARS.items():
        os.environ.setdefault(k, v)
    sys.path.insert(0, SIM)
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=7, loadout="mg",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.round_t[:] = -1e9
    return E, env


def idle(E, n):
    a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    a[:, 0], a[:, 1], a[:, 3], a[:, 4] = 1, 1, int(np.argmin(np.abs(E.TURN))), int(np.argmin(np.abs(E.PITCH)))
    return a


def arm(E, env, i, stack):
    env.hp[i], env.armor[i] = E.RJM.stack(stack)
    env.has[i] = False
    env.ammo[i] = 0.0
    env.has[i, E.ALWAYS], env.has[i, E.MG], env.has[i, E.RL] = True, True, True
    env.ammo[i, E.MG], env.ammo[i, E.RL] = 100.0, 25.0
    env.weapon[i], env.cool[i], env.fire_cd[i] = E.RL, 0.0, 0.0


def park(E, env, far_from):
    """the other seat: at the spawn point furthest from the link, standing; no rocket of an earlier try left in the air
    (one that flew off would explode in a later try: the tries must not depend on their order)"""
    env.ra[:] = False
    sp = np.asarray(env.spawns, np.float32)[:, :3]
    p = sp[int(np.linalg.norm(sp - far_from, axis=1).argmax())]
    env.w.reset(1, (float(p[0]), float(p[1]), float(p[2]) + 9.0), (0, 0, 0), 0.0)
    env._fresh(1, 0.0)


def place(E, env, p, yaw, vel=(0, 0, 0), dz=9.0):
    env.w.reset(0, (float(p[0]), float(p[1]), float(p[2]) + dz), tuple(float(v) for v in vel), float(yaw))
    env._fresh(0, float(yaw))
    env.state = env.w.state()


def one_try(E, env, r, start, yaw, pitch, delay, air, runup, hop=0.0):
    """one scripted execution; -> (cleared, distance of the first landing from the pros' landing, top above the take-off,
    frames in the air). hop: he comes in the air at this speed (a strafe jump's arrival) and fires over the take-off"""
    A, B = r["a"], r["b"]
    park(E, env, A)
    if hop > 0:
        uu = np.array([math.cos(math.radians(yaw)), math.sin(math.radians(yaw))], np.float32)
        p0 = A[:2] - uu * hop * 0.15
        place(E, env, (p0[0], p0[1], A[2]), yaw, vel=(uu[0] * hop, uu[1] * hop, 120.0), dz=0.0)
    else:
        place(E, env, start, yaw)
    arm(E, env, 0, r["stack"])
    env.run_k[:] = -1
    a = idle(E, env.n)
    u = np.array([math.cos(math.radians(yaw)), math.sin(math.radians(yaw))], np.float32)
    jf, f, air_n, top = -1, 0, 0, -1e9
    for f in range(320):
        env.round_t[:] = -1e9
        env.yaw[0], env.pitch[0] = yaw, (pitch if (jf >= 0 or f >= 2) else 0.0)
        env.mv[0] = 0.0
        a[0] = idle(E, 1)[0]
        s = env.state
        p = s[0, :3]
        if jf < 0 and hop > 0:
            a[0, 0] = 2
            if float(np.dot(p[:2] - A[:2], u)) >= -8.0 or f > 20:
                jf = f
        elif jf < 0:
            if runup:
                a[0, 0] = 2
                go = float(np.dot(p[:2] - A[:2], u)) >= -8.0 or f > 120
            else:
                go = f >= 4
            if go and s[0, 6] > 0.5:
                jf = f
        if jf >= 0:
            if f == jf and hop <= 0:
                a[0, 2] = 1
            if f == jf + delay:
                a[0, 5] = 1
            if air == "fwd" or (runup and f < jf):
                a[0, 0] = 2
        if jf < 0 and runup:
            a[0, 0] = 2
        prev = env.state.copy()
        env.step(a)
        s = env.state
        if env.hp[0] <= 0 or s[0, 2] < prev[0, 2] - 400:
            return False, 1e9, top, air_n
        if jf >= 0 and f > jf and not (hop > 0 and f <= jf + delay + 1):
            top = max(top, float(s[0, 2] - A[2]))
            landed = (s[0, 6] > 0.5) | ((prev[0, 5] < 0.0) & (s[0, 5] > 0.0))
            if landed:
                if air_n >= 8:
                    d = float(np.linalg.norm(s[0, :3] - B))
                    return d < E.RJ_LAND, d, top, air_n
                if f > jf + 3:
                    return False, float(np.linalg.norm(s[0, :3] - B)), top, air_n
                air_n = 0
            else:
                air_n += 1
    return False, 1e9, top, air_n


def clear(a):
    E, env = make_env(a.map)
    env.key_limits, env.human_aim, env.level = False, False, 1.0     # (the keys only: no finger or aim limits, the view held)
    R = env.route
    out = []
    only = {int(x) for x in (a.only or "").split(",") if x.strip()}
    for k, r in enumerate(env.rjs):
        if only and r["id"] not in only:
            continue
        A, B = r["a"], r["b"]
        d = np.hypot(R.nodes[:, 0] - A[0], R.nodes[:, 1] - A[1])
        ok = ~R.dead & (np.abs(R.nodes[:, 2] - A[2]) < 30.0)
        at = R.nodes[int(np.where(ok, d, 1e9).argmin())]
        yaw0 = math.degrees(math.atan2(B[1] - A[1], B[0] - A[0]))
        u = np.array([math.cos(math.radians(yaw0)), math.sin(math.radians(yaw0))], np.float32)
        back = A[:2] - 150.0 * u
        db = np.hypot(R.nodes[:, 0] - back[0], R.nodes[:, 1] - back[1])
        bi = int(np.where(ok, db, 1e9).argmin())
        starts = [("stand", at)] + ([("run", R.nodes[bi])] if db[bi] < 40.0 else []) + [("hop{}".format(v_), at) for v_ in (350, 450, 550)]
        won, best, tries = [], (1e9, None), 0
        for yo in (0.0, -10.0, 10.0):
            for sname, st in starts:
                yaw = math.degrees(math.atan2(A[1] - st[1], A[0] - st[0])) + yo if sname == "run" else yaw0 + yo
                hop = float(sname[3:]) if sname.startswith("hop") else 0.0
                for pitch in (55.0, 70.0, 88.0):
                    for delay in ((0,) if hop else (0, 1)):
                        for air in (("fwd",) if hop else ("fwd", "none")):
                            if won:
                                continue                  # (the first execution that clears it is enough)
                            c, dist, top, an = one_try(E, env, r, st, yaw, pitch, delay, air, sname == "run", hop)
                            tries += 1
                            if dist < best[0]:
                                best = (dist, dict(start=sname, yaw_off=yo, pitch=pitch, delay=delay, air=air, top=round(top), air_frames=an))
                            if c:
                                won.append(dict(start=sname, yaw_off=yo, pitch=pitch, delay=delay, air=air, top=round(top), d=round(dist)))
            if won:
                break
        row = dict(id=r["id"], n=r["n"], pros_top=round(r["top"]), dz=round(r["rise"]), length=round(r["length"]),
                   pros_pitch=round(r["pitch"]), tries=tries, cleared=len(won), best_d=round(best[0]) if best[0] < 1e8 else None,
                   best=best[1], first=won[0] if won else None)
        out.append(row)
        print(json.dumps(row), flush=True)
    res = dict(map=a.map, links_in_file=len(json.load(open(E.RJM.PATH)).get(a.map, {}).get("links", [])),
               links_on_walking_map=len(env.rjs), clearable=sum(1 for r_ in out if r_["cleared"]),
               clearable_ids=[r_["id"] for r_ in out if r_["cleared"]])
    print("RESULT " + json.dumps(res), flush=True)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(dict(res, links=out), open(a.out, "w"), indent=1)


def hand(a):
    """his own limits, as the simulator applies them to a network's seat"""
    E, env = make_env(a.map)
    R = env.route
    sp = np.asarray(env.spawns, np.float32)[:, :3]
    down = int(np.argmax(E.PITCH))
    res = dict(aim_level=os.environ.get("AIM_LEVEL"), key_every=E.KEY_EVERY, finger_hold_thumb=int(E.FINGER_HOLD[E.THUMB]),
               key_rate=E.KEY_RATE, level=env.level, pitch_cmd_max=float(E.PITCH[down]), turn_cap=E.TURN_CAP,
               mouse_smooth=E.MOUSE_SMOOTH, motor_noise=E.MOTOR_NOISE, motor_base=E.MOTOR_BASE, rows=[])
    for target in (50.0, 60.0, 70.0, 80.0, 88.0):
        for delay in range(5):
            for rep in range(4):
                park(E, env, sp[0])
                p = sp[0]
                place(E, env, p, 0.0)
                arm(E, env, 0, 200.0)
                env.run_k[:] = -1
                f_reach, jf, ask_f, shot_f, pitch_shot, held = -1, -1, -1, -1, None, []
                ammo0 = float(env.ammo[0, E.RL])
                for f in range(200):
                    env.round_t[:] = -1e9
                    act = idle(E, env.n)
                    if env.pitch[0] < target - 0.5:
                        act[0, 4] = down                  # the strongest look-down
                    else:                                 # what holds it against the ease back toward level
                        act[0, 4] = int(np.argmin(np.abs(E.PITCH - (1.0 - env.level) * env.pitch[0])))
                        if target >= 88.0:
                            act[0, 4] = int(np.argmin(np.abs(E.PITCH - 8.0)))   # (all the way down: the view stops at 89)
                    if f_reach < 0 and env.pitch[0] >= target - 0.5:
                        f_reach = f
                    dec_now = (env.key_tick + 1) % E.KEY_EVERY == 0      # his left hand reads the keys on this frame (seat 0)
                    if f_reach >= 0 and ask_f < 0 and dec_now:
                        ask_f = f                         # the jump asked on the frame his hand reads it ...
                    if ask_f >= 0 and jf < 0:
                        act[0, 2] = 1
                    if ask_f >= 0 and f >= ask_f + delay and shot_f < 0:
                        act[0, 5] = 1                     # ... and the click this many frames after
                    vz0, on0 = float(env.state[0, 5]), env.state[0, 6] > 0.5
                    env.step(act)
                    if f_reach >= 0:
                        held.append(float(env.pitch[0]))
                    if jf < 0 and on0 and float(env.state[0, 5]) > vz0 + 100.0:
                        jf = f
                    if shot_f < 0 and float(env.ammo[0, E.RL]) < ammo0:
                        shot_f, pitch_shot = f, float(env.pitch[0])
                    if shot_f >= 0 and jf >= 0 and f > max(shot_f, jf) + 2:
                        break
                res["rows"].append(dict(target=target, delay_asked=delay, rep=rep, frames_to_pitch=f_reach,
                                        jump_frame=jf, shot_frame=shot_f, jump_to_shot=(shot_f - jf) if (shot_f >= 0 and jf >= 0) else None,
                                        pitch_at_shot=round(pitch_shot, 1) if pitch_shot is not None else None,
                                        pitch_held_min=round(min(held), 1) if held else None))
    by = {}
    for r_ in res["rows"]:
        by.setdefault((r_["target"], r_["delay_asked"]), []).append(r_)
    for (t_, d_), rs in sorted(by.items()):
        js = [r_["jump_to_shot"] for r_ in rs if r_["jump_to_shot"] is not None]
        print("look-down {:>4.0f}: {:>2} frames to reach it; shot asked {} frame(s) after the jump: jump-to-shot {} ; view at the shot {}".format(
            t_, int(np.median([r_["frames_to_pitch"] for r_ in rs])), d_, js, [r_["pitch_at_shot"] for r_ in rs]), flush=True)
    print("RESULT " + json.dumps({k: v for k, v in res.items() if k != "rows"}), flush=True)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("clear", "hand"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="", help="clear: these links only (their numbers in the file's list)")
    a_ = ap.parse_args()
    low_priority()
    import numpy as np  # noqa: E402
    globals()["np"] = np
    if a_.what == "clear":
        clear(a_)
    else:
        hand(a_)

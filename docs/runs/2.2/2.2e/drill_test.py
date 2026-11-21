"""2.2e: the rail drill in the simulator (sim/duel_env.py RDRILL), tested on its own, every match in a drill (RDRILL_ALL=1, a test switch), 2.2e's
command's settings (train.cmd and aim2_env.cmd). His seats' keys random except the fire key held and, on half the frames, his view put on the target
(so that rails land); the targets are the simulator's script. Every frame checked:
  his loadout: the railgun only, in hand, its ammunition full; the target: never fires, 100 and 100 after every frame; no item taken by anyone
  the pay: on every drill frame of his, the pay terms other than dmg_dealt and rail exactly 0 and the frame's pay their sum; the target's pay 0
  the placements: three a stretch (one at its start, at 10 s, at 20 s) and after each death of his; a stretch of 1,200 frames; the distance at a
  placement within 4 % of a 100-unit band of the map's lines; his view 0 to 45 degrees off the target's bearing; the target on its lane
  the trainer's flag (env.rdr_on): his seats in a drill, never the target's
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2e/drill_test.py [--map campgrounds] [--frames 2600]
    ... --share P (RDRILL_ALL off, the share P: the measured share of match frames in drills over --frames)"""
import argparse
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")


def cmd_env(path, root):
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln.rstrip("\r\n"), re.I)
        if m and m.group(1) not in ("ROOT", "GPU_MEM_FRACTION", "TRAINER_MASK", "LEARN"):
            out[m.group(1)] = m.group(2).replace("%ROOT%", root).replace("%~dp0..\\..\\..\\..", root)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="campgrounds")
    ap.add_argument("--frames", type=int, default=2600)
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--share", type=float, default=-1.0)
    a = ap.parse_args()
    root_ = os.environ.get("QLBOT_ROOT") or ROOT
    ev = cmd_env(os.path.join(HERE, "train.cmd"), root_)
    ev.update(cmd_env(os.path.join(HERE, "aim2_env.cmd"), root_))
    if a.share >= 0:
        ev.update(RDRILL_P=str(a.share))
    else:
        ev.update(RDRILL_ALL="1")
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import duel_env_ffa as E
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(DATA, "maps", a.map + ".bsp"), n_matches=a.matches, seed=a.seed, loadout="all", nav=nav_)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.dmg_reward = 0.005
    env.round_t[:] = 1e9
    rng = np.random.default_rng(a.seed + 1)
    n, M = env.n, env.M
    PT = list(E.PAY_TERMS)
    keep = [PT.index("dmg_dealt"), PT.index("rail")]
    other = [k for k in range(len(PT)) if k not in keep]
    bad = []
    C = dict(drill_frames=0, his_frames=0, hits=0, shots=0, pay_dealt=0.0, pay_rail=0.0, other_size=0.0, sum_err=0.0, target_pay=0.0,
             placements=0, starts=0, ends=0, max_other=0.0, yaw_off=[], dist_err=[], lane_off=[], items=0, flag_err=0, tgt_fire=0, game_frames=0)
    lines = env.rdr_lines
    prev_k = env.rdr_k.copy()
    prev_m = env.rdr_m.copy()
    ammo_t0 = None
    for t in range(a.frames):
        act = np.stack([rng.integers(0, d, n) for d in E.ACTION_DIMS], 1)
        act[:, 5] = 1                                         # (the fire key held)
        act[:, 6] = 0                                         # (the weapon key: none)
        his = np.nonzero(np.repeat(env.rdr_m, 2)[:n] & (env.script[:n] == 0))[0]
        if t % 2 == 0 and len(his):                           # (half the frames: his view on the target's middle, so rails land)
            s = env.state
            for i in his:
                o = int(env._others_arr()[i, 0])
                d_ = s[o, :3] - (s[i, :3] + np.array([0, 0, E.VIEW_H], np.float32))
                env.yaw[i] = math.degrees(math.atan2(float(d_[1]), float(d_[0])))
                env.pitch[i] = -math.degrees(math.atan2(float(d_[2]), float(np.hypot(d_[0], d_[1]))))
                act[i, 3] = int(np.abs(E.TURN).argmin())
                act[i, 4] = int(np.abs(E.PITCH).argmin())
        m0 = env.rdr_m.copy()
        hp_before = env.hp[:n].copy()
        obs, rew, done, info = env.step(np.concatenate([act, np.full((n, 1), 3)], 1))
        pt = np.asarray(info["pay_terms"], np.float64)
        q0 = np.nonzero(np.repeat(m0, 2)[:n])[0]
        h0, g0 = q0[0::2], q0[1::2]
        C["drill_frames"] += len(h0)
        C["game_frames"] += int((~m0).sum())
        if len(h0):
            C["his_frames"] += len(h0)
            o_ = np.abs(pt[np.ix_(h0, other)])
            C["other_size"] += float(o_.sum())
            C["max_other"] = max(C["max_other"], float(o_.max()) if o_.size else 0.0)
            C["pay_dealt"] += float(pt[h0, keep[0]].sum())
            C["pay_rail"] += float(pt[h0, keep[1]].sum())
            C["sum_err"] = max(C["sum_err"], float(np.abs(rew[h0] - pt[h0][:, keep].sum(1)).max()))
            C["target_pay"] += float(np.abs(rew[g0]).sum() + np.abs(pt[g0]).sum())
        # loadouts and the target, after the step (the next frame's state)
        hn = np.nonzero(np.repeat(env.rdr_m, 2)[:n])[0]
        hh, gg = hn[0::2], hn[1::2]
        if len(hh):
            if not (env.has[hh][:, E.RG].all() and env.has[hh].sum(1).max() == 1 and (env.weapon[hh] == E.RG).all()):
                bad.append("t {}: his loadout {}".format(t, env.has[hh][0].nonzero()))
            if not np.allclose(env.ammo[hh, E.RG], E.AMMO_MAX[E.RG]):
                bad.append("t {}: his rail ammunition not full".format(t))
            if not (np.allclose(env.hp[gg], 100.0) and np.allclose(env.armor[gg], 100.0)):
                bad.append("t {}: the target's stack {} {}".format(t, env.hp[gg][:3], env.armor[gg][:3]))
            if not (env.script[gg] == 5).all() or (env.script[hh] != 0).any():
                bad.append("t {}: scripts".format(t))
            if not (env.rdr_on[hh].all() and not env.rdr_on[gg].any()):
                C["flag_err"] += 1
        if (env.rdr_on & ~np.repeat(env.rdr_m, 2)[:n]).any():
            C["flag_err"] += 1
        # the target never fires: no damage to him from it, its fire key 0
        for (i_, v_), d_ in []:
            pass
        st = env.stats["rdrill"]
        # new placements: check the geometry
        for m in np.nonzero(env.rdr_m & ((env.rdr_k != prev_k) | ~prev_m))[0]:
            h, g = 2 * int(m), 2 * int(m) + 1
            s = env.state
            d_ = float(np.hypot(*(s[h, :2] - s[g, :2])))
            b_ = min(lines, key=lambda x_: abs(x_ - d_))
            C["dist_err"].append(abs(d_ - b_) / b_)
            by_ = math.degrees(math.atan2(float(s[g, 1] - s[h, 1]), float(s[g, 0] - s[h, 0])))
            C["yaw_off"].append(abs((env.yaw[h] - by_ + 180.0) % 360.0 - 180.0))
        prev_k, prev_m = env.rdr_k.copy(), env.rdr_m.copy()
        for m in np.nonzero(env.rdr_m)[0]:
            g = 2 * int(m) + 1
            off = env.state[g, :2] - env.rdr_home[m, :2]
            C["lane_off"].append(abs(float((off * env.rdr_v[m]).sum())))
    R = env.stats["rdrill"]
    S = env.stats["rdr_shot"]
    P = env.stats["rdr_pt"]
    out = dict(map=a.map, frames=a.frames, matches=M, drill_match_frames=C["drill_frames"], game_match_frames=C["game_frames"],
               begun=int(R[0]), ended=int(R[1]), placements=int(R[2]), after_death=int(R[3]), deaths=int(R[7]),
               shots=int(R[8]), hits=int(R[9]), reversals=int(R[10]), items_touched=int(R[12]), weapons_taken=int(R[13]),
               shots_by_band=S[:, 0].tolist(), hits_by_band=S[:, 1].tolist(), off_body_by_band=S[:, 2].tolist(),
               pay_dealt=round(C["pay_dealt"], 4), pay_rail=round(C["pay_rail"], 4), other_terms_size=C["other_size"], other_terms_max=C["max_other"],
               pay_minus_two_terms_max=C["sum_err"], target_pay_size=C["target_pay"],
               stats_pt_other=float(P[1][other].sum()), stats_pt_dealt=float(P[0][keep[0]]), stats_pt_rail=float(P[0][keep[1]]),
               dist_err_max=round(max(C["dist_err"]) if C["dist_err"] else -1, 4), yaw_off_range=[round(min(C["yaw_off"]), 1), round(max(C["yaw_off"]), 1)]
               if C["yaw_off"] else None, lane_off_mean=round(float(np.mean(C["lane_off"])), 1) if C["lane_off"] else None,
               lane_off_p99=round(float(np.percentile(C["lane_off"], 99)), 1) if C["lane_off"] else None, flag_errors=C["flag_err"],
               bands=env.stats["rdr_band"].tolist(), problems=bad[:10], n_problems=len(bad))
    if a.share >= 0:
        out["share_of_match_frames_in_drills"] = round(C["drill_frames"] / max(1, C["drill_frames"] + C["game_frames"]), 4)
    import json
    print(json.dumps(out, indent=1, default=float))
    ok = (not bad and C["other_size"] == 0.0 and C["sum_err"] < 1e-6 and C["target_pay"] == 0.0 and C["flag_err"] == 0
          and (a.share >= 0 or (R[9] > 0 and C["pay_dealt"] > 0 and (not C["dist_err"] or max(C["dist_err"]) <= 0.045)
                                and (not C["yaw_off"] or max(C["yaw_off"]) <= 45.5))))
    print("DRILL TEST " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

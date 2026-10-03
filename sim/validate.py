"""Does the simulator move players like real Quake Live?

Reads a recording (inputs_<map>.txt from plugins/botctl.py) and, for every player and frame, puts the
simulated player in the recorded state, applies the recorded command, and compares the result with the
next recorded state. Alignment (found by testing, with minqlx.ran_usercmd recordings): the command on row k (keys and view
angles) is the one that turns row k's state into row k+1's. Server frames are 25 ms.
Reports one-step errors, split by situation, plus open-loop rollouts (errors that
build up over 0.5 s), which is what a policy trained in the simulator actually depends on.

    python sim/validate.py data/val_bloodrun/inputs_bloodrun.txt data/maps/bloodrun.bsp [--q3]
"""
import argparse
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsim import QL_PARAMS, Q3_PARAMS, World  # noqa: E402


def load(path):
    rows = defaultdict(list)
    for line in open(path):
        f = line.split()
        if len(f) < 18:
            continue
        rows[int(f[2])].append(dict(frame=int(f[0]), t=int(f[1]), pos=np.array(f[3:6], np.float32),
                                    vel=np.array(f[6:9], np.float32), pitch=float(f[9]), yaw=float(f[10]),
                                    move=(int(f[11]), int(f[12]), int(f[13])), health=int(f[16])))
    return rows


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs")
    ap.add_argument("bsp")
    ap.add_argument("--q3", action="store_true", help="plain Quake 3 movement rules instead of Quake Live's")
    ap.add_argument("--rollout", type=int, default=20, help="open-loop rollout length in frames")
    a = ap.parse_args()
    rows = load(a.inputs)
    w = World(a.bsp, n=1, params=Q3_PARAMS if a.q3 else QL_PARAMS)
    errs = defaultdict(list)
    skipped = 0
    for pid, rs in rows.items():
        w.reset(0, rs[0]["pos"], rs[0]["vel"], rs[0]["yaw"])
        for k in range(len(rs) - 1):
            r0, r1 = rs[k], rs[k + 1]
            dt = r1["t"] - r0["t"]
            # skip what movement can't explain: frame gaps, damage knockback, deaths/respawns, teleports
            if r1["frame"] != r0["frame"] + 1 or abs(r1["health"] - r0["health"]) > 1 or \
                    r1["health"] <= 0 or np.linalg.norm(r1["pos"] - r0["pos"]) > 60:
                skipped += 1
                w.reset(0, r1["pos"], r1["vel"], r1["yaw"])
                continue
            w.set(0, r0["pos"], r0["vel"], r0["yaw"], r0["t"])
            w.step(np.array([r0["move"]], np.int8), np.array([[r0["pitch"], r0["yaw"]]], np.float32), 25)
            s = w.state()[0]
            perr = float(np.linalg.norm(s[:3] - r1["pos"]))
            verr = float(np.linalg.norm(s[3:6] - r1["vel"]))
            air = abs(r0["vel"][2]) > 1 or abs(r1["vel"][2]) > 1
            jump = r1["vel"][2] - r0["vel"][2] > 100
            pad = r1["vel"][2] - r0["vel"][2] > 400          # jump pads (trigger_push) aren't movement physics
            kind = "jump pad" if pad else "jump" if jump else "air" if air else "ground"
            errs[kind].append((perr, verr))
            errs["all"].append((perr, verr))
    print("{} players, {} steps compared, {} skipped (knockback/respawn/teleport/gaps)".format(
        len(rows), len(errs["all"]), skipped))
    print("one-step error        n      pos p50   pos p95   vel p50   vel p95   (units, units/s)")
    for kind in ("all", "ground", "air", "jump", "jump pad"):
        e = np.array(errs[kind]) if errs[kind] else np.zeros((0, 2))
        print("  {:10} {:8}   {:8.2f}  {:8.2f}  {:8.1f}  {:8.1f}".format(
            kind, len(e), pct(e[:, 0], 50) if len(e) else 0, pct(e[:, 0], 95) if len(e) else 0,
            pct(e[:, 1], 50) if len(e) else 0, pct(e[:, 1], 95) if len(e) else 0))

    # open-loop rollouts: start from a recorded state, then feed only the recorded commands
    L = a.rollout
    finals = []
    for pid, rs in rows.items():
        for k in range(0, len(rs) - L, L):
            seg = rs[k:k + L + 1]
            ok = all(seg[j + 1]["frame"] == seg[j]["frame"] + 1 and abs(seg[j + 1]["health"] - seg[j]["health"]) <= 1 and seg[j + 1]["health"] > 0
                     and np.linalg.norm(seg[j + 1]["pos"] - seg[j]["pos"]) < 60
                     and seg[j + 1]["vel"][2] - seg[j]["vel"][2] < 400 for j in range(L))
            if not ok:
                continue
            w.reset(0, seg[0]["pos"], seg[0]["vel"], seg[0]["yaw"])
            w.set(0, seg[0]["pos"], seg[0]["vel"], seg[0]["yaw"], seg[0]["t"])
            for j in range(L):
                w.step(np.array([seg[j]["move"]], np.int8),
                       np.array([[seg[j]["pitch"], seg[j]["yaw"]]], np.float32), 25)
            finals.append(float(np.linalg.norm(w.state()[0][:3] - seg[L]["pos"])))
    if finals:
        print("open-loop {} frames ({:.2f} s): n={} drift p50 {:.1f}  p90 {:.1f}  p99 {:.1f} units".format(
            L, L * 0.025, len(finals), pct(finals, 50), pct(finals, 90), pct(finals, 99)))


if __name__ == "__main__":
    main()

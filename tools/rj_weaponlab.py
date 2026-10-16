"""weaponlab's rl_floor_<d> and rl_body (2026-10-07, data/weaponlab2) in the simulator: a rocket at the floor d units in
front of the target's box from 400 units, the target's damage and push. RL_QL from the environment (SW_EYE: RL_EYE).
python tools/rj_weaponlab.py"""
import json
import math
import os
import sys

import numpy as np

import rj_sim

D = rj_sim.D
env = rj_sim.make_env("campgrounds")
if os.environ.get("SW_EYE"):
    D.RL_EYE = float(os.environ["SW_EYE"])
LINE_START = (-1377.0, -817.0, 538.1)
sx, sy, sz = LINE_START
sp = (sx + 64, sy, 538.12)
tp = (sx + 64 + 400, sy, 538.12)
game = {}
for l in open(os.path.join(rj_sim.DATA, "weaponlab2", "weaponlab.jsonl")):
    r = json.loads(l)
    if r["rep"] != 1 or not r["test"].startswith(("rl_floor", "rl_body")):
        continue
    rows = r["rows"]
    i = next((k for k in range(1, len(rows)) if rows[k][9] < rows[k - 1][9] - 1), None)
    game[r["test"]] = (rows[i - 1][9] - rows[i][9], [round(rows[i][k] - rows[i - 1][k], 1) for k in (14, 16)]) if i else (0, [0, 0])
for test in sorted(game, key=lambda t: (len(t), t)):
    eye = (sp[0], sp[1], sz + 2 + 26.0)        # as weaponlab aimed: from the placed height (sz + 2), not the resting one
    if test == "rl_body":
        aim = (tp[0], tp[1], sz + 2 + 4.0)          # weaponlab's target place: placed at sz + 2
    else:
        off = float(test.split("_")[-1])
        aim = (tp[0] - (15 + off), tp[1], sz + 2 - 24.0)
    pitch = -math.degrees(math.atan2(aim[2] - eye[2], aim[0] - eye[0]))
    inp = [[0, 0, 0, 0]] * 10 + [[0, 0, 0, 1]] + [[0, 0, 0, 0]] * 30
    # player 0 the shooter, player 1 the target (rj_sim.run puts the second player at opp)
    rj_sim.run(env, sp, 0.0, pitch, 200.0, 0.0, [[0, 0, 0, 0]] * 10, opp=tp)
    env.hp[1] = 200.0
    prev_hp, prev_v = 200.0, env.state[1, 3:6].copy()
    res = (0, [0, 0])
    for k, (fw, sd, up, fire) in enumerate([[0, 0, 0, 1]] + [[0, 0, 0, 0]] * 30):
        a = np.zeros((2, len(D.ACTION_DIMS)), np.int64)
        a[:, 0] = a[:, 1] = 1
        a[:, 3] = D.TURN.tolist().index(0)
        a[:, 4] = D.PITCH.tolist().index(0)
        a[0, 5] = fire
        env.pitch[0] = pitch
        env.pitch[1] = 0.0
        env.step(a)
        h = float(env.hp[1])
        v = env.state[1, 3:6].copy()
        if h < prev_hp - 0.5:
            res = (prev_hp - h, [round(float(v[0] - prev_v[0]), 1), round(float(v[2] - prev_v[2]), 1)])
            break
        prev_hp, prev_v = h, v
    print("%-14s game dmg %3d kick %-16s | sim dmg %5.1f kick %s" % (test, game[test][0], game[test][1], res[0], res[1]))

"""Weapons: simulator vs real Quake Live (recorded by plugins/weaponlab.py).

    python sim/validate_weapons.py data/weaponlab/weaponlab.jsonl

For every real test (same positions, aim and timing) the duel simulator replays it and the two are compared:
damage to the target and to the shooter, the frame the damage lands, and the knockback (horizontal and
vertical speed of the target in the hit frame; the shooter's peak upward speed for rocket jumps).
Real health decays 1/s above 100 (the tests start at 200), so real damage includes ~1-2 points of decay.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import duel_env as D  # noqa: E402


def metrics(rows):
    """rows: [frame, s_hp, s_armor, sx, sy, sz, svx, svy, svz, t_hp, t_armor, tx, ty, tz, tvx, tvy, tvz]"""
    f0 = rows[0]
    hit = [i for i in range(1, len(rows)) if rows[i][9] < rows[i - 1][9] - 1]
    i = hit[0] if hit else None
    return dict(t_dmg=f0[9] - min(r[9] for r in rows), s_dmg=f0[1] - min(r[1] for r in rows),
                hit_frame=rows[i][0] if i is not None else None,
                n_hits=len(hit),
                kick_h=round(math.hypot(rows[i][14], rows[i][15])) if i is not None else 0,
                kick_z=round(rows[i][16]) if i is not None else 0,
                self_vz=round(max(r[8] for r in rows)))


def simulate(env, rec):
    rows = rec["rows"]
    f0 = rows[0]
    name = rec["test"]
    wname = name.split("_")[0].replace("kick", "")
    weapon = D.WEAPONS.index(wname)
    sp = rec.get("spec") or dict(hold=40 if name.startswith("lg_") else 2 if name.startswith("lgkick_") else 1,
                                 pin=name.startswith("lg_"))
    for i, base in ((0, 3), (1, 11)):
        env.w.reset(i, (f0[base], f0[base + 1], f0[base + 2]), (0, 0, 0), rec["yaw"] if i == 0 else rec["yaw"] + 180)
    env.yaw[:] = [rec["yaw"], rec["yaw"] + 180]
    env.pitch[:] = [rec["pitch"], 0.0]
    env.hp[:] = 200.0
    env.armor[:] = 0.0
    env.has[:] = True
    env.ammo[:] = 100.0
    env.mode[:] = -1
    env.item_up[:] = False                                   # no pickups during the tests
    env.item_t[:] = 1e9
    env.mv[:] = 0.0
    env.fire_q[:] = False
    env.cool[:] = 0.0
    env.weapon[:] = weapon
    env.ra[:] = False
    env.round_t[:] = 0.0
    env.state = env.w.state()
    tpos = np.array(f0[11:14], np.float32)
    out = []
    for k in range(len(rows) - 1):
        a = np.zeros((2, len(D.ACTION_DIMS)), np.int64)
        a[:, 0] = a[:, 1] = 1
        a[:, 3] = list(D.TURN).index(0)
        a[:, 4] = list(D.PITCH).index(0)
        firing = k < sp["hold"]
        a[0, 5] = 1 if firing else 0
        env.step(a)
        s = env.state
        out.append([k + 1, env.hp[0], 0, *s[0, :3], *s[0, 3:6], env.hp[1], 0, *s[1, :3], *s[1, 3:6]])
        if sp["pin"]:                                        # pinned like the real test
            env.w.reset(1, tpos, (0, 0, 0), rec["yaw"] + 180)
            env.state = env.w.state()
    return [[0, 200.0, 0, *f0[3:9], 200.0, 0, *f0[11:17]]] + out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real", nargs="+")
    a = ap.parse_args()
    recs = [json.loads(l) for f in a.real for l in open(f)]
    env = D.DuelEnv(os.path.join(ROOT, "data", "maps", "campgrounds.bsp"), n_matches=1, seed=0)
    env.level = 1.0
    env.round_len = 1e9
    real, sim = defaultdict(list), defaultdict(list)
    for r in recs:
        m = metrics(r["rows"])
        if r["rep"] == 0:
            continue                                         # the first repetition has setup glitches
        real[r["test"]].append(m)
        sim[r["test"]].append(metrics(simulate(env, r)))
    keys = ("t_dmg", "s_dmg", "hit_frame", "n_hits", "kick_h", "kick_z", "self_vz")
    print("{:14} {:>30} | {:>30}".format("test", "real: dmg self frame hits kh kz svz", "sim: dmg self frame hits kh kz svz"))
    for t in sorted(real):
        def med(rows, k):
            v = [x[k] for x in rows if x[k] is not None]
            return int(np.median(v)) if v else -1
        rv = [med(real[t], k) for k in keys]
        sv = [med(sim[t], k) for k in keys]
        print("{:14} {:>30} | {:>30}".format(t, " ".join(str(x) for x in rv), " ".join(str(x) for x in sv)))


if __name__ == "__main__":
    main()

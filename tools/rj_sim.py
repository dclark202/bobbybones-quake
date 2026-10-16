"""Rocket jumps in the duel simulator, with the inputs of the real game's rjlab records (plugins/rjlab.py).

Imports the repo's sim/ (read-only). The simulator switches are those of v0.3's checkpoint (env_vars) that touch
movement, shots and splash; the training-only ones play no part here.
    python tools/rj_sim.py probe <map> x y z           one rocket at his feet, printed
Used by tools/rj_compare.py (one map a process: the library holds one map). RL_QL / QL_FLOAT from the environment.
"""
import json
import math
import os
import sys

for k, v in dict(SHOT_MASK="1", LAVA="1", WALK_FIX="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1",
                 AUTO_SWITCH="1").items():
    os.environ.setdefault(k, v)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")      # (QLBOT_ROOT: the repo whose data/ to read)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import numpy as np  # noqa: E402
import duel_env as D  # noqa: E402

FAR = {"testlab": (10000.0, 6256.0, 8.0), "bloodrun": None}
_envs = {}


def make_env(mapname):
    if mapname in _envs:
        return _envs[mapname]
    env = D.DuelEnv(os.path.join(DATA, "maps", mapname + ".bsp"), n_matches=1, seed=0)
    env.level = 1.0
    env.round_len = 1e9
    env.human_aim = False
    env.key_limits = False
    _envs[mapname] = env
    return env


def run(env, start, yaw, pitch, hp, armor, inputs, opp=None, vel=(0, 0, 0)):
    """inputs: per frame [fwd, side, up, fire] (-127..127, 0/1). Returns rows after each frame:
    [k, hp, armor, x, y, z, vx, vy, vz, ground, rocket xyz or None]"""
    opp = opp or (start[0] + 4000.0, start[1], start[2])
    env.w.reset(0, start, vel, yaw)
    env.w.reset(1, opp, (0, 0, 0), yaw)
    env.yaw[:] = [yaw, yaw]
    env.pitch[:] = [pitch, 0.0]
    env.hp[:] = [hp, 100.0]
    env.armor[:] = [armor, 0.0]
    env.has[:] = True
    env.ammo[:] = 50.0
    env.mode[:] = -1
    env.item_up[:] = False
    env.item_t[:] = 1e9
    env.mv[:] = 0.0
    env.cmd[:] = 0.0
    env.fire_q[:] = False
    env.cool[:] = 0.0
    env.fire_cd[:] = 0.0
    env.weapon[:] = D.RL
    env.ra[:] = False
    env.duck[:] = False
    env.round_t[:] = 0.0
    env.goal[:] = -1
    env.state = env.w.state()
    out = []
    t0 = D.TURN.tolist().index(0)
    p0 = D.PITCH.tolist().index(0)
    for k, (fw, sd, up, fire) in enumerate(inputs):
        a = np.zeros((2, len(D.ACTION_DIMS)), np.int64)
        a[:, 0] = a[:, 1] = 1
        a[:, 3] = t0
        a[:, 4] = p0
        a[0, 0] = 1 + int(np.sign(fw))
        a[0, 1] = 1 + int(np.sign(sd))
        a[0, 2] = 1 if up > 0 else 0
        a[0, 5] = int(fire)
        env.pitch[0] = pitch
        env.step(a)
        s = env.state
        rk = None
        live = np.nonzero(env.ra[0])[0]
        if len(live):
            rk = [round(float(v), 1) for v in env.rp[0, live[0]]]
        out.append([k, float(env.hp[0]), float(env.armor[0]), *[round(float(v), 2) for v in s[0, :6]], float(s[0, 6]), rk])
    return out


def replay(rec, settle=10):
    env = make_env(rec["map"])
    h0 = [r for r in rec["rows"] if r[0] == 0][0]
    start = tuple(h0[3:6])
    vel = (0.0, 0.0, 0.0)
    inp = [[0, 0, 0, 0]] * settle + rec["inputs"]
    if rec.get("keys") == "run":                 # a run-up: from the game's state three frames before, running
        hm = [r for r in rec["rows"] if r[0] == -3][0]
        start, vel, settle = tuple(hm[3:6]), tuple(hm[6:9]), 3
        inp = [[127, 0, 0, 0]] * settle + rec["inputs"]
    # the game's own view (it holds the pitch at 87.89 degrees when 90 is asked: Quake 3's 16000 of 65536)
    rows = run(env, start, float(h0[10]), float(h0[9]), float(h0[1]), float(h0[2]), inp, vel=vel)
    return [[r[0] - settle + 1] + r[1:] for r in rows[settle:]]      # as the game's hooks: the state after input k is hook k+1


def probe(mapname, start, pitch=89.0):
    env = make_env(mapname)
    inp = [[0, 0, 0, 1 if k == 0 else 0] for k in range(40)]
    for r in run(env, start, 0.0, pitch, 100.0, 0.0, inp):
        print(r)


if __name__ == "__main__":
    if sys.argv[1] == "probe":
        probe(sys.argv[2], tuple(float(x) for x in sys.argv[3:6]))

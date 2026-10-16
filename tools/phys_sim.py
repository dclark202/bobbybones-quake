"""The movement cases of plugins/physlab.py replayed in the duel simulator, with the game's own commands (B-258).

    python tools/phys_sim.py <physlab.jsonl> <out.json> [NAME=VALUE ...]

Imports this repo's sim/ (its qsim library). The simulator switches are those of v0.3 (none of them touches movement
except QL_MOVE / QL_FLOAT and the switches of B-258, given on the command line). For each case: the trace from the
game's start state with the game's commands (8, 8 and 9 ms moves, the view turned a share of the way on each, as
minqlx/botctl.c does), and the one-frame step from every game state (the simulator put on the game's state, one frame
moved: the per-frame error). The map is read from QLBOT_ROOT's data/maps (default: this repo, then the main checkout).
"""
import json
import math
import os
import sys

ARGS = [a for a in sys.argv[1:] if "=" not in a]
for a in sys.argv[1:]:
    if "=" in a:
        k, v = a.split("=", 1)
        os.environ[k] = v
for k, v in dict(SHOT_MASK="1", LAVA="1", WALK_FIX="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1",
                 AUTO_SWITCH="1").items():
    os.environ.setdefault(k, v)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import numpy as np  # noqa: E402
import duel_env as D  # noqa: E402


def data_root():
    for r in (os.environ.get("QLBOT_ROOT"), ROOT, os.path.join(ROOT, "..", "..", "..")):
        if r and os.path.exists(os.path.join(r, "data", "maps", "testlab.bsp")):
            return os.path.abspath(r)
    raise SystemExit("no data/maps/testlab.bsp")


_env = {}


def world(mapname):
    if mapname not in _env:
        env = D.DuelEnv(os.path.join(data_root(), "data", "maps", mapname + ".bsp"), n_matches=1, seed=0)
        _env[mapname] = env
    return _env[mapname].w


def substeps(span):
    span = span if 6 <= span <= 100 else 25
    t = [span * k // 3 for k in range(1, 3)] + [span]
    return [t[0], t[1] - t[0], t[2] - t[1]], [t[0] / span, t[1] / span, 1.0]


def frame(w, mv, y_prev, yaw, span):
    """one game frame: three moves, the view turned from y_prev to yaw (minqlx/botctl.c)"""
    dy = (yaw - y_prev + 540.0) % 360.0 - 180.0
    ms, fr = substeps(span)
    moves = np.zeros((w.n, 3), np.int8)
    moves[0] = mv
    for m, f in zip(ms, fr):
        ang = np.zeros((w.n, 2), np.float32)
        ang[0] = (0.0, yaw if f >= 1.0 else y_prev + dy * f)
        w.step(moves, ang, m)
    return w.state()[0]


def replay(rec):
    w = world(rec["map"])
    far = np.array(rec["start"], np.float32) + np.array([0, 0, -100000.0], np.float32)
    rows = rec["rows"]
    ins = rec["ins"]
    span = [rows[k + 1][8] - rows[k][8] for k in range(len(rows) - 1)]
    # the trace: from the game's start with the game's commands
    w.reset(0, rec["start"], rec["start_vel"], rec["yaw0"])
    if w.n > 1:
        w.reset(1, far, (0, 0, 0), 0.0)
    out = [[0] + [float(v) for v in rec["start"]] + [float(v) for v in rec["start_vel"]] + [rec["yaw0"], 0.0]]
    y_prev = rec["yaw0"]
    for k, (f, fw, sd, up, yaw) in enumerate(ins):
        s = frame(w, (fw, sd, up), y_prev, yaw, span[k] if k < len(span) else 25)
        y_prev = yaw
        out.append([k + 1] + [round(float(v), 4) for v in s[:6]] + [round(float(s[7]), 4), float(s[6])])
    # the one-frame steps: the simulator on the game's state (flags as its own trace left them at that frame)
    w.reset(0, rec["start"], rec["start_vel"], rec["yaw0"])
    one = []
    y_prev = rec["yaw0"]
    ct = 1000
    for k, (f, fw, sd, up, yaw) in enumerate(ins):
        g = rows[k]
        if k > 0:
            w.set(0, g[1:4], g[4:7], y_prev, ct)
        s = frame(w, (fw, sd, up), y_prev, yaw, span[k] if k < len(span) else 25)
        ct += span[k] if k < len(span) else 25
        y_prev = yaw
        one.append([k + 1] + [round(float(v), 4) for v in s[:6]] + [float(s[6])])
    return out, one


def main():
    src, dst = ARGS[0], ARGS[1]
    recs = [json.loads(l) for l in open(src) if l.strip()]
    res = []
    for r in recs:
        if r["name"] == "warmup":
            continue
        tr, one = replay(r)
        res.append(dict(name=r["name"], rep=r["rep"], sim=tr, one=one))
    sw = {k: os.environ.get(k) for k in ("QL_FLOAT", "QL_MOVE", "QL_FWD", "QL_LAND", "QL_JUMP", "RL_QL")}
    json.dump(dict(switches=sw, cases=res), open(dst, "w"))
    print("replayed", len(res), "cases ->", dst, sw)


if __name__ == "__main__":
    main()

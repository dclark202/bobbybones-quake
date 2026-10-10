"""The pros' jumps as links of the walking map (v15, BACKLOG B-204).

tools/pro_gaps.py lists, per map, the jumps the pros make that a walker cannot (sim/pro_gaps/<map>.json: where from, where
to, the seconds in the air, the speed it needs). Here they become links of the walking map, for the strafe-jumping
teacher (movement_env.NavField) and for his own ways (duel_env.RouteField): from every standing spot at the take-off to
the spot nearest the landing, at the flight's seconds. Both also get, for every spot and goal, the first such jump on the
way ahead (how far the take-off is along the way, and which jump), which is what the five inputs of N_JUMP are made of.
Plain numpy: the simulator's workers import this.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_N = {"cannot": 20, "slower": 20, "just makes it": 30}     # how often the pros must have made it (by what a walker can do there)
N_JUMP = 5                                                    # inputs: a jump ahead, the speed it needs, the way to its take-off, its length, its rise
REACH = 1500.0                                                # a jump is "ahead" within this many units of way


def load(mapname, path=None):
    """the jumps of a map that are in use: [dict(id, a (take-off), b (landing), t, need, length, rise)]. An entry's
    "use" (true or false, set by hand) overrides the count rule."""
    p = path or os.path.join(HERE, "pro_gaps", mapname + ".json")
    if not os.path.exists(p):
        return []
    out = []
    for j in json.load(open(p)).get("jumps", []):
        use = j.get("use")
        if use is False or (use is None and j["n"] < MIN_N.get(j.get("walker"), 10 ** 9)):
            continue
        out.append(dict(id=int(j.get("id", len(out) + 1)), a=np.array(j["take_off"], np.float32), b=np.array(j["landing"], np.float32),
                        t=float(j["air_s"]), need=float(j["speed_needed"]), length=float(j["length"]), rise=float(j["rise"]),
                        n=int(j["n"])))
    return out


def links(jumps, nodes, locate, ok=None, reach=44.0):
    """-> [(from, to, seconds, index into jumps)]: from every standing spot within reach of the take-off, at its height,
    to the spot nearest the landing. ok: a flag per spot (dead or unplayable spots get no link)."""
    out = []
    for k, j in enumerate(jumps):
        b = int(np.asarray(locate(j["b"][None])).reshape(-1)[0])
        d = np.hypot(nodes[:, 0] - j["a"][0], nodes[:, 1] - j["a"][1])
        near = (d < reach) & (np.abs(nodes[:, 2] - j["a"][2]) < 30.0)
        if ok is not None:
            near &= ok
        idx = np.nonzero(near)[0]
        if not len(idx):
            idx = np.array([int(np.asarray(locate(j["a"][None])).reshape(-1)[0])])
        for a in idx:
            if int(a) != b and (ok is None or (ok[a] and ok[b])):
                out.append((int(a), b, float(j["t"]), k))
    return out


def look_ahead(nxt, jlink, nodes, reach=REACH, hops=64):
    """for one goal: nxt (the next spot of the way from every spot, -1 none) and jlink (the jump the step from a spot
    is, -1 a plain step) -> (units of way from every spot to the take-off of the first jump ahead, that jump's index);
    (1e9, -1) where there is none within reach."""
    n = len(nxt)
    cur = np.arange(n)
    dist = np.zeros(n, np.float32)
    fd = np.full(n, 1e9, np.float32)
    fi = np.full(n, -1, np.int32)
    live = np.ones(n, bool)
    for _ in range(hops):
        j = jlink[cur]
        hit = live & (j >= 0)
        fd[hit], fi[hit] = dist[hit], j[hit]
        nx = nxt[cur]
        live &= ~hit & (nx >= 0)
        if not live.any():
            break
        step = np.linalg.norm(nodes[np.maximum(nx, 0)] - nodes[cur], axis=1)
        dist = np.where(live, dist + np.minimum(step, 400.0), dist)       # (a teleporter's step is no distance to run)
        cur = np.where(live, nx, cur)
        live &= dist <= reach
    return fd, fi


def inputs(jumps, fd, fi, off):
    """the five inputs for players whose first jump ahead is fi (index, -1 none) at fd units of way from their spot; off:
    how far each stands from his spot. -> n x N_JUMP"""
    out = np.zeros((len(fi), N_JUMP), np.float32)
    if not len(jumps):
        return out
    has = fi >= 0
    k = np.maximum(fi, 0)
    need = np.array([j["need"] for j in jumps], np.float32)[k]
    length = np.array([j["length"] for j in jumps], np.float32)[k]
    rise = np.array([j["rise"] for j in jumps], np.float32)[k]
    out[:, 0] = has
    out[:, 1] = need / 600.0 * has
    out[:, 2] = np.minimum((fd + off) / 1000.0, 1.5) * has
    out[:, 3] = length / 600.0 * has
    out[:, 4] = np.clip(rise / 100.0, -3.0, 1.0) * has
    return out

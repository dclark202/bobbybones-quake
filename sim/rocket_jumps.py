"""The pros' rocket jumps as runs and as links of his ways (B-252, 2026-10-16).

docs/pro_rocket_jumps.json lists per map the rocket jumps the pros repeat (take-off, landing, the rise of the flight above
the take-off, the look-down, the health and armor at take-off; found in 5,039 demos, RESULTS 2026-10-15 12:45). Here they
become what duel_env's rocket jump runs (RJ_RUN_P) and his ways in games (RJ_OPEN) need: the jumps in sim/jump_links.py's
form (a, b, t, need, length, rise; need 0: a rocket jump asks no run-up speed), links of the walking map from every standing
spot at the take-off to the spot nearest the landing, and a copy of a route field whose one goal row is the landing, with the
way through the link. An entry's "use" (true or false, set by hand) is the owner's keep or drop.
Plain numpy: the simulator's workers import this.
"""
import copy
import heapq
import json
import math
import os

import numpy as np

import jump_links as JL

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("RJ_FILE") or os.path.join(HERE, "..", "docs", "pro_rocket_jumps.json")
GRAV = 800.0


def flight(rise, dz):
    """seconds in the air of a flight that tops out `rise` above the take-off and lands dz above it"""
    rise = max(float(rise), max(float(dz), 0.0) + 1.0)
    up = math.sqrt(2.0 * rise / GRAV)
    return up + math.sqrt(2.0 * max(rise - float(dz), 0.0) / GRAV)


def cleared(mapname):
    """the numbers of the map's rocket jumps that tools/rj_check.py clear found a scripted player to clear (sim/rj_clear.json)"""
    p = os.path.join(HERE, "rj_clear.json")
    return set(json.load(open(p)).get("cleared", {}).get(mapname, [])) if os.path.exists(p) else set()


def load(mapname, path=None, only=None):
    """the map's rocket jumps in use (only: their numbers, if given): [dict(id (its place in the list, from 1), a, b, t, need, length, rise, n, top, pitch,
    stack, self_damage)]; rise is the landing's height over the take-off (jump_links' meaning), top the flight's"""
    p = path or PATH
    if not os.path.exists(p):
        return []
    m = json.load(open(p)).get(mapname)
    if not m:
        return []
    out = []
    for k, l in enumerate(m.get("links", [])):
        if l.get("use") is False or (only is not None and k + 1 not in only):
            continue
        a, b = np.array(l["take_off"], np.float32), np.array(l["landing"], np.float32)
        dz = float(b[2] - a[2])
        out.append(dict(id=k + 1, a=a, b=b, t=flight(l.get("rise", 200.0), dz), need=0.0,
                        length=float(np.hypot(*(b[:2] - a[:2]))), rise=dz, n=int(l.get("n", 0)), top=float(l.get("rise", 0.0)),
                        pitch=float(l.get("pitch", 60.0)), stack=float(l.get("hp_at_take_off", 200.0)),
                        self_damage=float(l.get("self_damage", 33.0))))
    return out


def stack(total):
    """health and armor for a stack of `total` (the pros' health plus armor at take-off): 100 health first, then armor to
    100, then health to 200, then armor"""
    t = max(float(total), 1.0)
    hp = min(t, 100.0)
    ar = min(max(t - 100.0, 0.0), 100.0)
    hp += min(max(t - 200.0, 0.0), 100.0)
    ar += max(t - 300.0, 0.0)
    return hp, min(ar, 200.0)


def links(rjs, nodes, locate, ok=None):
    """-> [(from, to, seconds, index into rjs)] (sim/jump_links.links: the landing must be on the walking map)"""
    return JL.links(rjs, nodes, locate, ok=ok)


def _row(R, radj, gp):
    """one goal's seconds, next spots and via over the adjacency radj (Dijkstra from the goal, as RouteField.linked)"""
    n = len(R.nodes)
    T = np.full(n, 1e9, np.float32)
    nxt = np.full(n, -1, np.int32)
    b = int(R.locate(np.asarray(gp, np.float32)[None])[0])
    dist, pq = {b: 0.0}, [(0.0, b)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        for v, c in radj[u]:
            if d + c < dist.get(v, 1e18):
                dist[v] = d + c
                nxt[v] = u
                heapq.heappush(pq, (d + c, v))
    for v, d in dist.items():
        T[v] = d
    return T, nxt


def field(R, g, lk, rjs, goal=None):
    """a copy of route field R whose row g is the way to `goal` (default: R's own goal g) over the walking map plus the
    links lk (into rjs); every other row is R's (no jump ahead on them). Carries rjs as .jumps and .rj = True (the jump
    inputs index this list, not the map's strafe jumps)."""
    X = copy.copy(R)
    n, G = len(R.nodes), len(R.goals)
    radj, jl = [list(l_) for l_ in R.radj], {}
    for a, b, t, k in lk:
        radj[b].append((int(a), float(t)))
        jl[(int(a), int(b))] = int(k)
    X.goals = np.array(R.goals, np.float32).copy()
    if goal is not None:
        X.goals[g] = np.asarray(goal, np.float32)
    T, nxt = _row(R, radj, X.goals[g])
    X.T = np.array(R.T, copy=True)
    X.next = np.array(R.next, copy=True)
    X.T[g], X.next[g] = T, nxt
    X.via = np.array(R.via, copy=True)
    X.move = np.array(R.move, copy=True)
    X.via[g], X.move[g] = np.nan, False
    X.jlink = np.full((G, n), -1, np.int32)
    for a_ in np.nonzero(nxt >= 0)[0]:
        k_ = (int(a_), int(nxt[a_]))
        if k_ in jl:
            X.jlink[g, a_], X.move[g, a_] = jl[k_], True
            continue
        e_ = R._enter.get(k_)
        if e_ is not None:
            X.via[g, a_] = e_
        X.move[g, a_] = k_ in R._special
    X.jd = np.full((G, n), 1e9, np.float32)
    X.ji = np.full((G, n), -1, np.int32)
    X.jd[g], X.ji[g] = JL.look_ahead(nxt, X.jlink[g], R.nodes)
    X.walk = X.next
    X.T_walk = getattr(R, "T_walk", R.T)
    X.pro_step = np.zeros((G, n), bool)
    X.radj, X.jumps, X.rj = radj, list(rjs), True
    X._fwd, X._from, X._jl = None, {}, jl
    return X


def linked_all(R, lk, rjs, extra_cost=0.0, n_plain=0):
    """(RJ_OPEN) a copy of R whose ways (every row) also take the links lk (into rjs) at their seconds, plus extra_cost on
    a rocket jump's (rjs[n_plain:]; the first n_plain are strafe jumps open by JUMP_OPEN, at their own seconds)"""
    X = R.linked([(a, b, t + (extra_cost if k >= n_plain else 0.0), k) for a, b, t, k in lk], rjs)
    X.walk, X.T_walk, X.rj = X.next, getattr(R, "T_walk", R.T), True
    return X

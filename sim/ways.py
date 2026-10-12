"""Stage B part 3 (WAYS; docs/design/V02_STAGE_B.md, "Several ways to a target"): for every target up to two more sets of
ways beside the shortest, "the shortest way that follows the pros' second and third ways where they exist". Plain numpy
(no scipy, no torch: the simulator's workers load this file).

The pros' ways: sim/pro_ways/<map>.json (tools/pro_yardsticks.py): for every ordered pair of big items up to three ways,
the commonest first, each a path with a point every 128 units.

What a second (third) set of ways to a target is, step by step:
  1. THE PROS' WAYS INTO IT (plan). An item: the ways of the pairs that end at it. A holding place (TARGETS), which no
     pair ends at: the part up to the place of every way of any pair that passes it within WAY_PASS units (the pros walk
     through the places they hold on their way elsewhere), the most walked first. By origin (the item the way starts
     at): the ways are set beside the shortest way of the walking map from that origin, in the pros' order; a way that
     lies within WAY_SAME units of it on average (the pros' own rule for "the same way", 16 points along each) IS the
     shortest, and so is one that lies that near a way already taken. Of the ways left, the first that a walker can
     follow (steps 2 and 3 with that way alone must lead from the origin along it) is that origin's second way, the
     next its third. So where the pros' commonest way is not the walking map's shortest, their commonest is his second
     way. A way with a rocket jump is left out; a way the walking map has no links for (a drop or a jump it lacks:
     most of what is not taken), or one over the cap, is none.
     ... AND THAT HIS LEGS MAKE: a link of the walking map is something a scripted walker can take; the movement
     network that is his legs does not make every one of them (Blood Run, 2026-10-12: the third way to the rocket
     launcher takes a drop from the top floor onto a ledge 128 units below and 320 away; his legs missed it, landed
     on the ground floor, were sent round through the teleporter to the same drop and went round for good). So a way
     is taken only if it is listed as made in sim/pro_ways_legs/<map>.json, written by tools/ways_check.py: tries on
     his legs from the way's origin, and from the spawn points and other items whose way it changes. A map without
     that file has no second or third ways (WAY_UNTESTED=1 takes untested ways too: the tool's own passes, and
     checks). A way is named there by its origin, its target's place, its trips and its points (legs_key).
  2. THE SEARCH (price, solve). The shortest-way search to the target is run again with other prices: a link of the
     walking map that runs along one of those ways (both ends within WAY_R units sideways and WAY_Z in height of it,
     and not backward along it) costs a share of its seconds: WAY_ALPHA, or for a way the search does not follow at
     that (the map's links cover it only in part) the first of WAY_ALPHAS that makes it. Nothing costs more than it
     did and every price stays above zero, so the result is again one way from every point that arrives. Its seconds
     are then counted at the true prices.
  3. THE CAP (cap). From a point where that way costs more than WAY_CAP times the shortest (or has no advantage: there is
     none), his way by this set is the shortest way's step. The mix cannot circle: a step by the alternative shortens
     the alternative's seconds, a step by the shortest shortens the shortest's, and a point is "on the alternative"
     only while alternative <= WAY_CAP x shortest; had a circle a point w off the alternative with the least shortest
     seconds, the next off-point w2 on the circle would have alternative(w2) < alternative(x) <= WAY_CAP x shortest(x)
     < WAY_CAP x shortest(w) <= WAY_CAP x shortest(w2) for the on-point x after w: w2 would be on it. The seconds of the
     mixed set are counted along it (they never exceed WAY_CAP times the shortest, by the same sums); a circle found
     all the same (rounding) is opened by giving its points the shortest way's step.
  4. WHERE IT DIFFERS (differs). From a point the set's way "differs" from the shortest when more than WAY_DIFF of its
     seconds lie on points farther than WAY_FAR units from every point of the shortest way from there.
A set with no way of the pros (a target they have no second way into) is the shortest set itself: nothing is searched.
"""
import heapq
import json
import os

import numpy as np

WAY_ALPHA = float(os.environ.get("WAY_ALPHA") or 0.5)     # a link along the pros' way: this share of its seconds in the search
WAY_ALPHAS = (0.25, 0.1, 0.05)                            # ... and where the search does not follow a way at that, the first of these that does
WAY_CAP = float(os.environ.get("WAY_CAP") or 1.5)         # an alternative may cost this many times the shortest way, from any point
WAY_R, WAY_Z = 112.0, 72.0                                # a point of the walking map is on a pros' way within this (sideways, height)
WAY_BACK = 32.0                                           # a link may run this far backward along the way and still be "along" it
WAY_SAME = 200.0                                          # two ways are one when their paths lie this near on average (sim/pro_ways: same_way_within_units)
WAY_PASS, WAY_PASS_Z, WAY_PASS_MIN = 128.0, 64.0, 256.0   # a way passes a place within this; the part up to it must be this long
WAY_DIFF, WAY_FAR = 0.25, 128.0                           # "differs": this share of its seconds farther than this from the shortest way
TELE = 400.0                                              # a step of a pros' way this long is a teleporter (as tools/pro_yardsticks.py)
ITEM_R, ITEM_Z = 48.0, 128.0                              # a pros' item is a route goal within this


def load(mapname, folder=None):
    """the pros' ways of a map (None: no file)"""
    f = os.path.join(folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_ways"), mapname.lower() + ".json")
    if not os.path.exists(f):
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def load_legs(mapname, folder=None):
    """what tools/ways_check.py measured of a map's ways on his legs: {way's key: {"ok": bool, ...}} (None: no file)"""
    f = os.environ.get("WAY_LEGS_FILE") or os.path.join(folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_ways_legs"),
                                                        mapname.lower() + ".json")
    if not os.path.exists(f):
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh).get("ways", {})


def legs_key(origin, goal, trips, points):
    """the name of one of the pros' ways in sim/pro_ways_legs/<map>.json: where it starts, where it leads, its trips and points"""
    return "{}>{:.0f},{:.0f},{:.0f}:{}:{}".format(origin, float(goal[0]), float(goal[1]), float(goal[2]), int(trips), int(points))


def resample(path, k=16):
    """k points evenly along a path (tools/pro_yardsticks.py's _resample: a teleporter's leap counts as length)"""
    path = np.asarray(path, np.float64).reshape(-1, 3)
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    if d[-1] <= 0:
        return np.repeat(path[:1], k, 0)
    at = np.linspace(0.0, d[-1], k)
    return np.stack([np.interp(at, d, path[:, c]) for c in range(3)], 1)


def apart(a, b):
    """how far two paths lie from each other on average (16 points along each): under WAY_SAME they are one way"""
    return float(np.linalg.norm(resample(a) - resample(b), axis=1).mean())


def walk(nxt, a, cap=2000):
    """the points of the way from point a by the steps nxt (one row of a set of ways)"""
    out = [int(a)]
    while nxt[out[-1]] >= 0 and len(out) < cap:
        out.append(int(nxt[out[-1]]))
    return out


def _into(W, pos, place):
    """the pros' ways into a target at pos: [(origin label, points, trips, rocket jump)]. An item: the ways of the pairs
    that end at it, in the file's order (the commonest first). A holding place (no pair ends at it): the part up to it
    of every way that passes it within WAY_PASS units, the most walked first. (For an item the passing ways were tried
    too, 2026-10-11: on Blood Run and Aerowalk every one of them was the shortest way again.)"""
    pos = np.asarray(pos, np.float64)
    items = {k: np.asarray(v, np.float64) for k, v in W["items"].items()}
    out = []
    if not place:
        to = [k for k, p in items.items() if np.hypot(p[0] - pos[0], p[1] - pos[1]) < ITEM_R and abs(p[2] - pos[2]) < ITEM_Z]
        for pr in W["pairs"]:
            if pr["to"] in to:
                for w in pr["ways"]:
                    out.append((pr["from"], np.asarray(w["points"], np.float64), int(w["trips"]), bool(w["rocket_jump"])))
        return out
    for pr in W["pairs"]:
        for w in pr["ways"]:
            P = np.asarray(w["points"], np.float64)
            near = (np.hypot(P[:, 0] - pos[0], P[:, 1] - pos[1]) < WAY_PASS) & (np.abs(P[:, 2] - pos[2]) < WAY_PASS_Z)
            if not near.any():
                continue
            q = int(np.nonzero(near)[0][np.linalg.norm(P[near] - pos, axis=1).argmin()])
            hop = np.linalg.norm(np.diff(P[:q + 1], axis=0), axis=1)
            if q < 1 or float(hop[hop <= TELE].sum()) < WAY_PASS_MIN:
                continue
            out.append((pr["from"], np.concatenate([P[:q + 1], pos[None]]), int(w["trips"]), bool(w["rocket_jump"])))
    out.sort(key=lambda c: -c[2])
    return out


def plan(W, G, locate, T, nxt, goals, n_items, legs=None, untested=False):
    """step 1 for every target (a row of the walking map's ways: the first n_items are items, the rest holding places):
    -> [[the pros' ways that make its second set], [... its third set]] a row, each way (its points, its share of the
    price in the search), and a report a row: per origin the seconds of the shortest way and what became of each of
    the pros' ways.
    A way is taken only if a walker can follow it: the search with that way alone (steps 2 and 3) must lead from its
    origin along it (within WAY_SAME), at WAY_ALPHA of the price or, where the walking map's links cover the way only
    in part, at the first of WAY_ALPHAS that does. Otherwise the walking map has no such way (a jump or a drop it
    lacks), or it is over the cap, and the next of the pros' ways is tried in its place.
    ... and only if his legs make it (legs: load_legs(), what tools/ways_check.py measured): a way measured as not made
    is none (the file also keeps the ways the walking map could not follow, with the reason: they are not searched
    for again), and so is a way that was never measured unless `untested` says otherwise (the tool's own passes)."""
    plans, report = [], []
    nodes = G.nodes
    items = {k: np.asarray(v, np.float32) for k, v in (W or {}).get("items", {}).items()}
    for g in range(len(goals)):
        sets, rep = [[], []], []
        by = {}
        for org, P, trips, rj in (_into(W, goals[g], g >= n_items) if W else ()):
            by.setdefault(org, []).append((P, trips, rj))
        b = int(locate(np.asarray(goals[g], np.float32)[None])[0])
        nx_s = np.asarray(nxt[g], np.int64)
        for org, cands in by.items():
            a = int(locate(items[org][None])[0])
            if not T[g, a] < 1e8:
                continue
            short = nodes[walk(nx_s, a)]
            taken, row = [], dict(origin=org, shortest_s=round(float(T[g, a]), 2), ways=[])
            for P, trips, rj in cands:
                d0 = apart(P, short)
                one = dict(trips=trips, apart=int(d0))
                if rj:
                    one["what"] = "rocket jump"
                elif d0 <= WAY_SAME:
                    one["what"] = "the shortest"
                elif any(apart(P, Q) <= WAY_SAME for Q in taken):
                    one["what"] = "as one taken"
                elif len(taken) >= 2:
                    one["what"] = "one too many"
                elif (legs or {}).get(legs_key(org, goals[g], trips, len(P))) is None and not untested:
                    one["what"] = "not tried on his legs"
                elif not (legs or {}).get(legs_key(org, goals[g], trips, len(P)), {"ok": True})["ok"]:
                    one["what"] = (legs or {})[legs_key(org, goals[g], trips, len(P))].get("why") or "not made on his legs"
                else:
                    one["key"] = legs_key(org, goals[g], trips, len(P))
                    one["what"], raw = "no such way for a walker", None
                    for alpha in (WAY_ALPHA,) + tuple(x for x in WAY_ALPHAS if x < WAY_ALPHA):
                        nx_a, _, T_a = G.solve(b, G.price([(P, alpha)]))
                        if not T_a[a] < 1e8:
                            break                            # (no way of the walking map from the origin at all: a pros' step)
                        nx_f, T_f, _, _ = cap(T[g], nx_s, T_a, nx_a)
                        if apart(P, nodes[walk(nx_f, a)]) <= WAY_SAME:
                            one["what"], one["seconds"], one["price"] = "way {}".format(len(taken) + 2), round(float(T_f[a]), 2), alpha
                            sets[len(taken)].append((P, alpha))
                            taken.append(P)
                            break
                        raw = (nx_a, T_a)
                    if raw is not None and not one["what"].startswith("way ") and apart(P, nodes[walk(raw[0], a)]) <= WAY_SAME:
                        one["what"], one["times_the_shortest"] = "over the cap", round(float(raw[1][a] / max(float(T[g, a]), 1e-6)), 2)
                row["ways"].append(one)
            rep.append(row)
        plans.append(sets)
        report.append(rep)
    return plans, report


def _along(nodes, P):
    """for every point of the walking map: is it on the way P, and how far along the way (units from its start; a
    teleporter's leap counts nothing)"""
    n = len(nodes)
    P = np.asarray(P, np.float64)
    nd = nodes.astype(np.float64)
    best = np.full(n, 1e18)
    s = np.zeros(n)
    on = np.zeros(n, bool)
    hop = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s0 = 0.0
    for j in range(len(P)):
        if j + 1 < len(P) and hop[j] <= TELE and hop[j] > 0:  # the stretch to the next point
            ab = P[j + 1] - P[j]
            t = np.clip(((nd - P[j]) @ ab) / float(ab @ ab), 0.0, 1.0)
            q = P[j] + t[:, None] * ab
            ln = float(hop[j])
        else:                                                # (the last point, or the point before a teleporter: itself alone)
            t, q, ln = np.zeros(n), np.repeat(P[j][None], n, 0), 0.0
        dxy, dz = np.hypot(nd[:, 0] - q[:, 0], nd[:, 1] - q[:, 1]), np.abs(nd[:, 2] - q[:, 2])
        ok = (dxy <= WAY_R) & (dz <= WAY_Z)
        sc = dxy + 2.0 * dz
        up = ok & (sc < best)
        best[up], s[up] = sc[up], s0 + t[up] * ln
        on |= ok
        s0 += ln
    return on, s


class Graph:
    """a walking map's links as flat lists, for the searches: radj[u] holds (v, seconds[, kind]) for a link v -> u"""

    def __init__(self, nodes, radj):
        self.nodes = np.asarray(nodes, np.float32)
        ev, eu, ec, ek = [], [], [], []
        for u, lst in enumerate(radj):
            for it in lst:
                ev.append(int(it[0]))
                eu.append(u)
                ec.append(float(it[1]))
                ek.append(it[2] if len(it) > 2 else None)
        self.ev, self.eu, self.ec, self.ek = np.array(ev, np.int64), np.array(eu, np.int64), np.array(ec, np.float64), ek
        assert len(ec) == 0 or self.ec.min() > 0.0, "a link that costs nothing"
        self.inc = [[] for _ in range(len(self.nodes))]
        for e, u in enumerate(eu):
            self.inc[u].append(e)
        self._near = None

    def near(self):
        """[n, n]: two points lie within WAY_FAR units of each other"""
        if self._near is None:
            nd = self.nodes.astype(np.float32)
            self._near = np.zeros((len(nd), len(nd)), bool)
            for a in range(0, len(nd), 256):
                self._near[a:a + 256] = np.linalg.norm(nd[a:a + 256, None, :] - nd[None, :, :], axis=2) < WAY_FAR
        return self._near

    def price(self, ways):
        """step 2's prices: for every link the share of its seconds it costs in the search. ways: [(points, share)]; a
        link that runs along one of them (both ends on it, not backward) costs that way's share, the least of them"""
        m = np.ones(len(self.ec))
        for P, alpha in ways:
            on, s = _along(self.nodes, P)
            m = np.where(on[self.ev] & on[self.eu] & (s[self.eu] >= s[self.ev] - WAY_BACK), np.minimum(m, alpha), m)
        return m

    def solve(self, goal, price):
        """step 2: the search to the point `goal` with every link at its share `price` of its seconds -> for every point
        its next point (-1: none, or the goal), the link taken (-1), and its seconds at the true prices (1e9: no way)"""
        n = len(self.nodes)
        c2 = (self.ec * price).tolist()
        ev, inc = self.ev.tolist(), self.inc
        dist, nx, eid, order = {goal: 0.0}, [-1] * n, [-1] * n, []
        pq, done = [(0.0, goal)], [False] * n
        while pq:
            d, u = heapq.heappop(pq)
            if done[u] or d > dist.get(u, 1e18):
                continue
            done[u] = True
            order.append(u)
            for e in inc[u]:
                v = ev[e]
                nd = d + c2[e]
                if nd < dist.get(v, 1e18):
                    dist[v], nx[v], eid[v] = nd, u, e
                    heapq.heappush(pq, (nd, v))
        T = np.full(n, 1e9, np.float64)
        T[goal] = 0.0
        ec = self.ec
        for v in order[1:]:                                  # (a point's next point was settled before it)
            T[v] = T[nx[v]] + ec[eid[v]]
        return np.array(nx, np.int64), np.array(eid, np.int64), T


def cap(T_s, nx_s, T_a, nx_a, limit=None):
    """step 3 -> the mixed set: its next points, its seconds, the points whose step is the alternative's, and how many
    points a circle had to be opened at (0 but for rounding)"""
    limit = WAY_CAP if limit is None else limit
    n = len(T_s)
    T_s = np.asarray(T_s, np.float64)
    on = (T_a < 1e8) & (T_s < 1e8) & (T_a <= limit * T_s + 1e-6) & (nx_a >= 0)
    fixed = 0
    while True:
        nx = np.where(on, nx_a, nx_s).astype(np.int64)
        step = np.where(on, T_a - T_a[np.maximum(nx_a, 0)], T_s - T_s[np.maximum(nx_s, 0)])       # the seconds of a point's step
        T = np.full(n, -1.0)
        T[(nx < 0) | ~(T_s < 1e8)] = 0.0                     # (the goal; a point with no way keeps its 1e9 below)
        bad = []
        for v0 in range(n):
            if T[v0] >= 0:
                continue
            chain, seen, v = [], set(), v0
            while T[v] < 0 and v not in seen:
                seen.add(v)
                chain.append(v)
                v = int(nx[v])
            if T[v] < 0:                                     # a circle: its points take the shortest way's step
                bad += chain[chain.index(v):]
                for q in chain:
                    T[q] = 0.0
                continue
            t = T[v]
            for q in reversed(chain):
                t += step[q]
                T[q] = t
        if not bad:
            break
        on[bad] = False
        fixed += len(bad)
    T = np.where(T_s < 1e8, T, 1e9)
    return nx, T, on, fixed


def beside(G, nx_s):
    """[n, n]: point u lies within WAY_FAR units of the shortest way from point v (one row of the shortest set)"""
    n = len(nx_s)
    depth = np.zeros(n, np.int64)                            # a point's number of steps to the goal by the shortest way
    cur = np.arange(n)
    for _ in range(n):
        go = nx_s[cur] >= 0
        if not go.any():
            break
        depth[go] += 1
        cur = np.where(go, nx_s[cur], cur)
    ns = G.near().copy()
    for v in np.argsort(depth, kind="stable"):
        if nx_s[v] >= 0:
            ns[v] |= ns[nx_s[v]]
    return ns


def differs(ns, T_f, nx_f):
    """step 4 -> for every point: the set's way from it differs from the shortest way from it (ns: beside())"""
    n = len(T_f)
    far = np.zeros(n)
    cur, ar = np.arange(n), np.arange(n)
    for _ in range(n):
        nx = nx_f[cur]
        go = nx >= 0
        if not go.any():
            break
        st = np.where(go, T_f[cur] - T_f[np.maximum(nx, 0)], 0.0)
        far += np.where(go & ~ns[ar, np.maximum(nx, 0)], st, 0.0)
        cur = np.where(go, nx, cur)
    return (T_f < 1e8) & (far > WAY_DIFF * np.maximum(T_f, 1e-9))


def fields(G, goal_nodes, T, nxt, plans, want_diff=True):
    """steps 2 to 4 for every row -> wT [2, rows, n] (seconds), wnext [2, rows, n], weid [2, rows, n] (the link of a step
    that is the alternative's, -1 where it is the shortest way's), wdiff [2, rows, n], and how many circles were opened"""
    R_, n = len(goal_nodes), len(G.nodes)
    wT = np.repeat(np.asarray(T, np.float32)[None, :R_], 2, 0).copy()
    wnext = np.repeat(np.asarray(nxt, np.int32)[None, :R_], 2, 0).copy()
    weid = np.full((2, R_, n), -1, np.int64)
    wdiff = np.zeros((2, R_, n), bool)
    fixed = 0
    for g in range(R_):
        ns = None
        for k in range(2):
            ways = plans[g][k] if g < len(plans) else []
            if not ways:
                continue
            nx_s = np.asarray(nxt[g], np.int64)
            nx_a, eid_a, T_a = G.solve(int(goal_nodes[g]), G.price(ways))
            nx_f, T_f, on, fx = cap(T[g], nx_s, T_a, nx_a)
            fixed += fx
            wT[k, g], wnext[k, g] = T_f.astype(np.float32), nx_f.astype(np.int32)
            weid[k, g] = np.where(on, eid_a, -1)
            if want_diff:
                ns = beside(G, nx_s) if ns is None else ns
                wdiff[k, g] = differs(ns, T_f, nx_f)
    return wT, wnext, weid, wdiff, fixed


def route_alts(R, plans, G=None):
    """the second and third sets of ways of a RouteField (sim/duel_env.py), as arrays beside its own: wT, wnext, wvia,
    wdiff [2, goals, points]"""
    G = Graph(R.nodes, R.radj) if G is None else G
    goal_nodes = [int(R.locate(p[None])[0]) for p in R.goals]
    wT, wnext, weid, wdiff, fixed = fields(G, goal_nodes, R.T, R.walk if getattr(R, "walk", None) is not None else R.next, plans)
    wvia = np.repeat(np.asarray(R.via, np.float32)[None], 2, 0).copy()
    for k, g, v in zip(*np.nonzero(weid >= 0)):              # the steps that are the alternative's: a pad's plate, a teleporter's entrance
        e_ = R._enter.get((int(v), int(wnext[k, g, v])))
        wvia[k, g, v] = np.nan if e_ is None else e_
    R.wT, R.wnext, R.wvia, R.wdiff, R.way_fixed = wT, wnext, wvia, wdiff, fixed
    R.wjd = R.wji = None
    if getattr(R, "jlink", None) is not None and getattr(R, "_jl", None) is not None:      # a set with the pros' jumps (JUMP_OPEN):
        import jump_links as JL                                                             # the jump ahead on these ways
        wjl = np.repeat(np.asarray(R.jlink)[None], 2, 0).copy()
        for k, g, v in zip(*np.nonzero(weid >= 0)):
            wjl[k, g, v] = R._jl.get((int(v), int(wnext[k, g, v])), -1)
        R.wjd, R.wji = np.repeat(np.asarray(R.jd)[None], 2, 0).copy(), np.repeat(np.asarray(R.ji)[None], 2, 0).copy()
        for k, g in sorted({(int(k), int(g)) for k, g in zip(*np.nonzero((weid >= 0).any(2)))}):
            R.wjd[k, g], R.wji[k, g] = JL.look_ahead(wnext[k, g], wjl[k, g], R.nodes)
    return G


def nav_alts(F, plans_by_goal):
    """the second and third sets of ways of the movement network's own field (sim/movement_env.py's NavField, which keeps
    its links as radj since this part): two copies of it whose T, next, next_kind, jlink, via (and jd, ji) are the
    alternative's for the goals named in plans_by_goal {its goal: [[ways], [ways]]}; the other goals keep the shortest"""
    import copy
    G = Graph(F.nodes, F.radj)
    rows = len(F.goals)
    plans = [plans_by_goal.get(j, [[], []]) for j in range(rows)]
    goal_nodes = [int(F.locate(p[None])[0][0]) for p in F.goals]
    wT, wnext, weid, _, fixed = fields(G, goal_nodes, F.T, F.next, plans, want_diff=False)
    kinds = {"walk": 0, "air": 1, "tele": 2, "jump": 3}
    out = []
    for k in range(2):
        X = copy.copy(F)
        X.T, X.next = wT[k], wnext[k]
        X.next_kind, X.jlink = F.next_kind.copy(), F.jlink.copy()
        X.via = None if F.via is None else F.via.copy()
        for g, v in zip(*np.nonzero(weid[k] >= 0)):
            e = int(weid[k, g, v])
            u = int(wnext[k, g, v])
            X.next_kind[g, v] = kinds[G.ek[e]]
            X.jlink[g, v] = F._jl.get((int(v), u), -1) if G.ek[e] == "jump" else -1
            if X.via is not None:
                X.via[g, v] = F._enter.get((int(v), u), np.nan)
        X.reach = X.T < 1e8
        if getattr(F, "ji", None) is not None:
            import jump_links as JL
            la = [JL.look_ahead(X.next[g], X.jlink[g], F.nodes) for g in range(rows)]
            X.jd, X.ji = np.stack([x[0] for x in la]), np.stack([x[1] for x in la])
        X.way_fixed = fixed
        out.append(X)
    return out


def measure(n, T, wT, wnext, wdiff, row, starts):
    """one row's second and third sets from the points `starts` (n: the map's points): for each the starts that have a
    way, how many of them differ from the shortest, how much longer the way is in seconds where it differs (median,
    90th percentile) and at most, the worst ratio to the shortest, and how many arrive (the steps lead to the goal)"""
    out = []
    starts = np.asarray([s for s in starts if T[row, s] < 1e8], np.int64)
    for k in range(2):
        d = wdiff[k, row, starts]
        ex = (wT[k, row, starts] - T[row, starts]).astype(np.float64)
        arr = 0
        for s in starts:
            p = walk(wnext[k, row], s, cap=n + 1)
            arr += int(len(p) <= n and wT[k, row, p[-1]] == 0.0)
        ratio = wT[k, row, starts] / np.maximum(T[row, starts], 1e-6)
        out.append(dict(starts=int(len(starts)), differ=int(d.sum()), longer_median=round(float(np.median(ex[d])), 2) if d.any() else None,
                        longer_90=round(float(np.percentile(ex[d], 90)), 2) if d.any() else None, longer_worst=round(float(ex.max()), 2) if len(ex) else None,
                        ratio_worst=round(float(ratio.max()), 3) if len(ratio) else None, arrive=int(arr)))
    return out

"""Item-to-item movement task in the simulator, many players at once (one process).

Each player spawns on the map's nav graph and must reach a goal item as fast as possible. Nothing about
strafe jumping is coded: the reward is just "time saved toward the goal", so going faster than running
(320 units/s) only pays off if the policy discovers how.

Reward per 25 ms step = drop in estimated time-to-goal (nav-graph shortest time at run speed) - 0.025 s,
so plain running scores ~0, anything faster scores > 0. +1 on arrival, -1 for falling out of the map.

Observation (egocentric, rotated into the view's yaw):
  velocity (3), on ground (1), next 4 route waypoints (4 x 3) + "air/teleport" flags (4), goal (3),
  time-to-goal (1), 16 wall rays at waist height, 8 floor-ahead rays (pits/ledges)  -> 48 floats
Action (MultiDiscrete): forward {-,0,+}, strafe {-,0,+}, jump {0,1}, turn {9 bins, -30..+30 deg/frame}
"""
import heapq
import json
import math
import os
import sys
import zlib

import numpy as np
try:
    from scipy.spatial import cKDTree
except Exception:                                           # scipy missing or broken: plain numpy nearest-point search
    class cKDTree:
        def __init__(self, pts):
            self.pts = np.asarray(pts, np.float32)
            self.sq = (self.pts ** 2).sum(1)

        def query(self, x):
            x = np.asarray(x, np.float32)
            d2 = (x ** 2).sum(1)[:, None] - 2.0 * x @ self.pts.T + self.sq[None, :]
            k = d2.argmin(1)
            return np.sqrt(np.maximum(d2[np.arange(len(x)), k], 0.0)), k

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsim import World  # noqa: E402
import jump_links as JL  # noqa: E402

RUN = 320.0
DT = 0.025
TURN_BINS = np.array([-30, -15, -6, -2, 0, 2, 6, 15, 30], np.float32)
ACTION_DIMS = (3, 3, 2, len(TURN_BINS))
GOAL_CLASSES = ("weapon_", "item_armor_body", "item_armor_combat", "item_armor_jacket", "item_health_mega",
                "item_health_large", "item_quad")
FALL_COST = 0.05                                            # v14: seconds a point of fall damage costs (a far fall, 10 points: half a second)
LAVA_COST = float(os.environ.get("MOVE_LAVA_COST") or 1.0)  # v15: what a try that ends in lava or slime costs (an arrival pays 1)
HAZARD = 8 | 16                                             # lava, slime (the map's contents flags)
TELE_FAR = 160.0                                            # v14: a teleporter link starts within this of its entrance
N_WALL, N_FLOOR = 16, 8
# v15 (hand): the left hand he plays with (duel_env.limit_keys; the same numbers): ring finger = strafe left, middle =
# forward and back (no direct reversal), index = strafe right, thumb = jump
RING, MIDDLE, INDEX, THUMB = range(4)
FINGER_HOLD = np.array([6, 6, 6, 4], np.int64)              # frames a finger waits after it has acted
KEY_EVERY, KEY_BURST = 4, 10.0                              # the keys are read every 4 frames; a burst of ten key actions
KEY_RATE = float(os.environ.get("KEY_RATE") or 8.0)         # ... refilled at this many a second (v14: 8)
N_HAND = 5                                                  # inputs: the keys held (forward, strafe, jump), the hand's budget, frames to the next reading
N_MOUSE = 3                                                 # inputs: the view's turning speed, the direction the hand turns, frames until it may change
MOUSE_SMOOTH, MOUSE_SMOOTH_FINE, TURN_CAP = 0.75, 0.2, 30.0   # his mouse (duel_env): inertia a frame, for commands up to a degree, the fastest flick
MOUSE_REV = 8                                               # frames after a change of the turn's direction before the hand changes it again (0.2 s)
# Stage C part 2 (docs/design/V02_STAGE_C.md): his legs learn to run while they look somewhere, and to arrive at a place
# and stand. Three more inputs at the very end (N_C2; there when look, arrive or c2 is set, zero where nothing is given):
#   the sideways angle from his view to the look point / 90 degrees (left is plus; 1 is straight to his side, 2 behind
#   him), that a look direction is given, that he is to stand at the goal.
# A LOOK try (the share `look` of the tries, whatever their kind): a point of the walking map LOOK_NEAR to LOOK_FAR units
# from him, up to LOOK_OFF degrees to either side of his way, fixed in the world for LOOK_T seconds and then drawn anew
# from where he is (a stretch with none at the chance LOOK_NONE): the angle changes as he moves, as to the place he
# believes an enemy at. Progress counts only as far as his view is on it: in full within LOOK_IN degrees sideways, not
# at all beyond LOOK_OUT, a straight line between (MOVE_LOOK_OUT=<degrees> sets a wider edge for the start of a
# training, should the narrow one give it too little to go by; 45 is the rule). In such a try progress is paid on new
# ground only (the try's running best: a stretch of way given back while he looked away and made again while he looked
# is paid once, and a step back costs the time alone). Everything else is as in any try: the frame's time, an arrival,
# a jump made, lava and falls.
# An ARRIVE try (the share `arrive`): the goal is a place to stand at (the map's holding places of sim/pro_holds/<map>.json
# where stage B part 2 has written them, and ARRIVE_MORE points of the walking map with floor all round and as many at
# a ledge), "stand at the goal" is set from its start and the try does not end at the goal. Until he is first within
# STAND_R units of it (STAND_Z in height) everything is as in any try. From the next frame on: he stands while he is
# within that distance at under STAND_SPEED units a second over the ground; a frame standing pays STAND_PAY (with a look
# direction given: as far as his view is on it), the first one 1 as well (what an arrival pays); every other frame
# costs its time as before; outside the distance the progress he has lost by leaving is charged (against the try's
# running best, 0.5 s a frame at most) and what was charged is returned as he comes back, never more: leaving and
# coming back cannot earn. It ends STAND_T seconds after he was first within the distance.
N_C2 = 3
LOOK_IN, LOOK_OUT, LOOK_OFF = 30.0, max(31.0, float(os.environ.get("MOVE_LOOK_OUT") or 45.0)), 120.0
LOOK_NEAR, LOOK_FAR, LOOK_T, LOOK_NONE = 200.0, 1500.0, (2.0, 5.0), 0.2
STAND_R, STAND_Z, STAND_SPEED = 96.0, 64.0, 100.0           # (duel_env's HOLD_R and HOLD_Z of stage B part 2)
STAND_PAY, STAND_T, ARRIVE_MORE = 0.0125, (3.0, 6.0), 12
OBS_DIM = 3 + 1 + 12 + 4 + 3 + 1 + N_WALL + N_FLOOR


def shut_teleports(world, nav_path):
    """the walking map's teleporter links that cannot be taken: the straight line from the link's start to the teleporter's
    entrance is shut by one of the map's solid pieces (the map was walked without them; Battleforged, 2026-10-09: the
    movement network stood before three such faces in 30% of its tries). The same rule as duel_env's WALK_FIX."""
    if not getattr(world, "solids", None):
        return None
    g = json.load(open(nav_path))
    nd = np.array(g["nodes"], np.float32)
    sp = world.trigger_spots()
    tin = np.array([c for k, c, d in sp if k == 1], np.float32).reshape(-1, 3)
    tout = np.array([d for k, c, d in sp if k == 1], np.float32).reshape(-1, 3)
    drop = set()
    for a, b, t, kind in g["edges"]:
        if kind == "tele" and len(tin):
            j = int(np.linalg.norm(tout - nd[b], axis=1).argmin())
            if np.linalg.norm(tout[j] - nd[b]) < 150.0 and world.trace(nd[a], tin[j])["fraction"] < 0.97:
                drop.add((int(a), int(b)))
    return drop


def teleports(world):
    """the map's teleporters: (entrances, exits)"""
    sp = world.trigger_spots()
    return (np.array([c for k, c, d in sp if k == 1], np.float32).reshape(-1, 3),
            np.array([d for k, c, d in sp if k == 1], np.float32).reshape(-1, 3))


def arrive_points(world, nav_path, mapname, hazard):
    """the goals of the arrive tries (stage C part 2): the map's holding places (sim/pro_holds/<map>.json of stage B part
    2: the real ones, where the file is there), then ARRIVE_MORE points of the walking map with floor all round and as
    many at a ledge (a drop of 100 units or more, or lava, on two or more of the eight sides 96 units away, floor on
    three or more), drawn from a random stream of the map's own (the same in every worker and every run)."""
    pts = []
    hf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_holds", mapname.lower() + ".json")
    if os.path.exists(hf):
        with open(hf, encoding="utf-8") as fh:
            pts += [[float(x) for x in p_["pos"]] for p_ in (json.load(fh).get("places") or [])]
    nodes = np.array(json.load(open(nav_path))["nodes"], np.float32)
    down = np.array([[0, 0, -1.0]], np.float32)
    ok = np.array([world.cluster(p) >= 0 for p in nodes]) & (world.rays(nodes, down, 64.0)[:, 0] < 1)
    ang = np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False)
    st = np.concatenate([nodes[:, None, :2] + (np.stack([np.cos(ang), np.sin(ang)], 1) * 96.0)[None, :, :],
                         np.repeat(nodes[:, None, 2:3], N_FLOOR, 1)], 2).reshape(-1, 3).astype(np.float32)
    fr = world.rays(st, down, 256.0).reshape(-1)
    drop = fr * 256.0 > 124.0
    if hazard:
        end = st + np.array([0, 0, -1.0], np.float32)[None, :] * (fr * 256.0 - 4.0)[:, None]
        drop |= (world.contents_n(end) & HAZARD) != 0
        ok &= (world.contents_n(nodes + np.array([0, 0, -23.0], np.float32)) & HAZARD) == 0
    drop = drop.reshape(len(nodes), N_FLOOR)
    flat = (fr * 256.0 < 64.0).reshape(len(nodes), N_FLOOR) & ~drop
    rng = np.random.default_rng(zlib.crc32(mapname.lower().encode()))
    for sel in (ok & flat.all(1), ok & (drop.sum(1) >= 2) & (flat.sum(1) >= 3)):
        idx = np.nonzero(sel)[0]
        if len(idx):
            pts += [[float(x) for x in nodes[k]] for k in rng.choice(idx, min(ARRIVE_MORE, len(idx)), replace=False)]
    return pts


class NavField:
    """nav graph -> time-to-goal for every node and goal, next hops, fast position lookup"""

    def __init__(self, nav_path, goals, world=None, hazard=False, starts=None, drop=None, tele=None, jumps=None):
        g = json.load(open(nav_path))
        self.nodes = np.array(g["nodes"], np.float32)
        n = len(self.nodes)
        # recorded graphs contain junk (other map versions, glitches): with the real map, drop points outside
        # the playable space and only spawn players on points that have floor under them
        self.valid = np.ones(n, bool)
        self.spawnable = np.ones(n, bool)
        if world is not None:
            self.valid = np.array([world.cluster(p) >= 0 for p in self.nodes])
            floor = world.rays(self.nodes, np.array([[0, 0, -1.0]], np.float32), 64.0)[:, 0] < 1
            self.spawnable = self.valid & floor
            if hazard:                                        # v14: no point with its feet in lava or slime
                wet = (world.contents_n(self.nodes + np.array([0, 0, -23.0], np.float32)) & HAZARD) != 0
                self.valid &= ~wet
                self.spawnable &= ~wet
        radj = [[] for _ in range(n)]
        have = set()
        enter = {}                                            # v14: a teleporter link -> its entrance
        edges = [e for e in g["edges"] if self.valid[e[0]] and self.valid[e[1]] and not (drop and (e[0], e[1]) in drop)]
        for a, b, t, kind in edges:
            d = float(np.linalg.norm(self.nodes[a] - self.nodes[b]))
            cost = 0.1 if kind == "tele" else (d / RUN if kind == "walk" else max(t, d / 900.0))
            if kind == "tele" and tele is not None and len(tele[0]):
                # v14: a teleporter link costs the walk to its entrance, and one that starts far from the entrance is left
                # out (the walking map has links from 360 to 410 units away at 0.1 s: the way then "teleported" from
                # there, and the network, shown the far exit as its next point, ran at a wall; Battleforged, 2026-10-09)
                j = int(np.linalg.norm(tele[1] - self.nodes[b], axis=1).argmin())
                if np.linalg.norm(tele[1][j] - self.nodes[b]) < 150.0:
                    d_in = float(np.linalg.norm(tele[0][j] - self.nodes[a]))
                    if d_in > TELE_FAR:
                        continue
                    cost = 0.1 + d_in / RUN
                    enter[(a, b)] = tele[0][j]
            radj[b].append((a, cost, kind))
            have.add((a, b))
        for a, b, t, kind in edges:                           # flat walking works both ways
            if kind == "walk" and (b, a) not in have and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                radj[a].append((b, float(np.linalg.norm(self.nodes[a] - self.nodes[b])) / RUN, "walk"))
        self.kd_idx = np.nonzero(self.valid)[0]
        self._kd = cKDTree(self.nodes[self.kd_idx] * np.array([1, 1, 2.0], np.float32))   # vertical counts double
        self.jumps = list(jumps or [])                        # v15: the pros' jumps as links (sim/jump_links.py)
        jl = {}                                               # (from, to) -> the jump's index
        for a, b, t, k in (JL.links(self.jumps, self.nodes, lambda p: self.locate(p)[0], ok=self.valid) if self.jumps else ()):
            radj[b].append((a, t, "jump"))
            jl[(a, b)] = k
        self.radj, self._enter, self._jl = radj, enter, jl     # (kept for sim/ways.py: the second and third sets of ways)
        self.goals = np.array(goals, np.float32)
        G = len(goals)
        self.T = np.full((G, n), 1e9, np.float32)
        self.next = np.full((G, n), -1, np.int32)
        self.next_kind = np.zeros((G, n), np.int8)            # 0 walk, 1 air, 2 teleport, 3 one of the pros' jumps
        self.jlink = np.full((G, n), -1, np.int32)            # the jump the step from a point is (-1: a plain step)
        self.via = np.full((G, n, 3), np.nan, np.float32) if enter else None    # v14: where to step in, for a teleporter step
        for gi, gp in enumerate(self.goals):
            b, _ = self.locate(gp[None])
            b = int(b[0])
            dist = {b: 0.0}
            pq = [(0.0, b)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c, kind in radj[u]:                      # v -> u costs c
                    nd = d + c
                    if nd < dist.get(v, 1e18):
                        dist[v] = nd
                        self.next[gi, v] = u
                        self.next_kind[gi, v] = {"walk": 0, "air": 1, "tele": 2, "jump": 3}[kind]
                        self.jlink[gi, v] = jl.get((v, u), -1) if kind == "jump" else -1
                        if self.via is not None:
                            self.via[gi, v] = enter.get((v, u), np.nan)
                        heapq.heappush(pq, (nd, v))
            for v, d in dist.items():
                self.T[gi, v] = d
        self.reach = self.T < 1e8
        self.jd = self.ji = None                              # per goal and point: the way to the first jump ahead, and which
        if self.jumps:
            la = [JL.look_ahead(self.next[gi], self.jlink[gi], self.nodes) for gi in range(G)]
            self.jd, self.ji = np.stack([x[0] for x in la]), np.stack([x[1] for x in la])
        if starts is not None and len(starts):                # v14: a try starts only where the spawn points lead
            fwd = [[] for _ in range(n)]
            for b_ in range(n):
                for a_, c_, k_ in radj[b_]:
                    fwd[a_].append(b_)
            seen = np.zeros(n, bool)
            todo = [int(x) for x in np.unique(self.locate(np.asarray(starts, np.float32))[0])]
            seen[todo] = True
            while todo:
                u = todo.pop()
                for v in fwd[u]:
                    if not seen[v]:
                        seen[v] = True
                        todo.append(v)
            self.live = seen
            self.spawnable &= seen

    def locate(self, pos):
        d, k = self._kd.query(pos * np.array([1, 1, 2.0], np.float32))
        return self.kd_idx[k], d

    def potential(self, goal_idx, pos):
        """estimated seconds to the goal from pos (graph time from the nearest node + straight bit)"""
        idx, d = self.locate(pos)
        return self.T[goal_idx, idx] + d / RUN, idx


class MoveEnv:
    def __init__(self, bsp, nav_path, n=512, seed=0, max_goal_time=8.0, min_goal_time=0.8, substeps=(8, 8, 9),
                 stall_limit=5.0, obs_noise=0.0, delay_p=0.0, v14=False, jumps=False, jump_p=0.5, hand=False, mouse=False, mouse_rev=MOUSE_REV,
                 look=0.0, arrive=0.0, c2=False):
        """substeps: physics steps (ms) per 25 ms decision. (8, 8, 9) = a 125 fps human: the frame-rate
        dependent ground-strafe boost that 40 Hz bots get (25,) is not available, as for real players."""
        self.w = World(bsp, n=n)
        self.v14 = bool(v14)
        if self.v14:                                           # the game's own step height and wading, its solid pieces
            from qsim import QL_STEP, QL_WADE
            self.w.set_params2(QL_WADE, QL_STEP)
            self.w.add_solids()
        # Quake Live's physics of B-252 / B-258, from the environment as in duel_env.py (all off: Quake 3's, as before)
        ql_float, ql_fwd, ql_land = (float(os.environ.get(k_) or 0.0) > 0 for k_ in ("QL_FLOAT", "QL_FWD", "QL_LAND"))
        if ql_float or hasattr(self.w.lib, "qsim_snap"):
            self.w.set_snap(not ql_float)
        if ql_fwd or ql_land or hasattr(self.w.lib, "qsim_params3"):
            self.w.set_params3(ql_fwd, ql_land)
        ql_jump = float(os.environ.get("QL_JUMP") or 0.0) > 0
        if ql_jump or hasattr(self.w.lib, "qsim_params4"):
            self.w.set_params4(ql_jump)
        self.substeps = tuple(substeps)
        self.stall_limit = stall_limit
        # robustness for transfer to the real game: noisy senses and the odd one-frame-late command
        self.obs_noise, self.delay_p = obs_noise, delay_p
        self.prev_actions = None
        self.n = n
        self.rng = np.random.default_rng(seed)
        goals = [e["origin"] for e in self.w.entities
                 if e.get("classname", "").startswith(GOAL_CLASSES) and "origin" in e
                 and not (self.v14 and e["classname"] == "item_quad")]
        starts = [e["origin"] for e in self.w.spawns()]
        # v15 (jumps): the pros' jumps of this map are links of the walking map, five more inputs tell of a jump ahead
        # (zeros on a map without a list), and a share of the tries (jump_p) begins a second or two before a take-off
        self.jump_obs = bool(jumps)
        self.jumps = JL.load(os.path.splitext(os.path.basename(bsp))[0]) if jumps else []
        self.n_items = len(goals)                              # (a plain try's goal is an item; a jump's landing is a goal too, so
        goals = goals + [j_["b"] for j_ in self.jumps]         # that every jump has tries: many lie on no item's shortest way)
        self.look_p, self.arrive_p = float(look), float(arrive)        # stage C part 2 (see N_C2): the shares of look tries, of arrive tries
        self.c2 = N_C2 if (self.look_p > 0 or self.arrive_p > 0 or c2) else 0     # ... and how many inputs there are for them
        self.n_plain = len(goals)                              # (the goals of the plain tries and of the jumps' tries end here)
        if self.arrive_p > 0:                                  # the places to stand at, as goals after them
            goals = goals + arrive_points(self.w, nav_path, os.path.splitext(os.path.basename(bsp))[0], self.v14)
        self.field = NavField(nav_path, goals, world=self.w, hazard=self.v14, starts=starts if self.v14 else None,
                              drop=shut_teleports(self.w, nav_path) if self.v14 else None,
                              tele=teleports(self.w) if self.v14 else None, jumps=self.jumps)
        self.jump_p = float(jump_p) if self.jumps else 0.0
        self.try_by_k = {}                                     # jump -> [(goal, the points a try can begin at)]
        for g_ in range(self.n_plain if self.jumps else 0):    # (not the arrive tries' goals: a jump's try is to an item or its landing)
            for k_ in range(len(self.jumps)):
                st_ = np.nonzero((self.field.ji[g_] == k_) & (self.field.jd[g_] > JL.run_up(self.jumps[k_]["need"]))
                                 & (self.field.jd[g_] < 1300.0) & self.field.spawnable)[0]
                if len(st_):
                    self.try_by_k.setdefault(k_, []).append((g_, st_))
        self.jump_a = np.array([j["a"] for j in self.jumps], np.float32).reshape(-1, 3)
        self.jump_b = np.array([j["b"] for j in self.jumps], np.float32).reshape(-1, 3)
        self.hand = bool(hand)                                 # v15: his finger limits on the keys, and five inputs of what the hand holds
        self.mouse = bool(mouse)                               # v15: his mouse (see mouse_turn), and three inputs of what it does
        self.mouse_rev = float(mouse_rev)                      # ... the frames between two changes of the turn's direction
        self.mv = np.zeros(n, np.float32)                      # the view's turning speed, degrees a frame
        self.turn_dir = np.zeros(n, np.float32)                # the direction the hand turns (-1, 0 at the start, 1)
        self.rev_wait = np.zeros(n, np.float32)                # frames until it may change direction again
        self.key_last = np.tile(np.array([1, 1, 0], np.int64), (n, 1))     # the keys as they are held: forward, strafe, jump
        self.key_req = self.key_last.copy()                    # ... as last asked for
        self.key_hold = np.full((n, 4), 99, np.int64)          # frames since each finger acted
        self.key_tok = np.full(n, KEY_BURST, np.float32)
        self.key_tick = 0
        self.key_dec = np.ones(n, bool)                        # the keys were read this frame
        self.key_wait = ((-(1 + np.arange(n))) % KEY_EVERY).astype(np.float32)   # frames until they are read next (0: at the next step)
        self.try_k = np.full(n, -1, np.int32)                  # the jump this try is for (-1: a plain try)
        self.crossed = np.zeros(n, bool)
        self.at_edge = np.zeros(n, bool)
        self.fall_dmg = np.zeros(n, np.float32)
        self.spawn_nodes = np.nonzero(self.field.spawnable)[0]
        # stage C part 2: the arrive tries' goals that tries can start for, and each player's books
        t_ = self.field.T[self.n_plain:][:, self.spawn_nodes]
        self.arr_goals = self.n_plain + np.nonzero(((t_ >= min_goal_time) & (t_ <= 15.0)).sum(1) >= 20)[0]
        self.look_nodes = self.field.nodes[self.field.kd_idx]  # the points a look point is taken from
        self.look_try = np.zeros(n, bool)                      # a look try,
        self.look_on = np.zeros(n, bool)                       # ... a look direction is given now,
        self.look_pt = np.zeros((n, 3), np.float32)            # ... the point,
        self.look_t = np.zeros(n, np.float32)                  # ... seconds until it is drawn anew
        self.stand = np.zeros(n, bool)                         # an arrive try ("stand at the goal"),
        self.arr_len = np.zeros(n, np.float32)                 # ... the seconds it lasts after he was first within the distance,
        self.arr_t = np.full(n, -1.0, np.float32)              # ... the second of the try that was (-1: not yet),
        self.arr_sp = np.zeros(n, np.float32)                  # ... his speed over the ground as he crossed it,
        self.arr_stood = np.zeros(n, bool)                     # ... he has stood there (the first frame pays 1),
        self.arr_owed = np.zeros(n, np.float32)                # ... the lost progress charged and not yet returned, seconds,
        self.arr_n = np.zeros((n, 3), np.int64)                # ... frames since: all, within the distance, standing,
        self.arr_fell = np.zeros(n, bool)                      # ... he dropped below the place since
        self.c2_now = np.zeros(8, np.float64)                  # the frame's counters (_c2_pay)
        self.goal_pos = self.field.goals
        self.max_goal_time, self.min_goal_time = max_goal_time, min_goal_time
        nodes = self.field.nodes
        self.zmin = float(nodes[:, 2].min()) - 300
        ang = np.linspace(0, 2 * np.pi, N_WALL, endpoint=False)
        self.wall_dirs = np.stack([np.cos(ang), np.sin(ang), np.zeros_like(ang)], 1).astype(np.float32)
        fang = np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False)
        self.floor_off = np.stack([np.cos(fang), np.sin(fang)], 1).astype(np.float32) * 96.0
        self.goal = np.zeros(n, np.int32)
        self.yaw = np.zeros(n, np.float32)
        self.t = np.zeros(n, np.float32)
        self.limit = np.zeros(n, np.float32)
        self.phi = np.zeros(n, np.float32)
        self.best_phi = np.zeros(n, np.float32)
        self.stall = np.zeros(n, np.float32)
        self.start_phi = np.zeros(n, np.float32)
        for i in range(n):
            self._reset(i)
        self.state = self.w.state()

    def _reset(self, i):
        f = self.field
        self.try_k[i], self.crossed[i], self.at_edge[i] = -1, False, False
        self.key_last[i], self.key_req[i], self.key_hold[i], self.key_tok[i] = (1, 1, 0), (1, 1, 0), 99, KEY_BURST
        self.mv[i], self.turn_dir[i], self.rev_wait[i] = 0.0, 0.0, 0.0
        if self.c2:
            self._c2_clear(i)
        if self.arrive_p and len(self.arr_goals) and self.rng.random() < self.arrive_p:     # an arrive try: to a place, and stand there
            for _ in range(50):
                g = int(self.arr_goals[self.rng.integers(len(self.arr_goals))])
                node = int(self.spawn_nodes[self.rng.integers(len(self.spawn_nodes))])
                T = f.T[g, node]
                if self.min_goal_time <= T <= self.max_goal_time and f.next[g, node] >= 0:
                    break
            self.stand[i], self.arr_len[i] = True, self.rng.uniform(*STAND_T)
        elif self.jump_p and self.try_by_k and self.rng.random() < self.jump_p:
            ks = list(self.try_by_k)                           # (every jump as often as any other)
            k = int(ks[self.rng.integers(len(ks))])
            g, st = self.try_by_k[k][int(self.rng.integers(len(self.try_by_k[k])))]
            node = int(st[self.rng.integers(len(st))])
            T = f.T[g, node]
            self.try_k[i] = k
        else:
            for _ in range(50):
                g = int(self.rng.integers(getattr(self, "n_items", len(self.goal_pos))))
                node = int(self.spawn_nodes[self.rng.integers(len(self.spawn_nodes))])
                T = f.T[g, node]
                if self.min_goal_time <= T <= self.max_goal_time and f.next[g, node] >= 0:
                    break
        nxt = f.nodes[f.next[g, node]]
        p = f.nodes[node]
        face = math.degrees(math.atan2(nxt[1] - p[1], nxt[0] - p[0])) + float(self.rng.uniform(-90, 90) if self.try_k[i] < 0 else self.rng.uniform(-40, 40))
        self.w.reset(i, (p[0], p[1], p[2] + 2.0), (0, 0, 0), face)
        self.goal[i], self.yaw[i], self.t[i] = g, face, 0.0
        self.phi[i] = T
        self.best_phi[i] = T
        self.start_phi[i] = T
        self.stall[i] = 0.0
        self.limit[i] = 2.0 * T + 5.0
        if self.look_p and self.rng.random() < self.look_p:    # a look try: somewhere to look while he runs (any kind of try)
            self.look_try[i] = True
            self._look_draw(i, p, math.degrees(math.atan2(nxt[1] - p[1], nxt[0] - p[0])))

    def place(self, i, pos, yaw, goal_idx):
        """start player i at pos facing yaw, heading for goal goal_idx (evaluation)"""
        self.w.reset(i, (pos[0], pos[1], pos[2] + 2.0), (0, 0, 0), yaw)
        T, _ = self.field.potential(np.array([goal_idx]), np.array([pos], np.float32))
        self.goal[i], self.yaw[i], self.t[i] = goal_idx, yaw, 0.0
        if hasattr(self, "try_k"):
            self.try_k[i], self.crossed[i], self.at_edge[i] = -1, False, False
        self.phi[i] = self.best_phi[i] = self.start_phi[i] = T[0]
        self.stall[i] = 0.0
        self.limit[i] = 30.0
        if getattr(self, "c2", 0):                             # (stage C part 2: nothing given; a check sets it by hand)
            self._c2_clear(i)
        self.state = self.w.state()

    def observe(self):
        s = self.state
        pos, vel, ground = s[:, :3], s[:, 3:6], s[:, 6]
        yaw = np.radians(self.yaw)
        c, si = np.cos(yaw), np.sin(yaw)

        def rot(v):                                          # world xy -> view frame (forward, left)
            return np.stack([c * v[:, 0] + si * v[:, 1], -si * v[:, 0] + c * v[:, 1], v[:, 2]], 1)
        f = self.field
        pre_ = getattr(self, "pre", None)                     # (duel_env's legs: the nearest nodes and the wall and floor rays its
        self.pre = None                                       # caller worked out already for exactly these players; used once)
        if pre_ is not None and pre_[0] is not None:
            idx = pre_[0]
        else:
            idx, _ = f.locate(pos)
        wps, kinds = [], []
        cur = idx
        for _ in range(4):
            nx = f.next[self.goal, cur]
            ok = nx >= 0
            kinds.append(np.where(ok, f.next_kind[self.goal, cur], 0).astype(np.float32))
            via = f.via[self.goal, cur] if getattr(f, "via", None) is not None else None
            cur = np.where(ok, nx, cur)
            wp = f.nodes[cur]
            if via is not None:                               # v14: a step through a teleporter is shown as its entrance, not
                wp = np.where((ok & ~np.isnan(via[:, 0]))[:, None], via, wp)       # as the far place it takes him to
            wps.append(rot(wp - pos) / 512.0)
        goal = rot(self.goal_pos[self.goal] - pos) / 2000.0
        # wall rays turn with the view so the first one always points forward
        wd = self.wall_dirs
        dirs = np.stack([c[:, None] * wd[None, :, 0] - si[:, None] * wd[None, :, 1],
                         si[:, None] * wd[None, :, 0] + c[:, None] * wd[None, :, 1],
                         np.zeros((self.n, N_WALL), np.float32)], 2)
        if pre_ is not None and pre_[1] is not None:
            walls = pre_[1]
            floors = self._floor_rays(pos, c, si, fr=pre_[2])
        else:
            walls = self.w.rays_each(pos, dirs, 512.0)
            floors = self._floor_rays(pos, c, si)
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], np.concatenate(wps, 1), np.stack(kinds, 1) / 2.0,
                              goal, (self.phi / 10.0)[:, None], walls, floors], 1)
        if getattr(self, "jump_obs", False):                   # v15: the jump ahead on his way (sim/jump_links.py)
            if getattr(f, "ji", None) is not None:
                jo = JL.inputs(f.jumps, f.jd[self.goal, idx], f.ji[self.goal, idx], np.linalg.norm(f.nodes[idx] - pos, axis=1))
            else:
                jo = np.zeros((len(pos), JL.N_JUMP), np.float32)
            obs = np.concatenate([obs, jo], 1)
        if getattr(self, "hand", False):                       # v15: what his hand holds and can do
            ho = np.concatenate([(self.key_last[:, :2] - 1).astype(np.float32), self.key_last[:, 2:3].astype(np.float32),
                                 (self.key_tok / KEY_BURST)[:, None],
                                 (self.key_wait / KEY_EVERY)[:, None].astype(np.float32)], 1)
            obs = np.concatenate([obs, ho], 1)
        if getattr(self, "mouse", False):                      # v15: what his mouse is doing
            mo = np.stack([self.mv / TURN_CAP, self.turn_dir, self.rev_wait / getattr(self, "mouse_rev", MOUSE_REV)], 1).astype(np.float32)
            obs = np.concatenate([obs, mo], 1)
        if getattr(self, "c2", 0):                             # stage C part 2: where to look, and that he is to stand at the goal
            co = np.zeros((len(pos), N_C2), np.float32)        # (zeros where nothing is given, or nobody has set it: a teacher's asker)
            lk = getattr(self, "look_on", None)
            if lk is not None and len(lk) == len(pos) and lk.any():
                co[:, 0] = np.where(lk, self.look_angle(pos) / 90.0, 0.0)
                co[:, 1] = lk
            st_ = getattr(self, "stand", None)
            if st_ is not None and len(st_) == len(pos):
                co[:, 2] = st_
            obs = np.concatenate([obs, co], 1)
        if self.obs_noise:
            obs = obs + self.rng.normal(0, self.obs_noise, obs.shape)
        return obs.astype(np.float32)

    def _floor_rays(self, pos, c, si, fr=None):
        """fr: the rays' fractions [players, N_FLOOR] when the caller traced these very rays already"""
        off = np.stack([c[:, None] * self.floor_off[None, :, 0] - si[:, None] * self.floor_off[None, :, 1],
                        si[:, None] * self.floor_off[None, :, 0] + c[:, None] * self.floor_off[None, :, 1]], 2)
        starts = np.concatenate([pos[:, None, :2] + off, np.repeat(pos[:, None, 2:3], N_FLOOR, 1)], 2)
        down = np.array([[0, 0, -1.0]], np.float32)
        st = starts.reshape(-1, 3).astype(np.float32)
        fr = self.w.rays(st, down, 256.0).reshape(-1) if fr is None else np.asarray(fr, np.float32).reshape(-1)
        if getattr(self, "v14", False):                        # lava or slime where the ray ends: no floor there
            end = st + np.array([0, 0, -1.0], np.float32)[None, :] * (fr * 256.0 - 4.0)[:, None]
            fr = np.where((self.w.contents_n(end) & HAZARD) != 0, 1.0, fr)
        return fr.reshape(self.n, N_FLOOR)

    def _c2_clear(self, i):
        """stage C part 2: player i's try gives no look direction and is no arrive try (until drawn or set)"""
        self.look_try[i], self.look_on[i], self.stand[i], self.arr_t[i], self.arr_stood[i] = False, False, False, -1.0, False
        self.arr_owed[i], self.arr_sp[i], self.arr_n[i], self.arr_fell[i] = 0.0, 0.0, 0, False

    def look_angle(self, pos):
        """the sideways angle (degrees; left is plus) from each player's view to his look point"""
        d = self.look_pt - pos
        return ((np.degrees(np.arctan2(d[:, 1], d[:, 0])) - self.yaw + 180.0) % 360.0 - 180.0).astype(np.float32)

    def _way(self, i):
        """the direction (degrees) player i's way leads from where he is: to the third point ahead on it (his view's,
        where his way ends)"""
        f, p = self.field, self.state[i, :3]
        cur = int(f.locate(p[None])[0][0])
        for _ in range(3):
            nx = int(f.next[self.goal[i], cur])
            if nx < 0:
                break
            cur = nx
        d = f.nodes[cur] - p
        return float(self.yaw[i]) if float(np.hypot(d[0], d[1])) < 24.0 else math.degrees(math.atan2(d[1], d[0]))

    def _look_draw(self, i, pos, way):
        """a look try's next stretch for player i, who is at pos and whose way leads toward `way` (degrees): with the
        chance LOOK_NONE no look direction; else a point up to LOOK_OFF degrees to either side of his way (the angle
        drawn evenly) and LOOK_NEAR to LOOK_FAR units away, moved to the point of the walking map nearest to it inside
        the same angle (a map with none there: left in the air)."""
        self.look_t[i] = self.rng.uniform(*LOOK_T)
        if self.rng.random() < LOOK_NONE:
            self.look_on[i] = False
            return
        ang = math.radians(way + self.rng.uniform(-LOOK_OFF, LOOK_OFF))
        r = self.rng.uniform(LOOK_NEAR, LOOK_FAR)
        pt = np.array([pos[0] + r * math.cos(ang), pos[1] + r * math.sin(ang), pos[2]], np.float32)
        nd = self.look_nodes
        d = nd[:, :2] - np.asarray(pos[:2], np.float32)[None, :]
        off = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) - way + 180.0) % 360.0 - 180.0
        ok = np.nonzero((np.hypot(d[:, 0], d[:, 1]) >= LOOK_NEAR) & (np.abs(off) <= LOOK_OFF))[0]
        if len(ok):
            pt = nd[ok[np.linalg.norm(nd[ok] - pt[None, :], axis=1).argmin()]]
        self.look_pt[i], self.look_on[i] = pt, True

    def _c2_pay(self, s, pos, phi, reward, arrived):
        """stage C part 2 (see N_C2): the frame's pay in a look try and in an arrive try, in place of the plain one (the
        try's end is booked after it as for any try). Returns the pay; who arrived as a plain try does (an arrive try does
        not end at its goal); and for the arrive tries who has been within the distance, and whose time there is up."""
        speed = np.hypot(s[:, 3], s[:, 4])
        lk = self.look_on
        ang = np.abs(self.look_angle(pos)) if lk.any() else np.zeros(self.n, np.float32)
        gate = np.where(lk, np.clip((LOOK_OUT - ang) / (LOOK_OUT - LOOK_IN), 0.0, 1.0), 1.0).astype(np.float32)
        # a look try: progress on new ground only (the try's running best), and only as far as he looks
        reward = np.where(self.look_try, np.clip(self.best_phi - phi, 0.0, 0.5) * gate - DT, reward)
        # an arrive try
        gp = self.goal_pos[self.goal]
        inside = self.stand & (np.hypot(gp[:, 0] - pos[:, 0], gp[:, 1] - pos[:, 1]) < STAND_R) & (np.abs(gp[:, 2] - pos[:, 2]) < STAND_Z)
        second = self.stand & (self.arr_t >= 0.0)              # he was within the distance before this frame
        first = inside & ~second
        self.arr_t = np.where(first, self.t, self.arr_t).astype(np.float32)
        self.arr_sp = np.where(first, speed, self.arr_sp).astype(np.float32)
        standing = second & inside & (speed < STAND_SPEED)
        owed = np.minimum(np.maximum(phi - self.best_phi, 0.0), self.arr_owed + 0.5)     # the progress lost by leaving: charged 0.5 s a frame
        owed = np.where(second & ~inside, owed, 0.0).astype(np.float32)                  # at most; returned as he comes back, the rest inside
        new = standing & ~self.arr_stood
        self.arr_stood |= standing
        pay2 = (self.arr_owed - owed) + np.where(standing, STAND_PAY * gate, -DT) + new * 1.0
        reward = np.where(second, pay2, reward).astype(np.float32)
        self.arr_owed = owed
        self.arr_n += np.stack([second, second & inside, standing], 1)
        self.arr_fell |= second & (pos[:, 2] < gp[:, 2] - STAND_Z)
        # the counters, over the frames he travels (not an arrive try's part at the place): with a look direction given the
        # frames, of them his view within LOOK_IN degrees, the sum of his speed, frames at 400 or more; the same three
        # without one; the sum of the share of progress that counted
        here = second | first
        a_, b_ = lk & ~here, ~lk & ~here
        self.c2_now = np.array([a_.sum(), (a_ & (ang <= LOOK_IN)).sum(), speed[a_].sum(), (a_ & (speed >= 400.0)).sum(),
                                b_.sum(), speed[b_].sum(), (b_ & (speed >= 400.0)).sum(), gate[a_].sum()], np.float64)
        return reward, arrived & ~self.stand, (here, here & (self.t - self.arr_t >= self.arr_len))

    def _c2_ep(self, i, fell):
        """what a finished try's record says of stage C part 2: a look try, an arrive try; for an arrive try `arrived` is
        that he came within the distance and `t` the second he did, then the frames after it (all, within the distance,
        standing), his speed as he crossed it, and that he fell after arriving (into lava, out of the map, or below
        the place)"""
        d = dict(look=bool(self.look_try[i]), stand=bool(self.stand[i]))
        if self.stand[i]:
            got = bool(self.arr_t[i] >= 0.0)
            d.update(arrived=got, after=int(self.arr_n[i, 0]), within=int(self.arr_n[i, 1]), stood=int(self.arr_n[i, 2]),
                     cross=float(self.arr_sp[i]), fell_after=bool(got and (fell or self.arr_fell[i])))
            if got:
                d["t"] = float(self.arr_t[i])
        return d

    def limit_keys(self, a):
        """his left hand (see duel_env.limit_keys): the keys asked for become the keys one hand can hold"""
        n = self.n
        self.key_tick += 1
        dec = ((self.key_tick + np.arange(n)) % KEY_EVERY) == 0
        self.key_dec = dec
        self.key_req = np.where(dec[:, None], a[:, :3], self.key_req)
        want = self.key_req
        self.key_tok = np.minimum(KEY_BURST, self.key_tok + KEY_RATE * DT).astype(np.float32)
        self.key_hold += 1
        ready = self.key_hold >= FINGER_HOLD[None, :]
        last = self.key_last

        def act(finger, wants):
            ok = wants & ready[:, finger] & (self.key_tok >= 1.0)
            self.key_tok[ok] -= 1.0
            self.key_hold[ok, finger] = 0
            ready[ok, finger] = False
            return ok
        j_now, j_want = last[:, 2] == 1, want[:, 2] == 1
        j_new = np.where(act(THUMB, j_now != j_want), j_want, j_now)
        d_now, d_want = last[:, 1] == 2, want[:, 1] == 2
        d_new = np.where(act(INDEX, d_now != d_want), d_want, d_now)
        l_now, l_want = last[:, 1] == 0, want[:, 1] == 0
        l_new = np.where(act(RING, l_now != l_want), l_want, l_now)
        f_now, f_want = last[:, 0], want[:, 0].copy()
        f_want = np.where((f_now != 1) & (f_want != 1) & (f_now != f_want), 1, f_want)     # a reversal first lets go
        f_new = np.where(act(MIDDLE, f_now != f_want), f_want, f_now)
        strafe = np.where(l_new & ~d_new, 0, np.where(d_new & ~l_new, 2, 1))               # both down cancel out
        self.key_last = np.stack([f_new, strafe, j_new.astype(np.int64)], 1)
        self.key_wait = ((-(self.key_tick + 1 + np.arange(n))) % KEY_EVERY).astype(np.float32)
        return self.key_last

    def mouse_turn(self, cmd):
        """his mouse: the turn asked for (degrees a frame) -> the turn the view makes. A change of direction within
        MOUSE_REV frames of the last one is not made (the view rests); the rest is followed with inertia."""
        sg = np.sign(cmd)
        rev = (sg != 0) & (self.turn_dir != 0) & (sg != self.turn_dir)
        blocked = rev & (self.rev_wait > 0)
        cmd = np.where(blocked, 0.0, cmd).astype(np.float32)
        self.rev_wait = np.where(rev & ~blocked, self.mouse_rev, np.maximum(0.0, self.rev_wait - 1.0)).astype(np.float32)
        self.turn_dir = np.where((sg != 0) & ~blocked, sg, self.turn_dir).astype(np.float32)
        sm = np.where(np.abs(cmd) <= 1.0, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH)
        self.mv = np.clip(sm * self.mv + (1.0 - sm) * cmd, -TURN_CAP, TURN_CAP).astype(np.float32)
        return self.mv

    def step(self, actions):
        a = np.asarray(actions)
        if self.delay_p and self.prev_actions is not None:
            late = self.rng.random(self.n) < self.delay_p
            a = np.where(late[:, None], self.prev_actions, a)
        self.prev_actions = a.copy()
        if self.hand:
            a = a.copy()
            a[:, :3] = self.limit_keys(a)
        fwd = (a[:, 0].astype(np.int32) - 1) * 127
        side = (a[:, 1].astype(np.int32) - 1) * 127
        jump = a[:, 2].astype(np.int32) * 127
        turn = TURN_BINS[a[:, 3]]
        if self.mouse:
            turn = self.mouse_turn(turn)
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw
        done_ms = 0
        for ms in self.substeps:                               # the turn is spread over the physics steps
            done_ms += ms
            yaw = y0 + turn * (done_ms / 25.0)
            self.w.step(moves, np.stack([np.zeros(self.n, np.float32), yaw.astype(np.float32)], 1), ms)
        self.yaw = (y0 + turn + 180.0) % 360.0 - 180.0
        prev = self.state
        self.state = s = self.w.state()
        self.yaw = s[:, 7].copy()                              # teleporters snap the view
        pos = s[:, :3]
        phi, _ = self.field.potential(self.goal, pos)
        self.t += DT
        dphi = np.clip(self.phi - phi, -0.5, 0.5)
        reward = dphi - DT
        self.phi = phi
        gp = self.goal_pos[self.goal]
        arrived = (np.hypot(gp[:, 0] - pos[:, 0], gp[:, 1] - pos[:, 1]) < 40) & (np.abs(gp[:, 2] - pos[:, 2]) < 64)
        hold = None
        if self.c2:                                            # stage C part 2: a look try's pay, an arrive try's (see N_C2)
            reward, arrived, hold = self._c2_pay(s, pos, phi, reward, arrived)
        fell = pos[:, 2] < self.zmin
        hard = np.zeros(self.n, np.float32)
        wet = np.zeros(self.n, bool)
        if self.v14:
            wet = (self.w.contents_n(pos + np.array([0, 0, -23.0], np.float32)) & HAZARD) != 0
            fell = fell | wet
            delta = prev[:, 5] ** 2 * 0.0001                   # Quake 3's fall damage, from the speed of the landing
            hard = np.where((prev[:, 6] < 0.5) & (s[:, 6] > 0.5) & (prev[:, 5] < 0),
                            np.where(delta > 60.0, 10.0, np.where(delta > 40.0, 5.0, 0.0)), 0.0).astype(np.float32)
            self.fall_dmg += hard
        over = np.zeros(self.n, bool)
        if self.jump_p:                                        # a try for a jump: over it (+1, once), or fallen short (the try ends)
            on = np.nonzero((self.try_k >= 0) & ~self.crossed)[0]
            if len(on):
                A_, B_, p_ = self.jump_a[self.try_k[on]], self.jump_b[self.try_k[on]], pos[on]
                self.at_edge[on] |= (np.hypot(p_[:, 0] - A_[:, 0], p_[:, 1] - A_[:, 1]) < 120.0) & (np.abs(p_[:, 2] - A_[:, 2]) < 64.0)
                landed = (s[on, 6] > 0.5) | ((prev[on, 5] < 0.0) & (s[on, 5] > 0.0))    # on the floor, or touched it and jumped again inside the frame
                ov = self.at_edge[on] & (np.linalg.norm(p_ - B_, axis=1) < 110.0) & (landed | arrived[on])
                over[on[ov]] = True
                self.crossed[on[ov]] = True
                fell = fell.copy()
                at_gap = np.hypot(p_[:, 0] - B_[:, 0], p_[:, 1] - B_[:, 1]) < np.hypot(A_[:, 0] - B_[:, 0], A_[:, 1] - B_[:, 1]) + 150.0
                fell[on[self.at_edge[on] & ~ov & at_gap & (p_[:, 2] < np.minimum(A_[:, 2], B_[:, 2]) - 90.0)]] = True
        improved = phi < self.best_phi - 0.05
        self.best_phi = np.minimum(self.best_phi, phi)
        self.stall = np.where(improved, 0.0, self.stall + DT)
        timeout = (self.t > self.limit) | (self.stall > self.stall_limit)
        if hold is not None:                                   # (an arrive try, once he was within the distance, ends by its own clock)
            timeout = np.where(hold[0], hold[1], timeout)
        reward = reward + arrived * 1.0 - fell * 1.0 - (LAVA_COST - 1.0) * wet - FALL_COST * hard + over * 1.0
        done = arrived | fell | timeout
        speed = np.hypot(s[:, 3], s[:, 4])
        info = dict(speed=speed, ground=s[:, 6].copy(), key_dec=self.key_dec.copy() if self.hand else None)
        if self.c2:
            info["c2"] = self.c2_now
        ep = []
        for i in np.nonzero(done)[0]:
            ep.append(dict(arrived=bool(arrived[i]), fell=bool(fell[i]), lava=bool(wet[i]), t=float(self.t[i]),
                           est=float(self.start_phi[i]), goal=int(self.goal[i]), fall_dmg=float(self.fall_dmg[i]),
                           jump=int(self.try_k[i]), crossed=bool(self.crossed[i])))
            if self.c2:
                ep[-1].update(self._c2_ep(int(i), bool(fell[i])))
            self.fall_dmg[i] = 0.0
            self._reset(int(i))
        if len(ep):
            self.state = self.w.state()
        if self.look_p:                                        # a look try's point is drawn anew every few seconds, from where he is
            self.look_t = (self.look_t - DT).astype(np.float32)
            for i in np.nonzero(self.look_try & (self.look_t <= 0.0))[0]:
                self._look_draw(int(i), self.state[i, :3], self._way(int(i)))
        info["episodes"] = ep
        return self.observe(), reward.astype(np.float32), done, info

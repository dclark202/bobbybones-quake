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

RUN = 320.0
DT = 0.025
TURN_BINS = np.array([-30, -15, -6, -2, 0, 2, 6, 15, 30], np.float32)
ACTION_DIMS = (3, 3, 2, len(TURN_BINS))
GOAL_CLASSES = ("weapon_", "item_armor_body", "item_armor_combat", "item_armor_jacket", "item_health_mega",
                "item_health_large", "item_quad")
N_WALL, N_FLOOR = 16, 8
OBS_DIM = 3 + 1 + 12 + 4 + 3 + 1 + N_WALL + N_FLOOR


class NavField:
    """nav graph -> time-to-goal for every node and goal, next hops, fast position lookup"""

    def __init__(self, nav_path, goals, world=None):
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
        radj = [[] for _ in range(n)]
        have = set()
        edges = [e for e in g["edges"] if self.valid[e[0]] and self.valid[e[1]]]
        for a, b, t, kind in edges:
            d = float(np.linalg.norm(self.nodes[a] - self.nodes[b]))
            cost = 0.1 if kind == "tele" else (d / RUN if kind == "walk" else max(t, d / 900.0))
            radj[b].append((a, cost, kind))
            have.add((a, b))
        for a, b, t, kind in edges:                           # flat walking works both ways
            if kind == "walk" and (b, a) not in have and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                radj[a].append((b, float(np.linalg.norm(self.nodes[a] - self.nodes[b])) / RUN, "walk"))
        self.kd_idx = np.nonzero(self.valid)[0]
        self._kd = cKDTree(self.nodes[self.kd_idx] * np.array([1, 1, 2.0], np.float32))   # vertical counts double
        self.goals = np.array(goals, np.float32)
        G = len(goals)
        self.T = np.full((G, n), 1e9, np.float32)
        self.next = np.full((G, n), -1, np.int32)
        self.next_kind = np.zeros((G, n), np.int8)            # 0 walk, 1 air, 2 teleport
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
                        self.next_kind[gi, v] = {"walk": 0, "air": 1, "tele": 2}[kind]
                        heapq.heappush(pq, (nd, v))
            for v, d in dist.items():
                self.T[gi, v] = d
        self.reach = self.T < 1e8

    def locate(self, pos):
        d, k = self._kd.query(pos * np.array([1, 1, 2.0], np.float32))
        return self.kd_idx[k], d

    def potential(self, goal_idx, pos):
        """estimated seconds to the goal from pos (graph time from the nearest node + straight bit)"""
        idx, d = self.locate(pos)
        return self.T[goal_idx, idx] + d / RUN, idx


class MoveEnv:
    def __init__(self, bsp, nav_path, n=512, seed=0, max_goal_time=8.0, min_goal_time=0.8, substeps=(8, 8, 9),
                 stall_limit=5.0, obs_noise=0.0, delay_p=0.0):
        """substeps: physics steps (ms) per 25 ms decision. (8, 8, 9) = a 125 fps human: the frame-rate
        dependent ground-strafe boost that 40 Hz bots get (25,) is not available, as for real players."""
        self.w = World(bsp, n=n)
        self.substeps = tuple(substeps)
        self.stall_limit = stall_limit
        # robustness for transfer to the real game: noisy senses and the odd one-frame-late command
        self.obs_noise, self.delay_p = obs_noise, delay_p
        self.prev_actions = None
        self.n = n
        self.rng = np.random.default_rng(seed)
        goals = [e["origin"] for e in self.w.entities
                 if e.get("classname", "").startswith(GOAL_CLASSES) and "origin" in e]
        self.field = NavField(nav_path, goals, world=self.w)
        self.spawn_nodes = np.nonzero(self.field.spawnable)[0]
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
        for _ in range(50):
            g = int(self.rng.integers(len(self.goal_pos)))
            node = int(self.spawn_nodes[self.rng.integers(len(self.spawn_nodes))])
            T = f.T[g, node]
            if self.min_goal_time <= T <= self.max_goal_time and f.next[g, node] >= 0:
                break
        nxt = f.nodes[f.next[g, node]]
        p = f.nodes[node]
        face = math.degrees(math.atan2(nxt[1] - p[1], nxt[0] - p[0])) + float(self.rng.uniform(-90, 90))
        self.w.reset(i, (p[0], p[1], p[2] + 2.0), (0, 0, 0), face)
        self.goal[i], self.yaw[i], self.t[i] = g, face, 0.0
        self.phi[i] = T
        self.best_phi[i] = T
        self.start_phi[i] = T
        self.stall[i] = 0.0
        self.limit[i] = 2.0 * T + 5.0

    def place(self, i, pos, yaw, goal_idx):
        """start player i at pos facing yaw, heading for goal goal_idx (evaluation)"""
        self.w.reset(i, (pos[0], pos[1], pos[2] + 2.0), (0, 0, 0), yaw)
        T, _ = self.field.potential(np.array([goal_idx]), np.array([pos], np.float32))
        self.goal[i], self.yaw[i], self.t[i] = goal_idx, yaw, 0.0
        self.phi[i] = self.best_phi[i] = self.start_phi[i] = T[0]
        self.stall[i] = 0.0
        self.limit[i] = 30.0
        self.state = self.w.state()

    def observe(self):
        s = self.state
        pos, vel, ground = s[:, :3], s[:, 3:6], s[:, 6]
        yaw = np.radians(self.yaw)
        c, si = np.cos(yaw), np.sin(yaw)

        def rot(v):                                          # world xy -> view frame (forward, left)
            return np.stack([c * v[:, 0] + si * v[:, 1], -si * v[:, 0] + c * v[:, 1], v[:, 2]], 1)
        f = self.field
        idx, _ = f.locate(pos)
        wps, kinds = [], []
        cur = idx
        for _ in range(4):
            nx = f.next[self.goal, cur]
            ok = nx >= 0
            kinds.append(np.where(ok, f.next_kind[self.goal, cur], 0).astype(np.float32))
            cur = np.where(ok, nx, cur)
            wps.append(rot(f.nodes[cur] - pos) / 512.0)
        goal = rot(self.goal_pos[self.goal] - pos) / 2000.0
        # wall rays turn with the view so the first one always points forward
        wd = self.wall_dirs
        dirs = np.stack([c[:, None] * wd[None, :, 0] - si[:, None] * wd[None, :, 1],
                         si[:, None] * wd[None, :, 0] + c[:, None] * wd[None, :, 1],
                         np.zeros((self.n, N_WALL), np.float32)], 2)
        walls = self.w.rays_each(pos, dirs, 512.0)
        floors = self._floor_rays(pos, c, si)
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], np.concatenate(wps, 1), np.stack(kinds, 1) / 2.0,
                              goal, (self.phi / 10.0)[:, None], walls, floors], 1)
        if self.obs_noise:
            obs = obs + self.rng.normal(0, self.obs_noise, obs.shape)
        return obs.astype(np.float32)

    def _floor_rays(self, pos, c, si):
        off = np.stack([c[:, None] * self.floor_off[None, :, 0] - si[:, None] * self.floor_off[None, :, 1],
                        si[:, None] * self.floor_off[None, :, 0] + c[:, None] * self.floor_off[None, :, 1]], 2)
        starts = np.concatenate([pos[:, None, :2] + off, np.repeat(pos[:, None, 2:3], N_FLOOR, 1)], 2)
        down = np.array([[0, 0, -1.0]], np.float32)
        fr = self.w.rays(starts.reshape(-1, 3).astype(np.float32), down, 256.0)
        return fr.reshape(self.n, N_FLOOR)

    def step(self, actions):
        a = np.asarray(actions)
        if self.delay_p and self.prev_actions is not None:
            late = self.rng.random(self.n) < self.delay_p
            a = np.where(late[:, None], self.prev_actions, a)
        self.prev_actions = a.copy()
        fwd = (a[:, 0].astype(np.int32) - 1) * 127
        side = (a[:, 1].astype(np.int32) - 1) * 127
        jump = a[:, 2].astype(np.int32) * 127
        turn = TURN_BINS[a[:, 3]]
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw
        done_ms = 0
        for ms in self.substeps:                               # the turn is spread over the physics steps
            done_ms += ms
            yaw = y0 + turn * (done_ms / 25.0)
            self.w.step(moves, np.stack([np.zeros(self.n, np.float32), yaw.astype(np.float32)], 1), ms)
        self.yaw = (y0 + turn + 180.0) % 360.0 - 180.0
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
        fell = pos[:, 2] < self.zmin
        improved = phi < self.best_phi - 0.05
        self.best_phi = np.minimum(self.best_phi, phi)
        self.stall = np.where(improved, 0.0, self.stall + DT)
        timeout = (self.t > self.limit) | (self.stall > self.stall_limit)
        reward = reward + arrived * 1.0 - fell * 1.0
        done = arrived | fell | timeout
        speed = np.hypot(s[:, 3], s[:, 4])
        info = dict(speed=speed, ground=s[:, 6].copy())
        ep = []
        for i in np.nonzero(done)[0]:
            ep.append(dict(arrived=bool(arrived[i]), fell=bool(fell[i]), t=float(self.t[i]),
                           est=float(self.start_phi[i]), goal=int(self.goal[i])))
            self._reset(int(i))
        if len(ep):
            self.state = self.w.state()
        info["episodes"] = ep
        return self.observe(), reward.astype(np.float32), done, info

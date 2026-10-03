"""Duel simulator, first pass: two players per match, rocket launchers, damage, knockback, respawn.

Same movement physics as movement_env (human 125 fps substeps). Each player only knows what a human would:
the opponent's position when in line of sight and inside a 110 degree view, or roughly (with noise) when heard
nearby; incoming rockets when in line of sight. One policy controls both players (self-play).
Reward: +1 frag, -1 death (a suicide counts as a death), plus a small zero-sum damage term.

Quake Live values: rocket 1000 u/s, 100 direct, 84 splash within 120 units, refire 0.8 s,
knockback 1000 * 1.1 * damage / 200 u/s, own splash damage halved (rocket jumps cost health), spawn 125 hp.
Not yet: other weapons, armor, items, ammo, health decay.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsim import World  # noqa: E402

DT = 0.025
TURN = np.array([-30, -15, -6, -2, -0.5, 0, 0.5, 2, 6, 15, 30], np.float32)
PITCH = np.array([-10, -4, -1, 0, 1, 4, 10], np.float32)
ACTION_DIMS = (3, 3, 2, len(TURN), len(PITCH), 2, 4)   # forward, strafe, jump, turn, pitch, fire, weapon (keep/RL/RG/LG)
N_WALL, N_FLOOR, N_ROCK = 16, 8, 2
OBS_DIM = 3 + 1 + 1 + 1 + 1 + N_WALL + N_FLOOR + 12 + 6 * N_ROCK + 3
ROCKET_SPEED, ROCKET_DMG, SPLASH_DMG, SPLASH_R, REFIRE = 1000.0, 100.0, 84.0, 120.0, 0.8
KNOCK, SELF_FACTOR, SPAWN_HP, VIEW_H = 1.1, 0.5, 125.0, 26.0
RG_DMG, RG_REFIRE, RG_KNOCK = 80.0, 1.5, 0.85          # measured: 80 damage, 340 u/s knockback
LG_DMG, LG_TICK, LG_RANGE, LG_KNOCK = 6.0, 0.05, 768.0, 1.167   # measured: 6 per 50 ms, 35 u/s per tick, 700 hits / 800 misses
KNOCK_OTHER, KNOCK_SELF = 0.9, 1.1                     # measured: direct hit 450 u/s, own rocket at the feet 550 u/s
SPLASH_NEAR = 20.0                                     # measured splash falloff sits ~20 units closer than box distance
SWITCH = 0.1                                             # seconds to change weapons
REACT_FRAMES = 6                                         # 150 ms: what a player knows about the opponent lags
FOV_COS = math.cos(math.radians(55))
HEAR = 800.0
K = 6                                                  # rockets in flight per player, max
MINS = np.array([-15, -15, -24], np.float32)
MAXS = np.array([15, 15, 32], np.float32)


class DuelEnv:
    def __init__(self, bsp, n_matches=256, seed=0, substeps=(8, 8, 9), dmg_reward=0.004, nav=None, close_p=0.0):
        """close_p: chance a respawn lands 300-700 units from the opponent with line of sight (curriculum: players
        rarely meet on a big map early in training). Spots come from the nav graph (sim/build_nav.py)."""
        self.M = n_matches
        self.n = 2 * n_matches                          # player i's opponent is i ^ 1
        self.w = World(bsp, n=self.n)
        self.rng = np.random.default_rng(seed)
        self.substeps = tuple(substeps)
        self.dmg_reward = dmg_reward
        self.spawns = np.array([e["origin"] for e in self.w.spawns()], np.float32)
        self.spawn_yaw = np.array([float(e.get("angle", 0)) for e in self.w.spawns()], np.float32)
        self.close_p = close_p
        self.level = 0.95                                     # pitch easing per frame (1.0 = off, for tests)
        self.round_len = 15.0                                 # seconds; matches restart (players near each other) after this
        self.round_t = self.rng.uniform(0, 15.0, n_matches).astype(np.float32)
        self.spots = None
        if nav and os.path.exists(nav):
            import json
            self.spots = np.array(json.load(open(nav))["nodes"], np.float32)
        ang = np.linspace(0, 2 * np.pi, N_WALL, endpoint=False)
        self.wall_dirs = np.stack([np.cos(ang), np.sin(ang)], 1).astype(np.float32)
        fang = np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False)
        self.floor_off = np.stack([np.cos(fang), np.sin(fang)], 1).astype(np.float32) * 96.0
        n = self.n
        self.yaw = np.zeros(n, np.float32)
        self.pitch = np.zeros(n, np.float32)
        self.hp = np.full(n, SPAWN_HP, np.float32)
        self.cool = np.zeros(n, np.float32)
        self.seen_t = np.full(n, 9.0, np.float32)      # seconds since this player last saw/heard the opponent
        self.known = np.zeros((n, 3), np.float32)       # last known opponent position
        self.rp = np.zeros((n, K, 3), np.float32)       # rockets, owned by player i
        self.rv = np.zeros((n, K, 3), np.float32)
        self.ra = np.zeros((n, K), bool)
        self.weapon = np.zeros(n, np.int64)                  # 0 RL, 1 RG, 2 LG
        self.fire_q = np.zeros(n, bool)                       # shots triggered last frame (they leave this frame)
        self.fire_w = np.zeros(n, np.int64)
        self.rnew = np.zeros((n, K), bool)                    # rockets that appeared this frame (move from the next)
        self.opp_hist = []                                    # delayed opponent features (reaction time)
        self.stats = dict(frags=0, suicides=0, shots=0, direct=0, splash_hits=0, dmg=0.0, self_dmg=0.0,
                          rg_shots=0, rg_hits=0, lg_frames=0, lg_hits=0, rl_frags=0, rg_frags=0, lg_frags=0)
        for i in range(n):
            self._spawn(i, avoid=None if i % 2 == 0 else self.w.state()[i - 1, :3])
        self.state = self.w.state()
        self.visible = np.zeros(n, bool)

    # ---------------------------------------------------------------- spawning / helpers
    def _spawn(self, i, avoid):
        if avoid is not None and self.spots is not None and self.rng.random() < self.close_p:
            d = np.linalg.norm(self.spots - avoid, axis=1)
            cand = np.nonzero((d > 300) & (d < 700))[0]
            for k in self.rng.permutation(cand)[:8]:
                p = self.spots[k]
                if self.w.trace(p + np.array([0, 0, VIEW_H], np.float32), avoid + np.array([0, 0, 8.0], np.float32))["fraction"] >= 0.999:
                    face = math.degrees(math.atan2(avoid[1] - p[1], avoid[0] - p[0])) + float(self.rng.uniform(-60, 60))
                    self.w.reset(i, (p[0], p[1], p[2] + 1.0), (0, 0, 0), face)
                    self.yaw[i], self.pitch[i] = face, 0.0
                    self.hp[i], self.cool[i] = SPAWN_HP, 0.0
                    self.weapon[i] = 0
                    self.seen_t[i] = 9.0
                    self.ra[i] = False
                    self.fire_q[i] = False
                    return
        k = int(self.rng.integers(len(self.spawns)))
        if avoid is not None:                            # QL-ish: prefer a spawn away from the opponent
            d = np.linalg.norm(self.spawns - avoid, axis=1)
            far = np.nonzero(d > np.median(d))[0]
            if len(far):
                k = int(self.rng.choice(far))
        p = self.spawns[k]
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), float(self.spawn_yaw[k]))
        self.yaw[i], self.pitch[i] = self.spawn_yaw[k], 0.0
        self.hp[i], self.cool[i] = SPAWN_HP, 0.0
        self.weapon[i] = 0
        self.seen_t[i] = 9.0
        self.ra[i] = False
        self.fire_q[i] = False

    def _eye(self, s):
        e = s[:, :3].copy()
        e[:, 2] += VIEW_H
        return e

    def _los(self, a, b):
        """line of sight a -> b for many pairs (point traces)"""
        d = b - a
        L = np.linalg.norm(d, axis=1)
        out = np.zeros(len(a), bool)
        for k in range(len(a)):
            if L[k] < 1:
                out[k] = True
                continue
            out[k] = self.w.trace(a[k], b[k])["fraction"] >= 0.999
        return out

    @staticmethod
    def _seg_box(p0, p1, c):
        """does segment p0->p1 cross the player box around center c? (slab test, vectorized)"""
        lo, hi = c + MINS, c + MAXS
        d = p1 - p0
        with np.errstate(divide="ignore", invalid="ignore"):
            t0 = (lo - p0) / d
            t1 = (hi - p0) / d
        tmin = np.nanmax(np.where(np.isfinite(np.minimum(t0, t1)), np.minimum(t0, t1), -np.inf), axis=-1)
        tmax = np.nanmin(np.where(np.isfinite(np.maximum(t0, t1)), np.maximum(t0, t1), np.inf), axis=-1)
        inside = np.all((p0 >= lo) & (p0 <= hi), axis=-1)
        return inside | ((tmax >= np.maximum(tmin, 0)) & (tmin <= 1))

    # ---------------------------------------------------------------- observation
    def observe(self):
        s = self.state
        pos, vel, ground = s[:, :3], s[:, 3:6], s[:, 6]
        n = self.n
        yaw, pit = np.radians(self.yaw), np.radians(self.pitch)
        c, si = np.cos(yaw), np.sin(yaw)

        def rot(v):
            return np.stack([c * v[:, 0] + si * v[:, 1], -si * v[:, 0] + c * v[:, 1], v[:, 2]], 1)
        wd = self.wall_dirs
        dirs = np.stack([c[:, None] * wd[None, :, 0] - si[:, None] * wd[None, :, 1],
                         si[:, None] * wd[None, :, 0] + c[:, None] * wd[None, :, 1],
                         np.zeros((n, N_WALL), np.float32)], 2)
        walls = self.w.rays_each(pos, dirs, 512.0)
        off = np.stack([c[:, None] * self.floor_off[None, :, 0] - si[:, None] * self.floor_off[None, :, 1],
                        si[:, None] * self.floor_off[None, :, 0] + c[:, None] * self.floor_off[None, :, 1]], 2)
        starts = np.concatenate([pos[:, None, :2] + off, np.repeat(pos[:, None, 2:3], N_FLOOR, 1)], 2)
        floors = self.w.rays(starts.reshape(-1, 3).astype(np.float32), np.array([[0, 0, -1.0]], np.float32),
                             256.0).reshape(n, N_FLOOR)
        # opponent: exact when visible, last known (noisy) when heard / remembered
        opp = np.arange(n) ^ 1
        rel = rot(self.known - pos) / 1000.0
        exact = self.visible.astype(np.float32)
        ovel = rot(vel[opp]) / 400.0 * exact[:, None]
        to = self.known - self._eye(s)
        hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        ang_yaw = np.arctan2(to[:, 1], to[:, 0]) - yaw
        ang_pit = -np.arctan2(to[:, 2], hd) - pit
        opp_feat = np.concatenate([[exact], [np.exp(-self.seen_t)], rel.T, ovel.T, [np.sin(ang_yaw)], [np.cos(ang_yaw)], [np.cos(ang_pit)],
                                   [np.sin(ang_pit)]], 0).T * (self.seen_t < 5)[:, None]
        # incoming rockets (the opponent's), nearest N_ROCK
        rk = np.zeros((n, 6 * N_ROCK), np.float32)
        orp, orv, ora = self.rp[opp], self.rv[opp], self.ra[opp]
        dist = np.where(ora, np.linalg.norm(orp - pos[:, None, :], axis=2), 1e9)
        order = np.argsort(dist, axis=1)[:, :N_ROCK]
        for j in range(N_ROCK):
            idx = order[:, j]
            ok = dist[np.arange(n), idx] < 1500
            rp = orp[np.arange(n), idx] - pos
            rv = orv[np.arange(n), idx]
            rk[:, 6 * j:6 * j + 3] = rot(rp) / 1000.0 * ok[:, None]
            rk[:, 6 * j + 3:6 * j + 6] = rot(rv) / 1000.0 * ok[:, None]
        # reaction time: the opponent part of the observation is what the player saw REACT_FRAMES ago
        self.opp_hist.append(opp_feat.astype(np.float32))
        if len(self.opp_hist) > REACT_FRAMES + 1:
            self.opp_hist.pop(0)
        opp_feat = self.opp_hist[0]
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], (self.hp / 200.0)[:, None],
                              (self.cool / REFIRE)[:, None], (self.pitch / 90.0)[:, None], walls, floors,
                              opp_feat, rk, np.eye(3, dtype=np.float32)[self.weapon]], 1)
        return obs.astype(np.float32)

    # ---------------------------------------------------------------- step
    def step(self, actions):
        a = np.asarray(actions)
        n = self.n
        fwd = (a[:, 0].astype(np.int32) - 1) * 127
        side = (a[:, 1].astype(np.int32) - 1) * 127
        jump = a[:, 2].astype(np.int32) * 127
        turn, dpit, fire = TURN[a[:, 3]], PITCH[a[:, 4]], a[:, 5] == 1
        want = np.where(a[:, 6] == 0, self.weapon, a[:, 6].astype(np.int64) - 1)
        sw = want != self.weapon
        self.weapon = np.where(sw, want, self.weapon)
        self.cool = np.where(sw, np.maximum(self.cool, SWITCH), self.cool)
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw.copy()
        p1 = np.clip(self.pitch * self.level + dpit, -89, 89)   # the view eases back toward level (crosshair at head height)
        done_ms = 0
        for ms in self.substeps:
            done_ms += ms
            f = done_ms / 25.0
            self.w.step(moves, np.stack([self.pitch + (p1 - self.pitch) * f, y0 + turn * f], 1).astype(np.float32), ms)
        self.pitch = p1
        self.state = s = self.w.state()
        self.yaw = s[:, 7].copy()
        reward = np.zeros(n, np.float32)
        dmg_taken = np.zeros(n, np.float32)
        attacker = np.full(n, -1)

        # fire. Measured on a real server (plugins/weaponlab.py, sim/validate_weapons.py): a shot leaves one
        # frame after the command, and a rocket does not move on the frame it appears.
        self.cool = np.maximum(0.0, self.cool - DT)
        do_fire, do_w = self.fire_q, self.fire_w
        shoot = fire & (self.cool <= 0)
        self.cool = np.where(shoot, np.array([REFIRE, RG_REFIRE, LG_TICK])[self.weapon], self.cool)
        self.fire_q, self.fire_w = shoot, self.weapon.copy()
        hitscan_kill = {}
        kicked = False
        if do_fire.any():
            yr, pr = np.radians(self.yaw), np.radians(self.pitch)
            fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1).astype(np.float32)
            eye = self._eye(s)
            for i in np.nonzero(do_fire)[0]:
                wpn = int(do_w[i])
                if wpn == 0:                                # rocket
                    slot = np.nonzero(~self.ra[i])[0]
                    if len(slot):
                        k = slot[0]
                        self.rp[i, k] = eye[i] + fdir[i] * 14.0
                        self.rv[i, k] = fdir[i] * ROCKET_SPEED
                        self.ra[i, k] = True
                        self.rnew[i, k] = True
                        self.stats["shots"] += 1
                    continue
                rng_ = 8192.0 if wpn == 1 else LG_RANGE      # railgun / lightning gun: instant trace along the view
                fr = self.w.rays_each(eye[i:i + 1], fdir[i:i + 1, None, :], rng_)[0, 0]
                end = eye[i] + fdir[i] * rng_ * fr
                v = i ^ 1
                hit = bool(self._seg_box(eye[i:i + 1], end[None], s[v:v + 1, :3])[0])
                if wpn == 1:
                    self.stats["rg_shots"] += 1
                    dmg, kf = RG_DMG, RG_KNOCK
                else:
                    self.stats["lg_frames"] += 1
                    dmg, kf = LG_DMG, LG_KNOCK
                if hit:
                    self.w.knockback(int(v), fdir[i] * (1000.0 * kf * dmg / 200.0), int(dmg))
                    kicked = True
                    self.hp[v] -= dmg
                    dmg_taken[v] += dmg
                    attacker[v] = i
                    self.stats["dmg"] += dmg
                    self.stats["rg_hits" if wpn == 1 else "lg_hits"] += 1
                    hitscan_kill[v] = wpn

        # rockets fly: direct hits on the opponent, explosions on walls
        fresh = self.rnew.copy()
        self.rnew[:] = False
        alive = np.nonzero(self.ra & ~fresh)
        if len(alive[0]):
            owner, slot = alive
            p0 = self.rp[owner, slot]
            p1r = p0 + self.rv[owner, slot] * DT
            dirs = (p1r - p0) / (ROCKET_SPEED * DT)
            fr = self.w.rays_each(p0, dirs[:, None, :], ROCKET_SPEED * DT)[:, 0]
            hitpt = p0 + (p1r - p0) * fr[:, None]
            opp = owner ^ 1
            direct = self._seg_box(p0, hitpt, s[opp, :3])
            explode = direct | (fr < 1)
            self.rp[owner, slot] = p1r
            for q in np.nonzero(explode)[0]:
                i, k = owner[q], slot[q]
                self.ra[i, k] = False
                ep = hitpt[q]
                victims = []                                  # (player, health damage, knockback points, direction)
                if direct[q]:
                    victims.append((i ^ 1, ROCKET_DMG, ROCKET_DMG, dirs[q], True))
                    self.stats["direct"] += 1
                for v in (i, i ^ 1):                        # splash on both players (owner too)
                    if direct[q] and v == (i ^ 1):
                        continue
                    c = s[v, :3]
                    e2 = ep.copy()                            # measured: splash acts SPLASH_NEAR units closer than
                    h = c[:2] - ep[:2]                        # the plain box distance (horizontally toward the player)
                    hl = float(np.linalg.norm(h))
                    if hl > 1e-3:
                        e2[:2] += h / hl * min(SPLASH_NEAR, hl)
                    near = np.clip(e2, c + MINS, c + MAXS)
                    d = float(np.linalg.norm(e2 - near))
                    if d < SPLASH_R and self.w.trace(ep, c)["fraction"] >= 0.999:
                        f_ = 1.0 - d / SPLASH_R
                        kdir = c - e2
                        kdir[2] += 24.0                       # as in Quake 3: splash pushes upward
                        kn = float(np.linalg.norm(kdir))
                        kdir = kdir / kn if kn > 1e-3 else np.array([0, 0, 1.0], np.float32)
                        victims.append((v, SPLASH_DMG * f_, ROCKET_DMG * f_, kdir, False))
                for v, dmg, kpts, kdir, is_direct in victims:
                    take = dmg * (SELF_FACTOR if v == i else 1.0)
                    kf = KNOCK_SELF if v == i else KNOCK_OTHER
                    self.w.knockback(int(v), np.asarray(kdir, np.float32) * (1000.0 * kf * kpts / 200.0), int(kpts))
                    kicked = True
                    self.hp[v] -= take
                    dmg_taken[v] += take
                    if v != i:
                        attacker[v] = i
                        self.stats["dmg"] += take
                        if not is_direct:
                            self.stats["splash_hits"] += 1
                    else:
                        self.stats["self_dmg"] += take
                        if attacker[v] < 0:
                            attacker[v] = v
        if kicked:
            self.state = s = self.w.state()                  # knockback changed velocities

        # shaping (curriculum, annealed by the trainer): reward damage dealt to the opponent. Penalizing damage
        # taken made early self-play collapse into hiding (being seen = getting shot by a random rail).
        opp_all = np.arange(n) ^ 1
        dealt = np.where(attacker[opp_all] == np.arange(n), dmg_taken[opp_all], 0.0)
        reward += self.dmg_reward * dealt
        # deaths, frags, respawns
        done = np.zeros(n, bool)
        events = []
        dead = np.nonzero(self.hp <= 0)[0]
        for v in dead:
            k = attacker[v]
            reward[v] -= 1.0
            done[v] = True
            if k >= 0 and k != v:
                reward[k] += 1.0
                self.stats["frags"] += 1
                self.stats[("rl", "rg", "lg")[hitscan_kill.get(v, 0)] + "_frags"] += 1
            else:
                self.stats["suicides"] += 1
                reward[v ^ 1] += 0.0
            events.append(dict(victim=int(v), killer=int(k)))
        for v in dead:
            self._spawn(int(v), avoid=s[v ^ 1, :3])
        # fell out of the map counts as a suicide
        lo, hi = self.w.bounds()
        out = np.nonzero(s[:, 2] < lo[2] - 64)[0]
        for v in out:
            if not done[v]:
                reward[v] -= 1.0
                done[v] = True
                self.stats["suicides"] += 1
                self._spawn(int(v), avoid=s[v ^ 1, :3])
        # short rounds (curriculum): restart both players near each other every ~round_len seconds
        self.round_t += DT
        ends = np.nonzero(self.round_t > self.round_len * self.rng.uniform(0.67, 1.33, self.M))[0]
        for m in ends:
            self.round_t[m] = 0.0
            a_, b_ = 2 * m, 2 * m + 1
            done[a_] = done[b_] = True
            self._spawn(a_, avoid=None)
            self._spawn(b_, avoid=self.w.state()[a_, :3])
        if len(dead) or len(out) or len(ends):
            self.state = s = self.w.state()

        # senses: sight (line of sight + field of view) and hearing (rough position)
        eye = self._eye(s)
        opp = np.arange(n) ^ 1
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        yr, pr = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        infov = (to * fdir).sum(1) / dist > FOV_COS
        cand = np.nonzero(infov & (dist < 4000))[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = self._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        self.visible = vis
        heard = (~vis) & (dist < HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250)
        self.known[vis] = s[opp[vis], :3]
        if heard.any():
            self.known[heard] = s[opp[heard], :3] + self.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        self.seen_t = np.where(vis | heard, 0.0, self.seen_t + DT)
        info = dict(events=events)
        return self.observe(), reward.astype(np.float32), done, info

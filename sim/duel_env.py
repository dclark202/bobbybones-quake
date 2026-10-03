"""Duel simulator: two players per match, weapons, items, damage, knockback, respawn. Self-play ready.

Same movement physics as movement_env (human 125 fps substeps). Each player only knows what a human would:
the opponent's position when in line of sight and inside a 110 degree view (150 ms late), or roughly when
heard nearby; incoming rockets; item positions (map knowledge) and whether an item is up only while looking
at it. One policy can control both players (self-play).
Reward: +1 frag, -1 death (suicide = death), plus optional damage-dealt shaping (curriculum).

Weapons (checked against a real server, see docs/FINDINGS.md and sim/validate_weapons.py):
  rocket launcher  100 direct, 84 splash within 120 units, 1000 u/s, refire 0.8 s
  railgun          80, instant, refire 1.5 s
  lightning gun    6 per 50 ms, range 768
  machine gun      5 per 100 ms, instant (fallback, always owned; damage not yet checked against the game)
  A shot leaves one frame after the command. Knockback: 5 u/s per point, x0.9 on others, x1.1 on yourself,
  own splash damage halved (rocket jumps cost ~42 hp).
Items (Quake Live duel rules; pickup amounts and ammo caps not yet checked against the game):
  health +5 (to 200) / +25 / +50 (to 100) / mega +100 (to 200), respawn 35 s; armor shard +5 / 25 / 50 / 100
  (to 200), respawn 25 s; weapons respawn 5 s; ammo 40 s. Armor absorbs 2/3 of damage. Health and armor above
  100 decay 1 per second. Spawn: 125 health, 0 armor.
Aim: mouse-like. The policy picks a turn speed (0.1 .. 60 degrees per frame, so fine tracking and flicks are
both possible); the view follows it with a little inertia, and jerky changes cost a tiny bit of reward.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsim import World  # noqa: E402

DT = 0.025
_T = [0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60]
TURN = np.array([-v for v in reversed(_T)] + [0] + _T, np.float32)            # degrees per frame
_P = [0.1, 0.3, 1, 3, 8, 20]
PITCH = np.array([-v for v in reversed(_P)] + [0] + _P, np.float32)
WEAPONS = ("rl", "rg", "lg", "mg")
ACTION_DIMS = (3, 3, 2, len(TURN), len(PITCH), 2, 5)   # forward, strafe, jump, turn, pitch, fire, weapon (keep/RL/RG/LG/MG)
N_WALL, N_FLOOR, N_ROCK = 16, 8, 2
SLOTS = ("MH", "RA", "YA", "GA", "RL", "RG", "LG")     # nearest item of each kind is an input
OBS_DIM = 3 + 1 + 5 + 2 + N_WALL + N_FLOOR + 12 + 6 * N_ROCK + 4 + 3 + 3 + 6 * len(SLOTS)

ROCKET_SPEED, ROCKET_DMG, SPLASH_DMG, SPLASH_R, REFIRE = 1000.0, 100.0, 84.0, 120.0, 0.8
RG_DMG, RG_REFIRE, RG_KNOCK = 80.0, 1.5, 0.85          # measured: 80 damage, 340 u/s knockback
LG_DMG, LG_TICK, LG_RANGE, LG_KNOCK = 6.0, 0.05, 768.0, 1.167   # measured: 6 per 50 ms, 35 u/s per tick
MG_DMG, MG_TICK, MG_KNOCK = 5.0, 0.1, 1.0              # not yet measured
KNOCK_OTHER, KNOCK_SELF = 0.9, 1.1                     # measured: direct hit 450 u/s, own rocket at the feet 550 u/s
SPLASH_NEAR = 20.0                                     # measured splash falloff sits ~20 units closer than box distance
SELF_FACTOR, SPAWN_HP, VIEW_H = 0.5, 125.0, 26.0
SWITCH = 0.1                                           # seconds to change weapons (not yet measured)
REACT_FRAMES = 6                                       # 150 ms: what a player knows about the opponent lags
MOUSE_SMOOTH = 0.5                                     # view velocity inertia per frame
JERK_COST = 0.00002                                    # reward cost per degree/frame of change in the turn command
FOV_COS = math.cos(math.radians(55))
HEAR = 800.0
K = 6                                                  # rockets in flight per player, max
MINS = np.array([-15, -15, -24], np.float32)
MAXS = np.array([15, 15, 32], np.float32)
ARMOR_ABSORB = 0.66
AMMO_MAX = np.array([25, 25, 150], np.float32)         # rockets, slugs, cells
LOADOUTS = {"full": ((True, True, True), (10, 5, 60)), "mg": ((False, False, False), (0, 0, 0))}
# classname -> (kind, value, respawn seconds, cap, slot label)
ITEM_DEFS = {
    "item_health_small": ("hp", 5, 35, 200, None), "item_health": ("hp", 25, 35, 100, None),
    "item_health_large": ("hp", 50, 35, 100, None), "item_health_mega": ("hp", 100, 35, 200, "MH"),
    "item_armor_shard": ("ar", 5, 25, 200, None), "item_armor_jacket": ("ar", 25, 25, 200, "GA"),
    "item_armor_combat": ("ar", 50, 25, 200, "YA"), "item_armor_body": ("ar", 100, 25, 200, "RA"),
    "weapon_rocketlauncher": ("wp", 0, 5, 5, "RL"), "weapon_railgun": ("wp", 1, 5, 5, "RG"),
    "weapon_lightning": ("wp", 2, 5, 100, "LG"),
    "ammo_rockets": ("am", 0, 40, 5, None), "ammo_slugs": ("am", 1, 40, 5, None), "ammo_lightning": ("am", 2, 40, 60, None),
    "ammo_pack": ("pack", 0, 40, 0, None),
}


class DuelEnv:
    def __init__(self, bsp, n_matches=256, seed=0, substeps=(8, 8, 9), dmg_reward=0.004, nav=None, close_p=0.0,
                 loadout="full"):
        """close_p: chance a respawn lands 300-700 units from the opponent with line of sight (curriculum).
        loadout: "full" = spawn with RL/RG/LG and a little ammo (learn to aim first), "mg" = machine gun only."""
        self.M = n_matches
        self.n = 2 * n_matches                          # player i's opponent is i ^ 1
        self.w = World(bsp, n=self.n)
        self.rng = np.random.default_rng(seed)
        self.substeps = tuple(substeps)
        self.dmg_reward = dmg_reward
        self.loadout = loadout
        self.item_reward = 0.0                          # optional shaping: reward per 100 points of health/armor picked up
        self.spawns = np.array([e["origin"] for e in self.w.spawns()], np.float32)
        self.spawn_yaw = np.array([float(e.get("angle", 0)) for e in self.w.spawns()], np.float32)
        self.close_p = close_p
        self.level = 0.95                               # pitch easing per frame (1.0 = off, for tests)
        self.round_len = 15.0                           # seconds; matches restart (players near each other) after this
        self.round_t = self.rng.uniform(0, 15.0, n_matches).astype(np.float32)
        self.spots = None
        if nav and os.path.exists(nav):
            self.spots = np.array(json.load(open(nav))["nodes"], np.float32)
        ang = np.linspace(0, 2 * np.pi, N_WALL, endpoint=False)
        self.wall_dirs = np.stack([np.cos(ang), np.sin(ang)], 1).astype(np.float32)
        fang = np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False)
        self.floor_off = np.stack([np.cos(fang), np.sin(fang)], 1).astype(np.float32) * 96.0
        # items
        ents = [e for e in self.w.entities if e.get("classname") in ITEM_DEFS and "origin" in e]
        self.item_pos = np.array([e["origin"] for e in ents], np.float32).reshape(-1, 3)
        self.item_def = [ITEM_DEFS[e["classname"]] for e in ents]
        self.nI = len(ents)
        self.item_up = np.ones((n_matches, self.nI), bool)
        self.item_t = np.zeros((n_matches, self.nI), np.float32)        # seconds until it respawns
        self.slot_items = [[k for k, d in enumerate(self.item_def) if d[4] == lab] for lab in SLOTS]
        n = self.n
        self.yaw = np.zeros(n, np.float32)
        self.pitch = np.zeros(n, np.float32)
        self.mv = np.zeros((n, 2), np.float32)          # mouse velocity (yaw, pitch) in degrees per frame
        self.cmd = np.zeros((n, 2), np.float32)         # last turn command (for the jerk cost)
        self.hp = np.full(n, SPAWN_HP, np.float32)
        self.armor = np.zeros(n, np.float32)
        self.has = np.zeros((n, 3), bool)
        self.ammo = np.zeros((n, 3), np.float32)
        self.cool = np.zeros(n, np.float32)
        self.seen_t = np.full(n, 9.0, np.float32)       # seconds since this player last saw/heard the opponent
        self.known = np.zeros((n, 3), np.float32)       # last known opponent position
        self.rp = np.zeros((n, K, 3), np.float32)       # rockets, owned by player i
        self.rv = np.zeros((n, K, 3), np.float32)
        self.ra = np.zeros((n, K), bool)
        self.rnew = np.zeros((n, K), bool)              # rockets that appeared this frame (move from the next)
        self.weapon = np.zeros(n, np.int64)             # 0 RL, 1 RG, 2 LG, 3 MG
        self.fire_q = np.zeros(n, bool)                 # shots triggered last frame (they leave this frame)
        self.fire_w = np.zeros(n, np.int64)
        self.opp_hist = []                              # delayed opponent features (reaction time)
        self.stats = dict(frags=0, suicides=0, shots=0, direct=0, splash_hits=0, dmg=0.0, self_dmg=0.0,
                          rg_shots=0, rg_hits=0, lg_frames=0, lg_hits=0, mg_frames=0, mg_hits=0,
                          rl_frags=0, rg_frags=0, lg_frags=0, mg_frags=0,
                          pick_hp=0, pick_ar=0, pick_mega=0, pick_ra=0, pick_wp=0, pick_am=0, jerk=0.0)
        for i in range(n):
            self._spawn(i, avoid=None if i % 2 == 0 else self.w.state()[i - 1, :3])
        self.state = self.w.state()
        self.visible = np.zeros(n, bool)

    # ---------------------------------------------------------------- spawning / helpers
    def _fresh(self, i, yaw):
        self.yaw[i], self.pitch[i] = yaw, 0.0
        self.mv[i] = 0.0
        self.cmd[i] = 0.0
        self.hp[i], self.armor[i], self.cool[i] = SPAWN_HP, 0.0, 0.0
        has, ammo = LOADOUTS[self.loadout]
        self.has[i] = has
        self.ammo[i] = ammo
        self.weapon[i] = 0 if has[0] else 3
        self.seen_t[i] = 9.0
        self.ra[i] = False
        self.fire_q[i] = False

    def _spawn(self, i, avoid):
        if avoid is not None and self.spots is not None and self.rng.random() < self.close_p:
            d = np.linalg.norm(self.spots - avoid, axis=1)
            cand = np.nonzero((d > 300) & (d < 700))[0]
            for k in self.rng.permutation(cand)[:8]:
                p = self.spots[k]
                if self.w.trace(p + np.array([0, 0, VIEW_H], np.float32),
                                avoid + np.array([0, 0, 8.0], np.float32))["fraction"] >= 0.999:
                    face = math.degrees(math.atan2(avoid[1] - p[1], avoid[0] - p[0])) + float(self.rng.uniform(-60, 60))
                    self.w.reset(i, (p[0], p[1], p[2] + 1.0), (0, 0, 0), face)
                    self._fresh(i, face)
                    return
        k = int(self.rng.integers(len(self.spawns)))
        if avoid is not None:                            # prefer a spawn away from the opponent
            d = np.linalg.norm(self.spawns - avoid, axis=1)
            far = np.nonzero(d > np.median(d))[0]
            if len(far):
                k = int(self.rng.choice(far))
        p = self.spawns[k]
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), float(self.spawn_yaw[k]))
        self._fresh(i, float(self.spawn_yaw[k]))

    def _eye(self, s):
        e = s[:, :3].copy()
        e[:, 2] += VIEW_H
        return e

    def _los(self, a, b):
        """line of sight a -> b for many pairs (point traces)"""
        out = np.zeros(len(a), bool)
        for k in range(len(a)):
            out[k] = np.linalg.norm(b[k] - a[k]) < 1 or self.w.trace(a[k], b[k])["fraction"] >= 0.999
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

    def _damage(self, v, dmg):
        """armor absorbs 2/3 of the damage while it lasts; returns the total taken (health + armor)"""
        save = min(float(self.armor[v]), math.ceil(dmg * ARMOR_ABSORB))
        self.armor[v] -= save
        self.hp[v] -= dmg - save
        return dmg

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
        eye = self._eye(s)
        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        # opponent: exact when visible, last known (noisy) when heard / remembered
        opp = np.arange(n) ^ 1
        rel = rot(self.known - pos) / 1000.0
        exact = self.visible.astype(np.float32)
        ovel = rot(vel[opp]) / 400.0 * exact[:, None]
        to = self.known - eye
        hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        ang_yaw = np.arctan2(to[:, 1], to[:, 0]) - yaw
        ang_pit = -np.arctan2(to[:, 2], hd) - pit
        opp_feat = np.concatenate([[exact], [np.exp(-self.seen_t)], rel.T, ovel.T, [np.sin(ang_yaw)], [np.cos(ang_yaw)],
                                   [np.cos(ang_pit)], [np.sin(ang_pit)]], 0).T * (self.seen_t < 5)[:, None]
        # incoming rockets (the opponent's), nearest N_ROCK
        rk = np.zeros((n, 6 * N_ROCK), np.float32)
        orp, orv, ora = self.rp[opp], self.rv[opp], self.ra[opp]
        dist = np.where(ora, np.linalg.norm(orp - pos[:, None, :], axis=2), 1e9)
        order = np.argsort(dist, axis=1)[:, :N_ROCK]
        ar = np.arange(n)
        for j in range(N_ROCK):
            idx = order[:, j]
            ok = dist[ar, idx] < 1500
            rk[:, 6 * j:6 * j + 3] = rot(orp[ar, idx] - pos) / 1000.0 * ok[:, None]
            rk[:, 6 * j + 3:6 * j + 6] = rot(orv[ar, idx]) / 1000.0 * ok[:, None]
        # items: where the nearest one of each big kind is (map knowledge), and whether it is up, but only
        # while looking at it from within 1500 units (no timers given: remembering them is the player's job)
        items = np.zeros((n, 6 * len(SLOTS)), np.float32)
        up = np.repeat(self.item_up, 2, axis=0)                               # per player (its match)
        for j, ids in enumerate(self.slot_items):
            if not ids:
                continue
            ip = self.item_pos[ids]                                           # (k, 3)
            d = np.linalg.norm(ip[None, :, :] - pos[:, None, :], axis=2)      # (n, k)
            near = d.argmin(1)
            it = np.array(ids)[near]
            p = self.item_pos[it]
            tov = p - eye
            dd = np.linalg.norm(tov, axis=1) + 1e-6
            u = (tov / dd[:, None]).astype(np.float32)
            infov = ((u * fdir).sum(1) > FOV_COS) & (dd < 1500)
            sees = np.zeros(n, bool)
            ci = np.nonzero(infov)[0]                         # only trace toward items in view and in range
            if len(ci):
                fr = self.w.rays_each(eye[ci], u[ci][:, None, :], 1500.0)[:, 0]
                sees[ci] = fr * 1500.0 >= dd[ci] - 24
            isup = up[ar, it]
            items[:, 6 * j:6 * j + 3] = rot(p - pos) / 1000.0
            items[:, 6 * j + 3] = 1.0
            items[:, 6 * j + 4] = sees & isup
            items[:, 6 * j + 5] = sees & ~isup
        # reaction time: the opponent part of the observation is what the player saw REACT_FRAMES ago
        self.opp_hist.append(opp_feat.astype(np.float32))
        if len(self.opp_hist) > REACT_FRAMES + 1:
            self.opp_hist.pop(0)
        opp_feat = self.opp_hist[0]
        own = np.stack([self.hp / 200.0, self.armor / 200.0, np.minimum(self.cool, 1.5) / 1.5, self.pitch / 90.0,
                        (self.hp <= 0).astype(np.float32)], 1)
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], own, self.mv / 30.0, walls, floors, opp_feat, rk,
                              np.eye(4, dtype=np.float32)[self.weapon], self.has.astype(np.float32),
                              self.ammo / AMMO_MAX, items], 1)
        return obs.astype(np.float32)

    # ---------------------------------------------------------------- step
    def step(self, actions):
        a = np.asarray(actions)
        n = self.n
        fwd = (a[:, 0].astype(np.int32) - 1) * 127
        side = (a[:, 1].astype(np.int32) - 1) * 127
        jump = a[:, 2].astype(np.int32) * 127
        fire = a[:, 5] == 1
        # mouse: the chosen turn speed is followed with a little inertia; jerky commands cost a little
        cmd = np.stack([TURN[a[:, 3]], PITCH[a[:, 4]]], 1)
        jerk = np.abs(cmd - self.cmd).sum(1)
        self.cmd = cmd
        self.mv = MOUSE_SMOOTH * self.mv + (1.0 - MOUSE_SMOOTH) * cmd
        turn, dpit = self.mv[:, 0], self.mv[:, 1]
        # weapon switch (only to weapons owned)
        want = np.where(a[:, 6] == 0, self.weapon, a[:, 6].astype(np.int64) - 1)
        owned = np.concatenate([self.has, np.ones((n, 1), bool)], 1)[np.arange(n), want]
        want = np.where(owned, want, self.weapon)
        sw = want != self.weapon
        self.weapon = want
        self.cool = np.where(sw, np.maximum(self.cool, SWITCH), self.cool)
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw.copy()
        p1 = np.clip(self.pitch * self.level + dpit, -89, 89)   # the view eases back toward level
        done_ms = 0
        for ms in self.substeps:
            done_ms += ms
            f = done_ms / 25.0
            self.w.step(moves, np.stack([self.pitch + (p1 - self.pitch) * f, y0 + turn * f], 1).astype(np.float32), ms)
        self.pitch = p1
        self.state = s = self.w.state()
        self.yaw = s[:, 7].copy()
        reward = -JERK_COST * jerk.astype(np.float32)
        self.stats["jerk"] += float(jerk.sum())
        dmg_taken = np.zeros(n, np.float32)
        attacker = np.full(n, -1)

        # fire. Measured on a real server: a shot leaves one frame after the command, and a rocket does not
        # move on the frame it appears.
        self.cool = np.maximum(0.0, self.cool - DT)
        do_fire, do_w = self.fire_q, self.fire_w
        ammo_ok = np.concatenate([self.ammo > 0, np.ones((n, 1), bool)], 1)[np.arange(n), self.weapon]
        shoot = fire & (self.cool <= 0) & ammo_ok
        self.cool = np.where(shoot, np.array([REFIRE, RG_REFIRE, LG_TICK, MG_TICK])[self.weapon], self.cool)
        for wi in range(3):
            self.ammo[:, wi] -= shoot & (self.weapon == wi)
        self.fire_q, self.fire_w = shoot, self.weapon.copy()
        kill_w = {}
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
                rng_ = LG_RANGE if wpn == 2 else 8192.0      # railgun / lightning gun / machine gun: instant trace
                fr = self.w.rays_each(eye[i:i + 1], fdir[i:i + 1, None, :], rng_)[0, 0]
                end = eye[i] + fdir[i] * rng_ * fr
                v = i ^ 1
                hit = bool(self._seg_box(eye[i:i + 1], end[None], s[v:v + 1, :3])[0])
                name = WEAPONS[wpn]
                dmg, kf = {1: (RG_DMG, RG_KNOCK), 2: (LG_DMG, LG_KNOCK), 3: (MG_DMG, MG_KNOCK)}[wpn]
                self.stats["rg_shots" if wpn == 1 else name + "_frames"] += 1
                if hit:
                    self.w.knockback(int(v), fdir[i] * (1000.0 * kf * dmg / 200.0), int(dmg))
                    kicked = True
                    dmg_taken[v] += self._damage(v, dmg)
                    attacker[v] = i
                    self.stats["dmg"] += dmg
                    self.stats[name + "_hits"] += 1
                    kill_w[v] = wpn

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
                    dmg_taken[v] += self._damage(v, take)
                    if v != i:
                        attacker[v] = i
                        kill_w[v] = 0
                        self.stats["dmg"] += take
                        if not is_direct:
                            self.stats["splash_hits"] += 1
                    else:
                        self.stats["self_dmg"] += take
                        if attacker[v] < 0:
                            attacker[v] = v
        if kicked:
            self.state = s = self.w.state()                  # knockback changed velocities

        # shaping (curriculum): reward damage dealt to the opponent. Penalizing damage taken made early self-play
        # collapse into hiding (being seen = getting shot by a random rail).
        opp_all = np.arange(n) ^ 1
        dealt = np.where(attacker[opp_all] == np.arange(n), dmg_taken[opp_all], 0.0)
        reward += self.dmg_reward * dealt

        # items: pickups, respawns, decay above 100
        self.item_t = np.maximum(0.0, self.item_t - DT)
        self.item_up |= self.item_t <= 0
        if self.nI:
            dxy = np.linalg.norm(s[:, None, :2] - self.item_pos[None, :, :2], axis=2)
            dz = np.abs(s[:, None, 2] - self.item_pos[None, :, 2])
            touch = (dxy < 36) & (dz < 56) & np.repeat(self.item_up, 2, axis=0) & (self.hp > 0)[:, None]
            for i, it in zip(*np.nonzero(touch)):
                m = i // 2
                if not self.item_up[m, it]:
                    continue                                  # the other player took it this frame
                kind, val, resp, cap, lab = self.item_def[it]
                took = False
                gain = 0.0
                if kind == "hp" and self.hp[i] < cap:
                    gain = min(cap, self.hp[i] + val) - self.hp[i]
                    self.hp[i] += gain
                    took = True
                    self.stats["pick_mega" if lab == "MH" else "pick_hp"] += 1
                elif kind == "ar" and self.armor[i] < cap:
                    gain = min(cap, self.armor[i] + val) - self.armor[i]
                    self.armor[i] += gain
                    took = True
                    self.stats["pick_ra" if lab == "RA" else "pick_ar"] += 1
                elif kind == "wp":
                    self.has[i, val] = True
                    self.ammo[i, val] = min(AMMO_MAX[val], self.ammo[i, val] + cap)
                    took = True
                    self.stats["pick_wp"] += 1
                elif kind == "am" and self.ammo[i, val] < AMMO_MAX[val]:
                    self.ammo[i, val] = min(AMMO_MAX[val], self.ammo[i, val] + cap)
                    took = True
                    self.stats["pick_am"] += 1
                elif kind == "pack" and (self.ammo[i] < AMMO_MAX).any():
                    self.ammo[i] = np.minimum(AMMO_MAX, self.ammo[i] + np.array([5, 5, 50], np.float32) * self.has[i])
                    took = True
                    self.stats["pick_am"] += 1
                if took:
                    reward[i] += self.item_reward * (gain if kind in ("hp", "ar") else 10.0) / 100.0
                    self.item_up[m, it] = False
                    self.item_t[m, it] = resp
        self.hp = np.where(self.hp > 100, np.maximum(100.0, self.hp - DT), self.hp)
        self.armor = np.where(self.armor > 100, np.maximum(100.0, self.armor - DT), self.armor)

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
                self.stats[WEAPONS[kill_w.get(v, 0)] + "_frags"] += 1
            else:
                self.stats["suicides"] += 1
            events.append(dict(victim=int(v), killer=int(k)))
        for v in dead:
            self._spawn(int(v), avoid=s[v ^ 1, :3])
        lo, hi = self.w.bounds()
        out = np.nonzero(s[:, 2] < lo[2] - 64)[0]            # fell out of the map: a suicide
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
            self.item_up[m] = True
            self.item_t[m] = 0.0
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

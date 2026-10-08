"""Write sim/duel_env_ffa.py from sim/duel_env.py: the same simulator with groups of G players (2 to 6) who all
fight each other, instead of pairs. With G = 2 it plays exactly as duel_env does (tools/ffa_check.py compares
them frame by frame). Kept as a generated copy so the simulator of a run in progress is never touched.

    python tools/make_ffa_env.py

What changes for G > 2:
  - every player sees, hears and can hit every other player of his group; rockets splash on all of them
  - the "enemy" inputs describe the enemy he is attending to: the one in view nearest his crosshair, else the
    one seen or heard most recently
  - 18 more inputs at the end: up to two more enemies in view (where they are, whether they face him), how many
    are in view, how many players there are
  - arena rounds only (no aim rooms or courses with more than two players)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, "sim", "duel_env.py"), newline="", encoding="utf-8").read()
assert "\r\n" not in s


def rep(a, b, count=1):
    global s
    assert s.count(a) >= count, (s.count(a), a[:90])
    if count == 0:
        s = s.replace(a, b)
    else:
        assert s.count(a) == count, (s.count(a), a[:90])
        s = s.replace(a, b)


# ---- constants
rep("OBS_DIM = OBS_BASE + N_EXTRA + N_FIGHT + N_MEM + N_ROUTE + N_PAD + N_EAR + N_MORE + N_DENSE + N_V9 + N_INTENT",
    "N_FFA = 2 * 11 + 2                                     # two more enemies in view (11 each), enemies in view, players\n"
    "OBS_DIM = OBS_BASE + N_EXTRA + N_FIGHT + N_MEM + N_ROUTE + N_FFA + N_PAD + N_EAR + N_MORE + N_DENSE + N_V9 + N_INTENT")
rep("        return (np.arange(self.n) ^ 1)[:, None]", "        return self.others")
rep("        return [i ^ 1]", "        return [int(x) for x in self.others[i]]")
rep("        return j % 2", "        return j % self.G")

# ---- constructor
rep('''                 loadout="full", drill_weapons=(RL, RG, LG), teacher=None):''',
    '''                 loadout="full", drill_weapons=(RL, RG, LG), teacher=None, group=2):''')
rep('''        self.n = 2 * n_matches                          # player i's opponent is i ^ 1
''', '''        self.G = G = int(group)                         # players per group: all of a group fight each other
        self.n = group * n_matches
        ar_ = np.arange(self.n)
        self.slot = ar_ % G
        self.grp = (ar_ // G * G)[:, None] + np.arange(G)[None, :]                      # every member of the player's group
        self.others = (ar_ // G * G)[:, None] + (self.slot[:, None] + np.arange(1, G)[None, :]) % G     # the other members
        self.foe = self.others[:, 0].copy()             # the enemy a player is attending to (G = 2: the opponent)
        self.fidx = np.zeros(self.n, np.int64)          # ... as an index into others
        self.vis2 = np.zeros((self.n, G - 1), bool)     # per other player: in view / frames in view / noticed /
        self.vis_run2 = np.zeros((self.n, G - 1), np.int64)     # last known position / seconds since seen or heard
        self.acq2 = np.zeros((self.n, G - 1), bool)
        self.acq_extra2 = np.zeros((self.n, G - 1), np.int64)   # frames more before he is noticed, by surprise
        self.known2 = np.zeros((self.n, G - 1, 3), np.float32)
        self.seen2 = np.full((self.n, G - 1), 9.0, np.float32)
        self.dmg_on = np.zeros((self.n, G), np.float32)  # damage dealt to each member during his current life
        self.shot_src = np.full(self.n, -1, np.int64)   # whose shot / pain sound a player last noted
        self.pain_src = np.full(self.n, -1, np.int64)
        self.ffa_hist = []
''')
rep("2 * n_matches", "group * n_matches", 0)
rep('''            self._spawn(i, avoid=None if i % 2 == 0 else self.w.state()[i - 1, :3])''',
    '''            self._spawn(i, avoid=None if i % G == 0 else self.w.state()[i - 1, :3])''')

# ---- _fresh
rep('''        self.shot_t[i ^ 1] = self.trail_t[i ^ 1] = 99.0     # what the opponent knew about this player's shots is void
        self.pain_t[i ^ 1] = 99.0
''', '''        o_ = self.others[i]
        o1 = o_[(self.shot_src[o_] == i) | (self.G == 2)]
        self.shot_t[o1] = self.trail_t[o1] = 99.0           # what the others knew about this player's shots is void
        o1 = o_[(self.pain_src[o_] == i) | (self.G == 2)]
        self.pain_t[o1] = 99.0
        self.dmg_on[self.grp[i], self.slot[i]] = 0.0
''')
rep('''        self.dmg_life[i ^ 1] = 0.0                      # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // 2])
        kind = int(self.kind[i // 2])''', '''        if self.G == 2:
            self.dmg_life[i ^ 1] = 0.0                  # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // self.G])
        kind = int(self.kind[i // self.G])''')
rep('''        self.seen_t[i] = 9.0
        self.vis_run[i] = 0
        self.acquired[i] = False
''', '''        self.seen_t[i] = 9.0
        self.vis_run[i] = 0
        self.acquired[i] = False
        self.seen2[i], self.vis_run2[i], self.acq2[i] = 9.0, 0, False
''')

# ---- courses, run-and-gun
rep("            self._gun_place(i // 2)", "            self._gun_place(i // self.G)")
rep("        w_ = int(self.gun_w[i // 2])", "        w_ = int(self.gun_w[i // self.G])")
rep("                m_ = int(i) // 2", "                m_ = int(i) // self.G")
rep('''        """put the target of a run-and-gun round beside the path, 500 to 900 units ahead of the runner"""
        a_, b_ = 2 * m, 2 * m + 1''', '''        """put the target of a run-and-gun round beside the path, 500 to 900 units ahead of the runner"""
        a_, b_ = self.G * m, self.G * m + 1''')

# ---- lab rounds
rep('''        a_, b_ = 2 * m, 2 * m + 1
        for q in (a_, b_):
            self._course_close(q, False)
        f, L, rng = self.lab_force, self.lab, self.rng''', '''        a_, b_ = self.G * m, self.G * m + 1
        P = list(range(self.G * m, self.G * m + self.G))
        for q in P:
            self._course_close(q, False)
        f, L, rng = self.lab_force, self.lab, self.rng''')
rep('''        kd = f["kind"] if f else (NORMAL if u < pr else AIM if (u < pr + pa or not self.courses) else COURSE)
''', '''        kd = f["kind"] if f else (NORMAL if u < pr else AIM if (u < pr + pa or not self.courses) else COURSE)
        if self.G > 2 or "aim" not in L:                    # more than two players, or a map with only an arena: arena rounds
            kd = NORMAL
''')
rep('''        self.snd_t[a_] = self.snd_t[b_] = 99.0
        if kd == NORMAL:                                    # arena: the two fight each other, same weapons for both
            self.arena[m] = int(f["arena"]) if (f and "arena" in f) else int(rng.choice(self.arena_rooms))
''', '''        self.snd_t[a_] = self.snd_t[b_] = 99.0
        for q in P[2:]:
            self.script[q], self.goal[q], self.course[q], self.items_room[q], self.gun[q] = 0, -1, -1, False, False
            self.load_sets[q], self.frags_r[q], self.snd_t[q] = None, 0, 99.0
        if kd == NORMAL:                                    # arena: the players fight each other
            self.arena[m] = int(f["arena"]) if (f and "arena" in f) else int(rng.choice(self.arena_rooms))
            if "env" not in L:
                self.arena[m] = 3                           # a map with only the yard
            self.item_up[m, :], self.item_t[m, :] = True, 0.0
''')
rep('''            self.load_sets[a_] = self.load_sets[b_] = guns
            if self.arena_sets and not (f and "weapon" in f):   # fixed sets, drawn separately for each player
                for q in (a_, b_):
''', '''            for q in P:
                self.load_sets[q] = guns
            if self.arena_sets and not (f and "weapon" in f):   # fixed sets, drawn separately for each player
                for q in P:
''')
rep('''            self.state = self.w.state()
            self._arena_spawn(b_)
        elif kd == AIM:''', '''            for q in P[1:]:
                self.state = self.w.state()
                self._arena_spawn(q)
        elif kd == AIM:''')
rep('''            self.vis_run[a_], self.acquired[a_], self.seen_t[a_] = self.acquire_frames, True, 0.0
            self.known[a_] = home''', '''            self.vis_run[a_], self.acquired[a_], self.seen_t[a_] = self.acquire_frames, True, 0.0
            self.known[a_] = home
            self.vis_run2[a_, 0], self.acq2[a_, 0], self.seen2[a_, 0], self.known2[a_, 0] = self.acquire_frames, True, 0.0, home''')

# ---- arena spawn
rep('''        m, L, rng = i // 2, self.lab, self.rng
        opp = self.state[i ^ 1, :3]''', '''        m, L, rng = i // self.G, self.lab, self.rng
        oth = self.state[self.others[i], :3]''')
rep('''            E_ = L["env"]
            cand = [np.array([q[0], q[1], q[2] if len(q) > 2 else E_["z"]], np.float32) for q in E_["spots"]]
        if first:
            p = cand[int(rng.integers(len(cand)))]
        else:
            d = np.array([float(np.linalg.norm(q - opp)) for q in cand])
            ok = np.nonzero(d > 500)[0]
            p = cand[int(rng.choice(ok))] if len(ok) else cand[int(d.argmax())]
        face = math.degrees(math.atan2(opp[1] - p[1], opp[0] - p[0])) if not first else float(rng.uniform(-180, 180))''',
    '''            E_ = L["yard"] if self.arena[m] == 3 else L["env"]
            cand = [np.array([q[0], q[1], q[2] if len(q) > 2 else E_["z"]], np.float32) for q in E_["spots"]]
        if first:
            p = cand[int(rng.integers(len(cand)))]
        else:                                               # well away from everybody else
            d = np.array([min(float(np.linalg.norm(q - o_)) for o_ in oth) for q in cand])
            ok = np.nonzero(d > 500)[0]
            p = cand[int(rng.choice(ok))] if len(ok) else cand[int(d.argmax())]
        opp = oth[int(np.linalg.norm(oth - p, axis=1).argmin())]
        face = math.degrees(math.atan2(opp[1] - p[1], opp[0] - p[0])) if not first else float(rng.uniform(-180, 180))''')
rep('''        """a death on the lab map: back to the room's own spot, not to a map spawn point"""
        m = v // 2''', '''        """a death on the lab map: back to the room's own spot, not to a map spawn point"""
        m = v // self.G''')

# ---- shots noted, sounds
rep('''        s = self.state
        lis = src ^ 1
        k_ = np.repeat(self.kind, 2)[lis]
        alone = ((k_ == MOVE) | (k_ == SOLO) | ((k_ == COURSE) & ~self.gun[lis]))
        d = np.linalg.norm(s[src, :3] - s[lis, :3], axis=1)
        seen = self.acquired[lis] & ~alone
        ok = (seen | (d < HEAR_EVT)) & ~alone & (self.hp[lis] > 0)
        self.shot_t[lis[ok]] = 0.0''', '''        s = self.state
        lis = self.others[src].reshape(-1)                  # every other member of the shooter's group
        src = np.repeat(src, self.G - 1)
        k_ = np.repeat(self.kind, self.G)[lis]
        alone = ((k_ == MOVE) | (k_ == SOLO) | ((k_ == COURSE) & ~self.gun[lis]))
        d = np.linalg.norm(s[src, :3] - s[lis, :3], axis=1)
        acq_p = self.acquired[lis] if self.G == 2 else self.acq2[lis, (self.slot[src] - self.slot[lis]) % self.G - 1]
        seen = acq_p & ~alone
        ok = (seen | (d < HEAR_EVT)) & ~alone & (self.hp[lis] > 0)
        self.shot_src[lis[ok]] = src[ok]
        self.shot_t[lis[ok]] = 0.0''')
rep('''            sh, li = src[hit], lis[hit]
            eye = self._eye(s)''', '''            sh, li, acq_h = src[hit], lis[hit], acq_p[hit]
            eye = self._eye(s)''')
rep('''            vis = (self.acquired[li] | ((to * fl).sum(1) / dn > self.fov()[2][li])) & (dn < 2000.0)
            for k in np.nonzero(vis)[0]:
                if self.acquired[li[k]] or self.w.trace''', '''            vis = (acq_h | ((to * fl).sum(1) / dn > self.fov()[2][li])) & (dn < 2000.0)
            for k in np.nonzero(vis)[0]:
                if acq_h[k] or self.w.trace''')
rep('''        n = self.n
        opp = np.arange(n) ^ 1
        t = self.shot_t''', '''        n = self.n
        opp = self.foe
        t = self.shot_t''')
rep('''        s = self.state
        lis = src ^ 1
        k_ = np.repeat(self.kind, 2)[src]
        ok = (np.linalg.norm''', '''        s = self.state
        lis = self.others[src].reshape(-1)
        src = np.repeat(src, self.G - 1)
        if kind is not None and np.ndim(kind):
            kind = np.repeat(np.asarray(kind), self.G - 1)
        k_ = np.repeat(self.kind, self.G)[src]
        ok = (np.linalg.norm''')

# ---- observation
rep('''        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        opp = np.arange(n) ^ 1
        # Reaction time''', '''        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        opp = self.foe
        # Reaction time''')
rep('''        orp, orv, ora, orw = self.rp[opp], self.rv[opp], self.ra[opp], self.rw[opp]''',
    '''        oth = self.others                                    # everybody else's projectiles
        orp, orv = self.rp[oth].reshape(n, -1, 3), self.rv[oth].reshape(n, -1, 3)
        ora, orw = self.ra[oth].reshape(n, -1), self.rw[oth].reshape(n, -1)''')
rep('''        up = np.repeat(self.item_up, 2, axis=0)                               # per player (its match)''',
    '''        up = np.repeat(self.item_up, self.G, axis=0)                          # per player (its match)''')
rep('''                              self._fight(pos, eye, rot, visible), self._mem(opp), self._routes(pos, rot), self._pad_ear(yaw),
                              self._more(pos, rot, c, si, visible, opp_vel, seen_t), self._dense(eye, yaw, pit),
                              self._v9(pos, rot), self._intent(pos, rot, known, seen_t)], 1)
        return obs.astype(np.float32)''', '''                              self._fight(pos, eye, rot, visible), self._mem(opp), self._routes(pos, rot),
                              self._ffa(pos, eye, rot, yaw, pit), self._pad_ear(yaw),   # the group block keeps its place
                              self._more(pos, rot, c, si, visible, opp_vel, seen_t), self._dense(eye, yaw, pit),
                              self._v9(pos, rot), self._intent(pos, rot, known, seen_t)], 1)
        return obs.astype(np.float32)

    def _ffa(self, pos, eye, rot, yaw, pit):
        """more than two players (see N_FFA): up to two more enemies in view besides the one attended to, nearest
        the crosshair first: there, where (3), direction (yaw sin, cos; pitch sin), whether he faces this player.
        Then: enemies in view / 5, players beyond two / 4. Positions are as old as the reaction time."""
        n, G = self.n, self.G
        out = np.zeros((n, N_FFA), np.float32)
        if G == 2:
            return out
        self.ffa_hist.append((self.state[:, :3].copy(), self.acq2.copy(), self.yaw.copy()))
        while len(self.ffa_hist) > self.react_frames + 1:
            self.ffa_hist.pop(0)
        p_old, acq, yaw_old = self.ffa_hist[0]
        ar = np.arange(n)
        rest = acq.copy()
        rest[ar, self.fidx] = False                          # the attended enemy has his own inputs
        to = p_old[self.others] + np.array([0, 0, 4.0], np.float32) - eye[:, None, :]
        dist = np.linalg.norm(to, axis=2) + 1e-6
        fdir = np.stack([np.cos(pit) * np.cos(yaw), np.cos(pit) * np.sin(yaw), -np.sin(pit)], 1)
        off = np.where(rest, 1.0 - (to * fdir[:, None, :]).sum(2) / dist, 9.0)
        order = np.argsort(off, axis=1)
        for j in range(min(2, G - 2)):
            k = order[:, j]
            on = rest[ar, k]
            t_ = to[ar, k]
            o = self.others[ar, k]
            ay = np.arctan2(t_[:, 1], t_[:, 0]) - yaw
            ap = -np.arctan2(t_[:, 2], np.hypot(t_[:, 0], t_[:, 1]) + 1e-6) - pit
            back = np.arctan2(pos[:, 1] - p_old[o, 1], pos[:, 0] - p_old[o, 0]) - np.radians(yaw_old[o])
            blk = np.concatenate([np.ones((n, 1), np.float32), rot(p_old[o] - pos) / 1000.0,
                                  np.stack([np.sin(ay), np.cos(ay), np.sin(ap), np.cos(back)], 1),
                                  np.eye(NW, dtype=np.float32)[self.weapon[o]][:, [RL, RG, LG]]], 1)   # what he holds (v9)
            out[:, 11 * j:11 * j + 11] = blk * on[:, None]
        out[:, 16] = acq.sum(1) / 5.0
        out[:, 17] = (G - 2) / 4.0
        return out''')
rep('''        ar = np.arange(n)
        opp = ar ^ 1
        # clock (item timers are 25 s and 35 s) and score of the round
        t = np.repeat(self.round_t, 2)''', '''        ar = np.arange(n)
        opp = self.foe
        # clock (item timers are 25 s and 35 s) and score of the round (against the best of the others)
        t = np.repeat(self.round_t, self.G)
        best = self.frags_r[self.others].max(1)''')
rep('''                          np.minimum(self.frags_r[opp] / 10.0, 2.0),
                          np.clip((self.frags_r - self.frags_r[opp]) / 5.0, -2, 2)], 1)''',
    '''                          np.minimum(best / 10.0, 2.0),
                          np.clip((self.frags_r - best) / 5.0, -2, 2)], 1)''')
rep('''                                np.minimum(self.dmg_life / 200.0, 2.0)[:, None]], 1)''',
    '''                                np.minimum((self.dmg_life if self.G == 2 else self.dmg_on[ar, self.slot[opp]])
                                           / 200.0, 2.0)[:, None]], 1)''')

# ---- explosions
rep('''        for v in (i, i ^ 1):                              # splash on both players (owner too)''',
    '''        for v in [i] + [int(x) for x in self.others[i]]:  # splash on everybody in the group (owner too)''')

# ---- scripted players
rep("            ph = (self.round_t[idx // 2] / DT).astype(np.int64)", "            ph = (self.round_t[idx // self.G] / DT).astype(np.int64)")
rep('''        fighter = self.script[idx] == 2
        opp = idx ^ 1''', '''        fighter = self.script[idx] == 2
        opp = self.foe[idx]''')
rep("            z = self.lab_zone[idx // 2]", "            z = self.lab_zone[idx // self.G]")
rep("self.lab_jump[idx // 2] & ~near", "self.lab_jump[idx // self.G] & ~near")

# ---- step
rep('''        pkind = np.repeat(self.kind, 2)
        walk = (a[:, 7] == 1)''', '''        pkind = np.repeat(self.kind, self.G)
        walk = (a[:, 7] == 1)''')
rep('''                name = WEAPONS[wpn]
                v = i ^ 1
''', '''                name = WEAPONS[wpn]
                vs_ = [int(x) for x in self.others[i]]
''')
rep('''                    self.stats[name + "_shots_vis"] += hm * SG_PELLETS * int(self.visible[i])
                    to = s[v, :3] + np.array([0, 0, 4.0], np.float32) - eye[i]
                    d = float(np.linalg.norm(to)) + 1e-6
                    if self.w.trace(eye[i], s[v, :3] + np.array([0, 0, 4.0], np.float32))["fraction"] < 0.999:
                        continue
                    hd = math.hypot(to[0], to[1]) + 1e-6
                    ex = math.degrees(((math.atan2(to[1], to[0]) - yr[i]) + math.pi) % (2 * math.pi) - math.pi)
                    eyv = math.degrees(-math.atan2(to[2], hd) - pr[i])
                    wx, wy = math.degrees(math.atan2(15.0, d)), math.degrees(math.atan2(28.0, d))
                    p = (_phi((wx - ex) / SG_SIGMA) - _phi((-wx - ex) / SG_SIGMA)) * \\
                        (_phi((wy - eyv) / SG_SIGMA) - _phi((-wy - eyv) / SG_SIGMA))
                    hits = int(self.rng.binomial(SG_PELLETS, min(1.0, max(0.0, p))))
                    if hits:
                        self.stats[name + "_hits"] += hm * hits
                        self._hit(i, v, wpn, W_DMG[wpn] * hits, fdir[i], st)
                    continue''', '''                    self.stats[name + "_shots_vis"] += hm * SG_PELLETS * int(self.visible[i])
                    for v in vs_:
                        to = s[v, :3] + np.array([0, 0, 4.0], np.float32) - eye[i]
                        d = float(np.linalg.norm(to)) + 1e-6
                        if self.w.trace(eye[i], s[v, :3] + np.array([0, 0, 4.0], np.float32))["fraction"] < 0.999:
                            continue
                        hd = math.hypot(to[0], to[1]) + 1e-6
                        ex = math.degrees(((math.atan2(to[1], to[0]) - yr[i]) + math.pi) % (2 * math.pi) - math.pi)
                        eyv = math.degrees(-math.atan2(to[2], hd) - pr[i])
                        wx, wy = math.degrees(math.atan2(15.0, d)), math.degrees(math.atan2(28.0, d))
                        p = (_phi((wx - ex) / SG_SIGMA) - _phi((-wx - ex) / SG_SIGMA)) * \\
                            (_phi((wy - eyv) / SG_SIGMA) - _phi((-wy - eyv) / SG_SIGMA))
                        hits = int(self.rng.binomial(SG_PELLETS, min(1.0, max(0.0, p))))
                        if hits:
                            self.stats[name + "_hits"] += hm * hits
                            self._hit(i, v, wpn, W_DMG[wpn] * hits, fdir[i], st)
                    continue''')
rep('''                if bool(self._seg_box(eye[i:i + 1], end[None], s[v:v + 1, :3],
                                      np.where(self.duck[v:v + 1], TOP_DUCK, TOP))[0]):
                    self.stats[name + "_hits"] += hm
                    self._hit(i, v, wpn, W_DMG[wpn], fdir[i], st)''', '''                got = [v for v in vs_ if bool(self._seg_box(eye[i:i + 1], end[None], s[v:v + 1, :3],
                                                            np.where(self.duck[v:v + 1], TOP_DUCK, TOP))[0])]
                if got:                                     # the nearest player on the line takes the shot
                    v = min(got, key=lambda q: float(np.linalg.norm(s[q, :3] - eye[i])))
                    self.stats[name + "_hits"] += hm
                    self._hit(i, v, wpn, W_DMG[wpn], fdir[i], st)''')
rep('''            opp = owner ^ 1
            direct = self._seg_box(p0, hitpt, s[opp, :3], np.where(self.duck[opp], TOP_DUCK, TOP))''',
    '''            direct = np.zeros(len(owner), bool)
            d_on = np.full(len(owner), -1, np.int64)
            for k_ in range(self.G - 1):
                opp = self.others[owner, k_]
                dk = self._seg_box(p0, hitpt, s[opp, :3], np.where(self.duck[opp], TOP_DUCK, TOP)) & ~direct
                d_on[dk] = opp[dk]
                direct |= dk''')
rep("                    self._explode(i, wq, hitpt[q], i ^ 1, dirs[q], s, st)",
    "                    self._explode(i, wq, hitpt[q], int(d_on[q]), dirs[q], s, st)")
rep('''        opp_all = ar ^ 1
        hurt = np.nonzero((dmg_taken > 0) & (self.hp > 0))[0]              # pain sounds: the opponent hears them within earshot
        if len(hurt):
            lis_ = hurt ^ 1
            near_ = np.linalg.norm(s[hurt, :3] - s[lis_, :3], axis=1) < HEAR_EVT
            self.pain_t[lis_[near_]] = 0.0
            self.pain_b[lis_[near_]] = np.minimum(3, (self.hp[hurt[near_]] // 25).astype(np.int64))
        dealt = np.where(attacker[opp_all] == ar, dmg_taken[opp_all], 0.0)''',
    '''        hurt = np.nonzero((dmg_taken > 0) & (self.hp > 0))[0]              # pain sounds: the others hear them within earshot
        if len(hurt):
            lis_ = self.others[hurt].reshape(-1)
            hurt = np.repeat(hurt, self.G - 1)
            near_ = np.linalg.norm(s[hurt, :3] - s[lis_, :3], axis=1) < HEAR_EVT
            self.pain_t[lis_[near_]] = 0.0
            self.pain_src[lis_[near_]] = hurt[near_]
            self.pain_b[lis_[near_]] = np.minimum(3, (self.hp[hurt[near_]] // 25).astype(np.int64))
        dealt_to = np.where(attacker[self.grp] == ar[:, None], dmg_taken[self.grp], 0.0)    # per member of the group
        dealt_to[ar, self.slot] = 0.0
        dealt = dealt_to.sum(1)
        self.dmg_on += dealt_to
        opp_all = np.where((attacker >= 0) & (attacker != ar), attacker, self.foe)     # a hit is felt from the attacker's side''')
rep('''            touch = (dxy < 36) & (dz < 56) & np.repeat(self.item_up, 2, axis=0) & (self.hp > 0)[:, None]
            for i, it in zip(*np.nonzero(touch)):
                m = i // 2''', '''            touch = (dxy < 36) & (dz < 56) & np.repeat(self.item_up, self.G, axis=0) & (self.hp > 0)[:, None]
            for i, it in zip(*np.nonzero(touch)):
                m = i // self.G''')
rep('''            self._spawn(int(v), avoid=s[v ^ 1, :3], close=True if self.kind[v // 2] == AIM else None)''',
    '''            self._spawn(int(v), avoid=s[self.foe[v], :3], close=True if self.kind[v // self.G] == AIM else None)''')
rep('''                self._spawn(int(v), avoid=s[v ^ 1, :3])''', '''                self._spawn(int(v), avoid=s[self.foe[v], :3])''')
rep("            am = np.repeat(self.arena > 0, 2)", "            am = np.repeat(self.arena > 0, self.G)")
rep('''            self.round_t[m] = 0.0
            a_, b_ = 2 * m, 2 * m + 1
            if self.lab is not None:
                self._lab_round(int(m))
                done[a_] = done[b_] = True
                continue''', '''            self.round_t[m] = 0.0
            a_, b_ = self.G * m, self.G * m + 1
            P = list(range(self.G * m, self.G * m + self.G))
            done[P] = True
            if self.lab is not None:
                self._lab_round(int(m))
                continue''')
rep('''            if kd == MOVE and self.field is None:
                kd = NORMAL''', '''            if (kd == MOVE and self.field is None) or self.G > 2:      # more than two players: plain fights only
                kd = NORMAL''')
rep('''            elif kd == NORMAL and self.rng.random() < self.bot_p:
                self.script[b_] = 2''', '''            elif kd == NORMAL and self.G == 2 and self.rng.random() < self.bot_p:
                self.script[b_] = 2''')
rep('''                    for q in (a_, b_):
                        self.load_sets[q] = tuple(int(x) for x in self.rng.choice(guns''', '''                    for q in P:
                        self.load_sets[q] = tuple(int(x) for x in self.rng.choice(guns''')
rep('''                elif u < self.loadout_p[0] + self.loadout_p[1]:
                    self.load_sets[a_] = self.load_sets[b_] = ()''', '''                elif u < self.loadout_p[0] + self.loadout_p[1]:
                    for q in P:
                        self.load_sets[q] = ()''')
rep('''                self._spawn(a_, avoid=None)
                self._spawn(b_, avoid=self.w.state()[a_, :3], close=0.0 if kd == MOVE else None)''',
    '''                self._spawn(a_, avoid=None)
                self._spawn(b_, avoid=self.w.state()[a_, :3], close=0.0 if kd == MOVE else None)
                for q in P[2:]:
                    self.script[q], self.goal[q], self.frags_r[q], self.snd_t[q] = 0, -1, 0, 99.0
                    self._spawn(q, avoid=self.w.state()[q - 1, :3])''')
rep('''            done[a_] = done[b_] = True
            self.load_sets[a_] = self.load_sets[b_] = None''', '''            for q in P:
                self.load_sets[q] = None''')

# ---- senses: one pass per other member of the group, then the enemy attended to
a = s.index("        # senses: sight (line of sight + field of view) and hearing (rough position)")
b = s.index("        self._teach_update()\n        info = dict(events=events)")
s = s[:a] + '''        # senses: sight (line of sight + field of view) and hearing (rough position), for every other member
        eye = self._eye(s)
        yr, pr = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        pkind = np.repeat(self.kind, self.G)
        off = np.zeros((n, self.G - 1), np.float32)
        for k_ in range(self.G - 1):
            opp = self.others[:, k_]
            to = s[opp, :3] - eye
            dist = np.linalg.norm(to, axis=1) + 1e-6
            cosang = (to * fdir).sum(1) / dist
            off[:, k_] = 1.0 - cosang
            infov = cosang > self.fov()[2]
            cand = np.nonzero(infov & (dist < 4000))[0]
            vis = np.zeros(n, bool)
            if len(cand):
                vis[cand] = self._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
            vis &= (pkind != MOVE) & (pkind != SOLO) & ((pkind != COURSE) | self.gun)   # movement / solo / course: no other player
            heard = (~vis) & (dist < HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250) & (pkind != MOVE) & (pkind != SOLO) & (pkind != COURSE)
            self.vis2[:, k_] = vis
            if SURPRISE_MS > 0:                              # off the crosshair and unexpected: noticed later
                ecc_ = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
                self.acq_extra2[:, k_] = np.where(vis & (self.vis_run2[:, k_] == 0), surprise_frames(ecc_, self.seen2[:, k_]),
                                                  np.where(vis, self.acq_extra2[:, k_], 0))
            self.vis_run2[:, k_] = np.where(vis, self.vis_run2[:, k_] + 1, 0)
            acq = vis & (self.vis_run2[:, k_] >= max(1, self.acquire_frames - self.react_frames) + self.acq_extra2[:, k_])
            self.acq2[:, k_] = acq
            self.known2[acq, k_] = s[opp[acq], :3]
            if heard.any():
                self.known2[heard, k_] = s[opp[heard], :3] + self.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \\
                    np.array([1, 1, 0], np.float32)
            self.seen2[:, k_] = np.where(acq | heard, 0.0, self.seen2[:, k_] + DT)
        if self.G > 2:
            # attention: the noticed enemy nearest the crosshair (the current one is preferred a little, so the
            # choice does not flicker); with nobody noticed, the one in view, else the one seen or heard last
            cur = np.zeros((n, self.G - 1), bool)
            cur[ar, self.fidx] = True
            sc_ = np.where(self.acq2, off * np.where(cur, 0.6, 1.0), np.where(self.vis2, 2.0 + off, 4.0 + self.seen2))
            self.fidx = sc_.argmin(1)
        self.foe = self.others[ar, self.fidx]
        opp = self.foe
        vis = self.vis2[ar, self.fidx]
        self.visible = vis
        self.vis_run = self.vis_run2[ar, self.fidx]
        self.acquired = self.acq2[ar, self.fidx]
        self.known = self.known2[ar, self.fidx]
        self.seen_t = self.seen2[ar, self.fidx]
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        vh = np.nonzero(vis & (self.script == 0))[0]        # aim quality while the enemy is in view
        if len(vh):
            cosang = np.clip((to[vh] * fdir[vh]).sum(1) / dist[vh], -1, 1)
            self.stats["aim_err"] += float(np.degrees(np.arccos(cosang)).sum())
            self.stats["aim_frames"] += len(vh)
            self.stats["on_target"] += int(self._seg_box(eye[vh], eye[vh] + fdir[vh].astype(np.float32) * 4000.0,
                                                         s[opp[vh], :3],
                                                         np.where(self.duck[opp[vh]], TOP_DUCK, TOP)).sum())
            nv = vh[pkind[vh] == NORMAL]
            np.add.at(self.stats["w_dist"], (np.digitize(dist[nv], [300.0, 700.0]), self.weapon[nv]), 1)
''' + s[b:]

left = re.findall(r".*(?:\^ 1|// 2\b|repeat\(self\.[a-z_ >0]*, 2\b|2 \* m\b).*", s)
left = [l for l in left if "dmg_life[i ^ 1]" not in l]
assert not left, left
open(os.path.join(ROOT, "sim", "duel_env_ffa.py"), "w", newline="", encoding="utf-8").write(s)
print("wrote sim/duel_env_ffa.py")

"""2.1, the perfect-spam probe (docs/runs/2.1/INSTRUCTION.md, "The scripted seats"): can fire on a point with nobody in view pay at
all in the simulator: rockets, grenades or plasma put on a place the enemy is about to pass? The held-angle probe's method
(tools/run/hold_hook.py, whose moments, copies, mouse and counters this reuses); a measurement on tools/duel_eval.py's loop
(BRANCH_HOOK=spam_hook); trains nothing.

At a frozen moment (he on the floor, neither sees the other, the enemy 300 to 1,500 units away) every match is one branch:

  free            the network plays on                                               (the reference)
  free_<w>        the network plays on with weapon w in his hand (given)             (what the weapon alone is worth)
  <w>_oracle      a scripted spam with weapon w (rl, gl, pg; given, in hand): he stands, turns to the point and fires on it. The
                  point: the map's spam point (sim/order_maps, the pros' corridors and doorways) nearest to where the enemy TRULY
                  will be in a second, and the script knows the seconds of walking he has to it, so the first shot is timed to land
                  as he arrives (the upper bound: a brain that forecasts him perfectly)
  <w>_fair        the point nearest to where he LAST KNEW him (his own sighting or sound); no time known: he fires at once
  ..._rel         the script holds until SP_REL s after the enemy first came into his view, then the network plays on

Rockets and plasma need a clear line from his eye to the point (none: the branch is marked line = false and plays free); a grenade
takes its low arc to it. The script's seat stays a network seat (his mouse, his click limit, his finger limits), as the hold's.
With INSTR=1 the seat is also given the instruction (spam, the point, the weapon, the time) through instr_in(), so the branch's
frames carry the instruction's inputs and state as a drill's would.

Written per branch (HP_OUT, .jsonl): the hold probe's columns, and line, the seconds the script knew (-1: none), the distance to the
point, and the instruction's state at the end (-1: INSTR off).
"""
import os

import numpy as np

import hold_hook as HH

DEF_OPTS = "free,free_rl,rl_oracle_rel,rl_fair_rel,gl_oracle_rel,gl_fair_rel,pg_oracle_rel"


class Hook(HH.Hook):
    def __init__(self, E, env, mp, seed, ev, od):
        if not os.environ.get("HP_OPTS"):
            os.environ["HP_OPTS"] = DEF_OPTS
        super().__init__(E, env, mp, seed, ev, od)
        self.W = {"rl": E.RL, "gl": E.GL, "pg": E.PG}
        o_ = self.o_name
        self.o_w = np.array([self.W.get(x.split("_")[-1] if x.startswith("free_") else x.split("_")[0], -1) for x in o_])
        self.o_scr = np.array([x.split("_")[0] in self.W for x in o_])
        self.o_orc = np.array(["oracle" in x for x in o_])
        self.near_pt = float(os.environ.get("SP_NEAR", 600))                # a spam point this near his expected place, else that place
        self.ahead = float(os.environ.get("SP_AHEAD", 1.0))                 # seconds ahead the oracle places him
        self.early = float(os.environ.get("SP_EARLY", 0.4))                 # the first shot leaves when it would land this much before him
        self.tol = float(os.environ.get("SP_TOL", 3.0))                     # degrees off the aim he fires within
        self.rel = int(float(os.environ.get("SP_REL", os.environ.get("HP_REL", 1.5))) / E.DT)

    # ------------------------------------------------------------ the moment: the point of every branch
    def top(self, t, obs, h, h2):
        was = self.on
        super().top(t, obs, h, h2)
        if was or not self.on:
            return
        e, E = self.env, self.E
        i, o = self.ev, self.od
        g = self.o_w >= 0                                    # (the hold's ten rounds are few for plasma)
        e.ammo[i[g], self.o_w[g]] = np.maximum(e.ammo[i[g], self.o_w[g]], np.where(self.o_w[g] == E.PG, 60, 10))
        s = e.state
        want = np.where(self.o_orc[:, None], s[o, :3] + s[o, 3:6] * self.ahead, np.asarray(e.known, np.float32)[i])
        self.pt = want.astype(np.float32).copy()
        self.when = np.full(self.M, -1.0, np.float32)
        om, R = getattr(e, "om", None), getattr(e, "route", None)
        if om is not None and len(om["spam_pos"]):
            sp = np.asarray(om["spam_pos"], np.float32)
            dd = np.linalg.norm(want[:, None, :] - sp[None], axis=2)
            k = dd.argmin(1)
            use = dd.min(1) < self.near_pt
            self.pt[use] = sp[k[use]]
        if om is not None and R is not None:                 # the oracle's seconds: his walk to the point
            self.when = np.where(self.o_orc, om["walk"][R.locate(s[o, :3]), R.locate(self.pt)], -1.0).astype(np.float32)
            self.when = np.where(np.isfinite(self.when) & (self.when < 30.0), self.when, -1.0).astype(np.float32)
        eye = e._eye(s)[i]
        self.dpt = np.linalg.norm(self.pt - eye, axis=1)
        self.line = np.asarray(e._los(eye, self.pt), bool) | (self.o_w == E.GL)
        self.scr &= self.line                                # no line for a straight shot: the branch plays free
        self.ins_end = np.full(self.M, -1)
        self.el = 0.0
        self._instr(np.ones(self.M, bool))

    def _instr(self, live):
        """(INSTR) the script's seats under the instruction; every other seat, and a seat the script has let go, under none"""
        e, E = self.env, self.E
        if not getattr(E, "INSTR", False):
            return
        n = e.n
        verb, tg, w = np.zeros(n, np.int64), np.full(n, -1, np.int64), np.full(n, -1, np.int64)
        place, point = np.full((n, 3), np.nan, np.float32), np.full((n, 3), np.nan, np.float32)
        when = np.full(n, -1.0, np.float32)
        mm = np.nonzero(self.scr & live)[0]
        i = self.ev[mm]
        verb[i], w[i] = E.INS_SPAM, self.o_w[mm]
        place[i], point[i] = self.p0[mm], self.pt[mm]
        when[i] = np.where(self.when[mm] >= 0, np.maximum(self.when[mm] - self.el, 0.0), -1.0)
        e.instr_in(verb, tg, place, point, w, when)

    # ------------------------------------------------------------ the script's keys
    def act(self, t, obs, a):
        if not self.on:
            return
        e, E = self.env, self.E
        self.el = (t - self.t_copy) * E.DT
        vis_i = e.visible[self.ev]
        self.contact = np.where((self.contact < 0) & vis_i, t - self.t_copy, self.contact)
        self.scr &= e.hp[self.ev] > 0
        self.scr &= ~(self.o_rel & (self.contact >= 0) & (t - self.t_copy >= self.contact + self.rel))
        self._instr(np.ones(self.M, bool))
        mm = np.nonzero(self.scr)[0]
        if not len(mm):
            return
        i = self.ev[mm]
        s, w, pt = e.state, self.o_w[mm], self.pt[mm]
        eye = e._eye(s)[i]
        yaw, pit = np.radians(e.yaw[i]), np.radians(e.pitch[i])
        ey, ep = E.DuelEnv._aim_at(eye, pt, yaw, pit)
        to = pt - eye
        D = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        fly = np.linalg.norm(to, axis=1) / np.where(w == E.PG, E.P_SPEED[E.PG], E.P_SPEED[E.RL])
        gl = w == E.GL
        reach = np.ones(len(mm), bool)
        if gl.any():                                         # the grenade's low arc (the simulator's own sums: _v15, _ins)
            v_, g_ = float(E.P_SPEED[E.GL]), float(E.P_GRAV[E.GL])
            disc = v_ ** 4 - g_ * (g_ * D * D + 2.0 * to[:, 2] * v_ * v_)
            th = np.arctan2(v_ * v_ - np.sqrt(np.maximum(disc, 0.0)), g_ * D)
            ep = np.where(gl, np.degrees(-(th - 0.2 * np.cos(th)) - pit), ep)
            fly = np.where(gl, D / np.maximum(v_ * np.cos(th), 1.0), fly)
            reach = ~gl | (disc >= 0.0)
        ey, ep = ey.astype(np.float32), ep.astype(np.float32)
        hb = e.hb if E.HAND_BAND else e.mv
        lev = np.where(e.seen_t[i] > 0.5, e.level, 1.0).astype(np.float32)
        ti = e._rjc_pick(e.mv[i, 0], hb[i, 0], ey, E.TURN, lev, E.TURN_CAP if e.human_aim else None, None, rate=np.zeros(len(mm), np.float32))
        pi = e._rjc_pick(e.mv[i, 1], hb[i, 1], ep, E.PITCH, lev, None, e.pitch[i].astype(np.float32))
        left = np.where(self.when[mm] >= 0, self.when[mm] - self.el, -1.0)
        go = (self.when[mm] < 0) | (fly >= left - self.early)                 # timed: not before it would land SP_EARLY ahead of him
        fire = reach & go & (np.abs(ey) < self.tol) & (np.abs(ep) < self.tol) & (e.weapon[i] == w)
        a[i, 0], a[i, 1], a[i, 2] = 1, 1, 0                                    # he stands
        a[i, 3], a[i, 4] = ti, pi
        a[i, 5] = fire
        a[i, 6] = np.where(e.weapon[i] == w, 0, w + 1)
        a[i, 7:10] = 0

    # ------------------------------------------------------------ the outcome
    def after(self, t, r, info):
        if not self.on:
            return
        n0 = len(self.rows)
        if getattr(self.E, "INSTR", False):
            self.ins_end = np.where(self.env.ins_v[self.ev] > 0, self.env.ins_st[self.ev], self.ins_end)
        super().after(t, r, info)
        if len(self.rows) > n0:                              # the window's end: the rows just written, a branch a row in order
            for m, row in enumerate(self.rows[n0:]):
                row.update(line=bool(self.line[m]), when=float(self.when[m]), dpt=float(self.dpt[m]), ins=int(self.ins_end[m]))
            self._instr(np.zeros(self.M, bool))              # every seat under none again

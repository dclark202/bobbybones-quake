"""2.0c, the perfect-hold probe (docs/runs/2.1/DESIGN.md, "Teaching the hands a verb", condition 3): can a hold pay at all in the
simulator under his aim limits? A measurement on tools/duel_eval.py's loop (BRANCH_HOOK=hold_hook); trains nothing.

Every match of the job is one branch. All matches play freely (1.7a's update 90 on both seats); when some match stands at a moment
of the pros' kind of hold (he alive and on the floor, the enemy alive, neither sees the other, he has not seen him for a second, the
enemy 300 to 1,500 units away; first choice: he is within HP_NEAR units of one of the map's holding places, sim/pro_holds), that
moment is copied into every match with both networks' memories (branch_hook's way) and each branch plays one option for HP_WIN s:

  free          the network plays on, nothing changed                               (the reference)
  free_rg       the network plays on with the rail in his hand (given, 10 slugs)    (what the weapon alone is worth)
  <w>_<aim>     a scripted hold with weapon w (rg, lg, rl; given, in hand): he stands still, pre-aims, and fires as early as his
                limits allow. aim = oracle: until the enemy is in his view the script turns to the enemy's TRUE place through the
                wall (he "knew the opening": the upper bound; from the frame the enemy is truly in view to the frame he notices
                him the script holds still: the acquire delay is not tracked through). aim = fair: it turns to his own last
                sighting or sound of him (the inputs' direction), nothing if older than 5 s.
                From the frame he notices him (the inputs' "noticed in view") both aim by the inputs' crosshair error, i.e. with
                his reaction delay and sight error, and fire when the inputs say the crosshair is on him (rockets: at his feet
                with the lead of his believed speed, within 3 degrees).
  ..._net       the script stands, holds the weapon and pre-aims; from the frame he notices him the NETWORK aims and fires
                (his hands as they are today, made to stand)
  ..._rel       the script holds until HP_REL s after the enemy first came into his view, then the network plays on
                (without it the script stands still for the whole window)

The script's seat stays a network seat (script 0): its turn goes through his mouse (the smoothing, the flick cap, the hand's
bandwidth and noise: commands picked by the simulator's own _rjc_pick), its trigger through his click limit, its keys through his
finger limits. What is NOT his: the oracle's pre-aim, and a script that never moves.

Written per branch (HP_OUT, .jsonl): the option, the holding place (-1: none near), the distance at the copy, damage dealt and taken
(stack lost, a death = the stack he had), frags, pay of both seats, the frame the enemy came into his view (-1: never), the frames
from there to his first damage, shots and hits of the given weapon while the script held.
"""
import csv
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLS = {35: "noticed in view", 37: "last known position: forward", 40: "velocity: forward", 43: "direction: sin", 44: "direction: cos",
        45: "direction up-down: cos", 46: "direction up-down: sin", 51: "crosshair on him"}
DEF_OPTS = "free,free_rg,rg_oracle,rg_oracle_rel,rg_fair,rg_fair_rel,lg_oracle_rel,rl_oracle_rel"


class Hook:
    def __init__(self, E, env, mp, seed, ev, od):
        self.E, self.env, self.mp, self.ev, self.od = E, env, mp, np.asarray(ev), np.asarray(od)
        self.M = len(self.ev)
        rows = {int(r["index"]): r for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))}
        for c_, nm in COLS.items():                          # (the inputs the script reads are where it thinks they are)
            assert rows[c_]["group"] == "enemy" and rows[c_]["input"] == nm, (c_, rows[c_]["input"])
        self.opts = (os.environ.get("HP_OPTS") or DEF_OPTS).split(",")
        self.W = {"rg": E.RG, "lg": E.LG, "rl": E.RL}
        self.warm = int(float(os.environ.get("HP_WARM", 12)) / E.DT)
        self.win = int(float(os.environ.get("HP_WIN", 8)) / E.DT)
        self.rel = int(float(os.environ.get("HP_REL", 1.5)) / E.DT)
        self.wait = int(float(os.environ.get("HP_WAIT", 15)) / E.DT)     # after this long with no moment at a holding place: any place
        self.near = float(os.environ.get("HP_NEAR", 200))
        self.brake = int(os.environ.get("HP_BRAKE", 3))
        self.cmax = float(os.environ.get("HP_CMAX", 30))
        self.settle = float(os.environ.get("HP_SETTLE", 3))                # he fires only with the view this slow (degrees a frame)
        self.lead = float(os.environ.get("HP_LEAD", 0.15))               # seconds the script aims ahead: his reaction time and a frame
        self.out = os.environ.get("HP_OUT", "hold.jsonl")
        pf = os.path.join(ROOT, "sim", "pro_holds", mp + ".json")
        self.places = np.array([p["pos"] for p in json.load(open(pf))["places"]], np.float32) if os.path.exists(pf) else np.zeros((0, 3), np.float32)
        self.rng = np.random.default_rng(seed + 91)
        self.t0, self.on = self.warm, False
        self.rows, self.n_pts = [], 0
        self.trace = []
        o_ = [self.opts[m % len(self.opts)] for m in range(self.M)]
        self.o_w = np.array([self.W.get(x.split("_")[0], -1) if x != "free" else -1 for x in o_])        # the weapon given (-1: none)
        self.o_scr = np.array([x.split("_")[0] in self.W and not x.startswith("free") for x in o_])       # a scripted hold
        self.o_orc = np.array(["oracle" in x or "place" in x for x in o_])
        self.o_plc = np.array(["place" in x for x in o_])
        self.t_note = float(os.environ.get("HP_NOTE", 0.2))               # seconds from truly in view to noticed (measured: 200 ms)
        self.o_rel = np.array([x.endswith("_rel") for x in o_])
        self.o_net = np.array(["_net" in x for x in o_])
        self.o_name = o_

    def _stack(self):
        e = self.env
        return (np.maximum(e.hp, 0) + e.armor).astype(np.float64)

    # ------------------------------------------------------------ the moment
    def _find(self, t):
        e, s = self.env, self.env.state
        i, o = self.ev, self.od
        d = np.linalg.norm(s[i, :3] - s[o, :3], axis=1)
        ok = (e.hp[i] > 0) & (e.hp[o] > 0) & ~e.visible[i] & ~e.visible[o] & (e.seen_t[i] > 1.0) & (s[i, 6] > 0.5) & (d > 300) & (d < 1500)
        pl = np.full(self.M, -1)
        if len(self.places):
            dp = np.linalg.norm(s[i, None, :3] - self.places[None], axis=2)
            pl = np.where(dp.min(1) < self.near, dp.argmin(1), -1)
        c = np.nonzero(ok & (pl >= 0))[0]
        if not len(c) and t >= self.t0 + self.wait:
            c = np.nonzero(ok)[0]
        if not len(c):
            return None
        m = int(self.rng.choice(c))
        return m, int(pl[m]), float(d[m])

    def top(self, t, obs, h, h2):
        e, E = self.env, self.E
        if self.on or t < self.t0:
            return
        f = self._find(t)
        if f is None:
            return
        src, self.place, self.d0 = f
        mo = e._moment_take(src, obs)
        for m in range(self.M):
            if m != src:
                e._moment_set(m, mo, obs)
        h[:] = h[src]
        if h2 is not None:
            h2[:] = h2[src]
        g = self.o_w >= 0                                    # the weapon given, in his hand, ready
        i = self.ev[g]
        w = self.o_w[g]
        e.has[i, w] = True
        e.ammo[i, w] = np.maximum(e.ammo[i, w], np.where(w == E.LG, 100, 10))
        e.weapon[i] = w
        e.cool[i] = 0.0
        self.on, self.t_copy = True, t
        self.scr = self.o_scr.copy()                         # the script holds his seat
        self.contact = np.full(self.M, -1)
        self.first = np.full(self.M, -1)
        self.pay = np.zeros((self.M, 2))
        self.fr = np.zeros((self.M, 2))
        self.dmg = np.zeros((self.M, 2))                     # dealt (the opponent's stack lost), taken
        self.shots, self.hits = np.zeros(self.M), np.zeros(self.M)
        self.st = self._stack()
        self.am = e.ammo.copy()
        self.brg, self.b_ok, self.held = np.zeros(self.M), np.zeros(self.M, bool), np.zeros(self.M, bool)
        self.p0 = e.state[self.ev, :3].copy()
        self.shot1, self.hit1 = np.full(self.M, -1), np.zeros(self.M, bool)

    # ------------------------------------------------------------ the script's keys
    def act(self, t, obs, a):
        if not self.on:
            return
        e, E = self.env, self.E
        vis_i = e.visible[self.ev]
        self.contact = np.where((self.contact < 0) & vis_i, t - self.t_copy, self.contact)
        self.scr &= e.hp[self.ev] > 0                                          # dead: the network's again
        self.scr &= ~(self.o_rel & (self.contact >= 0) & (t - self.t_copy >= self.contact + self.rel))
        mm = np.nonzero(self.scr)[0]
        if not len(mm):
            return
        i, o = self.ev[mm], self.od[mm]
        ob, s = obs[i], e.state
        assert not np.any(np.asarray(getattr(e, "ta_add", 0.0))[i] != 0), "the legs' turn is added to the script's"
        seen = ob[:, 35] > 0.5                                                 # he has noticed him (his delays)
        w = self.o_w[mm]
        ey = np.degrees(np.arctan2(ob[:, 43], ob[:, 44]))                      # by his inputs: the last sighting or sound
        ep = np.degrees(np.arctan2(ob[:, 46], ob[:, 45]))
        # in view: where he will be when the shot lands. His picture of the enemy is a reaction time old, so the script aims
        # ahead by that and a frame, with the speed he believes (itself 200 ms late); rockets: their flight too, and his feet
        p, v = ob[:, 37:40] * 1000.0, ob[:, 40:43] * 400.0
        d = np.linalg.norm(p, axis=1) + 1e-6
        hd = np.hypot(p[:, 0], p[:, 1]) + 1e-6
        tl = self.lead + np.where(w == E.RL, d / E.P_SPEED[E.RL], 0.0)
        ey = ey + np.where(seen, np.degrees(np.arctan2(v[:, 1] * tl, hd)), 0.0)
        ep = ep + np.where(seen, -np.degrees(np.arctan2(v[:, 2] * tl, hd)) + np.where(w == E.RL, np.degrees(np.arctan2(24.0, hd)), 0.0), 0.0)
        eye = e._eye(s)[i]
        to = s[o, :3] + np.array([0, 0, 4.0], np.float32) - eye
        ty = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - e.yaw[i] + 180.0) % 360.0 - 180.0
        tp = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - e.pitch[i]
        pre = self.o_orc[mm] & ~seen                                           # the oracle's pre-aim: the true place, until he is truly in view
        hold = pre & e.visible[i]                                              # ... then still until he notices him
        # (..._place: the crosshair set where he will be when he is noticed, as a player who knows the opening sets it on the
        # enemy's path: from the frame he is truly in view, his true place plus his true speed times the time left to the notice)
        left = np.maximum(0.0, self.t_note - (t - self.t_copy - self.contact[mm]) * E.DT) + self.lead
        to2 = to + s[o, 3:6] * left[:, None]
        ty2 = (np.degrees(np.arctan2(to2[:, 1], to2[:, 0])) - e.yaw[i] + 180.0) % 360.0 - 180.0
        tp2 = -np.degrees(np.arctan2(to2[:, 2], np.hypot(to2[:, 0], to2[:, 1]) + 1e-6)) - e.pitch[i]
        plc = self.o_plc[mm]
        ey = np.where(pre, np.where(hold, np.where(plc, ty2, 0.0), ty), ey).astype(np.float32)
        ep = np.where(pre, np.where(hold, np.where(plc, tp2, 0.0), tp), ep).astype(np.float32)
        hb = e.hb if E.HAND_BAND else e.mv
        lev = np.where(e.seen_t[i] > 0.5, e.level, 1.0).astype(np.float32)
        brg = e.yaw[i] + ey                                                    # the aim point's bearing: how fast it moves (tracking)
        rate = np.where(seen & self.b_ok[mm], (brg - self.brg[mm] + 180.0) % 360.0 - 180.0, 0.0)
        rate = np.where(np.abs(rate) < 6.0, rate, 0.0).astype(np.float32)      # (a jump of the picture is no motion)
        self.brg[mm], self.b_ok[mm] = brg, seen
        ti = e._rjc_pick(e.mv[i, 0], hb[i, 0], ey, E.TURN, lev, E.TURN_CAP if e.human_aim else None, None, rate=rate)
        pi = e._rjc_pick(e.mv[i, 1], hb[i, 1], ep, E.PITCH, lev, None, e.pitch[i].astype(np.float32))
        fl = seen | (hold & plc)
        if fl.any():                                                           # in view: a flick (this frame's command, then the brake)
            ti = np.where(fl, self._flick(e.mv[i, 0], hb[i, 0], ey, E.TURN, E.TURN_CAP if e.human_aim else None, rate), ti)
            pi = np.where(fl, self._flick(e.mv[i, 1], hb[i, 1], ep, E.PITCH, None, 0.0), pi)
        cy, cp = E.TURN[ti], E.PITCH[pi]                                       # what is left after this frame's turn (the shot leaves after it)
        ry = ey - (np.where(np.abs(cy) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH) * e.mv[i, 0] + (1.0 - np.where(np.abs(cy) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH)) * cy)
        rp = ep - (np.where(np.abs(cp) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH) * e.mv[i, 1] + (1.0 - np.where(np.abs(cp) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH)) * cp)
        ty_, tp_ = np.degrees(np.arctan2(13.0, d)), np.degrees(np.arctan2(24.0, d))    # his body's half width and half height from here
        k_ = np.where(w == E.LG, 1.5, 1.0)
        fire = seen & np.where(w == E.RL, (np.abs(ry) < 3.0) & (np.abs(rp) < 3.0), (np.abs(ry) < ty_ * k_) & (np.abs(rp) < tp_ * k_))
        vy_ = np.where(np.abs(cy) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH) * e.mv[i, 0] + (1.0 - np.where(np.abs(cy) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH)) * cy
        fire = fire & ((w != E.RG) | (np.abs(vy_) < self.settle))
        fire = fire | (self.held[mm] & seen & (w != E.LG) & (e.fire_cd[i] <= 0) & (np.abs(ry) < 2 * ty_))   # a click begun is finished
        self.held[mm] = fire
        a[i, 0], a[i, 1], a[i, 2] = 1, 1, 0                                    # he stands
        net = self.o_net[mm] & seen                                            # (..._net: from the frame he notices him the network's own mouse and trigger)
        a[i, 3], a[i, 4] = np.where(net, a[i, 3], ti), np.where(net, a[i, 4], pi)
        a[i, 5] = np.where(net, a[i, 5], fire & (e.weapon[i] == w))
        a[i, 6] = np.where(e.weapon[i] == w, 0, w + 1)
        a[i, 7:10] = 0                                                         # no walk, zoom or lifted mouse
        if os.environ.get("HP_TRACE"):                                         # (the first shot, frame by frame: where its time goes)
            c_ = self.contact[mm]
            for j in np.nonzero((c_ >= 0) & (t - self.t_copy - c_ < 60))[0]:
                self.trace.append((self.n_pts, int(mm[j]), int(t - self.t_copy - c_[j]), int(e.acquired[i[j]]), int(seen[j]), float(ey[j]), float(ep[j]),
                                   float(ry[j]), float(rp[j]), float(ty_[j]), float(tp_[j]), int(fire[j]), int(e.weapon[i[j]] == w[j]), float(e.cool[i[j]]),
                                   float(e.fire_cd[i[j]]), int(e.mouse_hold[i[j], 0]), int(e.fire_last[i[j]]), float(e.ammo[i[j], w[j]]), float(d[j]),
                                   float(e.mv[i[j], 0]), float(E.TURN[ti[j]])))

    def _flick(self, vel, hb, err, cands, cap, rate):
        """per player the command that brings the view onto the target soonest: for every command, this frame with it and then
        BRAKE frames with none (his mouse as step() moves it: the smoothing, the flick cap, the hand's bandwidth); the one whose
        view comes to rest nearest the target (which moves on at rate degrees a frame)"""
        E = self.E
        c_ = cands[None, :].astype(np.float32)
        m_ = np.repeat(np.asarray(vel, np.float32)[:, None], cands.shape[0], 1)
        h_ = np.repeat(np.asarray(hb, np.float32)[:, None], cands.shape[0], 1)
        e_ = np.repeat(np.asarray(err, np.float32)[:, None], cands.shape[0], 1)
        r_ = np.asarray(rate, np.float32)
        r_ = r_[:, None] if r_.ndim else r_
        for f in range(1 + self.brake):
            cmd = c_ if f == 0 else np.zeros_like(c_)
            sm = np.where(np.abs(cmd) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH).astype(np.float32)
            m_ = sm * m_ + (1.0 - sm) * cmd
            if cap is not None:
                m_ = np.clip(m_, -cap, cap)
            if E.HAND_BAND:
                k_ = (1.0 - np.exp(-2.0 * np.pi * (E.HB_FC + E.HB_BETA * np.abs(h_)) * E.DT)).astype(np.float32)
                h_ = h_ + k_ * (m_ - h_)
                v_ = h_
            else:
                v_ = m_
            e_ = e_ - v_ + r_
        return np.argmin(np.abs(e_) + np.where(np.abs(c_) > self.cmax, 1e6, 0.0), 1)      # (no command over HP_CMAX: a wild hand shakes)

    # ------------------------------------------------------------ the outcome
    def after(self, t, r, info):
        if not self.on:
            return
        e = self.env
        self.pay[:, 0] += r[self.ev]
        self.pay[:, 1] += r[self.od]
        st = self._stack()
        lost = np.where(self.st - st >= 2.0, self.st - st, 0.0)
        for ev_ in info.get("events", ()):                   # (a death and the respawn fall in one step: the stack he had)
            k, v = int(ev_["killer"]), int(ev_["victim"])
            lost[v] = self.st[v]
            for side, seats in ((0, self.ev), (1, self.od)):
                wv = np.nonzero(seats == v)[0]
                if len(wv):
                    self.fr[wv[0], side] -= 1
                    if k >= 0 and k != v:
                        self.fr[wv[0], 1 - side] += 1
        self.dmg[:, 0] += lost[self.od]
        self.dmg[:, 1] += lost[self.ev]
        self.first = np.where((self.first < 0) & (self.contact >= 0) & (lost[self.od] > 0), t - self.t_copy - self.contact, self.first)
        g = np.nonzero(self.scr)[0]
        if len(g):
            i, w = self.ev[g], self.o_w[g]
            sh = np.maximum(0.0, self.am[i, w] - e.ammo[i, w])
            f1 = (self.shot1[g] < 0) & (sh > 0) & (self.contact[g] >= 0)     # his first shot after the enemy came into view
            self.shot1[g] = np.where(f1, t - self.t_copy - self.contact[g], self.shot1[g])
            self.hit1[g] = np.where(f1, lost[self.od[g]] > 0, self.hit1[g])
            self.shots[g] += sh
            self.hits[g] += (sh > 0) & (lost[self.od[g]] > 0)
        self.st, self.am = st, e.ammo.copy()
        if t == self.t_copy + self.win - 1:
            for m in range(self.M):
                self.rows.append(dict(map=self.mp, point=self.n_pts, t=int(self.t_copy), opt=self.o_name[m], place=self.place, d0=self.d0,
                                      dealt=float(self.dmg[m, 0]), taken=float(self.dmg[m, 1]), fr_he=float(self.fr[m, 0]), fr_opp=float(self.fr[m, 1]),
                                      pay_he=float(self.pay[m, 0]), pay_opp=float(self.pay[m, 1]), contact=int(self.contact[m]),
                                      first=int(self.first[m]), shot1=int(self.shot1[m]), hit1=bool(self.hit1[m]), moved=float(np.linalg.norm(e.state[self.ev[m], :3] - self.p0[m])), shots=float(self.shots[m]), hits=float(self.hits[m])))
            self.n_pts += 1
            self.on = False
            self.t0 = t + 1 + self.warm

    def end(self):
        if os.environ.get("HP_TRACE") and self.trace:
            np.save(os.environ["HP_TRACE"] + "_" + self.mp + ".npy", np.array(self.trace, np.float64))
        with open(self.out, "a", encoding="utf-8") as f:
            for r in self.rows:
                f.write(json.dumps(r) + "\n")

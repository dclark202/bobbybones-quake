"""aim3: his games in the columns of the pros' sets (sim/demo_dataset.py --lite3; tools/run/pro_aim.py reads both), so his aim is
measured exactly as theirs. A recorder on tools/duel_eval.py's loop (BRANCH_HOOK=aim_rec_hook); changes nothing in the game.

Every frame of his seats (the even ones, or all with AR_BOTH=1): health, armor, weapon, trigger, the enemy truly in view, his place,
the enemy's place and speed, yaw, pitch, the enemy "sent" (alive), a hit counter (one a frame on which he dealt damage: the
simulator's dmg_life), the seat, the ammunition, the reload left, crouched, his speed. A new stretch at the start and after a death.
Written at the game's end to AR_OUT (.npz: lite, first).
"""
import os

import numpy as np


class Hook:
    def __init__(self, E, env, mp, seed, ev, od):
        self.E, self.env = E, env
        self.seats = np.arange(env.n) if os.environ.get("AR_BOTH") else np.asarray(ev)
        self.opp = self.seats ^ 1
        self.rows, self.first = [], []
        self.hits = np.zeros(len(self.seats))
        self.dl0 = np.asarray(env.dmg_life, np.float64)[self.seats].copy()
        self.was = np.zeros(len(self.seats), bool)
        self.fire = np.zeros(len(self.seats))
        self.out = os.environ.get("AR_OUT", "aim_rec.npz")

    def top(self, t, obs, h, h2):
        pass

    def act(self, t, obs, a):
        self.fire = (a[self.seats, 5] == 1).astype(np.float64)

    def after(self, t, r, info):
        e, s, i, o = self.env, self.env.state, self.seats, self.opp
        dl = np.asarray(e.dmg_life, np.float64)[i]
        self.hits += dl > self.dl0 + 0.5
        self.dl0 = dl.copy()
        alive = e.hp[i] > 0
        row = np.concatenate([e.hp[i, None], e.armor[i, None], e.weapon[i, None], self.fire[:, None], e.visible[i, None], s[i, :3], s[o, :3],
                              s[o, 3:6], e.yaw[i, None], e.pitch[i, None], (e.hp[o] > 0)[:, None], self.hits[:, None], i[:, None], e.ammo[i],
                              e.cool[i, None] * 1000.0, e.duck[i, None], s[i, 3:6]], 1).astype(np.float32)
        died = np.zeros(len(i), bool)
        for ev_ in info.get("events", ()):
            died |= i == int(ev_["victim"])
        self.rows.append(row)
        self.first.append(~self.was | died | ~alive)
        self.was = alive & ~died

    def end(self):
        L = np.stack(self.rows, 1)                           # seats x frames x columns
        F = np.stack(self.first, 1)
        keep = L[:, :, 0] > 0
        lite = np.concatenate([L[k][keep[k]] for k in range(len(L))])
        first = []
        for k in range(len(L)):
            f = F[k][keep[k]].copy()
            if len(f):
                f[0] = True
                gone = np.diff(np.nonzero(keep[k])[0]) > 1   # frames left out between two kept ones: a new stretch
                f[1:] |= gone
            first.append(f)
        np.savez_compressed(self.out, lite=lite, first=np.concatenate(first))

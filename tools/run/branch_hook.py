"""2.0c, test 4 (docs/runs/2.1/DESIGN.md): the frozen moment. A measurement on tools/duel_eval.py's loop (BRANCH_HOOK=branch_hook);
trains nothing.

Every match of the job is one branch. The cycle: all matches play freely for BR_WARM seconds; then one match's moment (the simulator's
own _moment_take: bodies, stacks, rockets in the air, items, clocks, what each knows) is copied into every other match with both
networks' memories, so all stand at the same moment; then his seat of match m is held on the target BR_OPTS[m % K] for BR_HOLD
seconds (env.force_intent) and plays freely after; BR_WIN seconds after the copy each branch's outcome is written: the pay of both
seats over the window (the run's own pay), the stacks, frags and deaths. With R = matches / K branches a target, the spread between
the targets is set beside the spread between two branches of one target (the noise).

What is not the same in the branches: the simulator's random numbers (one stream for all matches: each branch draws its own), the
staggered reading frames of a seat. What is: everything a moment keeps, and the networks' memories.

Settings (environment): BR_OPTS "1,2,3,..." targets (duel_env INTENTS' numbers; default: the items, the enemy and the map's holding
places), BR_WARM 20, BR_HOLD 4, BR_WIN 10, BR_OUT a .jsonl to append to.
"""
import json
import os

import numpy as np


class Hook:
    def __init__(self, E, env, mp, seed, ev, od):
        self.E, self.env, self.mp, self.ev, self.od = E, env, mp, np.asarray(ev), np.asarray(od)
        self.M = len(self.ev)
        hn = int(getattr(env, "hold_n", 0))
        dflt = list(range(1, 9)) + list(range(E.HOLD_INTENT, E.HOLD_INTENT + hn))
        self.opts = [int(x) for x in os.environ["BR_OPTS"].split(",")] if os.environ.get("BR_OPTS") else dflt
        self.warm = int(float(os.environ.get("BR_WARM", 20)) / E.DT)
        self.hold = int(float(os.environ.get("BR_HOLD", 4)) / E.DT)
        self.win = int(float(os.environ.get("BR_WIN", 10)) / E.DT)
        self.out = os.environ.get("BR_OUT", "branch.jsonl")
        self.rng = np.random.default_rng(seed + 77)
        self.t0 = self.warm                                  # the frame of the next copy
        self.on = False
        self.rows, self.n_pts = [], 0
        env.force_intent = np.full(env.n, -1, np.int64)

    def _stack(self):
        e = self.env
        return (e.hp + e.armor).astype(np.float64).copy()

    def top(self, t, obs, h, h2):
        e = self.env
        if not self.on and t == self.t0:
            src = int(self.rng.integers(self.M))
            mo = e._moment_take(src, obs)
            for m in range(self.M):
                if m != src:
                    e._moment_set(m, mo, obs)
            h[:] = h[src]
            if h2 is not None:
                h2[:] = h2[src]
            self.own = int(e.intent[self.ev[src]])           # the target he was on at the moment
            e.force_intent[:] = -1
            e.force_intent[self.ev] = [self.opts[m % len(self.opts)] for m in range(self.M)]
            self.on, self.t_copy = True, t
            self.pay = np.zeros((self.M, 2))
            self.st0 = self._stack()
            self.fr = np.zeros((self.M, 2))
            self.got = None
        if self.on and t == self.t_copy + self.hold:
            self.got = e.intent[self.ev].copy()              # what he was really on at the end of the hold (a target the map lacks: 0)
            e.force_intent[:] = -1

    def after(self, t, r, info):
        if not self.on:
            return
        e = self.env
        self.pay[:, 0] += r[self.ev]
        self.pay[:, 1] += r[self.od]
        for ev_ in info.get("events", ()):                   # (duel_env's events: victim, killer (-1: his own hand or the map), weapon)
            k, v = int(ev_["killer"]), int(ev_["victim"])
            for side, seats in ((0, self.ev), (1, self.od)):
                w = np.nonzero(seats == v)[0]
                if len(w):                                   # the victim's side loses one, the other side gains one (not a suicide)
                    self.fr[w[0], side] -= 1
                    if k >= 0 and k != v:
                        self.fr[w[0], 1 - side] += 1
        if t == self.t_copy + self.win - 1:
            st = self._stack()
            for m in range(self.M):
                self.rows.append(dict(map=self.mp, point=self.n_pts, t=int(self.t_copy), own=self.own, opt=self.opts[m % len(self.opts)],
                                      got=int(self.got[m]) if self.got is not None else -1,
                                      pay_he=float(self.pay[m, 0]), pay_opp=float(self.pay[m, 1]), fr_he=float(self.fr[m, 0]), fr_opp=float(self.fr[m, 1]),
                                      st_he=float(st[self.ev[m]] - self.st0[self.ev[m]]), st_opp=float(st[self.od[m]] - self.st0[self.od[m]])))
            self.n_pts += 1
            self.on = False
            self.t0 = t + 1 + self.warm

    def end(self):
        with open(self.out, "a", encoding="utf-8") as f:
            for r in self.rows:
                f.write(json.dumps(r) + "\n")

"""(1.4b, BACKLOG B-300; owner 2026-11-03) matchmaking by difficulty (AlphaStar's prioritised fictitious self-play) and the league table.

The table (`data/sim_runs/league_table.json`, carried from run to run) keeps, by league file (an anchor by its file name, a snapshot as
<run>/snap_<minute>.pt): the training slices against it (one opponent network a rollout, about 10 s of each league game), the frags for
and against (one-against-one normal rounds and whole games: the trainer's kill hint), the win chance gained (the judge's win part at
G = 1, in its own unit: a frag at 0:0 with ten minutes left is 1), and `est`, his frags for and against with each older slice weighed
DECAY times the one after it. His frag share against a file, p = (for + 1) / (for + against + 2), is the draw's "win rate".

The draw (live dial d, 0 to 1): within the anchors and within the snapshots (the anchors' share, --anchor-p, kept), each file's chance is
(1 - d) x the even share + d x its share by (1 - p)^2, floored at half the even share; files named in `fixed` (the checks' opponent:
weighting it up when he loses to it would train him toward the gate) keep the even share. d = 0 is the even draw; the trainer then makes
exactly today's random calls."""
import json
import os

import numpy as np

DECAY = 0.7                          # an older slice against the same file weighs 0.7 of the one after it (about three slices' memory)
FLOOR = 0.5                          # each file's chance at least half the even share


class League:
    def __init__(self, path, run, fixed=()):
        self.path, self.run, self.fixed = path, run, set(f for f in fixed if f)
        self.tab = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f_:
                self.tab = json.load(f_)

    def p(self, name):
        """his frag share against `name`, from its decayed counts (1/2 with none)"""
        e_ = (self.tab.get(name) or {}).get("est") or [0.0, 0.0]
        return (float(e_[0]) + 1.0) / (float(e_[0]) + float(e_[1]) + 2.0)

    def shares(self, names, d):
        """each file's chance within its group at dial d"""
        k_ = len(names)
        even = 1.0 / k_
        w = np.full(k_, even)
        free = [i for i, n in enumerate(names) if n not in self.fixed]
        if d > 0 and free:
            mass = even * len(free)
            f = np.array([(1.0 - self.p(names[i])) ** 2 for i in free])
            fn = f / f.sum() * mass if f.sum() > 0 else np.full(len(free), even)
            fn = np.maximum(fn, FLOOR * even)
            fn = fn / fn.sum() * mass
            w[free] = (1.0 - d) * even + d * fn
        return w / w.sum()

    def pick(self, names, d, u):
        """the file drawn by the uniform number u (0 to 1)"""
        c_ = np.cumsum(self.shares(names, d))
        return int(min(np.searchsorted(c_, u * c_[-1], side="right"), len(names) - 1))

    def record(self, name, kf, ka, win, update):
        """one slice against `name`: his frags kf, its frags ka, his win chance gained"""
        e = self.tab.setdefault(name, dict(slices=0, frags_for=0, frags_against=0, win_gained=0.0, est=[0.0, 0.0], runs=[], first=""))
        e["slices"] += 1
        e["frags_for"] += int(kf)
        e["frags_against"] += int(ka)
        e["win_gained"] = round(float(e["win_gained"]) + float(win), 4)
        e["est"] = [round(DECAY * float(e["est"][0]) + kf, 3), round(DECAY * float(e["est"][1]) + ka, 3)]
        if self.run not in e["runs"]:
            e["runs"].append(self.run)
        e["first"] = e.get("first") or "{} u{}".format(self.run, update)
        e["last"] = "{} u{}".format(self.run, update)

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f_:
            json.dump(self.tab, f_, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

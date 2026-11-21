"""2.0b (docs/design/SPACE.md, docs/runs/2.0/2.0b/CARD.md): the table of a map, read in the simulator. Plain numpy, no tree, nothing
learned: the simulator (the truth columns, the inputs, the pay), the plugins and the checks read the same lookup.

The files: data/maps/space_<map>.npz (tools/run/space_score.py score, in the system Python: it needs scipy) and
sim/space_weapon.json (the pros' damage a second on a player in sight, by the weapon in the enemy's hand and the length of the line:
tools/run/space_score.py edge).

    S = load("bloodrun")            # None if the map has no table
    i = S.at(pos [n, 3])            # the nearest walking point of each place (the 32-unit cell's; the zones' grid)
    S.threat(frm, onto, wpn)        # damage a second a player round `frm` (anywhere he can walk to within REACH seconds), with the
                                    # weapon `wpn` in hand (duel_env's number), puts on the place `onto`
    S.edge(me, en, w_me, w_en)      # what he puts on where the enemy is, less what the enemy puts on where he is
    S.zone_cover(me, en, w_me, w_en)  # [n, MAX_Z] in -1 .. 1: of each zone, who puts more on it (his less the enemy's, a cover of
                                    # COVER_SCALE damage a second = 1; zones the map does not have: 0), and the mean over the map's points
    S.safer(me, en, w_en)           # the direction (a unit vector, or zeros) to the neighbouring point where the enemy's threat is
                                    # lowest, and how much lower it is there (damage a second)
A belief about the enemy that is a spread of places is read with `*_spread`: the same numbers as the mean over the places he may
be, each with its weight (the brain's place readout over the zones).
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAX_Z = 24                                                    # sim/zonemap.py's
COVER_SCALE = 10.0                                            # damage a second: this much more on a place than the enemy = the place is his
_W = None
_CACHE = {}


def weapons():
    """[9, 3]: damage a second by the weapon in hand (duel_env's numbers) and the line's length (under 400, 400 to 768, over 768)"""
    global _W
    if _W is None:
        _W = np.array(json.load(open(os.path.join(HERE, "space_weapon.json"), encoding="utf-8"))["dmg_s"], np.float32)
    return _W


class Space:
    def __init__(self, path):
        d = np.load(path)
        assert int(d["version"]) == 1, path
        self.P = d["nodes"].astype(np.float32)
        self.n = len(self.P)
        self.grid, self.lo, self.cell = d["grid"].astype(np.int64), d["lo"].astype(np.float64), float(d["cell"])
        self.dims = np.array(self.grid.shape, np.int64)
        self.seeb = d["seeb8"]                                # [3, from, onto] uint8: the share of from's reach that sees onto, * 255
        self.tz = d["tz8"]                                    # [3, from, zone] uint8: its mean over a zone's points
        self.zone, self.zsize = d["zone"].astype(np.int64), d["zsize"].astype(np.float32)
        self.k = len(self.zsize)
        self.zw = np.zeros(MAX_Z, np.float32)
        self.zw[:self.k] = self.zsize / max(float(self.zsize.sum()), 1.0)
        self.nb = d["nb"].astype(np.int64)                    # [point, NB]: its neighbours by walking time, -1 = none
        self.W = weapons()

    def at(self, pos):
        c = np.clip(((np.asarray(pos, np.float64).reshape(-1, 3) - self.lo) / self.cell).astype(np.int64), 0, self.dims - 1)
        return self.grid[c[:, 0], c[:, 1], c[:, 2]]

    def _w(self, wpn):
        return self.W[np.clip(np.asarray(wpn, np.int64), 0, len(self.W) - 1)]

    def threat(self, frm, onto, wpn):
        w = self._w(wpn)
        s = self.seeb
        return (w[:, 0] * s[0][frm, onto] + w[:, 1] * s[1][frm, onto] + w[:, 2] * s[2][frm, onto]) / np.float32(255.0)

    def edge(self, me, en, w_me, w_en):
        return self.threat(me, en, w_me) - self.threat(en, me, w_en)

    def zone_threat(self, frm, wpn):
        """[n, MAX_Z]: the damage a second a player round `frm` puts on each zone (its points' mean)"""
        w = self._w(wpn)
        t = (w[:, 0, None] * self.tz[0][frm] + w[:, 1, None] * self.tz[1][frm] + w[:, 2, None] * self.tz[2][frm]) / np.float32(255.0)
        out = np.zeros((len(t), MAX_Z), np.float32)
        out[:, :self.k] = t
        return out

    def zone_cover(self, me, en, w_me, w_en):
        c = np.clip((self.zone_threat(me, w_me) - self.zone_threat(en, w_en)) / COVER_SCALE, -1.0, 1.0)
        return c, c @ self.zw

    def safer(self, me, en, w_en):
        nb = self.nb[me]                                      # [n, NB]
        ok = nb >= 0
        nbs = np.where(ok, nb, me[:, None])
        w = self._w(w_en)
        s = self.seeb
        e = np.asarray(en)[:, None]
        t = (w[:, 0, None] * s[0][e, nbs] + w[:, 1, None] * s[1][e, nbs] + w[:, 2, None] * s[2][e, nbs]) / np.float32(255.0)
        here = self.threat(en, me, w_en)
        t = np.where(ok, t, np.inf)
        b = t.argmin(1)
        gain = here - t[np.arange(len(me)), b]
        to = self.P[nbs[np.arange(len(me)), b]] - self.P[me]
        nrm = np.linalg.norm(to, axis=1, keepdims=True)
        d = np.where((gain[:, None] > 0) & (nrm > 1e-3), to / np.maximum(nrm, 1e-3), 0.0)
        return d.astype(np.float32), np.maximum(gain, 0.0).astype(np.float32)

    # ---- against a belief: the enemy at the points `ens` [n, m] with the weights `p` [n, m] (rows sum to 1 or less)
    def threat_on_me_spread(self, me, ens, p, w_en):
        w = self._w(w_en)
        s = self.seeb
        m = np.asarray(me)[:, None]
        t = (w[:, 0, None] * s[0][ens, m] + w[:, 1, None] * s[1][ens, m] + w[:, 2, None] * s[2][ens, m]) / np.float32(255.0)
        return (t * p).sum(1)

    def threat_on_him_spread(self, me, ens, p, w_me):
        w = self._w(w_me)
        s = self.seeb
        m = np.asarray(me)[:, None]
        t = (w[:, 0, None] * s[0][m, ens] + w[:, 1, None] * s[1][m, ens] + w[:, 2, None] * s[2][m, ens]) / np.float32(255.0)
        return (t * p).sum(1)

    def zone_points(self, per=1):
        """for a belief over the zones: `per` points of each zone (those nearest its middle), [MAX_Z, per], -1 where the map has none"""
        out = np.full((MAX_Z, per), -1, np.int64)
        for z in range(self.k):
            mem = np.nonzero(self.zone == z)[0]
            if len(mem):
                o = np.argsort(np.linalg.norm(self.P[mem] - self.P[mem].mean(0), axis=1))[:per]
                out[z, :len(o)] = mem[o]
                out[z, len(o):] = mem[o[0]]
        return out


def path(name):
    return os.path.join(ROOT, "data", "maps", "space_{}.npz".format(name))


def load(name):
    """the map's table, or None (no file); kept once per process"""
    if name not in _CACHE:
        p = path(name)
        _CACHE[name] = Space(p) if os.path.exists(p) else None
    return _CACHE[name]

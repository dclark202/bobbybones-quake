"""v0.4.0 brain: a map's zones (sim/zones/<map>.json, made by tools/make_zones.py in the system Python). Plain numpy: the
simulator (TRACK_Z's truth columns) and the trainer (the readout's counters) read the same lookup.

    Z = load("bloodrun")         # None if the map has no zones file
    Z.k                      # the map's number of zones (at most MAX_Z)
    Z.locate(pos [n, 3])     # the zone of each place: the 32-unit cell's zone (its nearest walking point, height counted double)
"""
import base64
import json
import os
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_Z = 24                       # the readout's zone outputs (a map's own count masks the rest)
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity",
        "cure", "houseofdecay", "dismemberment")      # the zone_map column's numbers (fixed: a map added goes at the end)


class Zones:
    def __init__(self, d):
        self.map = d["map"]
        self.k = int(d["k"])
        assert 1 <= self.k <= MAX_Z, "{}: {} zones (at most {})".format(self.map, self.k, MAX_Z)
        self.cell = float(d["cell"])
        self.lo = np.array(d["lo"], np.float64)
        self.dims = np.array(d["dims"], np.int64)
        self.grid = np.frombuffer(zlib.decompress(base64.b64decode(d["grid"])), np.int8).reshape(tuple(self.dims)).copy()
        self.centres = np.array(d["centres"], np.float32)
        self.names = list(d.get("names") or [""] * self.k)
        self.node_zone = np.array(d.get("node_zone") or [], np.int64)

    def locate(self, pos):
        c = np.clip(((np.asarray(pos, np.float64).reshape(-1, 3) - self.lo) / self.cell).astype(np.int64), 0, self.dims - 1)
        return self.grid[c[:, 0], c[:, 1], c[:, 2]].astype(np.int64)


_CACHE = {}


def load(name):
    """the map's zones, or None (no file); kept once per process"""
    if name not in _CACHE:
        p = os.path.join(HERE, "zones", name + ".json")
        _CACHE[name] = Zones(json.load(open(p, encoding="utf-8"))) if os.path.exists(p) else None
    return _CACHE[name]

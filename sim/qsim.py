"""Python side of the movement simulator (sim/qsim.dll or qsim.so, built from sim/sim_api.c).

    w = World("data/maps/bloodrun.bsp", n=256)
    w.reset(i, origin, velocity, yaw)
    w.step(moves int8[n,3], angles float32[n,2], msec=25)
    s = w.state()   # float32[n,8]: x y z vx vy vz on_ground yaw

One World per process (the C side keeps one map and global state). Use processes for parallelism.
"""
import ctypes
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "qsim.dll" if sys.platform == "win32" else "libqsim.so")   # not qsim.so: Python would import it
F32 = np.ctypeslib.ndpointer(np.float32, flags="C_CONTIGUOUS")
I8 = np.ctypeslib.ndpointer(np.int8, flags="C_CONTIGUOUS")

# Quake Live duel movement (server cvars, 2026-10-02). Chain jump is off: recorded QL jumps 200 ms apart
# got the plain 275 (sim/validate.py), so pmove_ChainJump does not mean "+110 within 500 ms".
QL_PARAMS = dict(jump_velocity=275.0, auto_hop=1, chain_jump=0, chain_velocity=110.0, chain_ms=500)
Q3_PARAMS = dict(jump_velocity=270.0, auto_hop=0, chain_jump=0, chain_velocity=0.0, chain_ms=0)


def _lib():
    lib = ctypes.CDLL(LIB)
    lib.qsim_load_map.argtypes = [ctypes.c_char_p]
    lib.qsim_error.restype = ctypes.c_char_p
    lib.qsim_entity_string.restype = ctypes.c_char_p
    lib.qsim_params.argtypes = [ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_int]
    lib.qsim_create.argtypes = [ctypes.c_int]
    lib.qsim_reset.argtypes = [ctypes.c_int, F32, F32, ctypes.c_float]
    lib.qsim_set.argtypes = [ctypes.c_int, F32, F32, ctypes.c_float, ctypes.c_int]
    lib.qsim_step.argtypes = [ctypes.c_int, I8, F32, ctypes.c_int]
    lib.qsim_get.argtypes = [ctypes.c_int, F32]
    lib.qsim_rays.argtypes = [ctypes.c_int, F32, ctypes.c_int, F32, ctypes.c_float, F32]
    lib.qsim_rays_each.argtypes = [ctypes.c_int, F32, ctypes.c_int, F32, ctypes.c_float, F32]
    lib.qsim_contents.argtypes = [F32]
    lib.qsim_cluster.argtypes = [F32]
    lib.qsim_trace.argtypes = [F32, F32, F32, F32, F32]
    lib.qsim_world_bounds.argtypes = [F32]
    lib.qsim_knockback.argtypes = [ctypes.c_int, F32, ctypes.c_int]
    lib.qsim_add_trigger.argtypes = [ctypes.c_int, ctypes.c_int, F32, ctypes.c_float]
    return lib


def parse_entities(text):
    """the map's entity lump -> list of dicts (classname, origin, angle, ...)"""
    ents = []
    for block in re.findall(r"\{([^{}]*)\}", text):
        e = dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', block))
        if "origin" in e:
            e["origin"] = tuple(float(v) for v in e["origin"].split())
        ents.append(e)
    return ents


class World:
    def __init__(self, bsp, n=1, params=None):
        self.lib = _lib()
        if self.lib.qsim_load_map(os.path.abspath(bsp).encode()) != 0:
            raise RuntimeError("qsim: " + self.lib.qsim_error().decode())
        self.n = self.lib.qsim_create(n)
        self.set_params(**(params or QL_PARAMS))
        # only what exists in a duel (QL maps tag entities with gametype / not_gametype)
        self.entities = [e for e in parse_entities(self.lib.qsim_entity_string().decode("latin1"))
                         if "duel" not in e.get("not_gametype", "") and
                         ("gametype" not in e or "duel" in e["gametype"])]
        self._out = np.zeros((self.n, 8), np.float32)
        self.triggers = self._add_triggers()

    def _add_triggers(self):
        """jump pads (trigger_push) and teleporters (trigger_teleport) -> simulated after every move"""
        named = {e["targetname"]: e for e in self.entities if "targetname" in e and "origin" in e}
        out = []
        self.lib.qsim_clear_triggers()
        for e in self.entities:
            kind = {"trigger_push": 0, "trigger_teleport": 1}.get(e.get("classname"))
            if kind is None or not e.get("model", "").startswith("*") or e.get("target") not in named:
                continue
            dest = named[e["target"]]
            if self.lib.qsim_add_trigger(int(e["model"][1:]), kind, np.asarray(dest["origin"], np.float32),
                                         float(dest.get("angle", 0))) >= 0:
                out.append((e["classname"], e["model"], dest["origin"]))
        return out

    def trigger_spots(self):
        """(kind, center of the trigger brush, destination) for jump pads (kind 0) and teleporters (kind 1)"""
        if not hasattr(self.lib, "qsim_model_bounds"):
            return []
        self.lib.qsim_model_bounds.argtypes = [ctypes.c_int, F32]
        out = []
        for cls, model, dest in self.triggers:
            b = np.zeros(6, np.float32)
            self.lib.qsim_model_bounds(int(model[1:]), b)
            out.append((0 if cls == "trigger_push" else 1, (b[:3] + b[3:]) / 2.0, np.asarray(dest, np.float32)))
        return out

    def set_params(self, jump_velocity, auto_hop, chain_jump, chain_velocity, chain_ms):
        self.lib.qsim_params(jump_velocity, auto_hop, chain_jump, chain_velocity, chain_ms)

    def spawns(self):
        return [e for e in self.entities if e.get("classname") == "info_player_deathmatch"]

    def items(self):
        return [e for e in self.entities if e.get("classname", "").startswith(("item_", "weapon_", "ammo_"))]

    def reset(self, i, origin, velocity=(0, 0, 0), yaw=0.0):
        self.lib.qsim_reset(i, np.asarray(origin, np.float32), np.asarray(velocity, np.float32), float(yaw))

    def set(self, i, origin, velocity, yaw, command_time):
        self.lib.qsim_set(i, np.asarray(origin, np.float32), np.asarray(velocity, np.float32), float(yaw),
                          int(command_time))

    def step(self, moves, angles, msec=25):
        self.lib.qsim_step(self.n, np.ascontiguousarray(moves, np.int8), np.ascontiguousarray(angles, np.float32), msec)

    def state(self):
        self.lib.qsim_get(self.n, self._out)
        return self._out.copy()

    def rays(self, origins, dirs, maxdist):
        origins = np.ascontiguousarray(origins, np.float32)
        dirs = np.ascontiguousarray(dirs, np.float32)
        out = np.zeros((len(origins), len(dirs)), np.float32)
        self.lib.qsim_rays(len(origins), origins, len(dirs), dirs, float(maxdist), out)
        return out

    def rays_each(self, origins, dirs, maxdist):
        """origins n x 3, dirs n x k x 3 (per-origin directions) -> n x k hit fractions"""
        origins = np.ascontiguousarray(origins, np.float32)
        dirs = np.ascontiguousarray(dirs, np.float32)
        out = np.zeros(dirs.shape[:2], np.float32)
        self.lib.qsim_rays_each(len(origins), origins, dirs.shape[1], dirs, float(maxdist), out)
        return out

    PLAYER_MINS = np.array([-15, -15, -24], np.float32)
    PLAYER_MAXS = np.array([15, 15, 32], np.float32)

    def trace(self, start, end, mins=None, maxs=None):
        """box trace -> dict(fraction, endpos, normal, startsolid, allsolid); default box = a point"""
        out = np.zeros(9, np.float32)
        z = np.zeros(3, np.float32)
        self.lib.qsim_trace(np.asarray(start, np.float32), np.asarray(end, np.float32),
                            z if mins is None else np.asarray(mins, np.float32),
                            z if maxs is None else np.asarray(maxs, np.float32), out)
        return dict(fraction=float(out[0]), endpos=out[1:4].copy(), normal=out[4:7].copy(),
                    startsolid=bool(out[7]), allsolid=bool(out[8]))

    def bounds(self):
        out = np.zeros(6, np.float32)
        self.lib.qsim_world_bounds(out)
        return out[:3], out[3:]

    def knockback(self, i, kick, knockback):
        self.lib.qsim_knockback(i, np.asarray(kick, np.float32), int(knockback))

    def cluster(self, point):
        """-1 if the point is outside the playable map"""
        return self.lib.qsim_cluster(np.asarray(point, np.float32))

    def contents(self, point):
        return self.lib.qsim_contents(np.asarray(point, np.float32))

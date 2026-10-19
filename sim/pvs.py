"""A map's potentially-visible set (PVS), read from its .bsp in numpy: what a Quake 3 / Quake Live server sends a client.

    V = Vis("data/maps/bloodrun.bsp")
    c = V.clusters(points)              # (N,) the cluster of each point's leaf, -1 outside the map (in a wall, the void)
    V.sees(ca, cb)                      # (N,) bool: cluster cb is in the PVS of cluster ca (the server's test)
    V.sent(eye, pos)                    # (N,) bool: an entity at pos (a player's box) is sent to a client whose eye is at eye

The server (ioquake3 `SV_AddEntitiesVisibleFromPoint`) sends a client an entity, and so the entity's events (steps,
jumps, shots, pickups: everything the client can play a sound for), only when one of the clusters the entity's box
touches is in the PVS of the cluster of the client's eye. (It also tests the map's areas, which only doors that are
shut separate: the simulator's maps have none that are shut.) A cluster with no vis data sees everything.

The box's clusters are taken at its centre and its eight corners (the server takes every leaf the box touches; a
player's box is 30 x 30 x 56 units, much smaller than a cluster). Leaf lookup is the game's own descent of the BSP
tree (`CM_PointLeafnum_r`), the same as sim/qsim's `cluster()`.
"""
import struct

import numpy as np

LUMP_PLANES, LUMP_NODES, LUMP_LEAFS, LUMP_VIS = 2, 3, 4, 16
BOX_MINS = np.array([-15.0, -15.0, -24.0], np.float32)       # a standing player's box (bg_pmove.c)
BOX_MAXS = np.array([15.0, 15.0, 32.0], np.float32)


class Vis:
    def __init__(self, bsp):
        raw = open(bsp, "rb").read()
        assert raw[:4] == b"IBSP", bsp
        lumps = [struct.unpack_from("<ii", raw, 8 + 8 * k) for k in range(17)]

        def lump(k):
            o, n = lumps[k]
            return raw[o:o + n]
        pl = np.frombuffer(lump(LUMP_PLANES), np.float32).reshape(-1, 4)
        self.pn, self.pd = pl[:, :3].astype(np.float64), pl[:, 3].astype(np.float64)
        nd = np.frombuffer(lump(LUMP_NODES), np.int32).reshape(-1, 9)
        self.nplane, self.nchild = nd[:, 0].astype(np.int64), nd[:, 1:3].astype(np.int64)
        lf = np.frombuffer(lump(LUMP_LEAFS), np.int32).reshape(-1, 12)
        self.lcluster = lf[:, 0].astype(np.int64)
        vis = lump(LUMP_VIS)
        if len(vis) >= 8:
            self.nclusters, self.cbytes = struct.unpack_from("<ii", vis, 0)
            self.vis = np.frombuffer(vis[8:8 + self.nclusters * self.cbytes], np.uint8).reshape(self.nclusters, self.cbytes)
        else:                                                # (no vis data: the game sends everything)
            self.nclusters, self.cbytes, self.vis = 0, 0, None
        self._cache = {}

    def leaves(self, points):
        """(N, 3) points -> (N,) leaf numbers (CM_PointLeafnum)"""
        p = np.asarray(points, np.float64).reshape(-1, 3)
        node = np.zeros(len(p), np.int64)
        live = node >= 0
        while live.any():
            i = np.nonzero(live)[0]
            nd = node[i]
            pk = self.nplane[nd]
            d = (self.pn[pk] * p[i]).sum(1) - self.pd[pk]
            node[i] = np.where(d < 0, self.nchild[nd, 1], self.nchild[nd, 0])
            live[i] = node[i] >= 0
        return -1 - node

    def clusters(self, points):
        return self.lcluster[self.leaves(points)]

    def sees(self, ca, cb):
        """cluster cb in the PVS of cluster ca (elementwise; -1 on either side: not sent, as the server's test)"""
        ca, cb = np.broadcast_arrays(np.asarray(ca, np.int64), np.asarray(cb, np.int64))
        ok = (ca >= 0) & (cb >= 0)
        if self.vis is None:
            return ok
        a, b = np.where(ok, ca, 0), np.where(ok, cb, 0)
        return ok & ((self.vis[a, b >> 3] >> (b & 7)) & 1).astype(bool)

    def box_clusters(self, pos, mins=BOX_MINS, maxs=BOX_MAXS):
        """(N, 3) box origins -> (N, 9) clusters at the centre and the corners (-1 where a corner is in a wall)"""
        pos = np.asarray(pos, np.float32).reshape(-1, 3)
        corners = np.array([[x, y, z] for x in (mins[0], maxs[0]) for y in (mins[1], maxs[1]) for z in (mins[2], maxs[2])],
                           np.float32)
        pts = np.concatenate([pos[:, None, :] + ((mins + maxs) / 2.0)[None, None, :], pos[:, None, :] + corners[None]], 1)
        return self.clusters(pts.reshape(-1, 3)).reshape(len(pos), 9)

    def sent(self, eye, pos, box=True):
        """(N, 3) eyes, (N, 3) entity origins -> (N,) the server sends that entity (and its sounds) to that client.
        box False: the entity is a point (a temporary event at a place, an item)"""
        ce = self.clusters(eye)
        if not box:
            return self.sees(ce, self.clusters(pos))
        cb = self.box_clusters(pos)
        return self.sees(ce[:, None], cb).any(1)

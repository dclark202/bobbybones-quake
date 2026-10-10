"""The pros' jumps in training drawn from above, a picture and a list a map, for the owner to say which to keep (BACKLOG B-204).

    python tools/draw_gaps.py [--map aerowalk,bloodrun] [--panels auto|1|2]       (the system Python: it needs matplotlib)
        -> docs/design/jumps/<map>.png, <map>.md, and README.md: every map's picture and list on one page

Reads sim/pro_gaps/<map>.json (tools/pro_gaps.py), the map itself (data/maps/<map>.bsp) and its walking map
(data/maps/nav_<map>_sim.json: where a player can stand). No simulator is needed. The floors are the map's own faces
that look up and that a player stands on or beside, seen from above through the roofs: dark = low, light = high, a line
wherever the height steps, nothing where a wall or a pillar stands, lava, slime and water tinted. The items are those
a duel has.

On the floors the big items at their places, and every jump in training as an arrow from its take-off, where its number
sits in a circle, to its landing:
    red     a walker cannot make it                    } seen 20 times or more
    orange  a walker is a second or more slower        }
    blue    a walker just makes it, from the very edge: seen 30 times or more
    green   up a ledge with stairs or a way round beside it: the ones the owner named (LEDGES), seen 30 times or more
An entry of the lists that says "use" is in or out by that, however often it was seen (grey if there was a way beside
it). The width of a line says how often the pros jump it (times an hour). The arrows are bent a little, each to its own
right, so that a jump and the same jump the other way lie beside each other. Where arrows of different floors lie over
one another the picture has two panels: the map's middle height (the mean of the lowest and the highest standing spot
that a player gets to) parts them, moved to the nearest gap between the heights that jumps start from.

The list has a row a drawn jump: its number, its name (from where to where, by the nearest big items; "past" an item
that is more than 250 units off), the kind of jump by the speed it needs (running jump, circle jump, strafe jumps; a
ledge jump) with the height it gains or drops, and the times an hour. No player names are read or written.
"""
import argparse
import json
import os
import re

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = "aerowalk,bloodrun,lostworld,sinister,furiousheights,battleforged,campgrounds"
NAMES = dict(aerowalk="Aerowalk", bloodrun="Blood Run", lostworld="Lost World", sinister="Sinister",
             furiousheights="Furious Heights", battleforged="Battleforged", campgrounds="Campgrounds")
N_HARD, N_EDGE, N_LEDGE = 20, 30, 30                           # in training unless an entry says otherwise: seen this often ("cannot", "slower"; "just makes it"; a named ledge)
LEDGES = {("bloodrun", 26)}                                    # the jumps "up a ledge" the owner named: (map, id)
SPEED_RUN, SPEED_CIRCLE = 340, 440                             # speed needed up to here: a running jump, a circle jump; above: strafe jumps
SPEED_LINE = "Speed needed: running jump up to {} units a second, circle jump up to {}, strafe jumps above.".format(SPEED_RUN, SPEED_CIRCLE)
KINDS = ("cannot", "slower", "just makes it", "up a ledge", "a way beside it")       # the lists' "walker", the most telling first
COLOR = {"cannot": "#d81e1e", "slower": "#f39200", "just makes it": "#1565c8", "up a ledge": "#1f9a48",
         "a way beside it": "#6e6e6e"}
SAYS = {"cannot": "a walker cannot make it", "slower": "a walker is a second or more slower",
        "just makes it": "a walker just makes it, from the very edge", "up a ledge": "up a ledge, stairs or a way round beside it",
        "a way beside it": "a way beside it"}
ITEMS = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA",
         "weapon_rocketlauncher": "RL", "weapon_railgun": "RG", "weapon_lightning": "LG", "weapon_grenadelauncher": "GL",
         "weapon_plasmagun": "PG", "weapon_shotgun": "SG", "weapon_hmg": "HMG"}
FEET = 24.0                                                    # a standing spot and a jump's ends are his origin: this far above his feet
CELL = 2.0                                                     # the floor picture's grid, in units
STEP = 12.0                                                    # a line where the floor's height changes by more than this between two cells
RAD = 0.13                                                     # how far an arrow is bent (matplotlib's arc3)
C_SOLID, C_LAVA, C_SLIME, C_WATER, C_FOG = 1, 8, 16, 32, 64    # a shader's contents
SURF_SKY, SURF_NODRAW = 0x4, 0x80
TINT = {C_LAVA: (0.97, 0.76, 0.60), C_SLIME: (0.76, 0.89, 0.58), C_WATER: (0.70, 0.89, 0.93)}      # pale: the arrows keep the strong colours
WET = {C_LAVA: "lava", C_SLIME: "slime", C_WATER: "water"}
LOW, HIGH = np.array([0.47, 0.48, 0.50]), np.array([0.94, 0.94, 0.93])       # the floors' greys, lowest and highest
SHADER = np.dtype([("name", "S64"), ("flags", "<i4"), ("contents", "<i4")])
PLANE = np.dtype([("normal", "<f4", 3), ("dist", "<f4")])
NODE = np.dtype([("plane", "<i4"), ("child", "<i4", 2), ("mins", "<i4", 3), ("maxs", "<i4", 3)])
LEAF = np.dtype([("cluster", "<i4"), ("area", "<i4"), ("mins", "<i4", 3), ("maxs", "<i4", 3), ("face", "<i4"), ("nface", "<i4"),
                 ("brush", "<i4"), ("nbrush", "<i4")])
BRUSH = np.dtype([("side", "<i4"), ("nside", "<i4"), ("shader", "<i4")])
SIDE = np.dtype([("plane", "<i4"), ("shader", "<i4")])
MODEL = np.dtype([("mins", "<f4", 3), ("maxs", "<f4", 3), ("face", "<i4"), ("nface", "<i4"), ("brush", "<i4"), ("nbrush", "<i4")])
VERT = np.dtype([("pos", "<f4", 3), ("st", "<f4", 4), ("normal", "<f4", 3), ("color", "u1", 4)])
FACE = np.dtype([("shader", "<i4"), ("fog", "<i4"), ("type", "<i4"), ("vert", "<i4"), ("nvert", "<i4"), ("mesh", "<i4"),
                 ("nmesh", "<i4"), ("lm", "<i4", 5), ("lm_org", "<f4", 3), ("lm_vec", "<f4", 6), ("normal", "<f4", 3),
                 ("size", "<i4", 2)])


# ---- the map: its entities and its floors, straight from the file

def read_bsp(path):
    """a Quake Live map file (IBSP) -> its entity text and the lumps the floors are made of"""
    b = open(path, "rb").read()
    if b[:4] != b"IBSP":
        raise ValueError("not a Quake map: " + os.path.basename(path))
    d = np.frombuffer(b, "<i4", 34, 8).reshape(17, 2)

    def lump(i, dt):
        return np.frombuffer(b, dt, d[i, 1] // np.dtype(dt).itemsize, d[i, 0])
    return dict(text=b[d[0, 0]:d[0, 0] + d[0, 1]].split(b"\0")[0].decode("latin1"), shaders=lump(1, SHADER),
                planes=lump(2, PLANE), nodes=lump(3, NODE), leafs=lump(4, LEAF), leafbrushes=lump(6, "<i4"),
                models=lump(7, MODEL), brushes=lump(8, BRUSH), sides=lump(9, SIDE), verts=lump(10, VERT),
                mesh=lump(11, "<i4"), faces=lump(13, FACE))


def air(bsp, pts):
    """for each point: is it inside the map (in a leaf the game draws, not outside its hull), and is it inside a solid
    brush (a wall, a pillar). The map's own tree and brushes, read as the game's collision reads them."""
    pts = np.asarray(pts, np.float64).reshape(-1, 3)
    at = np.zeros(len(pts), np.int64)
    go = np.arange(len(pts))
    while len(go):                                             # down the tree to each point's leaf
        nd = bsp["nodes"][at[go]]
        pl = bsp["planes"][nd["plane"]]
        front = (pts[go] * pl["normal"]).sum(1) >= pl["dist"]
        at[go] = np.where(front, nd["child"][:, 0], nd["child"][:, 1])
        go = go[at[go] >= 0]
    leaf = -1 - at
    inside = bsp["leafs"]["cluster"][leaf] >= 0
    solid = np.zeros(len(pts), bool)
    is_solid = (bsp["shaders"]["contents"][bsp["brushes"]["shader"]] & C_SOLID) != 0
    order = np.argsort(leaf, kind="stable")
    for grp in np.split(order, np.flatnonzero(np.diff(leaf[order])) + 1):
        if not len(grp):
            continue
        L = bsp["leafs"][leaf[grp[0]]]
        for b in bsp["leafbrushes"][L["brush"]:L["brush"] + L["nbrush"]]:
            if is_solid[b]:
                br = bsp["brushes"][b]
                pl = bsp["planes"][bsp["sides"]["plane"][br["side"]:br["side"] + br["nside"]]]
                solid[grp[(pts[grp] @ pl["normal"].T.astype(np.float64) <= pl["dist"]).all(1)]] = True
    return inside, solid


def air_cells(bsp, H, lo, above):
    """air() for the point `above` the height of every cell of a height picture; both False where the picture has
    nothing. One look-up for a block of two by two cells (enough for a wall), one of its own for a cell whose height
    is not the block's (the edge of a floor over another)."""
    ny, nx = H.shape
    Hc = H[::2, ::2]
    block = np.repeat(np.repeat(Hc, 2, 0), 2, 1)[:ny, :nx]
    has = np.isfinite(H)
    with np.errstate(invalid="ignore"):
        own = has & ~(np.abs(H - block) < 4.0)
    j, i = np.nonzero(np.isfinite(Hc))
    oj, oi = np.nonzero(own)
    got = air(bsp, np.concatenate([
        np.stack([lo[0] + (2 * i + 1.0) * CELL, lo[1] + (2 * j + 1.0) * CELL, Hc[j, i] + above], 1),
        np.stack([lo[0] + (oi + 0.5) * CELL, lo[1] + (oj + 0.5) * CELL, H[oj, oi] + above], 1)]))
    out = []
    for v in got:
        c = np.zeros(Hc.shape, bool)
        c[j, i] = v[:len(j)]
        full = np.repeat(np.repeat(c, 2, 0), 2, 1)[:ny, :nx] & has
        full[oj, oi] = v[len(j):]
        out.append(full)
    return out


def duel_entities(text):
    """the map's entities as a duel has them (the rule of sim/qsim.py's World), the origin as numbers"""
    out = []
    for block in re.findall(r"\{([^{}]*)\}", text):
        e = dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', block))
        if "duel" in e.get("not_gametype", "") or ("gametype" in e and "duel" not in e["gametype"]) \
                or e.get("notfree", "0").strip() not in ("", "0"):
            continue
        if "origin" in e:
            e["origin"] = tuple(float(v) for v in e["origin"].split())
        out.append(e)
    return out


def live_spots(nav, ents, jumps):
    """the standing spots of the walking map that a player gets to: from the spawn points over its links and over the
    pros' jumps (it also has spots on roofs and on ledges outside that nobody reaches: they are not floor to draw)"""
    nodes = np.array(nav["nodes"], np.float64).reshape(-1, 3)
    starts = [e["origin"] for e in ents if e.get("classname") == "info_player_deathmatch" and "origin" in e]
    if not len(nodes) or not starts:
        return nodes
    links = [[] for _ in nodes]
    for e in nav.get("edges", []):
        links[e[0]].append(e[1])
    for j in jumps:
        a, b = j.get("node_a", -1), j.get("node_b", -1)
        if 0 <= a < len(nodes) and 0 <= b < len(nodes):
            links[a].append(b)
    todo = sorted({int(np.linalg.norm(nodes - np.array(s), axis=1).argmin()) for s in starts})
    seen = np.zeros(len(nodes), bool)
    seen[todo] = True
    while todo:
        for b in links[todo.pop()]:
            if not seen[b]:
                seen[b] = True
                todo.append(b)
    return nodes[seen]


def up_triangles(bsp, model=0, origin=(0.0, 0.0, 0.0)):
    """a model's triangles that face up, no steeper than a player walks on (n x 3 x 3), what each is (0 a floor, or
    the contents bit of the liquid whose surface it is) and the face it is a piece of (-1: of a mesh, where every
    triangle stands for itself)"""
    V, N, MV = bsp["verts"]["pos"], bsp["verts"]["normal"], bsp["mesh"]
    m = bsp["models"][model]
    tris, kinds, faces = [np.zeros((0, 3, 3), np.float32)], [np.zeros(0, np.int64)], [np.zeros(0, np.int64)]
    for fi in range(int(m["face"]), int(m["face"] + m["nface"])):
        f = bsp["faces"][fi]
        sh = bsp["shaders"][f["shader"]]
        if (sh["flags"] & (SURF_SKY | SURF_NODRAW)) or (sh["contents"] & C_FOG):
            continue
        if f["type"] in (1, 3):                                # a flat face, a mesh: triangles by the index list
            idx = (f["vert"] + MV[f["mesh"]:f["mesh"] + f["nmesh"] // 3 * 3]).reshape(-1, 3)
        elif f["type"] == 2:                                   # a curved patch: the grid of its control points is near enough
            w, h = int(f["size"][0]), int(f["size"][1])
            g = (f["vert"] + np.arange(w * h)).reshape(h, w)
            idx = np.concatenate([np.stack([g[:-1, :-1], g[:-1, 1:], g[1:, 1:]], -1).reshape(-1, 3),
                                  np.stack([g[:-1, :-1], g[1:, 1:], g[1:, :-1]], -1).reshape(-1, 3)])
        else:
            continue
        t = V[idx]
        c = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ln = np.linalg.norm(c, axis=1)
        up = (ln > 1e-3) & (np.abs(c[:, 2]) > 0.7 * ln) & (N[idx][:, :, 2].sum(1) > 0.0)
        tris.append(t[up] + np.asarray(origin, np.float32))
        kinds.append(np.full(int(up.sum()), int(sh["contents"]) & (C_LAVA | C_SLIME | C_WATER), np.int64))
        faces.append(np.full(int(up.sum()), -1 if f["type"] == 3 else fi, np.int64))
    return np.concatenate(tris), np.concatenate(kinds), np.concatenate(faces)


def map_triangles(bsp, ents):
    """the world's up-facing triangles and those of its solid pieces that are models of their own (a bridge, a
    platform at rest), as a duel has them"""
    tris, kinds, faces = up_triangles(bsp)
    for e in ents:
        cls, mod = e.get("classname", ""), e.get("model", "")
        if cls.startswith("func_") and cls not in ("func_timer", "func_group", "func_door") and mod[:1] == "*" \
                and mod[1:].isdigit() and int(mod[1:]) < len(bsp["models"]):
            t, k, f = up_triangles(bsp, int(mod[1:]), e.get("origin", (0.0, 0.0, 0.0)))
            tris, kinds, faces = np.concatenate([tris, t]), np.concatenate([kinds, k]), np.concatenate([faces, f])
    return tris, kinds, faces


def walkable(tri, face, feet, r=80.0, dz=44.0):
    """which triangles are floor that a player stands on or beside: a point of it lies within r (level) and dz (height)
    of where feet stand, or feet stand right on it; and with one triangle of a face the whole face (half a floor is
    no floor). Roofs, lamps and the scenery outside are left out by this."""
    keep = np.zeros(len(tri), bool)
    if not len(tri) or not len(feet):
        return keep
    a, b, c = tri[:, 0].astype(np.float64), tri[:, 1].astype(np.float64), tri[:, 2].astype(np.float64)
    m = (a + b + c) / 3.0
    S = np.stack([a, b, c, m, (a + b) / 2, (b + c) / 2, (c + a) / 2, (a + m) / 2, (b + m) / 2, (c + m) / 2], 1)
    for i in range(0, len(tri), 128):
        d = S[i:i + 128].reshape(-1, 1, 3) - feet[None]
        ok = (np.abs(d[:, :, 2]) < dz) & (d[:, :, 0] ** 2 + d[:, :, 1] ** 2 < r * r)
        keep[i:i + 128] = ok.any(1).reshape(-1, S.shape[1]).any(1)
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    flat = np.abs(den) > 1e-6
    den = np.where(flat, den, 1.0)
    for i in range(0, len(feet), 256):                         # a big floor whose corners are all far from him
        p = feet[i:i + 256, None, :]
        l1 = ((b[:, 1] - c[:, 1]) * (p[:, :, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (p[:, :, 1] - c[:, 1])) / den
        l2 = ((c[:, 1] - a[:, 1]) * (p[:, :, 0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (p[:, :, 1] - c[:, 1])) / den
        l3 = 1.0 - l1 - l2
        z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
        keep |= ((l1 >= 0) & (l2 >= 0) & (l3 >= 0) & flat & (np.abs(z - p[:, :, 2]) < dz)).any(0)
    whole = np.unique(face[keep & (face >= 0)])
    return keep | np.isin(face, whole)


def raster(tri, lo, shape, under=None):
    """the highest of the triangles over each cell of the grid (rows y, columns x; -inf where there is none).
    under: a height for each cell, only what lies below it counts (inf: the cell is not asked for)"""
    H = np.full(shape, -np.inf, np.float32)
    ny, nx = shape
    if under is not None:                                      # how many asked-for cells in any box, by four look-ups
        S = np.zeros((ny + 1, nx + 1), np.int64)
        S[1:, 1:] = np.isfinite(under).cumsum(0).cumsum(1)
    for t in tri.astype(np.float64):
        i0, i1 = int((t[:, 0].min() - lo[0]) // CELL), int((t[:, 0].max() - lo[0]) // CELL) + 1
        j0, j1 = int((t[:, 1].min() - lo[1]) // CELL), int((t[:, 1].max() - lo[1]) // CELL) + 1
        i0, j0, i1, j1 = max(i0, 0), max(j0, 0), min(i1, nx), min(j1, ny)
        if i0 >= i1 or j0 >= j1 or (under is not None and S[j1, i1] - S[j0, i1] - S[j1, i0] + S[j0, i0] == 0):
            continue
        (xa, ya, za), (xb, yb, zb), (xc, yc, zc) = t
        den = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
        if abs(den) < 1e-9:
            continue
        X = lo[0] + (np.arange(i0, i1) + 0.5) * CELL - xc
        Y = (lo[1] + (np.arange(j0, j1) + 0.5) * CELL - yc)[:, None]
        l1 = ((yb - yc) * X + (xc - xb) * Y) / den
        l2 = ((yc - ya) * X + (xa - xc) * Y) / den
        l3 = 1.0 - l1 - l2
        z = l1 * za + l2 * zb + l3 * zc
        ok = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
        if under is not None:
            ok &= z < under[j0:j1, i0:i1]
        np.maximum(H[j0:j1, i0:i1], np.where(ok, z, -np.inf), out=H[j0:j1, i0:i1])
    return H


def floors_seen(bsp, tri, lo, shape, feet):
    """the height of the highest floor over each cell, as someone above the map sees it who looks through roofs: the
    triangles' picture, without the pieces that are no floor. A face also runs on under a thin wall into the nothing
    behind it: there the floor under it shows instead. Where a wall or a pillar stands on a floor there is none.
    Returns the picture and how many standing spots had no face under them (see stamp)."""
    H = raster(tri, lo, shape)
    for _ in range(3):
        inside, solid = air_cells(bsp, H, lo, 30.0)
        ghost = np.isfinite(H) & ~inside & ~solid
        if not ghost.any():
            break
        H = np.where(ghost, raster(tri, lo, shape, np.where(ghost, H - 8.0, np.inf)), H)
    n = stamp(H, lo, feet)
    inside, solid = air_cells(bsp, H, lo, 30.0)
    H[~inside | solid] = -np.inf
    return H, n


def stamp(H, lo, feet, r=22.0, box=16.0):
    """a standing spot whose floor the map's faces do not show (an unseen clip brush carries him): a round piece.
    Not where any floor is drawn within his box: he also stands with his middle past a ledge's edge."""
    ny, nx = H.shape
    k, b = int(r // CELL), int(box // CELL)
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    disc = xx * xx + yy * yy <= k * k
    todo = []
    for p in feet:
        i, j = int((p[0] - lo[0]) // CELL), int((p[1] - lo[1]) // CELL)
        if k <= i < nx - k and k <= j < ny - k and H[j - b:j + b + 1, i - b:i + b + 1].max() <= p[2] - 40.0:
            todo.append((i, j, p[2]))
    for i, j, z in todo:                                       # after the looking: a piece is no floor for the next spot
        sub = H[j - k:j + k + 1, i - k:i + k + 1]
        sub[disc] = np.maximum(sub[disc], z)
    return len(todo)


def shade(H, liquids, zlo, zhi):
    """the floors' heights as a picture: dark low, light high, a dark line on the upper side of every step and where
    the floor ends, the liquids tinted, nothing where there is no floor"""
    has = np.isfinite(H)
    Hf = np.where(has, H, -1e9)
    t = np.clip((Hf - zlo) / max(1.0, zhi - zlo), 0.0, 1.0)[:, :, None]
    rgb = LOW + (HIGH - LOW) * t
    edge = np.zeros(H.shape, bool)
    dx, dy = Hf[:, 1:] - Hf[:, :-1], Hf[1:, :] - Hf[:-1, :]
    edge[:, 1:] |= dx > STEP
    edge[:, :-1] |= dx < -STEP
    edge[1:, :] |= dy > STEP
    edge[:-1, :] |= dy < -STEP
    rgb[edge & has] *= 0.42
    alpha = has.astype(np.float64)
    seen = []
    for kind, L in liquids.items():
        wet = np.isfinite(L) & (L > Hf - 2.0)
        if wet.sum() * CELL * CELL >= 1000.0:                  # worth a word in the legend
            seen.append(kind)
        inner = wet.copy()                                     # a cell with the liquid on all four sides
        inner[1:, :] &= wet[:-1, :]
        inner[:-1, :] &= wet[1:, :]
        inner[:, 1:] &= wet[:, :-1]
        inner[:, :-1] &= wet[:, 1:]
        rgb[wet] = np.array(TINT[kind])
        rgb[wet & ~inner] = 0.68 * np.array(TINT[kind])        # its shore: a line
        alpha[wet] = 1.0
    return np.concatenate([rgb, alpha[:, :, None]], 2), seen


# ---- the jumps

def chosen(jumps, mp=""):
    """the entries that are drawn: the jumps in training, the most frequent first within each kind. An entry that says
    "use" is in or out by that; one that does not is in when a walker cannot make it or is slower and it was seen
    N_HARD times, or a walker just makes it and it was seen N_EDGE times; and the ledge jumps the owner named."""
    out = []
    for i, j in enumerate(jumps):
        j.setdefault("id", i + 1)
        k, n, use = j["walker"], j["n"], j.get("use")
        if use is False or k not in KINDS:
            continue
        if use is True or (k in ("cannot", "slower") and n >= N_HARD) or (k == "just makes it" and n >= N_EDGE) \
                or (k == "up a ledge" and n >= N_LEDGE and (mp, j["id"]) in LEDGES):
            out.append(j)
    return sorted(out, key=lambda j: (KINDS.index(j["walker"]), -j["n"]))


def bent(a, b, rad=RAD, n=None):
    """the points of the arrow from a to b as matplotlib's arc3 draws it: bent to its own right"""
    a, b = np.asarray(a, np.float64)[:2], np.asarray(b, np.float64)[:2]
    d = b - a
    c = (a + b) / 2.0 + rad * np.array([d[1], -d[0]])
    t = np.linspace(0.0, 1.0, n or max(8, int(np.hypot(d[0], d[1]) / 6.0)))[:, None]
    return (1 - t) ** 2 * a + 2 * t * (1 - t) * c + t ** 2 * b


def split_height(z, mid, gap=64.0):
    """the height that parts the jumps into an upper and a lower picture: the middle of the gap between take-off
    heights (gap units or more) nearest to the map's middle height; None when they are all of one floor"""
    z = np.unique(np.asarray(z, np.float64))
    k = np.nonzero(np.diff(z) >= gap)[0]
    if not len(k):
        return None
    c = (z[k] + z[k + 1]) / 2.0
    return float(c[np.abs(c - mid).argmin()])


def in_the_way(jumps, split, H, lo):
    """how many of the lower floors' jumps would be hard to read in one picture: an arrow of the upper floors lies over
    them (within 30 units), or one of their ends is under an upper floor"""
    up = [bent(j["take_off"], j["landing"]) for j in jumps if j["take_off"][2] >= split]
    n = 0
    for j in jumps:
        if j["take_off"][2] >= split:
            continue
        cv = bent(j["take_off"], j["landing"])
        over = any(np.linalg.norm(cv[:, None] - u[None], axis=2).min() < 30.0 for u in up)
        under = False
        for p in (j["take_off"], j["landing"]):
            i, k = int((p[0] - lo[0]) // CELL), int((p[1] - lo[1]) // CELL)
            under |= 0 <= k < H.shape[0] and 0 <= i < H.shape[1] and H[k, i] > p[2] - FEET + 90.0
        n += bool(over or under)
    return n


def width(j):
    """an arrow's line width in points: by how often the pros jump it"""
    return float(np.clip(1.0 + 0.95 * np.sqrt(j["per_hour"]), 1.7, 6.6))


def end_says(text, point, items):
    """one end of a jump in words, from the list's "LG (74)": "LG"; over 250 units from it "past LG"; no item near
    "open floor". A yellow armor by the picture's name for it (the second of a map is YA2)."""
    m = re.match(r"\s*(\S+)\s*\((\d+)\)", text or "")
    if not m:
        return "open floor"
    lab = m.group(1)
    ya = [(n, p) for n, p in items if n.startswith("YA")]
    if lab == "YA" and ya:
        lab = min(ya, key=lambda it: float(np.linalg.norm(np.subtract(it[1], point))))[0]
    return ("past " if int(m.group(2)) > 250 else "") + lab


def heading(j):
    """which way a jump heads on the picture: north = +y, east = +x"""
    way = ("east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east")
    turn = np.degrees(np.arctan2(j["landing"][1] - j["take_off"][1], j["landing"][0] - j["take_off"][0]))
    return way[int(round(turn / 45.0)) % 8]


def names_say(rows, items):
    """the jumps' names: where from, where to; which way it heads where both ends have the same words, and where two
    jumps of the map would have one name"""
    ends = [(end_says(j.get("near_take_off"), j["take_off"], items), end_says(j.get("near_landing"), j["landing"], items))
            for j in rows]
    plain = ["{} to {}".format(a, b) for a, b in ends]
    return [p + (", heading " + heading(j) if a == b or plain.count(p) > 1 else "") for j, (a, b), p in zip(rows, ends, plain)]


def type_says(j):
    """the kind of jump it takes, by the speed it needs and the height it gains or drops"""
    if j["walker"] == "up a ledge":
        return "ledge jump (up {})".format(j["rise"])
    s = j["speed_needed"]
    says = "running jump" if s <= SPEED_RUN else "circle jump" if s <= SPEED_CIRCLE else "strafe jumps (run-up)"
    if j["rise"] >= 30:
        says += ", onto a ledge {} higher".format(j["rise"])
    elif j["rise"] <= -60:
        says += ", {} down".format(-j["rise"])
    return says


def same_jump(jumps, near=110.0):
    """pairs of ids whose take-offs and whose landings lie within `near` of each other: one jump listed twice"""
    out = []
    for a in range(len(jumps)):
        for b in range(a + 1, len(jumps)):
            ja, jb = jumps[a], jumps[b]
            if np.linalg.norm(np.subtract(ja["take_off"], jb["take_off"])) < near and \
                    np.linalg.norm(np.subtract(ja["landing"], jb["landing"])) < near:
                out.append((ja["id"], jb["id"]))
    return out


# ---- labels: a free place for each among the arrows (all in pixels)

class Places:
    def __init__(self, pts, frame):
        self.pts, self.frame = np.asarray(pts, np.float64).reshape(-1, 2), frame      # the arrows' points; the picture's box
        self.marks, self.boxes = np.zeros((0, 2)), []                                 # the items' spots; the labels there

    def cost(self, c, w, h, lines=25.0):
        x0, y0, x1, y1 = c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2
        v = 1000.0 * sum(1 for b in self.boxes if x0 < b[2] + 3 and b[0] - 3 < x1 and y0 < b[3] + 3 and b[1] - 3 < y1)
        for pts, each in ((self.pts, lines), (self.marks, 300.0)):
            v += each * int(((pts[:, 0] > x0 - 3) & (pts[:, 0] < x1 + 3) & (pts[:, 1] > y0 - 3) & (pts[:, 1] < y1 + 3)).sum())
        f = self.frame
        return v + (4000.0 if x0 < f[0] + 2 or y0 < f[1] + 2 or x1 > f[2] - 2 or y1 > f[3] - 2 else 0.0)

    def take(self, c, w, h):
        self.boxes.append((c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2))

    def beside_point(self, a, w, h):
        """an item's name: right beside its spot, on the side that is free"""
        best = None
        for k, (ux, uy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))):
            for far in (0.0, 16.0, 34.0):
                c = np.array([a[0] + ux * (w / 2 + 7 + far), a[1] + uy * (h / 2 + 7 + far)])
                v = self.cost(c, w, h) + 1.5 * k + 0.8 * far
                if best is None or v < best[0]:
                    best = (v, c, far)
        self.take(best[1], w, h)
        return best[1], best[2] > 0.0

    def on_point(self, a, w, h):
        """a jump's number: on its take-off, or right beside it where another number or an item's spot is already"""
        best = None
        for far in (0.0, 1.05, 1.6, 2.3, 3.2):
            for k, (ux, uy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))):
                r = far * (0.75 if ux and uy else 1.0)
                c = np.array([a[0] + ux * r * w, a[1] + uy * r * h])
                v = self.cost(c, w, h, lines=0.0) + 40.0 * far + 0.5 * k
                if best is None or v < best[0]:
                    best = (v, c, far)
                if far == 0.0:
                    break
        self.take(best[1], w, h)
        return best[1], best[2] > 0.0


# ---- the picture and the table

def draw(mp, out_dir, panels="auto", dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.patheffects as pe
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch, Patch
    from matplotlib.textpath import TextPath
    from matplotlib.ticker import MultipleLocator

    src = os.path.join(ROOT, "sim", "pro_gaps", mp + ".json")
    bsp_path = os.path.join(ROOT, "data", "maps", mp + ".bsp")
    nav_path = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    for p in (src, bsp_path, nav_path):
        if not os.path.exists(p):
            print("{}: {} is not there".format(mp, os.path.relpath(p, ROOT).replace("\\", "/")), flush=True)
            return None
    try:
        gaps = json.load(open(src))
    except ValueError as e:                                    # half written: tools/pro_gaps.py is at it
        print("{}: sim/pro_gaps/{}.json cannot be read yet ({})".format(mp, mp, e), flush=True)
        return None
    jumps = chosen(gaps["jumps"], mp)
    count = {k: sum(1 for j in jumps if j["walker"] == k) for k in KINDS}
    name = NAMES.get(mp, mp.capitalize())
    bsp = read_bsp(bsp_path)
    ents = duel_entities(bsp["text"])
    spots = live_spots(json.load(open(nav_path)), ents, gaps["jumps"])
    ends = np.array([j["take_off"] for j in jumps] + [j["landing"] for j in jumps], np.float64).reshape(-1, 3)
    feet = np.concatenate([spots, ends]) - np.array([0.0, 0.0, FEET])

    # the floors
    tri, kind, face = map_triangles(bsp, ents)
    pad = 110.0
    lo = np.concatenate([spots, ends])[:, :2].min(0) - pad
    hi = np.concatenate([spots, ends])[:, :2].max(0) + pad
    shape = (int(np.ceil((hi[1] - lo[1]) / CELL)), int(np.ceil((hi[0] - lo[0]) / CELL)))
    hi = lo + np.array([shape[1], shape[0]]) * CELL
    dry = kind == 0
    floor = tri[dry][walkable(tri[dry], face[dry], feet)]
    zlo, zhi = float(feet[:len(spots), 2].min()), float(feet[:len(spots), 2].max())
    wet = (kind != 0) & (tri[:, :, 2].max(1) > zlo - 200.0) & (tri[:, :, 2].min(1) < zhi + 50.0)
    liquids = {int(k): raster(tri[wet & (kind == k)], lo, shape) for k in np.unique(kind[wet])}
    for L in liquids.values():                                 # a liquid's face also runs on under walls and outside the map
        inside, solid = air_cells(bsp, L, lo, 4.0)
        L[~inside | solid] = -np.inf
    H, patched = floors_seen(bsp, floor, lo, shape, feet[:len(spots)])

    # one picture or two
    mid = (spots[:, 2].min() + spots[:, 2].max()) / 2.0
    split = split_height([j["take_off"][2] for j in jumps], mid) if jumps else None
    clash = in_the_way(jumps, split, H, lo) if split is not None else 0
    two = split is not None and (panels == "2" or (panels == "auto" and clash >= 3))
    if panels == "2" and split is None:
        split, two = float(mid), True
    views = [("", jumps, H, None)]
    if two:
        low = split - FEET + 28.0                               # the floors a jump from below the parting height can end on
        H_low, _ = floors_seen(bsp, floor[floor[:, :, 2].max(1) < low], lo, shape, feet[:len(spots)][feet[:len(spots), 2] < low])
        views = [("the upper floors: jumps that start above height {:.0f} (all floors, seen from above)".format(split),
                  [j for j in jumps if j["take_off"][2] >= split], H, (split, None)),
                 ("the lower floors: jumps that start below height {:.0f} (the floors above are left out)".format(split),
                  [j for j in jumps if j["take_off"][2] < split], H_low, (None, split))]

    # the sheet: every panel is the whole map at one scale
    W, Hh = hi[0] - lo[0], hi[1] - lo[1]
    s = min((13.0 if two else 16.0) / W, 13.5 / Hh)             # inches a unit
    aw, ah, gap_, left, top, bottom = W * s, Hh * s, 0.55, 0.6, 1.25, 1.75 + (0.22 if count["up a ledge"] else 0.0)
    fw, fh = left + len(views) * aw + (len(views) - 1) * gap_ + 0.3, bottom + ah + top
    fig = plt.figure(figsize=(fw, fh), dpi=dpi, facecolor="white")
    px = dpi / 72.0

    def size(text, pt, weight):                                # a label's box in pixels
        bb = TextPath((0, 0), text, size=pt, prop=FontProperties(weight=weight)).get_extents()
        return (bb.width + 0.62 * pt) * px, 1.36 * pt * px

    items, seen_ya = [], 0
    for e in ents:
        lab = ITEMS.get(e.get("classname"))
        if lab and "origin" in e:
            if lab == "YA":                                    # the second yellow armor of a map is "YA2" in the lists
                seen_ya += 1
                lab = "YA" if seen_ya == 1 else "YA{}".format(seen_ya)
            items.append((lab, e["origin"]))

    wet_seen = set()
    for v, (title, js, Hv, band) in enumerate(views):
        ax = fig.add_axes([(left + v * (aw + gap_)) / fw, bottom / fh, aw / fw, ah / fh])
        img, seen = shade(Hv, liquids, zlo, zhi)
        wet_seen.update(seen)
        ax.imshow(img, extent=(lo[0], hi[0], lo[1], hi[1]), origin="lower", interpolation="nearest", zorder=0)
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_aspect("equal")
        ax.xaxis.set_major_locator(MultipleLocator(256))
        ax.yaxis.set_major_locator(MultipleLocator(256))
        ax.tick_params(labelsize=7, colors="#9a9a9a", length=2)
        for sp in ax.spines.values():
            sp.set_color("#c8c8c8")
        if title:
            ax.set_title(title, fontsize=13, pad=8)
        T = ax.transData.transform
        back = ax.transData.inverted().transform
        f0, f1 = T(lo), T(hi)
        curves = {j["id"]: bent(T(j["take_off"][:2]), T(j["landing"][:2])) for j in js}
        pl = Places(np.concatenate(list(curves.values())) if curves else np.zeros((0, 2)), (f0[0], f0[1], f1[0], f1[1]))
        pl.marks = np.array([T(p[:2]) for _, p in items], np.float64).reshape(-1, 2)

        for j in sorted(js, key=lambda j: -KINDS.index(j["walker"])):          # red on top
            col, lw = COLOR[j["walker"]], width(j)
            z = 3 + (len(KINDS) - KINDS.index(j["walker"]))
            ax.add_patch(FancyArrowPatch(j["take_off"][:2], j["landing"][:2], connectionstyle="arc3,rad={}".format(RAD),
                                         arrowstyle="-|>,head_length=0.8,head_width=0.36", mutation_scale=8.0 + 2.3 * lw,
                                         lw=lw, color=col, shrinkA=0, shrinkB=0, zorder=z, joinstyle="miter",
                                         path_effects=[pe.Stroke(linewidth=lw + 2.4, foreground="white"), pe.Normal()]))

        for j in js:                                           # the numbers: each on its take-off, red first
            col, a = COLOR[j["walker"]], T(j["take_off"][:2])
            w_, h_ = size(str(j["id"]), 13.0, "bold")
            c, far = pl.on_point(a, max(w_, h_) + 6.0, max(w_, h_) + 6.0)
            if far:                                            # moved aside: a dot on the take-off itself and a line to it
                ax.plot([j["take_off"][0], back(c)[0]], [j["take_off"][1], back(c)[1]], "-", color=col, lw=1.6, zorder=11)
                ax.plot([j["take_off"][0]], [j["take_off"][1]], "o", ms=6.0, mfc=col, mec="white", mew=0.9, zorder=11)
            ax.text(*back(c), str(j["id"]), fontsize=13.0, fontweight="bold", color="white", ha="center", va="center",
                    zorder=13, bbox=dict(boxstyle="circle,pad=0.22", fc=col, ec="white", lw=1.6))

        for lab, p in items:                                   # the items: a spot and the name beside it
            here = band is None or ((band[0] is None or p[2] >= band[0] - 56.0) and (band[1] is None or p[2] < band[1] + 28.0))
            col = "#111111" if here else "#8a8a8a"
            w_, h_ = size(lab, 10.5, "bold")
            c, far = pl.beside_point(T(p[:2]), w_, h_)
            ax.plot([p[0]], [p[1]], "D", ms=5.0, mfc=col, mec="white", mew=0.8, zorder=9)
            if far:
                ax.plot([p[0], back(c)[0]], [p[1], back(c)[1]], "-", color=col, lw=0.7, zorder=9)
            ax.text(*back(c), lab, fontsize=10.5, fontweight="bold", color=col, ha="center", va="center", zorder=10,
                    bbox=dict(boxstyle="square,pad=0.16", fc="#fffbe6", ec=col, lw=0.7, alpha=0.92 if here else 0.75))

    fig.text(left / fw, 1.0 - 0.42 / fh, "{}: the pros' jumps from {} demos".format(name, gaps.get("demos", "?")),
             fontsize=21, fontweight="bold", ha="left", va="center")
    fig.text(left / fw, 1.0 - 0.80 / fh,
             "{} minutes of play. The jumps in training: each one's number sits on its take-off, the arrow runs to its "
             "landing. The numbers are the table's.".format(gaps.get("player_minutes", "?")),
             fontsize=11.5, color="#333333", ha="left", va="center")
    hands = [Line2D([], [], color=COLOR[k], lw=4.0, label="{}: {}".format(SAYS[k], count[k]))
             for k in KINDS if count[k] or k in ("cannot", "slower", "just makes it")]
    fig.legend(handles=hands, loc="lower left", bbox_to_anchor=(left / fw, 0.93 / fh), ncol=2, fontsize=11.5, frameon=False,
               handlelength=2.6, columnspacing=2.5, borderaxespad=0.0)
    hands = [Line2D([], [], color="#444444", lw=width(dict(walker="", per_hour=h)), label=says)
             for h, says in ((1, "once an hour"), (5, "5 times an hour"), (25, "25 times an hour"))]
    hands += [Patch(facecolor=TINT[k], edgecolor="#8a8a8a", label=WET[k]) for k in sorted(wet_seen)]
    fig.legend(handles=hands, loc="lower left", bbox_to_anchor=(left / fw, 0.56 / fh), ncol=len(hands), fontsize=10.5,
               frameon=False, handlelength=2.6, columnspacing=2.0, borderaxespad=0.0)
    labs = {lab[:2] for lab, _ in items}
    known = [says for k, says in (("MH", "MH mega health"), ("RA", "RA red armor"), ("YA", "YA yellow armor"),
                                  ("GA", "GA green armor")) if k in labs]
    fig.text(left / fw, 0.36 / fh, "{} an item: {}.   Floors: dark = low, light = high, a line where the height steps."
             .format(chr(0x25C6), ", ".join(known + ["the rest weapons"])), fontsize=10.5, color="#333333", ha="left", va="center")
    fig.text(left / fw, 0.13 / fh, "Drawn: the jumps in training (seen {} times or more where a walker cannot or is slower, {} "
             "where he just makes it, or picked by hand).{}".format(
                 N_HARD, N_EDGE, " An item's name in grey: it lies on the other floors." if two else ""),
             fontsize=10.5, color="#333333", ha="left", va="center")
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, mp + ".png")
    fig.savefig(png, dpi=dpi, facecolor="white")
    plt.close(fig)

    # the table: number, name, kind of jump, how often
    L = ["# {}: the pros' jumps in training".format(name), "", "![{}]({}.png)".format(name, mp), "", SPEED_LINE, "",
         "| # | Name | Jump type | Times an hour |", "|---|---|---|---|"]
    rows = sorted(jumps, key=lambda j: j["id"])
    for j, says in zip(rows, names_say(rows, items)):
        L.append("| {} | {} | {} | {} |".format(j["id"], says, type_says(j), j["per_hour"]))
    open(os.path.join(out_dir, mp + ".md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")

    twice = same_jump(jumps)
    rest = {}
    for j in gaps["jumps"]:                                    # what the lists hold and the picture leaves out
        if j not in jumps:
            rest[j["walker"]] = rest.get(j["walker"], 0) + 1
    print("{}: {} drawn of {} entries: {} (left out: {}); {}; {} spots without a floor face; "
          "drawn twice (take-offs and landings within 110 of each other): {}".format(
              mp, len(jumps), len(gaps["jumps"]), ", ".join("{} {}".format(count[k], k) for k in KINDS if count[k]) or "none",
              ", ".join("{} {}".format(n, k) for k, n in sorted(rest.items())) or "none",
              "two panels parted at {:.0f} ({} lower jumps in the way)".format(split, clash) if two else
              "one panel ({} lower jumps in the way)".format(clash), patched,
              ", ".join("{}={}".format(a, b) for a, b in twice) or "none"), flush=True)
    return png


def readme(out_dir):
    """one page for the owner, README.md: every map's picture and table (from the <map>.md files that are there)"""
    have = sorted(f[:-3] for f in os.listdir(out_dir) if f.endswith(".md") and f != "README.md"
                  and os.path.exists(os.path.join(out_dir, f[:-3] + ".png")))
    order = [m for m in MAPS.split(",") if m in have] + [m for m in have if m not in MAPS.split(",")]
    L = ["# The pros' jumps in training", "",
         "A map a section: the picture (each jump's number sits on its take-off, the arrow runs to its landing) and the",
         "list of its jumps. Red: a walker cannot make it. Orange: a walker is a second or more slower. Blue: a walker just",
         "makes it, from the very edge. Green: up a ledge. The thicker the arrow, the more often the pros jump it.", "",
         SPEED_LINE, ""]
    for mp in order:
        lines = open(os.path.join(out_dir, mp + ".md"), encoding="utf-8").read().splitlines()
        L += ["## " + NAMES.get(mp, mp.capitalize()), ""] + [ln for ln in lines[1:] if ln != SPEED_LINE]
        while L[-1] == "":
            L.pop()
        L.append("")
    out = []
    for ln in L:                                               # no two empty lines in a row
        if ln or (out and out[-1]):
            out.append(ln)
    open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out).rstrip("\n") + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=MAPS, help="maps, with commas")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "design", "jumps"))
    ap.add_argument("--panels", default="auto", choices=("auto", "1", "2"),
                    help="one picture, or two (upper and lower floors); auto: two where arrows of different floors overlap")
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args()
    for mp in a.map.split(","):
        if mp.strip():
            draw(mp.strip(), a.out, a.panels, a.dpi)
    if os.path.isdir(a.out):
        readme(a.out)


if __name__ == "__main__":
    main()

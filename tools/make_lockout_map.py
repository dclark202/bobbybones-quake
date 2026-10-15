"""Build "lockout": a Quake Live duel map after the floor plan of Halo 2's Lockout.

The plan is traced from the usual callout map of Lockout (two drawings: the top level and the bottom level, lined up
here on the lift), in that picture's pixel coordinates: 1 pixel = 6 units, the picture's top is north. Heights are
ours (the picture is flat). Items, weapons and spawns come from maps/lockout/layout.json, which the editor changes;
walls and floors are in this file.

    python tools/make_lockout_map.py [--reset]   # writes data/lab/maps/lockout.map, maps/lockout/{plan.json,rooms.json,editor.html}
    bash tools/build_lockout.sh                  # compiles it (q3map2, mbspc) and packs maps/lockout/lockout.pk3

Rooms joined by walkways over a drop that kills. Heights: the bottom 0, Bottom Blue 96, the main level 256, Top Blue
320, Top Sniper / Top BR / the ring 384.
  Blue (north)      Bottom Blue holds the lift pad; the lift throws you into Top Blue. A short ramp from Top Blue down
                    to Top Middle. The Blue Ramp runs from Bottom Blue down to Bottom Middle.
  Green Room        the pod corridor west of the Blue Ramp, from Bottom Blue's corner down into the bottom corridor.
  Elbow             two walkways west from Blue, each bending south to the Sniper Tower: the upper one from Top Blue
                    to Mid Sniper, the lower one from Bottom Blue to Bottom Sniper.
  Sniper Tower      west: Bottom Sniper, the Sniper Ramp up its west side to Mid Sniper, stairs inside to Top Sniper
                    (a platform over the corridor to Top Middle).
  Top Middle        the big square in the middle, solid. Bottom Middle below it, with the corridor west to Bottom Sniper
                    and the corridor east, then south, to the sword room under the Library.
  Library           south: a room of three bays. The Window is the walkway from Top Middle to it.
  BR Tower          east: Bottom BR (stairs up to the walkway), Mid BR (walkway from Top Middle), Top BR on its roof.
  the ring          the BR Tower Ramp climbs from Top Middle to a walkway round the east side at Top BR's height
                    (the BR Tower Bridge is its south leg into Top BR); stairs from its south-west corner down to the
                    Library's north side.
Every texture name is one the game's own maps use (the ones the training arena already uses)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 6                                                        # units per plan pixel
PX0, PY1 = 40, 345                                           # plan pixel at the map's west edge / south edge
X, Y = (410 - PX0) * S, (PY1 - 50) * S
B, BB, M, TB, TOP, ROOF, PIT = 0, 96, 256, 320, 384, 760, -640
T = 24                                                       # floor thickness
brushes, lights, spawns, extra, plan, pieces = [], [], [], [], [], []
ZONE = [(1.0, 1.0, 1.0)]

F1, F2, METAL, STAIR = "gothic_floor/largerblock3b3", "gothic_floor/largerblock3b3dim", "base_floor/clangdark", "gothic_floor/xstairtop4"
BRICK, BLK, KILL, IRON = "gothic_wall/streetbricks10", "gothic_block/blocks18c", "gothic_trim/skullsvertgray02a", "gothic_wall/iron01_e"
RUST, DARK, GOLD, CEIL = "gothic_trim/pitted_rust2", "gothic_block/dark_block", "gothic_wall/metaltech16gold", "gothic_ceiling/woodceiling1a"
PENT, SKIN, BOUNCE, CONC = "gothic_floor/metalbridge06_pent45", "skin/skin6", "gothic_floor/metalbridge06", "base_wall/concrete"
FACE = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) {} 0 0 0 0.5 0.5 0 0 0"


def mx(px):
    return (px - PX0) * S


def my(py):
    return (PY1 - py) * S


def R(x0, py0, x1, py1):
    """a rectangle in plan pixels -> map units (x0, y0, x1, y1)"""
    return mx(min(x0, x1)), my(max(py0, py1)), mx(max(x0, x1)), my(min(py0, py1))


def emit(faces, tex):
    brushes.append("{\n" + "\n".join(FACE.format(*[int(round(v)) for v in q], tex) for q in faces) + "\n}")


def box(x0, y0, z0, x1, y1, z1, tex=CONC, kind="wall"):
    """a solid box in map units"""
    x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
    if x1 - x0 < 1 or y1 - y0 < 1 or z1 - z0 < 1:
        return
    emit([(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
          (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)], tex)
    plan.append([int(x0), int(y0), int(x1), int(y1), int(z0), int(z1), kind])
    if kind in ("deck", "stairs", "pad"):
        pieces.append(((x0 + x1) / 2, (y0 + y1) / 2, z1, (x1 - x0) * (y1 - y0), ZONE[-1]))


def trigger(kind, x0, y0, z0, x1, y1, z1, more=""):
    f = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
         (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
    br = "{\n" + "\n".join(FACE.format(*[int(round(v)) for v in q], "common/trigger") for q in f) + "\n}"
    extra.append('{{\n"classname" "{}"{}\n{}\n}}'.format(kind, more, br))


def pbox(pr, z0, z1, tex=CONC, kind="wall"):
    r = R(*pr)
    box(r[0], r[1], z0, r[2], r[3], z1, tex, kind)


def slab(pr, z, tex=F1, kind="deck"):
    """a floor whose top is at z"""
    pbox(pr, z - T, z, tex, kind)


def slope(pr, zlo, zhi, toward, tex=METAL):
    """a floor that rises from zlo to zhi toward "n", "s", "e" or "w" (a smooth ramp, T thick at its low end)"""
    x0, y0, x1, y1 = R(*pr)
    zb = zlo - T
    zt = max(zlo, zhi)

    def h(x, y):
        f = {"n": (y - y0) / (y1 - y0), "s": (y1 - y) / (y1 - y0), "e": (x - x0) / (x1 - x0), "w": (x1 - x) / (x1 - x0)}[toward]
        return zlo + (zhi - zlo) * f
    emit([(x1, y1, h(x1, y1), x1, y0, h(x1, y0), x0, y1, h(x0, y1)), (x1, y1, zt, x0, y1, zt, x1, y1, zb), (x1, y1, zt, x1, y1, zb, x1, y0, zt),
          (x0, y0, zb, x1, y0, zb, x0, y1, zb), (x0, y0, zb, x0, y0, zt, x1, y0, zb), (x0, y0, zb, x0, y1, zb, x0, y0, zt)], tex)
    plan.append([int(x0), int(y0), int(x1), int(y1), int(zlo), int(zhi), "slope"])
    pieces.append(((x0 + x1) / 2, (y0 + y1) / 2, (zlo + zhi) / 2, (x1 - x0) * (y1 - y0), ZONE[-1]))


def stairs(pr, z0, z1, toward, tex=STAIR, step=16):
    """steps from z0 to z1 over a plan rectangle, rising toward "n", "s", "e" or "w"; solid underneath down to z0 - T"""
    x0, y0, x1, y1 = R(*pr)
    n = (z1 - z0) // step
    for k in range(n):
        f0, f1 = k / n, (k + 1) / n
        if toward == "e":
            box(x0 + (x1 - x0) * f0, y0, z0 - T, x0 + (x1 - x0) * f1, y1, z0 + step * (k + 1), tex, "stairs")
        elif toward == "w":
            box(x1 - (x1 - x0) * f1, y0, z0 - T, x1 - (x1 - x0) * f0, y1, z0 + step * (k + 1), tex, "stairs")
        elif toward == "n":
            box(x0, y0 + (y1 - y0) * f0, z0 - T, x1, y0 + (y1 - y0) * f1, z0 + step * (k + 1), tex, "stairs")
        else:
            box(x0, y1 - (y1 - y0) * f1, z0 - T, x1, y1 - (y1 - y0) * f0, z0 + step * (k + 1), tex, "stairs")


def walls(pr, z, h, doors=None, tex=BLK, t=12, door_h=128):
    """four walls just inside a plan rectangle, from z up h; doors = {"n": [(a, b)], ...} in plan pixels along that wall"""
    r = R(*pr)
    doors = doors or {}
    for side in "nsew":
        horiz = side in "ns"
        lo, hi = (r[0], r[2]) if horiz else (r[1], r[3])
        gaps = []
        for a, b in doors.get(side, []):
            ga, gb = (mx(a), mx(b)) if horiz else (my(b), my(a))
            gaps.append((min(ga, gb), max(ga, gb)))
        cuts = [lo] + [v for g in sorted(gaps) for v in g] + [hi]

        def put(a, b, z0, z1):
            if horiz:
                yy = (r[3] - t, r[3]) if side == "n" else (r[1], r[1] + t)
                box(a, yy[0], z0, b, yy[1], z1, tex)
            else:
                xx = (r[0], r[0] + t) if side == "w" else (r[2] - t, r[2])
                box(xx[0], a, z0, xx[1], b, z1, tex)
        for a, b in zip(cuts[0::2], cuts[1::2]):
            put(a, b, z, z + h)
        for a, b in gaps:
            if h > door_h:
                put(a, b, z + door_h, z + h)


def kerb(pr, z, tex=GOLD):
    pbox(pr, z, z + 20, tex, "rail")


def zone(c):
    ZONE.append(c)


# plan rectangles (pixels of the callout map, top-level drawing; the bottom drawing is moved to line up on the lift)
TOPBLUE = (165, 57, 230, 147)
BOTBLUE = (175, 62, 223, 147)
TOPMID = (155, 177, 238, 267)
BOTMID = (180, 217, 217, 255)
MIDSNP = (78, 212, 120, 287)
BOTSNP = (78, 215, 130, 282)
MIDBR = (283, 208, 345, 257)
BOTBR = (290, 208, 357, 255)
LIB = (213, 287, 343, 320)
SWORD = (257, 292, 337, 315)


def build(layout):
    # ---- the shell: dark rock all round, the pit far below, anything that falls dies
    box(-32, -32, PIT - 32, X + 32, Y + 32, PIT, DARK, "shell")
    box(-32, -32, PIT, 0, Y + 32, ROOF + 32, DARK, "shell")
    box(X, -32, PIT, X + 32, Y + 32, ROOF + 32, DARK, "shell")
    box(0, -32, PIT, X, 0, ROOF + 32, DARK, "shell")
    box(0, Y, PIT, X, Y + 32, ROOF + 32, DARK, "shell")
    box(-32, -32, ROOF, X + 32, Y + 32, ROOF + 32, CEIL, "shell")
    trigger("trigger_hurt", 0, 0, PIT + 40, X, Y, PIT + 300, '\n"dmg" "10000"')

    # ================= Blue
    zone((0.35, 0.75, 1.0))
    slab(BOTBLUE, BB, F2)                                                      # Bottom Blue
    walls(BOTBLUE, BB, TB - T - BB, {"s": [(192, 210)], "w": [(98, 112), (128, 147)]}, BRICK)
    pad = R(195, 66, 207, 78)
    box(pad[0], pad[1], BB, pad[2], pad[3], BB + 2, PENT, "pad")
    trigger("trigger_push", pad[0] + 8, pad[1] + 8, BB + 2, pad[2] - 8, pad[3] - 8, BB + 18, '\n"target" "lo_lift"')
    extra.append('{{\n"classname" "target_position"\n"targetname" "lo_lift"\n"origin" "{} {} {}"\n}}'.format(mx(201), my(84), TB + 150))
    for pr in ((165, 86, 230, 147), (165, 57, 189, 86), (213, 57, 230, 86)):   # Top Blue's floor, a hole over the pad
        slab(pr, TB, BOUNCE)
    walls(TOPBLUE, TB, 200, {"s": [(187, 207)], "w": [(95, 110)], "e": [(95, 110)]}, BRICK)
    slab(TOPBLUE, TB + 200 + T, CEIL, "roof")
    slab((230, 95, 240, 110), TB, METAL)                                       # the ledge outside the east door
    slope((187, 147, 207, 177), M, TB, "n")                                    # the short ramp down to Top Middle
    kerb((185, 147, 187, 177), TB); kerb((207, 147, 209, 177), TB)
    slope((192, 147, 210, 218), B, BB, "n", F2)                                # the Blue Ramp down to Bottom Middle
    pbox((190, 147, 192, 218), B - T, M - T, BRICK); pbox((210, 147, 212, 218), B - T, M - T, BRICK)
    # ================= the Green Room: from Bottom Blue's corner down to the bottom corridor, a nook past it
    zone((0.15, 1.0, 0.3))
    slab((143, 128, 175, 165), BB, F2)                                        # the landing at Bottom Blue's door
    slope((147, 165, 165, 222), B, BB, "n", F2)
    for pr in ((143, 128, 147, 165), (167, 128, 175, 165), (143, 165, 147, 222), (165, 165, 170, 222), (143, 125, 175, 128)):
        pbox(pr, B - T, M - T, SKIN)
    for py in (175, 195, 210):                                                 # the pods, against the walls
        pbox((147, py, 150, py + 8), B, B + 120, KILL, "cover")
        pbox((162, py, 165, py + 8), B, B + 120, KILL, "cover")
    # ================= the middle
    zone((1.0, 0.9, 0.7))
    slab(TOPMID, M, F1)                                                        # Top Middle, solid
    slab(BOTMID, B, PENT)                                                      # Bottom Middle under it
    walls(BOTMID, B, M - T, {"n": [(192, 210)], "w": [(222, 238)], "e": [(232, 245)]}, IRON)
    pbox((195, 250, 203, 254), B, B + 120, KILL, "cover")                      # the pod at its back
    zone((1.0, 0.5, 0.9))
    slab((130, 222, 180, 238), B, BOUNCE)                                      # corridor: Bottom Sniper to Bottom Middle
    slab((217, 232, 257, 245), B, BOUNCE)                                      # corridor east, then south, to the sword room
    slab((242, 245, 257, 292), B, BOUNCE)
    # ================= the Elbow, upper and lower
    zone((0.6, 0.6, 1.0))
    for z0, z1 in ((TB, M), (BB, B)):
        slab((127, 95, 165, 110) if z0 == TB else (127, 98, 175, 112), z0, METAL)   # the grated bridge from Blue
        slab((95, 80, 127, 110) if z0 == TB else (95, 85, 127, 112), z0, F1)         # the corner
        slope((95, 110, 120, 212) if z0 == TB else (95, 112, 120, 215), z1, z0, "n", METAL)   # down to the Sniper Tower
        kerb((93, 80, 95, 212), z0); kerb((95, 78, 127, 80), z0)
    # ================= the Sniper Tower
    zone((1.0, 0.75, 0.45))
    slab(BOTSNP, B, F2)                                                        # Bottom Sniper
    walls(BOTSNP, B, M - T, {"n": [(95, 120)], "e": [(222, 238)], "w": [(262, 282)]})
    slab((50, 272, 78, 290), B, F2)                                            # the Sniper Ramp's foot
    stairs((50, 212, 78, 272), B, M, "n")                                      # the Sniper Ramp, up the west side
    pbox((48, 212, 50, 290), B - T, M + 40, BRICK)
    slab(MIDSNP, M, F1)                                                        # Mid Sniper
    walls(MIDSNP, M, 240, {"w": [(212, 230)], "n": [(95, 120)], "e": [(220, 240), (267, 283)]}, BLK, 12, 240)   # doors to the roof: the upper east one is the way out at the top of the stairs
    stairs((85, 272, 120, 284), M, TOP, "e")                                   # inside, along the south wall, up to Top Sniper
    slab(MIDSNP, M + 240 + T, CEIL, "roof")
    slab((120, 220, 155, 240), M, BOUNCE)                                      # corridor to Top Middle
    zone((1.0, 0.85, 0.3))
    slab((120, 245, 157, 283), TOP, PENT)                                      # Top Sniper, a platform over the corridor
    kerb((155, 245, 157, 283), TOP); kerb((120, 243, 157, 245), TOP); kerb((120, 283, 157, 285), TOP)
    # ================= the Library and the sword room under it
    zone((0.8, 0.5, 1.0))
    slab((213, 267, 238, 287), M, BOUNCE)                                      # the Window
    slab(LIB, M, F1)
    for pr in ((213, 320, 243, 340), (250, 320, 300, 340), (313, 320, 343, 340)):
        slab(pr, M, PENT)
    walls((213, 287, 343, 340), M, TOP - T - M, {"n": [(213, 343)]}, BRICK, 12, 200)                     # open along its north side
    for pr in ((243, 320, 250, 340), (300, 320, 313, 340)):                     # the bay walls
        pbox(pr, M, TOP - T, BRICK)
    pbox((243, 320, 250, 340), M - T, M, F1, "deck"); pbox((300, 320, 313, 340), M - T, M, F1, "deck")
    slab((213, 287, 343, 340), TOP, CEIL, "roof")
    zone((1.0, 0.3, 0.3))
    slab(SWORD, B, F2)
    slab((242, 292, 257, 315), B, F2)
    slab((263, 315, 283, 328), B, PENT)                                        # the sword nook
    walls((242, 292, 337, 315), B, 160, {"n": [(242, 257), (320, 337)], "s": [(263, 283)]}, BRICK, 12, 120)
    walls((263, 315, 283, 328), B, 160, {"n": [(263, 283)]}, BRICK, 12, 120)
    slab((320, 255, 337, 292), B, BOUNCE)                                      # north to Bottom BR
    # ================= the BR Tower
    zone((0.5, 0.9, 1.0))
    slab(BOTBR, B, F2)
    walls(BOTBR, B, M - T, {"s": [(320, 337)], "w": [(232, 245)]})
    slab((270, 290, 232, 245), B, F2)                                          # the stub west of Bottom BR
    stairs((240, 233, 290, 247), B, M, "w")                                    # up to the walkway's east end at Top Middle
    slab((238, 220, 283, 233), M, BOUNCE)                                      # walkway: Top Middle to Mid BR
    slab(MIDBR, M, F1)
    walls(MIDBR, M, TOP - T - M, {"w": [(220, 233)]}, BLK, 12, 104)
    zone((1.0, 0.85, 0.3))
    slab(MIDBR, TOP, PENT)                                                     # Top BR, on the roof
    walls(MIDBR, TOP, 40, {"n": [(328, 345)], "s": [(317, 345)]}, GOLD, 8)
    # ================= the ring: the BR Tower Ramp, the walkway round the east, the BR Tower Bridge, down to the Library
    zone((0.3, 1.0, 0.9))
    slab((238, 180, 263, 207), M, BOUNCE)
    slope((263, 180, 328, 207), M, TOP, "e")                                   # the BR Tower Ramp
    slab((328, 177, 400, 200), TOP, METAL)                                     # north leg
    slab((328, 200, 345, 208), TOP, METAL)                                     # into Top BR
    slab((383, 200, 400, 290), TOP, METAL)                                     # east leg (the cliff side)
    kerb((398, 177, 400, 310), TOP)
    slab((328, 290, 400, 310), TOP, METAL)                                     # south leg
    slab((317, 257, 345, 290), TOP, METAL)                                     # the BR Tower Bridge, into Top BR from the south
    slab((328, 280, 345, 290), TOP, METAL)
    stairs((250, 277, 328, 287), M, TOP, "e", METAL, 8)                        # down along the Library's north side
    slab((238, 267, 250, 287), M, BOUNCE)                                      # the landing beside the Window
    # ---- lights: one over every floor piece, in its zone's colour, plus a few big ones under the roof
    for cx, cy, z, area, c in pieces:
        if area < 60 * 60:
            continue
        lights.append((cx, cy, z + (110 if area < 300 * 300 else 170), int(min(520, 180 + area ** 0.5 * 0.9)), c))
    for px, py, c in ((200, 100, (0.7, 0.8, 1.0)), (110, 150, (0.7, 0.8, 1.0)), (100, 250, (1.0, 0.9, 0.8)), (200, 220, (0.8, 0.9, 1.0)),
                      (320, 230, (0.9, 0.8, 1.0)), (280, 310, (1.0, 0.8, 0.9)), (380, 240, (0.7, 1.0, 0.9))):
        lights.append((mx(px), my(py), ROOF - 120, 800, c))
    # ---- items and spawns from the layout the editor writes
    for s in layout.get("spawns", []):
        spawns.append((s["x"], s["y"], s["z"] + 24, s.get("angle", 0)))
    for it in layout.get("items", []):
        extra.append('{{\n"classname" "{}"\n"origin" "{} {} {}"\n}}'.format(it["class"], int(it["x"]), int(it["y"]), int(it["z"]) + 24))


def first_layout():
    """the first placement (plan pixels and a floor height), written when maps/lockout/layout.json does not exist or with --reset"""
    items = [("weapon_railgun", 273, 322, B, "Sword spawn: the nook under the Library"),
             ("weapon_rocketlauncher", 156, 200, BB, "Green Room (Halo's shotgun)"),
             ("weapon_lightning", 222, 100, TB, "Top Blue, east side"),
             ("weapon_rocketlauncher", 314, 232, TOP, "Second rocket launcher: Top BR"),
             ("weapon_plasmagun", 275, 332, M, "Library, middle bay"),
             ("weapon_grenadelauncher", 198, 236, B, "Bottom Middle"),
             ("weapon_shotgun", 340, 232, B, "Bottom BR"),
             ("item_armor_combat", 108, 94, TB, "Yellow armor: the corner of the upper Elbow"),
             ("item_armor_body", 150, 276, TOP, "Red armor: Top Sniper"),
             ("item_health_mega", 250, 275, B, "Mega: the bottom corridor's south leg"),
             ("item_armor_combat", 328, 332, M, "Second yellow armor: Library, east bay"),
             ("item_health_large", 392, 188, TOP, "The ring's north-east corner"),
             ("item_health_large", 100, 270, B, "Bottom Sniper"),
             ("item_health", 165, 185, M, "Top Middle, north-west"), ("item_health", 230, 258, M, "Top Middle, south-east"),
             ("item_health", 90, 250, M, "Mid Sniper"), ("item_health", 300, 232, M, "Mid BR"),
             ("item_health", 107, 160, BB, "Lower Elbow"), ("item_health", 250, 193, M, "Foot of the BR Tower Ramp"),
             ("item_health", 200, 130, BB, "Bottom Blue"),
             ("item_armor_shard", 197, 162, TB, "Ramp: Top Blue to Top Middle"), ("item_armor_shard", 225, 277, M, "The Window"),
             ("item_armor_shard", 160, 230, B, "Bottom corridor, west"), ("item_armor_shard", 201, 182, BB, "Blue Ramp"),
             ("item_armor_shard", 365, 300, TOP, "The ring, south leg"), ("item_armor_shard", 64, 280, B, "Foot of the Sniper Ramp"),
             ("ammo_rockets", 155, 146, BB, "Green Room, top"), ("ammo_rockets", 330, 215, M, "Mid BR"),
             ("ammo_slugs", 300, 303, B, "Sword room"), ("ammo_lightning", 180, 130, TB, "Top Blue, west side"),
             ("ammo_cells", 228, 332, M, "Library, west bay"), ("ammo_grenades", 205, 243, B, "Bottom Middle"),
             ("ammo_shells", 300, 215, B, "Bottom BR")]
    sp = [(110, 230, B, 180), (100, 270, M, 0), (200, 135, TB, 270), (165, 255, M, 45), (240, 300, M, 90), (300, 215, M, 180),
          (320, 303, B, 180), (391, 250, TOP, 180), (110, 90, TB, 0), (345, 215, B, 180), (210, 130, BB, 180), (140, 255, TOP, 270)]
    return dict(version=4, note="items and spawns for maps/lockout; z is the floor height (the generator adds 24; items drop to the floor in the game). Edit with the editor page, then run tools/make_lockout_map.py",
                items=[{"id": "i%02d" % k, "class": c, "x": mx(px), "y": my(py), "z": z, "label": l} for k, (c, px, py, z, l) in enumerate(items)],
                spawns=[{"id": "s%02d" % k, "x": mx(px), "y": my(py), "z": z, "angle": a} for k, (px, py, z, a) in enumerate(sp)])


def main():
    path = os.path.join(ROOT, "maps", "lockout", "layout.json")
    if "--reset" in sys.argv or not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            json.dump(first_layout(), f, indent=1)
    with open(path, encoding="utf-8") as f:
        layout = json.load(f)
    build(layout)
    ents = ['{\n"classname" "worldspawn"\n"message" "BobbyBones: Lockout"\n"_ambient" "40"\n"_color" "1 1 1"\n' + "\n".join(brushes) + "\n}"]
    for x, y, z, a in spawns:
        ents.append('{{\n"classname" "info_player_deathmatch"\n"origin" "{} {} {}"\n"angle" "{}"\n}}'.format(int(x), int(y), int(z), int(a)))
    ents += extra
    for x, y, z, v, c in lights:
        ents.append('{{\n"classname" "light"\n"origin" "{} {} {}"\n"light" "{}"\n"_color" "{} {} {}"\n}}'.format(int(x), int(y), int(z), v, *[round(k, 2) for k in c]))
    os.makedirs(os.path.join(ROOT, "data", "lab", "maps"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "lab", "maps", "lockout.map"), "w", newline="\n") as f:
        f.write("\n".join(ents) + "\n")
    levels = [["low", -40, 200, "Bottom"], ["mid", 200, 360, "Main"], ["top", 360, 800, "Tops"]]
    pl = dict(size=[X, Y], levels=levels, boxes=[b for b in plan if b[6] not in ("shell", "roof")])
    with open(os.path.join(ROOT, "maps", "lockout", "plan.json"), "w", newline="\n") as f:
        json.dump(pl, f)
    tpl = os.path.join(ROOT, "maps", "lockout", "editor.template.html")
    if os.path.exists(tpl):                                  # the editor page: the plan and the current layout built in
        seed = json.dumps(dict(items=layout.get("items", []), spawns=layout.get("spawns", [])), separators=(",", ":"))
        page = open(tpl, encoding="utf-8").read().replace("/*PLAN_JSON*/null", json.dumps(pl, separators=(",", ":"))).replace("/*LAYOUT_JSON*/null", seed)
        with open(os.path.join(ROOT, "maps", "lockout", "editor.html"), "w", newline="\n", encoding="utf-8") as f:
            f.write(page)
    spots = [[s["x"], s["y"], s["z"] + 8] for s in layout.get("spawns", [])]
    with open(os.path.join(ROOT, "maps", "lockout", "rooms.json"), "w", newline="\n") as f:
        json.dump(dict(map="lockout", stations={}, courses={}, ambient=40, hurt=[[0, 0, PIT + 40, X, Y, PIT + 300, 100000]],
                       yard=dict(bounds=[0, 0, X, Y], z=8, spots=spots, items=True)), f, indent=1)
    print("lockout: {} brushes, {} lights, {} spawns, {} items -> data/lab/maps/lockout.map".format(
        len(brushes), len(lights), len(spawns), len(layout.get("items", []))))


if __name__ == "__main__":
    main()

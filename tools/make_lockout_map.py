"""Build "lockout": a Quake Live duel map after the floor plan of Halo 2's Lockout.

The plan is traced from the game's own loading-screen map (two floors drawn side by side; Halopedia, "Lockout Map"), in
its pixel coordinates: 1 pixel = 4 units, the picture's top is north. Heights, stairs and everything the plan does not
show are ours. Items, weapons and spawns come from maps/lockout/layout.json, which the editor changes; walls and
floors are in this file.

    python tools/make_lockout_map.py       # writes data/lab/maps/lockout.map, maps/lockout/plan.json, rooms.json, editor.html
    bash tools/build_lockout.sh            # compiles it (q3map2, mbspc) and packs maps/lockout/lockout.pk3

Three floors (0 bottom, 224 main, 448 tops) of rooms joined by narrow walkways over a drop that kills:
  lift tower     north. Bottom: the green room (pods), the lift pad. Main: the room the lift throws you into.
  centre         the open square platform (a hole in its middle), a bridge north to the lift tower.
                 Under it: the green corridor from the lift room to "bottom mid", and the exposed walkway west of it
                 (Halo's sword).
  Sniper Tower   south-west, three floors, two flights of stairs. Bridge to the centre at main.
  elbow          the L-shaped walkway from the lift tower west, then south to the Sniper Tower: one on each lower floor.
  BR Tower       east, three floors, stairs bottom to main. A walkway to the centre; its top is reached from the loop.
  library        south: main floor three bays, bottom floor one room. Joined to the centre, the BR Tower and the loop.
  loop           the walkway round the east side: from the centre, stairs up to the top floor, a bridge to the BR
                 Tower's top, stairs down again to the library.
Every texture name is one the game's own maps use (the ones the training arena already uses)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 4                                                        # units per plan pixel
PX0, PY1 = -20, 540                                          # plan pixel at the map's west edge / south edge
X, Y = (700 - PX0) * S, (PY1 + 30) * S
L1, L2, L3, ROOF, PIT = 0, 224, 448, 768, -640
T = 24                                                       # floor thickness
brushes, lights, spawns, extra, plan = [], [], [], [], []

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


def _faces(x0, y0, z0, x1, y1, z1):
    return [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
            (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]


def box(x0, y0, z0, x1, y1, z1, tex=CONC, kind="wall"):
    """a solid box in map units"""
    x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
    if x1 - x0 < 1 or y1 - y0 < 1 or z1 - z0 < 1:
        return
    brushes.append("{\n" + "\n".join(FACE.format(*[int(round(v)) for v in q], tex) for q in _faces(x0, y0, z0, x1, y1, z1)) + "\n}")
    plan.append([int(x0), int(y0), int(x1), int(y1), int(z0), int(z1), kind])


def trigger(kind, x0, y0, z0, x1, y1, z1, more=""):
    br = "{\n" + "\n".join(FACE.format(*[int(round(v)) for v in q], "common/trigger") for q in _faces(x0, y0, z0, x1, y1, z1)) + "\n}"
    extra.append('{{\n"classname" "{}"{}\n{}\n}}'.format(kind, more, br))


def slab(r, z, tex=F1, kind="deck"):
    box(r[0], r[1], z - T, r[2], r[3], z, tex, kind)


def walk(pr, z, rails="", tex=METAL):
    """a walkway: a floor and a kerb (24 high: a hop gets over it, a stumble does not) on the sides named in rails"""
    r = R(*pr)
    slab(r, z, tex)
    for s in rails:
        k = {"n": (r[0], r[3] - 8, r[2], r[3]), "s": (r[0], r[1], r[2], r[1] + 8), "w": (r[0], r[1], r[0] + 8, r[3]), "e": (r[2] - 8, r[1], r[2], r[3])}[s]
        box(k[0], k[1], z, k[2], k[3], z + 24, GOLD, "rail")


def walls(pr, z, h, doors=None, tex=BLK, t=16, door_h=128):
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


def stairs(pr, z0, z1, toward, tex=STAIR):
    """steps of 16 from z0 to z1 over a plan rectangle, rising toward "n", "s", "e" or "w"; solid underneath down to z0"""
    r = R(*pr)
    n = (z1 - z0) // 16
    for k in range(n):
        f0, f1 = k / n, (k + 1) / n
        if toward == "e":
            box(r[0] + (r[2] - r[0]) * f0, r[1], z0 - T, r[0] + (r[2] - r[0]) * f1, r[3], z0 + 16 * (k + 1), tex, "stairs")
        elif toward == "w":
            box(r[2] - (r[2] - r[0]) * f1, r[1], z0 - T, r[2] - (r[2] - r[0]) * f0, r[3], z0 + 16 * (k + 1), tex, "stairs")
        elif toward == "n":
            box(r[0], r[1] + (r[3] - r[1]) * f0, z0 - T, r[2], r[1] + (r[3] - r[1]) * f1, z0 + 16 * (k + 1), tex, "stairs")
        else:
            box(r[0], r[3] - (r[3] - r[1]) * f1, z0 - T, r[2], r[3] - (r[3] - r[1]) * f0, z0 + 16 * (k + 1), tex, "stairs")


def lamp(px, py, z, v=380, c=(1.0, 1.0, 1.0)):
    lights.append((mx(px), my(py), z, v, c))


TS = (22, 283, 168, 450)                                     # Sniper Tower
TB = (452, 272, 572, 365)                                    # BR Tower
TL = (235, -5, 352, 160)                                     # lift tower
LIB1, LIB2 = (365, 418, 541, 468), (318, 418, 545, 520)      # library, bottom and main floor
J1 = (261, 285, 328, 355)                                    # bottom mid


def build(layout):
    # ---- the shell: a box of dark rock, the pit's floor far below, anything that falls dies
    box(-32, -32, PIT - 32, X + 32, Y + 32, PIT, DARK, "pit")
    box(-32, -32, PIT, 0, Y + 32, ROOF + 32, DARK, "shell")
    box(X, -32, PIT, X + 32, Y + 32, ROOF + 32, DARK, "shell")
    box(0, -32, PIT, X, 0, ROOF + 32, DARK, "shell")
    box(0, Y, PIT, X, Y + 32, ROOF + 32, DARK, "shell")
    box(-32, -32, ROOF, X + 32, Y + 32, ROOF + 32, CEIL, "shell")
    trigger("trigger_hurt", 0, 0, PIT + 40, X, Y, PIT + 300, '\n"dmg" "10000"')

    # ---- lift tower: the green room at the bottom (pods, the pad), the arrival room above it
    slab(R(*TL), L1, F2)
    walls(TL, L1, L2 - T, {"s": [(279, 315)], "w": [(65, 92), (125, 150)]}, BRICK)
    for px, py in ((250, 40), (322, 40), (250, 100), (322, 100)):          # the stasis pods
        box(*R(px, py, px + 15, py + 28)[:2], L1, *R(px, py, px + 15, py + 28)[2:], L1 + 120, SKIN, "cover")
    pad = R(281, 4, 305, 28)
    box(pad[0], pad[1], L1, pad[2], pad[3], L1 + 2, PENT, "pad")
    trigger("trigger_push", pad[0] + 12, pad[1] + 12, L1 + 2, pad[2] - 12, pad[3] - 12, L1 + 18, '\n"target" "lo_lift"')
    extra.append('{{\n"classname" "target_position"\n"targetname" "lo_lift"\n"origin" "{} {} {}"\n}}'.format(mx(293), my(40), L2 + 150))
    for pr in ((235, 36, 352, 160), (235, -5, 270, 36), (316, -5, 352, 36)):   # main floor, a hole over the pad
        slab(R(*pr), L2, BOUNCE)
    walls(TL, L2, L3 - T - L2, {"s": [(277, 312)], "w": [(65, 92)]}, BRICK)
    slab(R(*TL), L3, CEIL)                                                  # its roof
    # ---- the bridge to the centre, the centre platform (a hole in the middle: bottom mid is under it)
    walk((277, 160, 312, 222), L2, "ew")
    for pr in ((215, 222, 368, 278), (215, 315, 368, 385), (215, 278, 275, 315), (312, 278, 368, 315), (330, 385, 368, 418)):
        slab(R(*pr), L2, F1)
    # ---- under the centre: the green corridor, bottom mid, the exposed walkway west of it, the side passage
    walk((279, 155, 315, 285), L1, "", F2)
    for px in (275, 315):
        box(*R(px, 160, px + 4, 285)[:2], L1, *R(px, 160, px + 4, 285)[2:], L1 + 96, SKIN, "wall")
    slab(R(*J1), L1, PENT)
    walls(J1, L1, L2 - T, {"n": [(279, 315)], "w": [(295, 322)], "e": [(315, 345)]}, IRON)
    walk((168, 295, 261, 322), L1, "", BOUNCE)                              # no kerbs: this is the dangerous one
    walk((195, 322, 228, 355), L1, "", BOUNCE)
    walk((198, 190, 225, 295), L1, "ew")
    slab(R(191, 122, 231, 190), L1, F2)
    walk((231, 125, 239, 150), L1, "")
    # ---- the elbow, on both lower floors
    for z in (L1, L2):
        walk((148, 65, 239, 92), z, "ns")
        walk((108, 42, 148, 283), z, "wn" if z == L2 else "w")
        r = R(144, 92, 148, 283)
        box(r[0], r[1], z, r[2], r[3], z + 24, GOLD, "rail")
    # ---- Sniper Tower: three floors, a flight of stairs from each of the lower two
    slab(R(*TS), L1, F2)
    walls(TS, L1, L2 - T, {"n": [(108, 148)], "e": [(295, 322)]})
    for pr in ((22, 283, 168, 298), (60, 298, 168, 450), (22, 410, 60, 450), (22, 298, 26, 410)):
        slab(R(*pr), L2, F1)
    walls(TS, L2, L3 - T - L2, {"n": [(108, 148)], "e": [(297, 335)]})
    for pr in ((22, 283, 168, 298), (96, 298, 168, 450), (22, 410, 96, 450), (22, 298, 62, 410)):
        slab(R(*pr), L3, PENT)
    walls(TS, L3, 40, {}, GOLD, 8)
    stairs((26, 298, 60, 410), L1, L2, "n")
    stairs((62, 298, 96, 410), L2, L3, "s")
    walk((168, 297, 215, 335), L2, "ns")                                    # bridge to the centre
    # ---- BR Tower: three floors, stairs from the bottom to the main floor, the top reached from the loop
    slab(R(*TB), L1, F2)
    walls(TB, L1, L2 - T, {"s": [(513, 538)]})
    for pr in ((452, 272, 572, 281), (452, 299, 572, 365), (452, 281, 465, 299), (549, 281, 572, 299)):
        slab(R(*pr), L2, F1)
    walls(TB, L2, L3 - T - L2, {"w": [(300, 335)], "s": [(508, 545)]})
    stairs((465, 281, 549, 299), L1, L2, "e")
    slab(R(*TB), L3, PENT)
    walls(TB, L3, 40, {"e": [(285, 313)]}, GOLD, 8)
    walk((368, 300, 452, 335), L2, "ns")                                    # walkway to the centre
    walk((508, 365, 545, 418), L2, "ew")                                    # main floor: to the library
    walk((513, 365, 538, 418), L1, "ew")                                    # bottom floor: to the library
    # ---- the library: three bays on the main floor, one room under them
    slab(R(*LIB1), L1, F2)
    walls(LIB1, L1, L2 - T, {"n": [(367, 391), (513, 538)]}, BRICK)
    slab(R(*LIB2), L2, F1)
    walls(LIB2, L2, L3 - T - L2, {"n": [(330, 368), (508, 545)], "e": [(425, 465)]}, BRICK)
    for px in (398, 468):                                                   # the bay walls, a doorway in each
        r = R(px, 418, px + 4, 440)
        box(r[0], r[1], L2, r[2], r[3], L3 - T, BRICK)
        r = R(px, 472, px + 4, 520)
        box(r[0], r[1], L2, r[2], r[3], L3 - T, BRICK)
    slab(R(*LIB2), L3, CEIL)
    # ---- bottom floor: bottom mid east, then south to the library
    walk((328, 315, 393, 345), L1, "n")
    walk((365, 345, 393, 418), L1, "ew")
    r = R(328, 341, 365, 345)
    box(r[0], r[1], L1, r[2], r[3], L1 + 24, GOLD, "rail")
    # ---- the loop round the east side: up to the top floor, a bridge to the BR Tower's top, down to the library
    walk((368, 240, 420, 262), L2, "ns")
    walk((420, 222, 510, 262), L2, "ns")
    stairs((510, 222, 622, 262), L2, L3, "e")
    walk((622, 222, 662, 313), L3, "ne")
    r = R(622, 262, 626, 285)
    box(r[0], r[1], L3, r[2], r[3], L3 + 24, GOLD, "rail")
    walk((572, 285, 622, 313), L3, "ns")
    stairs((622, 313, 662, 425), L2, L3, "n")
    walk((545, 425, 662, 465), L2, "se")
    # ---- lights: green below the lift, violet and cyan on the walkways, gold on the tops
    for px, py, z, v, c in (
            (293, 30, L1 + 150, 420, (0.2, 1.0, 0.4)), (293, 110, L1 + 150, 420, (0.3, 1.0, 0.5)),
            (293, 60, L2 + 160, 460, (0.3, 1.0, 1.0)), (293, 130, L2 + 160, 380, (0.6, 0.9, 1.0)),
            (297, 220, L1 + 150, 360, (0.3, 1.0, 0.4)), (294, 320, L1 + 150, 380, (1.0, 0.3, 0.9)),
            (214, 308, L1 + 170, 420, (1.0, 0.2, 0.7)), (211, 160, L1 + 150, 300, (0.8, 0.5, 1.0)), (211, 250, L1 + 150, 280, (0.8, 0.5, 1.0)),
            (294, 190, L2 + 200, 420, (1.0, 1.0, 1.0)), (250, 250, L2 + 260, 520, (0.8, 0.9, 1.0)), (340, 250, L2 + 260, 520, (1.0, 0.9, 0.7)),
            (250, 350, L2 + 260, 520, (1.0, 0.8, 0.9)), (345, 360, L2 + 260, 520, (0.8, 1.0, 0.9)),
            (128, 68, L1 + 150, 340, (0.5, 0.6, 1.0)), (128, 180, L1 + 150, 340, (0.5, 0.6, 1.0)), (190, 78, L1 + 150, 300, (0.5, 0.6, 1.0)),
            (128, 68, L2 + 200, 420, (1.0, 0.9, 0.2)), (128, 180, L2 + 200, 380, (0.4, 0.8, 1.0)), (190, 78, L2 + 200, 340, (0.4, 0.8, 1.0)),
            (115, 340, L1 + 150, 420, (1.0, 0.7, 0.5)), (115, 420, L1 + 150, 380, (1.0, 0.7, 0.5)),
            (115, 340, L2 + 160, 420, (0.6, 0.8, 1.0)), (115, 420, L2 + 160, 380, (0.6, 0.8, 1.0)),
            (120, 365, L3 + 220, 600, (1.0, 0.85, 0.3)), (43, 350, L1 + 150, 260, (1.0, 1.0, 1.0)), (79, 350, L2 + 180, 260, (1.0, 1.0, 1.0)),
            (190, 316, L2 + 200, 320, (1.0, 1.0, 1.0)),
            (512, 320, L1 + 150, 460, (1.0, 0.4, 0.4)), (512, 330, L2 + 160, 460, (1.0, 0.6, 0.9)), (512, 318, L3 + 220, 600, (1.0, 0.85, 0.3)),
            (410, 317, L2 + 200, 340, (1.0, 1.0, 1.0)), (526, 392, L2 + 180, 300, (1.0, 0.7, 0.9)), (526, 392, L1 + 150, 300, (1.0, 0.5, 0.5)),
            (450, 443, L1 + 150, 460, (1.0, 0.6, 0.3)), (358, 470, L2 + 160, 380, (0.7, 1.0, 0.5)), (432, 470, L2 + 160, 380, (1.0, 0.5, 0.9)),
            (508, 470, L2 + 160, 380, (0.5, 0.9, 1.0)),
            (360, 330, L1 + 150, 320, (0.9, 0.9, 1.0)), (379, 390, L1 + 150, 340, (0.3, 1.0, 1.0)),
            (394, 250, L2 + 200, 320, (0.8, 0.6, 1.0)), (465, 242, L2 + 200, 360, (0.8, 0.6, 1.0)), (566, 242, L2 + 320, 400, (0.8, 0.6, 1.0)),
            (642, 250, L3 + 200, 460, (0.3, 1.0, 0.9)), (597, 299, L3 + 200, 320, (1.0, 1.0, 1.0)), (642, 370, L2 + 320, 400, (0.3, 1.0, 0.9)),
            (600, 445, L2 + 200, 380, (0.3, 1.0, 0.9)),
            (350, 150, ROOF - 140, 900, (0.7, 0.8, 1.0)), (120, 200, ROOF - 140, 900, (0.7, 0.8, 1.0)), (560, 150, ROOF - 140, 900, (0.9, 0.7, 1.0)),
            (350, 420, ROOF - 140, 900, (0.7, 0.8, 1.0)), (600, 420, ROOF - 140, 900, (0.7, 1.0, 0.9)), (120, 480, ROOF - 140, 900, (1.0, 0.8, 0.8))):
        lamp(px, py, z, v, c)
    # ---- items and spawns from the layout the editor writes
    for s in layout.get("spawns", []):
        spawns.append((s["x"], s["y"], s["z"] + 24, s.get("angle", 0)))
    for it in layout.get("items", []):
        extra.append('{{\n"classname" "{}"\n"origin" "{} {} {}"\n}}'.format(it["class"], int(it["x"]), int(it["y"]), int(it["z"]) + 24))


def first_layout():
    """the first placement (plan pixels and a floor), written when maps/lockout/layout.json does not exist or with --reset"""
    items = [("weapon_railgun", 214, 308, L1, "Halo's sword: the exposed walkway under the centre"),
             ("weapon_rocketlauncher", 293, 118, L1, "Halo's shotgun: the green room under the lift"),
             ("weapon_lightning", 293, 110, L2, "Top of the lift, where it lands"),
             ("weapon_rocketlauncher", 512, 325, L3, "Second rocket launcher: top of the BR Tower"),
             ("weapon_plasmagun", 432, 480, L2, "Library, middle bay"),
             ("weapon_grenadelauncher", 450, 443, L1, "Library, bottom floor"),
             ("weapon_shotgun", 530, 330, L1, "BR Tower, bottom floor"),
             ("item_armor_combat", 128, 68, L2, "Yellow armor: the L of the elbow"),
             ("item_armor_body", 130, 432, L3, "Red armor: top of the Sniper Tower"),
             ("item_health_mega", 379, 395, L1, "Mega: bottom corridor, under the drop from the centre"),
             ("item_armor_combat", 520, 495, L2, "Second yellow armor: library, east bay"),
             ("item_health_large", 642, 245, L3, "Top corner of the loop"),
             ("item_health_large", 211, 150, L1, "Side room west of the lift"),
             ("item_health", 240, 245, L2, "Centre, north-west"), ("item_health", 345, 365, L2, "Centre, south-east"),
             ("item_health", 130, 330, L2, "Sniper Tower, main floor"), ("item_health", 480, 345, L2, "BR Tower, main floor"),
             ("item_health", 128, 180, L1, "Lower elbow"), ("item_health", 465, 242, L2, "Loop, north leg"),
             ("item_armor_shard", 294, 190, L2, "Bridge: lift to centre"), ("item_armor_shard", 190, 316, L2, "Bridge: centre to Sniper Tower"),
             ("item_armor_shard", 410, 317, L2, "Walkway: centre to BR Tower"), ("item_armor_shard", 211, 340, L1, "Stub off the rail walkway"),
             ("item_armor_shard", 350, 330, L1, "Bottom corridor"), ("item_armor_shard", 600, 445, L2, "Loop, south leg"),
             ("ammo_rockets", 330, 140, L1, "Green room"), ("ammo_rockets", 540, 345, L2, "BR Tower, main floor"),
             ("ammo_slugs", 294, 335, L1, "Bottom mid"), ("ammo_lightning", 255, 140, L2, "Lift room, main floor"),
             ("ammo_cells", 350, 495, L2, "Library, west bay"), ("ammo_grenades", 520, 443, L1, "Library, bottom floor"),
             X]
    sp = [(120, 430, L1, 90), (130, 400, L2, 0), (293, 145, L2, 270), (240, 365, L2, 45), (350, 500, L2, 90), (480, 350, L2, 180),
          (400, 443, L1, 0), (450, 242, L2, 180), (128, 250, L1, 270), (560, 330, L1, 180)]
    return dict(version=2, note="items and spawns for maps/lockout; z is the floor height (the generator adds 24). Edit with the editor page, then run tools/make_lockout_map.py",
                items=[{"id": "i%02d" % k, "class": c, "x": mx(px), "y": my(py), "z": z, "label": l} for k, (c, px, py, z, l) in enumerate(items)],
                spawns=[{"id": "s%02d" % k, "x": mx(px), "y": my(py), "z": z, "angle": a} for k, (px, py, z, a) in enumerate(sp)])


def main():
    import sys
    path = os.path.join(ROOT, "maps", "lockout", "layout.json")
    if "--reset" in sys.argv or not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            json.dump(first_layout(), f, indent=1)
    with open(path, encoding="utf-8") as f:
        layout = json.load(f)
    build(layout)
    ents = ['{\n"classname" "worldspawn"\n"message" "BobbyBones: Lockout"\n"_ambient" "45"\n"_color" "1 1 1"\n' + "\n".join(brushes) + "\n}"]
    for x, y, z, a in spawns:
        ents.append('{{\n"classname" "info_player_deathmatch"\n"origin" "{} {} {}"\n"angle" "{}"\n}}'.format(int(x), int(y), int(z), int(a)))
    ents += extra
    for x, y, z, v, c in lights:
        ents.append('{{\n"classname" "light"\n"origin" "{} {} {}"\n"light" "{}"\n"_color" "{} {} {}"\n}}'.format(int(x), int(y), int(z), v, *c))
    os.makedirs(os.path.join(ROOT, "data", "lab", "maps"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "lab", "maps", "lockout.map"), "w", newline="\n") as f:
        f.write("\n".join(ents) + "\n")
    levels = [["low", L1, "Bottom"], ["mid", L2, "Main"], ["top", L3, "Tops"]]
    pl = dict(size=[X, Y], levels=levels, boxes=[b for b in plan if b[6] not in ("shell", "pit")])
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
        json.dump(dict(map="lockout", stations={}, courses={}, ambient=45, hurt=[[0, 0, PIT + 40, X, Y, PIT + 300, 100000]],
                       yard=dict(bounds=[0, 0, X, Y], z=8, spots=spots, items=True)), f, indent=1)
    print("lockout: {} brushes, {} lights, {} spawns, {} items -> data/lab/maps/lockout.map".format(
        len(brushes), len(lights), len(spawns), len(layout.get("items", []))))


if __name__ == "__main__":
    main()

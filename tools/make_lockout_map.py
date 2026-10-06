"""Build "lockout": a Quake Live duel map after the layout of Halo 2's Lockout (from public descriptions, not from the game's
files: the proportions and details are ours). Items, weapons and spawns come from maps/lockout/layout.json, which the
editor (maps/lockout/editor.html) changes; the walls and floors are in this file.

    python tools/make_lockout_map.py       # writes data/lab/maps/lockout.map, maps/lockout/plan.json, maps/lockout/rooms.json
    bash tools/build_lockout.sh            # compiles it (q3map2, mbspc) and packs maps/lockout/lockout.pk3

Layout (x east, y north, units; inside 2944 x 2432; floors at 0 "low", 192 "mid", perches 352 and 416):
  centre deck      896 x 704 slab at mid. Under it the hall (shotgun, two skin-lined "chambers" in the north corners).
  gravity lift     open well south of the centre, a jump pad throws you up onto the lift top at the deck's south edge.
  elbow            a covered corridor from the lift well east, then north into the Sniper Tower's ground floor.
  Sniper Tower     east: ground floor, stairs up to the second floor, stairs on to the perch (railgun) at 416.
  BR Tower         west: the same, mirrored, the perch (lightning gun) at 352.
  library          north: a closed building at mid, bridged to the centre deck and to both towers' terraces.
  yards            ground level all round, cover blocks, stairs down from each terrace.
Every texture name is one the game's own maps use (the ones the training arena already uses)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
X, Y = 2944, 2432
LOW, MID, ROOF = 0, 192, 704
brushes, lights, spawns, extra, plan = [], [], [], [], []

# textures: cold blue-grey stone for the Forerunner parts, gold and pentagrams where it should hurt the eyes
F1, F2, METAL, STAIR = "gothic_floor/largerblock3b3", "gothic_floor/largerblock3b3dim", "base_floor/clangdark", "gothic_floor/xstairtop4"
BRICK, BLK, KILL, IRON = "gothic_wall/streetbricks10", "gothic_block/blocks18c", "gothic_trim/skullsvertgray02a", "gothic_wall/iron01_e"
RUST, DARK, GOLD, CEIL = "gothic_trim/pitted_rust2", "gothic_block/dark_block", "gothic_wall/metaltech16gold", "gothic_ceiling/woodceiling1a"
PENT, SKIN, BOUNCE = "gothic_floor/metalbridge06_pent45", "skin/skin6", "gothic_floor/metalbridge06"
PENTLIGHT, SKULL, CONC = "gothic_light/pentagram_light1_5K", "gothic_light/skulllight01", "base_wall/concrete"
FACE = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) {} 0 0 0 0.5 0.5 0 0 0"


def box(x0, y0, z0, x1, y1, z1, tex=CONC, kind="wall"):
    x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
    p = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
         (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
    brushes.append("{\n" + "\n".join(FACE.format(*[int(round(v)) for v in q], tex) for q in p) + "\n}")
    plan.append([x0, y0, x1, y1, z0, z1, kind])


def trigger(kind, x0, y0, z0, x1, y1, z1, dest, n, angle=None):
    f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) common/trigger 0 0 0 0.5 0.5 0 0 0"
    p = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
         (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
    br = "{\n" + "\n".join(f.format(*[int(round(v)) for v in q]) for q in p) + "\n}"
    extra.append('{{\n"classname" "{}"\n"target" "lo_t{}"\n{}\n}}'.format(kind, n, br))
    extra.append('{{\n"classname" "target_position"\n"targetname" "lo_t{}"\n"origin" "{} {} {}"\n}}'.format(n, *[int(v) for v in dest]))


def wallh(y, x0, x1, z0, z1, gaps=(), tex=BLK, t=32, lintel=None, put=None):
    """a wall along x at y..y+t from x0 to x1 with doorways (gaps = [(a, b)]); the lintel starts at z0 + 128 (or `lintel`)"""
    top = lintel if lintel is not None else z0 + 128
    box_ = put or box
    cuts = [x0] + [v for g in sorted(gaps) for v in g] + [x1]
    for a, b in zip(cuts[0::2], cuts[1::2]):
        if b > a:
            box_(a, y, z0, b, y + t, z1, tex)
    for a, b in gaps:
        box_(a, y, top, b, y + t, z1, tex)


def wallv(x, y0, y1, z0, z1, gaps=(), tex=BLK, t=32, lintel=None, put=None):
    top = lintel if lintel is not None else z0 + 128
    box_ = put or box
    cuts = [y0] + [v for g in sorted(gaps) for v in g] + [y1]
    for a, b in zip(cuts[0::2], cuts[1::2]):
        if b > a:
            box_(x, a, z0, x + t, b, z1, tex)
    for a, b in gaps:
        box_(x, a, top, x + t, b, z1, tex)


def tower(m, perch, name):
    """the east tower (m = 1) or its mirror (m = -1) with a perch at height `perch`. Coordinates are written for the east one."""
    def B(x0, y0, z0, x1, y1, z1, tex=CONC, kind="wall"):
        if m == 1:
            box(x0, y0, z0, x1, y1, z1, tex, kind)
        else:
            box(X - x0, y0, z0, X - x1, y1, z1, tex, kind)
    # outer walls up to 352. West (towards the centre): a ground door and, above the second floor, the bridge door
    wallv(2112, 928, 1504, 0, MID, [(1088, 1184)], put=B)
    wallv(2112, 928, 1504, MID, 352, [(1152, 1280)], lintel=296, put=B)
    wallh(928, 2112, 2624, 0, 352, [(2144, 2272)], put=B)                      # south: the elbow's door
    wallv(2592, 928, 1504, 0, 352, [(1088, 1184)], put=B)                      # east: a ground door to the yard
    wallh(1472, 2112, 2624, 0, MID, put=B)                                     # north: the terrace door at the second floor
    wallh(1472, 2112, 2624, MID, 352, [(2200, 2328)], lintel=296, put=B)
    # second floor (a slab at 160 - 192) with the stairwell open on the south side
    B(2112, 1056, 160, 2624, 1504, 192, F1, "deck")
    B(2528, 928, 160, 2624, 1056, 192, F1, "deck")
    B(2112, 928, 160, 2144, 1056, 192, F1, "deck")
    for k in range(12):                                                        # stairs from the ground floor, east
        B(2144 + 32 * k, 960, 0, 2144 + 32 * (k + 1), 1056, 16 * (k + 1), STAIR, "stairs")
    n = (perch - MID) // 16
    for k in range(n):                                                         # stairs from the second floor to the perch, north
        B(2560, 1056 + 20 * k, MID, 2624, 1056 + 20 * (k + 1), MID + 16 * (k + 1), STAIR, "stairs")
    ye = 1056 + 20 * n
    B(2336, ye, perch - 32, 2624, 1504, perch, PENT, "deck")                   # the perch
    B(2336, ye, perch, 2352, 1504, perch + 40, GOLD, "rail")
    B(2336, 1488, perch, 2624, 1504, perch + 40, GOLD, "rail")
    B(2608, ye, perch, 2624, 1504, perch + 40, GOLD, "rail")
    # the terrace north of the tower: solid block with its top at the second floor; a bridge to the library; stairs down
    B(2112, 1504, 0, 2624, 2016, MID, F2, "deck")
    B(2112, 1504, MID, 2624, 1520, MID + 40, GOLD, "rail")
    B(2112, 2000, MID, 2624, 2016, MID + 40, GOLD, "rail")
    B(2608, 1504, MID, 2624, 2016, MID + 40, GOLD, "rail")
    B(1792, 1856, 160, 2112, 1984, MID, METAL, "deck")                         # bridge to the library
    B(1792, 1856, MID, 2112, 1872, MID + 40, GOLD, "rail")
    B(1792, 1968, MID, 2112, 1984, MID + 40, GOLD, "rail")
    for k in range(12):                                                        # stairs down to the yard
        B(2624 + 32 * k, 1600, 0, 2656 + 32 * k, 1728, MID - 16 * k, STAIR, "stairs")
    # lighting
    col = (0.6, 0.8, 1.0) if m == 1 else (1.0, 0.7, 0.95)
    for (lx, ly, lz) in ((2368, 1144, 120), (2368, 1400, 330), (2480, 1400, perch + 120), (2208, 1240, 300)):
        lights.append((lx if m == 1 else X - lx, ly, lz, 420, col))


def build(layout):
    # ---- shell: the ground, four walls, the roof
    box(-32, -32, -64, X + 32, Y + 32, 0, F2, "floor")
    box(-32, -32, 0, 0, Y + 32, ROOF + 32, DARK)
    box(X, -32, 0, X + 32, Y + 32, ROOF + 32, DARK)
    box(0, -32, 0, X, 0, ROOF + 32, DARK)
    box(0, Y, 0, X, Y + 32, ROOF + 32, DARK)
    box(-32, -32, ROOF, X + 32, Y + 32, ROOF + 32, CEIL)
    # ---- the centre deck and the hall under it
    box(1024, 864, 160, 1920, 1568, MID, F1, "deck")
    wallh(864, 1024, 1920, 0, 160, [(1344, 1472)])                              # south: to the lift tunnel
    wallv(1024, 896, 1568, 0, 160, [(1120, 1248)])                              # west door
    wallv(1888, 896, 1568, 0, 160, [(1120, 1248)])                              # east door
    wallh(1536, 1056, 1888, 0, 160, [(1344, 1472)])                             # north door
    for px, py in ((1184, 1056), (1696, 1056), (1184, 1312), (1696, 1312)):
        box(px, py, 0, px + 64, py + 64, 160, IRON, "pillar")
    for cx0, cx1 in ((1056, 1280), (1664, 1888)):                               # the two green chambers (skin walls)
        gx = (1136, 1200) if cx0 == 1056 else (1744, 1808)
        wallh(1376, cx0, cx1, 0, 160, [gx], SKIN, 24, lintel=120)
        box(1264 if cx0 == 1056 else 1664, 1400, 0, 1280 if cx0 == 1056 else 1680, 1536, 160, SKIN)
    # ---- the gravity lift: an open well, a pad, the lift top on the deck's south edge
    wallv(1248, 256, 640, 0, 224, [(320, 448)])                                 # well walls (doors east and west)
    wallv(1536, 256, 640, 0, 224, [(320, 448)])
    wallh(256, 1248, 1568, 0, 224, [(1344, 1472)])                              # well south wall, a door to the yard
    wallv(1248, 640, 864, 0, 224)                                               # the tunnel under the lift top
    wallv(1536, 640, 864, 0, 224)
    box(1248, 640, 160, 1568, 864, MID, BOUNCE, "deck")                         # lift top
    box(1248, 640, MID, 1264, 864, MID + 40, GOLD, "rail")
    box(1552, 640, MID, 1568, 864, MID + 40, GOLD, "rail")
    box(1344, 448, 0, 1472, 576, 2, PENT, "pad")
    trigger("trigger_push", 1360, 464, 2, 1456, 560, 18, (1408, 640, 330), 1)
    # ---- the elbow: a covered corridor from the well's east door, then north to the Sniper Tower
    box(1568, 288, 0, 2304, 320, 160, BLK)
    box(1568, 448, 0, 2144, 480, 160, BLK)
    box(2112, 480, 0, 2144, 928, 160, BLK)
    box(2272, 320, 0, 2304, 928, 160, BLK)
    box(1568, 320, 128, 2272, 448, 160, METAL, "deck")                          # roof of the first leg
    box(2144, 448, 128, 2272, 928, 160, METAL, "deck")                          # roof of the second leg
    # ---- the two towers: east (the sniper), west (the battle rifle)
    tower(1, 416, "sniper")
    tower(-1, 352, "br")
    # ---- the library: a closed building at mid on a solid base
    box(1152, 1792, 0, 1792, 2336, MID, F2, "deck")
    wallh(1792, 1152, 1792, MID, 448, [(1312, 1504)], BRICK, lintel=MID + 104)
    wallh(2304, 1152, 1792, MID, 448, [], BRICK)
    wallv(1152, 1792, 2336, MID, 448, [(1856, 1984)], BRICK, lintel=MID + 104)
    wallv(1760, 1792, 2336, MID, 448, [(1856, 1984)], BRICK, lintel=MID + 104)
    box(1152, 1792, 448, 1792, 2336, 480, CEIL)
    for sx in (1216, 1344, 1472, 1600):                                        # the stacks
        box(sx, 2112, MID, sx + 32, 2272, MID + 128, GOLD, "cover")
    box(1312, 1568, 160, 1504, 1792, MID, METAL, "deck")                        # bridge from the deck
    box(1312, 1568, MID, 1328, 1792, MID + 40, GOLD, "rail")
    box(1488, 1568, MID, 1504, 1792, MID + 40, GOLD, "rail")
    # ---- cover in the yards: a pentagram plinth and skull pillars (they are meant to be loud)
    for cx, cy in ((400, 400), (2544, 400), (400, 2032), (2544, 2032), (700, 700), (2244, 700)):
        box(cx - 64, cy - 64, 0, cx + 64, cy + 64, 96, PENT, "cover")
        box(cx - 24, cy - 24, 96, cx + 24, cy + 24, 192, KILL, "cover")
    box(1056, 300, 0, 1120, 364, 128, IRON, "cover")
    box(1824, 300, 0, 1888, 364, 128, IRON, "cover")
    # ---- lights: cyan over the lift, green in the hall and chambers, gold up top, a different tint over each yard
    for (lx, ly, lz, v, c) in (
            (1408, 420, 400, 700, (0.3, 1.0, 1.0)), (1408, 760, 330, 320, (0.5, 0.9, 1.0)),
            (1250, 1040, 120, 360, (0.4, 1.0, 0.5)), (1680, 1040, 120, 360, (0.4, 1.0, 0.5)), (1470, 1300, 120, 360, (0.5, 1.0, 0.6)),
            (1168, 1470, 100, 300, (0.1, 1.0, 0.2)), (1776, 1470, 100, 300, (0.1, 1.0, 0.2)),
            (1472, 1216, 330, 520, (1.0, 0.9, 0.5)), (1130, 1300, 330, 360, (1.0, 0.8, 0.5)), (1810, 1300, 330, 360, (1.0, 0.8, 0.5)),
            (1472, 1680, 300, 300, (1.0, 1.0, 1.0)),
            (1472, 2060, 380, 520, (1.0, 0.5, 0.9)), (1250, 2200, 330, 300, (1.0, 0.7, 0.4)), (1700, 2200, 330, 300, (1.0, 0.7, 0.4)),
            (1850, 1920, 330, 300, (0.9, 1.0, 0.6)), (1100, 1920, 330, 300, (0.9, 1.0, 0.6)),
            (1850, 400, 100, 300, (0.7, 0.8, 1.0)), (2200, 400, 100, 300, (0.7, 0.8, 1.0)), (2200, 700, 100, 300, (0.7, 0.8, 1.0)),
            (400, 400, 560, 700, (1.0, 0.6, 0.2)), (2544, 400, 560, 700, (0.3, 1.0, 0.8)),
            (400, 2032, 560, 700, (0.9, 0.4, 1.0)), (2544, 2032, 560, 700, (1.0, 0.95, 0.3)),
            (700, 1200, 560, 600, (1.0, 0.5, 0.7)), (2244, 1200, 560, 600, (0.5, 0.7, 1.0)),
            (1472, 600, 560, 600, (0.9, 1.0, 0.5)), (1472, 1250, 600, 700, (0.8, 0.9, 1.0)),
            (400, 1200, 300, 400, (1.0, 0.9, 0.8)), (2544, 1200, 300, 400, (1.0, 0.9, 0.8)),
            (2870, 1650, 300, 300, (1.0, 0.8, 0.5)), (80, 1650, 300, 300, (1.0, 0.8, 0.5))):
        lights.append((lx, ly, lz, v, c))
    # ---- items and spawns from the layout the editor writes
    for s in layout.get("spawns", []):
        spawns.append((s["x"], s["y"], s["z"] + 24, s.get("angle", 0)))
    for it in layout.get("items", []):
        extra.append('{{\n"classname" "{}"\n"origin" "{} {} {}"\n}}'.format(it["class"], int(it["x"]), int(it["y"]), int(it["z"]) + 24))


def main():
    with open(os.path.join(ROOT, "maps", "lockout", "layout.json"), encoding="utf-8") as f:
        layout = json.load(f)
    build(layout)
    ents = ['{\n"classname" "worldspawn"\n"message" "BobbyBones: Lockout"\n"_ambient" "55"\n"_color" "1 1 1"\n' + "\n".join(brushes) + "\n}"]
    for x, y, z, a in spawns:
        ents.append('{{\n"classname" "info_player_deathmatch"\n"origin" "{} {} {}"\n"angle" "{}"\n}}'.format(int(x), int(y), int(z), int(a)))
    ents += extra
    for x, y, z, v, c in lights:
        ents.append('{{\n"classname" "light"\n"origin" "{} {} {}"\n"light" "{}"\n"_color" "{} {} {}"\n}}'.format(int(x), int(y), int(z), v, *c))
    os.makedirs(os.path.join(ROOT, "data", "lab", "maps"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "lab", "maps", "lockout.map"), "w", newline="\n") as f:
        f.write("\n".join(ents) + "\n")
    with open(os.path.join(ROOT, "maps", "lockout", "plan.json"), "w", newline="\n") as f:
        json.dump(dict(size=[X, Y], levels=dict(low=LOW, mid=MID, br_perch=352, sniper_perch=416), boxes=plan), f)
    spots = [[s["x"], s["y"], s["z"] + 8] for s in layout.get("spawns", [])]
    with open(os.path.join(ROOT, "maps", "lockout", "rooms.json"), "w", newline="\n") as f:
        json.dump(dict(map="lockout", stations={}, courses={}, ambient=55, yard=dict(bounds=[0, 0, X, Y], z=8, spots=spots, items=True)), f, indent=1)
    print("lockout: {} brushes, {} lights, {} spawns, {} items -> data/lab/maps/lockout.map".format(
        len(brushes), len(lights), len(spawns), len(layout.get("items", []))))


if __name__ == "__main__":
    main()

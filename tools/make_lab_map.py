"""Build the test map "bobbylab": one map with every test room, so the suite never changes maps.

    python tools/make_lab_map.py            # writes data/lab/bobbylab.map and maps/bobbylab/rooms.json
    (then compile, see the end of this file's output)

Areas (flat walls, stock textures):
  aim box          empty box 1536 x 1024 x 400: subject at one end, target about 700 units away
  environment box  1536 x 1536 x 400: pillars, two low walls, a platform with steps
  movement courses speed straight (20480 x 512, a mark every 2048 units), gaps (pits of growing width), ramps and
                   stairs up and down, slalom (walls from alternating sides)
Needs the real maps in data/maps/ (extracted from the game) and sim/qsim built.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
FLOOR, WALL, BLOCK, TRIM = "base_floor/concretefloor1", "base_wall/concrete", "gothic_block/blocks18c", "base_floor/clang_floor"
VOX = 8
brushes, lights, spawns = [], [], []


def box(x0, y0, z0, x1, y1, z1, tex=WALL):
    f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) {} 0 0 0 0.5 0.5 0 0 0"
    p = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
         (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
    brushes.append("{\n" + "\n".join(f.format(*[int(round(v)) for v in q], tex) for q in p) + "\n}")


def ramp(x0, y0, x1, y1, za, zb, base, tex=TRIM):
    """a brush whose top slopes from height za at x0 to zb at x1 (bottom at base)"""
    f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) {} 0 0 0 0.5 0.5 0 0 0"
    zt = max(za, zb)
    p = [(x1, y1, zb, x1, y0, zb, x0, y1, za), (x1, y1, zt, x0, y1, zt, x1, y1, base), (x1, y1, zt, x1, y1, base, x1, y0, zt),
         (x0, y0, base, x1, y0, base, x0, y1, base), (x0, y0, base, x0, y0, zt, x1, y0, base), (x0, y0, base, x0, y1, base, x0, y0, zt)]
    brushes.append("{\n" + "\n".join(f.format(*[int(round(v)) for v in q], tex) for q in p) + "\n}")


def room(x0, y0, z0, x1, y1, z1, t=32, floor=FLOOR):
    """hollow sealed box with the given inside dimensions, lit from the ceiling"""
    box(x0 - t, y0 - t, z0 - t, x1 + t, y1 + t, z0, floor)
    box(x0 - t, y0 - t, z1, x1 + t, y1 + t, z1 + t)
    box(x0 - t, y0 - t, z0, x0, y1 + t, z1)
    box(x1, y0 - t, z0, x1 + t, y1 + t, z1)
    box(x0, y0 - t, z0, x1, y0, z1)
    box(x0, y1, z0, x1, y1 + t, z1)
    for x in np.arange(x0 + 192, x1, 384):
        for y in np.arange(y0 + 192, y1, 384):
            lights.append((x, y, z1 - 24, 500))


def copy_region(world, lo, hi):
    """solid voxels of a region of a real map -> merged boxes (in the region's own coordinates, origin at lo)"""
    nx, ny, nz = [int((hi[k] - lo[k]) // VOX) for k in range(3)]
    solid = np.zeros((nx, ny, nz), bool)
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                solid[i, j, k] = world.contents((lo[0] + (i + 0.5) * VOX, lo[1] + (j + 0.5) * VOX,
                                                 lo[2] + (k + 0.5) * VOX)) & 1 != 0
    done = np.zeros_like(solid)
    out = []
    for k in range(nz):
        for j in range(ny):
            i = 0
            while i < nx:
                if not solid[i, j, k] or done[i, j, k]:
                    i += 1
                    continue
                i1 = i
                while i1 < nx and solid[i1, j, k] and not done[i1, j, k]:
                    i1 += 1
                j1 = j + 1
                while j1 < ny and solid[i:i1, j1, k].all() and not done[i:i1, j1, k].any():
                    j1 += 1
                k1 = k + 1
                while k1 < nz and solid[i:i1, j:j1, k1].all() and not done[i:i1, j:j1, k1].any():
                    k1 += 1
                done[i:i1, j:j1, k:k1] = True
                out.append((i * VOX, j * VOX, k * VOX, i1 * VOX, j1 * VOX, k1 * VOX))
                i = i1
    return out, (nx * VOX, ny * VOX, nz * VOX)


def main():
    from qsim import World
    rooms = dict(map="bobbylab", stations={})
    # ---- aim box
    room(0, 0, 0, 1536, 1024, 400)
    box(96, 0, 0, 104, 1024, 1, TRIM)                               # the firing line
    rooms["aim"] = dict(subject=[128, 512, 8], yaw=0, target=[832, 512, 8], zone=[640, 112, 1280, 912])
    spawns.append((128, 512, 24, 0))
    spawns.append((832, 512, 24, 180))
    # ---- environment box
    ey = 3000
    room(0, ey, 0, 1536, ey + 1536, 400)
    for px, py in ((384, 384), (1152, 384), (384, 1152), (1152, 1152)):
        box(px - 48, ey + py - 48, 0, px + 48, ey + py + 48, 400, BLOCK)          # full-height pillars
    for px, py in ((768, 512), (768, 1024)):
        box(px - 32, ey + py - 32, 0, px + 32, ey + py + 32, 128, BLOCK)          # head-high pillars
    box(576, ey + 240, 0, 960, ey + 272, 64, BLOCK)                              # low walls (crouch cover)
    box(576, ey + 1264, 0, 960, ey + 1296, 64, BLOCK)
    box(1280, ey + 576, 0, 1536, ey + 960, 96, TRIM)                             # platform
    for s in range(5):                                                          # steps up to it
        box(1280 - (s + 1) * 32, ey + 672, 0, 1280 - s * 32, ey + 864, 96 - (s + 1) * 16, TRIM)
    rooms["env"] = dict(bounds=[0, ey, 1536, ey + 1536], z=8,
                        spots=[[128, ey + 128], [1408, ey + 128], [128, ey + 1408], [1408, ey + 1408], [768, ey + 768],
                               [128, ey + 768], [768, ey + 128], [768, ey + 1408], [1400, ey + 768]])
    for x, y in rooms["env"]["spots"][:4]:
        spawns.append((x, y, 24, 0))
    # ---- speed straight
    sy = 6000
    SL = 20480                                                                  # long enough to build real speed
    room(0, sy, 0, SL, sy + 512, 256)
    for mark in range(2048, SL, 2048):                                          # distance marks on the floor
        box(mark, sy, 0, mark + 8, sy + 512, 1, TRIM)
    rooms["speed"] = dict(start=[64, sy + 256, 8], yaw=0, far=[SL - 64, sy + 256, 8], length=SL - 128)
    courses = dict(speed=dict(name="Speed straight", start=[64, sy + 256, 8], yaw=0, end_x=SL - 104, fall_z=-1e9,
                              checkpoints=[64], length=SL - 168, y=[sy, sy + 512]))
    # ---- gaps: a long run with pits to jump, each wider than the last (a running jump clears about 220 units)
    gy, x = 12000, 0
    plats, pits = [], []
    for g in (160, 224, 288, 352, 416, 480):
        plats.append((x, x + 1536))
        pits.append((x + 1536, x + 1536 + g))
        x += 1536 + g
    plats.append((x, x + 1536))
    GL = x + 1536
    room(0, gy, -256, GL, gy + 512, 320)
    for a, b in plats:
        box(a, gy, -256, b, gy + 512, 0, FLOOR)
        box(b - 8, gy, 0, b, gy + 512, 1, TRIM)                                   # the edge is marked
    courses["gaps"] = dict(name="Gaps", start=[64, gy + 256, 8], yaw=0, end_x=GL - 104, fall_z=-100,
                           checkpoints=[a + 64 for a, b in plats], length=GL - 168, y=[gy, gy + 512])
    # ---- ramps and stairs, up and down
    ry, x = 14000, 1024
    RH = 640
    feats = []                                      # (kind, length, height before, height after)
    h = 0

    def stairs(up, steps):
        nonlocal x, h
        for k in range(steps):
            z0, z1 = (h + k * 16, h + (k + 1) * 16) if up else (h - (k + 1) * 16, h - k * 16)
            top = z1 if up else z0
            box(x + k * 32, ry, 0, x + (k + 1) * 32, ry + 512, max(top, 1), TRIM)
        x += steps * 32
        h += steps * 16 if up else -steps * 16

    def flat(length):
        nonlocal x
        if h > 0:
            box(x, ry, 0, x + length, ry + 512, h, BLOCK)
        x += length

    def slope(length, dh):
        nonlocal x, h
        ramp(x, ry, x + length, ry + 512, h, h + dh, -16)
        x += length
        h += dh

    stairs(True, 12); flat(512); slope(768, -192); flat(768)
    slope(768, 256); flat(512); stairs(False, 16); flat(768)
    slope(512, 128); h = 0; flat(1024)                                           # a kicker: off the top, back to the floor
    stairs(True, 8); slope(512, -128); flat(768)
    slope(768, 192); flat(384); slope(768, -192); flat(1024)
    RL_ = x
    room(0, ry, 0, RL_, ry + 512, RH)
    courses["ramps"] = dict(name="Ramps and stairs", start=[64, ry + 256, 8], yaw=0, end_x=RL_ - 104, fall_z=-1e9,
                            checkpoints=[64], length=RL_ - 168, y=[ry, ry + 512])
    # ---- slalom: walls from alternating sides, speed has to be kept through the turns
    zy, ZL, ZW = 16000, 10240, 768
    room(0, zy, 0, ZL, zy + ZW, 320)
    for k, wx in enumerate(range(1280, ZL - 640, 1024)):
        if k % 2 == 0:
            box(wx, zy, 0, wx + 64, zy + 448, 320, BLOCK)
        else:
            box(wx, zy + ZW - 448, 0, wx + 64, zy + ZW, 320, BLOCK)
    courses["slalom"] = dict(name="Slalom", start=[64, zy + ZW // 2, 8], yaw=0, end_x=ZL - 104, fall_z=-1e9,
                             checkpoints=[64], length=ZL - 168, y=[zy, zy + ZW])
    rooms["courses"] = courses
    for c in courses.values():
        spawns.append((c["start"][0], c["start"][1], 24, 0))
    # ---- terrain stations: 3D copies of the real spots
    # The trick-jump copies (Campgrounds bridge to rail and pillars, Aerowalk and Blood Run red armor) were
    # removed on 2026-10-04: as test rooms they were not clear enough. copy_region() is kept for later use.
    stations = []
    ox = 0
    for key, mp, lo, hi, info in stations:
        w = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n=2)
        boxes, size = copy_region(w, lo, hi)
        base = (ox, 9000, 0)
        room(base[0], base[1], base[2], base[0] + size[0], base[1] + size[1], base[2] + size[2], floor=TRIM)
        for b in boxes:
            box(base[0] + b[0], base[1] + b[1], base[2] + b[2], base[0] + b[3], base[1] + b[4], base[2] + b[5], BLOCK)

        def conv(p):
            q = [base[0] + p[0] - lo[0], base[1] + p[1] - lo[1]]
            if len(p) > 2:
                z = p[2]
                if z == 0:                                   # 0 = "the floor here": find it on the real map
                    t = w.trace(np.array([p[0], p[1], hi[2] - 8], np.float32), np.array([p[0], p[1], lo[2]], np.float32))
                    z = float(t["endpos"][2]) + 24.0
                q.append(base[2] + z - lo[2])
            return [round(float(v), 1) for v in q]
        st = dict(name=info["name"], source=mp, start=conv(info["start"]), yaw=info["yaw"], goal=conv(info["goal"]),
                  goal_r=info["goal_r"], goal_dz=info["goal_dz"], offset=[base[0] - lo[0], base[1] - lo[1], base[2] - lo[2]])
        if "via" in info:
            st["via"] = [conv(v) for v in info["via"]]
        rooms["stations"][key] = st
        spawns.append((st["start"][0], st["start"][1], st["start"][2] + 8, info["yaw"]))
        print("{}: {} boxes, size {}".format(key, len(boxes), size))
        ox += size[0] + 256
    # ---- write the .map
    ents = ['{\n"classname" "worldspawn"\n"message" "BobbyBones test lab"\n"_ambient" "45"\n"_color" "1 1 1"\n'
            + "\n".join(brushes) + "\n}"]
    for x, y, z, a in spawns:
        ents.append('{{\n"classname" "info_player_deathmatch"\n"origin" "{} {} {}"\n"angle" "{}"\n}}'.format(
            int(x), int(y), int(z), int(a)))
    for x, y, z, v in lights:
        ents.append('{{\n"classname" "light"\n"origin" "{} {} {}"\n"light" "{}"\n}}'.format(int(x), int(y), int(z), v))
    os.makedirs(os.path.join(ROOT, "data", "lab", "maps"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "maps", "bobbylab"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "lab", "maps", "bobbylab.map"), "w", newline="\n") as f:
        f.write("\n".join(ents) + "\n")
    with open(os.path.join(ROOT, "maps", "bobbylab", "rooms.json"), "w", newline="\n") as f:
        json.dump(rooms, f, indent=1)
    print("{} brushes, {} lights, {} spawns -> data/lab/maps/bobbylab.map".format(len(brushes), len(lights), len(spawns)))


if __name__ == "__main__":
    main()

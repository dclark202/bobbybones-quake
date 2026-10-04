"""Build the test map "bobbylab": one map with every test room, so the suite never changes maps.

    python tools/make_lab_map.py            # writes data/lab/bobbylab.map and maps/bobbylab/rooms.json
    (then compile, see the end of this file's output)

Areas (flat walls, stock textures):
  aim box          empty box 1536 x 1024 x 400: subject at one end, target about 700 units away
  environment box  1536 x 1536 x 400: pillars, two low walls, a platform with steps
  speed straight   2048 x 256 flat run
  terrain stations 3D copies (8-unit blocks) of four classic spots on the real maps, sampled with the
                   simulator: Campgrounds bridge-to-rail and pillars, Aerowalk red armor, Blood Run red armor
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
    for s in range(6):                                                          # steps up to it
        box(1280 - (s + 1) * 32, ey + 672, 0, 1280 - s * 32, ey + 864, 96 - (s + 1) * 16, TRIM)
    rooms["env"] = dict(bounds=[0, ey, 1536, ey + 1536], z=8,
                        spots=[[128, ey + 128], [1408, ey + 128], [128, ey + 1408], [1408, ey + 1408], [768, ey + 768],
                               [128, ey + 768], [768, ey + 128], [768, ey + 1408], [1400, ey + 768]])
    for x, y in rooms["env"]["spots"][:4]:
        spawns.append((x, y, 24, 0))
    # ---- speed straight
    sy = 6000
    room(0, sy, 0, 2048, sy + 256, 256)
    box(1984, sy, 0, 1992, sy + 256, 1, TRIM)
    rooms["speed"] = dict(start=[64, sy + 128, 8], yaw=0, far=[1988, sy + 128, 8])
    # ---- terrain stations: 3D copies of the real spots
    stations = [
        ("b2r", "campgrounds", (-320, -1100, 380), (720, 40, 700),
         dict(start=[-100, -920, 545], yaw=0, goal=[448, -160, 528], goal_r=70, goal_dz=20,
              name="Campgrounds bridge to rail")),
        ("pillars", "campgrounds", (-1640, -110, 300), (-1060, 520, 680),
         dict(start=[-1356, 330, 0], yaw=-110, goal=[-1450, 56, 0], goal_r=40, goal_dz=30,
              via=[[-1450, 56], [-1228, 56], [-1356, 330]], name="Campgrounds pillars")),
        ("aero_ra", "aerowalk", (-780, -470, 20), (20, 330, 520),
         dict(start=[-304, 290, 0], yaw=-90, goal=[-384, -70, 352], goal_r=50, goal_dz=24, name="Aerowalk red armor")),
        ("ztn_ra", "bloodrun", (-560, -384, 190), (240, 416, 700),
         dict(start=[160, 300, 0], yaw=-135, goal=[-160, 16, 528], goal_r=50, goal_dz=24, name="Blood Run red armor")),
    ]
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

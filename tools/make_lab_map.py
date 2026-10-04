"""Build the test map "bobbylab": one map with every test room, so the suite never changes maps.

    python tools/make_lab_map.py            # writes data/lab/bobbylab.map and maps/bobbylab/rooms.json
    (then compile, see the end of this file's output)

Areas (flat walls, stock textures):
  aim box          empty box 1536 x 1024 x 400: subject at one end, target about 700 units away
  environment box  1536 x 1536 x 400: pillars, two low walls, a platform with steps
  movement courses speed straight, circle-jump gaps, two-hop gaps, ramps and stairs, slalom, turns (45 / 90 /
                   135 degrees and a hairpin), narrow path, pillars, rocket jumps
Needs the real maps in data/maps/ (extracted from the game) and sim/qsim built.
"""
import json
import math
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


def prism(pts, z0, z1, tex=WALL):
    """a brush with vertical sides over a convex footprint (points counter-clockwise seen from above)"""
    f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) {} 0 0 0 0.5 0.5 0 0 0"
    pts = [(int(round(x)), int(round(y))) for x, y in pts]
    (ax, ay), (bx, by), (cx, cy) = pts[0], pts[1], pts[2]
    faces = [(ax, ay, z1, cx, cy, z1, bx, by, z1), (ax, ay, z0, bx, by, z0, cx, cy, z0)]
    for k in range(len(pts)):
        (px, py), (qx, qy) = pts[k], pts[(k + 1) % len(pts)]
        faces.append((px, py, z0, px, py, z1, qx, qy, z0))
    brushes.append("{\n" + "\n".join(f.format(*q, tex) for q in faces) + "\n}")


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
    rooms["aim"] = dict(subject=[128, 512, 8], yaw=0, target=[832, 512, 8], zone=[640, 112, 1280, 912],
                        target_lg=[576, 512, 8], zone_lg=[384, 192, 800, 832])     # lightning gun reaches 768 units
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
                               [128, ey + 768], [768, ey + 128], [768, ey + 1408], [1400, ey + 768, 104]])
    for x, y in rooms["env"]["spots"][:4]:
        spawns.append((x, y, 24, 0))
    # ---- speed straight
    sy = 6000
    SL = 20480                                                                  # long enough to build real speed
    room(0, sy, 0, SL, sy + 512, 256)
    for mark in range(2048, SL, 2048):                                          # distance marks on the floor
        box(mark, sy, 0, mark + 8, sy + 512, 1, TRIM)
    rooms["speed"] = dict(start=[64, sy + 256, 8], yaw=0, far=[SL - 64, sy + 256, 8], length=SL - 128)
    # Movement courses. Each has: start, yaw, path (the line progress is measured along), end (point and radius),
    # fall_z (below it = fell), checkpoints (where a fall puts the player back: x, y, z, yaw), weapon, hint.
    courses = {}

    def course(key, name, hint, start, path, fall_z=-1e9, checkpoints=None, weapon="g", yaw=0, end_r=120, end_z=None):
        length = sum(math.hypot(path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1]) for k in range(len(path) - 1))
        courses[key] = dict(name=name, hint=hint, start=[float(v) for v in start], yaw=yaw,
                            path=[[float(x), float(y)] for x, y in path], end_r=end_r, end_z=end_z, fall_z=fall_z,
                            checkpoints=checkpoints or [[float(start[0]), float(start[1]), float(start[2]), yaw]],
                            weapon=weapon, length=round(length))
        spawns.append((start[0], start[1], start[2] + 16, yaw))

    course("speed", "Speed straight", "Flat straight: build speed and hold it to the far end.",
           [64, sy + 256, 8], [[64, sy + 256], [SL - 104, sy + 256]])

    def gap_course(key, name, hint, gy, plat, gaps):
        """platforms of length plat separated by pits; a fall puts the player back at the start of that platform"""
        x, plats = 0, []
        for g in gaps:
            plats.append((x, x + plat))
            x += plat + g
        plats.append((x, x + plat))
        L = x + plat
        room(0, gy, -256, L, gy + 512, 320)
        for a_, b_ in plats:
            box(a_, gy, -256, b_, gy + 512, 0, FLOOR)
            box(b_ - 8, gy, 0, b_, gy + 512, 1, TRIM)
        course(key, name, hint, [64, gy + 256, 8], [[64, gy + 256], [L - 104, gy + 256]], fall_z=-100,
               checkpoints=[[a_ + 64, gy + 256, 8, 0] for a_, b_ in plats])

    # a plain running jump clears about 250 units; these need more speed than that
    gap_course("circle", "Circle-jump gaps", "Short platforms: each gap needs one good circle jump from a standing start.",
               12000, 512, (264, 280, 296, 312, 328))
    gap_course("twohop", "Two-hop gaps", "Each platform has room for two jumps: circle jump, one strafe jump, then the gap.",
               13000, 768, (336, 360, 384, 400, 416))
    # ---- ramps and stairs, up and down
    ry, x = 14000, 1024
    RH = 640
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
    course("ramps", "Ramps and stairs", "Stairs and ramps up and down: keep your speed over them.",
           [64, ry + 256, 8], [[64, ry + 256], [RL_ - 104, ry + 256]])
    # ---- slalom: walls from alternating sides
    zy, ZL, ZW = 16000, 10240, 768
    room(0, zy, 0, ZL, zy + ZW, 320)
    for k, wx in enumerate(range(1280, ZL - 640, 1024)):
        if k % 2 == 0:
            box(wx, zy, 0, wx + 64, zy + 448, 320, BLOCK)
        else:
            box(wx, zy + ZW - 448, 0, wx + 64, zy + ZW, 320, BLOCK)
    course("slalom", "Slalom", "Walls from alternating sides: weave through without losing speed.",
           [64, zy + ZW // 2, 8], [[64, zy + ZW // 2], [ZL - 104, zy + ZW // 2]])
    # ---- turns: 45, 90, 135 degrees and a hairpin, in a walled corridor
    ty, W = 20000, 448
    c45 = math.sqrt(0.5)
    P = [(128.0, 0.0)]
    for dx, dy in ((1536, 0), (1280 * c45, 1280 * c45), (1280, 0), (0, 1280), (1536, 0), (-1280 * c45, -1280 * c45),
                   (1536, 0), (0, -640), (-1536, 0)):
        P.append((P[-1][0] + dx, P[-1][1] + dy))
    xs_, ys_ = [q[0] for q in P], [q[1] for q in P]
    shift = (-min(xs_) + 400, ty - min(ys_) + 400)
    P = [(q[0] + shift[0], q[1] + shift[1]) for q in P]
    room(min(q[0] for q in P) - 400, min(q[1] for q in P) - 400, 0, max(q[0] for q in P) + 400, max(q[1] for q in P) + 400, 320)

    def offset_line(pts, d):
        """the path moved sideways by d (left positive), with mitred corners"""
        out = []
        for k in range(len(pts)):
            def nrm(a_, b_):
                l_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
                return (-(b_[1] - a_[1]) / l_, (b_[0] - a_[0]) / l_)
            if k == 0:
                n = nrm(pts[0], pts[1])
                out.append((pts[0][0] + n[0] * d - (pts[1][0] - pts[0][0]) / 1536 * 128, pts[0][1] + n[1] * d))
            elif k == len(pts) - 1:
                n = nrm(pts[-2], pts[-1])
                out.append((pts[-1][0] + n[0] * d, pts[-1][1] + n[1] * d))
            else:
                n1, n2 = nrm(pts[k - 1], pts[k]), nrm(pts[k], pts[k + 1])
                bx_, by_ = n1[0] + n2[0], n1[1] + n2[1]
                bl = math.hypot(bx_, by_)
                bx_, by_ = bx_ / bl, by_ / bl
                m = d / max(0.3, bx_ * n1[0] + by_ * n1[1])
                out.append((pts[k][0] + bx_ * m, pts[k][1] + by_ * m))
        return out

    for side in (1, -1):
        line = offset_line(P, side * W / 2)
        for k in range(len(line) - 1):
            a_, b_ = line[k], line[k + 1]
            l_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
            n = (-(b_[1] - a_[1]) / l_ * side * 32, (b_[0] - a_[0]) / l_ * side * 32)
            quad = [a_, b_, (b_[0] + n[0], b_[1] + n[1]), (a_[0] + n[0], a_[1] + n[1])]
            if side == 1:
                quad = [quad[0], quad[3], quad[2], quad[1]]
            prism(quad, 0, 192, BLOCK)
    course("turns", "Turns", "A corridor with 45, 90 and 135 degree turns and a hairpin: take them as fast as you can.",
           [P[0][0] + 32, P[0][1], 8], P)
    # ---- narrow path over a pit, getting narrower
    ny_ = 24000
    segs = ((96, 1536), (64, 1536), (48, 1536), (32, 1536))
    NL = sum(l_ for w_, l_ in segs) + 512 + 512
    room(0, ny_, -256, NL, ny_ + 512, 320)
    box(0, ny_, -256, 512, ny_ + 512, 0, FLOOR)                                   # start pad
    x, cps, path = 512, [[64, ny_ + 256, 8, 0]], [[64, ny_ + 256]]
    for k, (w_, l_) in enumerate(segs):
        cy = ny_ + 256 + (48 if k % 2 else -48)                                   # the beam jogs sideways each time
        box(x, cy - w_ / 2, -256, x + l_, cy + w_ / 2, 0, TRIM)
        box(x - 64, ny_ + 256 - 128, -256, x + 64, ny_ + 256 + 128, 0, FLOOR)      # a small pad joins the beams
        cps.append([x, ny_ + 256, 8, 0])
        path += [[x, ny_ + 256], [x + 96, cy], [x + l_, cy]]
        x += l_
    box(x - 64, ny_ + 256 - 128, -256, x + 64, ny_ + 256 + 128, 0, FLOOR)
    box(x, ny_, -256, NL, ny_ + 512, 0, FLOOR)                                    # end pad
    path.append([NL - 104, ny_ + 256])
    course("narrow", "Narrow path", "A beam over a pit that gets narrower (96, 64, 48, 32 wide): fast, without falling.",
           [64, ny_ + 256, 8], path, fall_z=-100, checkpoints=cps)
    # ---- pillars: hop from top to top (spacing of the Campgrounds pillars), slight zigzag
    py_, NP, SPC = 26000, 36, 222
    PL = 384 + NP * SPC + 384
    room(0, py_, -256, PL, py_ + 512, 320)
    box(0, py_, -256, 320, py_ + 512, 0, FLOOR)
    path, cps = [[64, py_ + 256]], [[64, py_ + 256, 8, 0]]
    for k in range(NP):
        cx_, cy = 320 + 96 + k * SPC + 32, py_ + 256 + (40 if (k // 3) % 2 else -40)
        box(cx_ - 32, cy - 32, -256, cx_ + 32, cy + 32, 0, BLOCK)
        path.append([cx_, cy])
        if k % 6 == 5:
            cps.append([cx_, cy, 8, 0])
    box(PL - 384, py_, -256, PL, py_ + 512, 0, FLOOR)
    path.append([PL - 104, py_ + 256])
    course("pillars", "Pillars", "Hop from pillar to pillar (64 wide, 222 apart) to the far side.",
           [64, py_ + 256, 8], path, fall_z=-100, checkpoints=cps)
    # ---- rocket jumps: three ledges, each higher than a normal jump reaches
    ky = 28000
    room(0, ky, 0, 2560, ky + 512, 1200)
    tops = (224, 544, 944)                                                         # steps of 224, 320 and 400
    for k, t_ in enumerate(tops):
        box(640 + k * 640, ky, 0, 2560, ky + 512, t_, BLOCK)
    course("rocket", "Rocket jumps", "Rocket launcher, endless ammo: rocket-jump up three ledges (224, 320 and 400 high).",
           [64, ky + 256, 8], [[64, ky + 256], [640, ky + 256], [1280, ky + 256], [1920, ky + 256], [2400, ky + 256]],
           weapon="rl", end_z=tops[-1] - 8)
    rooms["courses"] = courses
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

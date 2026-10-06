"""Build the test map "testlab": one map with every test room, so the suite never changes maps.

    python tools/make_lab_map.py            # writes data/lab/testlab.map and maps/testlab/rooms.json
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
brushes, lights, spawns, extra = [], [], [], []      # extra: whole entities (triggers, items) as text


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
    area = sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1] for k in range(len(pts)))
    if area < 0:                                             # make the footprint counter-clockwise
        pts = pts[::-1]
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
    rooms = dict(map="testlab", stations={})
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

    def gap_course(key, name, hint, gy, plat, gaps, marks=None):
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
            if marks and b_ < L:                             # distances back from the edge: start of the run, first jump
                box(b_ - marks[0] - 48, gy + 128, 0, b_ - marks[0], gy + 384, 1, BLOCK)       # a pad: start here
                box(b_ - marks[1] - 8, gy + 64, 0, b_ - marks[1], gy + 448, 1, TRIM)          # a line: first jump
        back = (marks[0] + 24) if marks else None
        course(key, name, hint, [(plats[0][1] - back) if marks else 64, gy + 256, 8], [[64, gy + 256], [L - 104, gy + 256]],
               fall_z=-100,
               checkpoints=[[(b_ - back) if (marks and b_ < L) else a_ + 64, gy + 256, 8, 0] for a_, b_ in plats])

    # a plain running jump clears about 250 units; these need more speed than that
    gap_course("circle", "Circle-jump gaps", "Short platforms: each gap needs one good circle jump from a standing start.",
               12000, 512, (264, 280, 296, 312, 328))
    gap_course("twohop", "Two-hop gaps", "Start on the dark pad, circle jump at the first line, strafe jump, take off again at the edge.",
               13000, 768, (336, 360, 384, 400, 416), marks=(480, 330))
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

    # Walls: one plain rectangle per straight and side, no mitred corners (their odd angles gave the bot
    # navigation compiler more planes than it accepts). The outer wall of a turn runs on to the corner, the
    # inner one stops short of it.
    for side in (1, -1):
        for k in range(len(P) - 1):
            a_, b_ = P[k], P[k + 1]
            l_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
            u = ((b_[0] - a_[0]) / l_, (b_[1] - a_[1]) / l_)
            n = (-u[1] * side, u[0] * side)
            ext = []
            for v, (p0, p1, p2) in ((0, (P[k - 1] if k else None, a_, b_)), (1, (a_, b_, P[k + 2] if k + 2 < len(P) else None))):
                if p0 is None or p2 is None:
                    ext.append(128.0 if v == 0 else 0.0)
                    continue
                d1 = (p1[0] - p0[0], p1[1] - p0[1])
                d2 = (p2[0] - p1[0], p2[1] - p1[1])
                cr = d1[0] * d2[1] - d1[1] * d2[0]
                th = abs(math.atan2(cr, d1[0] * d2[0] + d1[1] * d2[1]))
                m = (W / 2) * math.tan(th / 2)
                inner = (cr > 0) == (side == 1)
                if inner:
                    ext.append(-m)
                elif m <= 260:
                    ext.append(m + 32.0 * math.tan(th / 2))
                else:
                    # a sharp turn: running both outer walls on to the corner would cut into other parts of the
                    # corridor, so they stop early and a short wall across the corner closes it
                    ext.append(256.0)
                    if v == 0 and side in (1, -1):
                        u1 = (d1[0] / math.hypot(*d1), d1[1] / math.hypot(*d1))
                        u2 = (d2[0] / math.hypot(*d2), d2[1] / math.hypot(*d2))
                        n1, n2 = (-u1[1] * side, u1[0] * side), (-u2[1] * side, u2[0] * side)
                        e1 = (p1[0] + u1[0] * 256 + n1[0] * W / 2, p1[1] + u1[1] * 256 + n1[1] * W / 2)
                        e2 = (p1[0] - u2[0] * 256 + n2[0] * W / 2, p1[1] - u2[1] * 256 + n2[1] * W / 2)
                        mid = ((e1[0] + e2[0]) / 2 - p1[0], (e1[1] + e2[1]) / 2 - p1[1])
                        ml = math.hypot(*mid)
                        o = (mid[0] / ml * 32, mid[1] / ml * 32)
                        prism([e1, e2, (e2[0] + o[0], e2[1] + o[1]), (e1[0] + o[0], e1[1] + o[1])], 0, 192, BLOCK)
            s0 = (a_[0] - u[0] * ext[0], a_[1] - u[1] * ext[0])
            s1 = (b_[0] + u[0] * ext[1], b_[1] + u[1] * ext[1])
            if math.hypot(s1[0] - s0[0], s1[1] - s0[1]) < 16 or (s1[0] - s0[0]) * u[0] + (s1[1] - s0[1]) * u[1] <= 0:
                continue
            d0, d1_ = W / 2, W / 2 + 32
            prism([(s0[0] + n[0] * d0, s0[1] + n[1] * d0), (s1[0] + n[0] * d0, s1[1] + n[1] * d0),
                   (s1[0] + n[0] * d1_, s1[1] + n[1] * d1_), (s0[0] + n[0] * d1_, s0[1] + n[1] * d1_)], 0, 192, BLOCK)
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
    py_, NP, SPC = 26000, 18, 222
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
    room(0, ky, 0, 3200, ky + 512, 1500)
    tops = (160, 384, 664, 1112)                                                   # steps of 160, 224, 280 and 448 (two rockets)
    for k, t_ in enumerate(tops):
        box(640 + k * 640, ky, 0, 3200, ky + 512, t_, BLOCK)
    course("rocket", "Rocket jumps", "Rocket launcher, endless ammo: rocket-jump up four ledges (160, 224, 280, and 448: that one needs a double rocket jump).",
           [64, ky + 256, 8], [[64, ky + 256], [640, ky + 256], [1280, ky + 256], [1920, ky + 256], [2560, ky + 256], [3040, ky + 256]],
           weapon="rl", end_z=tops[-1] - 8)

    # ================= rooms added 2026-10-04 (evening): bends, pads, drops, climb, dodge, peek, items =================
    def strip(pts, width, z0, z1, tex=FLOOR):
        """a platform along a polyline: one rectangle per leg, run on by half the width at both ends so legs join"""
        for k in range(len(pts) - 1):
            a_, b_ = pts[k], pts[k + 1]
            l_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
            u = ((b_[0] - a_[0]) / l_, (b_[1] - a_[1]) / l_)
            n = (-u[1] * width / 2, u[0] * width / 2)
            s0 = (a_[0] - u[0] * width / 2, a_[1] - u[1] * width / 2)
            s1 = (b_[0] + u[0] * width / 2, b_[1] + u[1] * width / 2)
            prism([(s0[0] + n[0], s0[1] + n[1]), (s1[0] + n[0], s1[1] + n[1]), (s1[0] - n[0], s1[1] - n[1]),
                   (s0[0] - n[0], s0[1] - n[1])], z0, z1, tex)

    # ---- bends: a track with no walls over a pit; speed has to be carried through the bends by air-steering
    by = 46000
    d45 = 724.0                                                                   # 1024 along a 45 degree leg
    B = [(256.0, by + 1500.0)]
    for dx, dy in ((1024, 0), (d45, d45), (512, 0), (2 * d45, -2 * d45), (512, 0), (2 * d45, 2 * d45), (512, 0),
                   (d45, -d45), (1024, 0)):
        B.append((B[-1][0] + dx, B[-1][1] + dy))
    BL = B[-1][0] + 256
    room(0, by, -256, BL, by + 3000, 320)
    strip(B, 320, -256, 0)
    box(0, by + 1244, -256, 416, by + 1756, 0, FLOOR)                             # start pad
    box(BL - 416, B[-1][1] - 256, -256, BL, B[-1][1] + 256, 0, FLOOR)             # end pad
    course("bends", "Bends", "A track with no walls over a pit: carry your speed through the bends.",
           [128, by + 1500, 8], [[128, by + 1500]] + [list(q) for q in B[1:]], fall_z=-100,
           checkpoints=[[128, by + 1500, 8, 0]] + [[q[0], q[1], 8, 0] for q in B[1:-1:2]])

    # ---- pads: a jump pad up to a ledge, a teleporter off it, a jump pad over a wall
    py2 = 32000
    yc = py2 + 256
    room(0, py2, 0, 6400, py2 + 512, 1100)
    box(1800, py2, 0, 3200, py2 + 512, 400, BLOCK)                                # the ledge
    box(4600, py2, 0, 4700, py2 + 512, 300, BLOCK)                                # the wall
    n_t = 0

    def trigger(kind, x0, y0, z0, x1, y1, z1, dest, angle=None):
        nonlocal n_t
        n_t += 1
        f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) common/trigger 0 0 0 0.5 0.5 0 0 0"
        p = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
             (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
        br = "{\n" + "\n".join(f.format(*[int(round(v)) for v in q]) for q in p) + "\n}"
        extra.append('{{\n"classname" "{}"\n"target" "lab_t{}"\n{}\n}}'.format(kind, n_t, br))
        extra.append('{{\n"classname" "{}"\n"targetname" "lab_t{}"\n"origin" "{} {} {}"{}\n}}'.format(
            "target_position" if kind == "trigger_push" else "misc_teleporter_dest", n_t, int(dest[0]), int(dest[1]), int(dest[2]),
            "" if angle is None else '\n"angle" "{}"'.format(int(angle))))

    box(1024 - 56, yc - 56, 0, 1024 + 56, yc + 56, 2, TRIM)                       # pad plates (what you see)
    trigger("trigger_push", 1024 - 48, yc - 48, 2, 1024 + 48, yc + 48, 18, (1700, yc, 640))
    box(3090, yc - 80, 400, 3100, yc + 80, 402, TRIM)                             # line in front of the teleporter
    trigger("trigger_teleport", 3120, yc - 72, 400, 3168, yc + 72, 528, (3520, yc, 40), angle=0)
    box(4200 - 56, yc - 56, 0, 4200 + 56, yc + 56, 2, TRIM)
    trigger("trigger_push", 4200 - 48, yc - 48, 2, 4200 + 48, yc + 48, 18, (4650, yc, 520))
    course("pads", "Jump pads and teleporter", "Jump pad up to the ledge, teleporter at its end, jump pad over the wall: keep moving.",
           [64, yc, 8], [[64, yc], [1024, yc], [1800, yc], [3120, yc], [3520, yc], [4200, yc], [5100, yc], [6296, yc]])

    # ---- drops: get down fast without fall damage (a fall of more than about 250 units hurts, 375 hurts more)
    dy_ = 34000
    room(0, dy_, 0, 4800, dy_ + 512, 1700)
    for x0_, x1_, top in ((0, 640, 1280), (640, 1280, 1080), (1280, 1920, 840), (1920, 2880, 520), (2880, 4800, 80)):
        box(x0_, dy_, 0, x1_, dy_ + 512, top, BLOCK)
    box(1920, dy_ + 256, 520, 2240, dy_ + 512, 680, TRIM)                         # side ledges: the careful way down
    box(2880, dy_ + 256, 80, 3200, dy_ + 512, 300, TRIM)
    course("drops", "Drops", "You have 1 health: any fall damage kills and ends the run. Get to the bottom fast; the side ledges split the big drops.",
           [64, dy_ + 128, 1288], [[64, dy_ + 128], [4696, dy_ + 128]])       # the straight line is the deadly one
    courses["drops"]["mortal"] = True                                             # 1 health: any fall damage ends the run

    # ---- climb: ledges that each need a jump (40 high: more than a step, less than a jump)
    cy_ = 36000
    room(0, cy_, 0, 4200, cy_ + 512, 1100)
    x, top = 512, 0
    for k in range(18):
        top += 40
        depth = 160 if k % 3 else 96
        box(x, cy_, 0, 4200, cy_ + 512, top, TRIM if k % 2 else BLOCK)
        x += depth
    course("climb", "Climb", "Eighteen ledges, each 40 high: jump up them without losing your rhythm.",
           [64, cy_ + 256, 8], [[64, cy_ + 256], [x + 600, cy_ + 256]], end_z=top - 8, end_r=200)

    # ---- dodge: a rocket turret at the far end; get to the line in front of it
    oy = 38000
    room(0, oy, 0, 3600, oy + 768, 320)
    for k, px in enumerate(range(700, 2800, 500)):
        box(px, oy + (120 if k % 2 else 520), 0, px + 64, oy + (248 if k % 2 else 648), 320, BLOCK)   # a little cover
    box(3000, oy, 0, 3008, oy + 768, 1, TRIM)                                     # the finish line
    box(3300, oy + 320, 0, 3500, oy + 448, 64, BLOCK)                             # the turret stands on this
    course("dodge", "Rocket dodge", "A rocket turret fires at you from the far end: reach the line in front of it taking as little damage as you can.",
           [64, oy + 384, 8], [[64, oy + 384], [3000, oy + 384]], end_r=400)
    courses["dodge"]["turret"] = [3400, oy + 384, 72, 180]

    # ---- peek: a rail duel through two gaps in a wall; the opponent stands in the open and does not move
    ky2 = 40000
    room(0, ky2, 0, 1600, ky2 + 1024, 320)
    for y0_, y1_ in ((0, 300), (420, 604), (724, 1024)):
        box(480, ky2 + y0_, 0, 512, ky2 + y1_, 320, BLOCK)
    rooms["peek"] = dict(subject=[200, ky2 + 512, 8], yaw=0, target=[1300, ky2 + 512, 8], target_yaw=180,
                         bounds=[0, ky2, 1600, ky2 + 1024])
    spawns.append((200, ky2 + 512, 24, 0))

    # ---- items: a ring corridor with a mega health and a red armor in opposite corners (35 s and 25 s timers)
    iy = 42000
    room(0, iy, 0, 3072, iy + 2048, 320)
    box(512, iy + 512, 0, 2560, iy + 1536, 320, BLOCK)
    extra.append('{{\n"classname" "item_health_mega"\n"origin" "{} {} 24"\n}}'.format(256, iy + 256))
    extra.append('{{\n"classname" "item_armor_body"\n"origin" "{} {} 24"\n}}'.format(2816, iy + 1792))
    rooms["items"] = dict(start=[1536, iy + 256, 8], yaw=0, mega=[256, iy + 256, 24], red_armor=[2816, iy + 1792, 24],
                          bounds=[0, iy, 3072, iy + 2048], secs=120)
    spawns.append((1536, iy + 256, 24, 0))

    # ---- write the maps
    def write(name, R, message):
        ents = ['{\n"classname" "worldspawn"\n"message" "' + message + '"\n"_ambient" "' + str(R.get("ambient", 45)) +
                '"\n"_color" "1 1 1"\n' + "\n".join(brushes) + "\n}"]
        for x, y, z, a in spawns:
            ents.append('{{\n"classname" "info_player_deathmatch"\n"origin" "{} {} {}"\n"angle" "{}"\n}}'.format(
                int(x), int(y), int(z), int(a)))
        ents += extra
        for li in lights:
            x, y, z, v = li[:4]
            col = '\n"_color" "{} {} {}"'.format(*li[4]) if len(li) > 4 else ""
            ents.append('{{\n"classname" "light"\n"origin" "{} {} {}"\n"light" "{}"{}\n}}'.format(int(x), int(y), int(z), v, col))
        os.makedirs(os.path.join(ROOT, "data", "lab", "maps"), exist_ok=True)
        os.makedirs(os.path.join(ROOT, "maps", name), exist_ok=True)
        with open(os.path.join(ROOT, "data", "lab", "maps", name + ".map"), "w", newline="\n") as f:
            f.write("\n".join(ents) + "\n")
        with open(os.path.join(ROOT, "maps", name, "rooms.json"), "w", newline="\n") as f:
            json.dump(R, f, indent=1)
        print("{}: {} brushes, {} lights, {} spawns -> data/lab/maps/{}.map".format(name, len(brushes), len(lights), len(spawns), name))

    write("testlab", rooms, "BobbyBones test lab")
    brushes.clear(); lights.clear(); spawns.clear(); extra.clear()
    write("train-arena", arena(trigger), "BobbyBones training arena")


def arena(trigger):
    """The training arena (map "train-arena", 2026-10-05; the owner's notes worked in the same evening): a small
    two-level arena in the manner of the duel maps. Inside 1792 x 1536.
      ground     an open middle with pillars and cover; a tunnel under the north balcony; a closed room in the
                 south-east (two doors, rockets inside); a low strip under the east balcony; a lava pit under the
                 catwalk
      upper      north and east balconies joined at the corner, a catwalk from the east balcony to the tower in the
                 middle, the roof of the south-east room (a short jump from the east balcony)
      ways up    stairs on the west wall, a ramp in front of the north balcony, a jump pad onto the tower
      the void   the south wall is open in the middle: beyond it is a drop that kills. The red armor stands on an
                 island in it. A walkway leads there from the east side; a circle jump from the edge is quicker
                 (256 units: a plain running jump falls short)
      teleporter from the tunnel's east end to the south-west corner
    Every texture name is one the game's own maps use."""
    F1, F2, METAL, STAIR = "gothic_floor/largerblock3b3", "gothic_floor/largerblock3b3dim", "base_floor/clangdark", "gothic_floor/xstairtop4"
    BRICK, BLK, KILL, IRON = "gothic_wall/streetbricks10", "gothic_block/blocks18c", "gothic_block/killblock_i", "gothic_wall/iron01_e"
    RUST, DARK, SUPPORT, CEIL = "gothic_trim/pitted_rust2", "gothic_block/dark_block", "gothic_trim/metalsupport4b", "gothic_block/blocks15"
    LAVA, SKY, PAD, PORTAL = "liquids/lavahell", "skies/meth_clouds_blue", "sfx/bouncepad01block18b", "sfx/portal_new_static_teal"
    X, Y, H, UP = 1792, 1536, 512, 192
    PIT = (1152, 544, 1344, 704)                              # the lava pit, under the catwalk
    VX0, VX1, VY = 512, 1280, -480                            # the void: beyond the south wall between these x
    # floor: a base under everything (lava where it shows), then the walking floor in pieces around the pit
    box(-32, -32, -96, X + 32, Y + 32, -64, DARK)
    box(-32, -32, -64, X + 32, Y + 32, -32, LAVA)
    for x0, y0, x1, y1, tex in ((-32, -32, PIT[0], Y + 32, F1), (PIT[2], -32, X + 32, Y + 32, F2),
                                (PIT[0], -32, PIT[2], PIT[1], F1), (PIT[0], PIT[3], PIT[2], Y + 32, F2)):
        box(x0, y0, -32, x1, y1, 0, tex)
    box(0, 0, H, X, Y, H + 32, CEIL)
    box(-32, -32, -64, 0, Y + 32, H + 32, BRICK)              # west, east, north walls
    box(X, -32, -64, X + 32, Y + 32, H + 32, BRICK)
    box(0, Y, -64, X, Y + 32, H + 32, BRICK)
    box(0, -32, 0, VX0, 0, H + 32, BRICK)                     # south wall, open to the void in the middle
    box(VX1, -32, 0, X, 0, H + 32, BRICK)
    box(VX0, -32, 256, VX1, 0, H + 32, RUST)                  # the beam over the opening
    # the void: sky all round, nothing below
    box(VX0 - 32, VY - 32, -800, VX0, -32, H + 32, SKY)
    box(VX1, VY - 32, -800, VX1 + 32, -32, H + 32, SKY)
    box(VX0 - 32, VY - 32, -800, VX1 + 32, VY, H + 32, SKY)
    box(VX0, VY, H, VX1, -32, H + 32, SKY)
    box(VX0 - 32, VY - 32, -832, VX1 + 32, 0, -800, DARK)
    box(VX0, -32, -800, VX1, 0, -96, DARK)                    # the cliff under the floor's edge
    box(832, -416, -32, 960, -288, 0, METAL)                  # the island (red armor), on a column
    box(864, -384, -800, 928, -320, -32, IRON)
    box(1216, -416, -16, 1280, -32, 0, METAL)                 # the walkway round from the east side
    box(960, -416, -16, 1216, -352, 0, METAL)
    hurt = [[VX0, VY, -760, VX1, -32, -400, 100000], [PIT[0], PIT[1], -40, PIT[2], PIT[3], -8, 20]]
    for k, (x0, y0, z0, x1, y1, z1, dps) in enumerate(hurt):
        f = "( {} {} {} ) ( {} {} {} ) ( {} {} {} ) common/trigger 0 0 0 0.5 0.5 0 0 0"
        q = [(x1, y1, z1, x1, y0, z1, x0, y1, z1), (x1, y1, z1, x0, y1, z1, x1, y1, z0), (x1, y1, z1, x1, y1, z0, x1, y0, z1),
             (x0, y0, z0, x1, y0, z0, x0, y1, z0), (x0, y0, z0, x0, y0, z1, x1, y0, z0), (x0, y0, z0, x0, y1, z0, x0, y0, z1)]
        br = "{\n" + "\n".join(f.format(*[int(v) for v in t]) for t in q) + "\n}"
        # the void kills at once; lava burns once a second (spawnflag 16 = slow)
        extra.append('{{\n"classname" "trigger_hurt"\n"dmg" "{}"{}\n{}\n}}'.format(
            10000 if dps >= 1000 else int(dps), "" if dps >= 1000 else '\n"spawnflags" "16"', br))
    # north balcony over the tunnel
    box(0, 1280, UP - 16, X, Y, UP, METAL)
    for x0_, x1_ in ((0, 384), (512, 1152), (1280, X)):       # the tunnel's front wall, two doorways
        box(x0_, 1280, 0, x1_, 1296, UP - 16, BLK)
    box(800, 1392, 0, 864, Y, 96, SUPPORT)                    # a half wall inside the tunnel
    # east balcony, the strip under it
    box(1536, 512, UP - 16, X, 1280, UP, METAL)
    box(1536, 768, 0, 1552, 1024, UP - 16, BLK)
    box(1536, 512, 0, 1568, 544, UP - 16, IRON)
    # the south-east room: walls to the roof, a door in the west wall and one in the north wall
    box(1280, 0, 0, 1296, 128, UP - 16, BLK)
    box(1280, 256, 0, 1296, 400, UP - 16, BLK)
    box(1280, 128, 128, 1296, 256, UP - 16, RUST)
    box(1296, 384, 0, 1472, 400, UP - 16, BLK)
    box(1600, 384, 0, X, 400, UP - 16, BLK)
    box(1472, 384, 128, 1600, 400, UP - 16, RUST)
    box(1280, 0, UP - 16, X, 400, UP, METAL)                  # its roof: a short jump from the east balcony
    for k in range(12):                                       # stairs on the west wall, up to the north balcony
        box(0, 896 + k * 32, 0, 192, 896 + (k + 1) * 32, 16 * (k + 1), STAIR)
    ramp(640, 1152, 1024, 1280, 0, UP, 0, METAL)              # ramp in front of the north balcony
    box(1024, 1152, 0, 1152, 1280, UP, BLK)
    box(768, 512, 0, 896, 736, UP, KILL)                      # the tower (mega health)
    box(896, 576, UP - 16, 1536, 672, UP, METAL)              # catwalk: tower to east balcony, over the lava
    box(576, 800, 0, 592, 1120, 224, BLK)                     # a long wall that splits the west side
    for x0, y0 in ((416, 320), (1088, 960)):                  # pillars
        box(x0, y0, 0, x0 + 64, y0 + 64, H, IRON)
    box(960, 400, 0, 1216, 432, 64, SUPPORT)                  # low wall (crouch cover)
    box(288, 928, 0, 384, 1024, 96, SUPPORT)                  # crates
    box(700, 1380, UP, 764, 1444, UP + 64, SUPPORT)
    box(1600, 880, UP, 1632, 1040, UP + 56, RUST)             # low wall on the east balcony
    box(300 - 56, 624 - 56, 0, 300 + 56, 624 + 56, 2, PAD)     # jump pad
    trigger("trigger_push", 300 - 48, 624 - 48, 2, 300 + 48, 624 + 48, 18, (630, 624, 340))
    box(1776, 1344, 0, 1790, 1488, 128, PORTAL)               # teleporter, at the tunnel's east end
    box(1680, 1330, 0, 1690, 1500, 2, RUST)
    trigger("trigger_teleport", 1728, 1344, 0, 1776, 1488, 128, (128, 128, 40), angle=45)
    for x in range(192, X, 384):                              # lights: warm overall, cold in the tunnel, red at the lava
        for y in range(192, Y, 384):
            lights.append((x, y, H - 24, 420, (1.0, 0.93, 0.82)))
    for x in (200, 700, 1200, 1650):
        lights.append((x, 1420, 120, 160, (0.55, 0.7, 1.0)))
    lights.append((1248, 624, 60, 260, (1.0, 0.45, 0.15)))
    lights.append((1540, 200, 130, 200, (1.0, 0.8, 0.5)))
    for x in (640, 896, 1152):
        lights.append((x, -240, 300, 380, (0.75, 0.85, 1.0)))
    lights.append((896, -352, 80, 150, (1.0, 0.3, 0.2)))      # the island glows red
    spots = [[128, 320, 8], [1664, 128, 8], [330, 128, 8], [640, 900, 8], [1300, 820, 8], [200, 1420, 8], [1400, 1420, 8],
             [1650, 640, 8], [200, 1408, UP + 8], [1400, 1408, UP + 8], [1664, 700, UP + 8], [1100, 624, UP + 8],
             [1540, 200, UP + 8]]
    for q in spots[:4] + spots[8:10]:
        spawns.append((q[0], q[1], q[2] + 16, 0))
    for cls, x_, y_, z_ in (("item_health_mega", 832, 624, UP + 24),        # on the tower (the jump pad lands there)
                            ("item_armor_body", 896, -352, 24),              # on the island in the void
                            ("weapon_railgun", 1500, 1408, UP + 24),         # north balcony, east end
                            ("weapon_rocketlauncher", 1540, 200, 24),        # inside the south-east room
                            ("weapon_lightning", 1664, 1000, 24),            # under the east balcony
                            ("item_health_large", 200, 1420, 24),            # in the tunnel, west end
                            ("item_health", 128, 700, 24), ("item_health", 1000, 1000, 24),
                            ("item_armor_shard", 1400, 100, UP + 24), ("item_armor_shard", 1680, 300, UP + 24)):
        extra.append('{{\n"classname" "{}"\n"origin" "{} {} {}"\n}}'.format(cls, x_, y_, z_))
    return dict(map="train-arena", stations={}, courses={}, hurt=hurt, ambient=30,
                yard=dict(bounds=[0, VY, X, Y], z=8, spots=spots, items=True))


if __name__ == "__main__":
    main()

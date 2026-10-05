"""First-person videos of BobbyBones on the test map's movement courses (simulator, flat-shaded ray tracing).

    python sim/render_course.py --run duel_gru_v4 [--policy file.pt] [--courses speed,ramps,...]

For every course: one attempt (the fastest finish of a few tries, or the furthest one if none finishes), drawn
from his eyes with the keys, the mouse turn, his speed against the 320 run cap and the progress along the course.
Writes videos/<run>_<minutes>/<course>.mp4 (real time, 40 frames a second). Needs ffmpeg and Pillow.
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import duel_env as E                 # noqa: E402
import test_suite as T               # noqa: E402

W, H, FOV = 480, 270, 100.0


def attempt(env, pol, k, secs=30.0):
    """one attempt at course k by player 0 -> frames, finished, seconds"""
    C = env.courses[k]
    env.lab_force = dict(kind=E.COURSE, course=k)
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    env.round_t[:] = 0.0
    frames = []
    base = env.stats["course"][k, 1]
    for t in range(int(secs / E.DT)):
        s = env.state[0].copy()
        fr = dict(pos=s[:3].copy(), vel=s[3:6].copy(), ground=float(s[6]), yaw=float(env.yaw[0]), pitch=float(env.pitch[0]),
                  prog=float(env.prog[0]), length=C["length"], hp=float(env.hp[0]))
        act, h = pol.act(obs, h)
        fr["a"] = act[0].copy()
        prev_prog = float(env.prog[0])
        obs, _, done, _ = env.step(act)
        h[done] = 0.0
        frames.append(fr)
        if float(env.prog[0]) < prev_prog - 200 and prev_prog > C["length"] - 400:      # restarted after reaching the end
            return frames, True, len(frames) * E.DT
    return frames, False, secs


def render(env, fr, cam_rays):
    eye = fr["pos"] + np.array([0, 0, 26.0], np.float32)
    y, p = math.radians(fr["yaw"]), math.radians(fr["pitch"])
    Rp = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]], np.float32)
    Ry = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]], np.float32)
    dirs = cam_rays @ Rp.T @ Ry.T
    frac = env.w.rays_each(eye[None], dirs.reshape(1, -1, 3), 6000.0).reshape(H, W)
    P = eye + dirs.reshape(H, W, 3) * (frac[..., None] * 6000.0)
    dx, dy = np.zeros_like(P), np.zeros_like(P)
    dx[:, :-1] = P[:, 1:] - P[:, :-1]
    dy[:-1] = P[1:] - P[:-1]
    n = np.cross(dx, dy)
    n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-6
    n *= -np.sign((n * dirs.reshape(H, W, 3)).sum(2, keepdims=True))
    light = np.array([0.35, 0.25, 0.9], np.float32)
    light /= np.linalg.norm(light)
    lam = np.clip((n * light).sum(2), 0, 1) * 0.65 + 0.35
    depth = frac * 6000.0
    fog = np.clip(1.0 - depth / 5000.0, 0.3, 1.0)
    floor = n[..., 2] > 0.7
    # a checker on the floor (128 units) so that speed can be seen
    chk = ((np.floor(P[..., 0] / 128.0) + np.floor(P[..., 1] / 128.0)) % 2 == 0)
    base = np.where(floor[..., None], np.where(chk[..., None], np.array([110, 125, 150], np.float32), np.array([135, 150, 175], np.float32)),
                    np.array([205, 180, 140], np.float32))
    img = base * (lam * fog)[..., None]
    edge = (np.abs(np.diff(depth, axis=1, prepend=depth[:, :1])) > 24) | (np.abs(np.diff(depth, axis=0, prepend=depth[:1])) > 24)
    img[edge] *= 0.35
    img[frac >= 0.999] = (40, 45, 60)
    return np.clip(img, 0, 255).astype(np.uint8)


def overlay(img, fr, label, t, font, big):
    im = Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    v, a = fr["vel"], fr["a"]
    sp = math.hypot(v[0], v[1])
    fwd, side, vert = int(a[0]) - 1, int(a[1]) - 1, int(a[2])
    turn = float(E.TURN[a[3]])
    d.rectangle([20, 20, 420, 44], outline=(255, 255, 255))
    d.rectangle([20, 20, 20 + int(min(sp, 1200) / 1200 * 400), 44], fill=(80, 220, 120) if sp > 320 else (230, 200, 80))
    cap = 20 + int(320 / 1200 * 400)
    d.line([cap, 14, cap, 50], fill=(255, 80, 80), width=3)
    d.text((430, 18), "{:4.0f} u/s".format(sp), fill=(255, 255, 255), font=big)
    d.text((cap - 14, 52), "320", fill=(255, 80, 80), font=font)
    d.text((20, 78), "{}   {:5.2f} s   {:.0f} / {:.0f} units   {}".format(
        label, t, fr["prog"], fr["length"], "airborne" if fr["ground"] < 0.5 else "on ground"), fill=(255, 255, 255), font=font)
    for k, on, (x, y) in (("W", fwd > 0, (90, 420)), ("A", side < 0, (40, 470)), ("S", fwd < 0, (90, 470)), ("D", side > 0, (140, 470))):
        d.rectangle([x, y, x + 44, y + 44], fill=(240, 240, 240) if on else (40, 40, 40), outline=(200, 200, 200))
        d.text((x + 14, y + 10), k, fill=(0, 0, 0) if on else (160, 160, 160), font=big)
    for name, on, x in (("JUMP", vert == 1, 200), ("CROUCH", vert == 2, 340), ("WALK", int(a[7]) == 1, 500)):
        d.rectangle([x, 470, x + 130, 514], fill=(240, 240, 240) if on else (40, 40, 40), outline=(200, 200, 200))
        d.text((x + 18, 480), name, fill=(0, 0, 0) if on else (160, 160, 160), font=big)
    cx = 790
    d.rectangle([cx - 150, 470, cx + 150, 514], outline=(200, 200, 200))
    x1 = cx - int(max(-30, min(30, turn)) * 5)
    d.rectangle([min(cx, x1), 470, max(cx, x1), 514], fill=(120, 170, 255))
    d.text((cx - 150, 444), "mouse turn {:+.1f} deg/frame".format(turn), fill=(255, 255, 255), font=font)
    d.line([W - 8, H, W + 8, H], fill=(255, 255, 255))
    d.line([W, H - 8, W, H + 8], fill=(255, 255, 255))
    return np.asarray(im)


def project(fr, pts):
    """world points -> screen pixels of the doubled picture (and whether each is in front of the eye)"""
    eye = fr["pos"] + np.array([0, 0, 26.0], np.float32)
    y, p = math.radians(fr["yaw"]), math.radians(fr["pitch"])
    f = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)])
    left = np.array([-math.sin(y), math.cos(y), 0.0])
    up = np.cross(f, left)
    d = np.asarray(pts, np.float64) - eye
    x, yv, z = d @ f, d @ left, d @ up
    tan_h = math.tan(math.radians(FOV / 2))
    sx = (1 - (yv / np.maximum(x, 1e-3)) / tan_h) * W
    sy = (1 - (z / np.maximum(x, 1e-3)) / (tan_h * H / W)) * H
    return sx, sy, x > 8


def hull(px, py):
    """convex hull of screen points (for drawing a box as a filled shape)"""
    pts = sorted(set(zip([float(v) for v in px], [float(v) for v in py])))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (q[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (q[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(q)
        return out[:-1]
    return half(pts) + half(pts[::-1])


def draw_box(d, fr, centre, yaw, size, lo, hi, fill, outline=(20, 20, 20)):
    """a box turned to yaw (degrees): half-sizes size = (forward, sideways), from height lo to hi above centre"""
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pts = []
    for fx in (-size[0], size[0]):
        for sy_ in (-size[1], size[1]):
            for z in (lo, hi):
                pts.append((centre[0] + c * fx - s_ * sy_, centre[1] + s_ * fx + c * sy_, centre[2] + z))
    sx, sy, ok = project(fr, pts)
    if ok.all():
        h = hull(sx, sy)
        if len(h) >= 3:
            d.polygon(h, fill=fill, outline=outline)


WCOL = {"rl": (255, 120, 40), "gl": (90, 220, 90), "pg": (90, 200, 255), "rg": (120, 255, 160), "lg": (190, 220, 255),
        "mg": (255, 240, 150), "hmg": (255, 210, 120), "sg": (255, 230, 170), "g": (200, 200, 200)}


def draw_enemy(d, fr, e):
    """an opponent as a figure: legs, body, head, and his weapon pointing where he aims"""
    o, yaw = e["pos"], e["yaw"]
    duck = e["duck"]
    hurt = e["hurt"]
    body = (255, 255, 255) if hurt else (70, 200, 90)          # bright green, like an enemy model; white when hit
    dark = (255, 255, 255) if hurt else (40, 130, 60)
    top = 16.0 if duck else 32.0
    draw_box(d, fr, o, yaw, (7, 12), -24.0, -4.0 if not duck else -12.0, dark)                       # legs
    draw_box(d, fr, o, yaw, (8, 14), -4.0 if not duck else -12.0, top - 10.0, body)                  # body
    draw_box(d, fr, o, yaw, (6, 6), top - 10.0, top, (235, 200, 160) if not hurt else (255, 255, 255))   # head
    # weapon: a bar from his right hand along his aim
    yr, pr = math.radians(yaw), math.radians(e["pitch"])
    f = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)])
    right = np.array([math.sin(yr), -math.cos(yr), 0.0])
    hand = np.array(o, np.float64) + right * 12.0 + np.array([0, 0, top - 16.0])
    sx, sy, ok = project(fr, [hand, hand + f * 26.0])
    if ok.all():
        d.line([float(sx[0]), float(sy[0]), float(sx[1]), float(sy[1])], fill=WCOL.get(e["w"], (220, 220, 220)), width=4)
    return hand + f * 26.0, f


def draw_shots(d, fr, muzzles):
    """beams and trails of this frame's hitscan shots, and every projectile in flight with its own look"""
    eye = fr["pos"] + np.array([0, 0, 26.0], np.float32)
    for who, (w, shot, muzzle, f_opp) in enumerate([(fr["w"][0], fr["shot"][0], None, None)] + muzzles):
        if not shot:
            continue
        if w not in ("rg", "lg", "mg", "hmg", "sg"):
            continue
        col = WCOL[w]
        width = 5 if w == "rg" else 3 if w == "lg" else 1
        if who == 0:                                             # his own shot: from the gun at the bottom right to the crosshair
            d.line([W * 2 - 150, H * 2 - 40, W, H], fill=col, width=width)
        elif muzzle is not None:
            reach = 768.0 if w == "lg" else 3000.0
            sx, sy, ok = project(fr, [muzzle, muzzle + f_opp * reach])
            if ok[0]:
                x1, y1 = (float(sx[1]), float(sy[1])) if ok[1] else (float(sx[0]) + (float(sx[0]) - W) * 4, float(sy[0]) + (float(sy[0]) - H) * 4)
                d.line([float(sx[0]), float(sy[0]), x1, y1], fill=col, width=width)
    for rp, kind, owner, rv in fr["rockets"]:
        name = E.WEAPONS[kind]
        sx, sy, ok = project(fr, [rp, rp - rv / (np.linalg.norm(rv) + 1e-6) * 60.0])
        if not ok[0]:
            continue
        dist = float(np.linalg.norm(rp - eye)) + 1.0
        r = max(3.0, min(26.0, 2200.0 / dist)) * (0.6 if name == "pg" else 1.0)
        x, y = float(sx[0]), float(sy[0])
        col = WCOL.get(name, (255, 200, 60))
        if name == "rl" and ok[1]:                               # rocket: a smoke trail behind it
            d.line([x, y, float(sx[1]), float(sy[1])], fill=(170, 170, 170), width=max(2, int(r / 2)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255) if owner != 0 else (60, 60, 60), width=2)
        if owner != 0:                                           # the enemy's: a ring so it stands out
            d.ellipse([x - r - 4, y - r - 4, x + r + 4, y + r + 4], outline=(255, 60, 60), width=2)


def fight(env, pol, where, secs, round_len):
    """self-play in an arena (1 = aim box, 2 = environment box): frames from player 0's eyes"""
    env.arena_len = round_len
    if os.environ.get("ARENA_SETS"):                         # e.g. "rl;rl,lg;rl,rg;rl,rg,lg": each player draws one, separately
        env.arena_sets = [tuple(E.WEAPONS.index(x) for x in s_.split(",")) for s_ in os.environ["ARENA_SETS"].split(";")]
    env.lab_force = dict(kind=E.NORMAL, arena=where)
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    nin = len(pol.mean)                                      # a network trained before inputs were added at the end
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    frames, frags = [], [0, 0]
    labels = {"MH": "MEGA", "RA": "RED ARMOR", "YA": "YELLOW ARMOR", "GA": "GREEN ARMOR"}
    for t in range(int(secs / E.DT)):
        s = env.state.copy()
        fr = dict(pos=s[0, :3].copy(), vel=s[0, 3:6].copy(), ground=float(s[0, 6]), yaw=float(env.yaw[0]), pitch=float(env.pitch[0]),
                  opp=s[1, :3].copy(), opp_duck=bool(env.duck[1]), seen=bool(env._los(env._eye(s)[:1], s[1:2, :3] + np.array([0, 0, 8.0], np.float32))[0]),
                  hp=(float(env.hp[0]), float(env.armor[0]), float(env.hp[1]), float(env.armor[1])),
                  w=(E.WEAPONS[int(env.weapon[0])], E.WEAPONS[int(env.weapon[1])]),
                  guns=" + ".join(E.WEAPONS[g].upper() for g in (env.load_sets[0] or ())),
                  opp_yaw=float(env.yaw[1]), opp_pitch=float(env.pitch[1]), opp_vel=s[1, 3:6].copy(),
                  zoom=bool(getattr(env, "zoom", np.zeros(2, bool))[0]),
                  rockets=[(env.rp[i, k].copy(), int(env.rw[i, k]), i, env.rv[i, k].copy())
                           for i in range(env.n) for k in range(env.rp.shape[1]) if env.ra[i, k]])
        eye0 = env._eye(s)[:1]
        fr["others"] = [dict(pos=s[j, :3].copy(), duck=bool(env.duck[j]), yaw=float(env.yaw[j]), pitch=float(env.pitch[j]),
                             w=E.WEAPONS[int(env.weapon[j])],
                             seen=bool(env._los(eye0, s[j:j + 1, :3] + np.array([0, 0, 8.0], np.float32))[0]))
                        for j in range(1, env.n)]
        fr["items"] = []
        if where == 3:                                           # the yard: what lies there, while it is up and in sight
            for k_, dfn in enumerate(env.item_def):
                ip = env.item_pos[k_]
                if env.item_up[0, k_] and env.w.trace(eye0[0], (ip + np.array([0, 0, 16.0], np.float32)).astype(np.float32))["fraction"] >= 0.999:
                    nm = labels.get(dfn[4]) or (E.WEAPONS[int(dfn[1])].upper() if dfn[0] == "wp" else
                                                "+{}".format(int(dfn[1])) if dfn[0] in ("hp", "ar") else "ammo")
                    fr["items"].append((ip.copy(), nm, dfn[0]))
        before = (env.hp + env.armor).copy()
        act, h = pol.act(obs[:, :nin], h)
        fr["a"] = act[0].copy()
        obs, r, done, info = env.step(act)
        if hasattr(env, "key_last"):                             # show what his fingers actually did, not every request
            fr["asked"] = int((act[0, :3] != env.key_last[0]).sum())
            fr["a"][:3] = env.key_last[0]
            fr["a"][5] = int(env.fire_last[0])
        h[done] = 0.0
        for e in info.get("events", []) if isinstance(info, dict) else []:
            if e["killer"] >= 0 and e["killer"] != e["victim"]:
                frags[min(1, e["killer"])] += 1
        fr["frags"] = tuple(frags)
        fq = getattr(env, "fire_q", np.zeros(env.n, bool))
        fr["shot"] = (bool(fq[0]), bool(fq[1]))                  # who fired on this frame (weapons as held before it)
        for j, o_ in enumerate(fr["others"], 1):
            o_["shot"], o_["hurt"] = bool(fq[j]), bool(env.hp[j] + env.armor[j] < before[j])
        fr["took"] = float(env.fb[0, 1]) * 100.0
        fr["dealt"] = float(env.fb[0, 0]) * 100.0
        frames.append(fr)
    return frames


def overlay_fight(img, fr, label, t, font, big):
    im = Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    # the opponent as a figure (only with a clear line to him), then shots and projectiles
    for ip, nm, kind in fr.get("items", []):
        sx, sy, ok = project(fr, [ip + np.array([0, 0, 8.0], np.float32)])
        if ok[0]:
            col = {"hp": (90, 160, 255), "ar": (255, 90, 90), "wp": (255, 220, 90)}.get(kind, (200, 200, 200))
            x, y = float(sx[0]), float(sy[0])
            d.polygon([(x, y - 9), (x + 7, y), (x, y + 9), (x - 7, y)], fill=col, outline=(20, 20, 20))
            d.text((x + 10, y - 9), nm, fill=col, font=font)
    muzzles = []
    for e in sorted(fr["others"], key=lambda q: -float(np.linalg.norm(q["pos"] - fr["pos"]))):     # far ones first
        mz, fo = draw_enemy(d, fr, e) if e["seen"] else (None, None)
        muzzles.append((e["w"], e["shot"], mz, fo))
    draw_shots(d, fr, muzzles)
    if fr["took"] > 0:                                         # he was hit: a red frame
        d.rectangle([0, 0, W * 2 - 1, H * 2 - 1], outline=(255, 40, 40), width=10)
    if fr["zoom"]:
        d.text((W - 30, 60), "ZOOM", fill=(255, 255, 120), font=big)
    v, a = fr["vel"], fr["a"]
    sp = math.hypot(v[0], v[1])
    fwd, side, vert, fire = int(a[0]) - 1, int(a[1]) - 1, int(a[2]), int(a[5])
    d.rectangle([20, 20, 320, 40], outline=(255, 255, 255))
    d.rectangle([20, 20, 20 + int(min(sp, 800) / 800 * 300), 40], fill=(80, 220, 120) if sp > 320 else (230, 200, 80))
    d.line([20 + 120, 14, 20 + 120, 46], fill=(255, 80, 80), width=3)
    d.text((330, 16), "{:4.0f} u/s".format(sp), fill=(255, 255, 255), font=big)
    d.text((20, 78), "{}   {:5.1f} s   this round: {}".format(label, t, fr["guns"] or "every weapon"), fill=(255, 255, 255), font=font)
    d.text((560, 16), "frags  him {}  :  {} {}".format(fr["frags"][0], fr["frags"][1], "other" if len(fr["others"]) == 1 else "others"),
           fill=(255, 255, 255), font=big)
    d.text((20, 380), "holding {}   health {:.0f}  armor {:.0f}".format(fr["w"][0].upper(), fr["hp"][0], fr["hp"][1]), fill=(255, 255, 255), font=big)
    if len(fr["others"]) == 1:
        d.text((560, 46), "other: {}  health {:.0f}".format(fr["w"][1].upper(), fr["hp"][2]), fill=(255, 200, 200), font=font)
    else:
        d.text((560, 46), "{} others, {} in sight".format(len(fr["others"]), sum(e["seen"] for e in fr["others"])),
               fill=(255, 200, 200), font=font)
    for k, on, (x, y) in (("W", fwd > 0, (90, 420)), ("A", side < 0, (40, 470)), ("S", fwd < 0, (90, 470)), ("D", side > 0, (140, 470))):
        d.rectangle([x, y, x + 44, y + 44], fill=(240, 240, 240) if on else (40, 40, 40), outline=(200, 200, 200))
        d.text((x + 14, y + 10), k, fill=(0, 0, 0) if on else (160, 160, 160), font=big)
    for name, on, x in (("JUMP", vert == 1, 200), ("CROUCH", vert == 2, 340), ("FIRE", fire == 1, 500)):
        d.rectangle([x, 470, x + 130, 514], fill=((255, 120, 80) if name == "FIRE" else (240, 240, 240)) if on else (40, 40, 40), outline=(200, 200, 200))
        d.text((x + 18, 480), name, fill=(0, 0, 0) if on else (160, 160, 160), font=big)
    d.line([W - 8, H, W + 8, H], fill=(255, 255, 255))
    d.line([W, H - 8, W, H + 8], fill=(255, 255, 255))
    return np.asarray(im)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="duel_gru_v4")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--courses", default="")
    ap.add_argument("--tries", type=int, default=4)
    ap.add_argument("--fight", default="", help="'aim', 'env' or 'yard': a self-play fight in that room instead of the courses")
    ap.add_argument("--env", default="duel_env", help="simulator module (duel_env_ffa for more than two players)")
    ap.add_argument("--group", type=int, default=2, help="players in the fight (needs --env duel_env_ffa)")
    ap.add_argument("--map", default="bobbylab", help="bobbyyard: the yard with items (with --fight yard)")
    ap.add_argument("--secs", type=float, default=60.0)
    ap.add_argument("--round", type=float, default=20.0, help="fight: seconds per round (new random weapons each round)")
    a = ap.parse_args()
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=5)
    if a.env != "duel_env":
        import importlib
        global E
        E = importlib.import_module(a.env)
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=4, loadout="all",
                    **(dict(group=a.group) if a.group != 2 else {}))
    if os.environ.get("ARENA_STACK") == "0":
        env.arena_stack = False
    env.react_frames = round(pol.react_ms / 25)
    xs = (np.arange(W) + 0.5) / W * 2 - 1
    ys = (np.arange(H) + 0.5) / H * 2 - 1
    tan_h = math.tan(math.radians(FOV / 2))
    gx, gy = np.meshgrid(xs, ys)
    cam = np.stack([np.ones_like(gx), -gx * tan_h, -gy * tan_h * H / W], 2).astype(np.float32)
    cam /= np.linalg.norm(cam, axis=2, keepdims=True)
    cam = cam.reshape(-1, 3)
    try:
        font, big = ImageFont.truetype("arial.ttf", 18), ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = big = ImageFont.load_default()
    out_dir = os.path.join(ROOT, "videos", "{}_{:04d}".format(a.run, int(pol.minutes)))
    os.makedirs(out_dir, exist_ok=True)
    if a.fight:
        frames = fight(env, pol, {"aim": 1, "env": 2, "yard": 3}[a.fight], a.secs, a.round)
        label = "fight against himself, {}".format({"aim": "aim box", "env": "environment box", "yard": "yard"}[a.fight])
        if a.group != 2:
            label = "{} copies of himself, all against all, {}".format(a.group, {"aim": "aim box", "env": "environment box", "yard": "yard"}[a.fight])
        path = os.path.join(out_dir, "fight_{}{}{}.mp4".format(a.fight, "" if a.group == 2 else "_{}".format(a.group),
                                                             "" if a.map == "bobbylab" else "_items"))
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                               "{}x{}".format(W * 2, H * 2), "-r", "40", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "23", path], stdin=subprocess.PIPE)
        for i, fr in enumerate(frames):
            ff.stdin.write(overlay_fight(render(env, fr, cam), fr, label, i * E.DT, font, big).tobytes())
        ff.stdin.close()
        ff.wait()
        sp = np.array([math.hypot(f["vel"][0], f["vel"][1]) for f in frames])
        print("fight: frags {} : {}, mean speed {:.0f}, enemy in line of sight {:.0%} -> {}".format(
            frames[-1]["frags"][0], frames[-1]["frags"][1], sp.mean(), np.mean([f["seen"] for f in frames]), path), flush=True)
        return
    want = [c for c in a.courses.split(",") if c]
    for k, C in enumerate(env.courses):
        if want and C["key"] not in want:
            continue
        best = None
        for _ in range(a.tries):
            frames, ok, secs = attempt(env, pol, k)
            score = (1, -secs) if ok else (0, max(f["prog"] for f in frames))
            if best is None or score > best[0]:
                best = (score, frames, ok, secs)
        _, frames, ok, secs = best
        label = "{}: {}".format(C["key"], "finished in {:.2f} s".format(secs) if ok else "not finished")
        path = os.path.join(out_dir, C["key"] + ".mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                               "{}x{}".format(W * 2, H * 2), "-r", "40", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "23", path], stdin=subprocess.PIPE)
        last = None
        for i, fr in enumerate(frames):
            last = overlay(render(env, fr, cam), fr, label, i * E.DT, font, big)
            ff.stdin.write(last.tobytes())
        for _ in range(40):
            ff.stdin.write(last.tobytes())
        ff.stdin.close()
        ff.wait()
        print("{:8s} {} -> {}".format(C["key"], label.split(": ")[1], path), flush=True)


if __name__ == "__main__":
    main()

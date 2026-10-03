"""First-person video of a movement policy in the simulator (to see its technique).

    python sim/render_fp.py --run multimap_v1 --map bloodrun [--trip MH>LG]

Picks the trip with the most fast airborne time (unless --trip), replays it with the policy, ray-traces each
frame against the real map geometry (flat shading: floors blue-grey, walls sand; no textures) and overlays the
keys pressed, the mouse turn, speed vs the 320 run cap, and the angle between view and velocity.
Writes data/sim_runs/<run>/fp_<map>_<trip>.mp4 (real time) and ..._slow.mp4 (quarter speed). Needs ffmpeg.
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
from eval_move import LABEL  # noqa: E402
from movement_env import ACTION_DIMS, MoveEnv, TURN_BINS  # noqa: E402

W, H, FOV = 480, 270, 100.0


def policy(run):
    import torch
    import torch.nn as nn
    ck = torch.load(os.path.join(ROOT, "data", "sim_runs", run, "policy.pt"), weights_only=False)
    body = nn.Sequential(nn.Linear(ck["obs_dim"], 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
    pi = nn.Linear(256, sum(ACTION_DIMS))
    sd = ck["model"]
    body.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("body.")})
    pi.load_state_dict({k[3:]: v for k, v in sd.items() if k.startswith("pi.")})

    def act(obs, rng):
        x = torch.from_numpy(np.clip((obs - ck["obs_mean"]) / np.sqrt(ck["obs_var"] + 1e-8), -10, 10).astype(np.float32))
        with torch.no_grad():
            return torch.stack([torch.distributions.Categorical(logits=l).sample()
                                for l in pi(body(x)).split(ACTION_DIMS, -1)], -1).numpy()
    return act


def run_trip(env, act, gi_from, gi_to, rng):
    f = env.field
    p = env.goal_pos[gi_from]
    node, _ = f.locate(p[None])
    nx = f.next[gi_to, node[0]]
    q = f.nodes[nx] if nx >= 0 else env.goal_pos[gi_to]
    env.place(0, p, math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])), gi_to)
    obs = env.observe()
    frames = []
    for t in range(int(20 / 0.025)):
        a = act(obs, rng)
        s = env.state[0].copy()
        yaw_before = float(env.yaw[0])
        obs, r, done, info = env.step(a)
        frames.append(dict(pos=s[:3], vel=s[3:6], ground=s[6], yaw=yaw_before, a=a[0].copy()))
        if done[0]:
            return frames, bool(info["episodes"][0]["arrived"])
    return frames, False


def render(env, fr, cam_rays):
    eye = fr["pos"] + np.array([0, 0, 26.0], np.float32)
    y = math.radians(fr["yaw"])
    c, s = math.cos(y), math.sin(y)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
    dirs = cam_rays @ R.T
    frac = env.w.rays_each(eye[None], dirs.reshape(1, -1, 3), 4096.0).reshape(H, W)
    P = eye + dirs.reshape(H, W, 3) * (frac[..., None] * 4096.0)
    dx = np.zeros_like(P)
    dy = np.zeros_like(P)
    dx[:, :-1] = P[:, 1:] - P[:, :-1]
    dy[:-1] = P[1:] - P[:-1]
    n = np.cross(dx, dy)
    n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-6
    n *= -np.sign((n * dirs.reshape(H, W, 3)).sum(2, keepdims=True))      # face the camera
    light = np.array([0.35, 0.25, 0.9], np.float32)
    light /= np.linalg.norm(light)
    lam = np.clip((n * light).sum(2), 0, 1) * 0.65 + 0.35
    depth = frac * 4096.0
    fog = np.clip(1.0 - depth / 2600.0, 0.25, 1.0)
    floor = n[..., 2] > 0.7
    base = np.where(floor[..., None], np.array([120, 135, 160], np.float32), np.array([205, 180, 140], np.float32))
    img = base * (lam * fog)[..., None]
    edge = (np.abs(np.diff(depth, axis=1, prepend=depth[:, :1])) > 24) | (np.abs(np.diff(depth, axis=0, prepend=depth[:1])) > 24)
    img[edge] *= 0.35
    img[frac >= 0.999] = (40, 45, 60)                                         # sky / void
    return np.clip(img, 0, 255).astype(np.uint8)


def overlay(img, fr, label, font, big):
    im = Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    v = fr["vel"]
    sp = math.hypot(v[0], v[1])
    fwd, side, jump, turn = int(fr["a"][0]) - 1, int(fr["a"][1]) - 1, int(fr["a"][2]), float(TURN_BINS[fr["a"][3]])
    vel_yaw = math.degrees(math.atan2(v[1], v[0])) if sp > 30 else fr["yaw"]
    off = (fr["yaw"] - vel_yaw + 180) % 360 - 180
    # speed bar with the 320 run cap
    d.rectangle([20, 20, 420, 44], outline=(255, 255, 255))
    d.rectangle([20, 20, 20 + int(min(sp, 900) / 900 * 400), 44], fill=(80, 220, 120) if sp > 320 else (230, 200, 80))
    cap = 20 + int(320 / 900 * 400)
    d.line([cap, 14, cap, 50], fill=(255, 80, 80), width=3)
    d.text((430, 18), "{:4.0f} u/s".format(sp), fill=(255, 255, 255), font=big)
    d.text((cap - 14, 52), "320", fill=(255, 80, 80), font=font)
    # keys
    keys = [("W", fwd > 0, (90, 420)), ("A", side < 0, (40, 470)), ("S", fwd < 0, (90, 470)), ("D", side > 0, (140, 470))]
    for k, on, (x, y) in keys:
        d.rectangle([x, y, x + 44, y + 44], fill=(240, 240, 240) if on else (40, 40, 40), outline=(200, 200, 200))
        d.text((x + 14, y + 10), k, fill=(0, 0, 0) if on else (160, 160, 160), font=big)
    d.rectangle([200, 470, 330, 514], fill=(240, 240, 240) if jump else (40, 40, 40), outline=(200, 200, 200))
    d.text((228, 480), "JUMP", fill=(0, 0, 0) if jump else (160, 160, 160), font=big)
    # mouse turn this frame (positive = left)
    cx = 760
    d.rectangle([cx - 150, 470, cx + 150, 514], outline=(200, 200, 200))
    x1 = cx - int(turn * 5)
    d.rectangle([min(cx, x1), 470, max(cx, x1), 514], fill=(120, 170, 255))
    d.text((cx - 150, 444), "mouse turn {:+.1f} deg/frame".format(turn), fill=(255, 255, 255), font=font)
    d.text((620, 414), "view vs velocity {:+.0f} deg".format(off), fill=(255, 255, 255), font=big)
    d.text((20, 70), "{}   {}".format(label, "airborne" if fr["ground"] < 0.5 else "on ground"), fill=(255, 255, 255), font=font)
    # crosshair
    d.line([W - 8, H, W + 8, H], fill=(255, 255, 255))
    d.line([W, H - 8, W, H + 8], fill=(255, 255, 255))
    return np.asarray(im)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="multimap_v1")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--trip", default=None, help="e.g. MH>LG; default = the fastest-looking trip")
    a = ap.parse_args()
    env = MoveEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"),
                  os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map)), n=1, seed=3)
    act = policy(a.run)
    rng = np.random.default_rng(0)
    ents = [e for e in env.w.entities if e.get("classname") in LABEL and "origin" in e]
    labels = [LABEL[e["classname"]] for e in ents]
    gidx = {}
    for e, lab in zip(ents, labels):
        if labels.count(lab) == 1:
            d = np.linalg.norm(env.goal_pos - np.array(e["origin"], np.float32), axis=1)
            if d.min() < 1:
                gidx[lab] = int(d.argmin())
    pairs = [(x, y) for x in gidx for y in gidx if x != y]
    if a.trip:
        pairs = [tuple(a.trip.split(">"))]
    best = None
    for x, y in pairs:
        frames, ok = run_trip(env, act, gidx[x], gidx[y], rng)
        if not ok or not 3.0 <= len(frames) * 0.025 <= 9.0 and not a.trip:
            continue
        score = sum(1 for f in frames if f["ground"] < 0.5 and math.hypot(*f["vel"][:2]) > 400)
        if best is None or score > best[0]:
            best = (score, x, y, frames)
    _, x, y, frames = best
    label = "{}: {} -> {} ({:.2f} s)".format(a.map, x, y, len(frames) * 0.025)
    print("rendering", label, len(frames), "frames", flush=True)
    xs = (np.arange(W) + 0.5) / W * 2 - 1
    ys = (np.arange(H) + 0.5) / H * 2 - 1
    tan_h = math.tan(math.radians(FOV / 2))
    tan_v = tan_h * H / W
    gx, gy = np.meshgrid(xs, ys)
    cam = np.stack([np.ones_like(gx), -gx * tan_h, -gy * tan_v], 2).astype(np.float32)   # forward, left, up
    cam /= np.linalg.norm(cam, axis=2, keepdims=True)
    cam = cam.reshape(-1, 3)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        big = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = big = ImageFont.load_default()
    out_dir = os.path.join(ROOT, "data", "sim_runs", a.run)
    name = "fp_{}_{}-{}".format(a.map, x, y)
    for suffix, fps in (("", 40), ("_slow", 10)):
        path = os.path.join(out_dir, name + suffix + ".mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                               "{}x{}".format(W * 2, H * 2), "-r", str(fps), "-i", "-", "-c:v", "libx264",
                               "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
        for fr in frames:
            ff.stdin.write(overlay(render(env, fr, cam), fr, label + ("   (1/4 speed)" if suffix else ""), font, big).tobytes())
        for _ in range(fps):                                                     # hold the last frame a second
            ff.stdin.write(overlay(render(env, frames[-1], cam), frames[-1], label, font, big).tobytes())
        ff.stdin.close()
        ff.wait()
        print("wrote", path, flush=True)


if __name__ == "__main__":
    main()

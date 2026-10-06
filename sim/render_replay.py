"""Render a video from a play-test session's frame log (the real game, e.g. Bobby against Nightmare on the server),
seen from Bobby's eyes with the same flat-shaded renderer as the simulator videos (sim/render_course.py). The log
has both players' positions, views, weapons, health and keys at 40 frames a second; projectiles and items are not
logged, so rockets in flight are not drawn.

    python sim/render_replay.py --session data/labtest/sessions/<dir> [--highlights 60] [--start 0 --secs 90] [--width 640]
"""
import argparse
import csv
import importlib
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import render_course as R            # noqa: E402

QLNAME = {5: "rl", 7: "rg", 6: "lg", 2: "mg", 3: "sg", 4: "gl", 8: "pg", 14: "hmg", 1: "g"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--env", default="duel_env_ffa_v8", help="any simulator module: only its world (ray casts) is used")
    ap.add_argument("--start", type=float, default=0.0, help="seconds after the arena start")
    ap.add_argument("--secs", type=float, default=90.0)
    ap.add_argument("--highlights", type=float, default=0.0, help="a reel of about this many seconds around Bobby's frags")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    R.E = E
    if a.width != 480:
        R.W, R.H, R.CRF = a.width, a.width * 9 // 16, "20"
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=1)
    rows = list(csv.DictReader(open(os.path.join(a.session, "frames.csv"))))
    ev = [json.loads(l) for l in open(os.path.join(a.session, "events.jsonl"), encoding="utf-8", errors="replace")]
    t0 = next((e["t"] for e in ev if e.get("event") == "arena_start"), float(rows[0]["t"]))
    deaths = [(e["t"], e["who"]) for e in ev if e.get("event") == "death"]
    hits = [(e["t"], e["victim"], e["dmg"]) for e in ev if e.get("event") == "hit"]
    xs = (np.arange(R.W) + 0.5) / R.W * 2 - 1
    ys = (np.arange(R.H) + 0.5) / R.H * 2 - 1
    tan_h = math.tan(math.radians(R.FOV / 2))
    gx, gy = np.meshgrid(xs, ys)
    cam = np.stack([np.ones_like(gx), -gx * tan_h, -gy * tan_h * R.H / R.W], 2).astype(np.float32)
    cam /= np.linalg.norm(cam, axis=2, keepdims=True)
    cam = cam.reshape(-1, 3)
    frames = []
    f_b, f_o = 0, 0
    di, hi = 0, 0
    for r in rows:
        t = float(r["t"])
        while di < len(deaths) and deaths[di][0] <= t:
            if deaths[di][1] == "opp":
                f_b += 1
            else:
                f_o += 1
            di += 1
        took, dealt = 0.0, 0.0
        while hi < len(hits) and hits[hi][0] <= t:
            if hits[hi][0] > t - 0.05:
                if hits[hi][1] == "bobby":
                    took += hits[hi][2]
                else:
                    dealt += hits[hi][2]
            hi += 1
        if t < t0 + a.start:
            continue
        if not a.highlights and t > t0 + a.start + a.secs:
            break
        g = lambda k: float(r[k] or 0)                                       # noqa: E731
        pos = np.array([g("b_x"), g("b_y"), g("b_z")], np.float32)
        opp = np.array([g("o_x"), g("o_y"), g("o_z")], np.float32)
        eye = pos + np.array([0, 0, 26.0], np.float32)
        seen = bool(env._los(eye[None], opp[None] + np.array([0, 0, 8.0], np.float32))[0]) and g("o_health") > 0
        bw, ow = QLNAME.get(int(g("b_weapon")), "mg"), QLNAME.get(int(g("o_weapon")), "mg")
        fwd, side, up, fire = int(np.sign(g("b_fwd"))), int(np.sign(g("b_right"))), g("b_up"), int(g("b_fire"))
        fr = dict(pos=pos, vel=np.array([g("b_vx"), g("b_vy"), g("b_vz")], np.float32), ground=float(abs(g("b_vz")) < 1),
                  yaw=g("b_yaw"), pitch=g("b_pitch"), opp=opp, opp_duck=bool(g("o_up") < 0), seen=seen,
                  hp=(g("b_health"), g("b_armor"), g("o_health"), g("o_armor")), w=(bw, ow), guns="Nightmare, the game's own bot",
                  opp_yaw=g("o_yaw"), opp_pitch=g("o_pitch"), opp_vel=np.array([g("o_vx"), g("o_vy"), g("o_vz")], np.float32),
                  zoom=False, intent="", rockets=[], booms=[],
                  others=[dict(pos=opp, duck=bool(g("o_up") < 0), yaw=g("o_yaw"), pitch=g("o_pitch"), w=ow, seen=seen,
                               shot=bool(int(g("o_fire"))), hurt=dealt > 0)],
                  items=[], a=np.array([fwd + 1, side + 1, 1 if up > 0 else 2 if up < 0 else 0, 0, 0, fire, 0, 0, 0, 0, 0], np.int64),
                  asked=0, frags=(f_b, f_o), shot=(bool(fire), bool(int(g("o_fire")))), took=took, dealt=dealt, t=t)
        frames.append(fr)
    label = "BobbyBones against Nightmare on the real server"
    name = "nightmare_{}.mp4".format(os.path.basename(a.session.rstrip("/\\")))
    if a.highlights > 0:
        hits_ = [i for i in range(1, len(frames)) if frames[i]["frags"][0] > frames[i - 1]["frags"][0]]
        pre, post, keep, last = int(3.2 / E.DT), int(1.0 / E.DT), [], -10 ** 9
        for i in hits_:
            lo = max(i - pre, last + 1, 0)
            if i - lo < int(1.5 / E.DT):
                lo = last + 1
            seg = list(range(lo, min(len(frames), i + post)))
            keep += seg
            last = seg[-1] if seg else last
            if len(keep) * E.DT >= a.highlights:
                break
        frames = [frames[j] for j in keep]
        label = "BobbyBones against Nightmare: his frags"
        name = name.replace(".mp4", "_highlights.mp4")
    out = a.out or os.path.join(ROOT, "videos", "replays", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        font, big = ImageFont.truetype("arial.ttf", 18), ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = big = ImageFont.load_default()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                           "{}x{}".format(R.W * 2, R.H * 2), "-r", "40", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", R.CRF, out], stdin=subprocess.PIPE)
    for i, fr in enumerate(frames):
        ff.stdin.write(R.overlay_fight(R.render(env, fr, cam), fr, label, i * E.DT, font, big).tobytes())
    ff.stdin.close()
    ff.wait()
    print("{} frames ({:.0f} s) -> {}".format(len(frames), len(frames) * E.DT, out))


if __name__ == "__main__":
    main()

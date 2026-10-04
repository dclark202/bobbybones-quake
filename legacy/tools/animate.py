"""Render the jumplab learning progress as a video: best attempt of each generation, played back in real time.

usage: python tools/animate.py data/jumplab_all.jsonl data/jumplab.mp4
"""
import json
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

src, out = sys.argv[1], sys.argv[2]
rs = [json.loads(l) for l in open(src)]
for i, r in enumerate(rs):
    r["n"] = i + 1

# best-so-far improvements, in the order they were discovered
show, best = [], -1e9
for r in rs:
    if r["score"] > best + 3 and len(r["path"]) > 5:
        best = r["score"]
        show.append(r)
show = show[-14:]

trace = np.loadtxt("data/campgrounds_trace.txt")
ground = trace[np.abs(trace[:, 5]) < 1]
top = ground[ground[:, 2] > 500]
low = ground[ground[:, 2] <= 500]

fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
ax = fig.add_axes([0.03, 0.08, 0.5, 0.82])
side = fig.add_axes([0.6, 0.12, 0.37, 0.6])
ax.scatter(low[:, 0], low[:, 1], s=1, c="#d8d8d8")
ax.scatter(top[:, 0], top[:, 1], s=1, c="#8fb3d9")
ax.add_patch(plt.Rectangle((330, -320), 190, 665, fill=False, ec="#d62728", lw=1.5))
ax.text(335, 355, "rail ledge", color="#d62728", fontsize=10)
ax.text(-380, -1110, "bridge (blue = top floor)", color="#1f5f9f", fontsize=10)
ax.plot(448, -160, marker="^", c="#d62728", ms=10)
ax.set_xlim(-400, 900)
ax.set_ylim(-1150, 420)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
side.axhline(538, c="#8fb3d9", lw=2)
side.axvline(-320, c="#d62728", ls="--")
side.text(-315, 600, "ledge edge", color="#d62728", fontsize=9)
side.set_xlim(-1050, -150)
side.set_ylim(380, 620)
side.set_xlabel("distance north (y)")
side.set_ylabel("height (z)")
side.set_title("side view")
title = fig.text(0.03, 0.94, "", fontsize=15, weight="bold")
sub = fig.text(0.6, 0.82, "", fontsize=12, family="monospace", va="top")
fig.text(0.6, 0.93, "Bot teaching itself the campgrounds bridge-to-rail jump", fontsize=11, color="#555")

ghosts, ghost_side = [], []
trail, = ax.plot([], [], c="#ff7f0e", lw=2)
dot, = ax.plot([], [], "o", c="#ff7f0e", ms=8)
strail, = side.plot([], [], c="#ff7f0e", lw=2)
sdot, = side.plot([], [], "o", c="#ff7f0e", ms=7)

frames = []
for k, r in enumerate(show):
    p = r["path"]
    for i in range(len(p)):
        frames.append((k, i))
    frames += [(k, len(p) - 1)] * 30  # hold the end for 0.75s

writer = FFMpegWriter(fps=40, bitrate=4000)
with writer.saving(fig, out, dpi=100):
    cur = -1
    for k, i in frames:
        r = show[k]
        p = np.array([q[:3] for q in r["path"]], dtype=float)
        if k != cur:
            if cur >= 0:
                prev = np.array([q[:3] for q in show[cur]["path"]], dtype=float)
                ghosts.append(ax.plot(prev[:, 0], prev[:, 1], c="#999", lw=0.8, alpha=0.5)[0])
                ghost_side.append(side.plot(prev[:, 1], prev[:, 2], c="#999", lw=0.8, alpha=0.5)[0])
            cur = k
            title.set_text("attempt #{}  (generation {})".format(r["n"], r["gen"]))
        sp = r["path"][i][3] if len(r["path"][i]) > 3 else 0
        result = "LANDED ON RAIL LEDGE" if r["success"] else ("fell short" if i == len(p) - 1 else "")
        sub.set_text("speed      {:4d} ups\npeak speed {:4d} ups\njumps      {:4d}\n{}".format(
            sp, r["peak_speed"], r["jumps"], result))
        trail.set_data(p[: i + 1, 0], p[: i + 1, 1])
        dot.set_data([p[i, 0]], [p[i, 1]])
        strail.set_data(p[: i + 1, 1], p[: i + 1, 2])
        sdot.set_data([p[i, 1]], [p[i, 2]])
        writer.grab_frame()
print("wrote", out, "attempts shown:", [r["n"] for r in show])

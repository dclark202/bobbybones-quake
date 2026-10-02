"""3D replay video of recorded attempts over the campgrounds point-cloud geometry.

usage: python tools/render3d.py out.mp4
"""
import json
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

OUT = sys.argv[1]
FPS = 25  # data is 40 Hz; we resample to real time

trace = np.loadtxt("data/campgrounds_trace.txt")
floor = trace[np.abs(trace[:, 5]) < 1][:, :3]
rows = [l.split() for l in open("data/practice/survey.txt")]
surv = np.array([[float(r[2]), float(r[3]), float(r[4])] for r in rows if r[-1] == "ok" and float(r[4]) < 630])
geo = np.vstack([floor, surv])
cells = []
for r in rows:
    if r[-1] != "ok":
        continue
    gx, gy, z = float(r[0]), float(r[1]), float(r[4])
    if z >= 639:
        continue                           # probe stuck in solid: skip
    top = z - 24                           # player origin is ~24 above the surface
    cells.append((gx - 16, gy - 16, top))
cells = np.array(cells)


def best(fn, pred=None):
    rs = [json.loads(l) for l in open(fn)]
    rs = [r for r in rs if r.get("path") and (pred is None or pred(r))]
    return max(rs, key=lambda r: r["score"])


clips = []
# --- pillars: platform -> A -> B ---
pil = best("data/practice/pillars_v2.jsonl")
path = np.array([q[:4] for q in pil["path"]], dtype=float)
# trim: stop 1.2 s after the second landing on pillar B
end = len(path)
for i, q in enumerate(path):
    if q[0] > -1300 and q[1] < 130 and q[2] > 530 and pil["path"][i][4] == 1:
        end = min(len(path), i + 48)
        break
clips.append(dict(title="Pillars by Yellow Armor: platform → pillar A → pillar B",
                  sub="learned by trial and error ({} attempts)".format(sum(1 for _ in open("data/practice/pillars_v2.jsonl"))),
                  path=path[:end], box=(-1600, -1100, -60, 420, -10, 640), elev=55, azim0=-100, slow=2, terrain=True))
# --- rocket jump ---
rj = best("data/practice/rj_high.jsonl")
path = np.array([q[:4] for q in rj["path"]], dtype=float)
x0, y0 = path[0, 0], path[0, 1]
clips.append(dict(title="Rocket jump: {} units of height".format(round(rj["score"])),
                  sub="look down, jump + fire in the same frame window (normal jump: ~47)",
                  path=path, box=(x0 - 300, x0 + 300, y0 - 300, y0 + 300, 0, 480), elev=10, azim0=-60, hold=40, slow=2))

fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
writer = FFMpegWriter(fps=FPS, bitrate=6000)
with writer.saving(fig, OUT, dpi=100):
    for clip in clips:
        p = clip["path"]
        x0, x1, y0, y1, z0, z1 = clip["box"]
        m = (geo[:, 0] > x0) & (geo[:, 0] < x1) & (geo[:, 1] > y0) & (geo[:, 1] < y1)
        g = geo[m]
        slow = clip.get("slow", 1)
        n_frames = int(len(p) / 40 * FPS * slow) + clip.get("hold", 25)
        tm = cells[(cells[:, 0] > x0 - 32) & (cells[:, 0] < x1) & (cells[:, 1] > y0 - 32) & (cells[:, 1] < y1)] if clip.get("terrain") else None
        for k in range(n_frames):
            i = min(len(p) - 1, int(k * 40 / FPS / slow))
            fig.clf()
            ax = fig.add_axes([0, 0, 1, 0.9], projection="3d")
            ax.computed_zorder = False
            if tm is not None:
                cmap = plt.get_cmap("viridis")
                cols = [cmap(min(1.0, max(0.0, t / 640.0))) for t in tm[:, 2]]
                ax.bar3d(tm[:, 0], tm[:, 1], np.zeros(len(tm)), 32, 32, np.maximum(tm[:, 2], 2), color=cols, alpha=0.55, shade=True, edgecolor="none", zorder=1)
            else:
                ax.plot_surface(*np.meshgrid([x0, x1], [y0, y1]), np.full((2, 2), p[0, 2] - 24), color="#bbbbbb", alpha=0.5)
            ax.plot(p[: i + 1, 0], p[: i + 1, 1], p[: i + 1, 2], c="#ff4500", lw=3, zorder=10)
            ax.scatter([p[i, 0]], [p[i, 1]], [p[i, 2]], s=160, c="#ff4500", edgecolors="k", depthshade=False, zorder=11)
            ax.plot([p[i, 0], p[i, 0]], [p[i, 1], p[i, 1]], [z0, p[i, 2]], c="#ff7f0e", lw=0.6, ls=":")
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_zlim(z0, z1)
            ax.set_box_aspect((x1 - x0, y1 - y0, (z1 - z0) * 1.0))
            ax.view_init(elev=clip["elev"], azim=clip["azim0"] + k * 0.25)
            ax.set_axis_off()
            fig.text(0.03, 0.94, clip["title"], fontsize=17, weight="bold")
            fig.text(0.03, 0.905, clip["sub"], fontsize=11, color="#555")
            fig.text(0.97, 0.94, "speed {:4.0f} ups   height {:4.0f}".format(p[i, 3], p[i, 2]), fontsize=13,
                     family="monospace", ha="right")
            if slow > 1:
                fig.text(0.97, 0.905, "{}x slow motion".format(1.0 / slow), fontsize=11, color="#555", ha="right")
            writer.grab_frame()
print("wrote", OUT)

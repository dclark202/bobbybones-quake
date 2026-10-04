"""Render an item-control run (itemrun_frames.jsonl) as a top-down video with live item timers.

usage: python tools/render_itemrun.py data/practice/itemrun_frames.jsonl data/itemrun.mp4 [start_s] [seconds]
"""
import json
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

src, out = sys.argv[1], sys.argv[2]
start_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
dur_s = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
FPS, STEP = 20, 2  # data is 40 Hz; render every 2nd frame

recs = [json.loads(l) for l in open(src)]
t0 = recs[0]["t"]
recs = [r for r in recs if start_s * 1000 <= r["t"] - t0 < (start_s + dur_s) * 1000]
events = []
try:
    for line in open(src.replace("itemrun_frames.jsonl", "itemrun_events.log")):
        if "picked" in line:
            events.append(line.strip())
except FileNotFoundError:
    pass

POS = {"RA": (256, -1344), "YA": (-1472, 448), "MH": (-576, -256)}
COL = {"RA": "#d62728", "YA": "#e6b800", "MH": "#1f77b4"}
NAME = {"RA": "Red Armor", "YA": "Yellow Armor", "MH": "Mega Health"}

trace = np.loadtxt("data/campgrounds_trace.txt")
g = trace[np.abs(trace[:, 5]) < 1]

fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
ax = fig.add_axes([0.0, 0.02, 0.62, 0.96])
ax.scatter(g[:, 0], g[:, 1], s=1, c=g[:, 2], cmap="Greys", vmin=-300, vmax=900)
for k, (x, y) in POS.items():
    ax.plot(x, y, "s", ms=16, mec=COL[k], mfc="none", mew=2)
ax.set_xlim(-1800, 1050)
ax.set_ylim(-1500, 1200)
ax.set_aspect("equal")
ax.axis("off")
timers = {k: ax.text(POS[k][0], POS[k][1] + 70, "", ha="center", fontsize=13, weight="bold", color=COL[k]) for k in POS}
trail, = ax.plot([], [], c="#ff7f0e", lw=1.5, alpha=0.8)
dot, = ax.plot([], [], "o", c="#ff7f0e", ms=9, mec="black")
flash = ax.text(0, 0, "", fontsize=12, weight="bold", ha="center")

side = fig.add_axes([0.64, 0.05, 0.34, 0.9])
side.axis("off")
side.text(0, 0.97, "Bot item control - campgrounds duel", fontsize=14, weight="bold", transform=side.transAxes)
side.text(0, 0.925, "armors respawn 25 s, mega 35 s", fontsize=10, color="#555", transform=side.transAxes)
clock = side.text(0, 0.85, "", fontsize=13, family="monospace", transform=side.transAxes)
rows = {k: side.text(0, 0.75 - i * 0.07, "", fontsize=13, family="monospace", color=COL[k], transform=side.transAxes)
        for i, k in enumerate(["RA", "MH", "YA"])}
stat = side.text(0, 0.47, "", fontsize=12, family="monospace", transform=side.transAxes, va="top")

pick_log = []
prev_avail = {}
spawn_seen = {}
hist_x, hist_y = [], []
writer = FFMpegWriter(fps=FPS, bitrate=5000)
with writer.saving(fig, out, dpi=100):
    for n, r in enumerate(recs):
        t = (r["t"] - t0) / 1000.0
        for k, (avail, ttl) in r["it"].items():
            was = prev_avail.get(k)
            if avail and was is False:
                spawn_seen[k] = t
            if was and not avail and abs(r["x"] - POS[k][0]) < 120 and abs(r["y"] - POS[k][1]) < 120:
                err = t - spawn_seen[k] if k in spawn_seen else None
                pick_log.append((t, k, err))
            prev_avail[k] = avail
        hist_x.append(r["x"])
        hist_y.append(r["y"])
        if n % STEP:
            continue
        hist_x, hist_y = hist_x[-160:], hist_y[-160:]
        trail.set_data(hist_x, hist_y)
        dot.set_data([r["x"]], [r["y"]])
        for k, (avail, ttl) in r["it"].items():
            timers[k].set_text("UP" if avail else "{:.1f}".format(max(ttl, 0)))
            rows[k].set_text("{:<13} {}".format(NAME[k], "UP" if avail else "{:5.1f} s".format(max(ttl, 0))))
        clock.set_text("time {:6.1f} s   speed {:4d} ups\nstate: {}".format(t, r["v"], "waiting for spawn" if r["s"] == "wait" else "-> " + r["s"]))
        recent = [p for p in pick_log if t - p[0] < 1.5]
        if recent:
            pt, pk, perr = recent[-1]
            flash.set_position((POS[pk][0], POS[pk][1] - 130))
            flash.set_color(COL[pk])
            flash.set_text("{} {}".format(pk, "+{:.2f}s".format(perr) if perr is not None else ""))
        else:
            flash.set_text("")
        timed = [p for p in pick_log if p[2] is not None]
        lines = ["pickups: {}".format(len(pick_log))]
        if timed:
            errs = sorted(abs(p[2]) for p in timed)
            lines.append("median time after spawn: {:.2f} s".format(errs[len(errs) // 2]))
        lines.append("")
        for pt, pk, perr in pick_log[-8:]:
            lines.append("{:6.1f}s  {}  {}".format(pt, pk, "+{:.2f}s after spawn".format(perr) if perr is not None else ""))
        stat.set_text("\n".join(lines))
        writer.grab_frame()
print("wrote", out, "seconds:", (recs[-1]["t"] - recs[0]["t"]) / 1000.0 if recs else 0, "pickups:", len(pick_log))

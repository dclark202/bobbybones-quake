"""Analyze a human-vs-bot session on campgrounds.

inputs : data/practice/trace_live.txt      (frame id x y z vx vy vz, all players, 40 Hz)
         data/practice/itemrun_frames.jsonl (bot telemetry incl. item states, 40 Hz)
outputs: data/session_report.txt, data/session_map.png
"""
import json
import math
from collections import defaultdict

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HUMAN, BOT = 1, 0
ITEMS = {"RA": (256, -1344, 208), "YA": (-1472, 448, 528), "MH": (-576, -256, 16)}

# the trace file spans several server restarts (frame counter resets); keep the latest segment
segments, cur, last = [], [], -1
for line in open("data/practice/trace_live.txt"):
    f = line.split()
    if len(f) != 8:
        continue
    fr = int(f[0])
    if fr < last:
        segments.append(cur)
        cur = []
    last = fr
    cur.append((fr, int(f[1])) + tuple(map(float, f[2:])))
segments.append(cur)
tr = defaultdict(list)
for row in segments[-1]:
    tr[row[1]].append((row[0],) + row[2:])
hum = np.array(tr[HUMAN])
bot = np.array(tr[BOT])
recs_all = [json.loads(l) for l in open("data/practice/itemrun_frames.jsonl")]
recs, last_t = [], -1
for r in recs_all:          # keep only the latest run (level time resets on restart)
    if r["t"] < last_t:
        recs = []
    recs.append(r)
    last_t = r["t"]

# align itemrun telemetry (level time) with trace frames using the bot's position
bot_by_pos = {}
for fr, x, y, z, *_ in tr[BOT]:
    bot_by_pos.setdefault((round(x), round(y), round(z)), fr)
offset = None
for r in recs:
    k = (r["x"], r["y"], r["z"])
    if k in bot_by_pos and r["v"] > 50:
        offset = bot_by_pos[k] - r["t"] / 25.0   # trace frame = t/25ms + offset
        break
hum_by_frame = {int(row[0]): row for row in hum}
bot_by_frame = {int(row[0]): row for row in bot}

# session window = frames where the human exists
f0, f1 = hum[0, 0], hum[-1, 0]
secs = (f1 - f0) / 40.0


def stats(arr, name):
    sp = np.hypot(arr[:, 4], arr[:, 5])
    alive = sp < 2000
    sp = sp[alive]
    deaths = int(np.sum(np.hypot(np.diff(arr[:, 1]), np.diff(arr[:, 2])) > 250))
    top = np.mean(arr[:, 3] > 500) * 100
    return ("{:<6} avg speed {:5.0f} ups | time above 320 ups (strafe-jumping) {:4.1f}% | top speed {:4.0f} | "
            "respawns {:2d} | time on top floors {:4.1f}%").format(name, sp.mean(), np.mean(sp > 330) * 100, sp.max(), deaths, top)


lines = ["Session: {:.1f} minutes on campgrounds (warmup duel, you vs Sarge)".format(secs / 60), "",
         stats(hum, "You"), stats(bot[(bot[:, 0] >= f0) & (bot[:, 0] <= f1)], "Sarge"), ""]

# item pickups: up -> taken transitions, credited to whoever was closest
picks = []
prev = {}
spawned = {}
for r in recs:
    fr = None if offset is None else int(round(r["t"] / 25.0 + offset))
    if fr is None or fr < f0 or fr > f1:
        for k, (av, ttl) in r["it"].items():
            prev[k] = av
        continue
    for k, (av, ttl) in r["it"].items():
        was = prev.get(k)
        if av and was is False:
            spawned[k] = r["t"]
        if was and not av:
            h = hum_by_frame.get(fr)
            if h is None:
                h = hum_by_frame.get(fr - 1)
            dh = math.dist(h[1:4], ITEMS[k]) if h is not None else 1e9
            db = math.dist((r["x"], r["y"], r["z"]), ITEMS[k])
            who = "You" if dh < db else "Sarge"
            late = (r["t"] - spawned[k]) / 1000.0 if k in spawned else None
            picks.append(((fr - f0) / 40.0, k, who, late))
        prev[k] = av

lines.append("Item pickups ({}):".format(len(picks)))
for who in ("You", "Sarge"):
    mine = [p for p in picks if p[2] == who]
    by = defaultdict(int)
    for p in mine:
        by[p[1]] += 1
    timed = [p[3] for p in mine if p[3] is not None]
    lines.append("  {:<6} RA {}  YA {}  MH {}   median time after spawn: {}".format(
        who, by["RA"], by["YA"], by["MH"], "{:.1f}s".format(sorted(timed)[len(timed) // 2]) if timed else "n/a"))
lines.append("")
lines.append("Timeline (time, item, who, seconds after it spawned):")
for t, k, who, late in picks:
    lines.append("  {:6.1f}s  {}  {:<6} {}".format(t, k, who, "+{:.1f}s".format(late) if late is not None else ""))

# where the human spends time
zones = {"RA room": (256, -1344, 200), "Mega area": (-576, -256, 300), "YA platform": (-1450, 400, 200),
         "Rail ledge": (450, 0, 250), "Bridge (top)": (150, -900, 300)}
lines.append("")
lines.append("Where you spent your time:")
for name, (x, y, r) in zones.items():
    pct = np.mean(np.hypot(hum[:, 1] - x, hum[:, 2] - y) < r) * 100
    lines.append("  {:<13} {:4.1f}%".format(name, pct))

open("data/session_report.txt", "w").write("\n".join(lines))
print("\n".join(lines))

trace = np.loadtxt("data/campgrounds_trace.txt")
g = trace[np.abs(trace[:, 5]) < 1]
fig, axs = plt.subplots(1, 2, figsize=(16, 8))
for ax, arr, title, col in ((axs[0], hum, "You", "Reds"), (axs[1], bot[(bot[:, 0] >= f0) & (bot[:, 0] <= f1)], "Sarge", "Blues")):
    ax.scatter(g[:, 0], g[:, 1], s=1, c="#dddddd")
    ax.hexbin(arr[:, 1], arr[:, 2], gridsize=45, cmap=col, mincnt=3, alpha=0.85)
    for k, (x, y, z) in ITEMS.items():
        ax.plot(x, y, "k^", ms=10)
        ax.text(x + 40, y, k, fontsize=11, weight="bold")
    ax.set_title(title + ": where you spent time")
    ax.set_aspect("equal")
    ax.set_xlim(-1800, 1050)
    ax.set_ylim(-1500, 1200)
    ax.set_xticks([])
    ax.set_yticks([])
plt.savefig("data/session_map.png", dpi=70, bbox_inches="tight")

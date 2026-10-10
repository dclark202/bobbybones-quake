"""A picture of tools/speed_profile.py's files (system Python: matplotlib is broken in the Anaconda Python).

    python tools/draw_speed.py out.png pros.json v14end.json now.json

Left: his travelling time (no enemy in view) by speed, a bar a source. Middle: the speed at the 1st, 2nd, 3rd ...
take-off of a chain of hops. Right: a minute of speed over time for the first and the last source, a tick at every
take-off, the stretches with an enemy in view marked along the bottom, a line at 400.
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

out, files = sys.argv[1], sys.argv[2:]
R = [json.load(open(f)) for f in files]
BAND = ("standing (under 40)", "slow (to 200)", "running (to 345)", "fast (to 420)", "very fast")
SHADE = ("#c9ccd1", "#9aa3ad", "#6f8fb3", "#3f73b7", "#1b3f8f")
LINE = ("#2b2b2b", "#b0562f", "#1f6fb5", "#3a8f4a", "#7a4fa3")
fig = plt.figure(figsize=(17, 5.6), dpi=130)
gs = fig.add_gridspec(2, 3, width_ratios=(1.0, 1.0, 1.7), hspace=0.35, wspace=0.22)

ax = fig.add_subplot(gs[:, 0])
for i, r in enumerate(R):
    left = 0.0
    for b in range(5):
        v = r["time_by_speed"]["travel"][b]
        ax.barh(i, v, left=left, color=SHADE[b], edgecolor="white", height=0.62)
        if v >= 0.06:
            ax.text(left + v / 2, i, "{:.0f}%".format(100 * v), ha="center", va="center", color="white" if b >= 2 else "#222", fontsize=9)
        left += v
    ax.text(1.02, i, "{:.1f}% at 400+".format(100 * r["at_400"]["time_share"]), va="center", fontsize=9, color="#222")
ax.set_yticks(range(len(R)))
ax.set_yticklabels([r["tag"] for r in R])
ax.invert_yaxis()
ax.set_xlim(0, 1.32)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
ax.set_title("Travelling time by speed (no enemy in view)", fontsize=11, loc="left")
for s_ in ("top", "right"):
    ax.spines[s_].set_visible(False)
ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in SHADE], BAND, fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)

ax = fig.add_subplot(gs[:, 1])
for i, r in enumerate(R):
    h = r["speed_at_hop"]
    if h:
        ax.plot([x["hop"] for x in h], [x["speed"] for x in h], marker="o", color=LINE[i % len(LINE)], linewidth=2, label=r["tag"])
        ax.text(h[-1]["hop"] + 0.1, h[-1]["speed"], r["tag"], color=LINE[i % len(LINE)], fontsize=9, va="center")
ax.axhline(320, color="#888", linewidth=0.8, linestyle=":")
ax.text(1, 322, "a runner's top speed", fontsize=8, color="#666", va="bottom")
ax.set_xlabel("take-off number in a chain of hops")
ax.set_ylabel("speed at the take-off")
ax.set_xlim(0.8, 7.6)
ax.set_title("Is speed built hop by hop?", fontsize=11, loc="left")
for s_ in ("top", "right"):
    ax.spines[s_].set_visible(False)

pick = [R[0], R[-1]] if len(R) > 1 else [R[0]]
for j, r in enumerate(pick):
    ax = fig.add_subplot(gs[j, 2])
    tr = r.get("trace")
    if tr:
        t = [k * 0.025 for k in range(len(tr["speed"]))]
        ax.plot(t, tr["speed"], color=LINE[(0 if j == 0 else len(R) - 1) % len(LINE)], linewidth=1.0)
        ax.vlines([h * 0.025 for h in tr["hops"]], 0, 28, color="#444", linewidth=0.8)
        ax.scatter([v * 0.025 for v in tr["inview"]], [-12] * len(tr["inview"]), s=3, color="#c0392b", marker="s")
    ax.axhline(400, color="#888", linewidth=0.8, linestyle=":")
    ax.set_ylim(-25, 720)
    ax.set_xlim(0, 60)
    ax.set_title("{}: a minute of one life (ticks: take-offs; red: an enemy in view)".format(r["tag"]), fontsize=10, loc="left")
    ax.set_ylabel("speed")
    if j == len(pick) - 1:
        ax.set_xlabel("seconds")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
fig.savefig(out, bbox_inches="tight")
print("wrote", out)

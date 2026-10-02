import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rs = [json.loads(l) for l in open("data/jumplab.jsonl")]
best = sorted(rs, key=lambda r: -r["score"])[:6]
d = np.loadtxt("data/campgrounds_trace.txt")
g = d[(np.abs(d[:, 5]) < 1) & (d[:, 2] > 500)]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 8))
a1.scatter(g[:, 0], g[:, 1], s=1, c="lightgray")
for r in best:
    p = np.array(r["path"])
    a1.plot(p[:, 0], p[:, 1], lw=1.5, label="score {:.0f} {} v{}".format(r["score"], r["why"], r["peak_speed"]))
    a2.plot(p[:, 1], p[:, 2], lw=1.5)
a1.add_patch(plt.Rectangle((330, -320), 190, 665, fill=False, ec="red"))
a1.set_xlim(-400, 900); a1.set_ylim(-1200, 400); a1.set_aspect("equal"); a1.legend(fontsize=8); a1.set_title("top view: best attempts (gray = top-floor walkable)")
a2.axhline(538, c="gray", ls="--"); a2.axvline(-320, c="red", ls="--")
a2.set_xlabel("y"); a2.set_ylabel("z"); a2.set_title("side view (y vs height); red = ledge start, gray = floor height")
plt.savefig(sys.argv[1] if len(sys.argv) > 1 else "data/jump_attempts.png", dpi=70, bbox_inches="tight")
for r in best[:3]:
    print({k: round(v) for k, v in r["params"].items()}, round(r["score"]), r["why"], r["peak_speed"], "end", r["path"][-1])

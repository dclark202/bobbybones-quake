"""Plot the drop-probe survey as a heightmap and list raised surfaces (pillar candidates)."""
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = [l.split() for l in open("data/practice/survey.txt")]
pts = np.array([[float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in rows if r[-1] == "ok"])
void = np.array([[float(r[0]), float(r[1])] for r in rows if r[-1] == "void"]) if any(r[-1] == "void" for r in rows) else np.zeros((0, 2))
trace = np.loadtxt("data/campgrounds_trace.txt")
g = trace[(np.abs(trace[:, 5]) < 1) & (trace[:, 0] < -950) & (trace[:, 1] > -100) & (trace[:, 1] < 750)]

fig, ax = plt.subplots(figsize=(10, 11))
sc = ax.scatter(pts[:, 2], pts[:, 3], c=pts[:, 4], s=90, marker="s", cmap="viridis", vmin=0, vmax=650)
plt.colorbar(sc, label="landing height (z)")
if len(void):
    ax.scatter(void[:, 0], void[:, 1], c="red", s=12, marker="x", label="void / out of map")
ax.scatter(g[:, 0], g[:, 1], s=1, c="white", alpha=0.6, label="where bots walk")
ax.plot(-1472, 448, "y*", ms=22, mec="k", label="yellow armor")
for x, y, X, Y, z in pts:
    ax.text(X, Y, "{:.0f}".format(z), fontsize=6, ha="center", va="center", color="w")
ax.set_aspect("equal")
ax.legend(loc="lower left", fontsize=8)
ax.set_title("drop-probe heightmap near yellow armor (landing z)")
plt.savefig("data/survey_ya.png", dpi=80, bbox_inches="tight")

# surfaces higher than the floor around them that bots never stand on = pillar candidates
walked = g[:, :3]
cand = []
for x, y, X, Y, z in pts:
    near = walked[(np.abs(walked[:, 0] - X) < 40) & (np.abs(walked[:, 1] - Y) < 40) & (np.abs(walked[:, 2] - (z)) < 30)]
    if len(near) == 0 and z > 40:
        cand.append((round(X), round(Y), round(z)))
print("probes ok:", len(pts), "void:", len(void))
print("unwalked raised surfaces:", sorted(cand, key=lambda c: (-c[2], c[0], c[1])))

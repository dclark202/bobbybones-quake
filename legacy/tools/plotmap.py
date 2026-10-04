import re, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = np.loadtxt("data/campgrounds_trace.txt")
ground = d[np.abs(d[:, 5]) < 1]  # vz == 0 -> standing/running on a floor
items = []
for line in open("data/campgrounds_items.txt"):
    m = re.match(r"item \d+ (\S+) at \((-?\d+),(-?\d+),(-?\d+)\)", line)
    if m:
        items.append((m.group(1), *map(int, m.groups()[1:])))

fig, ax = plt.subplots(figsize=(12, 12))
sc = ax.scatter(ground[:, 0], ground[:, 1], c=ground[:, 2], s=2, cmap="viridis")
plt.colorbar(sc, label="floor height (z)")
for name, x, y, z in items:
    if name.startswith(("weapon_", "item_armor_body", "item_armor_combat", "item_quad", "item_health_mega")):
        ax.plot(x, y, "r^", ms=9)
        ax.annotate("{} z{}".format(name.replace("weapon_", "").replace("item_", ""), z), (x, y), fontsize=9, color="red")
ax.set_aspect("equal"); ax.grid(alpha=.3)
ax.set_title("campgrounds: where bots stood (colour = height)")
plt.savefig("data/campgrounds_map.png", dpi=80, bbox_inches="tight")
# height histogram of floors
z = np.round(ground[:, 2] / 8) * 8
vals, counts = np.unique(z, return_counts=True)
print([(int(v), int(c)) for v, c in zip(vals, counts) if c > 100])

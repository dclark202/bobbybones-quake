"""The compact table the simulator's weapon teacher reads (PRO_WEAPON): per map, per 100 units of distance, the share of
rockets / rail / lightning among the frames a pro fired one of them while owning all three.

    python tools/pro_seed.py        docs/pro_tables.json (tools/pro_tables.py, 50-unit bins) -> sim/pro_seed.json

A map without such frames (no rail on it, or no demos) is left out: the simulator then takes "all", the maps together.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = json.load(open(os.path.join(ROOT, "docs", "pro_tables.json"), encoding="utf-8"))
seed = {}
for mp, d in src.items():
    fr = d["fired_frames"]
    if sum(fr) == 0:
        continue
    rows = []
    for b in range(15):
        n = fr[2 * b] + fr[2 * b + 1]
        rows.append([round((d["fired_by_distance"][w][2 * b] * fr[2 * b] + d["fired_by_distance"][w][2 * b + 1] * fr[2 * b + 1]) / max(1, n), 3)
                     for w in ("rl", "rg", "lg")])
    seed[mp] = dict(weapon_by_100_units=rows, order=["rl", "rg", "lg"], demos=d["demos"])
json.dump(seed, open(os.path.join(ROOT, "sim", "pro_seed.json"), "w", encoding="utf-8"), indent=1)
print("sim/pro_seed.json:", list(seed))

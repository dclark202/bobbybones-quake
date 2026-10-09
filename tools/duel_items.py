"""duel_items.py: the real game's duel items per map (class, resting place), from the listing of plugins/maplab.py
(data/maplab/maplab.jsonl) -> plugins/duel_items.json. The plugins give a free-for-all game this layout (owner,
2026-10-09: "use the duel weapon locations for all of the maps ... the only ones that exist in our world").

    python tools/duel_items.py            # after a new listing (a map added to the servers)
"""
import collections
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POWERUPS = ("item_quad", "item_enviro", "item_haste", "item_invis", "item_regen", "item_flight", "holdable_invulnerability")
rows = [json.loads(x) for x in open(os.path.join(ROOT, "data", "maplab", "maplab.jsonl")) if x.strip()]
out = {}
for r in rows:
    if r["factory"] == "duel" and r["map"] not in out:
        out[r["map"]] = [[i["cls"]] + [round(float(v), 1) for v in i["at"]] for i in r["items"] if i["cls"] not in POWERUPS]
json.dump(out, open(os.path.join(ROOT, "plugins", "duel_items.json"), "w"), separators=(",", ":"), sort_keys=True)
for mp, its in out.items():
    ffa = next((r for r in rows if r["map"] == mp and r["factory"] == "ffa"), None)
    d = collections.Counter(i[0] for i in its)
    line = "{:15s} {} items in a duel".format(mp, len(its))
    if ffa:
        f = collections.Counter(i["cls"] for i in ffa["items"])
        diff = {k: f.get(k, 0) - d.get(k, 0) for k in sorted(set(f) | set(d)) if f.get(k, 0) != d.get(k, 0)}
        moved = sum(1 for i in ffa["items"] if not any(i["cls"] == j[0] and abs(i["at"][0] - j[1]) < 40 and abs(i["at"][1] - j[2]) < 40 for j in its))
        line += "; free-for-all has {} ({} of them not at a duel item's place); by kind, free-for-all minus duel: {}".format(len(ffa["items"]), moved, diff or "the same")
    print(line)

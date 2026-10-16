"""Tables from tools/rj_compare.py's files: python tools/rj_report.py <switches off.json> <switches on.json> [--rows]"""
import json
import sys
from collections import defaultdict

off = json.load(open(sys.argv[1]))
on = json.load(open(sys.argv[2]))
show_rows = "--rows" in sys.argv


def rel(a, b):
    return abs(a - b) / max(abs(a), 1e-9)


def summary(data, label):
    n = 0
    ok = defaultdict(int)
    errs = defaultdict(list)
    for o in data:
        g, s = o["game"], o["sim"]
        if g is None or s is None:
            continue
        n += 1
        rr = rel(g["rise"], s["rise"])
        dd = abs(g["dist"] - s["dist"]) / max(g["dist"], 20.0)       # under 20 units: the share of 20
        vv = rel(g["top_vz"], s["top_vz"])
        ok["rise5"] += rr <= 0.05
        ok["dist5"] += dd <= 0.05
        ok["vz5"] += vv <= 0.05
        ok["dmg"] += abs(g["dmg"] - s["dmg"]) < 0.01 and abs(g["armor"] - s["armor"]) < 0.01
        ok["dmg1"] += abs(g["total"] - s["total"]) <= 1.01
        ok["blast"] += g["blast"] == s["blast"]
        ok["land"] += g["land"] == s["land"] or (g["land"] is not None and s["land"] is not None and abs(g["land"] - s["land"]) <= 1)
        errs["rise"].append(s["rise"] - g["rise"])
        errs["dist"].append(s["dist"] - g["dist"])
        errs["vz"].append(s["top_vz"] - g["top_vz"])
        errs["dmg"].append(s["total"] - g["total"])
    import numpy as np
    print("%-7s %3d jumps | rise within 5%%: %3d | dist within 5%%: %3d | top vz within 5%%: %3d | damage exact: %3d, within 1: %3d"
          " | blast frame same: %3d | landing within a frame: %3d" % (label, n, ok["rise5"], ok["dist5"], ok["vz5"], ok["dmg"],
                                                                     ok["dmg1"], ok["blast"], ok["land"]))
    for k in ("rise", "dist", "vz", "dmg"):
        e = np.array(errs[k])
        print("         sim - game %-5s mean %+7.1f  median %+7.1f  max |.| %6.1f" % (k, e.mean(), np.median(e), np.abs(e).max()))
    return n


for label, data in (("off", off), ("RL_QL", on)):
    summary(data, label)
print()
# by kind of jump
kinds = defaultdict(list)
for a, b in zip(off, on):
    k = (a["map"], a["place"], "st" if a["fire"] is None else "f%d" % a["fire"], a["armor"] > 0)
    kinds[k].append((a, b))
print("by kind (rep 0 and 1 together): mean game / off / RL_QL")
for k in sorted(kinds, key=str):
    v = kinds[k]
    def m(sel, key):
        xs = [sel(x)[key] for x in v if sel(x) is not None]
        return sum(xs) / max(len(xs), 1)
    print("%-9s %-4s %-3s armor%d n%3d | rise %5.0f %5.0f %5.0f | dist %5.0f %5.0f %5.0f | vz %4.0f %4.0f %4.0f | dmg %5.1f %5.1f %5.1f" % (
        k[0][:9], k[1], k[2], k[3], len(v),
        m(lambda x: x[0]["game"], "rise"), m(lambda x: x[0]["sim"], "rise"), m(lambda x: x[1]["sim"], "rise"),
        m(lambda x: x[0]["game"], "dist"), m(lambda x: x[0]["sim"], "dist"), m(lambda x: x[1]["sim"], "dist"),
        m(lambda x: x[0]["game"], "top_vz"), m(lambda x: x[0]["sim"], "top_vz"), m(lambda x: x[1]["sim"], "top_vz"),
        m(lambda x: x[0]["game"], "total"), m(lambda x: x[0]["sim"], "total"), m(lambda x: x[1]["sim"], "total")))
# the game's repeatability
by = defaultdict(list)
for o in off:
    by[(o["map"], o["name"])].append(o["game"])
pairs = [v for v in by.values() if len(v) > 1 and all(v)]
if pairs:
    print("\ngame repeatability over %d pairs: rise differs by max %.2f, distance by max %.2f, damage by max %.0f" % (
        len(pairs), max(abs(v[0]["rise"] - v[1]["rise"]) for v in pairs), max(abs(v[0]["dist"] - v[1]["dist"]) for v in pairs),
        max(abs(v[0]["total"] - v[1]["total"]) for v in pairs)))
if show_rows:
    print("\n%-34s %-8s | game: bl dmg arm   vz  rise  dist land | off: bl dmg   vz  rise  dist land | RL_QL: bl dmg arm  vz  rise  dist land" % ("case", "map"))
    for a, b in zip(off, on):
        if a["rep"] != 0:
            continue
        g, s, q = a["game"], a["sim"], b["sim"]
        f = lambda x, arm=True: ("%2s %3s %s%4.0f %5.0f %5.0f %4s" % (x["blast"], round(x["dmg"]), ("%3s " % round(x["armor"])) if arm else "",
                                                               x["top_vz"], x["rise"], x["dist"], x["land"])) if x else "-"
        print("%-34s %-8s | %s | %s | %s" % (a["name"], a["map"][:8], f(g), f(s, False), f(q)))

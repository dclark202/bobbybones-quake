"""The game's movement cases (plugins/physlab.py) beside the simulator's replays (tools/phys_sim.py), measure by measure.

    python tools/phys_compare.py <physlab.jsonl> <sim.json> [<sim2.json> ...] [--md] [--cases]

For each case and each of its measures: the game's number and each simulator's, and whether it is within 5% of the
game's (or within a small floor for numbers near zero: 2 u/s of speed, 1 u/s of a gain, 4 units of distance or height,
1 frame). The table at the end: by group of cases, the share of measures within 5%, per simulator. Repetitions: the
two takes of every case are set side by side first (the game's own repeatability).
"""
import json
import math
import sys
from collections import defaultdict

FLOOR = dict(speed=2.0, gain=1.0, dist=4.0, rise=2.0, frame=1.0, hops=0.0)


def group(name):
    for p, g in (("air_f_v", "air: forward held"), ("air_none", "air: no key"), ("air_back", "air: back"),
                 ("air_fr", "air: forward + strafe at an angle"), ("air_r_", "air: strafe alone at an angle"),
                 ("air_rturn", "air: strafe + turning"), ("air_frturn", "air: forward + strafe + turning"),
                 ("air_walk", "air: walk key"), ("air_fl", "air: forward + strafe at an angle"),
                 ("hop_", "strafe-jump chains"), ("land_", "landing and the next jump"),
                 ("hops_", "hops with forward held"), ("walk_", "floor: from a stand"), ("stop_", "floor: friction"),
                 ("run_", "floor: forward above running speed"),
                 ("crouch", "floor: crouch"), ("circle", "floor: circle strafe"), ("side_", "floor: from a stand"),
                 ("ramps", "ramps and stairs"), ("climb", "climb (ledges of 40)")):
        if name.startswith(p):
            return g
    return "other"


def hsp(r):
    return math.hypot(r[4], r[5])


def airborne(rows):
    """per row: in the air (vz not 0)"""
    return [abs(r[6]) > 1e-3 for r in rows]


def takeoffs(rows):
    out = []
    for k in range(1, len(rows)):
        if rows[k][6] > 100 and rows[k - 1][6] <= 1e-3 + (0 if k > 1 else 1e9):
            out.append(k)
    return out


def landings(rows):
    out = []
    for k in range(1, len(rows)):
        if abs(rows[k][6]) <= 1e-3 and rows[k - 1][6] < -1e-3:
            out.append(k)
    return out


def measures(name, rows):
    """rows: [k, x, y, z, vx, vy, vz, ...] from k = 0 (the start) on"""
    m = {}
    r0, rN = rows[0], rows[-1]
    m["speed_end"] = ("speed", hsp(rN))
    m["dist_end"] = ("dist", math.hypot(rN[1] - r0[1], rN[2] - r0[2]))
    m["rise"] = ("rise", max(r[3] for r in rows) - r0[3])
    la = landings(rows)
    to = takeoffs(rows)
    if name.startswith("air_"):
        k1 = la[0] if la else len(rows) - 1
        m["land_frame"] = ("frame", float(k1))
        m["air_gain"] = ("gain", hsp(rows[k1 - 1]) - hsp(r0))
        m["air_dist"] = ("dist", math.hypot(rows[k1][1] - r0[1], rows[k1][2] - r0[2]))
    if name.startswith(("hop_", "hops_", "ramps", "climb")):
        m["hops"] = ("hops", float(len(to)))
        for k in (40, 80, 120, 160):
            if k < len(rows):
                m["speed_%d" % k] = ("speed", hsp(rows[k]))
                m["dist_%d" % k] = ("dist", math.hypot(rows[k][1] - r0[1], rows[k][2] - r0[2]))
        if name.startswith(("ramps", "climb")):
            m["x_end"] = ("dist", rN[1] - r0[1])
            m["z_end"] = ("rise", rN[3] - r0[3])
    if name.startswith("land_"):
        m["land_frame"] = ("frame", float(la[0]) if la else -1.0)
        if len(to) >= 1:
            k2 = to[0]
            m["jump2_frame"] = ("frame", float(k2))
            m["jump2_speed"] = ("speed", hsp(rows[k2]))
    if name.startswith(("walk_", "stop_", "crouch", "circle", "side_", "run_")):
        for k in (3, 10, 20):
            m["speed_%d" % k] = ("speed", hsp(rows[k]))
    return m


def within(kind, g, s):
    return abs(s - g) <= max(0.05 * abs(g), FLOOR[kind])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    md = "--md" in sys.argv
    show = "--cases" in sys.argv
    recs = [json.loads(l) for l in open(args[0]) if l.strip()]
    recs = [r for r in recs if r["name"] != "warmup"]
    sims = []
    for p in args[1:]:
        d = json.load(open(p))
        sims.append((p, d.get("switches", {}), {(c["name"], c["rep"]): c for c in d["cases"]}))
    # the game's repeatability
    by = defaultdict(dict)
    for r in recs:
        by[r["name"]][r["rep"]] = r
    same = diff = 0
    worst = 0.0
    for n, reps in by.items():
        if 0 in reps and 1 in reps:
            a, b = reps[0]["rows"], reps[1]["rows"]
            d = max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra[1:7], rb[1:7]))
            worst = max(worst, d)
            same += d < 0.01
            diff += d >= 0.01
    print("the game's two takes: {} cases the same to 0.01, {} not (largest difference {:.3f})".format(same, diff, worst))
    tab = defaultdict(lambda: [[0, 0] for _ in sims])
    rows_out = []
    for r in recs:
        gm = measures(r["name"], [[0] + r["start"] + r["start_vel"]] + [x[:7] for x in r["rows"][1:]])
        line = [r["name"], r["rep"]]
        for si, (p, sw, cases) in enumerate(sims):
            c = cases.get((r["name"], r["rep"]))
            if c is None:
                continue
            sm = measures(r["name"], [x[:7] for x in c["sim"]][:len(r["rows"])])
            for k, (kind, gv) in gm.items():
                if k not in sm:
                    continue
                ok = within(kind, gv, sm[k][1])
                tab[(group(r["name"]), k)][si][0] += ok
                tab[(group(r["name"]), k)][si][1] += 1
                tab[(group(r["name"]), "all")][si][0] += ok
                tab[(group(r["name"]), "all")][si][1] += 1
                tab[("ALL", "all")][si][0] += ok
                tab[("ALL", "all")][si][1] += 1
                if show and r["rep"] == 0:
                    rows_out.append((r["name"], k, gv, si, sm[k][1], ok))
    if show:
        for n, k, gv, si, sv, ok in rows_out:
            print("{:28s} {:12s} game {:9.2f} sim{} {:9.2f} {}".format(n, k, gv, si, sv, "ok" if ok else "MISS"))
    hdr = ["group", "measure"] + ["{} {}".format(p.split("/")[-1].split("\\")[-1], ",".join("{}={}".format(k, v) for k, v in sw.items() if v)) for p, sw, _ in sims]
    print(("| " + " | ".join(hdr) + " |") if md else "\t".join(hdr))
    if md:
        print("|" + "---|" * len(hdr))
    for key in sorted(tab, key=lambda t: (t[0] == "ALL", t[0], t[1] != "all", t[1])):
        cells = ["{}/{}".format(a, b) for a, b in tab[key]]
        print(("| " + " | ".join([key[0], key[1]] + cells) + " |") if md else "\t".join([key[0], key[1]] + cells))


if __name__ == "__main__":
    main()

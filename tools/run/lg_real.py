"""(tools/run/lg_real.py; docs/design/LG_REAL_VS_SIM.md) 1.6a's lightning in real games against people (the public servers' session archive), by the numbers the simulator's checks give:
hit rate (hits / shots), shots a minute, damage a hit, and by distance; the same for the person. Shots = the lightning ammo's
decrements frame to frame; hits = the session's hit events with the lightning (weapon 6). Per the !aim level in force."""
import csv, glob, io, json, os, sys, tarfile
from collections import defaultdict
import numpy as np

ARCH = r"T:\quake-sessions\public"
LG = 6
BINS = [0, 200, 400, 600, 800, 10000]


def bin_of(d):
    for i in range(len(BINS) - 1):
        if d < BINS[i + 1]:
            return i
    return len(BINS) - 2


def one(tp, acc):
    with tarfile.open(tp) as tf:
        mem = {os.path.basename(m.name): m for m in tf.getmembers() if m.isfile()}
        if "meta.json" not in mem or "frames.csv" not in mem:
            return
        meta = json.load(tf.extractfile(mem["meta.json"]))
        if "1_6a" not in str(meta.get("policy")):
            return
        ev = [json.loads(l) for l in tf.extractfile(mem["events.jsonl"]).read().decode().splitlines() if l.strip()] if "events.jsonl" in mem else []
        rows = list(csv.reader(io.TextIOWrapper(tf.extractfile(mem["frames.csv"]), encoding="utf-8")))
    hd = rows[0]; ix = {k: i for i, k in enumerate(hd)}
    F = np.array([[float(x) if x not in ("", "-") else np.nan for x in r] for r in rows[1:] if len(r) == len(hd)])
    if len(F) < 100:
        return
    owner = any(p.get("owner") for p in meta.get("people", []))
    levels = sorted([(e["t"], str(e.get("level"))) for e in ev if e.get("event") == "aim"])
    def level_at(t):
        lv = "default"
        for t_, l_ in levels:
            if t_ <= t:
                lv = l_
        return lv
    t = F[:, ix["t"]]
    for side, o in (("b", "o"), ("o", "b")):
        am = F[:, ix[side + "_ammo_lg"]]; wp = F[:, ix[side + "_weapon"]]
        d = np.diff(am); held = (wp[1:] == LG) & (wp[:-1] == LG)
        shots = np.where(held & (d < 0) & (d >= -3), -d, 0.0)
        dist = np.linalg.norm(F[:, [ix[side + "_x"], ix[side + "_y"], ix[side + "_z"]]] - F[:, [ix[o + "_x"], ix[o + "_y"], ix[o + "_z"]]], axis=1)[1:]
        alive = F[1:, ix[side + "_health"]] > 0
        for k in range(len(shots)):
            if shots[k] > 0:
                key = (side, level_at(t[k + 1]), owner)
                acc[key]["shots"] += shots[k]; acc[key]["shots_b"][bin_of(dist[k])] += shots[k]
        # time: minutes alive with lightning held, minutes alive
        for k in np.nonzero(alive)[0]:
            pass
        for lv in set(level_at(x) for x in t[::400]) | {level_at(t[0])}:
            pass
        dt = np.diff(t); dt = np.clip(dt, 0, 0.1)
        for k in range(len(dt)):
            key = (side, level_at(t[k + 1]), owner)
            acc[key]["min"] += dt[k] / 60.0
            if wp[k + 1] == LG and alive[k]:
                acc[key]["lg_min"] += dt[k] / 60.0
    for e in ev:
        if e.get("event") == "hit" and e.get("attacker_weapon") == LG:
            side = "b" if e.get("victim") == "opp" else "o"
            key = (side, level_at(e["t"]), owner)
            acc[key]["hits"] += 1; acc[key]["dmg"] += e.get("dmg", 0); acc[key]["hits_b"][bin_of(e.get("dist", 0))] += 1
    acc[("n", "", owner)]["sessions"] += 1


def main():
    acc = defaultdict(lambda: {"shots": 0.0, "hits": 0, "dmg": 0, "min": 0.0, "lg_min": 0.0, "sessions": 0,
                               "shots_b": [0.0] * (len(BINS) - 1), "hits_b": [0] * (len(BINS) - 1)})
    tps = sorted(glob.glob(os.path.join(ARCH, "us", "2026110*_human.tar.gz")) + glob.glob(os.path.join(ARCH, "ams", "2026110*_human.tar.gz")))
    for tp in tps:
        try:
            one(tp, acc)
        except Exception as e:
            print("skip", os.path.basename(tp), e, file=sys.stderr)
    out = {}
    for (side, lv, own), a in sorted(acc.items(), key=str):
        if side == "n":
            out["sessions_owner" if own else "sessions_others"] = a["sessions"]; continue
        k = "{}|{}|{}".format("bobby" if side == "b" else "person", lv, "owner" if own else "others")
        out[k] = {"minutes": round(a["min"], 1), "lg_held_share": round(a["lg_min"] / max(1e-9, a["min"]), 3), "shots": int(a["shots"]),
                  "hits": a["hits"], "hit_rate": round(a["hits"] / max(1.0, a["shots"]), 3),
                  "shots_per_min": round(a["shots"] / max(1e-9, a["min"]), 1), "dmg_per_hit": round(a["dmg"] / max(1, a["hits"]), 2),
                  "dmg_per_min": round(a["dmg"] / max(1e-9, a["min"]), 1),
                  "hit_rate_by_dist": {"{}-{}".format(BINS[i], BINS[i + 1] if BINS[i + 1] < 10000 else "+"):
                                       (round(a["hits_b"][i] / a["shots_b"][i], 3) if a["shots_b"][i] >= 50 else None, int(a["shots_b"][i]))
                                       for i in range(len(BINS) - 1)}}
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

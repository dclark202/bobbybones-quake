"""Combine what every training BobbyBones learned into shared knowledge.

reads  /tmp/train/c*/{trace_live_<map>.txt, banned_moves.txt, experience.jsonl, results.jsonl}
writes /tmp/train/shared/{nav_<map>.json, weapon_policy.json, elo.json, report.txt} and appends elo_history.jsonl

- routes:  nav graph from all movement; moves that failed >= BAN_MIN times across the cluster are pruned
- weapons: per situation, the weapon with the best damage per second of firing in Bobby's own fights
           (needs >= MIN_SECONDS of firing); otherwise the human-learned seed policy
- rating:  Elo over all match results in time order (opponents start at 1500)
"""
import glob
import json
import os
import subprocess
import time
from collections import Counter, defaultdict

T = "/tmp/train"
SHARED = os.path.join(T, "shared")
MAP = os.environ.get("LAB_MAP", "bloodrun")
BAN_MIN = 3
MIN_SECONDS = 3.0
# seconds of firing per unit of ammo (QL refire times), to compare weapons fairly
REFIRE = {1: 0.4, 2: 0.1, 3: 1.0, 4: 0.8, 5: 0.8, 6: 0.05, 7: 1.5, 8: 0.1, 11: 1.0, 13: 0.05, 14: 0.075}
NAMES = {1: "G", 2: "MG", 3: "SG", 4: "GL", 5: "RL", 6: "LG", 7: "RG", 8: "PG", 11: "NG", 13: "CG", 14: "HMG"}
os.makedirs(SHARED, exist_ok=True)
dirs = sorted(glob.glob(os.path.join(T, "c*")))
report = ["BobbyBones training report  {}  ({} trainers)".format(time.strftime("%Y-%m-%d %H:%M"), len(dirs)), ""]

# ---------------- routes ----------------
bans = Counter()
for d in dirs:
    f = os.path.join(d, "banned_moves.txt")
    if os.path.exists(f):
        bans.update(l.strip() for l in open(f) if ">" in l)
pruned = [m for m, n in bans.items() if n >= BAN_MIN]
ban_file = os.path.join(SHARED, "banned_moves_pruned.txt")
open(ban_file, "w").write("\n".join(pruned) + ("\n" if pruned else ""))
traces = [f for f in ["/ql/maps-data/{}/walk_trace.txt".format(MAP)] if os.path.exists(f)]
traces += [f for f in (os.path.join(d, "trace_live_{}.txt".format(MAP)) for d in dirs) if os.path.exists(f)]
nav_out = os.path.join(SHARED, "nav_{}.json".format(MAP))
r = subprocess.run(["python3", "/tools/navgraph.py"] + traces + [nav_out + ".new"],
                   env=dict(os.environ, NAV_BANNED=ban_file), capture_output=True, text=True)
if r.returncode == 0:
    os.replace(nav_out + ".new", nav_out)
report.append("Routes: {} | failed moves reported {} | pruned (>= {} failures) {}".format(
    r.stdout.strip().replace("\n", " | "), sum(bans.values()), BAN_MIN, len(pruned)))

# ---------------- weapons ----------------
shots, dmg = defaultdict(Counter), defaultdict(Counter)
for d in dirs:
    f = os.path.join(d, "experience.jsonl")
    if not os.path.exists(f):
        continue
    for line in open(f):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        (shots if e["k"] == "shot" else dmg)[e["band"]][e["w"]] += e["n"]
seed_f = os.path.join(T, "seed_weapon_policy.json")
policy = json.load(open(seed_f)) if os.path.exists(seed_f) else {}
learned = 0
report.append("")
report.append("Weapons (damage per second of firing, Bobby's own fights):")
for band in sorted(shots):
    secs = {w: n * REFIRE.get(w, 0.5) for w, n in shots[band].items()}
    dps = {w: dmg[band][w] / s for w, s in secs.items() if s >= MIN_SECONDS}
    if not dps:
        continue
    best = max(dps, key=dps.get)
    if dps[best] > 0:
        policy[band] = best
        learned += 1
    report.append("  {:<20} -> {:<3} {}".format(band, NAMES.get(best, best), ", ".join(
        "{} {:.0f}dps/{:.0f}s".format(NAMES.get(w, w), v, secs[w]) for w, v in sorted(dps.items(), key=lambda kv: -kv[1]))))
json.dump(policy, open(os.path.join(SHARED, "weapon_policy.json"), "w"), indent=1)
report.append("  situations learned from self-play: {} (others: human seed)".format(learned))

# ---------------- rating ----------------
results = []
for d in dirs:
    f = os.path.join(d, "results.jsonl")
    if os.path.exists(f):
        for line in open(f):
            try:
                results.append(json.loads(line))
            except ValueError:
                pass
results.sort(key=lambda r: r["t"])
rating, opp_r, K = 1500.0, defaultdict(lambda: 1500.0), 24.0
wins = losses = draws = 0
per_opp = defaultdict(lambda: [0, 0, 0])
for r in results:
    o = r["opp"]
    s = 1.0 if r["bobby_score"] > r["opp_score"] else (0.5 if r["bobby_score"] == r["opp_score"] else 0.0)
    e = 1.0 / (1.0 + 10 ** ((opp_r[o] - rating) / 400.0))
    rating += K * (s - e)
    opp_r[o] -= K * (s - e)
    wins, draws, losses = wins + (s == 1), draws + (s == 0.5), losses + (s == 0)
    per_opp[o][0 if s == 1 else (1 if s == 0.5 else 2)] += 1
elo = dict(t=time.time(), games=len(results), rating=round(rating), wins=wins, draws=draws, losses=losses,
           opponents={o: dict(rating=round(v), wdl=per_opp[o]) for o, v in opp_r.items()})
json.dump(elo, open(os.path.join(SHARED, "elo.json"), "w"), indent=1)
with open(os.path.join(SHARED, "elo_history.jsonl"), "a") as f:
    f.write(json.dumps(dict(t=elo["t"], games=elo["games"], rating=elo["rating"])) + "\n")
report.append("")
report.append("Rating: BobbyBones {} after {} matches (W {} / D {} / L {}) vs Nightmare bots".format(
    elo["rating"], len(results), wins, draws, losses))
for o, v in sorted(elo["opponents"].items(), key=lambda kv: -kv[1]["rating"]):
    report.append("  {:<10} {:>5}  W/D/L {}".format(o, v["rating"], "/".join(map(str, v["wdl"]))))
recent = results[-20:]
if recent:
    report.append("  last {} frag diffs: {}".format(len(recent), " ".join("{:+d}".format(r["bobby_score"] - r["opp_score"]) for r in recent)))

# ---------------- movement: best route/movement style per trip ----------------
legs = []
for d in dirs:
    f = os.path.join(d, "legs.jsonl")
    if os.path.exists(f):
        for line in open(f):
            try:
                legs.append(json.loads(line))
            except ValueError:
                pass
by_style = defaultdict(lambda: defaultdict(list))
for l in legs:
    if l["fight"] > 1.0 or l["picked"] != l["key"].split(">")[1]:
        continue                                   # fights and detours don't measure the route
    st = l["style"]
    sig = json.dumps(st, sort_keys=True)
    by_style[l["key"]][sig].append(l)
move_policy = {}
report.append("")
report.append("Movement (median travel time per trip; best style needs >= 3 clean runs, >= 80% without getting stuck):")
for key in sorted(by_style):
    best = None
    for sig, runs in by_style[key].items():
        ok = [r for r in runs if r["stucks"] == 0]
        if len(runs) < 3 or len(ok) / len(runs) < 0.8:
            continue
        med = sorted(r["travel"] for r in ok)[len(ok) // 2]
        if best is None or med < best[0]:
            best = (med, sig, len(runs))
    all_runs = [r for runs in by_style[key].values() for r in runs]
    overall = sorted(r["travel"] for r in all_runs)[len(all_runs) // 2]
    if best:
        move_policy[key] = json.loads(best[1])
        report.append("  {:<8} best {:.1f}s (n={}) vs all styles {:.1f}s  style {}".format(key, best[0], best[2], overall, best[1]))
json.dump(move_policy, open(os.path.join(SHARED, "movement_policy.json"), "w"), indent=1)

# ---------------- did it move the needle? first vs last third of the run ----------------
def window_stats(rs, ls, xs):
    out = {}
    if rs:
        w = sum(1 for r in rs if r["bobby_score"] > r["opp_score"])
        out["win rate"] = "{:.0f}% ({} matches)".format(100.0 * w / len(rs), len(rs))
        out["avg frag diff"] = "{:+.1f}".format(sum(r["bobby_score"] - r["opp_score"] for r in rs) / len(rs))
    clean = [l for l in ls if l["fight"] <= 1.0]
    if clean:
        out["trips stuck"] = "{:.0f}% of {} trips".format(100.0 * sum(1 for l in clean if l["stucks"]) / len(clean), len(clean))
        out["median trip time"] = "{:.1f}s".format(sorted(l["travel"] for l in clean)[len(clean) // 2])
    shots = sum(e["n"] * REFIRE.get(e["w"], 0.5) for e in xs if e["k"] == "shot")
    dmg = sum(e["n"] for e in xs if e["k"] == "dmg")
    if shots:
        out["damage per second of firing"] = "{:.0f}".format(dmg / shots)
    return out


exp = []
for d in dirs:
    f = os.path.join(d, "experience.jsonl")
    if os.path.exists(f):
        for line in open(f):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if "t" in e:
                exp.append(e)
stamps = [r["t"] for r in results] + [l["t"] for l in legs] + [e["t"] for e in exp]
if stamps:
    t0, t1 = min(stamps), max(stamps)
    a, b = t0 + (t1 - t0) / 3.0, t0 + 2 * (t1 - t0) / 3.0
    first = window_stats([r for r in results if r["t"] < a], [l for l in legs if l["t"] < a], [e for e in exp if e["t"] < a])
    last = window_stats([r for r in results if r["t"] >= b], [l for l in legs if l["t"] >= b], [e for e in exp if e["t"] >= b])
    report.append("")
    report.append("First third vs last third of training ({:.1f} h total):".format((t1 - t0) / 3600.0))
    for k in sorted(set(first) | set(last)):
        report.append("  {:<28} {:>22}  ->  {}".format(k, first.get(k, "-"), last.get(k, "-")))

open(os.path.join(SHARED, "report.txt"), "w").write("\n".join(report) + "\n")
print("\n".join(report))

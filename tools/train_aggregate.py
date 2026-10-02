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
open(os.path.join(SHARED, "report.txt"), "w").write("\n".join(report) + "\n")
print("\n".join(report))

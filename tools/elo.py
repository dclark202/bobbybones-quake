"""elo.py [folder]: a server's leaderboard read on the PC (plugins/ladder.py writes ratings.json and frags.jsonl into the
server's data folder; tools/pull_sessions.sh copies both to the session archive every day).

    python tools/elo.py                      T:/quake-sessions/public, or data/public where that is not there
    python tools/elo.py data/labtest         another folder with the two files
    python tools/elo.py --net duel_gru_v14   one network of Bobby only

Prints the board as the server has it, and from the frag log, per network of Bobby and per person: the frags made and
taken against him, the person's share with its 95% range, and what the share is in rating points (the person's edge
over Bobby: 400 * log10(share / (1 - share))). Then Bobby's share by map and by warmup or game, and the table worked
out again from the frag log, to set beside the file (they must agree).

Names are in ratings.json only (the last name a player was seen with); the frag log has anonymous keys. Neither file
belongs in the repo.
"""
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
import ratings as R  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
only = sys.argv[sys.argv.index("--net") + 1] if "--net" in sys.argv else None
if only in args:
    args.remove(only)
folder = args[0] if args else next((p for p in ("T:/quake-sessions/public", os.path.join(ROOT, "data", "public"))
                                    if os.path.exists(os.path.join(p, "frags.jsonl"))), os.path.join(ROOT, "data", "public"))
fp, rp = os.path.join(folder, "frags.jsonl"), os.path.join(folder, "ratings.json")
if not os.path.exists(fp):
    sys.exit("no frags.jsonl in {}".format(folder))
frags = [json.loads(x) for x in open(fp) if x.strip()]
table = R.Table(rp)
name = lambda k: table.players.get(k, {}).get("name", k)


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    c, h = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def points(share):
    return 400.0 * math.log10(share / (1.0 - share)) if 0.0 < share < 1.0 else float("inf") * (1 if share >= 1.0 else -1)


print("{}: {} counted frags, {} rows in the table".format(folder, len(frags), len(table.players)))
nets = list(dict.fromkeys(f["net"] for f in frags))
bobby = R.BOT + nets[-1] if nets else None
print("\nThe board (Bobby's current network: {}):".format(R.label(nets[-1]) if nets else "-"))
for n, (k, p) in enumerate(table.board(bobby), 1):
    print("  {:2d}. {:24s} {:5.0f} (+-{:3.0f})  frags made {:4d}, taken {:4d}".format(n, p["name"], p["r"], 2 * p["rd"], p["won"], p["lost"]))
low = [(k, p) for k, p in table.players.items() if not k.startswith(R.BOT) and p["won"] + p["lost"] < R.MIN_FRAGS]
if low:
    print("  not ranked yet (under {} frags): {}".format(R.MIN_FRAGS, ", ".join("{} ({})".format(p["name"], p["won"] + p["lost"]) for k, p in low)))

for net in nets:
    if only and net != only:
        continue
    B = R.BOT + net
    F = [f for f in frags if f["net"] == net]
    made, taken = collections.Counter(), collections.Counter()
    for f in F:
        if f["victim"] == B:
            made[f["killer"]] += 1
        else:
            taken[f["victim"]] += 1
    tm, tt = sum(made.values()), sum(taken.values())
    lo, hi = wilson(tt, tm + tt)
    print("\nBobby {}: {} frags with {} people: he made {}, they made {}; his share {:.0%} ({:.0%} to {:.0%})".format(
        R.label(net), len(F), len(set(made) | set(taken)), tt, tm, tt / max(1, tm + tt), lo, hi))
    print("  {:24s} {:>5s} {:>5s} {:>6s} {:>13s} {:>22s}".format("person", "made", "taken", "share", "95% range", "edge over Bobby, points"))
    for k in sorted(set(made) | set(taken), key=lambda k: -(made[k] / max(1, made[k] + taken[k]))):
        n = made[k] + taken[k]
        lo, hi = wilson(made[k], n)
        edge = "{:+.0f} ({:+.0f} to {:+.0f})".format(points(made[k] / n), points(lo), points(hi)) if 0 < made[k] < n else "all one way"
        print("  {:24s} {:5d} {:5d} {:6.0%} {:>6.0%} to {:<4.0%} {:>22s}".format(name(k)[:24], made[k], taken[k], made[k] / n, lo, hi, edge))
    for title, key in (("by map", "map"), ("warmup or game", "state")):
        c = collections.defaultdict(lambda: [0, 0])
        for f in F:
            c[f.get(key)][0 if f["killer"] == B else 1] += 1
        print("  his share {}: {}".format(title, ", ".join("{} {:.0%} of {}".format(k, v[0] / (v[0] + v[1]), v[0] + v[1]) for k, v in sorted(c.items(), key=lambda q: -sum(q[1])))))

again = R.Table()
for f in frags:
    again.frag(f["killer"], name(f["killer"]), f["victim"], name(f["victim"]), f["t"])
worst = max((abs(again.players[k]["r"] - p["r"]) for k, p in table.players.items() if k in again.players), default=0.0)
missing = [k for k in table.players if k not in again.players] + [k for k in again.players if k not in table.players]
print("\nworked out again from the frag log: largest difference to the file {:.1f} points{}".format(
    worst, "; rows only on one side: {}".format(len(missing)) if missing else ""))

"""How a play test went, per game of a local server's data folder (2026-10-31, from the reads of v0.6.1d and b1.0a): stacks, weapons, items, lives, fights by who is ahead, tunnel vision (the person in sight, under 800 units: aim off by over 30 degrees, firing, closing).
    python tools/run/play_read.py data/duellive_b10a [--min-minutes 2]"""
import argparse
import collections
import csv
import glob
import json
import os

import numpy as np

WN = {1: "gaunt", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}
COLS = ["t", "b_x", "b_y", "b_z", "b_vx", "b_vy", "b_health", "b_armor", "b_weapon", "b_fire", "o_x", "o_y", "o_z", "o_vx", "o_vy", "o_health", "o_armor", "o_weapon", "o_fire", "b_sees", "los", "b_aim_err", "o_aim_err"]
ITEMS = ("item_health_mega", "item_armor_body", "item_armor_combat", "weapon_rocketlauncher", "weapon_lightning", "weapon_railgun", "weapon_plasmagun")


def game(d, S):
    t0, t1 = d["t0"], d["t"]
    R = list(csv.DictReader(open(os.path.join(S, "frames.csv"))))
    A = {c: np.array([float(r[c] or 0) for r in R]) for c in COLS}
    m = (A["t"] >= t0) & (A["t"] <= t1)
    A = {c: v[m] for c, v in A.items()}
    n = len(A["t"])
    if not n:
        return print(d["map"], "no frames")
    print("\n=====", d["map"], "score (person, him)", d["score"], "aim", d.get("aim"), "minutes {:.1f}{}".format(n * .025 / 60, " forfeit" if d.get("forfeit") else ""))
    al, oal = A["b_health"] > 0, A["o_health"] > 0
    stk = lambda p: A[p + "_health"] + np.minimum(A[p + "_armor"], 2 * A[p + "_health"])  # noqa: E731
    b, o = stk("b"), stk("o")
    print("stack alive: him {:.0f}, person {:.0f}; at 200+: him {:.0%}, person {:.0%}".format(b[al].mean(), o[oal].mean(), (b[al] >= 200).mean(), (o[oal] >= 200).mean()))
    for p, a in (("him", al), ("person", oal)):
        c = collections.Counter(A[("b" if p == "him" else "o") + "_weapon"][a].astype(int).tolist())
        print("  {} in hand {}".format(p, {WN.get(k, k): round(v / a.sum(), 2) for k, v in c.most_common(5)}))
    both = al & oal
    los = both & (A["los"] > 0)
    dist = np.sqrt((A["b_x"] - A["o_x"]) ** 2 + (A["b_y"] - A["o_y"]) ** 2 + (A["b_z"] - A["o_z"]) ** 2)
    close = los & (dist < 800)
    if close.any():
        cl = ((A["o_x"] - A["b_x"]) * A["b_vx"] + (A["o_y"] - A["b_y"]) * A["b_vy"])[close] / np.maximum(dist[close], 1)
        print("tunnel vision, the person in sight under 800 u ({:.0%} of both alive): him off by 30+ {:.0%}, firing {:.0%}, closing {:.0f} u/s; person off by 30+ {:.0%}, firing {:.0%}".format(
            close.sum() / both.sum(), (A["b_aim_err"][close] > 30).mean(), (A["b_fire"][close] > 0).mean(), cl.mean(), (A["o_aim_err"][close] > 30).mean(), (A["o_fire"][close] > 0).mean()))
    ed0 = np.diff(np.r_[0, los.astype(int), 0])              # (b1.3) chip damage: an exchange (a stretch in sight of 0.5 s or more) in which he or the person lost stack and neither died
    ch = collections.Counter()
    for a_, z_ in zip(np.where(ed0 == 1)[0], np.where(ed0 == -1)[0]):
        if z_ - a_ >= 20:
            z2 = min(z_ + 8, n - 1)
            if A["b_health"][z2] > 0 and A["o_health"][z2] > 0:
                db_, do_ = max(0.0, b[a_] - b[z2]), max(0.0, o[a_] - o[z2])
                if db_ > 0 or do_ > 0:
                    ch["n"] += 1
                    ch["him"] += do_
                    ch["person"] += db_
    mins_ = max(1e-6, both.sum() * .025 / 60)
    print("chip damage, exchanges with no death: {:.1f} a minute; stack taken a minute: by him {:.0f}, by the person {:.0f}".format(ch["n"] / mins_, ch["him"] / mins_, ch["person"] / mins_))
    E = [json.loads(x) for x in open(os.path.join(S, "events.jsonl"))]
    pk, seen = collections.Counter(), set()
    for e in E:
        if e["event"] == "pickup" and t0 <= e.get("t", 0) <= t1 and (e["item"], e["by"], round(e["t"], 1)) not in seen:
            seen.add((e["item"], e["by"], round(e["t"], 1)))
            pk[("him" if e["by"] == "bobby" else ("?" if e["by"] == "?" else "person"), e["item"])] += 1
    print("items (him/person):", {i.split("_", 1)[1]: "{}/{}".format(pk[("him", i)], pk[("person", i)]) for i in ITEMS})
    dead, st = np.where(al[:-1] & ~al[1:])[0], np.where(~al[:-1] & al[1:])[0]
    lv = [A["t"][x] - A["t"][(st[st < x][-1] + 1) if (st < x).any() else 0] for x in dead]
    if lv:
        print("lives {}: median {:.0f} s, under 20 s {:.0%}".format(len(lv), np.median(lv), (np.array(lv) < 20).mean()))
    ed = np.diff(np.r_[0, los.astype(int), 0])
    F = []
    for a_, z_ in zip(np.where(ed == 1)[0], np.where(ed == -1)[0]):
        if z_ - a_ >= 20:
            z2 = min(z_ + 8, n - 1)
            F.append((b[a_], o[a_], A["b_health"][z2] <= 0, A["o_health"][z2] <= 0))
    F = np.array(F) if F else np.zeros((0, 4))
    if len(F):
        print("fights {}: he starts ahead {:.0%}; stack at the start him {:.0f}, person {:.0f}".format(len(F), (F[:, 0] > F[:, 1]).mean(), F[:, 0].mean(), F[:, 1].mean()))
        for name, q in (("ahead by 25+", F[:, 0] > F[:, 1] + 25), ("level", np.abs(F[:, 0] - F[:, 1]) <= 25), ("behind by 25+", F[:, 0] < F[:, 1] - 25)):
            print("   {:14s} {:3d}: he kills {:3.0f}, dies {:3.0f}".format(name, q.sum(), F[q, 3].sum(), F[q, 2].sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--min-minutes", type=float, default=2)
    a = ap.parse_args()
    meta = [(s, json.load(open(os.path.join(s, "meta.json")))) for s in sorted(glob.glob(os.path.join(a.data, "sessions", "*")))]
    for d in map(json.loads, open(os.path.join(a.data, "duels.jsonl"))):
        if d.get("minutes", 0) < a.min_minutes:
            continue
        c = [s for s, m in meta if m.get("map") == d["map"] and m.get("started", 1e18) <= d["t0"] + 5]
        game(d, c[-1]) if c else print(d["map"], "no session")


if __name__ == "__main__":
    main()

"""What a shot costs, per map and gun, under SHOT_COST (sim/duel_env.py): how well the map feeds the gun, how far its
ammo is from the map's places, and the chance to hit from which a shot pays (belt full, half a pickup left, last shots).

    python tools/shot_prices.py [--map bloodrun,aerowalk,lostworld,arena1] [--cost 0.10] [--json docs/shot_prices.json]
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld,arena1")
    ap.add_argument("--cost", type=float, default=0.10)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    os.environ["SHOT_COST"] = str(a.cost)
    import duel_env as E
    out = {}
    for mp in a.map.split(","):
        env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=0,
                        nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
        guns = sorted({int(d[1]) for d in env.item_def if d[0] == "wp"} | {E.MG})
        print("\n{} (a shot pays from this chance to hit on; share {:.2f})".format(mp, a.cost))
        print("| Gun | Fire the map feeds, s/min | Map | Way to its ammo, s (median) | Place | Belt full | Half a pickup | Last shots |")
        print("|---|---|---|---|---|---|---|---|")
        out[mp] = {}
        for w in guns:
            way = env.shot_way[w] if env.shot_way is not None else np.array([1e9], np.float32)
            ok = way < 1e8
            med = float(np.median(way[ok])) if ok.any() else float("inf")
            near = float(np.clip(med / E.SHOT_NEAR_S, 0.5, 1.5))
            pay = [a.cost * float(np.clip(env.shot_scarce[w] * near * b, 0.25, 3.0)) for b in (0.5, 1.0, 1.5)]
            out[mp][E.WEAPONS[w]] = dict(fire_s_per_min=round(float(env.shot_fire[w]), 1), map=round(float(env.shot_scarce[w]), 2),
                                         way_s=round(med, 1) if ok.any() else None, place=round(near, 2), pays_from=[round(x, 3) for x in pay])
            print("| {} | {:.1f} | x{:.2f} | {} | x{:.2f} | {:.1%} | {:.1%} | {:.1%} |".format(
                E.WEAPONS[w].upper(), env.shot_fire[w], env.shot_scarce[w], "{:.1f}".format(med) if ok.any() else "none", near, *pay))
    if a.json:
        json.dump(out, open(os.path.join(ROOT, a.json), "w"), indent=1)


if __name__ == "__main__":
    main()

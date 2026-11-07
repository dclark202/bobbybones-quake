"""The weapon-push arms side by side (wpush.py's folders): record, win rate, frag share, kills a player per 10-minute game, his time with
the enemy in view, the weapon in hand in view (by distance) and out of view, frags by weapon, hit rates; the pushed side ("he")
beside the plain one ("opponent", the same save unpushed).

    python docs/runs/1.7/1.7c/exp/wsum.py data/sim_runs/duel_gru_1_7a/wpush/p2 data/sim_runs/duel_gru_1_7a/wpush/p4
"""
import glob
import json
import os
import sys
from collections import defaultdict


def arm(d):
    fs = sorted(glob.glob(os.path.join(d, "chk_*.json")))
    W = L = D = 0
    acc = defaultdict(lambda: defaultdict(float))
    n = 0
    maps = {}
    for f in fs:
        try:
            J = json.load(open(f))
        except Exception:                                    # noqa: BLE001
            continue
        for mp, M in J["maps"].items():
            W, L, D = W + M["won"], L + M["lost"], D + M["drawn"]
            maps[mp] = "{}-{}".format(M["won"], M["lost"])
            n += 1
            acc["share"][""] += M["frag_share"]
            for sd in ("he", "opponent"):
                S = M[sd]
                acc[sd]["kills"] += S["kills"] * 10.0 / M["minutes"]
                acc[sd]["view"] += S["in_view"]
                for w, v in S["by_style"]["general"]["in_hand_in_view"].items():
                    acc[sd]["in_" + w] += v
                for w, v in S.get("in_hand_out_of_view", {}).items():
                    acc[sd]["out_" + w] += v
            H = M["he"]
            for w, v in H.get("frags_by", {}).items():
                acc["he"]["frag_" + w] += v
            for w, v in H.get("hit_rate", {}).items():
                acc["he"]["hit_" + w] += v
            for b, row in H.get("in_hand_by_distance", {}).items():
                for w, v in row.items():
                    acc["he"]["{}_{}".format(b, w)] += v
    return dict(W=W, L=L, D=D, n=n, maps=maps, acc={k: {kk: vv / max(1, n) for kk, vv in v.items()} for k, v in acc.items()})


for d in sys.argv[1:]:
    r = arm(d)
    a = r["acc"]
    if not r["n"]:
        print(d, "nothing yet")
        continue
    h, o = a["he"], a["opponent"]
    print("== {} ({} maps): {}-{}-{} (W-L-D), win rate {:.1%}, frag share {:.1%}".format(os.path.basename(d), r["n"], r["W"], r["L"], r["D"],
                                                                                       r["W"] / max(1, r["W"] + r["L"]), a["share"][""]))
    print("   maps", r["maps"])
    for nm, s in (("pushed", h), ("plain", o)):
        print("   {:7s} kills/10 min {:5.2f} | in view {:.3f} | in hand in view rl/rg/lg {:.2f}/{:.2f}/{:.2f} | out of view rl/rg/lg {:.2f}/{:.2f}/{:.2f}".format(
            nm, s["kills"], s["view"], s.get("in_rl", 0), s.get("in_rg", 0), s.get("in_lg", 0), s.get("out_rl", 0), s.get("out_rg", 0), s.get("out_lg", 0)))
    print("   pushed: frags rl/rg/lg {:.2f}/{:.2f}/{:.2f} | hits rl/rg/lg {:.2f}/{:.2f}/{:.2f} | lg in hand close/mid/far {:.2f}/{:.2f}/{:.2f} | "
          "rl {:.2f}/{:.2f}/{:.2f} | rg {:.2f}/{:.2f}/{:.2f}".format(
              h.get("frag_rl", 0), h.get("frag_rg", 0), h.get("frag_lg", 0), h.get("hit_rl", 0), h.get("hit_rg", 0), h.get("hit_lg", 0),
              h.get("close_lg", 0), h.get("mid_lg", 0), h.get("far_lg", 0), h.get("close_rl", 0), h.get("mid_rl", 0), h.get("far_rl", 0),
              h.get("close_rg", 0), h.get("mid_rg", 0), h.get("far_rg", 0)))

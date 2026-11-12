"""2.1's three goals as readouts of recorded games (docs/runs/2.1/INSTRUCTION.md; owner, 2026-11-11: respect space, use the weapons
that need a plan, fire where the enemy will be / hold an angle / spam). READOUTS, never targets (CLAUDE.md rule 12): the same tables
for any network's records, so 2.1 has 1.8's numbers to stand beside. Measurement only; system Python (scipy); reads records, plays
nothing.

    python tools/run/goal_readout.py <recdir> [<recdir> ...] [--side 0] [--maps a,b] [--out <jsonl>]

<recdir>: tools/run/cypher_measure.py sim's records (rec_<map>_<k>.npz: pos, alive, weapon, vis, hp, ar, dealt, side; `fire` where the
recorder has it). --side: 0 = the network under test (in self-play both sides are it: --side -1 takes every seat).

  space    with the enemy near (1,500 units): the damage a second the enemy's weapon puts on his place from the ground the enemy can
           be on within 1.5 s (tools/run/space_score.py's threat: the map's sight lines by length x the weapon table); the share of
           that time by band, and "heavy" = 10 a second or more; the same for the edge (his on the enemy less the enemy's on him)
  weapons  with the enemy in view: the weapon in his hand by the distance (under 400 / 400 to 768 / over 768)
  unseen   his trigger time with the enemy NOT in view, by weapon (needs `fire`)
  waits    near, the enemy not in view, moved under 60 units in the last second: the share of the near time, the weapon in hand then,
           and what the next 5 s brought (dealt less taken)
  asked    (2.1, the owner's question: do the damage-trained hands overrule the head's weapon?) of the frames he fired in while his
           instruction asked for a weapon: the share fired with ANOTHER weapon, by the weapon asked for (needs `fire`, `wfire`, `askw`)
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

NEAR = 1500.0
STEP, BACK = 10, 40                                           # a sample every 0.25 s; "the last second"
WIN = 5.0                                                     # seconds ahead for "what it brought"
DBAND = (400.0, 768.0)
DNAMES = ("under 400", "400 to 768", "over 768")
TE = (2.0, 5.0, 10.0, 20.0)                                   # the threat on him, damage a second
TNAMES = ("under 2", "2 to 5", "5 to 10", "10 to 20", "over 20")
HEAVY = 10.0
EE = (-10.0, -3.0, 3.0, 10.0)
ENAMES = ("under -10", "-10 to -3", "-3 to 3", "3 to 10", "over 10")
WN = ("rockets", "rail", "lightning", "machine gun", "shotgun", "grenades", "plasma", "hmg", "gauntlet")   # duel_env's numbers
W3 = (0, 1, 2)


def seats(d, side):
    n = d["alive"].shape[1]
    sd = d["side"] if "side" in d.files else np.zeros(n, np.int8)
    return [s for s in range(n) if side < 0 or int(sd[s]) == side]


def rows(d, s):
    """one seat's samples with the enemy near: dict of arrays"""
    pos, alive, wp, vis = d["pos"].astype(np.float32), d["alive"], d["weapon"].astype(int), d["vis"]
    stack, dealt = d["hp"].astype(np.float32) + d["ar"].astype(np.float32), d["dealt"].astype(np.float64)
    T = alive.shape[0]
    o = s ^ 1
    idx = np.arange(BACK, T - 1, STEP)
    ii = idx[alive[idx, s] & alive[idx - BACK, s] & alive[idx, o]]
    ii = ii[np.linalg.norm(pos[ii, s] - pos[ii, o], axis=1) < NEAR]
    d1 = np.zeros(T)
    d1[1:] = np.where(alive[:-1, s], np.maximum(0.0, stack[:-1, s] - np.maximum(stack[1:, s], 0.0)), 0.0)
    d1[d1 < 2.0] = 0.0                                        # (the decay above 100 is not damage)
    ct, cd = np.concatenate([[0.0], np.cumsum(d1)]), np.concatenate([[0.0], np.cumsum(dealt[:, s])])
    F = int(round(WIN / float(d["dt"]) if "dt" in d.files else WIN / 0.025))
    e = np.minimum(ii + F, T - 1)
    r = dict(pos=pos[ii, s], en=pos[ii, o], w=wp[ii, s].clip(0, 8), we=wp[ii, o].clip(0, 8), seen=vis[ii, s].astype(bool),
             moved=np.linalg.norm(pos[ii, s] - pos[ii - BACK, s], axis=1), taken=ct[e + 1] - ct[ii + 1], dealt=cd[e + 1] - cd[ii + 1])
    if "fire" in d.files:                                    # every frame, not the samples: [frames of his trigger, weapon, seen]
        f = d["fire"][:, s].astype(bool) & alive[:, s]
        r["fire_w"], r["fire_seen"] = wp[f, s].clip(0, 8), vis[f, s].astype(bool)
        if "askw" in d.files and "wfire" in d.files:         # (2.1) the shots fired under an instruction that asked for a weapon
            aw, wf = d["askw"][:, s].astype(int), d["wfire"][:, s].astype(int)
            g = f & (aw >= 0)
            r["ask_w"], r["ask_other"] = aw[g].clip(0, 8), wf[g] != aw[g]
    return r


def new_acc():
    return dict(n=0, games=0, tn=np.zeros(5), en=np.zeros(5), hand=np.zeros((3, 9)), wait_n=np.zeros(9), wait_d=np.zeros(9),
                wait_t=np.zeros(9), fire=np.zeros(9), fire_unseen=np.zeros(9), space_n=0, has_fire=False,
                ask=np.zeros(9), ask_other=np.zeros(9), has_ask=False)


def add(A, r, S=None, W=None):
    n = len(r["w"])
    if not n:
        return
    A["n"] += n
    if S is not None:
        i, j = S.at(r["pos"]), S.at(r["en"])
        t_en = sum(W[r["we"]][:, q] * S.seeb[q][j, i] / 255.0 for q in range(3))      # on him
        t_me = sum(W[r["w"]][:, q] * S.seeb[q][i, j] / 255.0 for q in range(3))       # on the enemy
        A["tn"] += np.bincount(np.digitize(t_en, TE), minlength=5)
        A["en"] += np.bincount(np.digitize(t_me - t_en, EE), minlength=5)
        A["space_n"] += n
    db = np.digitize(np.linalg.norm(r["pos"] - r["en"], axis=1), DBAND)
    np.add.at(A["hand"], (db[r["seen"]], r["w"][r["seen"]]), 1)
    wt = ~r["seen"] & (r["moved"] < 60.0)
    np.add.at(A["wait_n"], r["w"][wt], 1)
    np.add.at(A["wait_d"], r["w"][wt], r["dealt"][wt])
    np.add.at(A["wait_t"], r["w"][wt], r["taken"][wt])
    if "fire_w" in r:
        A["has_fire"] = True
        np.add.at(A["fire"], r["fire_w"], 1)
        np.add.at(A["fire_unseen"], r["fire_w"][~r["fire_seen"]], 1)
    if "ask_w" in r:
        A["has_ask"] = True
        np.add.at(A["ask"], r["ask_w"], 1)
        np.add.at(A["ask_other"], r["ask_w"][r["ask_other"]], 1)


def summary(A):
    out = dict(samples_near=int(A["n"]), games=int(A["games"]))
    if A["space_n"]:
        out["threat_share"] = dict(zip(TNAMES, np.round(A["tn"] / A["space_n"], 4).tolist()))
        out["threat_heavy"] = round(float(A["tn"][np.digitize(HEAVY, TE):].sum() / A["space_n"]), 4)
        out["edge_share"] = dict(zip(ENAMES, np.round(A["en"] / A["space_n"], 4).tolist()))
    out["hand_in_view"] = {DNAMES[q]: {WN[w]: round(float(A["hand"][q, w] / max(A["hand"][q].sum(), 1)), 4) for w in W3} for q in range(3)}
    wn = A["wait_n"]
    out["waits"] = dict(share_of_near=round(float(wn.sum() / max(A["n"], 1)), 4),
                        hand={WN[w]: round(float(wn[w] / max(wn.sum(), 1)), 4) for w in W3},
                        net_5s={WN[w]: round(float((A["wait_d"][w] - A["wait_t"][w]) / max(wn[w], 1)), 2) for w in W3})
    if A["has_fire"]:
        out["fire_unseen"] = {WN[w]: round(float(A["fire_unseen"][w] / max(A["fire"][w], 1)), 4) for w in (0, 1, 5, 6)}
    else:
        out["fire_unseen"] = None                             # the records have no trigger
    if A["has_ask"]:                                          # (2.1) fired with another weapon than the one asked for
        out["asked_other"] = dict(shots=int(A["ask"].sum()), share=round(float(A["ask_other"].sum() / max(A["ask"].sum(), 1)), 4),
                                  by_asked={WN[w]: round(float(A["ask_other"][w] / A["ask"][w]), 4) for w in range(9) if A["ask"][w] > 0})
    else:
        out["asked_other"] = None                             # no instruction's weapon in these records
    return out


def show(nm, s):
    print("\n{}: {} games, {} samples with the enemy near".format(nm, s["games"], s["samples_near"]))
    if "threat_share" in s:
        print("  space    the threat on him, damage a second: " + ", ".join("{} {:.1%}".format(k, v) for k, v in s["threat_share"].items()))
        print("           heavy (10 or more): {:.1%} of his time near the enemy".format(s["threat_heavy"]))
        print("           the edge: " + ", ".join("{} {:.1%}".format(k, v) for k, v in s["edge_share"].items()))
    for q in DNAMES:
        print("  weapons  in view, {:<10}: ".format(q) + ", ".join("{} {:.0%}".format(k, v) for k, v in s["hand_in_view"][q].items()))
    w = s["waits"]
    print("  waits    {:.1%} of the near time; in hand: {}; the next 5 s, dealt less taken: {}".format(
        w["share_of_near"], ", ".join("{} {:.0%}".format(k, v) for k, v in w["hand"].items()),
        ", ".join("{} {:+.1f}".format(k, v) for k, v in w["net_5s"].items())))
    if s["fire_unseen"] is None:
        print("  unseen   not in these records (no trigger recorded)")
    else:
        print("  unseen   his trigger time with the enemy not in view: " + ", ".join("{} {:.0%}".format(k, v) for k, v in s["fire_unseen"].items()))
    if s.get("asked_other") is None:
        print("  asked    not in these records (no instruction asked for a weapon)")
    else:
        q = s["asked_other"]
        print("  asked    {} shots under an instruction's weapon; fired with another: {:.1%}; by the weapon asked for: {}".format(
            q["shots"], q["share"], ", ".join("{} {:.0%}".format(k, v) for k, v in q["by_asked"].items())))


def read(recdir, side, maps=None):
    import space_score as SS
    wt = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "space", "weapon_threat.json")
    W = np.array(json.load(open(wt))["dmg_s"]) if os.path.exists(wt) else None
    A = new_acc()
    for f in sorted(glob.glob(os.path.join(recdir, "rec_*.npz"))):
        mp = os.path.basename(f).split("_")[1]
        if maps and mp not in maps:
            continue
        S = SS.Score(mp) if W is not None and os.path.exists(SS.path(mp)) else None
        if S is not None and S.seeb is None:
            S = None
        d = np.load(f, allow_pickle=True)
        ss = seats(d, side)
        for s in ss:
            add(A, rows(d, s), S, W)
        A["games"] += max(1, len(ss) // (2 if side < 0 else 1))
    return summary(A)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("rec", nargs="+")
    ap.add_argument("--side", type=int, default=0)
    ap.add_argument("--maps", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    for rd in a.rec:
        s = read(rd, a.side, set(a.maps.split(",")) if a.maps else None)
        show(rd, s)
        if a.out:
            with open(a.out, "a", encoding="utf-8") as fo:
                fo.write(json.dumps(dict(rec=rd, side=a.side, **s)) + "\n")

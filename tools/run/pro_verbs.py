"""2.0c, test 5, first part (docs/runs/2.1/DESIGN.md): what the pros do that he has no instruction for, read from the demos by rule,
beside his own games. Measurement only; system Python.

    python tools/run/pro_verbs.py [--maps ...]

Rules (mine; to be read with the owner on samples before anything is trained on them):
  near       the enemy within 1,500 units (the pros: and sent by the server)
  hold       near, the enemy NOT in view, and he has moved under 60 units in the last second (he waits)
  move       near, the enemy not in view, moving
  fight      near, the enemy in view
  spam       (the pros only: his recorded games have no trigger) the trigger down with the enemy not in view
For each: its share of the near time, by the weapon in hand; and what the next 5 s brought (deals, takes: seed_calib2's measures).
The contest of an item needs the items' clocks, which the lite sets do not hold: not here.
"""
import argparse
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import seed_calib2 as C2  # noqa: E402

SS, ROOT, NOM, WIN = C2.SS, C2.ROOT, C2.NOM, C2.WIN
W3 = ((0, "rockets"), (1, "rail"), (2, "lightning"))


def pro_rows(files, step=10, back=40):
    F = int(round(WIN / 0.025))
    for f in files:
        d = np.load(f)
        L, first = d["lite"], d["first"]
        if len(L) < 400 or L.shape[1] < 33:
            continue
        seg = np.cumsum(first)
        pos, en, stack = L[:, 5:8], L[:, 8:11], L[:, 0] + L[:, 1]
        w = L[:, 2].astype(int).clip(0, 8)
        d1 = np.zeros(len(L))
        d1[1:] = np.where(seg[1:] == seg[:-1], np.maximum(0.0, stack[:-1] - stack[1:]), 0.0)
        d1[d1 < 2.0] = 0.0
        dh = np.diff(L[:, 32], prepend=L[0, 32])
        dh[first] = 0
        dh[(dh < 0) | (dh > 4)] = 0
        ct, cd = np.concatenate([[0.0], np.cumsum(d1)]), np.concatenate([[0.0], np.cumsum(dh * NOM[w])])
        idx = np.arange(back, len(L) - 1, step)
        idx = idx[(seg[idx] == seg[idx - back]) & (L[idx, 31] > 0)]
        idx = idx[np.linalg.norm(pos[idx] - en[idx], axis=1) < SS.NEAR]
        if not len(idx):
            continue
        e = np.minimum(idx + F, np.searchsorted(seg, seg[idx], side="right") - 1)
        yield dict(w=w[idx], seen=L[idx, 4] > 0, moved=np.linalg.norm(pos[idx] - pos[idx - back], axis=1), fire=L[idx, 3] > 0,
                   taken=ct[e + 1] - ct[idx + 1], dealt=cd[e + 1] - cd[idx + 1])


def bobby_rows(rec, mp, step=10, back=40):
    F = int(round(WIN / 0.025))
    for f in sorted(glob.glob(os.path.join(rec, "rec_{}_*.npz".format(mp)))):
        d = np.load(f, allow_pickle=True)
        pos, alive, wp, vis = d["pos"].astype(np.float32), d["alive"], d["weapon"].astype(int), d["vis"]
        stack, dealt = d["hp"].astype(np.float32) + d["ar"].astype(np.float32), d["dealt"].astype(np.float64)
        T, n = alive.shape
        idx = np.arange(back, T - 1, step)
        for s in range(n):
            o = s ^ 1
            ii = idx[alive[idx, s] & alive[idx - back, s] & alive[idx, o]]
            ii = ii[np.linalg.norm(pos[ii, s] - pos[ii, o], axis=1) < SS.NEAR]
            d1 = np.zeros(T)
            d1[1:] = np.where(alive[:-1, s], np.maximum(0.0, stack[:-1, s] - np.maximum(stack[1:, s], 0.0)), 0.0)
            d1[d1 < 2.0] = 0.0
            ct, cd = np.concatenate([[0.0], np.cumsum(d1)]), np.concatenate([[0.0], np.cumsum(dealt[:, s])])
            e = np.minimum(ii + F, T - 1)
            yield dict(w=wp[ii, s].clip(0, 8), seen=vis[ii, s], moved=np.linalg.norm(pos[ii, s] - pos[ii - back, s], axis=1),
                       taken=ct[e + 1] - ct[ii + 1], dealt=cd[e + 1] - cd[ii + 1])


def table(nm, gens):
    K = ("hold", "move", "fight")
    n, T, D = np.zeros((3, 9)), np.zeros((3, 9)), np.zeros((3, 9))
    sp, fr = np.zeros(9), np.zeros(9)
    for g in gens:
        for r in g:
            k = np.where(r["seen"], 2, np.where(r["moved"] < 60, 0, 1))
            np.add.at(n, (k, r["w"]), 1)
            np.add.at(T, (k, r["w"]), r["taken"])
            np.add.at(D, (k, r["w"]), r["dealt"])
            if "fire" in r:
                np.add.at(fr, r["w"], r["fire"])
                np.add.at(sp, r["w"], r["fire"] & ~r["seen"])
    tot = n.sum()
    print("\n{}: {:.0f} samples with the enemy near".format(nm, tot))
    print("  {:<8} {:>8} | by the weapon in hand: share of that kind, then deals / takes / the one less the other in the next 5 s".format("", "of near"))
    for i, k in enumerate(K):
        line = "  {:<8} {:>7.1%} |".format(k, n[i].sum() / max(tot, 1))
        for w_, wn in W3:
            c = max(n[i, w_], 1)
            line += " {} {:>4.0%} {:>5.1f}/{:>5.1f}/{:>+5.1f} |".format(wn[:4], n[i, w_] / max(n[i].sum(), 1), D[i, w_] / c, T[i, w_] / c, (D[i, w_] - T[i, w_]) / c)
        print(line)
    if fr.sum():
        print("  spam: the share of his trigger time with the enemy not in view: " + ", ".join(
            "{} {:.0%}".format(wn, sp[w_] / max(fr[w_], 1)) for w_, wn in W3 + ((5, "grenades"), (6, "plasma"))))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=SS.MAPS)
    ap.add_argument("--rec", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "cypher", "u90"))
    a = ap.parse_args()
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    maps = a.maps.split(",")
    table("the pros", (pro_rows(sorted(glob.glob(os.path.join(root, "sets_lite2", mp, "*.npz")))) for mp in maps))
    table("Bobby ({})".format(os.path.basename(a.rec)), (bobby_rows(a.rec, mp) for mp in maps))

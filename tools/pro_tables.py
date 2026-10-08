"""Tables from the pro demos to seed BobbyBones' teachers with (owner, 2026-10-08: "weapon preference, style, intention
can and should be tuned on the pro demos"). Reads the converted sets of sim/demo_dataset.py (per 25 ms frame: the
inputs of the followed player and what he did) and counts:

  weapon by distance   which of rockets / rail / lightning he holds and fires at which distance, in the frames where he
                       owns all three with ammo (a choice, not a lack)
  styles               per demo: his split between the three and the distance he fights at (do players differ?)
  spawn                the first big weapon after a spawn and how long it takes; time without one
  items                what he picks up next, by what he has (bare / armed, low / middle / stacked)
  engagement           how much he has the enemy in view, fires, and closes or opens the distance, by what he has and holds

    python tools/pro_tables.py [--map bloodrun] [--limit N] [--json docs/pro_tables.json]

One process on purpose (it may run beside a training run). No player names are in the sets.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")
BIG = (0, 1, 2)
EDGES = np.arange(0, 1550, 50)
STACK = ("low (<70)", "middle (70-150)", "stacked (>150)")
ITEMS = ("rl", "rg", "lg", "mega", "red", "yellow")


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default=os.path.join(ROOT, "docs", "pro_tables.json"))
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(demo_root(), "sets", a.map, "*.npz")))
    if a.limit:
        files = files[::max(1, len(files) // a.limit)][:a.limit]
    nb = len(EDGES)
    hand = np.zeros((9, nb))                  # in hand, enemy in view, owning all three: weapon x distance bin
    fired = np.zeros((9, nb))
    eng = np.zeros((4, 3, 5))                 # big weapons owned x stack: frames, in view, firing, closing sum, closing frames
    eng_w = np.zeros((9, 3, 5))               # weapon in hand x stack, the same
    nxt = np.zeros((2, 3, len(ITEMS)))        # bare / armed x stack -> the next thing picked up
    first_w = np.zeros(3)
    first_t, lives, bare_fr, alive_fr = [], 0, 0, 0
    per_demo = []
    dist_fire = {k: [] for k in BIG}
    stack_hist = np.zeros(8)                  # health + armor in steps of 50
    minutes = 0.0
    for fi, f in enumerate(files):
        try:
            d = np.load(f)
            o, act, first = d["obs"], d["act"], d["first"]
        except Exception:                      # noqa: BLE001
            continue
        hp = o[:, 4].astype(np.float32) * 200.0
        ar = o[:, 5].astype(np.float32) * 200.0
        alive = (o[:, 8] < 0.5) & (hp > 0)
        vis = (o[:, 35] > 0.5) & alive
        dist = np.linalg.norm(o[:, 37:40].astype(np.float32), axis=1) * 1000.0
        hold = o[:, 71:80].astype(np.float32).argmax(1)
        owns = o[:, 80:89] > 0.5
        ammo = o[:, 89:98].astype(np.float32) > 0.0
        fire = (act[:, 5] > 0) & alive
        n = len(hp)
        minutes += n / 2400.0
        nbig = owns[:, BIG].sum(1)
        tot = hp + ar
        sb = np.where(tot < 70, 0, np.where(tot <= 150, 1, 2))
        b = np.clip(np.digitize(dist, EDGES) - 1, 0, nb - 1)
        all3 = (owns[:, BIG] & ammo[:, BIG]).all(1)
        m = vis & all3
        np.add.at(hand, (hold[m], b[m]), 1)
        m = vis & all3 & fire
        np.add.at(fired, (hold[m], b[m]), 1)
        for k in BIG:
            mk = vis & fire & (hold == k)
            if mk.any():
                dist_fire[k].append(dist[mk][::8])
        # closing speed: the change of distance over one second, both ends in view
        dd = np.full(n, np.nan, np.float32)
        ok = vis[:-40] & vis[40:] & ~np.maximum.accumulate(first[::-1])[::-1][:-40] if False else vis[:-40] & vis[40:]
        cut = np.convolve(first.astype(np.int32), np.ones(41, np.int32))[40:40 + n - 40] > 0
        ok &= ~cut
        dd[:-40][ok] = (dist[:-40] - dist[40:])[ok]                     # positive = he closes in
        cl = np.isfinite(dd)
        for arr, key in ((eng, nbig), (eng_w, hold)):
            np.add.at(arr[:, :, 0], (key[alive], sb[alive]), 1)
            np.add.at(arr[:, :, 1], (key[vis], sb[vis]), 1)
            np.add.at(arr[:, :, 2], (key[fire], sb[fire]), 1)
            np.add.at(arr[:, :, 3], (key[cl], sb[cl]), dd[cl])
            np.add.at(arr[:, :, 4], (key[cl], sb[cl]), 1)
        np.add.at(stack_hist, np.clip((tot[alive] // 50).astype(np.int64), 0, 7), 1)
        alive_fr += int(alive.sum())
        bare_fr += int((alive & (nbig == 0)).sum())
        # pickups inside a stretch: a weapon newly owned, health up by 60 or more (mega), armor up by 75+ (red) / 40+ (yellow)
        same = ~first[1:] & alive[1:] & alive[:-1]
        ev = []
        for k in BIG:
            for t in np.nonzero(same & owns[1:, k] & ~owns[:-1, k])[0]:
                ev.append((int(t) + 1, k))
        dh, da = hp[1:] - hp[:-1], ar[1:] - ar[:-1]
        for t in np.nonzero(same & (dh >= 60))[0]:
            ev.append((int(t) + 1, 3))
        for t in np.nonzero(same & (da >= 75))[0]:
            ev.append((int(t) + 1, 4))
        for t in np.nonzero(same & (da >= 40) & (da < 75))[0]:
            ev.append((int(t) + 1, 5))
        ev.sort()
        for t, k in ev:
            t0 = max(0, t - 120)                                         # what he had three seconds before
            if first[t0 + 1:t + 1].any() or not alive[t0]:
                t0 = t - 1
            nxt[int(nbig[t0] > 0), sb[t0], k] += 1
        # spawns: a stretch that starts alive with no big weapon and no armor
        starts = np.nonzero(alive & ~np.concatenate([[False], alive[:-1]]) | (first & alive))[0]
        for t in starts:
            if nbig[t] > 0 or ar[t] > 0:
                continue
            lives += 1
            end = t + 1
            while end < n and alive[end] and not first[end]:
                end += 1
            got = np.nonzero(nbig[t:end] > 0)[0]
            if len(got):
                first_t.append(got[0] / 40.0)
                first_w[int(owns[t + got[0], BIG].argmax())] += 1
        m = vis & all3 & fire & (hold < 3)
        if m.sum() >= 400:
            sh = np.bincount(hold[m], minlength=3)[:3] / m.sum()
            per_demo.append([float(x) for x in sh] + [float(np.median(dist[vis & fire])) if (vis & fire).any() else 0.0])
        if fi % 100 == 0:
            print("{}/{} demos, {:.0f} minutes".format(fi, len(files), minutes), flush=True)

    def share(x):
        return (x / max(1.0, x.sum())).round(3).tolist()

    out = dict(map=a.map, demos=len(files), minutes=round(minutes, 1), edges=EDGES.tolist(), weapons=W[:3])
    three = hand[:3].sum(0)
    out["in_hand_by_distance"] = {W[k]: (hand[k] / np.maximum(1.0, three)).round(3).tolist() for k in BIG}
    out["in_hand_frames"] = three.astype(int).tolist()
    three_f = fired[:3].sum(0)
    out["fired_by_distance"] = {W[k]: (fired[k] / np.maximum(1.0, three_f)).round(3).tolist() for k in BIG}
    out["fired_frames"] = three_f.astype(int).tolist()
    out["fire_distance"] = {W[k]: [round(float(x)) for x in np.percentile(np.concatenate(dist_fire[k]), (10, 25, 50, 75, 90))]
                            for k in BIG if dist_fire[k]}
    pdm = np.array(per_demo) if per_demo else np.zeros((0, 4))
    out["styles"] = dict(demos=len(pdm), mean_split=pdm[:, :3].mean(0).round(3).tolist() if len(pdm) else [],
                         spread=pdm[:, :3].std(0).round(3).tolist() if len(pdm) else [],
                         leaning=[round(float((pdm[:, k] > 0.5).mean()), 3) for k in range(3)] if len(pdm) else [],
                         no_leaning=round(float((pdm[:, :3].max(1) <= 0.5).mean()), 3) if len(pdm) else 0,
                         distance_when_leaning=[round(float(np.median(pdm[pdm[:, k] > 0.5, 3]))) if (pdm[:, k] > 0.5).any() else 0
                                                for k in range(3)] if len(pdm) else [],
                         split_distance_corr=[round(float(np.corrcoef(pdm[:, k], pdm[:, 3])[0, 1]), 2) for k in range(3)] if len(pdm) > 5 else [])
    ft = np.array(first_t) if first_t else np.zeros(1)
    out["spawn"] = dict(lives=lives, got_a_big_weapon=round(len(first_t) / max(1, lives), 3), first_weapon=dict(zip(W[:3], share(first_w))),
                        seconds=[round(float(x), 1) for x in np.percentile(ft, (25, 50, 75, 90))],
                        time_without_one=round(bare_fr / max(1, alive_fr), 3))
    out["stack_time"] = dict(zip(["{}-{}".format(50 * i, 50 * i + 49) for i in range(7)] + ["350+"], share(stack_hist)))
    out["next_item"] = {("bare" if i == 0 else "armed") + ", " + STACK[j]: dict(zip(ITEMS, share(nxt[i, j])), n=int(nxt[i, j].sum()))
                        for i in range(2) for j in range(3)}

    def eng_rows(arr, names):
        r = {}
        for i, nm in enumerate(names):
            for j in range(3):
                fr = arr[i, j, 0]
                if fr < 2400:
                    continue
                r["{}, {}".format(nm, STACK[j])] = dict(minutes=round(fr / 2400.0, 1), in_view=round(float(arr[i, j, 1] / fr), 3),
                                                      firing=round(float(arr[i, j, 2] / fr), 3),
                                                      closing_units_per_s=round(float(arr[i, j, 3] / max(1.0, arr[i, j, 4])), 1))
        return r
    out["engagement_by_weapons_owned"] = eng_rows(eng, ("no big weapon", "one", "two", "three"))
    out["engagement_by_weapon_in_hand"] = eng_rows(eng_w, W)
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("edges", "in_hand_frames", "fired_frames")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())

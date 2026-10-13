"""The pros' spawn openings (owner, 2026-10-13: "He should have more or less memorized routes from each spawn point to
the nearest items. Sort of like chess openings"): for every spawn point of a map, what the pros pick up first, second
and third in a life that starts there, how long it takes them, the way they go, and whether the choice depends on where
the enemy was when he made the frag. Data only: nothing here is read by the simulator or the trainer yet.

    python tools/pro_openings.py [--map bloodrun,aerowalk,...] [--limit N]
        -> sim/pro_spawn_openings/<map>.json  and  docs/design/openings/README.md (the tables, all maps of the call)

Reads the light demo sets (sim/demo_dataset.py --lite: per 25 ms frame of the followed player his health, armor, the
weapons he owns, his position, the enemy's position while the server sent him; `first` = a new stretch: a spawn, a cut,
a gap). What the sets do not hold and how it is filled in:
  a spawn        a stretch that starts with 118 or more health (the game's 125), no armor and no weapon but the machine
                 gun and the gauntlet. The places are clustered (they repeat to the unit) and set beside the
                 info_player_deathmatch entities of data/maps/<map>.bsp: the position written is the pros' own (the
                 game's), `bsp` says how far the map file's nearest spawn entity is.
  a pickup       a weapon newly owned, health up by 60 or more (mega), armor up (100 red, 50 yellow, 25 green, 5 a shard),
                 given to the nearest item of that kind in plugins/duel_items.json within NEAR units. Ammunition boxes
                 cannot be seen (the sets say only "has ammunition"). A weapon gained far from every item of its kind is
                 a dropped one: it is counted (`drops`) and defines no opening.
  jumps          not recorded in the light sets: read off the height (rising by more than JUMP_VZ units a second out of
                 level or falling motion); a rise faster than PAD_VZ is a jump pad, a step of more than TELE units in a
                 frame a teleporter.
  the enemy      his position as the server last sent it in the last second of the life before (the frag); the time
                 between the death and the spawn is not in the sets. Distances are straight lines, not ways.

An opening = the first one, two or three big pickups (mega, the armors but shards, the weapons) within WINDOW seconds of
the spawn. It is kept when at least MIN_LIVES lives and MIN_SHARE of the spawn's lives took it. Its route is one real
life's: the one whose pickup times are nearest to the opening's medians (lives of ten seconds or more first).
One process on purpose (it runs beside a training run). No player names or demo names are read into any output.
"""
import argparse
import glob
import json
import os
import re
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure"
WINDOW = 15.0            # seconds of a life in which pickups count for its opening
ROUTE_S, ROUTE_DT = 10.0, 0.25
MIN_LIVES, MIN_SHARE = 5, 0.10
TOP = (4, 3, 2)          # openings kept per spawn at one, two, three pickups
NEAR = 120.0             # a pickup belongs to an item this near (as tools/pro_routes.py)
SPAWN_R = 64.0           # starts this near to each other are one spawn point
JUMP_VZ, PAD_VZ, TELE = 180.0, 420.0, 200.0
ENEMY_NEAR = 500.0       # "the enemy is at the item"
W = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")          # the sets' weapon order (duel_env.WEAPONS)
WCLASS = {"weapon_rocketlauncher": 0, "weapon_railgun": 1, "weapon_lightning": 2, "weapon_shotgun": 4,
          "weapon_grenadelauncher": 5, "weapon_plasmagun": 6, "weapon_hmg": 7}
LABEL = {"weapon_rocketlauncher": "RL", "weapon_railgun": "RG", "weapon_lightning": "LG", "weapon_shotgun": "SG",
         "weapon_grenadelauncher": "GL", "weapon_plasmagun": "PG", "weapon_hmg": "HMG", "item_health_mega": "MH",
         "item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA"}
SMALL = {"item_armor_shard": "shard", "item_health_small": "health5", "item_health": "health25", "item_health_large": "health50"}


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def bsp_spawns(mp):
    """the duel spawn entities of the map file (the filter of sim/qsim.py), read from the file itself"""
    f = os.path.join(ROOT, "data", "maps", mp + ".bsp")
    if not os.path.exists(f):
        return np.zeros((0, 3), np.float32)
    b = open(f, "rb").read()
    off, ln = struct.unpack("<ii", b[8:16])
    out = []
    for block in re.findall(r"\{([^{}]*)\}", b[off:off + ln].decode("latin1")):
        e = dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', block))
        if e.get("classname") != "info_player_deathmatch" or "origin" not in e:
            continue
        if "duel" in e.get("not_gametype", "") or ("gametype" in e and "duel" not in e["gametype"]) or \
                e.get("notfree", "0").strip() not in ("", "0"):
            continue
        out.append([float(v) for v in e["origin"].split()])
    return np.array(out, np.float32).reshape(-1, 3)


def map_items(mp):
    """the map's duel items: big ones with a label each (RL, RL2, YA, YA2, ...), small ones by kind"""
    rows = json.load(open(os.path.join(ROOT, "plugins", "duel_items.json")))[mp]
    big, small, seen = [], [], {}
    for cls, x, y, z in rows:
        if cls in LABEL:
            n = seen[cls] = seen.get(cls, 0) + 1
            big.append(dict(label=LABEL[cls] + (str(n) if n > 1 else ""), cls=cls, pos=[x, y, z]))
        elif cls in SMALL:
            small.append((SMALL[cls], [x, y, z]))
    return big, small


def nearest(pos, cand):
    """index into cand (a list of positions) of the one nearest to pos, and the distance"""
    if not len(cand):
        return -1, 1e9
    d = np.linalg.norm(np.asarray(cand, np.float32) - pos, axis=1)
    return int(d.argmin()), float(d.min())


def read_lives(mp, limit):
    """every spawn life of the map's sets: dict(pos0, seq [(label, seconds)], small counts, track, enemy at the frag)"""
    big, small = map_items(mp)
    by_cls = {}
    for i, it in enumerate(big):
        by_cls.setdefault(it["cls"], []).append(i)
    wcls = {v: k for k, v in WCLASS.items()}
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
    if limit:
        files = files[::max(1, len(files) // limit)][:limit]
    lives, used, frames, drops = [], 0, 0, 0
    win, rn, stepn = int(WINDOW * 40), int(ROUTE_S * 40), int(ROUTE_DT * 40)
    for fi, f in enumerate(files):
        try:
            d = np.load(f)
            q, first = d["lite"], d["first"].copy()
        except Exception:                                       # noqa: BLE001
            continue
        if q.ndim != 2 or q.shape[1] < 32 or len(q) < 2:
            continue
        used += 1
        frames += len(q)
        first[0] = True
        hp, ar, pos, epos = q[:, 0], q[:, 1], q[:, 5:8], q[:, 8:11]
        owns, present = q[:, 12:21] > 0.5, q[:, 31] > 0.5
        starts = np.nonzero(first)[0]
        seen_spawn = False
        ends = np.append(starts[1:], len(q))
        nobig = ~owns[:, [0, 1, 2, 4, 5, 6, 7]].any(1)
        for s, e in zip(starts, ends):
            if hp[s] < 118 or ar[s] > 0 or not nobig[s]:
                continue
            e2 = min(e, s + win)
            h, a, p, o = hp[s:e2], ar[s:e2], pos[s:e2], owns[s:e2]
            seq, sm = [], {}
            for k, cls in wcls.items():
                for t in np.nonzero(o[1:, k] & ~o[:-1, k])[0] + 1:
                    idx = by_cls.get(cls, [])
                    j, dist = nearest(p[t], [big[i]["pos"] for i in idx])
                    if j >= 0 and dist <= NEAR:
                        seq.append((int(t), big[idx[j]]["label"]))
                    else:
                        drops += 1
            dh, da = h[1:] - h[:-1], a[1:] - a[:-1]
            for t in np.nonzero(dh >= 60)[0] + 1:
                idx = by_cls.get("item_health_mega", [])
                j, dist = nearest(p[t], [big[i]["pos"] for i in idx])
                if j >= 0 and dist <= NEAR:
                    seq.append((int(t), big[idx[j]]["label"]))
            for t in np.nonzero((dh > 0) & (dh < 60))[0] + 1:
                kind = "health5" if dh[t - 1] <= 5 else ("health25" if dh[t - 1] <= 25 else "health50")
                sm[kind] = sm.get(kind, 0) + 1
            for t in np.nonzero(da > 0)[0] + 1:
                v = da[t - 1]
                cls = "item_armor_body" if v >= 75 else ("item_armor_combat" if v >= 40 else ("item_armor_jacket" if v >= 20 else None))
                if cls is None:
                    sm["shard"] = sm.get("shard", 0) + 1
                    continue
                idx = by_cls.get(cls, [])
                j, dist = nearest(p[t], [big[i]["pos"] for i in idx])
                if j >= 0 and dist <= NEAR:
                    seq.append((int(t), big[idx[j]]["label"]))
            seq.sort()
            labels, times = [], []
            for t, lab in seq:                                  # an item counts once in an opening
                if lab not in labels:
                    labels.append(lab)
                    times.append(t / 40.0)
            # the way, and what the height says of jumps
            tr = pos[s:min(e, s + rn + 1)]
            vz = np.diff(tr[:, 2]) * 40.0
            step = np.linalg.norm(np.diff(tr, axis=0), axis=1)
            tele = np.nonzero(step > TELE)[0] + 1
            # a take-off: the height starts to rise (the frame it happens in holds a part of the rise only), the frame
            # after rises faster than JUMP_VZ and the one after that is a free flight (gravity takes 20 a frame): a
            # stair's step and a ramp are not
            up = np.nonzero((vz[1:] >= 60.0) & (vz[:-1] < 60.0) & (step[1:] <= TELE))[0] + 1
            up = [t for t in up if t + 2 < len(vz) and vz[t + 1] > JUMP_VZ and abs(vz[t + 2] - (vz[t + 1] - 20.0)) < 10.0]
            jumps = [(round(float(t) / 40.0, 3), bool(vz[t + 1] > PAD_VZ)) for t in up]
            # the enemy as the server last sent him in the last second of the life before
            enemy = None
            # the game's start: the file's first spawn, in its first 40 seconds or out of the warm-up (he held three weapons or more)
            start = bool(not seen_spawn and (s < 1600 or owns[s - 1][[0, 1, 2, 4, 5, 6]].sum() >= 3))
            seen_spawn = True
            if s > 0 and not start:
                lo = max(int(starts[np.searchsorted(starts, s - 1, side="right") - 1]), s - 40)
                pr = np.nonzero(present[lo:s])[0]
                if len(pr) and hp[s - 1] < 118:
                    enemy = epos[lo + int(pr[-1])].astype(np.float64).round(0).tolist()
            lives.append(dict(pos0=pos[s].astype(np.float64), labels=labels, times=times, small=sm, secs=(e - s) / 40.0,
                              track=tr[::stepn].astype(np.float64).round(0), jumps=jumps,
                              tele=[round(float(t) / 40.0, 3) for t in tele], enemy=enemy, start=start))
        if fi % 200 == 0:
            print("  {} {}/{} sets, {} lives".format(mp, fi, len(files), len(lives)), flush=True)
    return big, lives, dict(demos=used, minutes=round(frames / 2400.0, 1), drops=drops)


def cluster(lives):
    """the places lives start at: the most used start first, everything within SPAWN_R of it is that spawn point"""
    P = np.array([l["pos0"] for l in lives]).reshape(-1, 3)
    left = np.ones(len(P), bool)
    out, which = [], np.full(len(P), -1)
    while left.any():
        key = np.round(P[left] / 16.0).astype(np.int64)
        u, c = np.unique(key, axis=0, return_counts=True)
        centre = u[c.argmax()] * 16.0
        m = left & (np.linalg.norm(P - centre, axis=1) < SPAWN_R)
        if not m.any():                                          # (cannot happen: the densest cell holds a start)
            break
        which[m] = len(out)
        out.append(np.median(P[m], axis=0))
        left &= ~m
    return out, which


def opening(group, n_spawn, depth):
    """one opening's facts from the lives that took it (group: lives whose first `depth` big pickups are the same)"""
    T = np.array([l["times"][:depth] for l in group])
    med = np.median(T, axis=0)
    err = np.abs(T - med).sum(1)
    long_ = np.array([l["secs"] >= ROUTE_S for l in group])
    order = np.lexsort((err, ~long_))                           # ten-second lives first, then the nearest to the medians
    rep = group[int(order[0])]
    small = {}
    for l in group:
        for k, v in l["small"].items():
            small[k] = small.get(k, 0) + v
    return dict(items=rep["labels"][:depth], lives=len(group), share=round(len(group) / n_spawn, 3),
                seconds=[round(float(x), 2) for x in med],
                seconds_quartiles=[[round(float(x), 2) for x in np.percentile(T[:, i], (25, 75))] for i in range(depth)],
                small_per_life={k: round(v / len(group), 2) for k, v in sorted(small.items())},
                route=dict(step_s=ROUTE_DT, seconds=round(min(rep["secs"], ROUTE_S), 2), xyz=rep["track"].tolist(),
                           pickups=[round(float(x), 2) for x in rep["times"][:depth]],
                           jumps=[t for t, pad in rep["jumps"] if not pad], pads=[t for t, pad in rep["jumps"] if pad],
                           teleports=rep["tele"]))


def tree(group, n_spawn, depth=1):
    """the openings among these lives at `depth` pickups, each with those that follow it"""
    if depth > 3:
        return []
    by = {}
    for l in group:
        if len(l["labels"]) >= depth:
            by.setdefault(l["labels"][depth - 1], []).append(l)
    out = []
    for lab, g in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(g) < MIN_LIVES or len(g) < MIN_SHARE * n_spawn:
            continue
        o = opening(g, n_spawn, depth)
        o["then"] = tree(g, n_spawn, depth + 1)
        out.append(o)
    return out[:TOP[depth - 1]]


def enemy_choice(group, opens, items):
    """does the first pickup depend on where the enemy was at the frag: among the lives that took one of the spawn's
    kept first pickups and have his position"""
    firsts = [o["items"][0] for o in opens]
    if len(firsts) < 2:
        return None
    ipos = np.array([items[f] for f in firsts], np.float64)
    rows = [(firsts.index(l["labels"][0]), np.linalg.norm(ipos - np.array(l["enemy"]), axis=1))
            for l in group if l["enemy"] is not None and l["labels"] and l["labels"][0] in firsts]
    if len(rows) < 20:
        return dict(lives=len(rows), note="too few lives with the enemy's position")
    ch = np.array([r[0] for r in rows])
    D = np.array([r[1] for r in rows])
    far, nearest_ = D.argmax(1), D.argmin(1)
    p = np.bincount(ch, minlength=len(firsts)) / len(ch)
    out = dict(lives=len(rows), first_items=firsts,
               took_farthest_from_enemy=round(float((ch == far).mean()), 3),
               by_chance=round(float(sum(p[k] * (far == k).mean() for k in range(len(firsts)))), 3),
               took_nearest_to_enemy=round(float((ch == nearest_).mean()), 3),
               nearest_by_chance=round(float(sum(p[k] * (nearest_ == k).mean() for k in range(len(firsts)))), 3),
               hits=int((ch == far).sum()), by_item=[])
    for k, f in enumerate(firsts):
        at = D[:, k] < ENEMY_NEAR
        out["by_item"].append(dict(item=f, enemy_at_it=int(at.sum()), taken_n=int((ch[at] == k).sum()),
                                   taken_with_enemy_at_it=round(float((ch[at] == k).mean()), 3) if at.sum() else None,
                                   taken_otherwise=round(float((ch[~at] == k).mean()), 3) if (~at).sum() else None,
                                   enemy_distance_when_taken=round(float(np.median(D[ch == k, k]))) if (ch == k).any() else None,
                                   enemy_distance_when_not=round(float(np.median(D[ch != k, k]))) if (ch != k).any() else None))
    return out


def build(mp, limit):
    big, lives, facts = read_lives(mp, limit)
    items = {it["label"]: it["pos"] for it in big}
    bsp = bsp_spawns(mp)
    out = dict(map=mp, demos=facts["demos"], minutes=facts["minutes"], lives=len(lives),
               game_start_lives=sum(1 for l in lives if l["start"]), dropped_weapon_pickups=facts["drops"],
               window_s=WINDOW, min_lives=MIN_LIVES, min_share=MIN_SHARE,
               items=items, spawns=[], other_starts=0)
    if not lives:
        return out
    centres, which = cluster(lives)
    keep = [k for k in range(len(centres)) if (which == k).sum() >= max(MIN_LIVES, 0.01 * len(lives))]
    out["other_starts"] = int(sum((which == k).sum() for k in range(len(centres)) if k not in keep))
    keep.sort(key=lambda k: -(which == k).sum())
    en_hit = en_n = 0
    at = {"stack": [0, 0, 0.0], "weapon": [0, 0, 0.0]}           # the enemy at the item: lives, taken, taken at the rate without him
    en_exp = 0.0
    for n, k in enumerate(keep):
        g = [lives[i] for i in np.nonzero(which == k)[0]]
        c = centres[k]
        j, dist = nearest(c, bsp)
        ni, nd = nearest(c, [it["pos"] for it in big])
        opens = tree(g, len(g))
        none = sum(1 for l in g if not l["labels"])
        en = enemy_choice(g, opens, items)
        if en and "hits" in en:
            en_hit += en["hits"]
            en_n += en["lives"]
            en_exp += en["by_chance"] * en["lives"]
            for b in en["by_item"]:
                if b["enemy_at_it"] and b["taken_otherwise"] is not None:
                    a_ = at["stack" if b["item"][:2] in ("MH", "RA", "YA", "GA") else "weapon"]
                    a_[0] += b["enemy_at_it"]
                    a_[1] += b["taken_n"]
                    a_[2] += b["taken_otherwise"] * b["enemy_at_it"]
        out["spawns"].append(dict(
            name="S{}".format(n + 1), pos=[round(float(x)) for x in c], lives=len(g),
            bsp=dict(pos=bsp[j].tolist(), distance=round(dist)) if j >= 0 else None,
            nearest_item=big[ni]["label"] if ni >= 0 else None, nearest_item_distance=round(nd),
            no_big_pickup=round(none / len(g), 3), enemy_known=sum(1 for l in g if l["enemy"] is not None),
            openings=opens, enemy=en))
    out["enemy_all_spawns"] = dict(lives=en_n, took_farthest_from_enemy=round(en_hit / en_n, 3) if en_n else None,
                                   by_chance=round(en_exp / en_n, 3) if en_n else None,
                                   enemy_at_item={k: dict(lives=v[0], taken=round(v[1] / v[0], 3), taken_without_him=round(v[2] / v[0], 3))
                                                  for k, v in at.items() if v[0]})
    return out


def table(res):
    """the map's table for the README"""
    L = ["### {}".format(res["map"]), "",
         "{} demos ({:.0f} minutes of play), {} spawn lives ({} of them a game's start), {} spawn points{}.".format(
             res["demos"], res["minutes"], res["lives"], res["game_start_lives"], len(res["spawns"]),
             ", {} starts at no spawn point left out".format(res["other_starts"]) if res["other_starts"] else ""), "",
         "| spawn | lives | opening (items in order) | share | seconds to first / second / third |",
         "|---|---|---|---|---|"]

    def rows(sp, opens, lead):
        for o in opens:
            L.append("| {} | {} | {} | {:.0%} | {} |".format(
                lead[0], lead[1], " > ".join(o["items"]), o["share"], " / ".join("{:.1f}".format(x) for x in o["seconds"])))
            lead = ("", "")
            rows(sp, o["then"], lead)

    for sp in res["spawns"]:
        lead = ("{} ({}, {}, {}; by {})".format(sp["name"], *sp["pos"], sp["nearest_item"]), str(sp["lives"]))
        if not sp["openings"]:
            L.append("| {} | {} | none kept ({:.0%} of lives took nothing big in {:.0f} s) | | |".format(
                lead[0], lead[1], sp["no_big_pickup"], res["window_s"]))
        rows(sp, sp["openings"], lead)
    L.append("")
    ea = res.get("enemy_all_spawns") or {}
    if ea.get("lives"):
        L.append("The enemy: in {} lives with his place at the frag known and a choice of first pickup, the pros took the one "
                 "farthest from him {:.0%} of the time; {:.0%} if the choice did not depend on him.".format(
                     ea["lives"], ea["took_farthest_from_enemy"], ea["by_chance"]))
        for k, nm in (("stack", "an armor or the mega"), ("weapon", "a weapon")):
            v = ea["enemy_at_item"].get(k)
            if v:
                L.append("With him within {:.0f} units of {} that is one of the spawn's first pickups ({} lives) they took it {:.0%} "
                         "of the time; {:.0%} at the rate of the lives without him there.".format(ENEMY_NEAR, nm, v["lives"], v["taken"], v["taken_without_him"]))
        L.append("")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=MAPS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--readme", default=os.path.join(ROOT, "docs", "design", "openings", "README.md"))
    ap.add_argument("--notes", default="", help="a text file put between the README's head and its tables (what stands out)")
    a = ap.parse_args()
    od = os.path.join(ROOT, "sim", "pro_spawn_openings")
    os.makedirs(od, exist_ok=True)
    L = []
    for mp in a.map.split(","):
        res = build(mp, a.limit)
        with open(os.path.join(od, mp + ".json"), "w", encoding="utf-8") as f:
            json.dump(res, f, separators=(",", ":"))
        L += table(res)
        print("{}: {} demos, {} lives, {} spawn points, {} openings at one pickup, {} in all; enemy {}".format(
            mp, res["demos"], res["lives"], len(res["spawns"]), sum(len(s["openings"]) for s in res["spawns"]),
            sum(count(s["openings"]) for s in res["spawns"]), json.dumps(res.get("enemy_all_spawns"))), flush=True)
    head = ["# The pros' spawn openings", "",
            "Written by `tools/pro_openings.py` from the light demo sets; the data is `sim/pro_spawn_openings/<map>.json` "
            "(per spawn point: its openings with shares, median times, a real route at {} s steps for {:.0f} s, and the "
            "first pickup set beside the enemy's place at the frag). An opening is the first one, two or three big pickups "
            "(mega MH, red RA, yellow YA, green GA, the weapons) within {:.0f} s of a spawn, kept at {} lives and {:.0%} of "
            "the spawn's lives; a row under an opening is what followed it. Shares are of the spawn's lives. Times are "
            "medians from the spawn.".format(ROUTE_DT, ROUTE_S, WINDOW, MIN_LIVES, MIN_SHARE), ""]
    notes = ""                                                  # what stands out: written by hand, kept over a new run
    if a.notes and os.path.exists(a.notes):
        notes = open(a.notes, encoding="utf-8").read()
    elif os.path.exists(a.readme):
        old = open(a.readme, encoding="utf-8").read()
        if "<!-- notes -->" in old and "<!-- tables -->" in old:
            notes = old.split("<!-- notes -->")[1].split("<!-- tables -->")[0]
    head += ["<!-- notes -->"] + notes.strip().split("\n") + ["<!-- tables -->", ""]
    os.makedirs(os.path.dirname(a.readme), exist_ok=True)
    with open(a.readme, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + L))


def count(opens):
    return sum(1 + count(o["then"]) for o in opens)


if __name__ == "__main__":
    sys.exit(main())

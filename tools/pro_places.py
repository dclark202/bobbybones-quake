"""Where the pros' blind shots land: the places of a map that rockets, grenades and plasma are fired at with no enemy in
view, for the "place tokens" a model can aim at.

    python tools/pro_places.py                         the six maps -> sim/pro_places/<map>.json and a list on stdout
    python tools/pro_places.py --picture               also docs/design/places/<map>.png (the system Python: matplotlib)
    python tools/pro_places.py --map bloodrun --shots his.npy --out his.json      another player's blind shots, the same way

Reads <demo root>/yardsticks/blind_<map>.npy, written by tools/pro_yardsticks.py (run that first): a row a blind shot
(no enemy in his view for a second or more): weapon, where it landed, where he stood, whether the enemy came into view
near there within 2 s, whether his hit counter went up as it landed (-1: not known). Where it landed is his view traced
to the first wall for rockets and plasma and the simulator's grenade flight for grenades (see that tool).

A place is found by weight: a rocket and a grenade count 1, a plasma cell 0.2 (five cells for a rocket, by damage; a
second of plasma is ten cells). A shot that lands under 150 units from where he stands is left out of the places: it
is a rocket jump or a shot at the floor, not a place to aim at (`at_own_feet` has their number and the spots they are
fired at most: the pros' rocket jumps). The heaviest cell of a 64-unit grid over what is left gives a start; the place's middle is
the weighted mean of the shots within RADIUS of it, moved to that mean three times; its shots are taken out and the next
place is looked for, until KEEP places are found. RADIUS is 128 units, a little over a rocket's splash (120). The typical
place the shots were fired from is found the same way among the places he stood (the two heaviest are given).

The strength of a position (`standing_there` of a place; sim/pro_places/<map>_cells.json for every cell of 256 x 256
units and 128 high): what the pros do and how it ends when they stand there, from two more files of that tool,
sight_<map>.npy (a row a sighting: the enemy comes into view after a second or more out of it) and view_<map>.npy (the
frames with the enemy in view, one row for every eight):
  sightings            that begin with him standing there (in a place: within RADIUS of its middle); with fewer than
                       MIN_SIGHT (30) nothing else is given for a place, and a cell is left out
  outcome              his frags less his deaths in the 10 s after such a sighting, a sighting (those whose 10 s lie
                       within one stretch of a demo: sightings_10s); frags and deaths apart too
  outcome_expected     the same for all sightings of the map in his situation (health plus armor under 60, 60 to 125,
                       over 125; a big weapon or none; the enemy's weapon big or small): what his stack and the weapons
                       would give anywhere. outcome_over_expected is the place's own share: stacked players stand near
                       the items, so the plain outcome of a place beside an armor says little about the place
  weapon_shares        the weapon in his hand, % of his time there with the enemy in view; fire_shares: of the time
                       he fires there, which weapon; firing_share: how much of that time he fires at all
  height               he stands 48 units or more above the enemy, level, or below, % of that time
  distance_median      to the enemy, over that time
  closing_speed, push_share   his mean speed toward the enemy in the 3 s after a sighting there, and the share of the
                       sightings in which it is over 150 units a second
No player names are read or written.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged"
NAMES = dict(aerowalk="Aerowalk", bloodrun="Blood Run", lostworld="Lost World", sinister="Sinister",
             furiousheights="Furious Heights", battleforged="Battleforged", campgrounds="Campgrounds")
W_NAME = {0: "rockets", 5: "grenades", 6: "plasma"}             # the simulator's weapon numbers (duel_env.WEAPONS)
WEIGHT = {0: 1.0, 5: 1.0, 6: 0.2}
RADIUS, GRID, KEEP = 128.0, 64.0, 24
FEET_R = 150.0                                                 # a shot that lands this near himself is no place to aim at (a rocket jump)
MIN_SIGHT = 30                                                 # sightings a place or a cell needs for its numbers
CELL, CELL_Z = 256.0, 128.0
WEAPONS = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")           # the simulator's order (duel_env.WEAPONS)
W_SAYS = dict(rl="rockets", rg="rail", lg="lightning", mg="machine gun", sg="shotgun", gl="grenades", pg="plasma", hmg="heavy machine gun",
              g="gauntlet")
# the columns of a sighting and of a view row (tools/pro_yardsticks.py: SIGHT_COLS, VIEW_COLS)
S_STACK, S_OWN, S_ENEMY, S_TOWARD, S_F10, S_D10 = 3, 4, 6, 8, 11, 12
V_WEAPON, V_FIRED, V_HEIGHT, V_DIST, V_MS = 3, 4, 5, 6, 7
ITEMS = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA",
         "weapon_rocketlauncher": "RL", "weapon_railgun": "RG", "weapon_lightning": "LG", "weapon_grenadelauncher": "GL",
         "weapon_plasmagun": "PG", "weapon_shotgun": "SG"}


def demo_root():
    f = os.path.join(ROOT, "data", "demo_root.txt")
    p = open(f).read().strip() if os.path.exists(f) else ""
    return p or os.path.join(ROOT, "data")


def heaviest(pts, wt, left, radius=RADIUS):
    """the middle of the heaviest place among the points still left, and which of them it takes"""
    cell = np.floor(pts[left] / GRID).astype(np.int64)
    key = (cell[:, 0] + 4096) * 67108864 + (cell[:, 1] + 4096) * 8192 + (cell[:, 2] + 4096)
    u, inv = np.unique(key, return_inverse=True)
    best = int(np.bincount(inv, weights=wt[left]).argmax())
    c = np.average(pts[left][inv == best], axis=0, weights=wt[left][inv == best])
    for _ in range(3):
        m = left & (np.linalg.norm(pts - c, axis=1) <= radius)
        if not m.any():
            break
        c = np.average(pts[m], axis=0, weights=wt[m])
    return c, left & (np.linalg.norm(pts - c, axis=1) <= radius)


def near_item(p, items):
    if not items:
        return None
    d = [float(np.linalg.norm(np.asarray(q) - p)) for _, q in items]
    k = int(np.argmin(d))
    return dict(item=items[k][0], units=round(d[k]), height=round(float(p[2] - items[k][1][2])))


def own_feet(shots, items, keep=8):
    """the blind shots that land at his own feet (rocket jumps mostly): where, the most used spots first"""
    if not len(shots):
        return []
    wq = shots[:, 0].astype(np.int64)
    wt = np.ones(len(shots))
    left = np.ones(len(shots), bool)
    out = []
    while len(out) < keep and left.any():
        c, m = heaviest(shots[:, 4:7], wt, left)
        if m.sum() < 0.01 * len(shots):
            break
        left &= ~m
        out.append(dict(pos=[round(float(x)) for x in c], shots={W_NAME[k]: int((m & (wq == k)).sum()) for k in W_NAME},
                        share=round(100.0 * float(m.sum()) / len(shots), 1), near=near_item(c, items)))
    return sorted(out, key=lambda o: -o["share"])


def places(shots, items=(), keep=KEEP):
    """rows of weapon, landing (3), stood (3), met, hit -> the places, the heaviest first"""
    shots = np.asarray(shots, np.float64).reshape(-1, 9)
    shots = shots[np.isin(shots[:, 0], list(WEIGHT))]
    feet = np.linalg.norm(shots[:, 1:4] - shots[:, 4:7], axis=1) < FEET_R
    jumps = own_feet(shots[feet], items)
    n_all = len(shots)
    shots = shots[~feet]
    wq = shots[:, 0].astype(np.int64)
    land, stood, met, hit = shots[:, 1:4], shots[:, 4:7], shots[:, 7], shots[:, 8]
    wt = np.array([WEIGHT[int(x)] for x in wq])
    total = float(wt.sum())
    left = np.ones(len(shots), bool)
    out = []
    while len(out) < keep and left.any():
        c, m = heaviest(land, wt, left)
        if wt[m].sum() < 0.002 * total:
            break
        left &= ~m
        # where they were fired from
        frm, lf = [], m.copy()
        for _ in range(2):
            if not lf.any():
                break
            fc, fm = heaviest(stood, wt, lf)
            lf &= ~fm
            frm.append(dict(pos=[round(float(x)) for x in fc], share=round(100.0 * float(wt[fm].sum() / wt[m].sum()), 1),
                            near=near_item(fc, items)))
        known = m & (hit >= 0)
        out.append(dict(
            id=len(out) + 1, pos=[round(float(x)) for x in c], radius=RADIUS, share=round(100.0 * float(wt[m].sum()) / total, 2),
            shots={W_NAME[k]: int((m & (wq == k)).sum()) for k in W_NAME}, near=near_item(c, items),
            distance_median=round(float(np.median(np.linalg.norm(land[m] - stood[m], axis=1)))),
            met_share=round(100.0 * float((wt[m] * met[m]).sum() / wt[m].sum()), 1),
            hit_share=round(100.0 * float((wt[known] * hit[known]).sum() / wt[known].sum()), 1) if known.any() else None,
            fired_from=frm))
    out.sort(key=lambda p: -p["share"])                         # (the heaviest cell first is not always the heaviest place)
    for k, p in enumerate(out):
        p["id"] = k + 1
    return dict(shots={W_NAME[k]: int((wq == k).sum()) for k in W_NAME}, weight=dict(rockets=1.0, grenades=1.0, plasma=0.2),
                at_own_feet=dict(shots=int(n_all - len(shots)), share=round(100.0 * (n_all - len(shots)) / max(1, n_all), 1), under_units=FEET_R,
                                 places=jumps),
                radius=RADIUS, in_places_share=round(100.0 * (1.0 - float(wt[left].sum()) / total), 1) if total else None, places=out)


def expected(sight):
    """frags less deaths in the 10 s after a sighting, by his situation (stack band, big weapon or none, the enemy's
    weapon), over all sightings of the map -> for every sighting what its situation gives anywhere"""
    known = sight[:, S_F10] >= 0
    key = sight[:, S_STACK] * 6 + sight[:, S_OWN] * 3 + sight[:, S_ENEMY]
    net = (sight[:, S_F10] - sight[:, S_D10]).astype(np.float64)
    tot = np.bincount(key[known], weights=net[known], minlength=18)
    cnt = np.bincount(key[known], minlength=18)
    return (tot / np.maximum(cnt, 1))[key]


def strength(sm, vm, sight, view, exp):
    """what the pros do and how it ends where the sightings `sm` begin and the view rows `vm` lie (see the top of the
    file); with fewer than MIN_SIGHT sightings only their number"""
    n = int(sm.sum())
    out = dict(sightings=n)
    if n < MIN_SIGHT:
        return out
    S = sight[sm]
    known = S[:, S_F10] >= 0
    k = int(known.sum())
    out["sightings_10s"] = k
    if k:
        fr, de = float(S[known, S_F10].sum()) / k, float(S[known, S_D10].sum()) / k
        ex = float(exp[sm][known].mean())
        out.update(outcome=round(fr - de, 3), frags_a_sighting=round(fr, 3), deaths_a_sighting=round(de, 3),
                   outcome_expected=round(ex, 3), outcome_over_expected=round(fr - de - ex, 3))
    out.update(closing_speed=round(float(S[:, S_TOWARD].mean()), 1), push_share=round(100.0 * float((S[:, S_TOWARD] > 150).mean()), 1))
    V = view[vm]
    ms = V[:, V_MS].astype(np.float64)
    if ms.sum() > 0:
        held = np.bincount(V[:, V_WEAPON], weights=ms, minlength=len(WEAPONS))
        fired = np.bincount(V[:, V_WEAPON], weights=ms * V[:, V_FIRED], minlength=len(WEAPONS))
        order = np.argsort(np.repeat(V[:, V_DIST], 1))
        cum = np.cumsum(ms[order])
        out.update(in_view_seconds=round(float(ms.sum()) / 1000.0, 1),
                   weapon_shares={W_SAYS[WEAPONS[q]]: round(100.0 * float(held[q] / ms.sum()), 1) for q in np.argsort(-held) if held[q] > 0.005 * ms.sum()},
                   firing_share=round(100.0 * float(fired.sum() / ms.sum()), 1),
                   fire_shares={W_SAYS[WEAPONS[q]]: round(100.0 * float(fired[q] / fired.sum()), 1) for q in np.argsort(-fired) if fired.sum() > 0 and fired[q] > 0.005 * fired.sum()},
                   height=dict(higher=round(100.0 * float(ms[V[:, V_HEIGHT] == 1].sum() / ms.sum()), 1),
                               level=round(100.0 * float(ms[V[:, V_HEIGHT] == 0].sum() / ms.sum()), 1),
                               lower=round(100.0 * float(ms[V[:, V_HEIGHT] == -1].sum() / ms.sum()), 1)),
                   distance_median=int(V[order, V_DIST][int(np.searchsorted(cum, 0.5 * cum[-1]))]))
    return out


def cells(sight, view, exp, items):
    """the strength of every cell of CELL x CELL x CELL_Z units that MIN_SIGHT sightings or more begin in, the most
    sightings first"""
    def key(pts):
        c = np.floor(pts[:, :3] / np.array([CELL, CELL, CELL_Z])).astype(np.int64)
        return (c[:, 0] + 512) * 1048576 + (c[:, 1] + 512) * 1024 + (c[:, 2] + 512)
    ks, kv = key(sight), key(view)
    u, n = np.unique(ks, return_counts=True)
    out = []
    for k_ in u[np.argsort(-n)]:
        if (ks == k_).sum() < MIN_SIGHT:
            break
        c = np.array([(k_ >> 20) - 512, ((k_ >> 10) & 1023) - 512, (k_ & 1023) - 512], np.float64)
        mid = (c + 0.5) * np.array([CELL, CELL, CELL_Z])
        out.append(dict(cell=[int(x) for x in c], middle=[round(float(x)) for x in mid], near=near_item(mid, items),
                        **strength(ks == k_, kv == k_, sight, view, exp)))
    return out


def map_items(mp):
    """the map's big items with their labels (a duel's), read from the map file"""
    import draw_gaps as G
    ents = G.duel_entities(G.read_bsp(os.path.join(ROOT, "data", "maps", mp + ".bsp"))["text"])
    seen, out = {}, []
    for e in ents:
        lab = ITEMS.get(e.get("classname"))
        if lab and "origin" in e:
            seen[lab] = seen.get(lab, 0) + 1
            out.append((lab if seen[lab] == 1 else "{}{}".format(lab, seen[lab]), e["origin"]))
    return out


def says(pl):
    n = pl["near"]
    where = "{} units from {}{}".format(n["units"], n["item"], ", {} {}".format(abs(n["height"]), "above" if n["height"] > 0 else "below") if abs(n["height"]) >= 48 else "") if n else ""
    f = pl["fired_from"][0] if pl["fired_from"] else None
    frm = "from {} ({}% of them, {} units from {})".format(f["pos"], f["share"], f["near"]["units"], f["near"]["item"]) if f and f["near"] else ""
    st = pl.get("standing_there") or {}
    stand = "  | standing there: {} sightings".format(st["sightings"]) if st else ""
    if st.get("outcome") is not None:
        stand += ", outcome {:+.2f} ({:+.2f} over his situation), holds {}".format(
            st["outcome"], st["outcome_over_expected"], ", ".join("{} {:.0f}%".format(k, v) for k, v in list(st.get("weapon_shares", {}).items())[:2]))
    return "{:2d}  {:5.2f}%  at {}  {}  rockets {} grenades {} plasma {}  fired from {} units away, {}  met {}% hit {}%{}".format(
        pl["id"], pl["share"], pl["pos"], where, pl["shots"]["rockets"], pl["shots"]["grenades"], pl["shots"]["plasma"],
        pl["distance_median"], frm, pl["met_share"], pl["hit_share"], stand)


def picture(mp, res, shots, out_png, dpi=90):
    """the map from above (the floors as tools/draw_gaps.py draws them), the blind shots' landings as dots, the places
    as numbered circles with a line to where most of their shots were fired from"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    import draw_gaps as G
    bsp = G.read_bsp(os.path.join(ROOT, "data", "maps", mp + ".bsp"))
    ents = G.duel_entities(bsp["text"])
    gaps_f = os.path.join(ROOT, "sim", "pro_gaps", mp + ".json")
    jumps = json.load(open(gaps_f))["jumps"] if os.path.exists(gaps_f) else []
    spots = G.live_spots(json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))), ents, jumps)
    feet = spots - np.array([0.0, 0.0, G.FEET])
    tri, kind, face = G.map_triangles(bsp, ents)
    lo = spots[:, :2].min(0) - 110.0
    hi = spots[:, :2].max(0) + 110.0
    shape = (int(np.ceil((hi[1] - lo[1]) / G.CELL)), int(np.ceil((hi[0] - lo[0]) / G.CELL)))
    hi = lo + np.array([shape[1], shape[0]]) * G.CELL
    dry = kind == 0
    floor = tri[dry][G.walkable(tri[dry], face[dry], feet)]
    zlo, zhi = float(feet[:, 2].min()), float(feet[:, 2].max())
    H, _ = G.floors_seen(bsp, floor, lo, shape, feet)
    img, _ = G.shade(H, {}, zlo, zhi)
    W, Hh = hi[0] - lo[0], hi[1] - lo[1]
    s = min(15.0 / W, 13.0 / Hh)
    fig = plt.figure(figsize=(W * s + 0.6, Hh * s + 1.5), dpi=dpi, facecolor="white")
    ax = fig.add_axes([0.3 / (W * s + 0.6), 0.5 / (Hh * s + 1.5), W * s / (W * s + 0.6), Hh * s / (Hh * s + 1.5)])
    ax.imshow(img, extent=(lo[0], hi[0], lo[1], hi[1]), origin="lower", interpolation="nearest", zorder=0)
    shots = np.asarray(shots, np.float64).reshape(-1, 9)
    col = {0: "#d81e1e", 5: "#1f9a48", 6: "#1565c8"}
    rng = np.random.default_rng(0)
    for k in (6, 0, 5):
        m = np.nonzero(shots[:, 0] == k)[0]
        if len(m) > 8000:
            m = rng.choice(m, 8000, replace=False)
        ax.scatter(shots[m, 1], shots[m, 2], s=1.2, c=col[k], alpha=0.10 if k == 6 else 0.22, linewidths=0, zorder=2)
    for pl in res["places"]:
        x, y = pl["pos"][0], pl["pos"][1]
        if pl["fired_from"]:
            f = pl["fired_from"][0]["pos"]
            ax.plot([f[0], x], [f[1], y], "-", color="#222222", lw=0.9, alpha=0.75, zorder=4)
            ax.plot([f[0]], [f[1]], "o", color="#222222", ms=3.5, zorder=4)
        big = max(pl["shots"], key=lambda k_: pl["shots"][k_] * {"rockets": 1.0, "grenades": 1.0, "plasma": 0.2}[k_])
        ec = {"rockets": col[0], "grenades": col[5], "plasma": col[6]}[big]
        ax.add_patch(Circle((x, y), RADIUS, fill=False, ec=ec, lw=1.8, zorder=5))
        ax.text(x, y, str(pl["id"]), ha="center", va="center", fontsize=10, weight="bold", color="black", zorder=6,
                bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec=ec, lw=1.0, alpha=0.92))
    for lab, p in map_items(mp):
        ax.text(p[0], p[1], lab, ha="center", va="center", fontsize=7.5, color="#333333", zorder=3,
                bbox=dict(boxstyle="round,pad=0.12", fc="#fff6c8", ec="#8a7a2a", lw=0.5, alpha=0.9))
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7, colors="#9a9a9a", length=2)
    n = res["shots"]
    ax.set_title("{}: where the pros' blind shots land ({} rockets red, {} grenades green, {} plasma cells blue).\n"
                 "The {} heaviest places (circles of {:.0f} units, the colour of their main weapon), each with a line to where most of its shots were fired from".format(
                     NAMES.get(mp, mp), n["rockets"], n["grenades"], n["plasma"], len(res["places"]), RADIUS), fontsize=10)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=MAPS)
    ap.add_argument("--shots", default=None, help="a file of blind shots instead of the pros' (one map)")
    ap.add_argument("--sight", default=None, help="his sightings, with --shots (default: beside the shots, sight_ for blind_)")
    ap.add_argument("--view", default=None, help="his view rows, with --shots")
    ap.add_argument("--out", default=None, help="where the places go (one map; default sim/pro_places/<map>.json)")
    ap.add_argument("--picture", action="store_true")
    ap.add_argument("--keep", type=int, default=KEEP)
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    for mp in a.map.split(","):
        f = a.shots or os.path.join(demo_root(), "yardsticks", "blind_{}.npy".format(mp))
        if not os.path.exists(f):
            print("{}: {} is not there (run tools/pro_yardsticks.py first)".format(mp, f))
            continue
        shots = np.load(f)
        items = map_items(mp)
        res = dict(map=mp, **places(shots, items, a.keep))
        out = a.out or os.path.join(ROOT, "sim", "pro_places", mp + ".json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        fs, fv = (a.sight or f.replace("blind_", "sight_")), (a.view or f.replace("blind_", "view_"))
        if os.path.exists(fs) and os.path.exists(fv) and fs != f:
            sight, view = np.load(fs).astype(np.int64), np.load(fv).astype(np.int64)
            exp = expected(sight)
            known = sight[:, S_F10] >= 0
            res["standing"] = dict(sightings=len(sight), sightings_10s=int(known.sum()), in_view_seconds=round(float(view[:, V_MS].sum()) / 1000.0),
                                   outcome=round(float((sight[known, S_F10] - sight[known, S_D10]).mean()), 3) if known.any() else None,
                                   min_sightings=MIN_SIGHT)
            for pl in res["places"]:
                c = np.array(pl["pos"], np.float64)
                pl["standing_there"] = strength(np.linalg.norm(sight[:, :3] - c, axis=1) <= RADIUS, np.linalg.norm(view[:, :3] - c, axis=1) <= RADIUS,
                                                sight, view, exp)
            cs = cells(sight, view, exp, items)
            cells_out = out[:-5] + "_cells.json"
            with open(cells_out, "w", encoding="utf-8") as fh:
                json.dump(dict(map=mp, cell=[CELL, CELL, CELL_Z], min_sightings=MIN_SIGHT, all=strength(np.ones(len(sight), bool), np.ones(len(view), bool), sight, view, exp),
                               cells=cs), fh, indent=1)
            print("{}: {} sightings, {} cells with {} or more -> {}".format(mp, len(sight), len(cs), MIN_SIGHT, os.path.relpath(cells_out, ROOT).replace("\\", "/")))
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
        print("{}: {} blind shots, {} of them at his own feet ({}%); the others ({}): {} places hold {}% of their weight".format(
            mp, len(shots), res["at_own_feet"]["shots"], res["at_own_feet"]["share"], res["shots"], len(res["places"]), res["in_places_share"]))
        for j in res["at_own_feet"]["places"][:4]:
            print("  at his own feet: {}% at {} ({} units from {}), rockets {} grenades {}".format(j["share"], j["pos"], j["near"]["units"] if j["near"] else "", j["near"]["item"] if j["near"] else "",
                                                                                           j["shots"]["rockets"], j["shots"]["grenades"]))
        for pl in res["places"]:
            print("  " + says(pl))
        if a.picture:
            png = os.path.join(ROOT, "docs", "design", "places", mp + ".png")
            picture(mp, res, shots, png)
            print("  picture: " + os.path.relpath(png, ROOT).replace("\\", "/"))


if __name__ == "__main__":
    main()

"""The behaviour check (owner, 2026-10-25: "add the behavior checks as well. To make sure we're not missing anything else"):
for every save the run's checks play, and every save the weapon watch measures, his behaviour map by map beside the
pros' demos, with an alarm wherever he is far off. Self-play habits went unseen for weeks (Campgrounds' railgun never
taken since v0.4.1; Hektik leaning on the rail since v0.4.2).

    python tools/behaviour_check.py baseline [--out data/behaviour/pros_baseline.json]      # once: the pros' numbers
    python tools/behaviour_check.py check --dir <watch folder> [--all] [--dry]              # every save not yet judged
    python tools/behaviour_check.py loop --dir <watch folder> [--every 120]                 # runs check on anything new

The pros (baseline): the light demo sets of sim/demo_dataset.py --lite (data/demo_root.txt: sets_lite/<map>/*.npz; a
"TDM-" file is left out), one followed player per set, every frame of 25 ms in which he is alive. Per map: the pooled
number over all sets and, for the spread, the number of each set with enough frames (p5, p10, p50, p90, p95).
His side: the checks' files (tools/duel_eval.py --json: chk_<update>[_prev][_aim<n>]_<map>.json, the "he" row) and the
weapon watch (weapon_watch.jsonl's saves, read from the workers' own counts in ww/<update>/<map>/*.json of railgap/railsim.py
or railsim2.py).

How the measures are matched (the same detector on both sides wherever it can be):
  pick_mh, pick_ra, pick_ya   per minute ALIVE: in one life health up by 60+ in one frame = a mega, armor up 75+ = a red,
                              40..75 = a yellow (tools/pro_tables.py's detector, the same as duel_eval's mega/red/yellow
                              counts; it misses a pickup near the caps on both sides alike). The checks count per minute of
                              the game: divided here by his share of time alive (1 - deaths a minute x 2.1 s, RESPAWN_QL).
  pick_<weapon>               per minute alive: a weapon newly owned within a life (a pickup of a weapon he already holds
                              is only ammunition in a demo and is not counted on either side; a dropped weapon counts on
                              both). The checks give the three big ones together (pick_big3); the weapon watch each.
  held_<weapon>               of the frames with the enemy in view, the share with that weapon in hand. The pros' "in view"
                              is the converter's sight (field of view, line of sight, the enemy in the snapshot) after the
                              noticing delay; his is the simulator's env.visible (the same cone and line, no delay).
  choice_<band>_<weapon>      the same while he owns RL, RG and LG with ammo (a choice, not a lack), by distance (< 300,
                              300..700, > 700), share among the three: weapon watch with railsim2.py only.
  time_bare, stack150, in_view, firing_in_view, standing, lower_in_view, higher_in_view, speed, first_weapon_s, lives_per_min:
                              shares of his time alive (as duel_eval): no big weapon; health + armor 150+; the enemy in view;
                              firing while in view; under 50 u/s; in view and 48+ units lower / higher than the enemy; the
                              mean horizontal speed (the pros' from positions 25 ms apart, a jump over 1,500 u/s taken for a
                              teleport and left out); the median seconds from a spawn to the first big weapon; spawns a
                              minute alive (the pros': a stretch of play that starts bare with no armor). firing_in_view is
                              rough (his "in view" has no noticing delay, so it reads low): never more than "watch".
The pros' sets: many demos (most of Sinister's, Furious Heights' and Battleforged's 2025-26 ones) lose the followed player
at his death (one fresh spawn a demo), so their spawn phase is missing: a map's baseline is made of the sets of whole lives
(0.3 fresh spawns a minute alive or more) for the spawn-sensitive measures (pickup rates, time bare, stack 150+, first
weapon, deaths) when it has eight or more of them, else of all its sets judged leniently (judge()); the shares of frames in
view from all sets. Deaths a minute (lives_per_min) is compared only on whole-life sets.
Left out as not comparable: frags by weapon, hit rates, shots (a demo has no kill or hit events in the light sets), "lower"
and "higher" out of view (the enemy's place is unknown in a demo while he is not sent), the mega and red shares (his share
of the spawns against another network; the pros' is one half by symmetry), dropped weapons taken, time by area.

Alarms: a rate at under a quarter of the pros' (pros at 0.05 a minute or more) or over four times (his 0.2 or more), a
share outside the pros' p5..p95 by sets and 0.10 or more from their pooled number (a small share: 0.03 or more and
under 0.4 or over 2.5 times theirs), a value (speed, first weapon) outside
p5..p95 and 20% or more off. "watch" one step milder (half / twice, p10..p90 and 0.05). A map's baseline of fewer than
ten sets is marked thin. Only items and weapons on the map in its duel layout (plugins/duel_items.json) are compared.
Writes <dir>/behaviour.log (one line a save and source) and <dir>/behaviour/<update>.md (the tables).
CPU only; reads files, plays nothing.
"""
import argparse
import glob
import json
import os
import re
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")
MAPS = ["campgrounds", "hektik", "sinister", "bloodrun", "aerowalk", "lostworld", "furiousheights", "battleforged", "toxicity", "cure"]
BASE = os.path.join(ROOT, "data", "behaviour", "pros_baseline.json")
BANDS = ("close", "mid", "far")
RESPAWN_S = 2.1
FULL_SPAWNS, MIN_FULL = 0.3, 8   # a set "of whole lives": 0.3 fresh spawns (125 health, no armor, no big weapon) a minute alive or more
SPAWN_SENSITIVE = ("time_bare", "stack150", "first_weapon_s", "pick_big3", "pick_rl", "pick_rg", "pick_lg", "pick_pg", "pick_gl", "pick_sg",
                   "pick_hmg")
MIN_FR_RATE, MIN_FR_SHARE = 7200, 1200          # a set's own number counts for the spread from 3 min alive / 30 s of frames
CLASS_ITEM = {"weapon_rocketlauncher": "rl", "weapon_railgun": "rg", "weapon_lightning": "lg", "weapon_plasmagun": "pg",
              "weapon_grenadelauncher": "gl", "weapon_shotgun": "sg", "weapon_hmg": "hmg", "item_health_mega": "mh",
              "item_armor_body": "ra", "item_armor_combat": "ya"}
NAMES = {"pick_mh": "MH /min", "pick_ra": "RA /min", "pick_ya": "YA /min", "pick_big3": "RL+RG+LG /min"}


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def map_items():
    """per map: the set of item names (rl rg lg pg gl sg hmg mh ra ya) in its duel layout"""
    p = os.path.join(ROOT, "plugins", "duel_items.json")
    out = {}
    try:
        d = json.load(open(p))
    except OSError:
        return out
    for mp, ents in d.items():
        out[mp] = {CLASS_ITEM[e[0]] for e in ents if e[0] in CLASS_ITEM}
    return out


# ----------------------------------------------------------------------------------------------------------- the pros
def demo_counts(f):
    d = np.load(f)
    if "lite" not in d.files:
        return None
    q, first = d["lite"], d["first"].astype(bool)
    n = len(q)
    if n < 400:
        return None
    hp, ar = q[:, 0], q[:, 1]
    alive = hp > 0
    vis = (q[:, 4] > 0.5) & alive
    pos, epos = q[:, 5:8], q[:, 8:11]
    dist = np.linalg.norm(epos - pos, axis=1)
    hold = np.clip(q[:, 2].astype(np.int64), 0, 8)
    owns, ammo = q[:, 12:21] > 0.5, q[:, 21:30] > 0.5
    fire = (q[:, 3] > 0) & alive
    c = {}
    c["fr"] = int(alive.sum())
    c["vis"] = int(vis.sum())
    c["fire_vis"] = int((vis & fire).sum())
    c["held"] = np.bincount(hold[vis], minlength=9).astype(float)
    own3 = (owns[:, :3] & ammo[:, :3]).all(1) & vis
    c["held3"] = np.zeros((3, 9))
    np.add.at(c["held3"], (np.digitize(dist[own3], [300.0, 700.0]), hold[own3]), 1)
    same = ~first[1:] & alive[1:] & alive[:-1]
    gain = owns[1:] & ~owns[:-1] & same[:, None]
    c["gain"] = gain.sum(0).astype(float)
    dh, da = hp[1:] - hp[:-1], ar[1:] - ar[:-1]
    c["mh"] = int((same & (dh >= 60)).sum())
    c["ra"] = int((same & (da >= 75)).sum())
    c["ya"] = int((same & (da >= 40) & (da < 75)).sum())
    nbig = owns[:, :3].sum(1)
    c["bare"] = int((alive & (nbig == 0)).sum())
    c["over150"] = int((alive & (hp + ar >= 150)).sum())
    up = pos[:, 2] - epos[:, 2]
    c["lower_vis"] = int((vis & (up < -48)).sum())
    c["higher_vis"] = int((vis & (up > 48)).sum())
    sp = np.hypot(*(pos[1:, :2] - pos[:-1, :2]).T) / 0.025
    ok = same & (sp < 1500.0)
    c["sp_n"], c["sp_sum"], c["stand"] = int(ok.sum()), float(sp[ok].sum()), int((ok & (sp < 50.0)).sum())
    ft, c["lives"], c["spawns"] = [], 0, 0
    starts = np.nonzero(first & alive)[0]
    ends = list(starts[1:]) + [n]
    for t, e in zip(starts, ends):
        if nbig[t] > 0 or ar[t] > 0:
            continue
        c["lives"] += 1
        c["spawns"] += int(hp[t] >= 124)
        got = np.nonzero(nbig[t:e] > 0)[0]
        if len(got):
            ft.append(got[0] / 40.0)
    c["first"] = ft
    return c


def measures_of(c):
    """the measures (as on his side) from summed counters"""
    m = {}
    mins = max(c["fr"], 1) / 2400.0
    for k in ("mh", "ra", "ya"):
        m["pick_" + k] = c[k] / mins
    for i, w in enumerate(W[:8]):
        m["pick_" + w] = c["gain"][i] / mins
    m["pick_big3"] = float(c["gain"][:3].sum()) / mins
    m["lives_per_min"] = c["lives"] / mins
    vis = max(c["vis"], 1)
    for i, w in enumerate(W):
        m["held_" + w] = c["held"][i] / vis
    for j, b in enumerate(BANDS):
        t3 = c["held3"][j, :3].sum()
        for i, w in enumerate(W[:3]):
            m["choice_{}_{}".format(b, w)] = c["held3"][j, i] / t3 if t3 > 0 else float("nan")
    fr = max(c["fr"], 1)
    m["time_bare"], m["stack150"], m["in_view"] = c["bare"] / fr, c["over150"] / fr, c["vis"] / fr
    m["firing_in_view"] = c["fire_vis"] / vis
    m["lower_in_view"], m["higher_in_view"] = c["lower_vis"] / vis, c["higher_vis"] / vis
    m["standing"] = c["stand"] / max(c["sp_n"], 1)
    m["speed"] = c["sp_sum"] / max(c["sp_n"], 1)
    m["first_weapon_s"] = float(np.median(c["first"])) if c["first"] else float("nan")
    return m


def enough(key, c):
    if key.startswith("pick_") or key == "lives_per_min" or key in ("time_bare", "stack150", "in_view", "standing", "speed"):
        return c["fr"] >= MIN_FR_RATE
    if key.startswith("choice_"):
        j = BANDS.index(key.split("_")[1])
        return c["held3"][j, :3].sum() >= MIN_FR_SHARE
    if key == "first_weapon_s":
        return len(c["first"]) >= 5
    return c["vis"] >= MIN_FR_SHARE


def baseline(a):
    out = dict(made=time.strftime("%Y-%m-%d %H:%M"), source=os.path.join(demo_root(), "sets_lite"), maps={},
               note="per followed player; rates per minute alive; shares of frames (see tools/behaviour_check.py)")
    for mp in a.maps.split(","):
        files = [f for f in sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
                 if not os.path.basename(f).upper().startswith("TDM")]
        if a.limit:
            files = files[::max(1, len(files) // a.limit)][:a.limit]
        per = []
        for f in files:
            try:
                c = demo_counts(f)
            except Exception:                                # noqa: BLE001
                c = None
            if c is not None:
                per.append(c)
        if not per:
            continue
        full = [c for c in per if c["spawns"] / max(c["fr"] / 2400.0, 1e-6) >= FULL_SPAWNS]
        use_full = len(full) >= MIN_FULL
        rows = {}
        for basis, group in (("all", per), ("full", full if use_full else [])):
            if not group:
                continue
            tot = None
            for c in group:
                if tot is None:
                    tot = {k: (np.array(v, float).copy() if isinstance(v, np.ndarray) else (list(v) if isinstance(v, list) else v)) for k, v in c.items()}
                else:
                    for k, v in c.items():
                        tot[k] = tot[k] + v
            each = [measures_of(c) for c in group]
            for k, v in measures_of(tot).items():
                if basis == "full" and k not in SPAWN_SENSITIVE + ("lives_per_min",):
                    continue                                 # (a share of frames in view: all sets)
                vals = np.array([e[k] for e, c in zip(each, group) if enough(k, c)], float)
                vals = vals[np.isfinite(vals)]
                r = dict(pooled=None if not np.isfinite(v) else round(float(v), 4), n_sets=int(len(vals)), basis=basis,
                         minutes_alive=round(tot["fr"] / 2400.0, 1))
                if len(vals):
                    r.update({"p{}".format(p): round(float(np.percentile(vals, p)), 4) for p in (5, 10, 50, 90, 95)})
                rows[k] = r
        fr_all = sum(c["fr"] for c in per)
        out["maps"][mp] = dict(sets=len(per), sets_full_life=len(full), basis="full" if use_full else "all",
                               minutes_alive=round(fr_all / 2400.0, 1), minutes_alive_full=round(sum(c["fr"] for c in full) / 2400.0, 1),
                               measures=rows)
        print("{}: {} sets ({} of whole lives{}), {:.0f} min alive".format(mp, len(per), len(full), "" if use_full else ": too few, all sets used",
                                                                         fr_all / 2400.0), flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("wrote", a.out)


# ----------------------------------------------------------------------------------------------------------- his side
def from_check(he):
    """measures from a check file's "he" row (tools/duel_eval.py), rates turned to per minute alive"""
    m = {}
    lpm = float(he.get("lives_per_min", 0.0))
    af = max(0.5, 1.0 - max(0.0, lpm - 0.1) * RESPAWN_S / 60.0)
    if "mega_share" in he:
        m["pick_mh"] = he["mega_share"] * 60.0 / 35.0 / af
    if "red_share" in he:
        m["pick_ra"] = he["red_share"] * 60.0 / 25.0 / af
    if "yellow_per_min" in he:
        m["pick_ya"] = he["yellow_per_min"] / af
    if "weapons_per_min" in he:
        m["pick_big3"] = he["weapons_per_min"] / af
    if "lives_per_min" in he:
        m["lives_per_min"] = lpm / af
    g = (he.get("by_style") or {}).get("general") or {}
    for w, v in (g.get("in_hand_in_view") or {}).items():
        m["held_" + w] = v
    for k_his, k in (("time_bare", "time_bare"), ("stack_150_up", "stack150"), ("in_view", "in_view"), ("firing_in_view", "firing_in_view"),
                     ("standing", "standing"), ("lower_in_view", "lower_in_view"), ("higher_in_view", "higher_in_view"),
                     ("speed", "speed"), ("first_weapon_s", "first_weapon_s")):
        if k_his in he and he[k_his] is not None:
            m[k] = float(he[k_his])
    return m


def from_ww(folder):
    """measures from the weapon watch's worker files of one map (side 0 = him); None without files"""
    fs = glob.glob(os.path.join(folder, "*.json"))
    if not fs:
        return None, 0.0
    gain, held, alive = np.zeros(9), np.zeros(9), 0.0
    held3, det, have3, have_det = np.zeros((3, 9)), dict(mh=0, ra=0, ya=0), False, False
    for f in fs:
        try:
            a = json.load(open(f))
        except Exception:                                    # noqa: BLE001
            continue
        gain += np.array(a["gain"][0], float)
        held += np.array(a["held_vis"][0], float)
        alive += a["alive"][0]
        if "held3_vis" in a:
            held3 += np.array(a["held3_vis"][0], float)
            have3 = True
        if "items_det" in a:
            for k in det:
                det[k] += a["items_det"][k][0]
            have_det = True
    mins = alive / 2400.0
    if mins <= 0:
        return None, 0.0
    m = {}
    for i, w in enumerate(W[:8]):
        m["pick_" + w] = gain[i] / mins
    m["pick_big3"] = gain[:3].sum() / mins
    th = held.sum()
    if th > 0:
        for i, w in enumerate(W):
            m["held_" + w] = held[i] / th
    if have_det:
        for k, v in det.items():
            m["pick_" + k] = v / mins
    if have3:
        for j, b in enumerate(BANDS):
            t3 = held3[j, :3].sum()
            if t3 >= 200:
                for i, w in enumerate(W[:3]):
                    m["choice_{}_{}".format(b, w)] = held3[j, i] / t3
    return m, mins


# ----------------------------------------------------------------------------------------------------------- judging
def label(k):
    if k in NAMES:
        return NAMES[k]
    if k.startswith("pick_"):
        return k[5:].upper() + " /min"
    if k.startswith("held_"):
        return k[5:].upper() + " held"
    if k.startswith("choice_"):
        _, b, w = k.split("_")
        return "{} chosen {}".format(w.upper(), b)
    return k


def fmt(k, v):
    if v is None or not np.isfinite(v):
        return "-"
    if k.startswith("pick_"):
        return "{:.2f}".format(v)
    if k in ("speed",):
        return "{:.0f}".format(v)
    if k == "lives_per_min":
        return "{:.2f}".format(v)
    if k == "first_weapon_s":
        return "{:.1f}".format(v)
    return "{:.0%}".format(v)


def judge(k, his, b, basis="full"):
    """'ALARM', 'watch' or '' for his number against the pros' row b (basis 'all': the map's sets are mostly spectator demos
    that lose the followed player at his death, so the spawn phase is under-represented: a pickup rate is judged only for
    being too low, a spawn-sensitive share is at most 'watch', deaths a minute not at all)"""
    if his is None or not np.isfinite(his) or b is None or b.get("pooled") is None:
        return ""
    if basis != "full" and k == "lives_per_min":
        return ""
    f = _judge(k, his, b)
    if basis != "full" and k in SPAWN_SENSITIVE and f:
        if k.startswith("pick_"):
            return f if his < b["pooled"] else ""
        return "watch"
    return f


def _judge(k, his, b):
    pro = b["pooled"]
    if k.startswith("pick_"):
        if pro >= 0.05:
            if his < 0.25 * pro:
                return "ALARM"
            if his > 4.0 * pro and his >= 0.2:
                return "ALARM"
            if his < 0.5 * pro or (his > 2.0 * pro and his >= 0.2):
                return "watch"
        elif his >= 0.3:
            return "ALARM"
        return ""
    lo5, hi95, lo10, hi90 = b.get("p5"), b.get("p95"), b.get("p10"), b.get("p90")
    if lo5 is None or b.get("n_sets", 0) < 3:                # (no spread by sets: by the pooled number alone)
        if k in ("speed", "first_weapon_s", "lives_per_min"):
            return ""
        return "ALARM" if abs(his - pro) >= 0.25 else "watch" if abs(his - pro) >= 0.15 else ""
    if k in ("speed", "first_weapon_s", "lives_per_min"):
        rel = abs(his - pro) / max(abs(pro), 1e-6)
        if (his < lo5 or his > hi95) and rel >= 0.2:
            return "ALARM"
        if (his < lo10 or his > hi90) and rel >= 0.1:
            return "watch"
        return ""
    far = abs(his - pro) >= 0.10 or (abs(his - pro) >= 0.03 and not 0.4 <= his / max(pro, 1e-6) <= 2.5)    # (a small share: by ratio)
    if (his < lo5 or his > hi95) and far:
        return "watch" if k in ROUGH else "ALARM"
    if (his < lo10 or his > hi90) and (abs(his - pro) >= 0.05 or far):
        return "watch"
    return ""


def relevant(k, items):
    """is measure k about something on the map (its duel layout)?"""
    if items is None:
        return True
    for p in ("pick_", "held_"):
        if k.startswith(p):
            w = k[len(p):]
            if w in ("big3", "mg", "g"):
                return True
            return w in items
    return True


ROUGH = ("firing_in_view",)       # (his "in view" has no noticing delay, the pros' has: his firing share reads low by design)
KNOWN = {("campgrounds", "pick_rg"), ("campgrounds", "held_rg"), ("campgrounds", "held_lg"), ("hektik", "held_rg"), ("hektik", "held_lg"),
         ("hektik", "held_rl")}   # (the two habits known on 2026-10-25: Campgrounds' rail never taken, Hektik's mix leaning on the rail)
ORDER = (["pick_mh", "pick_ra", "pick_ya", "pick_big3"] + ["pick_" + w for w in ("rl", "rg", "lg", "pg", "gl", "sg", "hmg")]
         + ["held_" + w for w in ("rl", "rg", "lg", "pg", "gl", "sg", "hmg", "mg", "g")]
         + ["choice_{}_{}".format(b, w) for b in BANDS for w in ("rl", "rg", "lg")]
         + ["time_bare", "stack150", "in_view", "firing_in_view", "standing", "lower_in_view", "higher_in_view", "speed", "first_weapon_s",
            "lives_per_min"])


def table(src, per_map, base, items):
    """markdown table and the alarm strings for one source: per_map = {map: (measures, note)}"""
    lines, alarms, watches = [], [], []
    for mp in MAPS:
        if mp not in per_map:
            continue
        m, note = per_map[mp]
        bm = (base.get("maps") or {}).get(mp)
        thin = bm is not None and bm["sets"] < 10
        basis = (bm or {}).get("basis", "full")
        head = "### {} ({}; pros: {} sets, {} min alive; spawn-sensitive measures from the {} sets of whole lives, {} min{}{})".format(
            mp, note, bm["sets"] if bm else 0, bm["minutes_alive"] if bm else 0, bm.get("sets_full_life", 0) if bm else 0,
            bm.get("minutes_alive_full", 0) if bm else 0, ", THIN" if thin else "",
            "" if basis == "full" else "; too few whole-life sets: spawn phase under-represented, judged leniently")
        lines += ["", head, "", "| measure | him | pros (pooled) | pros p5..p95 by set | sets | flag |", "|---|---|---|---|---|---|"]
        for k in ORDER:
            if k not in m or not relevant(k, items.get(mp)):
                continue
            b = (bm or {}).get("measures", {}).get(k) if bm else None
            fl = judge(k, m[k], b, b.get("basis", "all") if (b and k in SPAWN_SENSITIVE + ("lives_per_min",)) else "full")
            rng = "{}..{}".format(fmt(k, b.get("p5")), fmt(k, b.get("p95"))) if b and b.get("p5") is not None else "-"
            lines.append("| {} | {} | {} | {} | {} | {} |".format(label(k), fmt(k, m[k]), fmt(k, b["pooled"]) if b and b.get("pooled") is not None else "-",
                                                                 rng, b["n_sets"] if b else 0, fl))
            if fl:
                s = "{} {} {} (pros {}{}){}".format(mp, label(k), fmt(k, m[k]), fmt(k, b["pooled"]), ", thin" if thin else "",
                                                     " [known]" if (mp, k) in KNOWN else "")
                (alarms if fl == "ALARM" else watches).append(s)
    return lines, alarms, watches


# ----------------------------------------------------------------------------------------------------------- his saves
CHK = re.compile(r"chk_(\d+)(_prev)?(_aim\d+)?_([a-z0-9]+)\.json$")


def check_sets(d):
    """{(update, kind): {map: path}} of the check files in folder d (kind: 'prev', 'ctrl', 'prev_aim3', ...)"""
    out = {}
    for p in glob.glob(os.path.join(d, "chk_*.json")):
        mt = CHK.search(os.path.basename(p))
        if not mt:
            continue
        kind = ("prev" if mt.group(2) else "ctrl") + (mt.group(3) or "")
        out.setdefault((int(mt.group(1)), kind), {})[mt.group(4)] = p
    return out


def ww_saves(d):
    p = os.path.join(d, "weapon_watch.jsonl")
    out = []
    try:
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            if not r.get("skipped"):
                out.append(int(r["update"]))
    except OSError:
        pass
    return out


def opp_name(paths):
    for p in paths.values():
        try:
            o = json.load(open(p)).get("opp", "")
            return os.path.basename(str(o)).replace("policy:", "")
        except Exception:                                    # noqa: BLE001
            continue
    return "?"


def run_one(d, key, base, items, write_log=True):
    """judge one save and source: key = ('chk', update, kind) or ('ww', update); returns the log line"""
    if key[0] == "chk":
        _, upd, kind = key
        paths = check_sets(d).get((upd, kind), {})
        per = {}
        for mp, p in paths.items():
            try:
                he = json.load(open(p))["maps"][mp]["he"]
            except Exception:                                # noqa: BLE001
                continue
            per[mp] = (from_check(he), "check vs {}".format(kind))
        src = "check {} (vs {}, {} maps)".format(kind, opp_name(paths), len(per))
    else:
        _, upd = key
        per = {}
        for mp in MAPS:
            m, mins = from_ww(os.path.join(d, "ww", str(upd), mp))
            if m:
                per[mp] = (m, "weapon watch, {:.0f} min alive".format(mins))
        src = "weapon watch ({} maps)".format(len(per))
    lines, alarms, watches = table(src, per, base, items)
    tag = "u{} {}".format(upd, "chk-" + key[2] if key[0] == "chk" else "ww")
    new_ = [x for x in alarms if not x.endswith("[known]")]
    line = "{} {}: {}".format(time.strftime("%m-%d %H:%M"), tag, "{} ALARM ({} new): {}".format(len(alarms), len(new_), "; ".join(alarms))
                              if alarms else "no alarm")
    if watches:
        line += " | watch: " + "; ".join(watches)
    od = os.path.join(d, "behaviour")
    os.makedirs(od, exist_ok=True)
    md = os.path.join(od, "{}.md".format(upd))
    sect = ["", "## {} (written {})".format(src, time.strftime("%Y-%m-%d %H:%M")), "",
            "Alarms: " + ("; ".join(alarms) if alarms else "none"), "", "Watch: " + ("; ".join(watches) if watches else "none")] + lines
    secs = {}
    if os.path.exists(md):                                    # (one file a save: keep the other sources' sections)
        txt = open(md, encoding="utf-8").read()
        for part in re.split(r"\n(?=## )", txt):
            if part.startswith("## "):
                secs[part.split(" (written")[0]] = part
    secs["## " + src] = "\n".join(sect).strip("\n")
    head = "# Behaviour check, save {} ({})\n\nHim beside the pros' demos, per map (tools/behaviour_check.py; pros: {}).\n".format(
        upd, os.path.basename(os.path.abspath(d)), BASE_NOTE)
    with open(md, "w", encoding="utf-8") as f:
        f.write(head + "\n" + "\n\n".join(secs[k] for k in sorted(secs)) + "\n")
    if write_log:
        with open(os.path.join(d, "behaviour.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return line


BASE_NOTE = "data/behaviour/pros_baseline.json"


def pending(d, state, final=False):
    """the saves and sources not yet judged: a check set once all ten maps are there (or a later update's set has begun)"""
    sets = check_sets(d)
    keys = []
    ups = sorted({u for u, _ in sets})
    for (u, kind), paths in sorted(sets.items()):
        later = any(u2 > u for u2 in ups)
        if len(paths) >= len(MAPS) or later or final:
            keys.append(("chk", u, kind))
    keys += [("ww", u) for u in ww_saves(d)]
    return [k for k in keys if "|".join(map(str, k)) not in state]


def load_state(d):
    p = os.path.join(d, "behaviour", "state.json")
    try:
        return set(json.load(open(p)))
    except Exception:                                        # noqa: BLE001
        return set()


def save_state(d, s):
    os.makedirs(os.path.join(d, "behaviour"), exist_ok=True)
    with open(os.path.join(d, "behaviour", "state.json"), "w") as f:
        json.dump(sorted(s), f)


def check(a):
    base = json.load(open(a.base))
    items = map_items()
    state = set() if a.all else load_state(a.dir)
    for k in sorted(pending(a.dir, state, final=a.all), key=lambda k: (k[1], k[0])):
        print(run_one(a.dir, k, base, items, write_log=not a.dry), flush=True)
        state.add("|".join(map(str, k)))
    if not a.dry:
        save_state(a.dir, state)


def loop(a):
    base = json.load(open(a.base))
    items = map_items()
    with open(os.path.join(a.dir, "behaviour.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M") + " loop started\n")
    while True:
        try:
            state = load_state(a.dir)
            for k in sorted(pending(a.dir, state), key=lambda k: (k[1], k[0])):
                run_one(a.dir, k, base, items)
                state.add("|".join(map(str, k)))
                save_state(a.dir, state)
        except Exception as e:                               # noqa: BLE001
            with open(os.path.join(a.dir, "behaviour.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%m-%d %H:%M") + " error: {!r}\n".format(e))
        time.sleep(a.every)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--maps", default=",".join(MAPS))
    b.add_argument("--limit", type=int, default=0)
    b.add_argument("--out", default=BASE)
    for nm in ("check", "loop"):
        c = sub.add_parser(nm)
        c.add_argument("--dir", required=True, help="the run's watch folder (check files, weapon_watch.jsonl, ww/)")
        c.add_argument("--base", default=BASE)
        if nm == "check":
            c.add_argument("--all", action="store_true", help="every save there again, judged or not (a line each in the log)")
            c.add_argument("--dry", action="store_true", help="print the lines only (the tables are written; no log line, no state)")
        else:
            c.add_argument("--every", type=float, default=120.0)
    a = ap.parse_args()
    {"baseline": baseline, "check": check, "loop": loop}[a.cmd](a)


if __name__ == "__main__":
    main()

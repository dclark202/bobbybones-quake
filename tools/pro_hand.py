"""The pros' weapon in hand with nobody in view, as the table the simulator's HAND_TEACH lesson reads (sim/duel_env.py).

    python tools/pro_hand.py                  the counts kept per demo by tools/pro_yardsticks.py -> sim/pro_hand.json; the table printed
    python tools/pro_hand.py --show           the table of sim/pro_hand.json as it stands, nothing read from the demos' counts
    python tools/pro_hand.py --out <file>     written there (default sim/pro_hand.json beside this file's folder)
    python tools/pro_hand.py --min-minutes 30 the least minutes a map's own row needs (default 30)

What it is. docs/pro_yardsticks2.json, maps -> <map> -> weapon_in_hand, has the pros' time with no enemy in view by the
weapon in hand in five classes (rail, lightning, rockets, machine gun, other). The lesson wants every weapon by itself (he
is never told of a weapon he lacks, and "other" is three weapons), so this tool sums the same counts where they are
still whole: tools/pro_yardsticks.py keeps them per demo in <demo root>/yardsticks/<map>/<demo>.json (tally -> quietw ->
"travelling:seen:<band>" and "holding:seen:<band>": seconds by weapon). The five classes summed again here are set beside
docs/pro_yardsticks2.json for every map, state and band, and the largest difference is printed (--strict: more than 0.11
of a point of a share or 0.11 of a minute stops it): the table is that file's numbers, finer.

The definitions are tools/pro_yardsticks.py's (quiet_weapon, holds, see):
  nobody in view   alive and the enemy not inside his sight cone (55 degrees) under 4000 units with a clear line
  travelling       200 units a second or more over the ground, and not in a hold
  holding          a hold: 2 s or more within 150 units of where the stretch began, alive, no enemy in view, rockets,
                   lightning or rail in hand all the while (so a hold's row names those three and nothing else)
  the bands        how long ago the enemy was in view: under 5 s, 5 to 15 s, over 15 s, not yet in this stretch of the demo

The table (sim/pro_hand.json): maps -> "all" (the ten maps together) and each of the ten; a map has
  minutes  [state][band]            the pros' minutes the row rests on (the map's own, also where the row is the fallback)
  share    [state][band][weapon]    the share of that time with each weapon in hand, summing to 1 (weapons: the simulator's
                                    order without the gauntlet, which has no ammunition and 1.3% of the time: left out)
  own      [state][band]            true: the map's own row; false: the map has under --min-minutes of it and the row is
                                    "all"'s (the ten maps together)
A map that is not in the file takes "all" in the simulator.

Read with care: the shares are of the pros' TIME and not by what they owned at that moment. A pro with only the machine
gun counts toward the machine gun's share; the simulator renormalises a row over what he owns, which gives the small
weapons a little more than a pro who owns the same would give them.

QLBOT_ROOT: the repo, when this file is run from a copy (docs/pro_yardsticks2.json and data/demo_root.txt are read there)."""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
WEAPONS = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")           # the simulator's order (duel_env.WEAPONS)
NAMED = WEAPONS[:8]                                                        # ... without the gauntlet
STATES = ("travelling", "holding")
BANDS = ("seen under 5 s ago", "5 to 15 s ago", "over 15 s ago", "not seen yet in this stretch")
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")
CLASSES = (("rail_share", ("rg",)), ("lightning_share", ("lg",)), ("rockets_share", ("rl",)), ("machine_gun_share", ("mg",)),
           ("other_share", ("sg", "gl", "pg", "hmg", "g")))


def low_priority():
    """below normal, so that a training run on the same PC keeps its share (the handle's type set: the default cuts it on 64 bits)"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:                                                      # noqa: BLE001 (not Windows)
        pass


def demo_root():
    f = os.path.join(ROOT, "data", "demo_root.txt")
    assert os.path.exists(f), "no data/demo_root.txt under {} (QLBOT_ROOT: the repo)".format(ROOT)
    return open(f, encoding="utf-8").read().strip()


def count_map(mp):
    """a map's seconds by [state][band][weapon] (all nine), the demos counted and the versions of their counts"""
    sec = [[[0.0] * len(WEAPONS) for _ in BANDS] for _ in STATES]
    used, versions = 0, {}
    for f in sorted(glob.glob(os.path.join(demo_root(), "yardsticks", mp, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
        except Exception:                                                  # noqa: BLE001 (a file being written)
            continue
        if "tally" not in r:
            continue
        used += 1
        versions[r.get("version")] = versions.get(r.get("version"), 0) + 1
        q = r["tally"].get("quietw") or {}
        for s, st in enumerate(STATES):
            for b in range(len(BANDS)):
                for w, v in (q.get("{}:seen:{}".format(st, b)) or {}).items():
                    sec[s][b][WEAPONS.index(w)] += float(v)
    return sec, used, versions


def add(a, b):
    return [[[x + y for x, y in zip(ra, rb)] for ra, rb in zip(sa, sb)] for sa, sb in zip(a, b)]


def shares(row):
    """a row's seconds by weapon -> minutes (all nine weapons, as the yardsticks count them) and the shares of the named eight"""
    tot = sum(row[:len(NAMED)])
    return sum(row) / 60.0, ([round(x / tot, 4) for x in row[:len(NAMED)]] if tot > 0 else [0.0] * len(NAMED))


def five(row):
    """a row's seconds -> the five classes of docs/pro_yardsticks2.json, in points of a share"""
    tot = sum(row)
    return {k: (100.0 * sum(row[WEAPONS.index(w)] for w in ws) / tot if tot else 0.0) for k, ws in CLASSES}


def show(tab):
    ws = tab["weapons"]
    print("the pros' weapon in hand with nobody in view, % of their time (a row with under {:g} minutes of a map's own is the ten maps' row: marked *)".format(
        tab["min_minutes"]))
    print("{:15s} {:11s} {:29s} {:>8s}  ".format("map", "state", "the enemy was seen", "minutes") + " ".join("{:>5s}".format(w) for w in ws))
    for mp, d in tab["maps"].items():
        for s, st in enumerate(tab["states"]):
            for b, bn in enumerate(tab["bands"]):
                own = d.get("own", [[True] * len(tab["bands"])] * len(tab["states"]))[s][b]
                print("{:15s} {:11s} {:29s} {:8.1f}{} ".format(mp, st, bn, d["minutes"][s][b], " " if own else "*")
                      + " ".join("{:5.1f}".format(100.0 * x) for x in d["share"][s][b]))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "sim", "pro_hand.json"))
    ap.add_argument("--min-minutes", type=float, default=30.0, help="a map's own row needs this many of the pros' minutes; under it the row is the ten maps'")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--strict", action="store_true", help="stop when the five classes summed here are not docs/pro_yardsticks2.json's")
    a = ap.parse_args()
    if a.show:
        return show(json.load(open(a.out, encoding="utf-8")))
    low_priority()
    yard = json.load(open(os.path.join(ROOT, "docs", "pro_yardsticks2.json"), encoding="utf-8"))["maps"]
    per, demos, vers = {}, {}, {}
    for mp in MAPS:
        per[mp], demos[mp], v = count_map(mp)
        for k, n in v.items():
            vers[k] = vers.get(k, 0) + n
        print("{}: {} demos' counts read".format(mp, demos[mp]), file=sys.stderr, flush=True)
    assert sum(demos.values()) > 0, "no counts under {}/yardsticks (tools/pro_yardsticks.py makes them)".format(demo_root())
    allm = per[MAPS[0]]
    for mp in MAPS[1:]:
        allm = add(allm, per[mp])
    # ---- the five classes beside docs/pro_yardsticks2.json
    worst_s, worst_m, where, n_cmp = 0.0, 0.0, "", 0
    for mp, sec in [("all_ten", allm)] + [(m, per[m]) for m in MAPS]:
        y = (yard.get(mp) or {}).get("weapon_in_hand") or {}
        for s, st in enumerate(STATES):
            for b, bn in enumerate(BANDS):
                c = (y.get(st) or {}).get(bn)
                if not c or not c.get("minutes"):
                    continue
                mine = five(sec[s][b])
                ds = max(abs(mine[k] - c[k]) for k, _ in CLASSES)
                dm = abs(sum(sec[s][b]) / 60.0 - c["minutes"])
                n_cmp += 1
                if ds > worst_s:
                    worst_s, where = ds, "{} {} {}".format(mp, st, bn)
                worst_m = max(worst_m, dm)
    said = ("the five classes summed from the demos' counts beside docs/pro_yardsticks2.json: {} rows, the largest difference {:.2f} of a point of a share "
            "({}), {:.2f} of a minute; demos {} (the file's all_ten: {})".format(n_cmp, worst_s, where or "-", worst_m, sum(demos.values()),
                                                                                (yard.get("all_ten") or {}).get("demos")))
    print(said, file=sys.stderr, flush=True)
    if a.strict and (worst_s > 0.11 or worst_m > 0.11 or n_cmp == 0):
        sys.exit("STOPPED (--strict): the counts are not the ones docs/pro_yardsticks2.json was written from")
    # ---- the table
    g_all = sum(sum(r[WEAPONS.index("g")] for r in st_) for st_ in allm) / max(1e-9, sum(sum(sum(r) for r in st_) for st_ in allm))
    out_maps = {}
    am, ash = zip(*[zip(*[shares(allm[s][b]) for b in range(len(BANDS))]) for s in range(len(STATES))])
    out_maps["all"] = dict(demos=sum(demos.values()), minutes=[[round(x, 1) for x in r] for r in am], share=[list(r) for r in ash])
    for mp in MAPS:
        mm, sh, own = [], [], []
        for s in range(len(STATES)):
            mm.append([]), sh.append([]), own.append([])
            for b in range(len(BANDS)):
                m_, s_ = shares(per[mp][s][b])
                ok = m_ >= a.min_minutes
                mm[s].append(round(m_, 1)), own[s].append(bool(ok)), sh[s].append(s_ if ok else out_maps["all"]["share"][s][b])
        out_maps[mp] = dict(demos=demos[mp], minutes=mm, share=sh, own=own)
    tab = dict(about="the pros' weapon in hand with nobody in view (tools/pro_hand.py; the definitions are tools/pro_yardsticks.py's): share[state][band][weapon] "
                     "of their time, a row summing to 1; a map's row with under min_minutes of its own is the ten maps' row (own false); the gauntlet is left "
                     "out ({:.3%} of the time); the shares are not by what the pro owned".format(g_all),
               weapons=list(NAMED), states=list(STATES), bands=list(BANDS), min_minutes=a.min_minutes,
               source=dict(counts="<demo root>/yardsticks/<map>/<demo>.json: tally.quietw (tools/pro_yardsticks.py)", versions={str(k): n for k, n in vers.items()},
                           check=said),
               maps=out_maps)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(tab, f, indent=1)
        f.write("\n")
    show(tab)
    print("wrote {} ({} maps and 'all'; {} rows of {} are a map's own)".format(a.out, len(MAPS), sum(sum(sum(r) for r in d["own"]) for m, d in out_maps.items() if m != "all"),
                                                                             len(MAPS) * len(STATES) * len(BANDS)))


if __name__ == "__main__":
    main()

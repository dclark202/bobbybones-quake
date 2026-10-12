"""The second and third sets of ways of a map (WAYS, sim/ways.py), measured: what became of the pros' ways, and for every
target, from each spawn point and each other target, how often the second and the third way differ from the shortest
and how much longer they are; whether every set arrives.

    python tools/ways_measure.py <map>[,<map> ...] [--table 1] [--json out.json]      (Anaconda Python)

The simulator's switches are the environment's (set the run's: WALK_FIX, LAVA, PRO_WAYS, NEAREST, TARGETS, ...); WAYS is
set here. The ways are the ones his legs were measured to make (sim/pro_ways_legs/<map>.json, tools/ways_check.py);
WAY_UNTESTED=1: every way the walking map can follow. --table n: the table of target n (1 = the first route goal), start by start. "differs": more than a quarter of
the way's seconds farther than 128 units from the shortest way from the same start (sim/ways.py, WAY_DIFF, WAY_FAR).
QLBOT_ROOT: the repo, when this file is run from a copy. WAYS_ENV: the simulator's module (default duel_env_ffa)."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
os.environ["WAYS"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sim"))
import importlib  # noqa: E402

import numpy as np  # noqa: E402

E = importlib.import_module(os.environ.get("WAYS_ENV") or "duel_env_ffa")
import ways as WY  # noqa: E402


def one(mp, table):
    t0 = time.time()
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=2, seed=1, loadout="mg",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    t_env = time.time() - t0
    X = env.way_field
    assert X is not None, mp + ": no walking map"
    t0 = time.time()
    G = env.set_ways()                                        # (the same work once more: what a simulator's start pays for it)
    plans = env.way_plan
    t_build = time.time() - t0
    nI, n = len(env.route_goal), len(X.nodes)
    names = ["{} {}".format(g + 1, lab) for g, lab in enumerate(env.route_goal)] + ["{} H{}".format(nI + j + 1, j + 1) for j in range(len(X.goals) - nI)]
    fate = {}
    for rep in env.way_report:
        for r in rep:
            for w in r["ways"]:
                fate[w["what"]] = fate.get(w["what"], 0) + 1
    gn = [int(X.locate(p[None])[0]) for p in X.goals]
    sp = [int(x) for x in X.locate(env.spawns)]
    live = np.nonzero(~X.dead)[0]
    out = dict(map=mp, points=n, links=int(len(G.ec)), targets=len(X.goals), items=nI, places=len(X.goals) - nI, spawn_points=len(sp),
               measured_on_his_legs=env.way_legs is not None, untested_ways_taken=bool(E.WAY_UNTESTED),
               the_pros_ways=fate, seconds_to_build=round(t_build, 2), seconds_simulator_start=round(t_env, 2), circles_opened=int(X.way_fixed), rows=[])
    print("\n== {}: {} points, {} links, {} targets ({} items, {} places), {} spawn points | {} | the pros' ways into them: {} | built in {:.2f} s "
          "(the simulator's start: {:.1f} s) | circles opened: {}".format(
              mp, n, len(G.ec), len(X.goals), nI, len(X.goals) - nI, len(sp),
              ("his legs' file is there" if env.way_legs is not None else "NO FILE OF WHAT HIS LEGS MAKE") + (", untested ways taken too" if E.WAY_UNTESTED else ""),
              ", ".join("{} {}".format(v, k) for k, v in sorted(fate.items())), t_build, t_env, X.way_fixed))
    print("   {:9s} {:>6s} | {}".format("target", "starts", " | ".join("{:^58s}".format("the {} way: differs, longer s (median, 90%, worst), worst ratio, arrive".format(w)) for w in ("2nd", "3rd"))))
    tot = [dict(starts=0, differ=0, longer=[], ratio=0.0, arrive=0, all_differ=0, all=0, all_arrive=0) for _ in range(2)]
    for g in range(len(X.goals)):
        starts = sorted(set(sp + [gn[h] for h in range(len(X.goals)) if h != g]))
        ms = WY.measure(n, X.T, X.wT, X.wnext, X.wdiff, g, starts)
        ma = WY.measure(n, X.T, X.wT, X.wnext, X.wdiff, g, live)
        cells = []
        for k, m in enumerate(ms):
            st = np.asarray([s for s in starts if X.T[g, s] < 1e8], np.int64)
            d = X.wdiff[k, g, st]
            tot[k]["starts"] += m["starts"]
            tot[k]["differ"] += m["differ"]
            tot[k]["longer"] += [float(x) for x in (X.wT[k, g, st] - X.T[g, st])[d]]
            tot[k]["ratio"] = max(tot[k]["ratio"], m["ratio_worst"] or 0.0)
            tot[k]["arrive"] += m["arrive"]
            tot[k]["all_differ"] += ma[k]["differ"]
            tot[k]["all"] += ma[k]["starts"]
            tot[k]["all_arrive"] += ma[k]["arrive"]
            cells.append("{:3d} ({:4.0%})  {:>5s} {:>5s} {:>5s}   x{:.2f}   {:3d}/{:<3d}   all points {:4d}/{:<4d}".format(
                m["differ"], m["differ"] / max(1, m["starts"]), "-" if m["longer_median"] is None else "{:.1f}".format(m["longer_median"]),
                "-" if m["longer_90"] is None else "{:.1f}".format(m["longer_90"]), "{:.1f}".format(m["longer_worst"] or 0.0), m["ratio_worst"] or 1.0,
                m["arrive"], m["starts"], ma[k]["arrive"], ma[k]["starts"]))
        out["rows"].append(dict(target=names[g], pros_ways=[len(plans[g][0]), len(plans[g][1])], second=ms[0], third=ms[1],
                                all_points=[dict(starts=x["starts"], differ=x["differ"], arrive=x["arrive"]) for x in ma]))
        print("   {:9s} {:6d} | {}".format(names[g], ms[0]["starts"], " | ".join(cells)))
    for k, t in enumerate(tot):
        lg = np.asarray(t["longer"])
        out["second" if k == 0 else "third"] = dict(
            starts=t["starts"], differ=t["differ"], differ_share=round(t["differ"] / max(1, t["starts"]), 4),
            longer_median=round(float(np.median(lg)), 2) if len(lg) else None, longer_90=round(float(np.percentile(lg, 90)), 2) if len(lg) else None,
            longer_worst=round(float(lg.max()), 2) if len(lg) else None, ratio_worst=round(t["ratio"], 3), arrive=t["arrive"],
            all_points=t["all"], all_points_differ_share=round(t["all_differ"] / max(1, t["all"]), 4), all_points_arrive=t["all_arrive"])
        print("   the {} way, all targets: from {} starts (spawn points and the other targets) {} differ ({:.1%}); where it differs it is longer by {} s "
              "(median), {} (90%), {} (worst); worst ratio x{:.2f}; arrive {}/{}; from every point of the map: {:.1%} differ, arrive {}/{}".format(
                  ("2nd", "3rd")[k], t["starts"], t["differ"], t["differ"] / max(1, t["starts"]),
                  "-" if not len(lg) else "{:.1f}".format(float(np.median(lg))), "-" if not len(lg) else "{:.1f}".format(float(np.percentile(lg, 90))),
                  "-" if not len(lg) else "{:.1f}".format(float(lg.max())), t["ratio"], t["arrive"], t["starts"],
                  t["all_differ"] / max(1, t["all"]), t["all_arrive"], t["all"]))
    if table:
        g = table - 1
        print("   the table of target {} ({} at {}): seconds from each start by the shortest, the second and the third way (*: differs)".format(
            names[g], "an item" if g < nI else "a place", [int(x) for x in X.goals[g]]))
        rows = [("spawn {}".format(i + 1), s) for i, s in enumerate(sp)] + [(names[h], gn[h]) for h in range(len(X.goals)) if h != g]
        tab = []
        for nm, s in rows:
            if not X.T[g, s] < 1e8:
                print("      {:10s} no way".format(nm))
                continue
            c = ["{:5.1f}".format(float(X.T[g, s]))] + ["{:5.1f}{}".format(float(X.wT[k, g, s]), "*" if X.wdiff[k, g, s] else " ") for k in range(2)]
            tab.append(dict(start=nm, shortest=round(float(X.T[g, s]), 2), second=round(float(X.wT[0, g, s]), 2), third=round(float(X.wT[1, g, s]), 2),
                            second_differs=bool(X.wdiff[0, g, s]), third_differs=bool(X.wdiff[1, g, s])))
            print("      {:10s} {}".format(nm, "  ".join(c)))
        out["table"] = dict(target=names[g], rows=tab)
        out["report_of_that_target"] = env.way_report[g]
        for r in env.way_report[g]:
            print("      the pros from {} (shortest {:.1f} s): {}".format(r["origin"], r["shortest_s"], "; ".join(
                "{} trips, {} units from the shortest: {}".format(w["trips"], w["apart"], w["what"]) for w in r["ways"])))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    table, js = 0, None
    if "--table" in args:
        i = args.index("--table")
        table = int(args[i + 1])
        del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json")
        js = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    maps = args[0].split(",")
    if len(maps) == 1:
        res = [one(maps[0], table)]
    else:                                                    # a map a process, one after the other: the simulator's library keeps a
        import subprocess                                    # map's solid pieces, and a second map in one process is measured wrong
        import tempfile                                      # (2026-10-12: the ninth map of one process had its items elsewhere)
        res = []
        for m in maps:
            tmp = os.path.join(tempfile.gettempdir(), "ways_measure_{}_{}.json".format(os.getpid(), m))
            r = subprocess.run([sys.executable, os.path.abspath(__file__), m, "--json", tmp] + (["--table", str(table)] if table else []),
                               creationflags=0x4000 if os.name == "nt" else 0)
            if r.returncode == 0 and os.path.exists(tmp):
                with open(tmp, encoding="utf-8") as f:
                    res += json.load(f)
                os.remove(tmp)
            else:
                print(m, "FAILED", r.returncode, flush=True)
    if js:
        with open(js, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)

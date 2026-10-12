"""What his legs make of a map's second and third ways (WAYS, sim/ways.py): writes sim/pro_ways_legs/<map>.json, the list
the simulator takes its ways from. A way of the pros that the walking map can follow is not yet a way his legs make: the
movement network misses some of the walking map's drops and jumps, and a miss can send him round for good.

    python tools/ways_check.py <map>[,<map> ...] [--tries 6] [--need 5] [--out <folder>]      (Anaconda Python)

The simulator's switches are the environment's (set the run's: WALK_FIX, LAVA, PRO_WAYS, NEAREST, ..., LEGS=1 and
LEGS_NET, his legs' network); WAYS=1, TARGETS=1 and WAY_UNTESTED=1 are set here. A map a process (several maps: this
tool starts itself once a map, one after the other).

  1. Every way of the plan (a pros' way that the walking map can follow, by target and origin) is tried on his legs from
     its origin: --tries players with that target as their intention, that way, their legs on, nothing else pressed;
     made = --need of them stand at the target within max(6, 1.25 x the way's seconds + 3) seconds. A way not made is
     taken out, the plan is made anew (the next of the pros' ways may take its place) and the new ways are tried, until
     every way of the plan has been tried.
  2. With the ways that are left: from every spawn point and every other item from which one of the sets changes the way
     to a target, 4 tries (in games his trips begin at an item more often than at a spawn point); where at most two
     arrive and the shortest way from the same start does better by two or more (4 tries), the ways of that set that
     his way from there runs along are taken out too, and step 2 is done again (four times at most).
Make the files again when his legs' network or the walking map changes. QLBOT_ROOT: the repo, when this file is run from
a copy. WAYS_ENV: the simulator's module (default duel_env_ffa)."""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
SEATS, SP_TRIES = 64, 4


def one(mp, tries, need, out_dir):
    os.environ.update(WAYS="1", TARGETS="1", WAY_UNTESTED="1", LEGS="1")
    assert os.environ.get("LEGS_NET") and os.path.exists(os.environ["LEGS_NET"]), "LEGS_NET: his legs' network"
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sim"))
    import importlib
    import numpy as np
    E = importlib.import_module(os.environ.get("WAYS_ENV") or "duel_env_ffa")
    import ways as WY
    t_start = time.time()
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=SEATS, seed=7, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    env.arena_stack, env.arena_sets, env.loadout_p = False, [(E.MG,)], (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = env.close_p = env.item_run_p = env.jump_run_p = env.bot_p = env.runner_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.round_t[:] = 1e9
    n = env.n
    REST = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    REST[:, 0], REST[:, 1] = 1, 1
    REST[:, 3], REST[:, 4] = int(np.abs(E.TURN).argmin()), int(np.abs(E.PITCH).argmin())
    env.step(REST.copy())
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    env.script[:] = 0
    assert env.teacher is not None and env.way_field is not None, mp + ": no legs or no walking map"
    G_ = len(env._others_arr()[0]) + 1
    ev = np.arange(0, n, G_)[:SEATS]                          # the travellers: the first seat of every group
    X = env.way_field
    nI = len(env.route_goal)
    names = ["{} {}".format(g + 1, lab) for g, lab in enumerate(env.route_goal)] + ["{} H{}".format(nI + j + 1, j + 1) for j in range(len(X.goals) - nI)]
    W = WY.load(mp)
    items = {k: np.asarray(v, np.float32) for k, v in (W or {}).get("items", {}).items()}
    force = np.full(n, -1, np.int64)                         # the row of the walking map a traveller is sent to (one of two items of a kind, too)
    plain = env._trip_goal

    def trip_goal(intent, node, R=None, who=None):
        gi = plain(intent, node, R, who)
        idx = who if who is not None else (np.arange(n) if len(gi) == n else None)
        if idx is not None:
            f = force[np.asarray(idx)]
            gi = np.where(f >= 0, f, gi)
        return gi
    env._trip_goal = trip_goal
    rng = np.random.default_rng(5)

    def run(jobs):
        """jobs: [(row, way 0..2, start position or spawn point number)] -> per job (arrived, seconds, the way's seconds by the set)"""
        res = []
        for b0 in range(0, len(jobs), len(ev)):
            batch = jobs[b0:b0 + len(ev)]
            force[:] = -1
            act = REST.copy()
            goal, lim, tset = np.zeros((len(batch), 3), np.float32), np.zeros(len(batch)), np.zeros(len(batch))
            place = np.zeros(len(batch), bool)
            for q, (g, way, start) in enumerate(batch):
                i = int(ev[q])
                env.state = env.w.state()
                if np.ndim(start) == 0:
                    env._spawn_at(i, int(start))
                else:
                    yaw = float(rng.uniform(-180, 180))
                    env.w.reset(i, (float(start[0]), float(start[1]), float(start[2]) + 9.0), (0, 0, 0), yaw)
                    env._fresh(i, yaw)
                env.hp[i], env.armor[i] = 100.0, 0.0
                force[i] = g
                act[i, E.INTENT_HEAD] = E.INTENTS.index(env.route_goal[g]) if g < nI else E.HOLD_INTENT + (g - nI)
                act[i, E.LEGS_HEAD], act[i, E.WAY_HEAD] = 1, way
                goal[q], place[q] = X.goals[g], g >= nI
            for i in ev[len(batch):]:                        # (the seats with nothing to do: where they are, at rest)
                force[i] = -1
            env.state = env.w.state()
            env.item_up[:], env.item_t[:] = True, 0.0
            env.bel_t[:] = 99.0
            sel = ev[:len(batch)]
            node = X.locate(env.state[sel, :3])
            for q, (g, way, start) in enumerate(batch):
                tset[q] = float(X.T[g, node[q]] if way == 0 else X.wT[way - 1, g, node[q]])
            lim = np.maximum(6.0, 1.25 * np.minimum(tset, 60.0) + 3.0)
            arr = np.full(len(batch), -1.0)
            rx, rz = np.where(place, E.HOLD_R, 40.0), np.where(place, E.HOLD_Z, 60.0)
            for t in range(int(lim.max() / E.DT) + 1):
                env.step(act.copy())
                d = env.state[sel, :3] - goal
                here = (arr < 0) & (np.hypot(d[:, 0], d[:, 1]) < rx) & (np.abs(d[:, 2]) < rz) & ((t + 1) * E.DT <= lim)
                arr[here] = (t + 1) * E.DT
                if ((arr >= 0) | ((t + 1) * E.DT > lim)).all():
                    break
            res += [(bool(a_ >= 0), float(a_), float(s_)) for a_, s_ in zip(arr, tset)]
        return res

    legs, rows2 = {}, []

    def origins():
        """1. every way of the plan that has not been tried, from its origin -> how many were tried"""
        n_new = 0
        for rnd in range(6):
            env.set_ways(legs=legs, untested=True)
            todo = [(g, int(w["what"][4:]) - 2, r["origin"], w) for g, rep in enumerate(env.way_report) for r in rep for w in r["ways"]
                    if w["what"].startswith("way ") and w["key"] not in legs]
            if not todo:
                break
            n_new += len(todo)
            res = run([(g, k + 1, items[org]) for g, k, org, w in todo for _ in range(tries)])
            for j, (g, k, org, w) in enumerate(todo):
                rr = res[j * tries:(j + 1) * tries]
                got = sum(r_[0] for r_ in rr)
                legs[w["key"]] = dict(ok=bool(got >= need), target=names[g], origin=org, set=k + 2, trips=w["trips"], arrived=int(got), tries=tries,
                                      seconds_median=round(float(np.median([r_[1] for r_ in rr if r_[0]])), 1) if got else None,
                                      seconds_by_the_set=round(rr[0][2], 1))
                print("{} from its origin: {:>4s} to {:8s} the {} way ({} trips): {}/{} arrive{}{}".format(
                    mp, org, names[g], ("2nd", "3rd")[k], w["trips"], got, tries,
                    "" if not got else ", {:.1f} s (the set: {:.1f})".format(legs[w["key"]]["seconds_median"], rr[0][2]), "" if got >= need else "   <-- NOT MADE"), flush=True)
        return n_new

    sp_node = [int(x) for x in env.route.locate(env.spawns)]
    it_node = [int(env.route.locate(p_[None])[0]) for p_ in env.way_field.goals[:nI]]

    def others():
        """2. from the spawn points and the other items whose way a set changes -> how many ways were taken out"""
        total = 0
        for rnd in range(4):
            env.set_ways(legs=legs, untested=False)
            X = env.way_field
            jobs, seen = [], set()
            starts = [("spawn point {}".format(i + 1), nd) for i, nd in enumerate(sp_node)]
            for g in range(len(X.goals)):
                for k in range(2):
                    if not env.way_plan[g][k]:
                        continue
                    for nm, nd in starts + [("the {}".format(names[h]), nd) for h, nd in enumerate(it_node) if h != g]:
                        if X.wdiff[k, g, nd] and X.T[g, nd] < 1e8 and (g, k, nd) not in seen:
                            seen.add((g, k, nd))
                            jobs.append((g, k + 1, nd, nm))
            if not jobs:
                break
            res = run([(g, w, X.nodes[nd]) for g, w, nd, nm in jobs for _ in range(SP_TRIES)])
            got = [sum(r_[0] for r_ in res[j * SP_TRIES:(j + 1) * SP_TRIES]) for j in range(len(jobs))]
            bad = [j for j in range(len(jobs)) if got[j] <= SP_TRIES // 2]
            res0 = run([(jobs[j][0], 0, X.nodes[jobs[j][2]]) for j in bad for _ in range(SP_TRIES)]) if bad else []
            got0 = {j: sum(r_[0] for r_ in res0[q * SP_TRIES:(q + 1) * SP_TRIES]) for q, j in enumerate(bad)}
            rows2[:] = [dict(target=names[g], set=w + 1, start=nm, arrived=int(got[j]), tries=SP_TRIES,
                             **(dict(the_shortest_arrived=int(got0[j])) if j in got0 else {})) for j, (g, w, nd, nm) in enumerate(jobs)]
            blamed = 0
            for j in bad:
                if got0[j] - got[j] < 2:                     # (the shortest way from there does no better: not this set's doing)
                    continue
                g, w, nd, nm = jobs[j]
                k = w - 1
                ch = WY.walk(X.wnext[k, g], nd)
                alt = [(a_, b_) for a_, b_ in zip(ch[:-1], ch[1:]) if X.wnext[k, g, a_] != X.walk[g, a_]]
                keys = [w_["key"] for r in env.way_report[g] for w_ in r["ways"] if w_["what"] == "way {}".format(k + 2)]
                hit = []
                for (P, _), key in zip(env.way_plan[g][k], keys):
                    on, _s = WY._along(X.nodes, P)
                    if any(on[a_] and on[b_] for a_, b_ in alt):
                        hit.append(key)
                for key in (hit or keys):
                    if legs[key]["ok"]:
                        legs[key].update(ok=False, fails_from="{} ({}/{} arrive, the shortest way {}/{})".format(nm, got[j], SP_TRIES, got0[j], SP_TRIES))
                        blamed += 1
                        print("{}: from {} to {} by the {} way {}/{} arrive (the shortest {}/{}): {} taken out".format(
                            mp, nm, names[g], ("2nd", "3rd")[k], got[j], SP_TRIES, got0[j], SP_TRIES, key), flush=True)
            print("{} other starts: {} starts (spawn points and items) whose way a set changes, {} with at most {} of {} arriving, {} ways taken out".format(
                mp, len(jobs), len(bad), SP_TRIES // 2, SP_TRIES, blamed), flush=True)
            total += blamed
            if not blamed:
                break
        return total

    for _ in range(3):                                       # (a way taken out in step 2 may let another of the pros' ways in: it is tried too)
        origins()
        if not others():
            break
    env.set_ways(legs=legs, untested=True)                   # the ways the walking map cannot follow, with the reason: kept, so that the
    for g, rep in enumerate(env.way_report):                 # simulator does not search for them at every start
        for r in rep:
            for w in r["ways"]:
                if w["what"] in ("no such way for a walker", "over the cap") and w.get("key") and w["key"] not in legs:
                    legs[w["key"]] = dict(ok=False, why=w["what"], target=names[g], origin=r["origin"], trips=w["trips"],
                                          **({"times_the_shortest": w["times_the_shortest"]} if "times_the_shortest" in w else {}))
    env.set_ways(legs=legs, untested=False)
    left = sum(len(s_) for p_ in env.way_plan for s_ in p_)
    tried = [v for v in legs.values() if "why" not in v]
    out = dict(map=mp, made=time.strftime("%Y-%m-%d %H:%M"), legs=os.path.basename(os.path.dirname(os.environ["LEGS_NET"])), tries=tries, need=need,
               made_means="that many of the tries stand at the target within max(6, 1.25 x the way's seconds + 3) seconds, his legs on from the way's origin; "
                          "and from no spawn point or other item do at most {} of {} arrive where the shortest way does better by two".format(SP_TRIES // 2, SP_TRIES),
               switches={k_: os.environ[k_] for k_ in sorted(getattr(E, "PLAY_VARS", ())) if os.environ.get(k_)},
               ways=legs, other_starts=rows2)
    os.makedirs(out_dir, exist_ok=True)
    f = os.path.join(out_dir, mp + ".json")
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("{}: {} ways tried on his legs, {} made, {} not ({} more the walking map cannot follow); {} in the plan now; {:.0f} s -> {}".format(
        mp, len(tried), sum(v["ok"] for v in tried), sum(not v["ok"] for v in tried), len(legs) - len(tried), left, time.time() - t_start, f), flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    tries, need, out_dir = 6, 5, os.path.join(os.path.dirname(HERE), "sim", "pro_ways_legs")
    for flag in ("--tries", "--need", "--out"):
        if flag in args:
            i = args.index(flag)
            v = args[i + 1]
            del args[i:i + 2]
            if flag == "--tries":
                tries = int(v)
            elif flag == "--need":
                need = int(v)
            else:
                out_dir = os.path.abspath(v)
    if not args:
        sys.exit(__doc__)
    maps = args[0].split(",")
    if len(maps) == 1:
        one(maps[0], tries, need, out_dir)
    else:
        for m in maps:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), m, "--tries", str(tries), "--need", str(need), "--out", out_dir],
                               creationflags=0x4000 if os.name == "nt" else 0)
            if r.returncode:
                print(m, "FAILED", r.returncode, flush=True)

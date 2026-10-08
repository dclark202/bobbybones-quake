"""Can the walking teacher walk? A pupil who presses exactly what the teacher shows (keys, jump and, in item runs, the
turn), alone on the map, is sent from the spawn points to each big item, one try of 30 seconds each. If the teacher's
own pupil does not arrive, the teacher cannot teach that way, the scripted item runner (the same walker) does not get
there either, and his "next step" inputs point the same wrong way.

    python tools/teacher_check.py --map bloodrun [--goal RA] [--tries 4] [--nav-dir <folder with a trial graph>]

Prints per item: the share of tries that arrive and the median time; with --goal, where the tries that fail spend their
time (the graph point and the link wanted from there) and where they fall. A walking layer is fit to teach from when
every item is at 90% or more (RESULTS 2026-10-08: Blood Run red armor 73%, a yellow armor 66%). Anaconda Python.
"""
import argparse
import collections
import importlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--goal", default="", help="one item (MH, RA, RL, RG, LG, YA, YA2): print where its tries fail")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--nav-dir", default=os.path.join(ROOT, "data", "maps"))
    ap.add_argument("--tries", type=int, default=4, help="rounds of 32 tries each")
    ap.add_argument("--secs", type=float, default=30.0)
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    navp = os.path.join(a.nav_dir, "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=16, seed=5, loadout="all", nav=navp)
    kind = {(e[0], e[1]): e[3] for e in json.load(open(navp))["edges"]}
    env.item_run_p, env.collect_fight_p = 1.0, 0.0
    env.near_item_p = env.stack_p = env.close_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    if env.lab is not None:
        env.arena_rooms = [3]
        env.lab_p = (0.0, 0.0, 1.0)
    R, n = env.route, env.n
    mid_t, mid_p = len(E.TURN) // 2, len(E.PITCH) // 2
    orig = env._run_pick
    target = [0]
    env._run_pick = lambda i: (orig(i), env.run_k.__setitem__(i, target[0]))[0]     # the target stays the one under test
    env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    print("{}: the walking teacher's own pupil, {} tries an item from the spawn points, {:g} s each".format(a.map, 32 * a.tries, a.secs))
    for lab in ([a.goal] if a.goal else [l for l in env.route_goal if l in E.INTENTS]):
        k_goal = E.INTENTS.index(lab)
        gi = env.intent_gi[k_goal]
        it = env.route_item[gi]
        target[0] = k_goal
        tries = arrived = 0
        times, stand, falls = [], collections.Counter(), collections.Counter()
        for _ in range(a.tries):
            for i in range(n):                               # a fresh try for everybody: a spawn point, the item lying there
                env.state = env.w.state()
                env._spawn(i, avoid=None)
            env.state = env.w.state()
            env.run_k[:] = k_goal
            env.item_up[:, it], env.item_t[:, it] = True, 0.0
            env.round_t[:] = 0.0
            got, when = np.zeros(n, bool), np.zeros(n)
            ok0 = R.T[gi, R.locate(env.state[:, :3])] < 1e8
            lg = env.state[:, :3].copy()
            for t in range(int(a.secs / E.DT)):
                act = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
                act[:, 0] = act[:, 1] = 1
                act[:, 3], act[:, 4] = mid_t, mid_p
                tl = env.teach
                has = tl[:, 0] >= 0
                act[has, :3] = tl[has, :3]
                turn = tl[:, 3] >= 0
                act[turn, 3] = tl[turn, 3]
                act[:, 10] = k_goal
                s0 = env.state.copy()
                env.step(act)
                env.run_k[:] = k_goal
                s = env.state
                new = (np.linalg.norm(s[:, :3] - env.item_pos[it][None, :], axis=1) < 48) & ~got
                when = np.where(new, (t + 1) * E.DT, when)
                got |= new
                env.item_up[:, it], env.item_t[:, it] = True, 0.0
                node = R.locate(s[:, :3])
                for i in np.nonzero(~got & ok0)[0]:
                    stand[int(node[i])] += 1
                left = (s0[:, 6] > 0.5) & (s[:, 6] < 0.5)
                lg = np.where(left[:, None], s0[:, :3], lg)
                fell = (s0[:, 6] < 0.5) & (s[:, 6] > 0.5) & (lg[:, 2] - s[:, 2] > 100.0)
                for i in np.nonzero(fell & ~got & ok0)[0]:
                    falls[int(R.locate(lg[i:i + 1])[0])] += 1
            tries += int(ok0.sum())
            arrived += int((got & ok0).sum())
            times += when[got & ok0].tolist()
        no_way = 32 * a.tries - tries
        print("   {:4s} {:4.0%} arrive ({} of {}), median {:4.1f} s{}".format(
            lab, arrived / max(1, tries), arrived, tries, float(np.median(times)) if times else float("nan"),
            "; {} tries had no way in the graph".format(no_way) if no_way else ""))
        if not a.goal:
            continue

        def link(p):
            q = int(R.walk[gi, p])
            if q < 0:
                return "the goal's own point"
            d = R.nodes[q] - R.nodes[p]
            return "{} link of {:.0f} units, {:+.0f} high, to {}".format(kind.get((p, q), "?"), np.hypot(d[0], d[1]), d[2], R.nodes[q].round(0).tolist())
        tot = max(1, sum(stand.values()))
        print("   where the tries that have not arrived spend their time (graph point, share, way left, the link wanted from there):")
        for p, c in stand.most_common(6):
            print("      {} {:4.1%}, {:4.1f} s left | {}".format(R.nodes[p].round(0).tolist(), c / tot, float(R.T[gi, p]), link(p)))
        print("   falls of more than 100 units, by the point he left the ground at (a wanted drop counts too):")
        for p, c in falls.most_common(5):
            print("      {} x{}, {:.1f} s left | {}".format(R.nodes[p].round(0).tolist(), c, float(R.T[gi, p]), link(p)))


if __name__ == "__main__":
    main()

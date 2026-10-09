"""Alone on a map, does he go and get the item he intends? (owner, 2026-10-07: test this before adding solo runs.)
One learner a game; the other seat stands still, is not seen and cannot be hurt or hurt. The intention head is either
forced to one item for the whole round or left to him. Each round starts at a normal spawn with the machine gun.
Prints, per intention: the share of rounds in which he took the item, how long it took against the walking graph's
time from his spawn, and how far along the way he got when he did not.

    python tools/solo_item_check.py --run duel_gru_v9 --map arena1 [--policy file] [--secs 30] [--rounds 6]   (Anaconda Python)
"""
import argparse
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import test_suite as T   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--secs", type=float, default=30.0)
    ap.add_argument("--rounds", type=int, default=6)
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    T.E = E
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=7)
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.games, seed=21, loadout="all", nav=nav)
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.arena_len = env.round_len = a.secs
    env.stack_p = env.near_item_p = 0.0
    if env.lab is not None:
        env.arena_rooms = [3]
        env.lab_p = (0.0, 0.0, 1.0)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    n = env.n
    me = np.arange(0, n, 2)                                    # the learners; the odd seats stand still
    env._los = lambda a_, b_: np.zeros(len(a_), bool)          # nobody is seen
    env._hit = lambda *x, **k: None                            # nobody is hurt
    R = env.route
    lab = [E.INTENTS.index(l) if l in E.INTENTS else -1 for l in env.route_goal]
    nin = len(pol.mean)
    steps = int(a.secs / E.DT) - 2
    print("{} on {}: {} games x {} rounds of {:g} s, alone, machine gun at spawn".format(a.run, a.map, a.games, a.rounds, a.secs))
    print("{:>10s} | {:>7s} | {:>14s} | {:>15s} | {:>20s} | {:>9s}".format(
        "intention", "took it", "way at spawn s", "time he took s", "way covered if not", "speed u/s"))
    for name in ["free"] + [l for l in env.route_goal if l in E.INTENTS]:
        k = E.INTENTS.index(name) if name != "free" else 0
        took, t_way, t_took, cover, speed, chose = [], [], [], [], [], np.zeros(len(E.INTENTS))
        for _ in range(a.rounds):
            env.round_t[:] = 1e9
            h = pol.zeros(n)
            obs, _, _, _ = env.step(np.zeros((n, len(pol.dims)), np.int64))
            gi = lab.index(k) if name != "free" else None
            T0 = R.T[gi, R.locate(env.state[me, :3])] if gi is not None else None
            best = T0.copy() if gi is not None else None
            got = np.zeros(len(me), bool)
            when = np.full(len(me), np.nan)
            big = np.zeros((len(me), 2), bool)                  # free: did he take the mega / the red armor
            for t in range(steps):
                hp0, ar0, has0 = env.hp[me].copy(), env.armor[me].copy(), env.has[me].copy()
                p0 = env.state[me, :2].copy()
                act, h = pol.act(obs[:, :nin], h)
                act[1::2] = 0
                act[1::2, 0] = act[1::2, 1] = 1
                if name != "free":
                    act[me, 10] = k
                else:
                    np.add.at(chose, env.intent[me], 1)
                obs, _, done, _ = env.step(act)
                mh = (env.hp[me] - hp0 > 60) & (hp0 > 0)
                ra = env.armor[me] - ar0 > 60
                big |= np.stack([mh, ra], 1)
                if name in ("MH", "RA"):
                    now = mh if name == "MH" else ra
                elif name.startswith("YA"):                  # a yellow armor: armor gained on that armor's own spot
                    now = (env.armor[me] - ar0 > 20) & ~ra & (np.linalg.norm(env.state[me, :3] - R.goals[gi], axis=1) < 80)
                elif name != "free":
                    w = E.WEAPONS.index(name.lower())
                    now = env.has[me][:, w] & ~has0[:, w]
                else:
                    now = np.zeros(len(me), bool)
                when = np.where(now & ~got, (t + 1) * E.DT, when)
                got |= now
                if gi is not None:
                    best = np.minimum(best, R.T[gi, R.locate(env.state[me, :3])])
                speed.append(float(np.linalg.norm(env.state[me, :2] - p0, axis=1).mean()) / E.DT)
            if name == "free":
                took.append(big.mean(0))
            else:
                took.append(got)
                t_way.append(T0)
                t_took.append(when)
                cover.append(np.where(got, np.nan, 1.0 - best / np.maximum(T0, 1e-3)))
        if name == "free":
            b = np.mean(took, 0)
            ch = chose / max(1.0, chose.sum())
            print("{:>10s} | mega {:.0%}, red armor {:.0%} of the rounds | he chose: {} | {:>9.0f}".format(
                "his own", b[0], b[1], ", ".join("{} {:.0%}".format(E.INTENTS[i] if i else "none", ch[i]) for i in range(len(ch))), np.mean(speed)))
            continue
        took, t_way, t_took, cover = (np.concatenate(x) for x in (took, t_way, t_took, cover))
        print("{:>10s} | {:>6.0%} | {:>14.1f} | {:>15s} | {:>20s} | {:>9.0f}".format(
            name, took.mean(), float(np.mean(t_way)),
            "{:.1f} (way {:.1f})".format(float(np.nanmean(t_took)), float(t_way[took].mean())) if took.any() else "-",
            "{:.0%}".format(float(np.nanmean(cover))) if (~took).any() else "-", np.mean(speed)))


if __name__ == "__main__":
    main()

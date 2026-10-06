"""How he works the trigger, per weapon, in a few minutes of self-play on arena1: how long the button stays down
once pressed (median and mean, in ms), the share of presses shorter than 100 ms, and presses a second with the
weapon in hand and an enemy in view. A person holds the lightning gun down and taps the rail; a bot that taps the
lightning gun at the click budget looks like it is spamming (owner, 2026-10-06).

    python tools/fire_holds.py --run duel_gru_v8 [--group 3] [--minutes 3]      (Anaconda Python)
"""
import argparse
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import test_suite as T               # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--group", type=int, default=3)
    ap.add_argument("--groups", type=int, default=8)
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--minutes", type=float, default=3.0)
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=9)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.groups, seed=13, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, **(dict(group=a.group) if a.group != 2 else {}))
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [tuple(E.WEAPONS.index(x) for x in s_.split(",")) for s_ in "mg;rl;rg;lg;rl,rg;rl,lg;rg,lg;rl,rg,lg".split(";")]
    env.arena_len = 180.0
    env.lab_force = dict(kind=E.NORMAL, arena=3)
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    nin = len(pol.mean)
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    n = env.n
    run = np.zeros(n, np.int64)                              # frames the button has been down
    run_w = np.full(n, -1, np.int64)
    holds = {w: [] for w in range(len(E.WEAPONS))}           # completed presses, in frames
    presses = np.zeros(len(E.WEAPONS))
    frames_vis = np.zeros(len(E.WEAPONS))
    for t in range(int(a.minutes * 60 / E.DT)):
        act, h = pol.act(obs[:, :nin], h)
        obs, r, done, info = env.step(act)
        h[done] = 0.0
        fire = env.fire_last.astype(bool) if hasattr(env, "fire_last") else act[:, 5] == 1
        w = env.weapon
        for i in range(n):
            if fire[i] and (run[i] == 0 or run_w[i] != w[i]):
                if run[i] > 0:
                    holds[run_w[i]].append(run[i])
                run[i], run_w[i] = 1, w[i]
                presses[w[i]] += 1
            elif fire[i]:
                run[i] += 1
            elif run[i] > 0:
                holds[run_w[i]].append(run[i])
                run[i] = 0
        np.add.at(frames_vis, w[env.visible], 1)
    print("trigger per weapon ({:.0f} player-minutes on {}):".format(a.groups * a.group * a.minutes, a.map))
    print("  {:5s} {:>8s} {:>9s} {:>9s} {:>12s} {:>14s}".format("gun", "presses", "median", "mean", "under 100ms", "presses/s seen"))
    for k, name in enumerate(E.WEAPONS):
        hs = np.array(holds[k]) * E.DT * 1000.0
        if len(hs) < 20:
            continue
        print("  {:5s} {:8d} {:7.0f}ms {:7.0f}ms {:11.0%} {:14.2f}".format(
            name, len(hs), np.median(hs), hs.mean(), (hs < 100).mean(), presses[k] / max(1.0, frames_vis[k] * E.DT)))


if __name__ == "__main__":
    main()

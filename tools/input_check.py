"""Are his inputs alive, and are they the same on a real server as in the simulator?

    python tools/input_check.py --run duel_gru_v12 --env duel_env_ffa_v12 --inputs docs/INPUTS_v12.csv --map arena1
    python tools/input_check.py ... --real data/obscheck/obs_dump.npy      (a recording made with OBSDUMP=1 tools/bench_arena.sh)

Plays the network in its own simulator in normal rounds (the game's spawn, playing styles as in training) against
itself or the scripted item runner (--opp runner) and keeps the inputs he was given. Prints the inputs that never change
on that map (dead in training itself) and, with --real, the inputs whose values on the real server differ grossly from
the simulator's: every one of those is a gap in the plugin (plugins/duelbot.py feeds him through the simulator's
observe() but never runs its step(); RESULTS 2026-10-08 14:55). Anaconda Python.
"""
import argparse
import csv
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def collect(a):
    E = importlib.import_module(a.env)
    import test_suite as T
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=1)
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.games, seed=77, loadout="all",
                    nav=nav if os.path.exists(nav) else None)
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = env.close_p = env.item_run_p = env.bot_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.runner_p = 1.0 if a.opp == "runner" else 0.0
    if getattr(env, "lab", None) is not None:
        env.lab_force = dict(kind=E.NORMAL, arena=3)
        env.arena_len = 1e9
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    me = np.nonzero(env.script == 0)[0]
    pol.rng = np.random.default_rng(5)
    h = pol.zeros(len(me))
    keep, acts = [], []
    for t in range(int(a.minutes * 60 / E.DT)):
        act = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        al, h = pol.act(obs[me], h)
        act[me, :al.shape[1]] = al
        obs, r, done, info = env.step(act)
        alive = env.hp[me] > 0
        if t % 3 == 0:
            keep.append(obs[me][alive].copy())
            acts.append(al[alive].copy())
        if (t + 1) % int(120 / E.DT) == 0:                       # his clock and memory start over, as on the server
            env.round_t[:] = 0.0
            env.frags_r[:] = 0
            h[:] = 0.0
    return E, np.concatenate(keep), np.concatenate(acts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--opp", default="self", help="self or runner")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--real", default="", help="a recording of the real game's inputs (obs_dump.npy)")
    ap.add_argument("--skip", type=int, default=0, help="frames to drop from the start of the recording (the warmup)")
    a = ap.parse_args()
    names = [(r["group"], r["input"]) for r in csv.DictReader(open(a.inputs, encoding="utf-8"))]
    E, sim, acts = collect(a)
    assert sim.shape[1] == len(names), "the simulator gives {} inputs, {} lists {}".format(sim.shape[1], a.inputs, len(names))
    print("{} on {}: {} frames of inputs from the simulator".format(a.run or a.policy, a.map, len(sim)))
    dead = [j for j in range(sim.shape[1]) if sim[:, j].std() < 1e-7]
    by = {}
    for j in dead:
        by.setdefault(names[j][0], []).append("{} ({:g})".format(names[j][1], float(sim[0, j])))
    print("inputs that never change in the simulator on this map: {} of {}".format(len(dead), sim.shape[1]))
    for g, v in by.items():
        print("   {:16s} {}".format(g, "; ".join(v)[:420]))
    big = [(float(np.abs(sim[:, j]).max()), names[j]) for j in range(sim.shape[1]) if np.abs(sim[:, j]).max() > 4.0]
    if big:
        print("inputs beyond 4 in size:", [(round(m, 1), n_[1]) for m, n_ in big][:12])
    heads = ("forward", "strafe", "vertical", "turn", "pitch", "fire", "weapon", "walk", "zoom", "lift", "intention")
    print("his actions: " + " | ".join("{} {}".format(heads[k], np.round(np.bincount(acts[:, k], minlength=E.ACTION_DIMS[k]) / len(acts), 2).tolist())
                                      for k in range(acts.shape[1]) if k not in (3, 4)))
    if not a.real:
        return
    real = np.load(a.real)[a.skip:]
    assert real.shape[1] == sim.shape[1], "the recording has {} inputs".format(real.shape[1])
    print("\n{} frames from the real game".format(len(real)))
    rows = []
    for j, (g, nm) in enumerate(names):
        r, s = real[:, j], sim[:, j]
        rows.append((abs(float(r.mean() - s.mean())) / (float(s.std() + r.std()) + 0.02), j, g, nm, r, s))
    fmt = "   {:3d} {:12s} {:40s} real {:6.2f} sd {:5.2f} [{:5.2f}..{:5.2f}] | simulator {:6.2f} sd {:5.2f} [{:5.2f}..{:5.2f}]"
    print("never change in the real game, but do in the simulator:")
    for gap, j, g, nm, r, s in rows:
        if r.std() < 1e-7 and s.std() > 0.05:
            print(fmt.format(j, g[:12], nm[:40], r.mean(), r.std(), r.min(), r.max(), s.mean(), s.std(), s.min(), s.max()))
    print("never change in the simulator, but do in the real game:")
    for gap, j, g, nm, r, s in rows:
        if s.std() < 1e-7 and r.std() > 0.05:
            print(fmt.format(j, g[:12], nm[:40], r.mean(), r.std(), r.min(), r.max(), s.mean(), s.std(), s.min(), s.max()))
    print("the largest differences in the mean (in units of the spread):")
    for gap, j, g, nm, r, s in sorted(rows, key=lambda x: -x[0])[:40]:
        print("{:5.1f}".format(gap) + fmt.format(j, g[:12], nm[:40], r.mean(), r.std(), r.min(), r.max(), s.mean(), s.std(), s.min(), s.max()))


if __name__ == "__main__":
    main()

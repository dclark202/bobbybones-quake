"""Does the scripted item runner (script 3, sim/duel_env.py _runner_keys) get to the items? Two seats a game: seat 0
stands still and does nothing, seat 1 is the runner. Prints, per map, what the runner took a minute and how he stood.
    RUNNER_P=1 python tools/runner_check.py [--maps arena1,bloodrun,...] [--minutes 3]     (system or Anaconda Python)
"""
import argparse
import importlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default="arena1")
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--env", default="duel_env_ffa")
    a = ap.parse_args()
    os.environ["RUNNER_P"] = "1"
    E = importlib.import_module(a.env)
    mp = a.maps.split(",")[0]                                  # one map a process: the simulator has one world per process
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=a.games, seed=5, loadout="all", nav=nav)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.arena_len = 180.0
    if env.lab is not None:
        env.arena_rooms = [3]
        env.lab_p = (0.0, 0.0, 1.0)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.round_t[:] = 1e9
    act = np.zeros((env.n, len(E.ACTION_DIMS)), np.int64)
    act[:, 0] = act[:, 1] = 1                                  # no keys
    act[:, 3], act[:, 4] = int(np.abs(E.TURN).argmin()), int(np.abs(E.PITCH).argmin())
    env.step(act)
    run = np.nonzero(env.script == 3)[0]
    steps = int(a.minutes * 60 / E.DT)
    got = dict(mega=0, red=0, weapon=0)
    hp_s = ar_s = gun_s = moved = 0.0
    for t in range(steps):
        hp0, ar0, has0 = env.hp[run].copy(), env.armor[run].copy(), env.has[run].copy()
        p0 = env.state[run, :2].copy()
        env.step(act)
        run = np.nonzero(env.script == 3)[0] if t % 400 == 0 else run
        if len(hp0) != len(run):
            continue
        got["mega"] += int(((env.hp[run] - hp0 > 60) & (hp0 > 0)).sum())      # (a respawn is not a pickup)
        got["red"] += int((env.armor[run] - ar0 > 60).sum())
        got["weapon"] += int((env.has[run][:, [E.RL, E.RG, E.LG]] & ~has0[:, [E.RL, E.RG, E.LG]]).sum())
        hp_s += float(env.hp[run].mean())
        ar_s += float(env.armor[run].mean())
        gun_s += float(env.has[run][:, [E.RL, E.RG, E.LG]].any(1).mean())
        moved += float(np.linalg.norm(env.state[run, :2] - p0, axis=1).mean())
    mins = a.minutes * max(1, len(run))
    print("{:15s} runners {:2d} | per runner-minute: mega {:.2f}, red armor {:.2f}, big weapons {:.2f} | mean health {:.0f}, armor {:.0f}, "
          "a big weapon in hand {:.0%} of the time | speed {:.0f} u/s".format(
              mp, len(run), got["mega"] / mins, got["red"] / mins, got["weapon"] / mins, hp_s / steps, ar_s / steps, gun_s / steps,
              moved / steps / E.DT))


if __name__ == "__main__":
    main()

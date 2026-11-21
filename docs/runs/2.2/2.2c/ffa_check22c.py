"""2.2c: the generated module (sim/duel_env_ffa.py, tools/make_ffa_env.py) plays as sim/duel_env.py at two players, with 2.2c's command's settings
(CONTEST, RAIL_CHAIN, AHEAD_IN, NEAR_MISS, PAY_SPLIT on) on a map with its ways (the contest pay needs the route's seconds of way; tools/ffa_check.py's
test map has none and is missing from data/maps): the same seed, the same actions (mostly firing, turned toward the enemy) -> inputs, pay, round
ends and the pay by term, frame by frame. One simulator a process.
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2c/ffa_check22c.py [--map bloodrun] [--frames 1500]"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(module, mp, frames, out, matches):
    sys.path.insert(0, HERE)
    import ident_sim as IS
    root_ = os.environ.get("QLBOT_ROOT") or ROOT
    ev = IS.cmd_env(os.path.join(HERE, "train.cmd"), root_)
    ev.update(IS.cmd_env(os.path.join(HERE, "aim2_env.cmd"), root_))
    ev.update(PAY_SPLIT="1", PRO_START_P="0", FIGHT_START_P="0")
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import importlib
    E = importlib.import_module(module)
    D = os.path.join(root_, "data", "maps")
    env = E.DuelEnv(os.path.join(D, mp + ".bsp"), n_matches=matches, seed=5, loadout="all", nav=os.path.join(D, "nav_{}_sim.json".format(mp)))
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    env.dmg_reward, env.dmg_taken_w = 0.005, 0.9
    rng = np.random.default_rng(11)
    cut = E.OBS_BASE + E.N_EXTRA + E.N_FIGHT + E.N_MEM + E.N_ROUTE
    obs, rew, don, pts = [], [], [], []
    for t in range(frames):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.8
        s = env.state
        foe = np.arange(env.n) ^ 1
        to = s[foe, :3] - s[:, :3]
        ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw + 180.0) % 360.0 - 180.0
        ep = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - env.pitch
        aim = rng.random(env.n) < 0.7
        a[:, 3] = np.where(aim, np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1), a[:, 3])
        a[:, 4] = np.where(aim, np.abs(E.PITCH[None, :] - np.clip(ep, -10, 10)[:, None]).argmin(1), a[:, 4])
        a = np.concatenate([a, (3 + 4 * int(t % 8 == 0) + np.zeros(env.n, np.int64))[:, None]], 1)
        o, r, d, info = env.step(a)
        oo = o if not hasattr(E, "N_FFA") else np.delete(o, np.s_[cut:cut + E.N_FFA], axis=1)
        obs.append(oo.copy())
        rew.append(np.asarray(r).copy())
        don.append(np.asarray(d).copy())
        pts.append(np.asarray(info["pay_terms"]).copy())
    np.savez(out, obs=np.array(obs), rew=np.array(rew), don=np.array(don), pts=np.array(pts), contest=np.asarray(env.stats.get("contest", [])))
    print("{} on {}: {} frames x {} seats; the contest counters {}".format(module, mp, frames, env.n, np.round(np.asarray(env.stats.get("contest", [])), 3).tolist()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=1500)
    ap.add_argument("--matches", type=int, default=24)
    ap.add_argument("--one", nargs=2)
    a = ap.parse_args()
    if a.one:
        run(a.one[0], a.map, a.frames, a.one[1], a.matches)
        return 0
    tmp = tempfile.mkdtemp(prefix="ffa22c_")
    outs = []
    for mod in ("duel_env", "duel_env_ffa"):
        outs.append(os.path.join(tmp, mod + ".npz"))
        subprocess.run([sys.executable, __file__, "--map", a.map, "--frames", str(a.frames), "--matches", str(a.matches), "--one", mod, outs[-1]],
                       check=True, creationflags=NOWIN)
    A, B = np.load(outs[0]), np.load(outs[1])
    same = {k: bool(np.array_equal(A[k], B[k])) for k in ("obs", "rew", "don", "pts", "contest")}
    print("TWO PLAYERS on {} with 2.2c's switches: {} ({}); the contest counters (both) {}".format(a.map, "IDENTICAL to duel_env" if all(same.values()) else "DIFFERENT", same,
                                                                                               np.round(A["contest"], 3).tolist()))
    return 0 if all(same.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

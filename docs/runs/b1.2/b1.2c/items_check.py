"""SM_ITEMS's check (fixed seed, random actions, the run's settings, the CPU; each side a process): 1. off: the first 868 columns, pay, round ends the same to the bit as the code at git HEAD, the new columns zeros; 2. on: the game the same; for each small item, by what the code says: what it is, where it is, the way, what he believes against the truth, what it gives. Prints a player's table to read by eye, and the time a frame costs.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2c\\items_check.py > docs\\runs\\b1.2\\b1.2c\\items_check.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
CMD = os.path.join(ROOT, "docs", "runs", "b1.1", "b1.1a", "train.cmd")     # (no ITEM_RATE: git HEAD has none)
RUN0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_0")
FRAMES = 2400


def side(mod_path, mp, out, mode):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33")
    if mode == "on":
        envv["SM_ITEMS"] = "1"
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    spec.loader.exec_module(E)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    t0 = time.time()
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn = [], [], []
    wrong_up = total_up = 0
    t1 = time.time()
    for f in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        O.append(obs[:, :868].astype(np.float32) if f % 4 == 0 else O[-1])
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        if mode == "on" and f % 40 == 0:
            ids = env.sm_ids
            bel = env.sm_bel >= np.array([env.item_def[i][2] for i in ids])
            tr = env.item_up[np.arange(env.n) // 2][:, ids]
            wrong_up += int((bel != tr).sum())
            total_up += bel.size
    t2 = time.time()
    x = dict(obs=np.stack(O[::4]), rew=np.stack(R), done=np.stack(Dn), t_make=t1 - t0, t_frame=(t2 - t1) / FRAMES)
    x["new"] = obs[:, 868:] if obs.shape[1] > 868 else np.zeros((env.n, 0))
    if mode == "on":
        lab = {0: "bubbles", 1: "25 health", 2: "50 health", 3: "shards", 4: "green"}
        F = E.SM_F
        print("{}: {} small items in {} places (sizes {}), {} slots; belief wrong on {:.1%} of readings (it should be some: he doesn't see everything); make {:.1f} s, a frame {:.2f} ms".format(mp, len(env.sm_ids), len(env.sm_places), sorted((len(g) for g in env.sm_places), reverse=True), E.SM_SLOTS, wrong_up / max(1, total_up), t1 - t0, 1000 * (t2 - t1) / FRAMES), flush=True)
        for pl_ in (0, 7):
            n_ = obs[pl_, -E.N_ITEMS:]
            print("  player {} at {}, health {:.0f}, armor {:.0f}".format(pl_, np.round(env.state[pl_, :3]), env.hp[pl_], env.armor[pl_]))
            last = -1.0
            for j in range(E.SM_SLOTS):
                r = n_[j * F:j * F + F]
                assert r[0] == 1.0 or j >= len(env.sm_places), "an empty slot within the map's places"
                if r[0] != 1.0:
                    assert (r == 0).all(), "a slot beyond the map's places"
                    continue
                assert r[1:6].sum() == 1.0 and r[9] >= last - 1e-5, "what it is, or nearest first"
                last = r[9]
                print("  {} {:10s} fwd {:+.2f} left {:+.2f} up {:+.2f} | way {:.2f} step {:+.2f} {:+.2f} | there {} | gives {:.2f}".format(j + 1, lab[int(np.argmax(r[1:6]))], r[6], r[7], r[8], r[9], r[10], r[11], int(r[12]), r[13]))
    np.savez(out, **x)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b12c_items_")
    head = os.path.join(tmp, "duel_env_ffa_head.py")
    with open(head, "wb") as f:
        f.write(subprocess.check_output(["git", "show", "HEAD:sim/duel_env_ffa.py"], cwd=ROOT))
    now = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    ok = True

    def check(name, c):
        nonlocal ok
        ok = ok and bool(c)
        print(("PASS " if c else "FAIL ") + name, flush=True)

    for mp in ("bloodrun", "cure"):
        res = {}
        for name, mod, mode in (("head", head, "off"), ("off", now, "off"), ("on", now, "on")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H, O, N = res["head"], res["off"], res["on"]
        check("{} off: the first 868 inputs, pay and ends as HEAD".format(mp), np.array_equal(H["obs"], O["obs"]) and np.array_equal(H["rew"], O["rew"]) and np.array_equal(H["done"], O["done"]))
        check("{} off: the new inputs zeros".format(mp), (O["new"] == 0).all())
        check("{} on: the game the same".format(mp), np.array_equal(H["obs"], N["obs"]) and np.array_equal(H["rew"], N["rew"]))
        print("{} a frame: off {:.2f} ms, on {:.2f} ms; making the world: off {:.1f} s, on {:.1f} s".format(mp, 1000 * float(O["t_frame"]), 1000 * float(N["t_frame"]), float(O["t_make"]), float(N["t_make"])), flush=True)
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

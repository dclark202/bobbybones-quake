"""b1.1a's identity (fixed seed, random actions, the run's simulator settings, on the CPU, each side a process of its own):
  1. the code at git HEAD against today's, the lock at 8 s from the environment: inputs, pay, round ends, r_long and counters the same to the bit;
  2. today's, the lock set to 8 s by live_set at the first frame: the same to the bit;
  3. today's, the lock set to 1 s by live_set: target changes up; the game differs.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.1\\b1.1a\\ident.py > docs\\runs\\b1.1\\b1.1a\\ident.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
CMD = os.path.join(HERE, "train.cmd")
RUN0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_0")
FRAMES = 3000


def side(mod_path, mp, out, live):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1", WIN_SHADOW="1")
    assert envv.get("INTENT_HOLD") == "8", envv.get("INTENT_HOLD")
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    spec.loader.exec_module(E)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    if live != "none":
        E.live_set({"INTENT_HOLD": live})
        assert E.INTENT_HOLD == float(live)
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L = [], [], [], []
    ch = 0
    prev = env.intent.copy()
    for _ in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        ch += int((env.intent != prev).sum())
        prev = env.intent.copy()
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), changes=ch, **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b11a_ident_")
    head = os.path.join(tmp, "duel_env_ffa_head.py")
    with open(head, "wb") as f:
        f.write(subprocess.check_output(["git", "show", "HEAD:sim/duel_env_ffa.py"], cwd=ROOT))
    now = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    ok = True
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    for mp in ("bloodrun", "aerowalk"):
        res = {}
        for name, mod, live in (("head", head, "none"), ("now", now, "none"), ("live8", now, "8"), ("live1", now, "1")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, live], env=env)
            res[name] = np.load(o_)
        H = res["head"]
        for name in ("now", "live8"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl", "changes")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            print("{} HEAD against {}: {}".format(mp, name, same), flush=True)
            ok &= all(same.values())
        c8, c1 = int(res["live8"]["changes"]), int(res["live1"]["changes"])
        differs = not np.array_equal(res["live8"]["obs"], res["live1"]["obs"])
        print("{} target changes: at 8 s {}, at 1 s {}; the game differs {}".format(mp, c8, c1, differs), flush=True)
        ok &= c1 > c8 and differs
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""b1.0a's identity (fixed seed, random actions, the run's simulator settings, on the CPU, each side a process of its own):
  1. the code at git HEAD against today's with WIN_ADD unset and at 0: inputs, pay, round ends, r_long and counters the same to the bit;
  2. WIN_ADD 0.33 against 0: the same game (inputs, round ends, r_long), the pay differs by exactly 0.33 x the win part, the table's pay is untouched, the
     added pay is zero-sum between the seats.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.0a\\ident.py > docs\\runs\\b1.0a\\ident.log"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CMD = os.path.join(HERE, "train.cmd")
RUN0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_0")
FRAMES = 3000
A = 0.33


def side(mod_path, mp, out, add):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", PAY_SPLIT="1", WIN_SHADOW="1")
    if add != "unset":
        envv["WIN_ADD"] = add
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(ROOT, "sim", "duel_env_ffa.py")   # (the HEAD copy reads its files from sim/, as the module it stands for)
    spec.loader.exec_module(E)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L, W = [], [], [], [], []
    for _ in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        W.append(np.asarray(info["win_blend"], np.float64)[:, 2] if "win_blend" in info else np.zeros(env.n))
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), paid=np.stack(W), **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b10a_ident_")
    head = os.path.join(tmp, "duel_env_ffa_head.py")
    with open(head, "wb") as f:
        f.write(subprocess.check_output(["git", "show", "HEAD:sim/duel_env_ffa.py"], cwd=ROOT))
    now = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    ok = True
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    for mp in ("bloodrun", "aerowalk"):
        res = {}
        for name, mod, add in (("head", head, "unset"), ("unset", now, "unset"), ("zero", now, "0"), ("add", now, str(A))):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, add], env=env)
            res[name] = np.load(o_)
        H = res["head"]
        for name in ("unset", "zero"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            print("{} HEAD against WIN_ADD {}: {}".format(mp, name, same), flush=True)
            ok &= all(same.values())
        Z, B = res["zero"], res["add"]
        same = {k: bool(np.array_equal(Z[k], B[k])) for k in ("obs", "done", "rl")}
        d = B["rew"] - Z["rew"]
        err = float(np.abs(d - B["paid"]).max())
        zs = float(np.abs(d[:, ::2] + d[:, 1::2]).max())
        print("{} WIN_ADD {} against 0: the same game {}; |added| summed {:.2f}; added - A x win {:.2e}; the seats' sum {:.2e}".format(mp, A, same, float(np.abs(d).sum()), err, zs), flush=True)
        ok &= all(same.values()) and err < 1e-3 and zs < 1e-3 and float(np.abs(d).sum()) > 0
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

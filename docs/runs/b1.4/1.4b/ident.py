"""1.4b's identity (fixed seed, random actions, 1.3b's simulator settings, on the CPU, each side a process of its own):
  1. the code at git HEAD against today's with both new settings unset, and with env.wown_seat all 0: inputs, pay, round ends, r_long and
     counters the same to the bit;
  2. INTENT_SWITCH=0: the game the same to the bit; the pay higher by exactly 0.02 a charged change of target, nothing else;
  3. WEAPON_OWN=1: no held weapon turned into "nothing" (it was, unset), the game differs.
Data and tables are read from the main repo (this file runs in a worktree without data links).
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4b\\ident.py > docs\\runs\\b1.4\\1.4b\\ident.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")
CMD = os.path.join(MAIN, "docs", "runs", "b1.3", "1.3b", "train.cmd")
RUN0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_3b")
FRAMES = 3000


def side(mod_path, mp, out, mode):
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    sys.path.insert(0, os.path.join(MAIN, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1")
    envv.pop("INTENT_SWITCH", None)
    envv.pop("WEAPON_OWN", None)
    if mode == "sw0":
        envv["INTENT_SWITCH"] = "0"
    if mode == "wown":
        envv["WEAPON_OWN"] = "1"
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(MAIN, "sim", "duel_env_ffa.py")
    spec.loader.exec_module(E)
    assert E.WEAPON_FREE, "1.3b's settings have WEAPON_FREE=1"
    nav_ = os.path.join(MAIN, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(MAIN, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.8, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    if mode == "seat0":
        env.wown_seat = np.zeros(env.n, np.float32)
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L, CH = [], [], [], [], []
    for _ in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        prev = env.intent.copy()
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        CH.append((env.intent != prev).copy())
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), ch=np.stack(CH), **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="i14b_ident_")
    head = os.path.join(tmp, "duel_env_ffa_head.py")
    with open(head, "wb") as f:
        f.write(subprocess.check_output(["git", "show", "HEAD:sim/duel_env_ffa.py"], cwd=ROOT))
    now = os.path.join(ROOT, "sim", "duel_env_ffa.py")
    ok = True
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")

    def check(name, c):
        nonlocal ok
        ok = ok and bool(c)
        print(("PASS " if c else "FAIL ") + name, flush=True)

    for mp in ("bloodrun", "aerowalk"):
        res = {}
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("seat0", now, "seat0"), ("sw0", now, "sw0"), ("wown", now, "wown")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H, N = res["head"], res["now"]
        for name in ("now", "seat0"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl", "ch")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        S = res["sw0"]
        check("{} switch cost 0: the game the same".format(mp), all(np.array_equal(N[k], S[k]) for k in ("obs", "done", "ch")))
        d_ = S["rew"] - N["rew"]
        q_ = d_ / 0.02
        whole = bool(np.abs(q_ - np.round(q_)).max() < 1e-3) and bool((np.round(q_) >= 0).all())
        print("{} switch cost 0: pay up {:.3f} in {} frames ({} charged changes); changes of target {}".format(
            mp, d_.sum(), int((np.abs(d_) > 1e-9).sum()), int(np.round(q_).sum()), int(N["ch"].sum())), flush=True)
        check("{} switch cost 0: every difference a whole number of 0.02, none negative, some".format(mp), whole and d_.sum() > 0)
        W = res["wown"]
        wo_n, wo_w = N["st_weapon_own"], W["st_weapon_own"]
        print("{} held weapons turned into nothing (readings, turned): unset {}, WEAPON_OWN=1 {}".format(mp, wo_n.tolist(), wo_w.tolist()), flush=True)
        check("{} WEAPON_OWN=1: none turned (unset: some); the game differs".format(mp), wo_n[1] > 0 and wo_w[1] == 0 and not np.array_equal(N["obs"], W["obs"]))
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

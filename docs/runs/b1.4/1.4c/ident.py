"""1.4c's identity for the simulator (fixed seed, random actions, 1.4b's simulator settings, on the CPU, each side a process of
its own):
  1. the code at git HEAD against today's with nothing new set, and with a keep column of -1 everywhere (the lock rule decides
     every reading): inputs, pay, round ends, r_long, changes of target and counters the same to the bit;
  2. BLIND_FIRE_W=0: the game the same to the bit; the pay higher by exactly BLIND_FIRE_COST a billed frame, nothing else;
  3. a keep column of 0 everywhere (keep): no target changes at a reading that is not forced; of 1 everywhere (re-decide): every
     reading not forced counts, as the lock at 0 would; of random 0/1: the game differs and the readings his choice decided are counted.
Data and tables are read from the main repo (this file runs in a worktree without data links).
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4c\\ident.py > docs\\runs\\b1.4\\1.4c\\ident.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")
CMD = os.path.join(MAIN, "docs", "runs", "b1.4", "1.4b", "train.cmd")
RUN0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_4b")
FRAMES = 3000


def side(mod_path, mp, out, mode):
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    sys.path.insert(0, os.path.join(MAIN, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1")
    envv.pop("BLIND_FIRE_W", None)
    if mode == "bf0":
        envv["BLIND_FIRE_W"] = "0"
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(MAIN, "sim", "duel_env_ffa.py")
    spec.loader.exec_module(E)
    nav_ = os.path.join(MAIN, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(MAIN, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.8, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    krng = np.random.default_rng(99)                     # (the keep column's own stream: the actions' stays the same)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L, CH, KL, LV, FC, NI = [], [], [], [], [], [], [], [], []
    for _ in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        k_ = None
        if mode == "km1":
            k_ = np.full(env.n, -1)
        elif mode == "k0":
            k_ = np.zeros(env.n, np.int64)
        elif mode == "k1":
            k_ = np.ones(env.n, np.int64)
        elif mode == "krand":
            k_ = (krng.random(env.n) < 0.5).astype(np.int64)
        if k_ is not None:
            a = np.concatenate([a, k_[:, None]], 1)
        prev = env.intent.copy()
        forced = (env.intent == 0) | env.intent_done | env.intent_gone | env.intent_new
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        CH.append((env.intent != prev).copy())
        KL.append(env.keep_live.copy() if hasattr(env, "keep_live") else np.zeros(env.n, bool))
        LV.append(env.intent_live.copy())
        FC.append(forced)
        NI.append(env.intent.copy())
        if hasattr(env, "keep_feat"):
            f_ = env.keep_feat()
            assert f_.shape == (env.n, 3) and np.isfinite(f_).all()
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), ch=np.stack(CH), kl=np.stack(KL), lv=np.stack(LV),
             fc=np.stack(FC), ni=np.stack(NI), bfc=float(E.BLIND_FIRE_COST), **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="i14c_ident_")
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
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("km1", now, "km1"), ("bf0", now, "bf0"),
                                ("k0", now, "k0"), ("k1", now, "k1"), ("krand", now, "krand")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H, N = res["head"], res["now"]
        for name in ("now", "km1"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl", "ch")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            same["no keep decided"] = not B["kl"].any()
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        S = res["bf0"]
        check("{} blind-fire cost 0: the game the same".format(mp), all(np.array_equal(N[k], S[k]) for k in ("obs", "done", "ch", "rl")))
        d_ = S["rew"] - N["rew"]
        q_ = d_ / float(N["bfc"])
        whole = bool(np.abs(q_ - np.round(q_)).max() < 1e-3) and bool((np.round(q_) >= 0).all())
        print("{} blind-fire cost 0: pay up {:.4f} in {} frames ({} billed frames; the counter: {})".format(
            mp, d_.sum(), int((np.abs(d_) > 1e-9).sum()), int(np.round(q_).sum()), int(N["st_blind_bill"].sum())), flush=True)
        check("{} blind-fire cost 0: every difference a whole number of the cost, none negative, some".format(mp), whole and d_.sum() > 0)
        K0, K1, KR = res["k0"], res["k1"], res["krand"]
        nf0 = ~K0["fc"]
        ch_nf0 = K0["ch"] & nf0
        bad0 = ch_nf0 & (K0["ni"] != 0)                  # (a change to "nothing" in the same step is a death or a round's end, not a reading)
        print("{} keep everywhere: readings his choice decided {}, target changes where not forced {} (to nothing: {}), forced readings {}".format(
            mp, int(K0["kl"].sum()), int(ch_nf0.sum()), int((ch_nf0 & (K0["ni"] == 0)).sum()), int((K0["lv"] & K0["fc"]).sum())), flush=True)
        check("{} keep everywhere: his choice decided readings; no change of target where not forced but resets to nothing".format(mp),
              K0["kl"].sum() > 0 and int(bad0.sum()) == 0)
        nf1 = ~K1["fc"]
        lv1, kl1 = K1["lv"] & nf1, K1["kl"]
        print("{} re-decide everywhere: readings decided {}, of them counted {}; changes of target {} (unset: {})".format(
            mp, int(kl1.sum()), int((lv1 & kl1).sum()), int(K1["ch"].sum()), int(N["ch"].sum())), flush=True)
        check("{} re-decide everywhere: every reading his choice decided counted; more changes than the lock".format(mp),
              kl1.sum() > 0 and np.array_equal(lv1 & kl1, kl1) and K1["ch"].sum() > N["ch"].sum())
        kp_ = KR["st_keep"]
        print("{} random keep column: stats keep {}".format(mp, [int(x) for x in kp_]), flush=True)
        check("{} random keep column: the game differs; decided readings counted ({} = stats {})".format(mp, int(KR["kl"].sum()), int(kp_[3])),
              not np.array_equal(N["obs"], KR["obs"]) and int(KR["kl"].sum()) == int(kp_[3]) and kp_[3] > 0)
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

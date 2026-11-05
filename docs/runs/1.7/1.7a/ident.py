"""1.7a's identity for the simulator (fixed seed, random actions, 1.6a's simulator settings, on the CPU, each side a process of
its own):
  1. the code at git HEAD (1.6a's) against today's with nothing new set, with a keep column of -1 everywhere (the lock rule), and
     with the hand-over's coin always 0 (share 0) under random draws and keep readings: inputs, pay, round ends, r_long,
     changes of target and counters the same to the bit, no reading decided by the keep choice;
  2. share 1, keep everywhere (the coin 1, a keep reading every 8th frame, d 0): his seconds are the keep choice's, its readings
     five a second; no change of target where it had not ended (resets to "nothing" aside); arrivals stay his target;
  3. share 1, re-decide everywhere (d 1): every reading it decided counted; more changes of target than the lock;
  4. a random coin (share 0.5) and random draws: the game differs; the decided readings are the counter's (stats keep2); about
     half his seconds the keep choice's; keep_feat() 7 finite columns;
  5. (1.7, the combat order) COMBAT=1 with the order never asked (q 0, random o): the same to the bit as HEAD; asked at every
     reading with random choices, the keep choice at share 1, a brain's answer made from the truth (the enemy's place, and ahead
     by his speed): every kind chosen and followed, the drawn target not applied under an order, arrivals for cut off and spam,
     break off ended at its item, damage counted by kind.
Data and tables are read from the main repo (this file runs in a worktree without data links).
    docs\\runs\\1.7\\1.7a\\ident.py > docs\\runs\\1.7\\1.7a\\ident.log   (on the cores the owner gave: the scratchpad's run17.cmd)"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")
CMD = os.path.join(MAIN, "docs", "runs", "1.6", "1.6a", "train.cmd")
RUN0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_6a")
FRAMES = int(os.environ.get("IDENT_FRAMES") or 3000)
KR_EVERY = 8                                                 # (the head's tick: a keep reading on every 8th frame)


def settings():
    """1.6a's simulator settings, read once (its live files move while it trains: the sides must share one reading)"""
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1")
    return envv


def side(mod_path, mp, out, mode, sets=""):
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    sys.path.insert(0, os.path.join(MAIN, "sim"))
    envv = json.load(open(sets)) if sets else settings()
    if mode.startswith("cmb"):
        envv = dict(envv, COMBAT="1")
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(ROOT, "sim", "duel_env_ffa.py")      # (its tables: this checkout's sim/, the order's maps with them)
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
    O, R, Dn, L, CH, KL, LV, FC, NI, AR, KO, KC, CK, CL, VA, CO = [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []
    for f in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        k_ = None
        r_ = 4 * int(f % KR_EVERY == 0)
        if mode == "km1":
            k_ = np.full(env.n, -1)
        elif mode == "k0s":                              # share 0: the coin never; random draws, keep readings
            k_ = (krng.random(env.n) < 0.5).astype(np.int64) + r_
        elif mode == "k1keep":
            k_ = np.full(env.n, 2 + r_, np.int64)
        elif mode == "k1re":
            k_ = np.full(env.n, 3 + r_, np.int64)
        elif mode == "krand":
            k_ = (krng.random(env.n) < 0.5).astype(np.int64) + 2 * (krng.random(env.n) < 0.5).astype(np.int64) + r_
        elif mode == "cmbq0":                            # the order never asked: its fields random, q 0, the keep choice at share 0
            k_ = (krng.random(env.n) < 0.5).astype(np.int64) + r_ + 8 * krng.integers(0, 4, env.n) + 32 * krng.integers(0, 8, env.n)
        elif mode == "cmb":                              # asked at every reading, random kinds and candidates, the keep choice at share 1
            if f % KR_EVERY == 0:                        # (the keep reading: the candidates made after the tick's frame)
                X_, C_, P_ = env.order_feat()
                assert X_.shape == (env.n, E.CMB_ROWS, E.CMB_F) and np.isfinite(X_).all() and np.isfinite(C_).all() and np.isfinite(P_).all()
                VA.append(X_[:, :, E.CMB_FEAT.index("valid")].mean(0))
            k_ = (krng.random(env.n) < 0.3).astype(np.int64) + 2 + r_ + 8 * krng.integers(0, 4, env.n) + 32 * krng.integers(0, 8, env.n) + 256
            if f == 0:
                env._brain_init()
                env.brain_g[:] = 1.0
                env.brain_life[:] = True
            op_ = np.arange(env.n) ^ 1
            pos_, vel_ = env.state[op_, :3].astype(np.float32), env.state[op_, 3:6].astype(np.float32)
            fut_ = np.stack([pos_ + vel_ * h_ for h_ in (1.0, 2.0, 4.0)], 1)
            env.brain_in(dict(bel=pos_, ok=np.ones(env.n, bool), band=np.zeros((env.n, 4), np.float32), ztop=np.full(env.n, -1), fut=fut_))
        if k_ is not None:
            a = np.concatenate([a, k_[:, None]], 1)
        prev = env.intent.copy()
        arr0 = getattr(env, "intent_arr", np.zeros(env.n, bool))
        arr_ = arr0 & ~env.intent_new & ~env.intent_gone & (env.intent > 0)
        ended = (env.intent == 0) | (env.intent_done & ~arr_) | env.intent_gone | env.intent_new
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        CH.append((env.intent != prev).copy())
        KL.append(env.keep_live.copy())
        LV.append(env.intent_live.copy())
        FC.append(ended)
        NI.append(env.intent.copy())
        AR.append(arr_.copy())
        KO.append(getattr(env, "kown", np.zeros(env.n, bool)).copy())
        KC.append(np.full(env.n, -1, np.int64) if k_ is None else k_.copy())
        CK.append(getattr(env, "cmb_k", np.zeros(env.n, np.int64)).copy())
        CL.append(getattr(env, "cmb_live", np.zeros(env.n, bool)).copy())
        CO.append(getattr(env, "cmb_over", np.zeros(env.n, bool)).copy())
        if hasattr(env, "keep_feat"):
            f_ = env.keep_feat()
            assert f_.shape[0] == env.n and np.isfinite(f_).all()
            if hasattr(E, "KEEP_FEAT"):
                assert f_.shape == (env.n, E.KEEP_FEAT)
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), ch=np.stack(CH), kl=np.stack(KL), lv=np.stack(LV),
             fc=np.stack(FC), ni=np.stack(NI), ar=np.stack(AR), ko=np.stack(KO), kc=np.stack(KC), ck=np.stack(CK), cl=np.stack(CL), co=np.stack(CO),
             va=np.stack(VA) if VA else np.zeros((1, 1)), **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:7])
    tmp = tempfile.mkdtemp(prefix="i17a_ident_")
    sets = os.path.join(tmp, "settings.json")
    json.dump(settings(), open(sets, "w"))
    print("settings read once from 1.6a's command and its live files: {}".format(sets), flush=True)
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
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("km1", now, "km1"), ("k0s", now, "k0s"),
                                ("k1keep", now, "k1keep"), ("k1re", now, "k1re"), ("krand", now, "krand"), ("cmbq0", now, "cmbq0"),
                                ("cmb", now, "cmb")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode, sets], env=env)
            res[name] = np.load(o_)
        H, N = res["head"], res["now"]
        for name in ("now", "km1", "k0s", "cmbq0"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("rew", "done", "rl", "ch")}
            k0_ = H["obs"].shape[-1]                         # (1.7: the hands' N_ORD inputs appended: HEAD's columns to the bit; the
            same["obs"] = bool(np.array_equal(H["obs"], B["obs"][..., :k0_]))     # new ones zero with COMBAT off)
            if not name.startswith("cmb"):
                same["new inputs zero"] = not B["obs"][..., k0_:].any()
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            same["no keep decided"] = not B["kl"].any() and not B["ko"].any()
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        K0, K1, KR = res["k1keep"], res["k1re"], res["krand"]
        F_ = K0["ko"].shape[0]
        own0 = float(K0["ko"][60:].mean())                # (after every seat's first lock reading)
        rd0 = (K0["kl"] | (K0["lv"] & K0["fc"]))[60:]
        ps0 = float(rd0.sum()) / max(1.0, float(K0["ko"][60:].sum())) * 40.0
        print("{} keep everywhere: his seconds the keep choice's {:.3f}; its readings {:.2f} a second (decided {}, forced {})".format(
            mp, own0, ps0, int(K0["kl"].sum()), int((K0["lv"] & K0["fc"]).sum())), flush=True)
        check("{} keep everywhere: all his seconds the keep choice's; about five readings a second".format(mp), own0 > 0.999 and 4.5 < ps0 < 5.6)
        nf0 = ~K0["fc"] & K0["ko"]                       # (in the keep choice's seconds: before a seat's first lock reading the lock rule reads)
        ch_nf0 = K0["ch"] & nf0
        bad0 = ch_nf0 & (K0["ni"] != 0)
        arr_kept = int((K0["ar"] & K0["kl"]).sum())
        arr_ch = int((K0["ar"] & K0["kl"] & K0["ch"]).sum())
        print("{} keep everywhere: target changes where not ended {} (to nothing: {}); arrivals read {} times, changed {}; changes {} (lock: {})".format(
            mp, int(ch_nf0.sum()), int((ch_nf0 & (K0["ni"] == 0)).sum()), arr_kept, arr_ch, int(K0["ch"].sum()), int(N["ch"].sum())), flush=True)
        check("{} keep everywhere: no change where not ended but resets to nothing; arrivals never changed".format(mp),
              K0["kl"].sum() > 0 and int(bad0.sum()) == 0 and arr_ch == 0)
        nf1 = ~K1["fc"]
        lv1, kl1 = K1["lv"] & nf1, K1["kl"]
        print("{} re-decide everywhere: readings decided {}, of them counted {}; changes of target {} (lock: {})".format(
            mp, int(kl1.sum()), int((lv1 & kl1).sum()), int(K1["ch"].sum()), int(N["ch"].sum())), flush=True)
        check("{} re-decide everywhere: every reading his choice decided counted; more changes than the lock".format(mp),
              kl1.sum() > 0 and np.array_equal(lv1 & kl1, kl1) and K1["ch"].sum() > N["ch"].sum())
        k2_ = KR["st_keep2"] if "st_keep2" in KR.files else np.zeros(14)
        ownr = float(KR["ko"][60:].mean())
        print("{} random coin and draws: stats keep2 {}; his seconds the keep choice's {:.3f}".format(mp, [int(x) for x in k2_], ownr), flush=True)
        check("{} random coin and draws: the game differs; decided readings counted ({} = keep2 {}); about half his seconds".format(
            mp, int(KR["kl"].sum()), int(k2_[3])), not np.array_equal(N["obs"], KR["obs"]) and int(KR["kl"].sum()) == int(k2_[3]) and k2_[3] > 0
              and 0.4 < ownr < 0.6)
        ard_ = KR["ar"] & KR["kl"]
        kd_ = (KR["kc"] & 1) > 0
        kept_ch = int((ard_ & ~kd_ & KR["ch"]).sum())
        left_ = int((ard_ & kd_ & KR["lv"]).sum())
        print("{} random coin and draws: arrivals decided {} (kept {}, of them changed {}; re-decided {}, of them counted {})".format(
            mp, int(ard_.sum()), int((ard_ & ~kd_).sum()), kept_ch, int((ard_ & kd_).sum()), left_), flush=True)
        check("{} arrivals keepable: decided by the keep choice, kept ones never changed, re-decided ones counted".format(mp),
              ard_.sum() > 0 and kept_ch == 0 and left_ == int((ard_ & kd_).sum()))
        C = res["cmb"]
        nk_ = 4
        c_ = C["st_cmb"] if "st_cmb" in C.files else np.zeros(1 + 4 * nk_)
        ch_, fr_, ar_, dl_ = c_[1:1 + nk_], c_[1 + nk_:1 + 2 * nk_], c_[1 + 2 * nk_:1 + 3 * nk_], c_[1 + 3 * nk_:1 + 4 * nk_]
        print("{} the combat order: asked {}; chosen {}; frames {}; arrivals {}; damage {}".format(
            mp, int(c_[0]), [int(x) for x in ch_], [int(x) for x in fr_], [int(x) for x in ar_], [round(float(x)) for x in dl_]), flush=True)
        und_ = C["co"] & (C["ni"] != 8) & ~C["done"]     # (an order of a new kind: his target "the enemy", the drawn one not applied;
        #                                                  a reset on that frame ends it: "nothing")
        rk_ = (C["ck"] > 0) & C["done"]                  # (... and its kind with it, before the next reading)
        print("{} the combat order: readings with an order {}, off the enemy without a reset {}; a kind left at a reset {}".format(
            mp, int(C["co"].sum()), int(und_.sum()), int(rk_.sum())), flush=True)
        va_ = C["va"].mean(0)
        print("{} the combat order's candidates valid (share of seats): targets {}, cut off {}, spam {}, break off {}, ways {}".format(
            mp, va_[:17].round(2).tolist(), va_[17:20].round(2).tolist(), va_[20:28].round(2).tolist(), va_[28:36].round(2).tolist(), va_[36:].round(2).tolist()), flush=True)
        check("{} the combat order: every kind chosen and followed; arrivals for cut off, spam, break off; no target learnt under an order".format(mp),
              (ch_ > 0).all() and (fr_[1:] > 0).all() and ar_[1] > 0 and ar_[2] > 0 and ar_[3] > 0 and not und_.any() and not rk_.any()
              and va_[17:36].max() > 0.5)
        print("{} frames {}".format(mp, F_), flush=True)
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

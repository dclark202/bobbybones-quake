"""1.7b's identity for the simulator (fixed seed, random actions, 1.7a's simulator settings: its command and live files, on the CPU, each
side a process of its own):
  1. the code at git HEAD (1.7a's) against today's with nothing new set: inputs (HEAD's 990 columns), pay, round ends, r_long, changes of
     target and counters the same to the bit; the 4 new inputs (the yellow armors' timers) lie in [0, 2] and are not all zero on a map
     with yellow armors
  2. FIGHT_TRUTH=1 (the fight odds' labels): the game the same to the bit as HEAD; labels only where a fight was on, each 0 or 1
  3. COMBAT=1 with the order never asked (q 0, random fields; the keep choice at share 0): the same to the bit as HEAD
  4. the order asked at every reading with random kinds and candidates, a brain's answer made from the truth (as 1.7a's ident), with and
     without OUT_LIVE=1.5: with it break off is reached (arrivals counted) by living through it, the game differs from without
    python docs\\runs\\1.7\\1.7b\\ident.py > docs\\runs\\1.7\\1.7b\\ident.log   (on the efficiency cores, below normal)"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
CMD = os.path.join(ROOT, "docs", "runs", "1.7", "1.7a", "train.cmd")
RUN0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a")
FRAMES = int(os.environ.get("IDENT_FRAMES") or 3000)
KR_EVERY = 8


def settings():
    """1.7a's simulator settings, read once"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1")
    return envv


def side(mod_path, mp, out, mode, sets=""):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    envv = json.load(open(sets)) if sets else settings()
    envv = dict(envv, COMBAT="1")
    if mode == "fight":
        envv = dict(envv, FIGHT_TRUTH="1")
    if mode == "cmbout":
        envv = dict(envv, OUT_LIVE="1.5")
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa_id", mod_path)
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa_id"] = E
    E.__file__ = os.path.join(ROOT, "sim", "duel_env_ffa.py")      # (its tables: this checkout's sim/)
    spec.loader.exec_module(E)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.8, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    krng = np.random.default_rng(99)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L, CH, FW, FL = [], [], [], [], [], [], []
    C_ = {k_: i_ for i_, k_ in enumerate(E.AUX_COLS)}
    for f in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        k_ = None
        r_ = 4 * int(f % KR_EVERY == 0)
        if mode == "cmbq0":                                  # the order never asked: its fields random, q 0, the keep choice at share 0
            k_ = (krng.random(env.n) < 0.5).astype(np.int64) + r_ + 8 * krng.integers(0, 4, env.n) + 32 * krng.integers(0, 8, env.n)
        elif mode in ("cmb", "cmbout"):                      # asked at every reading, random kinds and candidates, the keep choice at share 1
            if f % KR_EVERY == 0:
                env.order_feat()
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
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
        L.append(np.asarray(info["r_long"], np.float32))
        CH.append((env.intent != prev).copy())
        if "fo_win" in C_:
            FW.append(np.asarray(info["aux"])[:, C_["fo_win"]].copy())
            FL.append(np.asarray(info["aux"])[:, C_["fo_lose"]].copy())
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), ch=np.stack(CH),
             fw=np.stack(FW) if FW else np.zeros((1, 1)), fl=np.stack(FL) if FL else np.zeros((1, 1)), **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:7])
    tmp = tempfile.mkdtemp(prefix="i17b_ident_")
    sets = os.path.join(tmp, "settings.json")
    json.dump(settings(), open(sets, "w"))
    print("settings read once from 1.7a's command and its live files: {}".format(sets), flush=True)
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
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("fight", now, "fight"), ("headq0", head, "cmbq0"),
                                ("cmbq0", now, "cmbq0"), ("cmb", now, "cmb"), ("cmbout", now, "cmbout")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode, sets], env=env)
            res[name] = np.load(o_)
        H = res["head"]
        k0_ = H["obs"].shape[-1]
        for name, ref in (("now", "head"), ("fight", "head"), ("cmbq0", "headq0")):
            B, H_ = res[name], res[ref]
            same = {k: bool(np.array_equal(H_[k], B[k])) for k in ("rew", "done", "rl", "ch")}
            same["obs (HEAD's {} columns)".format(k0_)] = bool(np.array_equal(H_["obs"], B["obs"][..., :k0_]))
            same["counters"] = all(k in B.files and np.array_equal(H_[k], B[k]) for k in H_.files if k.startswith("st_"))
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        N = res["now"]
        yt_ = N["obs"][..., k0_:]
        print("{} the yellow timers: {} columns, known-taken share {:.3f} / {:.3f}, values in [{:.3f}, {:.3f}]".format(
            mp, yt_.shape[-1], float(yt_[..., 0].mean()), float(yt_[..., 2].mean()), float(yt_.min()), float(yt_.max())), flush=True)
        check("{} the yellow timers: 4 columns in [0, 2], known some of the time".format(mp),
              yt_.shape[-1] == 4 and yt_.min() >= 0.0 and yt_.max() <= 2.0 and float(yt_[..., 0].mean()) > 0.01)
        Fg = res["fight"]
        w_, l_ = Fg["fw"], Fg["fl"]
        lab_ = w_ >= 0
        print("{} the fight labels: frames with a label {:.4f} of all; of them win {:.3f}, lose {:.3f}, both {:.3f}, neither {:.3f}".format(
            mp, float(lab_.mean()), float((w_[lab_] == 1).mean()) if lab_.any() else 0.0, float((l_[lab_] == 1).mean()) if lab_.any() else 0.0,
            float(((w_ == 1) & (l_ == 1))[lab_].mean()) if lab_.any() else 0.0, float(((w_ == 0) & (l_ == 0))[lab_].mean()) if lab_.any() else 0.0), flush=True)
        check("{} the fight labels: some frames labelled, every label 0 or 1, unlabelled -1 on both".format(mp),
              lab_.any() and np.isin(w_[lab_], (0.0, 1.0)).all() and np.isin(l_[lab_], (0.0, 1.0)).all() and ((l_ >= 0) == lab_).all())
        nk_ = 4
        for name in ("cmb", "cmbout"):
            c_ = res[name]["st_cmb"] if "st_cmb" in res[name].files else np.zeros(1 + 4 * nk_)
            print("{} {}: the order asked {}; chosen {}; frames {}; arrivals {}".format(
                mp, name, int(c_[0]), [int(x) for x in c_[1:1 + nk_]], [int(x) for x in c_[1 + nk_:1 + 2 * nk_]],
                [int(x) for x in c_[1 + 2 * nk_:1 + 3 * nk_]]), flush=True)
        c0_, c1_ = res["cmb"]["st_cmb"], res["cmbout"]["st_cmb"]
        print("{} OUT_LIVE: the frames {} (an arrival changes what the keep choice reads, not the frames, while the keep column is drawn as here)".format(
            mp, "differ" if not np.array_equal(res["cmb"]["obs"], res["cmbout"]["obs"]) else "the same"), flush=True)
        check("{} OUT_LIVE: break off arrived by living through it, more often than at its ways out (arrivals {} -> {}); the other kinds' as before".format(
            mp, int(c0_[1 + 2 * nk_ + 3]), int(c1_[1 + 2 * nk_ + 3])),
              c1_[1 + 2 * nk_ + 3] > c0_[1 + 2 * nk_ + 3] and np.array_equal(c0_[1 + 2 * nk_:1 + 2 * nk_ + 3], c1_[1 + 2 * nk_:1 + 2 * nk_ + 3]))
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

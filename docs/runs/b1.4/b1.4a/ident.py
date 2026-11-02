"""b1.3a's identity (fixed seed, random actions, the run's simulator settings, on the CPU, each side a process of its own):
  1. the code at git HEAD against today's with both switches off, and with CONTACT_FREE set to 0 live: inputs, pay, round ends, r_long and counters the same to the bit;
  2. DMG_ENEMY_ONLY=1 at weight 1: the game the same to the bit, the pay the same within rounding;
  3. at weight 0.65: enemy-only costs less than at weight 1, and more than the weight on all damage, by exactly what his own damage is worth;
  4. CONTACT_FREE=1 live: contacts counted, target changes up, the rule's lesson silent in them; the game differs.
Data and tables are read from the main repo when this file runs in a worktree.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.3\\b1.3a\\ident.py > docs\\runs\\b1.3\\b1.3a\\ident.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = ROOT if os.path.isdir(os.path.join(ROOT, "data")) else os.path.join(os.path.dirname(ROOT), "BobbyBones")
CMD = os.path.join(MAIN, "docs", "runs", "b1.2", "b1.2a", "train.cmd")
RUN0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_v0_6_0")
FRAMES = 3000


def side(mod_path, mp, out, mode):
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    sys.path.insert(0, os.path.join(MAIN, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33", PAY_SPLIT="1")
    if "enemy" in mode:
        envv["DMG_ENEMY_ONLY"] = "1"
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
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.65 if "65" in mode else 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    if "live0" in mode:
        E.live_set({"CONTACT_FREE": "0"})
    if "contact" in mode:
        E.live_set({"CONTACT_FREE": "1"})
        assert E.CONTACT_FREE == 1.0
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L, Tm = [], [], [], [], []
    ch = sil = 0
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
        if env.ct_free is not None if hasattr(env, "ct_free") else False:
            assert (env.intent_teach[env.ct_free & (env.script[:env.n] == 0)] == -1).all() or "contact" not in mode, "the rule spoke in a free contact"
            sil += int(env.ct_free.sum())
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), changes=ch, silent=sil, **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b13a_ident_")
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
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("live0", now, "live0"), ("all65", now, "w65"), ("enemy1", now, "enemy"), ("enemy65", now, "enemy65"), ("contact", now, "contact")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H = res["head"]
        for name in ("now", "live0"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl", "changes")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        N, E1, E65, A65 = res["now"], res["enemy1"], res["enemy65"], res["all65"]
        check("{} enemy-only at 1: the game the same".format(mp), np.array_equal(N["obs"], E1["obs"]) and np.array_equal(N["done"], E1["done"]))
        check("{} enemy-only at 1: the pay within rounding (largest {:.2e})".format(mp, np.abs(N["rew"] - E1["rew"]).max()), np.abs(N["rew"] - E1["rew"]).max() < 1e-5)
        check("{} enemy-only at 0.65: the game the same".format(mp), np.array_equal(N["obs"], E65["obs"]))
        s65, sall, s1 = E65["rew"].sum(), A65["rew"].sum(), N["rew"].sum()
        print("{} total pay: weight 1 {:.3f}, enemy-only 0.65 {:.3f}, all damage 0.65 {:.3f}".format(mp, s1, s65, sall), flush=True)
        check("{} enemy-only 0.65 pays above weight 1 and below the weight on all damage".format(mp), s1 < s65 < sall)
        C = res["contact"]
        cs = C["st_contact"]
        print("{} contact counters (begun, free, readings, changes, to the enemy): {}; frames silent {}; target changes {} against {}".format(mp, cs.tolist(), int(C["silent"]), int(C["changes"]), int(N["changes"])), flush=True)
        check("{} contacts counted and all free".format(mp), cs[0] > 0 and cs[1] == cs[0])
        check("{} target changes up, the game differs, the rule silent in them".format(mp), int(C["changes"]) > int(N["changes"]) and not np.array_equal(N["obs"], C["obs"]) and int(C["silent"]) > 0)
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

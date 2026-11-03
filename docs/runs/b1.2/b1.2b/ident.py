"""b1.2b's identity (fixed seed, random actions, the run's simulator settings, on the CPU, each side a process of its own):
  1. the code at git HEAD against today's with every new switch off, and with the new dials set to their shut values live: inputs, pay, round ends, r_long and counters the same to the bit;
  2. the table on: the game the same; small items paid; a match's item pay zero-sum to rounding; the pay is points x rate;
  3. COST_FIRE_W 0: the game the same; the shot price, fire toggle and weapon switch terms nothing, jerk as before;
  4. COST_JERK_W 0: the game the same; the jerk term nothing, the firing terms as before;
  5. CONTACT_FREE 1 live: contacts counted and all free; target changes up; the rule's label silent in them, from the first reading; the game differs.
Data and tables are read from the main repo when this file runs in a worktree.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2b\\ident.py > docs\\runs\\b1.2\\b1.2b\\ident.log"""
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
    if mode == "rate":
        envv.update(ITEM_RATE_HP="0.0025", ITEM_RATE_AR="0.002")
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
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    if mode == "shut":
        E.live_set({"CONTACT_FREE": "0", "COST_FIRE_W": "1", "COST_JERK_W": "1", "ITEM_RATE_HP": "0", "ITEM_RATE_AR": "0"})
    if mode == "fire0":
        E.live_set({"COST_FIRE_W": "0"})
        assert E.COST_FIRE_W == 0.0
    if mode == "jerk0":
        E.live_set({"COST_JERK_W": "0"})
        assert E.COST_JERK_W == 0.0
    if mode == "contact":
        E.live_set({"CONTACT_FREE": "1"})
        assert E.CONTACT_FREE == 1.0
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn, L = [], [], [], []
    T = list(E.PAY_TERMS)
    IT = [T.index(k_) for k_ in ("item_MH", "item_RA", "item_YA", "item_flat_other")]
    terms = np.zeros(len(T))
    net, pos = 0.0, 0.0
    ch, sil = 0, 0
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
        if mode == "contact" and env.ct_free is not None:
            m_ = env.ct_free & (env.script[:env.n] == 0)
            assert (env.intent_teach[m_] == -1).all(), "the rule spoke in a free contact"
            sil += int(m_.sum())
        pt = np.asarray(info["pay_terms"], np.float64)
        terms += np.abs(pt).sum(0)
        ip_ = pt[:, IT].sum(1)
        net = max(net, float(np.abs(ip_.reshape(-1, 2).sum(1)).max()))      # (duels: a match's two seats)
        pos += float(np.maximum(ip_, 0.0).sum())
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), rl=np.stack(L), terms=terms, names=np.array(T), item_net=net, item_pos=pos, changes=ch, silent=sil, **stv)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b12b_ident_")
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
        for name, mod, mode in (("head", head, "none"), ("now", now, "none"), ("shut", now, "shut"), ("rate", now, "rate"), ("fire0", now, "fire0"), ("jerk0", now, "jerk0"), ("contact", now, "contact")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H, N = res["head"], res["now"]
        for name in ("now", "shut"):
            B = res[name]
            same = {k: bool(np.array_equal(H[k], B[k])) for k in ("obs", "rew", "done", "rl")}
            same["counters"] = all(k in B.files and np.array_equal(H[k], B[k]) for k in H.files if k.startswith("st_"))
            check("{} HEAD against {}: {}".format(mp, name, same), all(same.values()))
        Rt = res["rate"]
        pb = Rt["st_pick_by"]
        want = 0.0025 * pb[8:12].sum() + 0.002 * pb[12:16].sum()
        print("{} pickups H5 H25 H50 MH A5 A25 A50 A100: {}; points: {}; the item pay {:.3f}, points x rate {:.3f}; a match's largest item net {:.2e}".format(mp, pb[:8].tolist(), pb[8:].tolist(), float(Rt["item_pos"]), want, float(Rt["item_net"])), flush=True)
        check("{} the table: the game the same".format(mp), np.array_equal(N["obs"], Rt["obs"]))
        check("{} small items picked up and paid".format(mp), pb[0] + pb[1] + pb[2] + pb[4] + pb[5] > 0 and float(Rt["item_pos"]) > 0)
        check("{} the item pay zero-sum".format(mp), float(Rt["item_net"]) < 1e-5)
        check("{} the pay is points x rate".format(mp), abs(float(Rt["item_pos"]) - want) < 1e-3 * max(1.0, want))
        T = [str(x) for x in N["names"]]
        tm = lambda R_, k_: float(R_["terms"][T.index(k_)])  # noqa: E731
        fire = ("shot_price", "fire_toggle", "weapon_switch")
        print("{} the terms, off: {}".format(mp, {k: round(tm(N, k), 3) for k in fire + ("jerk",)}), flush=True)
        check("{} the three firing terms were there".format(mp), all(tm(N, k) > 0 for k in fire))
        C = res["contact"]
        cs = C["st_contact"]
        print("{} contact (begun, free, readings, changes, to the enemy): {}; frames silent {}; target changes {} against {}".format(mp, cs.tolist(), int(C["silent"]), int(C["changes"]), int(N["changes"])), flush=True)
        check("{} contacts counted and all free".format(mp), cs[0] > 0 and cs[1] == cs[0])
        check("{} target changes up, the game differs, the rule silent".format(mp), int(C["changes"]) > int(N["changes"]) and not np.array_equal(N["obs"], C["obs"]) and int(C["silent"]) > 0)
        F0, J0 = res["fire0"], res["jerk0"]
        check("{} COST_FIRE_W 0: the game the same, the three terms nothing, jerk as before".format(mp), np.array_equal(N["obs"], F0["obs"]) and all(tm(F0, k) == 0 for k in fire) and abs(tm(F0, "jerk") - tm(N, "jerk")) < 1e-6)
        print("{} COST_JERK_W 0: game same {}, jerk {}, the three's differences {} (a term is a difference of float32 running pay, so rounding moves with what came before it)".format(mp, np.array_equal(N["obs"], J0["obs"]), tm(J0, "jerk"), [tm(J0, k) - tm(N, k) for k in fire]), flush=True)
        check("{} COST_JERK_W 0: the game the same, jerk nothing, the three as before to rounding".format(mp), np.array_equal(N["obs"], J0["obs"]) and tm(N, "jerk") > 0 and tm(J0, "jerk") == 0 and all(abs(tm(J0, k) - tm(N, k)) < 1e-4 * max(1.0, tm(N, k)) for k in fire))
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

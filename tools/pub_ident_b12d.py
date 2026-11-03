"""The public build for b1.2d (main merged into pub-perf, 2026-11-02) against main's simulator: fixed seed, random actions, b1.2d's end
settings, the group module the servers use; each side a process with its own sim/ first on the path. Inputs, pay and round ends
must be the same to the bit (pub-perf's speed-ups were proven bit-identical on their own; this proves the merge kept that).
    python tools/pub_ident_b12d.py <main checkout> <this checkout> [map ...]"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

FRAMES = 2400


def side(code, data_root, mp, out):
    sys.path.insert(0, os.path.join(code, "tools"))
    sys.path.insert(0, os.path.join(code, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(os.path.join(data_root, "docs", "runs", "b1.2", "b1.2d", "train.cmd"), os.path.join(data_root, "data", "sim_runs", "duel_gru_b1_2d"))
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(data_root, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33",
                ITEM_RATE_HP="0.0025", ITEM_RATE_AR="0.002", COST_FIRE_W="0", COST_JERK_W="0", CONTACT_FREE="1", ITEM_PT_MIX="1",
                SPEED_PAY="0.125", STACK_DIFF="0", RAIL_FAR_PAY="0.25", LEVEL_PULL="1")
    os.environ.update(envv)
    spec = importlib.util.spec_from_file_location("duel_env_ffa", os.path.join(code, "sim", "duel_env_ffa.py"))
    E = importlib.util.module_from_spec(spec)
    sys.modules["duel_env_ffa"] = E
    spec.loader.exec_module(E)
    nav_ = os.path.join(data_root, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(data_root, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.8, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn = [], [], []
    for f in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        if f % 4 == 0:
            O.append(obs.astype(np.float32))
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(Dn), dim=np.array(obs.shape[1]))


def main():
    if sys.argv[1] == "--side":
        side(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return 0
    main_co, this_co = sys.argv[1], sys.argv[2]
    maps = sys.argv[3:] or ["bloodrun", "aerowalk"]
    ok = True
    for mp in maps:
        res = {}
        for lab, co in (("main", main_co), ("pub", this_co)):
            out = os.path.join(tempfile.gettempdir(), "pub_ident_{}_{}.npz".format(lab, mp))
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1")
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--side", co, main_co, mp, out], env=env, capture_output=True, text=True)
            if r.returncode:
                print(lab, mp, "FAILED:", r.stderr[-1500:])
                return 1
            res[lab] = np.load(out)
        a, b = res["main"], res["pub"]
        same = {k: bool(np.array_equal(a[k], b[k])) for k in ("obs", "rew", "done")}
        print("{}: {} inputs; {} frames; the same to the bit: {}".format(mp, int(a["dim"]), FRAMES, same), flush=True)
        ok = ok and all(same.values())
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""b1.2d's check of the table by the point (fixed seed, random actions, b1.2c's settings, the CPU; each side a process), on the group module the run uses:
  1. off: inputs, pay and round ends the same to the bit as the code at git HEAD (b1.2c's);
  2. the split: ITEM_PT_LO = ITEM_PT_HI = 0.0025 pays as ITEM_RATE_HP = ITEM_RATE_AR = 0.0025 at HEAD;
  3. on (b1.2d's values, SM_PASS): the game the same; the pay's change zero-sum in every frame; points counted at or under 100, above it, decayed;
  4. the live names read.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2d\\pay_check.py > docs\\runs\\b1.2\\b1.2d\\pay_check.log"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
CMD = os.path.join(ROOT, "docs", "runs", "b1.2", "b1.2c", "train.cmd")
RUN0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_0")
FRAMES = 2400
ON = dict(ITEM_PT_LO="0.004", ITEM_PT_HI="0.002", ITEM_DECAY="0.002", SM_PASS="1")
MODES = {"off": {}, "rate": dict(ITEM_RATE_HP="0.0025", ITEM_RATE_AR="0.0025"),
         "split": dict(ITEM_RATE_HP="0", ITEM_RATE_AR="0", ITEM_PT_LO="0.0025", ITEM_PT_HI="0.0025"), "on": ON}


def side(mod_path, mp, out, mode):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import winpay_games as WG
    envv, _ = WG.run_env(CMD, RUN0)
    envv.update(STAGGER_START="1", WIN_JUDGE=os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz"), WIN_END="1", WIN_ADD="0.33",
                ITEM_RATE_HP="0.0025", ITEM_RATE_AR="0.002", COST_FIRE_W="0", COST_JERK_W="0", CONTACT_FREE="1")
    envv.update(MODES[mode])
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
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, Dn = [], [], []
    for f in range(FRAMES):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32) if f % 4 == 0 else O[-1])
        R.append(np.array(rew, np.float64))
        Dn.append(done.copy())
    st = env.stats
    x = dict(obs=np.stack(O[::4]), rew=np.stack(R), done=np.stack(Dn), n=env.n,
             item_pt=np.array(st.get("item_pt", np.zeros(3)), np.float64), sm_pass=np.array(st.get("sm_pass", np.zeros(10)), np.float64))
    if mode == "on":
        lv = E.live_values(lambda k: dict(ON, ITEM_RATE_HP="0.0025").get(k) or os.environ.get(k))
        x["live"] = np.array([lv["ITEM_PT_LO"], lv["ITEM_PT_HI"], lv["ITEM_DECAY"]])
    np.savez(out, **x)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--side":
        return side(*sys.argv[2:6])
    tmp = tempfile.mkdtemp(prefix="b12d_pay_")
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
        for name, mod, mode in (("head", head, "off"), ("off", now, "off"), ("head_rate", head, "rate"), ("split", now, "split"), ("on", now, "on")):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, name))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--side", mod, mp, o_, mode], env=env)
            res[name] = np.load(o_)
        H, O, HR, S, N = res["head"], res["off"], res["head_rate"], res["split"], res["on"]
        check("{} off: inputs, pay and ends as HEAD".format(mp), np.array_equal(H["obs"], O["obs"]) and np.array_equal(H["rew"], O["rew"]) and np.array_equal(H["done"], O["done"]))
        d_ = float(np.abs(HR["rew"] - S["rew"]).max())
        check("{} the split at one rate pays as HEAD's rate (largest difference {:.1e})".format(mp, d_), d_ < 1e-6 and np.array_equal(HR["obs"], S["obs"]))
        check("{} on: the game the same".format(mp), np.array_equal(O["obs"], N["obs"]) and np.array_equal(O["done"], N["done"]))
        n = int(N["n"])
        dd = (N["rew"] - O["rew"]).reshape(FRAMES, n // 2, 2).sum(2)
        check("{} on: the change in pay zero-sum in every frame (largest match sum {:.1e})".format(mp, float(np.abs(dd).max())), float(np.abs(dd).max()) < 1e-5)
        pm_ = n * FRAMES * 0.025 / 60.0
        ip = N["item_pt"] / pm_
        check("{} on: points a player-minute: to 100 {:.1f}, over 100 {:.1f}, decayed {:.1f} (charged back: never more than was paid above 100)".format(mp, *ip), ip[0] + ip[1] > 0 and 0 < ip[2] <= ip[1] + 1e-9)
        sp = N["sm_pass"]
        print("{} on: small places near his way (random play): {} passes, {} taken ({:.0%})".format(mp, int(sp[:5].sum()), int(sp[5:].sum()), sp[5:].sum() / max(1, sp[:5].sum())), flush=True)
        check("{} on: passes counted, taken no more than passes".format(mp), sp[:5].sum() > 0 and (sp[5:] <= sp[:5]).all())
        check("{} the live names read ({})".format(mp, list(N["live"])), list(N["live"]) == [0.004, 0.002, 0.002])
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

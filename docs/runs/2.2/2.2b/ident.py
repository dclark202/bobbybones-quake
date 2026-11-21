"""2.2b's identity test: the start (tools/fight22_init.py norm's; list 22b, the rater out, the fight network in, every new dial at 0) answers as
2.2a's update 90 on recorded play. 2.2a's update 90 plays every seat of a few matches in the simulator (2.2a's settings, FIGHT=1 so the fight
options' numbers and the hands' new columns are real), every frame recorded (his inputs, the keep rows, his pose, the legs' inputs, the fight
options' numbers at each keep reading); then both networks replay the recording from the same seeds (the checks' player, sim/test_suite.py):
every action, the keep column, the memory (his, the head's, the brain's), and the largest logit difference. PASS: 0 actions differ.
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2b/ident.py <policy_90.pt> <start.pt> [--maps bloodrun,toxicity]
        [--frames 1200] [--matches 16]"""
import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import legs_test as LT  # noqa: E402

ROOT = LT.ROOT


def record(pol, mp, frames, matches, seed):
    import importlib
    import btoken as BT
    import head2 as H2
    import test_suite as T
    import fight22 as F22
    E = importlib.import_module("duel_env_ffa")
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
    nav_ = os.path.join(LT.DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(LT.DATA, "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if getattr(E, "BRAIN_READ", False):
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    obs = env.observe()
    h = pol.zeros(env.n)
    rec = []
    for t in range(frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, mp)
        xl = env.legs_prep() if pol.needs_xl else None
        fx = F22.reader_fx(env) if (pol.k_r is not None and np.any(pol.k_r)) else None
        rec.append(dict(obs=np.asarray(obs, np.float32).copy(), kf=kf.copy(), pz=pz.copy(), zz=np.asarray(zz).copy(), xl=None if xl is None else xl.copy(), fx=fx))
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        nA = len(E.ACTION_DIMS)
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        an_ = pol.brain_answer(h)
        if an_ is not None:
            env.brain_in({k_: an_[k_] for k_ in ("bel", "ok", "band", "ztop") if k_ in an_})
        obs, r_, done, info = env.step(act)
        rec[-1]["done"] = np.asarray(done, bool).copy()
    return rec, now


def replay(pol, rec, now):
    idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
    n = len(rec[0]["obs"])
    h = pol.zeros(n)
    outs, logits, hs = [], [], []
    for f_ in rec:
        kw = {}
        if getattr(pol, "fight_due", False):
            assert f_["fx"] is not None, "the 2.2b network wants the fight options' numbers on a frame the recording has none"
            kw["fx"] = f_["fx"]
        ac, h = pol.act(f_["obs"][:, idx], h, xl=f_["xl"], pose=f_["pz"], zmap=f_["zz"], kf=f_["kf"], **kw)
        outs.append(ac.copy())
        logits.append(np.asarray(pol.last_logits, np.float32).copy())
        hs.append(h[:, :pol.H].copy())
        if f_["done"].any():
            pol.clear(h, f_["done"])
    return outs, logits, hs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--maps", default="bloodrun,toxicity")
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--seed", type=int, default=31)
    a = ap.parse_args()
    LT.setup()
    import test_suite as T
    tot, diff, kd, lmax, hmax = 0, 0, 0, 0.0, 0.0
    for mp in a.maps.split(","):
        rec, now = record(T.Policy(a.old, seed=a.seed), mp, a.frames, a.matches, a.seed)
        o1, l1, h1 = replay(T.Policy(a.old, seed=a.seed + 1), rec, now)
        o2, l2, h2 = replay(T.Policy(a.new, seed=a.seed + 1), rec, now)
        for x_, y_, la_, lb_, ha_, hb_ in zip(o1, o2, l1, l2, h1, h2):
            tot += x_[:, :-1].size
            diff += int((x_[:, :-1] != y_[:, :-1]).sum())
            kd += int((x_[:, -1] != y_[:, -1]).sum())
            lmax = max(lmax, float(np.abs(la_ - lb_).max()))
            hmax = max(hmax, float(np.abs(ha_ - hb_).max()))
        print("{}: {} frames x {} seats; actions that differ so far {} of {}; keep columns {}; largest logit difference {:.3g}; memory {:.3g}".format(
            mp, a.frames, len(rec[0]["obs"]), diff, tot, kd, lmax, hmax), flush=True)
    print("ident: actions that differ {} of {}; keep columns that differ {}; the largest logit difference {:.3g}; the largest memory difference {:.3g}".format(
        diff, tot, kd, lmax, hmax))
    print("ALL PASSED" if diff == 0 and kd == 0 else "FAILED")
    sys.exit(0 if diff == 0 and kd == 0 else 1)


if __name__ == "__main__":
    main()

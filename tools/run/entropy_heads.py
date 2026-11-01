"""Which of his choices grew less certain between saves (2026-10-31, b1.0a's entropy): one save plays itself in the simulator (the driver) while the other saves answer the same
frames, each with its own memory; per output, the mean entropy with the enemy in view and without, and the share of frames in view. Read only; on the CPU. Run it pinned to spare cores.
    python tools/run/entropy_heads.py --cmd <train.cmd> --run-dir <run folder> --out <dir> --saves name=path name=path ... [--maps a,b,c] [--frames 8000]"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAMES = ["forward", "strafe", "vertical", "turn", "pitch", "fire", "weapon", "walk", "zoom", "lift", "target", "legs", "way"]


def job(a, driver, mp, out):
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, trv = WG.run_env(a.cmd, a.run_dir)
    envv.update(WG.MEASURE)
    aim_ = os.path.join(os.path.dirname(os.path.abspath(a.cmd)), "aim2_env.cmd")    # (run_env reads the .cmd's own lines: the aim's file and the paths are set here)
    for line in open(aim_, encoding="utf-8", errors="replace"):
        s_ = line.strip()
        if s_.lower().startswith("set ") and "=" in s_:
            k_, v_ = s_[4:].split("=", 1)
            envv[k_.strip()] = v_.strip()
    envv["LEGS_NET"] = os.path.join(ROOT, "data", "sim_runs", "move_v17_look", "policy.npz")
    envv["WIN_JUDGE"] = os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz")
    os.environ.update(envv)
    import importlib
    import test_suite as T
    E = importlib.import_module("duel_env_ffa")
    S = dict(x.split("=", 1) for x in a.saves)
    P = {k: T.Policy(v, seed=11) for k, v in S.items()}
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=8, seed=5, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    n = env.n
    pd = P[driver]
    T.set_delays(E, env, [(np.arange(n), pd.react_ms, pd.acquire_ms)])
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.stack_p = env.near_item_p = env.drill_p = 0.0
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    if hasattr(env, "count_even"):
        env.count_even = True
    if hasattr(env, "legs_keep_who"):
        env.legs_keep_who = np.ones(n, bool)
    env.round_t[:] = 1e9
    env._teach_update()
    obs, _, done, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    H = {k: p.zeros(n) for k, p in P.items()}
    for k, p in P.items():
        p.clear(H[k], done)
    dims = [int(x) for x in pd.dims][:13]
    o_ = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    SUM = {k: np.zeros((2, len(dims))) for k in P}
    CNT = np.zeros(2)
    frags = 0
    import btoken as btoken_
    for f in range(a.frames):
        hev_ = env.head_events() if hasattr(env, "head_events") and pd.head_due(H[driver]).any() else None
        xl = env.legs_prep() if getattr(E, "LEGS_IN", False) and pd.needs_xl else None
        pz, zz = btoken_.pose_from_env(env, mp) if pd.needs_pose else (None, None)
        vis = np.asarray(env.visible, bool)[:n]
        act = None
        for k, p in P.items():
            kw = {"pose": pz, "zmap": zz} if p.needs_pose else {}
            ac_, H[k] = p.act(obs, H[k], hev_, xl=xl, **kw)
            if k == driver:
                act = ac_
            lg = p.last_logits
            for j in range(len(dims)):
                l_ = lg[:, o_[j]:o_[j + 1]]
                q = np.exp(l_ - l_.max(1, keepdims=True))
                q /= q.sum(1, keepdims=True)
                e_ = -(q * np.log(q + 1e-12)).sum(1)
                SUM[k][1, j] += e_[vis].sum()
                SUM[k][0, j] += e_[~vis].sum()
        CNT += (float((~vis).sum()), float(vis.sum()))
        if getattr(E, "BRAIN_READ", False):
            an_ = pd.brain_answer(H[driver])
            if an_ is not None:
                env.brain_in(an_)
        if getattr(E, "LEGS_IN", False) and pd.legsP is not None:
            env.legs_lg = pd.legs_logits(env.legs_prep())
        a_ = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a_[:, :min(act.shape[1], a_.shape[1])] = act[:, :a_.shape[1]]
        obs, _, done, info = env.step(a_)
        frags += len(info["events"])
        for k, p in P.items():
            p.clear(H[k], done)
    json.dump(dict(driver=driver, map=mp, frames=a.frames, cnt=CNT.tolist(), frags=frags, dims=dims, sum={k: v.tolist() for k, v in SUM.items()}), open(out, "w"))


def report(a):
    import glob
    R = [json.load(open(f)) for f in glob.glob(os.path.join(a.out, "eh_*.json"))]
    keys = [x.split("=", 1)[0] for x in a.saves]
    print("files", len(R), "| maps", sorted({r["map"] for r in R}))
    for d in sorted({r["driver"] for r in R}):
        Q = [r for r in R if r["driver"] == d]
        cnt = np.sum([r["cnt"] for r in Q], 0)
        mins = sum(r["frames"] for r in Q) * .025 / 60 * 8
        print("\nframes played by {}: enemy in view {:.1%} of frames; deaths {:.2f} a match-minute".format(d, cnt[1] / cnt.sum(), sum(r["frags"] for r in Q) / mins))
        print("  {:9s} {:>6s} |".format("output", "max") + "".join(" {:>9s}".format(k + " vw") for k in keys) + " |" + "".join(" {:>9s}".format(k + " no") for k in keys))
        S = {k: np.sum([r["sum"][k] for r in Q], 0) for k in keys}
        for j in range(len(Q[0]["dims"])):
            print("  {:9s} {:6.2f} |".format(NAMES[j], np.log(Q[0]["dims"][j])) + "".join(" {:9.3f}".format(S[k][1, j] / cnt[1]) for k in keys) + " |" + "".join(" {:9.3f}".format(S[k][0, j] / cnt[0]) for k in keys))
        w = np.array([float(x) for x in a.weights.split(",")])[:len(Q[0]["dims"])]
        print("  {:9s} {:6s} |".format("weighted", "") + "".join(" {:9.3f}".format((S[k][1] / cnt[1] * w).sum()) for k in keys) + " |" + "".join(" {:9.3f}".format((S[k][0] / cnt[0] * w).sum()) for k in keys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--saves", nargs="+", required=True)
    ap.add_argument("--maps", default="bloodrun,aerowalk,campgrounds")
    ap.add_argument("--drivers", default="", help="the saves that play (default: the first and the last)")
    ap.add_argument("--frames", type=int, default=8000)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--weights", default="0,0,0.25,0.25,0.25,0,0.5,0,1,1,0.1,0.1,0")
    ap.add_argument("--job", nargs=3, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.job:
        return job(a, a.job[0], a.job[1], a.job[2])
    os.makedirs(a.out, exist_ok=True)
    keys = [x.split("=", 1)[0] for x in a.saves]
    drv = a.drivers.split(",") if a.drivers else [keys[0], keys[-1]]
    todo = [(d, m) for d in drv for m in a.maps.split(",")]
    run = []
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    base = [sys.executable, os.path.abspath(__file__), "--cmd", a.cmd, "--run-dir", a.run_dir, "--out", a.out, "--frames", str(a.frames), "--saves"] + a.saves
    while todo or run:
        run = [r for r in run if r[0].poll() is None or print(r[1], "exit", r[0].returncode, flush=True)]
        while todo and len(run) < a.procs:
            d, m = todo.pop(0)
            o = os.path.join(a.out, "eh_{}_{}.json".format(d, m))
            run.append((subprocess.Popen(base + ["--job", d, m, o], cwd=ROOT, env=env, stdout=open(o + ".log", "w"), stderr=subprocess.STDOUT), (d, m)))
        time.sleep(5)
    report(a)


if __name__ == "__main__":
    main()

"""2.0c, test 4: the frozen moment, run and read (the hook: tools/run/branch_hook.py). Measurement only.

    python tools/run/branch_test.py run  [--maps bloodrun,lostworld] [--reps 4] [--minutes 6] [--tag t1]
    python tools/run/branch_test.py read [--tag t1]

run: 1.7a's update 90 against itself (the checks' settings from the save, tools/run/panel.py), one job a map; the matches of a job are
the branches (targets x reps). read: for every frozen moment, each target's mean outcome over its branches; how much of the outcome's
spread is the target (between targets) and how much is chance (between branches of one target); how often the target he was on is
among the best; what the best is worth over his own; and the simulator time a moment costs.

The outcome of a branch: his pay less the opponent's over the window (the run's own pay: frags, deaths, damage, items, the judge).
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = r"C:\Users\dacla\anaconda3\python.exe"
POL = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_end_17a.pt")
OUT = os.path.join(ROOT, "data", "sim_runs", "space", "branch")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(a):
    os.makedirs(OUT, exist_ok=True)
    sys.path.insert(0, HERE)
    os.environ["PANEL_RUN"] = "duel_gru_1_7a"
    os.chdir(ROOT)
    import panel as P
    sets_ = P.settings(0.0, a.policy)
    sets_ = [x for x in sets_ if not x.startswith("OVERTIME=")] + ["OVERTIME=0"]   # (a job's length is its --minutes: no overtime)
    inputs = a.inputs or os.path.join(ROOT, "docs", "INPUTS.csv")
    jobs = []
    for mp in a.maps.split(","):
        out = os.path.join(OUT, "{}_{}.jsonl".format(a.tag, mp))
        if os.path.exists(out):
            raise SystemExit(out + " is there: another --tag (nothing is overwritten)")
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1",
                   BRANCH_HOOK="branch_hook", BR_OUT=out, BR_WARM=str(a.warm), BR_HOLD=str(a.hold), BR_WIN=str(a.win))
        if a.opts:
            env["BR_OPTS"] = a.opts
        k = len(a.opts.split(",")) if a.opts else a.k
        cmd = [PY, "tools/duel_eval.py", "--run", "duel_gru_1_7a", "--policy", a.policy, "--opp", "policy:" + a.policy, "--inputs", inputs,
               "--opp-inputs", inputs, "--map", mp, "--games", str(k * a.reps), "--minutes", str(a.minutes), "--procs", "1",
               "--json", out + ".eval.json", "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
               "--round", "600", "--opp-round", "600"]
        cmd += [x for s_ in sets_ for x in ("--set", s_)]
        jobs.append((mp, out, cmd, env))
    t0 = time.time()
    procs = []
    for mp, out, cmd, env in jobs:
        p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(out + ".log", "w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=0x4000 | NOWIN)
        try:
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.SetProcessAffinityMask(ctypes.c_void_p(k32.OpenProcess(0x0200 | 0x0400, False, p.pid)), ctypes.c_size_t(int(a.mask, 16)))
        except Exception:  # noqa: BLE001
            pass
        procs.append((mp, out, p))
    for mp, out, p in procs:
        p.wait()
        n = sum(1 for _ in open(out)) if os.path.exists(out) else 0
        print("{}: exit {} rows {} ({:.0f} s)".format(mp, p.returncode, n, time.time() - t0), flush=True)


def read(a):
    import glob
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, a.tag + "_*.jsonl"))):
        rows += [json.loads(x) for x in open(f)]
    if not rows:
        raise SystemExit("no rows for --tag " + a.tag)
    by_o = {}
    for r in rows:
        if r["got"] == r["opt"] or r["opt"] < 0:
            by_o.setdefault(r["opt"], []).append((r["pay_he"] - r["pay_opp"], r["fr_he"] - r["fr_opp"], r["st_he"] - r["st_opp"]))
    print("by target (-1: free play, nothing forced): branches, his pay less the opponent's (its standard error), frags, stack")
    for o in sorted(by_o):
        v = np.array(by_o[o])
        print("  {:>3} {:>5}  {:+.3f} ({:.3f})  {:+.3f}  {:+6.1f}".format(o, len(v), v[:, 0].mean(), v[:, 0].std() / len(v) ** 0.5, v[:, 1].mean(), v[:, 2].mean()))
    pts = {}
    for r in rows:
        pts.setdefault((r["map"], r["point"]), []).append(r)
    y_of = {"pay": lambda r: r["pay_he"] - r["pay_opp"], "frags": lambda r: r["fr_he"] - r["fr_opp"], "stack": lambda r: r["st_he"] - r["st_opp"]}
    print("{} frozen moments on {} maps, {} branches; branches a moment {}".format(len(pts), len({k[0] for k in pts}), len(rows),
                                                                                   sorted({len(v) for v in pts.values()})))
    for nm, fy in y_of.items():
        btw, wth, top1, top3, gain, reps, ks = [], [], [], [], [], [], []
        for v in pts.values():
            by = {}
            for r in v:
                if r["got"] == r["opt"] or r["opt"] < 0:                     # (a target the map lacks, or one already taken, became nothing: left out)
                    by.setdefault(r["opt"], []).append(fy(r))
            by = {k: np.array(x) for k, x in by.items() if len(x) >= 2}
            if len(by) < 3:
                continue
            means = {k: x.mean() for k, x in by.items()}
            R = np.mean([len(x) for x in by.values()])
            w_ = np.mean([x.var(ddof=1) for x in by.values()])            # chance: between branches of one target
            b_ = max(0.0, np.var(list(means.values()), ddof=1) - w_ / R)  # the targets' true spread (the means' variance less the noise in it)
            btw.append(b_)
            wth.append(w_)
            reps.append(R)
            ks.append(len(by))
            order = sorted(means, key=lambda k: -means[k])
            own = v[0]["own"]
            if own in means:
                top1.append(order[0] == own)
                top3.append(own in order[:3])
                gain.append(means[order[0]] - means[own])
        B, W = float(np.mean(btw)), float(np.mean(wth))
        print("\noutcome '{}' (his less the opponent's over the window): {} moments with 3 or more targets, {:.1f} targets, {:.1f} branches a target".format(
            nm, len(btw), np.mean(ks), np.mean(reps)))
        print("  spread between targets (sd) {:.3f} | chance between two branches of one target (sd) {:.3f} | the target's share of one branch's outcome {:.1%}".format(
            B ** 0.5, W ** 0.5, B / max(B + W, 1e-12)))
        if B > 0:
            print("  branches a target for the targets' order to be half signal: {:.0f}".format(W / B))
        if top1:
            print("  the target he was on: the best in {:.1%} of moments, among the best three in {:.1%} (by chance {:.1%} and {:.1%}); the best target's mean over his own: {:+.3f} (inflated by chance: the best of noisy means)".format(
                np.mean(top1), np.mean(top3), 1 / np.mean(ks), 3 / np.mean(ks), np.mean(gain)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "read"))
    ap.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity")
    ap.add_argument("--policy", default=POL)
    ap.add_argument("--inputs", default="")
    ap.add_argument("--opts", default="")
    ap.add_argument("--k", type=int, default=16, help="the default targets: 8 and the map's holding places (up to 8)")
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=6.0)
    ap.add_argument("--warm", type=float, default=20.0)
    ap.add_argument("--hold", type=float, default=4.0)
    ap.add_argument("--win", type=float, default=10.0)
    ap.add_argument("--mask", default="C3FFF")
    ap.add_argument("--tag", default="t1")
    a_ = ap.parse_args()
    {"run": run, "read": read}[a_.cmd](a_)

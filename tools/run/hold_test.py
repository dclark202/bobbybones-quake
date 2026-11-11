"""2.0c, the perfect-hold probe: run and read (the hook: tools/run/hold_hook.py, which says what an option is). Measurement only.

    python tools/run/hold_test.py run  [--maps ...] [--reps 5] [--minutes 12] [--tag h1]
    python tools/run/hold_test.py read [--tag h1]

run: 1.7a's update 90 on both seats (the checks' settings from the save, tools/run/panel.py; 125 / 225 ms), one job a map on the
efficiency cores; the matches of a job are the branches (options x reps). read: per option, over the frozen moments (each moment's
branches averaged first, so the options are compared on the same moments): damage dealt less taken in the window, frags, pay; the
share of branches in which the enemy came into his view; the script's first shot (frames from the enemy in view to his first
damage; shots and hits while the script held); and the same for the moments at a holding place only and for those with contact.
"""
import argparse
import ctypes
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = r"C:\Users\dacla\anaconda3\python.exe"
POL = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_u90_17a.pt")
OUT = os.path.join(ROOT, "data", "sim_runs", "space", "hold")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(a):
    os.makedirs(OUT, exist_ok=True)
    sys.path.insert(0, HERE)
    os.environ["PANEL_RUN"] = "duel_gru_1_7a"
    os.chdir(ROOT)
    import hold_hook as H
    import panel as P
    sets_ = P.settings(0.0, a.policy)
    sets_ = [x for x in sets_ if not x.startswith("OVERTIME=")] + ["OVERTIME=0"]
    names = {x.split("=", 1)[0] for x in a.set}                     # (--set: simulator switches for the job, over the checks')
    sets_ = [x for x in sets_ if x.split("=", 1)[0] not in names] + a.set
    inputs = a.inputs or os.path.join(ROOT, "docs", "INPUTS_20a.csv")
    opts = a.opts or H.DEF_OPTS
    k = len(opts.split(","))
    procs = []
    t0 = time.time()
    for mp in a.maps.split(","):
        out = os.path.join(OUT, "{}_{}.jsonl".format(a.tag, mp))
        if os.path.exists(out):
            raise SystemExit(out + " is there: another --tag (nothing is overwritten)")
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1",
                   BRANCH_HOOK="hold_hook", HP_OUT=out, HP_OPTS=opts, HP_WARM=str(a.warm), HP_WIN=str(a.win), HP_REL=str(a.rel))
        cmd = [PY, "tools/duel_eval.py", "--run", "duel_gru_1_7a", "--policy", a.policy, "--opp", "policy:" + a.policy, "--inputs", inputs,
               "--opp-inputs", inputs, "--map", mp, "--games", str(k * a.reps), "--minutes", str(a.minutes), "--procs", "1",
               "--json", out + ".eval.json", "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
               "--round", "600", "--opp-round", "600"]
        cmd += [x for s_ in sets_ for x in ("--set", s_)]
        if a.aim:                                            # (his seats' own aim settings: duel_eval's --aim-he)
            cmd += ["--aim-he", a.aim]
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
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, a.tag + "_*.jsonl"))):
        rows += [json.loads(x) for x in open(f)]
    if not rows:
        raise SystemExit("no rows for --tag " + a.tag)
    pts = {}
    for r in rows:
        pts.setdefault((r["map"], r["point"]), []).append(r)
    opts = []
    for r in rows:
        if r["opt"] not in opts:
            opts.append(r["opt"])
    print("{} frozen moments on {} maps, {} branches; at a holding place: {}".format(
        len(pts), len({k[0] for k in pts}), len(rows), sum(v[0]["place"] >= 0 for v in pts.values())))

    def table(title, keep_pt, keep_row=lambda r: True):
        print("\n" + title)
        print("  {:<15} {:>7} | {:>6} {:>6} {:>14} | {:>6} | {:>14} | {:>8} | {:>7} {:>6} {:>5}".format(
            "option", "moments", "deals", "takes", "less (s.e.)", "frags", "pay less opp", "contact", "1st dmg", "shots", "hit"))
        ref = None
        for o in opts:
            ex, fr, pay, dl, tk, ct, fd, sh, ht, n, s1 = [], [], [], [], [], [], [], 0.0, 0.0, 0, []
            for v in pts.values():
                if not keep_pt(v):
                    continue
                b = [r for r in v if r["opt"] == o and keep_row(r)]
                if not b:
                    continue
                n += 1
                dl.append(np.mean([r["dealt"] for r in b]))
                tk.append(np.mean([r["taken"] for r in b]))
                ex.append(dl[-1] - tk[-1])
                fr.append(np.mean([r["fr_he"] - r["fr_opp"] for r in b]))
                pay.append(np.mean([r["pay_he"] - r["pay_opp"] for r in b]))
                ct.append(np.mean([r["contact"] >= 0 for r in b]))
                fd += [r["first"] * 25 for r in b if r["first"] >= 0]
                sh += sum(r["shots"] for r in b)
                s1 += [(r["shot1"] * 25, r["hit1"]) for r in b if r.get("shot1", -1) >= 0]
                ht += sum(r["hits"] for r in b)
            if not n:
                continue
            ex = np.array(ex)
            print("  {:<15} {:>7} | {:>6.1f} {:>6.1f} {:>+7.1f} ({:>4.1f}) | {:>+6.2f} | {:>+7.3f} ({:.3f}) | {:>7.0%} | {:>5.0f}ms {:>6.0f} {:>5}".format(
                o, n, np.mean(dl), np.mean(tk), ex.mean(), ex.std() / max(n, 1) ** 0.5, np.mean(fr), np.mean(pay), np.std(pay) / max(n, 1) ** 0.5,
                np.mean(ct), np.median(fd) if fd else float("nan"), sh, "{:.0%}".format(ht / sh) if sh and not o.startswith("rl") else "-")
                  + ("" if not s1 else " | first shot {:.0f} ms after he is in view, {} ({})".format(
                      np.median([x[0] for x in s1]), "-" if o.startswith("rl") else "hit {:.0%}".format(np.mean([x[1] for x in s1])), len(s1))))

    table("all moments (deals, takes: points of stack in the window; 1st dmg: the median from the enemy in view to his first damage)", lambda v: True)
    table("moments at a holding place", lambda v: v[0]["place"] >= 0)
    table("only branches in which the enemy came into his view", lambda v: True, lambda r: r["contact"] >= 0)
    for lo, hi in ((300, 700), (700, 1100), (1100, 1500)):
        table("the enemy {} to {} units away at the copy".format(lo, hi), lambda v, lo=lo, hi=hi: lo <= v[0]["d0"] < hi)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "read"))
    ap.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity")
    ap.add_argument("--policy", default=POL)
    ap.add_argument("--inputs", default="")
    ap.add_argument("--opts", default="")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--minutes", type=float, default=12.0)
    ap.add_argument("--warm", type=float, default=12.0)
    ap.add_argument("--win", type=float, default=8.0)
    ap.add_argument("--rel", type=float, default=1.5)
    ap.add_argument("--mask", default="3C3C", help="the efficiency cores 2-5, 10-13")
    ap.add_argument("--aim", default="", help="his seats' own aim settings, NAME=VALUE,... (duel_env SEAT_AIM)")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--tag", default="h1")
    a_ = ap.parse_args()
    {"run": run, "read": read}[a_.cmd](a_)

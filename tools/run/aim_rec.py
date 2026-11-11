"""aim3: record his games for tools/run/pro_aim.py (the recorder: tools/run/aim_rec_hook.py). Measurement only.

    python tools/run/aim_rec.py --tag base [--aim NAME=VALUE,...] [--set NAME=VALUE ...] [--games 16] [--minutes 10]
    python tools/run/pro_aim.py --src data/sim_runs/space/aimrec/base

A network against itself (1.7a's update 90 by default; the checks' settings from the save, tools/run/panel.py; 125 / 225 ms), one
job a map on the efficiency cores. --aim: both seats' own aim settings (duel_env SEAT_AIM); --set: simulator switches for the job.
"""
import argparse
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = r"C:\Users\dacla\anaconda3\python.exe"
POL = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_u90_17a.pt")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity")
    ap.add_argument("--policy", default=POL)
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS_20a.csv"))
    ap.add_argument("--aim", default="")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--mask", default="3C3C")
    a = ap.parse_args()
    out_dir = os.path.join(ROOT, "data", "sim_runs", "space", "aimrec", a.tag)
    if os.path.exists(out_dir):
        raise SystemExit(out_dir + " is there: another --tag (nothing is overwritten)")
    os.makedirs(out_dir)
    sys.path.insert(0, HERE)
    os.environ["PANEL_RUN"] = "duel_gru_1_7a"
    os.chdir(ROOT)
    import panel as P
    sets_ = [x for x in P.settings(0.0, a.policy) if not x.startswith("OVERTIME=")] + ["OVERTIME=0"]
    names = {x.split("=", 1)[0] for x in a.set}
    sets_ = [x for x in sets_ if x.split("=", 1)[0] not in names] + a.set
    procs, t0 = [], time.time()
    for mp in a.maps.split(","):
        out = os.path.join(out_dir, "rec_{}.npz".format(mp))
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1",
                   BRANCH_HOOK="aim_rec_hook", AR_OUT=out, AR_BOTH="1")
        cmd = [PY, "tools/duel_eval.py", "--run", "duel_gru_1_7a", "--policy", a.policy, "--opp", "policy:" + a.policy, "--inputs", a.inputs,
               "--opp-inputs", a.inputs, "--map", mp, "--games", str(a.games), "--minutes", str(a.minutes), "--procs", "1",
               "--json", out + ".eval.json", "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
               "--round", "600", "--opp-round", "600"]
        cmd += [x for s_ in sets_ for x in ("--set", s_)]
        if a.aim:
            cmd += ["--aim-he", a.aim, "--aim-opp", a.aim]
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
        print("{}: exit {} {} ({:.0f} s)".format(mp, p.returncode, "written" if os.path.exists(out) else "NOT written", time.time() - t0), flush=True)


if __name__ == "__main__":
    main()

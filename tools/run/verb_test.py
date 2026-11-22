"""2.1, the scripted seats (docs/runs/2.1/INSTRUCTION.md): run and read a probe of one verb on any run's save. Measurement only; it
plays games on the cores of --mask and touches no run. NOT RUN YET.

    python tools/run/verb_test.py run  --hook spam_hook --run duel_gru_1_8a --policy <save.pt> [--maps ...] [--reps 5] [--tag s1]
    python tools/run/verb_test.py run  --hook hold_hook --run duel_gru_1_8a --policy <save.pt> --tag h18
    python tools/run/verb_test.py read --tag s1

--hook: tools/run/hold_hook.py (the held angle: rail, lightning, rockets at the pros' holding places) or tools/run/spam_hook.py
(rockets, grenades, plasma on a point with nobody in view); each says what its options are. The save plays both seats with the
checks' settings for its run (tools/run/panel.py: the save's own switches, the run's live.json; 125 / 225 ms), INSTR=1 added (the
map's spam points, and the seat under the instruction). Before its numbers are used: tools/run/cypher_measure.py check for the same
run and save (CLAUDE.md rule 3). read: tools/run/hold_test.py's tables (each moment's branches averaged first), and for a spam
probe the branches with a clear line only.
"""
import argparse
import ctypes
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe"
OUT = os.environ.get("VERB_OUT") or os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "space", "verbs")   # (VERB_OUT: another folder for the rows)
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(a):
    assert a.run and a.policy, "--run and --policy"
    os.makedirs(OUT, exist_ok=True)
    sys.path.insert(0, HERE)
    os.environ["PANEL_RUN"] = a.run
    os.chdir(ROOT)
    import panel as P
    sets_ = [x for x in P.settings(a.percept_speed, a.policy) if not x.startswith("OVERTIME=")] + ["OVERTIME=0"]
    extra = a.set if any(x.startswith("INSTR=") for x in a.set) else a.set + ["INSTR=1"]
    names = {x.split("=", 1)[0] for x in extra}
    sets_ = [x for x in sets_ if x.split("=", 1)[0] not in names] + extra
    H = __import__(a.hook)
    opts = a.opts or H.DEF_OPTS
    k = len(opts.split(","))
    inputs = a.inputs or os.path.join(ROOT, "docs", "INPUTS.csv")
    json.dump(dict(hook=a.hook, run=a.run, policy=a.policy, sets=sets_, opts=opts, reps=a.reps, maps=a.maps, started=time.strftime("%Y-%m-%d %H:%M")),
              open(os.path.join(OUT, a.tag + ".meta.json"), "w"), indent=1)
    procs, t0 = [], time.time()
    for mp in a.maps.split(","):
        out = os.path.join(OUT, "{}_{}.jsonl".format(a.tag, mp))
        if os.path.exists(out):
            raise SystemExit(out + " is there: another --tag (nothing is overwritten)")
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1",
                   BRANCH_HOOK=a.hook, HP_OUT=out, HP_OPTS=opts, HP_WARM=str(a.warm), HP_WIN=str(a.win), HP_REL=str(a.rel))
        cmd = [PY, "tools/duel_eval.py", "--run", a.run, "--policy", a.policy, "--opp", "policy:" + a.policy, "--inputs", inputs,
               "--opp-inputs", inputs, "--map", mp, "--games", str(k * a.reps), "--minutes", str(a.minutes), "--procs", "1",
               "--json", out + ".eval.json", "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
               "--round", "600", "--opp-round", "600"]
        cmd += [x for s_ in sets_ for x in ("--set", s_)]
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
    sys.path.insert(0, HERE)
    import hold_test as HT
    HT.OUT = OUT
    rows = [json.loads(x) for f in sorted(glob.glob(os.path.join(OUT, a.tag + "_*.jsonl"))) for x in open(f)]
    if rows and "line" in rows[0]:
        n = sum(1 for r in rows if r["opt"].split("_")[0] in ("rl", "gl", "pg"))
        nl = sum(1 for r in rows if r["opt"].split("_")[0] in ("rl", "gl", "pg") and r["line"])
        print("spam branches: {} of {} had a line to the point (the others played free and are in the tables as they played)".format(nl, n))
    HT.read(a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "read"))
    ap.add_argument("--hook", default="spam_hook", choices=("spam_hook", "hold_hook"))
    ap.add_argument("--run", default="")
    ap.add_argument("--policy", default="")
    ap.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity")
    ap.add_argument("--inputs", default="")
    ap.add_argument("--opts", default="")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--minutes", type=float, default=12.0)
    ap.add_argument("--warm", type=float, default=12.0)
    ap.add_argument("--win", type=float, default=8.0)
    ap.add_argument("--rel", type=float, default=1.5)
    ap.add_argument("--percept-speed", type=float, default=0.0)
    ap.add_argument("--mask", default="3C3C", help="the efficiency cores 2-5, 10-13")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--tag", default="s1")
    a_ = ap.parse_args()
    {"run": run, "read": read}[a_.cmd](a_)

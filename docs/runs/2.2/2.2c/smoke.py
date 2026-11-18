"""2.2c's smoke (2.2b's, for 2.2c: its command, start_live.py, ramp_22c.py): the trainer of THIS checkout runs 2.2c's command made small (2 simulators x 8 matches x 384 frames, the
CPU unless SMOKE_GPU=1, below normal, pinned to 0x3C3C; SMOKE_UPDATES updates, default 10) on the start file (the first argument: 2.2c's start, tools/lever22_init.py then inputs22c.py stats; 2.2b's note: tools/fight22_init.py
norm's), the optimizer cold (none was kept at 2.2a's update 90), two converted anchors and the control as the league (the trainer leaves out of a
2.2a file the rater's parts), a live.json from start_live.py (2.2a's, --any), --snapshot-min 1 (the run's own snapshots join the league with their
fight network), and ramp_22c.py --scale SMOKE_SCALE (default 10: the card's stages walked ten times faster: H2_WADD to 0 by update 1, the token's gate
over updates 1 to 2; the lever is on from update LEV_FROM by the trainer's own count: SMOKE_EXTRA="--lev-from 3" walks it too). Then a resume for one more update. Then
ramp_22c.py --once over the metrics. Scratch folder data/sim_runs/scratch_22c_smoke<TEST_TAG>; nothing deleted, nothing else written.
SMOKE_FULL=1: the run's own size (30 simulators x 168 matches, 360 pieces) on the graphics card, SMOKE_UPDATES updates, no ramp (the dials at
SMOKE_LIVE's values), no resume: the full-size trial (memory, minutes an update). SMOKE_OPT=<opt file>: copied in as opt.pt (a carried optimizer).
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.2/2.2c/smoke.py <start file> <anchor a (list 22c)> <anchor b (list 22c)> <the control (list 22c)>"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DATA = os.environ.get("QLBOT_ROOT") or CODE
BS = "\\"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUN = "scratch_22c_smoke" + os.environ.get("TEST_TAG", "")
UPD = int(os.environ.get("SMOKE_UPDATES", "10"))
SCALE = float(os.environ.get("SMOKE_SCALE", "10"))
FULL = os.environ.get("SMOKE_FULL") == "1"
GPU = FULL or os.environ.get("SMOKE_GPU") == "1"
EXTRA = os.environ.get("SMOKE_EXTRA", "")
LIVE_SET = json.loads(os.environ.get("SMOKE_LIVE") or "{}")
CLOCK = int(os.environ.get("SMOKE_CLOCK", "0"))
CMD = os.path.join(HERE, "train.cmd")


def small_cmd(updates):
    t = open(CMD, encoding="ascii").read().replace("\r\n", "\n")
    rp = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\n{}".format(
               DATA, DATA, "" if GPU else "set CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1")),
          ("python.exe sim" + BS + "train_duel_rnn.py ", "python.exe " + os.path.join(CODE, "sim", "train_duel_rnn.py") + " ")]
    if not FULL:
        rp += [("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal /affinity 3C3C "),
               ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--minibatches 360 ", "--minibatches 4 "),
               ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 " + EXTRA + " >> ")]
    else:
        rp += [("%LEARN% >> ", "--snapshot-min 1000 --overlap 1 --learn-nosync 1 " + EXTRA + " >> ")]
    for a, b in rp:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    L_ = t.split("\n")
    cl_ = [i for i, x in enumerate(L_) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1 and len(re.findall(r"--max-updates \d+ ", L_[cl_[0]])) == 1
    L_[cl_[0]] = re.sub(r"--max-updates \d+ ", "--max-updates {} ".format(updates), L_[cl_[0]])
    t = "\n".join(L_)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + RUN + ".log", t)
    t = t.replace("%ROOT%\\docs\\", os.path.join(CODE, "docs") + "\\")
    assert not any("duel_gru_2_" in x for x in t.split("\n") if not x.startswith("rem"))
    return t


def run_cmd(D, name, t):
    cmd = os.path.join(D, name)
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=DATA, env=dict(os.environ, QLBOT_ROOT=DATA, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=NOWIN)
    while tr.poll() is None and time.time() - t0 < 300 * 60:
        time.sleep(10)
    return tr, t0


def main():
    start, an_a, an_b, ctl = sys.argv[1:5]
    D = os.path.join(DATA, "data", "sim_runs", RUN)
    assert not os.path.exists(os.path.join(D, "policy.pt")), "{} has a policy.pt: give another TEST_TAG (nothing is overwritten)".format(D)
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_), exist_ok=True)
    shutil.copy2(start, os.path.join(D, "policy.pt"))
    if CLOCK > 0:                                            # (2.2c, SMOKE_CLOCK=N: the run's own count starts at N, as on a resume after N updates:
        with open(os.path.join(D, "metrics.jsonl"), "w") as fh:   # the trainer's windows (--h2-choice-warm, --h2-freeze, --lev-from) read
            for k_ in range(CLOCK):                          # metrics.jsonl's lines; the trial exercises the switch at update 10)
                fh.write(json.dumps({"update": k_ + 1, "trial_clock": True}) + "\n")
    if os.environ.get("SMOKE_OPT"):                          # (a trial of a carried optimizer: e.g. 2.2a's keep\opt_u100.pt as opt.pt)
        shutil.copy2(os.environ["SMOKE_OPT"], os.path.join(D, "opt.pt"))
    for nm_, f_ in (("anchor_a.pt", an_a), ("anchor_b.pt", an_b), ("anchor_22a90.pt", ctl)):
        shutil.copy2(f_, os.path.join(D, "snapshots", nm_))
    py_ = sys.executable
    r_ = subprocess.run([py_, os.path.join(HERE, "start_live.py"), os.path.join(DATA, "data", "sim_runs", "duel_gru_2_2a", "live.json"),
                         os.path.join(D, "live.json"), "--any"], capture_output=True, text=True, creationflags=NOWIN)
    print(r_.stdout.strip(), r_.stderr.strip()[-500:], flush=True)
    if LIVE_SET:
        d_ = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
        d_.update(LIVE_SET)
        json.dump(d_, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    rmp_ = None
    if not FULL:
        rmp_ = subprocess.Popen([py_, os.path.join(HERE, "ramp_22c.py"), RUN, "--poll", "5", "--settle", "3", "--scale", str(SCALE)], cwd=CODE,
                                creationflags=NOWIN, stdout=open(os.path.join(D, "watch", "ramp_stdout.log"), "w"),
                                stderr=open(os.path.join(D, "watch", "ramp_stderr.log"), "w"))
    tr, t0 = run_cmd(D, "smoke.cmd", small_cmd(UPD))
    log_ = os.path.join(DATA, "data", "sim_runs", RUN + ".log")
    print("the run: exit {} in {:.1f} min".format(tr.returncode, (time.time() - t0) / 60.0), flush=True)
    ok_ = tr.returncode == 0
    if ok_ and not FULL:
        tr2, t1 = run_cmd(D, "smoke_resume.cmd", small_cmd(1))
        print("the resume: exit {} in {:.1f} min".format(tr2.returncode, (time.time() - t1) / 60.0), flush=True)
        ok_ = tr2.returncode == 0
        time.sleep(15)
    if rmp_ is not None:
        rmp_.terminate()
        r2_ = subprocess.run([py_, os.path.join(HERE, "ramp_22c.py"), RUN, "--once", "--scale", str(SCALE), "--dir", D], cwd=CODE, capture_output=True,
                             text=True, creationflags=NOWIN)
        print("ramp --once: exit {} {}".format(r2_.returncode, r2_.stderr.strip()[-800:]), flush=True)
    L = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"))] if os.path.exists(os.path.join(D, "metrics.jsonl")) else []
    L = L[CLOCK:]
    print("metrics lines: {}".format(len(L)))
    tail_ = open(log_, encoding="utf-8", errors="replace").read()[-3000:] if os.path.exists(log_) else ""
    print(tail_[-1500:])
    print("SMOKE " + ("PASSED" if ok_ and len(L) >= UPD else "FAILED"))
    sys.exit(0 if ok_ and len(L) >= UPD else 1)


if __name__ == "__main__":
    main()

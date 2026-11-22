"""2.0e's one check before the start (docs/runs/2.0/2.0e/CARD.md): the trainer runs on 1.6a's end brought to list 20e. 2.0e's command made
small (2 simulators x 8 matches x 96 frames, CPU, below normal, 3 updates), from a converted start with its optimizer and two converted
anchors, start_live.py's live.json with the dials at mid values (AIM3 half in, the pay half moved, DODGE_G 0.5). PASS: the trainer ends
with exit 0, three lines in metrics.jsonl, live.json applied, the dodge token's gate log(0.5), the optimizer loaded (not cold), a save
written. A scratch run folder only (data/sim_runs/scratch_20e_smoke<TAG>); nothing deleted.
    python docs/runs/2.0/2.0e/smoke.py <the converted start.pt> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
BS = "\\"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUN = "scratch_20e_smoke" + os.environ.get("TEST_TAG", "")
D = os.path.join(ROOT, "data", "sim_runs", RUN)
R6A = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_6a")


def main():
    s1, s1o, a1, a2 = sys.argv[1:5]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(s1, os.path.join(D, "policy.pt"))
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    shutil.copy2(a1, os.path.join(D, "snapshots", "anchor_16a.pt"))
    shutil.copy2(a2, os.path.join(D, "snapshots", "anchor_b12d.pt"))
    shutil.copy2(os.path.join(R6A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(R6A, "live.json"), os.path.join(D, "live.json")], creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(AIM3_W=0.5, AIM3_SIZE_A=0.695, AIM3_SIZE_B=0.1775, AIM3_LEAD=0.5, AIM3_RELOAD=0.5, DMG_REWARD=0.00525, DMG_TAKEN_W=0.9,
              RAIL_FAR_PAY=0.175, DODGE_G=0.5)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
                 ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
                 ("--max-updates 80 ", "--max-updates 3 "), ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 >> ")):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + RUN + ".log", t)
    assert not any("duel_gru_2_" in x for x in t.split("\n") if not x.startswith("rem"))
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), creationflags=NOWIN)
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
    logp = os.path.join(ROOT, "data", "sim_runs", RUN + ".log")
    log = open(logp, encoding="utf-8", errors="replace").read() if os.path.exists(logp) else ""
    mp = os.path.join(D, "metrics.jsonl")
    M = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ok = True

    def chk(name, good, more=""):
        nonlocal ok
        ok = ok and bool(good)
        print(("PASS  " if good else "FAIL  ") + name + (" | " + str(more) if more else ""), flush=True)

    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-3:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold", bool(opt_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in opt_), opt_[:3])
    dg = (M[-1].get("dodge_gate") or {}) if M else {}
    chk("the dodge gate: columns 0.5, token log(0.5)", dg and abs(float(dg.get("cols", 0)) - 0.5) < 1e-6 and abs(float(dg.get("token", 0)) - math.log(0.5)) < 1e-3, dg)
    it = (M[-1].get("intent") or {}) if M else {}
    chk("the lock's measures are recorded (trips, reached)", it.get("trips_per_player_min") is not None and it.get("reached") is not None, it)
    chk("no keep choice, no order in the metrics", M and not (M[-1].get("keep") or {}).get("g") and not (M[-1].get("cmb") or {}).get("g"),
        {k_: M[-1].get(k_) for k_ in ("keep", "cmb")} if M else "")
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

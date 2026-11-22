"""2.1c's live test of HELD_G (CLAUDE.md: every new live name gets its range and a live test; docs/runs/2.1/2.1c/CARD.md). The smoke's small
CPU trainer (2 simulators x 8 matches x 96 frames, below normal) on the widened start, in two arms:
  A. live.json starts at HELD_G 0; after update 1 it is written to 0.5; 5 updates. PASS: update 1 played 0 (no seat-frame on the held
     draw), the last update played 0.5, nothing refused.
  B. live.json with HELD_G 1.5 (out of its range): the trainer refuses the file and stops before its first rollout; no update.
Scratch run folders only (data/sim_runs/scratch_21c_live<TAG>_a, _b); nothing deleted.
    python docs/runs/2.1/2.1c/live_test.py <the widened start.pt> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
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
RUN = D = None
R6A = os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_0e")


def arm(name, start_g, late_g, updates):
    global RUN, D
    RUN = "scratch_21c_live" + os.environ.get("TEST_TAG", "") + "_" + name
    D = os.path.join(ROOT, "data", "sim_runs", RUN)
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
    lv.update(HELD_G=start_g)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
                 ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
                 ("--max-updates 100 ", "--max-updates {} ".format(updates)), ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 >> ")):
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
    wrote = False
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(2)
        if late_g is not None and not wrote and os.path.exists(os.path.join(D, "metrics.jsonl")) and os.path.getsize(os.path.join(D, "metrics.jsonl")) > 0:
            lv["HELD_G"] = late_g                             # (after update 1: as the ramp writes it)
            json.dump(lv, open(os.path.join(D, "live.json.tmp"), "w", encoding="utf-8"))
            os.replace(os.path.join(D, "live.json.tmp"), os.path.join(D, "live.json"))
            wrote = True
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

    chk("arm {}: the trainer ended by itself in {:.1f} min".format(name, (time.time() - t0) / 60), tr.poll() is not None)
    hd = [(m_.get("held") or {}) for m_ in M]
    if name == "a":
        chk("arm a: exit 0, {} updates".format(updates), log.strip() and "exit 0" in log.splitlines()[-1] and len(M) == updates, len(M))
        chk("arm a: update 1 played HELD_G 0, no seat-frame on the held draw", hd and hd[0].get("g") == 0.0 and hd[0].get("share") == 0.0, hd[:1])
        chk("arm a: the dial written after update 1 played by the last update (0.5), seats on it", hd and hd[-1].get("g") == 0.5 and hd[-1].get("share", 0) > 0.2, hd[-1:])
        chk("arm a: nothing refused", st.get("status") == "applied", st)
    else:
        chk("arm b: HELD_G 1.5 refused, the trainer stopped before its first rollout, no update", st.get("status") == "refused" and len(M) == 0,
            dict(status=st.get("status"), reason=st.get("reason"), updates=len(M)))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("arm {}: no NaN, no traceback in the log".format(name), not bad, bad[:3])
    return ok


def main():
    ok = arm("a", 0.0, 0.5, 5)
    ok = arm("b", 1.5, None, 2) and ok
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

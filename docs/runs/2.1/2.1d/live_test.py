"""2.1d's live test of PULL_G (CLAUDE.md: every new live name gets its range and a live test). The smoke's small CPU trainer (smoke.py's command:
2 simulators x 8 matches x 96 frames, below normal, pinned to the efficiency cores 0x3C3C; this checkout's trainer, the data of QLBOT_ROOT) on a
2.1c save given the plan inside its head (tools/plan_init.py add), in two arms:
  A. live.json starts at PULL_G 0 (HELD_G 0.5); after update 1 it is written to 1.0; 5 updates. PASS: update 1 played 0 (the pull zero to the
     bit), the last update played 1.0 with the pull above 0, its proof measured and at most 1e-3, nothing refused.
  B. live.json with PULL_G 6.0 (out of its range 0 .. 5): the trainer refuses the file and stops before its first rollout; no update.
Scratch run folders only (QLBOT_ROOT/data/sim_runs/scratch_21d_live<TAG>_a, _b); nothing deleted.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1d/live_test.py <a 2.1c save with its plan> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smoke as S                                            # noqa: E402  (its small command; its RUN set per arm)

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def arm(name, start_g, late_g, updates):
    S.RUN = "scratch_21d_live" + os.environ.get("TEST_TAG", "") + "_" + name
    DATA = S.DATA
    D = os.path.join(DATA, "data", "sim_runs", S.RUN)
    R1C = os.path.join(DATA, "data", "sim_runs", "duel_gru_2_1c")
    s1, s1o, a1, a2 = sys.argv[1:5]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    pi_ = [sys.executable, os.path.join(S.CODE, "tools", "plan_init.py")]
    subprocess.check_call(pi_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN)
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        subprocess.check_call(pi_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
                              env=cpu, creationflags=NOWIN)
    shutil.copy2(os.path.join(R1C, "live_settings.env"), os.path.join(D, "live_settings.env"))
    shutil.copy2(os.path.join(R1C, "live.json"), os.path.join(D, "live_21c.json"))      # (a copy out of the running run: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21c.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=start_g, HELD_G=0.5)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(S.small_cmd(D, updates).replace("\n", "\r\n"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=DATA, env=dict(os.environ, QLBOT_ROOT=DATA, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=NOWIN)
    wrote = False
    while tr.poll() is None and time.time() - t0 < 60 * 60:
        time.sleep(2)
        if late_g is not None and not wrote and os.path.exists(os.path.join(D, "metrics.jsonl")) and os.path.getsize(os.path.join(D, "metrics.jsonl")) > 0:
            lv["PULL_G"] = late_g                             # (after update 1: as the ramp writes it)
            json.dump(lv, open(os.path.join(D, "live.json.tmp"), "w", encoding="utf-8"))
            os.replace(os.path.join(D, "live.json.tmp"), os.path.join(D, "live.json"))
            wrote = True
    logp = os.path.join(DATA, "data", "sim_runs", S.RUN + ".log")
    log = open(logp, encoding="utf-8", errors="replace").read() if os.path.exists(logp) else ""
    mp = os.path.join(D, "metrics.jsonl")
    M = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ok = True

    def chk(nm, good, more=""):
        nonlocal ok
        ok = ok and bool(good)
        print(("PASS  " if good else "FAIL  ") + nm + (" | " + str(more)[:1500] if more != "" else ""), flush=True)

    chk("arm {}: the trainer ended by itself in {:.1f} min".format(name, (time.time() - t0) / 60), tr.poll() is not None)
    pu = [(m_.get("pull") or {}) for m_ in M]
    if name == "a":
        chk("arm a: exit 0, {} updates".format(updates), log.strip() and "exit 0" in log.splitlines()[-1] and len(M) == updates, len(M))
        chk("arm a: update 1 played PULL_G 0, the pull zero to the bit", pu and pu[0].get("g") == 0.0 and pu[0].get("size") == 0.0 and pu[0].get("max") == 0.0,
            pu[:1])
        chk("arm a: the dial written after update 1 played by the last update (1.0), the pull above 0, its proof at most 1e-3",
            pu and pu[-1].get("g") == 1.0 and float(pu[-1].get("size") or 0) > 0 and pu[-1].get("first_err") is not None and float(pu[-1]["first_err"]) <= 1e-3,
            pu[-1:])
        chk("arm a: nothing refused", st.get("status") == "applied", st)
    else:
        chk("arm b: PULL_G 6.0 refused, the trainer stopped before its first rollout, no update", st.get("status") == "refused" and len(M) == 0
            and "PULL_G" in str(st.get("reason")), dict(status=st.get("status"), reason=st.get("reason"), updates=len(M)))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("arm {}: no NaN, traceback or MAJOR PROBLEM in the log".format(name), not bad, bad[:3])
    return ok


def main():
    if not S.DATA or not os.path.isdir(os.path.join(S.DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    ok = arm("a", 0.0, 1.0, 5)
    ok = arm("b", 6.0, None, 2) and ok
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""2.1e's live test of SLOW_MIX, SLOW_BACK, SLOW_PICK (CLAUDE.md: every new live name gets its range and a live test). The smoke's small CPU
trainer (smoke.py's command: 2 simulators x 8 matches x 96 frames, below normal, pinned to the efficiency cores 0x3C3C; this checkout's trainer,
the data of QLBOT_ROOT) on a 2.1d save given the slow halves (tools/slow_init.py add; SMOKE_NONZERO's non-zero halves and read-back), in arms:
  A. live.json starts at SLOW_MIX 0, SLOW_BACK 0, SLOW_PICK 1 (PULL_G 1.0, HELD_G 0.5); after update 1 it is written to SLOW_MIX 1.0, SLOW_BACK
     1.0, SLOW_PICK 2 (the owner's switch of the half that plays, mid-run); 4 updates. PASS: update 1 played 0 / 0 / 1 and its pull is 2.1d's
     (the proof measured); the last update played 1.0 / 1.0 / 2, the pull's proof at most 1e-3; nothing refused; every half's readouts on.
  B. live.json with SLOW_MIX 1.5 (out of its range 0 .. 1): the trainer refuses the file and stops before its first rollout; no update.
  C. without a trainer, tools/run/live_accept.py (the trainer's own reader) on files with SLOW_PICK 1.5 (not a whole number), SLOW_PICK 3 and
     SLOW_BACK -0.1 (out of range): each refused; SLOW_PICK 0 and 2: accepted.
Scratch run folders only (QLBOT_ROOT/data/sim_runs/scratch_21e_live<TAG>_a, _b, _c); nothing deleted.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1e/live_test.py <a 2.1d save> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
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


def prep(name):
    S.RUN = "scratch_21e_live" + os.environ.get("TEST_TAG", "") + "_" + name
    D = os.path.join(S.DATA, "data", "sim_runs", S.RUN)
    R1D = os.path.join(S.DATA, "data", "sim_runs", "duel_gru_2_1d")
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(os.path.join(R1D, "live.json"), os.path.join(D, "live_21d.json"))      # (a copy out of the running run: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21d.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    return D, R1D


def arm(name, start, late, updates):
    D, R1D = prep(name)
    s1, s1o, a1, a2 = sys.argv[1:5]
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    si_ = [sys.executable, os.path.join(S.CODE, "tools", "slow_init.py")]
    subprocess.check_call(si_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN)
    S.nonzero(os.path.join(D, "policy.pt"))
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        subprocess.check_call(si_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
                              env=cpu, creationflags=NOWIN)
    shutil.copy2(os.path.join(R1D, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=1.0, HELD_G=0.5, **start)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(S.small_cmd(D, updates).replace("\n", "\r\n"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=S.DATA, env=dict(os.environ, QLBOT_ROOT=S.DATA, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=NOWIN)
    wrote = False
    while tr.poll() is None and time.time() - t0 < 90 * 60:
        time.sleep(2)
        if late is not None and not wrote and os.path.exists(os.path.join(D, "metrics.jsonl")) and os.path.getsize(os.path.join(D, "metrics.jsonl")) > 0:
            lv.update(late)                                  # (after update 1: as the ramp and the owner write them)
            json.dump(lv, open(os.path.join(D, "live.json.tmp"), "w", encoding="utf-8"))
            os.replace(os.path.join(D, "live.json.tmp"), os.path.join(D, "live.json"))
            wrote = True
    logp = os.path.join(S.DATA, "data", "sim_runs", S.RUN + ".log")
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
    sl = [(m_.get("slow") or {}) for m_ in M]
    pu = [(m_.get("pull") or {}) for m_ in M]
    if name == "a":
        chk("arm a: exit 0, {} updates".format(updates), log.strip() and "exit 0" in log.splitlines()[-1] and len(M) == updates, len(M))
        chk("arm a: update 1 played SLOW_MIX 0, SLOW_BACK 0, SLOW_PICK 1; its pull measured (2.1d's sums)",
            sl and sl[0].get("mix") == 0.0 and sl[0].get("back") == 0.0 and sl[0].get("pick") == 1 and pu and pu[0].get("first_err") is not None,
            (sl[0].get("mix"), sl[0].get("back"), sl[0].get("pick"), pu[0].get("first_err")) if sl and pu else None)
        chk("arm a: the dials written after update 1 played by the last update (1.0, 1.0, the half 2), the pull's proof at most 1e-3",
            sl and sl[-1].get("mix") == 1.0 and sl[-1].get("back") == 1.0 and sl[-1].get("pick") == 2 and pu[-1].get("first_err") is not None
            and float(pu[-1]["first_err"]) <= 1e-3, (sl[-1].get("mix"), sl[-1].get("back"), sl[-1].get("pick"), pu[-1].get("first_err")) if sl else None)
        chk("arm a: every update every half's readouts (three halves, rows) and not off", sl and all(len(s_.get("halves") or []) == 3 and not s_.get("off")
                                                                                       and (s_.get("rows") or 0) > 0 for s_ in sl),
            [(len(s_.get("halves") or []), s_.get("rows"), s_.get("off")) for s_ in sl])
        chk("arm a: nothing refused", st.get("status") == "applied", st)
    else:
        chk("arm b: SLOW_MIX 1.5 refused, the trainer stopped before its first rollout, no update", st.get("status") == "refused" and len(M) == 0
            and "SLOW_MIX" in str(st.get("reason")), dict(status=st.get("status"), reason=st.get("reason"), updates=len(M)))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("arm {}: no NaN, traceback or MAJOR PROBLEM in the log".format(name), not bad, bad[:3])
    return ok


def arm_c():
    D, _ = prep("c")
    ok = True
    base = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    for nm_, val_, want_ in (("SLOW_PICK", 1.5, False), ("SLOW_PICK", 3, False), ("SLOW_BACK", -0.1, False), ("SLOW_MIX", 1.01, False),
                             ("SLOW_PICK", 0, True), ("SLOW_PICK", 2, True), ("SLOW_MIX", 1.0, True)):
        p_ = os.path.join(D, "live_{}_{}.json".format(nm_, val_))
        json.dump(dict(base, **{nm_: val_}), open(p_, "w", encoding="utf-8"))
        r_ = subprocess.run([sys.executable, os.path.join(S.CODE, "tools", "run", "live_accept.py"), p_, "--env", "duel_env_ffa20e"],
                            env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1", DODGE_IN="1"), capture_output=True, text=True, creationflags=NOWIN, cwd=S.CODE)
        got_ = r_.returncode == 0
        good_ = got_ == want_
        ok = ok and good_
        print(("PASS  " if good_ else "FAIL  ") + "arm c: {} = {} {} (live_accept: {})".format(
            nm_, val_, "accepted" if got_ else "refused", (r_.stdout.strip().splitlines() or [""])[0][-200:]), flush=True)
    return ok


def main():
    if not S.DATA or not os.path.isdir(os.path.join(S.DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    ok = arm_c()
    ok = arm("a", dict(SLOW_MIX=0.0, SLOW_BACK=0.0, SLOW_PICK=1), dict(SLOW_MIX=1.0, SLOW_BACK=1.0, SLOW_PICK=2), 4) and ok
    ok = arm("b", dict(SLOW_MIX=1.5, SLOW_BACK=0.0, SLOW_PICK=1), None, 2) and ok
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

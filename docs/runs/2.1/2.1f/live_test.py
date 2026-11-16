"""2.1f's live test of OUT_G, OUT_PICK, OUT_TRIAL (CLAUDE.md: every new live name gets its range and a live test). The smoke's small CPU trainer
(smoke.py's command at SMOKE_STEPS, default here 96: 2 simulators x 8 matches, below normal, pinned to the efficiency cores 0x3C3C; this checkout's
trainer, the data of QLBOT_ROOT) on a 2.1d save given the outlook (tools/out_init.py add; smoke.nonzero's non-zero last layer), in arms:
  A. live.json starts at OUT_G 0, OUT_PICK 0, OUT_TRIAL 0 (PULL_G 1.0, HELD_G 0.5); after update 1 it is written to OUT_G 2.0, OUT_PICK 1,
     OUT_TRIAL 0.05 (mid-run, as the ramp and the owner write them); 4 updates. PASS: update 1 played 0 / 0 / 0 with no term and no trial trip;
     the last update played 2.0 / 1 / 0.05 with a term above 0 and the pull's proof at most 1e-3; nothing refused; the outlook not off.
  B. live.json with OUT_G 25 (out of its range 0 .. 20): the trainer refuses the file and stops before its first rollout; no update.
  C. without a trainer, tools/run/live_accept.py (the trainer's own reader): OUT_PICK 1.5 (not whole), OUT_PICK 5, OUT_G 20.5, OUT_G -0.1,
     OUT_TRIAL 0.3: each refused; OUT_PICK 4, OUT_G 20, OUT_TRIAL 0.2: accepted.
Scratch run folders only (QLBOT_ROOT/data/sim_runs/scratch_21f_live<TAG>_a, _b, _c); nothing deleted.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1f/live_test.py <a 2.1d save> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("SMOKE_STEPS", "96")
import smoke as S                                            # noqa: E402  (its small command; its RUN set per arm)

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def prep(name):
    S.RUN = "scratch_21f_live" + os.environ.get("TEST_TAG", "") + "_" + name
    D = os.path.join(S.DATA, "data", "sim_runs", S.RUN)
    R1D = os.path.join(S.DATA, "data", "sim_runs", "duel_gru_2_1d")
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(os.path.join(R1D, "live.json"), os.path.join(D, "live_21d.json"))      # (a copy out of 2.1d's folder: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21d.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    return D, R1D


def arm(name, start, late, updates):
    D, R1D = prep(name)
    s1, s1o, a1, a2 = sys.argv[1:5]
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    oi_ = [sys.executable, os.path.join(S.CODE, "tools", "out_init.py")]
    subprocess.check_call(oi_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN)
    S.nonzero(os.path.join(D, "policy.pt"))
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        subprocess.check_call(oi_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
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
    while tr.poll() is None and time.time() - t0 < 120 * 60:
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
    ol = [(m_.get("outlook") or {}) for m_ in M]
    pu = [(m_.get("pull") or {}) for m_ in M]
    if name == "a":
        chk("arm a: exit 0, {} updates".format(updates), log.strip() and "exit 0" in log.splitlines()[-1] and len(M) == updates, len(M))
        chk("arm a: update 1 played OUT_G 0, OUT_PICK 0, OUT_TRIAL 0: no term, no trial trip; the pull's proof measured",
            ol and ol[0].get("g") == 0.0 and ol[0].get("pick") == 0 and ol[0].get("trial") == 0.0 and float(ol[0].get("size") or 0) == 0.0
            and int(ol[0].get("trial_trips") or 0) == 0 and pu and pu[0].get("first_err") is not None,
            (ol[0].get("g"), ol[0].get("pick"), ol[0].get("trial"), ol[0].get("size"), ol[0].get("trial_trips"), pu[0].get("first_err")) if ol and pu else None)
        chk("arm a: the dials written after update 1 played by the last update (2.0, 1, 0.05) with a term above 0, the pull's proof at most 1e-3",
            ol and ol[-1].get("g") == 2.0 and ol[-1].get("pick") == 1 and abs(float(ol[-1].get("trial") or 0) - 0.05) < 1e-9
            and float(ol[-1].get("size") or 0) > 0 and pu[-1].get("first_err") is not None and float(pu[-1]["first_err"]) <= 1e-3,
            (ol[-1].get("g"), ol[-1].get("pick"), ol[-1].get("trial"), ol[-1].get("size"), ol[-1].get("trial_trips"), pu[-1].get("first_err")) if ol else None)
        chk("arm a: every update the outlook's record, rows, not off", ol and all((o_.get("rows") or 0) > 0 and not o_.get("off") for o_ in ol),
            [(o_.get("rows"), o_.get("off")) for o_ in ol])
        chk("arm a: nothing refused", st.get("status") == "applied", st)
    else:
        chk("arm b: OUT_G 25 refused, the trainer stopped before its first rollout, no update", st.get("status") == "refused" and len(M) == 0
            and "OUT_G" in str(st.get("reason")), dict(status=st.get("status"), reason=st.get("reason"), updates=len(M)))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("arm {}: no NaN, traceback or MAJOR PROBLEM in the log".format(name), not bad, bad[:3])
    return ok


def arm_c():
    D, _ = prep("c")
    ok = True
    base = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    for nm_, val_, want_ in (("OUT_PICK", 1.5, False), ("OUT_PICK", 5, False), ("OUT_G", 20.5, False), ("OUT_G", -0.1, False), ("OUT_TRIAL", 0.3, False),
                             ("OUT_PICK", 4, True), ("OUT_G", 20.0, True), ("OUT_TRIAL", 0.2, True)):
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
    ok = arm("a", dict(OUT_G=0.0, OUT_PICK=0, OUT_TRIAL=0.0), dict(OUT_G=2.0, OUT_PICK=1, OUT_TRIAL=0.05), 4) and ok
    ok = arm("b", dict(OUT_G=25.0, OUT_PICK=0, OUT_TRIAL=0.0), None, 2) and ok
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

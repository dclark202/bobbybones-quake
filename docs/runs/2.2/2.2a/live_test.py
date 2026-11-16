"""2.2a's live test of OUT_G, OUT_PICK, OUT_TRIAL and OUT_SRC (CLAUDE.md: every new live name gets its range and a live test; made from 2.1f's). The
smoke's small CPU trainer (smoke.py's command at SMOKE_STEPS, default here 256: the map sense's horizon fits; 2 simulators x 8 matches, below
normal, pinned to 0x3C3C; this checkout's trainer, the data of QLBOT_ROOT) on the start file (tools/out22_init.py add; smoke.nonzero's non-zero last
layers), in arms:
  A. live.json starts at OUT_G 0, OUT_PICK 0, OUT_TRIAL 0, OUT_SRC 0 (PULL_G 1.0, HELD_G 0.5); after update 1 it is written to OUT_G 2.0,
     OUT_PICK 1, OUT_TRIAL 0.05, OUT_SRC 1 (mid-run, as the ramp and the owner write them); 4 updates. PASS: update 1 played 0 / 0 / 0 / 0 with no
     term and no trial trip; the last update played 2.0 / 1 / 0.05 / 1 (desc's term) with a term above 0 and the pull's proof at most 1e-3;
     nothing refused; nothing off.
  B. live.json with OUT_SRC 2 (out of its range 0 .. 1): the trainer refuses the file and stops before its first rollout; no update.
  C. without a trainer, tools/run/live_accept.py (the trainer's own reader): OUT_PICK 1.5 (not whole), OUT_PICK 7, OUT_G 20.5, OUT_G -0.1,
     OUT_TRIAL 0.3, OUT_SRC 0.5 (not whole), OUT_SRC 2, OUT_SRC -1: each refused; OUT_PICK 6, OUT_G 20, OUT_TRIAL 0.2, OUT_SRC 1, OUT_SRC 0:
     accepted.
Scratch run folders only (QLBOT_ROOT/data/sim_runs/scratch_22a_live<TAG>_a, _b, _c); nothing deleted.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.2/2.2a/live_test.py <the start file> <2.1d's opt.pt> <anchor a.pt> <anchor b.pt>"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("SMOKE_STEPS", "256")
import smoke as S                                            # noqa: E402  (its small command; its RUN set per arm)

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def prep(name):
    S.RUN = "scratch_22a_live" + os.environ.get("TEST_TAG", "") + "_" + name
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
    shutil.copy2(s1, os.path.join(D, "policy.pt"))
    S.nonzero(os.path.join(D, "policy.pt"))
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        shutil.copy2(a_, os.path.join(D, "snapshots", os.path.basename(a_)))
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
    ol = [dict(m_.get("outlook") or {}, src=(m_.get("out22") or {}).get("src"), off22=(m_.get("out22") or {}).get("off")) for m_ in M]
    pu = [(m_.get("pull") or {}) for m_ in M]
    if name == "a":
        chk("arm a: exit 0, {} updates".format(updates), log.strip() and "exit 0" in log.splitlines()[-1] and len(M) == updates, len(M))
        chk("arm a: update 1 played OUT_G 0, OUT_PICK 0, OUT_TRIAL 0, OUT_SRC 0: no term, no trial trip; the pull's proof measured",
            ol and ol[0].get("g") == 0.0 and ol[0].get("pick") == 0 and ol[0].get("trial") == 0.0 and ol[0].get("src") == 0 and float(ol[0].get("size") or 0) == 0.0
            and int(ol[0].get("trial_trips") or 0) == 0 and pu and pu[0].get("first_err") is not None,
            (ol[0].get("g"), ol[0].get("pick"), ol[0].get("trial"), ol[0].get("size"), ol[0].get("trial_trips"), pu[0].get("first_err")) if ol and pu else None)
        chk("arm a: the dials written after update 1 played by the last update (2.0, 1, 0.05, desc) with a term above 0, the pull's proof at most 1e-3",
            ol and ol[-1].get("g") == 2.0 and ol[-1].get("pick") == 1 and abs(float(ol[-1].get("trial") or 0) - 0.05) < 1e-9 and ol[-1].get("src") == 1
            and float(ol[-1].get("size") or 0) > 0 and pu[-1].get("first_err") is not None and float(pu[-1]["first_err"]) <= 1e-3,
            (ol[-1].get("g"), ol[-1].get("pick"), ol[-1].get("trial"), ol[-1].get("size"), ol[-1].get("trial_trips"), pu[-1].get("first_err")) if ol else None)
        chk("arm a: every update the outlook's record, rows, not off; 2.2a's not off", ol and all((o_.get("rows") or 0) > 0 and not o_.get("off")
            and not o_.get("off22") for o_ in ol), [(o_.get("rows"), o_.get("off"), o_.get("off22")) for o_ in ol])
        chk("arm a: nothing refused", st.get("status") == "applied", st)
    else:
        chk("arm b: OUT_SRC 2 refused, the trainer stopped before its first rollout, no update", st.get("status") == "refused" and len(M) == 0
            and "OUT_SRC" in str(st.get("reason")), dict(status=st.get("status"), reason=st.get("reason"), updates=len(M)))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("arm {}: no NaN, traceback or MAJOR PROBLEM in the log".format(name), not bad, bad[:3])
    return ok


def arm_c():
    D, _ = prep("c")
    ok = True
    base = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    for nm_, val_, want_ in (("OUT_PICK", 1.5, False), ("OUT_PICK", 7, False), ("OUT_G", 20.5, False), ("OUT_G", -0.1, False), ("OUT_TRIAL", 0.3, False),
                             ("OUT_SRC", 0.5, False), ("OUT_SRC", 2, False), ("OUT_SRC", -1, False),
                             ("OUT_PICK", 6, True), ("OUT_G", 20.0, True), ("OUT_TRIAL", 0.2, True), ("OUT_SRC", 1, True), ("OUT_SRC", 0, True)):
        p_ = os.path.join(D, "live_{}_{}.json".format(nm_, val_))
        json.dump(dict(base, **{nm_: val_}), open(p_, "w", encoding="utf-8"))
        r_ = subprocess.run([sys.executable, os.path.join(S.CODE, "tools", "run", "live_accept.py"), p_, "--env", "duel_env_ffa20e"],
                            env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1", DODGE_IN="1", DESC_OX="1", FIGHT_TRUTH="1"), capture_output=True, text=True, creationflags=NOWIN, cwd=S.CODE)
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
    ok = arm("a", dict(OUT_G=0.0, OUT_PICK=0, OUT_TRIAL=0.0, OUT_SRC=0), dict(OUT_G=2.0, OUT_PICK=1, OUT_TRIAL=0.05, OUT_SRC=1), 4) and ok
    ok = arm("b", dict(OUT_G=0.0, OUT_PICK=0, OUT_TRIAL=0.0, OUT_SRC=2), None, 2) and ok
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""2.1d's smoke (the pull; docs/runs/2.1/2.1d): the trainer of THIS checkout (its sim/: the worktree's code) runs 2.1d's command made small
(2 simulators x 8 matches x 96 frames, CPU, below normal, pinned to the efficiency cores 0x3C3C, 3 updates) on a 2.1c save given the slow plan
inside its head (tools/plan_init.py add), with its optimizer, two anchors widened the same way (plan_init widen-league), and start_live.py's
live.json (from 2.1c's live.json as it is, --any) with PULL_G and HELD_G set (SMOKE_PULL_G, default 1.0; SMOKE_HELD_G, default 0.5). Then the
save is resumed for one more update (the same folder, the same command). The data (maps, the judge, the legs, 2.1c's files) come from
QLBOT_ROOT (the main checkout); the scratch run folder is QLBOT_ROOT/data/sim_runs/scratch_21d_smoke<TEST_TAG>; nothing deleted, nothing else
written. Then ramp_21d.py --once over its metrics (the flags on real lines).
PASS: exit 0 both times; three lines then four in metrics.jsonl; live.json applied; the optimizer loaded, not cold; rec "pull" every update
with the strength played, its proof first_err measured and at most 1e-3 (with the pull above 0), its sizes finite; rec "plan" with rows on
the first horizon; rec "held" at the share; the save carries head2.plan.* and plan_opt and no top-level plan; the resume says "from the
checkpoint"; no NaN or traceback; the ramp's pass ends cleanly.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1d/smoke.py <a 2.1c save with its plan> <its opt.pt> <anchor a.pt> <anchor b.pt>
(train.cmd must exist: make_files.py first.)"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))   # this checkout (the worktree): its sim/ and tools/
DATA = os.environ.get("QLBOT_ROOT") or ""
BS = "\\"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUN = "scratch_21d_smoke" + os.environ.get("TEST_TAG", "")
PULL_G = float(os.environ.get("SMOKE_PULL_G", "1.0"))
HELD_G = float(os.environ.get("SMOKE_HELD_G", "0.5"))


def small_cmd(D, updates):
    """2.1d's train.cmd made small: this checkout's trainer, the data's root, CPU, below normal on the efficiency cores"""
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(DATA, DATA)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal /affinity 3C3C "),
                 ("python.exe sim" + BS + "train_duel_rnn.py ", "python.exe " + os.path.join(CODE, "sim", "train_duel_rnn.py") + " "),
                 ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "),
                 ("--minibatches 360 ", "--minibatches 4 "), ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 --plan-every 2 >> ")):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    L_ = t.split("\n")                                       # (the command line only: the rem lines name the history's lengths)
    cl_ = [i for i, x in enumerate(L_) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1 and len(re.findall(r"--max-updates \d+ ", L_[cl_[0]])) == 1
    L_[cl_[0]] = re.sub(r"--max-updates \d+ ", "--max-updates {} ".format(updates), L_[cl_[0]])
    t = "\n".join(L_)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + RUN + ".log", t)
    assert not any("duel_gru_2_" in x for x in t.split("\n") if not x.startswith("rem"))
    return t


def run_cmd(D, name, t):
    cmd = os.path.join(D, name)
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=DATA, env=dict(os.environ, QLBOT_ROOT=DATA, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=NOWIN)
    while tr.poll() is None and time.time() - t0 < 60 * 60:
        time.sleep(10)
    return tr, t0


def main():
    if not DATA or not os.path.isdir(os.path.join(DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    D = os.path.join(DATA, "data", "sim_runs", RUN)
    R1C = os.path.join(DATA, "data", "sim_runs", "duel_gru_2_1c")
    s1, s1o, a1, a2 = sys.argv[1:5]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for p_ in (s1, s1o, a1, a2, os.path.join(HERE, "train.cmd"), os.path.join(HERE, "aim2_env.cmd"), os.path.join(R1C, "live.json"),
               os.path.join(R1C, "live_settings.env")):
        if not os.path.exists(p_):
            raise SystemExit("MISSING " + p_ + ": not started")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    pi_ = [sys.executable, os.path.join(CODE, "tools", "plan_init.py")]
    add_ = subprocess.run(pi_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN, capture_output=True, text=True)
    print(add_.stdout.strip(), add_.stderr.strip()[-2000:], flush=True)
    assert add_.returncode == 0, "plan_init add failed"
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        w_ = subprocess.run(pi_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
                            env=cpu, creationflags=NOWIN, capture_output=True, text=True)
        print(w_.stdout.strip(), w_.stderr.strip()[-2000:], flush=True)
        assert w_.returncode == 0, "plan_init widen-league failed"
    shutil.copy2(os.path.join(R1C, "live_settings.env"), os.path.join(D, "live_settings.env"))
    shutil.copy2(os.path.join(R1C, "live.json"), os.path.join(D, "live_21c.json"))      # (a copy out of the running run: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21c.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=PULL_G, HELD_G=HELD_G)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    tr, t0 = run_cmd(D, "small.cmd", small_cmd(D, 3))
    logp = os.path.join(DATA, "data", "sim_runs", RUN + ".log")
    log = open(logp, encoding="utf-8", errors="replace").read() if os.path.exists(logp) else ""
    mp = os.path.join(D, "metrics.jsonl")
    M = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ok = True

    def chk(name, good, more=""):
        nonlocal ok
        ok = ok and bool(good)
        print(("PASS  " if good else "FAIL  ") + name + (" | " + str(more)[:1500] if more != "" else ""), flush=True)

    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-1][-300:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold", bool(opt_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in opt_), opt_[:3])
    pl_l = [x for x in log.splitlines() if "slow plan INSIDE the head" in x]
    chk("the trainer's plan line: inside the head, its Adam from the checkpoint, the pull", bool(pl_l) and "from the checkpoint" in pl_l[0] and "THE PULL" in pl_l[0], pl_l[:1])
    pu = [(m_.get("pull") or {}) for m_ in M]
    print("pull records: " + json.dumps(pu), flush=True)
    num_ = lambda v_: isinstance(v_, (int, float)) and math.isfinite(float(v_))    # noqa: E731
    chk("rec pull every update, the strength played {}".format(PULL_G), M and all(p_ and abs(float(p_.get("g", -1)) - PULL_G) < 1e-6 for p_ in pu), [p_.get("g") for p_ in pu])
    fe_ = [p_.get("first_err") for p_ in pu]
    chk("the pull's proof measured every update, at most 1e-3 (pull_first_err)", M and all(x_ is not None and float(x_) <= 1e-3 for x_ in fe_), fe_)
    chk("the pull's sizes finite (size, norm, max) and the parts named", M and all(num_(p_.get("size")) and num_(p_.get("norm")) and num_(p_.get("max"))
                                                                                  and isinstance(p_.get("parts"), dict) for p_ in pu),
        [(p_.get("size"), p_.get("norm"), p_.get("max"), p_.get("parts")) for p_ in pu])
    if PULL_G > 0:
        chk("the pull moved his target scores (size above 0)", M and all(float(p_.get("size") or 0) > 0 for p_ in pu), [p_.get("size") for p_ in pu])
    else:
        chk("at strength 0 the pull is zero to the bit (size 0, max 0)", M and all(float(p_.get("size", 1)) == 0 and float(p_.get("max", 1)) == 0 for p_ in pu),
            [(p_.get("size"), p_.get("max")) for p_ in pu])
    pn = (M[-1].get("plan") or {}) if M else {}
    chk("rec plan: the first horizon with rows (n > 0), finite readouts, the lesson's loss", int((pn.get("h2s") or {}).get("n", 0)) > 0
        and num_((pn.get("h2s") or {}).get("kl_plan")) and num_(pn.get("loss")), {k_: pn.get(k_) for k_ in ("h2s", "h5s", "loss", "rows")})
    chk("rec plan: the pull's counterfactual and the kinds of changes", sorted((pn.get("pull_changes_min") or {}).keys()) == ["0.0", "0.5", "1.0", "2.0"]
        and isinstance(pn.get("changes"), dict), {k_: pn.get(k_) for k_ in ("pull_changes_min", "changes")})
    hd = (M[-1].get("held") or {}) if M else {}
    chk("rec held at the share {}".format(HELD_G), hd and abs(float(hd.get("g", -1)) - HELD_G) < 1e-6 and
        (HELD_G == 0.0 and float(hd.get("share", 1)) == 0.0 or 0.15 < float(hd.get("share", 0)) < 0.85), hd)
    no_major = [x for x in log.splitlines() if "MAJOR PROBLEM" in x]
    chk("no MAJOR PROBLEM line in the trainer's log (the plan's guard)", not no_major, no_major[:2])
    try:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        chk("the save: head2.plan.* in model, pull_g {}, plan_opt beside it, no top-level plan".format(PULL_G),
            all("head2.plan.l{}.weight".format(i_) in ck_["model"] for i_ in (1, 2, 3)) and abs(float(ck_["model"]["head2.pull_g"]) - PULL_G) < 1e-6
            and bool(ck_.get("plan_opt")) and "plan" not in ck_ and (ck_.get("head2") or {}).get("slowplan"),
            dict(plan_opt=bool(ck_.get("plan_opt")), plan=("plan" in ck_), pull_g=float(ck_["model"].get("head2.pull_g", -1)), slowplan=(ck_.get("head2") or {}).get("slowplan")))
        sn_ = [f_ for f_ in os.listdir(os.path.join(D, "snapshots")) if f_.startswith("snap_")]
        chk("a snapshot of this run (the league plays its own pull from it)", bool(sn_), sn_)
    except Exception as e_:                                  # noqa: BLE001
        chk("the save read", False, repr(e_))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    # the resume: one more update from the save just written (its plan, its Adam, the main optimizer)
    tr2, t2 = run_cmd(D, "small_resume.cmd", small_cmd(D, 1))
    log2 = open(logp, encoding="utf-8", errors="replace").read()[len(log):] if os.path.exists(logp) else ""
    M2 = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    pl2 = [x for x in log2.splitlines() if "slow plan INSIDE the head" in x]
    chk("the resume: exit 0, a fourth update", log2.strip() and "exit 0" in log2.splitlines()[-1] and len(M2) == 4, (len(M2), log2.rstrip().splitlines()[-1:] if log2.strip() else ""))
    chk("the resume reads the plan's Adam from the checkpoint", bool(pl2) and "from the checkpoint" in pl2[0], pl2[:1])
    o2_ = [x for x in log2.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the resume's optimizer loaded, not cold", bool(o2_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in o2_), o2_[:2])
    p4_ = (M2[-1].get("pull") or {}) if len(M2) == 4 else {}
    chk("the resume's pull proof", p4_.get("first_err") is not None and float(p4_["first_err"]) <= 1e-3, p4_.get("first_err"))
    bad2 = [x for x in log2.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("the resume: no NaN, traceback or MAJOR PROBLEM", not bad2, bad2[:3])
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_21d.py"), RUN, "--dir", D, "--once"], cwd=CODE, capture_output=True, text=True,
                         creationflags=NOWIN)
    wl_ = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(
        os.path.join(D, "watch", "watch.log")) else []
    pll_ = [x for x in wl_ if ": pull: strength" in x]
    chk("the ramp's pass over the metrics: exit 0, a pull line an update, no crash", rp_.returncode == 0 and len(pll_) == len(M2) and
        not any("CRASHED" in x for x in wl_), (rp_.returncode, rp_.stderr[-800:], len(pll_)))
    for x in wl_:
        print("    ramp: " + x, flush=True)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""2.1f's smoke (the outlook inside the head; docs/runs/2.1/2.1f): the trainer of THIS checkout (its sim/: the worktree's code) runs 2.1f's command
made small (2 simulators x 8 matches x SMOKE_STEPS frames, default 384 so that the 8-second windows of all8 and win8 fit, CPU, below normal, pinned
to the efficiency cores 0x3C3C, 3 updates) on a 2.1d save given the outlook (tools/out_init.py add) with its optimizer, two anchors widened the
same way (out_init widen-league), and start_live.py's live.json (from 2.1d's live.json as it is, --any) with PULL_G 1.0, HELD_G 0.5, OUT_G 1.0,
OUT_PICK 0, OUT_TRIAL 0.1 (SMOKE_PULL_G, SMOKE_HELD_G, SMOKE_OUT_G, SMOKE_PICK, SMOKE_TRIAL). With SMOKE_NONZERO=1 (the default) the start file's
outlook last layer is made non-zero first (a fixed-seed random, the test only) so that the term plays from update 1 and the pull's proof covers
it. With SMOKE_LEAGUE=1 (the default) the start file at out_g 0.5, out_pick 1 is put in the league as the run's own snapshot (snap_0000.pt), so
that the league's seats play an outlook of their own. Then the save is resumed for one more update (the same folder, the same command). The data
come from QLBOT_ROOT (the main checkout); the scratch run folder is QLBOT_ROOT/data/sim_runs/scratch_21f_smoke<TEST_TAG>; nothing deleted, nothing
else written. Then ramp_21f.py --once over its metrics (no out_mark.json: OUT_G never written).
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1f/smoke.py <a 2.1d save> <its opt.pt> <anchor a.pt> <anchor b.pt>
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
RUN = "scratch_21f_smoke" + os.environ.get("TEST_TAG", "")
PULL_G = float(os.environ.get("SMOKE_PULL_G", "1.0"))
HELD_G = float(os.environ.get("SMOKE_HELD_G", "0.5"))
OUT_G = float(os.environ.get("SMOKE_OUT_G", "1.0"))
PICK = int(os.environ.get("SMOKE_PICK", "0"))
TRIAL = float(os.environ.get("SMOKE_TRIAL", "0.1"))
STEPS = int(os.environ.get("SMOKE_STEPS", "384"))
NONZERO = os.environ.get("SMOKE_NONZERO", "1") == "1"
LEAGUE = os.environ.get("SMOKE_LEAGUE", "1") == "1"
KINDS = ["seg", "ret", "all8", "win8", "win5"]


def small_cmd(D, updates):
    """2.1f's train.cmd made small: this checkout's trainer, the data's root, CPU, below normal on the efficiency cores"""
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(DATA, DATA)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal /affinity 3C3C "),
                 ("python.exe sim" + BS + "train_duel_rnn.py ", "python.exe " + os.path.join(CODE, "sim", "train_duel_rnn.py") + " "),
                 ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps {} ".format(STEPS)),
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
    while tr.poll() is None and time.time() - t0 < 150 * 60:
        time.sleep(10)
    return tr, t0


def nonzero(path, seed=2126, scale=1.0):
    """the start file's outlook last layer made non-zero (a fixed-seed random; the test only)"""
    import torch
    ck = torch.load(path, weights_only=False, map_location="cpu")
    g = torch.Generator().manual_seed(seed)
    sd = ck["model"]
    w_ = sd["head2.out.l3.weight"]
    sd["head2.out.l3.weight"] = torch.randn(w_.shape, generator=g) * (scale / float(w_.shape[1]) ** 0.5)
    sd["head2.out.l3.bias"] = torch.randn(sd["head2.out.l3.bias"].shape, generator=g) * 0.1
    torch.save(ck, path)
    print("SMOKE_NONZERO: the outlook's last layer made non-zero (seed {})".format(seed), flush=True)


def main():
    if not DATA or not os.path.isdir(os.path.join(DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    D = os.path.join(DATA, "data", "sim_runs", RUN)
    R1D = os.path.join(DATA, "data", "sim_runs", "duel_gru_2_1d")
    s1, s1o, a1, a2 = sys.argv[1:5]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for p_ in (s1, s1o, a1, a2, os.path.join(HERE, "train.cmd"), os.path.join(HERE, "aim2_env.cmd"), os.path.join(R1D, "live.json"),
               os.path.join(R1D, "live_settings.env")):
        if not os.path.exists(p_):
            raise SystemExit("MISSING " + p_ + ": not started")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    oi_ = [sys.executable, os.path.join(CODE, "tools", "out_init.py")]
    add_ = subprocess.run(oi_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN, capture_output=True, text=True)
    print(add_.stdout.strip(), add_.stderr.strip()[-2000:], flush=True)
    assert add_.returncode == 0, "out_init add failed"
    if NONZERO:
        nonzero(os.path.join(D, "policy.pt"))
    if LEAGUE:                                               # (a league file with an outlook of its own that plays: the start file at out_g 0.5, the
        import torch                                         # kind 1, as the run's own first snapshot: the league's path is exercised)
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        ck_["model"]["head2.out_g"], ck_["model"]["head2.out_pick"] = torch.tensor(0.5), torch.tensor(1.0)
        torch.save(ck_, os.path.join(D, "snapshots", "snap_0000.pt"))
        print("SMOKE_LEAGUE: snapshots/snap_0000.pt = the start file at out_g 0.5, out_pick 1 (the league's own outlook plays)", flush=True)
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        w_ = subprocess.run(oi_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
                            env=cpu, creationflags=NOWIN, capture_output=True, text=True)
        print(w_.stdout.strip(), w_.stderr.strip()[-2000:], flush=True)
        assert w_.returncode == 0, "out_init widen-league failed"
    shutil.copy2(os.path.join(R1D, "live_settings.env"), os.path.join(D, "live_settings.env"))
    shutil.copy2(os.path.join(R1D, "live.json"), os.path.join(D, "live_21d.json"))      # (a copy out of 2.1d's folder: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21d.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=PULL_G, HELD_G=HELD_G, OUT_G=OUT_G, OUT_PICK=PICK, OUT_TRIAL=TRIAL)
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
        print(("PASS  " if good else "FAIL  ") + name + (" | " + str(more)[:2500] if more != "" else ""), flush=True)

    num_ = lambda v_: isinstance(v_, (int, float)) and math.isfinite(float(v_))    # noqa: E731
    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-1][-300:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold", bool(opt_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in opt_), opt_[:4])
    ol_ = [x for x in log.splitlines() if "the outlook INSIDE the head" in x]
    chk("the trainer's outlook line: inside the head, its Adam new at the first start", bool(ol_) and "Adam 0.0003 (new)" in ol_[0], ol_[:1])
    O_ = [(m_.get("outlook") or {}) for m_ in M]
    print("outlook records: " + json.dumps(O_)[:12000], flush=True)
    chk("rec outlook every update, played as set (g {}, pick {}, trial {}), not off".format(OUT_G, PICK, TRIAL), M and all(
        o_ and abs(float(o_.get("g", -1)) - OUT_G) < 1e-6 and int(o_.get("pick", -1)) == PICK and abs(float(o_.get("trial", -1)) - TRIAL) < 1e-6
        and not o_.get("off") and o_.get("kinds") == KINDS for o_ in O_), [(o_.get("g"), o_.get("pick"), o_.get("trial"), o_.get("off")) for o_ in O_])
    chk("rows every update: every keep reading on a held trip (decision and stay readings both), as the rollout counted them",
        all((o_.get("rows") or 0) > 0 and 0 < (o_.get("rows_decision") or 0) < o_["rows"] and o_.get("rows") == o_.get("readings")
            and o_.get("rows_decision") == o_.get("decisions") for o_ in O_),
        [(o_.get("rows"), o_.get("rows_decision"), o_.get("readings"), o_.get("decisions")) for o_ in O_])
    kr_ = []
    for o_ in O_:
        for k_ in KINDS:
            kd_ = (o_.get("kind") or {}).get(k_) or {}
            kr_.append((k_, kd_.get("rows"), (kd_.get("all") or {}).get("r2_goal"), (kd_.get("all") or {}).get("r2_blind"),
                        (kd_.get("decision") or {}).get("rows"), (kd_.get("stay") or {}).get("rows"), sorted((kd_.get("replay") or {}).keys()),
                        (kd_.get("z") or {}).get("p99")))
    chk("every kind every update: rows, R2 per goal and goal-blind finite overall, decision and stay rows, the replay at 0.5 .. 8, z's percentiles",
        all((r_[1] or 0) > 0 and num_(r_[2]) and num_(r_[3]) and (r_[4] or 0) > 0 and (r_[5] or 0) > 0 and r_[6] == ["0.5", "1.0", "2.0", "4.0", "8.0"]
            and num_(r_[7]) for r_ in kr_), kr_)
    chk("the labels' raw statistics: every kind with a spread above 0 (the win stream reaches the win kinds)",
        all(all((((o_.get("raw") or {}).get(k_)) or {}).get("sd", 0) > 0 for k_ in KINDS) for o_ in O_[1:] + O_[:1]),
        [{k_: (o_.get("raw") or {}).get(k_) for k_ in KINDS} for o_ in O_])
    sg_ = [o_.get("seg_readings") for o_ in O_]
    chk("the seg segments' lengths (readings): mean above 0, percentiles", all(s_ and num_(s_.get("mean")) and s_["mean"] > 0 for s_ in sg_), sg_)
    chk("a loss and the last layer's size every update", all(num_(o_.get("loss")) and num_(o_.get("l3")) for o_ in O_),
        [(o_.get("loss"), o_.get("l3")) for o_ in O_])
    if OUT_G > 0 and NONZERO:
        chk("the term played: its size above 0 on his frames, the share of his readings it changed recorded", all(
            float(o_.get("size") or 0) > 0 and num_(o_.get("changed")) for o_ in O_), [(o_.get("size"), o_.get("max"), o_.get("changed")) for o_ in O_])
    if TRIAL > 0:
        chk("trial trips: begun, their readings counted, none of their frames left in a target lesson",
            sum(int(o_.get("trial_trips") or 0) for o_ in O_) > 0 and sum(int(o_.get("trial_readings") or 0) for o_ in O_) > 0
            and all(int(o_.get("trial_in_lesson", -1)) == 0 for o_ in O_) and sum(int(o_.get("rows_trial") or 0) for o_ in O_) > 0,
            [(o_.get("trial_trips"), o_.get("trial_readings"), o_.get("trial_in_lesson"), o_.get("rows_trial")) for o_ in O_])
    else:
        chk("no trial trip at OUT_TRIAL 0", all(int(o_.get("trial_trips") or 0) == 0 and int(o_.get("trial_readings") or 0) == 0 for o_ in O_),
            [(o_.get("trial_trips"), o_.get("trial_readings")) for o_ in O_])
    pu = [(m_.get("pull") or {}) for m_ in M]
    fe_ = [p_.get("first_err") for p_ in pu]
    chk("the pull's proof with the outlook's term at {}: measured every update, at most 1e-3 (pull_first_err)".format(OUT_G),
        M and all(x_ is not None and float(x_) <= 1e-3 for x_ in fe_), fe_)
    no_major = [x for x in log.splitlines() if "MAJOR PROBLEM" in x]
    chk("no MAJOR PROBLEM line in the trainer's log (the plan's and the outlook's guards)", not no_major, no_major[:2])
    try:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        chk("the save: head2.out.* in model, the dials ({}, {}), out_opt and out_stats beside it, plan_opt kept, the layout's kinds".format(OUT_G, PICK),
            "head2.out.l3.weight" in ck_["model"] and abs(float(ck_["model"]["head2.out_g"]) - OUT_G) < 1e-6
            and int(round(float(ck_["model"]["head2.out_pick"]))) == PICK and bool(ck_.get("out_opt")) and bool(ck_.get("out_stats"))
            and bool(ck_.get("plan_opt")) and ck_["head2"]["outlook"]["kinds"] == KINDS,
            dict(out_opt=bool(ck_.get("out_opt")), out_stats=ck_.get("out_stats"), g=float(ck_["model"].get("head2.out_g", -1)),
                 pick=float(ck_["model"].get("head2.out_pick", -1)), outlook=(ck_.get("head2") or {}).get("outlook")))
        lg_ = [(o_.get("g_opp"), o_.get("pick_opp"), o_.get("opp_has")) for o_ in O_]
        print("INFO  snapshots of this run: {}; the league's (g, pick, plays) by update {}".format(
            [f_ for f_ in os.listdir(os.path.join(D, "snapshots")) if f_.startswith("snap_")], lg_), flush=True)
        if LEAGUE:
            chk("the league's own outlook played in some update (snap_0000: g 0.5, pick 1; an anchor: none)",
                any(x_[2] and x_[0] == 0.5 and x_[1] == 1 for x_ in lg_), lg_)
    except Exception as e_:                                  # noqa: BLE001
        chk("the save read", False, repr(e_))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    # the resume: one more update from the save just written (the outlook, its Adam, its statistics, the main optimizer)
    tr2, t2 = run_cmd(D, "small_resume.cmd", small_cmd(D, 1))
    log2 = open(logp, encoding="utf-8", errors="replace").read()[len(log):] if os.path.exists(logp) else ""
    M2 = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    ol2 = [x for x in log2.splitlines() if "the outlook INSIDE the head" in x]
    chk("the resume: exit 0, a fourth update", log2.strip() and "exit 0" in log2.splitlines()[-1] and len(M2) == 4, (len(M2), log2.rstrip().splitlines()[-1:] if log2.strip() else ""))
    chk("the resume reads the outlook's Adam and its labels' statistics from the checkpoint", bool(ol2) and "Adam 0.0003 (from the checkpoint)" in ol2[0]
        and "statistics (from the checkpoint)" in ol2[0], ol2[:1])
    o2_ = [x for x in log2.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the resume's optimizer loaded, not cold", bool(o2_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in o2_), o2_[:2])
    q4_ = (M2[-1].get("outlook") or {}) if len(M2) == 4 else {}
    p4_ = (M2[-1].get("pull") or {}) if len(M2) == 4 else {}
    chk("the resume's outlook record and the pull's proof", q4_ and (q4_.get("rows") or 0) > 0 and p4_.get("first_err") is not None
        and float(p4_["first_err"]) <= 1e-3, (q4_.get("g"), q4_.get("rows"), p4_.get("first_err")))
    bad2 = [x for x in log2.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("the resume: no NaN, traceback or MAJOR PROBLEM", not bad2, bad2[:3])
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_21f.py"), RUN, "--dir", D, "--once"], cwd=CODE, capture_output=True, text=True,
                         creationflags=NOWIN)
    wl_ = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(
        os.path.join(D, "watch", "watch.log")) else []
    okl_ = [x for x in wl_ if ": outlook " in x and " skill " in x]
    opl_ = [x for x in wl_ if ": outlook plays: " in x]
    chk("the ramp's pass over the metrics: exit 0, a skill line per kind and a 'plays' line an update, no crash",
        rp_.returncode == 0 and len(okl_) == len(KINDS) * len(M2) and len(opl_) == len(M2) and not any("CRASHED" in x for x in wl_),
        (rp_.returncode, rp_.stderr[-800:], len(okl_), len(opl_)))
    wr_ = [x for x in wl_ if "wrote" in x and "OUT_G" in x]
    chk("the ramp never wrote OUT_G (no out_mark.json)", not wr_, wr_[:2])
    mj_ = [x for x in wl_ if "MAJOR PROBLEM" in x]
    chk("the ramp's pass: no MAJOR PROBLEM (the dials played as the file has them)", not mj_, mj_[:3])
    for x in wl_:
        print("    ramp: " + x, flush=True)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

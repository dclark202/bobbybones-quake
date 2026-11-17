"""2.2a's smoke (made from 2.1f's): the trainer of THIS checkout runs 2.2a's command made small (2 simulators x 8 matches x SMOKE_STEPS frames, 384:
the 8-second windows fit; CPU, below normal, pinned to 0x3C3C; SMOKE_UPDATES updates, default 4) on the start file (tools/out22_init.py add's, given
as the first argument) with 2.1d's optimizer, two 2.1d anchors as they are (the trainer gives them 2.2a's parts at zero), and a live.json from
start_live.py (2.1d's, --any) with PULL_G 1.0, HELD_G 0.5, OUT_G SMOKE_OUT_G (1.0), OUT_SRC SMOKE_SRC (1: desc's term plays), OUT_TRIAL SMOKE_TRIAL
(0.1). With SMOKE_NONZERO=1 (default) the start's built outlook's l3, desc's l3 and the tracker's l3 are made non-zero first (fixed seeds; the test
only) so that the terms play from update 1 and the pull's proof covers them. With SMOKE_LEAGUE=1 (default) the start at out_g 0.5, out_src 1 is the
run's own snapshot (snap_0000.pt): the league's seats play desc's term of their own. Then a resume for one more update. Then ramp_22a.py --once
over the metrics. Scratch folder QLBOT_ROOT/data/sim_runs/scratch_22a_smoke<TEST_TAG>; nothing deleted, nothing else written.
SMOKE_EXTRA (e.g. "--seed 7 --dump-acts <path>") and SMOKE_UPDATES 2: the identity test's arm (only the run, no other check).
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.2/2.2a/smoke.py <start file (out22_init add)> <2.1d's opt.pt> <anchor a.pt> <anchor b.pt>"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DATA = os.environ.get("QLBOT_ROOT") or ""
BS = "\\"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUN = "scratch_22a_smoke" + os.environ.get("TEST_TAG", "")
PULL_G = float(os.environ.get("SMOKE_PULL_G", "1.0"))
HELD_G = float(os.environ.get("SMOKE_HELD_G", "0.5"))
OUT_G = float(os.environ.get("SMOKE_OUT_G", "1.0"))
SRC = int(os.environ.get("SMOKE_SRC", "1"))
TRIAL = float(os.environ.get("SMOKE_TRIAL", "0.1"))
STEPS = int(os.environ.get("SMOKE_STEPS", "384"))
UPD = int(os.environ.get("SMOKE_UPDATES", "4"))
NONZERO = os.environ.get("SMOKE_NONZERO", "1") == "1"
LEAGUE = os.environ.get("SMOKE_LEAGUE", "1") == "1"
EXTRA = os.environ.get("SMOKE_EXTRA", "")
CMD = os.environ.get("SMOKE_CMD") or os.path.join(HERE, "train.cmd")    # (the identity test's other arm: 2.1d's command)
KINDS = ["seg", "ret", "all8", "win8", "win5", "segw", "winit8"]


def small_cmd(D, updates):
    t = open(CMD, encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(DATA, DATA)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal /affinity 3C3C "),
                 ("python.exe sim" + BS + "train_duel_rnn.py ", "python.exe " + os.path.join(CODE, "sim", "train_duel_rnn.py") + " "),
                 ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps {} ".format(STEPS)),
                 ("--minibatches 360 ", "--minibatches 4 "),
                 ("%LEARN% >> ", ("--snapshot-min 1 --overlap 1 --learn-nosync 1 --plan-every 2 " if not EXTRA else
                                 "--snapshot-min 1000 " + ("--overlap 1 --learn-nosync 1 " if os.environ.get("SMOKE_OVERLAP") == "1" else "")) + EXTRA + " >> ")):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = t.replace("%ROOT%\\docs\\runs\\2.2\\2.2a\\items_22a.json", os.path.join(CODE, "docs", "runs", "2.2", "2.2a", "items_22a.json"))
    L_ = t.split("\n")
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
    while tr.poll() is None and time.time() - t0 < 240 * 60:
        time.sleep(10)
    return tr, t0


def nonzero(path):
    import torch
    ck = torch.load(path, weights_only=False, map_location="cpu")
    sd = ck["model"]
    g = torch.Generator().manual_seed(2126)
    for k_, sc_ in (("head2.out.l3.weight", 1.0), ("head2.dsc.desc.l3.weight", 2.0), ("head2.trk.l3.weight", 1.0)):
        w_ = sd[k_]
        sd[k_] = torch.randn(w_.shape, generator=g) * (sc_ / float(w_.shape[1]) ** 0.5)
    torch.save(ck, path)
    print("SMOKE_NONZERO: the built outlook's, desc's and the tracker's last layers made non-zero (seed 2126)", flush=True)


def main():
    if not DATA or not os.path.isdir(os.path.join(DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    D = os.path.join(DATA, "data", "sim_runs", RUN)
    R1D = os.path.join(DATA, "data", "sim_runs", "duel_gru_2_1d")
    s1, s1o, a1, a2 = sys.argv[1:5]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for p_ in (s1, s1o, a1, a2, CMD, os.path.join(HERE, "aim2_env.cmd"), os.path.join(R1D, "live.json"), os.path.join(R1D, "live_settings.env")):
        if not os.path.exists(p_):
            raise SystemExit("MISSING " + p_ + ": not started")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(s1, os.path.join(D, "policy.pt"))
    if NONZERO:
        nonzero(os.path.join(D, "policy.pt"))
    if LEAGUE:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        ck_["model"]["head2.out_g"], ck_["model"]["head2.out_pick"], ck_["model"]["head2.out_src"] = torch.tensor(0.5), torch.tensor(0.0), torch.tensor(1.0)
        torch.save(ck_, os.path.join(D, "snapshots", "snap_0000.pt"))
        print("SMOKE_LEAGUE: snapshots/snap_0000.pt = the start file at out_g 0.5, out_src 1 (the league's own desc term plays)", flush=True)
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        shutil.copy2(a_, os.path.join(D, "snapshots", os.path.basename(a_)))
    shutil.copy2(os.path.join(R1D, "live_settings.env"), os.path.join(D, "live_settings.env"))
    shutil.copy2(os.path.join(R1D, "live.json"), os.path.join(D, "live_21d.json"))
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21d.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=PULL_G, HELD_G=HELD_G, OUT_G=OUT_G, OUT_PICK=0, OUT_TRIAL=TRIAL, OUT_SRC=SRC)
    if os.environ.get("SMOKE_NO_OUT") == "1":                  # (the identity test's 2.1d arm: none of the outlook's names, 2.1d's live file)
        for k_ in ("OUT_G", "OUT_PICK", "OUT_TRIAL", "OUT_SRC"):
            lv.pop(k_, None)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    tr, t0 = run_cmd(D, "small.cmd", small_cmd(D, UPD))
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
    chk("{} updates in metrics.jsonl".format(UPD), len(M) == UPD, len(M))
    if EXTRA:
        print("ALL PASSED" if ok else "FAILED")
        return 0 if ok else 1
    chk("live.json applied", st.get("status") == "applied", st)
    l22 = [x for x in log.splitlines() if "2.2a (--out22)" in x]
    chk("the trainer's 2.2a line: the Adams new at the first start, the norm measured", bool(l22) and "Adams new" in l22[0] and "norm measured: True" in l22[0], l22[:1])
    O_ = [(m_.get("outlook") or {}) for m_ in M]
    Q_ = [(m_.get("out22") or {}) for m_ in M]
    chk("rec outlook and out22 every update, played as set (g {}, src {}, trial {}), not off".format(OUT_G, SRC, TRIAL), M and all(
        o_ and q_ and abs(float(o_.get("g", -1)) - OUT_G) < 1e-6 and int(q_.get("src", -1)) == SRC and abs(float(o_.get("trial", -1)) - TRIAL) < 1e-6
        and not o_.get("off") and not q_.get("off") and o_.get("kinds") == KINDS for o_, q_ in zip(O_, Q_)),
        [(o_.get("g"), q_.get("src"), o_.get("trial"), o_.get("off"), q_.get("off")) for o_, q_ in zip(O_, Q_)])
    bad_ = []
    for u_, (o_, q_) in enumerate(zip(O_, Q_)):
        for k_ in KINDS:
            for nm_, kd_ in (("built", (o_.get("kind") or {}).get(k_) or {}),) + tuple((s_, (((q_.get("desc") or {}).get(s_) or {}).get("kind") or {}).get(k_) or {})
                                                                                      for s_ in ("desc", "desc_nomap", "desc_notrk")):
                al_ = kd_.get("all") or {}
                if not ((kd_.get("rows") or 0) > 0 and num_(al_.get("r2_goal")) and num_(al_.get("r2_blind")) and (kd_.get("decision") or {}).get("rows")
                        and (kd_.get("stay") or {}).get("rows") and sorted((kd_.get("replay") or {}).keys()) == ["0.5", "1.0", "2.0", "4.0", "8.0"]):
                    bad_.append((u_ + 1, nm_, k_, kd_.get("rows"), al_.get("r2_goal")))
    chk("every kind of the built outlook and of the three desc siblings, every update: rows, R2 goal and goal-blind, decision and stay rows, the "
        "replay at 0.5 .. 8", not bad_, bad_[:8])
    fb_ = []
    for u_, (o_, q_) in enumerate(zip(O_, Q_)):
        for nm_, fd_ in (("built", o_.get("facts") or {}), ("desc", ((q_.get("desc") or {}).get("desc") or {}).get("facts") or {})):
            for f_ in ("he_dies", "i_die", "took", "my_h", "my_a", "en_h", "en_a"):
                if not ((fd_.get(f_) or {}).get("all") or {}).get("rows"):
                    fb_.append((u_ + 1, nm_, f_))
    chk("the facts of both outlooks every update (rows, Brier skill or R2)", not fb_, fb_[:8])
    raw_ = [(o_.get("raw") or {}) for o_ in O_]
    chk("the label kinds' raw statistics: segw and winit8 with a spread above 0 (the items' stream reaches them)",
        all(((r_.get("segw") or {}).get("sd") or 0) > 0 and ((r_.get("winit8") or {}).get("sd") or 0) > 0 for r_ in raw_), raw_[-1:])
    tk_ = [q_.get("tracker") or {} for q_ in Q_]
    chk("the tracker's near rows from update 2 (the 10 s window closes), scored and learnt; a loss and its last layer",
        all((t_.get("rows_near") or 0) > 0 and num_(t_.get("loss")) for t_ in tk_[1:]), [(t_.get("rows_near"), t_.get("rows_ctl"), t_.get("loss")) for t_ in tk_])
    sk_ = ((tk_[-1].get("all") or {}).get("idie5") or {})
    st_ = ((tk_[-1].get("all") or {}).get("stack_health") or {})
    chk("the tracker's readouts: Brier skill and AUC of a near output, the stack's middle and rule errors, coverage", num_(sk_.get("skill")) and
        num_(st_.get("mid_err")) and num_(st_.get("rule_err")) and num_(st_.get("inside")), dict(idie5=sk_, stack=st_))
    if UPD >= 12:                                            # (90 s of frames: the in-control labels come in, the near rows' split resolves)
        tl_ = tk_[-1]
        nin_ = sum(int(((tl_.get("in") or {}).get(o_) or {}).get("n") or 0) for o_ in ("idie5", "ctl_two"))
        nout_ = sum(int(((tl_.get("out") or {}).get(o_) or {}).get("n") or 0) for o_ in ("idie5", "ctl_two"))
        chk("after 90 s of frames: the in-control rows (the control ring's brain state, the tracker's columns) scored and learnt; near rows' split "
            "by the truth of in control resolved (in {}, out {})".format(nin_, nout_), (tl_.get("rows_ctl") or 0) > 0 and (tl_.get("split_resolved") or 0) > 0
            and nin_ > 0 and nout_ > 0 and num_(((tl_.get("all") or {}).get("ctl_two") or {}).get("skill")),
            [(t_.get("rows_ctl"), t_.get("split_resolved"), t_.get("pending")) for t_ in tk_])
    vw_ = [q_.get("vw") or {} for q_ in Q_]
    chk("the second value learns every update", all(num_(v_.get("loss_before")) and num_(v_.get("loss_after")) for v_ in vw_), vw_[-1:])
    at_ = [q_.get("attack") or {} for q_ in Q_]
    chk("the attack readouts every update (seat-time on the enemy by stack edge, both outlooks' centred value, the tracker's fight odds)",
        all(a_.get("readings") and sum(a_["readings"]) > 0 and a_.get("outlook_built") and a_.get("outlook_desc") for a_ in at_), at_[-1:])
    ms_ = [m_.get("map_sense") or {} for m_ in M]
    chk("the map sense's lesson every update (samples, R2)", all((x_.get("frames") or 0) > 0 for x_ in ms_), [(x_.get("frames"), x_.get("r2")) for x_ in ms_])
    if OUT_G > 0 and NONZERO:
        chk("the term played: its size above 0 on his frames; the share of his readings it changed recorded",
            all(float(o_.get("size") or 0) > 0 and num_(o_.get("changed")) for o_ in O_), [(o_.get("size"), o_.get("max"), o_.get("changed")) for o_ in O_])
    if TRIAL > 0:
        chk("trial trips: begun, counted, none of their frames left in a target lesson",
            sum(int(o_.get("trial_trips") or 0) for o_ in O_) > 0 and all(int(o_.get("trial_in_lesson", -1)) == 0 for o_ in O_),
            [(o_.get("trial_trips"), o_.get("trial_readings"), o_.get("trial_in_lesson"), o_.get("rows_trial")) for o_ in O_])
    pu = [(m_.get("pull") or {}) for m_ in M]
    fe_ = [p_.get("first_err") for p_ in pu]
    chk("the pull's proof with the outlook's term ({}) at {}: at most 1e-3 every update".format("desc" if SRC else "built", OUT_G),
        M and all(x_ is not None and float(x_) <= 1e-3 for x_ in fe_), fe_)
    if LEAGUE:
        lg_ = [(o_.get("g_opp"), q_.get("src_opp"), o_.get("opp_has")) for o_, q_ in zip(O_, Q_)]
        chk("the league's own desc term played in some update (snap_0000: g 0.5, src 1)", any(x_[2] and x_[0] == 0.5 and x_[1] == 1 for x_ in lg_), lg_)
    no_major = [x for x in log.splitlines() if "MAJOR PROBLEM" in x]
    chk("no MAJOR PROBLEM line in the trainer's log", not no_major, no_major[:2])
    try:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        chk("the save: 2.2a's parts in model, out_src {}, out22 (the Adams, the facts' statistics), out_opt, out_stats, map_sense".format(SRC),
            "head2.trk.l3.weight" in ck_["model"] and "head2.dsc.desc.l3.weight" in ck_["model"] and int(round(float(ck_["model"]["head2.out_src"]))) == SRC
            and bool(ck_.get("out22")) and bool(ck_.get("out_opt")) and bool(ck_.get("out_stats")) and bool(ck_.get("map_sense")),
            sorted(k_ for k_ in ck_ if k_ in ("out22", "out_opt", "out_stats", "map_sense", "plan_opt")))
    except Exception as e_:                                  # noqa: BLE001
        chk("the save read", False, repr(e_))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    tr2, t2 = run_cmd(D, "small_resume.cmd", small_cmd(D, 1))
    log2 = open(logp, encoding="utf-8", errors="replace").read()[len(log):] if os.path.exists(logp) else ""
    M2 = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    l22b = [x for x in log2.splitlines() if "2.2a (--out22)" in x]
    chk("the resume: exit 0, one more update", log2.strip() and "exit 0" in log2.splitlines()[-1] and len(M2) == UPD + 1, (len(M2), log2.rstrip().splitlines()[-1:] if log2.strip() else ""))
    chk("the resume reads the Adams of 2.2a's parts from the checkpoint", bool(l22b) and "Adams from the checkpoint" in l22b[0], l22b[:1])
    q4_ = (M2[-1].get("out22") or {}) if len(M2) == UPD + 1 else {}
    p4_ = (M2[-1].get("pull") or {}) if len(M2) == UPD + 1 else {}
    chk("the resume's records and the pull's proof (the tracker's rings and history start cold at a process start, as the control's: no near row "
        "in the resume's first update)", q4_ and q4_.get("tracker") is not None and not q4_.get("off") and p4_.get("first_err") is not None
        and float(p4_["first_err"]) <= 1e-3, ((q4_.get("tracker") or {}).get("rows_near"), q4_.get("off"), p4_.get("first_err")))
    bad2 = [x for x in log2.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("the resume: no NaN, traceback or MAJOR PROBLEM", not bad2, bad2[:3])
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_22a.py"), RUN, "--dir", D, "--once"], cwd=CODE, capture_output=True, text=True,
                         creationflags=NOWIN)
    wl_ = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(
        os.path.join(D, "watch", "watch.log")) else []
    chk("the ramp's pass over the metrics: exit 0, the outlook, desc, facts, tracker, map sense, attack lines every update, no crash",
        rp_.returncode == 0 and sum(1 for x in wl_ if ": outlooks seg gain" in x) == len(M2) and sum(1 for x in wl_ if ": tracker (all moments)" in x) == len(M2)
        and sum(1 for x in wl_ if ": attack by the stack edge" in x) == len(M2) and not any("CRASHED" in x for x in wl_), (rp_.returncode, rp_.stderr[-800:]))
    mj_ = [x for x in wl_ if "MAJOR PROBLEM" in x]
    chk("the ramp's pass: no MAJOR PROBLEM", not mj_, mj_[:3])
    for x in wl_:
        print("    ramp: " + x[:400], flush=True)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

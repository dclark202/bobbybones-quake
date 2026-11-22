"""2.1e's smoke (the head's slow halves; docs/runs/2.1/2.1e): the trainer of THIS checkout (its sim/: the worktree's code) runs 2.1e's command
made small (2 simulators x 8 matches x 96 frames, CPU, below normal, pinned to the efficiency cores 0x3C3C, 3 updates; the clocks SMOKE_CLOCKS,
default 2,3,4 head ticks, so that every half ticks on its clock within 96 frames) on a 2.1d save given the slow halves (tools/slow_init.py add)
with its optimizer, two anchors widened the same way (slow_init widen-league), and start_live.py's live.json (from 2.1d's live.json as it is,
--any) with PULL_G 1.0, HELD_G 0.5, SLOW_MIX 0.5, SLOW_BACK 0.5, SLOW_PICK 1 (SMOKE_PULL_G, SMOKE_HELD_G, SMOKE_MIX, SMOKE_BACK, SMOKE_PICK). With
SMOKE_NONZERO=1 (the default) the start file's three halves' last layers and the read-back's columns are made non-zero first (a fixed-seed
random: the slow odds not even, the read-back acting from the first frame), so that the pull's mix and the read-back play something from
update 1 and the pull's proof covers them. With SMOKE_LEAGUE=1 (the default) the start file at mix 0.5, back 0.5, pick 2 is put in the
league as the run's own snapshot (snapshots/snap_0000.pt), so that the league's seats play halves of their own. Then the save is resumed for one more update (the same folder, the same command). The data (maps, the
judge, the legs, 2.1d's files) come from QLBOT_ROOT (the main checkout); the scratch run folder is QLBOT_ROOT/data/sim_runs/scratch_21e_smoke
<TEST_TAG>; nothing deleted, nothing else written. Then ramp_21e.py --once over its metrics (the flags on real lines).
PASS: exit 0 both times; three lines then four in metrics.jsonl; live.json applied; the optimizer loaded, not cold, head2.inp's moments carried
over; the trainer's slow line (its Adam new, then from the checkpoint at the resume); rec "slow" every update with the mix, back and pick played as
set, all three halves with ticks of all three causes (over the run), their readouts (rows, kl and top-1 of the first horizon finite) and a loss;
rec "pull" with its proof first_err measured and at most 1e-3 (the CPU floor is about 1e-5); the save carries head2.slow.*, slow_opt and the
dials; no NaN, traceback or MAJOR PROBLEM; the ramp's pass ends cleanly with a slow line an update.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1e/smoke.py <a 2.1d save> <its opt.pt> <anchor a.pt> <anchor b.pt>
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
RUN = "scratch_21e_smoke" + os.environ.get("TEST_TAG", "")
PULL_G = float(os.environ.get("SMOKE_PULL_G", "1.0"))
HELD_G = float(os.environ.get("SMOKE_HELD_G", "0.5"))
MIX = float(os.environ.get("SMOKE_MIX", "0.5"))
BACK = float(os.environ.get("SMOKE_BACK", "0.5"))
PICK = int(os.environ.get("SMOKE_PICK", "1"))
CLOCKS = os.environ.get("SMOKE_CLOCKS", "2,3,4")
NONZERO = os.environ.get("SMOKE_NONZERO", "1") == "1"
LEAGUE = os.environ.get("SMOKE_LEAGUE", "1") == "1"


def small_cmd(D, updates):
    """2.1e's train.cmd made small: this checkout's trainer, the data's root, CPU, below normal on the efficiency cores"""
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
    assert len(cl_) == 1 and len(re.findall(r"--max-updates \d+ ", L_[cl_[0]])) == 1 and len(re.findall(r"--slow-clocks \S+ ", L_[cl_[0]])) == 1
    L_[cl_[0]] = re.sub(r"--max-updates \d+ ", "--max-updates {} ".format(updates), L_[cl_[0]])
    L_[cl_[0]] = re.sub(r"--slow-clocks \S+ ", "--slow-clocks {} ".format(CLOCKS), L_[cl_[0]])
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
    while tr.poll() is None and time.time() - t0 < 90 * 60:
        time.sleep(10)
    return tr, t0


def nonzero(path):
    """the start file's three halves' last layers and the read-back's columns made non-zero (a fixed-seed random; the test only)"""
    import torch
    sys.path.insert(0, os.path.join(CODE, "sim"))
    import head2 as H2
    ck = torch.load(path, weights_only=False, map_location="cpu")
    g = torch.Generator().manual_seed(2125)
    sd = ck["model"]
    for k_ in range(len(ck["head2"]["slowhalf"]["clocks"])):
        w_ = sd["head2.slow.{}.l3.weight".format(k_)]
        sd["head2.slow.{}.l3.weight".format(k_)] = torch.randn(w_.shape, generator=g) * (2.0 / float(w_.shape[1]) ** 0.5)
    o_ = H2._offs(ck["head2"])["slowback"]
    wi_ = sd["head2.inp.weight"].clone()
    wi_[:, o_[0]:o_[1]] = torch.randn(wi_.shape[0], o_[1] - o_[0], generator=g) * 0.05
    sd["head2.inp.weight"] = wi_
    torch.save(ck, path)
    print("SMOKE_NONZERO: the halves' last layers and the read-back's {} columns made non-zero (seed 2125)".format(o_[1] - o_[0]), flush=True)


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
    si_ = [sys.executable, os.path.join(CODE, "tools", "slow_init.py")]
    add_ = subprocess.run(si_ + ["add", s1, os.path.join(D, "policy.pt")], env=cpu, creationflags=NOWIN, capture_output=True, text=True)
    print(add_.stdout.strip(), add_.stderr.strip()[-2000:], flush=True)
    assert add_.returncode == 0, "slow_init add failed"
    if NONZERO:
        nonzero(os.path.join(D, "policy.pt"))
    if LEAGUE:                                               # (a league file with halves of its own that play: the start file at mix 0.5, back 0.5,
        import torch                                         # the half 2, as the run's own first snapshot: the league's path is exercised)
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        ck_["model"]["head2.slow_mix"], ck_["model"]["head2.slow_back"], ck_["model"]["head2.slow_pick"] = (
            torch.tensor(0.5), torch.tensor(0.5), torch.tensor(2.0))
        torch.save(ck_, os.path.join(D, "snapshots", "snap_0000.pt"))
        print("SMOKE_LEAGUE: snapshots/snap_0000.pt = the start file at mix 0.5, back 0.5, pick 2 (the league's own halves play)", flush=True)
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in (a1, a2):
        w_ = subprocess.run(si_ + ["widen-league", a_, os.path.join(D, "snapshots", os.path.basename(a_)), "--like", os.path.join(D, "policy.pt")],
                            env=cpu, creationflags=NOWIN, capture_output=True, text=True)
        print(w_.stdout.strip(), w_.stderr.strip()[-2000:], flush=True)
        assert w_.returncode == 0, "slow_init widen-league failed"
    shutil.copy2(os.path.join(R1D, "live_settings.env"), os.path.join(D, "live_settings.env"))
    shutil.copy2(os.path.join(R1D, "live.json"), os.path.join(D, "live_21d.json"))      # (a copy out of the running run: read, never written)
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(D, "live_21d.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(PULL_G=PULL_G, HELD_G=HELD_G, SLOW_MIX=MIX, SLOW_BACK=BACK, SLOW_PICK=PICK)
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
        print(("PASS  " if good else "FAIL  ") + name + (" | " + str(more)[:1800] if more != "" else ""), flush=True)

    num_ = lambda v_: isinstance(v_, (int, float)) and math.isfinite(float(v_))    # noqa: E731
    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-1][-300:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold; head2.inp's moments carried over (the read-back's columns)", bool(opt_) and not any(
        "cold" in x.lower() or "does not fit" in x.lower() for x in opt_) and any("head2.inp.weight carried over" in x for x in opt_), opt_[:4])
    sl_l = [x for x in log.splitlines() if "slow halves INSIDE the head" in x]
    chk("the trainer's slow line: inside the head, its Adam new at the first start", bool(sl_l) and "(new)" in sl_l[0], sl_l[:1])
    S_ = [(m_.get("slow") or {}) for m_ in M]
    print("slow records: " + json.dumps(S_)[:6000], flush=True)
    chk("rec slow every update, played as set (mix {}, back {}, pick {})".format(MIX, BACK, PICK), M and all(
        s_ and abs(float(s_.get("mix", -1)) - MIX) < 1e-6 and abs(float(s_.get("back", -1)) - BACK) < 1e-6 and int(s_.get("pick", -1)) == PICK
        and not s_.get("off") for s_ in S_), [(s_.get("mix"), s_.get("back"), s_.get("pick"), s_.get("off")) for s_ in S_])
    tick_ = [[sum(float(((s_.get("halves") or [{}] * 3)[k_].get("ticks_min") or {}).get(c_) or 0) for s_ in S_) for c_ in ("clock", "trip_end", "change")]
             for k_ in range(3)]
    chk("all three halves tick on all three causes over the run (clock, trip end, change of mind; a seat-minute summed)",
        len(S_) and all(all(v_ > 0 for v_ in r_) for r_ in tick_), tick_)
    rd_ = []
    for s_ in S_:
        for h_ in (s_.get("halves") or []):
            hk_ = sorted(k2_ for k2_ in h_ if k2_.startswith("h") and k2_[1:].isdigit())
            rd_.append((hk_, (h_.get(hk_[0]) or {}).get("n") if hk_ else None, (h_.get(hk_[0]) or {}).get("kl_slow") if hk_ else None,
                        (h_.get(hk_[0]) or {}).get("kl_fast") if hk_ else None, h_.get("loss"), h_.get("rows"), h_.get("tv"), h_.get("l3")))
    chk("every half's readouts every update: its first horizon with rows (n > 0), kl slow and fast finite, a loss, the odds' moves, its last layer",
        len(rd_) == 3 * len(M) and all(r_[0] and (r_[1] or 0) > 0 and num_(r_[2]) and num_(r_[3]) and num_(r_[4]) and num_(r_[6]) and num_(r_[7])
                                       for r_ in rd_), rd_)
    chk("the fast plan's moves and the replayed pull with each half's odds", all(num_((s_.get("fast") or {}).get("tv")) and all(
        sorted((h_.get("pull_changes_min") or {}).keys()) == ["0.0", "0.5", "1.0", "2.0"] for h_ in (s_.get("halves") or [])) for s_ in S_),
        [((s_.get("fast") or {}).get("tv"), [(h_.get("pull_changes_min") or {}).get("1.0") for h_ in (s_.get("halves") or [])]) for s_ in S_])
    chk("the read-back's weight size recorded (non-zero: SMOKE_NONZERO, or after PPO moved it)", all(num_(s_.get("readback_w")) for s_ in S_)
        and (not NONZERO or all(float(s_.get("readback_w") or 0) > 0 for s_ in S_)), [s_.get("readback_w") for s_ in S_])
    pu = [(m_.get("pull") or {}) for m_ in M]
    fe_ = [p_.get("first_err") for p_ in pu]
    chk("the pull's proof with the mix {} and the read-back {}: measured every update, at most 1e-3 (pull_first_err)".format(MIX, BACK),
        M and all(x_ is not None and float(x_) <= 1e-3 for x_ in fe_), fe_)
    chk("rec pull at strength {} with size above 0".format(PULL_G), M and all(abs(float(p_.get("g", -1)) - PULL_G) < 1e-6 and float(p_.get("size") or 0) > 0
                                                                            for p_ in pu), [(p_.get("g"), p_.get("size")) for p_ in pu])
    pn = (M[-1].get("plan") or {}) if M else {}
    chk("rec plan as 2.1d's (the fast plan's lesson goes on)", int((pn.get("h2s") or {}).get("n", 0)) > 0 and num_(pn.get("loss")),
        {k_: pn.get(k_) for k_ in ("h2s", "loss", "rows")})
    no_major = [x for x in log.splitlines() if "MAJOR PROBLEM" in x]
    chk("no MAJOR PROBLEM line in the trainer's log (the plan's and the halves' guards)", not no_major, no_major[:2])
    try:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        chk("the save: head2.slow.* in model, the dials ({}, {}, {}), slow_opt beside it, the layout's clocks {}".format(MIX, BACK, PICK, CLOCKS),
            all("head2.slow.{}.l3.weight".format(k_) in ck_["model"] for k_ in range(3)) and abs(float(ck_["model"]["head2.slow_mix"]) - MIX) < 1e-6
            and abs(float(ck_["model"]["head2.slow_back"]) - BACK) < 1e-6 and int(round(float(ck_["model"]["head2.slow_pick"]))) == PICK
            and bool(ck_.get("slow_opt")) and bool(ck_.get("plan_opt")) and ck_["head2"]["slowhalf"]["clocks"] == [int(c_) for c_ in CLOCKS.split(",")],
            dict(slow_opt=bool(ck_.get("slow_opt")), mix=float(ck_["model"].get("head2.slow_mix", -1)), back=float(ck_["model"].get("head2.slow_back", -1)),
                 pick=float(ck_["model"].get("head2.slow_pick", -1)), slowhalf=(ck_.get("head2") or {}).get("slowhalf")))
        sn_ = [f_ for f_ in os.listdir(os.path.join(D, "snapshots")) if f_.startswith("snap_")]
        lg_ = [(s_.get("mix_opp"), s_.get("back_opp"), s_.get("pick_opp"), s_.get("opp_has")) for s_ in S_]
        print("INFO  snapshots of this run: {}; the league's (mix, back, pick, has halves) by update {}".format(sn_, lg_), flush=True)
        if LEAGUE:
            chk("the league's own halves played in some update (snap_0000: mix 0.5, back 0.5, pick 2; an anchor: none)",
                any(x_[3] and x_[0] == 0.5 and x_[1] == 0.5 and x_[2] == 2 for x_ in lg_), lg_)
    except Exception as e_:                                  # noqa: BLE001
        chk("the save read", False, repr(e_))
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    # the resume: one more update from the save just written (the halves, their Adam, the main optimizer)
    tr2, t2 = run_cmd(D, "small_resume.cmd", small_cmd(D, 1))
    log2 = open(logp, encoding="utf-8", errors="replace").read()[len(log):] if os.path.exists(logp) else ""
    M2 = [json.loads(x) for x in open(mp, encoding="utf-8") if x.strip()] if os.path.exists(mp) else []
    sl2 = [x for x in log2.splitlines() if "slow halves INSIDE the head" in x]
    chk("the resume: exit 0, a fourth update", log2.strip() and "exit 0" in log2.splitlines()[-1] and len(M2) == 4, (len(M2), log2.rstrip().splitlines()[-1:] if log2.strip() else ""))
    chk("the resume reads the halves' Adam from the checkpoint", bool(sl2) and "from the checkpoint" in sl2[0], sl2[:1])
    o2_ = [x for x in log2.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the resume's optimizer loaded, not cold", bool(o2_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in o2_), o2_[:2])
    s4_ = (M2[-1].get("slow") or {}) if len(M2) == 4 else {}
    p4_ = (M2[-1].get("pull") or {}) if len(M2) == 4 else {}
    chk("the resume's slow record and the pull's proof", s4_ and len(s4_.get("halves") or []) == 3 and p4_.get("first_err") is not None
        and float(p4_["first_err"]) <= 1e-3, (s4_.get("mix"), s4_.get("back"), s4_.get("pick"), p4_.get("first_err")))
    bad2 = [x for x in log2.splitlines() if "nan" in x.lower().split() or "Traceback" in x or "MAJOR PROBLEM" in x]
    chk("the resume: no NaN, traceback or MAJOR PROBLEM", not bad2, bad2[:3])
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_21e.py"), RUN, "--dir", D, "--once"], cwd=CODE, capture_output=True, text=True,
                         creationflags=NOWIN)
    wl_ = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(
        os.path.join(D, "watch", "watch.log")) else []
    sll_ = [x for x in wl_ if ": slow halves: played mix" in x]
    shl_ = [x for x in wl_ if ": slow half " in x]
    fll_ = [x for x in wl_ if ": flicker: " in x]
    chk("the ramp's pass over the metrics: exit 0, a slow line, three half lines and a flicker line an update, no crash",
        rp_.returncode == 0 and len(sll_) == len(M2) and len(shl_) == 3 * len(M2) and len(fll_) == len(M2) and not any("CRASHED" in x for x in wl_),
        (rp_.returncode, rp_.stderr[-800:], len(sll_), len(shl_), len(fll_)))
    mj_ = [x for x in wl_ if "MAJOR PROBLEM" in x]
    chk("the ramp's pass: no MAJOR PROBLEM (the dials played as the file has them)", not mj_, mj_[:3])
    for x in wl_:
        print("    ramp: " + x, flush=True)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

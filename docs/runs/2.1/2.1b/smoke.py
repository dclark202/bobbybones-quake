"""2.1b's one check before the start (docs/runs/2.1/2.1b/CARD.md): the trainer of THIS checkout (its sim/, the b21b code) runs 2.1b's command
made small (2 simulators x 8 matches x 96 frames, CPU, below normal, 3 updates) on a 2.0e save given the keep choice and its quiet layer at zero
(tools/keep_init.py add --start zero --quiet 1, checked by keep_init same: "share 0: PASS"), with its optimizer, two of 2.0e's anchors, the map
sense's start, and start_live.py's live.json (from 2.0e's live.json as it is, --any) with BRANCH_P 0.5; the forks' windows made short
(--branch-win 64, --branch-long-secs 4) so forks complete within the smoke. The data (maps, the judge, the legs, 2.0e's files) come from
QLBOT_ROOT (the main checkout); the scratch run folder is QLBOT_ROOT/data/sim_runs/scratch_21b_smoke<TEST_TAG>; nothing deleted, nothing
else written. Then ramp_21b.py --once over its metrics (the flags on real lines).
PASS: the trainer ends with exit 0; three lines in metrics.jsonl; live.json applied; the optimizer loaded, not cold, and its saved groups
include "keep" and "keepq"; rec.stay.labels > 0 in some update; rec.keep.zone and rec.keep.teach present; rec.map_sense present;
stay_forks.jsonl has lines; a save written after the start with a top-level "stay" entry; no NaN or traceback; the ramp's pass ends cleanly
with a summary line an update.
    set QLBOT_ROOT=C:\\Users\\<user>\\Documents\\gh\\BobbyBones
    <anaconda python> docs/runs/2.1/2.1b/smoke.py <a 2.0e policy.pt> <its opt.pt>
(train.cmd must exist: make_files.py first.)"""
import json
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
RUN = "scratch_21b_smoke" + os.environ.get("TEST_TAG", "")


def main():
    if not DATA or not os.path.isdir(os.path.join(DATA, "data")):
        raise SystemExit("set QLBOT_ROOT to the checkout that holds data\\ (the main checkout): not started")
    D = os.path.join(DATA, "data", "sim_runs", RUN)
    R0 = os.path.join(DATA, "data", "sim_runs", "duel_gru_2_0e")
    s1, s1o = sys.argv[1:3]
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (set TEST_TAG; nothing deleted)")
    for p_ in (s1, s1o, os.path.join(HERE, "train.cmd"), os.path.join(R0, "live.json"), os.path.join(R0, "live_settings.env"),
               os.path.join(R0, "snapshots", "anchor_16a.pt"), os.path.join(R0, "snapshots", "anchor_b12d.pt"),
               os.path.join(DATA, "data", "sim_runs", "space", "mapsense_start.pt")):
        if not os.path.exists(p_):
            raise SystemExit("MISSING " + p_ + ": not started")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    cpu = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1")
    subprocess.check_call([sys.executable, os.path.join(CODE, "tools", "keep_init.py"), "add", s1, os.path.join(D, "policy.pt"), "--start", "zero",
                           "--quiet", "1", "--opt", s1o, os.path.join(D, "opt.pt")], env=cpu, creationflags=NOWIN)
    same_ = subprocess.run([sys.executable, os.path.join(CODE, "tools", "keep_init.py"), "same", s1, os.path.join(D, "policy.pt")], env=cpu,
                           creationflags=NOWIN, capture_output=True, text=True).stdout
    shutil.copy2(os.path.join(R0, "snapshots", "anchor_16a.pt"), os.path.join(D, "snapshots", "anchor_16a.pt"))
    shutil.copy2(os.path.join(R0, "snapshots", "anchor_b12d.pt"), os.path.join(D, "snapshots", "anchor_b12d.pt"))
    shutil.copy2(os.path.join(DATA, "data", "sim_runs", "space", "mapsense_start.pt"), os.path.join(D, "keep", "mapsense_start.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    subprocess.check_call([sys.executable, os.path.join(HERE, "start_live.py"), os.path.join(R0, "live.json"), os.path.join(D, "live.json"), "--any"],
                          creationflags=NOWIN)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(BRANCH_P=0.5)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(DATA, DATA)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /low /affinity 3C000 "),
                 ("python.exe sim" + BS + "train_duel_rnn.py ", "python.exe " + os.path.join(CODE, "sim", "train_duel_rnn.py") + " "),
                 ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 256 "),
                 ("--minibatches 360 ", "--minibatches 4 "), ("--branch-win 320 ", "--branch-win 64 "), ("--branch-long-secs 30 ", "--branch-long-secs 4 "),
                 ("duel_gru_2_1b" + BS + "keep" + BS + "mapsense_start.pt", RUN + BS + "keep" + BS + "mapsense_start.pt"),
                 ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 >> ")):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    L_ = t.split("\n")                                       # (the command line only: the rem lines name the history's lengths)
    cl_ = [i for i, x in enumerate(L_) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1 and len(re.findall(r"--max-updates \d+ ", L_[cl_[0]])) == 1
    L_[cl_[0]] = re.sub(r"--max-updates \d+ ", "--max-updates 3 ", L_[cl_[0]])
    t = "\n".join(L_)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + RUN + ".log", t)
    assert not any("duel_gru_2_" in x for x in t.split("\n") if not x.startswith("rem"))
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=DATA, env=dict(os.environ, QLBOT_ROOT=DATA, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=NOWIN)
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
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

    chk("keep_init same: share 0 to the bit", any(x.startswith("share 0: PASS") for x in same_.splitlines()),
        [x for x in same_.splitlines() if x.startswith("share 0") or x.startswith("same:")])
    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-1][-300:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold", bool(opt_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in opt_), opt_[:3])
    import torch
    names_ = []
    try:
        names_ = list(torch.load(os.path.join(D, "opt.pt"), map_location="cpu", weights_only=False).get("names") or [])
    except Exception as e_:                                  # noqa: BLE001
        names_ = ["(not read: {})".format(e_)]
    chk("the saved optimizer's groups include keep and keepq", "keep" in names_ and "keepq" in names_, names_)
    kl_ = [x for x in log.splitlines() if "keep choice" in x or "stay value" in x]
    chk("the trainer's keep choice lines (share 0, the quiet layer)", any("share 0.0000" in x for x in kl_) and any("KEEP_ZONE" in x for x in kl_), kl_[:4])
    labs_ = [((m_.get("stay") or {}).get("labels")) for m_ in M]
    chk("the stay value got labels in some update (rec.stay.labels > 0)", any((x_ or 0) > 0 for x_ in labs_), {
        "labels": labs_, "held_out": [(m_.get("stay") or {}).get("held_out") for m_ in M]})
    chk("rec.keep.zone recorded", any((m_.get("keep") or {}).get("zone") for m_ in M), [(m_.get("keep") or {}).get("zone") for m_ in M][-1:] if M else "")
    chk("rec.keep.teach recorded", any((m_.get("keep") or {}).get("teach") for m_ in M), [(m_.get("keep") or {}).get("teach") for m_ in M][-1:] if M else "")
    chk("rec.keep shares: KEEP_G 0, KEEPQ_G 0", M and all(float((m_.get("keep") or {}).get("g") or 0) == 0 and
                                                       float(((m_.get("keep") or {}).get("quiet") or {}).get("g") or 0) == 0 for m_ in M),
        [((m_.get("keep") or {}).get("g"), ((m_.get("keep") or {}).get("quiet") or {}).get("g")) for m_ in M])
    chk("rec.map_sense recorded", any(m_.get("map_sense") for m_ in M), [m_.get("map_sense") for m_ in M][-1:] if M else "")
    chk("rec.branch recorded (the keep forks)", any(m_.get("branch") for m_ in M), [(m_.get("branch") or {}).get("keep") for m_ in M])
    sf_ = os.path.join(D, "stay_forks.jsonl")
    nsf_ = sum(1 for x in open(sf_, encoding="utf-8") if x.strip()) if os.path.exists(sf_) else 0
    chk("stay_forks.jsonl has lines", nsf_ > 0, nsf_)
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    top_ = []
    try:
        top_ = list(torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).keys())
    except Exception as e_:                                  # noqa: BLE001
        top_ = ["(not read: {})".format(e_)]
    chk("the save has a top-level 'stay' entry", "stay" in top_, top_)
    rp_ = subprocess.run([sys.executable, os.path.join(HERE, "ramp_21b.py"), RUN, "--dir", D, "--once"], cwd=CODE, capture_output=True, text=True,
                         creationflags=NOWIN)
    wl_ = open(os.path.join(D, "watch", "watch.log"), encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(
        os.path.join(D, "watch", "watch.log")) else []
    summ_ = [x for x in wl_ if " shares KEEP_G " in x]
    chk("the ramp's pass over the metrics: exit 0, a summary line an update, no crash", rp_.returncode == 0 and len(summ_) == len(M) and
        not any("CRASHED" in x for x in wl_), (rp_.returncode, rp_.stderr[-800:], len(summ_)))
    for x in wl_:
        print("    ramp: " + x, flush=True)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

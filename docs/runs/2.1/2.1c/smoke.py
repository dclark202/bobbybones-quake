"""2.1c's smoke (docs/runs/2.1/2.1c/CARD.md; made from 2.0e's smoke.py): the trainer runs on 1.6a's end brought to list 20e. 2.0e's command made
small (2 simulators x 8 matches x 96 frames, CPU, below normal, 3 updates), from a converted start with its optimizer and two converted
anchors, start_live.py's live.json with the dials at mid values (AIM3 half in, the pay half moved, DODGE_G 0.5). PASS: the trainer ends
with exit 0, three lines in metrics.jsonl, live.json applied, the dodge token's gate log(0.5), the optimizer loaded (not cold), a save
written. A scratch run folder only (data/sim_runs/scratch_20e_smoke<TAG>); nothing deleted.
    python docs/runs/2.0/2.0e/smoke.py <the converted start.pt> <its opt.pt> <anchor a.pt> <anchor b.pt>"""
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
RUN = "scratch_21c_smoke" + os.environ.get("TEST_TAG", "")
D = os.path.join(ROOT, "data", "sim_runs", RUN)
R6A = os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_0e")


def main():
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
    lv.update(HELD_G=float(os.environ.get("SMOKE_HELD_G", "0.5")))
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
                 ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
                 ("--max-updates 100 ", "--max-updates 3 "), ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 --plan-horizons 3,6 --plan-every 2 >> ")):
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
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
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

    chk("the trainer ended by itself in {:.1f} min".format((time.time() - t0) / 60), tr.poll() is not None)
    chk("exit 0", "exit 0" in log.splitlines()[-1] if log.strip() else False, log.rstrip().splitlines()[-3:] if log.strip() else "(no log)")
    chk("three updates in metrics.jsonl", len(M) == 3, len(M))
    chk("live.json applied", st.get("status") == "applied", st)
    opt_ = [x for x in log.splitlines() if x.startswith("optimizer: ") or " optimizer: " in x]
    chk("the optimizer's state loaded, not cold", bool(opt_) and not any("cold" in x.lower() or "does not fit" in x.lower() for x in opt_), opt_[:3])
    hd = (M[-1].get("held") or {}) if M else {}
    chk("the held draw: share 0.5 played, about half his seat-frames on it, five readings a second there", hd and abs(float(hd.get("g", 0)) - float(os.environ.get("SMOKE_HELD_G", "0.5"))) < 1e-6
        and (float(os.environ.get("SMOKE_HELD_G", "0.5")) == 0.0 and float(hd.get("share", 1)) == 0.0
             or 0.25 < float(hd.get("share", 0)) < 0.75 and 3.0 < float(hd.get("readings_s", 0)) <= 5.01), hd)
    h2 = [x for x in log.splitlines() if "strategy head" in x and "goal" in x]
    chk("the head reads the part goal (19 numbers)", bool(h2), h2[:1] or [x for x in log.splitlines() if "strategy head" in x][:1])
    it = (M[-1].get("intent") or {}) if M else {}
    chk("the lock's measures are recorded (trips, reached)", it.get("trips_per_player_min") is not None and it.get("reached") is not None, it)
    chk("no keep choice, no order in the metrics", M and not (M[-1].get("keep") or {}).get("g") and not (M[-1].get("cmb") or {}).get("g"),
        {k_: M[-1].get(k_) for k_ in ("keep", "cmb")} if M else "")
    pn = (M[-1].get("plan") or {}) if M else {}                      # (--plan) the slow plan in shadow (the smoke's horizons 3 and 6 ticks)
    num_ = lambda d_: all(isinstance(v_, (int, float)) and math.isfinite(float(v_)) for v_ in d_.values() if not isinstance(v_, (dict, list)))
    chk("the slow plan's record: both horizons with rows, finite numbers", all(int((pn.get(k_) or {}).get("n", 0)) > 0 and num_(pn.get(k_) or {})
                                                                            for k_ in ("h2s", "h5s")), {k_: pn.get(k_) for k_ in ("h2s", "h5s")})
    chk("the slow plan's pull readout at the four strengths, its changes' kinds", sorted((pn.get("pull_changes_min") or {}).keys()) == ["0.0", "0.5", "1.0", "2.0"]
        and isinstance(pn.get("changes"), dict) and pn["changes"].get("n") is not None, {k_: pn.get(k_) for k_ in ("pull_changes_min", "changes", "loss")})
    pl_l = [x for x in log.splitlines() if "slow plan" in x]
    chk("the slow plan's start line", bool(pl_l), pl_l[:1])
    try:
        import torch
        ck_ = torch.load(os.path.join(D, "policy.pt"), weights_only=False, map_location="cpu")
        pe_ = ck_.get("plan") or {}
        chk("the save has the top-level entry plan with model and opt", bool(pe_.get("model")) and bool(pe_.get("opt")) and not any(k_.startswith("plan") for k_ in ck_["model"]),
            sorted(pe_.keys()))
    except Exception as e_:
        chk("the save has the top-level entry plan with model and opt", False, repr(e_))
    print("plan record of the last update: " + json.dumps(pn), flush=True)
    bad = [x for x in log.splitlines() if "nan" in x.lower().split() or "Traceback" in x]
    chk("no NaN, no traceback in the log", not bad, bad[:3])
    chk("a save was written after the start", os.path.getmtime(os.path.join(D, "policy.pt")) > t0)
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

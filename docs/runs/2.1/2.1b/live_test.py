"""2.1b's `live` test (CLAUDE.md: every new live name gets its range and a test on the real trainer): the trainer, small, on the CPU (idle,
cores 14-17), 5 updates from a start made by tools/keep_init.py add --start zero --quiet 1; after update 1 live.json is rewritten with
KEEP_G 0.5, KEEPQ_G 0.5, KEEP_TEACH 2, STAY_W 0.5, BRANCH_ZONE_P 0.3 and the simulator's KEEP_ZONE 1. PASS: nothing refused, applied by
update 4, the save's record of the simulators' values and the metrics carry them. Then tools/run/live_accept.py must REFUSE a file with
KEEPQ_G 1.5 and one with KEEP_ZONE 2. A scratch run folder only (data/sim_runs/scratch_21b_live<TAG> under QLBOT_ROOT); nothing deleted.
    python docs/runs/2.1/2.1b/live_test.py <start policy.pt> <its opt.pt> <tag>"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = os.environ.get("QLBOT_ROOT") or WT
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
OK = [True]


def check(name, cond):
    OK[0] = OK[0] and bool(cond)
    print(("PASS  " if cond else "FAIL  ") + name, flush=True)


def main():
    s1, s1o, tag = sys.argv[1:4]
    run = "scratch_21b_live" + tag
    D = os.path.join(MAIN, "data", "sim_runs", run)
    R0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_2_0e")
    assert not os.path.exists(D), D + " is there: another tag (nothing deleted)"
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(s1, os.path.join(D, "policy.pt"))
    shutil.copy2(s1o, os.path.join(D, "opt.pt"))
    for a_ in ("anchor_16a.pt", "anchor_b12d.pt"):
        shutil.copy2(os.path.join(R0, "snapshots", a_), os.path.join(D, "snapshots", a_))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(KEEP_G=0.0, KEEPQ_G=0.0, KEEP_TEACH=1.0, STAY_W=1.0, BRANCH_P=0.5, BRANCH_ZONE_P=0.5)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(WT, "docs", "runs", "2.0", "2.0e", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    BS = "\\"
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1\nset KEEP_ZONE=1\nset KEEP_SIG=1".format(MAIN, MAIN)),
                 ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /low /affinity 3C000 "), ("--workers 30 ", "--workers 2 "),
                 ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
                 ("--max-updates 80 ", "--max-updates 5 "), ("sim\\train_duel_rnn.py ", WT + "\\sim\\train_duel_rnn.py "),
                 ("%LEARN% >> ", "--snapshot-min 1 --overlap 1 --learn-nosync 1 --keep-g 0 --keepq-g 0 --stay 1 --keep-teach 1 --branch 1 --branch-p 0 "
                                 "--branch-keep 1 --branch-keep-long quiet --branch-zone-p 0.5 --branch-long 1 --branch-long-p 0 --branch-long-secs 4 "
                                 "--branch-win 64 --branch-hold 40 --branch-log 1 >> ")):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(run), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + run + ".log", t)
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(WT, "docs", "runs", "2.0", "2.0e", "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    MID = dict(KEEP_G=0.5, KEEPQ_G=0.5, KEEP_TEACH=2.0, STAY_W=0.5, BRANCH_ZONE_P=0.3, KEEP_ZONE="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=MAIN, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), creationflags=NOWIN)
    MET, wrote, t0 = os.path.join(D, "metrics.jsonl"), False, time.time()
    while tr.poll() is None and time.time() - t0 < 60 * 60:
        time.sleep(5)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(MID)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            print("after update 1: live.json {}".format(MID), flush=True)
    check("the trainer ended by itself", tr.poll() is not None)
    log = open(os.path.join(MAIN, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ap = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    M = [json.loads(x) for x in open(MET, encoding="utf-8") if x.strip()] if os.path.exists(MET) else []
    check("exit 0 and no refusal in the log", log.rstrip().splitlines()[-1].startswith("exit 0") and "REFUSED" not in log)
    check("live_status.json applied ({})".format(st.get("status")), st.get("status") == "applied")
    check("5 updates ({})".format(len(M)), len(M) == 5)
    got = {k_: (ap.get("file") or {}).get(k_) for k_ in MID}
    check("live_applied.json carries the new values ({}, from update {})".format(got, ap.get("from_update")),
          all(str(got.get(k_)) == str(v_) for k_, v_ in MID.items()) and (ap.get("from_update") or 99) <= 4)
    k_ = (M[-1].get("keep") or {}) if M else {}
    s_ = (M[-1].get("stay") or {}) if M else {}
    check("the last update played them: keep g {}, quiet g {}, teach w {}, stay w {}, zone_p {}".format(
        k_.get("g"), (k_.get("quiet") or {}).get("g"), (k_.get("teach") or {}).get("w"), s_.get("w"), s_.get("zone_p")),
        k_.get("g") == 0.5 and (k_.get("quiet") or {}).get("g") == 0.5 and (k_.get("teach") or {}).get("w") == 2.0 and s_.get("w") == 0.5 and s_.get("zone_p") == 0.3)
    z_ = k_.get("zone") or {}
    check("the layers decided once open (zone {}, quiet {})".format((z_.get("zone_layer") or {}).get("decided"), (z_.get("quiet_layer") or {}).get("decided")),
          (z_.get("zone_layer") or {}).get("decided", 0) > 0 and (z_.get("quiet_layer") or {}).get("decided", 0) > 0)
    import torch
    sim_ = ((torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("live") or {}).get("sim") or {})
    check("the save's record of the simulators' values: KEEP_ZONE {}".format(sim_.get("KEEP_ZONE")), sim_.get("KEEP_ZONE") in (True, 1, "1", 1.0))
    for bad_, nm_ in (({"KEEPQ_G": 1.5}, "KEEPQ_G 1.5"), ({"KEEP_ZONE": "2"}, "KEEP_ZONE 2")):
        f_ = os.path.join(D, "bad_live.json")
        lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
        lv.update(bad_)
        json.dump(lv, open(f_, "w", encoding="utf-8"))
        r_ = subprocess.run([sys.executable, os.path.join(WT, "tools", "run", "live_accept.py"), f_, "--env", "duel_env_ffa20e"], capture_output=True, text=True,
                            env=dict(os.environ, KEEP_ZONE="1", KEEP_SIG="1", DODGE_IN="1", PYTHONPATH=os.path.join(WT, "sim")), creationflags=NOWIN, cwd=WT)
        check("live_accept refuses {} (exit {}: {})".format(nm_, r_.returncode, (r_.stdout + r_.stderr).strip().splitlines()[-1:] if (r_.stdout + r_.stderr).strip() else ""), r_.returncode != 0)
    print("ALL PASSED" if OK[0] else "FAILED")
    sys.exit(0 if OK[0] else 1)


if __name__ == "__main__":
    main()

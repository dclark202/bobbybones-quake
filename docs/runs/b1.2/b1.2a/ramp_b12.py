"""b1.2a's schedule (owner, 2026-11-01: the lock "should go entirely, but step it in a way that we can trace when something goes wrong"). First the head: tools/run/ramp_head.py (shut 10 updates, the gate +0.1 a step, the head-open save kept
with its optimizer; a check of 40% or less holds a step). Then, if the lock is still at 8 s, the lock: INTENT_HOLD 8 -> 6 -> 4 -> 3 -> 2 -> 1 -> 0 s, one step every second save (~20 updates, ~76 min, room for one check at each value), the save before each
step kept with its optimizer (keep/policy_lock<value it was at>_b12a.pt). At 0 a reading is free at once; he reads once a second (INTENT_EVERY). Checks under 50% are flagged in watch.log; a check of 40% or less against the start holds a step.
    python docs/runs/b1.2/b1.2a/ramp_b12.py <run> [--every-saves N] [--min-s S] [--poll S] [--dir D]"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
VALUES = "6,4,3,2,1,0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--every-saves", type=int, default=2)
    ap.add_argument("--min-s", type=float, default=25 * 60)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--dir", default="")
    ap.add_argument("--settle", type=float, default=20)
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE = os.path.join(D, "watch"), os.path.join(D, "live.json")
    os.makedirs(WD, exist_ok=True)

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        for f in ("ramp.log", "watch.log"):
            with open(os.path.join(WD, f), "a") as fh:
                fh.write(line + "\n")

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start", "checks_ref.jsonl": "v0.6.0's end"}
        while True:
            for f_, n_ in seen.items():
                try:
                    R = [json.loads(x) for x in open(os.path.join(WD, f_)) if x.strip()]
                except FileNotFoundError:
                    continue
                for d in R[n_:]:
                    wr_ = d["won"] / max(1, d["won"] + d["lost"])
                    if wr_ < 0.5:
                        log("FLAG check update {} against {}: {}-{} = {:.1%}".format(d["update"], names[f_], d["won"], d["lost"], wr_))
                seen[f_] = len(R)
            time.sleep(a.poll)

    threading.Thread(target=flags, daemon=True).start()
    env = dict(os.environ, RAMP_HEAD_ONLY="1", RAMP_OPEN_NAME="policy_head_open_b12a.pt", RAMP_HOLD_AT="0.40", RAMP_FLAG="0")
    if a.dir:
        env["RAMP_DIR"] = a.dir
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "ramp_head.py"), a.run], cwd=ROOT, env=env)
    if r.returncode:
        log("RAMP FAILED: the head (exit {})".format(r.returncode))
        sys.exit(r.returncode)
    cur = float(json.load(open(LIVE, encoding="utf-8")).get("INTENT_HOLD", -1))
    if cur != 8.0:
        log("the head is open; the lock is at {}: no lock stage".format(cur))
    else:
        log("the head is open; the lock stage begins")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "ramp_live.py"), a.run, "INTENT_HOLD", "8", "0", "1", "--values", VALUES, "--keep-each", "policy_lock{}_b12a.pt",
                            "--every", str(a.every_saves), "--hold-at", "0.40", "--min-s", str(a.min_s), "--sleep", str(min(a.poll, 30)), "--settle", str(a.settle), "--dir", D], cwd=ROOT)
        if r.returncode:
            log("RAMP FAILED: the lock (exit {})".format(r.returncode))
            sys.exit(r.returncode)
        log("the lock is gone; the checks are still flagged")
    while True:
        time.sleep(a.poll)


if __name__ == "__main__":
    main()

"""b1.1a's schedule (owner, 2026-10-31; the card): shut to update 10; the brain's old belief out (BRAIN_FADE 0 -> 1, seven steps, one right after each save, ~4.5 h); held to update 90; the pull toward level
out (LEVEL_PULL 0.95 -> 1, three steps, ~2 h); held to update 130; the target lock out (INTENT_HOLD 8 -> 4 -> 2 -> 1 s, ~2 h). As b1.0a: a check under 50% is written as FLAG; only a check of 40% or less against the start holds a step.
Keeps the saves before each fade. WIN_ADD and everything else in live.json are left as they are.
    python docs/runs/b1.1/b1.1a/ramp_b11.py <run> [--shut N] [--hold-pull N] [--hold-lock N] [--brain-steps N] [--pull-steps N] [--min-s S] [--poll S] [--dir D]"""
import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
RAMP = os.path.join(ROOT, "tools", "run", "ramp_live.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--shut", type=int, default=10)
    ap.add_argument("--hold-pull", type=int, default=90)
    ap.add_argument("--hold-lock", type=int, default=130)
    ap.add_argument("--brain-steps", type=int, default=7)
    ap.add_argument("--pull-steps", type=int, default=3)
    ap.add_argument("--min-s", type=float, default=25 * 60)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--dir", default="")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    MET, WD = os.path.join(D, "metrics.jsonl"), os.path.join(D, "watch")
    os.makedirs(WD, exist_ok=True)

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        for f in ("ramp.log", "watch.log"):
            with open(os.path.join(WD, f), "a") as fh:
                fh.write(line + "\n")

    def updates():
        try:
            return sum(1 for x in open(MET) if x.strip())
        except FileNotFoundError:
            return 0

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start (b1.0a's end)", "checks_ref.jsonl": "v0.6.0's end"}
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

    def fade(name, frm, to, step, keep, *more):
        r = subprocess.run([sys.executable, RAMP, a.run, name, str(frm), str(to), str(step), "--keep-as", keep, "--hold-at", "0.40",
                            "--min-s", str(a.min_s), "--sleep", str(min(a.poll, 30)), "--dir", D] + list(more), cwd=ROOT)
        if r.returncode:
            log("RAMP FAILED: {} (exit {})".format(name, r.returncode))
            sys.exit(r.returncode)

    while updates() < a.shut:
        time.sleep(a.poll)
    up = lambda x, n: math.ceil(x / n * 1e6) / 1e6             # (rounded up: the last step lands on TO)  # noqa: E731
    fade("BRAIN_FADE", 0.0, 1.0, up(1.0, a.brain_steps), "policy_prebrain_b11a.pt")
    log("the brain's old belief is out; held to update {}".format(a.hold_pull))
    while updates() < a.hold_pull:
        time.sleep(a.poll)
    fade("LEVEL_PULL", 0.95, 1.0, up(0.05, a.pull_steps), "policy_nobrain_b11a.pt")
    log("the pull is out; held to update {}".format(a.hold_lock))
    while updates() < a.hold_lock:
        time.sleep(a.poll)
    fade("INTENT_HOLD", 8.0, 1.0, 1.0, "policy_nopull_b11a.pt", "--values", "4,2,1")
    log("the lock is out; all three fades done; the checks are still flagged")
    while True:
        time.sleep(a.poll)


if __name__ == "__main__":
    main()

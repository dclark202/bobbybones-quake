"""b1.2d's end at its save of update 80 (owner, 2026-11-02 17:10: "let's end the 1.2d at update 80; you can schedule that"): waits until update 71 is in metrics.jsonl
(the save of 70 is behind), then runs tools/run/stop_run.py duel_gru_b1_2d b12d --keep-checks, which keeps the next save, update 80's, as keep/policy_end_b12d.pt with its optimizer and stops
the trainer, ramp and self-play logger; the watcher stays and checks the save of update 80 against the start. Started detached; writes end_at_80.log.
    python docs/runs/b1.2/b1.2d/end_at_80.py"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MET = os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2d", "metrics.jsonl")
LOG = os.path.join(HERE, "end_at_80.log")


def say(s):
    with open(LOG, "a") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")


def last():
    try:
        with open(MET) as f:
            L = [x for x in f if x.strip()]
        return int(json.loads(L[-1].replace("NaN", "null"))["update"]) if L else 0
    except Exception:                                        # noqa: BLE001  (a line being written)
        return -1


say("waiting for update 71 (now {})".format(last()))
while last() < 71:
    time.sleep(30)
n = last()
if n >= 80:
    say("update {} already: the save of 80 is behind; NOT stopped (ask the owner)".format(n))
    sys.exit(1)
say("update {}: stop_run waits for the next save, update 80's".format(n))
with open(LOG, "a") as f:
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "stop_run.py"), "duel_gru_b1_2d", "b12d", "--keep-checks"], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
say("stop_run exit {}; the end at update {}".format(r.returncode, last()))

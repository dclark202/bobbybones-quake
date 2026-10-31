"""Starts v0.6.1d after v0.6.1c (owner, 2026-10-30: "Schedule this to run starting after c finishes, for 12 hours"). Waits until
v0.6.1c's log ends in "exit", keeps its end (keep/policy_end_v061c.pt + opt_end_v061c.pt, nothing overwritten), runs v0.6.1d's smoke
run into smoke.log, and only if that ends ALL PASSED runs start.ps1 (which makes every other check and refuses on any). A failed step
stops here, logged in after_c.log; nothing is started and nothing is deleted.
    python docs/runs/v0.6.1d/after_c.py"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SR = os.path.join(ROOT, "data", "sim_runs")
RC = os.path.join(SR, "duel_gru_v0_6_1c")
LOGC = os.path.join(SR, "duel_gru_v0_6_1c.log")


def say(s):
    with open(os.path.join(HERE, "after_c.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")


def ended():
    with open(LOGC, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 400))
        L = f.read().decode("utf-8", "replace").strip().splitlines()
    return bool(L) and L[-1].startswith("exit")


say("waiting for v0.6.1c's end")
while not ended():
    time.sleep(30)
time.sleep(60)
say("v0.6.1c ended")
for a, b in (("policy.pt", "policy_end_v061c.pt"), ("opt.pt", "opt_end_v061c.pt")):
    dst = os.path.join(RC, "keep", b)
    if not os.path.exists(dst):
        shutil.copy2(os.path.join(RC, a), dst)
    say("kept " + b)
with open(os.path.join(HERE, "smoke.log"), "w", encoding="utf-8") as f:
    r = subprocess.run([sys.executable, os.path.join(HERE, "smoke.py")], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
last = open(os.path.join(HERE, "smoke.log"), encoding="utf-8", errors="replace").read().strip().splitlines()[-1:]
say("smoke run: exit {} | {}".format(r.returncode, last))
if r.returncode or not last or "ALL PASSED" not in last[0]:
    say("THE SMOKE RUN DID NOT PASS: v0.6.1d not started")
    sys.exit(1)
r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "start.ps1")], cwd=ROOT)
say("start.ps1 exit {}".format(r.returncode))
sys.exit(r.returncode)

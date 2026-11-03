"""Owner's go, 2026-10-31 ("Start now 12 hrs"): v0.6.1e's smoke run into smoke.log, then start.ps1 if it ended ALL PASSED. Logged in go.log.
    python docs/runs/v0.6.1e/go.py"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def say(s):
    with open(os.path.join(HERE, "go.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")


say("smoke run started")
with open(os.path.join(HERE, "smoke.log"), "w", encoding="utf-8") as f:
    r = subprocess.run([sys.executable, os.path.join(HERE, "smoke.py")], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
last = open(os.path.join(HERE, "smoke.log"), encoding="utf-8", errors="replace").read().strip().splitlines()[-1:]
say("smoke run: exit {} | {}".format(r.returncode, last))
if r.returncode or not last or "ALL PASSED" not in last[0]:
    say("THE SMOKE RUN DID NOT PASS: v0.6.1e not started")
    sys.exit(1)
r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "start.ps1")], cwd=ROOT)
say("start.ps1 exit {}".format(r.returncode))
sys.exit(r.returncode)

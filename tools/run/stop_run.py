"""A run's end by hand (the owner's word only: CLAUDE.md's rule 6): at its next save, keeps policy.pt and opt.pt as keep/policy_end_<tag>.pt + opt_end_<tag>.pt, then stops its trainer, watcher, ramp, self-play logger and checks.
Starts nothing, deletes nothing; refuses if the end is already kept. --now: this save, without waiting (only right after a save).
    python tools/run/stop_run.py duel_gru_b1_1a b11a [--now] [--keep-checks]"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN, TAG = sys.argv[1], sys.argv[2]
D = os.path.join(ROOT, "data", "sim_runs", RUN)
POL, OPT = os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt")
ENDS = ((POL, os.path.join(D, "keep", "policy_end_{}.pt".format(TAG))), (OPT, os.path.join(D, "keep", "opt_end_{}.pt".format(TAG))))
assert not any(os.path.exists(b) for _, b in ENDS), "the end is already kept"
Q = ("Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'python.exe' -and $_.CommandLine -like '*{}*' -and $_.CommandLine -notlike '*stop_run*' }} "
     "| ForEach-Object {{ $_.ProcessId }}".format(RUN))
if "--keep-checks" in sys.argv:                              # (the trainer, ramp and self-play logger only: a running check and its watcher go on)
    Q = Q.replace("-notlike '*stop_run*'", "-notlike '*stop_run*' -and $_.CommandLine -notlike '*watch.py*' -and $_.CommandLine -notlike '*duel_eval*'")


def procs():
    return [int(x) for x in subprocess.run(["powershell", "-NoProfile", "-Command", Q], capture_output=True, text=True).stdout.split()]


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


seen = os.path.getmtime(POL)
if "--now" not in sys.argv:
    say("waiting for the next save; the last was " + time.ctime(seen))
    while True:
        time.sleep(10)
        tp, to = os.path.getmtime(POL), os.path.getmtime(OPT)
        if tp > seen and abs(tp - to) < 120 and time.time() - max(tp, to) > 20:
            break
for a, b in ENDS:
    shutil.copy2(a, b)
say("kept the save of {} as {}".format(time.ctime(os.path.getmtime(POL)), TAG))
P = procs()
say("stopping {}".format(P))
for p in P:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p)], capture_output=True)
time.sleep(30)
left = procs()
say("still running: {}".format(left))
sys.exit(1 if left else 0)

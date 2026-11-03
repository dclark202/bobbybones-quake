"""b1.0a's end and b1.1a's start (owner, 2026-10-31: b1.0 to about 21:00, then b1.1): waits until 21:00; at the next save of b1.0a (policy.pt and opt.pt rewritten and standing still), keeps them as
keep/policy_end_b10a.pt + opt_end_b10a.pt; stops b1.0a's trainer, watcher, ramp and self-play logger; then runs start.ps1, which refuses on any failed check. Logged in handover.log. Nothing is deleted.
    python docs/runs/b1.1/b1.1a/handover.py [--at HH:MM]"""
import datetime
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
D = os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_0a")
POL, OPT = os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt")


def say(s):
    with open(os.path.join(HERE, "handover.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")


def procs():
    """b1.0a's own processes, the trainer's and the watcher's children included by their command lines"""
    q = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*duel_gru_b1_0a*' -and "
         "($_.CommandLine -like '*train_duel_rnn*' -or $_.CommandLine -like '*watch.py*' -or $_.CommandLine -like '*ramp_win*' -or $_.CommandLine -like '*selfplay_*' -or $_.CommandLine -like '*duel_eval*') } "
         "| ForEach-Object { $_.ProcessId }")
    return [int(x) for x in subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True).stdout.split()]


def main():
    at = sys.argv[sys.argv.index("--at") + 1] if "--at" in sys.argv else "21:00"
    h, m = map(int, at.split(":"))
    when = datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
    say("armed: waiting for {}".format(when))
    while datetime.datetime.now() < when:
        time.sleep(30)
    seen = os.path.getmtime(POL)
    say("waiting for b1.0a's next save")
    while True:
        time.sleep(15)
        tp, to = os.path.getmtime(POL), os.path.getmtime(OPT)
        if tp > seen and abs(tp - to) < 120 and time.time() - max(tp, to) > 20:
            break
    shutil.copy2(POL, os.path.join(D, "keep", "policy_end_b10a.pt"))
    shutil.copy2(OPT, os.path.join(D, "keep", "opt_end_b10a.pt"))
    say("kept the save of {} as b1.0a's end".format(time.ctime(tp)))
    P = procs()
    say("stopping b1.0a's processes: {}".format(P))
    for p in P:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p)], capture_output=True)
    time.sleep(60)
    left = procs()
    if left:
        say("STILL RUNNING: {}: b1.1a not started".format(left))
        return 1
    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "start.ps1")], cwd=ROOT)
    say("start.ps1 exit {}".format(r.returncode))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())

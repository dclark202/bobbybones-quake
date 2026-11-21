"""The nightly housekeeping (owner, 2026-11-11: "every day or so they need to be migrated off and onto long term storage (T)"; "automate
the very simple mechanical stuff"). One hidden scheduled task ("BobbyBones nightly", pythonw: no window) runs, in this order:
    1. tools/run/backup.py          what cannot be remade, copied to T: (nothing removed anywhere)
    2. tools/run/offload.py auto    the intermediates of runs not trained for 3 days (the checks' recorded games, snapshots but the
                                    anchors, scratch test folders): copied to T:, each copy read back, then removed from C: by that
                                    check's manifest. keep/ is never touched; a run with a trainer running is left whole
    3. tools/run/docker_tidy.py     once a week: stopped containers, untagged images, old qlbot tags, build cache over 20 GB
While a trainer runs only step 1 is done (hard rule 9). A step that fails does not stop the next; each writes its own log (T:\\BobbyBones_backup\\backup.log, ...\\offload\\offload.log,
data\\docker_tidy.log) and this file's line goes to data\\nightly.log. With T: not there, steps 1 and 2 do nothing.
    register:  powershell -ExecutionPolicy Bypass -File tools\\run\\register_nightly.ps1"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOG = os.path.join(ROOT, "data", "nightly.log")
STAMP = os.path.join(ROOT, "data", "docker_tidy.stamp")
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)   # (no window; below normal: a run that trains keeps its cores)
PY = os.path.join(os.path.dirname(sys.executable), "python.exe")
if not os.path.exists(PY):
    PY = sys.executable


def step(name, *args, timeout=6 * 3600):
    t0 = time.time()
    try:
        r = subprocess.run([PY, os.path.join(HERE, name)] + list(args), capture_output=True, text=True, creationflags=NW, timeout=timeout, cwd=ROOT)
        rc, tail = r.returncode, ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1:]
    except (OSError, subprocess.TimeoutExpired) as x:
        rc, tail = -1, [repr(x)]
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("{} {} {} rc={} {:.0f}s | {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), name, " ".join(args), rc, time.time() - t0, (tail or [""])[0][:300]))
    return rc


def training():
    """a trainer is running (by its command line); True too if that cannot be told"""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*train_duel_rnn*' -and $_.Name -like 'python*' } | Measure-Object).Count"],
                             capture_output=True, text=True, creationflags=NW, timeout=120).stdout.strip()
        return int(out) > 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return True


def main():
    step("backup.py")
    if training():                                           # (hard rule 9: the running run gets full priority; the backup alone is small)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("{} a trainer is running: the offload and the Docker tidy wait for a night without one\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
        return 0
    step("offload.py", "auto", "--days", "3")
    if not os.path.exists(STAMP) or time.time() - os.stat(STAMP).st_mtime > 6.5 * 86400:
        if step("docker_tidy.py", timeout=3600) == 0:
            open(STAMP, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

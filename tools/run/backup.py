"""The nightly backup (owner, 2026-10-28, after the data loss): copies what cannot be remade to T:\\BobbyBones_backup (or BB_BACKUP),
never deleting anything there. Copied when new or changed (size or time): every run's keep/ (version ends, kept saves,
optimizers), live.json, live_settings.env, snapshots/ and selfplay/ (the self-play games the judges are fitted on); the trainers'
logs (data/sim_runs/*.log); data/maps; data/sim_runs/brainppl/ packs and shards; the movement
network (data/sim_runs/move_v17_look); the win-chance judges (data/sim_runs/judge); data/owner.env and data/demo_root.txt. Logs to <backup>/backup.log.
    python tools/run/backup.py            (the scheduled task "BobbyBones backup" runs it nightly)"""
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DST = os.environ.get("BB_BACKUP") or r"T:\BobbyBones_backup"
DATA = os.environ.get("BB_DATA") or os.path.join(ROOT, "data")


def want(rel):
    p = rel.replace("\\", "/").split("/")
    if rel in ("owner.env", "demo_root.txt") or p[0] == "maps":
        return True
    if p[0] == "sim_runs" and len(p) == 2:
        return p[1].endswith(".log")                         # the trainers' logs
    if p[0] == "sim_runs" and len(p) >= 3:
        if p[1] in ("brainppl", "move_v17_look", "judge"):
            return True
        return p[2] in ("keep", "snapshots", "selfplay", "live.json", "live_settings.env", "metrics.jsonl")
    return False


def main():
    if not os.path.isdir(os.path.dirname(DST.rstrip("\\/")) or DST):
        print("backup drive not there:", DST)
        return 1
    os.makedirs(DST, exist_ok=True)
    n = b = 0
    t0 = time.time()
    for dp, dn, fn in os.walk(DATA):
        dn[:] = [d for d in dn if not (os.path.islink(os.path.join(dp, d)) or getattr(os.path, "isjunction", lambda _: False)(os.path.join(dp, d)))]   # (never follow a link)
        for f in fn:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, DATA)
            if not want(rel):
                continue
            dst = os.path.join(DST, "data", rel)
            s = os.stat(src)
            if os.path.exists(dst):
                d = os.stat(dst)
                if d.st_size == s.st_size and int(d.st_mtime) >= int(s.st_mtime):
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst + ".part")
            os.replace(dst + ".part", dst)
            n += 1
            b += s.st_size
    with open(os.path.join(DST, "backup.log"), "a") as lg:
        lg.write("{} copied {} files, {:.1f} GB, {:.0f} s\n".format(time.strftime("%Y-%m-%d %H:%M"), n, b / 1e9, time.time() - t0))
    print("backup: copied", n, "files", round(b / 1e9, 2), "GB to", DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())

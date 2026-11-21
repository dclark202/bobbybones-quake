"""Keeping Docker's disk from filling C: (owner, 2026-11-11: "put a cap on its bloat"; "automate the very simple mechanical stuff").
What it removes, and nothing else:
    stopped containers older than 7 days
    untagged (dangling) images
    qlbot:<tag> images older than 14 days that no container uses, except the kept ones: qlbot:latest, qlbot:pub-*, and every tag named in
    data/docker_keep.txt (a tag a line). Every qlbot image can be rebuilt from git (docker build -t qlbot .)
    build cache above 20 GB
Another project's images are never touched. Nothing is done if Docker is not running. No window (CLAUDE.md, global rule): every child with
CREATE_NO_WINDOW. Logs to data/docker_tidy.log.
    python tools/run/docker_tidy.py [--dry]        (weekly, from tools/run/nightly.py)
The disk file itself (docker_data.vhdx) never shrinks on its own: tools/run/docker_compact.ps1, by hand, as administrator."""
import datetime
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "data", "docker_tidy.log")
KEEP_FILE = os.path.join(ROOT, "data", "docker_keep.txt")
KEEP = {"qlbot:latest"}
TAG_DAYS, CACHE = 14, "20GB"
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(*a, timeout=1800):
    try:
        r = subprocess.run(["docker"] + list(a), capture_output=True, text=True, creationflags=NW, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as x:
        return 1, repr(x)


def log(s):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")
    try:
        print(s, flush=True)
    except (OSError, ValueError, AttributeError):
        pass


def main():
    dry = "--dry" in sys.argv
    rc, out = run("info", "--format", "{{.ServerVersion}}", timeout=60)
    if rc != 0:
        log("docker is not running: nothing done")
        return 0
    keep = set(KEEP)
    if os.path.exists(KEEP_FILE):
        keep |= {x.strip() for x in open(KEEP_FILE, encoding="utf-8") if x.strip() and not x.startswith("#")}
    rc, used = run("ps", "-a", "--format", "{{.Image}}")
    used = set(used.split())
    rc, out = run("images", "--format", "{{.Repository}}:{{.Tag}}|{{.CreatedAt}}")
    old = []
    now = datetime.datetime.now()
    for line in out.splitlines():
        tag, _, made = line.partition("|")
        if not tag.startswith("qlbot:") or tag in keep or tag.startswith("qlbot:pub-") or tag in used or tag.endswith(":<none>"):
            continue
        try:
            age = (now - datetime.datetime.strptime(made[:19], "%Y-%m-%d %H:%M:%S")).days
        except ValueError:
            continue
        if age >= TAG_DAYS:
            old.append(tag)
    if dry:
        log("dry: would remove stopped containers over 7 days, untagged images, build cache over {}, and the tags {}".format(CACHE, old))
        return 0
    rc, a = run("container", "prune", "-f", "--filter", "until=168h")
    for t in old:
        run("rmi", t)
    rc, b = run("image", "prune", "-f")
    rc, c = run("builder", "prune", "-f", "--keep-storage", CACHE)
    rc, df = run("system", "df")
    last = lambda s: (s.strip().splitlines() or [""])[-1]   # noqa: E731
    log("containers: {} | old qlbot tags removed: {} | untagged images: {} | build cache: {}".format(last(a), old, last(b), last(c)))
    log("docker system df: " + " ; ".join(" ".join(x.split()) for x in df.strip().splitlines()[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

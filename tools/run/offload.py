"""Moving a run's intermediate files off C: to the long-term copy on T: (owner, 2026-11-11: "the intermediaries are going to eat up my
1TB nvme drive, and every day or so they need to be migrated off"; "be VERY careful not to delete any files that are not backed up").
Hard rule 1 applies: a file leaves C: only after its copy on T: was read back and its SHA-256 is the source's, and only by the manifest
of that check.

What is moved (the same paths under <backup>/data as tools/run/backup.py writes):
    sim_runs/<run>/watch/panel/**        the checks' recorded games (the bulk; the small check files of watch/ stay)
    sim_runs/<run>/snapshots/**          the league's snapshots, except anchor*.pt (a later run's league is built from them)
    sim_runs/scratch_*/**                the tests' scratch run folders, except those named in --keep-scratch (a prefix each)
What is never moved: keep/ (every version's end, the public and server models), the judges, the maps, the packs, a run's metrics, live
files and logs; anything of a run whose trainer is running; anything under a link (a junction is never entered).

    python tools/run/offload.py plan  [--keep-scratch scratch_18a] [--days 0]     the list and its size, nothing written
    python tools/run/offload.py copy  [same options]     copy what is not there, read every copy back, write the manifest
                                                         (<backup>/offload/manifest_<time>.json); nothing is removed from C:
    python tools/run/offload.py free <manifest>          remove from C: each file of the manifest whose check passed, if the source is
                                                         unchanged since (size, time) and the copy is still there at that size
    python tools/run/offload.py auto  [--days 3]         copy, then free by that copy's manifest (the nightly job: tools/run/nightly.py)
--days N: only files not written for N days, and no file of a run that was trained in the last N days (its policy.pt or metrics.jsonl). Folders are left in place, empty. Logs to <backup>/offload/offload.log."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DST = os.environ.get("BB_BACKUP") or r"T:\BobbyBones_backup"
DATA = os.environ.get("BB_DATA") or os.path.join(ROOT, "data")
CHUNK = 8 << 20


def is_link(p):
    return os.path.islink(p) or getattr(os.path, "isjunction", lambda _: False)(p)


def trainers():
    """the runs a trainer is running on (by its own command line)"""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*train_duel_rnn*' } | ForEach-Object { $_.CommandLine }"],
                             capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except OSError:
        return None
    runs = set()
    for line in out.splitlines():
        w = line.split()
        for i, x in enumerate(w):
            if x == "--run" and i + 1 < len(w):
                runs.add(w[i + 1].strip('"'))
    return runs


def want(parts, keep_scratch):
    """parts: the path under data/, split. -> the kind moved, or None"""
    if len(parts) < 4 or parts[0] != "sim_runs":
        return None
    run = parts[1]
    if "keep" in parts[2:]:
        return None
    if run.startswith("scratch_"):
        return None if any(run.startswith(k) for k in keep_scratch) else "scratch"
    if parts[2] == "watch" and len(parts) >= 5 and parts[3] == "panel":
        return "panel"
    if parts[2] == "snapshots" and not parts[-1].startswith("anchor"):
        return "snapshots"
    return None


def select(a):
    busy = trainers()
    assert busy is not None, "the running trainers could not be listed: nothing is selected"
    old = time.time() - a.days * 86400.0
    sel = []
    sr = os.path.join(DATA, "sim_runs")
    for run in sorted(os.listdir(sr)):
        top = os.path.join(sr, run)
        if not os.path.isdir(top) or is_link(top) or run in busy:
            continue
        if a.days > 0 and any(os.path.exists(os.path.join(top, f)) and os.stat(os.path.join(top, f)).st_mtime > old for f in ("policy.pt", "metrics.jsonl")):
            continue                                         # (a run of these days: a restart or its report may want its files here)
        for dp, dn, fn in os.walk(top):
            dn[:] = [d for d in dn if not is_link(os.path.join(dp, d))]
            for f in fn:
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, DATA)
                k = want(rel.replace("\\", "/").split("/"), a.keep_scratch)
                if k is None or is_link(src):
                    continue
                s = os.stat(src)
                if s.st_mtime > old:
                    continue
                sel.append(dict(rel=rel, kind=k, size=s.st_size, mtime=s.st_mtime))
    return sel, sorted(busy)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def copy_hash(src, dst):
    """src -> dst (through dst.part); the source's SHA-256, taken from the bytes that were written"""
    h = hashlib.sha256()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, "rb", buffering=0) as fi, open(dst + ".part", "wb", buffering=0) as fo:
        while True:
            b = fi.read(CHUNK)
            if not b:
                break
            h.update(b)
            fo.write(b)
        fo.flush()
        os.fsync(fo.fileno())
    st = os.stat(src)
    os.utime(dst + ".part", (st.st_atime, st.st_mtime))
    os.replace(dst + ".part", dst)
    return h.hexdigest()


def log(s):
    os.makedirs(os.path.join(DST, "offload"), exist_ok=True)
    with open(os.path.join(DST, "offload", "offload.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")
    print(s, flush=True)


def summary(sel):
    by = {}
    for e in sel:
        run = e["rel"].replace("\\", "/").split("/")[1]
        key = (e["kind"], "scratch_*" if e["kind"] == "scratch" else run)
        n, b = by.get(key, (0, 0))
        by[key] = (n + 1, b + e["size"])
    for (k, run), (n, b) in sorted(by.items(), key=lambda x: -x[1][1]):
        print("  {:9s} {:34s} {:6d} files {:8.2f} GB".format(k, run, n, b / 1e9))
    tot = {}
    for e in sel:
        tot[e["kind"]] = tot.get(e["kind"], 0) + e["size"]
    print("total: {} files, {:.1f} GB ({})".format(len(sel), sum(e["size"] for e in sel) / 1e9,
                                                   ", ".join("{} {:.1f}".format(k, v / 1e9) for k, v in sorted(tot.items()))), flush=True)


def plan(a):
    sel, busy = select(a)
    summary(sel)
    if busy:
        print("left out, a trainer is running on:", ", ".join(busy))
    return 0


def copy(a):
    if not os.path.isdir(os.path.dirname(DST.rstrip("\\/")) or DST):
        print("backup drive not there:", DST)
        return 1
    sel, busy = select(a)
    summary(sel)
    need = sum(e["size"] for e in sel)
    import shutil
    free = shutil.disk_usage(os.path.dirname(DST.rstrip("\\/")) or DST).free
    assert free > need + (50 << 30), "not enough room on the backup drive: {:.0f} GB free, {:.0f} GB to copy".format(free / 1e9, need / 1e9)
    mf = os.path.join(DST, "offload", "manifest_{}.json".format(time.strftime("%Y%m%d_%H%M%S")))
    os.makedirs(os.path.dirname(mf), exist_ok=True)
    log("copy: {} files, {:.1f} GB selected; manifest {}".format(len(sel), need / 1e9, mf))
    t0 = time.time()
    done = ok = copied = bad = 0
    for e in sel:
        src, dst = os.path.join(DATA, e["rel"]), os.path.join(DST, "data", e["rel"])
        try:
            if os.path.exists(dst) and os.path.getsize(dst) == e["size"]:
                hs = sha(src)                                # (there already, the nightly backup's: both sides read whole)
            else:
                hs = copy_hash(src, dst)
                copied += 1
            hd = sha(dst)                                    # (the copy read back from the backup drive)
            s2 = os.stat(src)
            e["sha256"], e["dst"] = hs, dst
            e["ok"] = bool(hs == hd and os.path.getsize(dst) == e["size"] and s2.st_size == e["size"] and s2.st_mtime == e["mtime"])
        except OSError as x:
            e["ok"], e["error"] = False, repr(x)
        ok += int(e["ok"])
        bad += int(not e["ok"])
        if not e["ok"]:
            log("NOT VERIFIED (it stays on C:): {} {}".format(e["rel"], e.get("error", "the copy's hash or the source differs")))
        done += e["size"]
        if (ok + bad) % 500 == 0:
            json.dump(dict(data=DATA, backup=DST, complete=False, files=sel), open(mf + ".part", "w"))
            print("  {:.1f} of {:.1f} GB, {} files, {:.0f} s".format(done / 1e9, need / 1e9, ok + bad, time.time() - t0), flush=True)
    json.dump(dict(data=DATA, backup=DST, complete=True, time=time.strftime("%Y-%m-%d %H:%M:%S"), files=sel), open(mf + ".part", "w"))
    os.replace(mf + ".part", mf)
    log("copy done: {} verified ({} newly copied), {} NOT verified, {:.1f} GB, {:.0f} s; manifest {}".format(ok, copied, bad, need / 1e9, time.time() - t0, mf))
    a.manifest = mf
    return 0 if bad == 0 else 2


def auto(a):
    rc = copy(a)
    if rc == 1 or not getattr(a, "manifest", None):
        return rc
    return free(a) or rc


def free(a):
    M = json.load(open(a.manifest))
    assert M.get("complete"), "the manifest is not of a finished copy"
    assert os.path.normcase(os.path.abspath(M["data"])) == os.path.normcase(os.path.abspath(DATA)), "the manifest is of another data folder"
    busy = trainers()
    assert busy is not None, "the running trainers could not be listed: nothing is removed"
    n = b = skip = 0
    for e in M["files"]:
        src = os.path.join(DATA, e["rel"])
        parts = e["rel"].replace("\\", "/").split("/")
        why = None
        if not e.get("ok") or not e.get("sha256"):
            why = "not verified at the copy"
        elif want(parts, ()) is None or "keep" in parts:
            why = "not a kind that is moved"
        elif parts[1] in busy:
            why = "a trainer is running on its run"
        elif not os.path.exists(src):
            continue                                         # (gone already: a second pass)
        elif is_link(src) or any(is_link(os.path.join(DATA, *parts[:i])) for i in range(1, len(parts))):
            why = "under a link"
        else:
            s = os.stat(src)
            dst = e["dst"]
            if s.st_size != e["size"] or s.st_mtime != e["mtime"]:
                why = "the source changed since the copy"
            elif not os.path.exists(dst) or os.path.getsize(dst) != e["size"]:
                why = "the copy is not there at its size"
        if why:
            skip += 1
            log("kept on C: ({}): {}".format(why, e["rel"]))
            continue
        os.remove(src)
        n += 1
        b += e["size"]
    log("free: {} files, {:.1f} GB removed from C: by {}; {} kept".format(n, b / 1e9, a.manifest, skip))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("plan", "copy", "auto"):
        p = sp.add_parser(c)
        p.add_argument("--keep-scratch", nargs="*", default=[], help="scratch folders that stay (a name's start each)")
        p.add_argument("--days", type=float, default=3.0 if c == "auto" else 0.0, help="only files not written for this many days")
    p = sp.add_parser("free")
    p.add_argument("manifest")
    a = ap.parse_args()
    return dict(plan=plan, copy=copy, free=free, auto=auto)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

"""The index of the public server's session archive: one row per session in <archive>/sessions.csv, written by the
daily pull (tools/pull_sessions.sh). Reads the packed sessions (<name>.tar.gz) and the leaderboard's frag log
(frags.jsonl: anonymous keys with times) beside them; a session already in the index is not read again.

    python tools/session_index.py [archive folder]     default T:/quake-sessions/public, or data/public
    python tools/session_index.py --since "2026-10-10 21:00"     the sessions with people from then on, and how many persons

Columns: session, kind (ffa / human: a 1v1 with a person / spar), map, policy, started and ended (PC time: the first and
last frame with a person in the game; empty when nobody played), minutes (time covered by frames), people_max (most
people in the game at once; 1 in a 1v1), persons (different people with a frag made or taken in that time: the
leaderboard's keys, so someone who never met Bobby is not counted), frags (between a person and a Bobby), deaths (all,
from the session's events), mb (size of the session unpacked).
"""
import csv
import json
import os
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLS = ["session", "kind", "map", "policy", "started", "ended", "minutes", "people_max", "persons", "frags", "deaths", "mb"]
FRAME = 0.025


def stamp(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""


def read_frags(folder):
    out = []
    try:
        for line in open(os.path.join(folder, "frags.jsonl")):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            who = [r.get(k) for k in ("killer", "victim")]
            out.append((r.get("t", 0.0), [w for w in who if w and not str(w).startswith("bobby")]))
    except OSError:
        pass
    return out


def row_of(path, frags):
    name = os.path.basename(path)[:-len(".tar.gz")]
    kind = name.rsplit("_", 1)[-1]
    row = dict.fromkeys(COLS, "")
    row.update(session=name, kind=kind, people_max=0, persons=0, frags=0, deaths=0, minutes=0.0)
    with tarfile.open(path) as t:
        members = {os.path.basename(m.name): m for m in t.getmembers() if m.isfile()}
        row["mb"] = round(sum(m.size for m in members.values()) / 1e6, 2)
        if "meta.json" in members:
            meta = json.load(t.extractfile(members["meta.json"]))
            row["map"], row["policy"] = meta.get("map", ""), meta.get("policy", "")
        if "events.jsonl" in members:
            for line in t.extractfile(members["events.jsonl"]):
                if b'"event": "death"' in line:
                    row["deaths"] += 1
        first = last = None
        stamps = 0
        if "frames.csv" in members:
            f = t.extractfile(members["frames.csv"])
            head = f.readline().decode().strip().split(",")
            ip = head.index("people") if "people" in head else None      # free-for-all: people in the game, per row
            prev = None
            for line in f:
                c = line.split(b",", 1)[0]
                if c != prev:
                    prev = c
                    stamps += 1
                    try:
                        last = float(c)
                    except ValueError:
                        continue
                    if first is None:
                        first = last
                if ip is not None:
                    try:
                        n = int(line.rsplit(b",", len(head) - ip)[1])
                    except (ValueError, IndexError):
                        n = 0
                    if n > row["people_max"]:
                        row["people_max"] = n
        if ip is None and kind == "human" and stamps:
            row["people_max"] = 1
        if kind == "spar":
            first = last = None if not stamps else first
        row["minutes"] = round(stamps * FRAME / 60.0, 1)
        if first is not None and row["people_max"]:
            row["started"], row["ended"] = stamp(first), stamp(last)
            seen = set()
            for ft, who in frags:
                if first - 1 <= ft <= last + 1 and who:
                    row["frags"] += 1
                    seen.update(who)
            row["persons"] = len(seen)
    return row


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else None
    if since:
        args = [a for a in args if a != since]
    folder = args[0] if args else next((p for p in ("T:/quake-sessions/public", os.path.join(ROOT, "data", "public"))
                                        if os.path.isdir(p)), ".")
    path = os.path.join(folder, "sessions.csv")
    rows = {}
    if os.path.exists(path):
        with open(path, newline="") as f:
            rd = csv.DictReader(f)
            if rd.fieldnames == COLS:
                rows = {r["session"]: r for r in rd}
    frags = read_frags(folder)
    new = 0
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".tar.gz") or fn[:-len(".tar.gz")] in rows:
            continue
        try:
            r = row_of(os.path.join(folder, fn), frags)
        except (tarfile.TarError, OSError, ValueError) as e:
            print("not read: {} ({})".format(fn, e))
            continue
        rows[r["session"]] = r
        new += 1
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])
    if since:
        t0 = time.mktime(time.strptime(since, "%Y-%m-%d %H:%M"))
        sel = [r for r in rows.values() if r["ended"] and time.mktime(time.strptime(r["ended"], "%Y-%m-%d %H:%M:%S")) >= t0]
        who = set()
        for ft, w_ in frags:
            if ft >= t0:
                who.update(w_)
        for r in sorted(sel, key=lambda r: r["started"]):
            print("{started}  {minutes:>6} min  {map:<15} {kind:<5} people {people_max}  persons {persons}  frags {frags}".format(**r))
        print("since {}: {} sessions with people, {} different persons with a frag made or taken".format(since, len(sel), len(who)))
    print("index: {} sessions ({} new) in {}".format(len(rows), new, path))


if __name__ == "__main__":
    main()

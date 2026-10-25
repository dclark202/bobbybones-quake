"""local_games.py: the game history and game reports of the owner's local play tests, on a site served from the PC only
(owner, 2026-10-25: "They *shouldn't* show up on the public leaderboard, just a local hosted site that I can review. But use
the same format"). Nothing here touches the public servers or the public site.

    python tools/local_games.py [--data data/duellive_v042end ...] [--out data/local_site] [--port 8766] [--watch 60]

Each --data folder is a local play-test server's data folder (duels.jsonl, frags.jsonl, ratings.json, sessions/, mind*.jsonl);
default: every data/duellive* folder with a duels.jsonl. A folder plays as a "server" named after it (duellive_v042end ->
v042end), so a game's id names the play test it came from. The steps are the public site's: tools/game_summary.py (with the
mind log), tools/board_merge.py (board and history), tools/board_page.py (the pages). --watch N builds again every N seconds
when a folder's files changed; --port serves the site at http://localhost:<port>/ (0: no server)."""
import argparse
import functools
import glob
import http.server
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def srv_name(folder):
    n = re.sub(r"^duellive_?", "", os.path.basename(os.path.normpath(folder)).lower())
    n = re.sub(r"[^a-z0-9]", "", n) or "pc"
    return n[:8]


def stamp(folders):
    s = []
    for d in folders:
        for f in ["duels.jsonl", "frags.jsonl"] + [os.path.basename(p) for p in glob.glob(os.path.join(d, "mind*.jsonl"))]:
            p = os.path.join(d, f)
            if os.path.exists(p):
                s.append((p, os.path.getmtime(p), os.path.getsize(p)))
    return tuple(s)


def session_lines(d, duels):
    """(owner, 2026-10-25: his local games were missing) a play test is often played in warmup or left by a map change,
    which writes no duels.jsonl line: every person's session of a minute or more that no game line covers becomes one
    (t0 and t from its frames, the score from the frags in it, forfeit unless ten minutes)"""
    import json
    frags = []
    try:
        with open(os.path.join(d, "frags.jsonl"), encoding="utf-8") as f:
            for raw in f:
                try:
                    frags.append(json.loads(raw))
                except ValueError:
                    pass
    except OSError:
        pass
    out = []
    for s in sorted(glob.glob(os.path.join(d, "sessions", "*_human"))):
        p = os.path.join(s, "frames.csv")
        try:
            with open(p, encoding="utf-8") as f:
                f.readline()
                first = f.readline().split(",", 1)[0]
                last = first
                for raw in f:
                    last = raw.split(",", 1)[0] or last
            t0, t1 = float(first), float(last)
        except (OSError, ValueError):
            continue
        if t1 - t0 < 60.0:
            continue
        mp = os.path.basename(s).split("_")[1].lower()
        if any(g.get("map") == mp and t0 - 30 <= float(g.get("t", 0)) <= t1 + 30 for g in duels):
            continue
        inn = [f for f in frags if f.get("map") == mp and t0 - 1 <= float(f.get("t", 0)) <= t1 + 1]
        bob = sum(1 for f in inn if str(f.get("killer", "")).startswith("bobby"))
        keys = [f.get("victim") for f in inn if str(f.get("killer", "")).startswith("bobby")] + \
               [f.get("killer") for f in inn if str(f.get("victim", "")).startswith("bobby")]
        key = max(set(keys), key=keys.count) if keys else "local"
        net = next((str(f.get("net")) for f in inn if f.get("net")), "")
        mins = (t1 - t0) / 60.0
        out.append(dict(t=round(t1, 2), t0=round(t0, 2), map=mp, net=net, key=key, owner=1, minutes=round(mins, 2),
                        score=[len(inn) - bob, bob], forfeit=int(mins < 9.9), kind="game", aim="", local_session=1))
    return out


def work_folder(d, work, n):
    """a copy of a play-test folder's board files with its sessions turned into game lines (session_lines)"""
    import json
    import shutil
    w = os.path.join(work, "srv_" + n)
    os.makedirs(w, exist_ok=True)
    for f in ("frags.jsonl", "ratings.json"):
        if os.path.exists(os.path.join(d, f)):
            shutil.copyfile(os.path.join(d, f), os.path.join(w, f))
    duels = []
    try:
        with open(os.path.join(d, "duels.jsonl"), encoding="utf-8") as f:
            duels = [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        pass
    lines = sorted(duels + session_lines(d, duels), key=lambda g: float(g.get("t", 0)))
    with open(os.path.join(w, "duels.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for g in lines:
            f.write(json.dumps(g) + "\n")
    return w


def build(folders, out):
    py = sys.executable
    work = os.path.join(out, "_work")
    games = os.path.join(work, "games")
    os.makedirs(games, exist_ok=True)
    names = {}
    for d in folders:
        n = srv_name(d)
        if n in names.values():
            n = (n[:6] + str(len(names)))[:8]
        w = work_folder(d, work, n)
        names[w] = n
        r = subprocess.run([py, os.path.join(HERE, "game_summary.py"), "--data", w, "--srv", n, "--all", "--redo", "--out", games,
                            "--sessions", os.path.join(d, "sessions")]
                           + sum((["--mind", m] for m in sorted(glob.glob(os.path.join(d, "mind*.jsonl")))), []),
                           capture_output=True, text=True)
        print("{}: {}".format(n, (r.stdout.strip().splitlines() or [r.stderr.strip()[-300:]])[-1]))
    board, hist = os.path.join(work, "board.json"), os.path.join(work, "history.json")
    args = [py, os.path.join(HERE, "board_merge.py"), "--out", board, "--history-out", hist]
    for d, n in names.items():
        args += ["--server", "{}={}".format(n, d)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print("board_merge failed:", (r.stderr or r.stdout)[-500:])
        return False
    site = os.path.join(out, "site")
    r = subprocess.run([py, os.path.join(HERE, "board_page.py"), board, site, "--history", hist, "--games", games,
                        "--maps", os.path.join(ROOT, "data", "maps"), "--items", os.path.join(ROOT, "plugins", "duel_items.json")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("board_page failed:", (r.stderr or r.stdout)[-500:])
        return False
    print("site built: {} games ({})".format(len(glob.glob(os.path.join(games, "*-*.json"))), time.strftime("%H:%M:%S")))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", action="append", default=[])
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "local_site"))
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--watch", type=float, default=0.0)
    a = ap.parse_args()
    folders = [os.path.abspath(d) for d in a.data] or sorted(
        d for d in glob.glob(os.path.join(ROOT, "data", "duellive*")) if os.path.exists(os.path.join(d, "duels.jsonl")) or glob.glob(os.path.join(d, "sessions", "*_human")))
    if not folders:
        sys.exit("no play-test data folders with a duels.jsonl")
    build(folders, a.out)
    site = os.path.join(a.out, "site")
    if a.port:
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=site)
        h.log_message = lambda *x, **k: None
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("serving http://localhost:{}/history/".format(a.port))
    if a.watch > 0:
        last = stamp(folders)
        while True:
            time.sleep(a.watch)
            now = stamp(folders)
            if now != last:
                last = now
                build(folders, a.out)
    elif a.port:
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()

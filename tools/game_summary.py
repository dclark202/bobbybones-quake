"""game_summary.py: one small JSON per finished duel, for the leaderboard site's game history and game reports (owner,
2026-10-25: "a separate Game history tab ... each game gets a unique id ... the row links to its detailed report").

    python3 tools/game_summary.py --data <server data folder> --srv us [--sessions <dir> ...] [--out <dir>]
        [--frags <frags.jsonl>] [--maps <data/maps>] [--win sim/win_chance.json] [--mind <mind.jsonl>] [--days 7] [--all]

Reads the server's duels.jsonl (plugins/ladder.py: one line per finished duel); for every real game (kind "game") of the
last --days days that has no summary yet, finds its session (plugins/duelbot.py: <data>/sessions/<UTC>_<map>_human/, or its
packed copy <data>/archive/<name>.tar.gz, or any folder named with --sessions) and writes <out>/<game id>.json (default
<data>/games). The id is ratings.game_id: <server>-<UTC start yyyymmdd-hhmmss>-<map>, the same on every machine.

What a summary holds (schema 1, all integers but the clock, positions in units of Q = 8 game units, times in seconds
from the game's start): the game (id, srv, map, t0, len, score [person, Bobby], forfeit, ot, aim, net), pos (both players'
places twice a second, flat [x, y, x, y, ...] / Q: "b" Bobby, "p" the person), frags ([t, victim 0 Bobby | 1 person,
x / Q, y / Q, the killing weapon (the game's numbers, 0 unknown), distance, 1 if the killer saw the victim, -1 if the
death was the victim's own (a suicide or the map: the game takes a point off him)], the running score after it), items
(the mega, red and yellow armor: [t, 0 MH | 1 RA | 2 YA, 0 Bobby | 1 person]), win (Bobby's chance of winning every 5 s
and right after each frag by the pros' score-and-clock table, sim/win_chance.json read as duel_env.py's WIN_PAY reads it:
a straight line between its time steps; in overtime each period is read as the last two minutes again), stats (the
game's own end-of-game table per player: kills, deaths, damage dealt and taken, per weapon [shots, hits, kills, seconds
held]) and, only when a mind log exists for the game (the data folder's mind files: every server records one from 2026-10-25), mind (what
Bobby believed: tools/board_page.py draws it).

Nothing personal: no key, no name, no Steam id, no address (the person is "p"; the history's names come from the board).
A game whose session is not there (played before the session logs, or its folder pulled off the server) gets no summary;
its row in the history is the basic one. Ids tried without a session are kept in <out>/_none.json and tried again only
for an hour after the game's end (a session still being written). Plain Python, no numpy: it runs on the servers' own
Python at nice 19 (private/tools/board).
"""
import argparse
import bisect
import calendar
import csv
import io
import glob
import json
import math
import os
import re
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p_ in (HERE, os.path.join(os.path.dirname(HERE), "plugins")):
    if os.path.exists(os.path.join(p_, "ratings.py")):
        sys.path.insert(0, p_)
        break
import ratings as R  # noqa: E402

SCHEMA = 1
Q = 8                                    # positions are stored in units of Q game units
ITEMS = {"item_health_mega": 0, "item_armor_body": 1, "item_armor_combat": 2}
WEAPONS = ("gauntlet", "machinegun", "shotgun", "grenade", "rocket", "lightning", "railgun", "plasma", "hmg", "bfg",
           "nailgun", "chaingun", "proxmine")
SESS_RE = re.compile(r"^(\d{8}-\d{6})_([a-z0-9_]+)_(human|spar)(?:\.tar\.gz)?$")


def write_atomic(path, text):
    tmp = "{}.tmp{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------- the win-chance table (as duel_env.py WIN_PAY)
class WinTable:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            wc = json.load(f)
        self.p = wc["p"]                                     # [time left step][lead + D]
        self.step = float(wc["left_s"][1])
        self.D = int(wc["diffs"][-1])

    def at(self, d, left):
        """Bobby's chance of winning d frags ahead with `left` seconds to play (duel_env._win_p)"""
        n = len(self.p)
        x = min(max(left / self.step, 0.0), n - 1.0)
        i0 = min(int(x), n - 2)
        f = x - i0
        j = int(min(max(round(d), -self.D), self.D)) + self.D
        return self.p[i0][j] * (1.0 - f) + self.p[i0 + 1][j] * f


def left_at(t, length=600.0, ot=120.0):
    """seconds left on the clock at t seconds into the game; overtime periods read as the last two minutes again"""
    if t < length:
        return length - t
    k = (t - length) % ot
    return ot - k


# ---------------------------------------------------------------------- sessions
class Session:
    """a session folder or its .tar.gz: meta.json, events.jsonl and frames.csv read on demand"""

    def __init__(self, path):
        self.path = path
        m = SESS_RE.match(os.path.basename(path))
        self.kind = m.group(3)
        self.map = m.group(2)
        self.start = float(calendar.timegm(time.strptime(m.group(1), "%Y%m%d-%H%M%S")))     # (the name's time is UTC)
        self.tar = path.endswith(".tar.gz")

    def read(self, name):
        if not self.tar:
            p = os.path.join(self.path, name)
            if not os.path.exists(p):
                return None
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()
        with tarfile.open(self.path, "r:gz") as tf:
            for m in tf:
                if m.isfile() and os.path.basename(m.name) == name:
                    return tf.extractfile(m).read().decode("utf-8", "replace")
        return None


def find_sessions(dirs):
    out = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            m = SESS_RE.match(n)
            if not m or m.group(3) != "human":
                continue
            key = n[:-7] if n.endswith(".tar.gz") else n
            p = os.path.join(d, n)
            if key in out and not out[key].tar:
                continue                                     # (a folder is read before its packed copy)
            if n.endswith(".tar.gz") or os.path.isdir(p):
                out[key] = Session(p)
    return sorted(out.values(), key=lambda s: s.start)


def session_for(sessions, mp, t0):
    """the session of a game on map mp that began at t0: the last human session on that map that started before it"""
    best = None
    for s in sessions:
        if s.map == mp and s.start <= t0 + 30.0:
            best = s
    return best


# ---------------------------------------------------------------------- one game
def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def summarise(line, srv, sess, frags_all, win, mind_path=None):
    """the summary of the duels.jsonl line `line` from session `sess`; None if the session does not cover the game"""
    t_end = float(line["t"])
    t0 = R.game_t0(line)
    length = t_end - t0
    mp = line.get("map")
    ev_txt = sess.read("events.jsonl")
    fr_txt = sess.read("frames.csv")
    if not ev_txt or not fr_txt:
        return None
    ev = []
    for raw in ev_txt.splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if isinstance(e, dict) and "t" in e:
            ev.append(e)
    # positions twice a second
    pos_b, pos_p, last, t_last = [], [], -1.0, None
    rd = csv.reader(io.StringIO(fr_txt))
    head = next(rd, None) or []
    ix = {c: i for i, c in enumerate(head)}
    need = ("t", "b_x", "b_y", "o_x", "o_y", "b_health", "o_health")
    if any(c not in ix for c in need):
        return None
    for r in rd:
        try:
            t = float(r[ix["t"]])
        except (ValueError, IndexError):
            continue
        if t < t0 or t > t_end:
            continue
        t_last = t
        if t - last < 0.5:
            continue
        last = t
        try:
            if ix.get("drill") is not None and r[ix["drill"]] not in ("-", ""):
                continue
            if float(r[ix["b_health"]]) > 0:
                pos_b += [int(round(float(r[ix["b_x"]]) / Q)), int(round(float(r[ix["b_y"]]) / Q))]
            if float(r[ix["o_health"]]) > 0:
                pos_p += [int(round(float(r[ix["o_x"]]) / Q)), int(round(float(r[ix["o_y"]]) / Q))]
        except (ValueError, IndexError):
            continue
    if t_last is None or t_last < t_end - 10.0:
        return None                                          # the session's frames do not reach the game (yet)
    # frags: the deaths in the game; a death that the ladder counted (a frag line within 1.5 s) is the other's
    # point, any other is the victim's own (a hit "in sight" does not tell: a rocket's splash on oneself is often in sight;
    # 92 of 95 games of the US archive end on the game's own score this way, the rest one frag off each side) (a suicide or the map: the game takes a point off him)
    fl = [f for f in frags_all if t0 - 2.0 <= num(f.get("t")) <= t_end + 2.0 and f.get("map") == mp]
    ft = [num(f.get("t")) for f in fl]
    kills = [e for e in ev if e.get("event") == "hit" and e.get("killed") and t0 - 1.0 <= e["t"] <= t_end + 1.0]
    frags, sc, used = [], [0, 0], set()
    for e in ev:
        if e.get("event") != "death" or not (t0 <= e["t"] <= t_end + 0.5) or e.get("drill"):
            continue
        vb = e.get("who") == "bobby"
        st = e.get("state") or {}
        at = st.get("bobby" if vb else "opp") or [0, 0]
        j = bisect.bisect_left(ft, e["t"] - 1.5)
        counted = None
        while j < len(fl) and ft[j] <= e["t"] + 1.5:
            f = fl[j]
            if j not in used and str(f.get("victim", "")).startswith(R.BOT) == vb:
                counted = j
                break
            j += 1
        k = min(kills, key=lambda h: abs(h["t"] - e["t"])) if kills else None
        if k is not None and (abs(k["t"] - e["t"]) > 1.0 or (k.get("victim") == "bobby") != vb):
            k = None
        if counted is not None:
            used.add(counted)
            sc[0 if vb else 1] += 1                          # (sc: [person, Bobby]) the killer's point
            own = 0
        else:
            sc[1 if vb else 0] -= 1
            own = 1
        frags.append([round(e["t"] - t0, 1), 0 if vb else 1, int(round(num(at[0]) / Q)), int(round(num(at[1]) / Q)),
                      int(k.get("attacker_weapon") or 0) if (k and not own) else 0,
                      int(k.get("dist") or 0) if (k and not own) else 0, (1 if k.get("los") else 0) if (k and not own) else 0,
                      -1 if own else 0, sc[0], sc[1]])
    # items
    items = []
    for e in ev:
        if e.get("event") == "pickup" and e.get("item") in ITEMS and t0 <= e["t"] <= t_end:
            by = e.get("by")
            if by in ("bobby", "opp"):
                items.append([round(e["t"] - t0, 1), ITEMS[e["item"]], 0 if by == "bobby" else 1])
    # win chance: every 5 s and right after each frag, from the game's own final score at the end
    wp = []
    if win is not None:
        marks = [(f[0], f[9] - f[8]) for f in frags]
        tt, i, d = 0.0, 0, 0
        pts = sorted(set([round(x * 5.0, 1) for x in range(int(length // 5) + 1)] + [m[0] for m in marks] + [round(length, 1)]))
        for tt in pts:
            while i < len(marks) and marks[i][0] <= tt:
                d = marks[i][1]
                i += 1
            wp.append([tt, int(round(1000 * win.at(d, left_at(tt))))])
    # the game's own end-of-game table
    stats = {}
    for e in ev:
        if e.get("event") != "player_stats" or e.get("warmup") or not (t_end - 20.0 <= e["t"] <= t_end + 120.0):
            continue
        who = "b" if e.get("bot") else "p"
        if who in stats:
            continue
        w = {}
        for k_, v in (e.get("weapons") or {}).items():
            k_ = k_.lower()
            row = [int(v.get("S") or 0), int(v.get("H") or 0), int(v.get("K") or 0), int(v.get("T") or 0)]
            if any(row):
                w[k_] = row
        dmg = e.get("damage") or {}
        stats[who] = dict(k=int(e.get("kills") or 0), d=int(e.get("deaths") or 0), dealt=int(dmg.get("DEALT") or 0),
                          taken=int(dmg.get("TAKEN") or 0), w=w)
    out = dict(v=SCHEMA, id=R.game_id(line, srv), srv=srv, map=mp, t0=int(t0), len=int(round(length)),
               score=[int(x) for x in line.get("score", [0, 0])], forfeit=int(bool(line.get("forfeit"))),
               ot=int(float(line.get("minutes") or 0.0) > 10.03), aim=str(line.get("aim") or ""), net=str(line.get("net") or ""), q=Q,
               pos=dict(b=pos_b, p=pos_p), frags=frags, items=items, win=wp, stats=stats)
    if mind_path:
        m = mind_section(mind_path, mp, t0, t_end, ev, fr_txt)
        if m:
            out["mind"] = m
    return out


# ---------------------------------------------------------------------- the mind log (local play tests; build_data2 of the mockup)
def mind_section(path, mp, t0, t1, ev, fr_txt):
    """what Bobby believed, from a mind log (plugins/duelbot.py !mind, five lines a second) beside where the person was:
    his error by seconds out of sight, his guesses ahead, his reads of the person's next item, the error over the game
    and his believed place twice a second. None without lines for this game."""
    M = []
    for p_ in ([path] if isinstance(path, str) else list(path)):
        try:
            if os.path.getmtime(p_) < t0:                    # (a rotated file that ended before the game began)
                continue
            with open(p_, encoding="utf-8") as f:
                for raw in f:
                    if '"k": "f"' not in raw and '"k":"f"' not in raw:
                        continue
                    try:
                        m = json.loads(raw)
                    except ValueError:
                        continue
                    if m.get("map") == mp and t0 <= num(m.get("t")) <= t1:
                        M.append(m)
        except OSError:
            continue
    M.sort(key=lambda m: num(m.get("t")))
    if len(M) < 50:
        return None
    tr = []
    rd = csv.reader(io.StringIO(fr_txt))
    head = next(rd, None) or []
    ix = {c: i for i, c in enumerate(head)}
    for r in rd:
        try:
            tr.append((float(r[ix["t"]]), float(r[ix["o_x"]]), float(r[ix["o_y"]])))
        except (ValueError, IndexError, KeyError):
            continue
    TT = [x[0] for x in tr]
    d2 = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])

    def at(t):
        i = min(len(tr) - 1, max(0, bisect.bisect_left(TT, t)))
        return tr[i]

    def med(v):
        v = sorted(x for x in v if x is not None)
        return int(round(v[len(v) // 2])) if v else None

    bel, last, last_seen, rows = [], -1.0, None, []
    for m in M:
        b = m.get("bel") or {}
        if m.get("seen"):
            last_seen = (m.get("en") or [0, 0])[:2]
            continue
        if not b.get("ok"):
            continue
        if m["t"] - last >= 0.5:
            last = m["t"]
            bel += [int(round(b["p"][0] / Q)), int(round(b["p"][1] / Q))]
        rows.append((b.get("unseen", 0.0), d2(b["p"], m["en"]), d2(last_seen, m["en"]) if last_seen else None))
    track = []
    for lo, hi, lab in ((0, 1, "0-1 s"), (1, 3, "1-3 s"), (3, 6, "3-6 s"), (6, 15, "6-15 s"), (15, 1e9, "15 s+")):
        k = [r for r in rows if lo <= r[0] < hi]
        track.append(dict(label=lab, share=round(len(k) / max(1, len(rows)), 2), brain=med([r[1] for r in k]), last=med([r[2] for r in k])))
    ahead = []
    for hi_, h in enumerate((1.0, 2.0, 4.0)):
        ea, es = [], []
        for m in M:
            b = m.get("bel") or {}
            if m.get("seen") or not m.get("ahead") or not b.get("ok") or not TT or m["t"] + h > TT[-1]:
                continue
            p = at(m["t"] + h)[1:]
            ea.append(d2(m["ahead"][hi_]["p"], p))
            es.append(d2(b["p"], p))
        ahead.append(dict(h=h, brain=med(ea), stay=med(es)))
    names = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "weapon_rocketlauncher": "RL",
             "weapon_railgun": "RG", "weapon_lightning": "LG"}
    opk = [(e["t"], names[e["item"]]) for e in ev if e.get("event") == "pickup" and e.get("by") == "opp" and e.get("item") in names
           and t0 <= e["t"] <= t1]
    conf, hit, n = {}, 0, 0
    for m in M:
        if not m.get("tgt"):
            continue
        nx = next((it for t, it in opk if 0 < t - m["t"] < 15), None)
        if nx is None:
            continue
        n += 1
        g = m["tgt"][0][0]
        hit += g == nx
        conf[(g, nx)] = conf.get((g, nx), 0) + 1
    truth, right = {}, {}
    for (g, tv), c in conf.items():
        truth[tv] = truth.get(tv, 0) + c
        if g == tv:
            right[tv] = right.get(tv, 0) + c
    target = dict(top1=round(hit / max(1, n), 3), by_truth={k: dict(n=truth[k], right=round(right.get(k, 0) / truth[k], 2)) for k in truth},
                  misses=[[g, tv, c] for (g, tv), c in sorted(conf.items(), key=lambda x: -x[1]) if g != tv][:4])
    sights = sur = 0
    for i, m in enumerate(M):
        if i and m.get("seen") and not M[i - 1].get("seen") and M[i - 1].get("appear"):
            sights += 1
            sur += M[i - 1]["appear"][0] < 0.15
    tl, lt = [], -10.0
    for m in M:
        b = m.get("bel") or {}
        if not m.get("seen") and b.get("ok") and m["t"] - lt >= 5:
            lt = m["t"]
            tl.append([round(m["t"] - t0, 1), int(round(d2(b["p"], m["en"])))])
    return dict(bel=bel, track=track, ahead=ahead, target=target, sightings=sights, surprises=sur,
                seen_share=round(sum(1 for m in M if m.get("seen")) / max(1, len(M)), 2), err_timeline=tl)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="the server's data folder (duels.jsonl, frags.jsonl, sessions/, archive/)")
    ap.add_argument("--srv", required=True, help="this server's name on the board (us, eu)")
    ap.add_argument("--sessions", action="append", default=[], help="more folders of sessions (folders or .tar.gz)")
    ap.add_argument("--duels", default=None, help="duels.jsonl (default <data>/duels.jsonl)")
    ap.add_argument("--frags", default=None, help="frags.jsonl (default <data>/frags.jsonl)")
    ap.add_argument("--out", default=None, help="where the summaries go (default <data>/games)")
    ap.add_argument("--win", default=None, help="the win-chance table (default sim/win_chance.json beside this tool)")
    ap.add_argument("--mind", action="append", default=None, help="mind logs (plugins/mindlog.py); default: the data folder's mind.jsonl and its rotated mind.<date-time>.jsonl")
    ap.add_argument("--days", type=float, default=7.0, help="games of the last DAYS days only (the servers keep sessions 7 days)")
    ap.add_argument("--all", action="store_true", help="every game, whatever its age (a backfill)")
    ap.add_argument("--redo", action="store_true", help="write the summaries again")
    a = ap.parse_args()
    out = a.out or os.path.join(a.data, "games")
    os.makedirs(out, exist_ok=True)
    win_p = a.win
    if not win_p:
        for c in (os.path.join(os.path.dirname(HERE), "sim", "win_chance.json"), os.path.join(HERE, "win_chance.json")):
            if os.path.exists(c):
                win_p = c
                break
    win = WinTable(win_p) if win_p and os.path.exists(win_p) else None
    minds = a.mind if a.mind is not None else sorted(glob.glob(os.path.join(a.data, "mind*.jsonl")))
    lines, _ = R.read_tail(a.duels or os.path.join(a.data, "duels.jsonl"), 0)
    now = time.time()
    games = [d for d in lines if d.get("kind") == "game" and "t" in d and (a.all or now - num(d["t"]) < a.days * 86400.0)]
    if not games:
        print("games: none to do")
        return
    none_p = os.path.join(out, "_none.json")
    try:
        none = set(json.load(open(none_p, encoding="utf-8")))
    except Exception:                                        # noqa: BLE001
        none = set()
    todo = []
    for d in games:
        if d.get("srv") and d["srv"] != a.srv:
            continue
        gid = R.game_id(d, a.srv)
        if not a.redo and (os.path.exists(os.path.join(out, gid + ".json")) or (gid in none and not a.all)):
            continue
        todo.append((gid, d))
    if not todo:
        print("games: {} recent, all done".format(len(games)))
        return
    sessions = find_sessions([os.path.join(a.data, "sessions"), os.path.join(a.data, "archive")] + a.sessions)
    frags, _ = R.read_tail(a.frags or os.path.join(a.data, "frags.jsonl"), 0)
    frags.sort(key=lambda f: num(f.get("t")))
    made = missing = waiting = 0
    for gid, d in todo:
        s = session_for(sessions, d.get("map"), R.game_t0(d))
        g = None
        if s is not None:
            try:
                g = summarise(d, a.srv, s, frags, win, minds)
            except Exception as e:                           # noqa: BLE001 - one broken session must not stop the rest
                print("{}: {} {}".format(gid, type(e).__name__, e))
        if g is None:
            if now - num(d["t"]) > 3600.0 or a.all:
                none.add(gid)
                missing += 1
            else:
                waiting += 1
            continue
        write_atomic(os.path.join(out, gid + ".json"), json.dumps(g, separators=(",", ":")))
        none.discard(gid)
        made += 1
    write_atomic(none_p, json.dumps(sorted(none)))
    print("games: {} written, {} without a session, {} waiting for their session; {} sessions seen".format(
        made, missing, waiting, len(sessions)))


if __name__ == "__main__":
    main()

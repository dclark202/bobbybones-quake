"""The pros' counterplay: tools/counterplay.py's numbers read from the professional players' duel demos, the yardstick
for his.

    python tools/counterplay_pros.py --map bloodrun,aerowalk --json pros.json          (Anaconda Python; no torch)
    python tools/counterplay_pros.py --map bloodrun --limit 20                          a sample

A demo is one player's view: his own health, armor and weapons are in it, the other player's never (only his place while
the server sends him). The true stacks of BOTH players, which counterplay.measure() wants, are therefore taken from the
games of which the archive holds both players' own recordings: the two demos run on the same server clock, so each
player's state is read from his own recording and the two are laid side by side by the server time. Nothing of a hidden
player is estimated. Games with one recording only, and spectators' recordings (they cut between the players), are not
used.

Which demos are two views of one game: data/win_chance/games.jsonl (tools/win_chance.py collect: every demo's score
changes on the game clock under a hash of its file name); two demos of a map with the same changes are tried as a pair
and taken if (1) each follows one player throughout, (2) the two follow different players, (3) their server times
overlap, and (4) where one recording holds the other player's place it is the place the other recording has for him at
that server time (median under 40 units). No names are read or written: a game is known by those hashes.

The trace (see counterplay.py), one sample every --every snapshots of 25 ms (5: 0.125 s, what counterplay.py's own
games have: its simulator frame is 25 ms and it keeps every fifth):
  pos, hp, armor   each player's own player state. Dead (about two seconds in the game, none in the simulator, where a
                   player is back at once): health and armor 0, and his place is where he comes back, as it is in the
                   simulator's traces: measure() takes a life's spawn place from the sample he died on
  has              the rocket launcher, the railgun, the lightning gun in his weapon bits
  alive            health above 0 and not in the dead state; died: alive on the sample before, not on this one
  vis              as the simulator's sight (duel_env: self.visible): the enemy within 4000 units, inside a cone of 55
                   degrees round his view (his own view angles), a clear line through the map from his eye (his own eye
                   height) to 8 units above the enemy's origin; only while both live
  the game         from its start (the map's restart) to the intermission as tools/pro_yardsticks.py reads them,
                   overtimes included, warmup never; the time a timeout stops the clock is cut out, and so is a hole of
                   more than a second in either recording (a shorter one holds the last snapshot); each piece is measured
                   by itself and the counters added
The seats: "he" is the player of a game who died less (its winner by frags; level: the lower client number), "opponent"
the other. "both" is the two seats' counters added: the pros as one player.

Output: --json in the shape counterplay.py writes (maps -> counters + summary, and "all"), with "both" (the pooled
summary), the games and the minutes beside them."""
import argparse
import collections
import contextlib
import glob
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p_ in (HERE, os.path.join(HERE, "demodump"), os.path.join(ROOT, "sim")):
    if p_ not in sys.path:
        sys.path.insert(0, p_)
import counterplay as C

MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure"
SNAP_MS = 25
FILL_MS = 1000                # a hole up to this long holds the last snapshot; a longer one cuts the game in two
MIN_PIECE_S = 20.0            # a piece shorter than this is not measured
SAME_PLACE = 40.0             # units: the median gap between a player's place in the two recordings of one game
BITS = (5, 7, 6)              # the game's weapon numbers: rocket launcher, railgun, lightning gun
SIGHT, FOV_COS = 4000.0, float(np.cos(np.radians(55.0)))


def key_of(path):
    return hashlib.sha1(os.path.basename(path).encode("utf-8", "replace")).hexdigest()[:16]


def groups(mp, cache):
    """the demos of a map that show the same game: lists of files"""
    import pro_yardsticks as Y
    files = {key_of(f): f for f in glob.glob(os.path.join(Y.demo_root(), "demos", mp, "*.dm_*")) if not f.endswith(".part")}
    by = collections.defaultdict(list)
    n = 0
    with open(cache, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("map") != mp or r["k"] not in files:
                continue
            n += 1
            if len(r.get("ev") or []) >= 4:                    # (fewer score changes do not tell two games apart)
                by[tuple((int(round(c * 10)), d) for c, _, d in r["ev"])].append(files[r["k"]])
    return [sorted(v) for _, v in sorted(by.items()) if len(v) >= 2], n


def load(demo, tmp):
    """one recording -> its player's own state on every snapshot of the game, or (None, why)"""
    import events_reader as R
    import pro_yardsticks as Y
    b, js, ev = (os.path.join(tmp, x) for x in ("d.bin", "d.json", "d.events.json"))
    for p in (b, js, ev):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run([Y.EXE, demo, b, js, ev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not (os.path.exists(b) and os.path.exists(js) and os.path.exists(ev)):
        return None, "parser"
    try:
        meta = json.load(open(js, encoding="utf-8", errors="replace"))
        E = R.load(ev)
        d = Y.read_dump(b)
        rec, info = Y.demo_record(b, meta, E)
    finally:
        for p in (b, js, ev):
            if os.path.exists(p):
                os.remove(p)
    if rec is None:
        return None, info.get("why", "not read")
    if not info.get("has_start"):
        return None, "begins in a running game"
    if info.get("cuts") or len(np.unique(rec["client"])) != 1:
        return None, "cuts between players"
    tf = d["time"]
    if len(E["times"]) != len(tf) or (np.diff(tf) < 0).any():
        return None, "times"
    # the snapshots the record kept (the game, he playing), by their time
    keep = np.searchsorted(tf, np.round(rec["t"] * 1000.0).astype(np.int64))
    if keep.max() >= len(tf) or not np.array_equal(tf[keep], np.round(rec["t"] * 1000.0).astype(np.int64)) or (np.diff(keep) <= 0).any():
        return None, "times"
    tm = E["times"][keep]
    if (np.diff(tm) <= 0).any():
        return None, "times"
    PS, ps = d["PS"], d["ps"][keep]
    st = ps[:, PS["stats"]:PS["stats"] + 16]
    alive = np.asarray(rec["alive"], bool)
    wslot, aslot = Y.stat_slots(st, alive)
    bits = st[:, wslot].astype(np.int64)
    cl = rec.get("clock_exact")
    stand = np.zeros(len(tm), bool)                            # the clock stands (a timeout)
    if cl is None or not np.isfinite(cl).all():
        return None, "no game clock"                           # (a timeout could not be told from play)
    stand[1:] = np.diff(cl) <= 1e-4
    ang = ps[:, PS["angles"]:PS["angles"] + 3]
    return dict(tm=tm, client=int(rec["client"][0]), pos=ps[:, PS["origin"]:PS["origin"] + 3].astype(np.float64),
                hp=np.where(alive, np.maximum(st[:, 0], 0.0), 0.0), armor=np.where(alive, np.maximum(st[:, aslot], 0.0), 0.0),
                has=np.stack([(bits >> q) & 1 for q in BITS], 1).astype(bool) & alive[:, None], alive=alive, yaw=ang[:, 1].astype(np.float64),
                pitch=ang[:, 0].astype(np.float64), eye_h=ps[:, PS["viewheight"]].astype(np.float64), stand=stand,
                enemy=np.asarray(rec["enemy"], np.float64), ended=bool(info.get("has_end"))), None


def same_game(a, b):
    """the median gap between b's place as a's recording has it and as his own has it, at the same server times"""
    have = np.isfinite(a["enemy"][:, 0])
    j = np.searchsorted(b["tm"], a["tm"][have])
    ok = j < len(b["tm"])
    ok[ok] &= b["tm"][j[ok]] == a["tm"][have][ok]
    ok[ok] &= b["alive"][j[ok]]
    if ok.sum() < 200:
        return None
    return float(np.median(np.linalg.norm(a["enemy"][have][ok] - b["pos"][j[ok]], axis=1)))


def traces(a, b, world, every):
    """two recordings of one game -> its pieces as traces (the seat order: a, b) and the seconds cut out"""
    step = SNAP_MS * every
    lo, hi = max(a["tm"][0], b["tm"][0]), min(a["tm"][-1], b["tm"][-1])
    grid = np.arange(lo, hi + 1, step, dtype=np.int64)
    if len(grid) < 10:
        return [], 0.0
    good = np.ones(len(grid), bool)
    col = {k: [] for k in ("pos", "hp", "armor", "has", "alive", "yaw", "pitch", "eye_h")}
    for r in (a, b):
        j = np.searchsorted(r["tm"], grid, side="right") - 1
        good &= (j >= 0) & (grid - r["tm"][np.maximum(j, 0)] <= FILL_MS)
        j = np.maximum(j, 0)
        # the clock stands on this sample if it stood on any snapshot since the last sample
        cs = np.concatenate([[0], np.cumsum(r["stand"])])
        good &= (cs[j + 1] - cs[np.maximum(j + 1 - every, 0)]) == 0
        for k in col:
            col[k].append(r[k][j])
    col = {k: np.stack(v, 1) for k, v in col.items()}
    pos, alive = col["pos"], col["alive"]
    for p in (0, 1):                                           # a dead player stands where he comes back (see the top of the file)
        nxt = np.where(alive[:, p], np.arange(len(grid)), len(grid))
        nxt = np.minimum.accumulate(nxt[::-1])[::-1]
        m = ~alive[:, p] & (nxt < len(grid))
        pos[m, p] = pos[nxt[m], p]
    # ---- sight, as the simulator's
    vis = np.zeros((len(grid), 2), bool)
    for p in (0, 1):
        o = 1 - p
        eye = pos[:, p] + np.stack([np.zeros(len(grid)), np.zeros(len(grid)), col["eye_h"][:, p]], 1)
        aim = pos[:, o] + np.array([0.0, 0.0, 8.0])
        to = aim - np.array([0.0, 0.0, 8.0]) - eye             # (the cone is measured to his origin, the line to 8 above it)
        dist = np.linalg.norm(to, axis=1) + 1e-6
        y, pt = np.radians(col["yaw"][:, p]), np.radians(np.clip(col["pitch"][:, p], -89.0, 89.0))
        fwd = np.stack([np.cos(pt) * np.cos(y), np.cos(pt) * np.sin(y), -np.sin(pt)], 1)
        cand = np.nonzero(good & alive.all(1) & ((to * fwd).sum(1) / dist > FOV_COS) & (dist < SIGHT))[0]
        if len(cand):
            vis[cand, p] = (world.lines(eye[cand].astype(np.float32), aim[cand].astype(np.float32), mask=1) >= 0.999) | (dist[cand] < 1.0)
    out, cut = [], 0.0
    edges = np.nonzero(np.diff(np.concatenate([[0], good.astype(np.int8), [0]])))[0]
    for s, e in zip(edges[::2], edges[1::2]):
        if (e - s) * step / 1000.0 < MIN_PIECE_S:
            continue
        al = alive[s:e]
        died = np.zeros(al.shape, bool)
        died[1:] = al[:-1] & ~al[1:]
        out.append(dict(dt=step / 1000.0, pos=pos[s:e], hp=col["hp"][s:e], armor=col["armor"][s:e], has=col["has"][s:e], alive=al, died=died, vis=vis[s:e]))
    kept = sum(len(t["pos"]) for t in out)
    return out, (len(grid) - kept) * step / 1000.0


def flip(c):
    """a game's counters with the two seats changed"""
    out = {k: [c[k][1], c[k][0]] for k in C.KEYS}
    out["trans"], out["lives"] = [c["trans"][1], c["trans"][0]], [c["lives"][1], c["lives"][0]]
    return out


def both(c):
    """the two seats' counters added, in both rows: summary()'s "he" of it is the pros as one player"""
    f = flip(c)
    return C.add(c, f)


def pooled(c):
    return C.summary(both(c))["he"]


def show_both(name, s):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        C.show(name, dict(he=s, opponent=s))
    lines = buf.getvalue().splitlines()
    n = 1 + (len(lines) - 1) // 2
    print(name + ", both seats added")
    print("\n".join(x.replace("  he       ", "  both     ", 1) for x in lines[1:n]))


def entry(c, extra):
    return dict(counters=c, summary=C.summary(c), both=pooled(c), **extra)


def low_priority():
    """below normal if nothing lower was asked for, so that a training run on the same PC keeps its share"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.GetPriorityClass.argtypes = (ctypes.c_void_p,)
        k.GetPriorityClass.restype = ctypes.c_uint32
        k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        if k.GetPriorityClass(k.GetCurrentProcess()) == 0x20:
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:                                          # noqa: BLE001 (not Windows)
        pass


def run_map(a, mp):
    """one map in this process (one qsim World a process)"""
    from qsim import World
    low_priority()
    world = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"))
    world.add_solids()
    gs, n_demos = groups(mp, a.cache)
    if a.limit:
        gs = gs[::max(1, len(gs) // a.limit)][:a.limit]
    tmp = tempfile.mkdtemp(prefix="cppros_", dir=a.tmp or None)
    total, why = None, collections.Counter()
    games = pieces = 0
    secs = cut = 0.0
    gaps, t0 = [], time.time()
    try:
        for g in gs:
            recs = []
            for f in g[:3]:
                try:
                    r, w = load(f, tmp)
                except Exception as e:                           # noqa: BLE001 (a broken demo must not stop the batch)
                    r, w = None, "error " + type(e).__name__
                if r is None:
                    why["a recording: " + w] += 1
                else:
                    recs.append(r)
            pair = None
            for i in range(len(recs)):
                for j in range(i + 1, len(recs)):
                    if pair is None and recs[i]["client"] != recs[j]["client"]:
                        pair = (recs[i], recs[j])
            if pair is None:
                why["no two players' own recordings"] += 1
                continue
            x, y = pair
            gap = [same_game(x, y), same_game(y, x)]
            if None in gap or max(gap) > SAME_PLACE:
                why["not the same game"] += 1
                continue
            trs, c_ = traces(x, y, world, a.every)
            if not trs:
                why["no overlap"] += 1
                continue
            c = None
            for tr in trs:
                c = C.add(c, C.measure(tr))
            deaths = [sum(int(tr["died"][:, p].sum()) for tr in trs) for p in (0, 1)]
            if deaths[0] > deaths[1] or (deaths[0] == deaths[1] and x["client"] > y["client"]):
                c = flip(c)                                      # he: the one who died less
            total = C.add(total, c)
            games += 1
            pieces += len(trs)
            secs += sum(len(tr["pos"]) for tr in trs) * trs[0]["dt"]
            cut += c_
            gaps += gap
            if games % 25 == 0:
                print("{}: {} games of {} groups, {:.0f} s".format(mp, games, len(gs), time.time() - t0), file=sys.stderr, flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if total is None:
        return dict(map=mp, games=0, demos=n_demos, groups=len(gs), left_out=dict(why))
    return dict(map=mp, counters=total, games=games, demos=n_demos, groups=len(gs), pieces=pieces, minutes=round(secs / 60.0, 1),
                cut_minutes=round(cut / 60.0, 2), left_out=dict(why), place_gap_median=round(float(np.median(gaps)), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--every", type=int, default=C.EVERY, help="a sample every this many snapshots of 25 ms (5: counterplay.py's own 0.125 s)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many games a map, spread over the archive (0: all)")
    ap.add_argument("--procs", type=int, default=2, help="maps read at a time (a process a map)")
    ap.add_argument("--cache", default=os.path.join(ROOT, "data", "win_chance", "games.jsonl"), help="tools/win_chance.py collect")
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--parts", default="", help="a folder that keeps each map's counters as it is done; a map found there is not read again")
    ap.add_argument("--json", default="")
    ap.add_argument("--one", default="", help=argparse.SUPPRESS)       # (a child: one map, its result to this file)
    a = ap.parse_args()
    assert os.path.exists(a.cache), "no {}: run `python tools/win_chance.py collect` first".format(a.cache)
    if a.one:
        r = run_map(a, a.map)
        json.dump(r, open(a.one + ".part", "w"))
        os.replace(a.one + ".part", a.one)
        return
    maps = [m for m in (MAPS if a.map == "all" else a.map).split(",") if m]
    tmp = a.parts or tempfile.mkdtemp(prefix="cppros_main_", dir=a.tmp or None)
    os.makedirs(tmp, exist_ok=True)
    res, running, todo, raw = {}, [], list(maps), {}
    env = dict(os.environ, PYTHONFAULTHANDLER="1")
    try:
        while todo or running:
            while todo and len(running) < max(1, a.procs):
                mp = todo.pop(0)
                out = os.path.join(tmp, "{}_{}_{}.json".format(mp, a.every, a.limit))
                if a.parts and os.path.exists(out):
                    raw[mp] = json.load(open(out))
                    continue
                cmd = [sys.executable, os.path.abspath(__file__), "--map", mp, "--every", str(a.every), "--limit", str(a.limit), "--cache", a.cache, "--one", out]
                running.append((mp, out, subprocess.Popen(cmd + (["--tmp", a.tmp] if a.tmp else []), env=env)))
            time.sleep(1.0 if running else 0.0)
            for it in list(running):
                code = it[2].poll()
                if code is None:
                    continue
                running.remove(it)
                if code != 0 or not os.path.exists(it[1]):
                    print("{}: the reader ended with code {}".format(it[0], code), file=sys.stderr, flush=True)
                    continue
                raw[it[0]] = json.load(open(it[1]))
    finally:
        if not a.parts:
            shutil.rmtree(tmp, ignore_errors=True)
    total, tg, tmin = None, 0, 0.0
    for mp in maps:
        r = raw.get(mp)
        if r is None:
            continue
        extra = {k: r[k] for k in ("games", "demos", "groups", "pieces", "minutes", "cut_minutes", "left_out", "place_gap_median") if k in r}
        print("{}: {} games with both players' own recordings ({} demos, {} groups of the same game; left out: {})".format(
            mp, r["games"], r["demos"], r["groups"], r["left_out"]))
        if not r["games"]:
            res[mp] = extra
            continue
        res[mp] = entry(r["counters"], extra)
        print("  {} minutes measured in {} pieces, {} minutes cut out (timeouts, holes); a player's place in the two recordings: {} units apart (median)".format(
            r["minutes"], r["pieces"], r["cut_minutes"], r["place_gap_median"]))
        C.show(mp, res[mp]["summary"])
        show_both(mp, res[mp]["both"])
        total = C.add(total, r["counters"])
        tg += r["games"]
        tmin += r["minutes"]
        sys.stdout.flush()
    if total is not None:
        res["all"] = entry(total, dict(games=tg, minutes=round(tmin, 1)))
        print("all maps: {} games, {} minutes".format(tg, round(tmin, 1)))
        C.show("all maps", res["all"]["summary"])
        show_both("all maps", res["all"]["both"])
    if a.json:
        json.dump(dict(what="the pros' duel demos, games with both players' own recordings; he = the player who died less, both = the seats added",
                       dt=SNAP_MS * a.every / 1000.0, gap=C.GAP, maps=res), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

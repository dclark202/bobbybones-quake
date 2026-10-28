"""Moments of PEOPLE's duels against Bobby for the simulator's pro starts (sim/duel_env.py PRO_START_P with
PEOPLE_START_SHARE), written to data/people_moments/<map>.npz (+ .json), in the format of tools/pro_moments.py's
sim/pro_moments/<map>.npz (the same loader reads both; owner, 2026-10-25: "a variety of in game starts with different
stack, positions and weapons in hand ... sample them from actual moments in the games played, weapon and ammo count in
all ... so he knows that 'rail on campgrounds is good'").

Sources: the 1v1 sessions with a person (plugins/duelbot.py: <UTC>_<map>_human/, a folder or its .tar.gz) of the owner's
local play tests (data/duellive_*/sessions) and of the public servers' archive on this PC (T:/quake-sessions/public and
its us/ and eu/; --sessions adds folders). A session holds BOTH players' truth every frame (frames.csv: b_* Bobby, o_* the
person) and the events (events.jsonl: pickups with the item and the taker, deaths, the game's end-of-game table).

The games: a session's real games are the windows of its end-of-game tables (player_stats, not warmup, not aborted, at
least five minutes played: the window is [end - play_time, end]) and of the servers' duel logs (duels.jsonl, kind "game":
[end - minutes, end]) that fall inside the session's frames; warmup (everyone holds every weapon) is outside every window.
Frames with a test room (drill not "-") are left out. Every --every seconds of a game's clock (5 to 595 s, no overtime) a
frame is a moment if
  - both players are alive and in the game (health over 0, a place), neither within --life seconds of his spawn (the
    game's start is a spawn), neither in a teleporter's step (over 400 units between two frames, half a second each side),
    the two more than 48 units apart;
  - both places stand in the simulator (tools/pro_moments.py's rule: not in a solid, lava or slime, a floor under him).

What a moment holds (seat 0: Bobby, seat 1: the person; the simulator draws which seat is his evenly, as for the pros):
  pos, vel, yaw, pitch, hp, armor (the game's, exact for both), the weapon in hand (the game's), the weapons owned
  (reconstructed: the machine gun and gauntlet at a spawn, every weapon picked up since, every weapon seen in hand since;
  the logged ammunition is not ownership: the game counts ammunition for weapons not held), the ammunition (rocket
  launcher, railgun and lightning gun: the game's own count, logged; the others worked out: a weapon pickup's or a box's
  amount (sim LOADOUTS, ITEM_DEFS), less the fire button's time with it in hand over the weapon's refire time), life
  (seconds since his spawn), score (frags each in this game, from the deaths), est 0 for both (health and armor exact).
  The game: clock, the items: item_left (seconds until each simulator item is back, 0 = there: from the pickups of both
  players since the game's start, each down for the simulator's respawn time), item_who (0 / 1 the seat that took it,
  -1 there), item_unsure (all False: both players' pickups are logged; a pickup more than PICK_R units from every
  simulator item of its class is a dropped weapon and leaves the map's items as they were).
  Weighting (for MOMENT_WEIGHTED): pre_wp [M, 2] (the seat picks up a weapon he does not own within --pre seconds),
  pre_big [M, 2] (... the mega, the red or a yellow armor), key_held [M, 2] (the seat owns the map's key weapon: --key,
  default railgun on Campgrounds, lightning gun on Hektik), weight = 1 + W_WP * any(pre_wp) + W_BIG * any(pre_big) +
  W_KEY * any(key_held) (--w-wp, --w-big, --w-key).
  demo: the game's number in this file, demo_kind "people", src 0 local play test / 1 public server.

No key, name, Steam id or address is read into the output (the session's names are not kept either).

    python tools/people_moments.py --map campgrounds [--every 4] [--cap 4000] [--seed 1] [--out data/people_moments]

One map a process (one simulator World a process).
"""
import argparse
import calendar
import csv
import glob
import io
import json
import os
import re
import sys
import tarfile
import time
from collections import Counter

for k_, v_ in (("OPENBLAS_NUM_THREADS", "1"), ("OMP_NUM_THREADS", "1"), ("ITEM_DROP", "1"), ("AMMO_PACKS", "0"),
               ("SOLIDS", "1"), ("LAVA", "1"), ("SHOT_MASK", "1"), ("WALK_FIX", "1")):
    os.environ.setdefault(k_, v_)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
sys.path.insert(0, SIM)

VERSION = 1
SESS_RE = re.compile(r"^(\d{8}-\d{6})_([a-z0-9_]+)_(human|spar|ffa)(?:\.tar\.gz)?$")
QLN = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}
DEF_DIRS = [os.path.join(ROOT, "data", "duellive_*", "sessions"), "T:/quake-sessions/public", "T:/quake-sessions/public/us",
            "T:/quake-sessions/public/eu"]
DEF_DUELS = [os.path.join(ROOT, "data", "duellive_*", "duels.jsonl"), "T:/quake-sessions/public/duels.jsonl",
             "T:/quake-sessions/public/duels_vultr.jsonl", "T:/quake-sessions/public/us/duels.jsonl",
             "T:/quake-sessions/public/eu/duels.jsonl"]
KEY_DEFAULT = {"campgrounds": ("rg",), "hektik": ("lg",)}
GAME_MIN = 300.0               # an end-of-game table counts from five minutes played (sim/head_data.py DUEL_WINDOW_MIN)
PICK_R = 64.0                  # a pickup to the simulator's item of its class (horizontal, each axis; the game's reach is 36)
PICK_DZ = 96.0
TELE = 400.0
BIG = ("MH", "RA", "YA")
NEED = ["t", "drill"] + ["{}_{}".format(p, c) for p in "bo" for c in ("x", "y", "z", "vx", "vy", "vz", "pitch", "yaw", "health",
                                                                       "armor", "weapon", "ammo_rl", "ammo_rg", "ammo_lg", "fire")]


def low_priority():
    try:
        import ctypes
        k_ = ctypes.windll.kernel32
        k_.GetCurrentProcess.restype = ctypes.c_void_p
        k_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k_.SetPriorityClass(k_.GetCurrentProcess(), 0x4000)
    except Exception:                                          # noqa: BLE001
        pass


# ---------------------------------------------------------------------- sessions (as tools/game_summary.py reads them)
class Session:
    def __init__(self, path, src):
        self.path, self.src = path, src
        m = SESS_RE.match(os.path.basename(path))
        self.kind, self.map = m.group(3), m.group(2)
        self.start = float(calendar.timegm(time.strptime(m.group(1), "%Y%m%d-%H%M%S")))
        self.tar = path.endswith(".tar.gz")
        self._tf = None

    def read_all(self, names):
        out = {}
        if not self.tar:
            for n in names:
                p = os.path.join(self.path, n)
                if os.path.exists(p):
                    with open(p, encoding="utf-8", errors="replace") as f:
                        out[n] = f.read()
            return out
        with tarfile.open(self.path, "r:gz") as tf:
            for m in tf:
                b = os.path.basename(m.name)
                if m.isfile() and b in names and b not in out:
                    out[b] = tf.extractfile(m).read().decode("utf-8", "replace")
        return out


def find_sessions(dirs, mapn):
    out = {}
    for pat in dirs:
        for d in sorted(glob.glob(pat)):
            if not os.path.isdir(d):
                continue
            src = 0 if "duellive_" in d.replace("\\", "/") else 1
            for n in os.listdir(d):
                m = SESS_RE.match(n)
                if not m or m.group(3) != "human" or m.group(2) != mapn:
                    continue
                key = n[:-7] if n.endswith(".tar.gz") else n
                p = os.path.join(d, n)
                if key in out and not out[key].tar:
                    continue                                 # (a folder before its packed copy)
                if n.endswith(".tar.gz") or os.path.isdir(p):
                    out[key] = Session(p, src)
    return sorted(out.values(), key=lambda s: s.start)


def duel_windows(paths, mapn):
    """[(t0, t1)] of the servers' duel logs' real games on this map (kind "game")"""
    w = []
    for pat in paths:
        for f in glob.glob(pat):
            try:
                lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for raw in lines:
                try:
                    d = json.loads(raw)
                    if d.get("kind") != "game" or d.get("map") != mapn:
                        continue
                    t1 = float(d["t"])
                    t0 = float(d["t0"]) if d.get("t0") else t1 - 60.0 * float(d.get("minutes") or 0.0)
                except (ValueError, TypeError, KeyError):
                    continue
                if t1 - t0 >= 60.0:
                    w.append((t0, t1))
    return sorted(set((round(a, 2), round(b, 2)) for a, b in w))


def games_of(events, dw, f0, f1):
    """a session's real games: [(t0, t1)] from its end-of-game tables, else the duel logs' windows inside its frames"""
    g = []
    for e in events:
        if e.get("event") == "player_stats" and not e.get("warmup") and not e.get("aborted") and float(e.get("play_time") or 0) >= GAME_MIN:
            t1 = float(e["t"])
            t0 = t1 - float(e["play_time"])
            if not any(abs(x[1] - t1) < 5 for x in g):
                g.append((t0, t1))
    for t0, t1 in dw:
        if t1 < f0 or t0 > f1:
            continue
        if any(min(t1, b) - max(t0, a) > 0.5 * (t1 - t0) for a, b in g):
            continue                                         # (the same game)
        if t0 < f0 - 5.0:
            t0 = None                                        # (the session began after the game had begun: its clock is not known)
        if t0 is not None:
            g.append((t0, min(t1, f1)))
    return sorted(g)


# ---------------------------------------------------------------------- the map (the simulator's items, its World)
class MapInfo:
    def __init__(self, mapn):
        import duel_env as E
        self.E = E
        bsp = os.path.join(ROOT, "data", "maps", mapn + ".bsp")
        self.env = E.DuelEnv(bsp, n_matches=1, seed=0, loadout="mg")
        self.w = self.env.w
        ents = [e for e in self.w.entities if e.get("classname") in E.ITEM_DEFS and "origin" in e]
        self.cls = [e["classname"] for e in ents]
        self.pos = self.env.item_pos.copy()
        self.idef = self.env.item_def
        self.nI = len(self.cls)
        self.lab = [d[4] for d in self.idef]
        self.resp = np.array([float(d[2]) for d in self.idef], np.float32)
        self.weapons = set(int(x) for x in self.env.map_weapons)

    def stands(self, p, ground):
        """tools/pro_moments.py MapInfo.stands: the place (nudged up out of the floor) or None"""
        E, w = self.E, self.w
        p = np.asarray(p, np.float32).copy()
        for dz in (0.0, 1.0, 2.0, 4.0):
            q = p + np.array([0, 0, dz], np.float32)
            if not w.trace(q, q, E.MINS, E.MAXS)["startsolid"]:
                p = q
                break
        else:
            return None
        if w.cluster(p) < 0:
            return None
        cc = w.contents_n(np.stack([p + np.array([0, 0, E.MINS[2] + 1.0], np.float32), p, p + np.array([0, 0, 26.0], np.float32)]))
        if ((cc & (E.C_LAVA | E.C_SLIME)) != 0).any():
            return None
        t = w.trace(p, p - np.array([0, 0, 24.0 if ground else 2000.0], np.float32), E.MINS, E.MAXS)
        if t["fraction"] >= 1.0:
            return None
        return p

    def item_of(self, cls, p):
        """the simulator item of class cls nearest p, or -1 (none within PICK_R: a dropped weapon)"""
        best, bd = -1, 1e9
        for j in range(self.nI):
            if self.cls[j] != cls:
                continue
            d = np.abs(self.pos[j] - p)
            if d[0] <= PICK_R and d[1] <= PICK_R and d[2] <= PICK_DZ and float(d.sum()) < bd:
                best, bd = j, float(d.sum())
        return best


def pitch180(p):
    p = np.asarray(p, np.float32)
    return ((p + 180.0) % 360.0) - 180.0


# ---------------------------------------------------------------------- one session
def read_frames(txt):
    rd = csv.reader(io.StringIO(txt))
    head = next(rd, None) or []
    ix = {c: i for i, c in enumerate(head)}
    if any(c not in ix for c in NEED):
        return None
    cols = {c: [] for c in NEED}
    n = len(head)
    for r in rd:
        if len(r) != n:
            continue
        try:
            vals = [float(r[ix[c]]) if c != "drill" else (r[ix[c]] in ("-", "")) for c in NEED]
        except ValueError:
            continue
        for c, v in zip(NEED, vals):
            cols[c].append(v)
    F = {c: np.asarray(v, np.float64 if c == "t" else np.float32) for c, v in cols.items()}
    F["drill"] = np.asarray(cols["drill"], bool)              # (True: real play, no test room)
    return F


def one_session(MI, sess, dw, every, life_s, pre_s, keyw, rng, counts):
    E = MI.E
    W, NWp = E.WEAPONS, len(E.WEAPONS)
    LD = E.LOADOUTS["all"][1]
    txt = sess.read_all(("meta.json", "events.jsonl", "frames.csv"))
    if "frames.csv" not in txt or "events.jsonl" not in txt:
        counts["sessions without frames or events"] += 1
        return []
    try:
        meta = json.loads(txt.get("meta.json") or "{}")
    except ValueError:
        meta = {}
    if meta.get("opponent") not in (None, "human") or meta.get("kind") == "ffa":
        counts["sessions not 1v1 with a person"] += 1
        return []
    ev = []
    for raw in txt["events.jsonl"].splitlines():
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if isinstance(e, dict) and "t" in e:
            ev.append(e)
    F = read_frames(txt["frames.csv"])
    del txt
    if F is None or len(F["t"]) < 400:
        counts["sessions too short or an old layout"] += 1
        return []
    T = F["t"]
    games = games_of(ev, dw, float(T[0]), float(T[-1]))
    if not games:
        counts["sessions without a real game"] += 1
        return []
    counts["sessions with a real game"] += 1
    picks = sorted((float(e["t"]), e.get("item"), 0 if e.get("by") == "bobby" else 1) for e in ev
                   if e.get("event") == "pickup" and e.get("by") in ("bobby", "opp") and e.get("item") in E.ITEM_DEFS)
    deaths = sorted((float(e["t"]), 0 if e.get("who") == "bobby" else 1) for e in ev
                    if e.get("event") == "death" and e.get("who") in ("bobby", "opp") and not e.get("drill"))
    P = {s: dict(pos=np.stack([F[p + "_x"], F[p + "_y"], F[p + "_z"]], 1), vel=np.stack([F[p + "_vx"], F[p + "_vy"], F[p + "_vz"]], 1))
         for s, p in enumerate("bo")}
    for s, p in enumerate("bo"):
        P[s]["alive"] = (F[p + "_health"] > 0) & (np.abs(P[s]["pos"]).sum(1) > 0)
        st = np.zeros(len(T))
        st[1:] = np.linalg.norm(np.diff(P[s]["pos"], axis=0), axis=1)
        P[s]["step"] = np.where(P[s]["alive"] & np.concatenate([[False], P[s]["alive"][:-1]]), st, 0.0)
    out = []
    for gi, (t0, t1) in enumerate(games):
        counts["games"] += 1
        a, b = np.searchsorted(T, t0), np.searchsorted(T, t1, side="right")
        if b - a < 400:
            counts["games without frames"] += 1
            continue
        if (T[a] - t0) > 5.0:
            counts["games whose first seconds are missing"] += 1
            continue
        idx = np.arange(a, b)
        tele = np.zeros(len(T), bool)
        for f in np.nonzero((P[0]["step"][idx] > TELE) | (P[1]["step"][idx] > TELE))[0] + a:
            tele[max(a, f - 20):min(b, f + 21)] = True
        gp = [x for x in picks if t0 <= x[0] <= t1]
        gd = [x for x in deaths if t0 <= x[0] <= t1]
        # the state run frame by frame: weapons owned, ammunition, spawn times
        has = np.zeros((2, NWp), bool)
        am = np.zeros((2, NWp), np.float32)
        born = np.full(2, t0)
        was = np.array([True, True])

        def spawn(s, t_):
            has[s] = False
            has[s, E.MG] = has[s, E.G] = True
            am[s] = 0.0
            am[s, E.MG] = LD[E.MG]
            born[s] = t_
        spawn(0, t0)
        spawn(1, t0)
        takes = []                                           # (t, simulator item, seat)
        pk = 0
        marks = np.arange(float(rng.uniform(0, every)) + 5.0, min(595.0, t1 - t0 - 1.0), every) + t0
        mi = 0
        for f in idx:
            t_ = float(T[f])
            for s, p in enumerate("bo"):
                al = bool(P[s]["alive"][f])
                if al and not was[s]:
                    spawn(s, t_)
                was[s] = al
            while pk < len(gp) and gp[pk][0] <= t_:
                _, cls, s = gp[pk]
                pk += 1
                kd, val, _, cap, lab = E.ITEM_DEFS[cls]
                if kd == "wp":
                    if not has[s, val]:
                        am[s, val] = max(am[s, val], float(LD.get(val, 10)))
                    else:
                        am[s, val] = min(float(E.AMMO_MAX[val]), am[s, val] + float(LD.get(val, 10)) * 0.5)
                    has[s, val] = True
                elif kd == "am":
                    am[s, val] = min(float(E.AMMO_MAX[val]), am[s, val] + float(cap))
                j = MI.item_of(cls, P[s]["pos"][f])
                if j >= 0:
                    takes.append((t_, j, s))
                else:
                    counts["pickups away from the map's items (drops)"] += 1
            for s, p in enumerate("bo"):
                if not P[s]["alive"][f]:
                    continue
                wn = QLN.get(int(F[p + "_weapon"][f]), "mg")
                w_ = W.index(wn)
                if not has[s, w_]:
                    has[s, w_] = True
                    am[s, w_] = max(am[s, w_], 1.0 if w_ != E.G else 0.0)
                for nm in ("rl", "rg", "lg"):
                    k_ = W.index(nm)
                    if has[s, k_]:
                        am[s, k_] = max(0.0, float(F["{}_ammo_{}".format(p, nm)][f]))
                if F[p + "_fire"][f] > 0 and wn in ("mg", "sg", "gl", "pg", "hmg"):
                    am[s, w_] = max(0.0 if w_ != E.MG else 0.0, am[s, w_] - float(E.DT) / float(E.W_REFIRE[w_]))
            if mi >= len(marks) or t_ < marks[mi]:
                continue
            while mi < len(marks) and marks[mi] <= t_:
                mi += 1
            counts["frames looked at"] += 1
            why = None
            if not F["drill"][f]:
                why = "a test room"
            elif not (P[0]["alive"][f] and P[1]["alive"][f]):
                why = "a player dead"
            elif t_ - born[0] < life_s or t_ - born[1] < life_s:
                why = "within the seconds after a spawn"
            elif tele[f]:
                why = "a teleporter step"
            if why:
                counts[why] += 1
                continue
            pa = MI.stands(P[0]["pos"][f], abs(float(P[0]["vel"][f][2])) < 1.0)
            pb = MI.stands(P[1]["pos"][f], abs(float(P[1]["vel"][f][2])) < 1.0)
            if pa is None or pb is None:
                counts["a place the simulator does not hold"] += 1
                continue
            if np.linalg.norm(pa - pb) < 48.0:
                counts["the two within 48 units"] += 1
                continue
            left = np.zeros(MI.nI, np.float32)
            who = np.full(MI.nI, -1, np.int8)
            for tk, j, s in takes:                           # (in time order: the last take of an item counts)
                l_ = float(MI.resp[j]) - (t_ - tk)
                if l_ > 0:
                    left[j], who[j] = l_, s
                else:
                    left[j], who[j] = 0.0, -1
            sc = [sum(1 for x in gd if x[0] <= t_ and x[1] == 1), sum(1 for x in gd if x[0] <= t_ and x[1] == 0)]
            hs = has.copy()
            hs[:, E.G] = True
            aa = np.where(hs, am, 0.0).astype(np.float32)
            aa[:, E.G] = 0.0
            pre_wp = np.zeros(2, bool)
            pre_big = np.zeros(2, bool)
            for tp, cls, s in gp:
                if tp <= t_ or tp > t_ + pre_s:
                    continue
                if any(x[0] <= tp and x[1] == s and x[0] > t_ for x in gd):
                    continue                                 # (he died first: another life's pickup)
                kd, val, _, _, lab = E.ITEM_DEFS[cls]
                if kd == "wp" and not hs[s, val]:
                    pre_wp[s] = True
                if lab in BIG:
                    pre_big[s] = True
            key_held = np.array([any(hs[s, W.index(k)] for k in keyw) for s in range(2)], bool)
            out.append(dict(
                clock=t_ - t0, score=tuple(sc), pos=(pa, pb), vel=(P[0]["vel"][f], P[1]["vel"][f]),
                yaw=(float(F["b_yaw"][f]), float(F["o_yaw"][f])), pitch=(float(F["b_pitch"][f]), float(F["o_pitch"][f])),
                hp=(float(F["b_health"][f]), float(F["o_health"][f])), armor=(float(F["b_armor"][f]), float(F["o_armor"][f])),
                has=(hs[0].copy(), hs[1].copy()), ammo=(aa[0], aa[1]),
                weapon=tuple(W.index(QLN.get(int(F[p + "_weapon"][f]), "mg")) for p in "bo"),
                life=(t_ - born[0], t_ - born[1]), left=left, who=who, pre_wp=pre_wp, pre_big=pre_big, key_held=key_held,
                src=sess.src))
            counts["moments"] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--sessions", action="append", default=[], help="more folders of sessions (folders or .tar.gz)")
    ap.add_argument("--no-default-dirs", action="store_true")
    ap.add_argument("--every", type=float, default=4.0)
    ap.add_argument("--life", type=float, default=2.0)
    ap.add_argument("--pre", type=float, default=6.0, help="seconds ahead for pre_wp / pre_big")
    ap.add_argument("--key", default=None, help="the map's key weapons, e.g. rg,lg (default: KEY_DEFAULT)")
    ap.add_argument("--w-wp", type=float, default=2.0)
    ap.add_argument("--w-big", type=float, default=1.0)
    ap.add_argument("--w-key", type=float, default=1.0)
    ap.add_argument("--cap", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-sessions", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "people_moments"))
    a = ap.parse_args()
    low_priority()
    rng = np.random.default_rng(a.seed)
    dirs = ([] if a.no_default_dirs else DEF_DIRS) + a.sessions
    sess = find_sessions(dirs, a.map)
    if a.max_sessions:
        sess = sess[:a.max_sessions]
    dw = duel_windows(DEF_DUELS, a.map)
    keyw = tuple(x.strip() for x in a.key.split(",") if x.strip()) if a.key is not None else KEY_DEFAULT.get(a.map, ())
    MI = MapInfo(a.map)
    keyw = tuple(k for k in keyw if MI.E.WEAPONS.index(k) in MI.weapons)
    counts = Counter()
    rows, gid = [], []
    t0 = time.time()
    ng = 0
    for ns, s in enumerate(sess):
        try:
            ms = one_session(MI, s, dw, a.every, a.life, a.pre, keyw, rng, counts)
        except Exception as e:                               # noqa: BLE001 (a broken session must not stop the map)
            counts["error"] += 1
            print("error", ns, type(e).__name__, str(e)[:160], flush=True)
            ms = []
        counts["sessions"] += 1
        counts["sessions local" if s.src == 0 else "sessions public"] += 1
        counts["moments local" if s.src == 0 else "moments public"] += len(ms)
        gs = sorted(set(round(m["clock"] - 0.0, 0) for m in ()))  # noqa: F841 (games are numbered by session below)
        for m in ms:
            rows.append(m)
            gid.append(ng)
        ng += 1
        if ns % 10 == 0:
            print("{} {}/{} moments {} {:.0f}s".format(a.map, ns + 1, len(sess), len(rows), time.time() - t0), flush=True)
    if len(rows) > a.cap:
        sel = np.sort(rng.choice(len(rows), a.cap, replace=False))
        rows = [rows[i] for i in sel]
        gid = [gid[i] for i in sel]
    os.makedirs(a.out, exist_ok=True)
    M = len(rows)

    def st(k, dt=np.float32):
        return np.array([[r[k][0], r[k][1]] for r in rows], dt).reshape(M, 2)

    def st2(k, dt, w):
        return np.array([np.stack(r[k]) for r in rows], dt).reshape(M, 2, w)
    pre_wp = np.array([r["pre_wp"] for r in rows], bool).reshape(M, 2)
    pre_big = np.array([r["pre_big"] for r in rows], bool).reshape(M, 2)
    key_held = np.array([r["key_held"] for r in rows], bool).reshape(M, 2)
    weight = (1.0 + a.w_wp * pre_wp.any(1) + a.w_big * pre_big.any(1) + a.w_key * key_held.any(1)).astype(np.float32)
    res = dict(
        version=np.int32(VERSION), clock=np.array([r["clock"] for r in rows], np.float32),
        score=st("score", np.int16), pos=st2("pos", np.float32, 3), vel=st2("vel", np.float32, 3),
        yaw=st("yaw"), pitch=pitch180(st("pitch")), hp=st("hp"), armor=st("armor"),
        has=st2("has", bool, 9), ammo=np.rint(st2("ammo", np.float32, 9)).astype(np.int16),
        weapon=st("weapon", np.int8), life=st("life"), est=np.zeros((M, 2), np.int8),
        item_left=np.array([r["left"] for r in rows], np.float16).reshape(M, MI.nI),
        item_who=np.array([r["who"] for r in rows], np.int8).reshape(M, MI.nI),
        item_unsure=np.zeros((M, MI.nI), bool),
        item_pos=MI.pos.astype(np.float32), item_cls=np.array(MI.cls),
        demo=np.array(gid, np.int16), demo_kind=np.array(["people"] * M), src=np.array([r["src"] for r in rows], np.int8),
        pre_wp=pre_wp, pre_big=pre_big, key_held=key_held, weight=weight)
    np.savez_compressed(os.path.join(a.out, a.map + ".npz"), **res)
    meta = dict(map=a.map, version=VERSION, moments=M, every=a.every, life=a.life, pre=a.pre, key=list(keyw),
                weights=dict(wp=a.w_wp, big=a.w_big, key=a.w_key), sessions=len(sess), counts=dict(counts),
                seconds=round(time.time() - t0))
    json.dump(meta, open(os.path.join(a.out, a.map + ".json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()

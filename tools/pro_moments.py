"""Moments of the pros' duels for the simulator's pro starts (sim/duel_env.py PRO_START_P), written to
sim/pro_moments/<map>.npz.

From the pro demos (the folder named in data/demo_root.txt, demos/<map>/*.dm_91, .dm_90, then .dm_73), parsed with
tools/demodump: every --every seconds of a demo's live game (the clock of tools/pro_yardsticks.py: not warmup, not a
timeout, before 10:00) a frame is a moment if
  - both players are in play: the demo's player alive (pm_type normal) and the enemy's entity sent and not dead; neither
    within --life seconds of his respawn (the enemy: of his death, plus the respawn delay), neither in a teleporter's
    step (a jump of over 400 units between two frames within 0.5 s), no cut of the followed player within 1 s;
  - no powerup on anyone, and the demo's map has no powerup item at all (the owner's rule: no powerups);
  - every map item of the simulator's list (the run's switches: ITEM_DROP=1, AMMO_PACKS=0) is matched by class and
    place to the demo's item entities (an old layout, a big item missing: the demo is skipped);
  - the state of every mega, red and yellow armor is known at that frame (see "items" below); a small item that is not
    known is taken as there and counted (`item_unsure`);
  - both places stand in the simulator: the player's box not in a solid, not in lava or slime, inside the map, a floor
    under a player on the ground within 24 units, some floor under one in the air within 2000 units.

Most demos of today's format are a spectator's: the followed player is one of the two, now and then the other (a cut).
"The demo's player" below is the one followed at that frame; a player's stack while he is not followed is worked out
from where it was last read (his last stretch followed) or from his respawn.

What a moment holds, a row a player (seat 0: the demo's player, seat 1: his enemy):
  pos, vel (the game's), yaw, pitch (the game's: looking down is positive, as the simulator's), hp, armor, has (9 weapons in
  the simulator's order), ammo (9), weapon (in hand), life (seconds since his respawn), score (frags; the enemy's as
  tools/pro_yardsticks.py reads it, checked by the rank), and est (0: read from the demo's player state, exact; 1: the
  enemy's stack, which no demo holds: worked out, see below).
  The game: clock (seconds), the items: item_left (seconds until each simulator item is back, 0 = there), item_who
  (who took it: 0, 1 the seat, -1 nobody or not known), item_unsure (a small item whose state is a guess: taken as there).

The demo's player is exact (his player state). The enemy's place, speed, view and weapon in hand are the game's (his
entity); his stack is not in any demo (a player's demo has his own stats only; the pain sound's band is all that is
sent of the other's health). It is worked out frame by frame from his last respawn (SPAWN_HP 125, no armor, the machine
gun with 100 bullets and the gauntlet):
  + his pickups: the ItemPickup events of his entity while the server sent him (exact), and every item of the map that
    went down when the demo's player did not take it (by the items' story, below) at the time worked out for it;
  - the followed player's hits (his hit counter, by the weapon in his hand: DMG_HIT per hit times DMG_SCALE, 0.6: fitted on
    Blood Run so that the pain bands heard fall as often above the worked-out health as below it), armor soaking ARMOR_ABSORB of
    each as the game does, the health kept above 0 while he lives; the pain sound's band (event 53 of his entity: 20,
    40, 60, 80 for under 25, 50, 75 and above) clamps the health into its band whenever it is heard;
  - a health or armor over 100 ticks down 1 a second, as the game's;
  weapons: those seen in his hand and taken since the respawn, ammunition: the pickup's (LOADOUTS["all"]) and the
  boxes', less one for each WeaponFired event of his while sent (at least one in the weapon in hand).

Items (per simulator item, from the demo's item entity matched to it): the server sends an item while it is there and
in the PVS of the followed player's eye (sim/pvs.py), so a frame with the item's place in the PVS says "there" (sent)
or "gone" (not sent). The exact takes are the ItemPickup events (the demo's player's own: always; the enemy's: while he
is sent), each down for the item's respawn time (the simulator's, item_def; the ItemRespawn event moves its end when it
is sent). A run of "gone" frames no exact take explains was the enemy's take, at a time between the last "there" before
it and its first "gone", and so that the item is back by the first "there" after (respawn time later): the middle of
that window if it is under ITEM_WIN seconds, else the run is not known. An item is known at a frame if it is inside a
known down time, or "there" frames lie before and after with less than its respawn time between them, or the frame is
within ITEM_SEEN seconds after a "there" and before any "gone".

    python tools/pro_moments.py --map bloodrun [--demos 150] [--every 4] [--cap 4000] [--seed 1]

One map a process (one simulator World a process). No player names are read or written: a demo is kept as a number
and a short hash of its file name.
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

for k_, v_ in (("OPENBLAS_NUM_THREADS", "1"), ("OMP_NUM_THREADS", "1"), ("ITEM_DROP", "1"), ("AMMO_PACKS", "0"),
               ("SOLIDS", "1"), ("LAVA", "1"), ("SHOT_MASK", "1"), ("WALK_FIX", "1")):
    os.environ.setdefault(k_, v_)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
sys.path.insert(0, SIM)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "demodump"))
import demo_reader as D  # noqa: E402
import events_reader as R  # noqa: E402
import pro_yardsticks as PY  # noqa: E402

EXE_CANDS = (os.path.join(ROOT, "tools", "demodump", "demodump.exe"),
             os.path.join(os.path.expanduser("~"), "ql-bot", "tools", "demodump", "demodump.exe"))
VERSION = 1
QL2SIM = {"ItemHealthSmall": "item_health_small", "ItemHealth": "item_health", "ItemHealthLarge": "item_health_large",
          "ItemHealthMega": "item_health_mega", "ItemArmorShard": "item_armor_shard", "ItemArmorJacket": "item_armor_jacket",
          "ItemArmorCombat": "item_armor_combat", "ItemArmorBody": "item_armor_body", "WeaponRocketLauncher": "weapon_rocketlauncher",
          "WeaponRailgun": "weapon_railgun", "WeaponLightningGun": "weapon_lightning", "WeaponShotgun": "weapon_shotgun",
          "WeaponGrenadeLauncher": "weapon_grenadelauncher", "WeaponPlasmaGun": "weapon_plasmagun", "WeaponHMG": "weapon_hmg",
          "AmmoRockets": "ammo_rockets", "AmmoSlugs": "ammo_slugs", "AmmoLightning": "ammo_lightning", "AmmoBullets": "ammo_bullets",
          "AmmoShells": "ammo_shells", "AmmoGrenades": "ammo_grenades", "AmmoCells": "ammo_cells", "AmmoHMG": "ammo_hmg",
          "AmmoPack": "ammo_pack"}
POWERUPS = ("ItemQuad", "ItemRegen", "ItemHaste", "ItemInvis", "ItemEnviro", "ItemFlight", "ItemGuard", "ItemScout",
            "ItemDoubler", "ItemAmmoRegen", "HoldableTeleporter", "HoldableMedkit", "HoldableKamikaze", "HoldablePortal",
            "HoldableInvulnerability")
BIG = ("MH", "RA", "YA")
ITEM_R = 48.0                  # a demo item entity to the simulator's item of its class
ITEM_WIN = 2.0                 # an unseen take's window is narrower than this: its middle is taken
ITEM_SEEN = 1.0                # seconds after a "there" that it still counts as there with nothing else known
EF_DEAD, EF_NODRAW = 0x1, 0x80
EV_PAIN = 53                   # Quake Live's pain event on a player entity (the parm: the band, 20 40 60 80)
PAIN_BAND = {20: (1.0, 24.0), 40: (25.0, 49.0), 60: (50.0, 74.0), 80: (75.0, 200.0)}
DMG_HIT = np.array([80, 80, 6, 5, 5, 80, 20, 8, 50], np.float32)    # a hit's damage by weapon (rl rg lg mg sg gl pg hmg g)
DMG_SCALE = float(os.environ.get("PM_DMG_SCALE") or 0.6)     # (fitted on Blood Run, 20 demos: as many pain bands heard over the worked-out health as under it)
RESPAWN_S = 2.0                # the enemy's respawn delay (the game's, about): his life counts from death + this
TELE = 400.0
RESP_SEEN = {}


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def low_priority():
    try:
        import ctypes
        k_ = ctypes.windll.kernel32
        k_.GetCurrentProcess.restype = ctypes.c_void_p
        k_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k_.SetPriorityClass(k_.GetCurrentProcess(), 0x4000)
    except Exception:                                          # noqa: BLE001
        pass


class MapInfo:
    """the simulator's items of the map (as a run makes them), its World, the PVS"""

    def __init__(self, mapn):
        import duel_env as E
        import pvs
        self.E = E
        bsp = os.path.join(ROOT, "data", "maps", mapn + ".bsp")
        self.env = E.DuelEnv(bsp, n_matches=1, seed=0, loadout="mg")
        self.w = self.env.w
        self.V = pvs.Vis(bsp)
        ents = [e for e in self.w.entities if e.get("classname") in E.ITEM_DEFS and "origin" in e]
        self.cls = [e["classname"] for e in ents]
        self.pos = self.env.item_pos.copy()
        self.idef = self.env.item_def
        self.nI = len(self.cls)
        self.lab = [d[4] for d in self.idef]
        self.resp = np.array([float(d[2]) for d in self.idef], np.float32)
        self.icl = self.V.box_clusters(self.pos, mins=np.array([-15, -15, -15], np.float32), maxs=np.array([15, 15, 15], np.float32))

    def stands(self, p, ground):
        """the place p is one the simulator can hold a player at (see the module's text); the place, nudged up a little
        out of the floor if it was in it, or None"""
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


def parse(demo, tmp):
    b, js, ev = (os.path.join(tmp, x) for x in ("d.bin", "d.json", "d.events.json"))
    for p in (b, js, ev):
        if os.path.exists(p):
            os.remove(p)
    exe = next((e for e in EXE_CANDS if os.path.exists(e)), EXE_CANDS[0])
    subprocess.run([exe, demo, b, js, ev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not (os.path.exists(b) and os.path.exists(js) and os.path.exists(ev)):
        return None
    try:
        d = D.load(b)
        E = R.load(ev)
        meta = json.load(open(js, encoding="utf-8", errors="replace"))
        rec, info = PY.demo_record(b, meta, E)
    finally:
        for p in (b, js, ev):
            if os.path.exists(p):
                os.remove(p)
    return d, E, rec, info


def story(times, up_obs, dn_obs, takes, resp_ev, R_, t_game0):
    """an item's story with hindsight: (down intervals [(a, b, who)], unknown windows [(a, b)]). times: the frames' server
    seconds; up_obs / dn_obs: bool per frame; takes: [(t, who)] exact; resp_ev: [t] exact returns"""
    downs = []
    for t_, who in sorted(takes):
        b_ = t_ + R_
        r_ = [x for x in resp_ev if t_ + R_ - 1.5 <= x <= t_ + R_ + 1.5]
        if r_:
            b_ = r_[0]
        downs.append((t_, b_, who))

    def covered(t_):
        return any(a - 0.3 <= t_ <= b + 0.3 for a, b, _ in downs)
    tu = times[up_obs]
    td = times[dn_obs]
    unknown = []
    td_free = np.array([x for x in td if not covered(x)])
    k = 0
    while k < len(td_free):
        x0 = td_free[k]
        iu = np.searchsorted(tu, x0)
        U = tu[iu] if iu < len(tu) else np.inf
        L = tu[iu - 1] if iu > 0 else t_game0
        cl = td_free[(td_free >= x0) & (td_free < U)]
        x1 = cl[-1]
        k += len(cl)
        rr = [x for x in resp_ev if x1 < x <= U + 0.05]
        if rr:
            U = min(U, rr[0])
        lo, hi = max(L, x1 - R_), min(x0, U - R_)
        if lo <= hi and hi - lo < ITEM_WIN:
            tk = 0.5 * (lo + hi)
            downs.append((tk, tk + R_, -2))            # (-2: worked out, by the one not followed)
        else:
            unknown.append((L, U))
    return sorted(downs), unknown, tu


def item_at(t, downs, unknown, tu, td, R_):
    """(left seconds, who, known) of an item at server second t"""
    for a, b, who in downs:
        if a <= t < b:
            return b - t, who, True
    for a, b in unknown:
        if a < t < b:
            return 0.0, -1, False
    i = np.searchsorted(tu, t, side="right")
    a = tu[i - 1] if i > 0 else None
    b = tu[i] if i < len(tu) else None
    if a is not None and b is not None and b - a < R_:
        return 0.0, -1, True
    if a is not None and t - a <= ITEM_SEEN:
        j = np.searchsorted(td, a, side="right")
        if j >= len(td) or td[j] > t:
            return 0.0, -1, True
    return 0.0, -1, False


def judge_rows(judge, E, rec, clock, cn, other, clients, dth, eh, ea, ehas, T, own_pw, en, counts, t_game0):
    """(the judge's pro rows, tools/run/pro_judge_rows.py) one row a second of the game's clock, the two players as two fixed
    seats (seat 0 = the lower client number, whoever the demo follows), as tools/run/fit_b.py reads them: the score, health,
    armor, dead, the big weapons owned (the followed player's exact, the other's worked out as above); kept only if the demo
    holds the game to its end (the clock at 599 s or more) with no powerup, no level end counted as anything but a draw. Sets
    judge["rows"], judge["final"] (seat 0, seat 1), judge["sig"] (the frag times: two recordings of one game share it)"""
    ok = np.isfinite(clock)
    if not ok.any() or float(np.nanmax(clock)) < 599.0:
        counts["judge: the game not held to its end"] += 1
        return
    if own_pw[ok].any() or (en["pw"][ok] != 0).any():
        counts["judge: a powerup"] += 1
        return
    c0, c1 = clients
    alive_rec = (np.asarray(rec["alive"], bool)) & (np.asarray(rec["health"]) > 0)
    rows, last_s = [], -1
    for f in np.nonzero(ok & (clock <= 600.5))[0]:
        s_ = int(np.floor(clock[f]))
        if s_ <= last_s or s_ >= 600:                       # (0..599 s: tools/run/fit_b.py reads frame 24,000 as overtime)
            continue
        last_s = s_
        me, op = int(cn[f]), int(other[f])
        sc = {me: int(rec["score"][f]), op: int(rec["enemy_score"][f])}
        dead = {}
        for cl in clients:
            ds_ = np.array(dth[cl])
            j_ = np.searchsorted(ds_, T[f], side="right") - 1
            dead[cl] = bool(j_ >= 0 and T[f] - ds_[j_] < 2.0)          # (from his death to his respawn, about 2 s)
        dead[me] = dead[me] or not bool(alive_rec[f])
        hp = {me: float(rec["health"][f]), op: float(eh[f])}
        ar = {me: float(rec["armor"][f]), op: float(ea[f])}
        hs = {me: rec["owned"][f].astype(bool), op: ehas[f]}
        r_ = [0, 0, s_ / 0.025]
        r_ += [sc[c0], sc[c1], hp[c0], ar[c0], hp[c1], ar[c1], float(dead[c0]), float(dead[c1])]
        r_ += [float(hs[c0][E.RL]), float(hs[c0][E.LG]), float(hs[c0][E.RG]), float(hs[c1][E.RL]), float(hs[c1][E.LG]), float(hs[c1][E.RG])]
        r_ += [0.0, float(sc[c0] - sc[c1])]
        rows.append(r_)
    if len(rows) < 500:
        counts["judge: under 500 seconds of rows"] += 1
        return
    fe_ = int(np.nonzero(ok & (clock <= 600.5))[0][-1])     # (the result: the score at the game's last frame)
    me_, op_ = int(cn[fe_]), int(other[fe_])
    sc_ = {me_: int(rec["score"][fe_]), op_: int(rec["enemy_score"][fe_])}
    rows[-1][3], rows[-1][4], rows[-1][18] = sc_[c0], sc_[c1], float(sc_[c0] - sc_[c1])   # (fit_b reads the result from the last row:
    judge["rows"] = rows                                  #  a frag in the game's last second moves there, under a second early)
    judge["final"] = (sc_[c0], sc_[c1])
    fr = sorted(round(float(t_) - t_game0, 0) for cl in clients for t_ in dth[cl])   # (the deaths on the game's clock)
    judge["sig"] = (int(sc_[c0] + sc_[c1]), tuple(fr[:12]))
    counts["judge: games"] += 1


def one_demo(MI, demo, tmp, every, life_s, rng, counts, judge=None):
    E = MI.E
    out = parse(demo, tmp)
    if out is None:
        counts["parser"] += 1
        return []
    d, EV, rec, info = out
    if rec is None:
        counts["no game"] += 1
        return []
    tm = d["time"].astype(np.int64)
    t_rec = np.rint(rec["t"] * 1000.0).astype(np.int64)
    keep = np.searchsorted(tm, t_rec)
    if (keep >= len(tm)).any() or (tm[np.minimum(keep, len(tm) - 1)] != t_rec).any():
        counts["frames"] += 1
        return []
    N = len(keep)
    T = rec["t"]
    clock = rec["clock"].astype(np.float64)
    if rec.get("clock_exact") is not None:
        clock = np.where(np.isfinite(clock), clock, rec["clock_exact"])
    if not np.isfinite(clock).any():
        counts["no clock"] += 1
        return []
    inv = {v: k for k, v in EV["item_ids"].items()}
    # ---- the demo's map items: entity number -> simulator item
    ents = {}
    for s_, its in enumerate(d["items"]):
        for r in its:
            k = int(r[0])
            e = ents.get(k)
            if e is None:
                ents[k] = e = dict(model=int(r[1]), pos=r[2:5].copy(), moved=False, n=0)
            e["n"] += 1
            if int(r[1]) != e["model"] or np.abs(r[2:5] - e["pos"]).max() > 1.0:
                e["moved"] = True
    names = {k: inv.get(e["model"], "?") for k, e in ents.items()}
    if any(names[k] in POWERUPS for k, e in ents.items() if not e["moved"]):
        counts["powerups on the map"] += 1
        return []
    sim_of = {}
    taken = set()
    for k, e in ents.items():
        if e["moved"] or names[k] not in QL2SIM:
            continue
        c_ = QL2SIM[names[k]]
        cand = [j for j in range(MI.nI) if MI.cls[j] == c_ and j not in taken]
        if not cand:
            if names[k] != "AmmoPack":
                counts["demo items without a simulator item"] += 1
            continue
        dd = [float(np.linalg.norm(MI.pos[j] - e["pos"])) for j in cand]
        j = cand[int(np.argmin(dd))]
        if min(dd) <= ITEM_R:
            sim_of[k] = j
            taken.add(j)
        else:
            counts["demo items without a simulator item"] += 1
    ent_of = {j: k for k, j in sim_of.items()}
    miss = [j for j in range(MI.nI) if j not in ent_of]
    if any(MI.lab[j] in BIG + ("RL", "RG", "LG") for j in miss):
        counts["layout: a big item not matched"] += 1
        return []
    counts["simulator items never seen (taken as there)"] += len(miss)
    # ---- per kept frame: the items sent, the PVS of his eye
    eye = rec["pos"] + np.stack([np.zeros(N), np.zeros(N), rec["eye_h"]], 1)
    ce = MI.V.clusters(eye)
    seen = MI.V.sees(ce[:, None, None], MI.icl[None, :, :]).any(2)       # (N, nI)
    present = np.zeros((N, MI.nI), bool)
    for f, s_ in enumerate(keep):
        for r in d["items"][s_]:
            j = sim_of.get(int(r[0]))
            if j is not None and not (int(r[5]) & EF_NODRAW):
                present[f, j] = True
    counts["item frames sent outside the PVS"] += int((present & ~seen).sum())
    counts["item frames sent in the PVS"] += int((present & seen).sum())
    up_obs = present
    dn_obs = seen & ~present
    remap = np.full(len(tm), -1, np.int64)
    remap[keep] = np.arange(N)
    cn = rec["client"]
    # ---- the enemy's entity per frame
    en = dict(pos=np.full((N, 3), np.nan, np.float32), vel=np.zeros((N, 3), np.float32), ang=np.zeros((N, 3), np.float32),
              wpn=np.full(N, -1, np.int64), ground=np.zeros(N, bool), num=np.full(N, -1, np.int64), pw=np.zeros(N, np.int64))
    for f, s_ in enumerate(keep):
        for r in d["players"][s_]:
            if int(r[0]) < 64 and int(r[0]) != cn[f] and not (int(r[12]) & EF_DEAD):
                en["pos"][f], en["vel"][f], en["ang"][f] = r[2:5], r[5:8], r[8:11]
                q = int(r[11])
                en["wpn"][f] = PY.WEAPONS.index(PY.QLW[q]) if q in PY.QLW else -1
                en["ground"][f] = int(r[13]) != 1023
                en["num"][f] = int(r[0])
                en["pw"][f] = int(r[18])
                break
    own_pw = np.zeros(N, bool)
    pw_ = d["ps"][keep, D.PS["powerups"]:D.PS["powerups"] + 16]
    own_pw = (pw_[:, 1:7] > 0).any(1)                        # (quad, battle suit, haste, invisibility, regeneration, flight)
    clients = sorted(set(int(x) for x in np.unique(cn)) | set(int(x) for x in np.unique(en["num"][en["num"] >= 0])))
    if len(clients) != 2:
        counts["not two players"] += 1
        return []
    other = np.where(cn == clients[0], clients[1], clients[0])          # the enemy of the followed player, per frame
    # ---- exact takes and returns (who: a client number)
    c = EV["c"]
    X = EV["events"]
    takes = {j: [] for j in range(MI.nI)}
    resp_ev = {j: [] for j in range(MI.nI)}
    picks = []                                               # (frame, simulator item, client) of the unfollowed: exact or worked out
    for r in X[X[:, c["event"]] == EV["event_ids"]["ItemPickup"]]:
        s_ = int(r[c["snap"]])
        if not (0 <= s_ < len(tm)) or remap[s_] < 0:
            continue
        f = int(remap[s_])
        src, num = int(r[c["source"]]), int(r[c["number"]])
        who = int(cn[f]) if src == 2 else num if (src == 1 and num == other[f]) else -1
        if who < 0:
            continue
        nm = inv.get(int(r[c["eventParm"]]), "")
        if nm not in QL2SIM:
            continue
        p = np.array([r[c["pos_trBase_0"]], r[c["pos_trBase_1"]], r[c["pos_trBase_2"]]], np.float32)
        cand = [j for j in range(MI.nI) if MI.cls[j] == QL2SIM[nm]]
        if not cand:
            continue
        dd = [float(np.linalg.norm(MI.pos[j][:2] - p[:2])) + 0.5 * abs(float(MI.pos[j][2] - p[2])) for j in cand]
        if min(dd) > 120.0:
            continue
        j = cand[int(np.argmin(dd))]
        takes[j].append((float(T[f]), who))
        counts["exact takes"] += 1
        if who != cn[f]:
            picks.append((f, j, who))
    for r in X[(X[:, c["event"]] == EV["event_ids"]["ItemRespawn"])]:
        s_ = int(r[c["snap"]])
        j = sim_of.get(int(r[c["number"]]))
        if j is not None and 0 <= s_ < len(tm) and remap[s_] >= 0:
            resp_ev[j].append(float(T[int(remap[s_])]))
    for j in range(MI.nI):                                   # (a check: the game's respawn times, from exact takes to returns)
        for x, _ in takes[j]:
            r_ = [y - x for y in resp_ev[j] if x < y <= x + 60.0]
            if r_:
                RESP_SEEN.setdefault(str(MI.lab[j] or MI.cls[j]), []).append(round(min(r_), 2))
    g0 = np.nonzero(np.isfinite(clock))[0]
    t_game0 = float(T[g0[0]] - clock[g0[0]])
    ST = []
    for j in range(MI.nI):
        downs, unknown, tu = story(T, up_obs[:, j], dn_obs[:, j], takes[j], sorted(resp_ev[j]), float(MI.resp[j]), t_game0)
        dn2 = []
        for a_, b_, who in downs:
            if who == -2:
                f = min(N - 1, int(np.searchsorted(T, a_)))     # (worked out: the one not followed then)
                who = int(other[f])
                picks.append((f, j, who))
                counts["takes worked out"] += 1
            dn2.append((a_, b_, who))
        counts["unknown windows"] += len(unknown)
        ST.append((dn2, unknown, tu, T[dn_obs[:, j]]))
    picks.sort()
    # ---- each player's stack, frame by frame: exact while followed, worked out while not
    ob = rec["obits"] if rec["obits"] is not None else np.zeros((0, 3))
    hits = rec["hits"]
    pain = {}
    shots = {}
    for r in X[(X[:, c["source"]] == 1) & (X[:, c["eType"]] == EV["entity_types"]["Player"])]:
        s_ = int(r[c["snap"]])
        if not (0 <= s_ < len(tm)) or remap[s_] < 0:
            continue
        f = int(remap[s_])
        if int(r[c["number"]]) != other[f]:
            continue
        if int(r[c["event"]]) == EV_PAIN:
            pain[f] = int(r[c["eventParm"]])
        elif int(r[c["event"]]) == EV["event_ids"]["WeaponFired"]:
            q = int(r[c["weapon"]])
            if q in PY.QLW:
                shots.setdefault(f, []).append(PY.WEAPONS.index(PY.QLW[q]))
    dth = {cl: sorted(float(t_) for t_, v, k in ob if int(v) == cl) for cl in clients}
    eh, ea = np.zeros(N, np.float32), np.zeros(N, np.float32)
    ehas, eammo = np.zeros((N, 9), bool), np.zeros((N, 9), np.float32)
    LD = E.LOADOUTS["all"][1]
    F = {}

    def respawn(cl):
        has = np.zeros(9, bool)
        am = np.zeros(9, np.float32)
        has[E.MG] = has[E.G] = True
        am[E.MG] = LD[E.MG]
        F[cl] = [float(E.SPAWN_HP), 0.0, has, am]
    for cl in clients:
        respawn(cl)
    di = {cl: 0 for cl in clients}
    pk = 0
    last_t = T[0]
    for f in range(N):
        t_ = T[f]
        for cl in clients:
            while di[cl] < len(dth[cl]) and dth[cl][di[cl]] <= t_:
                respawn(cl)
                di[cl] += 1
        me, op = int(cn[f]), int(other[f])
        F[me] = [float(rec["health"][f]), float(rec["armor"][f]), rec["owned"][f].astype(bool).copy(),
                 np.where(rec["owned"][f].astype(bool), rec["ammo"][f], 0.0).astype(np.float32)]
        F[me][2][E.G] = True
        H, A, has, am = F[op]
        dt_ = max(0.0, min(0.1, t_ - last_t))
        last_t = t_
        if H > 100:
            H = max(100.0, H - dt_)
        if A > 100:
            A = max(100.0, A - dt_)
        while pk < len(picks) and picks[pk][0] <= f:
            _, j, cl = picks[pk]
            pk += 1
            if cl != op:
                continue
            kd, val, _, cap, _ = MI.idef[j]
            if kd == "hp":
                H = max(H, min(100.0, H + val)) if cap <= 100 else min(float(cap), H + val)
            elif kd == "ar":
                A = min(float(cap), A + val)
            elif kd == "wp":
                am[val] = max(am[val], float(LD.get(val, 10))) if not has[val] else min(float(E.AMMO_MAX[val]), am[val] + float(LD.get(val, 10)) * 0.5)
                has[val] = True
            elif kd == "am":
                am[val] = min(float(E.AMMO_MAX[val]), am[val] + float(cap))
        if hits is not None and f > 0 and hits[f] > hits[f - 1] and rec["seg"][f] == rec["seg"][f - 1]:
            dmg = float(hits[f] - hits[f - 1]) * float(DMG_HIT[int(rec["weapon"][f])]) * DMG_SCALE
            save = min(A, float(np.ceil(dmg * E.ARMOR_ABSORB)))
            A -= save
            H = max(1.0, H - (dmg - save))
        if f in pain:
            lo, hi = PAIN_BAND.get(pain[f], (1.0, 200.0))
            counts["pain heard: the worked-out health under its band" if H < lo else "pain heard: over its band" if H > hi
                   else "pain heard: in its band"] += 1
            H = min(max(H, lo), hi)
        for wq in shots.get(f, ()):
            if wq != E.G:
                am[wq] = max(0.0, am[wq] - 1.0)
        w_ = int(en["wpn"][f])
        if w_ >= 0:
            if not has[w_]:
                has[w_] = True
                am[w_] = max(am[w_], float(LD.get(w_, 10)))
            if w_ != E.G:
                am[w_] = max(am[w_], 1.0)
        F[op] = [H, A, has, am]
        eh[f], ea[f] = H, A
        ehas[f], eammo[f] = has, am.copy()
    if judge is not None:                                    # (tools/run/pro_judge_rows.py) the judge's rows instead of moments
        judge_rows(judge, E, rec, clock, cn, other, clients, dth, eh, ea, ehas, T, own_pw, en, counts, t_game0)
        return []
    # ---- the moments
    out = []

    def life_of(cl_of):
        L = np.empty(N)
        for cl in clients:
            m_ = cl_of == cl
            ds = np.array(dth[cl])
            if len(ds):
                j_ = np.searchsorted(ds, T[m_], side="right") - 1
                L[m_] = np.where(j_ >= 0, T[m_] - ds[np.maximum(j_, 0)] - RESPAWN_S, T[m_] - t_game0)
            else:
                L[m_] = T[m_] - t_game0
        return L
    life_rec, life_en = life_of(cn), life_of(other)
    # the takes as seats at frame f: the followed one is 0
    step = np.zeros(N)
    step[1:] = np.linalg.norm(np.diff(rec["pos"], axis=0), axis=1)
    estep = np.zeros(N)
    estep[1:] = np.nan_to_num(np.linalg.norm(np.diff(en["pos"], axis=0), axis=1), nan=0.0)
    tele = np.zeros(N, bool)
    for f in np.nonzero((step > TELE) | (estep > TELE))[0]:
        tele[max(0, f - 20):f + 20] = True
    seg = rec["seg"]
    off = float(rng.uniform(0, every))
    marks = np.arange(off + 5.0, 595.0, every)
    fr = np.searchsorted(np.where(np.isfinite(clock), clock, -1.0), marks)
    for f, mk in zip(fr, marks):
        if f >= N or abs(clock[f] - mk) > 0.1:
            continue
        counts["frames looked at"] += 1
        why = None
        if not rec["alive"][f] or rec["health"][f] <= 0:
            why = "his player dead"
        elif not np.isfinite(en["pos"][f]).all():
            why = "the enemy not sent"
        elif life_rec[f] < life_s or life_en[f] < life_s:
            why = "within the seconds after a respawn"
        elif tele[f]:
            why = "a teleporter step"
        elif seg[max(0, f - 40)] != seg[f] or seg[min(N - 1, f + 40)] != seg[f]:
            why = "a cut near"
        elif own_pw[f] or en["pw"][f] != 0:
            why = "a powerup"
        if why:
            counts[why] += 1
            continue
        left = np.zeros(MI.nI, np.float32)
        who = np.full(MI.nI, -1, np.int8)
        uns = np.zeros(MI.nI, bool)
        bad = False
        for j in range(MI.nI):
            if j not in ent_of:
                uns[j] = True
                continue
            downs, unknown, tu, td = ST[j]
            l_, w_, kn = item_at(T[f], downs, unknown, tu, td, float(MI.resp[j]))
            if not kn:
                if MI.lab[j] in BIG:
                    bad = True
                    break
                uns[j] = True
                continue
            left[j] = min(l_, float(MI.resp[j]))
            who[j] = -1 if w_ < 0 or l_ <= 0 else 0 if w_ == cn[f] else 1
        if bad:
            counts["a big item's state not known"] += 1
            continue
        pa = MI.stands(rec["pos"][f], bool(rec["ground"][f]) if rec.get("ground") is not None else False)
        pb = MI.stands(en["pos"][f], bool(en["ground"][f]))
        if pa is None or pb is None:
            counts["a place the simulator does not hold"] += 1
            continue
        if np.linalg.norm(pa - pb) < 48.0:
            counts["the two within 48 units"] += 1
            continue
        ah = rec["owned"][f].astype(bool).copy()
        ah[E.G] = True
        aam = np.where(ah, rec["ammo"][f], 0.0).astype(np.float32)
        aam[E.G] = 0.0
        out.append(dict(
            clock=float(clock[f]), score=(int(rec["score"][f]), int(rec["enemy_score"][f])),
            pos=(pa, pb), vel=(rec["vel"][f], en["vel"][f]),
            yaw=(float(rec["yaw"][f]), float(en["ang"][f][1])), pitch=(float(rec["pitch"][f]), float(en["ang"][f][0])),
            hp=(float(rec["health"][f]), float(eh[f])), armor=(float(rec["armor"][f]), float(ea[f])),
            has=(ah, ehas[f]), ammo=(aam, eammo[f]), weapon=(int(rec["weapon"][f]), int(en["wpn"][f]) if en["wpn"][f] >= 0 else E.MG),
            life=(float(life_rec[f]), float(life_en[f])), left=left, who=who, uns=uns))
        counts["moments"] += 1
    return out


def pitch180(p):
    p = np.asarray(p, np.float32)
    return ((p + 180.0) % 360.0) - 180.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--demos", type=int, default=150)
    ap.add_argument("--every", type=float, default=4.0)
    ap.add_argument("--life", type=float, default=2.0)
    ap.add_argument("--cap", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(SIM, "pro_moments"))
    a = ap.parse_args()
    low_priority()
    rng = np.random.default_rng(a.seed)
    root = demo_root()
    dd = os.path.join(root, "demos", a.map)
    new = sorted(glob.glob(os.path.join(dd, "*.dm_91"))) + sorted(glob.glob(os.path.join(dd, "*.dm_90")))
    old = sorted(glob.glob(os.path.join(dd, "*.dm_73")))
    pick = list(rng.permutation(new))[:a.demos]
    if len(pick) < a.demos:
        pick += list(rng.permutation(old))[:a.demos - len(pick)]
    MI = MapInfo(a.map)
    from collections import Counter
    counts = Counter()
    tmp = tempfile.mkdtemp(prefix="pm_")
    rows, src = [], []
    t0 = time.time()
    for nd, demo in enumerate(pick):
        try:
            ms = one_demo(MI, demo, tmp, a.every, a.life, rng, counts)
        except Exception as e:                               # noqa: BLE001 (a broken demo must not stop the map)
            counts["error"] += 1
            print("error", nd, repr(e)[:160], flush=True)
            ms = []
        counts["demos"] += 1
        counts["demos with moments"] += int(bool(ms))
        h = hashlib.sha1(os.path.basename(demo).encode("utf-8", "replace")).hexdigest()[:10]
        for m in ms:
            rows.append(m)
            src.append((nd, h, os.path.splitext(demo)[1][1:]))
        if nd % 10 == 0:
            print("{} {}/{} moments {} {:.0f}s".format(a.map, nd + 1, len(pick), len(rows), time.time() - t0), flush=True)
    if len(rows) > a.cap:
        sel = np.sort(rng.choice(len(rows), a.cap, replace=False))
        rows = [rows[i] for i in sel]
        src = [src[i] for i in sel]
    os.makedirs(a.out, exist_ok=True)
    M = len(rows)

    def st(k, dt=np.float32):
        return np.array([[r[k][0], r[k][1]] for r in rows], dt) if M else np.zeros((0, 2), dt)
    res = dict(
        version=np.int32(VERSION), clock=np.array([r["clock"] for r in rows], np.float32),
        score=st("score", np.int16), pos=np.array([np.stack(r["pos"]) for r in rows], np.float32).reshape(M, 2, 3),
        vel=np.array([np.stack(r["vel"]) for r in rows], np.float32).reshape(M, 2, 3),
        yaw=st("yaw"), pitch=pitch180(st("pitch")), hp=st("hp"), armor=st("armor"),
        has=np.array([np.stack(r["has"]) for r in rows], bool).reshape(M, 2, 9),
        ammo=np.array([np.stack(r["ammo"]) for r in rows], np.int16).reshape(M, 2, 9),
        weapon=st("weapon", np.int8), life=st("life"),
        est=np.tile(np.array([0, 1], np.int8), (M, 1)),
        item_left=np.array([r["left"] for r in rows], np.float16).reshape(M, MI.nI),
        item_who=np.array([r["who"] for r in rows], np.int8).reshape(M, MI.nI),
        item_unsure=np.array([r["uns"] for r in rows], bool).reshape(M, MI.nI),
        item_pos=MI.pos.astype(np.float32), item_cls=np.array(MI.cls),
        demo=np.array([s[0] for s in src], np.int16), demo_hash=np.array([s[1] for s in src]),
        demo_kind=np.array([s[2] for s in src]))
    np.savez_compressed(os.path.join(a.out, a.map + ".npz"), **res)
    resp = {k: dict(n=len(v), median=float(np.median(v)), p10=float(np.percentile(v, 10)), p90=float(np.percentile(v, 90)))
            for k, v in sorted(RESP_SEEN.items())}
    meta = dict(respawn_seen=resp, map=a.map, version=VERSION, moments=M, every=a.every, life=a.life, demos=len(pick), counts=dict(counts),
                seconds=round(time.time() - t0))
    json.dump(meta, open(os.path.join(a.out, a.map + ".json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()

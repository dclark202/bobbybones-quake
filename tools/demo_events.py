"""Pro demos -> an event record per frame and what the demo shows next (the feasibility test of v16's event record,
docs/design/v16_event_record.md; the model is tools/event_pretrain.py).

    python tools/demo_events.py --out <folder>                       # every map of <demo root>/sets_lite, 2 processes
    python tools/demo_events.py --out <folder> --maps bloodrun --limit 150 --procs 8
    python tools/demo_events.py --show 3 --map aerowalk              # the events of one demo as a table (no names)

Input:  <demo root>/sets_lite/<map>/*.npz (sim/demo_dataset.py --lite: 32 numbers a frame for the followed player P:
        health, armor, weapon in hand, firing, enemy in view, his place, the enemy's place and weapon, weapons owned,
        weapons with ammunition, yaw, "the server sent the enemy") and plugins/duel_items.json (where a map's items lie).
Output: <folder>/<map>.npz, one row every `--every` frames (8: five a second), and <folder>/stats.json. No names.
        In a map's file: the rows (now, t, the targets, ev_n = how many of its chain's events a row knows, ev_ns = how
        many of them are of the rare kinds, ls / since / live = the enemy as last seen), `events` (when known, when it
        happened, kind, weapon + 1, place, four facts), `chains` (demo, first row, rows, first event, events, first
        place in ev_fast, in ev_slow), `ev_fast` / `ev_slow` (the event numbers of the frequent and the rare kinds),
        `pair` (a hash a demo: both recordings of one game share it).
    python tools/demo_events.py --stats <folder>                     # what is in it: chains, reach of the record, rates
    python tools/demo_events.py --reach <folder>                     # is his last pickup of an item still in the record

How the frames hang together
  stretch   as in the set: frames 25 ms apart between two `first` flags.
  life      stretches joined over a hole of a few lost frames (the next one starts within 100 units, no weapon lost).
  chain     lives joined over a death (the next stretch starts as a fresh spawn: 125 health, no armor, machine gun and
            gauntlet). The event record and the clock run on over a chain; 2 seconds are assumed for a respawn, 75 ms
            for a hole (the sets hold no time stamps). Anything else (a cut, the file's end) ends the chain: what came
            after is not known, and a target that reaches over that end is left out (-1), not counted as "no".
  Warm-up (everyone holds every weapon) is dropped.

The "now" vector (NOW_NAMES, 47 numbers): where he is, how he moves, health, armor, weapon in hand, weapons owned, the
enemy in view or not, where the enemy is from him and how the enemy moves and what he holds while in view, seconds
since the enemy was last in view, his own view direction, firing.

Events (EVENT_KINDS): kind, a weapon or none, a place on the map, a time, four facts (EVENT_FACTS).
  enemy in      the enemy came into view (after half a second or more out of it): where he was, what he held
  enemy out     the enemy went out of view: where he was last, how he moved, what he held, how long he had been in view.
                It enters the record half a second after the loss (a shorter loss is no event); until then the row's
                own "last seen" fields stand in for it (`live`), so that nothing is known later than a player knows it
  took ...      mega, red armor, yellow armor, green armor, a 25 or 50 health, a weapon he did not own (from the jumps
                in his health, armor and weapons, set at the item's spot)
  hurt          health and armor lost (the decay above 100 is not damage); at most one a second, each with all the
                damage since the one before
  fired         his own loud shots: rocket launcher, railgun, lightning gun; at most one every 1.5 s a weapon
  died, spawned

Targets, all from what the demo shows after the row (-1 = not asked on this row)
  a_time   enemy out of view now: until he is next in view. Buckets under 1, 1-2, 2-4, 4-8, 8-16 s, "over 16 s or
           never in this life"
  a_where  where he is when he comes into view, as an offset from where P is NOW (map axes, /1000), when a_time < 16 s
  b_kind   P's next big pickup within 16 s: mega, red armor, yellow armor, a weapon      b_time   until it, same buckets
  c_hurt   is P hurt within 2 s                         d_die    does P die within 5 s
  e_where  where the enemy is NOW, as an offset from P, on rows where he is out of view and the server sent him all
           the same (it sends whoever might be visible from P's part of the map: on most maps that is nearly always)
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DT = 0.025
WEAPONS = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")     # the order of sim/duel_env.py
RL, RG, LG, MG, SG, GL, PG, HMG, GAUNT = range(9)
# columns of a lite set (sim/demo_dataset.py, build_demo, the `lite` branch)
C_HP, C_AR, C_W, C_FIRE, C_ACQ, C_EW, C_YAW, C_PRES = 0, 1, 2, 3, 4, 11, 30, 31
C_POS, C_EPOS, C_HAS, C_AMMO = slice(5, 8), slice(8, 11), slice(12, 21), slice(21, 30)

HOLE_S, RESPAWN_S = 3 * DT, 2.0          # assumed lengths of a hole in the recording and of a respawn
OUT_WAIT = 0.5                           # the enemy is "gone" after this long out of view
HURT_EVERY, FIRE_EVERY = 1.0, 1.5        # at most one hurt event / one fired event of a weapon in this many seconds
EDGES = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
BUCKETS = ("under 1 s", "1-2 s", "2-4 s", "4-8 s", "8-16 s", "over 16 s or never")
HURT_S, DIE_S = 2.0, 5.0

EVENT_KINDS = ("none", "enemy in", "enemy out", "took mega", "took red armor", "took yellow armor", "took green armor",
               "took health", "took weapon", "hurt", "fired", "died", "spawned")
E_IN, E_OUT, E_MH, E_RA, E_YA, E_GA, E_HEALTH, E_WEAPON, E_HURT, E_FIRED, E_DIED, E_SPAWN = range(1, 13)
EVENT_FACTS = {
    "enemy in": "his health /200, his armor /200, the distance /1000, seconds since the enemy was seen before (log, 1 = never)",
    "enemy out": "the enemy's velocity /400 (3), seconds he had been in view (log)",
    "took ...": "health after /200, armor after /200, the gain /100, 0",
    "hurt": "health after /200, armor after /200, the damage /100, enemy in view or not",
    "fired": "health /200, armor /200, enemy in view or not, 0",
    "died": "health before /200, armor before /200, enemy in view or not, 0",
    "spawned": "health /200, 0, 0, 0",
}
SLOW_KINDS = (E_MH, E_RA, E_YA, E_GA, E_HEALTH, E_WEAPON, E_DIED, E_SPAWN)   # the rare ones (about ten a minute); the
#                                                                          others (sightings, hurt, fired) come 40 a minute
PICK_KINDS = ("mega", "red armor", "yellow armor", "weapon")           # the classes of b_kind
PICK_OF = {E_MH: 0, E_RA: 1, E_YA: 2, E_WEAPON: 3}

NOW_NAMES = (["x /1000", "y /1000", "z /1000", "vx /400", "vy /400", "vz /400", "health /100", "armor /100"]
             + ["in hand: " + w for w in WEAPONS] + ["owns: " + w for w in WEAPONS]
             + ["enemy in view", "enemy dx /1000", "enemy dy /1000", "enemy dz /1000", "enemy vx /400", "enemy vy /400",
                "enemy vz /400"] + ["enemy holds: " + w for w in WEAPONS]
             + ["since enemy seen (log, 0..1)", "enemy never seen", "view cos", "view sin", "firing"])
N_NOW = len(NOW_NAMES)
NOW_SEEN = NOW_NAMES.index("since enemy seen (log, 0..1)")
SEEN_CAP = 60.0

HEALTH = {"item_health_small": 5, "item_health": 25, "item_health_large": 50, "item_health_mega": 100}
ARMOR = {"item_armor_shard": 5, "item_armor_jacket": 25, "item_armor_combat": 50, "item_armor_body": 100}
WPN = {"weapon_rocketlauncher": RL, "weapon_railgun": RG, "weapon_lightning": LG, "weapon_shotgun": SG,
       "weapon_grenadelauncher": GL, "weapon_plasmagun": PG, "weapon_hmg": HMG}
H_KIND = {5: 0, 25: E_HEALTH, 50: E_HEALTH, 100: E_MH}
A_KIND = {5: 0, 25: E_GA, 50: E_YA, 100: E_RA}
MAP_WORDS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik",
             "toxicity", "cure", "ztn", "hub", "dm", "pov", "duel", "vs", "npz", "quakelive", "map", "game", "final")


def demo_root():
    f = os.path.join(ROOT, "data", "demo_root.txt")
    if os.path.exists(f):
        p = open(f).read().strip()
        if p:
            return p
    return os.path.join(ROOT, "data")


def map_items(mp):
    """a map's duel items (plugins/duel_items.json, from the real game): health, armor and weapon spots"""
    rows = json.load(open(os.path.join(ROOT, "plugins", "duel_items.json"))).get(mp, [])
    out = {"hp": [], "ar": [], "wp": []}
    for cls, x, y, z in rows:
        if cls in HEALTH:
            out["hp"].append((x, y, z, HEALTH[cls]))
        elif cls in ARMOR:
            out["ar"].append((x, y, z, ARMOR[cls]))
        elif cls in WPN:
            out["wp"].append((x, y, z, WPN[cls]))
    return {k: np.array(v, np.float32).reshape(-1, 4) for k, v in out.items()}


def pair_key(name):
    """a number that is the same for both players' recordings of one game (the words of the file name without the
    map, digits and order), so that the two never sit on both sides of the split. Only its hash is kept."""
    words = sorted(set(w for w in re.findall(r"[a-z]{3,}", name.lower()) if w not in MAP_WORDS))
    return int(hashlib.sha1(" ".join(words).encode()).hexdigest()[:12], 16)


def _near_item(tab, p, gain, radius=100.0):
    """the nearest item within reach whose amount can give this gain; (amount, spot) or None. Items of one kind lie in
    rows (shards, bubbles, two 25 healths) and two can be taken in one frame: the gain may be that of all of them."""
    if not len(tab):
        return None
    d = np.linalg.norm(tab[:, :3] - p[None], axis=1)
    for k in np.argsort(d):
        if d[k] > radius:
            break
        if gain <= tab[k, 3] * ((d < 2 * radius) & (tab[:, 3] == tab[k, 3])).sum() + 0.5:
            return float(tab[k, 3]), tab[k, :3]
    return None


def _fill_prev(a, bad):
    """rows flagged bad take the last good row before them (the first good one if none)"""
    n = len(a)
    idx = np.where(~bad, np.arange(n), -1)
    idx = np.maximum.accumulate(idx)
    if (idx < 0).any():
        good = np.flatnonzero(~bad)
        idx[idx < 0] = good[0] if len(good) else 0
    return a[idx]


def _bucket(dt):
    return np.searchsorted(EDGES, dt, side="right").astype(np.int8)


def _next_in_life(frames, life, t, n):
    """for every frame: the index into `frames` (sorted frame numbers of something) of the next one strictly after it in
    the same life, or -1; and the seconds until it"""
    k = np.searchsorted(frames, np.arange(n), side="right")
    ok = k < len(frames)
    nxt = frames[np.minimum(k, max(0, len(frames) - 1))] if len(frames) else np.zeros(n, np.int64)
    ok &= (life[nxt] == life) if len(frames) else False
    dt = np.where(ok, t[nxt] - t, np.inf)
    return np.where(ok, k, -1), dt


def chains_of(L, first):
    """the stretches of a set joined into chains: a list of (stretch numbers, how each follows the one before)"""
    has = L[:, C_HAS] > 0
    lost = np.zeros(len(L), bool)                       # weapons gone inside a stretch: a restart of the game
    lost[1:] = (has[:-1] & ~has[1:]).any(1)
    lost &= ~first
    first = first | lost
    st = np.flatnonzero(first)
    en = np.r_[st[1:], len(L)]
    nhas = has.sum(1)

    def fresh(i):
        return L[i, C_AR] == 0 and 120 <= L[i, C_HP] <= 125 and nhas[i] == 2 and has[i, MG] and has[i, GAUNT]

    S = len(st)
    link = ["cut"] * S
    for s in range(1, S):
        i, p = st[s], st[s] - 1
        d = float(np.linalg.norm(L[i, C_POS] - L[p, C_POS]))
        if d < 100 and bool((has[i] | ~has[p]).all()) and not lost[i] and not (fresh(i) and L[p, C_HP] < L[i, C_HP] - 10):
            link[s] = "cont"
        elif fresh(i) and not lost[i]:
            link[s] = "spawn"
    chains, cur, warm = [], None, False
    for s in range(S):
        i = st[s]
        if s == 0 or link[s] == "cut":
            warm = nhas[i] >= (7 if s == 0 else 8)      # everyone holds every weapon: the warm-up
        if warm and fresh(i) and link[s] != "cont":
            warm = False
            cur = None
        if warm:
            cur = None
            continue
        if cur is None or link[s] == "cut":
            cur = []
            chains.append(cur)
        cur.append(s)
    counts = {k: sum(1 for c in chains for s in c[1:] if link[s] == k) for k in ("cont", "spawn")}
    counts["cut"] = len(chains)
    return st, en, link, [c for c in chains if sum(en[s] - st[s] for s in c) >= 160], counts


def build_chain(L, st, en, link, ss, items, every):
    """one chain -> its rows (a dict of arrays) and its events (ta, te, kind, weapon, place, four facts)"""
    fi = np.concatenate([np.arange(st[s], en[s]) for s in ss])
    n = len(fi)
    t = np.zeros(n)
    life = np.zeros(n, np.int32)
    within = np.zeros(n, np.int32)
    segstart = np.zeros(n, bool)
    spawn_at, death_at = [], []
    off, lf, p0 = 0.0, 0, 0
    for k, s in enumerate(ss):
        m = en[s] - st[s]
        if k > 0:
            if link[s] == "spawn":
                death_at.append(p0 - 1)
                off += RESPAWN_S
                lf += 1
            else:
                off += HOLE_S
        if k == 0 or link[s] == "spawn":
            spawn_at.append(p0)
        t[p0:p0 + m] = off + DT * np.arange(m)
        off += DT * m
        life[p0:p0 + m] = lf
        within[p0:p0 + m] = np.arange(m)
        segstart[p0] = True
        p0 += m
    hp, ar = L[fi, C_HP], L[fi, C_AR]
    w = L[fi, C_W].astype(np.int64)
    fire = L[fi, C_FIRE] > 0
    acq = L[fi, C_ACQ] > 0
    pres = L[fi, C_PRES] > 0
    pos, epos = L[fi, C_POS], L[fi, C_EPOS]
    ew = L[fi, C_EW].astype(np.int64)
    has = L[fi, C_HAS] > 0
    yaw = np.radians(L[fi, C_YAW])
    same_life = np.r_[False, life[1:] == life[:-1]]
    fresh0 = L[fi[0], C_AR] == 0 and 120 <= L[fi[0], C_HP] <= 125 and has[0].sum() == 2
    if not fresh0:
        spawn_at = spawn_at[1:]
    # ---- how he moves: place differences (a teleporter or a stretch's first frame takes the frame before; a spawn stands)
    d = np.diff(pos, axis=0, prepend=pos[:1])
    bad = segstart | (np.abs(d).max(1) > 60)
    vel = _fill_prev(d / DT, bad)
    for p in spawn_at:
        vel[p] = 0.0
    # ---- how the enemy moves: over 100 ms where the server sent him throughout (his places are whole numbers)
    evel = np.zeros((n, 3), np.float32)
    seg = np.cumsum(segstart)
    if n > 4:
        d1 = epos[1:] - epos[:-1]
        ok1 = pres[1:] & pres[:-1] & (seg[1:] == seg[:-1]) & (np.abs(d1).max(1) < 60)
        evel[1:][ok1] = d1[ok1] / DT
        d4 = epos[4:] - epos[:-4]
        ok4 = pres[4:] & pres[:-4] & (seg[4:] == seg[:-4]) & (np.abs(d4).max(1) < 240)
        evel[4:][ok4] = d4[ok4] / (4 * DT)
    # ---- the enemy in view: when last, and the sightings (apart by OUT_WAIT or more)
    ar_n = np.arange(n)
    last = np.maximum.accumulate(np.where(acq, ar_n, -1))
    seen = last >= 0
    lastc = np.maximum(last, 0)
    since = np.where(seen, t - t[lastc], 999.0)
    A = np.flatnonzero(acq)
    ev = []                                                    # (ta, te, kind, weapon + 1, x, y, z, f0, f1, f2, f3)
    dur_at = np.zeros(n, np.float32)                           # how long the sighting had lasted, at an in-view frame
    if len(A):
        newep = np.r_[True, np.diff(t[A]) >= OUT_WAIT]
        ep = np.cumsum(newep) - 1
        ep_first = A[newep]
        ep_last = A[np.r_[newep[1:], True]]
        dur_at[A] = t[A] - t[ep_first[ep]]
        for e in range(len(ep_first)):
            f = ep_first[e]
            gap = np.log1p(min(SEEN_CAP, t[f] - t[ep_last[e - 1]])) / np.log1p(SEEN_CAP) if e else 1.0
            ev.append((t[f], t[f], E_IN, ew[f] + 1, *epos[f], hp[f] / 200, ar[f] / 200,
                       float(np.linalg.norm(epos[f] - pos[f])) / 1000, gap))
            f = ep_last[e]
            if t[f] + OUT_WAIT <= t[-1]:
                ev.append((t[f] + OUT_WAIT, t[f], E_OUT, ew[f] + 1, *epos[f], *(evel[f] / 400), np.log1p(dur_at[f]) / 4))
    # ---- pickups: jumps in health, armor and the weapons owned, inside a life
    dh = np.where(same_life, hp - np.r_[hp[:1], hp[:-1]], 0.0)
    da = np.where(same_life, ar - np.r_[ar[:1], ar[:-1]], 0.0)
    picks, n_fallback, n_picks = [], 0, 0
    for f in np.flatnonzero(dh > 0):
        hit = _near_item(items["hp"], pos[f], dh[f])
        if hit is None:
            kind, spot = (E_MH if dh[f] > 50 else E_HEALTH if dh[f] > 5 else 0), pos[f]
            n_fallback += kind != 0
        else:
            kind, spot = H_KIND[int(hit[0])], hit[1]
        if kind:
            n_picks += 1
            ev.append((t[f], t[f], kind, 0, *spot, hp[f] / 200, ar[f] / 200, dh[f] / 100, 0.0))
            if kind in PICK_OF:
                picks.append((f, PICK_OF[kind]))
    for f in np.flatnonzero(da > 0):
        hit = _near_item(items["ar"], pos[f], da[f])
        if hit is None:
            kind, spot = (E_RA if da[f] > 50 else E_YA if da[f] > 25 else E_GA if da[f] > 5 else 0), pos[f]
            n_fallback += kind != 0
        else:
            kind, spot = A_KIND[int(hit[0])], hit[1]
        if kind:
            n_picks += 1
            ev.append((t[f], t[f], kind, 0, *spot, hp[f] / 200, ar[f] / 200, da[f] / 100, 0.0))
            if kind in PICK_OF:
                picks.append((f, PICK_OF[kind]))
    new = has & ~np.r_[has[:1], has[:-1]] & same_life[:, None]
    for f, wi in zip(*np.nonzero(new)):
        tab = items["wp"]
        spot = pos[f]
        if len(tab):
            dd = np.where(tab[:, 3] == wi, np.linalg.norm(tab[:, :3] - pos[f][None], axis=1), 1e9)
            if dd.min() < 150:
                spot = tab[dd.argmin(), :3]
        ev.append((t[f], t[f], E_WEAPON, wi + 1, *spot, hp[f] / 200, ar[f] / 200, 0.0, 0.0))
        picks.append((f, PICK_OF[E_WEAPON]))
    # ---- hurt: health and armor lost, without the decay above 100 (one point a second each)
    php, par = np.r_[hp[:1], hp[:-1]], np.r_[ar[:1], ar[:-1]]
    dmg = np.where((dh < 0) & ~((dh == -1) & (php > 100)), -dh, 0.0) + np.where((da < 0) & ~((da == -1) & (par > 100)), -da, 0.0)
    hits = np.flatnonzero(dmg > 0)
    last_t, acc = -1e9, 0.0
    for f in hits:
        acc += dmg[f]
        if t[f] - last_t >= HURT_EVERY:
            ev.append((t[f], t[f], E_HURT, 0, *pos[f], hp[f] / 200, ar[f] / 200, acc / 100, float(acq[f])))
            last_t, acc = t[f], 0.0
    # ---- his own loud shots
    loud = fire & ((w == RL) | (w == RG) | (w == LG))
    last_t, last_w, prev_f = -1e9, -1, -9
    for f in np.flatnonzero(loud):
        going = prev_f == f - 1 and w[f] == last_w
        if w[f] != last_w or t[f] - last_t >= FIRE_EVERY + (0.1 if going else 0.0):
            ev.append((t[f], t[f], E_FIRED, w[f] + 1, *pos[f], hp[f] / 200, ar[f] / 200, float(acq[f]), 0.0))
            last_t, last_w = t[f], w[f]
        prev_f = f
    # ---- deaths and spawns
    for p in death_at:
        ev.append((t[p] + DT, t[p] + DT, E_DIED, 0, *pos[p], hp[p] / 200, ar[p] / 200, float(acq[p]), 0.0))
    for p in spawn_at:
        ev.append((t[p], t[p], E_SPAWN, 0, *pos[p], hp[p] / 200, 0.0, 0.0, 0.0))
    ev.sort(key=lambda e: e[0])
    E = np.array(ev, np.float32).reshape(-1, 11)
    ta = np.array([e[0] for e in ev])
    ta_slow = np.array([e[0] for e in ev if e[2] in SLOW_KINDS])
    # ---- where each life ends and how
    life_end = np.zeros(lf + 1)
    life_dead = np.zeros(lf + 1, bool)
    for k in range(lf + 1):
        life_end[k] = t[np.flatnonzero(life == k)[-1]] + DT
    for p in death_at:
        life_dead[life[p]] = True
    left = life_end[life] - t                                  # seconds of this life that the demo still shows
    dead = life_dead[life]
    # ---- targets
    k, dt_a = _next_in_life(A, life, t, n)
    a_time = np.where(acq, -1, np.where(dt_a < 16.0, _bucket(dt_a), np.where(dead | (left >= 16.0), 5, -1))).astype(np.int8)
    a_where = np.zeros((n, 3), np.float32)
    okw = (a_time >= 0) & (a_time < 5)
    a_where[okw] = (epos[A[k[okw]]] - pos[okw]) / 1000.0
    picks.sort()
    PF = np.array([p[0] for p in picks], np.int64)
    PK = np.array([p[1] for p in picks], np.int8)
    k, dt_b = _next_in_life(PF, life, t, n)
    b_time = np.where(dt_b < 16.0, _bucket(dt_b), np.where(dead | (left >= 16.0), 5, -1)).astype(np.int8)
    b_kind = np.where(b_time < 5, PK[np.maximum(k, 0)] if len(PK) else -1, -1).astype(np.int8)
    b_kind[b_time < 0] = -1
    _, dt_c = _next_in_life(hits, life, t, n)
    c_hurt = np.where((dt_c <= HURT_S) | (dead & (left <= HURT_S)), 1, np.where(left < HURT_S, -1, 0)).astype(np.int8)
    d_die = np.where(dead & (left <= DIE_S), 1, np.where(left < DIE_S, -1, 0)).astype(np.int8)
    e_ok = ~acq & pres
    # ---- rows
    sel = np.flatnonzero(within % every == 0)
    m = len(sel)
    now = np.zeros((m, N_NOW), np.float32)
    now[:, 0:3] = pos[sel] / 1000
    now[:, 3:6] = vel[sel] / 400
    now[:, 6], now[:, 7] = hp[sel] / 100, ar[sel] / 100
    now[np.arange(m), 8 + w[sel]] = 1
    now[:, 17:26] = has[sel]
    v = acq[sel]
    now[:, 26] = v
    now[:, 27:30] = np.where(v[:, None], (epos[sel] - pos[sel]) / 1000, 0)
    now[:, 30:33] = np.where(v[:, None], evel[sel] / 400, 0)
    now[np.flatnonzero(v), 33 + ew[sel][v]] = 1
    now[:, NOW_SEEN] = np.where(seen[sel], np.log1p(np.minimum(since[sel], SEEN_CAP)) / np.log1p(SEEN_CAP), 1.0)
    now[:, NOW_SEEN + 1] = ~seen[sel]
    now[:, NOW_SEEN + 2], now[:, NOW_SEEN + 3] = np.cos(yaw[sel]), np.sin(yaw[sel])
    now[:, NOW_SEEN + 4] = fire[sel]
    ls = np.zeros((m, 8), np.float32)                          # the enemy as last seen: place /1000, velocity /400, weapon + 1, time in view
    lc = lastc[sel]
    ls[:, 0:3] = epos[lc] / 1000
    ls[:, 3:6] = evel[lc] / 400
    ls[:, 6] = ew[lc] + 1
    ls[:, 7] = np.log1p(dur_at[lc]) / 4
    ls[~seen[sel]] = 0
    rows = {
        "now": now.astype(np.float16), "t": t[sel].astype(np.float32), "ls": ls.astype(np.float16),
        "since": np.minimum(since[sel], 999.0).astype(np.float32), "seen": seen[sel],
        "live": seen[sel] & ~v & (since[sel] < OUT_WAIT),
        "ev_n": np.searchsorted(ta, t[sel], side="right").astype(np.int32),   # events of this chain known at the row
        "ev_ns": np.searchsorted(ta_slow, t[sel], side="right").astype(np.int32),   # ... of them the rare kinds
        "a_time": a_time[sel], "a_where": a_where[sel].astype(np.float16), "b_kind": b_kind[sel], "b_time": b_time[sel],
        "c_hurt": c_hurt[sel], "d_die": d_die[sel], "e_ok": e_ok[sel],
        "e_where": np.where(e_ok[sel][:, None], (epos[sel] - pos[sel]) / 1000, 0).astype(np.float16),
        "pos": pos[sel].astype(np.float32),
    }
    info = {"frames": n, "lives": lf + 1, "deaths": len(death_at), "picks": n_picks, "fallback": n_fallback,
            "seconds": float(t[-1] - t[0])}
    return rows, E, info


def demo_rows(path, items, every):
    z = np.load(path)
    L, first = z["lite"], z["first"].copy()
    if len(L) < 800 or L.shape[1] != 32:
        return None
    st, en, link, chains, counts = chains_of(L, first)
    out = []
    for ss in chains:
        out.append(build_chain(L, st, en, link, ss, items, every))
    return out, counts


def worker(args):
    mp, files, every = args
    items = map_items(mp)
    res = []
    for f in files:
        try:
            r = demo_rows(f, items, every)
        except Exception as e:                                   # a broken set must not stop the batch
            print("failed ({}): {!r}".format(mp, e), flush=True)
            r = None
        res.append((pair_key(os.path.basename(f)), r))
    return mp, res


def pack_map(mp, results, out_dir):
    """all chains of a map into one file: rows, events, a table of chains (demo, first row, rows, first event, events,
    its first place in ev_fast, in ev_slow: the event numbers of the frequent and of the rare kinds, chain by chain)"""
    rows, evs, chain_tab, keys, fast, slow = {}, [], [], [], [], []
    r0 = e0 = f0 = s0 = 0
    stats = {"demos": 0, "chains": 0, "lives": 0, "deaths": 0, "rows": 0, "events": 0, "frames": 0, "picks": 0, "fallback": 0,
             "links": {"cont": 0, "spawn": 0, "cut": 0}, "kinds": [0] * len(EVENT_KINDS)}
    for key, r in results:
        if r is None or not r[0]:
            continue
        di = len(keys)
        keys.append(key)
        stats["demos"] += 1
        for k in stats["links"]:
            stats["links"][k] += r[1][k]
        for rw, E, info in r[0]:
            m = len(rw["t"])
            chain_tab.append((di, r0, m, e0, len(E), f0, s0))
            sl = np.isin(E[:, 2].astype(np.int64), SLOW_KINDS)
            fast.append(e0 + np.flatnonzero(~sl))
            slow.append(e0 + np.flatnonzero(sl))
            f0 += int((~sl).sum())
            s0 += int(sl.sum())
            for k, v in rw.items():
                rows.setdefault(k, []).append(v)
            evs.append(E)
            r0 += m
            e0 += len(E)
            stats["chains"] += 1
            for k in ("lives", "deaths", "frames", "picks", "fallback"):
                stats[k] += info[k]
            kc = np.bincount(E[:, 2].astype(np.int64), minlength=len(EVENT_KINDS))
            stats["kinds"] = [int(a + b) for a, b in zip(stats["kinds"], kc)]
    if not chain_tab:
        return None
    rows = {k: np.concatenate(v) for k, v in rows.items()}
    stats["rows"], stats["events"] = int(r0), int(e0)
    np.savez(os.path.join(out_dir, mp + ".npz"), events=np.concatenate(evs), chains=np.array(chain_tab, np.int64),
             pair=np.array(keys, np.int64), ev_fast=np.concatenate(fast).astype(np.int32),
             ev_slow=np.concatenate(slow).astype(np.int32), **rows)
    return stats


def show(mp, number, every):
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))
    r, counts = demo_rows(files[number], map_items(mp), every)
    print("demo {} of {} on {}: {} chains; links {}".format(number, len(files), mp, len(r), counts))
    for c, (rw, E, info) in enumerate(r):
        print("chain {}: {:.0f} s, {} lives, {} deaths, {} events, {} rows".format(c, info["seconds"], info["lives"],
                                                                                    info["deaths"], len(E), len(rw["t"])))
        for e in E[:400]:
            wn = WEAPONS[int(e[3]) - 1] if e[3] > 0 else ""
            print("  {:7.2f} s  {:18s} {:4s} at ({:6.0f} {:6.0f} {:5.0f})  facts {}".format(
                e[1], EVENT_KINDS[int(e[2])], wn, e[4], e[5], e[6], np.round(e[7:], 2)))


def stats(folder):
    """what is in a folder of samples: how long the chains are, how far back sixteen events reach, events a minute by
    kind, how often each target says what"""
    tot = {}
    print("| map | demos | hours | chains | deaths seen | rows | half the rows are in a chain longer than | 16 events reach back (median; 10% under; 10% over) | rows with a full record | 8 rare events reach back (median) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    S = json.load(open(os.path.join(folder, "stats.json")))
    every = S["every"]
    agg = {"span": [], "kinds": np.zeros(len(EVENT_KINDS)), "hours": 0.0}
    tg = {}
    for f in sorted(glob.glob(os.path.join(folder, "*.npz"))):
        mp = os.path.splitext(os.path.basename(f))[0]
        z = np.load(f)
        ch, E, t, ev_n = z["chains"], z["events"], z["t"], z["ev_n"]
        clen = np.repeat(ch[:, 2], ch[:, 2]) * every * DT
        e_lo = np.repeat(ch[:, 3], ch[:, 2])
        t0 = np.repeat(t[ch[:, 1]], ch[:, 2])
        full = ev_n >= 16
        span = np.where(full, t - E[np.maximum(e_lo + ev_n - 16, 0), 1], t - t0)
        s = S["maps"][mp]
        hours = s["frames"] * DT / 3600
        ns, s_lo = z["ev_ns"], np.repeat(ch[:, 6], ch[:, 2])
        fs = ns >= 8
        span_s = t[fs] - E[z["ev_slow"][(s_lo + ns - 8)[fs]], 1]
        print("| {} | {} | {:.1f} | {} | {} | {:,} | {:.0f} s | {:.0f} s; {:.0f} s; {:.0f} s | {:.0f}% | {:.0f} s |".format(
            mp, s["demos"], hours, s["chains"], s["deaths"], len(t), np.median(clen), np.median(span[full]),
            np.percentile(span[full], 10), np.percentile(span[full], 90), 100 * full.mean(), np.median(span_s)))
        agg["span"].append(span[full][::7])
        agg.setdefault("span_s", []).append(span_s[::7])
        agg["kinds"] += np.array(s["kinds"])
        agg["hours"] += hours
        for k, n in (("a_time", 6), ("b_kind", 4), ("b_time", 6), ("c_hurt", 2), ("d_die", 2)):
            y = z[k]
            tg.setdefault(k, np.zeros(n + 1))
            tg[k][:n] += np.bincount(y[y >= 0], minlength=n)
            tg[k][n] += (y < 0).sum()
        tg.setdefault("e_ok", np.zeros(2))
        tg["e_ok"] += [z["e_ok"].sum(), (~z["e_ok"] & (z["a_time"] != -1)).sum()]
        tg.setdefault("rows", 0)
        tg["rows"] += len(t)
    sp = np.concatenate(agg["span"])
    print("\nall maps: sixteen events reach back {:.0f} s at the median (a quarter of the rows under {:.0f} s, a quarter over {:.0f} s)".format(
        np.median(sp), np.percentile(sp, 25), np.percentile(sp, 75)))
    ss = np.concatenate(agg["span_s"])
    print("eight rare events (pickups, died, spawned) reach back {:.0f} s at the median (a quarter under {:.0f} s, a quarter over {:.0f} s)".format(
        np.median(ss), np.percentile(ss, 25), np.percentile(ss, 75)))
    print("\n| event | a minute |\n|---|---|")
    for k in range(1, len(EVENT_KINDS)):
        print("| {} | {:.2f} |".format(EVENT_KINDS[k], agg["kinds"][k] / (agg["hours"] * 60)))
    print("| all | {:.1f} |".format(agg["kinds"].sum() / (agg["hours"] * 60)))
    print("\nrows {:,}".format(tg["rows"]))
    for k, names in (("a_time", BUCKETS), ("b_kind", PICK_KINDS), ("b_time", BUCKETS), ("c_hurt", ("no", "yes")), ("d_die", ("no", "yes"))):
        c = tg[k]
        print("{}: asked on {:.1f}% of the rows; ".format(k, 100 * c[:-1].sum() / tg["rows"])
              + ", ".join("{} {:.1f}%".format(nm, 100 * v / c[:-1].sum()) for nm, v in zip(names, c[:-1])))
    print("e_where: the enemy out of view and sent by the server on {:.1f}% of the rows where he is out of view".format(
        100 * tg["e_ok"][0] / tg["e_ok"].sum()))


def reach(folder):
    """on the way to a big item (it is his next pickup, within 16 s): is his own last pickup of it still in the record?
    Of the last 16 events, and of the last 8 of the rare kinds."""
    tot = {}
    for f in sorted(glob.glob(os.path.join(folder, "*.npz"))):
        z = np.load(f)
        ch, E, t, ev_n, ev_ns, bk = z["chains"], z["events"], z["t"], z["ev_n"], z["ev_ns"], z["b_kind"]
        kind = E[:, 2].astype(np.int64)
        rank = np.cumsum(np.isin(kind, SLOW_KINDS))                  # rare events up to and with this one
        for name, ek, cls in (("mega", E_MH, 0), ("red armor", E_RA, 1), ("yellow armor", E_YA, 2)):
            a = tot.setdefault(name, np.zeros(5))
            for c in range(len(ch)):
                r0, m, e0, ne = ch[c, 1], ch[c, 2], ch[c, 3], ch[c, 4]
                rows = np.arange(r0, r0 + m)
                rows = rows[bk[rows] == cls]
                idx = np.flatnonzero(kind[e0:e0 + ne] == ek)         # this chain's pickups of the item
                if not len(rows) or not len(idx):
                    a[0] += len(rows)
                    continue
                k = np.searchsorted(idx, ev_n[rows], side="left")    # how many of them the row knows
                had = k > 0
                last = idx[np.maximum(k - 1, 0)]
                behind = ev_n[rows] - last                           # 1 = the newest event
                behind_s = ev_ns[rows] - (rank[e0 + last] - (rank[e0 - 1] if e0 > 0 else 0)) + 1
                a += [len(rows), had.sum(), (had & (behind <= 16)).sum(), (had & (behind_s <= 8)).sum(),
                      np.where(had, t[rows] - E[e0 + last, 1], 0).sum()]
    for name, a in tot.items():
        print("{:13s} rows on the way to it {:9.0f}; he took it before in this chain {:.0f}%; then it is among the last 16 "
              "events {:.0f}%, among the last 8 rare events {:.0f}%; mean time since {:.0f} s".format(
                  name, a[0], 100 * a[1] / a[0], 100 * a[2] / a[1], 100 * a[3] / a[1], a[4] / a[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default=None, help="print what is in a folder of samples")
    ap.add_argument("--reach", default=None, help="print how often his last pickup of an item is still in the record")
    ap.add_argument("--out", default=None)
    ap.add_argument("--maps", default=None, help="comma list; default every folder of sets_lite")
    ap.add_argument("--limit", type=int, default=0, help="at most this many demos a map")
    ap.add_argument("--every", type=int, default=8, help="one row every this many frames")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--show", type=int, default=None, help="print the events of demo number N of --map")
    ap.add_argument("--map", default="bloodrun")
    a = ap.parse_args()
    if a.stats:
        return stats(a.stats)
    if a.reach:
        return reach(a.reach)
    if a.show is not None:
        return show(a.map, a.show, a.every)
    import multiprocessing as mp_
    src = os.path.join(demo_root(), "sets_lite")
    maps = a.maps.split(",") if a.maps else sorted(os.listdir(src))
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    tasks = []
    for mp in maps:
        files = sorted(glob.glob(os.path.join(src, mp, "*.npz")))
        if a.limit:
            files = files[:: max(1, len(files) // a.limit)][:a.limit]
        tasks += [(mp, files[k:k + 40], a.every) for k in range(0, len(files), 40)]
    by_map = {mp: [] for mp in maps}
    with mp_.Pool(a.procs) as pool:
        for n, (mp, res) in enumerate(pool.imap(worker, tasks)):     # in order: the same files give the same output
            by_map[mp] += res
            if n % 10 == 0:
                print("{} of {} batches, {:.0f} s".format(n + 1, len(tasks), time.time() - t0), flush=True)
    allstats = {"every": a.every, "maps": {}}
    for mp in maps:
        s = pack_map(mp, by_map[mp], a.out)
        by_map[mp] = None
        if s:
            allstats["maps"][mp] = s
            print("{:15s} {:5d} demos {:6d} chains {:6d} lives {:9d} rows {:8d} events  ({:.1f} h; holes {} deaths {} cuts {}; "
                  "pickups with no item near {:.1f}%)".format(mp, s["demos"], s["chains"], s["lives"], s["rows"], s["events"],
                                                           s["frames"] * DT / 3600, s["links"]["cont"], s["links"]["spawn"],
                                                           s["links"]["cut"], 100.0 * s["fallback"] / max(1, s["picks"])), flush=True)
    allstats["event_kinds"] = EVENT_KINDS
    json.dump(allstats, open(os.path.join(a.out, "stats.json"), "w"), indent=1)
    print("done in {:.0f} s".format(time.time() - t0))


if __name__ == "__main__":
    main()

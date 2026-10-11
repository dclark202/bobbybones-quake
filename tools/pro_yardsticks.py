"""Yardsticks from the pro demos to judge a model's play against, beyond speed (tools/speed_profile.py):
  1 spam (shots with no enemy in view)       2 weapon combinations          3 play by score and time
  4 item timing                              5 extras, marked as such in the tables
  6 how predictable he is: his places, his height, his ways between the big items, his standing
  7 aggression by advantage: what he does in the 3 s after the enemy comes into view, by his situation
(the strength of a position, the eighth, is in tools/pro_places.py, from rows this tool writes).

    python tools/pro_yardsticks.py                              all six maps, every demo -> docs/pro_yardsticks.json, tables on stdout
    python tools/pro_yardsticks.py --map bloodrun --limit 100   a sample (shown only; --json <file> writes it)
    python tools/pro_yardsticks.py --check                      how good the game clock, the score and the pickups read from a demo are
    python tools/pro_yardsticks.py --show docs/pro_yardsticks.json

Input: <demo root>/demos/<map>/*.dm_91|dm_90|dm_73 (demo root: the folder named in data/demo_root.txt), parsed on the fly
with tools/demodump (--procs N processes, one map's collision in each). Per demo the counts are kept in
<demo root>/yardsticks/<map>/<demo>.json (--redo counts again; a new VERSION does too), and for tools/pro_places.py a
map's blind shots, sightings and frames with the enemy in view in <demo root>/yardsticks/blind_<map>.npy, sight_<map>.npy
and view_<map>.npy. The whole archive (4,166 demos) takes under three minutes with ten processes. No player names are
read from a demo or written anywhere.

The measuring is apart from the reading of a demo: measure() takes a record, frame by frame (make_record(): time, the
player's position, velocity, view, weapon, shots, health, armor, score, the enemy's position where it is known, who
leads, the game clock), so that the simulator's games go through the same functions. Whether the enemy is in view is
worked out here for both, from the positions and the map (see()). Another player's games:

    import pro_yardsticks as Y
    info = Y.map_info(world, "bloodrun")                 # world: the process's qsim.World of that map
    T = Y.new_tally()
    for game in games:                                   # one record a game and a player
        t, rows = Y.measure(Y.make_record(...), world, info)
        Y.add_tally(T, t)
    his = Y.report(T, zrange=Y.zranges())                # the pros' heights for "the lowest third"; the same keys as a map of the json

What is read from a demo, and how
  followed player   the player state of every snapshot. A demo is one view; a spectator's demo cuts between the two
                    players. Every stretch between cuts is measured for the player followed in it ("P").
  enemy             the other player's entity while the server sent it (roughly: while he could be seen or was near);
                    a corpse is not him. Nothing is known of him otherwise, and never his health or armor.
  shots             the ammunition of a weapon going down between two snapshots (it does on the snapshot his own missile
                    first appears in; his view on that snapshot is the missile's direction to 0.1 to 0.6 degrees median).
  score             his own: the player state's score. Who leads: the player state's rank (first, second, or tied),
                    which the server sorts from both scores: exact. The enemy's score itself is an estimate (P's deaths
                    less his own accidents, the enemy's last score seen before a cut, put right where the rank
                    contradicts it): the death notices are in a demo, but tools/demodump does not write which event an
                    event entity is once the parser library has seen it, so they cannot be told apart reliably.
  game clock        the level's start time is a config string, and tools/demodump writes only the server's two info
                    strings and the players', as they were at the demo's start. Read instead: the game begins with a restart of the map, which leaves a hole of 0.4 s in the
                    snapshots after which his score, deaths and hits are zero; the clock is the server time since then.
                    The game ends at the first intermission snapshot. A demo that begins in a running game has no clock
                    (it is left out of the tables by time); so has a game whose length fits no ten minutes plus overtimes
                    of two (a timeout stopped the clock somewhere).
  pickups           his health or armor going up while he stands at the item's spot (the map's own items, dropped to the
                    floor as the game does).
"""
import argparse
import glob
import json
import multiprocessing as mp_
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged"
VERSION = 11                                                    # of the counts kept per demo: a change here counts every demo again

# ---------------------------------------------------------------------------------------------------------------------
# the record and what is measured on it (no demo below this line until "reading a demo")
# ---------------------------------------------------------------------------------------------------------------------
WEAPONS = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")           # the simulator's order (duel_env.WEAPONS)
RL, RG, LG, MG, SG, GL, PG, HMG, GAUNT = range(9)
W_NAMES = dict(rl="rockets", gl="grenades", pg="plasma", rg="rail", lg="lightning", mg="machine gun", sg="shotgun")
SPAM_W = ("rl", "gl", "pg", "rg", "lg", "mg", "sg")
PROJ = {RL: 1000.0, GL: 700.0, PG: 2000.0}                      # units a second
FOV_COS = float(np.cos(np.radians(55.0)))                      # his sight cone, as the simulator's (duel_env.FOV_COS)
SIGHT = 4000.0
BLIND_S = 1.0                                                  # a shot is blind when the enemy has not been in view this long
MET_S, MET_R = 2.0, 300.0                                      # "the spam met him": in view within this time, this near where it landed
FEET_R = 150.0                                                 # a shot that lands this near himself is no spam: a rocket jump, a shot at the floor
COMBO_S = 1.5
LATE = 420.0                                                   # the game clock's split: before and after 7:00
STACK = 150.0
BACK_S, BACK_R = 2.0, 150.0                                    # at an item's return: within this time either side, this near
TAKE_R, TAKE_Z = 60.0, 80.0                                    # a pickup: his health or armor rises this near the item
RETURN = dict(mega=35.0, red=25.0, yellow=25.0, green=25.0)
ITEM_KIND = {"item_health_mega": "mega", "item_armor_body": "red", "item_armor_combat": "yellow", "item_armor_jacket": "green"}
GL_UP, GL_BOUNCE, GL_FUSE, GRAVITY = 0.2, 0.65, 2.5, 800.0     # a grenade, as the simulator flies it (duel_env.py)
CELL, CELL_Z = 192.0, 96.0                                     # the cells his time is counted in (how predictable his places are)
TOP_CELLS, CELL_SHARE = 8, 0.8
CELL_MIN_S = 180.0                                             # a player's own numbers need this much of his time in a record
HIGHER = 48.0
STAND = 50.0                                                   # units a second: under it he stands
BIG = {"item_health_mega": "MH", "item_armor_body": "RA", "item_armor_combat": "YA", "weapon_rocketlauncher": "RL",
       "weapon_railgun": "RG", "weapon_lightning": "LG"}       # the items a trip goes from and to
TRIP_MAX_S, TRIP_MIN_S, TRIP_PTS = 20.0, 1.0, 16
WAY_D = 200.0                                                  # two trips are the same way when their paths lie this near each other
WAY_MIN_TRIPS, WAY_MIN_SHARE = 30, 0.05                        # a pair counts from this many trips; a way from this share of them
SIGHT_OUT_S, SIGHT_S, SIGHT_FIRE_S, SIGHT_BREAK_S, SIGHT_AFTER_S = 1.0, 3.0, 1.0, 0.5, 10.0      # a sighting and what is read after it
PUSH = 150.0                                                   # he "pushes" when he closes faster than this over the 3 s
STACK_BANDS = ("under 60", "60 to 125", "over 125")
OWN_BANDS = ("no big weapon", "rockets, lightning or rail")
FRAG_BANDS = ("fragged him under 10 s ago", "10 to 25 s ago", "over 25 s ago or not yet")
ENEMY_BANDS = ("enemy holds a small weapon", "enemy holds a big weapon", "enemy's weapon unknown")
DIST_BANDS = ("under 400 units", "400 to 800", "over 800")
BIG_W = (RL, LG, RG)
VIEW_EVERY = 8                                                 # every this many frames with the enemy in view, a row for the places
SOLID = 1
LEADS = {1: "ahead", 0: "level", -1: "behind"}
STATES = [l + ", " + p for l in ("ahead", "level", "behind") for p in ("before 7:00", "after 7:00")]
STATE_KEYS = ("time", "alive", "inview", "toward", "dist", "frags", "deaths", "travel_t", "travel_d", "stack", "fire",
              "blind_rl", "blind_gl", "blind_pg", "rl", "gl", "pg", "away_rl", "away_gl", "away_pg")


def make_record(t, pos, vel, yaw, pitch, weapon, shots, health, armor, score, enemy, enemy_score=None, lead=None,
                clock=None, alive=None, eye_h=None, enemy_air=None, hits=None, seg=None, ammo=None, client=None, owned=None,
                enemy_weapon=None):
    """One player's game, frame by frame, as measure() wants it. Arrays of N frames in the order of time:
      t          seconds (any origin)                     pos, vel   (N, 3) units, units a second
      yaw, pitch degrees (pitch: looking down is positive, as the game's)
      weapon     in hand, an index of WEAPONS             shots      (K, 3) whole numbers: frame, weapon, how many left on it
      health, armor, score                                enemy      (N, 3) his position, NaN where it is not known
      enemy_score (N,) or lead (N,): +1 P leads, 0 level, -1 behind
      clock      seconds on the game clock (NaN where unknown; None: t from its first frame)
      alive      (None: health > 0)                       eye_h      height of his eye over his origin (None: 26)
      enemy_air  1 off the ground, 0 on it, -1 unknown    hits       his hits so far, a counter (None: not known)
      seg        a number per unbroken stretch of one player (None: one stretch)
      ammo       (N, 9) his ammunition by weapon in the order of WEAPONS (None: no weapon pickups are seen, so no trips
                 from and to weapons)                     client     who P is, a number (None: one player throughout)
      owned      (N, 9) which weapons he owns (None: those he has ammunition for)
      enemy_weapon (N,) the weapon in the enemy's hand, an index of WEAPONS, -1 where it is not known (None: never)"""
    n = len(t)
    r = dict(t=np.asarray(t, np.float64), pos=np.asarray(pos, np.float32).reshape(n, 3),
             vel=np.asarray(vel, np.float32).reshape(n, 3), yaw=np.asarray(yaw, np.float32),
             pitch=np.asarray(pitch, np.float32), weapon=np.asarray(weapon, np.int64),
             shots=np.asarray(shots, np.int64).reshape(-1, 3), health=np.asarray(health, np.float32),
             armor=np.asarray(armor, np.float32), score=np.asarray(score, np.int64),
             enemy=np.asarray(enemy, np.float32).reshape(n, 3))
    r["alive"] = (r["health"] > 0) if alive is None else np.asarray(alive, bool)
    r["eye_h"] = np.full(n, 26.0, np.float32) if eye_h is None else np.asarray(eye_h, np.float32)
    r["enemy_air"] = np.full(n, -1, np.int64) if enemy_air is None else np.asarray(enemy_air, np.int64)
    r["hits"] = None if hits is None else np.asarray(hits, np.int64)
    r["seg"] = np.zeros(n, np.int64) if seg is None else np.asarray(seg, np.int64)
    r["ammo"] = None if ammo is None else np.asarray(ammo, np.float32).reshape(n, len(WEAPONS))
    r["client"] = np.zeros(n, np.int64) if client is None else np.asarray(client, np.int64)
    r["owned"] = None if owned is None else np.asarray(owned, bool).reshape(n, len(WEAPONS))
    r["enemy_weapon"] = np.full(n, -1, np.int64) if enemy_weapon is None else np.asarray(enemy_weapon, np.int64)
    if lead is None:
        lead = np.sign(r["score"] - np.asarray(enemy_score, np.int64))
    r["lead"] = np.asarray(lead, np.int64)
    r["enemy_score"] = None if enemy_score is None else np.asarray(enemy_score, np.int64)
    r["clock"] = (r["t"] - r["t"][0]).astype(np.float32) if clock is None else np.asarray(clock, np.float32)
    same = np.zeros(n, bool)
    same[:-1] = r["seg"][1:] == r["seg"][:-1]
    w = np.zeros(n, np.float64)
    w[:-1] = np.diff(r["t"])
    step = float(np.median(w[:-1][same[:-1]])) if same[:-1].any() else 0.025
    r["w"] = np.where(same, np.clip(w, 0.0, 0.1), step)        # the seconds a frame stands for
    r["first"] = np.concatenate([[True], ~same[:-1]])          # a stretch begins
    return r


def _fwd(yaw, pitch):
    y, p = np.radians(yaw), np.radians(pitch)
    return np.stack([np.cos(p) * np.cos(y), np.cos(p) * np.sin(y), -np.sin(p)], -1).astype(np.float32)


def see(rec, world):
    """adds `inview` (the enemy inside his sight cone, under SIGHT units, a clear line from his eye to the enemy's
    chest or head through the map) and `since` (seconds since he last was; a stretch begins at 0: what came before
    it is not known, so its first second has no blind shots)"""
    n = len(rec["t"])
    eye = rec["pos"] + np.stack([np.zeros(n), np.zeros(n), rec["eye_h"]], 1).astype(np.float32)
    have = rec["alive"] & np.isfinite(rec["enemy"][:, 0])
    en = np.where(have[:, None], rec["enemy"], 0.0).astype(np.float32)
    to = en + np.array([0, 0, 8.0], np.float32) - eye
    dist = np.linalg.norm(to, axis=1) + 1e-6
    cosang = (to * _fwd(rec["yaw"], rec["pitch"])).sum(1) / dist
    inview = have & (cosang > FOV_COS) & (dist < SIGHT)
    idx = np.nonzero(inview)[0]
    if world is not None and len(idx):
        f1 = world.lines(eye[idx], en[idx] + np.array([0, 0, 8.0], np.float32), mask=SOLID)
        f2 = world.lines(eye[idx], en[idx] + np.array([0, 0, 26.0], np.float32), mask=SOLID)
        inview[idx] = (f1 >= 0.999) | (f2 >= 0.999)
    rec["eye"], rec["inview"], rec["dist"] = eye, inview, np.where(have, dist, np.nan)
    last = np.where(inview | rec["first"], rec["t"], -np.inf)
    rec["since"] = rec["t"] - np.maximum.accumulate(last)
    return rec


def grenade_end(world, eye, fdir):
    """where a grenade fired along fdir lies when its fuse ends: the simulator's own flight (700 units a second, lofted by
    0.2, gravity, each bounce keeps 0.65, 2.5 s), in steps of 25 ms. A grenade that meets a player goes off there: that
    is not in this."""
    p = (eye + fdir * 14.0).astype(np.float32)
    d = fdir.astype(np.float64).copy()
    d[2] += GL_UP
    v = d / np.linalg.norm(d) * PROJ[GL]
    left = GL_FUSE
    while left > 0:
        v[2] -= GRAVITY * 0.025
        p1 = p + (v * 0.025).astype(np.float32)
        tr = world.trace(p, p1, mask=SOLID)
        if tr["fraction"] < 1.0:
            nrm = tr["normal"].astype(np.float64)
            v = (v - 2.0 * float(v @ nrm) * nrm) * GL_BOUNCE
            p = (tr["endpos"] + tr["normal"] * 0.5).astype(np.float32)
            if nrm[2] > 0.2 and np.linalg.norm(v) < 40:
                break
        else:
            p = p1
        left -= 0.025
    return p


def landings(rec, world, frames, weapons):
    """where the shots of these frames come down: rockets and plasma along his view from his eye to the first wall,
    grenades by grenade_end()"""
    out = np.zeros((len(frames), 3), np.float32)
    if not len(frames):
        return out
    fd = _fwd(rec["yaw"][frames], rec["pitch"][frames])
    eye = rec["eye"][frames]
    line = weapons != GL
    if line.any():
        fr = world.lines(eye[line], eye[line] + fd[line] * 8192.0, mask=SOLID)
        out[line] = eye[line] + fd[line] * (8192.0 * fr[:, None])
    for k in np.nonzero(~line)[0]:
        out[k] = grenade_end(world, eye[k], fd[k])
    return out


def new_tally():
    return dict(demos=0, stretches=0, seconds=0.0, alive=0.0, clock_seconds=0.0,
                spam={w: dict(shots=0, blind=0, each=[]) for w in SPAM_W},     # each: a blind shot's distance, met, met in 1 s, near, hit
                combo={a: dict(n=0, rg=0, lg=0, air=0, air_known=0, gap=[]) for a in ("rl", "gl")},
                view_air=dict(known=0.0, air=0.0),
                state={s: {k: 0.0 for k in STATE_KEYS} for s in STATES + ["ahead", "level", "behind", "all",
                                                                          "stack under 100", "stack 100 to 149", "stack 150 or more"]},
                items={k: dict(pickups=0, counted=0, back=0, died=0, took=0, gaps=[]) for k in RETURN},
                cells={}, cells_own=[], zhist={}, height=dict(view=0.0, higher=0.0, lower=0.0), stand=dict(time=0.0, longest=[]),
                trips={}, aggro={}, aggro_dist={})


def add_tally(a, b):
    """a += b (numbers add, lists grow)"""
    for k, v in b.items():
        if isinstance(v, dict):
            add_tally(a.setdefault(k, {}), v)
        elif isinstance(v, list):
            a.setdefault(k, []).extend(v)
        else:
            a[k] = a.get(k, 0) + v
    return a


def measure(rec, world, info):
    """rec (make_record) on a map (qsim.World; info: map_info(world, name)) -> (tally, rows).
    rows: `blind` (a blind shot: weapon, where it landed (3), where he stood (3), met, hit or -1 for not known), `sight`
    and `view` (SIGHT_COLS, VIEW_COLS say what a row holds), for tools/pro_places.py"""
    see(rec, world)
    T = new_tally()
    items = info["items"]
    t, w, alive, inview, since, seg = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["since"], rec["seg"]
    n = len(t)
    T["demos"], T["stretches"] = 1, int(rec["first"].sum())
    T["seconds"], T["alive"] = float(w.sum()), float(w[alive].sum())
    same = ~rec["first"]                                        # frame i-1 is of the same stretch
    seg_end = np.zeros(n, np.int64)                             # the last frame of each frame's stretch
    ends = np.nonzero(np.concatenate([rec["first"][1:], [True]]))[0]
    starts = np.nonzero(rec["first"])[0]
    for a, b in zip(starts, ends):
        seg_end[a:b + 1] = b
    hsp = np.hypot(rec["vel"][:, 0], rec["vel"][:, 1])
    stack = rec["health"] + rec["armor"]
    en = rec["enemy"]
    rel = en - rec["pos"]
    toward = (rec["vel"] * rel).sum(1) / (np.linalg.norm(rel, axis=1) + 1e-6)
    # ---- shots: blind or not
    sh = rec["shots"]
    sh = sh[alive[sh[:, 0]]] if len(sh) else sh
    blind = since[sh[:, 0]] >= BLIND_S if len(sh) else np.zeros(0, bool)
    for wq, name in enumerate(WEAPONS):
        if name in T["spam"] and len(sh):
            m = sh[:, 1] == wq
            T["spam"][name]["shots"] = int(sh[m, 2].sum())
            T["spam"][name]["blind"] = int(sh[m & blind, 2].sum())
    bl = sh[blind & np.isin(sh[:, 1], (RL, GL, PG))] if len(sh) else np.zeros((0, 3), np.int64)
    rows = []
    away_n = {w_: np.zeros(n) for w_ in (RL, GL, PG)}           # blind shots a frame that land FEET_R or more from himself
    if len(bl) and world is not None:
        land = landings(rec, world, bl[:, 0], bl[:, 1])
        for (i, wq, cnt), L in zip(bl, land):
            sp = T["spam"][WEAPONS[wq]]
            d = float(np.linalg.norm(L - rec["eye"][i]))
            if d >= FEET_R:
                away_n[int(wq)][i] += cnt
            j1 = min(int(np.searchsorted(t, t[i] + MET_S, side="right")), seg_end[i] + 1)
            near = np.linalg.norm(en[i + 1:j1] - L, axis=1) <= MET_R          # (NaN where he is not known: False)
            seen = near & inview[i + 1:j1]
            met = bool(seen.any())
            met1 = bool((seen & (t[i + 1:j1] <= t[i] + 1.0)).any())
            hit = -1
            if rec["hits"] is not None:
                fl = d / PROJ[wq]
                lo, hi = (t[i] + 0.05, t[i] + GL_FUSE + 0.2) if wq == GL else (t[i] + fl - 0.15, t[i] + fl + 0.2)
                a = max(i, int(np.searchsorted(t, lo, side="left")) - 1)
                b = min(int(np.searchsorted(t, hi, side="right")) - 1, seg_end[i])
                if b > a:
                    hit = int(rec["hits"][b] > rec["hits"][a])
            sp["each"] += [[round(d), int(met), int(met1), int(bool(near.any())), hit]] * int(cnt)
            rows += [[int(wq), *[round(float(x)) for x in L], *[round(float(x)) for x in rec["pos"][i]], int(met), hit]] * int(cnt)
    # ---- combinations: the first rail or lightning shot after a rocket (a grenade) fired with the enemy in view
    if len(sh):
        order = np.argsort(sh[:, 0], kind="stable")
        prev = None
        for i, wq, cnt in sh[order]:
            if prev is not None and wq in (RG, LG) and prev[1] in (RL, GL) and seg[prev[0]] == seg[i] and \
                    t[i] - t[prev[0]] <= COMBO_S and since[prev[0]] <= 0.2:
                c = T["combo"]["rl" if prev[1] == RL else "gl"]
                c["n"] += 1
                c["rg" if wq == RG else "lg"] += 1
                c["gap"].append(round(float(t[i] - t[prev[0]]), 3))
                if rec["enemy_air"][i] >= 0:
                    c["air_known"] += 1
                    c["air"] += int(rec["enemy_air"][i] == 1)
            prev = (i, wq)
    known = inview & (rec["enemy_air"] >= 0)
    T["view_air"] = dict(known=float(w[known].sum()), air=float(w[known & (rec["enemy_air"] == 1)].sum()))
    # ---- by who leads and the game clock (and by his own stack)
    lead, clock = rec["lead"], rec["clock"]
    frag = np.zeros(n, bool)
    frag[1:] = (rec["score"][1:] > rec["score"][:-1]) & same[1:]
    died = np.zeros(n, bool)
    died[1:] = alive[:-1] & ~alive[1:] & same[1:]
    before = np.maximum(np.arange(n) - 1, 0)                    # a frag and a death belong to the state of the frame before
    fire = np.zeros(n)
    blind_n = {w_: np.zeros(n) for w_ in (RL, GL, PG)}
    all_n = {w_: np.zeros(n) for w_ in (RL, GL, PG)}
    if len(sh):
        np.add.at(fire, sh[:, 0], sh[:, 2])
        for w_ in (RL, GL, PG):
            m = sh[:, 1] == w_
            np.add.at(all_n[w_], sh[m, 0], sh[m, 2])
            np.add.at(blind_n[w_], sh[m & blind, 0], sh[m & blind, 2])
    masks = {"all": np.ones(n, bool)}
    hasclock = np.isfinite(clock)
    T["clock_seconds"] = float(w[hasclock].sum())
    for lv, ln in LEADS.items():
        masks[ln] = lead == lv
        masks[ln + ", before 7:00"] = (lead == lv) & hasclock & (clock < LATE)
        masks[ln + ", after 7:00"] = (lead == lv) & hasclock & (clock >= LATE)
    masks["stack under 100"] = alive & (stack < 100)
    masks["stack 100 to 149"] = alive & (stack >= 100) & (stack < STACK)
    masks["stack 150 or more"] = alive & (stack >= STACK)
    for name, m in masks.items():
        s = T["state"][name]
        ma, mv, mt = m & alive, m & inview, m & alive & ~inview
        s["time"], s["alive"], s["inview"] = float(w[m].sum()), float(w[ma].sum()), float(w[mv].sum())
        s["toward"], s["dist"] = float((toward[mv] * w[mv]).sum()), float((rec["dist"][mv] * w[mv]).sum())
        s["frags"], s["deaths"] = int(frag[m[before]].sum()), int(died[m[before]].sum())
        s["travel_t"], s["travel_d"] = float(w[mt].sum()), float((hsp[mt] * w[mt]).sum())
        s["stack"] = float(w[ma & (stack >= STACK)].sum())
        s["fire"] = float(fire[ma].sum())
        for w_, nm in ((RL, "rl"), (GL, "gl"), (PG, "pg")):
            s[nm], s["blind_" + nm] = float(all_n[w_][ma].sum()), float(blind_n[w_][ma].sum())
            s["away_" + nm] = float(away_n[w_][ma].sum())
    # ---- item timing
    dh = np.zeros(n)
    da = np.zeros(n)
    ok = same & alive & np.concatenate([[False], alive[:-1]])
    dh[1:] = np.diff(rec["health"])
    da[1:] = np.diff(rec["armor"])
    for it in items:
        col = dh if it["kind"] == "mega" else da
        at = ok & (col > 0) & (np.hypot(rec["pos"][:, 0] - it["pos"][0], rec["pos"][:, 1] - it["pos"][1]) < TAKE_R) & \
            (np.abs(rec["pos"][:, 2] - it["pos"][2]) < TAKE_Z)
        for o in it["rivals"]:                                  # another item of its sort is nearer: that one was taken
            at &= np.linalg.norm(rec["pos"] - it["pos"], axis=1) <= np.linalg.norm(rec["pos"] - o, axis=1)
        picks = np.nonzero(at)[0]
        if len(picks) > 1:                                      # (one pickup cannot be within 5 s of the one before)
            picks = picks[np.concatenate([[True], np.diff(t[picks]) > 5.0])]
        I = T["items"][it["kind"]]
        I["pickups"] += len(picks)
        near = alive & (np.linalg.norm(rec["pos"] - it["pos"], axis=1) <= BACK_R)
        R = RETURN[it["kind"]]
        for q, i in enumerate(picks):
            if q + 1 < len(picks) and seg[picks[q + 1]] == seg[i]:
                I["gaps"].append(round(float(t[picks[q + 1]] - t[i]), 2))
            e = seg_end[i]
            if t[e] < t[i] + R + BACK_S:                        # the stretch ends before the item is back: not counted
                continue
            a, b = np.searchsorted(t, [t[i] + R - BACK_S, t[i] + R + BACK_S])
            I["counted"] += 1
            I["back"] += int(near[a:b + 1].any())
            I["died"] += int((~alive[i:a]).any())
            I["took"] += int(q + 1 < len(picks) and picks[q + 1] <= e and t[picks[q + 1]] <= t[i] + R + 5.0)
    predictable(rec, info, T, dh, da, ok, seg_end)
    sight, view = sightings(rec, T, seg_end, frag, died, fire)
    return T, dict(blind=rows, sight=sight, view=view)


SIGHT_COLS = ("x", "y", "z", "stack band", "owns a big weapon", "frag band", "enemy weapon band", "lead", "speed toward him over 3 s",
              "fired within 1 s", "after 3 s: 0 still in view, 1 view broken, 2 he fragged him, 3 he died", "frags in 10 s (-1: not known)",
              "deaths in 10 s", "weapon in hand", "distance")
VIEW_COLS = ("x", "y", "z", "weapon in hand", "fired", "height: 1 higher, 0 level, -1 lower", "distance", "milliseconds this row stands for")


def sightings(rec, T, seg_end, frag, died, fire):
    """the seventh group, aggression by advantage: every time the enemy comes into his view after SIGHT_OUT_S or more
    out of it, what he does in the next SIGHT_S seconds, by his situation (into T["aggro"]). Returns the sightings as
    rows (SIGHT_COLS) and the frames with the enemy in view thinned to rows (VIEW_COLS), for the places."""
    t, w, alive, inview, since, pos, vel = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["since"], rec["pos"], rec["vel"]
    n = len(t)
    stack = rec["health"] + rec["armor"]
    own = (rec["ammo"] > 0) if rec["ammo"] is not None else None
    if own is not None and rec["owned"] is not None:
        own = own & rec["owned"]
    cfrag, cdied, cfire = np.cumsum(frag), np.cumsum(died), np.cumsum(fire > 0)
    lf = np.full(n, -np.inf)                                    # when he last fragged him, within the stretch (what came before it is not known)
    st_ = np.nonzero(rec["first"])[0]
    for a, b in zip(st_, np.concatenate([st_[1:], [n]])):
        lf[a:b] = np.maximum.accumulate(np.where(frag[a:b], t[a:b], -np.inf))
    starts = np.nonzero(inview & ~rec["first"] & (np.concatenate([[0.0], since[:-1]]) >= SIGHT_OUT_S - 0.03))[0]
    rows = []
    for i in starts:
        e = min(int(np.searchsorted(t, t[i] + SIGHT_S, side="right")) - 1, int(seg_end[i]))
        if e <= i:
            continue
        dead = np.nonzero(~alive[i:e + 1])[0]
        ea = i + int(dead[0]) - 1 if len(dead) else e           # his last frame alive in the 3 s
        en = rec["enemy"][i:ea + 1].copy()
        known = np.isfinite(en[:, 0])
        idx = np.maximum.accumulate(np.where(known, np.arange(len(en)), 0))
        en = en[idx]                                            # where he is not known: where he was last known
        rel = en - pos[i:ea + 1]
        tw = (vel[i:ea + 1] * rel).sum(1) / (np.linalg.norm(rel, axis=1) + 1e-6)
        ww = w[i:ea + 1]
        toward = float((tw * ww).sum() / max(1e-6, ww.sum()))
        f1 = min(int(np.searchsorted(t, t[i] + SIGHT_FIRE_S, side="right")) - 1, e)
        fired = int(cfire[f1] - cfire[i - 1] > 0)
        if cfrag[e] > cfrag[i]:
            after = 2
        elif len(dead):
            after = 3
        else:
            out = ~inview[i:e + 1]
            after, acc = 0, 0.0
            for q in range(len(out)):                           # the view broken for SIGHT_BREAK_S at a stretch
                acc = acc + w[i + q] if out[q] else 0.0
                if acc >= SIGHT_BREAK_S:
                    after = 1
                    break
        e10 = int(np.searchsorted(t, t[i] + SIGHT_AFTER_S, side="right")) - 1
        if e10 <= seg_end[i]:
            f10, d10 = int(cfrag[e10] - cfrag[i]), int(cdied[e10] - cdied[i])
        else:
            f10, d10 = -1, 0
        sb = 0 if stack[i] < 60 else 1 if stack[i] <= 125 else 2
        ob = int(own[i, list(BIG_W)].any()) if own is not None else 1
        ago = t[i] - lf[i]
        fb = 0 if ago < 10.0 else 1 if ago <= 25.0 else 2
        ew = int(rec["enemy_weapon"][i])
        eb = 2 if ew < 0 else int(ew in BIG_W)
        ld = int(rec["lead"][i])
        dist = float(rec["dist"][i])
        db = 0 if dist < 400 else 1 if dist <= 800 else 2
        for tab, key in (("aggro", "{}|{}|{}|{}|{}".format(sb, ob, fb, eb, ld)), ("aggro_dist", "{}|{}".format(sb, db))):
            c = T[tab].setdefault(key, dict(n=0, toward=0.0, push=0, fire=0, broke=0, frag=0, died=0, known10=0, frags10=0, deaths10=0))
            c["n"] += 1
            c["toward"] += toward
            c["push"] += int(toward > PUSH)
            c["fire"] += fired
            c["broke"] += int(after == 1)
            c["frag"] += int(after == 2)
            c["died"] += int(after == 3)
            if f10 >= 0:
                c["known10"] += 1
                c["frags10"] += f10
                c["deaths10"] += d10
        rows.append([int(round(float(x))) for x in pos[i]] + [sb, ob, fb, eb, ld, int(round(toward)), fired, after, f10, d10, int(rec["weapon"][i]),
                                                                int(round(dist))])
    # ---- the frames with the enemy in view, thinned
    v = np.nonzero(inview)[0]
    view = []
    if len(v):
        cw = np.concatenate([[0.0], np.cumsum(w[v])])
        cf = np.concatenate([[0], np.cumsum(fire[v] > 0)])
        dz = pos[v, 2] - rec["enemy"][v, 2]
        for a in range(0, len(v), VIEW_EVERY):
            b = min(a + VIEW_EVERY, len(v))
            i = v[a]
            view.append([int(round(float(x))) for x in pos[i]] + [int(rec["weapon"][i]), int(cf[b] - cf[a] > 0),
                         int(dz[a] >= HIGHER) - int(dz[a] <= -HIGHER), int(round(float(rec["dist"][i]))), int(round(1000.0 * (cw[b] - cw[a])))])
    return rows, view


def _spread(sec):
    """seconds by cell -> the share of the time in the TOP_CELLS most used, the number of cells that hold CELL_SHARE of
    it, the entropy of the time over cells in bits"""
    v = np.sort(np.asarray(list(sec), np.float64))[::-1]
    v = v[v > 0]
    p = v / v.sum()
    return [float(p[:TOP_CELLS].sum()), int(np.searchsorted(np.cumsum(p), CELL_SHARE - 1e-9) + 1), float(-(p * np.log2(p)).sum())]


def _resample(path, k=TRIP_PTS):
    """k points evenly along a path"""
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    if d[-1] <= 0:
        return np.repeat(path[:1], k, 0)
    at = np.linspace(0.0, d[-1], k)
    return np.stack([np.interp(at, d, path[:, c]) for c in range(3)], 1)


def predictable(rec, info, T, dh, da, ok, seg_end):
    """the sixth group: how predictable his places and ways are (his time over cells, his height, his ways between the
    big items, his standing), into the tally T"""
    t, w, alive, pos, seg = rec["t"], rec["w"], rec["alive"], rec["pos"], rec["seg"]
    name = info["name"]
    # ---- his time over cells, pooled and for each player with enough time of his own
    cx = np.floor(pos[:, 0] / CELL).astype(np.int64)
    cy = np.floor(pos[:, 1] / CELL).astype(np.int64)
    cz = np.floor(pos[:, 2] / CELL_Z).astype(np.int64)
    key = (cx + 512) * 1048576 + (cy + 512) * 1024 + (cz + 512)
    for c in np.unique(rec["client"]):
        m = alive & (rec["client"] == c)
        if not m.any():
            continue
        u, inv = np.unique(key[m], return_inverse=True)
        sec = np.bincount(inv, weights=w[m], minlength=len(u))
        for k_, s_ in zip(u.tolist(), sec.tolist()):
            kk = "{}:{}:{}:{}".format(name, (k_ >> 20) - 512, ((k_ >> 10) & 1023) - 512, (k_ & 1023) - 512)
            T["cells"][kk] = round(T["cells"].get(kk, 0.0) + s_, 3)
        if sec.sum() >= CELL_MIN_S:
            T["cells_own"].append([name] + _spread(sec) + [round(float(sec.sum()), 1)])
    zb = np.floor(pos[alive, 2] / 8.0).astype(np.int64)
    if len(zb):
        u, inv = np.unique(zb, return_inverse=True)
        for k_, s_ in zip(u.tolist(), np.bincount(inv, weights=w[alive], minlength=len(u)).tolist()):
            T["zhist"]["{}:{}".format(name, k_)] = round(s_, 3)
    # ---- his height beside the enemy's while he has him in view
    v = rec["inview"]
    dz = np.where(v, pos[:, 2] - rec["enemy"][:, 2], 0.0)
    T["height"] = dict(view=float(w[v].sum()), higher=float(w[v & (dz >= HIGHER)].sum()), lower=float(w[v & (dz <= -HIGHER)].sum()))
    # ---- standing
    sp = np.linalg.norm(rec["vel"], axis=1)
    st = alive & (sp < STAND)
    T["stand"]["time"] = float(w[st].sum())
    run = np.zeros(len(t))                                      # the seconds of the stand up to each frame
    acc = 0.0
    for i in np.nonzero(st)[0]:
        acc = acc + w[i] if (i > 0 and st[i - 1] and not rec["first"][i]) else w[i]
        run[i] = acc
    minute = np.floor((t - t[0]) / 60.0).astype(np.int64)
    longest = []
    for m_ in np.unique(minute):
        mm = minute == m_
        if w[mm & alive].sum() >= 30.0:                          # (a minute counts with half of it alive)
            longest.append(round(float(run[mm].max()), 2))
    T["stand"]["longest"] = longest
    # ---- trips between the big items: from one pickup to the next pickup of another of them, alive, TRIP_MAX_S at most
    ev = []
    for k, it in enumerate(info["big"]):
        if it["col"] == "health":
            col = dh
        elif it["col"] == "armor":
            col = da
        elif rec["ammo"] is not None:
            col = np.zeros(len(t))
            col[1:] = np.diff(rec["ammo"][:, it["col"]])
        else:
            continue
        at = ok & (col > 0) & (np.hypot(pos[:, 0] - it["pos"][0], pos[:, 1] - it["pos"][1]) < TAKE_R) & \
            (np.abs(pos[:, 2] - it["pos"][2]) < TAKE_Z)
        for o in it["rivals"]:
            at &= np.linalg.norm(pos - it["pos"], axis=1) <= np.linalg.norm(pos - o, axis=1)
        ev += [(int(i), k) for i in np.nonzero(at)[0]]
    ev.sort()
    dead = np.concatenate([[0], np.cumsum(~alive)])
    for (i, a), (j, b) in zip(ev[:-1], ev[1:]):
        if a == b or seg[i] != seg[j] or seg_end[i] < j or dead[j + 1] != dead[i] or not (TRIP_MIN_S <= t[j] - t[i] <= TRIP_MAX_S):
            continue
        kk = "{}:{}>{}".format(name, info["big"][a]["label"], info["big"][b]["label"])
        T["trips"].setdefault(kk, []).append([int(round(x)) for x in _resample(pos[i:j + 1].astype(np.float64)).ravel()] + [round(float(t[j] - t[i]), 2)])


def ways(trips):
    """the trips of one pair (rows: TRIP_PTS points and the seconds) -> the number of trips on each of their ways, the
    most used first. A trip joins the way whose first trip lies nearest, within WAY_D units on average along the path,
    else it opens a new way; then every trip goes to the nearest way once more."""
    P = np.asarray(trips, np.float64)[:, :TRIP_PTS * 3].reshape(len(trips), TRIP_PTS, 3)
    lead = [0]
    for i in range(1, len(P)):
        d = np.linalg.norm(P[lead] - P[i], axis=2).mean(1)
        if d.min() > WAY_D:
            lead.append(i)
    n = np.zeros(len(lead), np.int64)
    for a in range(0, len(P), 2000):
        d = np.linalg.norm(P[a:a + 2000, None] - P[lead][None], axis=3).mean(2)
        n += np.bincount(d.argmin(1), minlength=len(lead))
    return sorted(n.tolist(), reverse=True)


def _med(v, q=50):
    return round(float(np.percentile(v, q)), 1) if len(v) else None


def _share(a, b, digits=1):
    return round(100.0 * a / b, digits) if b else None


def report(T, zrange=None):
    """a tally -> the yardsticks. zrange: {map: (low, high)}, the heights the pros visit on a map, for "the lowest
    third" (None: this tally's own, from the 1st to the 99th percentile of its time)"""
    mins = T["alive"] / 60.0
    out = dict(demos=T["demos"], stretches=T["stretches"], minutes=round(T["seconds"] / 60.0, 1), minutes_alive=round(mins, 1),
               minutes_with_clock=round(T["clock_seconds"] / 60.0, 1))
    out["spam"] = {}
    for wn in SPAM_W:
        s = T["spam"][wn]
        r = dict(shots_a_minute=round(s["shots"] / mins, 2) if mins else None,
                 blind_a_minute=round(s["blind"] / mins, 3) if mins else None, blind_share=_share(s["blind"], s["shots"]))
        if wn in ("rl", "gl", "pg"):
            e = np.array(s["each"], np.int64).reshape(-1, 5)
            aw = e[e[:, 0] >= FEET_R]                           # the landing numbers are of the shots that land away from himself
            known = aw[aw[:, 4] >= 0]
            r.update(blind_shots=s["blind"], at_own_feet_share=_share(len(e) - len(aw), len(e)),
                     blind_away_a_minute=round(len(aw) / mins, 3) if mins else None,
                     blind_away_share=_share(len(aw), s["shots"]),
                     landing_distance_median=_med(aw[:, 0]), landing_distance_25=_med(aw[:, 0], 25), landing_distance_75=_med(aw[:, 0], 75),
                     met_share=_share(int(aw[:, 1].sum()), len(aw)), met_within_1s_share=_share(int(aw[:, 2].sum()), len(aw)),
                     near_any_view_share=_share(int(aw[:, 3].sum()), len(aw)), hit_share=_share(int(known[:, 4].sum()), len(known)))
        out["spam"][wn] = r
    out["combinations"] = {}
    for a, nm in (("rl", "rocket then rail or lightning"), ("gl", "grenade then rail or lightning")):
        c = T["combo"][a]
        out["combinations"][nm] = dict(per_ten_minutes=round(c["n"] / mins * 10.0, 2) if mins else None, n=c["n"],
                                       enemy_in_the_air_share=_share(c["air"], c["air_known"]), rail_share=_share(c["rg"], c["n"]),
                                       gap_median_s=_med(c["gap"]) if c["gap"] else None)
    out["combinations"]["enemy in the air, of all the time he is in view"] = _share(T["view_air"]["air"], T["view_air"]["known"])
    out["by_state"] = {}
    for name, s in T["state"].items():
        m = s["time"] / 60.0
        out["by_state"][name] = dict(
            minutes=round(m, 1), in_view_share=_share(s["inview"], s["alive"]),
            toward_enemy_speed=round(s["toward"] / s["inview"], 1) if s["inview"] else None,
            distance_in_view=round(s["dist"] / s["inview"]) if s["inview"] else None,
            frags_a_minute=round(s["frags"] / m, 3) if m else None, deaths_a_minute=round(s["deaths"] / m, 3) if m else None,
            travelling_speed=round(s["travel_d"] / s["travel_t"], 1) if s["travel_t"] else None,
            stacked_share=_share(s["stack"], s["alive"]),
            blind_rockets_a_minute=round(s["away_rl"] / s["alive"] * 60.0, 3) if s["alive"] else None,
            blind_grenades_a_minute=round(s["away_gl"] / s["alive"] * 60.0, 3) if s["alive"] else None,
            blind_plasma_a_minute=round(s["away_pg"] / s["alive"] * 60.0, 3) if s["alive"] else None,
            blind_rocket_share=_share(s["away_rl"], s["rl"]))
    out["items"] = {}
    for k, I in T["items"].items():
        out["items"][k] = dict(pickups=I["pickups"], pickups_a_ten_minutes=round(I["pickups"] / (T["seconds"] / 600.0), 2) if T["seconds"] else None,
                               counted=I["counted"], back_at_return_share=_share(I["back"], I["counted"]),
                               took_it_again_within_5s_share=_share(I["took"], I["counted"]),
                               died_before_return_share=_share(I["died"], I["counted"]),
                               gap_median_s=_med(I["gaps"]), gap_25=_med(I["gaps"], 25), gap_75=_med(I["gaps"], 75))
    out["predictability"] = predictability(T, zrange)
    out["aggression"] = aggression(T)
    return out


def zranges(path=None):
    """{map: (low, high)}: the heights the pros visit on each map, from the yardsticks' json"""
    res = json.load(open(path or os.path.join(ROOT, "docs", "pro_yardsticks.json"), encoding="utf-8"))
    return {m: tuple(v["predictability"]["maps"][m]["height_range"]) for m, v in res["maps"].items() if m in v["predictability"]["maps"]}


def _aggro(cs):
    """cells of T["aggro"] together -> the numbers of a row"""
    n = sum(c["n"] for c in cs)
    if not n:
        return dict(sightings=0)
    k10 = sum(c["known10"] for c in cs)
    return dict(sightings=n, closing_speed=round(sum(c["toward"] for c in cs) / n, 1), push_share=_share(sum(c["push"] for c in cs), n),
                fires_within_1s_share=_share(sum(c["fire"] for c in cs), n), view_broken_share=_share(sum(c["broke"] for c in cs), n),
                fragged_him_in_3s_share=_share(sum(c["frag"] for c in cs), n), died_in_3s_share=_share(sum(c["died"] for c in cs), n),
                frags_less_deaths_in_10s=round((sum(c["frags10"] for c in cs) - sum(c["deaths10"] for c in cs)) / k10, 3) if k10 else None)


def aggression(T):
    """the seventh group from a tally: every cell of the five-way table that has a sighting, and the tables by one and
    by two of its sides"""
    A = {tuple(int(x) for x in k.split("|")): c for k, c in T["aggro"].items()}
    sides = (("stack", STACK_BANDS), ("own", OWN_BANDS), ("frag", FRAG_BANDS), ("enemy", ENEMY_BANDS), ("score", ("behind", "level", "ahead")))

    def name(side, v):
        return sides[side][1][v + 1] if side == 4 else sides[side][1][v]

    def by(*which):
        out = {}
        for key in sorted({tuple(k[q] for q in which) for k in A}):
            out[", ".join(name(q, v) for q, v in zip(which, key))] = _aggro([c for k, c in A.items() if tuple(k[q] for q in which) == key])
        return out
    cells = [dict(stack=name(0, k[0]), own=name(1, k[1]), frag=name(2, k[2]), enemy=name(3, k[3]), score=name(4, k[4]), **_aggro([c]))
             for k, c in sorted(A.items())]
    D = {tuple(int(x) for x in k.split("|")): c for k, c in T["aggro_dist"].items()}
    by_dist = {"{}, {}".format(STACK_BANDS[a], DIST_BANDS[b]): _aggro([c]) for (a, b), c in sorted(D.items())}
    return dict(all=_aggro(list(A.values())), by_stack=by(0), by_own_weapon=by(1), by_last_frag=by(2), by_enemy_weapon=by(3), by_score=by(4),
                by_stack_and_distance=by_dist,
                by_stack_and_last_frag=by(0, 2), by_stack_and_enemy_weapon=by(0, 3), by_stack_and_own_weapon=by(0, 1),
                by_stack_and_score=by(0, 4), by_own_and_enemy_weapon=by(1, 3), by_stack_own_and_enemy_weapon=by(0, 1, 3), cells=cells)


def predictability(T, zrange=None):
    """the sixth group from a tally: per map, and over the maps their mean (a cell and a way belong to one map)"""
    maps = sorted({k.split(":")[0] for k in T["cells"]})
    per = {}
    for mp in maps:
        sec = [v for k, v in T["cells"].items() if k.startswith(mp + ":")]
        own = np.array([r[1:4] for r in T["cells_own"] if r[0] == mp], np.float64).reshape(-1, 3)
        top, n80, ent = _spread(sec)
        o = dict(pooled=dict(top8_share=round(100 * top, 1), cells_for_80=n80, entropy_bits=round(ent, 2), cells_used=len(sec)),
                 per_player=dict(n=len(own), top8_share=round(100 * float(own[:, 0].mean()), 1) if len(own) else None,
                                 cells_for_80=round(float(own[:, 1].mean()), 1) if len(own) else None,
                                 entropy_bits=round(float(own[:, 2].mean()), 2) if len(own) else None))
        z = sorted((int(k.split(":")[1]), v) for k, v in T["zhist"].items() if k.startswith(mp + ":"))
        zc = np.cumsum([v for _, v in z])
        if zrange and mp in zrange:
            lo, hi = zrange[mp]
        else:
            lo = z[int(np.searchsorted(zc, 0.01 * zc[-1]))][0] * 8.0
            hi = z[int(np.searchsorted(zc, 0.99 * zc[-1]))][0] * 8.0 + 8.0
        cut = lo + (hi - lo) / 3.0
        o["height_range"] = [lo, hi]
        o["lowest_third_share"] = _share(sum(v for b, v in z if b * 8.0 + 4.0 < cut), zc[-1])
        pairs = {}
        for k, tr in T["trips"].items():
            if k.startswith(mp + ":") and len(tr) >= WAY_MIN_TRIPS:
                n = ways(tr)
                big = [x for x in n if x >= max(3, WAY_MIN_SHARE * len(tr))]
                pairs[k.split(":")[1]] = dict(trips=len(tr), ways=len(big), commonest_share=round(100.0 * n[0] / len(tr), 1),
                                              one_off_share=round(100.0 * (1.0 - sum(big) / len(tr)), 1),
                                              seconds_median=_med([r[-1] for r in tr]))
        o["routes"] = dict(pairs=len(pairs), trips=sum(len(tr) for k, tr in T["trips"].items() if k.startswith(mp + ":")),
                           one_off_share_mean=round(float(np.mean([p["one_off_share"] for p in pairs.values()])), 1) if pairs else None,
                           ways_mean=round(float(np.mean([p["ways"] for p in pairs.values()])), 2) if pairs else None,
                           commonest_share_mean=round(float(np.mean([p["commonest_share"] for p in pairs.values()])), 1) if pairs else None,
                           by_pair=pairs)
        per[mp] = o
    H, S = T["height"], T["stand"]
    out = dict(height=dict(higher_share=_share(H["higher"], H["view"]), lower_share=_share(H["lower"], H["view"]),
                           level_share=_share(H["view"] - H["higher"] - H["lower"], H["view"])),
               standing=dict(share=_share(S["time"], T["alive"]), longest_a_minute_mean=round(float(np.mean(S["longest"])), 2) if S["longest"] else None,
                             longest_a_minute_median=_med(S["longest"]), longest_a_minute_90=_med(S["longest"], 90)),
               maps=per)

    def mean(f):
        v = [f(o) for o in per.values() if f(o) is not None]
        return round(float(np.mean(v)), 1) if v else None
    out["position"] = dict(pooled_top8_share=mean(lambda o: o["pooled"]["top8_share"]), pooled_cells_for_80=mean(lambda o: o["pooled"]["cells_for_80"]),
                           maps=len(per),
                           pooled_entropy_bits=mean(lambda o: o["pooled"]["entropy_bits"]),
                           per_player_top8_share=mean(lambda o: o["per_player"]["top8_share"]),
                           per_player_cells_for_80=mean(lambda o: o["per_player"]["cells_for_80"]),
                           per_player_entropy_bits=mean(lambda o: o["per_player"]["entropy_bits"]))
    out["lowest_third_share"] = mean(lambda o: o["lowest_third_share"])
    out["routes"] = dict(ways_mean=mean(lambda o: o["routes"]["ways_mean"]), commonest_share_mean=mean(lambda o: o["routes"]["commonest_share_mean"]),
                         one_off_share_mean=mean(lambda o: o["routes"]["one_off_share_mean"]),
                         pairs=sum(o["routes"]["pairs"] for o in per.values()))
    return out


def map_info(world, name):
    """what measure() needs of a map: its name; `items`, the mega health and the armors: kind, place (dropped to the
    floor as the game does) and the places of the other items of its sort (health or armor) that a pickup could be
    mistaken for; `big`, the items a trip goes from and to (those and the rocket launcher, rail, lightning): label,
    place, and what rises at a pickup (health, armor, or the ammunition of a weapon)"""
    ents = [e for e in world.entities if "origin" in e and e.get("classname", "").startswith(("item_health", "item_armor", "weapon_"))]
    pos = []
    for e in ents:
        p = np.array(e["origin"], np.float32)
        if not int(float(e.get("spawnflags", 0) or 0)) & 1:
            tr = world.trace(p, p - np.array([0, 0, 4096.0], np.float32), mins=(-15, -15, -15), maxs=(15, 15, 15), mask=SOLID)
            if not tr["startsolid"] and tr["fraction"] < 1.0:
                p = tr["endpos"]
        pos.append(p)
    out, big, seen = [], [], {}
    for e, p in zip(ents, pos):
        cls = e["classname"]
        sort = cls.split("_")[1] if cls.startswith("item_") else cls
        rivals = [q for f, q in zip(ents, pos) if f is not e and cls.startswith("item_") and f["classname"].startswith("item_" + sort)]
        if cls in ITEM_KIND:
            out.append(dict(kind=ITEM_KIND[cls], pos=p, rivals=rivals))
        if cls in BIG:
            seen[BIG[cls]] = seen.get(BIG[cls], 0) + 1
            n_same = sum(1 for f in ents if f["classname"] == cls)
            wname = {"weapon_rocketlauncher": "rl", "weapon_railgun": "rg", "weapon_lightning": "lg"}.get(cls)
            big.append(dict(label=BIG[cls] + (str(seen[BIG[cls]]) if n_same > 1 else ""), pos=p, rivals=rivals,
                            col=sort if wname is None else WEAPONS.index(wname)))
    return dict(name=name, items=out, big=big)


# ---------------------------------------------------------------------------------------------------------------------
# reading a demo
# ---------------------------------------------------------------------------------------------------------------------
QLW = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}      # the game's weapon numbers
HDR, PS_N, PL_N, MI_N, IT_N, EV_N = 6, 103, 19, 12, 6, 9      # tools/demodump's record (sim/demo_reader.py)
PM_INTERMISSION = 5
P_SCORE, P_HITS, P_RANK, P_TEAM, P_DEATHS = 0, 1, 2, 3, 7     # the player state's persistant fields in Quake Live's formats
RANK_TIED = 0x4000
EXE = os.path.join(ROOT, "tools", "demodump", "demodump.exe")


def demo_root():
    f = os.path.join(ROOT, "data", "demo_root.txt")
    p = open(f).read().strip() if os.path.exists(f) else ""
    return p or os.path.join(ROOT, "data")


def read_dump(binf):
    """tools/demodump's stream -> the server time, the player states and the other players' rows of every snapshot"""
    sys.path.insert(0, SIM)
    import demo_reader as D
    raw = np.fromfile(binf, dtype=np.float32)
    offs, i, n = [], 0, len(raw)
    while i + HDR + PS_N <= n:
        offs.append(i)
        i += HDR + PS_N + int(raw[i + 2]) * PL_N + int(raw[i + 3]) * MI_N + int(raw[i + 4]) * IT_N + int(raw[i + 5]) * EV_N
    offs = np.array(offs, np.int64)
    if not len(offs):
        return None
    hdr = raw[offs[:, None] + np.arange(HDR)]
    ps = raw[offs[:, None] + HDR + np.arange(PS_N)]
    npl = hdr[:, 2].astype(np.int64)
    snap = np.repeat(np.arange(len(offs)), npl)
    within = np.arange(len(snap)) - np.repeat(np.cumsum(npl) - npl, npl)
    pl = raw[(np.repeat(offs + HDR + PS_N, npl) + within * PL_N)[:, None] + np.arange(PL_N)] if len(snap) else np.zeros((0, PL_N), np.float32)
    return dict(time=hdr[:, 1].astype(np.int64), ps=ps, pl=pl, pl_snap=snap, PS=D.PS)


def stat_slots(st, alive):
    """the stats slots of the weapon bits and the armor (they differ between demo formats; as sim/demo_dataset.py)"""
    wslot, aslot, best = 3, 4, -1
    if alive.sum() < 100:
        return wslot, aslot
    for k in range(1, 16):
        v = st[alive, k].astype(np.int64)
        share = ((v & 6) == 6).mean() if (v >= 0).all() and v.max() < 65536 else 0.0
        if share > 0.98 and len(np.unique(v)) > best and v.max() >= 6:
            wslot, best = k, len(np.unique(v))
    cands = [(len(np.unique(st[alive, k])), k) for k in range(1, 16)
             if k != wslot and st[alive, k].min() >= 0 and st[alive, k].max() <= 200 and len(np.unique(st[alive, k])) > 8]
    if cands:
        aslot = max(cands)[1]
    return wslot, aslot


def demo_record(binf, meta):
    """one parsed demo -> (record of its game, facts about the reading) or (None, facts)"""
    d = read_dump(binf)
    info = dict(protocol=meta.get("protocol"), snapshots=0 if d is None else len(d["time"]))
    if d is None or len(d["time"]) < 800:
        return None, dict(info, why="short")
    PS, ps, tm = d["PS"], d["ps"], d["time"]
    N = len(tm)
    cs0 = (meta.get("gamestates") or [{}])[0].get("cs", {}).get("cs0", "")
    kv = dict(zip(cs0.split("\\")[1::2], cs0.split("\\")[2::2]))
    info["began"] = kv.get("g_gameState", "?")
    pers = ps[:, PS["persistant"]:PS["persistant"] + 16].astype(np.int64)
    pers[:, P_SCORE] = np.where(pers[:, P_SCORE] >= 32768, pers[:, P_SCORE] - 65536, pers[:, P_SCORE])   # (-1 after an accident, -999 after a forfeit)
    cn = ps[:, PS["clientNum"]].astype(np.int64)
    pm = ps[:, PS["pm_type"]].astype(np.int64)
    playing = (pers[:, P_TEAM] == 0) & (pm != PM_INTERMISSION)
    dt = np.diff(tm)
    inter = np.nonzero(pm == PM_INTERMISSION)[0]
    end = int(inter[0]) if len(inter) else N
    info["has_end"] = bool(len(inter))
    # ---- the game's start: the hole the restart leaves, after which the counters are zero
    start, t0 = 0, None
    if info["began"] != "IN_PROGRESS":
        cands = []
        for i in np.nonzero(dt[:end - 1] >= 300)[0]:
            j = np.nonzero(playing[i + 1:i + 1 + 200])[0]
            if len(j) and not pers[i + 1 + j[0], [P_SCORE, P_HITS, P_DEATHS]].any():
                cands.append(int(i))
        if not cands:
            return None, dict(info, why="no start")
        pick = cands[0]
        if info["has_end"]:                                    # the one that makes the game ten minutes (plus overtimes of two)
            for i in cands:
                L = int(tm[end]) - int(tm[i]) - 25
                if L >= 600000 and (L - 600000) % 120000 <= 2500:
                    pick = i
                    break
        start, t0 = pick + 1, int(tm[pick]) + 25
    info["has_start"] = t0 is not None
    clock = np.full(N, np.nan, np.float32)
    if t0 is not None:
        clock = ((tm - t0) / 1000.0).astype(np.float32)
        if info["has_end"]:
            L = int(tm[end]) - t0
            info["length_s"] = round(L / 1000.0, 2)
            if L > 602500 and (L - 600000) % 120000 > 2500:    # the clock stood somewhere (a timeout): no clock for this game
                clock[:] = np.nan
                info["clock_off"] = True
    ok = playing.copy()
    ok[:start] = False
    ok[end:] = False
    back = np.nonzero(dt[start:end - 1] <= 0)[0]
    if len(back):                                              # the server time must rise: the game is read up to where it does not
        ok[start + int(back[0]) + 1:] = False
        info["time_back"] = True
    if ok.sum() < 800:
        return None, dict(info, why="no game")
    st = ps[:, PS["stats"]:PS["stats"] + 16]
    health = st[:, 0]
    alive = ok & (health > 0) & (pm != 3)
    wslot, aslot = stat_slots(st, alive)
    # ---- the enemy: the other player's entity, not a corpse (those have numbers from 64 on), not dead
    pl, snap = d["pl"], d["pl_snap"]
    enemy = np.full((N, 3), np.nan, np.float32)
    air = np.full(N, -1, np.int64)
    eweap = np.full(N, -1, np.int64)
    if len(pl):
        m = (pl[:, 0] < 64) & (pl[:, 0] != cn[snap]) & ((pl[:, 12].astype(np.int64) & 1) == 0)
        s_, first = np.unique(snap[m], return_index=True)
        rows = pl[m][first]
        enemy[s_] = rows[:, 2:5]
        air[s_] = (rows[:, 13] == 1023).astype(np.int64)
        eweap[s_] = [WEAPONS.index(QLW[int(x)]) if int(x) in QLW else -1 for x in rows[:, 11]]
    # ---- stretches of one followed player
    brk = np.ones(N, bool)
    brk[1:] = (cn[1:] != cn[:-1]) | ~ok[1:] | ~ok[:-1] | (dt > 100) | (dt <= 0)
    seg = np.cumsum(brk)
    # ---- shots: a weapon's ammunition going down inside a stretch
    am = ps[:, PS["ammo"]:PS["ammo"] + 16].astype(np.int64)
    shots = []
    for q, name in QLW.items():
        if name == "g":
            continue
        dec = np.zeros(N, np.int64)
        dec[1:] = am[:-1, q] - am[1:, q]
        fr = np.nonzero(~brk & (dec > 0) & (dec <= 6) & (am[:, q] >= 0) & alive & np.concatenate([[False], alive[:-1]]))[0]
        shots += [(int(i), WEAPONS.index(name), int(dec[i])) for i in fr]
    # ---- who leads (the rank) and the enemy's score (an estimate, see the top of the file)
    rank = pers[:, P_RANK]
    lead = np.where((rank & RANK_TIED) != 0, 0, np.where((rank & 0xFF) == 0, 1, -1))
    score = pers[:, P_SCORE]
    escore = np.zeros(N, np.int64)
    last, e, fixes = {}, 0, 0
    prev = -1
    for i in np.nonzero(ok)[0]:
        c = int(cn[i])
        if prev >= 0 and int(cn[prev]) != c:                   # a cut: the enemy is now the one followed before
            e = last.get(int(cn[prev]), e)
        elif prev >= 0 and not brk[i]:
            if pers[i, P_DEATHS] > pers[prev, P_DEATHS] and score[i] >= score[prev]:
                e += int(pers[i, P_DEATHS] - pers[prev, P_DEATHS])
        sg = int(np.sign(score[i] - e))
        if sg != lead[i]:                                      # the rank knows better (an accident of his takes a point off him)
            e = int(score[i]) - int(lead[i]) if lead[i] else int(score[i])
            fixes += 1
        escore[i] = e
        last[c] = int(score[i])
        prev = i
    info["score_fixes"] = fixes
    keep = np.nonzero(ok)[0]
    remap = np.full(N, -1, np.int64)
    remap[keep] = np.arange(len(keep))
    shots = [(int(remap[i]), wq, c) for i, wq, c in shots if remap[i] >= 0]
    hand = np.array([WEAPONS.index(QLW.get(int(x), "mg")) for x in ps[keep, PS["weapon"]]], np.int64)
    ang = ps[keep, PS["angles"]:PS["angles"] + 3]
    rec = make_record(t=tm[keep] / 1000.0, pos=ps[keep, PS["origin"]:PS["origin"] + 3], vel=ps[keep, PS["velocity"]:PS["velocity"] + 3],
                      yaw=ang[:, 1], pitch=ang[:, 0], weapon=hand, shots=shots, health=health[keep], armor=st[keep, aslot],
                      score=score[keep], enemy=enemy[keep], enemy_score=escore[keep], lead=lead[keep], clock=clock[keep],
                      alive=alive[keep], eye_h=ps[keep, PS["viewheight"]], enemy_air=air[keep], hits=pers[keep, P_HITS], seg=seg[keep],
                      ammo=np.stack([np.zeros(len(keep)) if nm == "g" else am[keep, [q for q, x in QLW.items() if x == nm][0]] for nm in WEAPONS], 1),
                      client=cn[keep], owned=np.stack([(st[keep, wslot].astype(np.int64) >> [q for q, x in QLW.items() if x == nm][0]) & 1 for nm in WEAPONS], 1),
                      enemy_weapon=eweap[keep])
    info.update(recorder=int((meta.get("gamestates") or [{}])[0].get("client_num", -1)), cuts=int((np.diff(cn[keep]) != 0).sum()),
                final={int(c): int(v) for c, v in last.items()}, final_enemy=int(e), final_client=int(cn[keep[-1]]),
                step_ms=int(np.median(dt)))
    return rec, info


def parse(demo, tmp):
    """a demo file -> (record, facts)"""
    b, js = os.path.join(tmp, "d.bin"), os.path.join(tmp, "d.json")
    for p in (b, js):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run([EXE, demo, b, js], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not os.path.exists(js) or not os.path.exists(b):
        return None, dict(why="parser")
    meta = json.load(open(js, encoding="utf-8", errors="replace"))
    try:
        return demo_record(b, meta)
    finally:
        for p in (b, js):                                       # (a parsed demo is 18 MB)
            if os.path.exists(p):
                os.remove(p)


_W = {}


def _init(mp, tmp):
    sys.path.insert(0, SIM)
    from qsim import World
    w = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"))  # one World a process
    w.add_solids()
    _W.update(world=w, info=map_info(w, mp), tmp=os.path.join(tmp, str(os.getpid())), map=mp)
    os.makedirs(_W["tmp"], exist_ok=True)


def _one(args):
    demo, out, redo = args
    if not redo and os.path.exists(out):
        try:
            r = json.load(open(out))
            if r.get("version") == VERSION:
                return r
        except Exception:                                      # noqa: BLE001
            pass
    try:
        rec, info = parse(demo, _W["tmp"])
        if rec is None:
            r = dict(version=VERSION, skip=info.get("why", "?"), info=info)
        else:
            T, rows = measure(rec, _W["world"], _W["info"])
            r = dict(version=VERSION, tally=T, info=info, **rows)
    except Exception as e:                                      # a broken demo must not stop the batch
        r = dict(version=VERSION, skip="error", info=dict(error=repr(e)[:200]))
    with open(out, "w") as f:
        json.dump(r, f)
    return r


def run_map(mp, limit, procs, redo):
    files = sorted(f for f in glob.glob(os.path.join(demo_root(), "demos", mp, "*.dm_*")) if not f.endswith(".part"))
    if limit:
        files = files[::max(1, len(files) // limit)][:limit]
    out_dir = os.path.join(demo_root(), "yardsticks", mp)
    os.makedirs(out_dir, exist_ok=True)
    jobs = [(f, os.path.join(out_dir, os.path.splitext(os.path.basename(f))[0] + ".json"), redo) for f in files]
    tmp = tempfile.mkdtemp(prefix="yard_")                       # the parsed demos of the moment, a folder a process
    try:
        if procs <= 1:
            _init(mp, tmp)
            res = [_one(j) for j in jobs]
        else:
            with mp_.Pool(procs, initializer=_init, initargs=(mp, tmp)) as pool:
                res = pool.map(_one, jobs, chunksize=4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return files, res


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")
    return "\n".join(out)


def show(res):
    """the tables, markdown"""
    maps = [m for m in res["maps"] if m != "all"]
    cols = (["all"] if "all" in res["maps"] else []) + maps
    R = res["maps"]
    print("## The pros' yardsticks\n")
    print(table([["demos used"] + [R[m]["demos"] for m in cols], ["minutes of play"] + [R[m]["minutes"] for m in cols],
                 ["minutes with a game clock"] + [R[m]["minutes_with_clock"] for m in cols]], ["", *cols]))
    print("\n### 1. Spam: shots with no enemy in view for a second or more\n")
    rows = []
    for wn in SPAM_W:
        rows.append([W_NAMES[wn] + ": blind shots a minute"] + [R[m]["spam"][wn]["blind_a_minute"] for m in cols])
        rows.append([W_NAMES[wn] + ": blind, % of its shots"] + [R[m]["spam"][wn]["blind_share"] for m in cols])
    for wn in ("rl", "gl", "pg"):
        rows.append([W_NAMES[wn] + ": of the blind ones, at his own feet (under 150 units), % (extra)"] + [R[m]["spam"][wn]["at_own_feet_share"] for m in cols])
        rows.append([W_NAMES[wn] + ": blind and away (150 units or more) a minute"] + [R[m]["spam"][wn]["blind_away_a_minute"] for m in cols])
        rows.append([W_NAMES[wn] + ": blind and away, % of its shots"] + [R[m]["spam"][wn]["blind_away_share"] for m in cols])
        rows.append([W_NAMES[wn] + ": away: distance to where it lands, median"] + [R[m]["spam"][wn]["landing_distance_median"] for m in cols])
        rows.append([W_NAMES[wn] + ": away: enemy in view near there within 2 s, %"] + [R[m]["spam"][wn]["met_share"] for m in cols])
        rows.append([W_NAMES[wn] + ": away: a hit as it lands, % (extra)"] + [R[m]["spam"][wn]["hit_share"] for m in cols])
    print(table(rows, ["", *cols]))
    print("\n### 2. Combinations\n")
    rows = []
    for nm in ("rocket then rail or lightning", "grenade then rail or lightning"):
        rows.append([nm + ": a ten minutes"] + [R[m]["combinations"][nm]["per_ten_minutes"] for m in cols])
        rows.append([nm + ": enemy in the air at the second shot, %"] + [R[m]["combinations"][nm]["enemy_in_the_air_share"] for m in cols])
        rows.append([nm + ": the second weapon is the rail, % (extra)"] + [R[m]["combinations"][nm]["rail_share"] for m in cols])
    rows.append(["enemy in the air, % of all his time in view (to compare)"] + [R[m]["combinations"]["enemy in the air, of all the time he is in view"] for m in cols])
    print(table(rows, ["", *cols]))
    for m in cols[:1] + [c for c in cols[1:] if len(cols) <= 3]:
        print("\n### 3. By score and time ({})\n".format(m))
        names = STATES + ["ahead", "level", "behind", "all", "stack under 100", "stack 100 to 149", "stack 150 or more"]
        keys = (("minutes", "minutes"), ("in_view_share", "enemy in view, % of his time alive"), ("toward_enemy_speed", "speed toward the enemy in view"),
                ("distance_in_view", "distance in view (extra)"), ("frags_a_minute", "frags a minute"), ("deaths_a_minute", "deaths a minute"),
                ("travelling_speed", "travelling speed"), ("stacked_share", "150 or more health and armor, %"),
                ("blind_rockets_a_minute", "blind rockets away a minute (extra)"), ("blind_rocket_share", "blind and away, % of his rockets (extra)"))
        print(table([[n] + [R[m]["by_state"][n][k] for k, _ in keys] for n in names], ["state"] + [lbl for _, lbl in keys]))
    print("\n### 4. Item timing\n")
    rows = []
    for k in ("mega", "red", "yellow"):
        rows.append([k + ": pickups a ten minutes (extra)"] + [R[m]["items"][k]["pickups_a_ten_minutes"] for m in cols])
        rows.append([k + ": back within 150 units, 2 s either side of its return, %"] + [R[m]["items"][k]["back_at_return_share"] for m in cols])
        rows.append([k + ": took it again within 5 s of its return, % (extra)"] + [R[m]["items"][k]["took_it_again_within_5s_share"] for m in cols])
        rows.append([k + ": seconds between his pickups, median"] + [R[m]["items"][k]["gap_median_s"] for m in cols])
    print(table(rows, ["", *cols]))
    print("\n### 6. How predictable: places, height, ways, standing\n")
    P = {m: R[m]["predictability"] for m in cols}

    def pm(m, f, g):                                            # a map's own number, or over the maps their mean
        return g(P[m]) if m == "all" else f(P[m]["maps"][m]) if m in P[m]["maps"] else None
    rows = [
        ["one player in one game: time in his 8 most-used cells, %"] + [pm(m, lambda o: o["per_player"]["top8_share"], lambda o: o["position"]["per_player_top8_share"]) for m in cols],
        ["one player in one game: cells that hold 80% of his time"] + [pm(m, lambda o: o["per_player"]["cells_for_80"], lambda o: o["position"]["per_player_cells_for_80"]) for m in cols],
        ["one player in one game: entropy of his time over cells, bits"] + [pm(m, lambda o: o["per_player"]["entropy_bits"], lambda o: o["position"]["per_player_entropy_bits"]) for m in cols],
        ["all pros together: time in the 8 most-used cells, %"] + [pm(m, lambda o: o["pooled"]["top8_share"], lambda o: o["position"]["pooled_top8_share"]) for m in cols],
        ["all pros together: cells that hold 80% of the time"] + [pm(m, lambda o: o["pooled"]["cells_for_80"], lambda o: o["position"]["pooled_cells_for_80"]) for m in cols],
        ["all pros together: entropy, bits"] + [pm(m, lambda o: o["pooled"]["entropy_bits"], lambda o: o["position"]["pooled_entropy_bits"]) for m in cols],
        ["enemy in view: he stands 48 units or more higher, %"] + [P[m]["height"]["higher_share"] for m in cols],
        ["enemy in view: 48 or more lower, %"] + [P[m]["height"]["lower_share"] for m in cols],
        ["enemy in view: level, %"] + [P[m]["height"]["level_share"] for m in cols],
        ["time in the lowest third of the heights players visit, %"] + [pm(m, lambda o: o["lowest_third_share"], lambda o: o["lowest_third_share"]) for m in cols],
        ["trips between big items: pairs with 30 trips or more"] + [pm(m, lambda o: o["routes"]["pairs"], lambda o: o["routes"]["pairs"]) for m in cols],
        ["trips: clearly different ways a pair, mean"] + [pm(m, lambda o: o["routes"]["ways_mean"], lambda o: o["routes"]["ways_mean"]) for m in cols],
        ["trips: on the commonest way of their pair, %"] + [pm(m, lambda o: o["routes"]["commonest_share_mean"], lambda o: o["routes"]["commonest_share_mean"]) for m in cols],
        ["trips: on a way of their own (no clear way), %"] + [pm(m, lambda o: o["routes"]["one_off_share_mean"], lambda o: o["routes"]["one_off_share_mean"]) for m in cols],
        ["standing (under 50 units a second), % of his time alive"] + [P[m]["standing"]["share"] for m in cols],
        ["longest stand in a minute, seconds: mean"] + [P[m]["standing"]["longest_a_minute_mean"] for m in cols],
        ["longest stand in a minute, seconds: median"] + [P[m]["standing"]["longest_a_minute_median"] for m in cols],
    ]
    print(table(rows, ["", *cols]))
    A = R[cols[0]]["aggression"]
    keys = (("sightings", "sightings"), ("closing_speed", "closing speed"), ("push_share", "pushes, %"), ("fires_within_1s_share", "fires within 1 s, %"),
            ("view_broken_share", "view broken, %"), ("fragged_him_in_3s_share", "fragged him in 3 s, %"), ("died_in_3s_share", "died in 3 s, %"),
            ("frags_less_deaths_in_10s", "frags less deaths in 10 s"))
    print("\n### 7. Aggression by advantage ({}): the 3 s after the enemy comes into view\n".format(cols[0]))
    for title, tab in (("his health and armor", "by_stack"), ("his health and armor, and how long ago he fragged him", "by_stack_and_last_frag"),
                       ("his health and armor, his own weapons, the enemy's weapon", "by_stack_own_and_enemy_weapon"),
                       ("his health and armor, and the score", "by_stack_and_score"),
                       ("his health and armor, and the distance at the sighting (extra)", "by_stack_and_distance")):
        print(table([[k] + [v.get(q) for q, _ in keys] for k, v in A[tab].items()], [title] + [lbl for _, lbl in keys]) + "\n")


ABOUT = dict(
    blind_shot="a shot (a weapon's ammunition going down) while the enemy has not been in his view for 1.0 s or more; in view = inside a cone of 55 degrees round his view, under 4000 units, a clear line through the map from his eye to the enemy's chest or head",
    landing="rockets and plasma: his view traced from his eye to the first wall; grenades: the simulator's grenade flight (700 units a second, lofted, gravity, bounces keep 0.65) to where it lies when the 2.5 s fuse ends. A blind shot that lands under 150 units from his eye is 'at his own feet' (a rocket jump, a shot at the floor): it is counted, but the numbers of the landing (distance, met, hit) and 'blind and away' are of the others",
    met="the enemy in his view within 2 s of the shot and within 300 units of where it landed",
    hit="extra: his hit counter goes up in the 0.35 s round the moment the shot lands (a grenade: at any time until its fuse ends)",
    combination="the first rail or lightning shot within 1.5 s of a rocket (grenade) fired with the enemy in view (seen within the last 0.2 s), the rocket being his last shot before it",
    states="who leads is the player state's rank; the clock is the server time since the game's restart; frags and deaths a minute of his time in the state, dead time included",
    toward_enemy_speed="his velocity along the line to the enemy, averaged over the time the enemy is in view (the enemy's own movement is not in it)",
    travelling_speed="his mean horizontal speed while alive with no enemy in view",
    items="a pickup: his health (mega) or armor rising within 60 units of the item; back at its return: alive within 150 units of it at some moment from 2 s before to 2 s after (mega 35 s, armors 25 s after his pickup); counted only where the same stretch of the demo lasts that long",
    position="his time alive over cells of 192 x 192 x 96 units: the share in the 8 most used, the number of cells that hold 80% of it, the entropy in bits. 'per_player': each followed player of a demo with 3 minutes or more of his own, then the mean over them; 'pooled': the time of all of them on a map together. Over all maps: the mean of the maps",
    height="with the enemy in view: his origin 48 units or more above the enemy's, 48 or more below, or between. The lowest third: of the heights the pros visit on that map, from the 1st to the 99th percentile of their time (height_range, to be passed to report() for another player's games)",
    routes="a trip: from his pickup of one of mega, red armor, a yellow armor, a rocket launcher, the rail, the lightning gun to his next pickup of another of them (a weapon: its ammunition rising at its spot), alive throughout, 1 to 20 s. Its path is 16 points evenly along it; two trips are the same way when their paths lie within 200 units of each other on average (a trip joins the way whose first trip is nearest). A pair (from, to: the two directions apart) counts with 30 trips or more, a way with 5% of its pair's trips (3 at least)",
    standing="his speed under 50 units a second while alive; the longest stand in a minute: for every minute of the record with 30 s or more alive, the longest unbroken stand that reaches into it",
    aggression="a sighting: the enemy comes into his view after 1 s or more out of it. Read over the next 3 s (to his death, if he dies): his mean speed along the line to the enemy (plus = closing; where the enemy is not known, to where he last was); 'pushes': that mean over 150 units a second; whether he fires within 1 s; 'view broken': neither of them died and the enemy was out of his view for 0.5 s at a stretch (who broke it is not known); and over 10 s his frags less his deaths. The situation at the sighting: his health plus armor (under 60, 60 to 125, over 125); whether he owns rockets, lightning or rail with ammunition; how long ago he fragged this enemy (under 10 s: the enemy has just spawned; what he did before a cut of the demo is not known and counts as 'not yet'); the weapon in the enemy's hand (rockets, lightning, rail = big); who leads",
    not_measured=[
        "whether a blind shot did damage, exactly: a demo has no damage events. The extra 'hit' is his own hit counter going up as the shot lands",
        "where the enemy is while the server does not send him (out of sight and away): 'met' misses an enemy who was there unseen, and a blind shot at an enemy heard is not told from one at nothing",
        "the enemy's health, armor and weapons: play by 'who is stronger' can only be read from P's own stack",
        "the enemy's pickups and an item's true state while it is out of his sight: the return time counts from P's own pickup only; an item the enemy took in between returns later than counted",
        "the enemy's score as a number (the lead is exact, from the rank)",
        "the game clock of a demo that begins in a running game, and of a game with a timeout",
        "sounds: what he heard is not in a demo",
        "a grenade that went off on a player before its fuse ended",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=MAPS)
    ap.add_argument("--limit", type=int, default=0, help="at most this many demos a map, spread over the archive")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--json", default=None, help="where the numbers go (default docs/pro_yardsticks.json; a sample or a part of the maps is only shown)")
    ap.add_argument("--show", default=None)
    ap.add_argument("--check", action="store_true", help="the clock, the score and the pickups beside the demo site's own numbers")
    a = ap.parse_args()
    if a.show:
        return show(json.load(open(a.show)))
    maps = a.map.split(",")
    res, total, t0 = dict(about=ABOUT, maps={}), new_tally(), time.time()
    total_skips, infos = {}, {}
    for mp in maps:
        files, rs = run_map(mp, a.limit, a.procs, a.redo)
        T, skips, rows = new_tally(), {}, dict(blind=[], sight=[], view=[])
        infos[mp] = []
        for f, r in zip(files, rs):
            if "tally" in r:
                add_tally(T, r["tally"])
                for k in rows:
                    rows[k] += r[k]
            else:
                skips[r.get("skip", "?")] = skips.get(r.get("skip", "?"), 0) + 1
            infos[mp].append((os.path.basename(f), dict(info=r.get("info", {}), skip=r.get("skip"), used="tally" in r,
                                                        picks={k: v["pickups"] for k, v in r["tally"]["items"].items()} if "tally" in r else {})))
        del rs
        for k, width in (("blind", 9), ("sight", len(SIGHT_COLS)), ("view", len(VIEW_COLS))):          # (a sample's rows beside the archive's, not over them)
            np.save(os.path.join(demo_root(), "yardsticks", "{}_{}{}.npy".format(k, mp, ".sample" if a.limit else "")),
                    np.array(rows[k], np.int32).reshape(-1, width))
        del rows
        res["maps"][mp] = dict(report(T), demos_in_archive=len(files), left_out=skips)
        if len(maps) > 1:
            res["maps"][mp]["aggression"].pop("cells")          # (a map alone is too thin for the five-way table)
        add_tally(total, T)
        for k, v in skips.items():
            total_skips[k] = total_skips.get(k, 0) + v
        print("{}: {} demos, {} used, left out {}, {:.0f} s".format(mp, len(files), T["demos"], skips, time.time() - t0), file=sys.stderr, flush=True)
    if len(maps) > 1:
        res["maps"] = dict(all=dict(report(total), left_out=total_skips), **res["maps"])
        for o in res["maps"]["all"]["predictability"]["maps"].values():
            o["routes"].pop("by_pair")                          # (under the map itself)
    if a.check:
        return check(infos)
    out = a.json or (None if a.limit or a.map != MAPS else os.path.join(ROOT, "docs", "pro_yardsticks.json"))
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
    else:
        print("a sample or a part of the maps: nothing written (--json <file> writes it)", file=sys.stderr)
    show(res)


def check(infos):
    """the readings beside what else is known: the length of the games (ten minutes or overtimes of two), and for the
    demos of the site's index its final scores and pickup counts by client number"""
    idx = {}
    f = os.path.join(demo_root(), "demos", "index.jsonl")
    if os.path.exists(f):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            idx[d["file"]] = d
    n = lens = exact = early = off = 0
    own = [0, 0]
    est = [0, 0, 0]
    led = [0, 0]
    began, skips, steps = {}, {}, {}
    mins = [0, 0]
    pk = {k: [0, 0, 0, 0, 0] for k in ("mega", "red", "yellow")}      # demos, the same number, within one, his sum, the site's sum
    site_key = dict(mega="megaHealthPickups", red="redArmorPickups", yellow="yellowArmorPickups")
    for mp, rows in infos.items():
        for name, r in rows:
            i = r.get("info", {})
            began[i.get("began", "?")] = began.get(i.get("began", "?"), 0) + 1
            if not r["used"]:
                skips[r.get("skip")] = skips.get(r.get("skip"), 0) + 1
                continue
            n += 1
            steps[i.get("step_ms")] = steps.get(i.get("step_ms"), 0) + 1
            if "length_s" in i:
                lens += 1
                L = i["length_s"]
                if L >= 600 and (L - 600.0) % 120.0 <= 2.5:
                    exact += 1
                elif L < 600:
                    early += 1
                else:
                    off += 1
            d = idx.get(name)
            if d and i.get("has_end"):
                full = {p["player_stats"].get("clientNumber"): p["player_stats"] for p in d.get("demo_players", [])
                        if isinstance(p.get("player_stats"), dict)}
                site = {c: v.get("score") for c, v in full.items()}
                c = i["final_client"]
                if "length_s" in i and c in full and isinstance(full[c].get("playTime"), int) and full[c]["playTime"] > 0:
                    mins[1] += 1
                    mins[0] += int(full[c]["playTime"] == int(i["length_s"] // 60))
                if i.get("cuts") == 0 and i.get("has_start") and c in full:     # one player's own demo of a whole game
                    for k, sk in site_key.items():
                        if isinstance(full[c].get(sk), int):
                            a_, b_ = r["picks"].get(k, 0), full[c][sk]
                            pk[k][0] += 1
                            pk[k][1] += int(a_ == b_)
                            pk[k][2] += int(abs(a_ - b_) <= 1)
                            pk[k][3] += a_
                            pk[k][4] += b_
                c = i["final_client"]
                mine = i["final"].get(str(c), i["final"].get(c))
                others = [v for k, v in site.items() if k != c]
                if c in site and site[c] is not None and len(others) == 1 and others[0] is not None:
                    own[1] += 1
                    own[0] += int(site[c] == mine)
                    est[2] += 1
                    est[0] += int(others[0] == i["final_enemy"])
                    est[1] += int(abs(others[0] - i["final_enemy"]) <= 1)
                    led[1] += 1
                    led[0] += int(np.sign(site[c] - others[0]) == np.sign(mine - i["final_enemy"]))
    print("demos read {}, left out {}; the demo began in {}; snapshot step (ms) {}".format(n, skips, began, steps))
    print("games with a start and an end: {}; ten minutes or overtimes of two (to 2.5 s): {}; ended early: {}; fits nothing (no clock): {}".format(lens, exact, early, off))
    print("the site's final score of the player followed at the end = his score read: {} of {}".format(*own))
    print("the site's final score of the other = the estimate: {} of {} (within one: {}); who won agrees: {} of {}".format(est[0], est[2], est[1], *led))
    print("the site's minutes played = the whole minutes of the game's length read: {} of {}".format(*mins))
    for k, v in pk.items():
        print("{} pickups in a player's own demo of a whole game: the same number as the site's in {} of {} (within one: {}); read {} in all, the site {}".format(k, v[1], v[0], v[2], v[3], v[4]))


if __name__ == "__main__":
    main()

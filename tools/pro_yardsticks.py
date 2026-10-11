"""Yardsticks from the pro demos to judge a model's play against, beyond speed (tools/speed_profile.py):
  1 spam (shots with no enemy in view)       2 weapon combinations          3 play by score and time
  4 item timing                              5 extras, marked as such in the tables
  6 how predictable he is: his places, his height, his ways between the big items, his standing
  7 aggression by advantage: what he does in the 3 s after the enemy comes into view, by his situation
  9 walking and quiet      10 when they spam      11 combinations by hits
  12 where he looks with no enemy in view        13 holds and traps
  14 his hands: turn speed, the flick, accuracy  15 movement in a fight
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
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged"         # the trained maps: "all"
GROUPS2 = ("fights", "flick_curve", "view_travelling")         # the groups kept in the second file, docs/pro_yardsticks2.json
MORE = "campgrounds,hektik,toxicity,cure"                      # the maps of movement practice only: under their own names and in "all_ten"
VERSION = 15                                                    # of the counts kept per demo: a change here counts every demo again

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
WAY_STEP = 128.0                                               # a trip's path is kept as points this far apart
WAY_KEEP, WAY_KEEP_SHARE = 3, 0.10                             # sim/pro_ways: at most this many ways a pair, each with this share of its trips
RJ_UP = 300.0                                                  # a rocket jump: his upward speed rises by this within 0.25 s of a rocket of his
DROP = 128.0                                                   # a fall: this far down between leaving the ground and landing
TELE = 400.0                                                   # a step of this many units between two frames: a teleporter
QUIET_BIN, QUIET_BINS, STEADY = 10.0, 41, 3.0                  # the speed histogram's bins; steady: under this change of speed a frame
SEEN_S, LAST_R = 5.0, 600.0
HURT, HURT_BAD, HURT_S, DIED_S = 20.0, 50.0, 5.0, 10.0
NEAR_ITEM = 300.0
HIT_COMBO_S, JUGGLE_S, COMBO_FRAG_S = 1.5, 1.2, 2.0
SINCE_BANDS = ("under 2 s", "2 to 5 s", "5 to 10 s", "over 10 s", "not seen yet in this stretch")
ITEM_CATS = ("mega or armor, back within 5 s as far as he knows", "mega or armor, back in 5 to 10 s", "mega or armor, back in over 10 s",
             "mega or armor, its return unknown to him", "a rocket launcher, rail or lightning gun", "no big item within 300 units")
HOLD_R, HOLD_S = 150.0, 2.0                                    # a hold: within this far of where it began, this long, no enemy in view, a big weapon in hand
HEAR_R = 1200.0                                                # a jump, a shot, a pickup is heard this far (the simulator's HEAR_EVT)
NEAR_DEG = 20.0                                                # his view "points at" something within this angle
FIGHT_R = 800.0                                                # movement in a fight: the enemy in view within this
BIG_HIT = 50.0
UNSEEN_BANDS = ("unseen 1 to 3 s", "unseen 3 to 10 s", "unseen over 10 s")
HEARD_BANDS = ("no sound of his in the last second", "a jump, shot or pickup of his heard in the last second", "sounds not known")
ACC_BANDS = ("under 250 units", "250 to 500", "500 to 750", "750 to 1100", "over 1100", "enemy's place not known")
ACC_EDGES = (250.0, 500.0, 750.0, 1100.0)
CROSS_BANDS = ("enemy crossing under 15 degrees a second", "15 to 30", "30 to 60", "over 60")
DEAD_S = 2.1                                                   # a fragged player is back after this long (the median of the pros' own deaths)
# the pros' own stack by the seconds since they spawned (medians of 71 demos): what an enemy not seen for a while is guessed to have
PRIOR_T = (0.0, 3.5, 7.5, 12.5, 17.5, 25.0, 37.5, 52.5, 75.0, 105.0, 150.0)
PRIOR_V = (125.0, 122.0, 119.0, 126.0, 129.0, 138.0, 151.0, 163.0, 181.0, 188.0, 211.0)
DMG = {0: 70.0, 1: 80.0, 2: 6.0, 3: 5.0, 4: 40.0, 5: 60.0, 6: 20.0, 7: 8.0, 8: 50.0}     # what a hit of his is counted as, by weapon (WEAPONS' order)
EST_BANDS = ("enemy guessed under 60", "enemy guessed 60 to 125", "enemy guessed over 125", "enemy not guessed")
FIGHT_FACTORS = (("his health and armor", STACK_BANDS), ("the enemy's, as he can guess it", EST_BANDS),
                 ("in his hand", ("lightning", "rail", "rockets", "another weapon")),
                 ("in the enemy's hand", ("lightning or rail", "rockets", "another weapon", "not known")),
                 ("height", ("he stands higher", "level", "he stands lower")),
                 ("his cell for the pros", ("weak (under -0.05)", "neither", "strong (over +0.05)", "no number")),
                 ("distance", DIST_BANDS), ("score", ("behind", "level", "ahead")),
                 ("time left", ("over 3 minutes left", "3 minutes or less left", "overtime or no clock")),
                 ("the enemy spawned", ("under 10 s ago", "10 to 25 s ago", "over 25 s ago")))
FIGHT_PAIRS = ((0, 1), (0, 3), (1, 6), (0, 7), (0, 9))
CHOICES = ("takes it", "refuses it", "neither")
FIGHT_COLS = ("x", "y", "z", "his stack band", "enemy guessed band", "his weapon", "enemy's weapon", "height", "cell", "distance band", "score", "time left",
              "enemy spawned", "choice: 0 takes, 1 refuses, 2 neither", "damage dealt in 5 s (counted)", "taken in 5 s", "dealt in 10 s (-1: not known)",
              "taken in 10 s", "a frag for him within 10 s", "a frag of him", "he takes a big item within 15 s", "the enemy is seen or heard taking one",
              "distance", "enemy guessed", "his stack", "he is still in it after 3 s (takes it, the view not broken, not 150 farther)")
ERR_BANDS = ("0 to 5 degrees off", "5 to 10", "10 to 20", "20 to 40", "40 to 80", "over 80")
ERR_EDGES = (5.0, 10.0, 20.0, 40.0, 80.0)
FLICK_W = ("lightning", "rail", "rockets", "another weapon")
FAST = 350.0
VIEW_STEP = 16                                                 # every this many frames with no enemy in view, a sample for places and doorways
SOLID = 1
LEADS = {1: "ahead", 0: "level", -1: "behind"}
STATES = [l + ", " + p for l in ("ahead", "level", "behind") for p in ("before 7:00", "after 7:00")]
STATE_KEYS = ("time", "alive", "inview", "toward", "dist", "frags", "deaths", "travel_t", "travel_d", "stack", "fire",
              "blind_rl", "blind_gl", "blind_pg", "rl", "gl", "pg", "away_rl", "away_gl", "away_pg")


def make_record(t, pos, vel, yaw, pitch, weapon, shots, health, armor, score, enemy, enemy_score=None, lead=None,
                clock=None, alive=None, eye_h=None, enemy_air=None, hits=None, seg=None, ammo=None, client=None, owned=None,
                enemy_weapon=None, ground=None, enemy_sound=None, obits=None, enemy_life=None, clock_exact=None, enemy_pick=None):
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
      enemy_weapon (N,) the weapon in the enemy's hand, an index of WEAPONS, -1 where it is not known (None: never)
      ground     (N,) he stands on the ground (None: not known: no walking numbers, and a fall is read from his height)
      enemy_sound (N,) what the enemy did on this frame that is heard: 1 a jump, 2 a shot, 4 a pickup, added up; 0 nothing
                 or his place not known (None: sounds not known)
      obits      (K, 3) every death of the game: seconds (t's clock), the victim, the killer (-1: the world), the two as
                 `client` numbers (None: frags and deaths are read from his score and his health, inside a stretch only)
      enemy_life (N,) seconds since the enemy last died, or since the game began (None: not known)
      clock_exact (N,) the game clock where `clock` has none (a timeout, a demo that begins in a game); None: `clock`
      enemy_pick (M, 4) what the enemy was seen or heard picking up: frame, health and armor it gives, 1 for mega or an
                 armor (red, yellow), 1 for health"""
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
    r["ground"] = None if ground is None else np.asarray(ground, bool)
    r["enemy_sound"] = None if enemy_sound is None else np.asarray(enemy_sound, np.int64)
    r["obits"] = None if obits is None else np.asarray(obits, np.float64).reshape(-1, 3)
    r["enemy_life"] = None if enemy_life is None else np.asarray(enemy_life, np.float64)
    r["clock_exact"] = None if clock_exact is None else np.asarray(clock_exact, np.float64)
    r["enemy_pick"] = None if enemy_pick is None else np.asarray(enemy_pick, np.int64).reshape(-1, 4)
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
    los = inview.copy()                                         # `los`: a clear line to the enemy, wherever his view points
    idx = np.nonzero(have & (dist < SIGHT) & ~(cosang > FOV_COS))[0]
    if world is not None and len(idx):
        f1 = world.lines(eye[idx], en[idx] + np.array([0, 0, 8.0], np.float32), mask=SOLID)
        f2 = world.lines(eye[idx], en[idx] + np.array([0, 0, 26.0], np.float32), mask=SOLID)
        los[idx] = (f1 >= 0.999) | (f2 >= 0.999)
    rec["los"] = los
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
                trips={}, aggro={}, aggro_dist={},
                quiet=dict(ground={}, steady={}, crouch={}, by={}),
                when={w: dict(n=0, since={}, item={}, hurt=0, hurt_bad=0, after_death=0) for w in ("rl", "gl", "pg")},
                when_base=dict(alive=0.0, hurt=0.0, hurt_bad=0.0, after_death=0.0),
                hitcombo=dict(known=0.0, rl_shots=0, rl_hits=0, gl_shots=0, gl_hits=0, rl_lg=0, rl_rg=0, gl_lg=0, gl_rg=0, juggle=0, frags=0,
                              frags_combo=0, frags_juggle=0),
                look=dict(nv=0.0, known=0.0, at_enemy=0.0, ever=0.0, at_last=0.0, item=0.0, at_item=0.0, sight={}),
                holds=dict(n=0, time=0.0, alive=0.0, dur=[], seen3=0, dealt_first=0, took_first=0, frag5=0, died5=0, ended_by_view=0, w={},
                           look_time=0.0, look_item=0.0, look_exit=0.0, trap_shots=0, traps=0, with_trap=0, trap_frags=0, cells={}),
                hands=dict(turn=dict(travel={}, fight={}), flick=dict(n=0, size={}, peak={}, t_peak={}, shot={}, hit={}, err0={}, err3={}, shot_none=0, hit_none=0),
                           acc={}, lg_cross={}, lg_track=dict(time=0.0, reversals=0)),
                fight=dict(by={}, hit50={}),
                fights=dict(one={}, two={}), est_check=[], flickc={},
                tview=dict(move={}, fast=dict(time=0.0, along=0.0, ever=0.0, at_last=0.0, sample=0.0, at_place=0.0, door=0.0, at_door=0.0),
                           nv=dict(time=0.0, along=0.0, ever=0.0, at_last=0.0, sample=0.0, at_place=0.0, door=0.0, at_door=0.0)))


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
    n0 = len(rec["t"])
    ok0 = ~rec["first"] & rec["alive"] & np.concatenate([[False], rec["alive"][:-1]])
    dh0, da0 = np.zeros(n0), np.zeros(n0)
    dh0[1:], da0[1:] = np.diff(rec["health"]), np.diff(rec["armor"])
    big_picks = [_picks(rec, it, ok0, dh0 if it["col"] == "health" else da0) if it["col"] in ("health", "armor") else None for it in info["big"]]
    took = np.maximum(0.0, -(dh0 + da0)) * ok0                   # what a frame took off his health and armor (the slow loss above 100 is 1 a second)
    took[took < 3.0] = 0.0
    ctook = np.cumsum(took)
    tt = rec["t"]
    back5 = np.searchsorted(tt, tt - HURT_S, side="left")
    taken5 = ctook - ctook[np.maximum(back5 - 1, 0)]
    dead_t = np.where(~rec["alive"], tt, -np.inf)                # when he last was dead, within the stretch
    for a_, b_ in zip(np.nonzero(rec["first"])[0], np.concatenate([np.nonzero(rec["first"])[0][1:], [n0]])):
        dead_t[a_:b_] = np.maximum.accumulate(dead_t[a_:b_])
    after_death = rec["alive"] & (tt - dead_t <= DIED_S)
    ever = np.zeros(n0, bool)                                    # the enemy has been in view in this stretch
    for a_, b_ in zip(np.nonzero(rec["first"])[0], np.concatenate([np.nonzero(rec["first"])[0][1:], [n0]])):
        ever[a_:b_] = np.maximum.accumulate(rec["inview"][a_:b_])
    al_ = rec["alive"]
    T["when_base"] = dict(alive=float(rec["w"][al_].sum()), hurt=float(rec["w"][al_ & (taken5 >= HURT)].sum()),
                          hurt_bad=float(rec["w"][al_ & (taken5 >= HURT_BAD)].sum()), after_death=float(rec["w"][after_death].sum()))
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
                W_ = T["when"][WEAPONS[wq]]                        # when and at what the spam goes
                sb_ = 4 if not ever[i] else 0 if since[i] < 2.0 else 1 if since[i] < 5.0 else 2 if since[i] < 10.0 else 3
                dn_ = [float(np.linalg.norm(L - b_["pos"])) for b_ in info["big"]]
                k_ = int(np.argmin(dn_)) if dn_ else -1
                if k_ < 0 or dn_[k_] > NEAR_ITEM:
                    ic_ = 5
                elif big_picks[k_] is None:
                    ic_ = 4
                else:
                    pk_ = big_picks[k_][(big_picks[k_] < i) & (seg[big_picks[k_]] == seg[i])] if len(big_picks[k_]) else big_picks[k_]
                    left_ = t[pk_[-1]] + info["big"][k_]["back"] - t[i] if len(pk_) else -1.0
                    ic_ = 3 if left_ <= 0 else 0 if left_ <= 5.0 else 1 if left_ <= 10.0 else 2
                W_["n"] += int(cnt)
                W_["since"][str(sb_)] = W_["since"].get(str(sb_), 0) + int(cnt)
                W_["item"][str(ic_)] = W_["item"].get(str(ic_), 0) + int(cnt)
                W_["hurt"] += int(cnt) * int(taken5[i] >= HURT)
                W_["hurt_bad"] += int(cnt) * int(taken5[i] >= HURT_BAD)
                W_["after_death"] += int(cnt) * int(after_death[i])
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
        picks = _picks(rec, it, ok, dh if it["kind"] == "mega" else da)
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
    predictable(rec, info, T, dh, da, ok, seg_end, sh)
    sight, view = sightings(rec, T, seg_end, frag, died, fire)
    quiet(rec, T, ever, stack)
    hits, pr = hit_combos(rec, T, sh, frag, world, seg_end)
    starts_ = np.nonzero(inview & ~rec["first"] & (np.concatenate([[0.0], since[:-1]]) >= SIGHT_OUT_S - 0.03))[0]
    looking(rec, T, info, starts_, ever)
    holds(rec, T, info, world, hits, pr, took, frag, died, seg_end, since)
    hands(rec, T, starts_, hits, pr, sh, seg_end)
    fight_move(rec, T, took, stack, seg_end)
    est, prior = enemy_estimate(rec, hits)
    his_big = np.array(sorted({int(x) for k_, bp in enumerate(big_picks) if bp is not None and info["big"][k_]["back"] > 5.0 for x in bp}), np.int64)
    frows = fights(rec, T, info, starts_, hits, took, stack, est, prior, seg_end, his_big, frag, died)
    flick_curve(rec, T, hits, pr, sh, seg_end)
    travel_view(rec, T, info, world, ever)
    return T, dict(blind=rows, sight=sight, view=view, fight=frows)


def enemy_estimate(rec, hits):
    """the enemy's health plus armor as he can guess it, frame by frame: 125 as the enemy spawns; less what his own hits
    are counted as (DMG); more by what he sees or hears him pick up; and while he has not had him in view for 3 s it
    rises toward what the pros themselves have that long after a spawn (PRIOR), a fifteenth of the gap a second. A
    stretch begins at that table's value. Returns the guess and the table's value alone; (None, None) without
    `enemy_life`."""
    life = rec["enemy_life"]
    if life is None:
        return None, None
    n = len(life)
    prior = np.interp(np.maximum(life - DEAD_S, 0.0), PRIOR_T, PRIOR_V)
    delta = np.zeros(n)
    for f, wq, _ in hits:
        delta[f] -= DMG.get(int(wq), 10.0)
    if rec["enemy_pick"] is not None:
        for f, amount, _, _ in rec["enemy_pick"]:
            if 0 <= f < n:
                delta[f] += amount
    est = np.zeros(n)
    e = float(prior[0])
    first, since, w = rec["first"], rec["since"], rec["w"]
    for i in range(n):
        if first[i]:
            e = float(prior[i])
        elif life[i] < life[i - 1] - 0.5:                       # he died: he is back with what a spawn gives
            e = 125.0
        e += delta[i]
        if e > 200.0:
            e -= 2.0 * w[i]
        if since[i] > 3.0 and e < prior[i]:
            e += (prior[i] - e) * w[i] / 15.0
        e = min(max(e, 1.0), 400.0)
        est[i] = e
    return est, prior


def fights(rec, T, info, starts, hits, took, stack, est, prior, seg_end, his_big, frag, died):
    """fights taken and refused. An offer is a sighting. He takes it when within 3 s he deals damage or is 150 units or
    more nearer; refuses it when he does neither and the enemy is out of his view for 0.5 s at a stretch or he is 150 or
    more farther; else neither. How it went: the damage he deals (his hits, counted by DMG) and takes (his own health
    and armor) in 5 and 10 s, a frag for him or of him within 10 s, a big item for him or (seen or heard) the enemy
    within 15 s. Counted by every side of the situation (FIGHT_FACTORS) and a few pairs of them; returns a row a
    sighting (FIGHT_COLS)."""
    Fx = T["fights"]
    t, w, alive, inview, pos, en, dist = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["pos"], rec["enemy"], rec["dist"]
    n = len(t)
    dmg = np.zeros(n)
    for f, wq, _ in hits:
        dmg[f] += DMG.get(int(wq), 10.0)
    cd, ct = np.concatenate([[0.0], np.cumsum(dmg)]), np.concatenate([[0.0], np.cumsum(took)])
    hitc = dmg > 0
    ob = rec["obits"]
    ebig = np.sort(rec["enemy_pick"][rec["enemy_pick"][:, 2] > 0, 0]) if rec["enemy_pick"] is not None else np.zeros(0, np.int64)
    cellv = info.get("cellv") or {}
    ce = rec["clock_exact"] if rec["clock_exact"] is not None else rec["clock"]
    # ---- how good the guess of the enemy's stack is: at a cut to the other player his true stack is seen
    if est is not None:
        for i in np.nonzero(rec["first"])[0]:
            if i > 0 and rec["client"][i] != rec["client"][i - 1] and t[i] - t[i - 1] <= 0.25 and alive[i] and alive[i - 1]:
                T["est_check"].append([int(round(est[i - 1])), int(round(prior[i - 1])), int(round(stack[i]))])
    rows = []
    for i in starts:
        e3 = min(int(np.searchsorted(t, t[i] + 3.0, side="right")) - 1, int(seg_end[i]))
        if e3 <= i:
            continue
        dead = np.nonzero(~alive[i:e3 + 1])[0]
        ea = i + int(dead[0]) - 1 if len(dead) else e3
        dealt3 = bool(hitc[i + 1:ea + 1].any())
        kn = np.nonzero(np.isfinite(dist[i:ea + 1]))[0]
        d0 = float(dist[i])
        d1 = float(dist[i + kn[-1]]) if len(kn) else d0
        broke, acc = False, 0.0
        for q in range(i, ea + 1):
            acc = acc + w[q] if not inview[q] else 0.0
            if acc >= SIGHT_BREAK_S:
                broke = True
                break
        choice = 0 if (dealt3 or d1 - d0 <= -150.0) else 1 if (broke or d1 - d0 >= 150.0) else 2
        stay = int(choice == 0 and not broke and d1 - d0 < 150.0 and not len(dead))
        e = int(seg_end[i])
        e5 = min(int(np.searchsorted(t, t[i] + 5.0, side="right")) - 1, e)
        e10 = int(np.searchsorted(t, t[i] + 10.0, side="right")) - 1
        known10 = e10 <= e
        e10 = min(e10, e)
        dealt5, taken5 = cd[e5 + 1] - cd[i + 1], ct[e5 + 1] - ct[i + 1]
        dealt10, taken10 = cd[e10 + 1] - cd[i + 1], ct[e10 + 1] - ct[i + 1]
        c = rec["client"][i]
        if ob is not None:
            m = (ob[:, 0] > t[i]) & (ob[:, 0] <= t[i] + 10.0)
            ffor, fof = bool((m & (ob[:, 2] == c) & (ob[:, 1] != c)).any()), bool((m & (ob[:, 1] == c)).any())
        else:
            ffor, fof = bool(frag[i + 1:e10 + 1].any()), bool(died[i + 1:e10 + 1].any())
        e15 = min(int(np.searchsorted(t, t[i] + 15.0, side="right")) - 1, e)
        ihim = bool(((his_big > i) & (his_big <= e15)).any())
        ien = bool(((ebig > i) & (ebig <= e15)).any())
        sb = 0 if stack[i] < 60 else 1 if stack[i] <= 125 else 2
        eb = 3 if est is None else 0 if est[i] < 60 else 1 if est[i] <= 125 else 2
        hw = {LG: 0, RG: 1, RL: 2}.get(int(rec["weapon"][i]), 3)
        ewq = int(rec["enemy_weapon"][i])
        ew = 3 if ewq < 0 else 0 if ewq in (LG, RG) else 1 if ewq == RL else 2
        dz = pos[i, 2] - en[i, 2]
        hg = 0 if dz >= HIGHER else 2 if dz <= -HIGHER else 1
        cv = cellv.get(tuple(int(x) for x in np.floor(pos[i] / np.array([256.0, 256.0, 128.0]))))
        cs = 3 if cv is None else 0 if cv < -0.05 else 2 if cv > 0.05 else 1
        db = 0 if d0 < 400 else 1 if d0 <= 800 else 2
        ld = int(rec["lead"][i]) + 1
        tl = 2 if not np.isfinite(ce[i]) or ce[i] > 600.0 else 0 if 600.0 - ce[i] > 180.0 else 1
        lf = 999.0 if rec["enemy_life"] is None else rec["enemy_life"][i] - DEAD_S
        es = 0 if lf < 10.0 else 1 if lf <= 25.0 else 2
        lv = (sb, eb, hw, ew, hg, cs, db, ld, tl, es)
        keys = ["one:{}:{}:{}".format(fi, lv[fi], choice) for fi in range(len(lv))] + ["one:all:0:{}".format(choice)] + \
            ["two:{},{}:{},{}:{}".format(a, b, lv[a], lv[b], choice) for a, b in FIGHT_PAIRS]
        for k in keys:
            grp, rest = k.split(":", 1)
            C = Fx[grp].setdefault(rest, dict(n=0, k10=0, dealt5=0.0, taken5=0.0, dealt10=0.0, taken10=0.0, ffor=0, fof=0, ihim=0, ien=0, stay=0))
            C["n"] += 1
            C["stay"] += stay
            C["dealt5"] += dealt5
            C["taken5"] += taken5
            if known10:
                C["k10"] += 1
                C["dealt10"] += dealt10
                C["taken10"] += taken10
            C["ffor"] += int(ffor)
            C["fof"] += int(fof)
            C["ihim"] += int(ihim)
            C["ien"] += int(ien)
        rows.append([int(round(float(x))) for x in pos[i]] + list(lv) + [choice, int(round(dealt5)), int(round(taken5)), int(round(dealt10)) if known10 else -1,
                                                                        int(round(taken10)), int(ffor), int(fof), int(ihim), int(ien), int(round(d0)),
                                                                        -1 if est is None else int(round(est[i])), int(round(float(stack[i]))), stay])
    return rows


def flick_curve(rec, T, hits, pr, sh, seg_end):
    """the flick by how far off target he is as the enemy appears. An appearance here: a clear line to the enemy after 1 s
    or more without one, wherever his view points (so the angle runs to 180). Per band of that angle, by the weapon of
    his first shot (the one in his hand if he does not fire) and by the distance: the time to his first shot and to
    his first hit, and the shots and hits of the first 0.5 s of his fire."""
    Fc = T["flickc"]
    t, alive, en, eye = rec["t"], rec["alive"], rec["enemy"], rec["eye"]
    los = rec["los"]
    last = np.where(los | rec["first"], t, -np.inf)
    since_los = t - np.maximum.accumulate(last)
    starts = np.nonzero(los & ~rec["first"] & (np.concatenate([[0.0], since_los[:-1]]) >= SIGHT_OUT_S - 0.03))[0]
    if not len(starts):
        return
    fd = _fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    shf = sh[np.argsort(sh[:, 0], kind="stable")] if len(sh) else np.zeros((0, 3), np.int64)
    hit_fr = np.array(sorted({f for f, _, _ in hits}), np.int64)
    hit_shot = [(int(pr[k, 0]) if k >= 0 else f, wq) for f, wq, k in hits]     # the frame of the shot that hit, its weapon
    up = np.array([0, 0, 8.0])
    for i in starts:
        d = en[i] + up - eye[i]
        err = float(np.degrees(np.arccos(np.clip((d / (np.linalg.norm(d) + 1e-9)) @ fd[i], -1.0, 1.0))))
        eb = int(np.searchsorted(ERR_EDGES, err, side="right"))
        dist = float(np.linalg.norm(d))
        db = 0 if dist < 400 else 1 if dist <= 800 else 2
        e3 = min(int(np.searchsorted(t, t[i] + 3.0, side="right")) - 1, int(seg_end[i]))
        q = int(np.searchsorted(shf[:, 0], i)) if len(shf) else 0
        s1 = int(shf[q, 0]) if len(shf) and q < len(shf) and shf[q, 0] <= e3 else -1
        wq = int(shf[q, 1]) if s1 >= 0 else int(rec["weapon"][i])
        wc = {LG: 0, RG: 1, RL: 2}.get(wq, 3)
        h1 = np.searchsorted(hit_fr, i)
        hf = int(hit_fr[h1]) if h1 < len(hit_fr) and hit_fr[h1] <= e3 else -1
        s05 = h05 = 0
        if s1 >= 0:
            e05 = min(int(np.searchsorted(t, t[s1] + 0.5, side="right")) - 1, int(seg_end[i]))
            m = (shf[:, 0] >= s1) & (shf[:, 0] <= e05) & (shf[:, 1] == wq)
            s05 = int(shf[m, 2].sum())
            h05 = sum(1 for s0, w_ in hit_shot if s1 <= s0 <= e05 and w_ == wq)
        for key in ("e{}".format(eb), "e{}:w{}".format(eb, wc), "e{}:d{}".format(eb, db), "w{}".format(wc)):
            C = Fc.setdefault(key, dict(n=0, shot={}, shot_none=0, hit={}, hit_none=0, s05=0, h05=0))
            C["n"] += 1
            if s1 >= 0:
                _hadd(C["shot"], t[s1] - t[i], 0.05, 3.0)
            else:
                C["shot_none"] += 1
            if hf >= 0:
                _hadd(C["hit"], t[hf] - t[i], 0.05, 3.0)
            else:
                C["hit_none"] += 1
            C["s05"] += s05
            C["h05"] += min(h05, s05)


def travel_view(rec, T, info, world, ever):
    """where his view points with nobody in view: against his direction of travel (at FAST or more), and how much of the
    time it is within NEAR_DEG of where he last saw the enemy, of one of the map's places (the pros' blind shots land
    there; a clear line to it), of the doorway the enemy would come through (the first spot on the enemy's way from
    where he was last seen to him, by the walking map, that he has a clear line to). The last two on every VIEW_STEP-th
    frame."""
    V = T["tview"]
    t, w, alive, inview, pos, eye, en = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["pos"], rec["eye"], rec["enemy"]
    n = len(t)
    fd = _fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    cosn = np.cos(np.radians(NEAR_DEG))
    hsp = np.hypot(rec["vel"][:, 0], rec["vel"][:, 1])
    nv = alive & ~inview
    fast = nv & (hsp >= FAST)
    off = np.abs((rec["yaw"] - np.degrees(np.arctan2(rec["vel"][:, 1], rec["vel"][:, 0])) + 180.0) % 360.0 - 180.0)
    _hadd(V["move"], off[fast], 10.0, 170.0, w[fast])
    last = np.maximum.accumulate(np.where(inview, np.arange(n), 0))
    lastpos = np.where(np.isfinite(en[last]), en[last], 0.0).astype(np.float64) + np.array([0, 0, 8.0])
    dl = lastpos - eye
    at_last = (dl * fd).sum(1) / (np.linalg.norm(dl, axis=1) + 1e-9) >= cosn
    places = np.array(info.get("places") or [], np.float64).reshape(-1, 3)
    nodes, hop = info.get("nav_nodes"), info.get("nav_hop")
    samp = np.zeros(n, bool)
    samp[::VIEW_STEP] = True
    samp &= nv
    at_place = np.zeros(n, bool)
    door = np.zeros(n, bool)
    at_door = np.zeros(n, bool)
    idx = np.nonzero(samp)[0]
    if len(idx) and len(places) and world is not None:
        for q in range(len(places)):
            d = places[q] + np.array([0, 0, 16.0]) - eye[idx]
            dn = np.linalg.norm(d, axis=1) + 1e-9
            m = ((d * fd[idx]).sum(1) / dn >= cosn) & (dn <= 3000.0) & ~at_place[idx]
            if m.any():
                m[m] = world.lines(eye[idx][m], np.repeat((places[q] + np.array([0, 0, 16.0]))[None], int(m.sum()), 0), mask=SOLID) >= 0.999
                at_place[idx[m]] = True
    if len(idx) and nodes is not None and world is not None:
        di = idx[ever[idx]]
        if len(di):
            a_ = np.concatenate([np.linalg.norm(nodes[None, :, :] - pos[di[q:q + 200]][:, None, :], axis=2).argmin(1) for q in range(0, len(di), 200)])
            b_ = np.concatenate([np.linalg.norm(nodes[None, :, :] - lastpos[di[q:q + 200]][:, None, :], axis=2).argmin(1) for q in range(0, len(di), 200)])
            for i, a, b in zip(di, a_, b_):
                path, k = [int(b)], int(b)
                while k != a and len(path) < 64:
                    k = int(hop[k, a])
                    if k < 0:
                        break
                    path.append(k)
                P = nodes[path] + np.array([0, 0, 8.0])
                vis = world.lines(np.repeat(eye[i][None], len(P), 0), P, mask=SOLID) >= 0.999
                if not vis.any():
                    continue
                door[i] = True
                target = lastpos[i] if vis[0] else P[int(np.argmax(vis))]
                d = target - eye[i]
                at_door[i] = float(d @ fd[i]) / (np.linalg.norm(d) + 1e-9) >= cosn
    ws = w * VIEW_STEP
    for name, m in (("fast", fast), ("nv", nv)):
        V[name] = dict(time=float(w[m].sum()), along=float(w[m & (off <= NEAR_DEG)].sum()), ever=float(w[m & ever].sum()), at_last=float(w[m & ever & at_last].sum()),
                       sample=float(ws[m & samp].sum()), at_place=float(ws[m & at_place].sum()), door=float(ws[m & door].sum()), at_door=float(ws[m & at_door].sum()))


def _hadd(h, vals, step, top, weights=None):
    """values into a histogram kept as {bin: count}, bins `step` wide, everything from `top` on in the last"""
    vals = np.atleast_1d(np.asarray(vals, np.float64))
    if not len(vals):
        return
    b = np.minimum((np.maximum(vals, 0.0) / step).astype(np.int64), int(top / step))
    c = np.bincount(b, weights=None if weights is None else np.atleast_1d(weights))
    for k in np.nonzero(c)[0]:
        h[str(int(k))] = round(h.get(str(int(k)), 0) + float(c[k]), 3)


def _hq(h, q, step):
    """the q-th percentile of a histogram {bin: count}: the middle of the bin it falls in"""
    ks = sorted((int(k), v) for k, v in h.items())
    tot = sum(v for _, v in ks)
    acc = 0.0
    for k, v in ks:
        acc += v
        if tot and acc >= q / 100.0 * tot:
            return round((k + 0.5) * step, 3)
    return None


def _hunder(h, below, step):
    """the share of a histogram under a value, %"""
    tot = sum(h.values())
    return round(100.0 * sum(v for k, v in h.items() if (int(k) + 1) * step <= below) / tot, 1) if tot else None


def looking(rec, T, info, starts, ever):
    """where he looks with no enemy in view. At every sighting (the enemy comes into view after SIGHT_OUT_S or more out
    of it) the angle between his view and the direction to the place the enemy appears at, sideways and up-down apart,
    on that frame and 0.25 and 0.5 s before it, by the time unseen and by whether a sound of the enemy's reached him in
    the last second. And of his time with no enemy in view: how much his view is within NEAR_DEG of the enemy's true
    place (where it is known), of the place he last saw him, of the nearest mega or armor."""
    L = T["look"]
    t, w, alive, inview, pos, eye, en = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["pos"], rec["eye"], rec["enemy"]
    n = len(t)
    fd = _fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    cosn = np.cos(np.radians(NEAR_DEG))

    def at(target, m):
        d = target - eye
        d = d / (np.linalg.norm(d, axis=1)[:, None] + 1e-9)
        return m & ((d * fd).sum(1) >= cosn)
    up = np.array([0, 0, 8.0])
    nv = alive & ~inview
    known = nv & np.isfinite(en[:, 0])
    L["nv"], L["known"] = float(w[nv].sum()), float(w[known].sum())
    L["at_enemy"] = float(w[at(np.where(np.isfinite(en), en, 0.0) + up, known)].sum())
    last = np.maximum.accumulate(np.where(inview, np.arange(n), 0))
    ev = nv & ever
    L["ever"], L["at_last"] = float(w[ev].sum()), float(w[at(np.where(np.isfinite(en[last]), en[last], 0.0) + up, ev)].sum())
    if info["items"]:
        I = np.array([it["pos"] for it in info["items"]], np.float64)
        near = I[np.linalg.norm(pos[:, None, :] - I[None], axis=2).argmin(1)]
        L["item"], L["at_item"] = float(w[nv].sum()), float(w[at(near, nv)].sum())
    seg0 = np.maximum.accumulate(np.where(rec["first"], np.arange(n), 0))
    snd = rec["enemy_sound"]
    for i in starts:
        target = en[i] + up
        ub = 0 if rec["since"][i - 1] < 3.0 else 1 if rec["since"][i - 1] < 10.0 else 2
        if snd is None:
            hb = 2
        else:
            a = max(int(np.searchsorted(t, t[i] - 1.0)), int(seg0[i]))
            hb = int(bool(((snd[a:i] > 0) & (rec["dist"][a:i] <= HEAR_R)).any()))
        for lag, ln in ((0.0, "0"), (0.25, "25"), (0.5, "50")):
            j = i if lag == 0 else int(np.searchsorted(t, t[i] - lag + 1e-6, side="right")) - 1
            if j < seg0[i] or not alive[j]:
                continue
            d = target - eye[j]
            h = abs((np.degrees(np.arctan2(d[1], d[0])) - rec["yaw"][j] + 180.0) % 360.0 - 180.0)
            v = abs(-np.degrees(np.arctan2(d[2], np.hypot(d[0], d[1]))) - rec["pitch"][j])
            S = L["sight"].setdefault("{}|{}|{}".format(ln, ub, hb), dict(n=0, h={}, v={}))
            S["n"] += 1
            for name, x, top in (("h", h, 179), ("v", v, 89)):
                k = str(int(min(x, top)))
                S[name][k] = S[name].get(k, 0) + 1


def holds(rec, T, info, world, hits, pr, took, frag, died, seg_end, since):
    """holds and traps: the stretches he stays within HOLD_R of where the stretch began for HOLD_S or more, alive, no
    enemy in view, rockets, lightning or rail in hand; what follows them, where they are, what his view points at, and
    the blind rockets and grenades fired from them that hit"""
    Hd = T["holds"]
    t, w, alive, inview, pos = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["pos"]
    n = len(t)
    Hd["alive"] = float(w[alive].sum())
    okh = alive & ~inview & np.isin(rec["weapon"], BIG_W)
    bad = np.concatenate([[0], np.cumsum(~okh)])
    j2 = np.minimum(np.searchsorted(t, t + HOLD_S), n - 1)
    mid = (np.arange(n) + j2) // 2
    cand = okh & (t[j2] - t >= HOLD_S - 0.03) & (j2 <= seg_end) & (bad[j2 + 1] == bad[np.arange(n)]) & \
        (np.linalg.norm(pos[j2] - pos, axis=1) <= HOLD_R) & (np.linalg.norm(pos[mid] - pos, axis=1) <= HOLD_R)
    hitc = np.zeros(n, bool)                                    # his hit counter steps on this frame
    if rec["hits"] is not None:
        hitc[1:] = (np.diff(rec["hits"]) > 0) & ~rec["first"][1:]
    hurt = took > 0
    fd = _fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    cosn = np.cos(np.radians(NEAR_DEG))
    big = np.array([b["pos"] for b in info["big"]], np.float64).reshape(-1, 3)
    exits = np.array(info.get("exits", []), np.float64).reshape(-1, 3)
    shot_hit = {}                                               # a projectile's row -> the frame it hit on
    for f, wq, k in hits:
        if k >= 0 and k not in shot_hit:
            shot_hit[k] = f
    done = -1
    for a in np.nonzero(cand)[0]:
        if a <= done:
            continue
        K = int(min(seg_end[a], a + 4000))
        out = np.nonzero((np.linalg.norm(pos[a:K + 1] - pos[a], axis=1) > HOLD_R) | ~okh[a:K + 1])[0]
        b = a + int(out[0]) - 1 if len(out) else K
        if t[b] - t[a] < HOLD_S - 0.03:
            continue
        done = b
        Hd["n"] += 1
        Hd["time"] += float(w[a:b + 1].sum())
        Hd["dur"].append(round(float(t[b] - t[a]), 2))
        wn = WEAPONS[int(rec["weapon"][a])]
        Hd["w"][wn] = Hd["w"].get(wn, 0) + 1
        e = int(seg_end[a])
        e3 = min(int(np.searchsorted(t, t[b] + 3.0, side="right")) - 1, e)
        e5 = min(int(np.searchsorted(t, t[b] + 5.0, side="right")) - 1, e)
        Hd["seen3"] += int(inview[b + 1:e3 + 1].any())
        Hd["ended_by_view"] += int(b + 1 <= e and bool(inview[b + 1]))
        fh, ft = np.nonzero(hitc[b + 1:e5 + 1])[0], np.nonzero(hurt[b + 1:e5 + 1])[0]
        Hd["dealt_first"] += int(len(fh) > 0 and (len(ft) == 0 or fh[0] <= ft[0]))
        Hd["took_first"] += int(len(ft) > 0 and (len(fh) == 0 or ft[0] < fh[0]))
        Hd["frag5"] += int(frag[b + 1:e5 + 1].any())
        Hd["died5"] += int(died[b + 1:e5 + 1].any())
        # where: the cell of tools/pro_places.py's table (256 x 256 x 128), named by the nearest big item
        c = np.floor(pos[a] / np.array([256.0, 256.0, 128.0])).astype(np.int64)
        midc = (c + 0.5) * np.array([256.0, 256.0, 128.0])
        lab, un = "", 0
        if len(big):
            dn = np.linalg.norm(big - midc, axis=1)
            lab, un = info["big"][int(dn.argmin())]["label"], int(round(float(dn.min())))
        ck = "{}:{}:{}:{}:{}:{}".format(info["name"], int(c[0]), int(c[1]), int(c[2]), lab, un)
        C = Hd["cells"].setdefault(ck, dict(n=0))
        C["n"] += 1
        C[wn] = C.get(wn, 0) + 1
        # what his view points at: a big item, a teleporter's exit (within NEAR_DEG, a clear line to it), every fourth frame
        fr = np.arange(a, b + 1, 4)
        ww = np.array([w[q:q + 4].sum() for q in fr])
        seen = {}
        for name, P in (("item", big), ("exit", exits)):
            hit_ = np.zeros(len(fr), bool)
            for q in range(len(P)):
                d = P[q] + np.array([0, 0, 8.0]) - rec["eye"][fr]
                d = d / (np.linalg.norm(d, axis=1)[:, None] + 1e-9)
                m = (d * fd[fr]).sum(1) >= cosn
                if m.any() and world is not None:
                    m[m] = world.lines(rec["eye"][fr][m], np.repeat((P[q] + np.array([0, 0, 8.0]))[None], int(m.sum()), 0), mask=SOLID) >= 0.999
                hit_ |= m
            seen[name] = hit_
        Hd["look_time"] += float(ww.sum())
        Hd["look_item"] += float(ww[seen["item"]].sum())
        Hd["look_exit"] += float(ww[seen["exit"]].sum())
        # a trap: a blind rocket or grenade fired during the hold or within a second after it that hits within 1.5 s
        if pr is not None and len(pr):
            b1 = min(int(np.searchsorted(t, t[b] + 1.0, side="right")) - 1, e)
            ks = np.nonzero((pr[:, 0] >= a) & (pr[:, 0] <= b1) & np.isin(pr[:, 1], (RL, GL)) & (since[pr[:, 0]] >= BLIND_S))[0]
            Hd["trap_shots"] += len(ks)
            got = [k for k in ks if k in shot_hit and t[shot_hit[k]] - t[pr[k, 0]] <= 1.5]
            Hd["traps"] += len(got)
            Hd["with_trap"] += int(len(got) > 0)
            Hd["trap_frags"] += int(any(frag[shot_hit[k]:min(int(np.searchsorted(t, t[shot_hit[k]] + 2.0, side="right")), e + 1)].any() for k in got))


def hands(rec, T, starts, hits, pr, sh, seg_end):
    """his hands as a demo shows them: how fast his view turns (travelling, with the enemy in view), the flick after a
    sighting, accuracy by weapon and distance from the hits as hit_combos() gives them, lightning by how fast the enemy
    crosses his view, and how often his view changes its turning direction while he tracks with lightning"""
    Hn = T["hands"]
    t, w, alive, inview, en, eye = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["enemy"], rec["eye"]
    n = len(t)
    fd = _fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    dt = np.diff(t)
    ok = alive[1:] & alive[:-1] & ~rec["first"][1:] & (dt > 0)
    turn = np.zeros(n)                                          # degrees a second, from the frame before
    turn[1:] = np.where(ok, np.degrees(np.arccos(np.clip((fd[1:] * fd[:-1]).sum(1), -1.0, 1.0))) / np.maximum(dt, 1e-3), 0.0)
    okf = np.concatenate([[False], ok])
    for name, m in (("travel", okf & ~inview), ("fight", okf & inview)):
        _hadd(Hn["turn"][name], turn[m], 10.0, 2000.0, w[m])
    # ---- the flick: the 0.3 s after the enemy comes into view
    F = Hn["flick"]
    shot_fr = np.array(sorted({int(x[0]) for x in sh}), np.int64) if len(sh) else np.zeros(0, np.int64)
    hit_fr = np.array(sorted({f for f, _, _ in hits}), np.int64)
    up = np.array([0, 0, 8.0])

    def err(j):
        d = en[j] + up - eye[j]
        return float(np.degrees(np.arccos(np.clip((d / (np.linalg.norm(d) + 1e-9)) @ fd[j], -1.0, 1.0))))
    for i in starts:
        j = int(np.searchsorted(t, t[i] + 0.3, side="right")) - 1
        if j > seg_end[i] or j <= i or not alive[i:j + 1].all():
            continue
        F["n"] += 1
        _hadd(F["size"], np.degrees(np.arccos(np.clip(fd[i] @ fd[j], -1.0, 1.0))), 1.0, 180.0)
        k = i + 1 + int(np.argmax(turn[i + 1:j + 1]))
        _hadd(F["peak"], turn[k], 20.0, 3000.0)
        _hadd(F["t_peak"], t[k] - t[i], 0.025, 0.5)
        _hadd(F["err0"], err(i), 1.0, 180.0)
        if np.isfinite(en[j, 0]):
            _hadd(F["err3"], err(j), 1.0, 180.0)
        for name, fr in (("shot", shot_fr), ("hit", hit_fr)):
            q = np.searchsorted(fr, i)
            if q < len(fr) and fr[q] <= seg_end[i] and t[fr[q]] - t[i] <= 3.0:
                _hadd(F[name], t[fr[q]] - t[i], 0.05, 3.0)
            else:
                F[name + "_none"] = F.get(name + "_none", 0) + 1
    # ---- accuracy by weapon and distance (the enemy's place where it is known), the hits as hit_combos() gives them
    dist = rec["dist"]

    def band(f):                                                # (the shot that kills him: he is gone on its frame, so the frame before)
        d = dist[f] if np.isfinite(dist[f]) or f == 0 or rec["first"][f] else dist[f - 1]
        return 5 if not np.isfinite(d) else int(np.searchsorted(ACC_EDGES, d, side="right"))

    def acc(wq, b, key, cnt=1):
        A = Hn["acc"].setdefault(WEAPONS[wq], {}).setdefault(str(b), dict(shots=0, hits=0, direct=0))
        A[key] += int(cnt)
    for i, wq, cnt in sh:
        if wq in (LG, RG, RL, PG, MG, SG):
            acc(int(wq), band(i), "shots", cnt)
    for f, wq, k in hits:
        if wq not in (LG, RG, RL, PG, MG, SG):
            continue
        s0 = int(pr[k, 0]) if k >= 0 else f                     # a rocket's and a plasma ball's distance is the one it was fired at
        acc(wq, band(s0), "hits")
        if wq == RL and k >= 0 and np.isfinite(en[f, 0]):       # direct: the enemy within 60 units of where the rocket was in the last 75 ms
            a0, a1 = PROJ[RL] * max(0.0, t[f] - t[s0] - 0.075), PROJ[RL] * (t[f] - t[s0])
            c = en[f] + up - eye[s0]
            along = float(np.clip(c @ fd[s0], a0, a1))
            if np.linalg.norm(c - fd[s0] * along) <= 60.0:
                acc(RL, band(s0), "direct")
    # ---- lightning: by how fast the enemy crosses his view, and the turns of his view while tracking
    lg = sh[sh[:, 1] == LG][:, 0] if len(sh) else np.zeros(0, np.int64)
    lg_hit = {f for f, wq, _ in hits if wq == LG}
    for i in lg:
        if i < 1 or rec["first"][i] or not (np.isfinite(en[i, 0]) and np.isfinite(en[i - 1, 0])) or t[i] <= t[i - 1]:
            continue
        rel = (en[i] - en[i - 1]) / (t[i] - t[i - 1]) - rec["vel"][i]
        d = en[i] + up - eye[i]
        dn = np.linalg.norm(d) + 1e-9
        cross = np.degrees(np.linalg.norm(rel - (rel @ d) / dn * d / dn) / dn)
        b = 0 if cross < 15 else 1 if cross < 30 else 2 if cross < 60 else 3
        C = Hn["lg_cross"].setdefault(str(b), dict(shots=0, hits=0))
        C["shots"] += 1
        C["hits"] += int(int(i) in lg_hit or int(i) + 1 in lg_hit)
    if len(lg):
        fire = np.zeros(n, bool)
        fire[lg] = True
        recent = np.convolve(fire.astype(np.int64), np.ones(5, np.int64))[:n] > 0   # a cell of lightning within the last 100 ms
        track = recent & inview & (rec["weapon"] == LG) & okf
        dy = np.zeros(n)
        dy[1:] = (np.diff(rec["yaw"].astype(np.float64)) + 180.0) % 360.0 - 180.0
        sg = np.where(np.abs(dy) > 0.1, np.sign(dy), 0.0)
        idx = np.nonzero(track & (sg != 0))[0]
        if len(idx) > 1:
            near = (np.diff(idx) <= 4) & (seg_end[idx[:-1]] >= idx[1:])
            Hn["lg_track"]["reversals"] += int((near & (sg[idx[1:]] != sg[idx[:-1]])).sum())
        Hn["lg_track"]["time"] += float(w[track].sum())


def fight_move(rec, T, took, stack, seg_end):
    """movement in a fight (the enemy in view within FIGHT_R): changes of strafe direction, time in the air and crouched,
    jumps, speed, the change of the distance, by the weapon in his hand, by the enemy's, by his health and armor; and
    what he does in the 2 s after a hit of BIG_HIT or more"""
    Fg = T["fight"]
    t, w, alive, inview, vel, dist = rec["t"], rec["w"], rec["alive"], rec["inview"], rec["vel"], rec["dist"]
    n = len(t)
    m = inview & (np.nan_to_num(dist, nan=1e9) <= FIGHT_R)
    yr = np.radians(rec["yaw"].astype(np.float64))
    lat = vel[:, 0] * np.sin(yr) - vel[:, 1] * np.cos(yr)       # his speed to his right
    sg = np.where(np.abs(lat) > 60.0, np.sign(lat), 0.0)
    idx = np.nonzero(sg != 0)[0]
    flip = np.zeros(n, bool)                                    # his strafe direction is the other one than the last time he strafed
    if len(idx) > 1:
        ch = (sg[idx[1:]] != sg[idx[:-1]]) & (t[idx[1:]] - t[idx[:-1]] <= 1.0) & (seg_end[idx[:-1]] >= idx[1:])
        flip[idx[1:][ch]] = True
    gr = rec["ground"]
    jump = np.zeros(n, bool)
    if gr is not None:
        jump[1:] = gr[:-1] & ~gr[1:] & (vel[1:, 2] > 150.0) & ~rec["first"][1:]
    both = np.zeros(n, bool)
    both[1:] = m[1:] & m[:-1] & ~rec["first"][1:]
    dd = np.zeros(n)
    dd[1:] = np.where(both[1:], np.nan_to_num(dist[1:]) - np.nan_to_num(dist[:-1]), 0.0)
    sp = np.hypot(vel[:, 0], vel[:, 1])
    hw, ew = rec["weapon"], rec["enemy_weapon"]
    sit = {"all": np.ones(n, bool),
           "lightning in his hand": hw == LG, "rail in his hand": hw == RG, "rockets in his hand": hw == RL, "another weapon in his hand": ~np.isin(hw, BIG_W),
           "enemy holds lightning or rail": np.isin(ew, (LG, RG)), "enemy holds rockets": ew == RL, "enemy holds another weapon": (ew >= 0) & ~np.isin(ew, BIG_W),
           "stack under 60": stack < 60, "stack 60 to 125": (stack >= 60) & (stack <= 125), "stack over 125": stack > 125}
    for name, q in sit.items():
        q = q & m
        Fg["by"][name] = dict(time=float(w[q].sum()), flips=int(flip[q].sum()), air=float(w[q & ~gr].sum()) if gr is not None else 0.0,
                              ground_known=float(w[q].sum()) if gr is not None else 0.0, crouch=float(w[q & (rec["eye_h"] < 20.0)].sum()),
                              jumps=int(jump[q].sum()), speed=float((sp[q] * w[q]).sum()), ddist=float(dd[q & both].sum()), ddist_time=float(w[q & both].sum()))
    # ---- after a hit of BIG_HIT or more that he lives through
    for h in np.nonzero((took >= BIG_HIT) & alive)[0]:
        e = int(np.searchsorted(t, t[h] + 2.0, side="right")) - 1
        if e > seg_end[h] or e <= h:
            continue
        sb = 0 if stack[h] < 60 else 1 if stack[h] <= 125 else 2
        seen = bool(inview[max(0, h - 20):h + 1].any())
        key = "{}|{}".format(int(seen), sb)
        C = Fg["hit50"].setdefault(key, dict(n=0, died=0, known=0, ddist=0.0, away=0, closer=0, lost=0, wchange=0, alive2=0))
        C["n"] += 1
        dead = not alive[h:e + 1].all()
        C["died"] += int(dead)
        if dead:
            continue
        C["alive2"] += 1
        C["wchange"] += int((rec["weapon"][h + 1:e + 1] != rec["weapon"][h]).any())
        if np.isfinite(dist[h]) and np.isfinite(dist[e]):
            C["known"] += 1
            C["ddist"] += float(dist[e] - dist[h])
            C["away"] += int(dist[e] - dist[h] > 100.0)
            C["closer"] += int(dist[e] - dist[h] < -100.0)
        if seen:
            acc_, lost = 0.0, 0
            for q in range(h + 1, e + 1):
                acc_ = acc_ + w[q] if not inview[q] else 0.0
                if acc_ >= 0.5:
                    lost = 1
                    break
            C["lost"] += lost


def _picks(rec, it, ok, col):
    """the frames he picks an item up on: what it gives rises (col) while he is at its spot, and no other item of its sort
    is nearer; one pickup cannot be within 5 s of the one before"""
    pos, t = rec["pos"], rec["t"]
    at = ok & (col > 0) & (np.hypot(pos[:, 0] - it["pos"][0], pos[:, 1] - it["pos"][1]) < TAKE_R) & (np.abs(pos[:, 2] - it["pos"][2]) < TAKE_Z)
    for o in it["rivals"]:
        at &= np.linalg.norm(pos - it["pos"], axis=1) <= np.linalg.norm(pos - o, axis=1)
    picks = np.nonzero(at)[0]
    if len(picks) > 1:
        picks = picks[np.concatenate([[True], np.diff(t[picks]) > 5.0])]
    return picks


def quiet(rec, T, ever, stack):
    """walking and quiet: his time by speed on the ground (all of it; while his speed is steady; crouched), and for every
    situation the steady time by speed, the time crouched and moving, standing, in the air (the walking band is chosen
    in report(), from the histogram)"""
    if rec["ground"] is None:
        return
    t, w, alive, pos = rec["t"], rec["w"], rec["alive"], rec["pos"]
    n = len(t)
    sp = np.hypot(rec["vel"][:, 0], rec["vel"][:, 1])
    gr = rec["ground"] & alive
    ds = np.abs(np.diff(sp))
    steady = gr.copy()
    steady[1:] &= (ds < STEADY) & ~rec["first"][1:]
    steady[:-1] &= ds < STEADY
    crouch = alive & (rec["eye_h"] < 20.0)
    b = np.minimum((sp / QUIET_BIN).astype(np.int64), QUIET_BINS - 1)
    Q = T["quiet"]
    for name, m in (("ground", gr), ("steady", steady & ~crouch), ("crouch", gr & crouch)):
        h = np.bincount(b[m], weights=w[m], minlength=QUIET_BINS)
        Q[name] = {str(k): round(float(v), 3) for k, v in enumerate(h) if v > 0}
    # the place the enemy was last seen at, within the stretch
    last = np.maximum.accumulate(np.where(rec["inview"], np.arange(n), 0))
    lastpos = np.where(np.isfinite(rec["enemy"][last]), rec["enemy"][last], 0.0)
    near = ever & (np.linalg.norm(pos - lastpos, axis=1) <= LAST_R)
    sp3 = np.linalg.norm(rec["vel"], axis=1)
    sit = {"enemy seen within 5 s": ever & (rec["since"] < SEEN_S), "enemy not seen for 5 s or more": ever & (rec["since"] >= SEEN_S),
           "enemy not seen yet in this stretch": ~ever,
           "stack under 60": stack < 60, "stack 60 to 125": (stack >= 60) & (stack <= 125), "stack over 125": stack > 125,
           "behind": rec["lead"] < 0, "level": rec["lead"] == 0, "ahead": rec["lead"] > 0,
           "within 600 units of where the enemy was last seen": near, "farther from where he was last seen": ever & ~near, "all": np.ones(n, bool)}
    for name, m in sit.items():
        m = m & alive
        h = np.bincount(b[m & steady & ~crouch], weights=w[m & steady & ~crouch], minlength=QUIET_BINS)
        Q["by"][name] = dict(alive=float(w[m].sum()), stand=float(w[m & (sp3 < STAND)].sum()), crouch_move=float(w[m & gr & crouch & (sp >= STAND)].sum()),
                             air=float(w[m & ~rec["ground"]].sum()), steady={str(k): round(float(v), 3) for k, v in enumerate(h) if v > 0})


def hit_combos(rec, T, sh, frag, world, seg_end):
    """combinations by hits, from his own hit counter. A step of the counter on a frame he fires lightning, rail, machine
    gun or shotgun on (or the frame before) is that weapon's hit; any other step is the hit of the rocket, grenade or
    plasma ball of his that is due about then (a rocket and plasma: from 0.05 s after the shot to 0.2 s after it would
    reach the wall his view points at; a grenade: until its fuse ends). Counted: a rocket (a grenade) that hit, then a
    lightning or rail hit within HIT_COMBO_S; a rocket hit, then another rocket's hit within JUGGLE_S; his frags within
    COMBO_FRAG_S after such a pair."""
    H = T["hitcombo"]
    if rec["hits"] is None or world is None:
        return [], None
    t, alive = rec["t"], rec["alive"]
    n = len(t)
    H["known"] = float(rec["w"][alive].sum())
    inc = np.zeros(n, np.int64)
    inc[1:] = np.diff(rec["hits"])
    inc[rec["first"]] = 0
    inc = np.clip(inc, 0, 8)
    H["frags"] = int(frag.sum())
    if not len(sh):
        return [], None
    scan = np.full(n, -1, np.int64)                              # the hitscan weapon he fires on a frame
    for i, wq, _ in sh:
        if wq in (LG, RG, MG, SG, HMG) and (scan[i] < 0 or wq in (LG, RG)):
            scan[i] = wq
    pr = sh[np.isin(sh[:, 1], (RL, GL, PG))]
    H["rl_shots"], H["gl_shots"] = int(pr[pr[:, 1] == RL, 2].sum()), int(pr[pr[:, 1] == GL, 2].sum())
    lo = np.zeros(len(pr))
    hi = np.zeros(len(pr))
    if len(pr):
        line = pr[:, 1] != GL
        dist = np.zeros(len(pr))
        if line.any():
            fd = _fwd(rec["yaw"][pr[line, 0]], rec["pitch"][pr[line, 0]])
            eye = rec["eye"][pr[line, 0]]
            dist[line] = 8192.0 * world.lines(eye, eye + fd * 8192.0, mask=SOLID)
        speed = np.array([PROJ[int(x)] for x in pr[:, 1]])
        lo = t[pr[:, 0]] + 0.05
        hi = np.where(line, t[pr[:, 0]] + dist / speed + 0.2, t[pr[:, 0]] + GL_FUSE + 0.2)
    used = np.zeros(len(pr), bool)
    hits = []                                                   # (frame, weapon, the projectile's row or -1)
    for f in np.nonzero(inc)[0]:
        left = int(inc[f])
        wq = scan[f] if scan[f] >= 0 else scan[f - 1] if f > 0 else -1
        if wq >= 0:
            hits.append((int(f), int(wq), -1))
            left -= 1
            if left <= 0:
                continue
        c = np.nonzero((lo <= t[f]) & (t[f] <= hi) & (seg_end[pr[:, 0]] >= f) & ~used)[0] if len(pr) else []
        if len(c):
            k = c[np.argmin(np.abs(hi[c] - 0.2 - t[f]))]        # the one due nearest to now
            used[k] = pr[k, 1] != PG
            hits.append((int(f), int(pr[k, 1]), int(k)))
    rl = [(f, k) for f, wq, k in hits if wq == RL]
    gl = [(f, k) for f, wq, k in hits if wq == GL]
    beam = [(f, wq) for f, wq, _ in hits if wq in (LG, RG)]
    H["rl_hits"], H["gl_hits"] = len(rl), len(gl)
    bf = np.array([f for f, _ in beam], np.int64)
    pairs, juggles = [], []
    for name, first in (("rl", rl), ("gl", gl)):
        for f, _ in first:
            j = np.nonzero((bf > f) & (t[bf] <= t[f] + HIT_COMBO_S) & (seg_end[f] >= bf))[0] if len(bf) else []
            if len(j):
                H[name + ("_lg" if beam[j[0]][1] == LG else "_rg")] += 1
                pairs.append(int(bf[j[0]]))
    for a in range(len(rl) - 1):
        f, f2 = rl[a][0], rl[a + 1][0]
        if rl[a][1] != rl[a + 1][1] and t[f2] - t[f] <= JUGGLE_S and seg_end[f] >= f2:
            H["juggle"] += 1
            juggles.append(int(f2))
    fr = np.nonzero(frag)[0]
    for name, ends in (("frags_combo", pairs), ("frags_juggle", juggles)):
        e = np.array(sorted(set(ends)), np.int64)
        if len(e) and len(fr):
            H[name] = int(sum(1 for x in fr if ((e <= x) & (t[x] - t[e] <= COMBO_FRAG_S)).any()))
    return hits, pr


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


def predictable(rec, info, T, dh, da, ok, seg_end, sh=()):
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
    rockets = np.array(sorted({int(x[0]) for x in sh if x[1] == RL}), np.int64)
    for (i, a), (j, b) in zip(ev[:-1], ev[1:]):
        if a == b or seg[i] != seg[j] or seg_end[i] < j or dead[j + 1] != dead[i] or not (TRIP_MIN_S <= t[j] - t[i] <= TRIP_MAX_S):
            continue
        kk = "{}:{}>{}".format(name, info["big"][a]["label"], info["big"][b]["label"])
        path = pos[i:j + 1].astype(np.float64)
        step = np.linalg.norm(np.diff(path, axis=0), axis=1)
        vz = rec["vel"][i:j + 12, 2]
        rj = 0
        for s_ in rockets[(rockets >= i) & (rockets <= j)] - i:   # his upward speed jumps just after a rocket of his: a rocket jump
            if vz[s_:s_ + 11].max() - vz[max(0, s_ - 1)] > RJ_UP:
                rj = 1
        z = path[:, 2]
        if rec["ground"] is not None:                           # the farthest he falls between leaving the ground and landing
            g = rec["ground"][i:j + 1]
            drop, start, tele_at = 0.0, z[0], np.concatenate([[False], step > TELE])
            for q in range(1, len(g)):
                if tele_at[q] or (g[q - 1] and not g[q]):       # he leaves the ground (or comes out of a teleporter): the fall starts here
                    start = z[q - 1] if not tele_at[q] else z[q]
                if g[q] and not g[q - 1]:
                    drop = max(drop, start - z[q])
                if g[q]:
                    start = z[q]
        else:
            drop = float(np.max(np.maximum.accumulate(z) - z))
        pieces, a0 = [], 0                                       # the path every WAY_STEP units; a teleporter is one step of it
        for c in list(np.nonzero(step > TELE)[0]) + [len(path) - 1]:
            piece = path[a0:c + 1]
            ln = float(step[a0:c].sum())
            pieces.append(_resample(piece, max(2, int(np.ceil(ln / WAY_STEP)) + 1)) if len(piece) > 1 and ln > 0 else piece[:1])
            a0 = c + 1
        T["trips"].setdefault(kk, []).append([round(float(t[j] - t[i]), 2), rj, int(round(max(0.0, drop))), int((step > TELE).any())] +
                                             [int(round(x)) for x in np.concatenate(pieces).ravel()])


def trip_points(row):
    """a trip's row (seconds, rocket jump, fall, teleporter, then its path every WAY_STEP units) -> its path, (k, 3)"""
    return np.asarray(row[4:], np.float64).reshape(-1, 3)


def way_labels(trips):
    """the trips of one pair -> for each the number of its way, and their paths as TRIP_PTS points. A trip joins the way
    whose first trip lies nearest, within WAY_D units on average along the path, else it opens a new way; then every
    trip goes to the nearest way once more."""
    P = np.stack([_resample(trip_points(r)) for r in trips])
    lead = [0]
    for i in range(1, len(P)):
        d = np.linalg.norm(P[lead] - P[i], axis=2).mean(1)
        if d.min() > WAY_D:
            lead.append(i)
    lab = np.zeros(len(P), np.int64)
    for a in range(0, len(P), 2000):
        lab[a:a + 2000] = np.linalg.norm(P[a:a + 2000, None] - P[lead][None], axis=3).mean(2).argmin(1)
    return lab, P


def pro_ways(T, mp, info):
    """the ways of a map as routes (sim/pro_ways/<map>.json): for every ordered pair of big items with WAY_MIN_TRIPS trips
    or more its ways with WAY_KEEP_SHARE of the trips or more, the commonest first, WAY_KEEP at most; a way is given by
    the trip that lies nearest to the mean of its trips"""
    pairs = []
    for k, tr in sorted(T["trips"].items()):
        if not k.startswith(mp + ":") or len(tr) < WAY_MIN_TRIPS:
            continue
        lab, P = way_labels(tr)
        n = np.bincount(lab)
        ways_ = []
        for c in np.argsort(-n)[:WAY_KEEP]:
            if n[c] < WAY_KEEP_SHARE * len(tr):
                break
            m = np.nonzero(lab == c)[0]
            rows = [tr[i] for i in m]
            best = m[int(np.linalg.norm(P[m] - P[m].mean(0), axis=2).mean(1).argmin())]
            pts = trip_points(tr[best])
            rj = float(np.mean([r[1] for r in rows]))
            hop = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            ways_.append(dict(share=round(100.0 * n[c] / len(tr), 1), trips=int(n[c]), seconds_median=_med([r[0] for r in rows]),
                              seconds_typical=tr[best][0], length_units=int(round(float(hop[hop <= TELE].sum()))),
                              teleporter_after_point=[int(q) for q in np.nonzero(hop > TELE)[0]],
                              rocket_jump=bool(rj >= 0.5), rocket_jump_share=round(100.0 * rj, 1),
                              fall=bool(np.median([r[2] for r in rows]) >= DROP), fall_units_median=int(np.median([r[2] for r in rows])),
                              teleporter=bool(np.mean([r[3] for r in rows]) >= 0.5), points=[[int(x) for x in q] for q in pts]))
        if ways_:
            a, b = k.split(":")[1].split(">")
            pairs.append({"from": a, "to": b, "trips": len(tr), "seconds_median": _med([r[0] for r in tr]),
                          "trips_on_these_ways_share": round(sum(w_["share"] for w_ in ways_), 1), "ways": ways_})
    return dict(map=mp, step_units=WAY_STEP, same_way_within_units=WAY_D, min_trips=WAY_MIN_TRIPS, min_share=WAY_KEEP_SHARE,
                rocket_jump="his upward speed rises by {:.0f} or more within 0.25 s of a rocket of his, on half the way's trips or more".format(RJ_UP),
                fall="{:.0f} units or more down between leaving the ground and landing (the median of the way's trips)".format(DROP),
                items={b_["label"]: [int(round(float(x))) for x in b_["pos"]] for b_ in info["big"]}, pairs=pairs)


def ways(trips):
    """the trips of one pair -> the number of trips on each of their ways, the most used first (see way_labels)"""
    return sorted(np.bincount(way_labels(trips)[0]).tolist(), reverse=True)


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
    out["walking"] = walking(T)
    out["spam_when"] = spam_when(T)
    out["hit_combinations"] = hit_combinations(T)
    out["looking"] = looking_report(T)
    out["holds"] = holds_report(T)
    out["hands"] = hands_report(T)
    out["fight_movement"] = fight_report(T)
    out["fights"] = fights_report(T)
    out["flick_curve"] = flick_report(T)
    out["view_travelling"] = tview_report(T)
    return out


def _fight_cell(Fx, grp, prefix):
    """the three choices of one situation -> its numbers"""
    cs = [Fx[grp].get("{}:{}".format(prefix, c)) for c in range(3)]
    tot = sum(c["n"] for c in cs if c)
    if not tot:
        return dict(sightings=0)
    out = dict(sightings=tot)
    for c, nm in zip(cs, ("takes", "refuses", "neither")):
        out[nm + "_share"] = _share(c["n"] if c else 0, tot)
    t_, r_ = (cs[0]["n"] if cs[0] else 0), (cs[1]["n"] if cs[1] else 0)
    out["index"] = round(100.0 * t_ / (t_ + r_), 1) if t_ + r_ else None
    out["commits_share"] = _share(cs[0]["stay"] if cs[0] else 0, tot)        # takes it and is still in it after the 3 s
    out["fires_and_leaves_share"] = _share((cs[0]["n"] - cs[0]["stay"]) if cs[0] else 0, tot)
    for c, nm in zip(cs, ("when_taken", "when_refused", "when_neither")):
        if c and c["n"]:
            out[nm] = dict(sightings=c["n"], damage_dealt_less_taken_in_10s=round((c["dealt10"] - c["taken10"]) / c["k10"], 1) if c["k10"] else None,
                           damage_taken_in_10s=round(c["taken10"] / c["k10"], 1) if c["k10"] else None,
                           frag_for_him_share=_share(c["ffor"], c["n"]), frag_of_him_share=_share(c["fof"], c["n"]),
                           frags_for_less_of_him=round((c["ffor"] - c["fof"]) / c["n"], 3), big_item_for_him_share=_share(c["ihim"], c["n"]),
                           big_item_enemy_seen_share=_share(c["ien"], c["n"]))
    a, b = out.get("when_taken"), out.get("when_refused")
    out["taking_pays"] = round(a["frags_for_less_of_him"] - b["frags_for_less_of_him"], 3) if a and b else None
    return out


def fights_report(T):
    """fights taken and refused from a tally: all, by every side of the situation, by the pairs counted; and how good the
    guess of the enemy's stack is where the demo shows the truth (a cut to the other player)"""
    Fx = T["fights"]
    out = dict(all=_fight_cell(Fx, "one", "all:0"), by={}, pairs={})
    for fi, (fname, levels) in enumerate(FIGHT_FACTORS):
        out["by"][fname] = {levels[lv]: _fight_cell(Fx, "one", "{}:{}".format(fi, lv)) for lv in range(len(levels)) if any("{}:{}:{}".format(fi, lv, c) in Fx["one"] for c in range(3))}
    for a, b in FIGHT_PAIRS:
        tab = {}
        for la in range(len(FIGHT_FACTORS[a][1])):
            for lb in range(len(FIGHT_FACTORS[b][1])):
                c = _fight_cell(Fx, "two", "{},{}:{},{}".format(a, b, la, lb))
                if c["sightings"]:
                    tab["{}; {}".format(FIGHT_FACTORS[a][1][la], FIGHT_FACTORS[b][1][lb])] = c
        out["pairs"]["{} x {}".format(FIGHT_FACTORS[a][0], FIGHT_FACTORS[b][0])] = tab
    ec = np.array(T["est_check"], np.float64).reshape(-1, 3)
    if len(ec) >= 20:
        band = lambda x: np.where(x < 60, 0, np.where(x <= 125, 1, 2))
        be, bp, bt = band(ec[:, 0]), band(ec[:, 1]), band(ec[:, 2])
        out["enemy_stack_guess_check"] = dict(
            cuts=len(ec), guess_off_by_median=round(float(np.median(np.abs(ec[:, 0] - ec[:, 2]))), 1), table_alone_off_by_median=round(float(np.median(np.abs(ec[:, 1] - ec[:, 2]))), 1),
            guess_in_the_right_band_share=_share(int((be == bt).sum()), len(ec)), table_alone_in_the_right_band_share=_share(int((bp == bt).sum()), len(ec)),
            correlation=round(float(np.corrcoef(ec[:, 0], ec[:, 2])[0, 1]), 3),
            guessed_band_by_true_band={STACK_BANDS[q]: {STACK_BANDS[r]: _share(int(((bt == q) & (be == r)).sum()), int((bt == q).sum())) for r in range(3)} for q in range(3)})
    return out


def fight_model(rows, commit=False):
    """the calibrated aggression index: a logistic fit of "takes it" against "refuses it" on the sides of the situation
    (rows of FIGHT_COLS; the sightings that end in neither are left out). index(situation) = 1 / (1 + exp(-(intercept +
    the sum of its levels' effects))): the share of such offers the pros take among those they take or refuse.
    commit=True: "takes it and is still in it after the 3 s" against every other offer."""
    rows = np.asarray(rows, np.int64)
    if commit:
        y = (rows[:, 25] == 1).astype(np.float64)
    else:
        rows = rows[rows[:, 13] < 2]
        y = (rows[:, 13] == 0).astype(np.float64)
    cols, names = [np.ones(len(rows))], [("intercept", "")]
    for fi, (fname, levels) in enumerate(FIGHT_FACTORS):
        for lv in range(1, len(levels)):
            cols.append((rows[:, 3 + fi] == lv).astype(np.float64))
            names.append((fname, levels[lv]))
    X = np.stack(cols, 1)
    b = np.zeros(X.shape[1])
    for _ in range(25):
        pr_ = 1.0 / (1.0 + np.exp(-(X @ b)))
        W = pr_ * (1.0 - pr_) + 1e-9
        H = X.T @ (X * W[:, None]) + 1e-3 * np.eye(X.shape[1])
        b = b + np.linalg.solve(H, X.T @ (y - pr_) - 1e-3 * b)
    pr_ = np.clip(1.0 / (1.0 + np.exp(-(X @ b))), 1e-9, 1 - 1e-9)
    base = float(y.mean())
    ll = float(-(y * np.log(pr_) + (1 - y) * np.log(1 - pr_)).mean())
    ll0 = float(-(base * np.log(base) + (1 - base) * np.log(1 - base)))
    eff = {}
    for (fname, lvl), v in zip(names[1:], b[1:]):
        eff.setdefault(fname, {FIGHT_FACTORS[[f for f, _ in FIGHT_FACTORS].index(fname)][1][0]: 0.0})[lvl] = round(float(v), 3)
    return dict(sightings=int(len(rows)), takes_share=round(100.0 * base, 1), intercept=round(float(b[0]), 3), effects=eff,
                log_loss=round(ll, 4), log_loss_of_the_plain_share=round(ll0, 4),
                says="index = 1 / (1 + exp(-(intercept + the effects of the situation's levels))); the first level of every side is 0")


def fight_index(model, levels):
    """the index of one situation: `levels` {side's name: level's name} (a side left out counts as its first level)"""
    z = model["intercept"] + sum(model["effects"].get(k, {}).get(v, 0.0) for k, v in levels.items())
    return 1.0 / (1.0 + np.exp(-z))


def flick_report(T):
    Fc = T["flickc"]

    def cell(C):
        if not C or not C["n"]:
            return dict(appearances=0)
        ns, nh = sum(C["shot"].values()), sum(C["hit"].values())
        return dict(appearances=C["n"], a_shot_within_3s_share=_share(ns, C["n"]), seconds_to_the_first_shot_median=_hq(C["shot"], 50, 0.05),
                    seconds_to_the_first_shot_25=_hq(C["shot"], 25, 0.05), a_hit_within_3s_share=_share(nh, C["n"]),
                    seconds_to_the_first_hit_median=_hq(C["hit"], 50, 0.05), seconds_to_the_first_hit_25=_hq(C["hit"], 25, 0.05),
                    hits_of_the_first_half_second_of_fire_share=_share(C["h05"], C["s05"]), shots_in_it=C["s05"])
    return dict(by_angle={ERR_BANDS[e]: cell(Fc.get("e{}".format(e))) for e in range(len(ERR_BANDS))},
                by_weapon={FLICK_W[w_]: cell(Fc.get("w{}".format(w_))) for w_ in range(4)},
                by_angle_and_weapon={FLICK_W[w_]: {ERR_BANDS[e]: cell(Fc.get("e{}:w{}".format(e, w_))) for e in range(len(ERR_BANDS))} for w_ in range(3)},
                by_angle_and_distance={DIST_BANDS[d]: {ERR_BANDS[e]: cell(Fc.get("e{}:d{}".format(e, d))) for e in range(len(ERR_BANDS))} for d in range(3)})


def tview_report(T):
    V = T["tview"]
    out = dict(view_off_his_direction_of_travel=dict(median=_hq(V["move"], 50, 10.0), p75=_hq(V["move"], 75, 10.0), within_20_share=_hunder(V["move"], 20, 10.0),
                                                     within_40_share=_hunder(V["move"], 40, 10.0), over_90_share=round(100.0 - (_hunder(V["move"], 90, 10.0) or 0.0), 1) if V["move"] else None))
    for name, lbl in (("fast", "travelling at 350 or more, no enemy in view"), ("nv", "all his time with no enemy in view")):
        c = V[name]
        out[lbl] = dict(minutes=round(c["time"] / 60.0, 1), view_within_20_of_his_direction_of_travel_share=_share(c["along"], c["time"]),
                        view_within_20_of_where_he_last_saw_him_share=_share(c["at_last"], c["ever"]),
                        view_at_one_of_the_maps_places_share=_share(c["at_place"], c["sample"]),
                        view_at_the_doorway_the_enemy_would_come_through_share=_share(c["at_door"], c["door"]),
                        a_doorway_found_share_of_the_samples=_share(c["door"], c["sample"]))
    return out


LAGS = (("0", "as he comes into view"), ("25", "0.25 s before"), ("50", "0.5 s before"))


def looking_report(T):
    L = T["look"]

    def stats(lag, ub=None, hb=None):
        h, v, n = {}, {}, 0
        for k, S in L["sight"].items():
            a, b, c = k.split("|")
            if a == lag and (ub is None or int(b) == ub) and (hb is None or int(c) == hb):
                n += S["n"]
                for dst, src in ((h, S["h"]), (v, S["v"])):
                    for q, x in src.items():
                        dst[q] = dst.get(q, 0) + x
        return dict(sightings=n, sideways_median=_hq(h, 50, 1.0), sideways_25=_hq(h, 25, 1.0), sideways_75=_hq(h, 75, 1.0),
                    sideways_under_10_share=_hunder(h, 10, 1.0), sideways_under_20_share=_hunder(h, 20, 1.0),
                    up_down_median=_hq(v, 50, 1.0), up_down_75=_hq(v, 75, 1.0), up_down_under_10_share=_hunder(v, 10, 1.0)) if n else dict(sightings=0)
    return dict(
        no_enemy_in_view=dict(view_within_20_of_the_enemy_share=_share(L["at_enemy"], L["known"]), enemy_place_known_share_of_that_time=_share(L["known"], L["nv"]),
                              view_within_20_of_where_he_last_saw_him_share=_share(L["at_last"], L["ever"]),
                              view_within_20_of_the_nearest_mega_or_armor_share=_share(L["at_item"], L["item"])),
        at_a_sighting={lbl: stats(lag) for lag, lbl in LAGS},
        by_time_unseen={UNSEEN_BANDS[b]: {lbl: stats(lag, ub=b) for lag, lbl in LAGS} for b in range(3)},
        by_sound={HEARD_BANDS[b]: {lbl: stats(lag, hb=b) for lag, lbl in LAGS} for b in range(3) if any(k.endswith("|" + str(b)) for k in L["sight"])})


def holds_report(T):
    Hd = T["holds"]
    n, m10 = Hd["n"], Hd["alive"] / 600.0
    if not m10:
        return dict(known=False)
    cells = {}
    for k, c in Hd["cells"].items():
        mp, cx, cy, cz, lab, un = k.split(":")
        cells.setdefault(mp, []).append(dict(cell=[int(cx), int(cy), int(cz)], middle=[int((int(cx) + 0.5) * 256), int((int(cy) + 0.5) * 256), int((int(cz) + 0.5) * 128)],
                                             near=lab, near_units=int(un), holds=c["n"], weapons={w_: c[w_] for w_ in ("rl", "lg", "rg") if c.get(w_)}))
    top = {}
    for mp, cs in cells.items():
        tot = sum(c["holds"] for c in cs)
        top[mp] = [dict(c, share=round(100.0 * c["holds"] / tot, 1)) for c in sorted(cs, key=lambda c: -c["holds"])[:10]]
    return dict(known=True, holds=n, a_ten_minutes=round(n / m10, 2), share_of_his_time_alive=_share(Hd["time"], Hd["alive"]),
                seconds_median=_med(Hd["dur"]), seconds_75=_med(Hd["dur"], 75), seconds_90=_med(Hd["dur"], 90),
                weapon_in_hand={W_NAMES[w_]: _share(Hd["w"].get(w_, 0), n) for w_ in ("rl", "lg", "rg")},
                enemy_in_view_within_3s_of_its_end_share=_share(Hd["seen3"], n), ended_by_the_enemy_coming_into_view_share=_share(Hd["ended_by_view"], n),
                he_deals_damage_first_within_5s_share=_share(Hd["dealt_first"], n), he_takes_damage_first_within_5s_share=_share(Hd["took_first"], n),
                a_frag_for_him_within_5s_share=_share(Hd["frag5"], n), a_frag_of_him_within_5s_share=_share(Hd["died5"], n),
                view_at_a_big_item_share=_share(Hd["look_item"], Hd["look_time"]), view_at_a_teleporter_exit_share=_share(Hd["look_exit"], Hd["look_time"]),
                blind_rockets_and_grenades_from_holds_a_ten_minutes=round(Hd["trap_shots"] / m10, 2), traps_a_ten_minutes=round(Hd["traps"] / m10, 3),
                trap_shots_that_hit_share=_share(Hd["traps"], Hd["trap_shots"]), holds_with_a_trap_share=_share(Hd["with_trap"], n),
                traps_with_a_frag_within_2s_share=_share(Hd["trap_frags"], Hd["with_trap"]), top_cells=top)


def hands_report(T):
    Hn = T["hands"]
    out = dict(turn_speed={}, flick={}, accuracy={}, lightning_by_crossing_speed={}, lightning_tracking={})
    for name, lbl in (("travel", "no enemy in view"), ("fight", "enemy in view")):
        h = Hn["turn"][name]
        out["turn_speed"][lbl] = dict(median=_hq(h, 50, 10.0), p75=_hq(h, 75, 10.0), p90=_hq(h, 90, 10.0), p99=_hq(h, 99, 10.0),
                                      under_30_share=_hunder(h, 30, 10.0), under_100_share=_hunder(h, 100, 10.0), under_300_share=_hunder(h, 300, 10.0))
    F = Hn["flick"]
    if F["n"]:
        ns, nh = sum(F["shot"].values()), sum(F["hit"].values())
        out["flick"] = dict(sightings=F["n"], off_target_at_the_sighting_median=_hq(F["err0"], 50, 1.0), off_target_0_3s_later_median=_hq(F["err3"], 50, 1.0),
                            turn_in_0_3s_median=_hq(F["size"], 50, 1.0), turn_in_0_3s_75=_hq(F["size"], 75, 1.0), turn_in_0_3s_90=_hq(F["size"], 90, 1.0),
                            peak_speed_median=_hq(F["peak"], 50, 20.0), peak_speed_90=_hq(F["peak"], 90, 20.0), seconds_to_the_peak_median=_hq(F["t_peak"], 50, 0.025),
                            a_shot_within_3s_share=_share(ns, ns + F["shot_none"]), seconds_to_the_first_shot_median=_hq(F["shot"], 50, 0.05),
                            seconds_to_the_first_shot_25=_hq(F["shot"], 25, 0.05),
                            a_hit_within_3s_share=_share(nh, nh + F["hit_none"]), seconds_to_the_first_hit_median=_hq(F["hit"], 50, 0.05),
                            seconds_to_the_first_hit_25=_hq(F["hit"], 25, 0.05))
    for wn, A in Hn["acc"].items():
        row = {}
        tot = dict(shots=0, hits=0, direct=0)
        for b in range(len(ACC_BANDS)):
            c = A.get(str(b))
            if c:
                row[ACC_BANDS[b]] = dict(shots=c["shots"], hit_share=_share(c["hits"], c["shots"]), **({"direct_share": _share(c["direct"], c["shots"])} if wn == "rl" else {}))
                for k in tot:
                    tot[k] += c[k]
        row["all"] = dict(shots=tot["shots"], hit_share=_share(tot["hits"], tot["shots"]), **({"direct_share": _share(tot["direct"], tot["shots"])} if wn == "rl" else {}))
        out["accuracy"][W_NAMES.get(wn, wn)] = row
    out["lightning_by_crossing_speed"] = {CROSS_BANDS[int(b)]: dict(shots=c["shots"], hit_share=_share(c["hits"], c["shots"])) for b, c in sorted(Hn["lg_cross"].items())}
    tr = Hn["lg_track"]
    out["lightning_tracking"] = dict(seconds=round(tr["time"], 1), turning_direction_changes_a_second=round(tr["reversals"] / tr["time"], 2) if tr["time"] else None)
    return out


def fight_report(T):
    Fg = T["fight"]
    out = dict(by={}, after_a_big_hit={})
    for name, c in Fg["by"].items():
        if c["time"] <= 0:
            continue
        out["by"][name] = dict(minutes=round(c["time"] / 60.0, 1), strafe_changes_a_second=round(c["flips"] / c["time"], 2),
                               in_the_air_share=_share(c["air"], c["ground_known"]), crouched_share=_share(c["crouch"], c["time"], 2),
                               jumps_a_minute=round(c["jumps"] / c["time"] * 60.0, 1) if c["ground_known"] else None, speed=round(c["speed"] / c["time"], 1),
                               distance_change_a_second=round(c["ddist"] / c["ddist_time"], 1) if c["ddist_time"] else None)

    def merged(seen=None, sb=None):
        tot = {}
        for k, c in Fg["hit50"].items():
            a, b = (int(x) for x in k.split("|"))
            if (seen is None or a == seen) and (sb is None or b == sb):
                for q, v in c.items():
                    tot[q] = tot.get(q, 0) + v
        if not tot.get("n"):
            return dict(hits=0)
        return dict(hits=tot["n"], died_within_2s_share=_share(tot["died"], tot["n"]), weapon_change_share=_share(tot["wchange"], tot["alive2"]),
                    distance_change_mean=round(tot["ddist"] / tot["known"], 1) if tot["known"] else None, farther_by_100_share=_share(tot["away"], tot["known"]),
                    nearer_by_100_share=_share(tot["closer"], tot["known"]), **({"lost_view_share": _share(tot["lost"], tot["alive2"])} if seen == 1 else {}))
    out["after_a_big_hit"] = {"all": merged(), "enemy in view at the hit": merged(seen=1), "enemy not in view at the hit": merged(seen=0),
                              **{"enemy in view, " + STACK_BANDS[b] + " after it": merged(seen=1, sb=b) for b in range(3)}}
    return out


def walk_band(steady):
    """the walking speed from the time by steady speed on the ground: the fullest 10-unit bin from 100 to 260 units a
    second, if it stands clear of the bins 30 units to either side (twice their mean); else none"""
    h = np.array([steady.get(str(k), 0.0) for k in range(QUIET_BINS)])
    k = 10 + int(np.argmax(h[10:26]))
    side = np.mean([h[k - 3], h[k + 3]])
    clear = bool(h[k] > 0 and h[k] >= 2.0 * side)
    return k, clear, h


def walking(T):
    """walking and quiet from a tally: the speed histograms, the walking band found in them, and the shares of his time
    alive that he walks, moves crouched or stands, in all and by situation"""
    Q = T["quiet"]
    if not Q["by"]:
        return dict(known=False)
    k, clear, h = walk_band(Q["steady"])
    lo, hi = (k - 1, k + 1) if clear else (15, 17)                # (no clear peak: Quake's half speed, 160, to have a number)
    ground = np.array([Q["ground"].get(str(q), 0.0) for q in range(QUIET_BINS)])
    crouch = np.array([Q["crouch"].get(str(q), 0.0) for q in range(QUIET_BINS)])
    out = dict(known=True, walking_speed=[QUIET_BIN * k, QUIET_BIN * (k + 1)] if clear else None, clear_peak=clear,
               band=[QUIET_BIN * lo, QUIET_BIN * (hi + 1)], peak_over_its_sides=round(float(h[k] / max(1e-9, np.mean([h[k - 3], h[k + 3]]))), 2),
               ground_time_by_speed_share=[round(100.0 * float(x) / max(1e-9, ground.sum()), 2) for x in ground],
               steady_ground_time_by_speed_share=[round(100.0 * float(x) / max(1e-9, ground.sum()), 2) for x in h],
               crouched_ground_time_by_speed_share=[round(100.0 * float(x) / max(1e-9, ground.sum()), 2) for x in crouch], by={})
    for name, c in Q["by"].items():
        st = np.array([c["steady"].get(str(q), 0.0) for q in range(QUIET_BINS)])
        wk = float(st[lo:hi + 1].sum())
        out["by"][name] = dict(minutes=round(c["alive"] / 60.0, 1), walking_share=_share(wk, c["alive"], 2), crouched_moving_share=_share(c["crouch_move"], c["alive"], 2),
                               standing_share=_share(c["stand"], c["alive"], 2), quiet_share=_share(wk + c["crouch_move"] + c["stand"], c["alive"], 2),
                               in_the_air_share=_share(c["air"], c["alive"], 1))
    return out


def spam_when(T):
    """when and at what the blind shots that land away from himself go, a weapon"""
    out = {}
    B = T["when_base"]
    for wn in ("rl", "gl", "pg"):
        W = T["when"][wn]
        n = W["n"]
        out[wn] = dict(shots=n, since_last_seen={SINCE_BANDS[q]: _share(W["since"].get(str(q), 0), n) for q in range(len(SINCE_BANDS))},
                       landing={ITEM_CATS[q]: _share(W["item"].get(str(q), 0), n) for q in range(len(ITEM_CATS))},
                       hurt_in_the_5s_before_share=_share(W["hurt"], n), hurt_badly_share=_share(W["hurt_bad"], n),
                       within_10s_of_his_death_share=_share(W["after_death"], n))
    out["of_all_his_time_alive"] = dict(hurt_in_the_5s_before_share=_share(B["hurt"], B["alive"]), hurt_badly_share=_share(B["hurt_bad"], B["alive"]),
                                        within_10s_of_his_death_share=_share(B["after_death"], B["alive"]))
    return out


def hit_combinations(T):
    H = T["hitcombo"]
    m10 = H["known"] / 600.0
    if not m10:
        return dict(known=False)
    per = lambda x: round(x / m10, 3)
    return dict(known=True, rocket_hits_a_ten_minutes=per(H["rl_hits"]), rocket_hit_share=_share(H["rl_hits"], H["rl_shots"]),
                grenade_hits_a_ten_minutes=per(H["gl_hits"]), grenade_hit_share=_share(H["gl_hits"], H["gl_shots"]),
                rocket_hit_then_lightning_or_rail_hit_a_ten_minutes=per(H["rl_lg"] + H["rl_rg"]), rocket_then_rail_share=_share(H["rl_rg"], H["rl_lg"] + H["rl_rg"]),
                grenade_hit_then_lightning_or_rail_hit_a_ten_minutes=per(H["gl_lg"] + H["gl_rg"]),
                rocket_hit_then_rocket_hit_a_ten_minutes=per(H["juggle"]),
                frags=H["frags"], frags_after_a_pair_share=_share(H["frags_combo"], H["frags"]), frags_after_a_juggle_share=_share(H["frags_juggle"], H["frags"]),
                rocket_hits_followed_by_a_beam_hit_share=_share(H["rl_lg"] + H["rl_rg"], H["rl_hits"]))


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
                                              seconds_median=_med([r[0] for r in tr]))
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
                            col=sort if wname is None else WEAPONS.index(wname), back=RETURN.get(ITEM_KIND.get(cls), 5.0)))
    exits = [[float(x) for x in d] for cls_, _, d in getattr(world, "triggers", []) if cls_ == "trigger_teleport"]
    info = dict(name=name, items=out, big=big, exits=exits, places=[], cellv={}, nav_nodes=None, nav_hop=None)
    f = os.path.join(ROOT, "sim", "pro_places", name + ".json")
    if os.path.exists(f):
        info["places"] = [pl["pos"] for pl in json.load(open(f)).get("places", [])]
    f = os.path.join(ROOT, "sim", "pro_places", name + "_cells.json")
    if os.path.exists(f):
        info["cellv"] = {tuple(c["cell"]): c["outcome_over_expected"] for c in json.load(open(f))["cells"] if c.get("outcome_over_expected") is not None}
    nh = nav_hops(name)
    if nh is not None:
        info["nav_nodes"], info["nav_hop"] = nh
    return info


def nav_hops(name):
    """the walking map of a map (data/maps/nav_<map>_sim.json) and for every pair of its spots the next spot on the
    quickest way from the one to the other (kept in the demo root: it takes a minute to work out)"""
    src = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(name))
    if not os.path.exists(src):
        return None
    keep = os.path.join(demo_root(), "yardsticks", "navhop_{}.npz".format(name))
    if os.path.exists(keep) and os.path.getmtime(keep) >= os.path.getmtime(src):
        z = np.load(keep)
        return z["nodes"], z["hop"]
    nav = json.load(open(src))
    nodes = np.array(nav["nodes"], np.float64).reshape(-1, 3)
    n = len(nodes)
    D = np.full((n, n), np.inf, np.float32)
    hop = np.full((n, n), -1, np.int16)
    for e in nav["edges"]:
        a, b, c = int(e[0]), int(e[1]), float(e[2])
        if c < D[a, b]:
            D[a, b], hop[a, b] = c, b
    D[np.arange(n), np.arange(n)] = 0.0
    hop[np.arange(n), np.arange(n)] = np.arange(n)
    for k in range(n):
        alt = D[:, k:k + 1] + D[k:k + 1, :]
        better = alt < D
        D = np.where(better, alt, D)
        hop = np.where(better, hop[:, k:k + 1], hop)
    os.makedirs(os.path.dirname(keep), exist_ok=True)
    np.savez_compressed(keep, nodes=nodes, hop=hop)
    return nodes, hop


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


def demo_record(binf, meta, E=None):
    """one parsed demo -> (record of its game, facts about the reading) or (None, facts). E: the parser's events file
    (tools/demodump/events_reader.py): every death with killer and victim, the level's start time as the server sets
    it (timeouts in it), the enemy's pickups while the server sends him"""
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
    eev = np.full(N, -1, np.int64)                              # the enemy entity's event field, -1 where he is not sent
    if len(pl):
        m = (pl[:, 0] < 64) & (pl[:, 0] != cn[snap]) & ((pl[:, 12].astype(np.int64) & 1) == 0)
        s_, first = np.unique(snap[m], return_index=True)
        rows = pl[m][first]
        enemy[s_] = rows[:, 2:5]
        air[s_] = (rows[:, 13] == 1023).astype(np.int64)
        eweap[s_] = [WEAPONS.index(QLW[int(x)]) if int(x) in QLW else -1 for x in rows[:, 11]]
        eev[s_] = rows[:, 14].astype(np.int64)
    # a new event of his: the field changes (its two sequence bits count) between two snapshots he is in. Quake Live's
    # numbers: 10 a jump, 9 a jump pad, 20 a shot, 15 and 16 an item picked up
    esound = np.zeros(N, np.int64)
    new_ev = np.zeros(N, bool)
    new_ev[1:] = (eev[1:] >= 0) & (eev[:-1] >= 0) & (eev[1:] != eev[:-1]) & ((eev[1:] & 0xFF) != 0)
    kind = eev & 0xFF
    esound[new_ev & np.isin(kind, (9, 10))] |= 1
    esound[new_ev & (kind == 20)] |= 2
    esound[new_ev & np.isin(kind, (15, 16))] |= 4
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
                      enemy_weapon=eweap[keep], ground=ps[keep, PS["groundEntityNum"]] != 1023, enemy_sound=esound[keep],
                      **events_fields(E, tm, cn, keep, remap, start, end, t0))
    info["events"] = E is not None
    info.update(recorder=int((meta.get("gamestates") or [{}])[0].get("client_num", -1)), cuts=int((np.diff(cn[keep]) != 0).sum()),
                final={int(c): int(v) for c, v in last.items()}, final_enemy=int(e), final_client=int(cn[keep[-1]]),
                step_ms=int(np.median(dt)))
    return rec, info


def events_fields(E, tm, cn, keep, remap, start, end, t0):
    """what the parser's events file adds to a record: `obits`, `enemy_life`, `clock_exact`, `enemy_pick` (make_record)"""
    if E is None or len(E["times"]) != len(tm):
        return {}
    import events_reader as R
    N = len(tm)
    ob = R.obituaries(E)                                        # snap, server time, victim, killer, means
    ob = ob[(ob[:, 0] >= start) & (ob[:, 0] < min(end + 200, N))]
    obits = [[tm[s_] / 1000.0, v, k] for s_, _, v, k, _ in ob]
    # the level's start time as the server sets it: at the game's restart, and again when a timeout ends; while a
    # timeout runs the clock stands
    lst = np.full(N, np.nan)
    cid = E["config_string_ids"]
    evs = [(a, 0, x) for a, x in R.config_string(E, "LevelStartTime")] + [(a, 1, x) for a, x in R.config_string(E, "PauseStart")]
    evs.sort(key=lambda x: x[0])
    cur, pause = np.nan, None
    marks = []
    for a, kind, x in evs:
        try:
            v = float(x)
        except (TypeError, ValueError):
            v = 0.0
        if kind == 0:
            cur, pause = v, None
        else:
            pause = v if v > 0 else None
        marks.append((int(a), cur, pause))
    times = E["times"].astype(np.float64)
    clock = np.full(N, np.nan)
    for q, (a, cur, pause) in enumerate(marks):
        b = marks[q + 1][0] if q + 1 < len(marks) else N
        if b > a and np.isfinite(cur) and cur > 0:
            seg_t = times[a:b] if pause is None else np.minimum(times[a:b], pause)
            clock[a:b] = (seg_t - cur) / 1000.0
    clock[:start] = np.nan
    # the seconds since the enemy last died (or since the game began)
    life = np.full(N, 999.0)
    begin = t0 if t0 is not None else float(tm[start])
    for c in np.unique(cn[keep]):
        dts = np.sort(np.array([tm[s_] for s_, _, v, _, _ in ob if v != c], np.float64))
        m = cn == c
        if len(dts):
            j = np.searchsorted(dts, tm[m], side="right") - 1
            life[m] = np.where(j >= 0, (tm[m] - dts[np.maximum(j, 0)]) / 1000.0, (tm[m] - begin) / 1000.0)
        else:
            life[m] = (tm[m] - begin) / 1000.0
    # the enemy's pickups, seen or heard: an item-pickup event on his entity while the server sends him
    give = {"ItemHealthMega": (100, 1, 1), "ItemArmorBody": (100, 1, 0), "ItemArmorCombat": (50, 1, 0), "ItemArmorJacket": (25, 0, 0),
            "ItemArmorShard": (5, 0, 0), "ItemHealth": (25, 0, 1), "ItemHealthLarge": (50, 0, 1), "ItemHealthSmall": (5, 0, 1)}
    by_id = {E["item_ids"][k]: v for k, v in give.items() if k in E["item_ids"]}
    c_ = E["c"]
    picks = []
    for r in R.rows(E, "ItemPickup", source=1, etype="Player"):
        s_, num, item = int(r[c_["snap"]]), int(r[c_["number"]]), int(r[c_["eventParm"]])
        if 0 <= s_ < N and remap[s_] >= 0 and num != cn[s_] and num < 64 and item in by_id:
            picks.append([int(remap[s_]), *by_id[item]])
    return dict(obits=obits, enemy_life=life[keep], clock_exact=np.where(np.isfinite(clock[keep]), clock[keep], np.nan), enemy_pick=picks)


def parse(demo, tmp):
    """a demo file -> (record, facts)"""
    b, js, ev = os.path.join(tmp, "d.bin"), os.path.join(tmp, "d.json"), os.path.join(tmp, "d.events.json")
    for p in (b, js, ev):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run([EXE, demo, b, js, ev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not os.path.exists(js) or not os.path.exists(b):
        return None, dict(why="parser")
    meta = json.load(open(js, encoding="utf-8", errors="replace"))
    E = None
    if os.path.exists(ev):                                      # (the parser of 2026-10-11 on; without it the record has no deaths list)
        try:
            if os.path.join(HERE, "demodump") not in sys.path:
                sys.path.insert(0, os.path.join(HERE, "demodump"))
            import events_reader
            E = events_reader.load(ev)
        except Exception:                                      # noqa: BLE001
            E = None
    try:
        return demo_record(b, meta, E)
    finally:
        for p in (b, js, ev):                                   # (a parsed demo is 18 MB)
            if os.path.exists(p):
                os.remove(p)


_W = {}


def low_priority():
    """below normal, so that a training run on the same PC keeps its share"""
    try:
        import ctypes
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    except Exception:                                          # noqa: BLE001 (not Windows)
        pass


def _big():
    return [dict(label=b["label"], pos=[float(x) for x in b["pos"]]) for b in _W["info"]["big"]]


def _init(mp, tmp):
    low_priority()
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
    out_dir = os.path.join(demo_root(), "yardsticks", "sample", mp) if limit else os.path.join(demo_root(), "yardsticks", mp)
    os.makedirs(out_dir, exist_ok=True)
    jobs = [(f, os.path.join(out_dir, os.path.splitext(os.path.basename(f))[0] + ".json"), redo) for f in files]
    tmp = tempfile.mkdtemp(prefix="yard_")                       # the parsed demos of the moment, a folder a process
    try:
        if procs <= 1:
            _init(mp, tmp)
            res = [_one(j) for j in jobs]
            big = _big()
        else:
            with mp_.Pool(procs, initializer=_init, initargs=(mp, tmp)) as pool:
                res = pool.map(_one, jobs, chunksize=4)
                big = pool.apply(_big)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return files, res, big


ABOUT2 = ("fights", "flick_curve", "view_travelling")


def second_file(path):
    """docs/pro_yardsticks.json -> docs/pro_yardsticks2.json: where the groups of GROUPS2 are kept"""
    return path[:-5] + "2.json" if path.endswith(".json") else path + "2"


def load_both(path):
    """the yardsticks' json with the second file's groups put into its maps, if that file is there"""
    res = json.load(open(path, encoding="utf-8"))
    f2 = second_file(path)
    if os.path.exists(f2):
        r2 = json.load(open(f2, encoding="utf-8"))
        res.setdefault("about", {}).update(r2.get("about", {}))
        for m, v in r2.get("maps", {}).items():
            res["maps"].setdefault(m, {}).update({k: x for k, x in v.items() if k in GROUPS2})
    return res


def dump_json(obj, path, depth=4):
    """json with a line a key down to `depth` levels and whatever lies deeper on that line: readable in a diff, and well
    under half the size of a line a value"""
    def w(x, d, ind):
        if d >= depth or not isinstance(x, dict) or not x:
            return json.dumps(x)
        return "{\n" + ",\n".join(ind + " " + json.dumps(k) + ": " + w(v, d + 1, ind + " ") for k, v in x.items()) + "\n" + ind + "}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(w(obj, 0, "") + "\n")


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")
    return "\n".join(out)


def show(res):
    """the tables, markdown"""
    maps = [m for m in res["maps"] if m not in ("all", "all_ten")]
    cols = [m for m in ("all", "all_ten") if m in res["maps"]] + maps
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
        return g(P[m]) if m in ("all", "all_ten") else f(P[m]["maps"][m]) if m in P[m]["maps"] else None
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
    show_more(R, cols)
    show_fine(R, cols)
    show_fights(R, cols)


def show_more(R, cols):
    """the tables of walking, when they spam, combinations by hits"""
    print("### 9. Walking and quiet\n")
    Wk = {m: R[m]["walking"] for m in cols}
    if all(not v.get("known") for v in Wk.values()):
        print("(his feet on the ground are not in these records)\n")
    else:
        first = next(m for m in cols if Wk[m].get("known"))
        w0 = Wk[first]
        print("Time on the ground by speed ({}), % of all his time on the ground; steady = his speed changes by under {:g} a frame:\n".format(first, STEADY))
        idx = list(range(0, 36))
        print(table([["all", *[w0["ground_time_by_speed_share"][q] for q in idx]], ["steady, not crouched", *[w0["steady_ground_time_by_speed_share"][q] for q in idx]],
                     ["crouched", *[w0["crouched_ground_time_by_speed_share"][q] for q in idx]]], ["speed from", *[str(int(QUIET_BIN * q)) for q in idx]]))
        print("\n" + table([["a clear walking peak"] + [("yes" if Wk[m]["clear_peak"] else "no") if Wk[m].get("known") else None for m in cols],
                             ["walking speed found, from"] + [(Wk[m].get("walking_speed") or [None])[0] for m in cols],
                             ["the fullest bin from 100 to 260 over the bins 30 either side"] + [Wk[m].get("peak_over_its_sides") for m in cols]], ["", *cols]))
        names = list(w0["by"].keys())
        keys = (("minutes", "minutes"), ("walking_share", "walking, %"), ("crouched_moving_share", "crouched and moving, %"), ("standing_share", "standing, %"),
                ("quiet_share", "quiet in all, %"), ("in_the_air_share", "in the air, %"))
        print("\n" + table([[n] + [w0["by"][n][k] for k, _ in keys] for n in names], ["situation ({})".format(first)] + [lbl for _, lbl in keys]))
    print("\n### 10. When they spam: the blind shots that land away from himself ({})\n".format(cols[0]))
    S = R[cols[0]]["spam_when"]
    rows = [["shots"] + [S[w]["shots"] for w in ("rl", "gl", "pg")] + [None]]
    rows += [["enemy last in view: " + b + ", %"] + [S[w]["since_last_seen"][b] for w in ("rl", "gl", "pg")] + [None] for b in SINCE_BANDS]
    rows += [["lands within 300 units of: " + c + ", %"] + [S[w]["landing"][c] for w in ("rl", "gl", "pg")] + [None] for c in ITEM_CATS]
    for k, lbl in (("hurt_in_the_5s_before_share", "he lost 20 or more health and armor in the 5 s before, %"), ("hurt_badly_share", "50 or more, %"),
                   ("within_10s_of_his_death_share", "within 10 s of his own death, %")):
        rows.append([lbl] + [S[w][k] for w in ("rl", "gl", "pg")] + [S["of_all_his_time_alive"][k]])
    print(table(rows, ["", "rockets", "grenades", "plasma", "of all his time alive"]))
    print("\n### 11. Combinations by hits\n")
    keys = (("rocket_hits_a_ten_minutes", "rocket hits a ten minutes"), ("rocket_hit_share", "rockets that hit, %"),
            ("rocket_hit_then_lightning_or_rail_hit_a_ten_minutes", "rocket hit, then a lightning or rail hit within 1.5 s: a ten minutes"),
            ("rocket_hits_followed_by_a_beam_hit_share", "... % of his rocket hits"), ("rocket_then_rail_share", "... the second is the rail, %"),
            ("grenade_hit_then_lightning_or_rail_hit_a_ten_minutes", "grenade hit, then a lightning or rail hit within 1.5 s: a ten minutes"),
            ("rocket_hit_then_rocket_hit_a_ten_minutes", "rocket hit, then another rocket's hit within 1.2 s: a ten minutes"),
            ("frags_after_a_pair_share", "his frags within 2 s after such a pair (rocket or grenade, then beam), %"),
            ("frags_after_a_juggle_share", "his frags within 2 s after two rocket hits, %"))
    print(table([[lbl] + [R[m]["hit_combinations"].get(k) for m in cols] for k, lbl in keys], ["", *cols]))


def show_fine(R, cols):
    """the tables of where he looks, holds and traps, his hands, movement in a fight"""
    m0 = cols[0]
    Lk = R[m0]["looking"]
    print("\n### 12. Where he looks with no enemy in view ({})\n".format(m0))
    nv = Lk["no_enemy_in_view"]
    print(table([["of his time with no enemy in view: his view within 20 degrees of the enemy's true place (where the demo has it), %"] + [R[m]["looking"]["no_enemy_in_view"]["view_within_20_of_the_enemy_share"] for m in cols],
                 ["... the demo has the enemy's place for this much of that time, %"] + [R[m]["looking"]["no_enemy_in_view"]["enemy_place_known_share_of_that_time"] for m in cols],
                 ["... within 20 degrees of where he last saw him, %"] + [R[m]["looking"]["no_enemy_in_view"]["view_within_20_of_where_he_last_saw_him_share"] for m in cols],
                 ["... within 20 degrees of the nearest mega or armor, %"] + [R[m]["looking"]["no_enemy_in_view"]["view_within_20_of_the_nearest_mega_or_armor_share"] for m in cols]], ["", *cols]))
    keys = (("sightings", "sightings"), ("sideways_median", "sideways off: median"), ("sideways_25", "25th"), ("sideways_75", "75th"), ("sideways_under_10_share", "under 10 degrees, %"),
            ("sideways_under_20_share", "under 20, %"), ("up_down_median", "up-down off: median"), ("up_down_75", "75th"), ("up_down_under_10_share", "under 10, %"))
    rows = [["all sightings, " + lbl] + [Lk["at_a_sighting"][lbl].get(k) for k, _ in keys] for _, lbl in LAGS]
    for grp in ("by_time_unseen", "by_sound"):
        for band, v in Lk[grp].items():
            rows += [[band + ", " + lbl] + [v[lbl].get(k) for k, _ in keys] for _, lbl in LAGS]
    print("\n" + table(rows, ["the angle from his view to where the enemy appears"] + [lbl for _, lbl in keys]))
    print("\n### 13. Holds and traps\n")
    keys = (("a_ten_minutes", "holds a ten minutes"), ("share_of_his_time_alive", "% of his time alive"), ("seconds_median", "seconds: median"), ("seconds_90", "seconds: 90th percentile"),
            ("enemy_in_view_within_3s_of_its_end_share", "enemy in view within 3 s of its end, %"), ("ended_by_the_enemy_coming_into_view_share", "ended by the enemy coming into view, %"),
            ("he_deals_damage_first_within_5s_share", "he deals damage first within 5 s, %"), ("he_takes_damage_first_within_5s_share", "he takes damage first, %"),
            ("a_frag_for_him_within_5s_share", "a frag for him within 5 s, %"), ("a_frag_of_him_within_5s_share", "a frag of him, %"),
            ("view_at_a_big_item_share", "his view at a big item (20 degrees, a clear line), % of the hold"), ("view_at_a_teleporter_exit_share", "at a teleporter's exit, %"),
            ("blind_rockets_and_grenades_from_holds_a_ten_minutes", "blind rockets and grenades from holds a ten minutes"), ("traps_a_ten_minutes", "of them hit within 1.5 s (traps) a ten minutes"),
            ("trap_shots_that_hit_share", "... % of those shots"), ("holds_with_a_trap_share", "holds with a trap, %"))
    rows = [[lbl] + [R[m]["holds"].get(k) for m in cols] for k, lbl in keys]
    rows += [["in hand: " + w_ + ", %"] + [R[m]["holds"].get("weapon_in_hand", {}).get(w_) for m in cols] for w_ in ("rockets", "lightning", "rail")]
    print(table(rows, ["", *cols]))
    for m in [c for c in cols if c not in ("all", "all_ten")][:3]:
        tc = R[m]["holds"].get("top_cells", {}).get(m, [])
        print("\nThe cells of {} with the most holds: ".format(m) + "; ".join("{} units from {} at height {} {}% ({})".format(
            c["near_units"], c["near"], c["middle"][2], c["share"], ", ".join("{} {}".format(W_NAMES[k], v) for k, v in c["weapons"].items())) for c in tc[:5]))
    print("\n### 14. His hands ({})\n".format(m0))
    Hn = R[m0]["hands"]
    keys = (("median", "median"), ("p75", "75th"), ("p90", "90th"), ("p99", "99th"), ("under_30_share", "under 30, % of the time"), ("under_100_share", "under 100, %"), ("under_300_share", "under 300, %"))
    print(table([[n] + [v.get(k) for k, _ in keys] for n, v in Hn["turn_speed"].items()], ["turn speed of his view, degrees a second"] + [lbl for _, lbl in keys]))
    fl = (("off_target_at_the_sighting_median", "off target as the enemy comes into view, degrees, median"), ("off_target_0_3s_later_median", "off target 0.3 s later, median"),
          ("turn_in_0_3s_median", "his view's turn in those 0.3 s, degrees: median"), ("turn_in_0_3s_90", "90th percentile"), ("peak_speed_median", "peak turn speed in them, degrees a second: median"),
          ("peak_speed_90", "90th percentile"), ("seconds_to_the_peak_median", "seconds to the peak, median"), ("a_shot_within_3s_share", "a shot within 3 s, %"),
          ("seconds_to_the_first_shot_median", "seconds to the first shot, median"), ("a_hit_within_3s_share", "a hit within 3 s, %"), ("seconds_to_the_first_hit_median", "seconds to the first hit, median"))
    print("\n" + table([[lbl] + [R[m]["hands"]["flick"].get(k) for m in cols] for k, lbl in fl], ["the flick", *cols]))
    rows = []
    for wn, A in Hn["accuracy"].items():
        rows.append([wn + ": hits, % of its shots"] + [A.get(b, {}).get("hit_share") for b in ("all", *ACC_BANDS)])
        if wn == "rockets":
            rows.append(["rockets: direct hits, %"] + [A.get(b, {}).get("direct_share") for b in ("all", *ACC_BANDS)])
        rows.append([wn + ": shots"] + [A.get(b, {}).get("shots") for b in ("all", *ACC_BANDS)])
    print("\n" + table(rows, ["accuracy by the distance to the enemy", "all", *ACC_BANDS]))
    print("\n" + table([[b, v["shots"], v["hit_share"]] for b, v in Hn["lightning_by_crossing_speed"].items()] +
                        [["his view's changes of turning direction a second while tracking with lightning", None, Hn["lightning_tracking"].get("turning_direction_changes_a_second")]],
                        ["lightning", "cells", "hits, %"]))
    print("\n### 15. Movement in a fight: the enemy in view within 800 units ({})\n".format(m0))
    Fg = R[m0]["fight_movement"]
    keys = (("minutes", "minutes"), ("strafe_changes_a_second", "changes of strafe direction a second"), ("in_the_air_share", "in the air, %"), ("crouched_share", "crouched, %"),
            ("jumps_a_minute", "jumps a minute"), ("speed", "speed"), ("distance_change_a_second", "change of the distance a second"))
    print(table([[n] + [v.get(k) for k, _ in keys] for n, v in Fg["by"].items()], ["", *[lbl for _, lbl in keys]]))
    keys = (("hits", "hits of 50 or more"), ("died_within_2s_share", "dead within 2 s, %"), ("lost_view_share", "the enemy out of view for 0.5 s within 2 s, %"), ("weapon_change_share", "weapon changed, %"),
            ("distance_change_mean", "change of the distance in 2 s"), ("farther_by_100_share", "farther by 100 or more, %"), ("nearer_by_100_share", "nearer by 100 or more, %"))
    print("\n" + table([[n] + [v.get(k) for k, _ in keys] for n, v in Fg["after_a_big_hit"].items()], ["after a hit of 50 or more that he lives through", *[lbl for _, lbl in keys]]))


def show_fights(R, cols):
    """the tables of fights taken and refused, the flick by the angle, the view while travelling"""
    m0 = cols[0]
    if "fights" not in R[m0]:
        return
    Ft = R[m0]["fights"]
    print("\n### 16. Fights taken and refused ({}): what he does with a sighting, and how it goes\n".format(m0))
    keys = (("sightings", "sightings"), ("takes_share", "takes it, %"), ("commits_share", "... and is still in it after 3 s (commits), %"),
            ("refuses_share", "refuses it, %"), ("index", "index: taken of taken and refused, %"))
    sub = (("frags_for_less_of_him", "frags for less of him in 10 s"), ("damage_dealt_less_taken_in_10s", "damage dealt less taken in 10 s"), ("frag_of_him_share", "a frag of him, %"))

    def line(name, c):
        return [name] + [c.get(k) for k, _ in keys] + [(c.get("when_taken") or {}).get(k) for k, _ in sub] + [(c.get("when_refused") or {}).get(k) for k, _ in sub] + [c.get("taking_pays")]

    def short(name, c):                                         # (a map's own entry in the second file)
        return [name] + [c.get(k) for k, _ in keys] + [c.get("taken_frags_for_less_of_him", (c.get("when_taken") or {}).get("frags_for_less_of_him")),
                                                      c.get("refused_frags_for_less_of_him", (c.get("when_refused") or {}).get("frags_for_less_of_him")), c.get("taking_pays")]
    head = ["situation"] + [lbl for _, lbl in keys] + ["taken: " + lbl for _, lbl in sub] + ["refused: " + lbl for _, lbl in sub] + ["taking pays (frags)"]
    rows = [line("all", Ft["all"])]
    for fname, tab in Ft["by"].items():
        rows += [line("{}: {}".format(fname, lvl), c) for lvl, c in tab.items()]
    print(table(rows, head))
    for pname, tab in list(Ft.get("pairs", {}).items())[:2]:
        print("\n" + table([line(k, c) for k, c in tab.items()], [pname] + head[1:]))
    maps_ = [m for m in cols if m not in ("all", "all_ten", "all_given") and "fights" in R[m]]
    if len(maps_) > 1:
        print("\nBy map, all sightings:\n")
        print(table([short(m, R[m]["fights"]["all"]) for m in maps_], ["map"] + [lbl for _, lbl in keys] + ["taken: frags for less of him in 10 s", "refused: the same", "taking pays (frags)"]))
    ck = Ft.get("enemy_stack_guess_check")
    if ck:
        print("\nThe guess of the enemy's stack beside the truth at {} cuts to the other player: off by {} (median; the table of stack by time since a spawn alone: {}), in the right band {}% (the table alone {}%), correlation {}.".format(
            ck["cuts"], ck["guess_off_by_median"], ck["table_alone_off_by_median"], ck["guess_in_the_right_band_share"], ck["table_alone_in_the_right_band_share"], ck["correlation"]))
    for md, what in ((Ft.get("commit_model"), "Commits against every other offer"),):
        if md:
            print("\n{} as a formula ({} sightings, {}% commit; log loss {} against {}): intercept {}; effects ".format(
                what, md["sightings"], md["takes_share"], md["log_loss"], md["log_loss_of_the_plain_share"], md["intercept"]) +
                "; ".join("{}: {}".format(f, ", ".join("{} {:+.2f}".format(l_, v) for l_, v in e.items() if v)) for f, e in md["effects"].items()))
    md = Ft.get("index_model")
    if md:
        print("\nThe index as a formula ({} sightings taken or refused; log loss {} against {} for the plain share): intercept {}; effects ".format(
            md["sightings"], md["log_loss"], md["log_loss_of_the_plain_share"], md["intercept"]) +
            "; ".join("{}: {}".format(f, ", ".join("{} {:+.2f}".format(l_, v) for l_, v in e.items() if v)) for f, e in md["effects"].items()))
    Fl = R[m0]["flick_curve"]
    print("\n### 17. The flick by how far off target he is as the enemy appears ({})\n".format(m0))
    keys = (("appearances", "appearances"), ("a_shot_within_3s_share", "a shot within 3 s, %"), ("seconds_to_the_first_shot_median", "seconds to the first shot, median"),
            ("a_hit_within_3s_share", "a hit within 3 s, %"), ("seconds_to_the_first_hit_median", "seconds to the first hit, median"),
            ("hits_of_the_first_half_second_of_fire_share", "hits of the first 0.5 s of fire, %"))
    rows = [[b] + [c.get(k) for k, _ in keys] for b, c in Fl["by_angle"].items()]
    for wn, tab in Fl["by_angle_and_weapon"].items():
        rows += [["{}, {}".format(wn, b)] + [c.get(k) for k, _ in keys] for b, c in tab.items()]
    for dn, tab in Fl["by_angle_and_distance"].items():
        rows += [["{}, {}".format(dn, b)] + [c.get(k) for k, _ in keys] for b, c in tab.items()]
    print(table(rows, ["off target as a clear line to the enemy opens"] + [lbl for _, lbl in keys]))
    print("\nHis view with nobody in view:\n")
    Tv = {m: R[m]["view_travelling"] for m in cols}
    rows = [["travelling at 350 or more: his view off his direction of travel, degrees, median"] + [Tv[m]["view_off_his_direction_of_travel"]["median"] for m in cols],
            ["... within 20 degrees of it, % of that time"] + [Tv[m]["view_off_his_direction_of_travel"]["within_20_share"] for m in cols],
            ["... over 90 degrees off it, %"] + [Tv[m]["view_off_his_direction_of_travel"]["over_90_share"] for m in cols]]
    for lbl in ("travelling at 350 or more, no enemy in view", "all his time with no enemy in view"):
        for k, kl in (("view_within_20_of_where_he_last_saw_him_share", "within 20 degrees of where he last saw him, %"),
                      ("view_at_one_of_the_maps_places_share", "at one of the map's places (20 degrees, a clear line), %"),
                      ("view_at_the_doorway_the_enemy_would_come_through_share", "at the doorway the enemy would come through, %")):
            rows.append(["{}: {}".format(lbl, kl)] + [Tv[m][lbl][k] for m in cols])
    print(table(rows, ["", *cols]))


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
    walking="his feet on the ground and his horizontal speed steady (changing by under 3 units a second from frame to frame, the frame before and after); the walking speed is the fullest 10-unit bin of that time from 100 to 260 units a second if it stands clear of the bins 30 units either side, and walking is the steady time in that bin and the one either side of it, not crouched. Crouched and moving: his eye low, on the ground, 50 units a second or more. Standing: under 50. 'Quiet' is the three together",
    spam_when="the blind shots that land 150 units or more from himself. The landing place within 300 units of the nearest of mega, armors, rocket launcher, rail, lightning; a mega or armor's return 'as far as he knows': his own last pickup of it in this stretch plus 35 s (mega) or 25 s (armor), if that lies ahead; 'unknown' if he did not take it or it should be back. Hurt: his health plus armor went down by 20 (50) or more in the 5 s before, single losses of under 3 not counted",
    hit_combinations="from his own hit counter: a step of it on a frame he fires lightning, rail, machine gun or shotgun on (or the frame before) is that weapon's hit; any other step is the hit of the rocket, grenade or plasma ball of his that is due about then (from 0.05 s after the shot to 0.2 s after it would reach the wall his view pointed at; a grenade until its fuse ends). A pair: a rocket (grenade) that hit, then the first lightning or rail hit within 1.5 s. A frag 'after a pair': within 2 s of the pair's second hit",
    looking="a sighting: the enemy comes into view after 1 s or more out of it. The angle between his view and the direction from his eye to the place the enemy appears at (the enemy's place on the sighting's frame), sideways (yaw) and up-down (pitch) apart, on that frame and on the frames 0.25 s and 0.5 s before. On the sighting's frame the enemy is inside the 55 degree cone by definition. A sound: a new event of the enemy's entity (a jump or jump pad, a shot, an item picked up) in the last second while the server sent him and he was within 1200 units; a demo has his events only while the server sends him, which is also when the player's own game could play them. Of the time with no enemy in view: his view within 20 degrees of the enemy's true place (only where the demo has it), of the place he last saw him in this stretch, of the nearest mega or armor (walls not looked at)",
    holds="a hold: 2 s or more within 150 units of where the stretch began, alive, no enemy in view, rockets, lightning or rail in hand. What follows is read to 3 s (the enemy in view) and 5 s (who deals damage first: a step of his hit counter against a loss of his own health and armor; frags) after its end. Its cell: 256 x 256 x 128 as tools/pro_places.py's, named by the nearest big item. His view 'at' a big item or a teleporter's exit: within 20 degrees with a clear line, on every fourth frame of the hold. A trap: a rocket or grenade fired with no enemy in view for 1 s or more during the hold or within 1 s after it, whose hit (as in hit_combinations) comes within 1.5 s of the shot",
    hands="turn speed: the angle between his view on two snapshots over the time between them (a demo has his view 40 times a second, 30 in some old spectator demos: faster movements inside a snapshot are not seen, peaks are means over 25 ms). The flick: from the sighting's frame to 0.3 s later. Accuracy: hits as in hit_combinations over shots (ammunition going down), by the distance to the enemy on the shot's frame where the demo has his place; a rocket's hit is 'direct' when the enemy is within 60 units of where the rocket was in the 75 ms before the hit shows. The enemy's crossing speed: his velocity relative to P across the line of sight over the distance, in degrees a second, from his places on two snapshots. Turning changes while tracking: the sign of the yaw's change flips between two frames on which a lightning cell left within the last 0.1 s, with the enemy in view",
    fight_movement="frames with the enemy in view within 800 units. A change of strafe direction: his speed to his right (over 60 units a second) has the other sign than the last time it was over 60, within a second. A jump: he leaves the ground with 150 or more upward speed. The change of the distance: per second, both players' movement in it (minus = nearer). After a big hit: his health and armor fall by 50 or more on one frame and he lives; read 2 s on",
    fights="an offer: a sighting (the enemy in view after 1 s or more out of it). Takes it: within 3 s he deals damage (a step of his hit counter) or is 150 units or more nearer to the enemy than at the sighting (at the last moment of the 3 s the enemy's place is known). Refuses it: neither of those, and the enemy is out of his view for 0.5 s at a stretch or he is 150 or more farther. How it goes: the damage he deals is counted from his hits (rocket 70, rail 80, a lightning cell 6, machine gun 5, a shotgun shell 40, grenade 60, plasma 20: a demo has no damage numbers), the damage he takes is his own health and armor going down; frags from the game's death notices (exact, also after a cut of the demo); a big item (mega, red, yellow armor) for him within 15 s, and for the enemy only where the server sent the enemy's pickup. The enemy's stack is a guess (enemy_estimate): 125 at his spawn, less the counted damage of his hits, more by pickups seen or heard, rising toward the pros' own stack by time since a spawn while unseen; checked at the demos' cuts to the other player (enemy_stack_guess_check). The index of a situation: taken / (taken + refused); index_model gives it for any mix of the sides as a logistic formula. 'Commits': he takes it and after the 3 s the view was never broken for 0.5 s, he is not 150 farther and he lives (commits_share is of all offers; commit_model is its formula); 'fires and leaves' is the rest of the taken ones. 'Taking pays': frags for less frags of him within 10 s when taken, less the same when refused",
    flick_curve="an appearance: a clear line to the enemy opens after 1 s or more without one, wherever his view points (the sightings elsewhere need the enemy inside the 55 degree cone; here the angle runs to 180). The weapon is that of his first shot within 3 s, else the one in his hand. Hits as in hit_combinations; of the first 0.5 s of fire: the shots of that weapon from his first shot on for 0.5 s and the hits of those shots",
    view_travelling="his view against the direction of his velocity while he moves at 350 or more with no enemy in view; and on every 16th such frame: his view within 20 degrees of one of the map's places (sim/pro_places) with a clear line to it and under 3000 units, and of 'the doorway': the first spot on the walking map's quickest way from where he last saw the enemy to himself that he has a clear line to (the place itself if he has a clear line to it)",
    not_measured=[
        "whether a blind shot did damage, exactly: a demo has no damage events. The extra 'hit' is his own hit counter going up as the shot lands",
        "where the enemy is while the server does not send him (out of sight and away): 'met' misses an enemy who was there unseen, and a blind shot at an enemy heard is not told from one at nothing",
        "the enemy's health, armor and weapons: play by 'who is stronger' can only be read from P's own stack",
        "the enemy's pickups and an item's true state while it is out of his sight: the return time counts from P's own pickup only; an item the enemy took in between returns later than counted",
        "the enemy's score as a number (the lead is exact, from the rank)",
        "the game clock of a demo that begins in a running game, and of a game with a timeout",
        "sounds: what he heard is not in a demo",
        "a grenade that went off on a player before its fuse ended",
        "the enemy's own aim and hands: a demo has the followed player's view on every snapshot and the other player's only as an entity while the server sends him",
        "sounds the player heard from farther than the server sends an entity, footsteps (not read), and whether he listened",
        "direct and splash hits as such: a demo has no damage numbers; 'direct' is read from where the rocket was",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=MAPS + "," + MORE)
    ap.add_argument("--ways", default=None, help="the folder of the ways as routes (default sim/pro_ways; a sample writes none)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many demos a map, spread over the archive")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--json", default=None, help="where the numbers go (default docs/pro_yardsticks.json; a sample or a part of the maps is only shown)")
    ap.add_argument("--show", default=None)
    ap.add_argument("--check", action="store_true", help="the clock, the score and the pickups beside the demo site's own numbers")
    a = ap.parse_args()
    if a.show:
        return show(load_both(a.show))
    maps = a.map.split(",")
    res, total, t0 = dict(about=ABOUT, maps={}), new_tally(), time.time()
    total_skips, infos = {}, {}
    total10, skips10 = new_tally(), {}
    frows = {}
    for mp in maps:                                             # the walking maps' next steps, once, before the workers want them
        nav_hops(mp)
    ways_dir = a.ways or (None if a.limit else os.path.join(ROOT, "sim", "pro_ways"))
    low_priority()
    for mp in maps:
        files, rs, big = run_map(mp, a.limit, a.procs, a.redo)
        T, skips, rows = new_tally(), {}, dict(blind=[], sight=[], view=[], fight=[])
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
        frows[mp] = np.array(rows["fight"], np.int32).reshape(-1, len(FIGHT_COLS))
        for k, width in (("blind", 9), ("sight", len(SIGHT_COLS)), ("view", len(VIEW_COLS)), ("fight", len(FIGHT_COLS))):   # (a sample's rows beside the archive's, not over them)
            np.save(os.path.join(demo_root(), "yardsticks", "{}_{}{}.npy".format(k, mp, ".sample" if a.limit else "")),
                    np.array(rows[k], np.int32).reshape(-1, width))
        del rows
        res["maps"][mp] = dict(report(T), demos_in_archive=len(files), left_out=skips)
        if len(maps) > 1:
            res["maps"][mp]["aggression"].pop("cells")          # (a map alone is too thin for the five-way table)
            for k in ("ground_time_by_speed_share", "steady_ground_time_by_speed_share", "crouched_ground_time_by_speed_share"):
                res["maps"][mp]["walking"].pop(k, None)         # (the histograms under the sums)
        if ways_dir:                                             # the ways as routes
            os.makedirs(ways_dir, exist_ok=True)
            with open(os.path.join(ways_dir, mp + ".json"), "w", encoding="utf-8") as f:
                json.dump(pro_ways(T, mp, dict(big=big)), f)
        if mp in MAPS.split(","):
            add_tally(total, T)
            for k, v in skips.items():
                total_skips[k] = total_skips.get(k, 0) + v
        add_tally(total10, T)
        for k, v in skips.items():
            skips10[k] = skips10.get(k, 0) + v
        print("{}: {} demos, {} used, left out {}, {:.0f} s".format(mp, len(files), T["demos"], skips, time.time() - t0), file=sys.stderr, flush=True)
    if len(maps) > 1:
        six = [m for m in maps if m in MAPS.split(",")]
        tops = {}
        if len(six) > 1:
            tops["all"] = dict(report(total), left_out=total_skips)
        if len(maps) > len(six):
            tops["all_ten" if len(maps) == 10 else "all_given"] = dict(report(total10), left_out=skips10)
            tops["all_ten" if len(maps) == 10 else "all_given"]["aggression"].pop("cells")
        for v in tops.values():
            for o in v["predictability"]["maps"].values():
                o["routes"].pop("by_pair")                      # (under the map itself)
            v["holds"].pop("top_cells", None)                   # (under the map itself)
        for name, ms in (("all", six), ("all_ten", maps), ("all_given", maps)):
            if name in tops and sum(len(frows[m]) for m in ms) >= 2000:
                tops[name]["fights"]["index_model"] = fight_model(np.concatenate([frows[m] for m in ms]))
                tops[name]["fights"]["commit_model"] = fight_model(np.concatenate([frows[m] for m in ms]), commit=True)
        res["maps"] = dict(tops, **res["maps"])
    if a.check:
        return check(infos)
    out = a.json or (None if a.limit or a.map != MAPS + "," + MORE else os.path.join(ROOT, "docs", "pro_yardsticks.json"))
    if out:
        res2 = dict(about={k: ABOUT[k] for k in ABOUT2}, maps={})
        for m, v in res["maps"].items():                        # a map alone: without the tables by pair
            v2 = {k: v[k] for k in GROUPS2 if k in v}
            if m not in ("all", "all_ten", "all_given"):
                v2 = json.loads(json.dumps(v2))
                v2.get("fights", {}).pop("pairs", None)
                for c_ in [v2.get("fights", {}).get("all", {})] + [c_ for tab in v2.get("fights", {}).get("by", {}).values() for c_ in tab.values()]:
                    for k, short in (("when_taken", "taken_frags_for_less_of_him"), ("when_refused", "refused_frags_for_less_of_him"), ("when_neither", None)):
                        w_ = c_.pop(k, None)
                        if w_ and short:
                            c_[short] = w_.get("frags_for_less_of_him")
                for k in ("by_angle_and_distance", "by_angle_and_weapon"):
                    v2.get("flick_curve", {}).pop(k, None)
            res2["maps"][m] = dict(demos=v.get("demos"), minutes=v.get("minutes"), **v2)
        first = dict(about={k: x for k, x in res["about"].items() if k not in ABOUT2},
                     maps={m: {k: x for k, x in v.items() if k not in GROUPS2} for m, v in res["maps"].items()})
        dump_json(first, out)
        dump_json(res2, second_file(out))
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

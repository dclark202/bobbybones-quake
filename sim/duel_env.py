"""Duel simulator: two players per match, all duel weapons, items, damage, knockback, respawn. Self-play ready.

Same movement physics as movement_env (human 125 fps substeps). Each player only knows what a human would:
the opponent's position when in line of sight and inside a 110 degree view (150 ms late), or roughly when
heard nearby; incoming projectiles; item positions (map knowledge) and whether an item is up only while
looking at it. One policy can control both players (self-play).
Reward: +1 frag, -1 death (suicide = death), plus optional damage-dealt / item shaping (curriculum).

Weapons, measured on a real server (plugins/weaponlab.py, sim/validate_weapons.py, docs/RESULTS.md):
  rocket launcher   100 direct, 84 splash within 120 units, 1000 u/s, refire 0.8 s
  railgun           80, instant, refire 1.5 s
  lightning gun     6 per 50 ms, range 768
  machine gun       5 per 100 ms (the starting weapon)
  shotgun           20 pellets x 5, spread ~3 degrees (100 at 100 units, 60 at 300, 25 at 600), refire 1 s
  grenade launcher  100 direct, 100 splash within 150, 700 u/s with gravity, bounces, 2.5 s fuse, refire 0.8 s
  plasma gun        20 per hit every 100 ms, 2000 u/s, 15 splash within 20 units
  heavy machine gun 8 per 75 ms
  gauntlet          50 per 400 ms, melee reach
  A shot leaves one frame after the command; a projectile does not move on the frame it appears.
  Knockback: 5 u/s per point, with a factor per weapon; splash pushes upward; own splash damage is halved.
Items (Quake Live duel rules; pickup amounts measured on a real server, ammo caps not yet):
  health +5 (to 200) / +25 / +50 (to 100) / mega +100 (to 200), respawn 35 s; armor shard +5 / 25 / 50 / 100
  (to 200), respawn 25 s; weapons respawn 5 s; ammo 40 s. Armor absorbs 2/3 of damage. Health and armor above
  100 decay 1 per second. Spawn: 125 health, 0 armor.
Aim: mouse-like turn speeds (0.1 .. 60 degrees per frame) followed with a little inertia; jerky changes cost a
tiny bit of reward. The reticle-to-enemy distance is an input, computed from the player's current view and the
opponent's (150 ms old) position.
Weapon drills: in a share of rounds both players have exactly one weapon (see drill_p / drill_weapons).
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsim import World  # noqa: E402

DT = 0.025
_T = [0.03, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60]
TURN = np.array([-v for v in reversed(_T)] + [0] + _T, np.float32)            # degrees per frame
_P = [0.03, 0.1, 0.3, 1, 3, 8, 20]
PITCH = np.array([-v for v in reversed(_P)] + [0] + _P, np.float32)

# weapon table. kind: proj (projectile), hit (instant trace), pellet (shotgun), melee
RL, RG, LG, MG, SG, GL, PG, HMG, G = range(9)
WEAPONS = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")
NW = len(WEAPONS)
W_KIND = ("proj", "hit", "hit", "hit", "pellet", "proj", "proj", "hit", "melee")
W_DMG = np.array([100, 80, 6, 5, 5, 100, 20, 8, 50], np.float32)             # per hit / pellet
W_REFIRE = np.array([0.8, 1.5, 0.05, 0.1, 1.0, 0.8, 0.1, 0.075, 0.4], np.float32)
W_KNOCK = np.array([0.9, 0.85, 1.167, 0.4, 0.85, 1.1, 1.1, 0.625, 1.0], np.float32)     # direct hits, on other players
W_RANGE = np.array([0, 8192, 768, 8192, 8192, 0, 0, 8192, 52], np.float32)
# projectiles: speed, splash damage, splash radius, gravity, fuse seconds (0 = explodes on contact only)
P_SPEED = {RL: 1000.0, GL: 700.0, PG: 2000.0}
P_SPLASH = {RL: 84.0, GL: 100.0, PG: 15.0}
P_RADIUS = {RL: 120.0, GL: 150.0, PG: 20.0}
P_GRAV = {RL: 0.0, GL: 800.0, PG: 0.0}
P_FUSE = {RL: 0.0, GL: 2.5, PG: 0.0}
GL_BOUNCE = 0.65
SPLASH_KNOCK, SPLASH_KNOCK_SELF = 1.07, 1.3            # splash pushes 5 u/s per point of splash damage, times this
                                                       # (rocket at an enemy's feet 450 u/s, at your own 549; plasma 80 / 95)
SPLASH_NEAR = 20.0                                     # measured splash falloff sits ~20 units closer than box distance
SG_PELLETS, SG_SIGMA = 20, 3.0                         # pellet spread: gaussian, degrees
SELF_FACTOR, SPAWN_HP, VIEW_H = 0.5, 125.0, 26.0
SWITCH = 0.425                                         # seconds from the switch command until the new weapon can fire
                                                       # (measured: 17 frames, weaponlab set 3; was a guessed 0.1)
SWITCH_COST = 0.02                                     # reward cost per weapon switch (0.002 was drowned out by the entropy bonus)
BLIND_FIRE_COST = 0.003                                # per frame of holding fire with no enemy seen for over a second (was 0.0005)
MOUSE_SMOOTH_FINE = 0.2                                # less view inertia for small corrections (commands up to 1 degree)
NORMAL, AIM, DRILL, MOVE, SOLO, COURSE = range(6)      # round kinds (SOLO: test rooms only; COURSE: lab-map movement courses)
STYLES = ("random", "still", "slow", "fast", "jump")   # scripted target movement (test rooms use 1-4)
DRILL_AMMO = np.array([15, 10, 100, 100, 15, 10, 80, 100, 1], np.float32)   # finite ammo in drill and aim rounds
MOVE_SCALE, MOVE_ARRIVE = 0.2, 0.3                     # movement rounds: reward per second gained toward the goal, arrival
N_GOAL = 7                                             # goal inputs: on, where (3), next waypoint (3)
# inputs added after duel_gru_v3 (appended at the end, so an older network can be widened without losing skills):
# clock and score 10, more items 8 x 6, sounds 20, map position and identity 6, view / up / long rays 28,
# enemy details 12, hit feedback 4, nearest teleporter and jump pad 11, crouched 1
N_XITEMS = 8
N_VIEW, N_UP, N_LONG = 15, 5, 8
N_EXTRA = 10 + 6 * N_XITEMS + 20 + 6 + (N_VIEW + N_UP + N_LONG) + 12 + 4 + 11 + 1
MAP_IDS = ("bloodrun", "aerowalk", "lostworld")       # third slot was campgrounds until 2026-10-04
HEAR_EVT = 1200.0                                      # item pickups, weapon fire, jumps, teleports are heard this far
                                                       # (not measured against the game)
VIEW_H_DUCK, TOP, TOP_DUCK = 12.0, 32.0, 16.0          # eye height and box top when crouched (Quake 3 values)
WALK = 64                                              # key strength when walking (silent: under the footstep speed)
FALL_MED, FALL_FAR = 40.0, 60.0                        # Quake 3 fall damage: 5 above "medium", 10 above "far"
# scripted fighter styles, good and bad. Columns: turn gain, aim noise (deg), backs off below this distance,
# advances above this distance, fixed weapon (-1 = rockets close / lightning mid / rail far, -2 = random)
PERSONAS = ("allround", "sniper", "rusher", "tracker", "dodger", "stander", "jumper", "spammer")
P_GAIN = np.array([0.4, 0.4, 0.4, 0.45, 0.4, 0.15, 0.3, 0.3], np.float32)
P_NOISE = np.array([0.3, 0.3, 0.5, 0.3, 0.3, 0.6, 1.5, 1.5], np.float32)
P_NEAR = np.array([200, 700, 0, 250, 300, 0, 0, 200], np.float32)
P_FAR = np.array([500, 1200, 0, 550, 600, 1e9, 0, 500], np.float32)
P_WEAPON = np.array([-1, RG, RL, LG, -1, -1, -1, -2], np.int64)
REACT_FRAMES = 2                                       # 50 ms: tracking an enemy already in view lags by this much.
ACQUIRE_FRAMES = 8                                     # 200 ms: an enemy who has just come into view is not reacted to before this
TURN_CAP = 30.0                                        # fastest flick, degrees per frame (1200 deg/s)
MOTOR_NOISE, MOTOR_BASE = 0.08, 0.02                   # hand noise: this share of the view movement, plus a little, per frame
RELOAD_JITTER, RELOAD_JITTER_MAX = 0.05, 0.12          # slow weapons: random extra delay after the reload (mean, max seconds)
DMG_TAKEN_W = 2.0                                      # damage taken (any source) weighs this much against damage dealt
FIRE_TOGGLE_COST = 0.003                               # reward cost each time the fire button changes (holding is free)
LOAD_GUNS = (0, 1, 2, 4, 5, 6, 7)                      # weapons that random loadouts draw from (all but machine gun, gauntlet)
#                                                       older note: default 25 ms (one frame): what a player knows about the opponent lags.
                                                       # Was 6 (150 ms) up to duel_gru_v2; per run: env.react_frames / --react-ms
MOUSE_SMOOTH = 0.5                                     # view velocity inertia per frame
JERK_COST = 0.00002                                    # reward cost per degree/frame of change in the turn command
FOV_COS = math.cos(math.radians(55))
HEAR = 800.0
K = 8                                                  # projectiles in flight per player, max
MINS = np.array([-15, -15, -24], np.float32)
MAXS = np.array([15, 15, 32], np.float32)
ARMOR_ABSORB = 0.66
AMMO_MAX = np.array([25, 25, 150, 150, 25, 25, 150, 150, 1], np.float32)      # per weapon (gauntlet: none)
ALWAYS = np.array([False, False, False, True, False, False, False, False, True])   # machine gun + gauntlet
LOADOUTS = {   # weapons owned at spawn, ammo
    # ammo = what one weapon pickup gives in the real game (measured, plugins/itemlab.py)
    "full": ((RL, RG, LG), {RL: 10, RG: 10, LG: 100, MG: 100}),
    "all": ((RL, RG, LG, SG, GL, PG, HMG), {RL: 10, RG: 10, LG: 100, MG: 100, SG: 10, GL: 10, PG: 50, HMG: 50}),
    "mg": ((), {MG: 100}),
}
# forward, strafe, vertical (none / jump / crouch), turn, pitch, fire, weapon (keep/...), walk
ACTION_DIMS = (3, 3, 3, len(TURN), len(PITCH), 2, 1 + NW, 2)
N_WALL, N_FLOOR, N_PROJ = 16, 8, 2
SLOTS = ("MH", "RA", "YA", "GA", "RL", "RG", "LG", "SG", "GL", "PG", "HMG")   # nearest item of each kind is an input
OBS_BASE = 3 + 1 + 5 + 2 + N_WALL + N_FLOOR + 18 + 9 * N_PROJ + NW + NW + NW + 6 * len(SLOTS) + N_GOAL   # as in duel_gru_v3
OBS_DIM = OBS_BASE + N_EXTRA
# classname -> (kind, value, respawn seconds, cap or amount, slot label)
ITEM_DEFS = {
    "item_health_small": ("hp", 5, 35, 200, None), "item_health": ("hp", 25, 35, 100, None),
    "item_health_large": ("hp", 50, 35, 100, None), "item_health_mega": ("hp", 100, 35, 200, "MH"),
    "item_armor_shard": ("ar", 5, 25, 200, None), "item_armor_jacket": ("ar", 25, 25, 200, "GA"),
    "item_armor_combat": ("ar", 50, 25, 200, "YA"), "item_armor_body": ("ar", 100, 25, 200, "RA"),
    "weapon_rocketlauncher": ("wp", RL, 5, 10, "RL"), "weapon_railgun": ("wp", RG, 5, 10, "RG"),
    "weapon_lightning": ("wp", LG, 5, 100, "LG"), "weapon_shotgun": ("wp", SG, 5, 10, "SG"),
    "weapon_grenadelauncher": ("wp", GL, 5, 10, "GL"), "weapon_plasmagun": ("wp", PG, 5, 50, "PG"),
    "weapon_hmg": ("wp", HMG, 5, 50, "HMG"),
    "ammo_rockets": ("am", RL, 40, 5, None), "ammo_slugs": ("am", RG, 40, 5, None), "ammo_lightning": ("am", LG, 40, 50, None),
    "ammo_bullets": ("am", MG, 40, 50, None), "ammo_shells": ("am", SG, 40, 5, None), "ammo_grenades": ("am", GL, 40, 5, None),
    "ammo_cells": ("am", PG, 40, 50, None), "ammo_hmg": ("am", HMG, 40, 50, None),
    "ammo_pack": ("pack", 0, 40, 0, None),
}
PACK_AMMO = np.array([5, 5, 50, 50, 5, 5, 50, 50, 0], np.float32)


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class DuelEnv:
    def __init__(self, bsp, n_matches=256, seed=0, substeps=(8, 8, 9), dmg_reward=0.004, nav=None, close_p=0.0,
                 loadout="full", drill_weapons=(RL, RG, LG), teacher=None):
        """close_p: chance a respawn lands 300-700 units from the opponent with line of sight (curriculum).
        loadout: weapons at spawn ("full" = RL/RG/LG, "all" = every weapon, "mg" = machine gun + gauntlet only).
        drill_p (attribute): share of rounds where both players have exactly one weapon from drill_weapons."""
        self.M = n_matches
        self.n = 2 * n_matches                          # player i's opponent is i ^ 1
        self.w = World(bsp, n=self.n)
        self.rng = np.random.default_rng(seed)
        self.substeps = tuple(substeps)
        self.dmg_reward = dmg_reward
        self.loadout = loadout
        self.react_frames = REACT_FRAMES
        self.acquire_frames = ACQUIRE_FRAMES
        self.vis_run = np.zeros(2 * n_matches, np.int64)       # frames the opponent has been in view without a break
        self.acquired = np.zeros(2 * n_matches, bool)          # in view long enough to have been noticed
        self.fire_prev = np.zeros(2 * n_matches, bool)
        self.human_aim = True                           # flick cap, hand noise and reload jitter for policy players
        # spawn weapons in normal rounds: share of rounds with 1-2 random weapons each / the real duel spawn
        # (machine gun + gauntlet) / every weapon. Sets are drawn per player at the start of each round.
        self.loadout_p = (0.4, 0.2, 0.2, 0.2)           # ..., and both players with the same single weapon
        self.load_sets = [None] * (2 * n_matches)
        self.item_reward = 0.0                          # optional shaping: reward per 100 points of health/armor picked up
        self.spawns = np.array([e["origin"] for e in self.w.spawns()], np.float32)
        self.spawn_yaw = np.array([float(e.get("angle", 0)) for e in self.w.spawns()], np.float32)
        self.close_p = close_p
        self.level = 0.95                               # pitch eases back toward level (1.0 = off). 0.99 let it drift to floor/sky
        self.drill_p = 0.0                              # share of rounds where both players have ONE weapon
        self.drill_weapons = tuple(drill_weapons)
        self.mode = np.full(n_matches, -1, np.int64)    # per match: -1 = normal, else the only weapon allowed
        # round kinds. NORMAL: duel with the spawn loadout. AIM: the even player has one weapon, the odd player is a
        # scripted strafing target that does not shoot. DRILL: both have one weapon. MOVE: no fight, each player
        # runs to a big item (reward = time gained on the nav graph, as in movement_env).
        self.kind = np.zeros(n_matches, np.int64)
        self.kind_p = (1.0, 0.0, 0.0, 0.0)              # chance of NORMAL, AIM, DRILL, MOVE at each round start
        self.bot_p = 0.0                                # share of NORMAL rounds where the odd player is a scripted fighter
        self.aim_weapons = (LG, LG, LG, RG, RG, RL, PG, SG, HMG, MG)
        self.sg_spawn = True                            # False: nobody spawns holding a shotgun in normal rounds
        self.script = np.zeros(2 * n_matches, np.int64)  # per player: 0 = policy, 1 = strafing target, 2 = scripted fighter
        self.sc_t = np.zeros(2 * n_matches, np.float32)
        self.sc_dir = np.ones(2 * n_matches, np.int64)
        self.sc_fwd = np.zeros(2 * n_matches, np.int64)
        self.sc_jump = np.zeros(2 * n_matches, bool)
        self.sc_persona = np.zeros(2 * n_matches, np.int64)   # scripted fighter style (PERSONAS)
        self.sc_wpn = np.zeros(2 * n_matches, np.int64)
        self.persona_p = np.full(len(PERSONAS), 1.0 / len(PERSONAS))
        self.persona_force = None                       # test rooms: always this style
        self.move_len = 40.0                            # seconds per movement round (several goals in a row)
        # movement teacher: a movement-only policy (sim/train_move.py) whose actions are offered as labels in
        # movement rounds (self.teach: forward, strafe, jump, turn bin; -1 = no label)
        self.teacher = None
        self.teach = np.full((2 * n_matches, 4), -1, np.int64)
        nn_ = 2 * n_matches
        self.duck = np.zeros(nn_, bool)                 # crouched (smaller box, lower eye)
        self.frags_r = np.zeros(nn_, np.float32)        # frags in the current round (the score)
        self.snd_t = np.full((nn_, 4), 99.0, np.float32)    # seconds since heard: pickup, weapon fire, jump, teleport
        self.snd_pos = np.zeros((nn_, 4, 3), np.float32)
        self.snd_kind = np.zeros(nn_, np.int64)         # last pickup heard: 0 mega, 1 red armor, 2 other armor, 3 weapon
        self.fb = np.zeros((nn_, 4), np.float32)        # this frame: damage dealt, damage taken, direction it came from
        self.dmg_life = np.zeros(nn_, np.float32)       # damage dealt to the opponent during his current life
        name = os.path.splitext(os.path.basename(bsp))[0].lower()
        self.map_id = MAP_IDS.index(name) if name in MAP_IDS else -1
        self.sc_style = 0                               # target movement: 0 random (training), else STYLES index
        self.close_band = (300.0, 700.0)                # distance of "close" spawns (test rooms set their own)
        self.fixed_kind = None                          # test rooms: (kind, scripted type for the odd player)
        self.goal = np.full(2 * n_matches, -1, np.int64)  # MOVE rounds: index of the goal item
        self.phi = np.zeros(2 * n_matches, np.float32)    # estimated seconds to the goal
        self.walls = np.ones((2 * n_matches, N_WALL), np.float32)
        self.field = None
        self.round_len = 15.0                           # seconds; matches restart (players near each other) after this
        self.round_t = self.rng.uniform(0, 15.0, n_matches).astype(np.float32)
        self.spots = None
        if nav and os.path.exists(nav):
            self.spots = np.array(json.load(open(nav))["nodes"], np.float32)
        ang = np.linspace(0, 2 * np.pi, N_WALL, endpoint=False)
        self.wall_dirs = np.stack([np.cos(ang), np.sin(ang)], 1).astype(np.float32)
        fang = np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False)
        self.floor_off = np.stack([np.cos(fang), np.sin(fang)], 1).astype(np.float32) * 96.0
        # items
        ents = [e for e in self.w.entities if e.get("classname") in ITEM_DEFS and "origin" in e]
        self.item_pos = np.array([e["origin"] for e in ents], np.float32).reshape(-1, 3)
        self.item_def = [ITEM_DEFS[e["classname"]] for e in ents]
        self.nI = len(ents)
        self.item_up = np.ones((n_matches, self.nI), bool)
        self.item_t = np.zeros((n_matches, self.nI), np.float32)        # seconds until it respawns
        self.slot_items = [[k for k, d in enumerate(self.item_def) if d[4] == lab] for lab in SLOTS]
        # Weapons that lie on this map: nobody spawns with a weapon the map does not have (no heavy machine gun
        # on Aerowalk, for instance). A map without weapon pickups (the test map) allows all.
        self.map_weapons = sorted({int(d[1]) for d in self.item_def if d[0] == "wp"}) or list(range(NW))
        # more items as inputs: second yellow armor, three nearest 25/50 healths, two nearest bubbles or shards,
        # two nearest ammo boxes
        ya = [k for k, d in enumerate(self.item_def) if d[4] == "YA"]
        hl = [k for k, d in enumerate(self.item_def) if d[0] == "hp" and d[1] in (25, 50)]
        sm = [k for k, d in enumerate(self.item_def) if d[0] in ("hp", "ar") and d[1] == 5]
        am = [k for k, d in enumerate(self.item_def) if d[0] in ("am", "pack")]
        self.xslots = [(ya, 1), (hl, 0), (hl, 1), (hl, 2), (sm, 0), (sm, 1), (am, 0), (am, 1)]
        # teleporter entrances with their exits, and jump pads (from the map's trigger brushes)
        spots = self.w.trigger_spots() if hasattr(self.w, "trigger_spots") else []
        self.tele_in = np.array([c for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
        self.tele_out = np.array([d for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
        self.pads = np.array([c for k, c, d in spots if k == 0], np.float32).reshape(-1, 3)
        va, vp = np.radians([-40, -20, 0, 20, 40]), np.radians([-25, 0, 25])
        self.view_grid = np.array([(y, q) for q in vp for y in va], np.float32)        # yaw, pitch offsets
        self.up_dirs = np.array([[0, 0, 1.0]] + [[math.cos(t) * 0.7071, math.sin(t) * 0.7071, 0.7071]
                                                 for t in np.radians([0, 90, 180, 270])], np.float32)
        la = np.linspace(0, 2 * np.pi, N_LONG, endpoint=False)
        self.long_dirs = np.stack([np.cos(la), np.sin(la)], 1).astype(np.float32)
        self.lo, self.hi = [np.asarray(v, np.float32) for v in self.w.bounds()]
        # Test map ("lab"): fixed rooms described in maps/<map>/rooms.json (tools/make_lab_map.py). On such a map
        # every round is a lab room: an aim room (fixed placement, walking or jumping target) or a movement course.
        # New courses added to the map file are picked up here without code changes.
        self.lab, self.courses = None, []
        for cand in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maps", name, "rooms.json"),
                     os.path.join("/ql/maps-data", name, "rooms.json")):
            if os.path.exists(cand):
                self.lab = json.load(open(cand))
                break
        nn2 = 2 * n_matches
        self.course = np.full(nn2, -1, np.int64)        # movement course a player is running (-1 = none)
        self.prog = np.zeros(nn2, np.float32)           # distance along the course's path
        self.seg = np.zeros(nn2, np.int64)
        self.c_t = np.zeros(nn2, np.float32)            # seconds in this attempt
        self.c_top = np.zeros(nn2, np.float32)
        self.c_h = np.zeros(nn2, np.float32)
        self.lab_zone = np.zeros((n_matches, 4), np.float32)
        self.lab_home = np.zeros((n_matches, 3), np.float32)
        self.lab_subj = np.zeros((n_matches, 4), np.float32)    # subject spot and facing
        self.lab_jump = np.zeros(n_matches, bool)
        self.lab_p = (0.4, 0.6)                         # share of lab rounds: aim rooms / movement courses
        self.lab_force = None                           # test suite: dict(kind=..., weapon / where / jump / course)
        self.lab_aim_len, self.course_len = 25.0, 30.0
        if self.lab is not None:
            for key, c_ in self.lab.get("courses", {}).items():
                path = np.array(c_["path"], np.float32)
                seg_len = np.linalg.norm(path[1:] - path[:-1], axis=1)
                cum = np.concatenate([[0.0], np.cumsum(seg_len)]).astype(np.float32)
                cps = np.array([q[:3] for q in c_["checkpoints"]], np.float32)
                cyaw = np.array([q[3] if len(q) > 3 else c_["yaw"] for q in c_["checkpoints"]], np.float32)
                d = np.linalg.norm(path[None, :, :] - cps[:, None, :2], axis=2)
                self.courses.append(dict(key=key, path=path, seg_len=np.maximum(seg_len, 1e-3), cum=cum, cps=cps, cyaw=cyaw,
                                         cprog=cum[d.argmin(1)], start=np.array(c_["start"], np.float32), yaw=float(c_["yaw"]),
                                         fall_z=float(c_["fall_z"]), end_r=float(c_.get("end_r", 120)),
                                         end_z=c_.get("end_z"), weapon=c_.get("weapon", "g"), length=float(cum[-1])))
            self.round_t[:] = 1e9                                     # every match starts a lab room at once
        if nav and os.path.exists(nav):                 # movement goals: mega, red and yellow armor
            goals = [self.item_pos[k] for k, d in enumerate(self.item_def) if d[4] in ("MH", "RA", "YA")]
            if goals:
                from movement_env import NavField
                self.field = NavField(nav, goals, world=self.w)
            if goals and teacher and os.path.exists(teacher):
                import movement_env as M
                ck = np.load(teacher)                           # sim/export_policy.py output (no torch in workers)
                self.teacher_w = tuple(ck[k] for k in ("w0", "b0", "w1", "b1", "wp", "bp", "obs_mean", "obs_var"))
                # the teacher's observation code, on this world (a second World would resize shared buffers)
                T = self.teacher = M.MoveEnv.__new__(M.MoveEnv)
                T.w, T.obs_noise, T.rng = self.w, 0.0, self.rng
                tg = [e["origin"] for e in self.w.entities
                      if e.get("classname", "").startswith(M.GOAL_CLASSES) and "origin" in e]
                T.field = M.NavField(nav, tg, world=self.w)
                T.goal_pos = T.field.goals
                ta = np.linspace(0, 2 * np.pi, M.N_WALL, endpoint=False)
                T.wall_dirs = np.stack([np.cos(ta), np.sin(ta), np.zeros_like(ta)], 1).astype(np.float32)
                tf = np.linspace(0, 2 * np.pi, M.N_FLOOR, endpoint=False)
                T.floor_off = np.stack([np.cos(tf), np.sin(tf)], 1).astype(np.float32) * 96.0
                d = np.linalg.norm(self.teacher.goal_pos[None, :, :] - self.field.goals[:, None, :], axis=2)
                self.t_goal = d.argmin(1).astype(np.int32)        # our goal index -> the teacher's goal index
                self.t_turn = np.abs(TURN[None, :] - M.TURN_BINS[:, None]).argmin(1)   # teacher turn bin -> ours
        n = self.n
        self.yaw = np.zeros(n, np.float32)
        self.pitch = np.zeros(n, np.float32)
        self.mv = np.zeros((n, 2), np.float32)          # mouse velocity (yaw, pitch) in degrees per frame
        self.cmd = np.zeros((n, 2), np.float32)         # last turn command (for the jerk cost)
        self.hp = np.full(n, SPAWN_HP, np.float32)
        self.armor = np.zeros(n, np.float32)
        self.has = np.zeros((n, NW), bool)
        self.ammo = np.zeros((n, NW), np.float32)
        self.cool = np.zeros(n, np.float32)
        self.fire_cd = np.zeros(n, np.float32)          # reload left from the last shot (a switch waits for it)
        self.seen_t = np.full(n, 9.0, np.float32)       # seconds since this player last saw/heard the opponent
        self.known = np.zeros((n, 3), np.float32)       # last known opponent position
        self.rp = np.zeros((n, K, 3), np.float32)       # projectiles, owned by player i
        self.rv = np.zeros((n, K, 3), np.float32)
        self.ra = np.zeros((n, K), bool)
        self.rnew = np.zeros((n, K), bool)              # appeared this frame (move from the next)
        self.rw = np.zeros((n, K), np.int64)            # weapon that fired it
        self.rage = np.zeros((n, K), np.float32)        # seconds in flight (grenade fuse)
        self.weapon = np.zeros(n, np.int64)
        self.fire_q = np.zeros(n, bool)                 # shots triggered last frame (they leave this frame)
        self.fire_w = np.zeros(n, np.int64)
        self.opp_hist = []                              # delayed opponent state (reaction time)
        self.stats = dict(frags=0, suicides=0, dmg=0.0, self_dmg=0.0, jerk=0.0,
                          pick_hp=0, pick_ar=0, pick_mega=0, pick_ra=0, pick_wp=0, pick_am=0,
                          switches=0, fire_frames=0, blind_frames=0, play_frames=0, aim_err=0.0, aim_frames=0,
                          on_target=0, move_frames=0, move_arrive=0, move_speed=0.0, move_fast=0,
                          frags_vs_bot=0, bot_frags=0, target_kills=0, bot_frames=0, aim_round_frames=0,
                          w_dist=np.zeros((3, NW)), dmg_h=0.0, dmg_from_script=0.0,
                          vs_persona=np.zeros((3, len(PERSONAS))), fall_dmg=0.0, duck_frames=0, walk_frames=0)      # rows: frags against, deaths to, frames
        for wn in WEAPONS:
            self.stats[wn + "_shots"] = 0               # shots, ticks or pellets fired
            self.stats[wn + "_shots_vis"] = 0           # ... while the opponent was in view
            self.stats[wn + "_hits"] = 0
            self.stats[wn + "_frags"] = 0
        self.stats["direct"] = 0                        # rockets hitting the body
        # per course: attempts, finishes, time (finished attempts), distance, top speed, speed sum, frames, falls, height
        self.stats["course"] = np.zeros((16, 9))
        self.lab_course_ids = list(range(len(self.courses)))     # courses used when a lab round picks one
        for i in range(n):
            self._spawn(i, avoid=None if i % 2 == 0 else self.w.state()[i - 1, :3])
        self.state = self.w.state()
        self.visible = np.zeros(n, bool)

    # ---------------------------------------------------------------- spawning / helpers
    def _fresh(self, i, yaw):
        self.yaw[i], self.pitch[i] = yaw, 0.0
        self.mv[i] = 0.0
        self.cmd[i] = 0.0
        self.hp[i], self.armor[i], self.cool[i] = SPAWN_HP, 0.0, 0.0
        self.fire_cd[i] = 0.0
        self.duck[i] = False
        self.dmg_life[i ^ 1] = 0.0                      # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // 2])
        kind = int(self.kind[i // 2])
        self.has[i] = False
        self.ammo[i] = 0.0
        if kind in (MOVE, COURSE) or self.script[i] == 1:   # movement round / course / strafing target: unarmed
            self.weapon[i] = G
        elif mode >= 0:                                 # one weapon (finite ammo) + gauntlet
            self.has[i, mode] = True
            self.has[i, G] = True
            self.ammo[i, mode] = DRILL_AMMO[mode]
            self.weapon[i] = mode
        else:
            owned, ammo = LOADOUTS[self.loadout]
            if self.loadout == "all":
                owned = tuple(k for k in owned if k in self.map_weapons and (self.sg_spawn or k != SG))
                ammo = {k: v for k, v in ammo.items() if k in owned or k == MG}
            if self.load_sets[i] is not None and self.script[i] != 2:   # this round's drawn weapon set
                owned = self.load_sets[i]
                ammo = {k: LOADOUTS["all"][1][k] for k in owned}
                ammo[MG] = LOADOUTS["all"][1][MG]
            self.has[i, ALWAYS] = True
            for k in owned:
                self.has[i, k] = True
            for k, v in ammo.items():
                self.ammo[i, k] = v
            # spawn holding a random owned weapon, so normal fights are experienced with every weapon
            # (always starting on rockets, he switched to the shotgun once and never tried the others)
            self.weapon[i] = int(self.rng.choice(owned)) if owned else MG
            if self.script[i] == 2:                     # the scripted fighter does not run dry
                self.ammo[i] = np.minimum(AMMO_MAX, self.ammo[i] * 3)
        self.seen_t[i] = 9.0
        self.vis_run[i] = 0
        self.acquired[i] = False
        self.ra[i] = False
        self.fire_q[i] = False

    def _new_goal(self, i):
        """movement round: pick a big item 1.5-12 s away (by the nav graph) as player i's goal"""
        f = self.field
        pos = self.w.state()[i, :3]
        node, _ = f.locate(pos[None])
        T = f.T[:, node[0]]
        ok = np.nonzero((T > 3.0) & (T < 20.0))[0]            # long trips: speed has to be built and kept
        if not len(ok):
            ok = np.nonzero((T > 1.0) & (T < 1e8))[0]
        if not len(ok):
            self.goal[i] = -1
            return
        g = int(self.rng.choice(ok))
        self.goal[i] = g
        self.phi[i] = f.potential(np.array([g]), pos[None])[0][0]

    def _course_start(self, i, c):
        """put player i at the start of course c and begin an attempt"""
        C = self.courses[c]
        self.w.reset(i, (C["start"][0], C["start"][1], C["start"][2] + 2.0), (0, 0, 0), C["yaw"])
        self._fresh(i, C["yaw"])
        self.course[i], self.prog[i], self.seg[i], self.c_t[i], self.c_top[i], self.c_h[i] = c, 0.0, 0, 0.0, 0.0, 0.0
        if C["weapon"] == "rl":
            self.has[i, RL], self.ammo[i, RL], self.weapon[i] = True, 25, RL
        self.stats["course"][c, 0] += 1

    def _course_close(self, i, finished):
        """an attempt ends (finished, or the round is over): add it to the course statistics"""
        c = int(self.course[i])
        if c < 0:
            return
        row = self.stats["course"][c]
        row[1] += int(finished)
        row[2] += float(self.c_t[i]) if finished else 0.0
        row[3] += self.courses[c]["length"] if finished else float(self.prog[i])
        row[4] += float(self.c_top[i])
        row[8] += float(self.c_h[i])

    def _course_back(self, i):
        """after a fall or a death: back to the last checkpoint already passed"""
        C = self.courses[int(self.course[i])]
        ok = np.nonzero(C["cprog"] <= self.prog[i] + 32)[0]
        k = int(ok[C["cprog"][ok].argmax()]) if len(ok) else 0
        self.w.reset(i, (C["cps"][k, 0], C["cps"][k, 1], C["cps"][k, 2] + 2.0), (0, 0, 0), float(C["cyaw"][k]))
        self.yaw[i], self.pitch[i], self.mv[i] = float(C["cyaw"][k]), 0.0, 0.0
        self.hp[i], self.armor[i] = SPAWN_HP, 0.0
        self.stats["course"][int(self.course[i]), 7] += 1

    def _course_step(self, reward):
        """movement courses: progress along the path, falls, the finish. Returns True if anybody was moved."""
        moved = False
        s = self.state
        for c in np.unique(self.course[self.course >= 0]):
            C = self.courses[int(c)]
            idx = np.nonzero(self.course == c)[0]
            pos = s[idx, :3]
            a_, b_ = C["path"][:-1], C["path"][1:]
            ab = b_ - a_
            t_ = np.clip(((pos[:, None, :2] - a_[None]) * ab[None]).sum(2) / (C["seg_len"] ** 2)[None], 0, 1)
            d = np.linalg.norm(pos[:, None, :2] - (a_[None] + ab[None] * t_[:, :, None]), axis=2)
            ks = np.arange(len(a_))[None, :]
            d = np.where(np.abs(ks - self.seg[idx][:, None]) <= 1, d, 1e9)      # only near the current segment
            k = d.argmin(1)
            ar_ = np.arange(len(idx))
            prog = C["cum"][k] + t_[ar_, k] * C["seg_len"][k]
            self.seg[idx] = k
            new = np.maximum(self.prog[idx], prog)
            reward[idx] += MOVE_SCALE * (np.clip((new - self.prog[idx]) / 320.0, -0.5, 0.5) - DT)
            self.prog[idx] = new
            sp = np.hypot(s[idx, 3], s[idx, 4])
            self.c_t[idx] += DT
            self.c_top[idx] = np.maximum(self.c_top[idx], sp)
            self.c_h[idx] = np.maximum(self.c_h[idx], pos[:, 2] - C["start"][2])
            self.stats["course"][c, 5] += float(sp.sum())
            self.stats["course"][c, 6] += len(idx)
            if C["weapon"] == "rl":
                self.ammo[idx, RL] = 25
            end = C["path"][-1]
            at_end = (np.hypot(pos[:, 0] - end[0], pos[:, 1] - end[1]) < C["end_r"]) & \
                ((pos[:, 2] >= C["end_z"]) if C["end_z"] is not None else True)
            fell = (pos[:, 2] < C["fall_z"]) & ~at_end
            for i in idx[fell]:
                reward[i] -= 0.1
                self._course_back(int(i))
                moved = True
            for i in idx[at_end]:
                reward[i] += 2 * MOVE_ARRIVE
                self._course_close(int(i), True)
                self._course_start(int(i), int(c))
                moved = True
        return moved

    def _lab_round(self, m):
        """start a lab room for match m: an aim room (odd player = target) or a movement course for both players"""
        a_, b_ = 2 * m, 2 * m + 1
        for q in (a_, b_):
            self._course_close(q, False)
        f, L, rng = self.lab_force, self.lab, self.rng
        pa = self.lab_p[0] / self.lab_aim_len
        pc = self.lab_p[1] / self.course_len
        kd = f["kind"] if f else (AIM if (rng.random() < pa / (pa + pc) or not self.courses) else COURSE)
        self.kind[m], self.mode[m] = kd, -1
        self.script[a_] = self.script[b_] = 0
        self.goal[a_] = self.goal[b_] = -1
        self.course[a_] = self.course[b_] = -1
        self.load_sets[a_] = self.load_sets[b_] = None
        self.frags_r[a_] = self.frags_r[b_] = 0
        self.snd_t[a_] = self.snd_t[b_] = 99.0
        if kd == AIM:
            self.mode[m] = int(f["weapon"]) if f else int(rng.choice(self.aim_weapons))
            self.script[b_] = 1
            self.lab_jump[m] = bool(f["jump"]) if f else rng.random() < 0.5
            where = f["where"] if f else ("env" if rng.random() < 0.33 else "aim")
            if where == "aim":
                A = L["aim"]
                lg = self.mode[m] == LG and "zone_lg" in A      # keep the target inside lightning gun range
                home = np.array(A["target_lg"] if lg else A["target"], np.float32)
                subj, face = np.array(A["subject"], np.float32), float(A["yaw"])
                self.lab_zone[m] = A["zone_lg"] if lg else A["zone"]
            else:
                E_ = L["env"]
                spots = [np.array([q[0], q[1], q[2] if len(q) > 2 else E_["z"]], np.float32) for q in E_["spots"]]
                i = int(rng.integers(len(spots)))
                d = [float(np.linalg.norm(q - spots[i])) for q in spots]
                cand = [k for k, v in enumerate(d) if 400 <= v <= 1300] or [int(np.argmax(d))]
                j = int(rng.choice(cand))
                home, subj = spots[i], spots[j]
                face = math.degrees(math.atan2(home[1] - subj[1], home[0] - subj[0]))
                b = E_["bounds"]
                self.lab_zone[m] = [b[0] + 48, b[1] + 48, b[2] - 48, b[3] - 48]
            self.lab_home[m], self.lab_subj[m] = home, [subj[0], subj[1], subj[2], face]
            ty = float(rng.uniform(-180, 180))
            self.w.reset(b_, (home[0], home[1], home[2] + 2.0), (0, 0, 0), ty)
            self._fresh(b_, ty)
            self.w.reset(a_, (subj[0], subj[1], subj[2] + 2.0), (0, 0, 0), face)
            self._fresh(a_, face)
            # like a person after the countdown, the subject starts the room already looking at the target
            self.vis_run[a_], self.acquired[a_], self.seen_t[a_] = self.acquire_frames, True, 0.0
            self.known[a_] = home
        else:
            for q in (a_, b_):
                self._course_start(q, int(f["course"]) if f else int(rng.choice(self.lab_course_ids)))

    def _lab_respawn(self, v):
        """a death on the lab map: back to the room's own spot, not to a map spawn point"""
        m = v // 2
        if self.course[v] >= 0:
            self._course_back(v)
        elif self.script[v] == 1:
            h = self.lab_home[m]
            ty = float(self.rng.uniform(-180, 180))
            self.w.reset(v, (h[0], h[1], h[2] + 2.0), (0, 0, 0), ty)
            self._fresh(v, ty)
        else:
            q = self.lab_subj[m]
            self.w.reset(v, (q[0], q[1], q[2] + 2.0), (0, 0, 0), float(q[3]))
            self._fresh(v, float(q[3]))

    def _teach_update(self):
        """labels from the movement teacher for players on a movement goal (sampled from its policy)"""
        self.teach[:] = -1
        if self.teacher is None:
            return
        mi = np.nonzero((self.goal >= 0) & (self.script == 0))[0]
        if not len(mi):
            return
        T, s = self.teacher, self.state
        T.n, T.state, T.yaw = len(mi), s[mi], self.yaw[mi]
        T.goal = self.t_goal[self.goal[mi]]
        T.phi = T.field.potential(T.goal, s[mi, :3])[0]
        w0, b0, w1, b1, wp, bp, mean, var = self.teacher_w
        x = np.clip((T.observe() - mean) / np.sqrt(var + 1e-8), -10, 10).astype(np.float32)
        h = np.tanh(np.tanh(x @ w0.T + b0) @ w1.T + b1)
        lg = h @ wp.T + bp
        out, j = [], 0
        for d in (3, 3, 2, 9):
            l = lg[:, j:j + d]
            pr = np.exp(l - l.max(1, keepdims=True))
            pr /= pr.sum(1, keepdims=True)
            out.append((pr.cumsum(1) > self.rng.random((len(mi), 1))).argmax(1))
            j += d
        out[3] = self.t_turn[out[3]]
        self.teach[mi] = np.stack(out, 1)

    def _spawn(self, i, avoid, close=None):
        p_close = self.close_p if close is None else float(close)
        if avoid is not None and self.spots is not None and self.rng.random() < p_close:
            d = np.linalg.norm(self.spots - avoid, axis=1)
            cand = np.nonzero((d > self.close_band[0]) & (d < self.close_band[1]))[0]
            for k in self.rng.permutation(cand)[:24]:
                p = self.spots[k]
                if self.w.trace(p + np.array([0, 0, VIEW_H], np.float32),
                                avoid + np.array([0, 0, 8.0], np.float32))["fraction"] >= 0.999:
                    face = math.degrees(math.atan2(avoid[1] - p[1], avoid[0] - p[0])) + float(self.rng.uniform(-60, 60))
                    self.w.reset(i, (p[0], p[1], p[2] + 1.0), (0, 0, 0), face)
                    self._fresh(i, face)
                    return
        k = int(self.rng.integers(len(self.spawns)))
        if avoid is not None:                            # prefer a spawn away from the opponent
            d = np.linalg.norm(self.spawns - avoid, axis=1)
            far = np.nonzero(d > np.median(d))[0]
            if len(far):
                k = int(self.rng.choice(far))
        p = self.spawns[k]
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), float(self.spawn_yaw[k]))
        self._fresh(i, float(self.spawn_yaw[k]))

    def _eye(self, s):
        e = s[:, :3].copy()
        e[:, 2] += np.where(self.duck[:len(e)], VIEW_H_DUCK, VIEW_H)
        return e

    def _hear(self, cat, src, kind=None):
        """players src made a sound of category cat: their opponents hear it within HEAR_EVT (rough position)"""
        src = np.asarray(src)
        if not len(src):
            return
        s = self.state
        lis = src ^ 1
        k_ = np.repeat(self.kind, 2)[src]
        ok = (np.linalg.norm(s[src, :3] - s[lis, :3], axis=1) < HEAR_EVT) & (k_ != MOVE) & (k_ != SOLO)
        src, lis = src[ok], lis[ok]
        if not len(src):
            return
        self.snd_t[lis, cat] = 0.0
        self.snd_pos[lis, cat] = s[src, :3] + self.rng.normal(0, 60, (len(src), 3)).astype(np.float32) * \
            np.array([1, 1, 0.3], np.float32)
        if kind is not None:
            self.snd_kind[lis] = np.asarray(kind)[ok] if np.ndim(kind) else kind

    def _item_block(self, ids, rank, pos, eye, fdir, up, rot):
        """inputs for the rank-th nearest item of a group: where it is, and whether it is up (only while seen)"""
        n = self.n
        out = np.zeros((n, 6), np.float32)
        if len(ids) <= rank:
            return out
        ar = np.arange(n)
        ip = self.item_pos[ids]
        d = np.linalg.norm(ip[None, :, :] - pos[:, None, :], axis=2)
        near = d.argmin(1) if rank == 0 else np.argsort(d, axis=1)[:, rank]
        it = np.array(ids)[near]
        p = self.item_pos[it]
        tov = p - eye
        dd = np.linalg.norm(tov, axis=1) + 1e-6
        u = (tov / dd[:, None]).astype(np.float32)
        infov = ((u * fdir).sum(1) > FOV_COS) & (dd < 1500)
        sees = np.zeros(n, bool)
        ci = np.nonzero(infov)[0]                             # only trace toward items in view and in range
        if len(ci):
            fr = self.w.rays_each(eye[ci], u[ci][:, None, :], 1500.0)[:, 0]
            sees[ci] = fr * 1500.0 >= dd[ci] - 24
        isup = up[ar, it]
        out[:, 0:3] = rot(p - pos) / 1000.0
        out[:, 3] = 1.0
        out[:, 4] = sees & isup
        out[:, 5] = sees & ~isup
        return out

    def _los(self, a, b):
        """line of sight a -> b for many pairs (point traces)"""
        out = np.zeros(len(a), bool)
        for k in range(len(a)):
            out[k] = np.linalg.norm(b[k] - a[k]) < 1 or self.w.trace(a[k], b[k])["fraction"] >= 0.999
        return out

    @staticmethod
    def _seg_box(p0, p1, c, top=None):
        """does segment p0->p1 cross the player box around center c? (slab test, vectorized).
        top = height of the box above the origin (lower when crouched)"""
        lo, hi = c + MINS, c + MAXS
        if top is not None:
            hi = hi.copy()
            hi[..., 2] = c[..., 2] + top
        d = p1 - p0
        par = np.abs(d) < 1e-9                              # no movement along this axis (or none at all)
        inslab = (p0 >= lo) & (p0 <= hi)
        with np.errstate(divide="ignore", invalid="ignore"):
            t0 = (lo - p0) / d
            t1 = (hi - p0) / d
        tn = np.where(par, np.where(inslab, -np.inf, np.inf), np.minimum(t0, t1))
        tf = np.where(par, np.where(inslab, np.inf, -np.inf), np.maximum(t0, t1))
        tmin, tmax = tn.max(-1), tf.min(-1)
        return (tmax >= np.maximum(tmin, 0)) & (tmin <= 1)

    def _damage(self, v, dmg):
        """armor absorbs 2/3 of the damage while it lasts; returns the total taken (health + armor)"""
        save = min(float(self.armor[v]), math.ceil(dmg * ARMOR_ABSORB))
        self.armor[v] -= save
        self.hp[v] -= dmg - save
        return dmg

    # ---------------------------------------------------------------- observation
    def observe(self):
        s = self.state
        pos, vel, ground = s[:, :3], s[:, 3:6], s[:, 6]
        n = self.n
        yaw, pit = np.radians(self.yaw), np.radians(self.pitch)
        c, si = np.cos(yaw), np.sin(yaw)

        def rot(v):
            return np.stack([c * v[:, 0] + si * v[:, 1], -si * v[:, 0] + c * v[:, 1], v[:, 2]], 1)
        wd = self.wall_dirs
        dirs = np.stack([c[:, None] * wd[None, :, 0] - si[:, None] * wd[None, :, 1],
                         si[:, None] * wd[None, :, 0] + c[:, None] * wd[None, :, 1],
                         np.zeros((n, N_WALL), np.float32)], 2)
        walls = self.w.rays_each(pos, dirs, 512.0)
        self.walls = walls
        off = np.stack([c[:, None] * self.floor_off[None, :, 0] - si[:, None] * self.floor_off[None, :, 1],
                        si[:, None] * self.floor_off[None, :, 0] + c[:, None] * self.floor_off[None, :, 1]], 2)
        starts = np.concatenate([pos[:, None, :2] + off, np.repeat(pos[:, None, 2:3], N_FLOOR, 1)], 2)
        floors = self.w.rays(starts.reshape(-1, 3).astype(np.float32), np.array([[0, 0, -1.0]], np.float32),
                             256.0).reshape(n, N_FLOOR)
        eye = self._eye(s)
        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        opp = np.arange(n) ^ 1
        # Reaction time: what the player knows about the opponent (where, how fast, visible or not) is
        # REACT_FRAMES old. The player's own view is current, so the crosshair-to-enemy readings respond to
        # mouse movement immediately, as on a real screen.
        self.opp_hist.append((self.known.copy(), self.acquired.copy(), vel[opp].copy(), self.seen_t.copy()))
        while len(self.opp_hist) > self.react_frames + 1:
            self.opp_hist.pop(0)
        known, visible, opp_vel, seen_t = self.opp_hist[0]
        rel = rot(known - pos) / 1000.0
        exact = visible.astype(np.float32)
        ovel = rot(opp_vel) / 400.0 * exact[:, None]
        to = known + np.array([0, 0, 4.0], np.float32) - eye
        hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        ang_yaw = np.arctan2(to[:, 1], to[:, 0]) - yaw
        ang_pit = -np.arctan2(to[:, 2], hd) - pit
        # reticle distance to the enemy, in degrees: coarse (+-15) and fine (+-2) readings, both axes
        ey = np.degrees((ang_yaw + np.pi) % (2 * np.pi) - np.pi)
        ep_ = np.degrees(ang_pit)
        dist3 = np.linalg.norm(to, axis=1) + 1e-6
        on_target = self._seg_box(eye, eye + fdir.astype(np.float32) * 4000.0, known,
                                  np.where(self.duck[opp], TOP_DUCK, TOP)) & visible
        size = np.degrees(np.arctan2(20.0, dist3)) / 10.0      # how big the target looks
        opp_feat = np.concatenate([[exact], [np.exp(-seen_t)], rel.T, ovel.T, [np.sin(ang_yaw)], [np.cos(ang_yaw)],
                                   [np.cos(ang_pit)], [np.sin(ang_pit)],
                                   [np.clip(ey / 15.0, -1, 1)], [np.clip(ey / 2.0, -1, 1)],
                                   [np.clip(ep_ / 15.0, -1, 1)], [np.clip(ep_ / 2.0, -1, 1)],
                                   [on_target.astype(np.float32)], [np.clip(size, 0, 1)]], 0).T * (seen_t < 5)[:, None]
        # incoming projectiles (the opponent's), nearest N_PROJ: position, velocity, kind (rocket / grenade / plasma)
        rk = np.zeros((n, 9 * N_PROJ), np.float32)
        orp, orv, ora, orw = self.rp[opp], self.rv[opp], self.ra[opp], self.rw[opp]
        dist = np.where(ora, np.linalg.norm(orp - pos[:, None, :], axis=2), 1e9)
        order = np.argsort(dist, axis=1)[:, :N_PROJ]
        ar = np.arange(n)
        for j in range(N_PROJ):
            idx = order[:, j]
            ok = dist[ar, idx] < 1500
            rk[:, 9 * j:9 * j + 3] = rot(orp[ar, idx] - pos) / 1000.0 * ok[:, None]
            rk[:, 9 * j + 3:9 * j + 6] = rot(orv[ar, idx]) / 1000.0 * ok[:, None]
            kind = orw[ar, idx]
            rk[:, 9 * j + 6] = ok & (kind == RL)
            rk[:, 9 * j + 7] = ok & (kind == GL)
            rk[:, 9 * j + 8] = ok & (kind == PG)
        # items: where the nearest one of each big kind is (map knowledge), and whether it is up, but only
        # while looking at it from within 1500 units (no timers given: remembering them is the player's job)
        up = np.repeat(self.item_up, 2, axis=0)                               # per player (its match)
        items = np.concatenate([self._item_block(ids, 0, pos, eye, fdir, up, rot) for ids in self.slot_items], 1)
        own = np.stack([self.hp / 200.0, self.armor / 200.0, np.minimum(self.cool, 1.5) / 1.5, self.pitch / 90.0,
                        (self.hp <= 0).astype(np.float32)], 1)
        # movement-round goal: where it is and the next waypoint on the way (zeros in every other round)
        goal = np.zeros((n, N_GOAL), np.float32)
        gi = np.nonzero(self.goal >= 0)[0]
        if len(gi) and self.field is not None:
            f = self.field
            g = self.goal[gi]
            node, _ = f.locate(pos[gi])
            nx = f.next[g, node]
            wp = np.where((nx >= 0)[:, None], f.nodes[np.maximum(nx, 0)], f.goals[g])
            cg, sg = c[gi], si[gi]

            def rotg(v):
                return np.stack([cg * v[:, 0] + sg * v[:, 1], -sg * v[:, 0] + cg * v[:, 1], v[:, 2]], 1)
            goal[gi, 0] = 1.0
            goal[gi, 1:4] = rotg(f.goals[g] - pos[gi]) / 2000.0
            goal[gi, 4:7] = np.clip(rotg(wp - pos[gi]) / 500.0, -1, 1)
        for cc in np.unique(self.course[self.course >= 0]):
            C = self.courses[int(cc)]
            ci_ = np.nonzero(self.course == cc)[0]
            cg, sg = c[ci_], si[ci_]

            def ahead(dist_):
                pr = np.minimum(self.prog[ci_] + dist_, C["cum"][-1])
                return np.stack([np.interp(pr, C["cum"], C["path"][:, 0]), np.interp(pr, C["cum"], C["path"][:, 1])], 1)

            def rotc(v):
                return np.stack([cg * v[:, 0] + sg * v[:, 1], -sg * v[:, 0] + cg * v[:, 1]], 1)
            goal[ci_, 0] = 1.0
            goal[ci_, 1:3] = rotc(ahead(600.0) - pos[ci_, :2]) / 2000.0
            goal[ci_, 4:6] = np.clip(rotc(ahead(200.0) - pos[ci_, :2]) / 500.0, -1, 1)
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], own, self.mv / 30.0, walls, floors, opp_feat, rk,
                              np.eye(NW, dtype=np.float32)[self.weapon], self.has.astype(np.float32),
                              self.ammo / AMMO_MAX, items, goal, self._extra(pos, vel, eye, fdir, up, rot, c, si,
                                                                              yaw, pit, visible)], 1)
        return obs.astype(np.float32)

    def _extra(self, pos, vel, eye, fdir, up, rot, c, si, yaw, pit, visible):
        """the inputs added after duel_gru_v3 (see N_EXTRA)"""
        n = self.n
        ar = np.arange(n)
        opp = ar ^ 1
        # clock (item timers are 25 s and 35 s) and score of the round
        t = np.repeat(self.round_t, 2)
        clock = np.stack([np.minimum(t / 120.0, 2.0), np.sin(2 * np.pi * t / 25.0), np.cos(2 * np.pi * t / 25.0),
                          np.sin(2 * np.pi * t / 35.0), np.cos(2 * np.pi * t / 35.0), np.sin(2 * np.pi * t / 60.0),
                          np.cos(2 * np.pi * t / 60.0), np.minimum(self.frags_r / 10.0, 2.0),
                          np.minimum(self.frags_r[opp] / 10.0, 2.0),
                          np.clip((self.frags_r - self.frags_r[opp]) / 5.0, -2, 2)], 1)
        xitems = np.concatenate([self._item_block(ids, r, pos, eye, fdir, up, rot) for ids, r in self.xslots], 1)
        # sounds: how long ago and roughly where, per category; which pickup it was
        fresh = self.snd_t < 5.0
        rel = np.stack([rot(self.snd_pos[:, j] - pos) / 1000.0 for j in range(4)], 1) * fresh[:, :, None]
        snd = np.concatenate([np.exp(-self.snd_t), rel.reshape(n, 12),
                              np.eye(4, dtype=np.float32)[self.snd_kind] * fresh[:, :1]], 1)
        # where on the map, and which map
        where = np.concatenate([(pos - self.lo) / np.maximum(self.hi - self.lo, 1.0) * 2.0 - 1.0,
                                np.eye(len(MAP_IDS) + 1, dtype=np.float32)[np.full(n, self.map_id)][:, :len(MAP_IDS)]], 1)
        # sight: a coarse picture along the view, what is above, and long horizontal distances
        gy, gp = yaw[:, None] + self.view_grid[None, :, 0], pit[:, None] + self.view_grid[None, :, 1]
        vd = np.stack([np.cos(gp) * np.cos(gy), np.cos(gp) * np.sin(gy), -np.sin(gp)], 2).astype(np.float32)
        view = self.w.rays_each(eye, vd, 2000.0)
        ud = self.up_dirs
        udw = np.stack([c[:, None] * ud[None, :, 0] - si[:, None] * ud[None, :, 1],
                        si[:, None] * ud[None, :, 0] + c[:, None] * ud[None, :, 1],
                        np.repeat(ud[None, :, 2], n, 0)], 2).astype(np.float32)
        above = self.w.rays_each(eye, udw, 512.0)
        ld = self.long_dirs
        ldw = np.stack([c[:, None] * ld[None, :, 0] - si[:, None] * ld[None, :, 1],
                        si[:, None] * ld[None, :, 0] + c[:, None] * ld[None, :, 1],
                        np.zeros((n, N_LONG), np.float32)], 2).astype(np.float32)
        far = self.w.rays_each(pos, ldw, 2000.0)
        # the enemy while in view: weapon in hand, whether he faces this player, damage dealt to him this life
        v_ = visible.astype(np.float32)[:, None]
        oy = np.radians(self.yaw[opp])
        back = np.arctan2(pos[:, 1] - self.state[opp, 1], pos[:, 0] - self.state[opp, 0]) - oy
        enemy = np.concatenate([np.eye(NW, dtype=np.float32)[self.weapon[opp]] * v_,
                                np.stack([np.sin(back), np.cos(back)], 1) * v_,
                                np.minimum(self.dmg_life / 200.0, 2.0)[:, None]], 1)
        # nearest teleporter (entrance and exit) and jump pad
        tp = np.zeros((n, 11), np.float32)
        if len(self.tele_in):
            k = np.linalg.norm(self.tele_in[None] - pos[:, None], axis=2).argmin(1)
            tp[:, 0:3] = rot(self.tele_in[k] - pos) / 1000.0
            tp[:, 3:6] = rot(self.tele_out[k] - pos) / 1000.0
            tp[:, 6] = 1.0
        if len(self.pads):
            k = np.linalg.norm(self.pads[None] - pos[:, None], axis=2).argmin(1)
            tp[:, 7:10] = rot(self.pads[k] - pos) / 1000.0
            tp[:, 10] = 1.0
        return np.concatenate([clock, xitems, snd, where, view, above, far, enemy, self.fb, tp,
                               self.duck[:, None].astype(np.float32)], 1).astype(np.float32)

    # ---------------------------------------------------------------- damage helpers
    def _hit(self, i, v, wpn, dmg, kdir, st):
        """player i's weapon wpn hits player v for dmg, pushing along kdir"""
        kf = W_KNOCK[wpn]
        self.w.knockback(int(v), np.asarray(kdir, np.float32) * (1000.0 * kf * dmg / 200.0), int(min(200, dmg)))
        st["dmg_taken"][v] += self._damage(v, dmg)
        self.stats["dmg_h"] += float(dmg) * (self.script[i] == 0)
        self.stats["dmg_from_script"] += float(dmg) * (self.script[v] == 0 and self.script[i] != 0)
        st["attacker"][v] = i
        st["kill_w"][v] = wpn
        st["kicked"] = True
        self.stats["dmg"] += dmg

    def _explode(self, i, wpn, ep, direct_on, hit_dir, s, st):
        """projectile of player i (weapon wpn) explodes at ep; direct_on = player hit directly or None"""
        base = W_DMG[wpn]
        victims = []                                      # (player, health damage, knockback points, direction, direct)
        if direct_on is not None:
            victims.append((direct_on, base, base, hit_dir, True))
        for v in (i, i ^ 1):                              # splash on both players (owner too)
            if v == direct_on:
                continue
            c = s[v, :3]
            e2 = ep.copy()                                # measured: splash acts SPLASH_NEAR units closer than
            h = c[:2] - ep[:2]                            # the plain box distance (horizontally toward the player)
            hl = float(np.linalg.norm(h))
            if hl > 1e-3:
                e2[:2] += h / hl * min(SPLASH_NEAR, hl)
            hi_ = c + MAXS
            if self.duck[v]:
                hi_ = hi_.copy()
                hi_[2] = c[2] + TOP_DUCK
            near = np.clip(e2, c + MINS, hi_)
            d = float(np.linalg.norm(e2 - near))
            R = P_RADIUS[wpn]
            if d < R and self.w.trace(ep, c)["fraction"] >= 0.999:
                f_ = 1.0 - d / R
                kdir = c - e2
                kdir[2] += 24.0                           # as in Quake 3: splash pushes upward
                kn = float(np.linalg.norm(kdir))
                kdir = kdir / kn if kn > 1e-3 else np.array([0, 0, 1.0], np.float32)
                victims.append((v, P_SPLASH[wpn] * f_, P_SPLASH[wpn] * f_, kdir, False))
        for v, dmg, kpts, kdir, is_direct in victims:
            take = dmg * (SELF_FACTOR if v == i else 1.0)
            kf = W_KNOCK[wpn] if is_direct else (SPLASH_KNOCK_SELF if v == i else SPLASH_KNOCK)
            self.w.knockback(int(v), np.asarray(kdir, np.float32) * (1000.0 * kf * kpts / 200.0), int(min(200, kpts)))
            st["kicked"] = True
            st["dmg_taken"][v] += self._damage(v, take)
            if v != i:
                st["attacker"][v] = i
                st["kill_w"][v] = wpn
                self.stats["dmg_h"] += float(take) * (self.script[i] == 0)
                self.stats["dmg_from_script"] += float(take) * (self.script[v] == 0 and self.script[i] != 0)
                self.stats["dmg"] += take
                self.stats[WEAPONS[wpn] + "_hits"] += int(self.script[i] == 0)
                if is_direct and wpn == RL:
                    self.stats["direct"] += 1
            else:
                self.stats["self_dmg"] += take
                if st["attacker"][v] < 0:
                    st["attacker"][v] = v

    # ---------------------------------------------------------------- scripted players
    def _script_actions(self, idx):
        """actions for scripted players. 1 = strafing target (moves unpredictably, never shoots).
        2 = fighter: turns onto the opponent when in view (limited turn speed, a little noise), fires when on
        target, picks rockets close / lightning mid / rail far, strafes, and wanders toward open space otherwise."""
        k = len(idx)
        s, rng = self.state, self.rng
        self.sc_t[idx] -= DT
        ch = idx[self.sc_t[idx] <= 0]
        if len(ch):
            self.sc_t[ch] = np.where(self.sc_persona[ch] == 4, rng.uniform(0.15, 0.5, len(ch)),
                                     rng.uniform(0.3, 1.2, len(ch)))          # the dodger changes direction fast
            self.sc_wpn[ch] = rng.choice([RL, RG, LG, SG, PG, MG], len(ch))
            self.sc_dir[ch] = rng.choice([-1, -1, 1, 1, 0], len(ch))
            self.sc_fwd[ch] = rng.choice([-1, 0, 0, 1], len(ch))
            self.sc_jump[ch] = rng.random(len(ch)) < 0.2
        if self.sc_style:                                   # test rooms: a fixed, repeatable target pattern
            ph = (self.round_t[idx // 2] / DT).astype(np.int64)
            if self.sc_style == 1:                           # still
                self.sc_dir[idx], self.sc_fwd[idx], self.sc_jump[idx] = 0, 0, False
            else:                                            # strafe left/right, switching every 0.8 s
                side = np.where((ph // 32) % 2 == 0, 1, -1)
                if self.sc_style == 2:                       # slow: moves one frame in three (~1/3 run speed)
                    side = np.where(ph % 3 == 0, side, 0)
                self.sc_dir[idx], self.sc_fwd[idx] = side, 0
                self.sc_jump[idx] = self.sc_style == 4
        fighter = self.script[idx] == 2
        opp = idx ^ 1
        eye = s[idx, :3] + np.array([0, 0, VIEW_H], np.float32)
        vis = self.visible[idx] & fighter
        tgt = np.where(vis[:, None], s[opp, :3], self.known[idx]) + np.array([0, 0, 4.0], np.float32)
        to = tgt - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - self.yaw[idx] + 180.0) % 360.0 - 180.0
        ep = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - self.pitch[idx]
        # wander: turn toward the most open direction in the front half
        ang = np.degrees(np.linspace(0, 2 * np.pi, N_WALL, endpoint=False))
        ang = (ang + 180.0) % 360.0 - 180.0
        score = self.walls[idx] + 0.3 * np.cos(np.radians(ang))[None, :] + rng.uniform(0, 0.1, (k, N_WALL))
        score[:, np.abs(ang) > 100] = -1.0
        wander = ang[score.argmax(1)]
        per = self.sc_persona[idx]
        rush = fighter & (per == 2) & (dist < 400)             # the rusher aims rockets at the feet
        ep = np.where(rush, -np.degrees(np.arctan2(to[:, 2] - 24.0, np.hypot(to[:, 0], to[:, 1]) + 1e-6))
                      - self.pitch[idx], ep)
        chase = fighter & (self.seen_t[idx] < 2.0)
        turn = np.where(vis | chase, np.clip(ey * P_GAIN[per], -10, 10), np.clip(wander * 0.15, -6, 6))
        turn = np.where(fighter, turn + rng.normal(0, 1.0, k) * P_NOISE[per], np.clip(wander * 0.1, -3, 3))
        if self.sc_style:
            turn = np.where(fighter, turn, 0.0)             # test-room targets keep their facing (straight strafes)
        dpit = np.where(vis, np.clip(ep * 0.4, -6, 6), -self.pitch[idx] * 0.2)
        out = np.zeros((k, len(ACTION_DIMS)), np.int64)
        ffwd = np.where(vis, np.where(dist > P_FAR[per], 1, np.where(dist < P_NEAR[per], -1, self.sc_fwd[idx])), 1)
        hurt = (per == 4) & (self.hp[idx] + self.armor[idx] < 80)
        ffwd = np.where(hurt & vis, -1, ffwd)                  # the dodger backs off when hurt
        ffwd = np.where(per == 5, 0, ffwd)                     # the stander does not move
        fside = np.where((per == 5) | (per == 6), 0, self.sc_dir[idx])
        fjump = np.where(per == 6, True, np.where(per == 5, False, self.sc_jump[idx]))
        out[:, 0] = np.where(fighter, ffwd, self.sc_fwd[idx]) + 1
        out[:, 1] = np.where(fighter, fside, self.sc_dir[idx]) + 1
        out[:, 2] = np.where(fighter, fjump, self.sc_jump[idx])
        out[:, 3] = np.abs(TURN[None, :] - turn[:, None]).argmin(1)
        out[:, 4] = np.abs(PITCH[None, :] - dpit[:, None]).argmin(1)
        am = self.ammo[idx]
        want = np.where((dist < 350) & (am[:, RL] > 0), RL, np.where((dist < 800) & (am[:, LG] > 0), LG,
                        np.where(am[:, RG] > 0, RG, np.where(am[:, MG] > 0, MG, G))))
        fixed = P_WEAPON[per]
        fx = np.maximum(fixed, 0)
        want = np.where((fixed >= 0) & (am[np.arange(k), fx] > 0), fx, want)
        want = np.where(fixed == -2, self.sc_wpn[idx], want)
        cur = self.weapon[idx]
        out[:, 6] = np.where(fighter & (want != cur) & self.has[idx, want], want + 1, 0)
        tol = np.where(cur == RL, 6.0, 2.5)
        out[:, 5] = (vis & (np.abs(ey) < tol) & (np.abs(ep) < 4.0)) | (fighter & (per == 7))   # the spammer always fires
        if self.lab is not None:
            t1 = self.script[idx] == 1
            z = self.lab_zone[idx // 2]
            pos = s[idx, :3]
            near = t1 & ~((z[:, 0] + 120 <= pos[:, 0]) & (pos[:, 0] <= z[:, 2] - 120) &
                          (z[:, 1] + 120 <= pos[:, 1]) & (pos[:, 1] <= z[:, 3] - 120))
            dx, dy = (z[:, 0] + z[:, 2]) / 2 - pos[:, 0], (z[:, 1] + z[:, 3]) / 2 - pos[:, 1]
            yr_ = np.radians(self.yaw[idx])
            f_, l_ = dx * np.cos(yr_) + dy * np.sin(yr_), -dx * np.sin(yr_) + dy * np.cos(yr_)
            out[:, 0] = np.where(near, np.sign(np.where(np.abs(f_) > 40, f_, 0)).astype(np.int64) + 1, out[:, 0])
            out[:, 1] = np.where(near, -np.sign(np.where(np.abs(l_) > 40, l_, 0)).astype(np.int64) + 1, out[:, 1])
            out[:, 2] = np.where(t1, self.lab_jump[idx // 2] & ~near, out[:, 2])   # no jumping while walking back in
            out[:, 3] = np.where(t1, int(np.abs(TURN).argmin()), out[:, 3])
        return out

    # ---------------------------------------------------------------- step
    def step(self, actions):
        a = np.array(actions, copy=True)
        n = self.n
        ar = np.arange(n)
        sc = np.nonzero(self.script > 0)[0]
        if len(sc):
            a[sc] = self._script_actions(sc)
        human = self.script == 0                            # policy-controlled players (for the statistics)
        pkind = np.repeat(self.kind, 2)
        key = np.where(a[:, 7] == 1, WALK, 127).astype(np.int32)   # walking: slower and silent
        fwd = (a[:, 0].astype(np.int32) - 1) * key
        side = (a[:, 1].astype(np.int32) - 1) * key
        jump = np.where(a[:, 2] == 1, 127, np.where(a[:, 2] == 2, -127, 0)).astype(np.int32)   # jump / crouch
        self.duck = (a[:, 2] == 2) & (self.hp > 0)
        fire = a[:, 5] == 1
        prev = self.state.copy()
        # mouse: the chosen turn speed is followed with a little inertia; jerky commands cost a little
        cmd = np.stack([TURN[a[:, 3]], PITCH[a[:, 4]]], 1)
        jerk = np.abs(cmd - self.cmd).sum(1)
        self.cmd = cmd
        sm = np.where(np.abs(cmd) <= 1.0, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH)   # small corrections follow faster
        self.mv = sm * self.mv + (1.0 - sm) * cmd
        if self.human_aim:
            self.mv[:, 0] = np.clip(self.mv[:, 0], -TURN_CAP, TURN_CAP)
            jit = self.rng.normal(0, 1, self.mv.shape).astype(np.float32) * (MOTOR_NOISE * np.abs(self.mv) + MOTOR_BASE)
            jit[self.script > 0] = 0.0
            turn, dpit = self.mv[:, 0] + jit[:, 0], self.mv[:, 1] + jit[:, 1]
        else:
            turn, dpit = self.mv[:, 0], self.mv[:, 1]
        # weapon switch (only to weapons owned)
        want = np.where(a[:, 6] == 0, self.weapon, a[:, 6].astype(np.int64) - 1)
        want = np.where(self.has[ar, want], want, self.weapon)
        sw = want != self.weapon
        self.weapon = want
        # as in the game: a weapon change only starts once the reload from the last shot is over
        self.cool = np.where(sw, np.maximum(self.cool, self.fire_cd + SWITCH), self.cool)
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw.copy()
        # the view eases back toward level, but not while an enemy is in sight (no pull against vertical aim)
        lev = np.where(self.seen_t > 0.5, self.level, 1.0)
        p1 = np.clip(self.pitch * lev + dpit, -89, 89)
        done_ms = 0
        for ms in self.substeps:
            done_ms += ms
            f = done_ms / 25.0
            self.w.step(moves, np.stack([self.pitch + (p1 - self.pitch) * f, y0 + turn * f], 1).astype(np.float32), ms)
        self.pitch = p1
        self.state = s = self.w.state()
        self.yaw = s[:, 7].copy()
        reward = -JERK_COST * jerk.astype(np.float32)
        self.snd_t += DT
        self._hear(2, np.nonzero((prev[:, 6] > 0.5) & (s[:, 6] < 0.5) & (s[:, 5] > 100))[0])      # jumps
        self._hear(3, np.nonzero(np.linalg.norm(s[:, :3] - prev[:, :3], axis=1) > 200)[0])       # teleports
        # fall damage (Quake 3 rule: from the speed of the landing)
        land = (prev[:, 6] < 0.5) & (s[:, 6] > 0.5)
        delta = prev[:, 5] ** 2 * 0.0001
        fall = np.where(land & (prev[:, 5] < 0), np.where(delta > FALL_FAR, 10.0, np.where(delta > FALL_MED, 5.0, 0.0)), 0.0)
        fallers = np.nonzero(fall > 0)[0]
        reward -= SWITCH_COST * sw
        blind = fire & (self.seen_t > 1.0) & (pkind != MOVE) & (pkind != COURSE)
        reward -= BLIND_FIRE_COST * blind
        fight = human & (pkind != MOVE) & (pkind != COURSE)
        self.stats["switches"] += int((sw & fight).sum())
        self.stats["fire_frames"] += int((fire & fight).sum())
        self.stats["blind_frames"] += int((blind & fight).sum())
        self.stats["play_frames"] += int(fight.sum())
        self.stats["duck_frames"] += int((self.duck & fight).sum())
        self.stats["walk_frames"] += int(((a[:, 7] == 1) & fight).sum())
        self.stats["bot_frames"] += int((self.script == 2).sum())
        np.add.at(self.stats["vs_persona"][2], self.sc_persona[self.script == 2], 1)
        self.stats["aim_round_frames"] += int((human & (pkind == AIM)).sum())
        # movement rounds: reward = seconds gained toward the goal (nav-graph time), like movement_env
        mi = np.nonzero(self.goal >= 0)[0]
        if len(mi):
            phi, _ = self.field.potential(self.goal[mi], s[mi, :3])
            reward[mi] += MOVE_SCALE * (np.clip(self.phi[mi] - phi, -0.5, 0.5) - DT)
            self.phi[mi] = phi
            gp = self.field.goals[self.goal[mi]]
            arrived = (np.hypot(gp[:, 0] - s[mi, 0], gp[:, 1] - s[mi, 1]) < 40) & (np.abs(gp[:, 2] - s[mi, 2]) < 64)
            sp = np.hypot(s[mi, 3], s[mi, 4])
            self.stats["move_frames"] += len(mi)
            self.stats["move_speed"] += float(sp.sum())
            self.stats["move_fast"] += int(((sp > 330) & (s[mi, 6] < 0.5)).sum())
            for i, v in zip(mi[arrived], sp[arrived]):
                reward[i] += MOVE_ARRIVE * (0.5 + min(1.5, float(v) / 320.0))   # arriving fast is worth more
                self.stats["move_arrive"] += 1
                self._new_goal(int(i))
        self.stats["jerk"] += float(jerk.sum())
        st = dict(dmg_taken=np.zeros(n, np.float32), attacker=np.full(n, -1), kill_w={}, kicked=False)
        for v in fallers:
            self._damage(int(v), float(fall[v]))
            self.stats["fall_dmg"] += float(fall[v])

        if self.courses and (self.course >= 0).any() and self._course_step(reward):
            self.state = s = self.w.state()
            self.yaw = s[:, 7].copy()
        # fire: a shot leaves one frame after the command
        self.cool = np.maximum(0.0, self.cool - DT)
        self.fire_cd = np.maximum(0.0, self.fire_cd - DT)
        do_fire, do_w = self.fire_q, self.fire_w
        ammo_ok = (self.ammo[ar, self.weapon] > 0) | (self.weapon == G)
        shoot = fire & (self.cool <= 1e-4) & ammo_ok & self.has[ar, self.weapon]
        self.cool = np.where(shoot, W_REFIRE[self.weapon], self.cool)
        self.fire_cd = np.where(shoot, W_REFIRE[self.weapon], self.fire_cd)
        if self.human_aim:                                  # nobody fires on the exact frame the reload ends
            slow = shoot & (W_REFIRE[self.weapon] >= 0.4) & (self.script == 0)
            self.cool = self.cool + slow * np.minimum(self.rng.exponential(RELOAD_JITTER, n), RELOAD_JITTER_MAX).astype(np.float32)
        reward -= FIRE_TOGGLE_COST * (fire != self.fire_prev)
        self.fire_prev = fire.copy()
        use = shoot & (self.weapon != G)                    # ammo is finite in every round kind
        if getattr(self, "inf_ammo", False):               # test-suite aim rooms: ammo never runs out
            use = use & False
        self.ammo[ar[use], self.weapon[use]] -= 1
        self.fire_q, self.fire_w = shoot, self.weapon.copy()
        self._hear(1, np.nonzero(shoot & (self.weapon != G))[0])
        if do_fire.any():
            yr, pr = np.radians(self.yaw), np.radians(self.pitch)
            fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1).astype(np.float32)
            eye = self._eye(s)
            for i in np.nonzero(do_fire)[0]:
                wpn = int(do_w[i])
                hm = int(self.script[i] == 0)               # statistics count policy players only
                kind = W_KIND[wpn]
                name = WEAPONS[wpn]
                v = i ^ 1
                if kind == "proj":
                    slot = np.nonzero(~self.ra[i])[0]
                    if len(slot):
                        k = slot[0]
                        self.rp[i, k] = eye[i] + fdir[i] * 14.0
                        self.rv[i, k] = fdir[i] * P_SPEED[wpn]
                        if wpn == GL:                       # Quake lofts grenades a little (forward z + 0.2)
                            d_ = fdir[i].copy()
                            d_[2] += 0.2
                            self.rv[i, k] = d_ / np.linalg.norm(d_) * P_SPEED[wpn]
                        # measured: rockets and grenades do not move on the frame they appear, plasma does
                        self.ra[i, k], self.rnew[i, k], self.rw[i, k], self.rage[i, k] = True, wpn != PG, wpn, 0.0
                        self.stats[name + "_shots"] += hm
                        self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                    continue
                if kind == "pellet":                        # shotgun: 20 pellets, gaussian spread; expected hits
                    self.stats[name + "_shots"] += hm * SG_PELLETS
                    self.stats[name + "_shots_vis"] += hm * SG_PELLETS * int(self.visible[i])
                    to = s[v, :3] + np.array([0, 0, 4.0], np.float32) - eye[i]
                    d = float(np.linalg.norm(to)) + 1e-6
                    if self.w.trace(eye[i], s[v, :3] + np.array([0, 0, 4.0], np.float32))["fraction"] < 0.999:
                        continue
                    hd = math.hypot(to[0], to[1]) + 1e-6
                    ex = math.degrees(((math.atan2(to[1], to[0]) - yr[i]) + math.pi) % (2 * math.pi) - math.pi)
                    eyv = math.degrees(-math.atan2(to[2], hd) - pr[i])
                    wx, wy = math.degrees(math.atan2(15.0, d)), math.degrees(math.atan2(28.0, d))
                    p = (_phi((wx - ex) / SG_SIGMA) - _phi((-wx - ex) / SG_SIGMA)) * \
                        (_phi((wy - eyv) / SG_SIGMA) - _phi((-wy - eyv) / SG_SIGMA))
                    hits = int(self.rng.binomial(SG_PELLETS, min(1.0, max(0.0, p))))
                    if hits:
                        self.stats[name + "_hits"] += hm * hits
                        self._hit(i, v, wpn, W_DMG[wpn] * hits, fdir[i], st)
                    continue
                rng_ = W_RANGE[wpn]                           # instant trace: rail, lightning, machine guns, gauntlet
                fr = self.w.rays_each(eye[i:i + 1], fdir[i:i + 1, None, :], rng_)[0, 0]
                end = eye[i] + fdir[i] * rng_ * fr
                self.stats[name + "_shots"] += hm
                self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                if bool(self._seg_box(eye[i:i + 1], end[None], s[v:v + 1, :3],
                                      np.where(self.duck[v:v + 1], TOP_DUCK, TOP))[0]):
                    self.stats[name + "_hits"] += hm
                    self._hit(i, v, wpn, W_DMG[wpn], fdir[i], st)

        # projectiles fly: direct hits on the opponent, explosions on walls, grenades bounce and time out
        fresh = self.rnew.copy()
        self.rnew[:] = False
        alive = np.nonzero(self.ra & ~fresh)
        if len(alive[0]):
            owner, slot = alive
            wp = self.rw[owner, slot]
            grav = np.where(wp == GL, 800.0, 0.0).astype(np.float32)
            self.rv[owner, slot, 2] -= grav * DT
            self.rage[owner, slot] += DT
            p0 = self.rp[owner, slot]
            vel = self.rv[owner, slot]
            step_len = np.linalg.norm(vel, axis=1) * DT + 1e-6
            p1r = p0 + vel * DT
            dirs = (p1r - p0) / step_len[:, None]
            fr = np.empty(len(owner), np.float32)
            for q in range(len(owner)):                     # per-projectile step length (speeds differ)
                fr[q] = self.w.rays_each(p0[q:q + 1], dirs[q:q + 1, None, :], float(step_len[q]))[0, 0]
            hitpt = p0 + (p1r - p0) * fr[:, None]
            opp = owner ^ 1
            direct = self._seg_box(p0, hitpt, s[opp, :3], np.where(self.duck[opp], TOP_DUCK, TOP))
            fuse = np.array([P_FUSE[int(x)] for x in wp], np.float32)
            timeout = (fuse > 0) & (self.rage[owner, slot] >= fuse)
            wall = fr < 1
            self.rp[owner, slot] = hitpt
            for q in range(len(owner)):
                i, k, wq = owner[q], slot[q], int(wp[q])
                if direct[q]:
                    self.ra[i, k] = False
                    self._explode(i, wq, hitpt[q], i ^ 1, dirs[q], s, st)
                elif timeout[q] or (wall[q] and wq != GL):
                    self.ra[i, k] = False
                    self._explode(i, wq, hitpt[q], None, None, s, st)
                elif wall[q]:                               # grenade bounce off the surface it hit
                    tr = self.w.trace(p0[q], p0[q] + dirs[q] * float(step_len[q]))
                    nrm = tr["normal"]
                    vq = self.rv[i, k]
                    vq = (vq - 2.0 * float(vq @ nrm) * nrm) * GL_BOUNCE
                    if nrm[2] > 0.2 and np.linalg.norm(vq) < 40:
                        vq[:] = 0.0                         # resting on the floor until the fuse runs out
                    self.rv[i, k] = vq
                    self.rp[i, k] = hitpt[q] + nrm * 0.5
        if st["kicked"]:
            self.state = s = self.w.state()                  # knockback changed velocities
        dmg_taken, attacker, kill_w = st["dmg_taken"], st["attacker"], st["kill_w"]

        # shaping (curriculum): reward damage dealt to the opponent
        opp_all = ar ^ 1
        dealt = np.where(attacker[opp_all] == ar, dmg_taken[opp_all], 0.0)
        taken = dmg_taken + fall                            # from the opponent, own splash and falls alike
        reward += self.dmg_reward * (dealt - DMG_TAKEN_W * taken)   # getting hurt costs more than hurting pays
        self.dmg_life += dealt
        hitby = (attacker >= 0) & (attacker != ar) & (dmg_taken > 0)
        ang = np.arctan2(s[opp_all, 1] - s[:, 1], s[opp_all, 0] - s[:, 0]) - np.radians(self.yaw)
        self.fb = np.stack([np.minimum(dealt / 100.0, 2.0), np.minimum(dmg_taken / 100.0, 2.0),
                            np.sin(ang) * hitby, np.cos(ang) * hitby], 1).astype(np.float32)

        # items: pickups, respawns, decay above 100
        self.item_t = np.maximum(0.0, self.item_t - DT)
        self.item_up |= self.item_t <= 0
        if self.nI:
            dxy = np.linalg.norm(s[:, None, :2] - self.item_pos[None, :, :2], axis=2)
            dz = np.abs(s[:, None, 2] - self.item_pos[None, :, 2])
            touch = (dxy < 36) & (dz < 56) & np.repeat(self.item_up, 2, axis=0) & (self.hp > 0)[:, None]
            for i, it in zip(*np.nonzero(touch)):
                m = i // 2
                if not self.item_up[m, it]:
                    continue                                  # the other player took it this frame
                kind, val, resp, cap, lab = self.item_def[it]
                took = False
                if self.kind[m] != NORMAL and kind in ("wp", "am", "pack"):
                    continue                                  # aim / drill / movement rounds: no weapons or ammo
                gain = 0.0
                if kind == "hp" and self.hp[i] < cap:
                    gain = min(cap, self.hp[i] + val) - self.hp[i]
                    self.hp[i] += gain
                    took = True
                    self.stats["pick_mega" if lab == "MH" else "pick_hp"] += 1
                elif kind == "ar" and self.armor[i] < cap:
                    gain = min(cap, self.armor[i] + val) - self.armor[i]
                    self.armor[i] += gain
                    took = True
                    self.stats["pick_ra" if lab == "RA" else "pick_ar"] += 1
                elif kind == "wp":
                    self.has[i, val] = True
                    self.ammo[i, val] = min(AMMO_MAX[val], self.ammo[i, val] + cap)
                    took = True
                    self.stats["pick_wp"] += 1
                elif kind == "am" and self.ammo[i, val] < AMMO_MAX[val]:
                    self.ammo[i, val] = min(AMMO_MAX[val], self.ammo[i, val] + cap)
                    took = True
                    self.stats["pick_am"] += 1
                elif kind == "pack" and (self.ammo[i] < AMMO_MAX).any():
                    self.ammo[i] = np.minimum(AMMO_MAX, self.ammo[i] + PACK_AMMO * self.has[i])
                    took = True
                    self.stats["pick_am"] += 1
                if took and (lab in ("MH", "RA", "YA", "GA") or kind == "wp"):
                    self._hear(0, np.array([i]), 0 if lab == "MH" else 1 if lab == "RA" else 2 if kind == "ar" else 3)
                if took:
                    reward[i] += self.item_reward * (gain if kind in ("hp", "ar") else 10.0) / 100.0
                    self.item_up[m, it] = False
                    self.item_t[m, it] = resp
        self.hp = np.where(self.hp > 100, np.maximum(100.0, self.hp - DT), self.hp)
        self.armor = np.where(self.armor > 100, np.maximum(100.0, self.armor - DT), self.armor)

        # deaths, frags, respawns
        done = np.zeros(n, bool)                            # end of the round (memory and returns reset here only)
        died = np.zeros(n, bool)
        events = []
        dead = np.nonzero(self.hp <= 0)[0]
        for v in dead:
            k = attacker[v]
            reward[v] -= 1.0
            died[v] = True
            if k >= 0 and k != v:
                reward[k] += 1.0
                self.frags_r[k] += 1
                self.stats["frags"] += 1
                self.stats[WEAPONS[kill_w.get(v, 0)] + "_frags"] += int(self.script[k] == 0)
                if self.script[v] == 2:
                    self.stats["frags_vs_bot"] += 1
                    self.stats["vs_persona"][0, self.sc_persona[v]] += 1
                elif self.script[v] == 1:
                    self.stats["target_kills"] += 1
                if self.script[k] == 2:
                    self.stats["bot_frags"] += 1
                    self.stats["vs_persona"][1, self.sc_persona[k]] += 1
            else:
                self.stats["suicides"] += 1
            events.append(dict(victim=int(v), killer=int(k), weapon=int(kill_w.get(v, -1))))
        for v in dead:
            if self.lab is not None:
                self._lab_respawn(int(v))
                continue
            self._spawn(int(v), avoid=s[v ^ 1, :3], close=True if self.kind[v // 2] == AIM else None)
            if self.goal[v] >= 0:
                self._new_goal(int(v))
        lo, hi = self.w.bounds()
        out = np.nonzero(s[:, 2] < lo[2] - 64)[0]            # fell out of the map: a suicide
        for v in out:
            if not died[v]:
                reward[v] -= 1.0
                died[v] = True
                self.stats["suicides"] += 1
                self._spawn(int(v), avoid=s[v ^ 1, :3])
                if self.goal[v] >= 0:
                    self._new_goal(int(v))
        # short rounds (curriculum): restart both players near each other every ~round_len seconds
        self.round_t += DT
        klen = np.where(self.kind == NORMAL, self.round_len, np.where(self.kind == MOVE, self.move_len, 15.0))
        if self.fixed_kind is not None:
            klen = np.full(self.M, self.round_len)
        ends = np.nonzero(self.round_t > klen * self.rng.uniform(0.67, 1.33, self.M))[0]
        if self.lab is not None:                            # lab rooms have exact lengths
            ends = np.nonzero(self.round_t >= np.where(self.kind == COURSE, self.course_len, self.lab_aim_len))[0]
        for m in ends:
            self.round_t[m] = 0.0
            a_, b_ = 2 * m, 2 * m + 1
            if self.lab is not None:
                self._lab_round(int(m))
                done[a_] = done[b_] = True
                continue
            # kind_p is the share of playing TIME per kind: normal rounds last much longer than the others, so
            # the chance of starting each kind is weighted by 1 / its length
            wts = np.asarray(self.kind_p, np.float64) / np.array([self.round_len, 15.0, 15.0, self.move_len])
            kd = int(self.rng.choice(4, p=wts / wts.sum()))
            if self.rng.random() < self.drill_p:            # older option: share of one-weapon rounds
                kd = DRILL
            if self.fixed_kind is not None:
                kd = self.fixed_kind[0]
            if kd == MOVE and self.field is None:
                kd = NORMAL
            self.kind[m] = kd
            self.mode[m] = -1
            self.script[a_] = self.script[b_] = 0
            self.goal[a_] = self.goal[b_] = -1
            if self.fixed_kind is not None:                 # test rooms decide who the odd player is
                self.script[b_] = self.fixed_kind[1]
                if kd == AIM:
                    self.mode[m] = int(self.rng.choice(self.aim_weapons))
                elif kd == DRILL:
                    self.mode[m] = int(self.rng.choice(self.drill_weapons))
            elif kd == DRILL:
                self.mode[m] = int(self.rng.choice(self.drill_weapons))
            elif kd == AIM:
                self.mode[m] = int(self.rng.choice(self.aim_weapons))
                self.script[b_] = 1
            elif kd == NORMAL and self.rng.random() < self.bot_p:
                self.script[b_] = 2
            if self.script[b_] == 2:
                self.sc_persona[b_] = self.persona_force if self.persona_force is not None else \
                    int(self.rng.choice(len(PERSONAS), p=self.persona_p))
            done[a_] = done[b_] = True
            self.load_sets[a_] = self.load_sets[b_] = None
            if kd == NORMAL and self.fixed_kind is None:
                u = self.rng.random()
                guns = [g for g in LOAD_GUNS if g in self.map_weapons and (self.sg_spawn or g != SG)]
                if u < self.loadout_p[0]:
                    for q in (a_, b_):
                        self.load_sets[q] = tuple(int(x) for x in self.rng.choice(guns, min(len(guns), int(self.rng.integers(1, 3))), replace=False))
                elif u < self.loadout_p[0] + self.loadout_p[1]:
                    self.load_sets[a_] = self.load_sets[b_] = ()
                elif u >= sum(self.loadout_p[:3]):              # the same single weapon for both (finite ammo)
                    dw = [g for g in self.drill_weapons if g in self.map_weapons or g == MG] or list(self.drill_weapons)
                    self.mode[m] = int(self.rng.choice(dw))
            self.frags_r[a_] = self.frags_r[b_] = 0
            self.snd_t[a_] = self.snd_t[b_] = 99.0
            if kd == AIM or (self.fixed_kind is not None and kd == NORMAL):
                # the target first, then the shooter close by, facing it
                self._spawn(b_, avoid=None)
                self._spawn(a_, avoid=self.w.state()[b_, :3], close=True)
            else:
                self._spawn(a_, avoid=None)
                self._spawn(b_, avoid=self.w.state()[a_, :3], close=0.0 if kd == MOVE else None)
            if kd == MOVE:
                self._new_goal(a_)
                self._new_goal(b_)
            self.item_up[m] = True
            self.item_t[m] = 0.0
        if len(dead) or len(out) or len(ends):
            self.state = s = self.w.state()

        # senses: sight (line of sight + field of view) and hearing (rough position)
        eye = self._eye(s)
        opp = ar ^ 1
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        yr, pr = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        infov = (to * fdir).sum(1) / dist > FOV_COS
        cand = np.nonzero(infov & (dist < 4000))[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = self._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        pkind = np.repeat(self.kind, 2)
        vis &= (pkind != MOVE) & (pkind != SOLO) & (pkind != COURSE)   # movement / solo / course: no other player
        self.visible = vis
        heard = (~vis) & (dist < HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250) & (pkind != MOVE) & (pkind != SOLO) & (pkind != COURSE)
        vh = np.nonzero(vis & (self.script == 0))[0]        # aim quality while the opponent is in view
        if len(vh):
            cosang = np.clip((to[vh] * fdir[vh]).sum(1) / dist[vh], -1, 1)
            self.stats["aim_err"] += float(np.degrees(np.arccos(cosang)).sum())
            self.stats["aim_frames"] += len(vh)
            self.stats["on_target"] += int(self._seg_box(eye[vh], eye[vh] + fdir[vh].astype(np.float32) * 4000.0,
                                                         s[opp[vh], :3],
                                                         np.where(self.duck[opp[vh]], TOP_DUCK, TOP)).sum())
            nv = vh[pkind[vh] == NORMAL]
            np.add.at(self.stats["w_dist"], (np.digitize(dist[nv], [300.0, 700.0]), self.weapon[nv]), 1)
        self.vis_run = np.where(vis, self.vis_run + 1, 0)
        acq = vis & (self.vis_run >= max(1, self.acquire_frames - self.react_frames))
        self.acquired = acq
        self.known[acq] = s[opp[acq], :3]
        if heard.any():
            self.known[heard] = s[opp[heard], :3] + self.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        self.seen_t = np.where(acq | heard, 0.0, self.seen_t + DT)
        self._teach_update()
        info = dict(events=events)
        return self.observe(), reward.astype(np.float32), done, info

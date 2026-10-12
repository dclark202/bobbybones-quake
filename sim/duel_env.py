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
import jump_links as JL  # noqa: E402

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
# Machine guns scatter (owner, 2026-10-07: "mg all game is garbage"; the simulator's had none, so at 50% hits it was a
# laser at any range). Each bullet leaves inside a cone of this half-angle, as in the Quake 3 source (spread 200 at
# 8192 units, radius uniform). NOT yet measured on a Quake Live server: to be checked with plugins/weaponlab.py.
MG_SPREAD = 1.4                                        # degrees; 0 = none (duel_env_v8 and older)
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
# Item runs (owner, 2026-10-07: "solo runs on the maps to learn where the things are", as people learn a map; RESULTS
# 2026-10-07 09:15: alone, with the intention fixed, he took the item in 0 to 29% of 30-second rounds). A share of the
# playing time (ITEM_RUN_P) he is alone on the map: the target is given to him as his intention (one of the big items
# that is lying there, drawn at random, the next one when he has it), he is paid for every second of the way gained,
# loses the same for every second that passes, and gets a bonus on taking it. The game's spawn, real pickups.
RUN_LEN, RUN_SCALE, RUN_ARRIVE = 60.0, 0.2, 0.5
# Collect, then fight (the second half of the owner's solo-run idea: "actually see the benefit of picking them up"): a
# share of the item runs (COLLECT_FIGHT_P) turns into a fight after RUN_COLLECT seconds. Half of the seats, drawn at
# random, are put back to a plain spawn; the others keep what they gathered. So he meets, from both sides, a fight
# that was decided by what was collected before it.
RUN_COLLECT = 20.0
# The weapon rule (owner, 2026-10-07: "rockets are probably the most used weapon in the game, he needs to be coaxed
# into using them"; he picked the launcher up nine times in three games against Nightmare and never fired it): what a
# plain player would hold at this distance from an enemy seen in the last 1.5 s, among the weapons he has with ammo:
# rockets from W_RULE_RL[0] to W_RULE_RL[1] units, lightning up to its range, the rail beyond, else the machine gun.
# A label for the trainer's --weapon-teach loss on the weapon key, like the intention seed; not a reward.
W_RULE_RL, W_RULE_LG, W_RULE_RG = (60.0, 300.0), 700.0, 500.0
W_RULE_RG_OK = 300.0   # owner (2026-10-07): lightning and rail overlap by a lot. The rail is the choice from 500 on, the lightning
                       # gun up to 700; with the lightning gun in hand up to 700, or the rail in hand from 300 on, he is left alone
# (the distances are people's: in 183 minutes of logged play, with every weapon to hand, the weapon fired most was
# rockets below 150 units (28%), lightning from 150 to 700 (28% rising to 64%, rockets 17% then 6%), the rail beyond
# 700 (40%); tools/player_card.py. The first guess was rockets 100 to 450, the rail beyond 600.)
N_GOAL = 7                                             # goal inputs: on, where (3), next waypoint (3)
# inputs added after duel_gru_v3 (appended at the end, so an older network can be widened without losing skills):
# clock and score 10, more items 8 x 6, sounds 20, map position and identity 6, view / up / long rays 28,
# enemy details 12, hit feedback 4, nearest teleporter and jump pad 11, crouched 1
# (2026-10-06, v8) Inputs that are always zero on arena1 were retired, to keep the network near 400 inputs: yellow
# and green armor and the heavy machine gun (as items, as weapons held, owned, with ammo, in the enemy's hands, in
# memory, as shot sounds), the third health, the ammo boxes, the map name, the 60 s clock, and the directions of the
# routes (the chosen route keeps its direction, see N_INTENT). They come back with the duel maps (BACKLOG B-101): a
# widening, as before. The shotgun, grenade launcher and plasma gun stay (owner, 12:50: he must know the game's main
# weapons on every map, whether this map has them or not).
OBS_W = np.arange(9)                                       # the weapons the inputs cover: all nine (HMG back for v9: 29 of the 62 maps have one)
N_XITEMS = 4
N_VIEW, N_UP, N_LONG = 15, 5, 8
N_EXTRA = 8 + 6 * N_XITEMS + 20 + 3 + (N_VIEW + N_UP + N_LONG) + (len(OBS_W) + 3) + 4 + 11 + 1
MAP_IDS = ("bloodrun", "aerowalk", "lostworld")       # third slot was campgrounds until 2026-10-04
HEAR_EVT = 1200.0                                      # item pickups, weapon fire, jumps, teleports are heard this far
                                                       # (not measured against the game)
VIEW_H_DUCK, TOP, TOP_DUCK = 12.0, 32.0, 16.0          # eye height and box top when crouched (Quake 3 values)
WALK = 64                                              # key strength when walking (silent: under the footstep speed)
# Finger limits (2026-10-05): the left hand as on a keyboard. Five fingers, each with its own keys:
#   ring = strafe left, middle = forward AND back (one finger: no direct reversal, it passes through "no key"),
#   index = strafe right AND the weapon keys, thumb = jump, little finger = crouch (and walk).
# A finger that has just acted cannot act again for FINGER_HOLD frames, and the whole hand has a budget of
# KEY_RATE key actions a second (a press and a release are one action each; a weapon switch is one action).
# The numbers come from how fast a hand taps, not from the demos: keys inferred from demos flicker too much.
RING, MIDDLE, INDEX, THUMB, LITTLE = range(5)
FINGER_HOLD = np.array([6, 6, 6, 4, 20], np.int64)     # frames: 150 ms, the thumb (jump) 100 ms, the little finger
                                                       # (crouch) 500 ms: at most one crouch a second
KEY_RATE, KEY_BURST = float(os.environ.get("KEY_RATE") or 4.0), 10.0     # (owner, 2026-10-08: 5 a second from v13 on; he asked for 6.8 and
#   got 3.8, and people sustain 6.8 over ten seconds at their 90th percentile: to be watched)
# (2026-10-05, later) The budget is the hand's stamina: a burst of up to KEY_BURST key actions in quick succession,
# refilled at KEY_RATE a second, so that after a burst the hand is slow until it has recovered.
# The left hand also decides only every KEY_EVERY frames (ten times a second): what the keys and the weapon choice
# should be is read from the network then and held in between. The mouse and the fire button stay at 40 a second.
KEY_EVERY = 4
# The right hand on the mouse: index finger = fire, middle finger = zoom (held). The same rule: a finger that has
# just acted cannot act again for this many frames (a click is a press and a release). Fire: 200 ms, so at most 2.5
# clicks a second (owner, 2026-10-07: "he is spamming the lightning fire button; you hold it down; 2 or 3 clicks a
# second max"; it was 100 ms, five clicks a second, until v10). FIRE_HOLD sets the frames.
MOUSE_HOLD = np.array([int(os.environ.get("FIRE_HOLD") or 7), 6], np.int64)   # fire 175 ms: 2.9 clicks a second (owner, 2026-10-08: "up the clicks to 3"; 8 frames in v11), zoom 150 ms
# Zoom: the view narrows to ZOOM of its size (100 x 75 degrees -> 40 x 30), and the same hand movement turns the
# view ZOOM as far: finer aim and less shake in degrees, but slower turning and no view of the surroundings.
ZOOM = 0.4
# Sight limits (2026-10-05): distances to walls, floor and ceiling are only known inside the field of view (about
# 100 x 75 degrees around where he is looking, pitch included). Outside it they read UNSEEN.
FOV_H, FOV_V = math.radians(50.0), math.radians(37.5)
UNSEEN = -1.0
VEL_REACT_FRAMES = 8                                   # the enemy's velocity is known 200 ms late
ITEMS_ROOM_REWARD = 0.5                                # per pickup in the lab map's items room
FALL_MED, FALL_FAR = 40.0, 60.0                        # Quake 3 fall damage: 5 above "medium", 10 above "far"
# scripted fighter styles, good and bad. Columns: turn gain, aim noise (deg), backs off below this distance,
# advances above this distance, fixed weapon (-1 = rockets close / lightning mid / rail far, -2 = random)
# The ninth, "nightmare", is a stand-in for the game's Nightmare bot in the simulator, for checks only (tools/duel_eval.py;
# never drawn in training: persona_p gives it no share, and the game's bots are a yardstick, not a teacher): the item
# runner (script 3) with the weapons the game's bot was logged to fire (692 minutes of sparring: shotgun 36%, rail 26%,
# rockets 15%, lightning 12%, machine gun 11%; the rail beyond 700 units), little jumping, and an aim whose noise
# (NM_NOISE, degrees a frame) is set so that its scores against v10 and v11 come out as the real bot's did.
PERSONAS = ("allround", "sniper", "rusher", "tracker", "dodger", "stander", "jumper", "spammer", "nightmare",
            "holder", "lobber", "watcher")
NIGHTMARE = 8
# The last three (owner, 2026-10-09; docs/SCOPE_v15.md A1) are item runners (script 3) that do to him what people do:
#   holder   takes the mega and the red armor on their clocks whatever he has, and comes for him after a frag (B-188)
#   lobber   grenades and plasma into the place he is about to come out of (B-189)
#   watcher  stands where his way to an item can be seen, with the rail (B-190)
# Never drawn unless persona_p gives them a share.
HOLDER, LOBBER, WATCHER = 9, 10, 11
HOLD_EARLY = 3.0                                          # the holder leaves for an item so as to be there this early
P_GAIN = np.array([0.4, 0.4, 0.4, 0.45, 0.4, 0.15, 0.3, 0.3, float(os.environ.get("NM_GAIN") or 0.4), 0.4, 0.4, 0.4], np.float32)
P_NOISE = np.array([0.3, 0.3, 0.5, 0.3, 0.3, 0.6, 1.5, 1.5, float(os.environ.get("NM_NOISE") or 0.6),
                    float(os.environ.get("NM_NOISE") or 0.6), 0.5, 0.3], np.float32)
P_NEAR = np.array([200, 700, 0, 250, 300, 0, 0, 200, 150, 150, 300, 700], np.float32)
P_FAR = np.array([500, 1200, 0, 550, 600, 1e9, 0, 500, 600, 600, 700, 1200], np.float32)
P_WEAPON = np.array([-1, RG, RL, LG, -1, -1, -1, -2, -3, -1, -1, RG], np.int64)
NM_WEAPONS, NM_WEIGHTS = np.array([SG, RG, RL, LG, MG], np.int64), np.array([0.36, 0.26, 0.15, 0.12, 0.11])
# ---- Aim ability: one knob (owner, 2026-10-08: "on par or slightly above me, 10% over or so ... this will likely be
# turned into a parameter 'aim ability' with this as the baseline 3/5, a knob that can be tuned up or down").
# AIM_LEVEL 1 to 5 (fractions allowed), 3 by default. Level 3 is set from the owner's reflex-room runs and the logged
# games (docs/RESULTS.md 2026-10-08, aim audit): with these limits the network of that day tracked a strafing target
# 44% of the time (the owner 40%) and under fire 26% (20%), and noticed an enemy as fast as he does in the room.
# Each level is AIM_STEP times the errors and delays of the level above it (a first spacing: to be fitted to the
# spread of people's play as more of it is logged). What a level sets:
#   percept_sigma / tau / speed   the error in where he sees the enemy (degrees; how long it lingers; more per deg/s)
#   react_ms, acquire_ms          tracking delay on an enemy in view; delay before one who has just appeared is noticed
#   surprise_ms                   up to this much more before he is noticed when he turns up off the crosshair (nothing
#                                 within 10 degrees, all of it from 40 on) and unexpected (half if seen or heard in the
#                                 last 2 s): in real games people fire 0.5 s after an enemy appears, he fired after 0.2
#   flinch per damage / max / tau how far a hit throws his aim off, and for how long (the owner keeps half of his
#                                 tracking under fire; with the first values he kept 78%)
#   motor_noise / motor_base      hand noise
# AIM_PRESET=v12 or v10 gives the limits those networks were trained under (for checks of old networks). Any single
# value can still be set by its own environment variable (PERCEPT_SIGMA, FLINCH_PER_DMG, SURPRISE_MS, ...).
AIM_STEP = 1.25


def aim_settings(level=3.0, preset=""):
    f = AIM_STEP ** (3.0 - float(level))
    a = dict(level=float(level), percept_sigma=0.6 * f, percept_tau=0.15, percept_speed=0.0, react_ms=100.0 * f,
             acquire_ms=200.0 * f, surprise_ms=200.0 * f, flinch_per_dmg=0.25 * f, flinch_max=6.0 * min(f, 1.6),
             flinch_tau=0.5, motor_noise=0.10 * f, motor_base=0.05 * f)
    if preset in ("v12", "v11"):
        a.update(percept_sigma=1.2, percept_tau=0.5, percept_speed=0.012, react_ms=75.0, acquire_ms=200.0, surprise_ms=0.0,
                 flinch_per_dmg=0.12, flinch_max=3.0, flinch_tau=0.3, motor_noise=0.10, motor_base=0.05)
    elif preset == "v10":
        a.update(percept_sigma=0.6, percept_tau=0.15, percept_speed=0.0, react_ms=75.0, acquire_ms=200.0, surprise_ms=0.0,
                 flinch_per_dmg=0.12, flinch_max=3.0, flinch_tau=0.3, motor_noise=0.10, motor_base=0.05)
    return a


AIM_SET = aim_settings(os.environ.get("AIM_LEVEL") or 3.0, os.environ.get("AIM_PRESET") or "")   # (not "AIM": that is a round kind)


def _aim(var, key):
    return float(os.environ[var]) if os.environ.get(var) else float(AIM_SET[key])


REACT_FRAMES = 2                                       # 50 ms: tracking an enemy already in view lags by this much.
ACQUIRE_FRAMES = 8                                     # 200 ms: an enemy who has just come into view is not reacted to before this
# SEAT_DELAYS (2026-10-12, B-226): the two delays above are one number for every seat of a simulator (env.react_frames,
# env.acquire_frames: the trainer's --react-ms and --acquire-ms), or, in a check that seats two networks trained with
# different delays, one a seat: env.react_seat / env.acquire_seat (whole-number arrays, a number a seat; None: the one
# number). With them set, react_frames and acquire_frames must be the largest of the seats' (the lengths of the kept
# history go by them); sim/test_suite.py's set_delays() does it. In a group of more than two the block of the other
# enemies in view (_ffa) takes the largest delay for every seat.
SEAT_DELAYS = True
TURN_CAP = 30.0                                        # fastest flick, degrees per frame (1200 deg/s)
MOTOR_NOISE, MOTOR_BASE = _aim("MOTOR_NOISE", "motor_noise"), _aim("MOTOR_BASE", "motor_base")   # (0.10, 0.05 at level 3) hand noise: this share of the view movement, plus a little, per frame (0.14 until 2026-10-06 evening, owner: tune up)
RELOAD_JITTER, RELOAD_JITTER_MAX = 0.05, 0.12          # slow weapons: random extra delay after the reload (mean, max seconds)
DMG_TAKEN_W = 2.0                                      # damage taken (any source) weighs this much against damage dealt
FIRE_TOGGLE_COST = 0.003                               # reward cost each time the fire button changes (holding is free)
LOAD_GUNS = (0, 1, 2, 4, 5, 6, 7)                      # weapons that random loadouts draw from (all but machine gun, gauntlet)
#                                                       older note: default 25 ms (one frame): what a player knows about the opponent lags.
                                                       # Was 6 (150 ms) up to duel_gru_v2; per run: env.react_frames / --react-ms
# (2026-10-05) He reads where the enemy is against his crosshair only this well: a slowly drifting error, in degrees,
# on the direction to an enemy in view (every input that gives that direction carries it). A person judges the
# gap between crosshair and target by eye, not to a hundredth of a degree.
PERCEPT_SIGMA, PERCEPT_TAU = _aim("PERCEPT_SIGMA", "percept_sigma"), _aim("PERCEPT_TAU", "percept_tau")   # (by the aim level since 2026-10-08; 1.2, 0.5 in v11 and v12)
# degrees; seconds over which the error drifts. 2026-10-06 evening 1.0 -> 0.6 after the reflex room (he was wider than the owner
# there). 2026-10-07 evening the owner asks for LESS hitscan aim: in real games he is on target 56% of the time an enemy is in view
# (people 23%, Nightmare 27%) and 2.1 degrees off while firing (people 3.2): the reflex room flatters people. What makes a
# person's aim worse in play than in the room is not reaction: it is a slow, wandering offset (he "thinks" the enemy is a little
# off for half a second, not for a frame) that grows with how fast the target crosses his view. So for v11 (set by the launch
# file): a larger error that drifts slowly (PERCEPT_TAU 0.5: the memory cannot average it away as it does the 0.15 s one) and
# PERCEPT_SPEED degrees more for every degree a second the enemy's direction moves, at most PERCEPT_SPEED_MAX.
PERCEPT_SPEED, PERCEPT_SPEED_MAX = _aim("PERCEPT_SPEED", "percept_speed"), 3.0
# Values since 2026-10-07 20:15 (the first "click", owner: "nudge hitscan aim down 1-2 clicks"): 1.2 degrees, 0.5 s, 0.012.
# v10 under them in the reflex room, not yet adapted: error on a strafing target 3.0 -> 3.8 degrees (the owner 2.45), time on
# it 58% -> 54% (40%), lightning damage a second 83 -> 75 (58), first rail shot on a jumping target 74% -> 65% (88%).
# The second click, measured and kept ready: 1.6 / 0.6 / 0.02 -> 5.2 degrees, 44%, 67, 57%. Before: 0.6 / 0.15 / 0.
# (2026-10-05, B-94) Being shot at costs aim: a hit throws his read of the enemy's direction off by FLINCH_PER_DMG
# degrees per point of damage (at most FLINCH_MAX at a time), and the error stays larger while the flinch fades
# (FLINCH_TAU seconds). First values; to be set from players in the reflex test (calm half against the half under fire).
FLINCH_PER_DMG, FLINCH_MAX, FLINCH_TAU = _aim("FLINCH_PER_DMG", "flinch_per_dmg"), _aim("FLINCH_MAX", "flinch_max"), _aim("FLINCH_TAU", "flinch_tau")   # (0.12, 3.0, 0.3 until v12)
SURPRISE_MS = _aim("SURPRISE_MS", "surprise_ms")


def surprise_frames(ecc, seen_t):
    """frames more before an enemy who comes into view is noticed: by how far off the crosshair he is (degrees) and by
    whether he was seen or heard in the last two seconds (see the aim ability above)"""
    return np.rint(SURPRISE_MS * np.clip((ecc - 10.0) / 30.0, 0.0, 1.0) * np.where(seen_t < 2.0, 0.5, 1.0) / 25.0).astype(np.int64)
# (2026-10-05, B-93) The tracking delay is an average, not a floor: with an enemy in view he is sharper for a short
# spell (FOCUS_GAIN frames quicker) while his focus lasts, then slower than the average (FOCUS_LOSS frames) until
# it has come back. Focus runs down at one second a second with an enemy in view and comes back at FOCUS_REFILL.
FOCUS_SECS, FOCUS_REFILL, FOCUS_GAIN, FOCUS_LOSS = 2.0, 0.25, 2, 1
MOUSE_SMOOTH = 0.75                                    # view velocity inertia per frame
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
# Intention (2026-10-06, v8): an explicit choice of what to go for, read once a second (INTENT_EVERY frames, staggered
# by player) and held in between: nothing, the mega, the red armor, the rocket launcher, the railgun, the lightning
# gun. Changing it costs INTENT_SWITCH. Travel toward the chosen item pays (env.intent_seek per second of the way
# gained, while the item is up or comes up before he gets there), taking it pays env.item_reward. The choice is an
# input back to him, with the way to it, so "follow the arrow" is easy and "which arrow" is the decision.
INTENTS = ("none", "MH", "RA", "RL", "RG", "LG", "YA", "YA2", "EN",   # (v13: the yellow armors, up to two a map; the pros take them most of all)
           "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8")                # (TARGETS: the map's holding places, see below)
# "EN" (FIGHT_TARGET; owner, 2026-10-11: "'fight' is a target"): the enemy. Until then every target was an item, so his
# legs could carry him only to an item, which mostly means away from a fight: with more than 125 health and armor he
# closed on an enemy in view at 60 to 80 units a second, a stroll. With the enemy as his intention his way leads to the
# route goal nearest (in seconds of way) to where he believes the enemy is, his legs take it as any other way, and the
# intention is reached when the enemy is in view. A believed place older than EN_KNOWN seconds is no target. Nothing is
# paid for the way there: it pays by what the fight brings. With the switch off the choice counts as "none".
EN_INTENT = 8
FIGHT_TARGET = float(os.environ.get("FIGHT_TARGET") or 0.0) > 0
EN_KNOWN = float(os.environ.get("EN_KNOWN") or 20.0)
N_EN = 1                                                   # one more input (the last): his intention is the enemy
# TARGETS (stage B part 2, docs/design/V02_STAGE_B.md; owner, 2026-10-11: "Yes"): a target that is never "nothing". Measured
# that day: with no item due his intention is "nothing", his legs have nowhere to go, and he stands on his own feet at
# 270 units a second for 13 to 23% of his time, in odd places. "H1" to "H8" are the map's holding places: the eight
# places of sim/pro_holds/<map>.json (tools/pro_holds.py: where the pros hold longest and fare best), in the file's
# order; a map without the file, or with fewer places, has no such choice (it counts as "nothing"), and so does every
# place with the switch off. A place as his intention: his way leads to it (rows of the route field of their own, the
# walking map's ways; with jumps open in games, those too), his legs carry him there as to an item, the inputs "his
# way" show it as they show an item's. It is reached when he stands within HOLD_R units of it (and HOLD_Z in height):
# from then on he may choose anew at every reading, as after a pickup, but it stays his target for as long as he chooses
# it, and his legs do nothing while he stands there (he holds it on his own feet; they carry him back when he has left
# it). Before he has reached it the choice holds as an item's does (INTENT_HOLD), unless TARGETS_FREE=1: then a place
# can be left at any reading, as "nothing" can. Nothing is paid for it: no pay for the way, none for speed on it, no
# pay for being there, and leaving it costs nothing (INTENT_SWITCH is not charged). In an item run or a jump run the
# target is given, so a place is never one there. The item rule's lesson (intent_teach, the intention's teacher): where
# the rule names no item its label is -1 with the switch on, and the trainer leaves such a frame out, so that what he
# does with no item due is his own (it taught "nothing" there); the lesson is about which item among the items, so the
# trainer also takes the places out of its sum, as the enemy.
# A game server's plugin, which does not call step(): note_holds() every frame (the place reached).
HOLD_INTENT, HOLD_SLOTS = 9, 8                             # the first place among the intentions; how many
TARGETS = float(os.environ.get("TARGETS") or 0.0) > 0
TARGETS_FREE = float(os.environ.get("TARGETS_FREE") or 0.0) > 0
HOLD_R, HOLD_Z = 96.0, 64.0
assert INTENTS[HOLD_INTENT] == "H1" and len(INTENTS) == HOLD_INTENT + HOLD_SLOTS
# WAYS (stage B part 3, docs/design/V02_STAGE_B.md; owner, 2026-10-11: "Yes"; his "main failure point is that their routes are
# predictable"): several ways to a target. Until now there was one way to each target, the shortest, and his legs took it
# every time. With the switch on every target (an item; with TARGETS a holding place) has up to two more sets of ways
# beside the shortest, "the shortest way that follows the pros' second and third ways where they exist" (sim/ways.py
# says how they are made from sim/pro_ways/<map>.json: a way of the pros that the walking map can follow from its
# origin and that is not the shortest; where there is none, or it would cost more than WAY_CAP (1.5) times the shortest
# from where he stands, the set's way is the shortest; every set arrives from everywhere). Only ways that his legs were
# measured to make are taken (sim/pro_ways_legs/<map>.json, written by tools/ways_check.py with the movement network
# that is his legs: make it again when that network or the walking map changes); a map without the file has no second
# or third ways. WAY_UNTESTED=1 takes the ways that were never measured too (the tool's own passes, and checks).
#   The choice: one more output, the last (WAY_HEAD; N_WAYS choices: the shortest, the second, the third), read on the
# frames the intention is read and only on them (intend(): its tick, and INTENT_HOLD holds both), and held between.
# So the way is chosen with the target; at a later reading he may keep the target and change the way, which is no
# change of intention: nothing is charged (INTENT_SWITCH), nothing given back, the trip and its seconds go on (and
# INTENT_HOLD, which counts from the target's choice, does not start again). In an item run or a jump run the way is
# the shortest. A scripted player's way is the shortest.
#   What follows the way: the inputs "his way" (seconds to go, the next step: _intent), his legs (the movement
# network is shown that set's steps and seconds: copies of its own field made the same way, _move_ways), the trip's pay
# and what is counted on it (speed on his way; "the item comes back in time"). The item rule, the ways to the items
# as inputs (N_ROUTE), the way to a holding place as an input (N_B2) and which of two items of a kind is "nearest"
# stay the shortest set's.
#   The pay: nothing is paid for a way as such; a trip pays what it paid, at most its item, whichever way. The trip's
# count is "the least seconds to go so far" on the set he is on, as a share of that set's whole way at the moment the
# target was chosen (way_phi0, kept for all three). Where he changes the way alone, the share already paid goes over
# to the new set's scale (best = best x new whole way / old whole way), and where the new set has him further along
# than that share, the difference is forfeited, not paid (best = the least of that and the seconds to go now). So
# what a trip has paid is a running best over everything he has been through on the way he was on at the time: going
# back and forth between two places while flipping the way pays nothing after the first time (2026-10-08's rule: pay
# for progress on a running best), and a player who flips earns at most what the best of the three ways would have
# paid him over the same path.
#   WAY_MEASURE (on with WAYS; may be set alone, to measure a network without ways): his trips between two places
# (from his pickup of one route item to his next pickup of another in the same life, WT_MIN_S to WT_MAX_S seconds, in
# games) are kept as 16 points along the path (env.way_trips: this step's, [from, to, 48 numbers]) for the trainer's
# measure "of his trips between the same two places, the share on the commonest way" (the pros 43%, v0.1 57%).
# Changes nothing he does.
#   The last N_B3 inputs (zeros with the switch off): his way now (N_WAYS flags), how much longer the second and the
# third way to his target are than the shortest from where he stands (seconds / B3_LONGER, capped at 1), and whether each
# differs from the shortest from here (more than a quarter of its seconds farther than 128 units from the shortest way).
#   A game server's plugin: intend(choice, who, way) with the network's thirteenth output; nothing else (step() is not
# needed for the inputs: _intent() and _b3() read the sets directly).
WAYS = float(os.environ.get("WAYS") or 0.0) > 0
WAY_UNTESTED = float(os.environ.get("WAY_UNTESTED") or 0.0) > 0
WAY_MEASURE = WAYS or float(os.environ.get("WAY_MEASURE") or 0.0) > 0
WAY_HEAD, N_WAYS = 12, 3
N_B3, B3_LONGER = N_WAYS + 2 * (N_WAYS - 1), 5.0
WT_EVERY, WT_MAX, WT_MIN_S, WT_MAX_S = 4, 202, 1.0, 20.0   # a trip's path: a point every WT_EVERY frames, at most WT_MAX; the trips that count
INTENT_EVERY, INTENT_SWITCH = 40, 0.02
# (12:50) A choice holds for INTENT_HOLD seconds unless the item was taken or he died ("none" can be left at any read);
# the way to the chosen item is worth its pickup (INTENT_VALUE x env.item_reward), paid in parts as the way is gained,
# so a whole trip never pays more than the item itself.
# Pay for keeping a stack (owner, 2026-10-07: "good players maintain stack; bad players spawn and immediately start
# fighting"). Paid every second of a normal game while alive, in frags a minute at full value: STACK_PAY for health
# above 100 and armor (each counted to 100, half each), STACK_WPN for the big weapons in hand (rockets, lightning, rail:
# a third each). Costs: STACK_BARE while he holds none of the three, growing with the time he has gone without (nothing
# at the spawn, the full rate after STACK_BARE_RAMP seconds, on up to STACK_BARE_MAX times it); STACK_LOW while health
# and armor together are under STACK_LOW_AT (one rail shot kills), in proportion to how far under. All zero by default.
STACK_PAY = float(os.environ.get("STACK_PAY") or 0.0)
STACK_WPN = float(os.environ.get("STACK_WPN") or 0.0)
STACK_BARE = float(os.environ.get("STACK_BARE") or 0.0)
STACK_LOW = float(os.environ.get("STACK_LOW") or 0.0)
STACK_BARE_RAMP, STACK_BARE_MAX, STACK_LOW_AT = 5.0, 4.0, 70.0
# The walking teacher inside normal games (the fallback of 2026-10-07, off by default): while he holds none of the big
# weapons or is under STACK_LOW_AT, and no enemy is in view, the keys that walk to what the item rule names (intent_rule)
# are the labels of the trainer's teacher loss (--teach, fading), as in the item runs of v10.
STACK_TEACH = float(os.environ.get("STACK_TEACH") or 0.0) > 0
# Playing styles (owner, 2026-10-08: "some people do genuinely have a preference for weapons"): every life he is in one of
# four states, given to him as four inputs: general, or a preferred weapon (rockets, rail, lightning). With a preferred
# weapon he is pushed to fetch it first (the item rule names it), to hold it whenever he has it (the weapon teacher names
# it at every distance), to hurt with it (damage with it pays STYLE_DMG more) and to fight at its distance (STYLE_BAND
# frags a minute while the enemy is in view inside the band with it in hand). STYLE_P = the share of lives with a
# preferred weapon, split evenly; 0 = always general. Who chooses the state is a later step: here it is drawn.
STYLES = ("general", "rockets", "rail", "lightning")
STYLE_W = np.array([-1, RL, RG, LG], np.int64)
STYLE_LO = np.array([0.0, 60.0, 500.0, 150.0], np.float32)
STYLE_HI = np.array([0.0, 300.0, 1e9, 700.0], np.float32)
STYLE_P = float(os.environ.get("STYLE_P") or 0.0)
# STYLE_MIX (2026-10-12, the owner's decision 1 of docs/runs/PROPOSAL_v0.2.1.md; a PLAY_VAR, because the game servers draw
# a life's style too): the draw of his lives, e.g. "rockets:0.40,lightning:0.15,rail:0.10" = the share of ALL lives for
# each style named, the rest general (a style not named: no such lives; "general" may be named and must then be the
# rest). It replaces STYLE_P's even split. How the two combine: STYLE_P above 0 is still what turns styles on in this
# simulator (the draw in _fresh, the extra pay, the counters, the teachers' labels) and its size no longer sets any
# share; with STYLE_P at 0 nothing is drawn here whatever the mix says. Unset: today's draw.
# The main random stream moves exactly as it does without the mix (one number a life, and the even split's second
# number whenever the first is under STYLE_P: drawn and not used), so a fixed run with the mix set stays in step with
# the same run without it and differs only by what a style changes. A rail life on a map without a railgun is a
# general life, as ever. The plugins draw for themselves (they never call _fresh): style_draw() is theirs to call.


def style_mix(text):
    """ "rockets:0.40,lightning:0.15,rail:0.10" -> the running sums of the shares of STYLES[1:], in that order (None: no mix)"""
    if not (text or "").strip():
        return None
    sh = {}
    for part in text.split(","):
        k_, v_ = part.split(":")
        k_ = k_.strip()
        assert k_ in STYLES and k_ not in sh, "STYLE_MIX: '{}' is not one of {} or is named twice".format(k_, STYLES)
        sh[k_] = float(v_)
        assert sh[k_] >= 0.0, "STYLE_MIX: a share below nothing"
    tot = sum(v_ for k_, v_ in sh.items() if k_ != STYLES[0])
    assert tot <= 1.0 + 1e-9, "STYLE_MIX: the styles' shares add up to {:g}, more than all lives".format(tot)
    assert STYLES[0] not in sh or abs(sh[STYLES[0]] - (1.0 - tot)) < 1e-6, "STYLE_MIX: 'general' is the rest ({:g}), not {:g}".format(1.0 - tot, sh[STYLES[0]])
    return np.cumsum([sh.get(k_, 0.0) for k_ in STYLES[1:]])


STYLE_CUM = style_mix(os.environ.get("STYLE_MIX") or "")


def style_draw(u, cum=None):
    """(STYLE_MIX) the style of a life from one number u in [0, 1): rockets under the first running sum, rail under the
    second, lightning under the third, general above. (The simulator then makes a rail life general on a map without a
    railgun; a plugin that calls this does the same.)"""
    return (int(np.searchsorted(STYLE_CUM if cum is None else cum, u, side="right")) + 1) % len(STYLES)


# Seeds from the pro demos (owner, 2026-10-08; docs/PLAN.md "seeding his behavior from the pro demos"), off by default:
#   PRO_WEAPON=1    the weapon teacher names the pros' first choice for the distance among the big weapons he owns
#                   (sim/pro_seed.json, written from docs/pro_tables.json: per map, else all maps together); holding one
#                   within PRO_WEAPON_TIE of the first choice is left alone. Replaces the hand-set distances (W_RULE_*).
#   SPAWN_TEACH=1   the keys-only walking teacher (STACK_TEACH) also with an enemy in view while he holds no big weapon:
#                   the pros have one 2.7 s after a spawn and fight half as much without (the view stays his own).
PRO_WEAPON = float(os.environ.get("PRO_WEAPON") or 0.0) > 0
PRO_WEAPON_TIE = 0.10
SPAWN_TEACH = float(os.environ.get("SPAWN_TEACH") or 0.0) > 0
# The pros' weapon in hand with nobody in view, as a small standing pull (2026-10-12; change 7 of
# docs/runs/PROPOSAL_v0.2.1.md, the owner's decision 3). The pros put the humming weapons away when the enemy is out of
# sight (rail or lightning in hand 28% of their travelling time when he was seen under 5 s ago, 9% when over 15 s ago) and
# hold a spot on rockets (82%); he had rail or lightning in hand 61% and 73%, rockets 15% (docs/pro_yardsticks2.json,
# docs/bobby_yardsticks_v02m04272.json: weapon_in_hand). The table: sim/pro_hand.json (tools/pro_hand.py), per map, by
# state (travelling, holding) and by how long ago the enemy was in view, every weapon's share of the pros' time.
#   HAND_TEACH=1  step() gives info["hand_lab"]: per player a target over the choices of his weapon output (float32
#                 [players, 1 + weapons]; zeros = no label) for his NEXT reading of it, for the trainer's --hand-teach
#                 (cross-entropy on the frames his hand reads the weapon key). A training switch: not a PLAY_VAR, nothing
#                 of it is in the inputs or on a server.
#       A label is there when: the seat is a network's (not a scripted player's), he is alive, the round is a game (a normal
#       round on a duel map: no item run, no jump run, no one-weapon round, no aim round, not the test map), no enemy has
#       been in his view for HAND_OUT_F frames (1 s) or more, he has seen one in this round (until then the pros' row is
#       the opening of a game, when they own little: the lesson is silent), and he owns with ammunition at least two of
#       the weapons his row names.
#       In view: the enemy inside his sight cone under 4000 units with a clear line (self.visible; in a group any other
#       member), as tools/pro_yardsticks.py's see(): the fact, not what he has noticed. NOT seen_t, which a sound resets.
#       The row: his map's (sim/pro_hand.json: the ten maps' together where the map has too little of its own), by
#         state  holding: as the pros' tool counts a hold as nearly as a simulator can: he has stayed within HAND_HOLD_R
#                (150) units of where the stretch began for HAND_HOLD_F frames (2 s) or more, alive, nobody in view, rockets,
#                lightning or rail in hand all the while. (The tool marks a hold from its first frame, by hindsight; a label
#                cannot: here it begins when the two seconds are up. The pros' holds last 2.6 s at the median, so a hold's
#                row is on few frames. Little is lost: among the three big weapons the two rows are nearly the same, rockets
#                64 / 83 / 88% of them travelling and 71 / 86 / 92% holding by band; a hold's row only names no small weapon.)
#                Every other labelled frame takes the travelling row, also under 200 units a second (the tool counts
#                travelling at 200 or more: the counters below keep that apart).
#         band   frames since an enemy was last in view: under 5 s, 5 to 15 s, over 15 s. Not reset by his death (the
#                tool's is not); a new round begins with nobody seen.
#       The target: the row's shares of the weapons he owns with ammunition, made to sum to 1 (a weapon he lacks is
#       never named), in the weapon output's own choices as _weapon_teach writes a wanted weapon: choice w + 1 for
#       weapon w, and the share of the weapon already in his hand on choice 0, "keep".
#       HAND_TEACH_REDRAW (seconds, default 4; 0 = at every reading): the shares are of the pros' TIME. Given as the
#       target of every reading (ten a second) they would have him draw his weapon afresh ten times a second: from
#       rockets to something else at half of all readings while travelling. So the target is "keep" with chance 1 - L and
#       a fresh draw from the shares with chance L = (KEY_EVERY frames) / (HAND_TEACH_REDRAW seconds): followed to the
#       letter that is still the pros' shares of his time, with a change of weapon every few seconds and not every tenth.
#       How often: with the enemy out of view the pros' weapon is another within a second 19.7% of the time, within two
#       33.9% (docs/pro_yardsticks2.json, sounds -> baseline): a change every 4.7 s. He: 4.0% and 8.0%, a change every
#       24 s. The target followed to the letter changes about every 2 x REDRAW seconds (a fresh draw is the same weapon
#       about half the time): every 8 s at the default, the pros' own rate at about 2.5.
#   HAND_TEACH_GENERAL=1  the label in general lives only (STYLES: not in a rockets, rail or lightning life). Unset, a
#                 styled life is labelled as a general one: a lightning life is then pulled to rockets while nobody is in
#                 view and has to change when the fight begins.
# Always on, whatever the switches (stats; the seats count_even counts, alive, in a game):
#   qhand      [state, band, weapon] frames with nobody in view for 1 s or more, by the weapon in his hand. States as the
#              pros' tool: 0 travelling (200 units a second or more, not in a hold), 1 holding, 2 neither; a hold from its
#              first frame, as the tool has it: a frame is counted HAND_HOLD_F frames after it was played, when it is known
#              whether its stretch became a hold (a simulator's last two seconds are never counted). Bands: under 5 s, 5 to
#              15 s, over 15 s, nobody seen yet in this round.
#   qhand_meet [weapon] the weapon in his hand on the frame an enemy comes into view after 1 s or more out of it
#   qhand_sw   changes of the weapon in his hand on the frames of qhand (his key, a pickup's, the game's on an empty
#              weapon; not a death's), and those frames
#   qhand_on   [row, band, weapon] his hand on the frames the lesson would label (all conditions but the switches)
#   qhand_pro  [row, band, weapon] ... and the sum of the pros' shares for what he owned there: beside qhand_on, how far
#              his hand is from the lesson's
HAND_TEACH = float(os.environ.get("HAND_TEACH") or 0.0) > 0
HAND_TEACH_GENERAL = float(os.environ.get("HAND_TEACH_GENERAL") or 0.0) > 0
HAND_TEACH_REDRAW = float(os.environ.get("HAND_TEACH_REDRAW")) if os.environ.get("HAND_TEACH_REDRAW") else 4.0
HAND_LAM = min(1.0, KEY_EVERY * DT / HAND_TEACH_REDRAW) if HAND_TEACH_REDRAW > 0 else 1.0     # a reading's chance of a fresh draw
HAND_OUT_F, HAND_BAND_F = 40, (200, 600)               # frames: 1 s out of view; the bands' edges, 5 s and 15 s
HAND_HOLD_R, HAND_HOLD_F, HAND_TRAVEL = 150.0, 80, 200.0   # a hold: within this far for this many frames; travelling: this fast
#   PRO_ITEMS=1     the item rule (the intention head's teacher, and the walking teacher's target) in the pros' order:
#                   with no big weapon the nearest one that is there, rockets when it is within PRO_RL_EDGE seconds of
#                   the nearest (half of their first weapons are rockets); armed, the nearest of yellow armor, red armor
#                   and mega that is there and that he can still use; else the nearest big weapon he lacks.
PRO_ITEMS = float(os.environ.get("PRO_ITEMS") or 0.0) > 0
#   PRO_ROUTES=1    the way to a goal is the pros' where they went (sim/pro_routes/<map>.npz of tools/pro_routes.py: the
#                   step they took next from each place on their trips to it), the shortest way elsewhere: for the
#                   walking teacher and for the "next step" he is shown of his chosen way.
PRO_ROUTES = float(os.environ.get("PRO_ROUTES") or 0.0) > 0
# ITEM_BELIEF=1 (audit of 2026-10-08): what he is told about the item he has chosen ("is up", "comes back in") and what the
# item rule goes by is what he can know, not the true state: for every thing he can go for, the seconds since he knows it
# was taken (he took it, or it was taken within earshot, HEAR_EVT; or he saw its place empty, then counted as taken
# half its time ago); seeing it there clears that. Not known = thought to be there. The owner plays without item timers.
ITEM_BELIEF = float(os.environ.get("ITEM_BELIEF") or 0.0) > 0
# SHOT_COST (owner, 2026-10-08: "ammo is a scarce resource ... It's a learned behavior to be 'spam happy' or need to
# conserve ammo"): every shot he fires with a gun that uses ammo has a price: this share of what its hit would earn
# (SHOT_COST x the damage reward x the shot's full damage), times how scarce that ammo is for him at that moment:
#   the map    the seconds of fire the map feeds that gun per minute (one pickup of the gun, or the spawn's bullets, and
#              every box of its ammo once per its time): SHOT_REF_FIRE seconds = x1, half of that = x2 (held to 0.5 .. 2)
#   the place  the seconds of the way from where he stands to the nearest place that gun's ammo lies (the gun or a box):
#              SHOT_NEAR_S = x1 (0.5 .. 1.5)
#   his belt   a whole pickup's worth or more left = x0.5, half of one = x1, the last shots = x1.5
# and the three together held to 0.25 .. 3. With 0.10 and a factor of 1 a shot pays from one hit in ten on. In real games
# he fired 53% of the time an enemy was in view (people 24%) and 0.2 s after one appeared (0.5 s). 0 = off.
SHOT_COST = float(os.environ.get("SHOT_COST") or 0.0)
# The switches that change what a trained network is given or how its outputs are carried out. The trainer writes the
# ones that were set into the checkpoint, sim/export_duel.py into policy.npz, and the plugins set them before they load
# this module (until 2026-10-08 none reached a server: INTENT_HOLD was 8 in training and 3 there).
PLAY_VARS = ("INTENT_HOLD", "ITEM_BELIEF", "AIM_LEVEL", "AIM_PRESET", "FIRE_HOLD", "SURPRISE_MS", "AMMO_PACKS",
             "PERCEPT_SIGMA", "PERCEPT_TAU", "PERCEPT_SPEED", "KEY_RATE", "GROUND_SENSE", "SHOT_MASK", "LAVA", "WALK_FIX",
             "ITEM_DROP", "SOLIDS", "PRO_WAYS", "NEAREST", "PROJ_SEE", "JUMP_OPEN", "LEGS_LOOK", "LEGS_STAND", "LEGS", "LEGS_EVERY", "LEGS_OFF", "AUTO_SWITCH", "FIGHT_TARGET", "EN_KNOWN", "TARGETS", "TARGETS_FREE", "WAYS", "WAY_CAP", "WAY_ALPHA", "WAY_UNTESTED",
             "STYLE_MIX")
# ARMOR_COST (a proposal of 2026-10-08 after the owner's "go pick up the red armor"; 1.0 = off): what damage soaked by his
# armor costs him, as a share of what health lost costs. Damage taken was charged in full whether armor took it or not,
# so armor earned nothing in a fight but a later death. At a third, a hit on a player with armor costs him about half.
# What the attacker is paid does not change.
ARMOR_COST = float(os.environ.get("ARMOR_COST") or 1.0)
# CONTEST_P (owner, 2026-10-08: "yes", after "go pick up the red armor"): this share of the normal rounds on a real map
# starts as a race for a big item. The mega, the red armor or a yellow armor is not there and comes back in 4 to 8
# seconds (CONTEST_T), every player knows it, and everybody starts at a spawn point about that far from it by the
# walking graph. Whoever gets it fights the next fight with it. No new reward: the situation, dealt often. In self-play
# the big items lie untaken most of the time (the red armor 70% of the time on arena1 in training), so the race for
# one hardly ever happened, and nothing was lost by not running it.
CONTEST_P = float(os.environ.get("CONTEST_P") or 0.0)
# PRO_JUMP=1 (owner, 2026-10-08: "incentivise him to jump again, but informed by pro play ... jumping is how you strafe
# jump which IS a goal"): the walking teacher's label for the jump key comes from where the pros are in the air
# (tools/pro_jumps.py -> sim/pro_jump/<map>.npz: the share of their moving time in the air per cell of 64 units). It
# labels the key down where that share is over PRO_JUMP_AT while he is on his way at speed, and gives the key no label
# elsewhere (his own choice). Before, every taught frame that was not a gap or a step carried the label "no jump": the
# teacher that showed him the ways also taught him to keep his feet on the floor (he jumps in 1 to 2% of frames; the
# pros are in the air for most of their moving time).
PRO_JUMP = float(os.environ.get("PRO_JUMP") or 0.0) > 0
# GROUND_SENSE=1 (owner, 2026-10-08, after his two games against v12: "good players know how to move around the map
# without looking"): the floor round his feet (the eight readings 96 units away) and the lava and deadly drops there (96
# and 224 units away) are known to him in every direction, not only inside his field of view. In those games 6 of his 53
# deaths on arena1 were falls, all six while he moved in a direction outside his view (he looked at the enemy and stepped
# sideways); he moves that way 56 to 58% of the time. Walls, the far view, items and enemies stay view-only.
GROUND_SENSE = float(os.environ.get("GROUND_SENSE") or 0.0) > 0
# KNOW_PAY (owner, 2026-10-08: "He needs to be rewarded for knowing the enemy position"): frags a minute, at full knowledge,
# for knowing where his enemy is: in full while he has him in view, half on hearing him or right after losing him, gone
# KNOW_FADE seconds after that (in a group: the mean over his enemies). It gives looking around a use: in his games the
# owner turned his view twice as much as Bobby when nobody was about (median 58 against 25 to 30 degrees a second).
KNOW_PAY = float(os.environ.get("KNOW_PAY") or 0.0)
KNOW_FADE = 3.0
# PACE_PAY (owner, 2026-10-08: "basically no strafe jumping. This needs to be a priority now"): per second, for every
# 320 units a second he moves above running speed (held to one), while he is on the way to the item he chose, gains
# new ground on it at 60% of running pace or more, and no enemy was seen or heard for 1.5 s. It counts as pay of the
# trip: a trip given up gives it back. Item runs have their own pay for the pace (RUN_SCALE). The owner moved at 348 to
# 355 and above 400 for 27% of his moving time, Bobby at 313 to 322 and 3 to 5%.
PACE_PAY = float(os.environ.get("PACE_PAY") or 0.0)
# DROPS=1 (owner, 2026-10-08: "Does he know about DROPPED weapons? ... a very common and convenient way to get a weapon
# on spawn, especially in 3+ player matches"; "a pretty big oversight"): a player killed by another leaves the weapon he
# held on the floor, as the game does. Measured in a real game (plugins/droplab.py, docs/dropped_weapons.json): only on a
# kill by another player (not by his own hand or the map); only the weapon in his hand, never the machine gun or the
# gauntlet, and only with ammo left; it is thrown about DROP_THROW units the way he faced and lies DROP_LIFE seconds;
# whoever touches it has the weapon with one pickup's ammo, whatever the dead player had, added to his own up to the cap.
# He is shown the nearest one in his view (the N_DROP inputs: where, that it is there, rockets / lightning / rail, the
# time it has left); taking a weapon he did not have pays like any other new weapon. The walking teacher goes for one
# he can use that lies in plain sight within DROP_TEACH units.
DROPS = float(os.environ.get("DROPS") or 0.0) > 0
DROP_LIFE, DROP_MAX, DROP_THROW, DROP_TEACH = 30.0, 6, 140.0, 500.0
DROP_AMMO = np.array([10, 10, 100, 100, 10, 10, 50, 50, 0], np.float32)       # one pickup's worth per weapon (as LOADOUTS)
N_DROP = 8
# v14 (owner, 2026-10-09: "yes to additional inputs"; "He needs to have lead reading ... If there's additional inputs that
# would help him with this scope them"), the last N_V14 inputs:
#   his own movement, read out for strafe jumping (4): speed over the ground / 400; the sine and cosine of the angle from
#   his view to the way he is moving (zero under 50 units a second); the speed gained over the last 100 ms / 100.
#   where a rocket or a plasma ball fired now would meet the enemy he sees (6; zero with another weapon in hand or no enemy
#   in view): the crosshair's distance from that meeting point left-right (30 degrees, and fine: 2) and up-down (15, 2),
#   the flight time / 1.5 s, and how far below the meeting point the floor under it lies, as an angle / 15 degrees (a
#   rocket at his feet). Worked out from what he knows of the enemy (as old as his reaction time, the enemy's movement
#   200 ms old): a straight line on the ground, a thrown body's arc in the air, the projectile's speed (P_SPEED).
N_V14 = 10
# v15 (2026-10-10, docs/design/SCOPE_v15.md), the last N_V15 inputs: the jump ahead on his way (jump_links.N_JUMP: that
# there is one, the speed it needs, the way to its take-off, its length, its rise; in a jump run, zero elsewhere), and for
# the grenade launcher in his hand what the lead inputs are for rockets and plasma: how far his view is from the one that
# lands a grenade where he believes the enemy is (the low arc: yaw and pitch, coarse and fine), the seconds of its
# flight, and that it reaches. The enemy counts while in view and for GL_KNOWN seconds after.
# ... and (PROJ_SEE, owner 2026-10-10: every projectile in his field of vision, none through a wall, and what each
# one is and does) the enemy projectiles as a player sees them: inside his view cone, within PROJ_FAR units, the line
# from his eyes to it clear. The old inputs then show the nearest two he sees (they showed the nearest two in flight,
# through walls inside the cone, and anything within 400 units in any direction); four more follow here (place 3,
# speed 3, kind 3), and each of the six gets three more: a grenade's fuse left (1 = just fired), the seconds until it
# passes closest to him (over 2), and how close that is in splash radii (over 3; under a third: inside its blast).
N_PROJ_MORE, PROJ_FAR = 4, 1500.0
# The movement network as his legs (LEGS; owner, 2026-10-10: "build movement/fighting as a switch and let him decide when
# to use it"). Taught as a side lesson, strafe jumping never reached him: a network copies the movement network only
# loosely, and a loose copy does not strafe jump (RESULTS 2026-10-10 20:45). So it is not copied: it is a part of him.
# One more output (the last, LEGS_HEAD: his own movement, or his legs), read every LEGS_EVERY frames (four times a second,
# staggered by player) and held between. While it is on and he has a target (the item of his intention, or of his run)
# that the movement network knows a way to, his movement keys, his view's turn, walk and zoom (LEGS_TAKES) are the
# movement network's choices for that frame, made from its own inputs and under his finger and mouse limits; his view's
# pitch, his trigger, his weapon key and his intention stay his own. Without a way (no target, a map the network has no
# walking map of, the try of a jump its pupil fails at before its landing) the switch does nothing and he moves himself.
# Two inputs, the last of N_V15: the switch as it stands, and that his legs carried him on the last frame.
# The trainer counts the taken outputs on the frames he moved himself only, and the switch on the frames it was read.
LEGS = float(os.environ.get("LEGS") or 0.0) > 0
LEGS_EVERY = int(float(os.environ.get("LEGS_EVERY") or 10))
LEGS_OFF = int(float(os.environ.get("LEGS_OFF") or 1))    # readings of "my own movement" in a row that end a stretch on his legs (2026-10-11: with
#                 one, 62 to 73% of his stretches ended on a single "no" with no enemy in view and most lasted under a second)
# Stage C, part 1 (docs/design/V02_STAGE_C.md): his own movement taught by his legs, then the switch weaned. What his legs
# do in the stretches he chooses them is what he should be able to do himself: the same hands, the same moment.
#   LEGS_LABEL=1  step() gives info["legs_lab"], int8 [players, 4]: on the frames his legs carried him (legs_on) the
#                 movement network's four choices that were put in place of his own (forward and back, sideways, jump and
#                 crouch, the view's turn: his outputs 0 to 3, in his own numbering), -1 elsewhere. The trainer's
#                 --legs-teach lesson is made of it. Changes nothing he does and draws no random number.
#   LEGS_KEEP=<share>  (1 = as today; a training switch, not one of PLAY_VARS: a check or a server never sets it) when
#                 a stretch on his legs begins (his switch turns on) a draw: with the chance 1 - share the stretch is
#                 withheld. Until his switch is off again his own outputs move him and legs_on stays False (the input
#                 "his legs carried him" says so, the trainer counts his own movement outputs); the label is worked out
#                 all the same (the movement network is asked on the same frames and draws the same random numbers) and
#                 info["legs_held"] (bool [players]) marks the frames a withheld stretch has a label on. The draws come
#                 from a random stream of their own (rng_keep): the simulator's is not shifted by them. Stretches are
#                 withheld from the seats of legs_keep_who (all; the trainer takes the league's seats out: an older self
#                 keeps his legs). Below 1 it gives the labels whether LEGS_LABEL is set or not.
# Counted apart for the stretches his legs carried him and the withheld ones (stats["legs_keep"], seats of legs_keep_who):
# stretches begun, frames with a label, of them at LEGS_FAST units a second or more, his speed on them, and the speed
# gained over the first two seconds (LEGS_GAIN_FRAMES) of a run of such frames (frames with a label without a break, in
# one stay on the map), for the runs that last that long.
LEGS_LABEL = float(os.environ.get("LEGS_LABEL") or 0.0) > 0
LEGS_KEEP = min(1.0, max(0.0, float(os.environ.get("LEGS_KEEP") or 1.0)))
LEGS_LAB = LEGS and (LEGS_LABEL or LEGS_KEEP < 1.0)       # the labels are worked out and given
LEGS_FAST, LEGS_GAIN_FRAMES = 400.0, 80
N_LEGS = 2
# Stage C part 2 (docs/design/V02_STAGE_C.md): his legs take a look direction, and can stand at a place. Measured
# 2026-10-11: his legs hold his view's turn (strafe jumping is made with it), so three of four stretches on his legs end
# at a glimpse of the enemy; and they cannot stop: sent to a holding place they arrive at 370 units a second, let go
# of him at 96 units and he goes over the ledge. Both switches need a movement network trained for it
# (sim/train_move.py --look, --arrive: three more inputs, movement_env.N_C2; its policy.npz says so with `c2`); with any
# other network they do nothing.
#   LEGS_LOOK=1   while his legs carry him and he believes the enemy somewhere, that place is his legs' look point: they
#                 keep his view within about 30 degrees of it while they run. The place is the one of his own inputs
#                 "the enemy as he believes him" (N_V02: his last known place and a second of his last known movement,
#                 as old as his reaction time; seen or heard in the last V02_KNOWN seconds, or it is none), kept at
#                 every observe(): his legs know nothing he does not. With no belief they run as before.
#   LEGS_STAND=1  his target is one of the map's holding places (stage B part 2; without that part in this file the
#                 switch has nothing to do): his legs are told to stand at it, and they do not let go of him inside its
#                 HOLD_R units; they stop him there and hold him (his switch still takes him off them when he chooses).
# Counted (stats["legs_c2"]): frames his legs were asked with a look point; of them his view within 30 degrees of it
# as they were asked; frames they were told to stand at the goal.
LEGS_LOOK = float(os.environ.get("LEGS_LOOK") or 0.0) > 0
LEGS_STAND = float(os.environ.get("LEGS_STAND") or 0.0) > 0
INTENT_HEAD, LEGS_HEAD, LEGS_TAKES = 10, 11, (0, 1, 2, 3, 7, 8)
N_V15 = JL.N_JUMP + 6 + 9 * N_PROJ_MORE + 3 * (2 + N_PROJ_MORE) + N_LEGS + N_EN
# AUTO_SWITCH (owner, 2026-10-10: "if you run out of ammo it moves you to a different weapon. Give him that setting and
# use the weapon swaps from quake live"): the trigger pressed on an empty weapon brings up the highest weapon of the
# game's own order that has ammunition (the client's cg_switchOnEmpty, in the game's weapon numbers from the top:
# heavy machine gun, plasma, rail, lightning, rockets, grenades, shotgun, machine gun, gauntlet), after the empty click's
# half second (Quake 3's source: pm->ps->weaponTime += 500; not measured in Quake Live yet) and the weapon change itself.
AUTO_SWITCH = float(os.environ.get("AUTO_SWITCH") or 0.0) > 0
AUTO_ORDER = np.array([HMG, PG, RG, LG, RL, GL, SG, MG, G], np.int64)
NOAMMO_WAIT = 0.5
GL_KNOWN = 3.0
PROJ_SEE = float(os.environ.get("PROJ_SEE") or 0.0) > 0
LEAD_SPEED = np.zeros(NW, np.float32)
LEAD_SPEED[RL], LEAD_SPEED[PG] = P_SPEED[RL], P_SPEED[PG]
# TEACH_KEYS_ONLY=1 (owner, 2026-10-08: "KEYS TOWARD THE GOAL given the current view he has, meaning he can look freely
# around and is not being given a rule that forces him to look a certain way"): the walking teacher names no turn of the
# view in item runs either (in normal games it never did).
TEACH_KEYS_ONLY = float(os.environ.get("TEACH_KEYS_ONLY") or 0.0) > 0
# The map fixes of 2026-10-09 (the game's maps set beside the simulator: docs/RESULTS.md that day). Each has its own
# switch and all are off by default: v13 and every older network was trained without them.
#   SHOT_MASK=1   shots, missiles, splash and sight stop at solid brushes only, as in the game (its MASK_SHOT). Until now
#                 every trace also stopped at player-clip brushes: bars, grates and railings that the game does not draw
#                 and lets shots through (owner: "the wall between grenades and mega health; there's bars in it ... and
#                 you can shoot through it"): 1 to 5% of a map's lines of sight and fire were closed. What he feels of the
#                 walls, floors and ceilings for moving keeps the player's mask.
SHOT_MASK = float(os.environ.get("SHOT_MASK") or 0.0) > 0
SOLID_ONLY = 1                                             # CONTENTS_SOLID
#   LAVA=1        lava and slime hurt, as in the game: 30 (slime 10) times how deep he stands in it (1 = the feet, 2 = to
#                 the waist, 3 = over the eyes), at once and again every LAVA_TICK seconds. Measured in the game on
#                 2026-10-09 (plugins/poollab.py): Lost World, feet in lava, 100 health gone in 1.55 s; Battleforged, to
#                 the waist, in 0.83 s. Until now only a lab map's rooms.json named places that hurt: on the game's maps
#                 lava was water (on Lost World 59 points of the walking map, 4.6%, stand in it; Battleforged 30). With
#                 the switch the hazard inputs name lava under the spots round him, and no way leads through lava.
LAVA = float(os.environ.get("LAVA") or 0.0) > 0
#   WALK_FIX=1    two repairs to the walker, which is both the scripted item runner (the Nightmare stand-in) and the walking
#                 teacher's labels. (a) An entrance (a teleporter, a pad's plate) was "a step up" when its middle lay more
#                 than 18 units above him: he jumped, and in the air his target switched to where it takes him (the rule
#                 for a pad's flight), so he hopped on the spot. Now the entrance stays the target until he is thrown, and
#                 is no reason to jump. (b) "The next point is reached" was judged on the plan alone: at a drop whose landing
#                 lies under the edge he took it for reached and headed for the point after it, never stepping off. Now his
#                 height has to be near it too. Measured with both seats the stand-in (2026-10-09): stuck 47% -> 7% of the
#                 time on Sinister, 46% -> 15% on Lost World, 22% -> 5% on Furious Heights, 13% -> 3% on Battleforged.
#                 (c) The item rule names nothing the walking map has no way to (Aerowalk's red armor: half his time).
#                 (d) Points of the walking map that no spawn point reaches (on top of the clip above a map: Aerowalk 28%
#                 of its points, Battleforged 24%, Sinister 16%) take no part: no way leads through them and "the nearest
#                 point" is never one of them. (e) With SOLIDS, a teleporter link whose straight line to the entrance is
#                 shut (from behind the teleporter's solid face) is left out.
WALK_FIX = float(os.environ.get("WALK_FIX") or 0.0) > 0
TELE_FAR = 160.0                                       # (WALK_FIX) a teleporter link starts within this of its entrance
#   QL_MOVE=1     two numbers of Quake Live's movement that the simulator had from Quake 3: with the feet in water he
#                 moves at 0.933 of running speed (measured 298.7 units a second on Furious Heights and Hektik; the
#                 simulator 267), and a step may be 22 units high (the game's pmove_StepHeight; Quake 3's 18).
QL_MOVE = float(os.environ.get("QL_MOVE") or 0.0) > 0
#   ITEM_DROP=1   an item lies where the game lets it fall at a map's start (a 30-unit box dropped to the floor), not at the
#                 map file's point: on Sinister those float a median 43 units above the resting place, on Hektik eight
#                 items 30 to 40 (the game's own item list, plugins/maplab.py). The plugins match the game's items to his
#                 within 40 units: on Sinister most were not matched.
ITEM_DROP = float(os.environ.get("ITEM_DROP") or 0.0) > 0
#   SOLIDS=1      the map's solid pieces that are brush models of their own (func_static, a teleporter's face) are part of
#                 the collision, as in the game: Battleforged has a platform 24 units high beside its mega.
SOLIDS = float(os.environ.get("SOLIDS") or 0.0) > 0
#   PRO_WAYS=1    where the walking map has no way to a big item, the pros' way (sim/pro_routes/<map>.npz: their time and
#                 their next step from every place they passed on their trips to it), and from everywhere else the walk to
#                 the best such place. Aerowalk's red armor lies across a gap of 288 units, 56 up: the walking map (walks,
#                 plain jumps, drops, pads, teleporters) has no way to it from 98% of the map, so his way there, its
#                 seconds and its pay did not exist. The walker does not take such a step: the walking teacher gives no
#                 keys for it, and a scripted player goes by the walking map alone.
PRO_WAYS = float(os.environ.get("PRO_WAYS") or 0.0) > 0
#   NEAREST=1     every rocket launcher, railgun and lightning gun of a map is a goal of its own under its kind's name, and
#                 "the rocket launcher" of a way, an intention or a trip is the one the shortest way leads to from where he
#                 stands. Until now only the first of a kind in the map file was a goal: the second launcher of Aerowalk,
#                 Sinister, Furious Heights, Battleforged and Hektik was never one.
NEAREST = float(os.environ.get("NEAREST") or 0.0) > 0
#   RULE_WALK=1   the item rule (the intention head's teacher) and the draw of an item run's target count only the ways a
#                 walker can take, for him as for a scripted player: an item that only a pros' step leads to (PRO_WAYS:
#                 Aerowalk's red armor, a jump no walker makes; a walker gets there from 1% of the map's points) is not
#                 named and not drawn. With PRO_WAYS alone the rule named it a quarter of the time, he went and did not
#                 arrive, and lost Aerowalk to v13 12% to 88% within 17 minutes of every start of v14 (RESULTS
#                 2026-10-10 09:30). His inputs still show the pros' way: he may choose it himself. Off by default.
RULE_WALK = float(os.environ.get("RULE_WALK") or 0.0) > 0
# v15 (2026-10-10), both off by default:
#   JUMPS=1       the pros' jumps that a walker cannot make (tools/pro_gaps.py -> sim/pro_gaps/<map>.json) are links of a
#                 second set of ways (route_j), which are his in a jump run: a share of the playing time (JUMP_RUN_P, beside
#                 ITEM_RUN_P) in which he is alone on the map, begins a second or two of way before a take-off and goes
#                 for the item behind it, paid as in an item run; a try ends with the item, with a fall short of the
#                 landing, or after twice the way's seconds and JUMP_TRY_SLACK. Per jump: tries, over, fallen short. In
#                 games his ways stay a walker's (a jump is opened there when he is measured to make it: not built yet).
#   START_GUN_P   the share of his lives in games that begin with the grenade launcher or the plasma gun in his hand, with
#                 a pickup's ammunition (owner, 2026-10-10: "they are a real limitation to his play"; in every run before
#                 he held either 0.0% of the time and never found out what they do)
JUMPS = float(os.environ.get("JUMPS") or 0.0) > 0
#   JUMP_ALL=1    tries also at the jumps that lie on no item's fastest way, or with no room for their run-up on one (62 of
#                 the 144 in use, 2026-10-10). First a second set of his ways in which that one jump costs nothing, so
#                 the way to the two items nearest behind its landing takes it from a full run-up back. A jump that still
#                 has none gets ways to its landing first and from there to the nearest item of a kind the map has once
#                 (he has the plain ways again when he has landed there); with less way before the take-off than the
#                 run-up asks, the try begins as far back as the map allows (at the take-off itself where another jump
#                 lands there). In every jump run the movement teacher is asked for the landing until he is over it, as
#                 in its own tries, then for the item. It gives no labels before the landing of a jump named in
#                 sim/jump_labels.json (tools/jump_labels.py: the jumps at which a player who presses its labels alone
#                 does not come to the take-off in half of the tries: its own way goes round them from where his tries
#                 begin. A jump it goes for and seldom lands keeps its labels: they show the way, not the one execution).
JUMP_ALL = float(os.environ.get("JUMP_ALL") or 0.0) > 0
#   JUMP_OPEN     "aerowalk:1;bloodrun:1,26": per map, the jumps (their numbers in its list) that his ways take in games and
#                 item runs too: the inputs of his way, its pay, the item rule and the item runs' targets follow the
#                 walking map with those jumps (route_o). Scripted players keep the walking map's ways. A jump is opened
#                 when he is measured to make it in jump runs (tools/jump_check.py, the trainer's v15.jumps).
JUMP_OPEN = os.environ.get("JUMP_OPEN") or ""
#   TEACH_BEST=1  the movement teacher's labels are its likeliest choice per output, not a sample of its choices (B-201: a
#                 pupil of sampled labels learned its spread with it; tools/label_check.py --best says what they are worth)
TEACH_BEST = float(os.environ.get("TEACH_BEST") or 0.0) > 0
#   GL_QL=1       grenades and splash as measured in the game on 2026-10-10 (plugins/weaponlab.py set 4, data/weaponlab5): a
#                 bounce keeps the rest of its frame (the grenade came to rest 10 to 40% short of the game's), and splash
#                 reaches a player when the line from the blast to his middle or to one of four points 15 units beside it
#                 is clear (the game's CanDamage), not only the line to his middle
GL_QL = float(os.environ.get("GL_QL") or 0.0) > 0
START_GUN_P = float(os.environ.get("START_GUN_P") or 0.0)
#   START_GUN_W   "rl:0.5,pg:0.25,gl:0.25": which weapons those lives begin with and their shares, among the ones the map
#                 has (owner, 2026-10-10 17:35: rockets too, "50%/25%/25% rockets/plasma/grenades"). Unset: grenades and
#                 plasma evenly, as before.
START_GUN_W = {p_.split(":")[0].strip(): float(p_.split(":")[1]) for p_ in (os.environ.get("START_GUN_W") or "").split(",") if ":" in p_}
JUMP_TRY_SLACK = 4.0
# v14's own changes (the owner's calls of 2026-10-09, docs/MANIFEST_v14.md), each off by default:
#   SHOT_W        the shot's price by weapon, as multipliers of SHOT_COST, e.g. "rl:0.2,gl:0,pg:0" (rockets: "there should be
#                 an opportunity cost ... the cost can be very low"; plasma and grenades: "no opportunity cost").
#   TEACH_FREE=1  the weapon teacher is silent while he holds the shotgun, the grenade launcher or the plasma gun, and where
#                 its answer would be the machine gun while he owns one of those with ammo ("neutral *if* he switches to
#                 sg/plasma/grenade ... he can experiment with them"). Until v13 its label there was "switch", in every
#                 run since v10: 0.0% of his frags were with them.
#   SPEED_PAY     pay for covering his way fast ("320 -- 480 pay for speed bonus (flat above 480), it can be aggressive at
#                 first"): for every stretch of new ground on the way to his chosen item, by the speed he covers it at,
#                 nothing at SPEED_LO units a second, full from SPEED_HI on. The number is what a second at SPEED_HI straight
#                 along the way earns. Paid per stretch of ground and not per second, so a detour or a zigzag at speed earns
#                 nothing more and a way pays at most SPEED_PAY * 2/3 * its seconds however long he takes. In item runs, and
#                 in games with nobody seen for 1.5 s, where it counts as pay of the trip (a trip given up gives it back).
#                 In place of PACE_PAY, which paid 0.02 a player-minute.
SHOT_W = np.ones(NW, np.float32)
for part_ in (os.environ.get("SHOT_W") or "").split(","):
    if ":" in part_:
        SHOT_W[WEAPONS.index(part_.split(":")[0].strip())] = float(part_.split(":")[1])
TEACH_FREE = float(os.environ.get("TEACH_FREE") or 0.0) > 0
SPEED_PAY = float(os.environ.get("SPEED_PAY") or 0.0)
SPEED_PAY_RUN = float(os.environ.get("SPEED_PAY_RUN") or SPEED_PAY)       # ... its number in item runs (the same unless given)
SPEED_LO, SPEED_HI = 320.0, 480.0
#   HOP_PAY       a tiny pay for speed gained from hop to hop (owner, 2026-10-11: "pay him a tiny amount for it. but the key
#                 is getting him to use them and maintain speed"). At a take-off (the frame he leaves the ground by a jump:
#                 the jump key down, rising at a jump's speed, from the floor or having touched it inside the frame) in a
#                 game, an item run or a jump run, with no enemy in view: HOP_PAY for each unit of speed over the ground
#                 above the best take-off speed of this chain of hops so far, counting only speed between SPEED_LO and
#                 SPEED_HI. A chain is a run of hops with at most HOP_GROUND seconds on the ground between a landing and the
#                 next take-off; it ends, and its best is forgotten, when he stays on the ground longer, when an enemy comes
#                 into view, or when his speed falls under HOP_SLOW (a new life begins standing still, so a death ends it
#                 too). So a whole chain from 320 to 480 pays 160 x HOP_PAY (0.16 at 0.001) and never more, and speed lost
#                 and regained inside a chain pays nothing: the pay is on the chain's running best. Two things keep it
#                 from paying for what is not a gain from hop to hop: (1) a chain's first take-off sets its best and is
#                 not paid (there is no best "so far"; counted from 320 instead, 63% of what the movement network's pupil
#                 was paid on Blood Run came at first take-offs, for speed built running, 371 on average, and a chain
#                 broken on purpose paid again at once: also after an enemy had shown for a moment); (2) speed he is
#                 given in one frame of a chain, more than HOP_GIVEN units of it (a teleporter's exit, a jump pad, a
#                 blast, a slope), raises the best unpaid: his from there on, but not gained by hopping. Policy players
#                 only, on his own keys and on his legs alike. Not part of r_long, and nothing of it is in `dealt`.
#                 Counters: hop_pay (the sum), hop_n (take-offs that paid), hop_takeoffs (his take-offs with nobody in
#                 view, paid or not), hop_chains (chains begun: first take-offs). 0 = off.
HOP_PAY = float(os.environ.get("HOP_PAY") or 0.0)
HOP_GROUND, HOP_SLOW, HOP_GIVEN, HOP_VZ = 0.4, 250.0, 40.0, 400.0     # (a jump gives 275 upward, 385 soon after another; a pad more)
#   GAME_P, LATE_P, WIN_PAY   stage B part 4 (docs/design/V02_STAGE_B.md; the owner, 2026-10-11: whole games "Yes", a frag
#                 paid by what it moves his chance of winning "yes", late-game rounds from drawn states "yes, up to 25%").
#                 Training switches, all off by default. Duels on a real map only: a group of more than two, the test
#                 map and the test rooms play as before.
#   GAME_P=<share>  that share of the games' playing time (the NORMAL rounds': not the one-weapon rounds, not the item
#                 runs and jump runs) is whole duel games: GAME_LEN seconds on one clock and one score. Nothing is put
#                 back in between: the items return on their own clocks, stacks, dropped weapons and what each player
#                 knows carry on; a death is a respawn at a spawn point with the game's spawn (no weapon in hand by
#                 START_GUN_P, no random stack, no spawn near an item or in front of the enemy). Both seats are networks
#                 (no scripted opponent) and no game starts as a race for an item. The score is the game's: a frag is a
#                 point, a death by his own hand or by the world takes one off him (the round score of today counts
#                 frags only). The game ends at the limit, to the frame, and only then is the round "done"; level at the
#                 limit is a draw (no overtime; counted). The clock input is the share of the game played (in a round it
#                 is seconds / 120, held at 2: it would stand still from 4:00 on), the "time left" input the share left.
#   LATE_P=<share>  that share of it is late rounds: the last LATE_LEN seconds of such a game, begun at LATE_AT and
#                 played to the limit as a whole game is. The score is drawn: his lead uniform over -LATE_LEAD..LATE_LEAD
#                 on top of LATE_BASE frags each. The stacks go with it: each seat begins stacked with the chance
#                 0.5 + LATE_STACK x his lead (three ahead 0.8, level 0.5, three behind 0.2), as the simulator's random
#                 stack (stack_p: health 100 to 200, armor 0 to 150) with the big weapons the map has at 40% of full
#                 ammunition (the holder's start, HOLD_STACK); else as he spawns. The items' clocks are drawn as in the
#                 middle of a game: a mega or an armor is away with the chance LATE_DOWN[0], a weapon LATE_DOWN[1],
#                 anything else LATE_DOWN[2], for a time uniform over its return time; one of the stacked seats (any
#                 seat if none is) took it and knows when it is back, the other does not.
#                 The shares are of playing time, as kind_p's: a new round's kind is drawn by share / length.
#   WIN_PAY=1     in whole games and late rounds the flat pay for a frag (+1) and a death (-1) is not paid. Every frame
#                 pays the change in his chance of winning the game since the frame before, WIN_SCALE x (p - p before),
#                 p by his lead and the time left from sim/win_chance.json (tools/win_chance.py, the pros' games: the
#                 lead -10..10 by the time left in steps of 30 s, a straight line between the steps; 1 / 0.5 / 0 at the
#                 limit). WIN_SCALE = 1 / (p(one ahead, ten minutes left) - 0.5): a frag at 0:0 with ten minutes left is
#                 worth what a frag pays today. The second seat is paid the same amount with the other sign, so the two
#                 sum to nothing; and because each frame pays a difference of the same function, a game's pays sum to
#                 WIN_SCALE x (1, 0.5 or 0 less the chance at its start) whatever happened on the way: nothing in it
#                 can be pumped. Most of a frame's pay is at a frag (the step in the table); between frags the leader is
#                 paid a trickle as the clock runs down and the other one loses it. Paid at frags alone the sum would
#                 depend on the way: one frag behind early and level again late would pay more than it costs. Everything
#                 else of the pay stays. Not part of r_long.
#                 Counters: stats["games"] (GAMES_COLS); info["win_pay"] is the frame's pay by the game, per player.
GAME_P = float(os.environ.get("GAME_P") or 0.0)
LATE_P = float(os.environ.get("LATE_P") or 0.0)
WIN_PAY = float(os.environ.get("WIN_PAY") or 0.0) > 0
GAME_ON = GAME_P > 0 or LATE_P > 0
assert GAME_P >= 0 and LATE_P >= 0 and GAME_P + LATE_P <= 1.0 + 1e-9, "GAME_P and LATE_P are shares of the games' time"
GAME_LEN, LATE_AT = 600.0, 420.0
LATE_LEN = GAME_LEN - LATE_AT
GAME_FRAMES, LATE_FRAME = int(round(GAME_LEN / DT)), int(round(LATE_AT / DT))
LATE_LEAD, LATE_BASE, LATE_STACK, LATE_DOWN = 3, (2, 8), 0.1, (0.7, 0.2, 0.4)
GAMES_COLS = ("whole games ended", "late rounds ended", "of both: level at the limit", "the two scores of the whole games, summed",
              "ended in the second half of the matches (the trainer's league half: the first seat is his)", "of those: he won", "level", "he lost",
              "his lead at the end, summed", "what WIN_PAY paid him in them", "what the flat pay for frags and deaths would have",
              "all that ended: the size of the first seat's WIN_PAY, summed", "... of his flat pay", "frames of matches in whole games",
              "in late rounds", "whole games and late rounds begun")
#   HIGH_PAY      who stands higher (B-160: he fights from below; owner, 2026-10-09: "fights from the low ground"): a hit
#                 from above counts for more, to the one who deals it and to the one who takes it, and a hit from below
#                 for less: by HIGH_PAY (0.25 = a quarter) at HIGH_Z units of height between the two, in proportion
#                 below that. Own splash and falls are not changed. 0 = off.
HIGH_PAY = float(os.environ.get("HIGH_PAY") or 0.0)
HIGH_Z = float(os.environ.get("HIGH_Z") or 128.0)
#   TRICKS=1      the scripted opponents of docs/SCOPE_v15.md (the personas holder, lobber, watcher) get what they need:
#                 ways to places that are not items (the spawn points, posts to watch an item from). Off: none of it is
#                 built, and those personas play as the plain item runner.
TRICKS = float(os.environ.get("TRICKS") or 0.0) > 0
HOLD_HUNT, HOLD_HUNT_P = 10.0, 0.6                         # the holder after a frag: seconds he looks for him, and how often
WATCH_SECS = 25.0                                         # the watcher keeps a post this long
LOB_PG_NEAR, LOB_PG_FAR = 150.0, 1000.0                    # ... and in a fight it holds the plasma gun at these distances
LOB_AHEAD, LOB_PG_ETA, LOB_GL_ETA = 3.2, 1.0, (1.6, 3.0)   # the lobber: seconds of the other one's way he looks along; he fires plasma at an
#   exit when the other one is under LOB_PG_ETA from coming out of it, a grenade when LOB_GL_ETA away (its fuse is 2.5 s)
TRICK_P = np.zeros(3)                                     # of the item runner's rounds, the shares with the holder, the lobber, the watcher
for part_ in (os.environ.get("TRICK_P") or "").split(","):
    if ":" in part_:
        TRICK_P[("holder", "lobber", "watcher").index(part_.split(":")[0].strip())] = float(part_.split(":")[1])
if os.environ.get("TRICK_NOISE"):                         # their aim: degrees of noise a frame (the stand-in's 0.6 by default)
    P_NOISE[HOLDER:WATCHER + 1] = float(os.environ["TRICK_NOISE"])
HOLD_STACK = float(os.environ.get("HOLD_STACK") or 0.0)   # the share of his rounds the holder starts ahead (100 armor, the big weapons)
#   RUN_TEACHER=1 item runs: the strafe-jumping movement network (the trainer's --teacher) shows keys, jump and view toward
#                 his target, in place of the walking teacher's keys (those stay where the network has no way).
#   STACK_KEYS=0  no key labels in normal games (v13: the walking teacher's keys for a bare or low player with nobody about).
RUN_TEACHER = float(os.environ.get("RUN_TEACHER") or 0.0) > 0
STACK_KEYS = float(os.environ.get("STACK_KEYS") or 1.0) > 0
#   BLIND_RULE=1  shots with no enemy seen or heard for a second (owner, 2026-10-09). Until v13 every frame of fire then cost
#                 BLIND_FIRE_COST, whatever the weapon: a rocket held down blind cost 19 points of damage, and he fired
#                 blind in 0.0% of his frames where the pros with the launcher fire 22 to 40% of the time. Now:
#                 plasma and grenades are free ("no opportunity cost": zoning). A rocket is free when it is a rocket jump
#                 (lands within BLIND_JUMP units of him), lands within BLIND_NEAR units of where he thinks the enemy is
#                 (the last place seen or heard plus up to a second of the movement last seen: "leading the shots will
#                 likely go outside that"), or lands on a way the enemy is likely to take from there, toward him or toward
#                 a big item, at a point the enemy can have reached by the time it lands; any other rocket ("firing them
#                 at nonsense") costs BLIND_RL_DMG points of damage. Machine gun, shotgun, lightning and rail keep the
#                 cost per frame, but not in the first PREFIRE_T seconds while the crosshair is within PREFIRE_R units of
#                 where the enemy must be ("a small radius for allowance of prefire for hitscan weapons").
BLIND_RULE = float(os.environ.get("BLIND_RULE") or 0.0) > 0
BLIND_NEAR, BLIND_JUMP, BLIND_WAY_R, BLIND_SLACK, BLIND_RL_DMG = 600.0, 100.0, 200.0, 1.0, 6.0
BLIND_RL_DMG = float(os.environ.get("BLIND_RL_DMG") or BLIND_RL_DMG)      # (owner, 2026-10-11: more forgiving: 3)
# BLIND_PLACES=<radius>: a rocket with no enemy in view is free as well when it lands within that many units of one of the
# places the pros' blind shots land on this map (sim/pro_places/<map>.json: the 24 heaviest, from 4,085 demos). The pros
# fire half their rockets with nobody in view, 4.5 a minute; he fired 0.001.
BLIND_PLACES = float(os.environ.get("BLIND_PLACES") or 0.0)
PREFIRE_R, PREFIRE_T = 150.0, 1.5
LAVA_DMG, SLIME_DMG, LAVA_TICK = 30.0, 10.0, 0.5
C_LAVA, C_SLIME, C_WATER = 8, 16, 32                       # brush contents
PRO_JUMP_AT = float(os.environ.get("PRO_JUMP_AT") or 0.5)
CONTEST_T = (4.0, 8.0)
SHOT_REF_FIRE = 16.0
SHOT_NEAR_S = 3.0
SHOT_DMG = W_DMG * np.where(np.arange(NW) == SG, SG_PELLETS, 1).astype(np.float32)     # a whole shot's damage
SHOT_UNIT = np.array([10, 10, 100, 100, 10, 10, 50, 50, 1], np.float32)                # one pickup's worth (the spawn's bullets)
BELIEF_SEE = 1500.0                                    # an item's place is seen up to this far (as the item inputs)
PRO_RL_EDGE = 1.5
STYLE_DMG = float(os.environ.get("STYLE_DMG") or 0.5)
STYLE_BAND = float(os.environ.get("STYLE_BAND") or 0.5)
STACK_TEACH_QUIET = 1.5
INTENT_HOLD = float(os.environ.get("INTENT_HOLD") or 3.0)     # (v11: longer, with a release when the item is gone, see intend)
INTENT_VALUE = (0.0, 1.0, 1.0, 0.25, 0.25, 0.25, 0.5, 0.5, 0.0) + (0.0,) * 8     # (the enemy, a holding place: no pay for the way)
CLAW_ON_DEATH = False                                  # the trip's pay was also taken back when he died on the way: with half the
                                                       # trips ending in death the long ones (mega, red) lost money and he chose the
                                                       # launcher 92% of the time (v9 night, 2026-10-07). Now only a trip given up is clawed back (owner)
ACTION_DIMS = (3, 3, 3, len(TURN), len(PITCH), 2, 1 + NW, 2, 2, 2, len(INTENTS), 2, N_WAYS)  # ..., walk, zoom, lift the mouse, intention, his legs (LEGS), his way (WAYS)
assert len(ACTION_DIMS) == WAY_HEAD + 1
N_WALL, N_FLOOR, N_PROJ = 16, 8, 2
SLOTS = ("MH", "RA", "RL", "RG", "LG", "SG", "GL", "PG", "HMG")   # nearest item of each kind is an input
MEM_COLS = np.array([0, 1] + [2 + int(w) for w in OBS_W])  # the columns of e_got that are inputs (see N_MEM)
OBS_BASE = 3 + 1 + 5 + 2 + N_WALL + N_FLOOR + 18 + 9 * N_PROJ + 3 * len(OBS_W) + 6 * len(SLOTS) + N_GOAL
# Fight inputs (2026-10-05), appended after everything else:
#   enemy shots he saw or heard: firing right now 1, time since the last one 2, which weapon it was 9 (every weapon
#     has its own sound), how long until that weapon can fire again 1, whether he saw it or only heard it 1   = 14
#   the line of the enemy's last bullet, rail or lightning shot, while it is on screen (nearest point of it,
#     relative to him) 3 + a flag that fades with the trail 1                                             = 4
#   the enemy in view: crouched 1, in the air 1                                                           = 2
#   his own hand: the keys in effect 3, the budget of key actions 1, which fingers are free 5              = 9
#   his right hand: zoomed 1, fire finger free 1, zoom finger free 1                                       = 3
#   the enemy's pain sound when he is hit within earshot: which of the four (it depends on his health: under 25,
#     under 50, under 75, above) 4, fading 1. The only clue to the enemy's health; his health itself is never an input. = 5
N_FIGHT = (5 + len(OBS_W)) + 4 + 2 + 9 + 3 + 5
# Memory aids (2026-10-05, B-90: things a player keeps in his head), appended after the fight inputs:
#   the mega health and the red armor: known to have been taken (he took it or heard it taken) 1, and how long ago
#     as a share of its timer (35 s, 25 s) 1, for each: 4
#   what the enemy is known to have since his last death: mega 1, red armor 1 (heard or seen taken), each weapon
#     seen in his hands 9: 11
#   seconds since his own respawn 1; the enemy's last death known 1 and how long ago 1: 3
#   his own focus (see FOCUS_SECS): 1
N_MEM = 4 + len(MEM_COLS) + 3 + 1
# Routes (2026-10-06): the way to the mega health, the red armor and the three main weapons along the floor, as a
# player who knows the map has it: seconds of travel 1, and where the next step of the way lies 3, for each. The
# straight line he had before points through walls, and to the red armor of arena1 across a drop that kills.
ROUTE_ITEMS = ("MH", "RA", "RL", "RG", "LG", "YA", "YA2")
N_ROUTE = len(ROUTE_ITEMS)                               # v8: seconds only; the chosen route has its direction
# The mouse pad (2026-10-06): the view is turned by a mouse on a pad of finite width. PAD_DEG degrees of turning
# take the hand from one edge to the other; at the edge it cannot turn further that way: the mouse has to be lifted
# and set back in the middle, PAD_LIFT frames during which the view does not move. He can also lift it himself in
# a quiet moment (action "lift"). Set from the owner's sessions: longest one-way turn 219 degrees (99 in 100 under
# 170), pauses inside long turns 125 ms. Inputs: where the hand is on the pad (-1 to 1), mouse in the air: 2
PAD_DEG, PAD_LIFT = 240.0, 5
N_PAD = 2
# Hearing (2026-10-06): in the game a sound tells where it comes from, whether it is above or below, and whether
# its maker is coming or going. For the nearest enemy heard (running steps, jumps and landings, shots, within
# EAR_RANGE; no line of sight needed): just heard 1, fading 1, direction 2 (sin, cos against his view), above or
# below 1, loudness 1, closing or receding 1: 7. Direction and height are rough (EAR_NOISE degrees, 40 units).
# A railgun or a lightning gun in an enemy's hands hums: heard within HUM_RANGE even when he stands still and does not
# fire, and the hum tells which of the two it is: 2 more inputs.
EAR_RANGE, EAR_NOISE, HUM_RANGE = 1000.0, 10.0, 500.0
N_EAR = 7 + 2
# More of what a player sees and remembers (2026-10-06, after an audit of the inputs):
#   hazards: 8 directions round him at 96 and at 224 units, is the floor there lava (hurts) 16, a deadly drop 16.
#     Only inside his field of view, like the floor readings. Before, a deadly drop read like any ledge.
#   the enemy's last known speed and heading, kept for 5 s after he is lost from view: 3
#   where the nearest jump pad lands: 3
#   his own two nearest projectiles in flight: place 3, speed 3, kind 3, each: 18
HAZ_DIST = (96.0, 224.0)
N_MORE = 32 + 3 + 3 + 18
# A denser picture of the view (an experiment, off unless the environment variable DENSE_VIEW is 1): 9 x 5 distances
# across his view where the standard picture has 5 x 3, for reading cover, doorways and corners. Not in any run yet.
DENSE_YAW, DENSE_PITCH = np.radians(np.linspace(-48, 48, 9)), np.radians(np.linspace(-30, 30, 5))
N_DENSE = len(DENSE_YAW) * len(DENSE_PITCH) if os.environ.get("DENSE_VIEW") == "1" else 0
# The intention as an input (see INTENTS): the chosen way's seconds 1, next step 3, the item up 1, seconds until it
# comes back 1, which intention 6, seconds since chosen 1; and the map cells (v8): the 64-unit cell of the map he
# stands in and the one the enemy was last known in, as numbers for a learned table (the network keeps 16 learned
# numbers per cell: what that place is like). 0 = unknown. Always the last two inputs (CELL_COLS).
# (v9, 2026-10-06) The two cell numbers are replaced by what the map reader says about the two cells (16 numbers each,
# sim/map_reader.py, cached per map in data/maps/cells_<map>.npy; zeros without the file). Also new: item respawn
# sounds (mega, red, a weapon, a small health or armor came back within earshot: 4) and the four nearest spawn
# points (where he is from each: 12).
N_INTENT = 13 + 32 + 4 + 2                                 # (+ 4 since v12: his playing style, see STYLES; + 2 since v13: going for a yellow armor)
N_V9 = 4 + 12
MAX_CELLS, CELL_SIZE = 16384, 64.0                        # enough cells for the big maps (v9; the table is a file, not weights)
# v0.2 (2026-10-11; docs/runs/MANIFEST_v0.2.md section 2, docs/design/V16_ATTENTION.md: stage A of the attention model),
# the last N_V02 inputs, always there (zeros or "nothing known" where a map has no file). Nothing of the game changes
# with them. Positions are in his own frame (forward, left, up). Five groups, one after the other:
#   the game (V02_GAME, 3): the share of the round's time left; how loud he has been in the last V02_LOUD_T seconds (the
#     events hear() is called with: a frame of running steps counts a frame, a shot with anything but the gauntlet, a
#     jump or a landing V02_LOUD_EVT frames; 1 = heard all the time); he made such a noise in the last second while he
#     believed an enemy within earshot (seen or heard in the last V02_BY_KNOWN seconds, within EAR_RANGE of where he was
#     then). Not "an enemy heard him": that would tell him of an enemy standing still behind a wall.
#   his position (V02_POS, 10): his height above the place he believes the enemy is / 300; his height as a share of the
#     map's standing places below him; from sim/pro_places/<map>_cells.json for the cell (256 x 256 x 128 units) he
#     stands in: how a pro seen standing there fares against what his stack would give anywhere (/ 0.3), its sightings
#     (log, against the map's busiest cell), the pros' weapon in hand there (rockets, rail, lightning), the share of
#     their sightings there that they push, and that the cell has numbers; how many of the eight places below he has a
#     clear line to / 8.
#   the enemy as he believes him (V02_BEL, 21; in a group: the enemy he attends to, a reaction time after his attention
#     turned, as the older inputs of the enemy's place): that he believes anything (seen or
#     heard in the last V02_KNOWN seconds, in this round, and not known dead since) and where (his last known place and
#     a second of his last known movement) / 1500; seconds since he last heard him / 20 (running within HEAR, any sound
#     of hear() or _hear()) and where / 1500; how far he can have got since (400 units a second, to 3000); the way in
#     seconds from where he stands to the believed place, and from there to the mega and to the red armor (/ 15; 1 =
#     none, or nothing believed); the damage dealt to him this life / 200; seconds since his life began (/ 60: since the
#     frag he made or heard, else since the round began) and that the frag is known; how often he heard or saw him take
#     the mega, the red armor, a yellow (or green) armor this life (/ 2); rockets, rail, lightning seen in his hands.
#   the items (V02_ITEMS, 13: the nine SLOTS and the four more items, in the order of their own inputs): seconds since HE
#     last took the item of that slot / 40 (1 = never in this round).
#   the places (V02_SLOTS x V02_PF = 8 x 12): the places of sim/pro_places/<map>.json (where the pros' shots land with
#     nobody in view) nearest to him, nearest first: where / 1500, how far / 2000, a clear line from his eyes (traced every
#     V02_SEE_EVERY frames a player, kept between), how far from the believed place / 1500, the place's share of the pros'
#     blind shots / 15, how often they meet and hit the enemy there / 100, how a pro seen standing there fares / 0.3, that
#     it is the place nearest to the believed one, and that the slot holds a place.
# A sighting reaches them as late as it can reach the older inputs (his reaction time, and a frame for a used-up focus).
# What step() keeps for them, and a game server's plugin must (it calls observe() only): note_noise(), note_take(), the
# reset at a round's start (_v02_round), v02_left; hear(), _hear(), note_death() and _fresh() do their part themselves.
V02_GAME, V02_POS, V02_BEL, V02_SLOTS, V02_PF = 3, 10, 21, 8, 12
V02_ITEMS = len(SLOTS) + N_XITEMS
N_V02 = V02_GAME + V02_POS + V02_BEL + V02_ITEMS + V02_SLOTS * V02_PF
V02_KNOWN, V02_BY_KNOWN, V02_LOUD_T, V02_LOUD_EVT = 20.0, 3.0, 3.0, 8.0
V02_SEE_EVERY, V02_SEE_TOL, V02_SEE_LIFT, V02_WAY_MAX = 8, 24.0, 8.0, 15.0
# Stage B part 2: the last N_B2 inputs, always there (zeros on a map without sim/pro_holds/<map>.json; the same with
# TARGETS on or off, but for "his target"). For each of the map's eight holding places, in the file's order (slot j is
# the intention "place j"), B2_F numbers: where it is in his own frame (forward, left, up) / 1500; the way to it in
# seconds along the walking map / 15, capped at 1 (1 = none; the table of N_V02's ways); the pros' share of holds
# there, per cent / 10, capped at 1; how a pro seen standing there fares against what his stack would give anywhere /
# 0.3, between -1 and 1; that it is his target now; that the slot holds a place.
B2_F = 8
N_B2 = HOLD_SLOTS * B2_F
OBS_DIM = OBS_BASE + N_EXTRA + N_FIGHT + N_MEM + N_ROUTE + N_PAD + N_EAR + N_MORE + N_DENSE + N_V9 + N_INTENT + N_DROP + N_V14 + N_V15 + N_V02 + N_B2 + N_B3
CELL_COLS = None                                           # no learned cell table in the network any more
# Stage B, part 1 (docs/design/V02_STAGE_B.md): what the trainer's --aux lesson is made of. step() gives info["aux"], one row
# a player, as the game truly stands AFTER the step (the frame the returned inputs show) and what happened IN the step.
# Never an input, never paid; nothing in the simulator reads it. "The enemy" is the one his enemy inputs are about: the
# other player of a pair; in a group the one he attends to (in view nearest his crosshair, with nobody in view the one
# seen or heard last: self.foe).
#   en_fwd, en_left, en_up   where the enemy truly is, from him, turned to his facing (forward, left, up: units)
#   en_alive                 1: there is an enemy to place (he is alive, and the round has other players: not an item
#                            run, a jump run, a movement round, a course). Everybody is back on the map in the frame he
#                            dies, so in a game this is 1
#   en_in_view               1: he is in view (the simulator's own `visible`: inside his view cone with a clear line; not
#                            delayed by his reaction time as the inputs are)
#   mega_s, red_s            the true seconds until the mega and the red armor are back (0: lying there; AUX_ITEM_CAP:
#                            the map has none)
#   dmg_dealt, dmg_taken     in this step: the damage he did to other players; the damage he took from anything (enemies,
#                            his own splash, lava, a fall), health and armor together
#   frag, fragged            in this step: he made a frag (of another player); another player made a frag of him
#   x, y, z, yaw, pitch      his own place in the world and his view (degrees; yaw -180 to 180, pitch down is plus), so
#                            that a later place can be turned into this frame's view
#   died                     in this step: he died of anything (a frag, his own rocket, lava, the void) and is back at a
#                            spawn: his life's hindsight ends here (a round's end is `done`)
#   eye_h                    the height of his eyes above his place (crouched or not)
AUX_COLS = ("en_fwd", "en_left", "en_up", "en_alive", "en_in_view", "mega_s", "red_s", "dmg_dealt", "dmg_taken", "frag", "fragged",
            "x", "y", "z", "yaw", "pitch", "died", "eye_h")
AUX_ITEM_CAP = 40.0
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
# AMMO_PACKS=0: no universal ammo packs. The maps carry them next to the normal ammo boxes (7 on Blood Run, 6 on Aerowalk,
# 4 on Lost World), but a duel server does not spawn them: plugins/itemlab.py listed every item of the real game on three
# maps (2026-10-04) and there was none. With them the simulator feeds every gun two to three times the real game's ammo.
# Default: as it was (every run up to v12 and the learning-rate test of 2026-10-08 had them).
AMMO_PACKS = (os.environ.get("AMMO_PACKS") or "1") != "0"
if not AMMO_PACKS:
    del ITEM_DEFS["ammo_pack"]


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class RouteField:
    """a map's walking graph (sim/build_nav.py) -> seconds to each goal and the next step of the way, from anywhere.
    Plain numpy (the Anaconda Python's scipy is broken): the nearest graph point comes from a table over a grid."""
    CELL = 32.0

    def __init__(self, nav_path, goals, pads=(), teles=(), avoid=None, starts=None, drop=None, tele_far=None):
        """avoid: a flag per point of the walking map; no way leads into or out of a flagged point (lava, see LAVA).
        starts: the map's spawn points; the points none of them reaches are dead as well (WALK_FIX). drop: links to
        leave out, as (from, to). tele_far: a teleporter link costs the walk to its entrance, and one that starts
        further than this from the entrance is left out (WALK_FIX: the walking map has such links from 360 to 410
        units away at 0.1 s; the way then "teleported" out of Cure's pool and the walker swam at its wall)."""
        import heapq
        g = json.load(open(nav_path))
        self.nav_path = nav_path
        self.nodes = np.array(g["nodes"], np.float32)
        n = len(self.nodes)
        self.dead = np.zeros(n, bool) if avoid is None else np.asarray(avoid, bool).copy()
        if drop:
            g["edges"] = [e for e in g["edges"] if (e[0], e[1]) not in drop]
        tele_walk = {}
        if tele_far is not None and len(teles):
            tin0 = np.array([c for c, d in teles], np.float32).reshape(-1, 3)
            tout0 = np.array([d for c, d in teles], np.float32).reshape(-1, 3)
            keep = []
            for e in g["edges"]:
                if e[3] == "tele":
                    j = int(np.linalg.norm(tout0 - self.nodes[e[1]], axis=1).argmin())
                    if np.linalg.norm(tout0[j] - self.nodes[e[1]]) < 150.0:
                        d_in = float(np.linalg.norm(tin0[j] - self.nodes[e[0]]))
                        if d_in > tele_far:
                            continue
                        tele_walk[(e[0], e[1])] = d_in / 320.0
                keep.append(e)
            g["edges"] = keep
        if starts is not None and len(starts):
            live_e = [e for e in g["edges"] if not (self.dead[e[0]] or self.dead[e[1]])]
            fwd = [[] for _ in range(n)]
            for a, b, t, kind in live_e:
                fwd[a].append(b)
                if kind == "walk" and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                    fwd[b].append(a)
            for c_, d_ in pads:                               # (the pads' links, as they are added below)
                dx = np.hypot(self.nodes[:, 0] - c_[0], self.nodes[:, 1] - c_[1])
                land = int(np.linalg.norm(self.nodes - np.asarray(d_, np.float32) + np.array([0, 0, 100.0], np.float32), axis=1).argmin())
                for a_ in np.nonzero((dx < 130) & (np.abs(self.nodes[:, 2] - c_[2]) < 48))[0]:
                    fwd[int(a_)].append(land)
            seen = np.zeros(n, bool)
            far_ = np.where(self.dead[:, None], 1e9, self.nodes)
            stack = [int(np.linalg.norm(far_ - np.asarray(p_, np.float32), axis=1).argmin()) for p_ in starts]
            for s0 in stack:
                seen[s0] = True
            while stack:
                u_ = stack.pop()
                for v_ in fwd[u_]:
                    if not seen[v_] and not self.dead[v_]:
                        seen[v_] = True
                        stack.append(v_)
            self.dead |= ~seen
        avoid = self.dead if self.dead.any() else None
        radj, have = [[] for _ in range(n)], set()
        enter = {}                                            # a link that is entered somewhere: (from, to) -> that place
        special = set()                                       # the links that are not plain walking (a jump, a drop, a teleporter, a pad)
        tin = np.array([c for c, d in teles], np.float32).reshape(-1, 3)
        tout = np.array([d for c, d in teles], np.float32).reshape(-1, 3)
        if avoid is not None and np.any(avoid):
            g["edges"] = [e for e in g["edges"] if not (avoid[e[0]] or avoid[e[1]])]
        for a, b, t, kind in g["edges"]:
            d = float(np.linalg.norm(self.nodes[a] - self.nodes[b]))
            radj[b].append((a, 0.1 + tele_walk.get((a, b), 0.0) if kind == "tele" else (d / 320.0 if kind == "walk" else max(t, d / 900.0))))
            have.add((a, b))
            if kind != "walk":
                special.add((a, b))
            if kind == "tele" and len(tin):                   # a teleporter: the entrance of the one that comes out at the link's end
                j = int(np.linalg.norm(tout - self.nodes[b], axis=1).argmin())
                if np.linalg.norm(tout[j] - self.nodes[b]) < 150.0:
                    enter[(a, b)] = tin[j]
        for a, b, t, kind in g["edges"]:                      # flat walking works both ways
            if kind == "walk" and (b, a) not in have and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                radj[a].append((b, float(np.linalg.norm(self.nodes[a] - self.nodes[b])) / 320.0))
        for c_, d_ in pads:                                   # jump pads: from the plate to where it throws him
            dx = np.hypot(self.nodes[:, 0] - c_[0], self.nodes[:, 1] - c_[1])      # (the builder's walkers get thrown off
            on = np.nonzero((dx < 130) & (np.abs(self.nodes[:, 2] - c_[2]) < 48))[0]  # the plate: link from the floor round it)
            land = int(np.linalg.norm(self.nodes - np.asarray(d_, np.float32) + np.array([0, 0, 100.0], np.float32), axis=1).argmin())
            for a_ in on:
                radj[land].append((int(a_), 1.2 + float(dx[a_]) / 320.0))
                enter.setdefault((int(a_), land), np.asarray(c_, np.float32))      # a jump pad: its plate
                special.add((int(a_), land))
        self.radj = radj
        w = np.array([1, 1, 2.0], np.float32)                 # vertical distance counts double
        self.lo = self.nodes.min(0) - 64.0
        dims = np.ceil((self.nodes.max(0) + 64.0 - self.lo) / self.CELL).astype(int)
        self.dims = dims
        self.table = self._grid(nav_path, dims, w)
        self.goals = np.array(goals, np.float32).reshape(-1, 3)
        G = len(self.goals)
        self.T = np.full((G, n), 1e9, np.float32)
        self.next = np.full((G, n), -1, np.int32)
        for gi, gp in enumerate(self.goals):
            b = int(self.locate(gp[None])[0])
            dist, pq = {b: 0.0}, [(0.0, b)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c in radj[u]:
                    if d + c < dist.get(v, 1e18):
                        dist[v] = d + c
                        self.next[gi, v] = u
                        heapq.heappush(pq, (d + c, v))
            for v, d in dist.items():
                self.T[gi, v] = d
        # Where the step toward a goal goes through a jump pad or a teleporter, the place to head for is the plate or the
        # entrance, not the point it takes him to: until 2026-10-08 the walker (the walking teacher, the scripted item
        # runner) and the "next step" inputs aimed at the far point, through the wall or up the tower.
        self.via = np.full((G, n, 3), np.nan, np.float32)
        self.move = np.zeros((G, n), bool)                    # the step toward the goal from here is not plain walking
        self._enter, self._special = enter, special           # (kept for linked())
        for gi in range(G):
            for a_ in np.nonzero(self.next[gi] >= 0)[0]:
                k_ = (int(a_), int(self.next[gi, a_]))
                e_ = enter.get(k_)
                if e_ is not None:
                    self.via[gi, a_] = e_
                self.move[gi, a_] = k_ in special

    def add_goals(self, points):
        """more goals (TARGETS: a map's holding places): their rows of T, next, via, move, of the step to take (walk) and
        of pro_step, worked out from the walking map as the first ones' were. T_walk, a scripted walker's ways to the
        items, keeps its rows. Returns the first new row. A field made by linked() after this has the rows too."""
        import heapq
        pts = np.array(points, np.float32).reshape(-1, 3)
        g0, n = len(self.goals), len(self.nodes)
        T = np.full((len(pts), n), 1e9, np.float32)
        nxt = np.full((len(pts), n), -1, np.int32)
        via = np.full((len(pts), n, 3), np.nan, np.float32)
        move = np.zeros((len(pts), n), bool)
        for gi, gp in enumerate(pts):
            b = int(self.locate(gp[None])[0])
            dist, pq = {b: 0.0}, [(0.0, b)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c in self.radj[u]:
                    if d + c < dist.get(v, 1e18):
                        dist[v] = d + c
                        nxt[gi, v] = u
                        heapq.heappush(pq, (d + c, v))
            for v, d in dist.items():
                T[gi, v] = d
            for a_ in np.nonzero(nxt[gi] >= 0)[0]:
                k_ = (int(a_), int(nxt[gi, a_]))
                e_ = self._enter.get(k_)
                if e_ is not None:
                    via[gi, a_] = e_
                move[gi, a_] = k_ in self._special
        own_walk = getattr(self, "walk", None) is not None and self.walk is not self.next
        self.goals = np.concatenate([self.goals, pts])
        self.T = np.concatenate([self.T, T])                 # (a new array: T_walk, where it was this one, keeps the items' rows)
        self.next = np.concatenate([self.next, nxt])
        self.via = np.concatenate([self.via, via])
        self.move = np.concatenate([self.move, move])
        if getattr(self, "walk", None) is not None:
            self.walk = np.concatenate([self.walk, nxt]) if own_walk else self.next
        if getattr(self, "pro_step", None) is not None:
            self.pro_step = np.concatenate([self.pro_step, np.zeros(T.shape, bool)])
        return g0

    def linked(self, links, jumps):
        """a copy of this field whose ways also take the pros' jumps (sim/jump_links.py; links: from, to, seconds, jump).
        Its T, next, via and move are worked out again from the walking map and the links; jlink is the jump a point's
        next step is (-1: a plain step), jd and ji the first jump ahead on the way from every point (the units of way to
        its take-off, which jump)."""
        import copy
        import heapq
        X = copy.copy(self)
        n, G = len(self.nodes), len(self.goals)
        radj, jl = [list(l_) for l_ in self.radj], {}
        for a, b, t, k in links:
            radj[b].append((int(a), float(t)))
            jl[(int(a), int(b))] = int(k)
        X.radj, X.jumps, X._fwd, X._from = radj, list(jumps), None, {}
        X._jl = jl                                           # (WAYS: sim/ways.py reads it)
        X.T = np.full((G, n), 1e9, np.float32)
        X.next = np.full((G, n), -1, np.int32)
        for gi, gp in enumerate(self.goals):
            b = int(self.locate(gp[None])[0])
            dist, pq = {b: 0.0}, [(0.0, b)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c in radj[u]:
                    if d + c < dist.get(v, 1e18):
                        dist[v] = d + c
                        X.next[gi, v] = u
                        heapq.heappush(pq, (d + c, v))
            for v, d in dist.items():
                X.T[gi, v] = d
        X.via = np.full((G, n, 3), np.nan, np.float32)
        X.move = np.zeros((G, n), bool)
        X.jlink = np.full((G, n), -1, np.int32)
        for gi in range(G):
            for a_ in np.nonzero(X.next[gi] >= 0)[0]:
                k_ = (int(a_), int(X.next[gi, a_]))
                if k_ in jl:
                    X.jlink[gi, a_], X.move[gi, a_] = jl[k_], True
                    continue
                e_ = self._enter.get(k_)
                if e_ is not None:
                    X.via[gi, a_] = e_
                X.move[gi, a_] = k_ in self._special
        la = [JL.look_ahead(X.next[gi], X.jlink[gi], self.nodes) for gi in range(G)]
        X.jd, X.ji = np.stack([x[0] for x in la]), np.stack([x[1] for x in la])
        X.pro_step = np.zeros((G, n), bool)
        return X

    def add_ways(self, gi, tm, nx):
        """the pros' way to goal gi where the walking map has none (PRO_WAYS). tm, nx: their seconds to it and their next
        point from each point (1e9 / -1 where they never passed). A point counts only if following their steps from it
        ends on a point that has a way; from the other points without a way, the walk to the best of those. Returns how
        many points got a way."""
        import heapq
        tm, nx = np.asarray(tm, np.float32), np.asarray(nx, np.int64)
        no = (self.T[gi] >= 1e8) & ~self.dead
        dist = {}
        for q in np.nonzero(no & (tm < 1e8) & (nx >= 0))[0]:
            u, hops = int(q), 0
            while hops < 400 and no[u] and tm[u] < 1e8 and nx[u] >= 0 and not self.dead[u]:
                u, hops = int(nx[u]), hops + 1
            if not no[u] and not self.dead[u]:               # their steps end on a point with a way of its own
                dist[int(q)] = float(tm[q])
        if not dist:
            return 0
        pred = {}
        pq = [(d, q) for q, d in dist.items()]
        heapq.heapify(pq)
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            for v, c in self.radj[u]:
                if no[v] and d + c < dist.get(v, 1e18):
                    dist[v] = d + c
                    pred[v] = u
                    heapq.heappush(pq, (d + c, v))
        for v, d in dist.items():
            self.T[gi, v] = d
            if v in pred:
                self.next[gi, v] = pred[v]
            else:
                self.next[gi, v] = int(nx[v])
                self.pro_step[gi, v] = True
                self.move[gi, v] = True
        return len(dist)

    def _grid(self, nav_path, dims, w):
        """nearest node for every grid cell. Cached beside the walking map, or in $ROUTE_CACHE (the game server's map
        folder is read-only): building it took minutes on a big map (2026-10-06, Blood Run froze the server for the
        duration). Built in two passes: every node claims the cells within 256 units of it, the cells left (outside
        the walkable space) by brute force in chunks."""
        idx = np.nonzero(~self.dead)[0] if self.dead.any() else np.arange(len(self.nodes))   # the dead points are never "the nearest"
        nodes = self.nodes[idx]
        n = len(nodes)
        key = "{}x{}x{}_{}_{}".format(dims[0], dims[1], dims[2], n, int(self.CELL))
        ext = ".grid.npz"
        if self.dead.any():                                  # its own file: the plain table is another run's
            import zlib
            key += "_live{}".format(zlib.crc32(self.dead.tobytes()) & 0xffffffff)
            ext = ".grid_live.npz"
        paths = [nav_path + ext]
        if os.environ.get("ROUTE_CACHE"):
            paths.insert(0, os.path.join(os.environ["ROUTE_CACHE"], os.path.basename(nav_path) + ext))
        for p in paths:
            try:
                z = np.load(p)
                if str(z["key"]) == key:
                    return z["table"]
            except (OSError, KeyError, ValueError):
                pass
        dims = np.asarray(dims, np.int64)
        cx = [self.lo[k] + (np.arange(dims[k]) + 0.5) * self.CELL for k in range(3)]
        tf = np.full(int(np.prod(dims)), -1, np.int64)
        bf = np.full(int(np.prod(dims)), np.inf, np.float32)
        R = int(256 // self.CELL)
        off = np.stack(np.meshgrid(*[np.arange(-R, R + 1)] * 3, indexing="ij"), -1).reshape(-1, 3)
        base = ((nodes - self.lo) / self.CELL).astype(np.int64)
        for s0 in range(0, n, 1024):
            nd = np.arange(s0, min(n, s0 + 1024))
            cells = base[nd][:, None, :] + off[None, :, :]
            ok = ((cells >= 0) & (cells < dims)).all(2)
            ci = np.clip(cells, 0, dims - 1)
            centers = np.stack([cx[0][ci[..., 0]], cx[1][ci[..., 1]], cx[2][ci[..., 2]]], -1)
            d2 = np.where(ok, (((centers - nodes[nd][:, None, :]) * w) ** 2).sum(2), np.inf).astype(np.float32).ravel()
            flat = ((ci[..., 0] * dims[1] + ci[..., 1]) * dims[2] + ci[..., 2]).ravel()
            np.minimum.at(bf, flat, d2)
            hit = np.isfinite(d2) & (d2 == bf[flat])
            tf[flat[hit]] = np.repeat(nd, off.shape[0])[hit]
        rest = np.nonzero(tf < 0)[0]
        if len(rest):
            pts = np.stack(np.unravel_index(rest, tuple(dims)), 1)
            P = np.stack([cx[0][pts[:, 0]], cx[1][pts[:, 1]], cx[2][pts[:, 2]]], 1) * w
            nw = nodes * w
            for c0 in range(0, len(rest), 512):
                d2 = ((P[c0:c0 + 512, None, :] - nw[None, :, :]) ** 2).sum(2)
                tf[rest[c0:c0 + 512]] = d2.argmin(1)
        table = idx[tf].reshape(tuple(dims)).astype(np.int32)
        for p in paths:
            try:
                np.savez(p, table=table, key=key)
                break
            except OSError:
                continue
        return table

    def locate(self, pos):
        c = np.clip(((pos - self.lo) / self.CELL).astype(np.int64), 0, self.dims - 1)
        return self.table[c[:, 0], c[:, 1], c[:, 2]]

    def from_node(self, a):
        """seconds from point a to every point of the walking map (worked out once per point and kept)"""
        if getattr(self, "_fwd", None) is None:
            self._fwd, self._from = [[] for _ in range(len(self.nodes))], {}
            for b_, lst in enumerate(self.radj):
                for a_, c_ in lst:
                    self._fwd[a_].append((b_, c_))
        t = self._from.get(a)
        if t is None:
            import heapq
            dist, pq = {a: 0.0}, [(0.0, a)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, 1e18):
                    continue
                for v, c in self._fwd[u]:
                    if d + c < dist.get(v, 1e18):
                        dist[v] = d + c
                        heapq.heappush(pq, (d + c, v))
            t = np.full(len(self.nodes), 1e9, np.float32)
            t[list(dist)] = list(dist.values())
            self._from[a] = t
        return t

    def nearest(self, points):
        """seconds from every graph point to the nearest of these places (1e9 where there is no way)"""
        import heapq
        out = np.full(len(self.nodes), 1e9, np.float32)
        pq = []
        for b in sorted({int(b) for b in self.locate(np.asarray(points, np.float32).reshape(-1, 3))}):
            out[b] = 0.0
            pq.append((0.0, b))
        while pq:
            d, u = heapq.heappop(pq)
            if d > out[u]:
                continue
            for v, c in self.radj[u]:
                if d + c < out[v]:
                    out[v] = d + c
                    heapq.heappush(pq, (d + c, v))
        return out

    def ways(self, far=15.9):
        """the seconds of way between any two points of the walking map (N_V02: the way to where he believes the enemy
        is): W[b, a] is the way from a to b in sixteenths of a second, 255 = none or more than far seconds. Worked out
        once (a search from every point: half a minute on a big map) and kept in a file beside the walking map, or in
        $ROUTE_CACHE, named by a check sum of the links: another set of switches has another file."""
        import heapq
        import zlib
        n = len(self.nodes)
        flat = np.array([(u, v, int(round(c * 1000.0))) for u, l_ in enumerate(self.radj) for v, c in l_], np.int64).reshape(-1, 3)
        key = "{}_{:08x}_{}".format(n, zlib.crc32(flat.tobytes()) & 0xffffffff, int(round(far * 16)))
        name = os.path.basename(self.nav_path) + ".ways_" + key + ".npz"
        dirs = [os.path.dirname(os.path.abspath(self.nav_path))]
        if os.environ.get("ROUTE_CACHE"):
            dirs.insert(0, os.environ["ROUTE_CACHE"])
        for d_ in dirs:
            try:
                z = np.load(os.path.join(d_, name))
                if str(z["key"]) == key and z["ways"].shape == (n, n):
                    return z["ways"]
            except (OSError, KeyError, ValueError):
                pass
        W = np.full((n, n), 255, np.uint8)
        radj, push, pop = self.radj, heapq.heappush, heapq.heappop
        for b in range(n):
            if self.dead[b]:
                continue
            dist, pq = {b: 0.0}, [(0.0, b)]
            while pq:
                d, u = pop(pq)
                if d > dist[u]:
                    continue
                for v, c in radj[u]:
                    nd = d + c
                    if nd <= far and nd < dist.get(v, 1e18):
                        dist[v] = nd
                        push(pq, (nd, v))
            W[b, np.fromiter(dist.keys(), np.int64, len(dist))] = np.minimum(
                np.rint(np.fromiter(dist.values(), np.float64, len(dist)) * 16.0), 254.0).astype(np.uint8)
        for d_ in dirs:
            try:
                tmp = os.path.join(d_, "{}.{}.tmp.npz".format(name, os.getpid()))
                np.savez_compressed(tmp, ways=W, key=key)
                os.replace(tmp, os.path.join(d_, name))
                break
            except OSError:
                continue
        return W


class DuelEnv:
    def __init__(self, bsp, n_matches=256, seed=0, substeps=(8, 8, 9), dmg_reward=0.004, nav=None, close_p=0.0,
                 loadout="full", drill_weapons=(RL, RG, LG), teacher=None):
        """close_p: chance a respawn lands 300-700 units from the opponent with line of sight (curriculum).
        loadout: weapons at spawn ("full" = RL/RG/LG, "all" = every weapon, "mg" = machine gun + gauntlet only).
        drill_p (attribute): share of rounds where both players have exactly one weapon from drill_weapons."""
        self.M = n_matches
        self.n = 2 * n_matches                          # player i's opponent is i ^ 1
        self.w = World(bsp, n=self.n)
        self.new_lib = bool(getattr(self.w, "new", False))  # the simulator library of 2026-10-09 (masks, many contents, ...)
        assert self.new_lib or not SHOT_MASK, "SHOT_MASK needs the simulator library of 2026-10-09"
        self.sight = SOLID_ONLY if SHOT_MASK else None      # the mask of shots, missiles, splash and sight (None: the player's)
        assert self.new_lib or not LAVA, "LAVA needs the simulator library of 2026-10-09"
        assert self.new_lib or not (QL_MOVE or SOLIDS), "QL_MOVE and SOLIDS need the simulator library of 2026-10-09"
        if self.new_lib:                                     # (the library keeps these between worlds of one process: set both ways)
            from qsim import QL_STEP, QL_WADE
            self.w.set_params2(QL_WADE, QL_STEP) if QL_MOVE else self.w.set_params2()
            self.w.add_solids() if SOLIDS else self.w.lib.qsim_clear_solids()
        self.lava_t = np.zeros(self.n, np.float32)          # seconds until lava or slime hurts him again (LAVA)
        self.rng = np.random.default_rng(seed)
        self.substeps = tuple(substeps)
        self.dmg_reward = dmg_reward
        self.loadout = loadout
        self.react_frames = REACT_FRAMES
        self.acquire_frames = ACQUIRE_FRAMES
        self.react_seat = self.acquire_seat = None             # (SEAT_DELAYS) one a seat, in a check of two networks
        self.vis_run = np.zeros(2 * n_matches, np.int64)       # frames the opponent has been in view without a break
        self.acquired = np.zeros(2 * n_matches, bool)          # in view long enough to have been noticed
        self.acq_extra = np.zeros(2 * n_matches, np.int64)     # frames more this time, by surprise (surprise_frames)
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
        self.runner_p = float(os.environ.get("RUNNER_P") or 0.0)   # ... where he is the item runner (script 3, see _runner_keys)
        self.item_run_p = float(os.environ.get("ITEM_RUN_P") or 0.0)   # share of the playing time in item runs (see RUN_LEN)
        self.aim_weapons = (LG, LG, LG, RG, RG, RL, PG, SG, MG)
        self.sg_spawn = True                            # False: nobody spawns holding a shotgun in normal rounds
        self.script = np.zeros(2 * n_matches, np.int64)  # per player: 0 = policy, 1 = strafing target, 2 = scripted fighter
        self.sc_t = np.zeros(2 * n_matches, np.float32)
        self.sc_dir = np.ones(2 * n_matches, np.int64)
        self.sc_fwd = np.zeros(2 * n_matches, np.int64)
        self.sc_jump = np.zeros(2 * n_matches, bool)
        self.sc_stuck = np.zeros(len(self.sc_t), np.int64)  # the runner: frames without getting anywhere
        self.hunt_t = np.zeros(len(self.sc_t), np.float32)  # TRICKS, the holder: seconds left of coming for him after a frag
        self.x_goal = np.full(len(self.sc_t), -1, np.int64)  # ... a place that is not an item he walks to (index into xpts)
        self.watch_t = np.zeros(len(self.sc_t), np.float32)  # ... the watcher: seconds left at this post
        self.sc_look = np.zeros(len(self.sc_t), bool)       # ... he looks at what he remembers though nobody is in view
        self.hold_ahead = np.zeros(len(self.sc_t), bool)    # ... the holder starts this round ahead (HOLD_STACK); used up at his first spawn
        self.route_x, self.xpts, self.x_watch = None, None, {}
        self.run_k = np.full(len(self.sc_t), -1, np.int64)  # item run: the intention he is given (0 = none yet), -1 = not in one
        self.run_stuck = np.zeros(len(self.sc_t), np.int64) # item run: frames without getting anywhere (for the walking teacher)
        self.collect_fight_p = float(os.environ.get("COLLECT_FIGHT_P") or 0.0)   # share of the item runs that end in a fight (RUN_COLLECT)
        self.cf_t = np.full(n_matches, -1.0, np.float32)    # seconds until this match's item run turns into a fight (-1: none)
        self.cf_side = np.zeros(len(self.sc_t), np.int64)   # in that fight: 1 = kept what he gathered, 2 = put back to a plain spawn
        self.drill_mix_p = float(os.environ.get("DRILL_MIX_P") or 0.0)           # share of the one-weapon drills with the machine gun too
        self.drill_mix = np.zeros(n_matches, bool)
        self.intent_gone = np.zeros(len(self.sc_t), bool)   # the chosen item is not there and will not be in time: free to choose again
        self.sc_persona = np.zeros(2 * n_matches, np.int64)   # scripted fighter style (PERSONAS)
        self.sc_wpn = np.zeros(2 * n_matches, np.int64)
        self.persona_p = np.array([1.0 / NIGHTMARE] * NIGHTMARE + [0.0] * (len(PERSONAS) - NIGHTMARE))   # (the stand-in is never drawn)
        self.persona_force = None                       # test rooms: always this style
        self.move_len = 40.0                            # seconds per movement round (several goals in a row)
        # movement teacher: a movement-only policy (sim/train_move.py) whose actions are offered as labels in
        # movement rounds (self.teach: forward, strafe, jump, turn bin; -1 = no label)
        self.teacher = None
        self.teach = np.full((2 * n_matches, 5), -1, np.int64)      # (the fifth: the weapon key by the weapon rule, -1 = no label)
        nn_ = 2 * n_matches
        self.duck = np.zeros(nn_, bool)                 # crouched (smaller box, lower eye)
        self.frags_r = np.zeros(nn_, np.float32)        # frags in the current round (the score)
        self.snd_t = np.full((nn_, 4), 99.0, np.float32)    # seconds since heard: pickup, weapon fire, jump, teleport
        self.snd_pos = np.zeros((nn_, 4, 3), np.float32)
        self.snd_kind = np.zeros(nn_, np.int64)         # last pickup heard: 0 mega, 1 red armor, 2 other armor, 3 weapon
        self.fb = np.zeros((nn_, 4), np.float32)        # this frame: damage dealt, damage taken, direction it came from
        self.dmg_life = np.zeros(nn_, np.float32)       # damage dealt to the opponent during his current life
        name = os.path.splitext(os.path.basename(bsp))[0].lower()
        self.w_table = None                                 # the pros' weapon by distance (PRO_WEAPON): (15, 3) rockets, rail, lightning
        ps_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_seed.json")
        if PRO_WEAPON and os.path.exists(ps_):
            with open(ps_, encoding="utf-8") as f_:
                tb_ = json.load(f_)
            tb_ = tb_.get(name) or tb_.get("all")
            if tb_:
                self.w_table = np.array(tb_["weapon_by_100_units"], np.float32)
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
        if ITEM_DROP:                                        # as the game's FinishSpawningItem: dropped unless "suspended"
            for k_, e_ in enumerate(ents):
                if int(float(e_.get("spawnflags", 0) or 0)) & 1:
                    continue
                tr_ = self.w.trace(self.item_pos[k_], self.item_pos[k_] - np.array([0, 0, 4096.0], np.float32),
                                   mins=(-15, -15, -15), maxs=(15, 15, 15), mask=SOLID_ONLY)
                if not tr_["startsolid"] and tr_["fraction"] < 1.0:
                    self.item_pos[k_] = tr_["endpos"]
        self.item_def = [ITEM_DEFS[e["classname"]] for e in ents]
        self.nI = len(ents)
        self.item_up = np.ones((n_matches, self.nI), bool)
        self.item_t = np.zeros((n_matches, self.nI), np.float32)        # seconds until it respawns
        self.drop_pos = np.zeros((n_matches, DROP_MAX, 3), np.float32)  # weapons that dead players left (see DROPS):
        self.drop_w = np.full((n_matches, DROP_MAX), -1, np.int64)      # which weapon (-1: nothing in that slot)
        self.drop_t = np.zeros((n_matches, DROP_MAX), np.float32)       # seconds until it is gone
        self.slot_items = [[k for k, d in enumerate(self.item_def) if d[4] == lab] for lab in SLOTS]
        # Weapons that lie on this map: nobody spawns with a weapon the map does not have (no heavy machine gun
        # on Aerowalk, for instance). A map without weapon pickups (the test map) allows all.
        self.map_weapons = sorted({int(d[1]) for d in self.item_def if d[0] == "wp"}) or             [k for k in range(NW) if k != HMG]              # no heavy machine gun: most duel maps do not have one
        # more items as inputs: second yellow armor, three nearest 25/50 healths, two nearest bubbles or shards,
        # two nearest ammo boxes
        ya = [k for k, d in enumerate(self.item_def) if d[4] == "YA"]
        hl = [k for k, d in enumerate(self.item_def) if d[0] == "hp" and d[1] in (25, 50)]
        sm = [k for k, d in enumerate(self.item_def) if d[0] in ("hp", "ar") and d[1] == 5]
        am = [k for k, d in enumerate(self.item_def) if d[0] in ("am", "pack")]
        self.xslots = [(hl, 0), (hl, 1), (sm, 0), (sm, 1)]
        # teleporter entrances with their exits, and jump pads (from the map's trigger brushes)
        spots = self.w.trigger_spots() if hasattr(self.w, "trigger_spots") else []
        self.tele_in = np.array([c for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
        self.tele_out = np.array([d for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
        self.pads = np.array([c for k, c, d in spots if k == 0], np.float32).reshape(-1, 3)
        self.pad_dest = np.array([d for k, c, d in spots if k == 0], np.float32).reshape(-1, 3)
        va, vp = np.radians([-40, -20, 0, 20, 40]), np.radians([-25, 0, 25])
        self.view_grid = np.array([(y, q) for q in vp for y in va], np.float32)        # yaw, pitch offsets
        self.up_dirs = np.array([[0, 0, 1.0]] + [[math.cos(t) * 0.7071, math.sin(t) * 0.7071, 0.7071]
                                                 for t in np.radians([0, 90, 180, 270])], np.float32)
        la = np.linspace(0, 2 * np.pi, N_LONG, endpoint=False)
        self.long_dirs = np.stack([np.cos(la), np.sin(la)], 1).astype(np.float32)
        self.lo, self.hi = [np.asarray(v, np.float32) for v in self.w.bounds()]
        self.cell_n = np.maximum(1, np.ceil((self.hi[:2] - self.lo[:2]) / CELL_SIZE)).astype(np.int64)   # map cells (N_INTENT)
        self.cell_zmid = float(self.lo[2] + self.hi[2]) / 2.0
        self.cell_table = None                              # the map reader's 16 numbers per cell (see N_INTENT)
        if nav:
            ct_ = os.path.join(os.path.dirname(nav), "cells_{}.npy".format(os.path.splitext(os.path.basename(bsp))[0]))
            if os.path.exists(ct_):
                self.cell_table = np.load(ct_).astype(np.float32)
        self.resp_t = np.full(self.n, 99.0, np.float32)[:, None].repeat(4, 1)   # seconds since an item respawn was heard: mega, red, weapon, small
        # Test map ("lab"): fixed rooms described in maps/<map>/rooms.json (tools/make_lab_map.py). On such a map
        # every round is a lab room: an aim room (fixed placement, walking or jumping target) or a movement course.
        # New courses added to the map file are picked up here without code changes.
        self.lab, self.courses = None, []
        for cand in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maps", name, "rooms.json"),
                     os.path.join("/ql/maps-data", name, "rooms.json")):
            if os.path.exists(cand):
                self.lab = json.load(open(cand))
                break
        # places that hurt (lava) or kill (a void), from the map's rooms.json: x0, y0, z0, x1, y1, z1, damage a second
        # (1000 or more = death). A player is in one when his feet are.
        self.hurt_zones = np.array((self.lab or {}).get("hurt", []), np.float32).reshape(-1, 7)
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
        self.lab_len = np.full(n_matches, 30.0, np.float32)     # length of the lab round each match is in
        self.items_room = np.zeros(nn2, bool)           # player is in the items room (mega health and red armor on timers)
        self.lab_items_p = 0.0                          # chance that a course round is the items room instead
        # Run-and-gun (off unless lab_gun_p > 0): the first player runs a course with a weapon, the second is a
        # target that keeps appearing ahead of him beside the path. Damage pays in proportion to the runner's speed.
        self.lab_gun_p = 0.0
        # Arena (third value of lab_p): the two players of a match fight each other in the aim box or the
        # environment box, with the same one or two random weapons. No room to avoid each other.
        self.arena = np.zeros(n_matches, np.int64)      # 0 = not an arena round, 1 = aim box, 2 = environment box
        self.arena_len = 30.0
        self.arena_rooms = (1, 2)                       # rooms used for arena rounds: 1 = aim box, 2 = environment box
        self.arena_sets = None                          # or a list of weapon sets: each player draws his own (uneven fights)
        self.arena_full_p = 0.5                         # share of arena rounds with the full weapon set (else two random weapons)
        self.percept = np.zeros((self.n, 2), np.float32)  # error on the seen direction to the enemy (yaw, pitch), degrees
        self.percept_sigma = PERCEPT_SIGMA
        self.bearing = np.zeros((self.n, 2), np.float32)    # the true direction to the enemy last frame (yaw, pitch; for PERCEPT_SPEED)
        self.bearing_ok = np.zeros(self.n, bool)
        self.flinch = np.zeros(self.n, np.float32)        # extra error on that direction after being hit, degrees
        ng_ = len(self._mates(0)) + 1                       # players per group
        self.it_t = np.full((self.n, 2), 99.0, np.float32)  # seconds since mega / red armor were last known taken (99 = not known)
        self.bel_t = np.full((self.n, len(ROUTE_ITEMS)), 99.0, np.float32)   # the same for every route goal (ITEM_BELIEF)
        self.bel_prev = None                                # the goals' true state at the last look (to notice a pickup)
        self.bel_tick = 0
        self.e_got = np.zeros((self.n, ng_, 11), np.float32)    # per other player: what he is known to have (see N_MEM)
        self.e_life = np.full((self.n, ng_), 99.0, np.float32)  # per other player: seconds since his last known death
        self.life_t = np.zeros(self.n, np.float32)          # seconds since this player's own respawn
        self.first_wp = np.zeros(self.n, bool)              # has picked a weapon up in this life (statistics)
        self.item_up_t = None                               # per item: seconds it has been lying there
        self.last_vel = np.zeros((self.n, 3), np.float32)   # the enemy's speed and heading when last seen
        self.walk_last = np.zeros(self.n, bool)             # the walk key as the little finger has it
        self.pad = np.zeros(self.n, np.float32)             # the hand on the mouse pad, degrees from the middle
        self.pad_lift = np.zeros(self.n, np.int64)          # frames the mouse is still in the air
        self.pad_on = True
        self.ear = np.zeros((self.n, 4), np.float32)        # last sound heard: direction (world, radians), height, loudness, closing
        self.ear_t = np.full(self.n, 99.0, np.float32)      # seconds since
        self.ear_hum = np.full(self.n, -1, np.int64)        # the humming weapon heard with it (RG, LG) or -1
        self.stack_p = 0.0                                  # v9: share of spawns with a random stack (health 100-200, armor 0-150)
        self.near_item_p = 0.0                              # v9: share of spawns within 2 s of the mega or the red armor
        self.intent_paid = np.zeros(self.n, np.float32)     # what the current trip has paid (taken back if abandoned)
        self.intent_teach = np.zeros(self.n, np.int64)      # what a simple rule would go for (the intention head's teacher)
        self.item_seek = 0.0                                # reward per second of travel gained toward the nearest big item
        self.seek_phi = np.full(self.n, 15.0, np.float32)   # he could use and that is lying there (see step)
        self.route_item = []
        self.intent = np.zeros(self.n, np.int64)            # the intention (see INTENTS)
        self.intent_t = np.zeros(self.n, np.float32)        # seconds since chosen
        self.intent_phi = np.zeros(self.n, np.float32)      # seconds of the way left, last frame
        self.intent_best = np.zeros(self.n, np.float32)     # ... and the least it has been on this trip (only new ground pays)
        self.contest_it = np.full(n_matches, -1, np.int64)  # CONTEST_P: the item this round began as a race for, and the seconds
        self.contest_t = np.full(n_matches, -1.0, np.float32)   # left in which taking it is counted (statistics only)
        self.intent_phi0 = np.ones(self.n, np.float32)      # ... and when the choice was made (the whole way)
        self.intent_live = np.zeros(self.n, bool)           # the head was read this frame
        self.intent_changed = np.zeros(self.n, bool)
        self.intent_new = np.ones(self.n, bool)             # just spawned: read the head at once
        self.intent_done = np.zeros(self.n, bool)           # the chosen item was taken since the choice
        self.int_tick = 0
        self.intent_seek = 0.0                              # reward per second of the chosen way gained
        self.item_loss = 0.5                                # an enemy's mega or red costs this share of its pickup reward
        self.intent_gi = [-1] * len(INTENTS)                # intention -> index into route_goal
        self.intent_more = {}                               # NEAREST: intention -> its route goals, where a kind has several items
        self.route, self.route_goal = None, []              # the ways to the big items (see N_ROUTE)
        if nav and os.path.exists(nav):
            pos_ = {}
            for k_, d_ in enumerate(self.item_def):
                lab_ = d_[4] if d_[4] in ROUTE_ITEMS else (WEAPONS[int(d_[1])].upper() if d_[0] == "wp" else None)
                if lab_ == "YA" and "YA" in pos_ and "YA2" not in pos_:
                    lab_ = "YA2"                             # the second yellow armor of the map
                if lab_ in ROUTE_ITEMS and lab_ not in pos_:
                    pos_[lab_] = self.item_pos[k_]
            self.route_goal = [lab_ for lab_ in ROUTE_ITEMS if lab_ in pos_]
            self.route_item = [next(k_ for k_ in range(self.nI) if np.array_equal(self.item_pos[k_], pos_[lab_]))
                               for lab_ in self.route_goal]
            if NEAREST:                                      # the other big weapons of a kind: goals of their own, same name
                for k_, d_ in enumerate(self.item_def):
                    lab_ = WEAPONS[int(d_[1])].upper() if d_[0] == "wp" else None
                    if lab_ in ("RL", "RG", "LG") and k_ not in self.route_item:
                        self.route_goal.append(lab_)
                        self.route_item.append(k_)
                if len(self.route_goal) > self.bel_t.shape[1]:
                    self.bel_t = np.full((self.n, len(self.route_goal)), 99.0, np.float32)
            if self.route_goal:
                avoid_ = None
                if LAVA:                                     # the points of the walking map that stand in lava or slime
                    nodes_ = np.array(json.load(open(nav))["nodes"], np.float32)
                    avoid_ = (self.w.contents_n(nodes_ + np.array([0, 0, MINS[2] + 1.0], np.float32)) & (C_LAVA | C_SLIME)) != 0
                more_ = dict(avoid=avoid_) if avoid_ is not None else {}
                if WALK_FIX:
                    more_["starts"] = self.spawns
                    more_["tele_far"] = TELE_FAR
                    if getattr(self.w, "solids", None):      # teleporter links whose straight line to the entrance is shut
                        g_ = json.load(open(nav))
                        nd_ = np.array(g_["nodes"], np.float32)
                        tin_ = np.array([c for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
                        tout_ = np.array([d for k, c, d in spots if k == 1], np.float32).reshape(-1, 3)
                        drop_ = set()
                        for a_, b_, t_, kind_ in g_["edges"]:
                            if kind_ == "tele" and len(tin_):
                                j_ = int(np.linalg.norm(tout_ - nd_[b_], axis=1).argmin())
                                if np.linalg.norm(tout_[j_] - nd_[b_]) < 150.0 and self.w.trace(nd_[a_], tin_[j_])["fraction"] < 0.97:
                                    drop_.add((int(a_), int(b_)))
                        more_["drop"] = drop_
                    if LAVA:                                 # jumps and drops whose line passes over lava or slime: left out. A scripted
                        g_ = json.load(open(nav))            # walker lands in it (on Lost World the stand-in died in the lava 2.6 times a
                        nd_ = np.array(g_["nodes"], np.float32)       # game; at Toxicity's acid stone it stood 27% of its time)
                        air_ = [(a_, b_) for a_, b_, t_, kind_ in g_["edges"] if kind_ == "air"]
                        if air_:
                            A_, B_ = nd_[[e_[0] for e_ in air_]], nd_[[e_[1] for e_ in air_]]
                            over_ = np.zeros(len(air_), bool)
                            for f_ in (0.2, 0.35, 0.5, 0.65, 0.8):
                                P_ = (A_ + (B_ - A_) * f_).astype(np.float32)
                                P_[:, 2] = np.maximum(A_[:, 2], B_[:, 2]) + 8.0
                                fr_ = self.w.rays(P_, np.array([[0, 0, -1.0]], np.float32), 600.0)[:, 0]
                                end_ = P_.copy()
                                end_[:, 2] -= fr_ * 600.0 - 4.0
                                over_ |= (fr_ < 1.0) & ((self.w.contents_n(end_) & (C_LAVA | C_SLIME)) != 0)
                            self.over_hazard = int(over_.sum())
                            more_["drop"] = set(more_.get("drop", ())) | {e_ for e_, o_ in zip(air_, over_) if o_}
                self.route = RouteField(nav, [self.item_pos[k_] for k_ in self.route_item],
                                        pads=[(c, d) for k, c, d in spots if k == 0], teles=[(c, d) for k, c, d in spots if k == 1],
                                        **more_)
                self.intent_gi = [-1] + [self.route_goal.index(lab_) if lab_ in self.route_goal else -1 for lab_ in INTENTS[1:]]
                self.intent_more = {k_: np.array([g_ for g_, l_ in enumerate(self.route_goal) if l_ == INTENTS[k_]], np.int64)
                                    for k_ in range(1, len(INTENTS)) if self.route_goal.count(INTENTS[k_]) > 1}
                self.route.walk = self.route.next            # the step to take: the shortest way's, or the pros' (PRO_ROUTES)
                pr_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_routes", name + ".npz")
                self.route.T_walk = self.route.T             # the ways of the walking map alone (a scripted player's)
                self.route.pro_step = np.zeros(self.route.T.shape, bool)   # points whose next step is the pros', not a walk
                if TRICKS:
                    self._trick_points(nav, [(c, d) for k, c, d in spots if k == 0], [(c, d) for k, c, d in spots if k == 1], more_)
                if PRO_WAYS and os.path.exists(pr_):
                    pd_ = np.load(pr_)
                    labs_ = [str(x) for x in pd_["labels"]]
                    if int(pd_["nodes"]) == len(self.route.nodes) and "time" in pd_.files:
                        self.route.T_walk = self.route.T.copy()
                        for g_, lab_ in enumerate(self.route_goal):
                            if lab_ in labs_ and self.route_goal.index(lab_) == g_:   # (the pros' table is the first one's)
                                self.route.add_ways(g_, pd_["time"][labs_.index(lab_)], pd_["next"][labs_.index(lab_)])
                if PRO_ROUTES and os.path.exists(pr_):
                    pd_ = np.load(pr_)
                    labs_ = [str(x) for x in pd_["labels"]]
                    if int(pd_["nodes"]) == len(self.route.nodes):
                        walk_ = np.array(self.route.next).copy()
                        for g_, lab_ in enumerate(self.route_goal):
                            if lab_ in labs_ and self.route_goal.index(lab_) == g_:   # (the pros' table is the first one's)
                                pn_ = pd_["next"][labs_.index(lab_)]
                                walk_[g_] = np.where(pn_ >= 0, pn_, walk_[g_])
                                if "time" in pd_.files:      # places the walking graph has no way from (a jump it lacks)
                                    tm_ = pd_["time"][labs_.index(lab_)]
                                    open_ = (self.route.T[g_] >= 1e8) & (tm_ < 1e8)
                                    self.route.T[g_] = np.where(open_, tm_, self.route.T[g_])
                        self.route.walk = walk_
        # the map's holding places (sim/pro_holds/<map>.json, tools/pro_holds.py), in the file's order: N_B2, TARGETS
        self.hold_pos = np.zeros((0, 3), np.float32)        # where: a point of the walking map
        self.hold_feat = np.zeros((0, 2), np.float32)       # ... the pros' share of holds there / 10, how a pro standing there fares / 0.3
        self.hold_node = np.zeros(0, np.int64)              # ... its point of the walking map (the way to it, as an input)
        self.hold_n, self.hold_g0, self.hold_tg = 0, -1, [] # TARGETS: how many are targets, their first row among the route goals, and as goals of his legs' network
        hf_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_holds", os.path.splitext(os.path.basename(bsp))[0].lower() + ".json")
        if os.path.exists(hf_):
            with open(hf_, encoding="utf-8") as fh_:
                hl_ = (json.load(fh_).get("places") or [])[:HOLD_SLOTS]
            if hl_:
                self.hold_pos = np.array([p_["pos"] for p_ in hl_], np.float32).reshape(-1, 3)
                self.hold_feat = np.array([[min(1.0, max(0.0, float(p_.get("share") or 0.0) / 10.0)),
                                            min(1.0, max(-1.0, float(p_.get("outcome_over_expected") or 0.0) / 0.3))] for p_ in hl_], np.float32)
                if self.route is not None:
                    self.hold_node = np.asarray(self.route.locate(self.hold_pos), np.int64)
                    if TARGETS:
                        self.hold_g0 = self.route.add_goals(self.hold_pos)
                        assert self.hold_g0 == len(self.route_item)
                        self.hold_n = len(self.hold_pos)
                        for j_ in range(self.hold_n):
                            self.intent_gi[HOLD_INTENT + j_] = self.hold_g0 + j_
                        self.hold_tg = [[float(x_) for x_ in p_] for p_ in self.hold_pos]
        self.jumps, self.route_j, self.jump_tries = [], None, {}     # JUMPS: the pros' jumps, his ways with them, jump -> [(goal, start points, ways)]
        self.jfields = []                                   # ... the sets of ways of a jump run's players (0: route_j; JUMP_ALL: one more a jump)
        self.jrun_f = np.zeros(self.n, np.int64)            # ... which of them his try has
        self.jrun_past = np.zeros(self.n, bool)             # ... he has landed at the jump's landing (over it or not): the item is the goal
        self.jump_lab_off = np.zeros(0, bool)               # ... per jump: no teacher's labels before its landing (sim/jump_labels.json)
        self.jump_run_p = float(os.environ.get("JUMP_RUN_P") or 0.0)  # share of the playing time in jump runs
        self.jrun = np.zeros(self.n, bool)                  # in a jump run
        self.jrun_k = np.zeros(self.n, np.int64)            # ... the jump his try is for
        self.jrun_t = np.zeros(self.n, np.float32)          # ... the seconds the try has left
        self.jrun_edge = np.zeros(self.n, bool)             # ... he has been at its take-off
        self.jrun_over = np.zeros(self.n, bool)             # ... he is over it
        self.jrun_new = np.zeros(self.n, bool)              # ... the try began this frame
        self.jrun_it = np.full(self.n, -1, np.int64)        # ... the item that is its target
        self.jrun_paid = np.zeros(self.n, np.float32)       # ... what its way has paid so far (given back if it ends without the item)
        self._replaced = False                              # a try began inside this step: the state is read again at its end
        self.count_even = False                             # the jump counters count the even seats only (the trainer: those are always his)
        self.spam_places = np.zeros((0, 3), np.float32)     # BLIND_PLACES: where the pros' blind shots land on this map
        if BLIND_PLACES > 0:
            f_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_places", os.path.splitext(os.path.basename(bsp))[0] + ".json")
            if os.path.exists(f_):
                import json as json_
                self.spam_places = np.array([p_["pos"] for p_ in json_.load(open(f_))["places"]], np.float32).reshape(-1, 3)
        self.legs = np.zeros(self.n, bool)                  # LEGS: his switch as it stands (his legs, not his own movement),
        self.legs_on = np.zeros(self.n, bool)               # ... the movement network moved him this frame,
        self.legs_live = np.zeros(self.n, bool)             # ... the switch was read this frame
        self.legs_tick = 0
        self.legs_no = np.zeros(self.n, np.int64)           # ... readings of "my own movement" in a row (LEGS_OFF)
        self.legs_lab = np.full((self.n, 4), -1, np.int8)   # LEGS_LABEL: the movement network's four choices of this frame (-1: no label)
        self.legs_wh = np.zeros(self.n, bool)               # LEGS_KEEP: this frame a withheld stretch has a label (his own outputs moved him),
        self.legs_held = np.zeros(self.n, bool)             # ... the stretch he is in is withheld,
        self.legs_was = np.zeros(self.n, bool)              # ... his switch a frame ago (a stretch begins where it turns on),
        self.legs_keep_who = np.ones(self.n, bool)          # ... the seats stretches are withheld from, and the counters are of,
        self.rng_keep = np.random.default_rng([abs(int(seed)), 0xC1])    # ... the draws' own random stream,
        self.legs_run = np.zeros(self.n, np.int64)          # ... his frames with a label in a row (the counters' run),
        self.legs_sp0 = np.zeros(self.n, np.float32)        # ... his speed over the ground as that run began
        self.teach_runs = "all"                             # the key labels of this map's runs (the trainer's --teacher-skip): "all";
        #   "jump": none in item runs, the movement teacher's in jump runs; "none": none (a map its pupil fails on)
        self.jump_a = self.jump_b = np.zeros((0, 3), np.float32)
        self.route_o = None                                  # JUMP_OPEN: his ways outside jump runs, with the jumps that are open
        open_ = {}
        for part_ in JUMP_OPEN.split(";"):
            if ":" in part_:
                open_[part_.split(":")[0].strip()] = {int(x_) for x_ in part_.split(":")[1].split(",") if x_.strip()}
        open_ = self.jump_open = open_.get(os.path.splitext(os.path.basename(bsp))[0], set())
        if (JUMPS or open_) and self.route is not None:
            self.jumps = JL.load(os.path.splitext(os.path.basename(bsp))[0], also=open_)
            if self.jumps:
                R_ = self.route
                lk_ = JL.links(self.jumps, R_.nodes, R_.locate, ok=~R_.dead)
                if open_:
                    O_ = self.route_o = R_.linked([l_ for l_ in lk_ if self.jumps[l_[3]]["id"] in open_], self.jumps)
                    O_.walk, O_.T_walk = O_.next, R_.T_walk
            if self.jumps and JUMPS:
                J_ = self.route_j = R_.linked(lk_, self.jumps)
                J_.walk, J_.T_walk = J_.next, R_.T_walk
                self.jump_a = np.array([j_["a"] for j_ in self.jumps], np.float32).reshape(-1, 3)
                self.jump_b = np.array([j_["b"] for j_ in self.jumps], np.float32).reshape(-1, 3)
                for g_, lab_ in enumerate(self.route_goal):
                    same_ = self.intent_more.get(INTENTS.index(lab_), np.array([g_], np.int64))
                    best_ = J_.T[g_] <= J_.T[same_].min(0) + 1e-6       # (the item of its kind his way leads to from there)
                    for k_ in range(len(self.jumps)):
                        st_ = np.nonzero((J_.ji[g_] == k_) & (J_.jd[g_] > JL.run_up(self.jumps[k_]["need"])) & (J_.jd[g_] < 1300.0)
                                         & ~R_.dead & best_)[0]
                        if len(st_):
                            self.jump_tries.setdefault(k_, []).append((g_, st_, 0))
                self.jfields = [J_]
                self.jump_lab_off = np.zeros(len(self.jumps), bool)
                jl_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jump_labels.json")
                if os.path.exists(jl_):
                    off_ = set(json.load(open(jl_)).get("off", {}).get(os.path.splitext(os.path.basename(bsp))[0], []))
                    self.jump_lab_off = np.array([j_["id"] in off_ for j_ in self.jumps], bool)
                for k_ in (range(len(self.jumps)) if JUMP_ALL else ()):      # (see JUMP_ALL: the jump made free on the way to an item)
                    if k_ in self.jump_tries or not any(l_[3] == k_ for l_ in lk_):
                        continue
                    X_ = R_.linked([(a_, b_, 0.1 if q_ == k_ else t_, q_) for a_, b_, t_, q_ in lk_], self.jumps)
                    X_.walk, X_.T_walk = X_.next, R_.T_walk
                    nb_ = int(R_.locate(self.jump_b[k_][None])[0])
                    found_ = []
                    for g_, lab_ in enumerate(self.route_goal):
                        same_ = self.intent_more.get(INTENTS.index(lab_), np.array([g_], np.int64))
                        best_ = X_.T[g_] <= X_.T[same_].min(0) + 1e-6
                        st_ = np.nonzero((X_.ji[g_] == k_) & (X_.jd[g_] > JL.run_up(self.jumps[k_]["need"])) & (X_.jd[g_] < 1300.0)
                                         & ~R_.dead & best_)[0]
                        if len(st_) and X_.T[g_, nb_] < 1e8:
                            found_.append((float(X_.T[g_, nb_]), g_, st_))
                    for _, g_, st_ in sorted(found_, key=lambda f_: f_[0])[:2]:     # (the two items nearest behind the landing)
                        self.jump_tries.setdefault(k_, []).append((g_, st_, len(self.jfields)))
                    if k_ in self.jump_tries:
                        self.jfields.append(X_)
                for k_ in (range(len(self.jumps)) if JUMP_ALL else ()):      # (... and the jumps that still have none: to the landing first)
                    if k_ in self.jump_tries or not any(l_[3] == k_ for l_ in lk_):
                        continue
                    nb_ = int(R_.locate(self.jump_b[k_][None])[0])
                    one_ = [g_ for g_, lab_ in enumerate(self.route_goal)
                            if INTENTS.index(lab_) not in self.intent_more and J_.T[g_, nb_] < 1e8]
                    if not one_:
                        continue
                    g_ = min(one_, key=lambda q_: float(J_.T[q_, nb_]))      # the item nearest behind the landing
                    import copy as copy_
                    Rk_ = copy_.copy(R_)
                    Rk_.goals = np.array(R_.goals, np.float32).copy()
                    Rk_.goals[g_] = self.jump_b[k_]                          # (that item's row: the way to the landing)
                    X_ = Rk_.linked(lk_, self.jumps)
                    X_.walk, X_.T_walk, X_.goals = X_.next, R_.T_walk, R_.goals
                    ok_ = (X_.ji[g_] == k_) & (X_.jd[g_] < 1300.0) & ~R_.dead & (X_.T[g_] < 1e8)
                    far_ = float(X_.jd[g_][ok_].max()) if ok_.any() else 0.0
                    if not ok_.any():
                        continue
                    need_ = JL.run_up(self.jumps[k_]["need"])
                    st_ = np.nonzero(ok_ & (X_.jd[g_] >= (need_ if far_ > need_ else 0.6 * far_)))[0]
                    if not len(st_):
                        continue
                    X_.T[g_] = np.where(X_.T[g_] < 1e8, X_.T[g_] + J_.T[g_, nb_], X_.T[g_]).astype(X_.T.dtype)   # (... and the rest from there)
                    self.jump_tries[k_] = [(g_, st_, len(self.jfields))]
                    self.jfields.append(X_)
        self.way = np.zeros(self.n, np.int64)               # WAYS: his way to his target (0 the shortest, 1 the second set, 2 the third),
        self.way_was = np.zeros(self.n, np.int64)           # ... as it was before this frame's reading,
        self.way_live = np.zeros(self.n, bool)              # ... it was read this frame (with the intention),
        self.way_phi0 = np.ones((self.n, N_WAYS), np.float32)   # ... the whole way by each set when the target was chosen (the pay's scales)
        self.way_field, self.way_plan, self.way_report = None, None, None    # ... the set of ways that has the others beside it; sim/ways.py's plan
        self.t_ways = {}                                    # ... the movement network's own second and third fields (made when first needed)
        self.way_map = os.path.splitext(os.path.basename(bsp))[0].lower()
        if WAYS and self.route is not None:
            self.set_ways()
        self.way_trips = []                                 # WAY_MEASURE: the trips between two places that ended in this step,
        self.wt_from = np.full(self.n, -1, np.int64)        # ... the route goal he took last in this life (-1: none yet),
        self.wt_n = np.zeros(self.n, np.int64)              # ... the points of his path since,
        self.wt_t = np.zeros(self.n, np.float32)            # ... the seconds since,
        self.wt_pts = np.zeros((self.n, WT_MAX, 3), np.float32) if WAY_MEASURE else None
        self.wt_tick = 0
        self.soak = np.zeros(self.n, np.float32)            # damage his armor took this frame (see ARMOR_COST)
        self.pro_air = None                                 # PRO_JUMP: the pros' share of moving time in the air, per cell
        pj_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_jump", os.path.splitext(os.path.basename(bsp))[0] + ".npz")
        if PRO_JUMP and os.path.exists(pj_):
            z_ = np.load(pj_)
            self.pro_air = (z_["air"], z_["lo"], float(z_["zmid"]), float(z_["cell"]))
        self.shot_scarce = np.ones(NW, np.float32)          # SHOT_COST: how scarce each gun's ammo is on this map, and
        self.shot_way = None                                # the seconds to its nearest ammo from every graph point
        if SHOT_COST > 0:
            self._shot_supply()
        self.flinch_on = True
        self.focus = np.full(self.n, FOCUS_SECS, np.float32)   # seconds of sharp tracking left
        self.focus_on = True
        self.vel_frames = VEL_REACT_FRAMES              # delay on the enemy's velocity (see observe)
        self.dmg_taken_w = DMG_TAKEN_W                  # weight of damage taken against damage dealt
        self.key_limits = True                          # finger limits on the movement keys (KEY_HOLD, KEY_RATE)
        self.fov_sight = True                           # geometry only inside the field of view
        self.key_last = np.tile(np.array([1, 1, 0], np.int64), (nn2, 1))    # the key states in effect
        self.key_hold = np.full((nn2, 5), 99, np.int64)                    # frames since each finger last acted
        self.key_tok = np.full(nn2, KEY_BURST, np.float32)                 # budget of key changes
        self.key_req = np.tile(np.array([1, 1, 0, 0], np.int64), (nn2, 1)) # the left hand's standing decision: keys, weapon
        self.key_tick = 0
        self.key_dec = np.ones(nn2, bool)                   # this frame the left hand's outputs were read (see limit_keys)
        self.round_fac = self.rng.uniform(0.67, 1.33, n_matches).astype(np.float32)   # this round's length, as a share of the nominal one
        self.pain_t = np.full(nn2, 99.0, np.float32)    # seconds since this player last heard the enemy's pain sound
        self.pain_b = np.zeros(nn2, np.int64)           # which one: 0 under 25 health, 1 under 50, 2 under 75, 3 above
        self.arena_stack = True                         # arena rounds: random health and armor, the same for both players
        self.arena_hp = np.full(n_matches, SPAWN_HP, np.float32)
        self.arena_ar = np.zeros(n_matches, np.float32)
        self.zoom = np.zeros(nn2, bool)                 # zoomed in
        self.fire_last = np.zeros(nn2, bool)            # the fire button as the finger has it
        self.mouse_hold = np.full((nn2, 2), 99, np.int64)
        self.shot_t = np.full(nn2, 99.0, np.float32)    # seconds since the last enemy shot this player saw or heard
        self.shot_w = np.zeros(nn2, np.int64)           # the weapon of that shot
        self.shot_seen = np.zeros(nn2, bool)            # seen (else only heard)
        self.trail_t = np.full(nn2, 99.0, np.float32)   # seconds since the last enemy bullet / rail / lightning line seen
        self.trail_p = np.zeros((nn2, 3), np.float32)   # the point of that line nearest to this player
        self.no_walk = False                            # True: the walk key does nothing
        self.gun_courses = ("speed", "ramps", "slalom", "turns")
        self.gun = np.zeros(nn2, bool)                  # player is a run-and-gun runner
        self.gun_w = np.zeros(n_matches, np.int64)      # his weapon
        self.gun_tp = np.zeros(n_matches, np.float32)   # how far along the path the target stands
        self.items_len = 120.0
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
                                         end_z=c_.get("end_z"), weapon=c_.get("weapon", "g"), length=float(cum[-1]),
                                         mortal=bool(c_.get("mortal"))))
            self.round_t[:] = 1e9                                     # every match starts a lab room at once
        if nav and os.path.exists(nav):                 # movement goals: mega, red and yellow armor
            goals = [self.item_pos[k] for k, d in enumerate(self.item_def) if d[4] in ("MH", "RA", "YA")]
            if goals:
                from movement_env import NavField
                self.field = NavField(nav, goals, world=self.w)
            if LEGS and not teacher:                         # (his legs' network where no teacher is passed: checks, servers)
                teacher = os.environ.get("LEGS_NET")
            if goals and teacher and os.path.exists(teacher):
                import movement_env as M
                ck = np.load(teacher)                           # sim/export_policy.py output (no torch in workers)
                self.teacher_w = tuple(ck[k] for k in ("w0", "b0", "w1", "b1", "wp", "bp", "obs_mean", "obs_var"))
                # the teacher's observation code, on this world (a second World would resize shared buffers)
                T = self.teacher = M.MoveEnv.__new__(M.MoveEnv)
                T.w, T.obs_noise, T.rng = self.w, 0.0, self.rng
                T.v14 = bool(ck["v14"]) if "v14" in ck.files else False      # trained with lava and the game's step height (movement_env)
                tg = [e["origin"] for e in self.w.entities
                      if e.get("classname", "").startswith(M.GOAL_CLASSES) and "origin" in e
                      and not (T.v14 and e["classname"] == "item_quad")]
                T.field = (M.NavField(nav, tg + self.hold_tg, world=self.w, hazard=True, starts=self.spawns, drop=M.shut_teleports(self.w, nav), tele=M.teleports(self.w))
                           if T.v14 else M.NavField(nav, tg + self.hold_tg, world=self.w))     # (TARGETS: the holding places after its own goals)
                T.goal_pos = T.field.goals
                T.jump_obs = bool(ck["jumps"]) if "jumps" in ck.files else False   # trained with the five inputs of a jump ahead
                T.hand = bool(ck["hand"]) if "hand" in ck.files else False         # ... under his finger limits, with the five inputs of the hand
                T.mouse = bool(ck["mouse"]) if "mouse" in ck.files else False      # ... with his mouse, and its three inputs
                T.mouse_rev = self.t_rev = float(ck["mouse_rev"]) if "mouse_rev" in ck.files else 8.0
                T.c2 = int(ck["c2"]) if "c2" in ck.files else 0     # ... with the inputs of a look direction and "stand at the goal" (stage C part 2)
                self.t_w0 = ((np.ascontiguousarray(self.teacher_w[0][:, :-T.c2]), np.ascontiguousarray(self.teacher_w[0][:, -T.c2:]))
                             if T.c2 else None)                 # (its first layer for the old inputs, and for those: _move_labels)
                self.t_bins = M.TURN_BINS
                self.t_mid = int(np.argmin(np.abs(M.TURN_BINS)))   # its choice "no turn"
                self.t_field, self.t_field_j, self.t_nav = T.field, None, (nav, tg)   # (its field with the pros' jumps: _move_teach)
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
        self.sp_hist = np.zeros((n, 4), np.float32)     # his speed over the ground one to four frames ago (see N_V14; a plugin keeps it itself)
        self.wet = np.zeros(n, np.int8)                 # how deep he stands in water, slime or lava: feet 1, waist 2, head 3 (LAVA)
        self.cmd = np.zeros((n, 2), np.float32)         # last turn command (for the jerk cost)
        self.turn_dir = np.zeros(n, np.float32)         # the direction his hand turns the view (-1, 0, 1) and the frames since it
        self.rev_wait = np.zeros(n, np.float32)         # changed, counted down from the teacher's hold (for a teacher with his mouse)
        self.t_rev = getattr(self, "t_rev", 8.0)     # (the teacher's, if one was loaded above)
        self.hp = np.full(n, SPAWN_HP, np.float32)
        self.armor = np.zeros(n, np.float32)
        self.has = np.zeros((n, NW), bool)
        self.ammo = np.zeros((n, NW), np.float32)
        self.cool = np.zeros(n, np.float32)
        self.fire_cd = np.zeros(n, np.float32)          # reload left from the last shot (a switch waits for it)
        self.seen_t = np.full(n, 9.0, np.float32)       # seconds since this player last saw/heard the opponent
        self.known = np.zeros((n, 3), np.float32)       # last known opponent position
        self.style = np.zeros(n, np.int64)              # his playing style this life (STYLES; the game-server plugin sets it too)
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
                          arena=np.zeros(8),              # frags, player-frames, sum of speed, frames with the enemy in view, damage,
                                                          # frames standing still, frames looking over 40 degrees up or down, crouched frames
                          zoom_frames=0.0, key_asked=0, key_changes=0, key_blocked=0,   # movement-key changes made / refused by the finger limits
                          gun=np.zeros(3),                # run-and-gun: damage dealt, runner frames, sum of runner speed
                          lab_items=np.zeros(3),          # items room: mega pickups, red armor pickups, player-frames
                          switches=0, fire_frames=0, blind_frames=0, play_frames=0, aim_err=0.0, aim_frames=0,
                          on_target=0, move_frames=0, move_arrive=0, move_speed=0.0, move_fast=0,
                          cf_rounds=0, cf_stack_kills=0, cf_plain_kills=0, stack_frames=0, stack_over=0.0, stack_big=0.0, stack_bare=0, stack_low=0, stack_cost=0.0, stack_teach_frames=0, fire_vis=0, vis_frames_h=0, shot_cost=0.0, shot_n=0, shot_fac=0.0, soak=0.0, pick_wpnew=0, contest_rounds=0, contest_taken=0,
                          know=0.0, know_frames=0, pace_pay=0.0, pace_frames=0, trip_frames=0, trip_speed=0.0,
                          drops=0, pick_drop=0, pick_drop_new=0, drop_teach_frames=0,
                          close_v=np.zeros(3), close_n=np.zeros(3),     # his speed toward an enemy in view, by health plus armor: under 60, to 125, over
                          high=np.zeros(3), high_dmg=np.zeros(3),       # B-160: frames with his enemy in view, and damage dealt, standing lower by 48 units or more, level, higher
                          sc_frags_w=np.zeros(NW),                      # frags made by scripted players, by weapon
                          jump_tries=np.zeros(64), jump_over=np.zeros(64), jump_short=np.zeros(64),   # JUMPS: per jump of this map
                          jump_frames=0, start_gun=0,          # frames in jump runs; lives begun with a weapon in hand (START_GUN_P)
                          start_gun_w=np.zeros(len(WEAPONS)),  # ... by weapon
                          lob=np.zeros(3),                              # TRICKS, the lobber: frames firing at a place: plasma, grenades; at an exit
                          legs=np.zeros(8),               # LEGS: frames his legs carried him, of them with an enemy in view, frames the switch was on
                                                          # without a way, his frames alive; the first and the last of these in games; the sum of
                                                          # his speed on legs frames, on his own
                          legs_reads=np.zeros(2),         # ... the switch read, and read as "legs"
                          legs_keep=np.zeros((2, 7)),     # LEGS_LABEL / LEGS_KEEP, rows: the stretches his legs carried him, the withheld
                                                          # ones. Columns: stretches begun (his switch turned on); frames with a label, of
                                                          # them at 400 units a second or more, the sum of his speed on them; runs of such
                                                          # frames begun, runs that reached two seconds, the sum of the speed gained in them
                          en_frames=np.zeros(3),          # FIGHT_TARGET: frames his intention is the enemy, of them on his legs, with the enemy in view
                          way_reads=np.zeros(3),          # WAYS (the counted seats, see count_even): readings of his way, by the way read;
                          way_done=np.zeros(3),           # ... his trips reached (an item taken, a place stood at), by the way he was on;
                          way_frames=np.zeros(4),         # ... his frames alive in games with a target and a way to it, by way; of the frames on
                                                          # the second or third, those where it differs from the shortest from where he stands;
                          way_changes=0, way_trips_n=0,   # ... changes of the way alone; WAY_MEASURE: trips between two places kept
                          way_pay=np.zeros(2),            # ... what the ways of his trips paid him, and what trips given up gave back
                          hold_frames=np.zeros(6),        # TARGETS: frames his intention is a holding place, of them on his legs, standing at it,
                                                          # with the enemy in view; times he reached one; the sum of his speed on the way (not yet at it)
                          auto_switch=0,                  # AUTO_SWITCH: weapon changes the game made for him on an empty weapon
                          legs_c2=np.zeros(3),            # LEGS_LOOK: frames his legs were asked with a look point, of them his view within
                                                          # 30 degrees of it; LEGS_STAND: frames they were told to stand at the goal
                          high_pay=0.0,                                 # (HIGH_PAY) what the height of his hits added to his pay

                          style=np.zeros((4, 10)),        # per style: frames, his weapon in hand, enemy in view, in his band, sum of
                                                          # distance in view, damage, damage with his weapon, big weapons held, frags, deaths
                          wrule_frames=0, wrule_agree=0,
                          frags_vs_bot=0, bot_frags=0, target_kills=0, bot_frames=0, aim_round_frames=0,
                          w_dist=np.zeros((3, NW)), dmg_h=0.0, dmg_from_script=0.0,
                          hand_g=np.zeros(NW),                            # ... in games alone (not in one-weapon rounds)
                          hand_w=np.zeros(NW), blind_w=np.zeros(NW),      # frames with each weapon in hand; frames firing it with no enemy seen for a second
                          speed_pay=0.0, speed_pay_run=0.0, speed_frames=0, move_teach_frames=0,
                          blind_rl=0, blind_rl_how=np.zeros(5), prefire_frames=0, blind_bill=0,   # blind rockets: wasted, a jump, near, on a way, at one of the pros' places
                          vs_persona=np.zeros((3, len(PERSONAS))), fall_dmg=0.0, duck_frames=0, walk_frames=0)      # rows: frags against, deaths to, frames
        for wn in WEAPONS:
            self.stats[wn + "_shots"] = 0               # shots, ticks or pellets fired
            self.stats[wn + "_shots_vis"] = 0           # ... while the opponent was in view
            self.stats[wn + "_hits"] = 0
            self.stats[wn + "_frags"] = 0
        self.stats["hurt_dmg"], self.stats["void_deaths"] = 0.0, 0
        # (HAND_TEACH) the weapon in his hand with nobody in view: the pros' table for this map, what is kept a player, the counters
        self.hand_tab = None                                # [state, band, weapon] the pros' shares (None: no sim/pro_hand.json)
        hnd_f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_hand.json")
        if os.path.exists(hnd_f):
            with open(hnd_f, encoding="utf-8") as hnd_h:
                hnd_t = json.load(hnd_h)
            hnd_m = hnd_t["maps"].get(os.path.splitext(os.path.basename(bsp))[0].lower()) or hnd_t["maps"]["all"]
            self.hand_tab = np.zeros((2, 4, NW), np.float32)
            self.hand_tab[:, :, [WEAPONS.index(w_) for w_ in hnd_t["weapons"]]] = np.array(hnd_m["share"], np.float32)
        assert not HAND_TEACH or self.hand_tab is not None, "HAND_TEACH=1 needs sim/pro_hand.json (tools/pro_hand.py)"
        self.hand_fr = np.zeros(n, np.int64)                # frames since an enemy was last in his view (in a new round: since it began)
        self.hand_ever = np.zeros(n, bool)                  # an enemy has been in his view in this round
        self.hand_p0 = np.zeros((n, 3), np.float32)         # where his standing stretch began, and its frames (a hold from HAND_HOLD_F on)
        self.hand_hf = np.zeros(n, np.int64)
        self.hand_a0 = np.zeros(n, bool)                    # ... he could hold on the stretch's first frame (it is the hold's first then)
        self.hand_buf = np.full((HAND_HOLD_F + 1, n), -1, np.int64)   # the last frames' places in qhand, until it is known whether they
        self.hand_bp = 0                                    # were in a hold (-1: a frame that is not counted); where the oldest is
        self.hand_wp = np.full(n, -1, np.int64)             # the weapon in his hand a frame ago
        self.hand_state = np.full(n, 2, np.int64)           # this frame: 0 travelling, 1 holding, 2 neither; the band; nobody in view
        self.hand_band = np.full(n, 3, np.int64)            # for 1 s or more in a game on a network's seat (for the checks)
        self.hand_quiet = np.zeros(n, bool)
        self.hand_lab = np.zeros((n, 1 + NW), np.float32)   # the target of his next reading of the weapon key (zeros: no label)
        self.stats["qhand"], self.stats["qhand_meet"], self.stats["qhand_sw"] = np.zeros((3, 4, NW)), np.zeros(NW), np.zeros(2)
        self.stats["qhand_on"], self.stats["qhand_pro"] = np.zeros((2, 4, NW)), np.zeros((2, 4, NW))
        # HOP_PAY: what it paid, take-offs that paid, his take-offs with nobody in view, chains begun
        self.stats["hop_pay"], self.stats["hop_n"], self.stats["hop_takeoffs"], self.stats["hop_chains"] = 0.0, 0, 0, 0
        self.hop_best = np.zeros(n, np.float32)             # ... the best take-off speed of his chain of hops (0: no take-off yet)
        self.hop_sum = np.zeros(n, np.float32)              # ... what the chain has paid him
        self.hop_gnd = np.zeros(n, np.int64)                # ... his frames on the ground since he landed
        self.hop_k = np.zeros(n, np.int64)                  # ... the chain's take-offs so far that could be paid
        self.hop_sp = np.zeros(n, np.float32)               # ... his speed over the ground a frame ago
        # The game's pay (v0.2): the part of the last frame's reward that pays for items and stack, per player. In it: a
        # pickup's pay (item_reward: health, armor, a new weapon, a dropped one; the items room's), what an enemy's mega
        # or red costs (item_loss), the way to his chosen item (intent_seek, what a trip given up gives back, the price of
        # changing the intention; item_seek), item runs and jump runs (RUN_SCALE against the clock, RUN_ARRIVE, what a
        # failed try gives back) and the older movement rounds' run to a big item, the stack (STACK_PAY, STACK_WPN,
        # STACK_BARE, STACK_LOW) and knowing where the enemy is (KNOW_PAY). Not in it: damage, frags and deaths, shots,
        # blind fire, the hand's costs, styles, speed and pace pay, hop pay, the test map's courses. The reward is the same.
        self.r_long = np.zeros(n, np.float32)
        self.intent_fast = np.zeros(n, np.float32)          # the part of intent_paid that was pay for speed (not the game's pay)
        # mega / red armor: seconds they lay there before being taken (sum), times taken; first weapon of a life:
        # seconds after the spawn (sum), count
        self.stats["big_wait"], self.stats["big_taken"], self.stats["first_wp"] = np.zeros(2), np.zeros(2), np.zeros(2)
        self.stats["direct"] = 0                        # rockets hitting the body
        # intentions: frames per intention; trips chosen, reached, abandoned, ended by death; seconds to reach (sum)
        self.stats["intent_frames"], self.stats["intent_trips"], self.stats["intent_reach"] = np.zeros(len(INTENTS)), np.zeros(4), 0.0
        self.stats["big_up"], self.stats["big_frames"] = np.zeros(2), 0      # mega / red: frames lying there, frames
        self.big_ids = [next((k_ for k_, d_ in enumerate(self.item_def) if d_[4] == lab_), -1) for lab_ in ("MH", "RA")]
        # per course: attempts, finishes, time (finished attempts), distance, top speed, speed sum, frames, falls, height
        self.stats["course"] = np.zeros((16, 9))
        self.lab_course_ids = list(range(len(self.courses)))     # courses used when a lab round picks one
        self._game_init()
        self._v02_init(bsp)
        for i in range(n):
            self._spawn(i, avoid=None if i % 2 == 0 else self.w.state()[i - 1, :3])
        self.state = self.w.state()
        self.visible = np.zeros(n, bool)

    # ---------------------------------------------------------------- spawning / helpers
    def _acq_need(self):
        """frames an enemy must be in view before he is noticed: the acquire delay less the tracking delay, at least one.
        One number as ever; one a seat with SEAT_DELAYS (react_seat, acquire_seat)"""
        if self.react_seat is None and self.acquire_seat is None:
            return max(1, self.acquire_frames - self.react_frames)
        return np.maximum(1, (self.acquire_frames if self.acquire_seat is None else self.acquire_seat)
                          - (self.react_frames if self.react_seat is None else self.react_seat))

    def _fresh(self, i, yaw):
        self.yaw[i], self.pitch[i] = yaw, 0.0
        self.lava_t[i] = 0.0
        if STYLE_P > 0 and self.script[i] == 0:              # a new life: his playing style (here since 2026-10-08: in
            u_ = self.rng.random()                           # _spawn it missed arena1)
            self.style[i] = int(self.rng.integers(1, len(STYLES))) if u_ < STYLE_P else 0
            if STYLE_CUM is not None:                        # (STYLE_MIX) each style's own share of all lives, from the same
                self.style[i] = style_draw(u_)               # number (the stream has moved as it does without the mix)
            if STYLE_W[self.style[i]] >= 0 and int(STYLE_W[self.style[i]]) not in self.map_weapons:
                self.style[i] = 0                            # (no rail life on a map without a railgun)
        self.mv[i] = 0.0
        self.cmd[i] = 0.0
        self.turn_dir[i], self.rev_wait[i] = 0.0, 0.0
        self.hp[i], self.armor[i], self.cool[i] = SPAWN_HP, 0.0, 0.0
        self.fire_cd[i] = 0.0
        self.duck[i] = False
        self.key_last[i], self.key_hold[i], self.key_tok[i] = (1, 1, 0), 99, KEY_BURST
        self.key_req[i] = (1, 1, 0, 0)
        self.shot_t[i ^ 1] = self.trail_t[i ^ 1] = 99.0     # what the opponent knew about this player's shots is void
        self.pain_t[i ^ 1] = 99.0
        self.zoom[i], self.fire_last[i], self.mouse_hold[i] = False, False, 99
        self.flinch[i], self.focus[i] = 0.0, FOCUS_SECS
        self.life_t[i], self.first_wp[i] = 0.0, False
        if self.intent[i] > 0 and not self.intent_done[i]:
            self.stats["intent_trips"][3] += 1
        self.intent[i], self.intent_t[i], self.intent_new[i], self.intent_done[i] = 0, 0.0, True, False
        self.way[i], self.wt_from[i] = 0, -1                # (WAYS, WAY_MEASURE)
        self.pad[i], self.pad_lift[i], self.ear_t[i] = 0.0, 0, 99.0
        self.walk_last[i] = False
        self.e_got[self._mates(i), self._slot(i)] = 0.0     # what the others knew him to have is gone with him
        self.v02_pk[self._mates(i), self._slot(i)] = 0.0    # (N_V02: his big pickups as the others counted them)
        self.dmg_life[i ^ 1] = 0.0                      # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // 2])
        kind = int(self.kind[i // 2])
        game_ = GAME_ON and bool(self.game[self._match_of(i)])    # (a whole game or a late round: the game's spawn, see GAME_P)
        if self.stack_p > 0 and kind == NORMAL and self.script[i] == 0 and not game_ and self.rng.random() < self.stack_p:
            self.hp[i] = float(self.rng.uniform(100.0, 200.0))     # a random stack: the worth of armor is learned in fights
            self.armor[i] = float(self.rng.uniform(0.0, 150.0))
        self.intent_paid[i] = 0.0
        self.resp_t[i] = 99.0
        self.has[i] = False
        self.ammo[i] = 0.0
        if (kind in (MOVE, COURSE) and self.run_k[i] < 0) or self.script[i] == 1:   # movement round / course / strafing target: unarmed
            self.weapon[i] = G
        elif mode >= 0:                                 # one weapon (finite ammo) + gauntlet
            self.has[i, mode] = True
            self.has[i, G] = True
            self.ammo[i, mode] = DRILL_AMMO[mode]
            self.weapon[i] = mode
            if self.drill_mix[self._match_of(i)]:
                self.has[i, MG] = True                      # a mixed drill: the machine gun too, and half the time it is the
                self.ammo[i, MG] = LOADOUTS["all"][1][MG]   # one in his hand, so that taking the other is his to decide
                if self.rng.random() < 0.5:
                    self.weapon[i] = MG
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
            gun_ = [w_ for w_ in (GL, PG) if w_ in self.map_weapons] if START_GUN_P > 0 else []
            if START_GUN_W and START_GUN_P > 0:              # (see START_GUN_W: the weapons named, by their shares)
                gun_ = [w_ for w_ in range(len(WEAPONS)) if START_GUN_W.get(WEAPONS[w_], 0.0) > 0 and w_ in self.map_weapons]
            if gun_ and kind == NORMAL and self.script[i] == 0 and self.run_k[i] < 0 and not game_ and self.rng.random() < START_GUN_P:
                if START_GUN_W:
                    gw_ = np.array([START_GUN_W[WEAPONS[w_]] for w_ in gun_], np.float64)
                    w_ = int(gun_[int(self.rng.choice(len(gun_), p=gw_ / gw_.sum()))])
                else:
                    w_ = int(gun_[int(self.rng.integers(len(gun_)))])   # (see START_GUN_P; only a weapon the map has)
                self.has[i, w_] = True
                self.ammo[i, w_] = max(float(self.ammo[i, w_]), float(LOADOUTS["all"][1][w_]))
                self.weapon[i] = w_
                self.stats["start_gun"] += 1
                self.stats["start_gun_w"][w_] += 1
            if self.script[i] == 2:                     # the scripted fighter does not run dry
                self.ammo[i] = np.minimum(AMMO_MAX, self.ammo[i] * 3)
        if self.script[i] == 3 and self.sc_persona[i] == HOLDER and self.hold_ahead[i]:   # ahead from the first second, once
            self.hold_ahead[i] = False
            self.armor[i] = 100.0
            for w_ in (RL, LG, RG):
                self.has[i, w_] = True
                self.ammo[i, w_] = max(self.ammo[i, w_], AMMO_MAX[w_] * 0.4)
        if self.script[i] == 3 and self.sc_persona[i] in (LOBBER, WATCHER):   # their tools, every life
            for w_ in ((GL, PG) if self.sc_persona[i] == LOBBER else (RG,)):
                self.has[i, w_] = True
                self.ammo[i, w_] = AMMO_MAX[w_]
        self.hunt_t[i], self.x_goal[i], self.watch_t[i], self.sc_look[i] = 0.0, -1, 0.0, False
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
        if C["mortal"]:
            self.hp[i] = 1.0                                # any fall damage at all ends the attempt
        if self.gun[i]:
            self._gun_arm(i)
            self._gun_place(i // 2)
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
        self.hp[i], self.armor[i] = (1.0 if C["mortal"] else SPAWN_HP), 0.0
        if self.gun[i]:
            self._gun_arm(i)
        self.stats["course"][int(self.course[i]), 7] += 1

    def _gun_arm(self, i):
        w_ = int(self.gun_w[i // 2])
        self.has[i, w_], self.ammo[i, w_], self.weapon[i] = True, AMMO_MAX[w_], w_

    def _gun_place(self, m):
        """put the target of a run-and-gun round beside the path, 500 to 900 units ahead of the runner"""
        a_, b_ = 2 * m, 2 * m + 1
        C = self.courses[int(self.course[a_])]
        tp = min(float(self.prog[a_]) + float(self.rng.uniform(500, 900)), C["length"] - 150.0)
        x = float(np.interp(tp, C["cum"], C["path"][:, 0]))
        y = float(np.interp(tp, C["cum"], C["path"][:, 1]))
        k = int(np.clip(np.searchsorted(C["cum"], tp) - 1, 0, len(C["seg_len"]) - 1))
        d = (C["path"][k + 1] - C["path"][k]) / C["seg_len"][k]
        off = float(self.rng.uniform(-120, 120))
        x, y = x - d[1] * off, y + d[0] * off
        z = float(self.state[a_, 2])
        for up_ in (40.0, 120.0, 220.0, 340.0):             # the floor there: start inside the room, not in a ramp or the ceiling
            top = float(self.state[a_, 2]) + up_
            t = self.w.trace(np.array([x, y, top], np.float32), np.array([x, y, top - 2000.0], np.float32))
            if t["fraction"] > 0.001:
                z = float(t["endpos"][2]) + 26.0
                break
        self.gun_tp[m] = tp
        self.lab_home[m] = (x, y, z)
        self.lab_zone[m] = (x - 220, y - 220, x + 220, y + 220)
        self.lab_jump[m] = self.rng.random() < 0.5
        ty = float(self.rng.uniform(-180, 180))
        self.w.reset(b_, (x, y, z + 2.0), (0, 0, 0), ty)
        self._fresh(b_, ty)

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
            for i in idx[self.gun[idx]]:
                m_ = int(i) // 2
                self.ammo[i, self.gun_w[m_]] = AMMO_MAX[self.gun_w[m_]]
                self.stats["gun"][1] += 1
                self.stats["gun"][2] += float(np.hypot(s[i, 3], s[i, 4]))
                if self.prog[i] > self.gun_tp[m_] - 150.0 and self.gun_tp[m_] < C["length"] - 160.0:
                    self._gun_place(m_)
                    moved = True
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
        pr = (self.lab_p[2] / self.arena_len) if len(self.lab_p) > 2 else 0.0
        u = rng.random() * (pa + pc + pr)
        kd = f["kind"] if f else (NORMAL if u < pr else AIM if (u < pr + pa or not self.courses) else COURSE)
        self.kind[m], self.mode[m] = kd, -1
        self.arena[m] = 0
        self.script[a_] = self.script[b_] = 0
        self.goal[a_] = self.goal[b_] = -1
        self.course[a_] = self.course[b_] = -1
        self.items_room[a_] = self.items_room[b_] = False
        self.gun[a_] = self.gun[b_] = False
        self.lab_len[m] = self.lab_aim_len if kd == AIM else self.arena_len if kd == NORMAL else self.course_len
        self.load_sets[a_] = self.load_sets[b_] = None
        self.frags_r[a_] = self.frags_r[b_] = 0
        self.snd_t[a_] = self.snd_t[b_] = 99.0
        if kd == NORMAL:                                    # arena: the two fight each other, same weapons for both
            self.arena[m] = int(f["arena"]) if (f and "arena" in f) else int(rng.choice(self.arena_rooms))
            pool = [g for g in LOAD_GUNS if g in self.map_weapons]
            guns = tuple(int(x) for x in rng.choice(pool, 2, replace=False))           # two random weapons, the same for both
            if f and "weapon" in f:
                guns = (int(f["weapon"]),)
            if rng.random() < self.arena_full_p and not (f and "weapon" in f):
                guns = None                                 # the full weapon set
            self.load_sets[a_] = self.load_sets[b_] = guns
            if self.arena_sets and not (f and "weapon" in f):   # fixed sets, drawn separately for each player
                for q in (a_, b_):
                    self.load_sets[q] = tuple(self.arena_sets[int(rng.integers(len(self.arena_sets)))])
            if self.arena[m] == 3 and self.route is not None and not f and rng.random() < self.runner_p:
                self.script[b_] = 3                          # the yard: the item runner in a share of the rounds
                self.sc_persona[b_] = 0
                if TRICKS and TRICK_P.sum() > 0 and rng.random() < TRICK_P.sum():   # ... or one of the three in his place
                    self.sc_persona[b_] = (HOLDER, LOBBER, WATCHER)[int(rng.choice(3, p=TRICK_P / TRICK_P.sum()))]
                    self.hold_ahead[b_] = self.sc_persona[b_] == HOLDER and rng.random() < HOLD_STACK
            stack = (25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0)
            self.arena_hp[m], self.arena_ar[m] = float(rng.choice(stack)), float(rng.choice(stack))
            self.state = self.w.state()
            self._arena_spawn(a_, first=True)
            self.state = self.w.state()
            self._arena_spawn(b_)
        elif kd == AIM:
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
        elif "items" in L and ((f and f.get("items")) or (not f and rng.random() < self.lab_items_p)):
            # the items room: the first player alone with a mega health and a red armor on their timers (both up at
            # the start); the second player runs a course meanwhile
            I = L["items"]
            self.lab_len[m] = self.items_len
            self.item_up[m, :], self.item_t[m, :] = True, 0.0
            b = I["bounds"]                                 # start in the middle of one of the four corridors
            mids = ((b[0] + b[2]) / 2, b[1] + 256), ((b[0] + b[2]) / 2, b[3] - 256), (b[0] + 256, (b[1] + b[3]) / 2), (b[2] - 256, (b[1] + b[3]) / 2)
            sx, sy_ = mids[int(rng.integers(4))]
            iyaw = float(rng.uniform(-180, 180))
            self.w.reset(a_, (sx, sy_, I["start"][2] + 2.0), (0, 0, 0), iyaw)
            self._fresh(a_, iyaw)
            self.hp[a_], self.armor[a_] = 100.0, 0.0
            self.items_room[a_] = True
            self._course_start(b_, int(rng.choice(self.lab_course_ids)))
        elif (f and f.get("gun")) or (not f and rng.random() < self.lab_gun_p):
            ids = [k for k, C in enumerate(self.courses) if C["key"] in self.gun_courses]
            self.gun_w[m] = int(f["weapon"]) if (f and "weapon" in f) else int(rng.choice(self.aim_weapons))
            self.gun[a_] = True
            self.script[b_] = 1
            self._course_start(a_, int(f["course"]) if (f and "course" in f) else int(rng.choice(ids)))
        else:
            for q in (a_, b_):
                self._course_start(q, int(f["course"]) if f else int(rng.choice(self.lab_course_ids)))

    def _arena_spawn(self, i, first=False):
        """put player i somewhere in his arena, facing the opponent and (unless first) well away from him"""
        m, L, rng = i // 2, self.lab, self.rng
        opp = self.state[i ^ 1, :3]
        if self.arena[m] == 1:                              # the aim box: anywhere on its floor
            A = L["aim"]
            z = float(A["subject"][2])
            cand = [np.array([rng.uniform(96, 1440), rng.uniform(96, 928), z], np.float32) for _ in range(12)]
        else:
            E_ = L["env"]
            cand = [np.array([q[0], q[1], q[2] if len(q) > 2 else E_["z"]], np.float32) for q in E_["spots"]]
        if first:
            p = cand[int(rng.integers(len(cand)))]
        else:
            d = np.array([float(np.linalg.norm(q - opp)) for q in cand])
            ok = np.nonzero(d > 500)[0]
            p = cand[int(rng.choice(ok))] if len(ok) else cand[int(d.argmax())]
        face = math.degrees(math.atan2(opp[1] - p[1], opp[0] - p[0])) if not first else float(rng.uniform(-180, 180))
        self.w.reset(i, (p[0], p[1], p[2] + 2.0), (0, 0, 0), face)
        self._fresh(i, face)
        if self.arena_stack:                                # this round's health and armor
            self.hp[i], self.armor[i] = self.arena_hp[m], self.arena_ar[m]

    def _lab_respawn(self, v):
        """a death on the lab map: back to the room's own spot, not to a map spawn point"""
        m = v // 2
        if self.run_k[v] >= 0:                               # an item run: a spawn point of the map, as in a game
            self._spawn(v, avoid=None)
            return
        if self.arena[m]:
            self._arena_spawn(v)
        elif self.course[v] >= 0:
            self._course_back(v)
        elif self.items_room[v]:
            I = self.lab["items"]
            self.w.reset(v, (I["start"][0], I["start"][1], I["start"][2] + 2.0), (0, 0, 0), float(I["yaw"]))
            self._fresh(v, float(I["yaw"]))
            self.hp[v], self.armor[v] = 100.0, 0.0
        elif self.script[v] == 1:
            h = self.lab_home[m]
            ty = float(self.rng.uniform(-180, 180))
            self.w.reset(v, (h[0], h[1], h[2] + 2.0), (0, 0, 0), ty)
            self._fresh(v, ty)
        else:
            q = self.lab_subj[m]
            self.w.reset(v, (q[0], q[1], q[2] + 2.0), (0, 0, 0), float(q[3]))
            self._fresh(v, float(q[3]))

    def _run_teach(self):
        """item runs: the keys the scripted runner would press from where he stands, toward the target he was given
        (forward, strafe, jump, turn), as labels for the trainer's teacher loss (--teach, fading). The owner's call of
        2026-10-07: after three hours of item runs he took 0.15 targets a player-minute where a player who knows the
        ways takes about ten; he is shown the walk and the help is then taken away."""
        R = self.route
        if R is None:
            return
        ri = np.nonzero((self.run_k > 0) & (self.script == 0) & (self.hp > 0) & ~self.jrun)[0]   # (a jump is not a walker's: no keys in a jump run)
        kk = self.run_k[ri]
        if STACK_TEACH:                                     # ... and in normal games, bare or low, with nobody in view
            pk = np.repeat(self.kind, len(self.hp) // len(self.kind))
            need = (self.has[:, [RL, LG, RG]].sum(1) == 0) | ((self.hp + self.armor) < STACK_LOW_AT)
            # Keys only, no label for the view, and only when no enemy was seen or heard for STACK_TEACH_QUIET seconds: the
            # first version (2026-10-08 00:39) also taught where to look whenever nobody was in view, at full weight, and
            # within an hour he had all but stopped shooting (fire 31% -> 7% of frames, frags a match-minute 4.8 -> 1.1).
            quiet = ~self.visible & (self.seen_t > STACK_TEACH_QUIET)
            if SPAWN_TEACH:                                  # the spawn routine: to the first weapon whoever is in view
                quiet = quiet | (self.has[:, [RL, LG, RG]].sum(1) == 0)
            rj = np.nonzero((pk == NORMAL) & (self.run_k < 0) & (self.script == 0) & (self.hp > 0) & need
                            & quiet & (self.intent_teach > 0))[0]
            if not STACK_KEYS:
                rj = rj[:0]
            self.stats["stack_teach_frames"] += len(rj)
            n_run = len(ri)
            ri, kk = np.concatenate([ri, rj]), np.concatenate([kk, self.intent_teach[rj]])
        if not len(ri):
            return
        s = self.state
        pos = s[ri, :3]
        node = R.locate(pos)
        gi = self._trip_goal(kk, node)
        ok = (gi >= 0) & ~R.pro_step[np.maximum(gi, 0), node]   # (no keys for a step that is the pros': not a walk)
        if self.route_o is not None:                         # (JUMP_OPEN: nor where his own way takes a jump within 400 units)
            O_ = self.route_o
            go_ = self._trip_goal(kk, node, O_)
            ok &= ~((go_ >= 0) & (O_.ji[np.maximum(go_, 0), node] >= 0) & (O_.jd[np.maximum(go_, 0), node] < 400.0))
        g = np.maximum(gi, 0)
        nx = R.walk[g, node]
        tp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[g])
        near = np.hypot(tp[:, 0] - pos[:, 0], tp[:, 1] - pos[:, 1]) < 48.0
        if WALK_FIX:
            near = near & (np.abs(tp[:, 2] - pos[:, 2]) < 56.0)   # ... and at its height (a landing under the edge is not reached)
        nx2 = np.where(nx >= 0, R.walk[g, np.maximum(nx, 0)], -1)
        tp = np.where((near & (nx2 >= 0))[:, None], R.nodes[np.maximum(nx2, 0)], tp)
        tp = np.where((near & (nx >= 0) & (nx2 < 0))[:, None], R.goals[g], tp)
        tp = self._enter(R, g, node, nx, near, tp, s[ri, 6] > 0.5, pos if WALK_FIX else None, s[ri, 5],
                         (self.wet[ri] >= 2) if WALK_FIX else None)
        is_via = WALK_FIX & ~np.isnan(R.via[g, node][:, 0])
        to_drop = np.zeros(len(ri), bool)
        if DROPS and STACK_TEACH:
            tp, to_drop = self._teach_drop(ri, pos, tp.copy())
            to_drop[:n_run] = False                          # (in an item run he is alone: nothing is dropped)
            self.stats["drop_teach_frames"] += int(to_drop.sum())
        d = tp - pos
        hd = np.hypot(d[:, 0], d[:, 1])
        rel_deg = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) - self.yaw[ri] + 180.0) % 360.0 - 180.0
        rel = np.radians(rel_deg)
        fwd = np.where(np.cos(rel) > 0.38, 1, np.where(np.cos(rel) < -0.38, -1, 0))
        side = np.where(np.sin(rel) > 0.38, -1, np.where(np.sin(rel) < -0.38, 1, 0))
        slow = np.hypot(s[ri, 3], s[ri, 4]) < 80.0
        self.run_stuck[ri] = np.where(slow, self.run_stuck[ri] + 1, 0)
        up = (d[:, 2] > 18.0) & (hd < 260.0) & ~to_drop & ~is_via
        gap = (hd > 150.0) & (d[:, 2] > -40.0) & (nx >= 0) & ~near & ~to_drop
        jump = (s[ri, 6] > 0.5) & (up | gap | (self.run_stuck[ri] > 10))
        if WALK_FIX:
            jump = jump | ((self.wet[ri] >= 2) & (d[:, 2] > -24.0))    # (in water he swims up, as the scripted walker)
        vert = jump.astype(np.int64)
        if WALK_FIX:                                         # (under water, where the way leads down: he dives)
            vert = np.where((self.wet[ri] >= 2) & (d[:, 2] < -24.0), 2, vert)
        if self.pro_air is not None:                         # the jump key as the pros use it there (see PRO_JUMP)
            care = R.move[g, node] | ((nx >= 0) & R.move[g, np.maximum(nx, 0)]) | ((nx2 >= 0) & R.move[g, np.maximum(nx2, 0)])
            hop = self._pro_hop(pos) & (np.hypot(s[ri, 3], s[ri, 4]) > 200.0) & (np.abs(d[:, 2]) < 40.0) & ~care & (R.T[g, node] > 1.0)
            vert = np.where(jump | hop, 1, np.where(care, 0, -1))    # before a jump, a drop, a pad or a teleporter: feet down; else his own
        turn = np.clip(rel_deg * 0.5, -20.0, 20.0)
        lab = np.stack([fwd + 1, side + 1, vert, np.abs(TURN[None, :] - turn[:, None]).argmin(1)], 1)
        self.teach[ri[ok | to_drop], :4] = lab[ok | to_drop]
        if STACK_TEACH:
            self.teach[ri[n_run:], 3] = -1                   # (in a game the view is his own)
        if TEACH_KEYS_ONLY:
            self.teach[ri, 3] = -1                           # ... and in an item run too: the keys for the view he has

    @staticmethod
    def _enter(R, g, node, nx, near, tp, ground, pos=None, vz=None, swim=None):
        """the walker's target when the link from his point, or the one after the next point he has all but reached, goes
        through a jump pad or a teleporter: its plate or entrance (see RouteField.via). Only on the ground: thrown by the
        pad he steers for where it takes him, not back to the plate."""
        v0 = R.via[g, node]
        v1 = R.via[g, np.maximum(nx, 0)]
        if pos is not None:                                  # WALK_FIX: in a hop of his own beside the entrance it stays the target;
            with np.errstate(invalid="ignore"):              # only thrown by a pad (fast upward, or well above its plate) is he "in flight"
                beside = (vz < 290.0) & ((pos[:, 2] - np.where(np.isnan(v0[:, 2]), v1[:, 2], v0[:, 2])) < 64.0)
            ground = ground | beside
        if swim is not None:                                 # ... and swimming he is not in flight either (a teleporter under water)
            ground = ground | swim
        tp = np.where((ground & near & (nx >= 0) & ~np.isnan(v1[:, 0]))[:, None], v1, tp)
        return np.where((ground & ~np.isnan(v0[:, 0]))[:, None], v0, tp)

    def _pro_hop(self, pos):
        """is this a place where the pros are in the air for most of their moving time (see PRO_JUMP)"""
        air, lo, zmid, cell = self.pro_air
        cx = np.clip(((pos[:, 0] - lo[0]) / cell).astype(np.int64), 0, air.shape[2] - 1)
        cy = np.clip(((pos[:, 1] - lo[1]) / cell).astype(np.int64), 0, air.shape[1] - 1)
        return air[(pos[:, 2] > zmid).astype(np.int64), cy, cx] > PRO_JUMP_AT

    def _teach_update(self):
        """labels from the movement teacher for players on a movement goal (sampled from its policy)"""
        self.teach[:] = -1
        self._run_teach()
        if self.teach_runs != "all":                         # (no walking keys either where the movement teacher is kept out)
            self.teach[(self.run_k > 0) & (self.script == 0), :4] = -1
        self._weapon_teach()
        if RUN_TEACHER and self.teacher is not None and self.route is not None and self.teach_runs != "none":
            self._move_teach()
        if self.teacher is None:
            return
        mi = np.nonzero((self.goal >= 0) & (self.script == 0))[0]
        if not len(mi):
            return
        T, s = self.teacher, self.state
        T.n, T.state, T.yaw = len(mi), s[mi], self.yaw[mi]
        self._teacher_hand(T, mi)
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
            out.append(l.argmax(1) if TEACH_BEST else (pr.cumsum(1) > self.rng.random((len(mi), 1))).argmax(1))
            j += d
        if getattr(T, "mouse", False):                       # (a change of direction his hand cannot make yet: the view rests)
            sg_ = np.sign(self.t_bins[out[3]])
            w_ = mi
            out[3] = np.where((sg_ != 0) & (self.turn_dir[w_] != 0) & (sg_ != self.turn_dir[w_]) & (self.rev_wait[w_] > 0), self.t_mid, out[3])
        out[3] = self.t_turn[out[3]]
        self.teach[mi, :4] = np.stack(out, 1)

    def _teacher_hand(self, T, ii):
        """a movement network trained under the finger limits (train_move.py --hand) is shown the hand of the players
        it labels: the keys they hold, their budget of key actions, the frames until their keys are read next"""
        if getattr(T, "mouse", False):                       # ... and one trained with his mouse (--mouse) his view's turning speed,
            T.mv, T.turn_dir, T.rev_wait = self.mv[ii, 0].copy(), self.turn_dir[ii], self.rev_wait[ii]    # its direction, the frames to a change
        if not getattr(T, "hand", False):
            return
        kl = self.key_last[ii]
        T.key_last = np.stack([kl[:, 0], kl[:, 1], (kl[:, 2] == 1).astype(np.int64)], 1)
        T.key_tok = self.key_tok[ii]
        T.key_wait = ((-(self.key_tick + 1 + np.asarray(ii))) % KEY_EVERY).astype(np.float32)

    def _move_teach(self, ri=None, k=None, into=None):
        """item runs: what the strafe-jumping movement network would do toward his target (keys, jump and view), sampled
        from its policy, in place of the walking teacher's keys (see RUN_TEACHER).
        LEGS: the same for the players ri it moves, toward the targets k (per player), written into the array given"""
        if ri is None:
            ri = np.nonzero((self.run_k > 0) & (self.script == 0) & (self.hp > 0))[0]
            if self.teach_runs == "jump":
                ri = ri[self.jrun[ri]]
        if not len(ri):
            return
        T, s = self.teacher, self.state
        if getattr(self, "t_route", None) is None:           # our route goal -> the network's goal (the same item)
            ip = self.item_pos[np.array(self.route_item)]
            d = T.goal_pos[None, :len(self.t_nav[1]), :] - ip[:, None, :]
            hd = np.hypot(d[:, :, 0], d[:, :, 1]) + 1e6 * (np.abs(d[:, :, 2]) > 128.0)
            self.t_route = np.where(hd.min(1) < 48.0, hd.argmin(1), -1).astype(np.int32)
            if self.hold_tg:                                 # (TARGETS: a holding place's row -> its goal, after the network's own)
                self.t_route = np.concatenate([self.t_route, len(self.t_nav[1]) + np.arange(len(self.hold_tg), dtype=np.int32)])
        if self.jrun[ri].any():                              # the players of a jump run: the network's ways with the pros' jumps
            if not getattr(T, "jump_obs", False):
                ri = ri[~self.jrun[ri]]                      # (a network that was not trained on them has nothing to say there)
            else:
                import movement_env as M
                if self.t_field_j is None:
                    self.t_field_j = M.NavField(self.t_nav[0], list(self.t_nav[1]) + [j_["b"] for j_ in self.jumps],
                                                world=self.w, hazard=True, starts=self.spawns,       # (the landings are goals too, as in its task)
                                                drop=M.shut_teleports(self.w, self.t_nav[0]), tele=M.teleports(self.w), jumps=self.jumps)
                rj = ri[self.jrun[ri]]
                rj = rj[self.jrun_past[rj] | ~self.jump_lab_off[self.jrun_k[rj]]]      # (not before the landing of a jump its pupil fails at)
                ri = ri[~self.jrun[ri]]
                gp_ = T.goal_pos
                T.field, T.goal_pos = self.t_field_j, self.t_field_j.goals
                try:
                    for f_ in (np.unique(self.jrun_f[rj]) if len(self.jfields) > 1 else (0,)):
                        self._move_labels(rj[self.jrun_f[rj] == f_] if len(self.jfields) > 1 else rj, self.jfields[int(f_)], land=True, k=k, into=into)
                finally:
                    T.field, T.goal_pos = self.t_field, gp_
        if len(ri) and self.route_o is not None and getattr(T, "jump_obs", False):   # (JUMP_OPEN: its ways with the open jumps)
            import movement_env as M
            if getattr(self, "t_field_o", None) is None:
                self.t_field_o = M.NavField(self.t_nav[0], list(self.t_nav[1]) + self.hold_tg, world=self.w, hazard=True, starts=self.spawns,
                                            drop=M.shut_teleports(self.w, self.t_nav[0]), tele=M.teleports(self.w),
                                            jumps=[j_ for j_ in self.jumps if j_["id"] in self.jump_open])
            T.field = self.t_field_o
            try:
                self._move_ways(ri, self.route_o, k, into)
            finally:
                T.field = self.t_field
        elif len(ri):
            self._move_ways(ri, self.route, k, into)

    def _move_ways(self, ri, R, k, into):
        """_move_labels() for players ri whose ways are R's, each by the way he is on (WAYS): the movement network's own
        field for the shortest, its second and third fields (sim/ways.py's nav_alts: the same plan of the pros' ways,
        searched on its own walking map) for the others. Its field is put back as it was."""
        w = np.where(self.run_k[ri] >= 0, 0, self.way[ri]) if (WAYS and R is self.way_field) else None     # (in a run: the shortest)
        if w is None or not (w > 0).any():
            self._move_labels(ri, R, k=k, into=into)
            return
        T = self.teacher
        F = T.field
        alts = self.t_ways.get(id(F))
        if alts is None:
            import ways as WY_
            alts = self.t_ways[id(F)] = WY_.nav_alts(F, {int(self.t_route[g_]): self.way_plan[g_] for g_ in range(len(self.way_plan))
                                                         if g_ < len(self.t_route) and self.t_route[g_] >= 0})
        try:
            for j in range(N_WAYS):
                rj = ri[w == j]
                if len(rj):
                    T.field = F if j == 0 else alts[j - 1]
                    self._move_labels(rj, R, k=k, into=into)
        finally:
            T.field = F

    def _legs_c2(self, ri, k, legs):
        """stage C part 2: what a movement network with the inputs for it is told about the players ri it is asked for:
        the look point, that one is given, that he is to stand at the goal. legs: its choices will move them (as the
        teacher of item runs it is told nothing). LEGS_LOOK: the place he believes the enemy at, as his own inputs have it
        (kept by _v02 at the last observe()). LEGS_STAND: his target is one of the map's holding places."""
        m = len(ri)
        pt, on, st = np.zeros((m, 3), np.float32), np.zeros(m, bool), np.zeros(m, bool)
        if legs and LEGS_LOOK and getattr(self, "v02_bel", None) is not None:
            on = np.asarray(self.v02_bel_ok, bool)[ri]
            pt = np.where(on[:, None], self.v02_bel[ri], 0.0).astype(np.float32)
        if legs and LEGS_STAND and getattr(self, "hold_tg", None) and k is not None:      # (hold_tg: stage B part 2's places as his legs' goals)
            st = np.asarray(k)[ri] >= globals().get("HOLD_INTENT", 1 << 30)
        if on.any() or st.any():
            d_ = pt - self.state[ri, :3]
            off = (np.degrees(np.arctan2(d_[:, 1], d_[:, 0])) - self.yaw[ri] + 180.0) % 360.0 - 180.0
            self.stats["legs_c2"] += (int(on.sum()), int((on & (np.abs(off) <= 30.0)).sum()), int(st.sum()))
        return pt, on, st

    def _move_labels(self, ri, R, land=False, k=None, into=None):
        """the movement network's labels for players ri, whose ways are R's (the walking map's, or with the pros' jumps).
        land (a jump run): its goal is the landing of his try's jump until he is over it, as in its own tries, then the item
        (asked for the item from the start, its own ways went round some jumps: Blood Run 7, over 0 of 89 with its labels)"""
        T, s = self.teacher, self.state
        if not len(ri):
            return
        gi = self._trip_goal((self.run_k if k is None else k)[ri], R.locate(s[ri, :3]), R, who=ri)
        tg = np.where(gi >= 0, self.t_route[np.maximum(gi, 0)], -1)
        if land:
            tg = np.where(self.jrun_over[ri] | self.jrun_past[ri], tg, len(self.t_nav[1]) + self.jrun_k[ri])
        T.n, T.state, T.yaw = len(ri), s[ri], self.yaw[ri]
        self._teacher_hand(T, ri)
        T.goal = np.maximum(tg, 0).astype(np.int32)
        T.phi = T.field.potential(T.goal, s[ri, :3])[0]
        ok = (tg >= 0) & (T.phi < 1e8)                       # (no way in its own walking map: the walking teacher's keys stay)
        if not ok.any():
            return
        w0, b0, w1, b1, wp, bp, mean, var = self.teacher_w
        c2_ = getattr(T, "c2", 0)                            # (stage C part 2) a network with the inputs for it is told where to
        if c2_:                                              # look and that he is to stand at the goal; any other is asked as before
            T.look_pt, T.look_on, T.stand = self._legs_c2(ri, k, into is not None)
        x = np.clip((T.observe() - mean) / np.sqrt(var + 1e-8), -10, 10).astype(np.float32)
        if c2_:                                              # (the new inputs' part apart: with them at zero, or at zero weight, the
            T.look_on = T.stand = None                       # sum is bit for bit the old network's; and its other askers tell it nothing)
            lg = np.tanh(np.tanh(np.ascontiguousarray(x[:, :-c2_]) @ self.t_w0[0].T + x[:, -c2_:] @ self.t_w0[1].T + b0) @ w1.T + b1) @ wp.T + bp
        else:
            lg = np.tanh(np.tanh(x @ w0.T + b0) @ w1.T + b1) @ wp.T + bp
        out, j = [], 0
        for d_ in (3, 3, 2, 9):
            l_ = lg[:, j:j + d_]
            pr = np.exp(l_ - l_.max(1, keepdims=True))
            pr /= pr.sum(1, keepdims=True)
            out.append(l_.argmax(1) if TEACH_BEST else (pr.cumsum(1) > self.rng.random((len(ri), 1))).argmax(1))
            j += d_
        if getattr(T, "mouse", False):                       # (a change of direction his hand cannot make yet: the view rests)
            sg_ = np.sign(self.t_bins[out[3]])
            w_ = ri
            out[3] = np.where((sg_ != 0) & (self.turn_dir[w_] != 0) & (sg_ != self.turn_dir[w_]) & (self.rev_wait[w_] > 0), self.t_mid, out[3])
        out[3] = self.t_turn[out[3]]
        if into is not None:                                 # (LEGS: its choices move him)
            into[ri[ok]] = np.stack(out, 1)[ok]
            return
        self.teach[ri[ok], :4] = np.stack(out, 1)[ok]
        self.stats["move_teach_frames"] += int(ok.sum())

    def _legs_count(self, sp):
        """(LEGS_LABEL, LEGS_KEEP) stats["legs_keep"], columns 1 to 6: the frames with a label, apart for the stretches his
        legs carried him (row 0) and the withheld ones (row 1), of the seats in legs_keep_who. sp: his speed over the ground
        as the frame began (the state the label was made in). A run: his frames with a label without a break, in one
        stay on the map (a new life, a new round, a new try of a jump, the plain spawn an item run's fight begins with:
        wherever _fresh() put him anew, a new run begins); the speed gained in its first two seconds is his speed
        LEGS_GAIN_FRAMES frames after its first frame less his speed on that one, counted for the runs that last that long."""
        self.legs_run = np.where(self.legs_run * DT > self.life_t - 0.5 * DT, 0, self.legs_run)   # (the run is older than his stay: it ended there)
        lab = (self.legs_lab[:, 0] >= 0) & self.legs_keep_who
        first = lab & (self.legs_run == 0)
        self.legs_sp0 = np.where(first, sp, self.legs_sp0).astype(np.float32)
        self.legs_run = np.where(lab, self.legs_run + 1, 0)
        two = lab & (self.legs_run == LEGS_GAIN_FRAMES + 1)
        for r_, m_ in ((0, lab & ~self.legs_wh), (1, lab & self.legs_wh)):
            t_ = m_ & two
            self.stats["legs_keep"][r_, 1:] += (m_.sum(), (m_ & (sp >= LEGS_FAST)).sum(), sp[m_].sum(), (m_ & first).sum(),
                                                t_.sum(), (sp - self.legs_sp0)[t_].sum())

    def _legs_step(self, a):
        """LEGS: his switch is read (every LEGS_EVERY frames, staggered by player; held between), and for the players
        whose switch is on the movement network's choices of this frame take the place of their own movement keys and
        view turn in a (walk and zoom let go). Called before the finger limits: its keys pass through his hand as his do."""
        n = self.n
        who = self.script == 0
        self.legs_tick += 1
        live = who & ((self.legs_tick + np.arange(n)) % LEGS_EVERY == 0)
        ask = a[:, LEGS_HEAD] == 1
        if LEGS_OFF > 1:                                     # a stretch on his legs ends only at the LEGS_OFF-th "no" in a row
            self.legs_no = np.where(live, np.where(ask, 0, self.legs_no + 1), self.legs_no)
            ask = ask | (self.legs & (self.legs_no < LEGS_OFF))
        self.legs = np.where(live, ask, self.legs) & who & (self.hp > 0)
        self.legs_live = live
        self.stats["legs_reads"] += (int(live.sum()), int((live & (a[:, LEGS_HEAD] == 1)).sum()))
        self.legs_on = np.zeros(n, bool)
        if LEGS_LAB:                                         # (LEGS_LABEL, LEGS_KEEP) this frame's label, and the stretches withheld
            self.legs_lab = np.full((n, 4), -1, np.int8)
            self.legs_wh = np.zeros(n, bool)
            new_ = np.nonzero(self.legs & ~self.legs_was & self.legs_keep_who)[0]    # a stretch on his legs begins: his switch turns on
            self.legs_was = self.legs.copy()
            if LEGS_KEEP < 1.0 and len(new_):                # ... the draw: withheld with the chance 1 - LEGS_KEEP
                self.legs_held[new_] = self.rng_keep.random(len(new_)) >= LEGS_KEEP
            self.legs_held &= self.legs                      # (it ends with the stretch)
            self.stats["legs_keep"][:, 0] += (int((~self.legs_held[new_]).sum()), int(self.legs_held[new_].sum()))
        ri = np.nonzero(self.legs)[0]
        if not len(ri) or self.teacher is None or self.route is None:
            return
        k = np.where(self.run_k > 0, self.run_k, self.intent)       # his target: the item of his run, or of his intention
        ri = ri[k[ri] > 0]
        if self.hold_n:                                      # at his holding place there is no further way: he holds it on his own feet
            ri = ri[~self._hold_at(ri, k[ri])]
        if LEGS_STAND and getattr(self, "hold_tg", None) and getattr(self.teacher, "c2", 0):    # (stage C part 2) at his holding place
            ri = np.nonzero(self.legs)[0]                    # his legs do not let go of him: a network that can is told to stand
            ri = ri[k[ri] > 0]                               # there, and stops him (stage B part 2 takes him off his legs at the place)
        if not len(ri):
            return
        ch = np.full((n, 4), -1, np.int64)
        self._move_teach(ri, k, ch)
        ok = ch[:, 0] >= 0
        if LEGS_LAB:
            self.legs_lab = ch.astype(np.int8)               # the four choices where the movement network has a way, -1 elsewhere
            self.legs_wh = ok & self.legs_held               # a withheld stretch: the label is there, his own outputs stay
            ok = ok & ~self.legs_held
        a[ok, :4] = ch[ok]
        a[ok, 7:9] = 0
        self.legs_on = ok

    def _spawn(self, i, avoid, close=None):
        game_ = GAME_ON and bool(self.game[self._match_of(i)])    # (a whole game or a late round: a spawn point, away from the enemy)
        if self.near_item_p > 0 and self.route is not None and self.script[i] == 0 and self.run_k[i] < 0 and not game_ and self.rng.random() < self.near_item_p:
            gis = [g_ for g_, lab_ in enumerate(self.route_goal) if lab_ in ("MH", "RA")]
            if gis:                                          # near the mega or the red: he tastes the stack (v9)
                g_ = int(self.rng.choice(gis))
                near = np.nonzero(self.route.T[g_] < 2.0)[0]
                if len(near):
                    p = self.route.nodes[int(self.rng.choice(near))]
                    face = float(self.rng.uniform(-180, 180))
                    self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), face)
                    self._fresh(i, face)
                    return
        p_close = self.close_p if close is None else float(close)
        if game_:
            p_close = 0.0
        if avoid is not None and self.spots is not None and self.rng.random() < p_close:
            d = np.linalg.norm(self.spots - avoid, axis=1)
            cand = np.nonzero((d > self.close_band[0]) & (d < self.close_band[1]))[0]
            for k in self.rng.permutation(cand)[:24]:
                p = self.spots[k]
                if self.w.trace(p + np.array([0, 0, VIEW_H], np.float32),
                                avoid + np.array([0, 0, 8.0], np.float32), mask=self.sight)["fraction"] >= 0.999:
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

    def _spawn_at(self, i, k):
        """player i starts at spawn point k"""
        p = self.spawns[k]
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), float(self.spawn_yaw[k]))
        self._fresh(i, float(self.spawn_yaw[k]))

    def _contest_start(self, m):
        """a normal round of match m starts as a race for a big item (see CONTEST_P)"""
        R = self.route
        gis = [g_ for g_, lab_ in enumerate(self.route_goal) if lab_ in ("MH", "RA", "YA", "YA2")]
        if R is None or not gis:
            return
        g_ = int(self.rng.choice(gis))
        it = self.route_item[g_]
        t0 = float(self.rng.uniform(*CONTEST_T))
        t_sp = R.T[g_, R.locate(self.spawns)]                # the way from every spawn point, in seconds
        q = self._seats(m)
        near = np.argsort(np.abs(t_sp - (t0 + 0.5)) + self.rng.uniform(0.0, 0.75, len(t_sp)))    # about as far as it is away in time
        near = [int(k) for k in near if t_sp[k] < 1e8][:max(len(q), 3)]
        if len(near) < len(q):
            return
        for i, k in zip(q, self.rng.permutation(near)[:len(q)]):
            self.state = self.w.state()
            self._spawn_at(int(i), int(k))
        resp = float(self.item_def[it][2])
        self.item_up[m, it], self.item_t[m, it] = False, t0
        self.bel_t[q, g_] = resp - t0                        # everybody knows when it is back, as if he had heard it taken
        if self.route_goal[g_] in ("MH", "RA"):
            self.it_t[q, 0 if self.route_goal[g_] == "MH" else 1] = resp - t0
        self.contest_it[m], self.contest_t[m] = it, t0 + 10.0
        self.stats["contest_rounds"] += 1

    def _counted(self, i):
        """is player i (or each of an array of players) counted in the jump counters (see count_even)"""
        g_ = self._others_arr().shape[1] + 1
        return (np.asarray(i) % g_ % 2 == 0) | (not self.count_even)

    def _others_arr(self):
        """for every player, the other players of his group (one column each)"""
        return (np.arange(self.n) ^ 1)[:, None]

    def pad_turn(self, turn, dpit, lift, zs, who):
        """the mouse pad (see PAD_DEG): what is left of this frame's view movement. turn, dpit in degrees, lift =
        he asks to lift the mouse, zs = zoom scale (zoomed, the same hand movement turns the view less), who = the
        players it applies to"""
        if not self.pad_on:
            return turn, dpit
        half = PAD_DEG / 2.0
        air = (self.pad_lift > 0) & who
        self.pad_lift = np.where(air, self.pad_lift - 1, self.pad_lift)
        self.pad = np.where(air & (self.pad_lift == 0), 0.0, self.pad).astype(np.float32)    # set down in the middle
        hand = turn / zs                                     # how far the hand would move
        new = self.pad + np.where(air, 0.0, hand)
        over = (np.abs(new) > half) & who & ~air
        new = np.clip(new, -half, half)
        moved = np.where(who & ~air, (new - self.pad) * zs, np.where(who, 0.0, turn))
        self.pad = np.where(who, new, self.pad).astype(np.float32)
        start = who & ~air & (over | (lift & (np.abs(self.pad) > 0.15 * half)))
        self.pad_lift = np.where(start, PAD_LIFT, self.pad_lift)
        return moved.astype(np.float32), np.where(air, 0.0, dpit).astype(np.float32)

    def hear(self, noisy):
        """noisy: players who made a sound this frame. Everybody notes the nearest enemy he hears (see N_EAR)"""
        s, n = self.state, self.n
        oth = self._others_arr()
        d = np.linalg.norm(s[oth, :3] - s[:, None, :3], axis=2)
        hum = ((self.weapon == RG) | (self.weapon == LG))[oth] & (d < HUM_RANGE)       # the weapon's hum, always there
        ok = ((noisy[oth] & (d < EAR_RANGE)) | hum) & (self.hp[oth] > 0) & (self.hp > 0)[:, None]
        d = np.where(ok, d, 1e9)
        k = d.argmin(1)
        ar = np.arange(n)
        got = np.nonzero(d[ar, k] < 1e8)[0]
        if not len(got):
            return
        src = oth[got, k[got]]
        to = s[src, :3] - s[got, :3]
        dist = d[got, k[got]]
        ang = np.arctan2(to[:, 1], to[:, 0]) + np.radians(self.rng.normal(0, EAR_NOISE, len(got)))
        up = np.clip((to[:, 2] + self.rng.normal(0, 40.0, len(got))) / 200.0, -1.5, 1.5)
        close = -((s[src, 3:6] - s[got, 3:6]) * to).sum(1) / (dist + 1e-6)          # positive: the gap is closing
        self.ear[got] = np.stack([ang, up, 1.0 - dist / EAR_RANGE, np.clip(close / 400.0, -1.5, 1.5)], 1)
        self.ear_t[got] = 0.0
        self.ear_hum[got] = np.where(hum[got, k[got]], self.weapon[src], -1)
        dz_ = up * 200.0                                     # (N_V02: when and about where he last heard that player, from
        dh_ = np.sqrt(np.maximum(dist * dist - dz_ * dz_, 0.0))     # what the sound tells him: direction, height, loudness)
        self.v02_ht[got, self._slot(src)] = 0.0
        self.v02_hp[got, self._slot(src)] = s[got, :3] + np.stack([np.cos(ang) * dh_, np.sin(ang) * dh_, dz_], 1)

    def _more(self, pos, rot, c, si, visible, opp_vel, seen_t):
        """the inputs of N_MORE"""
        n = self.n
        ar = np.arange(n)
        haz = np.zeros((n, 32), np.float32)
        if len(self.hurt_zones):
            ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            see = (np.abs((ang + np.pi) % (2 * np.pi) - np.pi)[None, :] <= self.fov()[0][:, None]) if (self.fov_sight and not GROUND_SENSE) else True
            for r_, dist in enumerate(HAZ_DIST):
                sx = pos[:, 0:1] + (c[:, None] * np.cos(ang)[None] - si[:, None] * np.sin(ang)[None]) * dist
                sy = pos[:, 1:2] + (si[:, None] * np.cos(ang)[None] + c[:, None] * np.sin(ang)[None]) * dist
                starts = np.stack([sx, sy, np.repeat(pos[:, 2:3], 8, 1)], 2).reshape(-1, 3).astype(np.float32)
                fr = self.w.rays(starts, np.array([[0, 0, -1.0]], np.float32), 1200.0).reshape(n, 8)
                ez = pos[:, 2:3] - fr * 1200.0               # the floor under that spot
                for hz in self.hurt_zones:
                    inxy = (sx >= hz[0]) & (sx <= hz[3]) & (sy >= hz[1]) & (sy <= hz[4])
                    kill = hz[6] >= 1000
                    hit = inxy & ((ez <= hz[5]) if kill else ((ez >= hz[2] - 8) & (ez <= hz[5] + 8)))
                    k0 = 16 * r_ + (8 if kill else 0)
                    haz[:, k0:k0 + 8] = np.maximum(haz[:, k0:k0 + 8], hit & see)
        elif LAVA:                                           # the game's maps: is the floor under those spots in lava or slime
            ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            see = (np.abs((ang + np.pi) % (2 * np.pi) - np.pi)[None, :] <= self.fov()[0][:, None]) if (self.fov_sight and not GROUND_SENSE) else True
            for r_, dist in enumerate(HAZ_DIST):
                sx = pos[:, 0:1] + (c[:, None] * np.cos(ang)[None] - si[:, None] * np.sin(ang)[None]) * dist
                sy = pos[:, 1:2] + (si[:, None] * np.cos(ang)[None] + c[:, None] * np.sin(ang)[None]) * dist
                starts = np.stack([sx, sy, np.repeat(pos[:, 2:3], 8, 1)], 2).reshape(-1, 3).astype(np.float32)
                fr = self.w.rays(starts, np.array([[0, 0, -1.0]], np.float32), 1200.0).reshape(n, 8)
                ez = pos[:, 2:3] - fr * 1200.0               # the floor under that spot (a liquid's bottom: the ray goes through it)
                cc = self.w.contents_n(np.stack([sx, sy, ez + 4.0], 2).reshape(-1, 3)).reshape(n, 8)
                haz[:, 16 * r_:16 * r_ + 8] = (((cc & (C_LAVA | C_SLIME)) != 0) & (fr < 0.999)) & see
        self.last_vel = np.where(visible[:, None], opp_vel, self.last_vel).astype(np.float32)
        lv = rot(self.last_vel) / 400.0 * (seen_t < 5.0)[:, None]
        pd = np.zeros((n, 3), np.float32)
        if len(self.pads):
            k = np.linalg.norm(self.pads[None] - pos[:, None], axis=2).argmin(1)
            pd = np.clip(rot(self.pad_dest[k] - pos) / 1000.0, -3, 3)
        own = np.zeros((n, 18), np.float32)
        dist = np.where(self.ra, np.linalg.norm(self.rp - pos[:, None, :], axis=2), 1e9)
        order = np.argsort(dist, axis=1)[:, :2]
        for j in range(2):
            idx = order[:, j]
            ok = dist[ar, idx] < 1e8
            own[:, 9 * j:9 * j + 3] = np.clip(rot(self.rp[ar, idx] - pos) / 1000.0, -3, 3) * ok[:, None]
            own[:, 9 * j + 3:9 * j + 6] = rot(self.rv[ar, idx]) / 1000.0 * ok[:, None]
            kind = self.rw[ar, idx]
            own[:, 9 * j + 6], own[:, 9 * j + 7], own[:, 9 * j + 8] = ok & (kind == RL), ok & (kind == GL), ok & (kind == PG)
        return np.concatenate([haz, lv, pd, own], 1).astype(np.float32)

    def _dense(self, eye, yaw, pit):
        """the inputs of N_DENSE (nothing when the experiment is off)"""
        if not N_DENSE:
            return np.zeros((self.n, 0), np.float32)
        zf = np.where(self.zoom, ZOOM, 1.0)[:, None]
        gy = (yaw[:, None, None] + DENSE_YAW[None, None, :] * zf[:, :, None]).repeat(len(DENSE_PITCH), 1).reshape(self.n, -1)
        gp = (pit[:, None, None] + DENSE_PITCH[None, :, None] * zf[:, :, None]).repeat(len(DENSE_YAW), 2).reshape(self.n, -1)
        vd = np.stack([np.cos(gp) * np.cos(gy), np.cos(gp) * np.sin(gy), -np.sin(gp)], 2).astype(np.float32)
        return self.w.rays_each(eye, vd, 2000.0).astype(np.float32)

    def _pad_ear(self, yaw):
        """the inputs of N_PAD and N_EAR"""
        rel = self.ear[:, 0] - yaw
        on = (self.ear_t < 3.0).astype(np.float32)
        return np.stack([self.pad / (PAD_DEG / 2.0), (self.pad_lift > 0).astype(np.float32),
                         (self.ear_t < 0.06).astype(np.float32), np.exp(-2.0 * self.ear_t),
                         np.sin(rel) * on, np.cos(rel) * on, self.ear[:, 1] * on, self.ear[:, 2] * on, self.ear[:, 3] * on,
                         ((self.ear_hum == RG) & (self.ear_t < 0.5)).astype(np.float32),
                         ((self.ear_hum == LG) & (self.ear_t < 0.5)).astype(np.float32)], 1).astype(np.float32)

    def _drop_weapon(self, v):
        """player v, killed by another player, leaves the weapon he held (see DROPS)"""
        w = int(self.weapon[v])
        if ALWAYS[w] or self.ammo[v, w] <= 0:
            return
        m = int(v) // (self._others_arr().shape[1] + 1)
        if self.kind[m] != NORMAL:
            return
        s = self.state
        p0 = s[v, :3].astype(np.float32) + np.array([0, 0, 8.0], np.float32)
        yr = np.radians(float(self.yaw[v]))
        fw = np.array([np.cos(yr), np.sin(yr), 0.0], np.float32)
        fr = float(self.w.trace(p0, p0 + fw * (DROP_THROW + 16.0))["fraction"])          # thrown the way he faced, up to a wall
        p1 = p0 + fw * max(0.0, fr * (DROP_THROW + 16.0) - 16.0)
        fl = float(self.w.trace(p1, p1 - np.array([0, 0, 600.0], np.float32))["fraction"])
        if fl >= 0.999:
            return                                            # no floor under it: it fell out of the map
        p1 = p1 - np.array([0, 0, fl * 600.0 - 24.0], np.float32)
        for hz in self.hurt_zones:                           # (into lava or a pit: gone)
            if hz[0] <= p1[0] <= hz[3] and hz[1] <= p1[1] <= hz[4] and p1[2] - 24.0 <= hz[5] + 8.0:
                return
        free = np.nonzero(self.drop_w[m] < 0)[0]
        j = int(free[0]) if len(free) else int(self.drop_t[m].argmin())
        self.drop_pos[m, j], self.drop_w[m, j], self.drop_t[m, j] = p1, w, DROP_LIFE
        self.stats["drops"] += 1

    def _drops_step(self, reward):
        """the dropped weapons' time runs; a living player who touches one has it (see DROPS)"""
        live = self.drop_w >= 0
        self.drop_t = np.where(live, self.drop_t - DT, 0.0).astype(np.float32)
        self.drop_w[live & (self.drop_t <= 0)] = -1
        s = self.state
        for m, j in zip(*np.nonzero(self.drop_w >= 0)):
            q = self._seats(int(m))
            d = s[q, :3] - self.drop_pos[m, j][None, :]
            near = np.nonzero((np.hypot(d[:, 0], d[:, 1]) < 36) & (np.abs(d[:, 2]) < 56) & (self.hp[q] > 0))[0]
            if not len(near):
                continue
            i = int(q[near[np.hypot(d[near, 0], d[near, 1]).argmin()]])
            w = int(self.drop_w[m, j])
            had = bool(self.has[i, w])
            self.has[i, w] = True
            self.ammo[i, w] = min(AMMO_MAX[w], self.ammo[i, w] + DROP_AMMO[w])
            self.drop_w[m, j] = -1
            self.stats["pick_drop"] += 1
            self.stats["pick_drop_new"] += int(not had)
            self.stats["pick_wp"] += 1
            self.stats["pick_wpnew"] += int(not had)
            self._hear(0, np.array([i]), 3)
            if not self.first_wp[i]:
                self.first_wp[i] = True
                self.stats["first_wp"] += np.array([float(self.life_t[i]), 1.0])
            if not had:
                reward[i] += self.item_reward * 25.0 / 100.0             # as any weapon he did not have
                self.r_long[i] += self.item_reward * 25.0 / 100.0
            want_ = WEAPONS[w].upper()
            if want_ in INTENTS and self.intent[i] == INTENTS.index(want_) and not self.intent_done[i]:
                self.intent_done[i] = True                               # he has what he was going for
                self.stats["intent_trips"][1] += 1
                self.stats["intent_reach"] += float(self.intent_t[i])

    def _drops(self, pos, eye, rot, fdir):
        """the inputs of N_DROP: the nearest weapon a dead player left that he can see: where (3), that there is one,
        whether it is a rocket launcher, a lightning gun or a railgun, and the share of its time it has left"""
        n = self.n
        out = np.zeros((n, N_DROP), np.float32)
        if not (self.drop_w >= 0).any():
            return out
        grp = np.arange(n) // (self._others_arr().shape[1] + 1)
        w = self.drop_w[grp]
        p = self.drop_pos[grp]
        tov = p - eye[:, None, :]
        dd = np.linalg.norm(tov, axis=2) + 1e-6
        u = (tov / dd[:, :, None]).astype(np.float32)
        cand = (w >= 0) & ((u * fdir[:, None, :]).sum(2) > self.fov()[2][:n, None]) & (dd < 1500.0)
        sees = np.zeros(w.shape, bool)
        ci, cj = np.nonzero(cand)
        if len(ci):
            fr = self.w.rays_each(eye[ci].astype(np.float32), u[ci, cj][:, None, :], 1500.0, mask=self.sight)[:, 0]
            sees[ci, cj] = fr * 1500.0 >= dd[ci, cj] - 24
        dsee = np.where(sees, dd, 1e9)
        j = dsee.argmin(1)
        ar = np.arange(n)
        ok = dsee[ar, j] < 1e8
        wj = w[ar, j]
        out[:, 0:3] = np.clip(rot(p[ar, j] - pos) / 1000.0, -3, 3) * ok[:, None]
        out[:, 3] = ok
        out[:, 4], out[:, 5], out[:, 6] = ok & (wj == RL), ok & (wj == LG), ok & (wj == RG)
        out[:, 7] = np.where(ok, self.drop_t[grp][ar, j] / DROP_LIFE, 0.0)
        return out

    def _teach_drop(self, ri, pos, tp):
        """the walking teacher: a big weapon he lacks that a dead player left in plain sight within DROP_TEACH units is
        gone for first (straight at it); returns the target points and who is on such a way"""
        on = np.zeros(len(ri), bool)
        if not len(ri) or not (self.drop_w >= 0).any():
            return tp, on
        grp = ri // (self._others_arr().shape[1] + 1)
        up = np.array([0, 0, 8.0], np.float32)
        for a_ in np.nonzero((self.drop_w[grp] >= 0).any(1))[0]:
            i = int(ri[a_])
            best, bd = -1, DROP_TEACH
            for j in np.nonzero(self.drop_w[grp[a_]] >= 0)[0]:
                w = int(self.drop_w[grp[a_], j])
                d = self.drop_pos[grp[a_], j] - pos[a_]
                hd = float(np.hypot(d[0], d[1]))
                if w in (RL, LG, RG) and not self.has[i, w] and hd < bd and abs(float(d[2])) < 64.0 \
                        and self.w.trace(pos[a_] + up, self.drop_pos[grp[a_], j] + up, mask=self.sight)["fraction"] >= 0.999:
                    best, bd = int(j), hd
            if best >= 0:
                tp[a_] = self.drop_pos[grp[a_], best]
                on[a_] = True
        return tp, on

    def _knowledge(self):
        """how well each player knows where his enemy is, 0 to 1 (see KNOW_PAY)"""
        return np.where(self.acquired, 1.0, 0.5 * np.clip(1.0 - self.seen_t / KNOW_FADE, 0.0, 1.0))

    def _note_close(self, vh, s, to, dist):
        """players vh have their enemy in view: their own speed toward him (plus = closing in), booked by health plus armor"""
        own = (s[vh, 3:6] * to[vh]).sum(1) / dist[vh]
        st_ = self.hp[vh] + self.armor[vh]
        b_ = np.where(st_ < 60.0, 0, np.where(st_ <= 125.0, 1, 2))
        np.add.at(self.stats["close_v"], b_, own)
        np.add.at(self.stats["close_n"], b_, 1)
        dz_ = to[vh, 2] + self._eye(s)[vh, 2] - s[vh, 2]     # the enemy's feet above his own (B-160)
        np.add.at(self.stats["high"], np.where(dz_ > 48.0, 0, np.where(dz_ < -48.0, 2, 1)), 1)

    def _high(self, by, s, n):
        """who stood higher at each hit (B-160): counted always. With HIGH_PAY a hit from above is worth more and one from
        below less, to the one who dealt it and to the one who took it: returns the damage points that adds for each
        player as the one who dealt and as the one who took (None when the switch is off). The damage he is shown is
        not changed."""
        plus = np.zeros(n, np.float32) if HIGH_PAY > 0 else None
        minus = np.zeros(n, np.float32) if HIGH_PAY > 0 else None
        for (i_, v_), d_ in by.items():
            if i_ == v_:
                continue                                    # his own splash
            up_ = float(s[i_, 2] - s[v_, 2])                 # the one who dealt it stood this much higher
            if self.script[i_] == 0:
                self.stats["high_dmg"][0 if up_ < -48.0 else 2 if up_ > 48.0 else 1] += d_
            if plus is not None:
                f_ = HIGH_PAY * min(1.0, max(-1.0, up_ / HIGH_Z)) * d_
                plus[i_] += f_
                minus[v_] += f_
                if self.script[i_] == 0:
                    self.stats["high_pay"] += f_ * self.dmg_reward
        return None if plus is None else (plus, minus)

    def _mates(self, i):
        """the other players of player i's group"""
        return [i ^ 1]

    def _slot(self, j):
        """a player's place in his group"""
        return j % 2

    def _trip_goal(self, intent, node, R=None, who=None):
        """the route goal each player's intention means from the point he stands at: where a kind has several items
        (NEAREST) the one the shortest way leads to; -1 for no intention or a thing the map has not. R: the ways that
        count (a jump run's; the walking map's if not given)"""
        gi = np.array(self.intent_gi)[intent]
        T_ = (self.route if R is None else R).T
        if self.hold_n:                                      # (ways without the holding places' rows: no target there)
            gi = np.where(gi >= len(T_), -1, gi)
        for k_, gs_ in self.intent_more.items():
            w_ = np.nonzero(np.asarray(intent) == k_)[0]
            if len(w_):
                gi[w_] = gs_[T_[gs_][:, np.asarray(node)[w_]].argmin(0)]
        if FIGHT_TARGET:                                     # the enemy: the route goal nearest to where he believes him to be
            w_ = np.nonzero(np.asarray(intent) == EN_INTENT)[0]
            if len(w_) and who is None and len(gi) == self.n:
                who = np.arange(self.n)
            if len(w_) and who is not None:
                p_ = np.asarray(who)[w_]
                t_ = T_[:len(self.route_goal), (self.route if R is None else R).locate(self.known[p_])]      # (an item's row: not a holding place's)
                gi[w_] = np.where((self.seen_t[p_] <= EN_KNOWN) & (t_.min(0) < 1e8), t_.argmin(0), -1)
        return gi

    def set_ways(self, legs="file", untested=None):
        """WAYS: the second and third sets of ways (sim/ways.py), made or made anew. legs: what was measured of this map's
        ways on his legs ("file": sim/pro_ways_legs/<map>.json; a dict or None: tools/ways_check.py's own passes);
        untested: ways never measured are taken too (default: WAY_UNTESTED)."""
        import ways as WY_
        X_ = self.route_o if self.route_o is not None else self.route      # (JUMP_OPEN: his ways in games are those with the open jumps)
        G_ = WY_.Graph(X_.nodes, X_.radj)
        self.way_legs = WY_.load_legs(self.way_map) if isinstance(legs, str) else legs
        self.way_plan, self.way_report = WY_.plan(WY_.load(self.way_map), G_, X_.locate, X_.T, X_.walk, X_.goals, len(self.route_goal),
                                                  legs=self.way_legs, untested=WAY_UNTESTED if untested is None else bool(untested))
        WY_.route_alts(X_, self.way_plan, G_)
        self.way_field, self.t_ways = X_, {}
        return G_

    def _on_way(self, g, node, t, nx=None, via=None, w=None):
        """WAYS: for the players whose way (w; his own now if not given) is the second or third set, the seconds to go to
        goal g from point `node` by that set in place of the shortest's t, and its next point and the plate or entrance
        of its step in place of nx and via where those are given. Arrays over all players."""
        X = self.way_field
        if X is None:
            return t, nx, via
        w = np.where(self.run_k >= 0, 0, self.way) if w is None else w        # (in an item run or a jump run: the shortest)
        sel = np.nonzero(np.asarray(w) > 0)[0]
        if not len(sel):
            return t, nx, via
        k_, g_, n_ = np.asarray(w)[sel] - 1, np.asarray(g)[sel], np.asarray(node)[sel]
        t = np.array(t, copy=True)
        t[sel] = X.wT[k_, g_, n_]
        if nx is not None:
            nx = np.array(nx, copy=True)
            nx[sel] = X.wnext[k_, g_, n_]
        if via is not None:
            via = np.array(via, copy=True)
            via[sel] = X.wvia[k_, g_, n_]
        return t, nx, via

    def _alt(self):
        """the players whose ways are not the walking map's, with their ways: those of a jump run (every jump in use), and
        the other learners where jumps are open in games (JUMP_OPEN). [(a flag per player, the route field)]"""
        out = []
        if self.route_j is not None and self.jrun.any():
            if len(self.jfields) > 1:                        # (JUMP_ALL: a try at a jump on no item's way has its own ways)
                for f_ in np.unique(self.jrun_f[self.jrun]):
                    out.append((self.jrun & (self.jrun_f == f_), self.jfields[int(f_)]))
            else:
                out.append((self.jrun, self.route_j))
        if self.route_o is not None:
            m_ = (self.script == 0) & ~self.jrun
            if m_.any():
                out.append((m_, self.route_o))
        return out

    def _goal_state(self, gi, grp):
        """for route goal gi and every player: is it there, and the seconds until it is back (by what he knows with
        ITEM_BELIEF, else the truth)"""
        it = self.route_item[gi]
        if not ITEM_BELIEF:
            return self.item_up[grp, it], self.item_t[grp, it]
        resp = float(self.item_def[it][2])
        bt = self.bel_t[:, gi]
        return bt >= resp, np.maximum(0.0, resp - bt)

    def _belief_update(self):
        """ITEM_BELIEF: what each player knows about the things he can go for (see ITEM_BELIEF)"""
        if not self.route_item:
            return
        n = self.n
        eye = self._eye(self.state)
        yr_, pr_ = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)], 1)
        gsz = self._others_arr().shape[1] + 1
        grp = np.arange(n) // gsz
        items = np.array(self.route_item)
        up = self.item_up[:, items]                          # (matches, goals): the truth
        self.bel_t = np.minimum(self.bel_t + DT, 99.0).astype(np.float32)
        pos = self.state[:, :3]
        if self.bel_prev is not None and self.bel_prev.shape == up.shape:
            for m, g in zip(*np.nonzero(self.bel_prev & ~up)):     # taken since the last look: who is in earshot knows
                q = np.arange(m * gsz, (m + 1) * gsz)
                near = np.linalg.norm(pos[q] - self.item_pos[items[g]], axis=1) < HEAR_EVT
                self.bel_t[q[near], g] = 0.0
        self.bel_prev = up.copy()
        self.bel_tick += 1
        if self.bel_tick % 4:                                # the look at the items' places: ten times a second
            return
        for g, it in enumerate(items):
            tov = self.item_pos[it][None, :] - eye
            dd = np.linalg.norm(tov, axis=1) + 1e-6
            u = (tov / dd[:, None]).astype(np.float32)
            ci = np.nonzero(((u * fdir).sum(1) > self.fov()[2][:n]) & (dd < BELIEF_SEE) & (self.hp > 0))[0]
            if not len(ci):
                continue
            fr = self.w.rays_each(eye[ci], u[ci][:, None, :], BELIEF_SEE, mask=self.sight)[:, 0]
            sees = ci[fr * BELIEF_SEE >= dd[ci] - 24]
            if not len(sees):
                continue
            there = up[grp[sees], g]
            resp = float(self.item_def[it][2])
            bt = self.bel_t[sees, g]
            self.bel_t[sees, g] = np.where(there, 99.0, np.where(bt >= resp, resp / 2.0, bt))

    def _shot_supply(self):
        """SHOT_COST: how well this map feeds each gun, and where its ammo lies (see SHOT_COST)"""
        units = np.zeros(NW, np.float32)                     # what the map gives per minute
        units[MG] = LOADOUTS["mg"][1][MG]                    # the spawn's bullets
        src = [[] for _ in range(NW)]
        for k, d in enumerate(self.item_def):
            if d[0] == "wp":
                units[d[1]] += d[3]
                src[d[1]].append(k)
            elif d[0] == "am":
                units[d[1]] += d[3] * 60.0 / d[2]
                src[d[1]].append(k)
            elif d[0] == "pack":
                units += PACK_AMMO * 60.0 / d[2]
                for w_ in range(NW - 1):
                    src[w_].append(k)
        self.shot_fire = units * W_REFIRE                    # seconds of fire per minute
        self.shot_scarce = np.clip(SHOT_REF_FIRE / np.maximum(self.shot_fire, 1e-6), 0.5, 2.0).astype(np.float32)
        if self.route is not None:
            far = np.full(len(self.route.nodes), 1e9, np.float32)
            self.shot_way = np.stack([self.route.nearest(self.item_pos[s_]) if s_ else far for s_ in src])

    def note_pickup(self, i, k):
        """player i took the mega health (k = 0) or the red armor (k = 1): he knows, and so do those in earshot"""
        s = self.state
        self.it_t[i, k] = 0.0
        for j in self._mates(i):
            if np.linalg.norm(s[j, :3] - s[i, :3]) < HEAR_EVT:
                self.it_t[j, k] = 0.0
                self.e_got[j, self._slot(i), k] = 1.0

    def note_death(self, v, killer):
        """player v died: his killer knows, and those in earshot"""
        s = self.state
        for j in self._mates(v):
            if j == killer or np.linalg.norm(s[j, :3] - s[v, :3]) < HEAR_EVT:
                self.e_life[j, self._slot(v)] = 0.0
                self.e_got[j, self._slot(v)] = 0.0
                self._v02_void(j, v)

    def note_hit(self, v, dmg):
        """player v took dmg from an enemy: the flinch (used by the game-server plugin; step() does the same itself)"""
        add = min(FLINCH_MAX, FLINCH_PER_DMG * float(dmg))
        self.flinch[v] = min(FLINCH_MAX, float(self.flinch[v]) + add)
        self.percept[v] += (add * self.rng.normal(0, 1, 2)).astype(np.float32)

    def _mem(self, opp):
        """the inputs of N_MEM"""
        n = self.n
        ar = np.arange(n)
        known = (self.it_t < 90.0).astype(np.float32)
        items = np.stack([known[:, 0], np.minimum(self.it_t[:, 0] / 35.0, 2.0) * known[:, 0],
                          known[:, 1], np.minimum(self.it_t[:, 1] / 25.0, 2.0) * known[:, 1]], 1)
        el = self.e_life[ar, self._slot(opp)]
        ek = (el < 90.0).astype(np.float32)
        life = np.stack([np.minimum(self.life_t / 30.0, 2.0), ek, np.minimum(el / 30.0, 2.0) * ek], 1)
        focus = np.clip(self.focus / FOCUS_SECS, -0.25, 1.0)[:, None]
        return np.concatenate([items, self.e_got[ar, self._slot(opp)][:, MEM_COLS], life, focus], 1).astype(np.float32)

    def _routes(self, pos, rot):
        """the inputs of N_ROUTE"""
        out = np.zeros((self.n, N_ROUTE), np.float32)
        R = self.route
        if R is None:
            return out
        node = R.locate(pos)
        off = np.linalg.norm(R.nodes[node] - pos, axis=1) / 320.0
        alt = self._alt()
        for gi, lab in enumerate(self.route_goal):
            t = R.T[gi, node]
            for m_, X_ in alt:
                t = np.where(m_, X_.T[gi, node], t)
            v_, c_ = np.minimum((t + off) / 10.0, 2.0) * (t < 1e8), ROUTE_ITEMS.index(lab)
            if self.route_goal.index(lab) == gi:
                out[:, c_] = v_
            else:                                            # another item of the kind (NEAREST): the nearer one's seconds
                out[:, c_] = np.where((t < 1e8) & ((out[:, c_] == 0) | (v_ < out[:, c_])), v_, out[:, c_])
        return out

    def _cell(self, p, ok):
        """the map cell a point lies in, as a number for the learned table (see N_INTENT); 0 = unknown"""
        c = np.clip(((p[:, :2] - self.lo[:2]) / CELL_SIZE).astype(np.int64), 0, self.cell_n - 1)
        layer = (p[:, 2] > self.cell_zmid).astype(np.int64)
        idx = 1 + layer * int(self.cell_n[0] * self.cell_n[1]) + c[:, 1] * int(self.cell_n[0]) + c[:, 0]
        return np.where(ok, np.minimum(idx, MAX_CELLS - 1), 0).astype(np.float32)

    def _intent(self, pos, rot, known, seen_t):
        """the inputs of N_INTENT"""
        n = self.n
        out = np.zeros((n, N_INTENT), np.float32)
        out[np.arange(n), 45 + self.style] = 1.0            # his playing style
        R = self.route
        k = self.intent
        if R is not None:
            node = R.locate(pos)
            gi = self._trip_goal(k, node)
            alt = self._alt()
            for m_, X_ in alt:                               # (a jump run, or jumps open in games: the ways with those jumps)
                gi[m_] = self._trip_goal(k[m_], node[m_], X_, who=np.nonzero(m_)[0])
            valid = gi >= 0
            g = np.maximum(gi, 0)
            off = np.linalg.norm(R.nodes[node] - pos, axis=1) / 320.0
            t = R.T[g, node]
            nx = R.walk[g, node]
            via_ = R.via[g, node]
            for m_, X_ in alt:
                t, nx, via_ = np.where(m_, X_.T[g, node], t), np.where(m_, X_.next[g, node], nx), np.where(m_[:, None], X_.via[g, node], via_)
            if WAYS:                                         # (his way: the seconds and the next step of the set he chose; N_B3 reads the rest)
                self._way_obs = (g, node, valid & (t < 1e8) & (self.run_k < 0), t)
                t, nx, via_ = self._on_way(g, node, t, nx, via_)
            ok = valid & (t < 1e8)
            wp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[g])
            wp = np.where(((self.state[:len(node), 6] > 0.5) & ~np.isnan(via_[:, 0]))[:, None], via_, wp)   # a jump pad's plate, a teleporter's entrance
            out[:, 0] = np.minimum((t + off) / 10.0, 2.0) * ok
            out[:, 1:4] = np.clip(rot(wp - pos) / 200.0, -1.0, 1.0) * ok[:, None]
            grp = np.arange(n) // (self._others_arr().shape[1] + 1)
            gq_ = np.minimum(g, len(self.route_item) - 1)    # (a holding place's row is no item's: see below)
            it = np.array(self.route_item)[gq_]
            if ITEM_BELIEF:                                  # by what he knows
                resp_ = np.array([self.item_def[i_][2] for i_ in self.route_item], np.float32)[gq_]
                bt_ = self.bel_t[np.arange(n), gq_]
                out[:, 4] = (bt_ >= resp_) * valid
                out[:, 5] = np.minimum(np.maximum(0.0, resp_ - bt_) / 30.0, 2.0) * valid
            else:
                out[:, 4] = self.item_up[grp, it] * valid
                out[:, 5] = np.minimum(self.item_t[grp, it] / 30.0, 2.0) * valid
        out[k >= EN_INTENT, 4:6] = 0.0                      # (the enemy, a holding place: no item, nothing to be "up")
        oh_ = np.eye(len(INTENTS), dtype=np.float32)[k]
        out[:, 6:12] = oh_[:, :6]
        out[:, 49:51] = oh_[:, 6:8]                         # (the yellow armors, added after the style inputs)
        out[:, 12] = np.minimum(self.intent_t / 10.0, 2.0)
        if self.cell_table is not None:                     # what the map reader says about his cell and the enemy's
            out[:, 13:29] = self.cell_table[self._cell(pos, np.ones(n, bool)).astype(np.int64)]
            out[:, 29:45] = self.cell_table[self._cell(known, seen_t < 5.0).astype(np.int64)] * (seen_t < 5.0)[:, None]
        return out

    def _v9(self, pos, rot):
        """the inputs of N_V9: item respawns heard, the four nearest spawn points"""
        n = self.n
        out = np.zeros((n, N_V9), np.float32)
        out[:, :4] = np.exp(-self.resp_t)
        if len(self.spawns):
            d = np.linalg.norm(self.spawns[None, :, :] - pos[:, None, :], axis=2)
            order = np.argsort(d, axis=1)[:, :4]
            for j in range(min(4, len(self.spawns))):
                out[:, 4 + 3 * j:7 + 3 * j] = np.clip(rot(self.spawns[order[:, j]] - pos) / 1000.0, -3, 3)
        return out

    def note_respawn(self, k, who=None):
        """item k came back: the players (who, or every member of the item's match) within earshot hear it"""
        kind, val, resp, cap, lab = self.item_def[k]
        cat = 0 if lab == "MH" else 1 if lab == "RA" else 2 if kind == "wp" else 3
        idx = np.arange(self.n) if who is None else np.asarray(who)
        near = np.linalg.norm(self.state[idx, :3] - self.item_pos[k][None, :], axis=1) < HEAR_EVT
        self.resp_t[idx[near], cat] = 0.0

    def intent_rule(self):
        """a hand-written prior for the intention head, like the game bot's item table (owner, 2026-10-06: "seeding is
        fine here"): the mega when below 100 health and it is up or about to be, the red armor when below 50 armor,
        else the nearest big weapon he lacks that is up, else nothing. Imitated with a fading weight, not a reward."""
        n = self.n
        out = np.zeros(n, np.int64)
        R = self.route
        if R is None:
            return out
        node = R.locate(self.state[:, :3])
        Tn = R.T[:len(self.route_goal), node]                # seconds to every item's goal from where each player stands
        if PRO_WAYS:                                         # a scripted player walks: only the walking map's ways count for him
            Tn = R.T_walk[:, node] if RULE_WALK else np.where((self.script > 0)[None, :], R.T_walk[:, node], Tn)   # (RULE_WALK: for him too)
        if self.route_o is not None:                         # (JUMP_OPEN: the jumps that are open count for him)
            Tn = np.where(((self.script == 0) & ~self.jrun)[None, :], self.route_o.T[:len(self.route_goal), node], Tn)
        grp = np.arange(n) // (self._others_arr().shape[1] + 1)
        best_t = np.full(n, 1e9, np.float32)
        for gi, lab in enumerate(self.route_goal):
            t = Tn[gi]
            it = self.route_item[gi]
            gu_, gb_ = self._goal_state(gi, grp)
            soon = gu_ | (gb_ < t + 3.0)
            if WALK_FIX:
                soon = soon & (t < 1e8)                      # nothing he has no way to
            k = INTENTS.index(lab)
            if lab == "MH":
                want = (self.hp < 100.0) & soon
                out = np.where(want & (out == 0), k, out)
            elif lab == "RA":
                want = (self.armor < 50.0) & soon
                out = np.where(want & (out == 0), k, out)
        for gi, lab in enumerate(self.route_goal):           # then the nearest big weapon he does not own
            if lab in ("RL", "RG", "LG"):
                t = Tn[gi]
                it = self.route_item[gi]
                want = (out == 0) & ~self.has[:, WEAPONS.index(lab.lower())] & self._goal_state(gi, grp)[0] & (t < best_t)
                best_t = np.where(want, t, best_t)
                out = np.where(want, INTENTS.index(lab), out)
        if PRO_ITEMS:                                        # the pros' order (see PRO_ITEMS)
            out = np.zeros(n, np.int64)
            bare = self.has[:, [RL, RG, LG]].sum(1) == 0
            best_t = np.full(n, 1e9, np.float32)
            for gi, lab in enumerate(self.route_goal):       # armed: armor and health he can still use
                t = Tn[gi]
                it = self.route_item[gi]
                gu_, gb_ = self._goal_state(gi, grp)
                soon = (gu_ | (gb_ < t + 3.0)) & (t < 1e8)
                use = (self.armor < 150.0) if lab in ("YA", "YA2") else (self.armor < 175.0) if lab == "RA" else \
                    (self.hp < 175.0) if lab == "MH" else np.zeros(n, bool)
                want = ~bare & use & soon & (t < best_t)
                best_t = np.where(want, t, best_t)
                out = np.where(want, INTENTS.index(lab), out)
            best_t = np.full(n, 1e9, np.float32)
            for gi, lab in enumerate(self.route_goal):       # a big weapon: first of all when bare, else when nothing above
                if lab in ("RL", "RG", "LG"):
                    t = Tn[gi]
                    it = self.route_item[gi]
                    te = t - (PRO_RL_EDGE if lab == "RL" else 0.0)
                    want = (bare | (out == 0)) & ~self.has[:, WEAPONS.index(lab.lower())] & self._goal_state(gi, grp)[0] & (t < 1e8) & (te < best_t)
                    best_t = np.where(want, te, best_t)
                    out = np.where(want, INTENTS.index(lab), out)
        sw = STYLE_W[self.style]                             # a preferred weapon he lacks comes first
        for gi, lab in enumerate(self.route_goal):
            if lab in ("RL", "RG", "LG"):
                w_ = WEAPONS.index(lab.lower())
                it = self.route_item[gi]
                gu_, gb_ = self._goal_state(gi, grp)
                want = (sw == w_) & ~self.has[:, w_] & (Tn[gi] < 1e8) & (gu_ | (gb_ < Tn[gi] + 3.0))
                out = np.where(want, INTENTS.index(lab), out)
        hold = (self.script == 3) & (self.sc_persona == HOLDER)
        if hold.any():                                       # the holder: the mega and the red armor on their clocks, whatever he has
            best = np.full(n, 1e9, np.float32)
            pick = np.zeros(n, np.int64)
            for gi, lab in enumerate(self.route_goal):
                if lab in ("MH", "RA"):
                    t = Tn[gi]
                    gu_, gb_ = self._goal_state(gi, grp)
                    eta = np.where(gu_, 0.0, gb_)            # seconds until it is there, as far as he knows
                    go = hold & (t < 1e8) & (eta < t + HOLD_EARLY) & (eta < best)
                    best = np.where(go, eta, best)
                    pick = np.where(go, INTENTS.index(lab), pick)
            out = np.where(pick > 0, pick, out)
        return out

    def intend(self, choice, who, way=None):
        """the intention head: read once a second per player (staggered), at once after a spawn; held in between.
        who = the players it applies to (the game-server plugin passes one). Returns who was read this frame."""
        n = self.n
        self.int_tick += 1
        live = who & (((self.int_tick + np.arange(n)) % INTENT_EVERY == 0) | self.intent_new)
        choice = np.asarray(choice, np.int64)
        if not FIGHT_TARGET:                                 # (the enemy as a target: only with the switch)
            choice = np.where(choice == EN_INTENT, 0, choice)
        choice = np.where(choice >= HOLD_INTENT + self.hold_n, 0, choice)     # (a holding place: only with TARGETS, and one the map has)
        may = (self.intent == 0) | self.intent_done | (self.intent_t >= INTENT_HOLD) | self.intent_gone     # a choice holds (INTENT_HOLD)
        if TARGETS_FREE:                                     # (a holding place can be left at any reading, as "nothing")
            may = may | (self.intent >= HOLD_INTENT)
        live = live & may
        changed = live & (choice != self.intent)
        self.intent = np.where(live, choice, self.intent)
        self.intent_t = np.where(changed, 0.0, self.intent_t + DT * who).astype(np.float32)
        self.intent_new = np.where(live, False, self.intent_new)
        self.intent_done = np.where(changed, False, self.intent_done)
        self.intent_live, self.intent_changed = live, changed
        if WAYS:                                             # his way: read on the frames his intention is, held with it (see WAYS)
            self.way_was = self.way.copy()
            if way is not None:
                self.way = np.where(live, np.clip(np.asarray(way, np.int64), 0, N_WAYS - 1), self.way)
            self.way_live = live if way is not None else np.zeros(n, bool)
        return live

    def _eye(self, s):
        e = s[:, :3].copy()
        e[:, 2] += np.where(self.duck[:len(e)], VIEW_H_DUCK, VIEW_H)
        return e

    def fov(self):
        """half-width and half-height of each player's view (radians) and the cosine of his sight cone"""
        z = np.where(self.zoom, ZOOM, 1.0)
        return FOV_H * z, FOV_V * z, np.cos(np.radians(55.0) * z)

    def note_shots(self, src):
        """players src fired this frame: the opponent notes it if he has the shooter in view (after the noticing
        delay) or is within earshot; a bullet, rail or lightning line that he can see is remembered as a trail"""
        src = np.asarray(src)
        if not len(src):
            return
        s = self.state
        lis = src ^ 1
        k_ = np.repeat(self.kind, 2)[lis]
        alone = ((k_ == MOVE) | (k_ == SOLO) | ((k_ == COURSE) & ~self.gun[lis]))
        d = np.linalg.norm(s[src, :3] - s[lis, :3], axis=1)
        seen = self.acquired[lis] & ~alone
        ok = (seen | (d < HEAR_EVT)) & ~alone & (self.hp[lis] > 0)
        self.shot_t[lis[ok]] = 0.0
        self.shot_w[lis[ok]] = self.weapon[src[ok]]
        self.shot_seen[lis[ok]] = seen[ok]
        # the line of a hitscan shot (not rockets, grenades, plasma: those are projectiles he sees anyway)
        hit = np.isin(self.weapon[src], (RG, LG, MG, HMG, SG)) & ~alone & (self.hp[lis] > 0)
        if hit.any():
            sh, li = src[hit], lis[hit]
            eye = self._eye(s)
            yr, pr = np.radians(self.yaw[sh]), np.radians(self.pitch[sh])
            dv = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
            reach = np.where(self.weapon[sh] == LG, 768.0, 4000.0)
            along = np.clip(((eye[li] - eye[sh]) * dv).sum(1), 0.0, reach)
            near = eye[sh] + dv * along[:, None]
            to = near - eye[li]
            dn = np.linalg.norm(to, axis=1) + 1e-6
            yl, pl = np.radians(self.yaw[li]), np.radians(self.pitch[li])
            fl = np.stack([np.cos(pl) * np.cos(yl), np.cos(pl) * np.sin(yl), -np.sin(pl)], 1)
            vis = (self.acquired[li] | ((to * fl).sum(1) / dn > self.fov()[2][li])) & (dn < 2000.0)
            for k in np.nonzero(vis)[0]:
                if self.acquired[li[k]] or self.w.trace(eye[li[k]], near[k].astype(np.float32), mask=self.sight)["fraction"] >= 0.999:
                    self.trail_t[li[k]] = 0.0
                    self.trail_p[li[k]] = near[k]

    def _fight(self, pos, eye, rot, visible):
        """the inputs added on 2026-10-05 (see N_FIGHT)"""
        n = self.n
        opp = np.arange(n) ^ 1
        t = self.shot_t
        known = (t < 5.0).astype(np.float32)
        reload_ = np.clip((W_REFIRE[self.shot_w] - t) / 1.5, 0.0, 1.0) * known
        shots = np.concatenate([(t < 0.06).astype(np.float32)[:, None], np.exp(-2.0 * t)[:, None],
                                (np.minimum(t, 3.0) / 3.0)[:, None], np.eye(NW, dtype=np.float32)[self.shot_w][:, OBS_W] * known[:, None],
                                reload_[:, None], (self.shot_seen & (t < 5.0)).astype(np.float32)[:, None]], 1)
        fade = np.exp(-4.0 * self.trail_t)
        on = (self.trail_t < 1.0).astype(np.float32)
        trail = np.concatenate([np.clip(rot(self.trail_p - eye) / 500.0, -4, 4) * on[:, None], fade[:, None]], 1)
        v_ = visible.astype(np.float32)
        body = np.stack([self.duck[opp].astype(np.float32) * v_, (self.state[opp, 6] < 0.5).astype(np.float32) * v_], 1)
        hand = np.concatenate([(self.key_last - np.array([1, 1, 0]))[:, :2].astype(np.float32),
                               (self.key_last[:, 2:3] == 1).astype(np.float32) - (self.key_last[:, 2:3] == 2).astype(np.float32),
                               (self.key_tok / KEY_BURST)[:, None],
                               (self.key_hold >= FINGER_HOLD[None, :]).astype(np.float32)], 1)
        mouse = np.concatenate([self.zoom.astype(np.float32)[:, None],
                                (self.mouse_hold >= MOUSE_HOLD[None, :]).astype(np.float32)], 1)
        heard = (self.pain_t < 1.5).astype(np.float32)
        pain = np.concatenate([np.eye(4, dtype=np.float32)[self.pain_b] * heard[:, None], np.exp(-3.0 * self.pain_t)[:, None]], 1)
        return np.concatenate([shots, trail, body, hand, mouse, pain], 1).astype(np.float32)

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
        self.v02_ht[lis, self._slot(src)] = 0.0              # (N_V02: when and about where he last heard that player)
        self.v02_hp[lis, self._slot(src)] = self.snd_pos[lis, cat]

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
        infov = ((u * fdir).sum(1) > self.fov()[2][:len(u)]) & (dd < 1500)
        sees = np.zeros(n, bool)
        ci = np.nonzero(infov)[0]                             # only trace toward items in view and in range
        if len(ci):
            fr = self.w.rays_each(eye[ci], u[ci][:, None, :], 1500.0, mask=self.sight)[:, 0]
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
            out[k] = np.linalg.norm(b[k] - a[k]) < 1 or self.w.trace(a[k], b[k], mask=self.sight)["fraction"] >= 0.999
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
        self.soak[v] += save
        self.hp[v] -= dmg - save
        return dmg

    # ---------------------------------------------------------------- observation
    def observe(self):
        s = self.state
        pos, vel, ground = s[:, :3], s[:, 3:6], s[:, 6]
        n = self.n
        if ITEM_BELIEF:                                      # what he knows about the things he can go for
            self._belief_update()
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
        if self.fov_sight:                                   # only what the eyes cover (see FOV_H, FOV_V)
            wa = (np.linspace(0, 2 * np.pi, N_WALL, endpoint=False) + np.pi) % (2 * np.pi) - np.pi
            fh, fv, _ = self.fov()
            see = (np.abs(wa)[None, :] <= fh[:, None]) & (np.abs(pit)[:, None] <= fv[:, None])
            walls = np.where(see, walls, UNSEEN).astype(np.float32)
        off = np.stack([c[:, None] * self.floor_off[None, :, 0] - si[:, None] * self.floor_off[None, :, 1],
                        si[:, None] * self.floor_off[None, :, 0] + c[:, None] * self.floor_off[None, :, 1]], 2)
        starts = np.concatenate([pos[:, None, :2] + off, np.repeat(pos[:, None, 2:3], N_FLOOR, 1)], 2)
        floors = self.w.rays(starts.reshape(-1, 3).astype(np.float32), np.array([[0, 0, -1.0]], np.float32),
                             256.0).reshape(n, N_FLOOR)
        if self.fov_sight and not GROUND_SENSE:              # a floor spot is seen if the line from the eyes to it is in view
            fa = (np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False) + np.pi) % (2 * np.pi) - np.pi
            down = np.arctan2(VIEW_H + floors * 256.0, 96.0)             # how far below the horizon that spot lies
            see = (np.abs(fa)[None, :] <= fh[:, None]) & (np.abs(pit[:, None] - down) <= fv[:, None])
            floors = np.where(see, floors, UNSEEN).astype(np.float32)
        eye = self._eye(s)
        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        opp = np.arange(n) ^ 1
        # Reaction time: what the player knows about the opponent (where, how fast, visible or not) is
        # REACT_FRAMES old. The player's own view is current, so the crosshair-to-enemy readings respond to
        # mouse movement immediately, as on a real screen.
        self.opp_hist.append((self.known.copy(), self.acquired.copy(), vel[opp].copy(), self.seen_t.copy()))
        # (2026-10-05) How the enemy is MOVING is read later than where he is: a person follows steady movement
        # closely but needs about 200 ms to pick up a change of direction. So a well-timed reversal shakes the aim.
        keep = max(self.react_frames + FOCUS_LOSS, self.vel_frames) + 1
        while len(self.opp_hist) > keep:
            self.opp_hist.pop(0)
        known, visible, _, seen_t = self.opp_hist[max(0, len(self.opp_hist) - 1 - self.react_frames)]
        rf_ = self.react_frames if self.react_seat is None else self.react_seat     # (SEAT_DELAYS) one number, or one a seat
        if self.react_seat is not None:                      # ... each seat by its own delay (react_frames is the largest)
            pk_ = np.maximum(0, len(self.opp_hist) - 1 - rf_)
            known, visible, seen_t = (np.stack([h_[j_] for h_ in self.opp_hist])[pk_, np.arange(n)] for j_ in (0, 1, 3))
        if self.focus_on:                                    # the delay per player: sharp while focus lasts, then dull
            self.focus = np.where(self.acquired, self.focus - DT, self.focus + FOCUS_REFILL * DT)
            self.focus = np.clip(self.focus, -0.5, FOCUS_SECS).astype(np.float32)
            dly = rf_ + np.where(self.focus > 0, -FOCUS_GAIN, FOCUS_LOSS)
            dly = np.where(self.script == 0, np.maximum(dly, 1), rf_)
            L_ = len(self.opp_hist)
            pick = np.maximum(0, L_ - 1 - dly)
            ar_ = np.arange(n)
            known = np.stack([h_[0] for h_ in self.opp_hist])[pick, ar_]
            visible = np.stack([h_[1] for h_ in self.opp_hist])[pick, ar_]
            seen_t = np.stack([h_[3] for h_ in self.opp_hist])[pick, ar_]
        opp_vel = self.opp_hist[max(0, len(self.opp_hist) - 1 - self.vel_frames)][2]
        self.ear_t += DT
        self.resp_t += DT
        self.it_t += DT                                      # the memory aids (N_MEM) keep their own time here, so the
        self.e_life += DT                                    # game-server plugin, which does not call step(), has them too
        self.life_t += DT
        v_ = np.nonzero(visible)[0]
        self.e_got[v_, self._slot(opp[v_]), 2 + self.weapon[opp[v_]]] = 1.0     # the weapon seen in the enemy's hands
        if self.percept_sigma > 0:                           # the enemy is seen a little off from where he is
            rho = math.exp(-DT / PERCEPT_TAU)
            self.flinch = (self.flinch * math.exp(-DT / FLINCH_TAU)).astype(np.float32)
            sig_ = (self.percept_sigma + self.flinch)[:, None]
            if PERCEPT_SPEED > 0:                            # a target that crosses the view fast is judged worse
                tb_ = known - eye
                br_ = np.stack([np.degrees(np.arctan2(tb_[:, 1], tb_[:, 0])),
                                np.degrees(np.arctan2(tb_[:, 2], np.hypot(tb_[:, 0], tb_[:, 1]) + 1e-6))], 1).astype(np.float32)
                dy_ = (br_[:, 0] - self.bearing[:, 0] + 180.0) % 360.0 - 180.0
                w_ = np.hypot(dy_, br_[:, 1] - self.bearing[:, 1]) / DT * (visible & self.bearing_ok)
                sig_ = sig_ + np.minimum(PERCEPT_SPEED * w_, PERCEPT_SPEED_MAX)[:, None]
                self.bearing, self.bearing_ok = br_, visible.copy()
            self.percept = (rho * self.percept + math.sqrt(1.0 - rho * rho) * sig_ *
                            self.rng.normal(0, 1, (n, 2))).astype(np.float32)
            t_ = known - eye
            hd_ = np.hypot(t_[:, 0], t_[:, 1]) + 1e-6
            d_ = np.linalg.norm(t_, axis=1)
            off = np.tan(np.radians(self.percept)) * d_[:, None] * (visible & (self.script == 0))[:, None]
            known = known + np.stack([-t_[:, 1] / hd_ * off[:, 0], t_[:, 0] / hd_ * off[:, 0], off[:, 1]], 1).astype(np.float32)
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
            if self.fov_sight:
                to_p = orp[ar, idx] - eye
                dn = np.linalg.norm(to_p, axis=1) + 1e-6
                ok &= ((to_p * fdir).sum(1) / dn > self.fov()[2]) | (dn < 400.0)
            rk[:, 9 * j:9 * j + 3] = rot(orp[ar, idx] - pos) / 1000.0 * ok[:, None]
            rk[:, 9 * j + 3:9 * j + 6] = rot(orv[ar, idx]) / 1000.0 * ok[:, None]
            kind = orw[ar, idx]
            rk[:, 9 * j + 6] = ok & (kind == RL)
            rk[:, 9 * j + 7] = ok & (kind == GL)
            rk[:, 9 * j + 8] = ok & (kind == PG)
        self._pm = None                                      # (N_V15's part of the projectiles, for _v15)
        if PROJ_SEE:                                         # only what he sees, the nearest six of it
            rk, self._pm = self._proj(pos, eye, fdir, rot, vel)
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
            if self.fov_sight:                               # the track has to be seen; only its far end is known
                goal[ci_, 1:3] = np.clip(rotc(C["path"][-1][None] - pos[ci_, :2]) / 2000.0, -3, 3)
            else:
                goal[ci_, 1:3] = rotc(ahead(600.0) - pos[ci_, :2]) / 2000.0
                goal[ci_, 4:6] = np.clip(rotc(ahead(200.0) - pos[ci_, :2]) / 500.0, -1, 1)
        obs = np.concatenate([rot(vel) / 400.0, ground[:, None], own, self.mv / 30.0, walls, floors, opp_feat, rk,
                              np.eye(NW, dtype=np.float32)[self.weapon][:, OBS_W], self.has[:, OBS_W].astype(np.float32),
                              (self.ammo / AMMO_MAX)[:, OBS_W], items, goal, self._extra(pos, vel, eye, fdir, up, rot, c, si,
                                                                                         yaw, pit, visible),
                              self._fight(pos, eye, rot, visible), self._mem(opp), self._routes(pos, rot), self._pad_ear(yaw),
                              self._more(pos, rot, c, si, visible, opp_vel, seen_t), self._dense(eye, yaw, pit),
                              self._v9(pos, rot), self._intent(pos, rot, known, seen_t), self._drops(pos, eye, rot, fdir),
                              self._v14(vel, yaw, pit, eye, known, opp_vel, visible, opp),
                              self._v15(pos, yaw, pit, eye, known, seen_t, visible),
                              self._v02(pos, eye, rot, c, si, known, opp), self._b2(pos, c, si), self._b3(pos)], 1)
        return obs.astype(np.float32)

    def _proj(self, pos, eye, fdir, rot, vel):
        """the enemy projectiles he sees (PROJ_SEE): inside his view cone, within PROJ_FAR, the line from his eyes clear.
        -> the old inputs for the nearest two (place, speed, kind), and N_V15's part: the same for the next four, then
        for all six a grenade's fuse left, the seconds to its closest pass, that distance in splash radii"""
        n, S6 = len(pos), N_PROJ + N_PROJ_MORE
        oth = self._others_arr()
        P, V = self.rp[oth].reshape(n, -1, 3), self.rv[oth].reshape(n, -1, 3)
        A, W, G = self.ra[oth].reshape(n, -1), self.rw[oth].reshape(n, -1), self.rage[oth].reshape(n, -1)
        to = P - eye[:, None, :]
        dist = np.linalg.norm(to, axis=2) + 1e-6
        see = A & (dist < PROJ_FAR) & ((to * fdir[:, None, :]).sum(2) / dist > self.fov()[2][:, None])
        ii, kk = np.nonzero(see)
        if len(ii):
            clear = (self.w.lines(eye[ii], P[ii, kk]) if self.sight is None else self.w.lines(eye[ii], P[ii, kk], mask=self.sight)) >= 0.999
            see[ii[~clear], kk[~clear]] = False
        d = np.where(see, dist, 1e9)
        order = np.argsort(d, axis=1)[:, :S6]
        ar = np.arange(n)
        base, more = np.zeros((n, S6, 9), np.float32), np.zeros((n, S6, 3), np.float32)
        rad = np.ones(NW, np.float32)
        rad[RL], rad[GL], rad[PG] = P_RADIUS[RL], P_RADIUS[GL], P_RADIUS[PG]
        for j in range(order.shape[1]):
            idx = order[:, j]
            ok = d[ar, idx] < 1e8
            p_, v_, w_ = P[ar, idx], V[ar, idx], W[ar, idx]
            base[:, j, 0:3] = rot(p_ - pos) / 1000.0 * ok[:, None]
            base[:, j, 3:6] = rot(v_) / 1000.0 * ok[:, None]
            base[:, j, 6], base[:, j, 7], base[:, j, 8] = ok & (w_ == RL), ok & (w_ == GL), ok & (w_ == PG)
            rel, rv_ = p_ - pos, v_ - vel                    # (as if both kept their speed: a grenade's bounce is not foreseen)
            t_ = np.clip(-(rel * rv_).sum(1) / np.maximum((rv_ * rv_).sum(1), 1.0), 0.0, 2.0)
            near = np.linalg.norm(rel + rv_ * t_[:, None], axis=1)
            more[:, j, 0] = np.where(w_ == GL, np.clip((P_FUSE[GL] - G[ar, idx]) / P_FUSE[GL], 0.0, 1.0), 0.0) * ok
            more[:, j, 1] = t_ / 2.0 * ok
            more[:, j, 2] = np.clip(near / rad[w_], 0.0, 3.0) / 3.0 * ok
        return base[:, :N_PROJ].reshape(n, -1), np.concatenate([base[:, N_PROJ:].reshape(n, -1), more.reshape(n, -1)], 1)

    def _v15(self, pos, yaw, pit, eye, known, seen_t, visible):
        """the inputs of N_V15: the jump ahead on his way in a jump run (see JUMPS), and with the grenade launcher in his
        hand how far his view is from the one that lands a grenade where he believes the enemy is"""
        out = np.zeros((len(pos), N_V15), np.float32)
        for m_, J in self._alt():
            ii = np.nonzero(m_)[0]
            node = J.locate(pos[ii])
            gi = self._trip_goal(self.intent[ii], node, J, who=ii)
            g = np.maximum(gi, 0)
            jd_, ji_ = J.jd[g, node], J.ji[g, node]
            if WAYS and J is self.way_field and getattr(J, "wjd", None) is not None and (self.way[ii] > 0).any():
                w_ = np.nonzero(self.way[ii] > 0)[0]         # (the jump ahead on his second or third way)
                jd_, ji_ = jd_.copy(), ji_.copy()
                jd_[w_], ji_[w_] = J.wjd[self.way[ii][w_] - 1, g[w_], node[w_]], J.wji[self.way[ii][w_] - 1, g[w_], node[w_]]
            out[ii, :JL.N_JUMP] = JL.inputs(self.jumps, jd_, np.where(gi >= 0, ji_, -1),
                                           np.linalg.norm(J.nodes[node] - pos[ii], axis=1))
        on = (self.weapon == GL) & (self.hp > 0) & (visible | (seen_t < GL_KNOWN))
        if on.any():
            to = known - np.array([0, 0, 20.0], np.float32) - eye       # (the floor at his feet, about)
            D = np.hypot(to[:, 0], to[:, 1]) + 1e-6
            v_, g_ = float(P_SPEED[GL]), 800.0
            disc = v_ ** 4 - g_ * (g_ * D * D + 2.0 * to[:, 2] * v_ * v_)
            reach = on & (disc >= 0.0)
            th = np.arctan2(v_ * v_ - np.sqrt(np.maximum(disc, 0.0)), g_ * D)   # the low arc; the game lofts a grenade by 0.2
            ey = np.degrees((np.arctan2(to[:, 1], to[:, 0]) - yaw + np.pi) % (2 * np.pi) - np.pi)
            ep = np.degrees(-(th - 0.2 * np.cos(th)) - pit)
            tf = D / np.maximum(v_ * np.cos(th), 1.0)
            out[:, JL.N_JUMP:JL.N_JUMP + 6] = np.stack([np.clip(ey / 30.0, -1, 1), np.clip(ey / 2.0, -1, 1), np.clip(ep / 15.0, -1, 1),
                                           np.clip(ep / 2.0, -1, 1), np.clip(tf / 1.5, 0, 2), np.ones(len(pos))], 1) * reach[:, None]
        if getattr(self, "_pm", None) is not None:           # the projectiles he sees beyond the nearest two, and what each is about to do
            out[:, JL.N_JUMP + 6:N_V15 - N_LEGS - N_EN] = self._pm
        if LEGS:                                             # his legs: the switch as it stands, and that they carried him on the last frame
            out[:, N_V15 - N_EN - 2], out[:, N_V15 - N_EN - 1] = self.legs, self.legs_on
        if FIGHT_TARGET:                                     # his intention is the enemy
            out[:, N_V15 - 1] = self.intent == EN_INTENT
        return out

    def _v02_init(self, bsp):
        """the memory and the map tables of the N_V02 inputs (see N_V02)"""
        n = self.n
        ng_ = self._others_arr().shape[1] + 1
        self.v02_left = None                                # a game server sets it: the share of the game's time left
        self.v02_loud = np.zeros(n, np.float32)             # how loud he has been (0 to 1; see V02_LOUD_T)
        self.v02_by = np.full(n, 99.0, np.float32)          # seconds since he made a noise with an enemy believed in earshot
        self.v02_bt = np.full((n, ng_), 99.0, np.float32)   # per other player (by his place in the group, as e_got): seconds since
        #   he last saw or heard him in this round and that player's life as he knows it (99: nothing believed)
        self.v02_ht = np.full((n, ng_), 99.0, np.float32)   # ... seconds since he last heard him,
        self.v02_hp = np.zeros((n, ng_, 3), np.float32)     # ... and about where
        self.v02_pk = np.zeros((n, ng_, 3), np.float32)     # ... his pickups heard or seen this life: mega, red, yellow or green armor
        self.v02_took = np.full((n, self.nI), 99.0, np.float32)     # per item: seconds since this player took it (99: not in this round)
        self.v02_tick = 0
        self.v02_q = []                                     # the last frames' sightings: they reach these inputs a reaction time late
        self.v02_slots = [(np.asarray(ids_, np.int64), 0) for ids_ in self.slot_items] + [(np.asarray(ids_, np.int64), r_) for ids_, r_ in self.xslots]
        R = self.route
        zs_ = R.nodes[~R.dead][:, 2] if R is not None else self.spots[:, 2] if self.spots is not None else np.zeros(0, np.float32)
        self.v02_zs = np.sort(np.asarray(zs_, np.float32))  # the heights of the map's standing places
        self.v02_ways = R.ways() if R is not None else None     # seconds of way between any two points (RouteField.ways)
        self.v02_big = [self.intent_gi[INTENTS.index(l_)] for l_ in ("MH", "RA")]      # the route goals of the mega and the red armor (-1: none)
        here_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_places")
        name = os.path.splitext(os.path.basename(bsp))[0].lower()
        self.v02_cell = None                                # the pros' numbers by cell: size, lowest cell, cells a side, cell -> row, rows
        f_ = os.path.join(here_, name + "_cells.json")
        if os.path.exists(f_):
            with open(f_, encoding="utf-8") as fh_:
                pc_ = json.load(fh_)
            cl_ = [c_ for c_ in (pc_.get("cells") or []) if c_.get("outcome_over_expected") is not None]
            if cl_:
                ci_ = np.array([c_["cell"] for c_ in cl_], np.int64).reshape(-1, 3)
                lo_ = ci_.min(0)
                dims_ = ci_.max(0) - lo_ + 1
                idx_ = np.zeros(tuple(int(x_) for x_ in dims_), np.int32)
                rows_ = np.zeros((len(cl_) + 1, 7), np.float32)
                top_ = math.log1p(max(float(c_.get("sightings", 0.0)) for c_ in cl_)) or 1.0
                for k_, c_ in enumerate(cl_):
                    ws_ = c_.get("weapon_shares") or {}
                    rows_[k_ + 1] = (min(1.0, max(-1.0, float(c_["outcome_over_expected"]) / 0.3)), math.log1p(float(c_.get("sightings", 0.0))) / top_,
                                     float(ws_.get("rockets", 0.0)) / 100.0, float(ws_.get("rail", 0.0)) / 100.0, float(ws_.get("lightning", 0.0)) / 100.0,
                                     min(1.0, float(c_.get("push_share", 0.0) or 0.0) / 50.0), 1.0)
                    idx_[tuple(int(x_) for x_ in ci_[k_] - lo_)] = k_ + 1
                self.v02_cell = (np.array(pc_["cell"], np.float32), lo_, dims_, idx_, rows_)
        self.v02_pp = np.zeros((0, 3), np.float32)          # the pros' places: where,
        self.v02_pf = np.zeros((0, 4), np.float32)          # ... the share of their blind shots, met, hit, how standing there fares
        f_ = os.path.join(here_, name + ".json")
        if os.path.exists(f_):
            with open(f_, encoding="utf-8") as fh_:
                pl_ = json.load(fh_).get("places") or []
            if pl_:
                self.v02_pp = np.array([p_["pos"] for p_ in pl_], np.float32).reshape(-1, 3)
                self.v02_pf = np.array([[min(1.0, float(p_.get("share", 0.0) or 0.0) / 15.0), min(1.0, float(p_.get("met_share", 0.0) or 0.0) / 100.0),
                                         min(1.0, float(p_.get("hit_share", 0.0) or 0.0) / 100.0),
                                         min(1.0, max(-1.0, float((p_.get("standing_there") or {}).get("outcome_over_expected", 0.0) or 0.0) / 0.3))]
                                        for p_ in pl_], np.float32)
        self.v02_see = np.zeros((n, len(self.v02_pp)), bool)    # per player and place: the line from his eyes was clear at the last look

    def _v02_others(self):
        """per other player of his group (the columns of _others_arr): seconds since seen or heard, noticed in view, his
        last known place"""
        s2_ = getattr(self, "seen2", None)
        if s2_ is None:
            return self.seen_t[:, None], self.acquired[:, None], self.known[:, None, :]
        return s2_, self.acq2, self.known2

    def _v02_round(self, done):
        """a new round for these players: nothing is believed, nothing was taken (N_V02)"""
        self.v02_bt[done], self.v02_ht[done], self.v02_pk[done], self.v02_took[done] = 99.0, 99.0, 0.0, 99.0
        self.v02_loud[done], self.v02_by[done], self.v02_see[done] = 0.0, 99.0, False
        for q_ in self.v02_q:                                # (the sightings of the round before, still on their way)
            q_[0][done] = False

    def _v02_void(self, j, v):
        """player j knows that player v died: where he believed him, and where he heard him, is void (N_V02)"""
        self.v02_bt[j, self._slot(v)] = self.v02_ht[j, self._slot(v)] = 99.0
        for q_ in self.v02_q:
            q_[0][j, (self._slot(v) - self._slot(j)) % (q_[0].shape[1] + 1) - 1] = False

    def note_noise(self, shot, hop, steps):
        """the noise each player made this frame, by the events hear() is called with: a shot with anything but the
        gauntlet, a jump or a landing, a frame of running steps (N_V02: how loud he has been; that he made a noise with
        an enemy believed in earshot). A game server's plugin calls it beside hear()."""
        up_ = self.hp > 0
        add_ = (np.asarray(steps, np.float32) + V02_LOUD_EVT * (np.asarray(shot, np.float32) + np.asarray(hop, np.float32))) * up_
        self.v02_loud = np.minimum(1.0, self.v02_loud + (DT / V02_LOUD_T) * add_).astype(np.float32)
        oth_ = self._others_arr()
        kn_ = self._v02_others()[2]
        near_ = ((self.v02_bt[np.arange(self.n)[:, None], self._slot(oth_)] < V02_BY_KNOWN)
                 & (np.linalg.norm(kn_ - self.state[:, None, :3], axis=2) < EAR_RANGE)).any(1)
        self.v02_by = np.where((np.asarray(shot, bool) | np.asarray(hop, bool) | np.asarray(steps, bool)) & near_ & up_, 0.0, self.v02_by).astype(np.float32)

    def note_take(self, i, it):
        """player i took item it: he knows when (N_V02: since he last took it); a mega, a red, a yellow or a green armor is
        counted by every other player who hears it (as the pickup sound: HEAR_EVT) or has him in view. A game server's
        plugin calls it at every pickup."""
        self.v02_took[i, it] = 0.0
        lab = self.item_def[it][4]
        k = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab in ("YA", "GA") else -1
        if k < 0 or int(self.kind[self._match_of(i)]) in (MOVE, SOLO):     # (alone on the map: nobody else is about)
            return
        s = self.state
        a2_ = getattr(self, "acq2", None)
        for j in self._mates(i):
            sees = bool(self.acquired[j]) if a2_ is None else bool(a2_[j, (self._slot(i) - self._slot(j)) % (a2_.shape[1] + 1) - 1])
            if sees or np.linalg.norm(s[j, :3] - s[i, :3]) < HEAR_EVT:
                self.v02_pk[j, self._slot(i), k] += 1.0

    def _v02_clear(self, a, b):
        """is the line a -> b clear, for many pairs, as the eye sees (the sight mask); b may lie V02_SEE_TOL deep in a wall"""
        dd = np.linalg.norm(b - a, axis=1)
        if self.new_lib:
            fr = self.w.lines(a, b) if self.sight is None else self.w.lines(a, b, mask=self.sight)
        else:
            u_ = ((b - a) / np.maximum(dd, 1e-6)[:, None]).astype(np.float32)
            fr = self.w.rays_each(a, u_[:, None, :], 4096.0)[:, 0] * 4096.0 / np.maximum(dd, 1e-6)
        return fr * dd >= dd - V02_SEE_TOL

    def _v02(self, pos, eye, rot, c, si, known, opp):
        """the inputs of N_V02 (see there). known: the enemy's last known place as the other inputs have it (as old as his
        reaction time, with his error of sight). Their clocks are kept here, so a game server's plugin, which does not
        call step(), has them too."""
        n = self.n
        ar = np.arange(n)
        ar2 = ar[:, None]
        out = np.zeros((n, N_V02), np.float32)
        oth = self._others_arr()
        sl = self._slot(oth)
        grp = ar // (oth.shape[1] + 1)
        seen2, acq2, kn2 = self._v02_others()
        # seen or heard (running within HEAR) on this frame: it reaches these inputs as late as it can reach the older ones
        # (his reaction time, and a frame more when his focus is used up), so that nothing here tells of an enemy sooner
        # (in a group: and they turn to another enemy as late after his attention has)
        self.v02_q.append((seen2 <= 0.0, np.array(acq2, bool), np.array(kn2, np.float32), np.array(self._slot(opp), np.int64)))
        while len(self.v02_q) > self.react_frames + FOCUS_LOSS + 1:
            self.v02_q.pop(0)
        fresh, acq2, kn2, so = self.v02_q[0]
        if self.react_seat is not None:                      # (SEAT_DELAYS) each seat as late as its own delay
            pk_ = np.maximum(0, len(self.v02_q) - 1 - (self.react_seat + FOCUS_LOSS))
            fresh, acq2, kn2, so = (np.stack([q_[j_] for q_ in self.v02_q])[pk_, ar] for j_ in range(4))
        if fresh.any():
            self.v02_bt[ar2, sl] = np.where(fresh, 0.0, self.v02_bt[ar2, sl])
            hi_, hk_ = np.nonzero(fresh & ~acq2)             # ... heard only (running within HEAR): the rough place
            if len(hi_):
                self.v02_ht[hi_, sl[hi_, hk_]] = 0.0
                self.v02_hp[hi_, sl[hi_, hk_]] = kn2[hi_, hk_]
        bt = self.v02_bt[ar, so]
        bel_ok = bt < V02_KNOWN
        bel = (known + self.last_vel * np.minimum(bt, 1.0)[:, None]).astype(np.float32)     # (the extrapolation of the pre-fire rule)
        self.v02_bel, self.v02_bel_ok = bel, bel_ok          # (LEGS_LOOK: where his legs look; kept, changes nothing)
        # ---- the game
        if self.v02_left is not None:
            left = np.broadcast_to(np.asarray(self.v02_left, np.float32), (n,))
        else:
            if self.lab is not None:
                len_ = self.lab_len
            else:
                len_ = np.where(self.kind == NORMAL, self.round_len, np.where(self.kind == MOVE, self.move_len, 15.0))
                if self.fixed_kind is not None:
                    len_ = np.full(len(self.kind), self.round_len)
                len_ = len_ * self.round_fac
                if GAME_ON:                                  # (a whole game or a late round: the share of the game left)
                    len_ = np.where(self.game > 0, GAME_LEN, len_)
            left = np.clip(1.0 - self.round_t / np.maximum(len_, 1e-3), 0.0, 1.0)[grp]
        out[:, 0] = left
        out[:, 1] = self.v02_loud
        out[:, 2] = self.v02_by < 1.0
        # ---- his position
        o = V02_GAME
        out[:, o] = np.clip((pos[:, 2] - bel[:, 2]) / 300.0, -1.0, 1.0) * bel_ok
        if len(self.v02_zs):
            out[:, o + 1] = np.searchsorted(self.v02_zs, pos[:, 2] + 1.0) / float(len(self.v02_zs))
        else:
            out[:, o + 1] = np.clip((pos[:, 2] - self.lo[2]) / max(1.0, float(self.hi[2] - self.lo[2])), 0.0, 1.0)
        if self.v02_cell is not None:
            size_, lo_, dims_, idx_, rows_ = self.v02_cell
            ci = np.floor(pos / size_).astype(np.int64) - lo_
            ok = ((ci >= 0) & (ci < dims_)).all(1)
            ci = np.clip(ci, 0, dims_ - 1)
            out[:, o + 2:o + 9] = rows_[np.where(ok, idx_[ci[:, 0], ci[:, 1], ci[:, 2]], 0)]
        # ---- the enemy as he believes him
        o = V02_GAME + V02_POS
        ht = self.v02_ht[ar, so]
        out[:, o] = bel_ok
        out[:, o + 1:o + 4] = np.clip(rot(bel - pos) / 1500.0, -2.0, 2.0) * bel_ok[:, None]
        out[:, o + 4] = np.minimum(ht, 20.0) / 20.0
        out[:, o + 5:o + 8] = np.clip(rot(self.v02_hp[ar, so] - pos) / 1500.0, -2.0, 2.0) * (ht < 90.0)[:, None]
        out[:, o + 8] = np.where(bel_ok, np.minimum(bt * 400.0, 3000.0) / 3000.0, 1.0)
        way = np.ones((n, 3), np.float32)
        R = self.route
        if R is not None:
            nb = R.locate(bel)
            if self.v02_ways is not None:
                na = R.locate(pos)
                v_ = self.v02_ways[nb, na]
                t_ = v_ / 16.0 + np.linalg.norm(R.nodes[na] - pos, axis=1) / 320.0
                way[:, 0] = np.where(bel_ok & (v_ < 255), np.minimum(t_, V02_WAY_MAX) / V02_WAY_MAX, 1.0)
            for j_, g_ in enumerate(self.v02_big):
                if g_ >= 0:
                    t_ = R.T[g_, nb]
                    way[:, 1 + j_] = np.where(bel_ok & (t_ < 1e8), np.minimum(t_, V02_WAY_MAX) / V02_WAY_MAX, 1.0)
        out[:, o + 9:o + 12] = way
        dm_ = getattr(self, "dmg_on", None)                  # (a group of more than two: the damage dealt to that player)
        out[:, o + 12] = np.minimum((self.dmg_life if dm_ is None or dm_.shape[1] == 2 else dm_[ar, so]) / 200.0, 2.0)
        el = self.e_life[ar, so]
        out[:, o + 13] = np.minimum(np.minimum(el, self.round_t[grp]), 60.0) / 60.0
        out[:, o + 14] = el < 90.0
        out[:, o + 15:o + 18] = np.minimum(self.v02_pk[ar, so], 2.0) / 2.0
        out[:, o + 18:o + 21] = self.e_got[ar, so][:, [2 + RL, 2 + RG, 2 + LG]]
        # ---- the items: since he last took the one of each slot
        o = V02_GAME + V02_POS + V02_BEL
        out[:, o:o + V02_ITEMS] = 1.0
        if self.nI:
            d_it = np.linalg.norm(self.item_pos[None, :, :] - pos[:, None, :], axis=2)
            for j_, (ids_, rank_) in enumerate(self.v02_slots):
                if len(ids_) > rank_:
                    dj_ = d_it[:, ids_]
                    near_ = dj_.argmin(1) if rank_ == 0 else np.argsort(dj_, axis=1)[:, rank_]
                    out[:, o + j_] = np.minimum(self.v02_took[ar, ids_[near_]], 40.0) / 40.0
        # ---- the places
        o = V02_GAME + V02_POS + V02_BEL + V02_ITEMS
        P = len(self.v02_pp)
        if P:
            S = min(V02_SLOTS, P)
            d_pl = np.linalg.norm(self.v02_pp[None, :, :] - pos[:, None, :], axis=2)
            order = np.argsort(d_pl, axis=1)[:, :S]
            self.v02_tick += 1
            sel = np.nonzero((self.v02_tick + ar) % V02_SEE_EVERY == 0)[0]      # the look: every V02_SEE_EVERY frames a player
            if len(sel):
                pi_ = order[sel]
                ends_ = (self.v02_pp[pi_].reshape(-1, 3) + np.array([0, 0, V02_SEE_LIFT], np.float32)).astype(np.float32)
                self.v02_see[sel[:, None], pi_] = self._v02_clear(np.repeat(eye[sel], S, axis=0).astype(np.float32), ends_).reshape(len(sel), S)
            pp_ = self.v02_pp[order]                         # (players, slots, 3)
            rel = pp_ - pos[:, None, :]
            see = self.v02_see[ar2, order]
            blk = np.zeros((n, V02_SLOTS, V02_PF), np.float32)
            blk[:, :S, 0] = (c[:, None] * rel[:, :, 0] + si[:, None] * rel[:, :, 1]) / 1500.0
            blk[:, :S, 1] = (-si[:, None] * rel[:, :, 0] + c[:, None] * rel[:, :, 1]) / 1500.0
            blk[:, :S, 2] = rel[:, :, 2] / 1500.0
            blk[:, :S, :3] = np.clip(blk[:, :S, :3], -2.0, 2.0)
            blk[:, :S, 3] = np.minimum(d_pl[ar2, order] / 2000.0, 1.5)
            blk[:, :S, 4] = see
            blk[:, :S, 5] = np.where(bel_ok[:, None], np.minimum(np.linalg.norm(pp_ - bel[:, None, :], axis=2) / 1500.0, 1.0), 1.0)
            blk[:, :S, 6:10] = self.v02_pf[order]
            nearest_ = np.linalg.norm(self.v02_pp[None, :, :] - bel[:, None, :], axis=2).argmin(1)
            blk[:, :S, 10] = (order == nearest_[:, None]) & bel_ok[:, None]
            blk[:, :S, 11] = 1.0
            out[:, o:] = blk.reshape(n, -1)
            out[:, V02_GAME + 9] = see.sum(1) / float(V02_SLOTS)
        # ---- their clocks
        self.v02_bt = np.minimum(self.v02_bt + DT, 99.0).astype(np.float32)
        self.v02_ht = np.minimum(self.v02_ht + DT, 99.0).astype(np.float32)
        self.v02_took = np.minimum(self.v02_took + DT, 99.0).astype(np.float32)
        self.v02_by = np.minimum(self.v02_by + DT, 99.0).astype(np.float32)
        self.v02_loud = (self.v02_loud * (1.0 - DT / V02_LOUD_T)).astype(np.float32)
        return out

    def _hold_at(self, ii, k):
        """for players ii with the intentions k: his intention is a holding place and he stands at it (TARGETS)"""
        j = np.asarray(k) - HOLD_INTENT
        if not self.hold_n:
            return np.zeros(len(j), bool)
        d = self.state[ii, :3] - self.hold_pos[np.clip(j, 0, self.hold_n - 1)]
        return (j >= 0) & (j < self.hold_n) & (np.hypot(d[:, 0], d[:, 1]) < HOLD_R) & (np.abs(d[:, 2]) < HOLD_Z)

    def note_holds(self):
        """TARGETS: who stands at the holding place that is his intention: it is reached (he may choose anew at every
        reading; it stays his target while he chooses it). step() calls it; a game server's plugin must, every frame.
        Returns who stands at his place, and who reached it on this frame."""
        at = self._hold_at(np.arange(self.n), self.intent)
        new = at & ~self.intent_done
        self.intent_done = self.intent_done | at
        return at, new

    def _b2(self, pos, c, si):
        """the inputs of N_B2 (see there): the map's holding places, slot by slot"""
        n = len(pos)
        H = len(self.hold_pos)
        blk = np.zeros((n, HOLD_SLOTS, B2_F), np.float32)
        if not H:
            return blk.reshape(n, -1)
        rel = self.hold_pos[None, :, :] - pos[:, None, :]
        blk[:, :H, 0] = (c[:, None] * rel[:, :, 0] + si[:, None] * rel[:, :, 1]) / 1500.0
        blk[:, :H, 1] = (-si[:, None] * rel[:, :, 0] + c[:, None] * rel[:, :, 1]) / 1500.0
        blk[:, :H, 2] = rel[:, :, 2] / 1500.0
        blk[:, :H, :3] = np.clip(blk[:, :H, :3], -2.0, 2.0)
        blk[:, :H, 3] = 1.0
        R = self.route
        if R is not None and self.v02_ways is not None and len(self.hold_node) == H:
            na = R.locate(pos)
            v_ = self.v02_ways[self.hold_node[None, :], na[:, None]]     # (the way from his point to the place's, sixteenths of a second)
            t_ = v_ / 16.0 + (np.linalg.norm(R.nodes[na] - pos, axis=1) / 320.0)[:, None]
            blk[:, :H, 3] = np.where(v_ < 255, np.minimum(t_, V02_WAY_MAX) / V02_WAY_MAX, 1.0)
        blk[:, :H, 4:6] = self.hold_feat[None, :, :]
        if self.hold_n:
            blk[:, :H, 6] = (self.intent[:n, None] - HOLD_INTENT) == np.arange(H)[None, :]
        blk[:, :H, 7] = 1.0
        return blk.reshape(n, -1)

    def _b3(self, pos):
        """the inputs of N_B3 (see WAYS): his way now; for his target, how much longer the second and the third way are
        than the shortest from where he stands, and whether each differs from it from here. After _intent() (it leaves
        the target's row, his point and the shortest's seconds)."""
        n = len(pos)
        out = np.zeros((n, N_B3), np.float32)
        if not WAYS:
            return out
        out[np.arange(n), np.where(self.run_k[:n] >= 0, 0, self.way[:n])] = 1.0
        X, st = self.way_field, getattr(self, "_way_obs", None)
        if X is not None and st is not None:
            g, node, ok, t = st
            for k in range(N_WAYS - 1):
                out[:, N_WAYS + k] = np.clip((X.wT[k, g, node] - t) / B3_LONGER, 0.0, 1.0) * ok
                out[:, 2 * N_WAYS - 1 + k] = X.wdiff[k, g, node] * ok
        return out

    def _way_trip(self, i, b):
        """WAY_MEASURE: player i took the route goal b. With the one he took before it in this life that is a trip between
        two places: its path, 16 points along it, is kept (way_trips) for the measure of how predictable his ways are.
        His seats only (count_even), in games, not a scripted player."""
        a, k = int(self.wt_from[i]), int(self.wt_n[i])
        p = self.state[i, :3]
        if a >= 0 and a != b and k >= 1 and WT_MIN_S <= float(self.wt_t[i]) <= WT_MAX_S and self.script[i] == 0 and self.run_k[i] < 0 \
                and bool(self._counted(i)):
            import ways as WY_
            self.way_trips.append([a, int(b)] + [int(round(float(x_))) for x_ in WY_.resample(np.concatenate([self.wt_pts[i, :k], p[None]])).ravel()])
            self.stats["way_trips_n"] += 1
        self.wt_from[i], self.wt_n[i], self.wt_t[i] = b, 1, 0.0
        self.wt_pts[i, 0] = p

    def _v14(self, vel, yaw, pit, eye, known, opp_vel, visible, opp):
        """the inputs of N_V14: his own movement read out for strafe jumping (4), and where a rocket or a plasma ball fired
        now would meet the enemy he sees (6)"""
        sp = np.hypot(vel[:, 0], vel[:, 1])
        moving = sp > 50.0
        dv = np.arctan2(vel[:, 1], vel[:, 0]) - yaw
        own = np.stack([np.clip(sp / 400.0, 0, 3), np.sin(dv) * moving, np.cos(dv) * moving,
                        np.clip((sp - self.sp_hist[:, 3]) / 100.0, -1, 1)], 1)
        cs = LEAD_SPEED[self.weapon]
        on = visible & (cs > 0) & (self.hp > 0)
        c_ = np.maximum(cs, 1.0)
        r0 = known + np.array([0, 0, 4.0], np.float32) - eye
        air = self.state[opp, 6] < 0.5
        t = np.linalg.norm(r0, axis=1) / c_
        for _ in range(3):                                   # the flight time and the enemy's place by then, each from the other
            t = np.minimum(t, 3.0)
            dz = np.where(air, opp_vel[:, 2] * t - 400.0 * t * t, 0.0)
            m = r0 + np.stack([opp_vel[:, 0] * t, opp_vel[:, 1] * t, dz], 1)
            t = np.linalg.norm(m, axis=1) / c_
        t = np.minimum(t, 3.0)
        meet = eye + m
        top = np.maximum(meet[:, 2], known[:, 2]) + 16.0     # the floor under the meeting point: he does not fall through it
        st = np.stack([meet[:, 0], meet[:, 1], top], 1).astype(np.float32)
        fr = self.w.rays(st, np.array([[0, 0, -1.0]], np.float32), 1024.0, mask=self.sight)[:, 0]
        floor = top - fr * 1024.0
        meet[:, 2] = np.where(fr < 1.0, np.maximum(meet[:, 2], floor + 28.0), meet[:, 2])
        to = meet - eye
        hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        ey = np.degrees((np.arctan2(to[:, 1], to[:, 0]) - yaw + np.pi) % (2 * np.pi) - np.pi)
        ep = np.degrees(-np.arctan2(to[:, 2], hd) - pit)
        ef = np.degrees(-np.arctan2(floor + 2.0 - eye[:, 2], hd) - pit)
        lead = np.stack([np.clip(ey / 30.0, -1, 1), np.clip(ey / 2.0, -1, 1), np.clip(ep / 15.0, -1, 1), np.clip(ep / 2.0, -1, 1),
                         np.clip(t / 1.5, 0, 2), np.where(fr < 1.0, np.clip((ef - ep) / 15.0, 0, 1), 1.0)], 1) * on[:, None]
        return np.concatenate([own, lead], 1).astype(np.float32)

    def _extra(self, pos, vel, eye, fdir, up, rot, c, si, yaw, pit, visible):
        """the inputs added after duel_gru_v3 (see N_EXTRA)"""
        n = self.n
        ar = np.arange(n)
        opp = ar ^ 1
        # clock (item timers are 25 s and 35 s) and score of the round
        t = np.repeat(self.round_t, 2)
        clock = np.stack([np.minimum(t / 120.0, 2.0), np.sin(2 * np.pi * t / 25.0), np.cos(2 * np.pi * t / 25.0),
                          np.sin(2 * np.pi * t / 35.0), np.cos(2 * np.pi * t / 35.0), np.minimum(self.frags_r / 10.0, 2.0),
                          np.minimum(self.frags_r[opp] / 10.0, 2.0),
                          np.clip((self.frags_r - self.frags_r[opp]) / 5.0, -2, 2)], 1)
        if GAME_ON and self.game.any():                      # a whole game or a late round: the clock is the share of the game played
            gm_ = self.game[ar // (self._others_arr().shape[1] + 1)] > 0     # (seconds / 120 held at 2 would stand still from 4:00 on)
            clock[:, 0] = np.where(gm_, t / GAME_LEN, clock[:, 0])
        xitems = np.concatenate([self._item_block(ids, r, pos, eye, fdir, up, rot) for ids, r in self.xslots], 1)
        # sounds: how long ago and roughly where, per category; which pickup it was
        fresh = self.snd_t < 5.0
        rel = np.stack([rot(self.snd_pos[:, j] - pos) / 1000.0 for j in range(4)], 1) * fresh[:, :, None]
        snd = np.concatenate([np.exp(-self.snd_t), rel.reshape(n, 12),
                              np.eye(4, dtype=np.float32)[self.snd_kind] * fresh[:, :1]], 1)
        # where on the map, and which map
        where = (pos - self.lo) / np.maximum(self.hi - self.lo, 1.0) * 2.0 - 1.0
        # sight: a coarse picture along the view, what is above, and long horizontal distances
        zf = np.where(self.zoom, ZOOM, 1.0)[:, None]                 # zoomed: the picture covers a smaller angle
        gy, gp = yaw[:, None] + self.view_grid[None, :, 0] * zf, pit[:, None] + self.view_grid[None, :, 1] * zf
        vd = np.stack([np.cos(gp) * np.cos(gy), np.cos(gp) * np.sin(gy), -np.sin(gp)], 2).astype(np.float32)
        view = self.w.rays_each(eye, vd, 2000.0, mask=self.sight)   # what he sees where he looks (a clip brush is not drawn)
        ud = self.up_dirs
        udw = np.stack([c[:, None] * ud[None, :, 0] - si[:, None] * ud[None, :, 1],
                        si[:, None] * ud[None, :, 0] + c[:, None] * ud[None, :, 1],
                        np.repeat(ud[None, :, 2], n, 0)], 2).astype(np.float32)
        above = self.w.rays_each(eye, udw, 512.0)
        if self.fov_sight:
            az = np.where(np.hypot(ud[:, 0], ud[:, 1]) > 1e-3, np.arctan2(ud[:, 1], ud[:, 0]), 0.0)
            el = np.arcsin(np.clip(ud[:, 2], -1, 1))
            fh, fv, _ = self.fov()
            see = (np.abs(az)[None, :] <= fh[:, None]) & (np.abs(el[None, :] + pit[:, None]) <= fv[:, None])
            above = np.where(see, above, UNSEEN).astype(np.float32)
        ld = self.long_dirs
        ldw = np.stack([c[:, None] * ld[None, :, 0] - si[:, None] * ld[None, :, 1],
                        si[:, None] * ld[None, :, 0] + c[:, None] * ld[None, :, 1],
                        np.zeros((n, N_LONG), np.float32)], 2).astype(np.float32)
        far = self.w.rays_each(pos, ldw, 2000.0)
        if self.fov_sight:
            la_ = np.arctan2(ld[:, 1], ld[:, 0])
            see = (np.abs(la_)[None, :] <= fh[:, None]) & (np.abs(pit)[:, None] <= fv[:, None])
            far = np.where(see, far, UNSEEN).astype(np.float32)
        # the enemy while in view: weapon in hand, whether he faces this player, damage dealt to him this life
        v_ = visible.astype(np.float32)[:, None]
        oy = np.radians(self.yaw[opp])
        back = np.arctan2(pos[:, 1] - self.state[opp, 1], pos[:, 0] - self.state[opp, 0]) - oy
        enemy = np.concatenate([np.eye(NW, dtype=np.float32)[self.weapon[opp]][:, OBS_W] * v_,
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
        self._book(st, i, v, dmg, wpn)
        st["kicked"] = True
        self.stats["dmg"] += dmg

    def _book(self, st, i, v, dmg, wpn):
        """player i did dmg to player v: booked per attacker (until 2026-10-08 a victim had one attacker per frame, the
        last to hit, who was paid for everything the victim took in it and for the frag); the frag is his whose hit
        took the health below zero"""
        k_ = (int(i), int(v))
        st["by"][k_] = st["by"].get(k_, 0.0) + float(dmg)
        if st["killer"][v] < 0:
            st["kill_w"][v] = wpn
            if self.hp[v] <= 0:
                st["killer"][v] = i

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
            if d < R and (self.w.trace(ep, c, mask=self.sight)["fraction"] >= 0.999
                          or (GL_QL and any(self.w.trace(ep, c + np.array([ox_, oy_, 0.0], np.float32), mask=self.sight)["fraction"] >= 0.999
                                            for ox_, oy_ in ((15.0, 15.0), (15.0, -15.0), (-15.0, 15.0), (-15.0, -15.0))))):
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
                self._book(st, i, v, take, wpn)
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
                if self.hp[v] <= 0 and st["killer"][v] < 0:
                    st["killer"][v] = v

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
            nm_ = ch[self.sc_persona[ch] == NIGHTMARE]
            if len(nm_):
                self.sc_wpn[nm_] = rng.choice(NM_WEAPONS, len(nm_), p=NM_WEIGHTS / NM_WEIGHTS.sum())
            self.sc_dir[ch] = rng.choice([-1, -1, 1, 1, 0], len(ch))
            self.sc_fwd[ch] = rng.choice([-1, 0, 0, 1], len(ch))
            self.sc_jump[ch] = (rng.random(len(ch)) < 0.2) & (self.sc_persona[ch] != NIGHTMARE)
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
        runner = self.script[idx] == 3                      # the item runner aims, fires and picks weapons as the fighter does
        fighter = fighter | runner
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
        chase = fighter & ((self.seen_t[idx] < 2.0) | self.sc_look[idx])
        turn = np.where(vis | chase, np.clip(ey * P_GAIN[per], -10, 10), np.clip(wander * 0.15, -6, 6))
        turn = np.where(fighter, turn + rng.normal(0, 1.0, k) * P_NOISE[per], np.clip(wander * 0.1, -3, 3))
        if self.sc_style:
            turn = np.where(fighter, turn, 0.0)             # test-room targets keep their facing (straight strafes)
        dpit = np.where(vis | self.sc_look[idx], np.clip(ep * 0.4, -6, 6), -self.pitch[idx] * 0.2)
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
        nmw = self.sc_wpn[idx]                               # the stand-in: its drawn weapon if he has it, the rail far off
        nmw = np.where((dist > 700) & self.has[idx, RG] & (am[:, RG] > 0), RG, nmw)
        want = np.where((fixed == -3) & self.has[np.arange(k) * 0 + idx, nmw] & (am[np.arange(k), nmw] > 0), nmw, want)
        if TRICKS:                                           # the lobber fights with what it throws: plasma on an enemy in view from
            want = np.where((self.script[idx] == 3) & (per == LOBBER) & (dist > LOB_PG_NEAR) & (dist < LOB_PG_FAR)   # 150 to 1,000 units
                            & (am[:, PG] > 0), PG, want)     # (2026-10-10: its grenades and plasma made 0 to 25% of its frags; he has to meet them)
        cur = self.weapon[idx]
        out[:, 6] = np.where(fighter & (want != cur) & self.has[idx, want], want + 1, 0)
        tol = np.where((cur == RL) | (cur == SG), 6.0, 2.5)
        out[:, 5] = (vis & (np.abs(ey) < tol) & (np.abs(ep) < 4.0)) | (fighter & (per == 7))   # the spammer always fires
        if runner.any() and self.route is not None:
            self._runner_keys(idx, runner, out, vis | chase)
            if TRICKS:
                self._lob(idx, out, vis)
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

    def _match_of(self, i):
        return int(i) // (self._others_arr().shape[1] + 1)

    def _weapon_teach(self):
        """the fifth teacher label: the weapon key a plain player would press (see W_RULE_RL)"""
        who = (self.script == 0) & (self.hp > 0) & (self.seen_t < 1.5) & (self.run_k < 0)
        k_ = self.kind[np.arange(self.n) // (self._others_arr().shape[1] + 1)]
        who &= (k_ == NORMAL) | ((k_ == DRILL) & self.drill_mix[np.arange(self.n) // (self._others_arr().shape[1] + 1)])
        ii = np.nonzero(who)[0]
        if not len(ii):
            return
        d = np.linalg.norm(self.known[ii] - self.state[ii, :3], axis=1)
        ok = self.has[ii] & (self.ammo[ii] > 0)
        want = np.full(len(ii), MG, np.int64)
        want = np.where(ok[:, LG] & (d < W_RULE_LG), LG, want)
        want = np.where(ok[:, RG] & (d > W_RULE_RG), RG, want)
        hold = self.weapon[ii]                               # the overlap: either of the two is fine where both reach
        fine = ((want == RG) & (hold == LG) & ok[:, LG] & (d < W_RULE_LG)) | ((want == LG) & (hold == RG) & ok[:, RG] & (d > W_RULE_RG_OK))
        want = np.where(fine, hold, want)
        want = np.where(ok[:, RL] & (d > W_RULE_RL[0]) & (d < W_RULE_RL[1]), RL, want)
        if self.w_table is not None:                         # the pros' table in place of the distances above
            big_ = np.array([RL, RG, LG])
            pr = np.where(ok[:, big_], self.w_table[np.clip((d / 100.0).astype(np.int64), 0, len(self.w_table) - 1)], -1.0)
            best = pr.argmax(1)
            want = np.where(pr.max(1) >= 0, big_[best], MG)
            mine = (hold[:, None] == big_[None, :])
            p_mine = np.where(mine.any(1), (pr * mine).sum(1), -1.0)
            want = np.where((p_mine >= 0) & (p_mine >= pr.max(1) - PRO_WEAPON_TIE), hold, want)
        sw = STYLE_W[self.style[ii]]                         # his preferred weapon whenever he has it, at any distance
        want = np.where((sw >= 0) & ok[np.arange(len(ii)), np.maximum(sw, 0)], sw, want)
        want = np.where(ok[np.arange(len(ii)), want], want, self.weapon[ii])      # (no machine-gun ammo: keep what he holds)
        cur = self.weapon[ii]
        lab_ = np.where(want == cur, 0, want + 1)
        if TEACH_FREE:                                       # his own choice with the shotgun, grenades or plasma (see TEACH_FREE)
            lab_ = np.where(np.isin(cur, (SG, GL, PG)) | ((want == MG) & ok[:, [SG, GL, PG]].any(1)), -1, lab_)
        self.teach[ii, 4] = lab_
        self.stats["wrule_frames"] += len(ii)
        self.stats["wrule_agree"] += int((want == cur).sum())

    def _hand_step(self, done, died):
        """the weapon in his hand with nobody in view (see HAND_TEACH): what is kept for it and its counters, every frame
        and whatever the switch; with the switch the target of his next reading of the weapon key (self.hand_lab). Called at
        the end of step(), after the senses. Draws no random number and changes nothing the game reads."""
        n = self.n
        ar = np.arange(n)
        s, w = self.state, self.weapon
        new, died = np.asarray(done, bool), np.asarray(died, bool)
        v2_ = getattr(self, "vis2", None)                    # in view: any other member of his group
        inview = np.asarray(self.visible, bool) if v2_ is None else v2_.any(1)
        fr0 = np.where(new, 0, self.hand_fr)
        came = inview & (fr0 >= HAND_OUT_F)                  # an enemy comes into view after 1 s or more out of it
        fr = np.where(inview, 0, np.minimum(fr0 + 1, 1 << 30))
        ever = (self.hand_ever & ~new) | inview
        # a hold, as tools/pro_yardsticks.py's: within HAND_HOLD_R of where the stretch began, nobody in view, a big weapon in hand
        okh = (self.hp > 0) & ~inview & ((w == RL) | (w == RG) | (w == LG))
        anew = ~okh | new | died | (np.linalg.norm(s[:, :3] - self.hand_p0, axis=1) > HAND_HOLD_R)
        self.hand_p0 = np.where(anew[:, None], s[:, :3], self.hand_p0).astype(np.float32)
        self.hand_a0 = np.where(anew, okh, self.hand_a0)
        hf = np.where(anew, 0, self.hand_hf + 1)
        holding = okh & (hf >= HAND_HOLD_F)
        state = np.where(holding, 1, np.where(np.hypot(s[:, 3], s[:, 4]) >= HAND_TRAVEL, 0, 2))
        band = np.where(~ever, 3, np.where(fr < HAND_BAND_F[0], 0, np.where(fr < HAND_BAND_F[1], 1, 2)))
        grp = ar // (self._others_arr().shape[1] + 1)
        game = ((self.script == 0) & (self.hp > 0) & (self.kind[grp] == NORMAL) & (self.mode[grp] < 0) & (self.run_k < 0)
                & ~self.jrun & (self.lab is None))           # a network's seat, alive, in a game on a duel map
        quiet = game & ~inview & (fr >= HAND_OUT_F)
        cnt = self._counted(ar)
        st_ = self.stats
        q = quiet & cnt
        # qhand: a frame waits HAND_HOLD_F frames before it is counted; a stretch that becomes a hold meanwhile was one from its first frame
        bp = self.hand_bp
        old = self.hand_buf[bp]
        st_["qhand"] += np.bincount(old[old >= 0], minlength=3 * 4 * NW).reshape(3, 4, NW)
        self.hand_buf[bp] = np.where(q, (state * 4 + band) * NW + w, -1)
        self.hand_bp = bp = (bp + 1) % (HAND_HOLD_F + 1)     # (now the oldest frame kept: HAND_HOLD_F frames ago)
        c = np.nonzero(okh & (hf == HAND_HOLD_F))[0]         # a hold is known now
        if len(c):
            B = self.hand_buf[:, c]
            H = np.where(B >= 0, B % (4 * NW) + 4 * NW, B)   # the same band and weapon, the state "holding"
            H[bp] = np.where(self.hand_a0[c], H[bp], B[bp])  # (the stretch's first frame only if he could hold on it)
            self.hand_buf[:, c] = H
        st_["qhand_meet"] += np.bincount(w[came & game & cnt], minlength=NW)
        st_["qhand_sw"] += np.array([int((q & (w != self.hand_wp) & (self.hand_wp >= 0) & ~died & ~new).sum()), int(q.sum())], np.float64)
        lab = np.zeros((n, 1 + NW), np.float32)
        if self.hand_tab is not None:
            row = holding.astype(np.int64)                   # the lesson's row: a hold's, else the travelling row
            pi = np.where(self.has & (self.ammo > 0), self.hand_tab[row, band], 0.0).astype(np.float64)   # the pros' shares of what he owns
            elig = quiet & ever & ((pi > 0).sum(1) >= 2)
            pi = pi / np.maximum(pi.sum(1), 1e-12)[:, None]
            e = np.nonzero(elig & cnt)[0]
            if len(e):
                st_["qhand_on"] += np.bincount((row[e] * 4 + band[e]) * NW + w[e], minlength=2 * 4 * NW).reshape(2, 4, NW)
                np.add.at(st_["qhand_pro"], (row[e], band[e]), pi[e])
            if HAND_TEACH:
                give = elig & ((self.style == 0) | (not HAND_TEACH_GENERAL))
                lab[:, 1:] = HAND_LAM * pi                   # a fresh draw from the shares: choice w + 1 for weapon w ...
                lab[:, 0] = 1.0 - HAND_LAM + HAND_LAM * pi[ar, w]    # ... the weapon in his hand: "keep", as _weapon_teach's label 0
                lab[ar, w + 1] = 0.0
                lab[~give] = 0.0
        self.hand_lab = lab
        self.hand_fr, self.hand_ever, self.hand_hf, self.hand_wp = fr, ever, hf, w.copy()
        self.hand_state, self.hand_band, self.hand_quiet = state, band, quiet

    def _blind_rockets(self, ii, s, reward):
        """rockets fired with no enemy in view (see BLIND_RULE): free as a rocket jump, near where he thinks the enemy is,
        or on a way the enemy is likely to take from there; any other costs BLIND_RL_DMG points of damage"""
        yr, pr = np.radians(self.yaw[ii]), np.radians(self.pitch[ii])
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1).astype(np.float32)
        eye = self._eye(s)[ii]
        R = self.route
        for k, i in enumerate(ii):
            L = np.asarray(self.w.trace(eye[k], eye[k] + fdir[k] * 4000.0, mask=self.sight)["endpos"], np.float32)
            B = self.known[i] + self.last_vel[i] * min(float(self.seen_t[i]), 1.0)
            how = 0
            if np.linalg.norm(L - s[i, :3]) < BLIND_JUMP:
                how = 1
            elif np.linalg.norm(L - B) < BLIND_NEAR:
                how = 2
            elif len(self.spam_places) and float(np.linalg.norm(self.spam_places - L, axis=1).min()) < BLIND_PLACES:
                how = 4                                      # (a place the pros fire at with nobody in view)
            elif R is not None:
                nb, nl, me = (int(x) for x in R.locate(np.stack([B, L, s[i, :3]]).astype(np.float32)))
                if np.linalg.norm(R.nodes[nl] - L) < BLIND_WAY_R:
                    tb = R.from_node(nb)
                    by = float(self.seen_t[i]) + float(np.linalg.norm(L - eye[k])) / P_SPEED[RL] + BLIND_SLACK
                    if tb[nl] <= by and (tb[nl] + R.from_node(nl)[me] <= tb[me] + BLIND_SLACK
                                         or bool((tb[nl] + R.T[:len(self.route_goal), nl] <= R.T[:len(self.route_goal), nb] + BLIND_SLACK).any())):
                        how = 3
            self.stats["blind_rl"] += 1
            self.stats["blind_rl_how"][how] += 1
            if not how:
                reward[i] -= BLIND_RL_DMG * self.dmg_reward

    def _collect_to_fight(self, m):
        """the item run of match m becomes a fight (RUN_COLLECT): half of the seats back to a plain spawn"""
        q = self._seats(m)
        plain = self.rng.permutation(q)[:int(len(q) * 0.5)]
        for i in plain:                                     # (still an item run here: the game's spawn, no stack, a spawn point)
            self.state = self.w.state()
            self._spawn(int(i), avoid=None)
        self.state = self.w.state()
        self.cf_t[m] = -1.0
        self.cf_side[q] = 1
        self.cf_side[plain] = 2
        self.kind[m] = NORMAL
        self.run_k[q] = -1
        if self.lab is not None:
            self.arena[m] = 3                               # the yard: deaths come back inside it
        self.intent_new[q], self.intent_done[q] = True, True
        self.stats["cf_rounds"] += 1

    # ---------------------------------------------------------------- whole games and late rounds (GAME_P, LATE_P, WIN_PAY)
    def _game_init(self):
        """the books of whole games and late rounds (see GAME_P): per match what it is (0 nothing, 1 a whole game, 2 a late
        round), the game's clock in frames and the first seat's chance of winning as last paid; per player what WIN_PAY
        has paid him in this game and what the flat pay for his frags and deaths would have"""
        self.game = np.zeros(self.M, np.int64)
        self.g_tick = np.zeros(self.M, np.int64)
        self.g_p = np.full(self.M, 0.5, np.float64)
        self.g_win = np.zeros(self.n, np.float64)
        self.g_flat = np.zeros(self.n, np.float64)
        self.win_pay = np.zeros(self.n, np.float32)         # this frame's pay by the game, per player (info["win_pay"])
        self._late_m = []                                   # late rounds begun in this step: drawn after the round's reset
        self.win_tab, self.win_scale = None, 0.0
        if GAME_ON:
            self.stats["games"] = np.zeros(len(GAMES_COLS))
        if GAME_ON and WIN_PAY:
            f_ = os.environ.get("WIN_CHANCE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "win_chance.json")
            with open(f_, encoding="utf-8") as fh_:
                wc_ = json.load(fh_)
            p_ = np.array(wc_["p"], np.float64)             # [time left][lead]
            left_, d_ = np.array(wc_["left_s"], np.float64), np.array(wc_["diffs"], np.int64)
            D_ = int(d_[-1])
            assert p_.shape == (len(left_), len(d_)) and np.array_equal(d_, np.arange(-D_, D_ + 1)), "win_chance.json: the table's shape"
            assert left_[0] == 0.0 and np.allclose(np.diff(left_), left_[1]) and abs(left_[-1] - GAME_LEN) < 1e-6, "win_chance.json: the time steps"
            assert np.abs(p_ + p_[:, ::-1] - 1.0).max() < 1e-9, "win_chance.json: p(-d) must be 1 - p(d)"
            assert np.array_equal(p_[0], np.where(d_ > 0, 1.0, np.where(d_ < 0, 0.0, 0.5))), "win_chance.json: 1 / 0.5 / 0 at the limit"
            assert (np.diff(p_, axis=1) >= 0).all() and p_[-1, D_ + 1] > 0.5, "win_chance.json: the chance must rise with the lead"
            self.win_tab = (p_, float(left_[1]), D_)
            self.win_scale = 1.0 / (float(p_[-1, D_ + 1]) - 0.5)    # a frag at 0:0 with ten minutes left = a frag of today

    def _win_p(self, d, left):
        """the chance of winning the game for a player d frags ahead with `left` seconds to play (win_chance.json: a
        straight line between its time steps; a lead beyond the table counts as its last column)"""
        p, step, D = self.win_tab
        x = np.clip(np.asarray(left, np.float64) / step, 0.0, p.shape[0] - 1.0)
        i0 = np.minimum(x.astype(np.int64), p.shape[0] - 2)
        f = x - i0
        j = (np.clip(np.rint(np.asarray(d, np.float64)), -D, D) + D).astype(np.int64)
        return p[i0, j] * (1.0 - f) + p[i0 + 1, j] * f

    def _game_ok(self):
        """whole games are duels on a real map: not the test map's rooms, not a test room, not a group of more than two"""
        return GAME_ON and self.lab is None and self.fixed_kind is None and self._others_arr().shape[1] == 1

    def _game_rates(self):
        """round starts a second of playing time, by kind_p's shares: an ordinary game round, a whole game, a late round,
        and the other kinds together (aim, one weapon, movement)"""
        kp = np.asarray(self.kind_p, np.float64)
        return (float(kp[0]) * max(0.0, 1.0 - GAME_P - LATE_P) / self.round_len, float(kp[0]) * GAME_P / GAME_LEN,
                float(kp[0]) * LATE_P / LATE_LEN, float((kp[1:] / np.array([15.0, 15.0, self.move_len])).sum()))

    def _game_draw(self, m):
        """is match m's new round a whole game or a late round (by their shares of the playing time)? Then it begins here"""
        if not self._game_ok():
            return False
        r0, rg, rl, rx = self._game_rates()
        if rg + rl <= 0:
            return False
        u = self.rng.random() * (r0 + rg + rl + rx)
        if u >= rg + rl:
            return False
        self._game_start(m, late=bool(u >= rg))
        return True

    def _game_start(self, m, late):
        """match m begins a whole game, or a late round of one (see GAME_P): both seats are networks with the game's
        spawn, every item lies there, clock and score at nothing. A late round's clock, score, stacks and item clocks
        are drawn after the round's reset (_late_start)"""
        q = self._seats(m)
        self.kind[m], self.mode[m] = NORMAL, -1
        self.game[m] = 2 if late else 1
        self.g_tick[m], self.round_t[m], self.g_p[m] = 0, 0.0, 0.5
        self.script[q], self.goal[q], self.frags_r[q], self.snd_t[q] = 0, -1, 0, 99.0
        self.hold_ahead[q] = False
        self.g_win[q], self.g_flat[q] = 0.0, 0.0
        for i in q:
            self.load_sets[int(i)] = ()                     # the game's spawn: machine gun and gauntlet
        self._spawn(int(q[0]), avoid=None)
        self._spawn(int(q[1]), avoid=self.w.state()[int(q[0]), :3])
        self.item_up[m], self.item_t[m] = True, 0.0
        self.contest_t[m] = -1.0
        self.stats["games"][15] += 1
        if late:
            self._late_m.append(int(m))

    def _late_start(self, m):
        """the late round of match m (see LATE_P): the clock at LATE_AT, a drawn score, the stacks that go with it and
        the items' clocks as in the middle of a game"""
        rng = self.rng
        q = [int(x) for x in self._seats(m)]
        d = int(rng.integers(-LATE_LEAD, LATE_LEAD + 1))    # the first seat's lead
        base = int(rng.integers(LATE_BASE[0], LATE_BASE[1] + 1))
        stacked = []
        for i, d_ in zip(q, (d, -d)):
            self.frags_r[i] = base + max(d_, 0)
            if rng.random() < 0.5 + LATE_STACK * d_:         # the leader more often has the stack
                stacked.append(i)
                self.hp[i] = float(rng.uniform(100.0, 200.0))       # (as the random stack of stack_p)
                self.armor[i] = float(rng.uniform(0.0, 150.0))
                for w_ in (RL, LG, RG):                      # (as the holder's start, the weapons the map has)
                    if w_ in self.map_weapons:
                        self.has[i, w_] = True
                        self.ammo[i, w_] = max(float(self.ammo[i, w_]), float(AMMO_MAX[w_]) * 0.4)
                self.first_wp[i] = True
        self.g_tick[m], self.round_t[m] = LATE_FRAME, LATE_AT
        self.g_p[m] = float(self._win_p(d, GAME_LEN - LATE_AT)) if self.win_tab is not None else 0.5
        for it in range(self.nI):
            kind, val, resp, cap, lab = self.item_def[it]
            p_ = LATE_DOWN[0] if lab in ("MH", "RA", "YA", "GA") else LATE_DOWN[1] if kind == "wp" else LATE_DOWN[2]
            if rng.random() >= p_:
                continue
            left = float(rng.uniform(0.0, resp))            # seconds until it is back
            self.item_up[m, it], self.item_t[m, it] = False, left
            who = stacked or q
            i = int(who[int(rng.integers(len(who)))])       # who took it: he knows when it is back
            self.v02_took[i, it] = resp - left
            if lab in ("MH", "RA"):
                self.it_t[i, 0 if lab == "MH" else 1] = resp - left
            for g, ri in enumerate(self.route_item):
                if ri == it and g < self.bel_t.shape[1]:
                    self.bel_t[i, g] = resp - left
                    if self.bel_prev is not None and self.bel_prev.shape[0] == self.M and g < self.bel_prev.shape[1]:
                        self.bel_prev[m, g] = False          # (not "taken since the last look": nobody hears it now)

    def _game_step(self, reward):
        """a frame of the whole games and late rounds: their clock, to the frame, and with WIN_PAY the change in each
        player's chance of winning the game since the frame before (this frame's frags and deaths are in the score)"""
        self.win_pay[:] = 0.0
        gm = np.nonzero(self.game > 0)[0]
        if not len(gm):
            return
        self.g_tick[gm] += 1
        self.round_t[gm] = (self.g_tick[gm] * DT).astype(np.float32)    # (a sum of float32 steps is frames off after ten minutes)
        G = self.stats["games"]
        G[13] += int((self.game[gm] == 1).sum())
        G[14] += int((self.game[gm] == 2).sum())
        if self.win_tab is None:
            return
        g_ = self._others_arr().shape[1] + 1
        a_, b_ = gm * g_, gm * g_ + 1
        p = self._win_p(self.frags_r[a_] - self.frags_r[b_], GAME_LEN - self.g_tick[gm] * DT)
        pay = self.win_scale * (p - self.g_p[gm])
        self.g_p[gm] = p
        reward[a_] += pay
        reward[b_] -= pay
        self.win_pay[a_], self.win_pay[b_] = pay, -pay
        self.g_win[a_] += pay
        self.g_win[b_] -= pay

    def _game_end(self, m):
        """the whole game or late round of match m is over, at the limit (level is a draw: no overtime): into the counters"""
        q = self._seats(m)
        a_, b_ = int(q[0]), int(q[1])
        d = float(self.frags_r[a_] - self.frags_r[b_])
        G = self.stats["games"]
        G[0 if self.game[m] == 1 else 1] += 1
        G[2] += int(d == 0)
        if self.game[m] == 1:
            G[3] += float(self.frags_r[a_] + self.frags_r[b_])
        if m * 2 >= self.M:                                 # the trainer's league half: the first seat is his, the second the league's
            G[4] += 1
            G[5] += int(d > 0)
            G[6] += int(d == 0)
            G[7] += int(d < 0)
            G[8] += d
            G[9] += float(self.g_win[a_])
            G[10] += float(self.g_flat[a_])
        G[11] += abs(float(self.g_win[a_]))
        G[12] += abs(float(self.g_flat[a_]))
        self.game[m] = 0
        self.g_win[q], self.g_flat[q] = 0.0, 0.0

    def _seats(self, m):
        g_ = self._others_arr().shape[1] + 1
        return np.arange(g_ * m, g_ * m + g_)

    def _item_run_start(self, m):
        """start an item run for match m in a share of the rounds (see RUN_LEN); returns its seats, or None"""
        pj = self.jump_run_p if self.jump_tries else 0.0     # (jump runs: a share of the playing time beside the item runs')
        if self.item_run_p + pj <= 0 or self.route is None or self.fixed_kind is not None or getattr(self, "lab_force", None):
            return None
        if self.lab is not None:
            other = float(self.arena_len)
        else:
            other = 1.0 / max(1e-9, float((np.asarray(self.kind_p[:3], np.float64) / np.array([self.round_len, 15.0, 15.0])).sum()))
            if GAME_ON and self._game_ok():                  # (whole games and late rounds are longer than a round)
                r0_, rg_, rl_, _ = self._game_rates()
                other = 1.0 / max(1e-9, r0_ + rg_ + rl_ + float(self.kind_p[1]) / 15.0 + float(self.kind_p[2]) / 15.0)
        p = self.item_run_p + pj
        if self.rng.random() >= (p / RUN_LEN) / (p / RUN_LEN + (1.0 - p) / other):
            return None
        jump = pj > 0 and self.rng.random() < pj / p
        q = self._seats(m)
        if self.lab is not None:
            for i in q:
                self._course_close(int(i), False)
            self.arena[m] = 0
            self.course[q], self.items_room[q], self.gun[q] = -1, False, False
            self.lab_len[m] = RUN_LEN
        self.kind[m], self.mode[m] = MOVE, -1
        self.move_len = RUN_LEN
        self.script[q], self.goal[q], self.frags_r[q], self.snd_t[q] = 0, -1, 0, 99.0
        self.item_up[m], self.item_t[m] = True, 0.0
        self.run_k[q] = 0
        self.cf_side[q] = 0
        self.cf_t[m] = RUN_COLLECT if (not jump and self.rng.random() < self.collect_fight_p) else -1.0
        self.jrun[q] = jump
        for i in q:
            self.load_sets[int(i)] = ()                     # the game's spawn: machine gun and gauntlet
            self.state = self.w.state()
            if jump:
                self._jump_place(int(i))
            else:
                self._spawn(int(i), avoid=None)
        self.state = self.w.state()
        for i in (() if jump else q):
            self._run_pick(int(i))
        return q

    def _jump_place(self, i):
        """a jump run: player i begins a try a second or two of way before the take-off of one of the pros' jumps (every
        jump as often as any other), with the item behind it as his target; the item is put back if it was taken"""
        ks = list(self.jump_tries)
        k = int(ks[int(self.rng.integers(len(ks)))])
        g, st, f = self.jump_tries[k][int(self.rng.integers(len(self.jump_tries[k])))]
        J = self.jfields[f]
        self.jrun_f[i] = f
        node = int(st[int(self.rng.integers(len(st)))])
        nx = int(J.next[g, node])
        p, q = J.nodes[node], (J.nodes[nx] if nx >= 0 else J.goals[g])
        face = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) + float(self.rng.uniform(-40, 40))
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), face)
        self._fresh(i, face)
        m = self._match_of(i)
        self.item_up[m, self.route_item[g]], self.item_t[m, self.route_item[g]] = True, 0.0
        if g < self.bel_t.shape[1]:
            self.bel_t[i, g] = 99.0                         # ... and he knows it is there
        if self.route_goal[g] in ("MH", "RA"):
            self.it_t[i, 0 if self.route_goal[g] == "MH" else 1] = 99.0
        self.jrun_it[i], self.jrun_paid[i], self._replaced = self.route_item[g], 0.0, True
        self.run_k[i] = INTENTS.index(self.route_goal[g])
        self.intent_new[i], self.intent_done[i] = True, True     # the target is read at once
        self.jrun_k[i], self.jrun_t[i] = k, 2.0 * float(J.T[g, node]) + JUMP_TRY_SLACK
        self.jrun_edge[i], self.jrun_over[i], self.jrun_new[i] = False, False, True
        self.jrun_past[i] = False
        if self._counted(i):
            self.stats["jump_tries"][min(k, 63)] += 1

    def _run_pick(self, i):
        """item run: the next target of player i, one of the big items lying there that he can walk to"""
        R = self.route
        node = int(R.locate(self.w.state()[i:i + 1, :3])[0])
        m = i // (self._others_arr().shape[1] + 1)
        gk = {k: int(self._trip_goal(np.array([k]), np.array([node]))[0]) for k in range(1, HOLD_INTENT)}     # (an item: not a holding place)
        Tr = R.T_walk if (RULE_WALK and PRO_WAYS) else R.T    # (RULE_WALK: a target he can walk to, not one behind a pros' step)
        if self.route_o is not None:
            Tr = self.route_o.T                              # (JUMP_OPEN: ... or reach by a jump that is open)
        ks = [k for k, gi in gk.items() if gi >= 0 and k != self.run_k[i] and Tr[gi, node] < 1e8]
        ok = [k for k in ks if self.item_up[m, self.route_item[gk[k]]] and Tr[gk[k], node] > 1.0]
        ok = ok or ks
        self.run_k[i] = int(self.rng.choice(ok)) if ok else 0
        self.intent_new[i], self.intent_done[i] = True, True     # the new target is read at once

    def _runner_keys(self, idx, r, out, engaged):
        """script 3, the item runner (owner, 2026-10-07): he goes for what the item rule names (intent_rule: the mega
        when hurt, the red armor when bare, else the nearest big weapon he lacks) along the walking graph, and fights
        like the all-round scripted fighter when an enemy is in view, still moving along his way. He starts with the
        game's spawn and takes what he walks over. Not rewarded and not imitated: he is in a share of the rounds
        (RUNNER_P) so that the learner meets an opponent who turns up with the stack.
        TRICKS: the holder, the lobber and the watcher are runners too; where _trick_goals names a place that is not an
        item (a spawn point, a post) they walk there by the same rules."""
        R, s = self.route, self.state
        rl = np.nonzero(r)[0]
        ri = idx[rl]
        node = R.locate(s[ri, :3])
        lab = np.array([INTENTS.index(l) if l in INTENTS else -1 for l in self.route_goal], np.int64)
        k = self.intent_teach[ri]
        T = np.where(lab[None, :] == k[:, None], R.T_walk[:, node].T, 1e9)   # (he walks: the walking map's ways)
        gi = T.argmin(1)
        go = (k > 0) & (T[np.arange(len(ri)), gi] < 1e8)
        xg = np.full(len(ri), -1, np.int64)
        if TRICKS and self.route_x is not None:
            xg = self._trick_goals(ri, rl, engaged[rl], k)
        self._walk_keys(R, ri[xg == -1], rl[xg == -1], gi[xg == -1], go[xg == -1], out, engaged)
        if (xg >= 0).any():
            X = self.route_x
            xs = xg >= 0
            ok = X.T_walk[xg[xs], X.locate(s[ri[xs], :3])] < 1e8
            self._walk_keys(X, ri[xs], rl[xs], xg[xs], ok, out, engaged)
        st = rl[(xg == -2) & ~engaged[rl]]                   # at his post, nobody in view: he stands
        out[st, 0], out[st, 1], out[st, 2] = 1, 1, 0

    def _walk_keys(self, R, ri, rl, gi, go, out, engaged):
        """the keys of walkers ri (rows rl of out) along the ways of R to its goal gi"""
        if not len(ri):
            return
        s = self.state
        pos = s[ri, :3]
        node = R.locate(pos)
        nx = R.walk[gi, node]
        tp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[gi])
        near = np.hypot(tp[:, 0] - pos[:, 0], tp[:, 1] - pos[:, 1]) < 48.0
        if WALK_FIX:
            near = near & (np.abs(tp[:, 2] - pos[:, 2]) < 56.0)   # ... and at its height (a landing under the edge is not reached)
        nx2 = np.where(nx >= 0, R.walk[gi, np.maximum(nx, 0)], -1)
        tp = np.where((near & (nx2 >= 0))[:, None], R.nodes[np.maximum(nx2, 0)], tp)   # look one step further when close
        tp = np.where((near & (nx >= 0) & (nx2 < 0))[:, None], R.goals[gi], tp)
        tp = self._enter(R, gi, node, nx, near, tp, s[ri, 6] > 0.5, pos if WALK_FIX else None, s[ri, 5],
                         (self.wet[ri] >= 2) if WALK_FIX else None)
        is_via = WALK_FIX & ~np.isnan(R.via[gi, node][:, 0])
        d = tp - pos
        hd = np.hypot(d[:, 0], d[:, 1])
        rel_deg = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) - self.yaw[ri] + 180.0) % 360.0 - 180.0
        rel = np.radians(rel_deg)
        fwd = np.where(np.cos(rel) > 0.38, 1, np.where(np.cos(rel) < -0.38, -1, 0))
        side = np.where(np.sin(rel) > 0.38, -1, np.where(np.sin(rel) < -0.38, 1, 0))     # +1 = strafe right
        slow = np.hypot(s[ri, 3], s[ri, 4]) < 80.0
        self.sc_stuck[ri] = np.where(slow & go, self.sc_stuck[ri] + 1, 0)
        up = (d[:, 2] > 18.0) & (hd < 260.0) & ~is_via       # a step up, a ledge (an entrance is not one)
        gap = (hd > 150.0) & (d[:, 2] > -40.0) & (nx >= 0) & ~near     # a long edge of the graph on the level: a jump
        jump = (s[ri, 6] > 0.5) & (up | gap | (self.sc_stuck[ri] > 10))
        if WALK_FIX:                                         # in water to the waist or deeper he swims up, unless his way leads down
            jump = jump | ((self.wet[ri] >= 2) & (d[:, 2] > -24.0))    # (Cure's pool, 2026-10-09: the walker stood on its floor)
        out[rl, 0] = np.where(go, fwd + 1, out[rl, 0])
        out[rl, 1] = np.where(go, side + 1, out[rl, 1])
        dive = (self.wet[ri] >= 2) & (d[:, 2] < -24.0) if WALK_FIX else np.zeros(len(ri), bool)    # ... and down where it leads down
        out[rl, 2] = np.where(go, np.where(dive, 2, jump), out[rl, 2])
        turn = np.clip(rel_deg * 0.5, -20.0, 20.0)           # nobody in view: he looks where he is going
        look = go & ~engaged[rl]
        out[rl, 3] = np.where(look, np.abs(TURN[None, :] - turn[:, None]).argmin(1), out[rl, 3])

    def _lob(self, idx, out, vis):
        """TRICKS, the lobber (B-189): with nobody in view he fires where the other one is about to come out: the far end
        of a teleporter or a jump pad within the next steps of the other one's way to the item he is heading for, else
        the place he last saw him (for 4 s). Plasma where he has a line to the place, a grenade's arc where he has none
        and it is within 900 units. He keeps walking his own way meanwhile."""
        s, R = self.state, self.route
        up = np.array([0, 0, 24.0], np.float32)
        for j in np.nonzero((self.script[idx] == 3) & (self.sc_persona[idx] == LOBBER) & ~vis & (self.hp[idx] > 0))[0]:
            i = int(idx[j])
            o = int(self._others_arr()[i, 0])
            if self.hp[o] <= 0:
                continue
            P, exit_, eta = None, False, 0.0
            g = self.intent_gi[int(self.intent[o])] if self.intent[o] > 0 else -1
            if g >= 0:
                a0 = a = int(R.locate(s[o:o + 1, :3])[0])
                for _ in range(40):
                    b = int(R.walk[g, a])
                    if b < 0 or R.T[g, a0] - R.T[g, b] > LOB_AHEAD:
                        break
                    if not np.isnan(R.via[g, a][0]):         # this step goes through a teleporter or a pad: he comes out at b
                        P, exit_, eta = R.nodes[b] + up, True, float(R.T[g, a0] - R.T[g, b])   # ... in about this many seconds
                        break
                    a = b
            if P is None and self.seen_t[i] < 4.0:
                P = self.known[i] + up
            if P is None:
                continue
            eye = (s[i, :3] + np.array([0, 0, VIEW_H], np.float32)).astype(np.float32)
            to = (P - eye).astype(np.float64)
            D, dist = float(np.hypot(to[0], to[1])), float(np.linalg.norm(to))
            if dist > 1800.0 or dist < 200.0:
                continue
            if self.has[i, PG] and self.ammo[i, PG] > 0 and self.w.trace(eye, P.astype(np.float32), mask=self.sight)["fraction"] >= 0.97:
                if exit_ and eta > LOB_PG_ETA:               # (too early: the balls would be gone before he comes out)
                    continue
                wpn, pit = PG, -np.degrees(np.arctan2(to[2], D))
            elif D < 900.0 and self.has[i, GL] and self.ammo[i, GL] > 0:
                if exit_ and not (LOB_GL_ETA[0] <= eta <= LOB_GL_ETA[1]):   # (a grenade goes off 2.5 s after it is fired)
                    continue
                v_, g_ = float(P_SPEED[GL]), 800.0
                disc = v_ ** 4 - g_ * (g_ * D * D + 2.0 * to[2] * v_ * v_)
                if disc < 0:
                    continue
                th = np.arctan2(v_ * v_ - np.sqrt(disc), g_ * D)         # the low arc; the game lofts a grenade by 0.2
                wpn, pit = GL, -np.degrees(th - 0.2 * np.cos(th))
            else:
                continue
            ey = (np.degrees(np.arctan2(to[1], to[0])) - self.yaw[i] + 180.0) % 360.0 - 180.0
            ep = pit - self.pitch[i]
            out[j, 3] = int(np.abs(TURN - np.clip(ey * 0.5, -20.0, 20.0)).argmin())
            out[j, 4] = int(np.abs(PITCH - np.clip(ep * 0.4, -6.0, 6.0)).argmin())
            out[j, 6] = 0 if self.weapon[i] == wpn else wpn + 1
            out[j, 5] = int(self.weapon[i] == wpn and abs(ey) < 5.0 and abs(ep) < 4.0)
            if out[j, 5]:
                self.stats["lob"][0 if wpn == PG else 1] += 1
                self.stats["lob"][2] += int(exit_)

    def _trick_points(self, nav, pads, teles, more_):
        """TRICKS: the places a scripted opponent walks to that are not items, and the ways to them (a second route field):
        the map's spawn points (the holder comes for him after a frag), then for every item two posts to watch its
        approach from (the watcher): points 450 to 1400 units away that see the item and the most of the ground round
        it, the higher the better."""
        R = self.route
        pts = [np.asarray(p, np.float32) for p in self.spawns]
        self.x_spawns = len(pts)
        self.x_watch = {}
        live = np.nonzero(~R.dead)[0]
        rng = np.random.default_rng(7)
        eye = np.array([0, 0, VIEW_H], np.float32)
        up30 = np.array([0, 0, 30.0], np.float32)
        for gi, gp in enumerate(R.goals):
            d = np.linalg.norm(R.nodes[live] - gp, axis=1)
            cand = live[(d > 450.0) & (d < 1400.0) & (R.T_walk[gi, live] < 1e8)]
            near = live[d < 320.0]
            if not len(cand) or not len(near):
                continue
            cand = rng.choice(cand, min(60, len(cand)), replace=False)
            near = rng.choice(near, min(24, len(near)), replace=False)
            B = np.concatenate([R.nodes[near] + up30, (gp + up30)[None]]).astype(np.float32)
            score = np.zeros(len(cand))
            for a_, c_ in enumerate(cand):
                see = self._los(np.repeat((R.nodes[c_] + eye)[None], len(B), 0).astype(np.float32), B)
                score[a_] = (see[:-1].mean() + 0.003 * float(np.clip(R.nodes[c_][2] - gp[2], -100.0, 300.0))) * see[-1]
            posts = []
            for b_ in np.argsort(-score)[:6]:
                if score[b_] > 0.4 and all(np.linalg.norm(R.nodes[cand[b_]] - pts[q_]) > 250.0 for q_ in posts) and len(posts) < 2:
                    posts.append(len(pts))
                    pts.append(R.nodes[cand[b_]].copy())
            if posts:
                self.x_watch[gi] = posts
        self.xpts = np.array(pts, np.float32)
        self.route_x = RouteField(nav, self.xpts, pads=pads, teles=teles, **more_)
        self.route_x.walk, self.route_x.T_walk = self.route_x.next, self.route_x.T

    def _trick_goals(self, ri, rl, engaged, k):
        """TRICKS: for the runners ri, the place that is not an item each one walks to (an index into xpts), -1 for none
        (he follows the item rule), -2 for a watcher standing at his post.
        The holder, after a frag (hunt_t): once the other one lives again, the spawn point nearest to him, until he sees
        him or the time is up, and not while the mega or the red armor is due. The watcher: a post for the item the other
        one is heading for (his intention), kept WATCH_SECS; arrived, he stands and looks at the item."""
        X, R, s = self.route_x, self.route, self.state
        out = np.full(len(ri), -1, np.int64)
        opp = self._others_arr()[ri, 0]                      # the other one (these opponents are for duels)
        per = self.sc_persona[ri]
        big = np.isin(k, [INTENTS.index(l) for l in ("MH", "RA") if l in INTENTS])
        # the holder
        h = per == HOLDER
        self.hunt_t[ri] = np.where(h, np.maximum(0.0, self.hunt_t[ri] - DT), 0.0)
        self.hunt_t[ri[h & engaged]] = 0.0
        start = h & (self.hunt_t[ri] > 0) & (self.x_goal[ri] < 0) & (self.hp[opp] > 0)
        if start.any():
            sp = np.linalg.norm(self.xpts[None, :self.x_spawns] - s[opp[start], None, :3], axis=2).argmin(1)
            self.x_goal[ri[start]] = sp
        self.x_goal[ri[h & (self.hunt_t[ri] <= 0)]] = -1
        hunt = h & (self.x_goal[ri] >= 0) & ~big
        out[hunt] = self.x_goal[ri[hunt]]
        # the watcher
        w = per == WATCHER
        if w.any() and self.x_watch:
            self.watch_t[ri] = np.where(w, self.watch_t[ri] - DT, 0.0)
            for j in np.nonzero(w & ((self.watch_t[ri] <= 0) | (self.x_goal[ri] < 0)))[0]:
                g_ = self.intent_gi[int(self.intent[opp[j]])] if self.intent[opp[j]] > 0 else -1
                posts = self.x_watch.get(int(g_)) or (self.x_watch[self.rng.choice(list(self.x_watch))] if self.x_watch else None)
                self.x_goal[ri[j]] = int(self.rng.choice(posts)) if posts else -1
                self.watch_t[ri[j]] = WATCH_SECS
            ww = w & (self.x_goal[ri] >= 0) & self.has[ri, RG]       # (without the rail he is a runner until he has one)
            node = X.locate(s[ri, :3])
            at = ww & (X.T_walk[np.maximum(self.x_goal[ri], 0), node] < 0.25)
            out[ww] = self.x_goal[ri[ww]]
            out[at] = -2
            self.sc_look[ri] = at & ~engaged
            for j in np.nonzero(at & ~engaged)[0]:               # he looks at the item his post watches
                g_ = next((g for g, ps in self.x_watch.items() if int(self.x_goal[ri[j]]) in ps), None)
                if g_ is not None:
                    self.known[ri[j]] = R.goals[g_]
        far = (out >= 0) & (X.T_walk[np.maximum(out, 0), X.locate(s[ri, :3])] >= 1e8)
        out[far] = -1                                        # no way there from where he is: the item rule
        return out

    # ---------------------------------------------------------------- step
    def limit_keys(self, a, who=None):
        """finger limits (see FINGER_HOLD): turns the requested keys and weapon choice into what one hand can do.
        Changes a[:, :3] and a[:, 6] in place."""
        if who is None:
            who = self.script == 0
        self.key_tick += 1                                  # the left hand decides ten times a second (staggered by player)
        dec = ((self.key_tick + np.arange(len(a))) % KEY_EVERY == 0) | ~who
        self.key_dec = dec.copy()                           # (the trainer credits the keys and the weapon key on these frames only)
        cols = [0, 1, 2, 6]
        self.stats["key_asked"] += int(((a[:, :3] != self.key_last) & who[:, None] & dec[:, None]).sum())
        self.key_req = np.where(dec[:, None], a[:, cols], self.key_req)
        a[:, cols] = np.where(who[:, None], self.key_req, a[:, cols])
        self.key_tok = np.minimum(KEY_BURST, self.key_tok + KEY_RATE * DT).astype(np.float32)
        self.key_hold += 1
        ready = self.key_hold >= FINGER_HOLD[None, :]
        last = self.key_last

        def act(finger, wants):
            """the fingers that act now among those that want to; books the action"""
            ok = who & wants & ready[:, finger] & (self.key_tok >= 1.0)
            self.key_tok[ok] -= 1.0
            self.key_hold[ok, finger] = 0
            ready[ok, finger] = False
            self.stats["key_changes"] += int(ok.sum())
            self.stats["key_blocked"] += int((who & wants & ~ok).sum())
            return ok

        # thumb: jump key down or up
        j_now, j_want = last[:, 2] == 1, a[:, 2] == 1
        j_new = np.where(act(THUMB, j_now != j_want), j_want, j_now)
        # index finger: a weapon key first, then strafe right
        w_want = (a[:, 6] > 0) & (a[:, 6] - 1 != self.weapon)
        w_ok = act(INDEX, w_want)
        a[:, 6] = np.where(who & w_want & ~w_ok, 0, a[:, 6])
        d_now, d_want = last[:, 1] == 2, a[:, 1] == 2
        d_new = np.where(act(INDEX, d_now != d_want), d_want, d_now)
        # ring finger: strafe left
        l_now, l_want = last[:, 1] == 0, a[:, 1] == 0
        l_new = np.where(act(RING, l_now != l_want), l_want, l_now)
        # middle finger: forward and back; a reversal first lets go
        f_now, f_want = last[:, 0], a[:, 0].copy()
        f_want = np.where((f_now != 1) & (f_want != 1) & (f_now != f_want), 1, f_want)
        f_new = np.where(act(MIDDLE, f_now != f_want), f_want, f_now)
        # little finger: crouch
        c_now, c_want = last[:, 2] == 2, a[:, 2] == 2
        c_new = np.where(act(LITTLE, c_now != c_want), c_want, c_now)
        if a.shape[1] > 7:                                   # the walk key: the same finger, so not while it has just acted
            w_want = a[:, 7] == 1
            w_new = np.where(act(LITTLE, self.walk_last != w_want), w_want, self.walk_last)
            self.walk_last = np.where(who, w_new, w_want)
            a[:, 7] = self.walk_last
        # the right hand: fire (index finger) and zoom (middle finger); no shared budget, only the hold per finger
        self.mouse_hold += 1
        f_want = a[:, 5] == 1
        f_ok = who & (f_want != self.fire_last) & (self.mouse_hold[:, 0] >= MOUSE_HOLD[0])
        self.mouse_hold[f_ok, 0] = 0
        self.fire_last = np.where(who, np.where(f_ok, f_want, self.fire_last), f_want)
        a[:, 5] = self.fire_last
        if a.shape[1] > 8:
            z_want = a[:, 8] == 1
            z_ok = who & (z_want != self.zoom) & (self.mouse_hold[:, 1] >= MOUSE_HOLD[1])
            self.mouse_hold[z_ok, 1] = 0
            self.zoom = np.where(who, np.where(z_ok, z_want, self.zoom), False)
            a[:, 8] = self.zoom
        strafe = np.where(l_new & ~d_new, 0, np.where(d_new & ~l_new, 2, 1))       # both down cancel out
        vert = np.where(j_new, 1, np.where(c_new, 2, 0))
        new = np.stack([f_new, strafe, vert], 1)
        new = np.where(who[:, None], new, a[:, :3])
        self.key_last[:] = new
        a[:, :3] = new

    def aux(self, st=None, fall=None, events=(), died=None):
        """info["aux"] (see AUX_COLS): [players, len(AUX_COLS)] float32, the game as it truly stands now and, given step()'s
        books of the frame (st: the damage by attacker and by victim; fall: the fall damage; events: the frags; died), what
        happened in it. With nothing given the event columns are zero (a simulator's first frame). Reads only: no random
        number, no state changed."""
        n = self.n
        s = self.state
        C = {k_: i_ for i_, k_ in enumerate(AUX_COLS)}
        out = np.zeros((n, len(AUX_COLS)), np.float32)
        oth = self._others_arr()
        foe = getattr(self, "foe", None)                     # (a group: the enemy he attends to)
        if foe is None:
            foe = oth[:, 0]
        grp = np.arange(n) // (oth.shape[1] + 1)
        yr = np.radians(self.yaw)
        c, si = np.cos(yr), np.sin(yr)
        d = s[foe, :3] - s[:, :3]
        out[:, C["en_fwd"]] = c * d[:, 0] + si * d[:, 1]
        out[:, C["en_left"]] = -si * d[:, 0] + c * d[:, 1]
        out[:, C["en_up"]] = d[:, 2]
        kd = self.kind[grp]
        about = (kd != MOVE) & (kd != SOLO) & ((kd != COURSE) | self.gun)      # (the rounds in which he can see another player)
        out[:, C["en_alive"]] = about & (self.hp[foe] > 0)
        out[:, C["en_in_view"]] = np.asarray(self.visible, bool)
        for k_, id_ in enumerate(self.big_ids):              # the mega, the red armor
            out[:, C["mega_s"] + k_] = AUX_ITEM_CAP if id_ < 0 else np.where(self.item_up[grp, id_], 0.0,
                                                                             np.minimum(self.item_t[grp, id_], AUX_ITEM_CAP))
        out[:, C["x"]:C["x"] + 3] = s[:, :3]
        out[:, C["yaw"]] = (self.yaw + 180.0) % 360.0 - 180.0
        out[:, C["pitch"]] = self.pitch
        out[:, C["eye_h"]] = np.where(self.duck, VIEW_H_DUCK, VIEW_H)
        if st is not None:
            for (i_, v_), d_ in st["by"].items():            # (the damage as booked per attacker: _book)
                out[i_, C["dmg_dealt"]] += d_
            out[:, C["dmg_taken"]] = st["dmg_taken"] + (0.0 if fall is None else fall)
            for e_ in events:
                if e_["killer"] >= 0 and e_["killer"] != e_["victim"]:
                    out[e_["killer"], C["frag"]] = 1.0
                    out[e_["victim"], C["fragged"]] = 1.0
        if died is not None:
            out[:, C["died"]] = died
        return out

    def step(self, actions):
        a = np.array(actions, copy=True)
        n = self.n
        ar = np.arange(n)
        sc = np.nonzero(self.script > 0)[0]
        if len(sc):
            a[sc] = self._script_actions(sc)
        if LEGS and a.shape[1] > LEGS_HEAD:
            self._legs_step(a)
        if self.key_limits:
            self.limit_keys(a)
        human = self.script == 0                            # policy-controlled players (for the statistics)
        prev_int, prev_done = self.intent.copy(), self.intent_done.copy()
        self.intent_teach = self.intent_rule()
        self.intent_teach = np.where((np.repeat(self.kind, len(self.hp) // len(self.kind)) != NORMAL) & (self.run_k < 0), 0,
                                     self.intent_teach)     # a drill or an aim round: nothing to fetch
        if TARGETS:                                          # where the rule names no item its lesson is silent (a negative label: the
            self.intent_teach = np.where((self.intent_teach == 0) & human, -1, self.intent_teach)   # trainer leaves the frame out)
        ch_ = (a[:, 10] if a.shape[1] > 10 else np.zeros(n, np.int64)).copy()
        in_run = self.run_k >= 0
        ch_[in_run] = self.run_k[in_run]                    # an item run: the target is given, not chosen
        self.way_trips = []                                 # (WAY_MEASURE: this step's trips)
        wy_ = None
        if WAYS and a.shape[1] > WAY_HEAD:                   # his way: the thirteenth output; the shortest in an item run or a jump run
            wy_ = np.where(in_run, 0, a[:, WAY_HEAD])
        self.intend(ch_, human, wy_)
        self.intent_live = self.intent_live & ~in_run       # (and the intention head is not trained on those frames)
        if WAYS:                                             # (nor the way: it is given there)
            self.way_live = self.way_live & ~in_run
            self.stats["way_reads"] += np.bincount(self.way[self.way_live & self._counted(ar)], minlength=N_WAYS)
        self.stats["intent_trips"][0] += int((self.intent_changed & (self.intent > 0)).sum())
        self.stats["intent_trips"][2] += int((self.intent_changed & (prev_int > 0) & ~prev_done).sum())
        self.stats["intent_frames"] += np.bincount(self.intent[human], minlength=len(INTENTS))
        pkind = np.repeat(self.kind, 2)
        walk = (a[:, 7] == 1) & (not self.no_walk)
        key = np.where(walk, WALK, 127).astype(np.int32)   # walking: slower and silent
        fwd = (a[:, 0].astype(np.int32) - 1) * key
        side = (a[:, 1].astype(np.int32) - 1) * key
        jump = np.where(a[:, 2] == 1, 127, np.where(a[:, 2] == 2, -127, 0)).astype(np.int32)   # jump / crouch
        self.duck = (a[:, 2] == 2) & (self.hp > 0)
        fire = a[:, 5] == 1
        prev = self.state.copy()
        # mouse: the chosen turn speed is followed with a little inertia; jerky commands cost a little
        cmd = np.stack([TURN[a[:, 3]], PITCH[a[:, 4]]], 1)
        cmd = cmd * np.where(self.zoom, ZOOM, 1.0).astype(np.float32)[:, None]      # zoomed: the same hand movement turns less
        jerk = np.abs(cmd - self.cmd).sum(1)
        self.cmd = cmd
        sg_ = np.sign(cmd[:, 0])
        ch_ = (sg_ != 0) & (self.turn_dir != 0) & (sg_ != self.turn_dir)
        self.rev_wait = np.where(ch_, self.t_rev, np.maximum(0.0, self.rev_wait - 1.0)).astype(np.float32)
        self.turn_dir = np.where(sg_ != 0, sg_, self.turn_dir).astype(np.float32)
        sm = np.where(np.abs(cmd) <= 1.0, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH)   # small corrections follow faster
        self.mv = sm * self.mv + (1.0 - sm) * cmd
        if self.human_aim:
            zs = np.where(self.zoom, ZOOM, 1.0).astype(np.float32)
            self.mv[:, 0] = np.clip(self.mv[:, 0], -TURN_CAP * zs, TURN_CAP * zs)
            jit = self.rng.normal(0, 1, self.mv.shape).astype(np.float32) * (MOTOR_NOISE * np.abs(self.mv) + MOTOR_BASE * zs[:, None])
            jit[self.script > 0] = 0.0
            turn, dpit = self.mv[:, 0] + jit[:, 0], self.mv[:, 1] + jit[:, 1]
            turn, dpit = self.pad_turn(turn, dpit, (a[:, 9] == 1) if a.shape[1] > 9 else np.zeros(n, bool), zs, self.script == 0)
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
        self.r_long = r_long = np.zeros(n, np.float32)      # the game's part of this frame's pay (see r_long in __init__)
        self.snd_t += DT
        self.shot_t += DT
        self.pain_t += DT
        self.trail_t += DT
        self._hear(2, np.nonzero((prev[:, 6] > 0.5) & (s[:, 6] < 0.5) & (s[:, 5] > 100))[0])      # jumps
        self._hear(3, np.nonzero(np.linalg.norm(s[:, :3] - prev[:, :3], axis=1) > 200)[0])       # teleports
        self.sp_hist = np.roll(self.sp_hist, 1, 1)
        self.sp_hist[:, 0] = np.hypot(prev[:, 3], prev[:, 4])
        # fall damage (Quake 3 rule: from the speed of the landing)
        land = (prev[:, 6] < 0.5) & (s[:, 6] > 0.5)
        delta = prev[:, 5] ** 2 * 0.0001
        fall = np.where(land & (prev[:, 5] < 0), np.where(delta > FALL_FAR, 10.0, np.where(delta > FALL_MED, 5.0, 0.0)), 0.0)
        fallers = np.nonzero(fall > 0)[0]
        reward -= SWITCH_COST * sw
        if HOP_PAY:                                          # speed gained from hop to hop (see HOP_PAY)
            hv_ = np.hypot(s[:, 3], s[:, 4])
            hc_ = np.clip(hv_, SPEED_LO, SPEED_HI)
            giv_ = (hv_ > self.hop_sp + HOP_GIVEN) & (self.hop_best > 0)   # speed given to him in this one frame, in a chain
            self.hop_sp = hv_
            self.hop_gnd = np.where(s[:, 6] > 0.5, self.hop_gnd + 1, 0)
            end_ = (self.hop_gnd > HOP_GROUND / DT + 0.5) | (hv_ < HOP_SLOW) | np.asarray(self.visible, bool)   # the chain ends: its best is forgotten
            self.hop_best = np.where(end_, 0.0, np.where(giv_, np.maximum(self.hop_best, hc_), self.hop_best)).astype(np.float32)
            self.hop_sum = np.where(end_, 0.0, self.hop_sum).astype(np.float32)
            self.hop_k = np.where(end_, 0, self.hop_k)
            off_ = ((jump > 0) & (s[:, 6] < 0.5) & (s[:, 5] > 100.0) & (s[:, 5] < HOP_VZ) & ~end_
                    & ((prev[:, 6] > 0.5) | (prev[:, 5] <= 0.0)))          # a take-off: from the floor, or touched inside the frame
            can_ = off_ & human & (self.hp > 0) & ((pkind == NORMAL) | in_run)
            hop_ = HOP_PAY * np.where(can_ & (self.hop_best > 0), np.maximum(0.0, hc_ - self.hop_best), 0.0)   # (the first sets the best)
            reward += hop_
            self.hop_best = np.where(off_, np.maximum(self.hop_best, hc_), self.hop_best).astype(np.float32)
            self.hop_sum = (self.hop_sum + hop_).astype(np.float32)
            self.stats["hop_pay"] += float(hop_.sum())
            self.stats["hop_n"] += int((hop_ > 0).sum())
            self.stats["hop_takeoffs"] += int(can_.sum())
            self.stats["hop_chains"] += int((can_ & (self.hop_k == 0)).sum())
            self.hop_k = self.hop_k + can_
        blind = fire & (self.seen_t > 1.0) & (pkind != MOVE) & ((pkind != COURSE) | self.gun)
        if BLIND_RULE:                                       # (rockets by where they land, below; plasma and grenades free)
            bill = blind & np.isin(self.weapon, (MG, SG, LG, RG, HMG))
            pf_ = np.nonzero(bill & (self.seen_t <= PREFIRE_T))[0]
            if len(pf_):                                     # pre-fire: the crosshair on where the enemy must be by now
                yr_, pr_ = np.radians(self.yaw[pf_]), np.radians(self.pitch[pf_])
                fd_ = np.stack([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)], 1)
                to_ = (self.known[pf_] + self.last_vel[pf_] * np.minimum(self.seen_t[pf_], 1.0)[:, None]
                       + np.array([0, 0, 4.0], np.float32) - self._eye(s)[pf_])
                al_ = (to_ * fd_).sum(1)
                near_ = (al_ > 0) & (np.linalg.norm(to_ - al_[:, None] * fd_, axis=1) <= PREFIRE_R)
                bill[pf_[near_]] = False
                self.stats["prefire_frames"] += int(near_.sum())
            reward -= BLIND_FIRE_COST * bill
            self.stats["blind_bill"] += int(bill.sum())
        else:
            reward -= BLIND_FIRE_COST * blind
        fight = human & (pkind != MOVE) & ((pkind != COURSE) | self.gun)
        if LEGS:
            lg_, up_ = self.legs_on, human & (self.hp > 0)
            gm_ = up_ & (pkind == NORMAL) & (self.run_k < 0)
            sp_ = np.hypot(prev[:, 3], prev[:, 4])
            self.stats["legs"] += np.array([lg_.sum(), (lg_ & np.asarray(self.visible, bool)).sum(), (self.legs & ~lg_ & ~self.legs_wh).sum(), up_.sum(), (lg_ & gm_).sum(),
                                            gm_.sum(), sp_[lg_].sum(), sp_[up_ & ~lg_].sum()], np.float64)
            if LEGS_LAB:
                self._legs_count(sp_)
        self.stats["switches"] += int((sw & fight).sum())
        self.stats["hand_w"] += np.bincount(self.weapon[fight & (self.hp > 0)], minlength=NW)
        self.stats["hand_g"] += np.bincount(self.weapon[fight & (pkind == NORMAL) & (self.hp > 0)], minlength=NW)
        self.stats["blind_w"] += np.bincount(self.weapon[blind & fight], minlength=NW)
        self.stats["fire_frames"] += int((fire & fight).sum())
        self.stats["blind_frames"] += int((blind & fight).sum())
        self.stats["play_frames"] += int(fight.sum())
        self.stats["duck_frames"] += int((self.duck & fight).sum())
        self.stats["walk_frames"] += int((walk & fight).sum())
        self.stats["bot_frames"] += int((self.script >= 2).sum())
        np.add.at(self.stats["vs_persona"][2], self.sc_persona[self.script >= 2], 1)
        self.stats["aim_round_frames"] += int((human & (pkind == AIM)).sum())
        # movement rounds: reward = seconds gained toward the goal (nav-graph time), like movement_env
        mi = np.nonzero(self.goal >= 0)[0]
        if len(mi):
            phi, _ = self.field.potential(self.goal[mi], s[mi, :3])
            reward[mi] += MOVE_SCALE * (np.clip(self.phi[mi] - phi, -0.5, 0.5) - DT)
            r_long[mi] += MOVE_SCALE * (np.clip(self.phi[mi] - phi, -0.5, 0.5) - DT)
            self.phi[mi] = phi
            gp = self.field.goals[self.goal[mi]]
            arrived = (np.hypot(gp[:, 0] - s[mi, 0], gp[:, 1] - s[mi, 1]) < 40) & (np.abs(gp[:, 2] - s[mi, 2]) < 64)
            sp = np.hypot(s[mi, 3], s[mi, 4])
            self.stats["move_frames"] += len(mi)
            self.stats["move_speed"] += float(sp.sum())
            self.stats["move_fast"] += int(((sp > 330) & (s[mi, 6] < 0.5)).sum())
            for i, v in zip(mi[arrived], sp[arrived]):
                reward[i] += MOVE_ARRIVE * (0.5 + min(1.5, float(v) / 320.0))   # arriving fast is worth more
                r_long[i] += MOVE_ARRIVE * (0.5 + min(1.5, float(v) / 320.0))
                self.stats["move_arrive"] += 1
                self._new_goal(int(i))
        self.stats["jerk"] += float(jerk.sum())
        st = dict(dmg_taken=np.zeros(n, np.float32), attacker=np.full(n, -1), kill_w={}, kicked=False,
                  by={}, killer=np.full(n, -1))               # damage per (attacker, victim) this frame; who took him below zero
        for v in fallers:
            self._damage(int(v), float(fall[v]))
            self.stats["fall_dmg"] += float(fall[v])
        for hz in self.hurt_zones:                          # lava and the void
            feet = s[:, 2] + MINS[2]
            inz = (s[:, 0] >= hz[0]) & (s[:, 0] <= hz[3]) & (s[:, 1] >= hz[1]) & (s[:, 1] <= hz[4]) &                 (feet >= hz[2]) & (feet < hz[5]) & (self.hp > 0)
            for v in np.nonzero(inz)[0]:
                d_ = float(self.hp[v] + self.armor[v] + 1.0) if hz[6] >= 1000 else float(hz[6]) * DT
                if hz[6] >= 1000:
                    self.armor[v] = 0.0
                took_ = self._damage(int(v), d_)
                st["dmg_taken"][v] += took_ if hz[6] < 1000 else 0.0     # the void costs the death, nothing more
                self.stats["hurt_dmg"] += d_ if hz[6] < 1000 else 0.0
                self.stats["void_deaths"] += int(hz[6] >= 1000)
        if LAVA:                                             # lava and slime by the map's own brushes (see LAVA)
            self.lava_t = np.maximum(0.0, self.lava_t - DT).astype(np.float32)
            live_ = np.nonzero(self.hp > 0)[0]
            if len(live_):
                pts_ = s[live_, None, :3] + np.array([[0, 0, MINS[2] + 1.0], [0, 0, 1.0], [0, 0, 26.0]], np.float32)[None]
                cc_ = self.w.contents_n(pts_.reshape(-1, 3)).reshape(len(live_), 3)
                liq_ = (cc_ & (C_LAVA | C_SLIME | C_WATER)) != 0
                depth_ = liq_[:, 0].astype(np.int64) + (liq_[:, 0] & liq_[:, 1]) + (liq_[:, 0] & liq_[:, 1] & liq_[:, 2])
                self.wet[:] = 0
                self.wet[live_] = depth_
                dmg_ = depth_ * (LAVA_DMG * ((cc_[:, 0] & C_LAVA) != 0) + SLIME_DMG * ((cc_[:, 0] & C_SLIME) != 0))
                for k_ in np.nonzero((dmg_ > 0) & (self.lava_t[live_] <= 0))[0]:
                    v = int(live_[k_])
                    took_ = self._damage(v, float(dmg_[k_]))
                    st["dmg_taken"][v] += took_
                    self.stats["hurt_dmg"] += float(dmg_[k_])
                    self.lava_t[v] = LAVA_TICK

        if self.courses and (self.course >= 0).any() and self._course_step(reward):
            self.state = s = self.w.state()
            self.yaw = s[:, 7].copy()
        # fire: a shot leaves one frame after the command
        self.cool = np.maximum(0.0, self.cool - DT)
        self.fire_cd = np.maximum(0.0, self.fire_cd - DT)
        do_fire, do_w = self.fire_q, self.fire_w
        ammo_ok = (self.ammo[ar, self.weapon] > 0) | (self.weapon == G)
        shoot = fire & (self.cool <= 1e-4) & ammo_ok & self.has[ar, self.weapon]
        if AUTO_SWITCH:                                      # the trigger on an empty weapon: the game brings up another (see AUTO_SWITCH)
            dry = np.nonzero(fire & (self.cool <= 1e-4) & ~ammo_ok & (self.script == 0) & (self.hp > 0))[0]
            if len(dry):
                can = self.has[dry] & (self.ammo[dry] > 0)
                can[:, G] = True
                self.weapon[dry] = AUTO_ORDER[can[:, AUTO_ORDER].argmax(1)]
                self.cool[dry] = np.maximum(self.cool[dry], NOAMMO_WAIT + SWITCH)
                self.stats["auto_switch"] += len(dry)
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
        hum_ = (self.script == 0) & (self.hp > 0)
        self.stats["fire_vis"] += int((fire & self.visible & hum_).sum())
        self.stats["vis_frames_h"] += int((self.visible & hum_).sum())
        if SHOT_COST > 0:                                    # ammo is scarce: every shot has its price (see SHOT_COST)
            sc_ = np.nonzero(use & (self.script == 0))[0]
            if len(sc_):
                w_ = self.weapon[sc_]
                fac_ = self.shot_scarce[w_] * np.clip(1.5 - self.ammo[sc_, w_] / SHOT_UNIT[w_], 0.5, 1.5)
                if self.shot_way is not None:
                    fac_ = fac_ * np.clip(self.shot_way[w_, self.route.locate(s[sc_, :3])] / SHOT_NEAR_S, 0.5, 1.5)
                fac_ = np.clip(fac_, 0.25, 3.0)
                cost_ = SHOT_COST * self.dmg_reward * SHOT_DMG[w_] * fac_ * SHOT_W[w_]
                reward[sc_] -= cost_
                self.stats["shot_cost"] += float(cost_.sum())
                self.stats["shot_n"] += len(sc_)
                self.stats["shot_fac"] += float(fac_.sum())
        if BLIND_RULE:
            br_ = np.nonzero(use & (self.weapon == RL) & (self.script == 0) & (self.seen_t > 1.0) & (pkind != MOVE)
                             & ((pkind != COURSE) | self.gun))[0]
            if len(br_):
                self._blind_rockets(br_, s, reward)
        self.fire_q, self.fire_w = shoot, self.weapon.copy()
        self._hear(1, np.nonzero(shoot & (self.weapon != G))[0])
        self.hear((shoot & (self.weapon != G)) | ((prev[:, 6] > 0.5) != (s[:, 6] > 0.5)) |      # shots, jumps and landings,
                  ((s[:, 6] > 0.5) & (np.hypot(s[:, 3], s[:, 4]) > 200.0) & ~self.duck))      # running steps (not walking, not crouched)
        self.note_noise(shoot & (self.weapon != G), (prev[:, 6] > 0.5) != (s[:, 6] > 0.5),      # (N_V02: the same events, for the one who makes them)
                        (s[:, 6] > 0.5) & (np.hypot(s[:, 3], s[:, 4]) > 200.0) & ~self.duck)
        self.note_shots(np.nonzero(shoot & (self.weapon != G))[0])
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
                    if self.w.trace(eye[i], s[v, :3] + np.array([0, 0, 4.0], np.float32), mask=self.sight)["fraction"] < 0.999:
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
                fd = fdir[i]
                if MG_SPREAD > 0 and wpn in (MG, HMG):        # the bullet leaves somewhere inside the cone
                    u_ = np.cross(fd, np.array([0.0, 0.0, 1.0], np.float32))
                    u_ = u_ / (np.linalg.norm(u_) + 1e-6)
                    v_ = np.cross(fd, u_)
                    ra_, th_ = math.tan(math.radians(MG_SPREAD)) * self.rng.random(), self.rng.random() * 2 * math.pi
                    fd = fd + (u_ * math.cos(th_) + v_ * math.sin(th_)) * ra_
                    fd = (fd / np.linalg.norm(fd)).astype(np.float32)
                fr = self.w.rays_each(eye[i:i + 1], fd[None, None, :], rng_, mask=self.sight)[0, 0]
                end = eye[i] + fd * rng_ * fr
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
                fr[q] = self.w.rays_each(p0[q:q + 1], dirs[q:q + 1, None, :], float(step_len[q]), mask=self.sight)[0, 0]
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
                    tr = self.w.trace(p0[q], p0[q] + dirs[q] * float(step_len[q]), mask=self.sight)
                    nrm = tr["normal"]
                    vq = self.rv[i, k]
                    vq = (vq - 2.0 * float(vq @ nrm) * nrm) * GL_BOUNCE
                    if nrm[2] > 0.2 and np.linalg.norm(vq) < 40:
                        vq[:] = 0.0                         # resting on the floor until the fuse runs out
                    self.rv[i, k] = vq
                    self.rp[i, k] = hitpt[q] + nrm * 0.5
                    if GL_QL:                               # the rest of the frame, on its new way (not through a second surface)
                        rest_ = vq * (DT * (1.0 - float(fr[q])))
                        f2_ = self.w.trace(self.rp[i, k], self.rp[i, k] + rest_, mask=self.sight)["fraction"]
                        self.rp[i, k] = self.rp[i, k] + rest_ * max(0.0, f2_ - 0.01)
        if st["kicked"]:
            self.state = s = self.w.state()                  # knockback changed velocities
        dmg_taken, attacker, kill_w = st["dmg_taken"], st["attacker"], st["kill_w"]

        # shaping (curriculum): reward damage dealt to the opponent
        opp_all = ar ^ 1
        hurt = np.nonzero((dmg_taken > 0) & (self.hp > 0))[0]              # pain sounds: the opponent hears them within earshot
        if len(hurt):
            lis_ = hurt ^ 1
            near_ = np.linalg.norm(s[hurt, :3] - s[lis_, :3], axis=1) < HEAR_EVT
            self.pain_t[lis_[near_]] = 0.0
            self.pain_b[lis_[near_]] = np.minimum(3, (self.hp[hurt[near_]] // 25).astype(np.int64))
        dealt = np.zeros(n, np.float32)                     # per attacker (see _book)
        for (i_, v_), d_ in st["by"].items():
            dealt[i_] += d_
        high_ = self._high(st["by"], s, n)                  # (B-160) who stood higher at each hit; with HIGH_PAY what that adds for the two
        taken = dmg_taken + fall                            # from the opponent, own splash and falls alike
        self.stats["soak"] += float(self.soak[self.script == 0].sum())
        if ARMOR_COST != 1.0:                               # what his armor soaked costs him less (see ARMOR_COST)
            taken = taken - (1.0 - ARMOR_COST) * self.soak
        self.soak[:] = 0.0
        if self.gun.any():                                  # run-and-gun: damage pays by how fast the runner is moving
            gsp = np.clip(np.hypot(s[:, 3], s[:, 4]) / 320.0, 0.0, 1.5)
            self.stats["gun"][0] += float(dealt[self.gun].sum())
            dealt = np.where(self.gun, dealt * gsp, dealt)
        reward += self.dmg_reward * (dealt - self.dmg_taken_w * taken)   # damage taken against damage dealt
        if high_ is not None:                                # (HIGH_PAY) a hit from above is worth more to both, one from below less
            reward += self.dmg_reward * (high_[0] - self.dmg_taken_w * high_[1])
        if STYLE_P > 0:                                      # playing styles: his weapon, at its distance (see STYLES)
            live = (pkind == NORMAL) & (self.script == 0) & (self.hp > 0) & (self.run_k < 0)
            sw = STYLE_W[self.style]
            mine = live & (sw >= 0) & (self.weapon == sw)
            d_ = np.linalg.norm(self.known - s[:, :3], axis=1)
            seen = live & self.visible
            inb = mine & seen & (d_ > STYLE_LO[self.style]) & (d_ < STYLE_HI[self.style])
            reward += STYLE_DMG * self.dmg_reward * np.where(mine, dealt, 0.0) + STYLE_BAND * inb * (DT / 60.0)
            st_ = self.stats["style"]
            np.add.at(st_[:, 0], self.style[live], 1)
            np.add.at(st_[:, 1], self.style[mine], 1)
            np.add.at(st_[:, 2], self.style[seen], 1)
            np.add.at(st_[:, 3], self.style[inb], 1)
            np.add.at(st_[:, 4], self.style[seen], d_[seen])
            np.add.at(st_[:, 5], self.style[live], dealt[live])
            np.add.at(st_[:, 6], self.style[mine], dealt[mine])
            np.add.at(st_[:, 7], self.style[live], self.has[live][:, [RL, RG, LG]].sum(1))
        self.dmg_life += dealt
        hitby = (attacker >= 0) & (attacker != ar) & (dmg_taken > 0)
        if self.flinch_on and hitby.any():                  # a hit throws the aim off at once, and for a moment after
            add = np.minimum(FLINCH_MAX, FLINCH_PER_DMG * dmg_taken) * hitby * (self.script == 0)
            self.flinch = np.minimum(FLINCH_MAX, self.flinch + add).astype(np.float32)
            self.percept = (self.percept + add[:, None] * self.rng.normal(0, 1, (n, 2))).astype(np.float32)
        ang = np.arctan2(s[opp_all, 1] - s[:, 1], s[opp_all, 0] - s[:, 0]) - np.radians(self.yaw)
        self.fb = np.stack([np.minimum(dealt / 100.0, 2.0), np.minimum(dmg_taken / 100.0, 2.0),
                            np.sin(ang) * hitby, np.cos(ang) * hitby], 1).astype(np.float32)

        # items: pickups, respawns, decay above 100
        self.item_t = np.maximum(0.0, self.item_t - DT)
        self.contest_t = np.where(self.contest_t > 0, self.contest_t - DT, -1.0).astype(np.float32)
        if self.item_up_t is None:
            self.item_up_t = np.zeros_like(self.item_t)
        self.item_up_t = np.where(self.item_up, self.item_up_t + DT, 0.0).astype(np.float32)
        was_up_ = self.item_up.copy()
        self.item_up |= self.item_t <= 0
        for m_, k_ in zip(*np.nonzero(self.item_up & ~was_up_)):      # an item came back: heard within earshot
            self.note_respawn(int(k_), np.arange(self.n)[np.arange(self.n) // (self._others_arr().shape[1] + 1) == m_])
        for k_, id_ in enumerate(self.big_ids):
            if id_ >= 0:
                self.stats["big_up"][k_] += int(self.item_up[:, id_].sum())
        self.stats["big_frames"] += self.item_up.shape[0]
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
                if self.kind[m] != NORMAL and kind in ("wp", "am", "pack") and self.run_k[i] < 0:
                    continue                                  # aim / drill / movement rounds: no weapons or ammo (item runs: everything)
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
                    had_wp = bool(self.has[i, val])
                    self.has[i, val] = True
                    self.ammo[i, val] = min(AMMO_MAX[val], self.ammo[i, val] + cap)
                    took = True
                    self.stats["pick_wp"] += 1
                    self.stats["pick_wpnew"] += int(not had_wp)
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
                    self.note_take(int(i), int(it))          # (N_V02: when he last took it; who heard or saw a big one taken)
                    if WAY_MEASURE and int(it) in self.route_item:
                        self._way_trip(int(i), self.route_item.index(int(it)))
                own_ = bool(self.jrun[i]) and it == self.jrun_it[i]    # (a jump run: his target stays for the other seats' tries)
                if took and lab in ("MH", "RA") and not own_:
                    k_ = 0 if lab == "MH" else 1
                    self.note_pickup(int(i), k_)
                    self.stats["big_wait"][k_] += float(self.item_up_t[m, it])
                    self.stats["big_taken"][k_] += 1
                new_wp = took and kind == "wp" and not had_wp
                if took and kind == "wp" and not self.first_wp[i]:
                    self.first_wp[i] = True
                    self.stats["first_wp"] += np.array([float(self.life_t[i]), 1.0])
                if took and self.items_room[i]:              # the items room: each pickup counts, and he can always take the next
                    reward[i] += ITEMS_ROOM_REWARD
                    r_long[i] += ITEMS_ROOM_REWARD
                    self.hp[i], self.armor[i] = 100.0, 0.0
                    self.stats["lab_items"][0 if lab == "MH" else 1] += 1
                if took:
                    # health and armor by the points gained; a weapon he did not have counts as 25 points, one he
                    # has already (ammo) as nothing, so standing on a weapon's spot earns nothing
                    reward[i] += self.item_reward * (gain if kind in ("hp", "ar") else 25.0 if new_wp else 0.0) / 100.0
                    r_long[i] += self.item_reward * (gain if kind in ("hp", "ar") else 25.0 if new_wp else 0.0) / 100.0
                    want_ = lab if lab in ("MH", "RA") else WEAPONS[int(val)].upper() if kind == "wp" else ""
                    if lab == "YA" and it in self.route_item:
                        want_ = self.route_goal[self.route_item.index(it)]    # YA or YA2
                    if want_ in INTENTS and self.intent[i] == INTENTS.index(want_) and not self.intent_done[i]:
                        self.intent_done[i] = True                       # the trip he chose is complete
                        self.stats["intent_trips"][1] += 1
                        self.stats["intent_reach"] += float(self.intent_t[i])
                        if WAYS and self.script[i] == 0 and bool(self._counted(i)):
                            self.stats["way_done"][self.way[i]] += 1     # ... by the way he was on
                    if lab in ("MH", "RA") and self.item_loss > 0:       # the others lose a share: it was theirs to take
                        for o_ in self._mates(i):
                            if self.hp[o_] > 0 and self.run_k[o_] < 0:      # (not in an item run: there everybody is alone)
                                reward[o_] -= self.item_loss * self.item_reward * gain / 100.0
                                r_long[o_] -= self.item_loss * self.item_reward * gain / 100.0
                    if self.contest_t[m] > 0 and it == self.contest_it[m]:    # the item the round began as a race for
                        self.stats["contest_taken"] += int(self.script[i] == 0)
                        self.contest_t[m] = -1.0
                    if not own_:
                        self.item_up[m, it] = False
                        self.item_t[m, it] = resp
        self.hp = np.where(self.hp > 100, np.maximum(100.0, self.hp - DT), self.hp)
        self.armor = np.where(self.armor > 100, np.maximum(100.0, self.armor - DT), self.armor)
        if self.item_seek > 0 and self.route is not None:
            # Going for the items pays as he goes: seconds of travel gained toward the nearest big item that is lying
            # there and that he can use (mega below 200 health, red armor below 200 armor, a weapon he does not have).
            # Only steady movement counts: a jump in the figure (item taken, death, teleporter) pays nothing.
            R_ = self.route
            node = R_.locate(s[:, :3])
            off_ = np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0
            up_ = self.item_up[np.arange(n) // (self._others_arr().shape[1] + 1)]
            phi = np.full(n, 15.0, np.float32)
            for gi, lab_ in enumerate(self.route_goal):
                use = up_[:, self.route_item[gi]] & ((self.hp < 200) if lab_ == "MH" else (self.armor < 200) if lab_ == "RA"
                                                    else ~self.has[:, WEAPONS.index(lab_.lower())])
                phi = np.where(use, np.minimum(phi, R_.T[gi, node] + off_), phi)
            gain = self.seek_phi - phi
            reward += self.item_seek * np.where(np.abs(gain) < 0.4, gain, 0.0) * (self.script == 0) * (self.hp > 0)
            r_long += self.item_seek * np.where(np.abs(gain) < 0.4, gain, 0.0) * (self.script == 0) * (self.hp > 0)
            self.seek_phi = phi.astype(np.float32)
        if WAY_MEASURE:                                      # his path since the route item he took last: a point every WT_EVERY frames
            self.wt_tick += 1
            on_ = (self.wt_from >= 0) & (self.hp > 0)
            self.wt_t = np.where(on_, self.wt_t + DT, self.wt_t).astype(np.float32)
            if self.wt_tick % WT_EVERY == 0:
                w_ = np.nonzero(on_ & (self.wt_n < WT_MAX))[0]
                self.wt_pts[w_, self.wt_n[w_]] = s[w_, :3]
                self.wt_n[w_] += 1
        if self.route is not None:
            # The chosen way pays as he goes (see INTENTS): seconds of it gained, while the item is up or comes up before
            # he can be there. Only steady movement counts; a changed intention starts a new count.
            R_ = self.route
            node = R_.locate(s[:, :3])
            gi_ = self._trip_goal(self.intent, node)
            alt_ = self._alt()
            for m_, X_ in alt_:                              # (a jump run, or jumps open in games: the ways with those jumps)
                gi_[m_] = self._trip_goal(self.intent[m_], node[m_], X_, who=np.nonzero(m_)[0])
            valid = gi_ >= 0
            g_ = np.maximum(gi_, 0)
            t_ = R_.T[g_, node]
            for m_, X_ in alt_:
                t_ = np.where(m_, X_.T[g_, node], t_)
            tb_ = t_                                         # (the shortest set's seconds)
            if WAYS:                                         # his way: the seconds to go by the set he chose
                t_ = self._on_way(g_, node, tb_)[0]
            phi = np.where(valid, t_ + np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0, 0.0)
            grp = np.arange(n) // (self._others_arr().shape[1] + 1)
            it_ = np.array(self.route_item)[np.minimum(g_, len(self.route_item) - 1)]     # (a holding place's row is no item's: "soon" below)
            soon = self.item_up[grp, it_] | (self.item_t[grp, it_] < phi + 5.0) | (self.intent >= EN_INTENT)
            gone_before = self.intent_gone.copy()
            self.intent_gone = valid & ~soon & (self.intent > 0)
            if FIGHT_TARGET:                                 # the enemy as the target: reached when he is in view, given up when
                en_ = self.intent == EN_INTENT               # nothing is known of him any more
                self.intent_done = self.intent_done | (en_ & np.asarray(self.visible, bool)[:len(en_)])
                self.intent_gone = self.intent_gone | (en_ & ~valid)
                self.stats["en_frames"] += np.array([(en_ & (self.script == 0) & (self.hp > 0)).sum(), (en_ & self.legs_on).sum(),
                                                     (en_ & np.asarray(self.visible, bool)[:len(en_)] & (self.script == 0)).sum()], np.float64)
            if self.hold_n:                                  # a holding place as the target (TARGETS): reached where he stands at it,
                hd_ = self.intent >= HOLD_INTENT             # given up where no way leads to it
                at_, new_ = self.note_holds()
                self.intent_gone = self.intent_gone | (hd_ & (~valid | (t_ >= 1e8)))
                up_ = hd_ & (self.script == 0) & (self.hp > 0)
                new_ = new_ & up_
                self.stats["intent_trips"][1] += int(new_.sum())
                if WAYS:                                     # ... by the way he was on
                    self.stats["way_done"] += np.bincount(self.way[new_ & self._counted(ar)], minlength=N_WAYS)
                self.stats["intent_reach"] += float(self.intent_t[new_].sum())
                self.stats["hold_frames"] += np.array([up_.sum(), (up_ & self.legs_on).sum(), (up_ & at_).sum(),
                                                       (up_ & np.asarray(self.visible, bool)[:len(up_)]).sum(), new_.sum(),
                                                       np.hypot(s[:, 3], s[:, 4])[up_ & ~at_].sum()], np.float64)
            if WAYS and self.way_field is not None:          # (see WAYS, "the pay")
                off_ = np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0
                p3_ = np.stack([np.where(valid, self._on_way(g_, node, tb_, w=np.full(n, k_, np.int64))[0] + off_, 0.0) for k_ in range(N_WAYS)], 1)
                self.way_phi0 = np.where(self.intent_changed[:, None], np.maximum(p3_, 1.0), self.way_phi0).astype(np.float32)
                sw_ = (self.way != self.way_was) & ~self.intent_changed & valid & ~in_run     # the way alone changed: the trip goes on, on the new set's scale
                if sw_.any():
                    new0_ = self.way_phi0[ar, self.way]
                    self.intent_best = np.where(sw_, np.minimum(self.intent_best * new0_ / np.maximum(self.intent_phi0, 1e-6) * (1.0 - 1e-5), phi),
                                                self.intent_best).astype(np.float32)      # (a hair less: rounding must never pay, however often he flips)
                    self.intent_phi0 = np.where(sw_, new0_, self.intent_phi0).astype(np.float32)
                    self.stats["way_changes"] += int((sw_ & (self.script == 0) & (self.hp > 0) & self._counted(ar)).sum())
                on_ = valid & (t_ < 1e8) & (self.script == 0) & (self.hp > 0) & ~in_run & self._counted(ar)
                self.stats["way_frames"][:N_WAYS] += np.bincount(self.way[on_], minlength=N_WAYS)
                w_ = np.nonzero(on_ & (self.way > 0))[0]
                self.stats["way_frames"][N_WAYS] += int(self.way_field.wdiff[self.way[w_] - 1, g_[w_], node[w_]].sum())
            self.intent_phi0 = np.where(self.intent_changed, np.maximum(phi, 1.0), self.intent_phi0).astype(np.float32)
            # Only ground never reached before on this trip pays (the least seconds-to-go so far). Until 2026-10-08 every
            # frame's change paid unless it was a jump of 0.4 s or more: a fall cost nothing and the walk back was paid
            # again (at Blood Run's red armor four falls in a minute paid 2.9 times the armor), and backing off from a goal
            # chosen close by ran the trip's balance far below zero. Now a trip pays at most its item and never less than 0.
            self.intent_best = np.where(self.intent_changed, phi, self.intent_best).astype(np.float32)
            gain = np.maximum(0.0, self.intent_best - phi)
            self.intent_best = np.minimum(self.intent_best, phi).astype(np.float32)
            pay = valid & soon & ~self.intent_changed & ~self.intent_done & (self.script == 0) & (self.hp > 0)
            if self.hold_n:                                  # (nothing is paid for the way to a holding place, nor for speed on it)
                pay = pay & (self.intent < HOLD_INTENT)
            worth = self.item_reward * np.array(INTENT_VALUE, np.float32)[self.intent]      # the whole way is worth the pickup
            # a trip given up pays nothing (v9); one whose item another player took is not given up
            claw = self.intent_changed & (prev_int > 0) & ~prev_done & ~in_run & ~gone_before[:len(prev_int)]
            reward -= self.intent_paid * claw
            if WAYS:                                         # (counted: what trips given up gave back; below: what his ways paid)
                self.stats["way_pay"][1] += float((self.intent_paid * claw)[self._counted(ar)].sum())
            fast_ = np.where(self.intent_paid > 0, self.intent_fast, 0.0)      # the part of it that was pay for speed (a new life
            r_long -= (self.intent_paid - fast_) * claw                        # put intent_paid to nothing: _fresh)
            self.intent_fast = np.where(claw | self.intent_done, 0.0, fast_).astype(np.float32)
            self.intent_paid = np.where(claw | self.intent_done, 0.0, self.intent_paid).astype(np.float32)
            pay_now = self.intent_seek * worth * gain / self.intent_phi0 * pay
            reward += pay_now - INTENT_SWITCH * (self.intent_changed & (prev_int > 0) & ~in_run)
            r_long += pay_now - INTENT_SWITCH * (self.intent_changed & (prev_int > 0) & ~in_run)
            self.intent_paid = (self.intent_paid + pay_now).astype(np.float32)
            if WAYS:
                self.stats["way_pay"][0] += float(pay_now[self._counted(ar)].sum())
            if self.hold_n:                                  # (leaving a holding place costs nothing, as leaving "nothing")
                free_ = INTENT_SWITCH * (self.intent_changed & (prev_int >= HOLD_INTENT) & ~in_run)
                reward += free_
                r_long += free_
            if PACE_PAY or SPEED_PAY or SPEED_PAY_RUN:       # faster than running pace on his way, nobody about (see PACE_PAY, SPEED_PAY)
                if getattr(self, "pace_g", None) is None or len(self.pace_g) != n:
                    self.pace_g = np.zeros(n, np.float32)    # new ground gained lately (seconds of the way; 0.5 = running pace)
                self.pace_g = (0.95 * self.pace_g + np.where(pay, gain, 0.0)).astype(np.float32)
                sp_h = np.hypot(s[:, 3], s[:, 4])
                trip = pay & ~in_run & ~self.visible & (self.seen_t > 1.5)
                fast = trip & (self.pace_g > 0.3)
                pace_now = PACE_PAY * DT * np.clip(sp_h / 320.0 - 1.0, 0.0, 1.0) * fast
                if SPEED_PAY or SPEED_PAY_RUN:               # per stretch of new ground, by the speed he covers it at (see SPEED_PAY)
                    new_ = np.minimum(np.where(pay, gain, 0.0), 3.0 * DT)      # (a teleporter's leap counts as three frames' running)
                    sp_f = (320.0 / SPEED_HI) * new_ * np.clip((sp_h - SPEED_LO) / (SPEED_HI - SPEED_LO), 0.0, 1.0)
                    run_ok = in_run & (self.script == 0) & (self.hp > 0)
                    pace_now = pace_now + SPEED_PAY * sp_f * trip
                    reward += SPEED_PAY_RUN * sp_f * run_ok
                    self.stats["speed_pay"] += float((SPEED_PAY * sp_f * trip).sum())
                    self.stats["speed_pay_run"] += float((SPEED_PAY_RUN * sp_f * run_ok).sum())
                    self.stats["speed_frames"] += int(((sp_f > 0) & (trip | run_ok)).sum())
                reward += pace_now
                self.intent_paid = (self.intent_paid + pace_now).astype(np.float32)     # a trip given up gives it back
                self.intent_fast = (self.intent_fast + pace_now).astype(np.float32)     # ... as pay for speed, not the game's
                self.stats["pace_pay"] += float(pace_now.sum())
                self.stats["pace_frames"] += int((fast & (sp_h > 320.0)).sum())
                self.stats["trip_frames"] += int(trip.sum())
                self.stats["trip_speed"] += float(sp_h[trip].sum())
            run = in_run & (self.script == 0)
            if run.any():                                   # item runs: the way gained against the clock, a bonus on taking it
                alive = run & (self.hp > 0)
                reward += RUN_SCALE * (np.where(pay, gain, 0.0) - DT) * alive
                r_long += RUN_SCALE * (np.where(pay, gain, 0.0) - DT) * alive
                sp_ = np.hypot(s[:, 3], s[:, 4])
                self.stats["move_frames"] += int(alive.sum())
                self.stats["move_speed"] += float(sp_[alive].sum())
                self.stats["move_fast"] += int(((sp_ > 330) & (s[:, 6] < 0.5) & alive).sum())
                arr = run & self.intent_done & (self.run_k > 0) & (self.intent == self.run_k)     # (the pickup may be booked after this block: no "since last frame" test)
                gone = run & ~arr & (self.run_k > 0) & (self.intent == self.run_k) & valid & ~soon & ~self.intent_done
                self.jrun_new[:] = False
                jr = np.nonzero(alive & self.jrun)[0]       # jump runs: over the gap, fallen short of it, or out of time
                if len(jr):
                    self.stats["jump_frames"] += len(jr)
                    self.jrun_t[jr] -= DT
                    kk_ = self.jrun_k[jr]
                    A_, B_, p_ = self.jump_a[kk_], self.jump_b[kk_], s[jr, :3]
                    self.jrun_paid[jr] += (pay_now[jr] + RUN_SCALE * np.where(pay[jr], gain[jr], 0.0)).astype(np.float32)
                    self.jrun_edge[jr] |= (np.hypot(p_[:, 0] - A_[:, 0], p_[:, 1] - A_[:, 1]) < 120.0) & (np.abs(p_[:, 2] - A_[:, 2]) < 64.0)
                    landed_ = (s[jr, 6] > 0.5) | ((prev[jr, 5] < 0.0) & (s[jr, 5] > 0.0))   # on the floor, or touched it and jumped again inside the frame
                    ov_ = ~self.jrun_over[jr] & self.jrun_edge[jr] & (np.linalg.norm(p_ - B_, axis=1) < 110.0) & (landed_ | arr[jr])
                    self.jrun_over[jr[ov_]] = True
                    past_ = ov_ | ((np.linalg.norm(p_ - B_, axis=1) < 110.0) & landed_)     # landed at the jump's landing, over it or
                    self.jrun_past[jr[past_]] = True                                        # round it: from here the plain ways with
                    self.jrun_f[jr[past_]] = 0                                              # the pros' jumps, to the item
                    np.add.at(self.stats["jump_over"], np.minimum(kk_[ov_ & self._counted(jr)], 63), 1)
                    at_gap_ = np.hypot(p_[:, 0] - B_[:, 0], p_[:, 1] - B_[:, 1]) < np.hypot(A_[:, 0] - B_[:, 0], A_[:, 1] - B_[:, 1]) + 150.0
                    short_ = self.jrun_edge[jr] & ~self.jrun_over[jr] & at_gap_ & (p_[:, 2] < np.minimum(A_[:, 2], B_[:, 2]) - 90.0)
                    np.add.at(self.stats["jump_short"], np.minimum(kk_[short_ & self._counted(jr)], 63), 1)
                    for i in jr[(short_ | (self.jrun_t[jr] <= 0)) & ~arr[jr]]:
                        reward[i] -= float(self.jrun_paid[i])    # a try that ends without the item gives back what its way paid
                        r_long[i] -= float(self.jrun_paid[i])
                        self._jump_place(int(i))
                for i in np.nonzero(arr | gone | (run & (self.run_k == 0)))[0]:
                    if self.jrun_new[i]:
                        continue
                    if arr[i]:
                        reward[i] += RUN_ARRIVE
                        r_long[i] += RUN_ARRIVE
                        self.stats["move_arrive"] += 1
                    if self.jrun[i]:
                        self._jump_place(int(i))            # the next try
                    else:
                        self._run_pick(int(i))
            self.intent_phi = phi.astype(np.float32)

        if STACK_PAY or STACK_WPN or STACK_BARE or STACK_LOW:   # pay for the stack he keeps (see STACK_PAY)
            on = (pkind == NORMAL) & (self.hp > 0) & (self.script == 0) & (self.run_k < 0)
            big = self.has[:, [RL, LG, RG]].sum(1)
            over = (np.clip(self.hp - 100.0, 0.0, 100.0) + np.clip(self.armor, 0.0, 100.0)) / 200.0
            if getattr(self, "bare_t", None) is None or len(self.bare_t) != len(self.hp):
                self.bare_t = np.zeros(len(self.hp), np.float32)       # seconds of this life without a big weapon
            self.bare_t = np.where(on & (big == 0), self.bare_t + DT, 0.0).astype(np.float32)
            low = np.clip((STACK_LOW_AT - (self.hp + self.armor)) / STACK_LOW_AT, 0.0, 1.0)
            pay = (STACK_PAY * over + STACK_WPN * big / 3.0
                   - STACK_BARE * np.minimum(STACK_BARE_MAX, self.bare_t / STACK_BARE_RAMP)
                   - STACK_LOW * low) * (DT / 60.0)
            reward += np.where(on, pay, 0.0)
            r_long += np.where(on, pay, 0.0)
            self.stats["stack_frames"] += int(on.sum())
            self.stats["stack_over"] += float(over[on].sum())
            self.stats["stack_big"] += float(big[on].sum())
            self.stats["stack_bare"] += int((on & (big == 0)).sum())
            self.stats["stack_low"] += int((on & (low > 0)).sum())
            self.stats["stack_cost"] += float((STACK_BARE * np.minimum(STACK_BARE_MAX, self.bare_t / STACK_BARE_RAMP) + STACK_LOW * low)[on].sum()) * DT / 60.0

        if (self.drop_w >= 0).any():                         # weapons that dead players left (see DROPS)
            self._drops_step(reward)

        if KNOW_PAY:                                         # pay for knowing where the enemy is (see KNOW_PAY)
            on = (pkind == NORMAL) & (self.hp > 0) & (self.script == 0) & (self.run_k < 0)
            kn = self._knowledge()
            reward += np.where(on, KNOW_PAY * kn * (DT / 60.0), 0.0)
            r_long += np.where(on, KNOW_PAY * kn * (DT / 60.0), 0.0)
            self.stats["know"] += float(kn[on].sum())
            self.stats["know_frames"] += int(on.sum())

        # deaths, frags, respawns
        done = np.zeros(n, bool)                            # end of the round (memory and returns reset here only)
        died = np.zeros(n, bool)
        events = []
        dead = np.nonzero(self.hp <= 0)[0]
        for v in dead:
            k = st["killer"][v] if st["killer"][v] >= 0 else attacker[v]
            gm_ = GAME_ON and bool(self.game[self._match_of(v)])    # a whole game or a late round (GAME_P): the game's score,
            if gm_:                                                 # and with WIN_PAY the frag is paid by the game (_game_step)
                self.g_flat[v] -= 1.0
                if k >= 0 and k != v:
                    self.g_flat[k] += 1.0
                else:
                    self.frags_r[v] -= 1                    # (his own hand or the world: a point off him)
            if not (gm_ and WIN_PAY):
                reward[v] -= 1.0
            if k >= 0 and k != v and self.cf_side[k] and self.cf_side[v] and self.cf_side[k] != self.cf_side[v]:
                self.stats["cf_stack_kills" if self.cf_side[k] == 1 else "cf_plain_kills"] += 1
            if CLAW_ON_DEATH and self.intent[v] > 0 and not self.intent_done[v]:
                reward[v] -= float(self.intent_paid[v])      # the trip he died on pays nothing (v9; off since 2026-10-07)
                r_long[v] -= float(self.intent_paid[v] - min(self.intent_fast[v], self.intent_paid[v]))
            died[v] = True
            if STYLE_P > 0 and self.script[v] == 0:
                self.stats["style"][self.style[v], 9] += 1
            if k >= 0 and k != v:
                if STYLE_P > 0 and self.script[k] == 0:
                    self.stats["style"][self.style[k], 8] += 1
                if not (gm_ and WIN_PAY):
                    reward[k] += 1.0
                if DROPS:
                    self._drop_weapon(int(v))
                self.frags_r[k] += 1
                self.stats["frags"] += 1
                self.stats[WEAPONS[kill_w.get(v, 0)] + "_frags"] += int(self.script[k] == 0)
                if self.script[v] >= 2:                     # the scripted fighter or the item runner
                    self.stats["frags_vs_bot"] += 1
                    self.stats["vs_persona"][0, self.sc_persona[v]] += 1
                elif self.script[v] == 1:
                    self.stats["target_kills"] += 1
                if self.script[k] >= 2:
                    self.stats["bot_frags"] += 1
                    self.stats["sc_frags_w"][int(kill_w.get(v, 0))] += 1
                    self.stats["vs_persona"][1, self.sc_persona[k]] += 1
                    if self.script[k] == 3 and self.sc_persona[k] == HOLDER and self.rng.random() < HOLD_HUNT_P:
                        self.hunt_t[k], self.x_goal[k] = HOLD_HUNT, -1
            else:
                self.stats["suicides"] += 1
            events.append(dict(victim=int(v), killer=int(k), weapon=int(kill_w.get(v, -1))))
            self.note_death(int(v), int(k))
        for v in dead:
            if self.lab is not None:
                self._lab_respawn(int(v))
                continue
            if self.jrun[v]:                                # (a jump run: the next try)
                self._jump_place(int(v))
                continue
            self._spawn(int(v), avoid=s[v ^ 1, :3], close=True if self.kind[v // 2] in (AIM, DRILL) else None)
            if self.goal[v] >= 0:
                self._new_goal(int(v))
        lo, hi = self.w.bounds()
        out = np.nonzero(s[:, 2] < lo[2] - 64)[0]            # fell out of the map: a suicide
        for v in out:
            if not died[v]:
                gm_ = GAME_ON and bool(self.game[self._match_of(v)])
                if gm_:                                      # (a whole game: a point off him, and the death is an event)
                    self.g_flat[v] -= 1.0
                    self.frags_r[v] -= 1
                    events.append(dict(victim=int(v), killer=-1, weapon=-1))
                if not (gm_ and WIN_PAY):
                    reward[v] -= 1.0
                if CLAW_ON_DEATH and self.intent[v] > 0 and not self.intent_done[v]:
                    reward[v] -= float(self.intent_paid[v])
                    r_long[v] -= float(self.intent_paid[v] - min(self.intent_fast[v], self.intent_paid[v]))
                died[v] = True
                self.stats["suicides"] += 1
                self._spawn(int(v), avoid=s[v ^ 1, :3])
                if self.jrun[v]:                            # (a jump run: the next try)
                    self._jump_place(int(v))
                if self.goal[v] >= 0:
                    self._new_goal(int(v))
        # short rounds (curriculum): restart both players near each other every ~round_len seconds
        self.round_t += DT
        if GAME_ON:                                          # whole games and late rounds: their clock, and the frame's pay by the game
            self._game_step(reward)
        cf_ = np.nonzero(self.cf_t > 0)[0]
        if len(cf_):
            self.cf_t[cf_] -= DT
            for m_ in cf_[self.cf_t[cf_] <= 0]:
                self._collect_to_fight(int(m_))
        klen = np.where(self.kind == NORMAL, self.round_len, np.where(self.kind == MOVE, self.move_len, 15.0))
        if self.fixed_kind is not None:
            klen = np.full(self.M, self.round_len)
        ends = np.nonzero(self.round_t > klen * self.round_fac)[0]
        if GAME_ON:                                          # (a whole game ends at its limit, to the frame)
            ends = np.nonzero(np.where(self.game > 0, self.g_tick >= GAME_FRAMES, self.round_t > klen * self.round_fac))[0]
        if self.lab is not None:                            # lab rooms have exact lengths
            ends = np.nonzero(self.round_t >= self.lab_len)[0]
            am = np.repeat(self.arena > 0, 2)
            if am.any():
                self.stats["arena"][1] += float(am.sum())
                self.stats["arena"][2] += float(np.hypot(s[am, 3], s[am, 4]).sum())
                self.stats["arena"][3] += float(self.visible[am].sum())
                self.stats["arena"][4] += float(dealt[am].sum())
                self.stats["arena"][5] += float((np.hypot(s[am, 3], s[am, 4]) < 50).sum())
                self.stats["arena"][6] += float((np.abs(self.pitch[am]) > 40).sum())
                self.stats["arena"][7] += float(self.duck[am].sum())
                self.stats["zoom_frames"] += float(self.zoom[am].sum())
                self.stats["arena"][0] += float(sum(1 for e in events if am[e["victim"]] and e["killer"] >= 0 and e["killer"] != e["victim"]))
            self.stats["lab_items"][2] += float(self.items_room.sum())
        contest_m = []
        for m in ends:
            if GAME_ON and self.game[m]:                     # a whole game or a late round is over: its result into the counters
                self._game_end(int(m))
            self.round_fac[m] = self.rng.uniform(0.67, 1.33)
            self.drop_w[m] = -1
            self.run_k[self._seats(int(m))] = -1
            self.jrun[self._seats(int(m))] = False
            self.cf_side[self._seats(int(m))] = 0
            self.cf_t[m] = -1.0
            q_ = self._item_run_start(int(m))                # an item run in a share of the rounds (RUN_LEN)
            if q_ is not None:
                self.round_t[m] = 0.0
                done[q_] = True
                continue
            if GAME_ON and self._game_draw(int(m)):          # a whole game or a late round, in their share of the games' time
                done[self._seats(int(m))] = True
                continue
            self.round_t[m] = 0.0
            a_, b_ = 2 * m, 2 * m + 1
            if self.lab is not None:
                self._lab_round(int(m))
                done[a_] = done[b_] = True
                continue
            # kind_p is the share of playing TIME per kind: normal rounds last much longer than the others, so
            # the chance of starting each kind is weighted by 1 / its length
            wts = np.asarray(self.kind_p, np.float64) / np.array([self.round_len, 15.0, 15.0, self.move_len])
            if GAME_ON and self._game_ok():                  # (the whole games' and late rounds' part of the games' time was drawn above)
                wts[0] *= max(0.0, 1.0 - GAME_P - LATE_P)
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
                self.drill_mix[m] = self.rng.random() < self.drill_mix_p
            elif kd == AIM:
                self.mode[m] = int(self.rng.choice(self.aim_weapons))
                self.script[b_] = 1
            elif kd == NORMAL and self.route is not None and self.rng.random() < self.runner_p:
                self.script[b_] = 3                          # the item runner, with the all-round fighter's aim
                self.sc_persona[b_] = 0
                if TRICKS and TRICK_P.sum() > 0 and self.rng.random() < TRICK_P.sum():   # ... or one of the three in his place
                    self.sc_persona[b_] = (HOLDER, LOBBER, WATCHER)[int(self.rng.choice(3, p=TRICK_P / TRICK_P.sum()))]   # (until 2026-10-10
                    self.hold_ahead[b_] = self.sc_persona[b_] == HOLDER and self.rng.random() < HOLD_STACK              # only in the yard's rounds)
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
                self._spawn(b_, avoid=self.w.state()[a_, :3], close=0.0 if kd == MOVE else True if kd == DRILL else None)
            if kd == MOVE:
                self._new_goal(a_)
                self._new_goal(b_)
            self.item_up[m] = True
            self.item_t[m] = 0.0
            self.contest_t[m] = -1.0
            if CONTEST_P > 0 and kd == NORMAL and self.fixed_kind is None and self.rng.random() < CONTEST_P:
                contest_m.append(int(m))
        if done.any():                                      # a new round: nothing is known
            self.it_t[done], self.e_got[done], self.e_life[done] = 99.0, 0.0, 99.0
            self.bel_t[done] = 99.0
            self._v02_round(done)
        for m_ in contest_m:                                 # ... but for the rounds that start as a race for a big item
            self._contest_start(m_)
        if GAME_ON and self._late_m:                         # ... and for the late rounds: a drawn score, stacks, item clocks
            for m_ in self._late_m:
                self._late_start(m_)
            self._late_m = []
        if len(dead) or len(out) or len(ends) or self._replaced:
            self.state = s = self.w.state()
            self._replaced = False

        # senses: sight (line of sight + field of view) and hearing (rough position)
        eye = self._eye(s)
        opp = ar ^ 1
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        yr, pr = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        infov = (to * fdir).sum(1) / dist > self.fov()[2]
        cand = np.nonzero(infov & (dist < 4000))[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = self._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        pkind = np.repeat(self.kind, 2)
        vis &= (pkind != MOVE) & (pkind != SOLO) & ((pkind != COURSE) | self.gun)   # movement / solo / course: no other player
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
            self._note_close(vh, s, to, dist)
        if SURPRISE_MS > 0:                                  # off the crosshair and unexpected: noticed later
            ecc_ = np.degrees(np.arccos(np.clip((to * fdir).sum(1) / dist, -1.0, 1.0)))
            self.acq_extra = np.where(vis & (self.vis_run == 0), surprise_frames(ecc_, self.seen_t), np.where(vis, self.acq_extra, 0))
        self.vis_run = np.where(vis, self.vis_run + 1, 0)
        acq = vis & (self.vis_run >= self._acq_need() + self.acq_extra)
        self.acquired = acq
        self.known[acq] = s[opp[acq], :3]
        if heard.any():
            self.known[heard] = s[opp[heard], :3] + self.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        self.seen_t = np.where(acq | heard, 0.0, self.seen_t + DT)
        self._teach_update()
        info = dict(events=events)
        info["r_long"] = self.r_long.copy()                  # the game's part of this frame's pay, per player
        if LEGS_LAB:                                         # (stage C, part 1) what his legs chose on the frames they carried him, or
            info["legs_lab"], info["legs_held"] = self.legs_lab.copy(), self.legs_wh.copy()      # would have in a withheld stretch
        if GAME_ON:
            info["win_pay"] = self.win_pay.copy()            # (WIN_PAY) the frame's pay by the game, per player
        self._hand_step(done, died)                          # the weapon in his hand with nobody in view: the counters, always;
        if HAND_TEACH:                                       # (HAND_TEACH) the pros' shares as the target of his next reading of
            info["hand_lab"] = self.hand_lab.copy()          # the weapon key, for the trainer's --hand-teach
        info["aux"] = self.aux(st, fall, events, died)      # (stage B, part 1) the truth the trainer's --aux lesson is made of
        return self.observe(), reward.astype(np.float32), done, info

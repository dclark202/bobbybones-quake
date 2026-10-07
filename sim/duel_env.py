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
W_RULE_RL, W_RULE_LG, W_RULE_RG = (100.0, 450.0), 700.0, 600.0
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
KEY_RATE, KEY_BURST = 4.0, 10.0
# (2026-10-05, later) The budget is the hand's stamina: a burst of up to KEY_BURST key actions in quick succession,
# refilled at KEY_RATE a second, so that after a burst the hand is slow until it has recovered.
# The left hand also decides only every KEY_EVERY frames (ten times a second): what the keys and the weapon choice
# should be is read from the network then and held in between. The mouse and the fire button stay at 40 a second.
KEY_EVERY = 4
# The right hand on the mouse: index finger = fire, middle finger = zoom (held). The same rule: a finger that has
# just acted cannot act again for this many frames (a click is a press and a release: at most about six a second).
MOUSE_HOLD = np.array([4, 6], np.int64)                # fire 100 ms (at most five clicks a second), zoom 150 ms
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
PERSONAS = ("allround", "sniper", "rusher", "tracker", "dodger", "stander", "jumper", "spammer")
P_GAIN = np.array([0.4, 0.4, 0.4, 0.45, 0.4, 0.15, 0.3, 0.3], np.float32)
P_NOISE = np.array([0.3, 0.3, 0.5, 0.3, 0.3, 0.6, 1.5, 1.5], np.float32)
P_NEAR = np.array([200, 700, 0, 250, 300, 0, 0, 200], np.float32)
P_FAR = np.array([500, 1200, 0, 550, 600, 1e9, 0, 500], np.float32)
P_WEAPON = np.array([-1, RG, RL, LG, -1, -1, -1, -2], np.int64)
REACT_FRAMES = 2                                       # 50 ms: tracking an enemy already in view lags by this much.
ACQUIRE_FRAMES = 8                                     # 200 ms: an enemy who has just come into view is not reacted to before this
TURN_CAP = 30.0                                        # fastest flick, degrees per frame (1200 deg/s)
MOTOR_NOISE, MOTOR_BASE = 0.10, 0.05                   # hand noise: this share of the view movement, plus a little, per frame (0.14 until 2026-10-06 evening, owner: tune up)
RELOAD_JITTER, RELOAD_JITTER_MAX = 0.05, 0.12          # slow weapons: random extra delay after the reload (mean, max seconds)
DMG_TAKEN_W = 2.0                                      # damage taken (any source) weighs this much against damage dealt
FIRE_TOGGLE_COST = 0.003                               # reward cost each time the fire button changes (holding is free)
LOAD_GUNS = (0, 1, 2, 4, 5, 6, 7)                      # weapons that random loadouts draw from (all but machine gun, gauntlet)
#                                                       older note: default 25 ms (one frame): what a player knows about the opponent lags.
                                                       # Was 6 (150 ms) up to duel_gru_v2; per run: env.react_frames / --react-ms
# (2026-10-05) He reads where the enemy is against his crosshair only this well: a slowly drifting error, in degrees,
# on the direction to an enemy in view (every input that gives that direction carries it). A person judges the
# gap between crosshair and target by eye, not to a hundredth of a degree.
PERCEPT_SIGMA, PERCEPT_TAU = 0.6, 0.15                  # degrees; seconds over which the error drifts (1.0 until 2026-10-06 evening:
                                                       # v8 measured 3.5 deg aim error on a strafing target against the owner's 2.5; owner: tune up)
# (2026-10-05, B-94) Being shot at costs aim: a hit throws his read of the enemy's direction off by FLINCH_PER_DMG
# degrees per point of damage (at most FLINCH_MAX at a time), and the error stays larger while the flinch fades
# (FLINCH_TAU seconds). First values; to be set from players in the reflex test (calm half against the half under fire).
FLINCH_PER_DMG, FLINCH_MAX, FLINCH_TAU = 0.12, 3.0, 0.3
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
INTENTS = ("none", "MH", "RA", "RL", "RG", "LG")
INTENT_EVERY, INTENT_SWITCH = 40, 0.02
# (12:50) A choice holds for INTENT_HOLD seconds unless the item was taken or he died ("none" can be left at any read);
# the way to the chosen item is worth its pickup (INTENT_VALUE x env.item_reward), paid in parts as the way is gained,
# so a whole trip never pays more than the item itself.
INTENT_HOLD = float(os.environ.get("INTENT_HOLD") or 3.0)     # (v11: longer, with a release when the item is gone, see intend)
INTENT_VALUE = (0.0, 1.0, 1.0, 0.25, 0.25, 0.25)
CLAW_ON_DEATH = False                                  # the trip's pay was also taken back when he died on the way: with half the
                                                       # trips ending in death the long ones (mega, red) lost money and he chose the
                                                       # launcher 92% of the time (v9 night, 2026-10-07). Now only a trip given up is clawed back (owner)
ACTION_DIMS = (3, 3, 3, len(TURN), len(PITCH), 2, 1 + NW, 2, 2, 2, len(INTENTS))  # ..., walk, zoom, lift the mouse, intention
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
ROUTE_ITEMS = ("MH", "RA", "RL", "RG", "LG")
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
N_INTENT = 13 + 32
N_V9 = 4 + 12
MAX_CELLS, CELL_SIZE = 16384, 64.0                        # enough cells for the big maps (v9; the table is a file, not weights)
OBS_DIM = OBS_BASE + N_EXTRA + N_FIGHT + N_MEM + N_ROUTE + N_PAD + N_EAR + N_MORE + N_DENSE + N_V9 + N_INTENT
CELL_COLS = None                                           # no learned cell table in the network any more
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


class RouteField:
    """a map's walking graph (sim/build_nav.py) -> seconds to each goal and the next step of the way, from anywhere.
    Plain numpy (the Anaconda Python's scipy is broken): the nearest graph point comes from a table over a grid."""
    CELL = 32.0

    def __init__(self, nav_path, goals, pads=()):
        import heapq
        g = json.load(open(nav_path))
        self.nodes = np.array(g["nodes"], np.float32)
        n = len(self.nodes)
        radj, have = [[] for _ in range(n)], set()
        for a, b, t, kind in g["edges"]:
            d = float(np.linalg.norm(self.nodes[a] - self.nodes[b]))
            radj[b].append((a, 0.1 if kind == "tele" else (d / 320.0 if kind == "walk" else max(t, d / 900.0))))
            have.add((a, b))
        for a, b, t, kind in g["edges"]:                      # flat walking works both ways
            if kind == "walk" and (b, a) not in have and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                radj[a].append((b, float(np.linalg.norm(self.nodes[a] - self.nodes[b])) / 320.0))
        for c_, d_ in pads:                                   # jump pads: from the plate to where it throws him
            dx = np.hypot(self.nodes[:, 0] - c_[0], self.nodes[:, 1] - c_[1])      # (the builder's walkers get thrown off
            on = np.nonzero((dx < 130) & (np.abs(self.nodes[:, 2] - c_[2]) < 48))[0]  # the plate: link from the floor round it)
            land = int(np.linalg.norm(self.nodes - np.asarray(d_, np.float32) + np.array([0, 0, 100.0], np.float32), axis=1).argmin())
            for a_ in on:
                radj[land].append((int(a_), 1.2 + float(dx[a_]) / 320.0))
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

    def _grid(self, nav_path, dims, w):
        """nearest node for every grid cell. Cached beside the walking map, or in $ROUTE_CACHE (the game server's map
        folder is read-only): building it took minutes on a big map (2026-10-06, Blood Run froze the server for the
        duration). Built in two passes: every node claims the cells within 256 units of it, the cells left (outside
        the walkable space) by brute force in chunks."""
        n = len(self.nodes)
        key = "{}x{}x{}_{}_{}".format(dims[0], dims[1], dims[2], n, int(self.CELL))
        paths = [nav_path + ".grid.npz"]
        if os.environ.get("ROUTE_CACHE"):
            paths.insert(0, os.path.join(os.environ["ROUTE_CACHE"], os.path.basename(nav_path) + ".grid.npz"))
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
        base = ((self.nodes - self.lo) / self.CELL).astype(np.int64)
        for s0 in range(0, n, 1024):
            nd = np.arange(s0, min(n, s0 + 1024))
            cells = base[nd][:, None, :] + off[None, :, :]
            ok = ((cells >= 0) & (cells < dims)).all(2)
            ci = np.clip(cells, 0, dims - 1)
            centers = np.stack([cx[0][ci[..., 0]], cx[1][ci[..., 1]], cx[2][ci[..., 2]]], -1)
            d2 = np.where(ok, (((centers - self.nodes[nd][:, None, :]) * w) ** 2).sum(2), np.inf).astype(np.float32).ravel()
            flat = ((ci[..., 0] * dims[1] + ci[..., 1]) * dims[2] + ci[..., 2]).ravel()
            np.minimum.at(bf, flat, d2)
            hit = np.isfinite(d2) & (d2 == bf[flat])
            tf[flat[hit]] = np.repeat(nd, off.shape[0])[hit]
        rest = np.nonzero(tf < 0)[0]
        if len(rest):
            pts = np.stack(np.unravel_index(rest, tuple(dims)), 1)
            P = np.stack([cx[0][pts[:, 0]], cx[1][pts[:, 1]], cx[2][pts[:, 2]]], 1) * w
            nw = self.nodes * w
            for c0 in range(0, len(rest), 512):
                d2 = ((P[c0:c0 + 512, None, :] - nw[None, :, :]) ** 2).sum(2)
                tf[rest[c0:c0 + 512]] = d2.argmin(1)
        table = tf.reshape(tuple(dims)).astype(np.int32)
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
        self.persona_p = np.full(len(PERSONAS), 1.0 / len(PERSONAS))
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
        self.flinch = np.zeros(self.n, np.float32)        # extra error on that direction after being hit, degrees
        ng_ = len(self._mates(0)) + 1                       # players per group
        self.it_t = np.full((self.n, 2), 99.0, np.float32)  # seconds since mega / red armor were last known taken (99 = not known)
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
        self.intent_phi0 = np.ones(self.n, np.float32)      # ... and when the choice was made (the whole way)
        self.intent_live = np.zeros(self.n, bool)           # the head was read this frame
        self.intent_changed = np.zeros(self.n, bool)
        self.intent_new = np.ones(self.n, bool)             # just spawned: read the head at once
        self.intent_done = np.zeros(self.n, bool)           # the chosen item was taken since the choice
        self.int_tick = 0
        self.intent_seek = 0.0                              # reward per second of the chosen way gained
        self.item_loss = 0.5                                # an enemy's mega or red costs this share of its pickup reward
        self.intent_gi = [-1] * len(INTENTS)                # intention -> index into route_goal
        self.route, self.route_goal = None, []              # the ways to the big items (see N_ROUTE)
        if nav and os.path.exists(nav):
            pos_ = {}
            for k_, d_ in enumerate(self.item_def):
                lab_ = d_[4] if d_[4] in ROUTE_ITEMS else (WEAPONS[int(d_[1])].upper() if d_[0] == "wp" else None)
                if lab_ in ROUTE_ITEMS and lab_ not in pos_:
                    pos_[lab_] = self.item_pos[k_]
            self.route_goal = [lab_ for lab_ in ROUTE_ITEMS if lab_ in pos_]
            self.route_item = [next(k_ for k_ in range(self.nI) if np.array_equal(self.item_pos[k_], pos_[lab_]))
                               for lab_ in self.route_goal]
            if self.route_goal:
                self.route = RouteField(nav, [pos_[lab_] for lab_ in self.route_goal],
                                        pads=[(c, d) for k, c, d in spots if k == 0])
                self.intent_gi = [-1] + [self.route_goal.index(lab_) if lab_ in self.route_goal else -1 for lab_ in INTENTS[1:]]
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
                          arena=np.zeros(8),              # frags, player-frames, sum of speed, frames with the enemy in view, damage,
                                                          # frames standing still, frames looking over 40 degrees up or down, crouched frames
                          zoom_frames=0.0, key_asked=0, key_changes=0, key_blocked=0,   # movement-key changes made / refused by the finger limits
                          gun=np.zeros(3),                # run-and-gun: damage dealt, runner frames, sum of runner speed
                          lab_items=np.zeros(3),          # items room: mega pickups, red armor pickups, player-frames
                          switches=0, fire_frames=0, blind_frames=0, play_frames=0, aim_err=0.0, aim_frames=0,
                          on_target=0, move_frames=0, move_arrive=0, move_speed=0.0, move_fast=0,
                          cf_rounds=0, cf_stack_kills=0, cf_plain_kills=0, wrule_frames=0, wrule_agree=0,
                          frags_vs_bot=0, bot_frags=0, target_kills=0, bot_frames=0, aim_round_frames=0,
                          w_dist=np.zeros((3, NW)), dmg_h=0.0, dmg_from_script=0.0,
                          vs_persona=np.zeros((3, len(PERSONAS))), fall_dmg=0.0, duck_frames=0, walk_frames=0)      # rows: frags against, deaths to, frames
        for wn in WEAPONS:
            self.stats[wn + "_shots"] = 0               # shots, ticks or pellets fired
            self.stats[wn + "_shots_vis"] = 0           # ... while the opponent was in view
            self.stats[wn + "_hits"] = 0
            self.stats[wn + "_frags"] = 0
        self.stats["hurt_dmg"], self.stats["void_deaths"] = 0.0, 0
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
        self.pad[i], self.pad_lift[i], self.ear_t[i] = 0.0, 0, 99.0
        self.walk_last[i] = False
        self.e_got[self._mates(i), self._slot(i)] = 0.0     # what the others knew him to have is gone with him
        self.dmg_life[i ^ 1] = 0.0                      # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // 2])
        kind = int(self.kind[i // 2])
        if self.stack_p > 0 and kind == NORMAL and self.script[i] == 0 and self.rng.random() < self.stack_p:
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
        ri = np.nonzero((self.run_k > 0) & (self.script == 0) & (self.hp > 0))[0]
        if not len(ri):
            return
        s = self.state
        pos = s[ri, :3]
        node = R.locate(pos)
        gi = np.array(self.intent_gi)[self.run_k[ri]]
        ok = gi >= 0
        g = np.maximum(gi, 0)
        nx = R.next[g, node]
        tp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[g])
        near = np.hypot(tp[:, 0] - pos[:, 0], tp[:, 1] - pos[:, 1]) < 48.0
        nx2 = np.where(nx >= 0, R.next[g, np.maximum(nx, 0)], -1)
        tp = np.where((near & (nx2 >= 0))[:, None], R.nodes[np.maximum(nx2, 0)], tp)
        tp = np.where((near & (nx >= 0) & (nx2 < 0))[:, None], R.goals[g], tp)
        d = tp - pos
        hd = np.hypot(d[:, 0], d[:, 1])
        rel_deg = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) - self.yaw[ri] + 180.0) % 360.0 - 180.0
        rel = np.radians(rel_deg)
        fwd = np.where(np.cos(rel) > 0.38, 1, np.where(np.cos(rel) < -0.38, -1, 0))
        side = np.where(np.sin(rel) > 0.38, -1, np.where(np.sin(rel) < -0.38, 1, 0))
        slow = np.hypot(s[ri, 3], s[ri, 4]) < 80.0
        self.run_stuck[ri] = np.where(slow, self.run_stuck[ri] + 1, 0)
        up = (d[:, 2] > 18.0) & (hd < 260.0)
        gap = (hd > 150.0) & (d[:, 2] > -40.0) & (nx >= 0) & ~near
        jump = (s[ri, 6] > 0.5) & (up | gap | (self.run_stuck[ri] > 10))
        turn = np.clip(rel_deg * 0.5, -20.0, 20.0)
        lab = np.stack([fwd + 1, side + 1, jump.astype(np.int64), np.abs(TURN[None, :] - turn[:, None]).argmin(1)], 1)
        self.teach[ri[ok], :4] = lab[ok]

    def _teach_update(self):
        """labels from the movement teacher for players on a movement goal (sampled from its policy)"""
        self.teach[:] = -1
        self._run_teach()
        self._weapon_teach()
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
        self.teach[mi, :4] = np.stack(out, 1)

    def _spawn(self, i, avoid, close=None):
        if self.near_item_p > 0 and self.route is not None and self.script[i] == 0 and self.run_k[i] < 0 and self.rng.random() < self.near_item_p:
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

    def _more(self, pos, rot, c, si, visible, opp_vel, seen_t):
        """the inputs of N_MORE"""
        n = self.n
        ar = np.arange(n)
        haz = np.zeros((n, 32), np.float32)
        if len(self.hurt_zones):
            ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            see = (np.abs((ang + np.pi) % (2 * np.pi) - np.pi)[None, :] <= self.fov()[0][:, None]) if self.fov_sight else True
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

    def _mates(self, i):
        """the other players of player i's group"""
        return [i ^ 1]

    def _slot(self, j):
        """a player's place in his group"""
        return j % 2

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
        for gi, lab in enumerate(self.route_goal):
            t = R.T[gi, node]
            out[:, ROUTE_ITEMS.index(lab)] = np.minimum((t + off) / 10.0, 2.0) * (t < 1e8)
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
        R = self.route
        k = self.intent
        if R is not None:
            gi = np.array(self.intent_gi)[k]
            valid = gi >= 0
            g = np.maximum(gi, 0)
            node = R.locate(pos)
            off = np.linalg.norm(R.nodes[node] - pos, axis=1) / 320.0
            t = R.T[g, node]
            ok = valid & (t < 1e8)
            nx = R.next[g, node]
            wp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[g])
            out[:, 0] = np.minimum((t + off) / 10.0, 2.0) * ok
            out[:, 1:4] = np.clip(rot(wp - pos) / 200.0, -1.0, 1.0) * ok[:, None]
            grp = np.arange(n) // (self._others_arr().shape[1] + 1)
            it = np.array(self.route_item)[g]
            out[:, 4] = self.item_up[grp, it] * valid
            out[:, 5] = np.minimum(self.item_t[grp, it] / 30.0, 2.0) * valid
        out[:, 6:12] = np.eye(len(INTENTS), dtype=np.float32)[k]
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
        grp = np.arange(n) // (self._others_arr().shape[1] + 1)
        best_t = np.full(n, 1e9, np.float32)
        for gi, lab in enumerate(self.route_goal):
            t = R.T[gi, node]
            it = self.route_item[gi]
            soon = self.item_up[grp, it] | (self.item_t[grp, it] < t + 3.0)
            k = INTENTS.index(lab)
            if lab == "MH":
                want = (self.hp < 100.0) & soon
                out = np.where(want & (out == 0), k, out)
            elif lab == "RA":
                want = (self.armor < 50.0) & soon
                out = np.where(want & (out == 0), k, out)
        for gi, lab in enumerate(self.route_goal):           # then the nearest big weapon he does not own
            if lab in ("RL", "RG", "LG"):
                t = R.T[gi, node]
                it = self.route_item[gi]
                want = (out == 0) & ~self.has[:, WEAPONS.index(lab.lower())] & self.item_up[grp, it] & (t < best_t)
                best_t = np.where(want, t, best_t)
                out = np.where(want, INTENTS.index(lab), out)
        return out

    def intend(self, choice, who):
        """the intention head: read once a second per player (staggered), at once after a spawn; held in between.
        who = the players it applies to (the game-server plugin passes one). Returns who was read this frame."""
        n = self.n
        self.int_tick += 1
        live = who & (((self.int_tick + np.arange(n)) % INTENT_EVERY == 0) | self.intent_new)
        choice = np.asarray(choice, np.int64)
        may = (self.intent == 0) | self.intent_done | (self.intent_t >= INTENT_HOLD) | self.intent_gone     # a choice holds (INTENT_HOLD)
        live = live & may
        changed = live & (choice != self.intent)
        self.intent = np.where(live, choice, self.intent)
        self.intent_t = np.where(changed, 0.0, self.intent_t + DT * who).astype(np.float32)
        self.intent_new = np.where(live, False, self.intent_new)
        self.intent_done = np.where(changed, False, self.intent_done)
        self.intent_live, self.intent_changed = live, changed
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
                if self.acquired[li[k]] or self.w.trace(eye[li[k]], near[k].astype(np.float32))["fraction"] >= 0.999:
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
        if self.fov_sight:                                   # a floor spot is seen if the line from the eyes to it is in view
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
        if self.focus_on:                                    # the delay per player: sharp while focus lasts, then dull
            self.focus = np.where(self.acquired, self.focus - DT, self.focus + FOCUS_REFILL * DT)
            self.focus = np.clip(self.focus, -0.5, FOCUS_SECS).astype(np.float32)
            dly = self.react_frames + np.where(self.focus > 0, -FOCUS_GAIN, FOCUS_LOSS)
            dly = np.where(self.script == 0, np.maximum(dly, 1), self.react_frames)
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
                              self._v9(pos, rot), self._intent(pos, rot, known, seen_t)], 1)
        return obs.astype(np.float32)

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
        view = self.w.rays_each(eye, vd, 2000.0)
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
        if runner.any() and self.route is not None:
            self._runner_keys(idx, runner, out, vis | chase)
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
        want = np.where(ok[:, RG] & (d > W_RULE_RG), RG, want)
        want = np.where(ok[:, LG] & (d < W_RULE_LG), LG, want)
        want = np.where(ok[:, RL] & (d > W_RULE_RL[0]) & (d < W_RULE_RL[1]), RL, want)
        want = np.where(ok[np.arange(len(ii)), want], want, self.weapon[ii])      # (no machine-gun ammo: keep what he holds)
        cur = self.weapon[ii]
        self.teach[ii, 4] = np.where(want == cur, 0, want + 1)
        self.stats["wrule_frames"] += len(ii)
        self.stats["wrule_agree"] += int((want == cur).sum())

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

    def _seats(self, m):
        g_ = self._others_arr().shape[1] + 1
        return np.arange(g_ * m, g_ * m + g_)

    def _item_run_start(self, m):
        """start an item run for match m in a share of the rounds (see RUN_LEN); returns its seats, or None"""
        if self.item_run_p <= 0 or self.route is None or self.fixed_kind is not None or getattr(self, "lab_force", None):
            return None
        if self.lab is not None:
            other = float(self.arena_len)
        else:
            other = 1.0 / max(1e-9, float((np.asarray(self.kind_p[:3], np.float64) / np.array([self.round_len, 15.0, 15.0])).sum()))
        p = self.item_run_p
        if self.rng.random() >= (p / RUN_LEN) / (p / RUN_LEN + (1.0 - p) / other):
            return None
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
        self.cf_t[m] = RUN_COLLECT if self.rng.random() < self.collect_fight_p else -1.0
        for i in q:
            self.load_sets[int(i)] = ()                     # the game's spawn: machine gun and gauntlet
            self.state = self.w.state()
            self._spawn(int(i), avoid=None)
        self.state = self.w.state()
        for i in q:
            self._run_pick(int(i))
        return q

    def _run_pick(self, i):
        """item run: the next target of player i, one of the big items lying there that he can walk to"""
        R = self.route
        node = int(R.locate(self.w.state()[i:i + 1, :3])[0])
        m = i // (self._others_arr().shape[1] + 1)
        ks = [k for k, gi in enumerate(self.intent_gi) if k > 0 and gi >= 0 and k != self.run_k[i] and R.T[gi, node] < 1e8]
        ok = [k for k in ks if self.item_up[m, self.route_item[self.intent_gi[k]]] and R.T[self.intent_gi[k], node] > 1.0]
        ok = ok or ks
        self.run_k[i] = int(self.rng.choice(ok)) if ok else 0
        self.intent_new[i], self.intent_done[i] = True, True     # the new target is read at once

    def _runner_keys(self, idx, r, out, engaged):
        """script 3, the item runner (owner, 2026-10-07): he goes for what the item rule names (intent_rule: the mega
        when hurt, the red armor when bare, else the nearest big weapon he lacks) along the walking graph, and fights
        like the all-round scripted fighter when an enemy is in view, still moving along his way. He starts with the
        game's spawn and takes what he walks over. Not rewarded and not imitated: he is in a share of the rounds
        (RUNNER_P) so that the learner meets an opponent who turns up with the stack."""
        R, s = self.route, self.state
        rl = np.nonzero(r)[0]
        ri = idx[rl]
        pos = s[ri, :3]
        node = R.locate(pos)
        lab = np.array([INTENTS.index(l) if l in INTENTS else -1 for l in self.route_goal], np.int64)
        k = self.intent_teach[ri]
        T = np.where(lab[None, :] == k[:, None], R.T[:, node].T, 1e9)
        gi = T.argmin(1)
        go = (k > 0) & (T[np.arange(len(ri)), gi] < 1e8)
        nx = R.next[gi, node]
        tp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], R.goals[gi])
        near = np.hypot(tp[:, 0] - pos[:, 0], tp[:, 1] - pos[:, 1]) < 48.0
        nx2 = np.where(nx >= 0, R.next[gi, np.maximum(nx, 0)], -1)
        tp = np.where((near & (nx2 >= 0))[:, None], R.nodes[np.maximum(nx2, 0)], tp)   # look one step further when close
        tp = np.where((near & (nx >= 0) & (nx2 < 0))[:, None], R.goals[gi], tp)
        d = tp - pos
        hd = np.hypot(d[:, 0], d[:, 1])
        rel_deg = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) - self.yaw[ri] + 180.0) % 360.0 - 180.0
        rel = np.radians(rel_deg)
        fwd = np.where(np.cos(rel) > 0.38, 1, np.where(np.cos(rel) < -0.38, -1, 0))
        side = np.where(np.sin(rel) > 0.38, -1, np.where(np.sin(rel) < -0.38, 1, 0))     # +1 = strafe right
        slow = np.hypot(s[ri, 3], s[ri, 4]) < 80.0
        self.sc_stuck[ri] = np.where(slow & go, self.sc_stuck[ri] + 1, 0)
        up = (d[:, 2] > 18.0) & (hd < 260.0)                 # a step up, a ledge
        gap = (hd > 150.0) & (d[:, 2] > -40.0) & (nx >= 0) & ~near     # a long edge of the graph on the level: a jump
        jump = (s[ri, 6] > 0.5) & (up | gap | (self.sc_stuck[ri] > 10))
        out[rl, 0] = np.where(go, fwd + 1, out[rl, 0])
        out[rl, 1] = np.where(go, side + 1, out[rl, 1])
        out[rl, 2] = np.where(go, jump, out[rl, 2])
        turn = np.clip(rel_deg * 0.5, -20.0, 20.0)           # nobody in view: he looks where he is going
        look = go & ~engaged[rl]
        out[rl, 3] = np.where(look, np.abs(TURN[None, :] - turn[:, None]).argmin(1), out[rl, 3])

    # ---------------------------------------------------------------- step
    def limit_keys(self, a, who=None):
        """finger limits (see FINGER_HOLD): turns the requested keys and weapon choice into what one hand can do.
        Changes a[:, :3] and a[:, 6] in place."""
        if who is None:
            who = self.script == 0
        self.key_tick += 1                                  # the left hand decides ten times a second (staggered by player)
        dec = ((self.key_tick + np.arange(len(a))) % KEY_EVERY == 0) | ~who
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

    def step(self, actions):
        a = np.array(actions, copy=True)
        n = self.n
        ar = np.arange(n)
        sc = np.nonzero(self.script > 0)[0]
        if len(sc):
            a[sc] = self._script_actions(sc)
        if self.key_limits:
            self.limit_keys(a)
        human = self.script == 0                            # policy-controlled players (for the statistics)
        prev_int, prev_done = self.intent.copy(), self.intent_done.copy()
        self.intent_teach = self.intent_rule()
        ch_ = (a[:, 10] if a.shape[1] > 10 else np.zeros(n, np.int64)).copy()
        in_run = self.run_k >= 0
        ch_[in_run] = self.run_k[in_run]                    # an item run: the target is given, not chosen
        self.intend(ch_, human)
        self.intent_live = self.intent_live & ~in_run       # (and the intention head is not trained on those frames)
        self.stats["intent_trips"][0] += int((self.intent_changed & (self.intent > 0)).sum())
        self.stats["intent_trips"][2] += int((self.intent_changed & (prev_int > 0) & ~self.intent_done).sum())
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
        self.snd_t += DT
        self.shot_t += DT
        self.pain_t += DT
        self.trail_t += DT
        self._hear(2, np.nonzero((prev[:, 6] > 0.5) & (s[:, 6] < 0.5) & (s[:, 5] > 100))[0])      # jumps
        self._hear(3, np.nonzero(np.linalg.norm(s[:, :3] - prev[:, :3], axis=1) > 200)[0])       # teleports
        # fall damage (Quake 3 rule: from the speed of the landing)
        land = (prev[:, 6] < 0.5) & (s[:, 6] > 0.5)
        delta = prev[:, 5] ** 2 * 0.0001
        fall = np.where(land & (prev[:, 5] < 0), np.where(delta > FALL_FAR, 10.0, np.where(delta > FALL_MED, 5.0, 0.0)), 0.0)
        fallers = np.nonzero(fall > 0)[0]
        reward -= SWITCH_COST * sw
        blind = fire & (self.seen_t > 1.0) & (pkind != MOVE) & ((pkind != COURSE) | self.gun)
        reward -= BLIND_FIRE_COST * blind
        fight = human & (pkind != MOVE) & ((pkind != COURSE) | self.gun)
        self.stats["switches"] += int((sw & fight).sum())
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
        self.hear((shoot & (self.weapon != G)) | ((prev[:, 6] > 0.5) != (s[:, 6] > 0.5)) |      # shots, jumps and landings,
                  ((s[:, 6] > 0.5) & (np.hypot(s[:, 3], s[:, 4]) > 200.0) & ~self.duck))      # running steps (not walking, not crouched)
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
                fd = fdir[i]
                if MG_SPREAD > 0 and wpn in (MG, HMG):        # the bullet leaves somewhere inside the cone
                    u_ = np.cross(fd, np.array([0.0, 0.0, 1.0], np.float32))
                    u_ = u_ / (np.linalg.norm(u_) + 1e-6)
                    v_ = np.cross(fd, u_)
                    ra_, th_ = math.tan(math.radians(MG_SPREAD)) * self.rng.random(), self.rng.random() * 2 * math.pi
                    fd = fd + (u_ * math.cos(th_) + v_ * math.sin(th_)) * ra_
                    fd = (fd / np.linalg.norm(fd)).astype(np.float32)
                fr = self.w.rays_each(eye[i:i + 1], fd[None, None, :], rng_)[0, 0]
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
        hurt = np.nonzero((dmg_taken > 0) & (self.hp > 0))[0]              # pain sounds: the opponent hears them within earshot
        if len(hurt):
            lis_ = hurt ^ 1
            near_ = np.linalg.norm(s[hurt, :3] - s[lis_, :3], axis=1) < HEAR_EVT
            self.pain_t[lis_[near_]] = 0.0
            self.pain_b[lis_[near_]] = np.minimum(3, (self.hp[hurt[near_]] // 25).astype(np.int64))
        dealt = np.where(attacker[opp_all] == ar, dmg_taken[opp_all], 0.0)
        taken = dmg_taken + fall                            # from the opponent, own splash and falls alike
        if self.gun.any():                                  # run-and-gun: damage pays by how fast the runner is moving
            gsp = np.clip(np.hypot(s[:, 3], s[:, 4]) / 320.0, 0.0, 1.5)
            self.stats["gun"][0] += float(dealt[self.gun].sum())
            dealt = np.where(self.gun, dealt * gsp, dealt)
        reward += self.dmg_reward * (dealt - self.dmg_taken_w * taken)   # damage taken against damage dealt
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
                if took and lab in ("MH", "RA"):
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
                    self.hp[i], self.armor[i] = 100.0, 0.0
                    self.stats["lab_items"][0 if lab == "MH" else 1] += 1
                if took:
                    # health and armor by the points gained; a weapon he did not have counts as 25 points, one he
                    # has already (ammo) as nothing, so standing on a weapon's spot earns nothing
                    reward[i] += self.item_reward * (gain if kind in ("hp", "ar") else 25.0 if new_wp else 0.0) / 100.0
                    want_ = lab if lab in ("MH", "RA") else WEAPONS[int(val)].upper() if kind == "wp" else ""
                    if want_ in INTENTS and self.intent[i] == INTENTS.index(want_) and not self.intent_done[i]:
                        self.intent_done[i] = True                       # the trip he chose is complete
                        self.stats["intent_trips"][1] += 1
                        self.stats["intent_reach"] += float(self.intent_t[i])
                    if lab in ("MH", "RA") and self.item_loss > 0:       # the others lose a share: it was theirs to take
                        for o_ in self._mates(i):
                            if self.hp[o_] > 0:
                                reward[o_] -= self.item_loss * self.item_reward * gain / 100.0
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
            self.seek_phi = phi.astype(np.float32)
        if self.route is not None:
            # The chosen way pays as he goes (see INTENTS): seconds of it gained, while the item is up or comes up before
            # he can be there. Only steady movement counts; a changed intention starts a new count.
            R_ = self.route
            gi_ = np.array(self.intent_gi)[self.intent]
            valid = gi_ >= 0
            g_ = np.maximum(gi_, 0)
            node = R_.locate(s[:, :3])
            phi = np.where(valid, R_.T[g_, node] + np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0, 0.0)
            grp = np.arange(n) // (self._others_arr().shape[1] + 1)
            it_ = np.array(self.route_item)[g_]
            soon = self.item_up[grp, it_] | (self.item_t[grp, it_] < phi + 5.0)
            self.intent_gone = valid & ~soon & (self.intent > 0)
            self.intent_phi0 = np.where(self.intent_changed, np.maximum(phi, 1.0), self.intent_phi0).astype(np.float32)
            gain = self.intent_phi - phi
            pay = valid & soon & ~self.intent_changed & ~self.intent_done & (self.script == 0) & (self.hp > 0) & (np.abs(gain) < 0.4)
            worth = self.item_reward * np.array(INTENT_VALUE, np.float32)[self.intent]      # the whole way is worth the pickup
            claw = self.intent_changed & (prev_int > 0) & ~prev_done & ~in_run              # a trip given up pays nothing (v9)
            reward -= self.intent_paid * claw
            self.intent_paid = np.where(claw | self.intent_done, 0.0, self.intent_paid).astype(np.float32)
            pay_now = self.intent_seek * worth * gain / self.intent_phi0 * pay
            reward += pay_now - INTENT_SWITCH * (self.intent_changed & (prev_int > 0) & ~in_run)
            self.intent_paid = (self.intent_paid + pay_now).astype(np.float32)
            run = in_run & (self.script == 0)
            if run.any():                                   # item runs: the way gained against the clock, a bonus on taking it
                alive = run & (self.hp > 0)
                reward += RUN_SCALE * (np.where(pay, gain, 0.0) - DT) * alive
                sp_ = np.hypot(s[:, 3], s[:, 4])
                self.stats["move_frames"] += int(alive.sum())
                self.stats["move_speed"] += float(sp_[alive].sum())
                self.stats["move_fast"] += int(((sp_ > 330) & (s[:, 6] < 0.5) & alive).sum())
                arr = run & self.intent_done & (self.run_k > 0) & (self.intent == self.run_k)     # (the pickup may be booked after this block: no "since last frame" test)
                gone = run & ~arr & (self.run_k > 0) & (self.intent == self.run_k) & valid & ~soon & ~self.intent_done
                for i in np.nonzero(arr | gone | (run & (self.run_k == 0)))[0]:
                    if arr[i]:
                        reward[i] += RUN_ARRIVE
                        self.stats["move_arrive"] += 1
                    self._run_pick(int(i))
            self.intent_phi = phi.astype(np.float32)

        # deaths, frags, respawns
        done = np.zeros(n, bool)                            # end of the round (memory and returns reset here only)
        died = np.zeros(n, bool)
        events = []
        dead = np.nonzero(self.hp <= 0)[0]
        for v in dead:
            k = attacker[v]
            reward[v] -= 1.0
            if k >= 0 and k != v and self.cf_side[k] and self.cf_side[v] and self.cf_side[k] != self.cf_side[v]:
                self.stats["cf_stack_kills" if self.cf_side[k] == 1 else "cf_plain_kills"] += 1
            if CLAW_ON_DEATH and self.intent[v] > 0 and not self.intent_done[v]:
                reward[v] -= float(self.intent_paid[v])      # the trip he died on pays nothing (v9; off since 2026-10-07)
            died[v] = True
            if k >= 0 and k != v:
                reward[k] += 1.0
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
                    self.stats["vs_persona"][1, self.sc_persona[k]] += 1
            else:
                self.stats["suicides"] += 1
            events.append(dict(victim=int(v), killer=int(k), weapon=int(kill_w.get(v, -1))))
            self.note_death(int(v), int(k))
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
                if CLAW_ON_DEATH and self.intent[v] > 0 and not self.intent_done[v]:
                    reward[v] -= float(self.intent_paid[v])
                died[v] = True
                self.stats["suicides"] += 1
                self._spawn(int(v), avoid=s[v ^ 1, :3])
                if self.goal[v] >= 0:
                    self._new_goal(int(v))
        # short rounds (curriculum): restart both players near each other every ~round_len seconds
        self.round_t += DT
        cf_ = np.nonzero(self.cf_t > 0)[0]
        if len(cf_):
            self.cf_t[cf_] -= DT
            for m_ in cf_[self.cf_t[cf_] <= 0]:
                self._collect_to_fight(int(m_))
        klen = np.where(self.kind == NORMAL, self.round_len, np.where(self.kind == MOVE, self.move_len, 15.0))
        if self.fixed_kind is not None:
            klen = np.full(self.M, self.round_len)
        ends = np.nonzero(self.round_t > klen * self.rng.uniform(0.67, 1.33, self.M))[0]
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
        for m in ends:
            self.run_k[self._seats(int(m))] = -1
            self.cf_side[self._seats(int(m))] = 0
            self.cf_t[m] = -1.0
            q_ = self._item_run_start(int(m))                # an item run in a share of the rounds (RUN_LEN)
            if q_ is not None:
                self.round_t[m] = 0.0
                done[q_] = True
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
        if done.any():                                      # a new round: nothing is known
            self.it_t[done], self.e_got[done], self.e_life[done] = 99.0, 0.0, 99.0
        if len(dead) or len(out) or len(ends):
            self.state = s = self.w.state()

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

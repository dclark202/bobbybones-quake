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
import rocket_jumps as RJM  # noqa: E402

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
    # (branch aim2, 2026-10-27: the code's defaults are !aim default's, so a tool run without the run's environment plays as
    #  the servers do: percept_speed 0.075 x f (0 at every level before), PERCEPT_SPEED_MAX 1.5 (3.0), the rail's 0.001 (0))
    a = dict(level=float(level), percept_sigma=0.6 * f, percept_tau=0.15, percept_speed=0.075 * f, react_ms=100.0 * f,
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


REACT_FRAMES = 4                                       # 100 ms (!aim default; 2 = 50 ms until branch aim2, 2026-10-27): tracking an enemy already in view lags by this much.
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
PERCEPT_SPEED, PERCEPT_SPEED_MAX = _aim("PERCEPT_SPEED", "percept_speed"), float(os.environ.get("PERCEPT_SPEED_MAX") or 1.5)
# (v0.5.0: PERCEPT_SPEED_MAX settable, a PLAY_VAR; 3 degrees as before. The calibration of 2026-10-26: at 3 the lightning gun's
#  hit rate stops falling near 40% whatever PERCEPT_SPEED, the pros' is 33%.)
# PERCEPT_SPEED_MAX_RG / PERCEPT_SPEED_MAX_LG (v0.5.0, after the review of 2026-10-26; PLAY_VARS and live): the cap with the
# railgun / the lightning gun in hand (0: PERCEPT_SPEED_MAX). One cap moved both together (cap 5: lightning 37.4%, rail 38.2%,
# the pros 32.7 / 43.5): a rail shot is a flick, the lightning gun a track. Both 0 = the simulator before, bit for bit.
PERCEPT_SPEED_MAX_RG = float(os.environ.get("PERCEPT_SPEED_MAX_RG") or 0.001)     # (aim2 branch: !aim default's 0.001 when unset)
PERCEPT_SPEED_MAX_LG = float(os.environ.get("PERCEPT_SPEED_MAX_LG") or 0.0)
# Values since 2026-10-07 20:15 (the first "click", owner: "nudge hitscan aim down 1-2 clicks"): 1.2 degrees, 0.5 s, 0.012.
# v10 under them in the reflex room, not yet adapted: error on a strafing target 3.0 -> 3.8 degrees (the owner 2.45), time on
# it 58% -> 54% (40%), lightning damage a second 83 -> 75 (58), first rail shot on a jumping target 74% -> 65% (88%).
# The second click, measured and kept ready: 1.6 / 0.6 / 0.02 -> 5.2 degrees, 44%, 67, 57%. Before: 0.6 / 0.15 / 0.
# (2026-10-05, B-94) Being shot at costs aim: a hit throws his read of the enemy's direction off by FLINCH_PER_DMG
# degrees per point of damage (at most FLINCH_MAX at a time), and the error stays larger while the flinch fades
# (FLINCH_TAU seconds). First values; to be set from players in the reflex test (calm half against the half under fire).
FLINCH_PER_DMG, FLINCH_MAX, FLINCH_TAU = _aim("FLINCH_PER_DMG", "flinch_per_dmg"), _aim("FLINCH_MAX", "flinch_max"), _aim("FLINCH_TAU", "flinch_tau")   # (0.12, 3.0, 0.3 until v12)
SURPRISE_MS = _aim("SURPRISE_MS", "surprise_ms")


def surprise_frames(ecc, seen_t, ms=None):
    """frames more before an enemy who comes into view is noticed: by how far off the crosshair he is (degrees) and by
    whether he was seen or heard in the last two seconds (see the aim ability above)"""
    return np.rint((SURPRISE_MS if ms is None else ms) * np.clip((ecc - 10.0) / 30.0, 0.0, 1.0) * np.where(seen_t < 2.0, 0.5, 1.0) / 25.0).astype(np.int64)
# (2026-10-05, B-93) The tracking delay is an average, not a floor: with an enemy in view he is sharper for a short
# spell (FOCUS_GAIN frames quicker) while his focus lasts, then slower than the average (FOCUS_LOSS frames) until
# it has come back. Focus runs down at one second a second with an enemy in view and comes back at FOCUS_REFILL.
FOCUS_SECS, FOCUS_REFILL, FOCUS_GAIN, FOCUS_LOSS = 2.0, 0.25, 2, 1
# ---- AIM2 (v0.5.2 proposal, 2026-10-27; docs/v0.5.2/AIM_MODEL.md). All off by default: the simulator before, bit for bit.
# PLAY_VARS (a checkpoint, policy.npz and the plugins carry them); the numbers are live (live.json) so a run can open them
# slowly. One model for every weapon: nothing here looks at the weapon in hand.
#   AIM2=1          the sight error's speed term is the RETINAL SLIP and the ECCENTRICITY, not the world bearing's rate
#                   (PERCEPT_SPEED and its caps): slip = |the target's angular rate - his view's angular rate| (deg/s), as of
#                   his read delay (the same frame of the past as the place he reads); error + min(AIM2_C_SLIP x max(0, slip -
#                   AIM2_S0), AIM2_CAP_SLIP). Eccentricity = the angle between his view and the target as of the delay;
#                   error + min(AIM2_C_ECC x max(0, ecc - AIM2_E0), AIM2_CAP_ECC). Zoomed, the whole error (base, flinch,
#                   slip, eccentricity) is ZOOM as large (with ZOOM_PERCEPT; before: the base only). AIM2_W (live, 0..1, 1 by
#                   default) blends: the old speed term x (1 - W) + the new terms x W (W = 0: the old error exactly).
#   AIM2_SPLIT=1    the world picture apart from the aim error: the perceived place for his map memory, belief, places and
#                   tokens (and the geometry of the rocket and plasma lead and the rocket floor point) gets the delay and
#                   RANGE_FIX (VEL_FIX on the velocity) but the sight error only x (1 - AIM2_SPLIT_W) (live, 1 by default);
#                   the sight error stays on the crosshair-to-target angles, the on-target flag, the burst-to-enemy closeness
#                   and the final angles of the lead and rocket aim inputs.
#   AIM2_FOCUS=1    focus no longer cuts the read delay by FOCUS_GAIN frames: the cut is AIM2_FOCUS_GAIN (live, 0 by
#                   default; 2 = the old cut) and while focus lasts the base sight error is x AIM2_FOCUS_SIG (live, 0.75).
#   AIM2_FLINCH=1   a hit grows the flinch's sustained error only (FLINCH_TAU), no instantaneous kick to the error itself.
#   AIM2_SMOOTH_K   (live, 1 by default = as before) the view inertia MOUSE_SMOOTH / _FINE times this factor (0: none; the
#                   hand's bandwidth HAND_BAND then is the only filter between his command and his view).
AIM2 = float(os.environ.get("AIM2") or 0.0) > 0
AIM2_SPLIT = float(os.environ.get("AIM2_SPLIT") or 0.0) > 0
AIM2_FOCUS = float(os.environ.get("AIM2_FOCUS") or 0.0) > 0
AIM2_FLINCH = float(os.environ.get("AIM2_FLINCH") or 0.0) > 0


def _aim2_values(get):
    """the live numbers of AIM2 (see above) from get(name) -> the environment's string or None"""
    def f_(k_, d_):
        x_ = get(k_)
        return float(x_) if (x_ or "").strip() else float(d_)
    v = dict(AIM2_W=f_("AIM2_W", 1.0), AIM2_C_SLIP=f_("AIM2_C_SLIP", 0.02), AIM2_S0=f_("AIM2_S0", 15.0),
             AIM2_CAP_SLIP=f_("AIM2_CAP_SLIP", 2.0), AIM2_C_ECC=f_("AIM2_C_ECC", 0.04), AIM2_E0=f_("AIM2_E0", 2.0),
             AIM2_CAP_ECC=f_("AIM2_CAP_ECC", 2.0), AIM2_SPLIT_W=f_("AIM2_SPLIT_W", 1.0),
             AIM2_FOCUS_GAIN=f_("AIM2_FOCUS_GAIN", 0.0), AIM2_FOCUS_SIG=f_("AIM2_FOCUS_SIG", 0.75),
             AIM2_SMOOTH_K=f_("AIM2_SMOOTH_K", 1.0))
    for k_ in ("AIM2_W", "AIM2_SPLIT_W", "AIM2_FOCUS_SIG", "AIM2_SMOOTH_K"):
        if not 0.0 <= v[k_] <= 1.0:
            raise ValueError(k_ + " must be within 0 .. 1")
    for k_ in ("AIM2_C_SLIP", "AIM2_S0", "AIM2_CAP_SLIP", "AIM2_C_ECC", "AIM2_E0", "AIM2_CAP_ECC"):
        if not 0.0 <= v[k_] <= 1000.0:
            raise ValueError(k_ + " must be within 0 .. 1000")
    if v["AIM2_FOCUS_GAIN"] not in (0.0, 1.0, 2.0):
        raise ValueError("AIM2_FOCUS_GAIN must be 0, 1 or 2 (frames)")
    return v


globals().update(_aim2_values(os.environ.get))
AIM2_LIVE = ("AIM2_W", "AIM2_C_SLIP", "AIM2_S0", "AIM2_CAP_SLIP", "AIM2_C_ECC", "AIM2_E0", "AIM2_CAP_ECC", "AIM2_SPLIT_W",
             "AIM2_FOCUS_GAIN", "AIM2_FOCUS_SIG", "AIM2_SMOOTH_K", "FLINCH_PER_DMG", "FLINCH_MAX", "FLINCH_TAU")
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
# can be left at any reading, as "nothing" can. TARGETS_FREE=2 (2026-10-12): a place is left at any reading for an
# ITEM and for nothing else (a place held for 8 s cost him the mega: a place opened at 5% of his readings was 22% of
# his time and 38% of the frags against the same network on Blood Run); so an item is chosen when he would have
# chosen it from "nothing", and a place is not dropped for "nothing" or another place at the next reading. Nothing is paid for it: no pay for the way, none for speed on it, no
# pay for being there, and leaving it costs nothing (INTENT_SWITCH is not charged). In an item run or a jump run the
# target is given, so a place is never one there. The item rule's lesson (intent_teach, the intention's teacher): where
# the rule names no item its label is -1 with the switch on, and the trainer leaves such a frame out, so that what he
# does with no item due is his own (it taught "nothing" there); the lesson is about which item among the items, so the
# trainer also takes the places out of its sum, as the enemy.
# A game server's plugin, which does not call step(): note_holds() every frame (the place reached).
HOLD_INTENT, HOLD_SLOTS = 9, 8                             # the first place among the intentions; how many
TARGETS = float(os.environ.get("TARGETS") or 0.0) > 0
TARGETS_FREE = int(float(os.environ.get("TARGETS_FREE") or 0.0))
#   WEAPON_FREE=1  (v0.5.0, a PLAY_VAR; owner 2026-10-26: "Make the loophole fix") a weapon he holds is no target. Weapons come
#                  back every 5 s and a chosen weapon, once taken, stayed his "done" target with his way and legs still pointing
#                  at its spawn; choosing it again began no new trip. So a weapon was a free "hold this spawn" order: v0.4.4 sat
#                  on the lightning gun's (head open) or the rail's (head shut), re-taking it every 5 s for full ammunition and
#                  keeping it from the enemy (RESULTS 2026-10-26). With the switch: (1) taking the weapon he chose ends the choice
#                  (a new reading at once, as after a spawn); (2) a reading of a weapon he owns with at least one pickup's worth of
#                  ammunition (ITEM_DEFS: rockets 10, rail 10, lightning 100) is read as "nothing" (the hands his own, no way to a
#                  spawn), as the enemy is without HUNT. Going for a weapon he lacks, or to refill one that is low, stays.
#                  Off: as before, bit for bit.
WEAPON_FREE = float(os.environ.get("WEAPON_FREE") or 0.0) > 0
# v0.5.0's other loophole fixes (owner, 2026-10-26, the audit of v0.4.4's simulator; RESULTS 2026-10-26), each off by default:
#   SPEED_LOS=1        the speed pay (SPEED_PAY) only while the enemy is out of his LINE OF SIGHT: before, out of his view cone
#                      was enough, so facing away from the enemy kept it coming (a pay for not looking)
#   GONE_BELIEF=1      a choice held for INTENT_HOLD is let go early when its item is gone and not back in time ("gone"):
#                      judged by what he knows of the item (ITEM_BELIEF's bel_t), not the truth (a free probe of the item
#                      clocks out of his sight: a new reading taken early meant "it was taken")
#   TELEFRAG=1         a teleport that comes out on the other player kills him (the game's G_KillBox; the frag is the
#                      teleporter's, his damage the victim's whole stack): standing on an exit was safe in the simulator
#   JRUN_SPEED_BACK=1  a jump run's try that ends without the jump gives back its speed pay (SPEED_PAY_RUN) with the rest
#   SMALL_ZERO=1       the knowledge pay (KNOW_PAY) and the big weapons' pay by order (BIG_PICK_SEQ) zero-sum: what one
#                      player gets the other loses (both paid each other's pay before: a pay for peace)
SPEED_LOS = float(os.environ.get("SPEED_LOS") or 0.0) > 0
GONE_BELIEF = float(os.environ.get("GONE_BELIEF") or 0.0) > 0
TELEFRAG = float(os.environ.get("TELEFRAG") or 0.0) > 0
JRUN_SPEED_BACK = float(os.environ.get("JRUN_SPEED_BACK") or 0.0) > 0
SMALL_ZERO = float(os.environ.get("SMALL_ZERO") or 0.0) > 0
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
STACK_BARE_RAMP, STACK_LOW_AT = 5.0, 70.0
STACK_BARE_MAX = float(os.environ.get("STACK_BARE_MAX") or 4.0)   # (v0.3.1's pay, the owner 2026-10-15: 1 = a steady bleed, capped)
# v0.3.1's pay (the owner, 2026-10-15 evening, after his play test: "a bot that doesn't want to fight"), all off by default:
# BIG_PICK  > 0: a weapon picked up pays this once a life for each of the rocket launcher, lightning gun and railgun, and
#           nothing for the other weapons (off: any weapon he did not have counts as 25 points of item pay)
# SELF_DEBT = 1: health and armor he took off himself (his own splash, falls, lava and slime) are not paid again when a
#           pickup refills them ("never paid after self-damage")
# BIG_ONCE  = 1 (with BIG_PICK): BIG_PICK once a life for the first of the three only, not for each
# STACK_DIFF > 0: frags a minute for his stack against the enemy's (health and armor, a dead player's 0): STACK_DIFF x
#           (his - the enemy's) / 200, clamped to +-1, paid to him and taken from the enemy (zero-sum); duels only
# ITEM_FLAT = "MH:0.12,RA:0.12,YA:0.06": a flat pay a pickup of these items (whatever it adds), the same taken from the
#           enemy (zero-sum); every other item pays nothing under it (run with --item-reward 0 for the points' pay)
BIG_PICK = float(os.environ.get("BIG_PICK") or 0.0)
SELF_DEBT = float(os.environ.get("SELF_DEBT") or 0.0) > 0
BIG_ONCE = float(os.environ.get("BIG_ONCE") or 0.0) > 0
# BIG_PICK_SEQ = "0.10,0.06,0.05" (v0.3.8, the owner 2026-10-19; live): in place of BIG_PICK and BIG_ONCE, the big three paid
#           a life by the order he gets them: the first of the rocket launcher, lightning gun and railgun the first number,
#           the second the second, the third the third (missing numbers: nothing). A weapon he held already or got earlier
#           in the life pays nothing (BIG_PICK's rules, held weapons too: a rail start's railgun is one of his). Paid to
#           him only, nothing taken from the enemy (as BIG_PICK). Counters: stats["big_seq"] (pickups by order, pay by order).
BIG_PICK_SEQ = tuple(float(x_) for x_ in (os.environ.get("BIG_PICK_SEQ") or "").split(",") if x_.strip())
STACK_DIFF = float(os.environ.get("STACK_DIFF") or 0.0)
ITEM_FLAT = {k_: float(v_) for k_, v_ in (x_.split(":") for x_ in (os.environ.get("ITEM_FLAT") or "").split(",") if ":" in x_)}
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
# RG_FAR_PRICE (v0.3.8, the owner 2026-10-19: "0.010"; live; with SHOT_COST): a railgun shot fired while the nearest living
#              enemy is more than RG_FAR_DIST units away (3D, origin to origin, as RAIL_FAR_PAY measures it) costs this
#              fixed price in place of SHOT_COST's (no scarcity factor, no SHOT_W, no damage reward in it: today's base is
#              0.10 x 0.0055 x 80 = 0.044 times the factor 0.25 .. 3). Nearer, or nobody alive to shoot at: SHOT_COST's price.
#              0 = off. Counters: stats["rg_far"] (far rail shots, their price, what SHOT_COST would have priced them).
RG_FAR_PRICE = float(os.environ.get("RG_FAR_PRICE") or 0.0)
RG_FAR_DIST = float(os.environ.get("RG_FAR_DIST") or 700.0)
# The switches that change what a trained network is given or how its outputs are carried out. The trainer writes the
# ones that were set into the checkpoint, sim/export_duel.py into policy.npz, and the plugins set them before they load
# this module (until 2026-10-08 none reached a server: INTENT_HOLD was 8 in training and 3 there).
PLAY_VARS = ("INTENT_HOLD", "ITEM_BELIEF", "AIM_LEVEL", "AIM_PRESET", "FIRE_HOLD", "SURPRISE_MS", "AMMO_PACKS",
             "PERCEPT_SIGMA", "PERCEPT_TAU", "PERCEPT_SPEED", "KEY_RATE", "GROUND_SENSE", "SHOT_MASK", "LAVA", "WALK_FIX",
             "ITEM_DROP", "SOLIDS", "PRO_WAYS", "NEAREST", "PROJ_SEE", "JUMP_OPEN", "LEGS_LOOK", "LEGS_STAND", "LEGS", "LEGS_EVERY", "LEGS_OFF", "AUTO_SWITCH", "FIGHT_TARGET", "EN_KNOWN", "TARGETS", "TARGETS_FREE", "WAYS", "WAY_CAP", "WAY_ALPHA", "WAY_UNTESTED",
             "STYLE_MIX", "EN_STACK", "ES_MU_H", "ES_MU_A", "ES_SD_H", "ES_SD_A", "ES_TAU", "HUNT")
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
# B-253 stage (a) (the owner, 2026-10-15: "the separate movement network should really be part of the main fast network"):
# his legs' network as a branch of his own network. LEGS_IN=1 (with LEGS; a PLAY_VAR): legs_prep(), called by whoever
# plays him after observe() (the trainer's workers, the plugins, the checks' tools), gives the movement network's 61
# inputs of every seat that his legs could carry on the next step (normalised and cut at +-10 as the movement network
# takes them; zeros where it has no way), the same inputs _legs_step() would make. The player's network works out the
# branch's logits (17: forward 3, sideways 3, jump 3... in the movement network's order 3, 3, 2, 9) and hands them over
# in env.legs_lg [players, 17] before step(); _legs_step() then samples from them exactly as from its own sums (the
# same draws of the simulator's random stream, the same hand rule for the view's turn, the same turn bins). Given no
# logits (a caller that does not know the branch) it works them out itself as before. LEGS_IN_CHECK=1 works them out
# all the same and keeps the largest difference (legs_in_err: the largest logit difference, the rows compared, the
# rows whose sampled choice would differ). With LEGS_IN off nothing here runs and nothing changes.
LEGS_IN = LEGS and float(os.environ.get("LEGS_IN") or 0.0) > 0
LEGS_IN_CHECK = LEGS_IN and float(os.environ.get("LEGS_IN_CHECK") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("LEGS_IN",)
# v0.3.2 (the owner's play test of 2026-10-16: on his legs, 54% of his time, he has "blinders": they own his view's turn and
# know nothing of the enemy). LEGS_TURN_ADD=1 (with LEGS; a PLAY_VAR): one more output, the last (TA_HEAD: his own turn
# correction, the TA_BINS degrees a frame, the first of them 0), drawn every frame. On the frames his legs carry him his
# view's turn command is the legs' turn plus his correction (cut to the largest turn of TURN); the sum then goes through
# his mouse as any turn of his does (inertia, the flick cap, hand noise, the pad, the jerk's price): the same hand limits
# as now. On every other frame the output does nothing (the trainer counts it on the frames his legs moved him only).
# A network without the output (an older one, a league file, the control) gives 0 there, which is no correction. The
# converted start has the output shut (its weights 0, the bias of "0" TA_SHUT above the others: another bin is drawn
# with the chance e^-20) and the trainer's --turn-add-open opens it on a clock (as --gate-open). With it off ACTION_DIMS
# and everything else are as before.
LEGS_TURN_ADD = LEGS and float(os.environ.get("LEGS_TURN_ADD") or 0.0) > 0
TA_BINS = np.array([0.0, -0.5, 0.5, -1.0, 1.0, -2.0, 2.0, -4.0, 4.0, -8.0, 8.0, -15.0, 15.0], np.float32)   # degrees a frame (0 first)
TA_SHUT = 20.0 + float(np.log(len(TA_BINS) - 1))            # the shut start's bias of "0" over the others (weights 0): P(not 0) ~ e^-20
PLAY_VARS = PLAY_VARS + ("LEGS_TURN_ADD",)
# v0.3.3, one movement network step 2 (the same way as LEGS_TURN_ADD): LEGS_KEYS_ADD=1 (with LEGS; a PLAY_VAR) gives five
# more outputs at the end (KA_HEAD to KA_HEAD + 4, two choices each: 0 "my legs'", 1 "mine"), one for each of the legs'
# other outputs (KA_COLS: forward/back, sideways, jump/crouch, walk, zoom), drawn every frame. On the frames his legs carry
# him, where the choice is 1 his own output of that column takes the place of the legs' (his own outputs are drawn on
# every frame anyway); the result goes through his finger limits as any key of his (_legs_step is before them). Elsewhere
# the five do nothing. A network without them is given them shut (weights 0, the bias of 0 KA_SHUT over 1: "mine" with
# the chance e^-30, which a float32 draw never gives) and the trainer's --keys-add-open opens them on a clock. With it off
# ACTION_DIMS and everything else are as before.
LEGS_KEYS_ADD = LEGS and float(os.environ.get("LEGS_KEYS_ADD") or 0.0) > 0
KA_COLS = (0, 1, 2, 7, 8)                                   # forward/back, sideways, jump/crouch, walk, zoom
KA_SHUT = 30.0
PLAY_VARS = PLAY_VARS + ("LEGS_KEYS_ADD",)


def turn_sum(turn, add):
    """(LEGS_TURN_ADD) his view's turn command: the legs' (or his own) turn plus his correction, cut to the largest turn
    a command can ask for; where the correction is 0 the turn is left exactly as it was"""
    t_ = np.asarray(turn, np.float32)
    a_ = np.asarray(add, np.float32)
    return np.where(a_ != 0.0, np.clip(t_ + a_, -float(TURN[-1]), float(TURN[-1])), t_).astype(np.float32)


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
#   QL_FLOAT=1    velocity is not cut to whole units after every move (Quake 3's SnapVector, kept in the library from Quake 3):
#                 Quake Live keeps it as it is (plugins/rjlab.py, 2026-10-15: speeds of 549.88, -202.08 and 69.8 u/s after
#                 moves, a fall's speed down by exactly 20 a frame). Cut, the simulator's gravity loses about one unit a
#                 frame (19 for the game's 20): every jump and fall in the air about 5% higher and longer than the game's
#                 (a plain jump 49.8 units high against 47.3; a rocket jump at his feet 198 against 189). Needs the
#                 library of 2026-10-15 (qsim_snap). Off: the simulator is v0.3's.
QL_FLOAT = float(os.environ.get("QL_FLOAT") or 0.0) > 0
#   QL_FWD=1      Quake Live's push with the forward (or back) key alone (B-258; plugins/physlab.py, 2026-10-16): where
#                 Quake 3's move gives nothing (he moves at the wish speed or faster along it) the game pushes him along
#                 the wish direction by 0.2059 x (640 - his speed) a second, to 640 and never as a brake (at 320: 1.65
#                 u/s a frame; the simulator had nothing), in the air and on the floor (after friction: he slows down
#                 less). With a strafe key held the game is Quake 3's, to 0.01 u/s. This is why running rocket jumps and
#                 short hops with forward held landed short (B-252).
#   QL_LAND=1     his fall's speed is put to nothing when he lands, as in the game: Quake 3's walk move turned it into
#                 speed along the floor when the floor was met just at the end of a move (a launch at 400 up, 320 along:
#                 the game 320 after the landing, the simulator 447). Both need the library of 2026-10-16 (qsim_params3).
#                 Off: the simulator is v0.3's.
#   QL_JUMP=1     Quake Live's jumps (B-258; plugins/physlab.py, the game's pmove_ChainJump, AirSteps, StepJump): a jump
#                 within 500 ms of the last is faster by 110 x (1 - ms / 500) (125 ms after: 357.5 against 275), none within
#                 100 ms; a move in the air that ends on a floor with the jump held is a jump at once (a stair, a ledge:
#                 holding jump up stairs and onto ledges is the game's double jump); rising, he steps onto a ledge up to a
#                 step high (Quake 3 does not), losing 3% of his speed. Library of 2026-10-16 (qsim_params4).
QL_FWD = float(os.environ.get("QL_FWD") or 0.0) > 0
QL_LAND = float(os.environ.get("QL_LAND") or 0.0) > 0
QL_JUMP = float(os.environ.get("QL_JUMP") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("QL_FLOAT", "QL_FWD", "QL_LAND", "QL_JUMP")   # (kept in a checkpoint: the physics it was trained in)
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
#   RULE_CONTEST=<seconds>   (2026-10-12; the owner: "we should be pushing him hard to prioritize knowing where the enemy is and
#                 how that should inform what he does next") the item rule, his intention's teacher through a whole run, names the
#                 nearest item he can use and never looks at the enemy: a template by construction. With the switch the rule's
#                 lesson is SILENT (a negative label, as where it names nothing under TARGETS) on the frames he believes the enemy
#                 (his own inputs' believed place, not the truth) nearer to the item it names than he is himself by this many
#                 seconds of way or more: there what he goes for is his own to find, by what it pays him. Nothing is paid, nothing
#                 else is taught. 0: off. A training switch: not a PLAY_VAR. Counted: stats["rule_contest"] (frames silenced,
#                 frames the rule named an item for one of his seats).
RULE_CONTEST = float(os.environ.get("RULE_CONTEST") or 0.0)
#   RULE_HUNT=<points>   (2026-10-16; the owner: "Silence the item lesson when hunting is reasonable", for the hunt, HUNT, which
#                 the item rule never names and so taught down on every reading: 1.2% of his intentions at update 10 of
#                 duel_gru_v0_3_1b, 0.1% at update 40) the item rule's lesson is SILENT (a negative label, as RULE_CONTEST) on the
#                 frames where, for one of his seats in a game: neither the mega nor the red armor is up or due within his way
#                 to it and 3 s (the rule's own "soon"), he owns a big weapon with ammunition (rockets, rail, lightning), the enemy is not in
#                 view, and his own stack (health + armor) is above the enemy's as he believes it (EN_STACK, his inputs) by
#                 this many points or more. There his choice is his own, by what it pays him. Nothing is paid, nothing else is
#                 taught. 0: off. A training switch: not a PLAY_VAR. Counted: stats["rule_hunt"] (frames silenced, frames the
#                 rule named an item for one of his seats).
RULE_HUNT = float(os.environ.get("RULE_HUNT") or 0.0)
#   RULE_BLIND=<seconds>   (2026-10-13; the owner: "he does not change aggression/decisions based on the enemy location or
#                 knowledge") the rule's lesson is SILENT (a negative label) on the frames he has a belief of the enemy's place
#                 fresher than this many seconds (his own inputs' belief, the frame before: never the truth): with nobody known
#                 about the rule speaks as before (the prior: go and get items), with a fresh belief what he goes for is his own
#                 to find, by what it pays him. The openings' label (OPENINGS) is untouched. 0: off. A training switch: not a
#                 PLAY_VAR. Counted: stats["rule_blind"] (frames silenced, frames the rule named an item for one of his seats).
RULE_BLIND = float(os.environ.get("RULE_BLIND") or 0.0)
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
#   JUMP_WEIGHT=1 (v0.3.6, the owner's go of 2026-10-18) a jump run's jump is drawn with weight max(JUMP_W_FLOOR, 1 - his
#                 success there) instead of every jump as often as any other: the jumps he fails get most of the practice,
#                 the ones he makes still some. His success: per jump of this map in each simulator, a running average of
#                 "over" per try (over as the counters have it: at the take-off, then within 110 units of the landing on
#                 the floor or at the item), prior 0.5; a try's weight is 1 / (tries + 2) at first (the prior counts two
#                 tries), then that of an exponential average with a half-life of JUMP_W_HALF tries. A try counts when the
#                 next one begins (over or not: a fall short, his time over, a death, the item reached) or at once when he
#                 gets over; a try cut by the run's end counts nothing. The counted seats only (count_even): his own tries.
#                 The estimate lives in the process (a restart begins at the prior again). A training switch: not a PLAY_VAR.
#   JUMP_FAR_P    (v0.3.6, the owner's go of 2026-10-18; his value 0.5) the share of jump runs' tries that begin further back:
#                 JUMP_FAR_LO to JUMP_FAR_HI seconds of way before the take-off (3 to 5; with less way to it, from the
#                 farthest fifth of what there is), on the same way as the near start (the jump the first one ahead, the
#                 item behind it the nearest of its kind), and moving along the way at JUMP_FAR_SPEED (300 units a second:
#                 about his speed in games), so that he builds the jump's speed himself. The near start is as before (a
#                 second or two of way, standing). Its try's time: twice the way's seconds and JUMP_TRY_SLACK, as before.
#                 Counted: stats["jump_far"] (JUMP_FAR_COLS). A training switch: not a PLAY_VAR.
JUMP_WEIGHT = float(os.environ.get("JUMP_WEIGHT") or 0.0) > 0
JUMP_W_FLOOR = float(os.environ.get("JUMP_W_FLOOR") or 0.1)
JUMP_W_HALF = float(os.environ.get("JUMP_W_HALF") or 200.0)
#   JUMP_W_DROP   (the owner, 2026-10-20: "any jump he's already making >80% of the time can go, and he should focus on the ones
#                 that are really low") with JUMP_WEIGHT, a jump whose success (jw_s) is at this or above gets no tries (its
#                 weight 0; if every jump of the map is there, all as often as any other). 0: off. A training switch.
#   JUMP_OVER_PAY (the owner, 2026-10-20: "he needs better reinforcement for making that leap") paid once a try when he gets over
#                 the jump in a jump run (over as the counters have it), never given back by a try that then ends without the
#                 item. Jump runs only: he is alone there, so the equilibrium is simply to clear the gap; nothing in games
#                 changes. 0: off. A training switch.
#   PRO_JSTART_P  (the owner, 2026-10-20: "give him more a fighting chance with it") the share of a jump run's tries at a jump that
#                 has the pros' run-ups (sim/pro_jump_starts/<map>.npz: pos, vel, yaw, lead in frames before the pros' take-off,
#                 from plain jumps that landed) that begin in a pro's own state 0.2 to 1 s before the take-off: his speed and
#                 line, so that he meets the edge as they do and learns to press jump there. 0: off. A training switch.
#   JUMP_FOCUS    "aerowalk:1": jumps (by id) whose jump-run weight is multiplied by JUMP_FOCUS_W (the owner: "he should get it
#                 tonight"). A training switch.
JUMP_W_DROP = float(os.environ.get("JUMP_W_DROP") or 0.0)
JUMP_OVER_PAY = float(os.environ.get("JUMP_OVER_PAY") or 0.0)
PRO_JSTART_P = float(os.environ.get("PRO_JSTART_P") or 0.0)
JUMP_FOCUS = {p_.split(":")[0].strip(): {int(x_) for x_ in p_.split(":")[1].split(",") if x_.strip()}
              for p_ in (os.environ.get("JUMP_FOCUS") or "").split(";") if ":" in p_}
JUMP_FOCUS_W = float(os.environ.get("JUMP_FOCUS_W") or 1.0)
#   JUMP_SKIP     "aerowalk:16" (the owner, 2026-10-21: "aerowalk jump 16 is nonsensical"): per map ("map:id,id;map:id"), the pros'
#                 jumps (by id) left out of the jump runs altogether: no tries, never drawn (the jump stays in his inputs, in
#                 JUMP_OPEN and in the counters' list). Unset: nothing left out. A training switch.
JUMP_SKIP = {p_.split(":")[0].strip(): {int(x_) for x_ in p_.split(":")[1].split(",") if x_.strip()}
             for p_ in (os.environ.get("JUMP_SKIP") or "").split(";") if ":" in p_}
#   STUCK_STARTS=1 (the owner, 2026-10-21: the stuck spots as practice in "advanced movement") the spots where he gets stuck in
#                 real games (sim/stuck_starts.json: map, start, his heading, the item he was going for) are tries of the jump
#                 runs beside the jumps: he begins there standing (a little apart, his heading +-30 deg), and the try is over
#                 when he reaches the first spot of his way STUCK_ESC units away (or 48 up or down), then he goes on to the item
#                 as after a jump. They are drawn as the jumps are (JUMP_WEIGHT: the ones he fails more), counted at the end of
#                 the map's jump list (v15.jumps). A training switch.
STUCK_STARTS = float(os.environ.get("STUCK_STARTS") or 0.0) > 0
#   JUMP_PAST_PICK=1 (2026-10-21: Blood Run's jump id 2 starts 33 u from the red armor, its try's target: he took it within a few
#                 frames, the try ended "arrived" before the jump, a new one began, ~16,000 tries a 40 s, each paying the pickup
#                 and the arrival; under JUMP_WEIGHT it took 73% of all jump-run draws) a jump run's own target item cannot be
#                 taken before he is past the jump (jrun_past: over it, or landed at its landing). A training switch.
JUMP_PAST_PICK = float(os.environ.get("JUMP_PAST_PICK") or 0.0) > 0
#   JUMP_KEEP_CLOSED=1 (the owner, 2026-10-21: "if a jump is failing in games remove that route from the games and put it back in
#                 the trainer") JUMP_W_DROP drops only the jumps open in games (JUMP_OPEN) and the stuck spots: a jump closed in
#                 games is practised whatever his success in the runs. A training switch.
#   JUMP_VARY=1   (the owner, 2026-10-21: "make sure there's enough variance in position, look dir, speed, etc. for the jump
#                 practice that he's learning generally how to make the jump") far starts at 220-420 u/s (not 300) and +-12 deg
#                 off the way; near starts half the time already moving (0-350 u/s, +-15 deg); a pro's run-up start +-8 u in
#                 place, +-8 deg and 0.9-1.1x in speed, +-20 deg in view. (Start spots were already many nodes along the way,
#                 the view +-40 deg.) A training switch.
JUMP_KEEP_CLOSED = float(os.environ.get("JUMP_KEEP_CLOSED") or 0.0) > 0
#   JUMP_W_CAP=<share> (2026-10-21: Blood Run's id 2, made ~1%, took two thirds of the map's tries once the others passed
#                 JUMP_W_DROP) no one jump gets more than this share of a map's jump-run draws (when enough jumps are drawn
#                 for it to be possible). 0: off. A training switch.
JUMP_W_CAP = float(os.environ.get("JUMP_W_CAP") or 0.0)
JUMP_VARY = float(os.environ.get("JUMP_VARY") or 0.0) > 0
#   JUMP_SOLID_FIX=1 (2026-10-21: Aerowalk's jump 4 had one start spot and the player box was inside solid there: 20 of 20 tries
#                 stood still; ~60 spots on nine maps were inside solid) a jump run's start spots (near and far) where the player
#                 box is in something solid are left out; an entry left with none is moved to the nearest free spot (up to 32 u
#                 up, 16 u aside, with a floor under it), or dropped. A training switch.
JUMP_SOLID_FIX = float(os.environ.get("JUMP_SOLID_FIX") or 0.0) > 0
#   JUMP_OVER_ANY=1 (the owner, 2026-10-21, on the video: Sinister 26 and Toxicity 10 "made it though and you marked it as a miss")
#                 a try is over the jump when he touches the floor (or hops off it) within 110 u of its landing, no more than 40 u
#                 below it (not in the air: a jump short passes near it), from a flight that left the floor at least 60% of the gap's length
#                 from the landing and no more than 48 u below the lower of take-off and landing: his own take-off counts, not
#                 only the pros'; a walk round does not (it touches the floor near the landing). A training switch.
#                 =2 (2026-10-21 evening: =1 counted hops onto the landing from beyond it and hops on a lower floor at its height:
#                 Battleforged 3, Hektik 15, Aerowalk 17) the flight must leave the floor on the take-off's side (at least half the gap
#                 back along the landing-to-take-off line) and within 48 u of the take-off's height; the landing ring is 128 u; and this
#                 is the only rule (the old one, "at the take-off once, at the landing later", counted walks round: Hektik 15).
#                 =3 (the owner, 2026-10-21, on Sinister 29: "attempt 3 is not really a success he lucked into it": a run-off dropped
#                 onto the floor 122 u short) as =2, and where he comes down must be at least the gap less 64 u along the line from
#                 the take-off to the landing (horizontal: dot(p - A, unit(B - A)) >= gap - 64): a drop short of it, inside the
#                 ring, is not over.
JUMP_OVER_ANY = float(os.environ.get("JUMP_OVER_ANY") or 0.0)
#   JUMP_RUNUP=<u/s> (the owner, 2026-10-21: Campgrounds' bridge-to-rail jump "is basically never going to work, you need two
#                 hops"; "aerowalk red armor is easier with two hops") the jumps whose take-off needs this speed or more (the pros'
#                 'need') begin their near tries JUMP_RUNUP_LO to JUMP_RUNUP_HI seconds of way back, moving along the way (220-420
#                 u/s), room for a hop or two; for every jump: near start spots within 40 u of the take-off (on its lip: Toxicity 7
#                 slid off every try) are left out (the run-up spots instead when none is left), and an entry with no far spots
#                 gets them from every way that has the jump first (not only the ways to the nearest item: Cure 8, Blood Run 2).
#                 0: off. A training switch.
JUMP_RUNUP = float(os.environ.get("JUMP_RUNUP") or 0.0)
JUMP_RUNUP_LO = float(os.environ.get("JUMP_RUNUP_LO") or 1.2)
JUMP_RUNUP_HI = float(os.environ.get("JUMP_RUNUP_HI") or 2.5)
#   PRO_JSTART_MAXLEAD=<frames> (PRO_JSTART_P) the pros' run-up states used: up to this many frames before their take-off
#                 (the files hold 8 to 80; 40 = what was used before 2026-10-21 evening; 80: two seconds, their hops included).
PRO_JSTART_MAXLEAD = int(os.environ.get("PRO_JSTART_MAXLEAD") or 40)
STUCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stuck_starts.json")
STUCK_ESC = float(os.environ.get("STUCK_ESC") or 200.0)
JUMP_FAR_P = float(os.environ.get("JUMP_FAR_P") or 0.0)
JUMP_FAR_LO = float(os.environ.get("JUMP_FAR_LO") or 3.0)
JUMP_FAR_HI = float(os.environ.get("JUMP_FAR_HI") or 5.0)
JUMP_FAR_SPEED = float(os.environ.get("JUMP_FAR_SPEED") or 300.0)
JUMP_FAR_COLS = ("near tries", "near over", "far tries", "far over")
assert 0.0 <= JUMP_FAR_P <= 1.0 and 0.0 < JUMP_W_FLOOR <= 1.0 and JUMP_W_HALF > 0 and JUMP_FAR_HI > JUMP_FAR_LO
#   JUMP_OPEN     "aerowalk:1;bloodrun:1,26": per map, the jumps (their numbers in its list) that his ways take in games and
#                 item runs too: the inputs of his way, its pay, the item rule and the item runs' targets follow the
#                 walking map with those jumps (route_o). Scripted players keep the walking map's ways. A jump is opened
#                 when he is measured to make it in jump runs (tools/jump_check.py, the trainer's v15.jumps).
JUMP_OPEN = os.environ.get("JUMP_OPEN") or ""
# Rocket jump runs (B-252, 2026-10-16; sim/rocket_jumps.py), all off by default (with them off the simulator is v0.3.1's,
# by fixed runs). Meant with RL_QL=1 and the physics switches (QL_FLOAT, QL_FWD, QL_LAND, QL_JUMP): v0.3's rockets jump
# 60 units too low (RESULTS 2026-10-15 21:25).
#   RJ_RUN_P      the share of the playing time in rocket jump runs (beside ITEM_RUN_P and JUMP_RUN_P, from the same
#                 draw): he is put 30 to 90 units of way (RJ_BACK) before the take-off of one of the pros' rocket jumps on the map
#                 (docs/pro_rocket_jumps.json; every link as often as any other), facing its landing, with the machine gun
#                 and the rocket launcher in his hand (RJ_AMMO rockets) and the pros' health and armor at that take-off
#                 (their median; sim/rocket_jumps.stack). His target is the landing: his way's inputs lead there through
#                 the link (the five jump inputs show it as a jump ahead that needs no speed, N_JUMP). He ARRIVES when he
#                 comes down within 110 units of the landing from a flight of 8 frames or more that passed the take-off (120
#                 units about it, on the floor or in the air): paid RJ_ARRIVE, once, the next try at once. Nothing is paid for the way,
#                 for speed, or for a near miss (the owner, 2026-10-10: "the pros' take-off and landing places only count");
#                 the health a rocket costs him is priced as in games (damage taken). A try ends without pay when he stands
#                 on the floor outside the take-off and away from the landing after having been at the take-off, when he
#                 dies, or after RJ_TRY seconds plus the flight's. His legs (LEGS) and the movement and walking teachers are
#                 silent in these runs: his own keys, view and trigger move him. Counted: stats["rj_tries"],
#                 stats["rj_over"] (per link of the map, its number in the list less one), stats["rj_frames"],
#                 stats["rj_shots"] (rockets he fired in them).
#   RJ_LOOK_P     the share of the tries that begin with his view already down at the pros' look-down of that link
#                 (their median, within 5 degrees): the jump and the shot still his (the proposal's first rung). 0: level.
#   RJ_CLEARED=1  the runs and RJ_OPEN take only the rocket jumps that tools/rj_check.py clear found a scripted player with
#                 the right keys to clear in this simulator (sim/rj_clear.json: 77 of the 174 on the walking maps, 2026-10-16):
#                 a run must not ask for what cannot be done (Aerowalk's red armor in v14)
#   RJ_BACK       "30,90": a try begins this many units of way (the walking map's, to the take-off) before the take-off;
#                 "200,600" gives room for a run-up or a strafe jump in (the check: tools/rj_check.py clear)
#   RJ_ARRIVE     the pay for an arrival (default 0.5: an item run's or a jump run's arrival, RUN_ARRIVE)
#   RJ_OPEN       "bloodrun:1,3;aerowalk:all": per map, the rocket jumps (numbers in its list) his ways in games and item
#                 runs take while he holds the rocket launcher with a rocket and RJ_OPEN_HP or more of health and armor:
#                 his way's inputs and its pay follow those ways (the item rule, the item runs' targets and the scripted
#                 players keep theirs). A link costs its flight's seconds plus RJ_OPEN_COST (the health and the rocket).
#                 Open a link only when he is measured to make it in the runs (stats["rj_over"]): a way that names what he
#                 cannot do costs a map (Aerowalk in v14).
RJ_RUN_P = float(os.environ.get("RJ_RUN_P") or 0.0)
RJ_LOOK_P = float(os.environ.get("RJ_LOOK_P") or 0.0)
RJ_ARRIVE = float(os.environ.get("RJ_ARRIVE") or 0.5)
RJ_AMMO = float(os.environ.get("RJ_AMMO") or 10.0)
RJ_TRY = float(os.environ.get("RJ_TRY") or 2.5)
RJ_OPEN = os.environ.get("RJ_OPEN") or ""
RJ_OPEN_COST = float(os.environ.get("RJ_OPEN_COST") or 1.0)
RJ_OPEN_HP = float(os.environ.get("RJ_OPEN_HP") or 150.0)
RJ_CLEARED = float(os.environ.get("RJ_CLEARED") or 0.0) > 0   # only the rocket jumps a scripted player clears (sim/rj_clear.json)
RJ_BACK = tuple(float(x_) for x_ in (os.environ.get("RJ_BACK") or "30,90").split(","))   # units of way before the take-off a try begins (from, to)
RJ_EDGE, RJ_LAND = 120.0, 110.0                       # (the take-off's reach about it, the landing's: as the jump runs')
#   RJ_ONLY       "aerowalk:1" (the owner, 2026-10-23: rocket jump practice for Aerowalk's red armor only): per map the rocket
#                 jumps (numbers in its list) the runs may take; the runs are on those maps only (on the others a draw that
#                 would be a rocket jump run is what it would be without them), within RJ_CLEARED's list when that is on. With
#                 it set the runs' ways are built at the start even at RJ_RUN_P=0, so that RJ_RUN_P can be opened from 0 by
#                 live_settings.env (the trainer's LS_SPEC). RJ_OPEN is not limited by it. Unset: as before
#   RJ_FROM_JUMP=1 (the owner, 2026-10-23: rocket jumps are part of the 10% of advanced movement): on a map with rocket
#                 jump runs their share comes out of JUMP_RUN_P's (jump runs at JUMP_RUN_P - RJ_RUN_P, at least 0), so the runs
#                 together stay at JUMP_RUN_P; on a map without them the jump runs keep JUMP_RUN_P. Off: on top, as before
RJ_ONLY = os.environ.get("RJ_ONLY") or ""
RJ_FROM_JUMP = float(os.environ.get("RJ_FROM_JUMP") or 0.0) > 0
#   RJ_LOOK_CLEAR=1 (2026-10-23): RJ_LOOK_P's look-down is the pitch of the execution that cleared the link in this
#                 simulator (sim/rj_clear.json "first": Aerowalk 1 at 70 degrees), not the pros' median (47 there, which does
#                 not clear it in the run's physics); a link with no such entry keeps the pros'. Off: the pros', as before
RJ_LOOK_CLEAR = float(os.environ.get("RJ_LOOK_CLEAR") or 0.0) > 0
#   RJ_TEACH=1    (the owner, 2026-10-23: a lesson on the moment of the jump only) step() gives info["rj_lab"]: per player 1
#                 where the label says "jump and fire now" for his NEXT frame, 0 elsewhere (int8). Given only in a rocket jump
#                 run (RJ_RUN_P), alive and his own (no script), on the floor within RJ_TEACH_R units (horizontally; 30 in
#                 height) of the try's take-off, the rocket launcher in hand with a rocket and ready to fire by the next frame,
#                 his view RJ_TEACH_PITCH degrees or more down. Labels only: where he stands, how he looks and his air steering
#                 stay his own, the pay is unchanged (the landing only). The trainer's --rj-teach (live RJ_TEACH_W) grades his
#                 vertical key (jump) and his trigger toward it, each on the frames it is read. Off: no label, nothing else
#                 changes (the label is never an input and draws nothing from the random stream)
RJ_TEACH = float(os.environ.get("RJ_TEACH") or 0.0) > 0
RJ_TEACH_R = float(os.environ.get("RJ_TEACH_R") or 48.0)
RJ_TEACH_PITCH = float(os.environ.get("RJ_TEACH_PITCH") or 60.0)
#   RJ_LOOK_FREE=1 (off by default; 2026-10-23, found building RJ_TEACH): in a rocket jump run his view does not ease back
#                 toward level (the pull of 0.95 a frame with nobody in view, self.level): a try begun at 70 degrees down is at
#                 54 when he lands from the placing with still hands, and his view at the take-off was 10 to 15 degrees down on
#                 average in the tests, so RJ_TEACH's condition (60 or more) was met on no frame. Off: the pull, as before.
#                 RJ_TEACH_PITCH, RJ_TEACH_R and RJ_LOOK_FREE are live (the trainer's live_settings.env, "frame")
RJ_LOOK_FREE = float(os.environ.get("RJ_LOOK_FREE") or 0.0)
#   LEVEL_PULL=x  (B-275, v0.4.3; a PLAY_VAR and a live name) the view's pull toward level: with no enemy in view his pitch is
#                 times x every frame (env.level reads it; 1.0 = no pull). Unset: 0.95, the pull of 2026-10-03 exactly. The
#                 phase-out 0.95 -> 0.98 -> 0.99 -> 0.995 -> 1.0 by the run's live.json; the checkpoint's env_vars carry it
#                 (the trainer's environment), sim/export_duel.py writes it and the plugins set it before loading the simulator.
_lp_ = os.environ.get("LEVEL_PULL")
LEVEL_PULL = float(_lp_) if (_lp_ or "").strip() else 0.95
if not 0.0 <= LEVEL_PULL <= 1.0:
    raise ValueError("LEVEL_PULL must be within 0 .. 1")
PLAY_VARS = PLAY_VARS + ("LEVEL_PULL",)
PLAY_VARS = PLAY_VARS + ("WEAPON_FREE", "GONE_BELIEF", "TELEFRAG", "PERCEPT_SPEED_MAX", "PERCEPT_SPEED_MAX_RG", "PERCEPT_SPEED_MAX_LG")                   # (v0.5.0: a weapon he holds is no target; see WEAPON_FREE)
#   RJ_COPY=1     (the owner, 2026-10-23, "option 1": "one route that works that he has to use when he wants to get there") the
#                 whole route as a lesson: step() gives info["rj_copy"], per player and output (int8, -1 = no label) the scripted
#                 runner's choice for his NEXT frame in a rocket jump run (RJ_RUN_P), from the try's start to its landing: his
#                 forward, side and vertical keys, the view's turn and pitch commands, the trigger, the weapon key (keep with the
#                 launcher in hand, else the launcher), walk (on his way to the take-off) and zoom (off). The runner is the execution that cleared Aerowalk's
#                 red armor (sim/rj_clear.json "first": standing at the take-off, the view down at 70 degrees toward the landing,
#                 jump and fire on the same frame, forward held in the air), run as a policy on his state as the frame ends,
#                 never a tape: facing the jump (the take-off toward the landing), he steps to the take-off with the keys
#                 (aiming where his speed would stop him, Quake's friction), brings the view to the jump's yaw and RJ_COPY_PITCH
#                 down with commands chosen through his own mouse (the smoothing, the flick cap, HAND_BAND's low-pass and the
#                 ease toward level, a few frames ahead), and on the floor within RJ_COPY_R of the take-off, slower than
#                 RJ_COPY_V, the view within RJ_COPY_YAW of the jump's yaw and RJ_COPY_PTOL of its pitch and the launcher ready
#                 by the next frame: jump and fire; in the air from the take-off: forward, nothing else (a shot not yet fired:
#                 fire within RJ_COPY_LATE frames of leaving the floor). The finger limits, the key rate and the mouse act on
#                 the labels as on his own choices (a player who presses the labels is held to his hands: tools/rj_copy_check.py).
#                 Silent: not in a try, dead, a scripted seat, 40 units or more below the take-off (fallen off), more than
#                 RJ_COPY_FAR from it, or in the air without having left from it. Labels only, never an input, no draw from the
#                 random stream; the pay is unchanged. Counted (his counted seats): stats["rj_copy"] = [labelled frames, tries
#                 ended, arrived, died, health and armor lost in them, tries that lost RJ_COPY_BIG or more]. The trainer's
#                 --rj-copy (live RJ_COPY_W). Meant with RJ_LOOK_FREE=1 (the pupil test, 2026-10-23: 80% of tries over with it,
#                 50% with the ease toward level). Off: no label, nothing else changes
RJ_COPY = float(os.environ.get("RJ_COPY") or 0.0) > 0
RJ_COPY_PITCH = float(os.environ.get("RJ_COPY_PITCH") or 72.0)
RJ_COPY_R = float(os.environ.get("RJ_COPY_R") or 24.0)
RJ_COPY_V = float(os.environ.get("RJ_COPY_V") or 20.0)
RJ_COPY_YAW = float(os.environ.get("RJ_COPY_YAW") or 5.0)
RJ_COPY_PTOL = float(os.environ.get("RJ_COPY_PTOL") or 4.0)
RJ_COPY_LATE = int(os.environ.get("RJ_COPY_LATE") or 2)
RJ_COPY_FAR = float(os.environ.get("RJ_COPY_FAR") or 250.0)
RJ_COPY_BIG = float(os.environ.get("RJ_COPY_BIG") or 60.0)
RJ_COPY_DEAD = float(os.environ.get("RJ_COPY_DEAD") or 8.0)
RJ_COPY_H = int(os.environ.get("RJ_COPY_H") or 4)
RJ_COPY_VW = float(os.environ.get("RJ_COPY_VW") or 3.0)
RJC_HEADS = 9                                          # (RJ_COPY) the outputs labelled: keys 0-2, turn 3, pitch 4, fire 5, weapon 6, walk 7, zoom 8
#   ROUTE_COPY=aerowalk_ra[:circle|:hop2] (the owner, 2026-10-23 evening: "one route that works", in the jump runs, no rocket
#                 jump) the whole route to Aerowalk's red armor over the pros' gap jump (sim/pro_gaps/aerowalk.json id 1) as a
#                 lesson: step() gives info["rj_copy"] (as RJ_COPY: per player and output, int8, -1 = none) the scripted
#                 runner's choice for his NEXT frame in a jump run's try at that jump, from the try's start to the armor. Two
#                 routes (sim/route_copy_aerowalk_ra.json, from tools/route_copy_ref.py: the open-loop execution that clears
#                 the gap from the most of 9 starts): "circle", a circle jump from a standing start about 95 units behind the
#                 take-off, and "hop2", a circle-jump hop from about 330 back and the gap jump on its landing (the jump held:
#                 AUTO_HOP). Each try draws one (a stream of its own, ROUTE_COPY_P the share of circle; ":circle" or ":hop2"
#                 one only; the pupil test, tools/rj_copy_check.py --route, 2026-10-23: hop2 62 to 66% of tries at the armor in
#                 three samples of about 350, circle 6%: the standing circle jump leaves at 370 u/s, the gap asks about 425, and
#                 even the open loop with the view put exactly made it from 4 of its 9 starts; use ":hop2"). The runner as a
#                 policy on his state as the frame ends: (0) away from the staging spot's level or 250 units from it: along his
#                 try's way, running, the view toward the way two spots ahead (never across a jump: to the staging spot
#                 instead); near it, on the floor, not in the maneuver: walk to the route's staging spot (where his speed would
#                 stop him), the view to its start yaw; (1) at it,
#                 slow and facing: the maneuver, its frame found by his place and velocity (the nearest of the next few
#                 reference frames; off by more than ROUTE_COPY_TOL: back to 0): the reference's keys, its view yaw a few
#                 frames ahead (and its turn rate) turned by the angle between his velocity and the reference's, the jump where the reference
#                 jumps or he is past it; (2) the hop's flight (hop2): air strafing toward 60 units past the take-off (the
#                 strafe key by the side his velocity must turn to, the view ROUTE_COPY_MARGIN degrees past the angle that
#                 gains most: a hand a few degrees short of it gains nothing), the jump held as he comes down; (3) the gap's
#                 flight (from the hop's landing, also when he touches down and leaves inside one frame): air strafing toward
#                 the landing; (4) over it: walk onto the armor.
#                 The view through his own mouse (RJ_COPY's chooser), the keys through his hand. Silent: another jump's
#                 try, dead, a scripted seat, 64 units or more below the take-off on the floor, down off the landing's
#                 ledge after the gap, more than ROUTE_COPY_FAR from the take-off. Labels only, never an input, no draw from
#                 the simulator's random stream; the pay is unchanged. Counted (his counted seats): stats["route_copy"] =
#                 per route [labelled frames, tries ended, over the gap, at the armor (the run's arrival), fallen short].
#                 The trainer's --rj-copy (live RJ_COPY_W). Off: nothing changes
ROUTE_COPY = os.environ.get("ROUTE_COPY") or ""
ROUTE_COPY_P = float(os.environ.get("ROUTE_COPY_P") or 0.5)
ROUTE_COPY_TOL = float(os.environ.get("ROUTE_COPY_TOL") or 40.0)
ROUTE_COPY_FAR = float(os.environ.get("ROUTE_COPY_FAR") or 900.0)
ROUTE_COPY_LEAD = int(os.environ.get("ROUTE_COPY_LEAD") or 2)
ROUTE_COPY_HYST = float(os.environ.get("ROUTE_COPY_HYST") or 3.0)
ROUTE_COPY_GAIN = float(os.environ.get("ROUTE_COPY_GAIN") or 0.6)
ROUTE_COPY_HOPX = float(os.environ.get("ROUTE_COPY_HOPX") or 60.0)    # (hop2: the hop's flight aims this far past the take-off)
ROUTE_COPY_MARGIN = float(os.environ.get("ROUTE_COPY_MARGIN") or 24.0)   # (degrees past the strafe angle that gains most: his
#                                                        hand is a few degrees off, and short of that angle nothing is gained)
ROUTE_COPY_STAGE = float(os.environ.get("ROUTE_COPY_STAGE") or 14.0)
ROUTE_COPY_SYAW = float(os.environ.get("ROUTE_COPY_SYAW") or 8.0)
RC_WISH, RC_DTS = 320.0, 0.008                         # (the strafe angle: Quake's wish speed, the move's step)


def rc_steer(vel, tgt, side, ground, extra):
    """(ROUTE_COPY) view yaws [k] for forward + the side key (side +1 = right, -1 = left): the wish direction at the angle
    to the velocity that gains most, turned toward the side; extra degrees beyond it turn the velocity faster"""
    v = np.hypot(vel[:, 0], vel[:, 1])
    h = np.where(v > 30, np.degrees(np.arctan2(vel[:, 1], vel[:, 0])), tgt)
    acc = np.where(ground, 10.0, 1.0) * RC_WISH * RC_DTS
    th = np.where(v > RC_WISH - acc, np.degrees(np.arccos(np.clip((RC_WISH - acc) / np.maximum(v, 1e-3), -1.0, 1.0))), 0.0)
    th = np.minimum(88.0, th + extra)
    return h - side * th + side * 45.0
RJ_ONLY_MAP = {}
for part_ in RJ_ONLY.split(";"):
    if ":" in part_:
        RJ_ONLY_MAP[part_.split(":")[0].strip()] = {int(x_) for x_ in part_.split(":")[1].split(",") if x_.strip()}
PLAY_VARS = PLAY_VARS + ("RL_QL", "RJ_OPEN", "RJ_OPEN_COST", "RJ_OPEN_HP", "RJ_CLEARED")
#   TEACH_BEST=1  the movement teacher's labels are its likeliest choice per output, not a sample of its choices (B-201: a
#                 pupil of sampled labels learned its spread with it; tools/label_check.py --best says what they are worth)
TEACH_BEST = float(os.environ.get("TEACH_BEST") or 0.0) > 0
#   GL_QL=1       grenades and splash as measured in the game on 2026-10-10 (plugins/weaponlab.py set 4, data/weaponlab5): a
#                 bounce keeps the rest of its frame (the grenade came to rest 10 to 40% short of the game's), and splash
#                 reaches a player when the line from the blast to his middle or to one of four points 15 units beside it
#                 is clear (the game's CanDamage), not only the line to his middle
GL_QL = float(os.environ.get("GL_QL") or 0.0) > 0
#   RL_QL=1       rockets as measured in the game on 2026-10-15 (plugins/rjlab.py: 600 scripted rocket jumps on the test map
#                 and Blood Run; B-252): a rocket leaves on the frame of the command (not one frame after it), from the
#                 muzzle at the first of the frame's three moves (eye RL_EYE above his origin, 14 units ahead, cut to
#                 whole units as in Quake 3) and is RL_AHEAD units further on at that frame's end (the game's prestep); its
#                 blast point is cut to whole units toward where it came from; splash reaches a player's box grown by
#                 RL_BOX a side (fitted: 0.5 best, Quake 3's absmin / absmax are grown by 1), with no SPLASH_NEAR; RL_EYE
#                 and RL_AHEAD fitted too, on his own rockets and on weaponlab's rockets at the floor before another (26 is
#                 Quake 3's view height); damage in whole points as Quake 3 counts
#                 them (84 x falloff cut, halved and cut on oneself, at least 1); the push is 5 u/s per point of 100 x
#                 falloff times 1.1 on oneself and 0.9 on others (the game's: 550 u/s at a rocket at one's own feet, 450 at
#                 another's). Checked on others with weaponlab's rockets at the floor 0 to 140 units before a player
#                 (data/weaponlab2, 2026-10-07): within 2 to 6 points; weaponlab aimed from the placed height, 2 units
#                 above the resting eye, so its 'splash acts 20 units closer' (SPLASH_NEAR) was its own aim.
#                 Off: the simulator is v0.3's.
RL_QL = float(os.environ.get("RL_QL") or 0.0) > 0
RL_EYE, RL_AHEAD, RL_BOX, RL_KNOCK_BASE, RL_KNOCK_SELF, RL_KNOCK_OTHER = 26.5, 41.0, 0.5, 100.0, 1.1, 0.9
#   MISSILE_POINT=1  (B-267's finding, 2026-10-19) rockets, grenades and plasma fly as a point, as in Quake 3 (fire_rocket,
#                 fire_grenade and fire_plasma leave the missile's mins and maxs at zero; G_RunMissile traces a point).
#                 Until now each frame's step was qsim_rays_md's trace of a 2 x 2 x 2 box (the wall sensors' box): a rocket
#                 met a step's nosing a unit early and blew up about a unit further from the face. With the switch the
#                 projectiles' frame is Quake 3's (_fly_point): a point trace a frame; a grenade follows its parabola
#                 exactly (TR_GRAVITY: the frame's move is v t - 400 t^2, not the Euler step that falls 0.25 units a frame
#                 more); an impact (a wall, a player) blows up at the trace's end cut to whole units toward the missile's
#                 trBase (SnapVectorTowards: the muzzle, or a grenade's last bounce); a grenade's fuse blast at its place
#                 cut to whole units (SnapVector), after that frame's bounce; a bounce reflects the velocity of "the moment
#                 of the hit" (as Quake Live takes it, measured: see _fly_point), keeps GL_BOUNCE of it, puts the grenade
#                 one unit off the surface and loses the rest of the frame (trTime = level.time; GL_QL's "rest of the
#                 frame" is not used); when the surface faces up (normal z > 0.2) and less than 40 u/s is left it lies
#                 still (TR_STATIONARY) one unit off the surface, cut to whole units (as weaponlab5's grenade at rest).
#                 Checked on weaponlab5 (data/weaponlab5, 2026-10-10): 37 bounces of 37 within 0.2 units and 1 u/s of
#                 the game's (switch off: none within 0.2, 3 within 1 u/s). Not modelled: a missile that meets a sky
#                 surface (SURF_NOIMPACT) vanishes in the game; here it still blows up there (the library gives no
#                 surface flags). RL_QL's first stretch (a point trace already) is as it was. On a server the game does
#                 its own physics: the plugins need nothing. Off: the simulator is today's.
MISSILE_POINT = float(os.environ.get("MISSILE_POINT") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("MISSILE_POINT",)
# (MISSILE_POINT with RL_QL) RL_QL's fitted numbers for a point: a box's trace met the floor about a unit sooner and blew
# up about a unit further from it, so the fit of 2026-10-15 is taken again on the same rjlab records (tools/rj_compare.py,
# the test map's 486 jumps and Blood Run's 90; branch v037-missile, 2026-10-19): the first stretch one unit longer (42;
# 41 put 22 blasts a frame late), the splash box grown 1.5 a side (Quake 3's absmin / absmax grow by 1: damage exact in
# 398 of 486 with 1, 410 with 1.5, as with the box and 0.5), the muzzle's height as before (26.5; 26: rise within 5% in
# 471 of 486 against 479)
RL_AHEAD_PT, RL_BOX_PT, RL_EYE_PT = 42.0, 1.5, RL_EYE
PLAYER_MASK = 0x2010001                                 # MASK_PLAYERSOLID (what a trace with mask=None stops at), for qsim_lines_m
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
#   HOP_QUIET=1   (v0.3.4, a pay change the owner approved on 2026-10-17) HOP_PAY pays nothing on the frames where, by his own
#                 senses, the enemy is near: he heard him in the last HOP_QUIET_HEARD seconds (the hearing clock of the belief
#                 inputs, v02_ht), or believes him within HOP_QUIET_NEAR units (v02_bel), or his intention is one of the map's
#                 holding places. Equilibrium in self-play: both sides are paid less for noisy speed near each other, so
#                 the approaches near the enemy get quieter while speed away from him is paid as before (goals 1 and 3:
#                 speed and movement where it is free, positioning near the enemy). Counter: hop_quiet (take-offs it silenced).
HOP_QUIET = float(os.environ.get("HOP_QUIET") or 0.0) > 0
# AWARE_LOG=1   (2026-10-18, the owner: "anything to help us confirm that he's doing the things we want him to") measuring
#               only: counters of the awareness check (tools/awareness.py) in training, the counted seats in games (not runs):
#               moving (250 u/s and over) with the enemy alive and not in view, his yaw within 30 degrees of the believed
#               place (at most 5 s old) and of the true one; after a new enemy sound (none for 1 s before, not in view, not
#               already faced) the time until he faces it (0.1 s bins to 2 s, then never); his speed and take-offs in view,
#               unseen with the enemy near (heard within 2 s or believed within 700 units), unseen and far. Nothing is paid.
AWARE_LOG = float(os.environ.get("AWARE_LOG") or 0.0) > 0
HOP_QUIET_HEARD = float(os.environ.get("HOP_QUIET_HEARD") or 4.0)   # (2026-10-18: settings; the owner's run sets 1 s and 300 units)
HOP_QUIET_NEAR = float(os.environ.get("HOP_QUIET_NEAR") or 700.0)
PLAY_VARS = PLAY_VARS + ("HOP_QUIET", "HOP_QUIET_HEARD", "HOP_QUIET_NEAR")
# v0.3.4 D: WALK_NO_JUMP=1 (a PLAY_VAR; the owner's hard rule of 2026-10-17: in the game a held walk key does not stop a
# jump, so walking means jump off): wherever his walk key is on as his hands and legs leave it, before the finger limits,
# his jump (the vertical key's 1) is let go. Counter: walk_jump (frames of policy seats with both asked, before the rule).
WALK_NO_JUMP = float(os.environ.get("WALK_NO_JUMP") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("WALK_NO_JUMP",)
# v0.3.4 C: SOLO_SELF=1 (a training switch, not a PLAY_VAR: the trainer's --solo-self-drive sets it) in item runs and jump
# runs (run_k >= 0: no enemy) his legs do not carry him: he drives himself. The legs are still worked out as before (the
# simulator's random numbers are the same), only their choices are not taken there; the switch input reads "off" there.
SOLO_SELF = float(os.environ.get("SOLO_SELF") or 0.0) > 0
# v0.3.5, one movement network step 6: NO_SWITCH=1 (a PLAY_VAR) retires the switch to his legs: it is read as "my own
# movement" for every seat on every frame (the output stays in ACTION_DIMS, so every other output's draw is as before);
# his own network always drives. The legs' network is still worked out by whoever feeds it (legs_prep) for the parts that
# read it (legs_door, the gate and its motor layer), never to move him.
NO_SWITCH = float(os.environ.get("NO_SWITCH") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("NO_SWITCH",)


def walk_no_jump(a):
    """(WALK_NO_JUMP) a [players, outputs], in place: where the walk key (7) is on, the jump (vertical key 1) let go.
    Returns the rows that had both."""
    if a.shape[1] <= 7:
        return np.zeros(len(a), bool)
    both = (a[:, 7] == 1) & (a[:, 2] == 1)
    a[both, 2] = 0
    return both
HOP_GROUND, HOP_SLOW, HOP_GIVEN, HOP_VZ = 0.4, 250.0, 40.0, 400.0     # (a jump gives 275 upward, 385 soon after another; a pad more)
#   JUMP_COST=<c> (v0.3.9, live; the owner, 2026-10-21: "pay for hops that encourages NOT doing this [re-earning the 320->480 hop
#                 pay by starting new chains] and also not just spamming hop. He should use jumping to get placed quickly.
#                 Period.") a flat cost of c for every take-off of a network's seat (the take-off as HOP_CHAIN's, worked out on
#                 its own: the jump key down, off the floor, rising at a jump's speed, 100 < vz < HOP_VZ, from the floor or
#                 touching it inside the frame), alive, with no enemy in view (`visible`), in NORMAL rounds and item runs only
#                 (not jump runs, rocket jump runs, the test map's rooms). Not in r_long, nothing in `dealt`. With HOP_PAY and
#                 HOP_CHAIN off, jumping pays only through SPEED_PAY (speed over new ground on his way, not farmable), so a hop
#                 that does not buy speed is a small loss. Equilibrium: hop when it makes the way faster, not otherwise (each
#                 side alone pays its own; nothing passes between them: goal 1, speed and movement). With the enemy in view it
#                 costs nothing (the owner, 2026-10-19: few jumps in fights, his own choice there). 0: off. Counted:
#                 stats["jump_cost"] (JC_COLS, the counted seats).
JUMP_COST = float(os.environ.get("JUMP_COST") or 0.0)
JC_COLS = ("player-frames where it applies (alive, no enemy in view)", "take-offs costed", "cost summed")
# v0.3.7 (the owner's go of 2026-10-19), three switches, all off (or as today) by default:
#   JUMP_EVERY=<share> (a PLAY_VAR, live; 1 = always) the jump key read from his output on every frame (on that share of the
#                 frames between his hand's readings, drawn per seat and frame from a random stream of its own): his left hand
#                 still decides its other keys
#                 (forward and back, strafe, crouch, walk, the weapon key) once in KEY_EVERY frames, but whether the jump is
#                 down is taken from his vertical output (none, jump, crouch: "jump" or not) on every frame. Humans time a
#                 press to the millisecond; the finger limit is how often, not when: the thumb's FINGER_HOLD and the hand's
#                 KEY_RATE budget count every press and release as before. Crouch stays his hand's last reading (a jump asked
#                 in between wins, as in one reading). The trainer credits the vertical output on the hand's frames as
#                 before, and on the frames between for its jump bit alone (train_duel_rnn's JumpCat: the value 3 = "not
#                 jump"). Off: the 4-frame grid of v0.3.6 (he could not time a jump to a landing better than 0 to 3 frames).
#                 Set (any value, 0 too) it is on: a network trained on the grid has never been asked for its jump between the
#                 hand's readings (v0.3.6 read at JUMP_EVERY=1 pressed 44 times a minute instead of 24 and ran 6% slower,
#                 RESULTS 2026-10-19), so a run can start at a small share and raise it in live.json (B-265); at 0 everything
#                 is as off. key_jump [players]: this frame his jump was read between the hand's readings (the worker sends
#                 key_dec + 2 key_jump to the trainer). Counter: stats["jump_every"] (JE_COLS), the network's seats.
#   AUTO_HOP=0|1  (a PLAY_VAR, 1 = today) the movement code's pm_autoHop (qsim QL_PARAMS auto_hop): 1, a jump key held over a
#                 landing jumps again (the game's cg_autoHop 1); 0, a jump needs a new press (released and pressed again).
#                 sim/export_duel.py writes it into every policy.npz and the plugins put the bot's cg_autoHop to match.
#   HOP_CHAIN     (a pay; live, B-265; 0 = off) a chain of hops: jumps that each take off within HOP_CHAIN_MS of the last
#                 landing (any floor; a take-off as HOP_PAY's: the jump key down, rising at a jump's speed). A hop in a chain
#                 is paid when its take-off speed over the ground is at least the chain's best take-off so far less
#                 HOP_CHAIN_TOL (kept or gained); one that loses more ends the chain and begins a new one, unpaid. The pay of
#                 the k-th hop of a chain (k >= 2): HOP_CHAIN x min(HOP_CHAIN_CAP, 1 + HOP_CHAIN_STEP x (k - 2)) x
#                 clip((speed - SPEED_LO) / (SPEED_HI - SPEED_LO), 0, 1): 1, 1.5, 2, 2.5, 3 (the cap) for the 2nd to 6th
#                 hop, nothing for hopping under 320. The test is against the chain's running best, so speed lost and won
#                 back pays nothing more: a setback past the tolerance ends the chain and its multiplier. A chain also ends on
#                 the ground for longer than HOP_CHAIN_MS, with speed given in one frame (over HOP_GIVEN: a teleporter, a pad,
#                 a blast), at a death, and whenever the enemy is in his view (the awareness counters' notion: `visible`, or
#                 aimed at / acquired): the owner, 2026-10-19, "you really dont want to jump in fights it makes you easy to
#                 hit". A hop in view pays nothing, begins no chain and keeps none, so a chain cannot be carried through a
#                 fight for its multiplier: the pay is for traversal with the enemy unseen. Paid to the network's seats in
#                 games (under HOP_QUIET not where it silences HOP_PAY) and in item runs; not in jump runs and rocket jump
#                 runs, whose take-off is the pros' place and its approach, not a chain. Beside HOP_PAY, which pays the speed a
#                 chain gains above its best (at most 160 units' worth a chain): HOP_CHAIN pays each hop that keeps the speed, by
#                 the chain's length; on a gaining hop each pays its own part (the gain, the hop). HOP_CHAIN alone: HOP_PAY=0
#                 (both live). Not in r_long, nothing of it in `dealt`. Counters: stats["hop_chain"] (HC_COLS, then a
#                 histogram of the chains' lengths as they end, 1 to HC_BINS and over), the network's seats alive.
JE_ON = (os.environ.get("JUMP_EVERY") or "").strip() != ""     # (the machinery: the trainer's JumpCat, the codes sent with key_dec)
JUMP_EVERY = min(1.0, max(0.0, float(os.environ.get("JUMP_EVERY") or 0.0)))    # (the share; read at every frame: live)
AUTO_HOP = float(os.environ.get("AUTO_HOP") or 1.0) > 0
PLAY_VARS = PLAY_VARS + ("JUMP_EVERY", "AUTO_HOP")
JE_COLS = ("frames_between", "presses_between", "presses_grid", "releases_between", "releases_grid")
HOP_CHAIN = float(os.environ.get("HOP_CHAIN") or 0.0)
HOP_CHAIN_MS = float(os.environ.get("HOP_CHAIN_MS") or 150.0)
HOP_CHAIN_TOL = float(os.environ.get("HOP_CHAIN_TOL") or 15.0)
HOP_CHAIN_STEP = float(os.environ.get("HOP_CHAIN_STEP") or 0.5)
HOP_CHAIN_CAP = float(os.environ.get("HOP_CHAIN_CAP") or 3.0)
HC_COLS = ("takeoffs", "starts", "gained", "kept", "lost", "paid", "pay", "kept_unpaid", "takeoffs_view", "ended_view", "frames_view", "frames")
HC_BINS = 16
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
#   PAY_SPLIT=1   (record only; the pay is the same to the bit with it on or off) each frame's pay split by term:
#                 info["pay_terms"] [players, PAY_TERMS] (they sum to the frame's pay, to float rounding) and the counters
#                 stats["pay_terms"] [3, PAY_TERMS]: his counted seats' sums in every round, in whole games (a game under way
#                 at the frame's start), and the size (|x| summed, every round). A segment of step() between two marks goes
#                 to the mark's term; a few terms are booked where they are paid (damage dealt and taken, the item flats, the
#                 big three's order, the way, speed, frags, deaths, watching) and the segment around them keeps the rest
#                 ("..._other" terms are float rounding, or a pay of that segment this list does not name). tools/pay_ledger.py.
#   WIN_SHADOW=1  (record only) in whole games, late rounds and pro starts what WIN_PAY would pay this frame (the same
#                 table, scale and rule as _game_step, its own chance as last "paid", ws_p), never paid:
#                 info["win_shadow"], info["flat_frag"] (this frame's flat frag pay in such games, +1 a frag, -1 a death,
#                 what WIN_PAY takes out) and stats["win_shadow"] (WS_COLS, his counted seats). With WIN_PAY on it equals
#                 info["win_pay"].
PAY_SPLIT = float(os.environ.get("PAY_SPLIT") or 0.0) > 0
WIN_SHADOW = float(os.environ.get("WIN_SHADOW") or 0.0) > 0
PAY_TERMS = ("jerk", "weapon_switch", "hop", "blind_fire", "move_round", "course", "fire_toggle", "shot_price", "blind_rocket",
             "dmg_dealt", "dmg_taken", "high", "rail", "style", "item_MH", "item_RA", "item_YA", "item_flat_other", "big_order",
             "item_points", "item_loss", "items_other", "item_seek", "way", "way_claw", "speed", "speed_run", "intent_switch",
             "runs", "stack_diff", "stack_keep", "drops", "know", "frag", "death", "deaths_other", "win_pay", "watch", "preaim",
             "lg_quiet", "win_part")
PT_IX = {k_: i_ for i_, k_ in enumerate(PAY_TERMS)}
WS_COLS = ("his shadow WIN_PAY in games, summed", "its size", "his flat frag pay in games, summed", "its size", "his frames in games",
           "his games' frags (+1) and deaths (-1) counted")
#   WIN_W=w, WIN_GAIN=G, FADE_V=v   (v0.5.1; live names, all three; 0 / 1 / 0 by default, and with WIN_W and FADE_V both 0
#                 the simulator is what it was, to the bit: not one draw more, nothing paid otherwise) the cross-fade from the
#                 pays made by hand to the pay by the chance of winning (the generation's goal, owner 2026-10-23: "pay by win
#                 chance only"). It applies to the frames of every match with a game under way (self.game > 0 when the
#                 frame's clock is run, _game_step): whole games (1), late rounds (2), mid-game starts and the pros' and
#                 people's starts (3; PRO_KIND, to the game's limit with PRO_START_LEN=0, overtime as there), spawn starts and
#                 short starts (4) and rail starts. The practice rounds with no game keep their own pays as they were: jump
#                 runs, rocket jump runs, item runs (kind MOVE), the one-weapon and aim rounds (DRILL, AIM), the ordinary
#                 short NORMAL rounds, the test map's labs and courses (none of them is in v0.5.0's mix but the jump runs).
#                 In such a frame, per player, the pay is cut in three:
#                   combat   the flat pay for a frag (+1) and a death (-1) and the damage pay (dealt x dmg_reward less taken x
#                            dmg_taken_w x dmg_reward): the terms "frag", "death", "dmg_dealt", "dmg_taken";
#                   win      WIN_SCALE x (p - p before), p his chance of winning by lead and time left (WIN_PAY's rule, its
#                            own chance as last counted: wb_p, kept up every frame of every game whatever the switches, so
#                            a WIN_W opened in the middle of a game pays from that frame's chance on);
#                   other    everything else the frame pays (reward - combat): the item flats (the taker's gain and the
#                            mates' loss alike), the big three's order, the weapon and target switches, the shot price,
#                            the view jerk, the fire toggle, blind fire and blind rockets, KNOW_PAY, WATCH_PAY, PREAIM_PAY,
#                            RAIL_FAR_PAY, HIGH_PAY, STACK_DIFF and the stack keep, drops, the way and its claw, speed,
#                            LG_QUIET_COST: whatever is in it, no list to keep up;
#                 and paid  (1 - v) x other + (1 - w) x combat + w x G x win.  r_long (the items' and stack's part, not
#                 combat, not win) is (1 - v) x r_long: the win part is not in r_long, as WIN_PAY's was not. At w = 1 and
#                 v = 1 a game's frame pays the win part alone, exactly (0 x other is 0). With WIN_W > 0 or FADE_V > 0 the
#                 flat frag pay is counted as combat even with WIN_PAY=1 and WIN_PAY's own pay is not added (the blend
#                 takes its place); WIN_PAY=1 with both at 0 is what it was (the flat frag pay out, the win pay in, damage
#                 untouched). The trainer's own --info-pay (added to the reward outside the simulator; 0 in v0.5.0) is not
#                 faded.
#                 The equilibrium: the win part is zero-sum (the second seat is paid exactly the first seat's amount with
#                 the other sign) and each frame pays a difference of one function of the score and the clock, so a game's
#                 win part sums to w x G x WIN_SCALE x (its result 1 / 0.5 / 0 less the chance at its start, or at the
#                 frame w was last changed) whatever happened on the way: nothing in it can be pumped, and the only way to
#                 more of it is to win more games. In self-play the fixed point of the win part alone is the policy that
#                 wins most against the league. The (1 - w) combat part and the (1 - v) other part keep today's behaviour
#                 while they fade; the overtime's last frame reads 0 s left (_ot_left, fixed 2026-10-24, 4e52053: the fold
#                 showed 120 s there), so a game decided in overtime pays its outcome. Counters: stats["win_blend"] (WB_COLS,
#                 his counted seats in such frames, kept whether the blend is on or not, for sizing G); info["win_blend"]
#                 (blend on: per player [win, combat, the win part paid]); the pay term "win_part" (PAY_SPLIT; the other
#                 terms scaled with the pay they stand for). sim/win_chance.json is read whenever GAME_ON.
#   WIN_LONG=1    (live, 0 / 1, default 0; with the blend on) the win part paid (w x G x win) goes into r_long as well: the
#                 long value (--long-gamma, about two minutes ahead) learns the chance of winning when FADE_V takes the items
#                 out of r_long. r_long = (1 - v) x r_long + w x G x win in the games' frames.
#   WIN_STACK=1   (live, 0 / 1, default 0; the coefficients live too, their defaults the fit of 2026-10-26 (held out: the
#                 win chance's log loss 0.3959 -> 0.3848): WIN_TAU 32.5 s, WIN_PA 2.7546, WIN_PS 300, WIN_PRL 0.4277,
#                 WIN_PLG 0.4485, WIN_PRG 0.2922) the blend's chance with the stack in it:
#                 W~ = clip(W(lead, left) + PHI, 0, 1), PHI = (p_next - 0.5) x (W(lead + 1, left) - W(lead - 1, left)) x
#                 (1 - exp(-left / WIN_TAU)), p_next = sigmoid(WIN_PA x f(d) + WIN_PRL x dRL + WIN_PLG x dLG + WIN_PRG x dRG)
#                 the chance that the first seat scores the next frag: d his true stack (health + armor) less the other's,
#                 f(d) = tanh(d / WIN_PS) with WIN_PS > 0 else d / 100, dRL / dLG / dRG the big weapons owned (1 he only, -1
#                 the other only, 0 both or neither). A dead player (health 0 or less, or waiting to respawn) counts as his
#                 respawn will have him: SPAWN_HP, no armor, no big weapon (the fit saw both alive only; so PHI does not
#                 jump at the respawn, it steps once, at the frag, with the score). No intercept: the second seat's W~ is
#                 1 - the first's exactly (p_next and the lead swap, W(lead + 1) - W(lead - 1) is the same for both), so
#                 the win part stays zero-sum; PHI is 0 at the game's end (left 0), so a game's win part still sums to
#                 w x G x WIN_SCALE x (result - W~ at its start) (the start's W~ is taken with the start's stacks: a whole
#                 game's spawn, a late round's drawn stacks, a pro start's). A pickup, a hit, a weapon taken move the pay on
#                 that frame. Switched on or off in the middle of a game: one frame's step from W to W~ (or back). Only the
#                 blend reads it (WIN_PAY and WIN_SHADOW keep the table alone). The trainer's live.json takes numbers of 0
#                 or more only: a negative coefficient goes by live_settings.env or the run's environment.
#   WIN_SHAPE_K=k (v0.6.1; live, 0 or more, default 0: off, the simulator is v0.5.1's to the bit) a dense pay beside the win
#                 part that leaves its equilibrium alone (potential-based shaping, Ng, Harada and Russell 1999): in every frame
#                 of a game under way (the blend's frames, wb_gm) the first seat of a match is paid
#                     k x (WIN_SHAPE_G x PSI(now) - PSI(the frame before))      and the second seat exactly the opposite,
#                 PSI = (p_next - 0.5) x (1 - exp(-left / WIN_SHAPE_TAU)), p_next WIN_STACK's chance of the next frag (the same
#                 coefficients WIN_PA .. WIN_PRG, the same dead-player rule: a dead player counts as his respawn will have him),
#                 left the seconds to play as the blend reads them (overtime: the period's, 0 on its last frame). PSI is a
#                 function of the state only (stacks, big weapons, the clock), zero-sum (the second seat's PSI is minus the
#                 first's) and 0 at a game's end (left 0); a round that ends before (a spawn start, a moment's end) is cut
#                 there with PSI(end) := 0 (the frame's pay is corrected: k x (0 - PSI before)), as a terminal state must be.
#                 So over a game the shaping sums to  k x (WIN_SHAPE_G^T x 0 - PSI(start)) discounted at WIN_SHAPE_G, i.e. it adds
#                 a constant, -k PSI(start), to the value of the start and nothing to any choice: with WIN_SHAPE_G = the
#                 trainer's --gamma (0.999 a frame in v0.5.x; the trainer sets WIN_SHAPE_G to its --gamma when the run's
#                 environment does not name it) the discounted objective PPO maximises, and with it its fixed point in self-play,
#                 is exactly the win part's. Undiscounted, a game's shaping sums to -k PSI(start) - k (1 - WIN_SHAPE_G) x the sum
#                 of PSI over its frames (a stack lead held costs 0.1% of its PSI a frame): small and, being zero-sum, cancels
#                 between equal players. What it changes: a hit, a pickup, a big weapon taken pay on their frame instead of only
#                 through the frag they make likelier, and the pay is taken back when the advantage goes (a frag resets the
#                 dead player to the spawn's stack; the respawn moves nothing). Not faded by FADE_V or scaled by WIN_W (added
#                 after the blend), not in r_long. Opened in the middle of a game it pays from that frame on (its PSI before
#                 is read there, nothing paid that frame); set to 0 it forgets PSI. Counters (with k > 0): stats["win_shape"]
#                 (WSH_COLS); info["win_shape"]; PAY_SPLIT: in the term "win_part".
#   WIN_SHAPE_TAU (live, seconds, default 32.5: WIN_STACK's) how fast PSI goes to 0 at the end;  WIN_SHAPE_G (live, default
#                 0.999) its discount a frame: must be the trainer's --gamma.
WIN_LIVE = ("WIN_W", "WIN_GAIN", "FADE_V", "WIN_LONG", "WIN_STACK", "WIN_TAU", "WIN_PA", "WIN_PS", "WIN_PRL", "WIN_PLG", "WIN_PRG",
            "WIN_SHAPE_K", "WIN_SHAPE_TAU", "WIN_SHAPE_G")


def _win_live(get):
    """(v0.5.1) WIN_W, WIN_GAIN, FADE_V, WIN_LONG and the stack term's names from get(name) -> a string or None (unset: the
    default); ValueError on a value out of range (the trainer refuses the live file then)"""
    d_ = dict(WIN_W=0.0, WIN_GAIN=1.0, FADE_V=0.0, WIN_LONG=0.0, WIN_STACK=0.0,      # (the stack term's defaults: the fit of 2026-10-26)
              WIN_TAU=32.5, WIN_PA=2.7546, WIN_PS=300.0, WIN_PRL=0.4277, WIN_PLG=0.4485, WIN_PRG=0.2922,
              WIN_SHAPE_K=0.0, WIN_SHAPE_TAU=32.5, WIN_SHAPE_G=0.999)          # (v0.6.1, the shaping beside the win part: off)
    v = {}
    for k_, x0_ in d_.items():
        x_ = get(k_)
        v[k_] = float(x_) if (x_ or "").strip() else x0_
        if not np.isfinite(v[k_]):
            raise ValueError("{}: not a finite number".format(k_))
    if not 0.0 <= v["WIN_W"] <= 1.0 or not 0.0 <= v["FADE_V"] <= 1.0:
        raise ValueError("WIN_W and FADE_V must be within 0 .. 1")
    if not 0.0 < v["WIN_GAIN"] <= 100.0:
        raise ValueError("WIN_GAIN must be above 0 (at most 100)")
    if v["WIN_LONG"] not in (0.0, 1.0) or v["WIN_STACK"] not in (0.0, 1.0):
        raise ValueError("WIN_LONG and WIN_STACK are 0 or 1")
    if not v["WIN_TAU"] > 0 or v["WIN_PS"] < 0:
        raise ValueError("WIN_TAU must be above 0 and WIN_PS 0 or more")
    if v["WIN_SHAPE_K"] < 0 or not v["WIN_SHAPE_TAU"] > 0 or not 0.0 < v["WIN_SHAPE_G"] <= 1.0:
        raise ValueError("WIN_SHAPE_K must be 0 or more, WIN_SHAPE_TAU above 0, WIN_SHAPE_G within (0, 1]")
    v["WIN_LONG"], v["WIN_STACK"] = v["WIN_LONG"] > 0, v["WIN_STACK"] > 0
    return v


globals().update(_win_live(os.environ.get))
WB_COLS = ("his frames in games", "the win part at G = 1 (WIN_SCALE x the change in his chance), summed", "its size",
           "the combat pay (frags, deaths, damage) before the blend, summed", "its size", "the other pay before the blend: size",
           "the pay after the blend: size", "frames with the blend on")
WSH_COLS = ("his frames in games with the shaping on", "the shaping paid (k x (g PSI - PSI before)), summed", "its size",
            "the corrections at a round cut before the game's end, summed", "his rounds cut so")
#   OVERTIME=1    Quake Live's duel overtime (g_overtime 120): a whole game, a late round or a mid-game start that reaches
#                 the game's limit (GAME_LEN) with the score level goes on for another OT_LEN seconds, period after period,
#                 until a period ends with the score not level, or after OT_CAP periods (OVERTIME_CAP, 10): then it is a
#                 draw. A spawn start (SPAWN_START_P) ends after its seconds as before. Groups of three or more have no
#                 whole games (_game_ok), so nothing changes there. In overtime every time input reads as the game
#                 server's plugin shows it (plugins/duelbot.py GameClock.fed): the last OT_LEN seconds of the game again,
#                 round_t = 480 + ((t - 600) mod 120) for t past 600 (exactly 600: 600; the first frame of each further
#                 period: 480): the clock input (round_t / GAME_LEN), the item-timer waves, the v0.2 "left" (1 - round_t /
#                 GAME_LEN) and WIN_PAY's time left (the seconds left in the period). The game's frame counter g_tick runs
#                 on; nothing is reset between periods (no done: the memory goes on). Saved moments are taken before the
#                 limit only (a mid-game moment is at most at MID_HI; a respawn in overtime is not saved as a spawn moment).
#                 Counters: stats["overtime"] (OT_COLS). A training switch: not a PLAY_VAR.
OVERTIME = float(os.environ.get("OVERTIME") or 0.0) > 0
OT_LEN = 120.0
OT_FRAMES = int(round(OT_LEN / DT))
OT_CAP = int(os.environ.get("OVERTIME_CAP") or 10)
OT_KINDS = (1, 2, 3)                                        # whole games, late rounds, mid-game starts (not spawn starts: 4)
assert OT_CAP >= 1 and OT_FRAMES <= GAME_FRAMES
OT_COLS = ("games that went to overtime (whole, late, mid-game starts)", "overtime periods begun", "of those games: ended with a lead",
           "ended level at the cap (a draw)", "frames of matches in overtime",
           "overtime games ended in the second half of the matches (the trainer's league half: the first seat is his)",
           "of those: he won", "level", "he lost")
#   OPENINGS=1    the pros' spawn openings as the item rule's label (the owner, 2026-10-13: "spawn openings like chess
#                 openings"; sim/pro_spawn_openings/<map>.json of tools/pro_openings.py, docs/design/openings/README.md).
#                 It changes ONLY what the intention's teacher (intent_rule(), the trainer's --intent-teach) names in the
#                 first OPEN_SECS seconds of a life that begins at a spawn point, in a game (a NORMAL round, a whole game,
#                 a round begun from a saved moment), for his own seats: no output, no pay, no lesson on keys or view, and
#                 a scripted player's rule is what it was.
#                   first pickup    the pros' commonest first pickup from that spawn point;
#                   second pickup   their commonest second pickup after that first one, UNLESS he believes the enemy
#                                   within OPEN_AVOID units of it (his own belief, v02_bel of the frame before: never the
#                                   place of an enemy he could not know); then the next on that spawn's list (the other
#                                   seconds after that first by their lives, then the first and second pickups of the
#                                   spawn's other openings); if none is left the opening names nothing and the normal
#                                   rule speaks. After the second pickup or OPEN_SECS seconds: the normal rule.
#                   too little data (a spawn point the demos do not have, fewer than OPEN_MIN_LIVES lives at it, or no
#                                   first pickup he can name in OPEN_MIN_SHARE of them): the general rule the demos show:
#                                   the nearest big weapon first (by the rule's ways), then the nearest armor or mega the
#                                   enemy is not believed within OPEN_AVOID units of.
#                 An opening is cut to what he can name as an intention (INTENTS: plasma, grenades, the shotgun, the green
#                 armor and small items fall out of it), and a step is named only while the rule could name it: an item
#                 he believes there (or back within the way and 3 s, an armor or the mega), a weapon he does not own, with
#                 a way by the rule's own times (RULE_WALK: a walker's). A step that cannot be named is passed over.
#                 The opening's label is not silenced by RULE_CONTEST (the pros take the weapon whoever stands there; the
#                 second pickup has its own rule) and stands where TARGETS would be silent.
#                 OPEN_SILENT=1 (off by default: the owner's design is that the normal rule speaks): on the frames the
#                 avoid rule leaves no second pickup the lesson is silent (a negative label) instead: the normal rule
#                 knows nothing of the enemy and often names the very item avoided (Blood Run from the rocket spawns:
#                 the yellow armor) unless RULE_CONTEST silences it.
#                 Counters: stats["open"] (OPEN_COLS), of the seats the jump counters count (count_even: the even
#                 seats, his in the trainer's league half). A training switch: not a PLAY_VAR.
OPENINGS = float(os.environ.get("OPENINGS") or 0.0) > 0
OPEN_AVOID = float(os.environ.get("OPEN_AVOID") or 500.0)
OPEN_SECS = float(os.environ.get("OPEN_SECS") or 10.0)
OPEN_SILENT = float(os.environ.get("OPEN_SILENT") or 0.0) > 0     # (see below: 1 = where the avoid rule leaves none the lesson is silent)
OPEN_MIN_LIVES, OPEN_MIN_SHARE = 30, 0.10                  # a spawn point's lives in the demos, the first pickup's share of them
OPEN_SPAWN_R, OPEN_ITEM_R, OPEN_AT = 80.0, 64.0, 48.0      # a pros' start to the map's spawn point, an item of the file to
#                                                            the simulator's, his place at a life's first frame to a spawn point
OPEN_COLS = ("his lives begun in games", "of them at a spawn point with the pros' opening", "... with the general rule (too little data)",
             "lives in which the avoid rule changed the second pickup", "of them: it left none (the normal rule spoke)",
             "readings of his intention with an opening's label", "of them his choice was the label",
             "lives that took the first pickup named", "lives that took a second pickup of the opening",
             "seconds to the first big pickup of a life, summed", "lives with a big pickup")
#   MID_START_P, SPAWN_START_P   rounds begun from SAVED MOMENTS of whole games (the owner, 2026-10-13: "full games, mid game
#                 starts and '10s after a spawn with a believed enemy location'"): shares of the games' time, beside GAME_P
#                 and LATE_P and counted like them (a round's kind is drawn by share / length). Whole games must be on
#                 (GAME_P > 0): the moments come from them, in this simulator, while it runs.
#                 A moment is everything the simulator keeps for the two players of a match and for the match: every array
#                 with a row a player or a row a match (bodies, stacks, weapons, rockets in the air, the items' clocks,
#                 dropped weapons, score and game clock, and what each player KNOWS: where he last saw or heard the enemy
#                 and when, the item clocks he knows, what he saw the enemy take), the delayed sightings on their way, and
#                 the inputs of that frame. Begun from it, a round is that game from that frame on: nothing is invented.
#                 What is not kept: the network's own memory (the trainer's; it starts empty, as at every round), the
#                 simulator's random numbers, the frame counters that stagger the players' readings (his next reading of
#                 keys and intention can fall up to a few frames earlier or later), the hand statistics' last two seconds,
#                 and of the movement library the flags of a body in motion (jump held, the 160 ms after a teleporter,
#                 the double-jump clock): place, speed and view are exact (measured: tools of 2026-10-13).
#                   spawn moments   every respawn in a whole game or a mid-game start (SPAWN_START_BEL=1, the default: only
#                                   with a believed enemy place at that frame), the frame he stands at the spawn point.
#                   mid moments     MID_PER_GAME frames of every whole game, drawn evenly between MID_LO and MID_HI seconds.
#                 The newest SPAWN_BANK and MID_BANK moments are kept (a simulator's own; gone with the process).
#   MID_START_P=<share>   a mid-game start: a mid moment, played to the game's limit as a whole game is.
#   SPAWN_START_P=<share> a spawn start: a spawn moment, played for SPAWN_START_LEN seconds (10) of that game, then the
#                 round ends. In the second half of a simulator's matches (the trainer's league half, where the first seat
#                 is his) only moments whose spawning player is the first seat are used.
#                 Asked for with no moment saved yet (the first minutes of a process), a whole game begins instead or
#                 a round of the other kinds (the drills), by their shares of the time. A process begins with every
#                 whole game at 0:00: the mix is the one asked for only after a game's length (as with GAME_P alone).
#                 WIN_PAY carries on in both from the chance as last paid. Counters: stats["moments"] (MOMENT_COLS).
MID_START_P = float(os.environ.get("MID_START_P") or 0.0)
SPAWN_START_P = float(os.environ.get("SPAWN_START_P") or 0.0)
SPAWN_START_LEN = float(os.environ.get("SPAWN_START_LEN") or 10.0)
SPAWN_START_BEL = float(os.environ.get("SPAWN_START_BEL") or 1.0) > 0
#   RAIL_START_P=<share>   (v0.3.6, the owner's go of 2026-10-19: "let's plan to add some rail practice tonight") rail range
#                 starts: a share of the games' time, beside MID_START_P and counted like it (a round's kind is drawn by
#                 share / length), in rounds that begin as a mid-game start does (a saved mid moment: score, clock, stacks,
#                 items, what each knows) with the two players put at long range instead, where the pros fired the rail:
#                 a pair of places (the shooter's and the enemy's) of sim/rail_pairs/<map>.json (tools/rail_pairs.py: the
#                 pros' rail shots at 600 to 1100 units in the demos, each place let down onto the floor and the lines between
#                 them checked in this simulator), which seat stands at which end drawn evenly (zero-sum: the two seats are
#                 alike). Both get the railgun in hand, ready to fire, with at least RAIL_START_AMMO slugs; the rest of each
#                 one's stack is the moment's. Each keeps the pros' horizontal speed at that frame (at most 320) and looks
#                 toward the other within RAIL_START_YAW degrees (a uniform draw; pitch level): he has to notice and aim as
#                 ever (the reaction, acquire and surprise delays start at nothing seen; the sightings on their way are void).
#                 Rockets in the air from the moment are gone. Then it is a normal duel with normal pay: to the game's limit
#                 like a mid-game start (RAIL_START_LEN=0, the default; overtime as there) or for RAIL_START_LEN seconds of
#                 that game (as a spawn start). Its frames are a mid-game start's (game kind 3; with RAIL_START_LEN a spawn
#                 start's, kind 4) for everything that reads the kind (overtime, the head's win label), but not counted as
#                 one (stats["moments"]), and no moment is saved from it. A map with no railgun
#                 or no pairs (Lost World has no railgun) has none: its share goes to the other kinds by their shares.
#                 What the first frame's inputs show is the moment's (a frame of 25 ms before the change; the next frame's
#                 are the new places'). A training switch (a curriculum), not a PLAY_VAR: the servers need nothing.
#                 Counters: stats["rail_start"] (RAIL_START_COLS), the counted seats as RAIL_COLS's.
RAIL_START_P = float(os.environ.get("RAIL_START_P") or 0.0)
RAIL_START_LEN = float(os.environ.get("RAIL_START_LEN") or 0.0)
RAIL_START_YAW = float(os.environ.get("RAIL_START_YAW") or 45.0)
RAIL_START_AMMO = float(os.environ.get("RAIL_START_AMMO") or 10.0)
RAIL_EARLY = 10.0                                          # (the counters: a start's first seconds)
RAIL_TRIES = 16                                            # pairs tried at a start before the last one drawn stands
RAIL_START_COLS = ("rail starts begun", "asked for with no mid moment saved: a whole game or another kind instead", "rail starts ended",
                   "frames of matches in rail starts", "of them in a start's first RAIL_EARLY seconds",
                   "rail shots in rail starts (counted seats): near", "mid", "far", "hits: near", "mid", "far",
                   "frags by the rail: near", "mid", "far", "counted seats begun", "of them with a rail shot in the first RAIL_EARLY s",
                   "seconds to that first shot, summed", "placements that took another pair (a line or the room not clear)",
                   "the start distance, summed", "rail starts ended in the second half of the matches (the first seat is his)",
                   "of those: he won", "level", "he lost")
#   PRO_START_P=<share>   (v0.3.7, the owner's go of 2026-10-19: "this is what I thought they were. Can we do that instead?")
#                 pro starts: rounds that begin at a moment of a pros' duel on this map (sim/pro_moments/<map>.npz of
#                 tools/pro_moments.py: every few seconds of the demos' live games, both players in play, the items' states
#                 known). A share of the games' time beside GAME_P, MID_START_P and the rest, counted like them (a round's kind
#                 is drawn by share / length; the length is the map's moments' mean of the game time left). The round begins
#                 as a whole game does (_game_start: both seats networks, the round's reset: nothing is known, the memory
#                 empty) and is then put at the moment (after the reset, as a late round's draw is):
#                   the two players   each seat one of the two pros, which drawn evenly (zero-sum: the seats are alike):
#                                   place, speed (the game's), view (yaw and pitch), health, armor, the weapons he owns
#                                   (those the map has, the machine gun and the gauntlet always), their ammunition (at most
#                                   AMMO_MAX), the weapon in hand (ready: no switch, no reload), the seconds of his life;
#                                   one pro's stack is read from the demo's player state, the other's worked out (see
#                                   tools/pro_moments.py: no demo holds the other player's stats)
#                   the game        the score (frags each), the clock (the game's frame), WIN_PAY's chance from them, the
#                                   items: each there or back in its seconds; dropped weapons and rockets in the air: none
#                   his knowledge   what that pro could know and nothing else: the items he took himself are known to him
#                                   (when back: the item belief, the v0.2 "when he last took it", the mega and red clocks),
#                                   as _late_start does for its taker; of the enemy nothing (where, his stack: EN_STACK's
#                                   "nothing known"); the senses fill it from the first frame (the enemy is often in
#                                   view: a moment needs him sent, so in the PVS). No warm-in: nothing he could not know is
#                                   given, and the network's memory starts empty as at every round.
#                 Then it is a mid-game start: game kind 3 (PRO_START_LEN=0, the default: to the game's limit, overtime as
#                 there) or kind 4 for PRO_START_LEN seconds; normal pay (WIN_PAY from the chance at the moment). No moment
#                 is saved from it (mid or spawn). A map without the file has none: its share goes to the other kinds by
#                 their shares. A training switch (a curriculum), not a PLAY_VAR: the servers need nothing.
#                 Counters: stats["pro_start"] (PRO_START_COLS).
PRO_START_P = float(os.environ.get("PRO_START_P") or 0.0)
PRO_START_LEN = float(os.environ.get("PRO_START_LEN") or 0.0)
#   PEOPLE_START_SHARE=<share>   (2026-10-25, owner: "a variety of in game starts with different stack, positions and weapons in
#                 hand ... sample them from actual moments in the games played ... so he knows that 'rail on campgrounds is
#                 good'"): the share of the pro starts (PRO_START_P) that begin at a moment of a PERSON's duel against Bobby
#                 instead of a pros' demo: data/people_moments/<map>.npz of tools/people_moments.py (PEOPLE_MOMENTS_DIR), the
#                 same format and the same code (_pro_start; both players' truth: est 0). A map without the file keeps the
#                 pros' only; a map with people's moments and no pros' has people's only (at any share above 0). The share is
#                 of the starts' time: the starts' mean length is the two sources' mean by the share. Read at every draw (live:
#                 the trainer's live_settings.env); the file is read at the start whenever PRO_START_P is on. 0 (the default):
#                 not one random draw more, the simulator as before.
#   MOMENT_WEIGHTED=1    a pro start's moment is drawn by the file's "weight" column (tools/people_moments.py: moments a few
#                 seconds before a weapon he lacks or a big item is taken, and moments with the map's key weapon owned, count
#                 more); a file without the column (the pros') is drawn evenly. 0: evenly, as before. Live as well.
#   GEN_START_SHARE=<share>   (2026-10-25, owner: "a generative way of putting people in random positions, stacks, ammo, weapons
#                 in possession, on the map some point in time in the game, with all the in game timers in a random state ... make
#                 sure they get placed in reasonable spots, and then we can bias the sampling toward the things we want to
#                 encourage"; "new for each round basically unlimited"; places "biased towards [the pros'] heatmaps, but tunable"):
#                 the share of the pro starts (PRO_START_P) that begin at a GENERATED moment, drawn fresh for every start
#                 (_gen_moment): the places from sim/gen_places/<map>.npz (tools/gen_places.py: every point of the walking map
#                 reachable from a spawn and tried in this simulator: free box, no lava / slime / water, stood one second he
#                 stays on the ground), drawn by the pros' heatmap there (with a uniform share); the clock uniform in
#                 GEN_T_LO..GEN_T_HI, a score drawn for it, each seat's health, armor, weapons owned, ammunition, weapon in hand,
#                 life and speed drawn, the enemy at least GEN_APART away, every item up or back in a random part of its
#                 time (a big item that is back: one of the two took it and knows when). Then it is a pro start in every way
#                 (_pro_start: both seats' truth, nothing known of the enemy). The bias: GEN_BIAS (default sim/gen_bias.json,
#                 re-read when it changes, every GEN_RELOAD seconds at most): {"heat": exponent on the pros' heat (0: uniform
#                 over the safe places), "uniform": share drawn uniformly, "own": the chance a weapon of the map is owned,
#                 "maps": {map: {"own": {label: + chance}, "hand": {label: weight in hand}, "near": {label: chance the first
#                 seat starts within GEN_NEAR of that item's spawn}}}}; near an item, it is there and not owned half the
#                 time (the pickup), owned the other half (its use). Read at every draw (live). 0 (the default): not one
#                 random draw more, the simulator as before. Counters: stats["gen_start"] (GEN_START_COLS).
GEN_START_SHARE = float(os.environ.get("GEN_START_SHARE") or 0.0)
GEN_BIAS = os.environ.get("GEN_BIAS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_bias.json")
GEN_PLACES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_places")
GEN_T_LO, GEN_T_HI, GEN_APART, GEN_NEAR, GEN_RELOAD = 20.0, 580.0, 300.0, 320.0, 30.0
GEN_FAR = float(os.environ.get("GEN_FAR") or 800.0)        # (owner, 2026-10-25 ~22:45: "make the enemy spawn farther away and out of sight"):
#                 the enemy of a generated start at least GEN_FAR units away with no line of sight between the two (eye to eye);
#                 of 40 draws the first that is both, else the farthest unseen one, else the farthest
GEN_NEAR_S = float(os.environ.get("GEN_NEAR_S") or 3.0)    # (owner, 2026-10-25: "close needs to mean close in the sense of being able to
#                 walk to it quickly"): "near" an item = a place his ways reach it from in GEN_NEAR_S seconds or less (the route
#                 field's time: walking, pads, teleporters, the open jumps); an item with no way of its own: within GEN_NEAR units
GEN_START_COLS = ("generated starts begun", "of them placed near an item by the bias", "weapons owned (both seats, the map's, summed)",
                  "a big weapon in hand (both seats, summed)", "the bias file read")
PEOPLE_START_SHARE = float(os.environ.get("PEOPLE_START_SHARE") or 0.0)
MOMENT_WEIGHTED = int(float(os.environ.get("MOMENT_WEIGHTED") or 0))
PEOPLE_MOMENTS_DIR = os.environ.get("PEOPLE_MOMENTS_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "people_moments")
PEOPLE_START_COLS = ("pro starts from people's moments", "... counted seats begun", "... of them playing the person's seat",
                     "moments drawn by weight (either source)")
#   RUN_TARGET_W=1   (2026-10-25, owner's go: targeted practice for the items he never picks up): the item runs (ITEM_RUN_P:
#                 alone on the map from the game's spawn, his intention the target, paid by RUN_SCALE for the way gained and
#                 RUN_ARRIVE on taking it) draw their target by the map's weights in sim/run_targets.json ({map: {intention
#                 label: weight}}, tools/run_targets.py: from his own pickups a minute in whole games, the items he takes
#                 least weigh most) among the items lying there that his ways reach (_run_pick's rule, the walking map with
#                 its jump pads and teleporters), the next one drawn the same way when he has it. A map without a row in the
#                 table: evenly, as before. Read at every draw (live). 0 (the default): evenly, not one random draw changed.
RUN_TARGET_W = int(float(os.environ.get("RUN_TARGET_W") or 0))
RUN_TARGETS = os.environ.get("RUN_TARGETS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_targets.json")
PRO_KIND = 3 if PRO_START_LEN <= 0 else 4                 # (the game kind of its frames: a mid-game start's, or a spawn start's)
PRO_FRAMES = int(round(PRO_START_LEN / DT))
PRO_EARLY = 10.0                                           # (the counters: a start's first seconds)
PRO_START_COLS = ("pro starts begun", "pro starts ended", "frames of matches in pro starts", "of them in a start's first PRO_EARLY seconds",
                  "pro starts ended in the second half of the matches (the first seat is his)", "of those: he won", "level", "he lost",
                  "frags in pro starts (all seats)", "frags of the counted seats", "big pickups (mega, red, yellow) in pro starts, all seats",
                  "... of the counted seats", "pickups of any item, all seats", "the first seat's lead at the start, summed (abs)",
                  "counted seats begun", "of them with the worked-out stack (the demo's other player)", "the clock at the start, summed",
                  "his share of the frags in the ended starts (counted seats), summed", "ended starts with a frag")
MOMENT_P = MID_START_P + SPAWN_START_P + RAIL_START_P + PRO_START_P
MOMENTS = MOMENT_P > 0
assert MID_START_P >= 0 and SPAWN_START_P >= 0 and RAIL_START_P >= 0 and PRO_START_P >= 0 and GAME_P + LATE_P + MOMENT_P <= 1.0 + 1e-9, \
    "GAME_P, LATE_P, MID_START_P, SPAWN_START_P, RAIL_START_P and PRO_START_P are shares of the games' time"
assert MID_START_P + SPAWN_START_P + RAIL_START_P <= 0 or GAME_P > 0, \
    "MID_START_P, SPAWN_START_P and RAIL_START_P begin from moments of whole games: GAME_P must be on"
MID_LO, MID_HI, MID_PER_GAME = 60.0, 480.0, 2
MID_MEAN = GAME_LEN - 0.5 * (MID_LO + MID_HI)             # a mid-game start's length on average (for the shares)
RAIL_MEAN = MID_MEAN if RAIL_START_LEN <= 0 else min(RAIL_START_LEN, GAME_LEN - MID_HI)   # a rail start's length on average
RAIL_FRAMES = int(round(RAIL_START_LEN / DT))
RAIL_KIND = 3 if RAIL_START_LEN <= 0 else 4               # (the game kind of its frames: a mid-game start's, or a spawn start's)
SPAWN_BANK, MID_BANK = 256, 64
SPAWN_FRAMES = int(round(SPAWN_START_LEN / DT))
MOMENT_COLS = ("mid-game starts begun", "spawn starts begun", "mid-game starts ended", "spawn starts ended",
               "a start asked for with no moment saved: a whole game or another kind instead", "frames of matches in mid-game starts", "in spawn starts",
               "spawn moments saved", "mid-game moments saved", "respawns in whole games and mid-game starts", "of them with a believed enemy place",
               "mid-game starts ended in the second half of the matches (the first seat is his)", "of those: he won", "level", "he lost")
# what a moment does not hold: the map's and the setup's tables (some have as many rows as there are players or matches
# in one simulator or another), the group's fixed structure, and what only reports the step just made to the trainer
MOMENT_STATIC = ("cell_n", "cell_table", "floor_off", "hand_tab", "hi", "hold_feat", "hold_node", "hold_pos", "hurt_zones", "item_pos", "jump_a",
                 "jump_b", "jump_lab_off", "lo", "long_dirs", "pad_dest", "pads", "persona_p", "shot_fire", "shot_scarce", "shot_way", "spam_places",
                 "spawn_yaw", "spawns", "spots", "t_bins", "t_goal", "t_route", "t_turn", "tele_in", "tele_out", "up_dirs", "v02_pf", "v02_pp",
                 "v02_ways", "v02_zs", "view_grid", "w_table", "wall_dirs", "xpts", "open_first", "open_rank", "open_kind", "rule_tn", "hand_buf",
                 "foe", "fidx", "others", "grp", "slot", "legs_keep_who", "react_seat", "acquire_seat", "g_end",
                 "intent_live", "intent_changed", "intent_teach", "key_dec", "legs_live", "legs_on", "way_live", "legs_lab", "legs_wh", "win_pay",
                 "r_long", "op_lab", "pf_node", "emg_links",
                 "hd_ev", "hd_frames", "hd_clear", "hd_gr", "hd_z0", "hd_pos", "hd_w", "hd_gid", "hd_gid_ran", "hd_band",   # (HEAD_EVENTS)
                 "rail_m", "rail_t0", "rail_shot", "rail_pairs",    # (RAIL_START_P)
                 "pro_mm", "pro_t0", "pro_s0",                     # (PRO_START_P)
                 "pa_closed", "pa_since", "pa_pos", "pa_life", "stag_first")    # (the pre-aim counters, STAGGER_START)
MOMENT_HIST = ("opp_hist", "v02_q", "drift_q")                          # the last frames' sightings: lists of tuples of arrays a player a row
#   HIGH_PAY      who stands higher (B-160: he fights from below; owner, 2026-10-09: "fights from the low ground"): a hit
#                 from above counts for more, to the one who deals it and to the one who takes it, and a hit from below
#                 for less: by HIGH_PAY (0.25 = a quarter) at HIGH_Z units of height between the two, in proportion
#                 below that. Own splash and falls are not changed. 0 = off.
HIGH_PAY = float(os.environ.get("HIGH_PAY") or 0.0)
HIGH_Z = float(os.environ.get("HIGH_Z") or 128.0)
#   RAIL_FAR_PAY  (v0.3.6, the owner's go of 2026-10-18; a PLAY_VAR, 0 = off) the long-range rail: every railgun hit of a
#                 player on another pays the shooter RAIL_FAR_PAY x clip((d - RAIL_FAR_LO) / (RAIL_FAR_HI - RAIL_FAR_LO), 0, 1)
#                 and takes the same from the one hit (zero-sum); d = the 3D distance between the two players' origins (the
#                 state's x, y, z, not the eyes) at the hit; once a hit, whatever its damage. Its own term of the pay: not
#                 in `dealt` (his feedback inputs), not in the damage taken, not in r_long (combat pay, as HIGH_PAY).
#                 Equilibrium in self-play: each side is paid for its long rail hits what it pays for the other's, so a far
#                 rail fight is worth more to the one who wins it and long sight lines get more dangerous for both (goals 2
#                 and 3: weapon use, positioning: keep out of long lines without the rail, hold them with it).
#                 Counters always on (stats "rail", RAIL_COLS): the counted seats in games.
RAIL_FAR_PAY = float(os.environ.get("RAIL_FAR_PAY") or 0.0)
RAIL_FAR_LO = float(os.environ.get("RAIL_FAR_LO") or 600.0)
RAIL_FAR_HI = float(os.environ.get("RAIL_FAR_HI") or 900.0)
#   RAIL_STREAK_PAY (the owner, 2026-10-21: "a slight reward for stringing together consecutive hits on the rail") a rail hit that
#                 follows a rail hit (his last rail shot hit too; a miss or his death ends the string) pays the shooter
#                 RAIL_STREAK_PAY x (hits in the string - 1), at most RAIL_STREAK_CAP times, and takes the same from the one hit
#                 (zero-sum, as RAIL_FAR_PAY; booked with it in the rail counters' pay got). Equilibrium in self-play: each side
#                 is paid for its strings what it pays for the other's: a careful rail (a shot he will land) is worth more than
#                 a hopeful one, and being railed twice costs more, so getting out of a railer's line after the first hit
#                 matters (goals 2 and 4: weapon use, counterplay). 0: off. A training switch (pay only).
RAIL_STREAK_PAY = float(os.environ.get("RAIL_STREAK_PAY") or 0.0)
RAIL_STREAK_CAP = int(float(os.environ.get("RAIL_STREAK_CAP") or 3))
#   PREAIM_PAY=<k> (v0.3.9, the owner, 2026-10-21, after his Blood Run duel against v0.3.8: pre-aiming, "looking where the enemy will
#                 come from when it matters") a fresh sighting between the two players of a duel: the frame the line between them
#                 opens (an eye to the other's body, 8 u above his origin, clear, as the sight test traces it, within 4000 u; no
#                 view cone: either one's line will do) after it was shut for PREAIM_SHUT seconds (1.0) or more; both alive (and
#                 not waiting to respawn); neither placed in the last PREAIM_SHUT seconds (a spawn, a run's or a moment's start,
#                 a teleporter: a move of 100 u or more in one frame, or his life's clock begun again); only in games: NORMAL
#                 rounds (whole games, mid-game and pro starts too), not one-weapon rounds, not item, jump or rocket jump runs,
#                 not the test map's rooms. On that frame each player's error: the angle from his view (yaw and pitch) to the
#                 other's chest (that same point 8 u above the origin), q = clip(1 - err / 60, 0, 1); player i is paid
#                 k x (q_i - q_j) and j the same less (zero-sum, once a sighting; its own term, not in `dealt`, not in r_long,
#                 as RAIL_FAR_PAY). Equilibrium in self-play: each side gains what the other loses by facing the corner the
#                 other comes round, so both learn to hold their crosshair where the enemy will appear and to come round where
#                 he is not looking (wide, from above, from another door), and a sighting that is the other's surprise is
#                 worth more than his (goals 2, 3 and 4: weapon use, positioning, counterplay). 0: off. A training switch.
#                 Counters always on (they read the state only: the random stream is the same): stats["preaim"] (4 x NW, by the
#                 weapon in his hand: sightings, the error summed, within 15 deg, q summed) and stats["preaim_x"] (PREAIM_X_COLS)
#                 for the counted seats (_counted, policy seats).
PREAIM_PAY = float(os.environ.get("PREAIM_PAY") or 0.0)
PREAIM_SHUT = float(os.environ.get("PREAIM_SHUT") or 1.0)
PREAIM_X_COLS = ("seat-frames in games, both alive (counted seats)", "pay to every seat, summed (zero-sum: 0)", "pay to the counted seats",
                 "pay, absolute, summed over every seat")
#   STAGGER_START=1 (v0.3.9, the owner, 2026-10-21: the safe restart, "settings for the games that start next; no running game
#                 cut off") the first whole game (GAME_P) of each match after a simulator is made begins at a drawn point of its
#                 clock (0 to GAME_LEN seconds gone, uniform), 0-0, every item there, as a whole game's start is otherwise: the
#                 games of a process do not all end together, ten minutes after a (re)start. A late round, a mid-game or a spawn
#                 start, a pro start (its own clock) are as before; a match's later games begin at 0:00. Its own random stream
#                 (stag_rng): the run's is untouched. Counted: stats["stagger"] (games so begun, their start seconds summed).
#                 A training switch.
STAGGER_START = float(os.environ.get("STAGGER_START") or 0.0) > 0
#   LG_QUIET_COST=<c> (v0.3.10, live; the owner, 2026-10-22: "small noise pay for LG ... monitor over the first few hours and adjust
#                 if needed") a cost of c a second while a network's seat (script 0) is alive with the lightning gun in hand and, by
#                 HIS OWN SENSES, the enemy is away: not noticed in view (`acquired`, his own noticing after the reaction time) for
#                 3 s or more (lgq_t, his own clock: seconds since he last had the enemy acquired) and nothing of the enemy heard in
#                 the last 2 s (the newest of what reached his ears: ear_t, the ear inputs' clock that hear() resets on a footstep,
#                 a jump or landing, a shot or the hum of a rail or a lightning gun; snd_t, the event sounds of _hear (the enemy's
#                 pickups, shots, jumps, teleports); pain_t, the enemy's pain sound). The cost ramps with the time out of view:
#                 r = clip((lgq_t - 3) / (10 - 3), 0, 1), c x r x DT a frame; a sound heard in the last 2 s holds it at 0 (it does
#                 not start the ramp again). Games only: NORMAL rounds, whole games and pro starts (not one-weapon rounds, item,
#                 jump or rocket jump runs, the test map's rooms). Not in r_long, nothing in `dealt`. Equilibrium in self-play: a
#                 cost each side pays alone (nothing passes between them): rockets or the rail carried between fights, the LG
#                 brought out when a close fight is heard or expected; the enemy's sounds become worth more (goals 2 and 4:
#                 weapon use, counterplay). The escape is a switch while it is quiet (a switch takes time: not at contact). 0: off.
#                 Counters while it is on (the counted seats): stats["lg_quiet"] (LGQ_COLS), stats["lg_quiet_w"] (quiet frames,
#                 r > 0, by the weapon in hand), stats["lg_late"] (NW x NW: weapon changes in the 2 s before a fresh sighting, the
#                 PREAIM_PAY event, from -> to) and stats["lg_late_n"] (those sightings). The clocks and the ring of the last
#                 2 s (_watch_ring) are kept only while it (or WATCH_PAY) is on and only read the state: no random draw.
LG_QUIET_COST = float(os.environ.get("LG_QUIET_COST") or 0.0)
LGQ_UNSEEN, LGQ_FULL, LGQ_HEARD = 3.0, 10.0, 2.0          # (LG_QUIET_COST) out of view from 3 s, full at 10 s; a sound within 2 s holds it
LGQ_COLS = ("player-frames where it applies (alive, games, counted seats)", "quiet frames (r > 0)", "quiet frames with the LG in hand",
            "cost summed (counted seats)")
#   WATCH_PAY=<k> (v0.3.10, live; the owner, 2026-10-22: "back pay for 'having been looking in the right direction prior to enemy
#                 seen'. This is the first step into resurrecting the 'pay for knowing where the enemy is'") at each fresh
#                 sighting (exactly PREAIM_PAY's event: the line between the two opens after PREAIM_SHUT s or more shut, both
#                 alive, neither placed in the last PREAIM_SHUT s, games only), each of the two looks back over the previous
#                 WATCH_WIN seconds (1.5 s, 60 frames): on every frame of it that he was alive, the line between them was shut
#                 (the enemy hidden) and that came after his last placement, the angle between his view then (yaw and pitch)
#                 and the direction from his eye then to the spot the enemy came out at (the enemy's chest, 8 u above his origin,
#                 on the sighting frame); w = clip(1 - angle / 45, 0, 1). His score: the weighted mean of w over those frames,
#                 the weights rising linearly from 0.5 (the oldest frame) to 1 (the last before the sighting); 0 when no frame
#                 counts. Player i is paid k x (s_i - s_j) and j the same less (zero-sum, once a sighting, on the sighting frame;
#                 not in `dealt`, not in r_long, as PREAIM_PAY). The pay reads the truth (where the enemy came out); his inputs
#                 stay what he perceives. Equilibrium in self-play: watching an opening pays only if the enemy watched his
#                 worse, so both learn to watch the openings the other comes out of and to come out of the ones not watched
#                 (goals 3 and 4: positioning, counterplay). 0: off. Counters while it (or LG_QUIET_COST) is on: stats["watch"]
#                 (2 x NW by the weapon in hand at the sighting: sightings, score summed) and stats["watch_x"] (WATCH_X_COLS),
#                 the counted seats.
WATCH_PAY = float(os.environ.get("WATCH_PAY") or 0.0)
WATCH_WIN, WATCH_DEG, WATCH_RING = 60, 45.0, 80           # frames looked back (1.5 s), the angle where w reaches 0, the ring kept (2 s)
WATCH_X_COLS = ("sightings (counted seats)", "pay to every seat, summed (zero-sum: 0)", "pay to the counted seats",
                "pay, absolute, summed over every seat")
#   LG_DEAF=1     (v0.3.10, a PLAY_VAR: the checkpoints, checks and plugins carry it; the owner's choice of 2026-10-22, from the game's
#                 sound files: scratchpad lghum/REPORT.md) his own lightning gun muffles his hearing. While the weapon in his hand
#                 is the LG (alive) and he is not firing it: an enemy footstep (a footstep alone, not a jump, a landing or a
#                 shot) is heard only within LGD_STEP units (700; hear()'s 1,000 and the place-from-footsteps rule's HEAR 800
#                 both cut to it), with LGD_DIR x (d / LGD_STEP)^2 degrees (8) more direction error and LGD_LOUD (0.1) more of
#                 the distance as error (one draw a sound, as HEAR_FIX: the random stream is the same); the enemy's LG hum is not
#                 heard (a rail's hum is). While he fires the LG (the trigger held with the LG in hand and ammunition: lgd_fire,
#                 set by step() and by the plugins): footsteps within LGD_FIRE_STEP (500), every other sound of the enemy
#                 (pickups, jumps, landings, shots, pain: hear(), _hear, note_shots, the pain sound, note_pickup, note_take, the
#                 item belief) within LGD_FIRE_EVT (1,000) at most. Item returns, a death's obituary and his own sounds are as
#                 before. The footstep rules need HEAR_FIX (on since v0.3.8). Off: the simulator as it was.
LG_DEAF = float(os.environ.get("LG_DEAF") or 0.0) > 0
LGD_STEP = float(os.environ.get("LGD_STEP") or 700.0)
LGD_FIRE_STEP = float(os.environ.get("LGD_FIRE_STEP") or 500.0)
LGD_FIRE_EVT = float(os.environ.get("LGD_FIRE_EVT") or 1000.0)
LGD_DIR = float(os.environ.get("LGD_DIR") or 8.0)
LGD_LOUD = float(os.environ.get("LGD_LOUD") or 0.1)
PLAY_VARS = PLAY_VARS + ("LG_DEAF", "LGD_STEP", "LGD_FIRE_STEP", "LGD_FIRE_EVT", "LGD_DIR", "LGD_LOUD")
RAIL_COLS = ("frames", "shots_near", "shots_mid", "shots_far", "hits_near", "hits_mid", "hits_far",
             "hand_near", "hand_mid", "hand_far", "hand_view_near", "hand_view_mid", "hand_view_far", "pay_got", "pay_lost")
PLAY_VARS = PLAY_VARS + ("RAIL_FAR_PAY", "RAIL_FAR_LO", "RAIL_FAR_HI")
# ZOOM_PERCEPT (v0.3.8, the zoom check of 2026-10-19; a PLAY_VAR, 0 = off): zoomed as a person is. His hand noise already
#              shrinks with the zoom (MOTOR_NOISE on the zoomed movement, MOTOR_BASE and TURN_CAP times ZOOM); two things
#              did not: (1) the sight error PERCEPT_SIGMA (degrees) is ZOOM as large while zoomed (the target is drawn
#              1/ZOOM = 2.5 times larger: the gap between crosshair and target is judged as well in screen terms; the
#              flinch is not changed); (2) the faster follow of small corrections (MOUSE_SMOOTH_FINE) is for hand
#              movements up to 1 degree unzoomed (in view degrees: up to ZOOM degrees while zoomed), not view movements
#              up to 1 degree. The game: the owner's cg_zoomfov 42 against cg_fov 103 (0.41) with cg_zoomScaling 1 (the
#              mouse turns the view by the same ratio) is ZOOM = 0.4.
ZOOM_PERCEPT = float(os.environ.get("ZOOM_PERCEPT") or 0.0) > 0
PLAY_VARS = PLAY_VARS + ("ZOOM_PERCEPT",)
# B-265 (v0.3.6, the owner's go of 2026-10-18: "If a hot reload would allow for stuff like changing pay weights mid session
# then yes"): the pay weights a running trainer may change between two rollouts (its run folder's live.json; the trainer's
# own two, DMG_TAKEN_W and DMG_REWARD, are not module globals and are handled there). Each is a module global read only
# when the pay is worked out, nothing is made of it at import or in __init__: live_set() sets it in this process exactly as
# the import does from the environment (and the environment with it). Left out on purpose: anything read at import or in
# __init__ (SHOT_COST and SHOT_W make per-map tables; WIN_PAY its tables), every input, output, round-kind and map switch.
LIVE_VARS = ("ITEM_FLAT", "SPEED_PAY", "SPEED_PAY_RUN", "HOP_PAY", "HOP_QUIET", "HOP_QUIET_HEARD", "HOP_QUIET_NEAR",
             "HIGH_PAY", "HIGH_Z", "RAIL_FAR_PAY", "RAIL_FAR_LO", "RAIL_FAR_HI", "STACK_DIFF", "BLIND_RL_DMG",
             "HOP_CHAIN", "HOP_CHAIN_MS", "HOP_CHAIN_TOL", "HOP_CHAIN_STEP", "HOP_CHAIN_CAP", "JUMP_EVERY",    # (v0.3.7)
             "BIG_PICK_SEQ", "RG_FAR_PRICE", "RG_FAR_DIST",                                                         # (v0.3.8)
             "JUMP_COST",                                                                                           # (v0.3.9)
             "LG_QUIET_COST", "WATCH_PAY",                                                                          # (v0.3.10)
             "LEVEL_PULL",                                                                                          # (v0.4.3, B-275)
             "BLIND_AHEAD_P",                                                                                       # (v0.4.3, BLIND_AHEAD's chance a life)
             "PERCEPT_SPEED", "PERCEPT_SPEED_MAX_RG", "PERCEPT_SPEED_MAX_LG",                                    # (v0.4.4, owner 2026-10-26: "his LG is overtuned"; calibrated 0.05)
             ) + WIN_LIVE + AIM2_LIVE                                                                               # (v0.5.1, the cross-fade to the win pay; AIM2)
LIVE_STR = ("ITEM_FLAT", "BIG_PICK_SEQ")                   # (B-265) the live names whose value is a string, not one number


def live_values(get):
    """(B-265) the module globals of LIVE_VARS as the import works them out, from get(name) -> the environment's string or
    None. Raises ValueError on a value the import could not read (the trainer refuses the file then)."""
    v = {}
    flat_ = (get("ITEM_FLAT") or "").strip()
    v["ITEM_FLAT"] = {k_: float(v_) for k_, v_ in (x_.split(":") for x_ in flat_.split(",") if ":" in x_)}
    if flat_ and not v["ITEM_FLAT"]:
        raise ValueError("ITEM_FLAT {!r}: no NAME:value pair".format(flat_))
    v["SPEED_PAY"] = float(get("SPEED_PAY") or 0.0)
    v["SPEED_PAY_RUN"] = float(get("SPEED_PAY_RUN") or v["SPEED_PAY"])
    v["HOP_PAY"] = float(get("HOP_PAY") or 0.0)
    v["JUMP_COST"] = float(get("JUMP_COST") or 0.0)
    if v["JUMP_COST"] < 0:
        raise ValueError("JUMP_COST must be 0 or more")
    v["LG_QUIET_COST"] = float(get("LG_QUIET_COST") or 0.0)
    v["WATCH_PAY"] = float(get("WATCH_PAY") or 0.0)
    if v["LG_QUIET_COST"] < 0 or v["WATCH_PAY"] < 0:
        raise ValueError("LG_QUIET_COST and WATCH_PAY must be 0 or more")
    ps_ = get("PERCEPT_SPEED")                               # (v0.4.4) the fast-target limit, live; unset: the aim level's (0 at every level)
    v["PERCEPT_SPEED"] = float(ps_) if (ps_ or "").strip() else float(AIM_SET["percept_speed"])
    if not 0.0 <= v["PERCEPT_SPEED"] <= 0.2:
        raise ValueError("PERCEPT_SPEED must be within 0 .. 0.2")
    for k_ in ("PERCEPT_SPEED_MAX_RG", "PERCEPT_SPEED_MAX_LG"):     # (v0.5.0) the cap by weapon, live; unset: 0 (PERCEPT_SPEED_MAX)
        v[k_] = float(get(k_) or (0.001 if k_ == "PERCEPT_SPEED_MAX_RG" else 0.0))     # (aim2 branch: the rail's default 0.001)
        if not 0.0 <= v[k_] <= 20.0:
            raise ValueError(k_ + " must be within 0 .. 20")
    lp_ = get("LEVEL_PULL")                                  # (B-275) the view's pull toward level; unset: 0.95
    v["LEVEL_PULL"] = float(lp_) if (lp_ or "").strip() else 0.95
    if not 0.0 <= v["LEVEL_PULL"] <= 1.0:
        raise ValueError("LEVEL_PULL must be within 0 .. 1")
    bap_ = get("BLIND_AHEAD_P")                              # (v0.4.3) BLIND_AHEAD's chance a life; unset: 1
    v["BLIND_AHEAD_P"] = float(bap_) if (bap_ or "").strip() else 1.0
    if not 0.0 <= v["BLIND_AHEAD_P"] <= 1.0:
        raise ValueError("BLIND_AHEAD_P must be within 0 .. 1")
    v.update(_win_live(get))                                 # (v0.5.1) the cross-fade to the win pay, its long part, the stack term
    v.update(_aim2_values(get))                              # (AIM2) its live numbers
    for k_, d_ in (("FLINCH_PER_DMG", "flinch_per_dmg"), ("FLINCH_MAX", "flinch_max"), ("FLINCH_TAU", "flinch_tau")):
        x_ = get(k_)                                         # (AIM2) the flinch live; unset: the aim level's
        v[k_] = float(x_) if (x_ or "").strip() else float(AIM_SET[d_])
        if not 0.0 <= v[k_] <= 20.0 or (k_ == "FLINCH_TAU" and v[k_] <= 0.0):
            raise ValueError(k_ + " must be within 0 .. 20 (FLINCH_TAU above 0)")
    v["HOP_QUIET"] = float(get("HOP_QUIET") or 0.0) > 0
    v["HOP_QUIET_HEARD"] = float(get("HOP_QUIET_HEARD") or 4.0)
    v["HOP_QUIET_NEAR"] = float(get("HOP_QUIET_NEAR") or 700.0)
    v["HIGH_PAY"] = float(get("HIGH_PAY") or 0.0)
    v["HIGH_Z"] = float(get("HIGH_Z") or 128.0)
    v["RAIL_FAR_PAY"] = float(get("RAIL_FAR_PAY") or 0.0)
    v["RAIL_FAR_LO"] = float(get("RAIL_FAR_LO") or 600.0)
    v["RAIL_FAR_HI"] = float(get("RAIL_FAR_HI") or 900.0)
    v["STACK_DIFF"] = float(get("STACK_DIFF") or 0.0)
    v["BLIND_RL_DMG"] = float(get("BLIND_RL_DMG") or 6.0)
    v["JUMP_EVERY"] = min(1.0, max(0.0, float(get("JUMP_EVERY") or 0.0)))
    if v["JUMP_EVERY"] > 0 and not JE_ON:
        raise ValueError("JUMP_EVERY: the run did not start with it set (JUMP_EVERY=0 at the start makes it live)")
    v["HOP_CHAIN"] = float(get("HOP_CHAIN") or 0.0)
    v["HOP_CHAIN_MS"] = float(get("HOP_CHAIN_MS") or 150.0)
    v["HOP_CHAIN_TOL"] = float(get("HOP_CHAIN_TOL") or 15.0)
    v["HOP_CHAIN_STEP"] = float(get("HOP_CHAIN_STEP") or 0.5)
    v["HOP_CHAIN_CAP"] = float(get("HOP_CHAIN_CAP") or 3.0)
    v["RG_FAR_PRICE"] = float(get("RG_FAR_PRICE") or 0.0)
    v["RG_FAR_DIST"] = float(get("RG_FAR_DIST") or 700.0)
    if v["RG_FAR_PRICE"] < 0 or v["RG_FAR_DIST"] < 0:
        raise ValueError("RG_FAR_PRICE and RG_FAR_DIST must be 0 or more")
    v["BIG_PICK_SEQ"] = tuple(float(x_) for x_ in (get("BIG_PICK_SEQ") or "").split(",") if x_.strip())
    if len(v["BIG_PICK_SEQ"]) > 3 or any(x_ < 0 for x_ in v["BIG_PICK_SEQ"]):
        raise ValueError("BIG_PICK_SEQ: at most three numbers of 0 or more")
    for k_, x_ in v.items():
        for y_ in (x_.values() if isinstance(x_, dict) else x_ if isinstance(x_, tuple) else (x_,)):
            if not np.isfinite(float(y_)):
                raise ValueError("{}: not a finite number".format(k_))
    if v["RAIL_FAR_HI"] <= v["RAIL_FAR_LO"]:
        raise ValueError("RAIL_FAR_HI must be above RAIL_FAR_LO")
    if v["HOP_CHAIN_MS"] < 0 or v["HOP_CHAIN_TOL"] < 0 or v["HOP_CHAIN_STEP"] < 0 or v["HOP_CHAIN_CAP"] < 1.0:
        raise ValueError("HOP_CHAIN_MS, _TOL, _STEP must be 0 or more and HOP_CHAIN_CAP 1 or more")
    return v


def live_set(vals):
    """(B-265) vals {name of LIVE_VARS: the environment's string, or None = unset}: the environment and the module globals
    of this process set as if it had started so; returns the globals in force (live_now)"""
    bad_ = [k_ for k_ in vals if k_ not in LIVE_VARS]
    assert not bad_, "not a live name: {}".format(bad_)
    for k_, x_ in vals.items():
        if x_ is None:
            os.environ.pop(k_, None)
        else:
            os.environ[k_] = str(x_)
    globals().update(live_values(os.environ.get))
    return live_now()


def live_now():
    """(B-265) the LIVE_VARS globals in force in this process"""
    g_ = globals()
    return {k_: (dict(g_[k_]) if isinstance(g_[k_], dict) else g_[k_]) for k_ in LIVE_VARS}
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
TA_HEAD = len(ACTION_DIMS)                             # (LEGS_TURN_ADD) his turn correction while his legs carry him: the last output
if LEGS_TURN_ADD:
    ACTION_DIMS = ACTION_DIMS + (len(TA_BINS),)
KA_HEAD = len(ACTION_DIMS)                             # (LEGS_KEYS_ADD) the first of his five choices "my legs' / mine" on his legs
if LEGS_KEYS_ADD:
    ACTION_DIMS = ACTION_DIMS + (2,) * len(KA_COLS)
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
# The game's rules for hearing and for a respawn (B-270, 2026-10-19; docs/v0.4/FIDELITY_AUDIT.md gaps 3, 4 and 9). All off
# by default; off, the simulator is what it was (fixed runs of the trainer's workers, bit for bit).
#   HEAR_QL=1        (a PLAY_VAR) a sound is heard only where the game sends it: a Quake 3 / Quake Live server sends a client
#                    an entity, and so its events (steps, jumps, shots, pickups, pain), only when the entity's box touches a
#                    cluster in the potentially-visible set (PVS) of the client's eye (sim/pvs.py reads it from the map's
#                    .bsp). Checked on the pros' own demos (twelve maps, 6.8 million frames): when the server sent the enemy
#                    his box was in the PVS on 99.3% of the frames; in the gaps when it did not, 9% (places guessed between
#                    two sightings). The spheres (EAR_RANGE, HEAR_EVT, HEAR, HUM_RANGE) stay as the reach;
#                    a sound outside the PVS is silent, however near (within 1,000 units, 27% of the pros' frames and 31%
#                    on our servers' duels are walled off; Lost World 56%). A death is known to every other player (the obituary is a broadcast
#                    event). An item's sounds (taken, back) are tested at the item's place.
#   HEAR_QL_RANGE=u  (a PLAY_VAR, with HEAR_QL) every sphere becomes u units (Quake 3's client: the volume falls to nothing at
#                    1,330 units; Quake Live's client is closed). 0 (the default): the simulator's spheres.
#   RESPAWN_QL=s     (a PLAY_VAR; 1 = 2.1 s) a player killed in a fight round (not an item run, a jump run, a drill or the
#                    lab) is out of play for s seconds before he is back at a spawn point: not seen, not heard, not hurt
#                    (a shot or a rocket stops on his body and does nothing), takes nothing, presses nothing (keys, mouse,
#                    trigger and weapon key have no effect; his view stays where it was). His inputs go on from where his
#                    body lies, with the dead flag on, as a game server's plugin shows him while dead. The spawn point is
#                    chosen at the wait's end by the enemy's place then (_spawn's rule, the far half from the enemy, which
#                    fits the pros' respawns best). Measured (the pros' demos, twelve maps, and our servers): the game lets a
#                    player back 2.1 s after his death at the earliest and forces it at 4.5 s; Bobby taps fire and is
#                    back in 2.1 to 2.4 s (median 2.125). Pay unchanged: the death costs what it did, the wait pays nothing.
#                    Counters: rsp_waits (deaths that waited), rsp_wait_frames (player-frames out of play).
HEAR_QL = float(os.environ.get("HEAR_QL") or 0.0) > 0
HEAR_QL_RANGE = float(os.environ.get("HEAR_QL_RANGE") or 0.0)
if HEAR_QL and HEAR_QL_RANGE > 0:
    EAR_RANGE = HUM_RANGE = HEAR_EVT = HEAR = HEAR_QL_RANGE
#   SPAWN_QL=1       (a PLAY_VAR) the spawn points are the game's: info_player_start counts as one (Quake 3's g_client.c spawns
#                    it as an info_player_deathmatch; the simulator left it out). Of the twelve maps only Furious Heights
#                    (16, 352, 24: 7.2% of the pros' 2,047 respawns there) and Dismemberment (666, 1036, -8: 23.8% of 1,188)
#                    have one. The rule (_spawn: random among the far half of the points from the enemy) is unchanged:
#                    of the rules tried on 14,937 respawns of the pros (spectators' demos, the enemy's place known) it fits
#                    best (86.9% inside the half; Quake 3's far half from the death place 70.2%; uniform 50%).
SPAWN_QL = float(os.environ.get("SPAWN_QL") or 0.0) > 0
RESPAWN_QL = float(os.environ.get("RESPAWN_QL") or 0.0)
RESPAWN_QL_FRAMES = int(round((2.1 if RESPAWN_QL == 1.0 else RESPAWN_QL) / DT)) if RESPAWN_QL > 0 else 0
PLAY_VARS = PLAY_VARS + ("HEAR_QL", "HEAR_QL_RANGE", "RESPAWN_QL", "SPAWN_QL")
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
# v0.3.1, B-257 (the owner, 2026-10-15: "he should have a belief about my stack ... an expectation of the enemy's health +
# uncertainty"): the enemy's stack as he believes it, the last N_ES inputs (zeros with EN_STACK off; with it off nothing
# else changes). Worked out from his senses only, never from the enemy's true health: a filter he keeps in his head, a
# mean and a variance for the enemy's health and for his armor, per other player of his group (in a group the inputs
# are about the enemy he attends to, as the other enemy inputs):
#   a known spawn (the frag he made or heard: note_death; a round's start: _v02_round): health 125, armor 0, exactly;
#   health and armor over 100 tick down 1 a second, as in the game (exact);
#   a pickup heard within HEAR_EVT (1,200 units) or seen (note_take: every health and armor item, the rule of the game the
#     simulator uses: health +5 to 200, +25 and +50 only under 100 and to 100, the mega +100 to 200, armor to 200);
#   the damage he deals that player (his own hits only, never his own splash, and not the blow that kills: es_dmg, which
#     step() fills from the hits of the frame and a game server's plugin from the game's count of the damage he dealt,
#     note_dealt()) is taken off as the game takes it (armor soaks ARMOR_ABSORB of it while it lasts, the rest is health);
#   a pain sound heard (pain_t, pain_b: the bands under 25, 25 to 49, 50 to 74, 75 and over) pins the health into its band
#     (the three low bands set its spread to the band's; "75 and over" only lifts a mean below 75);
#   while that player is not in his view, the belief drifts toward what an unseen enemy's stack is on average (ES_MU_H,
#     ES_MU_A) and its spread grows toward that of an unseen enemy (ES_SD_H, ES_SD_A), with the time constant ES_TAU: the
#     items he may have taken unheard, the damage he may have taken from others, his own rockets and falls (an
#     Ornstein-Uhlenbeck prior; the four numbers are measured once in self-play, as a player knows from experience what
#     an enemy he has not seen for a while is likely to hold: ES_* below, and ES_TAU chosen against the truth: RESULTS 2026-10-15 21:15).
# The inputs: expected health / 200, expected armor / 200, expected health and armor together / 300, the spread (the
# standard deviation of the two together) / 150, seconds since the estimate was pinned (a known spawn, or a pain sound of
# the three low bands) / 30 capped at 1, "the estimate is weak" (expected health and armor together under ES_WEAK).
# Zeros in movement rounds and solo rooms (no enemy). A late round (LATE_P: drawn stacks) begins with nothing known: the
# unseen enemy's average and spread. What step() keeps and a game server's plugin must (it calls observe() only):
# note_take(), note_death(), _v02_round() and the pain sound (pain_t, pain_b, in a group pain_src) as the plugins keep them
# for v0.2's inputs; note_dealt() for every hit he lands on a living enemy; _es_set() for a seat a newcomer takes; on a frame
# on which observe() is not called, _es_update() (the plugins' v02_tick). The filter advances a frame at every observe():
# call observe() once a frame (as for v0.2's clocks).
EN_STACK = float(os.environ.get("EN_STACK") or 0.0) > 0
N_ES = 6
ES_MU_H = float(os.environ.get("ES_MU_H") or 124.0)
ES_MU_A = float(os.environ.get("ES_MU_A") or 88.0)
ES_SD_H = float(os.environ.get("ES_SD_H") or 38.0)
ES_SD_A = float(os.environ.get("ES_SD_A") or 57.0)
ES_TAU = float(os.environ.get("ES_TAU") or 120.0)
ES_WEAK = 80.0
ES_BAND_VAR = 25.0 ** 2 / 12.0                             # the spread of a health known to lie in a band of 25
# v0.3.1, B-256 (the owner, 2026-10-15: "build ALL of these things"), HUNT: the enemy as a target of his intention, the
# choice "EN" (EN_INTENT) of FIGHT_TARGET with the place he believes the enemy at as v0.2's inputs have it (v02_bel: seen
# or heard in the last V02_KNOWN seconds of this round, and not known dead since; with his reaction time and his error of
# sight), not only where he last saw him. His way and his legs are given the route goal that lies nearest (in seconds of
# way FROM the believed place) to it, an item's or (TARGETS) a holding place's, as an item's place is given today; the
# inputs "his way" show the way there and the input "his intention is the enemy" is on. Reached when the enemy is in
# view (he may choose anew at once), given up when nothing is believed of him any more. Nothing is paid for the way:
# it pays by what the fight brings. With the switch off (and FIGHT_TARGET off) the choice counts as "nothing". A network
# of v0.3's shape has the row shut (its bias -20): tools/hunt_init.py makes it a copy of "nothing" that is never chosen,
# and opens it out of "nothing" (--from-nothing). A game server's plugin: intent_release() calls note_hunt().
HUNT = float(os.environ.get("HUNT") or 0.0) > 0
EN_ON = FIGHT_TARGET or HUNT
# v0.4, the head (docs/v0.4/BUILD_v0.4.md section 3), HEAD_EVENTS=1 (a PLAY_VAR, off by default): what happened to him since
# the head last asked, as he could know it (never more than his inputs could tell him). head_events() gives [players, 32]
# float32 (HEAD_EVENT_COLS) and starts the count again; the trainer asks on the head's ticks. Fed by hooks that a game
# server's plugin calls too (it never calls step()):
#   note_combat(dealt, taken, frag, died)   dmg_dealt, dmg_taken (points; kept / 100), frag, died: step() from its books
#                                           of the frame (info["aux"]'s columns of the same names), once a frame
#   note_frame()                            en_seen (frames with an enemy noticed, as a share of the frames counted here),
#                                           en_pain (and en_heard: the pain sound is an event sound), weapon_change,
#                                           takeoff, fall_land: once a frame, after the senses, the pain sound and the
#                                           weapon in hand are set for the frame
#   _hear()                                 en_heard: the enemy's event sounds he hears (a shot, a pickup of a big item or
#                                           a weapon, a jump, a teleport); never the steady hum or running steps (hear())
#   note_take(i, it)                        took_*: his own pickup; en_took_*: another's pickup he saw (noticed in view) or
#                                           heard (HEAR_EVT), not in movement rounds and solo rooms
#   note_respawn(k, who)                    resp_*: an item's return heard (HEAR_EVT)
#   note_event(i, name, value)              anything else, by column name (adds)
# A round's end (done) starts a player's count again at the next step (the frame that ended it is still in the count, for
# a tick on that frame). Off: nothing of this is computed or kept, the simulator is today's.
# With it on, also the win label in info["aux"] (labels only, never inputs; AUX_COLS' last two):
#   win_game    the number of the whole game (GAME_P) or mid-game start (MID_START_P) the frame just played belongs to (a
#               running number of this simulator, from 0); -1: none (a normal round, an item run, a late round, a spawn start)
#   win_band    on the frame that ends such a game (done): the band of his final score margin (his frags less the best of
#               the others', a mid-game start's saved score included, overtime played out): 0 for -5 or less, 1 for -4 to -1,
#               2 level, 3 for 1 to 4, 4 for 5 or more (WIN_BAND_EDGES); -1 on every other frame
HEAD_EVENTS = float(os.environ.get("HEAD_EVENTS") or 0.0) > 0
HEAD_EVENT_COLS = ("dmg_dealt", "dmg_taken", "frag", "died", "en_seen", "en_heard",
                   "took_mh", "took_ra", "took_ya", "took_rl", "took_rg", "took_lg", "took_small",
                   "en_took_mh", "en_took_ra", "en_took_ya", "en_took_rl", "en_took_rg", "en_took_lg", "en_took_small",
                   "resp_mh", "resp_ra", "resp_ya", "resp_wp", "en_pain", "weapon_change", "takeoff", "fall_land",
                   "took_pg", "took_gl", "en_took_pg", "en_took_gl")
#   dmg_dealt, dmg_taken  points (health and armor together) / 100: dealt to other players; taken from anything (enemies,
#                         his own splash, lava, falls)
#   frag, died            frags he made of another player; his deaths of anything (counts)
#   en_seen               the share of the frames with an enemy noticed in view (his reaction time and acquire delay, as
#                         the inputs); en_heard: the enemy's event sounds he heard (see _hear() above, and his pain
#                         sounds), a count capped at HEAD_HEARD_CAP a tick
#   took_*                his pickups by class: mega, red armor, yellow armor, rocket launcher, railgun, lightning gun,
#                         plasma gun (took_pg), grenade launcher (took_gl), small = everything else (health, shards, green
#                         armor, ammunition, the shotgun, the heavy machine gun)
#   en_took_*             the same classes, for the pickups of others he saw or heard
#   resp_*                the returns he heard: mega, red armor, yellow armor, any weapon
#   en_pain               the enemy's pain sounds he heard; weapon_change: the weapon in his hand changed (not at a spawn)
#   takeoff               he left the ground going up (over 100 u/s: a jump, a jump pad); fall_land: he landed
#                         HEAD_FALL_DROP units or more below where he left the ground
N_HEAD_EVENTS = 32
assert len(HEAD_EVENT_COLS) == N_HEAD_EVENTS
HEAD_COL = {k_: i_ for i_, k_ in enumerate(HEAD_EVENT_COLS)}
HEAD_FALL_DROP = 64.0
HEAD_HEARD_CAP = 8.0                                       # en_heard: at most this many a tick (a tick is 8 frames)
WIN_BAND_EDGES = (-4.5, -0.5, 0.5, 4.5)                    # margin -> band: np.digitize(margin, WIN_BAND_EDGES)
WIN_KINDS = (1, 3)                                         # self.game: a whole game, a mid-game start
PLAY_VARS = PLAY_VARS + ("HEAD_EVENTS",)
# v0.3.6 (docs/v0.4/ROCKETS_v0.3.6.md items 1 to 4; the owner, 2026-10-17: rockets are aimed at things, the floor under the
# enemy, a wall, around a door, and splash is what to expect). Two switches, both PLAY_VARS and off by default; with them
# off their inputs are zeros and nothing else changes (nothing they work out is kept or read by anything else, and they draw
# no random numbers). Both come after N_ES at the end of the inputs; each has a token of its own in the attention part
# (sim/attn.py's LATE kinds "rocket" and "prefire"; tools/v036_init.py gives an older network them with their gate shut).
# A game server's plugin needs nothing more: they are made in observe() from what it keeps for the older inputs (the
# state, his weapon and hands, the enemy's known place, v0.2's belief, the walking map and its ways: tools/prep_ways.py).
# RL_AIM=1, the last N_RAIM inputs but N_PREF: with the rocket launcher in his hand (and alive)
#   the backstop (5): that it is on; where a rocket fired now along his view would explode (a trace from his eyes with the
#     shots' mask, RAIM_FAR at most): its distance / 2000 (capped at 2: nothing within RAIM_FAR), its height against his
#     eyes / 300 (-1 to 1); with the enemy in view (as the lead inputs: noticed, his reaction time late), that distance less
#     the enemy's / 500 (-1 to 1: below 0 it bursts before him) and the splash he would take there: 1 - the distance from
#     the burst to him / the rocket's splash radius (0 to 1; 0 = out of it).
#   the floor aim point (9), with the enemy in view: the floor under where he will be when a rocket fired now reaches that
#     floor (the lead inputs' flight time, worked out to the floor point; the enemy's own fall in the air as there; the floor
#     traced straight down from above that place, 1024 units, the shots' mask): that it is on; yaw from his crosshair to it
#     coarse (/ 30) and fine (/ 2); pitch coarse (/ 15) and fine (/ 2); a floor found; the enemy's feet above that floor then
#     / 200 (0 to 2: knocked or jumping high); the flight time / 1.5 (0 to 2); a clear line from his eyes to that point.
#   the nearest wall by that place (6), with the enemy in view: RAIM_WALL_N level traces from the predicted place (at the
#     height of his middle, RAIM_WALL units at most): that one hit; its way from that place in his own frame (sin, cos);
#     its distance / RAIM_WALL; yaw (/ 30) and pitch (/ 15) from his crosshair to the point it hit.
RL_AIM = float(os.environ.get("RL_AIM") or 0.0) > 0
N_RAIM = 20
RAIM_FAR, RAIM_WALL, RAIM_WALL_N = 4096.0, 192.0, 8
# PREFIRE=1, the last N_PREF inputs: the pros' blind-shot places of ONE weapon (the owner, 2026-10-18: rockets, grenades and
# plasma are aimed differently; sim/pro_places/<map>_rl.json, _gl.json, _pg.json of tools/pro_places.py --weapon; the mixed
# <map>.json that BLIND_PLACES and v0.2's place inputs read is not used here) that lie on the enemy's believed way to him:
# with v0.2's belief of the enemy (v02_bel: seen or heard in the last V02_KNOWN seconds, not known dead since), the enemy NOT
# in view, he alive. The list: the weapon in his hand when it is the rocket launcher, the grenade launcher or the plasma gun
# with ammunition and the map has a list for it; with any other weapon in his hand (or the one in hand without a list) the
# first of rockets, grenades, plasma that he has with ammunition and the map has a list for (PF_KINDS): a pre-fire is chosen
# before the switch to the weapon that makes it, and the rockets are the pre-fire weapon first; none: zeros. Three numbers of
# each slot say which list it is. The places are ranked by how far off the way they lie: the seconds of way from the believed
# place to the place and from it to him, less the way from the believed place to him (the walking map's table of ways,
# N_V02's), nearest the way first (ties: the nearer to the enemy); places within PF_SELF units of him are left out (his own
# splash). For each of the PF_SLOTS nearest (PF_F numbers; zeros in a slot with none): yaw from his crosshair to it / 30 and
# pitch / 15 (-1 to 1; the point the pros' shots land, PF_LIFT above it); its distance from his eyes / 2000 (to 1.5); when
# the enemy could be there: the seconds of way from the believed place to it less the time since that belief / 5 (-1 to 1:
# below 0 he could have passed it); the list's weapon's flight there / 1.5 (0 to 2: a rocket at 1000 units a second, a plasma
# cell at 2000, a grenade along its low arc; 0 where no grenade reaches); a clear line from his eyes (traced every frame);
# how far off the way / 5 seconds (0 to 1); that weapon's pros' share of their blind shots there / 15; the grenade list
# only: the pitch from his crosshair to the low arc that lands a grenade there / 15 (-1 to 1; 0 where none reaches, as the
# grenade arc inputs: lofted 0.2); that the slot holds a place; the list: rockets, grenades, plasma (one of three). A token a
# slot ("prefire").
PREFIRE = float(os.environ.get("PREFIRE") or 0.0) > 0
PF_SLOTS, PF_F = 3, 13
PF_KINDS = ("rl", "gl", "pg")                              # the lists, and the order of the fallback
N_PREF = PF_SLOTS * PF_F
PF_SELF, PF_LIFT, PF_TOL = 160.0, 2.0, 24.0
# EMERGE_IN=1 (v0.3.6, the owner, 2026-10-18), the last N_EMG inputs: where the enemy he believes in would come into his view.
# The walking map's way (walk, jump and teleporter links) from the believed place (v02_bel) to him, greedy by the table of
# ways (N_V02's), then walked back from him to the last point of it that his eyes see (a clear line, the shots' mask): the
# emergence point (the measuring version: AWARE_LOG's aw_emg). Worked out every EMG_EVERY frames a player (staggered) and
# held between; its direction from his eyes is read every frame. Live only while the belief is fresh (EMG_FRESH seconds at
# most) and the enemy is not in view; zeros otherwise. The inputs: live; sin and cos of the yaw from his facing to the point;
# that yaw / 30 (-1 to 1); the pitch from his view / 15 (-1 to 1); the distance from his eyes / 1500 (to 2); the point is the
# believed place itself (the whole way in sight); a way exists (0: none within the table's 16 s: the point inputs zeros).
# A token of its own ("emerge", sim/attn.py's LATE): a part of no older token, so that an older network's tokens keep their
# rows (tools/v036_init.py gives it with its gate shut). A game server's plugin needs nothing more (observe() keeps it).
EMERGE_IN = float(os.environ.get("EMERGE_IN") or 0.0) > 0
N_EMG = 8
EMG_EVERY, EMG_FRESH, EMG_STEPS = 4, 5.0, 96
PLAY_VARS = PLAY_VARS + ("RL_AIM", "PREFIRE", "EMERGE_IN")
# DRIFT_IN=1 (v0.3.8, the owner, 2026-10-20: "promising"; a PLAY_VAR, off by default), the last N_DRIFT inputs: how fast the
# enemy slides across his screen. The crosshair-to-enemy angles he already reads (opp_feat's coarse and fine yaw and pitch)
# are where the enemy is against the crosshair; a person also sees directly how fast that gap changes. The rate is the
# frame-to-frame change of exactly those perceived angles (the "known" enemy: his reaction and focus delays, the sight
# error PERCEPT_SIGMA / PERCEPT_TAU with the flinch, PERCEPT_SPEED, ZOOM_PERCEPT), his own view turn included as on a
# screen, in degrees a second. No truth: the sight error's own wander passes into the rate (at aim level 3 about 13 deg/s
# a frame on the raw rate, about 5 on the smoothed one, measured on testlab). On top of it, all named and all placeholders
# until pro-play measurements set them (the owner's standing policy of 2026-10-20):
#   DRIFT_DELAY  ms more before a motion is read than a place (0: the place's own delays only, which the rate inherits)
#   DRIFT_SIGMA  deg/s, a slowly wandering error on the rate (correlation time DRIFT_TAU s) beyond what the sight error gives
#   DRIFT_WEBER  the rate is read this share off (a wandering scale error, correlation time DRIFT_TAU): speed discrimination
#                in people is 5 to 10 % at best (Weber fraction), 0.10 a placeholder
#   DRIFT_MIN    deg/s: a slower slide is not noticed (reads 0); 2 a placeholder (a still-ish target)
#   DRIFT_SMOOTH s: the smoothed pair's decay (a person's motion sense integrates over about 0.1 s)
# Zeros with the enemy not in view (as he knows it: the delayed sighting), while dead, on the first frame of a sighting (no
# rate before two perceived frames), on a frame where the delay picked changes (focus), on a teleport or a respawn of either
# (a jump of 64 units in a frame) and when the attended enemy changes (groups). The inputs: the rate yaw / 180 and pitch / 90
# (clipped to -1..1; the sign of the angle inputs: + yaw = the enemy moves left of the crosshair, + pitch = down), then the
# same smoothed. A token of its own ("drift", sim/attn.py's LATE2, after every older kind: older networks keep their rows;
# tools/v038_init.py gives it with its gate shut). A plugin needs nothing more than observe() once a frame (it keeps the
# state; the plugins clear it where they clear opp_hist and on frames without observe()).
DRIFT_IN = float(os.environ.get("DRIFT_IN") or 0.0) > 0
N_DRIFT = 4
DRIFT_DELAY = float(os.environ.get("DRIFT_DELAY") or 0.0)
DRIFT_SIGMA = float(os.environ.get("DRIFT_SIGMA") or 0.0)
DRIFT_WEBER = float(os.environ.get("DRIFT_WEBER") or 0.10)
DRIFT_MIN = float(os.environ.get("DRIFT_MIN") or 2.0)
DRIFT_TAU = float(os.environ.get("DRIFT_TAU") or 0.15)
DRIFT_SMOOTH = float(os.environ.get("DRIFT_SMOOTH") or 0.1)
DRIFT_JUMP = 64.0
DRIFT_SCALE = (180.0, 90.0)
PLAY_VARS = PLAY_VARS + ("DRIFT_IN", "DRIFT_DELAY", "DRIFT_SIGMA", "DRIFT_WEBER", "DRIFT_MIN", "DRIFT_TAU", "DRIFT_SMOOTH")
# FIRE_QL=1 (v0.3.8, off by default; a PLAY_VAR: the plugins follow it; meant with RL_QL and MISSILE_POINT): every
# weapon fires on the frame of the command, as Quake Live does for a driven bot, not one frame later (fire_q; the rocket
# already does under RL_QL). How the game makes the shot (minqlx/botctl.c: the frame's command is moved as three, the
# press in each, the pitch final from the first and the yaw a share of the turn on each, y0 + turn * 8/25 on the first;
# the game fires in the first, after its 8 ms of movement, before G_RunFrame, so at the frame start's level time):
#   instant weapons (rail, lightning, machine guns, shotgun, gauntlet): from the eye after the first substep, along its
#     yaw and the final pitch, at the enemy where he stood at the frame's start, with the crouch he had then (the
#     game's own bot is moved after ours in its frame; a person's last command is at or before it: where his inputs
#     showed him);
#   rocket (with RL_QL): RL_QL's launch along that same yaw and pitch (RL_QL alone: the final yaw);
#   plasma and grenade: from the muzzle FIRE_MZ ahead of that eye (cut to whole units toward zero), its velocity cut
#     to whole units too (Quake 3's SnapVector on trBase and trDelta; the rocket's velocity as well), on the command's
#     frame, FIRE_FLY of flight at the frame's end (the game's 25 ms prestep and the frame: a driven bot's command runs
#     before G_RunFrame, at the frame start's level time). Fitted on weaponlab5's 29 grenades (2026-10-10, an AI-driven
#     bot: made inside G_RunFrame, so 25 ms of flight at that frame's end): a 26-unit eye, 5 units ahead, cut toward
#     zero, velocity cut, 25 ms: every first position within 0.43 units (mean 0.09; the record has one decimal); 14
#     ahead with 17 ms: 3.7 off. RL_QL's own fit agrees: 14 + 42 units at 1000 u/s = 5 + 51. A grenade's fuse counts
#     from the frame's start; what the first part of that flight meets (the enemy where he ends the frame, a wall) it
#     meets on this frame;
#   machine guns: the scatter of Quake 3's Bullet_Fire (a random angle, each axis a uniform share of it), MG_SPREAD wide
#     (its width not measured in the game: weaponlab3's machine guns at 400 units hit with every bullet);
#   shotgun: the pellets that hit are the expected share rounded, not a random draw: the game's pattern is fixed
#     (weaponlab3, 2026-10-03: 100, 60 and 25 damage at 100, 300 and 600 units on every repeat; the rounded share of the
#     simulator's spread gives exactly 100, 60, 25).
# The plugins send every press at once (duelbot.drive: no press_q hold; the rocket's only with RL_QL).
FIRE_QL = float(os.environ.get("FIRE_QL") or 0.0) > 0
HS_W = np.array([k_ != "proj" for k_ in W_KIND], bool)    # (FIRE_QL) the instant weapons
FIRE_MZ, FIRE_FLY = 5.0, 0.050                            # (FIRE_QL) the plasma's and the grenade's muzzle and first flight
PLAY_VARS = PLAY_VARS + ("FIRE_QL",)
# The senses as a person has them (v0.3.8; the input audit of 2026-10-20: scratch patches measured on v0.3.7's network, then
# made switches here). All PLAY_VARS, all off by default; off, the simulator is what it was (fixed runs, bit for bit).
#   HEAR_FIX=1       (with HEAR_QL for the walls) hearing by the game's events. Footsteps are events: one every HF_STEP_DT
#                    seconds (0.55) while a player is on the ground faster than HF_STEP_SPEED (150 units a second), not
#                    crouched; the first at once. A jump (off the ground, going up) is one too; in the air there is no
#                    step. The enemy's believed place (known) is set from a sound only on a footstep or a jump of his on
#                    that frame (no longer from every frame he runs faster than 250 units a second), with one direction
#                    error a sound (HF_DIR degrees, 10) and one error of the distance along it (HF_LOUD, a share: 0.3),
#                    the height HF_UP units off (40). The ear inputs (N_EAR): the same footsteps in place of every running
#                    frame (shots, jumps and landings as before); an event's own direction error (HF_DIR) and loudness
#                    error (HF_LOUD), once a sound; the closing-speed column 0 (a sound does not tell it); a weapon's hum
#                    (heard every frame) has a direction error that drifts (HF_HUM_TAU seconds, 1) instead of a fresh one a
#                    frame. The plugins make the same events (_hf_steps) and place the enemy by the same rule (_hf_place).
HEAR_FIX = float(os.environ.get("HEAR_FIX") or 0.0) > 0
HF_STEP_DT = float(os.environ.get("HF_STEP_DT") or 0.55)
HF_STEP_SPEED = float(os.environ.get("HF_STEP_SPEED") or 150.0)
HF_DIR = float(os.environ.get("HF_DIR") or 10.0)
HF_LOUD = float(os.environ.get("HF_LOUD") or 0.3)
HF_HUM_TAU = float(os.environ.get("HF_HUM_TAU") or 1.0)
HF_UP = float(os.environ.get("HF_UP") or 40.0)                       # (units: the height error of a sound)
HF_STEP_FRAMES = max(1, int(round(HF_STEP_DT / DT)))
PLAY_VARS = PLAY_VARS + ("HEAR_FIX", "HF_STEP_DT", "HF_STEP_SPEED", "HF_DIR", "HF_LOUD", "HF_HUM_TAU", "HF_UP")
#   VEL_FIX=1        the enemy's velocity as a person reads it, wherever his inputs use it (the velocity inputs, his speed when
#                    last seen, the believed place v02_bel that is made of it, the lead of a rocket or a plasma ball, the
#                    rocket's floor aim point): VEL_DELAY_MS old (200: the same as before, now a setting), times a scale error
#                    that drifts (VEL_WEBER, a share of the speed, 0.2; VEL_TAU seconds, 0.3), and below VEL_MIN units a
#                    second (30) read as standing still.
#   RANGE_FIX=1      the distance to an enemy in view judged by eye: his place (as the sight error leaves it) moved along
#                    the line from the eyes by a share of the distance that drifts (RANGE_WEBER, 0.15; RANGE_TAU seconds,
#                    0.5; at most half the distance); every input built on that place takes it (his place, his apparent
#                    size, the lead's flight time, the grenade arc, the rocket aim, the believed place).
#                    Both are kept in observe(): the plugins have them as they are.
VEL_FIX = float(os.environ.get("VEL_FIX") or 0.0) > 0
VEL_DELAY_MS = float(os.environ.get("VEL_DELAY_MS") or 200.0)
VEL_WEBER = float(os.environ.get("VEL_WEBER") or 0.2)
VEL_TAU = float(os.environ.get("VEL_TAU") or 0.3)
VEL_MIN = float(os.environ.get("VEL_MIN") or 30.0)
RANGE_FIX = float(os.environ.get("RANGE_FIX") or 0.0) > 0
RANGE_WEBER = float(os.environ.get("RANGE_WEBER") or 0.15)
RANGE_TAU = float(os.environ.get("RANGE_TAU") or 0.5)
PLAY_VARS = PLAY_VARS + ("VEL_FIX", "VEL_DELAY_MS", "VEL_WEBER", "VEL_TAU", "VEL_MIN", "RANGE_FIX", "RANGE_WEBER", "RANGE_TAU")
#   PROJ_FIX=1       (with PROJ_SEE) an enemy projectile as a person sees it: noticed only after PROJ_NOTICE_MS (100) in his
#                    sight on end (the view cone, a clear line); what he reads of it (place, speed, and the closest pass and
#                    its time worked out from them) is PROJ_READ_MS (100) old; a grenade's fuse only if he has seen it on
#                    every frame since it left (else the fuse input reads 0, as at its end). A projectile is followed by its
#                    slot (a new one when the slot's age goes back); the plugins keep a projectile in one slot while it
#                    flies (sync_world), as the simulator does.
PROJ_FIX = float(os.environ.get("PROJ_FIX") or 0.0) > 0
PROJ_NOTICE_MS = float(os.environ.get("PROJ_NOTICE_MS") or 100.0)
PROJ_READ_MS = float(os.environ.get("PROJ_READ_MS") or 100.0)
PLAY_VARS = PLAY_VARS + ("PROJ_FIX", "PROJ_NOTICE_MS", "PROJ_READ_MS")
#   SENSE_MINOR=1    the small ones, together: (a) the enemy's facing, crouch, being in the air and weapon in hand are read
#                    as he was one reaction time ago (the same old sighting as his place: opp_hist's pick; sm_hist keeps
#                    them), his facing with an error that drifts (SM_FACE_DEG, 15 degrees; SM_FACE_TAU, 0.5 s): the enemy
#                    inputs (his facing from where he was seen then), his body inputs, the weapon seen in his hands, and the in-air of the lead and the rocket aim;
#                    (b) a dropped weapon's time left only for a player who saw or heard the death (the killer, the dead,
#                    one with the dead in view or within earshot: drop_kn), else 0; (c) only a railgun's or a lightning
#                    gun's line is seen as a trail (no machine gun, shotgun or heavy machine gun lines); (d) a big item's
#                    pickup known only by its sound (not seen) starts his item clock with an error (SM_ITEM_SD, 0.75 s):
#                    it_t (the mega and the red armor) and ITEM_BELIEF's bel_t. All kept by the simulator's own calls,
#                    which the plugins make too (observe, note_pickup, note_shots); the duel plugin shows a dropped
#                    weapon's time to both (in a duel the killer and the dead know of every death that drops one).
SENSE_MINOR = float(os.environ.get("SENSE_MINOR") or 0.0) > 0
SM_FACE_DEG = float(os.environ.get("SM_FACE_DEG") or 15.0)
SM_FACE_TAU = float(os.environ.get("SM_FACE_TAU") or 0.5)
SM_ITEM_SD = float(os.environ.get("SM_ITEM_SD") or 0.75)
PLAY_VARS = PLAY_VARS + ("SENSE_MINOR", "SM_FACE_DEG", "SM_FACE_TAU", "SM_ITEM_SD")
#   HAND_BAND=1      a hand's bandwidth (the owner, 2026-10-20: "some kind of low pass filter on his LG aim"; every weapon,
#                    the hand is the same): the view's velocity follows the hand's (mv, after its smoothing and the flick
#                    cap) through a low-pass whose cutoff rises with the view's own speed, per axis: HB_FC Hz (4.0) plus
#                    HB_BETA Hz (0.5) for every degree a frame it turns (the one-euro filter's rule): small corrections are
#                    smoothed, a flick is let through. Sized offline on save 220's own commands while firing lightning
#                    (aim tables of 2026-10-20): yaw acceleration rms 4,600 -> 2,610 deg/s2, reversals 8.3 -> 4.8 a
#                    second, the view rate's power above 4 Hz 0.43 -> 0.27 (the pros: 2,455, 4.6, 0.29); a small step
#                    (0.8 deg/frame) at 50% / 90% in 50 / 100 ms (25 / 50 today), a flick (20 deg/frame) 66% -> 60% of its
#                    turn in 8 frames. The hand noise then rides on the filtered velocity. hb keeps the view's velocity; it
#                    is reset with mv. Scripted players are not filtered. The plugins call the same _hand_band.
HAND_BAND = float(os.environ.get("HAND_BAND") or 0.0) > 0
HB_FC = float(os.environ.get("HB_FC") or 4.0)
HB_BETA = float(os.environ.get("HB_BETA") or 0.5)
PLAY_VARS = PLAY_VARS + ("HAND_BAND", "HB_FC", "HB_BETA")
PLAY_VARS = PLAY_VARS + ("AIM2", "AIM2_SPLIT", "AIM2_FOCUS", "AIM2_FLINCH") + AIM2_LIVE + ("MOTOR_NOISE", "MOTOR_BASE")   # (AIM2)
# DUEL_QL=1 (v0.3.8, off by default; a PLAY_VAR): the duel factory's numbers where they differ from free-for-all's, in
#                    which every lab measurement before 2026-10-19 was made (the game's settings dump on the servers, which
#                    run the duel factory: docs/v0.3.7/REPORT_PLAYTEST_2026-10-19.md section 1). (a) With QL_JUMP, no jump
#                    within DQ_JUMP_MS (50) of the last (pmove_JumpTimeDeltaMin: free-for-all 100). (b) With QL_MOVE,
#                    wading at DQ_WADE (0.75: free-for-all's 0.8 is qsim.QL_WADE). (c) An item (and a dropped weapon) is
#                    taken with his origin at most DQ_PICK_Z (51) above or below its resting origin (free-for-all's
#                    g_itemHeight 35, duel's 15): 4,656 duel pickups of 2026-10-19/20 (play tests and the public server)
#                    reach 48.5 / 50.4 / 55 (99% / 99.9% / the highest, one) above it, the 7,767 free-for-all pickups of
#                    2026-10-12 63.7 / 64.7 / 66.6; the simulator's 56 lies between. Horizontally both modes are the same
#                    (dx, dy 99% 39): dxy < 36 stays. The game's crouch step jump (free-for-all on, duel off) is not in the
#                    simulator (its jumps never look at the crouch): duel-like already. The plugins and the servers need
#                    nothing: the server's game is the truth.
DUEL_QL = float(os.environ.get("DUEL_QL") or 0.0) > 0
DQ_JUMP_MS = float(os.environ.get("DQ_JUMP_MS") or 50.0)
DQ_WADE = float(os.environ.get("DQ_WADE") or 0.75)
DQ_PICK_Z = float(os.environ.get("DQ_PICK_Z") or 51.0)
PICK_Z = DQ_PICK_Z if DUEL_QL else 56.0                    # an item's reach in height (|dz| under it)
PLAY_VARS = PLAY_VARS + ("DUEL_QL", "DQ_JUMP_MS", "DQ_WADE", "DQ_PICK_Z")
# v0.4.2a (docs/v0.4.0/RUN_v0.4.2a.md; the trainer's --rule-fade): what the simulator itself did with the old hand-built belief
# of the unseen enemy (v02_bel, v02_bel_ok, the stack filter es_h + es_a) moves to the brain's answer on the fade's gate g.
#   BRAIN_READ=1   (a PLAY_VAR) at each life's start (_fresh) a draw with chance g, his seat's (set_brain_g; the trainer sends his
#                  g for his seats and the league file's for the league's), on its own random stream (brain_rng: the game's
#                  stream is never touched, so g = 0 is exactly the simulator without it). A life drawn "on the brain" reads
#                  the brain's answer of the frame (brain_in: the trainer's token answer, sent with the actions; in the checks
#                  test_suite.Policy.brain_answer) in place of the rule in: the legs' look point (_legs_c2, LEGS_LOOK), the
#                  hunt's target (_trip_goal, HUNT), the item lesson's silences (_rule_contested, RULE_CONTEST; RULE_HUNT by
#                  the brain's stack band: its odds times BRAIN_BAND_MID), the openings' "enemy near the item" (_open_step).
#                  The brain's place counts as believed while the answer is there and he saw or heard the enemy within
#                  BRAIN_KNOWN seconds (the same raw clock as the rule's: V02_KNOWN; 0: whenever there is an answer). A life on
#                  the brain with no answer believes nothing (it never falls back on the rule). Left on the rule: the
#                  spawn-moment curriculum (_moment_step), AWARE_LOG, the readout's yardstick (aux).
#                  Counted: stats["brain_lives"] (his lives begun, on the brain), stats["brain_read"] (per reader of
#                  BRAIN_READERS: seats read, on the brain), stats["brain_err"] (per band of BRAIN_ERR_BINS, seconds since
#                  seen, out of view, both believing: frames, the rule's place error, the brain's).
#   BLIND_BRAIN=1  (a training switch: a pay; the owner's word 2026-10-23) BLIND_RULE's pre-fire exemption (a hitscan shot
#                  within PREFIRE_R of where the enemy must be, in the first PREFIRE_T seconds unseen) and the blind rockets'
#                  "near where he thinks the enemy is" / "on a way from there" read the brain's place for a life on the brain
BRAIN_READ = float(os.environ.get("BRAIN_READ") or 0.0) > 0
BLIND_BRAIN = float(os.environ.get("BLIND_BRAIN") or 0.0) > 0
#   BLIND_AHEAD=1  (v0.4.3, a training switch beside BLIND_BRAIN; the owner, 2026-10-23: "no cost to spam/prefire where he expects
#                  the enemy is/will be", "it probably should be 'will be'") for a life on the brain, the waiver also where the
#                  brain says the enemy WILL BE: its readout ahead (sim/ahead.py "fut": his place in 1, 2 and 4 s, kept in map
#                  coordinates at the brain's tick; the trainer sends it with the answer, brain_in's "fut") within PREFIRE_R of
#                  the crosshair's line (a billed hitscan shot, seen_t up to BLIND_AHEAD_T seconds, 6) or within BLIND_NEAR of a
#                  blind rocket's landing (blind_rl_how's sixth column, "ahead"). A cost waived, never a pay; no answer ahead
#                  (none sent, a reset, the brain's answer not believed: brain_ok): nothing waived. Off: as before, bit for bit.
BLIND_AHEAD = float(os.environ.get("BLIND_AHEAD") or 0.0) > 0
BLIND_AHEAD_T = float(os.environ.get("BLIND_AHEAD_T") or 6.0)
#   BLIND_AHEAD_P=p  (v0.4.3; a LIVE_VARS name: live.json opens it slowly) with BLIND_AHEAD=1, the chance that a life (drawn at its
#                  start with BRAIN_READ's draw, brain_draw) has the waiver on "will be": a life on the brain AND drawn with chance
#                  p. Its own random stream (ahead_rng: the game's and the brain's streams are never touched), one number a seat
#                  at every life's start whatever p is: p = 0 is exactly BLIND_AHEAD off in play and pay. Unset: 1 (every life on
#                  the brain, the switch as first built). Counted: stats["ahead_lives"] (his lives begun, with the waiver).
_bap_ = os.environ.get("BLIND_AHEAD_P")
BLIND_AHEAD_P = float(_bap_) if (_bap_ or "").strip() else 1.0
if not 0.0 <= BLIND_AHEAD_P <= 1.0:
    raise ValueError("BLIND_AHEAD_P must be within 0 .. 1")
BRAIN_KNOWN = float(os.environ.get("BRAIN_KNOWN") or V02_KNOWN)
BRAIN_BAND_MID = np.array([37.5, 100.0, 162.5, 250.0], np.float32)    # the stack bands' middles (under 75, 75-124, 125-200, over 200)
BRAIN_READERS = ("legs_look", "hunt", "contest", "rule_hunt", "open", "blind")
BRAIN_ERR_BINS = ("0-2s", "2-5s", "5-10s", "10s+")
PLAY_VARS = PLAY_VARS + ("BRAIN_READ", "BRAIN_KNOWN")
N_FFA = 2 * 11 + 2                                     # two more enemies in view (11 each), enemies in view, players
OBS_DIM = OBS_BASE + N_EXTRA + N_FIGHT + N_MEM + N_ROUTE + N_FFA + N_PAD + N_EAR + N_MORE + N_DENSE + N_V9 + N_INTENT + N_DROP + N_V14 + N_V15 + N_V02 + N_B2 + N_B3 + N_ES + N_RAIM + N_PREF + N_EMG + N_DRIFT
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
# (2026-10-12, the questions a pro asks himself; the trainer's --aux-heads target, strength, first)
#   en_target                what the enemy goes for, a number of INTENTS: a network's seat its own intention as the simulator
#                            holds it (self.intent: 0 nothing, an item, the enemy, a holding place; after a pickup it stays
#                            the item until his next reading); the scripted item runner and the lobber the item the rule
#                            names them, to which they walk (_runner_keys: self.intent_teach, 0 nothing). -1, nothing to
#                            say: the other scripted opponents (the strafing target, the fighter; the holder and the
#                            watcher, whose target may be a place that is no intention), and a round without other players
#   en_band                  the enemy's health and armor together, in bands (AUX_BANDS): 0 under 75, 1 from 75 to under
#                            125, 2 from 125 to 200, 3 over 200
#   en_weapon                the weapon in the enemy's hand, a number of WEAPONS
#   mega_take, red_take      in this step: who took the mega, the red armor (the items of mega_s and red_s): 0 nobody of his
#                            match, 1 he, 2 another player of his match (in a pair: the enemy)
AUX_COLS = ("en_fwd", "en_left", "en_up", "en_alive", "en_in_view", "mega_s", "red_s", "dmg_dealt", "dmg_taken", "frag", "fragged",
            "x", "y", "z", "yaw", "pitch", "died", "eye_h",
            "en_target", "en_band", "en_weapon", "mega_take", "red_take",
            "en_near")
if HEAD_EVENTS:                                            # (HEAD_EVENTS) the win label: see there
    AUX_COLS = AUX_COLS + ("win_game", "win_band")
#   en_near                  (--aux-heads near) the landmark nearest the enemy where he truly is, a number of INTENTS as
#                            en_target: of the targets with a row of the route field on this map (the items; with TARGETS
#                            the map's holding places) the one with the least seconds of way FROM his place (route.T[row,
#                            route.locate(place)]; of several items of a kind the nearest). Never 0 ("none") or "EN". -1,
#                            nothing to say: a round without other players, no walking map, no landmark he can walk to
# v0.3.11 (docs/v0.3.11/INFO_PAY.md; the owner, 2026-10-22: "keep a running estimate of position, stack, ownership of
# weapons, direction, speed, etc of the enemy in memory ... paid proportional to how accurate this is"). TRACK_TRUTH=1 (a
# training switch, off by default; off: info["aux"] has exactly the columns above) adds the truth the trainer's belief
# readout (--track) is taught and scored on (--info-pay, in the trainer). Labels only, never inputs, never read by the
# simulator itself:
#   en_vfwd, en_vleft        the enemy's horizontal velocity turned to his facing (units a second)
#   en_own_rl ... en_own_sg  1: the enemy owns the rocket launcher, railgun, lightning gun, plasma gun, grenade launcher, shotgun
#   trk_on                   1: a duel's game (a whole game or a pro start; not a jump run, a lab, a drill) with both players
#                            alive and in play: the frames the readout is taught and scored on (the same for both seats)
#   unseen_s                 seconds since the enemy was last in his view (the simulator's own `visible`); TRACK_UNSEEN_CAP
#                            from the enemy's spawn until he is seen (the counters by time unseen)
#   bel_ok, bel_fwd, bel_left, bel_up, bel_age   his hand-built belief of v0.2's inputs (v02_bel, v02_bel_ok, v02_bt_now as
#                            the last observe() left them: one frame old), turned to his facing: the bar the readout must beat
#   es_stack                 the enemy's stack as EN_STACK's belief has it (health + armor; -1 with EN_STACK off)
TRACK_TRUTH = float(os.environ.get("TRACK_TRUTH") or 0.0) > 0
TRACK_OWN = ("rl", "rg", "lg", "pg", "gl", "sg")
TRACK_UNSEEN_CAP = 60.0
if TRACK_TRUTH:
    AUX_COLS = AUX_COLS + ("en_vfwd", "en_vleft") + tuple("en_own_" + w_ for w_ in TRACK_OWN) + (
        "trk_on", "unseen_s", "bel_ok", "bel_fwd", "bel_left", "bel_up", "bel_age", "es_stack")
# v0.4.0 brain, the zones and the velocity as speed and direction (the owner, 2026-10-23: "let's replace the 10+s range with
# the distribution over locations"; 2026-10-22: "speed+direction separately makes sense. Probably both can be averaged over a
# short window"). TRACK_Z=1 (a training switch, off by default, with TRACK_TRUTH only; off: info["aux"] as above) adds the
# truth of the readout's new outputs (sim/track_z.py). Labels only, never inputs, never read by the simulator itself:
#   en_zone                  the zone the enemy stands in (sim/zonemap.py: the map's sim/zones/<map>.json); -1 with no zones file
#   zone_n                   the map's number of zones (0 with no file): the readout's zone odds are masked to it
#   zone_map                 the map's number in zones.MAPS (-1: none)
#   en_spd8                  the enemy's mean horizontal speed over the last TRACK_Z_WIN frames (8: 0.2 s, the brain's tick;
#                            fewer since his spawn), units a second
#   en_mvf8, en_mvl8         the enemy's mean horizontal velocity over the same frames, turned to his facing now (units a
#                            second): its direction is the direction's truth, its size against en_spd8 how straight he went
#   zone_seen                the zone the enemy stood in when he was last in his view (this life of the enemy's; -1: not
#                            seen since the enemy's spawn): a bar for the readout's zones (the counters), never an input
TRACK_Z = float(os.environ.get("TRACK_Z") or 0.0) > 0
TRACK_Z_WIN = int(os.environ.get("TRACK_Z_WIN") or 8)
if TRACK_Z:
    assert TRACK_TRUTH, "TRACK_Z needs TRACK_TRUTH=1"
    AUX_COLS = AUX_COLS + ("en_zone", "zone_n", "zone_map", "en_spd8", "en_mvf8", "en_mvl8", "zone_seen")
# v0.4.1 (docs/v0.4.0/RUN_v0.4.1.md: the item race for the mega and the red armor). TRACK_RACE=1 (a training switch, off by
# default, with TRACK_TRUTH only; off: info["aux"] as above) adds the truth of the brain's readout ahead (sim/ahead.py, the
# trainer's --ahead); labels only, never inputs, never read by the simulator itself:
#   race_me_mh, race_en_mh   the seconds of way (the walking map's route field, as en_near's) from him and from the enemy to
#                            the mega (the nearest, where a map has several), capped at RACE_CAP (no way, no mega, no map)
#   race_me_ra, race_en_ra   the same to the red armor
# With mega_s / red_s (the seconds until it is back) the trainer makes his walking-time lead (race_en - race_me) and whether
# the enemy is there when it comes back (race_en at that frame within RACE_THERE seconds; sim/ahead.py)
TRACK_RACE = float(os.environ.get("TRACK_RACE") or 0.0) > 0
RACE_CAP = 30.0
if TRACK_RACE:
    assert TRACK_TRUTH, "TRACK_RACE needs TRACK_TRUTH=1"
    AUX_COLS = AUX_COLS + ("race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra")
# v0.4.3 (B-280; docs/v0.4.3/RUN_v0.4.3.md, "In control"). CONTROL_TRUTH=1 (a training switch, off by default; off: info["aux"]
# as above and nothing else changes) adds the truth of the brain's readout "in control": his share of the next two spawns of
# the mega and the red armor (the two kinds together, in the order they come up; an item lying there at the frame is the
# first). Known only in hindsight, so it is given CONTROL_H seconds late: the row of frame F carries the label of frame
# F - CONTROL_D (the trainer keeps the brain's state that long). Labels only, never inputs, never paid, never read by the
# simulator itself:
#   ctl_lab   of frame F - CONTROL_D, his share of the next two spawns: each 1 taken by him, 0 by the enemy, 0.5 come up and
#             still lying there CONTROL_H seconds on; their mean. -1, no label: that frame was not a duel's game (a whole game
#             or a pro start: as trk_on without "alive"), its round ended before both were taken, or the second had not
#             come up by then (a map without the two), or F < CONTROL_D
#   ctl_one   the same for the next spawn alone (1, 0, 0.5, -1)
#   ctl_mh, ctl_ra   the same for the next spawn of the mega alone, of the red armor alone (-1 also: the map has none)
#   ctl_age   the frames since the last fresh simulator, capped at CONTROL_D + 1: the trainer's check of the alignment
#   ctl_ok    1: THIS frame will have a label CONTROL_D frames on if its spawns resolve (a duel's game; not delayed)
CONTROL_TRUTH = float(os.environ.get("CONTROL_TRUTH") or 0.0) > 0
CONTROL_H = float(os.environ.get("CONTROL_H") or 90.0)
CONTROL_D = int(round(CONTROL_H / DT))
CONTROL_M = 16                                             # instances kept per match and item
if CONTROL_TRUTH:
    AUX_COLS = AUX_COLS + ("ctl_lab", "ctl_one", "ctl_age", "ctl_ok", "ctl_mh", "ctl_ra")
AUX_ITEM_CAP = 40.0
AUX_BANDS = (75.0, 125.0, 200.0)
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
WEAPON_PICK_AMMO = {d[1]: float(d[3]) for d in ITEM_DEFS.values() if d[0] == "wp"}     # (WEAPON_FREE) one pickup's ammunition
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
    @property
    def level(self):
        """(B-275) the view's pull toward level a frame with no enemy in view: LEVEL_PULL (live), unless a tool set env.level"""
        return LEVEL_PULL if getattr(self, "_level", None) is None else self._level

    @level.setter
    def level(self, v):
        self._level = None if v is None else float(v)

    def __init__(self, bsp, n_matches=256, seed=0, substeps=(8, 8, 9), dmg_reward=0.004, nav=None, close_p=0.0,
                 loadout="full", drill_weapons=(RL, RG, LG), teacher=None, group=2):
        """close_p: chance a respawn lands 300-700 units from the opponent with line of sight (curriculum).
        loadout: weapons at spawn ("full" = RL/RG/LG, "all" = every weapon, "mg" = machine gun + gauntlet only).
        drill_p (attribute): share of rounds where both players have exactly one weapon from drill_weapons."""
        self.M = n_matches
        self.G = G = int(group)                         # players per group: all of a group fight each other
        self.n = group * n_matches
        ar_ = np.arange(self.n)
        self.slot = ar_ % G
        self.grp = (ar_ // G * G)[:, None] + np.arange(G)[None, :]                      # every member of the player's group
        self.others = (ar_ // G * G)[:, None] + (self.slot[:, None] + np.arange(1, G)[None, :]) % G     # the other members
        self.foe = self.others[:, 0].copy()             # the enemy a player is attending to (G = 2: the opponent)
        self.fidx = np.zeros(self.n, np.int64)          # ... as an index into others
        self.vis2 = np.zeros((self.n, G - 1), bool)     # per other player: in view / frames in view / noticed /
        self.vis_run2 = np.zeros((self.n, G - 1), np.int64)     # last known position / seconds since seen or heard
        self.acq2 = np.zeros((self.n, G - 1), bool)
        self.acq_extra2 = np.zeros((self.n, G - 1), np.int64)   # frames more before he is noticed, by surprise
        self.known2 = np.zeros((self.n, G - 1, 3), np.float32)
        self.seen2 = np.full((self.n, G - 1), 9.0, np.float32)
        self.dmg_on = np.zeros((self.n, G), np.float32)  # damage dealt to each member during his current life
        self.shot_src = np.full(self.n, -1, np.int64)   # whose shot / pain sound a player last noted
        self.pain_src = np.full(self.n, -1, np.int64)
        self.ffa_hist = []
        self.w = World(bsp, n=self.n)
        self.new_lib = bool(getattr(self.w, "new", False))  # the simulator library of 2026-10-09 (masks, many contents, ...)
        assert self.new_lib or not SHOT_MASK, "SHOT_MASK needs the simulator library of 2026-10-09"
        self.sight = SOLID_ONLY if SHOT_MASK else None      # the mask of shots, missiles, splash and sight (None: the player's)
        assert self.new_lib or not LAVA, "LAVA needs the simulator library of 2026-10-09"
        assert self.new_lib or not (QL_MOVE or SOLIDS), "QL_MOVE and SOLIDS need the simulator library of 2026-10-09"
        if self.new_lib:                                     # (the library keeps these between worlds of one process: set both ways)
            from qsim import QL_STEP, QL_WADE
            self.w.set_params2(DQ_WADE if DUEL_QL else QL_WADE, QL_STEP) if QL_MOVE else self.w.set_params2()
            self.w.add_solids() if SOLIDS else self.w.lib.qsim_clear_solids()
        if QL_FLOAT or hasattr(self.w.lib, "qsim_snap"):
            self.w.set_snap(not QL_FLOAT)
        if QL_FWD or QL_LAND or hasattr(self.w.lib, "qsim_params3"):
            self.w.set_params3(QL_FWD, QL_LAND)
        if QL_JUMP or hasattr(self.w.lib, "qsim_params4"):
            self.w.set_params4(QL_JUMP, min_ms=DQ_JUMP_MS if DUEL_QL else 100.0)
        if not AUTO_HOP:                                     # (AUTO_HOP=0) a jump held over a landing does not jump again (World() set 1)
            from qsim import QL_PARAMS
            self.w.set_params(**dict(QL_PARAMS, auto_hop=0))
        self.lava_t = np.zeros(self.n, np.float32)          # seconds until lava or slime hurts him again (LAVA)
        self.pvs = None                                      # (HEAR_QL) the map's visibility data
        if HEAR_QL:
            import pvs as PVS_
            self.pvs = PVS_.Vis(bsp)
        self.rsp_wait = np.zeros(self.n, np.int64)          # (RESPAWN_QL) frames until he is back; 0: in play
        self.rsp_born = np.zeros(self.n, bool)              # (RESPAWN_QL) back at a spawn point on this frame
        self.rng = np.random.default_rng(seed)
        self.brain_seed = abs(int(seed))                     # (BRAIN_READ) the draws' own stream is made from it
        self.stag_rng = np.random.default_rng([abs(int(seed)), 0x57A6])     # (STAGGER_START) its own stream: the run's untouched
        self.stag_first = np.ones(self.M, bool)             # (STAGGER_START) the match's first whole game is still to come
        self.substeps = tuple(substeps)
        self.dmg_reward = dmg_reward
        self.loadout = loadout
        self.react_frames = REACT_FRAMES
        self.acquire_frames = ACQUIRE_FRAMES
        self.react_seat = self.acquire_seat = None             # (SEAT_DELAYS) one a seat, in a check of two networks
        self.vis_run = np.zeros(group * n_matches, np.int64)       # frames the opponent has been in view without a break
        self.acquired = np.zeros(group * n_matches, bool)          # in view long enough to have been noticed
        self.acq_extra = np.zeros(group * n_matches, np.int64)     # frames more this time, by surprise (surprise_frames)
        self.fire_prev = np.zeros(group * n_matches, bool)
        self.human_aim = True                           # flick cap, hand noise and reload jitter for policy players
        # spawn weapons in normal rounds: share of rounds with 1-2 random weapons each / the real duel spawn
        # (machine gun + gauntlet) / every weapon. Sets are drawn per player at the start of each round.
        self.loadout_p = (0.4, 0.2, 0.2, 0.2)           # ..., and both players with the same single weapon
        self.load_sets = [None] * (group * n_matches)
        self.item_reward = 0.0                          # optional shaping: reward per 100 points of health/armor picked up
        sp_ = self.w.spawns()
        if SPAWN_QL:                                         # (SPAWN_QL) the game spawns info_player_start as a spawn point too
            sp_ = sp_ + [e for e in self.w.entities if e.get("classname") == "info_player_start" and "origin" in e]
        self.spawns = np.array([e["origin"] for e in sp_], np.float32)
        self.spawn_yaw = np.array([float(e.get("angle", 0)) for e in sp_], np.float32)
        self.close_p = close_p
        self._level = None                              # pitch eases back toward level (1.0 = off): the property level, LEVEL_PULL
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
        self.script = np.zeros(group * n_matches, np.int64)  # per player: 0 = policy, 1 = strafing target, 2 = scripted fighter
        self.sc_t = np.zeros(group * n_matches, np.float32)
        self.sc_dir = np.ones(group * n_matches, np.int64)
        self.sc_fwd = np.zeros(group * n_matches, np.int64)
        self.sc_jump = np.zeros(group * n_matches, bool)
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
        self.sc_persona = np.zeros(group * n_matches, np.int64)   # scripted fighter style (PERSONAS)
        self.sc_wpn = np.zeros(group * n_matches, np.int64)
        self.persona_p = np.array([1.0 / NIGHTMARE] * NIGHTMARE + [0.0] * (len(PERSONAS) - NIGHTMARE))   # (the stand-in is never drawn)
        self.persona_force = None                       # test rooms: always this style
        self.move_len = 40.0                            # seconds per movement round (several goals in a row)
        # movement teacher: a movement-only policy (sim/train_move.py) whose actions are offered as labels in
        # movement rounds (self.teach: forward, strafe, jump, turn bin; -1 = no label)
        self.teacher = None
        self.teach = np.full((group * n_matches, 5), -1, np.int64)      # (the fifth: the weapon key by the weapon rule, -1 = no label)
        nn_ = group * n_matches
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
        self.zones = None                               # (TRACK_Z) the map's zones (sim/zonemap.py), for the truth columns only
        if TRACK_Z:
            import zonemap as zones_
            self.zones = zones_.load(name)
            self.zone_map = zones_.MAPS.index(name) if name in zones_.MAPS else -1
        self.sc_style = 0                               # target movement: 0 random (training), else STYLES index
        self.close_band = (300.0, 700.0)                # distance of "close" spawns (test rooms set their own)
        self.fixed_kind = None                          # test rooms: (kind, scripted type for the odd player)
        self.goal = np.full(group * n_matches, -1, np.int64)  # MOVE rounds: index of the goal item
        self.phi = np.zeros(group * n_matches, np.float32)    # estimated seconds to the goal
        self.walls = np.ones((group * n_matches, N_WALL), np.float32)
        self.field = None
        self.round_len = 15.0                           # seconds; matches restart (players near each other) after this
        self.round_t = self.rng.uniform(0, 15.0, n_matches).astype(np.float32)
        # a check's own clocks (2026-10-13; tools/duel_eval.py SeatClock): per seat the seconds since his round or game began,
        # whether his network was trained on whole games, what is added to the scores as he counts them, and (optional) the
        # length his "left" input counts down over. All None: the simulator's own clock and score (training, a server).
        self.clock_t = self.clock_game = self.clock_score = self.clock_len = None
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
        self.drop_kn = np.zeros((self.n, DROP_MAX), bool)                # (SENSE_MINOR) he saw or heard the death that left it
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
        nn2 = group * n_matches
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
        self.big_got = np.zeros((self.n, 3), bool)         # (BIG_PICK) rocket launcher, lightning gun, railgun paid this life
        self.self_debt = np.zeros(self.n, np.float32)       # (SELF_DEBT) health and armor he took off himself, not yet refilled
        self.item_up_t = None                               # per item: seconds it has been lying there
        self.last_vel = np.zeros((self.n, 3), np.float32)   # the enemy's speed and heading when last seen
        self.walk_last = np.zeros(self.n, bool)             # the walk key as the little finger has it
        self.pad = np.zeros(self.n, np.float32)             # the hand on the mouse pad, degrees from the middle
        self.pad_lift = np.zeros(self.n, np.int64)          # frames the mouse is still in the air
        self.pad_on = True
        self.ear = np.zeros((self.n, 4), np.float32)        # last sound heard: direction (world, radians), height, loudness, closing
        self.ear_t = np.full(self.n, 99.0, np.float32)      # seconds since
        self.ear_hum = np.full(self.n, -1, np.int64)        # the humming weapon heard with it (RG, LG) or -1
        self.hf_cnt = np.full(self.n, -1, np.int64)         # (HEAR_FIX) frames since his last footstep (-1: not running)
        self.hf_ev = np.zeros(self.n, bool)                 # (HEAR_FIX) he made a footstep or a jump this frame
        self.hf_foot = np.zeros(self.n, bool)               # (HEAR_FIX) ... a footstep (LG_DEAF muffles these)
        self.lgd_fire = np.zeros(self.n, bool)              # (LG_DEAF) he is firing the lightning gun (step() and the plugins set it)
        self.lgq_t = None                                   # (LG_QUIET_COST) seconds since he last had the enemy acquired: made when on
        self.wr_ = None                                     # (WATCH_PAY, LG_QUIET_COST) the ring of the last 2 s: made when on
        self.hf_hum = np.zeros(self.n, np.float32)          # (HEAR_FIX) the drifting direction error on a hum (degrees)
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
        self.run_tw = None                                  # ... the map's weights by intention (None: no row for this map)
        try:
            with open(RUN_TARGETS, encoding="utf-8") as fh_:
                rt_ = json.load(fh_).get(os.path.splitext(os.path.basename(bsp))[0].lower())
            if isinstance(rt_, dict) and rt_:
                self.run_tw = {INTENTS.index(k_): float(v_) for k_, v_ in rt_.items() if k_ in INTENTS and float(v_) > 0}
                self.run_tw = self.run_tw or None
        except (OSError, ValueError):
            pass
        self.jrun = np.zeros(self.n, bool)                  # in a jump run
        self.jrun_k = np.zeros(self.n, np.int64)            # ... the jump his try is for
        self.jrun_t = np.zeros(self.n, np.float32)          # ... the seconds the try has left
        self.jrun_edge = np.zeros(self.n, bool)             # ... he has been at its take-off
        self.jrun_over = np.zeros(self.n, bool)             # ... he is over it
        self.jrun_lift = np.zeros((self.n, 3), np.float32)  # ... (JUMP_OVER_ANY) where he last touched the floor
        self.jrun_new = np.zeros(self.n, bool)              # ... the try began this frame
        self.jrun_it = np.full(self.n, -1, np.int64)        # ... the item that is its target
        self.jrun_paid = np.zeros(self.n, np.float32)       # ... what its way has paid so far (given back if it ends without the item)
        self.jrun_far = np.zeros(self.n, bool)              # ... (JUMP_FAR_P) it began far back, moving
        self.jrun_open = np.zeros(self.n, bool)             # ... (JUMP_WEIGHT) its outcome is not in his success yet
        self.jw_s = np.full(64, 0.5)                        # (JUMP_WEIGHT) per jump of this map: his success, his tries counted
        self.jw_n = np.zeros(64)
        self.jfield_land = set()                            # the sets of ways (jfields) whose goal row leads to a jump's landing first
        self.jump_far = {}                                  # (JUMP_FAR_P) (jump, its entry in jump_tries) -> the far starting spots
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
        self.solo_now = np.zeros(self.n, bool)              # SOLO_SELF: in a run this frame (his legs' choices not taken)
        self.ta_add = np.zeros(self.n, np.float32)          # LEGS_TURN_ADD: his correction of this frame on top of his legs' turn (degrees)
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
                mp_ = os.path.splitext(os.path.basename(bsp))[0]
                self.jstart = {}                             # (PRO_JSTART_P) jump index -> the pros' run-up states
                self.stuck_names = []                        # (STUCK_STARTS) [(index into the jump lists, its name)]
                ps_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_jump_starts", mp_ + ".npz")
                if PRO_JSTART_P > 0 and os.path.exists(ps_):
                    S_ = np.load(ps_)
                    for k_, j_ in enumerate(self.jumps):
                        m_ = (S_["jump_id"] == j_["id"]) & (S_["lead"] <= PRO_JSTART_MAXLEAD)
                        if m_.any():
                            self.jstart[k_] = (S_["pos"][m_], S_["vel"][m_], S_["yaw"][m_])
                self.jfocus = np.array([JUMP_FOCUS_W if j_["id"] in JUMP_FOCUS.get(mp_, ()) else 1.0 for j_ in self.jumps])
                self.jdrop_ok = np.array([j_["id"] in self.jump_open for j_ in self.jumps], bool)   # (JUMP_KEEP_CLOSED)
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
                    self.jfield_land.add(len(self.jfields))
                    self.jfields.append(X_)
                if JUMP_FAR_P > 0:
                    self._jump_far_spots()
                self.n_real_jumps = len(self.jumps)
                if STUCK_STARTS:                             # (STUCK_STARTS) the spots he gets stuck at, as tries after the jumps
                    for sp_ in [x_ for x_ in json.load(open(STUCK_FILE)) if x_["map"] == mp_]:
                        if sp_["goal"] not in self.route_goal:
                            continue
                        g_ = int(np.argmin([float(J_.T[q_, int(R_.locate(np.array([sp_["start"]], np.float32))[0])]) if lab_ == sp_["goal"]
                                            else 1e9 for q_, lab_ in enumerate(self.route_goal)]))
                        a_ = np.array(sp_["start"], np.float32)
                        n0_ = int(R_.locate(a_[None])[0])
                        if float(J_.T[g_, n0_]) >= 1e8:
                            continue
                        nd_, b_ = n0_, None                  # the escape: the first spot on his way at STUCK_ESC units from the start
                        for _ in range(400):
                            nx_ = int(J_.next[g_, nd_])
                            if nx_ < 0:
                                break
                            nd_ = nx_
                            if math.hypot(*(R_.nodes[nd_][:2] - a_[:2])) >= STUCK_ESC or abs(float(R_.nodes[nd_][2] - a_[2])) >= 48.0:
                                b_ = np.array(R_.nodes[nd_], np.float32)
                                break
                        if b_ is None:
                            b_ = np.array(R_.goals[g_], np.float32)
                        k_ = len(self.jump_a)
                        self.jump_a = np.concatenate([self.jump_a, a_[None]])
                        self.jump_b = np.concatenate([self.jump_b, b_[None]])
                        self.jump_lab_off = np.append(self.jump_lab_off, True)
                        self.jfocus = np.append(self.jfocus, 1.0)
                        self.jdrop_ok = np.append(self.jdrop_ok, True)
                        self.jump_tries[k_] = [(g_, np.array([n0_]), 0)]
                        jt_, rs_ = float(sp_.get("jitter", 24.0)), np.random.default_rng(7 + k_)    # (its own draws: the run's stream untouched)
                        P_ = a_[None] + np.c_[rs_.uniform(-jt_, jt_, (64, 2)), np.zeros(64)].astype(np.float32)
                        self.jstart[k_] = (P_, np.zeros((64, 3), np.float32),
                                           (float(sp_["yaw"]) + rs_.uniform(-30, 30, 64)).astype(np.float32))
                        self.stuck_names.append((k_, sp_["name"]))
                if JUMP_SOLID_FIX:                           # (JUMP_SOLID_FIX) no start spot inside something solid
                    self._jump_solid_fix()
                self.jrunup = {}                             # (JUMP_RUNUP) (jump, entry) -> run-up start spots
                self.jrunup_line = set()
                if JUMP_RUNUP > 0:
                    self._jump_runup()
                    self._jump_runup_drop()
                sk_ = JUMP_SKIP.get(mp_, set())                  # (JUMP_SKIP) the jumps the owner left out of practice
                for k_ in [k_ for k_ in list(self.jump_tries) if k_ < self.n_real_jumps and int(self.jumps[k_]["id"]) in sk_]:
                    del self.jump_tries[k_]
                    self.jump_far = {kk_: v_ for kk_, v_ in self.jump_far.items() if kk_[0] != k_}
                    self.jrunup = {kk_: v_ for kk_, v_ in self.jrunup.items() if kk_[0] != k_}
                    self.jrunup_line = {kk_ for kk_ in self.jrunup_line if kk_[0] != k_}
                    self.jstart.pop(k_, None)
        self.rjs, self.rj_fields, self.rj_g, self.rj_start = [], [], [], []     # RJ_RUN_P: the map's rocket jumps, a try's ways,
        self.rj_open_field = None                           # ... the goal row that is the landing, the starting spots; RJ_OPEN
        self.rj_run_p = RJ_RUN_P
        self.rjrun = np.zeros(self.n, bool)                 # in a rocket jump run
        self.rjrun_k = np.zeros(self.n, np.int64)           # ... the rocket jump his try is for (into rjs)
        self.rjrun_t = np.zeros(self.n, np.float32)         # ... the seconds the try has left
        self.rjrun_edge = np.zeros(self.n, bool)            # ... he has been at its take-off
        self.rjrun_new = np.zeros(self.n, bool)             # ... the try began this frame
        self.rjrun_air = np.zeros(self.n, np.int64)         # ... frames in the air since he last touched the floor
        self.rjrun_from = np.zeros(self.n, bool)            # ... he has been at the take-off since he last touched the floor
        mapn_ = os.path.splitext(os.path.basename(bsp))[0]
        rj_open_ = {}
        for part_ in RJ_OPEN.split(";"):
            if ":" in part_:
                rj_open_[part_.split(":")[0].strip()] = part_.split(":")[1].strip()
        rj_runs_ = (RJ_RUN_P > 0 or RJ_ONLY_MAP) and (not RJ_ONLY_MAP or mapn_ in RJ_ONLY_MAP)   # (RJ_ONLY: the runs on its maps only)
        if (rj_runs_ or mapn_ in rj_open_) and self.route is not None:
            RJ_ = RJM
            R_ = self.route
            rjs_ = RJ_.load(mapn_, only=RJ_.cleared(mapn_) if RJ_CLEARED else None)
            lk_ = RJ_.links(rjs_, R_.nodes, R_.locate, ok=~R_.dead)
            items_ = [g_ for g_, lab_ in enumerate(self.route_goal) if INTENTS.index(lab_) not in self.intent_more
                      and 0 < INTENTS.index(lab_) < HOLD_INTENT]       # (a row of an item the map has once: its intention names it alone)
            keep_ = sorted({l_[3] for l_ in lk_})
            if RJ_ONLY_MAP:                                  # (RJ_ONLY) the runs' rocket jumps: its numbers only
                keep_ = [k_ for k_ in keep_ if rjs_[k_]["id"] in RJ_ONLY_MAP.get(mapn_, ())]
            if rj_runs_ and items_ and keep_:
                self.rjs = [rjs_[k_] for k_ in keep_]
                if RJ_LOOK_CLEAR:                            # (RJ_LOOK_CLEAR) the look-down of the execution that cleared it
                    fc_ = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rj_clear.json"))).get("first", {}).get(mapn_, {})
                    for r_ in self.rjs:
                        if str(r_["id"]) in fc_ and fc_[str(r_["id"])].get("pitch") is not None:
                            r_["look"] = float(fc_[str(r_["id"])]["pitch"])
                new_ = {k_: j_ for j_, k_ in enumerate(keep_)}
                lk2_ = [(a_, b_, t_, new_[k_]) for a_, b_, t_, k_ in lk_ if k_ in new_]   # (RJ_ONLY: its links only)
                for j_, r_ in enumerate(self.rjs):
                    g_ = min(items_, key=lambda q_: float(np.linalg.norm(np.asarray(R_.goals[q_]) - r_["b"])))   # (the item nearest the landing: its row)
                    X_ = RJ_.field(R_, g_, [l_ for l_ in lk2_ if l_[3] == j_], self.rjs, goal=r_["b"])
                    d_ = np.hypot(R_.nodes[:, 0] - r_["a"][0], R_.nodes[:, 1] - r_["a"][1])
                    st_ = np.nonzero((X_.ji[g_] == j_) & (X_.jd[g_] >= RJ_BACK[0]) & (X_.jd[g_] <= RJ_BACK[1]) & ~R_.dead)[0]   # (RJ_BACK units of way before it)
                    if not len(st_):
                        side_ = ((R_.nodes[:, :2] - r_["a"][:2]) * (r_["b"][:2] - r_["a"][:2])).sum(1) <= 0.0
                        st_ = (d_ > 30.0) & (d_ < 90.0) & (np.abs(R_.nodes[:, 2] - r_["a"][2]) < 30.0) & ~R_.dead & (X_.T[g_] < 1e8)
                        st_ = np.nonzero(st_ & side_)[0] if (st_ & side_).any() else np.nonzero(st_)[0]
                    if not len(st_):
                        st_ = np.nonzero((d_ < 44.0) & (np.abs(R_.nodes[:, 2] - r_["a"][2]) < 30.0) & ~R_.dead)[0]
                    self.rj_fields.append(X_)
                    self.rj_g.append(int(g_))
                    self.rj_start.append(st_)
                self.rj_a = np.array([r_["a"] for r_ in self.rjs], np.float32).reshape(-1, 3)
                self.rj_b = np.array([r_["b"] for r_ in self.rjs], np.float32).reshape(-1, 3)
            if mapn_ in rj_open_:                            # (RJ_OPEN) his ways in games with the open rocket jumps
                ids_ = None if rj_open_[mapn_] == "all" else {int(x_) for x_ in rj_open_[mapn_].split(",") if x_.strip()}
                lo_ = [l_ for l_ in lk_ if ids_ is None or rjs_[l_[3]]["id"] in ids_]
                if lo_:
                    js_, lj_ = [], []
                    if self.route_o is not None:             # (JUMP_OPEN too: its open jumps first, then the rocket jumps)
                        js_ = list(self.jumps)
                        lj_ = [l_ for l_ in JL.links(self.jumps, R_.nodes, R_.locate, ok=~R_.dead) if self.jumps[l_[3]]["id"] in self.jump_open]
                    self.rj_open_field = RJ_.linked_all(R_, lj_ + [(a_, b_, t_, k_ + len(js_)) for a_, b_, t_, k_ in lo_], js_ + rjs_,
                                                        RJ_OPEN_COST, n_plain=len(js_))
        self.rj_live = len(self.rjs) > 0
        self.rj_lab = np.zeros(self.n, np.int8)            # (RJ_TEACH) "jump and fire now" for his next frame
        self.rjc_lab = np.full((self.n, RJC_HEADS), -1, np.int8)   # (RJ_COPY) the runner's choice for his next frame (-1: none)
        self.rjc_hp0 = np.zeros(self.n, np.float32)         # ... health and armor at the try's start
        self.rjc_live = np.zeros(self.n, bool)              # ... a try counted and not yet ended
        self.rjc_up = np.full(self.n, 99, np.int64)         # ... frames since he left the floor at the take-off (99: he did not)
        self.rjc_ammo0 = np.zeros(self.n, np.float32)       # ... rockets at the try's start (fewer: the shot of this try is out)
        self.rjc_go = np.zeros(self.n, bool)                # ... the label of the last frame was "jump and fire"
        self.rc = None                                      # (ROUTE_COPY) the routes on this map (None: none)
        if ROUTE_COPY and getattr(self, "jumps", None):
            rn_ = ROUTE_COPY.split(":")[0].strip()
            rp_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_copy_{}.json".format(rn_))
            rd_ = json.load(open(rp_)) if os.path.exists(rp_) else None
            ks_ = [k_ for k_, j_ in enumerate(self.jumps) if rd_ is not None and int(j_["id"]) == int(rd_["jump_id"])]
            if rd_ is not None and rd_["map"] == mapn_.lower() and ks_ and rd_["routes"]:
                want_ = ROUTE_COPY.split(":")[1].strip() if ":" in ROUTE_COPY else None
                names_ = [nm_ for nm_ in ("circle", "hop2") if nm_ in rd_["routes"] and (want_ is None or nm_ == want_)]
                assert names_, "ROUTE_COPY={}: no such route in {}".format(ROUTE_COPY, rp_)
                rts_ = []
                for nm_ in names_:
                    R0_ = rd_["routes"][nm_]
                    fr_ = R0_["frames"]
                    j0_ = next((t_ for t_, x_ in enumerate(fr_) if x_["k"][2] == 1), len(fr_) - 1)   # (the first jump press)
                    k0_ = next((t_ for t_, x_ in enumerate(fr_) if x_["k"][0] != 1 or x_["k"][1] != 1), 0)   # (the stand before it: left out,
                    fr_ = fr_[k0_:j0_ + 1]                                                                       # the staging spot is it)
                    rts_.append(dict(name=nm_, hops=int(R0_["P"]["hops"]), side=int(R0_["P"]["side"]),
                                     p=np.array([x_["p"] for x_ in fr_], np.float32), v=np.array([x_["v"] for x_ in fr_], np.float32),
                                     yaw=np.array([x_["yaw"] for x_ in fr_], np.float32), k=np.array([x_["k"] for x_ in fr_], np.int64),
                                     start=np.array(R0_["start"], np.float32), syaw=float(R0_["start_yaw"])))
                A_ = np.array(rd_["A"], np.float32)
                B_ = np.array(rd_["B"], np.float32)
                U_ = (B_ - A_)[:2] / np.linalg.norm((B_ - A_)[:2])
                self.rc = dict(k=int(ks_[0]), routes=rts_, A=A_, B=B_, RA=np.array(rd_["RA"], np.float32), U=U_,
                               hop_tgt=A_[:2] + U_ * ROUTE_COPY_HOPX)
        self.rc_rng = np.random.default_rng(9173)           # (ROUTE_COPY) its own stream: which route a try takes
        self.rc_r = np.full(self.n, -1, np.int64)           # ... the route of his try (-1: none)
        self.rc_g = np.zeros(self.n, np.int64)              # ... the goal row of his try's ways
        self.rc_ph = np.zeros(self.n, np.int64)             # ... the phase (0 to the staging spot, 1 the maneuver, 2 the hop's
        self.rc_i = np.zeros(self.n, np.int64)              # flight, 3 the gap's, 4 over it); the reference frame
        self.rc_side = np.ones(self.n, np.int64)            # ... the air strafe's side
        self.rc_jmp = np.zeros(self.n, bool)                # ... the label of the last frame pressed the jump
        self.rc_down = np.zeros(self.n, bool)               # ... (hop2) he touched the floor after the hop
        self.rc_vz = np.zeros(self.n, np.float32)           # ... his upward speed as the last frame ended
        self.rc_live = np.zeros(self.n, bool)               # ... a counted try not yet ended
        self.rc_arr = np.zeros(self.n, bool)                # ... the try ends at the armor
        self.way =np.zeros(self.n, np.int64)               # WAYS: his way to his target (0 the shortest, 1 the second set, 2 the third),
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
        if VEL_FIX:                                     # (VEL_FIX) the delay as set
            self.vel_frames = max(0, int(round(VEL_DELAY_MS / 1000.0 / DT)))
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
        self.hb = np.zeros((n, 2), np.float32)          # (HAND_BAND) the view's velocity after the hand's bandwidth
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
        self.rbase = np.zeros((n, K, 3), np.float32)    # (MISSILE_POINT) its trBase: the muzzle, or a grenade's last bounce
        self.rrest = np.zeros((n, K), bool)             # (MISSILE_POINT) a grenade lying still (TR_STATIONARY)
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
                          jump_far=np.zeros(len(JUMP_FAR_COLS)),        # JUMP_FAR_P: tries and over by start (JUMP_FAR_COLS; counted seats)
                          jump_frames=0, start_gun=0,          # frames in jump runs; lives begun with a weapon in hand (START_GUN_P)
                          rj_tries=np.zeros(64), rj_over=np.zeros(64), rj_frames=0, rj_shots=0,   # RJ_RUN_P: per rocket jump of this map; frames, rockets fired
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
                          turn_add=np.zeros(3),           # LEGS_TURN_ADD: frames his legs carried him (counted seats), of them with a correction, its size (sum)
                          walk_jump=0,                    # frames of policy seats with walk and jump both asked (before WALK_NO_JUMP)
                          solo=np.zeros(2),               # SOLO_SELF: frames he drove himself in runs (counted seats, alive), his speed there (sum)
                          hop_quiet=0,                    # HOP_QUIET: take-offs whose pay it silenced
                          aw_bel=np.zeros(2), aw_tru=np.zeros(2),   # AWARE_LOG: frames, of them within 30 degrees (belief; truth)
                          aw_speed=np.zeros(6), aw_off=np.zeros(3),  # ... frames and speed sums, take-offs: in view, unseen near, far
                          aw_snd=np.zeros(22),            # ... turns after a sound by 0.1 s to 2 s, never, already facing
                          aw_emg=np.zeros(4),             # ... emergence point: frames, within 30 degrees (3D), no way, at the belief itself
                          keys_add=np.zeros(1 + len(KA_COLS)),   # LEGS_KEYS_ADD: frames his legs carried him (counted seats), of them his own output
                          #                                 in place of the legs' for each of KA_COLS
                          legs_c2=np.zeros(3),            # LEGS_LOOK: frames his legs were asked with a look point, of them his view within
                                                          # 30 degrees of it; LEGS_STAND: frames they were told to stand at the goal
                          high_pay=0.0,                                 # (HIGH_PAY) what the height of his hits added to his pay
                          rail=np.zeros(len(RAIL_COLS)),                # (RAIL_FAR_PAY) the rail by range, the counted seats in games: RAIL_COLS
                          rule_contest=np.zeros(2),                     # (RULE_CONTEST) frames the rule's lesson was silenced; frames it named an item
                          rule_hunt=np.zeros(2),                        # (RULE_HUNT) the same
                          rule_blind=np.zeros(2),                       # (RULE_BLIND) the same, for a fresh belief of the enemy's place

                          style=np.zeros((4, 10)),        # per style: frames, his weapon in hand, enemy in view, in his band, sum of
                                                          # distance in view, damage, damage with his weapon, big weapons held, frags, deaths
                          wrule_frames=0, wrule_agree=0,
                          frags_vs_bot=0, bot_frags=0, target_kills=0, bot_frames=0, aim_round_frames=0,
                          w_dist=np.zeros((3, NW)), dmg_h=0.0, dmg_from_script=0.0,
                          hand_g=np.zeros(NW),                            # ... in games alone (not in one-weapon rounds)
                          hand_w=np.zeros(NW), blind_w=np.zeros(NW),      # frames with each weapon in hand; frames firing it with no enemy seen for a second
                          speed_pay=0.0, speed_pay_run=0.0, speed_frames=0, move_teach_frames=0,
                          blind_rl=0, blind_rl_how=np.zeros(6 if BLIND_AHEAD else 5), prefire_frames=0, blind_bill=0,   # blind rockets: wasted, a jump, near, on a way, at one of the pros' places
                          vs_persona=np.zeros((3, len(PERSONAS))), fall_dmg=0.0, duck_frames=0, walk_frames=0)      # rows: frags against, deaths to, frames
        for wn in WEAPONS:
            self.stats[wn + "_shots"] = 0               # shots, ticks or pellets fired
            self.stats[wn + "_shots_vis"] = 0           # ... while the opponent was in view
            self.stats[wn + "_hits"] = 0
            self.stats[wn + "_frags"] = 0
        self.stats["hurt_dmg"], self.stats["void_deaths"] = 0.0, 0
        self.stats["preaim"] = np.zeros((4, NW))         # (PREAIM_PAY) fresh sightings by the weapon in hand: n, error summed, within 15 deg, q summed
        self.stats["preaim_x"] = np.zeros(len(PREAIM_X_COLS))
        self.pa_closed = None                            # (PREAIM_PAY) the books, made at the first frame (_preaim)
        if STAGGER_START:
            self.stats["stagger"] = np.zeros(2)          # (STAGGER_START) games begun at a drawn point of the clock, their start seconds
        if RESPAWN_QL:                                       # (RESPAWN_QL) deaths that waited, player-frames out of play
            self.stats["rsp_waits"], self.stats["rsp_wait_frames"] = 0, 0
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
        self.hc_len = np.zeros(n, np.int64)                 # (HOP_CHAIN) the hops of his chain so far (0: none)
        self.hc_best = np.zeros(n, np.float32)              # ... its best take-off speed over the ground
        self.hc_gnd = np.zeros(n, np.int64)                 # ... his frames on the ground since he landed
        self.hc_sp = np.zeros(n, np.float32)                # ... his speed over the ground a frame ago
        if HOP_CHAIN > 0:                                    # (a run that turns it on by live.json gets the counter at its first frame)
            self.stats["hop_chain"] = np.zeros(len(HC_COLS) + HC_BINS)
        self.key_jump = np.zeros(n, bool)                   # (JUMP_EVERY) this frame his jump was read between the hand's readings
        self.je_rng = None
        if JE_ON:
            self.stats["jump_every"] = np.zeros(len(JE_COLS))
            self.je_rng = np.random.default_rng(seed + 7771)  # (its own stream: the simulator's own draws are as without it)
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
        self._es_init()
        self.stats["run_item"] = np.zeros(1 + len(INTENTS))  # (RUN_TARGET_W) item runs begun, targets drawn by the table by intention
        if MOMENTS:                                          # (MID_START_P, SPAWN_START_P) the saved moments of whole games
            self._moment_init(seed)
        if RAIL_START_P > 0:                                 # (RAIL_START_P) the pros' long rail places of this map
            self._rail_start_init(bsp)
        if PRO_START_P > 0:                                  # (PRO_START_P) the moments of the pros' duels on this map
            self._pro_start_init(bsp)
        if OPENINGS:                                         # (OPENINGS) the pros' openings by spawn point
            self._open_init(bsp)
        for i in range(n):
            self._spawn(i, avoid=None if i % G == 0 else self.w.state()[i - 1, :3])
        self.state = self.w.state()
        self.visible = np.zeros(n, bool)
        if HEAD_EVENTS:                                      # (HEAD_EVENTS) the head's events and the win label
            self._head_init()

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
        if BRAIN_READ:                                       # (v0.4.2a) a new life: on the brain's answer with chance g
            self.brain_draw(i)
        self.lava_t[i] = 0.0
        self.rsp_wait[i] = 0                                 # (RESPAWN_QL) a new life is in play
        if STYLE_P > 0 and self.script[i] == 0:              # a new life: his playing style (here since 2026-10-08: in
            u_ = self.rng.random()                           # _spawn it missed arena1)
            self.style[i] = int(self.rng.integers(1, len(STYLES))) if u_ < STYLE_P else 0
            if STYLE_CUM is not None:                        # (STYLE_MIX) each style's own share of all lives, from the same
                self.style[i] = style_draw(u_)               # number (the stream has moved as it does without the mix)
            if STYLE_W[self.style[i]] >= 0 and int(STYLE_W[self.style[i]]) not in self.map_weapons:
                self.style[i] = 0                            # (no rail life on a map without a railgun)
        self.mv[i] = 0.0
        self.hb[i] = 0.0
        self.cmd[i] = 0.0
        self.turn_dir[i], self.rev_wait[i] = 0.0, 0.0
        self.hp[i], self.armor[i], self.cool[i] = SPAWN_HP, 0.0, 0.0
        self.fire_cd[i] = 0.0
        self.duck[i] = False
        self.key_last[i], self.key_hold[i], self.key_tok[i] = (1, 1, 0), 99, KEY_BURST
        self.key_req[i] = (1, 1, 0, 0)
        o_ = self.others[i]
        o1 = o_[(self.shot_src[o_] == i) | (self.G == 2)]
        self.shot_t[o1] = self.trail_t[o1] = 99.0           # what the others knew about this player's shots is void
        o1 = o_[(self.pain_src[o_] == i) | (self.G == 2)]
        self.pain_t[o1] = 99.0
        self.dmg_on[self.grp[i], self.slot[i]] = 0.0
        self.zoom[i], self.fire_last[i], self.mouse_hold[i] = False, False, 99
        self.flinch[i], self.focus[i] = 0.0, FOCUS_SECS
        self.life_t[i], self.first_wp[i] = 0.0, False
        self.big_got[i], self.self_debt[i] = False, 0.0
        if self.intent[i] > 0 and not self.intent_done[i]:
            self.stats["intent_trips"][3] += 1
        self.intent[i], self.intent_t[i], self.intent_new[i], self.intent_done[i] = 0, 0.0, True, False
        self.way[i], self.wt_from[i] = 0, -1                # (WAYS, WAY_MEASURE)
        self.pad[i], self.pad_lift[i], self.ear_t[i] = 0.0, 0, 99.0
        self.walk_last[i] = False
        self.e_got[self._mates(i), self._slot(i)] = 0.0     # what the others knew him to have is gone with him
        self.v02_pk[self._mates(i), self._slot(i)] = 0.0    # (N_V02: his big pickups as the others counted them)
        if self.G == 2:
            self.dmg_life[i ^ 1] = 0.0                  # what the opponent knows about this player's damage resets
        mode = int(self.mode[i // self.G])
        kind = int(self.kind[i // self.G])
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
        self.seen2[i], self.vis_run2[i], self.acq2[i] = 9.0, 0, False
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
            self._gun_place(i // self.G)
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
        self.hb[i] = 0.0
        self.hp[i], self.armor[i] = (1.0 if C["mortal"] else SPAWN_HP), 0.0
        if self.gun[i]:
            self._gun_arm(i)
        self.stats["course"][int(self.course[i]), 7] += 1

    def _gun_arm(self, i):
        w_ = int(self.gun_w[i // self.G])
        self.has[i, w_], self.ammo[i, w_], self.weapon[i] = True, AMMO_MAX[w_], w_

    def _gun_place(self, m):
        """put the target of a run-and-gun round beside the path, 500 to 900 units ahead of the runner"""
        a_, b_ = self.G * m, self.G * m + 1
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
                m_ = int(i) // self.G
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
        a_, b_ = self.G * m, self.G * m + 1
        P = list(range(self.G * m, self.G * m + self.G))
        for q in P:
            self._course_close(q, False)
        f, L, rng = self.lab_force, self.lab, self.rng
        pa = self.lab_p[0] / self.lab_aim_len
        pc = self.lab_p[1] / self.course_len
        pr = (self.lab_p[2] / self.arena_len) if len(self.lab_p) > 2 else 0.0
        u = rng.random() * (pa + pc + pr)
        kd = f["kind"] if f else (NORMAL if u < pr else AIM if (u < pr + pa or not self.courses) else COURSE)
        if self.G > 2 or "aim" not in L:                    # more than two players, or a map with only an arena: arena rounds
            kd = NORMAL
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
        for q in P[2:]:
            self.script[q], self.goal[q], self.course[q], self.items_room[q], self.gun[q] = 0, -1, -1, False, False
            self.load_sets[q], self.frags_r[q], self.snd_t[q] = None, 0, 99.0
        if kd == NORMAL:                                    # arena: the players fight each other
            self.arena[m] = int(f["arena"]) if (f and "arena" in f) else int(rng.choice(self.arena_rooms))
            if "env" not in L:
                self.arena[m] = 3                           # a map with only the yard
            self.item_up[m, :], self.item_t[m, :] = True, 0.0
            pool = [g for g in LOAD_GUNS if g in self.map_weapons]
            guns = tuple(int(x) for x in rng.choice(pool, 2, replace=False))           # two random weapons, the same for both
            if f and "weapon" in f:
                guns = (int(f["weapon"]),)
            if rng.random() < self.arena_full_p and not (f and "weapon" in f):
                guns = None                                 # the full weapon set
            for q in P:
                self.load_sets[q] = guns
            if self.arena_sets and not (f and "weapon" in f):   # fixed sets, drawn separately for each player
                for q in P:
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
            for q in P[1:]:
                self.state = self.w.state()
                self._arena_spawn(q)
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
            self.vis_run2[a_, 0], self.acq2[a_, 0], self.seen2[a_, 0], self.known2[a_, 0] = self.acquire_frames, True, 0.0, home
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
        m, L, rng = i // self.G, self.lab, self.rng
        oth = self.state[self.others[i], :3]
        if self.arena[m] == 1:                              # the aim box: anywhere on its floor
            A = L["aim"]
            z = float(A["subject"][2])
            cand = [np.array([rng.uniform(96, 1440), rng.uniform(96, 928), z], np.float32) for _ in range(12)]
        else:
            E_ = L["yard"] if self.arena[m] == 3 else L["env"]
            cand = [np.array([q[0], q[1], q[2] if len(q) > 2 else E_["z"]], np.float32) for q in E_["spots"]]
        if first:
            p = cand[int(rng.integers(len(cand)))]
        else:                                               # well away from everybody else
            d = np.array([min(float(np.linalg.norm(q - o_)) for o_ in oth) for q in cand])
            ok = np.nonzero(d > 500)[0]
            p = cand[int(rng.choice(ok))] if len(ok) else cand[int(d.argmax())]
        opp = oth[int(np.linalg.norm(oth - p, axis=1).argmin())]
        face = math.degrees(math.atan2(opp[1] - p[1], opp[0] - p[0])) if not first else float(rng.uniform(-180, 180))
        self.w.reset(i, (p[0], p[1], p[2] + 2.0), (0, 0, 0), face)
        self._fresh(i, face)
        if self.arena_stack:                                # this round's health and armor
            self.hp[i], self.armor[i] = self.arena_hp[m], self.arena_ar[m]

    def _lab_respawn(self, v):
        """a death on the lab map: back to the room's own spot, not to a map spawn point"""
        m = v // self.G
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
        ri = np.nonzero((self.run_k > 0) & (self.script == 0) & (self.hp > 0) & ~self.jrun & ~self.rjrun)[0]   # (a jump is not a walker's: no keys in a jump run; nor in a rocket jump run)
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
            ri = np.nonzero((self.run_k > 0) & (self.script == 0) & (self.hp > 0) & ~self.rjrun)[0]   # (RJ_RUN_P: silent in a rocket jump run)
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

    def _brain_init(self):
        """(BRAIN_READ) the brain's answer and the draws, made at their first use"""
        if getattr(self, "brain_life", None) is None or len(self.brain_life) != self.n:
            n = self.n
            self.brain_g = np.zeros(n, np.float32)
            self.brain_life = np.zeros(n, bool)
            self.brain_bel = np.zeros((n, 3), np.float32)
            self.brain_ok = np.zeros(n, bool)
            self.brain_band = np.zeros((n, 4), np.float32)
            self.brain_ztop = np.full(n, -1, np.int16)
            self.brain_rng = np.random.default_rng([int(getattr(self, "brain_seed", 0)), 0xB4A1])
            self.brain_tick = 0
            self.ahead_life = np.zeros(n, bool)          # (BLIND_AHEAD_P) the life's draw for the waiver on "will be"
            self.ahead_rng = np.random.default_rng([int(getattr(self, "brain_seed", 0)), 0xA4EAD])

    def set_brain_g(self, g):
        """(BRAIN_READ) each seat's chance that a life begun from now on reads the brain's answer: a number or [n]"""
        self._brain_init()
        self.brain_g[:] = np.clip(np.broadcast_to(np.asarray(g, np.float32), (self.n,)), 0.0, 1.0)

    def brain_draw(self, i, on=None):
        """(BRAIN_READ) a life of seat(s) i begins: drawn on the brain with chance brain_g (on: given, a plugin's own draw).
        One number of brain_rng a seat whatever g is (g = 0: never on)."""
        self._brain_init()
        ii = np.atleast_1d(np.asarray(i, np.int64))
        u = self.brain_rng.random(len(ii))
        v = (u < self.brain_g[ii]) if on is None else np.broadcast_to(np.asarray(on, bool), (len(ii),))
        self.brain_life[ii] = v
        if BLIND_AHEAD:                                      # (BLIND_AHEAD_P) the waiver on "will be" for this life: its own stream
            va_ = v & (self.ahead_rng.random(len(ii)) < BLIND_AHEAD_P)
            self.ahead_life[ii] = va_
        st = getattr(self, "stats", None)
        if st is not None and getattr(self, "script", None) is not None and hasattr(self, "count_even"):
            c = (self.script[ii] == 0) & self._counted(ii)
            st.setdefault("brain_lives", np.zeros(2))
            st["brain_lives"] += (float(c.sum()), float((c & v).sum()))
            if BLIND_AHEAD:
                st.setdefault("ahead_lives", np.zeros(2))
                st["ahead_lives"] += (float(c.sum()), float((c & va_).sum()))

    def brain_in(self, ans):
        """(BRAIN_READ) the brain's answer of this frame for every seat (btoken.answer_of: bel [n, 3] map coordinates, ok [n],
        band [n, 4] odds, ztop [n]); None leaves the last one"""
        if ans is None:
            return
        self._brain_init()
        self.brain_bel[:] = np.asarray(ans["bel"], np.float32)
        self.brain_ok[:] = np.asarray(ans["ok"], bool)
        self.brain_band[:] = np.asarray(ans["band"], np.float32)
        self.brain_ztop[:] = np.asarray(ans.get("ztop", np.full(self.n, -1)), np.int16)
        if "fut" in ans:                                     # (BLIND_AHEAD) the brain's places ahead (1, 2, 4 s; map) [n, 3, 3]
            self.brain_fut = np.asarray(ans["fut"], np.float32).reshape(self.n, -1, 3).copy()

    def _brain_count(self, key, rows):
        """(BRAIN_READ) a reader read these seats: his seats counted, those on the brain"""
        r = np.asarray(rows, np.int64)
        if not len(r):
            return
        c = (self.script[r] == 0) & self._counted(r)
        st = self.stats.setdefault("brain_read", np.zeros(2 * len(BRAIN_READERS)))
        j = BRAIN_READERS.index(key)
        st[2 * j] += float(c.sum())
        st[2 * j + 1] += float((c & self.brain_life[r]).sum())

    def _bel_src(self, key, rows=None):
        """the believed place of the unseen enemy [n, 3] and that he believes one [n] as the reader `key` reads them: the
        rule's (v02_bel, v02_bel_ok, kept by _v02 at the last observe(): the very objects, so a simulator without BRAIN_READ
        or with no life on the brain is unchanged) or, for a life on the brain (BRAIN_READ), the brain's answer. rows: the
        seats the reader reads (for the counters only)"""
        bel, ok = getattr(self, "v02_bel", None), getattr(self, "v02_bel_ok", None)
        if not BRAIN_READ or bel is None or ok is None or len(bel) != self.n:
            return bel, ok
        self._brain_init()
        self._brain_count(key, np.arange(self.n) if rows is None else rows)
        on = self.brain_life
        if not on.any():
            return bel, ok
        bt = getattr(self, "v02_bt_now", None)
        win = (np.asarray(bt, np.float32) < BRAIN_KNOWN) if (BRAIN_KNOWN > 0 and bt is not None and len(bt) == self.n) else np.ones(self.n, bool)
        return (np.where(on[:, None], self.brain_bel, np.asarray(bel, np.float32)).astype(np.float32),
                np.where(on, self.brain_ok & win, np.asarray(ok, bool)))

    def _stack_src(self, est, rows=None):
        """(RULE_HUNT) the enemy's expected stack [n] as the silence reads it: the filter's (est) or, for a life on the brain,
        the brain's stack band odds times BRAIN_BAND_MID (no answer: nothing to beat, never silent)"""
        if not BRAIN_READ:
            return est
        self._brain_init()
        self._brain_count("rule_hunt", np.arange(self.n) if rows is None else rows)
        on = self.brain_life
        if not on.any():
            return est
        bs = np.where(self.brain_ok, self.brain_band @ BRAIN_BAND_MID, np.inf)
        return np.where(on, bs, est).astype(np.float32)

    def _blind_src(self, rows):
        """(BLIND_BRAIN) for the seats rows: (on the brain [m], the brain's place [m, 3], an answer there [m]); None: all on the rule"""
        if not (BRAIN_READ and BLIND_BRAIN):
            return None
        self._brain_init()
        r = np.asarray(rows, np.int64)
        self._brain_count("blind", r)
        on = self.brain_life[r]
        if not on.any():
            return None
        return on, self.brain_bel[r], self.brain_ok[r]

    def _blind_fut(self, rows):
        """(BLIND_AHEAD) for the seats rows: (on the brain with an answer ahead [m], the brain's places ahead [m, 3, 3]); None:
        none (switch off, no answer ahead ever sent, no seat on the brain with one). Not counted again (_blind_src counts)"""
        if not (BRAIN_READ and BLIND_BRAIN and BLIND_AHEAD) or getattr(self, "brain_fut", None) is None:
            return None
        self._brain_init()
        r = np.asarray(rows, np.int64)
        on = self.brain_life[r] & self.brain_ok[r] & self.ahead_life[r]     # (BLIND_AHEAD_P: the life drawn for it)
        if not on.any():
            return None
        return on, self.brain_fut[r]

    def _brain_err_count(self):
        """(BRAIN_READ) every eighth frame: the place error of the rule's belief and of the brain's answer, his seats in a
        duel's game, the enemy alive and out of view, both believing; by the seconds since he saw him"""
        self._brain_init()
        self.brain_tick += 1
        bel, ok = getattr(self, "v02_bel", None), getattr(self, "v02_bel_ok", None)
        if self.brain_tick % 8 or bel is None or ok is None or len(bel) != self.n or len(self.hp) != 2 * len(self.kind):
            return
        n = self.n
        ar = np.arange(n)
        en = self._others_arr()[:, 0]
        vis = np.asarray(self.visible, bool)[:n] if getattr(self, "visible", None) is not None else np.zeros(n, bool)
        m = ((self.script == 0) & self._counted(ar) & (self.kind[ar // (self._others_arr().shape[1] + 1)] == NORMAL) & (self.run_k < 0) & (self.hp > 0) & (self.hp[en] > 0)
             & ~vis & np.asarray(ok, bool) & self.brain_ok)
        if not m.any():
            return
        tr = self.state[en, :3]
        er = np.linalg.norm(np.asarray(bel, np.float64) - tr, axis=1)
        eb = np.linalg.norm(self.brain_bel.astype(np.float64) - tr, axis=1)
        b = np.digitize(np.asarray(self.seen_t, np.float64), (2.0, 5.0, 10.0))
        st = self.stats.setdefault("brain_err", np.zeros(3 * len(BRAIN_ERR_BINS)))
        for k in range(len(BRAIN_ERR_BINS)):
            mk = m & (b == k)
            st[3 * k] += float(mk.sum())
            st[3 * k + 1] += float(er[mk].sum())
            st[3 * k + 2] += float(eb[mk].sum())

    def _legs_c2(self, ri, k, legs):
        """stage C part 2: what a movement network with the inputs for it is told about the players ri it is asked for:
        the look point, that one is given, that he is to stand at the goal. legs: its choices will move them (as the
        teacher of item runs it is told nothing). LEGS_LOOK: the place he believes the enemy at, as his own inputs have it
        (kept by _v02 at the last observe()). LEGS_STAND: his target is one of the map's holding places."""
        m = len(ri)
        pt, on, st = np.zeros((m, 3), np.float32), np.zeros(m, bool), np.zeros(m, bool)
        if legs and LEGS_LOOK and getattr(self, "v02_bel", None) is not None:
            bel_, bok_ = self._bel_src("legs_look", ri)      # (BRAIN_READ: the brain's place for a life on it)
            on = np.asarray(bok_, bool)[ri]
            pt = np.where(on[:, None], bel_[ri], 0.0).astype(np.float32)
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
        T.phi, idx_ = T.field.potential(T.goal, s[ri, :3])
        ok = (tg >= 0) & (T.phi < 1e8)                       # (no way in its own walking map: the walking teacher's keys stay)
        if not ok.any():
            return
        w0, b0, w1, b1, wp, bp, mean, var = self.teacher_w
        c2_ = getattr(T, "c2", 0)                            # (stage C part 2) a network with the inputs for it is told where to
        md_ = getattr(self, "_legs_mode", None) if into is not None else None     # (LEGS_IN, B-253: legs_prep() collects, _legs_step() uses)
        lg_in = getattr(self, "legs_lg", None) if md_ == "use" else None
        if c2_:                                              # look and that he is to stand at the goal; any other is asked as before
            T.look_pt, T.look_on, T.stand = self._legs_c2(ri, k, into is not None)
        if lg_in is not None and not LEGS_IN_CHECK:          # (LEGS_IN) the branch of his own network has worked them out
            if c2_:
                T.look_on = T.stand = None
            lg = np.asarray(lg_in, np.float32)[ri]
        else:
            T.pre = self._legs_pre(ri, T, idx_)
            x = np.clip((T.observe() - mean) / np.sqrt(var + 1e-8), -10, 10).astype(np.float32)
            if md_ == "collect":                             # (LEGS_IN) legs_prep(): the inputs, no sums, no draws
                if c2_:
                    T.look_on = T.stand = None
                self.legs_x[ri] = x
                self.legs_xok[ri] = ok
                return
            if c2_:                                          # (the new inputs' part apart: with them at zero, or at zero weight, the
                T.look_on = T.stand = None                   # sum is bit for bit the old network's; and its other askers tell it nothing)
                lg = np.tanh(np.tanh(np.ascontiguousarray(x[:, :-c2_]) @ self.t_w0[0].T + x[:, -c2_:] @ self.t_w0[1].T + b0) @ w1.T + b1) @ wp.T + bp
            else:
                lg = np.tanh(np.tanh(x @ w0.T + b0) @ w1.T + b1) @ wp.T + bp
            if lg_in is not None:                            # (LEGS_IN_CHECK) the given logits against its own; the given ones are used
                g_ = np.asarray(lg_in, np.float32)[ri]
                e_ = getattr(self, "legs_in_err", None)
                if e_ is None:
                    e_ = self.legs_in_err = np.zeros(3)
                o_ = ok & (np.abs(self.legs_x[ri] - x).max(1) == 0) if getattr(self, "legs_x", None) is not None and len(self.legs_x) == self.n else ok
                e_[0] = max(e_[0], float(np.abs(g_ - lg)[ok].max()))
                e_[1] += int(ok.sum())
                e_[2] += int((ok & ~o_).sum())               # (rows whose inputs at the step differ from legs_prep()'s: none if the order is kept)
                lg = g_
        out, j = [], 0
        for d_ in (3, 3, 2, 9):
            l_ = lg[:, j:j + d_]
            pr = np.exp(l_ - l_.max(1, keepdims=True))
            pr /= pr.sum(1, keepdims=True)
            out.append(l_.argmax(1) if TEACH_BEST else (pr.cumsum(1) > self.rng.random((len(ri), 1))).argmax(1))
            j += d_
        if md_ == "use":                                     # (LEGS_IN) the branch's own draw, before the hand rule and the turn bins
            if getattr(self, "legs_raw", None) is None or len(self.legs_raw) != self.n:
                self.legs_raw = np.full((self.n, 4), -1, np.int64)
            self.legs_raw[ri[ok]] = np.stack(out, 1)[ok]
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

    def _legs_pre(self, ri, T, idx):
        """what the movement network's observe() of the players ri would work out again (sim speed, 2026-10-19): the
        nearest nodes of its field (idx, from potential() of this very state) and the wall and floor rays, when observe()
        traced the same rays (the same position and view of every one of them, and the same ray layout). The rays are a
        function of the position and the view alone: the inputs are bit for bit those it would trace itself."""
        r_ = getattr(self, "_obs_rays", None)
        if (r_ is None or len(r_[0]) != self.n or N_WALL != len(T.wall_dirs) or N_FLOOR != len(T.floor_off)
                or not np.array_equal(r_[0][ri], self.state[ri, :3]) or not np.array_equal(r_[1][ri], self.yaw[ri])
                or not (np.array_equal(T.wall_dirs[:, :2], self.wall_dirs) and np.array_equal(T.floor_off, self.floor_off))):
            return (idx, None, None)
        return (idx, r_[2][ri], r_[3][ri])

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
        if NO_SWITCH:                                        # (NO_SWITCH) the switch is off for every seat
            a[:, LEGS_HEAD] = 0
        if SOLO_SELF:                                        # (SOLO_SELF) his runs this frame (an item run, a jump run: no enemy)
            self.solo_now = who & (self.run_k[:n] >= 0)
            c_ = self.solo_now & self._counted(np.arange(n)) & (self.hp > 0)
            self.stats["solo"] += (float(c_.sum()), float(np.hypot(self.state[c_, 3], self.state[c_, 4]).sum()))
        if LEGS_TURN_ADD:                                    # (LEGS_TURN_ADD) this frame's correction: none until his legs carry him
            self.ta_add = np.zeros(n, np.float32)
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
        if LEGS_IN:                                          # (B-253) the branch's draws of this frame (-1: his legs did not move him)
            self.legs_raw = np.full((n, 4), -1, np.int64)
        ri = np.nonzero(self.legs)[0]
        if not len(ri) or self.teacher is None or self.route is None:
            self.legs_lg = None
            return
        k, ri = self._legs_who(self.legs)
        if not len(ri):
            self.legs_lg = None
            return
        ch = np.full((n, 4), -1, np.int64)
        if LEGS_IN:                                          # (B-253) the branch's logits, if the caller gave them
            self._legs_mode = "use"
            try:
                self._move_teach(ri, k, ch)
            finally:
                self._legs_mode, self.legs_lg = None, None   # (used once: a stale set is never taken for a later frame's)
        else:
            self._move_teach(ri, k, ch)
        ok = ch[:, 0] >= 0
        if LEGS_LAB:
            self.legs_lab = ch.astype(np.int8)               # the four choices where the movement network has a way, -1 elsewhere
            self.legs_wh = ok & self.legs_held               # a withheld stretch: the label is there, his own outputs stay
            ok = ok & ~self.legs_held
        own_ = a[:, list(KA_COLS)].copy() if LEGS_KEYS_ADD and a.shape[1] >= KA_HEAD + len(KA_COLS) else None
        if SOLO_SELF:                                        # (SOLO_SELF) in his runs his legs' choices are not taken: he drives himself
            ok = ok & ~self.solo_now
        a[ok, :4] = ch[ok]
        a[ok, 7:9] = 0
        self.legs_on = ok
        if own_ is not None:                                 # (LEGS_KEYS_ADD) where he chose "mine", his own output in place of the legs'
            mine_ = ok[:, None] & (a[:, KA_HEAD:KA_HEAD + len(KA_COLS)] == 1)
            for j_, c_ in enumerate(KA_COLS):
                a[mine_[:, j_], c_] = own_[mine_[:, j_], j_]
            k_ = ok & self._counted(np.arange(n))
            self.stats["keys_add"] += np.concatenate([[k_.sum()], (mine_ & k_[:, None]).sum(0)]).astype(np.float64)
        if LEGS_TURN_ADD and a.shape[1] > TA_HEAD:           # his correction on top of the legs' turn (step() adds it to the command)
            self.ta_add = np.where(ok, TA_BINS[np.clip(a[:, TA_HEAD], 0, len(TA_BINS) - 1)], 0.0).astype(np.float32)
            c_ = ok & self._counted(np.arange(n))
            self.stats["turn_add"] += (int(c_.sum()), int((c_ & (self.ta_add != 0)).sum()), float(np.abs(self.ta_add[c_]).sum()))

    def _legs_who(self, on):
        """the seats his legs carry when the switch is on for the players on (bool [players]): those with a target (the
        item of his run, or of his intention) and not standing at his holding place. Returns (the targets, the seats)."""
        ri = np.nonzero(on)[0]
        k = np.where(self.run_k > 0, self.run_k, self.intent)       # his target: the item of his run, or of his intention
        ri = ri[(k[ri] > 0) & ~self.rjrun[ri]]                      # (RJ_RUN_P: in a rocket jump run his own keys move him)
        if self.hold_n:                                      # at his holding place there is no further way: he holds it on his own feet
            ri = ri[~self._hold_at(ri, k[ri])]
        if LEGS_STAND and getattr(self, "hold_tg", None) and getattr(self.teacher, "c2", 0):    # (stage C part 2) at his holding place
            ri = np.nonzero(on)[0]                           # his legs do not let go of him: a network that can is told to stand
            ri = ri[(k[ri] > 0) & ~self.rjrun[ri]]           # there, and stops him (stage B part 2 takes him off his legs at the place)
        return k, ri

    def legs_prep(self):
        """(LEGS_IN, B-253) the movement network's inputs [players, its inputs] float32 for every seat his legs could carry
        on the next step (a network's seat, alive, with a target and a way): what _legs_step() would give the movement
        network if his switch were on, worked out now from the same state (normalised and cut at +-10; zeros elsewhere).
        Also legs_xok (bool [players]): the rows with a way. Draws no random number and changes nothing the simulator
        does. Call it after observe() and before step(), with nothing between that moves a player or changes his
        target (a plugin that reads the intention in between calls it after that)."""
        T = self.teacher
        d_in = 0 if T is None else self.teacher_w[0].shape[1]
        self.legs_x = np.zeros((self.n, d_in), np.float32)
        self.legs_xok = np.zeros(self.n, bool)
        if T is None or self.route is None:
            return self.legs_x
        k, ri = self._legs_who((self.script == 0) & (self.hp > 0))
        if not len(ri):
            return self.legs_x
        c2s_ = self.stats["legs_c2"].copy() if "legs_c2" in self.stats else None
        self._legs_mode = "collect"
        try:
            self._move_teach(ri, k, np.full((self.n, 4), -1, np.int64))
        finally:
            self._legs_mode = None
            if c2s_ is not None:                             # (a look point counted once: on the frame it is used)
                self.stats["legs_c2"] = c2s_
        return self.legs_x

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

    def _clock_seats(self):
        """(a check: see clock_t in __init__) per seat the seconds since his round or his game began and whether his network
        was trained on whole games; None: the simulator's own clock"""
        if self.clock_t is None:
            return None
        ct = np.asarray(self.clock_t, np.float32)
        assert ct.shape == (self.n,), "clock_t: one number a seat"
        cg = np.zeros(self.n, bool) if self.clock_game is None else np.asarray(self.clock_game, bool)
        assert cg.shape == (self.n,), "clock_game: one flag a seat"
        return ct, cg

    def _aware_log(self):
        """(AWARE_LOG) the awareness counters of this frame (see AWARE_LOG); called after observe()"""
        n, s = self.n, self.state
        ar = np.arange(n)
        opp = self._others_arr()[:, 0]
        if getattr(self, "aw_pend", None) is None or len(self.aw_pend) != n:
            self.aw_pend, self.aw_t0 = np.zeros(n, bool), np.zeros(n)
            self.aw_pos, self.aw_last = np.zeros((n, 3)), np.full(n, -99.0)
            self.aw_clock = 0.0
        self.aw_clock += DT
        t = self.aw_clock
        alive = self.hp[:n] > 0
        game = (self.script[:n] == 0) & (self.run_k[:n] < 0) & self._counted(ar)
        inview = np.asarray(self.visible, bool)[:n] | np.asarray(self.acquired, bool)[:n]
        en_alive = alive[opp]
        yaw = np.asarray(self.yaw[:n], np.float64)

        def off_(to):
            d_ = np.asarray(to, np.float64)[:, :2] - s[:n, :2].astype(np.float64)
            a_ = (np.degrees(np.arctan2(d_[:, 1], d_[:, 0])) - yaw + 180.0) % 360.0 - 180.0
            return np.where(np.hypot(d_[:, 0], d_[:, 1]) >= 100.0, np.abs(a_), np.nan)
        sp = np.hypot(s[:n, 3], s[:n, 4])
        bel = getattr(self, "v02_bel", None)
        if bel is not None:
            bpos = np.asarray(bel, np.float64)[:n]
            fresh = np.asarray(self.v02_bel_ok, bool)[:n] & (np.asarray(getattr(self, "v02_bt_now", np.zeros(n)))[:n] <= 5.0)
        else:
            bpos, fresh = np.zeros((n, 3)), np.zeros(n, bool)
        base = game & alive & (sp >= 250.0) & ~inview & en_alive
        ob = off_(bpos)
        m_ = base & fresh & ~np.isnan(ob)
        self.stats["aw_bel"] += (float(m_.sum()), float((m_ & (ob <= 30.0)).sum()))
        ot = off_(s[opp, :3])
        m_ = base & ~np.isnan(ot)
        self.stats["aw_tru"] += (float(m_.sum()), float((m_ & (ot <= 30.0)).sum()))
        R = self.route
        W = getattr(self, "v02_ways", None)
        self.aw_tick = getattr(self, "aw_tick", 0) + 1
        if R is not None and W is not None and self.aw_tick % 8 == 0:
            if getattr(R, "_fwd", None) is None:
                R._fwd, R._from = [[] for _ in range(len(R.nodes))], getattr(R, "_from", {}) or {}
                for b_, lst in enumerate(R.radj):
                    for a_, c_ in lst:
                        R._fwd[a_].append((b_, c_))
            m_ = base & fresh
            ids = np.nonzero(m_)[0]
            if len(ids):
                eb = R.locate(bpos[ids].astype(np.float32))
                em = R.locate(s[ids, :3].astype(np.float32))
                for j_, i_ in enumerate(ids):
                    u, me = int(eb[j_]), int(em[j_])
                    if W[me, u] >= 255:
                        self.stats["aw_emg"][2] += 1.0
                        continue
                    path = [u]
                    for _ in range(96):
                        if u == me:
                            break
                        nxt, bc = -1, 1e18
                        for v_, c_ in R._fwd[u]:
                            wv = 0.0 if v_ == me else (W[me, v_] / 16.0 if W[me, v_] < 255 else 1e9)
                            if c_ + wv < bc:
                                nxt, bc = v_, c_ + wv
                        if nxt < 0 or nxt in path:
                            break
                        u = nxt
                        path.append(u)
                    eye = s[i_, :3].astype(np.float32) + np.array([0, 0, VIEW_H], np.float32)
                    pt, at_bel = None, True
                    for k_ in range(len(path) - 1, -1, -1):
                        q_ = R.nodes[path[k_]].astype(np.float32) + np.array([0, 0, VIEW_H], np.float32)
                        if self.w.trace(eye, q_, mask=self.sight)["fraction"] >= 0.999:
                            pt, at_bel = q_, k_ == 0
                        else:
                            break
                    if pt is None:                           # (not even his own point: the first step of the way)
                        pt = R.nodes[path[-1]].astype(np.float32) + np.array([0, 0, VIEW_H], np.float32)
                    d_ = pt.astype(np.float64) - eye
                    if np.hypot(d_[0], d_[1]) < 100.0:
                        continue
                    yr_, pr_ = np.radians(float(self.yaw[i_])), np.radians(float(self.pitch[i_]))
                    dv_ = np.array([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)])
                    cos_ = float(np.dot(dv_, d_) / max(1e-6, np.linalg.norm(d_)))
                    self.stats["aw_emg"][0] += 1.0
                    self.stats["aw_emg"][1] += float(cos_ >= np.cos(np.radians(30.0)))
                    self.stats["aw_emg"][3] += float(at_bel)
        ht_ = np.asarray(getattr(self, "v02_ht", np.full((n, 1), 99.0)))[:n]
        near = ~inview & ((ht_ < 2.0).any(1) | (fresh & (np.linalg.norm(bpos - s[:n, :3], axis=1) < 700.0)))
        sit = [inview, near, ~inview & ~near]
        ga = game & alive
        can_ = np.asarray(getattr(self, "aw_can", np.zeros(n, bool)), bool)[:n]
        for k_, c_ in enumerate(sit):
            self.stats["aw_speed"][2 * k_] += float((ga & c_).sum())
            self.stats["aw_speed"][2 * k_ + 1] += float(sp[ga & c_].sum())
            self.stats["aw_off"][k_] += float((ga & c_ & can_).sum())
        snd = np.asarray(self.snd_t[:n], np.float64)
        got = snd < 0.5 * DT
        pain = np.asarray(getattr(self, "pain_t", np.full(n, 99.0))[:n], np.float64) < 0.5 * DT
        heard = got.any(1) | pain
        hpos = np.where(got.any(1)[:, None], np.asarray(self.snd_pos[:n], np.float64)[ar, got.argmax(1)], s[opp, :3])
        drop = self.aw_pend & ~alive
        self.aw_pend &= ~drop
        if self.aw_pend.any():
            op = off_(self.aw_pos)
            dt_ = t - self.aw_t0
            fin = self.aw_pend & ~np.isnan(op) & (op <= 30.0)
            nev = self.aw_pend & ~fin & (dt_ > 2.0)
            np.add.at(self.stats["aw_snd"], np.clip((dt_[fin] / 0.1).astype(np.int64), 0, 19), 1.0)
            self.stats["aw_snd"][20] += float(nev.sum())
            self.aw_pend &= ~(fin | nev)
        new = heard & alive & game & ~inview & ~self.aw_pend & ((t - self.aw_last) >= 1.0)
        self.aw_last = np.where(heard, t, self.aw_last)
        if new.any():
            oh = off_(hpos)
            ok_ = new & ~np.isnan(oh)
            fac = ok_ & (oh <= 30.0)
            self.stats["aw_snd"][21] += float(fac.sum())
            st_ = ok_ & ~fac
            self.aw_pend |= st_
            self.aw_t0 = np.where(st_, t, self.aw_t0)
            self.aw_pos = np.where(st_[:, None], hpos, self.aw_pos)

    def _others_arr(self):
        """for every player, the other players of his group (one column each)"""
        return self.others

    def _hand_band(self, who):
        """(HAND_BAND) players who: their view's velocity (hb) one frame on toward the hand's (mv) through a first-order
        low-pass whose cutoff is HB_FC + HB_BETA x |hb| Hz (|hb| in degrees a frame), per axis. -> hb (all players).
        step() and the plugins' drive() call it after the flick cap, before the hand noise"""
        fc = HB_FC + HB_BETA * np.abs(self.hb)
        k = (1.0 - np.exp(-2.0 * np.pi * fc * DT)).astype(np.float32)
        new = self.hb + k * (self.mv - self.hb)
        self.hb = np.where(np.asarray(who, bool)[:, None], new, self.hb).astype(np.float32)
        return self.hb

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

    def hear(self, noisy, foot=None):
        """noisy: players who made a sound this frame. Everybody notes the nearest enemy he hears (see N_EAR). foot (LG_DEAF):
        those of noisy whose sound was a footstep alone"""
        s, n = self.state, self.n
        oth = self._others_arr()
        d = np.linalg.norm(s[oth, :3] - s[:, None, :3], axis=2)
        hum = ((self.weapon == RG) | (self.weapon == LG))[oth] & (d < HUM_RANGE)       # the weapon's hum, always there
        ok = ((noisy[oth] & (d < EAR_RANGE)) | hum) & (self.hp[oth] > 0) & (self.hp > 0)[:, None]
        if LG_DEAF:                                          # (LG_DEAF) his own lightning gun muffles footsteps and the enemy's LG hum
            lv_ = self._lgd_lvl(np.arange(n))[:, None]
            ft_ = (np.zeros(oth.shape, bool) if foot is None else np.asarray(foot, bool)[oth]) & noisy[oth]
            r_ev_ = np.where(lv_ == 2, min(EAR_RANGE, LGD_FIRE_EVT), EAR_RANGE)
            r_ft_ = np.where(lv_ == 2, min(EAR_RANGE, LGD_FIRE_STEP), np.where(lv_ == 1, min(EAR_RANGE, LGD_STEP), EAR_RANGE))
            hum = hum & ~((self.weapon[oth] == LG) & (lv_ >= 1))
            ok = (((noisy[oth] & ~ft_ & (d < r_ev_)) | (ft_ & (d < r_ft_))) | hum) & (self.hp[oth] > 0) & (self.hp > 0)[:, None]
            muf_ = ft_ & (lv_ >= 1)
        if HEAR_QL:                                          # (HEAR_QL) only what the game sends him
            g_ = self._hear_ok(np.broadcast_to(np.arange(n)[:, None], oth.shape), oth)
            ok, hum = ok & g_, hum & g_
        d = np.where(ok, d, 1e9)
        k = d.argmin(1)
        ar = np.arange(n)
        got = np.nonzero(d[ar, k] < 1e8)[0]
        if not len(got):
            return
        src = oth[got, k[got]]
        to = s[src, :3] - s[got, :3]
        dist = d[got, k[got]]
        if HEAR_FIX:                                         # (HEAR_FIX) an event's own errors, once a sound; a hum's direction
            z_ = self.rng.normal(0, 1, (len(got), 4))        # error drifts; the distance as loud as it sounds; no closing speed
            rho_ = math.exp(-DT / max(HF_HUM_TAU, 1e-3))
            self.hf_hum[got] = (rho_ * self.hf_hum[got] + math.sqrt(1.0 - rho_ * rho_) * HF_DIR * z_[:, 0]).astype(np.float32)
            only_hum_ = hum[got, k[got]] & ~noisy[oth][got, k[got]]
            if LG_DEAF:                                      # (LG_DEAF) a muffled footstep: more error of direction and distance
                mf_ = muf_[got, k[got]] & ~only_hum_
                sd_ = HF_DIR + np.where(mf_, LGD_DIR * (dist / LGD_STEP) ** 2, 0.0)
                ang = np.arctan2(to[:, 1], to[:, 0]) + np.radians(np.where(only_hum_, self.hf_hum[got], sd_ * z_[:, 1]))
                up = np.clip((to[:, 2] + HF_UP * z_[:, 2]) / 200.0, -1.5, 1.5)
                dist = np.clip(dist * (1.0 + (HF_LOUD + np.where(mf_, LGD_LOUD, 0.0)) * z_[:, 3]), 0.0, EAR_RANGE)
            else:
                ang = np.arctan2(to[:, 1], to[:, 0]) + np.radians(np.where(only_hum_, self.hf_hum[got], HF_DIR * z_[:, 1]))
                up = np.clip((to[:, 2] + HF_UP * z_[:, 2]) / 200.0, -1.5, 1.5)
                dist = np.clip(dist * (1.0 + HF_LOUD * z_[:, 3]), 0.0, EAR_RANGE)
            close = np.zeros(len(got))
        else:
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

    def _hf_steps(self, ground, ground_was, vel, duck, alive):
        """(HEAR_FIX) this frame's footsteps and jumps, for every player: a footstep every HF_STEP_FRAMES frames while on
        the ground faster than HF_STEP_SPEED, not crouched (the first at once); a jump: off the ground, going up. Keeps
        hf_cnt, sets hf_ev (a footstep or a jump: what tells the enemy's place); returns the footsteps. The plugins call it
        once a frame for all seats, as step() does."""
        ground, ground_was, duck, alive = (np.asarray(x_, bool) for x_ in (ground, ground_was, duck, alive))
        vel = np.asarray(vel, np.float32)
        run_ = ground & (np.hypot(vel[:, 0], vel[:, 1]) > HF_STEP_SPEED) & ~duck & alive
        cnt_ = np.where(run_, self.hf_cnt + 1, -1)
        foot_ = run_ & ((self.hf_cnt < 0) | (cnt_ >= HF_STEP_FRAMES))
        self.hf_cnt = np.where(foot_, 0, cnt_).astype(np.int64)
        self.hf_ev = foot_ | (ground_was & ~ground & (vel[:, 2] > 100.0) & alive)
        self.hf_foot = foot_
        return foot_

    def _hf_place(self, hh, src, muff=None):
        """(HEAR_FIX) where players hh place the enemies src they heard: HF_DIR degrees off across, HF_LOUD of the distance
        off along (one draw a sound), the height HF_UP units off. muff (LG_DEAF): the muffled footsteps among them, with
        LGD_DIR x (d / LGD_STEP)^2 degrees and LGD_LOUD more"""
        s = self.state
        z_ = self.rng.normal(0, 1, (len(hh), 3))
        tv_ = s[src, :3] - s[hh, :3]
        dh_ = np.hypot(tv_[:, 0], tv_[:, 1]) + 1e-6
        if muff is None:
            a_ = np.arctan2(tv_[:, 1], tv_[:, 0]) + np.radians(HF_DIR * z_[:, 0])
            r_ = dh_ * np.maximum(0.2, 1.0 + HF_LOUD * z_[:, 1])
        else:
            mf_ = np.asarray(muff, bool)
            a_ = np.arctan2(tv_[:, 1], tv_[:, 0]) + np.radians((HF_DIR + np.where(mf_, LGD_DIR * (dh_ / LGD_STEP) ** 2, 0.0)) * z_[:, 0])
            r_ = dh_ * np.maximum(0.2, 1.0 + (HF_LOUD + np.where(mf_, LGD_LOUD, 0.0)) * z_[:, 1])
        return np.stack([s[hh, 0] + np.cos(a_) * r_, s[hh, 1] + np.sin(a_) * r_, s[src, 2] + HF_UP * z_[:, 2]], 1).astype(np.float32)

    def _lgd_lvl(self, lis):
        """(LG_DEAF) listeners lis: 0 the LG not in his hand (or dead), 1 in hand, 2 firing it"""
        lis = np.asarray(lis)
        on_ = (self.weapon[lis] == LG) & (self.hp[lis] > 0)
        return np.where(on_ & self.lgd_fire[lis], 2, np.where(on_, 1, 0))

    def _evt_reach(self, lis):
        """the reach of an enemy's event sound (HEAR_EVT) for listeners lis; with LG_DEAF, LGD_FIRE_EVT at most while he
        fires the lightning gun. Off: HEAR_EVT itself"""
        if not LG_DEAF:
            return HEAR_EVT
        return np.where(self._lgd_lvl(lis) == 2, min(HEAR_EVT, LGD_FIRE_EVT), HEAR_EVT)

    def _lgd_hear_reach(self, lis, src):
        """(LG_DEAF) how far listeners lis place the enemies src from a sound this frame (HEAR): a footstep alone within
        LGD_STEP with his LG in hand, LGD_FIRE_STEP firing it; a jump within LGD_FIRE_EVT at most while firing"""
        lv_ = self._lgd_lvl(lis)
        ft_ = self.hf_foot[np.asarray(src)] if HEAR_FIX else np.ones(np.shape(lv_), bool)
        r_ft_ = np.where(lv_ == 2, min(HEAR, LGD_FIRE_STEP), np.where(lv_ == 1, min(HEAR, LGD_STEP), HEAR))
        r_ev_ = np.where(lv_ == 2, min(HEAR, LGD_FIRE_EVT), HEAR)
        return np.where(ft_, r_ft_, r_ev_)

    def _lgd_muff(self, lis, src):
        """(LG_DEAF) which of the sounds of enemies src that listeners lis placed were muffled footsteps; None with it off"""
        if not LG_DEAF:
            return None
        ft_ = self.hf_foot[np.asarray(src)] if HEAR_FIX else np.ones(len(np.atleast_1d(lis)), bool)
        return ft_ & (self._lgd_lvl(lis) >= 1)

    def _hear_ok(self, lis, src=None, pos=None):
        """(HEAR_QL) the game sends player lis the sounds of player src (his box) or of the point pos (an item's place): his
        eye's cluster sees one of theirs in the map's PVS (sim/pvs.py). Arrays of one shape (pos: one point or one a lis);
        True everywhere with HEAR_QL off"""
        lis = np.asarray(lis)
        if not HEAR_QL or self.pvs is None or lis.size == 0:
            return np.ones(lis.shape, bool)
        key_ = (id(self.state), self.state[:, :3].tobytes(), self.duck.tobytes())     # (the places too: a plugin writes the state in place)
        if getattr(self, "_pvs_key", None) != key_:           # every player's eye cluster and box clusters, once a frame
            self._pvs_key = key_
            self._pvs_eye = self.pvs.clusters(self._eye(self.state))
            self._pvs_box = self.pvs.box_clusters(self.state[:, :3])
        ce = self._pvs_eye[lis.reshape(-1)]
        if src is not None:
            ok = self.pvs.sees(ce[:, None], self._pvs_box[np.asarray(src).reshape(-1)]).any(1)
        else:
            pc = self.pvs.clusters(np.asarray(pos, np.float32).reshape(-1, 3))
            ok = self.pvs.sees(ce, np.broadcast_to(pc, ce.shape))
        return ok.reshape(lis.shape)

    def _hear1(self, j, i):
        """(HEAR_QL) one listener j, one player i: see _hear_ok"""
        return (not HEAR_QL) or bool(self._hear_ok(np.array([int(j)]), np.array([int(i)]))[0])

    def _wait_on(self, v):
        """(RESPAWN_QL) player v has just died: in a fight round (not an item run, a jump run, a drill, the lab) he is out
        of play for RESPAWN_QL_FRAMES before he respawns (step: the waits run down); False: he respawns now"""
        if not RESPAWN_QL or int(self.kind[self._match_of(v)]) != NORMAL or self.run_k[v] >= 0 or self.jrun[v] or self.rjrun[v]:
            return False
        self.rsp_wait[v] = RESPAWN_QL_FRAMES
        self.stats["rsp_waits"] += 1
        return True

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

    def _death_seen(self, j, v, killer):
        """(SENSE_MINOR) player j knows of v's death: he is v or the killer, has v in view, or is within earshot"""
        if j == v or j == killer:
            return True
        return self._sees(j, v) or (np.linalg.norm(self.state[j, :3] - self.state[v, :3]) < HEAR_EVT and self._hear1(j, v))

    def _sees(self, j, v):
        """player j has player v in view (noticed)"""
        a2_ = getattr(self, "acq2", None)
        return bool(self.acquired[j]) if a2_ is None else bool(a2_[j, (self._slot(v) - self._slot(j)) % (a2_.shape[1] + 1) - 1])

    def _drop_weapon(self, v, killer=-1):
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
        if SENSE_MINOR:                                      # (SENSE_MINOR) its time is known to those who saw or heard the death
            for q_ in self._seats(m):
                self.drop_kn[q_, j] = self._death_seen(int(q_), int(v), int(killer))
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
            near = np.nonzero((np.hypot(d[:, 0], d[:, 1]) < 36) & (np.abs(d[:, 2]) < PICK_Z) & (self.hp[q] > 0))[0]
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
            if BIG_PICK_SEQ:                                 # (v0.3.8) the big three a life by order
                b_ = (RL, LG, RG).index(int(w)) if int(w) in (RL, LG, RG) else -1
                if b_ >= 0:
                    p_ = self._big_seq(i, b_, had)
                    reward[i] += p_
                    self.r_long[i] += p_
                    if SMALL_ZERO and p_:                    # (SMALL_ZERO) the other loses as much
                        for o_ in self._mates(i):
                            reward[o_] -= p_
                            self.r_long[o_] -= p_
            elif BIG_PICK > 0:                               # (v0.3.1) the big three once a life, nothing else
                b_ = (RL, LG, RG).index(int(w)) if int(w) in (RL, LG, RG) else -1
                if b_ >= 0 and not self.big_got[i, b_] and not (BIG_ONCE and self.big_got[i].any()):
                    reward[i] += BIG_PICK
                    self.r_long[i] += BIG_PICK
                if b_ >= 0:
                    self.big_got[i, b_] = True
            elif not had:
                reward[i] += self.item_reward * 25.0 / 100.0             # as any weapon he did not have
                self.r_long[i] += self.item_reward * 25.0 / 100.0
            want_ = WEAPONS[w].upper()
            if want_ in INTENTS and self.intent[i] == INTENTS.index(want_) and not self.intent_done[i]:
                self.intent_done[i] = True                               # he has what he was going for
                if WEAPON_FREE:
                    self.intent_new[i] = True                            # (WEAPON_FREE) the choice ends: a new reading at once
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
        if SENSE_MINOR:                                      # (SENSE_MINOR) only if he saw or heard the death
            out[:, 7] *= self.drop_kn[ar, j]
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
        return np.where(self.acq2, 1.0, 0.5 * np.clip(1.0 - self.seen2 / KNOW_FADE, 0.0, 1.0)).mean(1)

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

    def _rail(self, s, st, do_fire, do_w, reward):
        """(RAIL_FAR_PAY) the long-range rail: the zero-sum pay of this frame's rail hits (with the switch on) into reward,
        and the counters (always): by range to the enemy (origin to origin), < RAIL_FAR_LO, up to RAIL_FAR_HI, beyond;
        shots and hits, frames with the rail in hand (the enemy alive; and of them in view), the pay got and lost.
        Counted: policy seats in games (not runs), as the awareness counters (_counted)."""
        n = self.n
        ar = np.arange(n)
        R = self.stats["rail"]
        opp = self._others_arr()[:, 0]
        cnt = (self.script[:n] == 0) & (self.run_k[:n] < 0) & self._counted(ar)
        d_en = np.linalg.norm(s[opp, :3] - s[:n, :3], axis=1)
        band = np.where(d_en < RAIL_FAR_LO, 0, np.where(d_en <= RAIL_FAR_HI, 1, 2))
        alive = self.hp[:n] > 0
        R[0] += int((cnt & alive).sum())
        sh_ = cnt & np.asarray(do_fire, bool)[:n] & (np.asarray(do_w)[:n] == RG)
        np.add.at(R, 1 + band[sh_], 1)
        hand_ = cnt & alive & (self.weapon[:n] == RG) & (self.hp[opp] > 0)
        np.add.at(R, 7 + band[hand_], 1)
        np.add.at(R, 10 + band[hand_ & np.asarray(self.visible, bool)[:n]], 1)
        rs_ = None
        if RAIL_START_P > 0 and MOMENTS and self.rail_m.any():     # (RAIL_START_P) the rail starts' own counters
            RS = self.stats["rail_start"]
            rs_ = np.repeat(self.rail_m, n // self.M)
            s0_ = sh_ & rs_
            np.add.at(RS, 5 + band[s0_], 1)
            f0_ = s0_ & ~self.rail_shot
            if f0_.any():
                t_ = (self.g_tick[ar[f0_] // (n // self.M)] - self.rail_t0[ar[f0_] // (n // self.M)]) * DT
                e_ = t_ < RAIL_EARLY
                RS[15] += float(e_.sum())
                RS[16] += float(t_[e_].sum())
                self.rail_shot[ar[f0_]] = True
        for i_, v_ in st.get("rail", ()):
            d_ = float(np.linalg.norm(s[i_, :3] - s[v_, :3]))
            if cnt[i_]:
                R[4 + (0 if d_ < RAIL_FAR_LO else 1 if d_ <= RAIL_FAR_HI else 2)] += 1
                if rs_ is not None and rs_[i_]:
                    b0_ = 0 if d_ < RAIL_FAR_LO else 1 if d_ <= RAIL_FAR_HI else 2
                    RS[8 + b0_] += 1
                    RS[11 + b0_] += int(self.hp[v_] <= 0)
            if RAIL_FAR_PAY > 0:
                b_ = RAIL_FAR_PAY * min(1.0, max(0.0, (d_ - RAIL_FAR_LO) / max(1e-6, RAIL_FAR_HI - RAIL_FAR_LO)))
                reward[i_] += b_
                reward[v_] -= b_
                if cnt[i_]:
                    R[13] += b_
                if cnt[v_]:
                    R[14] += b_
        if RAIL_STREAK_PAY > 0:                              # (RAIL_STREAK_PAY) rail hits in a row
            if getattr(self, "rail_streak", None) is None:
                self.rail_streak = np.zeros(n, np.int64)
            hit_ = {}
            for i_, v_ in st.get("rail", ()):
                hit_[int(i_)] = int(v_)
            shot_ = np.nonzero(np.asarray(do_fire, bool)[:n] & (np.asarray(do_w)[:n] == RG))[0]
            for i_ in shot_:
                i_ = int(i_)
                if i_ in hit_:
                    self.rail_streak[i_] += 1
                    if self.rail_streak[i_] >= 2:
                        b_ = RAIL_STREAK_PAY * min(int(self.rail_streak[i_]) - 1, RAIL_STREAK_CAP)
                        reward[i_] += b_
                        reward[hit_[i_]] -= b_
                        if cnt[i_]:
                            R[13] += b_
                else:
                    self.rail_streak[i_] = 0
            self.rail_streak[~alive] = 0

    def _preaim(self, s, reward):
        """(PREAIM_PAY) the fresh sightings of this frame (see PREAIM_PAY): with the switch on, the zero-sum pay into
        reward; the counters always (state read only, no random draw). Duels only (a group of two)"""
        g_ = self._others_arr().shape[1] + 1
        if g_ != 2 or self.lab is not None or self.fixed_kind is not None:
            return
        n, M = self.n, self.M
        pos = np.asarray(s[:n, :3], np.float64)
        if self.pa_closed is None:
            self.pa_closed = np.zeros(M)                     # seconds the line between a match's two players has been shut
            self.pa_since = np.zeros(n)                      # seconds since he was placed
            self.pa_pos = pos.copy()
            self.pa_life = np.asarray(self.life_t[:n], np.float64).copy()
        moved = np.linalg.norm(pos - self.pa_pos, axis=1) >= 100.0
        born = np.asarray(self.life_t[:n], np.float64) < self.pa_life
        self.pa_since = np.where(moved | born, 0.0, self.pa_since + DT)
        self.pa_pos = pos.copy()
        self.pa_life = np.asarray(self.life_t[:n], np.float64).copy()
        a_ = np.arange(0, n, g_)
        b_ = a_ + 1
        game = (self.kind[:M] == NORMAL) & (self.mode[:M] < 0) & (self.run_k[a_] < 0) & (self.run_k[b_] < 0)
        alive = (self.hp[:n] > 0) & (self.rsp_wait[:n] <= 0)
        both = game & alive[a_] & alive[b_]
        op = np.zeros(M, bool)
        c_ = np.nonzero(both)[0]
        if len(c_):
            vis_ = np.asarray(self.visible, bool)[:n]
            kn_ = vis_[a_[c_]] | vis_[b_[c_]]                # in view: the line is clear
            op[c_[kn_]] = True
            r_ = c_[~kn_]
            if len(r_):
                eye = self._eye(s)
                up_ = np.array([0, 0, 8.0], np.float32)
                ia_, ib_ = a_[r_], b_[r_]
                near_ = np.linalg.norm(s[ib_, :3] - eye[ia_], axis=1) < 4000
                r_, ia_, ib_ = r_[near_], ia_[near_], ib_[near_]
                if len(r_):
                    l1_ = self._los(eye[ia_], s[ib_, :3] + up_)
                    op[r_[l1_]] = True
                    r2_ = ~l1_
                    if r2_.any():
                        l2_ = self._los(eye[ib_[r2_]], s[ia_[r2_], :3] + up_)
                        op[r_[r2_][l2_]] = True
        sh_ = PREAIM_SHUT - 1e-6
        fresh = op & (self.pa_closed >= sh_) & (self.pa_since[a_] >= sh_) & (self.pa_since[b_] >= sh_)
        self.pa_closed = np.where(~game, 0.0, np.where(op, 0.0, self.pa_closed + DT))
        X_ = self.stats["preaim_x"]
        cnt = (self.script[:n] == 0) & self._counted(np.arange(n))
        X_[0] += float(cnt[a_[both]].sum() + cnt[b_[both]].sum())
        f_ = np.nonzero(fresh)[0]
        if WATCH_PAY > 0 or LG_QUIET_COST > 0:               # (WATCH_PAY, LG_QUIET_COST) the look-back and the late switches; the ring
            self._watch(s, reward, f_, a_, b_, cnt, op)
        else:
            self.wr_ = None                                  # (both off, by a live setting: the ring begins again when one is on)
        if not len(f_):
            return
        ii_ = np.concatenate([a_[f_], b_[f_]])
        jj_ = np.concatenate([b_[f_], a_[f_]])
        eye = self._eye(s)
        yr, pr = np.radians(self.yaw[ii_]), np.radians(self.pitch[ii_])
        fd_ = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        to_ = s[jj_, :3] + np.array([0, 0, 8.0], np.float32) - eye[ii_]
        cos_ = (to_ * fd_).sum(1) / (np.linalg.norm(to_, axis=1) * np.linalg.norm(fd_, axis=1) + 1e-9)
        err = np.degrees(np.arccos(np.clip(cos_, -1.0, 1.0)))
        q = np.clip(1.0 - err / 60.0, 0.0, 1.0)
        if PREAIM_PAY > 0:
            k_ = len(f_)
            d_ = PREAIM_PAY * (q[:k_] - q[k_:])
            reward[a_[f_]] += d_.astype(reward.dtype)
            reward[b_[f_]] -= d_.astype(reward.dtype)
            pay_ = np.concatenate([d_, -d_])
            X_[1] += float(pay_.sum())
            X_[2] += float(pay_[cnt[ii_]].sum())
            X_[3] += float(np.abs(pay_).sum())
        P_ = self.stats["preaim"]
        c2_ = cnt[ii_]
        w_ = self.weapon[ii_][c2_]
        np.add.at(P_[0], w_, 1.0)
        np.add.at(P_[1], w_, err[c2_])
        np.add.at(P_[2], w_, (err[c2_] <= 15.0).astype(np.float64))
        np.add.at(P_[3], w_, q[c2_])

    def _watch(self, s, reward, f_, a_, b_, cnt, op):
        """(WATCH_PAY, LG_QUIET_COST; from _preaim) the matches f_ with a fresh sighting this frame: each seat's look-back
        score (see WATCH_PAY) and the zero-sum pay with WATCH_PAY on; the weapon changes of the last 2 s (lg_late); then
        this frame into the ring (state read only, no random draw)"""
        n, L = self.n, WATCH_RING
        if self.wr_ is None:                                 # (made when first on: a frame not yet kept counts as not alive)
            self.wr_ = dict(h=0, yaw=np.zeros((L, n), np.float32), pit=np.zeros((L, n), np.float32),
                            eye=np.zeros((L, n, 3), np.float32), alive=np.zeros((L, n), bool), hid=np.zeros((L, n), bool),
                            w=np.full((L, n), -1, np.int64))
        R_ = self.wr_
        alive = (self.hp[:n] > 0) & (self.rsp_wait[:n] <= 0)
        if len(f_):
            ii_ = np.concatenate([a_[f_], b_[f_]])
            jj_ = np.concatenate([b_[f_], a_[f_]])
            k_ = np.arange(1, L + 1)                         # frames ago
            ix_ = (R_["h"] - k_) % L
            after_ = (k_[:, None] * DT) <= (self.pa_since[ii_][None, :] + 1e-6)     # after his last placement
            c2_ = cnt[ii_]
            if "watch" not in self.stats:
                self.stats["watch"], self.stats["watch_x"] = np.zeros((2, NW)), np.zeros(len(WATCH_X_COLS))
            # the look-back: the last WATCH_WIN frames
            kw_ = ix_[:WATCH_WIN]
            el_ = R_["alive"][kw_][:, ii_] & R_["hid"][kw_][:, ii_] & after_[:WATCH_WIN]
            yr_, pr_ = np.radians(R_["yaw"][kw_][:, ii_]), np.radians(R_["pit"][kw_][:, ii_])
            fd_ = np.stack([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)], 2)
            to_ = (s[jj_, :3] + np.array([0, 0, 8.0], np.float32))[None, :, :] - R_["eye"][kw_][:, ii_]
            cos_ = (to_ * fd_).sum(2) / (np.linalg.norm(to_, axis=2) * np.linalg.norm(fd_, axis=2) + 1e-9)
            ang_ = np.degrees(np.arccos(np.clip(cos_, -1.0, 1.0)))
            w_ = np.clip(1.0 - ang_ / WATCH_DEG, 0.0, 1.0)
            wt_ = (0.5 + 0.5 * (WATCH_WIN - k_[:WATCH_WIN]) / max(1, WATCH_WIN - 1))[:, None] * el_
            sc_ = np.where(wt_.sum(0) > 0, (wt_ * w_).sum(0) / np.maximum(wt_.sum(0), 1e-9), 0.0)
            X_ = self.stats["watch_x"]
            if WATCH_PAY > 0:
                m_ = len(f_)
                d_ = WATCH_PAY * (sc_[:m_] - sc_[m_:])
                reward[a_[f_]] += d_.astype(reward.dtype)
                reward[b_[f_]] -= d_.astype(reward.dtype)
                self._pt("watch", a_[f_], d_)
                self._pt("watch", b_[f_], -d_)
                pay_ = np.concatenate([d_, -d_])
                X_[1] += float(pay_.sum())
                X_[2] += float(pay_[c2_].sum())
                X_[3] += float(np.abs(pay_).sum())
            X_[0] += float(c2_.sum())
            W_ = self.stats["watch"]
            wh_ = self.weapon[ii_][c2_]
            np.add.at(W_[0], wh_, 1.0)
            np.add.at(W_[1], wh_, sc_[c2_])
            # the late switches: weapon changes in the last 2 s (the ring and this frame), his own frames alive after his placement
            if "lg_late" not in self.stats:
                self.stats["lg_late"], self.stats["lg_late_n"] = np.zeros((NW, NW)), np.zeros(1)
            wseq_ = np.concatenate([self.weapon[ii_][None, :], R_["w"][ix_][:, ii_]], 0)       # now, 1 ago, ... L ago
            aseq_ = np.concatenate([alive[ii_][None, :], R_["alive"][ix_][:, ii_] & after_], 0)
            ch_ = (wseq_[:-1] != wseq_[1:]) & aseq_[:-1] & aseq_[1:] & (wseq_[1:] >= 0) & c2_[None, :]
            t_, p_ = np.nonzero(ch_)
            np.add.at(self.stats["lg_late"], (wseq_[t_ + 1, p_], wseq_[t_, p_]), 1.0)
            self.stats["lg_late_n"][0] += float(c2_.sum())
        hid_ = np.repeat(~op, 2)[:n]                         # the line between the two shut (as _preaim's op; duels)
        h_ = R_["h"]
        R_["yaw"][h_], R_["pit"][h_], R_["eye"][h_] = self.yaw[:n], self.pitch[:n], self._eye(s)[:n]
        R_["alive"][h_], R_["hid"][h_], R_["w"][h_] = alive, hid_, self.weapon[:n]
        R_["h"] = (h_ + 1) % L

    def _lg_quiet(self, reward):
        """(LG_QUIET_COST) the cost a frame of the lightning gun in hand while, by his own senses, the enemy is away (see
        LG_QUIET_COST); the counters for the counted seats. State read only, no random draw"""
        n = self.n
        if self.lgq_t is None or len(self.lgq_t) != n:
            self.lgq_t = np.zeros(n, np.float32)             # (begun when first on: he has just seen him, nothing is costed for 3 s)
        acq_ = np.asarray(self.acquired, bool)[:n]
        self.lgq_t = np.where(acq_, 0.0, self.lgq_t + DT).astype(np.float32)
        heard_t = np.minimum(np.minimum(self.ear_t[:n], self.snd_t[:n].min(1)), self.pain_t[:n])
        if self.lab is not None or self.fixed_kind is not None:
            return
        g_ = self._others_arr().shape[1] + 1
        pk_ = np.repeat(self.kind, g_)[:n]
        pm_ = np.repeat(self.mode, g_)[:n]
        game = (pk_ == NORMAL) & (pm_ < 0) & (self.run_k[:n] < 0) & ~self.jrun[:n] & ~self.rjrun[:n]
        ok_ = game & (self.script[:n] == 0) & (self.hp[:n] > 0) & (self.rsp_wait[:n] <= 0)
        r_ = np.clip((self.lgq_t - LGQ_UNSEEN) / (LGQ_FULL - LGQ_UNSEEN), 0.0, 1.0) * (heard_t >= LGQ_HEARD) * ok_
        lg_ = self.weapon[:n] == LG
        cost_ = LG_QUIET_COST * r_ * lg_ * DT
        reward[:n] -= cost_.astype(reward.dtype)
        if "lg_quiet" not in self.stats:
            self.stats["lg_quiet"], self.stats["lg_quiet_w"] = np.zeros(len(LGQ_COLS)), np.zeros(NW)
        c_ = ok_ & self._counted(np.arange(n))
        q_ = c_ & (r_ > 0)
        self.stats["lg_quiet"] += (float(c_.sum()), float(q_.sum()), float((q_ & lg_).sum()), float(cost_[c_].sum()))
        np.add.at(self.stats["lg_quiet_w"], self.weapon[:n][q_], 1.0)

    def _mates(self, i):
        """the other players of player i's group"""
        return [int(x) for x in self.others[i]]

    def _slot(self, j):
        """a player's place in his group"""
        return j % self.G

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
        if HUNT:                                             # (B-256) the enemy: the route goal nearest to the place he believes him at
            w_ = np.nonzero(np.asarray(intent) == EN_INTENT)[0]
            if len(w_) and who is None and len(gi) == self.n:
                who = np.arange(self.n)
            bel_, bok_ = (self._bel_src("hunt", np.asarray(who)[w_]) if (len(w_) and who is not None)    # (kept by _v02 at the last
                          else (getattr(self, "v02_bel", None), getattr(self, "v02_bel_ok", None)))     # observe(): what his inputs show; BRAIN_READ)
            if len(w_) and who is not None and bel_ is None:
                gi[w_] = -1
            elif len(w_) and who is not None:
                p_ = np.asarray(who)[w_]
                nr_ = len(self.route_goal) + (self.hold_n if len(T_) >= len(self.route_goal) + self.hold_n else 0)    # (items' rows and, with TARGETS, the places')
                t_ = T_[:nr_, (self.route if R is None else R).locate(bel_[p_])]
                gi[w_] = np.where(np.asarray(bok_, bool)[p_] & (t_.min(0) < 1e8), t_.argmin(0), -1)
        elif FIGHT_TARGET:                                   # the enemy: the route goal nearest to where he believes him to be
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
        rjo_ = None
        if self.rj_open_field is not None:                   # (RJ_OPEN) the launcher in hand with a rocket, and the stack for it
            rjo_ = ((self.script == 0) & ~self.jrun & ~self.rjrun & (self.weapon == RL) & (self.ammo[:, RL] >= 1)
                    & (self.hp + self.armor >= RJ_OPEN_HP) & (self.hp > 0))
            if rjo_.any():
                out.append((rjo_, self.rj_open_field))
        if self.route_o is not None:
            m_ = (self.script == 0) & ~self.jrun & ~self.rjrun
            if rjo_ is not None:
                m_ = m_ & ~rjo_
            if m_.any():
                out.append((m_, self.route_o))
        if self.rj_live and self.rjrun.any():                # (RJ_RUN_P) a rocket jump run: the try's ways, to its landing
            for k_ in np.unique(self.rjrun_k[self.rjrun]):
                out.append((self.rjrun & (self.rjrun_k == k_), self.rj_fields[int(k_)]))
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
                near = np.linalg.norm(pos[q] - self.item_pos[items[g]], axis=1) < self._evt_reach(q)
                if HEAR_QL:                                  # (HEAR_QL) heard where the game sends it (at the item's place)
                    near &= self._hear_ok(q, pos=self.item_pos[items[g]])
                self.bel_t[q[near], g] = 0.0
                if SENSE_MINOR:                                  # (SENSE_MINOR) heard, not seen: his clock starts a little off
                    ip_ = self.item_pos[items[g]]
                    took_ = np.linalg.norm(pos[q] - ip_, axis=1) < 120.0         # (the one who took it)
                    kn_ = np.asarray(self.known, np.float32)[q]
                    saw_ = np.asarray(self.acquired, bool)[q] & (np.linalg.norm(kn_ - ip_, axis=1) < 150.0)
                    hq_ = q[near & ~took_ & ~saw_]
                    if len(hq_):
                        self.bel_t[hq_, g] = self.rng.normal(0, SM_ITEM_SD, len(hq_)).astype(np.float32)
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
            if np.linalg.norm(s[j, :3] - s[i, :3]) < self._evt_reach(j) and self._hear1(j, i):     # (HEAR_QL: where the game sends it)
                self.it_t[j, k] = 0.0
                if SENSE_MINOR and not self._sees(j, i):
                    self.it_t[j, k] = float(self.rng.normal(0, SM_ITEM_SD))   # (SENSE_MINOR) heard, not seen: a little off
                self.e_got[j, self._slot(i), k] = 1.0

    def note_death(self, v, killer):
        """player v died: his killer knows, and those in earshot"""
        s = self.state
        for j in self._mates(v):
            if j == killer or np.linalg.norm(s[j, :3] - s[v, :3]) < HEAR_EVT or HEAR_QL:     # (HEAR_QL: the obituary goes to all)
                self.e_life[j, self._slot(v)] = 0.0
                self.e_got[j, self._slot(v)] = 0.0
                self._v02_void(j, v)
                if EN_STACK:                                 # (B-257) he knows the stack of the new life: 125 and nothing
                    self._es_set(j, self._slot(v), spawn=True)
                    self.es_dmg[j, self._slot(v)] = 0.0

    def note_hit(self, v, dmg):
        """player v took dmg from an enemy: the flinch (used by the game-server plugin; step() does the same itself)"""
        add = min(FLINCH_MAX, FLINCH_PER_DMG * float(dmg))
        self.flinch[v] = min(FLINCH_MAX, float(self.flinch[v]) + add)
        if not AIM2_FLINCH:                                  # (AIM2_FLINCH: the sustained error only)
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
            gp_ = R.goals[g]
            for m_, X_ in alt:
                t, nx, via_ = np.where(m_, X_.T[g, node], t), np.where(m_, X_.next[g, node], nx), np.where(m_[:, None], X_.via[g, node], via_)
                gp_ = np.where(m_[:, None], X_.goals[g], gp_)    # (RJ_RUN_P: a try's goal row is the landing)
            if WAYS:                                         # (his way: the seconds and the next step of the set he chose; N_B3 reads the rest)
                self._way_obs = (g, node, valid & (t < 1e8) & (self.run_k < 0), t)
                t, nx, via_ = self._on_way(g, node, t, nx, via_)
            ok = valid & (t < 1e8)
            wp = np.where((nx >= 0)[:, None], R.nodes[np.maximum(nx, 0)], gp_)
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
        if HEAR_QL:                                          # (HEAR_QL) heard where the game sends it (at the item's place)
            near &= self._hear_ok(idx, pos=self.item_pos[k])
        self.resp_t[idx[near], cat] = 0.0
        if self._hd_live():                                  # (HEAD_EVENTS) mega, red, yellow, a weapon: heard back
            hc_ = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab == "YA" else 3 if kind == "wp" else -1
            if hc_ >= 0:
                self.hd_ev[idx[near], HEAD_COL["resp_mh"] + hc_] += 1.0

    def _rule_contested(self, lab):
        """(RULE_CONTEST) the players for whom the item the rule names (lab) is nearer, by RULE_CONTEST seconds of way or more,
        to the place they believe the enemy at (his own inputs' belief: v02_bel, the frame before) than to themselves"""
        out = np.zeros(self.n, bool)
        R = self.route
        bel, ok = self._bel_src("contest", np.nonzero(np.asarray(lab) > 0)[0])    # (BRAIN_READ: the brain's place for a life on it)
        if R is None or bel is None or ok is None or len(bel) != self.n:
            return out
        ok = np.asarray(ok, bool) & (lab > 0)
        if not ok.any():
            return out
        na, nb = R.locate(self.state[:, :3]), R.locate(np.asarray(bel, np.float32))
        for gi, lb in enumerate(self.route_goal):
            m = ok & (lab == INTENTS.index(lb)) if lb in INTENTS else None
            if m is not None and m.any():
                out |= m & (R.T[gi, nb] + RULE_CONTEST < R.T[gi, na])
        return out

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
        if OPENINGS:                                         # (the opening names by the same ways)
            self.rule_tn = Tn
        if RULE_HUNT > 0:                                    # (RULE_HUNT: is a mega or red armor up or due, by the same ways)
            big_ = np.zeros(n, bool)
            grp_ = np.arange(n) // (self._others_arr().shape[1] + 1)
            for gi, lab in enumerate(self.route_goal):
                if lab in ("MH", "RA"):
                    gu_, gb_ = self._goal_state(gi, grp_)
                    big_ |= (gu_ | (gb_ < Tn[gi] + 3.0)) & (Tn[gi] < 1e8)
            self.rule_big = big_
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
        if not EN_ON:                                        # (the enemy as a target: only with the switch, FIGHT_TARGET or HUNT)
            choice = np.where(choice == EN_INTENT, 0, choice)
        choice = np.where(choice >= HOLD_INTENT + self.hold_n, 0, choice)     # (a holding place: only with TARGETS, and one the map has)
        if WEAPON_FREE:                                      # (v0.5.0) a weapon he holds with a pickup's worth of ammunition: "nothing"
            for w_, lab_ in ((RL, "RL"), (RG, "RG"), (LG, "LG")):
                full_ = self.has[:n, w_] & (self.ammo[:n, w_] >= WEAPON_PICK_AMMO[w_])
                choice = np.where((choice == INTENTS.index(lab_)) & full_, 0, choice)
        may = (self.intent == 0) | self.intent_done | (self.intent_t >= INTENT_HOLD) | self.intent_gone     # a choice holds (INTENT_HOLD)
        if TARGETS_FREE == 1:                                # (a holding place can be left at any reading, as "nothing")
            may = may | (self.intent >= HOLD_INTENT)
        elif TARGETS_FREE >= 2:                              # (... for an item only)
            may = may | ((self.intent >= HOLD_INTENT) & (choice >= 1) & (choice < HOLD_INTENT))
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
        lis = self.others[src].reshape(-1)                  # every other member of the shooter's group
        src = np.repeat(src, self.G - 1)
        k_ = np.repeat(self.kind, self.G)[lis]
        alone = ((k_ == MOVE) | (k_ == SOLO) | ((k_ == COURSE) & ~self.gun[lis]))
        d = np.linalg.norm(s[src, :3] - s[lis, :3], axis=1)
        d = np.where(self._hear_ok(lis, src), d, 1e9) if HEAR_QL else d     # (HEAR_QL: heard where the game sends it)
        acq_p = self.acquired[lis] if self.G == 2 else self.acq2[lis, (self.slot[src] - self.slot[lis]) % self.G - 1]
        seen = acq_p & ~alone
        ok = (seen | (d < self._evt_reach(lis))) & ~alone & (self.hp[lis] > 0)
        self.shot_src[lis[ok]] = src[ok]
        self.shot_t[lis[ok]] = 0.0
        self.shot_w[lis[ok]] = self.weapon[src[ok]]
        self.shot_seen[lis[ok]] = seen[ok]
        # the line of a hitscan shot (not rockets, grenades, plasma: those are projectiles he sees anyway)
        hit = np.isin(self.weapon[src], (RG, LG) if SENSE_MINOR else (RG, LG, MG, HMG, SG)) & ~alone & (self.hp[lis] > 0)
        if hit.any():
            sh, li, acq_h = src[hit], lis[hit], acq_p[hit]
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
            vis = (acq_h | ((to * fl).sum(1) / dn > self.fov()[2][li])) & (dn < 2000.0)
            for k in np.nonzero(vis)[0]:
                if acq_h[k] or self.w.trace(eye[li[k]], near[k].astype(np.float32), mask=self.sight)["fraction"] >= 0.999:
                    self.trail_t[li[k]] = 0.0
                    self.trail_p[li[k]] = near[k]

    def _fight(self, pos, eye, rot, visible):
        """the inputs added on 2026-10-05 (see N_FIGHT)"""
        n = self.n
        opp = self.foe
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
        if SENSE_MINOR:                                      # (SENSE_MINOR) as seen a reaction time ago
            body = np.stack([self._sm_e["duck"].astype(np.float32) * v_, self._sm_e["air"].astype(np.float32) * v_], 1)
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
        lis = self.others[src].reshape(-1)
        src = np.repeat(src, self.G - 1)
        if kind is not None and np.ndim(kind):
            kind = np.repeat(np.asarray(kind), self.G - 1)
        k_ = np.repeat(self.kind, self.G)[src]
        ok = (np.linalg.norm(s[src, :3] - s[lis, :3], axis=1) < HEAR_EVT) & (k_ != MOVE) & (k_ != SOLO)
        if HEAR_QL:                                          # (HEAR_QL) where the game sends it
            ok &= self._hear_ok(lis, src)
        if RESPAWN_QL:                                       # (RESPAWN_QL) a body waiting to respawn makes no sound
            ok &= self.rsp_wait[src] <= 0
        if LG_DEAF:                                          # (LG_DEAF) firing the lightning gun: LGD_FIRE_EVT at most
            ok &= np.linalg.norm(s[src, :3] - s[lis, :3], axis=1) < self._evt_reach(lis)
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
        if self._hd_live():                                  # (HEAD_EVENTS) he heard an enemy's event sound
            np.add.at(self.hd_ev[:, HEAD_COL["en_heard"]], lis, 1.0)

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
        if self.sight is None or not len(a):                 # (the one call below needs a mask)
            for k in range(len(a)):
                out[k] = np.linalg.norm(b[k] - a[k]) < 1 or self.w.trace(a[k], b[k], mask=self.sight)["fraction"] >= 0.999
            return out
        a32, b32 = np.asarray(a, np.float32).reshape(-1, 3), np.asarray(b, np.float32).reshape(-1, 3)
        fr = self.w.lines(a32, b32, mask=self.sight)         # (the same point traces, one call: qsim_lines_m)
        dv = np.linalg.norm(np.asarray(b) - np.asarray(a), axis=1)
        close = dv < 1
        for k in np.nonzero(np.abs(dv - 1.0) < 1e-3)[0]:     # (at the edge: the pair's own norm, as before)
            close[k] = np.linalg.norm(b[k] - a[k]) < 1
        return close | (fr >= 0.999)

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
        self._obs_rays = (pos.copy(), self.yaw.copy(), self.walls, floors)    # (the same rays his legs' inputs trace: _legs_pre)
        if self.fov_sight and not GROUND_SENSE:              # a floor spot is seen if the line from the eyes to it is in view
            fa = (np.linspace(0, 2 * np.pi, N_FLOOR, endpoint=False) + np.pi) % (2 * np.pi) - np.pi
            down = np.arctan2(VIEW_H + floors * 256.0, 96.0)             # how far below the horizon that spot lies
            see = (np.abs(fa)[None, :] <= fh[:, None]) & (np.abs(pit[:, None] - down) <= fv[:, None])
            floors = np.where(see, floors, UNSEEN).astype(np.float32)
        eye = self._eye(s)
        fdir = np.stack([np.cos(pit) * c, np.cos(pit) * si, -np.sin(pit)], 1)
        opp = self.foe
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
        if DRIFT_IN:                                         # (DRIFT_IN) which old sighting is read: a change of it is no motion
            self._drift_pick = np.full(n, max(0, len(self.opp_hist) - 1 - self.react_frames) - len(self.opp_hist), np.int64)
        rf_ = self.react_frames if self.react_seat is None else self.react_seat     # (SEAT_DELAYS) one number, or one a seat
        if self.react_seat is not None:                      # ... each seat by its own delay (react_frames is the largest)
            pk_ = np.maximum(0, len(self.opp_hist) - 1 - rf_)
            known, visible, seen_t = (np.stack([h_[j_] for h_ in self.opp_hist])[pk_, np.arange(n)] for j_ in (0, 1, 3))
            if DRIFT_IN:
                self._drift_pick = np.asarray(pk_, np.int64) - len(self.opp_hist)
        if self.focus_on:                                    # the delay per player: sharp while focus lasts, then dull
            self.focus = np.where(self.acquired, self.focus - DT, self.focus + FOCUS_REFILL * DT)
            self.focus = np.clip(self.focus, -0.5, FOCUS_SECS).astype(np.float32)
            fg_ = self._sa("AIM2_FOCUS_GAIN")
            fg_ = (np.asarray(fg_).astype(np.int64) if np.ndim(fg_) else int(fg_)) if AIM2_FOCUS else FOCUS_GAIN
            dly = rf_ + np.where(self.focus > 0, -fg_, FOCUS_LOSS)
            dly = np.where(self.script == 0, np.maximum(dly, 1), rf_)
            L_ = len(self.opp_hist)
            pick = np.maximum(0, L_ - 1 - dly)
            if DRIFT_IN:
                self._drift_pick = np.asarray(pick - L_, np.int64)
            ar_ = np.arange(n)
            known = np.stack([h_[0] for h_ in self.opp_hist])[pick, ar_]
            visible = np.stack([h_[1] for h_ in self.opp_hist])[pick, ar_]
            seen_t = np.stack([h_[3] for h_ in self.opp_hist])[pick, ar_]
        opp_vel = self.opp_hist[max(0, len(self.opp_hist) - 1 - self.vel_frames)][2]
        if SENSE_MINOR:                                      # (SENSE_MINOR) his facing, crouch, air and weapon as seen with his place
            self._sm_note(opp, rf_, pick if self.focus_on else None)
        if VEL_FIX:                                          # (VEL_FIX) read as a person reads it
            opp_vel = self._vel_percept(opp_vel)
        self.ear_t += DT
        self.resp_t += DT
        self.it_t += DT                                      # the memory aids (N_MEM) keep their own time here, so the
        self.e_life += DT                                    # game-server plugin, which does not call step(), has them too
        self.life_t += DT
        v_ = np.nonzero(visible)[0]
        self.e_got[v_, self._slot(opp[v_]), 2 + (self._sm_e["weapon"][v_] if SENSE_MINOR else self.weapon[opp[v_]])] = 1.0     # the weapon seen in the enemy's hands
        known_w = None                                       # (AIM2_SPLIT) the world picture's place, apart from the aim's
        if AIM2:                                             # (AIM2) his view and the target's bearing kept a frame, for the slip
            self._aim2_note(eye, n)
        psg_ = self._sa("PERCEPT_SIGMA")                     # (SEAT_AIM: one a seat in a check; else the simulator's own)
        if np.any(np.asarray(psg_) > 0):                     # the enemy is seen a little off from where he is
            rho = math.exp(-DT / PERCEPT_TAU)
            ft_ = self._sa("FLINCH_TAU")
            self.flinch = (self.flinch * (math.exp(-DT / ft_) if not np.ndim(ft_) else np.exp(-DT / ft_))).astype(np.float32)
            sig_ = (psg_ + self.flinch)[:, None]
            if ZOOM_PERCEPT:                                 # (ZOOM_PERCEPT) zoomed: the target is judged on a larger picture
                sig_ = (psg_ * np.where(np.asarray(self.zoom, bool)[:n], ZOOM, 1.0) + self.flinch)[:, None]
            a2w_ = self._sa("AIM2_W")
            if AIM2 or AIM2_FOCUS:                           # (AIM2) the base error by focus; zoom on every term
                zf_ = np.where(np.asarray(self.zoom, bool)[:n], ZOOM, 1.0) if ZOOM_PERCEPT else np.ones(n)
                b_ = psg_ * (np.where(self.focus[:n] > 0, self._sa("AIM2_FOCUS_SIG"), 1.0) if (AIM2_FOCUS and self.focus_on) else 1.0)
                a2_ = (self._aim2_err(n, pick if self.focus_on else None, rf_) * a2w_) if AIM2 else 0.0
                zall_ = (1.0 - a2w_ * (1.0 - zf_)) if AIM2 else 1.0     # (W = 0: the flinch unscaled as before)
                sig_ = (b_ * zf_ + (self.flinch + a2_) * zall_)[:, None]
            psp_ = self._sa("PERCEPT_SPEED")
            if np.any(np.asarray(psp_) > 0):                 # a target that crosses the view fast is judged worse
                tb_ = known - eye
                br_ = np.stack([np.degrees(np.arctan2(tb_[:, 1], tb_[:, 0])),
                                np.degrees(np.arctan2(tb_[:, 2], np.hypot(tb_[:, 0], tb_[:, 1]) + 1e-6))], 1).astype(np.float32)
                dy_ = (br_[:, 0] - self.bearing[:, 0] + 180.0) % 360.0 - 180.0
                w_ = np.hypot(dy_, br_[:, 1] - self.bearing[:, 1]) / DT * (visible & self.bearing_ok)
                cap_ = PERCEPT_SPEED_MAX
                if PERCEPT_SPEED_MAX_RG > 0 or PERCEPT_SPEED_MAX_LG > 0:     # (the cap by the weapon in hand)
                    wh_ = np.asarray(self.weapon)[:len(w_)]
                    cap_ = np.where(wh_ == RG, PERCEPT_SPEED_MAX_RG or PERCEPT_SPEED_MAX,
                                    np.where(wh_ == LG, PERCEPT_SPEED_MAX_LG or PERCEPT_SPEED_MAX, PERCEPT_SPEED_MAX)).astype(np.float32)
                sig_ = sig_ + (np.minimum(psp_ * w_, cap_) * ((1.0 - a2w_) if AIM2 else 1.0))[:, None]
                self.bearing, self.bearing_ok = br_, visible.copy()
            self.percept = (rho * self.percept + math.sqrt(1.0 - rho * rho) * sig_ *
                            self.rng.normal(0, 1, (n, 2))).astype(np.float32)
            t_ = known - eye
            hd_ = np.hypot(t_[:, 0], t_[:, 1]) + 1e-6
            d_ = np.linalg.norm(t_, axis=1)
            off = np.tan(np.radians(self.percept)) * d_[:, None] * (visible & (self.script == 0))[:, None]
            dk_ = np.stack([-t_[:, 1] / hd_ * off[:, 0], t_[:, 0] / hd_ * off[:, 0], off[:, 1]], 1).astype(np.float32)
            if AIM2_SPLIT:                                   # (AIM2_SPLIT) the world picture keeps (1 - AIM2_SPLIT_W) of it
                sw_ = self._sa("AIM2_SPLIT_W")
                known_w = (known + ((1.0 - sw_) if not np.ndim(sw_) else (1.0 - sw_)[:, None]) * dk_).astype(np.float32)
            known = known + dk_
        if AIM2_SPLIT and known_w is None:
            known_w = known.copy()
        if RANGE_FIX:                                        # (RANGE_FIX) his distance judged by eye
            self._rf_known0 = known.copy()                   # (the place before it: DRIFT_IN's jump test, see _drift)
            known = self._range_percept(known, eye, visible)
            if AIM2_SPLIT:                                   # (the same share of the distance for the world picture)
                known_w = (known_w + (known_w - eye) * self._rf_g[:, None]).astype(np.float32)
        known_a = known                                      # the aim's place (the sight error on it)
        if AIM2_SPLIT:
            known = known_w
        rel = rot(known - pos) / 1000.0
        exact = visible.astype(np.float32)
        ovel = rot(opp_vel) / 400.0 * exact[:, None]
        to = known_a + np.array([0, 0, 4.0], np.float32) - eye
        hd = np.hypot(to[:, 0], to[:, 1]) + 1e-6
        ang_yaw = np.arctan2(to[:, 1], to[:, 0]) - yaw
        ang_pit = -np.arctan2(to[:, 2], hd) - pit
        if AIM2_SPLIT:                                       # (AIM2_SPLIT) the angles between the world's place and the aim's
            tw_ = known + np.array([0, 0, 4.0], np.float32) - eye
            hw_ = np.hypot(tw_[:, 0], tw_[:, 1]) + 1e-6
            self._a2_dang = np.stack([np.degrees((np.arctan2(to[:, 1], to[:, 0]) - np.arctan2(tw_[:, 1], tw_[:, 0]) + np.pi)
                                                 % (2 * np.pi) - np.pi),
                                      np.degrees(-np.arctan2(to[:, 2], hd) + np.arctan2(tw_[:, 2], hw_))], 1).astype(np.float32)
        # reticle distance to the enemy, in degrees: coarse (+-15) and fine (+-2) readings, both axes
        ey = np.degrees((ang_yaw + np.pi) % (2 * np.pi) - np.pi)
        ep_ = np.degrees(ang_pit)
        dist3 = np.linalg.norm(to, axis=1) + 1e-6
        on_target = self._seg_box(eye, eye + fdir.astype(np.float32) * 4000.0, known_a,
                                  np.where(self.duck[opp], TOP_DUCK, TOP)) & visible
        if AIM2_SPLIT:                                       # (AIM2_SPLIT) how big he looks: by the world's distance
            dist3 = np.linalg.norm(known + np.array([0, 0, 4.0], np.float32) - eye, axis=1) + 1e-6
        size = np.degrees(np.arctan2(20.0, dist3)) / 10.0      # how big the target looks
        opp_feat = np.concatenate([[exact], [np.exp(-seen_t)], rel.T, ovel.T, [np.sin(ang_yaw)], [np.cos(ang_yaw)],
                                   [np.cos(ang_pit)], [np.sin(ang_pit)],
                                   [np.clip(ey / 15.0, -1, 1)], [np.clip(ey / 2.0, -1, 1)],
                                   [np.clip(ep_ / 15.0, -1, 1)], [np.clip(ep_ / 2.0, -1, 1)],
                                   [on_target.astype(np.float32)], [np.clip(size, 0, 1)]], 0).T * (seen_t < 5)[:, None]
        # incoming projectiles (the opponent's), nearest N_PROJ: position, velocity, kind (rocket / grenade / plasma)
        rk = np.zeros((n, 9 * N_PROJ), np.float32)
        oth = self.others                                    # everybody else's projectiles
        orp, orv = self.rp[oth].reshape(n, -1, 3), self.rv[oth].reshape(n, -1, 3)
        ora, orw = self.ra[oth].reshape(n, -1), self.rw[oth].reshape(n, -1)
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
        up = np.repeat(self.item_up, self.G, axis=0)                          # per player (its match)
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
                              self._fight(pos, eye, rot, visible), self._mem(opp), self._routes(pos, rot),
                              self._ffa(pos, eye, rot, yaw, pit), self._pad_ear(yaw),   # the group block keeps its place
                              self._more(pos, rot, c, si, visible, opp_vel, seen_t), self._dense(eye, yaw, pit),
                              self._v9(pos, rot), self._intent(pos, rot, known, seen_t), self._drops(pos, eye, rot, fdir),
                              self._v14(vel, yaw, pit, eye, known, opp_vel, visible, opp),
                              self._v15(pos, yaw, pit, eye, known, seen_t, visible),
                              self._v02(pos, eye, rot, c, si, known, opp), self._b2(pos, c, si), self._b3(pos), self._es(opp),
                              self._raim(eye, yaw, pit, fdir, known, opp_vel, visible, opp, known_a), self._pref(pos, eye, yaw, pit, visible),
                              self._emerge(eye, yaw, pit, visible), self._drift(ey, ep_, visible, pos, known, opp)], 1)
        return obs.astype(np.float32)

    def _ffa(self, pos, eye, rot, yaw, pit):
        """more than two players (see N_FFA): up to two more enemies in view besides the one attended to, nearest
        the crosshair first: there, where (3), direction (yaw sin, cos; pitch sin), whether he faces this player.
        Then: enemies in view / 5, players beyond two / 4. Positions are as old as the reaction time."""
        n, G = self.n, self.G
        out = np.zeros((n, N_FFA), np.float32)
        if G == 2:
            return out
        self.ffa_hist.append((self.state[:, :3].copy(), self.acq2.copy(), self.yaw.copy()))
        while len(self.ffa_hist) > self.react_frames + 1:
            self.ffa_hist.pop(0)
        p_old, acq, yaw_old = self.ffa_hist[0]
        ar = np.arange(n)
        rest = acq.copy()
        rest[ar, self.fidx] = False                          # the attended enemy has his own inputs
        to = p_old[self.others] + np.array([0, 0, 4.0], np.float32) - eye[:, None, :]
        dist = np.linalg.norm(to, axis=2) + 1e-6
        fdir = np.stack([np.cos(pit) * np.cos(yaw), np.cos(pit) * np.sin(yaw), -np.sin(pit)], 1)
        off = np.where(rest, 1.0 - (to * fdir[:, None, :]).sum(2) / dist, 9.0)
        order = np.argsort(off, axis=1)
        for j in range(min(2, G - 2)):
            k = order[:, j]
            on = rest[ar, k]
            t_ = to[ar, k]
            o = self.others[ar, k]
            ay = np.arctan2(t_[:, 1], t_[:, 0]) - yaw
            ap = -np.arctan2(t_[:, 2], np.hypot(t_[:, 0], t_[:, 1]) + 1e-6) - pit
            back = np.arctan2(pos[:, 1] - p_old[o, 1], pos[:, 0] - p_old[o, 0]) - np.radians(yaw_old[o])
            blk = np.concatenate([np.ones((n, 1), np.float32), rot(p_old[o] - pos) / 1000.0,
                                  np.stack([np.sin(ay), np.cos(ay), np.sin(ap), np.cos(back)], 1),
                                  np.eye(NW, dtype=np.float32)[self.weapon[o]][:, [RL, RG, LG]]], 1)   # what he holds (v9)
            out[:, 11 * j:11 * j + 11] = blk * on[:, None]
        out[:, 16] = acq.sum(1) / 5.0
        out[:, 17] = (G - 2) / 4.0
        return out

    def _drift(self, ey, ep, visible, pos, known, opp):
        """the inputs of N_DRIFT (see DRIFT_IN): the perceived crosshair-to-enemy angle's rate, raw and smoothed. Keeps the
        last frame's perceived angles and the noises' states (drift_*), and the rates on their way (drift_q, DRIFT_DELAY)"""
        n = self.n
        out = np.zeros((n, N_DRIFT), np.float32)
        if not DRIFT_IN:
            return out
        if getattr(self, "drift_ang", None) is None or len(self.drift_ang) != n:
            self.drift_ang, self.drift_s = np.zeros((n, 2), np.float32), np.zeros((n, 2), np.float32)
            self.drift_ok, self.drift_sok = np.zeros(n, bool), np.zeros(n, bool)
            self.drift_pos, self.drift_kn = np.zeros((n, 3), np.float32), np.zeros((n, 3), np.float32)
            self.drift_pk, self.drift_foe = np.zeros(n, np.int64), np.full(n, -1, np.int64)
            self.drift_wn, self.drift_an = np.zeros((n, 2), np.float32), np.zeros((n, 2), np.float32)
            self.drift_q = []
        ang = np.stack([ey, ep], 1).astype(np.float32)
        pk = getattr(self, "_drift_pick", None)
        pk = np.zeros(n, np.int64) if pk is None else np.asarray(pk, np.int64).reshape(n)
        self._drift_pick = None
        k0_ = getattr(self, "_rf_known0", None) if RANGE_FIX else None
        if k0_ is not None and len(k0_) == n:                # (RANGE_FIX with DRIFT_IN, the v0.3.8 merge) the jump test on the place
            known = k0_                                      # before the distance error: that error slides the place along the line
        self._rf_known0 = None                               # from his eyes by tens of units a frame at long range (the angle stays
        foe = np.asarray(opp, np.int64).reshape(n)           # as it is) and read as a new sighting (DRIFT_JUMP), the rate zeroed
        now = np.asarray(visible, bool)[:n] & (self.hp[:n] > 0)
        ok = (now & self.drift_ok & (pk == self.drift_pk) & (foe == self.drift_foe)
              & (np.linalg.norm(pos - self.drift_pos, axis=1) < DRIFT_JUMP) & (np.linalg.norm(known - self.drift_kn, axis=1) < DRIFT_JUMP))
        d_ = ang - self.drift_ang
        d_[:, 0] = (d_[:, 0] + 180.0) % 360.0 - 180.0
        rate = d_ / DT                                       # degrees a second, as the perceived picture moved
        rho = math.exp(-DT / max(DRIFT_TAU, 1e-3))
        if DRIFT_WEBER > 0 or DRIFT_SIGMA > 0:               # the motion sense's own errors: a scale error and a wander, both slow
            z_ = self.rng.normal(0, 1, (n, 4)).astype(np.float32)
            self.drift_wn = (rho * self.drift_wn + math.sqrt(1 - rho * rho) * DRIFT_WEBER * z_[:, :2]).astype(np.float32)
            self.drift_an = (rho * self.drift_an + math.sqrt(1 - rho * rho) * DRIFT_SIGMA * z_[:, 2:]).astype(np.float32)
            rate = rate * (1.0 + self.drift_wn) + self.drift_an
        rate = np.where(ok[:, None], rate, 0.0).astype(np.float32)
        a_ = math.exp(-DT / max(DRIFT_SMOOTH, 1e-3))
        self.drift_s = np.where(ok[:, None], np.where(self.drift_sok[:, None], a_ * self.drift_s + (1 - a_) * rate, rate), 0.0).astype(np.float32)
        self.drift_sok = ok.copy()
        self.drift_ang, self.drift_ok, self.drift_pk, self.drift_foe = ang, now, pk, foe
        self.drift_pos, self.drift_kn = pos.astype(np.float32).copy(), known.astype(np.float32).copy()
        sm = self.drift_s
        if DRIFT_MIN > 0:                                    # too slow to be noticed
            rate = np.where(np.abs(rate) < DRIFT_MIN, 0.0, rate)
            sm = np.where(np.abs(sm) < DRIFT_MIN, 0.0, sm)
        sc = np.array(DRIFT_SCALE, np.float32)
        cur = np.concatenate([np.clip(rate / sc, -1, 1), np.clip(sm / sc, -1, 1)], 1).astype(np.float32)
        dq = int(round(DRIFT_DELAY / 1000.0 / DT))
        if dq <= 0:
            return cur
        self.drift_q.append((cur, ok.copy()))                # read DRIFT_DELAY later; zeros if the sighting broke in between
        while len(self.drift_q) > dq + 1:
            self.drift_q.pop(0)
        if len(self.drift_q) <= dq:
            return out
        held = np.stack([q_[1] for q_ in self.drift_q]).all(0)
        return np.where(held[:, None], self.drift_q[0][0], 0.0).astype(np.float32)

    def _sm_note(self, opp, rf_, pick):
        """(SENSE_MINOR) keeps every player's facing, crouch, air and weapon a frame (sm_hist, beside opp_hist and as long)
        and reads the enemy's at the sighting his place is read from (opp_hist's pick: pick, else rf_ frames back), and his
        place then (for the facing input); his facing with a drifting error (sm_face). -> self._sm_e, per player. Called once a frame by observe()"""
        n = self.n
        if getattr(self, "sm_hist", None) is None or getattr(self, "sm_face", None) is None or len(self.sm_face) != n:
            self.sm_hist, self.sm_face = [], np.zeros(n, np.float32)
        self.sm_hist.append((self.yaw[:n].astype(np.float32).copy(), np.asarray(self.duck[:n], bool).copy(),
                             (self.state[:n, 6] < 0.5).copy(), np.asarray(self.weapon[:n], np.int64).copy(),
                             self.state[:n, :3].astype(np.float32).copy()))
        L_ = len(self.opp_hist)
        while len(self.sm_hist) > L_:
            self.sm_hist.pop(0)
        while len(self.sm_hist) < L_:                       # (newer than opp_hist: the oldest stands for the frames before)
            self.sm_hist.insert(0, self.sm_hist[0])
        ar = np.arange(n)
        pk = np.asarray(pick, np.int64) if pick is not None else np.broadcast_to(np.maximum(0, L_ - 1 - np.asarray(rf_, np.int64)), (n,))
        H = [np.stack([h_[k_] for h_ in self.sm_hist]) for k_ in range(5)]
        rho = math.exp(-DT / max(SM_FACE_TAU, 1e-3))
        self.sm_face = (rho * self.sm_face + math.sqrt(1.0 - rho * rho) * SM_FACE_DEG * self.rng.normal(0, 1, n)).astype(np.float32)
        o_ = np.asarray(opp, np.int64)
        self._sm_e = dict(yaw=H[0][pk, o_] + self.sm_face, duck=H[1][pk, o_], air=H[2][pk, o_], weapon=H[3][pk, o_], pos=H[4][pk, o_])

    def _vel_percept(self, v):
        """(VEL_FIX) the enemy's velocity as he reads it: times a drifting scale error (VEL_WEBER, VEL_TAU), a speed below
        VEL_MIN read as none. Keeps the error (vf_w); called once a frame by observe()"""
        n = len(v)
        if getattr(self, "vf_w", None) is None or len(self.vf_w) != n:
            self.vf_w = np.zeros(n, np.float32)
        rho = math.exp(-DT / max(VEL_TAU, 1e-3))
        self.vf_w = (rho * self.vf_w + math.sqrt(1.0 - rho * rho) * VEL_WEBER * self.rng.normal(0, 1, n)).astype(np.float32)
        v = np.asarray(v, np.float32) * (1.0 + self.vf_w)[:, None]
        if VEL_MIN > 0:
            v = np.where(np.linalg.norm(v, axis=1, keepdims=True) < VEL_MIN, 0.0, v)
        return v.astype(np.float32)

    SEAT_AIM = ("PERCEPT_SIGMA", "PERCEPT_SPEED", "FLINCH_PER_DMG", "FLINCH_MAX", "FLINCH_TAU", "MOTOR_NOISE", "MOTOR_BASE",
                "SURPRISE_MS", "AIM2_W", "AIM2_C_SLIP", "AIM2_S0", "AIM2_CAP_SLIP", "AIM2_C_ECC", "AIM2_E0", "AIM2_CAP_ECC",
                "AIM2_SPLIT_W", "AIM2_FOCUS_GAIN", "AIM2_FOCUS_SIG", "AIM2_FLINCH")

    def _sa(self, name):
        """(SEAT_AIM, branch aim2) a check that seats two aim models: env.seat_aim = {name: one value a seat} for the names of
        SEAT_AIM; a name it does not hold, or seat_aim None (the default): the module's value (PERCEPT_SIGMA: the
        simulator's own percept_sigma), so nothing changes. To seat the old model beside AIM2 the module runs with AIM2,
        AIM2_SPLIT and AIM2_FOCUS on and the old seats get AIM2_W 0, AIM2_SPLIT_W 0, AIM2_FOCUS_GAIN 2, AIM2_FOCUS_SIG 1,
        AIM2_FLINCH 0 (the blend's start: the old model exactly, section 7 of docs/v0.5.2/AIM_MODEL.md)"""
        sa = getattr(self, "seat_aim", None)
        if sa is not None and name in sa:
            return np.asarray(sa[name], np.float64)[:self.n]
        return self.percept_sigma if name == "PERCEPT_SIGMA" else globals()[name]

    def _aim2_note(self, eye, n):
        """(AIM2) keeps a frame of his view (yaw, elevation) and of the true bearing to the enemy's acquired place (self.known,
        as opp_hist keeps it), with the acquired flag: the slip and the eccentricity are read from it at his read delay.
        observe() calls it every frame (the plugins too, through observe()); aim2_clear() empties it"""
        if getattr(self, "a2_hist", None) is None:
            self.a2_hist = []
        tb_ = self.known[:n] + np.array([0, 0, 4.0], np.float32) - eye
        by_ = np.degrees(np.arctan2(tb_[:, 1], tb_[:, 0]))
        bp_ = np.degrees(np.arctan2(tb_[:, 2], np.hypot(tb_[:, 0], tb_[:, 1]) + 1e-6))
        self.a2_hist.append(np.stack([np.asarray(self.yaw[:n], np.float64), -np.asarray(self.pitch[:n], np.float64), by_, bp_,
                                      np.asarray(self.acquired[:n], np.float64)], 1))
        keep = max(self.react_frames + FOCUS_LOSS, self.vel_frames) + 3
        while len(self.a2_hist) > keep:
            self.a2_hist.pop(0)

    def aim2_clear(self):
        """(AIM2) no slip until two new frames: where a plugin clears opp_hist"""
        self.a2_hist = []
        self.a2_last = None

    def _aim2_err(self, n, pick, rf_):
        """(AIM2) the slip and eccentricity terms of the sight error (degrees, a player), as of his read delay: pick (the
        index into opp_hist each player reads, with focus) or rf_ (his delay in frames: one number or one a seat). Keeps
        a2_last = (slip deg/s, ecc deg, error) for the measurements"""
        H = self.a2_hist
        L = len(H)
        Lo = len(self.opp_hist)
        if pick is not None:
            back = (Lo - 1) - np.asarray(pick, np.int64)
        else:
            back = np.broadcast_to(np.asarray(rf_, np.int64), (n,)).copy()
        back = np.minimum(back, Lo - 1)
        i1 = (L - 1) - back
        i0 = i1 - 1
        ok = i0 >= 0
        A = np.stack(H)                                      # (L, n, 5)
        ar = np.arange(n)
        h1 = A[np.maximum(i1, 0), ar]
        h0 = A[np.maximum(i0, 0), ar]
        w = lambda x: (x + 180.0) % 360.0 - 180.0
        sy = w(h1[:, 2] - h0[:, 2]) - w(h1[:, 0] - h0[:, 0])     # the target's turn across his view, a frame
        sp = (h1[:, 3] - h0[:, 3]) - (h1[:, 1] - h0[:, 1])
        both = ok & (h1[:, 4] > 0) & (h0[:, 4] > 0)
        slip = np.where(both, np.hypot(sy * np.cos(np.radians(h1[:, 3])), sp) / DT, 0.0)
        y1, e1, by, bp = (np.radians(h1[:, j]) for j in range(4))
        cosang = np.cos(e1) * np.cos(bp) * np.cos(by - y1) + np.sin(e1) * np.sin(bp)
        ecc = np.where((i1 >= 0) & (h1[:, 4] > 0), np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0))), 0.0)
        g_ = self._sa
        err = (np.minimum(g_("AIM2_C_SLIP") * np.maximum(0.0, slip - g_("AIM2_S0")), g_("AIM2_CAP_SLIP"))
               + np.minimum(g_("AIM2_C_ECC") * np.maximum(0.0, ecc - g_("AIM2_E0")), g_("AIM2_CAP_ECC")))
        err = err * (self.script[:n] == 0)
        self.a2_last = (slip.astype(np.float32), ecc.astype(np.float32), err.astype(np.float32))
        return err.astype(np.float32)

    def _range_percept(self, known, eye, visible):
        """(RANGE_FIX) the place of an enemy in view moved along the line from his eyes by a drifting share of the distance
        (RANGE_WEBER, RANGE_TAU; at most half). Keeps the error (rf_e); called once a frame by observe()"""
        n = len(known)
        if getattr(self, "rf_e", None) is None or len(self.rf_e) != n:
            self.rf_e = np.zeros(n, np.float32)
        rho = math.exp(-DT / max(RANGE_TAU, 1e-3))
        self.rf_e = (rho * self.rf_e + math.sqrt(1.0 - rho * rho) * RANGE_WEBER * self.rng.normal(0, 1, n)).astype(np.float32)
        g_ = (np.asarray(visible, bool)[:n] & (self.script[:n] == 0)).astype(np.float32) * np.clip(self.rf_e, -0.5, 0.5)
        self._rf_g = g_                                      # (AIM2_SPLIT: the same share for the world's place)
        return (known + (known - eye) * g_[:, None]).astype(np.float32)

    def drift_clear(self, seats=None):
        """(DRIFT_IN) no rate until two new perceived frames: a plugin calls it where it clears opp_hist, and on a frame
        without observe()"""
        if getattr(self, "drift_ang", None) is None:
            return
        s_ = slice(None) if seats is None else seats
        self.drift_ok[s_], self.drift_sok[s_] = False, False
        self.drift_s[s_] = 0.0
        for q_ in getattr(self, "drift_q", []):
            q_[1][s_] = False

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
        if PROJ_FIX:                                         # (PROJ_FIX) noticed late, read late, the fuse only if followed
            P, V, G, see = self._proj_fix(P, V, A, G, see)
            to = P - eye[:, None, :]
            dist = np.linalg.norm(to, axis=2) + 1e-6
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

    def _proj_fix(self, P, V, A, G, see):
        """(PROJ_FIX) per player and enemy projectile slot: frames it has flown (pf_life) and been in his sight on end
        (pf_run), the slots' ages (pf_age: a new projectile when it goes back), the last frames' readings (pf_hist).
        -> the place, speed and age PROJ_READ_MS old, the age 99 where he has not followed it since it left (its fuse
        unknown), and seen only after PROJ_NOTICE_MS in sight on end. Called once a frame by observe()"""
        if getattr(self, "pf_run", None) is None or self.pf_run.shape != see.shape:
            self.pf_run, self.pf_life = np.zeros(see.shape, np.int64), np.zeros(see.shape, np.int64)
            self.pf_age, self.pf_hist = np.zeros(see.shape, np.float32), []
        new_ = A & (G < self.pf_age - 1e-4)
        self.pf_life = np.where(A, np.where(new_, 1, self.pf_life + 1), 0)
        self.pf_run = np.where(see, np.where(new_, 1, self.pf_run + 1), 0)
        self.pf_age = np.where(A, G, 0.0).astype(np.float32)
        self.pf_hist.append((P.copy(), V.copy(), A.copy(), G.copy(), self.pf_run >= self.pf_life))
        dq = max(0, int(round(PROJ_READ_MS / 1000.0 / DT)))
        while len(self.pf_hist) > dq + 1:
            self.pf_hist.pop(0)
        P0, V0, A0, G0, Y0 = self.pf_hist[0]
        need = max(int(round(PROJ_NOTICE_MS / 1000.0 / DT)), dq + 1)
        see = see & A0 & (self.pf_run >= need)
        self._pf_last = see
        return P0, V0, np.where(Y0, G0, 99.0).astype(np.float32), see

    def proj_clear(self, seats=None):
        """(PROJ_FIX) nothing followed: a plugin calls it where it clears opp_hist (a new life)"""
        if getattr(self, "pf_run", None) is None:
            return
        s_ = slice(None) if seats is None else seats
        self.pf_run[s_] = 0
        for h_ in self.pf_hist:
            h_[4][s_] = False

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
            out[ii, :JL.N_JUMP] = JL.inputs(J.jumps if getattr(J, "rj", False) else self.jumps, jd_, np.where(gi >= 0, ji_, -1),   # (RJ_RUN_P, RJ_OPEN: its own list)
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
            out[:, N_V15 - N_EN - 2], out[:, N_V15 - N_EN - 1] = (self.legs & ~self.solo_now) if SOLO_SELF else self.legs, self.legs_on
        if EN_ON:                                            # his intention is the enemy (FIGHT_TARGET, HUNT)
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
        self.pf_map = name                                  # (PREFIRE: its lists of places a weapon are read at the first use)
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
        if EN_STACK:                                         # (B-257) everybody has just spawned: the stacks are known
            self._es_set(done, slice(None), spawn=True)

    # ---- B-257: the enemy's stack, believed (see EN_STACK)
    def _es_init(self):
        """the belief's state: per player and other player of his group (by his place in the group, as v02_bt): expected
        health and armor, their variances, seconds since pinned; and the damage he has dealt each, not yet taken off"""
        n = self.n
        ng_ = self._others_arr().shape[1] + 1
        self.es_h = np.full((n, ng_), SPAWN_HP, np.float32)
        self.es_a = np.zeros((n, ng_), np.float32)
        self.es_vh = np.zeros((n, ng_), np.float32)
        self.es_va = np.zeros((n, ng_), np.float32)
        self.es_pin = np.zeros((n, ng_), np.float32)
        self.es_dmg = np.zeros((n, ng_), np.float32)        # the damage he dealt each since the last frame of the belief

    def _es_set(self, rows, cols, spawn=True):
        """rows' belief of cols: a known spawn (spawn=True) or nothing known (the unseen enemy's average and spread)"""
        if spawn:
            self.es_h[rows, cols], self.es_a[rows, cols], self.es_vh[rows, cols], self.es_va[rows, cols] = SPAWN_HP, 0.0, 0.0, 0.0
            self.es_pin[rows, cols] = 0.0
        else:
            self.es_h[rows, cols], self.es_a[rows, cols] = ES_MU_H, ES_MU_A
            self.es_vh[rows, cols], self.es_va[rows, cols] = ES_SD_H ** 2, ES_SD_A ** 2
            self.es_pin[rows, cols] = 99.0

    def note_dealt(self, i, v, dmg):
        """(EN_STACK) player i hit player v (another of his group, alive after the hit) for dmg points (health and armor
        together, before the armor's share): his belief of v's stack loses it at the next frame of the belief. step()
        does it for the hits of each frame; a game server's plugin calls it with the game's count of what he dealt."""
        if EN_STACK and dmg > 0:
            self.es_dmg[i, self._slot(v)] += float(dmg)

    def _es_take(self, j, k, kind, val, cap):
        """player j saw or heard player k (by place in the group) take a health or armor item of value val to cap"""
        if kind == "hp":
            h, v = float(self.es_h[j, k]), float(self.es_vh[j, k])
            if cap <= 100:                                   # (+25 and +50: taken only under 100, so he was under 100)
                h = min(h, 99.0)
            sd = math.sqrt(max(v, 1.0))
            f = min(1.0, max(0.0, (cap - (h + val)) / (2.0 * sd) + 0.5))      # (the share of the belief the cap does not cut)
            self.es_h[j, k], self.es_vh[j, k] = min(float(cap), h + val), v * f
        else:
            a, v = float(self.es_a[j, k]), float(self.es_va[j, k])
            sd = math.sqrt(max(v, 1.0))
            f = min(1.0, max(0.0, (cap - (a + val)) / (2.0 * sd) + 0.5))
            self.es_a[j, k], self.es_va[j, k] = min(float(cap), a + val), v * f

    def _es_update(self):
        """a frame of the belief (observe() calls it; a game server's plugin on a frame without observe()): the damage he
        dealt, a pain sound heard, the tick above 100, the drift while unseen, the clocks"""
        if not EN_STACK:
            return
        n = self.n
        ar = np.arange(n)
        oth = self._others_arr()
        sl = self._slot(oth)                                 # (players, others): their places in the group
        ar2 = ar[:, None]
        # the damage he dealt: off the armor's share while it lasts (as _damage), the rest off the health (never below 1:
        # the blow that kills is not counted, note_dealt)
        d = self.es_dmg
        if (d > 0).any():
            save = np.minimum(self.es_a, np.ceil(ARMOR_ABSORB * d))
            self.es_a = (self.es_a - save).astype(np.float32)
            self.es_h = np.maximum(self.es_h - (d - save), 1.0).astype(np.float32)
        self.es_dmg = np.zeros_like(self.es_h)
        # a pain sound heard on this frame pins the health into its band
        pt_ = getattr(self, "pain_t", None)
        if pt_ is not None:
            fresh = np.nonzero(pt_[:n] < 0.5 * DT)[0]
            if len(fresh):
                src_ = getattr(self, "pain_src", None)
                who_ = oth[fresh, 0] if src_ is None else np.where(src_[fresh] >= 0, src_[fresh], oth[fresh, 0])
                k_ = self._slot(who_)
                b_ = self.pain_b[fresh]
                h_, v_ = self.es_h[fresh, k_], self.es_vh[fresh, k_]
                lo_ = np.where(b_ == 0, 1.0, 25.0 * b_).astype(np.float32)
                hi_ = np.where(b_ >= 3, 1e9, 25.0 * b_ + 24.0).astype(np.float32)
                inb = (h_ >= lo_) & (h_ <= hi_)
                low = b_ < 3
                self.es_h[fresh, k_] = np.where(low & ~inb, 0.5 * (lo_ + np.minimum(hi_, 99.0)), np.where(~low & ~inb, 87.5, h_))
                self.es_vh[fresh, k_] = np.where(low, np.where(inb, np.minimum(v_, ES_BAND_VAR), ES_BAND_VAR),
                                                 np.where(inb, v_, np.maximum(v_, ES_BAND_VAR)))
                self.es_pin[fresh, k_] = np.where(low, 0.0, self.es_pin[fresh, k_])
        # health and armor over 100 tick down a point a second
        self.es_h = np.where(self.es_h > 100.0, np.maximum(100.0, self.es_h - DT), self.es_h).astype(np.float32)
        self.es_a = np.where(self.es_a > 100.0, np.maximum(100.0, self.es_a - DT), self.es_a).astype(np.float32)
        # unseen: toward the unseen enemy's average, the spread toward its spread
        acq_ = np.zeros(self.es_h.shape, bool)
        acq_[ar2, sl] = np.asarray(self._v02_others()[1], bool)
        k_ = (DT / ES_TAU) * ~acq_
        self.es_h = (self.es_h + k_ * (ES_MU_H - self.es_h)).astype(np.float32)
        self.es_a = (self.es_a + k_ * (ES_MU_A - self.es_a)).astype(np.float32)
        self.es_vh = (self.es_vh + 2.0 * k_ * (ES_SD_H ** 2 - self.es_vh)).astype(np.float32)
        self.es_va = (self.es_va + 2.0 * k_ * (ES_SD_A ** 2 - self.es_va)).astype(np.float32)
        self.es_pin = np.minimum(self.es_pin + DT, 99.0).astype(np.float32)

    def _es(self, opp):
        """the inputs of N_ES (see EN_STACK), about the enemy opp of each player (in a group: the one he attends to)"""
        n = self.n
        out = np.zeros((n, N_ES), np.float32)
        if not EN_STACK:
            return out
        self._es_update()
        ar = np.arange(n)
        so = self._slot(opp)
        h, a = self.es_h[ar, so], self.es_a[ar, so]
        out[:, 0] = h / 200.0
        out[:, 1] = a / 200.0
        out[:, 2] = (h + a) / 300.0
        out[:, 3] = np.sqrt(np.maximum(self.es_vh[ar, so] + self.es_va[ar, so], 0.0)) / 150.0
        out[:, 4] = np.minimum(self.es_pin[ar, so], 30.0) / 30.0
        out[:, 5] = (h + a) < ES_WEAK
        grp = ar // (self._others_arr().shape[1] + 1)
        out[np.isin(self.kind[grp], (MOVE, SOLO))] = 0.0     # (no enemy about)
        return out

    @staticmethod
    def _aim_at(e, p, yaw, pit):
        """degrees from his crosshair (yaw, pit in radians) to the points p seen from the eyes e: (yaw, pitch; + = left, down)"""
        to = p - e
        hd = np.hypot(to[..., 0], to[..., 1]) + 1e-6
        ey = np.degrees((np.arctan2(to[..., 1], to[..., 0]) - yaw + np.pi) % (2 * np.pi) - np.pi)
        ep = np.degrees(-np.arctan2(to[..., 2], hd) - pit)
        return ey, ep

    def _raim(self, eye, yaw, pit, fdir, known, opp_vel, visible, opp, known_a=None):
        """the inputs of N_RAIM (see RL_AIM): with the rocket launcher in his hand, the backstop; with the enemy in view
        too, the floor aim point and the nearest wall by it. Reads only; keeps nothing."""
        n = self.n
        out = np.zeros((n, N_RAIM), np.float32)
        if not RL_AIM:
            return out
        ii = np.nonzero((self.weapon[:n] == RL) & (self.hp[:n] > 0))[0]
        if not len(ii):
            return out
        e_ = eye[ii].astype(np.float32)
        f_ = fdir[ii].astype(np.float32)
        kn = known[ii].astype(np.float32)
        vis = np.asarray(visible, bool)[ii]
        # ---- the backstop: where a rocket fired now along his view would burst
        fr = self.w.rays_each(e_, f_[:, None, :], RAIM_FAR, mask=self.sight)[:, 0]
        bd = fr * RAIM_FAR
        bp = e_ + f_ * bd[:, None]
        out[ii, 0] = 1.0
        out[ii, 1] = np.minimum(bd / 2000.0, 2.0)
        out[ii, 2] = np.clip((bp[:, 2] - e_[:, 2]) / 300.0, -1.0, 1.0)
        out[ii, 3] = np.clip((bd - np.linalg.norm(kn - e_, axis=1)) / 500.0, -1.0, 1.0) * vis
        kn_a = kn if (known_a is None or not AIM2_SPLIT) else known_a[ii].astype(np.float32)   # (AIM2_SPLIT) the aim's place
        out[ii, 4] = np.clip(1.0 - np.linalg.norm(bp - kn_a, axis=1) / P_RADIUS[RL], 0.0, 1.0) * vis * (fr < 1.0)
        jj = np.nonzero(vis)[0]
        if not len(jj):
            return out
        # ---- the floor aim point: the floor under where he will be when the rocket gets there
        k = ii[jj]
        e2, kn2, ov = e_[jj], kn[jj], opp_vel[k].astype(np.float32)
        air = self._sm_e["air"][k] if SENSE_MINOR else self.state[opp[k], 6] < 0.5
        feet = kn2 - np.array([0, 0, 24.0], np.float32)
        c_ = float(P_SPEED[RL])
        t = np.linalg.norm(feet - e2, axis=1) / c_
        for _ in range(3):                                   # the flight time and his place by then, each from the other
            t = np.minimum(t, 3.0)
            dz = np.where(air, ov[:, 2] * t - 400.0 * t * t, 0.0)
            m = feet + np.stack([ov[:, 0] * t, ov[:, 1] * t, dz], 1)
            aimz = np.minimum(m[:, 2], feet[:, 2])           # (aimed at the floor: no higher than his feet now)
            t = np.linalg.norm(np.stack([m[:, 0], m[:, 1], aimz], 1) - e2, axis=1) / c_
        t = np.minimum(t, 3.0)
        dz = np.where(air, ov[:, 2] * t - 400.0 * t * t, 0.0)
        m = (feet + np.stack([ov[:, 0] * t, ov[:, 1] * t, dz], 1)).astype(np.float32)
        top = np.maximum(m[:, 2], feet[:, 2]) + 40.0
        st = np.stack([m[:, 0], m[:, 1], top], 1).astype(np.float32)
        frd = self.w.rays(st, np.array([[0, 0, -1.0]], np.float32), 1024.0, mask=self.sight)[:, 0]
        found = frd < 1.0
        fz = np.where(found, top - frd * 1024.0, m[:, 2])
        fp = np.stack([m[:, 0], m[:, 1], fz + PF_LIFT], 1).astype(np.float32)
        ey, ep = self._aim_at(e2, fp, yaw[k], pit[k])
        if AIM2_SPLIT:                                       # (AIM2_SPLIT) the sight error on the final angles only
            ey, ep = ey + self._a2_dang[k, 0], ep + self._a2_dang[k, 1]
        o = 5
        out[k, o] = 1.0
        out[k, o + 1], out[k, o + 2] = np.clip(ey / 30.0, -1, 1), np.clip(ey / 2.0, -1, 1)
        out[k, o + 3], out[k, o + 4] = np.clip(ep / 15.0, -1, 1), np.clip(ep / 2.0, -1, 1)
        out[k, o + 5] = found
        out[k, o + 6] = np.clip((m[:, 2] - fz) / 200.0, 0.0, 2.0) * found
        out[k, o + 7] = np.clip(t / 1.5, 0.0, 2.0)
        out[k, o + 8] = self._v02_clear(e2, fp)
        # ---- the nearest wall by that place, at the height of his middle
        o = 14
        mid = (fp + np.array([0, 0, 24.0 - PF_LIFT], np.float32)).astype(np.float32)
        an = np.linspace(0.0, 2 * np.pi, RAIM_WALL_N, endpoint=False)
        dw = np.stack([np.cos(an), np.sin(an), np.zeros(RAIM_WALL_N)], 1).astype(np.float32)
        fw = self.w.rays_each(mid, np.repeat(dw[None], len(k), 0), RAIM_WALL, mask=self.sight)
        j_ = fw.argmin(1)
        fmin = fw[np.arange(len(k)), j_]
        hit = fmin < 1.0
        dist = fmin * RAIM_WALL
        wp = mid + dw[j_] * dist[:, None]
        rel = an[j_] - yaw[k]
        wy, wpi = self._aim_at(e2, wp, yaw[k], pit[k])
        out[k, o] = hit
        out[k, o + 1], out[k, o + 2] = np.sin(rel) * hit, np.cos(rel) * hit
        out[k, o + 3] = np.where(hit, dist / RAIM_WALL, 1.0)
        out[k, o + 4], out[k, o + 5] = np.clip(wy / 30.0, -1, 1) * hit, np.clip(wpi / 15.0, -1, 1) * hit
        return out

    def _pf_load(self):
        """(PREFIRE) the map's lists of places a weapon: {weapon: (places [P, 3], their share / 15 [P], walking-map points [P])}"""
        out = {}
        R = self.route
        here_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_places")
        for w_, k_ in zip((RL, GL, PG), PF_KINDS):
            f_ = os.path.join(here_, "{}_{}.json".format(self.pf_map, k_))
            pl_ = []
            if os.path.exists(f_):
                with open(f_, encoding="utf-8") as fh_:
                    pl_ = json.load(fh_).get("places") or []
            if pl_ and R is not None:
                pp_ = np.array([p_["pos"] for p_ in pl_], np.float32).reshape(-1, 3)
                sh_ = np.array([min(1.0, float(p_.get("share", 0.0) or 0.0) / 15.0) for p_ in pl_], np.float32)
                out[w_] = (pp_, sh_, R.locate(pp_))
        return out

    def _pref(self, pos, eye, yaw, pit, visible):
        """the inputs of N_PREF (see PREFIRE): the pros' blind-shot places of one weapon on the enemy's believed way to him.
        Reads the belief _v02 made this frame (v02_bel, v02_bel_ok, v02_bt_now); keeps only the map's lists (pf_lists)."""
        n = self.n
        out = np.zeros((n, N_PREF), np.float32)
        if not PREFIRE:
            return out
        R, W = self.route, self.v02_ways
        if R is None or W is None:
            return out
        if getattr(self, "pf_lists", None) is None:
            self.pf_lists = self._pf_load()
        L = self.pf_lists
        if not L:
            return out
        on = np.asarray(self.v02_bel_ok, bool)[:n] & ~np.asarray(visible, bool)[:n] & (self.hp[:n] > 0)
        okw = {w_: self.has[:n, w_].astype(bool) & (self.ammo[:n, w_] >= 1) & (w_ in L) for w_ in (RL, GL, PG)}
        pick = np.full(n, -1, np.int64)
        for w_ in (PG, GL, RL):                              # the fallback: the first of PF_KINDS he has (rockets written last: first)
            pick = np.where(okw[w_], w_, pick)
        hand = self.weapon[:n]
        for w_ in (RL, GL, PG):                              # the weapon in his hand, when it has a list
            pick = np.where((hand == w_) & okw[w_], w_, pick)
        pick = np.where(on, pick, -1)
        S_ = PF_SLOTS
        for w_, kc_ in zip((RL, GL, PG), range(3)):
            ii = np.nonzero(pick == w_)[0]
            if not len(ii):
                continue
            pps, shs, pn = L[w_]
            S = min(S_, len(pps))
            p_, e_ = pos[ii], eye[ii].astype(np.float32)
            na, nb = R.locate(p_), R.locate(np.asarray(self.v02_bel, np.float32)[ii])
            wb = W[pn[None, :], nb[:, None]].astype(np.float32)      # the way from the believed place to each place (16ths of a second)
            wm = W[na[:, None], pn[None, :]].astype(np.float32)      # ... from each place to him
            wbm = W[na, nb].astype(np.float32)[:, None]              # ... from the believed place to him
            ok = (wb < 255) & (wm < 255) & (np.linalg.norm(pps[None, :, :] - p_[:, None, :], axis=2) >= PF_SELF)
            det = np.maximum(np.where(wbm < 255, wb + wm - wbm, wb + wm), 0.0) / 16.0
            score = np.where(ok, det + 0.01 * wb / 16.0, np.inf)
            order = np.argsort(score, axis=1, kind="stable")[:, :S]
            ar = np.arange(len(ii))[:, None]
            valid = np.isfinite(score[ar, order])
            pp = (pps[order] + np.array([0, 0, PF_LIFT], np.float32)).astype(np.float32)        # (k, S, 3)
            ey, ep = self._aim_at(e_[:, None, :], pp, yaw[ii][:, None], pit[ii][:, None])
            to = pp - e_[:, None, :]
            d = np.linalg.norm(to, axis=2)
            bt = np.asarray(self.v02_bt_now, np.float32)[ii]
            since = bt - np.minimum(bt, 1.0)                 # (the believed place is where he was a second after the last news)
            blk = np.zeros((len(ii), PF_SLOTS, PF_F), np.float32)
            blk[:, :S, 0] = np.clip(ey / 30.0, -1, 1)
            blk[:, :S, 1] = np.clip(ep / 15.0, -1, 1)
            blk[:, :S, 2] = np.minimum(d / 2000.0, 1.5)
            blk[:, :S, 3] = np.clip((wb[ar, order] / 16.0 - since[:, None]) / 5.0, -1, 1)
            blk[:, :S, 5] = self._v02_clear(np.repeat(e_, S, axis=0), pp.reshape(-1, 3)).reshape(len(ii), S)
            blk[:, :S, 6] = np.minimum(det[ar, order] / 5.0, 1.0)
            blk[:, :S, 7] = shs[order]
            if w_ == GL:                                     # (the grenade's low arc, as the grenade arc inputs)
                D = np.hypot(to[..., 0], to[..., 1]) + 1e-6
                v_, g_ = float(P_SPEED[GL]), 800.0
                disc = v_ ** 4 - g_ * (g_ * D * D + 2.0 * to[..., 2] * v_ * v_)
                reach = disc >= 0.0
                th = np.arctan2(v_ * v_ - np.sqrt(np.maximum(disc, 0.0)), g_ * D)
                epg = np.degrees(-(th - 0.2 * np.cos(th)) - pit[ii][:, None])
                blk[:, :S, 8] = np.clip(epg / 15.0, -1, 1) * reach
                blk[:, :S, 4] = np.clip(D / np.maximum(v_ * np.cos(th), 1.0) / 1.5, 0.0, 2.0) * reach
            else:
                blk[:, :S, 4] = np.clip(d / float(P_SPEED[w_]) / 1.5, 0.0, 2.0)
            blk[:, :S, 9] = 1.0
            blk[:, :S, 10 + kc_] = 1.0
            blk[:, :S] *= valid[:, :, None]
            out[ii] = blk.reshape(len(ii), -1)
        return out

    def _emg_fwd(self):
        """(EMERGE_IN) the walking map's links forward, padded: [points, K] targets (-1: none) and their seconds"""
        R = self.route
        fwd = [[] for _ in range(len(R.nodes))]
        for b_, lst in enumerate(R.radj):
            for a_, c_ in lst:
                fwd[a_].append((b_, c_))
        K = max(1, max(len(f_) for f_ in fwd))
        to = np.full((len(fwd), K), -1, np.int64)
        co = np.full((len(fwd), K), 1e18, np.float64)
        for a_, f_ in enumerate(fwd):
            for j_, (b_, c_) in enumerate(f_):
                to[a_, j_], co[a_, j_] = b_, c_
        return to, co

    def _emerge(self, eye, yaw, pit, visible):
        """the inputs of N_EMG (see EMERGE_IN): the emergence point of the enemy he believes in. Keeps the point (emg_pt,
        emg_ok: worked out, at the belief, a way) between its readings."""
        n = self.n
        out = np.zeros((n, N_EMG), np.float32)
        if not EMERGE_IN:
            return out
        R, W = self.route, self.v02_ways
        if R is None or W is None:
            return out
        if getattr(self, "emg_pt", None) is None or len(self.emg_pt) != n:
            self.emg_pt, self.emg_ok = np.zeros((n, 3), np.float32), np.zeros((n, 3), bool)
            self.emg_tick = 0
        if getattr(self, "emg_links", None) is None:
            self.emg_links = self._emg_fwd()
        self.emg_tick += 1
        bt = np.asarray(self.v02_bt_now, np.float32)[:n]
        live = np.asarray(self.v02_bel_ok, bool)[:n] & (bt <= EMG_FRESH) & ~np.asarray(visible, bool)[:n] & (self.hp[:n] > 0)
        self.emg_ok[~live] = False
        due = np.nonzero(live & ((self.emg_tick + np.arange(n)) % EMG_EVERY == 0))[0]
        if len(due):
            to_, co_ = self.emg_links
            bel = np.asarray(self.v02_bel, np.float32)[due]
            u = R.locate(bel).astype(np.int64)
            me = R.locate(self.state[due, :3]).astype(np.int64)
            way = W[me, u] < 255
            path = np.full((len(due), EMG_STEPS + 1), -1, np.int64)
            path[:, 0] = u
            cur, act = u.copy(), way & (u != me)
            L = np.ones(len(due), np.int64)
            for k_ in range(1, EMG_STEPS + 1):              # the greedy way: the link that leaves the least way to him
                a_ = np.nonzero(act)[0]
                if not len(a_):
                    break
                cand = to_[cur[a_]]
                wv = np.where(cand == me[a_, None], 0.0, np.where(cand >= 0, W[me[a_, None], np.maximum(cand, 0)], 255).astype(np.float64))
                wv = np.where(wv >= 255, 1e9, wv / 16.0)
                c_ = np.where(cand >= 0, co_[cur[a_]] + wv, 1e18)
                nx = cand[np.arange(len(a_)), c_.argmin(1)]
                bad = (nx < 0) | (path[a_, :k_] == nx[:, None]).any(1)
                ok_ = ~bad
                path[a_[ok_], k_] = nx[ok_]
                cur[a_[ok_]] = nx[ok_]
                L[a_[ok_]] += 1
                act[a_[bad]] = False
                act[a_[ok_]] = nx[ok_] != me[a_[ok_]]
            e_ = eye[due].astype(np.float32)
            ii, kk = np.nonzero(path >= 0)
            pts = (R.nodes[path[ii, kk]] + np.array([0, 0, VIEW_H], np.float32)).astype(np.float32)
            fr = self.w.lines(e_[ii], pts) if self.sight is None else self.w.lines(e_[ii], pts, mask=self.sight)
            vis = np.zeros(path.shape, bool)
            vis[ii, kk] = fr >= 0.999
            kk = np.arange(path.shape[1])[None, :]           # walked back from his own point while the eyes see it: the point is
            brk = np.ones(path.shape, bool)                  # after the last break (a hidden point) on the way, or his own point
            brk[:, 1:] = ~(vis[:, :-1] & vis[:, 1:])         # when he does not see even that
            j_ = np.where(brk & (kk >= 1) & (kk <= (L - 1)[:, None]), kk, 0).max(1)
            pt = (R.nodes[path[np.arange(len(due)), j_]] + np.array([0, 0, VIEW_H], np.float32)).astype(np.float32)
            self.emg_pt[due] = np.where(way[:, None], pt, 0.0)
            self.emg_ok[due, 0] = True
            self.emg_ok[due, 1] = way & (j_ == 0) & vis[np.arange(len(due)), 0]
            self.emg_ok[due, 2] = way
        on = live & self.emg_ok[:, 0]
        pw = on & self.emg_ok[:, 2]
        ey, ep = self._aim_at(eye, self.emg_pt, yaw, pit)
        d = np.linalg.norm(self.emg_pt - eye, axis=1)
        out[:, 0] = on
        out[:, 1] = np.sin(np.radians(ey)) * pw
        out[:, 2] = np.cos(np.radians(ey)) * pw
        out[:, 3] = np.clip(ey / 30.0, -1, 1) * pw
        out[:, 4] = np.clip(ep / 15.0, -1, 1) * pw
        out[:, 5] = np.minimum(d / 1500.0, 2.0) * pw
        out[:, 6] = on & self.emg_ok[:, 1]
        out[:, 7] = pw
        return out

    def note_hunt(self, valid):
        """HUNT (and FIGHT_TARGET): the enemy as his target is reached when he is in view, given up where nothing is
        believed of him any more (valid: his intention has a route goal). step() calls it; a game server's plugin from
        intent_release()"""
        en_ = self.intent == EN_INTENT
        vis_ = np.asarray(self.visible, bool)[:len(en_)]
        self.intent_done = self.intent_done | (en_ & vis_)
        self.intent_gone = self.intent_gone | (en_ & ~np.asarray(valid, bool))
        return en_, vis_

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
        if self._hd_live():                                  # (HEAD_EVENTS) his pickup by class; another's, seen or heard
            c_ = self._hd_class(it)
            self.hd_ev[i, HEAD_COL["took_" + c_]] += 1.0
            if int(self.kind[self._match_of(i)]) not in (MOVE, SOLO):
                a2_ = getattr(self, "acq2", None)
                for j in self._mates(i):
                    sees = bool(self.acquired[j]) if a2_ is None else bool(a2_[j, (self._slot(i) - self._slot(j)) % (a2_.shape[1] + 1) - 1])
                    if sees or (np.linalg.norm(self.state[j, :3] - self.state[i, :3]) < self._evt_reach(j) and self._hear1(j, i)):
                        self.hd_ev[j, HEAD_COL["en_took_" + c_]] += 1.0
        lab = self.item_def[it][4]
        if EN_STACK and self.item_def[it][0] in ("hp", "ar") and int(self.kind[self._match_of(i)]) not in (MOVE, SOLO):
            kd_, val_, _, cap_, _ = self.item_def[it]        # (B-257) every health and armor pickup heard or seen: the belief of his stack
            a2_ = getattr(self, "acq2", None)
            for j in self._mates(i):
                sees = bool(self.acquired[j]) if a2_ is None else bool(a2_[j, (self._slot(i) - self._slot(j)) % (a2_.shape[1] + 1) - 1])
                if sees or (np.linalg.norm(self.state[j, :3] - self.state[i, :3]) < self._evt_reach(j) and self._hear1(j, i)):
                    self._es_take(j, self._slot(i), kd_, float(val_), float(cap_))
        k = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab in ("YA", "GA") else -1
        if k < 0 or int(self.kind[self._match_of(i)]) in (MOVE, SOLO):     # (alone on the map: nobody else is about)
            return
        s = self.state
        a2_ = getattr(self, "acq2", None)
        for j in self._mates(i):
            sees = bool(self.acquired[j]) if a2_ is None else bool(a2_[j, (self._slot(i) - self._slot(j)) % (a2_.shape[1] + 1) - 1])
            if sees or (np.linalg.norm(s[j, :3] - s[i, :3]) < self._evt_reach(j) and self._hear1(j, i)):
                self.v02_pk[j, self._slot(i), k] += 1.0

    # ---------------------------------------------------------------- the head's events and the win label (HEAD_EVENTS)
    def _head_init(self):
        """(HEAD_EVENTS) the books: per player the events since the head last asked (hd_ev, the frames counted in it), the
        rows to start again at the next step (a round ended), what the frame before showed (on the ground, where, where he
        left the ground, the weapon in hand); the win label's game numbers (now; of the frame being played) and band"""
        n = self.n
        s = self.state
        self.hd_ev = np.zeros((n, N_HEAD_EVENTS), np.float32)
        self.hd_frames = np.zeros(n, np.float32)
        self.hd_clear = np.zeros(n, bool)
        self.hd_gr = s[:, 6] > 0.5
        self.hd_pos = s[:, :3].astype(np.float32).copy()
        self.hd_z0 = s[:, 2].astype(np.float32).copy()
        self.hd_w = np.array(self.weapon, copy=True)
        self.hd_gid = np.full(n, -1, np.int64)
        self.hd_gid_ran = np.full(n, -1, np.int64)
        self.hd_band = np.full(n, -1, np.int64)
        self.hd_next = 0

    def _hd_live(self):
        return HEAD_EVENTS and getattr(self, "hd_ev", None) is not None

    def _hd_begin(self):
        """(HEAD_EVENTS) a step's start: the players whose round ended in the step before start their count again (from
        the state they begin in), and the game of the frame about to be played is noted (win_game)"""
        c = self.hd_clear
        if c.any():
            s = self.state
            self.hd_ev[c] = 0.0
            self.hd_frames[c] = 0.0
            self.hd_gr[c] = s[c, 6] > 0.5
            self.hd_pos[c] = s[c, :3]
            self.hd_z0[c] = s[c, 2]
            self.hd_w[c] = self.weapon[c]
            c[:] = False
        self.hd_gid_ran = self.hd_gid.copy()
        self.hd_band[:] = -1

    def _hd_game(self, q, kd):
        """(HEAD_EVENTS) the seats q begin a round of game kind kd (self.game): a new game number for a whole game or a
        mid-game start, none for the rest"""
        if not self._hd_live():
            return
        q = np.asarray(q, np.int64)
        if kd in WIN_KINDS:
            self.hd_gid[q] = self.hd_next
            self.hd_next += 1
        else:
            self.hd_gid[q] = -1

    def _hd_result(self, m):
        """(HEAD_EVENTS) the whole game or mid-game start of match m is over (before its score is cleared): the band of
        each seat's final margin, his frags less the best of the others'"""
        if not self._hd_live() or int(self.game[m]) not in WIN_KINDS:
            return
        q = self._seats(m)
        f = self.frags_r[q].astype(np.float64)
        for j_, i in enumerate(q):
            d = f[j_] - np.delete(f, j_).max()
            self.hd_band[int(i)] = int(np.digitize(d, WIN_BAND_EDGES))

    def _hd_end(self, done):
        """(HEAD_EVENTS) a step's end: the rounds that ended start their count at the next step; a seat in no whole game
        or mid-game start now has no game number"""
        if not self._hd_live():
            return
        done = np.asarray(done, bool)
        self.hd_clear |= done
        g_ = self._others_arr().shape[1] + 1
        off = ~np.isin(np.repeat(self.game, g_), WIN_KINDS)
        self.hd_gid[done & off] = -1

    def note_event(self, i, name, value=1.0):
        """(HEAD_EVENTS) add value to the column name (HEAD_EVENT_COLS) of the head's events of player i (a number or an
        array of them): for anything a game server's plugin knows that no other hook brings"""
        if not self._hd_live():
            return
        np.add.at(self.hd_ev[:, HEAD_COL[name]], np.asarray(i, np.int64), np.asarray(value, np.float32))

    def note_combat(self, dealt, taken, frag, died):
        """(HEAD_EVENTS) a frame's fighting, a value a player: the damage he dealt to other players and the damage he took
        from anything (points, health and armor together), the frags he made of another player, his deaths of anything.
        step() calls it from its books of the frame; a game server's plugin once a frame from the game's counts"""
        if not self._hd_live():
            return
        e, C = self.hd_ev, HEAD_COL
        e[:, C["dmg_dealt"]] += np.asarray(dealt, np.float32) / 100.0
        e[:, C["dmg_taken"]] += np.asarray(taken, np.float32) / 100.0
        e[:, C["frag"]] += np.asarray(frag, np.float32)
        e[:, C["died"]] += np.asarray(died, np.float32)

    def note_frame(self):
        """(HEAD_EVENTS) once a frame, after the senses (acquired, seen_t; in a group acq2, seen2), the pain sound (pain_t)
        and the weapon in hand (weapon) are set for it, and the state is the frame's: the frame is counted, with an enemy
        noticed in view or not; a fresh pain sound (also an event sound heard); a change of
        the weapon in hand; take-offs and landings from a fall. A spawn or a teleport (over 200 units in a frame) counts
        for none of the last three"""
        if not self._hd_live():
            return
        e, C, n = self.hd_ev, HEAD_COL, self.n
        self.hd_frames += 1.0
        a2_ = getattr(self, "acq2", None)
        acq_ = np.asarray(a2_, bool).any(1) if a2_ is not None else np.asarray(self.acquired, bool)[:n]
        pain_ = np.asarray(self.pain_t)[:n] < 0.5 * DT
        e[:, C["en_seen"]] += acq_
        e[:, C["en_pain"]] += pain_
        e[:, C["en_heard"]] += pain_
        s = self.state
        gr_ = s[:, 6] > 0.5
        pos_ = s[:, :3]
        moved_ = np.linalg.norm(pos_ - self.hd_pos, axis=1) > 200.0
        e[:, C["takeoff"]] += self.hd_gr & ~gr_ & (s[:, 5] > 100) & ~moved_
        e[:, C["fall_land"]] += ~self.hd_gr & gr_ & (self.hd_z0 - pos_[:, 2] >= HEAD_FALL_DROP) & ~moved_
        e[:, C["weapon_change"]] += (self.weapon != self.hd_w) & ~moved_ & (self.hp > 0)
        self.hd_z0 = np.where(gr_ | moved_, pos_[:, 2], self.hd_z0).astype(np.float32)
        self.hd_gr = gr_
        self.hd_pos = pos_.astype(np.float32).copy()
        self.hd_w = np.array(self.weapon, copy=True)

    def head_events(self):
        """(HEAD_EVENTS) [players, N_HEAD_EVENTS] float32: the head's events since the last call (see HEAD_EVENT_COLS;
        en_seen as a share of the frames counted); the count starts again. Zeros with the switch off"""
        if not self._hd_live():
            return np.zeros((self.n, N_HEAD_EVENTS), np.float32)
        out = self.hd_ev.copy()
        out[:, HEAD_COL["en_seen"]] /= np.maximum(self.hd_frames, 1.0)
        out[:, HEAD_COL["en_heard"]] = np.minimum(out[:, HEAD_COL["en_heard"]], HEAD_HEARD_CAP)
        self.hd_ev[:] = 0.0
        self.hd_frames[:] = 0.0
        self.hd_clear[:] = False
        return out

    def _hd_class(self, it):
        """(HEAD_EVENTS) item it's class, the end of its took_* and en_took_* names: mh, ra, ya, rl, rg, lg, pg, gl, small"""
        kind, val, _, _, lab = self.item_def[it]
        if lab in ("MH", "RA", "YA"):
            return lab.lower()
        if kind == "wp" and val in (RL, RG, LG, PG, GL):
            return ("rl", "rg", "lg", "pg", "gl")[(RL, RG, LG, PG, GL).index(val)]
        return "small"

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
        self.v02_bt_now = bt                                 # (RULE_BLIND: how old his belief is, seconds)
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
            cs_ = self._clock_seats()
            if cs_ is not None:                              # (a check: his own clock; a whole-games network: the share of the game left)
                lg_ = len_[grp] if isinstance(len_, np.ndarray) else len_
                lg_ = np.where(cs_[1], GAME_LEN, lg_)
                if self.clock_len is not None:
                    cl_ = np.asarray(self.clock_len, np.float64)
                    lg_ = np.where(cl_ > 0, cl_, lg_)
                left = np.clip(1.0 - cs_[0] / np.maximum(lg_, 1e-3), 0.0, 1.0)
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
        cs_ = self._clock_seats()                            # (a check: his own clock)
        out[:, o + 13] = np.minimum(np.minimum(el, self.round_t[grp] if cs_ is None else cs_[0]), 60.0) / 60.0
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
        air = self._sm_e["air"] if SENSE_MINOR else self.state[opp, 6] < 0.5
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
        if AIM2_SPLIT:                                       # (AIM2_SPLIT) the sight error on the final angles only
            ey, ep, ef = ey + self._a2_dang[:, 0], ep + self._a2_dang[:, 1], ef + self._a2_dang[:, 1]
        lead = np.stack([np.clip(ey / 30.0, -1, 1), np.clip(ey / 2.0, -1, 1), np.clip(ep / 15.0, -1, 1), np.clip(ep / 2.0, -1, 1),
                         np.clip(t / 1.5, 0, 2), np.where(fr < 1.0, np.clip((ef - ep) / 15.0, 0, 1), 1.0)], 1) * on[:, None]
        return np.concatenate([own, lead], 1).astype(np.float32)

    def _extra(self, pos, vel, eye, fdir, up, rot, c, si, yaw, pit, visible):
        """the inputs added after duel_gru_v3 (see N_EXTRA)"""
        n = self.n
        ar = np.arange(n)
        opp = self.foe
        # clock (item timers are 25 s and 35 s) and score of the round (against the best of the others)
        t = np.repeat(self.round_t, self.G)
        best = self.frags_r[self.others].max(1)
        clock = np.stack([np.minimum(t / 120.0, 2.0), np.sin(2 * np.pi * t / 25.0), np.cos(2 * np.pi * t / 25.0),
                          np.sin(2 * np.pi * t / 35.0), np.cos(2 * np.pi * t / 35.0), np.minimum(self.frags_r / 10.0, 2.0),
                          np.minimum(best / 10.0, 2.0),
                          np.clip((self.frags_r - best) / 5.0, -2, 2)], 1)
        if GAME_ON and self.game.any():                      # a whole game or a late round: the clock is the share of the game played
            gm_ = self.game[ar // (self._others_arr().shape[1] + 1)] > 0     # (seconds / 120 held at 2 would stand still from 4:00 on)
            clock[:, 0] = np.where(gm_, t / GAME_LEN, clock[:, 0])
        cs_ = self._clock_seats()
        if cs_ is not None:                                  # a check: each seat on the clock and the score of its own training
            ct_, cg_ = cs_
            clock[:, 0] = np.where(cg_, ct_ / GAME_LEN, np.minimum(ct_ / 120.0, 2.0))
            clock[:, 1], clock[:, 2] = np.sin(2 * np.pi * ct_ / 25.0), np.cos(2 * np.pi * ct_ / 25.0)
            clock[:, 3], clock[:, 4] = np.sin(2 * np.pi * ct_ / 35.0), np.cos(2 * np.pi * ct_ / 35.0)
            if self.clock_score is not None:
                oth_ = self._others_arr()
                adj_ = np.asarray(self.clock_score, np.float32)
                assert adj_.shape == (n, oth_.shape[1] + 1), "clock_score: his own score and each other player's, a seat"
                own_ = self.frags_r + adj_[:, 0]
                best_ = (self.frags_r[oth_] + adj_[:, 1:]).max(1)
                clock[:, 5], clock[:, 6] = np.minimum(own_ / 10.0, 2.0), np.minimum(best_ / 10.0, 2.0)
                clock[:, 7] = np.clip((own_ - best_) / 5.0, -2, 2)
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
        oy = np.radians(self._sm_e["yaw"] if SENSE_MINOR else self.yaw[opp])     # (SENSE_MINOR: as seen, a little off)
        back = np.arctan2(pos[:, 1] - self.state[opp, 1], pos[:, 0] - self.state[opp, 0]) - oy
        if SENSE_MINOR:                                      # (SENSE_MINOR) from where he was seen, as his facing
            back = np.arctan2(pos[:, 1] - self._sm_e["pos"][:, 1], pos[:, 0] - self._sm_e["pos"][:, 0]) - oy
        enemy = np.concatenate([np.eye(NW, dtype=np.float32)[self._sm_e["weapon"] if SENSE_MINOR else self.weapon[opp]][:, OBS_W] * v_,
                                np.stack([np.sin(back), np.cos(back)], 1) * v_,
                                np.minimum((self.dmg_life if self.G == 2 else self.dmg_on[ar, self.slot[opp]])
                                           / 200.0, 2.0)[:, None]], 1)
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
        if RESPAWN_QL and self.rsp_wait[v] > 0:             # (RESPAWN_QL) a body waiting to respawn: the shot stops on it, nothing more
            return
        kf = W_KNOCK[wpn]
        self.w.knockback(int(v), np.asarray(kdir, np.float32) * (1000.0 * kf * dmg / 200.0), int(min(200, dmg)))
        st["dmg_taken"][v] += self._damage(v, dmg)
        self.stats["dmg_h"] += float(dmg) * (self.script[i] == 0)
        self.stats["dmg_from_script"] += float(dmg) * (self.script[v] == 0 and self.script[i] != 0)
        st["attacker"][v] = i
        if wpn == RG and int(i) != int(v):                  # (RAIL_FAR_PAY) the rail hits of this frame: (shooter, victim)
            st.setdefault("rail", []).append((int(i), int(v)))
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

    def _fly_point(self, alive, s, st):
        """(MISSILE_POINT) the projectiles' frame as Quake 3's G_RunMissile, G_MissileImpact, G_BounceMissile and
        G_ExplodeMissile do it (see MISSILE_POINT): a point trace from where it is to where its trajectory puts it at the
        frame's end, then the impact, the bounce, the fuse"""
        owner, slot = alive
        wp = self.rw[owner, slot]
        grav = np.where(wp == GL, 800.0, 0.0).astype(np.float32)
        still = self.rrest[owner, slot]
        grav = np.where(still, 0.0, grav).astype(np.float32)       # TR_STATIONARY: a grenade at rest does not fall
        v0 = self.rv[owner, slot].copy()                           # the velocity at the frame's start
        self.rv[owner, slot, 2] -= grav * DT
        self.rage[owner, slot] += DT
        p0 = self.rp[owner, slot].copy()
        p1r = p0 + v0 * DT                                         # TR_LINEAR, or TR_GRAVITY's exact parabola
        p1r[:, 2] -= 0.5 * grav * DT * DT
        fr = self.w.lines(p0, p1r, mask=PLAYER_MASK if self.sight is None else self.sight)     # a point (mins, maxs 0)
        hitpt = (p0 + (p1r - p0) * fr[:, None]).astype(np.float32)
        fuse = np.array([P_FUSE[int(x)] for x in wp], np.float32)
        timeout = (fuse > 0) & (self.rage[owner, slot] >= fuse)
        wall = fr < 1
        self.rp[owner, slot] = hitpt
        for q in range(len(owner)):
            i, k, wq = owner[q], slot[q], int(wp[q])
            dq = p1r[q] - p0[q]
            dn = float(np.linalg.norm(dq))
            dirq = (dq / dn).astype(np.float32) if dn > 1e-9 else np.array([0.0, 0.0, -1.0], np.float32)
            d_on, ep = None, hitpt[q]
            for v_ in self._mates(int(i)):                         # the first body on the way (the trace's end there,
                if bool(self._seg_box(p0[q:q + 1], hitpt[q:q + 1], s[v_:v_ + 1, :3],          # its box entered 1/8 short)
                                      np.where(self.duck[v_:v_ + 1], TOP_DUCK, TOP))[0]):
                    e_ = self._box_entry(p0[q], hitpt[q], s[v_, :3], TOP_DUCK if self.duck[v_] else TOP)
                    if d_on is None or np.linalg.norm(e_ - p0[q]) < np.linalg.norm(ep - p0[q]):
                        d_on, ep = int(v_), e_
            if d_on is not None or (wall[q] and wq != GL):         # G_MissileImpact: the blast at the end, cut toward trBase
                self.ra[i, k] = False
                ep = self._snap_towards(ep, self.rbase[i, k])
                self._explode(i, wq, ep, d_on, dirq if d_on is not None else None, s, st, back=None)
                continue
            if wall[q]:                                            # G_BounceMissile
                tr = self.w.trace(p0[q], p1r[q], mask=self.sight)
                nrm = np.asarray(tr["normal"], np.float32)
                vh = v0[q].copy()
                # the velocity at "the moment of the hit" as Quake Live takes it: the frame's start plus the part of
                # the frame NOT flown, in whole ms (weaponlab5's 37 bounces after a first one, each put in at the game's
                # place and velocity of the frame before: new place within 0.2 units and new velocity within 1 u/s in
                # all 37, mean 0.2; Quake 3's G_BounceMissile takes the part flown, which the record does not follow)
                vh[2] -= float(grav[q]) * (math.floor(1000.0 * DT * (1.0 - float(fr[q])) + 1e-6) / 1000.0)
                vq = ((vh - 2.0 * float(vh @ nrm) * nrm) * GL_BOUNCE).astype(np.float32)
                if nrm[2] > 0.2 and float(np.linalg.norm(vq)) < 40.0:
                    self.rv[i, k] = 0.0                            # it lies one unit off the surface, cut to whole units
                    self.rrest[i, k] = True                        # (weaponlab5: at rest at -761.0, 513.0 over a floor at 512)
                    self.rp[i, k] = np.trunc(hitpt[q] + nrm)
                else:
                    self.rv[i, k] = vq                             # one unit off the surface; the rest of the frame is lost
                    self.rp[i, k] = hitpt[q] + nrm
                self.rbase[i, k] = self.rp[i, k]
            if timeout[q]:                                         # G_ExplodeMissile: where it is, SnapVector
                self.ra[i, k] = False
                self._explode(i, wq, np.trunc(self.rp[i, k]).astype(np.float32), None, None, s, st, back=None)

    @staticmethod
    def _box_entry(p0, p1, c, top):
        """where the segment p0 -> p1 enters the player box at c (its top `top` above the origin), backed off by
        SURFACE_CLIP_EPSILON (0.125) as the game's trace ends; p0 itself when it starts inside"""
        lo = c + MINS - 0.125
        hi = (c + MAXS + 0.125).copy()
        hi[2] = c[2] + top + 0.125
        d = p1 - p0
        tn = 0.0
        for a_ in range(3):
            if abs(float(d[a_])) < 1e-9:
                continue
            t0, t1 = (lo[a_] - p0[a_]) / d[a_], (hi[a_] - p0[a_]) / d[a_]
            tn = max(tn, float(min(t0, t1)))
        return (p0 + d * min(1.0, tn)).astype(np.float32)

    def _fire_launch(self, i, k, wpn, eye, fd, s, st):
        """(FIRE_QL) player i's plasma ball or grenade into slot k on the frame of the command (self.rv[i, k] its velocity,
        the grenade's lofted): from the game's muzzle, FIRE_FLY of flight by the frame's end. Placed where it is
        FIRE_FLY - DT after the launch so that this frame's flight (below in step) carries it to the end; what the
        stretch before that meets it meets now: the first body on it (where it ends the frame) or, for plasma, a wall.
        A grenade that meets a wall there leaves from the muzzle and bounces in the flight (25 ms late: a wall closer
        than about 24 units)."""
        g_ = 800.0 if wpn == GL else 0.0
        mz = np.trunc(eye + fd * FIRE_MZ).astype(np.float32)        # Quake 3's SnapVector on the muzzle
        v0 = np.trunc(self.rv[i, k]).astype(np.float32)            # ... and on its velocity
        ta = FIRE_FLY - DT
        pa = (mz + v0 * ta).astype(np.float32)
        pa[2] -= 0.5 * g_ * ta * ta
        self.rbase[i, k], self.rrest[i, k], self.rage[i, k] = mz, False, 0.0
        if ta > 0:
            fr = float(self.w.lines(mz[None], pa[None], mask=PLAYER_MASK if self.sight is None else self.sight)[0]) \
                if MISSILE_POINT else float(self.w.trace(mz, pa, mask=self.sight)["fraction"])
            hp_ = (mz + (pa - mz) * fr).astype(np.float32)
            d_on, ep = None, hp_
            for v_ in self._mates(int(i)):
                if bool(self._seg_box(mz[None], hp_[None], s[v_:v_ + 1, :3], np.where(self.duck[v_:v_ + 1], TOP_DUCK, TOP))[0]):
                    e_ = self._box_entry(mz, hp_, s[v_, :3], TOP_DUCK if self.duck[v_] else TOP)
                    if d_on is None or np.linalg.norm(e_ - mz) < np.linalg.norm(ep - mz):
                        d_on, ep = int(v_), e_
            dq = pa - mz
            dirq = (dq / max(1e-6, float(np.linalg.norm(dq)))).astype(np.float32)
            if d_on is not None or (fr < 1 and wpn != GL):           # it meets him, or the plasma a wall: the blast now
                self._explode(i, wpn, self._snap_towards(ep, mz) if MISSILE_POINT else ep, d_on,
                              dirq if d_on is not None else None, s, st, back=None if MISSILE_POINT else dirq)
                return
            if fr < 1:                                               # a grenade at a wall within the first stretch
                self.rp[i, k], self.rv[i, k] = mz, v0
                self.ra[i, k], self.rnew[i, k], self.rw[i, k] = True, False, wpn
                return
        self.rp[i, k] = pa
        self.rv[i, k] = v0 - np.array([0.0, 0.0, g_ * ta], np.float32)
        self.ra[i, k], self.rnew[i, k], self.rw[i, k] = True, False, wpn

    @staticmethod
    def _snap_towards(v, to):
        """Quake 3's SnapVectorTowards: each axis cut to a whole unit ((int), toward zero), plus one where `to` lies above"""
        t_ = np.trunc(np.asarray(v, np.float64))
        return np.where(np.asarray(to, np.float64) <= np.asarray(v, np.float64), t_, t_ + 1.0).astype(np.float32)

    def _explode(self, i, wpn, ep, direct_on, hit_dir, s, st, back=None):
        """projectile of player i (weapon wpn) explodes at ep; direct_on = player hit directly or None;
        back = the way it flew (RL_QL: the blast point is cut to whole units toward where it came from)"""
        if RL_QL and wpn == RL:
            return self._explode_ql(i, ep, direct_on, hit_dir, s, st, back)
        base = W_DMG[wpn]
        victims = []                                      # (player, health damage, knockback points, direction, direct)
        if direct_on is not None:
            victims.append((direct_on, base, base, hit_dir, True))
        for v in [i] + [int(x) for x in self.others[i]]:  # splash on everybody in the group (owner too)
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
            if RESPAWN_QL and self.rsp_wait[v] > 0:         # (RESPAWN_QL) a body waiting to respawn: the blast does nothing to it
                continue
            take = dmg * (SELF_FACTOR if v == i else 1.0)
            kf = W_KNOCK[wpn] if is_direct else (SPLASH_KNOCK_SELF if v == i else SPLASH_KNOCK)
            self.w.knockback(int(v), np.asarray(kdir, np.float32) * (1000.0 * kf * kpts / 200.0), int(min(200, kpts)))
            st["kicked"] = True
            took_s = self._damage(v, take)
            st["dmg_taken"][v] += took_s
            if SELF_DEBT and v == i:
                self.self_debt[v] += took_s
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

    def _explode_ql(self, i, ep, direct_on, hit_dir, s, st, back):
        """(RL_QL) a rocket of player i explodes at ep, as Quake 3's G_MissileImpact / G_RadiusDamage / G_Damage count it
        with Quake Live's numbers (plugins/rjlab.py, 2026-10-15)"""
        wpn = RL
        ep = np.asarray(ep, np.float64).copy()
        if back is not None:                              # SnapVectorTowards(endpos, the start): whole units, toward it
            t_ = np.trunc(ep)                             # (int) v, or (int) v + 1 where the start lies above it
            ep = np.where(np.asarray(back) >= 0, t_, t_ + 1.0)
        ep = ep.astype(np.float32)
        victims = []                                      # (player, damage points, push points, direction, direct)
        if direct_on is not None:                         # a direct hit: 100, pushed by 100 x 0.9 (W_KNOCK)
            victims.append((direct_on, float(W_DMG[wpn]), float(W_DMG[wpn] * W_KNOCK[wpn]), hit_dir, True))
        R = P_RADIUS[wpn]
        box_ = RL_BOX_PT if MISSILE_POINT else RL_BOX
        for v in [i] + [int(x) for x in self.others[i]]:  # (RL_QL) splash on everybody in the group, the owner too
            if v == direct_on:
                continue
            c = s[v, :3]
            hi_ = c + MAXS + box_
            if self.duck[v]:
                hi_ = hi_.copy()
                hi_[2] = c[2] + TOP_DUCK + box_
            near = np.clip(ep, c + MINS - box_, hi_)
            d = float(np.linalg.norm(ep - near))
            if d < R and (self.w.trace(ep, c, mask=self.sight)["fraction"] >= 0.999
                          or (GL_QL and any(self.w.trace(ep, c + np.array([ox_, oy_, 0.0], np.float32), mask=self.sight)["fraction"] >= 0.999
                                            for ox_, oy_ in ((15.0, 15.0), (15.0, -15.0), (-15.0, 15.0), (-15.0, -15.0))))):
                f_ = 1.0 - d / R
                kdir = (c - ep).astype(np.float32)
                kdir[2] += 24.0
                kn = float(np.linalg.norm(kdir))
                kdir = kdir / kn if kn > 1e-3 else np.array([0, 0, 1.0], np.float32)
                kp = int(RL_KNOCK_BASE * f_ * (RL_KNOCK_SELF if v == i else RL_KNOCK_OTHER))
                victims.append((v, float(int(P_SPLASH[wpn] * f_)), float(kp), kdir, False))
        for v, dmg, kpts, kdir, is_direct in victims:
            if RESPAWN_QL and self.rsp_wait[v] > 0:         # (RESPAWN_QL) a body waiting to respawn: the blast does nothing to it
                continue
            take = float(max(1, int(dmg * SELF_FACTOR) if v == i else int(dmg)))     # G_Damage: at least 1
            if kpts > 0:
                self.w.knockback(int(v), np.asarray(kdir, np.float32) * (5.0 * kpts), int(min(200, kpts)))
            st["kicked"] = True
            took_s = self._damage(v, take)
            st["dmg_taken"][v] += took_s
            if SELF_DEBT and v == i:
                self.self_debt[v] += took_s
            if v != i:
                st["attacker"][v] = i
                self._book(st, i, v, take, wpn)
                self.stats["dmg_h"] += float(take) * (self.script[i] == 0)
                self.stats["dmg_from_script"] += float(take) * (self.script[v] == 0 and self.script[i] != 0)
                self.stats["dmg"] += take
                self.stats[WEAPONS[wpn] + "_hits"] += int(self.script[i] == 0)
                if is_direct:
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
            ph = (self.round_t[idx // self.G] / DT).astype(np.int64)
            if self.sc_style == 1:                           # still
                self.sc_dir[idx], self.sc_fwd[idx], self.sc_jump[idx] = 0, 0, False
            else:                                            # strafe left/right, switching every 0.8 s
                side = np.where((ph // 32) % 2 == 0, 1, -1)
                if self.sc_style == 2:                       # slow: moves one frame in three (~1/3 run speed)
                    side = np.where(ph % 3 == 0, side, 0)
                self.sc_dir[idx], self.sc_fwd[idx] = side, 0
                self.sc_jump[idx] = self.sc_style == 4
        fighter = self.script[idx] == 2
        opp = self.foe[idx]
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
            z = self.lab_zone[idx // self.G]
            pos = s[idx, :3]
            near = t1 & ~((z[:, 0] + 120 <= pos[:, 0]) & (pos[:, 0] <= z[:, 2] - 120) &
                          (z[:, 1] + 120 <= pos[:, 1]) & (pos[:, 1] <= z[:, 3] - 120))
            dx, dy = (z[:, 0] + z[:, 2]) / 2 - pos[:, 0], (z[:, 1] + z[:, 3]) / 2 - pos[:, 1]
            yr_ = np.radians(self.yaw[idx])
            f_, l_ = dx * np.cos(yr_) + dy * np.sin(yr_), -dx * np.sin(yr_) + dy * np.cos(yr_)
            out[:, 0] = np.where(near, np.sign(np.where(np.abs(f_) > 40, f_, 0)).astype(np.int64) + 1, out[:, 0])
            out[:, 1] = np.where(near, -np.sign(np.where(np.abs(l_) > 40, l_, 0)).astype(np.int64) + 1, out[:, 1])
            out[:, 2] = np.where(t1, self.lab_jump[idx // self.G] & ~near, out[:, 2])   # no jumping while walking back in
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
            bk_ = True                                       # (BLIND_BRAIN) a life on the brain: its place (none: no "near" nor "way")
            if BLIND_BRAIN:
                bb_ = self._blind_src([i])
                if bb_ is not None:
                    B, bk_ = bb_[1][0], bool(bb_[2][0])
            how = 0
            if np.linalg.norm(L - s[i, :3]) < BLIND_JUMP:
                how = 1
            elif bk_ and np.linalg.norm(L - B) < BLIND_NEAR:
                how = 2
            elif len(self.spam_places) and float(np.linalg.norm(self.spam_places - L, axis=1).min()) < BLIND_PLACES:
                how = 4                                      # (a place the pros fire at with nobody in view)
            elif bk_ and R is not None:
                nb, nl, me = (int(x) for x in R.locate(np.stack([B, L, s[i, :3]]).astype(np.float32)))
                if np.linalg.norm(R.nodes[nl] - L) < BLIND_WAY_R:
                    tb = R.from_node(nb)
                    by = float(self.seen_t[i]) + float(np.linalg.norm(L - eye[k])) / P_SPEED[RL] + BLIND_SLACK
                    if tb[nl] <= by and (tb[nl] + R.from_node(nl)[me] <= tb[me] + BLIND_SLACK
                                         or bool((tb[nl] + R.T[:len(self.route_goal), nl] <= R.T[:len(self.route_goal), nb] + BLIND_SLACK).any())):
                        how = 3
            if not how and BLIND_AHEAD:                      # (BLIND_AHEAD) near where the brain says he will be in 1, 2 or 4 s
                fu_ = self._blind_fut([i])
                if fu_ is not None and bool(fu_[0][0]) and float(np.linalg.norm(fu_[1][0] - L[None, :], axis=1).min()) < BLIND_NEAR:
                    how = 5
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
    # ---------------------------------------------------------------- the pay split by term (PAY_SPLIT; record only)
    def _pt_begin(self):
        """(PAY_SPLIT) the frame's books: per player and term, the pay booked so far; the reward at the last mark"""
        if not PAY_SPLIT:
            return
        n = self.n
        self.pt = np.zeros((n, len(PAY_TERMS)), np.float64)
        self.pt_sub = np.zeros(n, np.float64)               # booked by name since the last mark
        self.pt_last = np.zeros(n, np.float64)
        g_ = self._others_arr().shape[1] + 1
        self.pt_gm = (self.game[np.arange(n) // g_] > 0) if GAME_ON else np.zeros(n, bool)

    def _ps(self, name, reward):
        """(PAY_SPLIT) a mark: what the reward gained since the last one, less what was booked by name, goes to `name`"""
        if not PAY_SPLIT:
            return
        r_ = np.asarray(reward[:self.n], np.float64)
        self.pt[:, PT_IX[name]] += r_ - self.pt_last - self.pt_sub
        self.pt_last = r_.copy()
        self.pt_sub[:] = 0.0

    def _pt(self, name, idx, val):
        """(PAY_SPLIT) a pay booked where it is paid: players idx (an index or an array), value(s) val"""
        if not PAY_SPLIT:
            return
        idx = np.atleast_1d(np.asarray(idx, np.int64))
        val = np.broadcast_to(np.asarray(val, np.float64), idx.shape)
        np.add.at(self.pt[:, PT_IX[name]], idx, val)
        np.add.at(self.pt_sub, idx, val)

    def _pt_end(self, info):
        """(PAY_SPLIT) the frame's split into info and the counters (his counted seats)"""
        if not PAY_SPLIT:
            return
        info["pay_terms"] = self.pt.astype(np.float32)
        P_ = self.stats.get("pay_terms")
        if P_ is None:
            P_ = self.stats["pay_terms"] = np.zeros((3, len(PAY_TERMS)))
        c_ = self._counted(np.arange(self.n)) & (self.script[:self.n] == 0)
        P_[0] += self.pt[c_].sum(0)
        P_[1] += self.pt[c_ & self.pt_gm].sum(0)
        P_[2] += np.abs(self.pt[c_]).sum(0)

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
        self.ws_tab, self.ws_scale = None, 0.0               # (WIN_SHADOW) the same table, recorded only
        self.ws_p = np.full(self.M, 0.5, np.float64)
        self.win_shadow = np.zeros(self.n, np.float32)
        self.ws_flat = np.zeros(self.n, np.float32)
        if GAME_ON:
            self.stats["games"] = np.zeros(len(GAMES_COLS))
        self.g_ot = np.zeros(self.M, np.int64) if OVERTIME else None     # (OVERTIME) overtime periods begun in match m's game
        if GAME_ON and OVERTIME:
            self.stats["overtime"] = np.zeros(len(OT_COLS))
        if GAME_ON and (WIN_PAY or WIN_SHADOW):
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
            if WIN_PAY:
                self.win_tab = (p_, float(left_[1]), D_)
                self.win_scale = 1.0 / (float(p_[-1, D_ + 1]) - 0.5)    # a frag at 0:0 with ten minutes left = a frag of today
            if WIN_SHADOW:
                self.ws_tab = (p_, float(left_[1]), D_)
                self.ws_scale = 1.0 / (float(p_[-1, D_ + 1]) - 0.5)
                self.stats["win_shadow"] = np.zeros(len(WS_COLS))
        # (WIN_W / FADE_V, v0.5.1) the blend's own chance, kept up in every game whatever the switches (they are live)
        self.wb_tab, self.wb_scale = None, 0.0
        self.wb_p = np.full(self.M, 0.5, np.float64)
        self.wb_raw = np.zeros(self.n, np.float64)           # this frame's win part at G = 1, per player
        self.wb_cb = np.zeros(self.n, np.float64)            # this frame's combat pay (frags, deaths, damage), per player
        self.wb_gm = np.zeros(self.n, bool)                  # this frame: a game under way in his match
        self.wb_left = np.zeros(self.M)                      # the seconds left the blend's chance read this frame, per match
        self.wsh_prev = np.full(self.M, np.nan)              # (WIN_SHAPE_K, v0.6.1) the first seat's PSI the frame before (nan: not kept)
        self.wsh_now = np.full(self.M, np.nan)               # ... and this frame's (for a round cut before the game's end)
        self.wsh_pay = np.zeros(self.n, np.float64)          # ... this frame's shaping, per player
        if GAME_ON:
            f_ = os.environ.get("WIN_CHANCE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "win_chance.json")
            if os.path.exists(f_):
                with open(f_, encoding="utf-8") as fh_:
                    wc_ = json.load(fh_)
                p_ = np.array(wc_["p"], np.float64)
                left_, d_ = np.array(wc_["left_s"], np.float64), np.array(wc_["diffs"], np.int64)
                D_ = int(d_[-1])
                assert p_.shape == (len(left_), len(d_)) and np.array_equal(d_, np.arange(-D_, D_ + 1)), "win_chance.json: the table's shape"
                assert left_[0] == 0.0 and np.allclose(np.diff(left_), left_[1]) and abs(left_[-1] - GAME_LEN) < 1e-6, "win_chance.json: the time steps"
                assert np.abs(p_ + p_[:, ::-1] - 1.0).max() < 1e-9, "win_chance.json: p(-d) must be 1 - p(d)"
                assert np.array_equal(p_[0], np.where(d_ > 0, 1.0, np.where(d_ < 0, 0.0, 0.5))), "win_chance.json: 1 / 0.5 / 0 at the limit"
                self.wb_tab = (p_, float(left_[1]), D_)
                self.wb_scale = 1.0 / (float(p_[-1, D_ + 1]) - 0.5)
                self.stats["win_blend"] = np.zeros(len(WB_COLS))

    def _wb_on(self):
        """(WIN_W / FADE_V) is the blend on in this frame's games?"""
        if not (GAME_ON and (WIN_W > 0 or FADE_V > 0)):
            return False
        if self.wb_tab is None:
            raise RuntimeError("WIN_W / FADE_V: no win_chance.json (or no whole games: GAME_P / LATE_P)")
        return True

    def _wb_chance(self, m, left):
        """(WIN_W) the blend's chance for the first seat of matches m with `left` seconds to play: W(lead, left) of
        win_chance.json, and with WIN_STACK the stack term on it (see WIN_STACK): clip(W + PHI, 0, 1), PHI = (p_next - 0.5)
        x (W(lead + 1) - W(lead - 1)) x (1 - exp(-left / WIN_TAU)), p_next = sigmoid(WIN_PA x f(stack difference) +
        WIN_PRL x dRL + WIN_PLG x dLG + WIN_PRG x dRG), the true stacks (health + armor) and the big weapons owned (-1 / 0 / 1)"""
        m = np.atleast_1d(np.asarray(m, np.int64))
        g_ = self._others_arr().shape[1] + 1
        a_, b_ = m * g_, m * g_ + 1
        d_ = (self.frags_r[a_] - self.frags_r[b_]).astype(np.float64)
        left = np.broadcast_to(np.asarray(left, np.float64), m.shape)
        W_ = self._win_p(d_, left, tab=self.wb_tab)
        if not WIN_STACK:
            return W_
        pn_ = self._wb_pnext(a_, b_)
        dW_ = self._win_p(d_ + 1.0, left, tab=self.wb_tab) - self._win_p(d_ - 1.0, left, tab=self.wb_tab)
        return np.clip(W_ + (pn_ - 0.5) * dW_ * (1.0 - np.exp(-np.maximum(left, 0.0) / WIN_TAU)), 0.0, 1.0)

    def _wb_pnext(self, a_, b_):
        """(WIN_STACK, WIN_SHAPE_K) the chance that seats a_ score the next frag against seats b_: sigmoid(WIN_PA x f(stack
        difference) + WIN_PRL x dRL + WIN_PLG x dLG + WIN_PRG x dRG), the true stacks (health + armor) and the big weapons
        owned (-1 / 0 / 1); a dead player as his respawn will have him"""
        dead_ = (self.hp <= 0) | (self.rsp_wait > 0)          # (a dead player as his respawn will have him: the spawn's
        st_ = lambda i_: np.where(dead_[i_], SPAWN_HP, np.asarray(self.hp[i_], np.float64) + np.asarray(self.armor[i_], np.float64))
        ds_ = st_(a_) - st_(b_)                               # health, no armor, no big weapon; the fit has both alive only)
        f_ = np.tanh(ds_ / WIN_PS) if WIN_PS > 0 else ds_ / 100.0
        hv_ = lambda w_: np.where(dead_[a_], 0.0, self.has[a_, w_].astype(np.float64)) - np.where(dead_[b_], 0.0, self.has[b_, w_].astype(np.float64))
        z_ = WIN_PA * f_ + WIN_PRL * hv_(RL) + WIN_PLG * hv_(LG) + WIN_PRG * hv_(RG)
        return 1.0 / (1.0 + np.exp(-z_))

    def _wsh_psi(self, m, left):
        """(WIN_SHAPE_K) the shaping's potential for the first seat of matches m with `left` seconds to play:
        (p_next - 0.5) x (1 - exp(-left / WIN_SHAPE_TAU)); the second seat's is minus it"""
        m = np.atleast_1d(np.asarray(m, np.int64))
        g_ = self._others_arr().shape[1] + 1
        left = np.broadcast_to(np.asarray(left, np.float64), m.shape)
        return (self._wb_pnext(m * g_, m * g_ + 1) - 0.5) * (1.0 - np.exp(-np.maximum(left, 0.0) / WIN_SHAPE_TAU))

    def _wsh_start(self, m, left):
        """(WIN_SHAPE_K) a game begins in match m with `left` seconds to play: its PSI there (with the start's stacks), or
        nothing kept with the shaping off"""
        self.wsh_prev[m] = float(self._wsh_psi(m, left)[0]) if WIN_SHAPE_K > 0 and self.wb_tab is not None else np.nan

    def _wsh_cut(self, m):
        """(WIN_SHAPE_K) match m's round ends here with its game not played to its end: the end is terminal, so its PSI is 0
        there and this frame's shaping is k x (0 - PSI before), not k x (g PSI now - PSI before): take g k PSI now back"""
        if not (WIN_SHAPE_K > 0) or not np.isfinite(self.wsh_now[m]):
            return
        g_ = self._others_arr().shape[1] + 1
        c_ = WIN_SHAPE_K * WIN_SHAPE_G * float(self.wsh_now[m])
        a_, b_ = m * g_, m * g_ + 1
        self.wsh_pay[a_] -= c_                               # (paid after the blend with the frame's shaping)
        self.wsh_pay[b_] += c_
        S_ = self.stats.get("win_shape")
        if S_ is not None and c_ != 0.0:
            for q_, x_ in ((a_, -c_), (b_, c_)):
                if self._counted(np.array([q_]))[0] and self.script[q_] == 0:
                    S_ += (0.0, x_, abs(x_), x_, 1.0)
        self.wsh_now[m] = np.nan

    def _wsh_pay(self, reward, info):
        """(WIN_SHAPE_K) this frame's shaping into the pay (after the blend: neither FADE_V nor WIN_W touch it), its counters"""
        gm = self.wb_gm
        y_ = np.where(gm, self.wsh_pay, 0.0)
        reward += y_.astype(reward.dtype)
        info["win_shape"] = y_.astype(np.float32)
        if PAY_SPLIT:
            self.pt[gm, PT_IX["win_part"]] += y_[gm]
        S_ = self.stats.get("win_shape")
        if S_ is None:
            S_ = self.stats["win_shape"] = np.zeros(len(WSH_COLS))
        c_ = gm & self._counted(np.arange(self.n)) & (self.script[:self.n] == 0)
        S_ += (float(c_.sum()), float(y_[c_].sum()), float(np.abs(y_[c_]).sum()), 0.0, 0.0)

    def _wb_blend(self, reward, info):
        """(WIN_W / FADE_V) the frame's pay in the games cut into combat, win and other and paid by the blend (see WIN_W)"""
        gm = self.wb_gm
        on = self._wb_on()
        WB = self.stats.get("win_blend")
        if not gm.any() or WB is None:
            return
        r64 = np.asarray(reward, np.float64)
        oth = r64 - self.wb_cb
        new = r64
        if on:
            w_, v_, g_ = float(WIN_W), float(FADE_V), float(WIN_GAIN)
            paid_ = w_ * g_ * self.wb_raw
            new = np.where(gm, (1.0 - v_) * oth + (1.0 - w_) * self.wb_cb + paid_, r64)
            reward[gm] = new[gm]
            if v_ > 0 or WIN_LONG:                           # (WIN_LONG) the win part into r_long too
                rl_ = np.asarray(self.r_long[gm], np.float64) * (1.0 - v_) + (paid_[gm] if WIN_LONG else 0.0)
                self.r_long[gm] = rl_.astype(self.r_long.dtype)
            info["win_blend"] = np.stack([self.wb_raw, self.wb_cb, np.where(gm, paid_, 0.0)], 1).astype(np.float32)
            if PAY_SPLIT:                                    # the terms scaled with the pay they stand for
                cb_ix = [PT_IX[k_] for k_ in ("frag", "death", "dmg_dealt", "dmg_taken")]
                sc_ = np.full(len(PAY_TERMS), 1.0 - v_)
                sc_[cb_ix] = 1.0 - w_
                sc_[PT_IX["win_part"]] = 0.0
                self.pt[gm] *= sc_
                self.pt[gm, PT_IX["win_part"]] = paid_[gm]
        c_ = gm & self._counted(np.arange(self.n)) & (self.script[:self.n] == 0)
        WB += (float(c_.sum()), float(self.wb_raw[c_].sum()), float(np.abs(self.wb_raw[c_]).sum()), float(self.wb_cb[c_].sum()),
               float(np.abs(self.wb_cb[c_]).sum()), float(np.abs(oth[c_]).sum()), float(np.abs(np.asarray(new)[c_]).sum()),
               float(c_.sum()) if on else 0.0)

    def _win_p(self, d, left, tab=None):
        """the chance of winning the game for a player d frags ahead with `left` seconds to play (win_chance.json: a
        straight line between its time steps; a lead beyond the table counts as its last column)"""
        p, step, D = self.win_tab if tab is None else tab
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
        return (float(kp[0]) * max(0.0, 1.0 - GAME_P - LATE_P - MOMENT_P) / self.round_len, float(kp[0]) * GAME_P / GAME_LEN,
                float(kp[0]) * LATE_P / LATE_LEN, float((kp[1:] / np.array([15.0, 15.0, self.move_len])).sum()))

    def _game_draw(self, m):
        """is match m's new round a whole game or a late round (by their shares of the playing time)? Then it begins here"""
        if not self._game_ok():
            return False
        if MOMENTS:                                          # (... or a round begun from a saved moment)
            return self._moment_draw(m)
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
        self.ws_p[m] = 0.5
        self.wb_p[m] = 0.5
        if OVERTIME:
            self.g_ot[m] = 0
        self.script[q], self.goal[q], self.frags_r[q], self.snd_t[q] = 0, -1, 0, 99.0
        self.hold_ahead[q] = False
        self.g_win[q], self.g_flat[q] = 0.0, 0.0
        for i in q:
            self.load_sets[int(i)] = ()                     # the game's spawn: machine gun and gauntlet
        self._spawn(int(q[0]), avoid=None)
        self._spawn(int(q[1]), avoid=self.w.state()[int(q[0]), :3])
        if WIN_STACK and self.wb_tab is not None:            # (WIN_STACK) the blend's chance at the start with the spawned stacks
            self.wb_p[m] = float(self._wb_chance(m, GAME_LEN)[0])
        self.item_up[m], self.item_t[m] = True, 0.0
        self.contest_t[m] = -1.0
        if STAGGER_START and not late and self.stag_first[m]:      # (STAGGER_START) the match's first whole game: a drawn point of its clock
            t_ = int(self.stag_rng.integers(0, GAME_FRAMES + 1))
            self.g_tick[m], self.round_t[m] = t_, np.float32(t_ * DT)
            if self.win_tab is not None:
                self.g_p[m] = float(self._win_p(np.zeros(1), np.array([GAME_LEN - t_ * DT]))[0])
            if self.ws_tab is not None:
                self.ws_p[m] = float(self._win_p(np.zeros(1), np.array([GAME_LEN - t_ * DT]), tab=self.ws_tab)[0])
            if self.wb_tab is not None:
                self.wb_p[m] = float(self._wb_chance(m, GAME_LEN - t_ * DT)[0])
            self.stats["stagger"] += (1.0, t_ * DT)
        self._wsh_start(m, GAME_LEN - int(self.g_tick[m]) * DT)     # (WIN_SHAPE_K) PSI at the start, with the spawned stacks
        if not late:
            self.stag_first[m] = False
        self.stats["games"][15] += 1
        self._hd_game(q, 2 if late else 1)                  # (HEAD_EVENTS) the win label's game number
        if MOMENTS:
            self._moment_game(m, late)
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
        if EN_STACK:                                         # (B-257) drawn stacks: nothing is known of them
            self._es_set(np.array(q), slice(None), spawn=False)
        self.g_p[m] = float(self._win_p(d, GAME_LEN - LATE_AT)) if self.win_tab is not None else 0.5
        if self.ws_tab is not None:
            self.ws_p[m] = float(self._win_p(d, GAME_LEN - LATE_AT, tab=self.ws_tab))
        if self.wb_tab is not None:
            self.wb_p[m] = float(self._wb_chance(m, GAME_LEN - LATE_AT)[0])
        self._wsh_start(m, GAME_LEN - LATE_AT)               # (WIN_SHAPE_K) PSI with the drawn stacks
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
        if WIN_SHADOW:
            self.win_shadow[:] = 0.0
        self.wb_raw[:] = 0.0
        self.wb_gm[:] = False
        self.wsh_pay[:] = 0.0
        gm = np.nonzero(self.game > 0)[0]
        if not len(gm):
            return
        self.g_tick[gm] += 1
        self.round_t[gm] = (self.g_tick[gm] * DT).astype(np.float32)    # (a sum of float32 steps is frames off after ten minutes)
        if OVERTIME:                                         # (OVERTIME) past the limit: the game's last OT_LEN seconds again
            ov_ = gm[self.g_tick[gm] > GAME_FRAMES]
            if len(ov_):
                self.round_t[ov_] = (self._ot_fold(self.g_tick[ov_]) * DT).astype(np.float32)
                self.stats["overtime"][4] += len(ov_)
        G = self.stats["games"]
        G[13] += int((self.game[gm] == 1).sum())
        G[14] += int((self.game[gm] == 2).sum())
        if self.wb_tab is not None:                          # (WIN_W / FADE_V) the win part at G = 1, kept up whatever the switches
            gb_ = self._others_arr().shape[1] + 1
            ab_, bb_ = gm * gb_, gm * gb_ + 1
            self.wb_gm[ab_], self.wb_gm[bb_] = True, True
            lb_ = GAME_LEN - self.g_tick[gm] * DT
            if OVERTIME:                                     # (the period's last frame: 0 s left, _ot_left)
                lb_ = np.where(self.g_tick[gm] > GAME_FRAMES, self._ot_left(self.g_tick[gm], self.round_t[gm]), lb_)
            self.wb_left[:] = 0.0
            self.wb_left[gm] = lb_
            pb_ = self._wb_chance(gm, lb_)
            yb_ = self.wb_scale * (pb_ - self.wb_p[gm])
            self.wb_p[gm] = pb_
            self.wb_raw[ab_], self.wb_raw[bb_] = yb_, -yb_
            self.wsh_now[:] = np.nan
            if WIN_SHAPE_K > 0:                              # (WIN_SHAPE_K, v0.6.1) the shaping: k (g PSI - PSI before), zero-sum
                ps_ = self._wsh_psi(gm, lb_)
                pv_ = self.wsh_prev[gm]
                y_ = np.where(np.isfinite(pv_), WIN_SHAPE_K * (WIN_SHAPE_G * ps_ - np.nan_to_num(pv_)), 0.0)   # (opened here: from now on)
                self.wsh_prev[gm], self.wsh_now[gm] = ps_, ps_
                self.wsh_pay[ab_], self.wsh_pay[bb_] = y_, -y_
            else:
                self.wsh_prev[:] = np.nan                    # (off: forgotten; opened again it reads PSI afresh)
        if self.ws_tab is not None:                          # (WIN_SHADOW) what WIN_PAY would pay this frame: recorded, never paid
            gw_ = self._others_arr().shape[1] + 1
            aw_, bw_ = gm * gw_, gm * gw_ + 1
            lw_ = GAME_LEN - self.g_tick[gm] * DT
            if OVERTIME:
                lw_ = np.where(self.g_tick[gm] > GAME_FRAMES, self._ot_left(self.g_tick[gm], self.round_t[gm]), lw_)
            pw_ = self._win_p(self.frags_r[aw_] - self.frags_r[bw_], lw_, tab=self.ws_tab)
            yw_ = self.ws_scale * (pw_ - self.ws_p[gm])
            self.ws_p[gm] = pw_
            self.win_shadow[aw_], self.win_shadow[bw_] = yw_, -yw_
            WS_ = self.stats["win_shadow"]
            for q_ in (aw_, bw_):
                c_ = q_[self._counted(q_) & (self.script[q_] == 0)]
                WS_ += (float(self.win_shadow[c_].sum()), float(np.abs(self.win_shadow[c_]).sum()), float(self.ws_flat[c_].sum()),
                        float(np.abs(self.ws_flat[c_]).sum()), float(len(c_)), float((self.ws_flat[c_] != 0).sum()))
        if self.win_tab is None:
            return
        g_ = self._others_arr().shape[1] + 1
        a_, b_ = gm * g_, gm * g_ + 1
        left_ = GAME_LEN - self.g_tick[gm] * DT
        if OVERTIME:                                         # (OVERTIME) in a period: the seconds left in it
            left_ = np.where(self.g_tick[gm] > GAME_FRAMES, self._ot_left(self.g_tick[gm], self.round_t[gm]), left_)
        p = self._win_p(self.frags_r[a_] - self.frags_r[b_], left_)
        pay = self.win_scale * (p - self.g_p[gm])
        self.g_p[gm] = p
        if self._wb_on():                                    # (WIN_W / FADE_V) the blend pays the win part in its place
            return
        reward[a_] += pay
        reward[b_] -= pay
        self.win_pay[a_], self.win_pay[b_] = pay, -pay
        self.g_win[a_] += pay
        self.g_win[b_] -= pay

    def _ot_left(self, tick, round_t):
        """(OVERTIME, WIN_PAY / WIN_SHADOW) the seconds left in the period for frames past the limit: the folded clock's, except
        on a period's last frame (tick GAME_FRAMES + k * OT_FRAMES), where the fold shows the next period's start (120 s) but
        the period is over: 0 there, so a game decided in overtime pays its outcome (1 / 0, a draw 0.5) on its last frame
        (until 2026-10-24 it read 120 s there: the last frame paid the wrong amount, even the wrong sign)"""
        last_ = (np.asarray(tick, np.int64) - GAME_FRAMES) % OT_FRAMES == 0
        return np.where(last_, 0.0, GAME_LEN - np.asarray(round_t).astype(np.float64))

    def _ot_fold(self, tick):
        """(OVERTIME) a game's frame past the limit as the plugin shows it: the last OT_LEN seconds again, period after
        period (frame GAME_FRAMES + k * OT_FRAMES, k >= 1, shows the period's start)"""
        return GAME_FRAMES - OT_FRAMES + (np.asarray(tick, np.int64) - GAME_FRAMES) % OT_FRAMES

    def _ot_ends(self, ends):
        """(OVERTIME) of the matches at their limit, a game with the score level goes on for another period (up to OT_CAP);
        a game in a period goes on to its end; the rest end"""
        OS = self.stats["overtime"]
        keep = []
        for m in ends:
            m = int(m)
            if self.game[m] not in OT_KINDS or (MOMENTS and int(self.g_end[m]) != GAME_FRAMES):
                keep.append(m)
                continue
            if self.g_tick[m] < GAME_FRAMES + OT_FRAMES * int(self.g_ot[m]):
                continue                                     # (in a period)
            q = self._seats(m)
            if self.frags_r[int(q[0])] == self.frags_r[int(q[1])] and self.g_ot[m] < OT_CAP:
                OS[0] += int(self.g_ot[m] == 0)
                OS[1] += 1
                self.g_ot[m] += 1
                continue
            keep.append(m)
        return np.array(keep, np.int64)

    def _ot_over(self, m):
        """(OVERTIME) a game that went to overtime is over: into the counters"""
        if self.g_ot[m] <= 0:
            return
        OS = self.stats["overtime"]
        q = self._seats(m)
        d = float(self.frags_r[int(q[0])] - self.frags_r[int(q[1])])
        OS[2 if d != 0 else 3] += 1
        if m * 2 >= self.M:
            OS[5] += 1
            OS[6 if d > 0 else 7 if d == 0 else 8] += 1
        self.g_ot[m] = 0

    def _game_end(self, m):
        """the whole game or late round of match m is over, at the limit (level is a draw: no overtime): into the counters"""
        self._hd_result(m)                                   # (HEAD_EVENTS) the win label: the band of the final margin
        if OVERTIME:
            self._ot_over(m)
        if MOMENTS and self.game[m] > 2:                     # (a round begun from a saved moment: its own counters)
            return self._moment_end(m)
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

    # ---------------------------------------------------------------- the pros' spawn openings (OPENINGS)
    def _open_init(self, bsp):
        """(OPENINGS) per spawn point of the map: the first pickup the opening names and the order of the second ones
        (open_first, open_rank by intention; open_kind 1), or the general rule (open_kind 0); per player the books of his
        life: the spawn point (-1: none), the step he is at (0 the first pickup, 1 the second, 2 over)"""
        n, S, K = self.n, len(self.spawns), HOLD_INTENT
        self.op_sp = np.full(n, -1, np.int64)
        self.op_st = np.full(n, 2, np.int64)
        self.op_lt = np.full(n, 1e9, np.float32)            # his life's clock at the last look (a new life: it has not gone on)
        self.op_av = np.zeros(n, np.int64)                  # the avoid rule in this life: 0 not, 1 changed the second pickup, 2 left none
        self.op_big = np.zeros(n, bool)                     # a big pickup in this life (the counter's)
        self.op_lab = np.zeros(n, np.int64)                 # the opening's label of this frame (0: it names nothing)
        self.stats["open"] = np.zeros(len(OPEN_COLS))
        self.open_first = np.zeros(S, np.int64)
        self.open_rank = np.full((S, K), 99, np.int64)
        self.open_kind = np.zeros(S, np.int64)
        self.open_info = [None] * S                         # (for the reader: the pros' name of the spawn point, lives, the steps)
        f_ = os.path.join(os.environ.get("OPEN_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_spawn_openings"),
                          os.path.splitext(os.path.basename(bsp))[0].lower() + ".json")
        if self.route is None or not os.path.exists(f_):
            return
        with open(f_, encoding="utf-8") as fh_:
            d_ = json.load(fh_)
        lab_of = {}                                          # the file's item -> his intention, by its place (0: none he can name)
        for nm_, p_ in (d_.get("items") or {}).items():
            dd_ = [float(np.linalg.norm(self.item_pos[it_] - np.array(p_, np.float32))) for it_ in self.route_item]
            if dd_ and min(dd_) < OPEN_ITEM_R and self.route_goal[int(np.argmin(dd_))] in INTENTS[1:EN_INTENT]:
                lab_of[nm_] = INTENTS.index(self.route_goal[int(np.argmin(dd_))])
        best = {}
        for sp_ in d_.get("spawns") or []:                   # the pros' start -> the map's spawn point (the nearest start wins it)
            b_ = sp_.get("bsp")
            if not b_ or float(b_.get("distance", 1e9)) > OPEN_SPAWN_R:
                continue
            dk_ = np.linalg.norm(self.spawns - np.array(b_["pos"], np.float32)[None, :], axis=1)
            k_ = int(dk_.argmin())
            if dk_[k_] < OPEN_AT and (k_ not in best or float(b_["distance"]) < float(best[k_]["bsp"]["distance"])):
                best[k_] = sp_
        for k_, sp_ in best.items():
            W = {}                                           # (first,) and (first, second) as he can name them -> lives

            def walk(node, pre):
                c_ = lab_of.get(node["items"][-1], 0)
                seq = pre
                if c_ and c_ not in pre:
                    seq = pre + (c_,)
                    W[seq] = W.get(seq, 0) + int(node["lives"])
                if len(seq) < 2:
                    for ch_ in node.get("then") or []:
                        walk(ch_, seq)

            for top_ in sp_.get("openings") or []:
                walk(top_, ())
            lives = int(sp_.get("lives", 0))
            firsts = sorted([(v_, q_[0]) for q_, v_ in W.items() if len(q_) == 1], reverse=True)
            self.open_info[k_] = dict(name=sp_.get("name"), lives=lives, kind=0, first=None, seconds=[])
            if lives < OPEN_MIN_LIVES or not firsts or firsts[0][0] < OPEN_MIN_SHARE * lives:
                continue
            f1 = firsts[0][1]
            order = [q_[1] for v_, q_ in sorted([(v_, q_) for q_, v_ in W.items() if len(q_) == 2 and q_[0] == f1], reverse=True)]
            order += [c_ for v_, c_ in firsts[1:]]           # then the spawn's other openings: their first pickups,
            order += [q_[1] for v_, q_ in sorted([(v_, q_) for q_, v_ in W.items() if len(q_) == 2 and q_[0] != f1], reverse=True)]   # their second ones
            seen_ = [f1]
            for c_ in order:
                if c_ not in seen_:
                    self.open_rank[k_, c_] = len(seen_) - 1
                    seen_.append(c_)
            self.open_first[k_], self.open_kind[k_] = f1, 1
            self.open_info[k_].update(kind=1, first=INTENTS[f1], seconds=[INTENTS[c_] for c_ in seen_[1:]],
                                      share=round(firsts[0][0] / max(1, lives), 3))

    def _open_step(self, human):
        """(OPENINGS) the opening's label of this frame, in place of the rule's where it names something (see OPENINGS)"""
        n, R = self.n, self.route
        self.op_lab = np.zeros(n, np.int64)
        Tn = getattr(self, "rule_tn", None)
        if R is None or Tn is None:
            return
        ar = np.arange(n)
        st_ = self.stats["open"]
        cn = self._counted(ar)                               # (the counters: his seats, as the jump counters')
        grp = ar // (self._others_arr().shape[1] + 1)
        on = human & (self.kind[grp] == NORMAL) & (self.run_k < 0) & (self.hp > 0) & (self.round_t[grp] < 1e8)    # (not a process's frame before its first round)
        new = self.life_t <= self.op_lt                     # a new life: his clock has not gone on (a life's clock goes on every
        #                                                      frame; after a respawn it is a frame old again, as it may have been)
        self.op_lt = self.life_t.copy()
        if new.any():
            ii = np.nonzero(new)[0]
            dd = np.linalg.norm(self.spawns[None, :, :] - self.state[ii, None, :3], axis=2)
            k_ = dd.argmin(1)
            at = (dd[np.arange(len(ii)), k_] < OPEN_AT) & on[ii]
            self.op_sp[ii] = np.where(at, k_, -1)
            self.op_st[ii] = np.where(at, 0, 2)
            self.op_av[ii], self.op_big[ii] = 0, False
            st_[0:3] += (float((on & cn)[ii].sum()), float((at & cn[ii] & (self.open_kind[k_] == 1)).sum()), float((at & cn[ii] & (self.open_kind[k_] == 0)).sum()))
        K = HOLD_INTENT
        t = np.full((n, K), 1e9, np.float32)                 # per intention he can name: the rule's seconds of way to the nearest
        valid = np.zeros((n, K), bool)                       # one the rule could name, whether there is one, whether he has
        done = np.zeros((n, K), bool)                        # taken it in this life (or owns the weapon), whether he believes the
        near = np.zeros((n, K), bool)                        # enemy near it; tk: taken from its place in this life (the counters')
        tk = np.zeros((n, K), bool)
        bel, bok = self._bel_src("open", np.nonzero(on)[0])  # (BRAIN_READ: the brain's place for a life on it)
        for gi, lab in enumerate(self.route_goal):
            c_ = INTENTS.index(lab)
            it = self.route_item[gi]
            tg = Tn[gi]
            gu_, gb_ = self._goal_state(gi, grp)
            took = (self.v02_took[:, it] < self.life_t) & (self.v02_took[:, it] < 90.0)     # (since he took it: less than his life; the clock stops at 99)
            if lab in ("RL", "RG", "LG"):
                w_ = WEAPONS.index(lab.lower())
                v_ = gu_ & ~self.has[:, w_] & (tg < 1e8)
                done[:, c_] |= self.has[:, w_]
            else:
                v_ = (gu_ | (gb_ < tg + 3.0)) & (tg < 1e8)
                done[:, c_] |= took
            tk[:, c_] |= took
            bet = v_ & (tg < t[:, c_])
            if bel is not None and bok is not None and len(bel) == n:
                near[:, c_] = np.where(bet, np.asarray(bok, bool) & (np.linalg.norm(bel - self.item_pos[it][None, :], axis=1) < OPEN_AVOID), near[:, c_])
            t[:, c_] = np.where(bet, tg, t[:, c_])
            valid[:, c_] |= v_
        fb = on & ~self.op_big & tk.any(1)                   # the first big pickup of a life: its seconds
        st_[9:11] += (float(self.life_t[fb & cn].sum()), float((fb & cn).sum()))
        self.op_big |= fb
        act = on & (self.op_sp >= 0) & (self.op_st < 2) & (self.life_t < OPEN_SECS)
        if not act.any():
            return
        sp = np.maximum(self.op_sp, 0)
        pro = self.open_kind[sp] == 1
        f1 = self.open_first[sp]
        wp_ = [INTENTS.index(x_) for x_ in ("RL", "RG", "LG")]
        sk_ = [INTENTS.index(x_) for x_ in ("MH", "RA", "YA", "YA2")]
        tw = np.where(valid[:, wp_], t[:, wp_], 1e9)
        s0 = act & (self.op_st == 0)
        got1 = np.where(pro, done[ar, f1], done[:, wp_].any(1))
        can1 = np.where(pro, valid[ar, f1], valid[:, wp_].any(1))
        st_[7] += float((s0 & cn & np.where(pro, tk[ar, f1], tk[:, wp_].any(1))).sum())
        lab1 = np.where(pro, f1, np.array(wp_)[tw.argmin(1)])
        self.op_st = np.where(s0 & (got1 | ~can1), 1, self.op_st)
        s0 = s0 & ~got1 & can1
        s1 = act & (self.op_st == 1)
        # the second pickups and their order: the pros' list, or (the general rule) the armors and the mega, the nearest first
        cand = np.where(pro[:, None], self.open_rank[sp] < 99, np.isin(np.arange(K), sk_)[None, :])
        rank = np.where(pro[:, None], self.open_rank[sp].astype(np.float32), t)
        got2 = s1 & (cand & done).any(1)
        st_[8] += float((got2 & cn & (cand & tk).any(1)).sum())
        self.op_st = np.where(got2, 2, self.op_st)
        s1 = s1 & ~got2
        plain = cand & valid & ~done
        free = plain & ~near
        p0, p1 = np.where(plain, rank, 2e9).argmin(1), np.where(free, rank, 2e9).argmin(1)
        ch = s1 & plain.any(1) & (~free.any(1) | (p0 != p1))     # the avoid rule changed what it names
        st_[3] += float((ch & cn & (self.op_av == 0)).sum())
        st_[4] += float((ch & cn & ~free.any(1) & (self.op_av < 2)).sum())
        self.op_av = np.where(ch, np.maximum(self.op_av, np.where(free.any(1), 1, 2)), self.op_av)
        out = np.where(s0, lab1, np.where(s1 & free.any(1), p1, 0))
        self.op_lab = out.astype(np.int64)
        self.intent_teach = np.where(self.op_lab > 0, self.op_lab, self.intent_teach)
        if OPEN_SILENT:                                      # (the avoid rule left none: nothing is taught on this frame)
            self.intent_teach = np.where(s1 & plain.any(1) & ~free.any(1), -1, self.intent_teach)

    # ---------------------------------------------------------------- rounds begun from saved moments (MID_START_P, SPAWN_START_P)
    def _moment_init(self, seed):
        """(MID_START_P, SPAWN_START_P) the books: the saved moments (spawn moments, mid-game moments: the newest are
        kept), the rounds to put in place at this step's end, per match the frame its game ends at and the frames of a
        whole game at which a mid-game moment is saved"""
        self.rng_mom = np.random.default_rng([abs(int(seed)), 0xC2])     # the draws' own random stream
        self.mom_bank = ([], [])
        self.mom_n = [0, 0]                                  # moments saved so far, by kind (the bank's oldest is replaced)
        self.mom_put = []
        self.mom_first = True                                # the second half of the matches: a spawn start's spawning player is the first seat
        self.g_end = np.full(self.M, GAME_FRAMES, np.int64)
        self.g_snap = np.full((self.M, MID_PER_GAME), -1, np.int64)
        self.stats["moments"] = np.zeros(len(MOMENT_COLS))
        self.rail_m = np.zeros(self.M, bool)                 # (RAIL_START_P) match m is in a rail start
        self.rail_pairs = None                               # ... the map's pairs of places (None: no rail starts here)
        self.pro_mo = None                                   # (PRO_START_P) the map's pro moments (None: no pro starts here)
        self.ppl_mo = None                                   # (PEOPLE_START_SHARE) the map's moments of people's duels (None: none)

    def _rail_start_init(self, bsp):
        """(RAIL_START_P) the map's pairs of places (sim/rail_pairs/<map>.json; none on a map without a railgun), the books"""
        self.stats["rail_start"] = np.zeros(len(RAIL_START_COLS))
        self.rail_t0 = np.zeros(self.M, np.int64)            # the game's frame the start began at
        self.rail_shot = np.zeros(self.n, bool)              # a counted seat has fired the rail since the start
        f_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rail_pairs", os.path.splitext(os.path.basename(bsp))[0].lower() + ".json")
        if RG not in self.map_weapons or not os.path.exists(f_):
            return
        with open(f_, encoding="utf-8") as fh_:
            pr_ = json.load(fh_)
        if pr_.get("pairs"):
            self.rail_pairs = np.array([p_[:10] for p_ in pr_["pairs"]], np.float32)

    def _pro_start_init(self, bsp):
        """(PRO_START_P) the map's moments of the pros' duels (sim/pro_moments/<map>.npz; none: no pro starts here) and of
        people's (PEOPLE_START_SHARE: PEOPLE_MOMENTS_DIR/<map>.npz), each file's items matched to this simulator's (same
        class, within 48 units), the books"""
        self.stats["pro_start"] = np.zeros(len(PRO_START_COLS))
        self.stats["people_start"] = np.zeros(len(PEOPLE_START_COLS))
        self.pro_mm = np.zeros(self.M, bool)                 # match m is in a pro start
        self.pro_t0 = np.zeros(self.M, np.int64)             # ... the game's frame it began at
        self.pro_s0 = np.zeros(self.n, np.float32)           # ... each seat's score at its start
        self._pro_put = []
        if getattr(self, "lab", None) is not None:
            return
        mapn_ = os.path.splitext(os.path.basename(bsp))[0].lower() + ".npz"
        self.pro_mo = self._moments_load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_moments", mapn_), "pro starts")
        if self.pro_mo is not None:
            self.pro_mean = self._moments_mean(self.pro_mo)
        self.ppl_mo = self._moments_load(os.path.join(PEOPLE_MOMENTS_DIR, mapn_), "people's starts")
        if self.ppl_mo is not None:
            self.ppl_mean = self._moments_mean(self.ppl_mo)
        self._gen_init(os.path.join(GEN_PLACES_DIR, mapn_))

    def _gen_init(self, f_):
        """(GEN_START_SHARE) the map's safe places and the pros' heat on them (none: no generated starts here), the books"""
        self.stats["gen_start"] = np.zeros(len(GEN_START_COLS))
        self.gen_pl, self.gen_bias, self.gen_bt, self.gen_bm = None, {}, -1e9, None
        self.gen_map = os.path.splitext(os.path.basename(f_))[0]
        if not os.path.exists(f_):
            return
        with np.load(f_) as z_:
            pos_, heat_ = z_["pos"].astype(np.float32), z_["heat"].astype(np.float64)
        if len(pos_) < 8:
            return
        self.gen_pl, self.gen_heat = pos_, heat_
        self.gen_near = {}                                   # (label -> the places his ways reach that item from quickly, its index)
        R_ = getattr(self, "route", None)
        node_ = None
        if R_ is not None:                                   # (each place's nearest point of the walking map)
            node_ = np.array([int(np.linalg.norm(R_.nodes - p_, axis=1).argmin()) for p_ in pos_])
        for it in range(self.nI):
            lab_ = self.item_def[it][4]
            if lab_ and lab_ not in self.gen_near:
                if node_ is not None and it in self.route_item:
                    g_ = self.route_item.index(it)
                    ix_ = np.nonzero(R_.T[g_, node_] <= GEN_NEAR_S)[0]
                else:
                    ix_ = np.nonzero(np.linalg.norm(pos_ - self.item_pos[it], axis=1) <= GEN_NEAR)[0]
                if len(ix_):
                    self.gen_near[lab_] = (ix_, it)
        self.gen_mean = float(GAME_LEN - 0.5 * (GEN_T_LO + GEN_T_HI)) if PRO_START_LEN <= 0 else float(min(PRO_START_LEN, GAME_LEN - 0.5 * (GEN_T_LO + GEN_T_HI)))

    def _gen_bias_now(self):
        """(GEN_START_SHARE) the bias file, re-read when it changed (at most every GEN_RELOAD seconds); its place weights"""
        import time as _t
        now_ = _t.time()
        if now_ - self.gen_bt >= GEN_RELOAD:
            self.gen_bt = now_
            try:
                mt_ = os.path.getmtime(GEN_BIAS)
            except OSError:
                mt_ = None
            if mt_ != getattr(self, "gen_mt", None) or self.gen_bm is None:
                self.gen_mt = mt_
                b_ = {}
                if mt_ is not None:
                    try:
                        with open(GEN_BIAS, encoding="utf-8") as fh_:
                            b_ = json.load(fh_)
                    except (OSError, ValueError):
                        b_ = self.gen_bias                   # (a file being written: the last one stays)
                self.gen_bias = b_ if isinstance(b_, dict) else {}
                h_ = np.power(self.gen_heat, float(self.gen_bias.get("heat", 1.0)))
                h_ = h_ / h_.sum() if h_.sum() > 0 else np.full(len(h_), 1.0 / len(h_))
                u_ = float(np.clip(self.gen_bias.get("uniform", 0.1), 0.0, 1.0))
                self.gen_bm = np.cumsum((1.0 - u_) * h_ + u_ / len(h_))
                self.stats["gen_start"][4] += 1
        return self.gen_bias

    def _gen_place(self, rng, among=None):
        c_ = self.gen_bm
        if among is not None:
            w_ = np.diff(np.concatenate([[0.0], c_]))[among]
            return int(among[min(len(among) - 1, int(np.searchsorted(np.cumsum(w_), rng.random() * w_.sum(), side="right")))])
        return min(len(c_) - 1, int(np.searchsorted(c_, rng.random() * c_[-1], side="right")))

    def _gen_moment(self):
        """(GEN_START_SHARE) a new generated moment in the moments' format (one row; the items in this simulator's order)"""
        rng, B = self.rng_mom, self._gen_bias_now()
        mb_ = (B.get("maps") or {}).get(self.gen_map) or {}
        own_b, hand_b, near_b = mb_.get("own") or {}, mb_.get("hand") or {}, mb_.get("near") or {}
        base_own = float(np.clip(B.get("own", 0.5), 0.0, 1.0))
        clock = float(rng.uniform(GEN_T_LO, GEN_T_HI))
        tot = int(rng.poisson(clock / 60.0 * rng.uniform(1.0, 3.0)))
        a_ = int(rng.binomial(tot, rng.beta(2.5, 2.5)))
        P = dict(clock=np.array([clock], np.float32), score=np.array([[a_, tot - a_]], np.int16),
                 pos=np.zeros((1, 2, 3), np.float32), vel=np.zeros((1, 2, 3), np.float32), yaw=np.zeros((1, 2), np.float32),
                 pitch=np.zeros((1, 2), np.float32), hp=np.zeros((1, 2), np.float32), armor=np.zeros((1, 2), np.float32),
                 has=np.zeros((1, 2, NW), bool), ammo=np.zeros((1, 2, NW), np.int16), weapon=np.zeros((1, 2), np.int8),
                 life=np.zeros((1, 2), np.float32), est=np.zeros((1, 2), np.int8),
                 item_left=np.zeros((1, self.nI), np.float32), item_who=np.full((1, self.nI), -1, np.int8),
                 imap=np.arange(self.nI, dtype=np.int64))
        near_it, near_lab = -1, None                         # (the bias: the first seat near an item's spawn)
        labs_ = [l_ for l_ in near_b if l_ in self.gen_near]
        if labs_:
            ps_ = np.array([max(0.0, float(near_b[l_])) for l_ in labs_])
            if ps_.sum() > 0.6:
                ps_ = ps_ * (0.6 / ps_.sum())
            u_ = rng.random()
            c_ = np.cumsum(ps_)
            if u_ < c_[-1]:
                near_lab = labs_[int(np.searchsorted(c_, u_, side="right"))]
        if near_lab is not None:
            ix_, near_it = self.gen_near[near_lab]
            j0 = self._gen_place(rng, ix_)
        else:
            j0 = self._gen_place(rng)
        p0 = self.gen_pl[j0]
        cand_ = np.array([self._gen_place(rng) for _ in range(40)])
        d_ = np.linalg.norm(self.gen_pl[cand_] - p0, axis=1)
        eye_ = np.array([0.0, 0.0, 26.0], np.float32)
        seen_ = self.w.lines(np.repeat((p0 + eye_)[None, :], len(cand_), 0), self.gen_pl[cand_] + eye_) >= 0.999
        ok_ = np.nonzero((d_ >= GEN_FAR) & ~seen_)[0]
        if len(ok_):
            j1 = int(cand_[ok_[0]])
        elif (~seen_).any():
            j1 = int(cand_[np.nonzero(~seen_)[0][int(np.argmax(d_[~seen_]))]])
        else:
            j1 = int(cand_[int(np.argmax(d_))])
        big_ = [w_ for w_ in self.map_weapons if w_ not in (MG, G)]
        GS_ = self.stats["gen_start"]
        for s_, j_ in enumerate((j0, j1)):
            P["pos"][0, s_] = self.gen_pl[j_]
            yaw_ = float(rng.uniform(-180.0, 180.0))
            P["yaw"][0, s_], P["pitch"][0, s_] = yaw_, float(rng.uniform(-15.0, 15.0))
            if rng.random() < 0.5:
                sp_, a2_ = float(rng.uniform(0.0, 320.0)), math.radians(float(rng.uniform(-180.0, 180.0)))
                P["vel"][0, s_, :2] = (sp_ * math.cos(a2_), sp_ * math.sin(a2_))
            u_ = rng.random()
            P["hp"][0, s_] = rng.uniform(25, 75) if u_ < 0.25 else rng.uniform(75, 125) if u_ < 0.70 else rng.uniform(125, 200)
            u_ = rng.random()
            P["armor"][0, s_] = 0.0 if u_ < 0.30 else rng.uniform(1, 50) if u_ < 0.60 else rng.uniform(50, 100) if u_ < 0.85 else rng.uniform(100, 200)
            has_ = P["has"][0, s_]
            has_[MG] = has_[G] = True
            for w_ in big_:
                pw_ = min(0.95, base_own + max(0.0, float(own_b.get(WEAPONS[w_].upper(), 0.0))))
                has_[w_] = rng.random() < pw_
            if s_ == 0 and near_lab is not None and self.item_def[near_it][0] == "wp":
                has_[int(self.item_def[near_it][1])] = rng.random() < 0.5     # (half: the pickup, half: its use)
            for w_ in np.nonzero(has_)[0]:
                if w_ != G:
                    P["ammo"][0, s_, w_] = int(round(float(rng.uniform(0.25, 1.0)) * float(AMMO_MAX[w_])))
            cand_ = [w_ for w_ in big_ if has_[w_]]
            wt_ = [max(0.0, float(hand_b.get(WEAPONS[w_].upper(), 1.0))) for w_ in cand_]
            cand_.append(MG)
            wt_.append(0.4)
            wt_ = np.array(wt_, np.float64)
            P["weapon"][0, s_] = cand_[min(len(cand_) - 1, int(np.searchsorted(np.cumsum(wt_), rng.random() * wt_.sum(), side="right")))]
            P["life"][0, s_] = float(rng.uniform(0.0, min(clock, 100.0)))
            GS_[2] += float(has_[big_].sum()) if big_ else 0.0
            GS_[3] += float(int(P["weapon"][0, s_]) != MG)
        for it in range(self.nI):
            resp_ = float(self.item_def[it][2])
            if it == near_it:
                continue                                     # (the item the bias put him near: it is there)
            if rng.random() >= 0.55:
                P["item_left"][0, it] = float(rng.uniform(0.0, resp_))
                if self.item_def[it][4] in ("MH", "RA", "YA"):
                    P["item_who"][0, it] = int(rng.random() < 0.5)
        GS_[0] += 1
        GS_[1] += float(near_lab is not None)
        return P

    @staticmethod
    def _moments_mean(P):
        return float(np.mean(GAME_LEN - P["clock"])) if PRO_START_LEN <= 0 else float(np.mean(np.minimum(PRO_START_LEN, GAME_LEN - P["clock"])))

    def _moments_load(self, f_, what):
        """a moments file (tools/pro_moments.py, tools/people_moments.py) as a dict with its items matched to this
        simulator's (imap), or None (no file, no moments, a big item not matched)"""
        if not os.path.exists(f_):
            return None
        z_ = np.load(f_)
        if not len(z_["clock"]):
            return None
        P = {k_: np.asarray(z_[k_]) for k_ in z_.files}
        cls_ = [e_["classname"] for e_ in self.w.entities if e_.get("classname") in ITEM_DEFS and "origin" in e_]
        fcls, fpos = [str(c_) for c_ in P["item_cls"]], P["item_pos"].astype(np.float32)
        imap = np.full(self.nI, -1, np.int64)
        used = set()
        for j_ in range(self.nI):
            cand = [c_ for c_ in range(len(fcls)) if fcls[c_] == cls_[j_] and c_ not in used]
            if cand:
                d_ = [float(np.linalg.norm(fpos[c_] - self.item_pos[j_])) for c_ in cand]
                if min(d_) <= 48.0:
                    imap[j_] = cand[int(np.argmin(d_))]
                    used.add(int(imap[j_]))
        if (imap < 0).any() and any(self.item_def[j_][4] in ("MH", "RA", "YA") for j_ in np.nonzero(imap < 0)[0]):
            print("{}: the items of {} do not match this simulator's (a big item missing): none here".format(what, f_), flush=True)
            return None
        P["imap"] = imap
        P["item_left"] = P["item_left"].astype(np.float32)
        if "weight" in P:                                    # (MOMENT_WEIGHTED) the draw's running sum
            w_ = np.maximum(P["weight"].astype(np.float64), 0.0)
            P["wcum"] = np.cumsum(w_) if w_.sum() > 0 else None
        return P                                             # (a dict: no array of it is taken into a saved moment)

    def _pro_ok(self):
        """(PRO_START_P) this map has pro starts now: the pros' moments, or people's with PEOPLE_START_SHARE on"""
        return self.pro_mo is not None or (PEOPLE_START_SHARE > 0 and self.ppl_mo is not None) or (GEN_START_SHARE > 0 and getattr(self, "gen_pl", None) is not None)

    def _pro_mean_now(self):
        """(PRO_START_P) the starts' mean length (for the shares): the pros' as before, or the two sources' by the share"""
        g_ = GEN_START_SHARE if getattr(self, "gen_pl", None) is not None else 0.0
        if self.pro_mo is None and self.ppl_mo is None:
            return self.gen_mean
        s_ = PEOPLE_START_SHARE if self.ppl_mo is not None else 0.0
        if s_ <= 0:
            m_ = self.pro_mean
        elif self.pro_mo is None:
            m_ = self.ppl_mean
        else:
            m_ = (1.0 - s_) * self.pro_mean + s_ * self.ppl_mean
        return m_ if g_ <= 0 else (1.0 - g_) * m_ + g_ * self.gen_mean

    def _pro_pick(self):
        """(PRO_START_P) the source (0 the pros, 1 people: PEOPLE_START_SHARE) and the moment of a new pro start; with both
        switches off one draw, as before"""
        rng, src = self.rng_mom, 0
        if GEN_START_SHARE > 0 and getattr(self, "gen_pl", None) is not None and (self.pro_mo is None and self.ppl_mo is None or rng.random() < GEN_START_SHARE):
            return 2, 0                                      # (GEN_START_SHARE) a generated moment, made at the start itself
        if PEOPLE_START_SHARE > 0 and self.ppl_mo is not None:
            src = 1 if (self.pro_mo is None or rng.random() < PEOPLE_START_SHARE) else 0
        P = self.ppl_mo if src else self.pro_mo
        if MOMENT_WEIGHTED and P.get("wcum") is not None:
            c_ = P["wcum"]
            k = min(len(c_) - 1, int(np.searchsorted(c_, rng.random() * c_[-1], side="right")))
            self.stats["people_start"][3] += 1
        else:
            k = int(rng.integers(len(P["clock"])))
        return src, k

    def _pro_start(self, m, k, src=0):
        """(PRO_START_P) match m, just begun as a whole game (its round's reset done), is put at pro moment k: which seat
        plays which pro drawn evenly; places, speeds, views, stacks, weapons, the score, the clock and the items as the
        moment has them; each seat knows the items its pro took (when they are back) and nothing of the enemy"""
        P, rng, PS_ = (self._gen_moment() if src == 2 else self.ppl_mo if src else self.pro_mo), self.rng_mom, self.stats["pro_start"]
        q = [int(x) for x in self._seats(m)]
        flip = int(rng.random() < 0.5)
        ok_w = np.zeros(NW, bool)
        ok_w[self.map_weapons] = True
        ok_w[MG] = ok_w[G] = True
        tick = int(min(GAME_FRAMES - 1, max(1, round(float(P["clock"][k]) / DT))))
        for j_, i in enumerate(q):
            s_ = j_ ^ flip                                   # (the pro this seat plays: 0 the demo's player, 1 his enemy)
            p_, v_ = P["pos"][k, s_].astype(np.float64), P["vel"][k, s_].astype(np.float64)
            yaw_, pit_ = float(P["yaw"][k, s_]), float(np.clip(P["pitch"][k, s_], -89.0, 89.0))
            self.w.reset(i, (p_[0], p_[1], p_[2]), (v_[0], v_[1], v_[2]), yaw_)
            self.yaw[i], self.pitch[i] = yaw_, pit_
            self.hp[i] = float(np.clip(P["hp"][k, s_], 1.0, 200.0))
            self.armor[i] = float(np.clip(P["armor"][k, s_], 0.0, 200.0))
            has_ = P["has"][k, s_].astype(bool) & ok_w
            has_[MG] = has_[G] = True
            self.has[i] = has_
            self.ammo[i] = np.where(has_, np.minimum(P["ammo"][k, s_].astype(np.float32), AMMO_MAX), 0.0)
            self.ammo[i, G] = 0.0
            w_ = int(P["weapon"][k, s_])
            self.weapon[i] = w_ if 0 <= w_ < NW and has_[w_] else MG
            self.life_t[i] = float(max(0.0, P["life"][k, s_]))
            self.first_wp[i] = bool(has_[[RL, RG, LG, SG, GL, PG, HMG]].any())
            self.mv[i], self.cmd[i] = 0.0, 0.0
            self.hb[i] = 0.0
            self.turn_dir[i], self.rev_wait[i] = 0.0, 0.0
            self.cool[i], self.fire_cd[i] = 0.0, 0.0
            self.fire_q[i] = False
            self.zoom[i], self.duck[i] = False, False
            self.ra[i] = False
            self.vis_run[i], self.acquired[i], self.visible[i] = 0, False, False
            self.frags_r[i] = float(P["score"][k, s_])
            self.pro_s0[i] = self.frags_r[i]
            if bool(self._counted(i)):
                PS_[14] += 1
                PS_[15] += float(P["est"][k, s_] > 0)
                if src == 1:                                 # (PEOPLE_START_SHARE) seat 1 of a people's moment is the person
                    self.stats["people_start"][1] += 1
                    self.stats["people_start"][2] += float(s_ == 1)
        qa = np.array(q)
        self.g_tick[m], self.round_t[m] = tick, np.float32(tick * DT)
        self.game[m] = PRO_KIND
        self._hd_game(qa, PRO_KIND)                          # (HEAD_EVENTS) the win label's game number
        self.g_end[m] = GAME_FRAMES if PRO_START_LEN <= 0 else min(GAME_FRAMES, tick + PRO_FRAMES)
        self.g_snap[m] = -1                                  # (no moment is saved from it)
        if OVERTIME:
            self.g_ot[m] = 0
        self.stats["games"][15] -= 1                         # (_game_start counted a whole game begun)
        d = int(self.frags_r[q[0]] - self.frags_r[q[1]])
        self.g_p[m] = float(self._win_p(d, GAME_LEN - tick * DT)) if self.win_tab is not None else 0.5
        if self.ws_tab is not None:
            self.ws_p[m] = float(self._win_p(d, GAME_LEN - tick * DT, tab=self.ws_tab))
        if self.wb_tab is not None:
            self.wb_p[m] = float(self._wb_chance(m, GAME_LEN - tick * DT)[0])
        self._wsh_start(m, GAME_LEN - tick * DT)             # (WIN_SHAPE_K) PSI with the start's stacks
        im_, L_, W_ = P["imap"], P["item_left"][k], P["item_who"][k]
        for it in range(self.nI):
            c_ = int(im_[it])
            left = float(L_[c_]) if c_ >= 0 else 0.0
            resp = float(self.item_def[it][2])
            left = min(max(left, 0.0), resp)
            self.item_up[m, it], self.item_t[m, it] = left <= 0.0, left
            if left <= 0.0:
                continue
            for g, ri in enumerate(self.route_item):         # (not "taken since the last look": nobody hears it now)
                if ri == it and self.bel_prev is not None and self.bel_prev.shape[0] == self.M and g < self.bel_prev.shape[1]:
                    self.bel_prev[m, g] = False
            who = int(W_[c_]) if c_ >= 0 else -1
            if who < 0:
                continue
            i = q[who ^ flip]                                # (the seat that plays the pro who took it: he knows when it is back)
            lab = self.item_def[it][4]
            self.v02_took[i, it] = resp - left
            if lab in ("MH", "RA"):
                self.it_t[i, 0 if lab == "MH" else 1] = resp - left
            for g, ri in enumerate(self.route_item):
                if ri == it and g < self.bel_t.shape[1]:
                    self.bel_t[i, g] = resp - left
        if EN_STACK:                                         # (B-257) nothing is known of the enemy's stack
            self._es_set(qa, slice(None), spawn=False)
        for h_ in self.opp_hist:                             # (what was on its way to his eyes was of the spawn places)
            h_[1][qa] = False
        for q_ in getattr(self, "v02_q", ()):
            q_[0][qa] = False
            q_[1][qa] = False
        self.pro_mm[m] = True
        self.pro_t0[m] = tick
        PS_[0] += 1
        if src == 1:
            self.stats["people_start"][0] += 1
        PS_[13] += abs(float(d))
        PS_[16] += tick * DT

    def _moment_game(self, m, late):
        """a whole game or a late round begins in match m: its limit, and a whole game's frames for the mid-game moments"""
        self.g_end[m] = GAME_FRAMES
        self.g_snap[m] = -1
        if not late:
            self.g_snap[m] = self.rng_mom.integers(int(round(MID_LO / DT)), int(round(MID_HI / DT)) + 1, MID_PER_GAME)

    def _moment_draw(self, m):
        """match m's new round: a whole game, a late round, a mid-game start or a spawn start (by their shares of the
        playing time), or none of them. A start from a moment is put in place at this step's end (_moment_step)"""
        r0, rg, rl, rx = self._game_rates()
        kp0 = float(self.kind_p[0])
        rm, rs = kp0 * MID_START_P / MID_MEAN, kp0 * SPAWN_START_P / SPAWN_START_LEN
        rr = kp0 * RAIL_START_P / RAIL_MEAN if self.rail_pairs is not None else 0.0     # (RAIL_START_P: rail range starts)
        rp = kp0 * PRO_START_P / self._pro_mean_now() if PRO_START_P > 0 and self._pro_ok() else 0.0     # (PRO_START_P: pro starts)
        if rg + rl + rm + rs + rr + rp <= 0:
            return False
        u = self.rng.random() * (r0 + rg + rl + rx + rm + rs + rr + rp)
        if u >= rg + rl + rm + rs + rr + rp:
            return False
        if u < rg + rl:
            self._game_start(m, late=bool(u >= rg))
            return True
        if u >= rg + rl + rm + rs + rr:                      # (PRO_START_P) a pro start: a whole game's start, then the moment
            self._game_start(m, late=False)                  # (after the round's reset: _pro_start)
            self._pro_put.append((int(m),) + self._pro_pick()[::-1])     # (m, moment, source: PEOPLE_START_SHARE)
            return True
        kd = 3 if u < rg + rl + rm else 4 if u < rg + rl + rm + rs else 5
        bank = self.mom_bank[0 if kd == 4 else 1]            # (the bank: spawn moments, mid-game moments; a rail start: a mid moment)
        if kd == 4 and self.mom_first and m * 2 >= self.M:   # (the first seat is his there: he is the one who spawns)
            bank = [b_ for b_ in bank if b_["who"] == 0]
        if not bank:                                         # nothing saved yet (a process's first minutes): a whole game or one of
            self.stats["moments" if kd < 5 else "rail_start"][4 if kd < 5 else 1] += 1     # the other kinds, by their shares of the time (drawn by the rates the
            kp = np.asarray(self.kind_p, np.float64)         # short kinds would take nearly every start, and a whole game at every
            oth = kp0 * max(0.0, 1.0 - GAME_P - LATE_P - MOMENT_P) + float(kp[1:].sum())      # ask would leave none for later)
            if self.rng_mom.random() * (kp0 * GAME_P + oth) >= kp0 * GAME_P:
                return False
            self._game_start(m, late=False)
            return True
        self.mom_put.append((int(m), bank[int(self.rng_mom.integers(len(bank)))], kd))
        return True

    def _moment_names(self):
        """the arrays a moment holds, by name: a row a player, a row a match (see MOMENT_STATIC for what it leaves)"""
        P, Q = [], []
        for k_, v_ in self.__dict__.items():
            if isinstance(v_, np.ndarray) and v_.ndim >= 1 and k_ not in MOMENT_STATIC:
                if v_.shape[0] == self.n:
                    P.append(k_)
                elif v_.shape[0] == self.M:
                    Q.append(k_)
        return P, Q

    def _moment_take(self, m, obs, who=-1):
        """the moment of match m as it stands at this step's end (obs: the inputs just made)"""
        q = self._seats(m)
        P, Q = self._moment_names()
        return dict(q0=int(q[0]), who=int(who), tick=int(self.g_tick[m]), obs=obs[q].copy(),
                    P={k_: getattr(self, k_)[q].copy() for k_ in P},
                    Q={k_: np.array(getattr(self, k_)[m], copy=True) for k_ in Q},
                    H={k_: [tuple(np.array(a_[q], copy=True) for a_ in f_) for f_ in getattr(self, k_)] for k_ in MOMENT_HIST if hasattr(self, k_)},
                    load=[self.load_sets[int(i)] for i in q])

    def _moment_set(self, m, mo, obs):
        """match m becomes the saved moment mo: its players' and its own rows of every array, the delayed sightings, the
        bodies in the movement library (place, speed, view), the inputs of that frame"""
        q = self._seats(m)
        off = int(q[0]) - mo["q0"]
        for k_, v_ in mo["P"].items():
            a_ = getattr(self, k_, None)
            if isinstance(a_, np.ndarray) and a_.shape[0] == self.n and a_.shape[1:] == v_.shape[1:]:
                a_[q] = np.where(v_ >= 0, v_ + off, v_) if k_ in ("shot_src", "pain_src") else v_      # (a player's number: the new seats')
        for k_, v_ in mo["Q"].items():
            a_ = getattr(self, k_, None)
            if isinstance(a_, np.ndarray) and a_.shape[0] == self.M and a_.shape[1:] == v_.shape:
                a_[m] = v_
        for k_, fr_ in mo["H"].items():
            L = getattr(self, k_, None)
            if L is not None and len(L) == len(fr_):         # (as many frames on their way as then: always, but in a simulator's first frames)
                for f_, g_ in zip(L, fr_):
                    for a_, v_ in zip(f_, g_):
                        a_[q] = v_
        hb_ = getattr(self, "hand_buf", None)
        if hb_ is not None:                                  # (the hand statistics' frames on their way belong to the round that ended)
            hb_[:, q] = -1
        for j_, i in enumerate(q):
            self.load_sets[int(i)] = mo["load"][j_]
            s_ = mo["P"]["state"][j_]
            self.w.reset(int(i), (float(s_[0]), float(s_[1]), float(s_[2])), (float(s_[3]), float(s_[4]), float(s_[5])), float(s_[7]))
        obs[q] = mo["obs"]

    def _moment_step(self, obs, done, died, info):
        """a step's end: the rounds drawn from a saved moment are put in place (and the inputs returned are that
        moment's), then this frame's moments are saved"""
        MS = self.stats["moments"]
        if self.mom_put:
            qq = []
            for m, mo, kd in self.mom_put:
                self._moment_set(m, mo, obs)
                if kd == 5:                                  # (RAIL_START_P) a rail start: a mid-game start's frames, at long range
                    self.game[m] = RAIL_KIND                 # (to the limit: a mid-game start's kind; RAIL_START_LEN: a spawn start's)
                    self._hd_game(self._seats(m), RAIL_KIND)
                    self.g_end[m] = GAME_FRAMES if RAIL_START_LEN <= 0 else min(GAME_FRAMES, int(self.g_tick[m]) + RAIL_FRAMES)
                    self.g_snap[m] = -1
                    if OVERTIME:
                        self.g_ot[m] = 0
                    self._rail_place(m)
                    qq += [int(i) for i in self._seats(m)]
                    continue
                self.game[m] = kd                            # 3 a mid-game start, 4 a spawn start
                self._hd_game(self._seats(m), kd)            # (HEAD_EVENTS) the win label's game number
                self.g_end[m] = GAME_FRAMES if kd == 3 else min(GAME_FRAMES, int(self.g_tick[m]) + SPAWN_FRAMES)
                self.g_snap[m] = -1
                if OVERTIME:
                    self.g_ot[m] = 0
                MS[kd - 3] += 1
                qq += [int(i) for i in self._seats(m)]
            self.mom_put = []
            if info.get("aux") is not None:                  # (the truth of the frame for --aux: the moment's, not the ended round's)
                info["aux"][qq] = self.aux()[qq]
            if "hand_lab" in info:
                info["hand_lab"][qq] = self.hand_lab[qq]
        nr_ = ~self.rail_m if PRO_START_P <= 0 else ~(self.rail_m | self.pro_mm)     # (rail starts and pro starts count apart)
        MS[5:7] += (float(((self.game == 3) & nr_).sum()), float(((self.game == 4) & nr_).sum()))
        if PRO_START_P > 0 and self.pro_mm.any():            # (PRO_START_P) the pro starts' frames
            PS_ = self.stats["pro_start"]
            PS_[2] += float(self.pro_mm.sum())
            PS_[3] += float((self.pro_mm & ((self.g_tick - self.pro_t0) * DT < PRO_EARLY)).sum())
        if self.rail_m.any():                                # (RAIL_START_P) the rail starts' frames
            RS = self.stats["rail_start"]
            RS[3] += float(self.rail_m.sum())
            RS[4] += float((self.rail_m & ((self.g_tick - self.rail_t0) * DT < RAIL_EARLY)).sum())
        bok = getattr(self, "v02_bel_ok", None)
        g_ = self._others_arr().shape[1] + 1
        for v in np.nonzero((self.rsp_born if RESPAWN_QL else died) & ~done)[0]:    # a respawn in a whole game or a mid-game start: the spawn moment
            m = self._match_of(v)
            if self.game[m] not in (1, 3) or self.rail_m[m] or (PRO_START_P > 0 and self.pro_mm[m]):   # (not from a rail or pro start)
                continue
            if OVERTIME and self.g_tick[m] >= GAME_FRAMES:  # (OVERTIME) moments are taken before the limit only
                continue
            MS[9] += 1
            if bok is None or not bool(bok[v]):
                if SPAWN_START_BEL:
                    continue
            else:
                MS[10] += 1
            self._moment_keep(0, self._moment_take(m, obs, who=int(v) % g_))
            MS[7] += 1
        for m in np.nonzero((self.game == 1) & (self.g_snap == self.g_tick[:, None]).any(1))[0]:
            self._moment_keep(1, self._moment_take(int(m), obs))
            MS[8] += 1

    def _rail_place(self, m):
        """(RAIL_START_P) match m, just made a saved mid moment, is put at long range: a pair of the pros' rail places (the
        ends drawn evenly between the two seats), both with the rail in hand and ready, the pros' horizontal speed,
        looking toward the other within RAIL_START_YAW degrees; nothing of the other is seen yet. A pair whose lines or
        room are not clear here is passed over for another (up to RAIL_TRIES; the last one drawn stands if none is)"""
        rng, RS = self.rng_mom, self.stats["rail_start"]
        q = [int(x) for x in self._seats(m)]
        P = self.rail_pairs
        for _ in range(RAIL_TRIES):
            r_ = P[int(rng.integers(len(P)))]
            ends = [(r_[0:3], r_[6:8]), (r_[3:6], r_[8:10])]
            if rng.random() < 0.5:
                ends = ends[::-1]
            pa, pb = ends[0][0].astype(np.float32), ends[1][0].astype(np.float32)
            room = all(not self.w.trace(p_, p_, MINS, MAXS)["startsolid"] for p_ in (pa, pb))
            lines = bool(self._los(np.stack([pa, pb]) + np.array([0, 0, VIEW_H], np.float32),
                                   np.stack([pb, pa]) + np.array([0, 0, 8.0], np.float32)).all())
            if room and lines:
                break
            RS[17] += 1
        for j_, i in enumerate(q):
            p_, v_ = ends[j_][0], ends[j_][1]
            o_ = ends[1 - j_][0]
            face = math.degrees(math.atan2(float(o_[1] - p_[1]), float(o_[0] - p_[0]))) + float(rng.uniform(-RAIL_START_YAW, RAIL_START_YAW))
            self.w.reset(i, (float(p_[0]), float(p_[1]), float(p_[2])), (float(v_[0]), float(v_[1]), 0.0), face)
            self.yaw[i], self.pitch[i] = face, 0.0
            self.mv[i], self.cmd[i] = 0.0, 0.0
            self.hb[i] = 0.0
            self.turn_dir[i], self.rev_wait[i] = 0.0, 0.0
            self.has[i, RG] = True
            self.ammo[i, RG] = max(float(self.ammo[i, RG]), RAIL_START_AMMO)
            self.weapon[i] = RG
            self.cool[i], self.fire_cd[i] = 0.0, 0.0
            self.fire_q[i] = False
            self.zoom[i], self.duck[i] = False, False
            self.ra[i] = False                               # (the moment's rockets in the air were fired from elsewhere)
            self.vis_run[i], self.acquired[i], self.visible[i] = 0, False, False
        qa = np.array(q)
        for h_ in self.opp_hist:                             # (what was on its way to his eyes was of the places before)
            h_[1][qa] = False
        for q_ in getattr(self, "v02_q", ()):
            q_[0][qa] = False
            q_[1][qa] = False
        self.state = self.w.state()
        self.rail_m[m] = True
        self.rail_t0[m] = int(self.g_tick[m])
        self.rail_shot[qa] = False
        RS[0] += 1
        RS[14] += float(self._counted(qa).sum())
        RS[18] += float(np.linalg.norm(ends[0][0] - ends[1][0]))

    def _moment_keep(self, kd, mo):
        bank, cap = self.mom_bank[kd], (SPAWN_BANK, MID_BANK)[kd]
        if len(bank) < cap:
            bank.append(mo)
        else:
            bank[self.mom_n[kd] % cap] = mo
        self.mom_n[kd] += 1

    def _moment_end(self, m):
        """the round of match m that began from a saved moment is over: a mid-game start at the game's limit (its result
        counts from the saved score), a spawn start after its seconds"""
        q = self._seats(m)
        MS = self.stats["moments"]
        kd = int(self.game[m])
        if PRO_START_P > 0 and self.pro_mm[m]:               # (PRO_START_P) a pro start: its own counters
            PS_ = self.stats["pro_start"]
            PS_[1] += 1
            got_ = self.frags_r[q] - self.pro_s0[q]
            PS_[8] += float(got_.sum())
            cq_ = self._counted(q)
            PS_[9] += float(got_[cq_].sum())
            if got_.sum() > 0:
                PS_[18] += 1
                PS_[17] += float(got_[cq_].sum() / got_.sum()) if cq_.sum() == 1 else 0.5
            if m * 2 >= self.M:
                d = float(self.frags_r[int(q[0])] - self.frags_r[int(q[1])])
                PS_[4] += 1
                PS_[5 if d > 0 else 6 if d == 0 else 7] += 1
            self.pro_mm[m] = False
            self.game[m] = 0
            self.g_win[q], self.g_flat[q] = 0.0, 0.0
            return
        if self.rail_m[m]:                                   # (RAIL_START_P) a rail start: its own counters
            RS = self.stats["rail_start"]
            RS[2] += 1
            if m * 2 >= self.M:
                d = float(self.frags_r[int(q[0])] - self.frags_r[int(q[1])])
                RS[19] += 1
                RS[20 if d > 0 else 21 if d == 0 else 22] += 1
            self.rail_m[m] = False
            self.rail_shot[q] = False
            self.game[m] = 0
            self.g_win[q], self.g_flat[q] = 0.0, 0.0
            return
        MS[kd - 1] += 1
        if kd == 3 and m * 2 >= self.M:
            d = float(self.frags_r[int(q[0])] - self.frags_r[int(q[1])])
            MS[11] += 1
            MS[12 if d > 0 else 13 if d == 0 else 14] += 1
        self.game[m] = 0
        self.g_win[q], self.g_flat[q] = 0.0, 0.0

    def _seats(self, m):
        g_ = self._others_arr().shape[1] + 1
        return np.arange(g_ * m, g_ * m + g_)

    def _item_run_start(self, m):
        """start an item run for match m in a share of the rounds (see RUN_LEN); returns its seats, or None"""
        pj = self.jump_run_p if self.jump_tries else 0.0     # (jump runs: a share of the playing time beside the item runs')
        pr = self.rj_run_p if self.rj_live else 0.0          # (RJ_RUN_P: rocket jump runs, the same)
        if RJ_FROM_JUMP and pr > 0:                          # (RJ_FROM_JUMP) out of the jump runs' share, not on top of it
            pj = max(0.0, pj - pr) if self.jump_tries else 0.0
        if self.item_run_p + pj + pr <= 0 or self.route is None or self.fixed_kind is not None or getattr(self, "lab_force", None):
            return None
        if self.lab is not None:
            other = float(self.arena_len)
        else:
            other = 1.0 / max(1e-9, float((np.asarray(self.kind_p[:3], np.float64) / np.array([self.round_len, 15.0, 15.0])).sum()))
            if GAME_ON and self._game_ok():                  # (whole games and late rounds are longer than a round)
                r0_, rg_, rl_, _ = self._game_rates()
                rm_ = float(self.kind_p[0]) * MID_START_P / MID_MEAN if MOMENTS else 0.0          # (the rounds begun from saved moments)
                rs_ = float(self.kind_p[0]) * SPAWN_START_P / SPAWN_START_LEN if MOMENTS else 0.0
                if MOMENTS and self.rail_pairs is not None:  # (RAIL_START_P: rail range starts)
                    rs_ += float(self.kind_p[0]) * RAIL_START_P / RAIL_MEAN
                if PRO_START_P > 0 and self._pro_ok():       # (PRO_START_P: pro starts)
                    rs_ += float(self.kind_p[0]) * PRO_START_P / self._pro_mean_now()
                other = 1.0 / max(1e-9, r0_ + rg_ + rl_ + rm_ + rs_ + float(self.kind_p[1]) / 15.0 + float(self.kind_p[2]) / 15.0)
        p = self.item_run_p + pj + pr
        if self.rng.random() >= (p / RUN_LEN) / (p / RUN_LEN + (1.0 - p) / other):
            return None
        jump = pj > 0 and self.rng.random() < pj / p
        rj = (not jump) and pr > 0 and self.rng.random() < pr / (p - pj)
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
        self.cf_t[m] = RUN_COLLECT if (not jump and not rj and self.rng.random() < self.collect_fight_p) else -1.0
        self.jrun[q] = jump
        self.rjrun[q] = rj
        for i in q:
            self.load_sets[int(i)] = ()                     # the game's spawn: machine gun and gauntlet
            self.state = self.w.state()
            if jump:
                self._jump_place(int(i))
            elif rj:
                self._rj_place(int(i))
            else:
                self._spawn(int(i), avoid=None)
        self.state = self.w.state()
        if RUN_TARGET_W and not (jump or rj):               # (RUN_TARGET_W) the item runs, counted
            self.stats["run_item"][0] += 1
        for i in (() if (jump or rj) else q):
            self._run_pick(int(i))
        return q

    def _jump_place(self, i):
        """a jump run: player i begins a try a second or two of way before the take-off of one of the pros' jumps (every
        jump as often as any other), with the item behind it as his target; the item is put back if it was taken"""
        ks = list(self.jump_tries)
        if JUMP_WEIGHT and self.jrun_open[i]:                # (JUMP_WEIGHT) the try before, not over: into his success
            self._jump_learn(int(self.jrun_k[i]), False)
        self.jrun_open[i] = JUMP_WEIGHT and bool(self._counted(i))
        if self.rc is not None:                              # (ROUTE_COPY) the try before ends; this one's route
            self._rc_close(i)
        if JUMP_WEIGHT:                                      # (JUMP_WEIGHT) the jumps he fails more often
            w_ = np.maximum(JUMP_W_FLOOR, 1.0 - self.jw_s[np.minimum(np.array(ks, np.int64), 63)])
            if JUMP_W_DROP > 0:                              # (JUMP_W_DROP) the jumps he makes at this rate or more: no tries
                dr_ = self.jw_s[np.minimum(np.array(ks, np.int64), 63)] >= JUMP_W_DROP
                if JUMP_KEEP_CLOSED:                         # (JUMP_KEEP_CLOSED) ... only those open in games (and the stuck spots)
                    dr_ = dr_ & self.jdrop_ok[np.array(ks, np.int64)]
                w_ = np.where(dr_, 0.0, w_)
                if w_.sum() <= 0:
                    w_ = np.ones(len(ks))
            if JUMP_FOCUS:                                   # (JUMP_FOCUS) the jumps the owner named: more tries
                w_ = w_ * self.jfocus[np.array(ks, np.int64)]
            if JUMP_W_CAP > 0 and (w_ > 0).sum() > 1:       # (JUMP_W_CAP) no one jump above this share of the draws
                cap_ = max(JUMP_W_CAP, 1.5 / float((w_ > 0).sum()))      # (with few jumps left: 1.5x an even share)
                for _ in range(6):
                    p_ = w_ / w_.sum()
                    if (p_ <= cap_ + 1e-9).all():
                        break
                    over_ = p_ > cap_
                    w_ = np.where(over_, cap_ * w_[~over_].sum() / max(1e-9, 1.0 - cap_ * over_.sum()), w_)
            k = int(ks[int(self.rng.choice(len(ks), p=w_ / w_.sum()))])
        else:
            k = int(ks[int(self.rng.integers(len(ks)))])
        e = int(self.rng.integers(len(self.jump_tries[k])))
        g, st, f = self.jump_tries[k][e]
        J = self.jfields[f]
        self.jrun_f[i] = f
        far = JUMP_FAR_P > 0 and self.rng.random() < JUMP_FAR_P and len(self.jump_far.get((k, e), ())) > 0
        if far:                                              # (JUMP_FAR_P) further back, moving along the way
            st = self.jump_far[(k, e)]
        ru_ = JUMP_RUNUP > 0 and not far and (k, e) in self.jrunup
        if ru_:                                              # (JUMP_RUNUP) a near try of a fast jump: room for a hop or two
            st = self.jrunup[(k, e)]
        node = int(st[int(self.rng.integers(len(st)))])
        nx = int(J.next[g, node])
        p, q = J.nodes[node], (J.nodes[nx] if nx >= 0 else J.goals[g])
        if ru_ and (k, e) in self.jrunup_line:               # (JUMP_RUNUP) a straight run-up: from a route node, at the take-off
            p, q = self.route.nodes[node], self.jump_a[k]
        face = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) + float(self.rng.uniform(-40, 40))
        vel = (0, 0, 0)
        if far or ru_:
            d_ = np.array([q[0] - p[0], q[1] - p[1]], np.float64)
            d_ = d_ / max(1e-6, float(np.hypot(*d_)))
            sp_ = JUMP_FAR_SPEED
            if JUMP_VARY:                                    # (JUMP_VARY) his speed and line along the way vary
                sp_ = float(self.rng.uniform(220.0, 420.0))
                a_ = math.radians(float(self.rng.uniform(-12, 12)))
                d_ = np.array([d_[0] * math.cos(a_) - d_[1] * math.sin(a_), d_[0] * math.sin(a_) + d_[1] * math.cos(a_)])
            vel = (float(d_[0] * sp_), float(d_[1] * sp_), 0.0)
        elif JUMP_VARY and self.rng.random() < 0.5:          # (JUMP_VARY) a near start half the time already moving
            d_ = np.array([q[0] - p[0], q[1] - p[1]], np.float64)
            d_ = d_ / max(1e-6, float(np.hypot(*d_)))
            a_ = math.radians(float(self.rng.uniform(-15, 15)))
            sp_ = float(self.rng.uniform(0.0, 350.0))
            vel = (float((d_[0] * math.cos(a_) - d_[1] * math.sin(a_)) * sp_), float((d_[0] * math.sin(a_) + d_[1] * math.cos(a_)) * sp_), 0.0)
        pro_ = k in self.jstart and (k >= getattr(self, "n_real_jumps", 10 ** 9) or (PRO_JSTART_P > 0 and self.rng.random() < PRO_JSTART_P))
        if pro_:                                             # (PRO_JSTART_P) a pro's own state before the take-off
            far = False
            P_, V_, Y_ = self.jstart[k]
            s_ = int(self.rng.integers(len(P_)))
            pos_ = [float(x_) for x_ in P_[s_]]
            face, vel = float(Y_[s_]), tuple(float(x_) for x_ in V_[s_])
            if JUMP_VARY and k < getattr(self, "n_real_jumps", 10 ** 9):   # (JUMP_VARY) around the pro's state, not on it
                a_ = math.radians(float(self.rng.uniform(-8, 8)))
                f_ = float(self.rng.uniform(0.9, 1.1))
                vel = (f_ * (vel[0] * math.cos(a_) - vel[1] * math.sin(a_)), f_ * (vel[0] * math.sin(a_) + vel[1] * math.cos(a_)), vel[2])
                face += float(self.rng.uniform(-20, 20))
                pos_[0] += float(self.rng.uniform(-8, 8))
                pos_[1] += float(self.rng.uniform(-8, 8))
            self.w.reset(i, tuple(pos_), vel, face)
        else:
            if JUMP_SOLID_FIX and (f, node) in self.jnode_fix:    # (JUMP_SOLID_FIX) the free spot next to a solid one
                p = self.jnode_fix[(f, node)]
            self.w.reset(i, (p[0], p[1], p[2] + 9.0), vel, face)
        self._fresh(i, face)
        self.jrun_far[i] = far
        if JUMP_OVER_ANY:                                    # (JUMP_OVER_ANY) he stands where he begins
            self.jrun_lift[i] = pos_ if pro_ else (p[0], p[1], p[2] + 9.0)
        if far and not JUMP_VARY:
            self.sp_hist[i] = JUMP_FAR_SPEED                 # (his speed of the last frames: what he moves at, not a gain)
        elif pro_ or ru_ or (JUMP_VARY and (vel[0] or vel[1])):
            self.sp_hist[i] = float(math.hypot(vel[0], vel[1]))
        m = self._match_of(i)
        self.item_up[m, self.route_item[g]], self.item_t[m, self.route_item[g]] = True, 0.0
        if g < self.bel_t.shape[1]:
            self.bel_t[i, g] = 99.0                         # ... and he knows it is there
        if self.route_goal[g] in ("MH", "RA"):
            self.it_t[i, 0 if self.route_goal[g] == "MH" else 1] = 99.0
        self.jrun_it[i], self.jrun_paid[i], self._replaced = self.route_item[g], 0.0, True
        if getattr(self, "jrun_spd", None) is not None and len(self.jrun_spd) == self.n:
            self.jrun_spd[i] = 0.0                           # (JRUN_SPEED_BACK) a new try's speed pay counts from nothing
        self.run_k[i] = INTENTS.index(self.route_goal[g])
        self.intent_new[i], self.intent_done[i] = True, True     # the target is read at once
        self.jrun_k[i], self.jrun_t[i] = k, 2.0 * float(J.T[g, node]) + JUMP_TRY_SLACK
        self.jrun_edge[i], self.jrun_over[i], self.jrun_new[i] = False, False, True
        self.jrun_past[i] = False
        if self._counted(i):
            self.stats["jump_tries"][min(k, 63)] += 1
            self.stats["jump_far"][2 if far else 0] += 1
        if self.rc is not None:                              # (ROUTE_COPY) a try at the route's jump: one of its routes
            on_ = k == self.rc["k"]
            nr_ = len(self.rc["routes"])
            self.rc_r[i] = (0 if nr_ == 1 or self.rc_rng.random() < ROUTE_COPY_P else 1) if on_ else -1
            self.rc_ph[i], self.rc_i[i], self.rc_jmp[i], self.rc_down[i] = 0, 0, False, False
            self.rc_g[i], self.rc_vz[i] = g, 0.0
            self.rc_live[i], self.rc_arr[i] = on_ and bool(self._counted(i)), False

    def _jump_solid_fix(self):
        """(JUMP_SOLID_FIX) the near and far start spots of every jump's entries where the player box (as w.reset puts
        him: 9 u above the node) is inside something solid are left out; an entry left with no near spot gets the nearest
        free spot round its first one (stored in jnode_fix), or is dropped, and a jump with no entry left is not drawn"""
        lo_, hi_ = np.array([-15.0, -15.0, -24.0]), np.array([15.0, 15.0, 32.0])

        def free_(o_):
            o_ = np.asarray(o_, np.float32)
            return not self.w.trace(o_, o_ + np.array([0.0, 0.0, 0.1], np.float32), lo_, hi_)["startsolid"]

        def floor_(o_):
            o_ = np.asarray(o_, np.float32)
            return self.w.trace(o_, o_ - np.array([0.0, 0.0, 48.0], np.float32), lo_, hi_)["fraction"] < 1.0

        self.jnode_fix = {}
        self.jsolid_log = []
        for k_ in list(self.jump_tries):
            keep_ = []
            for e_, (g_, st_, f_) in enumerate(self.jump_tries[k_]):
                J_ = self.jfields[f_]
                ok_ = np.array([free_(J_.nodes[int(n_)] + np.array([0.0, 0.0, 9.0])) for n_ in st_], bool)
                if (k_, e_) in self.jump_far:
                    far_ = self.jump_far[(k_, e_)]
                    fo_ = np.array([free_(J_.nodes[int(n_)] + np.array([0.0, 0.0, 9.0])) for n_ in far_], bool)
                    if fo_.any():
                        self.jump_far[(k_, e_)] = far_[fo_]
                    else:
                        del self.jump_far[(k_, e_)]
                if ok_.any():
                    if not ok_.all():
                        self.jsolid_log.append((k_, e_, int((~ok_).sum()), len(ok_)))
                    keep_.append((len(keep_), e_, (g_, np.asarray(st_)[ok_], f_)))
                    continue
                n0_ = int(st_[0])
                p0_ = np.array(J_.nodes[n0_], np.float64) + np.array([0.0, 0.0, 9.0])
                fix_ = None
                for dz_ in range(0, 36, 4):
                    for dx_, dy_ in ((0, 0), (8, 0), (-8, 0), (0, 8), (0, -8), (16, 0), (-16, 0), (0, 16), (0, -16),
                                     (12, 12), (-12, 12), (12, -12), (-12, -12)):
                        q_ = p0_ + np.array([dx_, dy_, dz_])
                        if free_(q_) and floor_(q_):
                            fix_ = q_
                            break
                    if fix_ is not None:
                        break
                if fix_ is None:
                    self.jsolid_log.append((k_, e_, len(ok_), len(ok_), "dropped"))
                    continue
                self.jnode_fix[(f_, n0_)] = fix_ - np.array([0.0, 0.0, 9.0])
                self.jsolid_log.append((k_, e_, len(ok_), len(ok_), "moved", [round(float(x_)) for x_ in fix_ - p0_]))
                keep_.append((len(keep_), e_, (g_, np.array([n0_], np.int64), f_)))
            if keep_:                                    # (the far spots follow their entries' new places)
                self.jump_far = {(kk_, e_): v_ for (kk_, e_), v_ in self.jump_far.items() if kk_ != k_} | \
                    {(k_, new_): self.jump_far[(k_, old_)] for new_, old_, _ in keep_ if (k_, old_) in self.jump_far}
                self.jump_tries[k_] = [ent_ for _, _, ent_ in keep_]
            else:
                del self.jump_tries[k_]
                self.jump_far = {(kk_, e_): v_ for (kk_, e_), v_ in self.jump_far.items() if kk_ != k_}

    def _jump_runup(self):
        """(JUMP_RUNUP) per real jump and entry: the spots whose way has this jump first, by seconds of way to its
        take-off (every way of the entry's field, not only those to the nearest item); run-up spots JUMP_RUNUP_LO to
        JUMP_RUNUP_HI s back for the fast jumps and for entries whose near spots are all on the take-off's lip (those
        left out); far spots (JUMP_FAR_LO to JUMP_FAR_HI s) where an entry has none. Spots in solid are left out."""
        lo_, hi_ = np.array([-15.0, -15.0, -24.0]), np.array([15.0, 15.0, 32.0])
        R_ = self.route
        self.jrunup_log = []
        self.jrunup_line = set()                         # (jump, entry): run-up spots on the jump's line (route nodes), run at A

        def free_(n_, X_):
            o_ = np.asarray(X_.nodes[int(n_)] + np.array([0.0, 0.0, 9.0]), np.float32)
            return not self.w.trace(o_, o_ + np.array([0.0, 0.0, 0.1], np.float32), lo_, hi_)["startsolid"]

        for k, ents in list(self.jump_tries.items()):
            if k >= self.n_real_jumps:
                continue
            A_ = self.jump_a[k]
            fast_ = float(self.jumps[k].get("need", 0.0)) >= JUMP_RUNUP
            for e, (g, st, f) in enumerate(list(ents)):
                X = self.jfields[f]
                nxt, jl = X.next[g], X.jlink[g]
                cur = np.arange(len(nxt))
                hit = np.full(len(nxt), -1, np.int64)
                live = X.T[g] < 1e8
                for _ in range(400):
                    j_ = jl[cur]
                    at_ = live & (j_ >= 0)
                    hit[at_ & (j_ == k)] = cur[at_ & (j_ == k)]
                    live &= ~at_ & (nxt[cur] >= 0)
                    if not live.any():
                        break
                    cur = np.where(live, nxt[cur], cur)
                ok = (hit >= 0) & ~R_.dead
                tt = np.where(ok, X.T[g] - X.T[g, np.maximum(hit, 0)], -1.0)

                def pick_(a_, b_, fall_=True):
                    sel_ = np.nonzero(ok & (tt >= a_) & (tt <= b_))[0]
                    if fall_ and not len(sel_) and ok.any() and float(tt.max()) > 0:
                        sel_ = np.nonzero(ok & (tt >= 0.8 * min(float(tt.max()), b_)) & (tt > 0))[0]
                    return np.array([n_ for n_ in sel_ if free_(n_, X)], np.int64)

                st_ = np.asarray(st)
                off_ = np.array([math.hypot(float(X.nodes[int(n_)][0] - A_[0]), float(X.nodes[int(n_)][1] - A_[1])) >= 40.0
                                 for n_ in st_], bool)
                lip_ = not off_.any()
                if off_.any() and not off_.all():
                    self.jump_tries[k][e] = (g, st_[off_], f)
                if fast_ or lip_:
                    ru_ = pick_(JUMP_RUNUP_LO, JUMP_RUNUP_HI)
                    kind_ = "way"
                    if len(ru_) < 5:                         # (almost) no way leads in: a straight run-up behind the take-off,
                        li_ = self._jump_line_spots(k)           # on the jump's line, level and clear, instead
                        if len(li_) > len(ru_):
                            ru_, kind_ = li_, "line"
                            self.jrunup_line.add((k, e))
                    if len(ru_):
                        self.jrunup[(k, e)] = ru_
                        fo_ = self.jump_far.get((k, e), ())       # far spots nearer than a run-up (JUMP_FAR's fall-back on a
                        if len(fo_) and max(math.hypot(float(X.nodes[int(n_)][0] - A_[0]), float(X.nodes[int(n_)][1] - A_[1]))
                                            for n_ in fo_) < 200.0:     # short way: Cure 8 began at 103 u half the time)
                            del self.jump_far[(k, e)]
                    elif lip_:                               # only a lip to start on and nothing behind it: not practised
                        kind_ = "dropped"                    # (Toxicity 7: he slid off on every try)
                    self.jrunup_log.append((int(self.jumps[k]["id"]), e, "fast" if fast_ else "lip", kind_, len(ru_)))
                if lip_ and (k, e) not in self.jrunup:
                    continue
                if (k, e) not in self.jump_far:
                    fa_ = pick_(JUMP_FAR_LO, JUMP_FAR_HI, False)     # (no fall-back: it gave spots by the edge)
                    if len(fa_):
                        self.jump_far[(k, e)] = fa_
                        self.jrunup_log.append((int(self.jumps[k]["id"]), e, "far", len(fa_)))

    def _jump_runup_drop(self):
        """(JUMP_RUNUP) the entries logged "dropped" out of jump_tries (a jump with none left is not drawn)"""
        for jid_, e_, _, kind_, _ in [x_ for x_ in self.jrunup_log if x_[3] == "dropped"]:
            k_ = [i_ for i_, j_ in enumerate(self.jumps) if int(j_["id"]) == jid_][0]
            self.jump_tries[k_][e_] = None
        for k_ in list(self.jump_tries):
            keep_ = [(i_, x_) for i_, x_ in enumerate(self.jump_tries[k_]) if x_ is not None]
            if len(keep_) == len(self.jump_tries[k_]):
                continue
            fa_ = {(k_, new_): self.jump_far[(k_, old_)] for new_, (old_, _) in enumerate(keep_) if (k_, old_) in self.jump_far}
            ru_ = {(k_, new_): self.jrunup[(k_, old_)] for new_, (old_, _) in enumerate(keep_) if (k_, old_) in self.jrunup}
            li_ = {(k_, new_) for new_, (old_, _) in enumerate(keep_) if (k_, old_) in self.jrunup_line}
            self.jump_far = {kk_: v_ for kk_, v_ in self.jump_far.items() if kk_[0] != k_} | fa_
            self.jrunup = {kk_: v_ for kk_, v_ in self.jrunup.items() if kk_[0] != k_} | ru_
            self.jrunup_line = {kk_ for kk_ in self.jrunup_line if kk_[0] != k_} | li_
            if keep_:
                self.jump_tries[k_] = [x_ for _, x_ in keep_]
            else:
                del self.jump_tries[k_]

    def _jump_line_spots(self, k):
        """(JUMP_RUNUP) the route's nodes 200 to 700 u behind jump k's take-off, within 50 deg of its line (landing to
        take-off, carried on), within 40 u of its height, the player box free there and clear all the way to the take-off"""
        lo_, hi_ = np.array([-15.0, -15.0, -24.0]), np.array([15.0, 15.0, 32.0])
        A_, B_ = np.asarray(self.jump_a[k], np.float64), np.asarray(self.jump_b[k], np.float64)
        u_ = (A_ - B_)[:2] / max(1e-6, float(np.hypot(*(A_ - B_)[:2])))
        N_ = np.asarray(self.route.nodes, np.float64)
        d_ = N_[:, :2] - A_[:2]
        r_ = np.hypot(d_[:, 0], d_[:, 1])
        cos_ = (d_ @ u_) / np.maximum(r_, 1e-6)
        cand_ = np.nonzero((r_ >= 200.0) & (r_ <= 700.0) & (cos_ >= np.cos(np.radians(50.0))) & (np.abs(N_[:, 2] - A_[2]) <= 40.0)
                           & ~self.route.dead)[0]
        out_ = []
        a9_ = (A_ + np.array([0.0, 0.0, 9.0])).astype(np.float32)
        for n_ in cand_:
            o_ = (N_[n_] + np.array([0.0, 0.0, 9.0])).astype(np.float32)
            t0_ = self.w.trace(o_, o_ + np.array([0.0, 0.0, 0.1], np.float32), lo_, hi_)
            if t0_["startsolid"]:
                continue
            if self.w.trace(o_, a9_, lo_, hi_)["fraction"] >= 0.999:
                out_.append(int(n_))
        return np.array(out_, np.int64)

    def _jump_learn(self, k, over):
        """(JUMP_WEIGHT) one try at jump k into his success there (see JUMP_WEIGHT)"""
        k = min(int(k), 63)
        a_ = max(1.0 / (self.jw_n[k] + 2.0), 1.0 - 0.5 ** (1.0 / JUMP_W_HALF))
        self.jw_s[k] += a_ * (float(over) - self.jw_s[k])
        self.jw_n[k] += 1.0

    def _jump_far_spots(self):
        """(JUMP_FAR_P) per jump and entry of jump_tries: the spots JUMP_FAR_LO to JUMP_FAR_HI seconds of way before its
        take-off whose way to the entry's goal has that jump as the first one ahead (and, for an item, leads to the nearest
        of its kind); with less way, the farthest fifth of what there is"""
        R_ = self.route
        for k, ents in self.jump_tries.items():
            for e, (g, st, f) in enumerate(ents):
                X = self.jfields[f]
                nxt, jl = X.next[g], X.jlink[g]
                n_ = len(nxt)
                cur = np.arange(n_)
                hit = np.full(n_, -1, np.int64)              # the take-off spot of the first jump ahead, if it is jump k
                live = X.T[g] < 1e8
                for _ in range(400):
                    j_ = jl[cur]
                    at_ = live & (j_ >= 0)
                    hit[at_ & (j_ == k)] = cur[at_ & (j_ == k)]
                    live &= ~at_ & (nxt[cur] >= 0)
                    if not live.any():
                        break
                    cur = np.where(live, nxt[cur], cur)
                ok = (hit >= 0) & ~R_.dead
                if f not in self.jfield_land:
                    same_ = self.intent_more.get(INTENTS.index(self.route_goal[g]), np.array([g], np.int64))
                    ok &= X.T[g] <= X.T[same_].min(0) + 1e-6
                if not ok.any():
                    continue
                tt = np.where(ok, X.T[g] - X.T[g, np.maximum(hit, 0)], -1.0)
                sel = np.nonzero(ok & (tt >= JUMP_FAR_LO) & (tt <= JUMP_FAR_HI))[0]
                if not len(sel):
                    sel = np.nonzero(ok & (tt >= 0.8 * float(tt.max())) & (tt > 0))[0]
                if len(sel):
                    self.jump_far[(k, e)] = sel.astype(np.int64)

    def _rj_step(self, rr, s, prev, reward, r_long):
        """(RJ_RUN_P) the players rr of rocket jump runs this frame: he arrives when he comes down within RJ_LAND of the
        landing from a flight of 8 frames or more that passed the take-off (RJ_EDGE about it: on the floor or in the air,
        as the pros come in from a jump); paid RJ_ARRIVE and the next try. A try ends without pay when he touches the floor
        elsewhere after having been at the take-off, or when its seconds are over."""
        self.stats["rj_frames"] += int(self._counted(rr).sum())
        self.rjrun_new[rr] = False
        self.rjrun_t[rr] -= DT
        kk_ = self.rjrun_k[rr]
        A_, B_, p_ = self.rj_a[kk_], self.rj_b[kk_], s[rr, :3]
        at_a = (np.hypot(p_[:, 0] - A_[:, 0], p_[:, 1] - A_[:, 1]) < RJ_EDGE) & (np.abs(p_[:, 2] - A_[:, 2]) < 64.0)
        near_b = np.linalg.norm(p_ - B_, axis=1) < RJ_LAND
        landed_ = (s[rr, 6] > 0.5) | ((prev[rr, 5] < 0.0) & (s[rr, 5] > 0.0))   # on the floor, or touched it and jumped again inside the frame
        from_, air_ = self.rjrun_from[rr] | at_a, self.rjrun_air[rr]
        ov_ = near_b & landed_ & from_ & (air_ >= 8)
        fail_ = landed_ & from_ & ~at_a & ~near_b
        self.rjrun_edge[rr] |= at_a
        self.rjrun_air[rr] = np.where(landed_, 0, air_ + 1)
        self.rjrun_from[rr] = np.where(landed_, at_a, from_)
        np.add.at(self.stats["rj_over"], np.minimum(kk_[ov_ & self._counted(rr)], 63), 1)
        for j in np.nonzero(ov_ | fail_ | (self.rjrun_t[rr] <= 0))[0]:
            i = int(rr[j])
            if ov_[j]:
                reward[i] += RJ_ARRIVE
                r_long[i] += RJ_ARRIVE
            if RJ_COPY:                                      # (RJ_COPY) the try's end: arrived or not
                self._rjc_close(i, 1 if ov_[j] else 0)
            self._rj_place(i)

    def _rjc_close(self, i, how):
        """(RJ_COPY) player i's try ends: how = 0 not over, 1 arrived, 2 died; counted for his counted seats (stats["rj_copy"])"""
        if not self.rjc_live[i]:
            return
        self.rjc_live[i] = False
        if "rj_copy" not in self.stats:
            self.stats["rj_copy"] = np.zeros(6)
        lost_ = float(self.rjc_hp0[i]) - (0.0 if how == 2 else float(max(self.hp[i], 0.0) + self.armor[i]))
        self.stats["rj_copy"] += np.array([0.0, 1.0, float(how == 1), float(how == 2), max(lost_, 0.0),
                                           float(lost_ >= RJ_COPY_BIG)], np.float64)

    def _rjc_pick(self, vel, hb, err, cands, lev, cap, pit, rate=None):
        """(RJ_COPY) per player the command (an index into cands) that brings the view's error err (degrees) nearest zero
        RJ_COPY_H frames ahead with it held, through his mouse as step() moves it: the smoothing (MOUSE_SMOOTH, the fine
        one for small commands), the flick cap (cap; None: none), HAND_BAND's low-pass, and for the pitch (pit: his pitch,
        lev: the ease toward level a frame) the ease; the error counted is where the view would come to rest: the error then
        less RJ_COPY_VW frames of its velocity then (the smoothing's tail), of the pitch's beyond what holds it against the ease;
        rate (degrees a frame, ROUTE_COPY's turning maneuver): the target moves at it, and the view should too"""
        r_ = 0.0 if rate is None else np.asarray(rate, np.float32)[:, None]
        c_ = cands[None, :].astype(np.float32)
        m_ = np.repeat(vel[:, None], len(cands), 1).astype(np.float32)
        h_ = np.repeat(hb[:, None], len(cands), 1).astype(np.float32)
        e_ = np.repeat(err[:, None], len(cands), 1).astype(np.float32)
        sm_ = np.where(np.abs(c_) <= 1.0, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH).astype(np.float32)
        p_ = None if pit is None else np.repeat(pit[:, None], len(cands), 1).astype(np.float32)
        v_ = m_
        for _ in range(max(1, RJ_COPY_H)):
            m_ = sm_ * m_ + (1.0 - sm_) * c_
            if cap is not None:
                m_ = np.clip(m_, -cap, cap)
            if HAND_BAND:
                k_ = (1.0 - np.exp(-2.0 * np.pi * (HB_FC + HB_BETA * np.abs(h_)) * DT)).astype(np.float32)
                h_ = h_ + k_ * (m_ - h_)
                v_ = h_
            else:
                v_ = m_
            if p_ is None:
                e_ = e_ - v_ + r_
            else:                                           # (the pitch: the ease toward level, then the movement)
                p1_ = np.clip(p_ * lev[:, None] + v_, -89.0, 89.0)
                e_ = e_ - (p1_ - p_)
                p_ = p1_
        hold_ = 0.0 if p_ is None else p_ * (1.0 - lev[:, None])      # (the pitch: the movement that holds it where it is)
        return np.argmin(np.abs(e_ - RJ_COPY_VW * (v_ - hold_ - r_)), 1)

    def rj_copy_label(self):
        """(RJ_COPY) per player and output the scripted runner's choice for his next frame (see RJ_COPY; -1: no label), from
        the state as the frame ends; reads only, changes nothing (no random draw)"""
        n = self.n
        lab = np.full((n, RJC_HEADS), -1, np.int8)
        self.rjc_lab = lab
        if not (self.rj_live and self.rjrun.any()):
            self.rjc_up[:] = 99
            return lab
        s = self.state
        ar = np.arange(n)
        kk_ = np.minimum(self.rjrun_k, len(self.rj_a) - 1)
        A_, B_ = self.rj_a[kk_], self.rj_b[kk_]
        p_, v_ = s[:, :3], s[:, 3:6]
        floor_ = s[:, 6] > 0.5
        dxy_ = np.hypot(p_[:, 0] - A_[:, 0], p_[:, 1] - A_[:, 1])
        own_ = self.rjrun & (self.script == 0) & (self.hp > 0)
        # frames since he left the floor on the runner's "jump and fire" (the label of the last frame): 0 on the frame he is
        # first in the air after it, counted on in the air; 99 on the floor, or in the air without it (a step down, a fall)
        up_ = np.where(floor_, 99, np.where(self.rjc_up < 99, self.rjc_up + 1, np.where(self.rjc_go, 0, 99)))
        self.rjc_up = np.where(own_, up_, 99).astype(np.int64)
        flight_ = own_ & ~floor_ & (self.rjc_up < 99)       # in the air from the take-off
        band_ = np.abs(p_[:, 2] - A_[:, 2]) < 64.0           # (the take-off is on a stair: 40 units of fall within 48 of it)
        ground_ = floor_ & band_ & (dxy_ <= RJ_COPY_FAR)     # on his way to the take-off: on the floor about it,
        near_air_ = ~floor_ & ~flight_ & band_ & (dxy_ <= RJ_COPY_FAR)   # or in the air there (a step down)
        on_ = own_ & (flight_ | ground_ | near_air_) & ~(flight_ & (p_[:, 2] < A_[:, 2] - 64.0))
        self.rjc_go = np.zeros(n, bool)
        if not on_.any():
            return lab
        yaw0_ = np.degrees(np.arctan2(B_[:, 1] - A_[:, 1], B_[:, 0] - A_[:, 0]))
        eyaw_ = ((yaw0_ - self.yaw + 180.0) % 360.0) - 180.0
        epit_ = RJ_COPY_PITCH - self.pitch
        lev_ = np.where(self.seen_t > 0.5, self.level, 1.0).astype(np.float32)
        if RJ_LOOK_FREE > 0:
            lev_ = np.where(self.rjrun, 1.0, lev_).astype(np.float32)
        hb_ = self.hb if HAND_BAND else self.mv
        ti_ = self._rjc_pick(self.mv[:, 0], hb_[:, 0], eyaw_, TURN, lev_, TURN_CAP if self.human_aim else None, None)
        pi_ = self._rjc_pick(self.mv[:, 1], hb_[:, 1], epit_, PITCH, lev_, None, self.pitch.astype(np.float32))
        # the keys on the floor: toward the take-off, aiming where his speed would stop him (Quake's friction: 6 a second, a
        # stop speed of 100), in the view's frame (forward along the view's yaw, right 90 degrees to its right)
        sp_ = np.hypot(v_[:, 0], v_[:, 1])
        dst_ = np.maximum(sp_ - 100.0, 0.0) / 6.0 + np.minimum(sp_, 100.0) ** 2 / 1200.0
        u_ = v_[:, :2] / np.maximum(sp_, 1e-3)[:, None]
        stop_ = p_[:, :2] + u_ * dst_[:, None]
        e_ = A_[:, :2] - stop_
        yr_ = np.radians(self.yaw)
        fe_ = e_[:, 0] * np.cos(yr_) + e_[:, 1] * np.sin(yr_)
        se_ = e_[:, 0] * np.sin(yr_) - e_[:, 1] * np.cos(yr_)
        fk_ = np.where(fe_ > RJ_COPY_DEAD, 2, np.where(fe_ < -RJ_COPY_DEAD, 0, 1))
        sk_ = np.where(se_ > RJ_COPY_DEAD, 2, np.where(se_ < -RJ_COPY_DEAD, 0, 1))
        ready_ = (self.weapon == RL) & (self.ammo[ar, RL] >= 1) & self.has[ar, RL] & (self.cool <= DT + 1e-4)
        go_ = (on_ & ground_ & (dxy_ < RJ_COPY_R) & (sp_ < RJ_COPY_V) & (np.abs(eyaw_) < RJ_COPY_YAW)
               & (np.abs(epit_) < RJ_COPY_PTOL) & ready_)
        self.rjc_go = go_.copy()
        # (within RJ_COPY_R he stops: no key until he is slow enough; further out the keys toward the take-off)
        inr_ = dxy_ < RJ_COPY_R * 0.75
        fk_ = np.where(inr_ & (np.hypot(e_[:, 0], e_[:, 1]) < RJ_COPY_R * 0.75), 1, fk_)
        sk_ = np.where(inr_ & (np.hypot(e_[:, 0], e_[:, 1]) < RJ_COPY_R * 0.75), 1, sk_)
        shot_ = self.ammo[ar, RL] < self.rjc_ammo0 - 0.5     # the try's rocket is out
        late_ = flight_ & (self.rjc_up <= RJ_COPY_LATE) & ~shot_ & ready_
        fwd_ = np.where(flight_, 2, np.where(go_, 2, fk_))
        side_ = np.where(flight_ | go_, 1, sk_)
        vert_ = np.where(go_ & ground_, 1, 0)
        fire_ = (go_ | late_).astype(np.int64)
        wpn_ = np.where(self.weapon == RL, 0, RL + 1)
        walk_ = (~flight_ & ~go_).astype(np.int64)           # (on his way to the take-off he walks: slow enough to stop on it)
        cols_ = (fwd_, side_, vert_, ti_, pi_, fire_, wpn_, walk_, np.zeros(n, np.int64))
        for j_, c_ in enumerate(cols_):
            lab[:, j_] = np.where(on_, c_, -1)
        self.rjc_lab = lab
        if "rj_copy" not in self.stats:
            self.stats["rj_copy"] = np.zeros(6)
        self.stats["rj_copy"][0] += float((on_ & self._counted(ar)).sum())
        return lab

    def _rc_close(self, i):
        """(ROUTE_COPY) player i's try ends (a new one begins): counted for his counted seats"""
        if self.rc_live[i] and self.rc_r[i] >= 0:
            if "route_copy" not in self.stats:
                self.stats["route_copy"] = np.zeros((len(self.rc["routes"]), 5))
            fell_ = (not self.jrun_over[i]) and float(self.state[i, 2]) < min(float(self.rc["A"][2]), float(self.rc["B"][2])) - 90.0
            self.stats["route_copy"][int(self.rc_r[i]), 1:5] += (1.0, float(self.jrun_over[i]), float(self.rc_arr[i]), float(fell_))
        self.rc_live[i], self.rc_arr[i] = False, False

    def route_copy_label(self):
        """(ROUTE_COPY) per player and output the scripted runner's choice for his next frame (see ROUTE_COPY; -1: none),
        from the state as the frame ends; changes only the runner's own bookkeeping (no random draw)"""
        n = self.n
        lab = np.full((n, RJC_HEADS), -1, np.int8)
        C = self.rc
        who = np.nonzero(self.jrun & (self.rc_r >= 0) & (self.jrun_k == C["k"]) & (self.script == 0) & (self.hp > 0))[0]
        if not len(who):
            return lab
        s = self.state
        A, B, RA = C["A"], C["B"], C["RA"]
        p, v = s[who, :3], s[who, 3:6]
        gr = s[who, 6] > 0.5
        sp = np.hypot(v[:, 0], v[:, 1])
        dA = np.hypot(p[:, 0] - A[0], p[:, 1] - A[1])
        ph = self.rc_ph[who].copy()
        # the phase from his state: in the air after the runner's jump, the hop's (hop2, not yet hopped) or the gap's flight
        rts = C["routes"]
        hops = np.array([rts[int(r_)]["hops"] for r_ in self.rc_r[who]])
        up_ = ~gr & self.rc_jmp[who] & (v[:, 2] > 100.0)
        ph = np.where(up_ & (ph <= 1) & (hops == 2), 2, ph)
        ph = np.where(up_ & (ph <= 1) & (hops == 1), 3, ph)
        bounce_ = (self.rc_vz[who] < 0.0) & (v[:, 2] > 100.0)               # (down and up again inside one frame: AUTO_HOP)
        down_ = self.rc_down[who] | ((ph == 2) & gr)
        ph = np.where((ph == 2) & ((down_ & ~gr & (v[:, 2] > 100.0)) | bounce_), 3, ph)   # (up again from the hop's landing: the gap jump)
        over_ = gr & (np.linalg.norm(p - B, axis=1) < 110.0) & (p[:, 2] > B[2] - 40.0)
        ph = np.where((ph == 3) & over_, 4, ph)
        ph = np.where(self.jrun_over[who] | self.jrun_past[who], np.maximum(ph, 4), ph)
        basin_ = np.array([np.hypot(*(rts[int(r_)]["start"][:2] - p[j_, :2])) < 250.0 for j_, r_ in enumerate(self.rc_r[who])])             & (np.abs(p[:, 2] - A[2]) < 40.0)                # (near the staging spot, on its level; elsewhere: along his try's way)
        off_ = (dA > ROUTE_COPY_FAR) | ((ph == 3) & gr & ~over_)
        off_ |= (ph == 4) & (p[:, 2] < B[2] - 40.0)
        fwd = np.ones(len(who), np.int64)
        side = np.ones(len(who), np.int64)
        jmp = np.zeros(len(who), np.int64)
        walk = np.zeros(len(who), np.int64)
        tyaw = self.yaw[who].astype(np.float64).copy()
        trate = np.zeros(len(who), np.float32)               # (the maneuver's turn rate, degrees a frame)
        idx = self.rc_i[who].copy()
        for j, i in enumerate(who):
            R = rts[int(self.rc_r[i])]
            if ph[j] <= 1 and not basin_[j]:                 # (far from the staging spot: along the way of his try, as fast as he
                ph[j] = 0                                    # runs, the view toward the way two spots ahead)
                X_ = self.jfields[int(self.jrun_f[i])] if int(self.jrun_f[i]) < len(self.jfields) else self.route
                g_ = int(self.rc_g[i])
                nd_ = int(X_.locate(p[j:j + 1])[0])
                n1_ = int(X_.next[g_, nd_]) if g_ < X_.next.shape[0] else -1
                n2_ = int(X_.next[g_, n1_]) if n1_ >= 0 else -1
                q_ = X_.nodes[n2_ if n2_ >= 0 else (n1_ if n1_ >= 0 else nd_)]
                ji_ = getattr(X_, "ji", None)
                near_jump_ = ji_ is not None and g_ < ji_.shape[0] and int(ji_[g_, nd_]) == C["k"] and float(X_.jd[g_, nd_]) < 400.0
                jl_ = getattr(X_, "jlink", None)
                if jl_ is not None and g_ < jl_.shape[0] and (int(jl_[g_, nd_]) >= 0 or (n1_ >= 0 and int(jl_[g_, n1_]) >= 0)):
                    near_jump_ = True                        # (the way's next step is a jump: not off the edge, to the staging spot)
                if n1_ < 0 or near_jump_ or np.hypot(*(q_[:2] - p[j, :2])) < 8.0:
                    q_ = R["start"]
                tyaw[j] = math.degrees(math.atan2(q_[1] - p[j, 1], q_[0] - p[j, 0]))
                fwd[j] = 2
            elif ph[j] <= 1 and gr[j]:
                d_ = np.linalg.norm(R["p"][:, :2] - p[j, :2], axis=1) + 0.1 * np.linalg.norm(R["v"][:, :2] - v[j, :2], axis=1)
                if ph[j] == 1:                               # the maneuver: the nearest of the next few reference frames
                    lo_ = int(idx[j])
                    hi_ = min(len(d_), lo_ + 8)
                    w_ = d_[lo_:hi_]
                    t_ = lo_ + int(np.nonzero(w_ <= w_.min() + 1.0)[0].max())    # (of equals the furthest on)
                    if d_[t_] > ROUTE_COPY_TOL:
                        ph[j] = 0                            # off it: back to the staging spot
                    else:
                        idx[j] = t_
                if ph[j] == 0:
                    e_ = R["start"][:2] - p[j, :2]
                    ey_ = ((R["syaw"] - float(self.yaw[i]) + 180.0) % 360.0) - 180.0
                    if np.hypot(*e_) < ROUTE_COPY_STAGE and sp[j] < 30.0 and abs(ey_) < ROUTE_COPY_SYAW:
                        ph[j], idx[j] = 1, 0                 # at the staging spot, slow and facing: the maneuver begins
                    else:
                        u_ = v[j, :2] / max(sp[j], 1e-3)
                        st_ = np.maximum(sp[j] - 100.0, 0.0) / 6.0 + min(sp[j], 100.0) ** 2 / 1200.0
                        e_ = R["start"][:2] - (p[j, :2] + u_ * st_)
                        yr_ = math.radians(float(self.yaw[i]))
                        fe_ = e_[0] * math.cos(yr_) + e_[1] * math.sin(yr_)
                        se_ = e_[0] * math.sin(yr_) - e_[1] * math.cos(yr_)
                        near_ = np.hypot(*e_) < ROUTE_COPY_STAGE * 0.75
                        fwd[j] = 1 if near_ else (2 if fe_ > RJ_COPY_DEAD else (0 if fe_ < -RJ_COPY_DEAD else 1))
                        side[j] = 1 if near_ else (2 if se_ > RJ_COPY_DEAD else (0 if se_ < -RJ_COPY_DEAD else 1))
                        walk[j] = 1 if np.hypot(*(R["start"][:2] - p[j, :2])) < 160.0 else 0
                        tyaw[j] = R["syaw"]
                if ph[j] == 1:
                    t_ = int(idx[j])
                    fwd[j], side[j] = int(R["k"][t_, 0]), int(R["k"][t_, 1])
                    last_ = len(R["p"]) - 1
                    past_ = float(np.dot(p[j, :2] - R["p"][last_, :2], C["U"])) > -4.0
                    jmp[j] = 1 if (t_ >= last_ or past_ or R["k"][t_, 2] == 1) else 0
                    ty_ = float(R["yaw"][min(last_, t_ + ROUTE_COPY_LEAD)])
                    trate[j] = float(R["yaw"][min(last_, t_ + 1)] - R["yaw"][t_]) if t_ < last_ else 0.0
                    if sp[j] > 100.0 and np.hypot(*R["v"][t_, :2]) > 100.0:     # (turned as his velocity is turned from the reference's)
                        dh_ = math.degrees(math.atan2(v[j, 1], v[j, 0]) - math.atan2(R["v"][t_, 1], R["v"][t_, 0]))
                        ty_ += ((dh_ + 180.0) % 360.0) - 180.0
                    tyaw[j] = ty_
            elif ph[j] in (2, 3) or (ph[j] <= 1 and not gr[j]):
                if ph[j] <= 1:                               # (in the air on his way to the staging spot or in the maneuver: as it was)
                    fwd[j], side[j] = 1, 1
                    tyaw[j] = R["syaw"] if ph[j] == 0 else float(R["yaw"][min(len(R["p"]) - 1, int(idx[j]) + ROUTE_COPY_LEAD)])
                    if ph[j] == 1:
                        fwd[j], side[j] = int(R["k"][int(idx[j]), 0]), int(R["k"][int(idx[j]), 1])
                else:
                    tg_ = C["hop_tgt"] if ph[j] == 2 else B[:2]
                    tgt_ = math.degrees(math.atan2(tg_[1] - p[j, 1], tg_[0] - p[j, 0]))
                    hv_ = math.degrees(math.atan2(v[j, 1], v[j, 0])) if sp[j] > 30 else tgt_
                    err_ = ((tgt_ - hv_ + 180.0) % 360.0) - 180.0
                    sd_ = int(self.rc_side[i])
                    if abs(err_) > ROUTE_COPY_HYST:
                        sd_ = 1 if err_ < 0 else -1
                    self.rc_side[i] = sd_
                    tyaw[j] = float(rc_steer(v[j:j + 1], np.array([tgt_]), sd_, np.array([False]), ROUTE_COPY_MARGIN + ROUTE_COPY_GAIN * abs(err_))[0])
                    fwd[j], side[j] = 2, 1 + sd_
                    if ph[j] == 2:                           # (the jump held as he comes down: the gap jump on the landing)
                        jmp[j] = 1 if (v[j, 2] < 0.0 or gr[j]) else 0
                if ph[j] == 2 and gr[j]:
                    jmp[j] = 1
            else:                                            # (4) over the gap: onto the armor
                tyaw[j] = math.degrees(math.atan2(RA[1] - p[j, 1], RA[0] - p[j, 0]))
                fwd[j] = 2
        self.rc_ph[who], self.rc_i[who] = ph, idx
        self.rc_vz[who] = v[:, 2]
        self.rc_down[who] = down_ & (ph == 2)
        self.rc_jmp[who] = (jmp == 1) & ~off_
        ey = (((tyaw - self.yaw[who]) + 180.0) % 360.0) - 180.0
        lev_ = np.where(self.seen_t[who] > 0.5, self.level, 1.0).astype(np.float32)
        hb_ = self.hb if HAND_BAND else self.mv
        ti = self._rjc_pick(self.mv[who, 0], hb_[who, 0], ey.astype(np.float32), TURN, lev_, TURN_CAP if self.human_aim else None, None, rate=trate)
        pi = self._rjc_pick(self.mv[who, 1], hb_[who, 1], (0.0 - self.pitch[who]).astype(np.float32), PITCH, lev_, None,
                            self.pitch[who].astype(np.float32))
        wpn = np.zeros(len(who), np.int64)
        cols = (fwd, side, jmp, ti, pi, np.zeros(len(who), np.int64), wpn, walk, np.zeros(len(who), np.int64))
        for c_, x_ in enumerate(cols):
            lab[who, c_] = np.where(off_, -1, x_)
        cnt_ = ~off_ & self._counted(who)
        if "route_copy" not in self.stats:
            self.stats["route_copy"] = np.zeros((len(rts), 5))
        np.add.at(self.stats["route_copy"][:, 0], self.rc_r[who][cnt_], 1.0)
        return lab

    def rj_teach_label(self):
        """(RJ_TEACH) per player 1 where the label says "jump and fire now" for the next frame (see RJ_TEACH), from the
        state as the frame ends; reads only, changes nothing"""
        lab = np.zeros(self.n, np.int8)
        if not (self.rj_live and self.rjrun.any()):
            self.rj_lab = lab
            return lab
        s = self.state
        kk_ = self.rjrun_k
        A_ = self.rj_a[np.minimum(kk_, len(self.rj_a) - 1)]
        dxy_ = np.hypot(s[:, 0] - A_[:, 0], s[:, 1] - A_[:, 1])
        dz_ = np.abs(s[:, 2] - A_[:, 2]) < 30.0
        ar = np.arange(self.n)
        own_ = self.rjrun & (self.script == 0) & (self.hp > 0)
        floor_ = own_ & (s[:, 6] > 0.5) & dz_
        near_ = floor_ & (dxy_ < RJ_TEACH_R)
        ready_ = near_ & (self.weapon == RL) & (self.ammo[ar, RL] >= 1) & self.has[ar, RL] & (self.cool <= DT + 1e-4)
        ok_ = ready_ & (self.pitch >= RJ_TEACH_PITCH)
        lab[ok_] = 1
        self.rj_lab = lab
        if "rj_near" not in self.stats:                     # (counted seats) his frames in the tries, on the floor within RJ_EDGE of the
            self.stats["rj_near"] = np.zeros(7)             # take-off, within RJ_TEACH_R, with the launcher ready, labelled; the sums of his
        c_ = self._counted(ar)                              # view's pitch on the floor within RJ_TEACH_R and within RJ_EDGE
        edge_ = floor_ & (dxy_ < RJ_EDGE)
        self.stats["rj_near"] += np.array([(own_ & c_).sum(), (edge_ & c_).sum(), (near_ & c_).sum(), (ready_ & c_).sum(), (ok_ & c_).sum(),
                                           self.pitch[near_ & c_].sum(), self.pitch[edge_ & c_].sum()], np.float64)
        return lab

    def _rj_place(self, i):
        """a rocket jump run (RJ_RUN_P): player i begins a try 30 to 90 units of floor before the take-off of one of the pros'
        rocket jumps (every one as often as any other), facing its landing, the rocket launcher in his hand, the pros'
        health and armor at that take-off; his target is the landing (the item row of the try's ways that leads there)"""
        k = int(self.rng.integers(len(self.rjs)))
        r, X, g, st = self.rjs[k], self.rj_fields[k], self.rj_g[k], self.rj_start[k]
        node = int(st[int(self.rng.integers(len(st)))])
        p = X.nodes[node]
        nx = int(X.next[g, node])
        q = X.nodes[nx] if (nx >= 0 and X.jlink[g, node] < 0 and np.hypot(*(r["a"][:2] - p[:2])) > 120.0) else r["b"]   # (near it: toward the landing)
        face = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) + float(self.rng.uniform(-15, 15))
        self.w.reset(i, (p[0], p[1], p[2] + 9.0), (0, 0, 0), face)
        self._fresh(i, face)
        self.ra[i] = False                                  # (his rockets of the last try are gone with it)
        if self.rng.random() < RJ_LOOK_P:                   # (RJ_LOOK_P) his view already down at the pros' look-down
            self.pitch[i] = float(np.clip(r.get("look", r["pitch"]) + self.rng.uniform(-5, 5), 0.0, 89.0))   # (RJ_LOOK_CLEAR: "look")
        self.hp[i], self.armor[i] = RJM.stack(r["stack"])
        self.has[i] = False
        self.ammo[i] = 0.0
        self.has[i, ALWAYS] = True
        self.has[i, MG], self.has[i, RL] = True, True
        self.ammo[i, MG], self.ammo[i, RL] = LOADOUTS["all"][1][MG], RJ_AMMO
        self.weapon[i] = RL
        m = self._match_of(i)
        self.item_up[m, self.route_item[g]], self.item_t[m, self.route_item[g]] = True, 0.0
        self.run_k[i] = INTENTS.index(self.route_goal[g])
        self.intent_new[i], self.intent_done[i] = True, True     # the target is read at once
        self.rjrun_k[i] = k
        self.rjrun_t[i] = float(X.T[g, int(X.locate(p[None])[0])]) + RJ_TRY
        self.rjrun_edge[i], self.rjrun_new[i] = False, True
        self.rjrun_air[i], self.rjrun_from[i] = 0, False
        if g < self.bel_t.shape[1]:
            self.bel_t[i, g] = 99.0                         # ... and he knows the row's item is there (its inputs say "up")
        self._replaced = True
        if self._counted(i):
            self.stats["rj_tries"][min(k, 63)] += 1
        if RJ_COPY:                                          # (RJ_COPY) the try's start: his stack and rockets, for its end
            self.rjc_hp0[i], self.rjc_ammo0[i] = float(self.hp[i] + self.armor[i]), float(self.ammo[i, RL])
            self.rjc_live[i], self.rjc_up[i], self.rjc_go[i] = bool(self._counted(i)), 99, False

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
        if ok and RUN_TARGET_W and self.run_tw is not None:  # (RUN_TARGET_W) by the map's weights (evenly if none of them is here)
            w_ = np.array([self.run_tw.get(int(k), 0.0) for k in ok], np.float64)
            self.run_k[i] = int(ok[int(self.rng.choice(len(ok), p=w_ / w_.sum()))]) if w_.sum() > 0 else int(self.rng.choice(ok))
            self.stats["run_item"][1 + int(self.run_k[i])] += 1
            self.intent_new[i], self.intent_done[i] = True, True
            return
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
    def _hop_quiet(self, s):
        """(HOP_QUIET) bool [players]: by his own senses the enemy is near (heard in the last HOP_QUIET_HEARD seconds, believed
        within HOP_QUIET_NEAR units) or his intention is one of the map's holding places"""
        q_ = (self.v02_ht < HOP_QUIET_HEARD).any(1) if getattr(self, "v02_ht", None) is not None else np.zeros(self.n, bool)
        if getattr(self, "v02_bel", None) is not None:
            q_ = q_ | (np.asarray(self.v02_bel_ok, bool) & (np.linalg.norm(self.v02_bel - s[:, :3], axis=1) < HOP_QUIET_NEAR))
        if self.hold_n:
            q_ = q_ | ((self.intent >= HOLD_INTENT) & (self.intent < HOLD_INTENT + HOLD_SLOTS))
        return q_

    def _rg_far(self, s, sc_, w_, cost_):
        """(RG_FAR_PRICE) the shot prices cost_ of the shooters sc_ (weapons w_) with the railgun's far shots at the fixed
        price: the nearest living enemy past RG_FAR_DIST (3D, origin to origin)"""
        st = self.stats.get("rg_far")
        if st is None:                                       # (also when turned on by live.json in a running simulator)
            st = self.stats["rg_far"] = np.zeros(4)
        oth_ = self._others_arr()[sc_]
        d_ = np.linalg.norm(s[oth_, :3] - s[sc_, None, :3], axis=2)
        d_ = np.where(self.hp[oth_] > 0, d_, np.inf).min(1)
        far_ = (w_ == RG) & np.isfinite(d_) & (d_ > RG_FAR_DIST)
        st[0] += int(((w_ == RG) & np.isfinite(d_)).sum())  # rail shots with an enemy alive, far ones, their price, the
        st[1] += int(far_.sum())                             # price SHOT_COST would have asked for them
        st[3] += float(cost_[far_].sum())
        cost_ = np.where(far_, np.float32(RG_FAR_PRICE), cost_).astype(cost_.dtype)
        st[2] += float(cost_[far_].sum())
        return cost_

    def _big_seq(self, i, b_, had):
        """(BIG_PICK_SEQ) player i picks up the big weapon b_ (0 rocket launcher, 1 lightning gun, 2 railgun; had: he held
        it before the pickup): the pay by order, and the weapon marked as got this life"""
        st = self.stats.get("big_seq")
        if st is None:                                       # (also when turned on by live.json in a running simulator)
            st = self.stats["big_seq"] = np.zeros(6)
        own_ = self.big_got[i] | self.has[i, [RL, LG, RG]]
        own_[b_] = self.big_got[i, b_] or had
        self.big_got[i, b_] = True
        if own_[b_]:
            return 0.0
        k_ = int(own_.sum())                                 # the big ones he had before: 0 = this is his first
        p_ = float(BIG_PICK_SEQ[k_]) if k_ < len(BIG_PICK_SEQ) else 0.0
        st[k_] += 1
        st[3 + k_] += p_
        return p_

    def _hop_chain(self, s, prev, jump, human, pkind, in_run):
        """(HOP_CHAIN) this frame's chains of hops: the state after the frame s, before it prev, the jump key as moved (jump:
        upmove), the network's seats (human), the round kinds and runs. Returns the pay [players] float32 (see HOP_CHAIN)."""
        n = self.n
        st = self.stats.get("hop_chain")
        if st is None:                                       # (turned on by live.json in a running simulator)
            st = self.stats["hop_chain"] = np.zeros(len(HC_COLS) + HC_BINS)
        C = {k_: i_ for i_, k_ in enumerate(HC_COLS)}
        H0 = len(HC_COLS)
        hv = np.hypot(s[:, 3], s[:, 4]).astype(np.float32)
        up = human & (self.hp > 0)
        L = self.hc_len
        giv = (hv > self.hc_sp + HOP_GIVEN) & (L > 0)        # speed given in one frame: not a hop's
        self.hc_sp = hv
        gr = s[:, 6] > 0.5
        self.hc_gnd = np.where(gr, self.hc_gnd + 1, 0)
        long_ = gr & (self.hc_gnd * DT * 1000.0 > HOP_CHAIN_MS + 0.5)    # on the ground too long since the landing
        inv_ = np.asarray(self.visible, bool)[:n] | np.asarray(getattr(self, "acquired", np.zeros(n, bool)), bool)[:n]   # the enemy in his view
        end_ = (L > 0) & (giv | long_ | ~up | inv_)
        st[C["ended_view"]] += float(((L > 0) & inv_ & ~giv & ~long_ & up).sum())
        np.add.at(st, H0 + np.minimum(L[end_], HC_BINS) - 1, 1.0)
        L = np.where(end_, 0, L)
        best = np.where(end_, 0.0, self.hc_best).astype(np.float32)
        off_all = ((jump > 0) & ~gr & (s[:, 5] > 100.0) & (s[:, 5] < HOP_VZ) & ((prev[:, 6] > 0.5) | (prev[:, 5] <= 0.0)) & up)   # a take-off
        off = off_all & ~inv_                                # (in view: nothing begins, nothing is kept)
        ch_ = off & (L > 0)                                  # ... in a chain: its landing was at most HOP_CHAIN_MS before
        gain = ch_ & (hv > best)
        kept = ch_ & ~gain & (hv >= best - HOP_CHAIN_TOL)
        lost = ch_ & ~gain & ~kept
        np.add.at(st, H0 + np.minimum(L[lost], HC_BINS) - 1, 1.0)
        start = off & ~gain & ~kept                          # a chain begins (or begins again after a loss): unpaid
        L = np.where(gain | kept, L + 1, np.where(start, 1, L))
        self.hc_best = np.where(gain | start, hv, best).astype(np.float32)
        self.hc_len = L
        ok = ((pkind == NORMAL) & ~in_run & ~inv_) | (in_run & ~self.jrun & ~self.rjrun & ~inv_)    # games with nobody in view, item runs
        if HOP_QUIET:
            ok = ok & ~self._hop_quiet(s)
        mult = np.minimum(HOP_CHAIN_CAP, 1.0 + HOP_CHAIN_STEP * (L - 2))
        sp_ = np.clip((hv - SPEED_LO) / (SPEED_HI - SPEED_LO), 0.0, 1.0)
        pd_ = (gain | kept) & ok & (sp_ > 0)
        pay = np.where(pd_, HOP_CHAIN * mult * sp_, 0.0).astype(np.float32)
        st[[C["takeoffs"], C["starts"], C["gained"], C["kept"], C["lost"], C["paid"], C["pay"], C["kept_unpaid"]]] += (
            off.sum(), start.sum(), gain.sum(), kept.sum(), lost.sum(), pd_.sum(), float(pay.sum()), ((gain | kept) & ~pd_).sum())
        st[[C["takeoffs_view"], C["frames_view"], C["frames"]]] += ((off_all & inv_).sum(), (up & inv_).sum(), up.sum())
        return pay

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
        if JE_ON and getattr(self, "je_rng", None) is not None:      # (JUMP_EVERY) the jump read between the hand's readings: down where he
            btw_ = who & ~dec & (self.je_rng.random(len(a)) < JUMP_EVERY)   # asks for it now, his hand's crouch (its last reading) kept
            self.key_jump = btw_.copy()                      # where he does not
            v_ = np.where(btw_, np.where(a[:, 2] == 1, 1, np.where(self.key_req[:, 2] == 2, 2, 0)), self.key_req[:, 2])
            self.stats["key_asked"] += int((((v_ == 1) != (self.key_last[:, 2] == 1)) & btw_).sum())
            a[:, cols] = np.where(who[:, None], self.key_req, a[:, cols])
            a[:, 2] = np.where(who, v_, a[:, 2])
        else:
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
        if JE_ON and "jump_every" in self.stats:            # (JUMP_EVERY) the thumb's presses and releases, between the hand's readings and on them
            btw_ = who & ~dec & self.key_jump
            self.stats["jump_every"] += np.array([btw_.sum(), (btw_ & j_new & ~j_now).sum(), (who & dec & j_new & ~j_now).sum(),
                                                  (btw_ & ~j_new & j_now).sum(), (who & dec & ~j_new & j_now).sum()], np.float64)
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

    def _trk_on(self, foe, grp):
        """(TRACK_TRUTH) [n] bool: a duel's game with both players alive and in play (as PREAIM_PAY's `both`)"""
        n = self.n
        if self._others_arr().shape[1] != 1 or self.lab is not None or self.fixed_kind is not None:
            return np.zeros(n, bool)
        game = (self.kind[grp] == NORMAL) & (self.mode[grp] < 0) & (self.run_k[:n] < 0) & (self.run_k[foe] < 0)
        rw_ = getattr(self, "rsp_wait", None)
        alive = (self.hp[:n] > 0) & ((np.asarray(rw_[:n]) <= 0) if rw_ is not None else True)
        return game & alive & alive[foe]

    def _trk_step(self):
        """(TRACK_TRUTH) once a frame, after the senses: the seconds since each player last had the enemy in view (60 from
        the enemy's spawn until he is seen). State kept for aux() only: nothing else reads it"""
        n = self.n
        foe = getattr(self, "foe", None)
        if foe is None:
            foe = self._others_arr()[:, 0]
        vis = np.asarray(self.visible, bool)[:n]
        life = np.asarray(self.life_t[:n], np.float64)
        if getattr(self, "trk_unseen", None) is None or len(self.trk_unseen) != n:
            self.trk_unseen = np.full(n, TRACK_UNSEEN_CAP)
            self.trk_life = life.copy()
        born = life[foe] < self.trk_life[foe]                # (the enemy's life clock began again: he spawned)
        gone = (self.hp[foe] <= 0) | born
        u_ = np.where(vis, 0.0, np.minimum(self.trk_unseen + DT, TRACK_UNSEEN_CAP))
        self.trk_unseen = np.where(gone & ~vis, TRACK_UNSEEN_CAP, u_)
        if TRACK_Z:                                          # (TRACK_Z) every player's horizontal velocity, the last TRACK_Z_WIN frames
            new_ = life < self.trk_life                      # (of his life: a spawn clears his rows)
            if getattr(self, "trk_vh", None) is None or self.trk_vh.shape[1] != n:
                self.trk_vh = np.zeros((TRACK_Z_WIN, n, 2))
                self.trk_vc = np.zeros(n)
                self.trk_vi = 0
            self.trk_vh[:, new_] = 0.0
            self.trk_vc[new_] = 0.0
            self.trk_vh[self.trk_vi % TRACK_Z_WIN] = np.asarray(self.state[:n, 3:5], np.float64)
            if getattr(self, "trk_zseen", None) is None or len(self.trk_zseen) != n:
                self.trk_zseen = np.full(n, -1, np.int64)
            if self.zones is not None:                       # (the zone he last saw the enemy in; the enemy's spawn forgets it)
                zf_ = self.zones.locate(self.state[foe, :3])
                self.trk_zseen = np.where(vis, zf_, np.where(gone, -1, self.trk_zseen))
            self.trk_vi += 1
            self.trk_vc = np.minimum(self.trk_vc + 1.0, TRACK_Z_WIN)
        self.trk_life = life.copy()

    def _race_cols(self, out, C, s, foe):
        """(TRACK_RACE) aux()'s columns of the item race (see TRACK_RACE): reads only"""
        n = self.n
        for k_, (cm_, ce_) in ((1, ("race_me_mh", "race_en_mh")), (2, ("race_me_ra", "race_en_ra"))):
            out[:, C[cm_]] = RACE_CAP
            out[:, C[ce_]] = RACE_CAP
            if self.route is None:
                continue
            gs_ = self.intent_more.get(k_)
            if gs_ is None:
                gs_ = np.array([self.intent_gi[k_]] if self.intent_gi[k_] >= 0 else [], np.int64)
            gs_ = gs_[gs_ < len(self.route.T)]
            if not len(gs_):
                continue
            nm_ = self.route.locate(s[:n, :3])
            ne_ = self.route.locate(s[foe, :3])
            out[:, C[cm_]] = np.minimum(self.route.T[gs_][:, nm_].min(0), RACE_CAP)
            out[:, C[ce_]] = np.minimum(self.route.T[gs_][:, ne_].min(0), RACE_CAP)

    def _trk_cols(self, out, C, s, foe, grp, c, si):
        """(TRACK_TRUTH) aux()'s columns of the belief readout (see TRACK_TRUTH): reads only"""
        n = self.n
        ar = np.arange(n)
        vf_ = np.asarray(s[foe, 3:5], np.float64)
        out[:, C["en_vfwd"]] = c * vf_[:, 0] + si * vf_[:, 1]
        out[:, C["en_vleft"]] = -si * vf_[:, 0] + c * vf_[:, 1]
        for w_ in TRACK_OWN:
            out[:, C["en_own_" + w_]] = np.asarray(self.has[foe, WEAPONS.index(w_)], np.float32)
        out[:, C["trk_on"]] = self._trk_on(foe, grp)
        u_ = getattr(self, "trk_unseen", None)
        out[:, C["unseen_s"]] = u_ if (u_ is not None and len(u_) == n) else TRACK_UNSEEN_CAP
        bel_ = getattr(self, "v02_bel", None)
        if bel_ is not None and len(bel_) == n:
            d_ = np.asarray(bel_, np.float64) - s[:, :3]
            ok_ = np.asarray(self.v02_bel_ok, bool)
            out[:, C["bel_ok"]] = ok_
            out[:, C["bel_fwd"]] = np.where(ok_, c * d_[:, 0] + si * d_[:, 1], 0.0)
            out[:, C["bel_left"]] = np.where(ok_, -si * d_[:, 0] + c * d_[:, 1], 0.0)
            out[:, C["bel_up"]] = np.where(ok_, d_[:, 2], 0.0)
            bt_ = getattr(self, "v02_bt_now", None)
            out[:, C["bel_age"]] = np.asarray(bt_, np.float32) if bt_ is not None and len(bt_) == n else -1.0
        else:
            out[:, C["bel_age"]] = -1.0
        if EN_STACK and getattr(self, "es_h", None) is not None:
            k_ = self._slot(foe)
            out[:, C["es_stack"]] = self.es_h[ar, k_] + self.es_a[ar, k_]
        else:
            out[:, C["es_stack"]] = -1.0
        if TRACK_RACE:                                       # (TRACK_RACE) the seconds of way to the mega and the red armor
            self._race_cols(out, C, s, foe)
        if TRACK_Z:                                          # (TRACK_Z) the zone the enemy stands in; his speed and way, 0.2 s
            Z_ = self.zones
            out[:, C["en_zone"]] = Z_.locate(s[foe, :3]) if Z_ is not None else -1
            out[:, C["zone_n"]] = Z_.k if Z_ is not None else 0
            out[:, C["zone_map"]] = self.zone_map
            vh_ = getattr(self, "trk_vh", None)
            if vh_ is not None and vh_.shape[1] == n:
                cnt_ = np.maximum(self.trk_vc[foe], 1.0)
                mv_ = vh_[:, foe].sum(0) / cnt_[:, None]
                out[:, C["en_spd8"]] = np.linalg.norm(vh_[:, foe], axis=2).sum(0) / cnt_
                out[:, C["en_mvf8"]] = c * mv_[:, 0] + si * mv_[:, 1]
                out[:, C["en_mvl8"]] = -si * mv_[:, 0] + c * mv_[:, 1]
            zs_ = getattr(self, "trk_zseen", None)
            out[:, C["zone_seen"]] = zs_ if (zs_ is not None and len(zs_) == n) else -1

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
        sf_ = self.script[foe]                               # what the enemy goes for: a network's seat its intention, the item runner
        tg_ = np.where(sf_ == 0, self.intent[foe],           # and the lobber what the rule names them, nothing to say of the rest
                       np.where((sf_ == 3) & (self.sc_persona[foe] != HOLDER) & (self.sc_persona[foe] != WATCHER), self.intent_teach[foe], -1))
        out[:, C["en_target"]] = np.where(about, tg_, -1)
        sk_ = self.hp[foe] + self.armor[foe]                 # his stack's band, the weapon in his hand
        out[:, C["en_band"]] = (sk_ >= AUX_BANDS[0]).astype(np.float32) + (sk_ >= AUX_BANDS[1]) + (sk_ > AUX_BANDS[2])
        out[:, C["en_weapon"]] = self.weapon[foe]
        nr_ = np.full(n, -1, np.int64)                       # the landmark nearest the enemy, by seconds of way from where he is
        if self.route is not None:
            nd_ = self.route.locate(s[foe, :3])
            bt_ = np.full(n, 1e8, np.float32)                # (a way of 1e8 s or more is no way)
            for k_ in range(1, len(INTENTS)):                # in the order of INTENTS: of two equally near the first
                gs_ = self.intent_more.get(k_)               # (NEAREST: the rows of a kind with several items)
                if gs_ is None:
                    gs_ = np.array([self.intent_gi[k_]] if self.intent_gi[k_] >= 0 else [], np.int64)
                gs_ = gs_[gs_ < len(self.route.T)]
                if k_ == EN_INTENT or not len(gs_):
                    continue
                t_ = self.route.T[gs_][:, nd_].min(0)
                nr_ = np.where(t_ < bt_, k_, nr_)
                bt_ = np.minimum(bt_, t_)
        out[:, C["en_near"]] = np.where(about, nr_, -1)
        if TRACK_TRUTH:                                      # (v0.3.11) the belief readout's truth (see TRACK_TRUTH)
            self._trk_cols(out, C, s, foe, grp, c, si)
        if st is not None:
            for (i_, v_), d_ in st["by"].items():            # (the damage as booked per attacker: _book)
                out[i_, C["dmg_dealt"]] += d_
            out[:, C["dmg_taken"]] = st["dmg_taken"] + (0.0 if fall is None else fall)
            for e_ in events:
                if e_["killer"] >= 0 and e_["killer"] != e_["victim"]:
                    out[e_["killer"], C["frag"]] = 1.0
                    out[e_["victim"], C["fragged"]] = 1.0
            for i_, k_ in getattr(self, "aux_take", ()):     # who took the mega (0) or the red armor (1) in this step: he, or
                c_ = C["mega_take"] + k_                     # another player of his match (he, if both did: a jump run's item stays)
                out[oth[i_], c_] = np.where(out[oth[i_], c_] == 1.0, 1.0, 2.0)
                out[i_, c_] = 1.0
        if died is not None:
            out[:, C["died"]] = died
        if "win_game" in C and self._hd_live():             # (HEAD_EVENTS) the win label (labels only)
            out[:, C["win_game"]] = self.hd_gid_ran
            out[:, C["win_band"]] = self.hd_band
        if CONTROL_TRUTH:                                    # (CONTROL_TRUTH) no label here: step()'s _ctl_step gives it
            out[:, C["ctl_lab"]] = -1.0
            out[:, C["ctl_one"]] = -1.0
            out[:, C["ctl_mh"]] = -1.0
            out[:, C["ctl_ra"]] = -1.0
        return out

    def _ctl_step(self, done, out):
        """(CONTROL_TRUTH) once a frame at the end of step(): the books of the mega's and the red armor's spawns (who took
        each), and the label "in control" of the frame CONTROL_D ago into out (info["aux"]; see CONTROL_TRUTH). State kept
        for this only: no random number, nothing else reads it"""
        n, D, M = self.n, CONTROL_D, CONTROL_M
        oth = self._others_arr()
        per = oth.shape[1] + 1
        G = n // per
        grp = np.arange(n) // per
        if getattr(self, "ctl_sp", None) is None or self.ctl_sp.shape[0] != G:
            self.ctl_f = 0                                   # frames since the books began
            self.ctl_rnd = np.zeros(G, np.int64)             # the round each match is in (a count of its ends)
            self.ctl_sp = np.zeros((G, 2, M), np.int64)      # per match and item: an instance's spawn frame,
            self.ctl_tk = np.full((G, 2, M), np.iinfo(np.int64).max, np.int64)   # the frame it was taken (max: not yet),
            self.ctl_by = np.full((G, 2, M), -1, np.int64)   # by whom, its round (-1: an empty slot)
            self.ctl_rn = np.full((G, 2, M), -1, np.int64)
            self.ctl_open = np.full((G, 2), -1, np.int64)    # the slot of the instance lying there now (-1: none)
            self.ctl_next = np.zeros((G, 2), np.int64)       # the next slot to write
            self.ctl_q_ok = np.zeros((D, n), bool)           # the last D frames: a duel's game, the round
            self.ctl_q_rn = np.zeros((D, G), np.int64)
        F = self.ctl_f
        for i_, k_ in getattr(self, "aux_take", ()):         # 1. this frame's takes close the instance lying there
            g_ = int(grp[i_])
            s_ = self.ctl_open[g_, k_]
            if s_ >= 0:
                self.ctl_tk[g_, k_, s_], self.ctl_by[g_, k_, s_] = F, int(i_)
                self.ctl_open[g_, k_] = -1
        dg_ = np.zeros(G, bool)                              # 2. a round's end: what lies there stays untaken in that round
        np.logical_or.at(dg_, grp, np.asarray(done, bool))
        self.ctl_rnd += dg_
        self.ctl_open[dg_] = -1
        for k_, id_ in enumerate(self.big_ids):              # 3. an item lying there with no open instance has come up
            if id_ < 0:
                continue
            new_ = np.nonzero(self.item_up[:G, id_] & (self.ctl_open[:, k_] < 0))[0]
            for g_ in new_:
                s_ = int(self.ctl_next[g_, k_])
                self.ctl_sp[g_, k_, s_], self.ctl_tk[g_, k_, s_] = F, np.iinfo(np.int64).max
                self.ctl_by[g_, k_, s_], self.ctl_rn[g_, k_, s_] = -1, self.ctl_rnd[g_]
                self.ctl_open[g_, k_] = s_
                self.ctl_next[g_, k_] = (s_ + 1) % M
        ok_ = np.zeros(n, bool)                              # this frame as a query: a duel's game (trk_on without "alive")
        if oth.shape[1] == 1 and self.lab is None and self.fixed_kind is None:
            foe = oth[:, 0]
            ok_ = (self.kind[grp] == NORMAL) & (self.mode[grp] < 0) & (self.run_k[:n] < 0) & (self.run_k[foe] < 0)
        C = {k_: i_ for i_, k_ in enumerate(AUX_COLS)}
        out[:, C["ctl_age"]] = min(F, D + 1)
        out[:, C["ctl_ok"]] = ok_
        if F >= D:                                           # 4. the label of the frame D ago, from the books
            q = F - D
            qok = self.ctl_q_ok[q % D]
            qrn = self.ctl_q_rn[q % D]
            sp = self.ctl_sp.reshape(G, 2 * M)
            tk = self.ctl_tk.reshape(G, 2 * M)
            by = self.ctl_by.reshape(G, 2 * M)
            rn = self.ctl_rn.reshape(G, 2 * M)
            cand = (rn == qrn[:, None]) & (tk > q) & (sp <= F)
            key_ = np.where(cand, sp, np.iinfo(np.int64).max)
            od_ = np.argsort(key_, axis=1, kind="stable")[:, :2]
            ga_ = np.arange(G)[:, None]
            c2_ = cand[ga_, od_]                             # [G, 2]: the first two instances after the query frame
            taken_ = tk[ga_, od_] <= F
            live_ = self.ctl_rnd == qrn                      # the round of the query frame goes on (an untaken one: 0.5)
            res_ = c2_ & (taken_ | live_[:, None])           # resolved: taken, or lying there all the horizon
            byq_ = by[ga_, od_][grp]                         # [n, 2]
            v_ = np.where(taken_[grp], (byq_ == np.arange(n)[:, None]).astype(np.float32), 0.5)
            one_ = qok & res_[grp, 0]
            two_ = qok & res_[grp, 0] & res_[grp, 1]
            out[:, C["ctl_one"]] = np.where(one_, v_[:, 0], -1.0)
            out[:, C["ctl_lab"]] = np.where(two_, v_.mean(1), -1.0)
            for k_, c_ in ((0, "ctl_mh"), (1, "ctl_ra")):       # each item alone: its first instance after the query frame
                ck_ = cand[:, k_ * M:(k_ + 1) * M]
                j_ = np.argmin(np.where(ck_, sp[:, k_ * M:(k_ + 1) * M], np.iinfo(np.int64).max), axis=1) + k_ * M
                h_ = ck_.any(1)
                tj_ = tk[np.arange(G), j_] <= F
                r_ = h_ & (tj_ | live_)
                vj_ = np.where(tj_[grp], (by[np.arange(G), j_][grp] == np.arange(n)).astype(np.float32), 0.5)
                out[:, C[c_]] = np.where(qok & r_[grp], vj_, -1.0)
        self.ctl_q_ok[F % D] = ok_                           # 5. this frame into the ring of queries
        self.ctl_q_rn[F % D] = self.ctl_rnd
        self.ctl_f = F + 1

    def step(self, actions):
        a = np.array(actions, copy=True)
        n = self.n
        if HEAD_EVENTS:                                      # (HEAD_EVENTS) the rows of ended rounds start again; this frame's game
            self._hd_begin()
        ar = np.arange(n)
        sc = np.nonzero(self.script > 0)[0]
        if len(sc):
            a[sc] = self._script_actions(sc)
        if LEGS and a.shape[1] > LEGS_HEAD:
            self._legs_step(a)
        if a.shape[1] > 7:                                   # (walk and jump both asked by a policy seat: counted; WALK_NO_JUMP lets the jump go)
            wj_ = (a[:, 7] == 1) & (a[:, 2] == 1) & (self.script == 0)
            self.stats["walk_jump"] += int(wj_.sum())
            if WALK_NO_JUMP:
                walk_no_jump(a)
        if self.key_limits:
            self.limit_keys(a)
        human = self.script == 0                            # policy-controlled players (for the statistics)
        if BRAIN_READ:                                       # (v0.4.2a) the rule's place error beside the brain's
            self._brain_err_count()
        prev_int, prev_done = self.intent.copy(), self.intent_done.copy()
        self.intent_teach = self.intent_rule()
        self.intent_teach = np.where((np.repeat(self.kind, len(self.hp) // len(self.kind)) != NORMAL) & (self.run_k < 0), 0,
                                     self.intent_teach)     # a drill or an aim round: nothing to fetch
        if TARGETS:                                          # where the rule names no item its lesson is silent (a negative label: the
            self.intent_teach = np.where((self.intent_teach == 0) & human, -1, self.intent_teach)   # trainer leaves the frame out)
        if RULE_CONTEST > 0:                                 # ... and where he believes the enemy nearer to the item it names
            rc_ = self._rule_contested(self.intent_teach) & human
            self.stats["rule_contest"] += (float(rc_.sum()), float(((self.intent_teach > 0) & human).sum()))
            self.intent_teach = np.where(rc_, -1, self.intent_teach)
        if RULE_HUNT > 0 and EN_STACK and len(self.hp) == 2 * len(self.kind):   # ... and where hunting is reasonable (RULE_HUNT; duels)
            en_ = self._others_arr()[:, 0]
            bel_ = self.es_h[ar, self._slot(en_)] + self.es_a[ar, self._slot(en_)]
            if BRAIN_READ:                                   # (v0.4.2a) a life on the brain: the brain's stack band
                bel_ = self._stack_src(bel_, np.nonzero(human & (self.intent_teach > 0))[0])
            game_ = np.repeat(self.kind, len(self.hp) // len(self.kind)) == NORMAL
            vis_ = np.asarray(self.visible, bool)[:n] if getattr(self, "visible", None) is not None else np.zeros(n, bool)
            rh_ = human & game_ & (self.run_k < 0) & (self.intent_teach > 0) & ~getattr(self, "rule_big", np.ones(n, bool)) \
                & (self.has[:, [RL, RG, LG]] & (self.ammo[:, [RL, RG, LG]] > 0)).any(1) & ~vis_ & (self.hp > 0) & (self.hp + self.armor >= bel_ + RULE_HUNT)
            self.stats["rule_hunt"] += (float(rh_.sum()), float(((self.intent_teach > 0) & human).sum()))
            self.intent_teach = np.where(rh_, -1, self.intent_teach)
        if RULE_BLIND > 0:                                   # ... and where he has a fresh belief of the enemy's place (RULE_BLIND)
            bt_ = getattr(self, "v02_bt_now", None)
            if bt_ is not None and len(bt_) == n:
                rb_ = human & (self.intent_teach > 0) & (np.asarray(bt_, np.float32) < RULE_BLIND)
                self.stats["rule_blind"] += (float(rb_.sum()), float(((self.intent_teach > 0) & human).sum()))
                self.intent_teach = np.where(rb_, -1, self.intent_teach)
        if OPENINGS:                                         # the first seconds of a life at a spawn point: the pros' opening
            self._open_step(human)
        ch_ = (a[:, 10] if a.shape[1] > 10 else np.zeros(n, np.int64)).copy()
        in_run = self.run_k >= 0
        ch_[in_run] = self.run_k[in_run]                    # an item run: the target is given, not chosen
        self.way_trips = []                                 # (WAY_MEASURE: this step's trips)
        self.aux_take = []                                  # (--aux, "who gets there first") this step's takes of the mega and the red armor
        wy_ = None
        if WAYS and a.shape[1] > WAY_HEAD:                   # his way: the thirteenth output; the shortest in an item run or a jump run
            wy_ = np.where(in_run, 0, a[:, WAY_HEAD])
        self.intend(ch_, human, wy_)
        self.intent_live = self.intent_live & ~in_run       # (and the intention head is not trained on those frames)
        if OPENINGS:                                         # ... how often his reading is the opening's label
            ol_ = (self.op_lab > 0) & self.intent_live & self._counted(ar)
            self.stats["open"][5:7] += (float(ol_.sum()), float((ol_ & (self.intent == self.op_lab)).sum()))
        if WAYS:                                             # (nor the way: it is given there)
            self.way_live = self.way_live & ~in_run
            self.stats["way_reads"] += np.bincount(self.way[self.way_live & self._counted(ar)], minlength=N_WAYS)
        self.stats["intent_trips"][0] += int((self.intent_changed & (self.intent > 0)).sum())
        self.stats["intent_trips"][2] += int((self.intent_changed & (prev_int > 0) & ~prev_done).sum())
        self.stats["intent_frames"] += np.bincount(self.intent[human], minlength=len(INTENTS))
        pkind = np.repeat(self.kind, self.G)
        walk = (a[:, 7] == 1) & (not self.no_walk)
        key = np.where(walk, WALK, 127).astype(np.int32)   # walking: slower and silent
        fwd = (a[:, 0].astype(np.int32) - 1) * key
        side = (a[:, 1].astype(np.int32) - 1) * key
        jump = np.where(a[:, 2] == 1, 127, np.where(a[:, 2] == 2, -127, 0)).astype(np.int32)   # jump / crouch
        hs_duck0 = self.duck.copy() if FIRE_QL else None     # (FIRE_QL) the crouch each had at the frame's start
        self.duck = (a[:, 2] == 2) & (self.hp > 0)
        fire = a[:, 5] == 1
        out_ = (self.rsp_wait > 0) if RESPAWN_QL else None   # (RESPAWN_QL) waiting to respawn: nothing he presses has an effect
        if out_ is not None and out_.any():
            fwd, side, jump, fire = np.where(out_, 0, fwd), np.where(out_, 0, side), np.where(out_, 0, jump), fire & ~out_
            self.stats["rsp_wait_frames"] += int(out_.sum())
        prev = self.state.copy()
        # mouse: the chosen turn speed is followed with a little inertia; jerky commands cost a little
        cmd = np.stack([TURN[a[:, 3]], PITCH[a[:, 4]]], 1)
        if LEGS_TURN_ADD and a.shape[1] > TA_HEAD:          # (LEGS_TURN_ADD) on his legs: their turn plus his correction (_legs_step)
            cmd[:, 0] = turn_sum(cmd[:, 0], self.ta_add)
        cmd = cmd * np.where(self.zoom, ZOOM, 1.0).astype(np.float32)[:, None]      # zoomed: the same hand movement turns less
        if out_ is not None and out_.any():                  # (RESPAWN_QL) ... nor his mouse
            cmd = np.where(out_[:, None], 0.0, cmd).astype(cmd.dtype)
        jerk = np.abs(cmd - self.cmd).sum(1)
        if out_ is not None:                                 # (RESPAWN_QL: and costs nothing)
            jerk = np.where(out_, 0.0, jerk).astype(jerk.dtype)
        self.cmd = cmd
        sg_ = np.sign(cmd[:, 0])
        ch_ = (sg_ != 0) & (self.turn_dir != 0) & (sg_ != self.turn_dir)
        self.rev_wait = np.where(ch_, self.t_rev, np.maximum(0.0, self.rev_wait - 1.0)).astype(np.float32)
        self.turn_dir = np.where(sg_ != 0, sg_, self.turn_dir).astype(np.float32)
        sm = np.where(np.abs(cmd) <= 1.0, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH)   # small corrections follow faster
        if ZOOM_PERCEPT:                                     # (ZOOM_PERCEPT) small in hand terms: 1 degree unzoomed
            sm = np.where(np.abs(cmd) <= np.where(self.zoom, ZOOM, 1.0)[:, None] + 1e-6, MOUSE_SMOOTH_FINE, MOUSE_SMOOTH)
        if AIM2_SMOOTH_K != 1.0:                             # (AIM2_SMOOTH_K) less (or no) view inertia, policy players
            sm = np.where((self.script == 0)[:, None], sm * AIM2_SMOOTH_K, sm)
        self.mv = sm * self.mv + (1.0 - sm) * cmd
        if self.human_aim:
            zs = np.where(self.zoom, ZOOM, 1.0).astype(np.float32)
            self.mv[:, 0] = np.clip(self.mv[:, 0], -TURN_CAP * zs, TURN_CAP * zs)
            if HAND_BAND:                                    # (HAND_BAND) the view follows the hand within its bandwidth
                v_ = np.where((self.script > 0)[:, None], self.mv, self._hand_band(self.script == 0))
                mn_, mb_ = self._sa("MOTOR_NOISE"), self._sa("MOTOR_BASE")
                mn_, mb_ = (mn_[:, None] if np.ndim(mn_) else mn_), (mb_[:, None] if np.ndim(mb_) else mb_)
                jit = self.rng.normal(0, 1, self.mv.shape).astype(np.float32) * (mn_ * np.abs(v_) + mb_ * zs[:, None])
                jit[self.script > 0] = 0.0
                turn, dpit = v_[:, 0] + jit[:, 0], v_[:, 1] + jit[:, 1]
            else:
                mn_, mb_ = self._sa("MOTOR_NOISE"), self._sa("MOTOR_BASE")
                mn_, mb_ = (mn_[:, None] if np.ndim(mn_) else mn_), (mb_[:, None] if np.ndim(mb_) else mb_)
                jit = self.rng.normal(0, 1, self.mv.shape).astype(np.float32) * (mn_ * np.abs(self.mv) + mb_ * zs[:, None])
                jit[self.script > 0] = 0.0
                turn, dpit = self.mv[:, 0] + jit[:, 0], self.mv[:, 1] + jit[:, 1]
            turn, dpit = self.pad_turn(turn, dpit, (a[:, 9] == 1) if a.shape[1] > 9 else np.zeros(n, bool), zs, self.script == 0)
        else:
            turn, dpit = self.mv[:, 0], self.mv[:, 1]
        if out_ is not None and out_.any():                  # (RESPAWN_QL) his view stays where it was
            turn, dpit = np.where(out_, 0.0, turn).astype(np.float32), np.where(out_, 0.0, dpit).astype(np.float32)
        # weapon switch (only to weapons owned)
        want = np.where(a[:, 6] == 0, self.weapon, a[:, 6].astype(np.int64) - 1)
        want = np.where(self.has[ar, want], want, self.weapon)
        if out_ is not None:                                 # (RESPAWN_QL) ... and his weapon key does nothing
            want = np.where(out_, self.weapon, want)
        sw = want != self.weapon
        self.weapon = want
        # as in the game: a weapon change only starts once the reload from the last shot is over
        self.cool = np.where(sw, np.maximum(self.cool, self.fire_cd + SWITCH), self.cool)
        moves = np.stack([fwd, side, jump], 1).astype(np.int8)
        y0 = self.yaw.copy()
        # the view eases back toward level, but not while an enemy is in sight (no pull against vertical aim)
        lev = np.where(self.seen_t > 0.5, self.level, 1.0)
        if RJ_LOOK_FREE > 0 and self.rj_live:                # (RJ_LOOK_FREE) not in a rocket jump run
            lev = np.where(self.rjrun, 1.0, lev)
        p1 = np.clip(self.pitch * lev + dpit, -89, 89)
        done_ms = 0
        hs_s1 = None                                         # (FIRE_QL) the state after the frame's first substep
        for ms in self.substeps:
            done_ms += ms
            f = done_ms / 25.0
            self.w.step(moves, np.stack([self.pitch + (p1 - self.pitch) * f, y0 + turn * f], 1).astype(np.float32), ms)
            if FIRE_QL and hs_s1 is None:
                hs_s1, hs_yaw1 = self.w.state(), y0 + turn * f
        self.pitch = p1
        self.state = s = self.w.state()
        self.yaw = s[:, 7].copy()
        reward = -JERK_COST * jerk.astype(np.float32)
        self._pt_begin()
        self._ps("jerk", reward)
        wb_on_ = self._wb_on()                               # (WIN_W / FADE_V) the blend this frame (live: read once a frame)
        self.wb_cb[:] = 0.0
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
        if out_ is not None:                                 # (RESPAWN_QL) a body waiting to respawn takes no fall damage
            fall = np.where(out_, 0.0, fall)
        fallers = np.nonzero(fall > 0)[0]
        reward -= SWITCH_COST * sw
        self.stats["w_switch"] = self.stats.get("w_switch", 0.0) + float(np.sum(np.asarray(sw) * (self.script == 0)))   # (v0.5.1: his weapon
        #                                                    switches, counted whatever the switch cost is: FADE_V takes it to 0)
        self._ps("weapon_switch", reward)
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
            if HOP_QUIET:                                    # (HOP_QUIET) nothing while the enemy is near by his own senses
                q_ = self._hop_quiet(s)
                self.stats["hop_quiet"] += int((q_ & (hop_ > 0)).sum())
                hop_ = np.where(q_, 0.0, hop_)
            reward += hop_
            self.hop_best = np.where(off_, np.maximum(self.hop_best, hc_), self.hop_best).astype(np.float32)
            self.hop_sum = (self.hop_sum + hop_).astype(np.float32)
            self.stats["hop_pay"] += float(hop_.sum())
            self.stats["hop_n"] += int((hop_ > 0).sum())
            self.stats["hop_takeoffs"] += int(can_.sum())
            self.stats["hop_chains"] += int((can_ & (self.hop_k == 0)).sum())
            self.hop_k = self.hop_k + can_
            self.aw_can = can_                               # (AWARE_LOG) this frame's take-offs
        if HOP_CHAIN > 0:                                    # chains of hops kept at speed (see HOP_CHAIN)
            reward += self._hop_chain(s, prev, jump, human, pkind, in_run)
        if JUMP_COST > 0 and self.lab is None and self.fixed_kind is None:     # (JUMP_COST) a flat cost a take-off, nobody in view
            jc_ = self.stats.get("jump_cost")
            if jc_ is None:                                  # (turned on by live.json in a running simulator: begins here)
                jc_ = self.stats["jump_cost"] = np.zeros(len(JC_COLS))
            nv_ = ~np.asarray(self.visible, bool)[:self.n]
            ok_ = human & (self.hp > 0) & nv_ & (((pkind == NORMAL) & ~in_run) | (in_run & ~self.jrun & ~self.rjrun))
            off_ = ((jump > 0) & (s[:, 6] < 0.5) & (s[:, 5] > 100.0) & (s[:, 5] < HOP_VZ)
                    & ((prev[:, 6] > 0.5) | (prev[:, 5] <= 0.0)) & ok_)                 # a take-off: from the floor, or touched inside the frame
            reward -= JUMP_COST * off_
            c_ = self._counted(np.arange(self.n))
            jc_ += (float((ok_ & c_).sum()), float((off_ & c_).sum()), JUMP_COST * float((off_ & c_).sum()))
        self._ps("hop", reward)
        blind = fire & (self.seen_t > 1.0) & (pkind != MOVE) & ((pkind != COURSE) | self.gun)
        if BLIND_RULE:                                       # (rockets by where they land, below; plasma and grenades free)
            bill = blind & np.isin(self.weapon, (MG, SG, LG, RG, HMG))
            pf_ = np.nonzero(bill & (self.seen_t <= PREFIRE_T))[0]
            if len(pf_):                                     # pre-fire: the crosshair on where the enemy must be by now
                yr_, pr_ = np.radians(self.yaw[pf_]), np.radians(self.pitch[pf_])
                fd_ = np.stack([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)], 1)
                to_ = (self.known[pf_] + self.last_vel[pf_] * np.minimum(self.seen_t[pf_], 1.0)[:, None]
                       + np.array([0, 0, 4.0], np.float32) - self._eye(s)[pf_])
                bb_ = self._blind_src(pf_) if BLIND_BRAIN else None      # (BLIND_BRAIN) a life on the brain: its place
                if bb_ is not None:
                    to_ = np.where(bb_[0][:, None], bb_[1] + np.array([0, 0, 4.0], np.float32) - self._eye(s)[pf_], to_)
                al_ = (to_ * fd_).sum(1)
                near_ = (al_ > 0) & (np.linalg.norm(to_ - al_[:, None] * fd_, axis=1) <= PREFIRE_R)
                if bb_ is not None:                          # (... with no answer there: no exemption)
                    near_ &= ~(bb_[0] & ~bb_[2])
                bill[pf_[near_]] = False
                self.stats["prefire_frames"] += int(near_.sum())
            if BLIND_AHEAD:                                  # (BLIND_AHEAD) the crosshair on where the brain says he will be in 1-4 s
                pa_ = np.nonzero(bill & (self.seen_t <= BLIND_AHEAD_T))[0]
                fu_ = self._blind_fut(pa_) if len(pa_) else None
                if fu_ is not None:
                    yr_, pr_ = np.radians(self.yaw[pa_]), np.radians(self.pitch[pa_])
                    fd_ = np.stack([np.cos(pr_) * np.cos(yr_), np.cos(pr_) * np.sin(yr_), -np.sin(pr_)], 1)
                    to_ = fu_[1] + np.array([0, 0, 4.0], np.float32) - self._eye(s)[pa_][:, None, :]     # [m, 3 horizons, 3]
                    al_ = (to_ * fd_[:, None, :]).sum(2)
                    nf_ = fu_[0] & ((al_ > 0) & (np.linalg.norm(to_ - al_[..., None] * fd_[:, None, :], axis=2) <= PREFIRE_R)).any(1)
                    bill[pa_[nf_]] = False
                    self.stats["prefire_ahead"] = self.stats.get("prefire_ahead", 0) + int(nf_.sum())
            reward -= BLIND_FIRE_COST * bill
            self.stats["blind_bill"] += int(bill.sum())
        else:
            reward -= BLIND_FIRE_COST * blind
        self._ps("blind_fire", reward)
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
        self._ps("move_round", reward)
        self.stats["jerk"] += float(jerk.sum())
        st = dict(dmg_taken=np.zeros(n, np.float32), attacker=np.full(n, -1), kill_w={}, kicked=False,
                  by={}, killer=np.full(n, -1))               # damage per (attacker, victim) this frame; who took him below zero
        if TELEFRAG:                                         # (TELEFRAG) a teleport onto the other player kills him (G_KillBox)
            tp_ = np.nonzero((np.linalg.norm(s[:, :3] - prev[:, :3], axis=1) > 200) & (self.hp > 0) & (pkind == NORMAL)
                             & (self.run_k < 0))[0]          # (games only: in an item or jump run each player is alone)
            for i in tp_:
                for v in self._mates(int(i)):
                    if self.hp[v] > 0 and self.run_k[v] < 0 and not (RESPAWN_QL and self.rsp_wait[v] > 0):
                        d_ = np.abs(s[v, :3] - s[i, :3])
                        if d_[0] < MAXS[0] - MINS[0] and d_[1] < MAXS[1] - MINS[1] and d_[2] < MAXS[2] - MINS[2]:
                            # his whole stack as damage, through the armor as any hit (armor takes 2/3 at most, so the
                            # health always goes below zero)
                            self._hit(int(i), int(v), G, float(self.hp[v] + self.armor[v]) + 1.0, np.zeros(3, np.float32), st)
                            self.stats["telefrag"] = self.stats.get("telefrag", 0) + 1
        for v in fallers:
            took_f = self._damage(int(v), float(fall[v]))
            if SELF_DEBT:
                self.self_debt[v] += took_f
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
                if SELF_DEBT and hz[6] < 1000:
                    self.self_debt[v] += took_
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
                    if SELF_DEBT:
                        self.self_debt[v] += took_
                    self.stats["hurt_dmg"] += float(dmg_[k_])
                    self.lava_t[v] = LAVA_TICK

        if self.courses and (self.course >= 0).any() and self._course_step(reward):
            self.state = s = self.w.state()
            self.yaw = s[:, 7].copy()
            if FIRE_QL:                                      # (a course moved him: the frame's end then)
                hs_s1, hs_yaw1 = s, self.yaw.copy()
        self._ps("course", reward)
        # fire: a shot leaves one frame after the command
        self.cool = np.maximum(0.0, self.cool - DT)
        self.fire_cd = np.maximum(0.0, self.fire_cd - DT)
        do_fire, do_w = self.fire_q, self.fire_w
        ammo_ok = (self.ammo[ar, self.weapon] > 0) | (self.weapon == G)
        shoot = fire & (self.cool <= 1e-4) & ammo_ok & self.has[ar, self.weapon]
        if LG_DEAF:                                          # (LG_DEAF) the trigger held on the lightning gun with ammunition: its loop plays
            self.lgd_fire = fire & (self.weapon == LG) & ammo_ok & self.has[ar, self.weapon] & (self.hp > 0)
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
        if out_ is not None:                                 # (RESPAWN_QL) a body waiting to respawn pays nothing for the trigger
            reward -= FIRE_TOGGLE_COST * ((fire != self.fire_prev) & ~out_)
        else:
            reward -= FIRE_TOGGLE_COST * (fire != self.fire_prev)
        self._ps("fire_toggle", reward)
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
                if RG_FAR_PRICE > 0 and (w_ == RG).any():          # (RG_FAR_PRICE) the far rail at a fixed price
                    cost_ = self._rg_far(s, sc_, w_, cost_)
                reward[sc_] -= cost_
                self.stats["shot_cost"] += float(cost_.sum())
                self.stats["shot_n"] += len(sc_)
                self.stats["shot_fac"] += float(fac_.sum())
        self._ps("shot_price", reward)
        if BLIND_RULE:
            br_ = np.nonzero(use & (self.weapon == RL) & (self.script == 0) & (self.seen_t > 1.0) & (pkind != MOVE)
                             & ((pkind != COURSE) | self.gun))[0]
            if len(br_):
                self._blind_rockets(br_, s, reward)
        self._ps("blind_rocket", reward)
        if RL_QL:                                            # (RL_QL) a rocket leaves on the frame of the command
            now_rl = shoot & (self.weapon == RL)
            if now_rl.any():
                do_fire = do_fire | now_rl
                do_w = np.where(now_rl, RL, do_w)
            self.fire_q, self.fire_w = shoot & ~now_rl, self.weapon.copy()
        else:
            self.fire_q, self.fire_w = shoot, self.weapon.copy()
        tg_, dk_ = s, self.duck                              # where the enemy's box is for an instant shot (FIRE_QL: the frame's start)
        if FIRE_QL:                                          # (FIRE_QL) an instant shot leaves on the frame of the command
            now_hs = shoot & (HS_W[self.weapon] | (self.weapon == PG) | (self.weapon == GL))
            if now_hs.any():
                do_fire = do_fire | now_hs
                do_w = np.where(now_hs, self.weapon, do_w)
            self.fire_q = self.fire_q & ~now_hs
            hs_now = now_hs | (now_rl if RL_QL else False)   # (and with RL_QL the rocket's way too) these shots: the first substep's view
            tg_, dk_ = prev, hs_duck0
        self._hear(1, np.nonzero(shoot & (self.weapon != G))[0])
        if self.rj_live:                                     # (RJ_RUN_P) rockets fired in rocket jump runs
            self.stats["rj_shots"] += int((shoot & (self.weapon == RL) & self.rjrun & self._counted(ar)).sum())
        if HEAR_FIX:                                         # (HEAR_FIX) shots, jumps and landings, footsteps as events
            foot_ = self._hf_steps(s[:, 6] > 0.5, prev[:, 6] > 0.5, s[:, 3:6], self.duck, self.hp > 0)
            if LG_DEAF:                                      # (LG_DEAF) the footsteps alone, for the muffling
                nz_ = (shoot & (self.weapon != G)) | ((prev[:, 6] > 0.5) != (s[:, 6] > 0.5))
                self.hear(nz_ | foot_, foot=foot_ & ~nz_)
            else:
                self.hear((shoot & (self.weapon != G)) | ((prev[:, 6] > 0.5) != (s[:, 6] > 0.5)) | foot_)
        else:
            self.hear((shoot & (self.weapon != G)) | ((prev[:, 6] > 0.5) != (s[:, 6] > 0.5)) |      # shots, jumps and landings,
                      ((s[:, 6] > 0.5) & (np.hypot(s[:, 3], s[:, 4]) > 200.0) & ~self.duck))      # running steps (not walking, not crouched)
        self.note_noise(shoot & (self.weapon != G), (prev[:, 6] > 0.5) != (s[:, 6] > 0.5),      # (N_V02: the same events, for the one who makes them)
                        (s[:, 6] > 0.5) & (np.hypot(s[:, 3], s[:, 4]) > 200.0) & ~self.duck)
        self.note_shots(np.nonzero(shoot & (self.weapon != G))[0])
        if do_fire.any():
            yr, pr = np.radians(self.yaw), np.radians(self.pitch)
            fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1).astype(np.float32)
            eye = self._eye(s)
            if FIRE_QL and hs_now.any():                     # (FIRE_QL) the eye and the yaw of the frame's first substep, the final pitch
                yr = np.where(hs_now, np.radians(hs_yaw1), yr)
                fdir[hs_now] = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1).astype(np.float32)[hs_now]
                eye[hs_now] = self._eye(hs_s1)[hs_now]
            for i in np.nonzero(do_fire)[0]:
                wpn = int(do_w[i])
                hm = int(self.script[i] == 0)               # statistics count policy players only
                kind = W_KIND[wpn]
                name = WEAPONS[wpn]
                vs_ = [int(x) for x in self.others[i]]
                if kind == "proj":
                    slot = np.nonzero(~self.ra[i])[0]
                    if len(slot):
                        k = slot[0]
                        self.rp[i, k] = eye[i] + fdir[i] * 14.0
                        self.rv[i, k] = fdir[i] * P_SPEED[wpn]
                        self.rbase[i, k], self.rrest[i, k] = self.rp[i, k], False      # (MISSILE_POINT) its trBase
                        if FIRE_QL and wpn == RL:           # (FIRE_QL) the velocity cut to whole units (SnapVector on trDelta)
                            self.rv[i, k] = np.trunc(self.rv[i, k])
                        if RL_QL and wpn == RL:             # (RL_QL) the muzzle at the first of the frame's three moves
                            ahead_, eye_ = (RL_AHEAD_PT, RL_EYE_PT) if MISSILE_POINT else (RL_AHEAD, RL_EYE)
                            o_ = prev[i, :3] + (s[i, :3] - prev[i, :3]) / 3.0
                            mz_ = np.trunc(o_ + np.array([0.0, 0.0, eye_ - (VIEW_H - VIEW_H_DUCK) * float(self.duck[i])],
                                                         np.float32) + fdir[i] * 14.0).astype(np.float32)
                            a_ = mz_ + fdir[i] * (ahead_ + DT * P_SPEED[wpn])
                            tr_ = self.w.trace(mz_, a_, mask=self.sight)
                            span_ = ahead_ + DT * P_SPEED[wpn]
                            near_ = mz_ + fdir[i] * min(ahead_, tr_["fraction"] * span_)
                            opp_rl = vs_                    # (RL_QL) whom it can meet within its first stretch
                            got_ = [q_ for q_ in opp_rl if bool(self._seg_box(mz_[None], near_[None].astype(np.float32),
                                                                              s[q_:q_ + 1, :3],
                                                                              np.where(self.duck[q_:q_ + 1], TOP_DUCK, TOP))[0])]
                            if got_ or tr_["fraction"] * span_ <= ahead_:     # it meets something within its first stretch
                                self.stats[name + "_shots"] += hm
                                self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                                dv_ = min(got_, key=lambda q_: float(np.linalg.norm(s[q_, :3] - mz_))) if got_ else None
                                if MISSILE_POINT and got_:      # (MISSILE_POINT) the trace's end at the body it met
                                    near_ = self._box_entry(mz_, near_.astype(np.float32), s[dv_, :3],
                                                            TOP_DUCK if self.duck[dv_] else TOP)
                                self._explode(i, wpn, near_.astype(np.float32), dv_,
                                              fdir[i] if got_ else None, s, st, back=fdir[i])
                                continue
                            # at this frame's end it is ahead_ beyond the muzzle: placed so that the flight below
                            # (one frame, this one) ends there
                            self.ra[i, k], self.rnew[i, k], self.rw[i, k], self.rage[i, k] = True, False, wpn, 0.0
                            self.rp[i, k] = mz_ + fdir[i] * (ahead_ - DT * P_SPEED[wpn])
                            self.rbase[i, k] = mz_                  # (MISSILE_POINT) its trBase: the muzzle
                            self.stats[name + "_shots"] += hm
                            self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                            continue
                        if wpn == GL:                       # Quake lofts grenades a little (forward z + 0.2)
                            d_ = fdir[i].copy()
                            d_[2] += 0.2
                            self.rv[i, k] = d_ / np.linalg.norm(d_) * P_SPEED[wpn]
                        if FIRE_QL and wpn != RL:           # (FIRE_QL) plasma and grenades as the game launches them
                            self._fire_launch(i, k, wpn, eye[i], fdir[i], s, st)
                            self.stats[name + "_shots"] += hm
                            self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                            continue
                        # measured: rockets and grenades do not move on the frame they appear, plasma does
                        self.ra[i, k], self.rnew[i, k], self.rw[i, k], self.rage[i, k] = True, wpn != PG, wpn, 0.0
                        self.stats[name + "_shots"] += hm
                        self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                    continue
                if kind == "pellet":                        # shotgun: 20 pellets, gaussian spread; expected hits
                    self.stats[name + "_shots"] += hm * SG_PELLETS
                    self.stats[name + "_shots_vis"] += hm * SG_PELLETS * int(self.visible[i])
                    for v in vs_:
                        to = tg_[v, :3] + np.array([0, 0, 4.0], np.float32) - eye[i]
                        d = float(np.linalg.norm(to)) + 1e-6
                        if self.w.trace(eye[i], tg_[v, :3] + np.array([0, 0, 4.0], np.float32), mask=self.sight)["fraction"] < 0.999:
                            continue
                        hd = math.hypot(to[0], to[1]) + 1e-6
                        ex = math.degrees(((math.atan2(to[1], to[0]) - yr[i]) + math.pi) % (2 * math.pi) - math.pi)
                        eyv = math.degrees(-math.atan2(to[2], hd) - pr[i])
                        wx, wy = math.degrees(math.atan2(15.0, d)), math.degrees(math.atan2(28.0, d))
                        p = (_phi((wx - ex) / SG_SIGMA) - _phi((-wx - ex) / SG_SIGMA)) * \
                            (_phi((wy - eyv) / SG_SIGMA) - _phi((-wy - eyv) / SG_SIGMA))
                        hits = int(round(SG_PELLETS * min(1.0, max(0.0, p)))) if FIRE_QL else int(self.rng.binomial(SG_PELLETS, min(1.0, max(0.0, p))))
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
                    if FIRE_QL:                             # (FIRE_QL) Quake 3's Bullet_Fire: a random angle, each axis a uniform share
                        th_ = self.rng.random() * 2 * math.pi
                        a_, b_ = math.cos(th_) * (2.0 * self.rng.random() - 1.0), math.sin(th_) * (2.0 * self.rng.random() - 1.0)
                        fd = fd + (u_ * a_ + v_ * b_) * math.tan(math.radians(MG_SPREAD))
                    else:
                        ra_, th_ = math.tan(math.radians(MG_SPREAD)) * self.rng.random(), self.rng.random() * 2 * math.pi
                        fd = fd + (u_ * math.cos(th_) + v_ * math.sin(th_)) * ra_
                    fd = (fd / np.linalg.norm(fd)).astype(np.float32)
                fr = self.w.rays_each(eye[i:i + 1], fd[None, None, :], rng_, mask=self.sight)[0, 0]
                end = eye[i] + fd * rng_ * fr
                self.stats[name + "_shots"] += hm
                self.stats[name + "_shots_vis"] += hm * int(self.visible[i])
                got = [v for v in vs_ if bool(self._seg_box(eye[i:i + 1], end[None], tg_[v:v + 1, :3],
                                                            np.where(dk_[v:v + 1], TOP_DUCK, TOP))[0])]
                if got:                                     # the nearest player on the line takes the shot
                    v = min(got, key=lambda q: float(np.linalg.norm(tg_[q, :3] - eye[i])))
                    self.stats[name + "_hits"] += hm
                    self._hit(i, v, wpn, W_DMG[wpn], fdir[i], st)

        # projectiles fly: direct hits on the opponent, explosions on walls, grenades bounce and time out
        fresh = self.rnew.copy()
        self.rnew[:] = False
        alive = np.nonzero(self.ra & ~fresh)
        if MISSILE_POINT and len(alive[0]):
            self._fly_point(alive, s, st)                    # (MISSILE_POINT) as Quake 3's G_RunMissile
        elif len(alive[0]):
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
            fr = self.w.rays_md(p0, dirs, step_len, mask=self.sight)     # per-projectile step length (speeds differ)
            hitpt = p0 + (p1r - p0) * fr[:, None]
            direct = np.zeros(len(owner), bool)
            d_on = np.full(len(owner), -1, np.int64)
            for k_ in range(self.G - 1):
                opp = self.others[owner, k_]
                dk = self._seg_box(p0, hitpt, s[opp, :3], np.where(self.duck[opp], TOP_DUCK, TOP)) & ~direct
                d_on[dk] = opp[dk]
                direct |= dk
            fuse = np.array([P_FUSE[int(x)] for x in wp], np.float32)
            timeout = (fuse > 0) & (self.rage[owner, slot] >= fuse)
            wall = fr < 1
            self.rp[owner, slot] = hitpt
            for q in range(len(owner)):
                i, k, wq = owner[q], slot[q], int(wp[q])
                if direct[q]:
                    self.ra[i, k] = False
                    self._explode(i, wq, hitpt[q], int(d_on[q]), dirs[q], s, st, back=dirs[q])
                elif timeout[q] or (wall[q] and wq != GL):
                    self.ra[i, k] = False
                    self._explode(i, wq, hitpt[q], None, None, s, st, back=dirs[q])
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
        hurt = np.nonzero((dmg_taken > 0) & (self.hp > 0))[0]              # pain sounds: the others hear them within earshot
        if len(hurt):
            lis_ = self.others[hurt].reshape(-1)
            hurt = np.repeat(hurt, self.G - 1)
            near_ = np.linalg.norm(s[hurt, :3] - s[lis_, :3], axis=1) < self._evt_reach(lis_)
            if HEAR_QL:                                      # (HEAR_QL) where the game sends it
                near_ &= self._hear_ok(lis_, hurt)
            self.pain_t[lis_[near_]] = 0.0
            self.pain_src[lis_[near_]] = hurt[near_]
            self.pain_b[lis_[near_]] = np.minimum(3, (self.hp[hurt[near_]] // 25).astype(np.int64))
        dealt_to = np.zeros((n, self.G), np.float32)         # per attacker and member of the group (see _book)
        for (i_, v_), d_ in st["by"].items():
            dealt_to[i_, self.slot[v_]] += d_
        dealt = dealt_to.sum(1)
        self.dmg_on += dealt_to
        opp_all = np.where((attacker >= 0) & (attacker != ar), attacker, self.foe)     # a hit is felt from the attacker's side
        if EN_STACK:                                         # (B-257) his own hits on a living enemy: his belief of that stack
            for (i_, v_), d_ in st["by"].items():
                if i_ != v_ and self.hp[v_] > 0:
                    self.note_dealt(i_, v_, d_)
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
        self.wb_cb += self.dmg_reward * (np.asarray(dealt, np.float64) - self.dmg_taken_w * np.asarray(taken, np.float64))   # (WIN_W: combat)
        if PAY_SPLIT:
            self._pt("dmg_dealt", ar, self.dmg_reward * dealt)
            self._pt("dmg_taken", ar, -self.dmg_reward * self.dmg_taken_w * np.asarray(taken, np.float64))
        if high_ is not None:                                # (HIGH_PAY) a hit from above is worth more to both, one from below less
            reward += self.dmg_reward * (high_[0] - self.dmg_taken_w * high_[1])
        self._ps("high", reward)
        self._rail(s, st, do_fire, do_w, reward)            # (RAIL_FAR_PAY) the long rail's pay (switch on) and its counters (always)
        self._ps("rail", reward)
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
        self._ps("style", reward)
        self.dmg_life += dealt
        hitby = (attacker >= 0) & (attacker != ar) & (dmg_taken > 0)
        if self.flinch_on and hitby.any():                  # a hit throws the aim off at once, and for a moment after
            fm_ = self._sa("FLINCH_MAX")
            add = np.minimum(fm_, self._sa("FLINCH_PER_DMG") * dmg_taken) * hitby * (self.script == 0)
            self.flinch = np.minimum(fm_, self.flinch + add).astype(np.float32)
            af_ = self._sa("AIM2_FLINCH")
            if np.ndim(af_):                                 # (SEAT_AIM) the kick for the seats without AIM2_FLINCH
                self.percept = (self.percept + (add * (af_ <= 0))[:, None] * self.rng.normal(0, 1, (n, 2))).astype(np.float32)
            elif not af_:                                    # (AIM2_FLINCH: the sustained error only)
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
            touch = (dxy < 36) & (dz < PICK_Z) & np.repeat(self.item_up, self.G, axis=0) & (self.hp > 0)[:, None]
            for i, it in zip(*np.nonzero(touch)):
                m = i // self.G
                if not self.item_up[m, it]:
                    continue                                  # the other player took it this frame
                kind, val, resp, cap, lab = self.item_def[it]
                took = False
                if self.kind[m] != NORMAL and kind in ("wp", "am", "pack") and self.run_k[i] < 0:
                    continue                                  # aim / drill / movement rounds: no weapons or ammo (item runs: everything)
                if JUMP_PAST_PICK and self.jrun[i] and not self.jrun_past[i] and it == self.jrun_it[i]:
                    continue                                  # (JUMP_PAST_PICK) a jump run's own target: only once he is past the jump
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
                    if PRO_START_P > 0 and self.pro_mm[self._match_of(int(i))]:      # (PRO_START_P) the pro starts' pickups
                        PS_ = self.stats["pro_start"]
                        PS_[12] += 1
                        if lab in ("MH", "RA", "YA"):
                            PS_[10] += 1
                            PS_[11] += float(self._counted(int(i)))
                    if int(it) in self.big_ids:              # (--aux, "who gets there first") the mega or the red armor: who took it
                        self.aux_take.append((int(i), self.big_ids.index(int(it))))
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
                    pts_ = gain if kind in ("hp", "ar") else 25.0 if new_wp else 0.0
                    if SELF_DEBT and kind in ("hp", "ar") and self.self_debt[i] > 0:
                        back_ = min(float(self.self_debt[i]), pts_)          # refilling what he took off himself pays nothing
                        self.self_debt[i] -= back_
                        pts_ -= back_
                    pay_ = self.item_reward * pts_ / 100.0
                    if BIG_PICK_SEQ and kind == "wp":                       # (v0.3.8) the big three a life by order
                        b_ = (RL, LG, RG).index(int(val)) if int(val) in (RL, LG, RG) else -1
                        pay_ = self._big_seq(i, b_, had_wp) if b_ >= 0 else 0.0
                        if SMALL_ZERO and pay_:              # (SMALL_ZERO) the other loses as much
                            for o_ in self._mates(i):
                                reward[o_] -= pay_
                                r_long[o_] -= pay_
                                if PAY_SPLIT:
                                    self._pt("big_order", o_, -pay_)
                    elif BIG_PICK > 0 and kind == "wp":                     # (v0.3.1) the big three once a life, nothing else
                        b_ = (RL, LG, RG).index(int(val)) if int(val) in (RL, LG, RG) else -1
                        pay_ = BIG_PICK if b_ >= 0 and not self.big_got[i, b_] else 0.0
                        if b_ >= 0:
                            self.big_got[i, b_] = True
                    if BIG_ONCE and kind == "wp" and BIG_PICK > 0 and not BIG_PICK_SEQ and pay_ > 0 and self.big_got[i].sum() > 1:
                        pay_ = 0.0                                          # (BIG_ONCE) only the first of the three pays
                    if ITEM_FLAT and lab in ITEM_FLAT and not own_:
                        pay_ += ITEM_FLAT[lab]
                        for o_ in self._mates(i):                           # (zero-sum) the enemy loses as much
                            reward[o_] -= ITEM_FLAT[lab]
                            r_long[o_] -= ITEM_FLAT[lab]
                    if PAY_SPLIT:
                        fl_ = float(ITEM_FLAT[lab]) if (ITEM_FLAT and lab in ITEM_FLAT and not own_) else 0.0
                        if fl_:
                            nm_ = ("item_" + lab) if lab in ("MH", "RA", "YA") else "item_flat_other"
                            self._pt(nm_, i, fl_)
                            for o_ in self._mates(i):
                                self._pt(nm_, o_, -fl_)
                        self._pt("big_order" if kind == "wp" and (BIG_PICK_SEQ or BIG_PICK > 0) else "item_points", i, float(pay_) - fl_)
                    reward[i] += pay_
                    r_long[i] += pay_
                    want_ = lab if lab in ("MH", "RA") else WEAPONS[int(val)].upper() if kind == "wp" else ""
                    if lab == "YA" and it in self.route_item:
                        want_ = self.route_goal[self.route_item.index(it)]    # YA or YA2
                    if want_ in INTENTS and self.intent[i] == INTENTS.index(want_) and not self.intent_done[i]:
                        self.intent_done[i] = True                       # the trip he chose is complete
                        if WEAPON_FREE and kind == "wp":
                            self.intent_new[i] = True                    # (WEAPON_FREE) a weapon taken ends the choice: read anew at once
                        self.stats["intent_trips"][1] += 1
                        self.stats["intent_reach"] += float(self.intent_t[i])
                        if WAYS and self.script[i] == 0 and bool(self._counted(i)):
                            self.stats["way_done"][self.way[i]] += 1     # ... by the way he was on
                    if lab in ("MH", "RA") and self.item_loss > 0:       # the others lose a share: it was theirs to take
                        for o_ in self._mates(i):
                            if self.hp[o_] > 0 and self.run_k[o_] < 0:      # (not in an item run: there everybody is alone)
                                reward[o_] -= self.item_loss * self.item_reward * gain / 100.0
                                self._pt("item_loss", o_, -self.item_loss * self.item_reward * gain / 100.0)
                                r_long[o_] -= self.item_loss * self.item_reward * gain / 100.0
                    if self.contest_t[m] > 0 and it == self.contest_it[m]:    # the item the round began as a race for
                        self.stats["contest_taken"] += int(self.script[i] == 0)
                        self.contest_t[m] = -1.0
                    if not own_:
                        self.item_up[m, it] = False
                        self.item_t[m, it] = resp
        self._ps("items_other", reward)
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
        self._ps("item_seek", reward)
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
            if GONE_BELIEF and ITEM_BELIEF:                  # (GONE_BELIEF) "gone" by what he knows of the item, not the truth
                gb_ = np.minimum(g_, self.bel_t.shape[1] - 1)
                rs_ = np.array([float(self.item_def[i_][2]) for i_ in it_], np.float32)
                bt_ = self.bel_t[np.arange(n), gb_]
                soon_b = (bt_ >= rs_) | (np.maximum(0.0, rs_ - bt_) < phi + 5.0) | (self.intent >= EN_INTENT)
                self.intent_gone = valid & ~soon_b & (self.intent > 0) & (self.intent < HOLD_INTENT)
            if EN_ON:                                        # the enemy as the target: reached when he is in view, given up when
                en_, vis_ = self.note_hunt(valid)            # nothing is known of him any more (FIGHT_TARGET, HUNT)
                self.stats["en_frames"] += np.array([(en_ & (self.script == 0) & (self.hp > 0)).sum(), (en_ & self.legs_on).sum(),
                                                     (en_ & vis_ & (self.script == 0)).sum()], np.float64)
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
            pay = valid & soon & ~self.intent_changed & ~self.intent_done & (self.script == 0) & (self.hp > 0) & ~self.rjrun   # (RJ_RUN_P: nothing for the way)
            if self.hold_n:                                  # (nothing is paid for the way to a holding place, nor for speed on it)
                pay = pay & (self.intent < HOLD_INTENT)
            if HUNT:                                         # (B-256: nor for the way to the enemy, nor for speed on it)
                pay = pay & (self.intent != EN_INTENT)
            worth =self.item_reward * np.array(INTENT_VALUE, np.float32)[self.intent]      # the whole way is worth the pickup
            # a trip given up pays nothing (v9); one whose item another player took is not given up
            claw = self.intent_changed & (prev_int > 0) & ~prev_done & ~in_run & ~gone_before[:len(prev_int)]
            reward -= self.intent_paid * claw
            self._pt("way_claw", ar, -(self.intent_paid * claw))
            if WAYS:                                         # (counted: what trips given up gave back; below: what his ways paid)
                self.stats["way_pay"][1] += float((self.intent_paid * claw)[self._counted(ar)].sum())
            fast_ = np.where(self.intent_paid > 0, self.intent_fast, 0.0)      # the part of it that was pay for speed (a new life
            r_long -= (self.intent_paid - fast_) * claw                        # put intent_paid to nothing: _fresh)
            self.intent_fast = np.where(claw | self.intent_done, 0.0, fast_).astype(np.float32)
            self.intent_paid = np.where(claw | self.intent_done, 0.0, self.intent_paid).astype(np.float32)
            pay_now = self.intent_seek * worth * gain / self.intent_phi0 * pay
            reward += pay_now - INTENT_SWITCH * (self.intent_changed & (prev_int > 0) & ~in_run)
            self._pt("way", ar, pay_now)
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
                if SPEED_LOS:                                # (SPEED_LOS) out of his line of sight, whichever way he faces
                    c_ = np.nonzero(trip & (sp_h > SPEED_LO))[0]
                    if len(c_):
                        eye_ = self._eye(s)[c_]
                        for o_ in self._others_arr()[c_].T:     # (every other player of his group)
                            los_ = self._los(eye_, s[o_, :3] + np.array([0, 0, 8.0], np.float32))
                            los_ &= np.linalg.norm(s[o_, :3] - s[c_, :3], axis=1) < 4000
                            if RESPAWN_QL:
                                los_ &= self.rsp_wait[o_] <= 0
                            trip[c_[los_]] = False
                fast = trip & (self.pace_g > 0.3)
                pace_now = PACE_PAY * DT * np.clip(sp_h / 320.0 - 1.0, 0.0, 1.0) * fast
                if SPEED_PAY or SPEED_PAY_RUN:               # per stretch of new ground, by the speed he covers it at (see SPEED_PAY)
                    new_ = np.minimum(np.where(pay, gain, 0.0), 3.0 * DT)      # (a teleporter's leap counts as three frames' running)
                    sp_f = (320.0 / SPEED_HI) * new_ * np.clip((sp_h - SPEED_LO) / (SPEED_HI - SPEED_LO), 0.0, 1.0)
                    run_ok = in_run & (self.script == 0) & (self.hp > 0) & ~self.rjrun     # (RJ_RUN_P: nor for speed)
                    pace_now = pace_now + SPEED_PAY * sp_f * trip
                    reward += SPEED_PAY_RUN * sp_f * run_ok
                    self._spr_now = (SPEED_PAY_RUN * sp_f * run_ok).astype(np.float32)   # (JRUN_SPEED_BACK) given back with a failed try
                    self._pt("speed_run", ar, SPEED_PAY_RUN * sp_f * run_ok)
                    self.stats["speed_pay"] += float((SPEED_PAY * sp_f * trip).sum())
                    self.stats["speed_pay_run"] += float((SPEED_PAY_RUN * sp_f * run_ok).sum())
                    self.stats["speed_frames"] += int(((sp_f > 0) & (trip | run_ok)).sum())
                reward += pace_now
                self._pt("speed", ar, pace_now)
                self.intent_paid = (self.intent_paid + pace_now).astype(np.float32)     # a trip given up gives it back
                self.intent_fast = (self.intent_fast + pace_now).astype(np.float32)     # ... as pay for speed, not the game's
                self.stats["pace_pay"] += float(pace_now.sum())
                self.stats["pace_frames"] += int((fast & (sp_h > 320.0)).sum())
                self.stats["trip_frames"] += int(trip.sum())
                self.stats["trip_speed"] += float(sp_h[trip].sum())
            self._ps("intent_switch", reward)
            run = in_run & (self.script == 0)
            if run.any():                                   # item runs: the way gained against the clock, a bonus on taking it
                alive = run & (self.hp > 0)
                aw_ = alive & ~self.rjrun                    # (RJ_RUN_P: a rocket jump run pays its arrival only, below)
                reward += RUN_SCALE * (np.where(pay, gain, 0.0) - DT) * aw_
                r_long += RUN_SCALE * (np.where(pay, gain, 0.0) - DT) * aw_
                sp_ = np.hypot(s[:, 3], s[:, 4])
                self.stats["move_frames"] += int(aw_.sum())
                self.stats["move_speed"] += float(sp_[aw_].sum())
                self.stats["move_fast"] += int(((sp_ > 330) & (s[:, 6] < 0.5) & aw_).sum())
                arr = run & self.intent_done & (self.run_k > 0) & (self.intent == self.run_k) & ~self.rjrun     # (the pickup may be booked after this block: no "since last frame" test)
                gone = run & ~arr & (self.run_k > 0) & (self.intent == self.run_k) & valid & ~soon & ~self.intent_done & ~self.rjrun
                rr = np.nonzero(alive & self.rjrun)[0] if self.rj_live else ()     # (RJ_RUN_P) rocket jump runs: at the landing, or not
                if len(rr):
                    self._rj_step(rr, s, prev, reward, r_long)
                self.jrun_new[:] = False
                jr = np.nonzero(alive & self.jrun)[0]       # jump runs: over the gap, fallen short of it, or out of time
                if len(jr):
                    self.stats["jump_frames"] += len(jr)
                    self.jrun_t[jr] -= DT
                    kk_ = self.jrun_k[jr]
                    A_, B_, p_ = self.jump_a[kk_], self.jump_b[kk_], s[jr, :3]
                    self.jrun_paid[jr] += (pay_now[jr] + RUN_SCALE * np.where(pay[jr], gain[jr], 0.0)).astype(np.float32)
                    if JRUN_SPEED_BACK and getattr(self, "_spr_now", None) is not None and len(self._spr_now) == n:
                        if getattr(self, "jrun_spd", None) is None or len(self.jrun_spd) != n:
                            self.jrun_spd = np.zeros(n, np.float32)
                        self.jrun_spd[jr] += self._spr_now[jr]   # (its own counter: the speed pay is in reward only, not r_long)
                    self.jrun_edge[jr] |= (np.hypot(p_[:, 0] - A_[:, 0], p_[:, 1] - A_[:, 1]) < 120.0) & (np.abs(p_[:, 2] - A_[:, 2]) < 64.0)
                    landed_ = (s[jr, 6] > 0.5) | ((prev[jr, 5] < 0.0) & (s[jr, 5] > 0.0))   # on the floor, or touched it and jumped again inside the frame
                    ov_ = ~self.jrun_over[jr] & self.jrun_edge[jr] & (np.linalg.norm(p_ - B_, axis=1) < 110.0) & (landed_ | arr[jr])
                    if JUMP_OVER_ANY:                        # (JUMP_OVER_ANY) over it from his own take-off
                        L_ = self.jrun_lift[jr]
                        gap_ = np.hypot(A_[:, 0] - B_[:, 0], A_[:, 1] - B_[:, 1])
                        if JUMP_OVER_ANY >= 2:                   # (=2) from the take-off's side, at its height
                            u_ = (A_[:, :2] - B_[:, :2]) / np.maximum(gap_, 1e-6)[:, None]
                            far_ = ((L_[:, :2] - B_[:, :2]) * u_).sum(1) >= 0.5 * gap_
                            high_ = np.abs(L_[:, 2] - A_[:, 2]) <= 48.0
                            ring_ = 128.0
                        else:
                            far_ = np.hypot(L_[:, 0] - B_[:, 0], L_[:, 1] - B_[:, 1]) >= 0.6 * gap_
                            high_ = L_[:, 2] >= np.minimum(A_[:, 2], B_[:, 2]) - 48.0
                            ring_ = 110.0
                        at_ = (np.linalg.norm(p_ - B_, axis=1) < ring_) & (p_[:, 2] >= B_[:, 2] - 40.0)
                        if JUMP_OVER_ANY >= 2:                   # (=2) this rule alone: "been at the take-off, then at the landing
                            ov_ = ~self.jrun_over[jr] & at_ & far_ & high_ & landed_    # some way" counted walks round (Hektik 15)
                            if JUMP_OVER_ANY >= 3:               # (=3) ... and down no shorter than the gap less 64 u from the take-off
                                ov_ &= ((p_[:, :2] - A_[:, :2]) * -u_).sum(1) >= gap_ - 64.0
                        else:
                            ov_ |= ~self.jrun_over[jr] & at_ & far_ & high_ & landed_
                        self.jrun_lift[jr[landed_]] = p_[landed_]
                    self.jrun_over[jr[ov_]] = True
                    if JUMP_OVER_PAY > 0:                    # (JUMP_OVER_PAY) over the gap: paid once a try, kept
                        reward[jr[ov_]] += JUMP_OVER_PAY
                        r_long[jr[ov_]] += JUMP_OVER_PAY
                    for i_ in (jr[ov_ & self.jrun_open[jr]] if JUMP_WEIGHT else ()):   # (JUMP_WEIGHT) over: into his success
                        self._jump_learn(int(self.jrun_k[i_]), True)
                        self.jrun_open[i_] = False
                    oc_ = ov_ & self._counted(jr)
                    self.stats["jump_far"][1] += int((oc_ & ~self.jrun_far[jr]).sum())
                    self.stats["jump_far"][3] += int((oc_ & self.jrun_far[jr]).sum())
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
                        if JRUN_SPEED_BACK and getattr(self, "jrun_spd", None) is not None:
                            reward[i] -= float(self.jrun_spd[i])  # ... and its speed pay (JRUN_SPEED_BACK; reward only)
                        self._jump_place(int(i))
                for i in np.nonzero(arr | gone | (run & (self.run_k == 0)))[0]:
                    if self.jrun_new[i]:
                        continue
                    if arr[i]:
                        reward[i] += RUN_ARRIVE
                        r_long[i] += RUN_ARRIVE
                        self.stats["move_arrive"] += 1
                    if self.jrun[i]:
                        if self.rc is not None:              # (ROUTE_COPY) the try ends at the armor, or not
                            self.rc_arr[i] = bool(arr[i])
                        self._jump_place(int(i))            # the next try
                    else:
                        self._run_pick(int(i))
            self.intent_phi = phi.astype(np.float32)

        self._ps("runs", reward)
        if STACK_DIFF:                                       # (v0.3.1) his stack against the enemy's, zero-sum (see STACK_DIFF)
            on_ = (pkind == NORMAL) & (self.script == 0) & (self.run_k < 0)
            st_ = np.where(self.hp > 0, np.maximum(self.hp, 0.0) + self.armor, 0.0)
            diff_ = np.clip((st_ - st_[self._others_arr()].mean(1)) / 200.0, -1.0, 1.0)   # (a group: against the mean of the others; trained in duels only)
            pay_ = np.where(on_, STACK_DIFF * diff_ * (DT / 60.0), 0.0)
            reward += pay_
            r_long += pay_
        self._ps("stack_diff", reward)
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

        self._ps("stack_keep", reward)
        if (self.drop_w >= 0).any():                         # weapons that dead players left (see DROPS)
            self._drops_step(reward)

        self._ps("drops", reward)
        if KNOW_PAY:                                         # pay for knowing where the enemy is (see KNOW_PAY)
            on = (pkind == NORMAL) & (self.hp > 0) & (self.script == 0) & (self.run_k < 0)
            kn = self._knowledge()
            kp_ = np.where(on, KNOW_PAY * kn * (DT / 60.0), 0.0)
            if SMALL_ZERO:                                   # (SMALL_ZERO) what he gets the other loses
                kp_ = kp_ - kp_[self._others_arr()].mean(1)
            reward += kp_
            r_long += kp_
            self.stats["know"] += float(kn[on].sum())
            self.stats["know_frames"] += int(on.sum())

        self._ps("know", reward)
        if WIN_SHADOW:
            self.ws_flat[:] = 0.0
        # deaths, frags, respawns
        if RESPAWN_QL:                                       # (RESPAWN_QL) the waits run down; at a wait's end he is back at a spawn
            self.rsp_born[:] = False                         # point chosen now, by where the enemy is now (see _spawn)
            back_ = np.nonzero(self.rsp_wait > 0)[0]
            self.rsp_wait[back_] -= 1
            for v in back_[self.rsp_wait[back_] == 0]:
                self._spawn(int(v), avoid=s[self._others_arr()[v, 0], :3])
                self.rsp_born[v] = True
                self.state = s = self.w.state()
        done = np.zeros(n, bool)                            # end of the round (memory and returns reset here only)
        died = np.zeros(n, bool)
        events = []
        dead = np.nonzero(self.hp <= 0)[0]
        if RESPAWN_QL:                                       # (RESPAWN_QL) a body waiting to respawn does not die again
            dead = dead[self.rsp_wait[dead] <= 0]
        for v in dead:
            k = st["killer"][v] if st["killer"][v] >= 0 else attacker[v]
            gm_ = GAME_ON and bool(self.game[self._match_of(v)])    # a whole game or a late round (GAME_P): the game's score,
            if gm_:                                                 # and with WIN_PAY the frag is paid by the game (_game_step)
                self.g_flat[v] -= 1.0
                if WIN_SHADOW:
                    self.ws_flat[v] -= 1.0
                    if k >= 0 and k != v:
                        self.ws_flat[k] += 1.0
                if k >= 0 and k != v:
                    self.g_flat[k] += 1.0
                else:
                    self.frags_r[v] -= 1                    # (his own hand or the world: a point off him)
            if not (gm_ and WIN_PAY and not wb_on_):         # (WIN_W / FADE_V: the blend pays it, in part)
                reward[v] -= 1.0
                self.wb_cb[v] -= 1.0
                self._pt("death", v, -1.0)
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
                if not (gm_ and WIN_PAY and not wb_on_):
                    reward[k] += 1.0
                    self.wb_cb[k] += 1.0
                    self._pt("frag", k, 1.0)
                if DROPS:
                    self._drop_weapon(int(v), int(k))
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
            if self.rjrun[v]:                               # (a rocket jump run: the next try)
                if RJ_COPY:                                  # (RJ_COPY) the try ends: he died
                    self._rjc_close(int(v), 2)
                self._rj_place(int(v))
                continue
            if self._wait_on(int(v)):                       # (RESPAWN_QL) out of play for the game's respawn wait
                continue
            self._spawn(int(v), avoid=s[self.foe[v], :3], close=True if self.kind[v // self.G] in (AIM, DRILL) else None)
            if self.goal[v] >= 0:
                self._new_goal(int(v))
        lo, hi = self.w.bounds()
        out = np.nonzero(s[:, 2] < lo[2] - 64)[0]            # fell out of the map: a suicide
        if RESPAWN_QL:                                       # (RESPAWN_QL: not a body waiting to respawn)
            out = out[self.rsp_wait[out] <= 0]
        for v in out:
            if not died[v]:
                gm_ = GAME_ON and bool(self.game[self._match_of(v)])
                if gm_:                                      # (a whole game: a point off him, and the death is an event)
                    self.g_flat[v] -= 1.0
                    if WIN_SHADOW:
                        self.ws_flat[v] -= 1.0
                    self.frags_r[v] -= 1
                    events.append(dict(victim=int(v), killer=-1, weapon=-1))
                if not (gm_ and WIN_PAY and not wb_on_):
                    reward[v] -= 1.0
                    self.wb_cb[v] -= 1.0
                    self._pt("death", v, -1.0)
                if CLAW_ON_DEATH and self.intent[v] > 0 and not self.intent_done[v]:
                    reward[v] -= float(self.intent_paid[v])
                    r_long[v] -= float(self.intent_paid[v] - min(self.intent_fast[v], self.intent_paid[v]))
                died[v] = True
                self.stats["suicides"] += 1
                if self._wait_on(int(v)):                   # (RESPAWN_QL) out of play for the game's respawn wait
                    continue
                self._spawn(int(v), avoid=s[self.foe[v], :3])
                if self.jrun[v]:                            # (a jump run: the next try)
                    self._jump_place(int(v))
                if self.rjrun[v]:                           # (a rocket jump run: the next try)
                    if RJ_COPY:                              # (RJ_COPY) the try ends: he died
                        self._rjc_close(int(v), 2)
                    self._rj_place(int(v))
                if self.goal[v] >= 0:
                    self._new_goal(int(v))
        self._ps("deaths_other", reward)
        # short rounds (curriculum): restart both players near each other every ~round_len seconds
        self.round_t += DT
        if GAME_ON:                                          # whole games and late rounds: their clock, and the frame's pay by the game
            self._game_step(reward)
        self._ps("win_pay", reward)
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
            ends = np.nonzero(np.where(self.game > 0, self.g_tick >= (self.g_end if MOMENTS else GAME_FRAMES), self.round_t > klen * self.round_fac))[0]
            if OVERTIME:                                     # (OVERTIME) a level game goes on, OT_LEN seconds a period
                ends = self._ot_ends(ends)
        if self.lab is not None:                            # lab rooms have exact lengths
            ends = np.nonzero(self.round_t >= self.lab_len)[0]
            am = np.repeat(self.arena > 0, self.G)
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
                self._wsh_cut(int(m))                        # (WIN_SHAPE_K) cut before its end: PSI there is 0 (0 at the end anyway)
                self._game_end(int(m))
            self.round_fac[m] = self.rng.uniform(0.67, 1.33)
            self.drop_w[m] = -1
            self.run_k[self._seats(int(m))] = -1
            self.jrun[self._seats(int(m))] = False
            self.jrun_open[self._seats(int(m))] = False      # (JUMP_WEIGHT: a try cut by the run's end counts nothing)
            self.rjrun[self._seats(int(m))] = False
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
            a_, b_ = self.G * m, self.G * m + 1
            P = list(range(self.G * m, self.G * m + self.G))
            done[P] = True
            if self.lab is not None:
                self._lab_round(int(m))
                continue
            # kind_p is the share of playing TIME per kind: normal rounds last much longer than the others, so
            # the chance of starting each kind is weighted by 1 / its length
            wts = np.asarray(self.kind_p, np.float64) / np.array([self.round_len, 15.0, 15.0, self.move_len])
            if GAME_ON and self._game_ok():                  # (the whole games' and late rounds' part of the games' time was drawn above)
                wts[0] *= max(0.0, 1.0 - GAME_P - LATE_P - MOMENT_P)
            kd = int(self.rng.choice(4, p=wts / wts.sum()))
            if self.rng.random() < self.drill_p:            # older option: share of one-weapon rounds
                kd = DRILL
            if self.fixed_kind is not None:
                kd = self.fixed_kind[0]
            if (kd == MOVE and self.field is None) or self.G > 2:      # more than two players: plain fights only
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
            elif kd == NORMAL and self.G == 2 and self.rng.random() < self.bot_p:
                self.script[b_] = 2
            if self.script[b_] == 2:
                self.sc_persona[b_] = self.persona_force if self.persona_force is not None else \
                    int(self.rng.choice(len(PERSONAS), p=self.persona_p))
            for q in P:
                self.load_sets[q] = None
            if kd == NORMAL and self.fixed_kind is None:
                u = self.rng.random()
                guns = [g for g in LOAD_GUNS if g in self.map_weapons and (self.sg_spawn or g != SG)]
                if u < self.loadout_p[0]:
                    for q in P:
                        self.load_sets[q] = tuple(int(x) for x in self.rng.choice(guns, min(len(guns), int(self.rng.integers(1, 3))), replace=False))
                elif u < self.loadout_p[0] + self.loadout_p[1]:
                    for q in P:
                        self.load_sets[q] = ()
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
                for q in P[2:]:
                    self.script[q], self.goal[q], self.frags_r[q], self.snd_t[q] = 0, -1, 0, 99.0
                    self._spawn(q, avoid=self.w.state()[q - 1, :3])
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
        if PRO_START_P > 0 and self._pro_put:                # ... and for the pro starts: the moment of a pros' duel
            for m_, k_, s_ in self._pro_put:
                self._pro_start(m_, k_, s_)
            self._pro_put = []
        if len(dead) or len(out) or len(ends) or self._replaced:
            self.state = s = self.w.state()
            self._replaced = False

        # senses: sight (line of sight + field of view) and hearing (rough position), for every other member
        eye = self._eye(s)
        yr, pr = np.radians(self.yaw), np.radians(self.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        pkind = np.repeat(self.kind, self.G)
        off = np.zeros((n, self.G - 1), np.float32)
        for k_ in range(self.G - 1):
            opp = self.others[:, k_]
            to = s[opp, :3] - eye
            dist = np.linalg.norm(to, axis=1) + 1e-6
            cosang = (to * fdir).sum(1) / dist
            off[:, k_] = 1.0 - cosang
            infov = cosang > self.fov()[2]
            cand = np.nonzero(infov & (dist < 4000))[0]
            vis = np.zeros(n, bool)
            if len(cand):
                vis[cand] = self._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
            vis &= (pkind != MOVE) & (pkind != SOLO) & ((pkind != COURSE) | self.gun)   # movement / solo / course: no other player
            if RESPAWN_QL:                                   # (RESPAWN_QL) a body waiting to respawn is out of play: not seen
                vis &= self.rsp_wait[opp] <= 0
            heard = (~vis) & (dist < HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250) & (pkind != MOVE) & (pkind != SOLO) & (pkind != COURSE)
            if HEAR_FIX:                                     # (HEAR_FIX) only a footstep or a jump of his on this frame tells
                heard = (~vis) & (dist < HEAR) & self.hf_ev[opp] & (pkind != MOVE) & (pkind != SOLO) & (pkind != COURSE)
            if RESPAWN_QL:                                   # (RESPAWN_QL) ... nor heard
                heard &= self.rsp_wait[opp] <= 0
            if HEAR_QL:                                      # (HEAR_QL) only what the game sends him
                heard &= self._hear_ok(ar, opp)
            if LG_DEAF:                                      # (LG_DEAF) his own lightning gun muffles the footsteps
                heard &= dist < self._lgd_hear_reach(ar, opp)
            self.vis2[:, k_] = vis
            if SURPRISE_MS > 0:                              # off the crosshair and unexpected: noticed later
                ecc_ = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
                self.acq_extra2[:, k_] = np.where(vis & (self.vis_run2[:, k_] == 0), surprise_frames(ecc_, self.seen2[:, k_]),
                                                  np.where(vis, self.acq_extra2[:, k_], 0))
            self.vis_run2[:, k_] = np.where(vis, self.vis_run2[:, k_] + 1, 0)
            acq = vis & (self.vis_run2[:, k_] >= self._acq_need() + self.acq_extra2[:, k_])
            self.acq2[:, k_] = acq
            self.known2[acq, k_] = s[opp[acq], :3]
            if heard.any() and HEAR_FIX:                     # (HEAR_FIX) placed by the sound: its direction and loudness
                self.known2[heard, k_] = self._hf_place(np.nonzero(heard)[0], opp[heard], muff=self._lgd_muff(ar[heard], opp[heard]))
            elif heard.any():
                self.known2[heard, k_] = s[opp[heard], :3] + self.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                    np.array([1, 1, 0], np.float32)
            self.seen2[:, k_] = np.where(acq | heard, 0.0, self.seen2[:, k_] + DT)
        if self.G > 2:
            # attention: the noticed enemy nearest the crosshair (the current one is preferred a little, so the
            # choice does not flicker); with nobody noticed, the one in view, else the one seen or heard last
            cur = np.zeros((n, self.G - 1), bool)
            cur[ar, self.fidx] = True
            sc_ = np.where(self.acq2, off * np.where(cur, 0.6, 1.0), np.where(self.vis2, 2.0 + off, 4.0 + self.seen2))
            self.fidx = sc_.argmin(1)
        self.foe = self.others[ar, self.fidx]
        opp = self.foe
        vis = self.vis2[ar, self.fidx]
        self.visible = vis
        self.vis_run = self.vis_run2[ar, self.fidx]
        self.acquired = self.acq2[ar, self.fidx]
        self.known = self.known2[ar, self.fidx]
        self.seen_t = self.seen2[ar, self.fidx]
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        vh = np.nonzero(vis & (self.script == 0))[0]        # aim quality while the enemy is in view
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
        self._teach_update()
        info = dict(events=events)
        self._preaim(s, reward)                              # (PREAIM_PAY) fresh sightings: the counters, always; the pay with the switch on
        self._ps("preaim", reward)
        if TRACK_TRUTH:                                      # (TRACK_TRUTH) the seconds each has not seen the enemy, for info["aux"]
            self._trk_step()
        if LG_QUIET_COST > 0:                                # (LG_QUIET_COST) the lightning gun carried while the enemy is away
            self._lg_quiet(reward)
        else:
            self.lgq_t = None                                # (off, by a live setting: his clock begins again when it is on)
        self._ps("lg_quiet", reward)
        if GAME_ON:                                          # (WIN_W / FADE_V) the blend in the games; its counters always
            self._wb_blend(reward, info)
            if WIN_SHAPE_K > 0:                              # (WIN_SHAPE_K, v0.6.1) the shaping, after the blend: not faded
                self._wsh_pay(reward, info)
        self._pt_end(info)
        info["r_long"] = self.r_long.copy()                  # the game's part of this frame's pay, per player
        if LEGS_LAB:                                         # (stage C, part 1) what his legs chose on the frames they carried him, or
            info["legs_lab"], info["legs_held"] = self.legs_lab.copy(), self.legs_wh.copy()      # would have in a withheld stretch
        if GAME_ON:
            info["win_pay"] = self.win_pay.copy()            # (WIN_PAY) the frame's pay by the game, per player
        if WIN_SHADOW:
            info["win_shadow"] = self.win_shadow.copy()      # (WIN_SHADOW) what WIN_PAY would have paid this frame (never paid)
            info["flat_frag"] = self.ws_flat.copy()          # ... and the flat frag pay of whole games this frame
        self._hand_step(done, died)                          # the weapon in his hand with nobody in view: the counters, always;
        if HAND_TEACH:                                       # (HAND_TEACH) the pros' shares as the target of his next reading of
            info["hand_lab"] = self.hand_lab.copy()          # the weapon key, for the trainer's --hand-teach
        if RJ_TEACH:                                         # (RJ_TEACH) "jump and fire now" for his next frame, for the trainer's --rj-teach
            info["rj_lab"] = self.rj_teach_label()
        if RJ_COPY or ROUTE_COPY:                            # (RJ_COPY, ROUTE_COPY) the runner's choice for his next frame, for the trainer's --rj-copy
            lab_ = self.rj_copy_label() if RJ_COPY else np.full((n, RJC_HEADS), -1, np.int8)
            if self.rc is not None:
                l2_ = self.route_copy_label()
                lab_ = np.where(l2_[:, :1] >= 0, l2_, lab_).astype(np.int8)
            info["rj_copy"] = lab_
        info["aux"] = self.aux(st, fall, events, died)      # (stage B, part 1) the truth the trainer's --aux lesson is made of
        if CONTROL_TRUTH:                                    # (CONTROL_TRUTH) "in control" of the frame CONTROL_D ago (labels only)
            self._ctl_step(done, info["aux"])
        if HEAD_EVENTS:                                      # (HEAD_EVENTS) the frame's events for the head
            dl_ = np.zeros(n, np.float32)
            for (i_, v_), d_ in st["by"].items():
                if i_ != v_:
                    dl_[i_] += d_
            fr_ = np.zeros(n, np.float32)
            for e_ in events:
                if e_["killer"] >= 0 and e_["killer"] != e_["victim"]:
                    fr_[e_["killer"]] += 1.0
            self.note_combat(dl_, st["dmg_taken"] + (0.0 if fall is None else fall), fr_, died)
            self.note_frame()
        obs = self.observe()
        if AWARE_LOG:                                        # (AWARE_LOG) measuring only
            self._aware_log()
        if MOMENTS:                                          # the rounds begun from a saved moment are put in place; this frame's
            self._moment_step(obs, done, died, info)         # moments are saved
        if HEAD_EVENTS:
            self._hd_end(done)
        return obs, reward.astype(np.float32), done, info

"""Self-play PPO with memory (GRU) in the duel simulator, against a league of its own past versions.

    python sim/train_duel_rnn.py --map bloodrun,aerowalk,lostworld --minutes 480 --run duel_gru_v1

Model: encoder (2 x 256) -> GRU (512) -> heads for each control + a value estimate. ~1.6 M weights.
The memory is carried frame to frame and reset when the player dies or the round restarts; training runs
over whole rollout sequences (128 frames = 3.2 s) so the network learns what is worth remembering (where the
opponent went, when an item was taken).
League: in half of the matches both players are the current policy; in the other half the second player is
a frozen snapshot of an earlier version (a new snapshot every --snapshot-min minutes, the last 8 kept). Only
the current policy's players are trained on.
Uses the GPU when PyTorch has CUDA (the simulator itself always runs on CPU workers).
Logs to data/sim_runs/<run>/metrics.jsonl; saves policy.pt (+ snapshots/).
"""
import argparse
import copy
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DT_MIN = 0.025 / 60.0


def wv_pack(env, pre, info, G):
    """(--win-value, WIN_SHADOW) per seat [n, 3] float32: this frame's shadow WIN_PAY, a cut (the seat's game ended, began,
    or its clock jumped: a new game in the same step), in a game after the frame"""
    g0, t0 = pre
    g1, t1 = env.game, env.g_tick
    cut_m = ((g0 > 0) != (g1 > 0)) | ((g0 > 0) & (t1 != t0 + 1))
    m_ = np.arange(env.n) // G
    ws_ = np.asarray(info.get("win_shadow", np.zeros(env.n, np.float32)), np.float32)
    return np.stack([ws_, cut_m[m_].astype(np.float32), (g1 > 0)[m_].astype(np.float32)], 1)


def worker(remote, bsp, matches, seed, nav, loadout, item_reward, drill_p, drill_weapons, react_frames, kind_p, bot_p,
           teacher, lab_courses, lab_p, loadout_p, lab_items_p, lab_gun_p=0.0, dmg_taken_w=2.0, no_walk=False, arena_len=30.0, arena_full=0.5,
           env_module="duel_env", group=2, intent_seek=0.0, item_loss=0.5, stack_p=0.0, near_item_p=0.0, move_only=False):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    import importlib
    E_ = importlib.import_module(env_module)
    DuelEnv, WEAPONS_ = E_.DuelEnv, E_.WEAPONS
    env = DuelEnv(bsp, n_matches=matches, seed=seed, nav=nav, close_p=1.0, loadout=loadout, teacher=teacher,
                  **(dict(group=group) if group != 2 else {}))
    G = group
    env.item_reward = item_reward
    env.item_seek = float(os.environ.get("ITEM_SEEK", "0"))  # reward per second of travel gained toward a big item he can use
    env.intent_seek, env.item_loss = intent_seek, item_loss
    env.stack_p, env.near_item_p = stack_p, near_item_p
    env.drill_p = drill_p
    env.react_frames = react_frames[0]
    env.acquire_frames = react_frames[1]
    env.kind_p = kind_p
    if env.lab is not None:                                  # the test map: movement courses only (for now)
        env.lab_p = lab_p
        keys_ = [C["key"] for C in env.courses]             # a course named twice gets twice the time
        env.lab_course_ids = [keys_.index(n_) for n_ in lab_courses if n_ in keys_] or env.lab_course_ids
    env.bot_p = bot_p
    if loadout_p:
        env.loadout_p = loadout_p
    env.lab_items_p = lab_items_p
    env.lab_gun_p = lab_gun_p
    env.dmg_taken_w = dmg_taken_w
    env.no_walk = no_walk
    env.arena_len, env.arena_full_p = arena_len, arena_full
    if os.environ.get("ARENA_SETS"):                         # e.g. "rl;rl,lg;rl,rg;rl,rg,lg": each player draws one, separately
        env.arena_sets = [tuple(WEAPONS_.index(x) for x in s_.split(",")) for s_ in os.environ["ARENA_SETS"].split(";")]
    if os.environ.get("ARENA_ROOMS"):                        # "env", "box" or "box,env"
        env.arena_rooms = tuple({"box": 1, "env": 2, "yard": 3}[x] for x in os.environ["ARENA_ROOMS"].split(","))
    if os.environ.get("ARENA_STACK") == "0":                 # arena rounds start on the normal spawn health, no armor
        env.arena_stack = False
    env.sg_spawn = os.environ.get("NO_SG_SPAWN") != "1"   # set NO_SG_SPAWN=1: the shotgun only comes from pickups
    WEAPONS = WEAPONS_
    env.drill_weapons = tuple(WEAPONS.index(w) for w in drill_weapons.split(","))
    if hasattr(env, "teach_runs"):                           # (--teacher-skip: the key labels of this map's runs)
        m_ = os.path.splitext(os.path.basename(bsp))[0]
        skip_ = (os.environ.get("TEACHER_SKIP") or "").split(",")
        env.teach_runs = "none" if m_ in skip_ else ("jump" if m_ + ":item" in skip_ else "all")
    if hasattr(env, "count_even"):
        env.count_even = not move_only                       # the jump counters: his seats only (in a move-only simulator every seat)
    if hasattr(env, "legs_keep_who") and not move_only:      # (LEGS_KEEP) stretches are withheld from his seats only: the odd seats of the
        i_ = np.arange(env.n)                                # second half of a simulator's players are the league's, an older self who
        env.legs_keep_who = ~((i_ >= env.n // 2) & (i_ % G % 2 == 1))      # keeps his legs (and is never learnt from)
    if move_only:                                            # a map he only learns to move on (--move-maps): every round an item
        pj_ = env.jump_run_p if getattr(env, "jump_tries", None) else 0.0   # run or a jump run, in the shares they have in the run
        pr_ = env.rj_run_p if getattr(env, "rj_live", False) else 0.0       # (RJ_RUN_P: or a rocket jump run)
        assert env.item_run_p > 0 and env.route is not None, "--move-maps needs ITEM_RUN_P and the map's walking map"
        if pr_ > 0:
            env.item_run_p, env.rj_run_p = env.item_run_p / (env.item_run_p + pj_ + pr_), pr_ / (env.item_run_p + pj_ + pr_)
            env.jump_run_p, env.collect_fight_p = 1.0 - env.item_run_p - env.rj_run_p, 0.0
        else:
            env.item_run_p = env.item_run_p / (env.item_run_p + pj_)
            env.jump_run_p, env.collect_fight_p = 1.0 - env.item_run_p, 0.0
    env.round_t[:] = 1e9                                     # every round starts anew at the first step: until 2026-10-08 the
    env._teach_update()                                      # first round after a (re)start was played with every weapon at spawn
    legs_in = bool(getattr(E_, "LEGS_IN", False))            # (LEGS_IN, B-253) his legs' inputs go to the branch of his network
    remote.send((env.observe(), env.teach.copy(), env.aux() if hasattr(env, "aux") else None,        # (--aux) the truth of the first frame
                 env.hand_lab.astype(np.float16) if getattr(E_, "HAND_TEACH", False) else None,         # (--hand-teach) the first frame's label (none yet)
                 env.legs_prep() if legs_in else None,      # (LEGS_IN) the movement network's inputs of the frame about to be played
                 sorted(set(E_.INTENTS.index(l_) for l_ in (getattr(env, "route_goal", None) or ())     # (--item-floor) the map's big items
                            if l_ in E_.INTENTS and 1 <= E_.INTENTS.index(l_) <= 7))))                    # as intentions (MH .. YA2)
    last = {k: np.copy(v) for k, v in env.stats.items()}
    tw_ = dict(step=0.0, legs_prep=0.0, send=0.0, idle=0.0, frames=0)      # (time.rollout_parts) this worker's seconds, since the last "times"
    t_idle = time.perf_counter()
    LSD = {} if os.environ.get("LIVE_DEBUG") == "1" else None        # (live_settings.env) LIVE_DEBUG=1: this worker's prints
    while True:
        cmd, data = remote.recv()
        t_got = time.perf_counter()
        tw_["idle"] += t_got - t_idle                        # (waiting for the trainer: its network, the other workers)
        if cmd == "step":
            if isinstance(data, tuple) and len(data) == 3:   # (v0.4.2a, --rule-fade with BRAIN_READ) the brain's answer of this frame
                env.brain_in(data[2])                        # too (the legs' logits or None)
                if data[1] is not None:
                    env.legs_lg = data[1]
                data = data[0]
            elif isinstance(data, tuple):                    # (LEGS_IN) the actions and the branch's logits [players, 17]
                env.legs_lg = data[1]
                data = data[0]
            wv_pre = ((env.game.copy(), env.g_tick.copy()) if getattr(env, "ws_tab", None) is not None else None)   # (--win-value)
            obs, rew, done, info = env.step(data)
            if LSD is not None:                              # (LIVE_DEBUG=1) the matches begun since the last live settings
                ls_debug_step(LSD, env, done)
            t_st = time.perf_counter()
            tw_["step"] += t_st - t_got
            tw_["frames"] += 1
            delta = {k: env.stats[k] - last.get(k, 0) for k in env.stats}     # (a counter that begins in a running simulator: HOP_CHAIN by live.json)
            last = {k: np.copy(v) for k, v in env.stats.items()}
            s = env.state
            delta["air_fast"] = int(((np.hypot(s[:, 3], s[:, 4]) > 330) & (s[:, 6] < 0.5)).sum())
            delta["visible"] = int(env.visible.sum())
            delta["players"] = env.n
            delta["way_trips"] = list(getattr(env, "way_trips", ()))      # (WAYS) this step's trips between two places: [from, to, 16 points]
            # frags scored by even (learner) players and by odd players, for learner-vs-snapshot win tracking
            ev = info["events"]
            delta["kills_even"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % G % 2 == 0)
            delta["kills_odd"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % G % 2 == 1)
            # (B-247) the league count behind vs_snapshot_kill_share / vs_anchor_kill_share: kills in one-against-one normal
            # rounds and whole games only (a drill's kill is aim alone; in a group of three two seats of three are his), and
            # even so a hint, not a check: 9.6-second slices against one opponent network an update
            hint_kill = [e for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and G == 2 and int(env.kind[e["killer"] // G]) == 0]
            delta["match_of_kill"] = [e["killer"] // G for e in hint_kill]
            delta["even_kill"] = [e["killer"] % G % 2 == 0 for e in hint_kill]
            lx_ = env.legs_prep() if legs_in else None       # (LEGS_IN) the movement network's inputs of the next frame
            t_lp = time.perf_counter()
            tw_["legs_prep"] += t_lp - t_st
            remote.send((obs, rew, done, delta, env.script > 0, env.teach.copy(), env.intent_live.copy(), env.intent_teach.copy(),
                         (env.key_dec.copy() if getattr(env, "je_rng", None) is None else (env.key_dec + 2 * env.key_jump).astype(np.int8))   # (JUMP_EVERY: 2 = the
                         if hasattr(env, "key_dec") else np.ones(env.n, bool),                               # jump alone was read)
                         env.legs_live.copy() if hasattr(env, "legs_live") else np.zeros(env.n, bool),      # (LEGS) the switch was read,
                         env.legs_on.copy() if hasattr(env, "legs_on") else np.zeros(env.n, bool),          # his legs moved him
                         np.asarray(info.get("r_long", np.zeros(env.n, np.float32)), np.float32),           # (v0.2) the part of this frame's pay that is for items and stack
                         info.get("aux"),                                                                   # (--aux) the truth the lesson's labels are made of (None: an older simulator)
                         (np.concatenate([info["legs_lab"], info["legs_held"][:, None]], 1).astype(np.int8)    # (--legs-teach) his legs' four choices
                          if "legs_lab" in info else None),                                               # (-1: no label), the stretch withheld; None: the simulator gives none
                         (info["hand_lab"].astype(np.float16) if "hand_lab" in info else None),            # (--hand-teach) the target of his NEXT reading of the weapon key (zeros: none)
                         lx_,                                                                               # (LEGS_IN) the movement network's inputs of the next frame
                         (np.asarray(env.legs_raw, np.int8) if legs_in and getattr(env, "legs_raw", None) is not None    # (--legs-learn) the branch's own draws
                          and len(env.legs_raw) == env.n else (np.full((env.n, 4), -1, np.int8) if legs_in else None)),  # of this frame (-1: none)
                         (env.solo_now.copy() if getattr(env, "solo_now", None) is not None else np.zeros(env.n, bool)),    # (SOLO_SELF) in his runs
                         (info["rj_lab"] if "rj_lab" in info else None),                                     # (--rj-teach) "jump and fire now" for his NEXT frame
                         (info["rj_copy"] if "rj_copy" in info else None),                                   # (--rj-copy) the runner's choices for his NEXT frame
                         (wv_pack(env, wv_pre, info, G) if wv_pre is not None else None)))                  # (--win-value) shadow pay, cut, in a game
            tw_["send"] += time.perf_counter() - t_lp        # (the reply's pickling and the pipe)
        elif cmd == "brain_g":                               # (v0.4.2a, --rule-fade with BRAIN_READ) each seat's chance that a life
            env.set_brain_g(data)                            # begun from now on reads the brain's answer
            remote.send(True)
        elif cmd == "times":                                 # (time.rollout_parts) this worker's seconds since the last call, then anew
            remote.send(dict(tw_))
            tw_ = dict(step=0.0, legs_prep=0.0, send=0.0, idle=0.0, frames=0)
        elif cmd == "curriculum":
            env.close_p, env.round_len, env.dmg_reward, env.intent_seek = data
            remote.send(True)
        elif cmd == "live":                                  # (B-265, live.json) pay weights changed between two rollouts: the
            vals_, dtw_ = data                               # module's globals as an import with that environment makes them,
            now_ = E_.live_set(vals_)                        # and the damage-taken weight of this simulator
            if dtw_ is not None:
                env.dmg_taken_w = float(dtw_)
            remote.send(dict(now_, DMG_TAKEN_W=float(env.dmg_taken_w)))
        elif cmd == "live_settings":                         # (live_settings.env, the safe restart: see LS_SPEC) between two
            remote.send(ls_worker(E_, env, data, bsp, move_only, LSD))     # rollouts: the module's values as its import makes them
        elif cmd == "head_events":                           # (--head) the head's events since the last call, on its ticks (None: the
            remote.send(np.asarray(env.head_events(), np.float32) if hasattr(env, "head_events") else None)   # simulator has none: zeros)
        elif cmd == "close":
            break
        t_idle = time.perf_counter()


def jump_far_rec(agg, agg_map):
    """(JUMP_FAR_P, v0.3.6) the jump runs' tries by start, near (standing, a second or two of way) and far (moving, 3 to 5 s
    of way): tries begun and over per try (an over may come in the update after its try began: a small count can read
    above 1), all maps and by map [near tries, near over, far tries, far over]"""
    def one_(v_):
        x_ = np.atleast_1d(v_.get("jump_far", np.zeros(4))).astype(np.float64)
        x_ = x_ if len(x_) == 4 else np.zeros(4)
        return x_
    a_ = one_(agg)
    return dict(near_tries=int(a_[0]), near_over=round(float(a_[1] / max(1.0, a_[0])), 3),
                far_tries=int(a_[2]), far_over=round(float(a_[3] / max(1.0, a_[2])), 3),
                by_map={m_: [int(x_[0]), round(float(x_[1] / max(1.0, x_[0])), 2), int(x_[2]), round(float(x_[3] / max(1.0, x_[2])), 2)]
                        for m_, x_ in ((m_, one_(v_)) for m_, v_ in agg_map.items()) if x_[0] + x_[2] > 0})


BRAIN_PFX = ("track.", "trackz.", "belief.", "ahead.")              # (v0.4.0) the brain's layers: the readout, its second part (--track-z), the belief
BRAIN_PFX = BRAIN_PFX + ("control.",)                               # (v0.4.3, --control) the readout "in control": a brain layer
LIVE_TRAINER = ("DMG_TAKEN_W", "DMG_REWARD", "INFO_PAY", "TRACK_W", "TRACK_TRUNK", "TRACK_Z_W", "BTOK_GATE_CAP", "BTOK_GATE_OPEN",
                "BELIEF_LR", "AHEAD_W", "RJ_TEACH_W", "FADE_CAP", "FADE_OPEN", "RJ_COPY_W",
                "INTENT_TEACH_W")   # (v0.4.3: a factor on the item rule's weight, its floor included: 0 silences it)   # (v0.4.2a: the rule fade's cap and its opening's minutes)     # (v0.4.1: the brain token's gate: its cap and its opening's minutes; the brain's rate; the ahead lesson's factor)     # (B-265) the trainer's own live names: --dmg-taken-w, --dmg-reward, --info-pay (v0.3.11), --track, --track-trunk (v0.3.11b: the readout's lesson and its share into his memory)
LIVE_TRAINER = LIVE_TRAINER + ("CONTROL_W",)                       # (v0.4.3, --control) a factor on the lesson "in control"   # (v0.4.2a: the rule fade's cap and its opening's minutes)     # (v0.4.1: the brain token's gate: its cap and its opening's minutes; the brain's rate; the ahead lesson's factor)     # (B-265) the trainer's own live names: --dmg-taken-w, --dmg-reward, --info-pay (v0.3.11), --track, --track-trunk (v0.3.11b: the readout's lesson and its share into his memory)
LIVE_TRAINER = LIVE_TRAINER + ("BRAIN_HUMAN_W",)                   # (brainppl, --brain-human) the people's lesson's weight beside self-play's

LIVE_TRAINER = LIVE_TRAINER + ("WIN_VALUE_W",)                     # (v0.4.3, --win-value) a factor on the shadow win value's rate
LIVE_TRAINER = LIVE_TRAINER + ("ITEM_FLOOR", "ITEM_FLOOR_W")          # (2026-10-25, --item-floor) the floor on his item intentions by map, its weight
LIVE_TRAINER = LIVE_TRAINER + ("H2_GATE_CAP", "H2_GATE_OPEN", "H2_PG", "H2_PLAN_GRAD")    # (v0.4.3, --head2) the strategy head's gate: its cap and its opening's minutes; its own lesson's factor; the plan's gradient into it


def live_read(path, E_, start, trainer_start):
    """(B-265) live.json -> (vals, trainer_vals, None) or (None, None, reason). The file is one JSON object {NAME: value}; a
    name is one of the simulator's LIVE_VARS or LIVE_TRAINER, a value a number or (ITEM_FLAT) the string the environment
    variable takes. The values in force are the run's start (its environment, its arguments) with the file laid over it:
    a name left out of the file has its start value, so {} puts everything back. Anything else refuses the whole file."""
    try:
        raw_ = json.load(open(path, encoding="utf-8"))
    except Exception as e_:
        return None, None, "not JSON: {}".format(e_)
    if not isinstance(raw_, dict):
        return None, None, "not a JSON object"
    allow_ = tuple(getattr(E_, "LIVE_VARS", ())) + LIVE_TRAINER
    bad_ = sorted(k_ for k_ in raw_ if k_ not in allow_)
    if bad_:
        return None, None, "not allowed: {} (allowed: {})".format(bad_, list(allow_))
    vals, tv = dict(start), dict(trainer_start)
    for k_, x_ in raw_.items():
        if isinstance(x_, bool) or not isinstance(x_, (int, float, str)):
            return None, None, "{}: {!r} is not a number or a string".format(k_, x_)
        if k_ not in getattr(E_, "LIVE_STR", ("ITEM_FLAT",)):          # (ITEM_FLAT, BIG_PICK_SEQ: the environment's string)
            try:
                f_ = float(x_)
            except ValueError:
                return None, None, "{}: {!r} is not a number".format(k_, x_)
            if not np.isfinite(f_) or f_ < 0:
                return None, None, "{}: {!r} is not a number of 0 or more".format(k_, x_)
        if k_ in LIVE_TRAINER:
            tv[k_] = float(x_)
        else:
            vals[k_] = str(x_)
    try:
        E_.live_values(vals.get)
    except Exception as e_:
        return None, None, "a value the simulator can not read: {}".format(e_)
    return vals, tv, None


# ---------------------------------------------------------------------------------------------------------------------
# The safe restart (live_settings.env; the owner, 2026-10-21: "you don't cut off any current games but change the ones
# that will be starting"). <run>/live_settings.env holds NAME=VALUE lines (# comments; tools/live_set.py writes it). The
# trainer reads it between two rollouts when its time stamp changes, checks every name against LS_SPEC, lays the file over
# the run's start environment (a name left out has its start value: an empty file puts everything back; a deleted file
# changes nothing) and sends the changes to every simulator. Two kinds of name:
#   "start"  read by the simulator only when a match's round, whole game or jump-run try begins (the draw of the round's
#            kind, the try's jump and its start). Set in every simulator between two rollouts, they reach exactly the
#            rounds, games and tries that begin after that: none under way sees them. The owner's safe restart.
#   "frame"  read on every frame while a game plays (the pays, the hearing). The module globals are shared by all of a
#            simulator's matches (168 in a run), stepped in one call, and with whole ten-minute games there is never a
#            moment when none of a simulator's matches is in a game: these are set between two rollouts for every match
#            at once. No game is ended or cut off; the games under way go on with the new value from their next frame.
# Each value is made as the module makes it at import (the same parse, the derived globals: HF_STEP_FRAMES, MOMENT_P,
# SHOT_W's table in place; the LIVE_VARS by the module's own live_values). Refused whole, nothing changed: a name not in
# the list or not in the simulator module, a value the module could not read, a change that would switch on or off a part
# built at the start (GAME_ON, MOMENTS; PRO_START_P, PRO_JSTART_P, JUMP_FAR_P from 0), a name that live.json sets.
# Logged: the run log ("live_settings: ..."), metrics.jsonl ("live_settings" on the next update's line),
# <run>/live_settings.history.jsonl, the checkpoint ("live_settings": the file in force; env_vars and game_vars as set).
# LIVE_DEBUG=1: every simulator prints what it set and, every 256 frames, how many of its matches have begun a round since.
# Without the file none of this runs (no message, no draw).
LS_SPEC = {                                                  # name -> (kind, parse)
    "GAME_P": ("start", "share"), "PRO_START_P": ("start", "share"), "JUMP_RUN_P": ("start", "env_share"),
    "PEOPLE_START_SHARE": ("start", "share"), "GEN_START_SHARE": ("start", "share"), "MOMENT_WEIGHTED": ("start", "int"), "RUN_TARGET_W": ("start", "int"),   # (2026-10-25: people's starts, weighted moments, targeted item runs)
    "ITEM_RUN_P": ("start", "env_share"),                     # (2026-10-25: the item runs' share, live: the simulator's attribute)
    "RJ_RUN_P": ("start", "env_share"),                      # (2026-10-23: rocket jump runs; their ways are built at the start: RJ_RUN_P > 0 or RJ_ONLY)
    "JUMP_W_FLOOR": ("start", "floor"), "JUMP_W_CAP": ("start", "pos"), "JUMP_W_DROP": ("start", "pos"),
    "JUMP_FOCUS_W": ("start", "pos"), "PRO_JSTART_P": ("start", "share"), "JUMP_FAR_P": ("start", "share"),
    "RAIL_STREAK_PAY": ("frame", "pos"), "RAIL_STREAK_CAP": ("frame", "int"), "JUMP_OVER_PAY": ("frame", "pos"),
    "SHOT_W": ("frame", "shot_w"), "PREAIM_PAY": ("frame", "pos"),
    "HF_STEP_DT": ("frame", "above0"), "HF_STEP_SPEED": ("frame", "pos"), "HF_DIR": ("frame", "pos"),
    "HF_LOUD": ("frame", "pos"), "HF_HUM_TAU": ("frame", "pos"), "HF_UP": ("frame", "pos"),
    "RJ_TEACH_PITCH": ("frame", "pos"), "RJ_TEACH_R": ("frame", "pos"), "RJ_LOOK_FREE": ("frame", "pos"),   # (RJ_TEACH, 2026-10-23)
    "RJ_COPY_PITCH": ("frame", "pos"), "RJ_COPY_R": ("frame", "pos"), "RJ_COPY_V": ("frame", "pos"),        # (RJ_COPY, 2026-10-23: the runner's
    "RJ_COPY_YAW": ("frame", "pos"), "RJ_COPY_PTOL": ("frame", "pos"),                                      # take-off condition)
}                                                            # ... and every name of the module's LIVE_VARS: ("frame", "live")
LS_FROM_ZERO = ("PRO_START_P", "PRO_JSTART_P", "JUMP_FAR_P")  # their tables are built at the start only when they are on
_LS_ORIG = {}                                                # this process's module values at import (before any change)


def ls_names(E_):
    """the names live_settings.env may set with this simulator module: {name: (kind, parse)}"""
    d_ = {k_: v_ for k_, v_ in LS_SPEC.items() if k_ in ("JUMP_RUN_P", "ITEM_RUN_P") or (hasattr(E_, k_) and
          (v_[1] != "pos" or isinstance(getattr(E_, k_), float)))}            # (PREAIM_PAY: only where it is one float)
    for k_ in getattr(E_, "LIVE_VARS", ()):
        d_.setdefault(k_, ("frame", "live"))
    return d_


def ls_orig(E_):
    """the module's values of the LS_SPEC names as the import made them (taken once a process, before anything is set)"""
    if id(E_) not in _LS_ORIG:
        _LS_ORIG[id(E_)] = {k_: (np.copy(getattr(E_, k_)) if isinstance(getattr(E_, k_), np.ndarray) else getattr(E_, k_))
                            for k_ in LS_SPEC if hasattr(E_, k_)}
    return _LS_ORIG[id(E_)]


def ls_derive(E_, get):
    """the module globals (and the simulator's own attributes) that the environment get(name) -> string or None makes, as
    the import makes them -> (globals {name: value}, env {name: value}). Raises ValueError on a value or a change the
    module could not take."""
    o_, names = ls_orig(E_), ls_names(E_)
    g, ev = {}, {}
    for k_, (kind_, how_) in names.items():
        if how_ == "live":
            continue
        s_ = get(k_)
        if s_ is None:                                       # unset now and at the start: the import's value
            if how_ == "env_share":                          # (JUMP_RUN_P, RJ_RUN_P: the simulator's attribute, 0 unset)
                ev[k_] = 0.0
            elif k_ in o_:
                g[k_] = o_[k_]
            continue
        s_ = str(s_).strip()
        try:
            if how_ == "shot_w":                             # (as the import: ones, then NAME:value pairs)
                w_ = np.ones(len(E_.WEAPONS), np.float32)
                for part_ in s_.split(","):
                    if ":" in part_:
                        w_[E_.WEAPONS.index(part_.split(":")[0].strip())] = float(part_.split(":")[1])
                x_ = w_
            elif how_ == "int":
                x_ = int(float(s_))
            else:
                x_ = float(s_)
        except (ValueError, IndexError) as e_:
            raise ValueError("{}={!r}: the simulator can not read it ({})".format(k_, s_, e_))
        for y_ in np.atleast_1d(x_):
            if not np.isfinite(float(y_)) or float(y_) < 0:
                raise ValueError("{}={!r}: not a number of 0 or more".format(k_, s_))
        if how_ in ("share", "env_share", "floor") and x_ > 1.0:
            raise ValueError("{}={!r}: a share, at most 1".format(k_, s_))
        if how_ in ("floor", "above0") and x_ <= 0:
            raise ValueError("{}={!r}: must be above 0".format(k_, s_))
        if k_ == "RJ_RUN_P" and x_ > 0 and float(o_.get(k_, 0.0)) <= 0 and not getattr(E_, "RJ_ONLY_MAP", None):
            raise ValueError("RJ_RUN_P: 0 at the start and no RJ_ONLY (the rocket jump runs' ways were not built): it can not be switched on in a running trainer")
        if k_ in LS_FROM_ZERO and float(o_.get(k_, 0.0)) <= 0 and x_ > 0:
            raise ValueError("{}: 0 at the start (its tables were not built): it can not be switched on in a running trainer".format(k_))
        (ev if how_ == "env_share" else g)[k_] = x_
    if "HF_STEP_DT" in g:                                    # (the derived globals, as the import makes them)
        g["HF_STEP_FRAMES"] = max(1, int(round(float(g["HF_STEP_DT"]) / float(E_.DT))))
    if "GAME_P" in g or "PRO_START_P" in g:
        gp_ = float(g.get("GAME_P", getattr(E_, "GAME_P", 0.0)))
        ps_ = float(g.get("PRO_START_P", getattr(E_, "PRO_START_P", 0.0)))
        lp_ = float(getattr(E_, "LATE_P", 0.0))
        mp_ = (float(getattr(E_, "MID_START_P", 0.0)) + float(getattr(E_, "SPAWN_START_P", 0.0))
               + float(getattr(E_, "RAIL_START_P", 0.0)) + ps_)
        if hasattr(E_, "GAME_ON") and (gp_ > 0 or lp_ > 0) != bool(E_.GAME_ON):
            raise ValueError("GAME_P={}: whole games would be switched {} (built at the start)".format(gp_, "on" if gp_ > 0 else "off"))
        if hasattr(E_, "MOMENTS") and (mp_ > 0) != bool(E_.MOMENTS):
            raise ValueError("PRO_START_P={}: the moment starts (MOMENTS) would be switched {} (built at the start)".format(
                ps_, "on" if mp_ > 0 else "off"))
        if gp_ + lp_ + mp_ > 1.0 + 1e-9:
            raise ValueError("GAME_P + LATE_P + the moment starts = {:.4f}: shares of the games' time, at most 1".format(gp_ + lp_ + mp_))
        if hasattr(E_, "MOMENT_P"):
            g["MOMENT_P"] = mp_
    if any(v_[1] == "live" for v_ in names.values()):        # the module's own pay weights: its own parse (B-265)
        try:
            g.update(E_.live_values(get))
        except Exception as e_:
            raise ValueError("a value the simulator can not read: {}".format(e_))
    return g, ev


def ls_apply(E_, vals, env=None, move_only=False):
    """vals {name: the environment's string, or None = unset}: checked first (ls_derive over this process's environment),
    then the environment, the module globals and (env) the simulator's attributes set -> (the names set, the names left)"""
    names = ls_names(E_)
    bad_ = [k_ for k_ in vals if k_ not in names]
    if bad_:
        raise ValueError("not a live setting here: {}".format(bad_))
    env_ = dict(os.environ)
    for k_, x_ in vals.items():
        if x_ is None:
            env_.pop(k_, None)
        else:
            env_[k_] = str(x_)
    g, ev = ls_derive(E_, env_.get)                          # (raises before anything is set)
    for k_, x_ in vals.items():
        if x_ is None:
            os.environ.pop(k_, None)
        else:
            os.environ[k_] = str(x_)
    for k_, x_ in g.items():
        if isinstance(x_, np.ndarray) and isinstance(getattr(E_, k_, None), np.ndarray):
            getattr(E_, k_)[...] = x_                        # (SHOT_W: the module's own table, in place)
        else:
            setattr(E_, k_, (dict(x_) if isinstance(x_, dict) else x_))
    left = []
    if env is not None:
        if "JUMP_RUN_P" in vals:
            if move_only:                                    # (--move-maps: its shares were worked out at the start)
                left.append("JUMP_RUN_P")
            else:
                env.jump_run_p = float(ev.get("JUMP_RUN_P", 0.0))
        if "ITEM_RUN_P" in vals:
            if move_only:                                    # (--move-maps: its shares were worked out at the start)
                left.append("ITEM_RUN_P")
            else:
                env.item_run_p = float(ev.get("ITEM_RUN_P", 0.0))
        if "RJ_RUN_P" in vals:
            if move_only:                                    # (--move-maps: its shares were worked out at the start)
                left.append("RJ_RUN_P")
            elif hasattr(env, "rj_run_p"):                   # (a map without the runs' ways keeps none: rj_live)
                env.rj_run_p = float(ev.get("RJ_RUN_P", 0.0))
        if "JUMP_FOCUS_W" in vals and getattr(env, "jfocus", None) is not None and getattr(env, "jumps", None) is not None:
            mp_ = os.path.splitext(os.path.basename(getattr(env, "_ls_bsp", "")))[0]     # (as __init__ makes it)
            env.jfocus = np.array([E_.JUMP_FOCUS_W if j_["id"] in getattr(E_, "JUMP_FOCUS", {}).get(mp_, ()) else 1.0
                                   for j_ in env.jumps])
    return sorted(vals), left


def ls_worker(E_, env, data, bsp, move_only, dbg):
    """(the worker's "live_settings") set the values -> the reply: what was set, how its matches stood"""
    env._ls_bsp = bsp
    try:
        set_, left_ = ls_apply(E_, data["vals"], env, move_only)
    except Exception as e_:
        return dict(ok=False, why=str(e_))
    gm_ = np.asarray(getattr(env, "game", np.zeros(0)))
    rep = dict(ok=True, seq=data["seq"], set=set_, left=left_, matches=int(env.M), in_games=int(np.count_nonzero(gm_)))
    if dbg is not None:                                      # (LIVE_DEBUG=1)
        dbg.update(seq=data["seq"], fresh=np.zeros(env.M, bool), frames=0)
        now_ = {k_: (getattr(E_, k_).tolist() if isinstance(getattr(E_, k_, None), np.ndarray) else getattr(E_, k_, None))
                for k_ in set_ if hasattr(E_, k_)}
        if "JUMP_RUN_P" in set_:
            now_["env.jump_run_p"] = float(getattr(env, "jump_run_p", -1))
        if "RJ_RUN_P" in set_:
            now_["env.rj_run_p"] = float(getattr(env, "rj_run_p", -1))
            now_["env.rj_live"] = bool(getattr(env, "rj_live", False))
        print("LIVE_DEBUG {} seq {}: set {} (left {}); the module now {}; {} of {} matches in a whole game or late round".format(
            os.path.basename(bsp), data["seq"], set_, left_, now_, rep["in_games"], env.M), flush=True)
    return rep


def ls_debug_step(dbg, env, done):
    """(LIVE_DEBUG=1) after a step: the matches that have begun a new round (a game, a try) since the last settings"""
    if not dbg or "fresh" not in dbg:
        return
    dbg["fresh"] |= np.asarray(done, bool).reshape(env.M, -1).any(1)
    dbg["frames"] += 1
    if dbg["frames"] % 256 == 0:
        print("LIVE_DEBUG seq {}: {} frames on, {} of {} matches have begun a round under the new settings ({} still in the "
              "round they had)".format(dbg["seq"], dbg["frames"], int(dbg["fresh"].sum()), env.M, int((~dbg["fresh"]).sum())), flush=True)


def ls_parse(txt):
    """live_settings.env -> ({name: value string}, None) or (None, reason)"""
    vals = {}
    for n_, line_ in enumerate(txt.splitlines(), 1):
        s_ = line_.strip().lstrip("﻿")
        if not s_ or s_.startswith("#"):
            continue
        if "=" not in s_:
            return None, "line {}: {!r} is not NAME=VALUE".format(n_, s_)
        k_, x_ = (t_.strip() for t_ in s_.split("=", 1))
        if not k_ or not all(c_.isupper() or c_.isdigit() or c_ == "_" for c_ in k_):
            return None, "line {}: {!r} is not a setting's name".format(n_, k_)
        if not x_:
            return None, "line {}: {} has no value (leave the line out for its start value)".format(n_, k_)
        if k_ in vals:
            return None, "line {}: {} is named twice".format(n_, k_)
        vals[k_] = x_
    return vals, None


def live_settings_init(out, E_):
    """the safe restart's books for this trainer (see LS_SPEC): the run's start environment of every live setting"""
    ls_orig(E_)
    nm_ = ls_names(E_)
    return dict(path=os.path.join(out, "live_settings.env"), hist=os.path.join(out, "live_settings.history.jsonl"),
                start={k_: os.environ.get(k_) for k_ in nm_}, now={k_: os.environ.get(k_) for k_ in nm_},
                seen=None, text=None, seq=0, file={})


def live_settings_poll(LS, pipes, E_, update, mins, live_start, live_path):
    """between two rollouts: a new or changed live_settings.env -> into every simulator and this process -> the record for
    the update's line (None: nothing new)"""
    try:
        st_ = os.stat(LS["path"])
    except OSError:
        return None                                          # (no file: nothing, as before)
    key_ = (st_.st_mtime_ns, st_.st_size)
    if key_ == LS["seen"]:
        return None
    LS["seen"] = key_
    try:
        txt_ = open(LS["path"], encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e_:
        LS["seen"] = None
        print("live_settings: {} could not be read ({}): tried again at the next update".format(LS["path"], e_), flush=True)
        return None
    if txt_ == LS["text"]:
        return None
    LS["text"] = txt_
    hist_ = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), update=update, minutes=round(mins, 2))
    vals, why_ = ls_parse(txt_)
    names = ls_names(E_)
    if why_ is None:
        bad_ = sorted(k_ for k_ in vals if k_ not in names)
        if bad_:
            why_ = "not a live setting: {} (allowed: {})".format(bad_, sorted(names))
    if why_ is None and os.path.exists(live_path):           # (one file a name: live.json sets its names at once)
        try:
            lj_ = json.load(open(live_path, encoding="utf-8"))
            both_ = sorted(k_ for k_ in vals if isinstance(lj_, dict) and k_ in lj_)
            if both_:
                why_ = "named in live.json too: {} (one file a name)".format(both_)
        except Exception:
            pass
    want = None
    if why_ is None:
        want = {k_: (vals[k_] if k_ in vals else LS["start"].get(k_)) for k_ in names}
        env_ = {k_: x_ for k_, x_ in os.environ.items() if k_ not in names}
        env_.update({k_: x_ for k_, x_ in want.items() if x_ is not None})
        try:
            ls_derive(E_, env_.get)
        except ValueError as e_:
            why_ = str(e_)
    if why_ is not None:
        print("live_settings: {} REFUSED at update {}, nothing changed: {}".format(LS["path"], update, why_), flush=True)
        with open(LS["hist"], "a", encoding="utf-8") as f_:
            f_.write(json.dumps(dict(hist_, refused=why_)) + "\n")
        return dict(refused=why_, from_update=update)
    ch_ = {k_: x_ for k_, x_ in want.items() if x_ != LS["now"].get(k_)}
    LS["seq"] += 1
    reps = []
    if ch_:
        for p in pipes:
            p.send(("live_settings", dict(vals=ch_, seq=LS["seq"])))
        reps = [p.recv() for p in pipes]
        ls_apply(E_, ch_)                                    # (this process too: the checkpoints' env_vars and game_vars)
        for k_ in ch_:
            if k_ in live_start:                             # (live.json's start follows: a later live.json keeps these)
                live_start[k_] = ch_[k_]
    bad_ = [r_.get("why") for r_ in reps if not r_.get("ok")]
    diff_ = {k_: [LS["now"].get(k_), ch_[k_]] for k_ in sorted(ch_)}
    LS["now"].update(ch_)
    LS["file"] = dict(vals)
    rec = dict(from_update=update, seq=LS["seq"], changed=diff_,
               at_next_round=sorted(k_ for k_ in ch_ if names[k_][0] == "start"),
               at_once=sorted(k_ for k_ in ch_ if names[k_][0] != "start"),
               matches=int(sum(r_.get("matches", 0) for r_ in reps)), in_games=int(sum(r_.get("in_games", 0) for r_ in reps)))
    left_ = sorted({k_ for r_ in reps for k_ in r_.get("left", ())})
    if left_:
        rec["left_in_move_maps"] = left_
    if bad_:
        rec["failed"] = bad_
    with open(LS["hist"], "a", encoding="utf-8") as f_:
        f_.write(json.dumps(dict(hist_, file=vals, **rec)) + "\n")
    show_ = ", ".join("{} {} -> {}".format(k_, "(unset)" if o_ is None else o_, "(unset)" if n_ is None else n_)
                      for k_, (o_, n_) in diff_.items()) or "nothing"
    print("live_settings: from update {} (seq {}): {}; at each match's next round, game or try: {}; at once (read every "
          "frame): {}; {} of {} matches are in a whole game and go on{}{}".format(
              update, LS["seq"], show_, rec["at_next_round"] or "-", rec["at_once"] or "-", rec["in_games"], rec["matches"],
              "; not in the move-only maps: {}".format(left_) if left_ else "",
              "; FAILED in {} simulators: {}".format(len(bad_), bad_[:2]) if bad_ else ""), flush=True)
    return rec


def aux_labels(A, dn, ix, frames):
    """(--aux; stage B, part 1) the labels of the things he is asked to foretell, made by hindsight inside one rollout.
      A   [T+1, n, columns] float32: row t is the simulator's info["aux"] as the game stood BEFORE step t (row T: after the
          last step). A row's event columns (damage, frag, fragged, died) are those of the step before it: step t's are in
          row t+1
      dn  [T, n]: his round ended in step t
      ix  {column name: its index} (the simulator's AUX_COLS);  frames: the windows (appear, fight, damage), in frames
    ->  Y [T, n, 8] float32: the enemy's place / 1500 (forward, left, up); the angles from his view to where the enemy next
                             appears / 90 (sideways -180 to 180 with left as plus, up-down with down as plus: the signs of
                             his crosshair inputs); the damage dealt less taken / 100; the seconds to the mega and to the
                             red armor / 40
        M [T, n, 6] bool:    the label is there: place, appear, the fight's end, its damage, mega, red
        C [T, n] int64:      the fight's end: 0 neither, 1 he makes a frag, 2 he is fragged (whichever comes first; a frag
                             of his in the frame he is fragged in counts as his)
    Where the labels are:
      place    the enemy is alive and not in view
      appear   the same, and the enemy is in view at a later frame at most `appear` frames on, the first such frame
      fight    the enemy is in view, and the whole window of `fight` (`damage`) frames lies inside the rollout: a frame
               whose window runs past the rollout's end has no label (labelled by what is seen of it, the late frames
               of every rollout would say "neither" and "little damage" for want of a future)
      mega, red   the map has one
    A step in which his round ends or he dies ends his hindsight: nothing after it counts for a frame before it.
    Whole tensors over the players and the frames; no loop over either."""
    import torch
    T, n = A.shape[0] - 1, A.shape[1]
    Wa, Wf, Wd = (int(x) for x in frames)
    dev_ = A.device
    S, E = A[:T], A[1:]                                      # the game before step t; what happened in step t
    BIG = 1 << 30
    tt = torch.arange(T + 1, device=dev_)[:, None]

    def nxt(flag):                                           # for every row, the first row at or after it where flag holds (BIG: none)
        c_ = torch.where(flag, tt[:flag.shape[0]].expand(flag.shape), torch.full(flag.shape, BIG, dtype=torch.long, device=dev_))
        return torch.flip(torch.cummin(torch.flip(c_, (0,)), 0).values, (0,))

    t0 = tt[:T]
    vis = A[..., ix["en_in_view"]] > 0.5                     # [T+1, n]
    hid = (S[..., ix["en_alive"]] > 0.5) & ~vis[:T]          # there is an enemy and he is not in view
    nc = nxt((dn > 0.5) | (E[..., ix["died"]] > 0.5))        # the step that ends his hindsight
    Y = torch.zeros(T, n, 8, dtype=torch.float32, device=dev_)
    M = torch.zeros(T, n, 6, dtype=torch.bool, device=dev_)
    # (a) where the unseen enemy is
    Y[..., 0:3] = S[..., ix["en_fwd"]:ix["en_fwd"] + 3] / 1500.0
    M[..., 0] = hid
    # (b) where he next appears: the enemy's place in the world at the first later frame he is in view, as angles from
    #     this frame's eyes and view
    na = nxt(vis)[:T]
    M[..., 1] = hid & (na - t0 <= Wa) & (nc >= na)
    yw = torch.deg2rad(A[..., ix["yaw"]])
    c_, s_ = torch.cos(yw), torch.sin(yw)
    f_, l_ = A[..., ix["en_fwd"]], A[..., ix["en_left"]]
    ew = torch.stack([A[..., ix["x"]] + c_ * f_ - s_ * l_, A[..., ix["y"]] + s_ * f_ + c_ * l_, A[..., ix["z"]] + A[..., ix["en_up"]]], -1)
    to = torch.gather(ew, 0, na.clamp(max=T)[..., None].expand(T, n, 3)) - S[..., ix["x"]:ix["x"] + 3]
    tz = to[..., 2] + 4.0 - S[..., ix["eye_h"]]              # (to the same point of him as his crosshair inputs: 4 above his place)
    ay = torch.rad2deg(torch.atan2(to[..., 1], to[..., 0])) - S[..., ix["yaw"]]
    ap = -torch.rad2deg(torch.atan2(tz, torch.hypot(to[..., 0], to[..., 1]) + 1e-6)) - S[..., ix["pitch"]]
    Y[..., 3] = ((ay + 180.0) % 360.0 - 180.0) / 90.0 * M[..., 1]
    Y[..., 4] = ap / 90.0 * M[..., 1]
    # (c) how the next fight ends, and the damage dealt less taken
    nf, nd = nxt(E[..., ix["frag"]] > 0.5), nxt(E[..., ix["fragged"]] > 0.5)
    lim = torch.minimum(t0 + (Wf - 1), nc)
    C = (nd <= lim).long() * 2
    C = torch.where((nf <= lim) & (nf <= nd), torch.ones_like(C), C)
    M[..., 2] = vis[:T] & (t0 + Wf <= T)
    P = torch.cat([torch.zeros(1, n, dtype=torch.float64, device=dev_),
                   torch.cumsum((E[..., ix["dmg_dealt"]] - E[..., ix["dmg_taken"]]).double(), 0)])
    end = torch.minimum(t0 + (Wd - 1), nc).clamp(max=T - 1)
    Y[..., 5] = ((torch.gather(P, 0, end + 1) - P[:T]) / 100.0).float()
    M[..., 3] = vis[:T] & (t0 + Wd <= T)
    # (d) when the big items return (the simulator gives 40 for an item the map has not)
    for k_, nm_ in enumerate(("mega_s", "red_s")):
        Y[..., 6 + k_] = S[..., ix[nm_]] / 40.0
        M[..., 4 + k_] = S[..., ix[nm_]] < 39.99
    return Y, M, C


def aux_guess(A, dn, ix, window):
    """(--aux-heads target, strength, first; 2026-10-12) the labels of three more questions of the --aux lesson, from the
    simulator's five last columns of info["aux"] (en_target, en_band, en_weapon, mega_take, red_take).
      A, dn, ix   as aux_labels takes them: A [T+1, n, columns], row t the game as it stood BEFORE step t and, in its event
                  columns (the takes), what happened in step t-1: step t's are in row t+1; dn [T, n] his round ended in step t
      window      (first) frames
    ->  K [T, n, 5] int64:  the classes: what the enemy goes for (a number of the simulator's INTENTS); his stack's band (0 to
                            3); the weapon in his hand (a number of WEAPONS); who takes the mega next, who the red armor
                            (0 nobody within the window, 1 he, 2 another player of his match: in a pair the enemy)
        M [T, n, 6] bool:   the label is there: target, band, weapon, the mega's taker, the red armor's taker; the sixth is
                            the target's on the frames the enemy is not in view (for the record only)
    Where the labels are:
      target    there is an enemy alive (en_alive: a round with other players) and the simulator has a target to name for
                him (en_target is not -1: a network's seat, a scripted item runner), in view or not
      band      there is an enemy alive, in view or not
      weapon    there is an enemy alive and he is not in view (in view it is an input already)
      first     the map has the item (lying there or away), there is an enemy alive, and the whole window lies inside the
                rollout (a frame whose window runs past the rollout's end has no label: the fight's rule). The class is by
                the item's first take in the steps t to t+window-1; a step in which his round ends is the last that counts
                for the frames before it (the take of that same step counts). His death does not end it: who takes the
                item next is a fact of the same game.
    Whole tensors over the players and the frames; no loop over either."""
    import torch
    T, n = A.shape[0] - 1, A.shape[1]
    W = int(window)
    dev_ = A.device
    S, E = A[:T], A[1:]                                      # the game before step t; what happened in step t
    BIG = 1 << 30
    t0 = torch.arange(T, device=dev_)[:, None]

    def nxt(flag):                                           # for every row, the first row at or after it where flag holds (BIG: none)
        c_ = torch.where(flag, t0.expand(flag.shape), torch.full(flag.shape, BIG, dtype=torch.long, device=dev_))
        return torch.flip(torch.cummin(torch.flip(c_, (0,)), 0).values, (0,))

    alive = S[..., ix["en_alive"]] > 0.5
    seen = S[..., ix["en_in_view"]] > 0.5
    K = torch.zeros(T, n, 5, dtype=torch.long, device=dev_)
    M = torch.zeros(T, n, 6, dtype=torch.bool, device=dev_)
    tg = S[..., ix["en_target"]].round().long()
    K[..., 0] = tg.clamp(min=0)
    M[..., 0] = alive & (tg >= 0)
    M[..., 5] = M[..., 0] & ~seen
    K[..., 1] = S[..., ix["en_band"]].round().long().clamp(0, 3)
    M[..., 1] = alive
    K[..., 2] = S[..., ix["en_weapon"]].round().long().clamp(min=0)
    M[..., 2] = alive & ~seen
    lim = torch.minimum(t0 + (W - 1), nxt(dn > 0.5))         # the last step that counts: the window's, or the one that ends his round
    for k_, (it_, tk_) in enumerate((("mega_s", "mega_take"), ("red_s", "red_take"))):
        who = E[..., ix[tk_]].round().long()                 # in step t: 0 nobody, 1 he, 2 another player took it
        nt = nxt(who > 0)
        K[..., 3 + k_] = torch.where(nt <= lim, torch.gather(who, 0, nt.clamp(max=T - 1)), torch.zeros_like(who))
        M[..., 3 + k_] = (S[..., ix[it_]] < 39.99) & alive & (t0 + W <= T)
    return K, M


def aux_near(A, dn, ix, window):
    """(--aux-heads near; 2026-10-12) near which landmark the enemy is, now and `window` frames on, from the simulator's column
    en_near of info["aux"] (a number of INTENTS; -1: nothing to say).
      A, dn, ix   as aux_labels takes them: A [T+1, n, columns], row t the game as it stood BEFORE step t; dn [T, n] his round
                  ended in step t
    ->  K [T, n, 2] int64:  the landmark nearest the enemy at frame t; at frame t+window
        M [T, n, 4] bool:   the label is there: now; later; and the same two on the frames the enemy is not in view at frame t
                            (for the record only)
    Where the labels are:
      now      there is an enemy alive (en_alive) and the simulator names a landmark (en_near is not -1)
      later    the same at frame t, the frame t+window lies inside the rollout (a frame whose window runs past the rollout's
               end has no label), the simulator names a landmark there, and his round does not end in the steps t to
               t+window-1 (the enemy of another round is nowhere for this one). His death, or the enemy's, does not end it:
               where the enemy is then is a fact of the same game.
    Whole tensors over the players and the frames; no loop over either."""
    import torch
    T, n = A.shape[0] - 1, A.shape[1]
    W = max(1, int(window))
    dev_ = A.device
    S = A[:T]
    BIG = 1 << 30
    t0 = torch.arange(T, device=dev_)[:, None]
    c_ = torch.where(dn > 0.5, t0.expand(dn.shape), torch.full(dn.shape, BIG, dtype=torch.long, device=dev_))
    ne = torch.flip(torch.cummin(torch.flip(c_, (0,)), 0).values, (0,))      # the first step at or after t that ends his round (BIG: none)
    alive = S[..., ix["en_alive"]] > 0.5
    seen = S[..., ix["en_in_view"]] > 0.5
    nr = A[..., ix["en_near"]].round().long()                # [T+1, n]
    lt = nr[(t0[:, 0] + W).clamp(max=T)]                     # the same column `window` frames on (the last row where that is past the end)
    K = torch.zeros(T, n, 2, dtype=torch.long, device=dev_)
    M = torch.zeros(T, n, 4, dtype=torch.bool, device=dev_)
    K[..., 0] = nr[:T].clamp(min=0)
    M[..., 0] = alive & (nr[:T] >= 0)
    K[..., 1] = lt.clamp(min=0)
    M[..., 1] = alive & (lt >= 0) & (t0 + W <= T) & (ne >= t0 + W)
    M[..., 2] = M[..., 0] & ~seen
    M[..., 3] = M[..., 1] & ~seen
    return K, M


def aux_life(A, dn, ix, life0=None):
    """(--aux-fresh, --aux-tail; v0.2.2) the age of his life in frames on every row of a rollout's truth.
      A   [T+1, n, columns]: info["aux"] rows (row t: the game before step t; its `died` column: he died in step t-1)
      dn  [T, n]: his round ended in step t;  life0 [n]: the age on row 0 (the last row of the rollout before; None: 0)
    A life begins on the row after a death or a round's end. -> [T+1, n] int64"""
    import torch
    T, n = A.shape[0] - 1, A.shape[1]
    rs = torch.zeros(T + 1, n, dtype=torch.bool)
    rs[1:] = (A[1:, :, ix["died"]].float() > 0.5) | (dn > 0.5)
    tt = torch.arange(T + 1)[:, None].expand(T + 1, n)
    last = torch.cummax(torch.where(rs, tt, torch.full_like(tt, -1)), 0).values
    l0 = torch.zeros(n, dtype=torch.long) if life0 is None else life0.long()
    return torch.where(last >= 0, tt - last, l0[None, :] + tt)


AUX_BEL_AGE = 3000.0 / 400.0                                 # (the v0.2 input: min(belief age x 400, 3000) / 3000: ages up to 7.5 s)


def aux_known(bel, life, secs, dt=0.025):
    """(--aux-fresh) may `place` and `near` be asked on this frame: his life is `secs` old or older, or he has seen or heard
    the enemy since it began (his belief, as his inputs have it, is not older than his life).
      bel   [rows, n, 5]: his raw inputs "believes anything", the believed place (forward, left, up) / 1500, the belief's
            age (min(age x 400, 3000) / 3000; 1 also when nothing is believed);  life [rows, n] frames -> [rows, n] bool"""
    import torch
    ok = bel[..., 0] > 0.5
    ag = bel[..., 4]
    bt = torch.where(ok & (ag < 0.99999), ag * AUX_BEL_AGE, torch.full_like(ag, 99.0))
    ls = life.float() * dt
    return (ls >= secs) | (bt <= ls + 1e-3)


def aux2_labels(A, dn, bel, ix, fr, fw, nw, guess, near, fresh, unseen, tw, tail=None, life0=None, chunk=4096):
    """(v0.2.2: --aux-tail, --aux-fresh, --aux-unseen) every label of the --aux lesson for one rollout, as aux_labels,
    aux_guess and aux_near make them, and then:
      tail   (--aux-tail) the rows of the rollout before's last `tw` frames are put in front (their truth `a`, `dn`), so
             that their windows run on into this rollout; a label there counts only where it was missing at the update
             before (its masks `m`, `km`, `nm`): the frames whose window ran past that rollout's end
      fresh  (--aux-fresh, seconds) `place` and `near` (all four of its masks) only where aux_known (his life's age by
             aux_life from `life0`; his belief from `bel`, [T+1, n, 5])
      unseen (--aux-unseen) `near` now and later only where the enemy is not in view at the frame (its masks 2 and 3)
      A [T+1, n, cols] (float16 as the trainer keeps it), dn [T, n]; fr, fw, nw the windows; guess / near: aux_guess /
      aux_near asked. -> dict: Y, M, C, K, KM, N, NM (the trainer's AUX_Y ... AUX_NM; None where not asked) over
      len(tail) + T rows; tw (the rows in front); life (the age on the last row, for the next rollout); tail (this
      rollout's last `tw` frames, for the next update; None when tw is 0); stats (numbers for the record)"""
    import torch
    T, n = A.shape[0] - 1, A.shape[1]
    assert 0 <= tw <= T, (tw, T)
    TW = 0 if tail is None else int(tail["a"].shape[0])
    Ae = A if not TW else torch.cat([tail["a"], A])
    De = dn if not TW else torch.cat([tail["dn"], dn])
    out = {k_: [] for k_ in ("Y", "M", "C", "K", "KM", "N", "NM")}
    for c0_ in range(0, n, chunk):
        a_, d_ = Ae[:, c0_:c0_ + chunk].float(), De[:, c0_:c0_ + chunk]
        y_, m_, c_ = aux_labels(a_, d_, ix, fr)
        out["Y"].append(y_.half())
        out["M"].append(m_)
        out["C"].append(c_.to(torch.uint8))
        if guess:
            k_, m_ = aux_guess(a_, d_, ix, fw)
            out["K"].append(k_.to(torch.uint8))
            out["KM"].append(m_)
        if near:
            k_, m_ = aux_near(a_, d_, ix, nw)
            out["N"].append(k_.to(torch.uint8))
            out["NM"].append(m_)
    R = {k_: (torch.cat(v_, 1) if v_ else None) for k_, v_ in out.items()}
    st = {}
    life = aux_life(A, dn, ix, life0)
    keep = None
    if fresh > 0:
        keep = aux_known(bel, life, fresh)
        kc = keep[:T]
        hid = (A[:T, :, ix["en_alive"]].float() > 0.5) & (A[:T, :, ix["en_in_view"]].float() <= 0.5)
        cut = hid & ~kc
        st["fresh_cut"] = round(float(cut.sum()) / max(1.0, float(hid.sum())), 4)      # of the frames `place` would be asked on
        st["fresh_cut_old_belief"] = round(float((cut & (bel[:T, :, 0] > 0.5)).sum()) / max(1.0, float(cut.sum())), 4)    # ... of those, with a belief from before his life
        kx = kc if not TW else torch.cat([tail["keep"], kc])
        R["M"][..., 0] &= kx
        if R["NM"] is not None:
            R["NM"] &= kx[..., None]
    if unseen and R["NM"] is not None:
        R["NM"][..., 0] = R["NM"][..., 2].clone()
        R["NM"][..., 1] = R["NM"][..., 3].clone()
    if TW:
        add_ = {}
        for q_, k_ in (("M", "m"), ("KM", "km"), ("NM", "nm")):
            if R[q_] is not None:
                R[q_][:TW] &= ~tail[k_]
                add_[q_] = [round(float(x_) / max(1.0, float(y_)), 4) for x_, y_ in zip(R[q_][:TW].sum((0, 1)).tolist(), R[q_][TW:].sum((0, 1)).tolist())]
        st["tail_added"] = add_                              # per mask: the labels the tail adds / the labels of this rollout's own frames
    R["tw"], R["life"], R["stats"], R["tail"] = TW, life[T].clone(), st, None
    if tw > 0:
        s_ = slice(TW + T - tw, TW + T)
        R["tail"] = dict(a=A[T - tw:T].clone(), dn=dn[T - tw:].clone(), keep=None if keep is None else keep[T - tw:T].clone(),
                         m=R["M"][s_].clone(), km=None if R["KM"] is None else R["KM"][s_].clone(), nm=None if R["NM"] is None else R["NM"][s_].clone())
    return R


def way_measure(store, keep=50, least=30, same=200.0):
    """(WAYS) how predictable his ways are, counted as tools/pro_yardsticks.py counts the pros' (way_labels: 43% for them,
    57% for v0.1 on recorded games): of his trips between the same two places, the share on the commonest way.
      store  {map: {(from, to): [a trip's path as 48 numbers, 16 points along it; the newest last]}}
    For every pair with `least` trips or more, its newest `keep`: a trip joins the way whose first trip lies nearest,
    within `same` units on average along the path, else it opens a new way; then every trip goes to the nearest way once
    more; the pair's number is the share of its trips on the way with the most. A map's number is the mean of its
    pairs'. The number of ways found grows with the number of trips, so the count is always over the same number.
    -> {map: {"commonest": per cent, "pairs": n, "trips": n}}"""
    out = {}
    for mp_ in sorted(store):
        sh, nt = [], 0
        for key in sorted(store[mp_]):
            tr = store[mp_][key][-keep:]
            if len(tr) < least:
                continue
            P = np.asarray(tr, np.float64).reshape(len(tr), -1, 3)
            lead = [0]
            for i in range(1, len(P)):
                if np.linalg.norm(P[lead] - P[i], axis=2).mean(1).min() > same:
                    lead.append(i)
            lab = np.linalg.norm(P[:, None] - P[lead][None], axis=3).mean(2).argmin(1)
            sh.append(float(np.bincount(lab).max()) / len(P))
            nt += len(P)
        if sh:
            out[mp_] = dict(commonest=round(100.0 * float(np.mean(sh)), 1), pairs=len(sh), trips=nt)
    return out


def gru_layout(done_h, dev):
    """(--learn-nosync) gru_seq's cut of the stretches worked out on the host from the done flags done_h [T, B] (a CPU
    tensor): the same integers gru_seq works out on the card, sent over without waiting for it -> dict(reset, S, L, flat,
    nz, h0rows) (flat, nz, h0rows on dev)"""
    import torch
    T, B = done_h.shape
    dn = done_h > 0.5
    st = torch.ones(T, B, dtype=torch.bool)
    st[1:] = dn[:-1]
    if not bool(st[1:].any()):
        return dict(reset=False)
    stb = st.t().reshape(-1)
    sid = torch.cumsum(stb.long(), 0) - 1
    S = int(sid[-1]) + 1
    idx = torch.arange(B * T)
    first = idx[stb]
    pos = idx - first[sid]
    L = int(pos.max()) + 1
    flat = pos * S + sid
    from0 = (first % T) == 0
    nz = torch.nonzero(from0).squeeze(1)
    h0rows = first[from0] // T
    pin = dev.type == "cuda"

    def up(x):
        return (x.pin_memory() if pin else x).to(dev, non_blocking=pin)
    return dict(reset=True, S=S, L=L, flat=up(flat), nz=up(nz), h0rows=up(h0rows))


def gru_seq(cell, e, h0, done, lay=None):
    """(--fast-gru, B-237) his memory over whole sequences by the library's GRU (cuDNN on the card), the same numbers as
    stepping the GRUCell frame by frame with the memory reset after every frame whose done flag is set:
        h_t = cell(e_t, h_{t-1} * (1 - done_{t-1})),  h_{-1} = h0
      cell  the trainer's nn.GRUCell (its four weights are used as they are: the gradient reaches them)
      e     [T, B, In] the encoder's output (with the attention part's added)
      h0    [B, H] the memory each player starts the rollout with
      done  [T, B] 1 where the memory is reset after that frame (death, round restart)
    -> [T, B, H] the memory after each frame (before its reset), as the frame-by-frame loop's.
    Each player's frames are cut into stretches at his resets; a stretch starts from h0 (the rollout's first) or from
    zeros (after a reset), so the cut is exact. The stretches are laid side by side, padded at their ends to the
    longest; a GRU only looks back, so the padding changes nothing that is read out (and gets no gradient).
      lay   (--learn-nosync) gru_layout()'s cut of these players, made on the host: the same integers, no waits for the card"""
    import torch
    T, B = done.shape
    w = [cell.weight_ih, cell.weight_hh, cell.bias_ih, cell.bias_hh]
    if lay is not None:
        if not lay["reset"]:
            return torch._VF.gru(e, h0[None].contiguous(), w, True, 1, 0.0, cell.training, False, False)[0]
        S, L, flat = lay["S"], lay["L"], lay["flat"]
        ef = e.transpose(0, 1).reshape(B * T, e.shape[-1])
        P = ef.new_zeros(L * S, e.shape[-1]).index_copy(0, flat, ef).view(L, S, e.shape[-1])
        hi = h0.new_zeros(S, h0.shape[-1]).index_copy(0, lay["nz"], h0[lay["h0rows"]])
        out = torch._VF.gru(P, hi[None], w, True, 1, 0.0, cell.training, False, False)[0]
        return out.reshape(L * S, -1).index_select(0, flat).view(B, T, -1).transpose(0, 1).contiguous()
    dn = done.detach() > 0.5
    st = torch.ones(T, B, dtype=torch.bool, device=e.device)       # a stretch starts here: the first frame, or after a reset
    st[1:] = dn[:-1]
    if not bool(st[1:].any()):                                     # no reset inside: the whole sequences in one go
        return torch._VF.gru(e, h0[None].contiguous(), w, True, 1, 0.0, cell.training, False, False)[0]
    stb = st.t().reshape(-1)                                       # player by player, frame by frame
    sid = torch.cumsum(stb.long(), 0) - 1                          # each frame's stretch
    S = int(sid[-1]) + 1
    idx = torch.arange(B * T, device=e.device)
    first = idx[stb]                                               # each stretch's first frame
    pos = idx - first[sid]                                         # a frame's place in its stretch
    L = int(pos.max()) + 1
    flat = pos * S + sid                                           # its row in the stretches laid side by side
    ef = e.transpose(0, 1).reshape(B * T, e.shape[-1])
    P = ef.new_zeros(L * S, e.shape[-1]).index_copy(0, flat, ef).view(L, S, e.shape[-1])
    from0 = (first % T) == 0                                       # the stretches that start the rollout carry h0, the rest zeros
    hi = h0.new_zeros(S, h0.shape[-1]).index_copy(0, torch.nonzero(from0).squeeze(1), h0[first[from0] // T])
    out = torch._VF.gru(P, hi[None], w, True, 1, 0.0, cell.training, False, False)[0]
    return out.reshape(L * S, -1).index_select(0, flat).view(B, T, -1).transpose(0, 1).contiguous()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--slow-mem", type=int, default=0,
                    help="(v0.3 candidate, 2026-10-14; sim/slowmem.py) 1: give him the slow memory: a second GRU (--slow-size) that ticks every "
                         "--slow-every frames on his fast memory and the encoder's mean, read by every output through a door that starts at "
                         "zero, taught over the last --slow-ring ticks (minutes) from a ring of its stored inputs. A network that has the part "
                         "keeps it whatever this says; 0 and a network without it: the trainer as before")
    ap.add_argument("--slow-size", type=int, default=256, help="(--slow-mem) the slow GRU's width (a new part only)")
    ap.add_argument("--slow-in", type=int, default=128, help="(--slow-mem) the width of its input squeeze (a new part only)")
    ap.add_argument("--slow-every", type=int, default=48, help="(--slow-mem) frames from tick to tick (a new part only; --steps must be a "
                    "whole number of ticks: 48 = 1.2 s, 8 ticks a rollout of 384)")
    ap.add_argument("--slow-ring", type=int, default=-1, help="(--slow-mem) ticks before the rollout the gradient reaches (320 x 1.2 s = 6.4 min; "
                    "-1: the network's own or 320; 0: no ring, the slow state carried as the fast one is)")
    ap.add_argument("--head", default="",
                    help="(v0.4, docs/v0.4/BUILD_v0.4.md; sim/head.py) give him the head: a layout as JSON text or a JSON file of "
                         "head.layout()'s arguments, or 'default'. A slow GRU that ticks every 8 frames on his fast memory, the encoder's "
                         "mean, a read of its store of three minutes and the simulator's events; its plan enters his fast GRU through "
                         "head.plan_in and its target and way are added to his intention's and his way's logits, all at zero to begin "
                         "with. A network that has the part keeps it (and its layout) whatever this says; '' and a network without it: "
                         "the trainer as before")
    ap.add_argument("--attn-mem-query", type=int, default=0,
                    help="(v0.4, the proposal's change 4; sim/attn.py \"mem\") 1: the attention part's second block takes its query also "
                         "from his memory of the frame before (h_{t-1}, read at half precision) through a layer at zero added to the "
                         "query: he answers exactly as before. The learning step reads h_{t-1} as he played it (kept on the host at half "
                         "precision, players x steps x 512 x 2 bytes): no gradient from the query into his memory. A network whose "
                         "layout has it keeps it whatever this says")
    ap.add_argument("--ordered-heads", type=int, default=0,
                    help="(v0.4, the proposal's change 7) 1: his choices are drawn in order: the intention (his target) first, then his "
                         "way, then the switch to his legs, then the weapon key, each with the choice drawn before it through a table of "
                         "its own (a row a choice before, at zero: he answers exactly as before) added to its logits. The checkpoint "
                         "keeps the order (\"ordered\") and the tables (order.*); a network that has them keeps them")
    ap.add_argument("--head-store-half", type=int, default=0,
                    help="(--head) 1: the head's store kept at half precision on the card (each slot rounded to float16 as it is written, in "
                         "play, in the learning step and on the servers alike: the layout's store_half), half its memory")
    ap.add_argument("--head-lr-scale", type=float, default=0.25, help="(--head) the head's learning rate as a share of the rest's (its own "
                                                                      "optimiser group; plan_in is the head's)")
    ap.add_argument("--head-v", type=float, default=0.5, help="(--head) the weight of the head's two values (on its ticks: v_short against "
                                                              "his returns, v_long against the long count's at --long-gamma)")
    ap.add_argument("--head-win", type=float, default=0.1, help="(--head) the weight of the win head's lesson: the band of his final score "
                                                                "margin, from info['aux'] win_game / win_band (HEAD_EVENTS=1; BUILD_v0.4.md "
                                                                "3a): a game that ends in the rollout gives its ticks the true band, one that "
                                                                "goes on its forecast at its last tick in the rollout (a value at gamma 1)")
    ap.add_argument("--head-win-true", type=float, default=1.0, help="(--head) ... the weight of a tick with the true band beside one with a "
                                                                     "forecast for its target")
    # v0.4.3 (docs/v0.4.3/RUN_v0.4.3.md, "The strategy head"; sim/head2.py): a small slow GRU ticking with the brain; a plan into
    # his fast GRU's input and a bias on his intention's logits, both at zero to begin with; it learns from its own two-minute value
    ap.add_argument("--head2", type=int, default=0, help="v0.4.3: 1 = the strategy head (sim/head2.py; a network without one gets one that answers "
                                                         "exactly as before). A network that has one keeps it whatever this says; 0 and a network without: as before")
    ap.add_argument("--head2-size", type=int, default=256, help="(--head2, a new head) its GRU's width")
    ap.add_argument("--head2-inp", type=int, default=256, help="(--head2, a new head) the squeeze of its inputs before the GRU")
    ap.add_argument("--head2-plan", type=int, default=64, help="(--head2, a new head) the plan's width")
    ap.add_argument("--head2-ctrl", type=int, default=4, help="(--head2, a new head) the slot for the 'in control' readout (B-280; zeros without one)")
    ap.add_argument("--head2-ctrl-src", default="", help="(--head2) what the ctrl slot reads: none (zeros), belief or both (the 'in control' "
                                                        "readout of that name, --control-src; its chances - 0.5, detached). Empty: the network's "
                                                        "head's own (none for a new head); a value is written into the head's layout")
    ap.add_argument("--head2-off", default="", help="(--head2, a new head) parts of its input left out (zeros), e.g. 'hands,ctrl' "
                                                    "(of brain, trk, trz, ahead, ctrl, obs, hands)")
    ap.add_argument("--head2-gamma", type=float, default=0.9998, help="(--head2, a new head) its value's and advantage's discount (0.9998: about two minutes)")
    ap.add_argument("--head2-lr-scale", type=float, default=1.0, help="(--head2) its learning rate as a share of --lr (its own group; plan_in is in it)")
    ap.add_argument("--head2-pg", type=float, default=1.0, help="(--head2) the weight of its own policy-gradient term (the bias on his intention, "
                                                                 "its own advantage; live: H2_PG, a factor on it)")
    ap.add_argument("--head2-v", type=float, default=0.5, help="(--head2) the weight of its value's lesson")
    ap.add_argument("--head2-plan-grad", type=float, default=0.0, help="(--head2) the share of the hands' gradient that goes on into the head through the "
                                                                       "plan (0: plan_in learns from the hands' loss, the head only from its own lessons; live: H2_PLAN_GRAD)")
    ap.add_argument("--head2-delay", type=float, default=0.0, help="(--head2) minutes after --head2-start before its gate begins to open")
    ap.add_argument("--head2-open", type=float, default=0.0, help="(--head2) minutes for its gate from 0 to 1 (0: held where it is; live: H2_GATE_OPEN)")
    ap.add_argument("--head2-cap", type=float, default=1.0, help="(--head2) its gate is never above this (live: H2_GATE_CAP; 0 shuts it at once)")
    ap.add_argument("--head2-start", type=float, default=-1.0, help="(--head2) the minute the delay counts from (-1: this process's start; pass it on every resume)")
    ap.add_argument("--head2-gate", type=float, default=-1.0, help="(--head2) the gate to start this process at (-1: the network's own, 0 for a new head)")
    ap.add_argument("--run", default="duel_gru_v1")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--matches", type=int, default=128, help="matches per worker (2 players each)")
    ap.add_argument("--steps", type=int, default=128, help="rollout length = training sequence length")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--lr", type=float, default=2.5e-4)
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--loadout", default="all")
    ap.add_argument("--item-reward", type=float, default=0.3, help="reward per 100 points of health/armor picked up")
    ap.add_argument("--item-loss", type=float, default=0.5, help="an enemy's mega or red armor costs this share of its pickup reward")
    ap.add_argument("--intent-seek", type=float, default=1.0, help="the chosen way pays this share of the item's pickup reward, spread along it")
    ap.add_argument("--lr-minutes", type=float, default=0.0, help="the learning rate decays to a tenth over this many minutes of training "
                    "in all (counted across restarts); 0 = over this run's --minutes, from the full rate again at every restart")
    ap.add_argument("--lr-end", type=float, default=0.1, help="the learning rate ends at this share of --lr (1 = constant). Note: with "
                    "--lr-minutes on a resumed run the decay counts the minutes of the whole lineage, so a long lineage sits at "
                    "this share from its first update (v8 to v12 did, at a tenth); --lr-minutes 0 decays over this run only")
    ap.add_argument("--lam", type=float, default=0.95, help="how far ahead an action gets credit in the advantage estimate: "
                    "0.95 at 40 decisions a second is about half a second, 0.98 about 1.2 s, 0.99 about 2.3 s")
    ap.add_argument("--close-floor", type=float, default=0.2, help="the share of respawns put 300 to 700 units in front of an "
                    "enemy once the near-spawn curriculum has run out (0 = none: every respawn at a spawn point)")
    ap.add_argument("--teach-trunk-move", type=float, default=-1.0, help="the same share for the movement teacher alone (keys, jump "
                    "and view in movement rounds and item runs); below 0: as --teach-trunk. Through the output layer alone "
                    "(0.05) the strafe-jumping teacher taught nothing and cost a third of his hit rate in 90 minutes "
                    "(2026-10-09, duel_gru_v14_try1); into the shared layers it had taught strafe jumping in 21 minutes "
                    "that morning (move_trial_a)")
    ap.add_argument("--teach-trunk", type=float, default=1.0, help="the teachers' losses (walking keys, weapon, intention) reach the "
                    "shared layers at this share of their weight; the output layer learns the labels in full. 1 = as before. A "
                    "teacher with new labels otherwise moves the whole network (RESULTS 2026-10-08 18:45)")
    ap.add_argument("--kl-heads", type=int, default=0, help="N = the policy's step per output head in the metrics of every N-th "
                    "update and of the first twenty (kl_heads; one more forward pass over the batch in those updates)")
    ap.add_argument("--lr-warm", type=float, default=0.0, help="the learning rate climbs from a tenth to full over this many minutes "
                    "from the teachers' start (--fade-start): new losses and labels move the network a long way in the first updates")
    ap.add_argument("--fade-start", type=float, default=-1.0, help="the teachers' fades count from this minute of training "
                    "(default: where this process starts; on a restart pass the first start's, so that the fades go on)")
    ap.add_argument("--intent-seek-minutes", type=float, default=0.0, help="that reward fades to a quarter over this time (0 = constant)")
    ap.add_argument("--stack-p", type=float, default=0.0, help="share of spawns with a random stack (health 100-200, armor 0-150)")
    ap.add_argument("--intent-teach", type=float, default=0.0, help="weight of imitating the simple item rule on the intention head (env.intent_rule)")
    ap.add_argument("--intent-teach-minutes", type=float, default=240.0, help="that weight fades to zero over this time")
    ap.add_argument("--intent-teach-floor", type=float, default=0.0, help="the item rule's weight never fades below this (0: to zero)")
    ap.add_argument("--weapon-teach", type=float, default=0.0, help="weight of imitating the weapon rule on the weapon key (env._weapon_teach)")
    ap.add_argument("--weapon-teach-minutes", type=float, default=240.0, help="that weight fades to zero over this time")
    ap.add_argument("--hand-teach", type=float, default=0.0,
                    help="the pros' weapon in hand with nobody in view, as a standing pull (0 = off): on the frames the simulator gives a "
                         "label (HAND_TEACH=1: the pros' shares of the weapons he owns, for his map, travelling or holding, by how long "
                         "ago an enemy was in view) and his hand reads the weapon key, cross-entropy of his weapon output against that "
                         "distribution. Not paid; no fade-out")
    ap.add_argument("--hand-teach-trunk", type=float, default=0.05, help="... the share of that lesson's gradient that reaches the shared "
                                                                         "layers (as --teach-trunk); the weapon output's layer learns it in full")
    ap.add_argument("--hand-teach-warm", type=float, default=0.0, help="... minutes over which its weight rises from nothing, counted from "
                                                                       "--fade-start")
    ap.add_argument("--rj-teach", type=float, default=0.0,
                    help="(RJ_TEACH=1, the owner 2026-10-23) the rocket jump's moment as a lesson (0 = off): on the frames the simulator "
                         "labels (a rocket jump practice try, on the floor at the take-off, the launcher ready, his view 60 degrees or more "
                         "down) his vertical key toward 'jump' on the frames its jump is read and his trigger toward 'fire'; nothing else. "
                         "Not paid. Live: RJ_TEACH_W in live.json is this weight")
    ap.add_argument("--rj-teach-trunk", type=float, default=0.05, help="... the share of that lesson's gradient that reaches the shared "
                                                                       "layers (as --teach-trunk); the two outputs' rows learn it in full")
    ap.add_argument("--rj-teach-warm", type=float, default=120.0, help="... minutes over which its weight rises from nothing, from --rj-teach-start")
    ap.add_argument("--rj-teach-start", type=float, default=-1.0, help="... the minute the warm-up counts from (-1: the first update of this "
                                                                       "process with the weight above 0: a live opening starts weak)")
    ap.add_argument("--rj-teach-done", type=float, default=0.25, help="... it fades out as he makes the jump: the weight is zero when his share of "
                                                                      "tries that arrive (the last --rj-teach-window tries) is this or more")
    ap.add_argument("--rj-teach-band", type=float, default=0.10, help="... and full at --rj-teach-done less this (linear between); 0: no fade")
    ap.add_argument("--rj-teach-window", type=int, default=100, help="... the tries the share is taken over (none: full weight until 40 tries)")
    ap.add_argument("--rj-copy", type=float, default=0.0,
                    help="(RJ_COPY=1, the owner 2026-10-23, 'option 1') the whole route of a rocket jump practice try as a lesson (0 = off): "
                         "on every frame the simulator labels (from the try's start to its landing, the scripted runner's choice for his "
                         "state) his forward, side and vertical keys, view turn and pitch, trigger, weapon key, walk and zoom toward the "
                         "label, each output on the frames its choice counts (the keys on his hand's readings, the jump bit on every frame). "
                         "Not paid. Live: RJ_COPY_W in live.json is this weight")
    ap.add_argument("--rj-copy-trunk", type=float, default=0.05, help="... the share of that lesson's gradient that reaches the shared "
                                                                      "layers (as --teach-trunk); the outputs' rows learn it in full")
    ap.add_argument("--rj-copy-warm", type=float, default=120.0, help="... minutes over which its weight rises from nothing, from --rj-copy-start")
    ap.add_argument("--rj-copy-start", type=float, default=-1.0, help="... the minute the warm-up counts from (-1: the first update of this "
                                                                      "process with the weight above 0: a live opening starts weak)")
    ap.add_argument("--near-item-p", type=float, default=0.0, help="share of spawns within 2 s of the mega or the red armor")
    ap.add_argument("--close-minutes", type=float, default=90, help="near-spawn curriculum: 100%% -> 20%% over this time")
    ap.add_argument("--snapshot-min", type=float, default=20)
    ap.add_argument("--anchor-p", type=float, default=0.0,
                    help="the share of rollouts whose league players are an anchor's (snapshots/anchor_*.pt: networks that never "
                         "leave the league, e.g. the run's starting network) and not one of the last eight snapshots'")
    ap.add_argument("--drill-p", type=float, default=0.0,
                    help="share of rounds where both players have one weapon only")
    ap.add_argument("--drill-weapons", default="rl,rg,lg,rl,rg,lg,sg,gl,pg,hmg,mg", help="weapons used in drill rounds (equal chance)")
    ap.add_argument("--lab-p", default="0.29,0.71", help="test map: share of playing time in aim rooms / movement courses "
                    "/ arena fights (third value optional)")
    ap.add_argument("--loadout-p", default="", help="normal rounds, share by spawn: random 1-2 weapons, real duel spawn "
                    "(machine gun and gauntlet), every weapon on the map, the same single weapon for both")
    ap.add_argument("--ent-heads", default="", help="weight of the exploration bonus per action head (forward, strafe, "
                    "vertical, turn, pitch, fire, weapon, walk, zoom); empty = 1 for all")
    ap.add_argument("--ent-coef", type=float, default=0.01, help="exploration bonus (entropy coefficient)")
    ap.add_argument("--item-floor", type=float, default=0.02,
                    help="(2026-10-25, owner: keep trying every item) the floor on his item intentions: on every map, the mean "
                         "probability of each big item the map has (MH, RA, YA, YA2, RL, RG, LG) over the frames his intention is "
                         "read (his own seats) should not fall below it (live ITEM_FLOOR)")
    ap.add_argument("--item-floor-w", type=float, default=0.0,
                    help="the floor's weight: loss += w * sum over (map, item) of relu(log floor - log mean p), per learning piece "
                         "(live ITEM_FLOOR_W; 0: no term, the trainer as before; the means are logged whatever the weight)")
    ap.add_argument("--arena-len", type=float, default=30.0, help="test map: seconds per arena round")
    ap.add_argument("--obs-dump", default="", help="write a sample of raw inputs (0.5%% of the rows of the updates --obs-dump-from..to) to this "
                    "file, for sim/renorm_policy.py --sample")
    ap.add_argument("--obs-dump-from", type=int, default=8)
    ap.add_argument("--obs-dump-to", type=int, default=20)
    ap.add_argument("--arena-full", type=float, default=0.5, help="test map: share of arena rounds with the full weapon set")
    ap.add_argument("--dmg-reward", type=float, default=0.0, help="reward per point of damage (0 = the old curriculum value, 0.001 by now)")
    ap.add_argument("--dmg-taken-w", type=float, default=2.0, help="weight of damage taken against damage dealt in the reward")
    ap.add_argument("--no-walk", action="store_true", help="the walk key does nothing")
    ap.add_argument("--lab-gun", type=float, default=0.0, help="test map: chance that a course round is run-and-gun "
                    "(a weapon, a target ahead beside the path, damage paid by the runner's speed)")
    ap.add_argument("--lab-items", type=float, default=0.0, help="test map: chance that a course round is the items room")
    ap.add_argument("--lab-courses", default="speed,slalom,ramps",
                    help="movement courses of the test map (testlab) used when that map is in --map")
    ap.add_argument("--minibatches", type=int, default=8,
                    help="players are split into this many groups per training pass (more = less GPU memory)")
    ap.add_argument("--long-gamma", type=float, default=0.0,
                    help="v0.2: the pay for items and stack (the simulator's r_long) is also counted this far ahead (0.9998 = about "
                         "two minutes); 0 = off. Two more value outputs estimate that pay at --gamma and at this; his credit is "
                         "today's plus a share of their difference")
    ap.add_argument("--long-ramp", type=float, default=60.0, help="... the share rises from nothing to all of it over this many minutes "
                                                                 "from the start (--fade-start), while the two new outputs learn")
    ap.add_argument("--long-cap", type=float, default=0.5, help="... and is cut when the long count would add more than this share of the size "
                                                                "of his credit of today (the mean of the absolute values)")
    ap.add_argument("--obs-half", action="store_true", help="v0.2: the rollout's stored inputs at half precision (they fill most of the card)")
    ap.add_argument("--fast-gru", type=int, default=0,
                    help="(B-237) 1: in the learning step his memory is worked out over whole sequences by the library's GRU "
                         "(gru_seq: cut at his resets, exact), not frame by frame in Python; the rollout is as before. 0 (default): as before")
    ap.add_argument("--overlap", type=int, default=0,
                    help="(B-266) 1: learn while the next games play: while update n learns, the simulators play rollout n+1 in a thread "
                         "of this process with a copy of the network as it was before update n's learning (one update stale; PPO's ratio "
                         "is taken against the log-probabilities of the copy that played, as always). The rollout's inputs are kept on the "
                         "host (players x steps x inputs) and go to the card a piece at a time. Not with --head, --slow-mem or the map "
                         "cells (v8). 0 (default): the trainer exactly as before")
    ap.add_argument("--overlap-switch-ms", type=float, default=0.2,
                    help="(--overlap) Python's thread switch interval in ms (sys.setswitchinterval; Python's own is 5): how long the "
                         "rollout's thread may wait for the interpreter while the learning step holds it")
    ap.add_argument("--overlap-kl-pieces", type=int, default=8,
                    help="(--overlap) pieces of players (every --minibatches-th player, spread over every simulator) on which the "
                         "staleness is measured before the learning step: overlap.kl_stale, the KL from the network that played to the "
                         "one that learns, its share of frames outside the clip, its value error. 0: not measured")
    ap.add_argument("--overlap-ppo", choices=("decoupled", "plain"), default="decoupled",
                    help="(--overlap) decoupled (default): decoupled PPO (Hilton et al. 2021): before the learning step the learner's own "
                         "network (the proximal one: pol before this update) gives its log-probabilities and values on the whole batch; "
                         "the clip is taken around it (ratio pi / pi_prox) and the loss weighted by pi_prox / pi_played (capped at "
                         "--overlap-is-cap); the advantages' baseline and the value targets are its values (--overlap-prox-values). "
                         "plain: the ratio against the network that played, as first built (its clip, around a network one update "
                         "old, pulls the learner back towards it: the GPU dry run of 2026-10-18)")
    ap.add_argument("--step-kl-pieces", type=int, default=0,
                    help="(without --overlap; a diagnostic) pieces of players (as --overlap-kl-pieces) on which the last update's step is "
                         "measured on this rollout's fresh frames: step_kl, the mean log p(now) - log p(before the last update) of what he "
                         "did (KL(now || before)); the counterpart of --overlap's kl_stale. 0 (default): not measured, nothing kept")
    ap.add_argument("--overlap-is-cap", type=float, default=2.0,
                    help="(--overlap-ppo decoupled) the cap on the weight pi_prox / pi_played (truncated importance weights)")
    ap.add_argument("--overlap-prox-values", type=int, default=1,
                    help="(--overlap-ppo decoupled) 1 (default): the advantages and value targets with the proximal network's values "
                         "(the last frame's bootstrap stays the played network's); 0: with the played network's values")
    ap.add_argument("--overlap-prox-merge", type=int, default=1,
                    help="(--overlap-ppo decoupled) the proximal pass in --minibatches / this many pieces (it keeps no graph, so a piece "
                         "can be larger; the pass's time goes with the number of pieces). 1 (default): the learning step's pieces")
    ap.add_argument("--overlap-priority", choices=("high", "equal"), default="high",
                    help="(--overlap) the rollout's stream on the card: high (above the learning step's, as first built) or equal")
    ap.add_argument("--learn-nosync", type=int, default=0,
                    help="(2026-10-19) 1: the learning step without its waits for the card, the same numbers (bit for bit on the CPU): "
                         "Adam's step counts kept on the host (opt.pt loaded onto the card put them there: two waits a parameter "
                         "every step), torch.distributions' argument checks off (a wait a distribution and a log-probability), each "
                         "piece's players' indices taken to the host once an epoch, the host buffers' pieces sent from pinned memory "
                         "without waiting, the fast GRU's cut and the advantages' frames worked out on the host, the counters summed "
                         "on the card and read once an update, the teachers' distributions made only for the outputs they read. "
                         "0 (default): as before")
    ap.add_argument("--adam-fused", type=int, default=0,
                    help="(2026-10-19) 1: torch's fused Adam (one kernel a group, its step counts on the card as the fused kernel "
                         "wants them): rounding differs from the default (foreach) Adam's, so not the same numbers; for an A/B. "
                         "opt.pt carries over both ways. 0 (default): as before")
    ap.add_argument("--aux", type=float, default=0.0,
                    help="stage B, part 1: the weight of the things he is asked to foretell from his memory (0 = off). Four small output "
                         "layers on his memory: where the unseen enemy is, where he next appears, how the fight ends, when the big items "
                         "return; labels by hindsight inside the rollout from the simulator's info['aux']. Never an input, never paid")
    ap.add_argument("--aux-heads", default="place,appear,fight,items",
                    help="... which are in the lesson: the four, and (2026-10-12; only when named) target = what the enemy goes for (his "
                         "intention, a class), strength = his stack's band and the weapon in his hand (two classes), first = who takes the "
                         "mega and who the red armor at its next pickup (he, another player, nobody within --aux-first-frames)")
    ap.add_argument("--aux-first-frames", type=int, default=400,
                    help="... (first) the window in frames (400 = 10 s). Only a frame whose whole window lies in the rollout is labelled, "
                         "so it is cut to three quarters of the rollout as the fight's: at 384 steps 400 becomes 288")
    ap.add_argument("--aux-near-frames", type=int, default=120,
                    help="... (--aux-heads near: near which landmark the enemy is, now and later; a landmark is an item or a holding place "
                         "of the intention list) how many frames on 'later' is (120 = 3 s); cut to three quarters of the rollout")
    ap.add_argument("--aux-trunk", type=float, default=1.0, help="... the share of the lesson's gradient that reaches the shared layers (his "
                                                                 "memory and what feeds it); the four output layers learn in full. 0 = "
                                                                 "they only read his memory (a measure of what it holds)")
    ap.add_argument("--aux-frames", default="200,400,200", help="... the windows in frames: the enemy appears within, the fight ends within, "
                                                                "the damage counted over. Only a frame whose whole window lies in the "
                                                                "rollout is labelled for the last two, so they are cut to three quarters "
                                                                "of the rollout (--steps): at 384 steps 400 becomes 288, and the first "
                                                                "96 frames of a rollout carry the fight's label")
    ap.add_argument("--aux-warm", type=float, default=0.0, help="... minutes over which the weight rises from nothing, from --fade-start")
    ap.add_argument("--aux-tail", action="store_true",
                    help="v0.2.2 (F4): every question is labelled over its whole window: the last frames of a rollout, whose window runs past its "
                         "end, are labelled at the next update with the next rollout's truth, on the memory he played them with (kept on the "
                         "CPU at half precision: players x the longest window asked x 512 x 2 bytes); they teach the questions' layers only")
    ap.add_argument("--aux-fresh", type=float, default=0.0,
                    help="v0.2.2 (F5): place and near are not asked on the frames where his life is younger than this many seconds and he "
                         "has had no sighting or sound of the enemy since it began (by his own belief inputs; at most 7.5). 0 = off")
    ap.add_argument("--aux-unseen", action="store_true", help="v0.2.2: near (now and later) is asked only while the enemy is out of his sight, as place is")
    ap.add_argument("--aux-measure", action="store_true",
                    help="v0.2.2: the record's aux.v022.memory_vs_belief: where his memory puts the unseen enemy against the place his belief "
                         "inputs give, on the same frames, by the belief's age")
    # v0.3.11 (docs/v0.3.11/INFO_PAY.md): his belief of the enemy read out of his memory (sim/track.py), taught, and paid for
    # being more right than the enemy's belief of him. Off (both 0, a network without track.* layers): the trainer as it was
    ap.add_argument("--track", type=float, default=0.0,
                    help="v0.3.11: the weight of the belief readout's lesson (the enemy's place with its spread, velocity, stack band, "
                         "weapon in hand, weapons owned: sim/track.py; the truth from info['aux'] with TRACK_TRUTH=1; never an input). 0 = off")
    ap.add_argument("--track-trunk", type=float, default=0.1, help="... the share of the lesson's gradient that reaches his memory and the "
                                                                    "layers below it (as --aux-trunk)")
    ap.add_argument("--track-parts", default="pos:1,vel:0.25,band:0.5,hand:0.25,own:0.25",
                    help="... the parts' weights, in the lesson and in the pay's score alike")
    ap.add_argument("--track-start", type=float, default=-1.0,
                    help="... the run's minute the readout's lesson began (its warm-up and the pay's delay count from it; -1: this process's start)")
    ap.add_argument("--track-warm", type=float, default=30.0, help="... minutes over which the lesson's weight rises from nothing")
    ap.add_argument("--track-lr-scale", type=float, default=1.0, help="... the readout's own layers learn at this many times --lr (a group of their own)")
    ap.add_argument("--info-pay", type=float, default=0.0,
                    help="v0.3.11: the zero-sum pay for knowing where the enemy is: every --info-every frames, k * (his readout's score - "
                         "the enemy's readout's score of him), both alive in a duel's game (a live name in live.json: INFO_PAY). 0 = off")
    ap.add_argument("--info-every", type=int, default=20, help="... frames between two scorings (20: 0.5 s)")
    ap.add_argument("--info-delay", type=float, default=60.0, help="... minutes after --track-start before the pay begins (the readout learns first)")
    ap.add_argument("--info-warm", type=float, default=60.0, help="... minutes over which the pay then rises to --info-pay")
    # v0.4.0 stage A (the owner, 2026-10-22: "these two need to be separate networks"): the enemy tracked by a memory of its own
    # (sim/belief.py); the readout reads it in place of his memory, its lesson reaches the belief and the readout only.
    # Off (0, a network without belief.* layers): the trainer as it was
    ap.add_argument("--belief", type=int, default=0,
                    help="v0.4.0: the belief memory's size (256): its own input layer on the normalised inputs, a GRU that ticks every "
                         "--belief-every frames on the mean and max of the frames since the last; the readout (--track) reads it. 0 = off "
                         "(a network that has one keeps it, with the size it has)")
    ap.add_argument("--belief-every", type=int, default=8, help="... frames between two ticks (8: 0.2 s); the readout is graded on the ticks")
    ap.add_argument("--belief-lr-scale", type=float, default=-1.0,
                    help="... the belief's own layers learn at this many times --lr (a group of their own, after the readout's); "
                         "-1: as --track-lr-scale")
    # v0.4.0 brain, the readout's second part (sim/track_z.py; the owner, 2026-10-23: "let's replace the 10+s range with the
    # distribution over locations"; 2026-10-22: speed and direction apart, over a short window): odds over the map's zones, the
    # enemy's speed and way over 0.2 s, read from the belief's state; a lesson only (TRACK_Z=1 gives its truth). Off: as before
    ap.add_argument("--track-z", default="", help="v0.4.0: the second part's lesson by part, e.g. zone:0.5,spd:0.25,dir:0.25 (with --belief; "
                    "a network that has the part keeps it). '' = off")
    ap.add_argument("--track-z-warm", type=float, default=60.0, help="... minutes over which its lesson rises from nothing (from --track-z-start)")
    ap.add_argument("--track-z-start", type=float, default=-1.0, help="... the minute its lesson counts from (-1: this process's start)")
    ap.add_argument("--track-z-lr-scale", type=float, default=-1.0, help="... its layers learn at this many times --lr (-1: as --track-lr-scale)")
    # v0.4.1 (docs/v0.4.0/RUN_v0.4.1.md; sim/btoken.py): the brain's answer as one more token of the hands' attention, behind a gate
    # that is shut (exactly: the token is not there) until it opens; the answers the hands saw are kept with the rollout
    ap.add_argument("--btoken", type=int, default=0, help="v0.4.1: 1 = the brain's token in the hands' attention (a network without one gets it, "
                    "its gate shut; a network that has one keeps it). 0 = off (a network that has one plays with its gate shut)")
    ap.add_argument("--btoken-delay", type=float, default=60.0, help="... minutes after --btoken-start before the gate begins to open")
    ap.add_argument("--btoken-open", type=float, default=240.0, help="... minutes for the gate from 0 to 1 (live: BTOK_GATE_OPEN; 0 holds it)")
    ap.add_argument("--btoken-cap", type=float, default=1.0, help="... the gate is never above this (live: BTOK_GATE_CAP; 0 shuts it at once)")
    ap.add_argument("--btoken-start", type=float, default=-1.0, help="... the minute the delay counts from (-1: this process's start; pass it on every resume)")
    ap.add_argument("--btoken-gate", type=float, default=-1.0, help="... the gate to start this process at (-1: the network's own, 0 for a new token)")
    ap.add_argument("--btoken-lr-scale", type=float, default=1.0, help="... the token's own first layer and mark learn at this many times --lr")
    # v0.4.2a (docs/v0.4.0/RUN_v0.4.2a.md; sim/rule_fade.py): the rule-made input columns faded out of the hands by a gate g
    # (times 1 - g after the input scaling; the brain reads them unfaded); the simulator's readers of the old belief on the
    # brain's answer for a life drawn with chance g (BRAIN_READ=1 in the simulator); g kept with each rollout, learnt at it
    ap.add_argument("--rule-fade", type=int, default=0, help="v0.4.2a: 1 = the rule fade (a network without its entry gets it, shut; "
                    "one that has it keeps it). 0 = off (a network that has it plays at g 0)")
    ap.add_argument("--rule-fade-delay", type=float, default=60.0, help="... minutes after --rule-fade-start before g begins to rise")
    ap.add_argument("--rule-fade-open", type=float, default=240.0, help="... minutes for g from 0 to 1 (live: FADE_OPEN; 0 holds it)")
    ap.add_argument("--rule-fade-cap", type=float, default=1.0, help="... g is never above this (live: FADE_CAP; 0 shuts it at once)")
    ap.add_argument("--rule-fade-start", type=float, default=-1.0, help="... the minute the delay counts from (-1: this process's start; pass it on every resume)")
    ap.add_argument("--rule-fade-g", type=float, default=-1.0, help="... g to start this process at (-1: the network's own, 0 for a new entry)")
    ap.add_argument("--ahead", default="", help="v0.4.1: the brain's readout of what comes next (sim/ahead.py), its lesson by part, e.g. "
                    "fut:0.5,target:0.25,appear:0.25 (with --belief and --track). '' = off (a network that has it keeps it)")
    ap.add_argument("--ahead-warm", type=float, default=30.0, help="... minutes over which its lesson rises from nothing (from --ahead-start)")
    ap.add_argument("--ahead-start", type=float, default=-1.0, help="... the minute its lesson counts from (-1: this process's start)")
    ap.add_argument("--ahead-lr-scale", type=float, default=-1.0, help="... its layers learn at this many times --lr (-1: as --track-lr-scale)")
    # (brainppl, 2026-10-24; sim/brain_human.py) the brain's lesson on people's games beside self-play's: a dataset of people's
    # sessions and pro demos (sim/brain_fit.py --save-pack); each learning step of the brain's lesson adds w x the same lesson
    # on the next piece of those lanes (w: --brain-human-w, live BRAIN_HUMAN_W, times its opening). Off (''): as before
    ap.add_argument("--brain-human", default="", help="brainppl: the people's dataset folders (obs.npy, done.npy, labels.pt), comma-separated "
                    "(e.g. the pro demos' and the server sessions'). '' = off")
    ap.add_argument("--brain-human-mix", default="", help="... their shares inside the people's part, e.g. 0.6,0.4 (default: even)")
    ap.add_argument("--brain-human-w", type=float, default=0.0, help="... the people's SHARE s of the brain's lesson: (1 - s) x self-play's + s x "
                    "people's (live: BRAIN_HUMAN_W; 0: self-play's alone, as before)")
    ap.add_argument("--brain-drop", default="", help="brainppl: a JSON {cols: [...]}: the brain's input weights of these columns held at zero "
                    "(the domain-leak check's columns, as sim/brain_fit.py --drop-cols). '' = off")
    ap.add_argument("--brain-human-open", type=float, default=0.0, help="... minutes over which the weight rises from 0 (from --brain-human-start)")
    ap.add_argument("--brain-human-start", type=float, default=-1.0, help="... the minute its opening counts from (-1: this process's start; give the same on every resume)")
    ap.add_argument("--brain-human-lanes", type=int, default=1, help="... lanes of the dataset in each piece (the groups of lanes in turn: with 16 lanes and 1, each lane moves on 1/16 of the pieces)")
    ap.add_argument("--brain-human-piece", type=int, default=384, help="... frames of a piece (whole ticks)")
    ap.add_argument("--control", type=float, default=0.0, help="v0.4.3 (B-280): the brain's readout 'in control' (sim/control.py), his share "
                    "of the next two mega / red armor spawns, a lesson only; its weight (a factor on --control-lr). 0 = off (a network that has it keeps "
                    "it). With --belief and --track; the simulator's CONTROL_TRUTH=1 gives the truth")
    ap.add_argument("--control-lr", type=float, default=1e-3, help="... its own Adam's rate at weight 1")
    ap.add_argument("--control-warm", type=float, default=60.0, help="... minutes over which its lesson rises from nothing (from --control-start)")
    ap.add_argument("--control-start", type=float, default=-1.0, help="... the minute its warm-up counts from (-1: this process's start)")
    ap.add_argument("--control-every", type=int, default=5, help="... the brain's state kept every this many of its ticks (5: 1 s; the ring "
                    "holds the horizon and a rollout: about 0.5 GB on the host with 10,080 players on the belief alone, 1.6 GB with the hands' "
                    "memory (both, belief,both))")
    ap.add_argument("--control-hid", type=int, default=64, help="... its hidden layer")
    ap.add_argument("--control-src", default="belief", help="... what it reads: the brain's state (belief, 256) or the brain's "
                    "state and his hands' memory, both detached (both, 256 + 512: the probe of 2026-10-24 read more from his memory; "
                    "the ring then holds three times as much); belief,both: two readouts side by side on one ring, each scored and "
                    "taught on its own (v0.4.2b)")
    ap.add_argument("--win-value", type=float, default=0.0, help="v0.4.3 (owner, 2026-10-24): the shadow win value (sim/win_value.py): "
                    "the value of WIN_SHADOW's pay (WIN_PAY as it would pay) on the brain's state and the hands' memory, detached; its own "
                    "Adam and random stream; never pay, advantage or play. Its weight (a factor on --win-value-lr); 0 = off (needs WIN_SHADOW=1)")
    ap.add_argument("--win-value-lr", type=float, default=1e-3, help="... its own Adam's rate at weight 1")
    ap.add_argument("--win-value-warm", type=float, default=60.0, help="... minutes over which its rate rises from nothing (from --win-value-start)")
    ap.add_argument("--win-value-start", type=float, default=-1.0, help="... the minute its warm-up counts from (-1: this process's start)")
    ap.add_argument("--win-value-every", type=int, default=2, help="... the states kept every this many of the brain's ticks (2: 0.4 s)")
    ap.add_argument("--win-value-hid", type=int, default=128, help="... its hidden layer")
    ap.add_argument("--win-value-gamma", type=float, default=1.0, help="... its discount a frame (1: the game's sum, cut at its end)")
    ap.add_argument("--win-value-lam", type=float, default=0.95, help="... TD(lambda) over its kept states")
    ap.add_argument("--win-value-cal-every", type=int, default=5, help="... every this many kept states go into the calibration at a game's end")
    ap.add_argument("--gamma", type=float, default=0.998,
                    help="how far ahead rewards count: 0.995 = about 5 s, 0.998 = about 12 s, 0.999 = about 25 s")
    ap.add_argument("--demo-dir", default="", help="pro-demo training data (sim/demo_dataset.py), folders separated by commas")
    ap.add_argument("--demo-coef", type=float, default=0.0, help="weight of the imitation loss on pro demos (0 = off)")
    ap.add_argument("--demo-minutes", type=float, default=0.0, help="the demo loss fades to zero over this time (0 = constant)")
    ap.add_argument("--demo-batch", type=int, default=64, help="demo sequences per minibatch")
    ap.add_argument("--demo-len", type=int, default=64, help="frames per demo sequence")
    ap.add_argument("--demo-pool", type=int, default=48, help="demo files held in memory (a new random set every 20 updates)")
    ap.add_argument("--demo-heads", default="1,1,1,1,1,0.5,0.5,1",
                    help="weight of each action head in the demo loss: forward, strafe, vertical, turn, pitch, fire, weapon, walk")
    ap.add_argument("--teacher", default="multimap_v1", help="movement policy run used as a teacher in movement rounds ('' = none)")
    ap.add_argument("--teacher-skip", default="", help="'toxicity,lostworld:item': a map alone = no key labels in its runs; map:item "
                    "= none in its item runs, the movement teacher's in its jump runs. Maps on which the movement teacher gives no labels: where its "
                    "pupil test fails (tools/label_check.py), e.g. lava he walks into with its labels alone")
    ap.add_argument("--move-maps", default="", help="maps (comma list) he only learns to move on: one more simulator per map "
                    "named, with item runs and jump runs only (no games, no league seats)")
    ap.add_argument("--move-matches", type=int, default=0, help="... its size in pairs of players (0 = half of --matches)")
    ap.add_argument("--teach", type=float, default=0.5, help="weight of the teacher loss at the start of this run")
    ap.add_argument("--teach-minutes", type=float, default=240, help="the teacher loss fades to zero over this time")
    ap.add_argument("--teach-warm", type=float, default=0.0, help="minutes over which that weight first rises from nothing: a new "
                    "teacher at full weight moves the whole policy in its first update (0.60 at 0.5 with the strafe-jumping "
                    "teacher, 2026-10-09; the run before started at 0.021), while its loss is still large")
    ap.add_argument("--legs-teach", type=float, default=0.0,
                    help="stage C, part 1: the weight of the lesson of his legs (0 = off). On the frames the simulator gives a label "
                         "(LEGS_LABEL=1: the movement network's four choices where his legs carried him, or would have in a withheld "
                         "stretch) his own outputs for forward and back, sideways, jump and crouch and the view's turn are pulled "
                         "toward it: cross-entropy, the keys only on the frames his hand reads them. Not paid")
    ap.add_argument("--legs-teach-trunk", type=float, default=1.0, help="... the share of that lesson's gradient that reaches the shared "
                                                                        "layers (as --teach-trunk); the output layer learns it in full")
    ap.add_argument("--legs-teach-warm", type=float, default=0.0, help="... minutes over which its weight rises from nothing, counted from "
                                                                       "--fade-start (a teacher at full weight from the first update "
                                                                       "has cost him aim before)")
    ap.add_argument("--legs-learn", type=float, default=0.0,
                    help="(LEGS_IN, B-253 stage b) his legs' branch learns from games: its learning rate is this share of the rest's "
                         "(0.25: a quarter), through the rate schedule; 0 = off (stage a: frozen). On the frames his legs moved him "
                         "the branch's log-probability of its own draw (before the hand rule; its keys only on the frames his hand "
                         "reads them) joins the PPO ratio, with the run's advantage")
    ap.add_argument("--legs-feat", type=int, default=0,
                    help="(one movement network, step 3; LEGS_IN) 1: the legs' branch's second hidden layer goes through a new "
                         "layer legs_door (256 -> 256, at zero) into his fast GRU's input on every frame (sim/legs_unify.py; "
                         "the branch's numbers detached). Saved in the checkpoint: a resume keeps it")
    ap.add_argument("--legs-guide", type=int, default=0,
                    help="(one movement network, step 4; LEGS_IN) 1: his movement outputs (LEGS_TAKES) get w * the branch's "
                         "choice mapped onto their bins as log-probabilities, w learnt per output from 0 (sim/legs_unify.py). "
                         "Saved in the checkpoint")
    ap.add_argument("--legs-ent", type=float, default=0.0,
                    help="... the exploration bonus on the branch's four choices: this times his own movement outputs' weights in "
                         "--ent-heads (forward, strafe, vertical for its jump, turn), so 1 = the same as his; 0 = none (the default: "
                         "the branch starts sharp from its own training and its draws already explore; a bonus pulls it flat)")
    ap.add_argument("--gate-open", type=float, default=0.0,
                    help="the attention part's gate (sim/attn.py): the tokens whose gate is below zero in the network he starts from "
                         "(new tokens begin shut at -30: tools/targets_init.py) are opened over this many minutes, counted from "
                         "--fade-start: before every rollout their gate is set to a value rising in a straight line from --gate-from "
                         "to 0 (never lowered: a gate already further open stays until the line passes it). At 0 it stays 0 and is "
                         "saved so; a resume goes on from the clock. 0 = off: the gate is left as the checkpoint has it. The "
                         "league's files keep their own gates")
    ap.add_argument("--turn-add-open", type=float, default=0.0,
                    help="(LEGS_TURN_ADD) his turn correction on his legs starts shut (the bias of its choice 0 at duel_env's TA_SHUT "
                         "over the others: another choice drawn with the chance e^-20, which no update finds by trying). It is opened "
                         "over this many minutes, counted from --turn-add-start: before every rollout that bias is held at or under a value "
                         "falling in a straight line from TA_SHUT to --turn-add-to (never raised: a bias already lower stays). After that "
                         "it is the network's own. 0 = off: the bias is left as the checkpoint has it. The league's files keep theirs")
    ap.add_argument("--turn-add-start", type=float, default=-1.0, help="... the minute of training the opening counts from (as "
                    "--fade-start; -1: where this process starts, so a resume must pass the first start's minute, which the trainer prints)")
    ap.add_argument("--turn-add-to", type=float, default=4.68, help="... where the line ends: the bias of 0 over the others (with the "
                                                                    "weights at 0, 4.68 draws a correction on 10%% of his frames on his legs)")
    ap.add_argument("--keys-add-open", type=float, default=0.0,
                    help="(LEGS_KEYS_ADD) his five choices 'my legs' / mine' on his legs (forward/back, sideways, jump/crouch, walk, "
                         "zoom) start shut (the bias of 'my legs' at duel_env's KA_SHUT over 'mine'). They are opened over this many "
                         "minutes counted from --keys-add-start, as --turn-add-open: before every rollout each bias is held at or "
                         "under a line falling from KA_SHUT to --keys-add-to (never raised). 0 = off: as the checkpoint has them")
    ap.add_argument("--keys-add-start", type=float, default=-1.0, help="... the minute of training the opening counts from (-1: where "
                    "this process starts; a resume must pass the first start's minute, which the trainer prints)")
    ap.add_argument("--keys-add-to", type=float, default=2.94, help="... where the line ends: the bias of 'my legs' over 'mine' (with "
                                                                    "the weights at 0, 2.94 gives 'mine' on 5%% of the frames on his legs)")
    ap.add_argument("--legs-gate", type=int, default=0,
                    help="(v0.3.4 A; LEGS_IN) 1: his own movement outputs (0, 1, 2, 3, 7, 8) get g(h) x the legs' choice mapped onto "
                         "their bins (as --legs-guide's) plus a motor layer of the legs' 256 numbers; g a linear layer of his memory, "
                         "both at zero (sim/legs_unify.py). Counts where he drives himself. Saved in the checkpoint")
    ap.add_argument("--legs-residual", type=int, default=0,
                    help="(v0.3.4 B; LEGS_IN with --legs-learn) 1: on his legs the legs' logits become (1 - a(h)) x theirs + W h, "
                         "a = clamp(linear(h), 0, 1) per choice, both at zero: the simulator draws his legs' choice from that, and "
                         "it learns from those draws as the branch does. Saved in the checkpoint")
    ap.add_argument("--legs-residual-ent", type=float, default=0.1,
                    help="(--legs-residual) the exploration bonus on his legs' four choices: this times his own movement outputs' "
                         "weights in --ent-heads")
    ap.add_argument("--solo-self-drive", type=int, default=0,
                    help="(v0.3.4 C) 1: in item runs and jump runs his legs do not carry him (duel_env's SOLO_SELF) and the switch's "
                         "lesson is silent there")
    ap.add_argument("--switch-fade", type=int, default=0,
                    help="(v0.3.4 C) 1: a bias taken off the switch's 'legs' choice, from 0 (or the checkpoint's), raised by "
                         "--switch-fade-step after each update in which his own speed in the runs is at least --switch-fade-speed, "
                         "up to --switch-fade-max. Saved in the checkpoint and in policy.npz (the plugins take it off too)")
    ap.add_argument("--no-switch", type=int, default=0,
                    help="(v0.3.5, step 6) 1: the switch to his legs retired (sets duel_env's NO_SWITCH): his own network always "
                         "drives, the switch's lesson is dropped, and the legs' branch is no longer detached in legs_door and the "
                         "gate's motor layer: it learns from his own loss through them, at --legs-learn of the rate")
    ap.add_argument("--switch-fade-step", type=float, default=0.25)
    ap.add_argument("--switch-fade-speed", type=float, default=325.0)
    ap.add_argument("--switch-fade-max", type=float, default=8.0)
    ap.add_argument("--legs-door-lr-scale", type=float, default=0.25,
                    help="(--legs-feat, --legs-guide) legs_door and the guide's weights in an optimiser group of their own at this share "
                         "of the rate (through the rate schedule)")
    ap.add_argument("--gate-from", type=float, default=-6.0, help="... where the line begins (at -6 a look at such a token weighs a "
                                                                 "four-hundredth of what it weighs at 0)")
    ap.add_argument("--gate-start", type=float, default=-1.0,
                    help="(v0.3.6) the minute of training --gate-open's line counts from (default: --fade-start, as before): a run "
                         "that gives new tokens to a network whose older ones were opened already (tools/v036_init.py) starts their "
                         "line at its own first minute, not at the teachers' fade start (which would open them at once)")
    ap.add_argument("--kind-p", default="0.40,0.15,0.10,0.35",
                    help="share of rounds: normal duel, aim (scripted strafing target), one-weapon drill, movement")
    ap.add_argument("--bot-p", type=float, default=0.5, help="share of normal rounds against the scripted fighter")
    ap.add_argument("--react-ms", type=float, default=100, help="tracking delay on an enemy already in view (100: !aim default; 50 until branch aim2)")
    ap.add_argument("--acquire-ms", type=float, default=200, help="delay before an enemy who just came into view is noticed")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--env", default="duel_env", help="simulator module (duel_env_ffa: groups of more than two players)")
    ap.add_argument("--group", default="2", help="players per group, all against all (needs --env duel_env_ffa). Several "
                    "sizes separated by commas (2,3,4): the workers take them in turn, each with about as many players")
    ap.add_argument("--max-updates", type=int, default=0, help="(checks) stop after this many updates (0: --minutes alone)")
    ap.add_argument("--seed", type=int, default=-1, help="(checks) the trainer's own random streams (torch, numpy) seeded; -1: not (as before)")
    ap.add_argument("--dump-acts", default="", help="(checks) after each update: <this>_<update>.pt with the rollout's actions, log p, "
                                                    "values and rewards (a fixed-seed identity check of two runs)")
    a = ap.parse_args()
    if a.solo_self_drive:                                    # (v0.3.4 C) read by the simulators (spawned with this environment)
        os.environ["SOLO_SELF"] = "1"


    import torch
    import torch.nn as nn
    if a.seed >= 0:                                          # (--seed) checks only: the simulators are seeded as always (3000 + worker)
        torch.manual_seed(a.seed)
        np.random.seed(a.seed)
    sys.path.insert(0, HERE)
    import importlib
    E_ = importlib.import_module(a.env)
    ACTION_DIMS, OBS_DIM, PERSONAS, WEAPONS = E_.ACTION_DIMS, E_.OBS_DIM, E_.PERSONAS, E_.WEAPONS
    KEY_HEADS = (0, 1, 2, 6)                                 # forward, strafe, vertical, weapon key: the left hand's outputs
    V_HEAD = 2                                               # (JUMP_EVERY) the vertical key (none, jump, crouch): its jump bit is read on every
    JE = bool(getattr(E_, "JE_ON", False))                   # frame, the rest on the hand's (see JumpCat, head_masks)
    I_HEAD = getattr(E_, "INTENT_HEAD", len(ACTION_DIMS) - 1)                # the intention; (LEGS) the switch to his legs and the
    L_HEAD, L_TAKES = (E_.LEGS_HEAD, tuple(E_.LEGS_TAKES)) if len(ACTION_DIMS) > getattr(E_, "LEGS_HEAD", 99) else (-1, ())   # outputs they take
    TA_HEAD = E_.TA_HEAD if getattr(E_, "LEGS_TURN_ADD", False) and len(ACTION_DIMS) > getattr(E_, "TA_HEAD", 99) else -1
    KA_ON = bool(getattr(E_, "LEGS_KEYS_ADD", False)) and len(ACTION_DIMS) >= getattr(E_, "KA_HEAD", 99) + 5     # (LEGS_KEYS_ADD)
    KA_HEAD, KA_COLS = (E_.KA_HEAD, tuple(E_.KA_COLS)) if KA_ON else (-1, ())       # his five "my legs' / mine" on his legs and their columns     # (LEGS_TURN_ADD) his turn correction on his legs: counted
    #                                                          on the frames his legs moved him only
    W_HEAD = E_.WAY_HEAD if len(ACTION_DIMS) > getattr(E_, "WAY_HEAD", 99) else -1     # (WAYS) his way to his target: read with the intention,
    W_ON = bool(getattr(E_, "WAYS", False))                                             # ... and with the switch off never (the output is there)

    EN_I = E_.EN_INTENT if getattr(E_, "EN_ON", getattr(E_, "FIGHT_TARGET", False)) else -1     # (FIGHT_TARGET, HUNT) the intention "the enemy"
    TG_I = (E_.HOLD_INTENT, E_.HOLD_INTENT + E_.HOLD_SLOTS) if getattr(E_, "TARGETS", False) else None     # (TARGETS) the intentions "place 1" to "place 8"

    LEGS_LAB = bool(getattr(E_, "LEGS_LAB", False))          # (--legs-teach) the simulators give the labels of his legs (LEGS_LABEL=1, or LEGS_KEEP below 1)
    # (LEGS_IN=1, B-253 stage a) his legs' network is a branch of his own: legs.0, legs.2, legs.4 (61 -> 256 -> 256 -> 17,
    # tanh), its weights those of --teacher's policy.npz (or the network's own, when it has them); frozen (no gradient, not
    # in the optimiser). The simulators send its inputs with every frame (duel_env's legs_prep()); its logits go back with
    # the actions and are what the simulator samples his legs' choices from. A league file without the branch is given
    # the movement network's.
    LEGS_IN = bool(getattr(E_, "LEGS_IN", False))
    LEGS_SD, LEGS_D, LEGS_SAID = {}, 0, []
    if LEGS_IN:
        assert a.teacher, "LEGS_IN=1: give --teacher <the movement network's run> (its policy.npz is the branch)"
        z_ = np.load(os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz"))
        LEGS_SD = {"legs.0.weight": z_["w0"], "legs.0.bias": z_["b0"], "legs.2.weight": z_["w1"], "legs.2.bias": z_["b1"],
                   "legs.4.weight": z_["wp"], "legs.4.bias": z_["bp"]}
        LEGS_D = int(z_["w0"].shape[1])
        assert int(z_["wp"].shape[0]) == 17, "the legs' network has {} outputs, the simulator samples 3 + 3 + 2 + 9".format(z_["wp"].shape[0])
        print("legs inside (LEGS_IN, B-253 stage a): the branch {} -> 256 -> 256 -> 17 from {} ({} weights), {}".format(
            LEGS_D, a.teacher, sum(v_.size for v_ in LEGS_SD.values()),
            "learning at {:g} of the rate (stage b), exploration bonus {:g}".format(a.legs_learn, a.legs_ent) if a.legs_learn > 0 else "frozen"), flush=True)
    # (--legs-learn, B-253 stage b) the branch learns: its log-probability of its own draw (env.legs_raw: before the turn's
    # hand rule) on the frames his legs moved him joins the ratio; its own optimiser group at --legs-learn of the rate
    LEGS_LEARN = LEGS_IN and a.legs_learn > 0
    assert a.legs_learn <= 0 or LEGS_IN, "--legs-learn: set LEGS_IN=1 (with LEGS=1 and --teacher <the movement network's run>)"
    assert a.legs_ent <= 0 or LEGS_LEARN, "--legs-ent: only with --legs-learn"
    LEGS_DIMS = (3, 3, 2, 9)                                 # the branch's four choices: forward, sideways, jump, turn (the simulator's order)
    LEGS_KEYS = (True, True, True, False)                    # ... the first three are keys: they count on the frames his hand reads them
    assert a.legs_teach <= 0 or LEGS_LAB, "--legs-teach: the simulator {} gives no labels (set LEGS_LABEL=1 with LEGS=1; p_c1_env.py)".format(a.env)
    HAND_LAB = bool(getattr(E_, "HAND_TEACH", False))        # (--hand-teach) the simulators give the label of his weapon output (HAND_TEACH=1)
    assert a.hand_teach <= 0 or HAND_LAB, "--hand-teach: the simulator {} gives no labels (set HAND_TEACH=1; p_hand_env.py)".format(a.env)
    assert 0.0 <= a.hand_teach_trunk <= 1.0, "--hand-teach-trunk: a share, 0 to 1"
    RJ_LAB = bool(getattr(E_, "RJ_TEACH", False))            # (--rj-teach) the simulators give the rocket jump's moment (RJ_TEACH=1)
    assert a.rj_teach <= 0 or RJ_LAB, "--rj-teach: the simulator {} gives no labels (set RJ_TEACH=1)".format(a.env)
    assert 0.0 <= a.rj_teach_trunk <= 1.0, "--rj-teach-trunk: a share, 0 to 1"
    FIRE_HEAD = 5                                            # (--rj-teach) the trigger (no, fire)
    RJC_LAB = bool(getattr(E_, "RJ_COPY", False)) or bool(getattr(E_, "ROUTE_COPY", ""))   # (--rj-copy) the simulators give the runner's choices (RJ_COPY=1, ROUTE_COPY)
    RJC_H = int(getattr(E_, "RJC_HEADS", 9))                 # ... for the outputs 0 to RJC_H - 1
    RJC_NAMES = ("fwd", "side", "vert", "turn", "pitch", "fire", "weapon", "walk", "zoom")[:RJC_H]
    assert a.rj_copy <= 0 or RJC_LAB, "--rj-copy: the simulator {} gives no labels (set RJ_COPY=1 or ROUTE_COPY)".format(a.env)
    assert 0.0 <= a.rj_copy_trunk <= 1.0, "--rj-copy-trunk: a share, 0 to 1"
    HAND_HEAD = 6                                            # ... the weapon key's output, where its choices begin among all outputs' and
    HAND_O, HAND_D = sum(ACTION_DIMS[:HAND_HEAD]), ACTION_DIMS[HAND_HEAD]      # how many they are ("keep", then a choice a weapon)

    def head_masks(dc, lv, ll, lo, act=None, so=None, ent=False):
        """per output: the frames its choice counted on (None: every frame). dc: the left hand's outputs were read, lv: the
        intention was read, ll: the switch to his legs was read, lo: his legs moved him (their outputs were not his).
        (LEGS_KEYS_ADD) act: his choices [..., outputs]: on his legs his own output of a column counts where he chose "mine"
        for it; the five choices count on his legs (the keys' on the frames his hand reads them).
        (JUMP_EVERY) the vertical key counts on every frame (on the frames between the hand's readings its stored choice is
        the jump bit alone: JumpCat); ent=True: the masks of the exploration bonus, where it stays on the hand's frames"""
        out = []
        mine_ = {}
        if KA_ON:
            assert act is not None, "LEGS_KEYS_ADD: head_masks needs his choices"
            mine_ = {c_: (act[..., KA_HEAD + i_] == 1).to(lo.dtype) for i_, c_ in enumerate(KA_COLS)}
        for j in range(len(ACTION_DIMS)):
            m = dc if j in KEY_HEADS else (lv if j == I_HEAD else (ll if j == L_HEAD else None))
            if JE and j == V_HEAD and not ent:                   # (JUMP_EVERY) the jump read on every frame
                m = None
            if j == L_HEAD and so is not None and a.solo_self_drive:     # (--solo-self-drive) not in his runs
                m = m * (1.0 - so)
            if j == L_HEAD and NO_SW:                            # (--no-switch) the switch's lesson dropped
                m = ll * 0.0
            if j == W_HEAD:                                      # (WAYS) his way: on the frames the intention was read; on none with the switch off
                m = lv if W_ON else lv * 0.0
            if j in L_TAKES:
                g_ = (1.0 - lo) if j not in mine_ else (1.0 - lo) + lo * mine_[j]      # (LEGS_KEYS_ADD) and where "mine" took it
                m = g_ if m is None else m * g_
            if KA_ON and KA_HEAD <= j < KA_HEAD + len(KA_COLS):  # (LEGS_KEYS_ADD) "my legs' / mine": on his legs
                m = lo * dc if KA_COLS[j - KA_HEAD] in KEY_HEADS else lo
            if j == TA_HEAD:                                     # (LEGS_TURN_ADD) his correction: only where it was added to his legs' turn
                m = lo
            out.append(m)
        return out

    OBS_FREEZE = 2e9                                         # frames after which the input statistics stand still (they did anyway)
    groups = [int(x) for x in str(a.group).split(",")]
    G = groups[0]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev.type == "cuda" and os.environ.get("GPU_MEM_FRACTION"):
        # PyTorch keeps freed blocks and so fills the card whatever the batch needs (15.8 GB with 8372 players and with
        # 7560 alike, 2026-10-06): this caps what the process may hold, leaving room for the desktop and a game
        torch.cuda.set_per_process_memory_fraction(float(os.environ["GPU_MEM_FRACTION"]))
    if dev.type == "cpu":
        torch.set_num_threads(6)
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)
    maps = a.map.split(",")
    os.environ["TEACHER_SKIP"] = a.teacher_skip              # (read by the simulators: the key labels of a map's runs)
    course_keys = []
    lab_json = os.path.join(ROOT, "maps", "testlab", "rooms.json")
    if os.path.exists(lab_json):
        course_keys = list(json.load(open(lab_json)).get("courses", {}))
    pipes = []
    w_group = [groups[w % len(groups)] for w in range(a.workers)]             # group size of each worker
    w_match = [max(2, (2 * a.matches // g_) // 2 * 2) for g_ in w_group]       # ... and its groups: about 2 x matches players
    w_map = [maps[w % len(maps)] for w in range(a.workers)]
    move_maps = [m_ for m_ in a.move_maps.split(",") if m_]                    # (--move-maps) one more worker a map: runs only
    w_group += [2] * len(move_maps)
    w_match += [max(2, (a.move_matches or a.matches // 2) // 2 * 2)] * len(move_maps)
    w_map += move_maps
    w_move = [w >= a.workers for w in range(len(w_map))]
    for w in range(len(w_map)):
        m = w_map[w]
        p_main, p_work = mp.Pipe()
        mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), w_match[w], 3000 + w,
                                        os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m)), a.loadout,
                                        a.item_reward, a.drill_p, a.drill_weapons, (round(a.react_ms / 25), round(a.acquire_ms / 25)),
                                        tuple(float(x) for x in a.kind_p.split(",")), a.bot_p,
                                        os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz") if (a.teacher and m not in a.teacher_skip.split(",")) else None,   # (the worker reads TEACH_RUNS_<map>)
                                        tuple(a.lab_courses.split(",")), tuple(float(x) for x in a.lab_p.split(",")),
                                        tuple(float(x) for x in a.loadout_p.split(",")) if a.loadout_p else None, a.lab_items, a.lab_gun,
                                        a.dmg_taken_w, a.no_walk, a.arena_len, a.arena_full, a.env, w_group[w],
                                        a.intent_seek, a.item_loss, a.stack_p, a.near_item_p, w_move[w]),
                   daemon=True).start()
        pipes.append(p_main)
    first = [p.recv() for p in pipes]
    if os.environ.get("TRAINER_MASK"):                                   # (2026-10-18, after the BIOS update) the workers keep the mask
        import pin as pin_                                               # they were started with; the trainer itself (its learning step's
        ok_ = pin_.pin_mask(int(os.environ["TRAINER_MASK"], 16))         # main thread) goes to the mask named here: the performance cores
        print("trainer process mask {} ({}); the {} workers keep the start mask".format(
            os.environ["TRAINER_MASK"], "set" if ok_ else "NOT SET", len(pipes)), flush=True)
    if a.teacher_skip:
        print("no key labels in the runs of: {}".format(a.teacher_skip), flush=True)
    obs = np.concatenate([f[0] for f in first])
    teach = np.concatenate([f[1] for f in first])
    hand = np.concatenate([f[3] for f in first]) if HAND_LAB else None      # (--hand-teach) the label of the frame about to be played
    rjl = np.zeros(len(obs), np.int8) if RJ_LAB else None                    # (--rj-teach) ... the rocket jump's (none on the first frame)
    rjc = np.full((len(obs), RJC_H), -1, np.int8) if RJC_LAB else None       # (--rj-copy) ... the runner's (none on the first frame)

    def legs_cat(parts):
        """(LEGS_IN) the workers' legs inputs as one array (a simulator without the movement network gives none: zeros)"""
        return np.concatenate([p_ if p_ is not None and p_.ndim == 2 and p_.shape[1] == LEGS_D else np.zeros((len(o_), LEGS_D), np.float32)
                               for p_, o_ in parts]).astype(np.float32)
    legs_x = legs_cat([(f[4], f[0]) for f in first]) if LEGS_IN else None
    N = len(obs)
    IF_MAPS = sorted(set(w_map))                                         # (--item-floor) the maps, each player's, each map's big items
    IF_PM = np.concatenate([np.full(len(f[0]), IF_MAPS.index(w_map[w]), np.int64) for w, f in enumerate(first)])
    IF_OK = np.zeros((len(IF_MAPS), len(getattr(E_, "INTENTS", ()))), bool)
    for w, f in enumerate(first):
        for k_ in (f[5] if len(f) > 5 else ()):
            IF_OK[IF_MAPS.index(w_map[w]), int(k_)] = True
    H = a.hidden

    CELL_DIM = 16                                            # v8 only: a learned table of 16 numbers per 64-unit cell
    HAS_CELLS = getattr(E_, "CELL_COLS", None) is not None   # (v9: the map reader's numbers are plain inputs instead)
    if HAS_CELLS:
        assert tuple(E_.CELL_COLS) == (OBS_DIM - 2, OBS_DIM - 1)

    ATT = None                                               # (v0.2) the attention part's layout: it comes with the network he resumes from
    SLOW_CK = None                                           # (--slow-mem) the slow memory's layout: comes with the network as the attention part's
    HEAD_CK = None                                           # (--head) the head's layout: comes with the network, as the slow memory's
    AUX_CK = ()                                              # (--aux) which of the layers of 2026-10-12 the network he resumes from has
    AUX_SAVE = {}                                            # (--aux) what is kept in a saved file beside the lesson's layers
    UNI_CK = None                                            # (--legs-feat, --legs-guide) the parts' layout: comes with the network
    TRK_CK = None                                            # (--track, v0.3.11) the belief readout's layout: comes with the network
    BEL_CK = None                                            # (--belief, v0.4.0 A) the belief memory's layout: comes with the network
    TRZ_CK = None                                            # (--track-z, v0.4.0) the readout's second part: comes with the network
    BTOK_CK = None                                           # (--btoken, v0.4.1) the brain's token: comes with the network
    AH_CK = None                                             # (--ahead, v0.4.1) the readout of what comes next: comes with the network
    CTL_CK = None                                            # (--control, v0.4.3) the readout "in control": comes with the network
    RF_CK = None                                             # (--rule-fade, v0.4.2a) the faded columns and the gate: come with the network
    H2_CK = None                                             # (--head2, v0.4.3) the strategy head's layout: comes with the network
    WV_CK = None                                             # (--win-value, v0.4.3) the shadow win value: its layout and weights
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck0_ = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location="cpu")
        ATT = ck0_.get("attn")
        SLOW_CK = ck0_.get("slow")
        HEAD_CK = ck0_.get("head")
        UNI_CK = ck0_.get("legs_unify")
        if any(k_.startswith("aux.") for k_ in ck0_["model"]):
            AUX_SAVE = dict(aux_heads=ck0_.get("aux_heads"))
        AUX_CK = tuple(h_ for h_ in ("target", "strength", "first", "near") if "aux.{}.weight".format(h_) in ck0_["model"])
        TRK_CK = ck0_.get("track") if any(k_.startswith("track.") for k_ in ck0_["model"]) else None
        BEL_CK = ck0_.get("belief") if any(k_.startswith("belief.") for k_ in ck0_["model"]) else None
        TRZ_CK = ck0_.get("track_z") if any(k_.startswith("trackz.") for k_ in ck0_["model"]) else None
        BTOK_CK = ck0_.get("btoken") if any(k_.startswith("attn.btok_") for k_ in ck0_["model"]) else None
        AH_CK = ck0_.get("ahead") if any(k_.startswith("ahead.") for k_ in ck0_["model"]) else None
        CTL_CK = ck0_.get("control") if any(k_.startswith("control.") for k_ in ck0_["model"]) else None
        RF_CK = ck0_.get("rule_fade")
        H2_CK = ck0_.get("head2") if any(k_.startswith("head2.") for k_ in ck0_["model"]) else None
        WV_CK = ck0_.get("win_value")                        # (--win-value) a top-level entry, never in "model"
        del ck0_
    if ATT is not None and a.attn_mem_query and not ATT.get("mem"):     # (--attn-mem-query) a new layer at zero
        ATT = dict(ATT, mem=H)
    ATT_MEM = bool(ATT is not None and ATT.get("mem"))
    if ATT_MEM:
        assert int(ATT["mem"]) == H, "the attention part's memory query reads {} numbers, his memory has {}".format(ATT["mem"], H)
        print("attention: block 2's query also from his memory of the frame before (--attn-mem-query)", flush=True)
    assert not a.attn_mem_query or ATT is not None, "--attn-mem-query: the network has no attention part"
    if ATT is not None:
        import attn as attn_
        assert ATT["obs_dim"] == OBS_DIM, "the network's tokens are cut from {} inputs, the simulator has {}".format(ATT["obs_dim"], OBS_DIM)
        print("attention: " + attn_.describe(ATT), flush=True)
    SLOW = SLOW_CK                                           # (--slow-mem) the network's own part, or a new one with its door shut
    if SLOW is not None or a.slow_mem > 0:
        import slowmem as slowmem_
        if SLOW is None:
            SLOW = slowmem_.layout(size=a.slow_size, inp=a.slow_in, every=a.slow_every, ring=320, fast=H, enc=256)
        if a.slow_ring >= 0:
            SLOW = dict(SLOW, ring=int(a.slow_ring))
        assert SLOW["fast"] == H and SLOW["enc"] == 256, "the slow memory's layout does not fit the network: {}".format(SLOW)
        assert a.steps % SLOW["every"] == 0, "--steps {} is not a whole number of the slow memory's ticks ({})".format(a.steps, SLOW["every"])
        assert not HAS_CELLS, "the slow memory is for networks without the learned map cells (v8)"
        print(slowmem_.describe(SLOW) + ("" if SLOW_CK is not None else " (new: its door shut)"), flush=True)
    SLOW_SAVE = {"slow": SLOW} if SLOW else {}               # (a checkpoint without the part is as it was)
    LONG = a.long_gamma > 0
    AUX_W = float(a.aux)                                     # (--aux) the lesson's weight. Its output layers are in the network when the
    AUX = AUX_W > 0 or bool(AUX_SAVE)                        # lesson is on, or when the network he resumes from has them (kept as they are)
    AUX_HEADS = tuple(x_ for x_ in a.aux_heads.split(",") if x_)
    assert all(x_ in ("place", "appear", "fight", "items", "target", "strength", "first", "near") for x_ in AUX_HEADS), a.aux_heads
    AUX_Q = tuple(h_ for h_ in ("target", "strength", "first", "near") if AUX_W > 0 and h_ in AUX_HEADS)       # (2026-10-12) the questions asked beside the four,
    AUX_NEW = tuple(h_ for h_ in ("target", "strength", "first", "near") if h_ in AUX_Q or h_ in AUX_CK)        # and their layers in the network (asked, or come with it)
    AUX_NN = dict(target=len(getattr(E_, "INTENTS", ())), strength=4 + len(E_.WEAPONS), first=6,       # their outputs: the intentions; 4 bands + the weapons; 3 + 3;
                  near=2 * len(getattr(E_, "INTENTS", ())))                                            # the intentions twice (the landmark now, later)
    AUX_KO = (("target", 0, AUX_NN["target"]), ("strength", 0, 4), ("strength", 4, AUX_NN["strength"]), ("first", 0, 3), ("first", 3, 6))   # label j: its layer, its outputs
    AUX_KN = tuple(hi_ - lo_ for _, lo_, hi_ in AUX_KO) + (AUX_NN["target"],)                           # the classes of each label (the sixth: the target, enemy unseen)
    aux = None
    if AUX_W > 0:
        AUX_COLS = getattr(E_, "AUX_COLS", None)
        assert AUX_COLS is not None and all(len(f) > 2 and f[2] is not None for f in first), \
            "--aux: the simulator {} gives no info['aux'] (p_b1_env.py)".format(a.env)
        AUX_IX = {k_: i_ for i_, k_ in enumerate(AUX_COLS)}
        aux = np.concatenate([f[2] for f in first])
        fr_ = [int(x_) for x_ in a.aux_frames.split(",")]
        AUX_FR = (min(fr_[0], a.steps), min(fr_[1], a.steps - a.steps // 4), min(fr_[2], a.steps - a.steps // 4))
        AUX_SAVE = dict(aux_heads=dict(place=3, appear=2, fight=4, items=2, place_units=1500.0, angle_degrees=90.0, damage_points=100.0,
                                       item_seconds=40.0, fight_classes=("neither", "frag", "fragged"), frames=AUX_FR, cols=tuple(AUX_COLS)))
        AUX_MI = torch.tensor([0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5], device=dev)   # which label each measure is of
        print("aux: weight {} on {}, {} of its gradient into the shared layers; windows in frames: appears within {}, the fight within {}, "
              "damage over {} (asked: {}; a rollout is {})".format(AUX_W, "+".join(AUX_HEADS), a.aux_trunk, AUX_FR[0], AUX_FR[1], AUX_FR[2],
                                                                   a.aux_frames, a.steps), flush=True)
        if AUX_NEW:
            AUX_SAVE["aux_heads"].update({h_: AUX_NN[h_] for h_ in AUX_NEW})
        if AUX_Q:
            assert all(c_ in AUX_IX for c_ in ("en_target", "en_band", "en_weapon", "mega_take", "red_take")), \
                "--aux-heads {}: the simulator {} has not the columns for them (p_g15_env.py)".format(a.aux_heads, a.env)
            AUX_FW = min(int(a.aux_first_frames), a.steps - a.steps // 4)
            AUX_SAVE["aux_heads"].update(target_classes=tuple(E_.INTENTS), band_edges=tuple(getattr(E_, "AUX_BANDS", ())), weapon_classes=tuple(E_.WEAPONS),
                                         first_classes=("nobody", "he", "another"), first_frames=AUX_FW)
            print("aux: and {}: {} outputs; who takes the big items next within {} frames (asked: {})".format(
                "+".join(AUX_Q), "+".join(str(AUX_NN[h_]) for h_ in AUX_Q), AUX_FW, a.aux_first_frames), flush=True)
        if "near" in AUX_Q:
            assert "en_near" in AUX_IX, "--aux-heads near: the simulator {} has not the column for it (p_g15_near_env.py)".format(a.env)
            AUX_NW = max(1, min(int(a.aux_near_frames), a.steps - a.steps // 4))
            AUX_SAVE["aux_heads"].update(near_classes=tuple(E_.INTENTS), near_frames=AUX_NW)
            print("aux: near: the landmark nearest the enemy now and {} frames on (asked: {})".format(AUX_NW, a.aux_near_frames), flush=True)

    AUX_TAIL, AUX_FRESH = AUX_W > 0 and a.aux_tail, (float(a.aux_fresh) if AUX_W > 0 else 0.0)      # (v0.2.2) the revised guessing game
    AUX_UNSEEN, AUX_MEAS = AUX_W > 0 and a.aux_unseen, AUX_W > 0 and a.aux_measure
    AUX2 = bool(AUX_TAIL or AUX_FRESH > 0 or AUX_UNSEEN)     # the labels are made by aux2_labels
    AUX_BEL = AUX_FRESH > 0 or AUX_MEAS                      # his raw belief inputs are kept frame by frame
    AUX_TW, AUX_TWN, AUX_TAILD, AUX_LIFE, AX2_ST = 0, 0, None, None, {}
    BEL_IX = None
    if AUX_W > 0 and (AUX2 or AUX_MEAS):
        assert 0.0 <= AUX_FRESH <= AUX_BEL_AGE, "--aux-fresh: 0 to {} seconds".format(AUX_BEL_AGE)
        if AUX_TAIL:                                         # the longest window of the questions asked (place, items: none)
            AUX_TW = max(([AUX_FR[0]] if "appear" in AUX_HEADS else []) + ([AUX_FR[1], AUX_FR[2]] if "fight" in AUX_HEADS else [])
                         + ([AUX_FW] if "first" in AUX_Q else []) + ([AUX_NW] if "near" in AUX_Q else []) + [0])
        BEL_IX = None
        if AUX_BEL:                                          # (the v0.2 inputs "the enemy as he believes him": believes, where x 3, how old)
            assert getattr(E_, "N_V02", 0) > 0, "--aux-fresh / --aux-measure: the simulator {} has not v0.2's inputs".format(a.env)
            # (v0.4: the enemy's stack, N_ES, comes last since the belief merge; until 2026-10-16 it was not subtracted here and the
            # five columns read were six to the left of the belief: only the guessing lesson's masks and measures read them)
            o_ = OBS_DIM - getattr(E_, "N_DRIFT", 0) - getattr(E_, "N_EMG", 0) - getattr(E_, "N_PREF", 0) - getattr(E_, "N_RAIM", 0) - getattr(E_, "N_ES", 0) - getattr(E_, "N_B3", 0) - getattr(E_, "N_B2", 0) - E_.N_V02 + E_.V02_GAME + E_.V02_POS
            BEL_IX = np.array([o_, o_ + 1, o_ + 2, o_ + 3, o_ + 8], np.int64)
    BEL_SEEN = [0]

    def bel_check(o):
        """(--aux-fresh, --aux-measure) the belief's columns are where the simulator puts them: "believes" is 0 or 1; with no
        belief the place reads 0 and the age 1 (checked on the first update's frames)"""
        bo_ = o[:, BEL_IX]
        nb_ = bo_[:, 0] == 0
        assert np.isin(bo_[:, 0], (0.0, 1.0)).all() and np.abs(bo_[nb_][:, 1:4]).max(initial=0.0) == 0.0 and (bo_[nb_][:, 4] == 1.0).all(), \
            "the belief's columns {} are not where the simulator puts them".format(BEL_IX.tolist())
        BEL_SEEN[0] += len(o)
    if BEL_IX is not None:
        bel_check(obs)
        print("aux (v0.2.2): tail {} ({} frames), fresh {} s, unseen {}, measure {}".format(bool(AUX_TAIL), AUX_TW, AUX_FRESH, bool(AUX_UNSEEN),
                                                                                           bool(AUX_MEAS)), flush=True)

    # (--track, --info-pay; v0.3.11, docs/v0.3.11/INFO_PAY.md) the belief readout (sim/track.py): its layout comes with the
    # network he resumes from, or is made new when the lesson or the pay is asked for (its last layer at zero). Off: nothing here
    import track as track_
    TRK_PARTS = track_.parse_weights(a.track_parts)
    # (--belief, v0.4.0 A; sim/belief.py) the belief memory: its layout comes with the network, or is made new by --belief (its
    # own start). With it the readout reads the belief's state, never his memory
    import belief as belief_
    BEL_L = BEL_CK
    if BEL_L is None and a.belief > 0:
        BEL_L = belief_.layout(OBS_DIM, hid=a.belief, every=a.belief_every)
    BEL = BEL_L is not None
    BK = int(BEL_L["every"]) if BEL else 0
    if BEL:
        assert int(BEL_L["obs_dim"]) == OBS_DIM, "the belief reads {} inputs, the simulator has {}".format(BEL_L["obs_dim"], OBS_DIM)
        assert a.belief <= 0 or (int(a.belief) == int(BEL_L["hid"]) and int(a.belief_every) == BK), \
            "--belief {} --belief-every {}: the network's belief is {} every {}".format(a.belief, a.belief_every, BEL_L["hid"], BK)
        assert a.steps % BK == 0, "--steps {} is not a whole number of the belief's ticks ({})".format(a.steps, BK)
        assert not HAS_CELLS, "--belief: not for networks with the learned map cells (v8)"
        assert a.info_pay <= 0, "--info-pay with --belief: not built (the pay would score the belief's readout; v0.4.0 A runs with it 0)"
        assert TRK_CK is None or TRK_CK.get("src") == "belief", \
            "the network's readout reads his memory: give it a fresh one on the belief (tools/belief_init.py add --replace-track)"
        print(belief_.describe(BEL_L) + (" (from the network)" if BEL_CK is not None else " (new)"), flush=True)
    else:
        assert TRK_CK is None or TRK_CK.get("src") != "belief", "the network's readout reads a belief memory it does not have"
    BEL_SAVE = {"belief": BEL_L} if BEL else {}
    BEL_LR = float(a.belief_lr_scale) if a.belief_lr_scale >= 0 else float(a.track_lr_scale)
    TRK_L = TRK_CK if TRK_CK is not None else (track_.layout(weights=TRK_PARTS) if (a.track > 0 or a.info_pay > 0 or BEL) else None)
    TRK = TRK_L is not None                                  # the readout's layers are in the network (kept as they are while off)
    TRK_ON = TRK and (a.track > 0 or a.info_pay > 0)         # the truth is read from the simulators (TRACK_TRUTH=1)
    if TRK:
        TRK_L = dict(TRK_L, weights=TRK_PARTS)
    if BEL:                                                  # (the layout says what the readout reads: tools and checks can tell)
        TRK_L = dict(TRK_L, src="belief", inp=int(BEL_L["hid"]))
        if a.track_trunk > 0:
            print("track: --track-trunk {} is not used with --belief (the lesson reaches the belief and the readout only)".format(a.track_trunk), flush=True)
    TRK_IN = int(BEL_L["hid"]) if BEL else H                 # what the readout reads: the belief's state, or his memory
    TRK_EVERY = BK if BEL else a.info_every                  # the frames the readout is scored on in the rollout (the counters)
    TRK_SAVE = {"track": TRK_L} if TRK else {}
    import track_z as trz_
    import zonemap as zonemap_
    TRZ_PARTS = trz_.parse_weights(a.track_z) if a.track_z else None
    TRZ_L = TRZ_CK if TRZ_CK is not None else (trz_.layout(weights=TRZ_PARTS, inp=int(BEL_L["hid"])) if (a.track_z and BEL) else None)
    assert TRZ_L is None or BEL, "--track-z: with --belief (it reads the belief's state)"
    TRZ = TRZ_L is not None                                  # the part's layers are in the network
    if TRZ and TRZ_PARTS is None:
        TRZ_PARTS = dict(TRZ_L["weights"])
    TRZ_ON = TRZ and TRK_ON and bool(a.track_z)              # its lesson and counters (the truth: TRACK_Z=1)
    if TRZ:
        TRZ_L = dict(TRZ_L, weights=TRZ_PARTS)
        TRK_SAVE["track_z"] = TRZ_L
    TRZ_LR = float(a.track_z_lr_scale) if a.track_z_lr_scale >= 0 else float(a.track_lr_scale)
    import btoken as btoken_                                 # (v0.4.1) the brain's token (sim/btoken.py) and the readout ahead (sim/ahead.py)
    import ahead as ahead_
    import control as control_                               # (v0.4.3) the readout "in control" (sim/control.py)
    BTOK_L = BTOK_CK
    if BTOK_L is None and a.btoken:
        assert BEL and TRK, "--btoken: with --belief and its readout (--track)"
        BTOK_L = btoken_.layout(TRK_L, TRZ_L, BK, btoken_.seen_col(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUTS.csv")))
    BTOK = BTOK_L is not None                                # the token's layers are in the network
    BTOK_ON = BTOK and bool(a.btoken)                        # it is made and fed in this run's rollouts
    if BTOK:
        assert ATT is not None, "--btoken: the network has no attention part"
        ATT = dict(ATT, btok=int(BTOK_L["dim"]))
        BTOK_G = [float(a.btoken_gate) if a.btoken_gate >= 0 else float(BTOK_L.get("gate", 0.0))]
        if not BTOK_ON:
            BTOK_G[0] = 0.0
        print(btoken_.describe(dict(BTOK_L, gate=BTOK_G[0])) + (" (from the network)" if BTOK_CK is not None else " (new: shut)")
              + ("" if BTOK_ON else ": NOT fed in this run (--btoken 0): the gate stays shut"), flush=True)
    else:
        BTOK_G = [0.0]
    import rule_fade as rfade_                               # (v0.4.2a) the rule fade (sim/rule_fade.py)
    RF_L = RF_CK
    RF_READ = bool(getattr(E_, "BRAIN_READ", False))         # (BRAIN_READ=1) the simulator's readers on the brain's answer, by the same gate
    if RF_L is None and a.rule_fade:
        RF_L = rfade_.layout(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUTS.csv"),
                             readers=RF_READ, blind=bool(getattr(E_, "BLIND_BRAIN", False)))
    RF = RF_L is not None                                    # the network has the entry
    RF_ON = RF and bool(a.rule_fade)                         # the gate moves in this run (off: g 0, the network without the fade)
    if RF:
        assert max(RF_L["cols"]) < OBS_DIM, "--rule-fade: the columns are past the network's inputs"
        RF_L = dict(RF_L, readers=RF_READ, blind=bool(getattr(E_, "BLIND_BRAIN", False)))    # (what this run's simulator does)
        RF_G = [float(a.rule_fade_g) if a.rule_fade_g >= 0 else float(RF_L.get("g", 0.0))]
        if not RF_ON:
            RF_G[0] = 0.0
        print(rfade_.describe(dict(RF_L, g=RF_G[0])) + (" (from the network)" if RF_CK is not None else " (new: shut)")
              + ("" if RF_ON else ": NOT moved in this run (--rule-fade 0): g stays 0"), flush=True)
        if RF_READ:
            assert RF_ON and BTOK_ON, "BRAIN_READ=1: with --rule-fade 1 and the brain's token fed (--btoken 1): the answer the simulators read is the token's"
    else:
        RF_G = [0.0]
        assert not RF_READ, "BRAIN_READ=1 without --rule-fade: no brain's answer goes to the simulators"
    AH_PARTS = ahead_.parse_weights(a.ahead) if a.ahead else None
    AH_L = AH_CK
    if AH_L is None and a.ahead:
        assert BEL, "--ahead: with --belief (it reads the belief's state)"
        AH_L = ahead_.layout(ACTION_DIMS[I_HEAD], inp=int(BEL_L["hid"]), weights=AH_PARTS,
                             race="race_me_mh" in tuple(getattr(E_, "AUX_COLS", ())))      # (the item race: TRACK_RACE=1)
    AH = AH_L is not None
    if AH and AH_PARTS is None:
        AH_PARTS = dict(AH_L["weights"])
    AH_ON = AH and TRK_ON and bool(a.ahead)
    AH_LR = float(a.ahead_lr_scale) if a.ahead_lr_scale >= 0 else float(a.track_lr_scale)
    if AH:
        AH_L = dict(AH_L, weights=AH_PARTS)
        TRK_SAVE["ahead"] = AH_L
        print("ahead (v0.4.1): the brain's readout of the enemy in {} s, what he goes for ({}), when he appears; {}; lesson {} rising over {} min, "
              "its layers at {} times --lr".format(AH_L["horiz"], AH_L["n_target"], "from the network" if AH_CK is not None else "new (its last layer at zero)",
                                                    AH_PARTS if AH_ON else "off", a.ahead_warm, AH_LR), flush=True)
    if CTL_CK is not None and int(CTL_CK.get("version", 1)) != 2:  # (v0.4.2b) a one-readout layout of branch v043-control: not carried over
        print("control: the network's readout (layout version {}) is left out; new readouts are made".format(CTL_CK.get("version", 1)), flush=True)
        CTL_CK = None
    CTL_L = CTL_CK                                           # (--control, v0.4.3) the readouts "in control": their layout, from the network or new
    if CTL_L is None and a.control > 0:
        assert BEL and TRK_ON, "--control: with --belief and --track (it reads the belief's state)"
        assert all(c_ in tuple(getattr(E_, "AUX_COLS", ())) for c_ in control_.COLS), "--control: the simulator gives no ctl_ columns (CONTROL_TRUTH=1)"
        CTL_L = control_.layout(srcs=a.control_src, bel=int(BEL_L["hid"]), mem=H, hid=a.control_hid, every=a.control_every,
                                horizon_frames=int(E_.CONTROL_D), tick=int(BEL_L["every"]))
    CTL = CTL_L is not None
    CTL_ON = CTL and a.control > 0
    if CTL_ON:
        assert int(CTL_L["horizon"]) == int(E_.CONTROL_D) and int(CTL_L["tick"]) == int(BEL_L["every"]), \
            "--control: the readout was made for a horizon of {} frames and ticks of {}; the simulator's CONTROL_D is {}".format(
                CTL_L["horizon"], CTL_L["tick"], E_.CONTROL_D)
        assert tuple(control_.names(CTL_L)) == control_.parse_srcs(a.control_src), \
            "--control-src {}: the network's readouts are {}".format(a.control_src, control_.names(CTL_L))
        assert int(CTL_L["bel"]) == int(BEL_L["hid"]) and int(CTL_L["mem"]) in (0, H), "--control: the readouts' widths do not fit the network"
    if CTL:
        TRK_SAVE["control"] = CTL_L
        print("control (v0.4.3/v0.4.2b): the brain's readouts 'in control' ({}), {}; lesson {} (rate {} x weight, rising over {} min "
              "from minute {}), states every {} ticks over {} frames ({} wide)".format(
                  ", ".join("{} {} -> {} -> {}".format(r_["name"], r_["inp"], r_["hid"], r_["d"]) for r_ in CTL_L["readouts"]),
                  "from the network" if CTL_CK is not None else "new (their last layers at zero)", a.control if CTL_ON else "off",
                  a.control_lr, a.control_warm, "this process's start" if a.control_start < 0 else a.control_start,
                  CTL_L["every"], CTL_L["horizon"], CTL_L["width"]), flush=True)
    BA_SEND = bool(getattr(E_, "BLIND_AHEAD", False))     # (v0.4.3, BLIND_AHEAD) the readout ahead's places go with the brain's answer
    if BA_SEND:
        assert RF_READ and AH and bool(getattr(E_, "BLIND_BRAIN", False)), \
            "BLIND_AHEAD=1: with BRAIN_READ=1, BLIND_BRAIN=1 and the readout ahead (--ahead): its places are what the waiver reads"
        print("blind ahead (v0.4.3): the out-of-view shot cost also waived where the brain says the enemy will be in {} s "
              "(a life on the brain; seen up to {} s ago)".format(AH_L["horiz"], getattr(E_, "BLIND_AHEAD_T", "?")), flush=True)
    TRZ_TC, TRZ_MAPI = None, None
    TRZ_PRIOR = np.zeros((len(zonemap_.MAPS), trz_.MAX_Z))    # (the counters' map prior: how often the enemy stood in each zone, so far)
    TRK_IX, TRK_TC, TRK_K = None, None, [0.0, 0.0]           # (the truth's columns; the pay's k and the lesson's weight of this rollout)
    if TRK_ON:
        assert groups == [2], "--track / --info-pay: duels only (--group 2): the pay pairs seat i with seat i ^ 1"
        cols_ = tuple(getattr(E_, "AUX_COLS", ()))
        need_ = track_.COLS + ("trk_on", "en_in_view", "unseen_s", "bel_ok", "bel_fwd", "bel_left", "bel_up", "bel_age", "es_stack")
        assert all(c_ in cols_ for c_ in need_) and all(len(f) > 2 and f[2] is not None for f in first), \
            "--track / --info-pay: the simulator {} gives no TRACK_TRUTH columns (set TRACK_TRUTH=1)".format(a.env)
        TRK_IX = {k_: i_ for i_, k_ in enumerate(cols_)}
        TRK_TC = [TRK_IX[c_] for c_ in track_.COLS]
        if TRZ_ON:                                           # (--track-z) its truth: TRACK_Z=1
            assert all(c_ in cols_ for c_ in trz_.COLS + ("zone_map", "zone_seen", "x", "y", "z", "yaw")), \
                "--track-z: the simulator {} gives no TRACK_Z columns (set TRACK_Z=1)".format(a.env)
            TRZ_TC = [TRK_IX[c_] for c_ in trz_.COLS]
            print("track_z (v0.4.0): the readout's second part {} ({} -> {} -> {}: zones over at most {}, speed, direction over 0.2 s); "
                  "lesson parts {} rising over {} min, its layers at {} times --lr".format(
                      "from the network" if TRZ_CK is not None else "new (its last layer at zero)", TRZ_L["inp"], TRZ_L["hid"], TRZ_L["d"],
                      trz_.MAX_Z, TRZ_PARTS, a.track_z_warm, TRZ_LR), flush=True)
        if aux is None:
            aux = np.concatenate([f[2] for f in first])
        print("track (v0.3.11): the belief readout {} ({} -> {} -> {}); lesson {} (memory share {}, warm {} min), parts {}; info pay {} "
              "every {} frames (after {} min, rising over {} min){}".format(
                  "from the network" if TRK_CK is not None else "new (its last layer at zero)", TRK_IN, TRK_L["hid"], TRK_L["d"], a.track,
                  a.track_trunk if not BEL else "none (--belief)", a.track_warm, TRK_PARTS, a.info_pay, a.info_every, a.info_delay, a.info_warm,
                  "" if a.track_start < 0 else "; counted from minute {}".format(a.track_start)), flush=True)
        if BEL:
            print("track (v0.4.0 A): the readout reads the belief memory's state ({}); lesson and counters on its ticks (every {} frames); "
                  "the belief's and the readout's layers learn at {} and {} times --lr".format(TRK_IN, BK, BEL_LR, a.track_lr_scale), flush=True)
    elif TRK:
        print("track (v0.3.11): the network's belief readout is kept as it is (no lesson, no pay)", flush=True)

    HEADL = HEAD_CK                                          # (--head) the network's own head, or a new one with its links at zero
    if HEADL is not None or a.head:
        import head as head_
        if HEADL is None:
            HA_ = head_.as_layout(a.head) if a.head != "default" else {}
            HA_ = {k_: v_ for k_, v_ in HA_.items() if k_ != "version"}
            HA_.update(fast=H, enc=256, n_target=ACTION_DIMS[I_HEAD], n_way=ACTION_DIMS[W_HEAD] if W_HEAD >= 0 else 1,
                       aux=(dict(place=3, appear=2, fight=4, items=2, **{h_: AUX_NN[h_] for h_ in AUX_NEW}) if AUX else {}))
            HEADL = head_.layout(**HA_)
        if a.head_store_half and not HEADL.get("store_half"):
            HEADL = dict(HEADL, store_half=1)
        assert HEADL["fast"] == H and HEADL["enc"] == 256, "the head's layout does not fit the network: {}".format(HEADL)
        assert HEADL["n_target"] == ACTION_DIMS[I_HEAD] and (W_HEAD < 0 or HEADL["n_way"] == ACTION_DIMS[W_HEAD]), \
            "the head's target and way ({}, {}) do not fit the outputs {}".format(HEADL["n_target"], HEADL["n_way"], ACTION_DIMS)
        assert a.steps % HEADL["every"] == 0, "--steps {} is not a whole number of the head's ticks ({})".format(a.steps, HEADL["every"])
        assert not SLOW, "the head and the slow memory together: not built"
        assert not HAS_CELLS, "the head is for networks without the learned map cells (v8)"
        assert a.demo_coef <= 0, "--demo-coef with the head: the demo loss steps his memory without the plan (not built)"
        print(head_.describe(HEADL) + ("" if HEAD_CK is not None else " (new: its links at zero)"), flush=True)
    HEAD_SAVE = {"head": HEADL} if HEADL else {}             # (a checkpoint without the part is as it was)
    H2L = H2_CK                                              # (--head2, v0.4.3) the network's own strategy head, or a new one at zero
    if H2L is None and a.head2:
        import head2 as head2_
        assert BEL and TRK, "--head2: with the brain (--belief) and its readout (--track)"
        H2L = head2_.layout(brain=int(BEL_L["hid"]), trk=int(TRK_L["d"]), trz=int(TRZ_L["d"]) if TRZ else 0, ahead=int(AH_L["d"]) if AH else 0,
                            ctrl=a.head2_ctrl, hands=H, enc=256, size=a.head2_size, inp=a.head2_inp, plan=a.head2_plan,
                            n_target=ACTION_DIMS[I_HEAD], every=BK, gamma=a.head2_gamma, on={p_: 0 for p_ in a.head2_off.split(",") if p_})
    H2 = H2L is not None
    if H2:
        import head2 as head2_
        assert BEL and TRK, "the strategy head reads the brain (--belief) and its readout (--track)"
        w_ = H2L["widths"]
        assert int(H2L["every"]) == BK and a.steps % BK == 0, "the strategy head ticks with the brain ({} frames; --steps a whole number of them)".format(BK)
        assert w_["brain"] == int(BEL_L["hid"]) and w_["trk"] == int(TRK_L["d"]) and w_["hands"] == H and int(H2L["enc"]) == 256, \
            "the strategy head's inputs do not fit the network: {}".format(w_)
        assert w_["trz"] == (int(TRZ_L["d"]) if TRZ else 0) and w_["ahead"] == (int(AH_L["d"]) if AH else 0), \
            "the strategy head reads the readouts {} / {}, the network has {} / {}".format(w_["trz"], w_["ahead"], TRZ_L and TRZ_L["d"], AH_L and AH_L["d"])
        assert int(H2L["n_target"]) == ACTION_DIMS[I_HEAD], "the strategy head's bias ({}) does not fit the intention ({})".format(H2L["n_target"], ACTION_DIMS[I_HEAD])
        assert not HEADL and not SLOW and not HAS_CELLS, "the strategy head with --head, --slow-mem or map cells: not built"
        assert a.demo_coef <= 0, "--demo-coef with the strategy head: the demo loss steps his memory without its plan (not built)"
        print(head2_.describe(H2L) + ("" if H2_CK is not None else " (new: its plan_in and target at zero)"), flush=True)
    if H2 and a.head2_ctrl_src:                              # (--head2-ctrl-src) the ctrl slot's source, kept in the head's layout
        assert a.head2_ctrl_src in head2_.CTRL_SRCS, "--head2-ctrl-src: one of {}".format(head2_.CTRL_SRCS)
        H2L = dict(H2L, ctrl_src=a.head2_ctrl_src)
    if H2 and head2_.ctrl_src(H2L) != "none":
        assert CTL and head2_.ctrl_src(H2L) in control_.names(CTL_L),             "the strategy head's ctrl slot reads the 'in control' readout {!r}: the network has {}".format(
                head2_.ctrl_src(H2L), control_.names(CTL_L) if CTL else "none (--control 1 --control-src ...)")
        assert int(H2L["widths"]["ctrl"]) == len(control_.OUTS), "the ctrl slot is {} wide; the readouts give {}".format(H2L["widths"]["ctrl"], len(control_.OUTS))
    if H2:
        print("head2: its ctrl slot reads {}".format("zeros" if head2_.ctrl_src(H2L) == "none" else
                                                   "the 'in control' readout {!r} (chances - 0.5, detached)".format(head2_.ctrl_src(H2L))), flush=True)
    H2_SAVE = {"head2": H2L} if H2 else {}                   # (a checkpoint without the part is as it was)
    H2_PG_ = [a.head2_pg, a.head2_plan_grad, 1.0]            # (--head2) its lesson's weight, the plan's gradient into it, live H2_PG's factor
    # (--legs-feat, --legs-guide; one movement network, steps 3 and 4: sim/legs_unify.py) the network's own parts, or new
    # ones at zero; a flag adds its part to a network that has none, a resume keeps what the network has
    import legs_unify as LU_
    UNI = LU_.as_layout(UNI_CK)
    if UNI is not None or a.legs_feat or a.legs_guide or a.legs_gate or a.legs_residual:
        assert LEGS_IN, "--legs-feat / --legs-guide: his legs' branch must be inside (LEGS_IN=1 with LEGS=1 and --teacher)"
        assert not HAS_CELLS, "--legs-feat / --legs-guide: not for networks with the learned map cells (v8)"
        import movement_env as M_
        UNI = LU_.layout(ACTION_DIMS, E_.TURN, M_.TURN_BINS, (UNI or {}).get("feat", 0) or a.legs_feat,
                         (UNI or {}).get("guide", 0) or a.legs_guide, gate=(UNI or {}).get("gate", 0) or a.legs_gate,
                         residual=(UNI or {}).get("residual", 0) or a.legs_residual, mem=H)
        assert tuple(UNI["outs"]) == tuple(L_TAKES), (UNI["outs"], L_TAKES)
        print(LU_.describe(UNI) + ("" if UNI_CK is not None else " (new: at zero)"), flush=True)
    UNI_FEAT, UNI_GUIDE = bool(UNI and UNI["feat"]), bool(UNI and UNI["guide"])
    UNI_GATE, UNI_RES = bool(UNI and UNI.get("gate")), bool(UNI and UNI.get("residual"))      # (v0.3.4 A, B)
    UNI_ON = UNI_FEAT or UNI_GUIDE or UNI_GATE or UNI_RES
    NO_SW = bool(a.no_switch)                                # (--no-switch, v0.3.5) his legs never drive: the switch is drawn as before and
    #                                                          set off for his seats and the league's snapshots (an anchor, the control, keeps
    #                                                          its own); the simulators are not told (NO_SWITCH there would take the control's
    #                                                          legs too); the checkpoint's env_vars carry NO_SWITCH=1 for the checks and plugins
    assert not NO_SW or (a.legs_learn > 0 and (UNI_FEAT or UNI_GATE)), \
        "--no-switch: with --legs-learn and --legs-feat or --legs-gate (the branch learns only through them then)"
    assert not (NO_SW and a.switch_fade), "--no-switch: --switch-fade has nothing left to fade"
    assert not UNI_RES or a.legs_learn > 0, "--legs-residual: with --legs-learn (its parts learn from the legs' draws, as the branch)"
    UNI_SAVE = {"legs_unify": UNI} if UNI_ON else {}
    UNI_PFX = ("legs_door.", "legs_guide", "legs_gate.", "legs_motor.", "legs_res_a.", "legs_res.")                  # (their names: in the main optimiser group, clipped on their own)
    UGM = None                                               # (--legs-guide) the mapping matrices on the device (made with the network)
    FADE = [0.0]                                             # (--switch-fade) the bias taken off the switch's "legs" choice now
    SW_ON = int(np.sum(ACTION_DIMS[:L_HEAD])) + 1 if L_HEAD >= 0 else -1
    HD_I0 = sum(ACTION_DIMS[:I_HEAD])                        # (--head) where the intention's and the way's logits begin
    HD_W0 = sum(ACTION_DIMS[:W_HEAD]) if W_HEAD >= 0 else -1

    def head_logits(lg, ta, wa):
        """(--head) his logits with the head's target and way added to the intention's and the way's"""
        parts = [lg[..., :HD_I0], lg[..., HD_I0:HD_I0 + ta.shape[-1]] + ta]
        if HD_W0 >= 0:
            parts += [lg[..., HD_I0 + ta.shape[-1]:HD_W0], lg[..., HD_W0:HD_W0 + wa.shape[-1]] + wa, lg[..., HD_W0 + wa.shape[-1]:]]
        else:
            parts += [lg[..., HD_I0 + ta.shape[-1]:]]
        return torch.cat(parts, -1)

    class Policy(nn.Module):
        def __init__(self):
            super().__init__()
            self.attn = attn_.make_module(ATT, 256) if ATT is not None else None
            self.door_open = True                                # (a league opponent whose door is shut skips the attention part)
            if LONG or ATT is not None:                          # (v0.2) the pay for items and stack, counted as far as the fight's and two minutes ahead
                self.v2 = nn.Linear(H, 2)
                nn.init.zeros_(self.v2.weight)
                nn.init.zeros_(self.v2.bias)
            if HAS_CELLS:
                self.cell = nn.Embedding(E_.MAX_CELLS, CELL_DIM)
                nn.init.normal_(self.cell.weight, 0.0, 0.1)
            self.enc = nn.Sequential(nn.Linear(OBS_DIM - 2 + 2 * CELL_DIM if HAS_CELLS else OBS_DIM, 256), nn.Tanh(),
                                     nn.Linear(256, 256), nn.Tanh())
            self.gru = nn.GRUCell(256, H)
            self.pi = nn.Linear(H, sum(ACTION_DIMS))
            if LEGS_IN:                                          # (LEGS_IN) his legs' branch: its own inputs, no memory
                self.legs = nn.Sequential(nn.Linear(LEGS_D, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh(), nn.Linear(256, 17))
            self.v = nn.Linear(H, 1)
            self.slow = slowmem_.make_module(SLOW) if SLOW else None     # (--slow-mem) sim/slowmem.py: inp, gru, door (zeros)
            if AUX:                                              # (--aux) from his memory: the unseen enemy's place (3), the angles to
                self.aux = nn.Module()                           # where he next appears (2), the fight's end (3 classes) and its damage
                self.aux.place, self.aux.appear = nn.Linear(H, 3), nn.Linear(H, 2)     # (1), the seconds to the mega and the red armor
                self.aux.fight, self.aux.items = nn.Linear(H, 4), nn.Linear(H, 2)      # (2). (Not a ModuleDict: "items" is a name of its own there.)
                for l_ in self.aux.children():                   # They start at nothing: until they have learnt something the lesson
                    nn.init.zeros_(l_.weight)                    # does not move his memory
                    nn.init.zeros_(l_.bias)
                for h_ in AUX_NEW:                               # (2026-10-12) what the enemy goes for (the intentions), his stack's band
                    l_ = nn.Linear(H, AUX_NN[h_])                # and weapon (4 + 9), who takes the mega and the red armor next (3 + 3):
                    nn.init.zeros_(l_.weight)                    # only the ones named in --aux-heads or in the network he resumes from
                    nn.init.zeros_(l_.bias)
                    setattr(self.aux, h_, l_)
            if TRK:                                              # (--track, v0.3.11) the belief readout from his memory (sim/track.py):
                self.track = track_.make_module(TRK_IN, TRK_L)   # its last layer at zero, made without a draw of the random stream
            if BEL:                                              # (--belief, v0.4.0 A) the belief memory: its own random stream
                self.belief = belief_.make_module(BEL_L)
            if TRZ:                                              # (--track-z) the readout's second part: its own random stream,
                self.trackz = trz_.make_module(int(TRZ_L["inp"]), TRZ_L)    # its last layer at zero
            if AH:                                               # (--ahead, v0.4.1) the readout of what comes next: its own stream, last layer at zero
                self.ahead = ahead_.make_module(int(AH_L["inp"]), AH_L)
            if CTL:                                              # (--control, v0.4.3) the readout "in control": its own stream, last layer at zero
                self.control = control_.make_module(CTL_L)
            if ORDER:                                            # (--ordered-heads) a table a link: a row for each choice before, at zero
                self.order = nn.Module()
                for p_, c_ in ORDER:
                    t_ = nn.Embedding(ACTION_DIMS[p_], ACTION_DIMS[c_])
                    nn.init.zeros_(t_.weight)
                    setattr(self.order, "t{}".format(c_), t_)
            if HEADL:                                            # (--head) sim/head.py; plan_in, target, way, win, aux at zero
                self.head = head_.make_module(HEADL)
                self.head_open = True                            # (a league opponent whose head is shut skips it)
            if UNI_FEAT:                                         # (--legs-feat) the legs' features into his fast GRU, at zero
                with torch.random.fork_rng(devices=[]):          # (made without a draw: the random stream after it is the one without)
                    self.legs_door = nn.Linear(UNI["hid"], UNI["enc"])
                nn.init.zeros_(self.legs_door.weight)
                nn.init.zeros_(self.legs_door.bias)
            if UNI_GUIDE:                                        # (--legs-guide) a weight per guided output, at zero
                self.legs_guide = nn.Parameter(torch.zeros(len(UNI["outs"])))
            with torch.random.fork_rng(devices=[]):              # (v0.3.4 A, B: made without a draw)
                if UNI_GATE:                                     # (--legs-gate) g(h) per guided output, the motor layer
                    self.legs_gate = nn.Linear(H, len(UNI["outs"]))
                    self.legs_motor = nn.Linear(UNI["hid"], UNI["motor"])
                if UNI_RES:                                      # (--legs-residual) a(h) per choice of the legs, W h on their 17
                    self.legs_res_a = nn.Linear(H, len(UNI["bdims"]))
                    self.legs_res = nn.Linear(H, int(sum(UNI["bdims"])))
            for n_ in ("legs_gate", "legs_motor", "legs_res_a", "legs_res"):
                if getattr(self, n_, None) is not None:
                    nn.init.zeros_(getattr(self, n_).weight)
                    nn.init.zeros_(getattr(self, n_).bias)
            self.fade = None                                     # (--switch-fade) the learner's: set after it is made
            self.rfg = 0.0                                       # (--rule-fade, v0.4.2a) the gate: a plain number, not a weight (the
            self.rf_m = None                                     # checkpoint's "rule_fade" carries it); the mask made for it
            self.h2_open = H2                                    # (--head2) a league network whose head is shut (or none) skips it
            if H2:                                               # (--head2, v0.4.3) sim/head2.py: plan_in and target at zero, the gate a buffer
                self.head2 = head2_.make_module(H2L)

        def hx(self, x):
            """(--rule-fade) the inputs as the hands read them: the rule-made columns times (1 - rfg); x itself at 0"""
            g_ = float(self.rfg)
            if not RF or not g_ > 0:
                return x
            if self.rf_m is None or self.rf_m[0] != g_ or self.rf_m[1].device != x.device:
                m_ = torch.ones(x.shape[-1], dtype=torch.float32)
                m_[torch.as_tensor(RF_L["cols"], dtype=torch.long)] = float(np.float32(1.0 - g_))
                self.rf_m = (g_, m_.to(x.device))
            return x * self.rf_m[1].to(x.dtype)

        def legs_comb(self, lgl, z):
            """(--legs-residual) the legs' logits his legs draw from: (1 - a(z)) x the branch's + W z; the branch's alone without"""
            return LU_.t_residual(self.legs_res_a, self.legs_res, lgl, z) if UNI_RES else lgl

        def out_(self, lg, z, gfn):
            """his logits: the parts that read his memory (--legs-guide, --legs-gate) and the switch's fade added"""
            if gfn is not None:
                lg = lg + gfn(z)
            if self.fade is not None:
                lg = lg - self.fade
            return lg

        def uni_parts(self, xl):
            """(--legs-feat, --legs-guide) for the branch's inputs xl [..., its inputs]: (what legs_door adds to his fast
            GRU's input or None, what the guide adds to his logits or None); the branch's numbers detached"""
            if not UNI_ON or xl is None:
                return None, None
            h2, lgl = LU_.t_branch(self.legs, xl, grad=NO_SW)  # (--no-switch: under the gradient, the branch learns through them)
            ok = LU_.t_way(xl)
            dadd = self.legs_door(h2) * ok[..., None] if UNI_FEAT else None
            if not (UNI_GUIDE or UNI_GATE):
                return dadd, None

            def gfn(z):                                          # (what the guide and the gate add to his logits, from his memory z)
                add = UGM.add(self.legs_guide, lgl, ok) if UNI_GUIDE else None
                if UNI_GATE:
                    g_ = UGM.add(self.legs_gate(z), lgl, ok) + UGM.place(self.legs_motor(h2) * ok[..., None])
                    add = g_ if add is None else add + g_
                return add
            return dadd, gfn

        def step(self, x, h, f=None, sm=None, hd=None, ev=None, xl=None, bt=None, g2=None):
            dadd, gadd = self.uni_parts(xl)                      # (--legs-feat, --legs-guide; xl: the branch's inputs of this frame)
            x = self.hx(x)                                       # (--rule-fade) the hands' inputs (the brain is given its own, unfaded)
            if HAS_CELLS:
                ids = x[:, -2:].long().clamp(0, E_.MAX_CELLS - 1)   # the last two inputs are cell numbers, not values
                x = torch.cat([x[:, :-2], self.cell(ids[:, 0]), self.cell(ids[:, 1])], 1)
            e = self.enc(x)
            if self.attn is not None and (f is not None or self.door_open):
                e = e + ((self.attn(x, hm=h, bt=bt) if ATT_MEM else self.attn(x, bt=bt)) if f is None else f)   # what the door lets through, added to
                #                                                  the old encoder's (--attn-mem-query: h is his memory of the frame before)
            if hd is not None:                                   # (--head) his fast GRU reads the plan; the head ticks on its frames
                h = self.gru(e + self.head.plan_in(hd.plan) if dadd is None else e + self.head.plan_in(hd.plan) + dadd, h)
                _, ta_, wa_ = head_.live(self.head, hd, e, h, ev)
                self.zl = h
                lg_ = head_logits(self.pi(h), ta_, wa_)
                return self.out_(lg_, h, gadd), self.v(h).squeeze(-1), h
            ein_ = e if dadd is None else e + dadd               # (--legs-feat: only his fast GRU reads the legs' features)
            if g2 is not None:                                   # (--head2) the strategy head's plan into his fast GRU's input
                ein_ = ein_ + g2[0]
            h = self.gru(ein_, h)
            if sm is None or self.slow is None:
                self.zl = h                                      # (what the outputs read: his memory, or with the slow one)
                lg_ = self.pi(h)
                if g2 is not None:                               # (--head2) ... and its bias on his intention's logits
                    lg_ = head2_.add_bias(lg_, g2[1], HD_I0)
                return self.out_(lg_, h, gadd), self.v(h).squeeze(-1), h
            z = slowmem_.live(self.slow, sm, e, h)               # (--slow-mem) z = h + door(s); the slow GRU ticks on its frames
            self.zl = z
            lg_ = self.pi(z)
            return self.out_(lg_, z, gadd), self.v(z).squeeze(-1), h

    ORDER = None                                             # (--ordered-heads) [(the output before, the output), ...] in the order drawn
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ORDER = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location="cpu").get("ordered")
    if ORDER is None and a.ordered_heads:
        ORDER = [[I_HEAD, W_HEAD], [W_HEAD, L_HEAD], [L_HEAD, 6]]
        assert min(min(p_) for p_ in ORDER) >= 0, "--ordered-heads: the simulator has no way or legs output"
    ORDER = [tuple(int(v_) for v_ in p_) for p_ in ORDER] if ORDER else None
    OFFS = np.concatenate([[0], np.cumsum(ACTION_DIMS)]).astype(int)
    assert not (JE and ORDER and any(V_HEAD in p_ for p_ in ORDER)), "JUMP_EVERY: the vertical key's stored choice can be 3 (not jump): it cannot be in --ordered-heads"
    if ORDER:
        print("ordered heads: " + " -> ".join(str(c_) for c_ in [ORDER[0][0]] + [c_ for _, c_ in ORDER]) + " (each read with the one drawn before)", flush=True)
    ORDER_SAVE = {"ordered": [list(p_) for p_ in ORDER]} if ORDER else {}

    def ord_lg(net, lg, act):
        """(--ordered-heads) his logits with each ordered output's table row of the choice drawn before it added"""
        add = torch.zeros_like(lg)
        for p_, c_ in ORDER:
            add[..., OFFS[c_]:OFFS[c_ + 1]] = getattr(net.order, "t{}".format(c_))(act[..., p_].long())
        return lg + add

    def draw(net, lg):
        """(--ordered-heads) his choices drawn in order -> (the choices, the distributions they were drawn from)"""
        act = torch.stack([d.sample() for d in dists(lg)], -1)
        for p_, c_ in ORDER:
            l_ = lg[..., OFFS[c_]:OFFS[c_ + 1]] + getattr(net.order, "t{}".format(c_))(act[..., p_])
            act[..., c_] = torch.distributions.Categorical(logits=l_).sample()
        return act, dists(ord_lg(net, lg, act))

    class JumpCat(torch.distributions.Categorical):
        """(JUMP_EVERY) the vertical key's distribution (none, jump, crouch) with two more values to score: 3 = "not jump"
        (none or crouch), his choice on a frame where only its jump bit was read; 4 = nothing of it was read (log 1).
        Sampling and entropy are the plain three."""

        def log_prob(self, value):
            v_ = value.long()
            lp_ = self.logits.gather(-1, v_.clamp(0, 2).unsqueeze(-1)).squeeze(-1)
            lp_ = torch.where(v_ == 3, torch.logsumexp(self.logits[..., [0, 2]], -1), lp_)
            return torch.where(v_ == 4, torch.zeros_like(lp_), lp_)

    def dists(logits):
        if JE:
            return [(JumpCat if j_ == V_HEAD else torch.distributions.Categorical)(logits=l) for j_, l in enumerate(logits.split(ACTION_DIMS, -1))]
        return [torch.distributions.Categorical(logits=l) for l in logits.split(ACTION_DIMS, -1)]

    def jump_only(act_v, code_):
        """(JUMP_EVERY) the vertical key's stored choice by the frame's code (1: the hand read it, 2: the jump alone, 0: nothing):
        as drawn, its jump bit (1, or 3 = not jump), or 4 (not read)"""
        return torch.where(code_ == 1, act_v, torch.where(code_ == 2, torch.where(act_v == 1, act_v, torch.full_like(act_v, 3)),
                                                          torch.full_like(act_v, 4)))

    def legs_fwd(net, xl):
        """(LEGS_IN) the branch's logits in full float32 (never under the attention part's half precision, no TF32: a rounded
        sum would change a draw now and then)"""
        with torch.autocast(device_type=dev.type, enabled=False):
            return net.legs(xl.float())

    def legs_lp(lg, raw, dc, lo):
        """(--legs-learn) the branch's log-probability of its own draws raw [..., 4] (-1: it drew nothing) under its logits
        lg [..., 17], counted on the frames his legs moved him (lo) and the branch drew; its three keys only on the frames
        his hand read them (dc), as his own keys. -> (the sum [...], the four distributions, the four masks)"""
        on = lo * (raw[..., 0] >= 0).float()
        ms = [on * dc if k_ else on for k_ in LEGS_KEYS]     # (JUMP_EVERY: its jump between the hand's readings is not counted)
        ds = [torch.distributions.Categorical(logits=l_) for l_ in lg.float().split(LEGS_DIMS, -1)]
        rl = raw.long().clamp(min=0)
        return sum(d_.log_prob(rl[..., j_]) * ms[j_] for j_, d_ in enumerate(ds)), ds, ms

    def load_net(net, sd):
        """a network's weights. Only the layers of --aux may be missing (they stay as they are: fresh in the learner) or
        left over (the lesson is off and they are not in this network)"""
        own_ = net.state_dict()                              # (v0.4.0: a league file's readout of another shape, e.g. v0.3.11's on his
        if any(k_.startswith(BRAIN_PFX) and k_ in own_ and tuple(v_.shape) != tuple(own_[k_].shape) for k_, v_ in sd.items()):
            sd = {k_: v_ for k_, v_ in sd.items() if not k_.startswith(BRAIN_PFX)}   # memory beside one on the belief: left out;
        bad = net.load_state_dict(sd, strict=False)          # the learner's own readout reads every seat)
        odd = [k_ for k_ in list(bad.missing_keys) + list(bad.unexpected_keys) if not k_.startswith("aux.") and not k_.startswith("head.aux.")
               and not k_.startswith(BRAIN_PFX) and not k_.startswith("attn.btok_")]     # (v0.4.1: a file without the brain's token plays it shut)     # (v0.3.11: the belief readout, as the aux layers; v0.4.0: the belief)
        assert not odd, "the network does not fit: {}".format(odd)

    HEAD_SHUT = ("plan_in.", "target.", "way.", "win.", "aux.")      # (--head) the links of a new head: zeros

    if ORDER:                                                # (--ordered-heads) a network without the tables gets them at zero
        load_net4_ = load_net

        def load_net(net, sd):
            if getattr(net, "order", None) is not None and not any(k_.startswith("order.") for k_ in sd):
                sd = dict(sd)
                sd.update({"order." + k_: torch.zeros_like(v_) for k_, v_ in net.order.state_dict().items()})
            load_net4_(net, sd)

    if ATT_MEM:                                              # (--attn-mem-query) a network without the query's layer gets it at zero
        load_net3_ = load_net

        def load_net(net, sd):
            if getattr(net.attn, "mq", None) is not None and "attn.mq.weight" not in sd:
                sd = dict(sd)
                sd["attn.mq.weight"] = torch.zeros_like(net.attn.mq.weight)
                sd["attn.mq.bias"] = torch.zeros_like(net.attn.mq.bias)
            load_net3_(net, sd)

    if HEADL:                                                # (--head) a network without the part (the control, older league files, the
        load_net2_ = load_net                                # start before conversion) gets one with its links at zero: it answers as it did

        def load_net(net, sd):
            if getattr(net, "head", None) is not None and "head.plan_in.weight" not in sd:
                sd = dict(sd)
                for k_, v_ in net.head.state_dict().items():
                    sd["head." + k_] = torch.zeros_like(v_) if k_.startswith(HEAD_SHUT) else v_
            load_net2_(net, sd)
            if getattr(net, "head", None) is not None:       # its head counts only if a link of it is open
                net.head_open = any(float(p_.abs().sum()) > 0 for n_, p_ in net.head.named_parameters()
                                    if n_.startswith(("plan_in.", "target.", "way.")))

    if H2:                                                   # (--head2) a network without the strategy head (the control, older league files,
        load_net9_ = load_net                                # the start before conversion) gets one shut: plan_in, target and the gate at zero

        def load_net(net, sd):
            if getattr(net, "head2", None) is not None and "head2.gate" not in sd:
                sd = dict(sd)
                for k_, v_ in net.head2.state_dict().items():
                    sd["head2." + k_] = torch.zeros_like(v_) if k_.startswith(("plan_in.", "target.", "gate")) else v_
            load_net9_(net, sd)
            if getattr(net, "head2", None) is not None:      # its head counts only if its gate is open and a link of it is not zero
                net.h2_open = bool(float(net.head2.gate) > 0 and any(float(p_.abs().sum()) > 0 for n_, p_ in net.head2.named_parameters()
                                                                     if n_.startswith(("plan_in.", "target."))))

    if SLOW:                                                 # (--slow-mem) a network without the part (the control, older league files, the
        load_net0_ = load_net                                # start before conversion) gets one with its door shut: it answers as it did

        def load_net(net, sd):
            if net.slow is not None and "slow.door.weight" not in sd:
                sd = dict(sd)
                for k_, v_ in net.slow.state_dict().items():
                    sd["slow." + k_] = torch.zeros_like(v_) if k_ == "door.weight" else v_
            load_net0_(net, sd)

    if LEGS_IN:                                              # (LEGS_IN) a network without the branch (the start, the control, an older
        load_net1_ = load_net                                # league file) is given the movement network's

        def load_net(net, sd):
            if getattr(net, "legs", None) is not None and "legs.0.weight" not in sd:
                sd = dict(sd)
                sd.update({k_: torch.from_numpy(np.asarray(v_)) for k_, v_ in LEGS_SD.items()})
            load_net1_(net, sd)

    if UNI_ON:                                               # (--legs-feat, --legs-guide) a network without the parts (the control, older
        load_net7_ = load_net                                # league files, the start before the flag) gets them at zero: it answers as it did

        def load_net(net, sd):
            add_ = {}
            if getattr(net, "legs_door", None) is not None and "legs_door.weight" not in sd:
                add_.update({"legs_door." + k_: torch.zeros_like(v_) for k_, v_ in net.legs_door.state_dict().items()})
            if getattr(net, "legs_guide", None) is not None and "legs_guide" not in sd:
                add_["legs_guide"] = torch.zeros_like(net.legs_guide)
            add_.update({k_: torch.zeros_like(v_) for k_, v_ in net.state_dict().items()        # (v0.3.4 A, B)
                         if k_.startswith(("legs_gate.", "legs_motor.", "legs_res_a.", "legs_res.")) and k_ not in sd})
            load_net7_(net, dict(sd, **add_) if add_ else sd)

    if UNI_GUIDE or UNI_GATE:                                # (--legs-gate maps the legs' choice as the guide does)
        UGM = LU_.GuideMaps(UNI, dev)

    if KA_ON:                                                # (LEGS_KEYS_ADD) a network without the five (the control, older league files,
        load_net8_ = load_net                                # the start before conversion) gets them shut: weights 0, the bias of "my
        KA_O = int(sum(ACTION_DIMS[:KA_HEAD]))               # legs'" at KA_SHUT over "mine"; it answers as it did

        def load_net(net, sd):
            if "pi.weight" in sd and sd["pi.weight"].shape[0] == KA_O:
                sd = dict(sd)
                k_ = 2 * len(KA_COLS)
                b_ = torch.zeros(k_, dtype=sd["pi.bias"].dtype, device=sd["pi.bias"].device)
                b_[0::2] = float(E_.KA_SHUT)
                sd["pi.weight"] = torch.cat([sd["pi.weight"], sd["pi.weight"].new_zeros(k_, sd["pi.weight"].shape[1])], 0)
                sd["pi.bias"] = torch.cat([sd["pi.bias"], b_], 0)
            load_net8_(net, sd)

    if TA_HEAD >= 0:                                         # (LEGS_TURN_ADD) a network without the correction (the control, older league
        load_net5_ = load_net                                # files, the start before conversion) gets it shut: weights 0, the bias of
        TA_O = int(sum(ACTION_DIMS[:TA_HEAD]))               # its 0 at TA_SHUT over the others; it answers as it did

        def load_net(net, sd):
            if "pi.weight" in sd and sd["pi.weight"].shape[0] == TA_O:
                sd = dict(sd)
                k_ = ACTION_DIMS[TA_HEAD]
                b_ = torch.zeros(k_, dtype=sd["pi.bias"].dtype, device=sd["pi.bias"].device)
                b_[0] = float(E_.TA_SHUT)
                sd["pi.weight"] = torch.cat([sd["pi.weight"], sd["pi.weight"].new_zeros(k_, sd["pi.weight"].shape[1])], 0)
                sd["pi.bias"] = torch.cat([sd["pi.bias"], b_], 0)
            load_net5_(net, sd)

    if LEGS_IN:                                              # (LEGS_IN) a branch narrower than the movement network's inputs (a league file
        load_net6_ = load_net                                # of v0.3.1 beside legs with the inputs of a look point, movement_env.N_C2): the
        #                                                      new inputs at zero weight, so it answers as its own legs (tools/legs_look_init.py
        #                                                      also folds the change of the input statistics in; this does not)

        def load_net(net, sd):
            if getattr(net, "legs", None) is not None and "legs.0.weight" in sd and sd["legs.0.weight"].shape[1] < LEGS_D:
                sd = dict(sd)
                w_ = sd["legs.0.weight"]
                sd["legs.0.weight"] = torch.cat([w_, w_.new_zeros(w_.shape[0], LEGS_D - w_.shape[1])], 1)
            load_net6_(net, sd)

    pol = Policy().to(dev)
    if LEGS_IN:
        with torch.no_grad():
            for k_, v_ in LEGS_SD.items():
                pol.state_dict()[k_].copy_(torch.from_numpy(np.asarray(v_)))
        pol.legs.requires_grad_(LEGS_LEARN)                  # stage (a): frozen; (b, --legs-learn): its own optimiser group
    if a.fast_gru:
        # cuDNN's GRU takes TF32 (10-bit products) when allowed, and torch allows it for cuDNN by default: 0.7% off the
        # frame-by-frame step in his memory, 0.5% in the gradients (2026-10-15). Off, it is the old step's to float32
        # rounding. The trainer has no other cuDNN work (the GRUCell and the linear layers are plain matrix products).
        torch.backends.cudnn.allow_tf32 = False
        import warnings
        warnings.filterwarnings("ignore", message="RNN module weights are not part of single contiguous chunk")   # (GRUCell's own four)
        print("fast GRU (B-237): the learning step's memory by the library's GRU over whole sequences{}".format(
            " (not with map cells: those networks keep the frame-by-frame step)" if HAS_CELLS else ""), flush=True)
    with torch.no_grad():                                   # start out mostly keeping the current weapon
        pol.pi.bias[sum(ACTION_DIMS[:6])] += 3.0
    opt = torch.optim.Adam([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("legs.") and not (HEADL and n_.startswith("head."))
                            and not (UNI_ON and n_.startswith(UNI_PFX)) and not n_.startswith(BRAIN_PFX) and not n_.startswith("attn.btok_")
                            and not (H2 and n_.startswith("head2."))],
                           lr=a.lr, eps=1e-5, **({"fused": True} if a.adam_fused else {}))   # (LEGS_IN: not the branch; --head: not the head)
    if HEADL:                                                # (--head) the head in a group of its own at --head-lr-scale of the rate
        opt.add_param_group({"params": list(pol.head.parameters()), "lr": a.lr * a.head_lr_scale, "lr_scale": a.head_lr_scale})
    if UNI_ON:                                               # (--legs-door-lr-scale) legs_door and the guide's weights in a group of their own
        opt.add_param_group({"params": [p_ for n_, p_ in pol.named_parameters() if n_.startswith(UNI_PFX)],
                             "lr": a.lr * a.legs_door_lr_scale, "lr_scale": a.legs_door_lr_scale})
    if LEGS_LEARN and dev.type == "cuda":                    # (--legs-learn) the branch's sums in full float32 (torch's default; said, so
        torch.backends.cuda.matmul.allow_tf32 = False        # nothing elsewhere turns it on: its draws are the simulator's from these logits)
    if LEGS_LEARN:                                           # (--legs-learn) the branch in a group of its own; every setting of the rate
        opt.add_param_group({"params": list(pol.legs.parameters()), "lr": a.lr * a.legs_learn, "lr_scale": a.legs_learn})   # keeps its share
    LEGS_GROUP = len(opt.param_groups) - 1                   # (the record's legs_learn rate: the branch's group, whatever comes after it)
    TRK_GROUP = [False]

    def trk_group():
        """(--track) the belief readout in a group of its own, the last: an optimizer saved without it loads into the groups
        before it, and one saved with it loads whole"""
        if TRK and not TRK_GROUP[0]:
            opt.add_param_group({"params": list(pol.track.parameters()), "lr": a.lr * a.track_lr_scale, "lr_scale": a.track_lr_scale})
            if BEL:                                          # (--belief, v0.4.0 A) the belief's own group, after the readout's
                opt.add_param_group({"params": list(pol.belief.parameters()), "lr": a.lr * BEL_LR, "lr_scale": BEL_LR})
            TRK_GROUP[0] = True

    TRZ_GROUP = [False]

    def trz_group():
        """(--track-z) the readout's second part in a group of its own, after the belief's: an optimizer saved without it
        (v0.4.0's) loads into the groups before it"""
        if TRZ and not TRZ_GROUP[0]:
            opt.add_param_group({"params": list(pol.trackz.parameters()), "lr": a.lr * TRZ_LR, "lr_scale": TRZ_LR})
            TRZ_GROUP[0] = True
    V41_GROUP = [False]
    N_V41 = int(BTOK) + int(AH)

    def v41_group():
        """(v0.4.1) the brain token's first layer and mark, then the readout ahead, in groups of their own after the others: an
        optimizer saved without them (v0.4.0's) loads into the groups before them"""
        if N_V41 and not V41_GROUP[0]:
            if BTOK:
                opt.add_param_group({"params": [p_ for n_, p_ in pol.named_parameters() if n_.startswith("attn.btok_")],
                                     "lr": a.lr * a.btoken_lr_scale, "lr_scale": a.btoken_lr_scale})
            if AH:
                opt.add_param_group({"params": list(pol.ahead.parameters()), "lr": a.lr * AH_LR, "lr_scale": AH_LR})
            V41_GROUP[0] = True
    H2_GROUP = [False]

    def h2_group():
        """(--head2) the strategy head in a group of its own after all the others: an optimizer saved without it loads into the
        groups before it"""
        if H2 and not H2_GROUP[0]:
            opt.add_param_group({"params": list(pol.head2.parameters()), "lr": a.lr * a.head2_lr_scale, "lr_scale": a.head2_lr_scale})
            H2_GROUP[0] = True
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    elapsed0 = 0.0
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location=dev)
        load_net(pol, ck["model"])
        if LEGS_IN:                                          # (the branch he resumes with against the movement network's file)
            d_ = max(float((pol.state_dict()[k_].cpu() - torch.from_numpy(np.asarray(v_))).abs().max()) for k_, v_ in LEGS_SD.items())
            print("legs inside: the branch {} the movement network's file (largest difference {:.3g})".format(
                "is" if d_ == 0 else "differs from", d_), flush=True)
        obs_mean, obs_var, obs_count = ck["obs_mean"], ck["obs_var"], ck["obs_count"]
        elapsed0 = ck.get("minutes", 0.0)
        op_ = os.path.join(out, "opt.pt")                     # (2026-10-18) the optimizer's state from the last save, if it fits
        if os.path.exists(op_):
            try:
                os_ = torch.load(op_, weights_only=False, map_location=dev)
                if H2 and N_V41 and TRK and len(os_["param_groups"]) == len(opt.param_groups) + 1 + int(BEL) + int(TRZ) + N_V41 + 1:
                    trk_group()                               # (v0.4.3: saved with the strategy head's group, the last)
                    trz_group()
                    v41_group()
                    h2_group()
                elif N_V41 and TRK and len(os_["param_groups"]) == len(opt.param_groups) + 1 + int(BEL) + int(TRZ) + N_V41:
                    trk_group()                               # (v0.4.1: saved with the token's and the ahead's groups, after the others)
                    trz_group()
                    v41_group()
                elif TRK and len(os_["param_groups"]) == len(opt.param_groups) + 1 + int(BEL) + int(TRZ):
                    trk_group()                               # (--track: saved with the readout's group; --belief: and the belief's;
                    trz_group()                               # --track-z: and the second part's)
                elif TRK and TRZ and len(os_["param_groups"]) == len(opt.param_groups) + 1 + int(BEL):
                    trk_group()                               # (--track-z added to a save without it: its group after the load)
                sc_ = [g_.get("lr_scale", 1.0) for g_ in opt.param_groups]      # (this run's scales: loading puts the saved ones back)
                for g_, s_ in zip(opt.param_groups, os_["param_groups"]):   # (torch checks the groups' sizes only: a moment of
                    for p_, i_ in zip(g_["params"], s_["params"]):           # another shape, or of another parameter, is refused here)
                        m_ = os_["state"].get(i_)
                        if m_ is not None and tuple(m_["exp_avg"].shape) != tuple(p_.shape):
                            raise ValueError("a saved moment of shape {} for a parameter of shape {} (tools/v036_init.py opt "
                                             "converts a widened network's)".format(tuple(m_["exp_avg"].shape), tuple(p_.shape)))
                opt.load_state_dict(os_)
                for g_, c_ in zip(opt.param_groups, sc_):     # (the rates are this run's, not the saved ones)
                    g_["lr_scale"], g_["lr"] = c_, a.lr * c_
                    if a.adam_fused:                          # (--adam-fused: the saved groups' own flag would put it back)
                        g_["fused"], g_["foreach"] = True, None
                n_st_ = 0
                for st_ in opt.state.values():                # (a step count loaded onto the card: the default Adam reads it with
                    if torch.is_tensor(st_.get("step")):      # .item(), a wait for the card a parameter twice every step)
                        if a.adam_fused:
                            st_["step"] = st_["step"].to(device=dev, dtype=torch.float32)
                        elif a.learn_nosync and st_["step"].device.type != "cpu":
                            st_["step"] = st_["step"].cpu()
                            n_st_ += 1
                print("optimizer: its state loaded from opt.pt{}".format(
                    " (--learn-nosync: {} step counts moved to the host)".format(n_st_) if a.learn_nosync else ""), flush=True)
            except Exception as e_:                           # noqa: BLE001  (another layout of groups: a cold start)
                print("optimizer: opt.pt does not fit ({}): a cold start".format(str(e_)[:120]), flush=True)
        else:
            print("optimizer: no opt.pt, a cold start", flush=True)
    trk_group()                                              # (--track) the readout's group, if the optimizer's state did not bring it
    trz_group()                                              # (--track-z) the second part's, after it
    v41_group()                                              # (v0.4.1) the token's and the ahead's, after them
    CTL_OPT = ({n_: torch.optim.Adam(pol.control[n_].parameters(), lr=a.control_lr) for n_ in control_.names(CTL_L)}
               if CTL_ON else None)                          # (--control) each readout's own, cold at a start
    CTL_GEN = torch.Generator().manual_seed(4046)            # ... the order of their minibatches: a stream of their own (his play's untouched)
    CTL_RING = [None]                                        # ... the brain's states as played, by global row (made at the first rollout)
    CTL_G = [0]                                              # ... the global row of the next rollout's first frame
    CTL_G0 = {}                                              # ... each rollout's first row, by its update
    CTL_T0 = float(a.control_start) if a.control_start >= 0 else float(elapsed0)
    CTL_LIVE = [1.0]                                         # (live.json's CONTROL_W: a factor on the lesson)
    import win_value as wv_                                  # (v0.4.3, --win-value) the shadow win value (sim/win_value.py)
    WV_ON = a.win_value > 0
    WV = WV_ACT = WV_OPT = WV_L = None
    if WV_CK is not None and not WV_ON:
        print("win value: the network's shadow win value is kept as it is (--win-value 0: not played, not learnt)", flush=True)
    if WV_ON:
        assert BEL, "--win-value: with --belief (it reads the brain's state)"
        assert bool(getattr(E_, "WIN_SHADOW", False)) and bool(getattr(E_, "GAME_ON", False)), "--win-value: WIN_SHADOW=1 in games (GAME_P)"
        assert set(groups) == {2}, "--win-value: duels only (--group 2)"
        assert a.steps % (BK * a.win_value_every) == 0, "--win-value: --steps a whole number of its kept ticks"
        WV_L = WV_CK["layout"] if WV_CK is not None else wv_.layout(bel=int(BEL_L["hid"]), mem=H, hid=a.win_value_hid, every=a.win_value_every,
                                                                    tick=BK, gamma=a.win_value_gamma, lam=a.win_value_lam,
                                                                    cal_every=a.win_value_cal_every)
        assert int(WV_L["bel"]) == int(BEL_L["hid"]) and int(WV_L["mem"]) == H and int(WV_L["tick"]) == BK, "--win-value: its widths do not fit"
        WV = wv_.make_module(WV_L).to(dev)
        if WV_CK is not None:
            WV.load_state_dict(WV_CK["model"])
        WV_ACT = copy.deepcopy(WV) if a.overlap else WV      # (--overlap: the copy the rollout's thread plays with)
        WV_OPT = torch.optim.Adam(WV.parameters(), lr=a.win_value_lr)    # (cold at a start, as the readouts')
        print("win value (v0.4.3, shadow): {} -> {} -> 1 on the brain's state and the hands' memory every {} ticks, gamma {} (cut at "
              "the game's end), TD({}); {}; lesson {} (rate {} x weight, rising over {} min from {}); host {:.2f} GB a rollout of states".format(
                  WV_L["width"], WV_L["hid"], WV_L["every"], WV_L["gamma"], WV_L["lam"], "from the network" if WV_CK is not None else
                  "new (its last layer at zero)", a.win_value, a.win_value_lr, a.win_value_warm,
                  "this process's start" if a.win_value_start < 0 else a.win_value_start,
                  wv_.n_kept(WV_L, a.steps) * N * WV_L["width"] * 2 / 1e9), flush=True)
    WV_GEN = torch.Generator().manual_seed(4048)             # (--win-value) its minibatch order: a stream of its own
    WV_T0 = float(a.win_value_start) if a.win_value_start >= 0 else float(elapsed0)
    WV_LIVE = [1.0]                                          # (live.json's WIN_VALUE_W)
    WV_PREV = [None]                                         # (the last rollout's kept states: learnt one rollout late)
    WV_ST = [None]                                           # (the per-seat stream, made at the first rollout)
    h2_group()                                               # (v0.4.3) the strategy head's, the last
    TRZ_T0 = float(a.track_z_start) if a.track_z_start >= 0 else float(elapsed0)
    TRZ_LIVE = [1.0]                                         # (live.json's TRACK_Z_W: a factor on the part's lesson, 1 at the start)

    def trz_lesson_w(mins):
        """(--track-z) the factor of the part's lesson at this minute: rising from nothing over --track-z-warm"""
        if not TRZ_ON:
            return 0.0
        return TRZ_LIVE[0] * (min(1.0, max(0.0, mins - TRZ_T0) / a.track_z_warm) if a.track_z_warm > 0 else 1.0)
    BEL_LR_NOW = [float(BEL_LR) if BEL else 0.0]             # (v0.4.1, live.json's BELIEF_LR) the brain's rate as a share of --lr
    AH_LIVE = [1.0]                                          # (live.json's AHEAD_W: a factor on the ahead lesson)
    RJ_LIVE = [float(a.rj_teach)]                            # (--rj-teach; live.json's RJ_TEACH_W: the lesson's weight)
    RJ_T0 = [float(a.rj_teach_start) if a.rj_teach_start >= 0 else None]     # ... the minute its warm-up counts from
    RJ_WIN = []                                              # ... [tries, arrived] of the last updates (the fade)
    if RJ_LAB and a.resume and os.path.exists(os.path.join(out, "metrics.jsonl")):     # ... carried over a restart: the last update's window
        try:
            for ln_ in open(os.path.join(out, "metrics.jsonl"), encoding="utf-8").readlines()[-50:]:
                if '"rj_teach"' in ln_:
                    rw_ = json.loads(ln_).get("rj_teach", {})
                    if rw_.get("window"):
                        RJ_WIN[:] = [list(rw_["window"])]
                    if RJ_T0[0] is None and rw_.get("start") is not None:
                        RJ_T0[0] = float(rw_["start"])
        except Exception as e_:
            print("rj_teach: the last window not read from metrics.jsonl: {}".format(e_), flush=True)

    def rj_teach_w(mins):
        """(--rj-teach) the lesson's weight at this minute: the live weight, rising over --rj-teach-warm from its start, times
        the fade by his share of tries that arrive (full at --rj-teach-done less --rj-teach-band, nothing at --rj-teach-done)"""
        if not RJ_LAB or RJ_LIVE[0] <= 0:
            return 0.0, 1.0
        if RJ_T0[0] is None:
            RJ_T0[0] = float(mins)
        w_ = RJ_LIVE[0] * (min(1.0, max(0.0, mins - RJ_T0[0]) / a.rj_teach_warm) if a.rj_teach_warm > 0 else 1.0)
        tr_, ov_ = (sum(x_[0] for x_ in RJ_WIN), sum(x_[1] for x_ in RJ_WIN))
        f_ = 1.0
        if tr_ >= 40 and a.rj_teach_band > 0:
            f_ = float(np.clip((a.rj_teach_done - ov_ / tr_) / a.rj_teach_band, 0.0, 1.0))
        return w_ * f_, f_
    RJC_LIVE = [float(a.rj_copy)]                            # (--rj-copy; live.json's RJ_COPY_W: the lesson's weight)
    IT_LIVE = [1.0]                                          # (v0.4.3; live.json's INTENT_TEACH_W: a factor on the item rule's weight, floor included)
    IF_LIVE = [float(a.item_floor_w), float(a.item_floor)]   # (--item-floor; live.json's ITEM_FLOOR_W, ITEM_FLOOR)
    IF_PMT = torch.from_numpy(IF_PM).to(dev)
    IF_OKT = torch.from_numpy(IF_OK).to(dev)
    IF_ONE = torch.nn.functional.one_hot(IF_PMT, len(IF_MAPS)).float()      # [N, maps]
    print("item floor: {} maps, their big items {}; floor {} weight {} (live ITEM_FLOOR, ITEM_FLOOR_W)".format(
        len(IF_MAPS), {m_: [E_.INTENTS[k_] for k_ in np.nonzero(IF_OK[j_])[0]] for j_, m_ in enumerate(IF_MAPS)}, a.item_floor, a.item_floor_w), flush=True)
    RJC_T0 = [float(a.rj_copy_start) if a.rj_copy_start >= 0 else None]     # ... the minute its warm-up counts from
    if RJC_LAB and RJC_T0[0] is None and a.resume and os.path.exists(os.path.join(out, "metrics.jsonl")):   # ... carried over a restart
        try:
            for ln_ in open(os.path.join(out, "metrics.jsonl"), encoding="utf-8").readlines()[-50:]:
                if '"rj_copy"' in ln_:
                    rc_ = json.loads(ln_).get("rj_copy", {})
                    if rc_.get("start") is not None:
                        RJC_T0[0] = float(rc_["start"])
        except Exception as e_:
            print("rj_copy: the warm-up's start not read from metrics.jsonl: {}".format(e_), flush=True)

    def rj_copy_w(mins):
        """(--rj-copy) the lesson's weight at this minute: the live weight, rising over --rj-copy-warm from its start"""
        if not RJC_LAB or RJC_LIVE[0] <= 0:
            return 0.0
        if RJC_T0[0] is None:
            RJC_T0[0] = float(mins)
        return RJC_LIVE[0] * (min(1.0, max(0.0, mins - RJC_T0[0]) / a.rj_copy_warm) if a.rj_copy_warm > 0 else 1.0)
    AH_T0 = float(a.ahead_start) if a.ahead_start >= 0 else float(elapsed0)
    BTOK_T0 = float(a.btoken_start) if a.btoken_start >= 0 else float(elapsed0)
    BTOK_LAST = [None]                                       # (the minute of the gate's last step)
    if BTOK_ON:
        print("btoken: gate {:.4f} now; shut until minute {:.1f} (--btoken-start {:.1f} + --btoken-delay {:g}), then 0 -> 1 over {:g} min, "
              "never above {:g} (live: BTOK_GATE_CAP, BTOK_GATE_OPEN; BELIEF_LR the brain's rate, now {:g})".format(
                  BTOK_G[0], BTOK_T0 + a.btoken_delay, BTOK_T0, a.btoken_delay, a.btoken_open, a.btoken_cap, BEL_LR_NOW[0]), flush=True)

    def ah_lesson_w(mins):
        """(--ahead) the factor of its lesson at this minute: rising from nothing over --ahead-warm"""
        if not AH_ON:
            return 0.0
        return AH_LIVE[0] * (min(1.0, max(0.0, mins - AH_T0) / a.ahead_warm) if a.ahead_warm > 0 else 1.0)
    BH = None                                                # (brainppl, --brain-human) the people's lesson
    BH_LIVE = [float(a.brain_human_w)]
    if a.brain_human:
        assert BEL and TRK_ON, "--brain-human: with --belief and --track (the brain's lesson)"
        import brain_human as bh_
        dirs_ = [d_ for d_ in a.brain_human.split(",") if d_]
        mx_ = [float(x_) for x_ in a.brain_human_mix.split(",")] if a.brain_human_mix else [1.0] * len(dirs_)
        assert len(mx_) == len(dirs_), "--brain-human-mix: one share a folder"
        BH = bh_.HumanMix([bh_.HumanLesson(d_, obs_mean, obs_var, int(BEL_L["hid"]), dev, piece=a.brain_human_piece, lanes=a.brain_human_lanes)
                           for d_ in dirs_], mx_)
        print(BH.describe() + "; share {} of the brain's lesson (live BRAIN_HUMAN_W), opening over {} min".format(a.brain_human_w, a.brain_human_open), flush=True)
    BDROP = None                                             # (--brain-drop) the columns the brain does not read
    if a.brain_drop:
        assert BEL, "--brain-drop: with --belief"
        BDROP = torch.tensor(json.load(open(a.brain_drop))["cols"], dtype=torch.long, device=dev)
        with torch.no_grad():
            pol.belief.inp.weight[:, BDROP] = 0.0
        print("brain-drop: the brain reads none of {} columns ({})".format(len(BDROP), a.brain_drop), flush=True)
    TRK_T0 = float(a.track_start) if a.track_start >= 0 else float(elapsed0)    # (--track) the minute its lesson and pay count from
    assert a.info_pay <= 0 or a.track > 0 or TRK_CK is not None, "--info-pay: with --track (a readout that learns) or one that has learnt"

    BEL_PAYNOTE = [False]

    def trk_pay_k(mins):
        """(--info-pay) k at this minute: nothing until --info-delay minutes after the lesson's start, then rising over --info-warm"""
        if not TRK_ON or a.info_pay <= 0:
            return 0.0
        if BEL:                                                  # (--belief: not built; a live INFO_PAY is not taken)
            if not BEL_PAYNOTE[0]:
                print("track: INFO_PAY {} with --belief is not built: the pay stays 0".format(a.info_pay), flush=True)
                BEL_PAYNOTE[0] = True
            return 0.0
        x_ = mins - TRK_T0 - a.info_delay
        if x_ <= 0:
            return 0.0
        return float(a.info_pay) * (min(1.0, x_ / a.info_warm) if a.info_warm > 0 else 1.0)

    BH_T0 = float(a.brain_human_start) if a.brain_human_start >= 0 else float(elapsed0)

    def bh_lesson_w(mins):
        """(--brain-human) the people's lesson's weight at this minute: the live factor, rising from 0 over --brain-human-open"""
        if BH is None:
            return 0.0
        return BH_LIVE[0] * (min(1.0, max(0.0, mins - BH_T0) / a.brain_human_open) if a.brain_human_open > 0 else 1.0)

    def trk_lesson_w(mins):
        """(--track) the lesson's weight at this minute: rising from nothing over --track-warm from the lesson's start"""
        if not TRK_ON or a.track <= 0:
            return 0.0
        return float(a.track) * (min(1.0, max(0.0, mins - TRK_T0) / a.track_warm) if a.track_warm > 0 else 1.0)
    LEGS_W0 = [p_.detach().clone() for p_ in pol.legs.parameters()] if LEGS_LEARN else None    # (--legs-learn) where the branch starts in this process
    if UNI_ON and float(os.environ.get("UNIFY_WAKE") or 0) > 0:     # (a test only: the parts woken with random weights of this size)
        with torch.no_grad():
            g_ = torch.Generator().manual_seed(11)
            sw_ = float(os.environ["UNIFY_WAKE"])
            if UNI_FEAT:
                pol.legs_door.weight.copy_(torch.randn(pol.legs_door.weight.shape, generator=g_) * sw_)
                pol.legs_door.bias.copy_(torch.randn(pol.legs_door.bias.shape, generator=g_) * sw_)
            if UNI_GUIDE:
                pol.legs_guide.copy_(torch.rand(pol.legs_guide.shape, generator=g_))
            for n_ in ("legs_gate", "legs_motor", "legs_res_a", "legs_res"):
                if getattr(pol, n_, None) is not None:
                    for p_ in getattr(pol, n_).parameters():
                        p_.copy_(torch.randn(p_.shape, generator=g_) * sw_)
            if UNI_RES:                                          # (a well inside (0, 1): the clamp's both sides seen)
                pol.legs_res_a.bias.copy_(torch.rand(pol.legs_res_a.bias.shape, generator=g_) * 0.6 + 0.2)
        print("UNIFY_WAKE: the parts woken at random (a test)", flush=True)
    UNI_W0 = {n_: p_.detach().clone() for n_, p_ in pol.named_parameters() if n_.startswith(UNI_PFX)}
    if a.switch_fade:                                        # (--switch-fade) from the checkpoint's, or 0
        assert L_HEAD >= 0, "--switch-fade: the simulator has no switch to his legs"
        FADE[0] = float(ck.get("switch_fade", 0.0)) if a.resume and os.path.exists(os.path.join(out, "policy.pt")) else 0.0
        FADE_V = torch.zeros(sum(ACTION_DIMS), device=dev)
        FADE_V[SW_ON] = 1.0
        pol.fade = FADE_V * FADE[0]
        print("switch fade: {:g} off the switch's 'legs' (+{:g} after an update with his run speed >= {:g}, up to {:g})".format(
            FADE[0], a.switch_fade_step, a.switch_fade_speed, a.switch_fade_max), flush=True)

    def norm(o):
        x = np.clip((o - obs_mean) / np.sqrt(obs_var + 1e-8), -10, 10).astype(np.float32)
        if HAS_CELLS:
            x[:, -2:] = o[:, -2:]                               # cell numbers stay as they are
        return x

    # ---- pro demos: sequences of (inputs, what the player did), imitated alongside the self-play loss
    import glob as _glob
    demo_files = [f for d_ in a.demo_dir.split(",") if d_ for f in sorted(_glob.glob(os.path.join(d_, "*.npz")))]
    demo_heads = [float(x) for x in a.demo_heads.split(",")]
    demo_rng = np.random.default_rng(77)
    demo_pool = []

    def demo_refill():
        demo_pool.clear()
        demo_files[:] = [f for d_ in a.demo_dir.split(",") if d_ for f in sorted(_glob.glob(os.path.join(d_, "*.npz")))]   # new conversions join in
        for k in demo_rng.choice(len(demo_files), min(a.demo_pool, len(demo_files)), replace=False):
            z = np.load(demo_files[k])
            if len(z["act"]) > a.demo_len + 1 and z["obs"].shape[1] == OBS_DIM:
                demo_pool.append((z["obs"], z["act"], z["first"]))

    def demo_batch():
        """(T, B, obs), (T, B, 8) actions, (T, B) first-frame flags"""
        T_, B_ = a.demo_len, a.demo_batch
        o = np.zeros((T_, B_, OBS_DIM), np.float32)
        ac = np.zeros((T_, B_, len(ACTION_DIMS)), np.int64)
        fi = np.zeros((T_, B_), np.float32)
        for b in range(B_):
            ob, act_, first_ = demo_pool[int(demo_rng.integers(len(demo_pool)))]
            s0 = int(demo_rng.integers(0, len(act_) - T_))
            o[:, b], ac[:, b], fi[:, b] = norm(ob[s0:s0 + T_].astype(np.float32)), act_[s0:s0 + T_], first_[s0:s0 + T_]
        return torch.from_numpy(o).to(dev), torch.from_numpy(ac).to(dev), torch.from_numpy(fi).to(dev)

    if a.demo_coef > 0:
        assert demo_files, "no demo files in --demo-dir"
        demo_refill()
        print("pro demos: {} files, {} in memory, weight {}".format(len(demo_files), len(demo_pool), a.demo_coef), flush=True)

    # what a checkpoint says of his clock (the checks' tools and the export read it): 600 when the games' time is all whole
    # games and mid-game starts (v0.2.2: one clock, one score, one memory a game), 120 otherwise (two-minute rounds)
    # (2026-10-22: every game-clock kind counts: whole games, late rounds and every moment start, the pros' starts too;
    # GAME_P + MID_START_P alone labelled v0.3.7 to v0.3.10 two-minute rounds)
    ROUND_SECS_CK = 600.0 if (float(getattr(E_, "GAME_P", 0.0)) + float(getattr(E_, "LATE_P", 0.0))
                              + float(getattr(E_, "MOMENT_P", getattr(E_, "MID_START_P", 0.0)))) >= 0.99 else 120.0

    LS = live_settings_init(out, E_)                                     # (the safe restart) <run>/live_settings.env: see LS_SPEC
    LIVE_KEPT = None                                                     # (B-265) the live values in force, once a live.json is applied
    def save(path, minutes):
        torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count, map=a.map,
                        obs_dim=OBS_DIM, action_dims=ACTION_DIMS, env="duel", arch="gru" if ATT is None else "gru+attn", attn=ATT,
                        hidden=H, minutes=minutes, **SLOW_SAVE, **HEAD_SAVE, **H2_SAVE, **ORDER_SAVE, **UNI_SAVE, **TRK_SAVE, **BEL_SAVE,
                        **({"btoken": dict(BTOK_L, gate=float(BTOK_G[0]))} if BTOK else {}),     # (v0.4.1: the gate as it is now)
                        **({"rule_fade": dict(RF_L, g=float(RF_G[0]))} if RF else {}),          # (v0.4.2a: the fade's gate as it is now)
                        **({"win_value": dict(layout=WV_L, model={k_: v_.detach().cpu() for k_, v_ in WV.state_dict().items()})} if WV is not None
                           else ({"win_value": WV_CK} if WV_CK is not None else {})),         # (v0.4.3, --win-value: never in "model")
                        **({"switch_fade": float(FADE[0])} if a.switch_fade else {}),
                        env_module=a.env, group=groups[0], groups=groups,
                        react_ms=a.react_ms, acquire_ms=a.acquire_ms, no_walk=bool(a.no_walk),
                        env_vars=dict({k_: os.environ[k_] for k_ in getattr(E_, "PLAY_VARS", ()) if os.environ.get(k_)}, **({"NO_SWITCH": "1"} if NO_SW else {}),
                                      **({"AUTO_HOP": "1" if E_.AUTO_HOP else "0"} if hasattr(E_, "AUTO_HOP") else {})),    # (v0.3.7: always said)
                        round_secs=ROUND_SECS_CK, arena_secs=float(a.arena_len),
                        game_secs=float(getattr(E_, "GAME_LEN", 0.0)) if getattr(E_, "GAME_ON", False) else 0.0,      # (GAME_P, LATE_P) he has played whole
                        game_vars={k_: os.environ[k_] for k_ in ("GAME_P", "LATE_P", "WIN_PAY", "MID_START_P", "SPAWN_START_P", "SPAWN_START_LEN", "OPENINGS", "OVERTIME", "STYLE_P") if os.environ.get(k_)},   # games: their clock and score
                        cells=E_.MAX_CELLS if HAS_CELLS else 0, cell_dim=CELL_DIM if HAS_CELLS else 0, **AUX_SAVE,
                        **({"live": LIVE_KEPT} if LIVE_KEPT is not None else {}),
                        **({"live_settings": dict(LS["file"])} if LS["file"] else {})),   # (live_settings.env: the file in force)   # (B-265) once a live.json is applied: the values in force
                   path)
        if os.path.basename(path) == "policy.pt":       # (2026-10-18) the optimizer's state beside it, for a resume
            torch.save(opt.state_dict(), os.path.join(os.path.dirname(path), "opt.pt.tmp"))
            os.replace(os.path.join(os.path.dirname(path), "opt.pt.tmp"), os.path.join(os.path.dirname(path), "opt.pt"))

    # league: odd players of the second half of every worker's matches are played by a frozen snapshot
    # (groups of more than two: every second member)
    w_n = [g_ * m_ for g_, m_ in zip(w_group, w_match)]                      # players of each worker
    w_off = np.concatenate([[0], np.cumsum(w_n)]).astype(int)
    assert w_off[-1] == N, (w_off[-1], N)
    is_odd = np.concatenate([np.arange(n_) % g_ % 2 == 1 for n_, g_ in zip(w_n, w_group)])
    league = np.zeros(N, bool)
    for w in range(a.workers):                                             # (not in a move-only simulator: all its players are his)
        league[w_off[w] + w_n[w] // 2:w_off[w + 1]] = True
    n_groups = int(sum(w_match[:a.workers]))                               # the games' groups and players: what the game numbers
    NP = int(w_off[a.workers])                                             # are counted over (a move-only simulator has its own, by map)
    snap_players = torch.from_numpy(league & is_odd).to(dev)          # controlled by the snapshot
    learn = (~snap_players).float()                                    # trained on
    snaps = []                                                         # frozen past policies (state dicts)
    SNAP_G = {}                                                        # (v0.4.1) a league file's own gate of the brain token
    SNAP_FG = {}                                                       # (v0.4.2a) ... and of the rule fade
    SNAP_NS = {}                                                       # (--no-switch) id(state dict) -> its switch is retired (a step-6 network)
    OPP_NS = [False]                                                   # ... the league network of this rollout's
    if a.resume:                                                       # the league survives a restart
        import glob
        import re as re_                                               # (by the minute in the name: from minute 10,000 the names have five
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "snap_*.pt")),          # digits and sort before the four-digit ones as text)
                        key=lambda f_: (int((re_.findall(r"\d+", os.path.basename(f_)) or ["0"])[0]), f_))[-8:]:
            ck_ = torch.load(f, weights_only=False, map_location=dev)
            snaps.append(ck_["model"])
            SNAP_G[id(snaps[-1])] = float((ck_.get("btoken") or {}).get("gate", 0.0)) if any(k_.startswith("attn.btok_") for k_ in ck_["model"]) else 0.0
            SNAP_FG[id(snaps[-1])] = float((ck_.get("rule_fade") or {}).get("g", 0.0))
            SNAP_NS[id(snaps[-1])] = str((ck_.get("env_vars") or {}).get("NO_SWITCH", "0")) not in ("0", "", "0.0")   # (--no-switch) a step-6 file
    anchors, vs_anchor = [], False                                     # ... and opponents that never leave it (--anchor-p)
    if a.anchor_p > 0:
        import glob
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "anchor_*.pt"))):
            ck_ = torch.load(f, weights_only=False, map_location=dev)
            anchors.append(ck_["model"])
            SNAP_G[id(anchors[-1])] = float((ck_.get("btoken") or {}).get("gate", 0.0)) if any(k_.startswith("attn.btok_") for k_ in ck_["model"]) else 0.0
            SNAP_FG[id(anchors[-1])] = float((ck_.get("rule_fade") or {}).get("g", 0.0))
            SNAP_NS[id(anchors[-1])] = str((ck_.get("env_vars") or {}).get("NO_SWITCH", "0")) not in ("0", "", "0.0")
        print("league anchors: {} (in {:.0%} of the rollouts)".format(len(anchors), a.anchor_p), flush=True)
    opp = copy.deepcopy(pol).eval()
    opp.fade = None                                          # (--switch-fade: the learner's alone)
    last_snap = time.time()
    h = torch.zeros(N, H, device=dev)
    h_opp = torch.zeros(N, H, device=dev)
    SM = SM_O = RING = None                                  # (--slow-mem) the slow state of his seats and of the league's, the ring
    if SLOW:
        SM, SM_O = slowmem_.State(N, SLOW, dev), slowmem_.State(N, SLOW, dev)
        RING = slowmem_.Ring(N, SLOW, a.steps // SLOW["every"], dev)
        print("slow memory: a ring of {} ticks x {} players x {} inputs at half precision on the host ({:.2f} GB)".format(
            RING.cap, N, SLOW["fast"] + SLOW["enc"], RING.u.numel() * 2 / 1e9), flush=True)
    H2S = H2O = None                                         # (--head2) the strategy head's state of his seats and of the league's
    H2_G, H2_LAST, H2_T0 = [0.0], [None], 0.0
    if H2:
        H2S, H2O = head2_.State(N, H2L, dev), head2_.State(N, H2L, dev)
        H2_G[0] = float(a.head2_gate) if a.head2_gate >= 0 else float(pol.head2.gate)
        with torch.no_grad():
            pol.head2.gate.fill_(min(H2_G[0], a.head2_cap))
        H2_G[0] = float(pol.head2.gate)
        H2_T0 = float(a.head2_start) if a.head2_start >= 0 else float(elapsed0)
        print("head2: gate {:.4f} now{}; lr x {}, its lesson x {}, value x {}, the plan's gradient into it x {}; ticks: u at half precision on "
              "the host ({:.2f} GB a rollout)".format(H2_G[0], "; held until minute {:.1f}, then 0 -> 1 over {:g} min (never above {:g}; live: H2_GATE_CAP, "
              "H2_GATE_OPEN)".format(H2_T0 + a.head2_delay, a.head2_open, a.head2_cap) if a.head2_open > 0 else " (held: --head2-open 0)",
              a.head2_lr_scale, a.head2_pg, a.head2_v, a.head2_plan_grad, (a.steps // BK) * N * head2_.u_width(H2L) * 2 / 1e9), flush=True)
    HS = HS_O = RINGH = None                                 # (--head) the head's state of his seats and of the league's, its ring
    HD_K = HD_J = 0
    HD_WG = HD_WB = -1                                       # (--head) the win label's columns in info["aux"] (-1: none: never taught)
    if HEADL:
        HD_K = int(HEADL["every"])
        HD_J = a.steps // HD_K
        HS, HS_O = head_.State(N, HEADL, dev), head_.State(N, HEADL, dev)
        if HEADL["ring"] > 0:
            RINGH = head_.Ring(N, HEADL, HD_J, dev)
            print("head: a ring of {} ticks x {} players x {} inputs at half precision on the host ({:.2f} GB)".format(
                RINGH.cap, N, head_.u_width(HEADL), RINGH.u.numel() * 2 / 1e9), flush=True)
        print("head: its store {} players x {} slots x {} on the {} ({:.2f} GB a state, two states)".format(
            N, HEADL["slots"], HEADL["slot"], dev.type, HS.slots.numel() * HS.slots.element_size() / 1e9), flush=True)
        AC_ = tuple(getattr(E_, "AUX_COLS", ()) or ())
        if "win_game" in AC_ and "win_band" in AC_:
            HD_WG, HD_WB = AC_.index("win_game"), AC_.index("win_band")
        HE_ = bool(getattr(E_, "HEAD_EVENTS", False))
        assert not HE_ or int(getattr(E_, "N_HEAD_EVENTS", HEADL["ev"])) == HEADL["ev"], \
            "the simulator gives {} events a tick, the head reads {}".format(getattr(E_, "N_HEAD_EVENTS", None), HEADL["ev"])
        print("head: events {}; the win head's labels {}".format(
            "from the simulators (HEAD_EVENTS)" if HE_ else "ZEROS (the simulator {} has HEAD_EVENTS off or none)".format(a.env),
            "from info['aux'] win_game / win_band (columns {}, {})".format(HD_WG, HD_WB) if HD_WG >= 0 else "NONE: never taught"), flush=True)
        print("head: lr x {}, values x {}, win x {} (true bands x {})".format(a.head_lr_scale, a.head_v, a.head_win, a.head_win_true), flush=True)

    def head_events():
        """(--head) the simulators' events of the head's tick about to come [N, ev] (zeros from a simulator without them)"""
        for p in pipes:
            p.send(("head_events", None))
        evs_ = []
        for w_, p in enumerate(pipes):
            r_ = p.recv()
            n_ = int(w_off[w_ + 1] - w_off[w_])
            evs_.append(np.zeros((n_, HEADL["ev"]), np.float32) if r_ is None else np.asarray(r_, np.float32).reshape(n_, HEADL["ev"]))
        return torch.from_numpy(np.concatenate(evs_)).to(dev)
    scr = torch.zeros(N, device=dev)                                   # scripted players (not trained on)

    T = a.steps
    b_hand = torch.zeros(T, N, HAND_D, dtype=torch.float16, device=dev) if HAND_LAB else None     # (--hand-teach) the target of the weapon
    B_HAND = b_hand
    #                                                                  output on that frame (zeros: no label)
    if HAND_LAB:
        print("hand: weight {} ({} of its gradient into the shared layers, rising over {:g} min), labels from the simulators: the target draws "
              "afresh every {:g} s{}".format(a.hand_teach, a.hand_teach_trunk, a.hand_teach_warm, float(getattr(E_, "HAND_TEACH_REDRAW", 0.0)),
                                             ", general lives only" if getattr(E_, "HAND_TEACH_GENERAL", False) else ""), flush=True)
    gamma, lam, clip, ent_coef = a.gamma, a.lam, 0.2, a.ent_coef
    ent_heads = [float(x) for x in a.ent_heads.split(",")] if a.ent_heads else [1.0] * len(ACTION_DIMS)
    ent_heads += [1.0] * (len(ACTION_DIMS) - len(ent_heads))
    t_start, total, update = time.time(), 0, 0
    dump = []
    log = open(os.path.join(out, "metrics.jsonl"), "a")
    print("recurrent self-play on {}: {} players, {} weights, device {}, {} min".format(
        a.map, N, sum(p.numel() for p in pol.parameters()), dev, a.minutes), flush=True)
    fade0 = a.fade_start if a.fade_start >= 0 else elapsed0             # the minute of training the teachers' fades count from
    GATE_M = None                                                        # (--gate-open) the tokens whose gate is below zero in the network
    if pol.attn is not None and getattr(pol.attn, "gate", None) is not None:   # he starts from: the ones the opening is for
        GATE_M = pol.attn.gate < 0
    assert a.gate_open <= 0 or (GATE_M is not None and a.gate_from <= 0), \
        "--gate-open: the network has no gated attention part (tools/targets_init.py makes one), or --gate-from is above 0"
    ka0 = a.keys_add_start if a.keys_add_start >= 0 else elapsed0       # (--keys-add-open) the minute its clock counts from
    assert a.keys_add_open <= 0 or KA_ON, "--keys-add-open: the simulator has no choices 'mine' on his legs (set LEGS_KEYS_ADD=1 with LEGS=1)"
    if KA_ON:
        KA_O = int(sum(ACTION_DIMS[:KA_HEAD]))

        def ka_over():
            """(LEGS_KEYS_ADD) the bias of "my legs'" over "mine", for each of the five"""
            b_ = pol.pi.bias[KA_O:KA_O + 2 * len(KA_COLS)].detach().view(-1, 2)
            return b_[:, 0] - b_[:, 1]
        print("keys on his legs (LEGS_KEYS_ADD): {} choices 'mine' for the columns {}, the bias of 'my legs' now {} over 'mine'{}".format(
            len(KA_COLS), list(KA_COLS), [round(float(x_), 2) for x_ in ka_over()],
            ", opened to {:g} over {:g} min counted from minute {:.2f} (--keys-add-start; this process starts at {:.2f})".format(
                a.keys_add_to, a.keys_add_open, ka0, elapsed0) if a.keys_add_open > 0 else " (left as they are: no --keys-add-open)"), flush=True)
    ta0 = a.turn_add_start if a.turn_add_start >= 0 else elapsed0       # (--turn-add-open) the minute its clock counts from
    assert a.turn_add_open <= 0 or TA_HEAD >= 0, "--turn-add-open: the simulator has no turn correction (set LEGS_TURN_ADD=1 with LEGS=1)"
    if TA_HEAD >= 0:
        TB_ = pol.pi.bias[TA_O:TA_O + ACTION_DIMS[TA_HEAD]].detach()
        print("turn correction (LEGS_TURN_ADD): {} choices, the bias of 0 now {:.2f} over the others{}".format(
            ACTION_DIMS[TA_HEAD], float(TB_[0] - TB_[1:].mean()),
            ", opened to {:g} over {:g} min counted from minute {:.2f} (--turn-add-start; this process starts at {:.2f})".format(
                a.turn_add_to, a.turn_add_open, ta0, elapsed0) if a.turn_add_open > 0 else
            " (left as it is: no --turn-add-open)"), flush=True)
    gate0 = a.gate_start if a.gate_start >= 0 else fade0                 # (--gate-start) the minute the gate's line counts from
    if a.gate_open > 0:
        print("gate: {} tokens (lowest now {:.2f}) open from {:g} to 0 over {:g} min, counted from minute {:.2f} (this process starts at {:.2f})".format(
            int(GATE_M.sum()), float(pol.attn.gate.min()), a.gate_from, a.gate_open, gate0, elapsed0), flush=True)
    if os.environ.get("STYLE_MIX"):                                      # (STYLE_MIX) what the simulators draw, said once
        sc_ = getattr(E_, "STYLE_CUM", None)
        if sc_ is None or not getattr(E_, "STYLE_P", 0.0) > 0:
            print("STYLE_MIX is set and {}: NO life is drawn by it".format("the simulator does not know it" if sc_ is None else "STYLE_P is 0"), flush=True)
        else:
            sh_ = np.diff(np.concatenate([[0.0], sc_]))
            print("styles: " + ", ".join("{} {:.0%}".format(k_, float(v_)) for k_, v_ in zip(E_.STYLES[1:], sh_))
                  + ", general {:.0%} of his lives (STYLE_MIX; a rail life on a map without a railgun is general)".format(1.0 - float(sc_[-1])), flush=True)
    WAY_STORE = {}                                                       # (WAYS) his trips between two places: {map: {(from, to): [paths]}}
    WAY_KEEP, WAY_MIN = 50, int(os.environ.get("WAY_TRIPS_MIN") or 30)   # ... the newest kept a pair; a pair counts from this many
    MAP_KEYS = ("players", "visible", "frags", "suicides", "pick_wp", "pick_mega", "pick_ra", "pick_ar", "stack_frames",
                "stack_bare", "stack_big", "stack_over", "first_wp", "fire_frames", "play_frames",
                "jump_tries", "jump_over", "jump_short", "jump_far", "jump_frames", "move_frames", "move_arrive", "move_speed", "move_fast",
                "rj_tries", "rj_over", "rj_frames", "rj_shots",
                "hurt_dmg", "legs", "games", "open", "moments", "overtime", "rail_start", "pro_start", "people_start", "gen_start", "run_item")
    LIVE_PATH = os.path.join(out, "live.json")                         # (B-265) pay weights changed while the run trains
    LIVE_ON = hasattr(E_, "live_set")
    LIVE_START = {k_: os.environ.get(k_) for k_ in getattr(E_, "LIVE_VARS", ())}      # the run's start: its environment
    LIVE_TSTART = dict(DMG_TAKEN_W=float(a.dmg_taken_w), DMG_REWARD=float(a.dmg_reward),
                       **({"INFO_PAY": float(a.info_pay), "TRACK_W": float(a.track), "TRACK_TRUNK": float(a.track_trunk)} if TRK_ON else {}),
                       **({"TRACK_Z_W": 1.0} if TRZ_ON else {}),
                       **({"BTOK_GATE_CAP": float(a.btoken_cap), "BTOK_GATE_OPEN": float(a.btoken_open)} if BTOK_ON else {}),
                       **({"BELIEF_LR": float(BEL_LR)} if BEL else {}), **({"AHEAD_W": 1.0} if AH_ON else {}),
                       **({"RJ_TEACH_W": float(a.rj_teach)} if RJ_LAB else {}),
                       **({"RJ_COPY_W": float(a.rj_copy)} if RJC_LAB else {}),
                       **({"INTENT_TEACH_W": 1.0} if a.intent_teach > 0 else {}),
                       **({"BRAIN_HUMAN_W": float(a.brain_human_w)} if BH is not None else {}),
                       ITEM_FLOOR=float(a.item_floor), ITEM_FLOOR_W=float(a.item_floor_w),
                       **({"FADE_CAP": float(a.rule_fade_cap), "FADE_OPEN": float(a.rule_fade_open)} if RF_ON else {}))   # ... and its arguments (v0.3.11: --info-pay with the readout on; v0.3.11b: --track, --track-trunk)
    LIVE_SEEN = None                                                     # the file as last read (LIVE_KEPT: the values in force, None: the start's)
    if LIVE_ON and os.path.exists(LIVE_PATH):
        print("live: {} is there at the start: it is read before the first rollout".format(LIVE_PATH), flush=True)
    OVL = bool(a.overlap)                                                # (--overlap, B-266) learn while the next games play
    DEC = OVL and a.overlap_ppo == "decoupled"                           # (--overlap-ppo) decoupled PPO around the learner's own network
    ACT = RS = STOP = None
    OBS_POOL = [None, None]                                              # (--overlap) the host's two input buffers [players, steps, inputs]
    if OVL:
        assert not HEADL and not SLOW and not HAS_CELLS, "--overlap: not with --head, --slow-mem or the map cells (not built)"
        import threading
        sys.setswitchinterval(max(1e-5, a.overlap_switch_ms / 1000.0))
        ACT = copy.deepcopy(pol)                                         # the network that plays: pol as it was before each learning step
        ACT.requires_grad_(False)
        RS = (torch.cuda.Stream(priority=-1 if a.overlap_priority == "high" else 0)    # the rollout's own stream on the card
              if dev.type == "cuda" else None)
        STOP = threading.Event()
        print("overlap: PPO {}{}; the rollout's stream priority {}".format(
            a.overlap_ppo, " (clip around the learner before the update, weights pi_prox/pi_played capped at {:g}, the baseline {})".format(
                a.overlap_is_cap, "the learner's values" if a.overlap_prox_values else "the played values") if DEC else "",
            a.overlap_priority), flush=True)
        print("overlap (B-266): the rollout of update n+1 plays while update n learns, with the network of before update n (one update "
              "stale); the rollout's thread {}, switch interval {:g} ms; its inputs on the host ({:.2f} GB a buffer, two)".format(
                  "on its own stream of the card" if RS is not None else "on the CPU", a.overlap_switch_ms,
                  N * T * OBS_DIM * (2 if a.obs_half else 4) / 1e9), flush=True)
    NOSYNC = bool(a.learn_nosync)                                        # (--learn-nosync) the learning step without its waits for the card
    CHK_ = [None, None]                                                  # ... the piece's players on the host, and the card's index they are
    XL_ = [None, None]                                                   # ... the card's index and the legs' inputs sent over for it
    PIN = NOSYNC and dev.type == "cuda"
    ADEV = dev if NOSYNC else None                                       # ... where the learning step's counters are summed (None: the host)
    if NOSYNC:
        torch.distributions.Distribution.set_default_validate_args(False)    # (the checks only raise on bad numbers: each waits for the card)
        print("learn-nosync: the learning step's waits for the card taken out (the same numbers)", flush=True)

    def FV_(t_):
        """a counter's number: float(t_) (a wait for the card), or with --learn-nosync the number left on the card in float64"""
        return t_.detach().double() if NOSYNC else float(t_)

    def up_(x_):
        """(--learn-nosync) a host tensor to the card from pinned memory, without waiting"""
        return (x_.pin_memory() if PIN else x_).to(dev, non_blocking=PIN)

    def BC_(y_, w_, n_):
        """a counter of the classes y_ weighted by w_ (float64), n_ classes, on the host: torch.bincount(...).cpu(); with
        --learn-nosync summed on the card by index_add_ (bincount waits for the card to learn its length)"""
        if not NOSYNC:
            return torch.bincount(y_, weights=w_, minlength=n_).cpu()
        return torch.zeros(n_, dtype=torch.float64, device=y_.device).index_add_(0, y_, w_)

    def HC_(t_):
        """a counter's numbers into a host counter: t_.cpu(), or with --learn-nosync left on the card (the counters are there)"""
        return t_ if NOSYNC else t_.cpu()

    def hchunk(chunk):
        """the piece's players' indices on the host: chunk.cpu(), or (--learn-nosync) the host copy made once an epoch"""
        return CHK_[0] if (NOSYNC and CHK_[1] is chunk) else chunk.cpu()

    def hsel(src, dim, chunk, ih_=None):
        """the rows of these players (axis dim) of src, on the card: as src[:, ih_].to(dev) (dim 1) and
        src.index_select(0, ih_).to(dev) (dim 0), ih_ the players on the host (chunk.cpu() if not given); with --learn-nosync
        gathered into pinned memory and sent without waiting"""
        if not NOSYNC:
            ih_ = chunk.cpu() if ih_ is None else ih_
            return (src[:, ih_] if dim == 1 else src.index_select(0, ih_)).to(dev)
        if src.device == dev:
            return src.index_select(dim, chunk)
        ih_ = hchunk(chunk) if ih_ is None else ih_
        sh_ = list(src.shape)
        sh_[dim] = len(ih_)
        b_ = torch.empty(sh_, dtype=src.dtype, pin_memory=PIN)
        torch.index_select(src, dim, ih_, out=b_)
        return b_.to(dev, non_blocking=PIN)

    def legs_x_of(chunk):
        """(LEGS_IN) the legs' inputs of these players on the card (--learn-nosync: sent once a piece, kept for its other reads)"""
        if NOSYNC and XL_[0] is chunk:
            return XL_[1]
        x_ = hsel(b_lx, 1, chunk)
        if NOSYNC:
            XL_[:] = [chunk, x_]
        return x_

    class LazyDists:
        """(--learn-nosync) dists(logits), each output's distribution made when it is first read (a teacher reads one or two)"""

        def __init__(self, lg_):
            self.parts, self.d = lg_.split(ACTION_DIMS, -1), {}

        def __getitem__(self, j_):
            if j_ not in self.d:
                self.d[j_] = (JumpCat if (JE and j_ == V_HEAD) else torch.distributions.Categorical)(logits=self.parts[j_])
            return self.d[j_]

        def __len__(self):
            return len(self.parts)

        def __iter__(self):
            return (self[j_] for j_ in range(len(self.parts)))
    CARRY = dict(obs=obs, teach=teach, hand=hand, aux=aux, legs_x=legs_x, scr=scr, h=h, h_opp=h_opp, rjl=rjl, rjc=rjc)    # from rollout to rollout
    if BTOK_ON:                                                          # (v0.4.1) the brain token's state of every seat (numpy, on the host)
        assert TRK_ON, "--btoken: with the readout's truth (TRACK_TRUTH=1): his own place and yaw come from info['aux']"
        assert not any(f_.startswith("zone") or f_.startswith("ztop") for f_ in BTOK_L["feats"]) or "zone_map" in tuple(E_.AUX_COLS), \
            "--btoken with the zones: TRACK_Z=1 (the zones' map number comes from info['aux'])"
        CARRY["tok"] = btoken_.Token(N, BTOK_L)
        CARRY["btg"] = BTOK_G[0]
    CARRY["rfg"] = RF_G[0]                                               # (v0.4.2a) the rule fade's gate of the coming rollout
    RF_T0 = float(a.rule_fade_start) if a.rule_fade_start >= 0 else float(elapsed0)
    RF_LAST = [None]                                                     # (the minute of the gate's last step)
    RF_OPP = [0.0]                                                       # (the league network's own g in this rollout)
    if RF_ON:
        print("rule fade: g {:.4f} now; held until minute {:.1f} (--rule-fade-start {:.1f} + --rule-fade-delay {:g}), then 0 -> 1 over {:g} min, "
              "never above {:g} (live: FADE_CAP, FADE_OPEN); the simulators' readers {}".format(
                  RF_G[0], RF_T0 + a.rule_fade_delay, RF_T0, a.rule_fade_delay, a.rule_fade_open, a.rule_fade_cap,
                  "on the brain's answer for a life drawn with chance g (BRAIN_READ=1{})".format(", the blind-fire exemption too (BLIND_BRAIN=1)" if RF_L["blind"] else "")
                  if RF_READ else "on the rule (BRAIN_READ unset)"), flush=True)
    if BEL:                                                              # (--belief) the belief's live state of every seat (the learner's
        CARRY["bs"] = belief_.State(N, BEL_L, dev)                       # network on every seat, as the readout's counters read it)

    def pre_rollout(upd):
        """what happens between two rollouts, before rollout `upd`: live.json, the gate's line, the biases' openings, the
        simulators' curriculum, a new league member, the league's network of this rollout (all on `pol` and in the
        simulators, never while a rollout plays) -> the numbers of that rollout for its update's record"""
        nonlocal LIVE_SEEN, LIVE_KEPT, snaps, last_snap, vs_anchor
        update = upd
        mins = elapsed0 + (time.time() - t_start) / 60
        LIVE_REC = None
        if os.path.exists(LIVE_PATH):                                    # (B-265) between two rollouts: a new or changed live.json
            try:
                st_ = os.stat(LIVE_PATH)
                txt_ = open(LIVE_PATH, encoding="utf-8").read()
            except OSError:
                st_, txt_ = None, None
            if txt_ is not None and (st_.st_mtime_ns, txt_) != LIVE_SEEN:
                LIVE_SEEN = (st_.st_mtime_ns, txt_)
                if not LIVE_ON:
                    lv_, lt_, why_ = None, None, "the simulator module {} has no live names".format(a.env)
                else:
                    lv_, lt_, why_ = live_read(LIVE_PATH, E_, LIVE_START, LIVE_TSTART)
                if why_ is not None:
                    LIVE_REC = dict(refused=why_, from_update=update)
                    print("live: {} REFUSED, nothing applied: {}".format(LIVE_PATH, why_), flush=True)
                else:
                    old_ = LIVE_KEPT or dict(sim=dict(LIVE_START), trainer=dict(LIVE_TSTART))
                    ch_ = {k_: v_ for k_, v_ in lv_.items() if old_["sim"].get(k_) != v_}
                    cht_ = {k_: v_ for k_, v_ in lt_.items() if old_["trainer"].get(k_) != v_}
                    for p in pipes:                                      # every simulator, then this process: the same values
                        p.send(("live", (lv_, lt_["DMG_TAKEN_W"])))
                    now_ = [p.recv() for p in pipes]
                    E_.live_set(lv_)                                     # (the environment too: the checkpoints' env_vars)
                    a.dmg_taken_w, a.dmg_reward = lt_["DMG_TAKEN_W"], lt_["DMG_REWARD"]
                    a.info_pay = lt_.get("INFO_PAY", a.info_pay)         # (v0.3.11: read before each rollout)
                    a.track = lt_.get("TRACK_W", a.track)                # (v0.3.11b: the lesson's weight, its warm-up as started)
                    a.track_trunk = min(1.0, lt_.get("TRACK_TRUNK", a.track_trunk))   # (v0.3.11b: its share into his memory, at the next learning step)
                    TRZ_LIVE[0] = float(lt_.get("TRACK_Z_W", TRZ_LIVE[0]))   # (--track-z: a factor on its lesson; 0 pauses it)
                    a.btoken_cap = float(lt_.get("BTOK_GATE_CAP", a.btoken_cap))     # (v0.4.1: the gate's cap: 0 shuts it at once)
                    a.btoken_open = float(lt_.get("BTOK_GATE_OPEN", a.btoken_open))  # (... the minutes of its opening: 0 holds it)
                    BEL_LR_NOW[0] = float(lt_.get("BELIEF_LR", BEL_LR_NOW[0]))       # (... the brain's rate, at the next learning step)
                    AH_LIVE[0] = float(lt_.get("AHEAD_W", AH_LIVE[0]))               # (... a factor on the ahead lesson)
                    RJ_LIVE[0] = float(lt_.get("RJ_TEACH_W", RJ_LIVE[0]))            # (--rj-teach: the lesson's weight; its warm-up from the first minute above 0)
                    RJC_LIVE[0] = float(lt_.get("RJ_COPY_W", RJC_LIVE[0]))           # (--rj-copy: the lesson's weight; its warm-up from the first minute above 0)
                    CTL_LIVE[0] = float(lt_.get("CONTROL_W", CTL_LIVE[0]))           # (--control: a factor on its lesson; 0 stops it)
                    WV_LIVE[0] = float(lt_.get("WIN_VALUE_W", WV_LIVE[0]))           # (--win-value: a factor on its rate; 0 stops it)
                    IT_LIVE[0] = float(lt_.get("INTENT_TEACH_W", IT_LIVE[0]))        # (v0.4.3: the item rule's factor, at the next learning step)
                    BH_LIVE[0] = float(lt_.get("BRAIN_HUMAN_W", BH_LIVE[0]))         # (--brain-human: the people's lesson's weight; 0 stops it)
                    IF_LIVE[0] = float(lt_.get("ITEM_FLOOR_W", IF_LIVE[0]))          # (--item-floor: its weight, 0 stops it; the floor)
                    IF_LIVE[1] = float(lt_.get("ITEM_FLOOR", IF_LIVE[1]))
                    a.rule_fade_cap = float(lt_.get("FADE_CAP", a.rule_fade_cap))    # (v0.4.2a: the rule fade's cap: 0 shuts it at once)
                    a.rule_fade_open = float(lt_.get("FADE_OPEN", a.rule_fade_open)) # (... the minutes of its opening: 0 holds it)
                    a.head2_cap = float(lt_.get("H2_GATE_CAP", a.head2_cap))         # (v0.4.3: the strategy head's gate: its cap, 0 shuts it at once)
                    a.head2_open = float(lt_.get("H2_GATE_OPEN", a.head2_open))      # (... the minutes of its opening: 0 holds it)
                    H2_PG_[2] = float(lt_.get("H2_PG", H2_PG_[2]))                   # (... a factor on its own lesson)
                    H2_PG_[1] = float(lt_.get("H2_PLAN_GRAD", H2_PG_[1]))            # (... the plan's gradient into it)
                    assert all(n_ == now_[0] for n_ in now_), "live: the simulators disagree"
                    LIVE_KEPT = dict(sim=dict(lv_), trainer=dict(lt_), from_update=update)
                    force_ = dict(now_[0], DMG_REWARD=a.dmg_reward, **({"INFO_PAY": a.info_pay, "TRACK_W": a.track, "TRACK_TRUNK": a.track_trunk} if TRK_ON else {}),
                                  **({"TRACK_Z_W": TRZ_LIVE[0]} if TRZ_ON else {}),
                                  **({"BTOK_GATE_CAP": a.btoken_cap, "BTOK_GATE_OPEN": a.btoken_open} if BTOK_ON else {}),
                                  **({"BELIEF_LR": BEL_LR_NOW[0]} if BEL else {}), **({"AHEAD_W": AH_LIVE[0]} if AH_ON else {}),
                                  **({"RJ_TEACH_W": RJ_LIVE[0]} if RJ_LAB else {}),
                                  **({"RJ_COPY_W": RJC_LIVE[0]} if RJC_LAB else {}),
                                  **({"CONTROL_W": CTL_LIVE[0]} if CTL_ON else {}),
                                  **({"WIN_VALUE_W": WV_LIVE[0]} if WV_ON else {}),
                                  **({"INTENT_TEACH_W": IT_LIVE[0]} if a.intent_teach > 0 else {}),
                                  **({"BRAIN_HUMAN_W": BH_LIVE[0]} if BH is not None else {}),
                                  ITEM_FLOOR=IF_LIVE[1], ITEM_FLOOR_W=IF_LIVE[0],
                                  **({"FADE_CAP": a.rule_fade_cap, "FADE_OPEN": a.rule_fade_open} if RF_ON else {}),
                                  **({"H2_GATE_CAP": a.head2_cap, "H2_GATE_OPEN": a.head2_open, "H2_PG": H2_PG_[2], "H2_PLAN_GRAD": H2_PG_[1]} if H2 else {}))
                    LIVE_REC = dict(applied=dict(ch_, **cht_), from_update=update, in_force=force_)
                    with open(os.path.join(out, "live_applied.json.tmp"), "w", encoding="utf-8") as f_:
                        json.dump(dict(from_update=update, minutes=round(mins, 2), file=json.loads(txt_), in_force=force_), f_, indent=1)
                    os.replace(os.path.join(out, "live_applied.json.tmp"), os.path.join(out, "live_applied.json"))
                    print("live: from update {} (before its rollout) in every simulator: changed {}; in force {}".format(
                        update, dict(ch_, **cht_) or "nothing", force_), flush=True)
        LS_REC = live_settings_poll(LS, pipes, E_, update, mins, LIVE_START, LIVE_PATH)   # (the safe restart: live_settings.env)
        if TRK_ON:                                                       # (--info-pay) the pay's k of this rollout (live.json's INFO_PAY, the delay, the ramp)
            TRK_K[0] = trk_pay_k(mins)
        if BTOK_ON:                                                      # (v0.4.1) the brain token's gate of this rollout: played and learnt at it
            BTOK_G[0] = btoken_.gate_step(BTOK_G[0], mins, BTOK_LAST[0], BTOK_T0, a.btoken_delay, a.btoken_open, a.btoken_cap)
            BTOK_LAST[0] = mins
            pol.attn.bgate = BTOK_G[0]
            CARRY["btg"] = BTOK_G[0]
        if H2:                                                           # (v0.4.3) the strategy head's gate of this rollout: played and learnt at it
            H2_G[0] = btoken_.gate_step(H2_G[0], mins, H2_LAST[0], H2_T0, a.head2_delay, a.head2_open, a.head2_cap)
            H2_LAST[0] = mins
            with torch.no_grad():
                pol.head2.gate.fill_(H2_G[0])
        if RF_ON:                                                        # (v0.4.2a) the rule fade's gate of this rollout: played and learnt at it
            RF_G[0] = btoken_.gate_step(RF_G[0], mins, RF_LAST[0], RF_T0, a.rule_fade_delay, a.rule_fade_open, a.rule_fade_cap)
            RF_LAST[0] = mins
            pol.rfg = RF_G[0]
            CARRY["rfg"] = RF_G[0]
        if a.gate_open > 0 and bool(GATE_M.any()):                       # (--gate-open) before the rollout: it is played and learnt
            gf_ = min(1.0, max(0.0, mins - gate0) / a.gate_open)        # from at one gate
            g_now = a.gate_from * (1.0 - gf_) if gf_ < 1.0 else 0.0
            with torch.no_grad():
                pol.attn.gate[GATE_M] = pol.attn.gate[GATE_M].clamp(min=g_now)
        if a.keys_add_open > 0 and KA_ON:                                # (--keys-add-open) before the rollout, as the turn's below
            kf_ = min(1.0, max(0.0, mins - ka0) / a.keys_add_open)
            if kf_ < 1.0 or update == 1:
                k_now = float(E_.KA_SHUT) + (a.keys_add_to - float(E_.KA_SHUT)) * kf_
                with torch.no_grad():
                    b_ = pol.pi.bias[KA_O:KA_O + 2 * len(KA_COLS)].view(-1, 2)
                    b_[:, 0] -= (b_[:, 0] - b_[:, 1] - k_now).clamp(min=0.0)
        if a.turn_add_open > 0 and TA_HEAD >= 0:                         # (--turn-add-open) before the rollout: it is played and learnt
            tf_ = min(1.0, max(0.0, mins - ta0) / a.turn_add_open)      # from at one bias
            if tf_ < 1.0 or update == 1:
                t_now = float(E_.TA_SHUT) + (a.turn_add_to - float(E_.TA_SHUT)) * tf_
                with torch.no_grad():                                    # (the bias of 0 over the mean of the others)
                    b_ = pol.pi.bias[TA_O:TA_O + ACTION_DIMS[TA_HEAD]]
                    over_ = float(b_[0] - b_[1:].mean())
                    if over_ > t_now:
                        b_[0] -= over_ - t_now
        close_p = max(a.close_floor, 1.0 - 0.8 * mins / a.close_minutes)
        round_len = 15.0 + 105.0 * (1.0 - (max(close_p, 0.2) - 0.2) / 0.8)
        dmg_reward = 0.004 * max(0.25, close_p)                         # damage shaping fades with the curriculum
        if a.dmg_reward > 0:                                            # ... unless it is set outright
            dmg_reward = a.dmg_reward
        seek_now = a.intent_seek * (max(0.25, 1.0 - (time.time() - t_start) / 60.0 / a.intent_seek_minutes)
                                    if a.intent_seek_minutes > 0 else 1.0)
        for p in pipes:
            p.send(("curriculum", (close_p, round_len, dmg_reward, seek_now)))
        for p in pipes:
            p.recv()
        if time.time() - last_snap > a.snapshot_min * 60:                # new league member
            last_snap = time.time()
            snaps.append(copy.deepcopy(pol.state_dict()))
            SNAP_G[id(snaps[-1])] = float(BTOK_G[0])                     # (v0.4.1: the gate it played at)
            SNAP_FG[id(snaps[-1])] = float(RF_G[0])                      # (v0.4.2a: the fade it played at)
            SNAP_NS[id(snaps[-1])] = NO_SW                               # (--no-switch: his own new snapshots are step-6 networks)
            snaps = snaps[-8:]
            save(os.path.join(out, "snapshots", "snap_{:04d}.pt".format(int(mins))), mins)
        if snaps:                                                        # pick this rollout's opponent
            vs_anchor = bool(anchors) and np.random.random() < a.anchor_p
            sd_o_ = anchors[np.random.randint(len(anchors))] if vs_anchor else snaps[np.random.randint(len(snaps))]
            load_net(opp, sd_o_)
            if BTOK:                                                     # (v0.4.1) the file's own gate (0: no token, or shut)
                opp.attn.bgate = float(SNAP_G.get(id(sd_o_), 0.0)) if BTOK_ON else 0.0
            if RF:                                                       # (v0.4.2a) the file's own fade (0: none)
                opp.rfg = RF_OPP[0] = float(SNAP_FG.get(id(sd_o_), 0.0)) if RF_ON else 0.0
            OPP_NS[0] = bool(SNAP_NS.get(id(sd_o_), False))
            opp.door_open = bool(opp.attn is not None and float(opp.attn.door.weight.abs().sum()) > 0)
        if RF_READ:                                                      # (v0.4.2a) each seat's chance of a life on the brain: his seats at his
            gs_ = np.where(league & is_odd, RF_OPP[0] if snaps else RF_G[0], RF_G[0]).astype(np.float32)   # g, the league's at its file's
            for w_, p in enumerate(pipes):
                p.send(("brain_g", gs_[w_off[w_]:w_off[w_ + 1]]))
            for p in pipes:
                p.recv()
        return dict(mins=mins, live_rec=LIVE_REC, live_settings=LS_REC, close_p=close_p, seek_now=seek_now, vs_anchor=vs_anchor,
                    has_snaps=bool(snaps), n_snaps=len(snaps), opp_ns=bool(OPP_NS[0]))

    TRK_BINS = ("in_view", "0-2s", "2-5s", "5-10s", "10s+", "unseen_since_spawn")   # (--track) the counters by time unseen

    def trk_stats_new():
        """(--track) a rollout's counters of the readout: his seats (the learner's), on the frames it is scored"""
        nb_ = len(TRK_BINS)
        return dict(err=[[] for _ in range(nb_)], bel=[[] for _ in range(nb_)], n=np.zeros(nb_), ll=np.zeros((nb_, len(track_.PARTS))),
                    band=np.zeros(nb_), hand=np.zeros(nb_), own=np.zeros(nb_), sd=np.zeros(nb_), bel_ok=np.zeros(nb_), score=np.zeros(nb_),
                    pay_sum=0.0, pay_abs=0.0, pay_hidden=0.0, pay_mine=0.0, scorings=0, seats=0, pairs_on=0,
                    z=trz_stats_new(nb_) if TRZ_ON else None)

    TRZ_FAR = 600.0                                          # (--track-z) "far": the readout's place this far or more from the truth
    TRZ_RB = 10                                              # ... the calibration's bins of the zones' odds

    def trz_stats_new(nb_):
        """(--track-z) a rollout's counters of the second part: by time unseen (nb_ bins) and by map (zonemap.MAPS)"""
        nm_ = len(zonemap_.MAPS)
        Z_ = {k_: np.zeros(nb_) for k_ in ("nv", "spd_nll", "polar", "vel_old", "vel_old_win", "dir_nll", "dir_n",
                                            "n", "top1", "top2", "nll", "pt", "seen", "seen_n", "pr1", "prnll", "far_n", "far_top2", "far_pt")}
        Z_.update(spd_err=[[] for _ in range(nb_)], dir_err=[[] for _ in range(nb_)],
                  rel_n=np.zeros((nb_, TRZ_RB)), rel_p=np.zeros((nb_, TRZ_RB)), rel_hit=np.zeros((nb_, TRZ_RB)),
                  map={k_: np.zeros(nm_) for k_ in ("n", "top1", "top2", "nll", "pt", "seen", "seen_n", "pr1", "prnll")})
        return Z_

    def trz_frame(TS, net, z, aux_np, ix_, b_, mu_, er_):
        """(--track-z) the second part's counters on a scoring frame, his seats ix_ in their bins b_ (time unseen): zone right
        (first, first two), its nll; three bars: the zone of the readout's own place (mu_, from him turned to his facing), the
        zone he last saw the enemy in, the map's commonest zone so far (and that prior's nll); the calibration (every zone's
        odds in TRZ_RB bins against how often it is the zone); where the place is far off (er_ >= TRZ_FAR), the first two
        zones right against the place's zone; the same by map. The speed's error and nll, the direction's error (degrees,
        where he moved 160 u/s or more on the mean) and nll; the polar density's nll (speed x direction / speed) beside the
        old velocity part's, against the instantaneous velocity (its own truth) and the 0.2 s mean"""
        Z_ = TS["z"]
        with torch.no_grad():
            iz_ = torch.from_numpy(ix_).to(z.device)
            o_ = net.trackz(z.float()[iz_]).float()
            y_ = torch.from_numpy(np.ascontiguousarray(aux_np[ix_][:, TRZ_TC], dtype=np.float32)).to(o_.device)
            ll_, wd_, hz_ = trz_.parts(o_, y_)
            pz_, sp_, _, ang_, _ = trz_.readable(o_, y_[:, 1].round().long())
            ll_, hz_, pz_, sp_, ang_ = (x_.cpu().numpy() for x_ in (ll_, hz_, pz_, sp_, ang_))
            yo_ = torch.from_numpy(np.ascontiguousarray(aux_np[ix_][:, TRK_TC], dtype=np.float32)).to(o_.device)
            to_ = net.track(z.float()[iz_]).float()
            v_old = track_.loglik(to_, yo_, floor=False)[:, 1].cpu().numpy()
            yw_ = yo_.clone()
            yw_[:, 3:5] = y_[:, 3:5]
            v_win = track_.loglik(to_, yw_, floor=False)[:, 1].cpu().numpy()
        A_ = aux_np[ix_].astype(np.float64)
        zt_ = np.round(A_[:, TRZ_TC[0]]).astype(np.int64)
        zm_ = np.round(A_[:, TRK_IX["zone_map"]]).astype(np.int64)
        zs_ = np.round(A_[:, TRK_IX["zone_seen"]]).astype(np.int64)
        yr_ = np.radians(A_[:, TRK_IX["yaw"]])
        c_, s_ = np.cos(yr_), np.sin(yr_)
        wx_ = A_[:, TRK_IX["x"]] + c_ * mu_[:, 0] - s_ * mu_[:, 1]
        wy_ = A_[:, TRK_IX["y"]] + s_ * mu_[:, 0] + c_ * mu_[:, 1]
        wz_ = A_[:, TRK_IX["z"]] + mu_[:, 2]
        top_ = np.argsort(-pz_, 1)[:, :2]
        spd_ = A_[:, TRZ_TC[2]]
        mv_ = A_[:, [TRZ_TC[3], TRZ_TC[4]]]
        mn_ = np.linalg.norm(mv_, axis=1)
        dth_ = np.degrees(np.abs((ang_ - np.arctan2(mv_[:, 1], mv_[:, 0]) + np.pi) % (2 * np.pi) - np.pi))
        polar_ = -(ll_[:, 1] + ll_[:, 2]) + np.log(np.maximum(spd_, 10.0))
        nb_ = len(TRK_BINS)
        ad_ = lambda k_, m_, v_: np.add.at(Z_[k_], b_[m_], v_)
        al_ = np.ones(len(ix_), bool)
        ad_("nv", al_, 1.0)
        ad_("spd_nll", al_, -ll_[:, 1])
        ad_("polar", al_, polar_)
        ad_("vel_old", al_, -v_old)
        ad_("vel_old_win", al_, -v_win)
        dm_ = mn_ >= 160.0
        ad_("dir_nll", dm_, -ll_[dm_, 2])
        ad_("dir_n", dm_, 1.0)
        se_ = np.abs(sp_ - spd_)
        for j_ in range(nb_):
            if (b_ == j_).any():
                Z_["spd_err"][j_].append(se_[b_ == j_].astype(np.float32))
            if (dm_ & (b_ == j_)).any():
                Z_["dir_err"][j_].append(dth_[dm_ & (b_ == j_)].astype(np.float32))
        zk_ = hz_.astype(bool) & (zm_ >= 0)
        pt_ = np.zeros(len(ix_), bool)
        pr1_ = np.zeros(len(ix_), bool)
        prn_ = np.zeros(len(ix_))
        zn_ = np.zeros(len(ix_), np.int64)
        for q_ in np.unique(zm_[zk_]):                                # (a map at a time: its lookup and prior)
            mq_ = zk_ & (zm_ == q_)
            Zm_ = zonemap_.load(zonemap_.MAPS[q_])
            if Zm_ is None:
                zk_ &= ~mq_
                continue
            zn_[mq_] = Zm_.k
            pt_[mq_] = Zm_.locate(np.stack([wx_[mq_], wy_[mq_], wz_[mq_]], 1)) == zt_[mq_]
            cnt_ = TRZ_PRIOR[q_, :Zm_.k]
            pr1_[mq_] = (int(cnt_.argmax()) == zt_[mq_]) & (cnt_.sum() > 0)
            prn_[mq_] = -np.log((cnt_[np.minimum(zt_[mq_], Zm_.k - 1)] + 1.0) / (cnt_.sum() + Zm_.k))
        t1_ = (top_[:, 0] == zt_).astype(np.float64)
        t2_ = ((top_[:, 0] == zt_) | (top_[:, 1] == zt_)).astype(np.float64)
        sk_ = zk_ & (zs_ >= 0)
        sh_ = (zs_ == zt_).astype(np.float64)
        ad_("n", zk_, 1.0)
        ad_("top1", zk_, t1_[zk_])
        ad_("top2", zk_, t2_[zk_])
        ad_("nll", zk_, -ll_[zk_, 0])
        ad_("pt", zk_, pt_[zk_].astype(np.float64))
        ad_("seen_n", sk_, 1.0)
        ad_("seen", sk_, sh_[sk_])
        ad_("pr1", zk_, pr1_[zk_].astype(np.float64))
        ad_("prnll", zk_, prn_[zk_])
        fk_ = zk_ & (er_ >= TRZ_FAR)
        ad_("far_n", fk_, 1.0)
        ad_("far_top2", fk_, t2_[fk_])
        ad_("far_pt", fk_, pt_[fk_].astype(np.float64))
        M_ = Z_["map"]                                                # (by map)
        for k_, m_, v_ in (("n", zk_, 1.0), ("top1", zk_, t1_[zk_]), ("top2", zk_, t2_[zk_]), ("nll", zk_, -ll_[zk_, 0]),
                           ("pt", zk_, pt_[zk_].astype(np.float64)), ("seen_n", sk_, 1.0), ("seen", sk_, sh_[sk_]),
                           ("pr1", zk_, pr1_[zk_].astype(np.float64)), ("prnll", zk_, prn_[zk_])):
            np.add.at(M_[k_], zm_[m_], v_)
        if zk_.any():                                                 # (the calibration: every zone of the map, its odds and whether it is the one)
            P_ = pz_[zk_]
            live_ = np.arange(trz_.MAX_Z)[None, :] < zn_[zk_][:, None]
            hit_ = (np.arange(trz_.MAX_Z)[None, :] == zt_[zk_][:, None]).astype(np.float64)
            rb_ = np.minimum((P_ * TRZ_RB).astype(np.int64), TRZ_RB - 1)
            bb_ = np.broadcast_to(b_[zk_][:, None], P_.shape)
            np.add.at(Z_["rel_n"], (bb_[live_], rb_[live_]), 1.0)
            np.add.at(Z_["rel_p"], (bb_[live_], rb_[live_]), P_[live_])
            np.add.at(Z_["rel_hit"], (bb_[live_], rb_[live_]), hit_[live_])
        np.add.at(TRZ_PRIOR, (zm_[zk_], zt_[zk_]), 1.0)              # (the prior learns after it is scored)

    def trz_stats_end(Z_):
        """(--track-z) the rollout's counters -> the record's numbers"""
        r3 = lambda x_, d_=4: round(float(x_), d_)
        out_ = {}
        for j_, nm_ in enumerate(TRK_BINS):
            n_, nv_ = Z_["n"][j_], Z_["nv"][j_]
            if nv_ <= 0:
                continue
            r_ = dict(frames=int(nv_), spd_err_med=r3(np.median(np.concatenate(Z_["spd_err"][j_])), 1), spd_nll=r3(Z_["spd_nll"][j_] / nv_, 3),
                      polar_nll=r3(Z_["polar"][j_] / nv_, 3), vel_old_nll=r3(Z_["vel_old"][j_] / nv_, 3),
                      vel_old_nll_win=r3(Z_["vel_old_win"][j_] / nv_, 3))
            if Z_["dir_n"][j_] > 0:
                r_.update(dir_err_med=r3(np.median(np.concatenate(Z_["dir_err"][j_])), 1), dir_nll=r3(Z_["dir_nll"][j_] / Z_["dir_n"][j_], 3),
                          dir_frames=int(Z_["dir_n"][j_]))
            if n_ > 0:
                rn_ = Z_["rel_n"][j_]
                r_.update(zone_frames=int(n_), zone_top1=r3(Z_["top1"][j_] / n_), zone_top2=r3(Z_["top2"][j_] / n_),
                          zone_nll=r3(Z_["nll"][j_] / n_, 3), point_zone=r3(Z_["pt"][j_] / n_),
                          seen_zone=r3(Z_["seen"][j_] / max(1.0, Z_["seen_n"][j_])), seen_frames=int(Z_["seen_n"][j_]),
                          prior_top1=r3(Z_["pr1"][j_] / n_), prior_nll=r3(Z_["prnll"][j_] / n_, 3),
                          calib_gap=r3((np.abs(Z_["rel_p"][j_] - Z_["rel_hit"][j_])).sum() / max(1.0, rn_.sum())))
                if Z_["far_n"][j_] > 0:
                    r_.update(far_frames=int(Z_["far_n"][j_]), far_top2=r3(Z_["far_top2"][j_] / Z_["far_n"][j_]),
                              far_point_zone=r3(Z_["far_pt"][j_] / Z_["far_n"][j_]))
            out_[nm_] = r_
        rn_, rp_, rh_ = Z_["rel_n"].sum(0), Z_["rel_p"].sum(0), Z_["rel_hit"].sum(0)
        out_["calib"] = dict(n=[int(x_) for x_ in rn_], p=[r3(p_ / max(1.0, n_)) for p_, n_ in zip(rp_, rn_)],
                             hit=[r3(h_ / max(1.0, n_)) for h_, n_ in zip(rh_, rn_)], gap=r3(np.abs(rp_ - rh_).sum() / max(1.0, rn_.sum())))
        M_ = Z_["map"]
        out_["by_map"] = {zonemap_.MAPS[q_]: dict(frames=int(M_["n"][q_]), top1=r3(M_["top1"][q_] / M_["n"][q_]), top2=r3(M_["top2"][q_] / M_["n"][q_]),
                                                  nll=r3(M_["nll"][q_] / M_["n"][q_], 3), point_zone=r3(M_["pt"][q_] / M_["n"][q_]),
                                                  seen_zone=r3(M_["seen"][q_] / max(1.0, M_["seen_n"][q_])), prior_top1=r3(M_["pr1"][q_] / M_["n"][q_]),
                                                  prior_nll=r3(M_["prnll"][q_] / M_["n"][q_], 3))
                          for q_ in range(len(zonemap_.MAPS)) if M_["n"][q_] > 0}
        return out_

    def trk_frame(net, aux_np, w_t, TS, k, z=None):
        """(--track, --info-pay) a scoring frame: every seat's readout (the learner's network on every seat's own memory: the
        league's seats are read by it too, so that both sides of a pair are judged by the same reader) against the truth of
        aux_np (info["aux"] of the frame the network has just read); the pay k * (his score - the enemy's) where both are on
        (zero-sum over each pair; nothing with k = 0); the counters into TS. -> the pay [N] on the card, or None"""
        with torch.no_grad():
            o_ = net.track((net.zl if z is None else z).float()).float()       # (--belief: z the belief's state)
            y_ = torch.from_numpy(np.ascontiguousarray(aux_np[:, TRK_TC], dtype=np.float32)).to(o_.device)
            on_np = aux_np[:, TRK_IX["trk_on"]] > 0.5
            on_ = torch.from_numpy(on_np).to(o_.device)
            ll_ = track_.loglik(o_, y_, floor=True)
            sc_ = (ll_ * track_.wvec(TRK_PARTS, o_)).sum(-1)
            pay_ = track_.pair_pay(sc_, on_, k) if k > 0 else None
            llp_ = track_.loglik(o_, y_, floor=False).cpu().numpy()
            mu_, sd_, bd_, hd_, ow_ = (x_.cpu().numpy() for x_ in track_.readable(o_))
        sc_ = sc_.cpu().numpy()
        en_ = np.arange(len(on_np)) ^ 1
        both_ = on_np & on_np[en_]
        me_ = both_ & (w_t.cpu().numpy() > 0)
        TS["scorings"] += 1
        TS["pairs_on"] += int(both_.sum()) // 2
        TS["seats"] += int(me_.sum())
        if pay_ is not None:
            pn_ = pay_.cpu().numpy()
            hid_ = (aux_np[:, TRK_IX["en_in_view"]] < 0.5) & (aux_np[en_, TRK_IX["en_in_view"]] < 0.5)
            TS["pay_sum"] += float(pn_[both_].sum())
            TS["pay_abs"] += float(np.abs(pn_[me_]).sum())
            TS["pay_hidden"] += float(np.abs(pn_[me_ & hid_]).sum())
            TS["pay_mine"] += float(pn_[me_].sum())
        if not me_.any():
            return pay_
        ix_ = np.nonzero(me_)[0]
        A_ = aux_np[ix_]
        us_ = A_[:, TRK_IX["unseen_s"]]
        b_ = np.where(A_[:, TRK_IX["en_in_view"]] > 0.5, 0, np.where(us_ >= E_.TRACK_UNSEEN_CAP - 1e-3, 5,
                      1 + np.digitize(us_, (2.0, 5.0, 10.0))))
        tr_ = A_[:, [TRK_IX["en_fwd"], TRK_IX["en_left"], TRK_IX["en_up"]]].astype(np.float64)
        er_ = np.linalg.norm(mu_[ix_] - tr_, axis=1)
        bok_ = A_[:, TRK_IX["bel_ok"]] > 0.5
        bp_ = np.where(bok_[:, None], A_[:, [TRK_IX["bel_fwd"], TRK_IX["bel_left"], TRK_IX["bel_up"]]], 0.0)
        be_ = np.linalg.norm(bp_ - tr_, axis=1)
        y_ = A_[:, TRK_TC]
        own_t = y_[:, 7:7 + len(track_.OWN)] > 0.5
        for j_ in range(len(TRK_BINS)):
            m_ = b_ == j_
            if not m_.any():
                continue
            TS["err"][j_].append(er_[m_].astype(np.float32))
            TS["bel"][j_].append(be_[m_].astype(np.float32))
            TS["n"][j_] += m_.sum()
            TS["ll"][j_] += llp_[ix_][m_].sum(0)
            TS["band"][j_] += (bd_[ix_][m_] == np.round(y_[m_, 5])).sum()
            TS["hand"][j_] += (hd_[ix_][m_] == np.round(y_[m_, 6])).sum()
            TS["own"][j_] += ((ow_[ix_][m_] > 0.5) == own_t[m_]).all(1).sum()
            TS["sd"][j_] += sd_[ix_][m_, 0].sum()
            TS["bel_ok"][j_] += bok_[m_].sum()
            TS["score"][j_] += sc_[ix_][m_].sum()
        if TS.get("z") is not None and z is not None:                 # (--track-z) the second part's counters
            trz_frame(TS, net, z, aux_np, ix_, b_, mu_[ix_], er_)
        return pay_

    def trk_stats_end(TS, k):
        """(--track) a rollout's counters -> the record's numbers (medians of the place's error by time unseen, the belief
        inputs' beside them; the mean plain log-likelihood of each part; called right; the pay)"""
        if TS is None:
            return None
        mins_ = TS["seats"] * TRK_EVERY * E_.DT / 60.0            # his seats' minutes of game time scored (a scoring stands for info_every frames)
        out_ = dict(k=round(k, 5), scorings=TS["scorings"], seat_minutes=round(mins_, 1), by=dict())
        for j_, nm_ in enumerate(TRK_BINS):
            n_ = TS["n"][j_]
            if n_ <= 0:
                continue
            e_, be_ = np.concatenate(TS["err"][j_]), np.concatenate(TS["bel"][j_])
            out_["by"][nm_] = dict(share=round(float(n_ / max(1.0, TS["n"].sum())), 4), err_med=round(float(np.median(e_)), 1),
                                   bel_med=round(float(np.median(be_)), 1), nearer=round(float((e_ < be_).mean()), 4),
                                   bel_ok=round(float(TS["bel_ok"][j_] / n_), 4), sd_xy=round(float(TS["sd"][j_] / n_), 1),
                                   nll={p_: round(float(-TS["ll"][j_, i_] / n_), 3) for i_, p_ in enumerate(track_.PARTS)},
                                   band_right=round(float(TS["band"][j_] / n_), 4), hand_right=round(float(TS["hand"][j_] / n_), 4),
                                   own_right=round(float(TS["own"][j_] / n_), 4), score=round(float(TS["score"][j_] / n_), 3))
        if TS.get("z") is not None:                                   # (--track-z)
            out_["z"] = trz_stats_end(TS["z"])
        if mins_ > 0:
            out_["pay"] = dict(abs_per_player_min=round(TS["pay_abs"] / mins_, 4), net_per_player_min=round(TS["pay_mine"] / mins_, 4),
                               hidden_share=round(TS["pay_hidden"] / max(1e-9, TS["pay_abs"]), 4), pairs_sum=float(TS["pay_sum"]))
        return out_

    def rollout(net, onet, C, upd, keep_raw, has_snaps, opp_ns, stop=None):
        """one rollout of T frames: his seats played by `net`, the league's by `onet` (off: pol and opp; --overlap: the copy
        ACT, in the rollout's thread); C the carry from rollout to rollout (the simulators' last frame, the memories),
        updated at the end -> the rollout's buffers and counts (None: stopped by `stop`)"""
        obs, teach, hand, aux, legs_x, scr, h, h_opp = (C[k_] for k_ in ("obs", "teach", "hand", "aux", "legs_x", "scr", "h", "h_opp"))
        b_hand = torch.zeros_like(B_HAND) if (OVL and B_HAND is not None) else B_HAND   # (--overlap: one a rollout)
        rjl = C.get("rjl")
        b_rj = torch.zeros(T, N, dtype=torch.int8, device=dev) if RJ_LAB else None     # (--rj-teach) the label of each frame's action
        rjc = C.get("rjc")
        b_rjc = torch.full((T, N, RJC_H), -1, dtype=torch.int8, device=dev) if RJC_LAB else None     # (--rj-copy) the runner's labels of each frame's action
        b_rl = b_val2 = b_lx = b_lr = b_llp = b_aux = b_ht = b_bel = b_ev = b_wg = b_wb = None
        HD_RS0 = HD_PEND = HD0 = hd_secs = SL_RS0 = SL_PEND = SL_S0 = sl_secs = None
        if OVL:                                                          # (--overlap) on the host, a player's frames together: [players, steps,
            b_obs = OBS_POOL[upd % 2]                                    # inputs]; two buffers in turn (the learning step reads the other)
            if b_obs is None:
                b_obs = OBS_POOL[upd % 2] = torch.empty(N, T, OBS_DIM, dtype=torch.float16 if a.obs_half else torch.float32)
        else:
            b_obs = torch.zeros(T, N, OBS_DIM, device=dev, dtype=torch.float16 if a.obs_half else torch.float32)
        b_hq = torch.zeros(T, N, H, dtype=torch.float16) if ATT_MEM else None   # (--attn-mem-query) his memory of the frame before, as played
        TOK_ = C.get("tok")                                              # (v0.4.1) the brain token: its state, the numbers each frame as played
        b_btok, btg_ = None, float(C.get("btg", 0.0))
        rfg_ = float(C.get("rfg", 0.0))                                  # (v0.4.2a) the rule fade's gate of this rollout
        if RF:
            net.rfg = rfg_                                               # (--overlap: the copy that plays has no gate of its own)
        if TOK_ is not None:
            net.attn.bgate = btg_                                        # (--overlap: the copy that plays has no gate of its own)
            b_btok = torch.zeros(N, T, BTOK_L["dim"], dtype=torch.float16) if OVL else torch.zeros(T, N, BTOK_L["dim"], dtype=torch.float16, device=dev)
            AUXC_ = tuple(E_.AUX_COLS)
        if LONG:
            b_rl = torch.zeros(T, N, device=dev)                             # the pay for items and stack, frame by frame
            b_val2 = torch.zeros(T + 1, N, 2, device=dev)                    # ... as he estimates it at --gamma and at --long-gamma
        b_act = torch.zeros(T, N, len(ACTION_DIMS), dtype=torch.long, device=dev)
        b_logp = torch.zeros(T, N, device=dev)
        b_val = torch.zeros(T + 1, N, device=dev)
        b_rew = torch.zeros(T, N, device=dev)
        b_done = torch.zeros(T, N, device=dev)
        b_w = torch.zeros(T, N, device=dev)
        b_live = torch.zeros(T, N, device=dev)                           # the intention head was read on that frame
        b_dec = torch.zeros(T, N, device=dev)                            # the left hand's outputs (keys, weapon key) were read on that frame
        b_ll = torch.zeros(T, N, device=dev)                             # (LEGS) the switch to his legs was read on that frame
        b_so = torch.zeros(T, N, device=dev)                             # (--solo-self-drive) in his runs: the switch's lesson silent
        b_lo = torch.zeros(T, N, device=dev)                             # ... his legs moved him on that frame
        if LEGS_LEARN or UNI_ON:                                         # (--legs-learn) the branch's inputs (off the card: 0.9 GB at 10,080
            b_lx = torch.zeros(T, N, LEGS_D)                             # players), its own draws and their log-probability as it played
        if LEGS_LEARN:                                                   # (--legs-feat, --legs-guide: the inputs alone)
            b_lr = torch.full((T, N, 4), -1, dtype=torch.int8, device=dev)
            b_llp = torch.zeros(T, N, device=dev)
        b_lab = torch.full((T, N, 5), -1, dtype=torch.int8, device=dev) if LEGS_LAB else None   # (--legs-teach) his legs' four choices on that frame
        #                                                                  (-1: no label), and that the stretch was withheld (LEGS_KEEP)
        b_iteach = torch.zeros(T, N, dtype=torch.long, device=dev)       # what the item rule would have chosen
        b_teach = torch.zeros(T, N, 5, dtype=torch.long, device=dev)
        if AUX_W > 0:
            b_aux = torch.zeros(T + 1, N, len(AUX_COLS), dtype=torch.float16)    # (--aux) the simulator's truth, frame by frame
        elif TRK_ON:                                                     # (--track, --info-pay) the same truth, for the readout alone
            b_aux = torch.zeros(T + 1, N, len(E_.AUX_COLS), dtype=torch.float16)
        TS_ = trk_stats_new() if TRK_ON else None                         # (--track) the readout's counters of this rollout
        TK_ = float(TRK_K[0]) if TRK_ON else 0.0                          # (--info-pay) the pay's k in this rollout
        if AUX_W > 0:
            b_ht = torch.zeros(AUX_TW, N, H, dtype=torch.float16) if AUX_TW else None      # (--aux-tail) his memory on the last frames
            b_bel = torch.zeros(T + 1, N, 5) if AUX_BEL else None                       # (--aux-fresh, --aux-measure) his belief inputs, raw
        h0 = h.clone()
        b_u2 = b_vh = b_lpi = h2s0 = None
        if H2:                                                           # (--head2) its ticks' inputs (host, half precision), its value, the
            b_u2 = torch.zeros(T // BK, N, head2_.u_width(H2L), dtype=torch.float16)      # intention's log-probability as played; the
            b_vh = torch.zeros(T + 1, N, device=dev)                     # held outputs made again with the weights it plays with; its start
            b_lpi = torch.zeros(T, N, device=dev)
            H2S.refresh(net.head2)
            if has_snaps and onet.h2_open:
                H2O.refresh(onet.head2)
            h2s0 = H2S.snap()
        BS_ = C.get("bs")                                                # (--belief) its live state; kept at the start for the update
        if WV_ON and WV_ST[0] is None:                                   # (--win-value) the per-seat stream, carried from rollout to rollout
            WV_ST[0] = wv_.Stream(WV_L, N, "cpu", group=2)            # (on the host: a few vectors a frame)
        if CTL_ON:                                                       # (--control) this rollout's first global row; the ring
            CTL_G0[upd] = CTL_G[0]
            if CTL_RING[0] is None:
                CTL_RING[0] = control_.Ring(CTL_L, N, T)
                print("control: the ring of states, {} slots of {} x {} ({:.2f} GB on the host)".format(
                    CTL_RING[0].S, N, CTL_L["width"], CTL_RING[0].nbytes() / 1e9), flush=True)
        bs0 = None
        if BS_ is not None:
            assert float(BS_.cnt.abs().max()) == 0.0, "the belief's rollout must start on a tick's boundary"
            bs0 = BS_.s.clone()
        if HEADL:                                                        # (--head) the rollout's events, win labels; the ring folded and
            t_hd = time.time()                                           # re-run as the slow memory's; he plays from the state the update
            b_ev = torch.zeros(HD_J, N, HEADL["ev"], device=dev)         # re-runs; its start kept for the update
            b_wg = torch.full((T, N), -1.0, device=dev)                  # (win_game, win_band of each frame: none until read)
            b_wb = torch.full((T, N), -1.0, device=dev)
            HS_O.g = HS.g                                                # (a league network whose head is shut skipped the frames)
            if RINGH is not None:
                RINGH.trim(net.head)
                head_.refresh(net.head, HS, RINGH.state_all(net.head))
            HD_RS0, HD_PEND, HD0 = HS.rs.clone(), [], HS.snap()
            hd_secs = [time.time() - t_hd, 0.0]
        if SLOW:                                                         # (--slow-mem) the ring's ticks beyond its length folded into its
            t_sl = time.time()                                           # stored state; he plays from the state the update re-runs
            RING.trim(net.slow)
            SM.s = RING.state_all(net.slow) * (1.0 - SM.rs)[:, None]
            SL_RS0, SL_PEND, SL_S0 = SM.rs.clone(), [], SM.s.clone()
            sl_secs = [time.time() - t_sl, 0.0]
        raw, agg, agg_map = [], {}, {}
        trips = []                                                       # (WAYS) his finished trips: they join WAY_STORE after the rollout
        lk = [0, 0]                                                      # league matches: learner kills, snapshot kills
        t_roll = time.time()                                             # (the record's "time": the rollout's seconds, the learning step's)
        if dev.type == "cuda" and not OVL:                               # (--overlap: at the learning step's start)
            torch.cuda.reset_peak_memory_stats()
        RP_ = dict(net=0.0, legs_net=0.0, send=0.0, wait=0.0, gather=0.0)   # (time.rollout_parts) the trainer's seconds of the rollout by part
        for t in range(T):
            if stop is not None and stop.is_set():                       # (--overlap) the run is over: the rollout is let go
                return None
            tp0_ = time.perf_counter()
            if keep_raw:
                raw.append(obs if obs_count < OBS_FREEZE else obs[np.random.rand(len(obs)) < 0.005])
            xc_ = torch.from_numpy(norm(obs))
            x = xc_.to(dev)
            if ATT_MEM:
                b_hq[t] = h.half().cpu()
            ev_ = None
            bt_t = None
            if TOK_ is not None:                                         # (v0.4.1) the last tick's answer turned to his pose now
                pose_, zm_ = btoken_.pose_from_aux(aux, AUXC_)
                TOK_.see(obs)
                bt16_ = torch.from_numpy(TOK_.features(pose_, zm_))
                if OVL:
                    b_btok[:, t] = bt16_
                else:
                    b_btok[t] = bt16_.to(dev)
                bt_t = bt16_.to(dev).float()
            xlu_ = torch.from_numpy(legs_x).to(dev) if UNI_ON else None  # (--legs-feat, --legs-guide) the branch's inputs of this frame
            if HEADL and (HS.g + 1) % HD_K == 0:                         # (--head) a tick: the simulators' events since the last
                ev_ = head_events()
                b_ev[t // HD_K] = ev_
            with torch.no_grad():
                if HEADL:
                    t_hd = time.time()
                    logits, val, h = net.step(x, h, hd=HS, ev=ev_, xl=xlu_)
                    if RINGH is not None and HS.ticked:                  # (--head) the tick's input, for the ring
                        HD_PEND.append((HS.u.half().cpu(), HS.r_tick.cpu()))
                    hd_secs[0] += time.time() - t_hd
                else:
                    logits, val, h = net.step(x, h, sm=SM, xl=xlu_, bt=bt_t, g2=H2S.adds(net.head2) if H2 else None)
                    if H2:                                               # (--head2) its value of this frame (before its tick)
                        b_vh[t] = head2_.value(net.head2, H2S.s, h)
                if SM is not None and SM.ticked:                         # (--slow-mem) the tick's input, for the ring
                    SL_PEND.append((SM.u.half().cpu(), SM.r_tick.cpu()))
                bt_ = BS_ is not None and BS_.frame(net.belief, x.half().float() if a.obs_half else x, (t + 1) % BK == 0)
                if bt_ and CTL_ON and CTL_RING[0].kept(CTL_G0[upd] + t):  # (--control) the state of this tick, kept every --control-every ticks
                    CTL_RING[0].push(CTL_G0[upd] + t, BS_.s if int(CTL_L["mem"]) == 0 else torch.cat([BS_.s.float(), h[:, :H].float()], 1))
                if H2 and bt_:                                           # (--head2) a tick with the brain's: what it knows, his stack, the hands' memory
                    sb_ = BS_.s
                    rd_ = dict(brain=sb_, trk=net.track(sb_), trz=net.trackz(sb_) if TRZ else None, ahead=net.ahead(sb_) if AH else None,
                               obs=x)
                    u2_ = head2_.feats(H2L, hands=h, ctrl=head2_.control_t(net, sb_, h, head2_.ctrl_src(H2L)), **rd_)
                    b_u2[t // BK] = u2_.half().cpu()
                    H2S.tick(net.head2, u2_)
                    if has_snaps and onet.h2_open:                       # (the league's own head on the same brain's answer, its own hands)
                        H2O.tick(onet.head2, head2_.feats(H2L, hands=h_opp, ctrl=head2_.control_t(net, sb_, h_opp, head2_.ctrl_src(H2L)), **rd_))
                if bt_ and TOK_ is not None:                             # (v0.4.1) a tick: the readouts' answer, kept in map coordinates
                    TOK_.answer(None, net.track(BS_.s).float().cpu().numpy(), net.trackz(BS_.s).float().cpu().numpy() if TRZ else None, pose_, zm_)
                    if BA_SEND:                                          # (v0.4.3, BLIND_AHEAD) ... and the readout ahead's places, kept so too
                        TOK_.answer_fut(net.ahead(BS_.s).float().cpu().numpy(), pose_)
                #                                                          (--belief) every seat at once: the inputs as the update re-reads them
                if LONG:
                    b_val2[t] = net.v2(net.zl)
                if ORDER:                                                # (--ordered-heads) drawn in order
                    act, ds = draw(net, logits)
                else:
                    ds = dists(logits)
                    act = torch.stack([d.sample() for d in ds], -1)
                lps = [d.log_prob(act[:, i]) for i, d in enumerate(ds)]
                if H2:                                                   # (--head2) the intention as played, for its own ratio
                    b_lpi[t] = lps[I_HEAD]
                if has_snaps and HEADL:                                      # (--head) the league's network with its own head, if open
                    lo, _, h_opp = onet.step(x, h_opp, hd=HS_O if onet.head_open else None, ev=ev_, xl=xlu_)
                    act_o = draw(onet, lo)[0] if ORDER else torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
                elif has_snaps:
                    lo, _, h_opp = onet.step(x, h_opp, sm=SM_O, xl=xlu_, bt=bt_t, g2=H2O.adds(onet.head2) if (H2 and onet.h2_open) else None)
                    act_o = draw(onet, lo)[0] if ORDER else torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
            if WV_ON and bt_ and wv_.kept(WV_L, t):                      # (--win-value) a kept tick: the brain's state, each seat's own hands' memory
                with torch.no_grad():
                    hm_ = torch.where(snap_players[:, None], h_opp, h) if has_snaps else h
                    wx_ = torch.cat([BS_.s.float(), hm_[:, :H].float()], 1).half()
                    WV_ST[0].keep(wx_, WV_ACT(wx_.float()).squeeze(-1))
            if NO_SW:                                                    # (--no-switch) off for his seats, and for the league's when its network
                act[:, L_HEAD] = torch.where(snap_players & has_snaps & (not opp_ns), act[:, L_HEAD], torch.zeros_like(act[:, L_HEAD]))
                #                                                          is a step-6 one (its file's env_vars: NO_SWITCH=1); v0.3.4's snapshots and
                #                                                          the control keep their own switch and legs, as they were trained
            if OVL:
                b_obs[:, t] = xc_
                b_act[t], b_val[t] = act, val
            else:
                b_obs[t], b_act[t], b_val[t] = x, act, val
            if AUX_TW and t >= T - AUX_TW:                               # (--aux-tail) his memory as he played the rollout's last frames
                b_ht[t - (T - AUX_TW)] = net.zl.half().cpu()             # (--slow-mem: what the outputs read; h with it off)
            if AUX_BEL:                                                  # (--aux-fresh, --aux-measure) his belief inputs on this frame
                b_bel[t] = torch.from_numpy(np.ascontiguousarray(obs[:, BEL_IX], dtype=np.float32))
                if upd == 1:
                    bel_check(obs)
            b_w[t] = learn * (1.0 - scr)
            b_teach[t] = torch.from_numpy(teach).to(dev)
            if HAND_LAB:
                b_hand[t] = torch.from_numpy(hand).to(dev)
            if RJ_LAB:
                b_rj[t] = torch.from_numpy(rjl).to(dev)
            if RJC_LAB:
                b_rjc[t] = torch.from_numpy(rjc).to(dev)
            if b_aux is not None:                                        # (--aux; --track)
                b_aux[t] = torch.from_numpy(aux)
            tpay_ = None
            if TS_ is not None and (bt_ if BS_ is not None else t % a.info_every == 0):    # (--track, --info-pay) his readout scored, the pay
                tpay_ = trk_frame(net, aux, b_w[t], TS_, TK_, z=BS_.s if BS_ is not None else None)    # (added to the reward of this
                #                                                          frame's action, below; --belief: on its ticks, from its state)
            an = act.cpu().numpy()
            tp1_ = time.perf_counter()
            RP_["net"] += tp1_ - tp0_                                    # (his network on the card and its draws, the frame's buffers)
            if LEGS_IN:                                                  # (LEGS_IN) his legs' logits: the branch of each seat's network
                with torch.no_grad():
                    xl_ = torch.from_numpy(legs_x).to(dev)
                    lgl_ = net.legs_comb(legs_fwd(net, xl_), net.zl)            # (--legs-residual: from his memory of this frame)
                    if has_snaps:
                        lgl_ = torch.where(snap_players[:, None], onet.legs_comb(legs_fwd(onet, xl_), onet.zl), lgl_)
                if LEGS_LEARN or UNI_ON:
                    b_lx[t] = torch.from_numpy(legs_x)
                lgn_ = lgl_.float().cpu().numpy()
                tp2_ = time.perf_counter()
                RP_["legs_net"] += tp2_ - tp1_
                for w_, p in enumerate(pipes):
                    p.send(("step", (an[w_off[w_]:w_off[w_ + 1]], lgn_[w_off[w_]:w_off[w_ + 1]])
                            + ((TOK_.answer_rows(w_off[w_], w_off[w_ + 1]),) if RF_READ else ())))
            elif RF_READ:                                                # (v0.4.2a, BRAIN_READ) the brain's answer goes with the actions
                tp2_ = time.perf_counter()
                for w_, p in enumerate(pipes):
                    p.send(("step", (an[w_off[w_]:w_off[w_ + 1]], None, TOK_.answer_rows(w_off[w_], w_off[w_ + 1]))))
            else:
                tp2_ = time.perf_counter()
                for w_, p in enumerate(pipes):
                    p.send(("step", an[w_off[w_]:w_off[w_ + 1]]))
            tp3_ = time.perf_counter()
            RP_["send"] += tp3_ - tp2_
            res = [p.recv() for p in pipes]
            tp4_ = time.perf_counter()
            RP_["wait"] += tp4_ - tp3_                                   # (the slowest worker's step and its reply: pickling, the pipe)
            obs = np.concatenate([r[0] for r in res])
            if LEGS_IN:
                legs_x = legs_cat([(r[15], r[0]) for r in res])
            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)
            if tpay_ is not None:                                        # (--info-pay) zero-sum over each pair of seats
                b_rew[t] += tpay_
            if LONG:
                b_rl[t] = torch.from_numpy(np.concatenate([r[11] for r in res])).to(dev)
            d = torch.from_numpy(np.concatenate([r[2] for r in res]).astype(np.float32)).to(dev)
            b_done[t] = d
            if WV_ON:                                                    # (--win-value) the frame's shadow pay, cut, in a game
                wp_ = torch.from_numpy(np.concatenate([r[20] if r[20] is not None else np.zeros((len(r[2]), 3), np.float32) for r in res]))
                WV_ST[0].frame(wp_[:, 0], wp_[:, 1], wp_[:, 2] > 0)
            if HEADL and HD_WG >= 0:                                     # (--head) the frame's game and, on its last frame, its band (BUILD 3a:
                wl_ = np.concatenate([r[12][:, [HD_WG, HD_WB]] if r[12] is not None else np.full((len(r[2]), 2), -1.0)   # the info of the step
                                      for r in res]).astype(np.float32)                                                  # that played frame t)
                b_wg[t] = torch.from_numpy(wl_[:, 0]).to(dev)
                b_wb[t] = torch.from_numpy(wl_[:, 1]).to(dev)
            live = torch.from_numpy(np.concatenate([r[6] for r in res]).astype(np.float32)).to(dev)
            b_live[t] = live
            b_iteach[t] = torch.from_numpy(np.concatenate([r[7] for r in res])).to(dev)
            dec = torch.from_numpy(np.concatenate([r[8] for r in res]).astype(np.float32)).to(dev)
            if JE:                                                       # (JUMP_EVERY) the code: 1 the hand read, 2 the jump alone was read
                jcode = dec.long()
                dec = (jcode == 1).float()
            b_dec[t] = dec
            ll = torch.from_numpy(np.concatenate([r[9] for r in res]).astype(np.float32)).to(dev)
            lo = torch.from_numpy(np.concatenate([r[10] for r in res]).astype(np.float32)).to(dev)
            b_ll[t], b_lo[t] = ll, lo
            b_so[t] = torch.from_numpy(np.concatenate([r[17] for r in res]).astype(np.float32)).to(dev)   # (--solo-self-drive)
            if LEGS_LAB:
                b_lab[t] = torch.from_numpy(np.concatenate([r[13] for r in res])).to(dev)
            # an output's part counts only on the frames its choice was read: the intention's when it was read, the left
            # hand's (keys, weapon key) on the one frame in four it decides on (until 2026-10-08 all four were counted and
            # three were noise), the switch to his legs when it was read, what his legs take only while he moves himself
            if JE:                                                       # (JUMP_EVERY) between the hand's readings only the jump bit was his
                av_ = jump_only(act[:, V_HEAD], jcode)
                b_act[t, :, V_HEAD] = av_.to(b_act.device)
                lps[V_HEAD] = ds[V_HEAD].log_prob(av_)
            b_logp[t] = sum(lp_ if m_ is None else lp_ * m_ for lp_, m_ in zip(lps, head_masks(dec, live, ll, lo, act, b_so[t])))
            if LEGS_LEARN:                                               # (--legs-learn) the branch's own draws (before the hand rule) join
                b_lr[t] = torch.from_numpy(np.concatenate([r[16] for r in res])).to(dev)        # what he did on the frames his legs moved him
                with torch.no_grad():
                    b_llp[t] = legs_lp(lgl_, b_lr[t], dec, lo)[0]
                b_logp[t] = b_logp[t] + b_llp[t]
            scr = torch.from_numpy(np.concatenate([r[4] for r in res]).astype(np.float32)).to(dev)
            teach = np.concatenate([r[5] for r in res])
            if HAND_LAB:
                hand = np.concatenate([r[14] for r in res])
            if RJ_LAB:                                                   # (--rj-teach; a simulator without it: none)
                rjl = np.concatenate([r[18] if r[18] is not None else np.zeros(len(r[2]), np.int8) for r in res]).astype(np.int8)
            if RJC_LAB:                                                  # (--rj-copy; a simulator without it: none)
                rjc = np.concatenate([r[19] if (len(r) > 19 and r[19] is not None) else np.full((len(r[2]), RJC_H), -1, np.int8)
                                      for r in res]).astype(np.int8)
            if AUX_W > 0 or TRK_ON:
                aux = np.concatenate([r[12] for r in res])
            h = h * (1.0 - d)[:, None]                                   # memory resets on death / round restart
            h_opp = h_opp * (1.0 - d)[:, None]
            if BS_ is not None:                                          # (--belief) ... and the belief's, by the same flag
                BS_.reset(d)
            if TOK_ is not None:                                         # (v0.4.1) ... and the token's answer
                TOK_.reset(d.cpu().numpy())
            if SM is not None:                                           # (--slow-mem) ... and the slow memory's
                SM.reset(d)
                SM_O.reset(d)
            if HS is not None:                                           # (--head) ... and the head's
                HS.reset(d)
                HS_O.reset(d)
            if H2S is not None:                                          # (--head2) ... and the strategy head's
                H2S.reset(d)
                H2O.reset(d)
            for w_, r in enumerate(res):
                for k, v in r[3].items():
                    if isinstance(v, list):
                        continue
                    if not w_move[w_]:                                   # (a move-only simulator: by map only)
                        agg[k] = agg.get(k, 0) + v
                    if k in MAP_KEYS:
                        am_ = agg_map.setdefault(w_map[w_], {})
                        am_[k] = am_.get(k, 0) + v
                for tr_ in r[3].get("way_trips", ()):                    # (WAYS) his finished trips between two places, by map and pair
                    trips.append((w_map[w_], int(tr_[0]), int(tr_[1]), tr_[2:]))
                for mk, ek in zip(r[3]["match_of_kill"], r[3]["even_kill"]):
                    if mk >= w_match[w_] // 2:                           # second half of the worker = league matches
                        lk[0 if ek else 1] += 1
            RP_["gather"] += time.perf_counter() - tp4_                  # (the replies put together and onto the card, the counters)
        for p in pipes:                                                  # (time.rollout_parts) the workers' own seconds of this rollout
            p.send(("times", None))
        tw_all_ = [p.recv() for p in pipes]
        RP_ = {k_: round(v_, 2) for k_, v_ in RP_.items()}
        for k_ in ("step", "legs_prep", "send", "idle"):                 # (the workers': mean and slowest, seconds of the rollout)
            v_ = [float(x_.get(k_, 0.0)) for x_ in tw_all_]
            RP_["worker_" + k_] = [round(float(np.mean(v_)), 2), round(float(np.max(v_)), 2)] if v_ else None
        with torch.no_grad():
            if HEADL:                                                    # (--head) the frame after the rollout: never a tick (T is whole ticks)
                _, vT_, hT_ = net.step(torch.from_numpy(norm(obs)).to(dev), h, hd=HS.peek(),
                                       xl=torch.from_numpy(legs_x).to(dev) if UNI_ON else None)
            else:
                btT_ = None
                if TOK_ is not None:                                     # (v0.4.1) the frame after: the token on a copy (the next rollout's first
                    st_ = TOK_.state()                                   # frame makes it again from the same state)
                    TOK_.see(obs)
                    btT_ = torch.from_numpy(TOK_.features(*btoken_.pose_from_aux(aux, AUXC_))).to(dev).float()
                    TOK_.load(st_)
                _, vT_, hT_ = net.step(torch.from_numpy(norm(obs)).to(dev), h, sm=SM.peek() if SM is not None else None,
                                       xl=torch.from_numpy(legs_x).to(dev) if UNI_ON else None, bt=btT_,
                                       g2=H2S.adds(net.head2) if H2 else None)
                if H2:
                    b_vh[T] = head2_.value(net.head2, H2S.s, hT_)
            b_val[T] = vT_
            if LONG:
                b_val2[T] = net.v2(net.zl)
        if b_aux is not None:                                            # (--aux; --track)
            b_aux[T] = torch.from_numpy(aux)
        if AUX_W > 0:
            if AUX_BEL:
                b_bel[T] = torch.from_numpy(np.ascontiguousarray(obs[:, BEL_IX], dtype=np.float32))
        ctl_b = None
        if CTL_ON:
            CTL_G[0] = CTL_G0[upd] + T                                   # (--control) the next rollout's rows follow on
            if b_aux is not None:                                        # ... the rows whose label came in this rollout, taken out
                ctl_b = control_.batch(CTL_RING[0], CTL_G0[upd], b_aux, TRK_IX, int(CTL_L["horizon"]))   # now, before the next
            CTL_G0.pop(upd, None)                                        # rollout writes over the ring (with --overlap too)
        t_done = time.time() if OVL else None
        C.update(obs=obs, teach=teach, hand=hand, aux=aux, legs_x=legs_x, scr=scr, h=h, h_opp=h_opp, rjl=rjl, rjc=rjc)
        return dict(b_obs=b_obs, b_hq=b_hq, b_rl=b_rl, b_val2=b_val2, b_act=b_act, b_logp=b_logp, b_val=b_val, b_rew=b_rew,
                    b_done=b_done, b_w=b_w, b_live=b_live, b_dec=b_dec, b_ll=b_ll, b_so=b_so, b_lo=b_lo, b_lx=b_lx, b_lr=b_lr,
                    b_llp=b_llp, b_lab=b_lab, b_iteach=b_iteach, b_teach=b_teach, b_aux=b_aux, b_ht=b_ht, b_bel=b_bel, b_ev=b_ev,
                    b_wg=b_wg, b_wb=b_wb, b_hand=b_hand, b_rj=b_rj, b_rjc=b_rjc, ctl_b=ctl_b, h0=h0, raw=raw, agg=agg, agg_map=agg_map, lk=lk, trips=trips,
                    keep_raw=keep_raw, t_roll=t_roll, t_done=t_done, HD_RS0=HD_RS0, HD_PEND=HD_PEND, HD0=HD0, hd_secs=hd_secs,
                    SL_RS0=SL_RS0, SL_PEND=SL_PEND, SL_S0=SL_S0, sl_secs=sl_secs, RP=RP_, trk=trk_stats_end(TS_, TK_), bs0=bs0,
                    b_btok=b_btok, btg=btg_, rfg=rfg_, b_u2=b_u2, b_vh=b_vh, b_lpi=b_lpi, h2s0=h2s0,
                    h2g=float(net.head2.gate) if H2 else 0.0, wv=WV_ST[0].take() if WV_ON else None)

    def launch(upd):
        """(--overlap) between two rollouts: what comes before rollout `upd`, pol copied into ACT, the rollout started in a thread"""
        RM_ = pre_rollout(upd)
        kr_ = obs_count < OBS_FREEZE or (bool(a.obs_dump) and a.obs_dump_from <= upd <= a.obs_dump_to)
        with torch.no_grad():
            sp_ = pol.state_dict()
            for k_, v_ in ACT.state_dict().items():
                v_.copy_(sp_[k_])
        ACT.fade = pol.fade
        if WV_ON and WV_ACT is not WV:                                   # (--win-value) the copy the rollout's values come from
            with torch.no_grad():
                for p_, q_ in zip(WV_ACT.parameters(), WV.parameters()):
                    p_.copy_(q_)
        if dev.type == "cuda":
            torch.cuda.synchronize()                                     # (the copies and the league's network are in place)
        box = dict(meta=RM_, R=None, err=None, upd=upd)

        def run_():
            try:
                if RS is not None:
                    with torch.cuda.stream(RS):
                        box["R"] = rollout(ACT, opp, CARRY, upd, kr_, RM_["has_snaps"], RM_["opp_ns"], STOP)
                        RS.synchronize()
                else:
                    box["R"] = rollout(ACT, opp, CARRY, upd, kr_, RM_["has_snaps"], RM_["opp_ns"], STOP)
            except BaseException:                                        # noqa: BLE001  (raised again in the main thread)
                import traceback
                box["err"] = traceback.format_exc()
        box["th"] = threading.Thread(target=run_, name="rollout {}".format(upd), daemon=True)
        box["th"].start()
        return box

    def join(box):
        """(--overlap) the rollout started by launch(), once it is over"""
        box["th"].join()
        if box["err"] is not None:
            raise RuntimeError("the rollout's thread (update {}) failed:\n{}".format(box["upd"], box["err"]))
        return box["R"]

    PEND, R, t_prev = None, None, None                                   # (--overlap) the rollout in flight; the last rollout's buffers
    PREV_SD = [None]                                                     # (--step-kl-pieces) pol before the last update's learning
    upd0_ = update
    while time.time() - t_start < a.minutes * 60 and not (a.max_updates > 0 and update - upd0_ >= a.max_updates):
        update += 1
        ovl_wait = 0.0
        if not OVL:
            RM = pre_rollout(update)
            R = None
            # the last rollout's buffers are let go before the new ones are made: the input buffer alone is 4.7 GiB with
            # 6,800 players, and two of them alive at once is what filled the card (15.8 GB) and broke the cap (2026-10-06)
            b_obs = b_act = b_logp = b_val = b_rew = b_done = b_w = b_live = b_dec = b_ll = b_lo = b_iteach = b_teach = b_rl = b_val2 = None
            b_lx = b_lr = b_llp = None
            if dev.type == "cuda":
                torch.cuda.empty_cache()
            keep_raw = obs_count < OBS_FREEZE or (bool(a.obs_dump) and a.obs_dump_from <= update <= a.obs_dump_to)
            R = rollout(pol, opp, CARRY, update, keep_raw, RM["has_snaps"], RM["opp_ns"])
        else:
            if PEND is None:                                             # (the first rollout: started and waited for)
                PEND = launch(update)
            t_w = time.time()
            R_new = join(PEND)
            ovl_wait = time.time() - t_w                                 # the main thread's wait for the rollout
            RM, PEND = PEND["meta"], None
            if dev.type == "cuda":
                torch.cuda.synchronize()                                 # (the last learning step is over before its buffers go)
            R = None
            # the last rollout's buffers are let go before the new ones are made: the input buffer alone is 4.7 GiB with
            # 6,800 players, and two of them alive at once is what filled the card (15.8 GB) and broke the cap (2026-10-06)
            b_obs = b_act = b_logp = b_val = b_rew = b_done = b_w = b_live = b_dec = b_ll = b_lo = b_iteach = b_teach = b_rl = b_val2 = None
            b_lx = b_lr = b_llp = None
            if dev.type == "cuda":
                torch.cuda.empty_cache()
            R, R_new = R_new, None
        b_obs, b_hq, b_rl, b_val2, b_act, b_logp, b_val, b_rew = (R[k_] for k_ in ("b_obs", "b_hq", "b_rl", "b_val2", "b_act", "b_logp", "b_val", "b_rew"))
        if os.environ.get("ROLL_DUMP"):                                   # (identity checks) the rollout as played
            os.makedirs(os.environ["ROLL_DUMP"], exist_ok=True)
            torch.save({k_: (R[k_].detach().cpu().clone() if torch.is_tensor(R[k_]) else None) for k_ in
                        ("b_act", "b_logp", "b_val", "b_rew", "b_done", "b_obs", "b_w", "b_iteach")},
                       os.path.join(os.environ["ROLL_DUMP"], "roll_{}.pt".format(update)))
        b_done, b_w, b_live, b_dec, b_ll, b_so, b_lo, b_lx = (R[k_] for k_ in ("b_done", "b_w", "b_live", "b_dec", "b_ll", "b_so", "b_lo", "b_lx"))
        b_lr, b_llp, b_lab, b_iteach, b_teach, b_aux, b_ht, b_bel = (R[k_] for k_ in ("b_lr", "b_llp", "b_lab", "b_iteach", "b_teach", "b_aux", "b_ht", "b_bel"))
        b_ev, b_wg, b_wb, b_hand, h0, raw, agg, agg_map, lk = (R[k_] for k_ in ("b_ev", "b_wg", "b_wb", "b_hand", "h0", "raw", "agg", "agg_map", "lk"))
        keep_raw, t_roll = R["keep_raw"], R["t_roll"]
        b_rj = R.get("b_rj")                                             # (--rj-teach)
        b_rjc = R.get("b_rjc")                                           # (--rj-copy)
        CTL_B = R.pop("ctl_b", None)                                     # (--control) this rollout's labelled states
        WV_B = R.pop("wv", None)                                         # (--win-value) this rollout's kept states, segments and counters
        BS0 = R.get("bs0")                                               # (--belief) its state at the rollout's start
        if H2:                                                           # (--head2) its ticks' inputs, values and the intention as played; learnt
            B_U2, B_VH, B_LPI, H2_S0V0, H2G_R = R["b_u2"], R["b_vh"], R["b_lpi"], R["h2s0"], float(R["h2g"])    # at the gate it was played at
            with torch.no_grad():
                pol.head2.gate.fill_(H2G_R)
        B_BTOK, BTG_R = R.get("b_btok"), float(R.get("btg") or 0.0)      # (v0.4.1) the token as he saw it, the gate he played at
        if BTOK:
            pol.attn.bgate = BTG_R if B_BTOK is not None else 0.0        # (learnt at the gate it was played at)
        RFG_R = float(R.get("rfg") or 0.0)                               # (v0.4.2a) the rule fade's gate he played at: learnt at it
        if RF:
            pol.rfg = RFG_R
        if a.dump_acts:                                                  # (--dump-acts) the rollout as played, for a fixed-seed identity check
            torch.save(dict(act=b_act.cpu(), logp=b_logp.cpu(), val=b_val.cpu(), rew=b_rew.cpu(), done=b_done.cpu()),
                       "{}_{}.pt".format(a.dump_acts, update))
        if HEADL:
            HD_RS0, HD_PEND, HD0, hd_secs = R["HD_RS0"], R["HD_PEND"], R["HD0"], R["hd_secs"]
        if SLOW:
            SL_RS0, SL_PEND, SL_S0, sl_secs = R["SL_RS0"], R["SL_PEND"], R["SL_S0"], R["sl_secs"]
        for m_, f_, t_, p_ in R["trips"]:                                # (WAYS) his finished trips between two places, by map and pair
            l_ = WAY_STORE.setdefault(m_, {}).setdefault((f_, t_), [])
            l_.append(p_)
            del l_[:-WAY_KEEP]
        mins, LIVE_REC, close_p, seek_now = RM["mins"], RM["live_rec"], RM["close_p"], RM["seek_now"]
        LS_REC = RM.get("live_settings")                                # (live_settings.env) read before this rollout
        R_VA, R_SN, R_NS = RM["vs_anchor"], RM["has_snaps"], RM["n_snaps"]    # (the league of this rollout: --overlap changes it before the record)
        if obs_count < OBS_FREEZE:
            flat = np.concatenate(raw)
            bm, bv, bc = flat.mean(0), flat.var(0), len(flat)
            delta, tot = bm - obs_mean, obs_count + bc
            obs_mean = obs_mean + delta * bc / tot
            obs_var = (obs_var * obs_count + bv * bc + delta ** 2 * obs_count * bc / tot) / tot
            obs_count = tot
        elif keep_raw:                                                   # a sample of raw inputs for sim/renorm_policy.py
            dump.append(np.concatenate(raw).astype(np.float32))
            if update == a.obs_dump_to:
                np.save(a.obs_dump, np.concatenate(dump))
                print("wrote {} rows of raw inputs to {}".format(sum(len(d_) for d_ in dump), a.obs_dump), flush=True)
                dump = []
        if OVL and time.time() - t_start < a.minutes * 60 and not (a.max_updates > 0 and update - upd0_ >= a.max_updates):   # (--overlap) the next rollout plays while this update learns
            PEND = launch(update + 1)
        t_learn = time.time()
        T_ROLL = t_learn - t_roll if not OVL else R["t_done"] - t_roll   # the rollout's seconds (--overlap: its thread's own)
        if OVL and dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats()
        def gae_():
            """the advantages and value targets from b_val (b_val2) -> (adv, ret, ret2, long_c, long_gap)"""
            ret2 = None
            adv = torch.zeros(T, N, device=dev)
            last = torch.zeros(N, device=dev)
            for t in reversed(range(T)):
                nonterm = 1.0 - b_done[t]
                dl = b_rew[t] + gamma * b_val[t + 1] * nonterm - b_val[t]
                last = dl + gamma * lam * nonterm * last
                adv[t] = last
            ret = adv + b_val[:T]
            long_c, long_gap = 0.0, 0.0
            if LONG:                                                         # the pay for items and stack: what counting it two minutes ahead adds
                long_c = min(1.0, max(0.0, mins - fade0) / a.long_ramp) if a.long_ramp > 0 else 1.0
                adv2 = torch.zeros(T, N, 2, device=dev)
                last2 = torch.zeros(N, 2, device=dev)
                g2 = torch.tensor([gamma, a.long_gamma], device=dev)
                for t in reversed(range(T)):
                    nt2 = (1.0 - b_done[t])[:, None]
                    dl2 = b_rl[t][:, None] + g2 * b_val2[t + 1] * nt2 - b_val2[t]
                    last2 = dl2 + g2 * lam * nt2 * last2
                    adv2[t] = last2
                ret2 = adv2 + b_val2[:T]
                long_gap = float((adv2[..., 1] - adv2[..., 0]).abs().mean() / (adv.abs().mean() + 1e-8))
                if a.long_cap > 0 and long_c * long_gap > a.long_cap:
                    long_c = a.long_cap / long_gap
                adv = adv + long_c * (adv2[..., 1] - adv2[..., 0])
            return adv, ret, ret2, long_c, long_gap
        ret2 = None
        if not DEC:
            adv, ret, ret2, long_c, long_gap = gae_()
        frac = min(1.0, mins / a.lr_minutes) if a.lr_minutes > 0 else min(1.0, (time.time() - t_start) / (a.minutes * 60))
        if BEL:                                                          # (v0.4.1, live.json's BELIEF_LR) the brain's group's share
            for g in opt.param_groups:
                if any(p_ is pol.belief.inp.weight for p_ in g["params"]):
                    g["lr_scale"] = BEL_LR_NOW[0]
        for g in opt.param_groups:                                       # (--legs-learn: the branch's group keeps its share, lr_scale)
            g["lr"] = a.lr * (1.0 - (1.0 - a.lr_end) * frac) * g.get("lr_scale", 1.0)
        lr_now = a.lr * (1.0 - (1.0 - a.lr_end) * frac)
        if a.lr_warm > 0:
            lr_now *= min(1.0, 0.1 + 0.9 * max(0.0, mins - fade0) / a.lr_warm)
            for g in opt.param_groups:
                g["lr"] = lr_now * g.get("lr_scale", 1.0)
        n_mb = a.minibatches
        DN_H = b_done.cpu() if NOSYNC else None                          # (--learn-nosync) the done flags and the learner's frames on the
        WP_H = (b_w > 0).cpu() if NOSYNC else None                       # host, once an update (gru_layout, the advantages' frames)
        kick = a.teach * max(0.0, 1.0 - (mins - fade0) / a.teach_minutes)
        if a.teach_warm > 0:
            kick *= min(1.0, max(0.0, mins - fade0) / a.teach_warm)
        kick_l = torch.zeros(())
        ik = a.intent_teach * max(0.0, 1.0 - (mins - fade0) / a.intent_teach_minutes)
        if a.intent_teach_floor > 0:                         # (v0.3.1, the owner 2026-10-15: fade 2.0 -> 0.1, then hold)
            ik = max(a.intent_teach_floor, ik)
        if IT_LIVE[0] != 1.0:                                # (v0.4.3, live.json's INTENT_TEACH_W) the floor faded with it (1: as before)
            ik = ik * IT_LIVE[0]
        ik_l = torch.zeros(())
        wk = a.weapon_teach * max(0.0, 1.0 - (mins - fade0) / a.weapon_teach_minutes)
        wk_l = torch.zeros(())
        lt_w = a.legs_teach * (min(1.0, max(0.0, mins - fade0) / a.legs_teach_warm) if a.legs_teach_warm > 0 else 1.0)   # (--legs-teach)
        lt_acc = torch.zeros(4, 6, dtype=torch.float64, device=dev)      # ... per output: its frames, the sum of its loss, his likeliest choice is the label's,
        #                                                                  the chance he gives the label; its frames in withheld stretches, his likeliest right there
        lt_fr = torch.zeros(3, dtype=torch.float64, device=dev)          # ... the learner's frames, of them with a label, of those in withheld stretches
        hd_w = a.hand_teach * (min(1.0, max(0.0, mins - fade0) / a.hand_teach_warm) if a.hand_teach_warm > 0 else 1.0)   # (--hand-teach)
        rj_w, rj_fade = rj_teach_w(mins)                                 # (--rj-teach)
        rjc_w = rj_copy_w(mins)                                          # (--rj-copy)
        rjc_acc = torch.zeros(RJC_H + 1, 4, dtype=torch.float64, device=dev)    # ... per output: the frames it counts on, the sum of his chance of the
        #                                                                  label, he chose it, the loss; the last row: labelled frames, of them with every
        #                                                                  key output read, all those agreeing, the lesson's loss
        rj_acc = torch.zeros(12, dtype=torch.float64, device=dev)        # ... the learner's labelled frames; [jump, fire]: read, the sum of his chance of
        #                                                                  the label, he chose it, the loss; the loss of both, its frames
        hd_acc = torch.zeros(7, dtype=torch.float64, device=dev)         # ... the learner's frames, of them with a label, of those read by his hand; over the
        #                                                                  last: the sums of the loss, of the target's own entropy, of his chance of a choice
        #                                                                  other than "keep", of the target's
        demo_w = a.demo_coef * (max(0.0, 1.0 - (time.time() - t_start) / 60.0 / a.demo_minutes) if a.demo_minutes > 0 else 1.0)
        demo_l, demo_acc = torch.zeros(()), [0.0, 0.0, 0.0]
        if demo_w > 0 and update % 5 == 0:
            demo_refill()
        def slow_z(chunk, e_, hs_a):
            """(--slow-mem) what the outputs read over the rollout: the slow state re-run from the ring (the gradient reaches its
            ticks, minutes back), then the rollout's own ticks from these players' encoder and fast memory"""
            t_ = time.time()
            if torch.is_grad_enabled():
                s0_ = RING.state(pol.slow, chunk.cpu()) * (1.0 - SL_RS0[chunk])[:, None]
            else:                                                        # (the pass before the update's steps, --kl-heads: the weights
                s0_ = SL_S0[chunk]                                       # the rollout was played with, the state it started from)
            z_ = slowmem_.seq_z(pol.slow, SLOW, e_, hs_a, 1.0 - b_done[:, chunk], s0_)
            sl_secs[1] += time.time() - t_
            return z_

        HO_ = [None, [], False]                                          # (--head) the last seq_pass's head outputs; the read's numbers (first pass)
        HO2_ = [None]                                                    # (--head2) the last seq_pass's strategy head outputs

        def h2pi_(hs_):
            """his logits from his memory, the strategy head's bias added as a number (the hands' loss never moves the head)"""
            lg_ = pol.pi(hs_)
            if H2:
                HO2_[0]["hands_int"] = lg_[..., HD_I0:HD_I0 + int(H2L["n_target"])].detach()
                lg_ = head2_.add_bias(lg_, HO2_[0]["bias"].detach(), HD_I0)
            return lg_
        UG_ = [None, None, None]                                         # (--legs-feat, --legs-guide) the last seq_pass's guide addition, the
        #                                                                  branch's logits and its "has a way" (for pi_t and the counters)

        XS_ = [None]                                                     # (--belief) the last seq_pass's inputs [T, players, inputs]

        def b_btok_of(chunk):
            """(v0.4.1) the token of these players [T, players, F] on the card, from the rollout's buffer"""
            return B_BTOK[:, chunk] if not OVL else hsel(B_BTOK, 0, chunk).transpose(0, 1).contiguous()

        def seq_pass(chunk, hh):
            """his outputs over the rollout's whole sequences for these players: the encoder, the attention part and the output
            layers in one go each, only his memory frame by frame -> (logits, value, memories, the two long values or None)"""
            xs_ = b_obs[:, chunk].float() if not OVL else hsel(b_obs, 0, chunk).float().transpose(0, 1).contiguous()
            if BEL:
                XS_[0] = xs_                                             # (--belief) the same inputs, for the belief's lesson (unfaded)
            xs_ = pol.hx(xs_)                                            # (--rule-fade) the hands' inputs
            e_ = pol.enc(xs_)
            if pol.attn is not None:
                if ATT_MEM:                                              # (--attn-mem-query) the query reads h_{t-1} as he played it
                    btm_ = b_btok_of(chunk).reshape(-1, B_BTOK.shape[-1]).float() if (B_BTOK is not None and BTG_R > 0) else None
                    e_ = e_ + pol.attn(xs_.reshape(-1, OBS_DIM), hm=hsel(b_hq, 1, chunk).float().reshape(-1, H), bt=btm_, bg=BTG_R).view(T, len(chunk), -1)
                else:
                    btc_ = None
                    if B_BTOK is not None and BTG_R > 0:                 # (v0.4.1) the token's numbers as he saw them (none: shut, not there)
                        btc_ = (b_btok_of(chunk)).reshape(-1, B_BTOK.shape[-1]).float()
                    e_ = e_ + pol.attn(xs_.reshape(-1, OBS_DIM), bt=btc_, bg=BTG_R).view(T, len(chunk), -1)
            dadd_ = gadd_ = None
            if UNI_ON:                                                   # (--legs-feat, --legs-guide) the branch on this piece's inputs
                xlc_ = legs_x_of(chunk)
                dadd_, gadd_ = pol.uni_parts(xlc_)
                if UNI_GUIDE:
                    UG_[1], UG_[2] = LU_.t_branch(pol.legs, xlc_)[1], LU_.t_way(xlc_)
            eg_ = e_ if dadd_ is None else e_ + dadd_                    # (only his fast GRU reads the legs' features)

            def gd_(lg_, z_):                                    # (the parts that read his memory, the fade; UG_[0] for pi_t)
                UG_[0] = gadd_(z_) if gadd_ is not None else None
                return pol.out_(lg_, z_, (lambda _: UG_[0]) if UG_[0] is not None else None)
            if HEADL:                                                    # (--head) the fast GRU in segments of the head's ticks, the head between
                t_ = time.time()
                st0_ = {k_: v_[chunk] for k_, v_ in HD0.items()}        # (no ring; or the pass before the update's steps: the state played from)
                if RINGH is not None and torch.is_grad_enabled():        # the slow state re-run from the ring (the gradient reaches its ticks)
                    k_ = (1.0 - HD_RS0[chunk])[:, None]
                    s0_ = RINGH.state(pol.head, chunk.cpu()) * k_
                    st0_.update(s=s0_, plan=torch.tanh(pol.head.plan_out(s0_)) * k_)
                ho_ = head_.seq(pol.head, HEADL, e_, 1.0 - b_done[:, chunk], st0_, pol.gru, hh, b_ev[:, chunk],
                                stats=HO_[1] if HO_[2] else None, xg=dadd_)
                hs_a = ho_["hs"]
                lg_h = pol.pi(hs_a)
                ho_["hand_int"] = lg_h[..., HD_I0:HD_I0 + HEADL["n_target"]].detach()
                HO_[0] = ho_
                hd_secs[1] += time.time() - t_
                return gd_(head_logits(lg_h, ho_["tadd"], ho_["wadd"]), hs_a), pol.v(hs_a).squeeze(-1), hs_a, (pol.v2(hs_a) if LONG else None)
            if H2:                                                       # (--head2) its sequence from the stored ticks, its plan into his fast GRU
                ho2_ = head2_.seq(pol.head2, H2L, hsel(B_U2, 1, chunk).float(), 1.0 - b_done[:, chunk], H2_S0V0[0][chunk], H2_S0V0[1][chunk],
                                  plan_grad=H2_PG_[1])
                if HO_[2]:
                    with torch.no_grad():
                        ho2_["gin_share"] = ho2_["gin"].norm(dim=-1).mean() / (eg_.norm(dim=-1).mean() + 1e-8)
                eg_ = eg_ + ho2_["gin"]
                HO2_[0] = ho2_
            if a.fast_gru:                                               # (B-237) the library's GRU over whole sequences, cut at his resets
                hs_a = gru_seq(pol.gru, eg_, hh, b_done[:, chunk], lay=gru_layout(DN_H[:, hchunk(chunk)], dev) if NOSYNC else None)
            else:
                dn_ = (1.0 - b_done[:, chunk])[..., None]
                hs_l = []
                for t in range(T):
                    hh = pol.gru(eg_[t], hh)
                    hs_l.append(hh)
                    hh = hh * dn_[t]
                hs_a = torch.stack(hs_l)
            if SLOW:                                                     # (--slow-mem) every output (the guessing game's too) reads z
                hs_a = slow_z(chunk, e_, hs_a)
            return gd_(h2pi_(hs_a), hs_a), pol.v(hs_a).squeeze(-1), hs_a, (pol.v2(hs_a) if LONG else None)

        kl_sum, cf_sum, kl_n = 0.0, 0.0, 0                              # the policy's step, measured in the last pass
        OVK_ = [0.0]                                                     # (decoupled) KL(played || now) in the last pass
        klh = np.zeros(len(ACTION_DIMS)) if not NOSYNC else torch.zeros(len(ACTION_DIMS), dtype=torch.float64, device=dev)
        old_h = None
        if not DEC and a.kl_heads and (update % a.kl_heads == 0 or update <= 20):    # the log-probability of what he did, per head, before the update
            with torch.no_grad():
                old_h = torch.zeros(T, N, len(ACTION_DIMS), device=dev)
                for chunk, ch_h in zip(torch.arange(N, device=dev).chunk(n_mb), torch.arange(N).chunk(n_mb)):
                    CHK_[:] = [ch_h, chunk]                              # (--learn-nosync: the piece's players on the host)
                    hh = h0[chunk]
                    lgs = []
                    if HAS_CELLS:
                        for t in range(T):
                            lg, v, hh = pol.step(b_obs[t, chunk].float(), hh)
                            lgs.append(lg)
                            hh = hh * (1.0 - b_done[t, chunk])[:, None]
                        lgk_ = torch.stack(lgs)
                    else:
                        lgk_ = seq_pass(chunk, hh)[0]
                    if ORDER:
                        lgk_ = ord_lg(pol, lgk_, b_act[:, chunk])
                    for j, dd in enumerate(dists(lgk_)):
                        old_h[:, chunk, j] = dd.log_prob(b_act[:, chunk, j])
        trk_w = trk_lesson_w(mins) if TRK_ON else 0.0                    # (--track) the readout's lesson of this update: its truth and mask
        trz_w = trz_lesson_w(mins) if (TRZ_ON and trk_w > 0) else 0.0     # (--track-z) the second part's, with it (TRACK_W 0 stops both)
        bh_w = bh_lesson_w(mins) if (BH is not None and trk_w > 0) else 0.0   # (--brain-human) the people's lesson's weight, with it
        if trz_w > 0:
            TRZ_Y = b_aux[:T][..., TRZ_TC][torch.arange(BK - 1, T, BK)].contiguous()
            tz_acc = torch.zeros(len(trz_.PARTS) + 1, dtype=torch.float64, device=ADEV)
        ah_w = ah_lesson_w(mins) if (AH_ON and trk_w > 0) else 0.0      # (--ahead) its lesson, with the readout's (TRACK_W 0 stops it too)
        if ah_w > 0:
            AHC_ = tuple(AH_L["cols"])
            assert all(c_ in TRK_IX for c_ in AHC_), "--ahead: the simulator gives no {} (TRACK_RACE=1 for the race)".format(
                [c_ for c_ in AHC_ if c_ not in TRK_IX])
            AH_C = [TRK_IX[c_] for c_ in AHC_]
            ys_ = [ahead_.labels(b_aux[:, c0_:c0_ + 2048][..., AH_C].float(), b_done[:, c0_:c0_ + 2048].cpu(), AHC_, BK, AH_L["n_target"],
                                 race=bool(AH_L.get("race"))) for c0_ in range(0, N, 2048)]
            AH_Y = [torch.cat([y_[i_] for y_ in ys_], 1) for i_ in range(len(ys_[0]))]   # (off the card: a piece goes over with its minibatch)
            ys_ = None
            NPA_ = len(ahead_.PARTS)
            ah_acc = torch.zeros(2 * NPA_ + 4, dtype=torch.float64, device=ADEV)  # the parts' loss sums, their frames, the place's error at 1, 2, 4 s, frames
        BTOK_ISO = None
        if trk_w > 0:
            TRK_Y = b_aux[:T][..., TRK_TC]                               # [T, N, 13] float16, off the card (a piece goes over with its minibatch)
            TRK_M = b_aux[:T][..., TRK_IX["trk_on"]] > 0.5
            if BEL:                                                      # (--belief) the ticks' frames only: what the belief's readout is graded on
                TRK_TF = torch.arange(BK - 1, T, BK)
                TRK_TFD = TRK_TF.to(dev)
                TRK_Y, TRK_M = TRK_Y[TRK_TF].contiguous(), TRK_M[TRK_TF].contiguous()
                BEL_ISO = None
                BH_ISO = None                                            # (--brain-human) the same proof for the people's lesson
            tk_acc = torch.zeros(len(track_.PARTS) + 1, dtype=torch.float64, device=ADEV)    # first pass: the parts' loss sums, weights
        aux_w = 0.0
        if AUX_W > 0:                                                    # (--aux) the lesson's labels, by hindsight inside this rollout
            aux_w = AUX_W * (min(1.0, max(0.0, mins - fade0) / a.aux_warm) if a.aux_warm > 0 else 1.0)
            t_aux = time.time()
            dn_ = b_done.cpu()
            ys_, ms_, cs_ = [], [], []
            for c0_ in range(0, N, 4096):                                # (a few thousand players at a time: whole tensors, no loop over players)
                y_, m_, c_ = aux_labels(b_aux[:, c0_:c0_ + 4096].float(), dn_[:, c0_:c0_ + 4096], AUX_IX, AUX_FR)
                ys_.append(y_.half())
                ms_.append(m_)
                cs_.append(c_.to(torch.uint8))
            AUX_Y, AUX_M, AUX_C = torch.cat(ys_, 1), torch.cat(ms_, 1), torch.cat(cs_, 1)      # (off the card: a piece goes over with its minibatch)
            ys_ = ms_ = cs_ = None
            aux_secs = time.time() - t_aux
            ax_s, ax_n, ax_w = torch.zeros(len(AUX_MI), dtype=torch.float64, device=ADEV), torch.zeros(6, dtype=torch.float64, device=ADEV), 0.0
            if AUX_Q:                                                    # (2026-10-12) the labels of the questions beside the four, the same way
                t_aux = time.time()
                ks_, ms_ = [], []
                for c0_ in range(0, N, 4096):
                    k_, m_ = aux_guess(b_aux[:, c0_:c0_ + 4096].float(), dn_[:, c0_:c0_ + 4096], AUX_IX, AUX_FW)
                    ks_.append(k_.to(torch.uint8))
                    ms_.append(m_)
                AUX_K, AUX_KM = torch.cat(ks_, 1), torch.cat(ms_, 1)     # (off the card, as the four's)
                ks_ = ms_ = None
                if "near" in AUX_Q:                                      # (near) the landmark nearest the enemy, now and later
                    ks_, ms_ = [], []
                    for c0_ in range(0, N, 4096):
                        k_, m_ = aux_near(b_aux[:, c0_:c0_ + 4096].float(), dn_[:, c0_:c0_ + 4096], AUX_IX, AUX_NW)
                        ks_.append(k_.to(torch.uint8))
                        ms_.append(m_)
                    AUX_N, AUX_NM = torch.cat(ks_, 1), torch.cat(ms_, 1)
                    ks_ = ms_ = None
                    nx_s, nx_n = torch.zeros(6, dtype=torch.float64, device=ADEV), torch.zeros(4, dtype=torch.float64, device=ADEV)      # sums: 2 losses, 4 x called right; weights
                    nx_h = [torch.zeros(AUX_NN["target"], dtype=torch.float64, device=ADEV) for _ in range(4)]             # how often each landmark is the true one
                guess_secs = time.time() - t_aux
                gx_s, gx_n = torch.zeros(11, dtype=torch.float64, device=ADEV), torch.zeros(6, dtype=torch.float64, device=ADEV)      # sums: 5 losses, 5 x called right, the target
                gx_h = [torch.zeros(n_, dtype=torch.float64, device=ADEV) for n_ in AUX_KN]                              # unseen; weights; how often each answer is true
        if AUX_W > 0 and AUX2:                                           # (v0.2.2) the labels again, by aux2_labels: the tail of the rollout before,
            AX2_ = aux2_labels(b_aux, b_done.cpu(), b_bel, AUX_IX, AUX_FR, AUX_FW if AUX_Q else 0,   # his life's first seconds, the enemy unseen
                               AUX_NW if "near" in AUX_Q else 0, bool(AUX_Q), "near" in AUX_Q, AUX_FRESH, AUX_UNSEEN, AUX_TW, AUX_TAILD, AUX_LIFE)
            AUX_Y, AUX_M, AUX_C = AX2_["Y"], AX2_["M"], AX2_["C"]
            if AUX_Q:
                AUX_K, AUX_KM = AX2_["K"], AX2_["KM"]
            if "near" in AUX_Q:
                AUX_N, AUX_NM = AX2_["N"], AX2_["NM"]
            AUX_TWN = AX2_["tw"]                                         # the rows in front: the rollout before's last frames
            AUX_TH, AUX_TWG = (AUX_TAILD["h"], AUX_TAILD["w"]) if AUX_TWN else (None, None)
            AUX_LIFE, AX2_ST, AUX_TAILD = AX2_["life"], AX2_["stats"], AX2_["tail"]
            if AUX_TAILD is not None:
                AUX_TAILD.update(h=b_ht, w=b_w[T - AUX_TW:].cpu())
            AX2_ = None
        if AUX_W > 0 and AUX_MEAS:                                       # (--aux-measure) bands: nothing believed, believed 0-2 s ago, 2-7.5 s, 7.5-20 s;
            mb_s = torch.zeros(4, 4, dtype=torch.float64, device=ADEV)                # frames, his memory's error, the belief's (nothing believed: the zero
            AUX_BL = b_bel[:T]                                           # answer's), frames his memory was nearer
        ll_acc = torch.zeros(8, dtype=torch.float64, device=ADEV)                     # (--legs-learn) the learner's frames, of them the branch's (turn), its
        #                                                                  KL in the last pass (sum, pieces), the first piece's largest |log p - log p
        #                                                                  at play| before any step, its entropy (sum), the gradient's size (sum, count)
        ll_first = [True]
        ug_acc = torch.zeros(len(L_TAKES), 3, dtype=torch.float64, device=ADEV)      # (--legs-guide) by guided output, the first pass: the frames his own
        #                                                                  output counted with the branch having a way, of them his choice the
        #                                                                  branch's likeliest, the chance a draw of the branch's equals his
        ug_first = [None]                                                # (--legs-feat, --legs-guide) the first piece's largest |log p - log p
        #                                                                  at play| before any step (the rollout's step and the pass agree)
        wy_acc = torch.zeros(8, dtype=torch.float64, device=dev)         # (WAYS) the learner's readings of his way: how many, the sum of the
        #                                                                  entropy, of the chance given to each way, the readings on each way
        hd_acc = torch.zeros(16, dtype=torch.float64)                   # (--head) the first pass's sums: tick weights, the plan's size, the values'
        #                                                                  loss (sum, pieces), the win head's (loss sum, labelled, game ends, the
        #                                                                  chance of the true band there, called right), the target's part of the
        #                                                                  intention's logits (head, hands, readings), its gradient (sum, count), its
        #                                                                  confidence at the game ends

        def pi_t(z_):
            """what the teachers' losses read: his logits from z_, the head's part added as it is but taught by them never (--head)"""
            lg_ = pol.pi(z_)
            if H2:                                                       # (--head2) its bias as it is, taught by them never
                lg_ = head2_.add_bias(lg_, HO2_[0]["bias"].detach(), HD_I0)
            lg_ = lg_ if not HEADL else head_logits(lg_, HO_[0]["tadd"].detach(), HO_[0]["wadd"].detach())
            return lg_ if UG_[0] is None else lg_ + UG_[0].detach()     # (--legs-guide: its part as it is, taught by them never)

        def aux_o(name, hx_):
            """(--aux) his answer to a question from hx_; with the head its own answer added (none on the tail's rows in front)"""
            o_ = getattr(pol.aux, name)(hx_)
            if HEADL and name in HO_[0]["aux"]:
                ad_ = HO_[0]["aux"][name]
                if ad_.shape[0] < o_.shape[0]:
                    ad_ = torch.cat([ad_.new_zeros((o_.shape[0] - ad_.shape[0],) + tuple(ad_.shape[1:])), ad_])
                o_ = o_ + ad_
            return o_

        SK_ = None
        if a.step_kl_pieces > 0 and not OVL:                             # (--step-kl-pieces) the last update's step on this rollout's frames:
            with torch.no_grad():                                        # pol before the last update put in place for the pass, then back
                cur_ = {k_: v_.detach().clone() for k_, v_ in pol.state_dict().items()}
                if PREV_SD[0] is not None:
                    pol.load_state_dict(PREV_SD[0])
                    SK_ = torch.zeros(2, dtype=torch.float64)
                    for k_ in range(min(a.step_kl_pieces, n_mb)):
                        chunk = torch.arange(k_, N, n_mb, device=dev)
                        lg_, v_, hs_, _ = seq_pass(chunk, h0[chunk])
                        if ORDER:
                            lg_ = ord_lg(pol, lg_, b_act[:, chunk])
                        hm_ = head_masks(b_dec[:, chunk], b_live[:, chunk], b_ll[:, chunk], b_lo[:, chunk], b_act[:, chunk], b_so[:, chunk])
                        lp_ = sum(dd.log_prob(b_act[:, chunk, j]) * (1.0 if hm_[j] is None else hm_[j]) for j, dd in enumerate(dists(lg_)))
                        if LEGS_LEARN:
                            lgl_ = pol.legs_comb(legs_fwd(pol, legs_x_of(chunk)), hs_)
                            lp_ = lp_ + legs_lp(lgl_, b_lr[:, chunk], b_dec[:, chunk], b_lo[:, chunk])[0]
                        w_ = b_w[:, chunk]
                        SK_ += torch.stack([w_.sum(), ((b_logp[:, chunk] - lp_) * w_).sum()]).double().cpu()
                    pol.load_state_dict(cur_)
                PREV_SD[0] = cur_
        OV_ = None                                                       # (--overlap) the staleness: the network that played (ACT, one update
        LP_PX = ISW = IS_ = None                                         # (decoupled) the learner's log p before the update, the capped weights
        if DEC:                                                          # (--overlap-ppo decoupled) the proximal pass: pol before any step of
            with torch.no_grad():                                        # this update on the whole batch: its log p of what he did (as the
                LP_PX = torch.zeros(T, N, device=dev)                    # learning passes count it), its values; per head for kl_heads
                V_PX = torch.zeros(T, N, device=dev)
                V2_PX = torch.zeros(T, N, 2, device=dev) if LONG else None
                if a.kl_heads and (update % a.kl_heads == 0 or update <= 20):
                    old_h = torch.zeros(T, N, len(ACTION_DIMS), device=dev)
                t_px = time.time()
                for chunk, ch_h in zip(torch.arange(N, device=dev).chunk(max(1, n_mb // max(1, a.overlap_prox_merge))),
                                       torch.arange(N).chunk(max(1, n_mb // max(1, a.overlap_prox_merge)))):
                    CHK_[:] = [ch_h, chunk]                              # (--learn-nosync: the piece's players on the host)
                    lg_, v_, hs_, v2_ = seq_pass(chunk, h0[chunk])
                    if ORDER:
                        lg_ = ord_lg(pol, lg_, b_act[:, chunk])
                    hm_ = head_masks(b_dec[:, chunk], b_live[:, chunk], b_ll[:, chunk], b_lo[:, chunk], b_act[:, chunk], b_so[:, chunk])
                    lp_ = 0
                    for j, dd in enumerate(dists(lg_)):
                        l_ = dd.log_prob(b_act[:, chunk, j])
                        if old_h is not None:
                            old_h[:, chunk, j] = l_
                        lp_ = lp_ + l_ * (1.0 if hm_[j] is None else hm_[j])
                    if LEGS_LEARN:                                       # (the legs' part, as in the learning passes)
                        lgl_ = pol.legs_comb(legs_fwd(pol, legs_x_of(chunk)), hs_)
                        lp_ = lp_ + legs_lp(lgl_, b_lr[:, chunk], b_dec[:, chunk], b_lo[:, chunk])[0]
                    LP_PX[:, chunk] = lp_
                    V_PX[:, chunk] = v_
                    if LONG:
                        V2_PX[:, chunk] = v2_
                lg_ = v_ = hs_ = v2_ = lp_ = None
                w_ = b_w
                d_ = b_logp - LP_PX                                      # log p(played) - log p(learner before the update)
                r_ = (-d_).clamp(max=30.0).exp()                         # pi_prox / pi_played
                ISW = r_.clamp(max=a.overlap_is_cap)
                OV_ = torch.stack([w_.sum(), (d_ * w_).sum(), (((r_ - 1.0).abs() > clip).float() * w_).sum(), ((r_ - 1.0).abs() * w_).sum(),
                                   ((V_PX - b_val[:T]).abs() * w_).sum(), (r_.clamp(max=1e3) * w_).sum()]).double().cpu()
                IS_ = [float((ISW * w_).sum() / w_.sum().clamp(min=1.0)), float((r_ * (w_ > 0)).max()),
                       float(((r_ > a.overlap_is_cap).float() * w_).sum() / w_.sum().clamp(min=1.0)),
                       float(((r_ < 1.0 / a.overlap_is_cap).float() * w_).sum() / w_.sum().clamp(min=1.0))]
                d_ = r_ = None
                if a.overlap_prox_values:                                # the baseline and the targets: the learner's values (the last
                    b_val[:T] = V_PX                                     # frame's bootstrap, b_val[T], stays the played network's)
                    if LONG:
                        b_val2[:T] = V2_PX
                V_PX = V2_PX = None
                IS_.append(time.time() - t_px)
            adv, ret, ret2, long_c, long_gap = gae_()
        if OVL and not DEC and a.overlap_kl_pieces > 0:                  # behind) against the one that learns, before any step of this update,
            OV_ = torch.zeros(6, dtype=torch.float64)                    # on pieces of every n_mb-th player (all simulators): the learner's
            with torch.no_grad():                                        # frames; sums of log p(played) - log p(now), of frames outside the
                for k_ in range(min(a.overlap_kl_pieces, n_mb)):         # clip, of |ratio - 1|, of |value now - value played|, of the ratio
                    chunk = torch.arange(k_, N, n_mb, device=dev)
                    lg_, v_, hs_, _ = seq_pass(chunk, h0[chunk])
                    if ORDER:
                        lg_ = ord_lg(pol, lg_, b_act[:, chunk])
                    hm_ = head_masks(b_dec[:, chunk], b_live[:, chunk], b_ll[:, chunk], b_lo[:, chunk], b_act[:, chunk], b_so[:, chunk])
                    lp_ = sum(dd.log_prob(b_act[:, chunk, j]) * (1.0 if hm_[j] is None else hm_[j]) for j, dd in enumerate(dists(lg_)))
                    if LEGS_LEARN:                                       # (the legs' part of the ratio, as in the learning passes)
                        lgl_ = pol.legs_comb(legs_fwd(pol, legs_x_of(chunk)), hs_)
                        lp_ = lp_ + legs_lp(lgl_, b_lr[:, chunk], b_dec[:, chunk], b_lo[:, chunk])[0]
                    w_ = b_w[:, chunk]
                    d_ = b_logp[:, chunk] - lp_
                    r_ = (-d_).exp()
                    OV_ += torch.stack([w_.sum(), (d_ * w_).sum(), (((r_ - 1.0).abs() > clip).float() * w_).sum(), ((r_ - 1.0).abs() * w_).sum(),
                                        ((v_ - b_val[:T, chunk]).abs() * w_).sum(), (r_ * w_).sum()]).double().cpu()
        if H2:                                                           # (--head2) its own advantage: GAE of his whole pay at its gamma, from its value
            ADV_H, RET_H = head2_.gae(b_rew, B_VH, b_done, float(H2L["gamma"]), lam)
            h2_acc = torch.zeros(12, dtype=torch.float64, device=dev)    # first pass: frames, the lesson's loss, the value's, the plan's size, the
            #                                                              bias's (centred, on read frames), the hands' intention logits' (same), read
            #                                                              frames, grad norm (sum, count), |gin| / |e| (sum, pieces), the ratio's clip share
        IF_ACC = torch.zeros(len(IF_MAPS), IF_OK.shape[1], device=dev)   # (--item-floor) epoch 0: sum of p over read frames, by map and item
        IF_CNT = torch.zeros(len(IF_MAPS), device=dev)                     # ... the read frames by map
        IF_LS = torch.zeros(4, dtype=torch.float64, device=dev)            # ... the term (sum), |grad| on the intention logits: the floor's, the bonus's, the pg's
        for epoch in range(3):
            HO_[2] = epoch == 0
            perm = torch.randperm(N, device=dev)
            perm_h = perm.cpu().chunk(n_mb) if NOSYNC else None          # (--learn-nosync) the pieces' players on the host, once an epoch
            for k_mb, chunk in enumerate(perm.chunk(n_mb)):              # whole sequences per player
                if NOSYNC:
                    CHK_[:] = [perm_h[k_mb], chunk]
                hh = h0[chunk]
                lgs, vals, hs = [], [], []
                if HAS_CELLS:
                    for t in range(T):
                        lg, v, hh = pol.step(b_obs[t, chunk].float(), hh)
                        lgs.append(lg)
                        vals.append(v)
                        hs.append(hh)
                        hh = hh * (1.0 - b_done[t, chunk])[:, None]
                    lg, v, hs_all, v2_all = torch.stack(lgs), torch.stack(vals), torch.stack(hs), None
                else:
                    lg, v, hs_all, v2_all = seq_pass(chunk, hh)
                if ORDER:                                                # (--ordered-heads) each ordered output read with what he drew before it
                    lg = ord_lg(pol, lg, b_act[:, chunk])
                ds = dists(lg)
                dst = ds                                                 # what the teachers' losses read
                if UNI_GUIDE and epoch == 0:                             # (--legs-guide) his own choice against the branch's (switch off)
                    with torch.no_grad():
                        hmu_ = head_masks(b_dec[:, chunk], b_live[:, chunk], b_ll[:, chunk], b_lo[:, chunk], b_act[:, chunk], b_so[:, chunk])
                        for i_, (o_, mp_) in enumerate(UGM.mapped(UG_[1])):
                            m_ = (1.0 if hmu_[o_] is None else hmu_[o_]) * UG_[2] * b_w[:, chunk]
                            ug_acc[i_] += HC_(torch.stack([m_.sum(), ((mp_.argmax(-1) == b_act[:, chunk, o_]).float() * m_).sum(),
                                                       ((ds[o_].probs * mp_.exp()).sum(-1) * m_).sum()]).double())
                if a.teach_trunk < 1.0 and (kick > 0 or wk > 0 or ik > 0):
                    hs_ = hs_all                                         # the same outputs, the shared layers held back
                    dst = (LazyDists if NOSYNC else dists)(pi_t(a.teach_trunk * hs_ + (1.0 - a.teach_trunk) * hs_.detach()))
                dstm = dst                                               # ... and what the movement teacher's loss reads (--teach-trunk-move)
                if kick > 0 and a.teach_trunk_move >= 0 and a.teach_trunk_move != a.teach_trunk:
                    tm_ = a.teach_trunk_move
                    dstm = ds if tm_ >= 1.0 else (LazyDists if NOSYNC else dists)(pi_t(tm_ * hs_all + (1.0 - tm_) * hs_all.detach()))
                A = b_act[:, chunk]
                lv = b_live[:, chunk]
                dc = b_dec[:, chunk]
                hm = head_masks(dc, lv, b_ll[:, chunk], b_lo[:, chunk], A, b_so[:, chunk])
                lp = sum(dd.log_prob(A[..., j]) * (1.0 if hm[j] is None else hm[j]) for j, dd in enumerate(ds))
                hme = head_masks(dc, lv, b_ll[:, chunk], b_lo[:, chunk], A, b_so[:, chunk], ent=True) if JE else hm    # (JUMP_EVERY: the bonus on the hand's frames)
                ent = sum(w_ * dd.entropy() * (1.0 if hme[j] is None else hme[j]) for j, (w_, dd) in enumerate(zip(ent_heads, ds)))
                wgt = b_w[:, chunk]
                if LEGS_LEARN:                                           # (--legs-learn) the branch's part of what he did, the same advantage
                    lgl_ = pol.legs_comb(legs_fwd(pol, legs_x_of(chunk)), hs_all)    # (--legs-residual)
                    lpl_, dsl_, msl_ = legs_lp(lgl_, b_lr[:, chunk], dc, b_lo[:, chunk])
                    if UNI_RES and a.legs_residual_ent > 0:              # (--legs-residual-ent) on his legs, at his own outputs' weights
                        ent = ent + a.legs_residual_ent * sum(w_ * d_.entropy() * m_ for w_, d_, m_ in zip(ent_heads[:4], dsl_, msl_))
                    lp = lp + lpl_
                    enl_ = sum(d_.entropy() * m_ for d_, m_ in zip(dsl_, msl_))        # (its entropy, for the record)
                    if a.legs_ent > 0:                                   # (--legs-ent) each choice at his own movement output's weight
                        ent = ent + a.legs_ent * sum(w_ * d_.entropy() * m_ for w_, d_, m_ in zip(ent_heads[:4], dsl_, msl_))   # (forward,
                        #                                                  sideways, jump as his vertical key, turn) times --legs-ent
                    with torch.no_grad():
                        if epoch == 0:
                            ll_acc[0] += FV_(wgt.sum())
                            ll_acc[1] += FV_((msl_[3] * wgt).sum())
                            ll_acc[5] += FV_((enl_ * wgt).sum())
                        if ll_first[0]:                                  # (before any step: the ratio's legs part is 1 to rounding)
                            ll_acc[4] = FV_(((lpl_ - b_llp[:, chunk]).abs() * (wgt > 0)).max())
                            ll_first[0] = False
                        if epoch == 2:
                            ll_acc[2] += FV_(((b_llp[:, chunk] - lpl_) * wgt).sum() / wgt.sum().clamp(min=1.0))
                            ll_acc[3] += 1.0
                if UNI_ON and ug_first[0] is None:                       # (before any step: the pass's log p is the rollout's to rounding)
                    with torch.no_grad():
                        ug_first[0] = FV_(((lp - (LP_PX[:, chunk] if DEC else b_logp[:, chunk])).abs() * (wgt > 0)).max())   # (decoupled: the proximal pass's)
                wsum = wgt.sum().clamp(min=1.0)
                ad = adv[:, chunk]
                ad = (ad - (ad * wgt).sum() / wsum) / ((ad[wgt > 0] if not NOSYNC else          # (--learn-nosync: the same frames, found on the host)
                                                        ad.reshape(-1).index_select(0, up_(WP_H[:, hchunk(chunk)].reshape(-1).nonzero().squeeze(1)))).std() + 1e-8)
                if DEC:                                                  # (decoupled PPO) the ratio against the learner before this update,
                    ratio = (lp - LP_PX[:, chunk]).exp()                 # the frames weighted by pi_prox / pi_played (capped)
                    isw = ISW[:, chunk]
                    if epoch == 2:                                       # (the measures on the played frames: weighted by isw, they are
                        with torch.no_grad():                            # the learner's own step, KL(prox || now), per head too)
                            iw_ = isw * wgt
                            iws_ = iw_.sum().clamp(min=1e-6)
                            kl_sum += FV_(((LP_PX[:, chunk] - lp) * iw_).sum() / iws_)
                            cf_sum += FV_((((ratio - 1.0).abs() > clip).float() * iw_).sum() / iws_)
                            kl_n += 1
                            OVK_[0] += FV_(((b_logp[:, chunk] - lp) * wgt).sum() / wsum)     # KL(played || now), as plain PPO's kl
                            if old_h is not None:
                                for j, dd in enumerate(ds):
                                    mk_ = 1.0 if hm[j] is None else hm[j]
                                    klh[j] += FV_(((old_h[:, chunk, j] - dd.log_prob(A[..., j])) * mk_ * iw_).sum() / iws_)
                    pg = -(isw * torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad) * wgt).sum() / wsum
                else:
                    ratio = (lp - b_logp[:, chunk]).exp()
                    if epoch == 2:
                        with torch.no_grad():
                            kl_sum += FV_(((b_logp[:, chunk] - lp) * wgt).sum() / wsum)
                            cf_sum += FV_((((ratio - 1.0).abs() > clip).float() * wgt).sum() / wsum)
                            kl_n += 1
                            if old_h is not None:
                                for j, dd in enumerate(ds):
                                    mk_ = 1.0 if hm[j] is None else hm[j]
                                    klh[j] += FV_(((old_h[:, chunk, j] - dd.log_prob(A[..., j])) * mk_ * wgt).sum() / wsum)
                    pg = -(torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad) * wgt).sum() / wsum
                vl = (0.5 * (v - ret[:, chunk]).pow(2) * wgt).sum() / wsum
                if LONG:
                    vl = vl + (0.5 * (v2_all - ret2[:, chunk]).pow(2).sum(-1) * wgt).sum() / wsum
                en = (ent * wgt).sum() / wsum
                if W_HEAD >= 0 and W_ON and epoch == 0:                  # (WAYS) how he chooses his way, on the frames it was read
                    with torch.no_grad():
                        wyf_ = lv * wgt
                        wy_acc += torch.cat([torch.stack([wyf_.sum(), (ds[W_HEAD].entropy() * wyf_).sum()]),
                                             (ds[W_HEAD].probs * wyf_[..., None]).sum((0, 1)),
                                             torch.stack([((A[..., W_HEAD] == j_).float() * wyf_).sum() for j_ in range(3)])]).double()
                loss = pg + 0.5 * vl - ent_coef * en
                if I_HEAD >= 0 and (IF_LIVE[0] > 0 or epoch == 0):      # (--item-floor) his item intentions' mean p by map, read frames
                    pi_ = ds[I_HEAD].probs                               # [T, n, intentions]
                    mr_ = lv * wgt                                       # (his own seats, the frames his intention was read)
                    oh_ = IF_ONE[chunk]                                  # [n, maps]
                    sp_ = torch.einsum("tn,tnk,nm->mk", mr_, pi_, oh_)
                    cn_ = torch.einsum("tn,nm->m", mr_, oh_)
                    if epoch == 0:
                        IF_ACC += sp_.detach()
                        IF_CNT += cn_.detach()
                    if IF_LIVE[0] > 0:
                        mp_ = sp_ / cn_.clamp(min=1.0)[:, None]
                        ok_ = IF_OKT & (cn_ > 0)[:, None]
                        fl_ = (torch.relu(float(np.log(max(IF_LIVE[1], 1e-6))) - torch.log(mp_ + 1e-6)) * ok_.float()).sum()   # (the log form:
                        #                                                  its pull does not die with p as relu(floor - p)'s does, dp/dz = p (1 - p))
                        loss = loss + IF_LIVE[0] * fl_
                        if epoch == 0:
                            IF_LS[0] += fl_.detach().double()
                            if k_mb == 0:                                # (the sizing: the two gradients on this piece's intention logits)
                                lgi_ = ds[I_HEAD].logits
                                g1_ = torch.autograd.grad(IF_LIVE[0] * fl_, lgi_, retain_graph=True)[0]
                                ei_ = (ent_heads[I_HEAD] * ds[I_HEAD].entropy() * (1.0 if hme[I_HEAD] is None else hme[I_HEAD]) * wgt).sum() / wsum
                                g2_ = torch.autograd.grad(ent_coef * ei_, lgi_, retain_graph=True)[0]
                                g3_ = torch.autograd.grad(pg, lgi_, retain_graph=True)[0]
                                IF_LS[1] += g1_.norm().double()
                                IF_LS[2] += g2_.norm().double()
                                IF_LS[3] += g3_.norm().double()
                if H2:                                                   # (--head2) its own lessons: the bias by its advantage (the hands' logits
                    ho2_ = HO2_[0]                                       # as numbers), its value on every learner frame
                    m2_ = lv * wgt
                    ms2_ = m2_.sum().clamp(min=1.0)
                    lpi_ = torch.log_softmax(ho2_["hands_int"] + ho2_["bias"], -1).gather(-1, A[..., I_HEAD:I_HEAD + 1]).squeeze(-1)
                    r2_ = (lpi_ - B_LPI[:, chunk]).exp()
                    ah_ = ADV_H[:, chunk]
                    mu2_ = (ah_ * m2_).sum() / ms2_
                    ah_ = (ah_ - mu2_) / (((ah_ - mu2_).pow(2) * m2_).sum() / ms2_).sqrt().clamp(min=1e-8)
                    pg2_ = -(torch.min(r2_ * ah_, r2_.clamp(1 - clip, 1 + clip) * ah_) * m2_).sum() / ms2_
                    vh_ = head2_.value(pol.head2, ho2_["s_held"], hs_all.detach())
                    vl2_ = (0.5 * (vh_ - RET_H[:, chunk]).pow(2) * wgt).sum() / wsum
                    loss = loss + H2_PG_[0] * H2_PG_[2] * pg2_ + a.head2_v * vl2_
                    if epoch == 0:
                        with torch.no_grad():
                            bc_ = ho2_["bias"] - ho2_["bias"].mean(-1, keepdim=True)
                            hc_ = ho2_["hands_int"] - ho2_["hands_int"].mean(-1, keepdim=True)
                            h2_acc[0] += wgt.sum()
                            h2_acc[1] += pg2_.detach() * ms2_
                            h2_acc[2] += vl2_.detach() * wsum
                            h2_acc[3] += ho2_["plan"][1:].norm(dim=-1).mean() * wsum
                            h2_acc[4] += (bc_.norm(dim=-1) * m2_).sum()
                            h2_acc[5] += (hc_.norm(dim=-1) * m2_).sum()
                            h2_acc[6] += m2_.sum()
                            if "gin_share" in ho2_:
                                h2_acc[9] += ho2_["gin_share"]
                                h2_acc[10] += 1.0
                            h2_acc[11] += (((r2_ - 1.0).abs() > clip).float() * m2_).sum()
                if HEADL:                                                # (--head) its values on its ticks; the win head's lesson
                    ho_ = HO_[0]
                    tf_ = torch.arange(HD_K - 1, T, HD_K, device=dev)
                    wt_ = wgt[tf_]
                    wts_ = wt_.sum().clamp(min=1.0)
                    hv_ = (0.5 * (ho_["v_short"] - ret[tf_][:, chunk]).pow(2) * wt_).sum() / wts_
                    if LONG:
                        hv_ = hv_ + (0.5 * (ho_["v_long"] - ret2[tf_][:, chunk, 1]).pow(2) * wt_).sum() / wts_
                    loss = loss + a.head_v * hv_
                    if HD_WG >= 0:
                        with torch.no_grad():
                            pw_ = torch.softmax(ho_["win"].detach(), -1)
                            G_, M_, TM_ = head_.win_targets(pw_, b_wg[:, chunk], b_wb[:, chunk], HD_K, wgt)
                            if a.head_win_true != 1.0:
                                M_ = M_ * (1.0 + (a.head_win_true - 1.0) * TM_.float())
                        ce_w = -(G_ * torch.log_softmax(ho_["win"], -1)).sum(-1)
                        wl_ = (ce_w * M_).sum() / M_.sum().clamp(min=1.0)
                        loss = loss + a.head_win * wl_
                    if epoch == 0:
                        with torch.no_grad():
                            hd_acc[0] += float(wt_.sum())
                            hd_acc[1] += float((ho_["plan"].norm(dim=-1) * wt_).sum())
                            hd_acc[2] += float(hv_)
                            hd_acc[3] += 1.0
                            if HD_WG >= 0:                                # (loss and calibration: the true bands' ticks only)
                                te_ = TM_.float() * wt_
                                hd_acc[4] += float((ce_w * te_).sum())
                                hd_acc[5] += float((M_ > 0).float().sum())
                                hd_acc[6] += float(te_.sum())
                                hd_acc[7] += float(((pw_ * G_).sum(-1) * te_).sum())
                                hd_acc[8] += float(((pw_.argmax(-1) == G_.argmax(-1)).float() * te_).sum())
                                hd_acc[15] += float((pw_.max(-1).values * te_).sum())
                            ir_ = lv * wgt                                # the frames his intention was read
                            ta_c = ho_["tadd"] - ho_["tadd"].mean(-1, keepdim=True)
                            hi_c = ho_["hand_int"] - ho_["hand_int"].mean(-1, keepdim=True)
                            hd_acc[9] += float((ta_c.norm(dim=-1) * ir_).sum())
                            hd_acc[10] += float((hi_c.norm(dim=-1) * ir_).sum())
                            hd_acc[11] += float(ir_.sum())
                if AUX_W > 0:                                            # (--aux) what he is asked to foretell from his memory
                    ci_ = hchunk(chunk)
                    ay_, am_, ac_ = hsel(AUX_Y, 1, chunk, ci_).float(), hsel(AUX_M, 1, chunk, ci_), hsel(AUX_C, 1, chunk, ci_).long()
                    hx_ = hs_all if a.aux_trunk >= 1.0 else a.aux_trunk * hs_all + (1.0 - a.aux_trunk) * hs_all.detach()   # (as --teach-trunk)
                    wa_ = wgt                                            # (the learner's frames; --aux-tail: the rollout before's last frames in front)
                    if AUX_TWN:
                        hx_ = torch.cat([hsel(AUX_TH, 1, chunk, ci_).float(), hx_])
                        wa_ = torch.cat([hsel(AUX_TWG, 1, chunk, ci_), wgt])
                    wm_ = am_.float() * wa_[..., None]                   # a label is there, on the learner's frames
                    wn_ = wm_.sum((0, 1)).clamp(min=1.0)
                    o_fi = aux_o("fight", hx_)
                    e_pl = aux_o("place", hx_) - ay_[..., 0:3]
                    e_ap = aux_o("appear", hx_) - ay_[..., 3:5]
                    e_sd = e_ap[..., 0] - 4.0 * torch.round(e_ap[..., 0] / 4.0)      # sideways the short way round (a whole turn is 4 x 90)
                    ce_ = nn.functional.cross_entropy(o_fi[..., :3].reshape(-1, 3), ac_.reshape(-1), reduction="none").view(ac_.shape)
                    e_dm = o_fi[..., 3] - ay_[..., 5]
                    e_it = aux_o("items", hx_) - ay_[..., 6:8]
                    al_ = dict(place=(e_pl.pow(2).sum(-1) * wm_[..., 0]).sum() / wn_[0],
                               appear=((e_sd.pow(2) + e_ap[..., 1].pow(2)) * wm_[..., 1]).sum() / wn_[1],
                               fight=(ce_ * wm_[..., 2]).sum() / wn_[2] + (e_dm.pow(2) * wm_[..., 3]).sum() / wn_[3],
                               items=(e_it[..., 0].pow(2) * wm_[..., 4]).sum() / wn_[4] + (e_it[..., 1].pow(2) * wm_[..., 5]).sum() / wn_[5])
                    if AUX_Q:                                            # (2026-10-12) what the enemy goes for, how strong he is, who takes the big items
                        ak_ = hsel(AUX_K, 1, chunk, ci_).long()
                        wk_ = hsel(AUX_KM, 1, chunk, ci_).float() * wa_[..., None]        # a label is there, on the learner's frames
                        wkn_ = wk_.sum((0, 1)).clamp(min=1.0)
                        og_ = {h_: aux_o(h_, hx_) for h_ in AUX_Q}
                        cg_ = {}                                         # label j: its outputs, its loss frame by frame, the true answer
                        for j_, (h_, lo_, hi_) in enumerate(AUX_KO):
                            if h_ in og_:
                                o_, y_ = og_[h_][..., lo_:hi_], ak_[..., j_].clamp(max=hi_ - lo_ - 1)
                                cg_[j_] = (o_, nn.functional.cross_entropy(o_.reshape(-1, hi_ - lo_), y_.reshape(-1), reduction="none").view(y_.shape), y_)
                        for h_ in AUX_Q:
                            al_[h_] = sum((cg_[j_][1] * wk_[..., j_]).sum() / wkn_[j_] for j_ in range(5) if AUX_KO[j_][0] == h_)
                    if "near" in AUX_Q:                                  # (near) two answers over the intentions: now, later
                        an_ = hsel(AUX_N, 1, chunk, ci_).long().clamp(max=AUX_NN["target"] - 1)
                        wr_ = hsel(AUX_NM, 1, chunk, ci_).float() * wa_[..., None]
                        wrn_ = wr_.sum((0, 1)).clamp(min=1.0)
                        on_ = og_["near"].view(og_["near"].shape[0], og_["near"].shape[1], 2, AUX_NN["target"])
                        cn_ = nn.functional.cross_entropy(on_.reshape(-1, AUX_NN["target"]), an_.reshape(-1), reduction="none").view(an_.shape)
                        al_["near"] = (cn_[..., 0] * wr_[..., 0]).sum() / wrn_[0] + (cn_[..., 1] * wr_[..., 1]).sum() / wrn_[1]
                    loss = loss + aux_w * sum(al_[k_] for k_ in AUX_HEADS)
                    if epoch == 0:                                       # his errors on frames this update has not yet learnt from
                        with torch.no_grad():
                            mv_ = torch.stack([e_pl.pow(2).sum(-1), e_pl.norm(dim=-1) * 1500.0, ay_[..., 0:3].norm(dim=-1) * 1500.0,
                                               e_sd.pow(2) + e_ap[..., 1].pow(2), e_sd.abs() * 90.0, e_ap[..., 1].abs() * 90.0,
                                               ay_[..., 3].abs() * 90.0, ay_[..., 4].abs() * 90.0,
                                               ce_, (o_fi[..., :3].argmax(-1) == ac_).float(), (ac_ == 0).float(), (ac_ == 1).float(), (ac_ == 2).float(),
                                               e_dm.pow(2), e_dm.abs() * 100.0, ay_[..., 5].abs() * 100.0,
                                               e_it[..., 0].pow(2), e_it[..., 0].abs() * 40.0, ay_[..., 6].abs() * 40.0,
                                               e_it[..., 1].pow(2), e_it[..., 1].abs() * 40.0, ay_[..., 7].abs() * 40.0], -1)
                            ax_s += HC_((mv_ * wm_[..., AUX_MI]).sum((0, 1)).double())
                            ax_n += HC_(wm_.sum((0, 1)).double())
                            ax_w += FV_(wgt.sum())
                            if AUX_MEAS:                                 # (--aux-measure) his memory against his belief inputs, where place is asked
                                bl_ = hsel(AUX_BL, 1, chunk, ci_)
                                wp_ = wm_[AUX_TWN:, :, 0]
                                tr_ = ay_[AUX_TWN:, :, 0:3] * 1500.0
                                hd_ = e_pl[AUX_TWN:].norm(dim=-1) * 1500.0
                                ok_ = bl_[..., 0] > 0.5
                                be_ = torch.where(ok_, (bl_[..., 1:4] * 1500.0 - tr_).norm(dim=-1), tr_.norm(dim=-1))
                                bd_ = torch.full(ok_.shape, 3, dtype=torch.long, device=dev)
                                if not NOSYNC:
                                    bd_[bl_[..., 4] < 0.99999] = 2
                                    bd_[bl_[..., 4] * AUX_BEL_AGE < 2.0] = 1
                                    bd_[~ok_] = 0
                                else:                                    # (--learn-nosync: the same, without a boolean index's wait)
                                    bd_.masked_fill_(bl_[..., 4] < 0.99999, 2)
                                    bd_.masked_fill_(bl_[..., 4] * AUX_BEL_AGE < 2.0, 1)
                                    bd_.masked_fill_(~ok_, 0)
                                for b_ in range(4):
                                    w_ = wp_ * (bd_ == b_).float()
                                    mb_s[b_] += HC_(torch.stack([w_.sum(), (hd_ * w_).sum(), (be_ * w_).sum(), ((hd_ < be_).float() * w_).sum()]).double())
                            if AUX_Q:
                                for j_, (o_, c_, y_) in cg_.items():
                                    r_ = (o_.argmax(-1) == y_).float()
                                    gx_s[j_] += FV_((c_ * wk_[..., j_]).sum())
                                    gx_s[5 + j_] += FV_((r_ * wk_[..., j_]).sum())
                                    gx_h[j_] += BC_(y_.reshape(-1), wk_[..., j_].reshape(-1).double(), AUX_KN[j_])
                                    if j_ == 0:                          # ... the target on the frames the enemy is not in view
                                        gx_s[10] += FV_((r_ * wk_[..., 5]).sum())
                                        gx_h[5] += BC_(y_.reshape(-1), wk_[..., 5].reshape(-1).double(), AUX_KN[5])
                                gx_n += HC_(wk_.sum((0, 1)).double())
                                if "near" in AUX_Q:
                                    rn_ = (on_.argmax(-1) == an_).float()        # [T, players, 2]
                                    for j_ in range(4):                          # now, later; the same with the enemy not in view
                                        nx_s[2 + j_] += FV_((rn_[..., j_ % 2] * wr_[..., j_]).sum())
                                        nx_h[j_] += BC_(an_[..., j_ % 2].reshape(-1), wr_[..., j_].reshape(-1).double(), AUX_NN["target"])
                                    nx_s[0] += FV_((cn_[..., 0] * wr_[..., 0]).sum())
                                    nx_s[1] += FV_((cn_[..., 1] * wr_[..., 1]).sum())
                                    nx_n += HC_(wr_.sum((0, 1)).double())
                if BTOK and BTOK_ISO is None and BEL and torch.is_tensor(loss) and loss.requires_grad:   # (v0.4.1) the proof, every update: the
                    bp_ = [(n_, p_) for n_, p_ in pol.named_parameters() if n_.startswith(BRAIN_PFX) and p_.requires_grad]      # game's losses
                    gb_ = torch.autograd.grad(loss, [p_ for _, p_ in bp_], allow_unused=True, retain_graph=True)               # reach no weight
                    br_ = [n_ for (n_, _), g_ in zip(bp_, gb_) if g_ is not None and float(g_.abs().sum()) != 0.0]            # of the brain
                    BTOK_ISO = dict(brain_params=len(bp_), brain_reached=len(br_), gate=BTG_R)
                    assert not br_, "the game's losses reached the brain: {}".format(br_[:5])
                    gb_ = None
                if trk_w > 0 and BEL:                                    # (--belief, v0.4.0 A) the readout's lesson on the belief's state at its
                    ci_ = hchunk(chunk)                                  # ticks, re-run from the rollout's start over the same inputs; nothing of
                    ty_ = hsel(TRK_Y, 1, chunk, ci_).float()             # the policy is in its graph (the inputs are numbers, not outputs)
                    tm_ = hsel(TRK_M, 1, chunk, ci_).float() * wgt.index_select(0, TRK_TFD)
                    lay_ = gru_layout(belief_.tick_resets(DN_H[:, ci_], BK)[1], dev) if (NOSYNC and a.fast_gru) else None
                    bs_ = belief_.seq(pol.belief, XS_[0], b_done[:, chunk], BS0[chunk], BK,
                                      gru_fn=(lambda c_, e_, h_, d_: gru_seq(c_, e_, h_, d_, lay=lay_)) if a.fast_gru else None)
                    tl_, tp_ = track_.loss(pol.track(bs_), ty_, TRK_PARTS, tm_)
                    if ah_w > 0:                                         # (--ahead) on the same state and ticks (the learner's frames)
                        ay_ = tuple(hsel(y_, 1, chunk, ci_) for y_ in AH_Y)
                        am_ = wgt.index_select(0, TRK_TFD)
                        ao_ = pol.ahead(bs_)
                        al_, ap_, an_ = ahead_.loss(ao_, AH_L, ay_, AH_PARTS, am_)
                        tl_ = tl_ + (ah_w / trk_w) * al_
                        if epoch == 0:
                            with torch.no_grad():
                                ah_acc += HC_(torch.cat([ap_ * an_.clamp(min=1.0), an_, ahead_.errors(ao_, ay_, am_) * an_[0], an_[0:1]]).double())
                    if trz_w > 0:                                        # (--track-z) the second part's lesson on the same state and frames
                        zl_, zp_ = trz_.loss(pol.trackz(bs_), hsel(TRZ_Y, 1, chunk, ci_).float(), TRZ_PARTS, tm_)
                        tl_ = tl_ + (trz_w / trk_w) * zl_                # (so that trk_w * tl_ is both lessons)
                        if epoch == 0:
                            with torch.no_grad():
                                tz_acc += HC_(torch.cat([zp_ * tm_.sum(), tm_.sum()[None]]).double())
                    if BEL_ISO is None:                                  # (the proof, every update: the lesson alone reaches no weight of the policy)
                        nm_ = [n_ for n_, p_ in pol.named_parameters() if p_.requires_grad]
                        gr_ = torch.autograd.grad(trk_w * tl_, [p_ for _, p_ in pol.named_parameters() if p_.requires_grad],
                                                  allow_unused=True, retain_graph=True)
                        pr_ = [n_ for n_, g_ in zip(nm_, gr_) if not n_.startswith(BRAIN_PFX) and g_ is not None
                               and float(g_.abs().sum()) != 0.0]
                        bn_ = [float(g_.norm()) for n_, g_ in zip(nm_, gr_) if n_.startswith("belief.") and g_ is not None]
                        tn_ = [float(g_.norm()) for n_, g_ in zip(nm_, gr_) if n_.startswith(("track.", "trackz.")) and g_ is not None]
                        BEL_ISO = dict(policy_params=sum(not n_.startswith(BRAIN_PFX) for n_ in nm_), policy_reached=len(pr_),
                                       belief_grad=round(float(np.sqrt(np.sum(np.square(bn_)))), 6) if bn_ else 0.0,
                                       track_grad=round(float(np.sqrt(np.sum(np.square(tn_)))), 6) if tn_ else 0.0)
                        assert not pr_, "the belief's lesson reached the policy's weights: {}".format(pr_[:5])
                        if trz_w > 0:
                            BEL_ISO["trackz_grad"] = round(float(np.sqrt(sum(float(g_.norm()) ** 2 for n_, g_ in zip(nm_, gr_)
                                                                                 if n_.startswith("trackz.") and g_ is not None))), 6)
                        gr_ = None
                    loss = loss + trk_w * tl_
                    if BH is not None and bh_w > 0:                  # (brainppl, --brain-human) the same lesson on the next piece of people's games
                        hl_ = BH.next_loss(pol, TRK_PARTS, TRZ_PARTS if trz_w > 0 else None, AH_L, AH_PARTS,
                                           trz_w / trk_w if trz_w > 0 else 0.0, ah_w / trk_w if ah_w > 0 else 0.0)
                        loss = loss + trk_w * bh_w * (hl_ - tl_)         # (the brain's lesson: (1 - s) x self-play's + s x people's)
                        if BH_ISO is None:                               # (v043b: the proof, every update: the people's lesson reaches no weight of the policy)
                            nm_ = [n_ for n_, p_ in pol.named_parameters() if p_.requires_grad]
                            gr_ = torch.autograd.grad(hl_, [p_ for _, p_ in pol.named_parameters() if p_.requires_grad],
                                                      allow_unused=True, retain_graph=True)
                            pr_ = [n_ for n_, g_ in zip(nm_, gr_) if not n_.startswith(BRAIN_PFX) and g_ is not None
                                   and float(g_.abs().sum()) != 0.0]
                            BH_ISO = dict(policy_params=sum(not n_.startswith(BRAIN_PFX) for n_ in nm_), policy_reached=len(pr_))
                            assert not pr_, "the people's lesson reached the policy's weights: {}".format(pr_[:5])
                            gr_ = None
                    if epoch == 0:
                        with torch.no_grad():
                            n_ = tm_.sum()
                            tk_acc += HC_(torch.cat([tp_ * n_, n_[None]]).double())
                elif trk_w > 0:                                          # (--track) the readout's lesson: the enemy as the truth has him
                    ci_ = hchunk(chunk)
                    ty_ = hsel(TRK_Y, 1, chunk, ci_).float()
                    tm_ = hsel(TRK_M, 1, chunk, ci_).float() * wgt       # (a duel's game, both alive, the learner's frames)
                    hx_ = hs_all if a.track_trunk >= 1.0 else a.track_trunk * hs_all + (1.0 - a.track_trunk) * hs_all.detach()
                    tl_, tp_ = track_.loss(pol.track(hx_.float()), ty_, TRK_PARTS, tm_)
                    loss = loss + trk_w * tl_
                    if epoch == 0:
                        with torch.no_grad():
                            n_ = tm_.sum()
                            tk_acc += HC_(torch.cat([tp_ * n_, n_[None]]).double())
                if kick > 0:                                             # imitate the movement teacher in movement rounds
                    tl = b_teach[:, chunk]
                    tm = (tl[..., 0] >= 0).float() * wgt
                    lt = sum(dstm[j].log_prob(tl[..., j].clamp(min=0)) * (tl[..., j] >= 0).float() for j in range(4))   # (a head can go unlabelled)
                    kick_l = -(lt * tm).sum() / tm.sum().clamp(min=1.0)
                    loss = loss + kick * kick_l
                if wk > 0:                                               # the weapon key leans on the weapon rule (rockets close, ...)
                    wl_ = b_teach[:, chunk][..., 4]
                    wm_ = (wl_ >= 0).float() * wgt
                    wk_l = -(dst[6].log_prob(wl_.clamp(min=0)) * wm_).sum() / wm_.sum().clamp(min=1.0)
                    loss = loss + wk * wk_l
                if ik > 0:                                               # the intention head leans on the item rule at first
                    it_ = b_iteach[:, chunk]
                    im_ = b_live[:, chunk] * wgt * (it_ >= 0).float()    # (TARGETS: a negative label: the rule names no item, the lesson is silent)
                    lpi_ = dst[I_HEAD].log_prob(it_.clamp(min=0))
                    out_ = dst[I_HEAD].probs[..., EN_I] if EN_I >= 0 else None       # the enemy as a target is not the item rule's to judge,
                    if TG_I is not None:                                 # nor is a holding place: the lesson is about which item, among the items
                        pl_ = dst[I_HEAD].probs[..., TG_I[0]:TG_I[1]].sum(-1)
                        out_ = pl_ if out_ is None else out_ + pl_
                    if out_ is not None:
                        lpi_ = lpi_ - torch.log1p(-out_.clamp(max=0.999))
                    ik_l = -(lpi_ * im_).sum() / im_.sum().clamp(min=1.0)
                    loss = loss + ik * ik_l
                if LEGS_LAB and (lt_w > 0 or epoch == 0):               # (--legs-teach) his own movement outputs toward what his legs chose
                    L_ = b_lab[:, chunk].long()
                    lm_ = (L_[..., 0] >= 0).float() * wgt                # a label is there, on the learner's frames
                    lms_ = [lm_ * dc, lm_ * dc, lm_ * dc, lm_]           # the keys on the frames his hand reads them, the view's turn on every one
                    lj_ = [L_[..., j].clamp(min=0) for j in range(4)]
                    if lt_w > 0:
                        tr_ = a.legs_teach_trunk                         # (as --teach-trunk: the same outputs, the shared layers held back)
                        dsl = ds if tr_ >= 1.0 else dists(pi_t(tr_ * hs_all + (1.0 - tr_) * hs_all.detach()))
                        lt_l = sum(-(dsl[j].log_prob(lj_[j]) * lms_[j]).sum() / lms_[j].sum().clamp(min=1.0) for j in range(4))
                        loss = loss + lt_w * lt_l
                    if epoch == 0:                                       # how near he is, on frames this update has not yet learnt from
                        with torch.no_grad():
                            hd_ = (L_[..., 4] > 0).float()
                            for j in range(4):
                                lpj_ = ds[j].log_prob(lj_[j])
                                hit_ = (ds[j].logits.argmax(-1) == lj_[j]).float()
                                lt_acc[j] += torch.stack([lms_[j].sum(), (-lpj_ * lms_[j]).sum(), (hit_ * lms_[j]).sum(), (lpj_.exp() * lms_[j]).sum(),
                                                          (lms_[j] * hd_).sum(), (hit_ * lms_[j] * hd_).sum()]).double()
                            lt_fr += torch.stack([wgt.sum(), lm_.sum(), (lm_ * hd_).sum()]).double()
                if HAND_LAB and (hd_w > 0 or epoch == 0):               # (--hand-teach) his weapon output toward the pros' shares of what he owns
                    Y_ = b_hand[:, chunk].float()
                    yl_ = (Y_.sum(-1) > 0.5).float() * wgt               # a label is there, on the learner's frames
                    ym_ = yl_ * dc                                       # ... and his hand reads the weapon key on that frame
                    Y_ = Y_ / Y_.sum(-1, keepdim=True).clamp(min=1e-6)   # (stored at half precision: a sum of 1 again)
                    if hd_w > 0:
                        tr_ = a.hand_teach_trunk
                        if tr_ >= 1.0:
                            lw_ = ds[HAND_HEAD].logits
                        else:                                            # as --teach-trunk (the same output, the shared layers held back to a
                            W_, c_ = pol.pi.weight[HAND_O:HAND_O + HAND_D], pol.pi.bias[HAND_O:HAND_O + HAND_D]     # share), on the weapon
                            lw_ = nn.functional.linear(hs_all.detach(), W_, c_)                                     # output's rows alone
                            if tr_ > 0:
                                z_ = nn.functional.linear(hs_all, W_.detach())
                                lw_ = lw_ + tr_ * (z_ - z_.detach())
                            lw_ = torch.log_softmax(lw_, -1)
                        hd_l = -((Y_ * lw_).sum(-1) * ym_).sum() / ym_.sum().clamp(min=1.0)
                        loss = loss + hd_w * hd_l
                    if epoch == 0:                                       # how near he is, on frames this update has not yet learnt from
                        with torch.no_grad():
                            lq_ = ds[HAND_HEAD].logits
                            hd_acc += torch.stack([wgt.sum(), yl_.sum(), ym_.sum(), (-(Y_ * lq_).sum(-1) * ym_).sum(),
                                                   (-(Y_ * torch.log(Y_.clamp(min=1e-9))).sum(-1) * ym_).sum(),
                                                   ((1.0 - lq_[..., 0].exp()) * ym_).sum(), ((1.0 - Y_[..., 0]) * ym_).sum()]).double()
                if RJ_LAB and b_rj is not None and (rj_w > 0 or epoch == 0):    # (--rj-teach) "jump and fire now" on the frames labelled
                    yr_ = (b_rj[:, chunk] > 0).float() * wgt             # a label, on the learner's frames (zeros elsewhere: no sync with the card)
                    Av_, Af_ = A[..., V_HEAD], A[..., FIRE_HEAD]
                    mj_ = yr_ * (1.0 if hm[V_HEAD] is None else hm[V_HEAD])          # the jump: where his vertical key's jump was read
                    if JE:
                        mj_ = mj_ * (Av_ != 4).float()
                    mf_ = yr_ * (1.0 if hm[FIRE_HEAD] is None else hm[FIRE_HEAD])    # the trigger: where it counts
                    one_ = torch.ones_like(Av_)
                    if rj_w > 0:
                        tr_ = a.rj_teach_trunk                       # (as --teach-trunk: the two outputs, the shared layers held back)
                        dsr_ = ds if tr_ >= 1.0 else dists(pi_t(tr_ * hs_all + (1.0 - tr_) * hs_all.detach()))
                        rj_l = (-(dsr_[V_HEAD].log_prob(one_) * mj_).sum() / mj_.sum().clamp(min=1.0)
                                - (dsr_[FIRE_HEAD].log_prob(one_) * mf_).sum() / mf_.sum().clamp(min=1.0))
                        loss = loss + rj_w * rj_l
                    if epoch == 0:                                   # how near he is, on frames this update has not yet learnt from
                        with torch.no_grad():
                            pj_ = ds[V_HEAD].log_prob(one_)
                            pf_ = ds[FIRE_HEAD].log_prob(one_)
                            rj_acc += torch.stack([yr_.sum(), mj_.sum(), (pj_.exp() * mj_).sum(), ((Av_ == 1).float() * mj_).sum(), (-pj_ * mj_).sum(),
                                                   mf_.sum(), (pf_.exp() * mf_).sum(), ((Af_ == 1).float() * mf_).sum(), (-pf_ * mf_).sum(),
                                                   ((Av_ == 1).float() * (Af_ == 1).float() * mj_ * mf_).sum(), (mj_ * mf_).sum(),
                                                   torch.zeros((), device=yr_.device)]).double()
                if RJC_LAB and b_rjc is not None and (rjc_w > 0 or epoch == 0):    # (--rj-copy) the runner's choices on the frames labelled
                    Y_ = b_rjc[:, chunk].long()                          # [T, players, outputs], -1: none
                    yl_ = (Y_[..., 0] >= 0).float() * wgt                # a label, on the learner's frames
                    tg_, mk_ = [], []
                    for j_ in range(RJC_H):
                        y_ = Y_[..., j_]
                        m_ = (y_ >= 0).float() * wgt * (1.0 if hm[j_] is None else hm[j_])
                        t_ = y_.clamp(min=0)
                        if JE and j_ == V_HEAD:                          # (JUMP_EVERY) the jump bit alone between the hand's readings: "jump"
                            Av_ = A[..., V_HEAD]                         # or "not jump" (3); nothing where it was not read (4)
                            m_ = m_ * (Av_ != 4).float()
                            t_ = torch.where(dc > 0.5, t_, torch.where(t_ == 1, t_, torch.full_like(t_, 3)))
                        tg_.append(t_)
                        mk_.append(m_)
                    if rjc_w > 0:
                        tr_ = a.rj_copy_trunk                        # (as --teach-trunk: the outputs, the shared layers held back)
                        dsc_ = ds if tr_ >= 1.0 else dists(pi_t(tr_ * hs_all + (1.0 - tr_) * hs_all.detach()))
                        rjc_l = sum(-(dsc_[j_].log_prob(tg_[j_]) * mk_[j_]).sum() / mk_[j_].sum().clamp(min=1.0) for j_ in range(RJC_H))
                        loss = loss + rjc_w * rjc_l
                    if epoch == 0:                                   # how near he is, on frames this update has not yet learnt from
                        with torch.no_grad():
                            agree_ = torch.ones_like(yl_)
                            rows_ = []
                            for j_ in range(RJC_H):
                                lpj_ = ds[j_].log_prob(tg_[j_])
                                aj_ = A[..., j_]
                                ok_ = (aj_ == tg_[j_]).float()
                                if JE and j_ == V_HEAD:                  # (the jump bit: drawn "jump" against a label "not jump" and back)
                                    ok_ = torch.where(tg_[j_] == 3, (aj_ != 1).float(), ok_)
                                agree_ = agree_ * torch.where(mk_[j_] > 0, ok_, torch.ones_like(ok_))
                                rows_.append(torch.stack([mk_[j_].sum(), (lpj_.exp() * mk_[j_]).sum(), (ok_ * mk_[j_]).sum(), (-lpj_ * mk_[j_]).sum()]))
                            kr_ = yl_ * (dc > 0.5).float()
                            rows_.append(torch.stack([yl_.sum(), kr_.sum(), (agree_ * kr_).sum(), torch.zeros((), device=yl_.device)]))
                            rjc_acc += torch.stack(rows_).double()
                if demo_w > 0:                                           # imitate what pro players did in the same situation
                    d_obs, d_act, d_first = demo_batch()
                    dh = torch.zeros(d_obs.shape[1], H, device=dev)
                    dl = []
                    for t in range(d_obs.shape[0]):
                        dh = dh * (1.0 - d_first[t])[:, None]
                        lg_, _, dh = pol.step(d_obs[t], dh)
                        dl.append(lg_)
                    dd_ = dists(torch.stack(dl)[8:])                      # the first frames only warm the memory up
                    da = d_act[8:]
                    demo_l = -sum(w_ * dd_[j].log_prob(da[..., j]).mean() for j, w_ in enumerate(demo_heads) if w_ > 0)
                    loss = loss + demo_w * demo_l
                    with torch.no_grad():
                        demo_acc = [float(((dd_[0].logits.argmax(-1) == da[..., 0]) & (dd_[1].logits.argmax(-1) == da[..., 1])).float().mean()),
                                    float((dd_[2].logits.argmax(-1) == da[..., 2]).float().mean()),
                                    float(((dd_[3].logits.argmax(-1) - da[..., 3]).abs() <= 1).float().mean())]
                opt.zero_grad()
                loss.backward()
                H2GR_ = None
                if H2:                                                   # (--head2) its gradient clipped on its own and kept out of the rest's clip
                    h2_acc[7] += nn.utils.clip_grad_norm_(pol.head2.parameters(), 0.5).detach().double()
                    h2_acc[8] += 1.0
                    H2GR_ = [p_.grad for p_ in pol.head2.parameters()]
                    for p_ in pol.head2.parameters():
                        p_.grad = None
                if LEGS_IN and not LEGS_SAID:                    # (LEGS_IN, stage a) said once: the frozen branch takes no gradient
                    LEGS_SAID.append(sum(int(p_.grad is not None and bool(p_.grad.abs().sum() > 0)) for p_ in pol.legs.parameters()))
                    print("legs inside: the first backward reached {} of the branch's {} tensors ({})".format(
                        LEGS_SAID[0], len(list(pol.legs.parameters())), "learning: all" if LEGS_LEARN else "frozen: none"), flush=True)
                if LEGS_LEARN:                                           # (--legs-learn) the branch's gradient is clipped on its own: the
                    ll_acc[6] += FV_(nn.utils.clip_grad_norm_(pol.legs.parameters(), 0.5))    # rest's step is as without it
                    ll_acc[7] += 1.0
                if HEADL:                                                # (--head) the head's gradient is clipped on its own: the rest's
                    hd_acc[12] += float(nn.utils.clip_grad_norm_(pol.head.parameters(), 0.5))       # step is as without it
                    hd_acc[13] += 1.0
                if UNI_ON:                                               # (--legs-feat, --legs-guide) their gradient clipped on its own: the
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if n_.startswith(UNI_PFX)], 0.5)    # rest's step is as without them
                if TRK:                                                  # (--track) the readout's gradient clipped on its own: the rest's
                    nn.utils.clip_grad_norm_(pol.track.parameters(), 0.5)    # step is as without it
                if BEL:                                                  # (--belief) the belief's on its own, as the readout's
                    nn.utils.clip_grad_norm_(pol.belief.parameters(), 0.5)
                    if BDROP is not None and pol.belief.inp.weight.grad is not None:    # (--brain-drop) no step on those columns
                        pol.belief.inp.weight.grad[:, BDROP] = 0.0
                if TRZ:                                                  # (--track-z) the second part's on its own
                    nn.utils.clip_grad_norm_(pol.trackz.parameters(), 0.5)
                if AH:                                                   # (--ahead) on its own, as the readout's
                    nn.utils.clip_grad_norm_(pol.ahead.parameters(), 0.5)
                if AUX:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("aux.") and not n_.startswith(UNI_PFX)
                                              and not (LEGS_LEARN and n_.startswith("legs.")) and not (HEADL and n_.startswith("head."))
                                              and not n_.startswith(BRAIN_PFX)], 0.5)
                    nn.utils.clip_grad_norm_(pol.aux.parameters(), 0.5)
                elif LEGS_LEARN:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("legs.") and not n_.startswith(UNI_PFX)
                                              and not (HEADL and n_.startswith("head.")) and not n_.startswith(BRAIN_PFX)], 0.5)
                elif HEADL:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("head.") and not n_.startswith(UNI_PFX)
                                              and not n_.startswith(BRAIN_PFX)], 0.5)
                elif UNI_ON:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith(UNI_PFX) and not n_.startswith(BRAIN_PFX)], 0.5)
                elif TRK:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith(BRAIN_PFX)], 0.5)
                else:
                    nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
                if H2GR_ is not None:                                    # (--head2) its gradient back for the step
                    for p_, g_ in zip(pol.head2.parameters(), H2GR_):
                        p_.grad = g_
                opt.step()
                if BDROP is not None:                                    # (--brain-drop) held at zero (Adam's moments move them otherwise)
                    with torch.no_grad():
                        pol.belief.inp.weight[:, BDROP] = 0.0
        if NOSYNC:                                                       # (--learn-nosync) the counters summed on the card, read once
            CHK_[:] = [None, None]
            XL_[:] = [None, None]
            kl_sum, cf_sum, OVK_[0] = float(kl_sum), float(cf_sum), float(OVK_[0])
            klh = klh.cpu().numpy()
            ll_acc, ug_acc = ll_acc.cpu(), ug_acc.cpu()
            if torch.is_tensor(ug_first[0]):
                ug_first[0] = float(ug_first[0])
            if trk_w > 0:
                tk_acc = tk_acc.cpu()
            if trz_w > 0:
                tz_acc = tz_acc.cpu()
            if AUX_W > 0:
                ax_s, ax_n, ax_w = ax_s.cpu(), ax_n.cpu(), float(ax_w)
                if AUX_MEAS:
                    mb_s = mb_s.cpu()
                if AUX_Q:
                    gx_s, gx_n, gx_h = gx_s.cpu(), gx_n.cpu(), [x_.cpu() for x_ in gx_h]
                    if "near" in AUX_Q:
                        nx_s, nx_n, nx_h = nx_s.cpu(), nx_n.cpu(), [x_.cpu() for x_ in nx_h]
        if SLOW:                                                         # (--slow-mem) the rollout's ticks join the ring
            RING.push(SL_PEND)
            SL_PEND = []
        if RINGH is not None:                                            # (--head) the rollout's ticks join its ring
            RINGH.push(HD_PEND)
            HD_PEND = []
        CTL_REC = None
        if CTL_ON:                                                       # (--control) the labels of this rollout: of frames CONTROL_D rows back
            t_ctl = time.time()
            cw_ = CTL_LIVE[0] * float(a.control) * (min(1.0, max(0.0, mins - CTL_T0) / a.control_warm) if a.control_warm > 0 else 1.0)
            if CTL_B is not None:
                CTL_REC = control_.record(control_.learn(pol.control, CTL_OPT, CTL_L, *CTL_B, lr=a.control_lr * cw_, dev=dev, gen=CTL_GEN),
                                          cw_, CTL_L, ring_gb=CTL_RING[0].nbytes() / 1e9 if CTL_RING[0] is not None else None)
            else:
                CTL_REC = dict(w=round(float(cw_), 4), frames=0)        # (none yet: the first CONTROL_D rows of a process)
            CTL_REC["secs"] = round(time.time() - t_ctl, 3)
            CTL_B = None
        WV_REC = None
        if WV_ON and WV_B is not None:                                   # (--win-value) the last rollout's states, learnt now (one rollout late)
            t_wv = time.time()
            wvw_ = WV_LIVE[0] * float(a.win_value) * (min(1.0, max(0.0, mins - WV_T0) / a.win_value_warm) if a.win_value_warm > 0 else 1.0)
            td_ = wv_.learn(WV, WV_OPT, WV_L, WV_PREV[0], WV_B, lr=a.win_value_lr * wvw_, dev=dev, gen=WV_GEN)
            WV_REC = wv_.record(td_, WV_B["cal"], wvw_, WV_L, gb=(WV_B["X"].numel() * 2 / 1e9) if WV_B["X"] is not None else None)
            WV_REC["secs"] = round(time.time() - t_wv, 3)
            WV_PREV[0] = dict(WV_B, cal=None)
            WV_B = None
        if os.environ.get("ROLL_DUMP"):                                   # (identity checks) the policy after the update
            torch.save({k_: v_.detach().cpu().clone() for k_, v_ in pol.state_dict().items()},
                       os.path.join(os.environ["ROLL_DUMP"], "pol_{}.pt".format(update)))
        t_end = time.time()
        total += T * N
        sim_min = T * DT_MIN * n_groups                                  # minutes of play, summed over the groups
        G = NP / n_groups                                                # mean players per group (for the per-player numbers)
        LG_ = np.atleast_1d(agg.get("legs", np.zeros(8)))              # (LEGS: the simulator's counters, see duel_env's stats)
        LR_ = np.atleast_1d(agg.get("legs_reads", np.zeros(2)))
        EN_ = np.atleast_1d(agg.get("en_frames", np.zeros(3)))
        HF_ = np.atleast_1d(agg.get("hold_frames", np.zeros(6)))
        rec = dict(update=update, steps=total, minutes=round(mins, 2), sps=int(total / (time.time() - t_start)),
                   fire_in_view=round(float(agg.get("fire_vis", 0) / max(1, agg.get("vis_frames_h", 0))), 3),
                   shot_cost_per_player_min=round(float(agg.get("shot_cost", 0.0) / max(1e-9, NP * T * DT_MIN)), 3),
                   shot_price=round(float(agg.get("shot_fac", 0.0) / max(1, agg.get("shot_n", 0))), 2),
                   armor_soaked_per_player_min=round(float(agg.get("soak", 0.0) / max(1e-9, NP * T * DT_MIN)), 1),
                   contest=dict(rounds=int(agg.get("contest_rounds", 0)),      # rounds begun as a race for a big item, and the
                                taken=round(float(agg.get("contest_taken", 0) / max(1, agg.get("contest_rounds", 0))), 2)),   # share a learner took it in
                   kl=round(kl_sum / max(1, kl_n), 5), clip_frac=round(cf_sum / max(1, kl_n), 4), lr=lr_now, lam=lam,
                   know=round(float(agg.get("know", 0.0) / max(1, agg.get("know_frames", 0))), 3),      # how well he knows where his enemy is, 0 to 1 (KNOW_PAY)
                   drops=dict(per_player_min=round(float(agg.get("drops", 0) / max(1e-9, NP * T * DT_MIN)), 3),            # weapons dead players left (DROPS)
                              taken=round(float(agg.get("pick_drop", 0) / max(1, agg.get("drops", 0))), 3),              # the share somebody took
                              new=round(float(agg.get("pick_drop_new", 0) / max(1, agg.get("pick_drop", 0))), 3)),       # ... of those, a weapon he did not have
                   pace=dict(pay_per_player_min=round(float(agg.get("pace_pay", 0.0) / max(1e-9, NP * T * DT_MIN)), 4),     # (PACE_PAY)
                             trip_speed=int(agg.get("trip_speed", 0.0) / max(1, agg.get("trip_frames", 0))),               # on his way, nobody about
                             over_320=round(float(agg.get("pace_frames", 0) / max(1, agg.get("trip_frames", 0))), 3)),
                   v14=dict(in_hand={w_: round(float(np.atleast_1d(agg.get("hand_w", np.zeros(len(WEAPONS))))[i_]              # the share of his playing time with each weapon in hand
                                                     / max(1.0, float(np.sum(agg.get("hand_w", 0.0))))), 3) for i_, w_ in enumerate(WEAPONS)},
                            blind_fire={w_: round(float(np.atleast_1d(agg.get("blind_w", np.zeros(len(WEAPONS))))[i_]          # ... of that time, firing it with no enemy seen for a second
                                                        / max(1.0, float(np.atleast_1d(agg.get("hand_w", np.zeros(len(WEAPONS))))[i_]))), 3) for i_, w_ in enumerate(WEAPONS)},
                            blind_rockets=dict(per_player_min=round(float(agg.get("blind_rl", 0) / max(1e-9, NP * T * DT_MIN)), 3),          # (BLIND_RULE)
                                               how={k_: round(float(np.atleast_1d(agg.get("blind_rl_how", np.zeros(5)))[i_] / max(1, agg.get("blind_rl", 0))), 3)
                                                    for i_, k_ in enumerate(("wasted", "jump", "near", "way", "place", "ahead")) if i_ < len(np.atleast_1d(agg.get("blind_rl_how", np.zeros(5))))}),
                            prefire_frames=int(agg.get("prefire_frames", 0)), **({"prefire_ahead": int(agg["prefire_ahead"])} if "prefire_ahead" in agg else {}),
                            **({"ahead_lives": round(float(np.atleast_1d(agg["ahead_lives"])[1] / max(1.0, float(np.atleast_1d(agg["ahead_lives"])[0]))), 4),
                                "ahead_p": float(getattr(E_, "BLIND_AHEAD_P", 0.0))} if "ahead_lives" in agg else {}),     # (BLIND_AHEAD_P) his lives begun with the waiver
                            blind_charged_frames=int(agg.get("blind_bill", 0)),
                            speed_pay_per_player_min=round(float(agg.get("speed_pay", 0.0) / max(1e-9, NP * T * DT_MIN)), 4),             # (SPEED_PAY: on his way in games)
                            speed_pay_run_per_player_min=round(float(agg.get("speed_pay_run", 0.0) / max(1e-9, NP * T * DT_MIN)), 4),     # ... in item runs
                            teacher_frames=round(float(agg.get("move_teach_frames", 0) / max(1, NP * T)), 4),                             # (RUN_TEACHER) the share of all frames it labels
                            height=dict(in_view={k_: round(float(np.atleast_1d(agg.get("high", np.zeros(3)))[i_] / max(1.0, float(np.sum(agg.get("high", 0.0))))), 3)       # B-160: with his enemy in view he stands lower by 48 units or more, level, higher
                                                 for i_, k_ in enumerate(("lower", "level", "higher"))},
                                        damage_from={k_: round(float(np.atleast_1d(agg.get("high_dmg", np.zeros(3)))[i_] / max(1.0, float(np.sum(agg.get("high_dmg", 0.0))))), 3)  # ... the damage he deals, by where he stands
                                                     for i_, k_ in enumerate(("lower", "level", "higher"))},
                                        pay_per_player_min=round(float(agg.get("high_pay", 0.0)) / max(1e-9, NP * T * DT_MIN), 4))),                 # (HIGH_PAY) what height added to his pay
                   v15=dict(jump_run_frames=round(float(agg.get("jump_frames", 0) / max(1, NP * T)), 4),                                   # (JUMPS) the share of all frames in jump runs
                            rj_run_frames=round(float(agg.get("rj_frames", 0) / max(1, NP * T)), 4),                                       # (RJ_RUN_P) rocket jump runs: the share of frames,
                            rj_tries=int(np.sum(agg.get("rj_tries", 0))),                                                                 # ... tries, the share that arrived, rockets a try
                            rj_over=round(float(np.sum(agg.get("rj_over", 0)) / max(1.0, float(np.sum(agg.get("rj_tries", 0))))), 3),
                            rj_shots=round(float(agg.get("rj_shots", 0)) / max(1.0, float(np.sum(agg.get("rj_tries", 0)))), 2),
                            rjs={m_: [[int(t_), round(float(o_ / max(1.0, t_)), 2)] for t_, o_ in                                         # ... per map and link (its place in the map's list of the links in use): tries, arrived
                                      zip(np.atleast_1d(v_.get("rj_tries", np.zeros(1))), np.atleast_1d(v_.get("rj_over", np.zeros(1))))][:int(np.max(np.nonzero(np.atleast_1d(v_.get("rj_tries", np.zeros(1))))[0], initial=-1)) + 1]
                                 for m_, v_ in agg_map.items() if float(np.sum(v_.get("rj_tries", 0))) > 0},
                            jump_tries=int(np.sum(agg.get("jump_tries", 0))),                                                             # ... tries begun, the share that got over, that fell short
                            jump_over=round(float(np.sum(agg.get("jump_over", 0)) / max(1.0, float(np.sum(agg.get("jump_tries", 0))))), 3),
                            jump_short=round(float(np.sum(agg.get("jump_short", 0)) / max(1.0, float(np.sum(agg.get("jump_tries", 0))))), 3),
                            jump_far=jump_far_rec(agg, agg_map),                                                                         # (JUMP_FAR_P) tries and over by start
                            jumps={m_: [[int(t_), round(float(o_ / max(1.0, t_)), 2)] for t_, o_ in                                       # ... per map and jump (its place in the map's list): tries, over
                                        zip(np.atleast_1d(v_.get("jump_tries", np.zeros(1))), np.atleast_1d(v_.get("jump_over", np.zeros(1))))][:int(np.max(np.nonzero(np.atleast_1d(v_.get("jump_tries", np.zeros(1))))[0], initial=-1)) + 1]
                                   for m_, v_ in agg_map.items() if float(np.sum(v_.get("jump_tries", 0))) > 0},
                            runs_by_map={m_: dict(items_per_min=round(float(v_.get("move_arrive", 0) / max(1, v_.get("move_frames", 0)) * 2400), 2),   # item runs and jump runs
                                                  speed=int(round(float(v_.get("move_speed", 0)) / max(1, v_.get("move_frames", 0)))),                       # by map: items a minute,
                                                  fast_air=round(float(v_.get("move_fast", 0) / max(1, v_.get("move_frames", 0))), 3),                      # speed, time fast in the air,
                                                  lava_per_min=round(float(v_.get("hurt_dmg", 0.0) / max(1, v_.get("players", 0)) * 2400), 1),             # lava and slime damage (all his time there)
                                                  move_only=m_ in move_maps)
                                         for m_, v_ in agg_map.items() if v_.get("move_frames", 0) > 0},
                            start_gun_per_player_min=round(float(agg.get("start_gun", 0) / max(1e-9, NP * T * DT_MIN)), 3),
                            start_gun_by={w_: int(np.atleast_1d(agg.get("start_gun_w", np.zeros(len(WEAPONS))))[i_])                     # ... by the weapon in hand (START_GUN_W)
                                          for i_, w_ in enumerate(WEAPONS) if np.atleast_1d(agg.get("start_gun_w", np.zeros(len(WEAPONS))))[i_] > 0},
                            in_hand_games={w_: round(float(np.atleast_1d(agg.get("hand_g", np.zeros(len(WEAPONS))))[i_]                # the share of his time in games (not in
                                                           / max(1.0, float(np.sum(agg.get("hand_g", 0.0))))), 4) for i_, w_ in enumerate(WEAPONS)}),   # one-weapon rounds) with each weapon in hand               # (START_GUN_P) lives begun with grenades or plasma in hand
                   legs=dict(share=round(float(LG_[0] / max(1.0, LG_[3])), 4),                 # (LEGS) the share of his time alive that his legs carried him,
                             in_games=round(float(LG_[4] / max(1.0, LG_[5])), 4),              # ... in games alone,
                             enemy_in_view=round(float(LG_[1] / max(1.0, LG_[0])), 4),         # ... of the legs' frames those with an enemy in view,
                             no_way=round(float(LG_[2] / max(1.0, LG_[3])), 4),                # ... his time with the switch on and no way to go,
                             asked=round(float(LR_[1] / max(1.0, LR_[0])), 4),                 # ... the share of the switch's readings that said "legs",
                             speed=[int(LG_[6] / max(1.0, LG_[0])), int(LG_[7] / max(1.0, LG_[3] - LG_[0]))],   # his speed on his legs, on his own
                             by_map={m_: round(float(np.atleast_1d(v_["legs"])[4] / max(1.0, float(np.atleast_1d(v_["legs"])[5]))), 3)        # in games, by map
                                     for m_, v_ in agg_map.items() if "legs" in v_ and float(np.atleast_1d(v_["legs"])[5]) > 0},
                             auto_switch_per_player_min=round(float(agg.get("auto_switch", 0)) / max(1e-9, NP * T * DT_MIN), 3)),   # (AUTO_SWITCH)
                   fight=dict(share=round(float(EN_[0] / max(1.0, LG_[3])), 4),                 # (FIGHT_TARGET) the share of his time alive with the enemy as his intention,
                              on_legs=round(float(EN_[1] / max(1.0, EN_[0])), 3),               # ... of it on his legs,
                              in_view=round(float(EN_[2] / max(1.0, EN_[0])), 3)),              # ... of it with the enemy in view
                   targets=dict(share=round(float(HF_[0] / max(1.0, LG_[3])), 4),               # (TARGETS) the share of his time alive with a holding place as his intention,
                                on_legs=round(float(HF_[1] / max(1.0, HF_[0])), 3),             # ... of it on his legs,
                                at_it=round(float(HF_[2] / max(1.0, HF_[0])), 3),               # ... standing at the place,
                                in_view=round(float(HF_[3] / max(1.0, HF_[0])), 3),             # ... with the enemy in view;
                                reached_per_player_min=round(float(HF_[4] / max(1e-9, NP * T * DT_MIN)), 3),      # places reached,
                                speed_on_the_way=int(HF_[5] / max(1.0, HF_[0] - HF_[2]))),     # his speed while not yet at it
                   closing=[int(v_ / max(1.0, c_)) for v_, c_ in zip(np.atleast_1d(agg.get("close_v", np.zeros(3))),       # his speed toward an enemy in view
                                                                    np.atleast_1d(agg.get("close_n", np.zeros(3))))],     # (health plus armor under 60, to 125, over)
                   kl_heads=[round(float(x), 5) for x in klh / max(1, kl_n)] if old_h is not None else None,
                   by_map={m_: dict(bare=round(float(v_.get("stack_bare", 0) / max(1, v_.get("stack_frames", 0))), 3),
                                    big_weapons=round(float(v_.get("stack_big", 0) / max(1, v_.get("stack_frames", 0))), 2),
                                    over=round(float(v_.get("stack_over", 0) / max(1, v_.get("stack_frames", 0))), 3),
                                    first_weapon_s=round(float(v_["first_wp"][0] / max(1.0, v_["first_wp"][1])), 1) if "first_wp" in v_ else None,
                                    weapons_per_player_min=round(float(v_.get("pick_wp", 0) / max(1e-9, v_.get("players", 0) * DT_MIN)), 2),
                                    mega_red_per_player_min=round(float((v_.get("pick_mega", 0) + v_.get("pick_ra", 0)) / max(1e-9, v_.get("players", 0) * DT_MIN)), 2),
                                    frags_per_player_min=round(float(v_.get("frags", 0) / max(1e-9, v_.get("players", 0) * DT_MIN)), 2),
                                    in_view=round(float(v_.get("visible", 0) / max(1, v_.get("players", 0))), 3),
                                    fire=round(float(v_.get("fire_frames", 0) / max(1, v_.get("play_frames", 0))), 3))
                           for m_, v_ in agg_map.items()},
                   frags_per_match_min=round(agg["frags"] / sim_min, 3),
                   suicides_per_match_min=round(agg["suicides"] / sim_min, 3),
                   hit_rate={w: round(float(agg[w + "_hits"] / max(1, agg[w + "_shots"])), 3) for w in WEAPONS},
                   frag_share={w: round(float(agg[w + "_frags"] / max(1, sum(agg[x + "_frags"] for x in WEAPONS))), 2) for w in WEAPONS},
                   pickups_per_player_min={k[5:]: round(float(agg[k] / (G * sim_min)), 2)
                                           for k in ("pick_hp", "pick_ar", "pick_mega", "pick_ra", "pick_wp", "pick_wpnew", "pick_am") if k in agg},
                   acc_visible={w: round(float(agg[w + "_hits"] / max(1, agg[w + "_shots_vis"])), 3) for w in ("rl", "rg", "lg")},
                   aim_err_visible=round(float(agg["aim_err"] / max(1, agg["aim_frames"])), 2),
                   on_target_visible=round(float(agg["on_target"] / max(1, agg["aim_frames"])), 3),
                   switches_per_min=round(float(agg["switches"] / max(1, agg["play_frames"]) * 2400), 1),
                   fire=round(float(agg["fire_frames"] / max(1, agg["play_frames"])), 3),
                   blind_fire=round(float(agg["blind_frames"] / max(1, agg["play_frames"])), 3),
                   weapon_by_dist={b: {w: round(float(agg["w_dist"][j, i] / max(1.0, agg["w_dist"][j].sum())), 2)
                                       for i, w in enumerate(WEAPONS) if agg["w_dist"][j, i] / max(1.0, agg["w_dist"][j].sum()) >= 0.05}
                                   for j, b in enumerate(("close", "mid", "far"))},
                   move=dict(arrive_per_min=round(float(agg["move_arrive"] / max(1, agg["move_frames"]) * 2400), 2),
                             speed=int(round(agg["move_speed"] / max(1, agg["move_frames"]))),
                             fast_air=round(float(agg["move_fast"] / max(1, agg["move_frames"])), 3)),
                   vs_bot=dict(frags_per_min=round(float(agg["frags_vs_bot"] / max(1, agg["bot_frames"]) * 2400), 2),
                               deaths_per_min=round(float(agg["bot_frags"] / max(1, agg["bot_frames"]) * 2400), 2)),
                   vs_persona={n_: [round(float(agg["vs_persona"][0, j] / max(1.0, agg["vs_persona"][2, j]) * 2400), 2),
                                    round(float(agg["vs_persona"][1, j] / max(1.0, agg["vs_persona"][2, j]) * 2400), 2)]
                               for j, n_ in enumerate(PERSONAS)},
                   course={key: dict(speed=int(agg["course"][k_, 5] / max(1.0, agg["course"][k_, 6])),
                                     finishes_per_min=round(float(agg["course"][k_, 1] / max(1.0, agg["course"][k_, 6]) * 2400), 2),
                                     falls_per_min=round(float(agg["course"][k_, 7] / max(1.0, agg["course"][k_, 6]) * 2400), 2))
                           for k_, key in enumerate(course_keys) if agg["course"][k_, 6] > 0},
                   arena=dict(frags_per_min=round(float(agg["arena"][0] / max(1.0, agg["arena"][1]) * 2400 * G), 2),
                              speed=int(agg["arena"][2] / max(1.0, agg["arena"][1])),
                              in_view=round(float(agg["arena"][3] / max(1.0, agg["arena"][1])), 3),
                              damage_per_min=round(float(agg["arena"][4] / max(1.0, agg["arena"][1]) * 2400), 1),
                              standing=round(float(agg["arena"][5] / max(1.0, agg["arena"][1])), 3),
                              looking_up_or_down=round(float(agg["arena"][6] / max(1.0, agg["arena"][1])), 3),
                              crouched=round(float(agg["arena"][7] / max(1.0, agg["arena"][1])), 3),
                              zoomed=round(float(agg["zoom_frames"] / max(1.0, agg["arena"][1])), 3)),
                   yard=dict(mega_per_player_min=round(float(agg.get("big_taken", np.zeros(2))[0] / (G * sim_min)), 3),
                             red_armor_per_player_min=round(float(agg.get("big_taken", np.zeros(2))[1] / (G * sim_min)), 3),
                             mega_lay_s=round(float(agg.get("big_wait", np.zeros(2))[0] / max(1.0, agg.get("big_taken", np.zeros(2))[0])), 1),
                             red_armor_lay_s=round(float(agg.get("big_wait", np.zeros(2))[1] / max(1.0, agg.get("big_taken", np.zeros(2))[1])), 1),
                             first_weapon_s=round(float(agg.get("first_wp", np.zeros(2))[0] / max(1.0, agg.get("first_wp", np.zeros(2))[1])), 1),
                             lives_with_a_weapon_per_min=round(float(agg.get("first_wp", np.zeros(2))[1] / (G * sim_min)), 2),
                             void_deaths_per_player_min=round(float(agg.get("void_deaths", 0) / (G * sim_min)), 3),
                             mega_lying=round(float(agg["big_up"][0] / max(1, agg["big_frames"])), 3),
                             red_armor_lying=round(float(agg["big_up"][1] / max(1, agg["big_frames"])), 3),
                             lava_dmg_per_player_min=round(float(agg.get("hurt_dmg", 0.0) / (G * sim_min)), 1)),
                   intent=dict(share={nm: round(float(agg["intent_frames"][k] / max(1.0, agg["intent_frames"].sum())), 3)
                                      for k, nm in enumerate(E_.INTENTS)},
                               trips_per_player_min=round(float(agg["intent_trips"][0] / (G * sim_min)), 2),
                               reached=round(float(agg["intent_trips"][1] / max(1.0, agg["intent_trips"][0])), 3),
                               abandoned=round(float(agg["intent_trips"][2] / max(1.0, agg["intent_trips"][0])), 3),
                               died=round(float(agg["intent_trips"][3] / max(1.0, agg["intent_trips"][0])), 3),
                               reach_s=round(float(agg["intent_reach"] / max(1.0, agg["intent_trips"][1])), 1),
                               seek=round(seek_now, 3)),
                   run_and_gun=dict(damage_per_min=round(float(agg["gun"][0] / max(1.0, agg["gun"][1]) * 2400), 1),
                                    speed=int(agg["gun"][2] / max(1.0, agg["gun"][1]))),
                   keys=dict(asked_per_s=round(float(agg["key_asked"] / max(1.0, G * sim_min * 60)), 2),
                             changes_per_s=round(float(agg["key_changes"] / max(1.0, G * sim_min * 60)), 2),
                             refused=round(float(agg["key_blocked"] / max(1.0, agg["key_blocked"] + agg["key_changes"])), 3)),
                   teach=[round(kick, 3), round(float(kick_l), 3)],
                   intent_teach=[round(ik, 3), round(float(ik_l), 3)],
                   rule_contest=round(float(np.atleast_1d(agg.get("rule_contest", np.zeros(2)))[0]) / max(1.0, float(np.atleast_1d(agg.get("rule_contest", np.zeros(2)))[-1])), 4),
                   rule_hunt=round(float(np.atleast_1d(agg.get("rule_hunt", np.zeros(2)))[0]) / max(1.0, float(np.atleast_1d(agg.get("rule_hunt", np.zeros(2)))[-1])), 4),      # (RULE_HUNT) the share of the rule's item frames silenced where hunting is reasonable
                   rule_blind=round(float(np.atleast_1d(agg.get("rule_blind", np.zeros(2)))[0]) / max(1.0, float(np.atleast_1d(agg.get("rule_blind", np.zeros(2)))[-1])), 4),      # (RULE_BLIND) the share of the rule's frames silenced by a fresh belief   # (RULE_CONTEST) the share of the rule's item frames silenced
                   weapon_teach=[round(wk, 3), round(float(wk_l), 3)],
                   weapon_rule_agree=round(float(agg.get("wrule_agree", 0) / max(1, agg.get("wrule_frames", 0))), 3),
                   stack=dict(over=round(float(agg.get("stack_over", 0)) / max(1, agg.get("stack_frames", 0)), 3),
                              big_weapons=round(float(agg.get("stack_big", 0)) / max(1, agg.get("stack_frames", 0)), 2),
                              bare=round(float(agg.get("stack_bare", 0)) / max(1, agg.get("stack_frames", 0)), 3),
                              low=round(float(agg.get("stack_low", 0)) / max(1, agg.get("stack_frames", 0)), 3),
                              taught=round(float(agg.get("stack_teach_frames", 0)) / max(1, agg.get("stack_frames", 0)), 3)),
                   style={nm_: dict(share=round(float(sy_[0] / max(1.0, agg["style"][:, 0].sum())), 2),
                                    his_weapon_in_hand=round(float(sy_[1] / max(1.0, sy_[0])), 3),
                                    big_weapons=round(float(sy_[7] / max(1.0, sy_[0])), 2),
                                    in_band=round(float(sy_[3] / max(1.0, sy_[2])), 3),
                                    distance=int(sy_[4] / max(1.0, sy_[2])),
                                    dmg_with_it=round(float(sy_[6] / max(1.0, sy_[5])), 3),
                                    frags_per_death=round(float(sy_[8] / max(1.0, sy_[9])), 2))
                          for nm_, sy_ in zip(("general", "rockets", "rail", "lightning"), agg["style"])} if "style" in agg else {},
                   collect_fight=dict(rounds=int(agg.get("cf_rounds", 0)), stack_kills=int(agg.get("cf_stack_kills", 0)),
                                      plain_kills=int(agg.get("cf_plain_kills", 0))),
                   items_room=dict(mega_per_2min=round(float(agg["lab_items"][0] / max(1.0, agg["lab_items"][2]) * 4800), 2),
                                   red_armor_per_2min=round(float(agg["lab_items"][1] / max(1.0, agg["lab_items"][2]) * 4800), 2)),
                   demo=dict(weight=round(demo_w, 3), loss=round(float(demo_l), 3), keys_right=round(demo_acc[0], 3),
                             vertical_right=round(demo_acc[1], 3), turn_within_one_bin=round(demo_acc[2], 3)),
                   crouch=round(float(agg["duck_frames"] / max(1, agg["play_frames"])), 3),
                   walk=round(float(agg["walk_frames"] / max(1, agg["play_frames"])), 3),
                   fall_dmg_per_min=round(float(agg["fall_dmg"] / (G * sim_min)), 2),
                   target_kills_per_min=round(float(agg["target_kills"] / max(1, agg["aim_round_frames"]) * 2400), 2),
                   visible=round(agg["visible"] / max(1, agg["players"]), 3),
                   air_fast=round(agg["air_fast"] / max(1, agg["players"]), 3),
                   jerk=round(agg["jerk"] / max(1, agg["players"]), 2),
                   vs_snapshot_kill_share=round(lk[0] / max(1, lk[0] + lk[1]), 3) if R_SN and not R_VA else None,
                   vs_anchor_kill_share=round(lk[0] / max(1, lk[0] + lk[1]), 3) if R_SN and R_VA else None,
                   league_size=R_NS, entropy=round(float(en), 3), close_p=round(close_p, 2),
                   time=dict(rollout=round(T_ROLL, 1), learn=round(t_end - t_learn, 1),                 # seconds of this update
                             rollout_parts=R.get("RP")),                                                              # ... the rollout's by part
                   gpu=dict(peak_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2), held_gb=round(torch.cuda.memory_reserved() / 1e9, 2))
                   if dev.type == "cuda" else None)                    # the card's memory at its peak in this update
        if SLOW:                                                         # (--slow-mem) its door, what comes through it beside his fast memory,
            with torch.no_grad():                                        # the ring's ticks, the seconds of its parts (fold + re-run before the
                ds_ = pol.slow.door(SM.s[:2048])                         # rollout; the passes of the update)
                rec["slow"] = dict(w=round(float(pol.slow.door.weight.abs().mean()), 6),
                                   share=round(float(ds_.abs().mean() / (CARRY["h"][:2048].abs().mean() + 1e-8)), 4),
                                   s=round(float(SM.s[:2048].abs().mean()), 4), ring=RING.L,
                                   ring_min=round(RING.L * SLOW["every"] * 0.025 / 60.0, 2),
                                   fold_s=round(sl_secs[0], 2), pass_s=round(sl_secs[1], 2))
        BTOK_EFFECT = None                                               # (v0.4.1) the token's change to the door's output, below
        if pol.attn is not None:                                         # the door: its weights, and what comes through it beside the old encoder's
            with torch.no_grad():
                xs_ = b_obs[T - 1, :2048].float() if not OVL else b_obs[:2048, T - 1].to(dev).float()
                rec["door"] = dict(w=round(float(pol.attn.door.weight.abs().mean()), 6),
                                   share=round(float(pol.attn(xs_).abs().mean() / (pol.enc(xs_).abs().mean() + 1e-8)), 4))
                if BTOK and B_BTOK is not None and BTG_R > 0:            # (v0.4.1) what the brain's token changes in what comes through the
                    bs_ = (B_BTOK[T - 1, :2048] if not OVL else B_BTOK[:2048, T - 1]).to(dev).float()      # door, against the door's
                    a0_ = pol.attn(xs_)                                  # own size (the last frame's first 2048 players)
                    BTOK_EFFECT = round(float((pol.attn(xs_, bt=bs_, bg=BTG_R) - a0_).abs().mean() / (a0_.abs().mean() + 1e-8)), 4)
        if UNI_ON:                                                       # (--legs-feat, --legs-guide) the parts: legs_door's size and the share
            with torch.no_grad():                                        # of his fast GRU's input variance that comes through it; the guide's
                rec_u = dict(first_err=ug_first[0])                      # weights and how often his own choice is the branch's (switch off)
                if UNI_FEAT:
                    xs_ = b_obs[T - 1, :2048].float() if not OVL else b_obs[:2048, T - 1].to(dev).float()
                    e_ = pol.enc(xs_) + (pol.attn(xs_) if pol.attn is not None else 0.0)
                    xl_ = b_lx[T - 1, :2048].to(dev)
                    d_ = pol.uni_parts(xl_)[0]
                    vd_, vt_ = float(d_.var(0).sum()), float((e_ + d_).var(0).sum())
                    rec_u.update(door_norm=round(float(pol.legs_door.weight.norm()), 6), door_bias=round(float(pol.legs_door.bias.norm()), 6),
                                 door_share=round(vd_ / max(vt_, 1e-12), 6), way=round(float(LU_.t_way(xl_).mean()), 4))
                if UNI_GUIDE:
                    ua_ = ug_acc.numpy()
                    rec_u.update(w=[round(float(x_), 5) for x_ in pol.legs_guide], outs=list(L_TAKES),
                                 frames=[int(x_) for x_ in ua_[:, 0]], agree=[round(float(x_), 4) for x_ in ua_[:, 1] / np.maximum(1.0, ua_[:, 0])],
                                 p_same=[round(float(x_), 4) for x_ in ua_[:, 2] / np.maximum(1.0, ua_[:, 0])])
                rec_u["moved"] = round(max(float((p_ - UNI_W0[n_]).abs().max()) for n_, p_ in pol.named_parameters() if n_ in UNI_W0), 7)
                rec["unify"] = rec_u
        if GATE_M is not None:                                           # (--gate-open) the gate of the tokens that began below zero: the
            rec["gate"] = dict(value=round(float(pol.attn.gate[GATE_M].min()), 4) if bool(GATE_M.any()) else 0.0,   # lowest now, how many
                               tokens=int(GATE_M.sum()), over=a.gate_open,                                           # they are, the opening asked
                               start=a.gate_from if a.gate_open > 0 else None)                                       # for (0 minutes: none)
        if LONG:
            rec["long"] = dict(share=round(long_c, 3), gap=round(long_gap, 4))
        if H2:                                                           # (--head2) the strategy head: its gate, lessons, size of its outputs, step
            ha2_ = h2_acc.cpu().numpy()
            with torch.no_grad():
                pin_ = pol.head2.plan_in.weight.norm()
            rec["head2"] = dict(
                gate=round(H2G_R, 5), cap=a.head2_cap, open_min=a.head2_open, pg_w=round(H2_PG_[0] * H2_PG_[2], 4), plan_grad=H2_PG_[1],
                pg_loss=round(float(ha2_[1] / max(1.0, ha2_[6])), 5), v_loss=round(float(ha2_[2] / max(1.0, ha2_[0])), 5),
                plan=round(float(ha2_[3] / max(1.0, ha2_[0])), 4),                                   # the plan's mean length (before the gate)
                gin_share=round(float(ha2_[9] / max(1.0, ha2_[10])), 6),                              # |gate x plan_in(plan)| beside his fast GRU's input
                bias=round(float(ha2_[4] / max(1.0, ha2_[6])), 5),                                    # the bias's centred length on read frames
                bias_share=round(float(ha2_[4] / max(1e-9, ha2_[4] + ha2_[5])), 5),                   # ... beside the hands' own intention logits
                clip_share=round(float(ha2_[11] / max(1.0, ha2_[6])), 4),
                grad=round(float(ha2_[7] / max(1.0, ha2_[8])), 5),                                    # its gradient's norm before its clip (0.5)
                plan_in_w=round(float(pin_), 6), target_w=round(float(pol.head2.target.weight.norm()), 6),
                v=round(float(B_VH[:T].mean()), 4), ret=round(float(RET_H.mean()), 4), adv_sd=round(float(ADV_H.std()), 4),
                lr=opt.param_groups[-1]["lr"], opp_open=bool(snaps and opp.h2_open))
        if HEADL:                                                        # (--head) the plan's size, plan_in, the head's part of his target, its
            ha_ = hd_acc.numpy()                                         # values' and win head's losses, the read, its step (first pass)
            rs_ = torch.stack(HO_[1]).sum(0).cpu().numpy() if HO_[1] else np.zeros(3)
            with torch.no_grad():
                pi_o = pol.head.plan_in(HS.plan[:2048]).abs().mean()
                en_o = pol.enc(b_obs[T - 1, :2048].float()).abs().mean()
            te_n = max(1.0, float(ha_[6]))
            rec["head"] = dict(
                plan=round(float(ha_[1] / max(1.0, ha_[0])), 4),                                    # the plan's mean length on his ticks
                plan_in=dict(w=round(float(pol.head.plan_in.weight.norm()), 6), b=round(float(pol.head.plan_in.bias.norm()), 6),
                             share=round(float(pi_o / (en_o + 1e-8)), 5)),                         # what it adds to his fast GRU's input, beside e
                target_share=round(float(ha_[9] / max(1e-9, ha_[9] + ha_[10])), 5),                 # the head's part of his intention's logits (centred)
                target_w=round(float(pol.head.target.weight.abs().mean()), 6), way_w=round(float(pol.head.way.weight.abs().mean()), 6),
                v_loss=round(float(ha_[2] / max(1.0, ha_[3])), 4),
                win=dict(on=HD_WG >= 0, loss=round(float(ha_[4] / te_n), 4),                       # the loss on the true bands' ticks, the share of ticks
                         labelled=round(float(ha_[5] / max(1.0, ha_[0])), 4), ends=int(ha_[6]),     # with a target, those with the true band; there: the chance of the
                         p_true=round(float(ha_[7] / te_n), 4), right=round(float(ha_[8] / te_n), 4),          # true band, called right, and
                         confidence=round(float(ha_[15] / te_n), 4)),                                         # the chance given its own call
                read=dict(entropy=round(float(rs_[0] / max(1.0, rs_[1])), 4),                       # the read's attention entropy (nats, a head)
                          slots=round(float(rs_[2] / max(1.0, rs_[1] / HEADL["read_heads"])), 1),   # the slots it read from
                          full=round(float(rs_[2] / max(1.0, rs_[1] / HEADL["read_heads"])) / HEADL["slots"], 4)),
                kl=dict(target=round(float(klh[I_HEAD] / max(1, kl_n)), 6), way=round(float(klh[W_HEAD] / max(1, kl_n)), 6) if W_HEAD >= 0 else None)
                if old_h is not None else None,
                grad=round(float(ha_[12] / max(1.0, ha_[13])), 4), lr=opt.param_groups[1]["lr"],
                events=round(float((b_ev != 0).float().mean()), 4),                                 # the share of event numbers not zero
                win_games=round(float((b_wg > -0.5).float().mean()), 4) if HD_WG >= 0 else 0.0,    # the share of frames in labelled games
                opp_open=bool(snaps and opp.head_open),                                             # the league's network has an open head
                ring=RINGH.L if RINGH is not None else 0, secs=[round(hd_secs[0], 2), round(hd_secs[1], 2)])
        if TRK_ON:                                                       # (--track, --info-pay) the readout's lesson and its counters (the rollout's)
            rec["track"] = dict(w=round(trk_w, 4), trunk=a.track_trunk if not BEL else 0.0, parts=TRK_PARTS, every=TRK_EVERY, rollout=R["trk"],
                                **({"src": "belief", "iso": BEL_ISO if trk_w > 0 else None} if BEL else {}))
            if BH is not None:                                           # (--brain-human) the people's lesson: its weight and its parts' means
                rec["brain_human"] = dict(w=round(bh_w, 4), live=BH_LIVE[0], iso=BH_ISO if bh_w > 0 else None, **(BH.take_counters() or {}))
            if trk_w > 0 and float(tk_acc[-1]) > 0:
                rec["track"]["loss"] = {p_: round(float(tk_acc[i_] / tk_acc[-1]), 4) for i_, p_ in enumerate(track_.PARTS)}
                rec["track"]["frames"] = int(tk_acc[-1])
            if TRZ_ON:
                rec["track"]["z_w"] = round(trz_w, 4)
                rec["track"]["z_parts"] = TRZ_PARTS
                if trz_w > 0 and float(tz_acc[-1]) > 0:
                    rec["track"]["z_loss"] = {p_: round(float(tz_acc[i_] / tz_acc[-1]), 4) for i_, p_ in enumerate(trz_.PARTS)}
        if BTOK:                                                         # (v0.4.1) the brain token: the gate it was played and learnt at, the proof
            rec["btoken"] = dict(gate=round(BTG_R, 5), fed=B_BTOK is not None, cap=a.btoken_cap, open_min=a.btoken_open,
                                 belief_lr=BEL_LR_NOW[0] if BEL else None, iso=BTOK_ISO, effect=BTOK_EFFECT)
            if B_BTOK is not None:
                bb_ = B_BTOK[:, :256].float() if OVL else B_BTOK[:, :256].float().transpose(0, 1)
                vi_ = BTOK_L["feats"].index("valid")
                rec["btoken"]["valid"] = round(float(bb_[..., vi_].mean()), 4)
                rec["btoken"]["abs_mean"] = round(float(bb_.abs().mean()), 4)
        if RF:                                                           # (v0.4.2a) the rule fade: the gate it was played and learnt at; the
            rec["rule_fade"] = dict(g=round(RFG_R, 5), cap=a.rule_fade_cap, open_min=a.rule_fade_open, opp_g=round(RF_OPP[0], 5),
                                    readers=RF_READ, blind=bool(RF_L["blind"]))      # simulators' readers: lives begun on the brain, each reader's
            if RF_READ and "brain_lives" in agg:                         # frames on the brain, the place error of the answer each read
                bl_ = np.atleast_1d(agg["brain_lives"]).astype(np.float64)
                br_ = np.atleast_1d(agg.get("brain_read", np.zeros(2 * len(E_.BRAIN_READERS)))).astype(np.float64).reshape(-1, 2)
                be_ = np.atleast_1d(agg.get("brain_err", np.zeros(3 * len(E_.BRAIN_ERR_BINS)))).astype(np.float64).reshape(-1, 3)
                rec["rule_fade"].update(lives=int(bl_[0]), lives_on_brain=round(float(bl_[1] / max(1.0, bl_[0])), 4),
                                        read_on_brain={k_: [int(br_[i_, 0]), round(float(br_[i_, 1] / max(1.0, br_[i_, 0])), 4)]
                                                       for i_, k_ in enumerate(E_.BRAIN_READERS)},
                                        err_by_unseen={k_: dict(n=int(be_[i_, 0]), rule=round(float(be_[i_, 1] / max(1.0, be_[i_, 0])), 1),
                                                                brain=round(float(be_[i_, 2] / max(1.0, be_[i_, 0])), 1))
                                                       for i_, k_ in enumerate(E_.BRAIN_ERR_BINS)})
        if ah_w > 0 and float(ah_acc[NPA_]) > 0:                         # (--ahead) its lesson's parts and the place's error by horizon
            ah_acc = ah_acc.cpu()
            rec["ahead"] = dict(w=round(ah_w, 4), parts=AH_PARTS, race=bool(AH_L.get("race")),
                                loss={p_: round(float(ah_acc[i_] / max(1.0, float(ah_acc[NPA_ + i_]))), 4) for i_, p_ in enumerate(ahead_.PARTS)},
                                frames=[int(ah_acc[NPA_ + i_]) for i_ in range(NPA_)],
                                err_units={"{:g}s".format(h_): round(float(ah_acc[2 * NPA_ + i_] / max(1.0, float(ah_acc[-1]))), 1)
                                           for i_, h_ in enumerate(ahead_.HORIZ)})
        if CTL_REC is not None:                                          # (--control) scored on each label before it is learnt from
            rec["control"] = CTL_REC
        if WV_REC is not None:                                           # (--win-value) the shadow win value: its lesson, its calibration
            rec["win_value"] = WV_REC
        if AUX_W > 0 and ax_w > 0:                                       # (--aux) each loss, and how well he foretells (first pass of the update)
            def q_(i_, d_=4):
                return round(float(ax_s[i_] / max(1.0, float(ax_n[int(AUX_MI[i_])]))), d_)
            rec["aux"] = dict(w=round(aux_w, 4), trunk=a.aux_trunk, heads=list(AUX_HEADS), frames=list(AUX_FR),
                              loss=dict(place=q_(0), appear=q_(3), fight=round(q_(8, 6) + q_(13, 6), 4), items=round(q_(16, 6) + q_(19, 6), 4)),
                              parts=dict(fight_class=q_(8), fight_damage=q_(13), mega=q_(16), red=q_(19)),
                              place_units=q_(1, 1),                      # (a) the mean distance between where he puts the unseen enemy and where he is
                              appear_deg=[q_(4, 2), q_(5, 2)],           # (b) the mean absolute error of the angle: sideways, up-down
                              fight_right=q_(9),                         # (c) the share of fights called right ...
                              fight_base=dict(neither=q_(10), frag=q_(11), fragged=q_(12)),      # ... and how the labelled fights end
                              damage_points=q_(14, 2),                   # ... the mean error of the damage dealt less taken
                              items_s=[q_(17, 2), q_(20, 2)],            # (d) the mean error in seconds: mega, red armor
                              zero=dict(place_units=q_(2, 1), appear_deg=[q_(6, 2), q_(7, 2)], damage_points=q_(15, 2),      # the same errors had he
                                        items_s=[q_(18, 2), q_(21, 2)]),                                                  # answered nothing (zeros)
                              labelled={k_: round(float(ax_n[i_] / ax_w), 4)       # the share of the learner's frames with each label
                                        for i_, k_ in enumerate(("place", "appear", "fight", "damage", "mega", "red"))},
                              label_s=round(aux_secs, 2))
            if AUX_Q:                                                    # (2026-10-12) each answer as the share called right, beside the share of
                ra_ = rec["aux"]                                         # the commonest true answer ("zero": had he always given that one)

                def g_(i_, j_, d_=4):
                    return round(float(gx_s[i_] / max(1.0, float(gx_n[j_]))), d_)

                def z_(j_):
                    return round(float(gx_h[j_].max() / max(1.0, float(gx_h[j_].sum()))), 4)

                def sh_(j_):
                    return [round(float(x_), 4) for x_ in (gx_h[j_] / max(1.0, float(gx_h[j_].sum()))).tolist()]

                if "target" in AUX_Q:                                    # what the enemy goes for: overall, and with the enemy not in view
                    ra_["loss"]["target"] = g_(0, 0)
                    ra_["target_right"], ra_["target_unseen_right"] = g_(5, 0), g_(10, 5)
                    ra_["zero"].update(target_right=z_(0), target_unseen_right=z_(5))
                    ra_["target_share"] = sh_(0)                         # how often each intention is the true answer (the simulator's INTENTS)
                if "strength" in AUX_Q:                                  # his stack's band; the weapon in his hand (enemy not in view)
                    ra_["loss"]["strength"] = round(g_(1, 1, 6) + g_(2, 2, 6), 4)
                    ra_["parts"].update(band=g_(1, 1), weapon=g_(2, 2))
                    ra_["band_right"], ra_["weapon_right"] = g_(6, 1), g_(7, 2)
                    ra_["zero"].update(band_right=z_(1), weapon_right=z_(2))
                    ra_["band_share"], ra_["weapon_share"] = sh_(1), sh_(2)      # under 75, 75-125, 125-200, over 200; the simulator's WEAPONS
                if "first" in AUX_Q:                                     # who takes the mega, the red armor next: [mega, red]
                    ra_["loss"]["first"] = round(g_(3, 3, 6) + g_(4, 4, 6), 4)
                    ra_["parts"].update(first_mega=g_(3, 3), first_red=g_(4, 4))
                    ra_["first_right"] = [g_(8, 3), g_(9, 4)]
                    ra_["zero"]["first_right"] = [z_(3), z_(4)]
                    ra_["first_share"] = [sh_(3), sh_(4)]                # nobody within the window, he, another player
                    ra_["first_frames"] = AUX_FW
                ra_["labelled"].update({k_: round(float(gx_n[j_] / ax_w), 4)     # the share of the learner's frames with each label
                                        for j_, (k_, h_) in enumerate((("target", "target"), ("band", "strength"), ("weapon", "strength"),
                                                                       ("first_mega", "first"), ("first_red", "first"), ("target_unseen", "target")))
                                        if h_ in AUX_Q})
                if "near" in AUX_Q:                                      # near which landmark the enemy is: [now, later], overall and unseen
                    def n_(i_, j_, d_=4):
                        return round(float(nx_s[i_] / max(1.0, float(nx_n[j_]))), d_)

                    def nz_(j_):
                        return round(float(nx_h[j_].max() / max(1.0, float(nx_h[j_].sum()))), 4)

                    ra_["loss"]["near"] = round(n_(0, 0, 6) + n_(1, 1, 6), 4)
                    ra_["parts"].update(near_now=n_(0, 0), near_later=n_(1, 1))
                    ra_["near_right"], ra_["near_unseen_right"] = [n_(2, 0), n_(3, 1)], [n_(4, 2), n_(5, 3)]
                    ra_["zero"].update(near_right=[nz_(0), nz_(1)], near_unseen_right=[nz_(2), nz_(3)])
                    ra_["near_share"] = [round(float(x_), 4) for x_ in (nx_h[0] / max(1.0, float(nx_h[0].sum()))).tolist()]    # how often each landmark is the nearest now
                    ra_["near_frames"] = AUX_NW
                    ra_["labelled"].update({k_: round(float(nx_n[j_] / ax_w), 4) for j_, k_ in enumerate(("near_now", "near_later", "near_now_unseen", "near_later_unseen"))})
                ra_["guess_s"] = round(guess_secs, 2)                    # the seconds the new labels took (label_s: the four's)
        if AUX_W > 0 and ax_w > 0 and (AUX2 or AUX_MEAS):               # (v0.2.2) the revised guessing game
            v2_ = dict(tail=bool(AUX_TAIL), tail_frames=AUX_TWN, fresh=AUX_FRESH, unseen=bool(AUX_UNSEEN))
            v2_.update(AX2_ST)
            if AUX_MEAS:
                v2_["memory_vs_belief"] = {k_: dict(share=round(float(mb_s[i_, 0]) / max(1.0, float(mb_s[:, 0].sum())), 4),
                                                    memory=round(float(mb_s[i_, 1]) / max(1.0, float(mb_s[i_, 0])), 1),
                                                    belief=round(float(mb_s[i_, 2]) / max(1.0, float(mb_s[i_, 0])), 1),
                                                    memory_nearer=round(float(mb_s[i_, 3]) / max(1.0, float(mb_s[i_, 0])), 4))
                                           for i_, k_ in enumerate(("none", "0-2s", "2-7.5s", "7.5-20s"))}
                v2_["memory_vs_belief"]["all"] = dict(memory=round(float(mb_s[:, 1].sum()) / max(1.0, float(mb_s[:, 0].sum())), 1),
                                                      belief=round(float(mb_s[:, 2].sum()) / max(1.0, float(mb_s[:, 0].sum())), 1),
                                                      memory_nearer=round(float(mb_s[:, 3].sum()) / max(1.0, float(mb_s[:, 0].sum())), 4))
            rec["aux"]["v022"] = v2_
        if RJ_LAB:                                                       # (--rj-teach) the lesson, its frames, his agreement; the runs' counts
            tr_n_, ov_n_ = float(np.sum(agg.get("rj_tries", 0))), float(np.sum(agg.get("rj_over", 0)))
            RJ_WIN.append([tr_n_, ov_n_])
            while len(RJ_WIN) > 1 and sum(x_[0] for x_ in RJ_WIN[1:]) >= a.rj_teach_window:
                RJ_WIN.pop(0)
            ra_ = rj_acc.cpu().numpy()
            rn_ = np.zeros(7)
            if np.size(agg.get("rj_near", 0)) == 7:
                rn_ = np.asarray(agg["rj_near"], np.float64)
            rec["rj_teach"] = dict(
                w=round(float(rj_w), 5), live=RJ_LIVE[0], fade=round(float(rj_fade), 3), trunk=a.rj_teach_trunk,
                start=None if RJ_T0[0] is None else round(RJ_T0[0], 2), warm=a.rj_teach_warm,
                labelled=int(ra_[0]),                                                                       # the learner's labelled frames (first pass)
                jump=dict(read=int(ra_[1]), p=round(float(ra_[2] / max(1.0, ra_[1])), 4), chose=round(float(ra_[3] / max(1.0, ra_[1])), 4),
                          loss=round(float(ra_[4] / max(1.0, ra_[1])), 4)),                                   # his chance of the jump there, his choices
                fire=dict(read=int(ra_[5]), p=round(float(ra_[6] / max(1.0, ra_[5])), 4), chose=round(float(ra_[7] / max(1.0, ra_[5])), 4),
                          loss=round(float(ra_[8] / max(1.0, ra_[5])), 4)),
                both=round(float(ra_[9] / max(1.0, ra_[10])), 4),                                            # jump and fire both, where both were read
                tries=int(tr_n_), over=round(ov_n_ / max(1.0, tr_n_), 3), shots=int(agg.get("rj_shots", 0)),
                near=dict(zip(("frames", "floor_edge", "floor_reach", "ready", "labelled"), (int(x_) for x_ in rn_[:5]))),   # (the simulators: his
                pitch_reach=round(float(rn_[5] / max(1.0, rn_[2])), 1), pitch_edge=round(float(rn_[6] / max(1.0, rn_[1])), 1),   # frames in the
                #                                                          tries; on the floor within 120 u of the take-off, within the label's
                #                                                          reach, the launcher ready there, labelled; his mean view pitch there)
                window=[float(sum(x_[0] for x_ in RJ_WIN)), float(sum(x_[1] for x_ in RJ_WIN))])
        if RJC_LAB:                                                      # (--rj-copy) the lesson, its frames, his agreement per output; the tries
            ca_ = rjc_acc.cpu().numpy()
            rs_ = np.zeros(6)
            if np.size(agg.get("rj_copy", 0)) == 6:
                rs_ = np.asarray(agg["rj_copy"], np.float64)
            tr_n_, ov_n_ = float(np.sum(agg.get("rj_tries", 0))), float(np.sum(agg.get("rj_over", 0)))
            rec["rj_copy"] = dict(
                w=round(float(rjc_w), 5), live=RJC_LIVE[0], trunk=a.rj_copy_trunk, warm=a.rj_copy_warm,
                start=None if RJC_T0[0] is None else round(RJC_T0[0], 2),
                labelled=int(ca_[RJC_H, 0]),                                                             # the learner's labelled frames (first pass)
                agree_all=round(float(ca_[RJC_H, 2] / max(1.0, ca_[RJC_H, 1])), 4),                     # ... where his hand read the keys: every output as labelled
                heads={nm_: dict(n=int(ca_[j_, 0]), p=round(float(ca_[j_, 1] / max(1.0, ca_[j_, 0])), 4),    # per output: its frames, his chance of the
                                 chose=round(float(ca_[j_, 2] / max(1.0, ca_[j_, 0])), 4),                  # label, his choice was the label, the loss
                                 loss=round(float(ca_[j_, 3] / max(1.0, ca_[j_, 0])), 4)) for j_, nm_ in enumerate(RJC_NAMES)},
                sim_labelled=int(rs_[0]), tries=int(tr_n_), over=round(ov_n_ / max(1.0, tr_n_), 3),           # (the simulators, his counted seats)
                ended=int(rs_[1]), arrived=round(float(rs_[2] / max(1.0, rs_[1])), 3), died=round(float(rs_[3] / max(1.0, rs_[1])), 3),
                lost_per_try=round(float(rs_[4] / max(1.0, rs_[1])), 1), lost_big=round(float(rs_[5] / max(1.0, rs_[1])), 3))
            ro_ = agg.get("route_copy")                                   # (ROUTE_COPY) per route: labelled frames, tries ended, over, at the armor, short
            if ro_ is not None and np.ndim(ro_) == 2:
                ro_ = np.asarray(ro_, np.float64)
                nm_ = [x_ for x_ in (("circle", "hop2") if ro_.shape[0] == 2 else (os.environ.get("ROUTE_COPY", ":?").split(":")[-1],))]
                rec["rj_copy"]["routes"] = {nm_[r_]: dict(labelled=int(ro_[r_, 0]), ended=int(ro_[r_, 1]),
                                                         over=round(float(ro_[r_, 2] / max(1.0, ro_[r_, 1])), 3),
                                                         arrived=round(float(ro_[r_, 3] / max(1.0, ro_[r_, 1])), 3),
                                                         short=round(float(ro_[r_, 4] / max(1.0, ro_[r_, 1])), 3)) for r_ in range(ro_.shape[0])}
        if "qhand" in agg:                                               # (--hand-teach) the weapon in his hand with nobody in view for 1 s or more:
            QH_ = np.asarray(agg["qhand"], np.float64).reshape(3, 4, -1)      # the simulators' counters (his counted seats, in games), also with the lesson off
            QM_, QS_ = np.asarray(agg["qhand_meet"], np.float64), np.asarray(agg["qhand_sw"], np.float64)
            QO_, QP_ = (np.asarray(agg[k_], np.float64).reshape(2, 4, -1) for k_ in ("qhand_on", "qhand_pro"))
            ha_ = hd_acc.cpu().numpy()
            WI_ = {w_: i_ for i_, w_ in enumerate(WEAPONS)}

            def sh_(x_, ws_=None, d_=4):                                 # the share of the frames x_ (by weapon) with one of ws_ in hand; None: no frames
                return (round(float(sum(x_[WI_[w_]] for w_ in ws_) / x_.sum()), d_) if ws_ else
                        {w_: round(float(x_[i_] / x_.sum()), d_) for w_, i_ in WI_.items() if x_[i_] > 0}) if x_.sum() > 0 else None

            def tv_(a_, b_):                                             # half the sum of the differences of two rows of shares (0: the same)
                return round(float(0.5 * np.abs(a_ / a_.sum() - b_ / b_.sum()).sum()), 4) if a_.sum() > 0 and b_.sum() > 0 else None
            rec["hand_teach"] = dict(
                w=round(hd_w, 4), trunk=a.hand_teach_trunk, on=HAND_LAB,
                redraw_s=float(getattr(E_, "HAND_TEACH_REDRAW", 0.0)),
                loss=round(float(ha_[3] / max(1.0, ha_[2])), 4) if HAND_LAB else None,                    # cross-entropy against the target, a labelled reading
                kl=round(float((ha_[3] - ha_[4]) / max(1.0, ha_[2])), 4) if HAND_LAB else None,            # ... less the target's own entropy: 0 = he chooses as the target
                labelled=round(float(ha_[1] / max(1.0, ha_[0])), 4) if HAND_LAB else None,                 # the share of the learner's frames with a label,
                read=round(float(ha_[2] / max(1.0, ha_[0])), 4) if HAND_LAB else None,                     # ... and with a label his hand reads (the lesson's frames)
                p_change=[round(float(ha_[5] / max(1.0, ha_[2])), 4), round(float(ha_[6] / max(1.0, ha_[2])), 4)] if HAND_LAB else None,   # a choice other than "keep" at such a reading: his chance, the target's
                # THE MEASURES (the simulators' count; bands: an enemy in view under 5 s ago, 5 to 15 s, over 15 s, nobody seen yet in this round)
                unseen_min=round(float(QH_.sum() * DT_MIN), 2),                                            # player-minutes with nobody in view for 1 s or more
                time=dict(travelling=round(float(QH_[0].sum() / max(1.0, QH_.sum())), 4), holding=round(float(QH_[1].sum() / max(1.0, QH_.sum())), 4),
                          neither=round(float(QH_[2].sum() / max(1.0, QH_.sum())), 4)),                    # of that time: at 200 or more and not in a hold; in a hold; neither
                humming=[sh_(QH_[:, b_].sum(0), ("rg", "lg")) for b_ in range(4)],                       # rail or lightning in hand, by band: all of that time
                humming_travelling=[sh_(QH_[0, b_], ("rg", "lg")) for b_ in range(4)],                   # ... travelling alone (the pros: 0.28, 0.12, 0.09)
                rockets=dict(travelling=sh_(QH_[0].sum(0), ("rl",)), holding=sh_(QH_[1].sum(0), ("rl",)), neither=sh_(QH_[2].sum(0), ("rl",))),   # rockets in hand (the pros holding: 0.82)
                in_hand=sh_(QH_.sum((0, 1))),                                                              # every weapon's share of that time
                meet=sh_(QM_), meets=int(QM_.sum()),                                                       # the weapon in his hand as an enemy comes into view after 1 s or more out of it
                changes_a_minute=round(float(QS_[0] / max(1e-9, QS_[1] * DT_MIN)), 2),                    # changes of the weapon in his hand a minute of that time
                on_label=dict(frames=int(QO_.sum()),                                                       # the frames the lesson would label (he owns two or more of the row's weapons):
                              share=round(float(QO_.sum() / max(1.0, QH_.sum())), 4),                      # ... their share of the time with nobody in view,
                              his=dict(travelling=sh_(QO_[0].sum(0)), holding=sh_(QO_[1].sum(0))),         # ... his hand on them,
                              pros=dict(travelling=sh_(QP_[0].sum(0)), holding=sh_(QP_[1].sum(0))),        # ... the pros' shares of what he owned there,
                              gap=dict(travelling=tv_(QO_[0].sum(0), QP_[0].sum(0)), holding=tv_(QO_[1].sum(0), QP_[1].sum(0)))))    # ... and how far apart (0 to 1)
        if "hop_pay" in agg:                                             # (HOP_PAY) speed gained from hop to hop: what it paid, how often
            pm_ = max(1e-9, NP * T * DT_MIN)
            rec["hop"] = dict(pay_per_player_min=round(float(agg["hop_pay"] / pm_), 4), paying_per_min=round(float(agg.get("hop_n", 0) / pm_), 2),
                              takeoffs_per_min=round(float(agg.get("hop_takeoffs", 0) / pm_), 2), chains_per_min=round(float(agg.get("hop_chains", 0) / pm_), 2))
        if "rg_far" in agg:                                              # (RG_FAR_PRICE) the far rail's fixed price
            rf_ = np.atleast_1d(agg["rg_far"]).astype(np.float64)
            pm_ = max(1e-9, NP * T * DT_MIN)
            rec["rg_far"] = dict(price=float(getattr(E_, "RG_FAR_PRICE", 0.0)), dist=float(getattr(E_, "RG_FAR_DIST", 0.0)),
                                 rail_shots_per_player_min=round(float(rf_[0] / pm_), 3), far_share=round(float(rf_[1] / max(1.0, rf_[0])), 3),
                                 far_price_mean=round(float(rf_[2] / max(1.0, rf_[1])), 4),          # what a far shot cost
                                 base_price_mean=round(float(rf_[3] / max(1.0, rf_[1])), 4))         # ... and what SHOT_COST would have asked
        if "big_seq" in agg:                                             # (BIG_PICK_SEQ) the big three by order a life: pickups and pay a player-minute
            bs_ = np.atleast_1d(agg["big_seq"]).astype(np.float64)
            pm_ = max(1e-9, NP * T * DT_MIN)
            rec["big_seq"] = dict(sizes=list(getattr(E_, "BIG_PICK_SEQ", ())),
                                  pickups_per_player_min=[round(float(x_ / pm_), 4) for x_ in bs_[:3]],     # first, second, third
                                  pay_per_player_min=round(float(bs_[3:].sum() / pm_), 4),
                                  pay_by_order_per_player_min=[round(float(x_ / pm_), 4) for x_ in bs_[3:]])
        if "hop_chain" in agg:                                           # (HOP_CHAIN) chains of hops: how many, how long, what they paid
            hc_ = np.atleast_1d(agg["hop_chain"]).astype(np.float64)
            C_ = {k_: i_ for i_, k_ in enumerate(E_.HC_COLS)}
            hh_ = hc_[len(E_.HC_COLS):]                                  # ended chains by length 1 .. HC_BINS (and over)
            ln_ = np.arange(1, len(hh_) + 1)
            n2_ = hh_[1:].sum()                                          # (a chain: two hops or more)
            cs_ = np.cumsum(hh_[1:]) / max(1.0, n2_)
            ch_ = max(1.0, hc_[C_["gained"]] + hc_[C_["kept"]] + hc_[C_["lost"]])
            pm_ = max(1e-9, NP * T * DT_MIN)
            rec["hop_chain"] = dict(chains_per_min=round(float(n2_ / pm_), 3), mean_len=round(float((hh_[1:] * ln_[1:]).sum() / max(1.0, n2_)), 2),
                                    p95_len=int(ln_[1:][min(len(cs_) - 1, int(np.searchsorted(cs_, 0.95)))]) if n2_ > 0 else 0,
                                    pay_per_player_min=round(float(hc_[C_["pay"]] / pm_), 4), paid_per_min=round(float(hc_[C_["paid"]] / pm_), 2),
                                    takeoffs_per_min=round(float(hc_[C_["takeoffs"]] / pm_), 2),
                                    gained=round(float(hc_[C_["gained"]] / ch_), 3), kept=round(float(hc_[C_["kept"]] / ch_), 3),
                                    lost=round(float(hc_[C_["lost"]] / ch_), 3), unpaid=round(float(hc_[C_["kept_unpaid"]] / max(1.0, hc_[C_["gained"]] + hc_[C_["kept"]])), 3),
                                    in_view=dict(takeoffs_per_min=round(float(hc_[C_["takeoffs_view"]] / max(1e-9, hc_[C_["frames_view"]] * DT_MIN)), 2),   # (the owner, 2026-10-19:
                                                 unseen_takeoffs_per_min=round(float(hc_[C_["takeoffs"]] / max(1e-9, (hc_[C_["frames"]] - hc_[C_["frames_view"]]) * DT_MIN)), 2),   # no jumping in fights)
                                                 share_of_time=round(float(hc_[C_["frames_view"]] / max(1.0, hc_[C_["frames"]])), 3),
                                                 chains_ended=int(hc_[C_["ended_view"]])))
        if "jump_every" in agg:                                          # (JUMP_EVERY) the thumb between the hand's readings and on them
            je_ = np.atleast_1d(agg["jump_every"]).astype(np.float64)
            pm_ = max(1e-9, NP * T * DT_MIN)
            rec["jump_every"] = dict(presses_per_min=round(float((je_[1] + je_[2]) / pm_), 2),
                                     presses_between=round(float(je_[1] / max(1.0, je_[1] + je_[2])), 3),
                                     releases_between=round(float(je_[3] / max(1.0, je_[3] + je_[4])), 3))
        if "games" in agg:                                               # (GAME_P, LATE_P, WIN_PAY) the whole games and late rounds that ended in this rollout
            g_ = np.atleast_1d(agg["games"]).astype(np.float64)        # (the simulator's GAMES_COLS)
            n_, l_ = max(1.0, g_[0] + g_[1]), max(1.0, g_[4])
            rec["games"] = dict(whole=int(g_[0]), late=int(g_[1]), begun=int(g_[15]), level_at_the_limit=int(g_[2]),
                                frags_a_whole_game=round(float(g_[3] / max(1.0, g_[0])), 1),
                                time_share=dict(whole=round(float(g_[13] / max(1.0, T * n_groups)), 4),             # of all the groups' time
                                                late=round(float(g_[14] / max(1.0, T * n_groups)), 4)),
                                league=dict(games=int(g_[4]), won=int(g_[5]), drawn=int(g_[6]), lost=int(g_[7]),     # his seat against the league's, in the
                                            frag_diff=round(float(g_[8] / l_), 2),                                 # league half of the matches (the league's
                                            win_pay_a_game=round(float(g_[9] / l_), 3),                            # network changes with every rollout)
                                            flat_pay_a_game=round(float(g_[10] / l_), 3),
                                            opponent_now="anchor" if (R_SN and R_VA) else "snapshot" if R_SN else "himself"),
                                pay_size=dict(win=round(float(g_[11] / n_), 3), flat=round(float(g_[12] / n_), 3)),  # the first seat's pay a game, without its sign
                                by_map={m_: [int(x_) for x_ in np.atleast_1d(v_["games"])[[0, 1, 4, 5, 6, 7]]]       # whole, late; league: games, won, level, lost
                                        for m_, v_ in agg_map.items() if "games" in v_ and float(np.atleast_1d(v_["games"])[[0, 1]].sum()) > 0})
        if "pay_terms" in agg and hasattr(E_, "PAY_TERMS"):              # (PAY_SPLIT, record only) his pay by term, his counted seats: a
            PT_ = np.asarray(agg["pay_terms"], np.float64).reshape(3, -1)  # player-minute's worth in every round and in whole games, and the
            pmh_ = max(1e-9, 0.5 * NP * T * DT_MIN)                      # share of the pay's size (|x| summed) by term
            sz_ = max(1e-12, float(PT_[2].sum()))
            rec["pay_terms"] = dict(per_player_min={k_: round(float(PT_[0, i_] / pmh_), 4) for i_, k_ in enumerate(E_.PAY_TERMS) if PT_[2, i_] > 0},
                                    games={k_: round(float(PT_[1, i_] / pmh_), 4) for i_, k_ in enumerate(E_.PAY_TERMS) if PT_[1, i_] != 0},
                                    size_share={k_: round(float(PT_[2, i_] / sz_), 4) for i_, k_ in enumerate(E_.PAY_TERMS) if PT_[2, i_] > 0},
                                    total_per_player_min=round(float(PT_[0].sum() / pmh_), 4))
        if "win_shadow" in agg:                                          # (WIN_SHADOW, record only) what WIN_PAY would have paid him in
            WS_ = np.atleast_1d(agg["win_shadow"]).astype(np.float64)    # whole games beside the flat frag pay it would take out (WS_COLS)
            wm_ = max(1e-9, float(WS_[4]) * DT_MIN)
            rec["win_shadow"] = dict(minutes=round(float(WS_[4]) * DT_MIN, 1), win_per_player_min=round(float(WS_[0] / wm_), 4),
                                     win_size_per_player_min=round(float(WS_[1] / wm_), 4), flat_per_player_min=round(float(WS_[2] / wm_), 4),
                                     flat_size_per_player_min=round(float(WS_[3] / wm_), 4),
                                     size_ratio_win_to_flat=round(float(WS_[1] / max(1e-9, WS_[3])), 4))
        if "win_blend" in agg:                                           # (v0.5.1, WIN_W / FADE_V) the blend's sizes a player-minute in games
            WB_ = np.atleast_1d(agg["win_blend"]).astype(np.float64)     # (the simulator's WB_COLS): for sizing WIN_GAIN, the win part at
            bm_ = max(1e-9, float(WB_[0]) * DT_MIN)                      # G = 1 against the combat pay it replaces
            rec["win_blend"] = dict(minutes=round(float(WB_[0]) * DT_MIN, 1), win_g1_per_player_min=round(float(WB_[1] / bm_), 4),
                                    win_g1_size=round(float(WB_[2] / bm_), 4), combat_per_player_min=round(float(WB_[3] / bm_), 4),
                                    combat_size=round(float(WB_[4] / bm_), 4), other_size=round(float(WB_[5] / bm_), 4),
                                    paid_size=round(float(WB_[6] / bm_), 4), blend_frames=int(WB_[7]),
                                    combat_to_win_g1=round(float(WB_[4] / max(1e-9, WB_[2])), 3))
        if "open" in agg:                                                # (OPENINGS) the pros' spawn openings as the item rule's label, his seats
            def open_(o_):                                               # (the simulator's OPEN_COLS)
                o_ = np.atleast_1d(o_).astype(np.float64)
                at_ = max(1.0, o_[1] + o_[2])
                return dict(lives=int(o_[0]),                                                        # his lives begun in games
                            with_opening=round(float((o_[1] + o_[2]) / max(1.0, o_[0])), 4),         # ... the share at a spawn point (an opening's label),
                            general_rule=round(float(o_[2] / at_), 4),                               # of them by the general rule (too little data),
                            avoid_changed=round(float(o_[3] / at_), 4),                              # with the second pickup changed by the believed enemy,
                            avoid_left_none=round(float(o_[4] / at_), 4),                            # ... to nothing (the normal rule spoke)
                            label_readings=int(o_[5]),                                               # readings of his intention with an opening's label
                            agree=round(float(o_[6] / max(1.0, o_[5])), 4),                          # ... his choice was the label
                            first_taken=round(float(o_[7] / at_), 4),                                # lives that took the first pickup named in the window,
                            second_taken=round(float(o_[8] / at_), 4),                               # ... and a second one of the opening
                            first_big_s=round(float(o_[9] / max(1.0, o_[10])), 2),                   # seconds to the first big pickup of a life
                            lives_with_a_big_pickup=round(float(o_[10] / max(1.0, o_[0])), 4))
            rec["openings"] = dict(open_(agg["open"]), by_map={m_: open_(v_["open"]) for m_, v_ in agg_map.items() if "open" in v_})
        if "moments" in agg:                                             # (MID_START_P, SPAWN_START_P) rounds begun from saved moments of whole games
            mo_ = np.atleast_1d(agg["moments"]).astype(np.float64)       # (the simulator's MOMENT_COLS)
            rec["moments"] = dict(mid_begun=int(mo_[0]), spawn_begun=int(mo_[1]), mid_ended=int(mo_[2]), spawn_ended=int(mo_[3]),
                                  no_moment_yet=int(mo_[4]),                                           # asked for with none saved: a whole game or a drill instead
                                  time_share=dict(mid=round(float(mo_[5] / max(1.0, T * n_groups)), 4),  # of all the groups' time
                                                  spawn=round(float(mo_[6] / max(1.0, T * n_groups)), 4)),
                                  saved=dict(spawn=int(mo_[7]), mid=int(mo_[8])),
                                  respawns=int(mo_[9]), with_a_believed_enemy=round(float(mo_[10] / max(1.0, mo_[9])), 4),
                                  league_mid=dict(games=int(mo_[11]), won=int(mo_[12]), drawn=int(mo_[13]), lost=int(mo_[14])),
                                  by_map={k_: [int(x_) for x_ in np.atleast_1d(v_["moments"])[[0, 1, 4, 7, 8]]]     # mid begun, spawn begun, none saved, saved spawn, saved mid
                                          for k_, v_ in agg_map.items() if "moments" in v_})
        if "rail_start" in agg:                                          # (RAIL_START_P) rail range starts: both at long range, the rail in hand
            rs_ = np.atleast_1d(agg["rail_start"]).astype(np.float64)    # (the simulator's RAIL_START_COLS)
            bd_ = ("near", "mid", "far")

            def rs_rec(x_):
                return dict(begun=int(x_[0]), ended=int(x_[2]), no_moment_yet=int(x_[1]),
                            time_share=round(float(x_[3] / max(1.0, T * n_groups)), 4),                    # of all the groups' time
                            early_share=round(float(x_[4] / max(1.0, T * n_groups)), 4),                   # ... in a start's first 10 s
                            shots={b_: int(x_[5 + k_]) for k_, b_ in enumerate(bd_)}, hits={b_: int(x_[8 + k_]) for k_, b_ in enumerate(bd_)},
                            frags={b_: int(x_[11 + k_]) for k_, b_ in enumerate(bd_)},
                            hit_rate={b_: round(float(x_[8 + k_] / max(1.0, x_[5 + k_])), 3) for k_, b_ in enumerate(bd_)},
                            first_shot_10s=round(float(x_[15] / max(1.0, x_[14])), 3),                     # counted seats with a rail shot within 10 s,
                            first_shot_s=round(float(x_[16] / max(1.0, x_[15])), 2),                       # ... and the seconds to it
                            start_distance=int(x_[18] / max(1.0, x_[0])), other_pair=int(x_[17]),
                            league=dict(games=int(x_[19]), won=int(x_[20]), drawn=int(x_[21]), lost=int(x_[22])))
            rec["rail_start"] = dict(rs_rec(rs_), p=float(getattr(E_, "RAIL_START_P", 0.0)), secs=float(getattr(E_, "RAIL_START_LEN", 0.0)),
                                     by_map={k_: rs_rec(np.atleast_1d(v_["rail_start"]).astype(np.float64))
                                             for k_, v_ in agg_map.items() if "rail_start" in v_})
        if "pro_start" in agg:                                           # (PRO_START_P) pro starts: rounds begun at moments of the pros' duels
            ps_ = np.atleast_1d(agg["pro_start"]).astype(np.float64)     # (the simulator's PRO_START_COLS)

            def ps_rec(x_):
                return dict(begun=int(x_[0]), ended=int(x_[1]),
                            time_share=round(float(x_[2] / max(1.0, T * n_groups)), 4),                    # of all the groups' time
                            early_share=round(float(x_[3] / max(1.0, T * n_groups)), 4),                   # ... in a start's first 10 s
                            frags=int(x_[8]), frags_counted=int(x_[9]), big_pickups=int(x_[10]), big_pickups_counted=int(x_[11]),
                            pickups=int(x_[12]), start_lead=round(float(x_[13] / max(1.0, x_[0])), 2),
                            start_clock=round(float(x_[16] / max(1.0, x_[0])), 1),
                            counted_seats=int(x_[14]), worked_out_stack=round(float(x_[15] / max(1.0, x_[14])), 3),
                            frag_share_counted=round(float(x_[17] / max(1.0, x_[18])), 3),
                            league=dict(games=int(x_[4]), won=int(x_[5]), drawn=int(x_[6]), lost=int(x_[7])))
            rec["pro_start"] = dict(ps_rec(ps_), p=float(getattr(E_, "PRO_START_P", 0.0)), secs=float(getattr(E_, "PRO_START_LEN", 0.0)),
                                    by_map={k_: ps_rec(np.atleast_1d(v_["pro_start"]).astype(np.float64))
                                            for k_, v_ in agg_map.items() if "pro_start" in v_})
        if "gen_start" in agg:                                           # (GEN_START_SHARE) the generated starts
            gs_ = np.atleast_1d(agg["gen_start"]).astype(np.float64)
            rec["gen_start"] = dict(begun=int(gs_[0]), near=int(gs_[1]), owned_per_seat=round(float(gs_[2] / max(1.0, 2 * gs_[0])), 3),
                                    big_in_hand=round(float(gs_[3] / max(1.0, 2 * gs_[0])), 3), bias_reads=int(gs_[4]),
                                    share=float(getattr(E_, "GEN_START_SHARE", 0.0)))
        if "people_start" in agg:                                        # (PEOPLE_START_SHARE, MOMENT_WEIGHTED) the pro starts from people's games
            pp_ = np.atleast_1d(agg["people_start"]).astype(np.float64)   # (the simulator's PEOPLE_START_COLS)
            rec["people_start"] = dict(begun=int(pp_[0]), counted_seats=int(pp_[1]), as_the_person=int(pp_[2]), weighted_draws=int(pp_[3]),
                                       share=float(getattr(E_, "PEOPLE_START_SHARE", 0.0)), weighted=int(getattr(E_, "MOMENT_WEIGHTED", 0)))
        if "run_item" in agg:                                            # (RUN_TARGET_W) item runs to the map's weighted targets
            ri_ = np.atleast_1d(agg["run_item"]).astype(np.float64)
            rec["run_item"] = dict(begun=int(ri_[0]), weighted=int(getattr(E_, "RUN_TARGET_W", 0)),
                                   targets={E_.INTENTS[j_]: int(ri_[1 + j_]) for j_ in range(len(E_.INTENTS)) if ri_[1 + j_] > 0},
                                   by_map={k_: int(np.atleast_1d(v_["run_item"])[0]) for k_, v_ in agg_map.items() if "run_item" in v_})
        if True:                                                         # (--item-floor) per map: the big items' mean p, those under the floor
            ia_, ic_ = IF_ACC.cpu().numpy(), IF_CNT.cpu().numpy()
            by_ = {}
            un_ = {}
            for j_, m_ in enumerate(IF_MAPS):
                if ic_[j_] <= 0:
                    continue
                mp_ = {E_.INTENTS[k_]: round(float(ia_[j_, k_] / ic_[j_]), 4) for k_ in np.nonzero(IF_OK[j_])[0]}
                by_[m_] = mp_
                lo_ = {k_: v_ for k_, v_ in mp_.items() if v_ < IF_LIVE[1]}
                if lo_:
                    un_[m_] = lo_
            ls_ = IF_LS.cpu().numpy()
            rec["item_floor"] = dict(w=IF_LIVE[0], floor=IF_LIVE[1], under=un_, by_map=by_, term=round(float(ls_[0]), 5),
                                     grad_floor=round(float(ls_[1]), 6), grad_bonus=round(float(ls_[2]), 6), grad_pg=round(float(ls_[3]), 6))
        if "overtime" in agg:                                            # (OVERTIME) games level at the limit played on, 120 s a period
            ot_ = np.atleast_1d(agg["overtime"]).astype(np.float64)      # (the simulator's OT_COLS)
            rec["overtime"] = dict(games=int(ot_[0]), periods=int(ot_[1]), ended_with_a_lead=int(ot_[2]), level_at_the_cap=int(ot_[3]),
                                   time_share=round(float(ot_[4] / max(1.0, T * n_groups)), 4),          # of all the groups' time
                                   league=dict(games=int(ot_[5]), won=int(ot_[6]), drawn=int(ot_[7]), lost=int(ot_[8])),
                                   by_map={k_: [int(x_) for x_ in np.atleast_1d(v_["overtime"])[[0, 1, 3]]]     # to overtime, periods, level at the cap
                                           for k_, v_ in agg_map.items() if "overtime" in v_})
        if W_HEAD >= 0:                                                  # (WAYS) his ways to his targets
            wa_ = wy_acc.cpu().numpy()
            WR_, WD_, WF_ = (np.atleast_1d(agg.get(k_, np.zeros(z_))).astype(np.float64) for k_, z_ in (("way_reads", 3), ("way_done", 3), ("way_frames", 4)))
            wm_ = way_measure(WAY_STORE, WAY_KEEP, WAY_MIN)
            rec["ways"] = dict(on=W_ON,
                               reads=[round(float(x_), 4) for x_ in wa_[5:8] / max(1.0, wa_[0])],        # the learner's readings of his way: the share on the shortest, the second, the third (what he drew),
                               p=[round(float(x_), 4) for x_ in wa_[2:5] / max(1.0, wa_[0])],            # ... the chance his network gave each,
                               entropy=round(float(wa_[1] / max(1.0, wa_[0])), 4),                       # ... its entropy (all alike: 1.0986),
                               read_frames=round(float(wa_[0] / max(1.0, float(b_w.sum()))), 5),         # ... the share of his frames it was read on
                               reads_sim=[round(float(x_), 4) for x_ in WR_ / max(1.0, WR_.sum())],      # the same by the simulators' count (his seats, every reading)
                               trips=[round(float(x_), 4) for x_ in WD_ / max(1.0, WD_.sum())],          # his finished trips (an item taken, a place reached) by the way he was on
                               time=[round(float(x_), 4) for x_ in WF_[:3] / max(1.0, WF_[:3].sum())],   # his time in games with a target and a way to it, by way
                               differs=round(float(WF_[3] / max(1.0, WF_[1] + WF_[2])), 4),              # of his time on the second or third: where it differs from the shortest from there
                               changes_per_player_min=round(float(agg.get("way_changes", 0)) / max(1e-9, NP * T * DT_MIN), 3),   # changes of the way alone
                               pay_per_player_min=[round(float(x_) / max(1e-9, NP * T * DT_MIN), 4)                    # what the ways of his trips paid, and what
                                                   for x_ in np.atleast_1d(agg.get("way_pay", np.zeros(2)))],          # trips given up gave back
                               commonest=round(float(np.mean([v_["commonest"] for v_ in wm_.values()])), 1) if wm_ else None,   # THE MEASURE: of his trips between the same
                               by_map={m_: v_["commonest"] for m_, v_ in wm_.items()},                   # two places, the share on the commonest way, per cent (the pros 43, v0.1 57);
                               pairs=sum(v_["pairs"] for v_ in wm_.values()),                            # by map; the pairs and trips it is counted over
                               counted=sum(v_["trips"] for v_ in wm_.values()),                          # (the newest WAY_KEEP of a pair with WAY_MIN or more);
                               trips_per_player_min=round(float(agg.get("way_trips_n", 0)) / max(1e-9, NP * T * DT_MIN), 3))     # the trips between two places that came in
        if LEGS_LAB:                                                     # (--legs-teach) the lesson of his legs, measured in the update's first pass
            la_, lf_ = lt_acc.cpu().numpy(), lt_fr.cpu().numpy()
            KP_ = np.asarray(agg.get("legs_keep", np.zeros((2, 7))), np.float64).reshape(2, 7)   # (the simulator's counters: carried, withheld)

            def kp_(r_):
                k_ = KP_[r_]
                return dict(stretches=int(k_[0]),                                       # stretches begun (his switch turned on), his seats only
                            frames=int(k_[1]),                                          # frames with a label,
                            fast=round(float(k_[2] / max(1.0, k_[1])), 4),              # ... the share of them at 400 units a second or more,
                            speed=int(k_[3] / max(1.0, k_[1])),                         # ... his mean speed on them,
                            runs=int(k_[4]), runs_2s=int(k_[5]),                        # runs of such frames begun, runs that lasted two seconds,
                            gain_2s=round(float(k_[6] / max(1.0, k_[5])), 1))           # ... the mean speed gained in their first two seconds
            rec["legs_teach"] = dict(w=round(lt_w, 4), trunk=a.legs_teach_trunk,
                                     loss=round(float((la_[:, 1] / np.maximum(1.0, la_[:, 0])).sum()), 4),                 # the four outputs' losses added,
                                     loss_by=[round(float(x_), 4) for x_ in la_[:, 1] / np.maximum(1.0, la_[:, 0])],       # ... and apart: forward, sideways, jump, turn
                                     labelled=round(float(lf_[1] / max(1.0, lf_[0])), 4),                                  # the share of the learner's frames with a label
                                     agree=[round(float(x_), 4) for x_ in la_[:, 2] / np.maximum(1.0, la_[:, 0])],         # his likeliest choice is the label's, by output
                                     p_label=[round(float(x_), 4) for x_ in la_[:, 3] / np.maximum(1.0, la_[:, 0])],       # the chance he gives the label, by output
                                     withheld=round(float(lf_[2] / max(1.0, lf_[1])), 4),                                  # the share of the labelled frames in withheld stretches
                                     agree_withheld=[round(float(x_), 4) for x_ in la_[:, 5] / np.maximum(1.0, la_[:, 4])] if lf_[2] > 0 else None,
                                     carried=kp_(0), held=kp_(1))
        if LEGS_LEARN:                                                   # (--legs-learn) the branch: its share of his frames, its step, how far
            with torch.no_grad():                                        # it has moved in this process (largest, and the sum against its size)
                mv_ = [float((p_ - p0_).abs().max()) for p_, p0_ in zip(pol.legs.parameters(), LEGS_W0)]
                mr_ = float(sum(float((p_ - p0_).abs().sum()) for p_, p0_ in zip(pol.legs.parameters(), LEGS_W0))
                            / max(1e-12, sum(float(p0_.abs().sum()) for p0_ in LEGS_W0)))
            rec["legs_learn"] = dict(rate=a.legs_learn, lr=opt.param_groups[LEGS_GROUP]["lr"], lr_rest=opt.param_groups[0]["lr"], ent_w=a.legs_ent,
                                     share=round(float(ll_acc[1] / max(1.0, float(ll_acc[0]))), 4),
                                     kl=round(float(ll_acc[2] / max(1.0, float(ll_acc[3]))), 6),
                                     first_err=float(ll_acc[4]), entropy=round(float(ll_acc[5] / max(1.0, float(ll_acc[1]))), 4),
                                     grad=round(float(ll_acc[6] / max(1.0, float(ll_acc[7]))), 4),
                                     moved_max=round(max(mv_), 7), moved_rel=round(mr_, 8))
        if a.solo_self_drive or a.switch_fade:                           # (v0.3.4 C) his own speed in the runs, the switch in games, the fade
            SO_ = np.atleast_1d(agg.get("solo", np.zeros(2)))
            sp_ = float(SO_[1] / SO_[0]) if SO_[0] > 0 else None
            f0_ = FADE[0]
            if a.switch_fade and sp_ is not None and sp_ >= a.switch_fade_speed:
                FADE[0] = min(a.switch_fade_max, FADE[0] + a.switch_fade_step)
                pol.fade = FADE_V * FADE[0]
            rec["solo"] = dict(frames=int(SO_[0]), speed=round(sp_, 1) if sp_ is not None else None,
                               switch_games=round(float(np.atleast_1d(agg.get("legs", np.zeros(8)))[4] / max(1.0, float(np.atleast_1d(agg.get("legs", np.zeros(8)))[5]))), 4),
                               fade=round(f0_, 3), fade_next=round(FADE[0], 3))
        if "aw_bel" in agg and float(np.atleast_1d(agg["aw_bel"])[0]) > 0:   # (AWARE_LOG) the awareness counters, his seats in games
            B_, U_, V_, O_, S_ = (np.atleast_1d(agg[k_]) for k_ in ("aw_bel", "aw_tru", "aw_speed", "aw_off", "aw_snd"))
            ns_ = float(S_[:21].sum())
            cs_ = np.cumsum(S_[:21])
            med_ = (float(np.searchsorted(cs_, ns_ / 2.0)) + 0.5) * 0.1 if ns_ > 0 else None
            M_ = np.atleast_1d(agg.get("aw_emg", np.zeros(4)))
            rec["aware"] = dict(look_on_belief=round(float(B_[1] / max(1.0, B_[0])), 4), look_on_truth=round(float(U_[1] / max(1.0, U_[0])), 4),
                                look_on_emergence=dict(share=round(float(M_[1] / max(1.0, M_[0])), 4), frames=int(M_[0]), no_way=int(M_[2]),
                                                       at_belief=round(float(M_[3] / max(1.0, M_[0])), 3)),
                                sound_turn=dict(n=int(ns_), median_s=(round(med_, 2) if med_ is not None and med_ <= 2.0 else "never"),
                                                within_1s=round(float(S_[:10].sum() / max(1.0, ns_)), 4), never=round(float(S_[20] / max(1.0, ns_)), 4),
                                                already_facing=int(S_[21])),
                                speed=dict(in_view=int(V_[1] / max(1.0, V_[0])), unseen_near=int(V_[3] / max(1.0, V_[2])), unseen_far=int(V_[5] / max(1.0, V_[4]))),
                                share=dict(in_view=round(float(V_[0] / max(1.0, V_[0] + V_[2] + V_[4])), 3), unseen_near=round(float(V_[2] / max(1.0, V_[0] + V_[2] + V_[4])), 3)),
                                takeoffs_per_min=dict(in_view=round(float(O_[0] / max(1e-9, V_[0] * DT_MIN)), 1), unseen_near=round(float(O_[1] / max(1e-9, V_[2] * DT_MIN)), 1),
                                                      unseen_far=round(float(O_[2] / max(1e-9, V_[4] * DT_MIN)), 1)))
        if "rail" in agg and float(np.atleast_1d(agg["rail"])[0]) > 0:   # (RAIL_FAR_PAY) the rail by range to the enemy, his counted seats in games
            RR_ = np.atleast_1d(agg["rail"]).astype(np.float64)          # (the simulator's RAIL_COLS)
            lm_ = max(1e-9, float(RR_[0]) * DT_MIN)                      # his minutes alive in games (the counted seats)
            bd_ = ("near", "mid", "far")
            rec["rail"] = dict(pay=float(getattr(E_, "RAIL_FAR_PAY", 0.0)), band=[float(getattr(E_, "RAIL_FAR_LO", 600.0)), float(getattr(E_, "RAIL_FAR_HI", 900.0))],
                               minutes=round(float(RR_[0]) * DT_MIN, 1),
                               shots={b_: int(RR_[1 + k_]) for k_, b_ in enumerate(bd_)}, hits={b_: int(RR_[4 + k_]) for k_, b_ in enumerate(bd_)},
                               hit_rate={b_: round(float(RR_[4 + k_] / max(1.0, RR_[1 + k_])), 3) for k_, b_ in enumerate(bd_)},
                               shots_per_min=round(float(RR_[1:4].sum() / lm_), 3),
                               in_hand={b_: round(float(RR_[7 + k_] / max(1.0, RR_[0])), 4) for k_, b_ in enumerate(bd_)},        # share of his time: the rail in hand, the enemy at that range
                               in_hand_in_view={b_: round(float(RR_[10 + k_] / max(1.0, RR_[0])), 4) for k_, b_ in enumerate(bd_)},   # ... and in view
                               pay_got_per_min=round(float(RR_[13] / lm_), 4), pay_lost_per_min=round(float(RR_[14] / lm_), 4))
        if "preaim" in agg and "preaim_x" in agg:                        # (PREAIM_PAY) fresh sightings by the weapon in hand, his counted seats in games
            PA_ = np.asarray(agg["preaim"], np.float64).reshape(4, -1)   # (the simulator's stats["preaim"]: n, error summed, within 15 deg, q summed)
            PX_ = np.atleast_1d(agg["preaim_x"]).astype(np.float64)      # (PREAIM_X_COLS)
            wn_ = [(w_, k_) for k_, w_ in enumerate(E_.WEAPONS) if w_ != "hmg"]
            pa_ = lambda r_, k_=None: float(PA_[r_].sum() if k_ is None else PA_[r_, k_])
            rec["preaim"] = dict(pay=float(getattr(E_, "PREAIM_PAY", 0.0)), minutes=round(float(PX_[0]) * DT_MIN, 1),
                                 per_min=round(pa_(0) / max(1e-9, float(PX_[0]) * DT_MIN), 3),
                                 n=dict({w_: int(pa_(0, k_)) for w_, k_ in wn_}, all=int(pa_(0))),
                                 err_mean=dict({w_: round(pa_(1, k_) / max(1.0, pa_(0, k_)), 2) for w_, k_ in wn_}, all=round(pa_(1) / max(1.0, pa_(0)), 2)),
                                 within15=dict({w_: round(pa_(2, k_) / max(1.0, pa_(0, k_)), 3) for w_, k_ in wn_}, all=round(pa_(2) / max(1.0, pa_(0)), 3)),
                                 q_mean=dict({w_: round(pa_(3, k_) / max(1.0, pa_(0, k_)), 3) for w_, k_ in wn_}, all=round(pa_(3) / max(1.0, pa_(0)), 3)),
                                 pay_sum=round(float(PX_[1]), 6), pay_got_per_min=round(float(PX_[2]) / max(1e-9, float(PX_[0]) * DT_MIN), 4))
        if "stagger" in agg:                                             # (STAGGER_START) the first whole games begun at a drawn point of the clock
            SG_ = np.atleast_1d(agg["stagger"]).astype(np.float64)
            rec["stagger"] = dict(games=int(SG_[0]), start_s_mean=round(float(SG_[1] / max(1.0, SG_[0])), 1))
        if "jump_cost" in agg:                                           # (JUMP_COST) take-offs costed: per minute of a counted seat where it applies
            JC_ = np.atleast_1d(agg["jump_cost"]).astype(np.float64)     # (the simulator's JC_COLS; alive, nobody in view, games and item runs)
            jm_ = max(1e-9, float(JC_[0]) * DT_MIN)
            rec["jump_cost"] = dict(cost=float(getattr(E_, "JUMP_COST", 0.0)), minutes=round(float(JC_[0]) * DT_MIN, 1),
                                    takeoffs_per_player_min=round(float(JC_[1]) / jm_, 2), cost_per_player_min=round(float(JC_[2]) / jm_, 4))
        if "watch" in agg and "watch_x" in agg:                          # (WATCH_PAY) the look-back score at a fresh sighting by the weapon in hand
            WA_ = np.asarray(agg["watch"], np.float64).reshape(2, -1)    # (the simulator's stats["watch"]: sightings, score summed; WATCH_X_COLS)
            WX_ = np.atleast_1d(agg["watch_x"]).astype(np.float64)
            wn_ = [(w_, k_) for k_, w_ in enumerate(E_.WEAPONS) if w_ != "hmg"]
            rec["watch"] = dict(pay=float(getattr(E_, "WATCH_PAY", 0.0)), n=dict({w_: int(WA_[0, k_]) for w_, k_ in wn_}, all=int(WA_[0].sum())),
                                score=dict({w_: round(float(WA_[1, k_] / max(1.0, WA_[0, k_])), 3) for w_, k_ in wn_},
                                           all=round(float(WA_[1].sum() / max(1.0, WA_[0].sum())), 3)),
                                pay_sum=round(float(WX_[1]), 6), pay_counted=round(float(WX_[2]), 5), pay_abs=round(float(WX_[3]), 5))
        if "lg_quiet" in agg:                                            # (LG_QUIET_COST) the LG carried while the enemy is away, by his own senses
            LQ_ = np.atleast_1d(agg["lg_quiet"]).astype(np.float64)      # (the simulator's LGQ_COLS; counted seats, alive, games)
            LW_ = np.atleast_1d(agg.get("lg_quiet_w", np.zeros(len(E_.WEAPONS)))).astype(np.float64)
            lqm_ = max(1e-9, float(LQ_[0]) * DT_MIN)
            ws_ = LW_ / max(1.0, float(LW_.sum()))
            ix_ = {w_: k_ for k_, w_ in enumerate(E_.WEAPONS)}
            rec["lg_quiet"] = dict(cost=float(getattr(E_, "LG_QUIET_COST", 0.0)), minutes=round(float(LQ_[0]) * DT_MIN, 1),
                                   cost_per_player_min=round(float(LQ_[3]) / lqm_, 4), quiet_share=round(float(LQ_[1] / max(1.0, LQ_[0])), 4),
                                   lg_quiet_share=round(float(LQ_[2] / max(1.0, LQ_[0])), 4),     # of his time in games: the LG in hand while quiet
                                   in_hand_quiet=dict(lg=round(float(ws_[ix_["lg"]]), 4), rl=round(float(ws_[ix_["rl"]]), 4), rg=round(float(ws_[ix_["rg"]]), 4),
                                                      other=round(float(1.0 - ws_[ix_["lg"]] - ws_[ix_["rl"]] - ws_[ix_["rg"]]), 4)))
        if "lg_late" in agg and "lg_late_n" in agg:                      # (LG_QUIET_COST) weapon changes in the 2 s before a fresh sighting
            LL_ = np.asarray(agg["lg_late"], np.float64).reshape(len(E_.WEAPONS), -1)
            ln_ = float(np.atleast_1d(agg["lg_late_n"])[0])
            pr_ = sorted(((float(LL_[a_, b_]), E_.WEAPONS[a_] + ">" + E_.WEAPONS[b_]) for a_ in range(LL_.shape[0]) for b_ in range(LL_.shape[1])
                          if LL_[a_, b_] > 0), reverse=True)[:8]
            rec.setdefault("lg_quiet", {})["late"] = dict(sightings=int(ln_), per_sighting=round(float(LL_.sum()) / max(1.0, ln_), 4),
                                                          top={k_: int(v_) for v_, k_ in pr_})
        if UNI_GATE or UNI_RES:                                          # (v0.3.4 A, B) the parts' sizes
            with torch.no_grad():
                rec["gate"] = {n_: round(float(sum(p_.abs().max() for p_ in getattr(pol, n_).parameters())), 6)
                               for n_ in ("legs_gate", "legs_motor", "legs_res_a", "legs_res") if getattr(pol, n_, None) is not None}
        if KA_ON:                                                        # (LEGS_KEYS_ADD) the share of his frames on his legs his own output took
            KA_ = np.atleast_1d(agg.get("keys_add", np.zeros(1 + len(KA_COLS))))     # each column, the five biases, the weights' largest
            with torch.no_grad():
                kw_ = pol.pi.weight[KA_O:KA_O + 2 * len(KA_COLS)]
            rec["keys_add"] = dict(frames=int(KA_[0]), cols=list(KA_COLS), share=[round(float(x_ / max(1.0, float(KA_[0]))), 5) for x_ in KA_[1:]],
                                   shut=[round(float(x_), 3) for x_ in ka_over()], w=round(float(kw_.abs().max()), 6))
        if TA_HEAD >= 0:                                                 # (LEGS_TURN_ADD) his correction: the share of his frames on his legs
            TA_ = np.atleast_1d(agg.get("turn_add", np.zeros(3)))        # it was not 0 on, its mean size there, the bias of 0 over the others
            with torch.no_grad():
                tb_ = pol.pi.bias[TA_O:TA_O + ACTION_DIMS[TA_HEAD]]
                tw_ = pol.pi.weight[TA_O:TA_O + ACTION_DIMS[TA_HEAD]]
            rec["turn_add"] = dict(frames=int(TA_[0]), share=round(float(TA_[1] / max(1.0, float(TA_[0]))), 5),
                                   size=round(float(TA_[2] / max(1.0, float(TA_[1]))), 3), shut=round(float(tb_[0] - tb_[1:].mean()), 3),
                                   w=round(float(tw_.abs().max()), 6))
        if SK_ is not None:                                              # (--step-kl-pieces)
            rec["step_kl"] = round(float(SK_[1]) / max(1.0, float(SK_[0])), 6)
        if LIVE_REC is not None:                                         # (B-265) live.json applied or refused before this rollout
            rec["live"] = LIVE_REC
        if LS_REC is not None:                                           # (the safe restart) live_settings.env read before this rollout
            rec["live_settings"] = LS_REC
        if OVL:                                                          # (--overlap) how stale the rollout was, and where the time went
            ow_ = max(1.0, float(OV_[0])) if OV_ is not None else 1.0
            rec["overlap"] = dict(
                ppo=a.overlap_ppo,
                kl_stale=round(float(OV_[1]) / ow_, 6) if OV_ is not None else None,      # mean log p(played) - log p(learner before this update)
                clip_stale=round(float(OV_[2]) / ow_, 4) if OV_ is not None else None,    # the share of frames already outside the clip
                ratio_dev=round(float(OV_[3]) / ow_, 4) if OV_ is not None else None,     # mean |ratio - 1| before any step
                ratio_mean=round(float(OV_[5]) / ow_, 4) if OV_ is not None else None,    # mean ratio (1 to sampling noise)
                v_stale=round(float(OV_[4]) / ow_, 4) if OV_ is not None else None,       # mean |value now - value as played|
                frames=int(OV_[0]) if OV_ is not None else 0,
                wait=round(ovl_wait, 1),                                                   # the main thread's wait for this rollout
                update_s=round(t_end - t_prev, 1) if t_prev is not None else None,         # seconds from the last update's end to this one's
                switch_ms=a.overlap_switch_ms, priority=a.overlap_priority, next_in_flight=PEND is not None)
            if DEC:                                                      # (decoupled) the weights pi_prox / pi_played: their mean after the
                rec["overlap"].update(                                   # cap, the largest before it, the shares above the cap and below 1/cap;
                    is_mean=round(IS_[0], 4), is_max=round(IS_[1], 3), is_capped=round(IS_[2], 4), is_low=round(IS_[3], 4),
                    is_cap=a.overlap_is_cap, prox_values=bool(a.overlap_prox_values), prox_s=round(IS_[4], 1),
                    kl_played=round(OVK_[0] / max(1, kl_n), 5))          # KL(played || after the update) (kl is the learner's own step)
            t_prev = t_end
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if update % 5 == 1:
            print(" ".join("{}={}".format(k, v) for k, v in rec.items()), flush=True)
        if update % 10 == 0:
            save(os.path.join(out, "policy.pt"), mins)
    if PEND is not None:                                                 # (--overlap) the rollout in flight when the time is up: stopped at
        STOP.set()                                                       # its next frame and not learnt from (policy.pt and opt.pt are the
        PEND["th"].join()                                                # last update's, as without --overlap)
        print("overlap: the rollout of update {} was stopped unlearnt at the end".format(PEND["upd"]), flush=True)
    save(os.path.join(out, "policy.pt"), elapsed0 + (time.time() - t_start) / 60)
    for p in pipes:
        p.send(("close", None))


if __name__ == "__main__":
    main()

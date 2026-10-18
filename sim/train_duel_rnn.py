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
                 env.legs_prep() if legs_in else None))     # (LEGS_IN) the movement network's inputs of the frame about to be played
    last = {k: np.copy(v) for k, v in env.stats.items()}
    while True:
        cmd, data = remote.recv()
        if cmd == "step":
            if isinstance(data, tuple):                      # (LEGS_IN) the actions and the branch's logits [players, 17]
                env.legs_lg = data[1]
                data = data[0]
            obs, rew, done, info = env.step(data)
            delta = {k: env.stats[k] - last[k] for k in env.stats}
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
            remote.send((obs, rew, done, delta, env.script > 0, env.teach.copy(), env.intent_live.copy(), env.intent_teach.copy(),
                         env.key_dec.copy() if hasattr(env, "key_dec") else np.ones(env.n, bool),
                         env.legs_live.copy() if hasattr(env, "legs_live") else np.zeros(env.n, bool),      # (LEGS) the switch was read,
                         env.legs_on.copy() if hasattr(env, "legs_on") else np.zeros(env.n, bool),          # his legs moved him
                         np.asarray(info.get("r_long", np.zeros(env.n, np.float32)), np.float32),           # (v0.2) the part of this frame's pay that is for items and stack
                         info.get("aux"),                                                                   # (--aux) the truth the lesson's labels are made of (None: an older simulator)
                         (np.concatenate([info["legs_lab"], info["legs_held"][:, None]], 1).astype(np.int8)    # (--legs-teach) his legs' four choices
                          if "legs_lab" in info else None),                                               # (-1: no label), the stretch withheld; None: the simulator gives none
                         (info["hand_lab"].astype(np.float16) if "hand_lab" in info else None),            # (--hand-teach) the target of his NEXT reading of the weapon key (zeros: none)
                         env.legs_prep() if legs_in else None,                                              # (LEGS_IN) the movement network's inputs of the next frame
                         (np.asarray(env.legs_raw, np.int8) if legs_in and getattr(env, "legs_raw", None) is not None    # (--legs-learn) the branch's own draws
                          and len(env.legs_raw) == env.n else (np.full((env.n, 4), -1, np.int8) if legs_in else None)),  # of this frame (-1: none)
                         (env.solo_now.copy() if getattr(env, "solo_now", None) is not None else np.zeros(env.n, bool))))   # (SOLO_SELF) in his runs
        elif cmd == "curriculum":
            env.close_p, env.round_len, env.dmg_reward, env.intent_seek = data
            remote.send(True)
        elif cmd == "head_events":                           # (--head) the head's events since the last call, on its ticks (None: the
            remote.send(np.asarray(env.head_events(), np.float32) if hasattr(env, "head_events") else None)   # simulator has none: zeros)
        elif cmd == "close":
            break


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


def gru_seq(cell, e, h0, done):
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
    longest; a GRU only looks back, so the padding changes nothing that is read out (and gets no gradient)."""
    import torch
    T, B = done.shape
    w = [cell.weight_ih, cell.weight_hh, cell.bias_ih, cell.bias_hh]
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
    ap.add_argument("--react-ms", type=float, default=50, help="tracking delay on an enemy already in view")
    ap.add_argument("--acquire-ms", type=float, default=200, help="delay before an enemy who just came into view is noticed")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--env", default="duel_env", help="simulator module (duel_env_ffa: groups of more than two players)")
    ap.add_argument("--group", default="2", help="players per group, all against all (needs --env duel_env_ffa). Several "
                    "sizes separated by commas (2,3,4): the workers take them in turn, each with about as many players")
    a = ap.parse_args()
    if a.solo_self_drive:                                    # (v0.3.4 C) read by the simulators (spawned with this environment)
        os.environ["SOLO_SELF"] = "1"


    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    import importlib
    E_ = importlib.import_module(a.env)
    ACTION_DIMS, OBS_DIM, PERSONAS, WEAPONS = E_.ACTION_DIMS, E_.OBS_DIM, E_.PERSONAS, E_.WEAPONS
    KEY_HEADS = (0, 1, 2, 6)                                 # forward, strafe, vertical, weapon key: the left hand's outputs
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
    HAND_HEAD = 6                                            # ... the weapon key's output, where its choices begin among all outputs' and
    HAND_O, HAND_D = sum(ACTION_DIMS[:HAND_HEAD]), ACTION_DIMS[HAND_HEAD]      # how many they are ("keep", then a choice a weapon)

    def head_masks(dc, lv, ll, lo, act=None, so=None):
        """per output: the frames its choice counted on (None: every frame). dc: the left hand's outputs were read, lv: the
        intention was read, ll: the switch to his legs was read, lo: his legs moved him (their outputs were not his).
        (LEGS_KEYS_ADD) act: his choices [..., outputs]: on his legs his own output of a column counts where he chose "mine"
        for it; the five choices count on his legs (the keys' on the frames his hand reads them)"""
        out = []
        mine_ = {}
        if KA_ON:
            assert act is not None, "LEGS_KEYS_ADD: head_masks needs his choices"
            mine_ = {c_: (act[..., KA_HEAD + i_] == 1).to(lo.dtype) for i_, c_ in enumerate(KA_COLS)}
        for j in range(len(ACTION_DIMS)):
            m = dc if j in KEY_HEADS else (lv if j == I_HEAD else (ll if j == L_HEAD else None))
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
    if a.teacher_skip:
        print("no key labels in the runs of: {}".format(a.teacher_skip), flush=True)
    obs = np.concatenate([f[0] for f in first])
    teach = np.concatenate([f[1] for f in first])
    hand = np.concatenate([f[3] for f in first]) if HAND_LAB else None      # (--hand-teach) the label of the frame about to be played

    def legs_cat(parts):
        """(LEGS_IN) the workers' legs inputs as one array (a simulator without the movement network gives none: zeros)"""
        return np.concatenate([p_ if p_ is not None and p_.ndim == 2 and p_.shape[1] == LEGS_D else np.zeros((len(o_), LEGS_D), np.float32)
                               for p_, o_ in parts]).astype(np.float32)
    legs_x = legs_cat([(f[4], f[0]) for f in first]) if LEGS_IN else None
    N = len(obs)
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
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck0_ = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location="cpu")
        ATT = ck0_.get("attn")
        SLOW_CK = ck0_.get("slow")
        HEAD_CK = ck0_.get("head")
        UNI_CK = ck0_.get("legs_unify")
        if any(k_.startswith("aux.") for k_ in ck0_["model"]):
            AUX_SAVE = dict(aux_heads=ck0_.get("aux_heads"))
        AUX_CK = tuple(h_ for h_ in ("target", "strength", "first", "near") if "aux.{}.weight".format(h_) in ck0_["model"])
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
            o_ = OBS_DIM - getattr(E_, "N_PREF", 0) - getattr(E_, "N_RAIM", 0) - getattr(E_, "N_ES", 0) - getattr(E_, "N_B3", 0) - getattr(E_, "N_B2", 0) - E_.N_V02 + E_.V02_GAME + E_.V02_POS
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

        def step(self, x, h, f=None, sm=None, hd=None, ev=None, xl=None):
            dadd, gadd = self.uni_parts(xl)                      # (--legs-feat, --legs-guide; xl: the branch's inputs of this frame)
            if HAS_CELLS:
                ids = x[:, -2:].long().clamp(0, E_.MAX_CELLS - 1)   # the last two inputs are cell numbers, not values
                x = torch.cat([x[:, :-2], self.cell(ids[:, 0]), self.cell(ids[:, 1])], 1)
            e = self.enc(x)
            if self.attn is not None and (f is not None or self.door_open):
                e = e + ((self.attn(x, hm=h) if ATT_MEM else self.attn(x)) if f is None else f)   # what the door lets through, added to
                #                                                  the old encoder's (--attn-mem-query: h is his memory of the frame before)
            if hd is not None:                                   # (--head) his fast GRU reads the plan; the head ticks on its frames
                h = self.gru(e + self.head.plan_in(hd.plan) if dadd is None else e + self.head.plan_in(hd.plan) + dadd, h)
                _, ta_, wa_ = head_.live(self.head, hd, e, h, ev)
                self.zl = h
                lg_ = head_logits(self.pi(h), ta_, wa_)
                return self.out_(lg_, h, gadd), self.v(h).squeeze(-1), h
            h = self.gru(e if dadd is None else e + dadd, h)     # (--legs-feat: only his fast GRU reads the legs' features)
            if sm is None or self.slow is None:
                self.zl = h                                      # (what the outputs read: his memory, or with the slow one)
                lg_ = self.pi(h)
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

    def dists(logits):
        return [torch.distributions.Categorical(logits=l) for l in logits.split(ACTION_DIMS, -1)]

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
        ms = [on * dc if k_ else on for k_ in LEGS_KEYS]
        ds = [torch.distributions.Categorical(logits=l_) for l_ in lg.float().split(LEGS_DIMS, -1)]
        rl = raw.long().clamp(min=0)
        return sum(d_.log_prob(rl[..., j_]) * ms[j_] for j_, d_ in enumerate(ds)), ds, ms

    def load_net(net, sd):
        """a network's weights. Only the layers of --aux may be missing (they stay as they are: fresh in the learner) or
        left over (the lesson is off and they are not in this network)"""
        bad = net.load_state_dict(sd, strict=False)
        odd = [k_ for k_ in list(bad.missing_keys) + list(bad.unexpected_keys) if not k_.startswith("aux.") and not k_.startswith("head.aux.")]
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
                            and not (UNI_ON and n_.startswith(UNI_PFX))],
                           lr=a.lr, eps=1e-5)                # (LEGS_IN: not the branch; --head: not the head)
    if HEADL:                                                # (--head) the head in a group of its own at --head-lr-scale of the rate
        opt.add_param_group({"params": list(pol.head.parameters()), "lr": a.lr * a.head_lr_scale, "lr_scale": a.head_lr_scale})
    if UNI_ON:                                               # (--legs-door-lr-scale) legs_door and the guide's weights in a group of their own
        opt.add_param_group({"params": [p_ for n_, p_ in pol.named_parameters() if n_.startswith(UNI_PFX)],
                             "lr": a.lr * a.legs_door_lr_scale, "lr_scale": a.legs_door_lr_scale})
    if LEGS_LEARN and dev.type == "cuda":                    # (--legs-learn) the branch's sums in full float32 (torch's default; said, so
        torch.backends.cuda.matmul.allow_tf32 = False        # nothing elsewhere turns it on: its draws are the simulator's from these logits)
    if LEGS_LEARN:                                           # (--legs-learn) the branch in a group of its own; every setting of the rate
        opt.add_param_group({"params": list(pol.legs.parameters()), "lr": a.lr * a.legs_learn, "lr_scale": a.legs_learn})   # keeps its share
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
    ROUND_SECS_CK = 600.0 if float(getattr(E_, "GAME_P", 0.0)) + float(getattr(E_, "MID_START_P", 0.0)) >= 0.99 else 120.0

    def save(path, minutes):
        torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count, map=a.map,
                        obs_dim=OBS_DIM, action_dims=ACTION_DIMS, env="duel", arch="gru" if ATT is None else "gru+attn", attn=ATT,
                        hidden=H, minutes=minutes, **SLOW_SAVE, **HEAD_SAVE, **ORDER_SAVE, **UNI_SAVE,
                        **({"switch_fade": float(FADE[0])} if a.switch_fade else {}),
                        env_module=a.env, group=groups[0], groups=groups,
                        react_ms=a.react_ms, acquire_ms=a.acquire_ms, no_walk=bool(a.no_walk),
                        env_vars=dict({k_: os.environ[k_] for k_ in getattr(E_, "PLAY_VARS", ()) if os.environ.get(k_)}, **({"NO_SWITCH": "1"} if NO_SW else {})),
                        round_secs=ROUND_SECS_CK, arena_secs=float(a.arena_len),
                        game_secs=float(getattr(E_, "GAME_LEN", 0.0)) if getattr(E_, "GAME_ON", False) else 0.0,      # (GAME_P, LATE_P) he has played whole
                        game_vars={k_: os.environ[k_] for k_ in ("GAME_P", "LATE_P", "WIN_PAY", "MID_START_P", "SPAWN_START_P", "SPAWN_START_LEN", "OPENINGS", "OVERTIME", "STYLE_P") if os.environ.get(k_)},   # games: their clock and score
                        cells=E_.MAX_CELLS if HAS_CELLS else 0, cell_dim=CELL_DIM if HAS_CELLS else 0, **AUX_SAVE),
                   path)

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
    SNAP_NS = {}                                                       # (--no-switch) id(state dict) -> its switch is retired (a step-6 network)
    OPP_NS = [False]                                                   # ... the league network of this rollout's
    if a.resume:                                                       # the league survives a restart
        import glob
        import re as re_                                               # (by the minute in the name: from minute 10,000 the names have five
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "snap_*.pt")),          # digits and sort before the four-digit ones as text)
                        key=lambda f_: (int((re_.findall(r"\d+", os.path.basename(f_)) or ["0"])[0]), f_))[-8:]:
            ck_ = torch.load(f, weights_only=False, map_location=dev)
            snaps.append(ck_["model"])
            SNAP_NS[id(snaps[-1])] = str((ck_.get("env_vars") or {}).get("NO_SWITCH", "0")) not in ("0", "", "0.0")   # (--no-switch) a step-6 file
    anchors, vs_anchor = [], False                                     # ... and opponents that never leave it (--anchor-p)
    if a.anchor_p > 0:
        import glob
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "anchor_*.pt"))):
            ck_ = torch.load(f, weights_only=False, map_location=dev)
            anchors.append(ck_["model"])
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
                "jump_tries", "jump_over", "jump_short", "jump_frames", "move_frames", "move_arrive", "move_speed", "move_fast",
                "rj_tries", "rj_over", "rj_frames", "rj_shots",
                "hurt_dmg", "legs", "games", "open", "moments", "overtime")
    while time.time() - t_start < a.minutes * 60:
        update += 1
        mins = elapsed0 + (time.time() - t_start) / 60
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
            SNAP_NS[id(snaps[-1])] = NO_SW                               # (--no-switch: his own new snapshots are step-6 networks)
            snaps = snaps[-8:]
            save(os.path.join(out, "snapshots", "snap_{:04d}.pt".format(int(mins))), mins)
        if snaps:                                                        # pick this rollout's opponent
            vs_anchor = bool(anchors) and np.random.random() < a.anchor_p
            sd_o_ = anchors[np.random.randint(len(anchors))] if vs_anchor else snaps[np.random.randint(len(snaps))]
            load_net(opp, sd_o_)
            OPP_NS[0] = bool(SNAP_NS.get(id(sd_o_), False))
            opp.door_open = bool(opp.attn is not None and float(opp.attn.door.weight.abs().sum()) > 0)
        # the last rollout's buffers are let go before the new ones are made: the input buffer alone is 4.7 GiB with
        # 6,800 players, and two of them alive at once is what filled the card (15.8 GB) and broke the cap (2026-10-06)
        b_obs = b_act = b_logp = b_val = b_rew = b_done = b_w = b_live = b_dec = b_ll = b_lo = b_iteach = b_teach = b_rl = b_val2 = None
        b_lx = b_lr = b_llp = None
        if dev.type == "cuda":
            torch.cuda.empty_cache()
        b_obs = torch.zeros(T, N, OBS_DIM, device=dev, dtype=torch.float16 if a.obs_half else torch.float32)
        b_hq = torch.zeros(T, N, H, dtype=torch.float16) if ATT_MEM else None   # (--attn-mem-query) his memory of the frame before, as played
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
            b_ht = torch.zeros(AUX_TW, N, H, dtype=torch.float16) if AUX_TW else None      # (--aux-tail) his memory on the last frames
            b_bel = torch.zeros(T + 1, N, 5) if AUX_BEL else None                       # (--aux-fresh, --aux-measure) his belief inputs, raw
        h0 = h.clone()
        if HEADL:                                                        # (--head) the rollout's events, win labels; the ring folded and
            t_hd = time.time()                                           # re-run as the slow memory's; he plays from the state the update
            b_ev = torch.zeros(HD_J, N, HEADL["ev"], device=dev)         # re-runs; its start kept for the update
            b_wg = torch.full((T, N), -1.0, device=dev)                  # (win_game, win_band of each frame: none until read)
            b_wb = torch.full((T, N), -1.0, device=dev)
            HS_O.g = HS.g                                                # (a league network whose head is shut skipped the frames)
            if RINGH is not None:
                RINGH.trim(pol.head)
                head_.refresh(pol.head, HS, RINGH.state_all(pol.head))
            HD_RS0, HD_PEND, HD0 = HS.rs.clone(), [], HS.snap()
            hd_secs = [time.time() - t_hd, 0.0]
        if SLOW:                                                         # (--slow-mem) the ring's ticks beyond its length folded into its
            t_sl = time.time()                                           # stored state; he plays from the state the update re-runs
            RING.trim(pol.slow)
            SM.s = RING.state_all(pol.slow) * (1.0 - SM.rs)[:, None]
            SL_RS0, SL_PEND, SL_S0 = SM.rs.clone(), [], SM.s.clone()
            sl_secs = [time.time() - t_sl, 0.0]
        raw, agg, agg_map = [], {}, {}
        keep_raw = obs_count < OBS_FREEZE or (bool(a.obs_dump) and a.obs_dump_from <= update <= a.obs_dump_to)
        lk = [0, 0]                                                      # league matches: learner kills, snapshot kills
        t_roll = time.time()                                             # (the record's "time": the rollout's seconds, the learning step's)
        if dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats()
        for t in range(T):
            if keep_raw:
                raw.append(obs if obs_count < OBS_FREEZE else obs[np.random.rand(len(obs)) < 0.005])
            x = torch.from_numpy(norm(obs)).to(dev)
            if ATT_MEM:
                b_hq[t] = h.half().cpu()
            ev_ = None
            xlu_ = torch.from_numpy(legs_x).to(dev) if UNI_ON else None  # (--legs-feat, --legs-guide) the branch's inputs of this frame
            if HEADL and (HS.g + 1) % HD_K == 0:                         # (--head) a tick: the simulators' events since the last
                ev_ = head_events()
                b_ev[t // HD_K] = ev_
            with torch.no_grad():
                if HEADL:
                    t_hd = time.time()
                    logits, val, h = pol.step(x, h, hd=HS, ev=ev_, xl=xlu_)
                    if RINGH is not None and HS.ticked:                  # (--head) the tick's input, for the ring
                        HD_PEND.append((HS.u.half().cpu(), HS.r_tick.cpu()))
                    hd_secs[0] += time.time() - t_hd
                else:
                    logits, val, h = pol.step(x, h, sm=SM, xl=xlu_)
                if SM is not None and SM.ticked:                         # (--slow-mem) the tick's input, for the ring
                    SL_PEND.append((SM.u.half().cpu(), SM.r_tick.cpu()))
                if LONG:
                    b_val2[t] = pol.v2(pol.zl)
                if ORDER:                                                # (--ordered-heads) drawn in order
                    act, ds = draw(pol, logits)
                else:
                    ds = dists(logits)
                    act = torch.stack([d.sample() for d in ds], -1)
                lps = [d.log_prob(act[:, i]) for i, d in enumerate(ds)]
                if snaps and HEADL:                                      # (--head) the league's network with its own head, if open
                    lo, _, h_opp = opp.step(x, h_opp, hd=HS_O if opp.head_open else None, ev=ev_, xl=xlu_)
                    act_o = draw(opp, lo)[0] if ORDER else torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
                elif snaps:
                    lo, _, h_opp = opp.step(x, h_opp, sm=SM_O, xl=xlu_)
                    act_o = draw(opp, lo)[0] if ORDER else torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
            if NO_SW:                                                    # (--no-switch) off for his seats, and for the league's when its network
                act[:, L_HEAD] = torch.where(snap_players & bool(snaps) & (not OPP_NS[0]), act[:, L_HEAD], torch.zeros_like(act[:, L_HEAD]))
                #                                                          is a step-6 one (its file's env_vars: NO_SWITCH=1); v0.3.4's snapshots and
                #                                                          the control keep their own switch and legs, as they were trained
            b_obs[t], b_act[t], b_val[t] = x, act, val
            if AUX_TW and t >= T - AUX_TW:                               # (--aux-tail) his memory as he played the rollout's last frames
                b_ht[t - (T - AUX_TW)] = pol.zl.half().cpu()             # (--slow-mem: what the outputs read; h with it off)
            if AUX_BEL:                                                  # (--aux-fresh, --aux-measure) his belief inputs on this frame
                b_bel[t] = torch.from_numpy(np.ascontiguousarray(obs[:, BEL_IX], dtype=np.float32))
                if update == 1:
                    bel_check(obs)
            b_w[t] = learn * (1.0 - scr)
            b_teach[t] = torch.from_numpy(teach).to(dev)
            if HAND_LAB:
                b_hand[t] = torch.from_numpy(hand).to(dev)
            if AUX_W > 0:
                b_aux[t] = torch.from_numpy(aux)
            an = act.cpu().numpy()
            if LEGS_IN:                                                  # (LEGS_IN) his legs' logits: the branch of each seat's network
                with torch.no_grad():
                    xl_ = torch.from_numpy(legs_x).to(dev)
                    lgl_ = pol.legs_comb(legs_fwd(pol, xl_), pol.zl)            # (--legs-residual: from his memory of this frame)
                    if snaps:
                        lgl_ = torch.where(snap_players[:, None], opp.legs_comb(legs_fwd(opp, xl_), opp.zl), lgl_)
                if LEGS_LEARN or UNI_ON:
                    b_lx[t] = torch.from_numpy(legs_x)
                lgn_ = lgl_.float().cpu().numpy()
                for w_, p in enumerate(pipes):
                    p.send(("step", (an[w_off[w_]:w_off[w_ + 1]], lgn_[w_off[w_]:w_off[w_ + 1]])))
            else:
                for w_, p in enumerate(pipes):
                    p.send(("step", an[w_off[w_]:w_off[w_ + 1]]))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            if LEGS_IN:
                legs_x = legs_cat([(r[15], r[0]) for r in res])
            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)
            if LONG:
                b_rl[t] = torch.from_numpy(np.concatenate([r[11] for r in res])).to(dev)
            d = torch.from_numpy(np.concatenate([r[2] for r in res]).astype(np.float32)).to(dev)
            b_done[t] = d
            if HEADL and HD_WG >= 0:                                     # (--head) the frame's game and, on its last frame, its band (BUILD 3a:
                wl_ = np.concatenate([r[12][:, [HD_WG, HD_WB]] if r[12] is not None else np.full((len(r[2]), 2), -1.0)   # the info of the step
                                      for r in res]).astype(np.float32)                                                  # that played frame t)
                b_wg[t] = torch.from_numpy(wl_[:, 0]).to(dev)
                b_wb[t] = torch.from_numpy(wl_[:, 1]).to(dev)
            live = torch.from_numpy(np.concatenate([r[6] for r in res]).astype(np.float32)).to(dev)
            b_live[t] = live
            b_iteach[t] = torch.from_numpy(np.concatenate([r[7] for r in res])).to(dev)
            dec = torch.from_numpy(np.concatenate([r[8] for r in res]).astype(np.float32)).to(dev)
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
            if AUX_W > 0:
                aux = np.concatenate([r[12] for r in res])
            h = h * (1.0 - d)[:, None]                                   # memory resets on death / round restart
            h_opp = h_opp * (1.0 - d)[:, None]
            if SM is not None:                                           # (--slow-mem) ... and the slow memory's
                SM.reset(d)
                SM_O.reset(d)
            if HS is not None:                                           # (--head) ... and the head's
                HS.reset(d)
                HS_O.reset(d)
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
                    l_ = WAY_STORE.setdefault(w_map[w_], {}).setdefault((int(tr_[0]), int(tr_[1])), [])
                    l_.append(tr_[2:])
                    del l_[:-WAY_KEEP]
                for mk, ek in zip(r[3]["match_of_kill"], r[3]["even_kill"]):
                    if mk >= w_match[w_] // 2:                           # second half of the worker = league matches
                        lk[0 if ek else 1] += 1
        with torch.no_grad():
            if HEADL:                                                    # (--head) the frame after the rollout: never a tick (T is whole ticks)
                _, vT_, hT_ = pol.step(torch.from_numpy(norm(obs)).to(dev), h, hd=HS.peek(),
                                       xl=torch.from_numpy(legs_x).to(dev) if UNI_ON else None)
            else:
                _, vT_, hT_ = pol.step(torch.from_numpy(norm(obs)).to(dev), h, sm=SM.peek() if SM is not None else None,
                                       xl=torch.from_numpy(legs_x).to(dev) if UNI_ON else None)
            b_val[T] = vT_
            if LONG:
                b_val2[T] = pol.v2(pol.zl)
        if AUX_W > 0:
            b_aux[T] = torch.from_numpy(aux)
            if AUX_BEL:
                b_bel[T] = torch.from_numpy(np.ascontiguousarray(obs[:, BEL_IX], dtype=np.float32))
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
        t_learn = time.time()
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
        frac = min(1.0, mins / a.lr_minutes) if a.lr_minutes > 0 else min(1.0, (time.time() - t_start) / (a.minutes * 60))
        for g in opt.param_groups:                                       # (--legs-learn: the branch's group keeps its share, lr_scale)
            g["lr"] = a.lr * (1.0 - (1.0 - a.lr_end) * frac) * g.get("lr_scale", 1.0)
        lr_now = a.lr * (1.0 - (1.0 - a.lr_end) * frac)
        if a.lr_warm > 0:
            lr_now *= min(1.0, 0.1 + 0.9 * max(0.0, mins - fade0) / a.lr_warm)
            for g in opt.param_groups:
                g["lr"] = lr_now * g.get("lr_scale", 1.0)
        n_mb = a.minibatches
        kick = a.teach * max(0.0, 1.0 - (mins - fade0) / a.teach_minutes)
        if a.teach_warm > 0:
            kick *= min(1.0, max(0.0, mins - fade0) / a.teach_warm)
        kick_l = torch.zeros(())
        ik = a.intent_teach * max(0.0, 1.0 - (mins - fade0) / a.intent_teach_minutes)
        if a.intent_teach_floor > 0:                         # (v0.3.1, the owner 2026-10-15: fade 2.0 -> 0.1, then hold)
            ik = max(a.intent_teach_floor, ik)
        ik_l = torch.zeros(())
        wk = a.weapon_teach * max(0.0, 1.0 - (mins - fade0) / a.weapon_teach_minutes)
        wk_l = torch.zeros(())
        lt_w = a.legs_teach * (min(1.0, max(0.0, mins - fade0) / a.legs_teach_warm) if a.legs_teach_warm > 0 else 1.0)   # (--legs-teach)
        lt_acc = torch.zeros(4, 6, dtype=torch.float64, device=dev)      # ... per output: its frames, the sum of its loss, his likeliest choice is the label's,
        #                                                                  the chance he gives the label; its frames in withheld stretches, his likeliest right there
        lt_fr = torch.zeros(3, dtype=torch.float64, device=dev)          # ... the learner's frames, of them with a label, of those in withheld stretches
        hd_w = a.hand_teach * (min(1.0, max(0.0, mins - fade0) / a.hand_teach_warm) if a.hand_teach_warm > 0 else 1.0)   # (--hand-teach)
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
        UG_ = [None, None, None]                                         # (--legs-feat, --legs-guide) the last seq_pass's guide addition, the
        #                                                                  branch's logits and its "has a way" (for pi_t and the counters)

        def seq_pass(chunk, hh):
            """his outputs over the rollout's whole sequences for these players: the encoder, the attention part and the output
            layers in one go each, only his memory frame by frame -> (logits, value, memories, the two long values or None)"""
            xs_ = b_obs[:, chunk].float()
            e_ = pol.enc(xs_)
            if pol.attn is not None:
                if ATT_MEM:                                              # (--attn-mem-query) the query reads h_{t-1} as he played it
                    e_ = e_ + pol.attn(xs_.reshape(-1, OBS_DIM), hm=b_hq[:, chunk.cpu()].to(dev).float().reshape(-1, H)).view(T, len(chunk), -1)
                else:
                    e_ = e_ + pol.attn(xs_.reshape(-1, OBS_DIM)).view(T, len(chunk), -1)
            dadd_ = gadd_ = None
            if UNI_ON:                                                   # (--legs-feat, --legs-guide) the branch on this piece's inputs
                xlc_ = b_lx[:, chunk.cpu()].to(dev)
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
            if a.fast_gru:                                               # (B-237) the library's GRU over whole sequences, cut at his resets
                hs_a = gru_seq(pol.gru, eg_, hh, b_done[:, chunk])
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
            return gd_(pol.pi(hs_a), hs_a), pol.v(hs_a).squeeze(-1), hs_a, (pol.v2(hs_a) if LONG else None)

        kl_sum, cf_sum, kl_n = 0.0, 0.0, 0                              # the policy's step, measured in the last pass
        klh = np.zeros(len(ACTION_DIMS))
        old_h = None
        if a.kl_heads and (update % a.kl_heads == 0 or update <= 20):    # the log-probability of what he did, per head, before the update
            with torch.no_grad():
                old_h = torch.zeros(T, N, len(ACTION_DIMS), device=dev)
                for chunk in torch.arange(N, device=dev).chunk(n_mb):
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
            ax_s, ax_n, ax_w = torch.zeros(len(AUX_MI), dtype=torch.float64), torch.zeros(6, dtype=torch.float64), 0.0
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
                    nx_s, nx_n = torch.zeros(6, dtype=torch.float64), torch.zeros(4, dtype=torch.float64)      # sums: 2 losses, 4 x called right; weights
                    nx_h = [torch.zeros(AUX_NN["target"], dtype=torch.float64) for _ in range(4)]             # how often each landmark is the true one
                guess_secs = time.time() - t_aux
                gx_s, gx_n = torch.zeros(11, dtype=torch.float64), torch.zeros(6, dtype=torch.float64)      # sums: 5 losses, 5 x called right, the target
                gx_h = [torch.zeros(n_, dtype=torch.float64) for n_ in AUX_KN]                              # unseen; weights; how often each answer is true
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
            mb_s = torch.zeros(4, 4, dtype=torch.float64)                # frames, his memory's error, the belief's (nothing believed: the zero
            AUX_BL = b_bel[:T]                                           # answer's), frames his memory was nearer
        ll_acc = torch.zeros(8, dtype=torch.float64)                     # (--legs-learn) the learner's frames, of them the branch's (turn), its
        #                                                                  KL in the last pass (sum, pieces), the first piece's largest |log p - log p
        #                                                                  at play| before any step, its entropy (sum), the gradient's size (sum, count)
        ll_first = [True]
        ug_acc = torch.zeros(len(L_TAKES), 3, dtype=torch.float64)      # (--legs-guide) by guided output, the first pass: the frames his own
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

        for epoch in range(3):
            HO_[2] = epoch == 0
            perm = torch.randperm(N, device=dev)
            for chunk in perm.chunk(n_mb):                               # whole sequences per player
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
                            ug_acc[i_] += torch.stack([m_.sum(), ((mp_.argmax(-1) == b_act[:, chunk, o_]).float() * m_).sum(),
                                                       ((ds[o_].probs * mp_.exp()).sum(-1) * m_).sum()]).double().cpu()
                if a.teach_trunk < 1.0 and (kick > 0 or wk > 0 or ik > 0):
                    hs_ = hs_all                                         # the same outputs, the shared layers held back
                    dst = dists(pi_t(a.teach_trunk * hs_ + (1.0 - a.teach_trunk) * hs_.detach()))
                dstm = dst                                               # ... and what the movement teacher's loss reads (--teach-trunk-move)
                if kick > 0 and a.teach_trunk_move >= 0 and a.teach_trunk_move != a.teach_trunk:
                    tm_ = a.teach_trunk_move
                    dstm = ds if tm_ >= 1.0 else dists(pi_t(tm_ * hs_all + (1.0 - tm_) * hs_all.detach()))
                A = b_act[:, chunk]
                lv = b_live[:, chunk]
                dc = b_dec[:, chunk]
                hm = head_masks(dc, lv, b_ll[:, chunk], b_lo[:, chunk], A, b_so[:, chunk])
                lp = sum(dd.log_prob(A[..., j]) * (1.0 if hm[j] is None else hm[j]) for j, dd in enumerate(ds))
                ent = sum(w_ * dd.entropy() * (1.0 if hm[j] is None else hm[j]) for j, (w_, dd) in enumerate(zip(ent_heads, ds)))
                wgt = b_w[:, chunk]
                if LEGS_LEARN:                                           # (--legs-learn) the branch's part of what he did, the same advantage
                    lgl_ = pol.legs_comb(legs_fwd(pol, b_lx[:, chunk.cpu()].to(dev)), hs_all)    # (--legs-residual)
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
                            ll_acc[0] += float(wgt.sum())
                            ll_acc[1] += float((msl_[3] * wgt).sum())
                            ll_acc[5] += float((enl_ * wgt).sum())
                        if ll_first[0]:                                  # (before any step: the ratio's legs part is 1 to rounding)
                            ll_acc[4] = float(((lpl_ - b_llp[:, chunk]).abs() * (wgt > 0)).max())
                            ll_first[0] = False
                        if epoch == 2:
                            ll_acc[2] += float(((b_llp[:, chunk] - lpl_) * wgt).sum() / wgt.sum().clamp(min=1.0))
                            ll_acc[3] += 1.0
                if UNI_ON and ug_first[0] is None:                       # (before any step: the pass's log p is the rollout's to rounding)
                    with torch.no_grad():
                        ug_first[0] = float(((lp - b_logp[:, chunk]).abs() * (wgt > 0)).max())
                wsum = wgt.sum().clamp(min=1.0)
                ad = adv[:, chunk]
                ad = (ad - (ad * wgt).sum() / wsum) / (ad[wgt > 0].std() + 1e-8)
                ratio = (lp - b_logp[:, chunk]).exp()
                if epoch == 2:
                    with torch.no_grad():
                        kl_sum += float(((b_logp[:, chunk] - lp) * wgt).sum() / wsum)
                        cf_sum += float((((ratio - 1.0).abs() > clip).float() * wgt).sum() / wsum)
                        kl_n += 1
                        if old_h is not None:
                            for j, dd in enumerate(ds):
                                mk_ = 1.0 if hm[j] is None else hm[j]
                                klh[j] += float(((old_h[:, chunk, j] - dd.log_prob(A[..., j])) * mk_ * wgt).sum() / wsum)
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
                    ci_ = chunk.cpu()
                    ay_, am_, ac_ = AUX_Y[:, ci_].to(dev).float(), AUX_M[:, ci_].to(dev), AUX_C[:, ci_].to(dev).long()
                    hx_ = hs_all if a.aux_trunk >= 1.0 else a.aux_trunk * hs_all + (1.0 - a.aux_trunk) * hs_all.detach()   # (as --teach-trunk)
                    wa_ = wgt                                            # (the learner's frames; --aux-tail: the rollout before's last frames in front)
                    if AUX_TWN:
                        hx_ = torch.cat([AUX_TH[:, ci_].to(dev).float(), hx_])
                        wa_ = torch.cat([AUX_TWG[:, ci_].to(dev), wgt])
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
                        ak_ = AUX_K[:, ci_].to(dev).long()
                        wk_ = AUX_KM[:, ci_].to(dev).float() * wa_[..., None]        # a label is there, on the learner's frames
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
                        an_ = AUX_N[:, ci_].to(dev).long().clamp(max=AUX_NN["target"] - 1)
                        wr_ = AUX_NM[:, ci_].to(dev).float() * wa_[..., None]
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
                            ax_s += (mv_ * wm_[..., AUX_MI]).sum((0, 1)).double().cpu()
                            ax_n += wm_.sum((0, 1)).double().cpu()
                            ax_w += float(wgt.sum())
                            if AUX_MEAS:                                 # (--aux-measure) his memory against his belief inputs, where place is asked
                                bl_ = AUX_BL[:, ci_].to(dev)
                                wp_ = wm_[AUX_TWN:, :, 0]
                                tr_ = ay_[AUX_TWN:, :, 0:3] * 1500.0
                                hd_ = e_pl[AUX_TWN:].norm(dim=-1) * 1500.0
                                ok_ = bl_[..., 0] > 0.5
                                be_ = torch.where(ok_, (bl_[..., 1:4] * 1500.0 - tr_).norm(dim=-1), tr_.norm(dim=-1))
                                bd_ = torch.full(ok_.shape, 3, dtype=torch.long, device=dev)
                                bd_[bl_[..., 4] < 0.99999] = 2
                                bd_[bl_[..., 4] * AUX_BEL_AGE < 2.0] = 1
                                bd_[~ok_] = 0
                                for b_ in range(4):
                                    w_ = wp_ * (bd_ == b_).float()
                                    mb_s[b_] += torch.stack([w_.sum(), (hd_ * w_).sum(), (be_ * w_).sum(), ((hd_ < be_).float() * w_).sum()]).double().cpu()
                            if AUX_Q:
                                for j_, (o_, c_, y_) in cg_.items():
                                    r_ = (o_.argmax(-1) == y_).float()
                                    gx_s[j_] += float((c_ * wk_[..., j_]).sum())
                                    gx_s[5 + j_] += float((r_ * wk_[..., j_]).sum())
                                    gx_h[j_] += torch.bincount(y_.reshape(-1), weights=wk_[..., j_].reshape(-1).double(), minlength=AUX_KN[j_]).cpu()
                                    if j_ == 0:                          # ... the target on the frames the enemy is not in view
                                        gx_s[10] += float((r_ * wk_[..., 5]).sum())
                                        gx_h[5] += torch.bincount(y_.reshape(-1), weights=wk_[..., 5].reshape(-1).double(), minlength=AUX_KN[5]).cpu()
                                gx_n += wk_.sum((0, 1)).double().cpu()
                                if "near" in AUX_Q:
                                    rn_ = (on_.argmax(-1) == an_).float()        # [T, players, 2]
                                    for j_ in range(4):                          # now, later; the same with the enemy not in view
                                        nx_s[2 + j_] += float((rn_[..., j_ % 2] * wr_[..., j_]).sum())
                                        nx_h[j_] += torch.bincount(an_[..., j_ % 2].reshape(-1), weights=wr_[..., j_].reshape(-1).double(),
                                                                   minlength=AUX_NN["target"]).cpu()
                                    nx_s[0] += float((cn_[..., 0] * wr_[..., 0]).sum())
                                    nx_s[1] += float((cn_[..., 1] * wr_[..., 1]).sum())
                                    nx_n += wr_.sum((0, 1)).double().cpu()
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
                if LEGS_IN and not LEGS_SAID:                    # (LEGS_IN, stage a) said once: the frozen branch takes no gradient
                    LEGS_SAID.append(sum(int(p_.grad is not None and bool(p_.grad.abs().sum() > 0)) for p_ in pol.legs.parameters()))
                    print("legs inside: the first backward reached {} of the branch's {} tensors ({})".format(
                        LEGS_SAID[0], len(list(pol.legs.parameters())), "learning: all" if LEGS_LEARN else "frozen: none"), flush=True)
                if LEGS_LEARN:                                           # (--legs-learn) the branch's gradient is clipped on its own: the
                    ll_acc[6] += float(nn.utils.clip_grad_norm_(pol.legs.parameters(), 0.5))    # rest's step is as without it
                    ll_acc[7] += 1.0
                if HEADL:                                                # (--head) the head's gradient is clipped on its own: the rest's
                    hd_acc[12] += float(nn.utils.clip_grad_norm_(pol.head.parameters(), 0.5))       # step is as without it
                    hd_acc[13] += 1.0
                if UNI_ON:                                               # (--legs-feat, --legs-guide) their gradient clipped on its own: the
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if n_.startswith(UNI_PFX)], 0.5)    # rest's step is as without them
                if AUX:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("aux.") and not n_.startswith(UNI_PFX)
                                              and not (LEGS_LEARN and n_.startswith("legs.")) and not (HEADL and n_.startswith("head."))], 0.5)
                    nn.utils.clip_grad_norm_(pol.aux.parameters(), 0.5)
                elif LEGS_LEARN:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("legs.") and not n_.startswith(UNI_PFX)
                                              and not (HEADL and n_.startswith("head."))], 0.5)
                elif HEADL:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith("head.") and not n_.startswith(UNI_PFX)], 0.5)
                elif UNI_ON:
                    nn.utils.clip_grad_norm_([p_ for n_, p_ in pol.named_parameters() if not n_.startswith(UNI_PFX)], 0.5)
                else:
                    nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
                opt.step()
        if SLOW:                                                         # (--slow-mem) the rollout's ticks join the ring
            RING.push(SL_PEND)
            SL_PEND = []
        if RINGH is not None:                                            # (--head) the rollout's ticks join its ring
            RINGH.push(HD_PEND)
            HD_PEND = []
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
                                                    for i_, k_ in enumerate(("wasted", "jump", "near", "way", "place")) if i_ < len(np.atleast_1d(agg.get("blind_rl_how", np.zeros(5))))}),
                            prefire_frames=int(agg.get("prefire_frames", 0)), blind_charged_frames=int(agg.get("blind_bill", 0)),
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
                   vs_snapshot_kill_share=round(lk[0] / max(1, lk[0] + lk[1]), 3) if snaps and not vs_anchor else None,
                   vs_anchor_kill_share=round(lk[0] / max(1, lk[0] + lk[1]), 3) if snaps and vs_anchor else None,
                   league_size=len(snaps), entropy=round(float(en), 3), close_p=round(close_p, 2),
                   time=dict(rollout=round(t_learn - t_roll, 1), learn=round(t_end - t_learn, 1)),                 # seconds of this update
                   gpu=dict(peak_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2), held_gb=round(torch.cuda.memory_reserved() / 1e9, 2))
                   if dev.type == "cuda" else None)                    # the card's memory at its peak in this update
        if SLOW:                                                         # (--slow-mem) its door, what comes through it beside his fast memory,
            with torch.no_grad():                                        # the ring's ticks, the seconds of its parts (fold + re-run before the
                ds_ = pol.slow.door(SM.s[:2048])                         # rollout; the passes of the update)
                rec["slow"] = dict(w=round(float(pol.slow.door.weight.abs().mean()), 6),
                                   share=round(float(ds_.abs().mean() / (h[:2048].abs().mean() + 1e-8)), 4),
                                   s=round(float(SM.s[:2048].abs().mean()), 4), ring=RING.L,
                                   ring_min=round(RING.L * SLOW["every"] * 0.025 / 60.0, 2),
                                   fold_s=round(sl_secs[0], 2), pass_s=round(sl_secs[1], 2))
        if pol.attn is not None:                                         # the door: its weights, and what comes through it beside the old encoder's
            with torch.no_grad():
                xs_ = b_obs[T - 1, :2048].float()
                rec["door"] = dict(w=round(float(pol.attn.door.weight.abs().mean()), 6),
                                   share=round(float(pol.attn(xs_).abs().mean() / (pol.enc(xs_).abs().mean() + 1e-8)), 4))
        if UNI_ON:                                                       # (--legs-feat, --legs-guide) the parts: legs_door's size and the share
            with torch.no_grad():                                        # of his fast GRU's input variance that comes through it; the guide's
                rec_u = dict(first_err=ug_first[0])                      # weights and how often his own choice is the branch's (switch off)
                if UNI_FEAT:
                    xs_ = b_obs[T - 1, :2048].float()
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
                                            opponent_now="anchor" if (snaps and vs_anchor) else "snapshot" if snaps else "himself"),
                                pay_size=dict(win=round(float(g_[11] / n_), 3), flat=round(float(g_[12] / n_), 3)),  # the first seat's pay a game, without its sign
                                by_map={m_: [int(x_) for x_ in np.atleast_1d(v_["games"])[[0, 1, 4, 5, 6, 7]]]       # whole, late; league: games, won, level, lost
                                        for m_, v_ in agg_map.items() if "games" in v_ and float(np.atleast_1d(v_["games"])[[0, 1]].sum()) > 0})
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
            rec["legs_learn"] = dict(rate=a.legs_learn, lr=opt.param_groups[-1]["lr"], lr_rest=opt.param_groups[0]["lr"], ent_w=a.legs_ent,
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
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if update % 5 == 1:
            print(" ".join("{}={}".format(k, v) for k, v in rec.items()), flush=True)
        if update % 10 == 0:
            save(os.path.join(out, "policy.pt"), mins)
    save(os.path.join(out, "policy.pt"), elapsed0 + (time.time() - t_start) / 60)
    for p in pipes:
        p.send(("close", None))


if __name__ == "__main__":
    main()

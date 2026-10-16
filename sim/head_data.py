"""Training sequences for v0.4's head (docs/v0.4/BUILD_v0.4.md section 4): what the network would have been shown, frame by
frame, in the body of a player who really played, and what that player then did over seconds and minutes.

    python sim/head_data.py demos --map bloodrun --limit 3 --ck <policy.pt> --out scratch/head_data
    python sim/head_data.py sessions --archives T:/quake-sessions/public/<a>.tar.gz ... --seat both --ck <policy.pt> --out ...
    python sim/head_data.py inputs --session <folder with inputs_*.npz, frames.csv, events.jsonl> --out ...
    python sim/head_data.py synth --session <an extracted session folder> --ck <policy.pt> --into <new folder>
    python sim/head_data.py show <shard.npz ...>        # shapes and how often each label is known
    python sim/head_data.py count                       # how many demos and duel sessions there are per map

Sources
  demos     the pro demos (<demo root>/demos/<map>, the folder named in data/demo_root.txt), parsed with tools/demodump into
            a scratch folder. The converted sets of sim/demo_dataset.py (<demo root>/sets) are NOT used: they hold the
            311 inputs of 2026-10-04 and the hands of v0.3.1 read 797. The inputs are built here again with today's
            observe() of the module the checkpoint names (duel_env_ffa, two players), fed the way the 1v1 plugin feeds it
            (plugins/duelbot.py frame(): fill_player, hear / note_noise, the items, note_take, the clock, senses, the
            hit feedback): the recording player is seat 0, the other player seat 1.
  sessions  the public server's 1v1 session archives (T:\\quake-sessions\\public\\*.tar.gz, read only; each is unpacked into
            a scratch folder): frames.csv has both players every frame, events.jsonl the pickups and deaths, missiles.csv
            the projectiles. Seat b (Bobby) or o (the person) is seat 0.
  inputs    the plugin's input logs (inputs_<n>.npz in a session folder: t, frame, obs[797], h[512], acts[13], every 8th
            frame; plugins/duelbot.py inputs_log). Nothing is rebuilt: the inputs and the memory are what he was given. The
            labels come from the same session's frames.csv and events.jsonl (by time).

What is not rebuilt exactly (demos and sessions; the input logs are exact)
  his intention   the choice of the hands' intention head is an input back to him (INTENTS). Here it is the item rule's
                  choice (env.intent_rule(), read every INTENT_EVERY frames through env.intend()), --intent rule; or nothing
                  (--intent none). Not the hands' own choice: that would need the network inside the builder.
  his way, legs   the way head's choice is 0; legs and their switch are what observe() shows with no legs network.
  demos           the enemy's health and armor (100 / 0), what the recorder dealt (0: no hit feedback, no note_dealt, no
                  pain sound), the enemy's crouch and his weapons beyond the one in hand; the enemy only while the server
                  sent him (else where he was last sent, not in view, not heard); items only while the server sent them
                  (else their last state, timers counted on); sounds only from what is seen in the snapshots (shots by the
                  firing flag, jumps, landings, teleports, pickups near him).
  sessions        ammunition of the shotgun, grenades, plasma and machine gun (frames.csv logs RL, RG and LG only: a typical
                  amount while held), the weapons owned beyond RL / RG / LG (those seen in hand since the spawn), item timers
                  (from the pickups of events.jsonl and the respawn times: no other item state is logged), the hit feedback
                  from health + armor drops (as the plugin does), the enemy's shots by the fire button and the weapon's refire.
  both            the random draws of hearing (env.rng) are not the server's.

Labels, one row per head tick (a tick on frame f of a shard when (f + 1) % 8 == 0, f counted over the frames that have
inputs: his living frames)
  target    the next item or holding place he reached, as an index of INTENTS: an item of the intention list (MH, RA, RL, RG,
            LG, YA, YA2) by its pickup, a holding place (H1..H8, sim/pro_holds/<map>.json) by standing within HOLD_R /
            HOLD_Z of it for HOLD_DWELL s; the first after the tick, within TARGET_HORIZON s and before his next death; -1
            where there is none.
  en_cls    the enemy's landmark 3, 10 and 30 s after the tick (the target nearest him in seconds of way, as the trainer's
            aux question "near": env.aux()'s en_near), -1 where not known: in a demo only while the server sent him, and
            never while he is dead. en_pos: his true place then (NaN where unknown).
  win       the band of the final score margin of the game, from the player's side: 0 <= -5, 1 -4..-1, 2 0, 3 1..4, 4 >= 5;
            -1 outside a whole game with a known end (demos: the intermission came; sessions: a real game, player_stats).
  baselines rule (env.intent_rule() of seat 0 at the tick), bel_cls (the landmark of the place v0.2's inputs believe the
            enemy at, v02_bel; -1 where nothing is believed): the gate numbers of pretrain_head.py.
  ev        the tick's 32 events (BUILD_v0.4 section 3), counted here by the builder until env.head_events() lands; the
            same columns: dealt, taken (/100), he fragged, he died, enemy in view (share of the tick's frames), enemy heard,
            his pickups MH RA YA RL RG LG health-or-ammo, the enemy's pickups heard or seen (same classes), respawns heard MH
            RA YA weapon, the enemy's pain heard, his weapon changed, he jumped, he landed from a fall, padding.

A shard (<out>/<source>_<name>.npz): obs [F, 797] float16 (inputs logs: one row a tick), done [F] (his memory is cleared
after this frame: a new game, a cut in the demo), tick [T] (the frame of each tick), the tick labels above, h_in [T, 512]
(inputs logs only: the memory he answered the tick's frame from), meta (JSON: source, map, seat, env module, switches).
No names, Steam ids or addresses are read or written.
"""
import argparse
import csv
import glob
import hashlib
import importlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

EVERY = 8                                                  # a head tick every 8 frames (BUILD_v0.4 section 1)
DT = 0.025
AHEAD = (3.0, 10.0, 30.0)                                  # the enemy's place this many seconds after a tick
TARGET_HORIZON = 60.0                                      # a target reached later than this after the tick says nothing
HOLD_DWELL = 1.0                                           # seconds at a holding place before it counts as reached
BAND_EDGES = (-5, -1, 0, 4)                                # <= -5 | -4..-1 | 0 | 1..4 | >= 5
N_EV = 32
EV_NAMES = ["dealt", "taken", "frag", "died", "seen", "heard"] + ["took_" + c for c in ("MH", "RA", "YA", "RL", "RG", "LG", "small")] + \
           ["en_took_" + c for c in ("MH", "RA", "YA", "RL", "RG", "LG", "small")] + ["resp_" + c for c in ("MH", "RA", "YA", "wp")] + \
           ["pain", "wswitch", "jumped", "landed"]
EV = {k: i for i, k in enumerate(EV_NAMES)}
assert len(EV_NAMES) <= N_EV
QLW = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}
TYPICAL_AMMO = {"mg": 100.0, "sg": 10.0, "gl": 10.0, "pg": 50.0, "hmg": 50.0}       # (sessions: not logged)
SCRATCH = os.path.join(ROOT, "scratch")
LAND_VZ = 400.0                                            # a landing at this falling speed or more is "from a fall"
DUEL_WINDOW_MIN = 300.0                                    # a real game counts as whole from five minutes of play


def band(margin):
    m = int(margin)
    return 0 if m <= -5 else 1 if m <= -1 else 2 if m == 0 else 3 if m <= 4 else 4


def demo_root():
    f = os.path.join(ROOT, "data", "demo_root.txt")
    if os.path.exists(f):
        p = open(f).read().strip()
        if p:
            return p
    return os.path.join(ROOT, "data")


# ------------------------------------------------------------------------------------------------------------ the simulator
def env_spec(ck_path=None, spec_path=None):
    """the simulator the hands were trained in: module, switches, delays (from a checkpoint, read with torch on the CPU,
    or from a JSON file written by `spec`)"""
    if spec_path:
        return json.load(open(spec_path))
    import torch
    ck = torch.load(ck_path, weights_only=False, map_location="cpu")
    return dict(env=str(ck.get("env_module") or "duel_env_ffa"), env_vars={k: str(v) for k, v in (ck.get("env_vars") or {}).items()},
                react_ms=float(ck.get("react_ms", 100.0)), acquire_ms=float(ck.get("acquire_ms", 200.0)),
                obs_dim=int(ck["obs_mean"].shape[0]), group=int(ck.get("group") or 2))


def make_env(spec, mp, seed=1):
    os.environ.update(spec["env_vars"])
    os.environ.setdefault("ROUTE_CACHE", os.path.join(SCRATCH, "route_cache"))   # (data/ is read only: caches go to scratch)
    os.makedirs(os.environ["ROUTE_CACHE"], exist_ok=True)
    E = importlib.import_module(spec["env"])
    assert E.OBS_DIM == spec["obs_dim"], (E.OBS_DIM, spec["obs_dim"])
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    kw = dict(group=spec.get("group", 2)) if spec["env"].endswith("ffa") else {}
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=seed, nav=nav if os.path.exists(nav) else None, **kw)
    env.react_frames = round(spec["react_ms"] / 25)
    env.acquire_frames = round(spec["acquire_ms"] / 25)
    env.lab = None
    env.kind[:] = E.NORMAL
    env.script[:] = 0
    if hasattr(env, "style"):                                # (from v0.3 on no styles: STYLE_P=0, as the export tells the plugins)
        env.style[:] = 0
    return E, env


def item_classes(env, E):
    """item index -> (intention index or -1, event class 0..6)"""
    intent = np.full(env.nI, -1, np.int64)
    for gi, lab in enumerate(env.route_goal):
        intent[env.route_item[gi]] = E.INTENTS.index(lab)
    cls = np.full(env.nI, 6, np.int64)
    for k, d in enumerate(env.item_def):
        kind, val, lab = d[0], d[1], d[4]
        cls[k] = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab in ("YA", "GA") else \
            3 if (kind == "wp" and val == E.RL) else 4 if (kind == "wp" and val == E.RG) else 5 if (kind == "wp" and val == E.LG) else 6
    return intent, cls


def landmark(env, E, pos):
    """the landmark nearest each place by seconds of way FROM it, as env.aux()'s en_near: [n] INTENTS index, -1 none"""
    pos = np.asarray(pos, np.float32).reshape(-1, 3)
    out = np.full(len(pos), -1, np.int64)
    R = env.route
    if R is None or not len(pos):
        return out
    nd = R.locate(pos)
    bt = np.full(len(pos), 1e8, np.float32)
    for k in range(1, len(E.INTENTS)):
        gs = env.intent_more.get(k)
        if gs is None:
            gs = np.array([env.intent_gi[k]] if env.intent_gi[k] >= 0 else [], np.int64)
        gs = np.asarray(gs, np.int64)
        gs = gs[gs < len(R.T)]
        if k == E.EN_INTENT or not len(gs):
            continue
        t = R.T[gs][:, nd].min(0)
        out = np.where(t < bt, k, out)
        bt = np.minimum(bt, t)
    return out


class Player:
    """one player's state for a frame, as the game (or a demo) gives it"""
    __slots__ = ("pos", "vel", "yaw", "pitch", "hp", "armor", "w", "has", "ammo", "duck", "fire", "alive", "present", "ground")

    def __init__(self, nw):
        self.pos, self.vel = np.zeros(3, np.float32), np.zeros(3, np.float32)
        self.yaw = self.pitch = 0.0
        self.hp, self.armor, self.w = 100.0, 0.0, 3
        self.has, self.ammo = np.zeros(nw, bool), np.zeros(nw, np.float32)
        self.duck = self.fire = False
        self.alive = self.present = True
        self.ground = None                                   # None: found by a ray as the plugin does


class Feeder:
    """the 1v1 plugin's frame() without the game: seat 0 is the player whose inputs are built, seat 1 the other one.
    One frame: frame(me, en, ...) -> the inputs [OBS_DIM] (None while seat 0 is dead), and the frame's events."""

    def __init__(self, E, env, intent_mode="rule"):
        self.E, self.env = E, env
        self.intent_mode = intent_mode
        self.alive = [None, None]
        self.ground_was, self.prev_opp = None, None
        self.fb_next = np.zeros(4, np.float32)
        self.item_up = np.ones(env.nI, bool)
        self.item_back = np.zeros(env.nI, np.float32)
        self.last_shot = [99.0, 99.0]
        self.w_last = None
        self.it_intent, self.it_cls = item_classes(env, E)
        self.ev = np.zeros(N_EV, np.float32)
        self.ev_frames = 0
        self.vz_was = 0.0

    # ---- events of the tick
    def take_events(self):
        ev = self.ev.copy()
        if self.ev_frames:
            ev[EV["seen"]] /= self.ev_frames
        self.ev[:] = 0.0
        self.ev_frames = 0
        return ev

    def _fill(self, i, p):
        env, E = self.env, self.E
        if p.ground is None:
            floor = env.w.rays(p.pos[None], np.array([[0, 0, -1.0]], np.float32), 30.0)[0, 0] < 1
            ground = 1.0 if (abs(p.vel[2]) < 1 and floor) else 0.0
        else:
            ground = float(p.ground)
        if hasattr(env, "sp_hist"):
            env.sp_hist[i, 1:] = env.sp_hist[i, :-1].copy()
            env.sp_hist[i, 0] = float(np.hypot(env.state[i, 3], env.state[i, 4]))
        env.state[i] = [*p.pos, *p.vel, ground, p.yaw]
        env.yaw[i], env.pitch[i] = p.yaw, float(np.clip(p.pitch, -89, 89))
        env.hp[i], env.armor[i] = p.hp, p.armor
        env.weapon[i] = p.w
        env.has[i] = p.has
        env.ammo[i] = p.ammo
        env.duck[i] = p.duck

    def new_game(self):
        """a real game has begun (the plugin's new_game_in): nothing known, nothing believed, nothing taken; the items lie there"""
        env = self.env
        if hasattr(env, "_v02_round"):
            env.it_t[:], env.e_got[:], env.e_life[:] = 99.0, 0.0, 99.0
            if hasattr(env, "bel_t"):
                env.bel_t[:] = 99.0
            env._v02_round(np.ones(env.n, bool))
        self.item_up[:] = True
        self.item_back[:] = 0.0

    def _senses(self, present):
        """the plugin's senses(): sight and hearing as step(); the other player only while present"""
        env, E = self.env, self.E
        s, n = env.state, 2
        eye = env._eye(s)
        opp = np.arange(n) ^ 1
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        yr, pr = np.radians(env.yaw), np.radians(env.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        infov = (to * fdir).sum(1) / dist > (env.fov()[2] if hasattr(env, "fov") else E.FOV_COS)
        alive = (env.hp[opp] > 0) & np.array([present, True])
        cand = np.nonzero(infov & (dist < 4000) & alive)[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = env._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        env.visible = vis
        heard = (~vis) & alive & (dist < E.HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250)
        if hasattr(env, "vis_run"):
            need_ = max(1, env.acquire_frames - env.react_frames)
            if getattr(E, "SURPRISE_MS", 0) > 0 and hasattr(env, "acq_extra"):
                ecc_ = np.degrees(np.arccos(np.clip((to * fdir).sum(1) / dist, -1.0, 1.0)))
                env.acq_extra = np.where(vis & (env.vis_run == 0), E.surprise_frames(ecc_, env.seen_t), np.where(vis, env.acq_extra, 0))
                need_ = need_ + env.acq_extra
            env.vis_run = np.where(vis, env.vis_run + 1, 0)
            vis = vis & (env.vis_run >= need_)
            env.acquired = vis
        env.known[vis] = s[opp[vis], :3]
        if heard.any():
            env.known[heard] = s[opp[heard], :3] + env.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        env.seen_t = np.where(vis | heard, 0.0, env.seen_t + E.DT).astype(np.float32)
        if hasattr(env, "seen2") and env.seen2.shape[1] == 1:
            env.vis2[:, 0], env.vis_run2[:, 0], env.acq2[:, 0] = env.visible, env.vis_run, env.acquired
            env.known2[:, 0], env.seen2[:, 0] = env.known, env.seen_t
        return bool(heard[0])

    def frame(self, me, en, clock_t, scores, taken=(), missiles=(), dealt=0.0, took=0.0, items=None, game_new=False):
        """one server frame. me, en: Player. clock_t: seconds of the game shown (whole-games clock). scores: (his, the
        other's). taken: [(seat, item index)] picked up this frame. missiles: [(seat, kind E.RL/GL/PG, pos, vel, age)].
        dealt / took: damage this frame (health + armor). items: (up [nI] bool, seen [nI] bool) from a demo snapshot, or
        None (the feeder's own timers). -> inputs [OBS_DIM] float32 or None (seat 0 dead)"""
        env, E = self.env, self.E
        ev = self.ev
        if game_new:
            self.new_game()
        for i, p in ((0, me), (1, en)):
            up = p.alive
            was = self.alive[i]
            if up and not was:
                if hasattr(env, "v02_pk"):                   # (new_life_of)
                    m_ = env._mates(i)
                    env.e_got[m_, env._slot(i)] = 0.0
                    env.v02_pk[m_, env._slot(i)] = 0.0
                if was is None and hasattr(env, "_es_set") and getattr(E, "EN_STACK", False):
                    env._es_set(1 - i, i, spawn=True)
                self.ground_was = None
                if i == 1:
                    env.dmg_life[0] = 0.0
                    if hasattr(env, "shot_t"):
                        env.shot_t[0] = env.trail_t[0] = 99.0
                    self.prev_opp = None
                else:
                    if hasattr(env, "life_t"):
                        env.life_t[0], env.flinch[0], env.focus[0] = 0.0, 0.0, E.FOCUS_SECS
                    if hasattr(env, "intent_new"):           # (fresh_life)
                        env.intent[0], env.intent_t[0], env.intent_new[0], env.intent_done[0] = 0, 0.0, True, False
                    for name, v in (("zoom", False), ("fire_last", False), ("mouse_hold", 99), ("pad", 0.0), ("pad_lift", 0),
                                    ("walk_last", False), ("resp_t", 99.0)):
                        if hasattr(env, name):
                            getattr(env, name)[0] = v
                    env.mv[:] = 0
                    env.cool[:] = 0
                    env.seen_t[:] = 9.0
                    env.opp_hist = []
                    self.w_last = None
            if was and not up:
                if hasattr(env, "note_death"):
                    env.note_death(i, 1 - i)
                ev[EV["died"] if i == 0 else EV["frag"]] += 1.0
            self.alive[i] = up
        # the items' clocks (the game's respawn times; a demo's snapshot overrides what it shows)
        back_now = []
        if env.nI:
            was_up = self.item_up.copy()
            self.item_back = np.maximum(0.0, self.item_back - DT)
            self.item_up |= (self.item_back <= 0.0)
            for seat, k in taken:
                if k >= 0:
                    self.item_up[k] = False
                    self.item_back[k] = float(env.item_def[k][2])
            if items is not None:
                up_, seen_ = items
                self.item_up = np.where(seen_, up_, self.item_up)
                self.item_back = np.where(seen_ & up_, 0.0, self.item_back)
            back_now = np.nonzero(self.item_up & ~was_up)[0]
        if not me.alive:                                     # (the plugin: both filled, nothing seen, the clocks go on)
            self._fill(0, me)
            self._fill(1, en)
            env.visible[:] = False
            if hasattr(env, "v02_took"):
                for name in ("v02_bt", "v02_ht", "v02_took", "v02_by"):
                    setattr(env, name, np.minimum(getattr(env, name) + E.DT, 99.0).astype(np.float32))
                env.v02_loud = (env.v02_loud * (1.0 - E.DT / E.V02_LOUD_T)).astype(np.float32)
            if getattr(E, "EN_STACK", False) and hasattr(env, "_es_update"):
                env._es_update()
            if env.nI:
                env.item_up[0] = self.item_up
                env.item_t[0] = np.minimum(60.0, self.item_back)
            return None
        self._fill(0, me)
        self._fill(1, en)
        # what he hears: running steps, jumps and landings, shots (the other player's only while present)
        st_ = env.state
        gr_ = st_[:, 6] > 0.5
        noisy = gr_ & (np.hypot(st_[:, 3], st_[:, 4]) > 200.0)
        ofire_ = bool(en.fire) and en.w != E.WEAPONS.index("g") and en.present
        if hasattr(env, "note_noise"):
            was_ = self.ground_was
            hop_ = (gr_ != was_) if was_ is not None else np.zeros(len(gr_), bool)
            if was_ is not None:
                ev[EV["jumped"]] += float(was_[0] and not gr_[0])
                ev[EV["landed"]] += float((not was_[0]) and gr_[0] and self.vz_was < -LAND_VZ)   # (from a fall: falling fast)
            self.ground_was = gr_.copy()
            self.vz_was = float(me.vel[2])
            steps_ = noisy & ~env.duck
            myshot = bool(me.fire) and me.w != E.WEAPONS.index("g")
            shot_ = np.array([myshot, ofire_], bool)
            heard_ = shot_ | hop_ | steps_
            heard_[0] = False
            heard_[1] &= en.present
            env.hear(heard_)
            env.note_noise(shot_, hop_, steps_)
            if heard_[1] and np.linalg.norm(st_[1, :3] - st_[0, :3]) < E.EAR_RANGE:
                ev[EV["heard"]] = 1.0                        # (a flag: any sound of his in the tick)
        # projectiles and items into the simulator
        env.ra[:] = False
        cnt = [0, 0]
        for seat, kind, p_, v_, age in missiles:
            k = cnt[seat]
            if k >= E.K:
                continue
            env.rp[seat, k], env.rv[seat, k], env.ra[seat, k] = p_, v_, True
            if hasattr(env, "rw"):
                env.rw[seat, k] = kind
            if hasattr(env, "rage"):
                env.rage[seat, k] = age
            cnt[seat] += 1
        if env.nI:
            for k in back_now:
                if hasattr(env, "note_respawn"):
                    env.note_respawn(int(k))
                c = self.it_cls[k]
                if np.linalg.norm(env.state[0, :3] - env.item_pos[k]) < E.HEAR_EVT:
                    lab = env.item_def[k][4]
                    j = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab in ("YA", "GA") else 3 if env.item_def[k][0] == "wp" else -1
                    if j >= 0:
                        ev[EV["resp_MH"] + j] += 1.0
            env.item_up[0] = self.item_up
            env.item_t[0] = np.minimum(60.0, self.item_back)
            for seat, k in taken:
                if k < 0 or seat not in (0, 1):
                    continue
                if hasattr(env, "note_take"):
                    env.note_take(seat, int(k))
                lab = env.item_def[k][4]
                if hasattr(env, "note_pickup") and lab in ("MH", "RA"):
                    env.note_pickup(seat, 0 if lab == "MH" else 1)
                c = int(self.it_cls[k])
                if seat == 0:
                    ev[EV["took_MH"] + c] += 1.0
                    want = E.INTENTS[int(env.intent[0])]            # (took_chosen)
                    lab2 = lab if lab else (E.WEAPONS[int(env.item_def[k][1])].upper() if env.item_def[k][0] == "wp" else None)
                    if lab2 is not None and (lab2 == want or (lab2 == "YA" and want == "YA2")):
                        env.intent_done[0] = True
                else:
                    kd, val = env.item_def[k][0], env.item_def[k][1]
                    big = 0 if lab == "MH" else 1 if lab == "RA" else 2 if lab in ("YA", "GA") else 3 if kd == "wp" else None
                    if big is not None:
                        env._hear(0, np.array([1]), big)
                    near_ = np.linalg.norm(env.state[1, :3] - env.state[0, :3]) < E.HEAR_EVT
                    if near_ or bool(env.visible[0]):
                        ev[EV["en_took_MH"] + c] += 1.0
        # the game's clock and score (a whole-games network: clock_frame)
        env.kind[0] = E.NORMAL
        if hasattr(env, "clock_t"):
            env.clock_t = np.full(env.n, clock_t, np.float32)
            env.clock_game = np.ones(env.n, bool)
        env.round_t[0] = clock_t
        if hasattr(env, "v02_left"):
            env.v02_left = min(1.0, max(0.0, 1.0 - clock_t / 600.0))
        env.frags_r[:] = scores
        env.duck[1] = en.duck
        env.snd_t += E.DT
        if hasattr(env, "resp_t"):
            env.resp_t += E.DT
        self._intent_release()
        if hasattr(env, "note_shots"):                       # the enemy's shots: the fire button and the weapon's refire
            env.shot_t += E.DT
            env.trail_t += E.DT
            self.last_shot[1] += DT
            if ofire_ and self.last_shot[1] >= float(E.W_REFIRE[en.w]) - 1e-6:
                env.note_shots(np.array([1]))
                self.last_shot[1] = 0.0
        po = self.prev_opp
        if po is not None and en.alive and en.present:
            if en.fire:
                env._hear(1, np.array([1]))
            if po[1] > 0.5 and env.state[1, 6] < 0.5 and env.state[1, 5] > 100:
                env._hear(2, np.array([1]))
            if np.linalg.norm(env.state[1, :3] - po[0]) > 200:
                env._hear(3, np.array([1]))
        self.prev_opp = (env.state[1, :3].copy(), float(env.state[1, 6])) if en.present else None
        env.fb[0] = self.fb_next
        self._senses(en.present)
        ob = env.observe()[0].copy()
        # his intention for the next frames (the plugin: after observe, from the network's choice)
        if hasattr(env, "intend") and self.intent_mode == "rule":
            env.intend(np.asarray(env.intent_rule(), np.int64), np.arange(env.n) == 0)
        elif hasattr(env, "intend"):
            env.intend(np.zeros(env.n, np.int64), np.arange(env.n) == 0)
        # the hit feedback for the next frame, his damage this life, the enemy's pain
        opos, pos = env.state[1, :3], env.state[0, :3]
        ang = math.atan2(opos[1] - pos[1], opos[0] - pos[0]) - math.radians(float(env.yaw[0]))
        self.fb_next = np.array([min(dealt / 100.0, 2.0), min(took / 100.0, 2.0), math.sin(ang) * (took > 0), math.cos(ang) * (took > 0)], np.float32)
        env.dmg_life[0] += dealt
        es_ = getattr(E, "EN_STACK", False) and hasattr(env, "note_dealt")
        if es_ and dealt > 0 and en.alive:
            env.note_dealt(0, 1, dealt)
        if took > 0 and hasattr(env, "note_hit") and getattr(env, "flinch_on", False):
            env.note_hit(0, took)
        if hasattr(env, "pain_t"):
            env.pain_t += E.DT
            if dealt > 0 and en.alive and float(np.linalg.norm(opos - pos)) < E.HEAR_EVT:
                env.pain_t[0], env.pain_b[0] = 0.0, min(3, int(en.hp) // 25)
                ev[EV["pain"]] += 1.0
        ev[EV["dealt"]] += dealt / 100.0
        ev[EV["taken"]] += took / 100.0
        ev[EV["seen"]] += float(env.visible[0])
        if self.w_last is not None and me.w != self.w_last:
            ev[EV["wswitch"]] += 1.0
        self.w_last = me.w
        self.ev_frames += 1
        return ob

    def _intent_release(self):
        """the plugin's intent_release(): the chosen item gone, a holding place reached, the enemy in view"""
        env, E = self.env, self.E
        R_ = getattr(env, "route", None)
        if R_ is None or not hasattr(env, "intent_gone"):
            return
        s = env.state
        node = R_.locate(s[:, :3])
        gi_ = env._trip_goal(env.intent, node) if hasattr(env, "_trip_goal") else np.array(env.intent_gi)[env.intent]
        valid = gi_ >= 0
        g_ = np.maximum(gi_, 0)
        phi = np.where(valid, R_.T[g_, node] + np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0, 0.0)
        it_ = np.array(env.route_item)[np.minimum(g_, len(env.route_item) - 1)]
        soon = env.item_up[0, it_] | (env.item_t[0, it_] < phi + 5.0) | (env.intent >= getattr(E, "EN_INTENT", 1 << 30))
        gone = valid & ~soon & (env.intent > 0)
        if getattr(env, "hold_n", 0):
            hd_ = env.intent >= E.HOLD_INTENT
            env.note_holds()
            gone = gone | (hd_ & (~valid | (R_.T[g_, node] >= 1e8)))
        mine_ = np.arange(env.n) == 0
        if getattr(E, "EN_ON", False):
            en_ = env.intent == E.EN_INTENT
            env.intent_done = env.intent_done | (en_ & np.asarray(env.visible, bool)[:len(en_)] & mine_)
            gone = gone | (en_ & ~valid)
        env.intent_gone = np.where(mine_, gone, False)


# ------------------------------------------------------------------------------------------------------------------- labels
class Timeline:
    """per server frame (living or not): time, who is followed and his place, who his enemy is and his place (known or
    not); the followed players' reaches (pickups of the intention list's items; the holding places are found from the
    places); the deaths; the games with the final margin of each player. A session's seats are 0 (him) and 1."""

    def __init__(self):
        self.t, self.who, self.me_pos, self.en_who, self.en_pos, self.en_known, self.me_alive = [], [], [], [], [], [], []
        self.reach = []                                      # (time, who, INTENTS index)
        self.deaths = []                                     # (time, who)
        self.games = []                                      # (t0, t1, {who: final margin} or None)

    def add(self, t, who, me_pos, en_who, en_pos, en_known, me_alive):
        self.t.append(t)
        self.who.append(who)
        self.me_pos.append(me_pos)
        self.en_who.append(en_who)
        self.en_pos.append(en_pos)
        self.en_known.append(en_known)
        self.me_alive.append(me_alive)

    def arrays(self):
        return (np.asarray(self.t, np.float64), np.asarray(self.who, np.int64), np.asarray(self.me_pos, np.float32).reshape(-1, 3),
                np.asarray(self.en_who, np.int64), np.asarray(self.en_pos, np.float32).reshape(-1, 3),
                np.asarray(self.en_known, bool), np.asarray(self.me_alive, bool))


def holds_reached(env, E, t, who, pos, alive):
    """(time, who, INTENTS index) where the followed player stood at a holding place for HOLD_DWELL s (the stay's start)"""
    out = []
    hp = getattr(env, "hold_pos", np.zeros((0, 3)))
    if not len(hp) or not len(t):
        return out
    d = pos[:, None, :] - hp[None]
    at = (np.hypot(d[..., 0], d[..., 1]) < E.HOLD_R) & (np.abs(d[..., 2]) < E.HOLD_Z) & alive[:, None]
    need = int(round(HOLD_DWELL / DT))
    for j in range(len(hp)):
        a = at[:, j]
        k = 0
        while k < len(a):
            if not a[k]:
                k += 1
                continue
            m = k
            while m < len(a) and a[m] and who[m] == who[k]:
                m += 1
            if m - k >= need:
                out.append((float(t[k]), int(who[k]), E.HOLD_INTENT + j))
            k = m
    return out


def tick_labels(env, E, tl, tick_t, tick_who, tick_en, tick_bel, tick_bel_ok):
    """the labels of every tick (see the top)"""
    T = len(tick_t)
    t, who, me_pos, en_who, en_pos, en_known, me_alive = tl.arrays()
    sw = t[1:][who[1:] != who[:-1]]                          # the moments another player is followed (a demo of a spectator)
    reach = sorted(tl.reach + holds_reached(env, E, t, who, me_pos, me_alive))
    target = np.full(T, -1, np.int16)
    for c in np.unique(tick_who):
        rr = [r for r in reach if r[1] == c]
        rt = np.array([r[0] for r in rr], np.float64)
        rc = np.array([r[2] for r in rr], np.int64)
        dth = np.sort(np.array([d_[0] for d_ in tl.deaths if d_[1] == c], np.float64))
        for j in np.nonzero(tick_who == c)[0]:
            tt = tick_t[j]
            k = np.searchsorted(rt, tt, side="right")
            if k < len(rt) and rt[k] - tt <= TARGET_HORIZON:
                nd = np.searchsorted(dth, tt, side="right")
                ns = np.searchsorted(sw, tt, side="right")
                if (nd >= len(dth) or dth[nd] > rt[k]) and (ns >= len(sw) or sw[ns] > rt[k]):
                    target[j] = rc[k]
    en_cls = np.full((T, len(AHEAD)), -1, np.int16)
    en_at = np.full((T, len(AHEAD), 3), np.nan, np.float32)
    for a, sec in enumerate(AHEAD):
        q = np.searchsorted(t, tick_t + sec - 1e-6)
        ok = q < len(t)
        q = np.minimum(q, len(t) - 1)
        ok &= np.abs(t[q] - (tick_t + sec)) < 0.2            # (a gap in the recording: unknown)
        mine = who[q] == tick_en                             # the enemy of the tick is the one followed then: his place is known
        theirs = (en_who[q] == tick_en) & en_known[q]        # ... or he is the other one and was sent
        p = np.where(mine[:, None], me_pos[q], en_pos[q])
        alive = np.where(mine, me_alive[q], True)
        ok &= (mine | theirs) & alive
        cls = landmark(env, E, p)
        en_cls[:, a] = np.where(ok & (cls >= 0), cls, -1)
        en_at[:, a] = np.where(ok[:, None], p, np.nan)
    bel_cls = np.where(np.asarray(tick_bel_ok, bool), landmark(env, E, np.asarray(tick_bel, np.float32)), -1).astype(np.int16)
    win = np.full(T, -1, np.int8)
    for t0, t1, margins in tl.games:
        if not margins:
            continue
        for c, m in margins.items():
            win[(tick_t >= t0) & (tick_t <= t1) & (tick_who == c)] = band(m)
    return dict(target=target, en_cls=en_cls, en_pos=en_at, bel_cls=bel_cls, win=win)


class Recorder:
    """collects a shard: the inputs of each living frame, the ticks, the baselines at each tick"""

    def __init__(self, feeder):
        self.f = feeder
        self.obs, self.done, self.tick, self.tick_t, self.ev = [], [], [], [], []
        self.rule, self.bel, self.bel_ok, self.intent_in, self.who, self.en = [], [], [], [], [], []

    def push(self, ob, t, who=0, en=1):
        env, E = self.f.env, self.f.E
        self.obs.append(ob.astype(np.float16))
        self.done.append(False)
        g = len(self.obs) - 1
        if (g + 1) % EVERY == 0:
            self.tick.append(g)
            self.tick_t.append(t)
            self.who.append(who)
            self.en.append(en)
            self.ev.append(self.f.take_events())
            self.rule.append(int(env.intent_rule()[0]))
            bel = getattr(env, "v02_bel", None)
            bok = getattr(env, "v02_bel_ok", None)
            self.bel.append(np.asarray(bel[0], np.float32) if bel is not None else np.zeros(3, np.float32))
            self.bel_ok.append(bool(bok[0]) if bok is not None else False)
            self.intent_in.append(int(env.intent[0]))

    def cut(self):
        """his memory is cleared after the last frame (a new game, a cut in a demo)"""
        if self.done:
            self.done[-1] = True

    def save(self, path, tl, meta):
        env, E = self.f.env, self.f.E
        if len(self.tick) < 4:
            return None
        lab = tick_labels(env, E, tl, np.asarray(self.tick_t, np.float64), np.asarray(self.who, np.int64),
                          np.asarray(self.en, np.int64), self.bel, self.bel_ok)
        arr = dict(obs=np.stack(self.obs), done=np.asarray(self.done, bool), tick=np.asarray(self.tick, np.int32),
                   tick_t=np.asarray(self.tick_t, np.float64), ev=np.stack(self.ev).astype(np.float16),
                   rule=np.asarray(self.rule, np.int16), intent_in=np.asarray(self.intent_in, np.int16),
                   bel=np.asarray(self.bel, np.float32), **lab)
        meta = dict(meta, n_frames=len(self.obs), n_ticks=len(self.tick), every=EVERY, ahead=AHEAD, intents=list(E.INTENTS),
                    ev_names=EV_NAMES, bands="<=-5,-4..-1,0,1..4,>=5")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        np.savez_compressed(path, meta=json.dumps(meta), **arr)
        return path


# --------------------------------------------------------------------------------------------------------------- demos
# the demo's item numbers (events_reader: E["item_ids"]) -> the simulator's class names (ITEM_DEFS)
DEMO_ITEMS = {"ItemHealthSmall": "item_health_small", "ItemHealth": "item_health", "ItemHealthLarge": "item_health_large",
              "ItemHealthMega": "item_health_mega", "ItemArmorShard": "item_armor_shard", "ItemArmorJacket": "item_armor_jacket",
              "ItemArmorCombat": "item_armor_combat", "ItemArmorBody": "item_armor_body",
              "WeaponRocketLauncher": "weapon_rocketlauncher", "WeaponRailgun": "weapon_railgun", "WeaponLightningGun": "weapon_lightning",
              "WeaponShotgun": "weapon_shotgun", "WeaponGrenadeLauncher": "weapon_grenadelauncher", "WeaponPlasmaGun": "weapon_plasmagun",
              "WeaponHMG": "weapon_hmg", "AmmoRockets": "ammo_rockets", "AmmoSlugs": "ammo_slugs", "AmmoLightning": "ammo_lightning",
              "AmmoBullets": "ammo_bullets", "AmmoShells": "ammo_shells", "AmmoGrenades": "ammo_grenades", "AmmoCells": "ammo_cells",
              "AmmoHMG": "ammo_hmg", "AmmoPack": "ammo_pack"}


def parse_demo(path, tmp):
    exe = os.environ.get("DEMODUMP") or os.path.join(ROOT, "tools", "demodump", "demodump.exe")
    b, js, ev = (os.path.join(tmp, n) for n in ("d.bin", "d.json", "d.events.json"))
    for p in (b, js, ev):
        if os.path.exists(p):
            os.remove(p)
    subprocess.run([exe, path, b, js, ev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    import demo_reader as D
    sys.path.insert(0, os.path.join(ROOT, "tools", "demodump"))
    import events_reader as R
    d = D.load(b)
    Ev = R.load(ev) if os.path.exists(ev) else None
    return d, Ev, R


def demo_games(Ev, R, N):
    """the games of a demo: [(first snapshot, intermission snapshot or None)] (a game starts where the level's start time
    becomes non-zero after warmup; a pause only moves it), the level's start time in force at every snapshot (ms, 0:
    warmup), and the score changes [(snapshot, client, +-1)]"""
    lst = np.zeros(N, np.int64)
    starts = []
    if Ev is None:
        return [], lst, []
    prev = 0
    for snap, s in R.config_string(Ev, "LevelStartTime"):
        try:
            v = int(s) if s else 0
        except ValueError:
            v = 0
        snap = min(int(snap), N - 1)
        lst[snap:] = v
        if v and not prev:
            starts.append(snap)
        prev = v
    ends = [min(int(snap), N - 1) for snap, s in R.config_string(Ev, "Intermission") if s and s != "0"]
    games = []
    for k, s0 in enumerate(starts):
        nxt = starts[k + 1] if k + 1 < len(starts) else N
        e = next((x for x in ends if s0 < x <= nxt), None)
        games.append((s0, e))
    ch = [(int(a), int(b), int(c)) for a, b, c in R.score_changes(Ev)]
    return games, lst, ch


def demo_pickups(Ev, R):
    """snapshot -> [(client, class name, place)] (the followed player's own and those the snapshots showed)"""
    out = {}
    if Ev is None:
        return out
    c = Ev["c"]
    names = {v: k for k, v in Ev["item_ids"].items()}
    seen = set()
    for r in R.rows(Ev, "ItemPickup"):
        snap, cl, it = int(r[c["snap"]]), int(r[c["number"]]), int(r[c["eventParm"]])
        if (snap, cl, it) in seen or cl < 0 or cl >= 64:
            continue
        seen.add((snap, cl, it))
        cls = DEMO_ITEMS.get(names.get(it, ""))
        if cls:
            out.setdefault(snap, []).append((cl, cls, np.array([r[c["pos_trBase_0"]], r[c["pos_trBase_1"]], r[c["pos_trBase_2"]]], np.float32)))
    return out


def nearest_item(env, E, cls, p, within=160.0):
    cand = [k for k in range(env.nI) if env.item_def[k] == E.ITEM_DEFS.get(cls)]
    if not cand:
        return -1
    k = min(cand, key=lambda k_: float(np.linalg.norm(env.item_pos[k_] - p)))
    return int(k) if float(np.linalg.norm(env.item_pos[k] - p)) < within else -1


def build_demo(spec, mp, path, out, intent_mode="rule", seed=1, max_frames=0):
    import demo_dataset as DS
    import demo_reader as D
    tmp = os.path.join(SCRATCH, "dd_{}".format(os.getpid()))
    os.makedirs(tmp, exist_ok=True)
    d, Ev, R = parse_demo(path, tmp)
    N = len(d["time"])
    if N < 800:
        return None, "short"
    t_ms = DS.exact_times(os.path.join(tmp, "d.bin"), d["time"])
    E, env = make_env(spec, mp, seed)
    names = E.WEAPONS
    NW = len(names)
    F = Feeder(E, env, intent_mode)
    rec = Recorder(F)
    tl = Timeline()
    wslot, aslot = DS.stat_layout(d)
    normal = int(np.bincount(d["pm_type"].clip(0, 15)).argmax())
    games, lst, changes = demo_games(Ev, R, N)
    picks = demo_pickups(Ev, R)
    in_game = np.zeros(N, bool)
    for s0, e in games:
        in_game[s0:(e if e is not None else N)] = True
    ps = d["ps"]
    me_cl = d["clientNum"]
    item_near = {}
    prev_cl, prev_t = None, None
    me, en = Player(NW), Player(NW)
    en_cl = -1
    en_seen = False
    score = {}
    ci = 0
    mi = d.get("missiles")
    g_cur = None
    for k in range(min(N, max_frames) if max_frames else N):
        tm = int(t_ms[k])
        cl = int(me_cl[k])
        playing = d["pm_type"][k] == normal
        gi = next((j for j, (s0, e) in enumerate(games) if s0 <= k and (e is None or k <= e)), None)
        game_new = gi is not None and gi != g_cur
        if gi != g_cur:
            score = {}
            if prev_cl is not None:
                rec.cut()
            g_cur = gi
        if prev_cl is not None and (cl != prev_cl or tm - prev_t > 1000):
            rec.cut()                                       # another player followed, or a gap: a new memory
            F.alive = [None, None]
            F.ground_was = None
        prev_cl, prev_t = cl, tm
        while ci < len(changes) and changes[ci][0] <= k:
            if gi is not None:
                score[changes[ci][1]] = score.get(changes[ci][1], 0) + changes[ci][2]
            if changes[ci][1] == cl and changes[ci][2] > 0:
                F.ev[EV["frag"]] += 1.0                     # (he fragged: his score went up)
            ci += 1
        s = d["stats"][k]
        alive_was = me.alive
        me.alive = bool(playing and s[0] > 0)
        me.pos, me.vel = d["origin"][k].astype(np.float32), d["velocity"][k].astype(np.float32)
        me.pitch, me.yaw = float(d["angles"][k][0]), float(d["angles"][k][1])
        hp_was = me.hp + me.armor
        me.hp, me.armor = float(max(s[0], 0)), float(s[aslot])
        bits = int(s[wslot])
        for q, nm in QLW.items():
            me.has[names.index(nm)] = bool(bits & (1 << q))
            me.ammo[names.index(nm)] = 0 if nm == "g" else max(0.0, float(d["ammo"][k][q]))
        me.w = names.index(QLW.get(int(d["weapon"][k]), "mg"))
        me.duck = bool(ps[k, D.PS["viewheight"]] < 20)
        me.fire = bool((int(ps[k, D.PS["eFlags"]]) & 0x100) or d["weaponstate"][k] == 3)
        me.ground = float(d["groundEntityNum"][k] != 1023)
        took = max(0.0, hp_was - (me.hp + me.armor)) if (me.alive and F.alive[0]) else 0.0
        en.present = False
        for row in d["players"][k]:
            if DS.is_enemy(row, cl):
                en.pos = np.array(row[2:5], np.float32)
                en.vel = np.array(row[5:8], np.float32)
                en.pitch, en.yaw = float(row[8]), float(row[9])
                en.w = names.index(QLW.get(int(row[11]), "mg"))
                en.fire = bool(int(row[12]) & 0x100)
                en.present = True
                en_cl = int(row[1])
                break
        en_seen |= en.present
        en.hp, en.armor = 100.0, 0.0
        en.has[:] = False
        en.has[[names.index("mg"), names.index("g"), en.w]] = True
        en.ammo[:] = 50.0
        en.alive = True                                     # (a dead enemy is not sent: he is away, not dead, to the senses)
        # items: those in the snapshot are there (a taken item is not sent); pickups from the demo's events
        seen_ = np.zeros(env.nI, bool)
        for it in d["items"][k]:
            key = (round(float(it[2])), round(float(it[3])), round(float(it[4])))
            idx = item_near.get(key)
            if idx is None:
                dd = np.linalg.norm(env.item_pos - np.array(key, np.float32), axis=1) if env.nI else np.array([1e9])
                idx = item_near[key] = int(dd.argmin()) if dd.min() < 48 else -1
            if idx >= 0 and (int(it[5]) & 0x80) == 0:
                seen_[idx] = True
        taken = []
        for c_, cls, p_ in picks.get(k, ()):
            idx = nearest_item(env, E, cls, p_)
            if idx < 0:
                continue
            seat = 0 if c_ == cl else 1 if (c_ == en_cl or en_cl < 0) else -1
            taken.append((seat, idx))
            if F.it_intent[idx] >= 0:
                tl.reach.append((tm / 1000.0, c_, int(F.it_intent[idx])))
        for seat, idx in taken:
            seen_[idx] = False
        # projectiles: number weapon trType trTime base3 delta3 otherEntityNum clientNum
        miss = []
        if mi is not None:
            kinds = {5: E.RL, 4: E.GL, 8: E.PG}
            for r in mi[k]:
                w_ = int(r[1])
                if w_ not in kinds:
                    continue
                age = max(0.0, (tm - float(r[3])) / 1000.0)
                p_ = np.array(r[4:7], np.float32) + np.array(r[7:10], np.float32) * age
                v_ = np.array(r[7:10], np.float32)
                if int(r[2]) == 5:                           # (TR_GRAVITY: a grenade)
                    p_[2] -= 0.5 * 800.0 * age * age
                    v_[2] -= 800.0 * age
                miss.append((0 if int(r[11]) == cl else 1, kinds[w_], p_, v_, age))
        if gi is not None and lst[k] > 0:
            clock = max(0.0, (tm - int(lst[k])) / 1000.0)
        else:
            clock = ((tm - int(t_ms[0])) / 1000.0) % 600.0
        sc = (score.get(cl, 0), sum(v for c_, v in score.items() if c_ != cl))
        if alive_was and not me.alive and F.alive[0]:
            tl.deaths.append((tm / 1000.0, cl))
        ob = F.frame(me, en, clock, sc, taken=taken, missiles=miss, dealt=0.0, took=took, items=(np.ones(env.nI, bool), seen_),
                     game_new=game_new)
        tl.add(tm / 1000.0, cl, me.pos.copy(), en_cl, en.pos.copy(), en.present, me.alive)
        if ob is not None:
            rec.push(ob, tm / 1000.0, cl, en_cl)
    # the games' final margins, for every player who scored or was followed; checked against the followed player's own
    # score (PERS_SCORE) at the intermission
    n_ok = 0
    for s0, e in games:
        if e is None:
            continue
        fs = {}
        for snap, c_, v in changes:
            if s0 <= snap <= e:
                fs[c_] = fs.get(c_, 0) + v
        c_end = int(me_cl[e])
        if int(ps[e, D.PS["persistant"]]) != fs.get(c_end, 0):
            tl.games.append((t_ms[s0] / 1000.0, t_ms[e] / 1000.0, None))
            continue
        pl = set(fs) | set(int(x) for x in np.unique(me_cl[s0:e + 1]))
        tl.games.append((t_ms[s0] / 1000.0, t_ms[e] / 1000.0,
                         {c_: fs.get(c_, 0) - sum(v for o_, v in fs.items() if o_ != c_) for c_ in pl}))
        n_ok += 1
    stem = os.path.splitext(os.path.basename(path))[0]         # (the file's name has the players' names: only a hash of it is kept)
    meta = dict(source="demo", map=mp, name="demo_" + hashlib.sha1(stem.encode("utf-8", "replace")).hexdigest()[:12], env=spec["env"], intent=intent_mode, games=len(games), games_known=n_ok,
                followed=int(len(np.unique(me_cl))), enemy_ever=bool(en_seen))
    shutil.rmtree(tmp, ignore_errors=True)
    return rec.save(out, tl, meta), "ok"


# ------------------------------------------------------------------------------------------------------------- sessions
def unpack(archive, into):
    """a session archive into a scratch folder (read only on T:); -> the session folder"""
    with tarfile.open(archive, "r:gz") as tf:
        names = [m for m in tf.getmembers() if m.isfile() and os.path.basename(m.name) in ("meta.json", "frames.csv", "events.jsonl", "missiles.csv")]
        for m in names:
            if ".." in m.name or m.name.startswith(("/", "\\")):
                continue
            tf.extract(m, into, filter="data")
    sess = os.path.join(into, os.path.basename(archive).replace(".tar.gz", ""))
    return sess


def read_frames(sess):
    rows = list(csv.reader(open(os.path.join(sess, "frames.csv"))))
    head = rows[0]
    c = {k: i for i, k in enumerate(head)}
    body = [r for r in rows[1:] if len(r) == len(head)]
    return c, body


def read_events(sess):
    out = []
    p = os.path.join(sess, "events.jsonl")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def session_games(events):
    """the real games of a 1v1 session: [(t0, t1, margin for bobby, margin for the person)] from player_stats (a game
    that was played, not warmup, not aborted) and the running score of the death events"""
    deaths = [(e["t"], int(e.get("bobby", 0)), int(e.get("opp", 0))) for e in events if e.get("event") == "death"]

    def score_at(t):
        b = o = 0
        for tt, bb, oo in deaths:
            if tt <= t:
                b, o = bb, oo
        return b, o
    games = []
    for e in events:
        if e.get("event") == "player_stats" and not e.get("warmup") and not e.get("aborted") and float(e.get("play_time") or 0) >= DUEL_WINDOW_MIN:
            t1 = float(e["t"])
            t0 = t1 - float(e["play_time"])
            if any(abs(g[1] - t1) < 5 for g in games):       # (one line per player)
                continue
            b0, o0 = score_at(t0)
            b1, o1 = score_at(t1)
            games.append((t0, t1, (b1 - b0) - (o1 - o0), (o1 - o0) - (b1 - b0)))
    return games


def build_session(spec, sess, seat, out, intent_mode="rule", seed=1, max_frames=0):
    meta_s = json.load(open(os.path.join(sess, "meta.json")))
    mp = meta_s["map"]
    if meta_s.get("opponent") not in ("human", "spar") or meta_s.get("kind") == "ffa":
        return None, "not 1v1"
    c, body = read_frames(sess)
    if len(body) < 2000:
        return None, "short"
    events = read_events(sess)
    games = session_games(events)
    E, env = make_env(spec, mp, seed)
    names = E.WEAPONS
    NW = len(names)
    qln = {5: "rl", 7: "rg", 6: "lg", 2: "mg", 3: "sg", 4: "gl", 8: "pg", 14: "hmg", 1: "g"}
    F = Feeder(E, env, intent_mode)
    rec = Recorder(F)
    tl = Timeline()
    me_p, en_p = ("b", "o") if seat == "b" else ("o", "b")
    me_who, en_who = ("bobby", "opp") if seat == "b" else ("opp", "bobby")
    pick = [(float(e["t"]), e["item"], e.get("by")) for e in events if e.get("event") == "pickup"]
    pi = 0
    miss_rows = {}
    mp_path = os.path.join(sess, "missiles.csv")
    if os.path.exists(mp_path):
        for r in csv.DictReader(open(mp_path)):
            miss_rows.setdefault(r["t"], []).append(r)
    born = {}
    me, en = Player(NW), Player(NW)
    owned = [set(), set()]
    tot = [None, None]
    score = [0, 0]
    t_sess0 = float(body[0][c["t"]])
    clock0 = t_sess0
    game_i = None
    alive_prev = [None, None]

    def fill(p, pre, k_own):
        r = row
        p.pos = np.array([float(r[c[pre + "_x"]]), float(r[c[pre + "_y"]]), float(r[c[pre + "_z"]])], np.float32)
        p.vel = np.array([float(r[c[pre + "_vx"]]), float(r[c[pre + "_vy"]]), float(r[c[pre + "_vz"]])], np.float32)
        p.pitch, p.yaw = float(r[c[pre + "_pitch"]]), float(r[c[pre + "_yaw"]])
        p.hp, p.armor = float(r[c[pre + "_health"]]), float(r[c[pre + "_armor"]])
        p.alive = p.hp > 0 and not (p.pos == 0).all()
        p.hp = max(0.0, p.hp)
        wn = qln.get(int(float(r[c[pre + "_weapon"]])), "mg")
        p.w = names.index(wn)
        if not p.alive:
            owned[k_own].clear()
        owned[k_own].update(("mg", "g", wn))
        p.has[:] = False
        p.ammo[:] = 0.0
        for nm in owned[k_own]:
            p.has[names.index(nm)] = True
            p.ammo[names.index(nm)] = TYPICAL_AMMO.get(nm, 0.0)
        for nm in ("rl", "rg", "lg"):
            a_ = float(r[c["{}_ammo_{}".format(pre, nm)]])
            p.has[names.index(nm)] = a_ >= 0
            p.ammo[names.index(nm)] = max(0.0, a_)
        p.duck = float(r[c[pre + "_up"]]) < 0
        p.fire = float(r[c[pre + "_fire"]]) > 0
        p.present = True
        p.ground = None

    for fi, row in enumerate(body[:max_frames] if max_frames else body):
        t = float(row[c["t"]])
        fill(me, me_p, 0)
        fill(en, en_p, 1)
        # the game's clock: a real game's own, else a free clock of 600 s from the session's start (as clock_frame)
        gi = next((j for j, g in enumerate(games) if g[0] <= t <= g[1]), None)
        game_new = False
        if gi != game_i:
            if gi is not None:
                game_new = True
                clock0 = games[gi][0]
            else:
                clock0 = t
            score = [0, 0]
            rec.cut()
            game_i = gi
        elif t - clock0 > 600.0 and gi is None:
            clock0 = t
            score = [0, 0]
            rec.cut()
        clock = t - clock0
        # damage this frame (health + armor drops of 3 or more: the plugin's log_frame), deaths and the score
        dmg = [0.0, 0.0]
        for i, p in enumerate((me, en)):
            tt = max(0.0, p.hp) + p.armor                    # (the plugin's log_frame: a drop of 3 or more; forgotten at a respawn)
            if p.alive and not alive_prev[i]:
                tot[i] = None
            if tot[i] is not None and tot[i] - tt >= 3 and tot[i] > 0:
                dmg[i] = tot[i] - tt
            tot[i] = tt
            if alive_prev[i] and not p.alive:
                score[1 - i] += 1
                if i == 0:
                    tl.deaths.append((t, 0))
            alive_prev[i] = p.alive
        taken = []
        while pi < len(pick) and pick[pi][0] <= t:
            _, cls, by = pick[pi]
            pi += 1
            st_ = 0 if by == me_who else 1 if by == en_who else -1
            if st_ < 0 or cls not in E.ITEM_DEFS:
                continue
            pp = (me if st_ == 0 else en).pos
            cand = [k for k in range(env.nI) if env.item_def[k] == E.ITEM_DEFS[cls]]
            if not cand:
                continue
            k = min(cand, key=lambda k_: float(np.linalg.norm(env.item_pos[k_] - pp)))
            taken.append((st_, int(k)))
            if st_ == 0 and F.it_intent[k] >= 0:
                tl.reach.append((t, 0, int(F.it_intent[k])))
        miss = []
        kinds = {5: E.RL, 4: E.GL, 8: E.PG}
        live_ = set()
        for r in miss_rows.get(row[c["t"]], []):
            w_ = int(r["weapon"])
            who = int(r["owner"])
            if w_ not in kinds or who not in (0, 1):
                continue
            seat_ = 0 if (who == 0) == (seat == "b") else 1
            num = int(r["num"])
            live_.add(num)
            age = t - born.setdefault(num, t)
            miss.append((seat_, kinds[w_], np.array([float(r["x"]), float(r["y"]), float(r["z"])], np.float32),
                         np.array([float(r["vx"]), float(r["vy"]), float(r["vz"])], np.float32), age))
        for num in [n_ for n_ in born if n_ not in live_]:
            del born[num]
        ob = F.frame(me, en, clock, (score[0], score[1]), taken=taken, missiles=miss, dealt=dmg[1],
                     took=dmg[0], items=None, game_new=game_new)
        tl.add(t, 0, me.pos.copy(), 1, en.pos.copy(), en.alive, me.alive)
        if ob is not None:
            rec.push(ob, t)
    for g in games:
        tl.games.append((g[0], g[1], {0: g[2] if seat == "b" else g[3]}))
    meta = dict(source="session", map=mp, name=os.path.basename(sess), seat=seat, policy=meta_s.get("policy"), env=spec["env"],
                intent=intent_mode, games=len(games))
    return rec.save(out, tl, meta), "ok"


# --------------------------------------------------------------------------------------------------------- input logs
def build_inputs(sess, out, spec=None, seed=1):
    """the plugin's input logs of one session (Bobby's seat): the inputs as given; the labels from frames.csv and
    events.jsonl of the same session, by time"""
    files = sorted(glob.glob(os.path.join(sess, "inputs_*.npz")))
    if not files:
        return None, "no input logs"
    zs = [np.load(f) for f in files]
    t = np.concatenate([z["t"] for z in zs]).astype(np.float64)
    frame = np.concatenate([z["frame"] for z in zs]).astype(np.int64)
    obs = np.concatenate([z["obs"] for z in zs]).astype(np.float16)
    h = np.concatenate([z["h"] for z in zs]).astype(np.float16)
    acts = np.concatenate([z["acts"] for z in zs]).astype(np.int16)
    meta_s = json.load(open(os.path.join(sess, "meta.json")))
    mp = meta_s["map"]
    if spec is None:
        spec = dict(env=meta_s.get("env") or "duel_env_ffa", env_vars={}, react_ms=100.0, acquire_ms=200.0, obs_dim=obs.shape[1], group=2)
    E, env = make_env(spec, mp, seed)
    c, body = read_frames(sess)
    events = read_events(sess)
    games = session_games(events)
    tl = Timeline()
    alive_prev = None
    for row in body:
        tt = float(row[c["t"]])
        bp = np.array([float(row[c["b_x"]]), float(row[c["b_y"]]), float(row[c["b_z"]])], np.float32)
        op = np.array([float(row[c["o_x"]]), float(row[c["o_y"]]), float(row[c["o_z"]])], np.float32)
        ba, oa = float(row[c["b_health"]]) > 0, float(row[c["o_health"]]) > 0
        tl.add(tt, 0, bp, 1, op, oa, ba)
        if alive_prev and not ba:
            tl.deaths.append((tt, 0))
        alive_prev = ba
    for e in events:
        if e.get("event") == "pickup" and e.get("by") == "bobby" and e.get("item") in E.ITEM_DEFS:
            tt, _, bp_, _, _, _, _ = tl.arrays()
            q = min(np.searchsorted(tt, e["t"]), len(tt) - 1)
            cand = [k for k in range(env.nI) if env.item_def[k] == E.ITEM_DEFS[e["item"]]]
            if cand:
                k = min(cand, key=lambda k_: float(np.linalg.norm(env.item_pos[k_] - bp_[q])))
                it_intent, _ = item_classes(env, E)
                if it_intent[k] >= 0:
                    tl.reach.append((float(e["t"]), 0, int(it_intent[k])))
    for g in games:
        tl.games.append((g[0], g[1], {0: g[2]}))
    # the baselines: the belief inputs are in the logged inputs (v0.2's "believed" group), the rule is not logged
    bel_ok = np.zeros(len(t), bool)
    bel = np.zeros((len(t), 3), np.float32)
    ix = belief_cols(E)
    if ix is not None:
        # (the believed place is in his own frame of reference: turned back with his logged position and view)
        tt_, _, bpos, _, _, _, _ = tl.arrays()
        q = np.minimum(np.searchsorted(tt_, t), len(tt_) - 1)
        yaw = np.array([float(body[min(j, len(body) - 1)][c["b_yaw"]]) for j in q], np.float32)
        bel, bel_ok = belief_world(obs.astype(np.float32), ix, bpos[q], yaw)
    lab = tick_labels(env, E, tl, t, np.zeros(len(t), np.int64), np.ones(len(t), np.int64), bel, bel_ok)
    arr = dict(obs=obs, h_in=h, acts=acts, done=np.zeros(len(t), bool), tick=np.arange(len(t), dtype=np.int32), tick_t=t,
               frame=frame, ev=np.zeros((len(t), N_EV), np.float16), rule=np.full(len(t), -1, np.int16),
               intent_in=acts[:, 10].astype(np.int16) if acts.shape[1] > 10 else np.full(len(t), -1, np.int16), **lab)
    meta = dict(source="inputs", map=mp, name=os.path.basename(sess), seat="b", env=spec["env"], n_frames=len(t), n_ticks=len(t),
                every=1, ahead=AHEAD, intents=list(E.INTENTS), ev_names=EV_NAMES, note="one row a tick; h_in is the memory he answered the row from; no events (not logged), no rule")
    np.savez_compressed(out, meta=json.dumps(meta), **arr)
    return out, "ok"


def belief_cols(E):
    """the input columns of v0.2's belief: believes, where (forward, left, up: x 3), how old (the trainer's BEL_IX)"""
    if getattr(E, "N_V02", 0) <= 0:
        return None
    o_ = E.OBS_DIM - getattr(E, "N_B3", 0) - getattr(E, "N_B2", 0) - getattr(E, "N_ES", 0) - E.N_V02 + E.V02_GAME + E.V02_POS
    return np.array([o_, o_ + 1, o_ + 2, o_ + 3, o_ + 8], np.int64)


def belief_world(obs, ix, pos, yaw):
    """the believed place in world coordinates from the inputs (his frame: forward, left, up, scaled as _v02 writes them)"""
    ok = obs[:, ix[0]] > 0.5
    sc = 1500.0                                              # (_v02: rot(bel - pos) / 1500, clipped to +-2)
    f, l, u = obs[:, ix[1]] * sc, obs[:, ix[2]] * sc, obs[:, ix[3]] * sc
    yr = np.radians(yaw)
    x = pos[:, 0] + np.cos(yr) * f - np.sin(yr) * l
    y = pos[:, 1] + np.sin(yr) * f + np.cos(yr) * l
    return np.stack([x, y, pos[:, 2] + u], 1).astype(np.float32), ok


# -------------------------------------------------------------------------------------------------- the synthetic log
def synth(spec, sess, into, ck=None, seed=1):
    """an input log made from a session (none exist yet): the session is replayed for Bobby's seat, every 8th frame of
    inputs is written as the plugin would, with the memory of the hands run over the replayed frames (or zeros without
    --ck) and acts of zeros. Only the plumbing is tested by it."""
    os.makedirs(into, exist_ok=True)
    for n in ("meta.json", "frames.csv", "events.jsonl", "missiles.csv"):
        if os.path.exists(os.path.join(sess, n)):
            shutil.copy(os.path.join(sess, n), into)
    tmp = os.path.join(SCRATCH, "synth_{}.npz".format(os.getpid()))
    build_session(spec, sess, "b", tmp, seed=seed)
    with np.load(tmp) as z_:
        z = {k: z_[k] for k in z_.files}
    obs, tick_t = z["obs"], z["tick_t"]
    rows = z["tick"]
    hs = np.zeros((len(obs), 512), np.float16)
    if ck:
        import pretrain_head as H_
        hd = H_.Hands(ck)
        e, hh = hd.run(obs.astype(np.float32), z["done"])
        hs[1:] = hh[:-1]                                     # (the memory he answered each frame from: after the frame before)
    n = len(rows)
    acts = np.zeros((n, 13), np.int16)
    half = n // 2
    for j, sl in enumerate((slice(0, half), slice(half, n))):
        np.savez_compressed(os.path.join(into, "inputs_{:04d}.npz".format(j)), t=tick_t[sl], frame=rows[sl].astype(np.int64),
                            obs=obs[rows[sl]], h=hs[rows[sl]], acts=acts[sl])
    os.remove(tmp)
    return into


# ---------------------------------------------------------------------------------------------------------- reports
def show(paths):
    tot = {}
    for p in paths:
        z = np.load(p)
        m = json.loads(str(z["meta"]))
        T = len(z["tick"])
        r = dict(ticks=T, target=float((z["target"] >= 0).mean()), win=float((z["win"] >= 0).mean()),
                 bel=float((z["bel_cls"] >= 0).mean()), **{"en{:g}".format(a): float((z["en_cls"][:, j] >= 0).mean()) for j, a in enumerate(m["ahead"])})
        print("{} {} {} {}: obs {} {}, ticks {}, done {}; known: target {:.2f}, enemy +3/+10/+30 s {:.2f} {:.2f} {:.2f}, win {:.2f} (band {}), belief {:.2f}".format(
            m["source"], m["map"], m.get("seat", "-"), m["name"][:40], z["obs"].shape, z["obs"].dtype, T, int(z["done"].sum()),
            r["target"], r["en3"], r["en10"], r["en30"], r["win"], sorted(set(z["win"].tolist())), r["bel"]))
        tg = z["target"][z["target"] >= 0]
        if len(tg):
            ints = m["intents"]
            print("   targets:", {ints[k]: int((tg == k).sum()) for k in np.unique(tg)})
        evm = z["ev"].astype(np.float32).mean(0)
        print("   events per tick:", {k: round(float(evm[i]), 3) for i, k in enumerate(m["ev_names"]) if evm[i]})
        for k, v in r.items():
            tot.setdefault(k, []).append((v, T))
    if len(paths) > 1:
        print("all:", {k: round(sum(v * w for v, w in x) / max(1, sum(w for _, w in x)), 3) if k != "ticks" else sum(v for v, _ in x) for k, x in tot.items()})


def count():
    """the demos and the 1v1 sessions per map (the sessions' real games read from each archive's events.jsonl, in memory)"""
    root = demo_root()
    print("demos ({}):".format(root))
    for mp in sorted(os.listdir(os.path.join(root, "demos"))):
        fs = [f for f in glob.glob(os.path.join(root, "demos", mp, "*.dm_*")) if not f.endswith(".part")]
        print("  {:15s} {:5d}".format(mp, len(fs)))
    arch = os.environ.get("SESSIONS") or r"T:\quake-sessions\public"
    per = {}
    idx_min = {}                                             # (the minutes covered by frames: the archive's index, sessions.csv)
    if os.path.exists(os.path.join(arch, "sessions.csv")):
        for r_ in csv.DictReader(open(os.path.join(arch, "sessions.csv"))):
            idx_min[r_["session"]] = float(r_.get("minutes") or 0.0)
    for f in sorted(glob.glob(os.path.join(arch, "*.tar.gz"))):
        kind = os.path.basename(f).replace(".tar.gz", "").split("_")[-1]
        mp = os.path.basename(f).split("_")[1] if "_" in os.path.basename(f) else "?"
        if kind not in ("human", "spar"):
            continue
        g = 0
        mins = 0.0
        try:
            with tarfile.open(f, "r:gz") as tf:
                for m in tf.getmembers():
                    if m.name.endswith("events.jsonl"):
                        ev = [json.loads(l) for l in io.TextIOWrapper(tf.extractfile(m), encoding="utf-8", errors="replace") if l.strip()]
                        g = len(session_games(ev))
        except (OSError, tarfile.TarError, ValueError):
            continue
        mins = idx_min.get(os.path.basename(f).replace(".tar.gz", ""), 0.0)
        r = per.setdefault(mp, [0, 0, 0.0])
        r[0] += 1
        r[1] += g
        r[2] += mins
    print("1v1 sessions ({}): map, sessions, real games of {:.0f} min or more, minutes (sessions.csv)".format(arch, DUEL_WINDOW_MIN / 60))
    for mp, (n, g, mins) in sorted(per.items()):
        print("  {:15s} {:4d} {:4d} {:7.0f}".format(mp, n, g, mins))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("demos", "sessions", "inputs", "synth", "show", "count", "spec"))
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--files", nargs="*", default=None, help="demos: these demo files")
    ap.add_argument("--archives", nargs="*", default=[])
    ap.add_argument("--session", default=None)
    ap.add_argument("--into", default=None)
    ap.add_argument("--seat", default="both", choices=("b", "o", "both"))
    ap.add_argument("--ck", default=None, help="the hands' checkpoint (its simulator module and switches)")
    ap.add_argument("--spec", default=None, help="the same from a JSON file (head_data.py spec --ck ... --out spec.json)")
    ap.add_argument("--intent", default="rule", choices=("rule", "none"))
    ap.add_argument("--out", default=os.path.join(SCRATCH, "head_data"))
    ap.add_argument("--max-frames", type=int, default=0, help="a quick look: only the first this many frames of each source")
    a = ap.parse_args()
    if a.what == "show":
        return show(a.paths)
    if a.what == "count":
        return count()
    spec = env_spec(a.ck, a.spec) if (a.ck or a.spec) else None
    if a.what == "spec":
        json.dump(spec, open(a.out, "w"), indent=1)
        return
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    if a.what == "demos":
        files = a.files or sorted(f for f in glob.glob(os.path.join(demo_root(), "demos", a.map, "*.dm_*")) if not f.endswith(".part"))
        if not a.files and a.limit:
            files = files[:: max(1, len(files) // a.limit)][:a.limit]
        for i, f in enumerate(files):
            out = os.path.join(a.out, "demo_{}_{:04d}.npz".format(a.map, i))
            try:
                p, why = build_demo(spec, a.map, f, out, a.intent, seed=i + 1, max_frames=a.max_frames)
            except Exception as e:                           # noqa: BLE001 - a broken demo must not stop the batch
                p, why = None, repr(e)[:200]
            print("demo {} -> {} ({}) {:.0f} s".format(i, p, why, time.time() - t0), flush=True)
    elif a.what == "sessions":
        for i, arc in enumerate(a.archives):
            sess = unpack(arc, os.path.join(SCRATCH, "sessions"))
            for seat in (("b", "o") if a.seat == "both" else (a.seat,)):
                out = os.path.join(a.out, "session_{}_{}.npz".format(os.path.basename(sess), seat))
                p, why = build_session(spec, sess, seat, out, a.intent, seed=i + 1, max_frames=a.max_frames)
                print("session {} seat {} -> {} ({}) {:.0f} s".format(os.path.basename(sess), seat, p, why, time.time() - t0), flush=True)
    elif a.what == "inputs":
        out = os.path.join(a.out, "inputs_{}.npz".format(os.path.basename(os.path.normpath(a.session))))
        p, why = build_inputs(a.session, out, spec)
        print("inputs -> {} ({})".format(p, why))
    elif a.what == "synth":
        print("synthetic input log ->", synth(spec, a.session, a.into, a.ck))


if __name__ == "__main__":
    main()

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
           env_module="duel_env", group=2, intent_seek=0.0, item_loss=0.5, stack_p=0.0, near_item_p=0.0):
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
    env.round_t[:] = 1e9                                     # every round starts anew at the first step: until 2026-10-08 the
    env._teach_update()                                      # first round after a (re)start was played with every weapon at spawn
    remote.send((env.observe(), env.teach.copy()))
    last = {k: np.copy(v) for k, v in env.stats.items()}
    while True:
        cmd, data = remote.recv()
        if cmd == "step":
            obs, rew, done, info = env.step(data)
            delta = {k: env.stats[k] - last[k] for k in env.stats}
            last = {k: np.copy(v) for k, v in env.stats.items()}
            s = env.state
            delta["air_fast"] = int(((np.hypot(s[:, 3], s[:, 4]) > 330) & (s[:, 6] < 0.5)).sum())
            delta["visible"] = int(env.visible.sum())
            delta["players"] = env.n
            # frags scored by even (learner) players and by odd players, for learner-vs-snapshot win tracking
            ev = info["events"]
            delta["kills_even"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % G % 2 == 0)
            delta["kills_odd"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % G % 2 == 1)
            delta["match_of_kill"] = [e["killer"] // G for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"]]
            delta["even_kill"] = [e["killer"] % G % 2 == 0 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"]]
            remote.send((obs, rew, done, delta, env.script > 0, env.teach.copy(), env.intent_live.copy(), env.intent_teach.copy(),
                         env.key_dec.copy() if hasattr(env, "key_dec") else np.ones(env.n, bool)))
        elif cmd == "curriculum":
            env.close_p, env.round_len, env.dmg_reward, env.intent_seek = data
            remote.send(True)
        elif cmd == "close":
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
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
    ap.add_argument("--weapon-teach", type=float, default=0.0, help="weight of imitating the weapon rule on the weapon key (env._weapon_teach)")
    ap.add_argument("--weapon-teach-minutes", type=float, default=240.0, help="that weight fades to zero over this time")
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
    ap.add_argument("--teach", type=float, default=0.5, help="weight of the teacher loss at the start of this run")
    ap.add_argument("--teach-minutes", type=float, default=240, help="the teacher loss fades to zero over this time")
    ap.add_argument("--teach-warm", type=float, default=0.0, help="minutes over which that weight first rises from nothing: a new "
                    "teacher at full weight moves the whole policy in its first update (0.60 at 0.5 with the strafe-jumping "
                    "teacher, 2026-10-09; the run before started at 0.021), while its loss is still large")
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

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    import importlib
    E_ = importlib.import_module(a.env)
    ACTION_DIMS, OBS_DIM, PERSONAS, WEAPONS = E_.ACTION_DIMS, E_.OBS_DIM, E_.PERSONAS, E_.WEAPONS
    KEY_HEADS = (0, 1, 2, 6)                                 # forward, strafe, vertical, weapon key: the left hand's outputs
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
    course_keys = []
    lab_json = os.path.join(ROOT, "maps", "testlab", "rooms.json")
    if os.path.exists(lab_json):
        course_keys = list(json.load(open(lab_json)).get("courses", {}))
    pipes = []
    w_group = [groups[w % len(groups)] for w in range(a.workers)]             # group size of each worker
    w_match = [max(2, (2 * a.matches // g_) // 2 * 2) for g_ in w_group]       # ... and its groups: about 2 x matches players
    for w in range(a.workers):
        m = maps[w % len(maps)]
        p_main, p_work = mp.Pipe()
        mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), w_match[w], 3000 + w,
                                        os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m)), a.loadout,
                                        a.item_reward, a.drill_p, a.drill_weapons, (round(a.react_ms / 25), round(a.acquire_ms / 25)),
                                        tuple(float(x) for x in a.kind_p.split(",")), a.bot_p,
                                        os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz") if a.teacher else None,
                                        tuple(a.lab_courses.split(",")), tuple(float(x) for x in a.lab_p.split(",")),
                                        tuple(float(x) for x in a.loadout_p.split(",")) if a.loadout_p else None, a.lab_items, a.lab_gun,
                                        a.dmg_taken_w, a.no_walk, a.arena_len, a.arena_full, a.env, w_group[w],
                                        a.intent_seek, a.item_loss, a.stack_p, a.near_item_p),
                   daemon=True).start()
        pipes.append(p_main)
    first = [p.recv() for p in pipes]
    obs = np.concatenate([f[0] for f in first])
    teach = np.concatenate([f[1] for f in first])
    N = len(obs)
    H = a.hidden

    CELL_DIM = 16                                            # v8 only: a learned table of 16 numbers per 64-unit cell
    HAS_CELLS = getattr(E_, "CELL_COLS", None) is not None   # (v9: the map reader's numbers are plain inputs instead)
    if HAS_CELLS:
        assert tuple(E_.CELL_COLS) == (OBS_DIM - 2, OBS_DIM - 1)

    class Policy(nn.Module):
        def __init__(self):
            super().__init__()
            if HAS_CELLS:
                self.cell = nn.Embedding(E_.MAX_CELLS, CELL_DIM)
                nn.init.normal_(self.cell.weight, 0.0, 0.1)
            self.enc = nn.Sequential(nn.Linear(OBS_DIM - 2 + 2 * CELL_DIM if HAS_CELLS else OBS_DIM, 256), nn.Tanh(),
                                     nn.Linear(256, 256), nn.Tanh())
            self.gru = nn.GRUCell(256, H)
            self.pi = nn.Linear(H, sum(ACTION_DIMS))
            self.v = nn.Linear(H, 1)

        def step(self, x, h):
            if HAS_CELLS:
                ids = x[:, -2:].long().clamp(0, E_.MAX_CELLS - 1)   # the last two inputs are cell numbers, not values
                x = torch.cat([x[:, :-2], self.cell(ids[:, 0]), self.cell(ids[:, 1])], 1)
            h = self.gru(self.enc(x), h)
            return self.pi(h), self.v(h).squeeze(-1), h

    def dists(logits):
        return [torch.distributions.Categorical(logits=l) for l in logits.split(ACTION_DIMS, -1)]

    pol = Policy().to(dev)
    with torch.no_grad():                                   # start out mostly keeping the current weapon
        pol.pi.bias[sum(ACTION_DIMS[:6])] += 3.0
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr, eps=1e-5)
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    elapsed0 = 0.0
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location=dev)
        pol.load_state_dict(ck["model"])
        obs_mean, obs_var, obs_count = ck["obs_mean"], ck["obs_var"], ck["obs_count"]
        elapsed0 = ck.get("minutes", 0.0)

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

    def save(path, minutes):
        torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count, map=a.map,
                        obs_dim=OBS_DIM, action_dims=ACTION_DIMS, env="duel", arch="gru", hidden=H, minutes=minutes,
                        env_module=a.env, group=groups[0], groups=groups,
                        react_ms=a.react_ms, acquire_ms=a.acquire_ms, no_walk=bool(a.no_walk),
                        env_vars={k_: os.environ[k_] for k_ in getattr(E_, "PLAY_VARS", ()) if os.environ.get(k_)},
                        round_secs=120.0, arena_secs=float(a.arena_len),
                        cells=E_.MAX_CELLS if HAS_CELLS else 0, cell_dim=CELL_DIM if HAS_CELLS else 0),
                   path)

    # league: odd players of the second half of every worker's matches are played by a frozen snapshot
    # (groups of more than two: every second member)
    w_n = [g_ * m_ for g_, m_ in zip(w_group, w_match)]                      # players of each worker
    w_off = np.concatenate([[0], np.cumsum(w_n)]).astype(int)
    assert w_off[-1] == N, (w_off[-1], N)
    is_odd = np.concatenate([np.arange(n_) % g_ % 2 == 1 for n_, g_ in zip(w_n, w_group)])
    league = np.zeros(N, bool)
    for w in range(a.workers):
        league[w_off[w] + w_n[w] // 2:w_off[w + 1]] = True
    n_groups = int(sum(w_match))
    snap_players = torch.from_numpy(league & is_odd).to(dev)          # controlled by the snapshot
    learn = (~snap_players).float()                                    # trained on
    snaps = []                                                         # frozen past policies (state dicts)
    if a.resume:                                                       # the league survives a restart
        import glob
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "snap_*.pt")))[-8:]:
            snaps.append(torch.load(f, weights_only=False, map_location=dev)["model"])
    anchors, vs_anchor = [], False                                     # ... and opponents that never leave it (--anchor-p)
    if a.anchor_p > 0:
        import glob
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "anchor_*.pt"))):
            anchors.append(torch.load(f, weights_only=False, map_location=dev)["model"])
        print("league anchors: {} (in {:.0%} of the rollouts)".format(len(anchors), a.anchor_p), flush=True)
    opp = copy.deepcopy(pol).eval()
    last_snap = time.time()
    h = torch.zeros(N, H, device=dev)
    h_opp = torch.zeros(N, H, device=dev)
    scr = torch.zeros(N, device=dev)                                   # scripted players (not trained on)

    T = a.steps
    gamma, lam, clip, ent_coef = a.gamma, a.lam, 0.2, a.ent_coef
    ent_heads = [float(x) for x in a.ent_heads.split(",")] if a.ent_heads else [1.0] * len(ACTION_DIMS)
    ent_heads += [1.0] * (len(ACTION_DIMS) - len(ent_heads))
    t_start, total, update = time.time(), 0, 0
    dump = []
    log = open(os.path.join(out, "metrics.jsonl"), "a")
    print("recurrent self-play on {}: {} players, {} weights, device {}, {} min".format(
        a.map, N, sum(p.numel() for p in pol.parameters()), dev, a.minutes), flush=True)
    fade0 = a.fade_start if a.fade_start >= 0 else elapsed0             # the minute of training the teachers' fades count from
    w_map = [maps[w % len(maps)] for w in range(a.workers)]
    MAP_KEYS = ("players", "visible", "frags", "suicides", "pick_wp", "pick_mega", "pick_ra", "pick_ar", "stack_frames",
                "stack_bare", "stack_big", "stack_over", "first_wp", "fire_frames", "play_frames")
    while time.time() - t_start < a.minutes * 60:
        update += 1
        mins = elapsed0 + (time.time() - t_start) / 60
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
            snaps = snaps[-8:]
            save(os.path.join(out, "snapshots", "snap_{:04d}.pt".format(int(mins))), mins)
        if snaps:                                                        # pick this rollout's opponent
            vs_anchor = bool(anchors) and np.random.random() < a.anchor_p
            opp.load_state_dict(anchors[np.random.randint(len(anchors))] if vs_anchor else snaps[np.random.randint(len(snaps))])
        # the last rollout's buffers are let go before the new ones are made: the input buffer alone is 4.7 GiB with
        # 6,800 players, and two of them alive at once is what filled the card (15.8 GB) and broke the cap (2026-10-06)
        b_obs = b_act = b_logp = b_val = b_rew = b_done = b_w = b_live = b_dec = b_iteach = b_teach = None
        if dev.type == "cuda":
            torch.cuda.empty_cache()
        b_obs = torch.zeros(T, N, OBS_DIM, device=dev)
        b_act = torch.zeros(T, N, len(ACTION_DIMS), dtype=torch.long, device=dev)
        b_logp = torch.zeros(T, N, device=dev)
        b_val = torch.zeros(T + 1, N, device=dev)
        b_rew = torch.zeros(T, N, device=dev)
        b_done = torch.zeros(T, N, device=dev)
        b_w = torch.zeros(T, N, device=dev)
        b_live = torch.zeros(T, N, device=dev)                           # the intention head was read on that frame
        b_dec = torch.zeros(T, N, device=dev)                            # the left hand's outputs (keys, weapon key) were read on that frame
        b_iteach = torch.zeros(T, N, dtype=torch.long, device=dev)       # what the item rule would have chosen
        b_teach = torch.zeros(T, N, 5, dtype=torch.long, device=dev)
        h0 = h.clone()
        raw, agg, agg_map = [], {}, {}
        keep_raw = obs_count < OBS_FREEZE or (bool(a.obs_dump) and a.obs_dump_from <= update <= a.obs_dump_to)
        lk = [0, 0]                                                      # league matches: learner kills, snapshot kills
        for t in range(T):
            if keep_raw:
                raw.append(obs if obs_count < OBS_FREEZE else obs[np.random.rand(len(obs)) < 0.005])
            x = torch.from_numpy(norm(obs)).to(dev)
            with torch.no_grad():
                logits, val, h = pol.step(x, h)
                ds = dists(logits)
                act = torch.stack([d.sample() for d in ds], -1)
                lps = [d.log_prob(act[:, i]) for i, d in enumerate(ds)]
                # the intention's part counts only when it was read, the left hand's (keys, weapon key) only on the one
                # frame in four it decides on: until 2026-10-08 all four were counted and three were noise
                logp = sum(lp_ for j_, lp_ in enumerate(lps[:-1]) if j_ not in KEY_HEADS)
                keylp = sum(lps[j_] for j_ in KEY_HEADS)
                if snaps:
                    lo, _, h_opp = opp.step(x, h_opp)
                    act_o = torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
            b_obs[t], b_act[t], b_logp[t], b_val[t] = x, act, logp, val
            b_w[t] = learn * (1.0 - scr)
            b_teach[t] = torch.from_numpy(teach).to(dev)
            an = act.cpu().numpy()
            for w_, p in enumerate(pipes):
                p.send(("step", an[w_off[w_]:w_off[w_ + 1]]))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)
            d = torch.from_numpy(np.concatenate([r[2] for r in res]).astype(np.float32)).to(dev)
            b_done[t] = d
            live = torch.from_numpy(np.concatenate([r[6] for r in res]).astype(np.float32)).to(dev)
            b_live[t] = live
            b_iteach[t] = torch.from_numpy(np.concatenate([r[7] for r in res])).to(dev)
            dec = torch.from_numpy(np.concatenate([r[8] for r in res]).astype(np.float32)).to(dev)
            b_dec[t] = dec
            b_logp[t] = b_logp[t] + lps[-1] * live + keylp * dec
            scr = torch.from_numpy(np.concatenate([r[4] for r in res]).astype(np.float32)).to(dev)
            teach = np.concatenate([r[5] for r in res])
            h = h * (1.0 - d)[:, None]                                   # memory resets on death / round restart
            h_opp = h_opp * (1.0 - d)[:, None]
            for w_, r in enumerate(res):
                for k, v in r[3].items():
                    if isinstance(v, list):
                        continue
                    agg[k] = agg.get(k, 0) + v
                    if k in MAP_KEYS:
                        am_ = agg_map.setdefault(w_map[w_], {})
                        am_[k] = am_.get(k, 0) + v
                for mk, ek in zip(r[3]["match_of_kill"], r[3]["even_kill"]):
                    if mk >= w_match[w_] // 2:                           # second half of the worker = league matches
                        lk[0 if ek else 1] += 1
        with torch.no_grad():
            b_val[T] = pol.step(torch.from_numpy(norm(obs)).to(dev), h)[1]
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
        adv = torch.zeros(T, N, device=dev)
        last = torch.zeros(N, device=dev)
        for t in reversed(range(T)):
            nonterm = 1.0 - b_done[t]
            dl = b_rew[t] + gamma * b_val[t + 1] * nonterm - b_val[t]
            last = dl + gamma * lam * nonterm * last
            adv[t] = last
        ret = adv + b_val[:T]
        frac = min(1.0, mins / a.lr_minutes) if a.lr_minutes > 0 else min(1.0, (time.time() - t_start) / (a.minutes * 60))
        for g in opt.param_groups:
            g["lr"] = a.lr * (1.0 - (1.0 - a.lr_end) * frac)
        lr_now = a.lr * (1.0 - (1.0 - a.lr_end) * frac)
        if a.lr_warm > 0:
            lr_now *= min(1.0, 0.1 + 0.9 * max(0.0, mins - fade0) / a.lr_warm)
            for g in opt.param_groups:
                g["lr"] = lr_now
        n_mb = a.minibatches
        kick = a.teach * max(0.0, 1.0 - (mins - fade0) / a.teach_minutes)
        if a.teach_warm > 0:
            kick *= min(1.0, max(0.0, mins - fade0) / a.teach_warm)
        kick_l = torch.zeros(())
        ik = a.intent_teach * max(0.0, 1.0 - (mins - fade0) / a.intent_teach_minutes)
        ik_l = torch.zeros(())
        wk = a.weapon_teach * max(0.0, 1.0 - (mins - fade0) / a.weapon_teach_minutes)
        wk_l = torch.zeros(())
        demo_w = a.demo_coef * (max(0.0, 1.0 - (time.time() - t_start) / 60.0 / a.demo_minutes) if a.demo_minutes > 0 else 1.0)
        demo_l, demo_acc = torch.zeros(()), [0.0, 0.0, 0.0]
        if demo_w > 0 and update % 5 == 0:
            demo_refill()
        kl_sum, cf_sum, kl_n = 0.0, 0.0, 0                              # the policy's step, measured in the last pass
        klh = np.zeros(len(ACTION_DIMS))
        old_h = None
        if a.kl_heads and (update % a.kl_heads == 0 or update <= 20):    # the log-probability of what he did, per head, before the update
            with torch.no_grad():
                old_h = torch.zeros(T, N, len(ACTION_DIMS), device=dev)
                for chunk in torch.arange(N, device=dev).chunk(n_mb):
                    hh = h0[chunk]
                    lgs = []
                    for t in range(T):
                        lg, v, hh = pol.step(b_obs[t, chunk], hh)
                        lgs.append(lg)
                        hh = hh * (1.0 - b_done[t, chunk])[:, None]
                    for j, dd in enumerate(dists(torch.stack(lgs))):
                        old_h[:, chunk, j] = dd.log_prob(b_act[:, chunk, j])
        for epoch in range(3):
            perm = torch.randperm(N, device=dev)
            for chunk in perm.chunk(n_mb):                               # whole sequences per player
                hh = h0[chunk]
                lgs, vals, hs = [], [], []
                for t in range(T):
                    lg, v, hh = pol.step(b_obs[t, chunk], hh)
                    lgs.append(lg)
                    vals.append(v)
                    if a.teach_trunk < 1.0 or 0.0 <= a.teach_trunk_move < 1.0:
                        hs.append(hh)
                    hh = hh * (1.0 - b_done[t, chunk])[:, None]
                lg = torch.stack(lgs)
                v = torch.stack(vals)
                ds = dists(lg)
                dst = ds                                                 # what the teachers' losses read
                if a.teach_trunk < 1.0 and (kick > 0 or wk > 0 or ik > 0):
                    hs_ = torch.stack(hs)                                # the same outputs, the shared layers held back
                    dst = dists(pol.pi(a.teach_trunk * hs_ + (1.0 - a.teach_trunk) * hs_.detach()))
                dstm = dst                                               # ... and what the movement teacher's loss reads (--teach-trunk-move)
                if kick > 0 and a.teach_trunk_move >= 0 and a.teach_trunk_move != a.teach_trunk:
                    tm_ = a.teach_trunk_move
                    dstm = ds if tm_ >= 1.0 else dists(pol.pi(tm_ * torch.stack(hs) + (1.0 - tm_) * torch.stack(hs).detach()))
                A = b_act[:, chunk]
                lv = b_live[:, chunk]
                dc = b_dec[:, chunk]
                lp = sum(dd.log_prob(A[..., j]) * (dc if j in KEY_HEADS else 1.0) for j, dd in enumerate(ds[:-1])) + ds[-1].log_prob(A[..., -1]) * lv
                ent = sum(w_ * dd.entropy() * (dc if j in KEY_HEADS else 1.0) for j, (w_, dd) in enumerate(zip(ent_heads[:-1], ds[:-1]))) \
                    + ent_heads[-1] * ds[-1].entropy() * lv
                wgt = b_w[:, chunk]
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
                                mk_ = dc if j in KEY_HEADS else (lv if j == len(ds) - 1 else 1.0)
                                klh[j] += float(((old_h[:, chunk, j] - dd.log_prob(A[..., j])) * mk_ * wgt).sum() / wsum)
                pg = -(torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad) * wgt).sum() / wsum
                vl = (0.5 * (v - ret[:, chunk]).pow(2) * wgt).sum() / wsum
                en = (ent * wgt).sum() / wsum
                loss = pg + 0.5 * vl - ent_coef * en
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
                    im_ = b_live[:, chunk] * wgt
                    ik_l = -(dst[-1].log_prob(it_) * im_).sum() / im_.sum().clamp(min=1.0)
                    loss = loss + ik * ik_l
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
                nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
                opt.step()
        total += T * N
        sim_min = T * DT_MIN * n_groups                                  # minutes of play, summed over the groups
        G = N / n_groups                                                 # mean players per group (for the per-player numbers)
        rec = dict(update=update, steps=total, minutes=round(mins, 2), sps=int(total / (time.time() - t_start)),
                   fire_in_view=round(float(agg.get("fire_vis", 0) / max(1, agg.get("vis_frames_h", 0))), 3),
                   shot_cost_per_player_min=round(float(agg.get("shot_cost", 0.0) / max(1e-9, N * T * DT_MIN)), 3),
                   shot_price=round(float(agg.get("shot_fac", 0.0) / max(1, agg.get("shot_n", 0))), 2),
                   armor_soaked_per_player_min=round(float(agg.get("soak", 0.0) / max(1e-9, N * T * DT_MIN)), 1),
                   contest=dict(rounds=int(agg.get("contest_rounds", 0)),      # rounds begun as a race for a big item, and the
                                taken=round(float(agg.get("contest_taken", 0) / max(1, agg.get("contest_rounds", 0))), 2)),   # share a learner took it in
                   kl=round(kl_sum / max(1, kl_n), 5), clip_frac=round(cf_sum / max(1, kl_n), 4), lr=lr_now, lam=lam,
                   know=round(float(agg.get("know", 0.0) / max(1, agg.get("know_frames", 0))), 3),      # how well he knows where his enemy is, 0 to 1 (KNOW_PAY)
                   drops=dict(per_player_min=round(float(agg.get("drops", 0) / max(1e-9, N * T * DT_MIN)), 3),            # weapons dead players left (DROPS)
                              taken=round(float(agg.get("pick_drop", 0) / max(1, agg.get("drops", 0))), 3),              # the share somebody took
                              new=round(float(agg.get("pick_drop_new", 0) / max(1, agg.get("pick_drop", 0))), 3)),       # ... of those, a weapon he did not have
                   pace=dict(pay_per_player_min=round(float(agg.get("pace_pay", 0.0) / max(1e-9, N * T * DT_MIN)), 4),     # (PACE_PAY)
                             trip_speed=int(agg.get("trip_speed", 0.0) / max(1, agg.get("trip_frames", 0))),               # on his way, nobody about
                             over_320=round(float(agg.get("pace_frames", 0) / max(1, agg.get("trip_frames", 0))), 3)),
                   v14=dict(in_hand={w_: round(float(np.atleast_1d(agg.get("hand_w", np.zeros(len(WEAPONS))))[i_]              # the share of his playing time with each weapon in hand
                                                     / max(1.0, float(np.sum(agg.get("hand_w", 0.0))))), 3) for i_, w_ in enumerate(WEAPONS)},
                            blind_fire={w_: round(float(np.atleast_1d(agg.get("blind_w", np.zeros(len(WEAPONS))))[i_]          # ... of that time, firing it with no enemy seen for a second
                                                        / max(1.0, float(np.atleast_1d(agg.get("hand_w", np.zeros(len(WEAPONS))))[i_]))), 3) for i_, w_ in enumerate(WEAPONS)},
                            blind_rockets=dict(per_player_min=round(float(agg.get("blind_rl", 0) / max(1e-9, N * T * DT_MIN)), 3),          # (BLIND_RULE)
                                               how={k_: round(float(np.atleast_1d(agg.get("blind_rl_how", np.zeros(4)))[i_] / max(1, agg.get("blind_rl", 0))), 3)
                                                    for i_, k_ in enumerate(("wasted", "jump", "near", "way"))}),
                            prefire_frames=int(agg.get("prefire_frames", 0)), blind_charged_frames=int(agg.get("blind_bill", 0)),
                            speed_pay_per_player_min=round(float(agg.get("speed_pay", 0.0) / max(1e-9, N * T * DT_MIN)), 4),             # (SPEED_PAY: on his way in games)
                            speed_pay_run_per_player_min=round(float(agg.get("speed_pay_run", 0.0) / max(1e-9, N * T * DT_MIN)), 4),     # ... in item runs
                            teacher_frames=round(float(agg.get("move_teach_frames", 0) / max(1, N * T)), 4),                             # (RUN_TEACHER) the share of all frames it labels
                            height=dict(in_view={k_: round(float(np.atleast_1d(agg.get("high", np.zeros(3)))[i_] / max(1.0, float(np.sum(agg.get("high", 0.0))))), 3)       # B-160: with his enemy in view he stands lower by 48 units or more, level, higher
                                                 for i_, k_ in enumerate(("lower", "level", "higher"))},
                                        damage_from={k_: round(float(np.atleast_1d(agg.get("high_dmg", np.zeros(3)))[i_] / max(1.0, float(np.sum(agg.get("high_dmg", 0.0))))), 3)  # ... the damage he deals, by where he stands
                                                     for i_, k_ in enumerate(("lower", "level", "higher"))},
                                        pay_per_player_min=round(float(agg.get("high_pay", 0.0)) / max(1e-9, N * T * DT_MIN), 4))),                 # (HIGH_PAY) what height added to his pay
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
                   league_size=len(snaps), entropy=round(float(en), 3), close_p=round(close_p, 2))
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

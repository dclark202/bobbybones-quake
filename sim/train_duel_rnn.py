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
           teacher, lab_courses, lab_p, loadout_p, lab_items_p, lab_gun_p=0.0):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    from duel_env import DuelEnv
    env = DuelEnv(bsp, n_matches=matches, seed=seed, nav=nav, close_p=1.0, loadout=loadout, teacher=teacher)
    env.item_reward = item_reward
    env.drill_p = drill_p
    env.react_frames = react_frames[0]
    env.acquire_frames = react_frames[1]
    env.kind_p = kind_p
    if env.lab is not None:                                  # the test map: movement courses only (for now)
        env.lab_p = lab_p
        env.lab_course_ids = [k for k, C in enumerate(env.courses) if C["key"] in lab_courses] or env.lab_course_ids
    env.bot_p = bot_p
    if loadout_p:
        env.loadout_p = loadout_p
    env.lab_items_p = lab_items_p
    env.lab_gun_p = lab_gun_p
    env.sg_spawn = os.environ.get("NO_SG_SPAWN") != "1"   # set NO_SG_SPAWN=1: the shotgun only comes from pickups
    from duel_env import WEAPONS
    env.drill_weapons = tuple(WEAPONS.index(w) for w in drill_weapons.split(","))
    env._teach_update()
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
            delta["kills_even"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % 2 == 0)
            delta["kills_odd"] = sum(1 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"] and e["killer"] % 2 == 1)
            delta["match_of_kill"] = [e["killer"] // 2 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"]]
            delta["even_kill"] = [e["killer"] % 2 == 0 for e in ev if e["killer"] >= 0 and e["killer"] != e["victim"]]
            remote.send((obs, rew, done, delta, env.script > 0, env.teach.copy()))
        elif cmd == "curriculum":
            env.close_p, env.round_len, env.dmg_reward = data
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
    ap.add_argument("--close-minutes", type=float, default=90, help="near-spawn curriculum: 100%% -> 20%% over this time")
    ap.add_argument("--snapshot-min", type=float, default=20)
    ap.add_argument("--drill-p", type=float, default=0.0,
                    help="share of rounds where both players have one weapon only")
    ap.add_argument("--drill-weapons", default="rl,rg,lg,rl,rg,lg,sg,gl,pg,hmg,mg", help="weapons used in drill rounds (equal chance)")
    ap.add_argument("--lab-p", default="0.29,0.71", help="test map: share of playing time in aim rooms / movement courses")
    ap.add_argument("--loadout-p", default="", help="normal rounds, share by spawn: random 1-2 weapons, real duel spawn "
                    "(machine gun and gauntlet), every weapon on the map, the same single weapon for both")
    ap.add_argument("--lab-gun", type=float, default=0.0, help="test map: chance that a course round is run-and-gun "
                    "(a weapon, a target ahead beside the path, damage paid by the runner's speed)")
    ap.add_argument("--lab-items", type=float, default=0.0, help="test map: chance that a course round is the items room")
    ap.add_argument("--lab-courses", default="speed,slalom,ramps",
                    help="movement courses of the test map (bobbylab) used when that map is in --map")
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
    ap.add_argument("--kind-p", default="0.40,0.15,0.10,0.35",
                    help="share of rounds: normal duel, aim (scripted strafing target), one-weapon drill, movement")
    ap.add_argument("--bot-p", type=float, default=0.5, help="share of normal rounds against the scripted fighter")
    ap.add_argument("--react-ms", type=float, default=50, help="tracking delay on an enemy already in view")
    ap.add_argument("--acquire-ms", type=float, default=200, help="delay before an enemy who just came into view is noticed")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    from duel_env import ACTION_DIMS, OBS_DIM, PERSONAS, WEAPONS
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev.type == "cpu":
        torch.set_num_threads(6)
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)
    maps = a.map.split(",")
    course_keys = []
    lab_json = os.path.join(ROOT, "maps", "bobbylab", "rooms.json")
    if os.path.exists(lab_json):
        course_keys = list(json.load(open(lab_json)).get("courses", {}))
    pipes = []
    for w in range(a.workers):
        m = maps[w % len(maps)]
        p_main, p_work = mp.Pipe()
        mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), a.matches, 3000 + w,
                                        os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m)), a.loadout,
                                        a.item_reward, a.drill_p, a.drill_weapons, (round(a.react_ms / 25), round(a.acquire_ms / 25)),
                                        tuple(float(x) for x in a.kind_p.split(",")), a.bot_p,
                                        os.path.join(ROOT, "data", "sim_runs", a.teacher, "policy.npz") if a.teacher else None,
                                        tuple(a.lab_courses.split(",")), tuple(float(x) for x in a.lab_p.split(",")),
                                        tuple(float(x) for x in a.loadout_p.split(",")) if a.loadout_p else None, a.lab_items, a.lab_gun),
                   daemon=True).start()
        pipes.append(p_main)
    first = [p.recv() for p in pipes]
    obs = np.concatenate([f[0] for f in first])
    teach = np.concatenate([f[1] for f in first])
    N = len(obs)
    H = a.hidden

    class Policy(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = nn.Sequential(nn.Linear(OBS_DIM, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
            self.gru = nn.GRUCell(256, H)
            self.pi = nn.Linear(H, sum(ACTION_DIMS))
            self.v = nn.Linear(H, 1)

        def step(self, x, h):
            h = self.gru(self.enc(x), h)
            return self.pi(h), self.v(h).squeeze(-1), h

    def dists(logits):
        return [torch.distributions.Categorical(logits=l) for l in logits.split(ACTION_DIMS, -1)]

    pol = Policy().to(dev)
    with torch.no_grad():                                   # start out mostly keeping the current weapon
        pol.pi.bias[sum(ACTION_DIMS[:-1])] += 3.0
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr, eps=1e-5)
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    elapsed0 = 0.0
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location=dev)
        pol.load_state_dict(ck["model"])
        obs_mean, obs_var, obs_count = ck["obs_mean"], ck["obs_var"], ck["obs_count"]
        elapsed0 = ck.get("minutes", 0.0)

    def norm(o):
        return np.clip((o - obs_mean) / np.sqrt(obs_var + 1e-8), -10, 10).astype(np.float32)

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
                        react_ms=a.react_ms, acquire_ms=a.acquire_ms),
                   path)

    # league: odd players of the second half of every worker's matches are played by a frozen snapshot
    is_odd = (np.arange(N) % 2 == 1)
    per_worker = 2 * a.matches
    league = np.zeros(N, bool)
    for w in range(a.workers):
        league[w * per_worker + per_worker // 2:(w + 1) * per_worker] = True
    snap_players = torch.from_numpy(league & is_odd).to(dev)          # controlled by the snapshot
    learn = (~snap_players).float()                                    # trained on
    snaps = []                                                         # frozen past policies (state dicts)
    if a.resume:                                                       # the league survives a restart
        import glob
        for f in sorted(glob.glob(os.path.join(out, "snapshots", "snap_*.pt")))[-8:]:
            snaps.append(torch.load(f, weights_only=False, map_location=dev)["model"])
    opp = copy.deepcopy(pol).eval()
    last_snap = time.time()
    h = torch.zeros(N, H, device=dev)
    h_opp = torch.zeros(N, H, device=dev)
    scr = torch.zeros(N, device=dev)                                   # scripted players (not trained on)

    T = a.steps
    gamma, lam, clip, ent_coef = a.gamma, 0.95, 0.2, 0.01
    t_start, total, update = time.time(), 0, 0
    log = open(os.path.join(out, "metrics.jsonl"), "a")
    print("recurrent self-play on {}: {} players, {} weights, device {}, {} min".format(
        a.map, N, sum(p.numel() for p in pol.parameters()), dev, a.minutes), flush=True)
    while time.time() - t_start < a.minutes * 60:
        update += 1
        mins = elapsed0 + (time.time() - t_start) / 60
        close_p = max(0.2, 1.0 - 0.8 * mins / a.close_minutes)
        round_len = 15.0 + 105.0 * (1.0 - (close_p - 0.2) / 0.8)
        dmg_reward = 0.004 * max(0.25, close_p)                         # damage shaping fades with the curriculum
        for p in pipes:
            p.send(("curriculum", (close_p, round_len, dmg_reward)))
        for p in pipes:
            p.recv()
        if time.time() - last_snap > a.snapshot_min * 60:                # new league member
            last_snap = time.time()
            snaps.append(copy.deepcopy(pol.state_dict()))
            snaps = snaps[-8:]
            save(os.path.join(out, "snapshots", "snap_{:04d}.pt".format(int(mins))), mins)
        if snaps:                                                        # pick this rollout's opponent
            opp.load_state_dict(snaps[np.random.randint(len(snaps))])
        b_obs = torch.zeros(T, N, OBS_DIM, device=dev)
        b_act = torch.zeros(T, N, len(ACTION_DIMS), dtype=torch.long, device=dev)
        b_logp = torch.zeros(T, N, device=dev)
        b_val = torch.zeros(T + 1, N, device=dev)
        b_rew = torch.zeros(T, N, device=dev)
        b_done = torch.zeros(T, N, device=dev)
        b_w = torch.zeros(T, N, device=dev)
        b_teach = torch.zeros(T, N, 4, dtype=torch.long, device=dev)
        h0 = h.clone()
        raw, agg = [], {}
        lk = [0, 0]                                                      # league matches: learner kills, snapshot kills
        for t in range(T):
            raw.append(obs)
            x = torch.from_numpy(norm(obs)).to(dev)
            with torch.no_grad():
                logits, val, h = pol.step(x, h)
                ds = dists(logits)
                act = torch.stack([d.sample() for d in ds], -1)
                logp = sum(d.log_prob(act[:, i]) for i, d in enumerate(ds))
                if snaps:
                    lo, _, h_opp = opp.step(x, h_opp)
                    act_o = torch.stack([d.sample() for d in dists(lo)], -1)
                    act = torch.where(snap_players[:, None], act_o, act)
            b_obs[t], b_act[t], b_logp[t], b_val[t] = x, act, logp, val
            b_w[t] = learn * (1.0 - scr)
            b_teach[t] = torch.from_numpy(teach).to(dev)
            an = act.cpu().numpy()
            for p, c in zip(pipes, np.array_split(an, len(pipes))):
                p.send(("step", c))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)
            d = torch.from_numpy(np.concatenate([r[2] for r in res]).astype(np.float32)).to(dev)
            b_done[t] = d
            scr = torch.from_numpy(np.concatenate([r[4] for r in res]).astype(np.float32)).to(dev)
            teach = np.concatenate([r[5] for r in res])
            h = h * (1.0 - d)[:, None]                                   # memory resets on death / round restart
            h_opp = h_opp * (1.0 - d)[:, None]
            for r in res:
                for k, v in r[3].items():
                    if isinstance(v, list):
                        continue
                    agg[k] = agg.get(k, 0) + v
                for mk, ek in zip(r[3]["match_of_kill"], r[3]["even_kill"]):
                    if mk >= a.matches // 2:                             # second half of the worker = league matches
                        lk[0 if ek else 1] += 1
        with torch.no_grad():
            b_val[T] = pol.step(torch.from_numpy(norm(obs)).to(dev), h)[1]
        flat = np.concatenate(raw)
        bm, bv, bc = flat.mean(0), flat.var(0), len(flat)
        delta, tot = bm - obs_mean, obs_count + bc
        obs_mean = obs_mean + delta * bc / tot
        obs_var = (obs_var * obs_count + bv * bc + delta ** 2 * obs_count * bc / tot) / tot
        obs_count = tot
        adv = torch.zeros(T, N, device=dev)
        last = torch.zeros(N, device=dev)
        for t in reversed(range(T)):
            nonterm = 1.0 - b_done[t]
            dl = b_rew[t] + gamma * b_val[t + 1] * nonterm - b_val[t]
            last = dl + gamma * lam * nonterm * last
            adv[t] = last
        ret = adv + b_val[:T]
        frac = min(1.0, (time.time() - t_start) / (a.minutes * 60))
        for g in opt.param_groups:
            g["lr"] = a.lr * (1.0 - 0.9 * frac)
        n_mb = a.minibatches
        kick = a.teach * max(0.0, 1.0 - (time.time() - t_start) / 60.0 / a.teach_minutes)
        kick_l = torch.zeros(())
        demo_w = a.demo_coef * (max(0.0, 1.0 - (time.time() - t_start) / 60.0 / a.demo_minutes) if a.demo_minutes > 0 else 1.0)
        demo_l, demo_acc = torch.zeros(()), [0.0, 0.0, 0.0]
        if demo_w > 0 and update % 5 == 0:
            demo_refill()
        for epoch in range(3):
            perm = torch.randperm(N, device=dev)
            for chunk in perm.chunk(n_mb):                               # whole sequences per player
                hh = h0[chunk]
                lgs, vals = [], []
                for t in range(T):
                    lg, v, hh = pol.step(b_obs[t, chunk], hh)
                    lgs.append(lg)
                    vals.append(v)
                    hh = hh * (1.0 - b_done[t, chunk])[:, None]
                lg = torch.stack(lgs)
                v = torch.stack(vals)
                ds = dists(lg)
                A = b_act[:, chunk]
                lp = sum(dd.log_prob(A[..., j]) for j, dd in enumerate(ds))
                ent = sum(dd.entropy() for dd in ds)
                wgt = b_w[:, chunk]
                wsum = wgt.sum().clamp(min=1.0)
                ad = adv[:, chunk]
                ad = (ad - (ad * wgt).sum() / wsum) / (ad[wgt > 0].std() + 1e-8)
                ratio = (lp - b_logp[:, chunk]).exp()
                pg = -(torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad) * wgt).sum() / wsum
                vl = (0.5 * (v - ret[:, chunk]).pow(2) * wgt).sum() / wsum
                en = (ent * wgt).sum() / wsum
                loss = pg + 0.5 * vl - ent_coef * en
                if kick > 0:                                             # imitate the movement teacher in movement rounds
                    tl = b_teach[:, chunk]
                    tm = (tl[..., 0] >= 0).float() * wgt
                    lt = sum(ds[j].log_prob(tl[..., j].clamp(min=0)) for j in range(4))
                    kick_l = -(lt * tm).sum() / tm.sum().clamp(min=1.0)
                    loss = loss + kick * kick_l
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
        sim_min = T * DT_MIN * (N // 2)
        rec = dict(update=update, steps=total, minutes=round(mins, 2), sps=int(total / (time.time() - t_start)),
                   frags_per_match_min=round(agg["frags"] / sim_min, 3),
                   suicides_per_match_min=round(agg["suicides"] / sim_min, 3),
                   hit_rate={w: round(float(agg[w + "_hits"] / max(1, agg[w + "_shots"])), 3) for w in WEAPONS},
                   frag_share={w: round(float(agg[w + "_frags"] / max(1, sum(agg[x + "_frags"] for x in WEAPONS))), 2) for w in WEAPONS},
                   pickups_per_player_min={k[5:]: round(float(agg[k] / (2 * sim_min)), 2)
                                           for k in ("pick_hp", "pick_ar", "pick_mega", "pick_ra", "pick_wp", "pick_am")},
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
                   run_and_gun=dict(damage_per_min=round(float(agg["gun"][0] / max(1.0, agg["gun"][1]) * 2400), 1),
                                    speed=int(agg["gun"][2] / max(1.0, agg["gun"][1]))),
                   teach=[round(kick, 3), round(float(kick_l), 3)],
                   items_room=dict(mega_per_2min=round(float(agg["lab_items"][0] / max(1.0, agg["lab_items"][2]) * 4800), 2),
                                   red_armor_per_2min=round(float(agg["lab_items"][1] / max(1.0, agg["lab_items"][2]) * 4800), 2)),
                   demo=dict(weight=round(demo_w, 3), loss=round(float(demo_l), 3), keys_right=round(demo_acc[0], 3),
                             vertical_right=round(demo_acc[1], 3), turn_within_one_bin=round(demo_acc[2], 3)),
                   crouch=round(float(agg["duck_frames"] / max(1, agg["play_frames"])), 3),
                   walk=round(float(agg["walk_frames"] / max(1, agg["play_frames"])), 3),
                   fall_dmg_per_min=round(float(agg["fall_dmg"] / (2 * sim_min)), 2),
                   target_kills_per_min=round(float(agg["target_kills"] / max(1, agg["aim_round_frames"]) * 2400), 2),
                   visible=round(agg["visible"] / max(1, agg["players"]), 3),
                   air_fast=round(agg["air_fast"] / max(1, agg["players"]), 3),
                   jerk=round(agg["jerk"] / max(1, agg["players"]), 2),
                   vs_snapshot_kill_share=round(lk[0] / max(1, lk[0] + lk[1]), 3) if snaps else None,
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

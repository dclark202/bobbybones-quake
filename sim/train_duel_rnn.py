"""Self-play PPO with memory (GRU) in the duel simulator, against a league of its own past versions.

    python sim/train_duel_rnn.py --map bloodrun,aerowalk,campgrounds --minutes 480 --run duel_gru_v1

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


def worker(remote, bsp, matches, seed, nav, loadout, item_reward):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    from duel_env import DuelEnv
    env = DuelEnv(bsp, n_matches=matches, seed=seed, nav=nav, close_p=1.0, loadout=loadout)
    env.item_reward = item_reward
    remote.send(env.observe())
    last = dict(env.stats)
    while True:
        cmd, data = remote.recv()
        if cmd == "step":
            obs, rew, done, info = env.step(data)
            delta = {k: env.stats[k] - last[k] for k in env.stats}
            last = dict(env.stats)
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
            remote.send((obs, rew, done, delta))
        elif cmd == "curriculum":
            env.close_p, env.round_len, env.dmg_reward = data
            remote.send(True)
        elif cmd == "close":
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,campgrounds")
    ap.add_argument("--run", default="duel_gru_v1")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--matches", type=int, default=128, help="matches per worker (2 players each)")
    ap.add_argument("--steps", type=int, default=128, help="rollout length = training sequence length")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--lr", type=float, default=2.5e-4)
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--loadout", default="full")
    ap.add_argument("--item-reward", type=float, default=0.05, help="reward per 100 points of health/armor picked up")
    ap.add_argument("--close-minutes", type=float, default=90, help="near-spawn curriculum: 100%% -> 20%% over this time")
    ap.add_argument("--snapshot-min", type=float, default=20)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    from duel_env import ACTION_DIMS, OBS_DIM
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev.type == "cpu":
        torch.set_num_threads(6)
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)
    maps = a.map.split(",")
    pipes = []
    for w in range(a.workers):
        m = maps[w % len(maps)]
        p_main, p_work = mp.Pipe()
        mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), a.matches, 3000 + w,
                                        os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m)), a.loadout,
                                        a.item_reward), daemon=True).start()
        pipes.append(p_main)
    obs = np.concatenate([p.recv() for p in pipes])
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

    def save(path, minutes):
        torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count, map=a.map,
                        obs_dim=OBS_DIM, action_dims=ACTION_DIMS, env="duel", arch="gru", hidden=H, minutes=minutes),
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
    opp = copy.deepcopy(pol).eval()
    last_snap = time.time()
    h = torch.zeros(N, H, device=dev)
    h_opp = torch.zeros(N, H, device=dev)

    T = a.steps
    gamma, lam, clip, ent_coef = 0.995, 0.95, 0.2, 0.01
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
            an = act.cpu().numpy()
            for p, c in zip(pipes, np.array_split(an, len(pipes))):
                p.send(("step", c))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)
            d = torch.from_numpy(np.concatenate([r[2] for r in res]).astype(np.float32)).to(dev)
            b_done[t] = d
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
        n_mb = 8
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
                wgt = learn[chunk][None, :].expand(T, -1)
                wsum = wgt.sum().clamp(min=1.0)
                ad = adv[:, chunk]
                ad = (ad - (ad * wgt).sum() / wsum) / (ad[wgt > 0].std() + 1e-8)
                ratio = (lp - b_logp[:, chunk]).exp()
                pg = -(torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad) * wgt).sum() / wsum
                vl = (0.5 * (v - ret[:, chunk]).pow(2) * wgt).sum() / wsum
                en = (ent * wgt).sum() / wsum
                loss = pg + 0.5 * vl - ent_coef * en
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
                opt.step()
        total += T * N
        sim_min = T * DT_MIN * (N // 2)
        rec = dict(update=update, steps=total, minutes=round(mins, 2), sps=int(total / (time.time() - t_start)),
                   frags_per_match_min=round(agg["frags"] / sim_min, 3),
                   suicides_per_match_min=round(agg["suicides"] / sim_min, 3),
                   rocket_hit=round((agg["direct"] + agg["splash_hits"]) / max(1, agg["shots"]), 3),
                   rg_hit=round(agg["rg_hits"] / max(1, agg["rg_shots"]), 3),
                   lg_hit=round(agg["lg_hits"] / max(1, agg["lg_frames"]), 3),
                   mg_hit=round(agg["mg_hits"] / max(1, agg["mg_frames"]), 3),
                   frag_share_rl_rg_lg_mg=[round(agg[k] / max(1, agg["frags"]), 2)
                                           for k in ("rl_frags", "rg_frags", "lg_frags", "mg_frags")],
                   pickups_per_player_min={k[5:]: round(agg[k] / (2 * sim_min), 2)
                                           for k in ("pick_hp", "pick_ar", "pick_mega", "pick_ra", "pick_wp", "pick_am")},
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

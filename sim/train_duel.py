"""Self-play PPO in the duel simulator (sim/duel_env.py): one policy plays both players of every match.

    python sim/train_duel.py --map bloodrun --minutes 120 --run duel_v1 [--init-move data/sim_runs/<run>/policy.pt]

Logs to data/sim_runs/<run>/metrics.jsonl. What to watch: suicides falling (no more shooting the floor),
frags/min rising, accuracy (rocket hits per shot) rising, then behaviour: aiming at feet (splash), dodging,
rocket jumps (self damage while still alive + big vertical speed).
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def worker(remote, bsp, matches, seed, nav):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    from duel_env import DuelEnv
    env = DuelEnv(bsp, n_matches=matches, seed=seed, nav=nav, close_p=1.0)
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
            delta["rj"] = int((s[:, 5] > 450).sum())                     # big upward speed: rocket jumps / pads
            delta["visible"] = int(env.visible.sum())
            delta["players"] = env.n
            remote.send((obs, rew, done, delta))
        elif cmd == "close_p":
            env.close_p, env.round_len = data
            remote.send(True)
        elif cmd == "close":
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--run", default="duel_v1")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--matches", type=int, default=128, help="matches per worker (2 players each)")
    ap.add_argument("--steps", type=int, default=128)
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--close-minutes", type=float, default=60, help="spawn-near-opponent curriculum: 100%% -> 20%% over this time")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    from duel_env import ACTION_DIMS, OBS_DIM
    torch.set_num_threads(6)
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    os.makedirs(out, exist_ok=True)
    pipes = []
    for w in range(a.workers):
        p_main, p_work = mp.Pipe()
        mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", a.map + ".bsp"), a.matches,
                                        2000 + w, os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))),
                   daemon=True).start()
        pipes.append(p_main)
    obs = np.concatenate([p.recv() for p in pipes])
    N = len(obs)

    class Policy(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.Sequential(nn.Linear(OBS_DIM, 384), nn.Tanh(), nn.Linear(384, 256), nn.Tanh())
            self.pi = nn.Linear(256, sum(ACTION_DIMS))
            self.v = nn.Sequential(nn.Linear(OBS_DIM, 384), nn.Tanh(), nn.Linear(384, 256), nn.Tanh(), nn.Linear(256, 1))

        def dist(self, x):
            return [torch.distributions.Categorical(logits=l) for l in self.pi(self.body(x)).split(ACTION_DIMS, -1)]

    pol = Policy()
    with torch.no_grad():                                  # start out mostly keeping the current weapon
        pol.pi.bias[sum(ACTION_DIMS[:-1])] += 3.0
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr, eps=1e-5)
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False)
        pol.load_state_dict(ck["model"])
        obs_mean, obs_var, obs_count = ck["obs_mean"], ck["obs_var"], ck["obs_count"]

    def norm(o):
        return np.clip((o - obs_mean) / np.sqrt(obs_var + 1e-8), -10, 10).astype(np.float32)

    def save():
        torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count, map=a.map,
                        obs_dim=OBS_DIM, action_dims=ACTION_DIMS, env="duel"), os.path.join(out, "policy.pt"))

    T = a.steps
    gamma, lam, clip, ent_coef = 0.995, 0.95, 0.2, 0.01
    t_start, total, update = time.time(), 0, 0
    log = open(os.path.join(out, "metrics.jsonl"), "a")
    print("self-play: {} players ({} matches) on {}, {} min".format(N, N // 2, a.map, a.minutes), flush=True)
    while time.time() - t_start < a.minutes * 60:
        update += 1
        close_p = max(0.2, 1.0 - 0.8 * (time.time() - t_start) / (a.close_minutes * 60))
        round_len = 15.0 + 105.0 * (1.0 - (close_p - 0.2) / 0.8)          # 15 s -> 120 s rounds
        for p in pipes:
            p.send(("close_p", (close_p, round_len)))
        for p in pipes:
            p.recv()
        b_obs = np.zeros((T, N, OBS_DIM), np.float32)
        b_act = np.zeros((T, N, len(ACTION_DIMS)), np.int64)
        b_logp = np.zeros((T, N), np.float32)
        b_val = np.zeros((T + 1, N), np.float32)
        b_rew = np.zeros((T, N), np.float32)
        b_done = np.zeros((T, N), np.float32)
        raw, agg = [], {}
        for t in range(T):
            raw.append(obs)
            x = torch.from_numpy(norm(obs))
            with torch.no_grad():
                ds = pol.dist(x)
                act = torch.stack([d.sample() for d in ds], -1)
                logp = sum(d.log_prob(act[:, i]) for i, d in enumerate(ds))
                val = pol.v(x).squeeze(-1)
            b_obs[t], b_act[t], b_logp[t], b_val[t] = x.numpy(), act.numpy(), logp.numpy(), val.numpy()
            for p, c in zip(pipes, np.array_split(act.numpy(), len(pipes))):
                p.send(("step", c))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            b_rew[t] = np.concatenate([r[1] for r in res])
            b_done[t] = np.concatenate([r[2] for r in res])
            for r in res:
                for k, v in r[3].items():
                    agg[k] = agg.get(k, 0) + v
        with torch.no_grad():
            b_val[T] = pol.v(torch.from_numpy(norm(obs))).squeeze(-1).numpy()
        flat = np.concatenate(raw)
        bm, bv, bc = flat.mean(0), flat.var(0), len(flat)
        delta, tot = bm - obs_mean, obs_count + bc
        obs_mean = obs_mean + delta * bc / tot
        obs_var = (obs_var * obs_count + bv * bc + delta ** 2 * obs_count * bc / tot) / tot
        obs_count = tot
        adv = np.zeros((T, N), np.float32)
        last = 0
        for t in reversed(range(T)):
            nonterm = 1.0 - b_done[t]
            dl = b_rew[t] + gamma * b_val[t + 1] * nonterm - b_val[t]
            last = dl + gamma * lam * nonterm * last
            adv[t] = last
        ret = adv + b_val[:T]
        O = torch.from_numpy(b_obs.reshape(T * N, -1))
        A = torch.from_numpy(b_act.reshape(T * N, -1))
        LP = torch.from_numpy(b_logp.reshape(-1))
        ADV = torch.from_numpy(adv.reshape(-1))
        RET = torch.from_numpy(ret.reshape(-1))
        frac = min(1.0, (time.time() - t_start) / (a.minutes * 60))
        for g in opt.param_groups:
            g["lr"] = a.lr * (1.0 - 0.9 * frac)
        for epoch in range(4):
            perm = torch.randperm(T * N)
            for i in range(0, T * N, 8192):
                idx = perm[i:i + 8192]
                ds = pol.dist(O[idx])
                lp = sum(d.log_prob(A[idx, j]) for j, d in enumerate(ds))
                ent = sum(d.entropy() for d in ds).mean()
                ratio = (lp - LP[idx]).exp()
                ad = ADV[idx]
                ad = (ad - ad.mean()) / (ad.std() + 1e-8)
                pg = -torch.min(ratio * ad, ratio.clamp(1 - clip, 1 + clip) * ad).mean()
                vl = 0.5 * (pol.v(O[idx]).squeeze(-1) - RET[idx]).pow(2).mean()
                loss = pg + 0.5 * vl - ent_coef * ent
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
                opt.step()
        total += T * N
        sim_min = T * DT_MIN * (N // 2)                                  # match-minutes simulated this update
        rec = dict(update=update, steps=total, minutes=round((time.time() - t_start) / 60, 2),
                   sps=int(total / (time.time() - t_start)),
                   frags_per_match_min=round(agg["frags"] / sim_min, 3),
                   suicides_per_match_min=round(agg["suicides"] / sim_min, 3),
                   shots_per_player_min=round(agg["shots"] / (2 * sim_min), 2),
                   hit_rate=round((agg["direct"] + agg["splash_hits"]) / max(1, agg["shots"]), 3),
                   direct_rate=round(agg["direct"] / max(1, agg["shots"]), 3),
                   dmg_per_self_dmg=round(agg["dmg"] / max(1.0, agg["self_dmg"]), 2),
                   visible=round(agg["visible"] / max(1, agg["players"]), 3),
                   air_fast=round(agg["air_fast"] / max(1, agg["players"]), 3),
                   rj=round(agg["rj"] / max(1, agg["players"]), 4),
                   rg_hit=round(agg["rg_hits"] / max(1, agg["rg_shots"]), 3),
                   lg_hit=round(agg["lg_hits"] / max(1, agg["lg_frames"]), 3),
                   frag_share_rl_rg_lg=[round(agg[k] / max(1, agg["frags"]), 2) for k in ("rl_frags", "rg_frags", "lg_frags")],
                   reward=round(float(b_rew.mean()), 4), entropy=round(float(ent), 3), close_p=round(close_p, 2))
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if update % 5 == 1:
            print(" ".join("{}={}".format(k, v) for k, v in rec.items()), flush=True)
        if update % 10 == 0:
            save()
    save()
    for p in pipes:
        p.send(("close", None))


DT_MIN = 0.025 / 60.0

if __name__ == "__main__":
    main()

"""Train a movement policy with PPO in the simulator (CPU).

    python sim/train_move.py --map bloodrun --minutes 60 --run bloodrun_v1

Workers (processes) each run a MoveEnv with many players; the main process runs the policy. Logs one
line per update to data/sim_runs/<run>/metrics.jsonl and saves policy.pt (+ obs normalization) there.
Watch for emergence in the log: "fast%" = share of moving time above 330 units/s (running caps at 320),
"vmax", and trip time vs the nav graph's run-speed estimate ("t/est" < 1 means faster than running).
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)      # (QLBOT_ROOT: the repo, when this file is run from a copy)


def worker(remote, bsp, nav, n, seed, substeps, v14=False):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    from movement_env import MoveEnv
    env = MoveEnv(bsp, nav, n=n, seed=seed, substeps=substeps, v14=v14)
    mapname = os.path.basename(bsp)[:-4]
    remote.send(env.observe())
    while True:
        cmd, data = remote.recv()
        if cmd == "step":
            obs, rew, done, info = env.step(data)
            sp, gr = info["speed"], info["ground"]
            moving = sp > 50
            for ep in info["episodes"]:
                ep["map"] = mapname
            stats = dict(n_moving=int(moving.sum()), n_fast=int((sp[moving] > 330).sum()),
                         vmax=float(sp.max()), air=float(1 - gr.mean()), episodes=info["episodes"])
            remote.send((obs, rew, done, stats))
        elif cmd == "curriculum":
            env.max_goal_time = data
            remote.send(True)
        elif cmd == "close":
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun", help="map, or comma list: workers are spread over the maps")
    ap.add_argument("--nav", default="sim", help="'sim' = data/maps/nav_<map>_sim.json (sim/build_nav.py), "
                                                 "'recorded' = data/practice/nav_<map>.json, or a path")
    ap.add_argument("--run", default="move_v1")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--envs", type=int, default=256, help="players per worker")
    ap.add_argument("--steps", type=int, default=64, help="rollout length per update")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--substeps", default="8,8,9", help="physics ms per 25 ms decision; 8,8,9 = 125 fps human, 25 = 40 Hz bot")
    ap.add_argument("--curr-threshold", type=float, default=0.6, help="success rate that unlocks longer trips")
    ap.add_argument("--v14", action="store_true", help="Quake Live's step height and wading, lava and slime, a price for fall "
                                                       "damage, starts where the spawn points lead (see movement_env.MoveEnv)")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    from movement_env import ACTION_DIMS, OBS_DIM
    torch.set_num_threads(6)
    maps = a.map.split(",")

    def nav_for(m):
        if a.nav == "sim":
            return os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m))
        if a.nav == "recorded":
            return os.path.join(ROOT, "data", "practice", "nav_{}.json".format(m))
        return a.nav
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    os.makedirs(out, exist_ok=True)

    pipes, procs = [], []
    for w in range(a.workers):
        p_main, p_work = mp.Pipe()
        substeps = tuple(int(x) for x in a.substeps.split(","))
        m = maps[w % len(maps)]
        pr = mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), nav_for(m),
                                             a.envs, 1000 + w, substeps, a.v14), daemon=True)
        pr.start()
        pipes.append(p_main)
        procs.append(pr)
    obs = np.concatenate([p.recv() for p in pipes])
    N = len(obs)

    class Policy(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.Sequential(nn.Linear(OBS_DIM, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
            self.pi = nn.Linear(256, sum(ACTION_DIMS))
            self.v = nn.Sequential(nn.Linear(OBS_DIM, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh(), nn.Linear(256, 1))

        def dist(self, x):
            logits = self.pi(self.body(x)).split(ACTION_DIMS, -1)
            return [torch.distributions.Categorical(logits=l) for l in logits]

    pol = Policy()
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr, eps=1e-5)
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    curriculum = 3.0
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False)
        pol.load_state_dict(ck["model"])
        obs_mean, obs_var, obs_count = ck["obs_mean"], ck["obs_var"], ck["obs_count"]
        curriculum = ck.get("curriculum", curriculum)
    for p in pipes:
        p.send(("curriculum", curriculum))
        p.recv()

    def norm(o):
        return np.clip((o - obs_mean) / np.sqrt(obs_var + 1e-8), -10, 10).astype(np.float32)

    T = a.steps
    gamma, lam, clip, ent_coef = 0.99, 0.95, 0.2, 0.01
    t_start, total, update = time.time(), 0, 0
    recent = []
    log = open(os.path.join(out, "metrics.jsonl"), "a")
    print("training {} players on {} ({} workers), {} min".format(N, a.map, a.workers, a.minutes), flush=True)
    while time.time() - t_start < a.minutes * 60:
        update += 1
        b_obs = np.zeros((T, N, OBS_DIM), np.float32)
        b_act = np.zeros((T, N, len(ACTION_DIMS)), np.int64)
        b_logp = np.zeros((T, N), np.float32)
        b_val = np.zeros((T + 1, N), np.float32)
        b_rew = np.zeros((T, N), np.float32)
        b_done = np.zeros((T, N), np.float32)
        raw = []
        n_moving = n_fast = 0
        vmax, air = 0.0, []
        for t in range(T):
            raw.append(obs)
            x = torch.from_numpy(norm(obs))
            with torch.no_grad():
                ds = pol.dist(x)
                act = torch.stack([d.sample() for d in ds], -1)
                logp = sum(d.log_prob(act[:, i]) for i, d in enumerate(ds))
                val = pol.v(x).squeeze(-1)
            b_obs[t], b_act[t], b_logp[t], b_val[t] = x.numpy(), act.numpy(), logp.numpy(), val.numpy()
            chunks = np.array_split(act.numpy(), len(pipes))
            for p, c in zip(pipes, chunks):
                p.send(("step", c))
            res = [p.recv() for p in pipes]
            obs = np.concatenate([r[0] for r in res])
            b_rew[t] = np.concatenate([r[1] for r in res])
            b_done[t] = np.concatenate([r[2] for r in res])
            for r in res:
                st = r[3]
                n_moving += st["n_moving"]
                n_fast += st["n_fast"]
                vmax = max(vmax, st["vmax"])
                air.append(st["air"])
                recent += st["episodes"]
        with torch.no_grad():
            b_val[T] = pol.v(torch.from_numpy(norm(obs))).squeeze(-1).numpy()
        # obs normalization update (running mean/var over this rollout)
        flat = np.concatenate(raw)
        bm, bv, bc = flat.mean(0), flat.var(0), len(flat)
        delta, tot = bm - obs_mean, obs_count + bc
        obs_mean = obs_mean + delta * bc / tot
        obs_var = (obs_var * obs_count + bv * bc + delta ** 2 * obs_count * bc / tot) / tot
        obs_count = tot
        # GAE
        adv = np.zeros((T, N), np.float32)
        last = 0
        for t in reversed(range(T)):
            nonterm = 1.0 - b_done[t]
            delta_t = b_rew[t] + gamma * b_val[t + 1] * nonterm - b_val[t]
            last = delta_t + gamma * lam * nonterm * last
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
        mb = 8192
        for epoch in range(4):
            perm = torch.randperm(T * N)
            for i in range(0, T * N, mb):
                idx = perm[i:i + mb]
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
        recent = recent[-4000:]
        arr = [e for e in recent if e["arrived"]]
        succ = len(arr) / max(1, len(recent))
        ratio_t = float(np.median([e["t"] / max(e["est"], 0.1) for e in arr])) if arr else float("nan")
        rec = dict(update=update, steps=total, minutes=round((time.time() - t_start) / 60, 2),
                   sps=int(total / (time.time() - t_start)), success=round(succ, 3),
                   fell=round(np.mean([e["fell"] for e in recent]) if recent else 0, 3),
                   t_over_est=round(ratio_t, 3), fast_pct=round(100.0 * n_fast / max(1, n_moving), 2),
                   vmax=round(vmax), air=round(float(np.mean(air)), 3), reward=round(float(b_rew.mean()), 4),
                   entropy=round(float(ent), 3), curriculum=curriculum,
                   fall_dmg=round(float(np.mean([e.get("fall_dmg", 0.0) for e in recent] or [0.0])), 2),
                   per_map_t={m: round(float(np.median([e["t"] / max(e["est"], 0.1) for e in arr if e.get("map") == m] or [0])), 3)
                              for m in maps},
                   per_map={m: round(float(np.mean([e["arrived"] for e in recent if e.get("map") == m] or [0])), 3)
                            for m in maps})
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if update % 5 == 1:
            print("upd {update} steps {steps:,} ({sps:,}/s) success {success:.0%} fell {fell:.0%} "
                  "t/est {t_over_est} fast% {fast_pct} vmax {vmax} air {air} curr {curriculum}s {per_map}".format(**rec), flush=True)
        if succ > a.curr_threshold and len(recent) > 2000 and curriculum < 15:
            curriculum = min(15.0, curriculum + 2.0)
            recent = []
            for p in pipes:
                p.send(("curriculum", curriculum))
                p.recv()
        if update % 20 == 0:
            torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count,
                            curriculum=curriculum, map=a.map, obs_dim=OBS_DIM, action_dims=ACTION_DIMS, v14=a.v14,
                            substeps=a.substeps),
                       os.path.join(out, "policy.pt"))
    torch.save(dict(model=pol.state_dict(), obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count,
                    curriculum=curriculum, map=a.map, obs_dim=OBS_DIM, action_dims=ACTION_DIMS, v14=a.v14,
                            substeps=a.substeps),
               os.path.join(out, "policy.pt"))
    for p in pipes:
        p.send(("close", None))
    print("done: {} steps".format(total), flush=True)


if __name__ == "__main__":
    main()

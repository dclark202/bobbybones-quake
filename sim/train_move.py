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


def worker(remote, bsp, nav, n, seed, substeps, v14=False, jumps=False, jump_p=0.5, hand=False, mouse=False, mouse_rev=8,
           look=0.0, arrive=0.0, c2=False):
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, HERE)
    from movement_env import MoveEnv
    env = MoveEnv(bsp, nav, n=n, seed=seed, substeps=substeps, v14=v14, jumps=jumps, jump_p=jump_p, hand=hand, mouse=mouse, mouse_rev=mouse_rev,
                  look=look, arrive=arrive, c2=c2)
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
                         vmax=float(sp.max()), air=float(1 - gr.mean()), episodes=info["episodes"],
                         key_dec=info.get("key_dec"),              # (hand: the frames on which the keys are read next)
                         c2=info.get("c2"))                        # (stage C part 2: the frame's counters of the look tries)
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
    ap.add_argument("--jumps", action="store_true", help="v15: the pros' jumps (sim/pro_gaps/<map>.json) are links of the walking "
                                                         "map, five more inputs tell of a jump ahead, and a share of the "
                                                         "tries begins before a take-off (see movement_env.MoveEnv)")
    ap.add_argument("--jump-p", type=float, default=0.5, help="the share of tries that begin before one of the pros' jumps")
    ap.add_argument("--low", action="store_true", help="run at low priority (beside a training run)")
    ap.add_argument("--mouse", action="store_true", help="v15: his mouse on the view (inertia, no change of the turn's direction within "
                    "0.2 s of the last) and three inputs of what it does")
    ap.add_argument("--mouse-rev", type=int, default=8, help="... the frames (40 a second) between two changes of the turn's direction")
    ap.add_argument("--hand", action="store_true", help="v15: his finger limits on the keys (read ten times a second, a finger at most "
                                                        "every 150 ms, KEY_RATE key actions a second) and five inputs of what the hand "
                                                        "holds; the key outputs are credited only on the frames they are read")
    ap.add_argument("--look", type=float, default=0.0, help="stage C part 2: the share of tries with somewhere to look while he runs "
                    "(a point up to 120 degrees off his way; progress counts only while his view is on it; see movement_env.N_C2)")
    ap.add_argument("--arrive", type=float, default=0.0, help="stage C part 2: the share of tries whose goal is a place to arrive at "
                    "and stand (the map's holding places, points with floor all round and at ledges)")
    ap.add_argument("--c2", action="store_true", help="the three inputs of stage C part 2 with neither kind of try (a network "
                    "that has them, trained on as it is)")
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"), help="where the network is worked out and updated")
    ap.add_argument("--threads", type=int, default=6, help="torch's threads on the processor")
    ap.add_argument("--runs-dir", default=None, help="the folder of the runs (default: data/sim_runs of the repo)")
    a = ap.parse_args()
    if a.low and os.name == "nt":
        import ctypes
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)

    import torch
    import torch.nn as nn
    sys.path.insert(0, HERE)
    import movement_env
    from movement_env import ACTION_DIMS
    C2 = movement_env.N_C2 if (a.look > 0 or a.arrive > 0 or a.c2) else 0     # stage C part 2: its three inputs, the last
    OBS_DIM = (movement_env.OBS_DIM + (movement_env.JL.N_JUMP if a.jumps else 0) + (movement_env.N_HAND if a.hand else 0)
               + (movement_env.N_MOUSE if a.mouse else 0) + C2)
    KEY_COL = -1 - (movement_env.N_MOUSE if a.mouse else 0) - C2   # the input "frames until the keys are read" (the last of the hand's)
    torch.set_num_threads(a.threads)
    dev = torch.device(a.device)
    assert dev.type == "cpu" or torch.cuda.is_available(), "--device cuda: no graphics card to be seen"
    print("device {} | torch threads {} | inputs {}".format(dev, a.threads, OBS_DIM), flush=True)     # (before anything is loaded or started)
    maps = a.map.split(",")

    def nav_for(m):
        if a.nav == "sim":
            return os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m))
        if a.nav == "recorded":
            return os.path.join(ROOT, "data", "practice", "nav_{}.json".format(m))
        return a.nav
    out = os.path.join(a.runs_dir or os.path.join(ROOT, "data", "sim_runs"), a.run)
    os.makedirs(out, exist_ok=True)

    pipes, procs = [], []
    for w in range(a.workers):
        p_main, p_work = mp.Pipe()
        substeps = tuple(int(x) for x in a.substeps.split(","))
        m = maps[w % len(maps)]
        pr = mp.Process(target=worker, args=(p_work, os.path.join(ROOT, "data", "maps", m + ".bsp"), nav_for(m),
                                             a.envs, 1000 + w, substeps, a.v14, a.jumps, a.jump_p, a.hand, a.mouse, a.mouse_rev,
                                             a.look, a.arrive, bool(C2)), daemon=True)
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

    pol = Policy().to(dev)
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr, eps=1e-5)
    obs_mean, obs_var, obs_count = np.zeros(OBS_DIM), np.ones(OBS_DIM), 1e-4
    curriculum = 3.0
    if a.resume and os.path.exists(os.path.join(out, "policy.pt")):
        ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False, map_location="cpu")
        sd = ck["model"]
        more = OBS_DIM - sd["body.0.weight"].shape[1]
        assert more >= 0, "the saved network has {} inputs, these options give {}: a network with the inputs of stage C part 2 needs --c2 (or --look, --arrive)".format(
            sd["body.0.weight"].shape[1], OBS_DIM)
        if more > 0:                                          # a network from before the inputs of a jump ahead: they start at nothing
            for k_ in ("body.0.weight", "v.0.weight"):
                sd[k_] = torch.cat([sd[k_], torch.zeros(sd[k_].shape[0], more)], 1)
            ck["obs_mean"] = np.concatenate([ck["obs_mean"], np.zeros(more)])
            ck["obs_var"] = np.concatenate([ck["obs_var"], np.ones(more)])
            print("carried over: {} more inputs, at zero weight".format(more), flush=True)
        pol.load_state_dict(sd)
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
        t_u0 = time.time()
        c2n, eps_now = np.zeros(8), []                         # stage C part 2: the frames' counters, the tries that ended in this update
        b_obs = np.zeros((T, N, OBS_DIM), np.float32)
        b_act = np.zeros((T, N, len(ACTION_DIMS)), np.int64)
        b_logp = np.zeros((T, N), np.float32)
        b_val = np.zeros((T + 1, N), np.float32)
        b_rew = np.zeros((T, N), np.float32)
        b_done = np.zeros((T, N), np.float32)
        b_dec = np.ones((T, N), np.float32)                    # (hand) the keys chosen at this step are read
        raw = []
        n_moving = n_fast = 0
        vmax, air = 0.0, []
        for t in range(T):
            raw.append(obs)
            x = torch.from_numpy(norm(obs)).to(dev)
            with torch.no_grad():
                ds = pol.dist(x)
                act = torch.stack([d.sample() for d in ds], -1)
                # (hand) the keys are read at the next step only for the players whose wait is over: the last input of the hand says so
                kd = torch.from_numpy((obs[:, KEY_COL] == 0).astype(np.float32)).to(dev) if a.hand else torch.ones(len(obs), device=dev)
                logp = sum(d.log_prob(act[:, i]) * (kd if i < 3 else 1.0) for i, d in enumerate(ds))
                val = pol.v(x).squeeze(-1)
            b_obs[t], b_act[t], b_logp[t], b_val[t] = x.cpu().numpy(), act.cpu().numpy(), logp.cpu().numpy(), val.cpu().numpy()
            b_dec[t] = kd.cpu().numpy()
            chunks = np.array_split(act.cpu().numpy(), len(pipes))
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
                eps_now += st["episodes"]
                if st.get("c2") is not None:
                    c2n += st["c2"]
        with torch.no_grad():
            b_val[T] = pol.v(torch.from_numpy(norm(obs)).to(dev)).squeeze(-1).cpu().numpy()
        t_u1 = time.time()
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
        O = torch.from_numpy(b_obs.reshape(T * N, -1)).to(dev)
        A = torch.from_numpy(b_act.reshape(T * N, -1)).to(dev)
        LP = torch.from_numpy(b_logp.reshape(-1)).to(dev)
        ADV = torch.from_numpy(adv.reshape(-1)).to(dev)
        RET = torch.from_numpy(ret.reshape(-1)).to(dev)
        DEC = torch.from_numpy(b_dec.reshape(-1)).to(dev)
        frac = min(1.0, (time.time() - t_start) / (a.minutes * 60))
        for g in opt.param_groups:
            g["lr"] = a.lr * (1.0 - 0.9 * frac)
        mb = 8192
        for epoch in range(4):
            perm = torch.randperm(T * N, device=dev)
            for i in range(0, T * N, mb):
                idx = perm[i:i + mb]
                ds = pol.dist(O[idx])
                lp = sum(d.log_prob(A[idx, j]) * (DEC[idx] if j < 3 else 1.0) for j, d in enumerate(ds))
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
        recent = recent[-(12000 if a.jumps else 4000):]
        arr = [e for e in recent if e["arrived"]]
        succ = len(arr) / max(1, len(recent))
        ratio_t = float(np.median([e["t"] / max(e["est"], 0.1) for e in arr])) if arr else float("nan")
        rec = dict(update=update, steps=total, minutes=round((time.time() - t_start) / 60, 2),
                   sps=int(total / (time.time() - t_start)), success=round(succ, 3),
                   fell=round(np.mean([e["fell"] for e in recent]) if recent else 0, 3),
                   lava=round(float(np.mean([e.get("lava", False) for e in recent])) if recent else 0, 3),
                   t_over_est=round(ratio_t, 3), fast_pct=round(100.0 * n_fast / max(1, n_moving), 2),
                   vmax=round(vmax), air=round(float(np.mean(air)), 3), reward=round(float(b_rew.mean()), 4),
                   entropy=round(float(ent), 3), curriculum=curriculum,
                   fall_dmg=round(float(np.mean([e.get("fall_dmg", 0.0) for e in recent] or [0.0])), 2),
                   per_map_t={m: round(float(np.median([e["t"] / max(e["est"], 0.1) for e in arr if e.get("map") == m] or [0])), 3)
                              for m in maps},
                   per_map={m: round(float(np.mean([e["arrived"] for e in recent if e.get("map") == m] or [0])), 3)
                            for m in maps})
        if a.jumps:                                            # the tries for the pros' jumps: the share that got over, all and per map and jump
            tr = [e for e in recent if e.get("jump", -1) >= 0]
            rec["jump_tries"] = len(tr)
            rec["jump_over"] = round(float(np.mean([e["crossed"] for e in tr] or [0])), 3)
            pj = {}
            for e in tr:
                pj.setdefault("{}:{}".format(e.get("map"), e["jump"]), []).append(e["crossed"])
            rec["per_jump"] = {k_: [round(float(np.mean(v_)), 2), len(v_)] for k_, v_ in sorted(pj.items())}
        rec["roll_s"], rec["update_s"] = round(t_u1 - t_u0, 2), round(time.time() - t_u1, 2)     # the simulators' part of the update, the network's
        if C2:
            # stage C part 2. The look tries, by frame of this update, over the frames he travels: with a look direction
            # given the share his view is within 30 degrees of it, the share of progress that counted, his speed and the
            # share at 400 or more; his speed and that share without one. The arrive tries that ended in this update:
            # how many, the share that came within the distance, of the frames after that the share within it and the
            # share standing, his speed as he crossed it, the share that fell after arriving.
            lf_, ff_ = max(1.0, c2n[0]), max(1.0, c2n[4])
            at_ = [e for e in eps_now if e.get("stand")]
            got_ = [e for e in at_ if e["arrived"]]
            aft_ = max(1.0, float(sum(e["after"] for e in got_)))
            rec.update(look_frames=int(c2n[0]), look_in30=round(c2n[1] / lf_, 3), look_counted=round(c2n[7] / lf_, 3), look_speed=round(c2n[2] / lf_),
                       look_fast=round(c2n[3] / lf_, 3), free_frames=int(c2n[4]), free_speed=round(c2n[5] / ff_), free_fast=round(c2n[6] / ff_, 3),
                       look_tries=sum(1 for e in eps_now if e.get("look")), tries=len(eps_now),
                       arr_tries=len(at_), arr_arrived=round(len(got_) / max(1, len(at_)), 3), arr_after=int(sum(e["after"] for e in got_)),
                       arr_within=round(sum(e["within"] for e in got_) / aft_, 3), arr_stood=round(sum(e["stood"] for e in got_) / aft_, 3),
                       arr_cross=round(float(np.mean([e["cross"] for e in got_] or [0.0]))),
                       arr_fell=round(float(np.mean([e["fell_after"] for e in got_] or [0.0])), 3))
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if update % 5 == 1:
            print("upd {update} steps {steps:,} ({sps:,}/s) success {success:.0%} fell {fell:.0%} lava {lava:.1%} "
                  "t/est {t_over_est} fast% {fast_pct} vmax {vmax} air {air} curr {curriculum}s {per_map}".format(**rec)
                  + (" | jumps over {:.0%} of {}".format(rec["jump_over"], rec["jump_tries"]) if a.jumps else "")
                  + (" | look: within 30 deg {look_in30:.0%}, speed {look_speed} ({look_fast:.0%} at 400+) against {free_speed} ({free_fast:.0%}) without"
                     " | stand: {arr_tries} tries, arrived {arr_arrived:.0%}, then within {arr_within:.0%}, standing {arr_stood:.0%}, crossed at {arr_cross},"
                     " fell {arr_fell:.0%}".format(**rec) if C2 else ""), flush=True)
        if succ > a.curr_threshold and len(recent) > 2000 and curriculum < 15:
            curriculum = min(15.0, curriculum + 2.0)
            recent = []
            for p in pipes:
                p.send(("curriculum", curriculum))
                p.recv()
        if update % 20 == 0:
            torch.save(dict(model={k_: v_.cpu() for k_, v_ in pol.state_dict().items()}, obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count,
                            curriculum=curriculum, map=a.map, obs_dim=OBS_DIM, action_dims=ACTION_DIMS, v14=a.v14, jumps=a.jumps,
                            hand=a.hand, mouse=a.mouse, mouse_rev=a.mouse_rev, substeps=a.substeps, c2=C2, look=a.look, arrive=a.arrive),
                       os.path.join(out, "policy.pt"))
    torch.save(dict(model={k_: v_.cpu() for k_, v_ in pol.state_dict().items()}, obs_mean=obs_mean, obs_var=obs_var, obs_count=obs_count,
                    curriculum=curriculum, map=a.map, obs_dim=OBS_DIM, action_dims=ACTION_DIMS, v14=a.v14, jumps=a.jumps,
                            hand=a.hand, mouse=a.mouse, mouse_rev=a.mouse_rev, substeps=a.substeps, c2=C2, look=a.look, arrive=a.arrive),
               os.path.join(out, "policy.pt"))
    for p in pipes:
        p.send(("close", None))
    print("done: {} steps".format(total), flush=True)


if __name__ == "__main__":
    main()

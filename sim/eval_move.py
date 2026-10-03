"""Evaluate a trained movement policy: item-to-item trip times, strafe-jump detection, a top-down picture.

    python sim/eval_move.py --run bloodrun_v1

Writes data/sim_runs/<run>/eval.json and trips.png. Nightmare baselines come from real QL training
trips (data/train/c*/trips.jsonl, Nightmare driving, no fighting); they include its detours.
"""
import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from movement_env import ACTION_DIMS, MoveEnv  # noqa: E402

LABEL = {"item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA", "item_health_mega": "MH",
         "weapon_rocketlauncher": "RL", "weapon_lightning": "LG", "weapon_railgun": "RG", "weapon_plasmagun": "PG",
         "weapon_shotgun": "SG", "weapon_grenadelauncher": "GL", "item_health_large": "h50", "item_quad": "QUAD"}


def nightmare_baselines(mapname):
    T = defaultdict(list)
    for f in glob.glob(os.path.join(ROOT, "data", "train", "c*", "trips.jsonl")):
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("driver") != "ai" or r.get("fight", 9) > 0.5 or r.get("map", "bloodrun") != mapname:
                continue
            a, b = (re.sub(r"@\d+", "", x) for x in r["key"].split(">"))
            if a != b and a != "spawn":
                T[(a, b)].append(r["secs"])
    return {k: (float(np.median(v)), len(v)) for k, v in T.items() if len(v) >= 20}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="bloodrun_v1")
    ap.add_argument("--repeats", type=int, default=8)
    ap.add_argument("--map", default=None, help="map to evaluate (default: the run's first map)")
    ap.add_argument("--nav", default="sim", help="sim | recorded")
    a = ap.parse_args()
    import torch
    import torch.nn as nn
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    ck = torch.load(os.path.join(out, "policy.pt"), weights_only=False)
    mapname = a.map or ck.get("map", "bloodrun").split(",")[0]
    navp = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)) if a.nav == "sim" else         os.path.join(ROOT, "data", "practice", "nav_{}.json".format(mapname))
    obs_dim = ck["obs_dim"]

    body = nn.Sequential(nn.Linear(obs_dim, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
    pi = nn.Linear(256, sum(ACTION_DIMS))
    sd = ck["model"]
    body.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("body.")})
    pi.load_state_dict({k[3:]: v for k, v in sd.items() if k.startswith("pi.")})

    base = nightmare_baselines(mapname)
    env0 = MoveEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"),
                   navp, n=1)
    goals = [e for e in env0.w.entities if e.get("classname") in LABEL and "origin" in e]
    labels = [LABEL[e["classname"]] for e in goals]
    uniq = [i for i, l in enumerate(labels) if labels.count(l) == 1]
    gidx = {}
    for i in uniq:                                           # map each goal entity to the env's goal index
        d = np.linalg.norm(env0.goal_pos - np.array(goals[i]["origin"], np.float32), axis=1)
        if d.min() < 1:
            gidx[labels[i]] = int(d.argmin())
    pairs = [(x, y) for x in gidx for y in gidx if x != y]
    n = len(pairs) * a.repeats
    env = MoveEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"),
                  navp, n=n)
    for k, (x, y) in enumerate(pairs):
        p = env.goal_pos[gidx[x]]
        f = env.field
        node, _ = f.locate(p[None])
        nx = f.next[gidx[y], node[0]]
        q = f.nodes[nx] if nx >= 0 else env.goal_pos[gidx[y]]
        yaw = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
        for r in range(a.repeats):
            env.place(k * a.repeats + r, p, yaw, gidx[y])
    obs = env.observe()
    finished = np.full(n, np.nan)
    traj = [[] for _ in range(n)]
    for step in range(int(30 / 0.025)):
        x = torch.from_numpy(np.clip((obs - ck["obs_mean"]) / np.sqrt(ck["obs_var"] + 1e-8), -10, 10).astype(np.float32))
        with torch.no_grad():
            logits = pi(body(x)).split(ACTION_DIMS, -1)
            act = torch.stack([torch.distributions.Categorical(logits=l).sample() for l in logits], -1).numpy()
        s = env.state
        for i in range(n):
            if np.isnan(finished[i]):
                traj[i].append((*s[i, :3], math.hypot(s[i, 3], s[i, 4]), s[i, 6], *act[i]))
        obs, rew, done, info = env.step(act)
        # MoveEnv restarts finished players; their episodes come back in the order of np.nonzero(done)
        for i, e in zip(np.nonzero(done)[0], info["episodes"]):
            if np.isnan(finished[i]):
                finished[i] = e["t"] if e["arrived"] else np.inf
        if not np.isnan(finished).any():
            break

    table = []
    for k, (x, y) in enumerate(pairs):
        ts = finished[k * a.repeats:(k + 1) * a.repeats]
        ok = ts[np.isfinite(ts)]
        nm = base.get((x, y))
        table.append(dict(trip="{}>{}".format(x, y), policy_median=float(np.median(ok)) if len(ok) else None,
                          success=float(len(ok) / len(ts)), nightmare_median=nm[0] if nm else None,
                          nightmare_n=nm[1] if nm else 0))
    # strafe-jump signature: sustained >330 u/s with jumps chained on landings and alternating strafe keys
    fast_air, hops, alt = 0, 0, 0
    moving = 0
    for tr in traj:
        arr = np.array(tr) if tr else np.zeros((0, 9))
        if not len(arr):
            continue
        sp, gr, side, jump = arr[:, 3], arr[:, 4], arr[:, 6], arr[:, 7]
        moving += int((sp > 50).sum())
        # ignore 1.5 s after a jump pad / teleporter kick (speed jump > 200 in one frame)
        kick = np.zeros(len(sp), bool)
        for j in np.nonzero(np.diff(sp) > 200)[0]:
            kick[j:j + 60] = True
        fast_air += int(((sp > 330) & (gr < 0.5) & ~kick).sum())
        hops += int(((jump[1:] == 1) & (gr[1:] > 0.5) & (sp[1:] > 330) & ~kick[1:]).sum())
        alt += int((np.abs(np.diff(side)) == 2).sum())
    emerg = dict(fast_air_pct=round(100.0 * fast_air / max(1, moving), 2), hops_above_330=hops,
                 strafe_switches=alt, vmax=float(max((max(t[3] for t in tr) for tr in traj if tr), default=0)))
    res = dict(run=a.run, map=mapname, trips=table, emergence=emerg)
    json.dump(res, open(os.path.join(out, "eval_{}.json".format(mapname)), "w"), indent=1)
    if mapname == ck.get("map", "bloodrun").split(",")[0]:
        json.dump(res, open(os.path.join(out, "eval.json"), "w"), indent=1)
    both = [t for t in table if t["policy_median"] and t["nightmare_median"]]
    print("trip        policy   nightmare(QL)   success")
    for t in sorted(both, key=lambda t: -t["nightmare_n"])[:15]:
        print("{:10} {:6.2f}s   {:6.2f}s (n={:4})   {:.0%}".format(t["trip"], t["policy_median"], t["nightmare_median"],
                                                                t["nightmare_n"], t["success"]))
    if both:
        faster = sum(t["policy_median"] < t["nightmare_median"] for t in both)
        print("policy faster on {}/{} compared trips; overall success {:.0%}".format(
            faster, len(both), np.mean([t["success"] for t in table])))
    print("emergence:", emerg)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 10), dpi=110)
    ax.scatter(env.field.nodes[:, 0], env.field.nodes[:, 1], s=1, c="#bbbbbb")
    for k in range(0, n, a.repeats):
        tr = np.array(traj[k]) if traj[k] else None
        if tr is None or len(tr) < 2:
            continue
        sc = ax.scatter(tr[:, 0], tr[:, 1], c=np.clip(tr[:, 3], 0, 700), cmap="viridis", s=3, vmin=0, vmax=700)
    for lab, gi in gidx.items():
        p = env.goal_pos[gi]
        ax.annotate(lab, (p[0], p[1]), fontsize=11, weight="bold", color="crimson")
    fig.colorbar(sc, ax=ax, shrink=0.7, label="horizontal speed (u/s); running caps at 320")
    ax.set_aspect("equal")
    ax.set_title("{}: learned movement, one run per trip".format(mapname))
    fig.savefig(os.path.join(out, "trips_{}.png".format(mapname)), bbox_inches="tight")
    print("wrote", os.path.join(out, "trips_{}.png".format(mapname)))


if __name__ == "__main__":
    main()

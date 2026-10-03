"""What did self-play learn? Plays a trained duel policy against itself and measures behaviours.

    python sim/eval_duel.py --run duel_v1 [--seconds 120]

- aim: where rockets explode relative to the target (feet = splash play), direct-hit share, rail/LG hit rates
- dodging: sideways speed relative to an incoming rocket vs at other times
- prefire: rockets fired while the opponent is NOT visible but was seen within the last second
- rocket jumps: own-rocket self-hits that launch the player upward (vz > 400) and are survived
- movement: share of time airborne above 330 u/s (strafe jumping) in fights
Also plays the policy against a "stand and spin" dummy and a random policy for a sanity baseline.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import duel_env as D  # noqa: E402


def load(run):
    import torch
    import torch.nn as nn
    ck = torch.load(os.path.join(ROOT, "data", "sim_runs", run, "policy.pt"), weights_only=False)
    body = nn.Sequential(nn.Linear(D.OBS_DIM, 384), nn.Tanh(), nn.Linear(384, 256), nn.Tanh())
    pi = nn.Linear(256, sum(D.ACTION_DIMS))
    sd = ck["model"]
    body.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("body.")})
    pi.load_state_dict({k[3:]: v for k, v in sd.items() if k.startswith("pi.")})

    def act(obs):
        x = torch.from_numpy(np.clip((obs - ck["obs_mean"]) / np.sqrt(ck["obs_var"] + 1e-8), -10, 10).astype(np.float32))
        with torch.no_grad():
            return torch.stack([torch.distributions.Categorical(logits=l).sample()
                                for l in pi(body(x)).split(D.ACTION_DIMS, -1)], -1).numpy()
    return act, ck


def play(env, policy_a, policy_b, frames):
    """even players use policy_a, odd players policy_b; returns per-frame records for analysis"""
    obs = env.observe()
    rec = dict(frames=0, prefire=0, shots_blind=0, shots=0, rj=0, sideways_threat=[], sideways_calm=[],
               fast_air=0, alive_frames=0, expl_dz=[], kills_a=0, kills_b=0, suicides=0)
    last_seen = np.full(env.n, -99.0)
    for f in range(frames):
        a = policy_a(obs)
        b = policy_b(obs)
        act = np.where((np.arange(env.n) % 2 == 0)[:, None], a, b)
        before_cool = env.cool.copy()
        before_hp = env.hp.copy()
        vis_before = env.visible.copy()
        last_seen[vis_before] = f
        obs, r, done, info = env.step(act)
        fired = (env.cool > before_cool + 0.5) & (env.weapon == 0)
        rec["shots"] += int(fired.sum())
        blind = fired & ~vis_before
        rec["shots_blind"] += int(blind.sum())
        rec["prefire"] += int((blind & (f - last_seen < 40)).sum())
        s = env.state
        # rocket jump: lost a little health (own splash), shot upward, still alive
        self_hit = (env.hp < before_hp - 3) & (s[:, 5] > 400) & ~done
        rec["rj"] += int(self_hit.sum())
        # dodging: incoming rocket within 400 units -> sideways speed relative to the rocket's path
        opp = np.arange(env.n) ^ 1
        for i in range(env.n):
            ra = env.ra[opp[i]]
            if ra.any():
                rp, rv = env.rp[opp[i]][ra], env.rv[opp[i]][ra]
                d = np.linalg.norm(rp - s[i, :3], axis=1)
                k = int(d.argmin())
                if d[k] < 400:
                    u = rv[k] / (np.linalg.norm(rv[k]) + 1e-6)
                    v = s[i, 3:6]
                    side = np.linalg.norm(v - u * (v @ u))
                    rec["sideways_threat"].append(float(side))
                    continue
            rec["sideways_calm"].append(float(np.linalg.norm(s[i, 3:5])))
        moving = np.hypot(s[:, 3], s[:, 4])
        rec["fast_air"] += int(((moving > 330) & (s[:, 6] < 0.5)).sum())
        rec["alive_frames"] += env.n
        for e in info["events"]:
            if e["killer"] < 0 or e["killer"] == e["victim"]:
                rec["suicides"] += 1
            elif e["killer"] % 2 == 0:
                rec["kills_a"] += 1
            else:
                rec["kills_b"] += 1
        rec["frames"] += 1
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="duel_v1")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--seconds", type=float, default=90)
    ap.add_argument("--matches", type=int, default=64)
    a = ap.parse_args()
    act, ck = load(a.run)
    bsp = os.path.join(ROOT, "data", "maps", a.map + ".bsp")
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    frames = int(a.seconds / D.DT)
    rng = np.random.default_rng(0)

    def random_policy(obs):
        return np.stack([rng.integers(d, size=len(obs)) for d in D.ACTION_DIMS], 1)

    def dummy(obs):                                     # stand still, never shoot
        out = np.zeros((len(obs), len(D.ACTION_DIMS)), np.int64)
        out[:, 0] = out[:, 1] = 1
        out[:, 3] = len(D.TURN) // 2
        out[:, 4] = len(D.PITCH) // 2
        return out
    results = {}
    for name, opp in (("self-play", act), ("vs random", random_policy), ("vs standing dummy", dummy)):
        env = D.DuelEnv(bsp, n_matches=a.matches, seed=7, nav=nav, close_p=0.2)
        env.round_len = 120.0
        st0 = dict(env.stats)
        r = play(env, act, opp, frames)
        st = {k: env.stats[k] - st0[k] for k in env.stats}
        mins = frames * D.DT / 60.0 * a.matches
        res = dict(kills_per_match_min=round(r["kills_a"] / mins, 2), deaths_per_match_min=round(r["kills_b"] / mins, 2),
                   suicides_per_match_min=round(r["suicides"] / mins, 2),
                   rocket_hit_rate=round((st["direct"] + st["splash_hits"]) / max(1, st["shots"]), 3),
                   direct_share=round(st["direct"] / max(1, st["direct"] + st["splash_hits"]), 3),
                   rg_hit=round(st["rg_hits"] / max(1, st["rg_shots"]), 3), lg_hit=round(st["lg_hits"] / max(1, st["lg_frames"]), 3),
                   blind_shot_share=round(r["shots_blind"] / max(1, r["shots"]), 3),
                   prefire_share=round(r["prefire"] / max(1, r["shots"]), 3),
                   rocket_jumps_per_player_min=round(r["rj"] / (2 * mins), 3),
                   sideways_speed_under_fire=round(float(np.median(r["sideways_threat"])) if r["sideways_threat"] else 0, 1),
                   speed_otherwise=round(float(np.median(r["sideways_calm"])) if r["sideways_calm"] else 0, 1),
                   fast_airborne_share=round(r["fast_air"] / max(1, r["alive_frames"]), 3))
        results[name] = res
        print(name, json.dumps(res))
    json.dump(results, open(os.path.join(ROOT, "data", "sim_runs", a.run, "eval_duel.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

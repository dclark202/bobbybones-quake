"""Does moving make him harder to hit? Two minutes of self-play in the environment box with the current checkpoint:
damage per second of firing with the enemy in view, split by whether the enemy was moving, and how he moves when
the enemy is in view.   python tools/dodge_check.py [run]      (Anaconda Python, from the repo folder)"""
import sys
import numpy as np
sys.path.insert(0, "sim")
import duel_env as E
import test_suite as T

run = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v5"
pol = T.Policy("data/sim_runs/{}/policy.pt".format(run), seed=3)
env = E.DuelEnv("data/maps/bobbylab.bsp", n_matches=32, seed=9, loadout="all")
env.react_frames = round(pol.react_ms / 25)
env.dmg_taken_w, env.no_walk, env.arena_len = 1.0, True, 60.0
env.lab_force = dict(kind=E.NORMAL, arena=2)
env.round_t[:] = 1e9
h = pol.zeros(env.n)
obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
opp = np.arange(env.n) ^ 1
fire_f = np.zeros(3); dmg = np.zeros(3); side = []; flips = 0; frames = 0; last_s = np.zeros(env.n)
for t in range(int(120 / E.DT)):
    act, h = pol.act(obs, h)
    s0 = env.state.copy(); vis = env.acquired.copy(); firing = act[:, 5] == 1
    obs, _, done, _ = env.step(act)
    h[done] = 0.0
    osp = np.hypot(s0[opp, 3], s0[opp, 4])
    b = np.where(osp < 50, 0, np.where(osp < 200, 1, 2))
    dealt = env.fb[:, 0] * 100.0
    m = vis & env.fire_last
    for k in range(3):
        fire_f[k] += (m & (b == k)).sum(); dmg[k] += dealt[m & (b == k)].sum()
    # own movement relative to the line to the enemy, while he is in view
    to = s0[opp, :2] - s0[:, :2]; to /= np.linalg.norm(to, axis=1, keepdims=True) + 1e-6
    lat = s0[:, 3] * -to[:, 1] + s0[:, 4] * to[:, 0]
    side += np.abs(lat[vis]).tolist()
    sg = np.sign(np.where(np.abs(lat) > 60, lat, 0))
    flips += int(((sg != 0) & (last_s != 0) & (sg != last_s) & vis).sum()); last_s = np.where(sg != 0, sg, last_s); frames += int(vis.sum())
print("DODGE damage per second of firing at an enemy in view: standing {:.0f}, slow {:.0f}, moving over 200 u/s {:.0f} | share of firing time: {} | "
      "his own sideways speed with the enemy in view: mean {:.0f} u/s, direction changes {:.1f} a second".format(
          *(dmg / np.maximum(1, fire_f) * 40), np.round(fire_f / fire_f.sum(), 2).tolist(), np.mean(side), flips / max(1, frames) * 40))

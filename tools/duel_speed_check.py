"""How the current duel_gru_v4 checkpoint moves in Blood Run self-play duels in the simulator (speed, enemy in view, weapon held),
with the spawn used in training and with every weapon in hand. Run with the Anaconda Python from the repo folder."""
import sys
import numpy as np
sys.path.insert(0, "sim")
import duel_env as E
import test_suite as T
pol = T.Policy("data/sim_runs/duel_gru_v4/policy.pt", seed=3)
env = E.DuelEnv("data/maps/bloodrun.bsp", n_matches=16, seed=5, nav="data/maps/nav_bloodrun_sim.json", close_p=0.2, loadout="all")
env.react_frames = round(pol.react_ms / 25)
env.kind_p = (1, 0, 0, 0); env.bot_p = 0.0; env.round_len = 120.0
for name, lp, sg in (("as trained tonight", (0.3, 0.5, 0.2, 0.0), False), ("every weapon incl. shotgun (benchmark server)", (0.0, 0.0, 1.0, 0.0), True)):
    env.loadout_p, env.sg_spawn = lp, sg
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    held = np.zeros(E.NW); sp = []; vis = []
    for t in range(int(100 / E.DT)):
        act, h = pol.act(obs, h)
        obs, _, done, _ = env.step(act)
        h[done] = 0.0
        held += np.bincount(env.weapon, minlength=E.NW)
        sp.append(np.hypot(env.state[:, 3], env.state[:, 4])); vis.append(env.visible.mean())
    sp = np.array(sp)
    print(name, "| speed mean %d, share above 330: %.2f | in view %.2f | held" % (sp.mean(), (sp > 330).mean(), np.mean(vis)),
          {E.WEAPONS[i]: round(float(held[i] / held.sum()), 2) for i in np.argsort(-held)[:4]})

"""What each weapon contributes, beyond who gets the kill. Three minutes of self-play in the environment box with
the current checkpoint and the run's weapon sets: share of damage by weapon, which weapon opened the fight (first
damage in an enemy's life), share of kills, and time held.   python tools/weapon_use.py [run]   (Anaconda Python)

Damage in a frame is put down to the player's projectile if one of his ended that frame, else to the weapon of
the shot that left that frame."""
import os
import sys

import numpy as np

sys.path.insert(0, "sim")
import duel_env as E          # noqa: E402
import test_suite as T        # noqa: E402

run = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v5"
pol = T.Policy("data/sim_runs/{}/policy.pt".format(run), seed=3)
env = E.DuelEnv("data/maps/testlab.bsp", n_matches=32, seed=13, loadout="all")
env.react_frames = round(pol.react_ms / 25)
env.dmg_taken_w, env.no_walk, env.arena_len = 1.0, True, 60.0
sets = os.environ.get("ARENA_SETS", "rl;rl,lg;rl,rg;rl,rg,lg")
env.arena_sets = [tuple(E.WEAPONS.index(x) for x in s_.split(",")) for s_ in sets.split(";")]
env.lab_force = dict(kind=E.NORMAL, arena=2)
env.round_t[:] = 1e9
h = pol.zeros(env.n)
obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
n, NW = env.n, E.NW
opp = np.arange(n) ^ 1
dmg, first, kills, held, owned = np.zeros(NW), np.zeros(NW), np.zeros(NW), np.zeros(NW), np.zeros(NW)
fresh = np.ones(n, bool)                                   # the enemy has not been damaged yet in his current life
for t in range(int(180 / E.DT)):
    act, h = pol.act(obs, h)
    ra0, rw0, rage0, fw = env.ra.copy(), env.rw.copy(), env.rage.copy(), env.fire_w.copy()
    obs, _, done, info = env.step(act)
    h[done] = 0.0
    dealt = env.fb[:, 0] * 100.0
    ended = ra0 & (~env.ra | (env.rage < rage0))
    for i in np.nonzero(dealt > 0)[0]:
        k = np.nonzero(ended[i])[0]
        w = int(rw0[i, k[0]]) if len(k) else int(fw[i])
        dmg[w] += dealt[i]
        if fresh[i]:
            first[w] += 1
            fresh[i] = False
    for e in info["events"]:
        fresh[opp[e["victim"]]] = True
        if e["killer"] >= 0 and e["killer"] != e["victim"] and e["weapon"] >= 0:
            kills[e["weapon"]] += 1
    fresh[done] = True
    np.add.at(held, env.weapon, 1)
    owned += env.has.sum(0)


def share(v):
    return {E.WEAPONS[k]: round(float(v[k] / max(1.0, v.sum())), 2) for k in np.argsort(-v) if v[k] / max(1.0, v.sum()) >= 0.005}


print("WEAPONS damage {} | opened the fight {} | kills {} | held (of the time he owned it) {}".format(
    share(dmg), share(first), share(kills),
    {E.WEAPONS[k]: round(float(held[k] / max(1.0, owned[k])), 2) for k in (E.RL, E.RG, E.LG, E.MG)}))

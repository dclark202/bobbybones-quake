"""Check sim/duel_env_ffa.py. First: with two players per group it must play exactly as sim/duel_env.py (same seed,
same actions: inputs, rewards and round ends compared frame by frame). Then: a short run with more players per
group, in the environment box and on the yard map with items, printing what happened.

    python tools/ffa_check.py            (Anaconda Python)
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def run(module, group, frames, out, bsp="testlab", rooms=(2,), sets=None, matches=24):
    import importlib
    E = importlib.import_module(module)
    kw = dict(group=group) if module.endswith("ffa") else {}
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", bsp + ".bsp"), n_matches=matches, seed=5, **kw)
    env.kind_p, env.lab_p, env.arena_rooms, env.arena_len, env.no_walk = (1, 0, 0, 0), (0, 0, 1), rooms, 20.0, True
    env.react_frames, env.acquire_frames = 3, 8
    env.dmg_reward, env.dmg_taken_w = 0.005, 1.0
    if sets:
        env.arena_sets = sets
    rng = np.random.default_rng(11)
    cut = E.OBS_BASE + E.N_EXTRA + E.N_FIGHT + E.N_MEM + E.N_ROUTE      # where the group block sits in duel_env_ffa
    obs, rew, don = [], [], []
    o = env.observe()
    for t in range(frames):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.8                  # mostly firing
        # turn toward the enemy attended to, so that shots land and there is something to compare
        foe = getattr(env, "foe", np.arange(env.n) ^ 1)
        s = env.state
        to = s[foe, :3] - s[:, :3]
        ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw + 180.0) % 360.0 - 180.0
        ep = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - env.pitch
        aim = rng.random(env.n) < 0.7
        a[:, 3] = np.where(aim, np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1), a[:, 3])
        a[:, 4] = np.where(aim, np.abs(E.PITCH[None, :] - np.clip(ep, -10, 10)[:, None]).argmin(1), a[:, 4])
        o, r, d, info = env.step(a)
        oo = o if not hasattr(E, "N_FFA") else np.delete(o, np.s_[cut:cut + E.N_FFA], axis=1)     # drop the group block: the rest must match
        obs.append(oo.copy()), rew.append(r.copy()), don.append(d.copy())
    st = env.stats
    line = "{} group {} on {}: {} inputs, frags {}, suicides {}, damage {:.0f}, in view {:.2f}, pickups mega {} red {} weapons {}".format(
        module, group, bsp, o.shape[1], int(st["frags"]), int(st["suicides"]), float(st["dmg"]), float(env.visible.mean()),
        int(st["pick_mega"]), int(st["pick_ra"]), int(st["pick_wp"]))
    if out:
        np.savez(out, obs=np.array(obs), rew=np.array(rew), don=np.array(don))
    print(line, flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        m, g, fr, out, bsp, room = sys.argv[1:7]
        run(m, int(g), int(fr), out if out != "-" else None, bsp, (int(room),),
            [(0,), (0, 2), (0, 1), (0, 1, 2)] if len(sys.argv) > 7 else None, matches=24 if int(g) == 2 else 8)
        sys.exit(0)
    tmp = tempfile.mkdtemp()
    outs = []
    for mod in ("duel_env", "duel_env_ffa"):               # one simulator per process
        outs.append(os.path.join(tmp, mod + ".npz"))
        subprocess.run([sys.executable, __file__, mod, "2", "3000", outs[-1], "testlab", "2", "sets"], check=True)
    a, b = np.load(outs[0]), np.load(outs[1])
    same = all(np.array_equal(a[k], b[k]) for k in ("obs", "rew", "don"))
    if not same:
        bad = np.nonzero((a["obs"] != b["obs"]).any((1, 2)) | (a["rew"] != b["rew"]).any(1))[0]
        print("first difference at frame", int(bad[0]), "inputs", np.nonzero((a["obs"][bad[0]] != b["obs"][bad[0]]).any(0))[0][:20])
    print("TWO PLAYERS: {}".format("identical to duel_env over 3000 frames" if same else "DIFFERENT"))
    for g, bsp, room in ((4, "testlab", 2), (6, "testlab", 2), (4, "arena1", 3), (6, "arena1", 3)):
        subprocess.run([sys.executable, __file__, "duel_env_ffa", str(g), "3000", "-", bsp, str(room)], check=True)

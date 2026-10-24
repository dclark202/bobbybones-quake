"""v0.4.0 brain: checks of the zones and the TRACK_Z truth columns (CPU, a minute). Run with TRACK_TRUTH=1 TRACK_Z=1:

    python tools/zones_check.py [--map aerowalk] [--frames 600]

1. every map's zones file: its grid gives the walking points the zone the file names for them (most of them: the grid is by
   32-unit cells, the zone by the point), every zone has points, the count is within 1 .. MAX_Z;
2. a simulator with random actions: en_zone is the zone of the enemy's own place (his row's x, y, z), zone_n the map's count;
   en_spd8 / en_mvf8 / en_mvl8 equal the mean of the enemy's last 8 velocities (kept here from the state, frame by frame,
   cleared at his spawn) turned to the reader's facing; zone_seen is the zone the enemy was in at the last frame he was in view;
3. the readout's second part (sim/track_z.py) at its start: even zones over the map's count (nll = log k), the direction
   even (nll = log 2 pi), and its lesson's gradient finite where the direction outputs are zero.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import zonemap  # noqa: E402


def files():
    for m in zonemap.MAPS:
        Z = zonemap.load(m)
        if Z is None:
            print("  {:15s} no zones file".format(m))
            continue
        import json
        nodes = np.array(json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(m))))["nodes"], np.float64)
        same = float((Z.locate(nodes) == Z.node_zone).mean())
        sz = np.bincount(Z.node_zone, minlength=Z.k)
        assert 1 <= Z.k <= zonemap.MAX_Z and sz.min() > 0 and len(Z.node_zone) == len(nodes) and same > 0.9, (m, Z.k, sz.min(), same)
        print("  {:15s} zones {:2d}, points a zone {:3d}..{:3d}; the grid agrees with the points' zones at {:.1%}".format(m, Z.k, sz.min(), sz.max(), same))


def sim(mapname, frames):
    import duel_env_ffa as E
    assert E.TRACK_Z, "run with TRACK_TRUTH=1 TRACK_Z=1"
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"), n_matches=8, seed=7,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)))
    C = {k: i for i, k in enumerate(E.AUX_COLS)}
    Z = zonemap.load(mapname)
    rng = np.random.default_rng(0)
    n = env.n
    hist = np.zeros((8, n, 2))
    cnt = np.zeros(n)
    life = np.asarray(env.life_t[:n], np.float64).copy()
    zseen = np.full(n, -1)
    bad = dict(zone=0, spd=0, mv=0, seen=0)
    checked = 0
    env.observe()
    for t in range(frames):
        a = np.stack([rng.integers(0, d, n) for d in E.ACTION_DIMS], 1)
        obs, rew, done, info = env.step(a)
        A = info["aux"]
        s = env.state
        lf = np.asarray(env.life_t[:n], np.float64)
        new = lf < life
        life = lf.copy()
        hist[:, new] = 0.0
        cnt[new] = 0
        hist[t % 8] = s[:n, 3:5]
        cnt = np.minimum(cnt + 1, 8)
        foe = np.arange(n) ^ 1
        vis = np.asarray(env.visible, bool)[:n]
        gone = (env.hp[foe] <= 0) | new[foe]
        zf = Z.locate(s[foe, :3])
        zseen = np.where(vis, zf, np.where(gone, -1, zseen))
        if t < 10:
            continue
        pos_foe = A[foe][:, [C["x"], C["y"], C["z"]]]
        bad["zone"] += int((A[:, C["en_zone"]] != Z.locate(pos_foe)).sum() + (A[:, C["zone_n"]] != Z.k).sum())
        mv = hist[:, foe].sum(0) / np.maximum(cnt[foe], 1)[:, None]
        sp = np.linalg.norm(hist[:, foe], axis=2).sum(0) / np.maximum(cnt[foe], 1)
        yr = np.radians(env.yaw[:n])
        c, si = np.cos(yr), np.sin(yr)
        f, l = c * mv[:, 0] + si * mv[:, 1], -si * mv[:, 0] + c * mv[:, 1]
        bad["spd"] += int((np.abs(A[:, C["en_spd8"]] - sp) > 0.05).sum())
        bad["mv"] += int(((np.abs(A[:, C["en_mvf8"]] - f) > 0.05) | (np.abs(A[:, C["en_mvl8"]] - l) > 0.05)).sum())
        bad["seen"] += int((A[:, C["zone_seen"]] != zseen).sum())
        checked += n
    # the 0.2 s mean against the instantaneous velocity the old readout learnt (en_vfwd, en_vleft): close but not the same
    print("  {} frames x {} players on {}: mismatches {} (of {} each)".format(frames, n, mapname, bad, checked))
    assert all(v == 0 for v in bad.values()), bad
    return env


def head():
    import torch
    import track_z as T
    torch.manual_seed(0)
    L = T.layout()
    m = T.make_module(256, L)
    x = torch.randn(64, 256)
    y = torch.zeros(64, len(T.COLS))
    y[:, 0] = torch.randint(0, 16, (64,))
    y[:, 1] = 16
    y[:, 2] = 300 + 100 * torch.randn(64)
    y[:, 3:5] = 300 * torch.randn(64, 2)
    o = m(x)
    ll, wd, hz = T.parts(o, y)
    assert torch.allclose(-ll[:, 0], torch.full((64,), math.log(16.0)), atol=1e-4), "zones not even at the start"
    assert torch.allclose(-ll[:, 2], torch.full((64,), math.log(2 * math.pi)), atol=1e-4), "direction not even at the start"
    l, p = T.loss(o, y, T.DEFAULT_W, torch.ones(64))
    l.backward()
    g = [q.grad for q in m.parameters()]
    assert all(torch.isfinite(q).all() for q in g), "a gradient that is not finite at the start"
    print("  the part at its start: zone nll {:.3f} (log 16 = {:.3f}), direction nll {:.3f} (log 2 pi = {:.3f}), speed nll {:.3f}; "
          "gradients finite".format(float(p[0]), math.log(16), float(p[2]), math.log(2 * math.pi), float(p[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="aerowalk")
    ap.add_argument("--frames", type=int, default=600)
    a = ap.parse_args()
    print("1. the zones files")
    files()
    print("2. the truth columns")
    sim(a.map, a.frames)
    print("3. the readout's second part")
    head()
    print("ok")


if __name__ == "__main__":
    main()

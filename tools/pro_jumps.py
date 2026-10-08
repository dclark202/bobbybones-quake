"""Where and how much the pros are in the air, per duel map: from every converted 1v1 demo (the light sets of
sim/demo_dataset.py --lite), with the map's own floor under each position.

    python tools/pro_jumps.py --map bloodrun,aerowalk,lostworld        -> sim/pro_jump/<map>.npz, docs/pro_jumps.json

Per map: the share of their moving time spent in the air, jumps a minute, speed on the ground and in the air, and a
table per cell of 64 units (top view, two floors by height as the map reader's cells) of the share of time in the air and
the mean speed there. The simulator's walking teacher takes its jump label from the table (PRO_JUMP): it used to label
"no jump" on every frame that was not a gap or a step, which taught him to keep his feet on the floor (2026-10-08: he
jumps in 1 to 2% of frames). No player names are read or written.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
CELL = 64.0
DT = 0.025                                                    # the demos' frames (40 a second)


def demo_root():
    p = os.path.join(ROOT, "data", "demo_root.txt")
    return open(p).read().strip() if os.path.exists(p) else os.path.join(ROOT, "data")


def build(mp, every, max_files):
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=0,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    w = env.w
    lo, hi = env.lo.copy(), env.hi.copy()
    zmid = float(lo[2] + hi[2]) / 2.0
    nx, ny = [int(v) for v in np.ceil((hi[:2] - lo[:2]) / CELL) + 1]
    T = np.zeros((2, ny, nx), np.float64)                       # moving frames
    A = np.zeros((2, ny, nx), np.float64)                       # ... of them in the air
    S = np.zeros((2, ny, nx), np.float64)                       # sum of speed
    down = np.array([[[0.0, 0.0, -1.0]]], np.float32)
    files = sorted(glob.glob(os.path.join(demo_root(), "sets_lite", mp, "*.npz")))[:max_files or None]
    tot = dict(frames=0, moving=0, air=0, air_moving=0, jumps=0, sp_ground=0.0, sp_air=0.0, n_ground=0, n_air=0, fast_air=0)
    sp_air_all, sp_gr_all = [], []
    for f in files:
        try:
            q = np.load(f)["lite"]
        except Exception:                                       # noqa: BLE001
            continue
        if len(q) < 200:
            continue
        pos = q[:, 5:8].astype(np.float32)
        alive = (q[:, 0] > 0) & (q[:, 31] > 0.5 if q.shape[1] > 31 else True)
        step = np.linalg.norm(pos[1:, :2] - pos[:-1, :2], axis=1)
        ok = alive[1:] & alive[:-1] & (step < 60.0)             # (a respawn or a teleporter is not speed)
        speed = np.where(ok, step / DT, 0.0)
        idx = np.nonzero(ok)[0][::every] + 1
        if not len(idx):
            continue
        p = pos[idx]
        fr = np.concatenate([w.rays_each(p[c:c + 4096], np.repeat(down, len(p[c:c + 4096]), 0), 400.0)[:, 0] for c in range(0, len(p), 4096)])
        air = fr * 400.0 > 24.0 + 6.0                           # the origin is 24 above his feet
        sp = speed[idx - 1]
        mv = sp > 150.0
        cx = np.clip(((p[:, 0] - lo[0]) / CELL).astype(int), 0, nx - 1)
        cy = np.clip(((p[:, 1] - lo[1]) / CELL).astype(int), 0, ny - 1)
        lz = (p[:, 2] > zmid).astype(int)
        np.add.at(T, (lz[mv], cy[mv], cx[mv]), 1.0)
        np.add.at(A, (lz[mv], cy[mv], cx[mv]), air[mv].astype(np.float64))
        np.add.at(S, (lz[mv], cy[mv], cx[mv]), sp[mv])
        tot["frames"] += len(idx)
        tot["moving"] += int(mv.sum())
        tot["air"] += int(air.sum())
        tot["air_moving"] += int((air & mv).sum())
        tot["sp_ground"] += float(sp[mv & ~air].sum())
        tot["n_ground"] += int((mv & ~air).sum())
        tot["sp_air"] += float(sp[mv & air].sum())
        tot["n_air"] += int((mv & air).sum())
        tot["fast_air"] += int((air & (sp > 400.0)).sum())
        if every == 1:
            tot["jumps"] += int((air[1:] & ~air[:-1] & (pos[idx][1:, 2] > pos[idx][:-1, 2])).sum())
        if len(sp_air_all) < 400:
            sp_air_all.append(sp[mv & air][::7])
            sp_gr_all.append(sp[mv & ~air][::7])
    out = os.path.join(ROOT, "sim", "pro_jump", mp + ".npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    share = np.where(T >= 40, A / np.maximum(T, 1), -1.0).astype(np.float32)        # -1: too little play there to say
    np.savez_compressed(out, lo=lo, zmid=zmid, cell=CELL, air=share, speed=np.where(T >= 40, S / np.maximum(T, 1), 0.0).astype(np.float32),
                        frames=T.astype(np.float32))
    a_, g_ = np.concatenate(sp_air_all) if sp_air_all else np.zeros(1), np.concatenate(sp_gr_all) if sp_gr_all else np.zeros(1)
    mins = tot["frames"] * every * DT / 60.0
    res = dict(demos=len(files), minutes=round(mins), moving_share=round(tot["moving"] / max(1, tot["frames"]), 3),
               air_share_of_moving=round(tot["air_moving"] / max(1, tot["moving"]), 3),
               speed_ground=round(tot["sp_ground"] / max(1, tot["n_ground"])), speed_air=round(tot["sp_air"] / max(1, tot["n_air"])),
               speed_air_quartiles=[int(v) for v in np.percentile(a_, [25, 50, 75, 95])],
               speed_ground_quartiles=[int(v) for v in np.percentile(g_, [25, 50, 75, 95])],
               air_over_400_share_of_all=round(tot["fast_air"] / max(1, tot["frames"]), 3),
               jumps_per_minute=round(tot["jumps"] / max(1e-9, mins), 1) if every == 1 else None,
               cells_known=int((share >= 0).sum()), cells_mostly_air=int((share > 0.5).sum()))
    print(mp, res, flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--every", type=int, default=1, help="use every n-th frame (1 = all; jumps a minute need 1)")
    ap.add_argument("--max-files", type=int, default=0)
    a = ap.parse_args()
    out = {mp: build(mp, a.every, a.max_files) for mp in a.map.split(",")}
    json.dump(out, open(os.path.join(ROOT, "docs", "pro_jumps.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

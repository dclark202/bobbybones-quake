"""The exchange model X of docs/design/SPACE.md (part A, the measurement; owner, 2026-11-09: "more testing and less 'train and hope'"):
with me here and him there, these weapons, these stacks: who comes out ahead in the next seconds. Reads the frame records of
tools/run/cypher_measure.py sim (rec_<map>_<k>.npz: both seats' place, health, armor, weapon, damage dealt, kills, every frame).
Nothing here touches a run or a simulator's play: it reads records, traces lines of sight on the map, and fits a small model on the CPU.

    python tools/run/space_fit.py rows <recdir> [--out <dir>] [--every 0.5] [--h 5] [--par 4]
        one process a map (one simulator World a process): rows_<map>.npz, a row every --every seconds a seat with both alive:
        the two zones, distance, height difference, line of sight each way, both stacks and weapons; what the next --h seconds
        brought (cut at the first death): who died first, the damage each dealt
    python tools/run/space_fit.py prorows [--maps a,b] [--demos 150] [--out data/sim_runs/space/pro_rows] [--par 4]
        the same rows from the pros' demos (tools/pro_moments.py's frames): the followed player exact, his enemy's stack worked out
    python tools/run/space_fit.py fit <rowsdir> [<rowsdir> ...] --out <model.pt> [--epochs 30]
        X fitted with the games split three ways (fit / stop / held out), in four sizes: the base rate, the stacks and weapons
        alone, with the geometry, with the learned part a zone. What the places add on held-out games is the measure
    python tools/run/space_fit.py zones <model.pt>          how holdable each zone is at level stacks (SPACE.md example 6)
    python tools/run/space_fit.py measure <model.pt> <rowsdir> [--side 0]
        whose ground he stands in by the stack ratio, entries into the enemy's ground and how they end, enemies in his ground
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import zonemap as ZM                                          # noqa: E402  (plain numpy)

NW = 9                                                        # weapons (duel_env.WEAPONS)
COLS = ("game", "map", "t", "side", "zi", "zj", "dist", "dz", "los_ij", "los_ji", "hp_i", "ar_i", "hp_j", "ar_j", "w_i", "w_j",
        "vis_i", "vis_j", "die_i", "die_j", "dmg_ij", "dmg_ji", "mv_i", "mv_j")
C = {k: n for n, k in enumerate(COLS)}
CONTACT = 20.0                                                # an exchange: this much damage, both ways together, in the window
BANDS = (0.0, 0.67, 0.9, 1.1, 1.5, 1e9)
BAND_NAMES = ("under 0.67", "0.67-0.9", "0.9-1.1", "1.1-1.5", "over 1.5")


def eff(hp, ar):
    """the effective stack (tools/run/cypher_measure.py's, sim/win_judge.py's rule)"""
    hp = np.maximum(hp, 0.0)
    return hp + np.minimum(ar, 2.0 * hp)


# ------------------------------------------------------------------------------------------------------------------ rows
def rows_map(a):
    meta = json.load(open(os.path.join(a.rec, "meta.json")))
    for s in meta["sets"]:                                    # the games' own switches: the line of sight is the games'
        k, v = s.split("=", 1)
        os.environ[k] = v
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1")
    import duel_env as D
    env = D.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=0)
    Z = ZM.load(a.map)
    assert Z is not None, "no zones for " + a.map
    mi = ZM.MAPS.index(a.map)
    out = []
    files = sorted(glob.glob(os.path.join(a.rec, "rec_{}_*.npz".format(a.map))))
    for fi, f in enumerate(files):
        d = np.load(f, allow_pickle=True)
        dt = float(d["dt"])
        step, win = int(round(a.every / dt)), int(round(a.h / dt))
        hp, ar, alive = d["hp"].astype(np.float32), d["ar"].astype(np.float32), d["alive"]
        pos, dealt, wp, vis, side = d["pos"].astype(np.float32), d["dealt"], d["weapon"], d["vis"], d["side"]
        T, n = hp.shape
        cum = np.concatenate([np.zeros((1, n), np.float64), np.cumsum(dealt, 0)])       # cum[t] = dealt before frame t
        for m in range(n // 2):
            i, j = 2 * m, 2 * m + 1
            both = alive[:, i] & alive[:, j]
            die = np.zeros((T, 2), bool)                      # a death on this frame
            die[1:, 0] = alive[:-1, i] & ~alive[1:, i]
            die[1:, 1] = alive[:-1, j] & ~alive[1:, j]
            anyd = np.nonzero(die.any(1))[0]
            ts = np.arange(step, T - win - 1, step)
            ts = ts[both[ts]]
            if not len(ts):
                continue
            nx = np.searchsorted(anyd, ts, side="right")      # the first death after t
            td = np.where(nx < len(anyd), anyd[np.minimum(nx, len(anyd) - 1)], T + win)
            inw = td <= ts + win
            end = np.where(inw, td, ts + win)                 # the window's last frame
            di = inw & die[np.minimum(td, T - 1), 0]
            dj = inw & die[np.minimum(td, T - 1), 1]
            dij = cum[end + 1, i] - cum[ts + 1, i]
            dji = cum[end + 1, j] - cum[ts + 1, j]
            pi, pj = pos[ts, i], pos[ts, j]
            eye = np.array([0, 0, float(D.VIEW_H)], np.float32)
            body = np.array([0, 0, 8.0], np.float32)
            lij = env._los(pi + eye, pj + body)
            lji = env._los(pj + eye, pi + body)
            zi, zj = Z.locate(pi), Z.locate(pj)
            dist = np.linalg.norm(pi - pj, axis=1)
            g = np.full(len(ts), fi * 100 + m, np.float64)
            back = np.maximum(ts - int(round(1.0 / dt)), 0)       # how far each moved in the second before
            mvi, mvj = np.linalg.norm(pi - pos[back, i], axis=1), np.linalg.norm(pj - pos[back, j], axis=1)
            for (x, y, zx, zy, lx, ly, dx, dy, ddx, ddy, sgn, m1, m2) in ((i, j, zi, zj, lij, lji, di, dj, dij, dji, 1.0, mvi, mvj),
                                                                 (j, i, zj, zi, lji, lij, dj, di, dji, dij, -1.0, mvj, mvi)):
                out.append(np.stack([g, np.full(len(ts), mi), ts * dt, np.full(len(ts), side[x]), zx, zy, dist,
                                     sgn * (pi[:, 2] - pj[:, 2]), lx, ly, hp[ts, x], ar[ts, x], hp[ts, y], ar[ts, y],
                                     wp[ts, x], wp[ts, y], vis[ts, x], vis[ts, y], dx, dy, ddx, ddy, m1, m2], 1))
    R = np.concatenate(out).astype(np.float32)
    np.savez_compressed(os.path.join(a.out, "rows_{}.npz".format(a.map)), rows=R, cols=np.array(COLS), zones=Z.k,
                        names=np.array(Z.names), every=a.every, h=a.h, rec=a.rec)
    print("{}: {} files, {} rows; an exchange in {:.1f}% of them, a death in {:.1f}%".format(
        a.map, len(files), len(R), 100 * ((R[:, C["dmg_ij"]] + R[:, C["dmg_ji"]]) >= CONTACT).mean(),
        100 * ((R[:, C["die_i"]] + R[:, C["die_j"]]) > 0).mean()), flush=True)


def rows(a):
    a.out = a.out or os.path.join(a.rec, "space")
    os.makedirs(a.out, exist_ok=True)
    maps = sorted({os.path.basename(f).split("_")[1] for f in glob.glob(os.path.join(a.rec, "rec_*.npz"))})
    procs = []
    for mp in maps:
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "rows1", a.rec, "--map", mp, "--out", a.out,
                                       "--every", str(a.every), "--h", str(a.h)], creationflags=0x4000 if os.name == "nt" else 0))
        while sum(p.poll() is None for p in procs) >= a.par:
            procs[0].wait() if procs[0].poll() is None else [p.wait() for p in procs if p.poll() is None][:1]
    bad = [p.wait() for p in procs]
    print("rows done: {} maps, exit codes {}".format(len(maps), sorted(set(bad))))


def prorows_map(a):
    """the pros' rows from the demos, through tools/pro_moments.py's frames (its `tracks`): the followed player exact, his enemy's
    place and weapon the game's while he is sent, the enemy's stack worked out (pro_moments: his pickups, the hits on him, his pain
    sounds). The damage in the window: the followed player's hits by the weapon in his hand (pro_moments' DMG_HIT and DMG_SCALE:
    an estimate) and the fall of his own health and armor. Each row from both seats (side 0 the followed player, 1 his enemy)"""
    import tempfile
    from collections import Counter
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import pro_moments as PM                                  # (sets its own switches before the simulator loads)
    PM.low_priority()
    rng = np.random.default_rng(a.seed)
    dd = os.path.join(PM.demo_root(), "demos", a.map)
    pick = list(rng.permutation(sorted(glob.glob(os.path.join(dd, "*.dm_91"))) + sorted(glob.glob(os.path.join(dd, "*.dm_90")))))
    if a.demos:
        pick = pick[:a.demos]
    MI = PM.MapInfo(a.map)
    E, env = MI.E, MI.env
    Z = ZM.load(a.map)
    mi = ZM.MAPS.index(a.map)
    counts, out, sigs = Counter(), [], set()
    tmp = tempfile.mkdtemp(prefix="spx_")
    eye, body = np.array([0, 0, float(E.VIEW_H)], np.float32), np.array([0, 0, 8.0], np.float32)
    stride = int(round(a.every / 0.025))
    for nd, demo in enumerate(pick):
        tr = {}
        try:
            PM.one_demo(MI, demo, tmp, 4.0, 2.0, rng, counts, tracks=tr)
        except Exception:                                     # noqa: BLE001 (a broken demo must not stop the map)
            counts["error"] += 1
            continue
        if "rec" not in tr or tr["rec"].get("hits") is None:
            counts["no frames or no hit counter"] += 1
            continue
        rec, en, T, dth = tr["rec"], tr["en"], np.asarray(tr["T"], np.float64), tr["dth"]
        cn, other = np.asarray(tr["cn"]).astype(int), np.asarray(tr["other"]).astype(int)
        sig = tuple(round(float(x), 0) for cl in sorted(dth) for x in dth[cl][:8])     # (two recordings of one game: one kept)
        if sig in sigs and len(sig) > 4:
            counts["a second recording"] += 1
            continue
        sigs.add(sig)
        N = len(T)
        hp, ar = np.asarray(rec["health"], np.float32), np.asarray(rec["armor"], np.float32)
        wp, seg, hits = np.asarray(rec["weapon"]).astype(int), np.asarray(rec["seg"]), np.asarray(rec["hits"], np.float64)
        eh, ea = np.asarray(tr["eh"], np.float32), np.asarray(tr["ea"], np.float32)
        same = np.zeros(N, bool)
        same[1:] = (seg[1:] == seg[:-1]) & (cn[1:] == cn[:-1])
        dealt = np.zeros(N)
        for f in np.nonzero(same & (np.diff(hits, prepend=hits[0]) > 0))[0]:
            dealt[f] = (hits[f] - hits[f - 1]) * float(PM.DMG_HIT[int(wp[f])]) * PM.DMG_SCALE
        st = hp + ar
        taken = np.zeros(N)
        taken[1:] = np.where(same[1:], np.maximum(0.0, st[:-1] - st[1:]), 0.0)
        taken[taken < 2.0] = 0.0                              # (the tick down above 100)
        cd, ctk = np.concatenate([[0.0], np.cumsum(dealt)]), np.concatenate([[0.0], np.cumsum(taken)])
        cuts = np.cumsum(np.concatenate([[0], (cn[1:] != cn[:-1]).astype(int)]))
        fs = np.arange(stride, N - 1, stride)
        ok = np.isfinite(en["pos"][fs]).all(1) & (hp[fs] > 0) & np.asarray(rec["alive"], bool)[fs] & (eh[fs] > 0) & \
            np.isfinite(np.asarray(tr["clock"], np.float64)[fs]) & ~np.asarray(tr["tele"], bool)[fs]
        fs = fs[ok]
        if not len(fs):
            continue
        dm, do, dead_op = np.full(len(fs), np.inf), np.full(len(fs), np.inf), np.zeros(len(fs), bool)
        for cl in dth:                                        # each one's next death after the frame; the enemy dead at the frame
            ds = np.array(dth[cl], np.float64)
            if not len(ds):
                continue
            j_ = np.searchsorted(ds, T[fs], side="right")
            nx = np.where(j_ < len(ds), ds[np.minimum(j_, len(ds) - 1)], np.inf)
            was = (j_ > 0) & (T[fs] - ds[np.maximum(j_ - 1, 0)] < 2.0)
            dm = np.where(cn[fs] == cl, nx, dm)
            do = np.where(other[fs] == cl, nx, do)
            dead_op |= (other[fs] == cl) & was
        te = np.minimum(np.minimum(dm, do), T[fs] + a.h)
        fe = np.clip(np.searchsorted(T, te, side="right") - 1, 0, N - 1)
        good = ~dead_op & (T[fe] >= te - 0.2) & (cuts[fe] == cuts[fs])
        di = (dm <= T[fs] + a.h) & (dm <= do)
        dj = (do <= T[fs] + a.h) & (do < dm)
        fs, fe, di, dj = fs[good], fe[good], di[good], dj[good]
        if not len(fs):
            continue
        pi, pj = np.asarray(rec["pos"], np.float32)[fs], np.asarray(en["pos"], np.float32)[fs]
        lij, lji = env._los(pi + eye, pj + body), env._los(pj + eye, pi + body)
        zi, zj = Z.locate(pi), Z.locate(pj)
        dist = np.linalg.norm(pi - pj, axis=1)
        dij, dji = cd[fe + 1] - cd[fs + 1], ctk[fe + 1] - ctk[fs + 1]
        wj = np.where(en["wpn"][fs] >= 0, en["wpn"][fs], E.MG)
        n_ = len(fs)
        g = np.full(n_, float(nd))
        back = np.maximum(fs - 40, 0)                         # how far each moved in the second before (nan: not known)
        okb = cuts[back] == cuts[fs]
        mvi = np.where(okb, np.linalg.norm(pi - np.asarray(rec["pos"], np.float32)[back], axis=1), np.nan)
        mvj = np.where(okb, np.linalg.norm(pj - np.asarray(en["pos"], np.float32)[back], axis=1), np.nan)
        for (sd_, zx, zy, sgn, lx, ly, h1, a1, h2, a2, w1, w2, d1, d2, x1, x2, m1, m2) in (
                (0, zi, zj, 1.0, lij, lji, hp[fs], ar[fs], eh[fs], ea[fs], wp[fs], wj, di, dj, dij, dji, mvi, mvj),
                (1, zj, zi, -1.0, lji, lij, eh[fs], ea[fs], hp[fs], ar[fs], wj, wp[fs], dj, di, dji, dij, mvj, mvi)):
            out.append(np.stack([g, np.full(n_, mi), T[fs], np.full(n_, sd_), zx, zy, dist, sgn * (pi[:, 2] - pj[:, 2]), lx, ly,
                                 h1, a1, h2, a2, w1, w2, lx, ly, d1, d2, x1, x2, m1, m2], 1))
        counts["games"] += 1
        if nd % 20 == 0:
            print("{} {}/{} games {} rows {}".format(a.map, nd + 1, len(pick), counts["games"], sum(len(o) for o in out)), flush=True)
    R = np.concatenate(out).astype(np.float32)
    os.makedirs(a.out, exist_ok=True)
    np.savez_compressed(os.path.join(a.out, "rows_{}.npz".format(a.map)), rows=R, cols=np.array(COLS), zones=Z.k,
                        names=np.array(Z.names), every=a.every, h=a.h, rec="pro demos", counts=json.dumps(dict(counts)))
    print("{}: {} demos, {} games, {} rows; an exchange in {:.1f}%, a death in {:.1f}%; {}".format(
        a.map, len(pick), counts["games"], len(R), 100 * ((R[:, C["dmg_ij"]] + R[:, C["dmg_ji"]]) >= CONTACT).mean(),
        100 * ((R[:, C["die_i"]] + R[:, C["die_j"]]) > 0).mean(),
        {k: v for k, v in counts.items() if k in ("error", "a second recording", "no frames or no hit counter", "parser", "no game")}),
        flush=True)


def prorows(a):
    import time
    procs = []
    for mp in a.maps.split(","):
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "prorows1", "--map", mp, "--out", a.out,
                                       "--every", str(a.every), "--h", str(a.h), "--demos", str(a.demos)],
                                      creationflags=0x4000 if os.name == "nt" else 0))
        while sum(p.poll() is None for p in procs) >= a.par:
            time.sleep(2)
    print("pro rows done: exit codes {}".format(sorted(set(p.wait() for p in procs))))


# ------------------------------------------------------------------------------------------------------------------- fit
def load_rows(dirs):
    R, tag = [], []
    for q, d in enumerate(dirs):
        for f in sorted(glob.glob(os.path.join(d, "rows_*.npz"))):
            r = np.load(f, allow_pickle=True)["rows"].astype(np.float64)
            r[:, C["game"]] += 1e6 * q + 1e4 * r[:, C["map"]]  # a game's number, its own over maps and folders
            R.append(r)
            tag.append((d, os.path.basename(f), len(r)))
    return np.concatenate(R), tag


def feats(R):
    """S: the stacks and weapons; G: the geometry; the map and the two zones as numbers (for the learned part)"""
    ei, ej = eff(R[:, C["hp_i"]], R[:, C["ar_i"]]), eff(R[:, C["hp_j"]], R[:, C["ar_j"]])
    oh = np.zeros((len(R), 2 * NW))
    oh[np.arange(len(R)), R[:, C["w_i"]].astype(int).clip(0, NW - 1)] = 1
    oh[np.arange(len(R)), NW + R[:, C["w_j"]].astype(int).clip(0, NW - 1)] = 1
    S = np.concatenate([np.stack([ei / 200, ej / 200, np.log((ei + 25) / (ej + 25)), R[:, C["hp_i"]] / 100, R[:, C["ar_i"]] / 100,
                                  R[:, C["hp_j"]] / 100, R[:, C["ar_j"]] / 100], 1), oh], 1)
    d = R[:, C["dist"]]
    G = np.stack([d / 1000, np.minimum(d, 3000.0) ** 0.5 / 30, 200.0 / (d + 200.0), R[:, C["dz"]] / 200,
                  R[:, C["los_ij"]], R[:, C["los_ji"]]], 1)
    zid = np.stack([R[:, C["map"]] * ZM.MAX_Z + R[:, C["zi"]], R[:, C["map"]] * ZM.MAX_Z + R[:, C["zj"]]], 1).astype(np.int64)
    return S.astype(np.float32), G.astype(np.float32), zid


def labels(R):
    cls = np.where(R[:, C["die_i"]] > 0, 0, np.where(R[:, C["die_j"]] > 0, 1, 2))        # (a trade on one frame: his own death)
    swing = np.clip(R[:, C["dmg_ij"]] - R[:, C["dmg_ji"]], -300, 300) / 100
    contact = ((R[:, C["dmg_ij"]] + R[:, C["dmg_ji"]]) >= CONTACT).astype(np.float32)
    return cls.astype(np.int64), swing.astype(np.float32), contact


def make_net(kind, ns, ng, emb=6):
    import torch
    import torch.nn as nn

    class X(nn.Module):
        def __init__(self):
            super().__init__()
            self.kind = kind
            nin = ns + (ng if kind in ("SG", "SGZ") else 0) + (2 * emb if kind == "SGZ" else 0)
            self.zi = nn.Embedding(len(ZM.MAPS) * ZM.MAX_Z, emb) if kind == "SGZ" else None
            self.zj = nn.Embedding(len(ZM.MAPS) * ZM.MAX_Z, emb) if kind == "SGZ" else None
            if self.zi is not None:
                nn.init.zeros_(self.zi.weight)
                nn.init.zeros_(self.zj.weight)
            self.f = nn.Sequential(nn.Linear(nin, 96), nn.ReLU(), nn.Linear(96, 96), nn.ReLU(), nn.Linear(96, 5))

        def forward(self, S, G, zid):
            x = [S]
            if self.kind in ("SG", "SGZ"):
                x.append(G)
            if self.kind == "SGZ":
                x += [self.zi(zid[:, 0]), self.zj(zid[:, 1])]
            o = self.f(torch.cat(x, 1))
            return o[:, :3], o[:, 3], o[:, 4]                 # who dies first (3 logits), the swing / 100, an exchange (logit)
    return X()


def scores(net, S, G, zid, cls, swing, contact):
    import torch
    import torch.nn.functional as F
    with torch.no_grad():
        lo, sw, ct = net(S, G, zid)
        p = torch.softmax(lo, 1)
        ll = float(F.cross_entropy(lo, cls))
        br = float(((p - F.one_hot(cls, 3).float()) ** 2).sum(1).mean())
        r2 = 1.0 - float(((sw - swing) ** 2).mean() / swing.var())
        cb = float(((torch.sigmoid(ct) - contact) ** 2).mean())
    return ll, br, r2, cb


def fit(a):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(1)
    torch.set_num_threads(4)
    R, tag = load_rows(a.rows)
    for t in tag:
        print("rows: {} {} {}".format(*t))
    S, G, zid = feats(R)
    cls, swing, contact = labels(R)
    games = np.unique(R[:, C["game"]])
    rng = np.random.default_rng(7)
    u = rng.random(len(games))
    part = dict(zip(games, np.where(u < 0.6, 0, np.where(u < 0.8, 1, 2))))               # by game: fit / stop / held out
    pt = np.array([part[g] for g in R[:, C["game"]]])
    mu, sd = S[pt == 0].mean(0), S[pt == 0].std(0) + 1e-6
    T = lambda x: torch.as_tensor(x)                          # noqa: E731
    St, Gt, Zt, ct_, sw_, co_ = T((S - mu) / sd), T(G), T(zid), T(cls), T(swing), T(contact)
    idx = [torch.as_tensor(np.nonzero(pt == k)[0]) for k in range(3)]
    print("{} rows of {} games: fit {}, stop {}, held out {}".format(len(R), len(games), *[len(i) for i in idx]))
    base = np.bincount(cls[pt == 0], minlength=3) / (pt == 0).sum()
    ho = cls[pt == 2]
    print("held out, who dies first within the window (he / the enemy / nobody): {:.3f} / {:.3f} / {:.3f}".format(
        *(np.bincount(ho, minlength=3) / len(ho))))
    b_ll = float(-np.log(base[ho]).mean())
    b_br = float(((base[None] - np.eye(3)[ho]) ** 2).sum(1).mean())
    b_cb = float(((contact[pt == 0].mean() - contact[pt == 2]) ** 2).mean())
    print("\n{:>22} | {:>8} {:>8} | {:>9} | {:>9}".format("held-out games", "log loss", "Brier", "swing R2", "exch. Brier"))
    print("{:>22} | {:>8.4f} {:>8.4f} | {:>9.3f} | {:>9.4f}".format("the base rate", b_ll, b_br, 0.0, b_cb))
    best_all = {}
    for kind, nm in (("S", "stacks and weapons"), ("SG", "+ the geometry"), ("SGZ", "+ a part by zone")):
        net = make_net(kind, S.shape[1], G.shape[1])
        opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-5)
        best, keep = 1e9, None
        for ep in range(a.epochs):
            perm = idx[0][torch.randperm(len(idx[0]))]
            for b in range(0, len(perm), 1024):
                k = perm[b:b + 1024]
                lo, sw, ct = net(St[k], Gt[k], Zt[k])
                loss = F.cross_entropy(lo, ct_[k]) + 0.5 * F.smooth_l1_loss(sw, sw_[k]) + \
                    0.5 * F.binary_cross_entropy_with_logits(ct, co_[k])
                opt.zero_grad()
                loss.backward()
                opt.step()
            v = scores(net, St[idx[1]], Gt[idx[1]], Zt[idx[1]], ct_[idx[1]], sw_[idx[1]], co_[idx[1]])
            if v[0] < best:
                best, keep = v[0], {k_: v_.clone() for k_, v_ in net.state_dict().items()}
        net.load_state_dict(keep)
        s = scores(net, St[idx[2]], Gt[idx[2]], Zt[idx[2]], ct_[idx[2]], sw_[idx[2]], co_[idx[2]])
        print("{:>22} | {:>8.4f} {:>8.4f} | {:>9.3f} | {:>9.4f}".format(nm, *s))
        best_all[kind] = keep
    # the geometry a zone pair has in these games (for the zones table and for reading X at a place he is not in)
    key = zid[:, 0] * 10000 + zid[:, 1]
    uk, inv = np.unique(key, return_inverse=True)
    pair = np.stack([uk // 10000, uk % 10000, np.bincount(inv)] + [np.bincount(inv, G[:, c]) / np.bincount(inv)
                                                                   for c in range(G.shape[1])], 1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    torch.save(dict(nets=best_all, mu=mu, sd=sd, ns=S.shape[1], ng=G.shape[1], pair=pair, rows=[list(t) for t in tag],
                    cols=list(COLS)), a.out)
    print("\nwritten: " + a.out)


def load_model(path, kind="SGZ"):
    import torch
    m = torch.load(path, map_location="cpu", weights_only=False)
    net = make_net(kind, m["ns"], m["ng"])
    net.load_state_dict(m["nets"][kind])
    net.eval()
    return m, net


def predict(m, net, R):
    """per row: P(he dies first), P(the enemy dies first), the swing he can expect (damage, his less the enemy's), P(an exchange)"""
    import torch
    S, G, zid = feats(R)
    with torch.no_grad():
        lo, sw, ct = net(torch.as_tensor((S - m["mu"]) / m["sd"]), torch.as_tensor(G), torch.as_tensor(zid))
        p = torch.softmax(lo, 1).numpy()
    return p[:, 0], p[:, 1], 100 * sw.numpy(), torch.sigmoid(ct).numpy()


# ----------------------------------------------------------------------------------------------------------------- zones
def zones(a):
    """a zone's hold at level stacks: both at 100 / 50 with the same weapon in hand (--weapon, duel_env's number: 2 the lightning
    gun), over the zones that see it in these games, weighted by how often the pair is seen"""
    m, net = load_model(a.model)
    pair = m["pair"]
    for mi, mp in enumerate(ZM.MAPS):
        Z = ZM.load(mp)
        sel = pair[(pair[:, 0] // ZM.MAX_Z == mi) & (pair[:, 2] >= a.min_rows)]
        if Z is None or not len(sel):
            continue
        R = np.zeros((len(sel), len(COLS)))
        R[:, C["map"]] = mi
        R[:, C["zi"]], R[:, C["zj"]] = sel[:, 0] % ZM.MAX_Z, sel[:, 1] % ZM.MAX_Z
        R[:, C["hp_i"]] = R[:, C["hp_j"]] = 100
        R[:, C["ar_i"]] = R[:, C["ar_j"]] = 50
        R[:, C["w_i"]] = R[:, C["w_j"]] = a.weapon
        R[:, C["dist"]] = sel[:, 3] * 1000
        R[:, C["dz"]] = sel[:, 6] * 200
        R[:, C["los_ij"]], R[:, C["los_ji"]] = sel[:, 7], sel[:, 8]
        pd_, pk_, sw, ct = predict(m, net, R)
        w = sel[:, 2] * sel[:, 7].clip(0.02)                  # pairs in sight count
        rows_ = []
        for z in range(Z.k):
            q = R[:, C["zi"]] == z
            if q.sum() < 2:
                continue
            ww = w[q] / w[q].sum()
            rows_.append((float((sw[q] * ww).sum()), float(((pk_[q] - pd_[q]) * ww).sum()), float((ct[q] * ww).sum()),
                          int(q.sum()), z, Z.names[z] or "-"))
        rows_.sort()
        print("\n{}: zones from the least holdable (the swing he can expect standing there, level stacks)".format(mp))
        for sw_, kd, c_, n_, z, nm in rows_:
            print("  zone {:>2} {:<8} swing {:>+6.1f}  kills less deaths {:>+6.3f}  an exchange {:>4.0f}%  ({} zones see it)".format(
                z, nm, sw_, kd, 100 * c_, n_))


# --------------------------------------------------------------------------------------------------------------- measure
def measure(a):
    m, net = load_model(a.model)
    _, net_s = load_model(a.model, "S")
    R, tag = load_rows([a.rows])
    if a.side >= 0:
        R = R[R[:, C["side"]] == a.side]
    pd_, pk_, sw, ct = predict(m, net, R)
    _, _, sw_s, _ = predict(m, net_s, R)
    ei, ej = eff(R[:, C["hp_i"]], R[:, C["ar_i"]]), eff(R[:, C["hp_j"]], R[:, C["ar_j"]])
    band = np.digitize(ei / np.maximum(ej, 1.0), BANDS) - 1
    ground = np.where(ct < a.quiet, 0, np.where(sw > a.edge, 1, np.where(sw < -a.edge, 3, 2)))   # quiet, his, contested, the enemy's
    print("{} rows (side {}); ground by X: quiet = an exchange under {:.0f}%, his / the enemy's = a swing over {:.0f}".format(
        len(R), a.side, 100 * a.quiet, a.edge))
    print("\n{:>11} | {:>6} | {:>6} {:>6} {:>9} {:>8} | {:>12} | {:>10}".format(
        "his / enemy", "rows", "quiet", "his", "contested", "enemy's", "places add", "died first"))
    for b, nm in enumerate(BAND_NAMES):
        q = band == b
        if q.sum() < 50:
            continue
        print("{:>11} | {:>6} | {:>5.1f}% {:>5.1f}% {:>8.1f}% {:>7.1f}% | {:>+12.1f} | {:>9.1f}%".format(
            nm, int(q.sum()), *[100 * (ground[q] == g).mean() for g in range(4)], float((sw[q] - sw_s[q]).mean()),
            100 * R[q, C["die_i"]].mean()))
    # entries: he was in quiet ground a row ago (the same game, the next sample) and is in the enemy's now
    t_ = R[:, C["t"]]                                          # (a game's seat's rows lie together, in the order of time)
    prev_ok = np.zeros(len(R), bool)
    step = float(np.median(np.diff(np.unique(t_)))) if len(R) > 2 else 0.5
    same = np.zeros(len(R), bool)
    same[1:] = (R[1:, C["game"]] == R[:-1, C["game"]]) & (np.abs(t_[1:] - t_[:-1] - step) < 1e-3)
    prev_ok[1:] = same[1:] & (ground[:-1] != 3)
    ent = prev_ok & (ground == 3)
    games = len(np.unique(R[:, C["game"]]))
    print("\nentries into the enemy's ground (not there a sample before), by his stack against the enemy's:")
    for b, nm in enumerate(BAND_NAMES):
        q = ent & (band == b)
        if q.sum() < 20:
            continue
        print("  {:>11}: {:>5.1f} a game; he died first {:>5.1f}%, the enemy {:>5.1f}%, nobody {:>5.1f}%; swing {:>+6.1f} (X said {:>+6.1f})".format(
            nm, q.sum() / games, 100 * R[q, C["die_i"]].mean(), 100 * (R[q, C["die_j"]] * (1 - R[q, C["die_i"]])).mean(),
            100 * ((R[q, C["die_i"]] + R[q, C["die_j"]]) == 0).mean(), float((R[q, C["dmg_ij"]] - R[q, C["dmg_ji"]]).mean()),
            float(sw[q].mean())))
    q = (ground == 1) & (R[:, C["los_ij"]] > 0)
    if q.sum() >= 20:
        print("\nan enemy in his ground and in his line of sight ({:.1f} samples a game): he dealt {:.0f} or more in the window {:.1f}%; "
              "the enemy died {:.1f}%, left alive {:.1f}%".format(q.sum() / games, CONTACT, 100 * (R[q, C["dmg_ij"]] >= CONTACT).mean(),
                                                               100 * R[q, C["die_j"]].mean(), 100 * (1 - R[q, C["die_j"]]).mean()))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("rows", "rows1"):
        p = sp.add_parser(nm)
        p.add_argument("rec")
        p.add_argument("--out", default="")
        p.add_argument("--every", type=float, default=0.5)
        p.add_argument("--h", type=float, default=5.0)
        p.add_argument("--par", type=int, default=4)
        p.add_argument("--map", default="")
    for nm in ("prorows", "prorows1"):
        p = sp.add_parser(nm)
        p.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure")
        p.add_argument("--map", default="")
        p.add_argument("--out", default=os.path.join(ROOT, "data", "sim_runs", "space", "pro_rows"))
        p.add_argument("--demos", type=int, default=150)
        p.add_argument("--every", type=float, default=0.5)
        p.add_argument("--h", type=float, default=5.0)
        p.add_argument("--par", type=int, default=4)
        p.add_argument("--seed", type=int, default=1)
    p = sp.add_parser("fit")
    p.add_argument("rows", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--epochs", type=int, default=30)
    p = sp.add_parser("zones")
    p.add_argument("model")
    p.add_argument("--weapon", type=int, default=2)
    p.add_argument("--min-rows", type=int, default=30)
    p = sp.add_parser("measure")
    p.add_argument("model")
    p.add_argument("rows")
    p.add_argument("--side", type=int, default=-1)
    p.add_argument("--quiet", type=float, default=0.2)
    p.add_argument("--edge", type=float, default=15.0)
    a = ap.parse_args()
    dict(rows=rows, rows1=rows_map, prorows=prorows, prorows1=prorows_map, fit=fit, zones=zones, measure=measure)[a.cmd](a)


if __name__ == "__main__":
    main()

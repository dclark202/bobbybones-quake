"""A score for every place on a map of how bad it is to hang out in (docs/design/SPACE.md; owner, 2026-11-09: "We need a score per
place on the map of how 'bad' that is to just hang out in ... Test it against the pros too"). First pass, from the map alone:

  for every walking point i (data/maps/nav_<map>_sim.json) and every point j that sees it (an eye at j, his body at i, the simulator's
  own line of sight with the games' switches): the seconds of walking from i to the nearest point j does not see (the walking map's
  own link times). The score B(i) = the mean over ALL points j of those seconds, capped at CAP (a point that does not see him: 0).
  So B is "an enemy turns up somewhere on the map: how long am I in his sight before I can be out of it", in seconds: many
  sightlines and far cover both raise it. Kept beside it: seen (the share of the map's points that see him), cover (the mean seconds
  to cover from those that do), near (the share within 1000 units that see him).

    python tools/run/space_score.py score [--maps a,b] [--par 4]         data/maps/space_<map>.npz (one process a map)
    python tools/run/space_score.py zones [--maps a,b]                   the score by zone (sim/zones), the worst first
    python tools/run/space_score.py test --rec <recdir> [--maps a,b] [--demos 150]
        where the pros stand (the demo sets' frames, <demo root>/sets_lite) and where he does (cypher_measure.py sim's records):
        by the map's own fifths of B, the share of time, of standing time (moved under STILL units in the last second), and the
        damage taken a minute, all with the enemy near (within NEAR units; the pros': and sent by the server)
    python tools/run/space_score.py draw [--maps a,b]                    docs/design/space/<map>.png
Nothing here touches a run: it traces lines on the map and reads records and demo sets."""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity,cure"
CAP = 3.0                                                     # seconds: beyond this a place is as bad as it gets
STILL, NEAR = 120.0, 1500.0
REACH = 1.5                                                   # seconds: the ground the enemy can be on from where he is
FWD = 2.0                                                     # seconds ahead for "what it brought"
FWDF = int(round(FWD / 0.025))
CTRL = 2.0                                                    # damage a second: the margin by which a place is covered by one of them
SETS = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "cypher", "u90", "meta.json")   # the games' switches (the sight's mask)
WZ = np.array([1.0, 1.0, 2.0])                                # height counted double in "the nearest point" (RouteField's rule)


def path(mp):
    return os.path.join(ROOT, "data", "maps", "space_{}.npz".format(mp))


def score_map(a):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    for s in json.load(open(SETS))["sets"]:
        k, v = s.split("=", 1)
        os.environ[k] = v
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1")
    import duel_env as D
    env = D.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=0)
    g = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))))
    P = np.array(g["nodes"], np.float32)
    n = len(P)
    eye, body = np.array([0, 0, float(D.VIEW_H)], np.float32), np.array([0, 0, 8.0], np.float32)
    t0 = time.time()
    V = np.zeros((n, n), bool)                                # V[j, i]: an eye at j sees a body at i
    for j in range(n):
        V[j] = env._los(np.repeat((P[j] + eye)[None], n, 0), P + body)
    V |= V.T                                                  # (either way: a shot goes both ways)
    np.fill_diagonal(V, True)
    e = [x for x in g["edges"] if x[3] in ("walk", "air")]
    ea, eb, ec = np.array([x[0] for x in e]), np.array([x[1] for x in e]), np.array([max(1e-3, float(x[2])) for x in e])
    tl = [x for x in g["edges"] if x[3] == "tele"] if os.environ.get("SPACE_TELE", "1") != "0" else []
    ta, tb, tc = (np.array([x[k] for x in tl], float if k == 2 else np.int64) for k in range(3))   # teleporters: one way
    A = coo_matrix((np.r_[ec, ec, np.maximum(tc, 1e-3)], (np.r_[ea, eb, ta].astype(np.int64), np.r_[eb, ea, tb].astype(np.int64))),
                   shape=(n, n)).tocsr()                       # A[u, v]: seconds from u to v
    AT = A.T.tocsr()
    cov = np.zeros((n, n), np.float32)                        # cov[j, i]: seconds from i to the nearest point j does not see
    for j in range(n):
        un = np.nonzero(~V[j])[0]
        if not len(un):
            cov[j] = CAP
            continue
        d = dijkstra(AT, directed=True, indices=un, min_only=True)   # (the links turned round: from i to the nearest of them)
        cov[j] = np.minimum(np.where(np.isfinite(d), d, CAP), CAP)
    cov[~V] = 0.0
    dist = np.linalg.norm(P[:, None] - P[None], axis=2)
    B = cov.mean(0)
    seen = V.mean(0)
    cover = cov.sum(0) / np.maximum(V.sum(0), 1)
    nr = dist < 1000.0
    near = (V & nr).sum(0) / np.maximum(nr.sum(0), 1)
    # the enemy's reach: where he can be within REACH seconds of walking from j. see[j, i]: the share of that ground that sees i;
    # thr[j, i]: the seconds to cover from it, on average ("he is somewhere round j: how exposed is i"). A belief about the enemy
    # that is a spread of places is read the same way: the mean of cov over the places he may be
    Dw = dijkstra(A, directed=True)
    R = (Dw <= REACH).astype(np.float32)
    cnt = np.maximum(R.sum(1, keepdims=True), 1.0)
    see = (R @ V.astype(np.float32)) / cnt
    thr = (R @ cov) / cnt
    # the same share cut by the distance of the sight line (DBAND): what a weapon's reach makes of it (the weapon table's bands)
    db = np.digitize(dist, DBAND)
    seeb = np.stack([(R @ (V & (db == q)).astype(np.float32)) / cnt for q in range(3)])
    # for the simulator (sim/space.py: plain numpy, no tree): the nearest walking point of every 32-unit cell (the zones' own grid),
    # and the tables by zone: tz[q, from, zone] = the mean of seeb over the zone's points (the threat a player round `from` puts on
    # a zone, by the line's length); the nearest lower-threat place is read from the points' neighbours (nb: up to NB a point)
    from scipy.spatial import cKDTree
    import zonemap as ZM
    Z = ZM.load(a.map)
    zn = Z.locate(P)
    gi = np.stack(np.meshgrid(*[np.arange(d_) for d_ in Z.dims], indexing="ij"), -1).reshape(-1, 3)
    cen = Z.lo + (gi + 0.5) * Z.cell
    grid = cKDTree(P * WZ).query(cen * WZ)[1].astype(np.int16).reshape(tuple(Z.dims))
    M = np.zeros((n, Z.k), np.float32)
    M[np.arange(n), zn] = 1.0
    zsize = M.sum(0)
    M /= np.maximum(zsize, 1.0)
    tz = np.stack([seeb[q] @ M for q in range(3)])
    NB = 12
    nb = np.full((n, NB), -1, np.int32)
    Acsr = A.tocsr()
    for u in range(n):
        v = Acsr.indices[Acsr.indptr[u]:Acsr.indptr[u + 1]]
        w_ = Acsr.data[Acsr.indptr[u]:Acsr.indptr[u + 1]]
        v = v[np.argsort(w_)][:NB]
        nb[u, :len(v)] = v
    np.savez_compressed(path(a.map), nodes=P, B=B.astype(np.float32), seen=seen.astype(np.float32), cover=cover.astype(np.float32),
                        near=near.astype(np.float32), cap=CAP, cov8=np.round(cov * 80).astype(np.uint8),   # cov8[j, i] / 80: seconds
                        see8=np.round(see * 255).astype(np.uint8), thr8=np.round(thr * 80).astype(np.uint8), reach=REACH,
                        seeb8=np.round(seeb * 255).astype(np.uint8), grid=grid, lo=np.asarray(Z.lo, np.float64), cell=float(Z.cell),
                        zone=zn.astype(np.int16), zsize=zsize.astype(np.float32), tz8=np.round(tz * 255).astype(np.uint8), nb=nb,
                        dband=np.array(DBAND, np.float32), version=1)
    print("{}: {} points, {:.0f} s; B mean {:.2f} (a fifth's edges {}); seen {:.2f}, cover {:.2f} s".format(
        a.map, n, time.time() - t0, B.mean(), np.round(np.quantile(B, [0.2, 0.4, 0.6, 0.8]), 2).tolist(), seen.mean(), cover.mean()),
        flush=True)


def score(a):
    procs = []
    for mp in a.maps.split(","):
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "score1", "--map", mp],
                                      creationflags=0x4000 if os.name == "nt" else 0, stdin=subprocess.DEVNULL))
        while sum(p.poll() is None for p in procs) >= a.par:
            time.sleep(1)
    print("score done: exit codes {}".format(sorted(set(p.wait() for p in procs))))


class Score:
    def __init__(self, mp):
        from scipy.spatial import cKDTree
        d = np.load(path(mp))
        self.P, self.B, self.seen, self.cover = d["nodes"], d["B"], d["seen"], d["cover"]
        self.cov = d["cov8"] if "cov8" in d.files else None   # [the enemy's point, his point]: seconds to cover * 80, 0 = not seen
        self.see = d["see8"] if "see8" in d.files else None   # ... the share of the enemy's reach that sees him * 255
        self.seeb = d["seeb8"] if "seeb8" in d.files else None   # [band, from, onto]: that share by the sight line's length
        self.tree = cKDTree(self.P * WZ)
        self.edges = np.quantile(self.B, [0.2, 0.4, 0.6, 0.8])

    def at(self, pos):
        """the nearest walking point's number for each place (a player's origin is 24 above his feet's floor: close enough)"""
        return self.tree.query(np.asarray(pos, np.float64) * WZ)[1]


def zones(a):
    import zonemap as ZM
    for mp in a.maps.split(","):
        S, Z = Score(mp), ZM.load(mp)
        z = Z.locate(S.P)
        rows = sorted(((float(S.B[z == k].mean()), float(S.seen[z == k].mean()), float(S.cover[z == k].mean()), k, Z.names[k] or "-")
                       for k in range(Z.k) if (z == k).any()), reverse=True)
        print("\n{}: zones from the worst to hang out in (B: seconds in sight before cover, an enemy anywhere; the map's mean {:.2f})".format(
            mp, S.B.mean()))
        for b, s, c, k, nm in rows:
            print("  zone {:>2} {:<8} B {:.2f}   seen by {:>4.0f}% of the map, cover {:.2f} s away".format(k, nm, b, 100 * s, c))


def _acc():
    return dict(t=np.zeros(5), still=np.zeros(5), dmg=np.zeros(5), dmg_still=np.zeros(5), n=0, games=0, bsum=0.0, bstill=0.0,
                nstill=0, tall=np.zeros(5), stall=np.zeros(5))


EX_EDGES = (1e-6, 0.5, 1.0, 2.0)                              # seconds to cover from the enemy where he is: out of sight, then bands
EX_NAMES = ("not in sight", "under 0.5 s", "0.5 to 1 s", "1 to 2 s", "over 2 s")


SEE_EDGES = (0.004, 0.25, 0.5, 0.75)                          # the share of the enemy's reach that sees him
SEE_NAMES = ("none of it", "under 25%", "25 to 50%", "50 to 75%", "over 75%")
WPN = ((0, "rockets"), (2, "lightning"), (1, "rail"))        # duel_env's numbers
DBAND = (400.0, 768.0)
DNAMES = ("under 400", "400 to 768", "768 to 1500")


def _add(acc, S, pos, moved, near, taken, dt, en=None, enw=None, fwd=None):
    """one stretch of samples: pos [n, 3], moved in the last second, the enemy near, the damage taken since the last sample;
    en: the enemy's place (where known: the rows with `near`), enw: the weapon in his hand, fwd: the damage taken in the next
    FWD seconds (nan: not known)"""
    k = S.at(pos)
    if en is not None and S.cov is not None and near.any():
        kj = S.at(en[near])
        ex = S.cov[kj, k[near]] / 80.0
        if S.see is not None and fwd is not None:
            sb = np.digitize(S.see[kj, k[near]] / 255.0, SEE_EDGES)
            fw, okf = fwd[near], np.isfinite(fwd[near])
            hid = ex <= 0                                     # not in his sight now
            for q in range(5):
                for nm_, m in (("r_all", (sb == q) & okf), ("r_hid", (sb == q) & okf & hid)):
                    acc.setdefault(nm_ + "_n", np.zeros(5))[q] += m.sum()
                    acc.setdefault(nm_ + "_d", np.zeros(5))[q] += fw[m].sum()
                    acc.setdefault(nm_ + "_h", np.zeros(5))[q] += (fw[m] >= 20).sum()
        if enw is not None:
            dd = np.linalg.norm(pos[near] - en[near], axis=1)
            db = np.digitize(dd, DBAND)
            W = acc.setdefault("w", np.zeros((3, 3, 2)))
            for wi, (wn, _) in enumerate(WPN):
                for q in range(3):
                    m = (enw[near] == wn) & (db == q) & (ex > 0)
                    W[wi, q, 0] += dt * m.sum()
                    W[wi, q, 1] += taken[near][m].sum()
        eb = np.digitize(ex, EX_EDGES)
        st_ = (moved < STILL)[near]
        for q in range(5):
            m = eb == q
            acc.setdefault("et", np.zeros(5))[q] += dt * m.sum()
            acc.setdefault("es", np.zeros(5))[q] += dt * (m & st_).sum()
            acc.setdefault("ed", np.zeros(5))[q] += taken[near][m].sum()
    b = S.B[k]
    band = np.digitize(b, S.edges)
    still = moved < STILL
    for q in range(5):
        m = band == q
        acc["tall"][q] += dt * m.sum()
        acc["stall"][q] += dt * (m & still).sum()
        m &= near
        acc["t"][q] += dt * m.sum()
        acc["still"][q] += dt * (m & still).sum()
        acc["dmg"][q] += taken[m].sum()
        acc["dmg_still"][q] += taken[m & still].sum()
    acc["bsum"] += b[near].sum()
    acc["n"] += int(near.sum())
    acc["bstill"] += b[near & still].sum()
    acc["nstill"] += int((near & still).sum())


def _report(nm, acc, S_mean):
    t, st = acc["t"], acc["still"]
    print("\n{}: {} games; with the enemy near {:.0f} min, standing {:.1f}% of it".format(nm, acc["games"], t.sum() / 60, 100 * st.sum() / max(t.sum(), 1)))
    print("  {:>24} | {:>8} {:>8} {:>8} {:>8} {:>8}".format("the map's fifths of B", "safest", "2", "3", "4", "worst"))
    f = lambda x: " ".join("{:>8.1f}".format(v) for v in x)      # noqa: E731
    print("  {:>24} | {}".format("share of time, %", f(100 * t / max(t.sum(), 1))))
    print("  {:>24} | {}".format("share of standing, %", f(100 * st / max(st.sum(), 1))))
    print("  {:>24} | {}".format("standing there, % of it", f(100 * st / np.maximum(t, 1))))
    print("  {:>24} | {}".format("damage taken a minute", f(60 * acc["dmg"] / np.maximum(t, 1))))
    print("  {:>24} | {}".format("... while standing", f(60 * acc["dmg_still"] / np.maximum(st, 1))))
    print("  {:>24} | {}".format("standing, enemy anywhere", f(100 * acc["stall"] / max(acc["stall"].sum(), 1))))
    print("  mean B where he is {:.3f}, where he stands {:.3f} (the map's points: {:.3f})".format(
        acc["bsum"] / max(acc["n"], 1), acc["bstill"] / max(acc["nstill"], 1), S_mean))
    if "et" in acc:
        et, es, ed = acc["et"], acc["es"], acc["ed"]
        print("  against the enemy where he IS (seconds of walking to the nearest place he does not see):")
        print("  {:>24} | {}".format("", " ".join("{:>12}".format(x) for x in EX_NAMES)))
        g = lambda x: " ".join("{:>12.1f}".format(v) for v in x)   # noqa: E731
        print("  {:>24} | {}".format("share of time, %", g(100 * et / max(et.sum(), 1))))
        print("  {:>24} | {}".format("share of standing, %", g(100 * es / max(es.sum(), 1))))
        print("  {:>24} | {}".format("standing there, % of it", g(100 * es / np.maximum(et, 1))))
        print("  {:>24} | {}".format("damage taken a minute", g(60 * ed / np.maximum(et, 1))))
        ins = et[1:].sum()
        print("  in his sight {:.1f}% of the time near him; of that, over 1 s from cover {:.1f}%".format(
            100 * ins / max(et.sum(), 1), 100 * et[3:].sum() / max(ins, 1)))
    if "r_all_n" in acc:
        print("  against where the enemy CAN BE within {:.1f} s (the share of that ground that sees him), the next {:.0f} s:".format(REACH, FWD))
        print("  {:>24} | {}".format("", " ".join("{:>12}".format(x) for x in SEE_NAMES)))
        g = lambda x: " ".join("{:>12.1f}".format(v) for v in x)   # noqa: E731
        for nm_, lab in (("r_all", "all samples"), ("r_hid", "NOT in his sight now")):
            n_, d_, h_ = acc[nm_ + "_n"], acc[nm_ + "_d"], acc[nm_ + "_h"]
            print("  {:>24} | {}".format(lab + ": share, %", g(100 * n_ / max(n_.sum(), 1))))
            print("  {:>24} | {}".format("damage taken", g(d_ / np.maximum(n_, 1))))
            print("  {:>24} | {}".format("hit for 20 or more, %", g(100 * h_ / np.maximum(n_, 1))))
    if "w" in acc:
        W = acc["w"]
        print("  in the enemy's sight, damage taken a minute by the weapon in his hand and the distance (minutes of it):")
        for wi, (_, wn) in enumerate(WPN):
            print("  {:>24} | {}".format(wn, "   ".join("{} {:>6.0f} ({:>5.0f})".format(DNAMES[q], 60 * W[wi, q, 1] / max(W[wi, q, 0], 1), W[wi, q, 0] / 60)
                                                        for q in range(3))))


def test(a):
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    step = 10                                                 # a sample every 0.25 s
    back = 40
    dt = step * 0.025
    tot = dict(pros=_acc(), bobby=_acc())
    smean = []
    for mp in a.maps.split(","):
        S = Score(mp)
        smean.append(S.B.mean())
        per = dict(pros=_acc(), bobby=_acc())
        files = sorted(glob.glob(os.path.join(root, "sets_lite", mp, "*.npz")))
        rng = np.random.default_rng(1)
        for f in list(rng.permutation(files))[:a.demos]:
            d = np.load(f)
            L, first = d["lite"], d["first"]
            if len(L) < 400:
                continue
            seg = np.cumsum(first)
            pos, en, stack = L[:, 5:8], L[:, 8:11], L[:, 0] + L[:, 1]
            idx = np.arange(back, len(L), step)
            idx = idx[seg[idx] == seg[idx - back]]
            if not len(idx):
                continue
            moved = np.linalg.norm(pos[idx] - pos[idx - back], axis=1)
            near = (L[idx, 31] > 0) & (np.linalg.norm(pos[idx] - en[idx], axis=1) < NEAR)
            drop = np.maximum(0.0, stack[idx - step] - stack[idx])
            drop[(seg[idx] != seg[idx - step]) | (drop < 2.0)] = 0.0
            d1 = np.zeros(len(L))                             # the damage taken a frame, and what the next FWD seconds bring
            d1[1:] = np.where(seg[1:] == seg[:-1], np.maximum(0.0, stack[:-1] - stack[1:]), 0.0)
            d1[d1 < 2.0] = 0.0
            cum = np.concatenate([[0.0], np.cumsum(d1)])
            last = np.searchsorted(seg, seg[idx], side="right") - 1       # his stretch's last frame
            fwd = cum[np.minimum(idx + FWDF, last) + 1] - cum[idx + 1]
            _add(per["pros"], S, pos[idx], moved, near, drop, dt, en[idx], L[idx, 11].astype(int), fwd)
            per["pros"]["games"] += 1
        for f in sorted(glob.glob(os.path.join(a.rec, "rec_{}_*.npz".format(mp)))):
            d = np.load(f, allow_pickle=True)
            pos, alive = d["pos"].astype(np.float32), d["alive"]
            stack = d["hp"].astype(np.float32) + d["ar"].astype(np.float32)
            T, n = alive.shape
            idx = np.arange(back, T, step)
            for s in range(n):
                o = s ^ 1
                ok = alive[idx, s] & alive[idx - back, s] & (np.minimum.reduceat(alive[:, s].astype(np.int8), idx - back)[:len(idx)] > 0)
                ii = idx[ok]
                moved = np.linalg.norm(pos[ii, s] - pos[ii - back, s], axis=1)
                near = alive[ii, o] & (np.linalg.norm(pos[ii, s] - pos[ii, o], axis=1) < NEAR)
                drop = np.maximum(0.0, stack[ii - step, s] - stack[ii, s])
                drop[drop < 2.0] = 0.0
                d1 = np.zeros(T)
                d1[1:] = np.where(alive[:-1, s], np.maximum(0.0, stack[:-1, s] - np.maximum(stack[1:, s], 0.0)), 0.0)
                d1[d1 < 2.0] = 0.0
                cum = np.concatenate([[0.0], np.cumsum(d1)])
                fwd = cum[np.minimum(ii + FWDF, T - 1) + 1] - cum[ii + 1]
                _add(per["bobby"], S, pos[ii, s], moved, near, drop, dt, pos[ii, o], d["weapon"][ii, o].astype(int), fwd)
            per["bobby"]["games"] += n // 2
        for who in per:
            for k_, v in per[who].items():
                tot[who][k_] = tot[who].get(k_, 0) + v
        if a.by_map:
            _report("{} pros".format(mp), per["pros"], S.B.mean())
            _report("{} Bobby".format(mp), per["bobby"], S.B.mean())
    _report("ALL MAPS, the pros", tot["pros"], float(np.mean(smean)))
    _report("ALL MAPS, Bobby ({})".format(a.rec), tot["bobby"], float(np.mean(smean)))


# ------------------------------------------------------------------------------------------------------------- the edge
def _pro_samples(root, mp, files, step=10, back=40):
    for f in files:
        d = np.load(f)
        L, first = d["lite"], d["first"]
        if len(L) < 400:
            continue
        seg = np.cumsum(first)
        pos, en, stack = L[:, 5:8], L[:, 8:11], L[:, 0] + L[:, 1]
        idx = np.arange(back, len(L), step)
        idx = idx[seg[idx] == seg[idx - back]]
        if not len(idx):
            continue
        d1 = np.zeros(len(L))
        d1[1:] = np.where(seg[1:] == seg[:-1], np.maximum(0.0, stack[:-1] - stack[1:]), 0.0)
        d1[d1 < 2.0] = 0.0
        cum = np.concatenate([[0.0], np.cumsum(d1)])
        last = np.searchsorted(seg, seg[idx], side="right") - 1
        near = (L[idx, 31] > 0) & (np.linalg.norm(pos[idx] - en[idx], axis=1) < NEAR)
        yield dict(pos=pos[idx][near], en=en[idx][near], wme=L[idx, 2].astype(int)[near], wen=L[idx, 11].astype(int)[near],
                   moved=np.linalg.norm(pos[idx] - pos[idx - back], axis=1)[near],
                   now=(cum[idx + 1] - cum[idx - step + 1])[near], fwd=(cum[np.minimum(idx + FWDF, last) + 1] - cum[idx + 1])[near])


def _bobby_samples(rec, mp, step=10, back=40):
    for f in sorted(glob.glob(os.path.join(rec, "rec_{}_*.npz".format(mp)))):
        d = np.load(f, allow_pickle=True)
        pos, alive, wp = d["pos"].astype(np.float32), d["alive"], d["weapon"].astype(int)
        stack = d["hp"].astype(np.float32) + d["ar"].astype(np.float32)
        kills, dealt = d["kills"], d["dealt"].astype(np.float64)
        T, n = alive.shape
        idx = np.arange(back, T, step)
        for s in range(n):
            o = s ^ 1
            ii = idx[alive[idx, s] & alive[idx - back, s] & alive[idx, o]]
            ii = ii[np.linalg.norm(pos[ii, s] - pos[ii, o], axis=1) < NEAR]
            d1 = np.zeros(T)
            d1[1:] = np.where(alive[:-1, s], np.maximum(0.0, stack[:-1, s] - np.maximum(stack[1:, s], 0.0)), 0.0)
            d1[d1 < 2.0] = 0.0
            cum = np.concatenate([[0.0], np.cumsum(d1)])
            cdl = np.concatenate([[0.0], np.cumsum(dealt[:, s])])
            e2 = np.minimum(ii + FWDF, T - 1)
            fr = np.zeros(T + 1)                              # his frags less his deaths, counted up
            for t_, v_, k_ in kills:
                if 0 <= t_ < T:
                    fr[int(t_) + 1:] += (1.0 if int(k_) == s and int(v_) != s else 0.0) - (1.0 if int(v_) == s else 0.0)
            e30 = np.minimum(ii + 1200, T - 1)
            yield dict(pos=pos[ii, s], en=pos[ii, o], wme=wp[ii, s], wen=wp[ii, o],
                       moved=np.linalg.norm(pos[ii, s] - pos[ii - back, s], axis=1), now=cum[ii + 1] - cum[ii - step + 1],
                       fwd=cum[e2 + 1] - cum[ii + 1], dealt=cdl[e2 + 1] - cdl[ii + 1], net30=fr[e30 + 1] - fr[ii + 1],
                       eff=np.stack([stack[ii, s], stack[ii, o]], 1))


def _threat(S, W, frm, onto, wpn):
    """the damage a second a player round `frm` (anywhere he can be within REACH) puts on a place `onto`, by the weapon in his hand
    (W[weapon, band]: the pros' damage a second along a sight line of that length)"""
    w = W[np.clip(wpn, 0, len(W) - 1)]
    return sum(w[:, q] * S.seeb[q][frm, onto] / 255.0 for q in range(3))


def _bands(x, e):
    return np.digitize(x, e)


def edge(a):
    """the edge of a pair of places: the damage a second he puts on where the enemy is, less what the enemy puts on where he is, each
    over the ground the other can be on within REACH seconds and by the weapon in hand (the weapon table: the pros' damage a second
    in sight, by weapon and the length of the line, measured on the first half of the demos; everything else on the second half)"""
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    dt = 0.25
    maps = a.maps.split(",")
    Wt = np.zeros((9, 3, 2))
    half = {}
    for mp in maps:
        S = Score(mp)
        files = list(np.random.default_rng(1).permutation(sorted(glob.glob(os.path.join(root, "sets_lite", mp, "*.npz")))))[:a.demos]
        half[mp] = files[len(files) // 2:]
        for s in _pro_samples(root, mp, files[:len(files) // 2]):
            i, j = S.at(s["pos"]), S.at(s["en"])
            ins = S.cov[j, i] > 0
            q = np.digitize(np.linalg.norm(s["pos"] - s["en"], axis=1), DBAND)
            np.add.at(Wt, (np.clip(s["wen"], 0, 8)[ins], q[ins], 0), dt)
            np.add.at(Wt, (np.clip(s["wen"], 0, 8)[ins], q[ins], 1), s["now"][ins])
    W = Wt[:, :, 1] / np.maximum(Wt[:, :, 0], 1.0)
    W[Wt[:, :, 0] < 120] = np.nan                             # under two minutes of it: the weapon's own mean, or nothing
    for w_ in range(9):
        fill = Wt[w_, :, 1].sum() / max(Wt[w_, :, 0].sum(), 1.0)
        W[w_] = np.where(np.isfinite(W[w_]), W[w_], fill)
    names = ("rockets", "rail", "lightning", "machine gun", "shotgun", "grenades", "plasma", "hmg", "gauntlet")
    print("the weapon table (the pros, damage a second in sight; under 400 / 400 to 768 / over 768 units; minutes):")
    for w_ in range(9):
        print("  {:<12} {:>5.1f} {:>5.1f} {:>5.1f}   ({:.0f} / {:.0f} / {:.0f})".format(names[w_], *W[w_], *(Wt[w_, :, 0] / 60)))
    os.makedirs(os.path.join(ROOT, "data", "sim_runs", "space"), exist_ok=True)
    json.dump(dict(weapons=names, bands=list(DBAND), dmg_s=np.round(W, 2).tolist(), minutes=np.round(Wt[:, :, 0] / 60, 1).tolist()),
              open(os.path.join(ROOT, "data", "sim_runs", "space", "weapon_threat.json"), "w"), indent=1)
    TE = (2.0, 5.0, 10.0, 20.0)                               # the threat on him, damage a second
    EE = (-10.0, -3.0, 3.0, 10.0)                             # the edge
    CE = (-0.3, -0.1, 0.1, 0.3)                               # the map: his share less the enemy's
    acc = {}
    for who in ("pros", "bobby"):
        A = acc[who] = dict(tn=np.zeros(5), td=np.zeros(5), th=np.zeros(5), en=np.zeros(5), es=np.zeros(5), ed=np.zeros(5),
                            ex=np.zeros(5), cn=np.zeros(5), cs=np.zeros(5), c30=np.zeros(5), X=[], n=0)
        for mp in maps:
            S = Score(mp)
            gen = _pro_samples(root, mp, half[mp]) if who == "pros" else _bobby_samples(a.rec, mp)
            for s in gen:
                if not len(s["pos"]):
                    continue
                i, j = S.at(s["pos"]), S.at(s["en"])
                t_en = _threat(S, W, j, i, s["wen"])          # on him
                t_me = _threat(S, W, i, j, s["wme"])          # on the enemy
                e = t_me - t_en
                tb, eb = _bands(t_en, TE), _bands(e, EE)
                still = s["moved"] < STILL
                for q in range(5):
                    m = tb == q
                    A["tn"][q] += m.sum()
                    A["td"][q] += s["fwd"][m].sum()
                    A["th"][q] += (s["fwd"][m] >= 20).sum()
                    m = eb == q
                    A["en"][q] += m.sum()
                    A["es"][q] += (m & still).sum()
                    A["ed"][q] += s["fwd"][m].sum()
                    if "dealt" in s:
                        A["ex"][q] += (s["dealt"][m] - s["fwd"][m]).sum()
                A["n"] += len(i)
                if who == "bobby":                            # the whole map: the ground each covers better than the other
                    for c0 in range(0, len(i), 8 * 256):
                        k = np.arange(c0, min(len(i), c0 + 8 * 256), 8)
                        wm, we = W[np.clip(s["wme"][k], 0, 8)], W[np.clip(s["wen"][k], 0, 8)]
                        Tm = sum(wm[:, q, None] * S.seeb[q][i[k]] / 255.0 for q in range(3))
                        Te = sum(we[:, q, None] * S.seeb[q][j[k]] / 255.0 for q in range(3))
                        mine, his = (Tm - Te > CTRL).mean(1), (Te - Tm > CTRL).mean(1)
                        c = mine - his
                        cb = _bands(c, CE)
                        for q in range(5):
                            m = cb == q
                            A["cn"][q] += m.sum()
                            A["cs"][q] += (s["dealt"][k][m] - s["fwd"][k][m]).sum()
                            A["c30"][q] += s["net30"][k][m].sum()
                        A["X"].append(np.stack([c, mine, his, np.log((s["eff"][k, 0] + 25) / (s["eff"][k, 1] + 25)), s["net30"][k],
                                                e[k]], 1))
    f5 = lambda x: " ".join("{:>11.1f}".format(v) for v in x)   # noqa: E731
    for who, nm in (("pros", "the pros (the second half of the demos)"), ("bobby", "Bobby ({})".format(a.rec))):
        A = acc[who]
        print("\n{}: {} samples with the enemy near".format(nm, A["n"]))
        print("  the threat on him, damage a second | {}".format(" ".join("{:>11}".format(x) for x in ("under 2", "2 to 5", "5 to 10", "10 to 20", "over 20"))))
        print("  {:>34} | {}".format("share of his time, %", f5(100 * A["tn"] / max(A["tn"].sum(), 1))))
        print("  {:>34} | {}".format("damage taken in the next 2 s", f5(A["td"] / np.maximum(A["tn"], 1))))
        print("  {:>34} | {}".format("hit for 20 or more, %", f5(100 * A["th"] / np.maximum(A["tn"], 1))))
        print("  the edge (his on the enemy less the enemy's on him) | {}".format(" ".join("{:>11}".format(x) for x in ("under -10", "-10 to -3", "-3 to 3", "3 to 10", "over 10"))))
        print("  {:>34} | {}".format("share of his time, %", f5(100 * A["en"] / max(A["en"].sum(), 1))))
        print("  {:>34} | {}".format("standing there, % of it", f5(100 * A["es"] / np.maximum(A["en"], 1))))
        print("  {:>34} | {}".format("damage taken in the next 2 s", f5(A["ed"] / np.maximum(A["en"], 1))))
        if who == "bobby":
            print("  {:>34} | {}".format("dealt less taken, the next 2 s", f5(A["ex"] / np.maximum(A["en"], 1))))
            print("  the map: the share he covers less the share the enemy covers | {}".format(
                " ".join("{:>11}".format(x) for x in ("under -0.3", "-0.3 to -0.1", "-0.1 to 0.1", "0.1 to 0.3", "over 0.3"))))
            print("  {:>34} | {}".format("share of his time, %", f5(100 * A["cn"] / max(A["cn"].sum(), 1))))
            print("  {:>34} | {}".format("dealt less taken, the next 2 s", f5(A["cs"] / np.maximum(A["cn"], 1))))
            print("  {:>34} | {}".format("frags less deaths, the next 30 s", " ".join("{:>11.3f}".format(v) for v in A["c30"] / np.maximum(A["cn"], 1))))
            X = np.concatenate(A["X"])
            print("  the map covered: his {:.1f}%, the enemy's {:.1f}%, neither or both the rest (a margin of {} damage a second)".format(
                100 * X[:, 1].mean(), 100 * X[:, 2].mean(), CTRL))
            y = X[:, 4]
            for lab, cols in (("the stack ratio alone", [3]), ("the map's cover alone", [0]), ("both", [3, 0]), ("both and the edge", [3, 0, 5])):
                Z = np.concatenate([X[:, cols], np.ones((len(X), 1))], 1)
                r = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
                print("    frags less deaths in the next 30 s explained by {:<22} R2 {:.4f}".format(lab, 1 - r.var() / y.var()))


def state(a):
    """a picture of one state: the enemy in a zone (--zone, its middle point) with a weapon (--weapon, duel_env's number: 0 rockets,
    1 rail, 2 lightning): the threat on every place, damage a second (docs/design/space/state_<map>_z<zone>_w<weapon>.png)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import zonemap as ZM
    W = np.array(json.load(open(os.path.join(ROOT, "data", "sim_runs", "space", "weapon_threat.json")))["dmg_s"])
    names = ("rockets", "rail", "lightning", "machine gun", "shotgun", "grenades", "plasma", "hmg", "gauntlet")
    S, Z = Score(a.map), ZM.load(a.map)
    z = Z.locate(S.P)
    mem = np.nonzero(z == a.zone)[0]
    j = int(mem[np.linalg.norm((S.P[mem] - S.P[mem].mean(0)) * WZ, axis=1).argmin()])
    T = sum(W[a.weapon, q] * S.seeb[q][j] / 255.0 for q in range(3))
    fig, ax = plt.subplots(1, 2, figsize=(17, 8))
    o = np.argsort(S.P[:, 2])
    sc = ax[0].scatter(S.P[o, 0], S.P[o, 1], c=T[o], s=14, cmap="RdYlGn_r", vmin=0, vmax=max(20.0, float(T.max())))
    ax[1].scatter(S.P[:, 0], S.P[:, 2], c=T, s=8, cmap="RdYlGn_r", vmin=0, vmax=max(20.0, float(T.max())))
    ax[0].plot(S.P[j, 0], S.P[j, 1], "k*", ms=22, mec="white")
    ax[1].plot(S.P[j, 0], S.P[j, 2], "k*", ms=16, mec="white")
    for k in range(Z.k):
        if (z == k).any() and Z.names[k]:
            c = S.P[z == k].mean(0)
            ax[0].text(c[0], c[1], Z.names[k], fontsize=10, weight="bold", ha="center", va="center",
                       bbox=dict(facecolor="white", alpha=0.75, lw=0, pad=1))
    fig.colorbar(sc, ax=ax[0], shrink=0.7, label="the threat on a place, damage a second")
    ax[0].set_title("{}: the enemy (star) in zone {} {} with {}; where he can be within {} s".format(
        a.map, a.zone, Z.names[a.zone], names[a.weapon], REACH))
    ax[1].set_title("from the side (x, height)")
    for x in ax:
        x.set_aspect("equal")
    fig.tight_layout()
    f = os.path.join(ROOT, "docs", "design", "space", "state_{}_z{}_w{}.png".format(a.map, a.zone, a.weapon))
    fig.savefig(f, dpi=80)
    print("drawn " + f)


def draw(a):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import zonemap as ZM
    out = os.path.join(ROOT, "docs", "design", "space")
    os.makedirs(out, exist_ok=True)
    for mp in a.maps.split(","):
        S, Z = Score(mp), ZM.load(mp)
        z = Z.locate(S.P)
        fig, ax = plt.subplots(1, 2, figsize=(17, 8))
        o = np.argsort(S.P[:, 2])
        sc = ax[0].scatter(S.P[o, 0], S.P[o, 1], c=S.B[o], s=14, cmap="RdYlGn_r", vmin=0, vmax=float(np.quantile(S.B, 0.98)))
        ax[1].scatter(S.P[:, 0], S.P[:, 2], c=S.B, s=8, cmap="RdYlGn_r", vmin=0, vmax=float(np.quantile(S.B, 0.98)))
        for k in range(Z.k):
            if (z == k).any() and Z.names[k]:
                c = S.P[z == k].mean(0)
                ax[0].text(c[0], c[1], Z.names[k], fontsize=10, weight="bold", ha="center", va="center",
                           bbox=dict(facecolor="white", alpha=0.75, lw=0, pad=1))
                ax[1].text(c[0], c[2], Z.names[k], fontsize=8, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.6, lw=0, pad=0.5))
        fig.colorbar(sc, ax=ax[0], shrink=0.7, label="seconds in sight before cover (an enemy anywhere)")
        ax[0].set_title("{}: how bad a place is to hang out in, from above (higher points drawn last)".format(mp))
        ax[1].set_title("from the side (x, height)")
        for x in ax:
            x.set_aspect("equal")
        fig.tight_layout()
        fig.savefig(os.path.join(out, mp + ".png"), dpi=80)
        plt.close(fig)
        print("drawn " + mp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("score", "score1", "zones", "test", "edge", "state", "draw"))
    ap.add_argument("--maps", default=MAPS)
    ap.add_argument("--map", default="")
    ap.add_argument("--par", type=int, default=4)
    ap.add_argument("--rec", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "cypher", "u90"))
    ap.add_argument("--demos", type=int, default=150)
    ap.add_argument("--by-map", action="store_true")
    ap.add_argument("--zone", type=int, default=0)
    ap.add_argument("--weapon", type=int, default=2)
    a = ap.parse_args()
    dict(score=score, score1=score_map, zones=zones, test=test, edge=edge, state=state, draw=draw)[a.cmd](a)


if __name__ == "__main__":
    main()

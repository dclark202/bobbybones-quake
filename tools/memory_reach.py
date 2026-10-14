"""How far back does his memory reach, and is it healthy after ten minutes without a reset? (the owner, 2026-10-13:
"make sure his memory can and does span the entire 10 minute game")

    python tools/memory_reach.py --policy data/sim_runs/<run>/policy.pt --map bloodrun,aerowalk --games 6 --minutes 10 \
        --set AIM_LEVEL=1.5 --set LEGS=1 ... --json out.json          (Anaconda Python, the processor only)

What it does, a map at a time:
1. RECORD (one simulator process): the network plays itself, whole games, the game's spawn rules as in tools/duel_eval.py;
   nobody's memory is ever reset. --wrap S: the clock and the round's score start over every S seconds as in the checks
   (default 120; 0: never). Kept per seat and frame: the inputs he was given, his place, enemy in view, alive.
2. Open loop (no simulator; the GRU is run again over the recorded inputs, so every copy is fed exactly the same):
     carried   memory from the game's start (this is the game as it was played: checked against the live state)
     reset     memory set to zero at t0                         -> does ANY past matter, and for how long
     swap      memory at t0 taken from ANOTHER game at the same time (same map, same seat)
                                                                 -> does THIS game's past matter (not just "warmed up")
     twin      memory set to zero every --check-round seconds (what the checks do), for the state's health per minute
   t0 every --t0-every seconds; each copy runs --horizon seconds. Per delay after t0 and per output: the total variation
   between the carried network's action odds and the copy's (0: the same odds; 1: no action in common; it is the share of
   frames on which the two would act differently at best coupling), the KL divergence, how often the most likely action
   differs; the value outputs' difference in units of the value's own spread; the distance of the two states.
   The inputs are the same on both sides, so the floor is zero: two states that have forgotten their difference give the
   same odds to seven digits. "Reach" = the delay after which the curve stays under a threshold (--thresholds).
3. STATE HEALTH: per minute of the game, carried and twin: the state's size (RMS of a unit), the share of units beyond
   0.98, the mean change a frame, the policy's entropy, the value, and how far the mean state of that minute lies from the
   mean state of minutes one and two (the twin, which is reset every two minutes, is the control for what the game's
   phase does to the inputs).
4. PROBES (ridge regression, numpy; train and test split by game): can something that is NOT in his inputs at t be read
   off his state at t? His own place k seconds ago; the seconds since the enemy was last in view (his inputs keep a
   believed place for 20 s only); the unseen enemy's place now; the minute of the game (with --wrap the clock inputs
   repeat every round, so only memory can tell). The same probe from the inputs at t ("inputs") and from the encoder's
   output at t ("encoder": every memoryless feature the network itself computes) is the baseline: what the state adds
   over them is memory.

Limits to keep in mind: open loop says how long the past moves his action odds on the SAME inputs; it does not say what a
different action would have led to (closed loop the games part at once and nothing can be compared). A network's own
last choices are among its inputs (the intention, his hands), and here they are the carried network's on every copy.
"""
import argparse
import csv
import importlib
import json
import multiprocessing as mp_
import os
import sys
import tempfile
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

HEAD_NAMES = ("forward", "side", "jump", "turn", "pitch", "fire", "weapon", "walk", "zoom", "lift", "intention", "legs", "way")
GROUPS = (("keys", (0, 1, 2, 7)), ("turn/pitch", (3, 4)), ("fire", (5,)), ("weapon", (6,)), ("zoom/lift", (8, 9)),
          ("intention", (10,)), ("legs", (11,)), ("way", (12,)))
DELAYS = (0.1, 0.5, 1, 2, 5, 10, 20, 40, 80, 160, 300)
PROBE_K = (1, 2, 5, 10, 20, 40, 80)


def names(path):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(path, encoding="utf-8"))]


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


# ---------------------------------------------------------------------------------------------------------- recording
def record(job):
    """a simulator worker (no torch here): games of the network against itself, nobody's memory reset; writes .npy files"""
    (envmod, envvars, mp, games, minutes, seed, pol, idx, wrap_secs, delays, stem) = job
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    import test_suite as T_
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    n = env.n
    T_.set_delays(E, env, [(np.arange(n), delays[0], delays[1])])
    env.arena_stack = False                                   # (the rules of a check game: tools/duel_eval.py play())
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.runner_p = 0.0
    if getattr(env, "lab", None) is not None:
        env.lab_force = dict(kind=E.NORMAL, arena=3)
        env.arena_len = 1e9
    env.round_t[:] = 1e9
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    env.script[:] = 0
    pol.rng = np.random.default_rng(seed)
    h = pol.zeros(n)
    frames = int(minutes * 60 / E.DT)
    wrap = max(1, int(wrap_secs / E.DT)) if wrap_secs > 0 else 0
    om = np.lib.format.open_memmap(stem + "_obs.npy", mode="w+", dtype=np.float32, shape=(n, frames, len(idx)))
    pos = np.zeros((n, frames, 3), np.float32)
    flags = np.zeros((n, frames), np.uint8)                   # 1: the enemy in view, 2: alive, 4: his legs carry him
    kills = np.zeros(n)
    restarts = 0
    for t in range(frames):
        o = obs[:, idx]
        om[:, t] = o
        pos[:, t] = env.state[:, :3]
        alive = env.hp > 0
        flags[:, t] = ((env.visible & alive).astype(np.uint8) + 2 * alive.astype(np.uint8)
                       + 4 * getattr(env, "legs_on", np.zeros(n, bool)).astype(np.uint8))
        al, h = pol.act(o, h)
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a[:, :al.shape[1]] = al
        obs, _, done, info = env.step(a)
        restarts += int(done.any())
        for e in info["events"]:
            v, k = int(e["victim"]), int(e["killer"])
            if k >= 0 and k != v:
                kills[k] += 1
        if wrap and (t + 1) % wrap == 0:                        # the clock and the round's score start over; the memory does not
            env.round_t[:] = 0.0
            env.frags_r[:] = 0
    om.flush()
    del om
    np.save(stem + "_pos.npy", pos)
    np.save(stem + "_flags.npy", flags)
    np.save(stem + "_hend.npy", h)
    json.dump(dict(dt=float(E.DT), n=int(n), frames=frames, kills=kills.tolist(), restarts=restarts, dims=[int(x) for x in E.ACTION_DIMS],
                   wrap=wrap_secs, map=mp), open(stem + "_meta.json", "w"))
    return stem


# ------------------------------------------------------------------------------------------------- the network, open
class Net:
    """the checks' numpy network (sim/test_suite.py Policy) taken apart: encoder, one GRU step, the outputs' logits, the values"""

    def __init__(self, path):
        import torch
        import test_suite as T
        self.pol = p = T.Policy(path, seed=1)
        ck = torch.load(path, weights_only=False, map_location="cpu")
        sd = {k: v.cpu().numpy() for k, v in ck["model"].items()}
        vw, vb = [sd["v.weight"]], [sd["v.bias"]]
        self.vnames = ["value"]
        if "v2.weight" in sd:
            vw.append(sd["v2.weight"])
            vb.append(sd["v2.bias"])
            self.vnames += ["long value a", "long value b"]
        self.wv, self.bv = np.concatenate(vw, 0).astype(np.float32), np.concatenate(vb, 0).astype(np.float32)
        self.H, self.dims = p.H, p.dims
        self.wihT, self.whhT, self.wpT = (np.ascontiguousarray(x.T) for x in (p.wih, p.whh, p.wp))
        self.minutes = p.minutes
        self.door = p.attP is not None

    def encode(self, obs, chunk=1024):
        """raw inputs [N, D] -> what the GRU is given [N, 256], and the normalised inputs [N, D]"""
        p = self.pol
        out, xs = [], []
        for i in range(0, len(obs), chunk):
            o = np.asarray(obs[i:i + chunk])
            x = np.clip((o - p.mean) / np.sqrt(p.var + 1e-8), -10, 10).astype(np.float32)
            xa = x
            if p.cell is not None:
                ids = np.clip(o[:, -2:].astype(np.int64), 0, len(p.cell) - 1)
                x = np.concatenate([x[:, :-2], p.cell[ids[:, 0]], p.cell[ids[:, 1]]], 1)
            e = np.tanh(x @ p.w0.T + p.b0)
            e = np.tanh(e @ p.w1.T + p.b1)
            if p.attP is not None:
                e = e + p.attn_fwd(p.attn, p.attP, xa)
            out.append(e.astype(np.float32))
            xs.append(xa)
        return np.concatenate(out), np.concatenate(xs)

    def gru(self, gi, h):
        p, H = self.pol, self.H
        gh = h @ self.whhT + p.bhh
        r = sig(gi[:, :H] + gh[:, :H])
        z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
        nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
        return ((1 - z) * nn_ + z * h).astype(np.float32)


def new_acc(K, nh, nv, minutes, H):
    return dict(div=np.zeros((4 * K, nh, 3)), val=np.zeros((4 * K, nv)), hd=np.zeros(4 * K), cnt=np.zeros(4 * K),
                vsum=np.zeros(nv), vsq=np.zeros(nv), vn=0.0,
                health=np.zeros((2, minutes, 5)), hmean=np.zeros((2, minutes, H)), hcnt=np.zeros((2, minutes)),
                twin=np.zeros((minutes, nh, 3)), twin_n=np.zeros(minutes), branches=np.zeros(4))


def analyse(net, stem, a, acc):
    """the open-loop passes over one map's recording, summed into acc; -> (the states kept for the probes, a few facts)"""
    meta = json.load(open(stem + "_meta.json"))
    DT, S, T = meta["dt"], meta["n"], meta["frames"]
    obs = np.load(stem + "_obs.npy", mmap_mode="r")
    H, dims = net.H, net.dims
    nh = len(dims)
    off = np.concatenate([[0], np.cumsum(dims)])
    t_ = time.time()
    E = np.zeros((S, T, net.wihT.shape[0]), np.float32)
    for s in range(S):
        E[s], _ = net.encode(obs[s])
    print("    {}: encoded {} seats x {} frames in {:.0f} s".format(meta["map"], S, T, time.time() - t_), flush=True)
    K = int(round(a.horizon / DT))
    every = int(round(a.t0_every / DT))
    starts = set(range(int(round(a.t0_first / DT)), T - int(10 / DT), every))
    half_at = int(round(a.early / DT))
    twin_every = int(round(a.check_round / DT))
    can_swap = S >= 4
    sub = int(round(a.probe_every / DT))
    hs = np.zeros((S, (T + sub - 1) // sub, H), np.float32)
    seat = np.concatenate([np.arange(S), np.arange(S)])       # rows: carried [0:S], twin [S:2S], then the copies
    kind = np.full(2 * S, -1)
    t0s = np.zeros(2 * S, np.int64)
    h = np.zeros((2 * S, H), np.float32)
    bih, bp = net.pol.bih, net.pol.bp
    t_ = time.time()
    for t in range(T):
        if t and t % twin_every == 0:
            h[S:2 * S] = 0.0
        if t in starts:
            add_h = [np.zeros((S, H), np.float32)]
            add_k = [np.zeros(S, np.int64)]
            if can_swap:
                add_h.append(h[(np.arange(S) + 2) % S].copy())   # the next game's memory, the same seat of it
                add_k.append(np.ones(S, np.int64))
            for hh, kk in zip(add_h, add_k):
                h = np.concatenate([h, hh])
                seat = np.concatenate([seat, np.arange(S)])
                kind = np.concatenate([kind, kk])
                t0s = np.concatenate([t0s, np.full(S, t)])
                acc["branches"][2 * kk[0] + int(t >= half_at)] += S
        gi = (E[:, t] @ net.wihT + bih)[seat]
        hn = net.gru(gi, h)
        m = min(int(t * DT / 60.0), acc["health"].shape[1] - 1)
        step = np.abs(hn[:2 * S] - h[:2 * S]).mean(1)
        h = hn
        logits = h @ net.wpT + bp
        v = h @ net.wv.T + net.bv
        LP = np.empty_like(logits)
        for j in range(nh):
            l = logits[:, off[j]:off[j + 1]]
            l = l - l.max(1, keepdims=True)
            LP[:, off[j]:off[j + 1]] = l - np.log(np.exp(l).sum(1, keepdims=True))
        P = np.exp(LP)
        ent = -(P[:2 * S] * LP[:2 * S]).sum(1)
        for w in (0, 1):
            r_ = slice(w * S, (w + 1) * S)
            hw = h[r_]
            acc["health"][w, m] += [np.sqrt((hw ** 2).mean(1)).sum(), (np.abs(hw) > 0.98).mean(1).sum(), step[r_].sum(), ent[r_].sum(), v[r_, 0].sum()]
            acc["hmean"][w, m] += hw.sum(0)
            acc["hcnt"][w, m] += S
        acc["vsum"] += v[:S].sum(0)
        acc["vsq"] += (v[:S] ** 2).sum(0)
        acc["vn"] += S
        if t % sub == 0:
            hs[:, t // sub] = h[:S]
        # every other row against the carried row of its seat
        rows = np.arange(S, len(h))
        sr = seat[rows]
        d = np.zeros((len(rows), nh, 3))
        for j in range(nh):
            sl = slice(off[j], off[j + 1])
            pa, pb, la, lb = P[sr, sl], P[rows, sl], LP[sr, sl], LP[rows, sl]
            d[:, j, 0] = 0.5 * np.abs(pa - pb).sum(1)
            d[:, j, 1] = (pa * (la - lb)).sum(1)
            d[:, j, 2] = pa.argmax(1) != pb.argmax(1)
        acc["twin"][m] += d[:S].sum(0)
        acc["twin_n"][m] += S
        if len(rows) > S:
            br = rows[S:]
            k = t - t0s[br]
            ix = (2 * kind[br] + (t0s[br] >= half_at)) * K + k
            np.add.at(acc["div"], ix, d[S:])
            np.add.at(acc["val"], ix, np.abs(v[br] - v[seat[br]]))
            np.add.at(acc["hd"], ix, np.linalg.norm(h[br] - h[seat[br]], axis=1) / (np.linalg.norm(h[seat[br]], axis=1) + 1e-9))
            np.add.at(acc["cnt"], ix, 1.0)
            keep = np.ones(len(h), bool)
            keep[br] = k + 1 < K
            if not keep.all():
                h, seat, kind, t0s = h[keep], seat[keep], kind[keep], t0s[keep]
        if t and t % int(60 / DT) == 0:
            print("      minute {} of {:g} ({} rows, {:.0f} s)".format(t * DT / 60, T * DT / 60, len(h), time.time() - t_), flush=True)
    live = np.load(stem + "_hend.npy")
    facts = dict(map=meta["map"], seats=S, frames=T, dt=DT, wrap=meta["wrap"], frags_a_game=float(np.sum(meta["kills"]) / (S / 2)),
                 restarts=meta["restarts"], replay_error=float(np.abs(live - h[:S]).max()), swap=bool(can_swap))
    return dict(hs=hs, E=E, sub=sub, meta=meta), facts


# ------------------------------------------------------------------------------------------------------------- probes
def ridge(Xa, Ya, Xv, Yv, Xt, Yt):
    """standardised ridge, the weight chosen on the validation games -> R2 on the test games (all targets together)"""
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-6
    Xa, Xv, Xt = ((x - mu) / sd for x in (Xa, Xv, Xt))
    ym = Ya.mean(0)
    A = (Xa.T @ Xa).astype(np.float64)
    B = (Xa.T @ (Ya - ym)).astype(np.float64)
    best = None
    for lam in (1e-3, 1e-2, 1e-1, 1.0):
        W = np.linalg.solve(A + lam * len(Xa) * np.eye(A.shape[0]), B)
        ev = float(((Xv @ W + ym - Yv) ** 2).sum())
        if best is None or ev < best[0]:
            best = (ev, W)
    W = best[1]
    sse = float(((Xt @ W + ym - Yt) ** 2).sum())
    sst = float(((Yt - Yt.mean(0)) ** 2).sum())
    return 1.0 - sse / max(sst, 1e-12)


def probes(net, stem, kept, a):
    meta, sub, hs, E = kept["meta"], kept["sub"], kept["hs"], kept["E"]
    DT, S, T = meta["dt"], meta["n"], meta["frames"]
    G = S // 2
    if G < 3:
        return None
    obs = np.load(stem + "_obs.npy", mmap_mode="r")
    pos = np.load(stem + "_pos.npy") / 1000.0
    vis = (np.load(stem + "_flags.npy") & 1) > 0
    ts = np.arange(0, T, sub)
    p = net.pol
    X = np.stack([np.clip((np.asarray(obs[s][ts]) - p.mean) / np.sqrt(p.var + 1e-8), -10, 10).astype(np.float32) for s in range(S)])
    Ee = E[:, ts]
    since = np.zeros((S, T), np.float32)                      # seconds since the enemy was last in his view (from the game's start)
    c = np.zeros(S)
    for t in range(T):
        c = np.where(vis[:, t], 0.0, c + DT)
        since[:, t] = c
    game = np.arange(S) // 2
    n_te = max(1, G // 4)
    te, va = game >= G - n_te, game == G - n_te - 1
    tr = ~te & ~va
    feats = {"inputs": X, "encoder": Ee, "state": hs}
    out = {}

    def fit(name, Y, mask):
        """Y [S, n, k], mask [S, n]"""
        r = {}
        for fn, F in feats.items():
            sel = lambda g: (F[g][mask[g]], Y[g][mask[g]])
            (xa, ya), (xv, yv), (xt, yt) = sel(tr), sel(va), sel(te)
            if min(len(xa), len(xv), len(xt)) < 200:
                return
            r[fn] = round(ridge(xa, ya, xv, yv, xt, yt), 3)
        r["n_test"] = int(mask[te].sum())
        out[name] = r

    all_ = np.ones((S, len(ts)), bool)
    for k in PROBE_K:
        kf = int(round(k / DT))
        Y = pos[:, np.maximum(ts - kf, 0)]
        fit("his own place {} s ago".format(k), Y, all_ & (ts >= kf)[None, :])
    sn = since[:, ts]
    fit("seconds since the enemy was in view (log)", np.log1p(np.minimum(sn, 120.0))[:, :, None], all_)
    fit("... on frames unseen for over 20 s", np.log1p(np.minimum(sn, 120.0))[:, :, None], sn > 20.0)
    en = pos[np.arange(S) ^ 1][:, ts]
    fit("the enemy's place now, unseen for over 3 s", en, sn > 3.0)
    fit("the enemy's place now, unseen for over 20 s", en, sn > 20.0)
    fit("the minute of the game", np.broadcast_to((ts * DT / 60.0)[None, :, None], (S, len(ts), 1)), all_)
    return out


# ------------------------------------------------------------------------------------------------------------ tables
def summarise(net, acc, DT, a):
    K = acc["div"].shape[0] // 4
    nh = len(net.dims)
    groups = [(g, [j for j in hs_ if j < nh]) for g, hs_ in GROUPS]
    groups = [(g, js) for g, js in groups if js]
    vstd = np.sqrt(np.maximum(acc["vsq"] / max(acc["vn"], 1) - (acc["vsum"] / max(acc["vn"], 1)) ** 2, 1e-12))
    edges = [0, 1]                                            # (index k of a copy = (k + 1) frames after t0)
    while edges[-1] < K:
        edges.append(max(edges[-1] + 1, int(round(edges[-1] * 1.2))))
    edges[-1] = K
    res = {}
    for ki, kname in ((0, "reset"), (1, "swap")):
        for part, halves in (("all", (0, 1)), ("early t0", (0,)), ("late t0", (1,))):
            div = sum(acc["div"][(2 * ki + h_) * K:(2 * ki + h_ + 1) * K] for h_ in halves)
            val = sum(acc["val"][(2 * ki + h_) * K:(2 * ki + h_ + 1) * K] for h_ in halves)
            hd = sum(acc["hd"][(2 * ki + h_) * K:(2 * ki + h_ + 1) * K] for h_ in halves)
            cnt = sum(acc["cnt"][(2 * ki + h_) * K:(2 * ki + h_ + 1) * K] for h_ in halves)
            if cnt.sum() == 0:
                continue

            def win(lo, hi):
                n_ = cnt[lo:hi].sum()
                if n_ == 0:
                    return None
                d = div[lo:hi].sum(0) / n_
                return dict(n=int(n_), tv={HEAD_NAMES[j] if j < len(HEAD_NAMES) else "head{}".format(j): float(d[j, 0]) for j in range(nh)},
                            kl={HEAD_NAMES[j] if j < len(HEAD_NAMES) else "head{}".format(j): float(d[j, 1]) for j in range(nh)},
                            flip={HEAD_NAMES[j] if j < len(HEAD_NAMES) else "head{}".format(j): float(d[j, 2]) for j in range(nh)},
                            group_tv={g: float(d[js, 0].mean()) for g, js in groups}, group_kl={g: float(d[js, 1].mean()) for g, js in groups},
                            group_flip={g: float(d[js, 2].mean()) for g, js in groups},
                            value={nm: float(val[lo:hi, i].sum() / n_ / vstd[i]) for i, nm in enumerate(net.vnames)},
                            state=float(hd[lo:hi].sum() / n_))

            table = {}
            for dl in DELAYS:
                f = dl / DT
                lo, hi = max(0, int(np.floor(f / 1.1)) - 1), min(K, max(int(np.ceil(f * 1.1)), int(np.floor(f / 1.1))))
                if lo < K and hi > lo:
                    w = win(lo, hi)
                    if w:
                        table["{:g}".format(dl)] = w
            curve = [dict(to_s=edges[i + 1] * DT, **w) for i in range(len(edges) - 1) for w in [win(edges[i], edges[i + 1])] if w]
            reach = {}
            for thr in a.thresholds:
                rr = {}
                series = {g: [c["group_tv"][g] for c in curve] for g, _ in groups}
                series.update({nm: [c["value"][nm] for c in curve] for nm in net.vnames})
                series["state"] = [c["state"] for c in curve]
                for nm, ys in series.items():
                    over = [i for i, y in enumerate(ys) if y >= thr]
                    rr[nm] = 0.0 if not over else (None if over[-1] == len(curve) - 1 else curve[over[-1]]["to_s"])   # None: not within the horizon
                reach["{:g}".format(thr)] = rr
            res["{} / {}".format(kname, part)] = dict(table=table, reach=reach, curve=[dict(to_s=c["to_s"], n=c["n"], group_tv=c["group_tv"], value=c["value"],
                                                                                           state=c["state"]) for c in curve])
    M = acc["health"].shape[1]
    health = {}
    for w, who in ((0, "carried"), (1, "twin")):
        n_ = np.maximum(acc["hcnt"][w], 1)
        hm = acc["hmean"][w] / n_[:, None]
        ref = hm[:min(2, M)].mean(0)
        health[who] = [dict(minute=m + 1, rms=float(acc["health"][w, m, 0] / n_[m]), saturated=float(acc["health"][w, m, 1] / n_[m]),
                            change=float(acc["health"][w, m, 2] / n_[m]), entropy=float(acc["health"][w, m, 3] / n_[m]),
                            value=float(acc["health"][w, m, 4] / n_[m]), drift=float(np.sqrt(((hm[m] - ref) ** 2).mean())))
                       for m in range(M) if acc["hcnt"][w, m] > 0]
    twin = [dict(minute=m + 1, **{g: float(acc["twin"][m][js, 0].mean() / acc["twin_n"][m]) for g, js in groups})
            for m in range(M) if acc["twin_n"][m] > 0]
    return dict(open_loop=res, health=health, twin_tv=twin, value_std={nm: float(vstd[i]) for i, nm in enumerate(net.vnames)},
                branches=dict(reset_early=int(acc["branches"][0]), reset_late=int(acc["branches"][1]), swap_early=int(acc["branches"][2]),
                              swap_late=int(acc["branches"][3])))


def show(out, net, a):
    fm = lambda x: "  -   " if x is None else ("{:6.4f}".format(x) if x < 9.9995 else "{:6.2f}".format(x))
    for key in ("reset / all", "swap / all", "swap / early t0", "swap / late t0"):
        r = out["open_loop"].get(key)
        if not r:
            continue
        cols = [d for d in ("{:g}".format(x) for x in DELAYS) if d in r["table"]]
        if not cols:
            continue
        print("\n{}: total variation of his action odds against the carried memory, by seconds after t0 (value, state: see the head of the file)".format(key))
        print("  {:14s}".format("after (s)") + "".join("{:>8s}".format(c) for c in cols))
        for g in list(r["table"][cols[0]]["group_tv"]):
            print("  {:14s}".format(g) + "".join("  " + fm(r["table"][c]["group_tv"][g]) for c in cols))
        for nm in net.vnames:
            print("  {:14s}".format(nm) + "".join("  " + fm(r["table"][c]["value"][nm]) for c in cols))
        print("  {:14s}".format("state distance") + "".join("  " + fm(r["table"][c]["state"]) for c in cols))
        print("  {:14s}".format("copies") + "".join("{:>8d}".format(r["table"][c]["n"]) for c in cols))
        for thr, rr in r["reach"].items():
            print("  stays under {} after: ".format(thr) + ", ".join("{} {}".format(k_, "never (within {:g} s)".format(a.horizon) if v_ is None else "{:.3g} s".format(v_))
                                                                    for k_, v_ in rr.items()))
    print("\nthe state per minute of the game (carried: never reset; twin: the same inputs, memory reset every {:g} s)".format(a.check_round))
    print("  minute | carried: rms  beyond 0.98  change/frame  entropy   value  drift | twin: rms  beyond 0.98  change/frame  entropy   value  drift")
    tw = {h_["minute"]: h_ for h_ in out["health"]["twin"]}
    for h_ in out["health"]["carried"]:
        w = tw[h_["minute"]]
        print("  {:6d} | {:12.3f} {:11.4f} {:13.4f} {:8.3f} {:7.3f} {:6.3f} | {:9.3f} {:11.4f} {:13.4f} {:8.3f} {:7.3f} {:6.3f}".format(
            h_["minute"], h_["rms"], h_["saturated"], h_["change"], h_["entropy"], h_["value"], h_["drift"],
            w["rms"], w["saturated"], w["change"], w["entropy"], w["value"], w["drift"]))
    print("\ncarried against twin, total variation by minute (what a reset every {:g} s changes in his action odds)".format(a.check_round))
    for r in out["twin_tv"]:
        print("  minute {:2d}: ".format(r["minute"]) + "  ".join("{} {:.4f}".format(k_, v_) for k_, v_ in r.items() if k_ != "minute"))
    if out.get("probes"):
        print("\nprobes: R2 on games held out (mean over maps), read from his inputs at t, the encoder's output at t, his state at t")
        for nm, r in out["probes"].items():
            print("  {:46s} inputs {:6.3f}   encoder {:6.3f}   state {:6.3f}   ({} frames)".format(nm, r["inputs"], r["encoder"], r["state"], r["n_test"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"), help="the list of input names the network was trained with")
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--games", type=int, default=6, help="games a map (two seats a game are recorded; the swap needs 2, the probes 3)")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator setting for the recorded games")
    ap.add_argument("--wrap", type=float, default=120.0, help="the clock and the round's score start over every this many seconds in the "
                    "recorded games, as in the checks (0: never). The memory is never reset")
    ap.add_argument("--check-round", type=float, default=120.0, help="the twin's memory is reset every this many seconds")
    ap.add_argument("--t0-first", type=float, default=37.0)
    ap.add_argument("--t0-every", type=float, default=30.0)
    ap.add_argument("--early", type=float, default=150.0, help="t0 before this many seconds: an early copy")
    ap.add_argument("--horizon", type=float, default=300.0)
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.05, 0.01, 0.001])
    ap.add_argument("--probe-every", type=float, default=0.5)
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--react-ms", type=float, default=None)
    ap.add_argument("--acquire-ms", type=float, default=None)
    ap.add_argument("--out", default="", help="a folder for the recordings (default: a temporary one). With --reuse a recording found there is not played again")
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    net = Net(a.policy)
    now, old = names(os.path.join(ROOT, "docs", "INPUTS.csv")), names(a.inputs)
    assert len(old) == len(net.pol.mean), "the network has {} inputs, {} lists {}".format(len(net.pol.mean), a.inputs, len(old))
    idx = np.array([now.index(x) for x in old])
    envvars = dict(x.split("=", 1) for x in a.set)
    delays = (net.pol.react_ms if a.react_ms is None else a.react_ms, net.pol.acquire_ms if a.acquire_ms is None else a.acquire_ms)
    folder = a.out or tempfile.mkdtemp(prefix="memreach_")
    os.makedirs(folder, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.policy))[0]
    print("{} ({:.0f} minutes trained; {} inputs, {} outputs, attention {}), wrap {:g} s, recordings in {}".format(
        a.policy, net.minutes, len(old), len(net.dims), "on" if net.door else "off or none", a.wrap, folder), flush=True)
    acc, facts, pr, DT = None, [], [], 0.025
    for mp in a.map.split(","):
        stem = os.path.join(folder, "{}_{}_g{}_m{:g}_w{:g}_s{}".format(tag, mp, a.games, a.minutes, a.wrap, a.seed))
        if not (a.reuse and os.path.exists(stem + "_meta.json")):
            t_ = time.time()
            with mp_.Pool(1) as pool:                         # one simulator a process: a new process a map
                pool.map(record, [(a.env, envvars, mp, a.games, a.minutes, a.seed, net.pol, idx, a.wrap, delays, stem)])
            print("  {}: {} games of {:g} minutes recorded in {:.0f} s".format(mp, a.games, a.minutes, time.time() - t_), flush=True)
        meta = json.load(open(stem + "_meta.json"))
        DT = meta["dt"]
        if acc is None:
            acc = new_acc(int(round(a.horizon / DT)), len(net.dims), len(net.vnames), int(np.ceil(a.minutes)), net.H)
        kept, f = analyse(net, stem, a, acc)
        facts.append(f)
        print("  {}: {:.1f} frags a game; the replay's state against the live one at the end: {:.2g} (largest difference of a unit)".format(
            mp, f["frags_a_game"], f["replay_error"]), flush=True)
        if not a.no_probe:
            p_ = probes(net, stem, kept, a)
            if p_:
                pr.append(p_)
        del kept
    out = summarise(net, acc, DT, a)
    out.update(policy=a.policy, env=a.env, set=envvars, wrap=a.wrap, games=a.games, minutes=a.minutes, maps=facts, horizon=a.horizon)
    if pr:
        keys = [k for k in pr[0] if all(k in p_ for p_ in pr)]
        out["probes"] = {k: {f: (int(sum(p_[k][f] for p_ in pr)) if f == "n_test" else round(float(np.mean([p_[k][f] for p_ in pr])), 3)) for f in pr[0][k]}
                         for k in keys}
        out["probes_by_map"] = {f["map"]: p_ for f, p_ in zip(facts, pr)} if len(pr) == len(facts) else None
    show(out, net, a)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()

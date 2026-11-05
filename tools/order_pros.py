"""1.7, the combat order's start fitted to the pros (docs/runs/1.7/BUILD.md part 9; README S4): the pros' duels labelled in
hindsight with the order's kinds and candidates, the candidates and their numbers made by the simulator's own order_feat() on the
demo's state, and the kind's context layer and the pointer's numbers part fitted to them by maximum likelihood with a small L2.

  python tools/order_pros.py label --map bloodrun [--demos 40] [--every 0.5] [--cap 12000] [--cmd <train.cmd> --run-dir <run>]
      -> data/order_pros/<map>.npz (+ .json: what was read, why moments were left out, the labels' counts)
  python tools/order_pros.py fit [--maps all] [--l2 0.001,0.01,0.1] [--out docs/runs/1.7/1.7a/order_fit.json]
      -> the fit (tools/order_init.py add --fit reads it): ok_c (the kind on the situation's numbers), op_x and op_v (the pointer
         on a candidate's numbers); the weights on the head's state (ok_s, op_s) stay zero

The demos (data/demo_root.txt: demos/<map>/*.dm_91, .dm_90, then .dm_73) are read by tools/pro_moments.py (tools/demodump): the
followed player exact, the enemy's place, view and weapon from his entity, his stack worked out, the items' states. A moment every
--every seconds of the live game where pro_moments.py takes one (both in play, no respawn, teleporter step or cut near, the big items'
states known), and the demo follows the same player alive for WIN seconds after it (the labels look that far ahead).

The simulator (one DuelEnv with the run's settings, 1.6a's by default, and COMBAT=1) is put at each moment as its pro starts are
(DuelEnv._pro_start: places, speeds, views, stacks, weapons, the clock, the items), and the followed player's belief of the enemy as
the simulator's rule makes it from his senses: where he last saw him in this stretch of the demo (his sight cone, a clear line:
tools/pro_yardsticks.py see()) or heard him (his shots, pain sounds and pickups within the simulator's EAR_RANGE), known for the
simulator's own V02_KNOWN seconds (as its belief is: sight and sound); the enemy's stack as pro_moments.py works it out. The brain is not run on
demos: its places ahead are stood in for by the believed place moved on by the enemy's last seen speed for (seconds since + horizon),
stopped at the first wall (the player's box). The brain's pass odds are its start's (0.1 everywhere, as the readout starts).

The labels (detail, decided from the README's labels; the first that holds):
  spam        a blind shot of his (rockets, grenades, plasma; the enemy out of view BLIND_S or more) in the SPAM_WIN after the moment,
              landing FEET_R or more from him (tools/pro_yardsticks.py landings()): the spam candidate nearest its landing within
              SPAM_MATCH (else the kind alone)
  (break off, cut off and chase read where the enemy is later: none of them where the enemy dies or a teleporter carries either
  within the window: a won fight's respawn far away is no break off)
  break off   the enemy in view within CONTACT_IN before the moment; OUT_S later no clear line between them, OUT_GROW units further
              apart, no item taken: the way out nearest where he is then within OUT_MATCH (else the kind alone)
  item        an item of the targets (MH, RA, YA, RL, RG, LG) taken by him within WIN: the target as chosen, that item
  hold        the enemy out of view; within HOLD_R of a holding place for HOLD_S: the target as chosen, that place
  cut off     the enemy out of view, his belief known, MOVE_MIN units moved in MOVE_S: where he is then within CUT_R of where the enemy
              is 1, 2 or 4 s after the moment, and CUT_EDGE nearer to that than to the believed place: cut off at that horizon
  chase       as cut off's first part, CHASE_GAIN nearer the believed place than at the moment: the target as chosen, the enemy
  otherwise   the target as chosen, its target not named (the kind alone)

The fit: the kind's logits ok_c(ctx) (ok_s on the state zero), a kind with no valid candidate shut, as sim/head2.py order_scores();
the pointer g(x) = op_v(tanh(op_x(x))) (op_s zero), a softmax over the kind's valid candidates (the targets': over the valid targets).
The negative log-likelihood of the labels plus l2 (|ok_c.weight|^2 + |op_x.weight|^2 + |op_v.weight|^2); the l2 chosen by the held
out tenth of the demos; the fit on the rest. One process a map for `label` (one simulator World a process); CPU.
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")
OUT = os.path.join(ROOT, "data", "order_pros")
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")
WIN = 4.0                       # the labels' window ahead (s)
SPAM_WIN, SPAM_MATCH = 0.5, 300.0
CONTACT_IN, OUT_S, OUT_GROW, OUT_MATCH = 1.0, 3.0, 300.0, 400.0
HOLD_R, HOLD_S = 150.0, 2.0
MOVE_S, MOVE_MIN, CUT_R, CUT_EDGE, CHASE_GAIN = 2.0, 250.0, 400.0, 200.0, 200.0
HORIZ = (1.0, 2.0, 4.0)
PASS_START = 0.1                # (sim/passodds.py PRIOR: the readout's answer at the start, every candidate)
TARGET_ITEMS = ("MH", "RA", "RL", "RG", "LG", "YA", "YA2")
KINDS = ("target", "cut", "spam", "out")


def _setup(cmd, run_dir):
    """the run's simulator settings in the environment, COMBAT on, before the simulator is imported"""
    sys.path.insert(0, SIM)
    sys.path.insert(0, HERE)
    import winpay_games as WG
    envv, _ = WG.run_env(cmd, run_dir)
    os.environ.update(envv)
    os.environ.update(COMBAT="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")


def _map_info(PM, E, env, bsp):
    """pro_moments.MapInfo on this simulator (its walking map is the order tables')"""
    import pvs
    MI = object.__new__(PM.MapInfo)
    MI.E, MI.env, MI.w = E, env, env.w
    MI.V = pvs.Vis(bsp)
    ents = [e for e in MI.w.entities if e.get("classname") in E.ITEM_DEFS and "origin" in e]
    MI.cls = [e["classname"] for e in ents]
    MI.pos = env.item_pos.copy()
    MI.idef = env.item_def
    MI.nI = len(MI.cls)
    MI.lab = [d[4] for d in MI.idef]
    MI.resp = np.array([float(d[2]) for d in MI.idef], np.float32)
    MI.icl = MI.V.box_clusters(MI.pos, mins=np.array([-15, -15, -15], np.float32), maxs=np.array([15, 15, 15], np.float32))
    return MI


def _moments_npz(rows, MI, path):
    """pro_moments.py's file for these moments (DuelEnv._moments_load reads it)"""
    M = len(rows)

    def st(k, dt=np.float32):
        return np.array([[r[k][0], r[k][1]] for r in rows], dt)
    np.savez(path, version=np.int32(1), clock=np.array([r["clock"] for r in rows], np.float32), score=st("score", np.int16),
             pos=np.array([np.stack(r["pos"]) for r in rows], np.float32).reshape(M, 2, 3),
             vel=np.array([np.stack(r["vel"]) for r in rows], np.float32).reshape(M, 2, 3),
             yaw=st("yaw"), pitch=(((st("pitch") + 180.0) % 360.0) - 180.0).astype(np.float32), hp=st("hp"), armor=st("armor"),
             has=np.array([np.stack(r["has"]) for r in rows], bool).reshape(M, 2, 9),
             ammo=np.array([np.stack(r["ammo"]) for r in rows], np.int16).reshape(M, 2, 9),
             weapon=st("weapon", np.int8), life=st("life"), est=np.tile(np.array([0, 1], np.int8), (M, 1)),
             item_left=np.array([r["left"] for r in rows], np.float16).reshape(M, MI.nI),
             item_who=np.array([r["who"] for r in rows], np.int8).reshape(M, MI.nI),
             item_unsure=np.array([r["uns"] for r in rows], bool).reshape(M, MI.nI),
             item_pos=MI.pos.astype(np.float32), item_cls=np.array(MI.cls))


def _last_seen(inview, first):
    """per frame: the last frame of this stretch with the enemy in view (-1: none yet)"""
    N = len(inview)
    ar = np.arange(N)
    ls = np.maximum.accumulate(np.where(inview, ar, -1))
    st0 = np.maximum.accumulate(np.where(first, ar, 0))
    return np.where(ls >= st0, ls, -1)


def label(a):
    _setup(a.cmd, a.run_dir)
    import duel_env as E
    import pro_moments as PM
    import pro_yardsticks as PY
    PM.low_priority()
    mapn = a.map
    bsp = os.path.join(ROOT, "data", "maps", mapn + ".bsp")
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapn))
    env = E.DuelEnv(bsp, n_matches=1, seed=7, loadout="all", nav=nav)
    assert env.om is not None, "no order tables for {} (tools/order_maps.py)".format(mapn)
    assert env.n == 2
    env.observe()
    env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    MI = _map_info(PM, E, env, bsp)
    n = env.n
    CT, C0, SL = E.CMB_T, E.CMB_C0, E.CMB_SLOTS
    FV = E.CMB_FEAT.index("valid")
    rng = np.random.default_rng(a.seed)
    dd = os.path.join(PM.demo_root(), "demos", mapn)
    new = sorted(glob.glob(os.path.join(dd, "*.dm_91"))) + sorted(glob.glob(os.path.join(dd, "*.dm_90")))
    old = sorted(glob.glob(os.path.join(dd, "*.dm_73")))
    pick = list(rng.permutation(new))[:a.demos]
    if len(pick) < a.demos:
        pick += list(rng.permutation(old))[:a.demos - len(pick)]
    counts = Counter()
    tmp = tempfile.mkdtemp(prefix="op_")
    Xs, Cs, KD, CD, DH, WHY = [], [], [], [], [], []
    t0 = time.time()
    for nd, demo in enumerate(pick):
        tr = {}
        try:
            ms = PM.one_demo(MI, demo, tmp, a.every, 2.0, rng, counts, tracks=tr)
        except Exception as e:                               # noqa: BLE001 (a broken demo must not stop the map)
            counts["error"] += 1
            print("error", nd, repr(e)[:160], flush=True)
            continue
        counts["demos"] += 1
        if not ms:
            continue
        h_ = hashlib.sha1(os.path.basename(demo).encode("utf-8", "replace")).hexdigest()[:10]
        rec, en, T, cn, seg = tr["rec"], tr["en"], tr["T"], tr["cn"], tr["seg"]
        PY.see(rec, env.w)
        N = len(T)
        inview, los, first, alive = rec["inview"], rec["los"], rec["first"], np.asarray(rec["alive"], bool)
        ls = _last_seen(inview, first)
        since_all = np.where(ls >= 0, T - T[np.maximum(ls, 0)], np.inf)     # (out of view this long: a shot is blind from BLIND_S)
        hp_ = np.zeros(N, bool)                              # (his ears, as the simulator's: the enemy's shots, pain sounds and pickups
        for f_ in list(tr["shots"].keys()) + list(tr["pain"].keys()):    # within EAR_RANGE; his belief from sight and sound)
            hp_[int(f_)] = True
        for j_, tk_ in tr["takes"].items():
            for t_, who in tk_:
                f_ = min(N - 1, int(np.searchsorted(T, t_)))
                if who == tr["other"][f_]:
                    hp_[f_] = True
        epf_ = np.isfinite(en["pos"]).all(1)
        dist_ = np.where(epf_, np.linalg.norm(np.nan_to_num(en["pos"]) - rec["pos"], axis=1), np.inf)
        heard_ = hp_ & epf_ & (dist_ <= E.EAR_RANGE)
        counts["frames he heard the enemy"] += int(heard_.sum())
        lk = _last_seen(inview | heard_, first)
        since_k = np.where(lk >= 0, T - T[np.maximum(lk, 0)], np.inf)
        epos, evel = en["pos"], en["vel"]
        mine = []                                            # his own takes: (time, simulator item)
        for j_, tk_ in tr["takes"].items():
            for t_, who in tk_:
                f_ = min(N - 1, int(np.searchsorted(T, t_)))
                if who == cn[f_]:
                    mine.append((float(t_), int(j_)))
        mine.sort()
        shots = rec["shots"] if rec.get("shots") is not None and len(rec["shots"]) else np.zeros((0, 3), np.int64)
        pfile = os.path.join(tmp, "m.npz")
        _moments_npz(ms, MI, pfile)
        env.pro_mo = env._moments_load(pfile, "order pros")
        if env.pro_mo is None:
            counts["items not matched"] += 1
            continue
        for k, m in enumerate(ms):
            f = int(m["f"])
            t = float(T[f])
            f4 = int(np.searchsorted(T, t + WIN))
            if f4 >= N or seg[f4] != seg[f] or (cn[f:f4 + 1] != cn[f]).any() or not alive[f:f4 + 1].all():
                counts["not followed alive for the window"] += 1
                continue
            fl = int(lk[f])
            since = float(since_k[f])
            known = fl >= 0 and since <= E.V02_KNOWN and bool(np.isfinite(epos[fl]).all())
            bel = epos[fl].astype(np.float32) if known else np.zeros(3, np.float32)
            fut = np.zeros((3, 3), np.float32)
            if known:
                v_ = evel[fl].astype(np.float32).copy()
                v_[2] = 0.0
                for hi_, hz_ in enumerate(HORIZ):
                    ext = bel + v_ * (since + hz_)
                    fut[hi_] = env.w.trace(bel, ext, E.MINS, E.MAXS)["endpos"]
            # ---- the simulator at the moment, his belief as above
            env._pro_start(0, k, 0)
            env.state = env.w.state()
            p0 = np.asarray(m["pos"][0], np.float32)
            i0 = int(np.argmin(np.linalg.norm(env.state[:n, :3] - p0, axis=1)))
            env._brain_init()
            env.brain_life[:] = False
            env.brain_life[i0] = True
            env.brain_bel[i0], env.brain_ok[i0] = bel, known
            env.brain_fut = np.zeros((n, 3, 3), np.float32)
            env.brain_fut[i0] = fut
            env.v02_bel[i0], env.v02_bel_ok[i0] = bel, known
            if getattr(env, "v02_bt_now", None) is not None:
                env.v02_bt_now[i0] = since if known else 99.0
            env.seen_t[i0] = min(since, 9.0) if known else 9.0
            if E.EN_STACK:
                env.es_h[i0, 0], env.es_a[i0, 0] = float(tr["eh"][f]), float(tr["ea"][f])
            env.intent[:] = 0
            X, C, P = env.order_feat()
            x, c, pp = X[i0].copy(), C[i0].copy(), P[i0]
            x[:, E.CMB_PASS0:E.CMB_PASS0 + 3] = PASS_START
            val = x[:, FV] > 0.5
            pos = rec["pos"]
            kd, cd, why = 0, -1, "none"
            # spam
            fs = int(np.searchsorted(T, t + SPAM_WIN))
            sm_ = (shots[:, 0] >= f) & (shots[:, 0] < fs) & np.isin(shots[:, 1], (PY.RL, PY.GL, PY.PG)) if len(shots) else np.zeros(0, bool)
            if sm_.any():
                sf = shots[sm_, 0].astype(np.int64)
                bl_ = since_all[sf] >= PY.BLIND_S
                if bl_.any():
                    land = PY.landings(rec, env.w, sf[bl_], shots[sm_, 1][bl_].astype(np.int64))
                    far = np.linalg.norm(land - rec["eye"][sf[bl_]], axis=1) >= PY.FEET_R
                    if far.any():
                        kd, why = 2, "spam"
                        r0 = CT + C0[2]
                        rr = np.arange(r0, r0 + SL[2])
                        d_ = np.linalg.norm(pp[rr][:, None, :] - land[far][None, :, :], axis=2).min(1)
                        d_ = np.where(val[rr], d_, np.inf)
                        if d_.min() <= SPAM_MATCH:
                            cd = int(d_.argmin())
            took = [j_ for t_, j_ in mine if t < t_ <= t + WIN]
            cl_ = int(tr["other"][f])                        # (the enemy's death or a teleporter in the window: his later places are not his way)
            clean_ = not any(t < x_ <= t + WIN for x_ in tr["dth"].get(cl_, ())) and not bool(np.asarray(tr["tele"][f:f4 + 1]).any())
            if not clean_:
                counts["window with his death or a teleporter (no break off, cut off or chase)"] += 1
            if kd == 0:                                      # break off
                f3 = int(np.searchsorted(T, t + OUT_S))
                if clean_ and since < CONTACT_IN and np.isfinite(epos[f]).all() and not los[f3] and \
                        not [1 for t_, _ in mine if t < t_ <= t + OUT_S]:
                    d0 = float(np.linalg.norm(epos[f] - pos[f]))
                    d3 = float(np.linalg.norm(epos[f3] - pos[f3])) if np.isfinite(epos[f3]).all() else np.inf
                    if d3 - d0 >= OUT_GROW:
                        kd, why = 3, "break off"
                        r0 = CT + C0[3]
                        rr = np.arange(r0, r0 + SL[3])
                        d_ = np.where(val[rr], np.linalg.norm(pp[rr] - pos[f3], axis=1), np.inf)
                        if d_.min() <= OUT_MATCH:
                            cd = int(d_.argmin())
            if kd == 0 and why == "none" and took:           # item
                lab_ = MI.lab[took[0]]
                if lab_ in TARGET_ITEMS and lab_ in E.INTENTS:
                    why = "item"
                    r_ = E.INTENTS.index(lab_)
                    cd = r_ if val[r_] else -1
            if kd == 0 and why == "none" and not inview[f]:  # hold
                f2 = int(np.searchsorted(T, t + HOLD_S))
                for j_ in range(env.hold_n):
                    if (np.linalg.norm(pos[f:f2 + 1] - env.hold_pos[j_], axis=1) <= HOLD_R).all():
                        why, cd = "hold", (E.HOLD_INTENT + j_) if val[E.HOLD_INTENT + j_] else -1
                        break
            if kd == 0 and why == "none" and not inview[f] and known and clean_:     # cut off, chase
                f2 = int(np.searchsorted(T, t + MOVE_S))
                if float(np.linalg.norm(pos[f2] - pos[f])) >= MOVE_MIN:
                    dest = pos[f2]
                    dh = np.array([float(np.linalg.norm(dest - epos[min(N - 1, int(np.searchsorted(T, t + hz_)))]))
                                   if np.isfinite(epos[min(N - 1, int(np.searchsorted(T, t + hz_)))]).all() else np.inf for hz_ in HORIZ])
                    db = float(np.linalg.norm(dest - bel))
                    h_star = int(dh.argmin())
                    if dh[h_star] <= CUT_R and dh[h_star] + CUT_EDGE < db:
                        kd, why = 1, "cut off"
                        cd = h_star if val[CT + C0[1] + h_star] else -1
                    elif db < float(np.linalg.norm(pos[f] - bel)) - CHASE_GAIN:
                        why = "chase"
                        cd = E.EN_INTENT if val[E.EN_INTENT] else -1
            counts["label: " + why] += 1
            counts["label: " + why + (" (its candidate)" if cd >= 0 else " (the kind alone)")] += 1
            Xs.append(x.astype(np.float16))
            Cs.append(c.astype(np.float32))
            KD.append(kd)
            CD.append(cd)
            DH.append(h_)
            WHY.append(why)
        if nd % 5 == 0:
            print("{} {}/{} moments {} {:.0f}s".format(mapn, nd + 1, len(pick), len(KD), time.time() - t0), flush=True)
    K = len(KD)
    sel = np.arange(K)
    if K > a.cap:
        sel = np.sort(rng.choice(K, a.cap, replace=False))
    out_ = a.out or OUT
    os.makedirs(out_, exist_ok=True)
    np.savez_compressed(os.path.join(out_, mapn + ".npz"), X=np.stack(Xs)[sel] if K else np.zeros((0, E.CMB_ROWS, E.CMB_F), np.float16),
                        C=np.stack(Cs)[sel] if K else np.zeros((0, len(E.CMB_CTX)), np.float32),
                        kind=np.array(KD, np.int8)[sel], cand=np.array(CD, np.int8)[sel], demo=np.array(DH)[sel], why=np.array(WHY)[sel],
                        feat=np.array(E.CMB_FEAT), ctx=np.array(E.CMB_CTX))
    meta = dict(map=mapn, demos=len(pick), moments=int(K), kept=int(len(sel)), every=a.every, seconds=round(time.time() - t0),
                settings=dict(cmd=a.cmd, run_dir=a.run_dir), counts=dict(sorted(counts.items())))
    json.dump(meta, open(os.path.join(out_, mapn + ".json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


def fit(a):
    import torch
    sys.path.insert(0, SIM)
    import head2 as head2_
    maps = MAPS if a.maps == "all" else tuple(a.maps.split(","))
    Xl, Cl, Kl, Dl, Hl, Ml = [], [], [], [], [], []
    for m_ in maps:
        p_ = os.path.join(OUT, m_ + ".npz")
        if not os.path.exists(p_):
            print("no labels for {}: left out".format(m_))
            continue
        z = np.load(p_)
        assert z["X"].shape[1:] == (head2_.CMB_ROWS, head2_.CMB_F) and z["C"].shape[1] == head2_.CMB_NCTX
        Xl.append(z["X"])
        Cl.append(z["C"])
        Kl.append(z["kind"].astype(np.int64))
        Dl.append(z["cand"].astype(np.int64))
        Hl.append(np.array([int(h, 16) % 10 == 0 for h in z["demo"]], bool))
        Ml += [m_] * len(z["kind"])
    X = torch.from_numpy(np.concatenate(Xl))
    C = torch.from_numpy(np.concatenate(Cl))
    KD = torch.from_numpy(np.concatenate(Kl))
    CD = torch.from_numpy(np.concatenate(Dl))
    HO = torch.from_numpy(np.concatenate(Hl))
    Mn = np.array(Ml)
    K = len(KD)
    print("{} moments, {} held out (a tenth of the demos)".format(K, int(HO.sum())))
    CT, C0, SL, NK = head2_.CMB_T, head2_.CMB_C0, head2_.CMB_SLOTS, head2_.CMB_NK
    VAL = head2_.CMB_VALID
    val = X[..., VAL] > 0.5
    avail = torch.stack([torch.ones(K, dtype=torch.bool)] + [val[:, CT + C0[k]:CT + C0[k] + SL[k]].any(1) for k in range(1, NK)], 1)
    # the rows a label's candidate is among (within its kind's block; the targets': 0 to 16) and its row index
    KA = avail.gather(1, KD[:, None]).squeeze(1)              # (a label whose kind has no valid candidate there: the network cannot choose it;
    print("{} labels of a kind with no valid candidate at that moment: left out of the kind's term ({})".format(   # left out of its term)
        int((~KA).sum()), {KINDS[k]: int(((~KA) & (KD == k)).sum()) for k in range(NK)}), flush=True)
    row0 = torch.tensor([0] + [CT + C0[k] for k in range(1, NK)])
    nrow = torch.tensor([CT] + [SL[k] for k in range(1, NK)])

    def nll(P, idx, train):
        x = X[idx].float()
        c = C[idx]
        kd, cd = KD[idx], CD[idx]
        kl = c @ P["U"].T + P["b"]
        kl = torch.where(avail[idx], kl, torch.full_like(kl, -1e9))
        ka = KA[idx]
        lk = torch.where(ka, -torch.log_softmax(kl, -1).gather(1, kd[:, None]).squeeze(1), torch.zeros(len(kd)))
        g = torch.tanh(x @ P["B"].T + P["c"]) @ P["v"]
        has = cd >= 0
        lc = torch.zeros_like(lk)
        if has.any():
            ii = torch.nonzero(has).squeeze(1)
            r0_, nr_ = row0[kd[ii]], nrow[kd[ii]]
            ar = torch.arange(CT)[None, :]
            rows = (r0_[:, None] + ar).clamp(max=head2_.CMB_ROWS - 1)
            gi = g[ii][torch.arange(len(ii))[:, None], rows]
            vi = val[idx][ii][torch.arange(len(ii))[:, None], rows] & (ar < nr_[:, None])
            gi = torch.where(vi, gi, torch.full_like(gi, -1e9))
            lc[ii] = -torch.log_softmax(gi, -1).gather(1, cd[ii][:, None]).squeeze(1)
        return lk, lc, has, ka

    def run(l2, idx_tr, steps):
        torch.manual_seed(0)
        m0 = head2_.make_module(dict(head2_.layout(), cmb=1))          # (the pointer's numbers part from its own start)
        fr = torch.bincount(KD[idx_tr][KA[idx_tr]], minlength=NK).float() + 1.0
        P = dict(U=torch.zeros(NK, head2_.CMB_NCTX), b=torch.log(fr / fr.sum()),
                 B=m0.op_x.weight.detach().clone(), c=m0.op_x.bias.detach().clone(), v=torch.randn(head2_.CMB_HID) * 0.01)
        for p_ in P.values():
            p_.requires_grad_(True)
        opt = torch.optim.Adam(P.values(), lr=0.01)
        bs = 4096
        g_ = torch.Generator().manual_seed(1)
        for s in range(steps):
            j = idx_tr[torch.randint(len(idx_tr), (bs,), generator=g_)]
            lk, lc, has, ka = nll(P, j, True)
            loss = lk.sum() / ka.sum().clamp(min=1) + lc.sum() / has.sum().clamp(min=1) + l2 * (P["U"].pow(2).sum() + P["B"].pow(2).sum() + P["v"].pow(2).sum())
            opt.zero_grad()
            loss.backward()
            opt.step()
        return P

    def score(P, idx):
        with torch.no_grad():
            lk, lc, has, ka = nll(P, idx, False)
        return float(lk[ka].mean()), float(lc[has].mean()) if has.any() else float("nan")

    def base(idx_tr, idx):
        fr = torch.bincount(KD[idx_tr][KA[idx_tr]], minlength=NK).float() + 1.0
        P = dict(U=torch.zeros(NK, head2_.CMB_NCTX), b=torch.log(fr / fr.sum()), B=torch.zeros(head2_.CMB_HID, head2_.CMB_F),
                 c=torch.zeros(head2_.CMB_HID), v=torch.zeros(head2_.CMB_HID))
        return score(P, idx)
    tr_ = torch.nonzero(~HO).squeeze(1)
    te_ = torch.nonzero(HO).squeeze(1)
    res = {}
    for l2 in [float(x) for x in a.l2.split(",")]:
        P = run(l2, tr_, a.steps)
        res[l2] = score(P, te_)
        print("l2 {}: held out: the kind {:.4f}, the candidate {:.4f} (the kinds' shares alone, candidates even: {:.4f}, {:.4f})".format(
            l2, *res[l2], *base(tr_, te_)), flush=True)
    l2 = min(res, key=lambda k_: res[k_][0] + (res[k_][1] if np.isfinite(res[k_][1]) else 0.0))
    P = run(l2, tr_, a.steps)
    with torch.no_grad():
        tk_ = te_[KA[te_]]
        kl = C[tk_] @ P["U"].T + P["b"]
        kl = torch.where(avail[tk_], kl, torch.full_like(kl, -1e9))
        pk = torch.softmax(kl, -1).mean(0)
    obs = torch.bincount(KD[tk_], minlength=NK).float() / max(1, len(tk_))
    out = {"ok_c.weight": P["U"].detach().tolist(), "ok_c.bias": P["b"].detach().tolist(), "op_x.weight": P["B"].detach().tolist(),
           "op_x.bias": P["c"].detach().tolist(), "op_v.weight": [P["v"].detach().tolist()], "op_v.bias": [0.0],
           "l2": l2, "held_out": dict(kind_nll=res[l2][0], cand_nll=res[l2][1], base=list(base(tr_, te_)),
                                      kinds_predicted=[round(float(x), 4) for x in pk], kinds_seen=[round(float(x), 4) for x in obs]),
           "moments": int(K), "maps": sorted(set(Mn.tolist())),
           "labels": {KINDS[k]: int((KD == k).sum()) for k in range(NK)}, "with_candidate": int((CD >= 0).sum()),
           "left_out_of_the_kind": int((~KA).sum()),
           "feat": list(np.load(os.path.join(OUT, Ml[0] + ".npz"))["feat"]), "ctx": list(np.load(os.path.join(OUT, Ml[0] + ".npz"))["ctx"])}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=0)
    print("wrote {}: l2 {}; held out: the kind {:.4f} (base {:.4f}), the candidate {:.4f} (base {:.4f}); the kinds predicted {} seen {}".format(
        a.out, l2, res[l2][0], out["held_out"]["base"][0], res[l2][1], out["held_out"]["base"][1], out["held_out"]["kinds_predicted"],
        out["held_out"]["kinds_seen"]))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd_", required=True)
    p = sp.add_parser("label")
    p.add_argument("--map", required=True)
    p.add_argument("--demos", type=int, default=40)
    p.add_argument("--every", type=float, default=0.5)
    p.add_argument("--cap", type=int, default=12000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--cmd", default=os.path.join(MAIN, "docs", "runs", "1.6", "1.6a", "train.cmd"))
    p.add_argument("--run-dir", default=os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_6a"))
    p.add_argument("--out", default="", help="the folder (default data/order_pros)")
    p = sp.add_parser("fit")
    p.add_argument("--maps", default="all")
    p.add_argument("--l2", default="0.0001,0.001,0.01")
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--out", default=os.path.join(ROOT, "docs", "runs", "1.7", "1.7a", "order_fit.json"))
    a = ap.parse_args()
    {"label": label, "fit": fit}[a.cmd_](a)


if __name__ == "__main__":
    main()

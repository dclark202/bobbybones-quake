"""(brainppl, 2026-10-24) the brain taught how people play: offline, supervised, on people's games beside self-play.

    python sim/brain_fit.py --ck <v0.4.2 policy.pt> --ppl <dir of ppl_*.npz> --sim <dir of sim_*.npz> --out <dir>
                            [--epochs 6] [--human-w 0.5] [--device cuda|cpu] [--eval-only]

Only the brain (belief.*) and its readouts (track.*, trackz.*, ahead.*) learn; nothing of the hands (encoder, attention, GRU,
pi, v, the token's layers) is in the optimizer, and the saved checkpoint is the input checkpoint with only those tensors
replaced. The lesson is the trainer's own (sim/train_duel_rnn.py, --belief with --track, --track-z, --ahead): the inputs
normalised as the trainer stores them (clip((obs - mean) / sd, +-10), half precision), belief.seq over 384-frame pieces with
the state carried between them (as rollouts), the readouts graded on the ticks, track.loss x --track (0.3) + track_z.loss x 1 +
ahead.loss x 1 (the run's weights; parts from the checkpoint's layouts), each module's gradient clipped to 0.5, Adam at the
run's rates (the brain 2.5 x 1e-4, the readouts 5 x 1e-4).

Data: sim/brain_data.py shards. People's sessions are split by session: held out are the owner's play tests of today
(data/duellive_v042) and a fixed 15% of the rest; self-play is split by match (match 0 of every map shard held out). A batch
is --lanes lanes of people and as many of self-play; the loss is human_w x people's + (1 - human_w) x self-play's.

Reported (held out, before and after): the place's error (median, units, by seconds unseen), the truth in the top-3 zones,
the 1/2/4 s places' errors against "he stays where believed now", the target's top-1 (people: the next big item he picks up
within 15 s), the appearance bands' NLL and calibration, every part's NLL.
"""
import argparse
import glob
import json
import math
import os
import random
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ahead as ahead_  # noqa: E402
import belief as belief_  # noqa: E402
import brain_data as BD  # noqa: E402
import track as track_  # noqa: E402
import track_z as trz_  # noqa: E402

assert tuple(track_.COLS) == BD.TRACK_COLS and tuple(trz_.COLS) == BD.TRZ_COLS and tuple(ahead_.COLS) + tuple(ahead_.COLS_RACE) == BD.AHEAD_COLS
K = 8
TC = 384
BRAIN_PFX = ("belief.", "track.", "trackz.", "ahead.")
UNSEEN_BINS = ((0, 1), (1, 3), (3, 6), (6, 15), (15, 1e9))
HOLD_FRAC = 0.15
TODAY = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "data", "duellive_v042", "sessions", "*_human"))}   # (the owner's play tests of 2026-10-24: held out)


# ------------------------------------------------------------------------------------------------------------- the data
def remap(aux, cols):
    """a shard's aux columns (its meta's list) -> today's COLS (a column it lacks: 0)"""
    if list(cols) == list(BD.COLS):
        return aux
    out = np.zeros(aux.shape[:-1] + (len(BD.COLS),), np.float32)
    ix = {k: i for i, k in enumerate(cols)}
    for j, k in enumerate(BD.COLS):
        if k in ix:
            out[..., j] = aux[..., ix[k]]
    return out


def load_streams(ppl_dir, sim_dir, games_only=False, demo_dir=None, demo_max=0):
    """-> list of dict(obs [F, D] f16, done [F], aux [F + 1, C], src "ppl"/"sim"/"demo", name, held)"""
    out = []
    rng = random.Random(20261024)
    fresh = lambda f_: time.time() - os.path.getmtime(f_) < 90          # (a file still being written by a builder: left out)
    for f in [f_ for f_ in sorted(glob.glob(os.path.join(ppl_dir, "ppl_*.npz"))) if not fresh(f_)] if ppl_dir else []:
        z = np.load(f)
        m = json.loads(str(z["meta"]))
        name = m["name"]
        owner_today = name in TODAY
        held = owner_today or rng.random() < HOLD_FRAC
        aux = remap(z["aux"][:, 0].astype(np.float32), m["cols"])
        if games_only and "ingame" in z.files:
            aux[:-1][~z["ingame"], BD.COLS.index("trk_on")] = 0.0
        out.append(dict(obs=z["obs"][:, 0], done=z["done"][:, 0].copy(), aux=aux, src="ppl", name=name, held=held,
                        today=owner_today, map=m["map"], policy=m.get("policy"), **({"xl": z["xl"]} if "xl" in z.files else {})))
    for f in [f_ for f_ in sorted(glob.glob(os.path.join(sim_dir, "sim_*.npz"))) if not fresh(f_)] if sim_dir else []:
        z = np.load(f)
        m = json.loads(str(z["meta"]))
        S = z["obs"].shape[1]
        for s in range(S):
            out.append(dict(obs=z["obs"][:, s], done=z["done"][:, s].copy(), aux=remap(z["aux"][:, s].astype(np.float32), m["cols"]), src="sim",
                            name="{}_{}".format(os.path.basename(f), s), held=(s // 2) == 0, today=False, map=m["map"], policy="sim",
                            **({"xl": z["xl"][:, s]} if "xl" in z.files else {})))
    dfs = [f_ for f_ in sorted(glob.glob(os.path.join(demo_dir, "demo_*.npz"))) if not fresh(f_)] if demo_dir else []
    if demo_max:
        dfs = dfs[:demo_max]
    for f in dfs:                                            # (pro demos: held out by demo file, a fixed 10% by the name's hash)
        try:
            z = np.load(f)
            m = json.loads(str(z["meta"]))
        except Exception:                                    # noqa: BLE001 - a file still being written
            continue
        held = int(m["name"][-6:], 16) % 10 == 0
        out.append(dict(obs=z["obs"][:, 0], done=z["done"][:, 0].copy(), aux=remap(z["aux"][:, 0].astype(np.float32), m["cols"]), src="demo",
                        name=m["name"], held=held, today=False, map=m["map"], policy="pro"))
    return out


def pack(streams, lanes):
    """streams into `lanes` lanes of equal length (whole pieces of TC), a reset after each stream -> obs [L, B, D] f16,
    done [L, B], aux [L + 1, B, C], valid [L, B] (padding 0)"""
    streams = sorted(streams, key=lambda s: -len(s["obs"]))
    tot = sum(len(s["obs"]) for s in streams)
    lanes = max(1, min(lanes, len(streams) * 4, tot // (TC * 4)))
    bins = [[] for _ in range(lanes)]
    ln = np.zeros(lanes, np.int64)
    for s in streams:
        j = int(np.argmin(ln))
        bins[j].append(s)
        ln[j] += len(s["obs"])
    L = int(math.ceil(ln.max() / TC) * TC)
    D = streams[0]["obs"].shape[1]
    Cn = streams[0]["aux"].shape[1]
    obs = np.zeros((L, lanes, D), np.float16)
    done = np.zeros((L, lanes), bool)
    aux = np.zeros((L + 1, lanes, Cn), np.float32)
    valid = np.zeros((L, lanes), bool)
    tpos = np.full((L, lanes), -1, np.int64)                 # (a frame's place in its own stream: the minute of the game, the scoreboard)
    for j, bl in enumerate(bins):
        p = 0
        for s in bl:
            n = len(s["obs"])
            obs[p:p + n, j] = s["obs"]
            d = s["done"].copy()
            d[-1] = True
            done[p:p + n, j] = d
            aux[p:p + n, j] = s["aux"][:n]
            valid[p:p + n, j] = True
            tpos[p:p + n, j] = np.arange(n)
            p += n
        if p < L:
            done[p - 1, j] = True
            done[L - 1, j] = True
        aux[L, j] = aux[max(0, p - 1), j]
    aux[:-1][~valid, BD.COLS.index("trk_on")] = 0.0          # (padding: no lesson)
    return dict(obs=obs, done=done, aux=aux, valid=valid, L=L, B=lanes, tpos=tpos)


def labels(P, n_target):
    """the trainer's truth at the ticks, over whole lanes: (TRK_Y [W, B, 13], TRK_M [W, B], TRZ_Y [W, B, 5], AH_Y tuple, extras)"""
    C = {k: i for i, k in enumerate(BD.COLS)}
    aux = torch.from_numpy(P["aux"])
    done = torch.from_numpy(P["done"].astype(np.float32))
    L = P["L"]
    tf = torch.arange(K - 1, L, K)
    trk_y = aux[:L][tf][..., [C[c] for c in track_.COLS]]
    trk_m = aux[:L][tf][..., C["trk_on"]] > 0.5
    trz_y = aux[:L][tf][..., [C[c] for c in trz_.COLS]]
    cols = tuple(ahead_.COLS) + tuple(ahead_.COLS_RACE)
    ys = [ahead_.labels(aux[:, c0:c0 + 64][..., [C[c] for c in cols]], done[:, c0:c0 + 64], cols, K, n_target, race=True)
          for c0 in range(0, P["B"], 64)]
    ah_y = tuple(torch.cat([y[i] for y in ys], 1) for i in range(len(ys[0])))
    dm = aux[:L][tf][..., C["src_demo"]] > 0.5
    if bool(dm.any()):                                       # (a demo's rows: the ahead places never (the enemy sent at t + h is the
        ag = aux.clone()                                     # recorder's PVS: "hidden enemies come toward me"); his target and when he
        drow = ag[..., C["src_demo"]] > 0.5                  # appears on every frame of a game, sent or not (both fully defined there))
        ag[..., C["trk_on"]] = torch.where(drow, ag[..., C["trk_game"]], ag[..., C["trk_on"]])
        ys2 = [ahead_.labels(ag[:, c0:c0 + 64][..., [C[c] for c in cols]], done[:, c0:c0 + 64], cols, K, n_target, race=True)
               for c0 in range(0, P["B"], 64)]
        ah2 = tuple(torch.cat([y[i] for y in ys2], 1) for i in range(len(ys2[0])))
        ah_y = list(ah_y)
        ah_y[1] = ah_y[1] * (~dm).float()[..., None]                                   # fut_m
        for i in (4, 5):                                                               # appear, appear_m: every game frame
            ah_y[i] = torch.where(dm, ah2[i], ah_y[i])
        ah_y[3] = ah_y[3] * (~dm).float()                    # target_m: none from demos (check A: a demo holds about 40% of the enemy's
        #                                                      big pickups, only those in the recorder's PVS: "his next take" would be wrong)
        ah_y = tuple(ah_y)
    pm = torch.ones(trk_y.shape[:2] + (len(track_.PARTS),))
    pm[..., track_.PARTS.index("band")] = (~dm).float()
    pm[..., track_.PARTS.index("own")] = (~dm).float()
    ex = dict(unseen=aux[:L][tf][..., C["unseen_s"]], zone=aux[:L][tf][..., C["en_zone"]], zone_n=aux[:L][tf][..., C["zone_n"]], pm=pm, demo=dm)
    return trk_y, trk_m, trz_y, ah_y, ex


def track_loss(o, y, weights, mask, pm):
    """track.loss with a mask per part (pm [..., 5]; all ones: exactly track.loss)"""
    m = mask.float()[..., None] * pm
    ll = track_.loglik(o, y, floor=False)
    parts = -(ll * m).sum(tuple(range(ll.dim() - 1))) / m.sum(tuple(range(m.dim() - 1))).clamp(min=1.0)
    return (parts * track_.wvec(weights, o)).sum(), parts.detach()


# ------------------------------------------------------------------------------------------------------------ the brain
class Brain(torch.nn.Module):
    def __init__(self, ck):
        super().__init__()
        self.belief = belief_.make_module(ck["belief"])
        self.track = track_.make_module(int(ck["belief"]["hid"]), ck["track"])
        self.trackz = trz_.make_module(int(ck["belief"]["hid"]), ck["track_z"])
        self.ahead = ahead_.make_module(int(ck["belief"]["hid"]), ck["ahead"])
        sd = {k: v for k, v in ck["model"].items() if k.startswith(BRAIN_PFX)}
        miss = self.load_state_dict(sd, strict=True)
        self.L = dict(belief=ck["belief"], track=ck["track"], track_z=ck["track_z"], ahead=ck["ahead"])


def norm_fn(ck, dev):
    mean = torch.from_numpy(np.asarray(ck["obs_mean"], np.float32)).to(dev)
    sd = torch.from_numpy(np.sqrt(np.asarray(ck["obs_var"], np.float64) + 1e-8).astype(np.float32)).to(dev)

    def f(o):
        return torch.clamp((o.float() - mean) / sd, -10, 10).half().float()       # (--obs-half: the trainer stores them so)
    return f


def piece(brain, P, Y, nf, dev, p0, s, w=(0.3, 1.0, 1.0)):
    """the lesson of one piece of TC frames from frame p0, the belief's state s -> (loss, parts [12], ticks, the state after)"""
    trk_y, trk_m, trz_y, ah_y, ex = Y
    x = nf(torch.from_numpy(P["obs"][p0:p0 + TC]).to(dev))
    d = torch.from_numpy(P["done"][p0:p0 + TC].astype(np.float32)).to(dev)
    sl = slice(p0 // K, p0 // K + TC // K)
    bs = belief_.seq(brain.belief, x, d, s, K)
    tm = trk_m[sl].to(dev).float()
    tl, tp = track_loss(brain.track(bs), trk_y[sl].to(dev), brain.L["track"]["weights"], tm, ex["pm"][sl].to(dev))
    zl, zp = trz_.loss(brain.trackz(bs), trz_y[sl].to(dev), brain.L["track_z"]["weights"], tm)
    al, ap, an = ahead_.loss(brain.ahead(bs), brain.L["ahead"], tuple(y[sl].to(dev) for y in ah_y), brain.L["ahead"]["weights"], torch.ones_like(tm))
    return w[0] * tl + w[1] * zl + w[2] * al, torch.cat([tp, zp, ap]).detach(), float(tm.sum()), bs[-1].detach()


def train_epoch(brain, packs_w, nf, dev, opt, anchor=None, dcols=None):
    """one pass: a step a piece, the pieces of each set (people, self-play) side by side, each set's loss times its weight;
    a set shorter than the longest starts again (its lanes end on a reset)"""
    n = max(P["L"] // TC for (P, Y), w in packs_w)
    st = [torch.zeros(P["B"], int(brain.L["belief"]["hid"]), device=dev) for (P, Y), w in packs_w]
    acc = [[] for _ in packs_w]
    for i in range(n):
        loss = 0.0
        for j, ((P, Y), w) in enumerate(packs_w):
            p0 = (i % (P["L"] // TC)) * TC
            if p0 == 0:
                st[j] = torch.zeros_like(st[j])
            l_, pr_, nt_, st[j] = piece(brain, P, Y, nf, dev, p0, st[j])
            loss = loss + w * l_
            acc[j].append(np.r_[pr_.cpu().numpy(), nt_])
        if anchor is not None and anchor[1] > 0:             # (--anchor-l2) a pull toward the start's brain (save 160's)
            loss = loss + anchor[1] * sum(((p_ - anchor[0][n_]) ** 2).sum() for n_, p_ in brain.named_parameters())
        opt.zero_grad()
        loss.backward()
        for m in (brain.track, brain.belief, brain.trackz, brain.ahead):
            torch.nn.utils.clip_grad_norm_(m.parameters(), 0.5)
        opt.step()
        drop_cols(brain, dcols)
    out = []
    for a_ in acc:
        a_ = np.array(a_)
        out.append((a_[:, :-1] * a_[:, -1:]).sum(0) / max(1.0, a_[:, -1].sum()))
    return out


def drop_cols(brain, cols):
    """the brain's input weights of these columns to zero (it reads them as nothing: the same in every domain)"""
    if cols is not None and len(cols):
        with torch.no_grad():
            brain.belief.inp.weight[:, cols] = 0.0


def run_pieces(brain, P, Y, nf, dev, train=False, opt=None, weight=1.0, step_fn=None, collect=None, w=(0.3, 1.0, 1.0)):
    """one pass over the lanes in pieces of TC frames, the belief's state carried (detached) -> mean loss parts"""
    trk_y, trk_m, trz_y, ah_y, ex = Y
    B, L = P["B"], P["L"]
    s = torch.zeros(B, int(brain.L["belief"]["hid"]), device=dev)
    obs, done = P["obs"], P["done"]
    tw = brain.L["track"]["weights"]
    zw = brain.L["track_z"]["weights"]
    aw = brain.L["ahead"]["weights"]
    acc = []
    WC = TC // K
    for p0 in range(0, L, TC):
        x = nf(torch.from_numpy(obs[p0:p0 + TC]).to(dev))
        d = torch.from_numpy(done[p0:p0 + TC].astype(np.float32)).to(dev)
        k0 = p0 // K
        sl = slice(k0, k0 + WC)
        with torch.set_grad_enabled(train):
            bs = belief_.seq(brain.belief, x, d, s, K)
            ty, tm = trk_y[sl].to(dev), trk_m[sl].to(dev).float()
            o1 = brain.track(bs)
            tl, tp = track_loss(o1, ty, tw, tm, ex["pm"][sl].to(dev))
            o2 = brain.trackz(bs)
            zl, zp = trz_.loss(o2, trz_y[sl].to(dev), zw, tm)
            ay = tuple(y[sl].to(dev) for y in ah_y)
            o3 = brain.ahead(bs)
            al, ap, an = ahead_.loss(o3, brain.L["ahead"], ay, aw, torch.ones_like(tm))
            loss = w[0] * tl + w[1] * zl + w[2] * al
            if train:
                opt.zero_grad()
                (weight * loss).backward()
                for m in (brain.track, brain.belief, brain.trackz, brain.ahead):
                    torch.nn.utils.clip_grad_norm_(m.parameters(), 0.5)
                opt.step()
        s = bs[-1].detach()
        if collect is not None:
            collect(sl, o1.detach(), o2.detach(), o3.detach(), tm)
        acc.append(torch.cat([tp, zp, ap, tm.sum()[None]]).detach().cpu().numpy())
    a = np.array(acc)
    wsum = a[:, -1].sum()
    return (a[:, :-1] * a[:, -1:]).sum(0) / max(1.0, wsum)


def evaluate(brain, P, Y, nf, dev, n_target):
    """the counters on held-out lanes"""
    trk_y, trk_m, trz_y, ah_y, ex = Y
    W = trk_y.shape[0]
    B = P["B"]
    O1 = torch.zeros(W, B, track_.D)
    O2 = torch.zeros(W, B, trz_.D)
    O3 = torch.zeros(W, B, int(brain.L["ahead"]["d"]))

    def col(sl, o1, o2, o3, tm):
        n = o1.shape[0]
        O1[sl.start:sl.start + n] = o1.cpu()
        O2[sl.start:sl.start + n] = o2.cpu()
        O3[sl.start:sl.start + n] = o3.cpu()
    brain.eval()
    parts = run_pieces(brain, P, Y, nf, dev, train=False, collect=col)
    m = trk_m.bool()
    r = dict(ticks=int(m.sum()), nll=dict(zip(["pos", "vel", "band", "hand", "own", "zone", "spd", "dir", "fut", "target", "appear", "race"],
                                              [round(float(v), 4) for v in parts])))
    pos = O1[..., track_.SL["pos"]] * track_.U
    tru = trk_y[..., 0:3].float()
    err = (pos[..., :2] - tru[..., :2]).norm(dim=-1)
    us = ex["unseen"]
    r["place_err_median"] = dict(all=round(float(err[m].median()), 1))
    for lo, hi in UNSEEN_BINS:
        mm = m & (us >= lo) & (us < hi)
        r["place_err_median"]["{}-{}s".format(lo, hi if hi < 1e8 else "")] = round(float(err[mm].median()), 1) if mm.any() else None
        r["place_err_median"]["n_{}-{}s".format(lo, hi if hi < 1e8 else "")] = int(mm.sum())
    zn = ex["zone_n"].round().long()
    zt = ex["zone"].round().long()
    hz = m & (zt >= 0) & (zn > 0)
    lg = trz_.zone_logits(O2, zn)
    top3 = lg.topk(3, dim=-1).indices
    r["zone_top3"] = round(float((top3 == zt.clamp(min=0)[..., None]).any(-1)[hz].float().mean()), 4) if hz.any() else None
    r["zone_top1"] = round(float((top3[..., 0] == zt)[hz].float().mean()), 4) if hz.any() else None
    fut, fm, tg, tmk, ap, am = ah_y[:6]
    nh = len(ahead_.HORIZ)
    f = O3[..., :5 * nh].reshape(W, B, nh, 5)
    r["ahead"] = {}
    for j, hzn in enumerate(ahead_.HORIZ):
        mj = fm[..., j] > 0.5
        e = ((f[..., j, :2] - fut[..., j, :2]).norm(dim=-1) * 1000.0)[mj]
        eb = ((pos[..., :2] / 1000.0 - fut[..., j, :2]).norm(dim=-1) * 1000.0)[mj]      # (he stays where the brain believes him now)
        r["ahead"]["{:g}s".format(hzn)] = dict(median=round(float(e.median()), 1) if len(e) else None,
                                               stays_median=round(float(eb.median()), 1) if len(eb) else None, n=int(mj.sum()))
    nt = n_target
    tlog = O3[..., 5 * nh:5 * nh + nt]
    mt = tmk > 0.5
    r["target_top1"] = round(float((tlog.argmax(-1) == tg)[mt].float().mean()), 4) if mt.any() else None
    r["target_n"] = int(mt.sum())
    if mt.any():                                             # (the people's question names an item: the brain's best item among them)
        import duel_env as E_
        ix = torch.tensor([E_.INTENTS.index(l_) for l_ in BD.BIG_LABS if l_ in E_.INTENTS])
        r["target_top1_items"] = round(float((ix[tlog[..., ix].argmax(-1)] == tg)[mt].float().mean()), 4)
    if mt.any():
        cnt = torch.bincount(tg[mt], minlength=nt).float()
        r["target_base_most_common"] = round(float(cnt.max() / cnt.sum()), 4)
    alog = torch.log_softmax(O3[..., 5 * nh + nt:5 * nh + nt + 4], -1)
    ma = am > 0.5
    if ma.any():
        pa = alog.exp()[ma]
        ta = ap[ma]
        r["appear"] = dict(nll=round(float(-alog[ma].gather(-1, ta[:, None]).mean()), 4), acc=round(float((pa.argmax(-1) == ta).float().mean()), 4),
                           pred_mean=[round(float(v), 3) for v in pa.mean(0)], true_freq=[round(float(v), 3) for v in torch.bincount(ta, minlength=4).float() / len(ta)],
                           ece=round(float(_ece(pa, ta)), 4), n=int(ma.sum()))
    brain.train()
    return r


def _ece(p, t, bins=10):
    conf, pred = p.max(-1)
    ok = (pred == t).float()
    e = 0.0
    for b in range(bins):
        mm = (conf >= b / bins) & (conf < (b + 1) / bins)
        if mm.any():
            e += float(mm.float().mean()) * abs(float(ok[mm].mean()) - float(conf[mm].mean()))
    return e


# ------------------------------------------------------------------------------------------------------- the play effect
def play_effect(ck_old, ck_new, streams, max_frames=6000, rows=8):
    """the hands with each brain over the same recorded inputs: the mean KL per frame of the policy's outputs (summed over
    the outputs) and the share of frames whose most likely choice changes, per output"""
    import test_suite as T_
    pa, pb = T_.Policy(ck_old), T_.Policy(ck_new)
    C = {k: i for i, k in enumerate(BD.COLS)}
    import btoken as btoken_
    sel = [s_ for s_ in streams if "xl" in s_ and len(s_["obs"]) >= min(max_frames, 3000)][:rows]
    assert sel, "no streams with the legs' inputs (sim/brain_data.py --xl)"
    n = min(min(len(s["obs"]) for s in sel), max_frames)
    ha, hb = pa.zeros(len(sel)), pb.zeros(len(sel))
    dims = pa.dims
    o_ = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    kl = np.zeros(len(dims))
    flip = np.zeros(len(dims))
    cnt = 0
    for t in range(n):
        ob = np.stack([s["obs"][t] for s in sel]).astype(np.float32)
        ax = np.stack([s["aux"][t] for s in sel])
        pose, zm = btoken_.pose_from_aux(ax, BD.COLS)
        xl = np.stack([s["xl"][t] for s in sel]).astype(np.float32)
        _, ha = pa.act(ob, ha, pose=pose, zmap=zm, xl=xl)
        _, hb = pb.act(ob, hb, pose=pose, zmap=zm, xl=xl)
        la, lb = pa.last_logits, pb.last_logits
        for j in range(len(dims)):
            a_ = la[:, o_[j]:o_[j + 1]]
            b_ = lb[:, o_[j]:o_[j + 1]]
            pa_ = np.exp(a_ - a_.max(1, keepdims=True)); pa_ /= pa_.sum(1, keepdims=True)
            pb_ = np.exp(b_ - b_.max(1, keepdims=True)); pb_ /= pb_.sum(1, keepdims=True)
            kl[j] += float((pa_ * (np.log(pa_ + 1e-12) - np.log(pb_ + 1e-12))).sum(1).sum())
            flip[j] += float((a_.argmax(1) != b_.argmax(1)).sum())
        cnt += len(sel)
        dn = np.array([bool(s["done"][t]) for s in sel])
        if dn.any():
            ix = np.nonzero(dn)[0]
            pa.clear(ha, ix)
            pb.clear(hb, ix)
    return dict(frames=cnt, kl_per_frame=round(float(kl.sum() / cnt), 5), kl_by_output=[round(float(v / cnt), 5) for v in kl],
                argmax_changed=[round(float(v / cnt), 4) for v in flip], argmax_changed_any_mean=round(float(flip.mean() / cnt), 4))


def play_all(a, tuned, rep):
    """the play effect: the hands on recorded inputs (with the legs' inputs) with the old and the tuned brain"""
    for k, (pd_, sd_) in (("ppl_today", (a.play_ppl, None)), ("sim", (None, a.play_sim))):
        try:
            st_ = load_streams(pd_, sd_)
            if st_:
                rep.setdefault("play", {})[k] = play_effect(a.ck, tuned, st_, max_frames=a.play_frames)
                print("play", k, json.dumps(rep["play"][k]), flush=True)
        except Exception as e:                               # noqa: BLE001
            rep.setdefault("play_error", {})[k] = repr(e)[:400]
            print("play effect failed", k, repr(e), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ck", required=True)
    ap.add_argument("--ppl", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "ppl"))
    ap.add_argument("--sim", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "sim"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sim_runs", "brainppl"))
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lanes", type=int, default=64)
    ap.add_argument("--human-w", type=float, default=0.5, help="people's sessions' share of the lesson")
    ap.add_argument("--demo-w", type=float, default=0.0, help="pro demos' share of the lesson (self-play: the rest)")
    ap.add_argument("--demo", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "demo"))
    ap.add_argument("--demo-max", type=int, default=0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--bel-scale", type=float, default=2.5)
    ap.add_argument("--rd-scale", type=float, default=5.0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--games-only", action="store_true", help="people: only the frames of real games (player_stats) are taught")
    ap.add_argument("--tag", default="brainppl")
    ap.add_argument("--play-frames", type=int, default=4000)
    ap.add_argument("--save-pack", default="", help="write the people's and demos' TRAINING data packed for the trainer's --brain-human "
                    "(obs.npy memory-mapped, done.npy, labels.pt, meta.json) into this folder and stop")
    ap.add_argument("--pack-lanes", type=int, default=16)
    ap.add_argument("--pack-src", default="ppl,demo", help="--save-pack: which sources (ppl, demo)")
    ap.add_argument("--drop-cols", default="", help="a JSON {cols: [...]}: the brain's input weights of these columns at zero (kept so)")
    ap.add_argument("--anchor-l2", type=float, default=0.0, help="a pull of the brain's weights toward the start's (sum of squares times this)")
    ap.add_argument("--play-ppl", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "ppl_xl"), help="the play effect's people's streams (with xl)")
    ap.add_argument("--play-sim", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "sim_xl"), help="... and self-play's")
    ap.add_argument("--play-only", default="", help="the play effect only, of this tuned checkpoint against --ck")
    a = ap.parse_args()
    dev = torch.device(a.device)
    torch.manual_seed(1)
    ck = torch.load(a.ck, weights_only=False, map_location="cpu")
    nt = int(ck["ahead"]["n_target"])
    t0 = time.time()
    if a.play_only:
        rep = {}
        play_all(a, a.play_only, rep)
        json.dump(rep, open(os.path.join(a.out, "play_{}.json".format(a.tag)), "w"), indent=1)
        return
    S = load_streams(a.ppl, a.sim, a.games_only, a.demo if a.demo_w > 0 or a.eval_only or a.save_pack else None, a.demo_max)
    groups = {}
    for s in S:
        k = (s["src"], "held" if s["held"] else "train") if not s["today"] else ("ppl", "today")
        groups.setdefault(k, []).append(s)
    counts = {"{}_{}".format(*k): dict(streams=len(v), hours=round(sum(len(s["obs"]) for s in v) / 40 / 3600, 2),
                                       lesson_hours=round(sum(float((s["aux"][:-1, BD.COLS.index("trk_on")] > 0.5).sum()) for s in v) / 40 / 3600, 2))
              for k, v in sorted(groups.items())}
    print("data", json.dumps(counts), "{:.0f} s".format(time.time() - t0), flush=True)
    if a.save_pack:
        tr = [s_ for s_ in S if not s_["held"] and not s_["today"] and s_["src"] in tuple(a.pack_src.split(","))]
        P = pack(tr, a.pack_lanes)
        trk_y, trk_m, trz_y, ah_y, ex = labels(P, nt)
        os.makedirs(a.save_pack, exist_ok=True)
        np.save(os.path.join(a.save_pack, "obs.npy"), P["obs"])
        np.save(os.path.join(a.save_pack, "done.npy"), P["done"])
        torch.save(dict(trk_y=trk_y.half(), trk_m=trk_m, pm=ex["pm"].half(), trz_y=trz_y.float(), ah_y=list(ah_y)), os.path.join(a.save_pack, "labels.pt"))
        srcs = {}
        for s_ in tr:
            srcs[s_["src"]] = srcs.get(s_["src"], 0) + len(s_["obs"])
        json.dump(dict(lanes=P["B"], frames=P["L"], cols=list(BD.COLS), sources={k_: round(v_ / 144000.0, 2) for k_, v_ in srcs.items()},
                       streams=len(tr), names=sorted(s_["name"] for s_ in tr), ck=os.path.basename(a.ck)),
                  open(os.path.join(a.save_pack, "meta.json"), "w"), indent=1)
        print("pack", a.save_pack, P["L"], P["B"], srcs, flush=True)
        return
    packs = {}
    for k, v in groups.items():
        nm = "{}_{}".format(*k)
        lanes = a.lanes if k[1] == "train" else max(4, min(a.lanes, len(v)))
        P = pack(v, lanes)
        packs[nm] = (P, labels(P, nt))
        print("packed", nm, P["L"], P["B"], "{:.0f} s".format(time.time() - t0), flush=True)
    nf = norm_fn(ck, dev)
    brain = Brain(ck).to(dev)
    dcols = None
    if a.drop_cols:
        dcols = torch.tensor(json.load(open(a.drop_cols))["cols"], dtype=torch.long, device=dev)
        drop_cols(brain, dcols)
        print("the brain reads none of {} columns ({})".format(len(dcols), a.drop_cols), flush=True)
    rep = dict(ck=os.path.basename(a.ck), data=counts, args=vars(a))
    evs = [k for k in packs if not k.endswith("_train")]
    rep["before"] = {k: evaluate(brain, *packs[k], nf, dev, nt) for k in evs}         # (with --drop-cols: the start with those columns unread)
    print("before", json.dumps(rep["before"]), flush=True)
    if not a.eval_only:
        opt = torch.optim.Adam([dict(params=list(brain.track.parameters()) + list(brain.trackz.parameters()) + list(brain.ahead.parameters()),
                                     lr=a.lr * a.rd_scale),
                                dict(params=brain.belief.parameters(), lr=a.lr * a.bel_scale)])
        anc = ({n_: p_.detach().clone() for n_, p_ in brain.named_parameters()}, a.anchor_l2) if a.anchor_l2 > 0 else None
        hp, sp, dp = packs.get("ppl_train"), packs.get("sim_train"), packs.get("demo_train")
        wd = a.demo_w if dp else 0.0
        ws = 1.0 - a.human_w - wd
        rep["epochs"] = []
        best = None
        for ep in range(a.epochs):
            te = time.time()
            # people's and self-play's pieces in turn, each weighted (both lanes' sets walk their own pieces)
            pw = [(q_, w_) for q_, w_ in ((hp, a.human_w), (dp, wd), (sp, ws)) if q_ is not None and w_ > 0]
            res = train_epoch(brain, pw, nf, dev, opt, anchor=anc, dcols=dcols)
            lh, ls = res[0], res[-1]
            ev = {k: evaluate(brain, *packs[k], nf, dev, nt) for k in evs}
            score = sum(ev[k]["nll"]["pos"] * 0.3 + ev[k]["nll"]["zone"] * 0.5 + ev[k]["nll"]["fut"] * 0.5 + ev[k]["nll"]["target"] * 0.25
                        for k in evs if k.startswith(("ppl", "demo")))
            sscore = sum(ev[k]["nll"]["pos"] * 0.3 + ev[k]["nll"]["zone"] * 0.5 + ev[k]["nll"]["fut"] * 0.5 for k in evs if k.startswith("sim"))
            row = dict(epoch=ep + 1, train_ppl=None if lh is None else [round(float(v), 4) for v in lh],
                       train_sim=None if ls is None else [round(float(v), 4) for v in ls], held=ev, score_ppl=round(score, 4),
                       score_sim=round(sscore, 4), secs=round(time.time() - te))
            rep["epochs"].append(row)
            print("epoch", json.dumps(row), flush=True)
            score = score + sscore                           # (the choice: people's held-out and self-play's held-out together: no forgetting bought)
            if best is None or score < best[0]:
                best = (score, ep + 1, {k: v.detach().cpu().clone() for k, v in brain.state_dict().items()})
        brain.load_state_dict(best[2])
        rep["best_epoch"] = best[1]
        rep["after"] = {k: evaluate(brain, *packs[k], nf, dev, nt) for k in evs}
        print("after", json.dumps(rep["after"]), flush=True)
        ck2 = dict(ck)
        md = dict(ck["model"])
        for n_, v in brain.state_dict().items():
            for pf, mod in (("belief.", "belief"), ("track.", "track"), ("trackz.", "trackz"), ("ahead.", "ahead")):
                if n_.startswith(pf):
                    assert n_ in md and md[n_].shape == v.shape, n_
                    md[n_] = v.detach().cpu().to(md[n_].dtype)
        changed = [k for k in md if not torch.equal(md[k], ck["model"][k])]
        assert all(k.startswith(BRAIN_PFX) for k in changed), changed
        ck2["model"] = md
        ck2["brainppl"] = dict(src=os.path.basename(a.ck), human_w=a.human_w, epochs=a.epochs, best_epoch=best[1], data=counts,
                               changed=len(changed))
        outp = os.path.join(a.out, "policy_{}.pt".format(a.tag))
        torch.save(ck2, outp)
        rep["saved"] = outp
        rep["changed_tensors"] = changed
        print("saved", outp, len(changed), "tensors", flush=True)
        play_all(a, outp, rep)
    json.dump(rep, open(os.path.join(a.out, "report_{}.json".format(a.tag)), "w"), indent=1)
    print("done {:.0f} s".format(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()

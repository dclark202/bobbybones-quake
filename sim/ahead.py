"""v0.4.1: the brain's readouts of what comes next (the trainer's --ahead; docs/v0.4.0/RUN_v0.4.1.md, BELIEF_LOOP.md part 1).
A third readout on the belief's state, beside sim/track.py and sim/track_z.py: a lesson only (graded against what happened
later in the same rollout), no pay, and nothing reads it (not part of the hands' token yet).

  fut    the enemy's place in 1, 2 and 4 s, in his facing of NOW (forward, left, up; thousands of units), each with two log
         spreads (across the floor, up and down): Gaussians as sim/track.py's place
  target what the enemy is going for: his own intention (the simulator's en_target: a network's seat its intention, the
         item runner's rule; nothing to say of the rest), over the intention head's choices
  appear when he next comes into view, while he is not in view now: under 1 s, 1-3 s, 3-6 s, over 6 s
  race   (a layout with "race": the simulator's TRACK_RACE=1) the item race for the mega and the red armor: his walking-time
         lead (the enemy's seconds of way to it minus his, in tens of seconds; a Gaussian with a spread) and, while it is
         down, the chance that the enemy is within RACE_THERE seconds of it when it comes back (if that is inside the rollout)

The truth comes from the rollout's own frames (info["aux"], TRACK_TRUTH=1) and is graded on the belief's ticks; a question
whose answer lies past the rollout's end, or past a death or a frag (his memory and the brain are cleared; the enemy
respawns), is left out. Module: Linear(256 -> hid) + ReLU + Linear(hid -> D), its last layer at zero (bias: the prior
spreads), from a random stream of its own. Not built here: the item race for the mega and the red armor (his walking-time
lead, the chance the enemy is there at the spawn): built on 2026-10-23 as the part "race" (TRACK_RACE=1 gives its truth).
"""
import math

import torch

HORIZ = (1.0, 2.0, 4.0)                    # seconds ahead
FR = tuple(int(round(h / 0.025)) for h in HORIZ)
APPEAR = (1.0, 3.0, 6.0)                   # the bands' edges (seconds)
APPEAR_FR = int(round(APPEAR[-1] / 0.025))
U = 1000.0
LS_XY = (math.log(0.04), math.log(4.0))
LS_Z = (math.log(0.03), math.log(1.5))
PRIOR = dict(ls_xy=math.log(0.8), ls_z=math.log(0.15))
PARTS = ("fut", "target", "appear", "race")
DEFAULT_W = dict(fut=0.5, target=0.25, appear=0.25, race=0.25)
COLS = ("en_fwd", "en_left", "en_up", "x", "y", "z", "yaw", "en_in_view", "en_target", "frag", "fragged", "trk_on")
COLS_RACE = ("mega_s", "red_s", "race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra")
RACE_CAP = 30.0                   # (the simulator's: no way)
RACE_THERE = 1.0                  # the enemy "there" at the respawn: within this many seconds of way of it
LEAD_U = 10.0                     # the lead in tens of seconds
LS_L = (math.log(0.02), math.log(3.0))          # the lead's spread: 0.2 to 30 s
PRIOR_L = math.log(0.5)


def layout(n_target, hid=256, inp=256, weights=None, race=False):
    d = 5 * len(HORIZ) + int(n_target) + len(APPEAR) + 1 + (6 if race else 0)
    return dict(version=1, hid=int(hid), inp=int(inp), d=d, n_target=int(n_target), horiz=list(HORIZ), appear=list(APPEAR),
                parts=list(PARTS), weights=dict(weights or DEFAULT_W), cols=list(COLS + (COLS_RACE if race else ())),
                race=bool(race), src="belief")


def race_at(L):
    """where the race's six outputs begin (lead, its log spread, there: mega then red)"""
    return 5 * len(HORIZ) + int(L["n_target"]) + len(APPEAR) + 1


def parse_weights(s):
    if str(s).strip() in ("1", "default"):
        return dict(DEFAULT_W)
    w = {k: 0.0 for k in PARTS}
    for part in str(s).split(","):
        if ":" in part:
            k, v = part.split(":")
            assert k.strip() in PARTS, "--ahead: {} is not one of {}".format(k, PARTS)
            w[k.strip()] = float(v)
    return w


def _inv(v, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * math.atanh((v - mid) / half)


def _squash(x, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * torch.tanh((x - mid) / half)


def make_module(H, L, seed=4043):
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        m = nn.Sequential(nn.Linear(H, int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), int(L["d"])))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
        for k in range(len(HORIZ)):
            m[2].bias[5 * k + 3] = _inv(PRIOR["ls_xy"], *LS_XY)
            m[2].bias[5 * k + 4] = _inv(PRIOR["ls_z"], *LS_Z)
        if L.get("race"):
            r0 = race_at(L)
            for k in range(2):
                m[2].bias[r0 + 3 * k + 1] = _inv(PRIOR_L, *LS_L)
    return m


def labels(aux, done, cols, K, n_target, race=False):
    """the truth at the belief's ticks of a rollout: aux [T + 1, N, C] (float), done [T, N] -> (fut [W, N, 3 horizons, 3],
    fut_m [W, N, 3], target [W, N] long, target_m [W, N], appear [W, N] long, appear_m [W, N]) and with race: (lead [W, N, 2],
    lead_m, there [W, N, 2], there_m), W = T / K, tick k on frame k K + K - 1"""
    C = {c: i for i, c in enumerate(cols)}
    T = done.shape[0]
    aux = aux.float()
    dn = (done > 0.5).float()
    ev = ((aux[:T + 1, :, C["frag"]] > 0.5) | (aux[:T + 1, :, C["fragged"]] > 0.5)).float()      # a frag of either at frame t
    # breaks between t and t + d: a reset after any frame t .. t + d - 1 or a frag at any frame t + 1 .. t + d
    cd = torch.cat([torch.zeros_like(dn[:1]), torch.cumsum(dn, 0)], 0)          # cd[t] = resets after frames < t
    ce = torch.cat([torch.zeros_like(ev[:1]), torch.cumsum(ev, 0)], 0)          # ce[t] = frags at frames < t
    tf = torch.arange(K - 1, T, K, device=aux.device)
    W = len(tf)
    on = aux[:, :, C["trk_on"]] > 0.5
    yaw = torch.deg2rad(aux[..., C["yaw"]])
    me = aux[..., [C["x"], C["y"], C["z"]]]
    rel = aux[..., [C["en_fwd"], C["en_left"], C["en_up"]]]
    c, s = torch.cos(yaw), torch.sin(yaw)
    ew = torch.stack([me[..., 0] + c * rel[..., 0] - s * rel[..., 1], me[..., 1] + s * rel[..., 0] + c * rel[..., 1],
                      me[..., 2] + rel[..., 2]], -1)                            # the enemy's place on the map, every frame
    N = aux.shape[1]
    fut = torch.zeros(W, N, len(FR), 3, device=aux.device)
    fm = torch.zeros(W, N, len(FR), device=aux.device)
    for j, d in enumerate(FR):
        t2 = tf + d
        ok = t2 <= T
        t2c = t2.clamp(max=T)
        dw = ew[t2c] - me[tf]
        ct, st = c[tf], s[tf]
        fut[:, :, j, 0] = (ct * dw[..., 0] + st * dw[..., 1]) / U
        fut[:, :, j, 1] = (-st * dw[..., 0] + ct * dw[..., 1]) / U
        fut[:, :, j, 2] = dw[..., 2] / U
        clean = ((cd[t2c] - cd[tf]) < 0.5) & ((ce[(t2c + 1).clamp(max=T + 1)] - ce[tf + 1]) < 0.5)
        fm[:, :, j] = (ok[:, None] & on[tf] & on[t2c] & clean).float()
    tg = aux[tf][..., C["en_target"]].round().long()
    tm = (on[tf] & (tg >= 0) & (tg < n_target)).float()
    # when he comes into view: the first frame after t with the enemy in view
    vis = aux[:T + 1, :, C["en_in_view"]] > 0.5
    big = T + 10
    idx = torch.arange(T + 1, device=aux.device)[:, None].expand(T + 1, N)
    nxt = torch.where(vis, idx, torch.full_like(idx, big))
    nxt = torch.flip(torch.cummin(torch.flip(nxt, [0]), 0).values, [0])         # nxt[t] = first frame >= t in view
    t1 = (tf + 1).clamp(max=T)
    fa = nxt[t1]                                                                 # [W, N]
    secs = (fa - tf[:, None]).float() * 0.025
    band = (secs >= APPEAR[0]).long() + (secs >= APPEAR[1]).long() + (secs >= APPEAR[2]).long()
    seen_in = fa <= T
    horizon = (tf[:, None] + APPEAR_FR) <= T
    end = torch.where(seen_in, fa, (tf[:, None] + APPEAR_FR).clamp(max=T))
    clean = ((cd.gather(0, end) - cd[tf]) < 0.5) & ((ce.gather(0, (end + 1).clamp(max=T + 1)) - ce[tf + 1]) < 0.5)
    am = (on[tf] & ~vis[tf] & clean & (seen_in | horizon)).float()
    out = (fut, fm, tg.clamp(0, n_target - 1), tm, band, am)
    if not race:
        return out
    lead = torch.zeros(W, N, 2, device=aux.device)
    lm = torch.zeros(W, N, 2, device=aux.device)
    there = torch.zeros(W, N, 2, device=aux.device)
    thm = torch.zeros(W, N, 2, device=aux.device)
    for k, (cs, cme, cen) in enumerate((("mega_s", "race_me_mh", "race_en_mh"), ("red_s", "race_me_ra", "race_en_ra"))):
        me_, en_ = aux[tf][..., C[cme]], aux[tf][..., C[cen]]
        lead[..., k] = (en_ - me_) / LEAD_U
        lm[..., k] = (on[tf] & (me_ < RACE_CAP - 0.01) & (en_ < RACE_CAP - 0.01)).float()
        sk = aux[tf][..., C[cs]]                                                 # seconds until it is back (0: up; 40: no such item)
        tr = tf[:, None] + torch.ceil(sk / 0.025).long()                        # the frame it comes back on
        ok = on[tf] & (sk > 0.01) & (sk < 39.0) & (tr <= T)
        ent = aux[tr.clamp(max=T), torch.arange(N, device=aux.device)[None, :].expand(W, N), C[cen]]
        there[..., k] = (ent <= RACE_THERE).float()
        thm[..., k] = ok.float()
    return out + (lead, lm, there, thm)


def loss(o, L, y, weights, mask):
    """the lesson: o [W, B, D]; y = labels() of these players; mask [W, B] (the learner's frames) -> (loss, parts [4], their
    frames [4]) (the race 0 without it)"""
    fut, fm, tg, tm, ap, am = y[:6]
    o = o.float()
    nh = len(HORIZ)
    f = o[..., :5 * nh].reshape(*o.shape[:-1], nh, 5)
    lxy = _squash(f[..., 3], *LS_XY)
    lz = _squash(f[..., 4], *LS_Z)
    e = f[..., :3] - fut
    nll = (0.5 * ((e[..., 0] ** 2 + e[..., 1] ** 2) * torch.exp(-2 * lxy) + e[..., 2] ** 2 * torch.exp(-2 * lz))
           + 1.5 * math.log(2 * math.pi) + 2 * lxy + lz + 3 * math.log(U))
    m = mask.float()
    mf = fm * m[..., None]
    p_f = (nll * mf).sum() / mf.sum().clamp(min=1.0)
    nt = int(L["n_target"])
    lt = torch.log_softmax(o[..., 5 * nh:5 * nh + nt], -1).gather(-1, tg[..., None])[..., 0]
    mt = tm * m
    p_t = -(lt * mt).sum() / mt.sum().clamp(min=1.0)
    la = torch.log_softmax(o[..., 5 * nh + nt:5 * nh + nt + len(APPEAR) + 1], -1).gather(-1, ap[..., None])[..., 0]
    ma = am * m
    p_a = -(la * ma).sum() / ma.sum().clamp(min=1.0)
    p_r = o.new_zeros(())
    nr = o.new_zeros(())
    if L.get("race") and len(y) > 6:
        lead, lm, there, thm = y[6:]
        r0 = race_at(L)
        rr = o[..., r0:r0 + 6].reshape(*o.shape[:-1], 2, 3)
        ls = _squash(rr[..., 1], *LS_L)
        nll_l = 0.5 * ((rr[..., 0] - lead) * torch.exp(-ls)) ** 2 + ls + 0.5 * math.log(2 * math.pi) + math.log(LEAD_U)
        nll_t = torch.nn.functional.binary_cross_entropy_with_logits(rr[..., 2], there, reduction="none")
        ml = lm * m[..., None]
        mth = thm * m[..., None]
        nr = ml.sum() + mth.sum()
        p_r = ((nll_l * ml).sum() + (nll_t * mth).sum()) / nr.clamp(min=1.0)
    pv = torch.stack([p_f, p_t, p_a, p_r])
    w = torch.tensor([float(weights.get(k, 0.0)) for k in PARTS], dtype=torch.float32, device=o.device)
    return (pv * w).sum(), pv.detach(), torch.stack([mf.sum(), mt.sum(), ma.sum(), nr]).detach()


def errors(o, y, mask):
    """the counters: the median-free means of the place's error (units) at each horizon, the target right, the band right"""
    fut, fm, tg, tm, ap, am = y[:6]
    nh = len(HORIZ)
    f = o.float()[..., :5 * nh].reshape(*o.shape[:-1], nh, 5)
    m = mask.float()
    mf = fm * m[..., None]
    err = ((f[..., :2] - fut[..., :2]).norm(dim=-1) * U * mf).sum((0, 1)) / mf.sum((0, 1)).clamp(min=1.0)
    return err.detach()

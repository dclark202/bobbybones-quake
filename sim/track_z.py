"""v0.4.0 brain: the readout's second part (the trainer's --track-z), beside sim/track.py's 27 outputs, reading the same belief
state. The owner, 2026-10-23: "let's replace the 10+s range with the distribution over locations"; 2026-10-22: "speed+direction
separately makes sense. Probably both can be averaged over a short window".

  zone  odds over the map's zones (sim/zonemap.py; MAX_Z outputs, masked to the map's own count): where the enemy is, as a
        distribution, so a split belief (two rooms) can be said; a single place with a spread cannot
  spd   the enemy's mean horizontal speed over the last 0.2 s (the simulator's en_spd8), a Gaussian (mean, log spread)
  dir   the way he moved over the same 0.2 s (the direction of en_mvf8, en_mvl8: his mean velocity turned to the reader's
        facing), a von Mises in natural form: two outputs eta = kappa (cos mu, sin mu), log p = eta . u(theta) - log(2 pi
        I0(|eta|)); eta = 0 is the even spread over every direction (the start: no atan2, no division at zero). The lesson
        weighs a frame's direction by min(1, |mean velocity| / DIR_FULL): a still or zig-zagging enemy's way counts little.

Module: Linear(belief H -> hid) + ReLU + Linear(hid -> D), the last layer at zero (bias: the speed's prior): at the start the
zones are even over the map's count, the speed the prior, the direction even. Lesson only (no pay); nothing reads it.
"""
import math

import torch

MAX_Z = 24                        # (sim/zonemap.py's MAX_Z)
PARTS = ("zone", "spd", "dir")
D = MAX_Z + 2 + 2
SL = dict(zone=slice(0, MAX_Z), spd=MAX_Z, ls_s=MAX_Z + 1, dir=slice(MAX_Z + 2, MAX_Z + 4))
U = 1000.0                        # units a second of the speed
LS_S = (math.log(0.01), math.log(0.6))          # the speed's spread: 10 to 600 units a second
PRIOR = dict(spd=0.30, ls_s=math.log(0.13))     # the last layer's bias at the start (the enemy's mean speed is ~300 +- 130)
DIR_FULL = 320.0                  # a direction counts fully from this mean velocity on (units a second)
KAPPA_MAX = 200.0                 # (|eta| is clamped here in the likelihood: about 4 degrees of spread)
COLS = ("en_zone", "zone_n", "en_spd8", "en_mvf8", "en_mvl8")
DEFAULT_W = dict(zone=0.5, spd=0.25, dir=0.25)


def layout(hid=256, weights=None, inp=256):
    return dict(version=1, hid=int(hid), d=D, inp=int(inp), parts=list(PARTS), weights=dict(weights or DEFAULT_W), cols=list(COLS),
                max_z=MAX_Z, units=U, dir_full=DIR_FULL, src="belief")


def _squash(x, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * torch.tanh((x - mid) / half)


def make_module(H, L, seed=4041):
    """Linear(H, hid), ReLU, Linear(hid, D), its last layer at zero and the bias the prior; from a random stream of its own"""
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        m = nn.Sequential(nn.Linear(H, int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), D))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
        m[2].bias[SL["spd"]] = PRIOR["spd"]
        lo, hi = LS_S
        mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
        m[2].bias[SL["ls_s"]] = mid + half * math.atanh((PRIOR["ls_s"] - mid) / half)
    return m


def parse_weights(s):
    w = {k: 0.0 for k in PARTS}
    for part in str(s).split(","):
        if ":" in part:
            k, v = part.split(":")
            assert k.strip() in PARTS, "--track-z: {} is not one of {}".format(k, PARTS)
            w[k.strip()] = float(v)
    return w


def zone_logits(o, zn):
    """the zones' log-odds masked to the map's count: o [..., D], zn [...] (the map's zones; 0: none) -> [..., MAX_Z]"""
    lg = o[..., SL["zone"]].float()
    ar = torch.arange(MAX_Z, device=o.device)
    return lg.masked_fill(ar >= zn[..., None].clamp(min=1), -1e4)


def i0_log(k):
    """log I0(k) for k >= 0 (i0e(k) = exp(-k) I0(k))"""
    return torch.log(torch.special.i0e(k)) + k


def parts(o, y):
    """per frame: (log-likelihoods [..., 3] of zone, speed (per unit a second), direction (per radian); the direction's weight
    [...]; has-zone mask [...]). y [..., len(COLS)] the raw columns"""
    o = o.float()
    y = y.float()
    zt, zn = y[..., 0].round().long(), y[..., 1].round().long()
    hz = (zt >= 0) & (zn > 0) & (zt < zn)
    lz = torch.log_softmax(zone_logits(o, zn), -1).gather(-1, zt.clamp(0, MAX_Z - 1)[..., None])[..., 0]
    lz = torch.where(hz, lz, torch.zeros_like(lz))
    s = y[..., 2] / U
    ls = _squash(o[..., SL["ls_s"]], *LS_S)
    l_s = -0.5 * ((o[..., SL["spd"]] - s) * torch.exp(-ls)) ** 2 - ls - 0.5 * math.log(2 * math.pi) - math.log(U)
    mv = y[..., 3:5]
    mn = mv.norm(dim=-1)
    u = mv / mn.clamp(min=1e-6)[..., None]
    eta = o[..., SL["dir"]]
    k = torch.sqrt((eta ** 2).sum(-1) + 1e-12)
    scale = torch.where(k > KAPPA_MAX, KAPPA_MAX / k, torch.ones_like(k))
    eta = eta * scale[..., None]
    k = k * scale
    l_d = (eta * u).sum(-1) - math.log(2 * math.pi) - i0_log(k)
    wd = (mn / DIR_FULL).clamp(max=1.0) * (mn > 1.0).float()
    return torch.stack([lz, l_s, l_d], -1), wd, hz


def loss(o, y, weights, mask):
    """the lesson: weighted negative log-likelihoods averaged over the mask (the zone over the frames with a zone, the
    direction weighted by wd) -> (loss, the parts' means [3] (the direction's per unit of its weight))"""
    ll, wd, hz = parts(o, y)
    m = mask.float()
    mz = m * hz.float()
    md = m * wd
    d = lambda w: w.sum().clamp(min=1.0)
    pz = -(ll[..., 0] * mz).sum() / d(mz)
    ps = -(ll[..., 1] * m).sum() / d(m)
    pd = -(ll[..., 2] * md).sum() / d(md)
    pv = torch.stack([pz, ps, pd])
    w = torch.tensor([float(weights.get(k, 0.0)) for k in PARTS], dtype=torch.float32, device=o.device)
    return (pv * w).sum(), pv.detach()


def readable(o, zn):
    """the counters' numbers: zone odds [..., MAX_Z], the speed (units a second), its spread, the direction's angle (radians,
    from his facing, left positive) and its concentration kappa"""
    o = o.float()
    pz = torch.softmax(zone_logits(o, zn), -1)
    eta = o[..., SL["dir"]]
    return (pz, o[..., SL["spd"]] * U, torch.exp(_squash(o[..., SL["ls_s"]], *LS_S)) * U, torch.atan2(eta[..., 1], eta[..., 0]),
            eta.norm(dim=-1))

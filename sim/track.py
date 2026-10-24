"""v0.3.11: his belief of the enemy, read out of his memory, and how it is scored (docs/v0.3.11/INFO_PAY.md).

The readout is a small part of the network (the trainer's --track; not an action, never an input): from what his outputs
read (his memory, `zl`) a layer of 256 and a last layer that starts at zero, to

  pos   the enemy's place from him, turned to his facing (forward, left, up), in thousands of units, with two spreads
        (log of the standard deviation: across the floor, and up and down)
  vel   the enemy's horizontal velocity, turned to his facing (thousands of units a second), with one spread
  band  his stack's band (health and armor: under 75, 75 to 124, 125 to 200, over 200: the simulator's AUX_BANDS)
  hand  the weapon in his hand (the simulator's WEAPONS)
  own   which of the rocket launcher, railgun, lightning gun, plasma gun, grenade launcher and shotgun he owns

Two uses of the same numbers (both proper scoring rules: a belief scores best on average by saying what it believes):
  loss()    the lesson (supervised): the negative log-likelihood of the truth, part by part, plain
  score()   the pay's score: the log-likelihood with a floor, so that one wild miss cannot cost more than a set amount
            and the score is bounded: each Gaussian is mixed with a uniform (EPS of the mass) over a box of the size of a
            duel map (place) or a disk of 900 units a second (velocity); each category with EPS_CAT spread evenly
The trainer's --info-pay pays k * (his score - the enemy's score) every --info-every frames: zero-sum by construction.
"""
import math

import torch

WEAPONS_N = 9                     # the simulator's WEAPONS: rl, rg, lg, mg, sg, gl, pg, hmg, g
OWN = ("rl", "rg", "lg", "pg", "gl", "sg")
PARTS = ("pos", "vel", "band", "hand", "own")
D = 3 + 2 + 2 + 1 + 4 + WEAPONS_N + len(OWN)          # 27 outputs
SL = dict(pos=slice(0, 3), ls_xy=3, ls_z=4, vel=slice(5, 7), ls_v=7, band=slice(8, 12), hand=slice(12, 21), own=slice(21, 27))
U = 1000.0                        # units of the readout's places (and units a second of its velocity)
# the spreads' ranges (a smooth squash keeps every spread inside, with a gradient everywhere): 40 units to 4000 across the
# floor, 30 to 1500 up and down, 30 to 1000 units a second
LS_RANGE = dict(ls_xy=(math.log(0.04), math.log(4.0)), ls_z=(math.log(0.03), math.log(1.5)), ls_v=(math.log(0.03), math.log(1.0)))
EPS, VOL = 0.05, 1.6e10           # the place's floor: 5% of the mass spread over a 4000 x 4000 x 1000 unit box
EPS_V, AREA_V = 0.05, math.pi * 900.0 ** 2
EPS_CAT = 0.02
# the truth's columns, in this order, from the simulator's info["aux"] (TRACK_TRUTH=1)
COLS = ("en_fwd", "en_left", "en_up", "en_vfwd", "en_vleft", "en_band", "en_weapon") + tuple("en_own_" + w for w in OWN)
DEFAULT_W = dict(pos=1.0, vel=0.25, band=0.5, hand=0.25, own=0.25)
PRIOR = dict(ls_xy=math.log(0.8), ls_z=math.log(0.15), ls_v=math.log(0.3))      # the last layer's bias at the start


def layout(hid=256, weights=None):
    """the checkpoint's "track" entry: what the readout is and how its pay scores"""
    return dict(version=1, hid=int(hid), d=D, parts=list(PARTS), weights=dict(weights or DEFAULT_W), cols=list(COLS), units=U,
                eps=EPS, vol=VOL, eps_v=EPS_V, area_v=AREA_V, eps_cat=EPS_CAT, weapons_n=WEAPONS_N, own=list(OWN))


def make_module(H, L):
    """the readout: Linear(H, hid), ReLU, Linear(hid, D), its last layer at zero (bias: the prior spreads). Made without a
    draw from the global random stream (the stream after it is the one without)"""
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        m = nn.Sequential(nn.Linear(H, int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), D))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
        for k, v in PRIOR.items():                           # (through the squash's inverse: the spreads start exactly at the prior)
            lo, hi = LS_RANGE[k]
            mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
            m[2].bias[SL[k]] = mid + half * math.atanh((v - mid) / half)
    return m


def parse_weights(s):
    """"pos:1,vel:0.25,..." -> dict (missing parts: 0)"""
    w = {k: 0.0 for k in PARTS}
    for part in str(s).split(","):
        if ":" in part:
            k, v = part.split(":")
            assert k.strip() in PARTS, "--track-parts: {} is not one of {}".format(k, PARTS)
            w[k.strip()] = float(v)
    return w


def _squash(x, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * torch.tanh((x - mid) / half)


def spreads(o):
    """log standard deviations (in units of U), squashed into their ranges: [..., 3] (xy, z, v)"""
    return torch.stack([_squash(o[..., SL[k]], *LS_RANGE[k]) for k in ("ls_xy", "ls_z", "ls_v")], -1)


def truth(y):
    """y [..., len(COLS)] the raw columns -> (place / U [..., 3], velocity / U [..., 2], band, weapon [...] long, own [..., 6])"""
    y = y.float()
    return (y[..., 0:3] / U, y[..., 3:5] / U, y[..., 5].round().long().clamp(0, 3), y[..., 6].round().long().clamp(0, WEAPONS_N - 1),
            y[..., 7:7 + len(OWN)].clamp(0, 1))


def loglik(o, y, floor=True):
    """the log-likelihood of the truth under the readout, part by part: [..., 5] (nats; the places in units, so that the
    numbers are the same whatever U is). floor=False: plain (the lesson); True: with the floors (the pay's score)"""
    o = o.float()
    p, v, b, w, own = truth(y)
    ls = spreads(o)
    lxy, lz, lv = ls[..., 0], ls[..., 1], ls[..., 2]
    e = o[..., SL["pos"]] - p
    lg_p = (-0.5 * ((e[..., 0] ** 2 + e[..., 1] ** 2) * torch.exp(-2 * lxy) + e[..., 2] ** 2 * torch.exp(-2 * lz))
            - 1.5 * math.log(2 * math.pi) - 2 * lxy - lz - 3 * math.log(U))
    ev = o[..., SL["vel"]] - v
    lg_v = -0.5 * (ev ** 2).sum(-1) * torch.exp(-2 * lv) - math.log(2 * math.pi) - 2 * lv - 2 * math.log(U)
    lb = torch.log_softmax(o[..., SL["band"]], -1)
    lh = torch.log_softmax(o[..., SL["hand"]], -1)
    lo = o[..., SL["own"]]
    if floor:
        lg_p = torch.logaddexp(lg_p + math.log(1 - EPS), torch.full_like(lg_p, math.log(EPS / VOL)))
        lg_v = torch.logaddexp(lg_v + math.log(1 - EPS_V), torch.full_like(lg_v, math.log(EPS_V / AREA_V)))
        lb = torch.log((1 - EPS_CAT) * lb.exp() + EPS_CAT / 4)
        lh = torch.log((1 - EPS_CAT) * lh.exp() + EPS_CAT / WEAPONS_N)
        po = torch.sigmoid(lo)
        lgo = (own * torch.log((1 - EPS_CAT) * po + EPS_CAT / 2) + (1 - own) * torch.log((1 - EPS_CAT) * (1 - po) + EPS_CAT / 2)).sum(-1)
    else:
        lgo = -torch.nn.functional.binary_cross_entropy_with_logits(lo, own, reduction="none").sum(-1)
    lg_b = lb.gather(-1, b[..., None])[..., 0]
    lg_h = lh.gather(-1, w[..., None])[..., 0]
    return torch.stack([lg_p, lg_v, lg_b, lg_h, lgo], -1)


def wvec(weights, like):
    return torch.tensor([float(weights.get(k, 0.0)) for k in PARTS], dtype=torch.float32, device=like.device)


def score(o, y, weights):
    """the pay's score: the weighted sum of the floored log-likelihoods [...] (nats)"""
    return (loglik(o, y, floor=True) * wvec(weights, o)).sum(-1)


def loss(o, y, weights, mask):
    """the lesson: the weighted negative plain log-likelihood, averaged over the mask; and the parts' means [5]"""
    m = mask.float()
    n = m.sum().clamp(min=1.0)
    ll = loglik(o, y, floor=False)
    parts = -(ll * m[..., None]).sum(tuple(range(ll.dim() - 1))) / n
    return (parts * wvec(weights, o)).sum(), parts.detach()


def pair_pay(sc, on, k):
    """the zero-sum pay of seats in pairs (seat i's enemy is i ^ 1): k * (sc[i] - sc[i ^ 1]) where both seats are on (the
    game, both alive), else 0. sc, on [N] (N even) -> [N]; sums to zero over every pair"""
    e = torch.arange(len(sc), device=sc.device) ^ 1
    both = on & on[e]
    return torch.where(both, k * (sc - sc[e]), torch.zeros_like(sc))


def readable(o):
    """the readout in the world's units for the counters: place [..., 3] (units, from him, turned to his facing), the
    spreads [..., 3] (units across, up and down, units a second), band, hand [...] (most likely), own [..., 6] (chance)"""
    o = o.float()
    return (o[..., SL["pos"]] * U, torch.exp(spreads(o)) * U, o[..., SL["band"]].argmax(-1), o[..., SL["hand"]].argmax(-1),
            torch.sigmoid(o[..., SL["own"]]))

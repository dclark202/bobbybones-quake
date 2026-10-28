"""(v0.6.1, WIN_JUDGE) the judge: his chance of winning a duel, learned from how his own games ended, with the owner's four
axioms built into its shape (owner, 2026-10-28: "frag good, death bad, deal damage good, take damage bad").

    P(seat a wins) = sigmoid( (d + mu) / s )
      d   = a's lead in frags
      mu  = h(a) - h(b)                                  the stack edge in frags (one h for both seats: fair by construction)
      s   = sqrt(0.02 + left x rate(t))                  the frags still to come; rate > 0 learned by the time
      h(p) = A(E) - B(E) + sum over RL, LG, RG of own x (-W_FLOOR + softplus(net_w(t)))
      A(E) = sum_k a_k(t) tanh(b_k x_hi),  x_hi = max(E - 125, 0) / 100,  a_k, b_k >= 0         rises with the stack above a respawn
      B(E) = LO_CAP g(t) sum_k pi_k tanh(c_k x_lo),  x_lo = (125 - min(E, 125)) / 125,  in [0, LO_CAP]   below a respawn
      E   = health + min(armor, 2 x health) (armor absorbs 2/3 of damage); a dead player = his respawn (125, no weapons)
      t   = left / 600; a(t), g(t), rate(t), the weapons' values: small networks of the time left only
The axioms, by construction:
  deal damage good, take damage bad: h rises with a player's own E (A rises, B falls; weapons do not depend on E);
  frag good, death bad: a kill sets the enemy to E 125 with no weapons, h = 0 there; before it h >= -(LO_CAP + 3 W_FLOOR) =
  -0.75, so mu falls by at most 0.75 while d rises by 1: d + mu gains at least 0.25 (s does not move on the frame).
Weapons are not constrained beyond the floor (a weapon can be worth little or a little less than nothing: the owner's
edge cases). Fitted by tools/run/fit_b.py (torch, the same function with xp = torch); used by duel_env's win pay as numpy.
"""
import numpy as np

SPAWN = 125.0
LO_CAP = 0.6
W_FLOOR = 0.05
K = 4
H = 8
GAME_LEN = 600.0
SHAPES = dict(a_w1=(1, H), a_b1=(H,), a_w2=(H, K), a_b2=(K,), bh=(K,),
              g_w1=(1, H), g_b1=(H,), g_w2=(H, 1), g_b2=(1,), pl=(K,), bl=(K,),
              w_w1=(1, H), w_b1=(H,), w_w2=(H, 3), w_b2=(3,),
              s_w1=(1, H), s_b1=(H,), s_w2=(H, 1), s_b2=(1,))


def init(seed=0):
    """a start near B2's fit (2026-10-28, last night's games): a stack above a respawn worth up to ~2 frags, below it up to
    ~0.5, the rocket launcher and the lightning gun a little, the spread ~0.1 frag^2 a second"""
    r = np.random.default_rng(seed)
    P = {k: (0.1 * r.standard_normal(s)).astype(np.float64) for k, s in SHAPES.items()}
    P["a_b2"][:] = -0.5                                      # softplus(-0.5) ~ 0.47 each, K = 4: up to ~1.9 frags
    P["bh"][:] = 0.5
    P["g_b2"][:] = 1.5                                       # g ~ 0.82
    P["bl"][:] = 1.0
    P["w_b2"][:] = -2.0                                      # ~0.08 a weapon
    P["s_b2"][:] = -2.2                                      # softplus ~ 0.105
    return P


def _sp(x, xp):
    """softplus, stable, for numpy or torch"""
    return xp.log1p(xp.exp(-abs(x))) + (x + abs(x)) * 0.5


def _sig(x, xp):
    return 1.0 / (1.0 + xp.exp(-x))


def _mlp(P, p, t, xp):
    return xp.tanh(t[..., None] @ P[p + "_w1"] + P[p + "_b1"]) @ P[p + "_w2"] + P[p + "_b2"]


def value(P, E, w, t, xp=np):
    """h: a player's worth in frags beside the score: E [n] effective stack (dead: 125), w [n, 3] owns RL, LG, RG (dead: 0),
    t [n] = left / 600"""
    xh = (E - SPAWN + abs(E - SPAWN)) * 0.5 / 100.0
    xl = (SPAWN - E + abs(SPAWN - E)) * 0.5 / SPAWN
    A = (_sp(_mlp(P, "a", t, xp), xp) * xp.tanh(xh[..., None] * _sp(P["bh"], xp))).sum(-1)
    e_ = xp.exp(P["pl"] - P["pl"].max())
    pi = e_ / e_.sum()
    Bv = LO_CAP * _sig(_mlp(P, "g", t, xp)[..., 0], xp) * (pi * xp.tanh(xl[..., None] * _sp(P["bl"], xp))).sum(-1)
    Wv = ((_sp(_mlp(P, "w", t, xp), xp) - W_FLOOR) * w).sum(-1)
    return A - Bv + Wv


def chance(P, d, left, Ea, wa, Eb, wb, xp=np):
    """P(seat a wins): d [n] a's lead, left [n] seconds to play (the period's in overtime), Ea / Eb [n], wa / wb [n, 3]"""
    t = left / GAME_LEN
    t = (t + abs(t)) * 0.5                                   # (t >= 0)
    mu = value(P, Ea, wa, t, xp) - value(P, Eb, wb, t, xp)
    s = xp.sqrt(0.02 + left * _sp(_mlp(P, "s", t, xp)[..., 0], xp))
    return _sig((d + mu) / s, xp)


def effective(hp, armor, dead):
    """E: health + min(armor, 2 x health); a dead player: the respawn's 125"""
    hp = np.asarray(hp, np.float64)
    ar = np.asarray(armor, np.float64)
    return np.where(dead, SPAWN, hp + np.minimum(ar, 2.0 * np.maximum(hp, 0.0)))


def save(path, P, meta):
    import json
    np.savez(path, meta=np.array(json.dumps(meta)), **{k: np.asarray(v, np.float64) for k, v in P.items()})


def load(path):
    """-> (params as float64 arrays, meta dict); checks the shapes"""
    import json
    z = np.load(path, allow_pickle=False)
    P = {k: np.array(z[k], np.float64) for k in SHAPES}
    for k, s in SHAPES.items():
        assert P[k].shape == s, "win judge {}: {} is {}, not {}".format(path, k, P[k].shape, s)
    return P, json.loads(str(z["meta"]))

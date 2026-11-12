"""(v0.6.1, WIN_JUDGE) the judge: his chance of winning a duel, learned from how his own games ended, with the owner's four
axioms built into its shape (owner, 2026-10-28: "frag good, death bad, deal damage good, take damage bad"; "taking into account
the decay for armor/health above 100 is the right design choice").

    P(seat a wins) = sigmoid( (d + mu) / s )
      d   = a's lead in frags
      mu  = h(a) - h(b)                                  the stack edge in frags (one h for both seats: fair by construction)
      s   = sqrt(0.02 + left x rate(t))                  the frags still to come; rate > 0 learned by the time
      a player's stack in two parts (the game's armor rule: armor absorbs 2/3 of damage, so it counts up to twice the health):
        L = min(hp, 100) + min(min(armor, 100), 2 x min(hp, 100))     the lasting part (what does not decay)
        D = hp + min(armor, 2 x hp) - L                                the decaying part (health and armor above 100)
        a dead player = his respawn: health 125, no armor, no weapons (L 100, D 25: the anchor)
      h(p) = [A_L(L) - B_L(L)] + [A_D(D) - B_D(D)] + sum over RL, LG, RG of own x (-W_FLOOR + softplus(net_w(t)))
        above the anchor (L > 100, D > 25): A = sum_k a_k(t) tanh(b_k x_hi), a_k, b_k >= 0          free, rising
        below it: B = cap x g(t) sum_k pi_k tanh(c_k x_lo) in [0, cap], rising as the part falls;  caps L 0.5, D 0.1
      t = left / 600; a(t), g(t), rate(t), the weapons' values: small networks of the time left only
The axioms, by construction:
  deal damage good, take damage bad: L and D never fall when health or armor rise, and h rises with each of them, so h rises
  with a player's health and armor (weapons do not depend on them);
  frag good, death bad: a kill sets the enemy to the anchor, where h = 0; before it h >= -(0.5 + 0.1 + 3 W_FLOOR) = -0.75, so mu
  falls by at most 0.75 while d rises by 1: d + mu gains at least 0.25 (s does not move on the frame).
Weapons are not constrained beyond the floor (a weapon can be worth little or a little less than nothing: the owner's edge
cases). Fitted by tools/run/fit_b.py (torch, the same function with xp = torch); used by duel_env's win pay as numpy.
"""
import numpy as np

SPAWN = 125.0                                                # (a respawn's health: the anchor is L 100, D 25)
L0, D0 = 100.0, 25.0
LO_CAP_L, LO_CAP_D = 0.5, 0.1
W_FLOOR = 0.05
K = 4
H = 8
GAME_LEN = 600.0
VERSION = 2                                                  # (2: the stack in a lasting and a decaying part)
SHAPES = dict(a_w1=(1, H), a_b1=(H,), a_w2=(H, K), a_b2=(K,), bh=(K,),
              e_w1=(1, H), e_b1=(H,), e_w2=(H, K), e_b2=(K,), eh=(K,),
              g_w1=(1, H), g_b1=(H,), g_w2=(H, 2), g_b2=(2,), pl=(K,), bl=(K,), ql=(K,), cl=(K,),
              w_w1=(1, H), w_b1=(H,), w_w2=(H, 3), w_b2=(3,),
              s_w1=(1, H), s_b1=(H,), s_w2=(H, 1), s_b2=(1,))


def init(seed=0):
    """a start near the first judge's fit (2026-10-28, last night's games): a stack above a respawn worth up to ~2 frags,
    the decaying part a little less a point, below a respawn up to the caps, the weapons a little, the spread ~0.1 frag^2 a
    second"""
    r = np.random.default_rng(seed)
    P = {k: (0.1 * r.standard_normal(s)).astype(np.float64) for k, s in SHAPES.items()}
    P["a_b2"][:] = -0.5                                      # lasting above 100: softplus(-0.5) ~ 0.47 each, K = 4
    P["bh"][:] = 0.5
    P["e_b2"][:] = -1.0                                      # decaying above 25
    P["eh"][:] = 0.5
    P["g_b2"][:] = 1.5                                       # the floors' gates ~ 0.82
    P["bl"][:] = 1.0
    P["cl"][:] = 1.0
    P["w_b2"][:] = -2.0                                      # ~0.08 a weapon
    P["s_b2"][:] = -2.2                                      # softplus ~ 0.105
    return P


def _sp(x, xp):
    """softplus, stable, for numpy or torch"""
    return xp.log1p(xp.exp(-abs(x))) + (x + abs(x)) * 0.5


def _sig(x, xp):
    return 1.0 / (1.0 + xp.exp(-x))


def _relu(x):
    return (x + abs(x)) * 0.5


def _mlp(P, p, t, xp):
    return xp.tanh(t[..., None] @ P[p + "_w1"] + P[p + "_b1"]) @ P[p + "_w2"] + P[p + "_b2"]


def _soft(v, xp):
    e_ = xp.exp(v - v.max())
    return e_ / e_.sum()


def value(P, S, w, t, xp=np):
    """h: a player's worth in frags beside the score: S [n, 2] (L, D: the lasting and the decaying part of his stack; dead: the
    anchor 100, 25), w [n, 3] owns RL, LG, RG (dead: 0), t [n] = left / 600"""
    L, D = S[..., 0], S[..., 1]
    g = _sig(_mlp(P, "g", t, xp), xp)                        # [n, 2]: the floors' gates by the time
    AL = (_sp(_mlp(P, "a", t, xp), xp) * xp.tanh((_relu(L - L0) / 100.0)[..., None] * _sp(P["bh"], xp))).sum(-1)
    BL = LO_CAP_L * g[..., 0] * (_soft(P["pl"], xp) * xp.tanh((_relu(L0 - L) / L0)[..., None] * _sp(P["bl"], xp))).sum(-1)
    AD = (_sp(_mlp(P, "e", t, xp), xp) * xp.tanh((_relu(D - D0) / 100.0)[..., None] * _sp(P["eh"], xp))).sum(-1)
    BD = LO_CAP_D * g[..., 1] * (_soft(P["ql"], xp) * xp.tanh((_relu(D0 - D) / D0)[..., None] * _sp(P["cl"], xp))).sum(-1)
    Wv = ((_sp(_mlp(P, "w", t, xp), xp) - W_FLOOR) * w).sum(-1)
    return AL - BL + AD - BD + Wv


def chance(P, d, left, Sa, wa, Sb, wb, xp=np):
    """P(seat a wins): d [n] a's lead, left [n] seconds to play (the period's in overtime), Sa / Sb [n, 2] (parts()), wa / wb [n, 3]"""
    t = _relu(left / GAME_LEN)
    mu = value(P, Sa, wa, t, xp) - value(P, Sb, wb, t, xp)
    s = xp.sqrt(0.02 + left * _sp(_mlp(P, "s", t, xp)[..., 0], xp))
    return _sig((d + mu) / s, xp)


def parts(hp, armor, dead):
    """[n, 2]: (L, D), the lasting and the decaying part of a stack (see the top); a dead player: the anchor (100, 25)"""
    hp = np.maximum(np.asarray(hp, np.float64), 0.0)
    ar = np.maximum(np.asarray(armor, np.float64), 0.0)
    h1 = np.minimum(hp, 100.0)
    L = h1 + np.minimum(np.minimum(ar, 100.0), 2.0 * h1)
    E = hp + np.minimum(ar, 2.0 * hp)
    dead = np.asarray(dead, bool)
    return np.stack([np.where(dead, L0, L), np.where(dead, D0, E - L)], -1)


def save(path, P, meta):
    import json
    np.savez(path, meta=np.array(json.dumps(dict(meta, version=VERSION))), **{k: np.asarray(v, np.float64) for k, v in P.items()})


def load(path):
    """-> (params as float64 arrays, meta dict); checks the version and the shapes"""
    import json
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    assert meta.get("version") == VERSION, "win judge {}: version {}, this code reads {}".format(path, meta.get("version"), VERSION)
    P = {k: np.array(z[k], np.float64) for k in SHAPES}
    for k, s in SHAPES.items():
        assert P[k].shape == s, "win judge {}: {} is {}, not {}".format(path, k, P[k].shape, s)
    return P, meta


# ---- (1.9a, JUDGE_ITEMS; the owner, 2026-11-12: "Judge with items. As long as the head understands the value of items, we're good";
# "the judge just pays the head") the judge with the next mega's and red armor's race in it, for the HEAD's pay only.
#   mu' = mu + sum over the two items of  K_item x w x [ p x (h_a(stack_a + item) - h_a(stack_a)) - (1 - p) x (h_b(stack_b + item) - h_b(stack_b)) ]
#     h            the judge's own value of a stack (value() above, at this time left): what the item is worth to each is the judge's
#     p            the chance seat a takes it first: sigmoid((T_b - T_a) / tau), T = max(his walking seconds to it, seconds until it is back)
#     w            how soon it counts: exp(-seconds until it is back / horizon), 0 if it is back only after the game's end
#     K_item >= 0, tau > 0, horizon > 0: fitted (tools/run/fit_items.py: tau on who really took it first, K and horizon on how games ended)
# Its axioms, by construction (K >= 0, h rising with the stack, p rising as a gets nearer): an item is never worth less than nothing to
# the one who takes it, and being nearer to an item can only raise a's chance; an item absent on the map adds 0.
ITEM_GAIN = (("MH", 100.0, 0.0, 200.0), ("RA", 0.0, 100.0, 200.0))     # (the item, health it adds, armor it adds, the cap; QL duel)
SPAWN_HP = 125.0


def items_default():
    return dict(version=1, tau=2.0, horizon=15.0, k=[1.0, 1.0], dead_walk=8.0, far=60.0)


def items_load(path):
    import json
    IP = json.load(open(path))
    assert int(IP.get("version", 0)) == 1, "the items' judge {}: version {}".format(path, IP.get("version"))
    assert IP.get("accepted", True) is not False, "the items' judge {}: its fit was NOT accepted (tools/run/fit_items.py)".format(path)
    assert float(IP["tau"]) > 0 and float(IP["horizon"]) > 0 and all(float(k) >= 0 for k in IP["k"]) and len(IP["k"]) == 2, \
        "the items' judge {}: tau and horizon above 0, two K of 0 or more".format(path)
    return IP


def _with_item(hp, ar, dead, j):
    """the stack after taking item j: a dead player takes it after his respawn (health 125, no armor)"""
    _, dh, da, cap = ITEM_GAIN[j]
    h0 = np.where(dead, SPAWN_HP, np.maximum(np.asarray(hp, np.float64), 0.0))
    a0 = np.where(dead, 0.0, np.maximum(np.asarray(ar, np.float64), 0.0))
    return parts(np.minimum(h0 + dh, cap) if dh > 0 else h0, np.minimum(a0 + da, cap) if da > 0 else a0, np.zeros_like(np.asarray(dead, bool)))


def items_term(P, IP, left, hpa, ara, deada, wa, hpb, arb, deadb, wb, ra, rb, xp=np, p_only=False):
    """the items' part of mu [n] for seat a against b. ra / rb: dict(present [n, 2], tsp [n, 2], walk [n, 2]) of each seat
    (the simulator's item_race(); tsp the same for both). p_only: (the chance a takes each item first [n, 2], w [n, 2])"""
    t = _relu(np.asarray(left, np.float64) / GAME_LEN)
    left = np.asarray(left, np.float64)
    tau, H, far = float(IP["tau"]), float(IP["horizon"]), float(IP.get("far", 60.0))
    Sa, Sb = parts(hpa, ara, deada), parts(hpb, arb, deadb)
    ha, hb = value(P, Sa, wa, t, xp), value(P, Sb, wb, t, xp)
    tsp = np.asarray(ra["tsp"], np.float64)
    Ta = np.maximum(np.minimum(np.asarray(ra["walk"], np.float64), far), tsp)
    Tb = np.maximum(np.minimum(np.asarray(rb["walk"], np.float64), far), tsp)
    p = 1.0 / (1.0 + np.exp(-np.clip((Tb - Ta) / tau, -40.0, 40.0)))
    wa_, wb_ = np.asarray(ra["walk"], np.float64), np.asarray(rb["walk"], np.float64)
    reach = (wa_ < far) | (wb_ < far)                        # (an item neither can reach on the route field, e.g. a jump's: as absent)
    w = np.asarray(ra["present"], bool) * reach * np.exp(-tsp / H) * (tsp < left[:, None])
    if p_only:
        return p, w
    out = np.zeros(len(left))
    for j in range(len(ITEM_GAIN)):
        ga = value(P, _with_item(hpa, ara, deada, j), wa * (~np.asarray(deada, bool))[:, None], t, xp) - ha
        gb = value(P, _with_item(hpb, arb, deadb, j), wb * (~np.asarray(deadb, bool))[:, None], t, xp) - hb
        out = out + float(IP["k"][j]) * w[:, j] * (p[:, j] * np.maximum(ga, 0.0) - (1.0 - p[:, j]) * np.maximum(gb, 0.0))
    return out


def chance_items(P, IP, d, left, hpa, ara, deada, wa, hpb, arb, deadb, wb, ra, rb):
    """P(seat a wins) with the items' race in mu (see above); with every K at 0 it is chance() to the bit"""
    left = np.asarray(left, np.float64)
    Sa, Sb = parts(hpa, ara, deada), parts(hpb, arb, deadb)
    t = _relu(left / GAME_LEN)
    mu = value(P, Sa, wa, t) - value(P, Sb, wb, t) + items_term(P, IP, left, hpa, ara, deada, wa, hpb, arb, deadb, wb, ra, rb)
    s = np.sqrt(0.02 + left * _sp(_mlp(P, "s", t, np)[..., 0], np))
    return _sig((np.asarray(d, np.float64) + mu) / s, np)

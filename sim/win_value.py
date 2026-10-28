"""v0.4.3: the shadow win value (the trainer's --win-value; owner's go, 2026-10-24). A shadow only: it never feeds the pay,
the advantages, the policy's inputs or his play; nothing of it reaches the policy, the brain or the main value.

What it learns: the value of WIN_PAY's pay as WIN_SHADOW records it (info["win_shadow"]: WIN_SCALE x the change in the win
table's chance of the frame; with the overtime fix of 2026-10-24, a game decided in overtime pays its outcome on its last
frame). Over a game those pays telescope to WIN_SCALE x (the result - the chance at its start), so its value at a moment is
WIN_SCALE x (his expected result - the table's chance now): what he knows beyond the table (the lead and the clock).

Discount: gamma 1 with the game's end as the cut (the default; --win-value-gamma). The pay is a difference of one bounded
function and a game always ends (ten minutes and at most ten periods of two), so the undiscounted sum is finite and is
exactly the quantity wanted (result minus the table's chance, in frag units); a discount below 1 would shrink a late lead's
worth toward 0 and blur the "beyond the table" reading. A cut is any change of the seat's game (it ends, or a game begins
where none was, or the match's game clock jumps: a new game in the same step): nothing is carried over a cut. Deaths are no
cut (a game spans many lives).

What it reads: the brain's state (sim/belief.py, 256) and the hands' fast memory (512) at the brain's ticks, every
`every` ticks (2: 0.4 s), as the "in control" readout "both" does; for a league seat its own network's hands' memory. Stored
detached at half precision on the host; one Linear-ReLU-Linear (768 -> hid -> 1), its last layer at zero (a guess of 0), from
a random stream of its own; its own Adam (cold at every process start), its own generator for the minibatch order: the
trainer's random streams, and so his play, are untouched.

How it learns (one rollout late): the states kept in rollout u - 1 get TD(lambda) returns from the pay that came after each
up to the next kept state (rollout u's first closes the last segment) and its own values (no_grad) of the next states,
bootstrapped at rollout u's first kept state; masked to the states in a game. Mean squared error, one pass.

Counters (metrics.jsonl "win_value"): td: the lesson's frames, its loss and the explained variance of the values against
their TD(lambda) targets before the step; cal: at each game's end, every `cal_every`-th kept state of each seat's game (as
played: the value of the copy that played the rollout) against its realised return (the shadow pay from that state to the
game's end): explained variance, the slope of the return on the value (1: calibrated), the correlation; beyond: the two
seats' value difference against the realised return (= WIN_SCALE x (the result - the table's chance at that moment)):
its correlation (what the value adds to the table, as tools/value_ready.py's section (a)).

The checkpoint carries it as a top-level entry "win_value" (layout and weights), never in "model": the export, the checks'
tools, test_suite.Policy and the league's and anchors' loading read "model" and do not see it.
"""
import math

import numpy as np
import torch

VERSION = 1
SEED = 4047


def layout(bel=256, mem=512, hid=128, every=2, tick=8, gamma=1.0, lam=0.95, cal_every=5, cal_cap=600):
    return dict(version=VERSION, bel=int(bel), mem=int(mem), width=int(bel) + int(mem), hid=int(hid), every=int(every),
                tick=int(tick), gamma=float(gamma), lam=float(lam), cal_every=int(cal_every), cal_cap=int(cal_cap))


def make_module(L):
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(SEED)
        m = nn.Sequential(nn.Linear(int(L["width"]), int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), 1))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
    return m


def kept(L, t):
    """frame t of a rollout (T a whole number of ticks) is a tick the value keeps"""
    K = int(L["tick"])
    return t % K == K - 1 and (t // K) % int(L["every"]) == 0


def n_kept(L, T):
    return sum(1 for t in range(T) if kept(L, t))


class Stream:
    """per seat, carried from rollout to rollout: the open segment's pay (acc, from the last kept state on), whether a cut
    came in it (endf), the discount reached (disc), in a game now (ing), the game's shadow pay so far (cum), and the
    calibration's history of this game (value as played, cum at that moment, the two seats' value difference)"""

    def __init__(self, L, n, dev, group=2):
        self.L, self.n, self.dev, self.group = L, int(n), dev, int(group)
        self.acc = torch.zeros(n, device=dev, dtype=torch.float64)
        self.endf = torch.zeros(n, device=dev, dtype=torch.float64)
        self.disc = torch.ones(n, device=dev, dtype=torch.float64)
        self.ing = torch.zeros(n, device=dev, dtype=torch.bool)
        self.cum = torch.zeros(n, device=dev, dtype=torch.float64)
        S = int(L["cal_cap"])
        self.hp = torch.zeros(S, n, device=dev)
        self.hc = torch.zeros(S, n, device=dev, dtype=torch.float64)
        self.hv = torch.zeros(S, n, device=dev)
        self.cnt = torch.zeros(n, device=dev, dtype=torch.long)
        self.nk = 0                                            # kept states so far (the calibration's every cal_every-th)
        self.new_roll()

    def new_roll(self):
        self.X, self.close, self.ingk = [], [], []
        self.cal = torch.zeros(10, dtype=torch.float64, device=self.dev)   # n, sy, syy, sp, spp, spy, svd, svdvd, svdy, seats ended

    def keep(self, X, pred):
        """a kept tick: X [n, width] (any precision; detached here), pred [n] the value as played"""
        self.close.append(torch.stack([self.acc, self.endf, self.disc], 1).float().cpu())
        self.acc.zero_()
        self.endf.zero_()
        self.disc.fill_(1.0)
        self.X.append(X.detach().to("cpu", torch.float16))
        self.ingk.append(self.ing.cpu().clone())
        if self.nk % int(self.L["cal_every"]) == 0:
            p_ = pred.detach().float().to(self.dev)
            ok_ = self.ing & (self.cnt < self.hp.shape[0])
            i_ = torch.nonzero(ok_).squeeze(1)
            if len(i_):
                pr_ = p_.view(-1, self.group)
                vd_ = (pr_[:, :1] - pr_[:, 1:2]).repeat(1, self.group) if self.group == 2 else torch.zeros_like(pr_)
                if self.group == 2:
                    vd_[:, 1] = -vd_[:, 1]
                vd_ = vd_.reshape(-1)
                c_ = self.cnt[i_]
                self.hp[c_, i_] = p_[i_]
                self.hc[c_, i_] = self.cum[i_]
                self.hv[c_, i_] = vd_[i_]
                self.cnt[i_] += 1
        self.nk += 1

    def frame(self, ws, cut, ing_after):
        """after a frame's step: ws [n] the shadow pay, cut [n] (0/1), ing_after [n] in a game after it"""
        ws = ws.to(self.dev, torch.float64)
        cut = cut.to(self.dev, torch.float64)
        self.acc += self.disc * ws * (1.0 - self.endf)
        self.cum += ws
        self.endf = torch.maximum(self.endf, cut)
        self.disc *= float(self.L["gamma"])
        ce_ = (cut > 0) & (self.cnt > 0)
        if bool(ce_.any()):                                   # a game over for these seats: their states against what came
            i_ = torch.nonzero(ce_).squeeze(1)
            S = self.hp.shape[0]
            m_ = torch.arange(S, device=self.dev)[:, None] < self.cnt[i_][None, :]
            y_ = (self.cum[i_][None, :] - self.hc[:, i_])[m_]
            p_ = self.hp[:, i_][m_].double()
            v_ = self.hv[:, i_][m_].double()
            self.cal += torch.stack([y_.new_tensor(float(len(y_))), y_.sum(), (y_ * y_).sum(), p_.sum(), (p_ * p_).sum(), (p_ * y_).sum(),
                                     v_.sum(), (v_ * v_).sum(), (v_ * y_).sum(), y_.new_tensor(float(len(i_)))])
        cc_ = cut > 0
        self.cum[cc_] = 0.0
        self.cnt[cc_] = 0
        self.ing = ing_after.to(self.dev, torch.bool)

    def take(self):
        """the rollout's kept states, segments and counters (and a fresh rollout)"""
        out = dict(X=torch.stack(self.X) if self.X else None, close=torch.stack(self.close) if self.close else None,
                   ing=torch.stack(self.ingk) if self.ingk else None, cal=self.cal.cpu())
        self.new_roll()
        return out

    def state(self):
        return {k: getattr(self, k).clone() for k in ("acc", "endf", "disc", "ing", "cum", "hp", "hc", "hv", "cnt")}


def _vals(mod, X, dev, mb=16384):
    out = torch.empty(X.shape[:-1])
    Xf = X.reshape(-1, X.shape[-1])
    o_ = out.view(-1)
    with torch.no_grad():
        for b in range(0, len(Xf), mb):
            o_[b:b + mb] = mod(Xf[b:b + mb].to(dev).float()).squeeze(-1).float().cpu()
    return out


def learn(mod, opt, L, prev, cur, lr, dev, gen, mb=8192):
    """prev, cur: two rollouts' take(); the states of prev learnt with TD(lambda) returns (cur's first state closes and
    bootstraps the last segment) -> counters dict(n, loss, ev, vmean, vsd)"""
    if prev is None or prev["X"] is None or cur is None or cur["X"] is None:
        return {}
    X = prev["X"]                                             # [J, n, width] half
    J = X.shape[0]
    seg = torch.cat([prev["close"][1:], cur["close"][:1]], 0).double()     # [J, n, 3]: the segment after each state
    V = _vals(mod, X, dev).double()                           # [J, n]
    Vb = _vals(mod, cur["X"][:1], dev).double()[0]
    lam = float(L["lam"])
    G = torch.zeros(J, X.shape[1], dtype=torch.float64)
    nxt_v, nxt_g = Vb, Vb
    for j in range(J - 1, -1, -1):
        r_, e_, d_ = seg[j, :, 0], seg[j, :, 1], seg[j, :, 2]
        G[j] = r_ + d_ * (1.0 - e_) * ((1.0 - lam) * nxt_v + lam * nxt_g)
        nxt_v, nxt_g = V[j], G[j]
    M = prev["ing"]                                           # [J, n] in a game at the state
    if not bool(M.any()):
        return dict(n=0)
    Xs, Gs, Vs = X[M], G[M].float(), V[M]
    y_, v_ = Gs.double(), Vs
    out = dict(n=int(len(Gs)), ev=float(1.0 - (y_ - v_).var() / y_.var().clamp(min=1e-12)) if len(Gs) > 1 else float("nan"),
               vmean=float(v_.mean()), vsd=float(v_.std()) if len(v_) > 1 else 0.0, gmean=float(y_.mean()), gsd=float(y_.std()) if len(y_) > 1 else 0.0)
    if lr <= 0:
        out["loss"] = float(((y_ - v_) ** 2).mean())
        return out
    for g_ in opt.param_groups:
        g_["lr"] = float(lr)
    B = len(Gs)
    pm = torch.randperm(B, generator=gen)
    ls_, nb_ = 0.0, 0
    for b in range(0, B, mb):
        i_ = pm[b:b + mb]
        xb, yb = Xs[i_].to(dev).float(), Gs[i_].to(dev)
        l_ = ((mod(xb).squeeze(-1) - yb) ** 2).mean()
        opt.zero_grad(set_to_none=True)
        l_.backward()
        torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
        opt.step()
        ls_ += float(l_.detach()) * len(i_)
        nb_ += len(i_)
    out["loss"] = ls_ / max(1, nb_)
    return out


def _r(x, k=4):
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, k)


def record(td, cal, w, L, gb=None):
    """the update's counters -> metrics.jsonl's "win_value" """
    rec = dict(w=round(float(w), 4), gamma=L["gamma"], lam=L["lam"])
    if gb is not None:
        rec["host_gb"] = round(float(gb), 3)
    if td:
        rec["td"] = {k: (_r(v) if isinstance(v, float) else v) for k, v in td.items()}
    c = [float(x) for x in cal] if cal is not None else [0.0] * 10
    n = c[0]
    rec["cal"] = dict(n=int(n), seats_ended=int(c[9]))
    if n >= 10:
        my, mp, mv = c[1] / n, c[3] / n, c[6] / n
        vy, vp, vv = c[2] / n - my * my, c[4] / n - mp * mp, c[7] / n - mv * mv
        cpy, cvy = c[5] / n - mp * my, c[8] / n - mv * my
        ve = vy - 2 * cpy + vp                                # var(y - p)
        rec["cal"].update(ev=_r(1.0 - ve / vy) if vy > 0 else None, slope=_r(cpy / vp) if vp > 0 else None,
                          corr=_r(cpy / math.sqrt(vp * vy)) if vp > 0 and vy > 0 else None, ymean=_r(my), vmean=_r(mp))
        rec["beyond"] = dict(corr_vd=_r(cvy / math.sqrt(vv * vy)) if vv > 0 and vy > 0 else None)
    return rec

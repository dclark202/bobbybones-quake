"""v0.4.3 (B-280; docs/v0.4.3/RUN_v0.4.3.md, "In control"): the brain's readout "in control", the trainer's --control.

"In control" is his share of the next two spawns of the mega and the red armor (who takes them), known only in hindsight:
the simulator's CONTROL_TRUTH=1 gives it CONTROL_H seconds late (info["aux"]'s ctl_lab: the label of the row CONTROL_D
rows before; ctl_one: the next spawn alone). A lesson only: no pay, nothing reads it yet (the head will, v0.4.3).

The readout reads the brain's state (the belief, 256 numbers at its ticks) as the brain had it while he played: the
rollout keeps that state (detached, half precision, on the host) every --control-every ticks in a ring as long as the
horizon, and when a label arrives the readout learns from the state of its frame. Its gradient reaches the readout's own
layers only (the state is a stored number, not the brain's output in this update): whether the information is in the brain
already is what tools/control_probe.py measured; the brain learning for it would need its inputs re-run over 90 s.

Module: Linear(256 -> hid) + ReLU + Linear(hid -> 4) (the logits: the next two spawns, the next one, the next mega, the next red armor), its last layer at
zero (a guess of 0.5), from a random stream of its own. Its own Adam (tiny; not in the run's optimizer groups, so an opt.pt
of the run loads as before; its state starts cold at every process start). The lesson's weight scales its rate (Adam does
not feel a loss's scale): --control-lr x the weight x the warm-up (live CONTROL_W: a factor, 0 stops it).

Each label is scored before the readout learns from it: the counters (Brier against the constant guess, the share of
labelled frames) are an honest test on unseen frames.
"""
import math

import torch

COLS = ("ctl_lab", "ctl_one", "ctl_mh", "ctl_ra", "ctl_age")
OUTS = ("two", "one", "mh", "ra")      # (the head of v0.4.3 reads the four: sim/head2.py's "in control" slot)


def layout(inp=256, hid=64, every=5, horizon_frames=3600, tick=8):
    return dict(version=1, inp=int(inp), hid=int(hid), d=len(OUTS), every=int(every), horizon=int(horizon_frames), tick=int(tick),
                src="belief", outs=list(OUTS))


def make_module(L, seed=4044):
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        m = nn.Sequential(nn.Linear(int(L["inp"]), int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), int(L["d"])))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
    return m


class Ring:
    """the brain's states at the kept ticks, by the trainer's global row (rollout after rollout, the simulators in lockstep):
    a row g is kept when it is a tick (g % tick == tick - 1) and (g // tick) % every == 0"""

    def __init__(self, L, n):
        self.L, self.n = L, int(n)
        self.step = int(L["tick"]) * int(L["every"])
        self.S = int(L["horizon"]) // self.step + 4          # (the horizon and a rollout's worth more)
        self.buf = torch.zeros(self.S, self.n, int(L["inp"]), dtype=torch.float16)
        self.g = torch.full((self.S,), -1, dtype=torch.long)

    def kept(self, g):
        K = int(self.L["tick"])
        return g % K == K - 1 and (g // K) % int(self.L["every"]) == 0

    def push(self, g, s):
        """at row g (a tick of the belief) its state s [n, inp] (any device)"""
        if not self.kept(g):
            return
        k = (g // self.step) % self.S
        self.buf[k] = s.detach().to("cpu", torch.float16)
        self.g[k] = int(g)

    def get(self, g):
        """the state of row g ([n, inp] float16, host) or None if not kept (or written over)"""
        if g < 0 or not self.kept(g):
            return None
        k = (g // self.step) % self.S
        return self.buf[k] if int(self.g[k]) == int(g) else None


def batch(ring, g0, aux, ix, D):
    """this rollout's labels: aux [T + 1, n, C] (b_aux, rows g0 .. g0 + T), ix: column -> index; -> (states [B, inp],
    labels [B, 2], mask [B, 2]) on the host, the rows whose frame D rows back has a kept state (B = kept rows x n)"""
    T = aux.shape[0] - 1
    xs, ys = [], []
    for t in range(T):
        s_ = ring.get(int(g0) + t - int(D))
        if s_ is None:
            continue
        xs.append(s_)
        ys.append(torch.stack([aux[t, :, ix[c_]] for c_ in ("ctl_lab", "ctl_one", "ctl_mh", "ctl_ra")], -1).float())
    if not xs:
        return None
    X = torch.cat(xs, 0)
    Y = torch.cat(ys, 0)
    M = (Y >= 0).float()
    keep = M.sum(1) > 0                                       # (a row with no label is left out)
    return X[keep], Y[keep].clamp(min=0.0), M[keep]


def learn(mod, opt, X, Y, M, lr, dev, mb=8192, epochs=1):
    """score (before learning) and one pass of the lesson -> counters (sums: the readout's squared error and the constant
    guess's per output, frames per output, BCE sum)"""
    d = int(mod[2].out_features)
    out = torch.zeros(3 * d + 1, dtype=torch.float64)
    if X is None or not len(X):
        return out
    for g_ in opt.param_groups:
        g_["lr"] = float(lr)
    Xd, Yd, Md = X.to(dev).float(), Y.to(dev), M.to(dev)
    with torch.no_grad():
        p_ = torch.sigmoid(mod(Xd))
        out[0:d] = (((p_ - Yd) ** 2) * Md).sum(0).double().cpu()
        out[d:2 * d] = (((0.5 - Yd) ** 2) * Md).sum(0).double().cpu()
        out[2 * d:3 * d] = Md.sum(0).double().cpu()
        out[3 * d] = float((torch.nn.functional.binary_cross_entropy(p_.clamp(1e-6, 1 - 1e-6), Yd, reduction="none") * Md).sum())
    if lr <= 0:
        return out
    for _ in range(int(epochs)):
        pm = torch.randperm(len(Xd), device=Xd.device)
        for b in range(0, len(pm), mb):
            i_ = pm[b:b + mb]
            l_ = (torch.nn.functional.binary_cross_entropy_with_logits(mod(Xd[i_]), Yd[i_], reduction="none") * Md[i_]).sum() / \
                Md[i_].sum().clamp(min=1.0)
            opt.zero_grad(set_to_none=True)
            l_.backward()
            torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
            opt.step()
    return out


def record(acc, w):
    """the update's counters -> metrics.jsonl's "control" (skill: 1 - Brier / the 0.5 guess's; the bar to beat is the label's
    own spread)"""
    d = (len(acc) - 1) // 3
    nf = [float(acc[2 * d + i]) for i in range(d)]
    return dict(w=round(float(w), 4), outs=list(OUTS[:d]), frames=[int(x) for x in nf],
                brier=[round(float(acc[i]) / max(1.0, nf[i]), 4) for i in range(d)],
                brier_half=[round(float(acc[d + i]) / max(1.0, nf[i]), 4) for i in range(d)],
                bce=round(float(acc[3 * d]) / max(1.0, sum(nf)), 4))

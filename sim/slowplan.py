"""2.1c (docs/runs/2.1/2.1c/CARD.md; owner 2026-11-15): the slow plan, in SHADOW. "Where his own target choice is heading": from the
strategy head's state at a keep reading, for each horizon h (in head ticks: 10 = 2 s, 25 = 5 s), his own target probabilities averaged
over the next h keep readings.

It learns silently: NOTHING reads it. No action, no log-probability, no gradient of the network changes with it. Its lesson is a
soft-label cross-entropy on his own fast odds of the readings that followed (never a pro's choice, never a rule's: CLAUDE.md rules 12,
13). It prepares a later step (pulling his fast choice toward the plan) that is not built.

Its input: the head's state at the reading (detached). Its output: per horizon, logits over the n_target targets. Refreshed every
`every` head ticks (1 s) and whenever his held numbers are drawn anew; held between (the trainer).

Its own module, its own Adam and its own random stream (the minibatches' order); a top-level entry "plan" of the checkpoint (as the
stay value's), never in "model"; the league files do not carry it.

(2.1d, the pull: docs/runs/2.1/2.1d) The same module moves INSIDE the strategy head (sim/head2.py add_slowplan: the layers head2.plan.*, the
buffers pull_g, pull_h; tools/plan_init.py add), so every reader of a network file plays it: his target scores as played get pull_g x
log(max(the plan's odds, floor)). Its lesson is still this file's (labels from his fast odds BEFORE the pull, never the pulled choice), on
the learner's copy with its own Adam (the checkpoint's top-level "plan_opt"); the main optimizer never steps it.
"""
import math

VERSION = 1
SEED = 5151


def layout(head=256, n_target=17, hid=128, horizons=(10, 25), every=5):
    hz = tuple(int(h_) for h_ in horizons)
    assert len(hz) >= 1 and all(h_ >= 1 for h_ in hz), "slowplan: horizons of at least one head tick"
    return dict(version=VERSION, head=int(head), n_target=int(n_target), hid=int(hid), horizons=list(hz), every=int(every),
                out=len(hz) * int(n_target))


def make_module(L):
    """two hidden layers, the last at zero (even odds at the start), from a random stream of its own (the global one untouched)"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "slowplan: layout version {} expected".format(VERSION)

    class Plan(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED)
                self.l1 = nn.Linear(int(L["head"]), int(L["hid"]))
                self.l2 = nn.Linear(int(L["hid"]), int(L["hid"]))
                self.l3 = nn.Linear(int(L["hid"]), int(L["out"]))
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()
            self.nh = len(L["horizons"])
            self.ni = int(L["n_target"])

        def forward(self, s):
            """s [B, head] -> logits [B, n_horizons, n_target]"""
            h = torch.relu(self.l1(s.float()))
            h = torch.relu(self.l2(h))
            return self.l3(h).view(-1, self.nh, self.ni)
    return Plan()


def odds(M, s):
    """the plan's odds [B, n_horizons, n_target] (no gradient)"""
    import torch
    with torch.no_grad():
        return torch.softmax(M(s.detach().float()), -1)


def generator(seed=SEED + 1):
    import torch
    return torch.Generator().manual_seed(int(seed))


def labels(pf, done, mrow, horizons, bk):
    """the labels of one rollout. pf [J, N, NI] his fast odds at each keep reading; done [T, N] the round ends (b_done); mrow [J, N]
    the rows (his seats, the readings where the plan was refreshed). -> per horizon (rows' index j [R], seat i [R], label [R, NI]),
    a row valid only if j + h is inside the rollout and no round ended on frames j*bk .. (j+h)*bk"""
    import torch
    J, N, NI = pf.shape
    cs = torch.cat([torch.zeros(1, N, device=done.device), torch.cumsum((done > 0).float(), 0)], 0)   # cs[t] = ends on frames < t
    cp = torch.cat([torch.zeros(1, N, NI, device=pf.device), torch.cumsum(pf.float(), 0)], 0)          # cp[j] = sum of readings < j
    out = []
    for h in horizons:
        h = int(h)
        if J - h <= 0:
            out.append((torch.zeros(0, dtype=torch.long), torch.zeros(0, dtype=torch.long), torch.zeros(0, NI)))
            continue
        jj = torch.arange(J - h, device=pf.device)
        f0, f1 = jj * bk, (jj + h) * bk                                  # frames j*bk .. (j+h)*bk, both in
        clean = (cs[f1 + 1] - cs[f0]) == 0                               # [J-h, N]
        ok = clean & mrow[:J - h].bool()
        lab = (cp[jj + h + 1] - cp[jj + 1]) / float(h)                   # readings j+1 .. j+h
        j_, i_ = torch.nonzero(ok, as_tuple=True)
        out.append((jj[j_], i_, lab[j_, i_]))
    return out


def readouts(M, S, P, Y, h_i):
    """measured BEFORE the lesson (held out): S [R, head] the states, P [R, NI] his fast odds at the reading, Y [R, NI] the labels; h_i
    the horizon's index. -> dict n, ce_plan, ce_now, ent, kl_plan, kl_now, top1_plan, top1_now"""
    import torch
    R = int(len(Y))
    if R == 0:
        return dict(n=0)
    with torch.no_grad():
        lq = torch.log_softmax(M(S.float()), -1)[:, h_i]
        Y = Y.float()
        ce_p = float(-(Y * lq).sum(-1).mean())
        ce_n = float(-(Y * torch.log(P.float().clamp(min=1e-6))).sum(-1).mean())
        ent = float(-(Y * torch.log(Y.clamp(min=1e-12))).sum(-1).mean())
        yt = Y.argmax(-1)
        t1p = float((lq.argmax(-1) == yt).float().mean())
        t1n = float((P.argmax(-1) == yt).float().mean())
    fin = lambda v: round(v, 5) if math.isfinite(v) else None
    return dict(n=R, ce_plan=fin(ce_p), ce_now=fin(ce_n), ent=fin(ent), kl_plan=fin(ce_p - ent), kl_now=fin(ce_n - ent),
                top1_plan=round(t1p, 4), top1_now=round(t1n, 4))


def learn(M, opt, S, Y, H, epochs=2, mb=1024, gen=None, clip=1.0, decay=0.0):
    """one rollout's lesson: S [R, head] the states (detached), Y [R, NI] the labels, H [R] the horizon's index of each row; the
    soft-label cross-entropy against a row's own horizon, each horizon's mean in a minibatch, summed over the horizons. -> the last loss.
    (2.1d, CLAUDE.md rule 11) decay: decoupled weight decay on the last layer's weights after each step, lr x decay (the pull adds the plan's
    log-odds to the head's target scores: a sum of two learned outputs; 0: none, as 2.1c)"""
    import torch
    R = int(len(Y))
    if R == 0:
        return None
    S, Y, H = S.detach().float(), Y.detach().float(), H.long()
    loss_ = None
    with torch.enable_grad():
        for _ in range(int(epochs)):
            perm = torch.randperm(R, generator=gen) if gen is not None else torch.randperm(R)
            for i in range(0, R, int(mb)):
                j = perm[i:i + int(mb)].to(S.device)
                lq = torch.log_softmax(M(S[j]), -1)                      # [b, nh, NI]
                lqh = lq.gather(1, H[j][:, None, None].expand(-1, 1, lq.shape[-1])).squeeze(1)
                ce = -(Y[j] * lqh).sum(-1)
                l_ = sum(ce[H[j] == k_].mean() for k_ in torch.unique(H[j]).tolist())     # summed over the horizons (each its mean)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(M.parameters(), float(clip))
                opt.step()
                if decay > 0:                                    # (2.1d) the decay of the sum's plan part, after its own step
                    with torch.no_grad():
                        M.l3.weight.mul_(1.0 - float(opt.param_groups[0]["lr"]) * float(decay))
                loss_ = float(l_)
    return loss_


def loss_of(M, S, Y, H):
    """the loss after the lesson (no gradient): each horizon's mean cross-entropy, summed"""
    import torch
    if len(Y) == 0:
        return None
    with torch.no_grad():
        lq = torch.log_softmax(M(S.float()), -1)
        lqh = lq.gather(1, H.long()[:, None, None].expand(-1, 1, lq.shape[-1])).squeeze(1)
        ce = -(Y.float() * lqh).sum(-1)
        return float(sum(ce[H == k_].mean() for k_ in torch.unique(H).tolist()))

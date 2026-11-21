"""2.1 (docs/runs/2.1/README.md, build 4; owner 2026-11-14): the stay value. "Keeping my target beats a new draw by this much", in the
strategy head's own value units (the head's pay and its value: sim/head2.py).

Its lesson: the frozen moments KEEP AGAINST A NEW DRAW (sim/branch.py keep_plan): a moment of a self-play match copied into two other
matches; in one his held target is forced (he keeps it), in the other a target drawn from his own scores of that moment (what a
re-decision gives; it may be the same one); both then play on as he plays. The label of a moment is the change of his standing in
the keep branch less the redraw branch's, each sum_{k<W} gamma^k pay[k] + gamma^W V_head[W] - V_head[0] (sim/branch.py outcomes;
V_head[0] is the same for both and cancels): W = 8 s in contact and at an arrival, 30 s in quiet (a trip to the mega is 10 to 15 s).
Never a pro's choice, never a rule's (CLAUDE.md rules 12, 13): only what the two branches brought.

It reads the situation (the brain's state, the hands' memory, the head's state: the three the head's value and the appraisals read)
and the keep choice's own numbers (sim/head2.py keep_x: the age, contact, the held target's log p, arrived, since the arrival, a sound,
a hit unseen) and the target's change signals (KSIG). Its output is the label in units of `scale` (a buffer: the mean size of the labels
it was taught, kept as a running mean), so value() is in the head's units.

Its own module and Adam, a top-level entry "stay" of the checkpoint (as the appraisals'): the export reads it for the servers (the quiet
layer's input), the league files do not carry it (a league network plays quiet with the lock rule).
"""
import numpy as np

VERSION = 1
SEED = 4071


def layout(bel=256, mem=512, head=256, kx=7, ksig=5, hid=128):
    sit = int(bel) + int(mem) + int(head)
    return dict(version=VERSION, bel=int(bel), mem=int(mem), head=int(head), kx=int(kx), ksig=int(ksig), sit=sit,
                inp=sit + int(kx) + int(ksig), hid=int(hid))


def make_module(L):
    """two layers, the last at zero (no preference at the start), from a random stream of its own; the buffer scale (1)"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "stay: layout version {} expected".format(VERSION)

    class Stay(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED)
                self.l1 = nn.Linear(int(L["inp"]), int(L["hid"]))
                self.l2 = nn.Linear(int(L["hid"]), int(L["hid"]))
                self.l3 = nn.Linear(int(L["hid"]), 1)
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()
            self.register_buffer("scale", torch.ones(()))
            self.register_buffer("seen", torch.zeros(()))

        def forward(self, x):
            h = torch.relu(self.l1(x.float()))
            h = torch.relu(self.l2(h))
            return self.l3(h).squeeze(-1)
    return Stay()


def x_of(bel, mem, s, kx, ksig):
    """the input [B, inp] from the brain's state [B, bel], the hands' memory [B, mem], the head's state [B, head], keep_x [B, kx], the
    change signals [B, ksig] (torch; detached)"""
    import torch
    return torch.cat([bel.float(), mem.float(), s.float(), kx.float(), ksig.float()], -1).detach()


def value(M, x):
    """the stay value [B] in the head's units (no gradient)"""
    import torch
    with torch.no_grad():
        return M(x) * M.scale


def learn(M, opt, x, y, w=None, epochs=2, mb=512, gen=None, rate=1.0, decay=0.995):
    """one update's lesson: x [R, inp], y [R] the labels (keep less redraw, head units), w [R] the rows' weights (None: 1). The scale
    follows the labels' mean size (a running mean); the regression is a smooth L1 on y / scale. -> dict of the readouts measured
    BEFORE the lesson (held out: these rows were never taught): n, the sign right (rows with |y| over a tenth of the scale), the
    correlation, the mean label, the loss"""
    import torch
    R = int(len(y))
    if R == 0:
        return dict(n=0)
    y = y.float()
    w = torch.ones_like(y) if w is None else w.float()
    with torch.no_grad():
        p0 = M(x) * M.scale
        big = (y.abs() > 0.1 * M.scale)
        sgn = float(((torch.sign(p0) == torch.sign(y)) & big).float().sum() / big.float().sum().clamp(min=1.0))
        yc, pc = y - y.mean(), p0 - p0.mean()
        cor = float((yc * pc).sum() / (yc.norm() * pc.norm()).clamp(min=1e-9))
        sc_old = float(M.scale)
        first = float(M.seen) == 0.0
        m_ = float(y.abs().mean())
        if m_ > 0:
            M.scale.fill_(m_ if first else decay * sc_old + (1.0 - decay) * m_)
        M.seen.add_(float(R))
    loss_ = 0.0
    if rate > 0:
        for _ in range(int(epochs)):
            perm = torch.randperm(R, generator=gen) if gen is not None else torch.randperm(R)
            for i in range(0, R, int(mb)):
                j = perm[i:i + int(mb)].to(x.device)
                p = M(x[j])
                l_ = (torch.nn.functional.smooth_l1_loss(p, y[j] / M.scale, reduction="none") * w[j]).sum() / w[j].sum().clamp(min=1e-6)
                opt.zero_grad(set_to_none=True)
                (rate * l_).backward()
                torch.nn.utils.clip_grad_norm_(M.parameters(), 1.0)
                opt.step()
                loss_ = float(l_)
    return dict(n=R, n_sign=int(big.sum()), sign=round(sgn, 4), cor=round(cor, 4), mean=round(float(y.mean()), 5),
                size=round(m_, 5), scale=round(float(M.scale), 5), loss=round(loss_, 5))


# ---------------------------------------------------------------------------------------------------------------- numpy (servers)
def np_weights(M):
    return {k: v.detach().cpu().numpy().astype(np.float32) for k, v in M.state_dict().items()}


def np_value(W, x):
    """value() in numpy: W from np_weights (or the export), x [B, inp]"""
    h = np.maximum(np.asarray(x, np.float32) @ W["l1.weight"].T + W["l1.bias"], 0.0)
    h = np.maximum(h @ W["l2.weight"].T + W["l2.bias"], 0.0)
    return ((h @ W["l3.weight"].T + W["l3.bias"])[:, 0] * float(np.asarray(W["scale"]).reshape(-1)[0])).astype(np.float32)

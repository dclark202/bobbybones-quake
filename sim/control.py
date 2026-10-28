"""v0.4.3 (B-280; docs/v0.4.3/RUN_v0.4.3.md, "In control"): the brain's readouts "in control", the trainer's --control.

"In control" is his share of the next two spawns of the mega and the red armor (who takes them), known only in hindsight:
the simulator's CONTROL_TRUTH=1 gives it CONTROL_H seconds late (info["aux"]'s ctl_lab: the label of the row CONTROL_D
rows before; ctl_one: the next spawn alone). A lesson only: no pay, nothing reads it yet (the head will, v0.4.3).

The readouts read what he had in mind while he played: the brain's state (the belief, 256 numbers at its ticks) and, for
the second readout, his hands' GRU memory beside it (512): the rollout keeps that state (detached, half precision, on the
host) every --control-every ticks in a ring as long as the horizon and one rollout more, and at the rollout's end the rows
whose label has arrived (their frame CONTROL_D rows back) are taken out with their labels; the update then scores and
teaches each readout on them. Their gradient reaches the readouts' own layers only (the state is a stored number, not the
brain's or the hands' output in this update): nothing of it reaches the policy, the brain or their optimizer.

Layout version 2 (2026-10-24, v0.4.2b): one or more readouts side by side ("belief": the brain's 256; "both": the brain's
256 and the hands' 512), each Linear(inp -> hid) + ReLU + Linear(hid -> 4) (the logits: the next two spawns, the next one,
the next mega, the next red armor), its last layer at zero (a guess of 0.5), from a random stream of its own; the module
is a ModuleDict (weights "control.<name>.*"). Each has its own Adam (tiny; not in the run's optimizer groups, so an
opt.pt of the run loads as before; its state starts cold at every process start) and the minibatch order comes from a
generator of its own (the trainer's random streams, and so his play, are untouched). The lesson's weight scales its rate
(Adam does not feel a loss's scale): --control-lr x the weight x the warm-up (live CONTROL_W: a factor, 0 stops it).
A layout of version 1 (one readout, "control.0.*", branch v043-control's) is not carried over: the trainer starts new.

Each label is scored before a readout learns from it, so the counters are an honest test on unseen frames: the Brier
score per output, beside two guesses that know nothing of the state: 0.5 (brier_half) and the best constant in hindsight
(brier_const: the labels' own spread in this update); skill = 1 - brier / brier_const (above 0: the state tells more than
the base rate); the AUC of the frames with a clear label (above 0.5 against below 0.5).
"""
import math

import numpy as np
import torch

COLS = ("ctl_lab", "ctl_one", "ctl_mh", "ctl_ra", "ctl_age")
OUTS = ("two", "one", "mh", "ra")      # (the head of v0.4.3 reads the four: sim/head2.py's "in control" slot)
SRCS = ("belief", "both")              # (the readouts' sources: the brain's state; the brain's state and the hands' memory)
SEEDS = {"belief": 4044, "both": 4045}


def parse_srcs(s):
    """'belief', 'both' or 'belief,both' -> a tuple in SRCS order"""
    got = [x.strip() for x in str(s).split(",") if x.strip()]
    assert got and all(x in SRCS for x in got), "--control-src: belief, both or belief,both (got {!r})".format(s)
    return tuple(x for x in SRCS if x in got)


def layout(srcs=("belief",), bel=256, mem=512, hid=64, every=5, horizon_frames=3600, tick=8):
    """the readouts' layout (version 2): the ring's width is the brain's state, and the hands' memory after it if a
    readout reads it; a readout reads the ring's first inp columns"""
    srcs = parse_srcs(",".join(srcs)) if not isinstance(srcs, str) else parse_srcs(srcs)
    both = "both" in srcs
    ro = [dict(name=s, src="belief" if s == "belief" else "belief+memory", inp=int(bel) + (int(mem) if s == "both" else 0),
               hid=int(hid), d=len(OUTS)) for s in srcs]
    return dict(version=2, bel=int(bel), mem=int(mem) if both else 0, width=int(bel) + (int(mem) if both else 0),
                every=int(every), horizon=int(horizon_frames), tick=int(tick), d=len(OUTS), outs=list(OUTS), readouts=ro)


def names(L):
    return [r["name"] for r in L["readouts"]]


def make_module1(r, seed):
    import torch.nn as nn
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        m = nn.Sequential(nn.Linear(int(r["inp"]), int(r["hid"])), nn.ReLU(), nn.Linear(int(r["hid"]), int(r["d"])))
    with torch.no_grad():
        m[2].weight.zero_()
        m[2].bias.zero_()
    return m


def make_module(L):
    """the readouts as a ModuleDict by name (made without a draw of the global random stream)"""
    import torch.nn as nn
    assert int(L.get("version", 1)) == 2, "control: layout version 2 expected"
    return nn.ModuleDict({r["name"]: make_module1(r, SEEDS.get(r["name"], 4044)) for r in L["readouts"]})


class Ring:
    """the states at the kept ticks, by the trainer's global row (rollout after rollout, the simulators in lockstep):
    a row g is kept when it is a tick (g % tick == tick - 1) and (g // tick) % every == 0. It holds the horizon and one
    rollout of T rows more: at a rollout's end every row whose label came in this rollout is still there"""

    def __init__(self, L, n, T):
        self.L, self.n = L, int(n)
        self.step = int(L["tick"]) * int(L["every"])
        self.S = (int(L["horizon"]) + int(T)) // self.step + 2
        self.buf = torch.zeros(self.S, self.n, int(L["width"]), dtype=torch.float16)
        self.g = torch.full((self.S,), -1, dtype=torch.long)

    def nbytes(self):
        return self.buf.numel() * self.buf.element_size()

    def kept(self, g):
        K = int(self.L["tick"])
        return g % K == K - 1 and (g // K) % int(self.L["every"]) == 0

    def push(self, g, s):
        """at row g (a tick of the belief) its state s [n, width] (any device)"""
        if not self.kept(g):
            return
        k = (g // self.step) % self.S
        self.buf[k] = s.detach().to("cpu", torch.float16)
        self.g[k] = int(g)

    def get(self, g):
        """the state of row g ([n, width] float16, host) or None if not kept (or written over)"""
        if g < 0 or not self.kept(g):
            return None
        k = (g // self.step) % self.S
        return self.buf[k] if int(self.g[k]) == int(g) else None


def batch(ring, g0, aux, ix, D):
    """this rollout's labels: aux [T + 1, n, C] (b_aux, rows g0 .. g0 + T), ix: column -> index; -> (states [B, width]
    float16, labels [B, 4], mask [B, 4]) on the host (copies: the ring may be written over after), the rows whose frame
    D rows back has a kept state (B = kept rows x n, less the rows with no label); None if none"""
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
    if not bool(keep.any()):
        return None
    return X[keep], Y[keep].clamp(min=0.0), M[keep]


def auc(p, y):
    """the AUC of scores p against the frames labelled above 0.5 (positive) and below (negative); ties share their rank.
    nan when one side is empty"""
    p, y = np.asarray(p, np.float64), np.asarray(y, np.float64)
    pos, neg = y > 0.5, y < 0.5
    sel = pos | neg
    p, pos = p[sel], pos[sel]
    n1 = int(pos.sum())
    n0 = len(p) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    o_ = np.argsort(p, kind="mergesort")
    _, inv, cnt = np.unique(p[o_], return_inverse=True, return_counts=True)
    avg = np.cumsum(cnt) - (cnt - 1) / 2.0                    # (1-based, the mean rank of each tie)
    r_ = np.empty(len(p))
    r_[o_] = avg[inv]
    return float((r_[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * float(n0)))


def learn(mods, opts, L, X, Y, M, lr, dev, gen, mb=8192, epochs=1):
    """score each readout (before learning), then one pass of its lesson -> counters by name: dict(sq [d], n [d], bce,
    auc [d]) and "base": dict(half [d], const [d], n [d], pos [d], neg [d]) (sums over the frames; auc of this update).
    The states go to the card a minibatch at a time; the order comes from gen (a CPU generator of the readouts' own)"""
    d = len(OUTS)
    out = {}
    if X is None or not len(X):
        return out
    Y64, M64 = Y.double(), M.double()
    n_ = M64.sum(0)
    ybar = (Y64 * M64).sum(0) / n_.clamp(min=1.0)
    out["base"] = dict(half=(((0.5 - Y64) ** 2) * M64).sum(0), const=(((ybar - Y64) ** 2) * M64).sum(0), n=n_,
                       pos=((Y > 0.5).double() * M64).sum(0), neg=((Y < 0.5).double() * M64).sum(0))
    B = len(X)
    for r in L["readouts"]:
        nm, inp = r["name"], int(r["inp"])
        mod, opt = mods[nm], opts[nm]
        P = torch.empty(B, d)
        with torch.no_grad():
            for b in range(0, B, mb):
                P[b:b + mb] = torch.sigmoid(mod(X[b:b + mb, :inp].to(dev).float())).float().cpu()
        P64 = P.double()
        bce = (torch.nn.functional.binary_cross_entropy(P.clamp(1e-6, 1 - 1e-6), Y, reduction="none").double() * M64).sum()
        au_ = [auc(P[:, j].numpy()[M[:, j].numpy() > 0], Y[:, j].numpy()[M[:, j].numpy() > 0]) for j in range(d)]
        out[nm] = dict(sq=(((P64 - Y64) ** 2) * M64).sum(0), bce=float(bce), auc=au_)
        if lr <= 0:
            continue
        for g_ in opt.param_groups:
            g_["lr"] = float(lr)
        for _ in range(int(epochs)):
            pm = torch.randperm(B, generator=gen)
            for b in range(0, B, mb):
                i_ = pm[b:b + mb]
                xb, yb, mk = X[i_, :inp].to(dev).float(), Y[i_].to(dev), M[i_].to(dev)
                l_ = (torch.nn.functional.binary_cross_entropy_with_logits(mod(xb), yb, reduction="none") * mk).sum() / \
                    mk.sum().clamp(min=1.0)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step()
    return out


def _r(x, k=4):
    x = float(x)
    return None if math.isnan(x) else round(x, k)


def record(acc, w, L, ring_gb=None):
    """the update's counters -> metrics.jsonl's "control": the frames and the two guesses per output, then per readout
    its Brier, skill (1 - Brier / the best constant's), AUC and BCE"""
    if not acc or "base" not in acc:
        return dict(w=round(float(w), 4), frames=0)
    b = acc["base"]
    d = len(OUTS)
    nf = [float(b["n"][i]) for i in range(d)]
    bc = [float(b["const"][i]) / max(1.0, nf[i]) for i in range(d)]
    rec = dict(w=round(float(w), 4), outs=list(OUTS), frames=[int(x) for x in nf],
               pos=[int(b["pos"][i]) for i in range(d)], neg=[int(b["neg"][i]) for i in range(d)],
               brier_half=[round(float(b["half"][i]) / max(1.0, nf[i]), 4) for i in range(d)],
               brier_const=[round(x, 4) for x in bc])
    if ring_gb is not None:
        rec["ring_gb"] = round(float(ring_gb), 3)
    for nm in names(L):
        if nm not in acc:
            continue
        a_ = acc[nm]
        br = [float(a_["sq"][i]) / max(1.0, nf[i]) for i in range(d)]
        rec[nm] = dict(brier=[round(x, 4) for x in br],
                       skill=[_r(1.0 - br[i] / bc[i]) if bc[i] > 0 else None for i in range(d)],
                       auc=[_r(x) for x in a_["auc"]],
                       bce=round(float(a_["bce"]) / max(1.0, sum(nf)), 4))
    return rec

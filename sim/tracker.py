"""2.2a (docs/runs/2.2/DESIGN.md "Three jobs, three learners"; the owner, 2026-11-16 evening: "the tracker is basically a build on to the brain"):
THE TRACKER. What is true now, and how things will go as he is playing. Plain feed-forward readouts on the brain, no memory of its own (the
brain's memory already holds what happened), its own Adam, no pay, nothing of the policy reads it: only the "desc" outlooks read its outputs,
as numbers (sim/desc22.py). Inside the strategy head (head2.trk.*) so every reader of a network file has it.

What it reads (numbers only, never a gradient back): the brain's state (256, as played: a stored number) and the columns of his own state that
the head reads (head2's obs_cols: his health, armor, weapons, ammunition, item timers, clock and score) and the counters below, by NAME from the
network's input list (each an input he already has, as perceived; none new). NOT the hands' memory. The inputs are rounded to half precision at
their one source (inp()/np_inp()): played and learnt alike.

Its outputs (OUTS, in this order; logits for the binary ones, the stack quantiles in hundreds of points):
  ctl_two ctl_one ctl_mh ctl_ra  "in control": sim/control.py's four chances, the same labels (CONTROL_TRUTH, 90 s late)
  fo_win fo_lose                 a fight now: he (the enemy) dies first / I die first (sim/fightodds.py's labels: FIGHT_TRUTH=1, 5 s late)
  idie5 idie10 hedie5 hedie10    I die within 5 / 10 s; he dies within 5 / 10 s (hindsight, from the rollout; a round's end cuts the window)
  con2 con5                      contact (the enemy in view) within 2 / 5 s (cut also by his own death)
  enh_q10 enh_q50 enh_q90        the enemy's health now: the 0.1, 0.5, 0.9 quantiles (pinball loss against the truth at that moment)
  ena_q10 ena_q50 ena_q90        ... and his armor
The yardstick of the stack: the simulator's rule-made estimate (EN_STACK's es_h, es_a, which make the "believed stack" inputs) against the
same truth. The existing readouts ("control" belief and both) keep learning beside it.

Scored BEFORE it learns from a row (prequential): Brier skill against the best constant and AUC for the binary outputs; pinball loss, the
middle's error, the rule's error, the share of truths inside low..high, the range's width by seconds since he last saw the enemy. All
moments, and split by in control / out of control by the TRUTH of "in control" (its next-two-spawns label above / below a half), which
arrives 90 s after the row: the split of a near row's scores is counted when its control label comes in (a queue of scored rows).

Numpy at the top level (the game server imports this file); torch inside the torch functions.
"""
import math

import numpy as np

VERSION = 1
SEED = 2201
OUTS = ("ctl_two", "ctl_one", "ctl_mh", "ctl_ra", "fo_win", "fo_lose", "idie5", "idie10", "hedie5", "hedie10", "con2", "con5",
        "enh_q10", "enh_q50", "enh_q90", "ena_q10", "ena_q50", "ena_q90")
NB = 12                                                       # the binary outputs: the first twelve
QS = (0.1, 0.5, 0.9)
CTL = slice(0, 4)
FO = slice(4, 6)
NEAR_B = slice(6, 12)
ENH = slice(12, 15)
ENA = slice(15, 18)
WIN_F = dict(idie5=200, idie10=400, hedie5=200, hedie10=400, con2=80, con5=200)   # frames (DT 0.025 s)
# the counters he has, by name (group | input), beside the head's own columns: what he saw and heard of the enemy, what he dealt him since
# his last respawn, the items he saw or heard him take, how long ago the enemy last died as he knows it, his own respawn
EXTRA = (("enemy", "noticed in view"), ("enemy", "seen or heard recently"), ("enemy", "damage dealt to the enemy this life"),
         ("memory", "enemy has the mega health"), ("memory", "enemy has the red armor"),
         ("memory", "enemy seen with rocket launcher"), ("memory", "enemy seen with railgun"), ("memory", "enemy seen with lightning gun"),
         ("memory", "enemy seen with machine gun"), ("memory", "enemy seen with shotgun"), ("memory", "enemy seen with grenade launcher"),
         ("memory", "enemy seen with plasma gun"), ("memory", "enemy seen with heavy machine gun"), ("memory", "enemy seen with gauntlet"),
         ("memory", "time since his own respawn"), ("memory", "enemy's last death known"), ("memory", "time since the enemy's last death"),
         ("v02 believed", "seconds since he last heard him"))
SEEN_BINS = (1.0, 3.0, 10.0)                                  # (the range's width by seconds since he last saw or heard the enemy)
O22 = ("hp", "armor", "es_h", "es_a", "seen_t", "reach", "win_b", "win_it")   # (the simulators' per-seat numbers after each step: sim/train_duel_rnn.py)


def extra_cols(input_names, extra=EXTRA):
    """the counters' columns in a network's input list (its "input_names": [group, input] pairs) -> (indices, names, missing)"""
    nm = [tuple(x) for x in input_names]
    idx, got, miss = [], [], []
    for g_, n_ in extra:
        if (g_, n_) in nm:
            idx.append(nm.index((g_, n_)))
            got.append(g_ + " | " + n_)
        else:
            miss.append(g_ + " | " + n_)
    return idx, got, miss


def layout(obs_cols, obs_names, bel=256, hid=128, every_near=2, every_ctl=5, tick=8, ctl_d=3600, fight_d=200):
    """obs_cols: the input columns (head2's obs_cols + the counters), obs_names: their names"""
    oc = [int(c) for c in obs_cols]
    return dict(version=VERSION, bel=int(bel), obs_cols=oc, obs_names=list(obs_names), width=int(bel) + len(oc), hid=int(hid),
                outs=list(OUTS), qs=list(QS), every_near=int(every_near), every_ctl=int(every_ctl), tick=int(tick),
                h_near=max(WIN_F.values()), ctl_d=int(ctl_d), fight_d=int(fight_d), win_f=dict(WIN_F))


def make_module(L):
    """Linear -> ReLU -> Linear -> ReLU -> the outputs; its last layer at zero (every chance 0.5, every quantile 0), from a random stream of
    its own (the global one untouched)"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "tracker: layout version {} expected".format(VERSION)

    class Tracker(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED)
                self.l1 = nn.Linear(int(L["width"]), int(L["hid"]))
                self.l2 = nn.Linear(int(L["hid"]), int(L["hid"]))
                self.l3 = nn.Linear(int(L["hid"]), len(OUTS))
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()

        def forward(self, x):
            h = torch.relu(self.l1(x.float()))
            h = torch.relu(self.l2(h))
            return self.l3(h)
    return Tracker()


def inp(L, brain, obs):
    """the tracker's input [B, width] (torch): the brain's state and his normalised inputs' columns, rounded to half precision (its one source)"""
    import torch
    c_ = torch.as_tensor(L["obs_cols"], dtype=torch.long, device=obs.device)
    return torch.cat([brain.float(), obs.float()[:, c_]], 1).half().float()


def np_inp(L, brain, obs):
    return np.concatenate([np.asarray(brain, np.float32), np.asarray(obs, np.float32)[:, np.asarray(L["obs_cols"], np.int64)]],
                          1).astype(np.float16).astype(np.float32)


def readable(o):
    """the outputs as numbers (torch): the twelve chances (sigmoid), the six quantiles as they are -> [B, 18]"""
    import torch
    return torch.cat([torch.sigmoid(o[:, :NB].float()), o[:, NB:].float()], 1)


def np_params(W, prefix="trk."):
    ks = ("l1.weight", "l1.bias", "l2.weight", "l2.bias", "l3.weight", "l3.bias")
    if not all(prefix + k_ in W for k_ in ks):
        return None
    return tuple(np.asarray(W[prefix + k_], np.float32) for k_ in ks)


def np_forward(PW, x):
    h = np.maximum(np.asarray(x, np.float32) @ PW[0].T + PW[1], 0.0)
    h = np.maximum(h @ PW[2].T + PW[3], 0.0)
    return (h @ PW[4].T + PW[5]).astype(np.float32)


def np_readable(o):
    o = np.asarray(o, np.float32)
    return np.concatenate([1.0 / (1.0 + np.exp(-o[:, :NB])), o[:, NB:]], 1).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------------ the rings and labels
class History:
    """per global frame and seat, what the near labels are made of (on the host, a ring of frames): his death in the step of that frame, the
    enemy's, the enemy in view after it, a round's end without his death, the fight label the aux row of that frame carries (fo_win, fo_lose:
    -1 unknown; the label of frame g - fight_d), the in-control label it carries (ctl_lab: of frame g - ctl_d)"""

    def __init__(self, n, frames):
        import torch
        self.n, self.F = int(n), int(frames)
        self.ev = torch.zeros(self.F, self.n, dtype=torch.uint8)       # bits: 1 his death, 2 the enemy's, 4 contact, 8 a round's end
        self.fo = torch.full((self.F, self.n, 2), -1, dtype=torch.int8)
        self.ctl = torch.full((self.F, self.n), -1.0, dtype=torch.float16)
        self.g = torch.full((self.F,), -1, dtype=torch.long)

    def nbytes(self):
        return self.ev.numel() + self.fo.numel() + 2 * self.ctl.numel()

    def put(self, g, ev, fo, ctl):
        k = int(g) % self.F
        self.ev[k], self.fo[k], self.ctl[k], self.g[k] = ev, fo, ctl, int(g)

    def has(self, g0, g1):
        import torch
        gg = torch.arange(int(g0), int(g1))
        return bool((self.g[gg % self.F] == gg).all())


def near_labels(hist, q, win_f, fight_d):
    """the near labels of the rows at global frame q [all seats] -> (Y [n, 12] float32, M [n, 12] bool) for outputs 4..11 (the first four,
    in control, are the ctl rows' own); M False where unknown. The windows start at the step of frame q (the state was read before it)"""
    import torch
    F, n = hist.F, hist.n
    W = max(win_f.values())
    gg = torch.arange(int(q), int(q) + W)
    ev = hist.ev[gg % F].long()                                      # [W, n]
    big = W + 10

    def first(bit):
        m = (ev & bit) > 0
        idx = torch.where(m, torch.arange(W)[:, None].expand(W, n), torch.full((W, n), big))
        return idx.min(0).values

    d_me, d_en, d_con, d_end = first(1), first(2), first(4), first(8)
    Y = torch.zeros(n, NB)
    M = torch.zeros(n, NB, dtype=torch.bool)
    for nm_, j_ in (("idie5", 6), ("idie10", 7)):
        Y[:, j_] = ((d_me < win_f[nm_]) & (d_me <= d_end)).float()
        M[:, j_] = True
    for nm_, j_ in (("hedie5", 8), ("hedie10", 9)):
        Y[:, j_] = ((d_en < win_f[nm_]) & (d_en <= d_end)).float()
        M[:, j_] = True
    cut_ = torch.minimum(d_end, d_me)
    for nm_, j_ in (("con2", 10), ("con5", 11)):
        Y[:, j_] = ((d_con < win_f[nm_]) & (d_con <= cut_)).float()
        M[:, j_] = True
    kf_ = (int(q) + int(fight_d)) % F
    if int(hist.g[kf_]) == int(q) + int(fight_d):
        fo_ = hist.fo[kf_].float()
        Y[:, 4:6] = fo_.clamp(min=0.0)
        M[:, 4:6] = fo_ >= 0
    return Y, M


def pinball(pred, y, qs=QS):
    """the mean pinball loss of quantiles pred [B, 3] against y [B] (torch)"""
    import torch
    q = torch.as_tensor(qs, dtype=pred.dtype, device=pred.device)[None]
    e = y[:, None] - pred
    return torch.maximum(q * e, (q - 1.0) * e)


def loss(o, Y, M):
    """the lesson of a batch: o [B, 18] the outputs, Y [B, 18] the labels (the stacks in hundreds), M [B, 18] which are known. The mean BCE of
    the known chances plus the mean pinball of the known quantiles"""
    import torch
    F_ = torch.nn.functional
    Mb = M[:, :NB].float()
    lb = (F_.binary_cross_entropy_with_logits(o[:, :NB].float(), Y[:, :NB].float(), reduction="none") * Mb).sum() / Mb.sum().clamp(min=1.0)
    lq = None
    for sl_ in (ENH, ENA):
        m_ = M[:, sl_][:, 0]
        if bool(m_.any()):
            t_ = pinball(o[m_][:, sl_].float(), Y[m_][:, sl_.start].float()).mean()
            lq = t_ if lq is None else lq + t_
    return lb if lq is None else lb + lq


def learn(mod, opt, X, Y, M, lr, dev, gen, mb=8192, epochs=1, clip=1.0):
    """one pass of the lesson (the scores are taken before, by score()). X [B, width] float16 (host), Y [B, 18], M [B, 18]"""
    import torch
    if X is None or not len(X) or lr <= 0:
        return None
    for g_ in opt.param_groups:
        g_["lr"] = float(lr)
    B = len(X)
    l_out = None
    with torch.enable_grad():
        for _ in range(int(epochs)):
            pm = torch.randperm(B, generator=gen)
            for b in range(0, B, int(mb)):
                i_ = pm[b:b + int(mb)]
                l_ = loss(mod(X[i_].to(dev).float()), Y[i_].to(dev), M[i_].to(dev))
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), float(clip))
                opt.step()
                l_out = float(l_)
    return l_out


def predict(mod, X, dev, mb=16384):
    import torch
    with torch.no_grad():
        return torch.cat([readable(mod(X[b:b + mb].to(dev).float())).cpu() for b in range(0, len(X), mb)]) if len(X) else None


# ------------------------------------------------------------------------------------------------------------------ the readouts
class Acc:
    """an update's sums: per binary output and split (all, in, out): the frames, the sum of p and y, the squared error, the labels' sum of
    squares (for the best constant's Brier), and the scores for the AUC; per quantile set: pinball, |middle - truth|, |rule - truth|, inside,
    width by seconds since seen"""

    SPLITS = ("all", "in", "out")

    def __init__(self):
        self.b = {s_: dict(n=np.zeros(NB), sy=np.zeros(NB), syy=np.zeros(NB), sq=np.zeros(NB), P=[[] for _ in range(NB)],
                           Y=[[] for _ in range(NB)]) for s_ in self.SPLITS}
        self.q = {s_: {k_: dict(n=0, pin=0.0, mid=0.0, rule=0.0, inside=0.0, below=0.0, above=0.0, cross=0.0,
                                wid=np.zeros(len(SEEN_BINS) + 1), wn=np.zeros(len(SEEN_BINS) + 1)) for k_ in ("health", "armor")}
                  for s_ in self.SPLITS}

    def add_b(self, split, P, Y, M, cap=200000):
        P, Y, M = np.asarray(P, np.float64), np.asarray(Y, np.float64), np.asarray(M, bool)
        d = self.b[split]
        for j in range(NB):
            m = M[:, j]
            if not m.any():
                continue
            p_, y_ = P[m, j], Y[m, j]
            d["n"][j] += len(y_)
            d["sy"][j] += y_.sum()
            d["syy"][j] += (y_ ** 2).sum()
            d["sq"][j] += ((p_ - y_) ** 2).sum()
            if sum(len(x_) for x_ in d["P"][j]) < cap:
                d["P"][j].append(p_.astype(np.float32))
                d["Y"][j].append(y_.astype(np.float32))

    def add_q(self, split, which, pred, y, rule, seen):
        """pred [B, 3] the quantiles (hundreds), y [B] the truth, rule [B] the rule's estimate, seen [B] seconds since he last saw him"""
        pred, y, rule, seen = (np.asarray(v_, np.float64) for v_ in (pred, y, rule, seen))
        if not len(y):
            return
        d = self.q[split][which]
        q = np.asarray(QS)[None]
        e = y[:, None] - pred
        d["n"] += len(y)
        d["pin"] += np.maximum(q * e, (q - 1.0) * e).sum()
        d["mid"] += np.abs(pred[:, 1] - y).sum()
        d["rule"] += np.abs(rule - y).sum()
        lo_, hi_ = np.minimum(pred[:, 0], pred[:, 2]), np.maximum(pred[:, 0], pred[:, 2])
        d["inside"] += ((y >= lo_) & (y <= hi_)).sum()
        d["below"] += (y < lo_).sum()
        d["above"] += (y > hi_).sum()
        d["cross"] += ((pred[:, 0] > pred[:, 1]) | (pred[:, 1] > pred[:, 2])).sum()
        b_ = np.searchsorted(np.asarray(SEEN_BINS), seen, side="right")
        np.add.at(d["wid"], b_, hi_ - lo_)
        np.add.at(d["wn"], b_, 1.0)

    def record(self):
        from control import auc as auc_
        out = {}
        for s_ in self.SPLITS:
            d = self.b[s_]
            r = {}
            for j in range(NB):
                n_ = float(d["n"][j])
                if n_ < 2:
                    r[OUTS[j]] = dict(n=int(n_))
                    continue
                ybar = d["sy"][j] / n_
                bc = d["syy"][j] / n_ - ybar ** 2
                br = d["sq"][j] / n_
                P_ = np.concatenate(d["P"][j]) if d["P"][j] else np.zeros(0)
                Y_ = np.concatenate(d["Y"][j]) if d["Y"][j] else np.zeros(0)
                au = auc_(P_, Y_) if len(P_) else float("nan")
                r[OUTS[j]] = dict(n=int(n_), rate=round(float(ybar), 4), brier=round(float(br), 5), brier_const=round(float(bc), 5),
                                  skill=(round(float(1.0 - br / bc), 4) if bc > 0 else None), auc=(None if math.isnan(au) else round(float(au), 4)))
            for k_ in ("health", "armor"):
                q_ = self.q[s_][k_]
                n_ = max(1, q_["n"])
                r["stack_" + k_] = dict(n=int(q_["n"]), pinball=round(q_["pin"] / n_ / 3.0, 5), mid_err=round(100.0 * q_["mid"] / n_, 2),
                                        rule_err=round(100.0 * q_["rule"] / n_, 2), inside=round(q_["inside"] / n_, 4),
                                        below=round(q_["below"] / n_, 4), above=round(q_["above"] / n_, 4), crossed=round(q_["cross"] / n_, 4),
                                        width_by_seen={"<{}s".format(SEEN_BINS[0]) if i_ == 0 else (">{}s".format(SEEN_BINS[-1]) if i_ == len(SEEN_BINS)
                                                       else "{}-{}s".format(SEEN_BINS[i_ - 1], SEEN_BINS[i_])):
                                                       (round(100.0 * q_["wid"][i_] / q_["wn"][i_], 1) if q_["wn"][i_] > 0 else None)
                                                       for i_ in range(len(SEEN_BINS) + 1)})
            out[s_] = r
        return out

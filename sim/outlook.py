"""2.1f (docs/runs/2.1/2.1f/CARD.md; owner 2026-11-16): the OUTLOOK, inside the strategy head. "He's thinking in the hypothetical future (8 s
ahead) and pulling towards what will have the best outlook in the forward time window".

What it is. From the head's state s (256; detached for its lesson): Linear 128 -> ReLU -> Linear 128 -> ReLU -> Linear to K x (n_target + 1)
numbers: for each label kind k, one number per target (the outlook of committing to that target from here) and one GOAL-BLIND number (the same
label predicted without knowing the target: the baseline that shows whether knowing the goal helps). Its last layer starts at zero (every
outlook 0: no term), from a random stream of its own (the global one untouched). Inside the head (sim/head2.py add_outlook: head2.out.*, the
buffers out_g, out_pick), so every reader of a network file plays it.

The term on his target scores (the one played kind, out_pick): out_g x clip(o_k[target] - mean over the targets of o_k, +-clip), in the label's
STANDARDISED units (no division by the outlook's own spread: a weak signal stays small; parent review 2026-11-16), rounded to half precision at this
one source (term() and np_term(): the trainer keeps it so a frame and adds it again in the learner to the bit). With out_g 0 or the last layer at
zero the term is exactly 0.

The label kinds (the trainer makes them; the names are kept in the layout; "seg" first: out_pick 0 plays it):
  seg    the option's value: the head's pay (gamma a frame) from the reading until he LEAVES the goal he is on (the next keep reading whose goal
         differs, or after a new draw; a death or a round's end cuts it, its pay in, no bootstrap), plus, still alive there, gamma^k x the head's
         own value at that reading (as stored for the learner); past the rollout's end the head's last bootstrap value (its return's)
  ret    the head's own return target at the reading (its value's target: GAE of the head's pay at its gamma and lambda, bootstrapped by
         its value)
  all8   the head's pay summed with its gamma over the next 40 head ticks (320 frames), cut at a death or a round's end (that frame's pay in,
         nothing after); a row whose window passes the rollout's end is dropped
  win8   the same window over the win-chance part of the pay alone (the stream --head2-pay win would pay: the judge's win_raw x the gain)
  win5   the win-chance part over 25 head ticks (200 frames)
Each kind's labels are standardised by a running mean and spread (Stats, kept in the checkpoint's top-level "out_stats"); the outlook is in
those units. Its lesson: the smooth L1 of the number of the goal he is on and of the goal-blind number against the standardised label, at EVERY
keep reading of his on a held trip (decisions and stays: the term is added at every reading, so it learns where it is used; trial trips' rows
in, marked); its own Adam (the checkpoint's "out_opt"), the main optimizer never steps it (rule 13: it learns silently).

2.2a (docs/runs/2.2/DESIGN.md; the build of 2026-11-16): two more kinds and the FACTS.
  segw   as seg, over the win chance WITH the items (the judge that sees the items, sim/win_judge.py JUDGE_ITEMS: the stream --head2-pay win
         would pay under it, "win_it"), bootstrapped by the head's silent second value (vw: a value of that stream on the head's state, its
         own Adam; value_module())
  winit8 that stream over 8 s (320 frames)
  (win8 and win5 stay on the judge WITHOUT the items, "win_b", what the hands' win part is; without JUDGE_ITEMS both streams are the same)
The facts (FACTS; a layout with "facts": a second last layer l3f, facts x (n_target + 1), the goal-blind last): for the goal he is on, over the
same segment as seg (from the reading until he leaves the goal; his death or a round's end cuts it): he_dies (the enemy died in it), i_die,
took (he reached or took the target), his own stack at its end (health, armor) and the enemy's true stack at its end (health, armor; a death:
0). The three binary ones by a logistic loss (reported: Brier skill against the best constant and AUC), the stacks in hundreds, standardised
by running statistics, smooth L1. A row whose segment runs past the rollout's end with no cut has no facts (they cannot be bootstrapped).
They are silent readouts: never in the term.

Numpy at the top level (the game server imports this file); torch inside the torch functions.
"""
import math

import numpy as np

VERSION = 1
SEED = 6161
KINDS = ("seg", "ret", "all8", "win8", "win5")
KINDS22 = KINDS + ("segw", "winit8")                        # (2.2a) the kinds of 2.2a's outlooks
WINDOW = {"all8": 320, "win8": 320, "win5": 200, "winit8": 320}     # frames: 40 and 25 head ticks of 8 frames
STREAM = {"seg": "seg", "ret": "ret", "all8": "all", "win8": "win", "win5": "win", "segw": "segw", "winit8": "winit"}
FACTS = ("he_dies", "i_die", "took", "my_h", "my_a", "en_h", "en_a")    # (2.2a) the facts of a segment
FBIN = 3                                                    # ... the first three binary, the four stacks (hundreds) after
CLIP = 5.0                                                  # the centred outlook (standardised units) is clipped to +- this before out_g
STAT_RATE = 0.05                                            # the labels' running mean and spread: this rate an update (the first update: its own)
REPLAY_G = (0.5, 1.0, 2.0, 4.0, 8.0)                        # the first-order replay's strengths (the readout the mark is chosen from)


def layout(head=256, n_target=17, kinds=KINDS, hid=128, clip=CLIP, facts=False):
    ks = [str(k_) for k_ in kinds]
    assert ks and all(k_ in STREAM for k_ in ks) and len(set(ks)) == len(ks), "outlook: kinds among {}".format(KINDS22)
    return dict(version=VERSION, head=int(head), n_target=int(n_target), kinds=ks, hid=int(hid), clip=float(clip),
                out=len(ks) * (int(n_target) + 1), **({"facts": list(FACTS)} if facts else {}))


def make_module(L):
    """two hidden layers, the last at zero (every outlook 0), from a random stream of its own (the global one untouched)"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "outlook: layout version {} expected".format(VERSION)

    class Outlook(nn.Module):
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
            self.nk = len(L["kinds"])
            self.ni = int(L["n_target"])
            self.nf = len(L.get("facts") or ())
            if self.nf:                                      # (2.2a) the facts' last layer: a stream of its own, at zero
                with torch.random.fork_rng(devices=[]):
                    torch.manual_seed(SEED + 7)
                    self.l3f = nn.Linear(int(L["hid"]), self.nf * (self.ni + 1))
                with torch.no_grad():
                    self.l3f.weight.zero_()
                    self.l3f.bias.zero_()

        def forward(self, s):
            """s [B, head] -> [B, kinds, n_target + 1] (the last column: goal-blind)"""
            h = torch.relu(self.l1(s.float()))
            h = torch.relu(self.l2(h))
            return self.l3(h).view(-1, self.nk, self.ni + 1)

        def both(self, s):
            """(2.2a) -> (the kinds [B, kinds, n_target + 1], the facts [B, facts, n_target + 1] or None)"""
            h = torch.relu(self.l1(s.float()))
            h = torch.relu(self.l2(h))
            return self.l3(h).view(-1, self.nk, self.ni + 1), (self.l3f(h).view(-1, self.nf, self.ni + 1) if self.nf else None)
    return Outlook()


def outlook(M, s):
    """the outlook [B, kinds, n_target + 1] (no gradient)"""
    import torch
    with torch.no_grad():
        return M(s.detach().float())


def zed(o, clip=CLIP):
    """z [B, n_target] from one kind's outlook o [B, n_target + 1]: the targets' numbers less their mean, in the label's standardised units (no
    division by the outlook's own spread: a weak signal stays small), clipped to +-clip"""
    o_ = o[..., :-1].float()
    return (o_ - o_.mean(-1, keepdim=True)).clamp(-float(clip), float(clip))


def term(o, g, clip=CLIP):
    """the term on the target's logits [B, n_target]: g x z, rounded to half precision. g: a number or [B, 1]"""
    return (g * zed(o, clip)).half().float()


def gumbel_given_top(phi, k, gen):
    """(the trial trips) the held draw's numbers g [B, K] for log-probabilities phi [B, K], drawn from the Gumbel numbers' law GIVEN that the
    held pick argmax(phi + g) is k [B] (the top value Z ~ Gumbel(logsumexp(phi)); every other phi_i + g_i a Gumbel truncated below Z): the trip
    then runs exactly as a held trip whose draw landed on k (its mid-trip changes when his scores cross, as any trip's)"""
    import torch
    B_, K_ = phi.shape
    ph_ = phi.float()
    u0 = torch.rand(B_, generator=gen, device=ph_.device).clamp(1e-12, 1.0 - 1e-7)
    Z = torch.logsumexp(ph_, -1) - torch.log(-torch.log(u0))
    u = torch.rand(B_, K_, generator=gen, device=ph_.device).clamp(1e-12, 1.0 - 1e-7)
    v = -torch.logaddexp(-Z[:, None].expand(-1, K_), -(ph_ - torch.log(-torch.log(u))))
    v = torch.minimum(v, torch.nextafter(Z, Z - 1.0)[:, None])
    v = v.scatter(1, k.long()[:, None], Z[:, None])
    return v - ph_


def np_params(W):
    """the outlook's arrays (l1, l2, l3: weight, bias) from the head's weights (head2.params_np / the plugin's W2), None without them"""
    ks = ("out.l1.weight", "out.l1.bias", "out.l2.weight", "out.l2.bias", "out.l3.weight", "out.l3.bias")
    if not all(k_ in W for k_ in ks):
        return None
    return tuple(np.asarray(W[k_], np.float32) for k_ in ks)


def np_outlook(PW, L, hs):
    """outlook() in numpy: PW from np_params, L the outlook's layout, hs [B, >= head] (the head's state first) -> [B, kinds, n_target + 1]"""
    s = np.asarray(hs, np.float32)[:, :int(L["head"])]
    h = np.maximum(s @ PW[0].T + PW[1], 0.0)
    h = np.maximum(h @ PW[2].T + PW[3], 0.0)
    return (h @ PW[4].T + PW[5]).astype(np.float32).reshape(len(s), len(L["kinds"]), int(L["n_target"]) + 1)


def np_term(o, g, clip=CLIP):
    """term() in numpy: [B, n_target] float32 holding half-precision numbers"""
    o_ = np.asarray(o, np.float32)[..., :-1]
    z_ = np.clip(o_ - o_.mean(-1, keepdims=True), -np.float32(clip), np.float32(clip))
    return (np.float32(g) * z_).astype(np.float16).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------------ the labels
def window_sums(rew, done, gamma, W):
    """the pay rew [T, N] summed with gamma over the next W frames from each frame t, cut at a done (that frame's pay in, nothing after);
    done [T, N] (b_done: a death or a round's end after that frame's action). -> (lab [T, N] float64, ok [T] bool: the window t .. t + W - 1
    lies inside the rollout). The window: F_t - gamma^W x (no done on t .. t + W - 1) x F_{t+W}, F the discounted sum cut at done (float64)"""
    import torch
    T, N = rew.shape
    dev = rew.device
    F = torch.zeros(T + 1, N, dtype=torch.float64, device=dev)
    r64 = rew.double()
    nd = 1.0 - (done > 0).double()
    for t in reversed(range(T)):
        F[t] = r64[t] + float(gamma) * nd[t] * F[t + 1]
    cs = torch.cat([torch.zeros(1, N, dtype=torch.float64, device=dev), torch.cumsum((done > 0).double(), 0)], 0)
    lab = torch.zeros(T, N, dtype=torch.float64, device=dev)
    ok = torch.zeros(T, dtype=torch.bool, device=dev)
    n_ = T - int(W) + 1
    if n_ > 0:
        tt = torch.arange(n_, device=dev)
        clean = ((cs[tt + int(W)] - cs[tt]) == 0).double()
        lab[:n_] = F[tt] - (float(gamma) ** int(W)) * clean * F[tt + int(W)]
        ok[:n_] = True
    return lab, ok


def segment_ends(G_r, nd_r):
    """(kind "seg") for each reading j and seat: the reading at which he leaves the goal he is on at j [J, N] long (J: past the rollout's end).
    G_r [J, N] long: the goal he is on at each keep reading on a held trip (-1: none, not on a held trip, not alive); nd_r [J, N] bool: a new
    draw since the reading before (a trip's end). He leaves at the first later reading whose goal differs from j's or that follows a new draw"""
    import torch
    J, N = G_r.shape
    ch = torch.zeros(J, N, dtype=torch.bool, device=G_r.device)
    ch[1:] = (G_r[1:] != G_r[:-1]) | nd_r[1:].bool()
    nxt = torch.full((J, N), J, dtype=torch.long, device=G_r.device)
    for j in range(J - 2, -1, -1):
        nxt[j] = torch.where(ch[j + 1], torch.full_like(nxt[j + 1], j + 1), nxt[j + 1])
    return nxt


def seg_values(rew, done, val, gamma, rows_t, rows_i, end_t):
    """(kind "seg", the option's value) his pay from the row's reading t until he leaves the goal (the frame end_t of the leaving reading; T: the
    rollout's end) at gamma a frame, cut at a death or a round's end (that frame's pay in, no bootstrap after), plus, alive and in the same round at
    end_t, gamma^(end_t - t) x the head's value there (val [T + 1, N] as the head's return uses it: val[T] the rollout's last bootstrap). ->
    (the labels [R] float64, the segment's length in frames to the leaving reading or the frame after the cut [R] long)"""
    import torch
    T, N = rew.shape
    dev = rew.device
    F = torch.zeros(T + 1, N, dtype=torch.float64, device=dev)
    r64, nd = rew.double(), 1.0 - (done > 0).double()
    for t in reversed(range(T)):
        F[t] = r64[t] + float(gamma) * nd[t] * F[t + 1]
    cs = torch.cat([torch.zeros(1, N, dtype=torch.float64, device=dev), torch.cumsum((done > 0).double(), 0)], 0)
    dn_ = torch.full((T + 1, N), T, dtype=torch.long, device=dev)            # the first done frame at or after t (T: none)
    for t in reversed(range(T)):
        dn_[t] = torch.where(done[t] > 0, torch.full_like(dn_[t + 1], t), dn_[t + 1])
    t_, i_, e_ = rows_t.long(), rows_i.long(), end_t.long()
    clean = (cs[e_, i_] - cs[t_, i_]) == 0                                    # no done on t .. end_t - 1
    gk = torch.pow(torch.full_like(t_, 0, dtype=torch.float64) + float(gamma), (e_ - t_).double())
    lab = F[t_, i_] + torch.where(clean, gk * (val[e_, i_].double() - F[e_, i_]), torch.zeros_like(gk))
    ln_ = torch.minimum(e_, dn_[t_, i_] + 1) - t_
    return lab, ln_


def labels(kinds, rows_t, rows_i, ret=None, pay_all=None, pay_win=None, done=None, gamma=0.9998, val=None, seg_end=None, pay_wit=None, val_w=None):
    """each row's raw label per kind -> (Y [R, K] float32, OK [R, K] bool, the segments' lengths in frames [R] or None). rows_t, rows_i [R] long
    (frame, seat); ret [T, N] the head's return target (kind "ret"); pay_all, pay_win [T, N] the head's whole pay and the win-chance part;
    val [T + 1, N] the head's value as stored, seg_end [R] the frame of each row's leaving reading (kind "seg"). (2.2a) pay_wit [T, N] the win
    chance with the items, val_w [T + 1, N] the head's silent second value of it (kinds "segw", "winit8"). None: that kind's rows not ok"""
    import torch
    R = int(len(rows_t))
    dev = rows_t.device
    Y = torch.zeros(R, len(kinds), dtype=torch.float32, device=dev)
    OK = torch.zeros(R, len(kinds), dtype=torch.bool, device=dev)
    SL = None
    cache = {}
    for k_, nm_ in enumerate(kinds):
        if R == 0:
            continue
        if nm_ == "seg":
            if pay_all is not None and done is not None and val is not None and seg_end is not None:
                lab_, SL = seg_values(pay_all, done, val, gamma, rows_t, rows_i, seg_end)
                Y[:, k_] = lab_.float()
                OK[:, k_] = torch.isfinite(Y[:, k_])
            continue
        if nm_ == "segw":                                   # (2.2a) as seg over the win chance with the items, its own value
            if pay_wit is not None and done is not None and val_w is not None and seg_end is not None:
                lab_, _ = seg_values(pay_wit, done, val_w, gamma, rows_t, rows_i, seg_end)
                Y[:, k_] = lab_.float()
                OK[:, k_] = torch.isfinite(Y[:, k_])
            continue
        if nm_ == "ret":
            if ret is not None:
                Y[:, k_] = ret[rows_t, rows_i].float()
                OK[:, k_] = torch.isfinite(Y[:, k_])
            continue
        src_ = pay_all if STREAM[nm_] == "all" else (pay_wit if STREAM[nm_] == "winit" else pay_win)
        if src_ is None or done is None:
            continue
        key_ = (STREAM[nm_], WINDOW[nm_])
        if key_ not in cache:
            cache[key_] = window_sums(src_, done, gamma, WINDOW[nm_])
        lab_, okt_ = cache[key_]
        Y[:, k_] = lab_[rows_t, rows_i].float()
        OK[:, k_] = okt_[rows_t] & torch.isfinite(Y[:, k_])
    return Y, OK, SL


class Stats:
    """each kind's labels' running mean and spread (a rate STAT_RATE an update; the first update: its own), their counts"""

    def __init__(self, kinds, d=None):
        self.kinds = list(kinds)
        K = len(self.kinds)
        self.mean, self.var, self.n = np.zeros(K), np.ones(K), np.zeros(K, np.int64)
        if d:
            for k_, nm_ in enumerate(self.kinds):
                if nm_ in d.get("kinds", []):
                    j_ = d["kinds"].index(nm_)
                    self.mean[k_], self.var[k_], self.n[k_] = float(d["mean"][j_]), float(d["var"][j_]), int(d["n"][j_])

    def update(self, Y, OK):
        """-> this batch's raw mean and spread per kind (None where no rows)"""
        raw = []
        for k_ in range(len(self.kinds)):
            y_ = Y[OK[:, k_], k_].double()
            if len(y_) < 2:
                raw.append(None)
                continue
            m_, v_ = float(y_.mean()), float(y_.var())
            raw.append((m_, math.sqrt(max(v_, 0.0)), int(len(y_))))
            if self.n[k_] == 0:
                self.mean[k_], self.var[k_] = m_, max(v_, 1e-12)
            else:
                self.mean[k_] += STAT_RATE * (m_ - self.mean[k_])
                self.var[k_] += STAT_RATE * (max(v_, 1e-12) - self.var[k_])
            self.n[k_] += len(y_)
        return raw

    def standardise(self, Y):
        import torch
        m_ = torch.as_tensor(self.mean, dtype=torch.float32, device=Y.device)
        s_ = torch.as_tensor(np.sqrt(np.maximum(self.var, 1e-12)), dtype=torch.float32, device=Y.device)
        return (Y - m_) / s_

    def ready(self, k_):
        return bool(self.n[k_] > 0)

    def to_dict(self):
        return dict(kinds=list(self.kinds), mean=[float(x_) for x_ in self.mean], var=[float(x_) for x_ in self.var], n=[int(x_) for x_ in self.n])


def generator(seed=SEED + 1):
    import torch
    return torch.Generator().manual_seed(int(seed))


def _gather_goal(out, G):
    """out [b, K, NT + 1], G [b] -> the chosen target's number per kind [b, K]"""
    return out.gather(-1, G[:, None, None].expand(-1, out.shape[1], 1)).squeeze(-1)


def _loss(out, G, Z, OK):
    import torch
    F_ = torch.nn.functional
    pg = _gather_goal(out, G)
    pb = out[..., -1]
    l_ = None
    for k_ in range(Z.shape[1]):
        m_ = OK[:, k_]
        if not bool(m_.any()):
            continue
        t_ = F_.smooth_l1_loss(pg[m_, k_], Z[m_, k_]) + F_.smooth_l1_loss(pb[m_, k_], Z[m_, k_])
        l_ = t_ if l_ is None else l_ + t_
    return l_


def learn(M, opt, S, G, Z, OK, epochs=2, mb=1024, gen=None, clip=1.0, decay=0.0):
    """one rollout's lesson: S [R, head] the states (detached), G [R] the target he took, Z [R, K] the standardised labels, OK [R, K];
    each kind's mean smooth L1 of the chosen target's number and of the goal-blind number, summed over the kinds. (rule 11) decay: decoupled
    weight decay on the last layer's weights after each step, lr x decay. -> the last loss"""
    import torch
    R = int(len(G))
    if R == 0 or not bool(OK.any()):
        return None
    S, G, Z, OK = S.detach().float(), G.long(), Z.detach().float(), OK.bool()
    loss_ = None
    with torch.enable_grad():
        for _ in range(int(epochs)):
            perm = torch.randperm(R, generator=gen) if gen is not None else torch.randperm(R)
            for i in range(0, R, int(mb)):
                j = perm[i:i + int(mb)].to(S.device)
                l_ = _loss(M(S[j]), G[j], Z[j], OK[j])
                if l_ is None:
                    continue
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(M.parameters(), float(clip))
                opt.step()
                if decay > 0:
                    with torch.no_grad():
                        M.l3.weight.mul_(1.0 - float(opt.param_groups[0]["lr"]) * float(decay))
                loss_ = float(l_)
    return loss_


def forward_rows(M, S, chunk=8192):
    import torch
    with torch.no_grad():
        return torch.cat([M(S[i:i + chunk].float()) for i in range(0, len(S), chunk)]) if len(S) else None


def loss_of(M, S, G, Z, OK):
    import torch
    if len(G) == 0:
        return None
    with torch.no_grad():
        l_ = _loss(forward_rows(M, S), G.long(), Z.float(), OK.bool())
    return float(l_) if l_ is not None else None


def _qt(x, q):
    """torch.quantile on at most 4M numbers (an even stride of a larger set: its size limit)"""
    import torch
    x = x.flatten().float()
    if x.numel() > 4000000:
        x = x[::int(math.ceil(x.numel() / 4000000))]
    return torch.quantile(x, q)


def _r2(p, y):
    if len(y) < 2:
        return None
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return None
    return 1.0 - float(((y - p) ** 2).sum()) / sst


def _corr(x, y):
    if len(x) < 3:
        return None
    x_, y_ = x - x.mean(), y - y.mean()
    d_ = float(x_.norm() * y_.norm())
    return float((x_ * y_).sum()) / d_ if d_ > 0 else None


def _q(v, d=4):
    return None if v is None or not math.isfinite(v) else round(float(v), d)


def _block(o_, g_, y_, NT):
    """the skill numbers of one set of rows: o_ [n, NT + 1] (one kind), g_ [n], y_ [n] standardised labels"""
    n_ = int(len(y_))
    if n_ < 2:
        return dict(rows=n_)
    o_, y_ = o_.double(), y_.double()
    pg_ = o_.gather(1, g_[:, None]).squeeze(1)
    pb_ = o_[:, -1]
    r2g_, r2b_ = _r2(pg_, y_), _r2(pb_, y_)
    mu_ = o_[:, :NT].mean(-1)
    return dict(rows=n_, r2_goal=_q(r2g_), r2_blind=_q(r2b_), gain=_q(r2g_ - r2b_) if (r2g_ is not None and r2b_ is not None) else None,
                corr=_q(_corr(pg_ - mu_, y_ - pb_)), top_share=_q(float((o_[:, :NT].argmax(-1) == g_).double().mean())))


def readouts(out, G, Z, OK, dec=None, ctrl=None, trial=None, base=None, clip=CLIP):
    """measured BEFORE the lesson (prequential: rows it has not learnt from). out [R, K, NT + 1] the outlook now, G [R] the goal he is on, Z
    [R, K] the labels standardised by the statistics before this rollout, OK [R, K]; dec [R] bool (a decision reading: a new draw applied or a
    change mid-trip; else a stay reading); ctrl [R] bool or None (in control by his own readout); trial [R] bool or None (on a trial trip); base
    [R, NT] (his log-probabilities without the term + the held numbers, as played) or None. -> per kind a dict: the skill overall, at decision
    readings and at stay readings (R2 of the goal's number, of the goal-blind one, their difference, the correlation of the goal's number less
    the mean with the label less the goal-blind number, the share where the outlook's top is the goal he is on); by control and trial; rows per
    goal; the spread between the targets; z's size; the first-order replay: the share of his own readings whose pick changes at each REPLAY_G"""
    import torch
    K, NT = out.shape[1], out.shape[2] - 1
    res = []
    for k_ in range(K):
        m_ = OK[:, k_]
        d_ = dict(all=_block(out[m_, k_], G[m_].long(), Z[m_, k_], NT))
        d_["rows"] = int(m_.sum())
        if dec is not None:
            for nm_, s_ in (("decision", m_ & dec.bool()), ("stay", m_ & ~dec.bool())):
                d_[nm_] = _block(out[s_, k_], G[s_].long(), Z[s_, k_], NT)
        for nm_, f_, ab_ in (("ctrl", ctrl, ("in", "out")), ("trial", trial, ("trial", "own"))):
            if f_ is None:
                continue
            d_[nm_] = {ab_[0]: _block(out[m_ & f_.bool(), k_], G[m_ & f_.bool()].long(), Z[m_ & f_.bool(), k_], NT),
                       ab_[1]: _block(out[m_ & ~f_.bool(), k_], G[m_ & ~f_.bool()].long(), Z[m_ & ~f_.bool(), k_], NT)}
        o_ = out[:, k_].double()
        cen_ = o_[:, :NT] - o_[:, :NT].mean(-1, keepdim=True)
        sp_ = cen_.pow(2).mean(-1).sqrt().float()
        z_ = zed(out[:, k_], clip)
        az_ = z_.abs().float()
        d_.update(per_goal=torch.bincount(G[m_].long(), minlength=NT)[:NT].tolist(),
                  spread=dict(mean=_q(float(sp_.mean())), p10=_q(float(_qt(sp_, 0.1))), p50=_q(float(_qt(sp_, 0.5))),
                              p90=_q(float(_qt(sp_, 0.9))), rms=_q(float(cen_.pow(2).mean().sqrt()), 6)) if len(sp_) else None,
                  z=dict(mean_abs=_q(float(az_.mean())), p50=_q(float(_qt(az_.flatten(), 0.5))),
                         p90=_q(float(_qt(az_.flatten(), 0.9))), p99=_q(float(_qt(az_.flatten(), 0.99)))) if az_.numel() else None)
        if base is not None and len(base):
            own_ = ~trial.bool() if trial is not None else torch.ones(len(G), dtype=torch.bool, device=G.device)
            b_ = base[own_].float()
            zz_ = z_[own_]
            a0_ = b_.argmax(-1)
            d_["replay"] = {str(g_): _q(float(((b_ + float(g_) * zz_).argmax(-1) != a0_).double().mean())) if len(b_) else None for g_ in REPLAY_G}
            d_["replay_rows"] = int(len(b_))
        res.append(d_)
    return res


def spread_rms(out):
    """the RMS of the centred outlook per kind over the rows [K] (what out_scale follows)"""
    NT = out.shape[2] - 1
    c_ = out[..., :NT] - out[..., :NT].mean(-1, keepdim=True)
    return c_.double().pow(2).mean((0, 2)).sqrt()


# ------------------------------------------------------------------------------------------------------------------ (2.2a) the facts
def fact_labels(rows_t, rows_i, seg_end, done, died_me, died_en, reach, hp_after, foe):
    """the facts of each row's segment -> (FY [R, 7] float32: the binary three 0 / 1, the stacks in hundreds; FM [R, 7] bool). rows_t, rows_i
    [R]; seg_end [R] the frame of the leaving reading (T: past the rollout's end); done [T, N] (b_done: his death or a round's end after the
    step of that frame); died_me, died_en [T, N] bool his death, the enemy's, in the step of that frame; reach [T, N] bool his target reached
    or taken after that step; hp_after [T, N, 2] his health and armor after that step (the enemy's: the row of seat foe[i]). The segment:
    frames t .. e - 1, e = min(seg_end, the first done at or after t, + 1); with no done before T and seg_end = T the facts are unknown"""
    import torch
    T, N = done.shape
    dev = done.device
    t_, i_, e_ = rows_t.long(), rows_i.long(), seg_end.long()
    dn_ = torch.full((T + 1, N), T, dtype=torch.long, device=dev)
    for t in reversed(range(T)):
        dn_[t] = torch.where(done[t] > 0, torch.full_like(dn_[t + 1], t), dn_[t + 1])
    d0_ = dn_[t_, i_]
    cut_ = d0_ < e_                                              # (a done inside the segment cuts it after that frame)
    e2_ = torch.where(cut_, d0_ + 1, e_)
    known_ = cut_ | (e_ < T)

    def anyin(x):
        cs = torch.cat([torch.zeros(1, N, dtype=torch.float64, device=dev), torch.cumsum(x.double(), 0)], 0)
        return (cs[e2_, i_] - cs[t_, i_]) > 0

    f_ = torch.as_tensor(foe, dtype=torch.long, device=dev)[i_]
    he_, me_, tk_ = anyin(died_en), anyin(died_me), anyin(reach)
    last_ = (e2_ - 1).clamp(min=0)
    my_ = hp_after[last_, i_].float().clamp(min=0.0) / 100.0
    en_ = hp_after[last_, f_].float().clamp(min=0.0) / 100.0
    my_ = torch.where(me_[:, None], torch.zeros_like(my_), my_)
    en_ = torch.where(he_[:, None], torch.zeros_like(en_), en_)
    FY = torch.stack([he_.float(), me_.float(), tk_.float(), my_[:, 0], my_[:, 1], en_[:, 0], en_[:, 1]], 1)
    FM = known_[:, None].expand(-1, len(FACTS)).clone()
    return FY, FM


def facts_loss(fo, G, FZ, FM):
    """the facts' lesson: fo [b, F, NT + 1] (logits for the binary three, standardised stacks after), G [b], FZ [b, F] (0 / 1; standardised
    stacks), FM [b, F] -> the summed mean loss of the goal's number and the goal-blind one (None without a known label)"""
    import torch
    F_ = torch.nn.functional
    pg = fo.gather(-1, G[:, None, None].expand(-1, fo.shape[1], 1)).squeeze(-1)
    pb = fo[..., -1]
    l_ = None
    for k_ in range(fo.shape[1]):
        m_ = FM[:, k_]
        if not bool(m_.any()):
            continue
        if k_ < FBIN:
            t_ = F_.binary_cross_entropy_with_logits(pg[m_, k_], FZ[m_, k_]) + F_.binary_cross_entropy_with_logits(pb[m_, k_], FZ[m_, k_])
        else:
            t_ = F_.smooth_l1_loss(pg[m_, k_], FZ[m_, k_]) + F_.smooth_l1_loss(pb[m_, k_], FZ[m_, k_])
        l_ = t_ if l_ is None else l_ + t_
    return l_


def learn2(params, opt, fwd, R, G, Z, OK, FZ=None, FM=None, epochs=2, mb=1024, gen=None, clip=1.0, decay=0.0, decay_w=None):
    """(2.2a) one rollout's lesson of an outlook, the facts with it: fwd(idx) -> (the kinds [b, K, NT + 1], the facts [b, F, NT + 1] or None)
    for the rows idx (a long tensor on the host); G [R] the goal he is on, Z [R, K] standardised labels, OK [R, K]; FZ, FM [R, F] the facts'
    labels (or None). (rule 11) decay: decoupled weight decay on decay_w (the term's last layer) after each step, lr x decay -> the last loss"""
    import torch
    R = int(R)
    if R == 0:
        return None
    G, Z, OK = G.long(), Z.detach().float(), OK.bool()
    loss_ = None
    with torch.enable_grad():
        for _ in range(int(epochs)):
            perm = torch.randperm(R, generator=gen) if gen is not None else torch.randperm(R)
            for i in range(0, R, int(mb)):
                j = perm[i:i + int(mb)]
                out_, fo_ = fwd(j)
                jd = j.to(out_.device)
                l_ = _loss(out_, G[jd], Z[jd], OK[jd])
                if fo_ is not None and FZ is not None:
                    lf_ = facts_loss(fo_, G[jd], FZ[jd].float(), FM[jd].bool())
                    if lf_ is not None:
                        l_ = lf_ if l_ is None else l_ + lf_
                if l_ is None:
                    continue
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(params, float(clip))
                opt.step()
                if decay > 0 and decay_w is not None:
                    with torch.no_grad():
                        for w_ in decay_w:
                            w_.mul_(1.0 - float(opt.param_groups[0]["lr"]) * float(decay))
                loss_ = float(l_)
    return loss_


def _auc(p, y):
    from control import auc as auc_
    import math as m_
    a_ = auc_(np.asarray(p, np.float64), np.asarray(y, np.float64))
    return None if m_.isnan(a_) else round(float(a_), 4)


def facts_block(fo_, g_, y_, k_):
    """the skill of one fact on a set of rows: fo_ [n, NT + 1] (that fact), g_ [n], y_ [n] (0 / 1 or standardised)"""
    import torch
    n_ = int(len(y_))
    if n_ < 2:
        return dict(rows=n_)
    pg_ = fo_.gather(1, g_[:, None]).squeeze(1).double()
    pb_ = fo_[:, -1].double()
    y_ = y_.double()
    if k_ < FBIN:
        pg_, pb_ = torch.sigmoid(pg_), torch.sigmoid(pb_)
        bc_ = float(((y_ - y_.mean()) ** 2).mean())
        bg_, bb_ = float(((pg_ - y_) ** 2).mean()), float(((pb_ - y_) ** 2).mean())
        return dict(rows=n_, rate=_q(float(y_.mean())), skill_goal=_q(1.0 - bg_ / bc_) if bc_ > 0 else None,
                    skill_blind=_q(1.0 - bb_ / bc_) if bc_ > 0 else None,
                    auc_goal=_auc(pg_.cpu().numpy(), y_.cpu().numpy()), auc_blind=_auc(pb_.cpu().numpy(), y_.cpu().numpy()))
    r2g_, r2b_ = _r2(pg_, y_), _r2(pb_, y_)
    return dict(rows=n_, r2_goal=_q(r2g_), r2_blind=_q(r2b_), gain=_q(r2g_ - r2b_) if (r2g_ is not None and r2b_ is not None) else None)


def facts_readouts(fo, G, FZ, FM, dec=None):
    """measured BEFORE the lesson: per fact, overall and at decision and stay readings"""
    res = {}
    for k_, nm_ in enumerate(FACTS[:fo.shape[1]]):
        m_ = FM[:, k_]
        d_ = dict(all=facts_block(fo[m_, k_], G[m_].long(), FZ[m_, k_], k_))
        if dec is not None:
            for s_nm, s_ in (("decision", m_ & dec.bool()), ("stay", m_ & ~dec.bool())):
                d_[s_nm] = facts_block(fo[s_, k_], G[s_].long(), FZ[s_, k_], k_)
        res[nm_] = d_
    return res


class FactStats:
    """the stacks' running mean and spread (the four after the binary three), the binary ones untouched"""

    def __init__(self, d=None):
        self.mean, self.var, self.n = np.zeros(len(FACTS)), np.ones(len(FACTS)), np.zeros(len(FACTS), np.int64)
        if d:
            self.mean[:], self.var[:], self.n[:] = d["mean"], d["var"], d["n"]

    def update(self, FY, FM):
        for k_ in range(FBIN, len(FACTS)):
            y_ = FY[FM[:, k_], k_].double()
            if len(y_) < 2:
                continue
            m_, v_ = float(y_.mean()), float(y_.var())
            if self.n[k_] == 0:
                self.mean[k_], self.var[k_] = m_, max(v_, 1e-12)
            else:
                self.mean[k_] += STAT_RATE * (m_ - self.mean[k_])
                self.var[k_] += STAT_RATE * (max(v_, 1e-12) - self.var[k_])
            self.n[k_] += len(y_)

    def standardise(self, FY):
        import torch
        out = FY.clone().float()
        for k_ in range(FBIN, len(FACTS)):
            out[:, k_] = (FY[:, k_].float() - float(self.mean[k_])) / float(math.sqrt(max(float(self.var[k_]), 1e-12)))
        return out

    def to_dict(self):
        return dict(facts=list(FACTS), mean=[float(x_) for x_ in self.mean], var=[float(x_) for x_ in self.var], n=[int(x_) for x_ in self.n])


# ------------------------------------------------------------------------------------------------------------------ (2.2a) the second value
def value_module(head=256, hid=128):
    """the head's silent second value (vw): the return of the win chance WITH the items at the head's gamma and lambda, from the head's state
    (detached). Linear -> ReLU -> Linear(1), its last layer at zero, a random stream of its own"""
    import torch
    import torch.nn as nn

    class VW(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED + 11)
                self.l1 = nn.Linear(int(head), int(hid))
                self.l2 = nn.Linear(int(hid), 1)
            with torch.no_grad():
                self.l2.weight.zero_()
                self.l2.bias.zero_()

        def forward(self, s):
            return self.l2(torch.relu(self.l1(s.float()))).squeeze(-1)
    return VW()


def value_learn(mod, opt, S, Y, epochs=2, mb=4096, gen=None, clip=1.0):
    """its lesson: S [R, head] the states, Y [R] the return targets; smooth L1 (as the head's own value) -> (the loss before, the loss after)"""
    import torch
    F_ = torch.nn.functional
    R = int(len(Y))
    if R == 0:
        return None, None
    with torch.no_grad():
        l0_ = float(F_.smooth_l1_loss(torch.cat([mod(S[i:i + 8192]) for i in range(0, R, 8192)]), Y.float()))
    with torch.enable_grad():
        for _ in range(int(epochs)):
            perm = torch.randperm(R, generator=gen) if gen is not None else torch.randperm(R)
            for i in range(0, R, int(mb)):
                j = perm[i:i + int(mb)].to(S.device)
                l_ = F_.smooth_l1_loss(mod(S[j]), Y[j].float())
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), float(clip))
                opt.step()
    with torch.no_grad():
        l1_ = float(F_.smooth_l1_loss(torch.cat([mod(S[i:i + 8192]) for i in range(0, R, 8192)]), Y.float()))
    return l0_, l1_

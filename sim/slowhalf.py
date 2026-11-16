"""2.1e (docs/runs/2.1/2.1e/CARD.md; owner 2026-11-15): the head's SLOW HALVES. "I'm going to go get mega" is the slow half; "every
200 ms I ask myself what else should I be doing, knowing that I've already committed" is the fast half (the head as it is).

Three slow halves live inside the strategy head (sim/head2.py add_slowhalf: the layers head2.slow.0/1/2.*, the buffers slow_mix, slow_back,
slow_pick, the layout's entry "slowhalf"). Each one:
  input     Linear(the head's state (size) + the part "goal" (the target he holds one-hot, its age, the held-draw flag) -> hid), ReLU
  memory    GRUCell(hid -> hid), a state per seat, zeros at the start and after a death
  plan      Linear(hid -> hid), ReLU, Linear(hid -> horizons x n_target) with the LAST layer at zero (even odds at the start)
made from a random stream of its own (the global stream untouched). It TICKS (reads its inputs, steps its memory once, rewrites its odds)
when any of:
  clock     its clock's number of head ticks (keep readings) have passed since its last tick (5, 10, 20: 1 s, 2 s, 4 s; --slow-clocks)
  trip end  the moment his held numbers are rolled anew (his target ended: reached, gone, a spawn; or "nothing" once a second): its FIRST
            frame (the held draw rolls again every frame until a reading takes the new target: one event, one tick; build decision of 11-15)
  change    a change of mind mid-trip: his target changed on the frame before without a new roll there (and not by a death)
Between ticks its state and odds are frozen. At a death its state goes to zeros and its odds to even.

What plays (only the half slow_pick names; the other two are silent to the end, their readouts go on):
  channel 2, the pull's source   the pull's log-odds = (1 - slow_mix) x log(max(fast plan's odds, floor)) + slow_mix x log(max(the slow half's,
                                 floor)) of the same horizon; at slow_mix 0 the 2.1d pull to the bit (pull_vec's own sums)
  channel 3, the read-back       the head's input part "slowback": slow_back x the slow half's state (128), read at the head's tick; its
                                 weights start at zero (tools/slow_init.py add), the head's PPO trains them; the state is stored as played
                                 (a constant for the learner: no gradient into the slow half from PPO)
What each half learns from: ONLY the fast plan's lesson (sim/slowplan.py labels' semantics): at each of its ticks, forecast his own fast target
odds BEFORE any pull, averaged over the next h keep readings, per horizon; soft-label cross-entropy; the gradient through its own memory over
the ticks of a rollout (the state at the rollout's start the stored one, detached); its own Adam (the checkpoint's top-level "slow_opt"); the
decoupled decay of rule 11 on each half's last layer (live H2_L2). No pay, no copy of the fast plan, nothing from the pros (rules 12, 13).
"""
import math

import numpy as np

VERSION = 1
SEED = 6161
CAUSES = ("clock", "trip_end", "change")
CB_TE, CB_CH = 8, 16                                         # a row's cause bits: 1 << k the clock of half k; 8 a trip's end; 16 a change of mind


def layout(head=256, goal=19, n_target=17, hid=128, horizons=(10, 25), clocks=(5, 10, 20)):
    hz = tuple(int(h_) for h_ in horizons)
    ck = tuple(int(c_) for c_ in clocks)
    assert len(hz) >= 1 and all(h_ >= 1 for h_ in hz), "slowhalf: horizons of at least one head tick"
    assert 1 <= len(ck) <= 3 and all(c_ >= 1 for c_ in ck), "slowhalf: one to three clocks of at least one head tick"
    return dict(version=VERSION, head=int(head), goal=int(goal), n_target=int(n_target), hid=int(hid), horizons=list(hz), clocks=list(ck),
                inp=int(head) + int(goal), out=len(hz) * int(n_target))


def make_half(L, k):
    """one slow half (its own random stream: SEED + 101 k; the global one untouched), its plan's last layer at zero"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "slowhalf: layout version {} expected".format(VERSION)

    class Half(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED + 101 * int(k))
                self.inp = nn.Linear(int(L["inp"]), int(L["hid"]))
                self.gru = nn.GRUCell(int(L["hid"]), int(L["hid"]))
                self.l2 = nn.Linear(int(L["hid"]), int(L["hid"]))
                self.l3 = nn.Linear(int(L["hid"]), int(L["out"]))
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()
            self.nh = len(L["horizons"])
            self.ni = int(L["n_target"])

        def step(self, x, s):
            """one tick: x [B, inp] (the head's state, the goal), s [B, hid] -> the state after"""
            return self.gru(torch.relu(self.inp(x.float())), s.float())

        def forward(self, s):
            """s [B, hid] -> its plan's logits [B, horizons, n_target]"""
            return self.l3(torch.relu(self.l2(s.float()))).view(-1, self.nh, self.ni)
    return Half()


def make_halves(L):
    import torch.nn as nn
    return nn.ModuleList([make_half(L, k_) for k_ in range(len(L["clocks"]))])


def pull_mix(fast_h, slow_h, g, floor, mix):
    """(torch) the pull on the target's logits [B, n_target] with its source mixed: g x ((1 - mix) x log(max(fast, floor)) + mix x
    log(max(slow, floor))), rounded to half precision. mix: a number or [B, 1]; a number 0 (or slow_h None): head2.pull_vec's own sums"""
    import torch
    import head2 as head2_
    if slow_h is None or (not torch.is_tensor(mix) and float(mix) <= 0.0):
        return head2_.pull_vec(fast_h, g, floor)
    lf = torch.log(fast_h.float().clamp(min=float(floor)))
    ls = torch.log(slow_h.float().clamp(min=float(floor)))
    return (g * ((1.0 - mix) * lf + mix * ls)).half().float()


def np_pull_mix(fast_h, slow_h, g, floor, mix):
    """pull_mix() in numpy (the checks' player and the plugin: the same sums); mix 0 or slow_h None: head2.np_pull's own"""
    import head2 as head2_
    if slow_h is None or float(mix) <= 0.0:
        return head2_.np_pull(fast_h, g, floor)
    lf = np.log(np.maximum(np.asarray(fast_h, np.float32), np.float32(floor)))
    ls = np.log(np.maximum(np.asarray(slow_h, np.float32), np.float32(floor)))
    m = np.float32(mix)
    return (np.float32(g) * ((np.float32(1.0) - m) * lf + m * ls)).astype(np.float16).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------- the trainer's state
class State:
    """every seat's slow halves in the rollout (his seats and the league's: each plays its own network's halves). s [K, n, hid], odds
    [K, n, horizons, n_target], cnt [K, n] keep readings since its last tick, rf [K, n] a reset since its last tick, chg [n] a change of mind
    on the frame before (set after the simulators' step: tick at the next frame)"""

    def __init__(self, n, L, dev):
        import torch
        self.L = L
        K, H, nh, ni = len(L["clocks"]), int(L["hid"]), len(L["horizons"]), int(L["n_target"])
        self.K, self.ni = K, ni
        self.clocks = torch.tensor([int(c_) for c_ in L["clocks"]], device=dev)[:, None]
        self.s = torch.zeros(K, n, H, device=dev)
        self.odds = torch.full((K, n, nh, ni), 1.0 / ni, device=dev)
        self.cnt = torch.zeros(K, n, dtype=torch.long, device=dev)
        self.rf = torch.ones(K, n, dtype=torch.bool, device=dev)
        self.chg = torch.zeros(n, dtype=torch.bool, device=dev)
        self.frp = torch.zeros(n, dtype=torch.bool, device=dev)

    def causes(self, reading, fr):
        """this frame's ticks before anything reads the halves: reading (a python bool: a keep reading, t % every == 0) counts the clocks; fr
        [n] the roll moment (the held draw's: his target ended, or "nothing" once a second): a trip's end ticks on its FIRST frame (the roll
        repeats every frame until a reading takes the new target: one event, one tick); the change of mind of the frame before -> (tick [K, n]
        bool, the rows' cause bits [n] uint8: 1 << k the clock of half k, 8 a trip's end, 16 a change of mind)"""
        import torch
        if reading:
            self.cnt += 1
            clock = self.cnt >= self.clocks
        else:
            clock = torch.zeros_like(self.rf)
        fr = fr.bool()
        te = fr & ~self.frp
        self.frp = fr
        ev = te | self.chg
        tick = clock | ev[None]
        cb = (clock.to(torch.uint8) * torch.tensor([1 << k_ for k_ in range(self.K)], dtype=torch.uint8, device=clock.device)[:, None]).sum(0, dtype=torch.uint8)
        cb = cb + te.to(torch.uint8) * CB_TE + self.chg.to(torch.uint8) * CB_CH
        self.chg = torch.zeros_like(self.chg)
        return tick, cb

    def tick(self, mine_halves, opp_halves, x, tick, mine):
        """the ticks: x [n, inp] each seat's inputs (its own head's state, the goal); mine [n] his seats (the rest: the league's, by
        opp_halves; None: a league network without halves: its seats' halves stay as they are) -> per half (rows [r], their odds before
        [r, horizons, n_target], a reset since their last tick [r])"""
        import torch
        out = []
        with torch.no_grad():
            for k_ in range(self.K):
                out.append(self._tick_one(k_, mine_halves, opp_halves, x, tick, mine))
        return out

    def _tick_one(self, k_, mine_halves, opp_halves, x, tick, mine):
        import torch
        r_ = torch.nonzero(tick[k_], as_tuple=True)[0]
        old_ = self.odds[k_, r_].clone()
        rf_ = self.rf[k_, r_].clone()
        if len(r_):
            for hv_, sel_ in ((mine_halves, mine[r_]), (opp_halves, ~mine[r_])):
                rr_ = r_[sel_]
                if hv_ is None or not len(rr_):
                    continue
                s_ = hv_[k_].step(x[rr_], self.s[k_, rr_])
                self.s[k_, rr_] = s_
                self.odds[k_, rr_] = torch.softmax(hv_[k_](s_), -1)
            self.cnt[k_, r_] = 0
            self.rf[k_, r_] = False
        return r_, old_, rf_

    def reset(self, d):
        """a death (the trainer's done): zeros, even odds, the clocks from naught, a reset marked"""
        m_ = d > 0
        self.s[:, m_] = 0.0
        self.odds[:, m_] = 1.0 / self.ni
        self.cnt[:, m_] = 0
        self.rf[:, m_] = True
        self.frp = self.frp & ~m_                            # (the spawn's roll: a trip's end of its own, its first frame ticks)

    def pick_rows(self, which, pm, po, mine):
        """[n, ...] of `which` (self.s or self.odds) of each seat's picked half: pm his network's pick, po the league's"""
        import torch
        a_, b_ = which[int(pm)], which[int(po)]
        sh_ = (-1,) + (1,) * (a_.dim() - 1)
        return torch.where(mine.view(sh_), a_, b_)


# ------------------------------------------------------------------------------------------------------------- the learner's lesson
def labels_at(pf, done, jj, ii, horizons, bk):
    """slowplan.labels' semantics at given rows: pf [J, N, NI] his fast odds (before the pull) at each keep reading; done [T, N]; jj [R] the
    keep reading of each row (its tick's frame // bk), ii [R] its seat -> (Y [R, horizons, NI] the mean of his fast odds over readings j+1 ..
    j+h, ok [R, horizons]: j + h inside the rollout and no round ended on frames j*bk .. (j+h)*bk)"""
    import torch
    J, N, NI = pf.shape
    cs = torch.cat([torch.zeros(1, N, device=done.device), torch.cumsum((done > 0).float(), 0)], 0)
    cp = torch.cat([torch.zeros(1, N, NI, device=pf.device), torch.cumsum(pf.float(), 0)], 0)
    jj, ii = jj.long(), ii.long()
    Y, OK = [], []
    for h in horizons:
        h = int(h)
        jc = (jj + h).clamp(max=J - 1)
        valid = (jj + h) <= (J - 1)
        clean = (cs[jc * bk + 1, ii] - cs[jj * bk, ii]) == 0
        Y.append((cp[jc + 1, ii] - cp[jj + 1, ii]) / float(h))
        OK.append(valid & clean)
    return torch.stack(Y, 1), torch.stack(OK, 1)


def pack(seat, t, nseat):
    """the rows of one half as sequences: seat [r] (0 .. nseat - 1), t [r] their frames -> P [Kmax, nseat] the row of each seat's q-th tick in
    time order (-1: none)"""
    import torch
    if len(seat) == 0:
        return torch.full((0, nseat), -1, dtype=torch.long, device=seat.device)
    key = seat.long() * (int(t.max()) + 1) + t.long()
    order = torch.argsort(key)
    so = seat.long()[order]
    cnt = torch.bincount(so, minlength=nseat)
    start = torch.cumsum(cnt, 0) - cnt
    rank = torch.arange(len(so), device=seat.device) - start[so]
    P = torch.full((int(cnt.max()), nseat), -1, dtype=torch.long, device=seat.device)
    P[rank, so] = order
    return P


def run_seq(half, s0, X, Z, M):
    """a chunk of seats through their ticks: s0 [c, hid] the state at the rollout's start (detached), X [Q, c, inp], Z [Q, c] a reset before
    the tick, M [Q, c] a tick there -> the logits at each tick [Q, c, horizons, NI] (where M; the gradient through the memory)"""
    import torch
    s = s0.detach().float()
    out = []
    for q_ in range(X.shape[0]):
        m_ = M[q_][:, None]
        s_n = half.step(X[q_], s * (~Z[q_]).float()[:, None])
        s = torch.where(m_, s_n, s)
        out.append(half(s))
    return torch.stack(out, 0)


def _chunk_rows(P, rows_k, cs):
    """the chunk's sequences: P [Q, nseat], rows_k [r] the half's rows in the rollout's row list, cs the chunk's seats -> (Pc [Q', c], M [Q', c],
    rows [Q', c] in the rollout's row list) with the empty tail cut"""
    import torch
    Pc = P[:, cs]
    M = Pc >= 0
    q_ = int(M.any(1).nonzero().max()) + 1 if bool(M.any()) else 0
    Pc, M = Pc[:q_], M[:q_]
    return Pc, M, rows_k[Pc.clamp(min=0)]


def lesson_loss(lq, Y, OK):
    """each horizon's mean soft-label cross-entropy over its valid rows, summed over the horizons; None without a valid row"""
    tot = None
    for h_ in range(Y.shape[1]):
        m_ = OK[:, h_]
        if not bool(m_.any()):
            continue
        ce = -(Y[m_, h_].float() * lq[m_, h_]).sum(-1).mean()
        tot = ce if tot is None else tot + ce
    return tot


def forward_rows(half, k, s0, P, rows_k, X, Z, chunk=2048):
    """(no gradient) the half's logits at each of its rows -> [r, horizons, NI] in the order of rows_k"""
    import torch
    nseat = P.shape[1]
    out = torch.zeros(len(rows_k), half.nh, half.ni, device=X.device)
    with torch.no_grad():
        for c0 in range(0, nseat, chunk):
            cs = torch.arange(c0, min(nseat, c0 + chunk), device=X.device)
            Pc, M, rr = _chunk_rows(P, rows_k, cs)
            if not len(Pc):
                continue
            Xc = X[rr].float() * M[..., None].float()
            Zc = (((Z[rr].long() >> k) & 1) > 0) & M
            lg = run_seq(half, s0[cs], Xc, Zc, M)
            out[Pc[M]] = lg[M]
    return out


def learn(half, opt, k, s0, P, rows_k, X, Z, Y, OK, epochs=2, chunk=1024, gen=None, clip=1.0, decay=0.0):
    """one rollout's lesson of half k: the seats in chunks (a random order of its own stream), each chunk's sequences through the memory with
    the gradient (BPTT over the rollout's ticks), its own Adam; after each step the decay of its plan's last layer (rule 11). -> the last loss"""
    import torch
    nseat = P.shape[1]
    if nseat == 0 or P.shape[0] == 0:
        return None
    loss_ = None
    with torch.enable_grad():
        for _ in range(int(epochs)):
            perm = torch.randperm(nseat, generator=gen) if gen is not None else torch.randperm(nseat)
            perm = perm.to(X.device)
            for c0 in range(0, nseat, int(chunk)):
                cs = perm[c0:c0 + int(chunk)]
                Pc, M, rr = _chunk_rows(P, rows_k, cs)
                if not len(Pc):
                    continue
                Xc = X[rr].float() * M[..., None].float()
                Zc = (((Z[rr].long() >> k) & 1) > 0) & M
                lg = run_seq(half, s0[cs], Xc, Zc, M)
                rows_ = rr[M]
                l_ = lesson_loss(torch.log_softmax(lg[M], -1), Y[rows_], OK[rows_])
                if l_ is None:
                    continue
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(half.parameters(), float(clip))
                opt.step()
                if decay > 0:                                    # (rule 11: the pull's log-odds a sum of two learned parts' outputs)
                    with torch.no_grad():
                        half.l3.weight.mul_(1.0 - float(opt.param_groups[0]["lr"]) * float(decay))
                loss_ = float(l_)
    return loss_


def readouts(lq, Y, OK, Pf, Pn, horizons):
    """BEFORE the lesson (held out): lq [r, horizons, NI] the half's log-odds at its ticks, Y / OK the labels, Pf [r, horizons, NI] the fast
    plan's held odds at the same frames, Pn [r, NI] his own fast odds at the reading -> {"h<ticks>": n, kl and top-1 of the slow half, the fast
    plan, his odds now}"""
    import torch
    fin = lambda v: round(v, 5) if math.isfinite(v) else None    # noqa: E731
    out = {}
    with torch.no_grad():
        for h_i, h_ in enumerate(horizons):
            m_ = OK[:, h_i]
            n_ = int(m_.sum())
            if n_ == 0:
                out["h{}".format(h_)] = dict(n=0)
                continue
            y_ = Y[m_, h_i].float()
            ent = float(-(y_ * torch.log(y_.clamp(min=1e-12))).sum(-1).mean())
            ce_s = float(-(y_ * lq[m_, h_i]).sum(-1).mean())
            pf_ = Pf[m_, h_i].float()
            ce_f = float(-(y_ * torch.log(pf_.clamp(min=1e-6))).sum(-1).mean())
            pn_ = Pn[m_].float()
            ce_n = float(-(y_ * torch.log(pn_.clamp(min=1e-6))).sum(-1).mean())
            yt = y_.argmax(-1)
            out["h{}".format(h_)] = dict(n=n_, kl_slow=fin(ce_s - ent), kl_fast=fin(ce_f - ent), kl_now=fin(ce_n - ent),
                                         top1_slow=round(float((lq[m_, h_i].argmax(-1) == yt).float().mean()), 4),
                                         top1_fast=round(float((pf_.argmax(-1) == yt).float().mean()), 4),
                                         top1_now=round(float((pn_.argmax(-1) == yt).float().mean()), 4))
    return out


# ------------------------------------------------------------------------------------------------------------- numpy (the readers)
def np_params(W, k):
    """half k's arrays from the head's weights (head2.params_np: names without "head2."), None without them"""
    ks = ("inp.weight", "inp.bias", "gru.weight_ih", "gru.bias_ih", "gru.weight_hh", "gru.bias_hh", "l2.weight", "l2.bias", "l3.weight", "l3.bias")
    pre = "slow.{}.".format(int(k))
    if not all(pre + k_ in W for k_ in ks):
        return None
    return {k_: np.asarray(W[pre + k_], np.float32) for k_ in ks}


def np_step(P, x, s):
    """Half.step in numpy: x [B, inp], s [B, hid] -> [B, hid] float32 (torch's GRUCell: gates r, z, n)"""
    x = np.asarray(x, np.float32)
    s = np.asarray(s, np.float32)
    H = s.shape[1]
    a = np.maximum(x @ P["inp.weight"].T + P["inp.bias"], 0.0)
    gi = a @ P["gru.weight_ih"].T + P["gru.bias_ih"]
    gh = s @ P["gru.weight_hh"].T + P["gru.bias_hh"]
    r = 1.0 / (1.0 + np.exp(-(gi[:, :H] + gh[:, :H])))
    z = 1.0 / (1.0 + np.exp(-(gi[:, H:2 * H] + gh[:, H:2 * H])))
    n = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    return ((1.0 - z) * n + z * s).astype(np.float32)


def np_odds(P, nh, ni, s):
    """the plan's odds [B, nh, ni] float32 from the state s [B, hid]"""
    h = np.maximum(np.asarray(s, np.float32) @ P["l2.weight"].T + P["l2.bias"], 0.0)
    z = (h @ P["l3.weight"].T + P["l3.bias"]).astype(np.float64).reshape(len(h), nh, ni)
    z = np.exp(z - z.max(-1, keepdims=True))
    return (z / z.sum(-1, keepdims=True)).astype(np.float32)


class NpState:
    """the readers' (test_suite.Policy, plugins/netpass.py) one slow half (the picked one) of B seats, the trainer's State's rules: a tick at
    its clock (keep readings counted, kr), at the roll moment's first frame (fr) and at a change of mind (his target changed on the frame before without a
    new roll there and not by a clear); between ticks frozen; a clear: zeros, even odds"""

    def __init__(self, L, k, P):
        self.L, self.k, self.P = L, int(k), P
        self.clock = int(L["clocks"][int(k)])
        self.nh, self.ni, self.H, self.S = len(L["horizons"]), int(L["n_target"]), int(L["hid"]), int(L["head"])
        self.s = self.odds = self.cnt = self.prev_t = self.prev_fr = self.clr = None
        self.last = None                                     # (this frame's ticks and causes: tick, clock, roll, change)

    def ensure(self, B):
        if self.s is None or len(self.s) != B:
            self.s = np.zeros((B, self.H), np.float32)
            self.odds = np.full((B, self.nh, self.ni), 1.0 / self.ni, np.float32)
            self.cnt = np.zeros(B, np.int64)
            self.prev_t, self.prev_fr, self.clr = None, np.zeros(B, bool), np.zeros(B, bool)

    def clear(self, rows):
        if self.s is None:
            return
        r = slice(None) if rows is None else rows
        self.s, self.odds = self.s.copy(), self.odds.copy()
        self.s[r] = 0.0
        self.odds[r] = np.float32(1.0 / self.ni)
        self.cnt[r] = 0
        self.clr[r] = True

    def step(self, tgt, fr, kr, h2s, goal):
        """this frame's ticks (before the pull and the head's tick): tgt [B] his target in the keep rows, fr [B] the roll moment, kr [B] a keep
        reading, h2s [B, >= head] the head's state its outputs read, goal [B, goal] the part "goal" -> the tick mask"""
        B = len(tgt)
        self.ensure(B)
        tgt = np.asarray(tgt).astype(np.int64)
        fr = np.asarray(fr, bool)
        kr = np.asarray(kr, bool) if kr is not None else np.zeros(B, bool)
        chg = (tgt != self.prev_t) & ~self.prev_fr & ~self.clr if self.prev_t is not None else np.zeros(B, bool)
        self.cnt = self.cnt + kr.astype(np.int64)
        clock = kr & (self.cnt >= self.clock)
        te = fr & ~(self.prev_fr & ~self.clr)               # (a trip's end ticks on its first frame; after a clear the spawn's roll is a new one)
        tick = clock | te | chg
        if tick.any():
            r = np.nonzero(tick)[0]
            x = np.concatenate([np.asarray(h2s, np.float32)[r, :self.S], np.asarray(goal, np.float32)[r]], 1)
            s_ = np_step(self.P, x, self.s[r])
            self.s, self.odds = self.s.copy(), self.odds.copy()
            self.s[r] = s_
            self.odds[r] = np_odds(self.P, self.nh, self.ni, s_)
            self.cnt[r] = 0
        self.prev_t, self.prev_fr = tgt.copy(), fr.copy()
        self.clr = np.zeros(B, bool)
        self.last = (tick, clock, te, chg)
        return tick

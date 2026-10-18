"""The head (v0.4, docs/v0.4/BUILD_v0.4.md section 1; CANDIDATE_v0.4.md): the strategy side beside his hands. A bigger cousin
of the slow memory (sim/slowmem.py): a GRU of `size` that ticks once every `every` frames, with a store of the last three
minutes read by attention, and a plan that it sends to the hands.

What it is
  At a tick (frame t with (g + 1) % every == 0, g the global frame count, as slowmem) it
    1. ages every written slot of its store by one tick,
    2. reads the store: 4-head attention queried by the slow state of the tick before (s), keys and values from
       [slot ; 8 age features]; a store with no slots reads zeros,
    3. steps: u = [his fast memory h after frame t (fast) ; the mean of the encoder's output e over the tick's frames (enc) ;
       the read (read) ; the tick's events (ev)], p = tanh(inp(u)), s = GRUCell(p, s),
    4. makes the plan: plan = tanh(plan_out(s)), held until the next tick,
    5. writes, every `write_every` of its ticks since it was cleared, one slot: write([s ; mean e ; events]) into a ring of
       `slots` slots (the oldest goes).
  The plan reaches the hands through head.plan_in (Linear plan -> enc, zeros at the start): his fast GRU reads
  x_fast = e + plan_in(plan) in place of e (its own shape is unchanged). The plan of a tick at frame t is read from frame
  t + 1 on (frame t's own fast step is done before the tick).
  Outputs, all from s: target (added to his intention's logits) and way (added to his way's logits), from the slow state of
  the moment, so from the tick's frame on and held to the next tick; v_short, v_long (values on the ticks), win (5 bands of
  the final score margin), aux.* (the guessing questions: added to the hands' answers, held as target is).
  target, way, win, aux and plan_in start at zero: a network given the part answers exactly as before.
  A reset (the trainer's done) clears s, the plan, the running mean, the store and its tick count (as slowmem: from the
  frame after; target and way read target(0) = its bias from there).

How it is taught (the trainer, sim/train_duel_rnn.py --head)
  As slowmem: a ring of the tick inputs u of the last `ring` ticks before the rollout (fp16, host), the slow GRU re-run over
  it under the gradient; the store's slots from before the rollout are stored numbers (no gradient), the slots written in
  the rollout are under it. Because the plan feeds the fast GRU, the learning step runs the fast GRU in segments of `every`
  frames (one fused call each, seq()), a head tick between.

State in the trainer (State, one for his seats and one for the league's): s, plan, acc (the encoder's sum since the tick),
cnt (frames in it), slots [n, slots, slot], age1 [n, slots] (the slot's age in ticks + 1; 0: never written since the clear),
ticks (the head's ticks since the clear: a slot is written when ticks % write_every == 0, at (ticks / write_every - 1) %
slots), rs (a reset since the last tick).

Numpy only at the top level (the game server imports this file); torch is imported inside the torch functions. The numpy
side (np_state_width, np_tick) is lane serve's (BUILD_v0.4.md section 5).
"""
import json
import math

import numpy as np

VERSION = 1
N_AGE = 8                                                    # age features of a slot
AGE_PERIODS = (16.0, 128.0, 1024.0)                          # ... their sine and cosine periods in ticks


def layout(every=8, size=1024, inp=768, fast=512, enc=256, ev=32, plan=256, slots=224, write_every=4, slot=128, read=256,
           read_heads=4, ring=96, n_target=17, n_way=3, win_bands=5, chrono=96, aux=None, store_half=0):
    """the part's shape and timing; kept in a checkpoint as "head" and in policy.npz as JSON text. aux: {question: outputs}
    (the hands' --aux layers it answers beside them; {} none). chrono: as slowmem (the slow GRU's longest starting time
    scale in ticks; 0: PyTorch's own start). store_half: 1: a slot is written at half precision (rounded to float16 as it is
    written, in torch and numpy alike; the trainer keeps the store at half precision on the card, half its memory)"""
    assert read % read_heads == 0, (read, read_heads)
    return dict(version=VERSION, every=int(every), size=int(size), inp=int(inp), fast=int(fast), enc=int(enc), ev=int(ev),
                plan=int(plan), slots=int(slots), write_every=int(write_every), slot=int(slot), read=int(read),
                read_heads=int(read_heads), ring=int(ring), n_target=int(n_target), n_way=int(n_way), win_bands=int(win_bands),
                chrono=int(chrono), aux={str(k): int(v) for k, v in (aux or {}).items()}, store_half=int(store_half))


def describe(lay):
    return ("head: {} wide, a tick every {} frames ({:.2f} s), squeeze {} from {} = {} + {} + {} + {}, plan {}, store {} x {} "
            "(a slot every {} ticks: {:.1f} min), read {} in {} heads, taught over {} ticks ({:.1f} s), aux {}").format(
        lay["size"], lay["every"], lay["every"] * 0.025, lay["inp"], u_width(lay), lay["fast"], lay["enc"], lay["read"], lay["ev"],
        lay["plan"], lay["slots"], lay["slot"], lay["write_every"], lay["slots"] * lay["write_every"] * lay["every"] * 0.025 / 60.0,
        lay["read"], lay["read_heads"], lay["ring"], lay["ring"] * lay["every"] * 0.025, "+".join(sorted(lay.get("aux", {}))) or "none")


def as_layout(x):
    """a layout from a checkpoint's dict, a policy.npz's text, a JSON string or a JSON file's path; "default": layout()"""
    if x is None:
        return None
    if isinstance(x, dict):
        return x
    x = str(x)
    if x == "default":
        return layout()
    if x.lstrip().startswith("{"):
        return json.loads(x)
    with open(x) as f_:
        return json.load(f_)


def u_width(lay):
    """the tick's input: h (fast) ; mean e (enc) ; the read (read) ; events (ev)"""
    return int(lay["fast"]) + int(lay["enc"]) + int(lay["read"]) + int(lay["ev"])


def age_features_np(age, lay):
    """a slot's age in ticks (>= 0) -> its 8 features: age / horizon, log(1 + age) / log(1 + horizon), and sine and cosine at
    periods of 16, 128 and 1024 ticks (horizon: the store's length in ticks, slots x write_every)"""
    A = float(lay["slots"] * lay["write_every"])
    a = np.asarray(age, np.float32)
    f = [a / A, np.log1p(a) / math.log1p(A)]
    for P in AGE_PERIODS:
        w = np.float32(2.0 * math.pi / P)
        f += [np.sin(a * w), np.cos(a * w)]
    return np.stack(f, -1).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------------ torch
def _age_features(age, lay):
    """the same in torch (age: a float tensor)"""
    import torch
    A = float(lay["slots"] * lay["write_every"])
    f = [age / A, torch.log1p(age) / math.log1p(A)]
    for P in AGE_PERIODS:
        w = 2.0 * math.pi / P
        f += [torch.sin(age * w), torch.cos(age * w)]
    return torch.stack(f, -1)


def make_module(lay, seed=None):
    """the part as a torch module. Layers: inp (u -> inp), gru (nn.GRU inp -> size), plan_out (size -> plan), plan_in (plan ->
    enc, zeros), write (size + enc + ev -> slot), rq (size -> read), rk, rv (slot + 8 -> read), ro (read -> read), target,
    way, win (zeros), v_short, v_long, aux.<question> (zeros). seed: its own random stream (the converter), None: the global
    one (the trainer)"""
    import torch
    import torch.nn as nn

    class Head(nn.Module):
        def __init__(self):
            super().__init__()
            S_, C_ = lay["size"], lay["slot"]
            self.inp = nn.Linear(u_width(lay), lay["inp"])
            self.gru = nn.GRU(lay["inp"], S_)
            self.plan_out = nn.Linear(S_, lay["plan"])
            self.plan_in = nn.Linear(lay["plan"], lay["enc"])
            self.write = nn.Linear(S_ + lay["enc"] + lay["ev"], C_)
            self.rq = nn.Linear(S_, lay["read"])
            self.rk = nn.Linear(C_ + N_AGE, lay["read"])
            self.rv = nn.Linear(C_ + N_AGE, lay["read"])
            self.ro = nn.Linear(lay["read"], lay["read"])
            self.target = nn.Linear(S_, lay["n_target"])
            self.way = nn.Linear(S_, lay["n_way"])
            self.win = nn.Linear(S_, lay["win_bands"])
            self.v_short = nn.Linear(S_, 1)
            self.v_long = nn.Linear(S_, 1)
            self.aux = nn.Module()                           # (not a ModuleDict: "items" is a name of its own there)
            for k_, n_ in sorted(lay.get("aux", {}).items()):
                setattr(self.aux, k_, nn.Linear(S_, int(n_)))
            for l_ in [self.plan_in, self.target, self.way, self.win] + list(self.aux.children()):
                nn.init.zeros_(l_.weight)                    # the exact start: he answers as without the part
                nn.init.zeros_(l_.bias)
            tmax = int(lay.get("chrono", 0))
            if tmax > 1:                                     # as slowmem: the update gate starts near 1 for long time scales
                with torch.no_grad():
                    tau = 1.0 + torch.rand(S_) * (tmax - 1.0)
                    self.gru.bias_ih_l0[S_:2 * S_] = torch.log((tau - 1.0).clamp(min=1e-3))
                    self.gru.bias_hh_l0[S_:2 * S_] = 0.0

    if seed is None:
        return Head()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return Head()


def cell(mod, p, s):
    """one step of the slow GRU (the same weights as the fused nn.GRU)"""
    import torch
    g = mod.gru
    return torch.gru_cell(p, s, g.weight_ih_l0, g.weight_hh_l0, g.bias_ih_l0, g.bias_hh_l0)


def read(mod, lay, s, slots, age1, stats=None):
    """the store's read for B players: s [B, size] (the query: the slow state of the tick before), slots [B, S, slot],
    age1 [B, S] (age + 1; 0: empty) -> [B, read] (zeros where the store is empty). Worked without the keys and values of
    every slot: the score is q.(Wk [slot ; age] + bk), split into its slot and age parts, and the value part is the weighted
    sum of [slot ; age] put through Wv (the same numbers, a fraction of the memory). stats: a list that gets [the sum of the
    attention's entropy over heads and players with a slot, those players x heads, the slots they had]"""
    import torch
    B, S, C = slots.shape
    if slots.dtype != s.dtype:                               # (store_half) worked at full precision, a few thousand players at a time
        CH = 2048                                            # (the whole store at full precision at once would cost what halving saved)
        if B > CH:
            return torch.cat([read(mod, lay, s[c0:c0 + CH], slots[c0:c0 + CH], age1[c0:c0 + CH], stats) for c0 in range(0, B, CH)])
        slots = slots.to(s.dtype)
    Hh, R = int(lay["read_heads"]), int(lay["read"])
    dh = R // Hh
    valid = age1 > 0
    anyv = valid.any(1)
    af = _age_features((age1 - 1.0).clamp(min=0.0), lay)                 # [B, S, 8]
    q = mod.rq(s).view(B, Hh, dh)
    Wk = mod.rk.weight.view(Hh, dh, C + N_AGE)
    qk = torch.einsum("bhd,hdc->bhc", q, Wk)                             # q put into [slot ; age] space
    sc = (torch.einsum("bhc,bsc->bhs", qk[..., :C], slots) + torch.einsum("bhc,bsc->bhs", qk[..., C:], af)
          + (q * mod.rk.bias.view(Hh, dh)).sum(-1)[..., None]) / math.sqrt(dh)
    sc = sc.masked_fill(~valid[:, None, :], -1e9)
    a = torch.softmax(sc, -1) * anyv[:, None, None].to(sc.dtype)        # (an empty store: no weights at all)
    ws = torch.einsum("bhs,bsc->bhc", a, slots)
    wa = torch.einsum("bhs,bsc->bhc", a, af)
    Wv = mod.rv.weight.view(Hh, dh, C + N_AGE)
    vh = (torch.einsum("bhc,hdc->bhd", ws, Wv[..., :C]) + torch.einsum("bhc,hdc->bhd", wa, Wv[..., C:])
          + mod.rv.bias.view(Hh, dh) * a.sum(-1)[..., None])
    out = mod.ro(vh.reshape(B, R)) * anyv[:, None].to(sc.dtype)
    if stats is not None:
        with torch.no_grad():
            ent = -(a * torch.log(a.clamp(min=1e-12))).sum(-1)            # [B, heads]
            stats.append(torch.stack([(ent * anyv[:, None]).sum(), anyv.sum() * float(Hh), (valid.sum(1) * anyv).sum()]).double())
    return out


def tick(mod, lay, s, slots, age1, ticks, h, mean, ev, stats=None):
    """one tick for B players (their store already cleared where a reset came): -> (s, plan, slots, age1, ticks, u). The
    same function for live() and seq(): the same numbers"""
    import torch
    age1 = torch.where(age1 > 0, age1 + 1.0, age1)
    ticks = ticks + 1.0
    r = read(mod, lay, s, slots, age1, stats)
    u = torch.cat([h, mean, r, ev], 1)
    s = cell(mod, torch.tanh(mod.inp(u)), s)
    plan = torch.tanh(mod.plan_out(s))
    W, S = int(lay["write_every"]), int(lay["slots"])
    tk = torch.round(ticks).long()
    wr = (tk % W) == 0
    if bool(wr.any()):
        pos = (tk // W - 1) % S
        hit = (torch.arange(S, device=s.device)[None, :] == pos[:, None]) & wr[:, None]       # [B, S]
        new = mod.write(torch.cat([s, mean, ev], 1))
        if lay.get("store_half"):                            # (store_half) the slot as the store keeps it; the gradient as if not rounded
            new = new + (new.half().to(new.dtype) - new).detach()
        slots = torch.where(hit[..., None], new[:, None, :].to(slots.dtype), slots)
        age1 = torch.where(hit, torch.ones_like(age1), age1)
    return s, plan, slots, age1, ticks, u


class State:
    """the head's live state for n players (the trainer's rollout; one for him, one for the league's opponent)"""

    def __init__(self, n, lay, dev):
        import torch
        self.lay, self.K = lay, int(lay["every"])
        self.s = torch.zeros(n, lay["size"], device=dev)
        self.plan = torch.zeros(n, lay["plan"], device=dev)
        self.acc = torch.zeros(n, lay["enc"], device=dev)
        self.cnt = torch.zeros(n, device=dev)
        self.slots = torch.zeros(n, lay["slots"], lay["slot"], device=dev, dtype=torch.float16 if lay.get("store_half") else torch.float32)
        self.age1 = torch.zeros(n, lay["slots"], device=dev)
        self.ticks = torch.zeros(n, device=dev)
        self.rs = torch.ones(n, device=dev)                  # a reset since the last tick (a fresh state counts as one: its plan is 0)
        self.g = 0                                           # the global frame count (ticks: (g + 1) % K == 0)
        self.ticked, self.u, self.r_tick, self.stats = False, None, None, None

    def reset(self, d):
        """after a frame: d [n] 1 where his memory is cleared (done). Out of place (peek() copies share the tensors)"""
        import torch
        if not bool((d > 0).any()):
            return
        k = 1.0 - d
        self.s = self.s * k[:, None]
        self.plan = self.plan * k[:, None]
        self.acc = self.acc * k[:, None]
        self.cnt = self.cnt * k
        self.slots = self.slots * k[:, None, None].to(self.slots.dtype)
        self.age1 = self.age1 * k[:, None]
        self.ticks = self.ticks * k
        self.rs = torch.maximum(self.rs, d)

    def peek(self):
        """a copy that a look ahead may step without moving this one (the value of the frame after the rollout)"""
        c = State.__new__(State)
        c.__dict__.update(self.__dict__)
        return c

    def snap(self, idx=None):
        """the state at the rollout's start for seq(): a dict of its tensors (for the players idx)"""
        d_ = dict(s=self.s, plan=self.plan, slots=self.slots, age1=self.age1, ticks=self.ticks, rs=self.rs, cnt=self.cnt)
        return d_ if idx is None else {k_: v_[idx] for k_, v_ in d_.items()}


def adds(mod, s):
    """what the head adds to his intention's and his way's logits, from the slow state of the moment"""
    return mod.target(s), mod.way(s)


def live(mod, st, e, h, ev=None):
    """one frame for all players: e [n, enc] (the encoder and the attention part's output), h [n, fast] (his fast memory
    after this frame, stepped on x_fast = e + plan_in(st.plan)), ev [n, ev] (the tick's events; None: zeros) -> (the plan
    for the next frames [n, plan], target_add [n, n_target], way_add [n, n_way]) for this frame's outputs. Ticks on its
    frames (st.ticked, st.u, st.r_tick: what the ring keeps)."""
    import torch
    st.acc = st.acc + e
    st.cnt = st.cnt + 1.0
    st.ticked = (st.g + 1) % st.K == 0
    st.g += 1
    if st.ticked:
        if ev is None:
            ev = torch.zeros(e.shape[0], st.lay["ev"], device=e.device)
        st.s, st.plan, st.slots, st.age1, st.ticks, st.u = tick(mod, st.lay, st.s, st.slots, st.age1, st.ticks, h,
                                                                st.acc / st.cnt[:, None], ev.to(e.dtype), st.stats)
        st.r_tick = st.rs.clone()
        st.rs = torch.zeros_like(st.rs)
        st.acc = torch.zeros_like(st.acc)
        st.cnt = torch.zeros_like(st.cnt)
    ta, wa = adds(mod, st.s)
    return st.plan, ta, wa


def refresh(mod, st, s):
    """(the ring) before a rollout: the slow state he plays from is the one the update re-runs; the plan is made again from
    it (0 where a reset came since the last tick, as in play)"""
    import torch
    with torch.no_grad():
        k = (1.0 - st.rs)[:, None]
        st.s = s * k
        st.plan = torch.tanh(mod.plan_out(st.s)) * k


def fast_seq(cell_, e, h0, done):
    """the fast GRU over a stretch of frames by the library's GRU, cut at his resets (the trainer's gru_seq, B-237; copied
    so that this file does not import the trainer): h_t = cell(e_t, h_{t-1} * (1 - done_{t-1})), h_{-1} = h0 -> [T, B, H]"""
    import torch
    T, B = done.shape
    w = [cell_.weight_ih, cell_.weight_hh, cell_.bias_ih, cell_.bias_hh]
    dn = done.detach() > 0.5
    st = torch.ones(T, B, dtype=torch.bool, device=e.device)
    st[1:] = dn[:-1]
    if not bool(st[1:].any()):
        return torch._VF.gru(e, h0[None].contiguous(), w, True, 1, 0.0, cell_.training, False, False)[0]
    stb = st.t().reshape(-1)
    sid = torch.cumsum(stb.long(), 0) - 1
    S = int(sid[-1]) + 1
    idx = torch.arange(B * T, device=e.device)
    first = idx[stb]
    pos = idx - first[sid]
    L = int(pos.max()) + 1
    flat = pos * S + sid
    ef = e.transpose(0, 1).reshape(B * T, e.shape[-1])
    P = ef.new_zeros(L * S, e.shape[-1]).index_copy(0, flat, ef).view(L, S, e.shape[-1])
    from0 = (first % T) == 0
    hi = h0.new_zeros(S, h0.shape[-1]).index_copy(0, torch.nonzero(from0).squeeze(1), h0[first[from0] // T])
    out = torch._VF.gru(P, hi[None], w, True, 1, 0.0, cell_.training, False, False)[0]
    return out.reshape(L * S, -1).index_select(0, flat).view(B, T, -1).transpose(0, 1).contiguous()


def seq(mod, lay, e, dn, st0, cell_, h0, ev, stats=None, xg=None):
    """the learning step over a rollout's whole sequences, the same numbers as live() frame by frame, under the gradient.
      e    [T, B, enc]  the encoder's output (the attention part's added)
      dn   [T, B]       1 - done (a reset after that frame)
      st0  dict         the head at the rollout's start (after the reset of the frame before): s, plan [B, ...] (under the
                        gradient when re-run from the ring), slots, age1, ticks, cnt (State.snap())
      cell_             his fast GRU (nn.GRUCell; its weights are used as they are)
      h0   [B, fast]    his fast memory at the rollout's start
      ev   [J, B, ev]   the events of each tick (J = T / every)
      xg   [T, B, enc]  (--legs-feat; None: nothing) added to the fast GRU's input only (the running mean reads e)
    T must be a whole number of ticks and the rollout must start on a tick's boundary (the trainer's global frame count), so
    the running mean is empty at its start. The fast GRU runs in segments of `every` frames (one fused call each), the head's
    tick between. -> dict: hs [T, B, fast] (the fast memory after each frame, before its reset), tadd [T, B, n_target], wadd
    [T, B, n_way] (what the head adds to the frame's logits), aux {question: [T, B, n]} (added to the hands' answers),
    s [J, B, size] (after each tick), plan [J, B, plan], v_short, v_long [J, B], win [J, B, bands], u [J, B, u] (the ticks'
    inputs, for the ring)"""
    import torch
    T, B = dn.shape
    K = int(lay["every"])
    assert T % K == 0, (T, K)
    J = T // K
    if st0.get("cnt") is not None and st0["cnt"].numel():
        assert float(st0["cnt"].abs().max()) == 0.0, "the rollout does not start on a tick's boundary"
    s, plan0 = st0["s"], st0["plan"]
    slots, age1, ticks = st0["slots"].to(e.dtype), st0["age1"], st0["ticks"]       # (store_half: the slots as kept, at full precision)
    h = h0
    hs_l, S_l, P_l, U_l = [], [], [], []
    ones = torch.ones_like(dn[:1])
    for j in range(J):
        f0 = j * K
        dseg = dn[f0:f0 + K]
        # the plan his fast step reads on this segment's frames: the last tick's (frame f0 - 1), cleared from the frame after
        # a reset; on the first segment the rollout's own (st0, already cleared)
        pd = torch.cat([ones, dseg[:K - 1]], 0) if j == 0 else torch.cat([dn[f0 - 1:f0], dseg[:K - 1]], 0)
        alive = torch.cumprod(pd, 0)                                     # [K, B]
        pl = (plan0 if j == 0 else P_l[-1])[None] * alive[..., None]
        xf_ = e[f0:f0 + K] + mod.plan_in(pl)
        if xg is not None:                                               # (--legs-feat) what only the fast GRU reads beside: the legs' features
            xf_ = xf_ + xg[f0:f0 + K]
        hseg = fast_seq(cell_, xf_, h, 1.0 - dseg)
        hs_l.append(hseg)
        h = hseg[-1] * dseg[-1][:, None]
        # the tick at frame f0 + K - 1: the store and the slow state cleared where a reset came since the last tick
        kp = (dseg[:K - 1].prod(0) if j == 0 else dn[f0 - 1:f0 + K - 1].prod(0))
        g = torch.cat([dseg[:K - 1], ones], 0)
        keep = torch.flip(torch.cumprod(torch.flip(g, [0]), 0), [0])    # a frame counts in the mean if no reset after it
        mean = (keep[..., None] * e[f0:f0 + K]).sum(0) / keep.sum(0)[:, None]
        s_prev = (s if j == 0 else S_l[-1]) * kp[:, None]
        slots, age1, ticks = slots * kp[:, None, None], age1 * kp[:, None], ticks * kp
        s_new, p_new, slots, age1, ticks, u = tick(mod, lay, s_prev, slots, age1, ticks, hseg[-1], mean, ev[j].to(e.dtype), stats)
        S_l.append(s_new)
        P_l.append(p_new)
        U_l.append(u)
    hs = torch.cat(hs_l, 0)
    Ss = torch.stack(S_l)                                                # [J, B, size]
    # the slow state each frame's outputs read: the last tick's (the rollout's own before the first), the bias of the layers
    # (target(0)) from the frame after a reset until the next tick
    St = torch.cat([s[None], Ss], 0)                                     # [J + 1, B, size]
    G = torch.cat([ones, dn, torch.ones_like(dn[:K - 1])], 0).reshape(J + 1, K, B)
    alive = torch.cumprod(torch.cat([torch.ones_like(G[:, :1]), G[:, :-1]], 1), 1).reshape(-1, B)[1:T + 1]    # [T, B]
    idx = (torch.arange(T, device=dn.device) + 1) // K

    def held(layer):
        o = layer(St)[idx]
        return o * alive[..., None] + layer.bias * (1.0 - alive[..., None])

    out = dict(hs=hs, tadd=held(mod.target), wadd=held(mod.way), aux={k_: held(l_) for k_, l_ in mod.aux.named_children()},
               s=Ss, plan=torch.stack(P_l), v_short=mod.v_short(Ss).squeeze(-1), v_long=mod.v_long(Ss).squeeze(-1),
               win=mod.win(Ss), u=torch.stack(U_l))
    return out


class Ring:
    """the trainer's store of the head's tick inputs u: the last `ring` ticks of every player before the rollout (fp16 on the
    host), their reset flags and the slow state before the oldest (on the card). As slowmem.Ring (whose re-run reads the
    module's inp and gru, the same names here), with the head's wider u"""

    def __init__(self, n, lay, ticks_per_rollout, dev):
        import torch
        self.lay, self.R = lay, int(lay["ring"])
        self.cap = self.R + int(ticks_per_rollout)
        self.u = torch.zeros(n, self.cap, u_width(lay), dtype=torch.float16)
        self.r = torch.zeros(n, self.cap, dtype=torch.uint8)
        self.start, self.L = 0, 0
        self.s0 = torch.zeros(n, lay["size"], device=dev)
        self.dev = dev


def _ring_methods():
    """slowmem.Ring's order, push, trim, state and state_all, as they are"""
    import slowmem as slowmem_
    for k_ in ("order", "push", "trim", "state", "state_all"):
        setattr(Ring, k_, getattr(slowmem_.Ring, k_))


try:                                                         # (slowmem is numpy-only at its top level: safe on a server)
    _ring_methods()
except ImportError:                                          # (a copy of this file without slowmem beside it: no Ring)
    pass


def win_targets(p, wg, wb, K, wgt=None):
    """(the trainer) the win head's targets over a rollout (BUILD_v0.4.md section 3a, lane sim's columns of info["aux"]):
      p     [J, B, bands] the head's chances at each tick (no gradient)
      wg    [T, B] win_game: the whole game or mid-game start that frame belongs to (-1: none), read from the info of the
            step that played the frame
      wb    [T, B] win_band: the band of his final margin on the frame that ends the game, -1 on every other frame
    -> (G [J, B, bands], mask [J, B], true [J, B]): every tick of a game that ends in the rollout gets one_hot(its band)
    (true); a tick of a game that goes on past the rollout gets the chance at that game's last tick in the rollout, and
    that last tick is masked (gamma 1: the forecast is a value); a tick outside a labelled game is masked."""
    import torch
    T, B = wg.shape
    J, nb = p.shape[0], p.shape[2]
    tf = torch.arange(J, device=wg.device) * K + K - 1
    g = wg[tf]                                                           # [J, B] each tick's game
    ok = g > -0.5
    end = wb > -0.5                                                      # [T, B] the frames that end a game
    m_ = (wg[None, :, :] == g[:, None, :]) & end[None] & ok[:, None, :]  # [J, T, B] a frame of the tick's game that ends it
    ended = m_.any(1)
    band = torch.where(m_, wb[None].expand(J, T, B), torch.full_like(wb[None].expand(J, T, B), -1.0)).max(1).values
    same = (g[:, None, :] == g[None, :, :])                              # [J, J, B] ticks of the same game
    jj = torch.arange(J, device=wg.device)
    last = torch.where(same, jj[None, :, None].expand(J, J, B), torch.full_like(jj[None, :, None].expand(J, J, B), -1)).max(1).values
    boot = p.gather(0, last.clamp(min=0)[..., None].expand(J, B, nb))   # the chance at the game's last tick in the rollout
    oh = torch.nn.functional.one_hot(band.clamp(0, nb - 1).long(), nb).to(p.dtype)
    G = torch.where(ended[..., None], oh, boot)
    mask = (ok & (ended | (last != jj[:, None]))).to(p.dtype)
    if wgt is not None:
        mask = mask * wgt[tf]
    return G, mask, ended & ok


# ------------------------------------------------------------------------------------------------------------------ numpy
# (lane serve: BUILD_v0.4.md section 5. The torch side above is the reference: np_tick must match live() to 1e-5.)
def params_np(sd, prefix="head."):
    """the part's arrays from a state dict of numpy arrays (or of tensors)"""
    out = {}
    for k, v in sd.items():
        if k.startswith(prefix):
            out[k[len(prefix):]] = np.asarray(v.cpu().numpy() if hasattr(v, "cpu") else v, np.float32)
    return out


def _np_off(lay):
    """the numpy state's columns: name -> (start, end)"""
    S, P, E = int(lay["size"]), int(lay["plan"]), int(lay["enc"])
    NS, C = int(lay["slots"]), int(lay["slot"])
    o, out = 0, {}
    for name, w in (("s", S), ("plan", P), ("acc", E), ("n", 1), ("f", 1), ("store", NS * (C + 1)), ("ticks", 1)):
        out[name] = (o, o + w)
        o += w
    return out


def np_state_width(lay):
    """the numpy state's width per seat: [s (size) | plan | acc e (enc) | n (frames in acc) | frames (the tick's clock: kept
    by np_clear, as the trainer's global frame count) | store: slots x (slot + 1: its age + 1, 0 empty) | the head's ticks
    since the clear (a slot is written when it is a multiple of write_every, as tick())]"""
    return _np_off(lay)["ticks"][1]


def _np_sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def np_read(W, lay, s, slots, age1):
    """read() in numpy: s [B, size] (the slow state of the tick before), slots [B, S, slot], age1 [B, S] (age + 1; 0: empty)
    -> [B, read] (zeros where the store is empty). The same folding of the key and value layers into the query and the
    weighted sum as read()."""
    B, S, C = slots.shape
    Hh, R = int(lay["read_heads"]), int(lay["read"])
    dh = R // Hh
    valid = age1 > 0
    anyv = valid.any(1)
    af = age_features_np(np.maximum(age1 - 1.0, 0.0), lay)               # [B, S, 8]
    q = (s @ W["rq.weight"].T + W["rq.bias"]).reshape(B, Hh, dh)
    Wk = W["rk.weight"].reshape(Hh, dh, C + N_AGE)
    qk = np.einsum("bhd,hdc->bhc", q, Wk)
    sc = (np.einsum("bhc,bsc->bhs", qk[..., :C], slots) + np.einsum("bhc,bsc->bhs", qk[..., C:], af)
          + (q * W["rk.bias"].reshape(Hh, dh)).sum(-1)[..., None]) / math.sqrt(dh)
    sc = np.where(valid[:, None, :], sc, -1e9)
    sc = sc - sc.max(-1, keepdims=True)
    a = np.exp(sc)
    a = a / a.sum(-1, keepdims=True) * anyv[:, None, None]
    ws = np.einsum("bhs,bsc->bhc", a, slots)
    wa = np.einsum("bhs,bsc->bhc", a, af)
    Wv = W["rv.weight"].reshape(Hh, dh, C + N_AGE)
    vh = (np.einsum("bhc,hdc->bhd", ws, Wv[..., :C]) + np.einsum("bhc,hdc->bhd", wa, Wv[..., C:])
          + W["rv.bias"].reshape(Hh, dh) * a.sum(-1)[..., None])
    out = (vh.reshape(B, R) @ W["ro.weight"].T + W["ro.bias"]) * anyv[:, None]
    return out.astype(np.float32)


def np_tick(W, lay, e, h_after, hf, events=None):
    """live() in numpy, one frame for B seats:
      e        [B, enc]   the encoder's output with the attention part's added (what the fast GRU was given before the plan's)
      h_after  [B, fast]  his fast memory after this frame (stepped on e + plan_in(the plan in hf))
      hf       [B, np_state_width]  the head's state before the frame (np.zeros for a new seat)
      events   [B, ev]    the tick's events (the simulator's head_events(), fetched on a frame np_due() names); read on
                          the tick rows only; None: zeros
    -> (plan [B, plan] for the next frames, target_add [B, n_target], way_add [B, n_way] for this frame's logits, the state
    after). Ticks on the rows whose clock reaches a multiple of `every` (np_due); a reset is np_clear() after the frame."""
    o = _np_off(lay)
    K, NS, C, S = int(lay["every"]), int(lay["slots"]), int(lay["slot"]), int(lay["size"])
    hf2 = np.array(hf, np.float32, copy=True)
    a0, a1 = o["acc"]
    ni, fi, ki = o["n"][0], o["f"][0], o["ticks"][0]
    hf2[:, a0:a1] += e
    hf2[:, ni] += 1.0
    hf2[:, fi] += 1.0
    tick = (np.rint(hf2[:, fi]).astype(np.int64) % K) == 0
    if tick.any():
        ti = np.nonzero(tick)[0]
        s = hf2[ti, o["s"][0]:o["s"][1]]
        mean = hf2[ti, a0:a1] / hf2[ti, ni][:, None]
        st = hf2[ti, o["store"][0]:o["store"][1]].reshape(len(ti), NS, C + 1)
        slots, age1 = st[..., :C], st[..., C]
        age1 = np.where(age1 > 0, age1 + 1.0, age1)                      # (tick(): every written slot a tick older, then the read)
        ticks = hf2[ti, ki] + 1.0
        ev = np.zeros((len(ti), int(lay["ev"])), np.float32) if events is None else np.asarray(events, np.float32)[ti]
        rd = np_read(W, lay, s, slots, age1)
        u = np.concatenate([h_after[ti], mean, rd, ev], 1)
        p = np.tanh(u @ W["inp.weight"].T + W["inp.bias"])
        gi = p @ W["gru.weight_ih_l0"].T + W["gru.bias_ih_l0"]
        gh = s @ W["gru.weight_hh_l0"].T + W["gru.bias_hh_l0"]
        r = _np_sig(gi[:, :S] + gh[:, :S])
        zg = _np_sig(gi[:, S:2 * S] + gh[:, S:2 * S])
        nn_ = np.tanh(gi[:, 2 * S:] + r * gh[:, 2 * S:])
        s = (1 - zg) * nn_ + zg * s
        hf2[ti, o["s"][0]:o["s"][1]] = s
        hf2[ti, o["plan"][0]:o["plan"][1]] = np.tanh(s @ W["plan_out.weight"].T + W["plan_out.bias"])
        tk = np.rint(ticks).astype(np.int64)
        wr = (tk % int(lay["write_every"])) == 0
        if wr.any():
            wi = np.nonzero(wr)[0]
            pos = (tk[wi] // int(lay["write_every"]) - 1) % NS
            slots = slots.copy()
            slots[wi, pos] = np.concatenate([s[wi], mean[wi], ev[wi]], 1) @ W["write.weight"].T + W["write.bias"]
            if lay.get("store_half"):                        # (store_half) the slot rounded to float16 as it is written, as in training
                slots[wi, pos] = slots[wi, pos].astype(np.float16).astype(np.float32)
            age1[wi, pos] = 1.0
        hf2[ti, o["store"][0]:o["store"][1]] = np.concatenate([slots, age1[..., None]], -1).reshape(len(ti), -1)
        hf2[ti, ki] = ticks
        hf2[ti, a0:a1] = 0.0
        hf2[ti, ni] = 0.0
    s_all = hf2[:, o["s"][0]:o["s"][1]]
    t_add = (s_all @ W["target.weight"].T + W["target.bias"]).astype(np.float32)
    w_add = (s_all @ W["way.weight"].T + W["way.bias"]).astype(np.float32)
    return hf2[:, o["plan"][0]:o["plan"][1]], t_add, w_add, hf2


def np_due(lay, hf):
    """[B] bool: the coming frame is a tick for these rows (the caller fetches the tick's events before it)"""
    f = np.rint(hf[:, _np_off(lay)["f"][0]]).astype(np.int64) + 1
    return (f % int(lay["every"])) == 0


def np_clear(lay, hf, rows=None):
    """State.reset() on the numpy state, in place (a view is cleared through): everything but the tick's clock cleared, so
    that the head ticks on the same frames for every seat, as in training (the global frame count). rows: a bool mask or
    indices (None: all)"""
    fi = _np_off(lay)["f"][0]
    rows = slice(None) if rows is None else rows
    f = hf[rows, fi].copy()
    hf[rows] = 0.0
    hf[rows, fi] = f
    return hf


def np_plan(lay, hf):
    """the plan of the last tick held in the state [B, plan]"""
    o = _np_off(lay)["plan"]
    return hf[:, o[0]:o[1]]


def np_plan_in(W, plan):
    """the plan as the fast GRU's extra input: plan_in(plan) [B, enc] (x_fast = e + plan_in(plan))"""
    return (plan @ W["plan_in.weight"].T + W["plan_in.bias"]).astype(np.float32)

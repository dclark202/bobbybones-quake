"""v0.4.0 stage A: his belief of the enemy in a memory of its own (the owner, 2026-10-22: "these two need to be separate
networks"). A small network beside the policy that tracks the enemy; v0.3.11's readout (sim/track.py) reads its state in
place of the policy's memory. Nothing of the policy reads it yet: the policy answers exactly as without it.

What it is (the trainer's --belief H, --belief-every K)
  inp   Linear(the policy's normalised inputs -> H) + tanh, frame by frame. It reads the same flat normalised input vector the
        policy's encoder reads (the trainer's norm(obs): (obs - mean) / sd clipped to +-10, before the encoder and the
        attention part; at half precision where the trainer stores its inputs so, --obs-half), with its own weights: nothing of
        the policy (encoder, attention part, GRU) is shared or reached by its gradient.
  gru   GRUCell(2H -> H), stepped once every K frames (a tick: frame t of a rollout with (t + 1) % K == 0; K = 8 is 0.2 s, the
        clock of the strategy head to come). At a tick it reads the summary of the frames since the last tick:
        concat(mean of inp's outputs, max of inp's outputs). The max keeps a single frame's event (a sound, a glimpse): a
        one-frame spike reaches the tick's input at full size, not divided by K.
  Between ticks the state is held. A reset (the trainer's `done`: death, a game's end, the same flag that clears the policy's
  memory) clears the state and the frames gathered since the last tick, after the frame it comes on: the next tick sums only
  the frames after the reset (always at least one: the tick's own frame).

Its state is carried as the policy's memory is: stepped online in the rollout (State, one call a frame for every seat at
once), kept at each rollout's start (the rollouts are whole ticks long, so a rollout starts with nothing gathered), and run
again over the whole rollout in the learning step (seq) from that kept state, under the gradient.

Numpy-free at the top level: torch is imported inside the functions (simulator workers must not import torch).
"""
VERSION = 1
SPIKE_FLOOR = -2.0                # the running max's start: below anything tanh gives (a tick always has at least one frame)


def layout(obs_dim, hid=256, every=8):
    """the checkpoint's "belief" entry"""
    return dict(version=VERSION, obs_dim=int(obs_dim), hid=int(hid), every=int(every), summary="mean+max", reads="obs_norm")


def describe(L):
    return "belief (v0.4.0 A): its own memory of {} beside the policy's; reads the {} normalised inputs ({} -> {}, tanh), a tick every {} " \
           "frames ({:.2f} s) on the mean and max of the frames since the last ({} -> GRU {})".format(
               L["hid"], L["obs_dim"], L["obs_dim"], L["hid"], L["every"], L["every"] * 0.025, 2 * L["hid"], L["hid"])


def make_module(L, seed=4040):
    """the part: inp (Linear obs_dim -> hid), gru (GRUCell 2 hid -> hid), PyTorch's own start; made from a random stream of
    its own (the global stream after it is the one without)"""
    import numpy as np
    import torch
    import torch.nn as nn

    class Belief(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Linear(int(L["obs_dim"]), int(L["hid"]))
            self.gru = nn.GRUCell(2 * int(L["hid"]), int(L["hid"]))
            fd_ = L.get("fade") or {}                       # (v0.6.1b, --brain-fade) the old belief's columns faded out of the brain:
            self.fade_cols = [int(c_) for c_ in fd_.get("cols", ())]    # plain attributes, not weights (the state dict is as before)
            self.fade_g = float(fd_.get("g", 0.0))
            self.fade_m = None

        def enc(self, x):
            g_ = float(self.fade_g)
            if not (g_ > 0 and self.fade_cols):
                return torch.tanh(self.inp(x))
            w_ = self.inp.weight                             # (v0.6.1b) the faded columns' weights times (1 - g): the same sums as
            if self.fade_m is None or self.fade_m[0] != g_ or self.fade_m[1].device != w_.device:    # those inputs times (1 - g)
                m_ = torch.ones(w_.shape[1], dtype=torch.float32)
                m_[torch.as_tensor(self.fade_cols, dtype=torch.long)] = float(np.float32(1.0 - g_))
                self.fade_m = (g_, m_.to(w_.device))
            return torch.tanh(torch.nn.functional.linear(x, w_ * self.fade_m[1].to(w_.dtype), self.inp.bias))

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return Belief()


def fade_layout(cols, g=0.0):
    """(v0.6.1b, --brain-fade) the "fade" entry of the checkpoint's "belief": the columns (the hands' rule fade's, sim/rule_fade.py)
    and the gate g; the brain reads those inputs times (1 - g) (at 0: exactly the brain without it)"""
    return dict(cols=[int(c_) for c_ in cols], g=float(g))


class State:
    """the live state of n seats (the trainer's rollout): s the belief, and the frames gathered since the last tick"""

    def __init__(self, n, L, dev):
        import torch
        H = int(L["hid"])
        self.K = int(L["every"])
        self.s = torch.zeros(n, H, device=dev)
        self.sum = torch.zeros(n, H, device=dev)
        self.mx = torch.full((n, H), SPIKE_FLOOR, device=dev)
        self.cnt = torch.zeros(n, device=dev)

    def frame(self, mod, x, tick):
        """one frame for every seat: x [n, obs_dim] the normalised inputs the policy read; tick: step the GRU (after this
        frame is gathered). -> True if it ticked"""
        import torch
        u = mod.enc(x)
        self.sum = self.sum + u
        self.mx = torch.maximum(self.mx, u)
        self.cnt = self.cnt + 1.0
        if tick:
            self.s = mod.gru(torch.cat([self.sum / self.cnt[:, None], self.mx], 1), self.s)
            self.sum = torch.zeros_like(self.sum)
            self.mx = torch.full_like(self.mx, SPIKE_FLOOR)
            self.cnt = torch.zeros_like(self.cnt)
        return tick

    def reset(self, d):
        """after a frame: d [n] 1 where the policy's memory is cleared (done)"""
        import torch
        k = 1.0 - d
        self.s = self.s * k[:, None]
        self.sum = self.sum * k[:, None]
        self.cnt = self.cnt * k
        self.mx = torch.where(d[:, None] > 0.5, torch.full_like(self.mx, SPIKE_FLOOR), self.mx)


def summaries(u, done, K):
    """the ticks' inputs over a rollout: u [T, B, H] inp's outputs, done [T, B] -> (inputs [T/K, B, 2H], reset [T/K, B]):
    a frame counts toward its tick (the window's last frame) if no reset comes between it and the tick (a reset on the tick's
    own frame comes after the tick); reset[k] = 1 where the state is cleared between tick k - 1 and tick k (a reset on a frame
    from tick k - 1's on, before tick k's; for k = 0 from the rollout's first frame: the frame before is the rollout before's,
    whose reset the kept state has had)"""
    import torch
    T, B, H = u.shape
    assert T % K == 0, "a rollout of {} frames is not whole ticks of {}".format(T, K)
    W = T // K
    d = (done.detach() > 0.5).float().view(W, K, B)
    # c[j] = resets on frames j .. K-2 of the window (frame K-1 is the tick's own): a frame counts if c[j] == 0
    dk = torch.cat([d[:, :K - 1], torch.zeros_like(d[:, :1])], 1)
    c = torch.flip(torch.cumsum(torch.flip(dk, [1]), 1), [1])
    ok = (c < 0.5)                                                  # [W, K, B]
    uw = u.view(W, K, B, H)
    okf = ok.float()[..., None]
    mean = (uw * okf).sum(1) / okf.sum(1)
    mx = torch.where(ok[..., None], uw, torch.full_like(uw, SPIKE_FLOOR)).max(1).values
    rst = tick_resets(done, K)[0]
    return torch.cat([mean, mx], -1), rst


def tick_resets(done, K):
    """done [T, B] (on any device) -> (rst [T/K, B]: 1 where the state is cleared before tick k, a reset on frames kK - 1 ..
    kK + K - 2; dn [T/K, B]: the same as the trainer's gru_seq reads its done flags, dn[k] = rst[k + 1], the last 0)"""
    import torch
    T, B = done.shape
    W = T // K
    dp = torch.cat([torch.zeros_like(done[:1]), done[:-1]], 0).detach()     # dp[t] = done[t - 1]
    rst = (dp.reshape(W, K, B) > 0.5).any(1).float()
    return rst, torch.cat([rst[1:], torch.zeros_like(rst[:1])], 0)


def seq(mod, x, done, s0, K, gru_fn=None):
    """the belief over a rollout's whole sequences, under the gradient: x [T, B, obs_dim] the normalised inputs, done [T, B],
    s0 [B, H] the state kept at the rollout's start -> the state after each tick [T/K, B, H] (the same numbers as State
    frame by frame). gru_fn: the trainer's gru_seq (the library's GRU, cut at the resets), else a loop over the ticks"""
    u = mod.enc(x)
    inp, rst = summaries(u, done, K)
    W = inp.shape[0]
    h0 = s0 * (1.0 - rst[0])[:, None]
    if gru_fn is not None:                                          # gru_seq: h_k = cell(e_k, h_{k-1} * (1 - dn_{k-1})), dn_k = rst_{k+1}
        import torch
        dn = torch.cat([rst[1:], torch.zeros_like(rst[:1])], 0)
        return gru_fn(mod.gru, inp.contiguous(), h0.contiguous(), dn)
    import torch
    out, s = [], h0
    for k in range(W):
        if k > 0:
            s = s * (1.0 - rst[k])[:, None]
        s = mod.gru(inp[k], s)
        out.append(s)
    return torch.stack(out)


def tick_frames(T, K):
    """the frames of a rollout the belief ticks on (and its readout is graded on)"""
    return list(range(K - 1, T, K))

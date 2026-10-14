"""The slow memory (v0.3 candidate, 2026-10-14; slowmem/SLOWMEM_BUILD.md): a second, small memory beside his GRU of 512 that
ticks once every `every` simulator steps and can be taught over minutes.

What it is
  At a tick (frame t with (frame + 1) % every == 0) it reads u = [his fast memory h after frame t, the mean of the encoder's
  output over the frames since the last tick], squeezes it (p = tanh(inp(u)), `inp` wide) and steps a GRU of `size` with it.
  Its state s reaches the outputs through a door: the outputs read z = h + door(s) in place of h (the policy, the values, the
  guessing game's questions). The door starts at zero: a network given the part answers exactly as before (as the attention
  part's last layer, sim/attn.py). The fast memory's own recurrence is unchanged (the GRU of 512 steps on h, not on z).
  A reset (death, a game's end: the trainer's `done`) clears s and the running mean as it clears h.

How it is taught over minutes (the trainer, sim/train_duel_rnn.py --slow-mem 1)
  The trainer keeps, per player, a ring of the slow memory's inputs u of the last `ring` ticks before the rollout (fp16, on
  the host) and the slow state before the ring's oldest tick. In an update the slow GRU is run again from that state over
  the ring (with the weights of the moment, under the gradient: one fused GRU call over the ticks after the player's last
  reset) and then over the rollout's own ticks, whose u is worked out afresh from the encoder and the fast memory (under the
  gradient). So the gradient of a loss in this rollout reaches the slow GRU's and the squeeze's weights through every tick of
  the ring, minutes back; the fast side (encoder, attention part, fast GRU) is reached only through the rollout's own ticks:
  u of an older tick is a stored number from older weights (stale as any stored activation; with a learning rate of 1e-4
  it moves little over a few minutes). Before each rollout the ring's oldest ticks beyond `ring` are folded into the stored
  state (with the weights of the moment, no gradient) and the slow state he plays with is run again over the ring, so that
  what he plays and what he learns from are the same numbers.

The numpy side (sim/test_suite.py Policy, plugins/netpass.py) carries the whole state in one array per seat, wider than
the fast memory alone: [h (fast) | s (size) | the encoder's sum since the tick (enc) | frames in that sum | frames since the
memory was cleared]. A caller that clears a seat's memory (h[i] = 0) clears all of it: the next tick comes `every` frames
later. The trainer ticks on the global frame count (a phase that does not restart at a reset): both are what he meets.

Numpy only at the top level (the game server imports this file); torch is imported inside the torch functions.
"""
import json

import numpy as np

VERSION = 1


def layout(size=256, inp=128, every=48, ring=320, fast=512, enc=256, chrono=320):
    """the part's shape and timing; kept in a checkpoint as "slow" and in policy.npz as text. chrono: the longest of the
    slow GRU's starting time scales in ticks (its units keep what they hold over 1 to `chrono` ticks at the start, spread
    evenly: the "chrono" start of Tallec and Ollivier, 2018; 0: PyTorch's own start). Only the start: learnt after."""
    return dict(version=VERSION, size=int(size), inp=int(inp), every=int(every), ring=int(ring), fast=int(fast), enc=int(enc),
                chrono=int(chrono))


def describe(lay):
    return "slow memory: {} wide, a tick every {} frames ({:.2f} s), squeeze {} from {} + {}, taught over {} ticks ({:.1f} min)".format(
        lay["size"], lay["every"], lay["every"] * 0.025, lay["inp"], lay["fast"], lay["enc"], lay["ring"],
        lay["ring"] * lay["every"] * 0.025 / 60.0)


def width(lay):
    """the numpy state's width per seat"""
    return int(lay["fast"]) + int(lay["size"]) + int(lay["enc"]) + 2


def as_layout(x):
    """a layout from a checkpoint's dict or a policy.npz's text"""
    if x is None:
        return None
    if isinstance(x, dict):
        return x
    return json.loads(str(x))


# ------------------------------------------------------------------------------------------------------------------ torch
def make_module(lay, seed=None):
    """the part as a torch module: inp (Linear fast+enc -> inp), gru (nn.GRU inp -> size, one layer), door (Linear size ->
    fast, no bias, zeros). seed: its own random stream (the converter), None: the global one (the trainer)"""
    import torch
    import torch.nn as nn

    class SlowMem(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Linear(lay["fast"] + lay["enc"], lay["inp"])
            self.gru = nn.GRU(lay["inp"], lay["size"])
            self.door = nn.Linear(lay["size"], lay["fast"], bias=False)
            nn.init.zeros_(self.door.weight)
            tmax = int(lay.get("chrono", 0))
            if tmax > 1:                                     # the update gate z (h' = (1 - z) n + z h) starts near 1 for long time
                S_ = lay["size"]                             # scales: bias log(tau - 1), tau even over 1 .. chrono ticks
                with torch.no_grad():
                    tau = 1.0 + torch.rand(S_) * (tmax - 1.0)
                    self.gru.bias_ih_l0[S_:2 * S_] = torch.log((tau - 1.0).clamp(min=1e-3))
                    self.gru.bias_hh_l0[S_:2 * S_] = 0.0

    if seed is None:
        return SlowMem()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return SlowMem()


def cell(mod, p, s):
    """one step of the slow GRU (the same weights as the fused nn.GRU)"""
    import torch
    g = mod.gru
    return torch.gru_cell(p, s, g.weight_ih_l0, g.weight_hh_l0, g.bias_ih_l0, g.bias_hh_l0)


class State:
    """the slow memory's live state for n players (the trainer's rollout; one for him, one for the league's opponent)"""

    def __init__(self, n, lay, dev):
        import torch
        self.lay, self.K = lay, int(lay["every"])
        self.s = torch.zeros(n, lay["size"], device=dev)
        self.acc = torch.zeros(n, lay["enc"], device=dev)
        self.n = torch.zeros(n, device=dev)
        self.rs = torch.zeros(n, device=dev)                 # a reset since the last tick (the ring's flag of the next tick)
        self.g = 0                                           # the global frame count (ticks: (g + 1) % K == 0)
        self.ticked, self.u, self.r_tick = False, None, None

    def reset(self, d):
        """after a frame: d [n] 1 where his memory is cleared (done)"""
        k = (1.0 - d)
        self.s = self.s * k[:, None]
        self.acc = self.acc * k[:, None]
        self.n = self.n * k
        self.rs = torch_max(self.rs, d)

    def peek(self):
        """a copy that a look ahead may step without moving this one (the value of the frame after the rollout)"""
        c = State.__new__(State)
        c.__dict__.update(self.__dict__)
        return c


def torch_max(a, b):
    import torch
    return torch.maximum(a, b)


def live(mod, st, e, h):
    """one frame for all players: e [n, enc] (what the encoder and the attention part gave), h [n, fast] (his fast memory
    after this frame) -> z [n, fast], what the outputs read. Ticks the slow GRU on its frames (st.ticked, st.u, st.r_tick:
    what the ring keeps)."""
    import torch
    st.acc = st.acc + e
    st.n = st.n + 1.0
    st.ticked = (st.g + 1) % st.K == 0
    st.g += 1
    if st.ticked:
        u = torch.cat([h, st.acc / st.n[:, None]], 1)
        st.s = cell(mod, torch.tanh(mod.inp(u)), st.s)
        st.u, st.r_tick = u, st.rs.clone()
        st.rs = torch.zeros_like(st.rs)
        st.acc = torch.zeros_like(st.acc)
        st.n = torch.zeros_like(st.n)
    return h + mod.door(st.s)


def ring_run(mod, u, r, s0):
    """the slow state after the ring's ticks: u [L, B, fast+enc] (the stored inputs, oldest first), r [L, B] (1: a reset
    before that tick), s0 [B, size] (the state before the oldest). One fused GRU call over each player's ticks after his
    last reset (a reset clears the state: what came before it does not matter). Under the gradient if the caller is."""
    import torch
    from torch.nn.utils.rnn import pack_padded_sequence
    L, B = r.shape
    if L == 0:
        return s0
    p = torch.tanh(mod.inp(u))
    ar = torch.arange(L, device=r.device)
    lr = torch.where(r > 0, ar[:, None].expand(L, B), torch.full_like(ar[:, None].expand(L, B), -1)).max(0).values
    st = lr.clamp(min=0)
    h0 = torch.where((lr >= 0)[:, None], torch.zeros_like(s0), s0)
    gi = (st[None, :] + ar[:, None]).clamp(max=L - 1)
    pg = p.gather(0, gi[..., None].expand(L, B, p.shape[-1]))
    pk = pack_padded_sequence(pg, (L - st).cpu(), enforce_sorted=False)
    _, hn = mod.gru(pk, h0[None].contiguous())
    return hn[0]


def ring_run_loop(mod, u, r, s0):
    """the same, tick by tick (the reference the tests check ring_run against)"""
    s = s0
    for j in range(r.shape[0]):
        s = cell(mod, __import__("torch").tanh(mod.inp(u[j])), s * (1.0 - r[j].float())[:, None])
    return s


def seq_z(mod, lay, e, hs, dn, s0):
    """what the outputs read over a rollout's whole sequences: e [T, B, enc], hs [T, B, fast] (the fast memory after each
    frame, before its reset), dn [T, B] (1 - done), s0 [B, size] (the slow state at the rollout's start, after the reset of
    the frame before). T must be a whole number of ticks and the rollout must start on a tick's boundary (the trainer's
    global frame count). The same numbers as live() frame by frame, under the gradient: the rollout's ticks only are
    stepped in Python (T / every of them), the rest is whole tensors. -> z [T, B, fast]"""
    import torch
    T, B = dn.shape
    K = int(lay["every"])
    assert T % K == 0, (T, K)
    J = T // K
    dseg = dn.reshape(J, K, B)
    g = torch.cat([dseg[:, :K - 1], torch.ones_like(dseg[:, :1])], 1)
    keep = torch.flip(torch.cumprod(torch.flip(g, [1]), 1), [1])            # a frame counts in its tick's mean if no reset after it
    es = e.reshape(J, K, B, e.shape[-1])
    mean = (keep[..., None] * es).sum(1) / keep.sum(1)[..., None]
    ht = hs.reshape(J, K, B, hs.shape[-1])[:, K - 1]
    p = torch.tanh(mod.inp(torch.cat([ht, mean], -1)))
    s, states = s0, [s0]
    for j in range(J):
        kp = dn[0:K - 1].prod(0) if j == 0 else dn[j * K - 1:j * K + K - 1].prod(0)
        s = cell(mod, p[j], s * kp[:, None])
        states.append(s)
    D = mod.door(torch.stack(states))                       # [J + 1, B, fast]
    G = torch.cat([torch.ones_like(dn[:1]), dn, torch.ones_like(dn[:K - 1])], 0).reshape(J + 1, K, B)
    alive = torch.cumprod(torch.cat([torch.ones_like(G[:, :1]), G[:, :-1]], 1), 1).reshape(-1, B)[1:T + 1]
    idx = (torch.arange(T, device=dn.device) + 1) // K
    return hs + D[idx] * alive[..., None]


class Ring:
    """the trainer's store of the slow memory's inputs: the last `ring` ticks of every player before the rollout (fp16 on the
    host: 10,080 players x 320 ticks x 768 = 5 GB), their reset flags, and the slow state before the oldest (on the card)"""

    def __init__(self, n, lay, ticks_per_rollout, dev):
        import torch
        self.lay, self.R = lay, int(lay["ring"])
        self.cap = self.R + int(ticks_per_rollout)
        self.u = torch.zeros(n, self.cap, lay["fast"] + lay["enc"], dtype=torch.float16)     # (player-major: a minibatch's
        self.r = torch.zeros(n, self.cap, dtype=torch.uint8)                                  # players are whole blocks)
        self.start, self.L = 0, 0
        self.s0 = torch.zeros(n, lay["size"], device=dev)
        self.dev = dev

    def order(self):
        import torch
        return (self.start + torch.arange(self.L)) % self.cap

    def push(self, pending):
        """after an update: the rollout's ticks [(u [n, ...], r [n]), ...] join the ring"""
        for u, r in pending:
            assert self.L < self.cap, "the ring is full: trim() before the rollout"
            pos = (self.start + self.L) % self.cap
            self.u[:, pos] = u
            self.r[:, pos] = r.to(self.r.dtype)
            self.L += 1

    def trim(self, mod, chunk=2048):
        """before a rollout: the ticks beyond `ring` are folded into the stored state (the weights of the moment, no gradient)"""
        import torch
        with torch.no_grad():
            while self.L > self.R:
                u, r = self.u[:, self.start], self.r[:, self.start]
                for c0 in range(0, self.s0.shape[0], chunk):
                    sl = slice(c0, c0 + chunk)
                    p = torch.tanh(mod.inp(u[sl].to(self.dev).float()))
                    self.s0[sl] = cell(mod, p, self.s0[sl] * (1.0 - r[sl].to(self.dev).float())[:, None])
                self.start = (self.start + 1) % self.cap
                self.L -= 1

    def state(self, mod, ci):
        """the slow state after the ring for the players ci (a host index tensor): under the gradient if the caller is"""
        s0 = self.s0[ci.to(self.dev)]
        if self.L == 0:
            return s0
        o = self.order()
        u = self.u[ci][:, o].to(self.dev).float().transpose(0, 1)
        r = self.r[ci][:, o].to(self.dev).transpose(0, 1)
        return ring_run(mod, u, r, s0)

    def state_all(self, mod, chunk=256):
        import torch
        out = torch.zeros_like(self.s0)
        with torch.no_grad():
            for c0 in range(0, self.s0.shape[0], chunk):
                ci = torch.arange(c0, min(c0 + chunk, self.s0.shape[0]))
                out[ci.to(self.dev)] = self.state(mod, ci)
        return out


# ------------------------------------------------------------------------------------------------------------------ numpy
def params_np(sd, prefix="slow."):
    """the part's arrays from a state dict of numpy arrays (or of tensors)"""
    out = {}
    for k, v in sd.items():
        if k.startswith(prefix):
            out[k[len(prefix):]] = np.asarray(v.cpu().numpy() if hasattr(v, "cpu") else v, np.float32)
    return out


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def np_step(W, lay, e, h, hf):
    """one frame in numpy: e [B, enc] (the encoder's output, the attention part's added), h [B, fast] (the fast memory after
    this frame), hf [B, width] (the whole state before it) -> z [B, fast] (what the outputs read), the whole state after"""
    H, S, E, K = int(lay["fast"]), int(lay["size"]), int(lay["enc"]), int(lay["every"])
    s = hf[:, H:H + S].astype(np.float32).copy()
    acc = hf[:, H + S:H + S + E] + e
    n = hf[:, H + S + E] + 1.0
    f = hf[:, H + S + E + 1] + 1.0
    tick = (np.rint(f).astype(np.int64) % K) == 0
    if tick.any():
        u = np.concatenate([h[tick], acc[tick] / n[tick, None]], 1)
        p = np.tanh(u @ W["inp.weight"].T + W["inp.bias"])
        gi = p @ W["gru.weight_ih_l0"].T + W["gru.bias_ih_l0"]
        s_ = s[tick]
        gh = s_ @ W["gru.weight_hh_l0"].T + W["gru.bias_hh_l0"]
        r = _sig(gi[:, :S] + gh[:, :S])
        zg = _sig(gi[:, S:2 * S] + gh[:, S:2 * S])
        nn_ = np.tanh(gi[:, 2 * S:] + r * gh[:, 2 * S:])
        s[tick] = (1 - zg) * nn_ + zg * s_
        acc = acc.copy()
        acc[tick] = 0.0
        n = n.copy()
        n[tick] = 0.0
    z = h + s @ W["door.weight"].T
    hf2 = np.concatenate([h, s, acc, n[:, None], f[:, None]], 1).astype(np.float32)
    return z.astype(np.float32), hf2

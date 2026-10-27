"""v0.4.3: the strategy head (docs/v0.4.3/RUN_v0.4.3.md, "The strategy head"; the trainer's --head2). A small slow GRU
beside his hands that ticks with the brain (every 8 frames, 0.2 s), reads what the brain knows and what he has, and acts by
a plan into the hands' memory and a bias on the intention head's choice. Not sim/head.py (v0.4's earlier candidate, ~7 M
weights, a store read by attention, its inputs under the gradient); this one is ~0.65 M and reads only numbers.

What it reads (one vector u at each tick, all numbers: no gradient reaches anything it reads)
  brain  the brain's memory after its tick (sim/belief.py: 256)
  trk    the brain's readout of the enemy now (sim/track.py: 27; raw outputs, clipped to +-10)
  trz    the readout's second part (sim/track_z.py: 28: the zones, speed, direction)
  ahead  the readout of what comes next (sim/ahead.py: where he will be in 1/2/4 s, what he goes for, when he appears, the
         item race)
  ctrl   the slot for the "in control" readouts (B-280; sim/control.py, layout version 2: a ModuleDict `control` of readouts
         "belief" on the brain's state and "both" on the brain's state and the hands' memory). The layout's "ctrl_src" picks
         one ("belief" or "both"; the trainer's --head2-ctrl-src) or none ("none", the default: zeros, as before). What it
         reads: the readout's four chances minus 0.5 (sigmoid(logits) - 0.5: 0 for a readout whose last layer is at zero),
         its input rounded to half precision as the readouts learn it; worked out under no_grad: a number to the head, no
         gradient from the head reaches the readouts, the brain or the hands through it (the head's learning step re-reads
         the stored u in any case)
  obs    his own normalised inputs that say his stack, his item timers, score and clock (the columns of docs/INPUTS.csv named
         by OBS_SEL, kept in the layout as indices: health, armor, weapons owned and ammunition, the mega and red armor's
         place and sight, the clock and score, the round's time left, the seconds since he took each item, his intention)
  hands  the hands' fast memory after the tick's frame (512)
  Each part can be left out by the layout's "on" (zeros in its place); the vector is rounded to half precision before use,
  in the trainer (which stores it so) and in numpy alike.

What it is
  p = tanh(inp(u)); s = GRUCell(p, s) (size 256; the update gate started slow: "chrono" ticks, as sim/slowmem.py)
  plan = tanh(plan_out(s))  [64]                 bias = gate * target(s)  [the intention's choices]
  held from the frame after the tick to the next tick; zeros after a reset (death, a game's end: the hands' own flag) until
  the next tick. The hands' fast GRU reads x + gate * plan_in(plan) (x: the encoder and attention part's output); the bias is
  added to the intention head's logits. plan_in and target start at exactly zero: a network given the head answers
  exactly as it did. The gate (a buffer in the state dict, "head2.gate"; live in the trainer) scales both outputs: 0 is the
  network without the head whatever its weights.
  v = value(cat[s, hands' memory of the frame]) -> 1: the head's own two-minute value of all his pay (gamma 0.9998).

How it learns (the trainer; the routing of its gradient)
  (1) its value: v against the returns of his whole pay at gamma = layout "gamma" (0.9998, about two minutes), on every
      learner frame; the gradient reaches v, the GRU and inp (the hands' memory it reads is a number).
  (2) its bias: a clipped policy-gradient term of its own on the intention head, on the frames the intention was read,
      with the head's own advantage (GAE at gamma 0.9998 from v) and the hands' logits held fixed; in the hands' loss the
      bias is a number (the hands' advantage never moves the head through it, the head's never moves the hands).
  (3) its plan: plan_in is a layer of the hands and learns from their loss; the gradient that would go on into the head
      through the plan is cut (times --head2-plan-grad, 0 by default): the plan is the head's state as the head's own
      lessons shape it, and the hands learn to read it.
  The head's sequence is re-run in the learning step from the stored u of the rollout's ticks and the state at its start
  (truncated there: 48 ticks, 9.6 s, of backpropagation through time; its state itself is carried across rollouts).

Numpy only at the top level (the game server imports this file); torch inside the torch functions.
"""
import csv
import math
import os

import numpy as np

VERSION = 1
PARTS = ("brain", "trk", "trz", "ahead", "ctrl", "obs", "hands")
CTRL_SRCS = ("none", "belief", "both")                     # (the ctrl slot's source: sim/control.py's readouts by name)
CLIP = 10.0
# (group, input) of docs/INPUTS.csv; an input of None: every row of the group
OBS_SEL = (("self", "health"), ("self", "armor"), ("weapons", "owns "), ("weapons", "ammo: "),
           ("items", "nearest mega health: "), ("items", "nearest red armor: "),
           ("clock and score", None), ("v02 game", None), ("v02 items", None), ("intention", None))


def obs_cols(inputs_csv=None):
    """the indices of OBS_SEL's inputs in docs/INPUTS.csv (an input name ending in a space or ': ' is a prefix)"""
    if inputs_csv is None:
        inputs_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUTS.csv")
    out = []
    for r in csv.DictReader(open(inputs_csv, encoding="utf-8")):
        g, n = r["group"], r["input"]
        if "believed" in n:                                  # (the old rule-made belief stays out: v0.4.2's fade)
            continue
        for sg, sn in OBS_SEL:
            if g == sg and (sn is None or n == sn or (sn.endswith(" ") and n.startswith(sn))):
                out.append(int(r["index"]))
                break
    return sorted(out)


def layout(brain=256, trk=27, trz=28, ahead=0, ctrl=4, obs=None, hands=512, enc=256, size=256, inp=256, plan=64,
           n_target=17, every=8, gamma=0.9998, chrono=300, on=None, ctrl_src="none"):
    """the part's shape; kept in a checkpoint as "head2" (the gate is the state dict's head2.gate). obs: the input columns
    (obs_cols()); on: {part: 0 or 1} (default all on; a part off reads zeros)"""
    obs = [int(c) for c in (obs if obs is not None else obs_cols())]
    on_ = {p: 1 for p in PARTS}
    on_.update({str(k): int(v) for k, v in (on or {}).items()})
    w = dict(brain=int(brain), trk=int(trk), trz=int(trz), ahead=int(ahead), ctrl=int(ctrl), obs=len(obs), hands=int(hands))
    assert ctrl_src in CTRL_SRCS, "ctrl_src: one of {}".format(CTRL_SRCS)
    return dict(version=VERSION, widths=w, on=on_, obs_cols=obs, enc=int(enc), size=int(size), inp=int(inp), plan=int(plan),
                n_target=int(n_target), every=int(every), gamma=float(gamma), chrono=int(chrono), ctrl_src=str(ctrl_src))


def ctrl_src(L):
    """the ctrl slot's source ("none" for a layout made before it was wired)"""
    return str(L.get("ctrl_src", "none") or "none")


def u_width(L):
    return int(sum(L["widths"][p] for p in PARTS))


def n_weights(L):
    U, I, S, P, E, N, Hh = u_width(L), L["inp"], L["size"], L["plan"], L["enc"], L["n_target"], L["widths"]["hands"]
    return (U * I + I) + 3 * S * (I + S) + 6 * S + (S * P + P) + (P * E + E) + (S * N + N) + (S + Hh + 1)


def describe(L):
    return ("strategy head (v0.4.3): GRU {} a tick every {} frames ({:.2f} s) on {} numbers ({}), plan {} into the hands' "
            "input, a bias on {} intentions, its value at gamma {} ({:.0f} s); {:,} weights").format(
        L["size"], L["every"], L["every"] * 0.025, u_width(L),
        " + ".join("{} {}{}".format(p, L["widths"][p], "" if L["on"].get(p, 1) else " (off)") for p in PARTS if L["widths"][p]),
        L["plan"], L["n_target"], L["gamma"], 0.025 / max(1e-9, 1.0 - L["gamma"]), n_weights(L))


def _offs(L):
    o, out = 0, {}
    for p in PARTS:
        out[p] = (o, o + int(L["widths"][p]))
        o += int(L["widths"][p])
    return out


# ------------------------------------------------------------------------------------------------------------------ torch
def make_module(L, seed=4044):
    """the part: inp, gru (GRUCell), plan_out, plan_in (zeros), target (zeros), v; the buffer gate (0). From a random stream
    of its own (the global stream after it is the one without)"""
    import torch
    import torch.nn as nn

    class Head2(nn.Module):
        def __init__(self):
            super().__init__()
            S = int(L["size"])
            self.inp = nn.Linear(u_width(L), int(L["inp"]))
            self.gru = nn.GRUCell(int(L["inp"]), S)
            self.plan_out = nn.Linear(S, int(L["plan"]))
            self.plan_in = nn.Linear(int(L["plan"]), int(L["enc"]))
            self.target = nn.Linear(S, int(L["n_target"]))
            self.v = nn.Linear(S + int(L["widths"]["hands"]), 1)
            self.register_buffer("gate", torch.zeros(()))
            for l_ in (self.plan_in, self.target, self.v):
                nn.init.zeros_(l_.weight)
                nn.init.zeros_(l_.bias)
            tmax = int(L.get("chrono", 0))
            if tmax > 1:                                     # the update gate starts near 1 for long time scales (in ticks)
                with torch.no_grad():
                    tau = 1.0 + torch.rand(S) * (tmax - 1.0)
                    self.gru.bias_ih[S:2 * S] = torch.log((tau - 1.0).clamp(min=1e-3))
                    self.gru.bias_hh[S:2 * S] = 0.0

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return Head2()


def feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None):
    """u [B, u_width] (float32 holding half-precision numbers) from the parts (a part None or off: zeros). obs: his
    normalised inputs [B, all inputs] (the columns are taken here)"""
    import torch
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands)
    ref = next(v for v in src.values() if v is not None)
    B = ref.shape[0]
    cols = []
    for p in PARTS:
        w = int(L["widths"][p])
        if w == 0:
            continue
        v = src[p]
        if v is None or not L["on"].get(p, 1):
            cols.append(torch.zeros(B, w, device=ref.device))
            continue
        v = v.float()
        if p == "obs":
            v = v[:, torch.as_tensor(L["obs_cols"], dtype=torch.long, device=v.device)]
        if v.shape[1] != w:                                  # (ctrl: the readout's first columns, zeros past its end)
            v = v[:, :w] if v.shape[1] > w else torch.cat([v, v.new_zeros(B, w - v.shape[1])], 1)
        if p in ("trk", "trz", "ahead", "ctrl"):
            v = v.clamp(-CLIP, CLIP)
        cols.append(v)
    return torch.cat(cols, 1).half().float()


def outs(mod, s):
    """(plan, bias) of a state s [..., size]: the plan tanh(plan_out(s)), the bias with the gate applied (the plan's is applied
    where the hands read it: gate x plan_in(plan))"""
    import torch
    return torch.tanh(mod.plan_out(s)), mod.gate * mod.target(s)


def value(mod, s, h):
    import torch
    return mod.v(torch.cat([s, h], -1)).squeeze(-1)


def control_t(net, s_brain, hands=None, src="none"):
    """(the ctrl slot) the "in control" readout src ("belief": on the brain's state; "both": on the brain's state and the
    hands' memory) of the network's ModuleDict `control` -> [B, 4] its chances minus 0.5, a number (no_grad, detached);
    None (zeros in the slot) for "none" or a network without that readout"""
    import torch
    if src in (None, "none"):
        return None
    c = getattr(net, "control", None)
    if c is None or not hasattr(c, "keys") or src not in c.keys():
        return None
    with torch.no_grad():
        x = s_brain.detach().float()
        if src == "both":
            m = int(c[src][0].in_features) - x.shape[1]
            x = torch.cat([x, hands.detach()[:, :m].float()], 1)
        return (torch.sigmoid(c[src](x.half().float()).float()) - 0.5).detach()


class State:
    """the head's live state for n seats (the trainer's rollout): s, valid (outputs held: no reset since the last tick), the
    held plan and bias"""

    def __init__(self, n, L, dev):
        import torch
        self.L = L
        self.s = torch.zeros(n, int(L["size"]), device=dev)
        self.valid = torch.zeros(n, device=dev)
        self.plan = torch.zeros(n, int(L["plan"]), device=dev)
        self.bias = torch.zeros(n, int(L["n_target"]), device=dev)

    def refresh(self, mod):
        """before a rollout: the held outputs made again from the state with the weights and gate it is played at (the
        learning step makes the first segment's the same way)"""
        import torch
        with torch.no_grad():
            p, b = outs(mod, self.s)
            self.plan, self.bias = p * self.valid[:, None], b * self.valid[:, None]

    def adds(self, mod):
        """(what the hands' fast GRU input gets, what the intention's logits get) on this frame"""
        return mod.gate * mod.plan_in(self.plan) * self.valid[:, None], self.bias

    def tick(self, mod, u):
        import torch
        self.s = mod.gru(torch.tanh(mod.inp(u)), self.s)
        self.valid = torch.ones_like(self.valid)
        self.plan, self.bias = outs(mod, self.s)

    def reset(self, d):
        k = 1.0 - d
        self.s = self.s * k[:, None]
        self.valid = self.valid * k
        self.plan = self.plan * k[:, None]
        self.bias = self.bias * k[:, None]

    def snap(self):
        return self.s.clone(), self.valid.clone()


def seq(mod, L, U, dn, s0, v0, plan_grad=0.0):
    """the learning step over a rollout's whole sequences, the same numbers as the rollout's State frame by frame:
      U   [J, B, u]  the ticks' inputs as stored (J = T / every; tick j on frame j every + every - 1)
      dn  [T, B]     1 - done (a reset after that frame)
      s0, v0         the state and its valid flag at the rollout's start (State.snap(), after the reset of the frame before)
    -> dict gin [T, B, enc] (into the fast GRU's input), bias [T, B, n_target], s_held [T, B, size] (the state each frame's
    outputs read; zeros after a reset), alive [T, B], s [J, B, size], plan [J + 1, B, plan] (the held plans: the rollout's
    own first)"""
    import torch
    T, B = dn.shape
    K = int(L["every"])
    assert T % K == 0, (T, K)
    J = T // K
    s = s0
    S_l = [s0]
    for j in range(J):
        f0 = j * K
        keep = dn[max(f0 - 1, 0):f0 + K - 1].prod(0)       # no reset since the last tick (the rollout's start: s0 is after it)
        s = mod.gru(torch.tanh(mod.inp(U[j])), s * keep[:, None])
        S_l.append(s)
    St = torch.stack(S_l)                                    # [J + 1, B, size]: the state each segment's frames read
    P, Bi = outs(mod, St)
    al = []
    for j in range(J):
        f0 = j * K
        g = torch.cat([(v0 if j == 0 else dn[f0 - 1])[None], dn[f0:f0 + K - 1]], 0)
        al.append(torch.cumprod(g, 0))
    alive = torch.cat(al, 0)                                 # [T, B]
    idx = torch.arange(T, device=dn.device) // K
    am = alive[..., None]
    Pf = P[idx] * am
    if plan_grad != 1.0:                                     # (the gradient into the head through the plan, times plan_grad)
        Pf = Pf.detach() + plan_grad * (Pf - Pf.detach()) if plan_grad > 0 else Pf.detach()
    gin = mod.gate * mod.plan_in(Pf) * am
    return dict(gin=gin, bias=Bi[idx] * am, s_held=St[idx] * am, alive=alive, s=St[1:], plan=P)


def gae(rew, val, done, gamma, lam):
    """the head's advantages and returns: rew, done [T, B], val [T + 1, B]"""
    import torch
    T = rew.shape[0]
    adv = torch.zeros_like(rew)
    last = torch.zeros_like(rew[0])
    for t in reversed(range(T)):
        nt = 1.0 - done[t]
        dl = rew[t] + gamma * val[t + 1] * nt - val[t]
        last = dl + gamma * lam * nt * last
        adv[t] = last
    return adv, adv + val[:T]


def add_bias(lg, bias, i0):
    """his logits with the bias added to the intention's (its choices begin at i0)"""
    import torch
    n = bias.shape[-1]
    return torch.cat([lg[..., :i0], lg[..., i0:i0 + n] + bias, lg[..., i0 + n:]], -1)


# ------------------------------------------------------------------------------------------------------------------ numpy
def params_np(sd, prefix="head2."):
    out = {}
    for k, v in sd.items():
        if k.startswith(prefix):
            out[k[len(prefix):]] = np.asarray(v.cpu().numpy() if hasattr(v, "cpu") else v, np.float32)
    return out


def np_state_width(L):
    """per seat: [s (size) | valid]"""
    return int(L["size"]) + 1


def np_open(W):
    """the head acts (its gate above 0 and plan_in or target not all zero)"""
    return float(np.asarray(W.get("gate", 0.0))) > 0 and (np.abs(W["plan_in.weight"]).sum() + np.abs(W["plan_in.bias"]).sum()
                                                          + np.abs(W["target.weight"]).sum() + np.abs(W["target.bias"]).sum()) > 0


def np_adds(W, L, hs):
    """(the fast GRU input's addition [B, enc], the intention's bias [B, n_target]) from the state hs [B, np_state_width]"""
    S = int(L["size"])
    s, ok = hs[:, :S], hs[:, S:S + 1]
    g = np.float32(W.get("gate", 0.0))
    plan = np.tanh(s @ W["plan_out.weight"].T + W["plan_out.bias"]) * ok
    gin = g * (plan @ W["plan_in.weight"].T + W["plan_in.bias"]) * ok
    bias = g * (s @ W["target.weight"].T + W["target.bias"]) * ok
    return gin.astype(np.float32), bias.astype(np.float32)


def np_mlp(P, x):
    """Linear (2 arrays) or Linear-ReLU-Linear (4)"""
    if len(P) == 2:
        return x @ P[0].T + P[1]
    return np.maximum(x @ P[0].T + P[1], 0.0) @ P[2].T + P[3]


def mlp_of(sd, name):
    """a readout's arrays from a state dict: name.0/name.2 (Sequential) or name.weight (Linear); None if absent"""
    g = lambda k: np.asarray(sd[k].cpu().numpy() if hasattr(sd[k], "cpu") else sd[k], np.float32)
    if name + ".0.weight" in sd:
        return tuple(g("{}.{}.{}".format(name, i, w)) for i in (0, 2) for w in ("weight", "bias"))
    if name + ".weight" in sd:
        return (g(name + ".weight"), g(name + ".bias"))
    return None


def np_ctrl_params(sd, L):
    """(the ctrl slot, numpy) the arrays of the readout the layout names (Linear-ReLU-Linear), None for "none" or absent"""
    src = ctrl_src(L)
    if src == "none":
        return None
    return mlp_of(sd, "control." + src)


def np_ctrl(P, s_brain, hands=None):
    """control_t() in numpy: P from np_ctrl_params (None: None); hands: the hands' memory after the frame (for "both")"""
    if P is None:
        return None
    x = np.asarray(s_brain, np.float32)
    m = int(P[0].shape[1]) - x.shape[1]
    if m > 0:
        x = np.concatenate([x, np.asarray(hands, np.float32)[:, :m]], 1)
    x = x.astype(np.float16).astype(np.float32)
    return (1.0 / (1.0 + np.exp(-np_mlp(P, x))) - 0.5).astype(np.float32)


def np_feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None):
    """feats() in numpy"""
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands)
    B = len(next(v for v in src.values() if v is not None))
    cols = []
    for p in PARTS:
        w = int(L["widths"][p])
        if w == 0:
            continue
        v = src[p]
        if v is None or not L["on"].get(p, 1):
            cols.append(np.zeros((B, w), np.float32))
            continue
        v = np.asarray(v, np.float32)
        if p == "obs":
            v = v[:, np.asarray(L["obs_cols"], np.int64)]
        if v.shape[1] != w:
            v = v[:, :w] if v.shape[1] > w else np.concatenate([v, np.zeros((B, w - v.shape[1]), np.float32)], 1)
        if p in ("trk", "trz", "ahead", "ctrl"):
            v = np.clip(v, -CLIP, CLIP)
        cols.append(v)
    return np.concatenate(cols, 1).astype(np.float16).astype(np.float32)


def np_tick(W, L, u, hs):
    """a tick for these rows: u [m, u_width], hs [m, np_state_width] -> the state after"""
    S = int(L["size"])
    s = hs[:, :S]
    p = np.tanh(u @ W["inp.weight"].T + W["inp.bias"])
    gi = p @ W["gru.weight_ih"].T + W["gru.bias_ih"]
    gh = s @ W["gru.weight_hh"].T + W["gru.bias_hh"]
    r = 1.0 / (1.0 + np.exp(-(gi[:, :S] + gh[:, :S])))
    z = 1.0 / (1.0 + np.exp(-(gi[:, S:2 * S] + gh[:, S:2 * S])))
    n = np.tanh(gi[:, 2 * S:] + r * gh[:, 2 * S:])
    out = np.empty_like(hs)
    out[:, :S] = (1 - z) * n + z * s
    out[:, S] = 1.0
    return out.astype(np.float32)


def np_clear(L, hs, rows=None):
    r = slice(None) if rows is None else rows
    hs[r] = 0.0
    return hs

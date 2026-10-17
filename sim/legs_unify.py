"""One movement network, steps 3 and 4 (v0.4, branch um34): his legs' branch (LEGS_IN, B-253: 61 -> 256 -> 256 -> 17 in
the trainer's Policy as legs.0, legs.2, legs.4) reaches the rest of his network in two ways, each behind a trainer flag
that is off by default, each starting exactly where the network was.

  step 3, --legs-feat: the branch's second hidden layer (256 numbers, after its tanh) goes through a new layer
          "legs_door" (Linear 256 -> 256, at zero) and is added to his fast GRU's input on every frame (the branch is
          worked out on every frame for it, whether his legs drive or not). Only the GRU reads it: the slow memory, the
          head's running mean and the attention part see the encoder's numbers as before.
  step 4, --legs-guide: his own movement outputs (forward, sideways, vertical, turn, walk, zoom: LEGS_TAKES) get
          w_j * (the branch's choice mapped onto that output's bins, as log-probabilities), w a learnt number per output
          starting at 0: p_his ~ p_own * p_branch^w (a product of experts; w = 1 is the plain product). The mapping is
          the one _legs_step() uses to turn the branch's draws into his keys: forward and sideways bin for bin, the
          branch's jump (2) onto his vertical key's first two bins (his crouch, the third, never: the floor), the
          branch's nine turn bins onto his turn bins by duel_env's t_turn (the nearest of TURN; several of the branch's
          bins on one of his are summed), walk and zoom "off" (the branch lets them go). A bin the branch never gives
          reads FLOOR. The guide is added on every frame; it counts only where his own outputs drive (the trainer's
          head_masks drop the frames his legs moved him), so it acts on the frames with the switch off.
  Both: only on rows where the branch has a way (its inputs are not all zero: duel_env's legs_prep() gives zeros on
  the rows without one, legs_xok); elsewhere they add nothing. With legs_door at zero and w at zero every answer is
  the old one bit for bit (x + 0 = x). The branch's numbers are detached: neither lesson moves the branch (with
  --legs-learn the branch still learns from its own draws as before).

The layout ("legs_unify" in a checkpoint, as text in policy.npz) carries the mapping, so the numpy side needs nothing
of the simulator. Numpy only at the top (the plugins import this file on a game server); torch inside the t_ functions.
"""
import json

import numpy as np

OUTS = (0, 1, 2, 3, 7, 8)                 # his outputs the guide reaches (duel_env's LEGS_TAKES)
SRC = (0, 1, 2, 3, -1, -1)                # ... the branch's choice each is mapped from (-1: none, the branch lets it go)
BDIMS = (3, 3, 2, 9)                      # the branch's four choices: forward, sideways, jump, turn
FLOOR = -10.0                             # the log-probability a bin the branch never gives reads


def layout(action_dims, turn, turn_bins, feat, guide, enc=256, hid=256, gate=0, residual=0, mem=512):
    """the parts' layout: which are on, the mapping of each guided output ("M": [his bins, the branch's bins], or a
    column for an output the branch lets go: the chance of each of his bins)"""
    action_dims = [int(d) for d in action_dims]
    t_turn = np.abs(np.asarray(turn, np.float32)[None, :] - np.asarray(turn_bins, np.float32)[:, None]).argmin(1)
    M = []
    for o, s in zip(OUTS, SRC):
        hd = action_dims[o]
        if s < 0:
            m = np.zeros((hd, 1))
            m[0, 0] = 1.0                 # walk, zoom: "off" (their first bin) for certain
        elif s == 3:
            m = np.zeros((hd, BDIMS[3]))
            m[t_turn, np.arange(BDIMS[3])] = 1.0
        else:
            assert BDIMS[s] <= hd, (o, s, hd)
            m = np.zeros((hd, BDIMS[s]))
            m[np.arange(BDIMS[s]), np.arange(BDIMS[s])] = 1.0
        M.append(m.tolist())
    return dict(version=2, feat=int(bool(feat)), guide=int(bool(guide)), gate=int(bool(gate)), residual=int(bool(residual)),
                enc=int(enc), hid=int(hid), mem=int(mem), outs=list(OUTS), src=list(SRC), bdims=list(BDIMS), floor=FLOOR, M=M,
                action_dims=action_dims, motor=int(sum(action_dims[o] for o in OUTS)))


def as_layout(x):
    """a layout from a checkpoint's dict or policy.npz's text"""
    if x is None:
        return None
    if isinstance(x, (str, bytes, np.ndarray)):
        x = json.loads(str(x))
    x = dict(x)
    x.setdefault("gate", 0)
    x.setdefault("residual", 0)
    return x


def describe(lay):
    p = ["the legs' features into his fast GRU through legs_door"] if lay["feat"] else []
    p += ["the legs' guide on his movement outputs {}".format(lay["outs"])] if lay["guide"] else []
    p += ["the gate g(h) and the motor layer on his own movement outputs (v0.3.4 A)"] if lay.get("gate") else []
    p += ["the residual on his legs: (1 - a(h)) legs + W h (v0.3.4 B)"] if lay.get("residual") else []
    return "one movement network: " + "; ".join(p)


# ---- numpy ---------------------------------------------------------------------------------------------------------

def np_way(xl):
    """[B] float32: 1 where the branch has a way (its inputs are not all zero)"""
    return (np.abs(np.asarray(xl)).max(-1) > 0).astype(np.float32)


def np_branch(W6, xl):
    """the branch on its inputs: (the second hidden layer [B, 256], the logits [B, 17]). W6: w0, b0, w1, b1, wp, bp"""
    w0, b0, w1, b1, wp, bp = W6
    x = np.asarray(xl, np.float32)[:, :w0.shape[1]]          # (a branch without the three inputs of a look point: the old inputs come first)
    h2 = np.tanh(np.tanh(x @ w0.T + b0) @ w1.T + b1)
    return h2, h2 @ wp.T + bp


def np_door(Wd, bd, h2, ok):
    """what legs_door adds to his fast GRU's input [B, 256]"""
    return (h2 @ Wd.T + bd) * ok[:, None]


def np_guide_add(lay, w, lgl, ok, total):
    """what the guide adds to his logits [B, total]. w: [6] (the static guide) or [B, 6] (the gate g(h), v0.3.4 A)"""
    off = np.concatenate([[0], np.cumsum(lay["action_dims"])]).astype(int)
    bo = np.concatenate([[0], np.cumsum(lay["bdims"])]).astype(int)
    add = np.zeros((len(lgl), total), np.float32)
    for i, (o, s) in enumerate(zip(lay["outs"], lay["src"])):
        M = np.asarray(lay["M"][i], np.float32)
        if s < 0:
            q = np.broadcast_to(M[:, 0], (len(lgl), M.shape[0]))
        else:
            l_ = lgl[:, bo[s]:bo[s + 1]].astype(np.float32)
            e_ = np.exp(l_ - l_.max(-1, keepdims=True))     # (softmax as torch works it out)
            q = (e_ / e_.sum(-1, keepdims=True)) @ M.T
        wi = w[:, i:i + 1] if np.ndim(w) > 1 else w[i]
        add[:, off[o]:off[o + 1]] = wi * np.log(np.maximum(q, np.exp(lay["floor"]))) * ok[:, None]
    return add


def np_place(lay, v, total):
    """(v0.3.4 A) the motor layer's numbers [B, motor] in their outputs' places in his logits [B, total], zeros elsewhere"""
    off = np.concatenate([[0], np.cumsum(lay["action_dims"])]).astype(int)
    add = np.zeros((len(v), total), np.float32)
    j = 0
    for o in lay["outs"]:
        d = int(off[o + 1] - off[o])
        add[:, off[o]:off[o + 1]] = v[:, j:j + d]
        j += d
    return add


def np_gate_add(lay, Wg, bg, Wm, bm, z, h2, lgl, ok, total):
    """(v0.3.4 A, --legs-gate) what the gate and the motor layer add to his logits [B, total]: g(z) times the legs' choice
    mapped onto his bins, plus the motor layer of the legs' 256 numbers"""
    g = z @ Wg.T + bg
    return np_guide_add(lay, g, lgl, ok, total) + np_place(lay, (h2 @ Wm.T + bm) * ok[:, None], total)


def np_residual(Wa, ba, Wr, br, lgl, z):
    """(v0.3.4 B, --legs-residual) the legs' logits [B, 17] as his legs draw from them: (1 - a(z)) x the branch's + W z,
    a = clamp(Wa z + ba, 0, 1), one for each of the four choices"""
    a = np.clip(z @ Wa.T + ba, 0.0, 1.0)
    a = np.repeat(a, BDIMS, axis=-1)
    return ((1.0 - a) * lgl + (z @ Wr.T + br)).astype(np.float32)


# ---- torch ---------------------------------------------------------------------------------------------------------

def t_way(xl):
    return (xl.abs().amax(-1) > 0).float()


def t_branch(legs, xl):
    """(detached) the branch's second hidden layer and logits: legs is the trainer's nn.Sequential (legs.0 .. legs.4)"""
    import torch
    with torch.no_grad(), torch.autocast(device_type=xl.device.type, enabled=False):
        h2 = legs[:4](xl[..., :legs[0].in_features].float())   # (a branch narrower than the inputs: the old ones come first)
        return h2, legs[4](h2)


class GuideMaps:
    """the mapping matrices on a device, made once"""

    def __init__(self, lay, dev):
        import torch
        self.lay = lay
        self.M = [torch.tensor(m, dtype=torch.float32, device=dev) for m in lay["M"]]
        self.off = np.concatenate([[0], np.cumsum(lay["action_dims"])]).astype(int)
        self.bo = np.concatenate([[0], np.cumsum(lay["bdims"])]).astype(int)

    def mapped(self, lgl):
        """the branch's choices as log-probabilities over each guided output's bins: [(output, [..., its bins]), ...]"""
        import torch
        out = []
        for i, (o, s) in enumerate(zip(self.lay["outs"], self.lay["src"])):
            M = self.M[i]
            if s < 0:
                q = M[:, 0].expand(lgl.shape[:-1] + (M.shape[0],))
            else:
                q = torch.softmax(lgl[..., self.bo[s]:self.bo[s + 1]].float(), -1) @ M.t()
            out.append((o, torch.log(q.clamp(min=float(np.exp(self.lay["floor"]))))))
        return out

    def place(self, v):
        """(v0.3.4 A) the motor layer's numbers [..., motor] in their outputs' places in his logits, zeros elsewhere"""
        import torch
        parts, j = [], 0
        for o in range(len(self.off) - 1):
            d = int(self.off[o + 1] - self.off[o])
            if o in self.lay["outs"]:
                parts.append(v[..., j:j + d])
                j += d
            else:
                parts.append(torch.zeros(v.shape[:-1] + (d,), device=v.device, dtype=v.dtype))
        return torch.cat(parts, -1)

    def add(self, w, lgl, ok):
        """what the guide adds to his logits [..., total] (under the gradient of w only). w: [6], or [..., 6] (the gate)"""
        import torch
        mp = dict(self.mapped(lgl))
        parts = []
        for o in range(len(self.off) - 1):
            if o in mp:
                i = self.lay["outs"].index(o)
                parts.append((w[..., i:i + 1] if w.dim() > 1 else w[i]) * mp[o] * ok[..., None])
            else:
                parts.append(torch.zeros(lgl.shape[:-1] + (int(self.off[o + 1] - self.off[o]),), device=lgl.device))
        return torch.cat(parts, -1)


def t_residual(res_a, res, lgl, z):
    """(v0.3.4 B) the legs' logits as his legs draw from them: (1 - clamp(res_a(z), 0, 1)) x lgl + res(z)"""
    import torch
    a = res_a(z).clamp(0.0, 1.0)
    a = torch.repeat_interleave(a, torch.tensor(BDIMS, device=a.device), dim=-1)
    return (1.0 - a) * lgl + res(z)

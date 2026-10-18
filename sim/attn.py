"""v0.2, stage A of the attention model: the inputs cut into tokens, two attention blocks, a door into his memory.

What he is shown stays one flat list of inputs (docs/INPUTS.csv); this file says which inputs make which token
(layout_from_csv), holds the network part in torch for the trainer (make_module) and the same sums in plain numpy for
the checks and the game server (forward_np). The simulator's workers do not import it (no torch in a worker).

The shape, as timed on the rented server (tools/attention_timing_v16.py): every kind of token has its own first layer
to D numbers and every token a learned mark; block 1 lets every token look at every token (4 heads, then a feed-forward
part D -> 2D -> D); block 2 is worked out for two rows only, the summary token and his own; those 2D numbers go through
the door, a layer that starts at zero, and are added to what the old encoder gives his memory. With the door at zero
the network is the old one exactly."""
import csv
import os

import numpy as np

D_TOKEN, HEADS = 96, 4

# which groups of docs/INPUTS.csv make which kind of token (one token a kind unless it is split by the entity named
# before the colon of an input's name: "nearest mega health: forward" belongs to the token "nearest mega health")
ONE = [("self", ("self", "weapons", "own hands", "his movement", "his legs", "style", "hits", "grenade arc", "lead")),
       ("game", ("clock and score", "v02 game")),
       ("around", ("walls", "floor", "sight", "hazards", "place", "map reader", "v02 position")),
       ("enemy", ("enemy", "enemy shots", "enemy pain")),
       ("others", ("more enemies",)),
       ("believed", ("memory", "hearing", "v02 believed")),
       ("drop", ("dropped weapon",)),
       ("way", ("movement goal", "routes", "jump ahead", "intention")),
       ("sound", ("sounds",)),
       ("ways", ("b3 ways",))]                               # (stage B part 3: his way, and what the other ways are from here)
SPLIT = [("proj", ("projectiles",)), ("item", ("items", "more items", "v02 items")), ("place", ("v02 places",)),
         ("hold", ("b2 holds",))]                            # (stage B part 2: a token a holding place)
LATE = [("stack", ("v031 enemy stack",)),                  # (v0.3.1, B-257: the enemy's stack believed; after the split kinds, so
         ("rocket", ("v036 rocket aim",))]                   # that an older network's tokens keep their rows; v0.3.6: RL_AIM)
LATE_SPLIT = [("prefire", ("v036 prefire",))]               # (v0.3.6, PREFIRE: a token a pre-fire place; after the late kinds)
# A layout may say "gated": the network then carries "gate" among its weights (not trained: a buffer), a number a token
# (the summary token too) that is added to every look at that token before the softmax of both blocks. A network that
# is given new tokens answers as before while their gate is very negative (GATE_SHUT: nothing looks at them;
# tools/targets_init.py makes such a network and opens the gate). Every file of a run has its own gate: the league's
# older selves keep theirs shut when the learner's is opened. Not gated: the sums are what they were.
GATE_SHUT = -30.0
# (v0.4, the proposal's change 4; the trainer's --attn-mem-query) A layout may say "mem": H. Block 2's query for its read rows
# then also comes from his memory of the frame before (h_{t-1}, the fast GRU's state before this frame's step, read at half
# precision so that the trainer can keep it for the learning step): q = Wq norm(x) + mq(h_{t-1}), the layer mq at zero to
# begin with (the network answers exactly as without it). Not given h (forward(x) alone): as without it.


def layout_from_csv(path):
    """{"obs_dim", "D", "heads", "kinds": [{"name", "idx": [[input indices of one token] ...]}], "read": [summary row, his own row]}.
    Every input has exactly one token; a group this file does not know goes to a token "rest"."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    n = len(rows)
    used = np.zeros(n, bool)
    kinds = []
    for name, groups in ONE:
        idx = [int(r["index"]) for r in rows if r["group"] in groups]
        if idx:
            kinds.append(dict(name=name, idx=[idx]))
            used[idx] = True

    def split(name, groups):
        ent = {}
        for r in rows:
            if r["group"] in groups:
                key = r["input"].split(":")[0].strip()
                if r["group"] == "v02 items":                # "since he took: nearest mega health" belongs to that item's token
                    key = r["input"].split(":", 1)[1].strip()
                ent.setdefault(key, []).append(int(r["index"]))
        if ent:
            w = max(len(v) for v in ent.values())
            kinds.append(dict(name=name, idx=[v + [-1] * (w - len(v)) for v in ent.values()], names=list(ent.keys())))
            for v in ent.values():
                used[v] = True
    for name, groups in SPLIT:
        split(name, groups)
    for name, groups in LATE:
        idx = [int(r["index"]) for r in rows if r["group"] in groups]
        if idx:
            kinds.append(dict(name=name, idx=[idx]))
            used[idx] = True
    for name, groups in LATE_SPLIT:
        split(name, groups)
    rest = [i for i in range(n) if not used[i]]
    if rest:
        kinds.append(dict(name="rest", idx=[rest]))
    flat = [i for k in kinds for t in k["idx"] for i in t if i >= 0]
    assert sorted(flat) == list(range(n)), "an input is in no token or in two"
    n_tok = sum(len(k["idx"]) for k in kinds)
    self_row = [k["name"] for k in kinds].index("self")           # (the kinds before "self" would shift it: it is the first)
    assert self_row == 0
    return dict(obs_dim=n, D=D_TOKEN, heads=HEADS, kinds=kinds, read=[n_tok, 0], tokens=n_tok + 1)   # the summary token is the last row


def describe(lay):
    return "{} inputs in {} tokens (+ a summary): ".format(lay["obs_dim"], lay["tokens"] - 1) + ", ".join(
        "{} {}x{}".format(k["name"], len(k["idx"]), len(k["idx"][0])) for k in lay["kinds"])


def make_module(lay, out_dim=256, seed=0):
    """the torch part: .forward(x [B, obs_dim], already normalised) -> [B, out_dim], what the door lets through"""
    import torch
    import torch.nn as nn

    import torch.nn.functional as F_

    D, H_ = lay["D"], lay["heads"]
    AMP = os.environ.get("ATTN_AMP", "1") == "1"            # on the card the attention part is worked out at half precision (bfloat16):
                                                             # with whole sequences of 384 frames in an update it is what fills the card

    def norm(x):                                             # (x - mean) / sqrt(variance + 1e-5) over the last axis, no learned scale
        return F_.layer_norm(x, (x.shape[-1],), None, None, 1e-5)

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.q, self.k, self.v, self.o = (nn.Linear(D, D, bias=False) for _ in range(4))
            self.f1, self.f2 = nn.Linear(D, 2 * D, bias=False), nn.Linear(2 * D, D, bias=False)

        def forward(self, xq, xall, gate=None, qadd=None):
            B, Q, T = xq.shape[0], xq.shape[1], xall.shape[1]
            hd = D // H_
            q = self.q(norm(xq))
            if qadd is not None:                             # ("mem") the query's part from his memory of the frame before
                q = q + qadd
            q = q.view(B, Q, H_, hd).transpose(1, 2)
            na = norm(xall)
            k = self.k(na).view(B, T, H_, hd).transpose(1, 2)
            v = self.v(na).view(B, T, H_, hd).transpose(1, 2)
            y = xq + self.o(F_.scaled_dot_product_attention(q, k, v, attn_mask=None if gate is None else gate.to(q.dtype)[None, :])
                            .transpose(1, 2).reshape(B, Q, D))                                           # softmax(q k' / sqrt(hd) + gate) v
            return y + self.f2(F_.relu(self.f1(norm(y)), inplace=True))

    class Attn(nn.Module):
        def __init__(self):
            super().__init__()
            g = torch.Generator().manual_seed(seed)
            self.emb = nn.ModuleList([nn.Linear(len(k["idx"][0]), D, bias=False) for k in lay["kinds"]])
            for k_, e in zip(lay["kinds"], self.emb):
                self.register_buffer("idx_" + k_["name"], torch.tensor(k_["idx"], dtype=torch.long) % (lay["obs_dim"] + 1), persistent=False)   # -1 -> a column of zeros
                with torch.no_grad():
                    e.weight.copy_(torch.randn(e.weight.shape, generator=g) / max(1.0, e.weight.shape[1]) ** 0.5)
            self.mark = nn.Parameter(torch.randn(lay["tokens"], D, generator=g) * 0.1)
            self.b1, self.b2 = Block(), Block()
            for b in (self.b1, self.b2):
                for l in (b.q, b.k, b.v, b.o, b.f1, b.f2):
                    with torch.no_grad():
                        l.weight.copy_(torch.randn(l.weight.shape, generator=g) / l.weight.shape[1] ** 0.5 * (0.5 if l in (b.o, b.f2) else 1.0))
            self.door = nn.Linear(2 * D, out_dim, bias=False)
            nn.init.zeros_(self.door.weight)
            self.read = list(lay["read"])
            if lay.get("gated"):                                 # (see GATE_SHUT)
                self.register_buffer("gate", torch.zeros(lay["tokens"]))
            else:
                self.gate = None
            if lay.get("mem"):                                   # ("mem", see there) zeros: the exact start
                self.mq = nn.Linear(int(lay["mem"]), len(lay["read"]) * D)
                nn.init.zeros_(self.mq.weight)
                nn.init.zeros_(self.mq.bias)

        def forward(self, x, hm=None):
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=AMP and x.is_cuda):
                xp = torch.cat([x, x.new_zeros(x.shape[0], 1)], 1)
                toks = [e(xp[:, getattr(self, "idx_" + k_["name"])]) for k_, e in zip(lay["kinds"], self.emb)]
                t = torch.cat(toks + [x.new_zeros(x.shape[0], 1, D)], 1) + self.mark
                t = self.b1(t, t, self.gate)
                qa = None
                if hm is not None and getattr(self, "mq", None) is not None:
                    qa = self.mq(hm.half().float()).view(x.shape[0], len(self.read), D)
                r = self.b2(t[:, self.read], t, self.gate, qa)
                out = self.door(norm(r.reshape(x.shape[0], 2 * D)))
            return out.float()

    return Attn()


def params_np(sd, prefix="attn."):
    """the attention part's weights out of a state dict (numpy arrays), for forward_np"""
    return {k[len(prefix):]: (v.cpu().numpy() if hasattr(v, "cpu") else np.asarray(v)) for k, v in sd.items() if k.startswith(prefix)}


def _norm(x):
    m = x.mean(-1, keepdims=True)
    return (x - m) / np.sqrt(((x - m) ** 2).mean(-1, keepdims=True) + 1e-5)


def _block(P, b, xq, xall, heads, gate=None, qadd=None):
    B, Q, D = xq.shape
    T = xall.shape[1]
    hd = D // heads
    q = _norm(xq) @ P[b + ".q.weight"].T
    if qadd is not None:
        q = q + qadd
    q = q.reshape(B, Q, heads, hd).transpose(0, 2, 1, 3)
    na = _norm(xall)
    k = (na @ P[b + ".k.weight"].T).reshape(B, T, heads, hd).transpose(0, 2, 3, 1)
    v = (na @ P[b + ".v.weight"].T).reshape(B, T, heads, hd).transpose(0, 2, 1, 3)
    a = (q @ k) / np.sqrt(hd)
    if gate is not None:
        a = a + gate
    a = np.exp(a - a.max(-1, keepdims=True))
    a /= a.sum(-1, keepdims=True)
    y = xq + (a @ v).transpose(0, 2, 1, 3).reshape(B, Q, D) @ P[b + ".o.weight"].T
    return y + np.maximum(_norm(y) @ P[b + ".f1.weight"].T, 0.0) @ P[b + ".f2.weight"].T


def forward_np(lay, P, x, hm=None):
    """the same sums as make_module().forward in numpy: x [B, obs_dim] normalised -> [B, out_dim]. hm [B, H]: his memory of
    the frame before (a layout with "mem"; read at half precision as the torch side does)"""
    x = np.asarray(x, np.float32)
    xp = np.concatenate([x, np.zeros((len(x), 1), np.float32)], 1)
    toks = []
    for i, k in enumerate(lay["kinds"]):
        idx = np.asarray(k["idx"], np.int64) % (lay["obs_dim"] + 1)
        toks.append(xp[:, idx] @ P["emb.{}.weight".format(i)].T)
    t = np.concatenate(toks + [np.zeros((len(x), 1, lay["D"]), np.float32)], 1) + P["mark"]
    gate = np.asarray(P["gate"], np.float32) if lay.get("gated") else None
    t = _block(P, "b1", t, t, lay["heads"], gate)
    qa = None
    if hm is not None and lay.get("mem") and "mq.weight" in P:
        h16 = np.asarray(hm, np.float32).astype(np.float16).astype(np.float32)
        qa = (h16 @ np.asarray(P["mq.weight"], np.float32).T + P["mq.bias"]).reshape(len(x), len(lay["read"]), lay["D"])
    r = _block(P, "b2", t[:, lay["read"]], t, lay["heads"], gate, qa)
    return _norm(r.reshape(len(x), -1)) @ P["door.weight"].T

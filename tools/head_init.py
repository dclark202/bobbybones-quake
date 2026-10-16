"""Gives a network the head of v0.4 (sim/head.py; docs/v0.4/BUILD_v0.4.md) with its links at zero: it plays exactly as before.

    python tools/head_init.py <in.pt> <out.pt> [--head default|<layout json or file>|none] [--seed 0] [--attn-mem-query]
                              [--ordered-heads]
    python tools/head_init.py --same <a.pt> <b.pt> [--frames 2400] [--players 16] [--obs <raw inputs .npy>]
                                                   (do two networks answer alike? every output, frame by frame)

The part goes into the state dict under "head." (plan_in, target, way, win and its aux answers all zeros), its layout into the
file ("head"): his fast memory's and encoder's widths, the intention's and the way's outputs (the simulator's INTENT_HEAD 10
and WAY_HEAD 12) and the guessing questions the network has (its aux.* layers) are read from the network. The trainer gives a
league file without the part one with its links at zero as it loads it; the checks' tools and the export read only what is
in the file. A network that has the part already is refused.
--attn-mem-query: the attention part's second block also queried by his memory of the frame before, its layer at zero
(sim/attn.py "mem"; the trainer's --attn-mem-query). --ordered-heads: his intention, way, legs switch and weapon key drawn
in that order, each with a table at zero of the choice before it (the trainer's --ordered-heads). --head none: only those.

--same runs both networks in torch on the processor over the same inputs: random normalised inputs (or rows of raw inputs
from --obs, normalised by each network's own statistics), random inputs of his legs' branch and random events, with resets
(a share of the players every frame and all of them at frame 1000); his memory, the head's state and the store carried as in
play. It prints the largest difference of each output (his logits with the head's part added, the values, the guessing
answers with the head's, his legs' logits, his fast memory) and exits 0 when the largest of all is below 1e-6."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

INTENT_HEAD, WAY_HEAD = 10, 12                               # (duel_env's: his intention's output and his way's)


def head_layout(ck, spec="default"):
    """the head's layout for this network: spec's sizes, the network's widths and outputs"""
    import head as H_
    sd = ck["model"]
    ad = tuple(ck["action_dims"])
    aux = {k[4:-7]: int(v.shape[0]) for k, v in sd.items() if k.startswith("aux.") and k.endswith(".weight") and k.count(".") == 2}
    kw = {k_: v_ for k_, v_ in H_.as_layout(spec).items() if k_ != "version"} if spec != "default" else {}
    kw.update(fast=int(sd["gru.weight_hh"].shape[1]), enc=int(sd["gru.weight_ih"].shape[1]), n_target=int(ad[INTENT_HEAD]),
              n_way=int(ad[WAY_HEAD]) if len(ad) > WAY_HEAD else 1, aux=aux)
    return H_.layout(**kw)


LEGS_HEAD, WEAPON_HEAD = 11, 6


def convert(src, dst, spec="default", seed=0, mem=False, ordered=False):
    import torch
    import head as H_
    ck = torch.load(src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    said = []
    if spec != "none":
        assert ck.get("head") is None, "{} has a head already".format(src)
        assert ck.get("slow") is None, "{} has the slow memory: the head beside it is not built".format(src)
        lay = head_layout(ck, spec)
        for k, v in H_.make_module(lay, seed).state_dict().items():
            sd["head." + k] = v
        ck["head"] = lay
        said.append("{}; weights {}".format(H_.describe(lay), sum(int(np.prod(v.shape)) for k, v in sd.items() if k.startswith("head."))))
    if mem:
        assert ck.get("attn") is not None and not ck["attn"].get("mem"), "--attn-mem-query: no attention part, or it has the query already"
        Hd = int(sd["gru.weight_hh"].shape[1])
        ck["attn"] = dict(ck["attn"], mem=Hd)
        sd["attn.mq.weight"] = torch.zeros(len(ck["attn"]["read"]) * int(ck["attn"]["D"]), Hd)
        sd["attn.mq.bias"] = torch.zeros(len(ck["attn"]["read"]) * int(ck["attn"]["D"]))
        said.append("the attention part's memory query (at zero)")
    if ordered:
        assert not ck.get("ordered"), "--ordered-heads: the network has them already"
        ad = tuple(ck["action_dims"])
        ck["ordered"] = [[INTENT_HEAD, WAY_HEAD], [WAY_HEAD, LEGS_HEAD], [LEGS_HEAD, WEAPON_HEAD]]
        for p_, c_ in ck["ordered"]:
            sd["order.t{}.weight".format(c_)] = torch.zeros(ad[p_], ad[c_])
        said.append("ordered outputs {} (tables at zero)".format(ck["ordered"]))
    torch.save(ck, dst)
    print("{} -> {}: {}".format(os.path.basename(src), os.path.basename(dst), "; ".join(said)))


def make_net(ck):
    """the whole network of a checkpoint in torch (the trainer's Policy without the trainer): encoder, attention part, fast
    GRU, outputs, values, guessing answers, his legs' branch, the head"""
    import torch
    import torch.nn as nn
    import head as H_
    sd = ck["model"]
    obs, Hd, ad = int(ck["obs_dim"]), int(ck["hidden"]), tuple(ck["action_dims"])
    assert ck.get("slow") is None and not ck.get("cells"), "a network with the slow memory or map cells: not for this tool"

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            if ck.get("attn") is not None:
                import attn as A_
                self.attn = A_.make_module(ck["attn"], 256)
            else:
                self.attn = None
            self.enc = nn.Sequential(nn.Linear(obs, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
            self.gru = nn.GRUCell(256, Hd)
            self.pi = nn.Linear(Hd, sum(ad))
            self.v = nn.Linear(Hd, 1)
            if "v2.weight" in sd:
                self.v2 = nn.Linear(Hd, 2)
            if "legs.0.weight" in sd:
                self.legs = nn.Sequential(nn.Linear(sd["legs.0.weight"].shape[1], 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh(),
                                          nn.Linear(256, sd["legs.4.weight"].shape[0]))
            names = sorted({k.split(".")[1] for k in sd if k.startswith("aux.")})
            if names:
                self.aux = nn.Module()
                for n_ in names:
                    setattr(self.aux, n_, nn.Linear(Hd, sd["aux.{}.weight".format(n_)].shape[0]))
            self.head = H_.make_module(ck["head"]) if ck.get("head") is not None else None
            if ck.get("ordered"):
                self.order = nn.Module()
                for p_, c_ in ck["ordered"]:
                    setattr(self.order, "t{}".format(c_), nn.Embedding(ad[p_], ad[c_]))

    net = Net()
    net.load_state_dict(sd, strict=True)
    net.eval()
    net.lay = ck.get("head")
    net.ad = ad
    net.ordered = [tuple(p_) for p_ in ck.get("ordered") or []]
    return net


def draw_u(l, u):
    """a choice from logits l [B, n] with the uniform numbers u [B], as plugins/netpass.py draws"""
    p = np.exp(l - l.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    return (p.cumsum(1) > u[:, None]).argmax(1)


def same(a, b, frames=2400, players=16, obs_file=None, seed=1):
    import torch
    import head as H_
    torch.set_num_threads(1)
    cka = torch.load(a, weights_only=False, map_location="cpu")
    ckb = torch.load(b, weights_only=False, map_location="cpu")
    assert int(cka["obs_dim"]) == int(ckb["obs_dim"]) and tuple(cka["action_dims"]) == tuple(ckb["action_dims"]), "different shapes"
    na, nb = make_net(cka), make_net(ckb)
    obs_dim, ad = int(cka["obs_dim"]), tuple(cka["action_dims"])
    I0, W0 = sum(ad[:INTENT_HEAD]), sum(ad[:WAY_HEAD]) if len(ad) > WAY_HEAD else -1
    rng = np.random.default_rng(seed)
    raw = np.load(obs_file).astype(np.float32) if obs_file else None
    dev = torch.device("cpu")

    def norm(ck, o):
        return np.clip((o - ck["obs_mean"]) / np.sqrt(ck["obs_var"] + 1e-8), -10, 10).astype(np.float32)

    sts = [H_.State(players, n.lay, dev) if n.head is not None else None for n in (na, nb)]
    hs = [torch.zeros(players, int(c["hidden"])) for c in (cka, ckb)]
    ev_w = max([n.lay["ev"] for n in (na, nb) if n.lay] or [32])
    legs_d = na.legs[0].in_features if hasattr(na, "legs") else 0
    worst = {}

    def upd(k, x, y):
        worst[k] = max(worst.get(k, 0.0), float((x - y).abs().max()))

    def frame(i_, net, ck, x, xl, ev):
        with torch.no_grad():
            st, h = sts[i_], hs[i_]
            xx = torch.from_numpy(x)
            e = net.enc(xx)
            if net.attn is not None:
                e = e + net.attn(xx, hm=h)                  # (a layout with "mem": his memory of the frame before)
            if net.head is not None:
                h = net.gru(e + net.head.plan_in(st.plan), h)
                _, ta, wa = H_.live(net.head, st, e, h, ev[:, :net.lay["ev"]])
            else:
                h = net.gru(e, h)
            lg = net.pi(h)
            if net.head is not None:
                lg = torch.cat([lg[:, :I0], lg[:, I0:I0 + ta.shape[1]] + ta, lg[:, I0 + ta.shape[1]:W0], lg[:, W0:W0 + wa.shape[1]] + wa,
                                lg[:, W0 + wa.shape[1]:]], 1) if W0 >= 0 else torch.cat([lg[:, :I0], lg[:, I0:I0 + ta.shape[1]] + ta,
                                                                                          lg[:, I0 + ta.shape[1]:]], 1)
            if net.ordered:                                  # (--ordered-heads) drawn in order with the same numbers in both networks:
                o_ = np.concatenate([[0], np.cumsum(ad)]).astype(int)       # the logits each was drawn from (a choice before is
                ac_ = torch.zeros(len(lg), len(ad), dtype=torch.long)     # the same where the logits are)
                for j in range(len(ad)):
                    ac_[:, j] = torch.from_numpy(draw_u(lg[:, o_[j]:o_[j + 1]].numpy(), U[:, j]))
                lg = lg.clone()
                for p_, c_ in net.ordered:
                    lg[:, o_[c_]:o_[c_ + 1]] += getattr(net.order, "t{}".format(c_))(ac_[:, p_])
                    ac_[:, c_] = torch.from_numpy(draw_u(lg[:, o_[c_]:o_[c_ + 1]].numpy(), U[:, c_]))
            out = dict(logits=lg, v=net.v(h), h=h)
            if hasattr(net, "v2"):
                out["v2"] = net.v2(h)
            if hasattr(net, "legs"):
                out["legs"] = net.legs(torch.from_numpy(xl))
            if hasattr(net, "aux"):
                for n_, l_ in net.aux.named_children():
                    o_ = l_(h)
                    if net.head is not None and hasattr(net.head.aux, n_):
                        o_ = o_ + getattr(net.head.aux, n_)(st.s)
                    out["aux." + n_] = o_
            hs[i_] = h
            return out

    for f_ in range(frames):
        U = rng.random((players, len(ad)))
        if raw is not None:
            o = raw[rng.integers(0, len(raw), players)]
            xa, xb = norm(cka, o), norm(ckb, o)
        else:
            xa = np.clip(rng.standard_normal((players, obs_dim)) * 1.5, -10, 10).astype(np.float32)
            xb = xa
        xl = rng.standard_normal((players, max(1, legs_d))).astype(np.float32)
        ev = torch.from_numpy(rng.standard_normal((players, ev_w)).astype(np.float32))
        oa = frame(0, na, cka, xa, xl, ev)
        ob = frame(1, nb, ckb, xb, xl, ev)
        for k_ in set(oa) & set(ob):
            upd(k_, oa[k_], ob[k_])
        d = (rng.random(players) < 0.004).astype(np.float32)
        if f_ == 1000:
            d[:] = 1.0
        dt = torch.from_numpy(d)
        for i_ in range(2):
            hs[i_] = hs[i_] * (1.0 - dt)[:, None]
            if sts[i_] is not None:
                sts[i_].reset(dt)
    big = max(worst.values())
    print("{} and {}: {} frames x {} players ({} inputs), resets {:.1%} a frame and all at frame 1000".format(
        os.path.basename(a), os.path.basename(b), frames, players, "recorded" if raw is not None else "random", 0.004))
    for k_ in sorted(worst):
        print("  {:10s} largest difference {:.3g}".format(k_, worst[k_]))
    for i_, (n_, st) in enumerate(zip((a, b), sts)):
        if st is not None:
            print("  {}: head ticks {}, slots written in the store now {} of {}".format(
                os.path.basename(n_), st.g // st.lay["every"], int((st.age1 > 0).sum()), st.age1.numel()))
    print("largest of all {:.3g}: {}".format(big, "THE SAME" if big < 1e-6 else "DIFFERENT"))
    return big


if __name__ == "__main__":
    args = sys.argv[1:]

    def opt(name, d):
        return type(d)(args[args.index(name) + 1]) if name in args else d
    if args and args[0] == "--same":
        b_ = same(args[1], args[2], frames=opt("--frames", 2400), players=opt("--players", 16), obs_file=opt("--obs", "") or None)
        sys.exit(0 if b_ < 1e-6 else 1)
    convert(args[0], args[1], spec=opt("--head", "default"), seed=opt("--seed", 0), mem="--attn-mem-query" in args,
            ordered="--ordered-heads" in args)

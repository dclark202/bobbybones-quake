"""Does an event record foretell what a pro demo shows next? Three models of about one size on the samples of
tools/demo_events.py, compared on demos held out and on maps never trained on (docs/design/v16_event_record.md).
None of Bobby's outputs is trained here: the targets are what the demo shows after the frame.

    python tools/event_pretrain.py --data <folder> --model events --minutes 10     # the Anaconda Python (GPU PyTorch)
    python tools/event_pretrain.py --data <folder> --model mlp --minutes 5
    python tools/event_pretrain.py --data <folder> --model gru --minutes 8 [--bptt 32 --tag gru_short]
    python tools/event_pretrain.py --data <folder> --model events --record split --tag events_split
    python tools/event_pretrain.py --data <folder> --model both --record split --bptt 128 --streams 64
    python tools/event_pretrain.py --data <folder> --model events --load --ablate   # which events carry it
    python tools/event_pretrain.py --report                                         # the tables, from the saved results

  events   tokens = the now vector and 16 events (kind and weapon as learned vectors, the place relative to him now,
           the age on a log scale, the facts); two self-attention blocks of width 96 with 4 heads; read out at the now
           token. --record plain: the last 16 events. --record split: the last 8 of the frequent kinds (sightings,
           hurt, fired) and the last 8 of the rare ones (pickups, died, spawned)
  mlp      no memory: the now vector alone
  gru      the memory he has today: a GRU of 256 stepped over the now vectors of a chain row by row (five a second),
           its state carried from the chain's first row; trained through --bptt rows (256 = 51 s; 32 = 6.4 s, the
           reach of his training today)
  both     v16's arrangement: the record's read-out enters the same GRU's input through an adapter that starts at zero
Every model also gets a learned vector for the map (a map never trained on, and one training row in ten, gets the
"unknown map" vector; for the models with a state it is one chain in ten, anew each pass). Weights and results: data/sim_runs/event_pretrain/<tag>.pt and results_<tag>.json.

Split: the demos of the six training maps by pair of players (both recordings of one game on one side), one pair in
ten held out; the maps of HELD_MAPS are never trained on.
"""
import argparse
import glob
import heapq
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import demo_events as DE                                                    # noqa: E402

HELD_MAPS = ("campgrounds", "hektik", "toxicity", "cure")
OUT_DIR = os.path.join(ROOT, "data", "sim_runs", "event_pretrain")
K_EVENTS = 16
NK = len(DE.EVENT_KINDS)
N_EVNUM = 3 + 1 + 2 + 3 + 4 * NK
# the outputs: a_time 6, a_where 3, b_kind 4, b_time 6, c_hurt 1, d_die 1, e_where 3
S_AT, S_AW, S_BK, S_BT, S_C, S_D, S_EW = slice(0, 6), slice(6, 9), slice(9, 13), slice(13, 19), 19, 20, slice(21, 24)
N_OUT = 24
W_WHERE = 5.0                                                               # weight of the two place losses
SINCE_BINS = ((0.0, 1.0, "under 1 s"), (1.0, 4.0, "1-4 s"), (4.0, 16.0, "4-16 s"), (16.0, 1e9, "over 16 s or never"))
ROW_KEYS = ("now", "t", "ls", "since", "seen", "live", "ev_n", "ev_ns", "a_time", "a_where", "b_kind", "b_time", "c_hurt",
            "d_die", "e_ok", "e_where", "pos")


def load(data_dir, device, torch, limit_rows=0):
    """every map's file into one set of tensors on the device; rows carry their chain, map and split
    (0 train, 1 demos held out, 2 a map never trained on)"""
    files = sorted(glob.glob(os.path.join(data_dir, "*.npz")))
    names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    train_maps = [m for m in names if m not in HELD_MAPS]
    rows = {k: [] for k in ROW_KEYS}
    extra = {k: [] for k in ("chain", "map", "mapname", "split", "ev_lo", "f_lo", "s_lo")}
    events, chains, fast, slow = [], [], [], []
    r_off = e_off = c_off = f_off = s_off = 0
    for mi, (f, mp) in enumerate(zip(files, names)):
        z = np.load(f)
        ch = z["chains"]                           # demo, first row, rows, first event, events, first fast, first slow
        held = mp in HELD_MAPS
        sp = np.full(len(ch), 2, np.int8) if held else (z["pair"][ch[:, 0]] % 10 == 0).astype(np.int8)
        n = int(ch[:, 2].sum())
        for k in ROW_KEYS:
            rows[k].append(z[k])
        extra["chain"].append(np.repeat(np.arange(len(ch)) + c_off, ch[:, 2]).astype(np.int32))
        extra["map"].append(np.full(n, 0 if held else 1 + train_maps.index(mp), np.int8))
        extra["mapname"].append(np.full(n, mi, np.int8))
        extra["split"].append(np.repeat(sp, ch[:, 2]))
        extra["ev_lo"].append(np.repeat(ch[:, 3] + e_off, ch[:, 2]).astype(np.int32))
        extra["f_lo"].append(np.repeat(ch[:, 5] + f_off, ch[:, 2]).astype(np.int32))
        extra["s_lo"].append(np.repeat(ch[:, 6] + s_off, ch[:, 2]).astype(np.int32))
        events.append(z["events"])
        fast.append(z["ev_fast"] + e_off)
        slow.append(z["ev_slow"] + e_off)
        chains.append(np.stack([ch[:, 1] + r_off, ch[:, 2], sp, np.full(len(ch), mi)], 1))
        r_off += n
        e_off += len(z["events"])
        f_off += len(z["ev_fast"])
        s_off += len(z["ev_slow"])
        c_off += len(ch)
    D = {}
    for k in ROW_KEYS:
        a = np.concatenate(rows[k])
        D[k] = torch.from_numpy(a).to(device)
    for k in extra:
        D[k] = torch.from_numpy(np.concatenate(extra[k])).to(device)
    D["ev_hi"] = D["ev_lo"] + D["ev_n"]
    D["events"] = torch.from_numpy(np.concatenate(events)).to(device)
    D["ev_fast"] = torch.from_numpy(np.concatenate(fast).astype(np.int64)).to(device)
    D["ev_slow"] = torch.from_numpy(np.concatenate(slow).astype(np.int64)).to(device)
    D["chains"] = np.concatenate(chains)                                   # first row, rows, split, map number
    D["maps"], D["train_maps"] = names, train_maps
    tr = (D["split"] == 0).nonzero().squeeze(1)
    pick = tr[torch.randint(len(tr), (min(len(tr), 1000000),), device=device, generator=torch.Generator(device).manual_seed(1))]
    x = D["now"][pick].float()
    D["mu"], D["sd"] = x.mean(0), x.std(0).clamp(min=0.05)
    return D


def base_rates(D, torch):
    """what the trivial guesses need, from the training rows: how often each bucket, the mean offsets"""
    tr = D["split"] == 0
    b = {}
    for k, n in (("a_time", 6), ("b_kind", 4), ("b_time", 6)):
        y = D[k][tr]
        c = torch.bincount(y[y >= 0].long(), minlength=n).float()
        b[k] = c / c.sum()
    for k in ("c_hurt", "d_die"):
        y = D[k][tr]
        b[k] = (y[y >= 0] == 1).float().mean()
    m = tr & (D["a_time"] >= 0) & (D["a_time"] < 5)
    b["a_where"] = D["a_where"][m].float().mean(0)
    b["e_where"] = D["e_where"][tr & D["e_ok"]].float().mean(0)
    return b


def record(D, rows, torch, split=False, max_age=None, drop_kind=None, keep=K_EVENTS, part=None):
    """the 16 events of each row's record as numbers, kind, weapon and a mask. plain: the last 16 known at the row.
    split: the last 8 of the frequent kinds (sightings, hurt, fired) and the last 8 of the rare ones (pickups, died,
    spawned). The enemy's loss of the last half second (not yet an event) stands as the newest of the frequent ones."""
    dev = rows.device
    K = K_EVENTS
    ar = torch.arange(K, device=dev)
    live = D["live"][rows]
    sh = live.long()[:, None]
    if split:
        h = K // 2
        ns = D["ev_ns"][rows].long()
        nf = D["ev_n"][rows].long() - ns
        flo, slo = D["f_lo"][rows].long(), D["s_lo"][rows].long()
        i_f = (flo + nf)[:, None] - h + ar[None, :h] + sh
        i_s = (slo + ns)[:, None] - h + ar[None, :h]
        vf = (i_f >= flo[:, None]) & (i_f < (flo + nf)[:, None])
        vs = i_s >= slo[:, None]
        valid = torch.cat([vf, vs], 1)
        idx = torch.cat([D["ev_fast"][i_f.clamp(0, len(D["ev_fast"]) - 1)], D["ev_slow"][i_s.clamp(min=0)]], 1)
        slot = h - 1
    else:
        hi, lo = D["ev_hi"][rows].long(), D["ev_lo"][rows].long()
        idx = hi[:, None] - K + ar[None] + sh
        valid = (idx >= lo[:, None]) & (idx < hi[:, None])
        slot = K - 1
    ev = D["events"][idx.clamp(0, len(D["events"]) - 1)]
    te, kind, wid = ev[..., 1].clone(), ev[..., 2].long(), ev[..., 3].long()
    epos, facts = ev[..., 4:7].clone(), ev[..., 7:11].clone()
    t, since = D["t"][rows], D["since"][rows]
    r = live.nonzero().squeeze(1)
    if len(r):
        ls = D["ls"][rows[r]].float()
        te[r, slot] = t[r] - since[r]
        kind[r, slot] = DE.E_OUT
        wid[r, slot] = ls[:, 6].long()
        epos[r, slot] = ls[:, 0:3] * 1000
        facts[r, slot, :3] = ls[:, 3:6]
        facts[r, slot, 3] = ls[:, 7]
        valid[r, slot] = True
    age = (t[:, None] - te).clamp(min=0)
    if max_age is not None:
        valid = valid & (age <= max_age)
    if drop_kind is not None:
        valid = valid & (kind != drop_kind)
    if keep < K:                                                            # plain: only the newest `keep`
        valid[:, :K - keep] = False
    if part == "rare":
        valid[:, :K // 2] = False
    if part == "frequent":
        valid[:, K // 2:] = False
    kind = torch.where(valid, kind, torch.zeros_like(kind))
    wid = torch.where(valid, wid, torch.zeros_like(wid))
    rel = (epos - D["pos"][rows][:, None]) / 1000
    oh = torch.nn.functional.one_hot(kind, NK).float()
    num = torch.cat([rel, rel.norm(dim=-1, keepdim=True), (torch.log1p(age) / math.log1p(120.0))[..., None],
                     (age.clamp(max=10) / 10)[..., None], epos / 1000, (oh[..., None] * facts[..., None, :]).flatten(-2)], -1)
    return num * valid[..., None], kind, wid, valid


def build(kind, torch, n_maps, hidden=256, split=False):
    nn = torch.nn

    class Front(nn.Module):
        """the now vector, made standard, beside a learned vector for the map"""
        def __init__(self):
            super().__init__()
            self.mapv = nn.Embedding(n_maps + 1, 16)
            self.n_in = DE.N_NOW + 16
            self.salt = None                # a number a pass: the models with a state lose the map for whole chains

        def front(self, D, rows):
            m = D["map"][rows].long()
            if self.training and self.salt is None:
                m = torch.where(torch.rand(len(rows), device=rows.device) < 0.1, torch.zeros_like(m), m)
            elif self.training:
                c = D["chain"][rows].long()
                m = torch.where((c * 7919 + self.salt) % 10 == 0, torch.zeros_like(m), m)
            return torch.cat([(D["now"][rows].float() - D["mu"]) / D["sd"], self.mapv(m)], 1)

    class Events(Front):
        def __init__(self, width=96, heads=4, blocks=2, head=True):
            super().__init__()
            self.width = width
            self.now = nn.Linear(self.n_in, width)
            self.evn = nn.Linear(N_EVNUM, width)
            self.kind = nn.Embedding(NK + 1, width)
            self.wpn = nn.Embedding(len(DE.WEAPONS) + 1, width)
            layer = nn.TransformerEncoderLayer(width, heads, 2 * width, dropout=0.0, activation="gelu", batch_first=True,
                                               norm_first=True)
            self.enc = nn.TransformerEncoder(layer, blocks, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(width)
            if head:
                self.out = nn.Linear(width, N_OUT)
            self.rec = {}

        def read(self, D, rows, x=None):
            """the now token's row after the attention blocks: what the record says about this moment"""
            num, kind, wid, valid = record(D, rows, torch, split=split, **self.rec)
            x = self.front(D, rows) if x is None else x
            tok = torch.cat([(self.now(x) + self.kind.weight[NK])[:, None], self.evn(num) + self.kind(kind) + self.wpn(wid)], 1)
            mask = torch.cat([torch.zeros(len(rows), 1, dtype=torch.bool, device=rows.device), ~valid], 1)
            return self.norm(self.enc(tok, src_key_padding_mask=mask)[:, 0])

        def forward(self, D, rows):
            return self.out(self.read(D, rows))

    class Mlp(Front):
        def __init__(self, width=320):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(self.n_in, width), nn.GELU(), nn.Linear(width, width), nn.GELU(),
                                     nn.Linear(width, width), nn.GELU(), nn.Linear(width, N_OUT))

        def forward(self, D, rows):
            return self.net(self.front(D, rows))

    class Gru(Front):
        def __init__(self):
            super().__init__()
            self.enc = nn.Sequential(nn.Linear(self.n_in, 128), nn.Tanh())
            self.gru = nn.GRU(128, hidden, batch_first=True)
            self.out = nn.Linear(hidden, N_OUT)

        def forward(self, D, rows, h):
            """rows: (streams, steps), -1 where a stream has nothing; h: the state carried in"""
            B, T = rows.shape
            ok = rows >= 0
            x = self.front(D, rows.clamp(min=0).flatten()).view(B, T, -1) * ok[..., None]
            y, h = self.gru(self.enc(x), h)
            return self.out(y), h

    class Both(Events):
        """the proposed arrangement: the record's read-out enters the GRU's input through an adapter that starts at zero"""
        def __init__(self):
            super().__init__(head=False)
            self.inp = nn.Sequential(nn.Linear(self.n_in, 128), nn.Tanh())
            self.adapt = nn.Linear(self.width, 128)
            nn.init.zeros_(self.adapt.weight)
            nn.init.zeros_(self.adapt.bias)
            self.gru = nn.GRU(128, hidden, batch_first=True)
            self.out = nn.Linear(hidden, N_OUT)

        def forward(self, D, rows, h):
            B, T = rows.shape
            ok = rows >= 0
            flat = rows.clamp(min=0).flatten()
            x = self.front(D, flat)
            z = self.inp(x) + self.adapt(self.read(D, flat, x))
            y, h = self.gru(z.view(B, T, -1) * ok[..., None], h)
            return self.out(y), h

    return {"events": Events, "mlp": Mlp, "gru": Gru, "both": Both}[kind]()


def losses(out, D, rows, torch):
    F = torch.nn.functional
    z = out.sum() * 0.0
    L = {}
    y = D["a_time"][rows].long()
    m = y >= 0
    L["a_time"] = F.cross_entropy(out[m][:, S_AT], y[m]) if m.any() else z
    m = (y >= 0) & (y < 5)
    L["a_where"] = F.smooth_l1_loss(out[m][:, S_AW], D["a_where"][rows[m]].float(), beta=0.1) * 3 if m.any() else z
    y = D["b_kind"][rows].long()
    m = y >= 0
    L["b_kind"] = F.cross_entropy(out[m][:, S_BK], y[m]) if m.any() else z
    y = D["b_time"][rows].long()
    m = y >= 0
    L["b_time"] = F.cross_entropy(out[m][:, S_BT], y[m]) if m.any() else z
    for k, s in (("c_hurt", S_C), ("d_die", S_D)):
        y = D[k][rows]
        m = y >= 0
        L[k] = F.binary_cross_entropy_with_logits(out[m][:, s], y[m].float()) if m.any() else z
    m = D["e_ok"][rows]
    L["e_where"] = F.smooth_l1_loss(out[m][:, S_EW], D["e_where"][rows[m]].float(), beta=0.1) * 3 if m.any() else z
    total = L["a_time"] + L["b_kind"] + L["b_time"] + L["c_hurt"] + L["d_die"] + W_WHERE * (L["a_where"] + L["e_where"])
    return total, L


def _auc(score, y, torch):
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    rank = torch.empty(len(score), device=score.device, dtype=torch.float64)
    rank[torch.argsort(score)] = torch.arange(1, len(score) + 1, device=score.device, dtype=torch.float64)
    return float((rank[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _where(pred, tgt, torch):
    d = (pred - tgt).norm(dim=1) * 1000
    if not len(d):
        return {"n": 0}
    return {"n": int(len(d)), "mean": float(d.mean()), "median": float(d.median()), "within256": float((d < 256).float().mean())}


def metrics(out, D, rows, base, torch):
    """held-out numbers for one model's outputs on these rows, with the trivial guesses beside them"""
    F = torch.nn.functional
    M = {"rows": int(len(rows))}
    since = D["since"][rows]
    seen = D["seen"][rows]
    here = D["pos"][rows] / 1000
    last_off = D["ls"][rows][:, 0:3].float() - here                         # where he was last seen, from P now
    for k, s, n in (("a_time", S_AT, 6), ("b_kind", S_BK, 4), ("b_time", S_BT, 6)):
        y = D[k][rows].long()
        m = y >= 0
        lg, yy = out[m][:, s].float(), y[m]
        M[k] = {"n": int(m.sum()), "loss": float(F.cross_entropy(lg, yy)), "acc": float((lg.argmax(1) == yy).float().mean()),
                "trivial_loss": float(-(torch.log(base[k])[yy]).mean()), "trivial_acc": float((yy == base[k].argmax()).float().mean()),
                "rates": [float(v) for v in torch.bincount(yy, minlength=n).float() / max(1, len(yy))]}
        if k == "a_time":
            M[k]["by_since"] = {}
            for lo, hi, name in SINCE_BINS:
                b = (since[m] >= lo) & (since[m] < hi)
                if b.any():
                    M[k]["by_since"][name] = {"n": int(b.sum()), "loss": float(F.cross_entropy(lg[b], yy[b])),
                                              "acc": float((lg[b].argmax(1) == yy[b]).float().mean()),
                                              "trivial_loss": float(-(torch.log(base[k])[yy[b]]).mean())}
    for k, s in (("c_hurt", S_C), ("d_die", S_D)):
        y = D[k][rows]
        m = y >= 0
        lg, yy = out[m][:, s].float(), y[m] == 1
        p = base[k].clamp(1e-6, 1 - 1e-6)
        M[k] = {"n": int(m.sum()), "rate": float(yy.float().mean()), "loss": float(F.binary_cross_entropy_with_logits(lg, yy.float())),
                "acc": float(((lg > 0) == yy).float().mean()), "auc": _auc(lg, yy, torch),
                "trivial_loss": float(-(yy.float() * torch.log(p) + (1 - yy.float()) * torch.log(1 - p)).mean()),
                "trivial_acc": float((~yy).float().mean())}
    for k, s, m in (("a_where", S_AW, (D["a_time"][rows] >= 0) & (D["a_time"][rows] < 5)), ("e_where", S_EW, D["e_ok"][rows])):
        tgt = D[k][rows[m]].float()
        M[k] = _where(out[m][:, s].float(), tgt, torch)
        M[k]["trivial_mean_offset"] = _where(base[k][None].expand(len(tgt), 3), tgt, torch)
        guess = torch.where(seen[m][:, None], last_off[m], base[k][None].expand(len(tgt), 3))
        M[k]["trivial_last_seen"] = _where(guess, tgt, torch)
        M[k]["by_since"] = {}
        for lo, hi, name in SINCE_BINS:
            b = (since[m] >= lo) & (since[m] < hi)
            if b.any():
                M[k]["by_since"][name] = {"model": _where(out[m][:, s].float()[b], tgt[b], torch),
                                          "last_seen": _where(guess[b], tgt[b], torch)}
    return M


def pack(chains, B, T, rng=None):
    """chains (first row, rows) laid end to end in B streams, each padded to a multiple of T so that a chain starts
    only at a window's start. Returns the row numbers (streams, length; -1 = nothing) and where a state is new."""
    order = np.arange(len(chains)) if rng is None else rng.permutation(len(chains))
    B = min(B, len(chains))
    heap = [(0, b) for b in range(B)]
    plan = [[] for _ in range(B)]
    for c in order:
        n, b = heapq.heappop(heap)
        w = int(math.ceil(chains[c][1] / T))
        plan[b].append((c, n // T, w))
        heapq.heappush(heap, (n + w * T, b))
    W = max(n for n, _ in heap) // T
    idx = np.full((B, W * T), -1, np.int64)
    new = np.zeros((B, W), bool)
    for b in range(B):
        for c, w0, w in plan[b]:
            r0, m = int(chains[c][0]), int(chains[c][1])
            idx[b, w0 * T:w0 * T + m] = np.arange(r0, r0 + m)
            new[b, w0] = True
    return idx, new


def run_gru(model, D, chains, torch, T, B, opt=None, sched=None, rng=None, deadline=None):
    """one pass over these chains; with an optimizer: training (returns the mean loss), else the outputs row by row"""
    dev = D["now"].device
    idx, new = pack(chains, B, T, rng)
    idx_t, new_t = torch.from_numpy(idx).to(dev), torch.from_numpy(new).to(dev)
    h = torch.zeros(1, idx.shape[0], model.gru.hidden_size, device=dev)
    outs, rws, tot, cnt = [], [], 0.0, 0
    for w in range(new.shape[1]):
        rows = idx_t[:, w * T:(w + 1) * T]
        h = h * (~new_t[:, w]).float()[None, :, None]
        ok = (rows >= 0).flatten()
        if opt is None:
            with torch.no_grad():
                out, h = model(D, rows, h)
            outs.append(out.flatten(0, 1)[ok])
            rws.append(rows.flatten()[ok])
        else:
            out, h = model(D, rows, h)
            loss, _ = losses(out.flatten(0, 1)[ok], D, rows.flatten()[ok], torch)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched()
            h = h.detach()
            tot += float(loss)
            cnt += 1
            if deadline and time.time() > deadline:
                break
    if opt is None:
        return torch.cat(outs), torch.cat(rws)
    return tot / max(1, cnt)


def predict(model, D, rows, torch, bs=8192):
    outs = []
    with torch.no_grad():
        for k in range(0, len(rows), bs):
            outs.append(model(D, rows[k:k + bs]))
    return torch.cat(outs)


def evaluate(model, kind, D, base, torch, bptt=1024):
    model.eval()
    res = {}
    for sp, name in ((1, "held-out demos"), (2, "held-out maps")):
        if kind in ("gru", "both"):
            ch = D["chains"][D["chains"][:, 2] == sp]
            if not len(ch):
                continue
            out, rows = run_gru(model, D, ch, torch, *((bptt, 256) if kind == "gru" else (128, 48)))
        else:
            rows = (D["split"] == sp).nonzero().squeeze(1)
            if not len(rows):
                continue
            out = predict(model, D, rows, torch)
        res[name] = metrics(out, D, rows, base, torch)
        if sp == 2:
            res["by map"] = {}
            for mi, mp in enumerate(D["maps"]):
                m = D["mapname"][rows] == mi
                if m.any():
                    res["by map"][mp] = metrics(out[m], D, rows[m], base, torch)
    model.train()
    return res


def short(res):
    out = []
    for name in ("held-out demos", "held-out maps"):
        if name in res:
            r = res[name]
            out.append("{}: until seen {:.3f}/{:.2f}  where {:.0f}  pickup {:.3f}/{:.2f}  when {:.3f}/{:.2f}  hurt {:.3f} auc {:.3f}  "
                       "die {:.4f} auc {:.3f}  enemy now {:.0f}".format(
                           name, r["a_time"]["loss"], r["a_time"]["acc"], r["a_where"].get("mean", 0), r["b_kind"]["loss"],
                           r["b_kind"]["acc"], r["b_time"]["loss"], r["b_time"]["acc"], r["c_hurt"]["loss"], r["c_hurt"]["auc"],
                           r["d_die"]["loss"], r["d_die"]["auc"], r["e_where"].get("mean", 0)))
    return "\n".join(out)


def train(a):
    import torch
    torch.manual_seed(a.seed)
    dev = torch.device(a.device if a.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    torch.set_num_threads(2)
    if dev.type == "cuda":                                  # the card is shared with a training run: 30% of it at most
        torch.cuda.set_per_process_memory_fraction(a.gpu_share)
    if a.model == "both" and a.streams * a.bptt > a.step_rows:
        a.streams = max(1, a.step_rows // a.bptt)
        print("both: {} streams of {} rows a step (the attention blocks see every row: memory)".format(a.streams, a.bptt), flush=True)
    tag = a.tag or a.model
    t0 = time.time()
    D = load(a.data, dev, torch)
    base = base_rates(D, torch)
    n_tr = int((D["split"] == 0).sum())
    print("{} rows ({} train, {} demos held out, {} maps held out), {} events, {} chains; loaded in {:.0f} s".format(
        len(D["t"]), n_tr, int((D["split"] == 1).sum()), int((D["split"] == 2).sum()), len(D["events"]), len(D["chains"]),
        time.time() - t0), flush=True)
    model = build(a.model, torch, len(D["train_maps"]), split=a.record == "split").to(dev)
    n_par = sum(p.numel() for p in model.parameters())
    print("model {} ({}): {} weights".format(a.model, tag, n_par), flush=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, tag + ".pt")
    if a.load:
        model.load_state_dict(torch.load(path, map_location=dev)["model"])
    if a.ablate:
        return ablate(model, D, base, torch, tag, a.record == "split")
    its, spent = 0, 0.0
    if not a.load:
        opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
        t_start = time.time()
        budget = a.minutes * 60.0
        deadline = t_start + budget
        count = [0]

        def sched():
            count[0] += 1
            p = min(1.0, (time.time() - t_start) / budget)
            lr = a.lr * min(1.0, count[0] / 300.0) * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * p)))
            for g in opt.param_groups:
                g["lr"] = lr

        last_log = time.time()
        if a.model in ("gru", "both"):
            ch = D["chains"][D["chains"][:, 2] == 0]
            rng = np.random.default_rng(a.seed)
            ep = 0
            while time.time() < deadline:
                model.salt = int(rng.integers(1 << 20))
                ls = run_gru(model, D, ch, torch, a.bptt, a.streams, opt, sched, rng, deadline)
                ep += 1
                if time.time() - last_log > 45:
                    model.eval()
                    o, r = run_gru(model, D, D["chains"][D["chains"][:, 2] == 1], torch, *((1024, 256) if a.model == "gru" else (128, 48)))
                    with torch.no_grad():
                        pl, _ = losses(o, D, r, torch)
                    model.train()
                    last_log = time.time()
                    print("{:5.1f} min, pass {}, {} steps, train loss {:.4f}, held-out demos {:.4f}".format(
                        (time.time() - t_start) / 60, ep, count[0], ls, float(pl)), flush=True)
        else:
            tr = (D["split"] == 0).nonzero().squeeze(1)
            probe = (D["split"] == 1).nonzero().squeeze(1)
            probe = probe[torch.randperm(len(probe), device=dev)[:100000]]
            run = 0.0
            while time.time() < deadline:
                rows = tr[torch.randint(len(tr), (a.batch,), device=dev)]
                loss, _ = losses(model(D, rows), D, rows, torch)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched()
                run = 0.98 * run + 0.02 * float(loss) if count[0] > 1 else float(loss)
                if time.time() - last_log > 45:
                    last_log = time.time()
                    model.eval()
                    with torch.no_grad():
                        pl, _ = losses(predict(model, D, probe, torch), D, probe, torch)
                    model.train()
                    print("{:5.1f} min, {} steps ({:.1f} passes), train loss {:.4f}, held-out demos {:.4f}".format(
                        (time.time() - t_start) / 60, count[0], count[0] * a.batch / n_tr, run, float(pl)), flush=True)
        its, spent = count[0], time.time() - t_start
        torch.save({"model": model.state_dict(), "kind": a.model, "mu": D["mu"].cpu(), "sd": D["sd"].cpu(),
                    "train_maps": D["train_maps"], "now_names": DE.NOW_NAMES, "event_kinds": DE.EVENT_KINDS,
                    "event_facts": DE.EVENT_FACTS, "k_events": K_EVENTS, "outputs": "a_time 6, a_where 3, b_kind 4, b_time 6, c_hurt, d_die, e_where 3",
                    "args": vars(a)}, path)
    res = evaluate(model, a.model, D, base, torch)
    res.update({"model": a.model, "tag": tag, "weights": n_par, "steps": its, "train_seconds": spent, "train_rows": n_tr,
                "maps": D["maps"], "train_maps": D["train_maps"], "bptt": a.bptt if a.model in ("gru", "both") else None,
                "record": a.record if a.model in ("events", "both") else None,
                "base": {k: (v.tolist() if v.dim() else float(v)) for k, v in base.items()}})
    json.dump(res, open(os.path.join(OUT_DIR, "results_{}.json".format(tag)), "w"), indent=1)
    print(short(res), flush=True)
    if dev.type == "cuda":
        print("GPU memory at the peak: {:.1f} GB".format(torch.cuda.max_memory_allocated() / 2 ** 30))


def ablate(model, D, base, torch, tag, split):
    """the trained event model read with parts of the record hidden: by age, by number, by kind"""
    rows = (D["split"] == 1).nonzero().squeeze(1)
    model.eval()
    res = {}
    cases = [("the whole record", {})] + [("no record", {"keep": 0})]
    if split:
        cases += [("only the 8 frequent", {"part": "frequent"}), ("only the 8 rare", {"part": "rare"})]
    else:
        cases += [("the last {} events".format(k), {"keep": k}) for k in (1, 2, 4, 8)]
    cases += [("events of the last {} s".format(s), {"max_age": float(s)}) for s in (2, 5, 10, 20, 40)]
    cases += [("without: " + DE.EVENT_KINDS[k], {"drop_kind": k}) for k in range(1, NK)]
    for name, rec in cases:
        model.rec = rec
        res[name] = metrics(predict(model, D, rows, torch), D, rows, base, torch)
        r = res[name]
        print("{:28s} until seen {:.3f}  where {:4.0f}  pickup {:.3f}  when {:.3f}  hurt {:.4f}  die {:.4f}  enemy now {:4.0f}".format(
            name, r["a_time"]["loss"], r["a_where"]["mean"], r["b_kind"]["loss"], r["b_time"]["loss"], r["c_hurt"]["loss"],
            r["d_die"]["loss"], r["e_where"]["mean"]), flush=True)
    model.rec = {}
    json.dump(res, open(os.path.join(OUT_DIR, "ablate_{}.json".format(tag)), "w"), indent=1)


def report(tags):
    R = {}
    for t in tags:
        f = os.path.join(OUT_DIR, "results_{}.json".format(t))
        if os.path.exists(f):
            R[t] = json.load(open(f))
    if not R:
        return print("no results in", OUT_DIR)
    any_ = next(iter(R.values()))
    print("| model | weights | steps | minutes |\n|---|---|---|---|")
    for t, r in R.items():
        print("| {} | {:,} | {:,} | {:.1f} |".format(t, r["weights"], r["steps"], r["train_seconds"] / 60))
    for split in ("held-out demos", "held-out maps"):
        print("\n**{}** ({:,} rows)\n".format(split, any_[split]["rows"]))
        print("| target | rows | trivial | " + " | ".join(R) + " |\n|---|---|---|" + "---|" * len(R))
        for k, name in (("a_time", "enemy next in view: when (loss / right bucket)"), ("b_kind", "next pickup: which (loss / right)"),
                        ("b_time", "next pickup: when (loss / right bucket)")):
            x = any_[split][k]
            print("| {} | {:,} | {:.3f} / {:.1f}% | ".format(name, x["n"], x["trivial_loss"], 100 * x["trivial_acc"])
                  + " | ".join("{:.3f} / {:.1f}%".format(r[split][k]["loss"], 100 * r[split][k]["acc"]) for r in R.values()) + " |")
        for k, name in (("c_hurt", "hurt within 2 s (loss / AUC)"), ("d_die", "dies within 5 s (loss / AUC)")):
            x = any_[split][k]
            print("| {} ({:.1f}% yes) | {:,} | {:.4f} / 0.500 | ".format(name, 100 * x["rate"], x["n"], x["trivial_loss"])
                  + " | ".join("{:.4f} / {:.3f}".format(r[split][k]["loss"], r[split][k]["auc"]) for r in R.values()) + " |")
        for k, name in (("a_where", "enemy next in view: where (mean error, units / within 256)"),
                        ("e_where", "enemy now, out of view (mean error, units / within 256)")):
            x = any_[split][k]
            print("| {} | {:,} | last seen {:.0f} / {:.0f}%; mean offset {:.0f} / {:.0f}% | ".format(
                name, x["n"], x["trivial_last_seen"]["mean"], 100 * x["trivial_last_seen"]["within256"],
                x["trivial_mean_offset"]["mean"], 100 * x["trivial_mean_offset"]["within256"])
                + " | ".join("{:.0f} / {:.0f}%".format(r[split][k]["mean"], 100 * r[split][k]["within256"]) for r in R.values()) + " |")
        for k, name in (("a_where", "enemy next in view: where"), ("e_where", "enemy now, out of view")):
            print("\n{}, mean error in units by how long he has been out of view ({})\n".format(name, split))
            print("| out of view for | rows | last seen | " + " | ".join(R) + " |\n|---|---|---|" + "---|" * len(R))
            for _, _, b in SINCE_BINS:
                x = any_[split][k]["by_since"].get(b)
                if x:
                    print("| {} | {:,} | {:.0f} | ".format(b, x["model"]["n"], x["last_seen"]["mean"])
                          + " | ".join("{:.0f}".format(r[split][k]["by_since"][b]["model"]["mean"]) for r in R.values()) + " |")
        if split == "held-out maps":
            print("\nmap by map (never trained on): when next in view (loss) / next pickup right / hurt AUC / enemy now, mean error\n")
            print("| map | rows | trivial | " + " | ".join(R) + " |\n|---|---|---|" + "---|" * len(R))
            for mp, x in any_.get("by map", {}).items():
                print("| {} | {:,} | {:.3f} / {:.0f}% / 0.500 / last seen {:.0f} | ".format(
                    mp, x["rows"], x["a_time"]["trivial_loss"], 100 * x["b_kind"]["trivial_acc"], x["e_where"]["trivial_last_seen"]["mean"])
                    + " | ".join("{:.3f} / {:.0f}% / {:.3f} / {:.0f}".format(
                        r["by map"][mp]["a_time"]["loss"], 100 * r["by map"][mp]["b_kind"]["acc"], r["by map"][mp]["c_hurt"]["auc"],
                        r["by map"][mp]["e_where"]["mean"]) for r in R.values()) + " |")
        print("\nenemy next in view: when, loss by how long he has been out of view ({})\n".format(split))
        print("| out of view for | rows | trivial | " + " | ".join(R) + " |\n|---|---|---|" + "---|" * len(R))
        for _, _, b in SINCE_BINS:
            x = any_[split]["a_time"]["by_since"].get(b)
            if x:
                print("| {} | {:,} | {:.3f} | ".format(b, x["n"], x["trivial_loss"])
                      + " | ".join("{:.3f}".format(r[split]["a_time"]["by_since"][b]["loss"]) for r in R.values()) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="the folder tools/demo_events.py wrote")
    ap.add_argument("--model", default="events", choices=("events", "mlp", "gru", "both"))
    ap.add_argument("--tag", default=None, help="name of the weights and results (default: the model's)")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--batch", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--record", default="plain", choices=("plain", "split"),
                    help="events: the last 16 events, or the last 8 frequent and the last 8 rare")
    ap.add_argument("--bptt", type=int, default=256, help="gru: rows the training reaches back through")
    ap.add_argument("--streams", type=int, default=128, help="gru: chains stepped side by side")
    ap.add_argument("--step-rows", type=int, default=6144, help="both: at most this many rows a training step")
    ap.add_argument("--gpu-share", type=float, default=0.3, help="at most this share of the graphics card's memory")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--load", action="store_true", help="read the saved weights and only evaluate")
    ap.add_argument("--ablate", action="store_true", help="events model: hide parts of the record (with --load)")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--tags", default="mlp,gru_short,gru,events,events_split,both")
    a = ap.parse_args()
    if a.report:
        return report(a.tags.split(","))
    train(a)


if __name__ == "__main__":
    main()

"""2.1 (docs/runs/2.1/TRAINER_PARTS.md, piece 4; the trainer's --spawn-odds): the brain's question "where does he respawn". The owner,
2026-11-11: "he should know where the spawn points are, and be able to decide in the seconds after a frag to either spam or rush a
known spawn point, specifically one that he thinks the enemy will be at"; "people do do stuff like shoot a stream of plasma at a
known spawn point that they think they can force".

The simulator puts a killed player at a random one of the half of the map's spawn points farthest from his enemy when the wait ends
(RESPAWN_QL), so where he stands and goes decides which half: the readout learns that from the brain's state and the hands' memory.
Its answer: odds over the map's spawn points (padded to the simulator's SPAWN_MAX, masked to the map's own count), written into the
spawn rows' column INS_FILL["spawn_odds"] of the instruction's candidates (each row's spawn point: env.ins_cspawn).

The truth (SPAWN_TRUTH=1: info["aux"]'s en_spawn, the spawn point's number on the frame the enemy is back, else -1) is a label only.
A sample: every tick of the head at which the enemy is dead and whose respawn falls inside the same rollout with no round's end
between (decided here: every such tick, not one frame, because the head decides at each of them); the input is the brain's state and
the hands' memory of that tick. Beside its own score the record gives the simulator's own prior: uniform over the far half from where
he stands at the sample (what a player who knows the rule and nothing else would say).

Where it lives: as sim/knownodds.py: "spawn" at the top of a checkpoint, its own Adam, learnt after the PPO epochs.
"""
import numpy as np                                           # (numpy alone at the top: a game server's plugin reads np_odds)

COLS = ("en_spawn", "en_alive")
SEED = 4073


def layout(bel=256, mem=512, hid=128, smax=32, tick=8, back=96):
    """back: the frames before a respawn a sample may lie (the simulator's wait and a tick more)"""
    return dict(version=1, bel=int(bel), mem=int(mem), width=int(bel) + int(mem), hid=int(hid), smax=int(smax), tick=int(tick), back=int(back))


def make_module(L):
    """Linear(width -> hid) + ReLU + Linear(hid -> smax), its last layer at zero (every spawn point of the map alike)"""
    import control as control_
    assert int(L.get("version", 0)) == 1, "spawnodds: layout version 1 expected"
    return control_.make_module1(dict(inp=int(L["width"]), hid=int(L["hid"]), d=int(L["smax"])), SEED)


def _mask(z, nsp):
    import torch
    ar = torch.arange(z.shape[1], device=z.device)
    return z.masked_fill(ar[None, :] >= nsp[:, None].clamp(min=1), -1e4)


def odds(mod, s_brain, hands, nsp):
    """-> [n, smax] the odds over the seat's map's spawn points (nsp [n] their count; 0: zeros), a number (no gradient)"""
    import torch
    with torch.no_grad():
        x = s_brain.detach().float()
        m = int(mod[0].in_features) - x.shape[1]
        x = torch.cat([x, hands.detach()[:, :m].float()], 1)
        nsp = torch.as_tensor(nsp, dtype=torch.long, device=x.device)
        p = torch.softmax(_mask(mod(x.half().float()).float(), nsp), 1)
        return p * (nsp > 0).float()[:, None]


def np_params(sd):
    g = lambda k: np.asarray(sd[k].detach().cpu().numpy() if hasattr(sd[k], "detach") else sd[k], np.float32)   # noqa: E731
    return tuple(g("{}.{}".format(i, w)) for i in (0, 2) for w in ("weight", "bias"))


def np_odds(P, s_brain, hands, nsp):
    """odds() in numpy (the checks, the servers)"""
    x = np.asarray(s_brain, np.float32)
    m = int(P[0].shape[1]) - x.shape[1]
    x = np.concatenate([x, np.asarray(hands, np.float32)[:, :m]], 1).astype(np.float16).astype(np.float32)
    z = (np.maximum(x @ P[0].T + P[1], 0.0) @ P[2].T + P[3]).astype(np.float64)
    nsp = np.asarray(nsp, np.int64)
    z[np.arange(z.shape[1])[None, :] >= np.maximum(nsp, 1)[:, None]] = -1e4
    p = np.exp(z - z.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    return (p * (nsp > 0)[:, None]).astype(np.float32)


def batch(L, U2, o_brain, o_hands, aux, done, ix, nsp, tab=None, live=None):
    """a rollout's samples. U2 [J, N, u] the head's inputs at its ticks (tick j: frame (j + 1) * tick - 1), o_brain / o_hands the parts'
    columns; aux [T + 1, N, C] the truth (row t: what frame t's inputs show), done [T, N] (1: the round ended with frame t's step);
    ix: column -> index (en_spawn, en_alive; x, y, z: his own place, for the prior); nsp [N] each seat's map's spawn points; tab
    [N] each seat's row of the spawn tables (for the prior; None: none); live [N] the seats that count.
    -> dict(X [B, width] float16, y [B] long, nsp [B], pos [B, 3] or None, tab [B] or None) on the host, or None"""
    import torch
    K, back = int(L["tick"]), int(L["back"])
    T = aux.shape[0] - 1
    J = U2.shape[0]
    sp = aux[:, :, ix["en_spawn"]].float()
    ev_t, ev_i = torch.nonzero(sp[1:T + 1] >= 0, as_tuple=True)          # (row t + 1: he is back after frame t's step ... or row t itself:
    ev_t = ev_t + 1                                                      #  both read as "the row that shows him back")
    if not len(ev_t):
        return None
    dn = torch.cat([torch.zeros(1, done.shape[1]), torch.cumsum(done.float().cpu(), 0)], 0)      # rounds ended before frame t
    alive = aux[:, :, ix["en_alive"]].float() > 0.5
    nsp_t = torch.as_tensor(np.asarray(nsp), dtype=torch.long)
    keep = nsp_t[ev_i] > 0
    if live is not None:
        keep = keep & torch.as_tensor(live, dtype=torch.bool)[ev_i]
    ev_t, ev_i = ev_t[keep], ev_i[keep]
    lab = sp[ev_t, ev_i].long()
    okl = lab < nsp_t[ev_i]
    ev_t, ev_i, lab = ev_t[okl], ev_i[okl], lab[okl]
    xs, ys, ns, ps, ts = [], [], [], [], []
    has_pos = all(c in ix for c in ("x", "y", "z"))
    for k in range(1, back // K + 2):                                    # the k-th tick before the respawn's row
        j = ev_t // K - k                                                # the last tick whose frame is before row ev_t, and those before it
        f = (j + 1) * K - 1
        ok = (j >= 0) & (j < J) & (f < ev_t) & (ev_t - f <= back)
        if not bool(ok.any()):
            continue
        j_, f_, i_, t_ = j[ok], f[ok], ev_i[ok], ev_t[ok]
        good = ~alive[f_, i_] & (dn[torch.clamp(t_, max=dn.shape[0] - 1), i_] == dn[f_, i_])    # he was dead at the tick; no round's end between
        if not bool(good.any()):
            continue
        j_, f_, i_ = j_[good], f_[good], i_[good]
        u = U2[j_, i_]
        xs.append(torch.cat([u[:, o_brain[0]:o_brain[1]], u[:, o_hands[0]:o_hands[0] + int(L["mem"])]], 1).to(torch.float16))
        ys.append(lab[ok][good])
        ns.append(nsp_t[i_])
        if has_pos:
            ps.append(torch.stack([aux[f_, i_, ix[c]].float() for c in ("x", "y", "z")], 1))
        if tab is not None:
            ts.append(torch.as_tensor(np.asarray(tab), dtype=torch.long)[i_])
    if not xs:
        return None
    return dict(X=torch.cat(xs, 0), y=torch.cat(ys, 0), nsp=torch.cat(ns, 0), pos=torch.cat(ps, 0) if ps else None,
                tab=torch.cat(ts, 0) if ts else None)


def prior(pos, y, nsp, tab, tables):
    """the simulator's own rule as a guess: uniform over the spawn points farther than the median from where he stands. pos [B, 3],
    y [B] the truth, nsp [B], tab [B] rows of tables [W, smax, 3] -> (top-1, top-3 expected hits [B], the share of the truth inside
    the far half)"""
    import torch
    P = torch.as_tensor(np.asarray(tables), dtype=torch.float32)[tab]                # [B, smax, 3]
    d = (P - pos[:, None, :]).norm(dim=2)
    ar = torch.arange(P.shape[1])[None, :]
    has = ar < nsp[:, None]
    dm = torch.where(has, d, torch.full_like(d, float("nan")))
    med = torch.nanmedian(dm, dim=1).values
    far = has & (d > med[:, None])
    nf = far.sum(1).clamp(min=1).float()
    inside = far.gather(1, y[:, None]).squeeze(1).float()
    return inside / nf, inside * torch.clamp(nf, max=3.0) / nf, inside


def learn(mod, opt, L, B, lr, dev, gen, tables=None, mb=8192, epochs=1):
    """scored before it is learnt from (cross-entropy, top-1, top-3; the uniform guess over the map's points; the rule's prior where
    the tables are given), then one pass -> counters for record()"""
    import torch
    out = {}
    if B is None or not len(B["y"]):
        return out
    X, y, nsp = B["X"], B["y"], B["nsp"]
    n = len(y)
    with torch.no_grad():
        Z = torch.cat([_mask(mod(X[b:b + mb].to(dev).float()).float(), nsp[b:b + mb].to(dev)).cpu() for b in range(0, n, mb)])
        lp = torch.log_softmax(Z, 1)
        top3 = Z.topk(min(3, Z.shape[1]), 1).indices
        out.update(n=n, ce=float(-lp.gather(1, y[:, None]).sum()), ce_uni=float(torch.log(nsp.float().clamp(min=1.0)).sum()),
                   top1=float((Z.argmax(1) == y).sum()), top3=float((top3 == y[:, None]).any(1).sum()),
                   uni1=float((1.0 / nsp.float().clamp(min=1.0)).sum()), uni3=float((3.0 / nsp.float().clamp(min=3.0)).sum()))
        if tables is not None and B.get("pos") is not None and B.get("tab") is not None:
            p1, p3, ins = prior(B["pos"], y, nsp, B["tab"], tables)
            out.update(pri1=float(p1.sum()), pri3=float(p3.sum()), far=float(ins.sum()))
    if lr <= 0:
        return out
    for g_ in opt.param_groups:
        g_["lr"] = float(lr)
    for _ in range(int(epochs)):
        pm = torch.randperm(n, generator=gen)
        for b in range(0, n, mb):
            i_ = pm[b:b + mb]
            z = _mask(mod(X[i_].to(dev).float()), nsp[i_].to(dev))
            l_ = torch.nn.functional.cross_entropy(z.float(), y[i_].to(dev))
            opt.zero_grad(set_to_none=True)
            l_.backward()
            torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
            opt.step()
    return out


def record(acc, w, L):
    """-> metrics.jsonl's "spawn": the samples; before the step: cross-entropy beside the uniform guess's, how often his first guess
    and his first three hold the truth, beside the uniform guess's and the rule's prior (the far half from where he stands)"""
    rec = dict(w=round(float(w), 4), frames=int(acc.get("n", 0)) if acc else 0)
    if not acc or not acc.get("n"):
        return rec
    n = float(acc["n"])
    rec.update(ce=round(acc["ce"] / n, 4), ce_uniform=round(acc["ce_uni"] / n, 4), top1=round(acc["top1"] / n, 4), top3=round(acc["top3"] / n, 4),
               uniform_top1=round(acc["uni1"] / n, 4), uniform_top3=round(acc["uni3"] / n, 4))
    if "pri1" in acc:
        rec.update(prior_top1=round(acc["pri1"] / n, 4), prior_top3=round(acc["pri3"] / n, 4), truth_in_far_half=round(acc["far"] / n, 4))
    return rec

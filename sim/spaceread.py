"""2.0b (docs/runs/2.0/2.0b/CARD.md part 1; the trainer's --space-read): the brain's readout "space": from his senses, the threat on him
and what he puts on the enemy (damage a second), the map's cover (his share of the zones less the enemy's) and the cover of each zone.
The truth is the map's table read at the true places and weapons this frame (the simulator's SPACE_TRUTH=1: info["aux"]'s sp_
columns; sim/space.py): exact, no hindsight. A lesson only, never pay; nothing reads it but the record (the inputs of part 2 are the
table read at his belief, not this readout).

Built on sim/fightodds.py's pattern and sim/control.py's parts (its Ring, its readout's shape): the readout reads the brain's state and
the hands' memory beside it ("both"), kept every `every` ticks of the brain in a ring one rollout long; at the rollout's end each kept
row is scored against its own frame's truth, then taught. Its gradient reaches its own layers only: nothing of it reaches the policy,
the brain or their optimizer.

Layout: {"version": 1, "bel", "mem", "width", "every", "horizon": 0, "tick", "d": 27, "outs", "readouts": [{"name": "both", "inp", "hid",
"d"}]}; the module is a ModuleDict `space` ({"both": Linear(inp -> hid) + ReLU + Linear(hid -> 27)}, its last layer at zero: a guess of
0 everywhere, from a random stream of its own); its own Adam (cold at a process start). Targets: the two threats / SCALE (at most 1.5),
the covers as they are (-1 .. 1). Scored by the squared error against the best constant's (skill = 1 - the one over the other), by group.
"""
import math

import torch

import control as control_

SP_Z = 24
COLS = ("sp_ok", "sp_thr", "sp_put", "sp_agg") + tuple("sp_z{}".format(k) for k in range(SP_Z))
OUTS = ("thr", "put", "agg") + tuple("z{}".format(k) for k in range(SP_Z))
GROUPS = (("thr", 0, 1), ("put", 1, 2), ("agg", 2, 3), ("zones", 3, 3 + SP_Z))
SCALE = 40.0
SEED = 4051


def layout(bel=256, mem=512, hid=128, every=2, tick=8):
    ro = [dict(name="both", src="belief+memory", inp=int(bel) + int(mem), hid=int(hid), d=len(OUTS))]
    return dict(version=1, bel=int(bel), mem=int(mem), width=int(bel) + int(mem), every=int(every), horizon=0, tick=int(tick),
                d=len(OUTS), outs=list(OUTS), scale=SCALE, readouts=ro)


def names(L):
    return [r["name"] for r in L["readouts"]]


def make_module(L):
    """the readout as a ModuleDict by name (made without a draw of the global random stream)"""
    import torch.nn as nn
    assert int(L.get("version", 0)) == 1, "spaceread: layout version 1 expected"
    return nn.ModuleDict({r["name"]: control_.make_module1(r, SEED) for r in L["readouts"]})


Ring = control_.Ring


def batch(ring, g0, aux, ix):
    """this rollout's labels: aux [T + 1, n, C] (b_aux, rows g0 .. g0 + T), ix: column -> index -> (states [B, width] float16, targets
    [B, 27]) on the host, the kept rows where sp_ok; None if none"""
    T = aux.shape[0] - 1
    xs, ys, ms = [], [], []
    for t in range(T):
        s_ = ring.get(int(g0) + t)
        if s_ is None:
            continue
        a_ = aux[t]
        y_ = torch.cat([(a_[:, ix["sp_thr"]].float() / SCALE).clamp(0.0, 1.5)[:, None], (a_[:, ix["sp_put"]].float() / SCALE).clamp(0.0, 1.5)[:, None],
                        a_[:, ix["sp_agg"]].float()[:, None], a_[:, ix["sp_z0"]:ix["sp_z0"] + SP_Z].float()], 1)
        xs.append(s_.clone())
        ys.append(y_)
        ms.append(a_[:, ix["sp_ok"]] > 0)
    if not xs:
        return None
    X, Y, M = torch.cat(xs, 0), torch.cat(ys, 0), torch.cat(ms, 0)
    if not bool(M.any()):
        return None
    return X[M], Y[M]


def learn(mods, opts, L, X, Y, lr, dev, gen, mb=8192, epochs=1):
    """score the readout (before learning), then one pass of its lesson -> counters"""
    out = {}
    if X is None or not len(X):
        return out
    Y64 = Y.double()
    B = len(X)
    ybar = Y64.mean(0)
    out["base"] = dict(n=B, const=((Y64 - ybar) ** 2).sum(0), zero=(Y64 ** 2).sum(0), mean=ybar,
                       over20=float((Y64[:, 0] * SCALE > 20.0).sum()), edge10=float(((Y64[:, 1] - Y64[:, 0]) * SCALE < -10.0).sum()))
    for r in L["readouts"]:
        nm, inp = r["name"], int(r["inp"])
        mod, opt = mods[nm], opts[nm]
        P = torch.empty(B, int(L["d"]))
        with torch.no_grad():
            for b in range(0, B, mb):
                P[b:b + mb] = mod(X[b:b + mb, :inp].to(dev).float()).float().cpu()
        out[nm] = dict(sq=((P.double() - Y64) ** 2).sum(0))
        if lr <= 0:
            continue
        for g_ in opt.param_groups:
            g_["lr"] = float(lr)
        for _ in range(int(epochs)):
            pm = torch.randperm(B, generator=gen)
            for b in range(0, B, mb):
                i_ = pm[b:b + mb]
                l_ = torch.nn.functional.smooth_l1_loss(mod(X[i_, :inp].to(dev).float()), Y[i_].to(dev), beta=0.1)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step()
    return out


def _r(x, k=4):
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, k)


def record(acc, w, L, ring_gb=None):
    """the update's counters -> metrics.jsonl's "space": the frames, then by group (the threat on him, what he puts on the enemy, the
    map's cover, the zones) the truth's mean, the best constant's squared error, the readout's, and the skill (1 - the one over the
    other; above 0: it beats its base rate)"""
    if not acc or "base" not in acc:
        return dict(w=round(float(w), 4), frames=0)
    b = acc["base"]
    n = max(1.0, float(b["n"]))
    rec = dict(w=round(float(w), 4), frames=int(b["n"]), scale=SCALE,      # (the card's measures on the training's own frames, every seat)
               thr_over20=_r(b["over20"] / n), edge_under10=_r(b["edge10"] / n))
    if ring_gb is not None:
        rec["ring_gb"] = round(float(ring_gb), 3)
    for nm in names(L):
        if nm not in acc:
            continue
        sq = acc[nm]["sq"]
        g = {}
        for gn, i0, i1 in GROUPS:
            c_, s_ = float(b["const"][i0:i1].sum()) / n / (i1 - i0), float(sq[i0:i1].sum()) / n / (i1 - i0)
            g[gn] = dict(mean=_r(float(b["mean"][i0:i1].mean())), mse_const=_r(c_, 5), mse=_r(s_, 5), skill=_r(1.0 - s_ / c_) if c_ > 0 else None)
        rec[nm] = g
    return rec

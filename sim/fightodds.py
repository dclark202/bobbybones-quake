"""1.7b (docs/runs/1.7/1.7b/CARD.md part 1; the trainer's --fight-odds): the brain's readout "the fight odds": how a fight that is on
ends, his enemy dead first or he dead first, known only in hindsight (the simulator's FIGHT_TRUTH=1 gives it FIGHT_H seconds late:
info["aux"]'s fo_win, fo_lose of the row FIGHT_D rows before). Cypher (docs/design/CYPHER.md): "who's going to win the fight even
before the fight comes", from the two stacks. A lesson only, never pay; the strategy head reads its two chances (its part "fight",
sim/head2.py), so the head's order (engage or break off) has the brain's honest number for who would win.

Built on sim/control.py's pattern and parts (its Ring, its AUC, its readout's shape): the readout reads the brain's state and the hands'
memory beside it ("both": the brain knows the enemy, the hands' memory his own stack), kept at every tick of the brain (0.2 s) in a
ring as long as the horizon and one rollout more; at the rollout's end the rows whose label came in are scored, then taught. Its
gradient reaches its own layers only: nothing of it reaches the policy, the brain or their optimizer.

Layout: {"version": 1, "bel", "mem", "width", "every", "horizon", "tick", "d": 2, "outs": ["win", "lose"], "readouts": [{"name": "both",
"inp", "hid", "d"}]}; the module is a ModuleDict `fight` ({"both": Linear(inp -> hid) + ReLU + Linear(hid -> 2)}, its last layer at zero:
a guess of 0.5 each, from a random stream of its own); its own Adam (cold at a process start). The head reads sigmoid(logits) - 0.5.
"""
import math

import numpy as np
import torch

import control as control_

COLS = ("fo_win", "fo_lose", "fo_age", "fo_ok")
OUTS = ("win", "lose")
SEED = 4047


def layout(bel=256, mem=512, hid=64, every=1, horizon_frames=200, tick=8):
    ro = [dict(name="both", src="belief+memory", inp=int(bel) + int(mem), hid=int(hid), d=len(OUTS))]
    return dict(version=1, bel=int(bel), mem=int(mem), width=int(bel) + int(mem), every=int(every), horizon=int(horizon_frames),
                tick=int(tick), d=len(OUTS), outs=list(OUTS), readouts=ro)


def names(L):
    return [r["name"] for r in L["readouts"]]


def make_module(L):
    """the readout as a ModuleDict by name (made without a draw of the global random stream)"""
    import torch.nn as nn
    assert int(L.get("version", 0)) == 1, "fightodds: layout version 1 expected"
    return nn.ModuleDict({r["name"]: control_.make_module1(r, SEED) for r in L["readouts"]})


Ring = control_.Ring


def batch(ring, g0, aux, ix, D):
    """this rollout's labels: aux [T + 1, n, C] (b_aux, rows g0 .. g0 + T), ix: column -> index -> (states [B, width] float16,
    labels [B, 2], mask [B, 2]) on the host, the rows whose frame D rows back has a kept state and a label; None if none"""
    T = aux.shape[0] - 1
    xs, ys = [], []
    for t in range(T):
        s_ = ring.get(int(g0) + t - int(D))
        if s_ is None:
            continue
        xs.append(s_)
        ys.append(torch.stack([aux[t, :, ix[c_]] for c_ in ("fo_win", "fo_lose")], -1).float())
    if not xs:
        return None
    X = torch.cat(xs, 0)
    Y = torch.cat(ys, 0)
    M = (Y >= 0).float()
    keep = M.sum(1) > 0
    if not bool(keep.any()):
        return None
    return X[keep], Y[keep].clamp(min=0.0), M[keep]


def learn(mods, opts, L, X, Y, M, lr, dev, gen, mb=8192, epochs=1):
    """score the readout (before learning), then one pass of its lesson -> counters as sim/control.py's learn"""
    d = int(L["d"])
    out = {}
    if X is None or not len(X):
        return out
    Y64, M64 = Y.double(), M.double()
    n_ = M64.sum(0)
    ybar = (Y64 * M64).sum(0) / n_.clamp(min=1.0)
    out["base"] = dict(half=(((0.5 - Y64) ** 2) * M64).sum(0), const=(((ybar - Y64) ** 2) * M64).sum(0), n=n_,
                       pos=((Y > 0.5).double() * M64).sum(0), neg=((Y < 0.5).double() * M64).sum(0))
    B = len(X)
    for r in L["readouts"]:
        nm, inp = r["name"], int(r["inp"])
        mod, opt = mods[nm], opts[nm]
        P = torch.empty(B, d)
        with torch.no_grad():
            for b in range(0, B, mb):
                P[b:b + mb] = torch.sigmoid(mod(X[b:b + mb, :inp].to(dev).float())).float().cpu()
        P64 = P.double()
        bce = (torch.nn.functional.binary_cross_entropy(P.clamp(1e-6, 1 - 1e-6), Y, reduction="none").double() * M64).sum()
        au_ = [control_.auc(P[:, j].numpy()[M[:, j].numpy() > 0], Y[:, j].numpy()[M[:, j].numpy() > 0]) for j in range(d)]
        out[nm] = dict(sq=(((P64 - Y64) ** 2) * M64).sum(0), bce=float(bce), auc=au_)
        if lr <= 0:
            continue
        for g_ in opt.param_groups:
            g_["lr"] = float(lr)
        for _ in range(int(epochs)):
            pm = torch.randperm(B, generator=gen)
            for b in range(0, B, mb):
                i_ = pm[b:b + mb]
                xb, yb, mk = X[i_, :inp].to(dev).float(), Y[i_].to(dev), M[i_].to(dev)
                l_ = (torch.nn.functional.binary_cross_entropy_with_logits(mod(xb), yb, reduction="none") * mk).sum() / \
                    mk.sum().clamp(min=1.0)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step()
    return out


def _r(x, k=4):
    x = float(x)
    return None if math.isnan(x) else round(x, k)


def record(acc, w, L, ring_gb=None):
    """the update's counters -> metrics.jsonl's "fight": the frames and the two guesses per output, then the readout's Brier,
    skill (1 - Brier / the best constant's), AUC and BCE"""
    if not acc or "base" not in acc:
        return dict(w=round(float(w), 4), frames=0)
    b = acc["base"]
    d = int(L["d"])
    nf = [float(b["n"][i]) for i in range(d)]
    bc = [float(b["const"][i]) / max(1.0, nf[i]) for i in range(d)]
    rec = dict(w=round(float(w), 4), outs=list(OUTS), frames=[int(x) for x in nf],
               pos=[int(b["pos"][i]) for i in range(d)], neg=[int(b["neg"][i]) for i in range(d)],
               brier_half=[round(float(b["half"][i]) / max(1.0, nf[i]), 4) for i in range(d)],
               brier_const=[round(x, 4) for x in bc])
    if ring_gb is not None:
        rec["ring_gb"] = round(float(ring_gb), 3)
    for nm in names(L):
        if nm not in acc:
            continue
        a_ = acc[nm]
        br = [float(a_["sq"][i]) / max(1.0, nf[i]) for i in range(d)]
        rec[nm] = dict(brier=[round(x, 4) for x in br], skill=[_r(1.0 - br[i] / bc[i]) if bc[i] > 0 else None for i in range(d)],
                       auc=[_r(x) for x in a_["auc"]], bce=round(float(a_["bce"]) / max(1.0, sum(nf)), 4))
    return rec


# the head's reading of it: sim/head2.py's fight_t (torch) and np_fight_params / np_fight (numpy, the checks and the servers)

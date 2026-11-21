"""2.1 (docs/runs/2.1/DESIGN.md, questions A1 to A6; the trainer's --appraise): the appraisals. One network that forecasts, for any
candidate instruction from a moment, what committing to it brings over the next 8 s:
  dealt, taken     the damage he deals and takes (/ 100)
  he_dies, i_die   the enemy dies; he dies (chances)
  item             he takes the mega or the red armor (a chance)
  dv               how his standing changes: the strategy head's own value as an n-step advantage,
                   sum_{k<W} gamma^k pay[t0 + k] + gamma^W V_head[t0 + W] - V_head[t0]   (docs/runs/2.1/RUNDOWN.md decision 1, option a:
                   the head's value reads the items' clocks; the win judge does not)
It reads the situation (the brain's state, the hands' memory, the head's state: the same three the head's value reads) and the
candidate: its verb (8, sim/duel_env.py's INS_VERBS; all zeros while the candidates are targets only), its target (17), its weapon
(9 and "none"), and the map sense at its place (8; zeros where not known).

Its lesson: the frozen moments' branches only (sim/branch.py: the same moment played out under several first choices, each with its
true outcome). No pro game teaches it (decision 2; CLAUDE.md rule 12). A LESSON ONLY: nothing reads its output yet (gate 0), its
gradient reaches its own layers alone; its own module and Adam, a top-level entry "appraise" of the checkpoint (as the shadow win
value's): the export, the checks, the league and the anchors do not see it.
"""
import math

import numpy as np

VERSION = 1
SEED = 4062
OUTS = ("dealt", "taken", "he_dies", "i_die", "item", "dv", "dv_long")   # (dv_long, owner 2026-11-11, the score and the clock: the same
#   change of his standing over a LONG window (30 s, sim/branch.py's long branches), labelled only on those. The 8 s dv already ends on
#   the head's own two-minute value, which reads the score and the clock; the long window is a check on that reading, played out)
REG = (0, 1, 5, 6)                                            # regressions (smooth L1); the rest chances (BCE)
CH = (2, 3, 4)
Y_SCALE = 100.0
N_VERB, N_WEAPON, N_MS = 8, 10, 8


def layout(bel=256, mem=512, head=256, targets=17, hid=256, gamma=0.9998, hold=40, win=320, xf=0, quiet=0):
    """xf (2.1, the instruction): the numbers of a candidate row as the simulator gives them (sim/duel_env.py instr_feat, INS_F), read
    beside the verb, target and weapon; 0: a network made before the simulator had them (targets only)"""
    sit = int(bel) + int(mem) + int(head)
    cand = N_VERB + int(targets) + N_WEAPON + int(xf) + int(bool(quiet)) + N_MS      # (quiet: the instruction asks for quiet movement, one number)
    return dict(quiet=int(bool(quiet)), version=VERSION, bel=int(bel), mem=int(mem), head=int(head), sit=sit, verbs=N_VERB, targets=int(targets), weapons=N_WEAPON,
                ms=N_MS, xf=int(xf), cand=cand, inp=sit + cand, hid=int(hid), d=len(OUTS), outs=list(OUTS), gamma=float(gamma), hold=int(hold),
                win=int(win), y_scale=Y_SCALE)


def make_module(L):
    """its last layer at zero (0 damage, chances of a half, no change), from a random stream of its own"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "appraise: layout version {} expected".format(VERSION)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(SEED)
        m = nn.Sequential(nn.Linear(int(L["inp"]), int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), int(L["hid"])), nn.ReLU(),
                          nn.Linear(int(L["hid"]), int(L["d"])))
    with torch.no_grad():
        m[4].weight.zero_()
        m[4].bias.zero_()
    return m


def cand(L, target, verb=None, weapon=None, ms=None, x=None, quiet=None):
    """the candidates as the network reads them [B, cand] float32 (numpy): target [B] (0 .. targets - 1; under 0: none, zeros), verb
    [B] (1 .. 7; None or under 1: no verb, zeros), weapon [B] (0 .. 8; None or under 0: "none"), ms [B, 8] the map sense at its
    place (None: zeros), x [B, xf] an instruction's row (None: zeros; its verb is among its own numbers)"""
    target = np.asarray(target, np.int64)
    n = len(target)
    out = np.zeros((n, int(L["cand"])), np.float32)
    r = np.arange(n)
    if verb is not None:
        v = np.asarray(verb, np.int64)
        m = (v >= 1) & (v < N_VERB)
        out[r[m], v[m]] = 1.0
    tm = target >= 0
    out[r[tm], N_VERB + np.clip(target[tm], 0, int(L["targets"]) - 1)] = 1.0
    xf = int(L.get("xf", 0) or 0)
    if x is not None and xf:
        o = N_VERB + int(L["targets"]) + N_WEAPON
        out[:, o:o + xf] = np.asarray(x, np.float32).reshape(n, xf)
    if quiet is not None and L.get("quiet"):
        out[:, N_VERB + int(L["targets"]) + N_WEAPON + xf] = (np.asarray(quiet) > 0).astype(np.float32)
    w = np.full(n, -1, np.int64) if weapon is None else np.asarray(weapon, np.int64)
    out[r, N_VERB + int(L["targets"]) + np.where((w >= 0) & (w < N_WEAPON - 1), w, N_WEAPON - 1)] = 1.0
    if ms is not None:
        out[:, -N_MS:] = np.asarray(ms, np.float32).reshape(n, N_MS)
    return out


def cand_rows(L, X, weapon=None, quiet=None):
    """(2.1) the candidates of instruction rows as tensors, on X's device: X [..., xf] -> [..., cand]; weapon [...] (long; None or
    under 0: "none")"""
    import torch
    o = N_VERB + int(L["targets"])
    xf = int(L.get("xf", 0) or 0)
    assert xf == X.shape[-1], "appraise: the layout reads {} numbers a row, the simulator gives {}".format(xf, X.shape[-1])
    out = X.new_zeros(tuple(X.shape[:-1]) + (int(L["cand"]),), dtype=torch.float32)
    w = torch.full(tuple(X.shape[:-1]), N_WEAPON - 1, dtype=torch.long, device=X.device) if weapon is None else \
        torch.where((weapon >= 0) & (weapon < N_WEAPON - 1), weapon, torch.full_like(weapon, N_WEAPON - 1))
    out.scatter_(-1, (o + w)[..., None], 1.0)
    out[..., o + N_WEAPON:o + N_WEAPON + xf] = X.float()
    if quiet is not None and L.get("quiet"):
        out[..., o + N_WEAPON + xf] = (quiet > 0).float()
    return out


def forecast_rows(mod, L, S, X, weapon=None, mb=262144, quiet=None):
    """(2.1) the forecasts of every row of every seat: S [n, sit], X [n, C, xf] (weapon [n, C] or None) -> [n, C, 6] (no gradient)"""
    import torch
    n, C = X.shape[0], X.shape[1]
    out = torch.empty(n, C, len(OUTS), device=X.device)
    step = max(1, int(mb) // max(1, C))
    with torch.no_grad():
        for b in range(0, n, step):
            x_ = X[b:b + step]
            c_ = cand_rows(L, x_, None if weapon is None else weapon[b:b + step], None if quiet is None else quiet[b:b + step])
            s_ = S[b:b + step].float()[:, None, :].expand(-1, C, -1)
            out[b:b + step] = forecast(mod, s_.reshape(-1, s_.shape[-1]), c_.reshape(-1, c_.shape[-1])).view(len(x_), C, -1)
    return out


def forecast(mod, S, C):
    """-> [B, 6]: dealt, taken (damage / 100), the three chances (0 .. 1), dv"""
    import torch
    z = mod(torch.cat([S.float(), C.float()], 1))
    return torch.cat([z[:, :2], torch.sigmoid(z[:, 2:5]), z[:, 5:]], 1)


def learn(mod, opt, L, S, C, Y, M, lr, dev, gen, mb=4096, epochs=1):
    """S [B, sit] (half precision or not), C [B, cand], Y [B, 6] (dealt and taken / 100; 0 or 1; dv), M [B, 6] (1: a label)
    -> score before learning, then one pass (smooth L1 on the regressions, BCE on the chances) -> the counters for record()"""
    import torch
    import torch.nn.functional as F
    out = {}
    if S is None or not len(S):
        return out
    S, C, Y, M = (torch.as_tensor(x_) for x_ in (S, C, Y, M))
    Y, M = Y.float(), M.float()
    n = len(S)
    P = torch.empty(n, len(OUTS))
    with torch.no_grad():
        for b in range(0, n, mb):
            P[b:b + mb] = forecast(mod, S[b:b + mb].to(dev), C[b:b + mb].to(dev)).float().cpu()
    y64, m64, p64 = Y.double(), M.double(), P.double()
    out.update(n=m64.sum(0), sy=(y64 * m64).sum(0), syy=(y64 ** 2 * m64).sum(0), sq=((p64 - y64) ** 2 * m64).sum(0), rows=n)
    if lr > 0:
        for g_ in opt.param_groups:
            g_["lr"] = float(lr)
        reg, ch = list(REG), list(CH)
        for _ in range(int(epochs)):
            pm = torch.randperm(n, generator=gen)
            for b in range(0, n, mb):
                i_ = pm[b:b + mb]
                z = mod(torch.cat([S[i_].to(dev).float(), C[i_].to(dev).float()], 1))
                yb, mk = Y[i_].to(dev), M[i_].to(dev)
                l_ = ((F.smooth_l1_loss(z[:, reg], yb[:, reg], reduction="none") * mk[:, reg]).sum()
                      + (F.binary_cross_entropy_with_logits(z[:, ch], yb[:, ch], reduction="none") * mk[:, ch]).sum()) / mk.sum().clamp(min=1.0)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step()
    return out


def record(acc, w, L):
    """-> metrics.jsonl's "appraise": the branches learnt from; for each output its mean, and before the step: the regressions' R2,
    the chances' Brier score beside the best constant's (skill = 1 - the one over the other)"""
    rec = dict(w=round(float(w), 4), rows=int(acc.get("rows", 0)) if acc else 0)
    if not acc or not acc.get("rows"):
        return rec
    for k, o in enumerate(OUTS):
        n = float(acc["n"][k])
        if n < 2:
            continue
        mean = float(acc["sy"][k]) / n
        var = float(acc["syy"][k]) / n - mean ** 2
        mse = float(acc["sq"][k]) / n
        d = dict(n=int(n), mean=round(mean * (float(L["y_scale"]) if k < 2 else 1.0), 4))
        if k in REG:
            d["r2"] = round(1.0 - mse / var, 4) if var > 0 else None
        else:
            d["brier"], d["brier_const"] = round(mse, 4), round(var, 4)
            d["skill"] = round(1.0 - mse / var, 4) if var > 0 else None
        rec[o] = d
    return rec


def _nan(x):
    return None if isinstance(x, float) and math.isnan(x) else x


# ------------------------------------------------------------------------------------------------------------------ numpy
# (2.1) the checks' player and a game server's plugin: the forecasts of an instruction's candidate rows, the trainer's sums


def np_params(sd):
    return {k: (v.detach().cpu().numpy() if hasattr(v, "detach") else np.asarray(v)).astype(np.float32) for k, v in sd.items()}


def np_forecast_rows(P, L, S, X, weapon=None, quiet=None):
    """forecast_rows in numpy: S [n, sit], X [n, C, xf], weapon [n, C] (None or under 0: "none") -> [n, C, 6]"""
    S, X = np.asarray(S, np.float32), np.asarray(X, np.float32)
    n, C = X.shape[0], X.shape[1]
    o, xf = N_VERB + int(L["targets"]), int(L.get("xf", 0) or 0)
    assert xf == X.shape[-1], "appraise: the layout reads {} numbers a row, the simulator gives {}".format(xf, X.shape[-1])
    c = np.zeros((n, C, int(L["cand"])), np.float32)
    w = np.full((n, C), N_WEAPON - 1, np.int64) if weapon is None else np.where((np.asarray(weapon) >= 0) & (np.asarray(weapon) < N_WEAPON - 1),
                                                                               np.asarray(weapon, np.int64), N_WEAPON - 1)
    np.put_along_axis(c, (o + w)[..., None], 1.0, axis=-1)
    c[..., o + N_WEAPON:o + N_WEAPON + xf] = X
    if quiet is not None and L.get("quiet"):
        c[..., o + N_WEAPON + xf] = (np.asarray(quiet) > 0).astype(np.float32)
    x = np.concatenate([np.broadcast_to(S[:, None, :], (n, C, S.shape[1])), c], -1)
    z = np.maximum(x @ P["0.weight"].T + P["0.bias"], 0.0)
    z = np.maximum(z @ P["2.weight"].T + P["2.bias"], 0.0)
    z = z @ P["4.weight"].T + P["4.bias"]
    z[..., 2:5] = 1.0 / (1.0 + np.exp(-z[..., 2:5]))
    return z.astype(np.float32)

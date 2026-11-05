"""1.7, the combat order (docs/runs/1.7/README.md S3, BUILD.md part 5): the brain's lesson of the odds that the enemy passes each of the
order's candidates within 1, 2 and 4 s. A readout on the brain's state at its tick (a number: no gradient into the brain, "first with no
gradient into the brain") and a candidate's place as he sees it (the simulator's order_feat numbers: GEO). Graded in hindsight on the
rollout's truth (info["aux"]: his place and facing, the enemy's place, as sim/ahead.py), left out past the rollout's end, a death or a
frag. Its answers go into the candidates' numbers (order_feat's pass_1, pass_2, pass_4) as numbers. No pay, nothing else reads it.

Module: Linear(brain + len(GEO) -> hid) + ReLU + Linear(hid -> 3), its last layer at zero with the prior's bias (PRIOR), from a random
stream of its own.
"""
import math

import torch

HORIZ = (1.0, 2.0, 4.0)
FR = tuple(int(round(h / 0.025)) for h in HORIZ)
R_XY, R_Z = 192.0, 128.0                   # "passes": within this across and up or down (BUILD.md, detail)
GEO = ("k_none", "k_item", "k_enemy", "k_hold", "k_cut", "k_spam", "k_out", "k_way", "valid", "t_me", "t_en", "height", "range",
       "fwd", "left", "up", "sees_1", "sees_2", "sees_4", "seen_me", "door", "corridor", "tele_out", "tele_in")
PRIOR = 0.1
COLS = ("x", "y", "z", "yaw", "en_fwd", "en_left", "en_up", "frag", "fragged", "trk_on")


def layout(feat_names, inp=256, hid=64):
    """feat_names: the simulator's CMB_FEAT (its order_feat columns)"""
    return dict(version=1, inp=int(inp), hid=int(hid), geo=[list(feat_names).index(g) for g in GEO], horiz=list(HORIZ), r_xy=R_XY, r_z=R_Z)


def make_module(L, seed=4171):
    import torch.nn as nn

    class Pass(nn.Module):
        def __init__(self):
            super().__init__()
            self.l1 = nn.Linear(int(L["inp"]) + len(L["geo"]), int(L["hid"]))
            self.l2 = nn.Linear(int(L["hid"]), len(L["horiz"]))
            nn.init.zeros_(self.l2.weight)
            nn.init.constant_(self.l2.bias, math.log(PRIOR / (1.0 - PRIOR)))

        def forward(self, bs, x):
            """bs [..., inp] the brain's state (a number), x [..., R, F] the candidates' numbers -> logits [..., R, 3]"""
            g = x[..., self.geo_idx].float()
            b = bs.detach().float()[..., None, :].expand(*g.shape[:-1], bs.shape[-1])
            return self.l2(torch.relu(self.l1(torch.cat([b, g], -1))))

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        m = Pass()
    m.register_buffer("geo_idx", torch.tensor(L["geo"], dtype=torch.long))
    return m


def labels(aux, done, cols, K, pts):
    """the truth at the keep readings of a rollout: aux [T + 1, N, C] (float), done [T, N], pts [J, N, R, 3] the candidates' places
    at reading j (frame j K) -> (y [J, N, R, 3] 1 where the enemy came within R_XY across and R_Z up or down of the place within the
    horizon, m [J, N, R, 3] the questions that count: his truth there on the reading and over the window, no reset or frag in it,
    the window inside the rollout)"""
    C = {c: i for i, c in enumerate(cols)}
    T = done.shape[0]
    aux = aux.float()
    pts = pts.float()
    J, N, R = pts.shape[0], pts.shape[1], pts.shape[2]
    dn = (done > 0.5).float()
    ev = ((aux[:T + 1, :, C["frag"]] > 0.5) | (aux[:T + 1, :, C["fragged"]] > 0.5)).float()
    cd = torch.cat([torch.zeros_like(dn[:1]), torch.cumsum(dn, 0)], 0)
    ce = torch.cat([torch.zeros_like(ev[:1]), torch.cumsum(ev, 0)], 0)
    on = aux[:, :, C["trk_on"]] > 0.5
    yaw = torch.deg2rad(aux[..., C["yaw"]])
    me = aux[..., [C["x"], C["y"], C["z"]]]
    rel = aux[..., [C["en_fwd"], C["en_left"], C["en_up"]]]
    c, s = torch.cos(yaw), torch.sin(yaw)
    ew = torch.stack([me[..., 0] + c * rel[..., 0] - s * rel[..., 1], me[..., 1] + s * rel[..., 0] + c * rel[..., 1],
                      me[..., 2] + rel[..., 2]], -1)                       # the enemy's place on the map, every frame [T + 1, N, 3]
    oncum = torch.cat([torch.zeros_like(on[:1].float()), torch.cumsum((~on).float(), 0)], 0)    # frames without his truth before t
    y = torch.zeros(J, N, R, len(FR), device=aux.device)
    m = torch.zeros(J, N, R, len(FR), device=aux.device)
    for j in range(J):
        t0 = j * K
        if t0 > T:
            break
        hit = ((torch.linalg.norm(ew[t0, :, None, :2] - pts[j][:, :, :2], dim=-1) < R_XY) &      # (there now: within every horizon)
               ((ew[t0, :, None, 2] - pts[j][:, :, 2]).abs() < R_Z))
        last = t0
        for h, d in enumerate(FR):
            t2 = min(t0 + d, T)
            if t2 > last:
                seg = ew[last + 1:t2 + 1]                                     # [L, N, 3]
                dxy = torch.linalg.norm(seg[:, :, None, :2] - pts[j][None, :, :, :2], dim=-1)
                dz = (seg[:, :, None, 2] - pts[j][None, :, :, 2]).abs()
                hit = hit | ((dxy < R_XY) & (dz < R_Z)).any(0)
                last = t2
            ok = (t0 + d <= T)
            clean = ((cd[t2] - cd[t0]) < 0.5) & ((ce[min(t2 + 1, T + 1)] - ce[t0 + 1]) < 0.5) & ((oncum[t2 + 1] - oncum[t0]) < 0.5)
            y[j, :, :, h] = hit.float()
            m[j, :, :, h] = (clean & on[t0] & bool(ok)).float()[:, None].expand(N, R)
    return y, m


def loss(logits, y, m, w=None):
    """the masked binary cross-entropy (w [..., R]: a weight a candidate, e.g. valid) -> (the loss, its questions)"""
    mm = m if w is None else m * w[..., None]
    n = mm.sum().clamp(min=1.0)
    return (torch.nn.functional.binary_cross_entropy_with_logits(logits.float(), y, reduction="none") * mm).sum() / n, mm.sum()


def np_forward(W, L, bs, x):
    """the readout in numpy: bs [B, inp], x [B, R, F] -> odds [B, R, 3]"""
    import numpy as np
    g = np.asarray(x, np.float32)[..., L["geo"]]
    b = np.repeat(np.asarray(bs, np.float32)[:, None, :], g.shape[1], 1)
    h = np.maximum(0.0, np.concatenate([b, g], -1) @ W["l1.weight"].T + W["l1.bias"])
    z = h @ W["l2.weight"].T + W["l2.bias"]
    return 1.0 / (1.0 + np.exp(-z))

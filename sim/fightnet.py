"""2.2b (docs/runs/2.2/2.2b/CARD.md "The fight network"; the owner, 11-17: "Choosing whether to fight or not and how is literally the core of the
game, so it makes sense it should be its own dedicated network"): THE FIGHT NETWORK. A plain feed-forward network (two hidden layers of 256), no
memory of its own: it reads three (the belief's, the item picker's, the hands'), all as numbers (no gradient into anything it reads), and gives

  scores [4]     one for each fight option: at him, cut him off, an angle on his path, back off (sim/duel_env.py FIGHT). They sit beside the item
                 picker's scores of the items in one list (the trainer's held draw); a trainable bias `sbias` on all four (the one number set by
                 hand at update 60: the four options' total share at that moment, then learnt)
  weapon [10]    a score for each choice of the weapon key (no press, the nine weapons): x FIGHT_W added to the hands' weapon logits
  values [2]     two forecasts of its own pay: the damage and frags part, the win-chance part (each its own lesson; their advantages brought to the
                 same size before they are added)

What it reads (the inputs rule, CLAUDE.md "Inputs": each standardised by its measured average and spread, a constant one by spread 1; clipped
to +-10 and rounded to half precision at the one source, as every reader's inputs since 2026-11-15):
  brain   the belief's memory (the brain's state at its tick)
  trk     the tracker's 18 readable outputs (sim/tracker.py: in control, the fight odds, deaths and contact soon, the enemy's stack as a range)
  obs     the item picker's own columns of his inputs by name (head2's obs_cols: his stack, weapons, ammunition, item timers, score, clock)
  items   the item picker's scores of every target (the log-probabilities of its 17, before the pull)
  head    the item picker's memory (its state that this frame's outputs read)
  hands   the hands' memory
  opts    for each fight option: order_feat()'s numbers of its place (OPT_COLS: valid, his and the enemy's seconds of way, where it is, what it
          sees, a doorway, an item), and the tracker's odds the enemy passes it within 1, 2, 4 s (at him and back off: 0)
  dest    where he is headed now: his target (one-hot), the fight option he is on (one-hot), the seconds he has been headed there

Numpy at the top level (the checks and the plugins read it); torch inside the torch functions.
"""
import numpy as np

VERSION = 1
SEED = 2220
OPTS = ("him", "cut", "angle", "away")
OPT_COLS = ("valid", "t_me", "t_en", "height", "range", "fwd", "left", "up", "sees_1", "sees_2", "sees_4", "seen_me", "door", "corridor",
            "item_up", "item_back", "pro_hold")
N_PASS = 3
NW_KEY = 10
HID = 256
N_OUT = len(OPTS) + NW_KEY + 2
IN_CLIP = 10.0
NEG = -1.0e4                                                  # (a shut or invalid choice's logit: e^-1e4 is 0 in float32)
EN_INTENT, HOLD_INTENT = 8, 9                                 # (sim/duel_env.py's: "the enemy", the first holding place; the trainer checks them)
FG_ASK, FG_KIND, FG_CAND = 2048, 4096, 65536                  # (sim/duel_env.py's keep column for a fight option; the trainer checks them)


def shut_mask(n_target):
    """the item picker's targets shut where the fight options are in his list: "the enemy" and the places"""
    m_ = np.zeros(int(n_target), bool)
    m_[EN_INTENT] = True
    m_[HOLD_INTENT:] = True
    return m_


def layout(brain, trk, obs_cols, obs_names, n_target, head, hands, cmb_feat, pass_norm, hid=HID):
    """the inputs' parts and widths; obs_cols: the item picker's columns of his inputs (head2's obs_cols); cmb_feat: the simulator's CMB_FEAT;
    pass_norm: dict(mean, sd, idx) of the tracker's pass scorer (desc22's order norm of its 19 numbers, and their columns of CMB_FEAT)"""
    parts = [("brain", int(brain)), ("trk", int(trk)), ("obs", len(obs_cols)), ("items", int(n_target)), ("head", int(head)), ("hands", int(hands)),
             ("opts", len(OPTS) * (len(OPT_COLS) + N_PASS)), ("dest", int(n_target) + len(OPTS) + 1)]
    return dict(version=VERSION, parts=[[k_, w_] for k_, w_ in parts], width=int(sum(w_ for _, w_ in parts)), obs_cols=[int(c_) for c_ in obs_cols],
                obs_names=list(obs_names), n_target=int(n_target), hid=int(hid), n_out=N_OUT, opts=list(OPTS), opt_cols=list(OPT_COLS),
                opt_idx=[list(cmb_feat).index(c_) for c_ in OPT_COLS], cmb_f=len(cmb_feat), nw_key=NW_KEY,
                pass_norm=dict(mean=[float(x_) for x_ in pass_norm["mean"]], sd=[float(x_) for x_ in pass_norm["sd"]],
                               idx=[int(x_) for x_ in pass_norm["idx"]]),
                norm=None)


def names(L):
    """every input's name, in order"""
    out = []
    for k_, w_ in L["parts"]:
        if k_ == "obs":
            out += ["obs " + str(n_) for n_ in L["obs_names"]]
        elif k_ == "opts":
            out += ["{} {}".format(o_, c_) for o_ in OPTS for c_ in list(OPT_COLS) + ["pass_1", "pass_2", "pass_4"]]
        elif k_ == "dest":
            out += ["dest target {}".format(j_) for j_ in range(L["n_target"])] + ["dest fight {}".format(o_) for o_ in OPTS] + ["dest seconds"]
        else:
            out += ["{} {}".format(k_, j_) for j_ in range(w_)]
    return out


def pass_in(L, X, xp=np):
    """the pass scorer's numbers of places: X [..., CMB_F] (order_feat()'s columns, a place read as a holding place) -> [..., 19] standardised,
    clipped, rounded to half precision (sim/desc22.py order_norm's arithmetic)"""
    P = L["pass_norm"]
    if xp is np:
        g_ = (np.asarray(X, np.float32)[..., np.asarray(P["idx"], np.int64)] - np.asarray(P["mean"], np.float32)) / np.asarray(P["sd"], np.float32)
        return np.clip(g_, -np.float32(IN_CLIP), np.float32(IN_CLIP)).astype(np.float16).astype(np.float32)
    import torch
    d_ = X.device
    g_ = (X.float()[..., torch.as_tensor(P["idx"], dtype=torch.long, device=d_)] - torch.as_tensor(P["mean"], dtype=torch.float32, device=d_)) \
        / torch.as_tensor(P["sd"], dtype=torch.float32, device=d_)
    return g_.clamp(-IN_CLIP, IN_CLIP).half().float()


def pick_cut(pass3, vc):
    """cut off's candidate: the highest of the odds at 2 and 4 s among the valid ones (he reaches it before the enemy) -> [B] (numpy or torch)"""
    try:
        import torch
        if torch.is_tensor(pass3):
            sc_ = torch.where(vc, torch.maximum(pass3[..., 1], pass3[..., 2]), torch.full_like(pass3[..., 1], -1.0))
            return sc_.argmax(-1)
    except ImportError:
        pass
    sc_ = np.where(vc, np.maximum(pass3[..., 1], pass3[..., 2]), -1.0)
    return sc_.argmax(-1)


def options(F, pass3, xp=np):
    """the four options at a reading from the simulator's fight_feat() F (numpy arrays, or torch tensors with xp=torch) and the pass odds of cut
    off's candidates pass3 [B, FG_NC, 3] -> (rows [B, 4, CMB_F], pass [B, 4, 3], valid [B, 4], cand [B]: the candidate cut off and the angle
    are asked with)"""
    c_ = pick_cut(pass3, F["vc"])
    if xp is np:
        ar_ = np.arange(len(c_))
        rows = np.stack([np.asarray(F["Xh"], np.float32), np.asarray(F["Xc"], np.float32)[ar_, c_], np.asarray(F["Xs"], np.float32)[ar_, c_],
                         np.asarray(F["Xa"], np.float32)], 1)
        ps = np.zeros(rows.shape[:2] + (N_PASS,), np.float32)
        ps[:, 1] = pass3[ar_, c_]
        ps[:, 2] = pass3[ar_, c_]
        valid = np.stack([F["vh"], F["vc"][ar_, c_], F["vs"][ar_, c_], F["va"]], 1).astype(bool)
        return rows, ps, valid, c_
    import torch
    ar_ = torch.arange(len(c_), device=c_.device)
    rows = torch.stack([F["Xh"].float(), F["Xc"].float()[ar_, c_], F["Xs"].float()[ar_, c_], F["Xa"].float()], 1)
    ps = torch.zeros(rows.shape[:2] + (N_PASS,), device=rows.device)
    ps[:, 1] = pass3[ar_, c_].float()
    ps[:, 2] = pass3[ar_, c_].float()
    valid = torch.stack([F["vh"], F["vc"][ar_, c_], F["vs"][ar_, c_], F["va"]], 1).bool()
    return rows, ps, valid, c_


def raw(L, brain, trk, xobs, items, head, hands, rows, ps, tgt, fk, secs, xp=np):
    """the raw inputs [B, width]: brain [B, 256], trk [B, 18] (readable), xobs [B, his list] (his normalised inputs: the obs columns are taken by
    the layout), items [B, n_target] (log-probabilities), head [B, S], hands [B, H], rows [B, 4, CMB_F], ps [B, 4, 3], tgt [B] his target,
    fk [B] the fight option he is on (0 none, 1..4), secs [B] his seconds on the target"""
    if xp is np:
        f32 = lambda z_: np.asarray(z_, np.float32)   # noqa: E731
        B = len(brain)
        oc_ = np.asarray(L["obs_cols"], np.int64)
        opt_ = np.concatenate([f32(rows)[..., np.asarray(L["opt_idx"], np.int64)], f32(ps)], 2).reshape(B, -1)
        dest_ = np.concatenate([np.eye(L["n_target"], dtype=np.float32)[np.clip(np.asarray(tgt, np.int64), 0, L["n_target"] - 1)],
                                np.eye(len(OPTS) + 1, dtype=np.float32)[np.clip(np.asarray(fk, np.int64), 0, len(OPTS))][:, 1:],
                                np.minimum(f32(secs) / 10.0, 2.0)[:, None]], 1)
        return np.concatenate([f32(brain), f32(trk), f32(xobs)[:, oc_], f32(items), f32(head), f32(hands), opt_, dest_], 1)
    import torch
    d_ = brain.device
    B = brain.shape[0]
    oc_ = torch.as_tensor(L["obs_cols"], dtype=torch.long, device=d_)
    opt_ = torch.cat([rows.float()[..., torch.as_tensor(L["opt_idx"], dtype=torch.long, device=d_)], ps.float()], 2).reshape(B, -1)
    dest_ = torch.cat([torch.nn.functional.one_hot(tgt.long().clamp(0, L["n_target"] - 1), L["n_target"]).float(),
                       torch.nn.functional.one_hot(fk.long().clamp(0, len(OPTS)), len(OPTS) + 1).float()[:, 1:],
                       (secs.float() / 10.0).clamp(max=2.0)[:, None]], 1)
    return torch.cat([brain.float(), trk.float(), xobs.float()[:, oc_], items.float(), head.float(), hands.float(), opt_, dest_], 1)


def norm_in(L, x, xp=np):
    """the layout's measured norm: (x - mean) / sd, clipped to +-10, rounded to half precision (the one source)"""
    N_ = L["norm"]
    assert N_ is not None, "the fight network's inputs have no measured norm (tools/fight22_init.py)"
    if xp is np:
        z_ = (np.asarray(x, np.float32) - np.asarray(N_["mean"], np.float32)) / np.asarray(N_["sd"], np.float32)
        return np.clip(z_, -np.float32(IN_CLIP), np.float32(IN_CLIP)).astype(np.float16).astype(np.float32)
    import torch
    d_ = x.device
    z_ = (x.float() - torch.as_tensor(N_["mean"], dtype=torch.float32, device=d_)) / torch.as_tensor(N_["sd"], dtype=torch.float32, device=d_)
    return z_.clamp(-IN_CLIP, IN_CLIP).half().float()


def make_module(L):
    """l1 -> ReLU -> l2 -> ReLU -> l3 (4 scores, 10 weapon scores, 2 values); l3 at zero (every option level, no weapon nudge, values 0); sbias
    0; from a random stream of its own (the global one untouched)"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "fightnet: layout version {} expected".format(VERSION)

    class FightNet(nn.Module):
        def __init__(self):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(SEED)
                self.l1 = nn.Linear(int(L["width"]), int(L["hid"]))
                self.l2 = nn.Linear(int(L["hid"]), int(L["hid"]))
                self.l3 = nn.Linear(int(L["hid"]), int(L["n_out"]))
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()
            self.sbias = nn.Parameter(torch.zeros(()))

        def forward(self, x):
            o_ = self.l3(torch.relu(self.l2(torch.relu(self.l1(x.float())))))
            return o_[:, :len(OPTS)] + self.sbias, o_[:, len(OPTS):len(OPTS) + NW_KEY], o_[:, len(OPTS) + NW_KEY:]
    return FightNet()


def np_params(sd):
    """the weights of a state dict (torch tensors or arrays; the prefix "fight." or none) as numpy arrays"""
    g_ = lambda k_: np.asarray(sd[k_].detach().cpu().numpy() if hasattr(sd[k_], "detach") else sd[k_], np.float32)   # noqa: E731
    pre_ = "fight." if "fight.l1.weight" in sd else ""
    return {k_: g_(pre_ + k_) for k_ in ("l1.weight", "l1.bias", "l2.weight", "l2.bias", "l3.weight", "l3.bias", "sbias")}


def np_forward(P, x):
    """forward() in numpy -> (scores [B, 4], weapon [B, 10], values [B, 2])"""
    h_ = np.maximum(np.asarray(x, np.float32) @ P["l1.weight"].T + P["l1.bias"], 0.0)
    h_ = np.maximum(h_ @ P["l2.weight"].T + P["l2.bias"], 0.0)
    o_ = h_ @ P["l3.weight"].T + P["l3.bias"]
    return (o_[:, :len(OPTS)] + np.float32(P["sbias"])).astype(np.float32), o_[:, len(OPTS):len(OPTS) + NW_KEY].astype(np.float32), \
        o_[:, len(OPTS) + NW_KEY:].astype(np.float32)


def masked_scores(S, valid, xp=np):
    """the scores with an invalid option shut (NEG)"""
    if xp is np:
        return np.where(np.asarray(valid, bool), np.asarray(S, np.float32), np.float32(NEG))
    return xp.where(valid.bool(), S.float(), xp.full_like(S.float(), NEG))


def mix_logp(S, valid, k, p_prac, at_draw, fl_on, joint_lsm=None):
    """(torch) THE MIXTURE: the probability that option k [B] was played at a decision, as the trainer plays it: at a new draw (at_draw) with
    the chance p_prac a practice trip (half: an option dealt evenly among the valid ones; half: from the fight network's own softmax over the
    valid ones), else his list (fl_on: the fight options are in it; joint_lsm [B, 4]: the list's log-probabilities of the four, None: not in it).
    k < 0: an item from the list (its probability is the caller's). -> log p [B]"""
    import torch
    nv_ = valid.float().sum(-1).clamp(min=1.0)
    u_ = valid.float() / nv_[:, None]
    own_ = torch.softmax(masked_scores(S, valid, torch), -1)
    kk_ = k.clamp(min=0)[:, None]
    pm_ = 0.5 * u_.gather(1, kk_).squeeze(1) + 0.5 * own_.gather(1, kk_).squeeze(1)
    pp_ = torch.where(at_draw, torch.full_like(pm_, float(p_prac)), torch.zeros_like(pm_))
    pl_ = torch.zeros_like(pm_)
    if joint_lsm is not None:
        pl_ = torch.where(fl_on, joint_lsm.exp().gather(1, kk_).squeeze(1), torch.zeros_like(pm_))
    return torch.log((pp_ * pm_ + (1.0 - pp_) * pl_).clamp(min=1e-12))


def joint_lsm(items, S, valid, shut, xp=np):
    """the one list's log-probabilities [B, n_target + 4]: the item picker's target logits items [B, n_target] with "the enemy" and the places
    shut (shut [n_target] bool) and the fight network's scores of the valid options"""
    if xp is np:
        it_ = np.where(np.asarray(shut, bool)[None, :], np.float32(NEG), np.asarray(items, np.float32))
        z_ = np.concatenate([it_, masked_scores(S, valid)], 1)
        z_ = z_ - z_.max(1, keepdims=True)
        return z_ - np.log(np.exp(z_).sum(1, keepdims=True))
    import torch
    it_ = torch.where(shut.bool()[None, :], torch.full_like(items.float(), NEG), items.float())
    return torch.log_softmax(torch.cat([it_, masked_scores(S, valid, torch)], -1), -1)


def gae_ticks(pay, val, done, gamma, lam):
    """(torch) GAE on the ticks: pay [J, B] summed over each tick's frames, val [J + 1, B], done [J, B] (a round ended within the tick) ->
    (adv [J, B], ret [J, B])"""
    import torch
    J = pay.shape[0]
    adv = torch.zeros_like(pay)
    last = torch.zeros_like(pay[0])
    for j in range(J - 1, -1, -1):
        nd_ = 1.0 - done[j]
        d_ = pay[j] + gamma * val[j + 1] * nd_ - val[j]
        last = d_ + gamma * lam * nd_ * last
        adv[j] = last
    return adv, adv + val[:J]


def size_of(z):
    """(rule 11) the centred length of the rows of z [..., k]: its size as the ramp flags it (over 40)"""
    import torch
    if torch.is_tensor(z):
        return float((z.float() - z.float().mean(-1, keepdim=True)).norm(dim=-1).mean())
    z = np.asarray(z, np.float32)
    return float(np.linalg.norm(z - z.mean(-1, keepdims=True), axis=-1).mean())


def bias_for_share(lse_items, lse_fight, target, lo=-30.0, hi=30.0):
    """the one number of update 60: the bias b on all four scores at which the four options' total share of his decisions, averaged over the
    rows, is `target`: mean(sigmoid(lse_fight + b - lse_items)) = target (lse_items: the log-sum-exp of the items left in the list, lse_fight:
    of the four scores). Bisection"""
    li_, lf_ = np.asarray(lse_items, np.float64), np.asarray(lse_fight, np.float64)
    if len(li_) == 0 or not 0.0 < float(target) < 1.0:
        return None
    for _ in range(80):
        m_ = 0.5 * (lo + hi)
        sh_ = float(np.mean(1.0 / (1.0 + np.exp(-(lf_ + m_ - li_)))))
        if sh_ < target:
            lo = m_
        else:
            hi = m_
    return 0.5 * (lo + hi)


def ppo_term(lp, lp_old, adv, w, clip, cap=3.0):
    """(torch) the clipped term on rows: ratio exp(lp - lp_old), advantages adv, weights w (0/1) -> the loss (to minimise), the share clipped"""
    import torch
    r_ = (lp - lp_old).clamp(max=30.0).exp()
    t_ = torch.min(r_ * adv, r_.clamp(1 - clip, 1 + clip) * adv)
    t_ = torch.where(adv < 0, torch.max(t_, cap * adv), t_)
    ws_ = w.sum().clamp(min=1.0)
    return -(t_ * w).sum() / ws_, float((((r_ - 1.0).abs() > clip).float() * w).sum() / ws_)


def std_adv(a, w):
    """(torch) advantages brought to mean 0, spread 1 over the rows weighted w"""
    import torch
    ws_ = w.sum().clamp(min=1.0)
    mu_ = (a * w).sum() / ws_
    sd_ = (((a - mu_) ** 2 * w).sum() / ws_).sqrt().clamp(min=1e-8)
    return (a - mu_) / sd_


def l2_decay(mod, w, lr):
    """(rule 11) decoupled decay on the first and the last layer (H2_L2's form): p -= lr x w x p"""
    import torch
    if w <= 0:
        return
    with torch.no_grad():
        for p_ in (mod.l1.weight, mod.l3.weight):
            p_.mul_(1.0 - float(lr) * float(w))


def sizes(mod):
    """the decayed layers' sizes (their norms): first and last"""
    return dict(l1=round(float(mod.l1.weight.norm()), 4), l3=round(float(mod.l3.weight.norm()), 4), sbias=round(float(mod.sbias), 4))


class NpFight:
    """(the readers: sim/test_suite.py, the build's tests) the fight network in numpy as the trainer plays it at a keep reading. fck: the
    checkpoint's "fight22" (layout, model); h2W: the head's weights (prefix "head2." stripped: the tracker's trk.*); h2L: the head's layout"""

    def __init__(self, fck, h2W, h2L):
        import tracker as tracker_
        self.L = fck["layout"]
        self.P = np_params(fck["model"])
        self.TL = h2L["trk22"]
        self.trkW = tracker_.np_params(h2W)
        self.passW = tracker_.np_pass_params(h2W)
        assert self.trkW is not None and self.passW is not None, "the fight network reads the tracker and its pass odds: the head has none"

    def reading(self, F, brain, xn, items, head, hands, tgt, fk, secs):
        """F: the simulator's fight_feat() of these seats (after the frame before); brain [B, 256] the brain's state; xn [B, his list] his
        normalised inputs; items [B, n_target] the target logits before the pull; head [B, S] the head's state the frame's outputs read; hands
        [B, H] his memory after the frame; tgt, fk, secs: where he is headed (the simulator's, after the frame before) -> dict(S scores,
        W weapon scores, V values, valid, cand, x the network's inputs, trk, pass3)"""
        import tracker as tracker_
        h_ = tracker_.np_trunk(self.trkW, tracker_.np_inp(self.TL, brain, xn))
        trk_ = tracker_.np_readable(h_ @ self.trkW[4].T + self.trkW[5])
        p3_ = tracker_.np_pass(self.passW, h_, pass_in(self.L, F["Xc"]))
        rows, ps, valid, c_ = options(F, p3_)
        z_ = np.asarray(items, np.float32)
        z_ = z_ - z_.max(1, keepdims=True)
        lsm_ = z_ - np.log(np.exp(z_).sum(1, keepdims=True))
        xr_ = raw(self.L, brain, trk_, xn, lsm_, head, hands, rows, ps, tgt, fk, secs)
        if self.L.get("norm") is None:                       # (tools/fight22_init.py sample: the raw inputs, before the norm is measured; the last
            B_ = len(xr_)                                    # layer at zero: every score 0)
            return dict(S=np.zeros((B_, len(OPTS)), np.float32), W=np.zeros((B_, NW_KEY), np.float32), V=np.zeros((B_, 2), np.float32),
                        valid=valid, cand=c_, x=xr_, trk=trk_, pass3=p3_)
        x_ = norm_in(self.L, xr_)
        S, W, V = np_forward(self.P, x_)
        return dict(S=S, W=W, V=V, valid=valid, cand=c_, x=x_, trk=trk_, pass3=p3_)

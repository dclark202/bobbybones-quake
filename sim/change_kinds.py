"""(b22r, owner 2026-11-16) READOUTS ONLY of his changes of target mid-trip (the held draw; sim/train_duel_rnn.py, "the kinds of his changes
mid-trip"): nothing here is played or learnt. The owner: "Interrupt because responding to something is what should be happening. Interrupt
for no good reason is what shouldn't"; his good pattern: "going to mega; sees enemy, fires a shot to force him to back off; resumes going to
mega". The trainer's own definitions are used, not redefined here:
  news           the keep row the choice read (the frame before the change) has contact (column 1 > 0: the enemy seen within CONTACT_S), a
                 sound (column 5, seconds since he heard the enemy, < 1.0) or a hit unseen (column 6, seconds since he was hit with the enemy
                 out of view, < 1.0): news_kinds() below is that test split by kind (its any() is the trainer's nws_)
  back within 2 s, judged   the trainer's PBK_["back"] (back to the old target within 80 frames, no new draw between) over the changes made
                 at least 80 frames before the rollout's end (its full_)
Kept beside the trainer's list of changes (PBK_), in the same order: per change its news (by kind), the new target, the plan's top target
at the change and the frame of the return (-1: none). Per keep reading on a held trip (the population where a change can happen): the base
rate of news. summary() gives the record's new keys."""
import torch

KINDS = ("contact", "sound", "hit_unseen")
NB_ = 9                                                      # base readings, with news, by kind (3); changes by kind (3); changes off a reading


def news_kinds(kf):
    """[n, 3] bool from keep rows kf [n, >= 7]: contact (col 1 > 0), a sound within 1 s (col 5 < 1.0), a hit unseen within 1 s (col 6 < 1.0)"""
    return torch.stack([kf[:, 1] > 0, kf[:, 5] < 1.0, kf[:, 6] < 1.0], 1)


def plan_top(pl0, sl0, mix, floor):
    """the plan's top target [n] at horizon 0 as it pulled: the fast plan's odds pl0 [n, NI]; with a slow half's odds sl0 and mix > 0 the
    mixed log-odds (1 - mix) x log(max(fast, floor)) + mix x log(max(slow, floor)) (sim/slowhalf.pull_mix's source)"""
    if sl0 is None or float(mix) <= 0.0:
        return pl0.float().argmax(-1)
    lf = torch.log(pl0.float().clamp(min=float(floor)))
    ls = torch.log(sl0.float().clamp(min=float(floor)))
    return ((1.0 - float(mix)) * lf + float(mix) * ls).argmax(-1)


def new_state(dev):
    """(per rollout) the per-change list (parallel to the trainer's PBK_) and the counts"""
    return (dict(kind=torch.zeros(0, 3, dtype=torch.bool, device=dev), new=torch.zeros(0, dtype=torch.long, device=dev),
                 ptop=torch.zeros(0, dtype=torch.long, device=dev), tb=torch.zeros(0, dtype=torch.long, device=dev),
                 seen=torch.zeros(0, dtype=torch.bool, device=dev)),
            torch.zeros(NB_, dtype=torch.float64, device=dev))


def frame(S, NB, PBK, t, reading, kf_old, tg_n, ev, base, top_fn):
    """one frame, AFTER the trainer's own block updated PBK (its backs found this frame, this frame's changes appended): the frame of each
    newly found back; the base counts (base [N] bool: his seats on a held trip, alive, no new draw, at a keep reading); this frame's changes
    ev [N] (the trainer's ev_p) with their kinds of news from kf_old (the rows the choice read), the new target tg_n and top_fn(seats) the
    plan's top target. Returns S (NB in place)."""
    n0 = len(S["seen"])
    if n0:
        nb_ = PBK["back"][:n0] & ~S["seen"]
        S["tb"] = torch.where(nb_, torch.full_like(S["tb"], int(t)), S["tb"])
        S["seen"] = S["seen"] | nb_
    nk_ = news_kinds(kf_old)
    if reading:
        bk_ = nk_ & base[:, None]
        NB[0] += base.sum().double()                         # (on the device: no wait for the card)
        NB[1] += bk_.any(1).sum().double()
        NB[2:5] += bk_.sum(0).double()
    if bool(ev.any()):                                       # (the trainer's own block waits on the same test this frame)
        se_ = torch.nonzero(ev, as_tuple=True)[0]
        NB[5:8] += nk_[se_].sum(0).double()
        if not reading:
            NB[8] += len(se_)
        S = dict(kind=torch.cat([S["kind"], nk_[se_]]), new=torch.cat([S["new"], tg_n[se_]]), ptop=torch.cat([S["ptop"], top_fn(se_).long()]),
                 tb=torch.cat([S["tb"], torch.full_like(se_, -1)]), seen=torch.cat([S["seen"], torch.zeros_like(se_, dtype=torch.bool)]))
    if len(S["seen"]) != len(PBK["seat"]):
        raise RuntimeError("the change kinds' list ({}) is out of step with the trainer's ({})".format(len(S["seen"]), len(PBK["seat"])))
    return S


def _r(x, d=4):
    return None if x is None else round(float(x), d)


def summary(S, NB, PBK, PCH, T, BK, held_min, src):
    """the record's new keys (beside the trainer's n, back_2s, n_2s, news, against_plan, unchanged)"""
    full_ = PBK["t0"] <= (T - 1 - 80)                        # (the trainer's full_: the changes old enough to be judged)
    bk_ = PBK["back"] & full_
    st_ = ~PBK["back"] & full_
    nw_ = S["kind"].any(1)
    n2_ = float(full_.sum())
    c_ = dict(news_back=float((bk_ & nw_).sum()), news_stuck=float((st_ & nw_).sum()), quiet_back=float((bk_ & ~nw_).sum()),
              quiet_stuck=float((st_ & ~nw_).sum()))
    out = {k_: _r(v_ / max(1.0, n2_)) for k_, v_ in c_.items()}
    out.update({k_ + "_n": int(v_) for k_, v_ in c_.items()})
    nch_ = float(PCH[0])
    base_ = float(NB[1]) / float(NB[0]) if float(NB[0]) > 0 else None
    atc_ = float(PCH[1]) / nch_ if nch_ > 0 else None
    out.update(news_base=_r(base_), news_at_change=_r(atc_), news_lift=_r(atc_ / base_, 3) if (base_ and atc_ is not None) else None,
               base_n=int(NB[0]), off_reading_n=int(NB[8]))
    kd_ = {}
    for i_, k_ in enumerate(KINDS):
        b_ = float(NB[2 + i_]) / float(NB[0]) if float(NB[0]) > 0 else None
        a_ = float(NB[5 + i_]) / nch_ if nch_ > 0 else None
        kd_[k_] = dict(base=_r(b_), at_change=_r(a_), lift=_r(a_ / b_, 3) if (b_ and a_ is not None) else None)
    out["news_kind"] = kd_
    nbk_, nst_ = float(bk_.sum()), float(st_.sum())
    out.update(back_to_plan=_r(float((bk_ & (PBK["old"] == S["ptop"])).sum()) / nbk_) if nbk_ > 0 else None,
               stuck_to_plan=_r(float((st_ & (S["new"] == S["ptop"])).sum()) / nst_) if nst_ > 0 else None, plan_src=src)
    if nbk_ > 0:
        g_ = (S["tb"][bk_] - PBK["t0"][bk_]).double() / float(BK)
        out["back_gap"] = dict(median=_r(g_.median(), 2), mean=_r(g_.mean(), 2), n=int(nbk_))
    else:
        out["back_gap"] = dict(median=None, mean=None, n=0)
    out.update(news_min=_r(float(PCH[1]) / held_min, 3) if held_min > 0 else None,
               quiet_min=_r((nch_ - float(PCH[1])) / held_min, 3) if held_min > 0 else None)
    return out

"""2.2a (docs/runs/2.2/DESIGN.md): a 2.1d network given 2.2a's parts inside its strategy head, with nothing of them in effect, so that it answers
exactly as before.

    python tools/out22_init.py add <2.1d's end> <out.pt> --samples <play22 sample npz>[,<...>] [--metrics <2.1d's metrics.jsonl>]
        the run's start. The head's layout gets:
          "outlook"  sim/head2.py add_outlook with the kinds seg, ret, all8, win8, win5, segw, winit8 and the facts (head2.out.*: l3 and l3f at
                     zero); out_g 0, out_pick 0 (seg)
          "trk22"    the tracker (sim/tracker.py; head2.trk.*, l3 at zero): the brain's state + the head's own columns (its obs_cols) + the
                     counters of tracker.EXTRA found by name in the network's input list
          "desc22"   the desc outlooks (sim/desc22.py; head2.dsc.<desc, desc_nomap, desc_notrk>.*, l3 at zero), its inputs' norm MEASURED on the
                     samples (tools/run/play22.py sample: 2.1d's end playing in the simulator): each column's mean and spread over the keep
                     readings (a target's columns over the targets there, valid 1); the tracker's twelve chances by the measured base rate of
                     their labels (mean p, spread sqrt(p (1 - p))): the fight's and the deaths' and contact's from the samples, in control's from
                     2.1d's own control readout in its metrics (its labels' counts: --metrics); the stack quantiles by the enemy's measured health
                     and armor (hundreds); a column constant in the samples gets spread 1 (listed)
          "vw"       the head's second value (head2.vw.*, its last layer at zero)
        and out_src 0 (the built outlook's term). The checkpoint gets "map_sense": the map sense's layout over the ten maps' tables
        (data/maps/space_<map>.npz) and the start file's weights (data/sim_runs/space/mapsense_start.pt), the corrections at zero. Everything
        else is kept: the slow plan and its Adam, the pull, the main optimizer (none of the new parts is in its groups)
"""
import argparse
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")
CMB_FEAT = ("k_none", "k_item", "k_enemy", "k_hold", "k_cut", "k_spam", "k_out", "k_way", "valid", "t_me", "t_en", "height", "range",
            "fwd", "left", "up", "sees_1", "sees_2", "sees_4", "seen_me", "door", "corridor", "width", "tele_out", "tele_in",
            "item_up", "item_back", "pro_rl", "pro_gl", "pro_pg", "pro_hold", "pass_1", "pass_2", "pass_4")     # (sim/duel_env.py's, checked below)
CMB_CTX = ("contact", "seen_ago", "health", "armor", "en_health", "en_armor", "ahead_ok", "belief_ok", "ahead_range", "ahead_height",
           "w_rl", "w_lg", "w_rg", "w_other")
NEAR_CONST = 1e-3                                             # (a column whose measured spread is under this: spread 1)
CONTROL_D, FIGHT_D = 3600, 200                                # (the simulator's CONTROL_H 90 s, FIGHT_H 5 s at 40 frames a second; the trainer checks)


def rates(samples):
    """the measured base rates of the tracker's near labels and the enemy's stack, from the samples' per-frame truths"""
    import tracker as TR
    acc = {k_: [0.0, 0.0] for k_ in TR.OUTS[4:12]}
    eh, ea = [], []
    for z in samples:
        died, con, alive, enal = z["died"], z["con"], z["alive"], z["en_alive"]
        F, n = died.shape
        foe = np.arange(n) ^ 1
        end = z["clr"] & ~died
        fw, fl = z["fo_win"], z["fo_lose"]
        D = FIGHT_D
        for k_, (y_, m_) in (("fo_win", (fw[D:], fw[D:] >= 0)), ("fo_lose", (fl[D:], fl[D:] >= 0))):
            acc[k_][0] += float(y_[m_].sum())
            acc[k_][1] += float(m_.sum())
        for t in range(1, F - 400, 8):
            al_ = alive[t - 1]                               # (he alive at the frame of the reading: after the step before)
            for nm_, W_, ev_ in (("idie5", 200, died), ("idie10", 400, died), ("hedie5", 200, died[:, foe]), ("hedie10", 400, died[:, foe]),
                                 ("con2", 80, con), ("con5", 200, con)):
                win_ = ev_[t:t + W_]
                cut_ = end[t:t + W_] | (died[t:t + W_] if nm_.startswith("con") else np.zeros_like(end[t:t + W_]))
                fe_ = np.where(win_.any(0), win_.argmax(0), 10 ** 6)
                fc_ = np.where(cut_.any(0), cut_.argmax(0), 10 ** 6)
                y_ = (fe_ < 10 ** 6) & ((fe_ <= fc_) if not nm_.startswith("con") else ((fe_ <= fc_)))
                acc[nm_][0] += float(y_[al_].sum())
                acc[nm_][1] += float(al_.sum())
        m_ = z["alive"][:-1] & z["en_alive"][:-1]
        hp = z["hp"][:-1]
        eh.append(hp[:, foe, 0][m_] / 100.0)
        ea.append(hp[:, foe, 1][m_] / 100.0)
    out = {k_: (v_[0] / v_[1] if v_[1] > 0 else 0.5) for k_, v_ in acc.items()}
    eh, ea = np.concatenate(eh), np.concatenate(ea)
    return out, dict(eh=(float(eh.mean()), float(eh.std())), ea=(float(ea.mean()), float(ea.std())), n=dict({k_: int(v_[1]) for k_, v_ in acc.items()}, stack=int(len(eh))))


def pass_rates(samples):
    """(2.2a) the base rate of the pass odds' labels in the samples, per horizon: at each keep reading, every place target there (an item or a
    holding place, valid), the enemy within sim/passodds.py's 192 across and 128 up or down of it at the reading's frame or within 1, 2, 4 s,
    no reset of his and no death of either in the window, the window inside the sample"""
    import tracker as TR
    hit_n, n_ = np.zeros(3), np.zeros(3)
    for z in samples:
        pos, clr, died = z["pos"], z["clr"], z["died"]
        F, n = clr.shape
        foe = np.arange(n) ^ 1
        rt, ri, P = z["rt"], z["ri"], z["pts"]
        valid = z["tgt"][..., 0] > 0.5
        place = valid & np.isin(np.arange(P.shape[1]), np.asarray(TR.PASS_TARGETS))[None, :]
        for r_ in range(len(rt)):
            t, i = int(rt[r_]), int(ri[r_])
            if t < 1:
                continue
            for h_, d_ in enumerate(TR.PASS_FR):
                if t + d_ > F:
                    continue
                if clr[t:t + d_, i].any() or died[t:t + d_, i].any() or died[t:t + d_, foe[i]].any():
                    continue
                e_ = pos[t - 1:t + d_, foe[i]]                    # (the enemy's place at frames t .. t + d: after the steps t - 1 .. t + d - 1)
                pk_ = place[r_]
                if not pk_.any():
                    continue
                pp_ = P[r_][pk_]
                dxy = np.linalg.norm(e_[:, None, :2] - pp_[None, :, :2], axis=-1)
                dz = np.abs(e_[:, None, 2] - pp_[None, :, 2])
                hit_n[h_] += ((dxy < TR.PASS_R_XY) & (dz < TR.PASS_R_Z)).any(0).sum()
                n_[h_] += pk_.sum()
    return [float(hit_n[h_] / max(1.0, n_[h_])) for h_ in range(3)], [int(x_) for x_ in n_]


def ctl_rates(metrics):
    """in control's base rates from 2.1d's own control readout (its last record with frames): the mean of each label, from the counts above,
    below and at a half (two: 0.5 counted half)"""
    last = None
    for ln in open(metrics, encoding="utf-8"):
        try:
            r = json.loads(ln)
        except Exception:                                    # noqa: BLE001
            continue
        c = r.get("control")
        if c and c.get("frames") and min(c["frames"]) > 0:
            last = (r.get("update"), c)
    assert last is not None, "no control record in {}".format(metrics)
    u, c = last
    out = []
    for j in range(4):
        n_, p_, q_ = float(c["frames"][j]), float(c["pos"][j]), float(c["neg"][j])
        out.append(((p_ + 0.5 * (n_ - p_ - q_)) / n_, math.sqrt(max(float(c["brier_const"][j]), 1e-6))))   # (the labels' own spread)
    return out, u, c["frames"]


def norm_of(samples, rt, st, ctl):
    import desc22 as D
    import tracker as TR
    sn, tn = D.sit_names(), D.tgt_names()
    S = np.concatenate([z["sit"] for z in samples]).astype(np.float64)
    G = np.concatenate([z["tgt"] for z in samples]).astype(np.float64)
    vi = tn.index("valid")
    Gv = G[G[..., vi] > 0.5]
    sm, ss = S.mean(0), S.std(0)
    tm, ts = Gv.mean(0), Gv.std(0)
    const = []
    for nm_, m_, s_ in ((sn, sm, ss), (tn, tm, ts)):
        for k_, x_ in enumerate(s_):
            if not x_ > NEAR_CONST:                       # (the review: a constant or nearly constant column gets spread 1)
                const.append(nm_[k_])
                s_[k_] = 1.0
    # the tracker's: by design from the base rates
    for j_, o_ in enumerate(TR.OUTS):
        k_ = sn.index("trk " + o_)
        if j_ < 4:
            sm[k_], ss[k_] = ctl[j_]
            if ("trk " + o_) in const:
                const.remove("trk " + o_)
            continue
        elif j_ < TR.NB:
            p_ = rt[o_ if o_ not in ("fo_win", "fo_lose") else o_]
        else:
            p_ = None
        if p_ is not None:
            sm[k_], ss[k_] = p_, max(math.sqrt(max(p_ * (1.0 - p_), 0.0)), 1e-3)
        else:
            mu_, sd_ = st["eh"] if o_.startswith("enh") else st["ea"]
            sm[k_], ss[k_] = mu_, max(sd_, 1e-3)
        if ("trk " + o_) in const:
            const.remove("trk " + o_)
    for h_, nm_ in enumerate(D.PASS_NAMES):                   # (2.2a: the pass odds by design from their measured base rates)
        k_ = tn.index(nm_)
        p_ = st["pass"][h_]
        tm[k_], ts[k_] = p_, max(math.sqrt(max(p_ * (1.0 - p_), 0.0)), 1e-3)
        if nm_ in const:
            const.remove(nm_)
    return dict(sit_mean=[float(x_) for x_ in sm], sit_sd=[float(x_) for x_ in ss], tgt_mean=[float(x_) for x_ in tm], tgt_sd=[float(x_) for x_ in ts],
                measured=True, rows=int(len(S)), target_rows=int(len(Gv)), constant=const,
                trk_by_design=dict(ctl=ctl, near={k_: round(v_, 5) for k_, v_ in rt.items()}, stack=st, pass_rates=st["pass"], pass_n=st["pass_n"]))


def add(a):
    import torch
    import head2 as H2
    import outlook as OL
    import tracker as TR
    import desc22 as D
    import mapsense as MS
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L = ck.get("head2")
    assert L is not None and H2.has_goal(L) and H2.has_slowplan(L), "a 2.1d network: the goal part and the slow plan inside the head"
    assert not H2.has_outlook(L), "the head has the outlook already (a 2.1f file): start from 2.1d's end"
    import duel_env_ffa as E                                 # (the constants only: the order's columns)
    assert tuple(E.CMB_FEAT) == CMB_FEAT and tuple(E.CMB_CTX) == CMB_CTX, "the simulator's order columns changed"
    assert int(E.CONTROL_D) == CONTROL_D and int(E.FIGHT_D) == FIGHT_D, "the simulator's horizons are not the defaults"
    L1 = H2.add_outlook(L, kinds=OL.KINDS22, hid=128, facts=True)
    names = [" | ".join(x_) for x_ in ck["input_names"]]
    xc, xn, miss = TR.extra_cols(ck["input_names"])
    oc = list(L["obs_cols"]) + [c_ for c_ in xc if c_ not in L["obs_cols"]]
    TL = None                                                 # (made below, once the pass odds' base rates are measured)
    samples = [np.load(p_) for p_ in a.samples.split(",") if p_]
    got_ = sorted(str(z_["map"]) for z_ in samples)
    assert got_ == sorted(MAPS), "the norm is measured on all ten training maps (the review): the samples have {}".format(got_)
    rt, st = rates(samples)
    st["pass"], st["pass_n"] = pass_rates(samples)
    ctl, cu, cf = ctl_rates(a.metrics)
    nm = norm_of(samples, rt, st, ctl)
    TL = TR.layout(oc, [names[c_] for c_ in oc], bel=int(ck["belief"]["hid"]), ctl_d=CONTROL_D, fight_d=FIGHT_D, pass_in=len(D.TGT_COLS),
                   pass_prior=st["pass"])
    nm["ctl_from"] = dict(metrics=os.path.basename(a.metrics), update=cu, frames=cf)
    nm["samples"] = [os.path.basename(p_) for p_ in a.samples.split(",") if p_]
    DL = D.layout(OL.KINDS22, OL.FACTS, head=int(L["size"]), n_target=int(L["n_target"]), hid=128, norm=nm, cmb_feat=CMB_FEAT, cmb_ctx=CMB_CTX)
    L2 = H2.add_parts22(L1, TL, DL)
    m2 = H2.make_module(L2)
    old = {k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")}
    new = m2.state_dict()
    for k_, v_ in old.items():                               # every part of before as it was
        assert k_ in new and new[k_].shape == v_.shape, "head2.{}: not in the new head".format(k_)
        new[k_] = v_.clone()
    for k_ in ("out_g", "out_pick", "out_src"):
        new[k_] = torch.zeros(())
    m2.load_state_dict(new, strict=True)
    for k_, v_ in m2.state_dict().items():
        ck["model"]["head2." + k_] = v_.detach().clone()
    for nm_ in ("out.l3.weight", "out.l3.bias", "out.l3f.weight", "out.l3f.bias", "trk.l3.weight", "trk.l3.bias", "vw.l2.weight", "vw.l2.bias",
                "trk.p2.weight") + \
            tuple("dsc.{}.l3.{}".format(s_, w_) for s_ in DL["sibs"] for w_ in ("weight", "bias")):
        assert float(ck["model"]["head2." + nm_].abs().sum()) == 0.0, nm_ + " not at zero"
    ck["head2"] = L2
    ck["env_vars"] = dict(ck.get("env_vars") or {}, DESC_OX="1")   # (the checks and the servers: the file's readers load the order's map numbers)
    tabs, mmiss = MS.load_tables(DATA and os.path.dirname(DATA), MAPS)
    assert not mmiss, "the map sense's tables missing: {}".format(mmiss)
    msL = MS.layout(tabs)
    msm = MS.make_module(msL)
    about = MS.load_start(msm, a.ms_start)
    ck["map_sense"] = dict(layout=msL, model={k_: v_.detach().clone() for k_, v_ in msm.state_dict().items()})
    torch.save(ck, a.out)
    print("wrote {}: {}".format(a.out, H2.describe(L2)))
    print("the tracker reads the brain's {} + {} columns ({} counters by name{}); the desc outlooks' norm measured on {} keep-reading rows ({} targets "
          "there) of {}; columns constant in the samples (spread 1): {}".format(TL["bel"], len(oc), len(xc), "; MISSING: " + ", ".join(miss) if miss else "",
                                                                                nm["rows"], nm["target_rows"], nm["samples"], nm["constant"] or "none"))
    print("the tracker's chances by design: in control {} (2.1d's control readout at update {}), near {}, the enemy's stack (hundreds) {}".format(
        [(round(x_[0], 4), round(x_[1], 4)) for x_ in ctl], cu, nm["trk_by_design"]["near"], st))
    print("the map sense: {} maps, {} corrections at zero, the shared part from {} ({})".format(len(msL["maps"]), msL["rows"], a.ms_start, about))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--samples", required=True)
    p.add_argument("--metrics", default=os.path.join(DATA, "sim_runs", "duel_gru_2_1d", "metrics.jsonl"))
    p.add_argument("--ms-start", default=os.path.join(DATA, "sim_runs", "space", "mapsense_start.pt"))
    a = ap.parse_args()
    sys.exit(int({"add": add}[a.cmd](a) or 0))


if __name__ == "__main__":
    main()

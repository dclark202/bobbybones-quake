"""(brainppl) the overnight scoreboard: a save's brain on held-out people's data (the held-out pro demos, by file, and the
owner's play tests of 2026-10-24 in data/duellive_v042: Campgrounds and Hektik apart), beside a reference save.

    python tools/brainppl_score.py --ck <save> [--ref <save 160>] [--out <json>] [--hands]

  (a) the target: top-1 overall, and the weapon recall (the brain's top-1 is RL when the person's next big take was RL; RG)
  (b) the 1 s and 2 s places: the median error's gain over "he stays where the brain believes him now"
  (c) appearance: the mean predicted P(in view within 1 s) over the actual rate (the label's own definition: the first
      frame after the tick with the enemy in his raw field of view and line of sight, while he is not in view now)
  (d) the item race (sessions; demos have none): sign accuracy of his walking-time lead, and the false leads (the brain says
      he is more than 1 s ahead and the person is there when it comes back)
  (e) --hands: the hands over the owner's recorded sessions (their inputs replayed, sim/brain_data.py --xl) with each save's
      brain: the intention's shares, how often it names the red armor while it is down for more than 10 s, and the mean
      (the hands' use of the token in a run: the trainer's btoken.effect, logged every update)
"""
import argparse
import json
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import ahead as ahead_  # noqa: E402
import brain_data as BD  # noqa: E402
import brain_fit as BF  # noqa: E402
import track as track_  # noqa: E402

INT = ("none", "MH", "RA", "RL", "RG", "LG", "YA", "YA2", "EN")


def outputs(brain, P, Y, nf, dev):
    W, B = Y[0].shape[:2]
    O = [torch.zeros(W, B, track_.D), torch.zeros(W, B, 28), torch.zeros(W, B, int(brain.L["ahead"]["d"]))]

    def col(sl, o1, o2, o3, tm):
        n = o1.shape[0]
        for k_, o_ in enumerate((o1, o2, o3)):
            O[k_][sl.start:sl.start + n] = o_.cpu()
    brain.eval()
    BF.run_pieces(brain, P, Y, nf, dev, train=False, collect=col)
    return O


def scores(brain, P, Y, nf, dev, nt, L):
    trk_y, trk_m, trz_y, ah_y, ex = Y
    O1, O2, O3 = outputs(brain, P, Y, nf, dev)
    r = {}
    nh = len(ahead_.HORIZ)
    fut, fm, tg, tmk, ap, am = ah_y[:6]
    tl = O3[..., 5 * nh:5 * nh + nt]
    mt = tmk > 0.5
    top = tl.argmax(-1)
    r["target_top1"] = round(float((top == tg)[mt].float().mean()), 4) if mt.any() else None
    if mt.any():                                             # the odds' log loss and Brier score, the confusion (truth row, top-1 column)
        lp = torch.log_softmax(tl, -1)
        r["target_logloss"] = round(float(-lp.gather(-1, tg[..., None])[..., 0][mt].mean()), 4)
        oh = torch.nn.functional.one_hot(tg.clamp(0, nt - 1), nt).float()
        r["target_brier"] = round(float(((lp.exp() - oh) ** 2).sum(-1)[mt].mean()), 4)
        cls = sorted(set(tg[mt].tolist()) | set(top[mt].tolist()))
        names = [INT[c] if c < len(INT) else "H{}".format(c - 8) for c in cls]
        cm = {names[i]: {names[j]: int(((tg == ci) & (top == cj) & mt).sum()) for j, cj in enumerate(cls)} for i, ci in enumerate(cls)}
        r["target_confusion"] = {k: {kk: vv for kk, vv in v.items() if vv} for k, v in cm.items() if sum(v.values())}
        tp_ = torch.from_numpy(P["tpos"][np.arange(7, P["L"], 8)])          # (the tick's frame in its own session: the game's minute)
        mn = (tp_ // 2400).clamp(max=9)
        r["target_top1_by_minute"] = {int(m_): round(float((top == tg)[mt & (mn == m_)].float().mean()), 3)
                                      for m_ in range(10) if bool((mt & (mn == m_)).any())}
    r["target_n"] = int(mt.sum())
    for w_ in ("RL", "RG", "MH", "RA"):
        k_ = INT.index(w_)
        m_ = mt & (tg == k_)
        r["recall_" + w_] = round(float((top == k_)[m_].float().mean()), 4) if m_.any() else None
        r["n_" + w_] = int(m_.sum())
    pos = O1[..., track_.SL["pos"]] * track_.U
    f = O3[..., :5 * nh].reshape(*O3.shape[:2], nh, 5)
    for j, hz in enumerate(ahead_.HORIZ[:2]):
        mj = fm[..., j] > 0.5
        if mj.any():
            e = ((f[..., j, :2] - fut[..., j, :2]).norm(dim=-1) * 1000.0)[mj]
            eb = ((pos[..., :2] / 1000.0 - fut[..., j, :2]).norm(dim=-1) * 1000.0)[mj]
            r["ahead_{:g}s".format(hz)] = dict(median=round(float(e.median()), 1), stays=round(float(eb.median()), 1),
                                              gain=round(float(eb.median() - e.median()), 1), n=int(mj.sum()))
    al = torch.softmax(O3[..., 5 * nh + nt:5 * nh + nt + 4], -1)
    ma = am > 0.5
    if ma.any():
        p1 = float(al[..., 0][ma].mean())
        a1 = float((ap == 0)[ma].float().mean())
        r["appear_1s"] = dict(pred=round(p1, 4), actual=round(a1, 4), ratio=round(p1 / max(a1, 1e-6), 3), n=int(ma.sum()))
    if L.get("race") and len(ah_y) > 6:
        lead, lm, there, thm = ah_y[6:]
        r0 = ahead_.race_at(L)
        rr = O3[..., r0:r0 + 6].reshape(*O3.shape[:2], 2, 3)
        m_ = lm > 0.5
        if m_.any():
            r["race_sign_acc"] = round(float((torch.sign(rr[..., 0]) == torch.sign(lead))[m_].float().mean()), 4)
            r["race_n"] = int(m_.sum())
        m2 = (thm > 0.5) & (rr[..., 0] > 0.1)                 # (he believes he is more than 1 s ahead, and it is down)
        if m2.any():
            r["race_false_leads"] = round(float((there > 0.5)[m2].float().mean()), 4)
            r["race_lead_claims"] = int(m2.sum())
    return r


def hands(ck_a, ck_b, streams, frames=6000):
    """the intention's shares and the red armor while down, the token's attention weight, with each save"""
    import test_suite as T_
    import attn as attn_
    import btoken as btoken_
    C = {k: i for i, k in enumerate(BD.COLS)}
    out = {}
    for tag, ck in (("ref", ck_a), ("new", ck_b)):
        p = T_.Policy(ck)
        sel = [s for s in streams if "xl" in s and len(s["obs"]) >= min(frames, 3000)]
        n = min(min(len(s["obs"]) for s in sel), frames)
        h = p.zeros(len(sel))
        o_ = np.concatenate([[0], np.cumsum(p.dims)]).astype(int)
        cnt = np.zeros(17)
        ra_down = ra_named = 0
        for t in range(n):
            ob = np.stack([s["obs"][t] for s in sel]).astype(np.float32)
            ax = np.stack([s["aux"][t] for s in sel])
            pose, zm = btoken_.pose_from_aux(ax, BD.COLS)
            xl = np.stack([s["xl"][t] for s in sel]).astype(np.float32)
            _, h = p.act(ob, h, pose=pose, zmap=zm, xl=xl)
            li = p.last_logits[:, o_[10]:o_[11]]
            am_ = li.argmax(1)
            cnt += np.bincount(am_, minlength=17)[:17]
            dn = ax[:, C["red_s"]] > 10.0
            ra_down += int(dn.sum())
            ra_named += int((dn & (am_ == INT.index("RA"))).sum())
        sh = cnt / cnt.sum()
        out[tag] = dict(frames=int(cnt.sum()), intention={INT[k] if k < len(INT) else "H{}".format(k - 8): round(float(v), 4) for k, v in enumerate(sh) if v > 0.005},
                        ra_named_while_down_10s=round(ra_named / max(1, ra_down), 4), ra_down_frames=ra_down)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ck", required=True)
    ap.add_argument("--ref", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "policy_v042_160.pt"))
    ap.add_argument("--ppl", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "ppl"))
    ap.add_argument("--demo", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "demo"))
    ap.add_argument("--xl", default=os.path.join(ROOT, "data", "sim_runs", "brainppl", "data", "ppl_xl"))
    ap.add_argument("--hands", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    dev = torch.device(a.device)
    S = BF.load_streams(a.ppl, None, False, a.demo, 0)
    sets = {"today_campgrounds": [s for s in S if s["today"] and s["map"] == "campgrounds"],
            "today_hektik": [s for s in S if s["today"] and s["map"] == "hektik"],
            "today_all": [s for s in S if s["today"]],
            "demo_held": [s for s in S if s["src"] == "demo" and s["held"]]}
    rep = {}
    for tag, ck_p in (("ref", a.ref), ("new", a.ck)):
        ck = torch.load(ck_p, weights_only=False, map_location="cpu")
        nt = int(ck["ahead"]["n_target"])
        brain = BF.Brain(ck).to(dev)
        nf = BF.norm_fn(ck, dev)
        for k, v in sets.items():
            if not v:
                continue
            P = BF.pack(v, max(1, min(8, len(v))))
            Y = BF.labels(P, nt)
            rep.setdefault(k, {})[tag] = scores(brain, P, Y, nf, dev, nt, ck["ahead"])
    if a.hands:
        rep["hands"] = hands(a.ref, a.ck, BF.load_streams(a.xl, None))
    print(json.dumps(rep, indent=1))
    if a.out:
        json.dump(rep, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()

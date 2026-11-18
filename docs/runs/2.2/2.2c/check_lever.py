"""2.2c: THE CHECKS PLAY THE LEVER AS THE TRAINER DOES, on one save (the brief: "a check must play the lever exactly as training does; prove it on
one save"). A save whose lever has learnt (not zero) plays every seat of a few matches through the checks' player (sim/test_suite.py Policy, as
tools/duel_eval.py and tools/run/ws_eval.py use it), every frame recorded; then:
  (a) at every keep reading, the Policy's lever on its own inputs against the trainer's torch network (sim/fightnet.py make_module, the save's
      weights) on the same inputs: the largest difference
  (b) the recording replayed twice from the same seeds, at the save's share and at share 0: the target logits as drawn (after the pull and the
      lever: Policy.last_target_logits) differ ONLY in "the enemy" (8),
      by exactly the lever's add as played (LEV_G x the lever, rounded to half precision: fightnet.lever_add, the trainer's own function)
  (c) the hands' inputs of the lever (fight_scores' first column) = that add
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2c/check_lever.py <save.pt> [--map bloodrun] [--frames 600]"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import play22c as PL  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("save")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--seed", type=int, default=61)
    a = ap.parse_args()
    PL.setup()
    import torch
    import fightnet as FN
    import test_suite as T
    now = PL.full_names()
    pol = T.Policy(a.save, seed=a.seed)
    assert pol.lever, "not a network with the lever"
    ck = torch.load(a.save, map_location="cpu", weights_only=False)
    net = FN.make_module(ck["fight22"]["layout"])
    net.load_state_dict({k_: torch.as_tensor(np.asarray(v_.detach().cpu().numpy() if hasattr(v_, "detach") else v_)) for k_, v_ in ck["fight22"]["model"].items()})
    idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
    E, env = PL.make_env(a.map, a.matches, a.seed, pol)
    obs = env.observe()
    h = pol.zeros(env.n)
    rec, dl, nread, lev_abs = [], 0.0, 0, 0.0
    fs_bad = 0.0
    for t in range(a.frames):
        pol.fg_last = None
        act, h = PL.frame(E, env, pol, obs, h, idx, a.map, rec)
        if pol.fg_last is not None:
            r_, o_ = pol.fg_last
            lt_, _ = net(torch.from_numpy(np.asarray(o_["x"], np.float32)))
            dl = max(dl, float(np.abs(lt_.detach().numpy() - o_["lev"]).max()))
            nread += len(r_)
            lev_abs = max(lev_abs, float(np.abs(o_["lev"]).max()))
            fs_ = pol.fight_scores()
            fs_bad = max(fs_bad, float(np.abs(fs_[:, 0] - np.clip(FN.lever_add(pol.fg_lev, pol.lev_g), -5, 5)).max()) + float(np.abs(fs_[:, 1:]).max()))
        obs, r_, done, info = env.step(act)
        rec[-1]["done"] = np.asarray(done, bool).copy()
        d = np.asarray(done, bool)
        if d.any():
            pol.clear(h, d)
    print("(a) {} keep readings: the Policy's lever against the trainer's torch network on the same inputs: largest difference {:.3g} (the lever's "
          "largest |value| {:.3g}, the save's share {})".format(nread, dl, lev_abs, pol.lev_g))
    print("(c) the hands' inputs of the lever (fight_scores) against the add: largest difference {:.3g}".format(fs_bad))
    outs = []
    for g_ in (pol.lev_g, 0.0):
        p_ = T.Policy(a.save, seed=a.seed + 1)
        p_.set_fight(g=g_)
        hh = p_.zeros(len(rec[0]["obs"]))
        L_, A_ = [], []
        for f_ in rec:
            kw = {"fx": f_["fx"]} if (getattr(p_, "fight_due", False) and f_["fx"] is not None) else {}
            ac, hh = p_.act(f_["obs"][:, idx], hh, xl=f_["xl"], pose=f_["pz"], zmap=f_["zz"], kf=f_["kf"], **kw)
            L_.append(np.asarray(p_.last_target_logits, np.float32).copy())
            A_.append(FN.lever_add(p_.fg_lev, pol.lev_g) if p_.fg_lev is not None else None)
            if f_["done"].any():
                p_.clear(hh, f_["done"])
        outs.append((L_, A_))
    worst_other, worst_en, n_ = 0.0, 0.0, 0
    for la_, lb_, ad_ in zip(outs[0][0], outs[1][0], outs[0][1]):
        d_ = la_ - lb_
        worst_other = max(worst_other, float(np.abs(np.delete(d_, FN.EN_INTENT, 1)).max()))
        if ad_ is not None:
            worst_en = max(worst_en, float(np.abs(d_[:, FN.EN_INTENT] - ad_).max()))
            n_ += 1
    print("(b) {} frames replayed at the share {} and at 0: the target logits differ in the other targets by {:.3g}, in 'the enemy' from the add by "
          "{:.3g}".format(n_, pol.lev_g, worst_other, worst_en))
    ok_ = dl < 1e-4 and worst_other == 0.0 and worst_en < 1e-5 and fs_bad < 1e-6 and lev_abs > 0
    print("ALL PASSED" if ok_ else "FAILED")
    sys.exit(0 if ok_ else 1)


if __name__ == "__main__":
    main()

"""2.1d (the pull; docs/runs/2.1/2.1d): the slow plan moved INSIDE the strategy head, so every reader of a network file (the trainer, the checks'
player, the plugin) plays it, with nothing of it in effect until its strength is opened.

    python tools/plan_init.py add <a 2.1c save> <out.pt> [--pull-h 0]
        the run's start. The save's top-level "plan" (sim/slowplan.py, 2.1c's shadow plan: layout, weights, Adam) becomes the head's layers
        head2.plan.* (the same module, the same weights), the layout's entry "slowplan" (horizons, every, hid, floor: sim/head2.py add_slowplan;
        the layout's own "plan" is the hands' plan width), the buffers head2.pull_g 0 (no pull) and head2.pull_h (which horizon pulls); its Adam
        becomes the top-level "plan_opt"; the entry "plan" goes. The MAIN optimizer needs nothing: the plan's layers are in none of its groups
        (sim/train_duel_rnn.py h2_group leaves "plan." out), so the save's opt.pt loads as it is.
    python tools/plan_init.py widen-league <in.pt> <out.pt> [--like <a file with the plan inside>]
        a league file, an anchor, the control: the head given a plan with its last layer at zero (even odds) and no pull (strength 0); its
        widths from --like's layout (default 2.1c's: horizons 10, 25; hid 128; every 5; floor 0.01). A file without a head, or with the plan
        already: written as it is
    python tools/plan_init.py same <a.pt> <b.pt> --sample <obs.npy, the simulator's full rows>
        both through test_suite.Policy on real rows with keep rows fed (random targets, ages, trip ends; the same to both): 0 actions may differ
        (b's pull 0). Then b at pull 1 on the same rows, for information: how many actions the pull moves
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
KEYS = ("l1.weight", "l1.bias", "l2.weight", "l2.bias", "l3.weight", "l3.bias")


def check_head(ck):
    """the head's whole state (the plan in it) loads strictly into the module of its layout"""
    import head2 as H2
    L = ck["head2"]
    m = H2.make_module(L)
    sd = {k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")}
    m.load_state_dict(sd, strict=True)
    return m


def add(a):
    import torch
    import head2 as H2
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L = ck.get("head2")
    assert L is not None and "head2.inp.weight" in ck["model"], "the network has no strategy head"
    assert not H2.has_slowplan(L), "the head has the slow plan inside already"
    PL = ck.get("plan")
    assert PL is not None and PL.get("model") and PL.get("layout"), "no top-level 'plan' in {} (a 2.1c save with --plan 1)".format(a.inp)
    PLL = PL["layout"]
    assert int(PLL["head"]) == int(L["size"]) and int(PLL["n_target"]) == int(L["n_target"]), "the plan's widths do not fit the head"
    assert 0 <= a.pull_h < len(PLL["horizons"]), "--pull-h: the plan has horizons {}".format(PLL["horizons"])
    L2 = H2.add_slowplan(L, horizons=PLL["horizons"], every=PLL["every"], hid=PLL["hid"], floor=H2.PULL_FLOOR)
    sd = ck["model"]
    for k_ in KEYS:
        sd["head2.plan." + k_] = PL["model"][k_].detach().cpu().float().clone()
    sd["head2.pull_g"] = torch.zeros(())
    sd["head2.pull_h"] = torch.tensor(float(a.pull_h))
    ck["head2"] = L2
    ck["plan_opt"] = PL.get("opt")
    del ck["plan"]
    m = check_head(ck)
    for k_ in KEYS:                                          # (the same weights, to the bit)
        assert torch.equal(m.plan.state_dict()[k_], PL["model"][k_].detach().cpu().float()), k_
    torch.save(ck, a.out)
    print("wrote {}: the slow plan inside the head (head2.plan.*: {} -> {} -> {} -> {} horizons {} x {} targets; every {}, floor {}); pull 0 on "
          "horizon {} ({} ticks); its Adam as top-level plan_opt ({}); |plan.l3.weight| {:.4f}".format(
              a.out, L["size"], PLL["hid"], PLL["hid"], len(PLL["horizons"]), PLL["horizons"], L["n_target"], PLL["every"], H2.PULL_FLOOR,
              a.pull_h, PLL["horizons"][a.pull_h], "kept" if PL.get("opt") is not None else "none", float(sd["head2.plan.l3.weight"].norm())))


def widen_league(a):
    import torch
    import head2 as H2
    import slowplan as SP
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    if ck.get("head2") is None or "head2.inp.weight" not in ck["model"]:     # (an anchor from before the head: nothing to give)
        torch.save(ck, a.out)
        print("wrote {}: no strategy head in this file, written as it is".format(a.out))
        return
    if H2.has_slowplan(ck["head2"]):
        torch.save(ck, a.out)
        print("wrote {}: the head has the slow plan inside already, written as it is (pull {:.4f})".format(a.out, float(ck["model"].get("head2.pull_g", 0.0))))
        return
    like = dict(horizons=[10, 25], every=5, hid=128, floor=H2.PULL_FLOOR)
    if a.like:
        lk_ = torch.load(a.like, weights_only=False, map_location="cpu")
        assert H2.has_slowplan(lk_.get("head2")), "--like: the file has no slow plan inside its head"
        like = dict(lk_["head2"]["slowplan"])
    L2 = H2.add_slowplan(ck["head2"], horizons=like["horizons"], every=like["every"], hid=like["hid"], floor=like["floor"])
    M = SP.make_module(H2.slowplan_layout(L2))               # (its own random stream; its last layer at zero: even odds)
    sd = ck["model"]
    for k_, v_ in M.state_dict().items():
        sd["head2.plan." + k_] = v_.detach().clone()
    sd["head2.pull_g"] = torch.zeros(())
    sd["head2.pull_h"] = torch.zeros(())
    ck["head2"] = L2
    check_head(ck)
    assert float(sd["head2.plan.l3.weight"].abs().sum() + sd["head2.plan.l3.bias"].abs().sum()) == 0.0
    torch.save(ck, a.out)
    print("wrote {}: the head given the slow plan (horizons {}, hid {}) with its last layer at zero (even odds); no pull (strength 0)".format(
        a.out, like["horizons"], like["hid"]))


def same(a):
    import input_list as IL
    import test_suite as T
    import head2 as H2
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == len(pb.mean), "the two read different lists"
    assert pb.planW is not None and pb.pull_g == 0.0 and pa.planW is None, "b: the plan inside its head at pull 0; a: without it"
    assert pa.goal_on and pb.goal_on and pa.held_g == pb.held_g, "both read the goal he holds, at the same held share"
    names = getattr(pa, "names", None)
    assert names, "a network of a cleaned list (its names in the file)"
    lst = [L for L in (IL.load("20e"), IL.load(18), IL.load("20d")) if [tuple(x) for x in L["names"]] == [tuple(x) for x in names]]
    assert lst, "the network's list is not 20e, 18 or 20d"
    src = np.asarray(lst[0]["src"], np.int64)
    X = np.load(a.sample, mmap_mode="r")
    B, F = a.seats, a.rows // a.seats

    def run(pb_g):
        pa_, pb_ = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
        if pb_g > 0:
            pb_.set_pull_g(pb_g)
        for p in (pa_, pb_):
            if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
                p.h2_live = True
        rng = np.random.default_rng(3)
        pick = rng.permutation(len(X))[:B * F].reshape(F, B)
        ha, hb = pa_.zeros(B), pb_.zeros(B)
        pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
        kf = np.zeros((B, H2.KEEP_FEAT + 1), np.float32)
        dact, n, ticks, held = 0, 0, 0, 0
        for t in range(F):
            raw = np.asarray(X[np.sort(pick[t])], np.float32)
            if raw.shape[1] != len(pa_.mean):                # (the simulator's full rows -> the network's list)
                full_ = np.zeros((len(raw), int(src.max()) + 1), np.float32)
                full_[:, :raw.shape[1]] = raw[:, :full_.shape[1]]
                if raw.shape[1] < full_.shape[1]:
                    full_[:, raw.shape[1]:] = rng.uniform(-1, 1, (len(raw), full_.shape[1] - raw.shape[1])).astype(np.float32)
                raw = full_[:, src]
            pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
            pose[:, 3] = rng.uniform(-180, 180, B)
            kw = {}
            if pa_.needs_xl:
                kw["xl"] = rng.normal(0, 1, (B, pa_.legsP[0].shape[1])).astype(np.float32)
            kf[:, 0] = rng.uniform(0, 25, B)                 # (both read them: random ages, targets, trip ends)
            kf[:, 2] = rng.integers(0, 17, B)
            kf[:, -1] = rng.random(B) < 0.1
            oa, ha = pa_.act(raw, ha, pose=pose, zmap=zmap, kf=kf.copy(), **kw)
            ob, hb = pb_.act(raw, hb, pose=pose, zmap=zmap, kf=kf.copy(), **kw)
            ticks += int(pb_.k_r.sum()) if pb_.k_r is not None else 0
            held += int((ob[:, -1] & 2).sum())
            dact += int((oa != ob).sum())
            n += oa.size
            if t % 97 == 96:
                r = rng.random(B) < 0.3
                pa_.clear(ha, r)
                pb_.clear(hb, r)
        return dact, n, ticks, held
    d0, n0, t0, h0 = run(0.0)
    print("same: {} real rows x {} seats ({} head ticks, {} seat-frames on the held draw): actions that differ at pull 0: {} of {}".format(
        F, B, t0, h0, d0, n0))
    d1, n1, _, _ = run(1.0)
    print("for information: b at pull 1.0 on the same rows: actions that differ {} of {} (the plan's odds {}uniform)".format(
        d1, n1, "not " if d1 > 0 else "maybe "))
    ok = d0 == 0 and t0 > 0
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--pull-h", type=int, default=0)
    p = sp.add_parser("widen-league")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--like", default="")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--sample", required=True)
    p.add_argument("--rows", type=int, default=3200)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    sys.exit(int({"add": add, "widen-league": widen_league, "same": same}[a.cmd](a) or 0))


if __name__ == "__main__":
    main()

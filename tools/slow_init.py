"""2.1e (the head's slow halves; docs/runs/2.1/2.1e): a 2.1d network given the three slow halves inside its strategy head, with nothing of them
in effect, so that it answers as before.

    python tools/slow_init.py add <a 2.1d save> <out.pt> [--clocks 5,10,20] [--hid 128]
        the run's start. The head's layout gets the entry "slowhalf" (sim/head2.py add_slowhalf: the clocks in head ticks, the width, the slow
        plan's horizons) and the input part "slowback" (the read-back: hid columns of zero weights at the end of what the head's first layer
        reads; the file's "head2_inp_map" says where each old column is: the trainer's --opt-small-items carries the optimizer's moments); the
        layers head2.slow.<k>.* (sim/slowhalf.py: each from its own random stream, its plan's last layer at zero: even odds); the buffers
        head2.slow_mix 0 (the pull's source: the fast plan alone), head2.slow_back 0 (the read-back shut), head2.slow_pick 1 (the 2-second half).
        Everything else is kept: the slow plan (head2.plan.*) and its Adam (plan_opt), the pull's strength. The slow halves' Adam (the
        checkpoint's top-level "slow_opt") is made by the trainer at its first start. The MAIN optimizer: the halves are in none of its groups
        (sim/train_duel_rnn.py h2_group leaves "slow." out); its moments of head2.inp.weight are carried by --opt-small-items 1 and the map.
    python tools/slow_init.py widen-league <in.pt> <out.pt> [--like <a file with the slow halves>]
        a league file, an anchor, the control: the head given the slow halves with their last layers at zero (even odds), never pulling (mix 0)
        and the read-back's columns at zero (back 0); the clocks and width from --like's layout (default 5, 10, 20 and 128). A file without a
        head, or with the halves already: written as it is. A head without the part "goal" or the slow plan: refused (tools/plan_init.py
        widen-league first)
    python tools/slow_init.py same <a.pt> <b.pt> --sample <obs.npy, the simulator's full rows>
        both through test_suite.Policy on real rows with keep rows fed (random targets, ages, trip ends; the same to both): 0 actions may differ
        (b's mix 0, back 0), at the file's pull and again at pull 1.0 on both. Then, for information, b at mix 1.0 and back 1.0: how many
        actions that moves (even odds and zero read-back weights at the start)
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def check_head(ck):
    """the head's whole state (the halves in it) loads strictly into the module of its layout"""
    import head2 as H2
    m = H2.make_module(ck["head2"])
    sd = {k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")}
    m.load_state_dict(sd, strict=True)
    return m


def widen(ck, clocks, hid, pick=1.0):
    """the halves and the read-back's columns into a checkpoint (in place) -> (old inp width, new)"""
    import torch
    import head2 as H2
    import slowhalf as SH
    L = ck["head2"]
    sd = ck["model"]
    L2 = H2.add_slowhalf(L, clocks=clocks, hid=hid)
    W = sd["head2.inp.weight"]
    old = int(W.shape[1])
    assert old == H2.u0_width(L), (old, H2.u0_width(L))
    k = int(L2["widths"]["slowback"])
    assert H2._offs(L2)["slowback"] == (old, old + k), "the part 'slowback' is not at the end of what the head's first layer reads"
    sd["head2.inp.weight"] = torch.cat([W, torch.zeros(W.shape[0], k, dtype=W.dtype)], 1)
    M = SH.make_halves(H2.slowhalf_layout(L2))
    for k_, v_ in M.state_dict().items():
        sd["head2.slow." + k_] = v_.detach().clone()
    sd["head2.slow_mix"] = torch.zeros(())
    sd["head2.slow_back"] = torch.zeros(())
    sd["head2.slow_pick"] = torch.tensor(float(pick))
    ck["head2"] = L2
    m = check_head(ck)
    for k_ in range(len(L2["slowhalf"]["clocks"])):
        assert float(m.slow[k_].l3.weight.abs().sum() + m.slow[k_].l3.bias.abs().sum()) == 0.0, "half {}: its last layer not at zero".format(k_)
    assert float(m.inp.weight[:, old:].abs().sum()) == 0.0 and torch.equal(m.inp.weight[:, :old], W.float()), "the read-back's columns"
    return old, old + k


def add(a):
    import torch
    import head2 as H2
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L = ck.get("head2")
    assert L is not None and "head2.inp.weight" in ck["model"], "the network has no strategy head"
    assert not H2.has_slowhalf(L), "the head has the slow halves already"
    assert H2.has_goal(L) and H2.has_slowplan(L), "a 2.1d network: the part 'goal' and the slow plan inside the head (tools/plan_init.py add)"
    clocks = [int(x_) for x_ in a.clocks.split(",") if x_.strip()]
    old, new = widen(ck, clocks, a.hid)
    ck["head2_inp_map"] = list(range(old))                   # (each old column where it was; the read-back's after them)
    torch.save(ck, a.out)
    L2 = ck["head2"]
    print("wrote {}: the slow halves inside the head (head2.slow.0..{}: head state {} + goal {} -> {} -> GRU {} -> {} -> horizons {} x {}; clocks {} "
          "head ticks); the read-back's {} columns at zero (the head's input {} -> {}); mix 0, back 0, pick 1; the slow plan, its Adam (plan_opt "
          "{}) and the pull ({:.4f}) kept".format(a.out, len(clocks) - 1, L2["size"], L2["widths"]["goal"], a.hid, a.hid, a.hid,
                                                  L2["slowhalf"]["horizons"], L2["n_target"], clocks, new - old, old, new,
                                                  "kept" if ck.get("plan_opt") is not None else "none", float(ck["model"].get("head2.pull_g", 0.0))))
    print(H2.describe(L2))


def widen_league(a):
    import torch
    import head2 as H2
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    if ck.get("head2") is None or "head2.inp.weight" not in ck["model"]:     # (an anchor from before the head: nothing to give)
        torch.save(ck, a.out)
        print("wrote {}: no strategy head in this file, written as it is".format(a.out))
        return
    if H2.has_slowhalf(ck["head2"]):
        torch.save(ck, a.out)
        print("wrote {}: the head has the slow halves already, written as it is (mix {:.4f}, back {:.4f})".format(
            a.out, float(ck["model"].get("head2.slow_mix", 0.0)), float(ck["model"].get("head2.slow_back", 0.0))))
        return
    if not (H2.has_goal(ck["head2"]) and H2.has_slowplan(ck["head2"])):
        raise SystemExit("{}: its head has not the part 'goal' and the slow plan (tools/plan_init.py widen-league first): not written".format(a.inp))
    clocks, hid = [5, 10, 20], 128
    if a.like:
        lk_ = torch.load(a.like, weights_only=False, map_location="cpu")
        assert H2.has_slowhalf(lk_.get("head2")), "--like: the file has no slow halves inside its head"
        clocks, hid = list(lk_["head2"]["slowhalf"]["clocks"]), int(lk_["head2"]["slowhalf"]["hid"])
    old, new = widen(ck, clocks, hid)
    torch.save(ck, a.out)
    print("wrote {}: the head given the slow halves (clocks {}, hid {}) with their last layers at zero (even odds), never pulling (mix 0), the "
          "read-back's {} columns at zero (back 0)".format(a.out, clocks, hid, new - old))


def same(a):
    import input_list as IL
    import test_suite as T
    import head2 as H2
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == len(pb.mean), "the two read different lists"
    assert pb.shL is not None and pb.sh_mix == 0.0 and pb.sh_back == 0.0 and pa.shL is None, "b: the slow halves at mix 0, back 0; a: without them"
    assert pa.goal_on and pb.goal_on and pa.held_g == pb.held_g and pa.pull_g == pb.pull_g, "both read the goal, at the same held share and pull"
    names = getattr(pa, "names", None)
    assert names, "a network of a cleaned list (its names in the file)"
    lst = [L for L in (IL.load("20e"), IL.load(18), IL.load("20d")) if [tuple(x) for x in L["names"]] == [tuple(x) for x in names]]
    assert lst, "the network's list is not 20e, 18 or 20d"
    src = np.asarray(lst[0]["src"], np.int64)
    X = np.load(a.sample, mmap_mode="r")
    B, F = a.seats, a.rows // a.seats

    def run(pull_g, mix, back):
        pa_, pb_ = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
        if pull_g is not None:
            pa_.set_pull_g(pull_g)
            pb_.set_pull_g(pull_g)
        pb_.set_slow_mix(mix)
        pb_.set_slow_back(back)
        for p in (pa_, pb_):
            if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
                p.h2_live = True
        rng = np.random.default_rng(3)
        pick = rng.permutation(len(X))[:B * F].reshape(F, B)
        ha, hb = pa_.zeros(B), pb_.zeros(B)
        pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
        kf = np.zeros((B, H2.KEEP_FEAT + 1), np.float32)
        dact, n, ticks, sticks = 0, 0, 0, np.zeros(3, np.int64)
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
            ch_ = rng.random(B) < 0.15
            kf[:, 2] = np.where(ch_, rng.integers(0, 17, B), kf[:, 2])
            kf[:, -1] = rng.random(B) < 0.05
            oa, ha = pa_.act(raw, ha, pose=pose, zmap=zmap, kf=kf.copy(), **kw)
            ob, hb = pb_.act(raw, hb, pose=pose, zmap=zmap, kf=kf.copy(), **kw)
            ticks += int(pb_.k_r.sum()) if pb_.k_r is not None else 0
            if pb_.sh is not None and pb_.sh.last is not None:
                tk_, cl_, fr_, cg_ = pb_.sh.last
                sticks += np.array([int(cl_.sum()), int(fr_.sum()), int(cg_.sum())])
            dact += int((oa != ob).sum())
            n += oa.size
            if t % 97 == 96:
                r = rng.random(B) < 0.3
                pa_.clear(ha, r)
                pb_.clear(hb, r)
        return dact, n, ticks, sticks
    ok = True
    for pg_ in ([None] + ([1.0] if pa.planW is not None else [])):
        d0, n0, t0, s0 = run(pg_, 0.0, 0.0)
        print("same: {} real rows x {} seats ({} head ticks) at pull {}: actions that differ at mix 0, back 0: {} of {}".format(
            F, B, t0, "the file's ({})".format(pa.pull_g) if pg_ is None else pg_, d0, n0))
        ok = ok and d0 == 0 and t0 > 0
    d1, n1, _, s1 = run(1.0 if pa.planW is not None else None, 1.0, 1.0)
    print("for information: b at pull 1.0, mix 1.0, back 1.0 on the same rows (its halves at even odds, the read-back's weights zero): actions "
          "that differ {} of {}; the picked half's ticks by cause (clock, trip end, change) {}".format(d1, n1, s1.tolist()))
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--clocks", default="5,10,20")
    p.add_argument("--hid", type=int, default=128)
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

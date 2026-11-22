"""2.1f (the outlook; docs/runs/2.1/2.1f): a 2.1d network given the outlook inside its strategy head, with nothing of it in effect, so that it
answers as before.

    python tools/out_init.py add <a 2.1d save> <out.pt> [--kinds seg,ret,all8,win8,win5] [--hid 128]
        the run's start. The head's layout gets the entry "outlook" (sim/head2.py add_outlook: the kinds, the width, the clip); the layers
        head2.out.* (sim/outlook.py: from its own random stream, its last layer at zero: every outlook 0); the buffers head2.out_g 0 (no term) and
        head2.out_pick 0 (the first kind: "seg"). Everything else is kept: the slow plan and its Adam (plan_opt), the pull, the head's input (the
        outlook reads the head's state, no new input). The outlook's Adam (the checkpoint's top-level "out_opt") and its labels' statistics
        ("out_stats") are made by the trainer at its first start. The MAIN optimizer: the outlook is in none of its groups (sim/train_duel_rnn.py
        h2_group leaves "out." out), so 2.1d's opt file loads as it is.
    python tools/out_init.py widen-league <in.pt> <out.pt> [--like <a file with the outlook>]
        a league file, an anchor, the control: the head given the outlook with its last layer at zero and no term (out_g 0); the kinds and width
        from --like's layout (default as add's). A file without a head, or with the outlook already: written as it is. A head without the slow
        plan: refused (tools/plan_init.py widen-league first)
    python tools/out_init.py same <a.pt> <b.pt> --sample <obs.npy, the simulator's full rows>
        both through test_suite.Policy on real rows with keep rows fed (random targets, ages, trip ends; the same to both): 0 actions may differ
        (b at out_g 0), at the file's pull and again at pull 1.0 on both. Then b at out_g 1.0 (its last layer at zero): 0 may differ either
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
KINDS = "seg,ret,all8,win8,win5"


def check_head(ck):
    """the head's whole state (the outlook in it) loads strictly into the module of its layout"""
    import head2 as H2
    m = H2.make_module(ck["head2"])
    sd = {k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")}
    m.load_state_dict(sd, strict=True)
    return m


def widen(ck, kinds, hid):
    """the outlook into a checkpoint (in place)"""
    import torch
    import head2 as H2
    import outlook as OL
    L2 = H2.add_outlook(ck["head2"], kinds=kinds, hid=hid)
    M = OL.make_module(H2.outlook_layout(L2))
    sd = ck["model"]
    for k_, v_ in M.state_dict().items():
        sd["head2.out." + k_] = v_.detach().clone()
    sd["head2.out_g"] = torch.zeros(())
    sd["head2.out_pick"] = torch.zeros(())
    ck["head2"] = L2
    m = check_head(ck)
    assert float(m.out.l3.weight.abs().sum() + m.out.l3.bias.abs().sum()) == 0.0, "the outlook's last layer not at zero"


def add(a):
    import torch
    import head2 as H2
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L = ck.get("head2")
    assert L is not None and "head2.inp.weight" in ck["model"], "the network has no strategy head"
    assert not H2.has_outlook(L), "the head has the outlook already"
    assert H2.has_goal(L) and H2.has_slowplan(L), "a 2.1d network: the part 'goal' and the slow plan inside the head (tools/plan_init.py add)"
    kinds = [k_.strip() for k_ in a.kinds.split(",") if k_.strip()]
    widen(ck, kinds, a.hid)
    torch.save(ck, a.out)
    L2 = ck["head2"]
    print("wrote {}: the outlook inside the head (head2.out: head state {} -> {} -> {} -> kinds {} x ({} targets + goal-blind), its last layer at "
          "zero); out_g 0, out_pick 0 ({}); the slow plan, its Adam (plan_opt {}), the pull ({:.4f}), the slow halves ({}) kept".format(
              a.out, L2["size"], a.hid, a.hid, kinds, L2["n_target"], kinds[0], "kept" if ck.get("plan_opt") is not None else "none",
              float(ck["model"].get("head2.pull_g", 0.0)), "yes" if H2.has_slowhalf(L2) else "none"))
    print(H2.describe(L2))


def widen_league(a):
    import torch
    import head2 as H2
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    if ck.get("head2") is None or "head2.inp.weight" not in ck["model"]:     # (an anchor from before the head: nothing to give)
        torch.save(ck, a.out)
        print("wrote {}: no strategy head in this file, written as it is".format(a.out))
        return
    if H2.has_outlook(ck["head2"]):
        torch.save(ck, a.out)
        print("wrote {}: the head has the outlook already, written as it is (out_g {:.4f})".format(a.out, float(ck["model"].get("head2.out_g", 0.0))))
        return
    if not H2.has_slowplan(ck["head2"]):
        raise SystemExit("{}: its head has not the slow plan (tools/plan_init.py widen-league first): not written".format(a.inp))
    kinds, hid = KINDS.split(","), 128
    if a.like:
        lk_ = torch.load(a.like, weights_only=False, map_location="cpu")
        assert H2.has_outlook(lk_.get("head2")), "--like: the file has no outlook inside its head"
        kinds, hid = list(lk_["head2"]["outlook"]["kinds"]), int(lk_["head2"]["outlook"]["hid"])
    widen(ck, kinds, hid)
    torch.save(ck, a.out)
    print("wrote {}: the head given the outlook (kinds {}, hid {}) with its last layer at zero, no term (out_g 0)".format(a.out, kinds, hid))


def same(a):
    import input_list as IL
    import test_suite as T
    import head2 as H2
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == len(pb.mean), "the two read different lists"
    assert pb.outW is not None and pb.out_g == 0.0 and pa.outW is None, "b: the outlook at out_g 0; a: without it"
    assert pa.goal_on and pb.goal_on and pa.held_g == pb.held_g and pa.pull_g == pb.pull_g, "both read the goal, at the same held share and pull"
    names = getattr(pa, "names", None)
    assert names, "a network of a cleaned list (its names in the file)"
    lst = [L for L in (IL.load("20e"), IL.load(18), IL.load("20d")) if [tuple(x) for x in L["names"]] == [tuple(x) for x in names]]
    assert lst, "the network's list is not 20e, 18 or 20d"
    src = np.asarray(lst[0]["src"], np.int64)
    X = np.load(a.sample, mmap_mode="r")
    B, F = a.seats, a.rows // a.seats

    def run(pull_g, out_g, held_g=None):
        pa_, pb_ = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
        if pull_g is not None:
            pa_.set_pull_g(pull_g)
            pb_.set_pull_g(pull_g)
        if held_g is not None:
            pa_.held_g = pb_.held_g = held_g
        pb_.set_out_g(out_g)
        for p in (pa_, pb_):
            if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
                p.h2_live = True
        rng = np.random.default_rng(3)
        pick = rng.permutation(len(X))[:B * F].reshape(F, B)
        ha, hb = pa_.zeros(B), pb_.zeros(B)
        pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
        kf = np.zeros((B, H2.KEEP_FEAT + 1), np.float32)
        dact, n, ticks = 0, 0, 0
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
            dact += int((oa != ob).sum())
            n += oa.size
            if t % 97 == 96:
                r = rng.random(B) < 0.3
                pa_.clear(ha, r)
                pb_.clear(hb, r)
        return dact, n, ticks
    ok = True
    for pg_ in ([None] + ([1.0] if pa.planW is not None else [])):
        for og_ in (0.0, 1.0):
            d0, n0, t0 = run(pg_, og_, 0.5)
            print("same: {} real rows x {} seats ({} head ticks), held share 0.5, pull {}: actions that differ at out_g {} (b's last layer at zero): "
                  "{} of {}".format(F, B, t0, "the file's ({})".format(pa.pull_g) if pg_ is None else pg_, og_, d0, n0))
            ok = ok and d0 == 0 and t0 > 0
    print("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--kinds", default=KINDS)
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

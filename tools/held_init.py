"""2.1c: a network given the head's part "goal" (the target he holds, its age, whether the trip is on the held draw: the held draw's
learned comparison) with nothing of it in effect, so that it answers as before.

    python tools/held_init.py add <in.pt> <out.pt>
        the run's start. The strategy head's input gets the part "goal" (sim/head2.py add_goal: n_target + 2 numbers): columns of zero
        weights at the end of what its first layer reads; the file's "head2_inp_map" says where each old column is (the trainer's
        --opt-small-items carries the optimizer's moments). The share head2.held_g 0 (the lock rule on every trip).
    python tools/held_init.py widen-league <in.pt> <out.pt>
        a league file, an anchor, the control: the head's input widened the same way (the trainer plays every head on the learner's
        layout); its share 0: a league seat without the held draw plays the lock rule
    python tools/held_init.py same <a.pt> <b.pt> --sample <obs.npy, the simulator's full rows>
        both through test_suite.Policy on real rows, b given keep rows with random targets, ages and trip ends: 0 actions may differ
        (b's share is 0 and its new columns' weights are zero)
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def widen_head(ck):
    import torch
    import head2 as H2
    L = ck.get("head2")
    sd = ck["model"]
    assert L is not None and "head2.inp.weight" in sd, "the network has no strategy head"
    assert not H2.has_goal(L), "the head has the part 'goal' already"
    L2 = H2.add_goal(L)
    W = sd["head2.inp.weight"]
    old = int(W.shape[1])
    assert old == H2.u0_width(L), (old, H2.u0_width(L))
    k = int(L2["widths"]["goal"])
    assert H2._offs(L2)["goal"] == (old, old + k), "the part 'goal' is not at the end of what the head's first layer reads"
    sd["head2.inp.weight"] = torch.cat([W, torch.zeros(W.shape[0], k, dtype=W.dtype)], 1)
    sd["head2.held_g"] = torch.zeros(())
    ck["head2"] = L2
    ck["head2_inp_map"] = list(range(old))                   # (each old column where it was; the new ones after them)
    return L2, k, old


def add(a):
    import torch
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L2, k, old = widen_head(ck)
    torch.save(ck, a.out)
    print("wrote {}: the head's input {} -> {} columns ({} of the part 'goal', at zero); the held draw's share 0".format(a.out, old, old + k, k))


def same(a):
    import input_list as IL
    import test_suite as T
    import head2 as H2
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == len(pb.mean), "the two read different lists"
    assert pb.goal_on and pb.held_g == 0.0 and not pa.goal_on, "b: the part 'goal' at share 0; a: without it"
    names = getattr(pa, "names", None)
    assert names, "a network of a cleaned list (its names in the file)"
    lst = [L for L in (IL.load("20e"), IL.load(18), IL.load("20d")) if [tuple(x) for x in L["names"]] == [tuple(x) for x in names]]
    assert lst, "the network's list is not 20e, 18 or 20d"
    src = np.asarray(lst[0]["src"], np.int64)
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
            p.h2_live = True
    X = np.load(a.sample, mmap_mode="r")
    rng = np.random.default_rng(3)
    B, F = a.seats, a.rows // a.seats
    pick = rng.permutation(len(X))[:B * F].reshape(F, B)
    ha, hb = pa.zeros(B), pb.zeros(B)
    pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
    kf = np.zeros((B, H2.KEEP_FEAT + 1), np.float32)
    dact, n, ticks = 0, 0, 0
    for t in range(F):
        raw = np.asarray(X[np.sort(pick[t])], np.float32)
        if raw.shape[1] != len(pa.mean):                     # (the simulator's full rows -> the network's list)
            full_ = np.zeros((len(raw), int(src.max()) + 1), np.float32)
            full_[:, :raw.shape[1]] = raw[:, :full_.shape[1]]
            if raw.shape[1] < full_.shape[1]:
                full_[:, raw.shape[1]:] = rng.uniform(-1, 1, (len(raw), full_.shape[1] - raw.shape[1])).astype(np.float32)
            raw = full_[:, src]
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        kf[:, 0] = rng.uniform(0, 25, B)                     # (b reads them: random ages, targets, trip ends)
        kf[:, 2] = rng.integers(0, 17, B)
        kf[:, -1] = rng.random(B) < 0.1
        oa, ha = pa.act(raw, ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw, hb, pose=pose, zmap=zmap, kf=kf, **kw)
        ticks += int(pb.k_r.sum()) if pb.k_r is not None else 0
        dact += int((oa != ob[:, :oa.shape[1]]).sum())
        assert ob.shape[1] == oa.shape[1] + 1 and not (ob[:, -1] & 3).any(), "b's keep column: no draw, no coin at share 0"
        n += oa.size
        if t % 97 == 96:
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same: {} real rows x {} seats ({} head ticks read the goal): actions that differ: {} of {}".format(F, B, ticks, dact, n))
    print("ALL PASSED" if dact == 0 and ticks > 0 else "FAILED")
    return 0 if dact == 0 and ticks > 0 else 1


def widen_league(a):
    import torch
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    if ck.get("head2") is None or "head2.inp.weight" not in ck["model"]:     # (an anchor from before the head: nothing to widen; the lock rule)
        torch.save(ck, a.out)
        print("wrote {}: no strategy head in this file, written as it is".format(a.out))
        return
    L2, k, old = widen_head(ck)
    torch.save(ck, a.out)
    print("wrote {}: the head's input widened by {} columns at zero; the held draw's share 0 (the lock rule)".format(a.out, k))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("add", "widen-league"):
        p = sp.add_parser(nm)
        p.add_argument("inp")
        p.add_argument("out")
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

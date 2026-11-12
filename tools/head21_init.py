"""2.1: a network given the head's choice of an instruction with nothing of it in effect, so that it answers as before. NOT RUN YET.

    python tools/head21_init.py add <in.pt> <out.pt> [--hid 128] [--warm 20000]
        the run's start (a network of list 21: tools/inputs21.py convert first). What is added:
          - the strategy head's input gets the part "ins" (sim/head2.py ins_u_width: the row he is on, its forecast then and now, the
            simulator's change signals, how long, on one): columns of zero weights at the end of what its first layer reads; the
            file's "head2_inp_map" says where each old column is (the trainer's --opt-small-items carries the optimizer's moments);
          - the scorer INSIDE the head (the owner, 2026-11-11): layers head2.ins_* of the network's own weights (the rows' scorer, the
            weapon's scores, the quiet logit; their last layers at zero: every offered row alike; the share head2.ins_g 0). The trainer
            puts them in the optimizer's group "ins" (a saved optimizer without it: Adam starts them fresh);
          - "ins" at the top of the file: what is not a weight (the appraisals' branches seen 0, the warm-up, the row "none", the
            columns the brain's answers are written into);
          - "appraise" at the top of the file, where the file has none: the appraisals reading a row's numbers (xf), last layer at zero.
            A file whose appraisals were made without the rows (xf 0) is refused: they cannot read a candidate.
    python tools/head21_init.py widen-league <in.pt> <out.pt>
        a league file, an anchor, the control: the head's input widened the same way and the scorer's layers of the same shapes
        (the trainer plays every head on the learner's layout); its share 0: a league seat is under no instruction
    python tools/head21_init.py same <a.pt> <b.pt> --sample <obs.npy, the simulator's full rows>
        both through their own lists on real rows: 0 actions may differ (the share is 0: no instruction is given)

The simulator's shape (the rows a tick, the numbers a row, the weapons, the row "none") is read from sim/duel_env_ffa.py with INSTR=1.
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def sim_shape():
    os.environ["INSTR"] = "1"
    import duel_env_ffa as E
    assert getattr(E, "INSTR", False) and all(hasattr(E, k) for k in ("INS_C", "INS_F", "NW")), "the simulator has no instruction candidates (instr_feat)"
    return dict(c=int(E.INS_C), xf=int(E.INS_F), nw=int(E.NW), none_row=int(getattr(E, "INS_NONE_ROW", -1)),
                fill={str(k): int(v) for k, v in dict(getattr(E, "INS_FILL", {}) or {}).items()},
                verbs=[str(v) for v in getattr(E, "INS_VERBS", ())], feat=[str(x) for x in getattr(E, "INS_FEAT", ())])


def widen_head(ck, shape, hid, quiet=0, ms=0, bq=1):
    """the head's layout with the part "ins" and its first layer widened by that many zero columns -> (the new layout, columns added)"""
    import torch
    import head2 as H2
    L = ck.get("head2")
    sd = ck["model"]
    assert L is not None and "head2.inp.weight" in sd, "the network has no strategy head"
    assert not H2.has_ins(L), "the head has the part 'ins' already"
    L2 = H2.add_ins(L, shape["xf"], shape["nw"], shape["c"], hid, quiet=quiet, ms=ms, bq=bq)    # (ms: the map sense at a row's place after its
    #                                                          own numbers; bq: the brain's three numbers among the head's inputs)
    W = sd["head2.inp.weight"]
    old = int(W.shape[1])
    assert old == H2.u0_width(L), (old, H2.u0_width(L))
    k = int(L2["widths"]["ins"])
    assert H2._offs(L2)["ins"] == (old, old + k), "the part 'ins' is not at the end of what the head's first layer reads"
    sd["head2.inp.weight"] = torch.cat([W, torch.zeros(W.shape[0], k, dtype=W.dtype)], 1)
    ck["head2"] = L2
    ck["head2_inp_map"] = list(range(old))                   # (each old column where it was; the new ones after them)
    m = H2.make_module(L2)                                   # (inside the head) the scorer's layers as a new head of this layout makes them:
    n_ins = 0                                                # the hidden layers drawn from the head's own stream, the last layers at zero,
    for k_, v_ in m.state_dict().items():                    # the quiet logit's bias at INS_Q0, the share 0
        if k_.startswith("ins_"):
            assert "head2." + k_ not in sd, "the network has the scorer's layers already"
            sd["head2." + k_] = v_.detach().clone()
            n_ins += int(v_.numel()) if k_ != "ins_g" else 0
    assert not sd["head2.ins_iv.weight"].any() and not sd["head2.ins_wv.weight"].any() and float(sd["head2.ins_g"]) == 0.0
    ck["head2_ins_weights"] = n_ins
    return L2, k


def add(a):
    import torch
    import appraise as AP
    import head2 as H2
    shape = sim_shape()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    assert ck.get("ins") is None, "the file has the instruction's scorer already"
    L2, k = widen_head(ck, shape, a.hid, a.quiet, a.ms, a.bq)
    xf_ = int(L2["ins"]["xf"])                               # (a row as the scorer and the appraisals read it: the simulator's numbers and, with --ms, the map sense's)
    ck["ins"] = dict(seen=0, warm=int(a.warm), none_row=shape["none_row"], verbs=shape["verbs"], feat=shape["feat"], fill=shape["fill"])    # (no weights: head2.ins_* in "model")
    made = ""
    if ck.get("appraise") is None:
        AL = AP.layout(bel=int(L2["widths"]["brain"]), mem=int(L2["widths"]["hands"]), head=int(L2["size"]), targets=int(L2["n_target"]),
                       gamma=float(L2["gamma"]), xf=xf_, quiet=a.quiet)
        am = AP.make_module(AL)
        ck["appraise"] = dict(layout=AL, model={k_: v_.detach().cpu() for k_, v_ in am.state_dict().items()})
        made = "; the appraisals made new ({} -> 6, last layer at zero)".format(AL["inp"])
    else:
        assert int(ck["appraise"]["layout"].get("xf", 0) or 0) == xf_, \
            "the file's appraisals read {} numbers a row, a row has {}: they cannot read a candidate".format(
                ck["appraise"]["layout"].get("xf", 0), xf_)
        assert not a.quiet or ck["appraise"]["layout"].get("quiet"), "the file's appraisals do not read the quiet bit"
    torch.save(ck, a.out)
    print("wrote {}: the head's input {} -> {} columns ({} of the part 'ins', at zero); the scorer over {} rows of {} numbers and {} "
          "weapons INSIDE the head ({:,} weights head2.ins_*, its last layers at zero, share 0, the row 'none' {}){}".format(
              a.out, H2.u0_width(L2) - k, H2.u0_width(L2), k, shape["c"], shape["xf"], shape["nw"],
              int(ck.pop("head2_ins_weights")), shape["none_row"], made))


def widen_league(a):
    import torch
    shape = sim_shape()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    L2, k = widen_head(ck, shape, a.hid, a.quiet, a.ms, a.bq)
    n_ = int(ck.pop("head2_ins_weights"))
    torch.save(ck, a.out)
    print("wrote {}: the head's input widened by {} columns at zero; the scorer's layers of the learner's shapes ({:,} weights, the last "
          "layers at zero, share 0: a league seat is under no instruction)".format(a.out, k, n_))


def same(a):
    import input_list as IL
    import test_suite as T
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == len(pb.mean), "the two read different lists"
    assert not getattr(pb, "ins_due", False) and float(getattr(pb, "ins_g", 0.0)) == 0.0, "b's share is above 0"
    names = getattr(pa, "names", None)
    assert names, "a network of a cleaned list (its names in the file)"
    lst = [L for L in (IL.load(21), IL.load(18)) if [tuple(x) for x in L["names"]] == [tuple(x) for x in names]]
    assert lst, "the network's list is not 18 or 21"
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
    kf = np.zeros((B, 7), np.float32)
    dact, n = 0, 0
    for t in range(F):
        raw = np.asarray(X[np.sort(pick[t])], np.float32)
        if raw.shape[1] != len(pa.mean):                     # (the simulator's full rows -> the network's list; a sample recorded before the
            full_ = np.zeros((len(raw), int(src.max()) + 1), np.float32)   # list's last columns existed: those read random numbers, as
            full_[:, :raw.shape[1]] = raw[:, :full_.shape[1]]               # tools/inputs21.py same fills them)
            if raw.shape[1] < full_.shape[1]:
                full_[:, raw.shape[1]:] = rng.uniform(-1, 1, (len(raw), full_.shape[1] - raw.shape[1])).astype(np.float32)
            raw = full_[:, src]
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        if getattr(pa, "keep_on", False):
            kf[:, 0] = rng.uniform(0, 5, B)
            kf[:, 2] = rng.integers(0, 9, B)
            kw["kf"] = kf
        oa, ha = pa.act(raw, ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw, hb, pose=pose, zmap=zmap, **kw)
        dact += int((oa != ob).sum())
        n += oa.size
        if t % 97 == 96:
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same: {} real rows x {} seats: actions that differ: {} of {}".format(F, B, dact, n))
    print("ALL PASSED" if dact == 0 else "FAILED")
    return 0 if dact == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("add", "widen-league"):
        p = sp.add_parser(nm)
        p.add_argument("inp")
        p.add_argument("out")
        p.add_argument("--hid", type=int, default=128)
        p.add_argument("--warm", type=int, default=20000)
        p.add_argument("--quiet", type=int, default=1, help="the instruction's sixth field (quiet movement): the scorer's third choice, never asked at the start")
        p.add_argument("--ms", type=int, default=1, help="the map sense at each row's place (eight numbers) is read after the row's own by the scorer and "
                       "the appraisals (the trainer's --ins-ms 1 with --map-sense); 0: not read")
        p.add_argument("--bq", type=int, default=1, help="the brain's three numbers among the head's inputs: the chance the enemy knows where he is, how "
                       "spread its zone odds are, how far apart its places ahead (zero weights at the start)")
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

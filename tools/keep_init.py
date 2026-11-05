"""1.4c: give a network with the strategy head (sim/head2.py) the keep choice, its start the target lock made soft, its share 0.

  python tools/keep_init.py add <in policy.pt> <out policy.pt> [--slope 0.75] [--edge 8.5] [--contact-p 0.9] [--opt <in opt.pt> <out opt.pt>]
      the keep layer added: z = keep(cat[head state, hands' memory, f]) -> the logit of re-deciding; its weights on the head's
      state and the hands' memory zero, on f (head2.keep_x: the age out of contact in s / 10, contact, the held target's log p / 5)
      the lock made soft: out of contact sigmoid(slope x (age - edge)), in contact --contact-p; keep_g 0 (the lock rule decides every
      reading: the network plays as before). --opt copies the optimizer's state (the trainer adds the keep choice's group after
      the head's when it loads one saved without it).
  python tools/keep_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass of both on the same random inputs and draws (tools/head2_init.py same): 0 actions differ for
      a network and its copy with the keep choice at share 0; then b at share 1 with the simulator's numbers drawn at random:
      the keep column comes back, its re-decisions by age and contact as the start says

CPU only (CUDA_VISIBLE_DEVICES=-1).
"""
import argparse
import math
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def start_p(slope, edge, contact_p, age, contact):
    """the start's chance to re-decide at an age (s) and contact (0 or 1)"""
    if contact:
        return contact_p
    return 1.0 / (1.0 + math.exp(-slope * (min(age, 20.0) - edge)))


def add(a):
    import torch
    import head2 as head2_
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    L = ck.get("head2")
    assert L is not None and "head2.gate" in sd, "the keep choice belongs to the strategy head: a network with it (1.3b on)"
    assert not L.get("keep") and "head2.keep.weight" not in sd, "the network already has the keep choice"
    L = dict(L, keep=1)
    S, Hh, F = int(L["size"]), int(L["widths"]["hands"]), head2_.KEEP_F
    w = torch.zeros(1, S + Hh + F)
    b = -a.slope * a.edge                                    # out of contact: slope x (age - edge), the age in s (the input is s / 10)
    w[0, S + Hh + 0] = a.slope * 10.0
    w[0, S + Hh + 1] = math.log(a.contact_p / (1.0 - a.contact_p)) - b    # in contact (the age input 0 there): logit(contact_p)
    sd["head2.keep.weight"] = w
    sd["head2.keep.bias"] = torch.tensor([b], dtype=torch.float32)
    sd["head2.keep_g"] = torch.zeros(())
    ck["head2"] = L
    m = head2_.make_module(L)                                # (the module loads it: every key in place)
    m.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    torch.save(ck, a.out)
    print(head2_.describe(L))
    print("wrote {}: the keep choice at share 0; its start, the chance to re-decide:".format(a.out))
    for age in (1, 3, 5, 7, 8, 9, 10, 11.5, 15):
        print("  out of contact, age {:>4} s: {:.4f}".format(age, start_p(a.slope, a.edge, a.contact_p, age, 0)))
    print("  in contact: {:.4f}".format(a.contact_p))
    if a.opt:
        shutil.copyfile(a.opt[0], a.opt[1])
        print("copied the optimizer's state {} -> {} (the keep choice's group is added by the trainer)".format(*a.opt))


def same(a):
    import head2_init as H2I
    import test_suite as T
    dh, dact = H2I.same(a)                                   # (a at its share, b at its: 0 for a file from add)
    ok = dact == 0 and dh == 0.0
    print("share 0: {}".format("PASS (the same to the bit)" if ok else "FAIL"))
    pb = T.Policy(a.b, seed=7)
    assert pb.h2 is not None and pb.h2.get("keep"), "b has no keep choice"
    pb.h2_live = True
    pb.set_keep_g(1.0)
    rng = np.random.default_rng(5)
    B, Fr = a.seats, a.frames
    hb = pb.zeros(B)
    pose = np.zeros((B, 4), np.float32)
    zmap = np.full(B, 0, np.int64)
    raw = rng.normal(pb.mean, np.sqrt(pb.var) + 1e-3, size=(Fr, B, len(pb.mean))).astype(np.float32)
    n_ = {}
    for t in range(Fr):
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        age = rng.uniform(0, 16, B).astype(np.float32)
        ct = (rng.random(B) < 0.3).astype(np.float32)
        kf = np.stack([age, ct, rng.integers(0, pb.dims[10], B).astype(np.float32)], 1)
        kw = {"xl": rng.normal(0, 1, (B, pb.legsP[0].shape[1])).astype(np.float32)} if pb.needs_xl else {}
        ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, kf=kf, **kw)
        assert ob.shape[1] == len(pb.dims) + 1 and set(np.unique(ob[:, -1])) <= {0, 1}, "the keep column at share 1: 0 or 1"
        for i in range(B):
            k_ = ("contact",) if ct[i] else ("age", int(age[i] // 2) * 2)
            c_ = n_.setdefault(k_, [0, 0])
            c_[0] += 1
            c_[1] += int(ob[i, -1])
    good = True
    for k_ in sorted(n_, key=str):
        c_ = n_[k_]
        p_ = c_[1] / max(1, c_[0])
        e_ = a.contact_p if k_[0] == "contact" else start_p(a.slope, a.edge, a.contact_p, k_[1] + 1.0, 0)
        print("  share 1, {}: re-decided {:.3f} of {} (the start at the middle of the band: {:.3f})".format(k_, p_, c_[0], e_))
        if k_[0] == "contact":
            good = good and abs(p_ - a.contact_p) < 0.06
    lo_ = sum(n_[k][1] for k in n_ if k[0] == "age" and k[1] <= 2) / max(1, sum(n_[k][0] for k in n_ if k[0] == "age" and k[1] <= 2))
    hi_ = sum(n_[k][1] for k in n_ if k[0] == "age" and k[1] >= 12) / max(1, sum(n_[k][0] for k in n_ if k[0] == "age" and k[1] >= 12))
    good = good and lo_ < 0.05 and hi_ > 0.9
    print("share 1: {} (young targets kept {:.3f}, old ones re-decided {:.3f}; in contact near {:g})".format("PASS" if good else "FAIL", 1 - lo_, hi_, a.contact_p))
    print("ALL PASSED" if (ok and good) else "FAILED")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "same"):
        p = sp.add_parser(name)
        if name == "add":
            p.add_argument("inp")
            p.add_argument("out")
            p.add_argument("--opt", nargs=2, default=None)
        else:
            p.add_argument("a")
            p.add_argument("b")
            p.add_argument("--frames", type=int, default=400)
            p.add_argument("--seats", type=int, default=8)
        p.add_argument("--slope", type=float, default=0.75, help="out of contact: the logit of re-deciding rises this much a second of age")
        p.add_argument("--edge", type=float, default=8.5, help="... and is 0 (an even chance) at this age (s): the lock's 8 s, read a second late")
        p.add_argument("--contact-p", type=float, default=0.9, help="in contact: the chance to re-decide (the lock rule: every reading free)")
    a = ap.parse_args()
    add(a) if a.cmd == "add" else same(a)


if __name__ == "__main__":
    main()

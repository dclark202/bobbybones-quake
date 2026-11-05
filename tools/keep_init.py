"""1.4c, 1.7a: give a network with the strategy head (sim/head2.py) the keep choice, its start the target lock made soft, its share 0.

  python tools/keep_init.py add <in policy.pt> <out policy.pt> [--slope 0.75] [--edge 8.5] [--contact-p 0.9] [--arrive-p 0.9]
                                [--rate 5] [--opt <in opt.pt> <out opt.pt>]
      the keep layer added (the layout's "keep" 2): z = keep(cat[head state, hands' memory, f]) -> the logit of re-deciding at a
      keep reading; its weights on the head's state, the hands' memory, the held target's log p, the seconds since the arrival, the
      sound and the hit zero; on the age, contact and arrival the lock made soft. 1.4c's start was a chance a second (one reading
      a second): out of contact sigmoid(slope x (age - edge)), in contact --contact-p. With --rate readings a second (1.7a: five,
      the head's tick) the same chance a second is 1 - (1 - p)^(1 / rate) a reading; out of contact a logistic in the age is
      fitted to it (the seconds a target is held: the survival curves matched), in contact and at an arrival out of contact
      (--arrive-p a second, as the lock rule's forced reading once a second) the exact chance a reading. keep_g 0 (the lock rule
      decides every second: the network plays as before). --opt copies the optimizer's state (the trainer adds the keep
      choice's group after the load).
  python tools/keep_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass of both on the same random inputs and draws (tools/head2_init.py same): 0 actions differ for
      a network and its copy with the keep choice at share 0; then b at share 1 with the simulator's numbers drawn at random:
      the keep column comes back (d + 2 c + 4 r: the coin always 1, a keep reading on the frames after the head's tick), its
      re-decisions by age, contact and arrival as the start says; at share 0.5 the coin half the time

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


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    return math.log(p / (1.0 - p))


def per_reading(p_sec, rate):
    """the chance a reading that gives the chance p_sec a second at rate readings a second"""
    return 1.0 - (1.0 - np.asarray(p_sec, np.float64)) ** (1.0 / rate)


def fit(slope, edge, rate):
    """a logistic z = w x age + b (age in s) a reading whose seconds held match 1.4c's start a second (survival curves, out of
    contact, quietly). -> w, b, the ages, the start's survival, the fit's"""
    ages = np.arange(0.0, 24.0 + 1e-9, 1.0 / rate)
    q_t = per_reading(sig(slope * (np.minimum(ages, 20.0) - edge)), rate)
    S_t = np.concatenate([[1.0], np.cumprod(1.0 - q_t)[:-1]])
    best = (1e9, 0.0, 0.0)
    for w in np.arange(0.30, 1.20 + 1e-9, 0.005):
        bs = np.arange(-14.0, -2.0 + 1e-9, 0.01)
        q_f = sig(w * np.minimum(ages, 20.0)[None, :] + bs[:, None])
        S_f = np.concatenate([np.ones((len(bs), 1)), np.cumprod(1.0 - q_f, 1)[:, :-1]], 1)
        e = ((S_f - S_t[None, :]) ** 2).sum(1)
        i = int(e.argmin())
        if e[i] < best[0]:
            best = (float(e[i]), float(w), float(bs[i]))
    w, b = best[1], best[2]
    S_f = np.concatenate([[1.0], np.cumprod(1.0 - sig(w * np.minimum(ages, 20.0) + b))[:-1]])
    return w, b, ages, S_t, S_f


def add(a):
    import torch
    import head2 as head2_
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    L = ck.get("head2")
    assert L is not None and "head2.gate" in sd, "the keep choice belongs to the strategy head: a network with it (1.3b on)"
    assert not L.get("keep") and "head2.keep.weight" not in sd, "the network already has the keep choice"
    L = dict(L, keep=2)
    S, Hh, F = int(L["size"]), int(L["widths"]["hands"]), head2_.KEEP_F
    w_age, b, ages, S_t, S_f = fit(a.slope, a.edge, a.rate)
    qc, qa = float(per_reading(a.contact_p, a.rate)), float(per_reading(a.arrive_p, a.rate))
    w = torch.zeros(1, S + Hh + F)
    w[0, S + Hh + 0] = w_age * 10.0                          # (the age input is s / 10, 0 in contact and at an arrival)
    w[0, S + Hh + 1] = logit(qc) - b                         # in contact: logit(qc)
    w[0, S + Hh + 3] = logit(qa) - b                         # arrived out of contact: logit(qa)
    sd["head2.keep.weight"] = w
    sd["head2.keep.bias"] = torch.tensor([b], dtype=torch.float32)
    sd["head2.keep_g"] = torch.zeros(())
    ck["head2"] = L
    m = head2_.make_module(L)                                # (the module loads it: every key in place)
    m.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    torch.save(ck, a.out)
    print(head2_.describe(L))
    print("wrote {}: the keep choice at share 0 (layout keep 2, {} numbers); its start at {} readings a second:".format(a.out, F, a.rate))
    print("  out of contact, quiet: z = {:.4f} x age + {:.4f} a reading (1.4c's start a second: sigmoid({} x (age - {})))".format(w_age, b, a.slope, a.edge))
    print("  {:>6} {:>12} {:>12} {:>12} {:>16}".format("age s", "start /s", "fit /s", "fit /reading", "held S fit-start"))
    for age in (1, 3, 5, 7, 8, 9, 10, 11.5, 13, 15):
        ps_ = float(sig(a.slope * (min(age, 20.0) - a.edge)))
        pr_ = float(sig(w_age * age + b))
        pf_ = 1.0 - (1.0 - pr_) ** a.rate
        i_ = int(round(age * a.rate))
        print("  {:>6} {:>12.4f} {:>12.4f} {:>12.4f} {:>+16.4f}".format(age, ps_, pf_, pr_, S_f[i_] - S_t[i_]))
    dt_ = 1.0 / a.rate
    print("  seconds held (quiet, out of contact): the start {:.2f}, the fit {:.2f}".format(float(S_t.sum() * dt_), float(S_f.sum() * dt_)))
    print("  in contact: {:.4f} a reading ({} a second); arrived out of contact: {:.4f} a reading ({} a second)".format(qc, a.contact_p, qa, a.arrive_p))
    if a.opt:
        shutil.copyfile(a.opt[0], a.opt[1])
        print("copied the optimizer's state {} -> {} (the keep choice's group is added by the trainer)".format(*a.opt))


def same(a):
    import head2_init as H2I
    import test_suite as T
    import head2 as head2_
    dh, dact = H2I.same(a)                                   # (a at its share, b at its: 0 for a file from add)
    ok = dact == 0 and dh == 0.0
    print("share 0: {}".format("PASS (the same to the bit)" if ok else "FAIL"))
    pb = T.Policy(a.b, seed=7)
    assert pb.h2 is not None and int(pb.h2.get("keep") or 0) == 2, "b has no keep choice of 1.7a's (layout keep 2)"
    pb.h2_live = True
    kw_ = np.asarray(pb.h2W["keep.weight"])[0, -head2_.KEEP_F:]
    kb_ = float(np.asarray(pb.h2W["keep.bias"]).reshape(-1)[0])
    good = True
    for g_ in (1.0, 0.5):
        pb.set_keep_g(g_)
        pb.k_r = None
        rng = np.random.default_rng(5)
        B, Fr = a.seats, a.frames
        hb = pb.zeros(B)
        pose = np.zeros((B, 4), np.float32)
        zmap = np.full(B, 0, np.int64)
        raw = rng.normal(pb.mean, np.sqrt(pb.var) + 1e-3, size=(Fr, B, len(pb.mean))).astype(np.float32)
        n_, coin_, rd_, fr_ = {}, 0, 0, 0
        for t in range(Fr):
            pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
            pose[:, 3] = rng.uniform(-180, 180, B)
            age = rng.uniform(0, 16, B).astype(np.float32)
            ct = (rng.random(B) < 0.3).astype(np.float32)
            ar = ((rng.random(B) < 0.2) & (ct == 0)).astype(np.float32)
            kf = np.stack([age, ct, rng.integers(0, pb.dims[10], B).astype(np.float32), ar, rng.uniform(0, 10, B),
                           rng.uniform(0, 20, B), rng.uniform(0, 20, B)], 1).astype(np.float32)
            kw = {"xl": rng.normal(0, 1, (B, pb.legsP[0].shape[1])).astype(np.float32)} if pb.needs_xl else {}
            ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, kf=kf, **kw)
            assert ob.shape[1] == len(pb.dims) + 1 and ob[:, -1].min() >= 0 and ob[:, -1].max() <= 7, "the keep column: d + 2 c + 4 r"
            col = ob[:, -1]
            coin_ += int(((col >> 1) & 1).sum())
            rd_ += int(((col >> 2) & 1).sum())
            fr_ += B
            if g_ < 1.0:
                continue
            for i in range(B):
                k_ = ("contact",) if ct[i] else (("arrived",) if ar[i] else ("age", int(age[i] // 2) * 2))
                c_ = n_.setdefault(k_, [0, 0])
                c_[0] += 1
                c_[1] += int(col[i] & 1)
        print("share {}: the coin {:.3f} of frames; keep readings {:.3f} of frames (the head ticks every few frames)".format(g_, coin_ / fr_, rd_ / fr_))
        good = good and abs(coin_ / fr_ - g_) < 0.03 and 0.0 < rd_ / fr_ < 0.5
        if g_ < 1.0:
            continue
        for k_ in sorted(n_, key=str):
            c_ = n_[k_]
            p_ = c_[1] / max(1, c_[0])
            if k_[0] == "contact":
                e_ = float(sig(kb_ + kw_[1]))
            elif k_[0] == "arrived":
                e_ = float(sig(kb_ + kw_[3]))
            else:
                e_ = float(sig(kb_ + kw_[0] * (k_[1] + 1.0) / 10.0))
            print("  share 1, {}: re-decided {:.3f} of {} (the start at the band's middle, held log p aside: {:.3f})".format(k_, p_, c_[0], e_))
            if k_[0] in ("contact", "arrived"):
                good = good and abs(p_ - e_) < 0.06
        lo_ = sum(n_[k][1] for k in n_ if k[0] == "age" and k[1] <= 2) / max(1, sum(n_[k][0] for k in n_ if k[0] == "age" and k[1] <= 2))
        hi_ = sum(n_[k][1] for k in n_ if k[0] == "age" and k[1] >= 12) / max(1, sum(n_[k][0] for k in n_ if k[0] == "age" and k[1] >= 12))
        good = good and lo_ < 0.02 and hi_ > 0.3
        print("share 1: young targets kept {:.3f} a reading, old ones re-decided {:.3f} a reading".format(1 - lo_, hi_))
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
        p.add_argument("--slope", type=float, default=0.75, help="1.4c's start: out of contact the logit of re-deciding a second rises this much a second of age")
        p.add_argument("--edge", type=float, default=8.5, help="... and is 0 (an even chance) at this age (s): the lock's 8 s, read a second late")
        p.add_argument("--contact-p", type=float, default=0.9, help="in contact: the chance to re-decide a second (the lock rule: every reading free)")
        p.add_argument("--arrive-p", type=float, default=0.9, help="(1.7a) arrived out of contact: the chance to re-decide a second (the lock rule: a forced reading a second)")
        p.add_argument("--rate", type=float, default=5.0, help="(1.7a) keep readings a second (the head's tick: 5)")
    a = ap.parse_args()
    add(a) if a.cmd == "add" else same(a)


if __name__ == "__main__":
    main()

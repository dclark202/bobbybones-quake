"""v0.4.3: give a network the strategy head (sim/head2.py) with its outputs at zero, and prove it answers as before.

  python tools/head2_init.py add <in policy.pt> <out policy.pt> [--gate G] [--opt <in opt.pt> <out opt.pt>] [--off hands,ctrl]
      [--ctrl-src none|belief|both]
      the head added (plan_in and target at zero, so the network answers exactly as without it whatever the gate); the gate
      written into head2.gate (default 1: the trainer's --head2-open 0 holds it there; 0: shut). --opt copies the optimizer's
      state (the trainer adds the head's own group after the others when it loads one saved without it).
  python tools/head2_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass (test_suite.Policy) of both on the same random inputs, the same draws: the largest
      difference of his memory and of the actions (the brain stepped in both, as in training)

CPU only (CUDA_VISIBLE_DEVICES=-1). A network needs the brain (belief, track; v0.4.1 on).
"""
import argparse
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
INTENT_HEAD = 10


def add(a):
    import torch
    import head2 as head2_
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    assert ck.get("head2") is None and not any(k.startswith("head2.") for k in sd), "the network already has a strategy head"
    assert ck.get("belief") is not None and "track.0.weight" in sd, "the strategy head reads the brain: a network with --belief and --track"
    tz = int(ck["track_z"]["d"]) if (ck.get("track_z") and "trackz.0.weight" in sd) else 0
    ah = int(ck["ahead"]["d"]) if (ck.get("ahead") and "ahead.0.weight" in sd) else 0
    L = head2_.layout(brain=int(ck["belief"]["hid"]), trk=int(sd["track.2.weight"].shape[0]), trz=tz, ahead=ah, ctrl=a.ctrl,
                      hands=int(ck["hidden"]), enc=256, size=a.size, inp=a.inp_w, plan=a.plan,
                      n_target=int(ck["action_dims"][INTENT_HEAD]), every=int(ck["belief"]["every"]), gamma=a.gamma,
                      on={p: 0 for p in a.off.split(",") if p}, ctrl_src=a.ctrl_src)
    assert max(L["obs_cols"]) < int(ck["obs_dim"]), "docs/INPUTS.csv does not fit the network's {} inputs".format(ck["obs_dim"])
    m = head2_.make_module(L)
    with torch.no_grad():
        m.gate.fill_(a.gate)
    for k, v in m.state_dict().items():
        sd["head2." + k] = v.clone()
    ck["head2"] = L
    torch.save(ck, a.out)
    print(head2_.describe(L))
    print("wrote {} (gate {:g}; plan_in and target at zero)".format(a.out, a.gate))
    if a.opt:
        shutil.copyfile(a.opt[0], a.opt[1])
        print("copied the optimizer's state {} -> {} (the head's group is added by the trainer)".format(*a.opt))


def same(a):
    import test_suite as T
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and float(p.h2W["gate"]) > 0 and not p.h2_live:
            print("{}: its strategy head is shut by its zero links: played as the force test below".format(os.path.basename(a.a if p is pa else a.b)))
    # (a head at zero links is not stepped: force it, so that the test runs the head's whole numpy path)
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and float(p.h2W["gate"]) > 0:
            p.h2_live = True
    assert pa.brain_on and pb.brain_on, "the brain is not stepped (its token's gate shut): nothing to compare"
    rng = np.random.default_rng(3)
    B, F = a.seats, a.frames
    ha, hb = pa.zeros(B), pb.zeros(B)
    dh, dact, dlog = 0.0, 0, 0.0
    W0 = pa.W if pa.h2 is None else pa.h2_at
    W1 = pb.W if pb.h2 is None else pb.h2_at
    raw = rng.normal(pa.mean, np.sqrt(pa.var) + 1e-3, size=(F, B, len(pa.mean))).astype(np.float32)
    pose = np.zeros((B, 4), np.float32)
    zmap = np.full(B, 0, np.int64)
    for t in range(F):
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:                                       # (the legs' branch's inputs: random too)
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        oa, ha = pa.act(raw[t], ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, **kw)
        dh = max(dh, float(np.abs(ha[:, :min(W0, pa.H)] - hb[:, :min(W1, pb.H)]).max()))
        dact += int((oa != ob).sum())
        if t % 97 == 96:                                      # a reset now and then, as a death
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same: {} frames x {} seats: largest |h a - h b| = {:.3g}; actions that differ: {}".format(F, B, dh, dact))
    if pb.h2 is not None:
        s_ = hb[:, pb.h2_at:pb.h2_at + int(pb.h2["size"])]
        print("  (b's strategy head ran: its state's mean |s| {:.4f}, valid {:.2f})".format(float(np.abs(s_).mean()),
                                                                                        float(hb[:, pb.h2_at + int(pb.h2["size"])].mean())))
    return dh, dact


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--gate", type=float, default=1.0)
    p.add_argument("--opt", nargs=2, default=None)
    p.add_argument("--off", default="")
    p.add_argument("--ctrl", type=int, default=4)
    p.add_argument("--ctrl-src", default="none", help="what the ctrl slot reads: none (zeros), belief or both (the 'in control' readout "
                                                     "of that name; the trainer's --head2-ctrl-src can change it later)")
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--inp-w", type=int, default=256)
    p.add_argument("--plan", type=int, default=64)
    p.add_argument("--gamma", type=float, default=0.9998)
    q = sp.add_parser("same")
    q.add_argument("a")
    q.add_argument("b")
    q.add_argument("--frames", type=int, default=400)
    q.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    add(a) if a.cmd == "add" else same(a)


if __name__ == "__main__":
    main()

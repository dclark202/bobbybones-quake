"""1.5a, part D: give a network with the strategy head (sim/head2.py; 1.3b's end on, with or without the keep choice) the head's weapon
part, at zero.

  python tools/weapon_init.py add <in policy.pt> <out policy.pt> [--wadd 1] [--opt <in opt.pt> <out opt.pt>]
      the layout's "weapon" (the weapon key's choices) and its inputs "wobs" (head2.W_OBS's columns of docs/INPUTS.csv: the weapon
      in his hand and whether he can fire, the enemy's weapon in view and since his last death, the hums, the enemy in view and his
      last known place); winp (those inputs into the head's GRU input) and wsc (its scores on the weapon key) at exactly zero; wadd
      (the scores' add) --wadd. --opt copies the optimizer's state (the trainer adds the weapon part's group after the keep
      choice's, or the head's, when it loads one saved without it).
  python tools/weapon_init.py same <a.pt> <b.pt> [--frames 400] [--seats 8]
      the checks' numpy forward pass of both on the same random inputs and draws: 0 actions differ, the hands' memory and the
      head's state the same to the bit (a: the source, b: from add); then b with wsc made random (winp still zero): only the weapon
      key's column differs, the hands' memory and the head's state still the same; then b with winp random too: the head's state
      moves; and b with wadd 0 (the blanked check) against a: the same to the bit again

CPU only (CUDA_VISIBLE_DEVICES=-1).
"""
import argparse
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
WKEY = 6                                                     # the weapon key's output (keep, then 1 + the weapon's index)


def add(a):
    import torch
    import head2 as head2_
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    sd = ck["model"]
    L = ck.get("head2")
    assert L is not None and "head2.gate" in sd, "the weapon part belongs to the strategy head: a network with it (1.3b on)"
    assert not L.get("weapon") and "head2.wsc.weight" not in sd, "the network already has the weapon part"
    import duel_env as E_                                    # (the weapon key's width: the simulator's actions)
    n = int(E_.ACTION_DIMS[WKEY])
    assert n == 1 + len(E_.WEAPONS), (n, E_.WEAPONS)
    cols = head2_.obs_cols(sel=head2_.W_OBS)
    assert len(cols) == 35, "the weapon part's inputs: {} columns, 35 expected ({})".format(len(cols), cols)
    L2 = head2_.add_weapon(L, cols, n)
    I_, S = int(L["inp"]), int(L["size"])
    sd["head2.winp.weight"] = torch.zeros(I_, len(cols))
    sd["head2.winp.bias"] = torch.zeros(I_)
    sd["head2.wsc.weight"] = torch.zeros(n, S)
    sd["head2.wsc.bias"] = torch.zeros(n)
    sd["head2.wadd"] = torch.tensor(float(a.wadd))
    ck["head2"] = L2
    m = head2_.make_module(L2)                               # (the module loads it: every key in place)
    m.load_state_dict({k[len("head2."):]: v for k, v in sd.items() if k.startswith("head2.")})
    torch.save(ck, a.out)
    print(head2_.describe(L2))
    print("its inputs (wobs, {}): {}".format(len(cols), cols))
    print("wrote {}: the weapon part at zero, wadd {:g}".format(a.out, float(a.wadd)))
    if a.opt:
        shutil.copyfile(a.opt[0], a.opt[1])
        print("copied the optimizer's state {} -> {} (the weapon part's group is added by the trainer)".format(*a.opt))


def run(pa, pb, a, seed=3):
    """both on the same random inputs and draws -> (largest |hands' memory a - b|, largest |head state a - b|, actions that differ
    by output)"""
    rng = np.random.default_rng(seed)
    B, F = a.seats, a.frames
    ha, hb = pa.zeros(B), pb.zeros(B)
    dh = ds = 0.0
    dact = np.zeros(len(pa.dims) + 1, np.int64)              # (the last: the keep column)
    S = int(pa.h2["size"])
    raw = rng.normal(pa.mean, np.sqrt(pa.var) + 1e-3, size=(F, B, len(pa.mean))).astype(np.float32)
    pose = np.zeros((B, 4), np.float32)
    zmap = np.full(B, 0, np.int64)
    for t in range(F):
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kf = np.stack([rng.uniform(0, 16, B), (rng.random(B) < 0.3).astype(np.float32),
                       rng.integers(0, pa.dims[10], B).astype(np.float32)], 1).astype(np.float32)
        kw = {"kf": kf}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        oa, ha = pa.act(raw[t], ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(raw[t], hb, pose=pose, zmap=zmap, **kw)
        dh = max(dh, float(np.abs(ha[:, :pa.H] - hb[:, :pb.H]).max()))
        ds = max(ds, float(np.abs(ha[:, pa.h2_at:pa.h2_at + S] - hb[:, pb.h2_at:pb.h2_at + S]).max()))
        n_ = min(oa.shape[1], ob.shape[1])
        dact[:n_] += (oa[:, :n_] != ob[:, :n_]).sum(0)
        if t % 97 == 96:                                      # a reset now and then, as a death
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    return dh, ds, dact


def same(a):
    import test_suite as T
    ok = True

    def pol(path):
        p = T.Policy(path, seed=7)
        assert p.h2 is not None and p.brain_on, "a network with the strategy head and the brain"
        p.h2_live = True                                      # (the head's whole numpy path, as tools/head2_init.py same)
        return p

    def say(name, cond, msg):
        nonlocal ok
        ok = ok and bool(cond)
        print("{} {}: {}".format("PASS" if cond else "FAIL", name, msg))

    pa, pb = pol(a.a), pol(a.b)
    assert pb.h2.get("weapon") and "wsc.weight" in pb.h2W, "b has no weapon part"
    dh, ds, dact = run(pa, pb, a)
    say("b as built", dh == 0.0 and ds == 0.0 and dact.sum() == 0,
        "{} frames x {} seats: |h a - h b| {:.3g}, |head a - head b| {:.3g}, actions that differ {}".format(a.frames, a.seats, dh, ds, int(dact.sum())))
    rng = np.random.default_rng(11)                          # (each comparison from two fresh networks: their draws' streams start alike)
    wr_ = rng.normal(0, 0.05, pb.h2W["wsc.weight"].shape).astype(np.float32)
    br_ = rng.normal(0, 0.5, pb.h2W["wsc.bias"].shape).astype(np.float32)
    ir_ = rng.normal(0, 0.05, pb.h2W["winp.weight"].shape).astype(np.float32)

    def b_with(**kw):
        p = pol(a.b)
        p.h2W = dict(p.h2W, **kw)
        return p

    pa, pb = pol(a.a), b_with(**{"wsc.weight": wr_, "wsc.bias": br_})
    dh, ds, dact = run(pa, pb, a)
    oth = int(dact.sum() - dact[WKEY])
    say("wsc random", dh == 0.0 and ds == 0.0 and dact[WKEY] > 0 and oth == 0,
        "the weapon key differs {} times, the other outputs {}; |h| {:.3g}, |head| {:.3g}".format(int(dact[WKEY]), oth, dh, ds))
    pa, pb = pol(a.a), b_with(**{"wsc.weight": wr_, "wsc.bias": br_, "winp.weight": ir_})
    dh, ds, dact = run(pa, pb, a)
    say("winp random too", ds > 0.0, "the head's state moves ({:.3g}); the hands' memory {:.3g} (the plan's gate {})".format(
        ds, dh, float(np.asarray(pb.h2W.get("gate", 0.0)))))
    pa, pb = pol(a.a), b_with(**{"wsc.weight": wr_, "wsc.bias": br_})
    pb.set_head2_wadd(0.0)
    pb.h2_live = True
    dh, ds, dact = run(pa, pb, a)
    say("wadd 0 (the blanked check)", dh == 0.0 and ds == 0.0 and dact.sum() == 0,
        "actions that differ {} with wsc random and its add 0".format(int(dact.sum())))
    print("ALL PASSED" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--wadd", type=float, default=1.0, help="the head's weapon scores' add (1: on; its scores start at zero)")
    p.add_argument("--opt", nargs=2, default=None)
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--frames", type=int, default=400)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "add":
        add(a)
    else:
        sys.exit(0 if same(a) else 1)


if __name__ == "__main__":
    main()

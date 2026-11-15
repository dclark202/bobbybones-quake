"""2.1 (docs/runs/2.1/README.md): the keep choice's quiet layer and the stay value PLAYED by the numpy players: the checks' (sim/test_suite.py
Policy) and the servers' (sim/export_duel.py -> plugins/netpass.py), on a duel map in the simulator with KEEP_ZONE=1 KEEP_SIG=1.

    python tools/run/keep21_playtest.py --src <policy.pt of a network without the keep choice> --work <scratch folder>
        [--cmd docs/runs/2.0/2.0e/train.cmd] [--map bloodrun] [--frames 800] [--matches 4]

  a. MAKE: tools/keep_init.py add <src> --start zero --quiet 1 (the keep choice and its quiet layer at zero), then in the file: a stay
     value (sim/stay.py make_module, its last layer random and nonzero, scale 1.5), the quiet layer's weights nonzero, keep_g = keepq_g
     = 1 (quiet.pt); the same with keep_g = keepq_g = 0 (quiet_g0.pt); quiet.pt exported by sim/export_duel.py (quiet.npz).
  b. PLAY: quiet.pt on every seat (test_suite.Policy, seed 0) in the simulator (the run's switches from --cmd, KEEP_ZONE=1, KEEP_SIG=1):
     the column carries bits 512 (the quiet draw) and 1024 (the quiet coin), the simulator's keep_live has 2s (the quiet layer decided),
     the stay value is made and moves.
  c. SERVER = CHECKS: the recorded frames (inputs, keep_feat, pose, resets) replayed through test_suite.Policy (seed 0) and through
     plugins/netpass.py on quiet.npz (rng seed 0; its keep stream 1414 = Policy's 0 + 1414): the actions, the keep column, the stay
     value, the quiet layer's numbers and logit, and the memory arrays, frame by frame. The bar: every difference 0.
  d. SHARE 0 = AS BEFORE: quiet_g0.pt and the source file replayed on the same frames: the actions and the memory to the bit (quiet_g0
     gives no keep column at keep_g 0 and keepq_g 0).

One simulator in this process (one World a process). Reads the maps from QLBOT_ROOT's data/maps."""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def make(a):
    import torch
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import head2 as head2_
    import stay as stay_
    os.makedirs(a.work, exist_ok=True)
    kq0 = os.path.join(a.work, "keepq_zero.pt")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "keep_init.py"), "add", a.src, kq0, "--start", "zero", "--quiet", "1"],
                       capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1500:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("keep_init add failed")
    ck = torch.load(kq0, weights_only=False, map_location="cpu")
    L2 = ck["head2"]
    assert L2.get("keep") and L2.get("keepq"), "keep_init gave no quiet layer"
    H = int(ck["model"]["gru.weight_hh"].shape[1])
    SL = stay_.layout(bel=int(ck["belief"]["hid"]), mem=H, head=int(L2["size"]), kx=head2_.KEEP_F, ksig=head2_.KSIG)
    M = stay_.make_module(SL)
    g = torch.Generator().manual_seed(2101)
    with torch.no_grad():
        M.l3.weight.copy_(torch.randn(M.l3.weight.shape, generator=g) * 0.4)
        M.l3.bias.fill_(0.2)
        M.scale.fill_(1.5)
    opt = torch.optim.Adam(M.parameters(), lr=1e-4)
    ck["stay"] = dict(layout=SL, model={k_: v_.detach().cpu() for k_, v_ in M.state_dict().items()}, opt=opt.state_dict())
    sd = ck["model"]
    sd["head2.keepq.weight"] = torch.tensor([[0.9, 0.6, 0.5, -0.4, 0.7, 0.8, 0.3][:head2_.KEEPQ_F]], dtype=torch.float32)
    sd["head2.keepq.bias"] = torch.tensor([-0.3], dtype=torch.float32)
    sd["head2.keep_g"] = torch.ones(())
    sd["head2.keepq_g"] = torch.ones(())
    q1 = os.path.join(a.work, "quiet.pt")
    torch.save(ck, q1)
    sd["head2.keep_g"] = torch.zeros(())
    sd["head2.keepq_g"] = torch.zeros(())
    torch.save(ck, os.path.join(a.work, "quiet_g0.pt"))
    print("a. MADE {} (stay: inp {}, hid {}; keep_g 1, keepq_g 1) and quiet_g0.pt (shares 0)".format(q1, SL["inp"], SL["hid"]), flush=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "keep21_playtest", "--policy", os.path.abspath(q1),
                        "--out", os.path.join(a.work, "quiet.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1500:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(os.path.join(a.work, "quiet.npz"))
    need = ["head2.keepq.weight", "head2.keepq.bias", "head2.keepq_g", "head2.keep_g", "stay", "stay.l1.weight", "stay.l3.weight", "stay.scale"]
    miss = [k_ for k_ in need if k_ not in z.files]
    print("a. EXPORT: {}".format("PASS (quiet layer, shares, stay value in the file)" if not miss else "FAIL missing {}".format(miss)), flush=True)
    return not miss


def cmd_env(path, root):
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import keep21_simtest as ks_
    return ks_.cmd_env(path, root)


def play(a):
    ev = cmd_env(a.cmd, os.environ.get("QLBOT_ROOT") or ROOT)
    ev.update(KEEP_ZONE="1", KEEP_SIG="1")
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))
    import importlib
    import csv
    E = importlib.import_module("duel_env_ffa")
    import test_suite as T
    import btoken as BT
    assert E.KEEP_ZONE and E.KEEP_SIG, "the switches did not reach the simulator"
    q1 = os.path.join(a.work, "quiet.pt")
    pol = T.Policy(q1, seed=0)
    assert pol.kq_on and pol.keepq_g == 1.0 and pol.keep_g == 1.0 and pol.stayW is not None, "quiet.pt: the quiet layer, its share or the stay value not read"
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    idx = np.array([now.index(tuple(x_)) for x_ in pol.names]) if pol.names else np.arange(len(pol.mean))
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(DATA, "maps", a.map + ".bsp"), n_matches=a.matches, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    n = env.n
    nA = len(E.ACTION_DIMS)
    obs = env.observe()
    h = pol.zeros(n)
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[], kl=[], sv=[], kq=[], H=[])
    for t in range(a.frames):
        kf = env.keep_feat()
        pz, zz = BT.pose_from_env(env, a.map)
        xl = env.legs_prep() if pol.needs_xl else None
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        assert ac.shape[1] == len(pol.dims) + 1, "no keep column"
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac), ("H", h)):
            rec[k_].append(None if v_ is None else np.array(v_).copy())
        rec["sv"].append(np.array(pol.sv).copy())
        rec["kq"].append(np.concatenate([pol.last_keepq[0], pol.last_keepq[1][:, None]], 1).copy())
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:     # (as tools/netpass_check.py: his legs' branch for the simulator)
            env.legs_lg = pol.legs_logits(env.legs_prep())
        obs, r_, done, info = env.step(act)
        rec["kl"].append(np.asarray(env.keep_live).astype(np.int8).copy())
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    kc = np.array([x_[:, -1] for x_ in rec["act"]])
    kl = np.array(rec["kl"])
    sv = np.array(rec["sv"])
    b512, b1024, b4 = int(((kc & 512) > 0).sum()), int(((kc & 1024) > 0).sum()), int(((kc & 4) > 0).sum())
    n1, n2 = int((kl == 1).sum()), int((kl == 2).sum())
    nsv = len(np.unique(np.round(sv, 6)))
    okb = b512 > 0 and b1024 > 0 and n2 > 0 and n1 > 0 and b1024 == kc.size and nsv > 3 and np.abs(sv).max() > 0
    print("b. PLAY {} frames x {} seats on {}: column bit 512 on {} seat-frames, bit 1024 on {} (of {}), keep readings (bit 4) {}; keep_live 1 (zone) {}, "
          "2 (quiet) {}; stay value: {} distinct values, range {:.3f} .. {:.3f}; the quiet logit {:.3f} .. {:.3f}: {}".format(
              a.frames, n, a.map, b512, b1024, kc.size, b4, n1, n2, nsv, sv.min(), sv.max(),
              float(np.min([x_[:, -1].min() for x_ in rec["kq"]])), float(np.max([x_[:, -1].max() for x_ in rec["kq"]])), "PASS" if okb else "FAIL"), flush=True)
    # c. the checks' player again and the plugins' pass on the same frames
    pol2 = T.Policy(q1, seed=0)
    h2 = pol2.zeros(n)
    import netpass as N
    P, A = N.load(os.path.join(a.work, "quiet.npz"))
    assert N.keepq_g(P) == 1.0 and N.keep_g(P) == 1.0 and P["_kq"]["stay"] is not None, "quiet.npz: the quiet layer, its share or the stay value not read"
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    bad = dict(replay=0, act=0, col=0, sv=0, kq=0, H=0)
    first = {}
    for t in range(a.frames):
        o_ = rec["obs"][t]
        ac2, h2 = pol2.act(o_[:, idx], h2, xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        kqn = np.concatenate([P["_last_keepq"][0], P["_last_keepq"][1][:, None]], 1)
        kqp = np.concatenate([pol2.last_keepq[0], pol2.last_keepq[1][:, None]], 1)
        for k_, c_ in (("replay", not np.array_equal(ac2, rec["act"][t])), ("act", not np.array_equal(acn, ac2[:, :-1])),
                       ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])), ("sv", not np.array_equal(P["_kq"]["sv"], pol2.sv)),
                       ("kq", not np.array_equal(kqn, kqp)), ("H", not np.array_equal(hn, h2))):
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    okc = not any(bad.values())
    print("c. SERVER = CHECKS over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, stay value {}, quiet numbers+logit {}, "
          "memory {}{}: {}".format(a.frames, bad["replay"], bad["act"], bad["col"], bad["sv"], bad["kq"], bad["H"],
                                   " (first: {})".format(first) if first else "", "PASS" if okc else "FAIL"), flush=True)
    # d. shares 0: as the source file, to the bit
    pg0, ps = T.Policy(os.path.join(a.work, "quiet_g0.pt"), seed=0), T.Policy(a.src, seed=0)
    assert pg0.kq_on and pg0.keep_g == 0 and pg0.keepq_g == 0 and not pg0.keep_on
    hg, hs = pg0.zeros(n), ps.zeros(n)
    assert hg.shape == hs.shape, "the memory arrays differ in width"
    dd = dict(act=0, H=0)
    for t in range(a.frames):
        o_ = rec["obs"][t][:, idx]
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t])
        a1, hg = pg0.act(o_, hg, kf=rec["kf"][t], **kw)
        a2, hs = ps.act(o_, hs, **kw)
        dd["act"] += int(not np.array_equal(a1, a2))
        dd["H"] += int(not np.array_equal(hg, hs))
        if rec["clr"][t].any():
            pg0.clear(hg, rec["clr"][t])
            ps.clear(hs, rec["clr"][t])
    okd = not any(dd.values())
    print("d. SHARES 0 = THE SOURCE FILE over {} frames: frames with a difference: actions {}, memory {}: {}".format(a.frames, dd["act"], dd["H"], "PASS" if okd else "FAIL"),
          flush=True)
    return okb and okc and okd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(DATA, "sim_runs", "duel_gru_2_0e", "keep", "policy_u10_20e.pt"))
    ap.add_argument("--work", required=True)
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.0", "2.0e", "train.cmd"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=800)
    ap.add_argument("--matches", type=int, default=4)
    ap.add_argument("--legs", default="move_v17_look", help="the movement network's run (the export's --legs: a network with LEGS=1)")
    ap.add_argument("--skip-make", action="store_true")
    a = ap.parse_args()
    ok = True
    if not a.skip_make:
        ok = make(a) and ok
    ok = play(a) and ok
    print("ALL PASSED" if ok else "FAILED", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

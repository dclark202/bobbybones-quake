"""2.1f: the outlook end to end outside the trainer, in the real simulator (docs/runs/2.1/2.1f; made from tools/run/slow_playtest.py).

  a. MAKE: tools/out_init.py add <a 2.1d save> -> out0.pt (the outlook inside the head: out_g 0, out_pick 0); the same with the held share 0.5,
     the pull 1.0, out_g 1.0, out_pick 0 and the outlook's last layer made non-zero by a fixed-seed random (the test only: so that the term is not
     zero) -> out.pt; sim/export_duel.py -> out.npz (the outlook's layers and dials in the file).
  b. PLAY: out.pt on every seat of a few matches through test_suite.Policy with the keep rows and the trip-end column (recorded for c and d);
     then (c2, information, and a check that the term acts) out.pt at out_g 1.0 against itself at out_g 0 on the same frames: frames that differ.
  c. SERVER = CHECKS at out_g 1.0: out.pt's recorded frames replayed through test_suite.Policy (seed 0) and through plugins/netpass.py on the
     export: the actions, the keep column, the whole memory array, the plan's held odds, frame by frame: 0 differences.
  d. OUT_G 0 = THE SOURCE FILE: out0.pt against <src> on the same frames, and out.pt at out_g 0 (its non-zero layer silent) against <src>, at the
     files' own pull and held share and again at pull 1.0 and held share 0.5 on both: 0 differences in the actions, the keep column and the memory.

    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/run/out_playtest.py --src <2.1d save> --work <a scratch folder>
One simulator in this process. Nothing deleted."""
import argparse
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    # this checkout: its sim/, plugins/, tools/
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")                       # the data: the main checkout's in a worktree
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SHARE, PULL, OUTG, PICK = 0.5, 1.0, 1.0, 0


def make(a):
    import torch
    os.makedirs(a.work, exist_ok=True)
    p0 = os.path.join(a.work, "out0.pt")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "out_init.py"), "add", a.src, p0], capture_output=True, text=True, creationflags=NOWIN)
    print(r.stdout.strip(), flush=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit("out_init add failed")
    ck = torch.load(p0, weights_only=False, map_location="cpu")
    sd = ck["model"]
    sd["head2.held_g"] = torch.tensor(SHARE)
    sd["head2.pull_g"] = torch.tensor(PULL)
    sd["head2.out_g"] = torch.tensor(OUTG)
    sd["head2.out_pick"] = torch.tensor(float(PICK))
    g_ = torch.Generator().manual_seed(2127)
    w_ = sd["head2.out.l3.weight"]
    sd["head2.out.l3.weight"] = torch.randn(w_.shape, generator=g_) * (4.0 / float(w_.shape[1]) ** 0.5)
    sd["head2.out.l3.bias"] = torch.randn(sd["head2.out.l3.bias"].shape, generator=g_) * 0.3
    p1 = os.path.join(a.work, "out.pt")
    torch.save(ck, p1)
    print("a. out.pt: held share {}, pull {}, out_g {}, out_pick {}; the outlook's last layer made non-zero (seed 2127)".format(SHARE, PULL, OUTG, PICK), flush=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "out_playtest", "--policy", os.path.abspath(p1),
                        "--out", os.path.join(a.work, "out.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True,
                       creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1500:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(os.path.join(a.work, "out.npz"))
    ok = all(k_ in z.files for k_ in ("head2.out.l1.weight", "head2.out.l3.weight", "head2.out_g", "head2.out_pick")) \
        and abs(float(z["head2.out_g"]) - OUTG) < 1e-6 and int(round(float(z["head2.out_pick"]))) == PICK and '"outlook"' in str(z["head2"])
    print("a. EXPORT: {}".format("PASS (the outlook's layers, the dials and the layout in the file)" if ok else "FAIL (the outlook or its dials not in the export)"),
          flush=True)
    return ok


def play(a):
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import keep21_simtest as ks_
    ev = ks_.cmd_env(a.cmd, os.environ.get("QLBOT_ROOT") or ROOT)
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))
    import importlib
    import csv
    E = importlib.import_module("duel_env_ffa")
    import test_suite as T
    import btoken as BT
    import head2 as H2
    p1, p0 = os.path.join(a.work, "out.pt"), os.path.join(a.work, "out0.pt")
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    pol = T.Policy(p1, seed=0)
    assert pol.goal_on and abs(pol.held_g - SHARE) < 1e-6 and pol.out_on and pol.out_pick == PICK, "out.pt: the outlook not read"
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
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[])
    tsz, tn = 0.0, 0
    for t in range(a.frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, a.map)
        xl = env.legs_prep() if pol.needs_xl else None
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        assert ac.shape[1] == len(pol.dims) + 1, "no keep column"
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac)):
            rec[k_].append(None if v_ is None else np.array(v_).copy())
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        obs, r_, done, info = env.step(act)
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    print("b. PLAY {} frames x {} seats on {}, out.pt (out_g {}, kind {}): played".format(a.frames, n, a.map, OUTG, PICK), flush=True)
    okb = True
    # c. the checks' player again and the plugins' pass on the same frames
    pol2 = T.Policy(p1, seed=0)
    h2 = pol2.zeros(n)
    import netpass as N
    P, A = N.load(os.path.join(a.work, "out.npz"))
    assert abs(N.held_g(P) - SHARE) < 1e-6 and N.goal_on(P) and N.column_on(P) and abs(N.pull_g(P) - PULL) < 1e-6 and N.out_on(P), "out.npz: not read"
    assert abs(N.out_g(P) - OUTG) < 1e-6 and P["_out"]["pick"] == PICK, "out.npz: the dials"
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    bad, first = dict(replay=0, act=0, col=0, H=0, plan=0), {}
    for t in range(a.frames):
        o_ = rec["obs"][t]
        ac2, h2 = pol2.act(o_[:, idx], h2, xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        for k_, c_ in (("replay", not np.array_equal(ac2, rec["act"][t])), ("act", not np.array_equal(acn, ac2[:, :-1])),
                       ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])), ("H", not np.array_equal(hn, h2)),
                       ("plan", not np.array_equal(P["_plan"]["odds"], pol2.pl_odds))):
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    okc = not any(bad.values())
    print("c. SERVER = CHECKS at out_g {} over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, memory {}, "
          "the plan's held odds {}{}: {}".format(OUTG, a.frames, bad["replay"], bad["act"], bad["col"], bad["H"], bad["plan"],
                                                  " (first: {})".format(first) if first else "", "PASS" if okc else "FAIL"), flush=True)
    # c2. the term moves his play: out.pt at out_g 1.0 against itself at out_g 0 on the same frames (information)
    pa_, pb_ = T.Policy(p1, seed=0), T.Policy(p1, seed=0)
    pb_.set_out_g(0.0)
    ha_, hb_ = pa_.zeros(n), pb_.zeros(n)
    dd_ = 0
    for t in range(a.frames):
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        x1_, ha_ = pa_.act(rec["obs"][t][:, idx], ha_, **kw)
        x2_, hb_ = pb_.act(rec["obs"][t][:, idx], hb_, **kw)
        dd_ += int(not np.array_equal(x1_, x2_))
        if rec["clr"][t].any():
            pa_.clear(ha_, rec["clr"][t])
            pb_.clear(hb_, rec["clr"][t])
    print("c2. for information: out.pt at out_g {} against out_g 0 on the same frames: {} of {} frames differ (the term acts)".format(OUTG, dd_, a.frames),
          flush=True)
    okc = okc and dd_ > 0
    # d. out_g 0: as the source file
    okd = True
    for nm_, fl_, pg_, hg_ in (("out0.pt, the files' own pull and held share", p0, None, None), ("out0.pt, pull {} held share {}".format(PULL, SHARE), p0, PULL, SHARE),
                               ("out.pt at out_g 0 (its non-zero layer silent), pull {} held share {}".format(PULL, SHARE), p1, PULL, SHARE)):
        pg0, ps = T.Policy(fl_, seed=0), T.Policy(a.src, seed=0)
        pg0.set_out_g(0.0)
        assert pg0.outW is not None and ps.outW is None
        if pg_ is not None:
            for p_ in (pg0, ps):
                p_.set_pull_g(pg_)
                p_.held_g = hg_
        else:
            pg0.held_g = ps.held_g
            pg0.set_pull_g(ps.pull_g)
        hg, hs = pg0.zeros(n), ps.zeros(n)
        dd, dh, mh = 0, 0, 0.0
        for t in range(a.frames):
            o_ = rec["obs"][t][:, idx]
            kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t])
            a1, hg = pg0.act(o_, hg, kf=rec["kf"][t], **kw)
            a2, hs = ps.act(o_, hs, kf=rec["kf"][t], **kw)
            dd += int(not np.array_equal(a1, a2))
            dh += int(not np.array_equal(hg, hs))
            mh = max(mh, float(np.abs(hg - hs).max()))
            if rec["clr"][t].any():
                pg0.clear(hg, rec["clr"][t])
                ps.clear(hs, rec["clr"][t])
        print("d. OUT_G 0 = THE SOURCE FILE ({}) over {} frames: frames with a difference in the actions or the keep column {}, in the memory "
              "{} (largest {:.2e}): {}".format(nm_, a.frames, dd, dh, mh, "PASS" if dd == 0 and dh == 0 else "FAIL"), flush=True)
        okd = okd and dd == 0 and dh == 0
    return okb and okc and okd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="a 2.1d save (the slow plan inside its head, the goal part)")
    ap.add_argument("--work", required=True)
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.1", "2.1d", "train.cmd"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--legs", default="move_v17_look", help="the movement network's run (the export's --legs: a network with LEGS=1)")
    ap.add_argument("--skip-make", action="store_true", help="the files of a. are in --work already (a second map)")
    a = ap.parse_args()
    ok = True if a.skip_make else make(a)
    ok = play(a) and ok
    print("ALL PASSED" if ok else "FAILED", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

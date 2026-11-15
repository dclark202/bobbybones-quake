"""2.1d: the pull end to end outside the trainer, in the real simulator (docs/runs/2.1/2.1d; made from tools/run/held_playtest.py).

  a. MAKE: tools/plan_init.py add <a 2.1c save> -> pull0.pt (the plan inside the head, pull 0); the same with the held share 0.5 -> pull0h.pt;
     the same with the held share 0.5 and the pull 1.0 -> pull.pt (if the source's plan is near even odds, its last layer moved by a fixed-seed
     random so the pull does something: said); sim/export_duel.py -> pull.npz (the plan's layers, the strength and the layout in the file).
  b. PLAY: pull0h.pt and pull.pt on every seat of a few matches through test_suite.Policy with the keep rows and the trip-end column, the
     same seeds: the changes of target a seat-minute on held trips (at a trip's end, mid-trip) and on lock trips, at pull 0 and at pull 1.0.
  c. SERVER = CHECKS at pull 1.0: pull.pt's recorded frames replayed through test_suite.Policy (seed 0) and through plugins/netpass.py on the
     export: the actions, the keep column, the whole memory array and the plan's held odds, frame by frame: 0 differences.
  d. PULL 0 = THE SOURCE FILE: pull0.pt against <src> on the same frames, both with the keep rows: 0 differences in the actions and the column.

    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/run/pull_playtest.py --src <2.1c save> --work <a scratch folder>
One simulator in this process. Nothing deleted."""
import argparse
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    # this checkout: its sim/, plugins/, tools/
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")                       # the data: the main checkout's in a worktree
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SHARE, PULL = 0.5, 1.0


def make(a):
    import torch
    os.makedirs(a.work, exist_ok=True)
    p0 = os.path.join(a.work, "pull0.pt")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "plan_init.py"), "add", a.src, p0], capture_output=True, text=True, creationflags=NOWIN)
    print(r.stdout.strip(), flush=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit("plan_init add failed")
    ck = torch.load(p0, weights_only=False, map_location="cpu")
    ck["model"]["head2.held_g"] = torch.tensor(SHARE)
    torch.save(ck, os.path.join(a.work, "pull0h.pt"))
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import head2 as H2
    W = H2.params_np({k_: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")})
    S = int(ck["head2"]["size"])
    rs_ = np.random.default_rng(5)
    hs_ = np.concatenate([np.zeros((1, S + 1), np.float32), rs_.uniform(-1, 1, (255, S + 1)).astype(np.float32)])
    od_ = H2.np_plan_odds(H2.np_plan_params(W), ck["head2"], hs_)
    spread = float((od_.max(-1) - od_.min(-1)).mean())
    moved = spread < 0.05
    if moved:                                                # (near even odds: the last layer moved by a fixed-seed random)
        g_ = torch.Generator().manual_seed(2121)
        w_ = ck["model"]["head2.plan.l3.weight"]
        ck["model"]["head2.plan.l3.weight"] = w_ + torch.randn(w_.shape, generator=g_) * (2.0 / float(w_.shape[1]) ** 0.5)
    ck["model"]["head2.pull_g"] = torch.tensor(PULL)
    p1 = os.path.join(a.work, "pull.pt")
    torch.save(ck, p1)
    print("a. the source's plan: the odds' spread (largest less smallest, mean over 256 head states) {:.4f}: {}".format(
        spread, "NEAR EVEN: its last layer moved by a fixed-seed random for pull.pt" if moved else "not even: pull.pt keeps the source's plan"), flush=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "pull_playtest", "--policy", os.path.abspath(p1),
                        "--out", os.path.join(a.work, "pull.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1500:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(os.path.join(a.work, "pull.npz"))
    ok = "head2.pull_g" in z.files and abs(float(z["head2.pull_g"]) - PULL) < 1e-6 and "head2.plan.l3.weight" in z.files \
        and abs(float(z["head2.held_g"]) - SHARE) < 1e-6 and '"slowplan"' in str(z["head2"])
    print("a. EXPORT: {}".format("PASS (the plan's layers, the pull {} and the held share {} in the file)".format(PULL, SHARE) if ok else
                                 "FAIL (the plan, the pull or the layout not in the export)"), flush=True)
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
    p1, p0h = os.path.join(a.work, "pull.pt"), os.path.join(a.work, "pull0h.pt")
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]

    def one(path, keep_rec):
        pol = T.Policy(path, seed=0)
        assert pol.goal_on and abs(pol.held_g - SHARE) < 1e-6 and pol.keep_on and pol.planW is not None, path + ": the held share or the plan not read"
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
        cnt = np.zeros((2, 3))                               # [lock, held] x (seat-frames alive, changes of target, of them at a trip's end)
        for t in range(a.frames):
            kf = H2.np_kf_end(env)
            pz, zz = BT.pose_from_env(env, a.map)
            xl = env.legs_prep() if pol.needs_xl else None
            ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
            assert ac.shape[1] == len(pol.dims) + 1, "no keep column"
            act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
            if keep_rec:
                for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac)):
                    rec[k_].append(None if v_ is None else np.array(v_).copy())
            if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
                env.legs_lg = pol.legs_logits(env.legs_prep())
            was, on, te = env.intent[:n].copy(), pol.hd_on.copy(), kf[:, -1] > 0
            obs, r_, done, info = env.step(act)
            alive = env.hp[:n] > 0
            chg = env.intent[:n] != was
            for j_, m_ in ((0, ~on), (1, on)):
                cnt[j_] += ((m_ & alive).sum(), (m_ & chg).sum(), (m_ & chg & te).sum())
            d = np.asarray(done, bool).copy()
            rec["clr"].append(d)
            if d.any():
                pol.clear(h, d)
        return cnt, rec, idx, n

    pm = lambda c_, j_, k_: c_[j_, k_] / max(1.0, c_[j_, 0]) * 2400.0    # noqa: E731
    c0, _, _, _ = one(p0h, False)
    c1, rec, idx, n = one(p1, True)
    kc = np.array([x_[:, -1] for x_ in rec["act"]])
    sh = float(((kc & 2) > 0).mean())
    for nm_, c_ in (("PULL 0", c0), ("PULL {}".format(PULL), c1)):
        print("b. PLAY {} frames x {} seats on {}, {}: changes of target a seat-minute ON THE HELD DRAW {:.1f} ({:.1f} at a trip's end, {:.1f} MID-TRIP); "
              "on the lock {:.1f} ({:.1f} mid-trip); held seat-minutes {:.1f}".format(
                  a.frames, n, a.map, nm_, pm(c_, 1, 1), pm(c_, 1, 2), pm(c_, 1, 1) - pm(c_, 1, 2), pm(c_, 0, 1), pm(c_, 0, 1) - pm(c_, 0, 2),
                  c_[1, 0] / 2400.0), flush=True)
    okb = 0.3 < sh < 0.7 and int(((kc & 4) > 0).sum()) > 0
    print("b. the coin on {:.3f} of pull.pt's seat-frames, keep readings {}: {}".format(sh, int(((kc & 4) > 0).sum()), "PASS" if okb else "FAIL"), flush=True)
    # c. the checks' player again and the plugins' pass on the same frames, at pull 1.0
    pol2 = T.Policy(p1, seed=0)
    h2 = pol2.zeros(n)
    import netpass as N
    P, A = N.load(os.path.join(a.work, "pull.npz"))
    assert abs(N.held_g(P) - SHARE) < 1e-6 and N.goal_on(P) and N.column_on(P) and abs(N.pull_g(P) - PULL) < 1e-6 and N.pull_on(P), "pull.npz: not read"
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
    print("c. SERVER = CHECKS at pull {} over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, memory {}, the plan's "
          "held odds {}{}: {}".format(PULL, a.frames, bad["replay"], bad["act"], bad["col"], bad["H"], bad["plan"],
                                      " (first: {})".format(first) if first else "", "PASS" if okc else "FAIL"), flush=True)
    # d. pull 0: as the source file
    pg0, ps = T.Policy(os.path.join(a.work, "pull0.pt"), seed=0), T.Policy(a.src, seed=0)
    assert pg0.planW is not None and pg0.pull_g == 0 and ps.planW is None and pg0.held_g == ps.held_g
    hg, hs = pg0.zeros(n), ps.zeros(n)
    dd = 0
    for t in range(a.frames):
        o_ = rec["obs"][t][:, idx]
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t])
        a1, hg = pg0.act(o_, hg, kf=rec["kf"][t], **kw)
        a2, hs = ps.act(o_, hs, kf=rec["kf"][t], **kw)
        dd += int(not np.array_equal(a1, a2)) + int(not np.array_equal(hg, hs))
        if rec["clr"][t].any():
            pg0.clear(hg, rec["clr"][t])
            ps.clear(hs, rec["clr"][t])
    print("d. PULL 0 = THE SOURCE FILE over {} frames: frames with a difference in the actions, the keep column or the memory: {}: {}".format(
        a.frames, dd, "PASS" if dd == 0 else "FAIL"), flush=True)
    return okb and okc and dd == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="a 2.1c save with its plan (top-level 'plan')")
    ap.add_argument("--work", required=True)
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.1", "2.1c", "train.cmd"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=2400)
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

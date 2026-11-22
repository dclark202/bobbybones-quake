"""2.1e: the head's slow halves end to end outside the trainer, in the real simulator (docs/runs/2.1/2.1e; made from tools/run/pull_playtest.py).

  a. MAKE: tools/slow_init.py add <a 2.1d save> -> slow0.pt (the halves inside the head: mix 0, back 0, pick 1); the same with the held share
     0.5, the pull 1.0, mix 0.5, back 0.5, the three halves' last layers and the read-back's columns made non-zero by a fixed-seed random (the
     test only: so that the halves' odds are not even and the read-back acts) -> slow.pt; sim/export_duel.py -> slow.npz (the halves' layers and
     the dials in the file).
  b. PLAY: slow.pt on every seat of a few matches through test_suite.Policy with the keep rows and the trip-end column: the picked half's ticks
     by cause (clock, the roll moment, a change of mind) and the changes of target a seat-minute.
  c. SERVER = CHECKS at mix 0.5, back 0.5: slow.pt's recorded frames replayed through test_suite.Policy (seed 0) and through plugins/netpass.py
     on the export: the actions, the keep column, the whole memory array, the plan's held odds, the slow half's state and odds, frame by frame: 0
     differences.
  d. MIX 0, BACK 0 = THE SOURCE FILE: slow0.pt against <src> on the same frames, both with the keep rows, at the file's own pull and held share
     and again at pull 1.0 and held share 0.5 on both: 0 differences in the actions, the keep column and the memory.

    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/run/slow_playtest.py --src <2.1d save> --work <a scratch folder>
One simulator in this process. Nothing deleted."""
import argparse
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    # this checkout: its sim/, plugins/, tools/
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")                       # the data: the main checkout's in a worktree
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SHARE, PULL, MIX, BACK, PICK = 0.5, 1.0, 0.5, 0.5, 1


def make(a):
    import torch
    os.makedirs(a.work, exist_ok=True)
    p0 = os.path.join(a.work, "slow0.pt")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "slow_init.py"), "add", a.src, p0], capture_output=True, text=True, creationflags=NOWIN)
    print(r.stdout.strip(), flush=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit("slow_init add failed")
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import head2 as H2
    ck = torch.load(p0, weights_only=False, map_location="cpu")
    sd = ck["model"]
    sd["head2.held_g"] = torch.tensor(SHARE)
    sd["head2.pull_g"] = torch.tensor(PULL)
    sd["head2.slow_mix"] = torch.tensor(MIX)
    sd["head2.slow_back"] = torch.tensor(BACK)
    sd["head2.slow_pick"] = torch.tensor(float(PICK))
    g_ = torch.Generator().manual_seed(2125)
    for k_ in range(len(ck["head2"]["slowhalf"]["clocks"])):
        w_ = sd["head2.slow.{}.l3.weight".format(k_)]
        sd["head2.slow.{}.l3.weight".format(k_)] = torch.randn(w_.shape, generator=g_) * (2.0 / float(w_.shape[1]) ** 0.5)
    o_ = H2._offs(ck["head2"])["slowback"]
    wi_ = sd["head2.inp.weight"].clone()
    wi_[:, o_[0]:o_[1]] = torch.randn(wi_.shape[0], o_[1] - o_[0], generator=g_) * 0.05
    sd["head2.inp.weight"] = wi_
    p1 = os.path.join(a.work, "slow.pt")
    torch.save(ck, p1)
    print("a. slow.pt: held share {}, pull {}, mix {}, back {}, pick {}; the halves' last layers and the read-back's {} columns made non-zero (seed "
          "2125)".format(SHARE, PULL, MIX, BACK, PICK, o_[1] - o_[0]), flush=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "slow_playtest", "--policy", os.path.abspath(p1),
                        "--out", os.path.join(a.work, "slow.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True,
                       creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1500:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(os.path.join(a.work, "slow.npz"))
    ok = all(k_ in z.files for k_ in ("head2.slow.0.l3.weight", "head2.slow.2.gru.weight_hh", "head2.slow_mix", "head2.slow_back", "head2.slow_pick")) \
        and abs(float(z["head2.slow_mix"]) - MIX) < 1e-6 and abs(float(z["head2.slow_back"]) - BACK) < 1e-6 \
        and int(round(float(z["head2.slow_pick"]))) == PICK and '"slowhalf"' in str(z["head2"]) and '"slowback"' in str(z["head2"])
    print("a. EXPORT: {}".format("PASS (the halves' layers, the dials and the layout in the file)" if ok else "FAIL (the halves or the dials not in the export)"),
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
    p1, p0 = os.path.join(a.work, "slow.pt"), os.path.join(a.work, "slow0.pt")
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    pol = T.Policy(p1, seed=0)
    assert pol.goal_on and abs(pol.held_g - SHARE) < 1e-6 and pol.keep_on and pol.shL is not None and pol.sh_on, "slow.pt: the halves not read"
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
    cause = np.zeros(4, np.int64)                            # (the picked half's ticks: clock, roll moment, change of mind, all)
    chg_n, alive_n = 0, 0
    for t in range(a.frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, a.map)
        xl = env.legs_prep() if pol.needs_xl else None
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        assert ac.shape[1] == len(pol.dims) + 1, "no keep column"
        if pol.sh.last is not None:
            tk_, cl_, fr_, cg_ = pol.sh.last
            cause += np.array([int(cl_.sum()), int(fr_.sum()), int(cg_.sum()), int(tk_.sum())])
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac)):
            rec[k_].append(None if v_ is None else np.array(v_).copy())
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        was = env.intent[:n].copy()
        obs, r_, done, info = env.step(act)
        alive_n += int((env.hp[:n] > 0).sum())
        chg_n += int((env.intent[:n] != was).sum())
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    sm_ = alive_n / 2400.0
    okb = cause[0] > 0 and cause[1] > 0 and cause[2] > 0
    print("b. PLAY {} frames x {} seats on {}, slow.pt: the picked half (clock {} head ticks) ticked {} times: clock {}, the roll moment {}, a change "
          "of mind {} ({:.1f} ticks a seat-minute); changes of target a seat-minute {:.1f}: {}".format(
              a.frames, n, a.map, pol.shL["clocks"][PICK], cause[3], cause[0], cause[1], cause[2], cause[3] / max(sm_, 1e-9), chg_n / max(sm_, 1e-9),
              "PASS (every cause seen)" if okb else "FAIL (a cause never seen)"), flush=True)
    # c. the checks' player again and the plugins' pass on the same frames
    pol2 = T.Policy(p1, seed=0)
    h2 = pol2.zeros(n)
    import netpass as N
    P, A = N.load(os.path.join(a.work, "slow.npz"))
    assert abs(N.held_g(P) - SHARE) < 1e-6 and N.goal_on(P) and N.column_on(P) and abs(N.pull_g(P) - PULL) < 1e-6 and N.slow_on(P), "slow.npz: not read"
    assert abs(P["_shalf"]["mix"] - MIX) < 1e-6 and abs(P["_shalf"]["back"] - BACK) < 1e-6 and P["_shalf"]["pick"] == PICK, "slow.npz: the dials"
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    bad, first = dict(replay=0, act=0, col=0, H=0, plan=0, slow_s=0, slow_odds=0), {}
    for t in range(a.frames):
        o_ = rec["obs"][t]
        ac2, h2 = pol2.act(o_[:, idx], h2, xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        st_n, st_p = P["_shalf"]["st"], pol2.sh
        for k_, c_ in (("replay", not np.array_equal(ac2, rec["act"][t])), ("act", not np.array_equal(acn, ac2[:, :-1])),
                       ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])), ("H", not np.array_equal(hn, h2)),
                       ("plan", not np.array_equal(P["_plan"]["odds"], pol2.pl_odds)), ("slow_s", not np.array_equal(st_n.s, st_p.s)),
                       ("slow_odds", not np.array_equal(st_n.odds, st_p.odds))):
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    okc = not any(bad.values())
    print("c. SERVER = CHECKS at mix {}, back {} over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, memory {}, "
          "the plan's held odds {}, the slow half's state {} and odds {}{}: {}".format(
              MIX, BACK, a.frames, bad["replay"], bad["act"], bad["col"], bad["H"], bad["plan"], bad["slow_s"], bad["slow_odds"],
              " (first: {})".format(first) if first else "", "PASS" if okc else "FAIL"), flush=True)
    # d. mix 0, back 0: as the source file (at the file's own pull and held share, then at pull 1.0 and held share 0.5 on both)
    okd = True
    for nm_, pg_, hg_ in (("the files' own pull and held share", None, None), ("pull {} and held share {} on both".format(PULL, SHARE), PULL, SHARE)):
        pg0, ps = T.Policy(p0, seed=0), T.Policy(a.src, seed=0)
        assert pg0.shL is not None and pg0.sh_mix == 0 and pg0.sh_back == 0 and ps.shL is None and pg0.held_g == ps.held_g and not pg0.sh_on
        if pg_ is not None:
            for p_ in (pg0, ps):
                p_.set_pull_g(pg_)
                p_.held_g = hg_
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
        print("d. MIX 0, BACK 0 = THE SOURCE FILE ({}) over {} frames: frames with a difference in the actions or the keep column {}, in the memory "
              "{} (largest {:.2e}): {}".format(nm_, a.frames, dd, dh, mh, "PASS" if dd == 0 and dh == 0 else "FAIL"), flush=True)
        okd = okd and dd == 0 and dh == 0
    return okb and okc and okd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="a 2.1d save (the slow plan inside its head, the goal part)")
    ap.add_argument("--work", required=True)
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.1", "2.1d", "train.cmd"))
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

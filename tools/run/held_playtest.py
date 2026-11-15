"""2.1c: the held draw end to end outside the trainer, in the real simulator (docs/runs/2.1/2.1c/CARD.md).

  a. MAKE: tools/held_init.py add <src> (the head's part "goal" at zero, share 0) -> held0.pt; the same file with the share 0.5 -> held.pt;
     sim/export_duel.py -> held.npz (the share and the layout's part "goal" in the file).
  b. PLAY: held.pt on every seat of a few matches through test_suite.Policy with the keep rows and the trip-end column
     (head2.np_kf_end): about half the seat-frames under the coin; per seat-minute, the changes of target on held trips and on lock trips.
  c. SERVER = CHECKS: the recorded frames replayed through test_suite.Policy (seed 0) and through plugins/netpass.py on the export:
     the actions, the keep column and the whole memory array, frame by frame: 0 differences.
  d. SHARE 0 = THE SOURCE FILE: held0.pt against <src> on the same frames: 0 differences in the actions.

    CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/run/held_playtest.py --work <a scratch folder> [--src <policy.pt>]
One simulator in this process. Nothing deleted."""
import argparse
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SHARE = 0.5


def make(a):
    import torch
    os.makedirs(a.work, exist_ok=True)
    h0 = os.path.join(a.work, "held0.pt")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "held_init.py"), "add", a.src, h0], capture_output=True, text=True, creationflags=NOWIN)
    print(r.stdout.strip(), flush=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit("held_init add failed")
    ck = torch.load(h0, weights_only=False, map_location="cpu")
    ck["model"]["head2.held_g"] = torch.tensor(SHARE)
    h1 = os.path.join(a.work, "held.pt")
    torch.save(ck, h1)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "held_playtest", "--policy", os.path.abspath(h1),
                        "--out", os.path.join(a.work, "held.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)
    print(r.stdout.strip()[-1200:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(os.path.join(a.work, "held.npz"))
    ok = "head2.held_g" in z.files and abs(float(z["head2.held_g"]) - SHARE) < 1e-6
    print("a. EXPORT: {}".format("PASS (the share {} in the file)".format(SHARE) if ok else "FAIL (head2.held_g not in the export)"), flush=True)
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
    h1 = os.path.join(a.work, "held.pt")
    pol = T.Policy(h1, seed=0)
    assert pol.goal_on and abs(pol.held_g - SHARE) < 1e-6 and pol.keep_on, "held.pt: the part 'goal' or the share not read"
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
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[])
    gu = []                                                  # (the part "goal" as the head reads it: its measured average and spread)
    cnt = np.zeros((2, 3))                                   # [lock, held] x (seat-frames alive, changes of target, of them at a trip's end)
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
        was, on, te = env.intent[:n].copy(), pol.hd_on.copy(), kf[:, -1] > 0
        if t % 8 == 0:
            gu.append(H2.np_goal_u(pol.h2, kf[:, :-1], on))
        obs, r_, done, info = env.step(act)
        alive = env.hp[:n] > 0
        chg = env.intent[:n] != was
        for j_, m_ in ((0, ~on), (1, on)):
            cnt[j_] += ((m_ & alive).sum(), (m_ & chg).sum(), (m_ & chg & te).sum())
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    kc = np.array([x_[:, -1] for x_ in rec["act"]])
    sh = float(((kc & 2) > 0).mean())
    pm = lambda j_, k_: cnt[j_, k_] / max(1.0, cnt[j_, 0]) * 2400.0
    okb = 0.3 < sh < 0.7 and int(((kc & 4) > 0).sum()) > 0
    print("b. PLAY {} frames x {} seats on {}: the coin on {:.3f} of seat-frames, keep readings {}; changes of target a seat-minute: ON THE LOCK {:.1f} "
          "({:.1f} at a trip's end, {:.1f} mid-trip), ON THE HELD DRAW {:.1f} ({:.1f} at a trip's end, {:.1f} mid-trip): {}".format(
              a.frames, n, a.map, sh, int(((kc & 4) > 0).sum()), pm(0, 1), pm(0, 2), pm(0, 1) - pm(0, 2), pm(1, 1), pm(1, 2), pm(1, 1) - pm(1, 2),
              "PASS" if okb else "FAIL"), flush=True)
    G = np.concatenate(gu)
    nt_ = int(pol.h2["n_target"])
    print("b. THE PART 'goal' as read ({} rows): the one-hot's columns average {} (spread {:.3f} .. {:.3f}); the age (twos of seconds, cut at 10) average "
          "{:.3f} spread {:.3f} max {:.3f}, at the cut {:.4f} of rows; on the held draw average {:.3f}".format(
              len(G), [round(float(x_), 3) for x_ in G[:, :nt_].mean(0)], float(G[:, :nt_].std(0).min()), float(G[:, :nt_].std(0).max()),
              float(G[:, nt_].mean()), float(G[:, nt_].std()), float(G[:, nt_].max()), float((G[:, nt_] >= 10.0).mean()), float(G[:, nt_ + 1].mean())), flush=True)
    # c. the checks' player again and the plugins' pass on the same frames
    pol2 = T.Policy(h1, seed=0)
    h2 = pol2.zeros(n)
    import netpass as N
    P, A = N.load(os.path.join(a.work, "held.npz"))
    assert abs(N.held_g(P) - SHARE) < 1e-6 and N.goal_on(P) and N.column_on(P), "held.npz: the share or the part 'goal' not read"
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    bad, first = dict(replay=0, act=0, col=0, H=0), {}
    for t in range(a.frames):
        o_ = rec["obs"][t]
        ac2, h2 = pol2.act(o_[:, idx], h2, xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        for k_, c_ in (("replay", not np.array_equal(ac2, rec["act"][t])), ("act", not np.array_equal(acn, ac2[:, :-1])),
                       ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])), ("H", not np.array_equal(hn, h2))):
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    okc = not any(bad.values())
    print("c. SERVER = CHECKS over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, memory {}{}: {}".format(
        a.frames, bad["replay"], bad["act"], bad["col"], bad["H"], " (first: {})".format(first) if first else "", "PASS" if okc else "FAIL"), flush=True)
    # d. share 0: as the source file
    pg0, ps = T.Policy(os.path.join(a.work, "held0.pt"), seed=0), T.Policy(a.src, seed=0)
    assert pg0.goal_on and pg0.held_g == 0
    hg, hs = pg0.zeros(n), ps.zeros(n)
    dd = 0
    for t in range(a.frames):
        o_ = rec["obs"][t][:, idx]
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t])
        a1, hg = pg0.act(o_, hg, kf=rec["kf"][t], **kw)
        a2, hs = ps.act(o_, hs, **kw)
        dd += int(not np.array_equal(a1[:, :a2.shape[1]], a2)) + int((a1[:, -1] & 3).any())
        if rec["clr"][t].any():
            pg0.clear(hg, rec["clr"][t])
            ps.clear(hs, rec["clr"][t])
    print("d. SHARE 0 = THE SOURCE FILE over {} frames: frames with a difference in the actions or a coin in the column: {}: {}".format(
        a.frames, dd, "PASS" if dd == 0 else "FAIL"), flush=True)
    return okb and okc and dd == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(DATA, "sim_runs", "duel_gru_2_0e", "keep", "policy_end_20e.pt"))
    ap.add_argument("--work", required=True)
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.1", "2.1c", "train.cmd"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=2400)
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--legs", default="move_v17_look", help="the movement network's run (the export's --legs: a network with LEGS=1)")
    a = ap.parse_args()
    ok = make(a)
    ok = play(a) and ok
    print("ALL PASSED" if ok else "FAILED", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

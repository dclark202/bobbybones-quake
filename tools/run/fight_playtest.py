"""2.2c's aggression lever (sim/fightnet.py VERSION_LEVER) on a server: the plugin's pass against the checks' player, in the real simulator
(made from tools/run/out_playtest.py and tools/run/play22.py; the network: 2.2e's end, or any save with the lever).

  a. EXPORT: sim/export_duel.py <src> -> fight.npz: the lever's layout (its measured norm, its dials) and its layers in the file; with
     --refuse <a 2.2b save> (four fight options, layout version 1) the export must still refuse it.
  b. PLAY (the checks' player drives): <src> on every seat of a few matches through test_suite.Policy (seed 0) with the keep rows and the
     trip-end column, as tools/duel_eval.py feeds it: after each act() the lever's add to the simulator (env.fg_score: the hands' inputs
     "b22b fight") and the brain's answer with its places ahead (env.brain_in: BRAIN_READ's readers and AHEAD_IN's inputs). Every frame
     recorded.
  c. SERVER = CHECKS: the recorded frames replayed through test_suite.Policy (seed 0) and through plugins/netpass.py on the export (rng seed
     0), frame by frame: the actions, the keep column, the whole memory array, the plan's held odds, the lever's held number, the lever's
     inputs and outputs at every keep reading, his target logits as drawn (the lever in them), what the plugin gives the simulator after the
     frame (netpass.fight_scores = Policy.fight_scores; netpass.brain_answer with "fut" = Policy.brain_answer): 0 differences.
  d. THE PLUGIN DRIVES: netpass on every seat drives the simulator with plugins/duelbot.py's feeding (fight_scores -> env.fg_score,
     brain_feed -> the brain's answer and its places ahead); its frames replayed through test_suite.Policy: 0 differences (actions, keep
     column, memory, the lever, the feeds).
  e. For information: the lever's numbers (keep readings, its add's spread, how often "the enemy" is the drawn target), and the same frames
     at LEV_G 0 against LEV_G 1 (frames whose actions differ: the lever acts).

    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \\
        python tools/run/fight_playtest.py --src <a save with the lever> --cmd <its train.cmd> --work <a scratch folder> [--maps bloodrun,aerowalk]

The simulator's switches: the run's command's `set` lines, then the export's env_vars over them (what a server sets), the rail drill and the
fight starts off (RDRILL_P 0, FIGHT_START_P 0: never in a real game). One simulator module in this process. Nothing deleted."""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    # this checkout: its sim/, plugins/, tools/
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")                       # the data: the main checkout's in a worktree
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def export(a, src, out):
    return subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "fight_playtest", "--policy", os.path.abspath(src),
                           "--out", out, "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)


def make(a):
    os.makedirs(a.work, exist_ok=True)
    out = os.path.join(a.work, "fight.npz")
    r = export(a, a.src, out)
    print(r.stdout.strip()[-1200:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("export failed")
    z = np.load(out)
    fj = json.loads(str(z["fight22"])) if "fight22" in z.files else {}
    ok = bool(fj) and int(fj["layout"]["version"]) == 2 and fj["layout"].get("norm") is not None \
        and all("fight22.l{}.{}".format(i_, w_) in z.files for i_ in (1, 2, 3) for w_ in ("weight", "bias"))
    print("a. EXPORT: {} (the lever's layout v{}, {} inputs, LEV_G {}, its layers in the file)".format(
        "PASS" if ok else "FAIL", fj.get("layout", {}).get("version"), fj.get("layout", {}).get("width"), (fj.get("dials") or {}).get("LEV_G")), flush=True)
    if a.refuse:
        r = export(a, a.refuse, os.path.join(a.work, "refused.npz"))
        rf_ = r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr) and not os.path.exists(os.path.join(a.work, "refused.npz"))
        print("a2. EXPORT of {} (2.2b's four options): {}".format(os.path.basename(a.refuse), "REFUSED as it must be: PASS" if rf_ else "NOT REFUSED: FAIL"),
              flush=True)
        ok = ok and rf_
    return ok


def setup(a):
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import keep21_simtest as ks_
    ev = ks_.cmd_env(a.cmd, os.environ.get("QLBOT_ROOT") or ROOT)
    z = np.load(os.path.join(a.work, "fight.npz"))
    ev.update(json.loads(str(z["env_vars"])))               # (what the plugin sets before it loads the simulator: duelbot.env_module)
    ev.update(RDRILL_P="0", FIGHT_START_P="0")              # (training's own rounds: never in a real game)
    os.environ.update({k_: str(v_) for k_, v_ in ev.items()})
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))


def make_env(E, T, pol, mp, matches, seed=7):
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if getattr(E, "BRAIN_READ", False):                      # (as tools/duel_eval.py: the simulator's readers on the brain's answer, every
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))   # life drawn at the network's fade)
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    return env


def col_idx(pol):
    import csv
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    return np.array([now.index(tuple(x_)) for x_ in pol.names]) if pol.names else np.arange(len(pol.mean))


def ans_full(E, n, an_):
    """tools/duel_eval.py's answer of every seat for env.brain_in (zeros where a seat has none)"""
    ans_ = dict(bel=np.zeros((n, 3), np.float32), ok=np.zeros(n, bool), band=np.zeros((n, 4), np.float32), ztop=np.full(n, -1, np.int16))
    if getattr(E, "COMBAT", False) or getattr(E, "AHEAD_IN", False):
        ans_["fut"] = np.zeros((n, 3, 3), np.float32)
    if an_ is not None:
        for k_ in ans_:
            if k_ in an_:
                ans_[k_][:] = an_[k_]
    return ans_


def same_ans(a1, a2):
    """two brain answers (dicts) equal, key by key (None = None)"""
    if a1 is None or a2 is None:
        return a1 is None and a2 is None
    return sorted(a1) == sorted(a2) and all(np.array_equal(np.asarray(a1[k_]), np.asarray(a2[k_])) for k_ in a1)


def play_policy(E, T, pol, env, mp, frames):
    """b: the checks' player on every seat, fed as tools/duel_eval.py feeds it; every frame recorded"""
    import head2 as H2
    import btoken as BT
    idx = col_idx(pol)
    n, nA = env.n, len(E.ACTION_DIMS)
    obs = env.observe()
    h = pol.zeros(n)
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[], fs=[], ans=[], lev=[], tl=[], kr=[])
    for t in range(frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, mp)
        xl = env.legs_prep() if pol.needs_xl else None
        rec["kr"].append(None if pol.k_r is None else np.asarray(pol.k_r, bool).copy())
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        fs_ = pol.fight_scores()
        if fs_ is not None:                                  # (2.2b, 2.2c) the hands' inputs of the next frame (tools/duel_eval.py)
            env.fg_score = np.asarray(fs_, np.float32).copy()
        an_ = pol.brain_answer(h)
        if getattr(E, "BRAIN_READ", False):                  # (the brain's answer and its places ahead to the simulator, tools/duel_eval.py)
            env.brain_in(ans_full(E, n, an_))
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac), ("fs", fs_), ("lev", pol.fg_lev),
                       ("tl", getattr(pol, "last_target_logits", None))):
            rec[k_].append(None if v_ is None else np.array(v_).copy())
        rec["ans"].append(an_)
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        obs, r_, done, info = env.step(act)
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    return rec


def play_plugin(E, N, P, A, env, mp, frames, pol_names):
    """d: netpass on every seat drives the simulator, fed as plugins/duelbot.py feeds it (act(): step(), brain_feed, fight_scores ->
    env.fg_score); every frame recorded"""
    import btoken as BT
    import csv
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    assert [tuple(x_) for x_ in json.loads(str(P["input_names"]))] == [tuple(x_) for x_ in pol_names]
    n, nA = env.n, len(E.ACTION_DIMS)
    obs = env.observe()
    hn = np.zeros((n, N.width(P)), np.float32)
    rng = np.random.default_rng(0)
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[], fs=[], ans=[], lev=[], tl=[], col=[])
    for t in range(frames):
        kf = N.kf_rows(P, env) if N.column_on(P) else None
        pz, zz = BT.pose_from_env(env, mp) if N.needs_pose(P) else (None, None)
        xl = env.legs_prep() if N.needs_xl(P) else None
        acn, hn = N.step(P, A, np.asarray(obs, np.float32), hn, rng, xl=xl, pose=pz, zmap=zz, **({"kf": kf} if kf is not None else {}))
        N.brain_feed(P, env, hn, np.arange(n))               # (duelbot.act: the brain's answer, its places ahead, to the simulator)
        fs_ = N.fight_scores(P)
        if fs_ is not None:                                  # (duelbot.act: the lever's add, the hands' inputs of the next frame)
            env.fg_score = np.asarray(fs_, np.float32).copy()
        col_ = np.asarray(P["_keep"], np.int64) if P.get("_keep") is not None else np.full(n, -1, np.int64)
        act = np.concatenate([acn[:, :nA], col_[:, None]], 1)
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", acn), ("fs", fs_), ("lev", P["_fgt"]["lev"]),
                       ("tl", P.get("_target_logits")), ("col", col_)):
            rec[k_].append(None if v_ is None else np.array(v_).copy())
        rec["ans"].append(N.brain_answer(P, hn))
        if getattr(E, "LEGS_IN", False) and "legs_w0" in P:
            N.legs_feed(P, env, E, rows=np.arange(n))
        obs, r_, done, info = env.step(act)
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            N.clear(P, hn, d)
    return rec


def replay(a, E, T, N, rec, idx, n, label, drove):
    """the recorded frames through a fresh test_suite.Policy (seed 0) and a fresh netpass load (rng seed 0): every difference counted"""
    pol2 = T.Policy(a.src, seed=0)
    h2 = pol2.zeros(n)
    P, A = N.load(os.path.join(a.work, "fight.npz"))
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    keys = ("rec", "act", "col", "H", "plan", "lev", "lev_in", "lev_out", "tlog", "fs", "ans")
    bad, first = {k_: 0 for k_ in keys}, {}
    nread, lev_in_max = 0, 0.0
    for t in range(len(rec["obs"])):
        o_ = rec["obs"][t]
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        pol2.fg_last = None
        P["_fgt"]["last"] = None
        ac2, h2 = pol2.act(o_[:, idx], h2, **kw)
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        fl2, fln = pol2.fg_last, P["_fgt"]["last"]
        rd_ = fl2 is not None or fln is not None
        if rd_:
            nread += 0 if fl2 is None else len(fl2[0])
        lin_ = rd_ and not (fl2 is not None and fln is not None and np.array_equal(fl2[0], fln[0]) and np.array_equal(fl2[1]["x"], fln[1]["x"])
                            and np.array_equal(fl2[1]["trk"], fln[1]["trk"]))
        lout_ = rd_ and not (fl2 is not None and fln is not None and np.array_equal(fl2[1]["lev"], fln[1]["lev"]) and np.array_equal(fl2[1]["V"], fln[1]["V"]))
        if rd_ and fl2 is not None and fln is not None and fl2[1]["x"].shape == fln[1]["x"].shape:
            lev_in_max = max(lev_in_max, float(np.abs(fl2[1]["x"] - fln[1]["x"]).max()) if fl2[1]["x"].size else 0.0)
        if drove == "plugin":                                # (the plugin's own frames: what it played and fed then = the replays)
            rec_bad = not np.array_equal(rec["act"][t], acn) or not np.array_equal(rec["col"][t], ac2[:, -1])                 or not np.array_equal(rec["fs"][t], pol2.fight_scores()) or not same_ans(rec["ans"][t], pol2.brain_answer(h2))
        else:                                                # (the checks' player's own frames and feeds = the replays')
            rec_bad = not np.array_equal(ac2, rec["act"][t]) or not np.array_equal(rec["fs"][t], N.fight_scores(P))                 or not same_ans(rec["ans"][t], N.brain_answer(P, hn)) or not np.array_equal(rec["lev"][t], P["_fgt"]["lev"])
        checks = (("rec", rec_bad),
                  ("act", not np.array_equal(acn, ac2[:, :-1])),
                  ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])),
                  ("H", not np.array_equal(hn, h2)),
                  ("plan", not np.array_equal(P["_plan"]["odds"], pol2.pl_odds)),
                  ("lev", not np.array_equal(P["_fgt"]["lev"], pol2.fg_lev)),
                  ("lev_in", lin_), ("lev_out", lout_),
                  ("tlog", not np.array_equal(P.get("_target_logits"), getattr(pol2, "last_target_logits", None))),
                  ("fs", not np.array_equal(N.fight_scores(P), pol2.fight_scores())),
                  ("ans", not same_ans(N.brain_answer(P, hn), pol2.brain_answer(h2))))
        for k_, c_ in checks:
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    ok = not any(bad.values())
    print("{} over {} frames x {} seats ({} keep-reading rows): frames with a difference: recording {}, actions {}, keep column {}, memory {}, the "
          "plan's held odds {}, the lever held {}, the lever's inputs {} (largest {:.1e}), its outputs {}, target logits as drawn {}, the lever's add "
          "to the simulator {}, the brain's answer with its places ahead {}{}: {}".format(
              label, len(rec["obs"]), n, nread, bad["rec"], bad["act"], bad["col"], bad["H"], bad["plan"], bad["lev"], bad["lev_in"], lev_in_max,
              bad["lev_out"], bad["tlog"], bad["fs"], bad["ans"], " (first: {})".format(first) if first else "", "PASS" if ok else "FAIL"), flush=True)
    return ok, nread


def info(E, T, a, rec, idx, n, nA):
    """e: the lever's numbers on the recorded frames; LEV_G 0 against LEV_G 1 on the same frames"""
    import csv
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    c_fs = now.index(("b22b fight", "fight network's score: at him"))
    c_ah = now.index(("b22c ahead", "the brain's places ahead: there is an answer"))
    ob_ = np.stack([np.asarray(o_, np.float32) for o_ in rec["obs"]])
    print("e. for information: the hands' inputs the plugin must feed, in the recorded frames: the lever's column non-zero in {:.1%} of "
          "seat-frames (largest {:.3f}), the brain's places ahead answered in {:.1%}".format(
              float(np.mean(ob_[..., c_fs] != 0)), float(np.abs(ob_[..., c_fs]).max()), float(np.mean(ob_[..., c_ah] > 0))), flush=True)
    lv_ = np.concatenate([np.asarray(f_)[:, 0] for f_ in rec["fs"] if f_ is not None]) if any(f_ is not None for f_ in rec["fs"]) else np.zeros(1)
    tg_ = np.concatenate([np.asarray(x_)[:, 10] for x_ in rec["act"]])
    pa_, pb_ = T.Policy(a.src, seed=0), T.Policy(a.src, seed=0)
    pb_.set_fight(g=0.0)
    ha_, hb_ = pa_.zeros(n), pb_.zeros(n)
    dd_ = dt_ = 0
    for t in range(len(rec["obs"])):
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        x1_, ha_ = pa_.act(rec["obs"][t][:, idx], ha_, **kw)
        x2_, hb_ = pb_.act(rec["obs"][t][:, idx], hb_, **kw)
        dd_ += int(not np.array_equal(x1_, x2_))
        dt_ += int(not np.array_equal(x1_[:, 10], x2_[:, 10]))
        if rec["clr"][t].any():
            pa_.clear(ha_, rec["clr"][t])
            pb_.clear(hb_, rec["clr"][t])
    print("e. for information: the lever's add as played (LEV_G {}) over the frames: mean {:+.3f}, spread {:.3f}, range {:+.3f} .. {:+.3f}; "
          "'the enemy' the drawn target in {:.1%} of seat-frames; LEV_G 0 against LEV_G {} on the same frames: {} of {} frames differ in an "
          "action, {} in the target".format(pa_.lev_g, float(lv_.mean()), float(lv_.std()), float(lv_.min()), float(lv_.max()),
                                            float(np.mean(tg_ == 8)), pa_.lev_g, dd_, len(rec["obs"]), dt_), flush=True)


def play(a):
    setup(a)
    import importlib
    E = importlib.import_module("duel_env_ffa")
    import test_suite as T
    import netpass as N
    assert getattr(E, "FIGHT", False) and getattr(E, "AHEAD_IN", False), "the simulator's switches: FIGHT and AHEAD_IN expected on (the export's env_vars)"
    pol = T.Policy(a.src, seed=0)
    assert pol.fgt is not None and pol.lever and pol.ahead_in, "the source has no lever or no places ahead in its list"
    P0, _ = N.load(os.path.join(a.work, "fight.npz"))
    assert N.lever_on(P0) and P0["_ahead_in"] and abs(N.lev_g(P0) - pol.lev_g) < 1e-9, "fight.npz: the lever not read"
    print("the lever: LEV_G {} (the file's dials), its inputs {}; the strategy head live {}; held share {}, pull {}; the brain's places ahead in "
          "his list; the simulator: FIGHT {}, AHEAD_IN {}, BRAIN_READ {}, FG_IN_G {}; aim: react {} ms, acquire {} ms, PERCEPT_SIGMA {}".format(
              pol.lev_g, pol.fgt.L["width"], pol.h2_live, pol.held_g, pol.pull_g, E.FIGHT, E.AHEAD_IN, getattr(E, "BRAIN_READ", None),
              getattr(E, "FG_IN_G", None), pol.react_ms, pol.acquire_ms, getattr(E, "PERCEPT_SIGMA", None)), flush=True)
    ok = True
    for mp in a.maps.split(","):
        pol = T.Policy(a.src, seed=0)
        idx = col_idx(pol)
        env = make_env(E, T, pol, mp, a.matches)
        rec = play_policy(E, T, pol, env, mp, a.frames)
        n, nA = env.n, len(E.ACTION_DIMS)
        print("b. PLAY {} frames x {} seats on {}: the checks' player drove (fed as tools/duel_eval.py)".format(a.frames, n, mp), flush=True)
        okc, nr_ = replay(a, E, T, N, rec, idx, n, "c. SERVER = CHECKS on {}".format(mp), "policy")
        ok = ok and okc and nr_ > 0
        P, A = N.load(os.path.join(a.work, "fight.npz"))
        pol_d = T.Policy(a.src, seed=0)
        env = make_env(E, T, pol_d, mp, a.matches, seed=11)
        recd = play_plugin(E, N, P, A, env, mp, a.frames, pol_d.names)
        print("d. PLAY {} frames x {} seats on {}: the plugin's pass drove (fed as plugins/duelbot.py)".format(a.frames, n, mp), flush=True)
        okd, nr_d = replay(a, E, T, N, recd, idx, n, "d. THE PLUGIN DRIVES, the checks' player replays, on {}".format(mp), "plugin")
        ok = ok and okd and nr_d > 0
        info(E, T, a, rec, idx, n, nA)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="a save with the aggression lever (2.2c on: 2.2e's keep/policy_end_22e.pt)")
    ap.add_argument("--cmd", required=True, help="its run's train.cmd (the simulator's switches; the export's env_vars over them)")
    ap.add_argument("--work", required=True)
    ap.add_argument("--maps", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--legs", default="move_v17_look", help="the movement network's run (the export's --legs: a network with LEGS=1)")
    ap.add_argument("--refuse", default="", help="a 2.2b save (four fight options): its export must still be refused")
    ap.add_argument("--skip-make", action="store_true", help="fight.npz is in --work already")
    a = ap.parse_args()
    ok = True if a.skip_make else make(a)
    ok = play(a) and ok
    print("ALL PASSED" if ok else "FAILED", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

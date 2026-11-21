"""2.2b's tests (the brief's list; every one prints its numbers and PASS or FAIL; exit 1 on a failure). Scratch only: the scratchpad or
data/sim_runs/scratch_22b_*; nothing deleted.
    guard   the judge's guard refuses: (a) WIN_ADD 0.33 without JUDGE_PAY; (b) JUDGE_PAY with an items' fit not accepted; (c) one that does not
            exist; accepts (d) the judge with an accepted fit and (e) no win-chance pay; tools/run/check_settings.py refuses 2.2a's command and
            passes 2.2b's on the guard; tools/run/make_train_cmd.py refuses an old-form command with the item-blind pay (and writes nothing); the
            trainer refuses at its start (exit 2) and goes past the guard with --old-judge-replay 1
    live    every new live name (FGT_G, FGT_W, PRACTICE_P, FGT_BIAS, H2_WADD, FGT_GATE; NEAR_PAY, NEAR_OUT) refused out of its range and accepted
            in it, by the trainer's own reader (sim/train_duel_rnn.py live_read)
    unit    the mixture's probability and the dealing as played (fix A: the kind drawn among four, dealt if valid); the one list's masks (the enemy and the places shut, an invalid option shut); the pay split's parts sum
            to the frame's pay (a simulator run with NEAR_MISS on); the near miss: zero-sum, graded, its cap; a fight start: one seat fresh
            (spawn health, the machine gun) at a spawn point, the other a moment's, a frag added; the win scale's arithmetic
    freeze  (the restart, 11-17) sim/h2freeze.py on the start's own head2 (CPU): one held step leaves every held parameter bit-identical and
            moves the forecast's last layer; after the window the body moves and the weapon scores do not; a zero gradient would move them
    (run each group in its own process: `all` runs live before unit, and unit's near-miss and fight-start checks then fail)
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2b/tests.py <guard|live|unit|freeze|all>"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
sys.path.insert(0, HERE)
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FAILS = []


def check(name, ok, detail=""):
    print("{:5s} {} {}".format("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        FAILS.append(name)


def guard():
    import judge_guard as JG
    tmp = tempfile.mkdtemp(prefix="g22b_")
    bad_ = os.path.join(tmp, "items_bad.json")
    json.dump({"accepted": False}, open(bad_, "w"))
    judge_ = os.path.join(ROOT, "data", "sim_runs", "judge", "judge_v060_wpn.npz")
    good_ = os.path.join(ROOT, "docs", "runs", "2.2", "2.2b", "items_22b.json")
    for nm_, env_, want_ in (("a: no JUDGE_PAY", dict(WIN_ADD="0.33", WIN_JUDGE=judge_, JUDGE_ITEMS=good_), False),
                             ("b: a fit not accepted", dict(WIN_ADD="0.33", JUDGE_PAY="1", WIN_JUDGE=judge_, JUDGE_ITEMS=bad_), False),
                             ("c: no such fit", dict(WIN_ADD="0.33", JUDGE_PAY="1", WIN_JUDGE=judge_, JUDGE_ITEMS=bad_ + ".none"), False),
                             ("d: the judge with an accepted fit", dict(WIN_ADD="0.33", JUDGE_PAY="1", WIN_JUDGE=judge_, JUDGE_ITEMS=good_), True),
                             ("e: no win-chance pay", dict(WIN_ADD="0"), True)):
        ok_, why_ = JG.check(env_, None, ROOT)
        check("guard " + nm_, ok_ == want_, why_[:160])
    ok_, _ = JG.check(dict(WIN_ADD="0"), {"WIN_ADD": 0.33}, ROOT)
    check("guard f: the live file switches the pay on (WIN_ADD 0.33) without the judge with the items", not ok_)
    py_ = sys.executable
    r_ = subprocess.run([py_, os.path.join(ROOT, "tools", "run", "check_settings.py"), os.path.join(ROOT, "docs", "runs", "2.2", "2.2a", "train.cmd")],
                        capture_output=True, text=True, creationflags=NOWIN)
    check("check_settings refuses 2.2a's command", r_.returncode == 1 and "REFUSED the judge's guard" in r_.stdout, r_.stdout.strip().splitlines()[0][:160])
    r_ = subprocess.run([py_, os.path.join(ROOT, "tools", "run", "check_settings.py"), os.path.join(HERE, "train.cmd")], capture_output=True, text=True,
                        creationflags=NOWIN)
    check("check_settings passes 2.2b's command on the guard", "judge's guard: the win-chance pay reads the judge with the items" in r_.stdout,
          r_.stdout.strip().splitlines()[0][:160])
    src_ = os.path.join(tmp, "old.cmd")
    open(src_, "w").write("@echo off\ncd /d C:\\Users\\dacla\\ql-bot\nset WIN_ADD=0.33\nset WIN_JUDGE=x\nstart \"\" python sim\\train_duel_rnn.py --run x\n")
    tc_ = os.path.join(HERE, "train.cmd")
    h0_ = hashlib.sha256(open(tc_, "rb").read()).hexdigest()
    r_ = subprocess.run([py_, os.path.join(ROOT, "tools", "run", "make_train_cmd.py"), src_, "2.2/2.2b"], capture_output=True, text=True, creationflags=NOWIN)
    h1_ = hashlib.sha256(open(tc_, "rb").read()).hexdigest()
    check("make_train_cmd refuses (and writes nothing)", r_.returncode != 0 and "REFUSED, train.cmd not written" in (r_.stdout + r_.stderr) and h0_ == h1_,
          (r_.stdout + r_.stderr).strip().splitlines()[-1][:160])
    env_ = dict(os.environ, WIN_ADD="0.33", JUDGE_PAY="0", CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1")
    r_ = subprocess.run([py_, os.path.join(ROOT, "sim", "train_duel_rnn.py"), "--run", "scratch_22b_guardtest", "--workers", "1"], capture_output=True,
                        text=True, env=env_, creationflags=NOWIN, timeout=600)
    check("the trainer refuses at its start", r_.returncode == 2 and "REFUSED (the judge's guard, 2.2b)" in r_.stdout, (r_.stdout.strip().splitlines() or [""])[-1][:160])
    r_ = subprocess.run([py_, os.path.join(ROOT, "sim", "train_duel_rnn.py"), "--run", "scratch_22b_guardtest", "--workers", "1", "--old-judge-replay", "1",
                         "--env", "no_such_module_22b"], capture_output=True, text=True, env=env_, creationflags=NOWIN, timeout=600)
    check("the trainer goes past the guard with --old-judge-replay 1", "the judge's guard: --old-judge-replay 1:" in r_.stdout,
          [l_ for l_ in r_.stdout.splitlines() if "judge's guard" in l_][:1])


def live():
    os.environ.update(FIGHT="1", NEAR_MISS="1", PAY_SPLIT="1", CUDA_VISIBLE_DEVICES="-1")
    import importlib
    import train_duel_rnn as T
    E_ = importlib.import_module("duel_env_ffa22b")
    start = {k_: os.environ.get(k_) for k_ in getattr(E_, "LIVE_VARS", ())}
    tstart = {k_: 0.0 for k_ in ("DMG_TAKEN_W", "DMG_REWARD")}
    base = json.load(open(os.path.join(ROOT, "data", "sim_runs", "scratch_22b_start", "live_start.json"), encoding="utf-8"))

    def read(d):
        fd_, p_ = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd_, "w", encoding="utf-8") as f_:
            json.dump(d, f_)
        try:
            return T.live_read(p_, E_, start, tstart)[2]
        finally:
            os.unlink(p_)
    check("live: the start's file accepted", read(base) is None)
    for nm_, bad_, good_ in (("FGT_G", (-0.1, 1.5), (0.0, 1.0)), ("FGT_W", (-0.1, 5.5), (0.0, 5.0)), ("PRACTICE_P", (-0.1, 0.31), (0.0, 0.3)),
                             ("FGT_BIAS", (-30.5, 30.5), (-30.0, 30.0)), ("H2_WADD", (-0.1, 1.1), (0.0, 1.0)), ("FGT_GATE", (-30.5, 0.1), (-30.0, 0.0)),
                             ("NEAR_PAY", (-0.1, 10.5), (0.0, 10.0)), ("NEAR_OUT", (150.0, 650.0), (151.0, 600.0))):
        for v_ in bad_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} refused".format(nm_, v_), w_ is not None, (w_ or "")[:120])
        for v_ in good_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} accepted".format(nm_, v_), w_ is None, (w_ or "")[:120])


def unit():
    import torch
    import fightnet as FN
    S = torch.zeros(1, 4)
    v = torch.tensor([[True, True, True, False]])
    lp = FN.mix_logp(S, v, torch.tensor([1]), 0.12, torch.tensor([True]), torch.tensor([False]), None)
    check("mixture: equal scores, 3 valid, practice 0.12, the list off (a kind drawn among four)", abs(float(lp.exp()) - 0.12 * 0.25) < 1e-7, float(lp.exp()))
    jl = torch.log_softmax(torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]), -1)[:, 2:]
    lp = FN.mix_logp(S, torch.ones(1, 4, dtype=torch.bool), torch.tensor([0]), 0.12, torch.tensor([True]), torch.tensor([True]), jl)
    want = 0.12 * 0.25 + 0.88 * (1.0 / 6.0)
    check("mixture: practice 0.12 and the list on (six equal choices), all four valid", abs(float(lp.exp()) - want) < 1e-6, (float(lp.exp()), want))
    lp = FN.mix_logp(S, v, torch.tensor([0]), 0.12, torch.tensor([True]), torch.tensor([True]), jl)
    want = 0.12 * 0.25 + (1.0 - 0.12 * 0.75) * (1.0 / 6.0)
    check("mixture: one kind invalid: its attempts fall to his list", abs(float(lp.exp()) - want) < 1e-6, (float(lp.exp()), want))
    S2 = torch.tensor([[1.0, 2.0, 0.5, 0.0]])
    lp = FN.mix_logp(S2, torch.ones(1, 4, dtype=torch.bool), torch.tensor([1]), 0.05, torch.tensor([True]), torch.tensor([False]), None)
    want = 0.05 * (0.5 * 0.25 + 0.5 * float(torch.softmax(S2, -1)[0, 1]))
    check("mixture: its own half by its softmax over all four", abs(float(lp.exp()) - want) < 1e-7, (float(lp.exp()), want))
    # the dealing as played (fightnet.prac_deal, the trainer's own call) against the probabilities the lessons use: every outcome's frequency
    g_ = torch.Generator().manual_seed(7)
    B_ = 400000
    Sg = torch.tensor([[1.0, -0.5, 0.3, 2.0]]).repeat(B_, 1)
    vg = torch.tensor([[True, False, True, False]]).repeat(B_, 1)       # (him and the angle valid; cut off and back off not)
    el = torch.ones(B_, dtype=torch.bool)
    at_, k_, own_, dl_ = FN.prac_deal(Sg, vg, el, 0.3, torch.ones(B_, dtype=torch.bool), g_)
    fr_ = [float((dl_ & (k_ == j_)).float().mean()) for j_ in range(4)]
    pk_ = [float(FN.mix_logp(Sg[:1], vg[:1], torch.tensor([j_]), 0.3, torch.tensor([True]), torch.tensor([False]), None).exp()) for j_ in range(4)]
    pk_ = [p_ if vg[0, j_] else 0.0 for j_, p_ in enumerate(pk_)]
    keep_ = float(FN.list_keep(Sg[:1], vg[:1], 0.3, torch.tensor([True]))[0])
    err_ = max(abs(a_ - b_) for a_, b_ in zip(fr_, pk_))
    check("the dealing as played: each kind's dealt frequency is the mixture's practice part", err_ < 0.002, (fr_, pk_))
    check("the dealing as played: the share left to his list is list_keep", abs(float((~dl_).float().mean()) - keep_) < 0.002,
          (float((~dl_).float().mean()), keep_))
    tot_ = sum(pk_) + keep_ * 1.0
    check("the mixture sums to 1 (the practice kinds + his list)", abs(tot_ - 1.0) < 1e-6, tot_)
    check("attempts by kind are a quarter each in the even half", abs(float(((k_ == 3) & at_ & ~own_).float().sum() / (at_ & ~own_).float().sum()) - 0.25) < 0.005)
    shut = torch.as_tensor(FN.shut_mask(17))
    it = torch.zeros(1, 17)
    jl = FN.joint_lsm(it, torch.zeros(1, 4), torch.tensor([[True, False, True, True]]), shut, torch).exp()
    check("the one list: the enemy and the places shut, an invalid option shut", float(jl[0, 8]) < 1e-30 and float(jl[0, 9:17].sum()) < 1e-30
          and float(jl[0, 18]) < 1e-30 and abs(float(jl.sum()) - 1.0) < 1e-6 and abs(float(jl[0, 0]) - 1.0 / 11.0) < 1e-6, jl[0].tolist()[:2])
    jn = FN.joint_lsm(it.numpy(), np.zeros((1, 4), np.float32), np.array([[True, False, True, True]]), FN.shut_mask(17))
    check("the one list: numpy as torch", float(np.abs(np.exp(jn) - jl.numpy()).max()) < 1e-7)
    b = FN.bias_for_share(np.zeros(1000), np.full(1000, -2.0), 0.3)
    sh = float(np.mean(1.0 / (1.0 + np.exp(-(-2.0 + b)))))
    check("the one number: the bias at which the four's share is the target", abs(sh - 0.3) < 1e-6, (b, sh))
    # the simulator: the pay split, the near miss, a fight start
    os.environ.update(FIGHT="1", NEAR_MISS="1", NEAR_PAY="5", PAY_SPLIT="1", OUT_LIVE="1.5", GAME_P="0.5", PRO_START_P="0.0001", FIGHT_START_P="0.4999",
                      SPAWN_QL="1", RESPAWN_QL="1")
    import ident_sim as IS
    ev = IS.cmd_env(IS.CMD22A, os.environ.get("QLBOT_ROOT") or ROOT)
    for k_ in ("GAME_P", "PRO_START_P", "MID_START_P", "SPAWN_START_P", "RAIL_START_P", "LATE_P"):
        ev.pop(k_, None)
    for k_, v_ in ev.items():
        os.environ.setdefault(k_, v_)
    import duel_env_ffa as E
    import fight22 as F22
    DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
    env = E.DuelEnv(os.path.join(DATA, "maps", "bloodrun.bsp"), n_matches=16, seed=5, loadout="all", nav=os.path.join(DATA, "maps", "nav_bloodrun_sim.json"))
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    rng = np.random.default_rng(3)
    nA = len(E.ACTION_DIMS)
    err, n_fs, fresh_ok, steps = 0.0, 0, [], 0
    fs_orig = env._fight_start

    def fs_seen(m):                                          # (each fight start, looked at as it is made: one seat fresh, a frag added)
        q_ = [int(x) for x in env._seats(m)]
        f0 = env.frags_r[q_].copy()
        fs_orig(m)
        fr_ = [i_ for i_ in q_ if env.has[i_].sum() == 2 and env.has[i_, E.MG] and env.has[i_, E.G] and env.weapon[i_] == E.MG]
        fresh_ok.append(len(fr_) >= 1 and abs(float((env.frags_r[q_] - f0).sum()) - 1.0) < 1e-9)
    env._fight_start = fs_seen
    for t in range(600):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.6
        a[:, 6] = np.where(rng.random(env.n) < 0.1, 1 + np.array([E.RL, E.GL, E.PG])[rng.integers(0, 3, env.n)], a[:, 6])
        fs0 = float(env.stats.get("fight_start", np.zeros(2))[0])
        obs, r, d, info = env.step(np.concatenate([a, np.full((env.n, 1), 3 + 4 * int(t % 8 == 0))], 1))
        p4 = F22.pay_parts(E, info)
        err = max(err, float(np.abs(p4[:, :4].sum(1) - np.asarray(r, np.float64)).max()))
        steps += 1
        fs1 = float(env.stats.get("fight_start", np.zeros(2))[0])
        if fs1 > fs0:
            n_fs += int(fs1 - fs0)
    check("the pay split: items + fight + win + other = the frame's pay", err < 1e-4, "largest |difference| {:.2e} over {} frames".format(err, steps))
    nm = np.asarray(env.stats.get("near_miss", np.zeros(6)))
    check("near misses paid in a run (NEAR_PAY 5)", nm[1] > 0, "bursts near unhurt {:.0f}, paid {:.0f}, f {:.2f}, pay {:.4f}".format(nm[0], nm[1], nm[2], nm[3]))
    check("fight starts happen (FIGHT_START_P)", n_fs > 0 and len(fresh_ok) > 0 and all(fresh_ok), "{} begun (counted seats), {} made; a fresh seat and one frag added in each: {}".format(n_fs, len(fresh_ok), all(fresh_ok)))
    # the near miss directly: zero-sum, graded, capped
    env.nm_pay[:] = 0.0
    env.nm_bud[:] = 1.0
    s = env.state
    i, v = 0, 1
    env.hp[v] = 100.0
    env.rsp_wait[v] = 0
    c = s[v, :3]
    ep = (c + np.array([float(E.MAXS[0]) + 200.0, 0.0, 0.0], np.float32)).astype(np.float32)      # 200 units beyond his box
    env._near_miss(i, E.RL, ep, [], s)
    f_ = (float(E.NEAR_OUT) - 200.0) / (float(E.NEAR_OUT) - float(E.P_RADIUS[E.RL]))
    pay_ = 5.0 * f_ * env.dmg_reward
    check("near miss: graded (200 units out: f {:.3f}) and zero-sum".format(f_), abs(env.nm_pay[i] - pay_) < 1e-9 and abs(env.nm_pay[v] + pay_) < 1e-9,
          (env.nm_pay[i], env.nm_pay[v], pay_))
    ep2 = (c + np.array([float(E.MAXS[0]) + 50.0, 0.0, 0.0], np.float32)).astype(np.float32)        # within the splash: f 1, but the budget left is 1 - f_
    env._near_miss(i, E.RL, ep2, [], s)
    check("near miss: the cap (one full a second: the second pays only the budget left)", abs(env.nm_pay[i] - 5.0 * env.dmg_reward) < 1e-9,
          (env.nm_pay[i], 5.0 * env.dmg_reward))
    env._near_miss(i, E.RL, ep2, [(v, 10.0, 10.0, None, False)], s)
    check("near miss: a burst that hurt the enemy pays nothing", abs(env.nm_pay[i] - 5.0 * env.dmg_reward) < 1e-9)
    k_i, k_f = (lambda fl_, w_: max(1.0, fl_ / w_))(3.0, 1.5), (lambda fl_, w_: max(1.0, fl_ / w_))(1.0, 4.0)
    check("the win scale: max(1, flat / win)", k_i == 2.0 and k_f == 1.0)


def freeze(start=None):
    """(the restart, 11-17) the item picker held: on the start's own head2 (CPU), with Adam moments primed by an unheld step (stale
    momentum, as a carried optimizer has), one held step (run update 1) leaves every held parameter bit-identical and moves the forecast's
    last layer (v); the goal and weapon scores on a fixed batch are bit-identical; the trainer's decays as gated there; then run update 11:
    the body moves, the weapon scores (wsc, winp) still do not. A control: a zero gradient (not None) with the same moments moves them."""
    import torch
    import head2 as head2_
    import h2freeze as HZ
    torch.manual_seed(0)
    start = start or os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_2b_failed_1117", "keep", "policy_start_22b.pt")
    ck_ = torch.load(start, map_location="cpu", weights_only=False)
    L_ = ck_["head2"]["layout"] if "layout" in ck_["head2"] else ck_["head2"]
    m_ = head2_.make_module(L_)
    m_.load_state_dict({k_[6:]: v_ for k_, v_ in ck_["model"].items() if k_.startswith("head2.")})
    mainp_ = [p_ for n_, p_ in m_.named_parameters() if not n_.startswith(("winp.", "wsc.", "plan.", "trk."))]
    opt_ = torch.optim.Adam(mainp_, lr=1e-4, eps=1e-5)
    opt_.add_param_group({"params": list(m_.winp.parameters()) + list(m_.wsc.parameters()), "lr": 1e-4})
    popt_, topt_ = torch.optim.Adam(m_.plan.parameters(), lr=1e-4), torch.optim.Adam(m_.trk.parameters(), lr=1e-4)
    S_ = int(m_.gru.hidden_size)
    Hh_ = int(m_.v.in_features) - S_
    W_ = int(m_.inp.in_features) + int(m_.winp.in_features)
    u_, s0_, h_ = torch.randn(32, W_) * 0.5, torch.randn(32, S_) * 0.3, torch.randn(32, Hh_) * 0.3
    coef_ = {n_: torch.randn_like(p_) for n_, p_ in m_.named_parameters()}

    def loss_():
        s_ = m_.gru(head2_.pre(m_, u_), s0_)
        l_ = head2_.value(m_, s_, h_).pow(2).mean() + m_.target(s_).pow(2).mean() + m_.wsc(s_).pow(2).mean() + m_.plan_out(s_).pow(2).mean()
        return l_ + sum((p_ * coef_[n_]).sum() * 1e-3 for n_, p_ in m_.named_parameters())     # (every parameter has a gradient)

    def step(fz, zero_not_none=False):
        for o_ in (opt_, popt_, topt_):
            o_.zero_grad(set_to_none=True)
        loss_().backward()
        if fz is not None:
            if zero_not_none:
                for n_, p_ in m_.named_parameters():
                    if fz.frozen(n_):
                        p_.grad = torch.zeros_like(p_)
            else:
                fz.drop_grads()
        opt_.step()
        with torch.no_grad():                                     # (the trainer's decays, gated as there)
            if fz is None or not fz.frozen("target.weight"):
                m_.target.weight *= 1.0 - 1e-4 * 0.01
            if fz is None or not fz.frozen("wsc.weight"):
                m_.wsc.weight *= 1.0 - 1e-4 * 0.01
        for pre_, o_ in (("plan.", popt_), ("trk.", topt_)):      # (their own Adam: skipped while held)
            if fz is None or not fz.own_adam_frozen(pre_):
                o_.step()
    step(None)                                                    # (moments primed: stale momentum)
    sd0_ = {k_: v_.clone() for k_, v_ in m_.state_dict().items()}
    fz_ = HZ.Freeze(m_, window=10, done0=0, freeze=True, wfreeze=True)
    fz_.set_update(1)
    step(fz_)
    r_ = fz_.record(restore=False)
    check("freeze: run update 1, every held parameter bit-identical ({} of {})".format(r_["held_n"], len(fz_.names)), r_["held_max"] == 0.0 and not r_["moved"],
          "largest difference {} on {}".format(r_["held_max"], [n_ for n_, d_ in r_["held_by_name"].items() if d_]))
    check("freeze: the forecast's last layer moved", all(d_ > 0 for d_ in r_["forecast_moved"].values()) and set(r_["forecast_moved"]) == {"v.weight", "v.bias"},
          str(r_["forecast_moved"]))
    check("freeze: goal, weapon and plan scores on a fixed batch bit-identical", all(v_ == 0.0 for v_ in r_["outputs_vs_start"].values()), str(r_["outputs_vs_start"]))
    fz_.set_update(10)
    step(fz_)
    r10_ = fz_.record(restore=False)
    check("freeze: run update 10 still held", r10_["on"] and r10_["held_max"] == 0.0, "held_max {}".format(r10_["held_max"]))
    fz_.set_update(11)
    step(fz_)
    r11_ = fz_.record(restore=False)
    body_ = {n_: d_ for n_, d_ in r11_["held_by_name"].items()}
    check("freeze: run update 11, the window over: the body moved, the weapon scores still bit-identical",
          (not r11_["on"]) and r11_["weapon_max"] == 0.0 and set(body_) == {"winp.weight", "winp.bias", "wsc.weight", "wsc.bias"} and r11_["free_max"] > 0,
          "weapon {} (held {}), the rest's largest movement {}, the goal scores' {}".format(r11_["weapon_max"], sorted(body_), r11_["free_max"],
                                                                                           r11_["outputs_vs_start"].get("target")))
    m_.load_state_dict(sd0_)
    fc_ = HZ.Freeze(m_, window=10, done0=0, freeze=True, wfreeze=True)
    fc_.set_update(1)
    step(fc_, zero_not_none=True)
    rc_ = fc_.record(restore=False)
    check("freeze control: a zero gradient (not None) with stale moments DOES move the held parameters", rc_["held_max"] > 0,
          "largest difference {}".format(rc_["held_max"]))
    fr_ = HZ.Freeze(m_, window=10, done0=10, freeze=True, wfreeze=False)
    check("freeze: a resume after the run's update 10 does not start the window again", not fr_.set_update(1))
    fp_ = HZ.Freeze(m_, window=10, done0=0, freeze=True, wfreeze=True)
    fp_.set_update(3)
    w0_ = m_.wsc.weight.detach().clone()
    with torch.no_grad():
        m_.wsc.weight.add_(0.5)
    rp_ = fp_.record(restore=True)
    check("freeze: a held parameter found moved is reported and put back", rp_["restored"] and "wsc.weight" in rp_["moved"] and torch.equal(m_.wsc.weight, w0_),
          "held_max {} moved {}".format(rp_["held_max"], rp_["moved"]))
    import alarms_22b as AL
    ls_ = AL.lines(dict(h2_freeze=rp_), 3)
    check("freeze: the ramp's line for it is MAJOR", any(l_.startswith("MAJOR PROBLEM update 3: A FROZEN PART") for l_ in ls_), ls_[-1][:140])


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for nm_, fn_ in (("guard", guard), ("live", live), ("unit", unit), ("freeze", freeze)):
        if which in (nm_, "all"):
            fn_()
    print("ALL PASSED" if not FAILS else "FAILED: {}".format(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()

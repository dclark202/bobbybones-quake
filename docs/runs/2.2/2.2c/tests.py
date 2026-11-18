"""2.2c's tests (the build's brief; every one prints its numbers and PASS or FAIL; exit 1 on a failure). Scratch only (a temp folder); nothing deleted.
    unit    THE CONTEST PAY on constructed cases (the simulator's own code: sim/duel_env.py _cb_pick, _cb_frame, _rc_pick, _rc_line): a free pickup
            costs the other CEDE_W of the pay; full pressure moves CONTEST_W; partial pressure graded; damage taken off; the cap per spawn; the
            picker never below 20% of what his pickup paid (with the by-the-second pay before it); the steal and its 10 s; the pay by the second
            and its stop beyond 6 s of way, its cap; zero-sum to the last digit; the rail's pickup pay once a life; the long line only with the rail
            in hand beyond 768; then a whole run with every switch on: every new term zero-sum in every match of every frame, the pay split's
            parts (2.2c's groups) sum to the frame's pay; THE LEVER: the numpy reader (the checks' player) as the trainer's torch, its add rounded
            to half precision, its layout's inputs; the near miss untouched
    live    every new live name (LEV_G, CONTEST_W, CEDE_W, RAIL_PICK_PAY, RAIL_LINE_PAY, RAIL_FAR_PAY) refused out of its range and accepted at its
            ends, by the trainer's own reader (sim/train_duel_rnn.py live_read)
    (run each group in its own process)
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2c/tests.py <unit|live> [<start.pt for the lever>]"""
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
sys.path.insert(0, HERE)
FAILS = []


def check(name, ok, detail=""):
    print("{:5s} {} {}".format("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        FAILS.append(name)


def cmd_env():
    import ident_sim as IS
    root_ = os.environ.get("QLBOT_ROOT") or ROOT
    ev = IS.cmd_env(os.path.join(HERE, "train.cmd"), root_)
    ev.update(IS.cmd_env(os.path.join(HERE, "aim2_env.cmd"), root_))
    return ev


def live():
    os.environ.update(cmd_env())
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import importlib
    import train_duel_rnn as T
    E_ = importlib.import_module("duel_env_ffa22c")
    start = {k_: os.environ.get(k_) for k_ in getattr(E_, "LIVE_VARS", ())}
    tstart = {k_: 0.0 for k_ in ("DMG_TAKEN_W", "DMG_REWARD")}
    import start_live as SL
    tmp_ = tempfile.mkdtemp(prefix="l22c_")
    bp_ = os.path.join(tmp_, "live.json")
    sys.argv = ["x", os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "duel_gru_2_2a", "live.json"), bp_]
    SL.main()
    base = json.load(open(bp_, encoding="utf-8"))

    def read(d):
        p_ = os.path.join(tmp_, "t.json")
        json.dump(d, open(p_, "w", encoding="utf-8"))
        return T.live_read(p_, E_, start, tstart)[2]
    check("live: the start's file accepted", read(base) is None)
    for nm_, bad_, good_ in (("LEV_G", (-0.1, 1.1), (0.0, 1.0)), ("CONTEST_W", (-0.1, 1.1), (0.0, 1.0)), ("CEDE_W", (-0.1, 0.6), (0.0, 0.5)),
                             ("RAIL_PICK_PAY", (-0.1, 1.1), (0.0, 1.0)), ("RAIL_LINE_PAY", (-0.1, 1.1), (0.0, 1.0)), ("RAIL_FAR_PAY", (-0.1, 1.1), (0.0, 1.0))):
        for v_ in bad_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} refused".format(nm_, v_), w_ is not None, (w_ or "")[:120])
        for v_ in good_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} accepted".format(nm_, v_), w_ is None, (w_ or "")[:120])


def make_env(seed=5, matches=1):
    import importlib
    E = importlib.import_module("duel_env_ffa")
    D = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "maps")
    env = E.DuelEnv(os.path.join(D, "bloodrun.bsp"), n_matches=matches, seed=seed, loadout="all", nav=os.path.join(D, "nav_bloodrun_sim.json"))
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    return E, env


def fresh_books(env):
    env.cb_r1[:] = 0.0
    env.cb_r2 = np.zeros_like(env.cb_r2)
    env.cb_bt[:] = -10 ** 9
    env.cb_bw[:] = 0.0
    env.cb_dd[:] = 0.0
    env.cb_dt[:] = 0.0
    env.cb_mv[:] = 0.0
    env.cb_chg[:] = 0.0
    env.cb_stl[:] = -10 ** 9
    env._pt_begin()


def unit(start=None):
    ev = cmd_env()
    ev.update(PAY_SPLIT="1", CUDA_VISIBLE_DEVICES="-1", GAME_P="0.65", PRO_START_P="0", FIGHT_START_P="0")
    os.environ.update(ev)
    E, env = make_env()
    assert E.CONTEST and E.RAIL_CHAIN and E.AHEAD_IN and E.PAY_SPLIT
    check("the contested items of Blood Run (the route goals of MH, RA, YA, RL, RG, LG)", len(env.cb_it) >= 4, env.cb_lab)
    k = env.cb_lab.index("MH")
    it = int(env.cb_it[k])
    i, j = 0, 1
    env.script[:] = 0
    env.run_k[:] = -1
    env.jrun[:] = False
    env.items_room[:] = False
    env.kind[0], env.mode[0] = E.NORMAL, -1
    s = env.state
    ci = E.PT_IX["contest"]
    cs = E.PT_IX["contest_sec"]

    def pick(pay):
        fresh_rw = np.zeros(env.n, np.float32), np.zeros(env.n, np.float32)
        env._pt_begin()
        env._cb_pick(i, it, pay, fresh_rw[0], fresh_rw[1], s)
        return fresh_rw[0], env.pt[:, ci].copy()

    fresh_books(env)
    r, pt = pick(0.35)
    check("a free pickup: the other pays the picker CEDE_W (0.1) of the pay: +0.035 / -0.035", abs(float(r[i]) - 0.035) < 1e-7 and abs(float(r[j]) + 0.035) < 1e-7,
          r.tolist())
    check("zero-sum to the last digit (the frame's pay and the term's books)", float(r.sum()) == 0.0 and float(pt.sum()) == 0.0, (float(r.sum()), float(pt.sum())))
    fresh_books(env)
    env.cb_r2[j, k] = 0.5
    env.cb_dd[j, 0] = 100.0
    r, pt = pick(0.35)
    check("full pressure (shells 0.5 and 100 damage 0.5): CONTEST_W (0.8) of 0.35 = 0.28 moves to him; the picker keeps 0.07 (20%)",
          abs(float(r[j]) - 0.28) < 1e-7 and abs(float(r[i]) + 0.28) < 1e-7 and abs(0.35 + float(r[i]) - 0.07) < 1e-7, r.tolist())
    check("zero-sum to the last digit", float(r.sum()) == 0.0 and float(pt.sum()) == 0.0)
    fresh_books(env)
    env.cb_r2[j, k] = 0.25
    r, _ = pick(0.35)
    want_ = 0.35 * (0.8 * 0.25 - 0.1 * 0.75)
    check("pressure 0.25 (shells): 0.35 x (0.8 x 0.25 - 0.1 x 0.75) = {:.5f} to him".format(want_), abs(float(r[j]) - want_) < 1e-7, r.tolist())
    fresh_books(env)
    env.cb_r1[j, k, 3] = 1.0
    r, _ = pick(0.35)
    want_ = 0.35 * (0.8 * 0.25 - 0.1 * 0.75)
    check("rung 1 (set on it, 1 in the last second) is a quarter: the same {:.5f}".format(want_), abs(float(r[j]) - want_) < 1e-7, r.tolist())
    fresh_books(env)
    env.cb_r2[j, k] = 0.5
    env.cb_dd[j, 0] = 100.0
    env.cb_dt[j, 1] = 200.0
    r, _ = pick(0.35)
    check("damage taken from the enemy taken off (200 points = 1): pressure 0, the free pickup's charge", abs(float(r[j]) + 0.035) < 1e-7, r.tolist())
    fresh_books(env)
    env.cb_r2[j, k] = 0.5
    env.cb_dd[j, 0] = 100.0
    env.cb_mv[0, k] = 0.25
    r, _ = pick(0.35)
    check("the cap per spawn: 0.25 moved already (by the second), at most 0.28 in all: 0.03 more", abs(float(r[j]) - 0.03) < 1e-7, r.tolist())
    fresh_books(env)
    env.cb_r2[j, k] = 0.5
    env.cb_dd[j, 0] = 100.0
    env.cb_chg[i, k] = 0.05
    env.cb_mv[0, k] = 0.05
    r, _ = pick(0.10)
    check("the picker never below 20% of what his pickup paid: a mega that paid him 0.10, charged 0.05 by the second already: 0.03 more "
          "(0.08 = 80% in all)", abs(float(r[j]) - 0.03) < 1e-7 and abs(env.cb_chg[i, k] - 0.08) < 1e-9, (r.tolist(), float(env.cb_chg[i, k])))
    fresh_books(env)
    env.cb_stl[i, k] = env.cb_f - 10
    r, pt = pick(0.35)
    check("THE STEAL: he took the item the enemy was headed for, having pressured it 0.25 s before: 0.28 from the enemy, and the free charge "
          "0.035 (the enemy put no pressure on his pickup): +0.315", abs(float(r[i]) - 0.315) < 1e-6 and abs(float(r[j]) + 0.315) < 1e-6, r.tolist())
    check("the steal zero-sum, once (the mark consumed)", float(r.sum()) == 0.0 and float(pt.sum()) == 0.0 and env.cb_stl[i, k] < 0)
    fresh_books(env)
    env.cb_stl[i, k] = env.cb_f - 401
    r, _ = pick(0.35)
    check("no steal after 10 s (10.025 s)", abs(float(r[i]) - 0.035) < 1e-7, r.tolist())
    # THE PAY BY THE SECOND: _cb_frame with the seconds of way given
    nC = len(env.cb_it)

    def sec(way_o, way_j=8.0, mv=0.0, chg=0.0):
        fresh_books(env)
        env.hp[:] = 100.0
        env.armor[:] = 0.0
        env.weapon[:] = E.G                                  # (no weapon that reaches: rung 1's quarter 0)
        env.item_up[0, it] = True
        env.cb_mv[0, k] = mv
        env.cb_chg[j, k] = chg
        W = np.full((env.n, nC), 50.0)
        W[j, k], W[i, k] = way_o, way_j                      # (j is the enemy here: nearer the mega)
        env._cb_ways = lambda s_: W
        env.cb_rt = np.asarray(env.round_t[:env.M], np.float64).copy()
        env.cb_bt[i, 0] = env.cb_f
        env.cb_bp[i, 0] = env.item_pos[it]
        env.cb_bw[i, 0] = 0.25
        env.cb_bf[i, 0] = 0.0
        rw_, rl_ = np.zeros(env.n, np.float32), np.zeros(env.n, np.float32)
        env._cb_frame(s, {"by": {}}, rw_, rl_)
        del env._cb_ways
        return rw_, env.pt[:, cs].copy()
    base_ = min(0.35, 100.0 * float(E.ITEM_PT_HI))
    want_ = 0.8 / 5.0 * base_ * 0.5 * E.DT
    r, pt = sec(5.9)
    check("by the second: the enemy 5.9 s from the mega, nearer than he, his shell at it (pressure 2 x 0.25 = 0.5): 0.16 x {:.3f} (the mega to "
          "the enemy at 100 health) x 0.5 x 0.025 s = {:.6f} a frame".format(base_, want_), abs(float(r[i]) - want_) < 1e-8 and abs(float(r[j]) + want_) < 1e-8,
          r.tolist())
    check("by the second: zero-sum to the last digit", float(r.sum()) == 0.0 and float(pt.sum()) == 0.0)
    r, _ = sec(6.1)
    check("by the second: stops beyond 6 s of way (6.1)", float(np.abs(r).sum()) == 0.0, r.tolist())
    r, _ = sec(5.0, way_j=4.0)
    check("by the second: none when he is the nearer", float(np.abs(r).sum()) == 0.0, r.tolist())
    r, _ = sec(5.0, mv=0.28 - 1e-5)
    check("by the second: the cap per spawn (0.28 of the mega's 0.35)", abs(float(r[i]) - 1e-5) < 1e-8, r.tolist())
    r, _ = sec(5.0, chg=0.8 * base_)
    check("by the second: the enemy never charged more than 80% of what the mega would pay him", float(np.abs(r).sum()) == 0.0, r.tolist())
    # THE RAIL CHAIN
    env._pt_begin()
    rw_, rl_ = np.zeros(env.n, np.float32), np.zeros(env.n, np.float32)
    env.rc_paid = np.zeros(env.n, bool)
    env._rc_pick(i, rw_, rl_)
    a1 = rw_.copy()
    env._rc_pick(i, rw_, rl_)
    a2 = rw_ - a1
    env._fresh(i, 0.0)
    env._rc_pick(i, rw_, rl_)
    a3 = rw_ - a1
    check("the rail's pickup pay: 0.15 to him, 0.15 from the enemy (zero-sum); none again in the same life; again after a new life",
          abs(float(a1[i]) - 0.15) < 1e-7 and float(a1.sum()) == 0.0 and float(np.abs(a2).sum()) == 0.0 and abs(float(a3[i]) - 0.15) < 1e-7,
          (a1.tolist(), a2.tolist(), a3.tolist()))
    pos = np.zeros((env.n, 3))
    pos[j, 0] = 1000.0
    for nm_, wi_, wj_, dj_, want_ in (("beyond 768, the rail in his hand, the enemy's not: 0.10 x 0.8", E.RG, E.MG, 1000.0, 0.08),
                                      ("within 768: nothing", E.RG, E.MG, 700.0, 0.0), ("no rail in his hand: nothing", E.MG, E.MG, 1000.0, 0.0),
                                      ("both with the rail: 0.10 x (0.8 - 0.5)", E.RG, E.RG, 1000.0, 0.03)):
        env._pt_begin()
        env.weapon[i], env.weapon[j] = wi_, wj_
        pos[j, 0] = dj_
        rw_ = np.zeros(env.n, np.float32)
        d_ = env._rc_line(np.array([i]), np.array([j]), np.array([0.8, 0.5]), pos, np.ones(env.n, bool), rw_)
        check("the long line: " + nm_, abs(float(rw_[i]) - want_) < 1e-7 and float(rw_.sum()) == 0.0 and abs(float(env.pt[:, E.PT_IX["rail_line"]].sum())) == 0.0,
              rw_.tolist())
    # A WHOLE RUN with every switch on: the new terms zero-sum in every match of every frame; the pay split's parts sum to the frame's pay
    import fight22 as F22
    assert F22.SPLIT == "22c"
    E2, env2 = make_env(seed=9, matches=8)
    rng = np.random.default_rng(3)
    worst, worst_sp, paid = 0.0, 0.0, dict(contest=0.0, contest_sec=0.0, rail_pick=0.0, rail_line=0.0)
    for t in range(3000):
        act = np.stack([rng.integers(0, d_, env2.n) for d_ in E2.ACTION_DIMS], 1)
        act[:, 5] = rng.random(env2.n) < 0.5
        act = np.concatenate([act, (3 + 4 * int(t % 8 == 0) + np.zeros(env2.n, np.int64))[:, None]], 1)
        o_, r_, d_, info = env2.step(act)
        P = env2.pt
        for nm_ in paid:
            c_ = P[:, E2.PT_IX[nm_]].reshape(-1, 2).sum(1)
            worst = max(worst, float(np.abs(c_).max()))
            paid[nm_] += float(np.abs(P[:, E2.PT_IX[nm_]]).sum())
        p4_ = F22.pay_parts(E2, info)
        worst_sp = max(worst_sp, float(np.abs(p4_[:, :4].sum(1) - np.asarray(r_, np.float64)).max()))
    C_ = env2.stats.get("contest")
    check("a whole run (8 matches x 3,000 frames, random actions, every switch on): the new terms zero-sum in every match of every frame",
          worst <= 1e-15, "largest |sum| {:.3g}; sizes {}".format(worst, {k_: round(v_, 4) for k_, v_ in paid.items()}))
    check("... and they were paid (the contest pay at pickups and by the second)", paid["contest"] > 0 and paid["contest_sec"] > 0, paid)
    check("the pay split's parts (2.2c's groups) sum to the frame's pay", worst_sp < 1e-5, worst_sp)
    print("      (the run's contest counters: {})".format(dict(zip(E2.CB_COLS, np.round(C_, 3).tolist())) if C_ is not None else None))
    g_ = F22.groups(list(E2.PAY_TERMS))
    nm_g = {k2_: [E2.PAY_TERMS[x_] for x_ in g_[k2_]] for k2_ in ("items", "fight", "win")}
    check("2.2c's split: the item picker counts the contest pay, the rail chain and the far rail; the fight network damage, frags, deaths (no "
          "near miss, no far rail)", all(x_ in nm_g["items"] for x_ in ("contest", "contest_sec", "rail_pick", "rail_line", "rail"))
          and set(nm_g["fight"]) == {"dmg_dealt", "dmg_taken", "frag", "death", "deaths_other", "high"} and "near_miss" not in nm_g["fight"], nm_g)
    # THE LEVER: numpy (the checks' player) as torch (the trainer)
    import torch
    import fightnet as FN
    if start:
        ck = torch.load(start, map_location="cpu", weights_only=False)
        L = ck["fight22"]["layout"]
        check("the start's fight network is the lever's layout (version 2), its last layer zero, LEV_G 0 in the file", FN.is_lever(L) and
              float(ck["fight22"]["model"]["l3.weight"].abs().sum()) == 0.0 and float(ck["fight22"]["model"]["l3.bias"].abs().sum()) == 0.0
              and ck["fight22"]["dials"].get("LEV_G") == 0.0, [k_ for k_, _ in L["parts"]])
        mod = FN.make_module(L)
        sd_ = {k_: torch.as_tensor(np.asarray(v_)) for k_, v_ in ck["fight22"]["model"].items()}
        g = torch.Generator().manual_seed(1)
        sd_["l3.weight"] = torch.randn(sd_["l3.weight"].shape, generator=g) * 0.05
        sd_["l3.bias"] = torch.randn(sd_["l3.bias"].shape, generator=g) * 0.05
        mod.load_state_dict(sd_)
        x = torch.randn(64, int(L["width"]), generator=g)
        lt_, vt_ = mod(x)
        ln_, vn_ = FN.np_forward_lever(FN.np_params({k_: v_.numpy() for k_, v_ in sd_.items()}), x.numpy())
        check("the lever: numpy as torch (64 rows, a last layer made non-zero)", float(np.abs(lt_.detach().numpy() - ln_).max()) < 1e-5
              and float(np.abs(vt_.detach().numpy() - vn_).max()) < 1e-5, float(np.abs(lt_.detach().numpy() - ln_).max()))
        a_t = FN.lever_add(lt_.detach(), 1.0, torch)
        a_n = FN.lever_add(ln_, 1.0)
        check("the lever's add rounded to half precision as played, numpy as torch", float(np.abs(a_t.numpy() - a_n).max()) < 1e-3
              and np.array_equal(a_n, a_n.astype(np.float16).astype(np.float32)), float(np.abs(a_t.numpy() - a_n).max()))
        v_ = FN.lever_vec(torch.tensor([1.5, -2.0]), 17, torch)
        check("the lever's vector: only 'the enemy' (8)", float(v_[:, 8].sub(torch.tensor([1.5, -2.0])).abs().max()) == 0.0 and float(v_.abs().sum()) == 3.5)
        nm_ = FN.names(L)
        check("the lever's inputs: no options' numbers, no fight option he is on", not any(n_.startswith(("him ", "cut ", "angle ", "away ", "dest fight"))
                                                                                            for n_ in nm_), len(nm_))
    print("ALL PASSED" if not FAILS else "FAILED: {}".format(FAILS))


def main():
    {"unit": unit, "live": live}[sys.argv[1]](*sys.argv[2:])
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()

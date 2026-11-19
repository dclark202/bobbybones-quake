"""2.2d's tests (the build's brief; every one prints its numbers and PASS or FAIL; exit 1 on a failure). Scratch only (a temp folder); nothing deleted.
    unit    THE THREE PAYS AT ZERO, under 2.2d's command (CONTEST=1 CONTEST_LOG=1 CONTEST_W=0 CEDE_W=0, RAIL_CHAIN=1 RAIL_LINE_PAY=0, NEAR_MISS=1
            NEAR_PAY=0), on constructed cases with the simulator's own code (sim/duel_env.py _cb_pick, _cb_frame, _near_miss, _preaim): a pickup
            under full pressure, a free pickup, a steal, the pay by the second, a near miss: nothing written to the frame's pay or r_long, the
            terms 0.0, the counters counted (the steal and the frame by the second on the event); then a whole run (8 matches x 3,000 frames,
            random actions, every switch of the command): the terms contest, contest_sec, rail_line, near_miss exactly 0.0 on every seat of
            every frame, rail_pick and rail paid, the pay split's parts summing to the frame's pay, the counters counting (the contest pay's,
            the near miss's, RAIL_WOULD's, FREE_SEE's)
            THE RAIL LOG LINE (RAIL_WOULD, _rw_frame) on constructed frames: a seat with the enemy in sight and his crosshair on the enemy's body
            -> a window that books one possible hit of 80 after 60 frames (1.5 s) with the damage booked in it; the same seat looking away -> 0;
            no window while the enemy is out of his sight; windows do not overlap
            THE FREE PICKUP'S LINE (FREE_SEE, _free_see): a seat with a line and one without (the item behind a wall), and a dead one
    live    every live name 2.2d sets (LEV_G, CONTEST_W, CEDE_W, RAIL_PICK_PAY, RAIL_LINE_PAY, RAIL_FAR_PAY, NEAR_PAY) refused out of its range and
            accepted at its ends, by the trainer's own reader (sim/train_duel_rnn.py live_read); the start's file accepted
    watch   tools/run/watch.py's checks at named updates (CHECK_AT 10,30,50,60,70, CHECK_REF_AT 60, CHECK_END 1) on a simulated run (a fake clock,
            saves every 10 updates to 80, the trainer's exit line; the checks recorded, not played): the order, 60 against both, the end, none skipped
    (run each group in its own process)
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2d/tests.py <unit|live|watch>"""
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
sys.path.insert(1, os.path.join(HERE, "..", "2.2c"))
FAILS = []
DROPPED = ("contest", "contest_sec", "rail_line", "near_miss")


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
    tmp_ = tempfile.mkdtemp(prefix="l22d_")
    bp_ = os.path.join(tmp_, "live.json")
    sys.argv = ["x", os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "duel_gru_2_2a", "live.json"), bp_]
    SL.main()
    base = json.load(open(bp_, encoding="utf-8"))
    check("live: the start's file has the three pays at 0 (CONTEST_W, CEDE_W, RAIL_LINE_PAY, NEAR_PAY) and RAIL_PICK_PAY 0.15, RAIL_FAR_PAY 0.5",
          all(base.get(k_) == 0.0 for k_ in ("CONTEST_W", "CEDE_W", "RAIL_LINE_PAY", "NEAR_PAY")) and base.get("RAIL_PICK_PAY") == 0.15
          and base.get("RAIL_FAR_PAY") == 0.5, {k_: base.get(k_) for k_ in ("CONTEST_W", "CEDE_W", "RAIL_LINE_PAY", "NEAR_PAY", "RAIL_PICK_PAY", "RAIL_FAR_PAY")})

    def read(d):
        p_ = os.path.join(tmp_, "t.json")
        json.dump(d, open(p_, "w", encoding="utf-8"))
        return T.live_read(p_, E_, start, tstart)[2]
    check("live: the start's file accepted", read(base) is None)
    for nm_, bad_, good_ in (("LEV_G", (-0.1, 1.1), (0.0, 1.0)), ("CONTEST_W", (-0.1, 1.1), (0.0, 1.0)), ("CEDE_W", (-0.1, 0.6), (0.0, 0.5)),
                             ("RAIL_PICK_PAY", (-0.1, 1.1), (0.0, 1.0)), ("RAIL_LINE_PAY", (-0.1, 1.1), (0.0, 1.0)), ("RAIL_FAR_PAY", (-0.1, 1.1), (0.0, 1.0)),
                             ("NEAR_PAY", (-0.1, 10.5), (0.0, 10.0))):
        for v_ in bad_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} refused".format(nm_, v_), w_ is not None, (w_ or "")[:120])
        for v_ in good_:
            w_ = read(dict(base, **{nm_: v_}))
            check("live: {} {} accepted".format(nm_, v_), w_ is None, (w_ or "")[:120])


def make_env(seed=5, matches=1, mp="bloodrun"):
    import importlib
    E = importlib.import_module("duel_env_ffa")
    D = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "maps")
    env = E.DuelEnv(os.path.join(D, mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=os.path.join(D, "nav_{}_sim.json".format(mp)))
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


def unit():
    ev = cmd_env()
    ev.update(PAY_SPLIT="1", CUDA_VISIBLE_DEVICES="-1", GAME_P="0.65", PRO_START_P="0", FIGHT_START_P="0")
    os.environ.update(ev)
    E, env = make_env()
    check("2.2d's command: CONTEST, CONTEST_LOG, RAIL_CHAIN, NEAR_MISS, RAIL_WOULD, FREE_SEE on; CONTEST_W, CEDE_W, RAIL_LINE_PAY, NEAR_PAY 0; "
          "RAIL_PICK_PAY 0.15, RAIL_FAR_PAY 0.5", E.CONTEST and E.CONTEST_LOG and E.RAIL_CHAIN and E.NEAR_MISS and E.RAIL_WOULD and E.FREE_SEE
          and E.CONTEST_W == 0.0 and E.CEDE_W == 0.0 and E.RAIL_LINE_PAY == 0.0 and E.NEAR_PAY == 0.0 and E.RAIL_PICK_PAY == 0.15
          and E.RAIL_FAR_PAY == 0.5, dict(CONTEST_W=E.CONTEST_W, CEDE_W=E.CEDE_W, RAIL_LINE_PAY=E.RAIL_LINE_PAY, NEAR_PAY=E.NEAR_PAY))
    k = env.cb_lab.index("MH")
    it = int(env.cb_it[k])
    i, j = 0, 1
    env.script[:] = 0
    env.run_k[:] = -1
    env.jrun[:] = False
    env.items_room[:] = False
    env.kind[0], env.mode[0] = E.NORMAL, -1
    s = env.state
    ci, cs = E.PT_IX["contest"], E.PT_IX["contest_sec"]
    C = env.stats["contest"]

    def pick(pay, w=(0.8, 0.1)):
        E.CONTEST_W, E.CEDE_W = w                            # (even at 2.2c's dials CONTEST_LOG moves nothing)
        rw_, rl_ = np.zeros(env.n, np.float32), np.zeros(env.n, np.float32)
        env._pt_begin()
        env._cb_pick(i, it, pay, rw_, rl_, s)
        E.CONTEST_W, E.CEDE_W = 0.0, 0.0
        return rw_, rl_, env.pt[:, [ci, cs]].copy()
    for w_ in ((0.0, 0.0), (0.8, 0.1)):
        fresh_books(env)
        c0 = C.copy()
        r, rl, pt = pick(0.35, w_)
        check("a free pickup (CONTEST_W, CEDE_W = {}): nothing to the pay, r_long, the terms; counted as free (C[7] +1) and his distance".format(w_),
              not r.any() and not rl.any() and not pt.any() and C[7] - c0[7] == 1 and C[0] - c0[0] == 1 and C[8] > c0[8],
              (r.tolist(), (C - c0)[[0, 1, 7, 8, 12, 13]].tolist()))
        fresh_books(env)
        env.cb_r2[j, k] = 0.5
        env.cb_dd[j, 0] = 100.0
        c0 = C.copy()
        r, rl, pt = pick(0.35, w_)
        check("full pressure (CONTEST_W, CEDE_W = {}): nothing to the pay, r_long, the terms; counted under pressure (C[1] +1, pressure 1), the "
              "pay columns 0".format(w_), not r.any() and not rl.any() and not pt.any() and C[1] - c0[1] == 1 and abs(C[2] - c0[2] - 1.0) < 1e-12
              and C[12] == c0[12] and C[13] == c0[13] and C[17] == c0[17], (r.tolist(), (C - c0)[[1, 2, 12, 13, 17]].tolist()))
        fresh_books(env)
        env.cb_stl[i, k] = env.cb_f - 10
        c0 = C.copy()
        r, rl, pt = pick(0.35, w_)
        check("THE STEAL (CONTEST_W, CEDE_W = {}): counted (C[11] +1) on the event, nothing paid, the mark consumed".format(w_),
              C[11] - c0[11] == 1 and not r.any() and not rl.any() and not pt.any() and env.cb_stl[i, k] < 0, ((C - c0)[[11, 12, 13]].tolist(), r.tolist()))
    nC = len(env.cb_it)

    def sec(way_o, way_j=8.0, w=(0.8, 0.1)):
        fresh_books(env)
        env.hp[:] = 100.0
        env.armor[:] = 0.0
        env.weapon[:] = E.G
        env.item_up[0, it] = True
        W = np.full((env.n, nC), 50.0)
        W[j, k], W[i, k] = way_o, way_j
        env._cb_ways = lambda s_: W
        env.cb_rt = np.asarray(env.round_t[:env.M], np.float64).copy()
        env.cb_bt[i, 0] = env.cb_f
        env.cb_bp[i, 0] = env.item_pos[it]
        env.cb_bw[i, 0] = 0.25
        env.cb_bf[i, 0] = 0.0
        E.CONTEST_W, E.CEDE_W = w
        rw_, rl_ = np.zeros(env.n, np.float32), np.zeros(env.n, np.float32)
        c0_ = C.copy()
        env._cb_frame(s, {"by": {}}, rw_, rl_)
        E.CONTEST_W, E.CEDE_W = 0.0, 0.0
        del env._cb_ways
        return rw_, rl_, env.pt[:, [ci, cs]].copy(), C - c0_
    for w_ in ((0.0, 0.0), (0.8, 0.1)):
        r, rl, pt, dc = sec(5.9, w=w_)
        check("by the second (CONTEST_W, CEDE_W = {}; the enemy 5.9 s from the mega, nearer, his shell at it): the frame counted (C[16] +1), "
              "nothing paid, the cap not counted (C[17] 0)".format(w_), dc[16] == 1 and dc[17] == 0 and dc[14] == 0 and dc[15] == 0 and not r.any()
              and not rl.any() and not pt.any(), (dc[[14, 15, 16, 17]].tolist(), r.tolist()))
    r, rl, pt, dc = sec(6.1)
    check("by the second: none beyond 6 s of way (6.1), nothing counted", dc[16] == 0 and not r.any(), dc[[16, 17]].tolist())
    # THE NEAR MISS at NEAR_PAY 0: counted, paid 0
    env.nm_pay = np.zeros(env.n, np.float64)
    env.nm_bud = np.ones(env.n, np.float64)
    env.hp[:] = 100.0
    N_ = env.stats.setdefault("near_miss", np.zeros(6))
    n0 = N_.copy()
    ep_ = np.asarray(env.state[j, :3], np.float64) + np.array([60.0, 0.0, 0.0])
    env._near_miss(i, E.RL, ep_, [], env.state)
    check("the near miss at NEAR_PAY 0: a rocket 60 units from the enemy's box, unhurt: counted (paid count +1, its grade 1) and its pay exactly 0",
          N_[1] - n0[1] == 1 and N_[3] == n0[3] and not env.nm_pay.any(), ((N_ - n0).tolist(), env.nm_pay.tolist()))
    # A WHOLE RUN with every switch of the command: the dropped terms exactly 0 everywhere; the counters count
    import fight22 as F22
    assert F22.SPLIT == "22c"
    E2, env2 = make_env(seed=9, matches=8)
    rng = np.random.default_rng(3)
    nz_ = {k_: 0 for k_ in DROPPED}
    paid = {k_: 0.0 for k_ in DROPPED + ("rail_pick", "rail")}
    worst_sp, frames = 0.0, 0
    for t in range(3000):
        act = np.stack([rng.integers(0, d_, env2.n) for d_ in E2.ACTION_DIMS], 1)
        act[:, 5] = rng.random(env2.n) < 0.5
        act = np.concatenate([act, (3 + 4 * int(t % 8 == 0) + np.zeros(env2.n, np.int64))[:, None]], 1)
        o_, r_, d_, info = env2.step(act)
        P = np.asarray(info["pay_terms"], np.float64)
        for nm_ in paid:
            col_ = P[:, E2.PT_IX[nm_]]
            paid[nm_] += float(np.abs(col_).sum())
            if nm_ in DROPPED:
                nz_[nm_] += int(np.count_nonzero(col_))
        p4_ = F22.pay_parts(E2, info)
        worst_sp = max(worst_sp, float(np.abs(p4_[:, :4].sum(1) - np.asarray(r_, np.float64)).max()))
        frames += 1
    check("a whole run (8 matches x 3,000 frames, random actions, 2.2d's switches): contest, contest_sec, rail_line, near_miss exactly 0.0 on every "
          "seat of every frame", all(v_ == 0 for v_ in nz_.values()) and all(paid[k_] == 0.0 for k_ in DROPPED),
          "non-zero entries {}; sizes {}".format(nz_, {k_: paid[k_] for k_ in DROPPED}))
    check("... rail_pick and rail (the far rail) present and paid", paid["rail_pick"] > 0 and "rail" in E2.PT_IX,
          {k_: round(paid[k_], 4) for k_ in ("rail_pick", "rail")})
    check("the pay split's parts (2.2c's groups) sum to the frame's pay", worst_sp < 1e-5, worst_sp)
    C2, N2, RW2, FS2 = (env2.stats.get(k_) for k_ in ("contest", "near_miss", "rail_would", "free_see"))
    check("the counters count: the contest pay's (the enemy's big pickups, free, pressured), the near miss's (bursts near, counted at pay 0), "
          "RAIL_WOULD's windows, FREE_SEE's", C2 is not None and C2[0] > 0 and C2[7] > 0 and N2 is not None and N2[0] > 0 and RW2 is not None
          and RW2[..., 0].sum() > 0 and FS2 is not None and FS2[[0, 2, 4]].sum() > 0,
          dict(contest=dict(zip(("big", "pressured", "free", "steals", "by_sec_frames", "cap", "pay_to", "pay_from"),
                                [C2[0], C2[1], C2[7], C2[11], C2[16], C2[17], C2[12], C2[13]])),
               near_miss=N2.tolist(), rail_would_windows=RW2[..., 0].tolist(), rail_would_possible=RW2[..., 1].tolist(),
               rail_would_dealt=np.round(RW2[..., 2], 1).tolist(), free_see=FS2.tolist()))
    check("... the contest pay's pay columns and the cap 0 in the whole run", C2[12] == 0 and C2[13] == 0 and C2[14] == 0 and C2[15] == 0 and C2[17] == 0,
          C2[12:18].tolist())
    rail_would_cases(E, env)
    free_see_cases(E, env)
    print("ALL PASSED" if not FAILS else "FAILED: {}".format(FAILS))


def _aim_at(E, env, i, tgt):
    """seat i's yaw and pitch set to look from his eye at the point tgt"""
    eye = env._eye(env.state)[i].astype(np.float64)
    to = np.asarray(tgt, np.float64) - eye
    env.yaw[i] = np.degrees(np.arctan2(to[1], to[0]))
    env.pitch[i] = -np.degrees(np.arctan2(to[2], np.hypot(to[0], to[1])))


def rail_would_cases(E, env):
    """(RAIL_WOULD) constructed frames on a seat pair of a running simulator with a clear line between them"""
    s = env.state
    i, j = 0, 1
    eye = env._eye(s)
    if not env._los(eye[i:i + 1].astype(np.float32), (s[j:j + 1, :3] + np.array([0, 0, 8.0])).astype(np.float32))[0]:
        found = False
        for t in range(400):                                 # (walk on until the two see each other)
            env.step(np.zeros((env.n, len(E.ACTION_DIMS) + 1), np.int64)[:, :len(E.ACTION_DIMS)])
            s = env.state
            eye = env._eye(s)
            env.hp[:] = 100.0
            if env._los(eye[i:i + 1].astype(np.float32), (s[j:j + 1, :3] + np.array([0, 0, 8.0])).astype(np.float32))[0]:
                found = True
                break
        if not found:
            check("RAIL_WOULD: a frame with a clear line between seats 0 and 1 found", False)
            return
    env.hp[:] = 100.0
    env.script[:] = 0
    env.run_k[:] = -1
    env.rw_t0 = None
    RW = env.stats.setdefault("rail_would", np.zeros((4, 2, 3)))
    vis = np.zeros(env.n, bool)
    vis[i] = True
    env.visible = vis
    d_ = float(np.linalg.norm(s[j, :3] - s[i, :3]))
    b_ = int(np.digitize([d_], E.RW_BANDS)[0])
    own_ = int(bool(env.has[i, E.RG]))
    r0 = RW.copy()
    _aim_at(E, env, i, s[j, :3] + np.array([0, 0, 8.0]))
    env._rw_frame(s, {"by": {(i, j): 30.0}})
    check("RAIL_WOULD: the enemy in his sight, his crosshair on the enemy's body with a clear line: a window open, a hit marked",
          env.rw_t0[i] >= 0 and bool(env.rw_hit[i]), dict(t0=int(env.rw_t0[i]), hit=bool(env.rw_hit[i]), dist=round(d_, 1), band=b_, own=own_))
    for f_ in range(58):
        env._rw_frame(s, {"by": {(i, j): 30.0}})
    check("... after 59 frames the window still open (nothing booked)", env.rw_t0[i] >= 0 and np.array_equal(RW, r0), (RW - r0)[b_, own_].tolist())
    env._rw_frame(s, {"by": {(i, j): 30.0}})
    dl_ = (RW - r0)[b_, own_]
    check("... at the 60th frame (1.5 s) booked in band {} (distance {:.0f}), rail owned {}: 1 window, 80 possible, 60 x 30 = 1800 dealt; the seat "
          "free".format(b_, d_, own_), dl_.tolist() == [1.0, 80.0, 1800.0] and env.rw_t0[i] < 0 and float(np.abs(RW - r0).sum()) == 1881.0, dl_.tolist())
    r1 = RW.copy()
    env.yaw[i] = env.yaw[i] + 90.0
    env._rw_frame(s, {"by": {}})
    check("the same seat looking 90 degrees away: a new window (no overlap: it opens only now), no hit", env.rw_t0[i] >= 0 and not bool(env.rw_hit[i]))
    for f_ in range(59):
        env._rw_frame(s, {"by": {}})
    dl_ = (RW - r1)[b_, own_]
    check("... booked: 1 window, 0 possible, 0 dealt", dl_.tolist() == [1.0, 0.0, 0.0], dl_.tolist())
    env.visible = np.zeros(env.n, bool)
    r2 = RW.copy()
    for f_ in range(70):
        env._rw_frame(s, {"by": {(i, j): 30.0}})
    check("the enemy out of his sight: no window opens, nothing booked (the damage outside a window not counted)", env.rw_t0[i] < 0 and np.array_equal(RW, r2))
    env.visible = vis
    _aim_at(E, env, i, s[j, :3] + np.array([0, 0, 8.0]))
    hp0 = env.hp.copy()
    env.hp[j] = 0.0
    env._rw_frame(s, {"by": {}})
    check("the enemy dead: no window opens", env.rw_t0[i] < 0)
    env.hp[:] = hp0


def free_see_cases(E, env):
    """(FREE_SEE) _free_see on constructed cases: the item seen from a place on a clear line, from behind a wall, and a dead seat"""
    s = env.state.copy()
    k = env.cb_lab.index("MH")
    it = int(env.cb_it[k])
    ip = env.item_pos[it].astype(np.float64)
    FS = env.stats.setdefault("free_see", np.zeros(6))
    j = 1
    env.hp[:] = 100.0
    env.duck[:] = False
    # a place on a clear line: the item's own place 40 units up (eye height above it); one behind a wall: the farthest walkable node without a line
    s[j, :3] = ip + np.array([0, 0, 0.0], np.float32)
    f0 = FS.copy()
    env._free_see(j, it, 0.0, s)
    check("FREE_SEE: standing on the item: counted with a line", (FS - f0).tolist()[:3] == [1.0, 0.0, 0.0], (FS - f0).tolist())
    nodes = np.asarray(env.route.nodes, np.float64) if env.route is not None else np.zeros((0, 3))
    eyes = (nodes + np.array([0, 0, float(E.VIEW_H)])).astype(np.float32)
    los = env._los(eyes, np.repeat((ip + np.array([0, 0, 16.0]))[None], len(nodes), 0).astype(np.float32)) if len(nodes) else np.zeros(0, bool)
    if (~los).any():
        q = int(np.nonzero(~los)[0][0])
        s[j, :3] = nodes[q]
        f0 = FS.copy()
        env._free_see(j, it, 1234.0, s)
        check("FREE_SEE: from a route node with no line to the mega: counted without, its distance summed", (FS - f0).tolist()[2:4] == [1.0, 1234.0]
              and (FS - f0)[0] == 0, (FS - f0).tolist())
    else:
        check("FREE_SEE: a route node with no line to the mega found", False)
    env.hp[j] = 0.0
    f0 = FS.copy()
    env._free_see(j, it, 500.0, s)
    check("FREE_SEE: a dead seat: counted dead, not with or without", (FS - f0).tolist() == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0], (FS - f0).tolist())
    env.hp[j] = 100.0


def watch():
    """tools/run/watch.py's queue on a simulated run: a fake clock, the trainer's saves every 10 updates to 80, its exit line"""
    import importlib
    import shutil
    tmp_ = tempfile.mkdtemp(prefix="w22d_")
    os.environ["QLBOT_ROOT"] = tmp_
    run_ = "scratch_watch"
    D = os.path.join(tmp_, "data", "sim_runs", run_)
    os.makedirs(os.path.join(D, "keep"))
    os.environ.update(CHECK_AT="10,30,50,60,70", CHECK_REF_AT="60", CHECK_END="1", CTRL_PREV="PREV.pt", CTRL_REF="REF.pt", CTRL_PREV_LABEL="the start",
                      CTRL_REF_LABEL="2.1d's end")
    pol = os.path.join(D, "policy.pt")
    open(pol, "w").write("0")
    met = os.path.join(D, "metrics.jsonl")
    open(met, "w").close()
    sys.argv = ["watch.py", run_]
    W = importlib.import_module("watch")
    clock = [1.0e9]
    mt = {pol: clock[0]}
    played = []
    TH = [None]

    class FakeTime:
        @staticmethod
        def time():
            return clock[0]

        @staticmethod
        def sleep(s_):
            import threading as th_
            import time as rt_
            if th_.current_thread() is TH[0]:                # (the watch's own loop moves the fake clock; the queue's thread waits for real)
                clock[0] += s_
                sim_step()
            else:
                rt_.sleep(0.002)

        @staticmethod
        def strftime(f_, *a_):
            return "T{:.0f}".format(clock[0] - 1.0e9)
    state = dict(u=0, next_t=clock[0] + 380.0, ended=False)

    def sim_step():                                          # (the trainer: an update every 380 s; a save at every 10th; at 80 its exit line)
        while clock[0] >= state["next_t"] and state["u"] < 80:
            state["u"] += 1
            open(met, "a").write(json.dumps({"update": state["u"]}) + "\n")
            if state["u"] % 10 == 0:
                mt[pol] = state["next_t"]
            state["next_t"] += 380.0
        if state["u"] >= 80 and not state["ended"] and clock[0] >= state["next_t"]:
            state["ended"] = True
            mt[pol] = clock[0]
            open(os.path.join(tmp_, "data", "sim_runs", run_ + ".log"), "a").write("trainer stuff\nexit 0\n")
    W.time = FakeTime
    W.os.path.getmtime = lambda p_: mt.get(p_, 0.0)
    real_copy = shutil.copy
    W.shutil.copy = lambda a_, b_: real_copy(a_, b_)

    def fake_check(k_, n_, c_, l_):
        played.append((n_, c_, os.path.basename(k_)))
        import time as rt_
        rt_.sleep(0.05)
    W.check_games = fake_check
    W.check_panel = lambda pol_, upd_, busy_: None
    import threading
    th = threading.Thread(target=W.main, daemon=True)
    TH[0] = th
    th.start()
    th.join(120)
    W.os.path.getmtime = os.path.getmtime
    print("      the checks played, in order: {}".format(played))
    want = [(10, "PREV.pt"), (30, "PREV.pt"), (50, "PREV.pt"), (60, "PREV.pt"), (60, "REF.pt"), (70, "PREV.pt"), (80, "PREV.pt")]
    check("the watcher's queue: 10, 30, 50, 60 (the start, then 2.1d's end), 70 and the end (80), in order, none skipped, the watch done",
          [(a_, b_) for a_, b_, _ in played] == want and not th.is_alive(), played)
    check("... the end check plays the save copied after the trainer's exit (keep/policy_end_check_80.pt)", bool(played) and played[-1][2] == "policy_end_check_80.pt",
          played[-1:] if played else None)


def main():
    {"unit": unit, "live": live, "watch": watch}[sys.argv[1]](*sys.argv[2:])
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()

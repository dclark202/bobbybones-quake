"""v0.4.1 checks of the brain's token (sim/btoken.py, sim/attn.py "btok") and the readout ahead (sim/ahead.py), on the CPU:

    CUDA_VISIBLE_DEVICES=-1 python tools/btoken_check.py [--policy data/sim_runs/<run>/policy.pt]

  attn    the attention part with the token at gate 0 (bt given or not) answers bit for bit as the same part without the
          token's layers; at a gate above 0 the answer moves; numpy (forward_np) = torch at every gate; the weight on the token
          in each softmax is exactly gate x its weight at gate 1 (unnormalised)
  turn    an answer that is the truth at the tick, turned to a later pose, is the truth seen from that pose (the simulator's
          own en_fwd / en_left rule); a reset clears it; the zones' top places are the centres seen from the pose
  gate    the schedule: shut through the delay, the rise, the cap, a hold (open 0), a close (cap 0)
  ahead   the labels of a made-up rollout: the place in 1, 2, 4 s in the facing of now, the masks at a reset and past the end;
          the appearance band
  brain   (with --policy) the policy's attention part of a real save, with and without the token at gate 0: bit for bit
"""
import argparse
import math
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import ahead as ahead_  # noqa: E402
import attn as attn_  # noqa: E402
import btoken as btoken_  # noqa: E402

OK = []


def check(name, cond, info=""):
    OK.append(bool(cond))
    print("{} {}{}".format("PASS" if cond else "FAIL", name, (": " + str(info)) if info else ""), flush=True)


def lay_small():
    kinds = [dict(name="self", idx=[[0, 1, 2]]), dict(name="enemy", idx=[[3, 4, 5, 6]]), dict(name="item", idx=[[7, 8], [9, -1]])]
    return dict(obs_dim=10, D=96, heads=4, kinds=kinds, read=[4, 0], tokens=5, gated=True)


def t_attn(lay=None, x=None, sd=None):
    torch.manual_seed(0)
    lay = lay or lay_small()
    F = 17
    m0 = attn_.make_module(lay, 256, seed=3)
    m1 = attn_.make_module(dict(lay, btok=F), 256, seed=3)
    if sd is not None:
        m0.load_state_dict(sd, strict=False)
    with torch.no_grad():
        m0.door.weight.normal_(0, 0.1) if sd is None else None
    m1.load_state_dict(m0.state_dict(), strict=False)
    with torch.no_grad():
        if getattr(m0, "gate", None) is not None:
            m1.gate.copy_(m0.gate)
    x = torch.randn(64, lay["obs_dim"]) if x is None else x
    bt = torch.randn(64, F)
    with torch.no_grad():
        y0 = m0(x)
        y1a = m1(x)
        y1b = m1(x, bt=bt)
        m1.bgate = 0.0
        y1c = m1(x, bt=bt, bg=0.0)
        y1g = m1(x, bt=bt, bg=0.3)
        y1h = m1(x, bt=bt, bg=1.0)
    check("attn: gate 0, no token given = the part without the token (bit for bit)", torch.equal(y0, y1a))
    check("attn: gate 0, token given = the part without the token (bit for bit)", torch.equal(y0, y1b) and torch.equal(y0, y1c))
    d3 = float((y1g - y0).abs().max())
    d1 = float((y1h - y0).abs().max())
    check("attn: gate 0.3 / 1 moves the answer", d3 > 0 and d1 > d3 * 0.5, "max change {:.3g} at 0.3, {:.3g} at 1".format(d3, d1))
    P = attn_.params_np({"attn." + k: v for k, v in m1.state_dict().items()}, "attn.")
    L1 = dict(lay, btok=F)
    for g in (0.0, 0.3, 1.0):
        yn = attn_.forward_np(L1, P, x.numpy(), bt=bt.numpy(), bg=g)
        with torch.no_grad():
            yt = m1(x, bt=bt, bg=g).numpy()
        check("attn: numpy = torch at gate {:g}".format(g), np.abs(yn - yt).max() < 1e-4, "max diff {:.2g}".format(np.abs(yn - yt).max()))
    yn0 = attn_.forward_np(lay, attn_.params_np({"attn." + k: v for k, v in m0.state_dict().items()}, "attn."), x.numpy())
    yn1 = attn_.forward_np(L1, P, x.numpy(), bt=bt.numpy(), bg=0.0)
    check("attn: numpy gate 0 = numpy without the token (bit for bit)", np.array_equal(yn0, yn1))
    # the softmax weight on the token is gate x its unnormalised weight: log(g) added to the scores
    s = torch.randn(10)
    for g in (0.25, 0.5):
        w1 = torch.softmax(torch.cat([s, torch.tensor([0.7])]), 0)
        wg = torch.softmax(torch.cat([s, torch.tensor([0.7 + math.log(g)])]), 0)
        r_ = (wg[-1] / wg[:-1].sum()) / (w1[-1] / w1[:-1].sum())
        check("attn: the token's weight against the rest scales by exactly the gate ({:g})".format(g), abs(float(r_) - g) < 1e-6, float(r_))
    # the gradient reaches the token's layer only when it is open
    m1.zero_grad()
    m1(x, bt=bt, bg=0.0).sum().backward()
    g0 = m1.btok_emb.weight.grad
    check("attn: at gate 0 the token's layer gets no gradient", g0 is None or float(g0.abs().sum()) == 0.0)


def t_turn():
    rng = np.random.default_rng(1)
    n = 50
    L = btoken_.layout(dict(parts=["pos", "vel", "band", "hand", "own"], weights=dict(pos=1, vel=0, band=0.5, hand=0.25, own=0.25)),
                       dict(parts=["zone", "spd", "dir"], weights=dict(zone=0.5, spd=0.25, dir=0.25)), 8, 35)
    check("turn: the feature list", "vel_f" not in L["feats"] and "zone_23" in L["feats"] and "dir_c" in L["feats"], "{} numbers".format(L["dim"]))
    T = btoken_.Token(n, L)
    me0 = rng.uniform(-1000, 1000, (n, 3)).astype(np.float32)
    yaw0 = rng.uniform(-180, 180, n).astype(np.float32)
    en = rng.uniform(-1000, 1000, (n, 3))
    ev = rng.uniform(-300, 300, (n, 2))                                    # the enemy's way (map)

    def rel(me, yaw, w):                                                   # the simulator's rule (aux: en_fwd, en_left, en_up)
        r = np.radians(yaw.astype(np.float64))
        c, s = np.cos(r), np.sin(r)
        d = w - me
        return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1], d[:, 2]], 1)

    def relv(yaw, v):
        r = np.radians(yaw.astype(np.float64))
        c, s = np.cos(r), np.sin(r)
        return np.stack([c * v[:, 0] + s * v[:, 1], -s * v[:, 0] + c * v[:, 1]], 1)
    o1 = np.zeros((n, 27))
    o1[:, 0:3] = rel(me0, yaw0, en) / 1000.0
    o2 = np.zeros((n, 28))
    o2[:, 0] = 5.0                                                        # zone 0 the likeliest
    o2[:, 26:28] = relv(yaw0, ev) / 50.0                                   # eta along his way, turned to the tick's facing
    zm = np.zeros(n, np.int64)                                            # bloodrun
    obs = np.zeros((n, 40), np.float32)
    T.see(obs)
    f0 = T.features(np.c_[me0, yaw0], zm).astype(np.float32)
    check("turn: no answer before the first tick (zeros but the time unseen)", np.abs(f0[:, :-3]).max() == 0 and (f0[:, -1] == 0).all())
    T.answer(None, o1, o2, np.c_[me0, yaw0], zm)
    me1 = me0 + rng.uniform(-200, 200, (n, 3)).astype(np.float32)
    yaw1 = ((yaw0 + rng.uniform(-90, 90, n) + 180) % 360 - 180).astype(np.float32)
    f1 = T.features(np.c_[me1, yaw1], zm).astype(np.float64)
    ix = T.ix
    want = rel(me1, yaw1, en) / 1000.0
    got = f1[:, [ix["pos_f"], ix["pos_l"], ix["pos_u"]]]
    check("turn: the place re-turned to a later pose is the truth from there", np.abs(got - want).max() < 2e-3, "max {:.2g} (half precision)".format(np.abs(got - want).max()))
    dw = relv(yaw1, ev)
    dw = dw / np.linalg.norm(dw, axis=1, keepdims=True)
    gd = f1[:, [ix["dir_c"], ix["dir_s"]]]
    gd = gd / np.linalg.norm(gd, axis=1, keepdims=True)
    check("turn: the direction re-turned to a later facing", np.abs(gd - dw).max() < 5e-3, "max {:.2g}".format(np.abs(gd - dw).max()))
    ct, kz = btoken_.zone_table()
    zc = ct[0, 0][None].astype(np.float64)
    wz = rel(me1, yaw1, np.repeat(zc, n, 0)) / 1000.0
    gz = f1[:, [ix["ztop0_f"], ix["ztop0_l"], ix["ztop0_u"]]]
    check("turn: the likeliest zone's centre from the pose now (bloodrun zone 0, {} zones)".format(kz[0]), np.abs(gz - wz).max() < 2e-3)
    check("turn: the zone odds sum to 1 over the map's count", abs(f1[:, ix["zone_0"]:ix["zone_0"] + 24].sum(1) - 1).max() < 2e-3
          and np.abs(f1[:, ix["zone_0"] + int(kz[0]):ix["zone_0"] + 24]).max() == 0)
    f2 = T.features(np.c_[me1, yaw1], zm).astype(np.float32)
    check("turn: the age counts on (0 on the first frame after the tick)", abs(f2[0, ix["age"]] - 1.0 / 8) < 1e-3 and f1[0, ix["age"]] == 0)
    d = np.zeros(n)
    d[:10] = 1
    T.reset(d)
    f3 = T.features(np.c_[me1, yaw1], zm).astype(np.float32)
    check("turn: a reset clears the answer (only the time unseen is left)", np.abs(f3[:10, :-3]).max() == 0 and (f3[:10, -1] == 0).all()
          and (f3[10:, -1] == 1).all())
    obs[:5, 35] = 1.0
    T.see(obs)
    f4 = T.features(np.c_[me1, yaw1], zm).astype(np.float32)
    check("turn: the time unseen is 0 where he notices the enemy", (f4[:5, ix["unseen"]] == 0).all() and (f4[5:, ix["unseen"]] > 0.9).all())


def t_gate():
    g, last = 0.0, None
    seq = []
    for m in np.arange(0, 400, 10.0):
        g = btoken_.gate_step(g, m, last, 0.0, 60.0, 240.0, 1.0)
        last = m
        seq.append(g)
    check("gate: shut for the first hour", max(seq[:7]) == 0.0, seq[:8])
    check("gate: half open two hours after the delay, open at five hours", abs(seq[18] - 0.5) < 1e-9 and seq[-1] == 1.0, (seq[18], seq[-1]))
    h = btoken_.gate_step(0.4, 200.0, 190.0, 0.0, 60.0, 0.0, 1.0)
    check("gate: open 0 holds", h == 0.4)
    c = btoken_.gate_step(0.4, 200.0, 190.0, 0.0, 60.0, 240.0, 0.0)
    check("gate: cap 0 shuts it at once", c == 0.0)
    c2 = btoken_.gate_step(0.4, 200.0, 190.0, 0.0, 60.0, 240.0, 0.3)
    check("gate: a cap below it holds it at the cap", c2 == 0.3)


def t_ahead():
    T, N, K = 384, 3, 8
    cols = ahead_.COLS
    C = {c: i for i, c in enumerate(cols)}
    aux = torch.zeros(T + 1, N, len(cols))
    t = torch.arange(T + 1).float()
    ex, ey = 100.0 + 3.0 * t, -50.0 + 1.0 * t                              # the enemy on the map
    for i in range(N):
        mx, my, yw = 10.0 * i + 0.5 * t, 0.0 * t, (20.0 * i + 0.3 * t)
        r = torch.deg2rad(yw)
        dx, dy = ex - mx, ey - my
        aux[:, i, C["x"]], aux[:, i, C["y"]], aux[:, i, C["yaw"]] = mx, my, yw
        aux[:, i, C["en_fwd"]] = torch.cos(r) * dx + torch.sin(r) * dy
        aux[:, i, C["en_left"]] = -torch.sin(r) * dx + torch.cos(r) * dy
    aux[..., C["trk_on"]] = 1.0
    aux[..., C["en_target"]] = 2.0
    aux[200:, 1, C["en_in_view"]] = 1.0                                    # seat 1 sees him from frame 200
    done = torch.zeros(T, N)
    done[100, 2] = 1.0                                                     # seat 2 dies after frame 100
    fut, fm, tg, tm, ap, am = ahead_.labels(aux, done, cols, K, 17)
    k, j, i = 2, 0, 0                                                      # tick 2 (frame 23), 1 s ahead
    f0 = 23
    r = math.radians(float(aux[f0, i, C["yaw"]]))
    dx, dy = float(ex[f0 + 40] - aux[f0, i, C["x"]]), float(ey[f0 + 40] - aux[f0, i, C["y"]])
    want = (math.cos(r) * dx + math.sin(r) * dy, -math.sin(r) * dx + math.cos(r) * dy)
    got = (float(fut[k, i, j, 0]) * 1000, float(fut[k, i, j, 1]) * 1000)
    check("ahead: the place in 1 s in the facing of now", abs(got[0] - want[0]) < 0.05 and abs(got[1] - want[1]) < 0.05, (got, want))
    check("ahead: past the rollout's end left out", fm[-1, 0].sum() == 0 and fm[(T - 160) // K - 1, 0, 2] == 1 and fm[(T - 160) // K + 1, 0, 2] == 0)
    kk = 11                                                                # tick 11 = frame 95: 1 s ahead crosses the reset after 100
    check("ahead: across a reset left out", fm[kk, 2, 0] == 0 and fm[kk, 0, 0] == 1 and fm[13, 2, 0] == 1)
    check("ahead: the target", bool((tg == 2).all()) and bool((tm == 1).all()))
    kb = (200 - 7) // K                                                    # the tick at frame 199 - ...: seat 1 sees him at 200
    f_ = kb * K + K - 1
    band = int(sum((200 - f_) * 0.025 >= e for e in ahead_.APPEAR))
    check("ahead: the appearance band", int(ap[kb, 1]) == band and am[kb, 1] == 1 and am[30, 1] == 0, (int(ap[kb, 1]), band))
    check("ahead: no appearance within 6 s counts only with 6 s of rollout left", am[0, 0] == 1 and int(ap[0, 0]) == 3 and am[W_last(T, K), 0] == 0)
    m = ahead_.make_module(256, ahead_.layout(17))
    o = m(torch.zeros(T // K, N, 256))
    lv, pv, nv = ahead_.loss(o, ahead_.layout(17), (fut, fm, tg, tm, ap, am), ahead_.DEFAULT_W, torch.ones(T // K, N))
    check("ahead: the start's loss is finite", bool(torch.isfinite(lv)), [round(float(x), 3) for x in pv])


def W_last(T, K):
    return T // K - 1


def t_env(mp="bloodrun"):
    """his pose as the trainer reads it (info["aux"]) and as the checks read it (the simulator): the same numbers"""
    os.environ["TRACK_TRUTH"] = "1"
    os.environ["TRACK_Z"] = "1"
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=2, seed=5, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    env.reset() if hasattr(env, "reset") else None
    rng = np.random.default_rng(0)
    bad = 0
    for t in range(60):
        a_ = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        env.step(a_)
        p1, z1 = btoken_.pose_from_aux(env.aux(), E.AUX_COLS)
        p2, z2 = btoken_.pose_from_env(env, mp)
        bad += int(not (np.array_equal(p1, p2) and np.array_equal(z1, z2)))
    check("env: his pose from info['aux'] (training) = from the simulator (checks), 60 frames", bad == 0, "{} frames differ".format(bad))


def t_policy(path):
    ck = torch.load(path, weights_only=False, map_location="cpu")
    lay = ck["attn"]
    lay = {k: v for k, v in lay.items() if k != "btok"}
    sd = {k[5:]: v for k, v in ck["model"].items() if k.startswith("attn.") and not k.startswith("attn.btok_")}
    x = torch.randn(256, lay["obs_dim"]) * 1.5
    m0 = attn_.make_module(lay, 256)
    m0.load_state_dict(sd, strict=True)
    m1 = attn_.make_module(dict(lay, btok=72), 256)
    m1.load_state_dict(sd, strict=False)
    bt = torch.randn(256, 72)
    with torch.no_grad():
        y0, y1, y2 = m0(x), m1(x, bt=bt, bg=0.0), m1(x, bt=bt, bg=1.0)
    check("brain: the save's attention part with the token at gate 0 (bit for bit)", torch.equal(y0, y1))
    check("brain: ... and at gate 1 it moves", float((y2 - y0).abs().max()) > 0, "max change {:.3g} (the door's output, mean |y| {:.3g})".format(
        float((y2 - y0).abs().max()), float(y0.abs().mean())))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="")
    ap.add_argument("--env", action="store_true", help="also the pose check in a simulator (bloodrun)")
    a = ap.parse_args()
    t_attn()
    t_turn()
    t_gate()
    t_ahead()
    if a.policy:
        t_policy(a.policy)
    if a.env:
        t_env()
    print("{} of {} passed".format(sum(OK), len(OK)))
    sys.exit(0 if all(OK) else 1)

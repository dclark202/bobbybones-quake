"""v0.4.1: the plugins' forward pass (plugins/netpass.py) against the checks' (sim/test_suite.py Policy) with the brain's token, on
the CPU. A game on one map is played by the network on both seats (its token open), its frames are recorded (inputs, the legs'
inputs, each seat's pose as btoken.pose_from_env gives it, resets: the simulator's and some forced ones off the tick clock), and
replayed through both paths at gates 0, 0.1 and 1 (netpass by NET_BTOKEN_GATE on the exported file): the actions, the logits,
the log-probs of the actions drawn, the token and the whole memory array frame by frame. With --old-npz (an export by the
export_duel.py before v0.4.1) and --old-netpass (the netpass.py before), gate 0 is also set beside the plugin as it was.

    CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/netpass_check.py --policy <policy.pt> --npz <its export by
        sim/export_duel.py> [--legs-net <the export's legs.npz>] [--map bloodrun] [--frames 800] [--env duel_env_ffa]

The bar: every difference 0 (the two paths make the same sums in the same order). Run 2026-10-23 on scratch_v041_d's save:
0 at every gate, 1,600 frames on Blood Run and 900 on Aerowalk; the server image's numpy (2.2.6) the same.
"""
import argparse
import importlib
import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))

ap = argparse.ArgumentParser()
ap.add_argument("--policy", required=True)
ap.add_argument("--npz", required=True)
ap.add_argument("--legs-net", default="", help="the movement network the simulator needs with LEGS=1 (default: legs.npz beside --npz)")
ap.add_argument("--map", default="bloodrun")
ap.add_argument("--frames", type=int, default=800)
ap.add_argument("--env", default="duel_env_ffa")
ap.add_argument("--old-npz", default="")
ap.add_argument("--old-netpass", default="")
a = ap.parse_args()

P0 = dict(np.load(a.npz))
os.environ.update({k: str(v) for k, v in json.loads(str(P0.get("env_vars", "{}"))).items()})   # (as the plugins: before the module)
os.environ["LEGS_NET"] = a.legs_net or os.path.join(os.path.dirname(os.path.abspath(a.npz)), "legs.npz")
E = importlib.import_module(a.env)
import test_suite as T  # noqa: E402
import btoken as BT  # noqa: E402
import netpass as N  # noqa: E402

FR, MAP = a.frames, a.map
nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(MAP))
env = E.DuelEnv(os.path.join(ROOT, "data", "maps", MAP + ".bsp"), n_matches=1, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
pol = T.Policy(a.policy, seed=3)
assert pol.btok is not None, "this network has no brain token"
pol.set_gate(1.0)
T.set_delays(E, env, [(np.arange(0, 2, 2), pol.react_ms, pol.acquire_ms), (np.arange(1, 2, 2), pol.react_ms, pol.acquire_ms)])
env.kind_p = (1.0, 0.0, 0.0, 0.0)
env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
env.round_t[:] = 1e9
obs, _, _, _ = env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
env.round_len = env.arena_len = 1e9
env.round_t[:] = 0.0
env.script[:] = 0
n = env.n
h = pol.zeros(n)
rec = dict(obs=[], xl=[], pose=[], zmap=[], clr=[])
FORCE = {int(FR * 0.19): [1], int(FR * 0.49) | 1: [0], int(FR * 0.75): [0, 1]}
for t in range(FR):
    pz, zz = BT.pose_from_env(env, MAP)
    xl = env.legs_prep() if pol.needs_xl else None
    for k, v in (("obs", obs), ("xl", xl), ("pose", pz), ("zmap", zz)):
        rec[k].append(None if v is None else np.array(v).copy())
    act, h = pol.act(obs, h, xl=xl, pose=pz, zmap=zz)
    if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
        env.legs_lg = pol.legs_logits(env.legs_prep())
    obs, r, done, info = env.step(act)
    d = np.asarray(done, bool).copy()
    for k in FORCE.get(t, []):
        d[k] = True
    rec["clr"].append(d)
    if d.any():
        pol.clear(h, d)
print("recorded {} frames on {} (resets on {} seat-frames, zones' map {})".format(FR, MAP, int(np.sum(rec["clr"])), int(rec["zmap"][0][0])), flush=True)


def watch(code):
    box = []

    def prof(frame, event, arg):
        if event == "return" and frame.f_code is code:
            box.append((np.array(frame.f_locals["logits"], np.float64), None if frame.f_locals.get("bt") is None else np.array(frame.f_locals["bt"])))
    return box, prof


def logp(lg, dims, act):
    o = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    s = np.zeros(len(lg))
    for j in range(len(dims)):
        l_ = lg[:, o[j]:o[j + 1]] - lg[:, o[j]:o[j + 1]].max(1, keepdims=True)
        s += l_[np.arange(len(lg)), act[:, j]] - np.log(np.exp(l_).sum(1))
    return s


def play_policy(g):
    p = T.Policy(a.policy, seed=11)
    p.set_gate(g)
    hh = p.zeros(n)
    box, prof = watch(T.Policy.act.__code__)
    A_, H_ = [], []
    for t in range(FR):
        sys.setprofile(prof)
        ac, hh = p.act(rec["obs"][t], hh, xl=rec["xl"][t], **({"pose": rec["pose"][t], "zmap": rec["zmap"][t]} if p.needs_pose else {}))
        sys.setprofile(None)
        A_.append(ac), H_.append(hh.copy())
        if rec["clr"][t].any():
            p.clear(hh, rec["clr"][t])
    return np.array(A_), np.array(H_), box, p.dims


def play_net(mod, path, g):
    if g is not None:
        os.environ["NET_BTOKEN_GATE"] = str(g)
    P, A = mod.load(path)
    os.environ.pop("NET_BTOKEN_GATE", None)
    rng = np.random.default_rng(11)
    hh = np.zeros((n, mod.width(P)), np.float32)
    box, prof = watch(mod.step.__code__)
    A_, H_ = [], []
    for t in range(FR):
        kw = dict(pose=rec["pose"][t], zmap=rec["zmap"][t]) if getattr(mod, "needs_pose", lambda P_: False)(P) else {}
        sys.setprofile(prof)
        ac, hh = mod.step(P, A, rec["obs"][t], hh, rng, xl=rec["xl"][t] if mod.needs_xl(P) else None, **kw)
        sys.setprofile(None)
        A_.append(ac), H_.append(hh.copy())
        if rec["clr"][t].any():
            mod.clear(P, hh, rec["clr"][t])
    return np.array(A_), np.array(H_), box, P


def compare(tag, x, y, dims):
    (Ax, Hx, bx), (Ay, Hy, by) = x[:3], y[:3]
    lx, ly = np.array([b[0] for b in bx]), np.array([b[0] for b in by])
    w = min(Hx.shape[-1], Hy.shape[-1])
    out = dict(action_frames_differ=int((Ax != Ay).any(-1).any(-1).sum()), logits=float(np.abs(lx - ly).max()),
               logp=float(max(np.abs(logp(lx[t], dims, Ax[t]) - logp(ly[t], dims, Ay[t])).max() for t in range(FR))),
               memory=float(np.abs(Hx[..., :w] - Hy[..., :w]).max()))
    if bx[0][1] is not None and by[0][1] is not None:
        out["token"] = float(np.abs(np.array([b[1] for b in bx]) - np.array([b[1] for b in by])).max())
    print("{:58s} {}".format(tag, json.dumps(out)), flush=True)
    return lx, all(v == 0 for v in out.values())


ok, L = True, {}
for g in (0.0, 0.1, 1.0):
    rp = play_policy(g)
    L[g], ok_ = compare("gate {:g}: test_suite.Policy vs netpass".format(g), rp, play_net(N, a.npz, g), rp[3])
    ok &= ok_
    if g == 0.0 and a.old_npz and a.old_netpass:
        sp_ = importlib.util.spec_from_file_location("netpass_old", a.old_netpass)
        NO = importlib.util.module_from_spec(sp_)
        sp_.loader.exec_module(NO)
        ok &= compare("gate 0: the old netpass and export vs the new", play_net(NO, a.old_npz, None), play_net(N, a.npz, 0.0), rp[3])[1]
print("the token moves the network: logits at gate 1 vs 0, max |diff| {:.3g}".format(float(np.abs(L[1.0] - L[0.0]).max())))
for g in (0.0, 1.0):
    os.environ["NET_BTOKEN_GATE"] = str(g)
    P, A = N.load(a.npz)
    os.environ.pop("NET_BTOKEN_GATE", None)
    rng, hh, ts = np.random.default_rng(1), np.zeros((1, N.width(P)), np.float32), []
    for t in range(FR):
        kw = dict(pose=rec["pose"][t][:1], zmap=rec["zmap"][t][:1]) if N.needs_pose(P) else {}
        t0 = time.perf_counter()
        ac, hh = N.step(P, A, rec["obs"][t][:1], hh, rng, xl=rec["xl"][t][:1] if N.needs_xl(P) else None, **kw)
        ts.append(time.perf_counter() - t0)
    ts = np.array(ts[50:]) * 1000.0
    print("netpass.step, one seat, gate {:g}: mean {:.2f} ms, p99 {:.2f}, max {:.2f}".format(g, ts.mean(), np.percentile(ts, 99), ts.max()))
print("PASS: every difference 0" if ok else "FAIL: see above")
sys.exit(0 if ok else 1)

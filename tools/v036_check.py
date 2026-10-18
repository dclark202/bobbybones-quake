"""v0.3.6 unit checks (small: 4 players, tens of frames, one core; Anaconda Python, pinned to the performance cores).

    python tools/v036_check.py ident      the inputs with RL_AIM and PREFIRE off are v0.3.5's (duel_env_v035, duel_env_ffa_v035)
                                           frame for frame on a few frames of Blood Run; with them on every older input and reward
                                           is the same, the new ones live (T_FRAMES, default 40; T_GIVE_RL=1: rockets and
                                           grenades for all from the third frame, the same in every simulator)
    python tools/v036_check.py hand       the new inputs on hand-built states on Blood Run, against numbers worked out by hand
    python tools/v036_check.py ffa        tools/ffa_check.py's two-player comparison, small (300 frames), with both switches on
    python tools/v036_check.py torch <widened.pt>   the attention part in torch (as the trainer builds it) against numpy; the
                                           new columns move nothing while the gate is shut
    python tools/v036_check.py dump <module> <out.npz>   (inside: one simulator a process)
V036_CMD: a run's .cmd whose `set` lines give the switches (the run's own: v0.3.5's solo .cmd); none: the defaults. The ways
tables a simulator works out go to ROUTE_CACHE (default: a folder in the system's temporary folder), not to data/maps."""
import os
import subprocess
import sys

import numpy as np

import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.environ.get("ROUTE_CACHE") or os.path.join(tempfile.gettempdir(), "v036_check")
os.makedirs(CACHE, exist_ok=True)
SIM = os.path.join(ROOT, "sim")
MAPS = os.path.join(ROOT, "data", "maps")
CMD = os.environ.get("V036_CMD") or ""
FRAMES = int(os.environ.get("T_FRAMES") or 40)
N_NEW = 20 + 3 * 13                                        # (RL_AIM's N_RAIM and PREFIRE's N_PREF: v0.3.6's new inputs)


def run_env():
    """a run's switches (its .cmd: V036_CMD), less the GPU and the legs' network file"""
    env = {}
    for l_ in (open(CMD, encoding="utf-8") if CMD else ()):
        l_ = l_.strip()
        if l_.lower().startswith("set ") and "=" in l_:
            k_, v_ = l_[4:].split("=", 1)
            if k_ not in ("GPU_MEM_FRACTION", "LEGS_NET"):
                env[k_] = v_
    return env


def dump(module, out):
    sys.path.insert(0, SIM)
    import importlib
    E = importlib.import_module(module)
    kw = dict(group=2) if "ffa" in module else {}
    env = E.DuelEnv(os.path.join(MAPS, "bloodrun.bsp"), n_matches=2, seed=5, nav=os.path.join(MAPS, "nav_bloodrun_sim.json"),
                    close_p=1.0, **kw)
    env.react_frames, env.acquire_frames = 4, 8
    env.kind_p = (1, 0, 0, 0)
    env.round_t[:] = 1e9
    rng = np.random.default_rng(11)
    obs, rew = [env.observe()], []
    for t in range(FRAMES):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.5
        if os.environ.get("T_GIVE_RL"):
            a[:, 6] = 0                                    # (no weapon key: the rocket launcher stays in hand)
        s = env.state                                      # turn toward the enemy, so that he is in view now and then
        to = s[np.arange(env.n) ^ 1, :3] - s[:, :3]
        ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw + 180.0) % 360.0 - 180.0
        a[:, 3] = np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1)
        if t == 2 and os.environ.get("T_GIVE_RL"):          # (the same to both simulators: rockets and grenades in hand, so the new inputs live)
            env.has[:, E.RL], env.ammo[:, E.RL], env.has[:, E.GL], env.ammo[:, E.GL] = True, 50, True, 50
            env.has[:, E.PG], env.ammo[:, E.PG] = True, 50
            a[:, 6] = 1 + E.RL
        o, r, d, info = env.step(a)
        obs.append(o.copy())
        rew.append(np.asarray(r).copy())
    np.savez(out, obs=np.array(obs), rew=np.array(rew), weapon=env.weapon)
    print(module, "obs", obs[0].shape, "frames", FRAMES)


def sub(module, out, extra=None):
    e = dict(os.environ, **run_env())
    e.update(ROUTE_CACHE=CACHE, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    for k_ in ("RL_AIM", "PREFIRE"):
        e.pop(k_, None)
    e.update(extra or {})
    subprocess.run([sys.executable, os.path.abspath(__file__), "dump", module, out], check=True, env=e)
    return np.load(out)


def ident():
    tmp = os.path.join(CACHE, "out")
    os.makedirs(tmp, exist_ok=True)
    ok = True
    for new_, old_ in (("duel_env", "duel_env_v035"), ("duel_env_ffa", "duel_env_ffa_v035")):
        a = sub(old_, os.path.join(tmp, old_ + ".npz"))
        b = sub(new_, os.path.join(tmp, new_ + "_off.npz"))
        c = sub(new_, os.path.join(tmp, new_ + "_on.npz"), dict(RL_AIM="1", PREFIRE="1"))
        k = a["obs"].shape[2]
        same_off = np.array_equal(a["obs"], b["obs"][:, :, :k]) and np.array_equal(a["rew"], b["rew"]) and not b["obs"][:, :, k:].any()
        same_on = np.array_equal(a["obs"], c["obs"][:, :, :k]) and np.array_equal(a["rew"], c["rew"])
        live = c["obs"][:, :, k:]
        print("{}: {} inputs -> {}; off: identical to {} and the new zeros: {}; on: the older inputs and rewards identical: {}; "
              "new inputs nonzero in {:.0%} of player-frames (rocket aim {:.0%}, pre-fire {:.0%})".format(
                  new_, k, b["obs"].shape[2], old_, same_off, same_on, float((live != 0).any(2).mean()),
                  float((live[:, :, :20] != 0).any(2).mean()), float((live[:, :, 20:] != 0).any(2).mean())))
        ok &= same_off and same_on
    print("IDENT", "PASS" if ok else "FAIL")
    return ok


def hand():
    """hand-built states: two players on Blood Run, the rocket launcher, the enemy seen; the numbers checked by hand"""
    os.environ.update(run_env(), ROUTE_CACHE=CACHE, RL_AIM="1", PREFIRE="1")
    sys.path.insert(0, SIM)
    import duel_env as E
    env = E.DuelEnv(os.path.join(MAPS, "bloodrun.bsp"), n_matches=1, seed=5, nav=os.path.join(MAPS, "nav_bloodrun_sim.json"), close_p=1.0)
    env.react_frames, env.acquire_frames = 0, 0
    env.kind_p = (1, 0, 0, 0)
    env.round_t[:] = 1e9
    env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))   # (a first frame: the round begins)
    R = env.route
    # two standing places 600 units apart on the floor of the walking map, a clear line between
    nodes = R.nodes[~R.dead]
    pick = None
    rng = np.random.default_rng(3)
    for _ in range(4000):
        a_, b_ = nodes[rng.integers(len(nodes))], nodes[rng.integers(len(nodes))]
        d_ = np.linalg.norm(a_[:2] - b_[:2])
        if 500 < d_ < 700 and abs(a_[2] - b_[2]) < 8 and env.w.lines(a_[None] + [0, 0, 26], b_[None] + [0, 0, 26])[0] >= 0.999:
            pick = (a_, b_)
            break
    assert pick is not None
    A_, B_ = pick
    yaw = float(np.degrees(np.arctan2(B_[1] - A_[1], B_[0] - A_[0])))
    env.w.reset(0, tuple(A_ + [0, 0, 9.0]), (0, 0, 0), yaw)
    env.w.reset(1, tuple(B_ + [0, 0, 9.0]), (0, 0, 0), yaw + 180.0)
    for _ in range(12):                                  # settle on the floor, then see each other
        env.w.step(np.zeros((env.n, 4), np.float32), np.stack([np.zeros(env.n), np.array([yaw, yaw + 180.0]), np.zeros(env.n)], 1).astype(np.float32))
    env.state = env.w.state()
    env.yaw[:] = (yaw, yaw + 180.0)
    env.pitch[:] = 0.0
    env.hp[:] = 100
    env.has[:, E.RL] = True
    env.ammo[:, E.RL] = 10
    env.weapon[:] = E.RL
    opp = np.arange(env.n) ^ 1

    def see(on, frames):
        """hand-set senses: each sees the other (noticed at once) or not; then the inputs of the last frame"""
        for _ in range(frames):
            env.known[:] = env.state[opp, :3] if on else env.known
            env.acquired[:] = on
            env.visible[:] = on
            env.seen_t[:] = 0.0 if on else env.seen_t + E.DT
            o_ = env.observe()
        return o_
    o = see(True, 12)
    k = E.OBS_DIM - E.N_RAIM - E.N_PREF
    ra = o[0, k:k + E.N_RAIM]
    s = env.state
    print("A {} B {} dist {:.0f}".format(np.round(s[0, :3]), np.round(s[1, :3]), float(np.linalg.norm(s[1, :3] - s[0, :3]))))
    print("rocket aim:", np.round(ra, 3))
    # by hand: a level view at the enemy standing still on the same floor. The floor point lies straight ahead (yaw 0), below the
    # horizon by atan((eye height above the origin + 24 - 2) / distance); the flight is the line's length / 1000; the backstop is
    # a trace of the map (he does not stop it): beyond him; the splash on him 0 unless the wall behind him is within 120 units
    d_ = float(np.hypot(*(s[1, :2] - s[0, :2])))
    dz_ = E.VIEW_H + 24.0 - 2.0 + (s[0, 2] - s[1, 2])
    exp_pitch = np.degrees(np.arctan2(dz_, d_))
    fr_ = env.w.rays_each(env._eye(s)[:1], np.array([[[np.cos(np.radians(yaw)), np.sin(np.radians(yaw)), 0.0]]], np.float32), 4096.0, mask=env.sight)[0, 0] * 4096.0
    checks = [("backstop on", ra[0] == 1.0),
              ("backstop distance = a trace by hand ({:.1f} vs {:.1f})".format(ra[1] * 2000.0, fr_), abs(min(ra[1] * 2000.0, 4000.0) - min(fr_, 4000.0)) < 1.0),
              ("backstop level (height {:.1f})".format(ra[2] * 300.0), abs(ra[2] * 300.0) < 1.0),
              ("backstop beyond the enemy", ra[3] > 0),
              ("splash = by hand", abs(ra[4] - max(0.0, 1.0 - (fr_ - (d_)) / 120.0)) < 0.05),
              ("floor point on", ra[5] == 1.0),
              ("floor yaw ~0 ({:.3f} deg)".format(ra[6] * 30.0), abs(ra[6] * 30.0) < 0.5),
              ("floor pitch = by hand ({:.2f} vs {:.2f} deg)".format(ra[8] * 15.0, exp_pitch), abs(ra[8] * 15.0 - exp_pitch) < 0.3),
              ("floor pitch fine = coarse x 7.5 (clipped)", abs(ra[9] - np.clip(ra[8] * 7.5, -1, 1)) < 1e-4),
              ("floor found", ra[10] == 1.0), ("his feet on it", ra[11] < 0.02),
              ("flight time = the line / 1000 ({:.3f} s)".format(ra[12] * 1.5), abs(ra[12] * 1.5 - np.hypot(d_, dz_) / 1000.0) < 0.01),
              ("floor clear", ra[13] == 1.0)]
    # by hand: the nearest wall by him, 8 level traces from his middle (24 above the floor)
    mid = np.array([s[1, 0], s[1, 1], s[1, 2] - 24.0 + 24.0], np.float32)
    an = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    fw = env.w.rays_each(mid[None], np.stack([np.cos(an), np.sin(an), np.zeros(8)], 1)[None].astype(np.float32), 192.0, mask=env.sight)[0]
    j_ = int(fw.argmin())
    if fw[j_] < 1.0:
        rel = an[j_] - np.radians(yaw)
        checks += [("wall found", ra[14] == 1.0), ("wall distance = by hand ({:.1f} vs {:.1f})".format(ra[17] * 192.0, fw[j_] * 192.0), abs(ra[17] - fw[j_]) < 0.02),
                   ("wall direction = by hand", abs(ra[15] - np.sin(rel)) < 0.02 and abs(ra[16] - np.cos(rel)) < 0.02)]
    else:
        checks += [("no wall within 192: found 0, distance 1", ra[14] == 0.0 and ra[17] == 1.0)]
    # the enemy moving sideways at 320 u/s: the floor point leads him by about 320 x the flight time
    env.w.reset(1, tuple(s[1, :3]), (-320.0 * np.sin(np.radians(yaw)), 320.0 * np.cos(np.radians(yaw)), 0.0), yaw + 180.0)
    env.state = env.w.state()
    env.opp_hist.clear()
    o6 = see(True, 12)
    ra6 = o6[0, k:k + E.N_RAIM]
    lead_deg = np.degrees(np.arctan2(320.0 * ra6[12] * 1.5, d_))
    checks.append(("floor point leads a strafing enemy ({:.2f} vs {:.2f} deg)".format(ra6[6] * 30.0, lead_deg), abs(ra6[6] * 30.0 - lead_deg) < 1.0))
    env.w.reset(1, tuple(s[1, :3]), (0.0, 0.0, 0.0), yaw + 180.0)
    env.state = env.w.state()
    # the rocket pointed at the floor 60 degrees down: the backstop is near and below (eye above the floor = VIEW_H + 24)
    env.pitch[0] = 60.0
    o2 = env.observe()
    ra2 = o2[0, k:k + E.N_RAIM]
    exp_d = (E.VIEW_H + 24.0) / np.sin(np.radians(60.0))
    checks.append(("backstop at the floor 60 deg down: {:.1f} vs {:.1f} units".format(ra2[1] * 2000.0, exp_d), abs(ra2[1] * 2000.0 - exp_d) < 4.0))
    checks.append(("backstop height {:.1f} vs {:.1f}".format(ra2[2] * 300.0, -(E.VIEW_H + 24.0)), abs(ra2[2] * 300.0 + E.VIEW_H + 24.0) < 3.0))
    env.pitch[0] = 0.0
    env.weapon[0] = E.LG
    o3 = env.observe()
    checks.append(("no rocket launcher in hand: zeros", not o3[0, k:k + E.N_RAIM].any()))
    env.weapon[0] = E.RL
    checks.append(("pre-fire off while the enemy is in view", not o[0, k + E.N_RAIM:].any()))
    # pre-fire: the enemy seen, then not (the belief of the last sighting); the list by the weapon, the ranking by hand
    import json as json_
    lists = {}
    for w_, k_ in zip((E.RL, E.GL, E.PG), E.PF_KINDS):
        f_ = os.path.join(SIM, "pro_places", "bloodrun_{}.json".format(k_))
        pl_ = json_.load(open(f_, encoding="utf-8"))["places"]
        lists[w_] = (np.array([q_["pos"] for q_ in pl_], np.float32), np.array([min(1.0, q_["share"] / 15.0) for q_ in pl_], np.float32))
    R, W = env.route, env.v02_ways
    see(False, 20)

    def case(name, hand, haves, want):
        """his weapon in hand, the weapons he has (with ammunition) -> the list expected (None: zeros), checked slot by slot"""
        for w_ in (E.RL, E.GL, E.PG, E.LG):
            env.has[0, w_], env.ammo[0, w_] = w_ in haves, 10 if w_ in haves else 0
        env.weapon[0] = hand
        o_ = see(False, 1)
        pf = o_[0, k + E.N_RAIM:].reshape(E.PF_SLOTS, E.PF_F)
        if want is None:
            checks.append(("pre-fire, {}: zeros".format(name), not pf.any()))
            return
        pp, sh = lists[want]
        me, bel = env.state[0, :3], env.v02_bel[0]
        na, nb = int(R.locate(me[None])[0]), int(R.locate(bel[None])[0])
        best = []
        for q in range(len(pp)):
            pn = int(R.locate(pp[q:q + 1])[0])
            wb, wm, wbm = int(W[pn, nb]), int(W[na, pn]), int(W[na, nb])
            if wb == 255 or wm == 255 or np.linalg.norm(pp[q] - me) < E.PF_SELF:
                continue
            det = max((wb + wm - (wbm if wbm < 255 else 0)), 0) / 16.0
            best.append((det + 0.01 * wb / 16.0, q, det, wb / 16.0))
        best.sort()
        eye0 = env._eye(env.state)[0]
        bt = float(env.v02_bt_now[0])
        good, slots = bool(env.v02_bel_ok[0]) and len(best) > 0, []
        for j, (_, q, det, wbs) in enumerate(best[:E.PF_SLOTS]):
            p_ = pp[q] + np.array([0, 0, E.PF_LIFT], np.float32)
            ey, ep = env._aim_at(eye0, p_, np.radians(env.yaw[0]), np.radians(env.pitch[0]))
            dd = float(np.linalg.norm(p_ - eye0))
            gp, fl = 0.0, dd / {E.RL: 1000.0, E.PG: 2000.0}.get(want, 1.0)
            if want == E.GL:                                 # the low arc by hand: tan(th) = (v^2 - sqrt(v^4 - g (g D^2 + 2 dz v^2))) / (g D)
                D, dz, v, g = float(np.hypot(*(p_[:2] - eye0[:2]))), float(p_[2] - eye0[2]), 700.0, 800.0
                disc = v ** 4 - g * (g * D * D + 2 * dz * v * v)
                if disc >= 0:
                    th = np.arctan2(v * v - np.sqrt(disc), g * D)
                    gp, fl = np.degrees(-(th - 0.2 * np.cos(th)) - np.radians(env.pitch[0])) / 15.0, D / (v * np.cos(th))
                else:
                    fl = 0.0
            exp = [np.clip(ey / 30, -1, 1), np.clip(ep / 15, -1, 1), min(dd / 2000, 1.5), np.clip((wbs - (bt - min(bt, 1))) / 5, -1, 1),
                   np.clip(fl / 1.5, 0, 2), None, min(det / 5, 1), sh[q], np.clip(gp, -1, 1), 1.0] + [float(w_ == want) for w_ in (E.RL, E.GL, E.PG)]
            good &= all(e_ is None or abs(float(pf[j, c_]) - float(e_)) < 1e-3 for c_, e_ in enumerate(exp))
            slots.append(q)
        good &= len(best) >= E.PF_SLOTS or not pf[len(best):].any()
        checks.append(("pre-fire, {}: the {} list, slots = by hand (places {})".format(name, E.PF_KINDS[(E.RL, E.GL, E.PG).index(want)], slots), good))
    case("rockets in hand", E.RL, (E.RL,), E.RL)
    case("grenades in hand (rockets too)", E.GL, (E.RL, E.GL), E.GL)
    case("plasma in hand", E.PG, (E.PG,), E.PG)
    case("lightning in hand, all three", E.LG, (E.RL, E.GL, E.PG, E.LG), E.RL)
    case("lightning in hand, grenades and plasma", E.LG, (E.GL, E.PG, E.LG), E.GL)
    case("lightning in hand, plasma only", E.LG, (E.PG, E.LG), E.PG)
    case("lightning only", E.LG, (E.LG,), None)
    env.has[0, E.RL], env.ammo[0, E.RL], env.weapon[0] = True, 10, E.RL
    checks.append(("pre-fire off while the enemy is in view", not see(True, 3)[0, k + E.N_RAIM:].any()))
    bad = [n_ for n_, ok_ in checks if not ok_]
    for n_, ok_ in checks:
        print("  {:<70s} {}".format(n_, "ok" if ok_ else "FAIL"))
    print("HAND", "PASS" if not bad else "FAIL: " + "; ".join(bad))


def ffa():
    tmp = os.path.join(CACHE, "out")
    os.makedirs(tmp, exist_ok=True)
    e = dict(os.environ, RL_AIM="1", PREFIRE="1", CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    outs = []
    for mod in ("duel_env", "duel_env_ffa"):
        outs.append(os.path.join(tmp, "ffa_" + mod + ".npz"))
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ffa_check.py"), mod, "2", "300", outs[-1], "testlab", "2", "sets"], check=True, env=e)
    a, b = np.load(outs[0]), np.load(outs[1])
    same = all(np.array_equal(a[k], b[k]) for k in ("obs", "rew", "don"))
    print("TWO PLAYERS, RL_AIM and PREFIRE on: {} over 300 frames; the rocket aim inputs nonzero in {:.0%} of player-frames".format(
        "identical to duel_env" if same else "DIFFERENT", float((a["obs"][:, :, -(N_NEW):-(N_NEW - 20)] != 0).any(2).mean())))


def torch_check(path):
    import torch
    sys.path.insert(0, SIM)
    import attn as A
    torch.set_num_threads(1)
    ck = torch.load(path, weights_only=False, map_location="cpu")
    lay, sd = ck["attn"], ck["model"]
    m = A.make_module(lay, sd["gru.weight_ih"].shape[1])
    missing, extra = m.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("attn.")}, strict=False)
    x = np.random.default_rng(0).standard_normal((256, lay["obs_dim"])).astype(np.float32)
    with torch.no_grad():
        yt = m(torch.from_numpy(x)).numpy()
    yn = A.forward_np(lay, A.params_np(sd), x)
    x2 = x.copy()
    x2[:, -N_NEW:] = np.random.default_rng(1).standard_normal((256, N_NEW)) * 5
    with torch.no_grad():
        yt2 = m(torch.from_numpy(x2)).numpy()
    print("torch attention part: missing {} unexpected {}; torch against numpy {:.2e}; the {} new columns changed: the output moved {:.2e}".format(
        missing, extra, float(np.abs(yt - yn).max()), N_NEW, float(np.abs(yt2 - yt).max())))


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "ident":
        ident()
    elif sys.argv[1] == "hand":
        hand()
    elif sys.argv[1] == "ffa":
        ffa()
    elif sys.argv[1] == "torch":
        torch_check(sys.argv[2])

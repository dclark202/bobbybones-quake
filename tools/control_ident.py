"""CONTROL_TRUTH is labels only: a fixed-seed replay of the run's simulator with it off and on must be the same to the bit
(inputs, pay, round ends, r_long, events, the counters, every info["aux"] column of the run), and with it on the label
must be what a hindsight count over the replay's own frames gives (tools/control_probe.offline_labels).

    python tools/control_ident.py --run-cmd <run .cmd> --run-dir <run folder> [--map bloodrun,aerowalk] [--frames 3000]
        [--horizon 20]   (CONTROL_H for the check: a short one, so that labels come inside the replay)
    (Anaconda Python; each side in a process of its own, as the switches are read at import)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def side(mp, frames, out, envv):
    os.environ.update(envv)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import importlib
    E = importlib.import_module("duel_env_ffa")
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 0.75, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    H = []
    AX, DN = [], []
    for t in range(frames):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        H.append((obs.astype(np.float32), rew.astype(np.float32), done.copy(), np.asarray(info["r_long"], np.float32),
                  [(e["victim"], e["killer"]) for e in info["events"]]))
        AX.append(np.asarray(info["aux"], np.float32))
        DN.append(np.asarray(done, bool).copy())
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=np.stack([x[0] for x in H]), rew=np.stack([x[1] for x in H]), done=np.stack([x[2] for x in H]),
             rl=np.stack([x[3] for x in H]), ev=np.array(json.dumps([x[4] for x in H], default=int)), aux=np.stack(AX),
             cols=np.array(E.AUX_COLS), D=E.CONTROL_D, **stv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=3000)
    ap.add_argument("--horizon", type=float, default=20.0)
    ap.add_argument("--side", nargs=3, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(a.run_cmd, a.run_dir)
    envv.update(STAGGER_START="1", CONTROL_H=str(a.horizon))
    if a.side:
        envv.update(CONTROL_TRUTH=a.side[2])
        side(a.side[0], a.frames, a.side[1], envv)
        return
    import control_probe as CP
    ok = True
    tmp = tempfile.mkdtemp(prefix="control_ident_")
    for mp in a.map.split(","):
        outs = []
        for on_ in ("0", "1"):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, on_))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--run-cmd", a.run_cmd, "--run-dir", a.run_dir,
                                   "--frames", str(a.frames), "--horizon", str(a.horizon), "--side", mp, o_, on_])
            outs.append(np.load(o_))
        A, B = outs
        same = {k: bool(np.array_equal(A[k], B[k])) for k in ("obs", "rew", "done", "rl")}
        same["events"] = str(A["ev"]) == str(B["ev"])
        ka = [k for k in A.files if k.startswith("st_")]
        same["counters"] = all(k in B.files and np.array_equal(A[k], B[k]) for k in ka) and \
            sorted(k for k in B.files if k.startswith("st_")) == sorted(ka)
        ca, cb = list(A["cols"]), list(B["cols"])
        same["aux columns"] = cb[:len(ca)] == ca and cb[len(ca):] == ["ctl_lab", "ctl_one", "ctl_age", "ctl_ok", "ctl_mh", "ctl_ra"] and \
            np.array_equal(A["aux"], B["aux"][..., :len(ca)])
        D = int(B["D"])
        offs = CP.offline_labels(B["aux"], cb, B["done"], D)
        envs = [B["aux"][D:, :, cb.index(c_)] for c_ in ("ctl_lab", "ctl_one", "ctl_mh", "ctl_ra")]   # the row of f + D: frame f's label
        env_two, env_one = envs[0], envs[1]
        off_two, off_one = offs[0], offs[1]
        T_ = env_two.shape[0]
        same_ = [bool(np.array_equal(e_, o_[:T_])) for e_, o_ in zip(envs, offs)]
        lab_ok = all(same_)
        print("    labels two, one, mega, red as hindsight gives them: {}; defined {}".format(
            same_, [round(float((e_ >= 0).mean()), 3) for e_ in envs]))
        nd_ = int((env_two >= 0).sum())
        print("{}: {} frames, 24 players | identical off/on: {} | labels as hindsight gives them: {} ({} labelled frames of {}, "
              "values {})".format(mp, a.frames, same, lab_ok, nd_, env_two.size,
                                  {float(v): int(c) for v, c in zip(*np.unique(env_two[env_two >= 0], return_counts=True))}))
        if not lab_ok:
            bad = np.argwhere((env_two != off_two[:T_]) | (env_one != off_one[:T_]))
            print("    first differences (frame, seat, env two, hindsight two, env one, hindsight one):",
                  [(int(f), int(i), float(env_two[f, i]), float(off_two[f, i]), float(env_one[f, i]), float(off_one[f, i]))
                   for f, i in bad[:8]])
        ok &= all(same.values()) and lab_ok
    print("IDENTICAL with CONTROL_TRUTH off and on; the labels are the hindsight count" if ok else "DIFFERENT: see above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

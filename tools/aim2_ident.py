"""AIM2's identity proof: a fixed-seed replay of the run's simulator (its .cmd's settings and live.json) with random actions
for every output, in two code trees and/or two settings, compared to the bit (inputs, pay, round ends, kills, the counters).

    python tools/aim2_ident.py --run-cmd <run .cmd> --live <live.json> --code-a <tree> --code-b <tree>
           [--set-b NAME=VALUE ...] [--module duel_env_ffa|duel_env] [--map bloodrun,aerowalk] [--frames 1500]

Each side runs in a process of its own (the switches are read at import). Used for: (1) the branch aim2 with every AIM2
switch off against the running run's code (v051); (2) aim2 with the switches on at their "old" settings (AIM2_W=0,
AIM2_SPLIT_W=0, AIM2_FOCUS_GAIN=2, AIM2_FOCUS_SIG=1, AIM2_SMOOTH_K=1) against off: the blend's start is the old simulator.
Anaconda or system Python with numpy; no torch.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cmd_env(path):
    """the `set NAME=VALUE` lines of a run's .cmd (not the `if ... set` ones)"""
    env = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s.lower().startswith("set ") and "=" in s:
            k, v = s[4:].split("=", 1)
            env[k.strip()] = v.strip()
    return env


def side(code, module, mp, frames, out, envv):
    os.environ.update(envv)
    sys.path.insert(0, os.path.join(code, "sim"))
    import importlib
    E = importlib.import_module(module)
    data = os.path.join(ROOT, "data", "maps")
    nav_ = os.path.join(data, "nav_{}_sim.json".format(mp))
    kw = dict(group=2) if module.endswith("ffa") else {}
    env = E.DuelEnv(os.path.join(data, mp + ".bsp"), n_matches=12, seed=7, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, **kw)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.react_frames, env.acquire_frames = 4, 8                # the run's --react-ms 100 --acquire-ms 200
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    O, R, D, EV = [], [], [], []
    acq, dmg, zoomed = 0, 0.0, 0
    for t in range(frames):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        O.append(obs.astype(np.float32))
        R.append(np.asarray(rew, np.float32))
        D.append(np.asarray(done).copy())
        EV.append([(e.get("victim"), e.get("killer")) for e in info.get("events", [])])
        acq += int(np.asarray(env.acquired).sum())
        zoomed += int(np.asarray(env.zoom).sum())
        dmg = float(np.asarray(env.dmg_life).sum()) if t == 0 else dmg + float(np.maximum(0, np.asarray(env.dmg_life)).sum()) * 0
    stv = {}
    for k, v_ in env.stats.items():
        try:
            stv["st_" + k] = np.asarray(v_, np.float64)
        except (TypeError, ValueError):
            pass
    np.savez(out, obs=np.stack(O), rew=np.stack(R), done=np.stack(D), ev=np.array(json.dumps(EV, default=int)),
             view=np.stack([env.yaw, env.pitch]), acq=acq, zoomed=zoomed, hp=np.asarray(env.hp), percept=np.asarray(env.percept),
             **stv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--live", default="")
    ap.add_argument("--code-a", required=True)
    ap.add_argument("--code-b", required=True)
    ap.add_argument("--set-a", nargs="*", default=[])
    ap.add_argument("--set-b", nargs="*", default=[])
    ap.add_argument("--module", default="duel_env_ffa")
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=1500)
    ap.add_argument("--side", nargs=6, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.side:
        code, module, mp, frames, out, envj = a.side
        side(code, module, mp, int(frames), out, json.load(open(envj)))
        return
    base = cmd_env(a.run_cmd)
    if a.live:
        for k, v in json.load(open(a.live)).items():
            base[k] = str(v)
    base.update(OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    tmp = tempfile.mkdtemp(prefix="aim2id_")
    ok_all = True
    for mp in a.map.split(","):
        outs = []
        for tag, code, sets in (("a", a.code_a, a.set_a), ("b", a.code_b, a.set_b)):
            e = dict(base)
            e.update(dict(s.split("=", 1) for s in sets))
            ej = os.path.join(tmp, "{}_{}.json".format(mp, tag))
            json.dump(e, open(ej, "w"))
            out = os.path.join(tmp, "{}_{}.npz".format(mp, tag))
            env_ = dict(os.environ)
            env_.update(e)
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--run-cmd", a.run_cmd, "--code-a", code,
                                "--code-b", code, "--side", code, a.module, mp, str(a.frames), out, ej],
                               env=env_, cwd=code, capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stdout[-2000:], r.stderr[-4000:])
                raise SystemExit("side {} failed on {}".format(tag, mp))
            outs.append(np.load(out))
        A, B = outs
        bad = []
        for k in A.files:
            if k not in B.files:
                bad.append(k + " (missing in b)")
                continue
            x, y = A[k], B[k]
            if x.shape != y.shape or not (np.array_equal(x, y) if x.dtype.kind in "SUOb" else
                                          np.array_equal(np.nan_to_num(x), np.nan_to_num(y))):
                if x.shape == y.shape and x.dtype.kind == "f":
                    d = np.abs(x.astype(np.float64) - y.astype(np.float64))
                    bad.append("{}: max diff {:.3g} at {}".format(k, d.max(), np.unravel_index(d.argmax(), d.shape)))
                else:
                    bad.append(k)
        n_frames, n_pl = A["obs"].shape[0], A["obs"].shape[1]
        kills = len([e for f in json.loads(str(A["ev"])) for e in f])
        print("{} {}: {} frames x {} players x {} inputs, {} deaths, {} player-frames with the enemy acquired, {} zoomed, damage {:.0f}: {}".format(
            a.module, mp, n_frames, n_pl, A["obs"].shape[2], kills, int(A["acq"]), int(A["zoomed"]),
            float(A["st_dmg"].sum()) if "st_dmg" in A.files else -1, "IDENTICAL" if not bad else "DIFFER: " + "; ".join(bad[:8])))
        ok_all &= not bad
    print("ALL IDENTICAL" if ok_all else "NOT IDENTICAL")


if __name__ == "__main__":
    main()

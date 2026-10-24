"""PAY_SPLIT and WIN_SHADOW are record only: a fixed-seed replay of the run's simulator with them off and on must be the
same to the bit (inputs, pay, round ends, r_long, the counters the simulator had before them).

    python tools/winpay_ident.py --run-cmd <run .cmd> --run-dir <run folder> [--map bloodrun,aerowalk] [--frames 3000]
    (Anaconda Python; each side in a process of its own, as the switches are read at import)

The run's settings as tools/winpay_games.py reads them (its .cmd, live_settings.env, live_applied.json), its own shares
(whole games, pro starts, jump runs), staggered first games so that games end inside the replay; random actions from a
fixed stream for every output. Also checked with the switches on: the split sums to the frame's pay.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def side(args):
    mp, frames, out, envv = args
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
    terms_err, shadow = 0.0, []
    for t in range(frames):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        obs, rew, done, info = env.step(a)
        H.append((obs.astype(np.float32), rew.astype(np.float32), done.copy(), np.asarray(info["r_long"], np.float32),
                  [(e["victim"], e["killer"]) for e in info["events"]]))
        if "pay_terms" in info:
            terms_err = max(terms_err, float(np.abs(info["pay_terms"].sum(1) - rew).max()))
            shadow.append(np.asarray(info["win_shadow"], np.float64))
    obs = np.stack([x[0] for x in H])
    rew = np.stack([x[1] for x in H])
    done = np.stack([x[2] for x in H])
    rl = np.stack([x[3] for x in H])
    ev = json.dumps([x[4] for x in H], default=int)
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=obs, rew=rew, done=done, rl=rl, ev=np.array(ev), **stv,
             terms_err=terms_err, shadow=np.stack(shadow) if shadow else np.zeros(0),
             ws=np.asarray(env.stats.get("win_shadow", np.zeros(1)), np.float64),
             games=np.asarray(env.stats.get("games", np.zeros(2)), np.float64))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=3000)
    ap.add_argument("--side", nargs=3, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(a.run_cmd, a.run_dir)
    envv.update(STAGGER_START="1")
    if a.side:
        on_ = a.side[2] == "1"
        envv.update(PAY_SPLIT="1" if on_ else "0", WIN_SHADOW="1" if on_ else "0")
        side((a.side[0], a.frames, a.side[1], envv))
        return
    ok = True
    tmp = tempfile.mkdtemp(prefix="winpay_ident_")
    for mp in a.map.split(","):
        outs = []
        for on_ in ("0", "1"):
            o_ = os.path.join(tmp, "{}_{}.npz".format(mp, on_))
            subprocess.check_call([sys.executable, os.path.abspath(__file__), "--run-cmd", a.run_cmd, "--run-dir", a.run_dir,
                                   "--frames", str(a.frames), "--side", mp, o_, on_])
            outs.append(np.load(o_))
        A, B = outs
        same = {k: bool(np.array_equal(A[k], B[k])) for k in ("obs", "rew", "done", "rl")}
        same["events"] = str(A["ev"]) == str(B["ev"])
        ka = [k for k in A.files if k.startswith("st_")]
        same["counters"] = all(k in B.files and np.array_equal(A[k], B[k]) for k in ka)
        same["new counters only"] = sorted(k[3:] for k in B.files if k.startswith("st_") and k not in ka) == ["pay_terms", "win_shadow"]
        print("{}: {} frames, 24 players | identical: {} | the split sums to the pay within {:.2e} | games ended {}".format(
            mp, a.frames, same, float(B["terms_err"]), int(B["games"][0] + B["games"][1]) if len(B["games"]) > 1 else 0))
        print("    shadow counters (WS_COLS): {}".format([round(float(x), 3) for x in B["ws"]]))
        ok &= all(same.values()) and float(B["terms_err"]) < 1e-4
    print("IDENTICAL with PAY_SPLIT and WIN_SHADOW off and on" if ok else "DIFFERENT: see above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

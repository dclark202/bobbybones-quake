"""2.2a: DESC_OX off and on, the simulator to the bit (a fixed-seed replay). Each arm is a process of its own (the switch is read at import): the
2.1d command's simulator settings (its `set` lines), duel_env_ffa on a map with 8 matches, random actions from a fixed stream for FRAMES frames;
the ON arm also calls order_feat() and desc22.env_ox() on every eighth frame, as the trainer's simulators do after a tick's frame. The inputs,
pay, round ends and the simulator's aux truth of every frame are hashed and compared.
    QLBOT_ROOT=<the checkout with data> python docs/runs/2.2/2.2a/desc_ox_ident.py [--map bloodrun] [--frames 2000]"""
import argparse
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def arm(mp, frames, on):
    import numpy as np
    sys.path.insert(0, os.path.join(CODE, "tools", "run"))
    import keep21_simtest as ks_
    root = os.environ.get("QLBOT_ROOT") or CODE
    ev = ks_.cmd_env(os.path.join(CODE, "docs", "runs", "2.1", "2.1d", "train.cmd"), root)
    ev.update(FIGHT_TRUTH="1")
    if on:
        ev["DESC_OX"] = "1"
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(CODE, "sim"))
    import duel_env_ffa as E
    import desc22 as D
    assert bool(getattr(E, "DESC_OX", False)) == on
    data = os.path.join(root, "data", "maps")
    nav_ = os.path.join(data, "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(data, mp + ".bsp"), n_matches=8, seed=5, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    rng = np.random.default_rng(11)
    h = hashlib.sha256()
    nox = 0
    for t in range(frames):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        obs, rew, done, info = env.step(a)
        for x_ in (obs, rew, done, info.get("aux")):
            if x_ is not None:
                h.update(np.ascontiguousarray(np.asarray(x_)).tobytes())
        if on and t % 8 == 7:
            ox_ = D.env_ox(env)
            nox += int(np.asarray(ox_[0])[..., 0:9].astype(np.float32).sum() > 0)
    print("HASH {} {}".format(h.hexdigest(), nox), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=2000)
    ap.add_argument("--arm", default="")
    a = ap.parse_args()
    if a.arm:
        arm(a.map, a.frames, a.arm == "on")
        return 0
    out = {}
    for nm_ in ("off", "on"):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--arm", nm_, "--map", a.map, "--frames", str(a.frames)], capture_output=True,
                           text=True, creationflags=NOWIN, env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1"))
        ln_ = [x for x in r.stdout.splitlines() if x.startswith("HASH ")]
        out[nm_] = ln_[0].split()[1:] if ln_ else None
        if not ln_:
            print(r.stderr[-2000:])
    ok = out["off"] is not None and out["on"] is not None and out["off"][0] == out["on"][0] and int(out["on"][1]) > 0
    print("DESC_OX off and on, {} frames x 16 seats on {}: the inputs, pay, round ends and truth {} (sha256 {} / {}); the description read on {} "
          "ticks with numbers in it: {}".format(a.frames, a.map, "the same to the bit" if ok else "DIFFER", (out["off"] or ["-"])[0][:16],
                                               (out["on"] or ["-"])[0][:16], (out["on"] or ["", "0"])[1], "PASS" if ok else "FAIL"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""2.2e: the simulator's new switch (RDRILL, the rail drill) off = the tree before it, to the bit; and RDRILL=1 with its share RDRILL_P 0 = the
tree before it too (not one draw more). Fixed-seed replays (2.2c's ident_sim.py's play and cmp, with 2.2d's command's settings and the trainer's
first frame: every round ends at the first step, as the trainer's workers start them, so the round draw runs on every match): every input by
name, pay, round ends, targets, stacks, places equal to the bit. Each replay in its own process (hidden).
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2e/ident_22e.py <old tree> <out folder>
<old tree>: the tree before the build (git archive of the commit before, with sim/qsim.dll copied in).
    ... ident_22e.py play <tree> <out.npz> --map M --seed S --frames F [--set NAME=value ...]     (one replay)"""
import argparse
import csv
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
CMD = os.path.join(ROOT, "docs", "runs", "2.2", "2.2d", "train.cmd")          # (2.2d's command: the run before)
IS = os.path.join(ROOT, "docs", "runs", "2.2", "2.2c", "ident_sim.py")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AIM4 = ["PERCEPT_SIGMA=0.64", "AIM2_C_SLIP=0.007", "AIM2_CAP_SLIP=1.1", "AIM2_C_ECC=0.01", "AIM2_FOCUS_SIG=0.7", "FLINCH_PER_DMG=0", "FLINCH_MAX=0",
        "MOTOR_NOISE=0.080", "MOTOR_BASE=0.038", "VEL_DELAY_MS=175", "VEL_WEBER=0.15", "RANGE_WEBER=0.17", "AIM3_PURSUIT_TAU=0.10", "AIM3_SIZE_A=0",
        "AIM3_SIZE_B=0.49"]
P22E = ["RAIL_PICK_PAY=0", "RAIL_FAR_PAY=0.2"]
CASES = (("off: RDRILL unset, 2.2d's settings", "bloodrun", 800, [], []),
         ("off: RDRILL unset, 2.2d's settings", "campgrounds", 1200, [], []),
         ("on, share 0: RDRILL=1 RDRILL_P=0 in the new tree, 2.2d's settings", "campgrounds", 1200, [], ["RDRILL=1", "RDRILL_P=0"]),
         ("on, share 0: RDRILL=1 RDRILL_P=0 in the new tree, 2.2e's aim4 and pays (both trees)", "hektik", 1200, AIM4 + P22E,
          AIM4 + P22E + ["RDRILL=1", "RDRILL_P=0"]))


def cmd_env(path, root):
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln.rstrip("\r\n"), re.I)
        if m and m.group(1) not in ("ROOT", "GPU_MEM_FRACTION", "TRAINER_MASK", "LEARN"):
            out[m.group(1)] = m.group(2).replace("%ROOT%", root).replace("%~dp0..\\..\\..\\..", root)
    return out


def play(a):
    ev = cmd_env(CMD, os.environ.get("QLBOT_ROOT") or ROOT)
    ev.update(cmd_env(os.path.join(os.path.dirname(CMD), "aim2_env.cmd"), os.environ.get("QLBOT_ROOT") or ROOT))
    for kv in a.set or ():
        k, v = kv.split("=", 1)
        ev[k] = v
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(a.tree, "sim"))
    import importlib
    E = importlib.import_module("duel_env_ffa")
    names = [(r["group"], r["input"]) for r in csv.DictReader(open(os.path.join(a.tree, "docs", "INPUTS.csv"), encoding="utf-8"))]
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(DATA, "maps", a.map + ".bsp"), n_matches=8, seed=a.seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.round_t[:] = 1e9                                     # (as the trainer's workers: every round starts anew at the first step)
    rng = np.random.default_rng(a.seed + 1)
    o = env.observe()
    assert o.shape[1] == len(names), (o.shape, len(names))
    rec = {k: [] for k in ("obs", "rew", "don", "intent", "hp", "armor", "pos", "frags")}
    for t in range(a.frames):
        act = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        act[:, 5] = rng.random(env.n) < 0.5
        col = 3 + 4 * int(t % 8 == 0) + np.zeros(env.n, np.int64)
        act = np.concatenate([act, col[:, None]], 1)
        o, r, d, info = env.step(act)
        rec["obs"].append(np.asarray(o, np.float32).copy())
        rec["rew"].append(np.asarray(r, np.float32).copy())
        rec["don"].append(np.asarray(d, bool).copy())
        rec["intent"].append(np.asarray(env.intent[:env.n]).copy())
        rec["hp"].append(np.asarray(env.hp[:env.n], np.float32).copy())
        rec["armor"].append(np.asarray(env.armor[:env.n], np.float32).copy())
        rec["pos"].append(np.asarray(env.state[:env.n, :3], np.float32).copy())
        rec["frags"].append(np.asarray(env.frags_r[:env.n], np.float32).copy())
    np.savez_compressed(a.out, names=np.array(["{}|{}".format(g, n) for g, n in names]), **{k: np.stack(v) for k, v in rec.items()})
    print("wrote {}: {} frames, {} seats, {} inputs; round ends {}".format(a.out, a.frames, env.n, len(names), int(np.stack(rec["don"]).sum())))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "play":
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd")
        ap.add_argument("tree")
        ap.add_argument("out")
        ap.add_argument("--map", default="bloodrun")
        ap.add_argument("--seed", type=int, default=11)
        ap.add_argument("--frames", type=int, default=800)
        ap.add_argument("--set", action="append")
        play(ap.parse_args())
        return
    old, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    bad = 0
    for k_, (nm_, mp_, fr_, so_, sn_) in enumerate(CASES):
        files = []
        for tr_, set_ in ((old, so_), (ROOT, sn_)):
            f_ = os.path.join(out, "case{}_{}.npz".format(k_, "old" if tr_ == old else "new"))
            r_ = subprocess.run([sys.executable, os.path.abspath(__file__), "play", tr_, f_, "--map", mp_, "--frames", str(fr_), "--seed", str(31 + k_)]
                                + [x_ for s_ in set_ for x_ in ("--set", s_)], capture_output=True, text=True, creationflags=NOWIN)
            if r_.returncode != 0:
                print("play FAILED ({}): {}".format(tr_, (r_.stdout + r_.stderr)[-1500:]))
                bad += 1
            else:
                print("   " + r_.stdout.strip().splitlines()[-1])
            files.append(f_)
        r_ = subprocess.run([sys.executable, IS, "cmp"] + files, capture_output=True, text=True, creationflags=NOWIN)
        print("case {}: {} | {} {} frames x 16 seats".format(k_, nm_, mp_, fr_))
        print("   " + (r_.stdout + r_.stderr).strip().replace("\n", "\n   "), flush=True)
        bad += r_.returncode != 0
    print("ALL IDENTICAL" if not bad else "FAILED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

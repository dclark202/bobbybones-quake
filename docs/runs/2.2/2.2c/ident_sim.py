"""2.2c (from 2.2b's): the simulator's new switches off (CONTEST, RAIL_CHAIN, AHEAD_IN) = the simulator before them, to the bit (fixed-seed replays). One process a replay.

    play <tree> <out.npz> --map M --seed S --frames F [--set NAME=value ...]
        the group module (duel_env_ffa) of <tree>/sim with 2.2b's settings (its train.cmd's `set` lines) and the --set ones, 8 matches, random
        actions from a fixed stream with the held draw's keep column (d + 2c + 4r); every frame's inputs (by NAME, the tree's docs/INPUTS.csv),
        pay, round ends, targets, health and armor, places
    cmp <a.npz> <b.npz>
        every input both have by name, the pay, the ends, the targets, the stacks, the places: equal to the bit; the inputs only one has: listed
        with their largest |value|
    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2c/ident_sim.py ...
"""
import argparse
import csv
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
CMD22A = os.path.join(ROOT, "docs", "runs", "2.2", "2.2b", "train.cmd")      # (2.2c: the settings of 2.2b's command, the run before)


def cmd_env(path, root):
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln.rstrip("\r\n"), re.I)
        if m and m.group(1) not in ("ROOT", "GPU_MEM_FRACTION", "TRAINER_MASK", "LEARN"):
            out[m.group(1)] = m.group(2).replace("%ROOT%", root).replace("%~dp0..\\..\\..\\..", root)
    return out


def play(a):
    ev = cmd_env(CMD22A, os.environ.get("QLBOT_ROOT") or ROOT)
    a2 = os.path.join(ROOT, "docs", "runs", "2.2", "2.2b", "aim2_env.cmd")
    if os.path.exists(a2):
        ev.update(cmd_env(a2, os.environ.get("QLBOT_ROOT") or ROOT))
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
    rng = np.random.default_rng(a.seed + 1)
    nk = len(E.ACTION_DIMS)
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
    print("wrote {}: {} frames, {} seats, {} inputs".format(a.out, a.frames, env.n, len(names)))


def cmp(a):
    A, B = np.load(a.a), np.load(a.b)
    na, nb = list(A["names"]), list(B["names"])
    both = [x for x in na if x in nb]
    ia, ib = [na.index(x) for x in both], [nb.index(x) for x in both]
    bad = []
    d_obs = float(np.abs(A["obs"][..., ia] - B["obs"][..., ib]).max())
    if d_obs != 0.0 or not np.array_equal(A["obs"][..., ia], B["obs"][..., ib]):
        bad.append("inputs (largest |difference| {})".format(d_obs))
    for k in ("rew", "don", "intent", "hp", "armor", "pos", "frags"):
        if not np.array_equal(A[k], B[k]):
            bad.append("{} (largest |difference| {})".format(k, float(np.abs(A[k].astype(np.float64) - B[k].astype(np.float64)).max())))
    only = [(x, float(np.abs(B["obs"][..., nb.index(x)]).max())) for x in nb if x not in na]
    only_a = [x for x in na if x not in nb]
    print("cmp: {} frames x {} seats; {} inputs by name in both; only in b: {} (largest |value| {}); only in a: {}".format(
        A["obs"].shape[0], A["obs"].shape[1], len(both), len(only), max([v for _, v in only], default=0.0), len(only_a)))
    print("pay summed a {:.6f} b {:.6f}; round ends {} {}".format(float(A["rew"].sum()), float(B["rew"].sum()), int(A["don"].sum()), int(B["don"].sum())))
    print("IDENTICAL" if not bad else "DIFFERS: " + "; ".join(bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("play")
    p.add_argument("tree")
    p.add_argument("out")
    p.add_argument("--map", default="bloodrun")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--frames", type=int, default=800)
    p.add_argument("--set", action="append")
    p = sp.add_parser("cmp")
    p.add_argument("a")
    p.add_argument("b")
    a = ap.parse_args()
    sys.exit(int({"play": play, "cmp": cmp}[a.cmd](a) or 0))


if __name__ == "__main__":
    main()

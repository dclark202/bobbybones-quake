"""2.0b, the simulator's part alone (sim/duel_env.py against sim/duel_env_20a.py, the frozen copy of 2.0a's simulator):

    python docs/runs/2.0/2.0b/tests_env.py [--map bloodrun] [--frames 2500]

  off   every switch of 2.0b off: the same seed and actions give the same inputs (the old columns; the new ones zeros), pay and
        round ends as 2.0a's simulator, frame by frame
  on    SPACE_TRUTH, SPACE_IN, EDGE_PAY, COVER_PAY, PAY_SPLIT on: the play (round ends, the old inputs) still the same; the truth
        columns in range; the new inputs live and in range; the edge and the cover zero-sum between a match's two seats, every
        frame; the ledger's terms sum to the pay; the pay differs from `off` by exactly the two terms
One simulator a process."""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def run(module, mp, frames, out):
    import importlib
    E = importlib.import_module(module)
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=12, seed=5)
    env.react_frames, env.acquire_frames = 3, 8
    env.dmg_reward, env.dmg_taken_w = 0.001, 1.0
    rng = np.random.default_rng(11)
    obs, rew, don, aux, pt = [], [], [], [], []
    env.observe()
    for t in range(frames):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.8
        foe = np.arange(env.n) ^ 1
        s = env.state
        to = s[foe, :3] - s[:, :3]
        ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw + 180.0) % 360.0 - 180.0
        aim = rng.random(env.n) < 0.7
        a[:, 3] = np.where(aim, np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1), a[:, 3])
        o, r, d, info = env.step(a)
        obs.append(o.astype(np.float32)), rew.append(np.asarray(r, np.float64).copy()), don.append(np.asarray(d).copy())
        aux.append(info["aux"].copy())
        if "pay_terms" in info:
            pt.append(info["pay_terms"].astype(np.float64))
    np.savez(out, obs=np.array(obs), rew=np.array(rew), don=np.array(don), aux=np.array(aux), pt=np.array(pt),
             cols=np.array(E.AUX_COLS), terms=np.array(E.PAY_TERMS), n_new=getattr(E, "N_SP", 0) + getattr(E, "N_SPT", 0))
    print("{} on {}: {} inputs, {} frames, frags {}".format(module, mp, o.shape[1], frames, int(env.stats["frags"])), flush=True)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        return run(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=2500)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="t20b_")
    base = dict(os.environ, OPENBLAS_NUM_THREADS="1", PAY_SPLIT="1", GAME_P="1", ITEM_BELIEF="1")
    for k in ("SPACE_TRUTH", "SPACE_IN", "EDGE_PAY", "COVER_PAY", "SPACE_GATE"):
        base.pop(k, None)
    on = dict(base, SPACE_TRUTH="1", SPACE_IN="1", EDGE_PAY="0.0005", COVER_PAY="0.002")
    res = {}
    for nm, mod, env in (("old", "duel_env_20a", base), ("off", "duel_env", base), ("on", "duel_env", on)):
        f = os.path.join(tmp, nm + ".npz")
        subprocess.run([sys.executable, os.path.abspath(__file__), "run", mod, a.map, str(a.frames), f], check=True, env=env,
                       stdin=subprocess.DEVNULL)
        res[nm] = np.load(f)
    old, off, on_ = res["old"], res["off"], res["on"]
    bad = 0

    def check(name, cond, extra=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("{} {} {}".format("ok  " if cond else "FAIL", name, extra), flush=True)
    w = old["obs"].shape[2]
    nn = int(off["n_new"])
    check("off: the old inputs as 2.0a's simulator", np.array_equal(old["obs"], off["obs"][:, :, :w]), "({} + {} columns)".format(w, nn))
    check("off: the new inputs are zeros", off["obs"].shape[2] == w + nn and not off["obs"][:, :, w:].any())
    check("off: the pay as 2.0a's simulator", np.array_equal(old["rew"], off["rew"]))
    check("off: the round ends as 2.0a's simulator", np.array_equal(old["don"], off["don"]))
    check("off: the truth columns unchanged", np.array_equal(old["aux"], off["aux"]))
    k = len(old["terms"])
    check("off: the ledger's old terms unchanged, the new ones zero", np.array_equal(old["pt"], off["pt"][:, :, :k]) and not off["pt"][:, :, k:].any())
    check("on: the round ends the same (the switches do not touch the play)", np.array_equal(off["don"], on_["don"]))
    check("on: the old inputs the same", np.array_equal(off["obs"][:, :, :w], on_["obs"][:, :, :w]))
    C = {c: i for i, c in enumerate(on_["cols"])}
    A = on_["aux"]
    ok = A[:, :, C["sp_ok"]] > 0
    check("on: the truth is there", ok.mean() > 0.3, "(sp_ok in {:.0f}% of the frames)".format(100 * ok.mean()))
    z = A[:, :, C["sp_z0"]:C["sp_z0"] + 24]
    check("on: the truth in range and finite", np.isfinite(A).all() and (np.abs(z) <= 1.0001).all() and (np.abs(A[:, :, C["sp_agg"]]) <= 1.0001).all()
          and (A[:, :, C["sp_thr"]] >= 0).all() and (A[:, :, C["sp_thr"]] < 60).all(),
          "(threat mean {:.2f}, max {:.1f}; |agg| mean {:.3f})".format(A[:, :, C["sp_thr"]][ok].mean(), A[:, :, C["sp_thr"]].max(), np.abs(A[:, :, C["sp_agg"]][ok]).mean()))
    check("on: the edge = put - threat", np.allclose(A[:, :, C["sp_edge"]], A[:, :, C["sp_put"]] - A[:, :, C["sp_thr"]], atol=1e-4))
    e = A[:, :, C["sp_edge"]]
    check("on: the truth zero-sum between a match's seats (edge, aggregate, zones)", np.abs(e[:, 0::2] + e[:, 1::2]).max() < 1e-3
          and np.abs(A[:, 0::2, C["sp_agg"]] + A[:, 1::2, C["sp_agg"]]).max() < 1e-4 and np.abs(z[:, 0::2] + z[:, 1::2]).max() < 1e-4)
    new = on_["obs"][:, :, w:]
    live = (np.abs(new) > 0).any(0).any(0)
    check("on: the new inputs live and in range", np.isfinite(new).all() and np.abs(new).max() <= 1.5001 and live[:8].all(),
          "({} of {} columns ever non-zero; he believes a place in {:.0f}% of the frames)".format(int(live.sum()), nn, 100 * new[:, :, 0].mean()))
    T = {c: i for i, c in enumerate(on_["terms"])}
    pe, pc = on_["pt"][:, :, T["edge"]], on_["pt"][:, :, T["cover"]]
    check("on: the edge pay zero-sum, every frame", np.abs(pe[:, 0::2] + pe[:, 1::2]).max() < 1e-9 and np.abs(pe).sum() > 0,
          "(size {:.4f} a player-minute)".format(np.abs(pe).mean() * 40 * 60))
    check("on: the cover pay zero-sum, every frame", np.abs(pc[:, 0::2] + pc[:, 1::2]).max() < 1e-9 and np.abs(pc).sum() > 0,
          "(size {:.4f} a player-minute)".format(np.abs(pc).mean() * 40 * 60))
    check("on: the edge pay is the dial's arithmetic (0.0005 a damage-second, a frame 1/40 s)",
          np.allclose(pe, np.where(ok, e, 0.0) * 0.0005 / 40.0, atol=1e-7))
    check("on: the ledger sums to the pay", np.allclose(on_["pt"].sum(2), on_["rew"], atol=1e-6))
    check("on: the pay = off's pay + the two terms", np.allclose(on_["rew"], off["rew"] + pe + pc, atol=1e-6))
    print("{} FAILED".format(bad) if bad else "all passed", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

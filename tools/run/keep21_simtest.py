"""2.1 (docs/runs/2.1/README.md, builds 2 and 5): the simulator's KEEP_ZONE and KEEP_SIG, tested on a duel map with a run's switches.

    python tools/run/keep21_simtest.py all [--cmd docs/runs/2.0/2.0e/train.cmd] [--ref <repo of the running run>] [--map bloodrun]

  1. OFF = BIT-IDENTICAL: this tree's simulator with both switches off against the reference tree's (the running run's code), the
     same seed and the same random actions with a keep column (bits 512 / 1024 set at random too: off, they must be ignored):
     inputs, pay, round ends, his target, keep_live and keep_feat frame by frame.
  2. TWO PLAYERS: this tree's duel_env against its generated duel_env_ffa (group 2) with both switches on: the same frame by frame.
  3. ON: KEEP_ZONE=1 KEEP_SIG=1: keep_feat has 7 + KSIG columns in their ranges; keep_live is 1 (the zone layer) only in contact or at an
     arrival and 2 (the quiet layer) only in quiet; with the quiet coin never given (bit 1024 off) the quiet layer decides nothing and
     the quiet readings are the lock rule's (a quiet change only at a target 8 s old or ended); stats["keep3"] adds up.

Each simulator in a process of its own (one World a process). Reads the maps from QLBOT_ROOT's data/maps (the repo)."""
import argparse
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")


def cmd_env(path, root):
    """the `set NAME=value` lines of a run's .cmd (the paths: under root)"""
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln.rstrip("\r\n"), re.I)
        if m and m.group(1) not in ("ROOT", "GPU_MEM_FRACTION", "TRAINER_MASK"):
            out[m.group(1)] = m.group(2).replace("%ROOT%", root).replace("%~dp0..\\..\\..\\..", root)
    return out


def play(tree, module, out, frames, mp, seed, group):
    sys.path.insert(0, os.path.join(tree, "sim"))
    import importlib
    E = importlib.import_module(module)
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    kw = dict(group=group) if module.endswith("ffa") else {}
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=8, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None, **kw)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed + 1)
    rec = {k: [] for k in ("obs", "rew", "don", "intent", "kl", "kf", "zone", "ok3", "mom")}
    o = env.observe()
    nk = len(E.ACTION_DIMS)
    for t in range(frames):
        a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
        a[:, 5] = rng.random(env.n) < 0.5
        col = (rng.random(env.n) < 0.4).astype(np.int64) + 2 * (rng.random(env.n) < 0.7) + 4 * int(t % 8 == 0)
        col = col + 512 * (rng.random(env.n) < 0.4) + 1024 * (rng.random(env.n) < float(os.environ.get("T_QCOIN", "0.6")))
        a = np.concatenate([a, col[:, None]], 1)
        assert a.shape[1] == nk + 1
        o, r, d, info = env.step(a)
        rec["obs"].append(np.asarray(o, np.float32).copy())
        rec["rew"].append(np.asarray(r, np.float32).copy())
        rec["don"].append(np.asarray(d).copy())
        rec["intent"].append(np.asarray(env.intent[:env.n]).copy())
        rec["kl"].append(np.asarray(env.keep_live).astype(np.int8).copy())
        rec["kf"].append(env.keep_feat().copy())
        rec.setdefault("il", []).append(np.asarray(env.intent_live[:env.n], bool).copy())   # (the target was read this frame: every tree has it)
        rec["mom"].append(np.asarray(env.stats.get("moments", np.zeros(1)), np.float64).sum())    # (rounds started from a saved moment, so far)
        kr_ = getattr(env, "keep_rec", None)                 # (the simulator's own zone and forced readings of this frame; off: none)
        rec["zone"].append(kr_[0].copy() if kr_ is not None else np.zeros(env.n, bool))
        rec["ok3"].append(np.stack([kr_[1], kr_[2]], 1).copy() if kr_ is not None else np.zeros((env.n, 2), bool))
        k2_ = getattr(env, "keep_rec2", None)
        rec.setdefault("dbg", []).append(np.stack(list(kr_[3:]) + list(k2_[:2]) + [k2_[2]], 1).astype(np.int64) if (kr_ is not None and k2_ is not None) else np.zeros((env.n, 9), np.int64))
    np.savez(out, **{k: np.array(v) for k, v in rec.items() if v},
             keep3=np.asarray(env.stats.get("keep3", np.zeros(10))), ksig=int(getattr(E, "KSIG", 0)),
             hold=float(E.INTENT_HOLD))
    print("played {} frames of {} from {}".format(frames, module, tree), flush=True)


def sub(tree, module, frames, mp, seed, group, env_):
    f = tempfile.mktemp(suffix=".npz")
    e = dict(os.environ, **env_)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "play", tree, module, f, str(frames), mp, str(seed), str(group)], env=e,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), capture_output=True, text=True)
    print(r.stdout.strip()[-2000:], flush=True)
    if r.returncode != 0:
        print(r.stderr[-6000:], flush=True)
        raise SystemExit("the play of {} from {} failed".format(module, tree))
    return np.load(f)


def same(a, b, keys):
    bad = []
    for k in keys:
        if a[k].shape != b[k].shape:
            bad.append((k, "shape", a[k].shape, b[k].shape))
            continue
        x, y = a[k], b[k]
        diff = ~((x == y) | (np.isnan(x) & np.isnan(y))) if x.dtype.kind == "f" else (x != y)
        if diff.any():
            fr = np.nonzero(diff.reshape(len(diff), -1).any(1))[0]
            bad.append((k, "first frame", int(fr[0]), "frames", len(fr)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--cmd", default=os.path.join(ROOT, "docs", "runs", "2.0", "2.0e", "train.cmd"))
    ap.add_argument("--ref", default=os.environ.get("QLBOT_ROOT") or ROOT)
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=3000)
    a = ap.parse_args()
    if a.what == "play":
        tree, module, out, frames, mp, seed, group = a.rest
        play(tree, module, out, int(frames), mp, int(seed), int(group))
        return
    base = cmd_env(a.cmd, os.environ.get("QLBOT_ROOT") or ROOT)
    off = dict(base, KEEP_ZONE="0", KEEP_SIG="0")
    on = dict(base, KEEP_ZONE="1", KEEP_SIG="1")
    ok = True
    keys = ("obs", "rew", "don", "intent", "kl", "kf")
    # 1. off = bit-identical against the reference tree
    if os.path.abspath(a.ref) != os.path.abspath(ROOT):
        r_ = sub(a.ref, "duel_env_ffa", a.frames, a.map, 7, 2, {k: v for k, v in off.items() if k not in ("KEEP_ZONE", "KEEP_SIG")})
        t_ = sub(ROOT, "duel_env_ffa", a.frames, a.map, 7, 2, off)
        bad = same(r_, t_, keys)
        def noread(z_):
            it_ = z_["intent"]
            c_ = np.zeros_like(it_, bool)
            c_[1:] = it_[1:] != it_[:-1]
            return int((c_ & ~z_["il"]).sum()), int(c_.sum())
        print("1b. target changes on a frame his target was NOT read (not the reading's doing): the reference tree {} of {}, this tree {} of {}".format(
            *noread(r_), *noread(t_)), flush=True)
        print("1. OFF against {}: {}".format(a.ref, "IDENTICAL over {} frames ({} seats)".format(a.frames, r_["obs"].shape[1]) if not bad else "DIFFERENT {}".format(bad)), flush=True)
        ok = ok and not bad
    else:
        print("1. skipped: no reference tree (--ref)")
    # 2. two players: duel_env against duel_env_ffa, switches on
    d_ = sub(ROOT, "duel_env", a.frames, a.map, 9, 2, on)
    f_ = sub(ROOT, "duel_env_ffa", a.frames, a.map, 9, 2, on)
    nb = d_["obs"].shape[2]
    bad = same(dict(d_, obs=d_["obs"]), dict(f_, obs=f_["obs"][..., :nb] if f_["obs"].shape[2] == nb else f_["obs"]), ("rew", "don", "intent", "kl", "kf"))
    print("2. TWO PLAYERS, switches on: duel_env against duel_env_ffa: {}".format("IDENTICAL (pay, ends, target, keep_live, keep_feat)" if not bad else "DIFFERENT {}".format(bad)), flush=True)
    ok = ok and not bad
    # 3. on: the zone split, the signals
    kf, kl, zn, it = f_["kf"], f_["kl"], f_["zone"], f_["intent"]
    K = int(f_["ksig"])
    good = kf.shape[2] == 7 + K
    print("3a. keep_feat {} columns (7 + KSIG {}): {}".format(kf.shape[2], K, "ok" if good else "WRONG"))
    s_ = kf[..., 7:]
    rng_ok = bool(((s_[..., [0, 1, 3]] == 0) | (s_[..., [0, 1, 3]] == 1)).all() and (s_[..., 2] >= 0).all() and (s_[..., 2] <= 2).all()
                  and (s_[..., 4] >= 0).all() and (s_[..., 4] <= 2).all())
    print("3b. signals in their ranges: {}; share of seat-frames on: item there {:.3f}, an item {:.3f}, belief moved {:.3f} (mean {:.3f}), pain {:.3f}, stack fell {:.3f}".format(
        "ok" if rng_ok else "OUT", (s_[..., 0] > 0).mean(), (s_[..., 1] > 0).mean(), (s_[..., 2] > 0).mean(), s_[..., 2].mean(), (s_[..., 3] > 0).mean(), (s_[..., 4] > 0).mean()))
    z1 = bool((zn[kl == 1]).all())
    q2 = bool((~zn[kl == 2]).all())
    print("3c. keep_live 1 (zone layer) {} times, all in contact or arrived: {}; keep_live 2 (quiet layer) {} times, all in quiet: {}".format(
        int((kl == 1).sum()), z1, int((kl == 2).sum()), q2))
    k3 = f_["keep3"]
    print("3d. stats keep3: zone seat-frames {:.0f}, readings {:.0f}, changed {:.0f}; quiet seat-frames {:.0f}, readings {:.0f}, changed {:.0f}; "
          "zone layer decided {:.0f} re-decided {:.0f}; quiet layer decided {:.0f} re-decided {:.0f}".format(*k3))
    sumok = abs(k3[0] + k3[3] - kl.size) < 1 and k3[6] == (kl == 1).sum() and k3[8] == (kl == 2).sum()
    print("3e. keep3 adds up (zone + quiet seat-frames = all, the layers' decisions = keep_live's): {}".format(sumok))
    ok = ok and good and rng_ok and z1 and q2 and (kl == 1).any() and (kl == 2).any() and sumok
    # 4. no quiet coin: the quiet layer decides nothing; a quiet change only where the lock lets it
    n_ = sub(ROOT, "duel_env_ffa", a.frames, a.map, 11, 2, dict(on, T_QCOIN="0"))
    kl0, zn0, it0, o3 = n_["kl"], n_["zone"], n_["intent"], n_["ok3"]
    chg = np.zeros_like(it0, bool)
    chg[1:] = it0[1:] != it0[:-1]
    qchg = chg & ~zn0
    rs4 = np.asarray(n_["don"]).astype(bool)                 # (a round's end: the next round may start from a saved moment, whose target is put in
    rs4 = rs4 | np.concatenate([rs4[:1] * False, rs4[:-1]])  # place at the step's end: not a reading)
    bad4 = qchg & ~o3[..., 0] & ~o3[..., 1] & ~rs4            # a quiet change neither forced nor let by the lock rule (age, ended, a free contact)
    print("4. no quiet coin: quiet layer decisions {} (want 0); quiet target changes {}: forced {}, let by the lock rule {}, NEITHER {} (want 0)".format(
        int((kl0 == 2).sum()), int(qchg.sum()), int((qchg & o3[..., 0]).sum()), int((qchg & ~o3[..., 0] & o3[..., 1]).sum()), int(bad4.sum())))
    ok = ok and (kl0 == 2).sum() == 0 and not bad4.any()
    # 5. the quiet layer's coin given: the quiet changes it made are its own (keep_live 2), none where the lock rule would have held
    #    unless the layer re-decided
    it5 = f_["intent"]
    chg5 = np.zeros_like(it5, bool)
    chg5[1:] = it5[1:] != it5[:-1]
    mm5 = np.diff(np.concatenate([[0.0], np.asarray(f_["mom"])])) > 0     # (a frame some match was put in place from a saved moment)
    rs5 = np.asarray(f_["don"]).astype(bool)
    rs5 = rs5 | np.concatenate([rs5[:1] * False, rs5[:-1]])
    q5 = chg5 & ~zn & (kl == 0) & ~f_["ok3"][..., 0] & ~f_["ok3"][..., 1] & ~rs5 & f_["il"]    # (a change on a frame with a reading)
    print("5a. quiet changes on a frame with no reading at all (outside the reading; see 1b): {}".format(int((chg5 & ~zn & ~f_["il"] & ~rs5).sum())))
    print("5. with the quiet coin: quiet changes neither forced, nor the lock rule's, nor the quiet layer's: {} (want 0)".format(int(q5.sum())))
    for t_, i_ in list(zip(*np.nonzero(q5)))[:5]:
        print("   frame {} seat {}: target {} -> {}, keep_live {}, zone {}, forced {}, rule may {}, done t-2..t {}, age before {:.2f}, kf {}".format(
            t_, i_, it5[t_ - 1, i_], it5[t_, i_], kl[t_, i_], zn[t_, i_], f_["ok3"][t_, i_, 0], f_["ok3"][t_, i_, 1],
            np.asarray(f_["don"])[max(0, t_ - 2):t_ + 1, i_].tolist(), f_["kf"][t_ - 1, i_, 0], np.round(f_["kf"][t_, i_, :7], 2).tolist())
              + " | a match put in place from a saved moment on this frame: {}".format(bool(mm5[t_]))
              + " | kread lrn own kqd kd live may choice: {}".format(f_["dbg"][t_, i_].tolist()))
    ok = ok and not q5.any()
    print("ALL PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

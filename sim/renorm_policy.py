"""Give a network fresh input statistics without changing what it does.

The trainer keeps one running mean and variance per input, averaged over everything it has ever seen, and by 2026-10-08
that average was 1.1e10 frames long: it no longer moves, and it still carries the test map of v4 and v5, which was
twenty times the size of a duel map. The direction to the mega and to the red armor reached the network at 3% and 6%
of their proper size (the same inputs for the three big weapons at 110 to 135%), and every input added since v5 kept the
"mean 0, spread 1" it was appended with (RESULTS 2026-10-08, the wiring review).

This measures every input afresh and rewrites the first layer so that the network's output stays the same:
    W[:, j] *= sd_new / sd_old,    b += W_old[:, j] * (m_new - m_old) / sd_old.
What changes is how fast each input can be learned from afterwards. Only inputs whose size is off by more than a factor
of two are touched, and only those the rewrite is exact for (none of their values in the sample at the old clip of 10).
Inputs that do not vary in the sample are left as they are, except those whose saved spread was zero (they would jump to
the clip the first time they changed): those get spread 1 and zero weights, like a new input. The league snapshots are
fed the learner's statistics, so they are rewritten with it (--also).

--woke OLD.npy: a setting can bring inputs to life that never varied while he trained (GROUND_SENSE, 2026-10-08: the floor
readings beside and behind him were blank for as long as he has had a field of view). Their weights are whatever five
days of a constant input left there. Inputs that are constant in OLD.npy (a sample under the old settings) and vary in the
sample start like new inputs: zero weights, what the constant gave the first layer folded into its bias, fresh
statistics. So he plays exactly as before on what he knew, and learns the rest. --only-woke touches nothing else.

    python sim/renorm_policy.py --src data/sim_runs/RUN/policy.pt --dst data/sim_runs/RUN/policy.pt
        --also "data/sim_runs/RUN/snapshots/snap_*.pt" --sample obs_sample.npy
            (raw inputs from the trainer itself: train_duel_rnn.py --obs-dump, the exact mix of maps and rounds)
    ... or, without --sample: --env duel_env_ffa --map bloodrun,aerowalk,lostworld,arena1 [--set ITEM_BELIEF=1 --set STYLE_P=0.75]
(Anaconda Python; a copy of every file it rewrites is kept beside it as <name>.before_renorm.)
"""
import argparse
import csv
import glob
import importlib
import os
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def sample(E, pol, mp, games, minutes, seed):
    """the inputs of every living seat in normal rounds (the game's spawn) and in item runs; the trainer's own sample
    (--sample) is the better one: this has neither its drills nor its groups"""
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav if os.path.exists(nav) else None)
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.close_p = env.bot_p = 0.0
    env.near_item_p = 0.25
    env.item_run_p = 0.2
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.runner_p = 0.25
    env.round_len, env.arena_len = 120.0, 180.0
    if getattr(env, "lab", None) is not None:
        env.arena_rooms = [3]
        env.lab_p = (0.0, 0.0, 1.0)
    n = env.n
    env.round_t[:] = 1e9
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    keep = []
    for t in range(int(minutes * 60 / E.DT)):
        act, h = pol.act(obs, h)
        obs, r, done, info = env.step(act)
        h[done] = 0.0
        if t % 2 == 0:
            keep.append(obs.copy())
    env.w = None
    return np.concatenate(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--also", default="", help="more networks that share these statistics (the league snapshots), a glob; rewritten in place")
    ap.add_argument("--sample", default="", help="raw inputs written by the trainer (--obs-dump): used instead of playing here")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld,arena1")
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator setting for the sample, as in training")
    ap.add_argument("--dry", action="store_true", help="print what would change and write nothing")
    ap.add_argument("--woke", default="", help="a sample under the settings he trained with: inputs constant there and varying in "
                    "the sample start as new inputs (zero weights, the constant's part in the bias)")
    ap.add_argument("--only-woke", action="store_true", help="rewrite nothing but those")
    ap.add_argument("--woke-names", default="", help="only inputs whose name starts with one of these (comma-separated): a sample "
                    "played differently from the old one brings other inputs to life that have nothing to do with the setting")
    a = ap.parse_args()
    os.environ.update(dict(x.split("=", 1) for x in a.set))
    import torch
    if a.sample:
        X = np.load(a.sample).astype(np.float64)
    else:
        import test_suite as T
        E = importlib.import_module(a.env)
        pol = T.Policy(a.src, seed=3)
        X = np.concatenate([sample(E, pol, mp, a.games, a.minutes, 40 + k) for k, mp in enumerate(a.map.split(","))]).astype(np.float64)
    ck = torch.load(a.src, weights_only=False, map_location="cpu")
    m_old = np.asarray(ck["obs_mean"], np.float64)
    sd_old = np.sqrt(np.asarray(ck["obs_var"], np.float64) + 1e-8)
    assert X.shape[1] == len(m_old), "the sample has {} inputs, the network takes {}".format(X.shape[1], len(m_old))
    m_new, sd_new = m_old.copy(), sd_old.copy()
    varies = X.std(0) > 1e-6
    fresh = X.mean(0)
    reach = np.abs(X - fresh[None, :]).max(0)
    want = np.maximum(np.maximum(X.std(0), reach / 10.0), 0.02)  # with this spread nothing in the sample meets the clip
    at_clip = (np.abs((X - m_old[None, :]) / sd_old[None, :]) > 10).any(0)
    X0 = np.load(a.woke).astype(np.float64) if a.woke else None  # ... nor anything in the sample of what he knew: the rewrite has
    if X0 is not None:                                           # to be exact there too (2026-10-09: a value of the old maps met
        assert X0.shape[1] == len(m_old)                         # the new clip and the first layer moved by 0.04)
        want = np.maximum(want, np.abs(X0 - fresh[None, :]).max(0) / 10.0)
        at_clip |= (np.abs((X0 - m_old[None, :]) / sd_old[None, :]) > 10).any(0)
    off = (sd_old / want > 2.0) | (sd_old / want < 0.5)
    live = varies & off & ~at_clip                               # the inputs rewritten
    m_new[live] = fresh[live]
    sd_new[live] = want[live]
    never = ~varies & (sd_old < 1e-3)                            # constant here and never seen to vary: as a new input
    woke = np.zeros(len(m_old), bool)
    if a.woke:
        woke = (X0.std(0) < 1e-6) & varies
        if a.woke_names:
            nm_ = [r["input"] for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
            assert len(nm_) == len(m_old), "docs/INPUTS.csv does not list this network's inputs"
            woke &= np.array([x.startswith(tuple(a.woke_names.split(","))) for x in nm_])
        if a.only_woke:
            live[:] = False
            never[:] = False
            m_new, sd_new = m_old.copy(), sd_old.copy()          # (the statistics of the others stay as they are)
        live &= ~woke
        never &= ~woke
        m_new[woke], sd_new[woke] = fresh[woke], want[woke]
    m_new[never], sd_new[never] = X[0, never], 1.0
    names = None
    for f in ("INPUTS.csv", "INPUTS_v12.csv", "INPUTS_v11.csv"):
        try:
            nm = [r["input"] for r in csv.DictReader(open(os.path.join(ROOT, "docs", f), encoding="utf-8"))]
        except OSError:
            continue
        if len(nm) == len(m_old):
            names = nm
            break
    print("{} frames; {} of {} inputs vary there; rewritten: {} (their size was off by more than two); left alone: {} that are off but meet "
          "the old clip; {} had never varied (now spread 1, zero weights)".format(
              len(X), int(varies.sum()), len(m_old), int(live.sum()), int((varies & off & at_clip).sum()), int(never.sum())))
    order = [j for j in np.argsort(-np.abs(np.log(sd_old / np.maximum(sd_new, 1e-12)))) if live[j]]
    print("the inputs that change most (saved spread -> new; the factor is the size at which they reached the network, 1 = right):")
    for j in order[:30]:
        print("   {:3d} {:46s} {:8.3f} -> {:6.3f}   x{:.2f}".format(j, (names[j] if names else "")[:46], sd_old[j], sd_new[j], sd_new[j] / sd_old[j]))
    if woke.any():
        print("woken (constant under the old settings, varying now; zero weights, the constant folded into the bias): {}".format(
            [(int(j), (names[j] if names else "")[:28], "was {:g}".format(X0[0, j])) for j in np.nonzero(woke)[0]]))
    left = [j for j in np.nonzero(varies & off & at_clip & ~woke)[0]] if not a.only_woke else []
    if left:
        print("left alone (off, but at the old clip in the sample):", [(int(j), (names[j] if names else "")[:30], round(float(sd_old[j] / want[j]), 2)) for j in left[:12]])

    def rewrite(path):
        c = torch.load(path, weights_only=False, map_location="cpu")
        sd = c["model"] if "model" in c else c
        W = sd["enc.0.weight"].double().numpy()
        b = sd["enc.0.bias"].double().numpy()
        assert W.shape[1] == len(m_old), path
        const = np.clip((X[0] - m_old) / sd_old, -10, 10)        # what an input that never varied gave the first layer
        b2 = b + (W[:, live] * ((m_new[live] - m_old[live]) / sd_old[live])[None, :]).sum(1) + (W[:, never] * const[never][None, :]).sum(1)
        W2 = W.copy()
        W2[:, live] = W[:, live] * (sd_new[live] / sd_old[live])[None, :]
        W2[:, never] = 0.0
        if woke.any():
            zc = np.clip((X0[0] - m_old) / sd_old, -10, 10)     # what the constant gave the first layer
            b2 = b2 + (W[:, woke] * zc[woke][None, :]).sum(1)
            W2[:, woke] = 0.0
        sd["enc.0.weight"] = torch.from_numpy(W2).to(sd["enc.0.weight"].dtype)
        sd["enc.0.bias"] = torch.from_numpy(b2).to(sd["enc.0.bias"].dtype)
        if "obs_mean" in c:
            c["obs_mean"] = m_new.astype(np.asarray(c["obs_mean"]).dtype)
            c["obs_var"] = (sd_new ** 2 - 1e-8).astype(np.asarray(c["obs_var"]).dtype)
        return c

    def first_layer(c, mean, sd):
        m = c["model"] if "model" in c else c
        x = np.clip(((X0 if X0 is not None else X)[::5] - mean) / sd, -10, 10)     # (with --woke: on what he knew, the old sample)
        return x @ m["enc.0.weight"].double().numpy().T + m["enc.0.bias"].double().numpy()

    new = rewrite(a.src)
    before, after = first_layer(ck, m_old, sd_old), first_layer(new, m_new, sd_new)
    worst = float(np.abs(before - after).max())
    print("first layer before and after on the sample: largest difference {:.2e} (typical size {:.2f})".format(worst, float(np.abs(before).mean())))
    assert worst < 1e-3, "the rewrite changed what the network computes"
    if a.dry:
        return
    files = [(a.src, a.dst, new)] + ([(f, f, None) for f in sorted(glob.glob(a.also))] if a.also else [])
    for src, dst, c in files:
        c = c if c is not None else rewrite(src)
        if os.path.exists(dst) and not os.path.exists(dst + ".before_renorm"):
            shutil.copy(dst, dst + ".before_renorm")
        torch.save(c, dst)
    print("rewrote {} file(s); copies of the old ones end in .before_renorm".format(len(files)))


if __name__ == "__main__":
    main()

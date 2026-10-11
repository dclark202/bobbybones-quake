"""Where the switch to his legs starts (duel_env's LEGS): fitted to a plain rule, his to change from the first update.

    python tools/legs_init.py collect <policy.pt> <map> <out.npz>      (a map a process; Anaconda Python)
    python tools/legs_init.py fit <policy.pt> <out.pt> <npz> [<npz> ...]
    python tools/legs_init.py off <file.pt> [<file.pt> ...]            (in place: a network that never uses its legs)

A new output that starts at "never" is not found by trying: a quarter of a second on the legs now and then gains nothing,
strafe jumping pays only when it is kept up. So the switch starts as the rule that was tried by hand on 2026-10-10
(RESULTS 20:45): legs while he has a target and no enemy has been in view for RULE_QUIET seconds. No reward and no
teacher's label says so afterwards: the rule only places the output's weights at the start.

collect: the network plays itself in the simulator's games, item runs and jump runs with the rule on the switch; what
its memory holds on a share of the frames (the 512 numbers its outputs are read from) is kept beside the rule's answer.
fit: a logistic fit of the rule from those numbers becomes the weights of the new output; the network is widened to the
simulator's inputs and outputs first (new inputs at zero weight). Prints how often the fitted output agrees with the rule.
     LEGS_SHARP=2 makes the fit's answers firmer (its weights times two): a plain fit says "legs" with 0.92 where the rule
     does and 0.11 where it does not, so a switch read ten times a second would flicker and his legs would start in fights.
off: the new output with a bias that never chooses the legs (the control and the league's older selves)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULE_QUIET = 1.5
OFF_BIAS = 12.0


def widen(ck, E):
    """the checkpoint with the simulator's inputs and outputs: new inputs at zero weight, new outputs at zero weight and 'off'"""
    import numpy as np
    import torch
    sd = ck["model"]
    extra = E.OBS_DIM - sd["enc.0.weight"].shape[1]
    assert extra >= 0
    if extra:
        sd["enc.0.weight"] = torch.cat([sd["enc.0.weight"], torch.zeros(sd["enc.0.weight"].shape[0], extra, dtype=sd["enc.0.weight"].dtype)], 1)
        ck["obs_mean"] = np.concatenate([ck["obs_mean"], np.zeros(extra)])
        ck["obs_var"] = np.concatenate([ck["obs_var"], np.ones(extra)])
        ck["obs_dim"] = E.OBS_DIM
    need = sum(E.ACTION_DIMS) - sd["pi.weight"].shape[0]
    assert need in (0, 2), need
    if need:
        sd["pi.weight"] = torch.cat([sd["pi.weight"], torch.zeros(2, sd["pi.weight"].shape[1], dtype=sd["pi.weight"].dtype)], 0)
        sd["pi.bias"] = torch.cat([sd["pi.bias"], torch.tensor([OFF_BIAS, -OFF_BIAS], dtype=sd["pi.bias"].dtype)])
    ck["action_dims"] = tuple(E.ACTION_DIMS)
    return ck


def collect(policy, mapname, out):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["LEGS"] = "1"
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import numpy as np
    import duel_env_ffa as E
    import test_suite as T_
    pol = T_.Policy(policy, seed=3)
    n_in = len(pol.mean)
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"), n_matches=int(os.environ.get("LEGS_GAMES", "24")), seed=31, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)), close_p=0.0,
                    teacher=os.path.join(ROOT, "data", "sim_runs", os.environ.get("LEGS_TEACHER", "move_v15n"), "policy.npz"))
    env.react_frames = round(pol.react_ms / 25)
    env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    frames = int(float(os.environ.get("LEGS_MINUTES", "5")) * 60 / E.DT)
    every = int(os.environ.get("LEGS_KEEP", "12"))
    X, Y, V, R = [], [], [], []
    for t in range(frames):
        al, h = pol.act(obs[:, :n_in], h)
        rule = ((env.intent > 0) | (env.run_k > 0)) & ~np.asarray(env.visible, bool) & (env.seen_t > RULE_QUIET) & (env.hp > 0)
        keep = ((t + np.arange(n)) % every == 0) & (env.script == 0) & (env.hp > 0)
        X.append(h[keep].astype(np.float16))
        Y.append(rule[keep])
        V.append(np.asarray(env.visible, bool)[keep])
        R.append((env.run_k >= 0)[keep])
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a[:, :al.shape[1]] = al
        a[:, E.LEGS_HEAD] = rule
        obs, r, d, info = env.step(a)
        h[np.asarray(d) > 0] = 0.0
    L = env.stats["legs"]
    np.savez_compressed(out, x=np.concatenate(X), y=np.concatenate(Y), vis=np.concatenate(V), run=np.concatenate(R))
    print("{}: {} frames kept, the rule says legs on {:.0%}; his legs carried him {:.0%} of his time ({:.0%} in games), speed on legs {:.0f}, on his own {:.0f}".format(
        mapname, sum(len(x) for x in X), float(np.concatenate(Y).mean()), L[0] / max(1.0, L[3]), L[4] / max(1.0, L[5]),
        L[6] / max(1.0, L[0]), L[7] / max(1.0, L[3] - L[0])), flush=True)


def fit(policy, out, files):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import numpy as np
    import torch
    import duel_env_ffa as E
    torch.set_num_threads(4)
    D = [np.load(f) for f in files]
    X = torch.from_numpy(np.concatenate([d["x"] for d in D]).astype(np.float32))
    Y = torch.from_numpy(np.concatenate([d["y"] for d in D]).astype(np.float32))
    vis = np.concatenate([d["vis"] for d in D])
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(X))
    cut = int(0.9 * len(X))
    tr, te = torch.from_numpy(idx[:cut]), torch.from_numpy(idx[cut:])
    w = torch.zeros(X.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([w, b], lr=0.01)
    for ep in range(60):
        perm = tr[torch.randperm(len(tr))]
        for i in range(0, len(perm), 4096):
            k = perm[i:i + 4096]
            loss = torch.nn.functional.binary_cross_entropy_with_logits(X[k] @ w + b, Y[k]) + 1e-4 * (w * w).sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        pr = torch.sigmoid(X[te] @ w + b).numpy()
    y = Y[te].numpy() > 0.5
    v = vis[idx[cut:]]
    print("frames {} ({} held out); the rule says legs on {:.1%}".format(len(X), len(te), float(y.mean())))
    print("the fitted output: the rule's answer is its likelier one on {:.1%} of the frames; it says legs with {:.2f} where the rule does, "
          "{:.2f} where it does not, {:.3f} with an enemy in view".format(float(((pr > 0.5) == y).mean()), float(pr[y].mean()), float(pr[~y].mean()),
                                                                        float(pr[v].mean()) if v.any() else 0.0))
    sharp = float(os.environ.get("LEGS_SHARP", "1"))        # the fit's answers made firmer by this factor (see the top)
    if sharp != 1.0:
        with torch.no_grad():
            pr = torch.sigmoid(sharp * (X[te] @ w + b)).numpy()
        print("made firmer by {:g}: legs with {:.3f} where the rule says so, {:.3f} where it does not, {:.4f} with an enemy in view".format(
            sharp, float(pr[y].mean()), float(pr[~y].mean()), float(pr[v].mean()) if v.any() else 0.0))
    ck = widen(torch.load(policy, weights_only=False, map_location="cpu"), E)
    sd = ck["model"]
    o = sum(E.ACTION_DIMS[:E.LEGS_HEAD])
    with torch.no_grad():
        sd["pi.weight"][o] = 0.0
        sd["pi.bias"][o] = 0.0
        sd["pi.weight"][o + 1] = (sharp * w).detach().to(sd["pi.weight"].dtype)
        sd["pi.bias"][o + 1] = sharp * float(b)
    ck["legs_init"] = dict(rule_quiet=RULE_QUIET, frames=len(X), agree=float(((pr > 0.5) == y).mean()), sharp=sharp)
    torch.save(ck, out)
    print("written:", out, "({} inputs, outputs {})".format(sd["enc.0.weight"].shape[1], ck["action_dims"]))


def off(files):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import torch
    import duel_env_ffa as E
    o = sum(E.ACTION_DIMS[:E.LEGS_HEAD])
    for f in files:
        ck = widen(torch.load(f, weights_only=False, map_location="cpu"), E)
        sd = ck["model"]
        with torch.no_grad():
            sd["pi.weight"][o:o + 2] = 0.0
            sd["pi.bias"][o], sd["pi.bias"][o + 1] = OFF_BIAS, -OFF_BIAS
        torch.save(ck, f)
        print("no legs:", f, "({} inputs, {} outputs)".format(sd["enc.0.weight"].shape[1], len(ck["action_dims"])))


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "fit":
        fit(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == "off":
        off(sys.argv[2:])
    else:
        sys.exit(__doc__)

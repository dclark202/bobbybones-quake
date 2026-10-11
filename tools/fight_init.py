"""Where "the enemy" as a target starts (duel_env's FIGHT_TARGET): fitted to a plain rule, his to change from the first update.

    python tools/fight_init.py collect <policy.pt> <map> <out.npz>     (a map a process; Anaconda Python)
    python tools/fight_init.py fit <policy.pt> <out.pt> <npz> [<npz> ...]
    python tools/fight_init.py never <file.pt> [<file.pt> ...]         (in place: a network that never takes the enemy as its target)

A ninth intention that starts at "never" would be found slowly and the item rule's lesson would pull against it. So its
weights are placed by a fit to a plain rule (rule() below: he is strong and armed, the enemy has just spawned and was seen
a moment ago), as the switch to his legs was (tools/legs_init.py). No reward
and no teacher's label says so afterwards, and the item rule's lesson leaves the new choice alone (the trainer).

collect: the network plays itself with the rule on its intention; what its memory holds on a share of the frames is kept
beside the rule's answer. fit: a logistic fit of the rule becomes the weights of the new choice (FIGHT_SHARP makes it
firmer); the network is widened to the simulator's inputs and outputs first. never: the new choice with a bias that is
never taken (the control and the league's older selves)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEVER = -20.0


def rule(env, E):
    """FIGHT_RULE=narrow (the default since the trial of 2026-10-11): strong and armed, the enemy spawned under 10 seconds
    ago and was seen within 4: the pros' own strongest case, and level in duels where the broad rule lost (it cost him
    his items). FIGHT_RULE=broad: strong and armed, the enemy known within 8 s, and he is new (20 s) or I have 175"""
    st = env.hp + env.armor
    big = [E.RL, E.LG, E.RG, E.PG]
    armed = (env.has[:, big] & (env.ammo[:, big] > 0)).any(1)
    new_ = env.life_t[env._others_arr()].min(1)
    if os.environ.get("FIGHT_RULE", "narrow") == "broad":
        return (st >= 125.0) & armed & (env.seen_t <= 8.0) & ((new_ < 20.0) | (st >= 175.0)) & (env.hp > 0) & (env.run_k < 0)
    return (st >= 125.0) & armed & (new_ < 10.0) & (env.seen_t <= 4.0) & (env.hp > 0) & (env.run_k < 0)


def widen(ck, E, bias=NEVER):
    """the checkpoint with the simulator's inputs (new ones at zero weight) and the ninth intention (zero weight, the bias given)"""
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
    old = [int(x) for x in ck["action_dims"]]
    new = [int(x) for x in E.ACTION_DIMS]
    if old != new:
        assert len(old) == len(new) and old[:10] == new[:10] and old[11:] == new[11:] and new[10] == old[10] + 1, (old, new)
        o = sum(old[:10]) + old[10]                           # where the new choice's row goes
        w, b = sd["pi.weight"], sd["pi.bias"]
        sd["pi.weight"] = torch.cat([w[:o], torch.zeros(1, w.shape[1], dtype=w.dtype), w[o:]], 0)
        sd["pi.bias"] = torch.cat([b[:o], torch.tensor([bias], dtype=b.dtype), b[o:]])
        ck["action_dims"] = tuple(new)
    return ck


def collect(policy, mapname, out):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["FIGHT_TARGET"] = "1"
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import numpy as np
    import duel_env_ffa as E
    import test_suite as T_
    pol = T_.Policy(policy, seed=3)
    n_in = len(pol.mean)
    o10 = sum(pol.dims[:10])
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"), n_matches=int(os.environ.get("FIGHT_GAMES", "24")), seed=33, loadout="all",
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)), close_p=0.0)
    env.react_frames = round(pol.react_ms / 25)
    env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.item_run_p = env.jump_run_p = 0.0                    # games only: the enemy is no target in a run
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    frames = int(float(os.environ.get("FIGHT_MINUTES", "6")) * 60 / E.DT)
    every = int(os.environ.get("FIGHT_KEEP", "12"))
    X, Y, C = [], [], []
    for t in range(frames):
        al, h = pol.act(obs[:, :n_in], h)
        r_ = rule(env, E)
        keep = ((t + np.arange(n)) % every == 0) & (env.script == 0) & (env.hp > 0)
        lg = h[keep] @ pol.wp[o10:o10 + pol.dims[10]].T + pol.bp[o10:o10 + pol.dims[10]]
        X.append(h[keep].astype(np.float16))
        Y.append(r_[keep])
        C.append((lg.max(1) + np.log(np.exp(lg - lg.max(1, keepdims=True)).sum(1))).astype(np.float32))   # what his other choices weigh together
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a[:, :al.shape[1]] = al
        a[:, E.INTENT_HEAD] = np.where(r_, E.EN_INTENT, a[:, E.INTENT_HEAD])
        obs, r, d, info = env.step(a)
        h[np.asarray(d) > 0] = 0.0
    F = env.stats["en_frames"]
    L = env.stats["legs"]
    np.savez_compressed(out, x=np.concatenate(X), y=np.concatenate(Y), c=np.concatenate(C))
    print("{}: {} frames kept, the rule says the enemy on {:.1%}; his intention was the enemy {:.1%} of his time ({:.0%} of that on his legs, {:.0%} with him in view)".format(
        mapname, sum(len(x) for x in X), float(np.concatenate(Y).mean()), F[0] / max(1.0, L[3]), F[1] / max(1.0, F[0]), F[2] / max(1.0, F[0])), flush=True)


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
    c = float(np.concatenate([d["c"] for d in D]).mean())
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(X))
    cut = int(0.9 * len(X))
    tr, te = torch.from_numpy(idx[:cut]), torch.from_numpy(idx[cut:])
    w = torch.zeros(X.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([w, b], lr=0.01)
    pos = float(Y.mean())
    for ep in range(60):
        perm = tr[torch.randperm(len(tr))]
        for i in range(0, len(perm), 4096):
            k = perm[i:i + 4096]
            loss = torch.nn.functional.binary_cross_entropy_with_logits(X[k] @ w + b, Y[k]) + 1e-4 * (w * w).sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
    sharp = float(os.environ.get("FIGHT_SHARP", "1"))
    with torch.no_grad():
        pr = torch.sigmoid(sharp * (X[te] @ w + b)).numpy()
    y = Y[te].numpy() > 0.5
    print("frames {} ({} held out); the rule says the enemy on {:.1%}".format(len(X), len(te), pos))
    print("the fitted choice (firmer by {:g}): the rule's answer is its likelier one on {:.1%} of the frames; it says the enemy with {:.2f} where the rule does, {:.3f} where it does not".format(
        sharp, float(((pr > 0.5) == y).mean()), float(pr[y].mean()) if y.any() else 0.0, float(pr[~y].mean())))
    ck = widen(torch.load(policy, weights_only=False, map_location="cpu"), E)
    sd = ck["model"]
    o = sum(E.ACTION_DIMS[:E.INTENT_HEAD]) + E.EN_INTENT
    with torch.no_grad():
        sd["pi.weight"][o] = (sharp * w).detach().to(sd["pi.weight"].dtype)
        sd["pi.bias"][o] = sharp * float(b) + c              # (against what his other choices weigh together on average)
    ck["fight_init"] = dict(frames=len(X), rule_share=pos, agree=float(((pr > 0.5) == y).mean()), sharp=sharp, others=c)
    torch.save(ck, out)
    print("written:", out, "({} inputs, outputs {})".format(sd["enc.0.weight"].shape[1], ck["action_dims"]))


def never(files):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import torch
    import duel_env_ffa as E
    o = sum(E.ACTION_DIMS[:E.INTENT_HEAD]) + E.EN_INTENT
    for f in files:
        ck = widen(torch.load(f, weights_only=False, map_location="cpu"), E)
        sd = ck["model"]
        with torch.no_grad():
            sd["pi.weight"][o] = 0.0
            sd["pi.bias"][o] = NEVER
        torch.save(ck, f)
        print("never the enemy:", f, "({} inputs, outputs {})".format(sd["enc.0.weight"].shape[1], tuple(ck["action_dims"])))


if __name__ == "__main__":
    if sys.argv[1] == "collect":
        collect(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "fit":
        fit(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == "never":
        never(sys.argv[2:])
    else:
        sys.exit(__doc__)

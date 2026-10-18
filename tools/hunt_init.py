"""v0.3.1 (B-256, B-257): a network of v0.3's shape made a network of the simulator with EN_STACK and HUNT
(sim/duel_env.py), with both new parts closed: it answers as before.

    python tools/hunt_init.py widen <in.pt> <out.pt> [--stats sample.npy]      (a new file)
    python tools/hunt_init.py never <file.pt> [<file.pt> ...]                  (in place: the control, the league's files)
    python tools/hunt_init.py open <in.pt> <out.pt> --from-nothing 0.03         (the enemy as a target opened out of "nothing")
    python tools/hunt_init.py open <in.pt> <out.pt> --from YA 0.1               (... out of another choice: an item or a place)

widen / never: (1) the inputs are widened to the simulator's: the six of the enemy's believed stack (N_ES, the group
"v031 enemy stack") get zero weight in the old encoder, mean 0 and spread 1 in the input statistics (or, with --stats, the
mean and spread of a sample of raw inputs under EN_STACK=1: the weights are zero, so this changes nothing either), and a
token of their own in the attention part (a new kind, "stack", its gate shut: attn.GATE_SHUT, nothing looks at it);
(2) the intention "the enemy" (EN_INTENT, the ninth choice; in v0.3 a row of zeros with bias -20) becomes a copy of the
row of "nothing" (weights and bias) less 20 (NEVER): in every state it is e^-20 as likely as "nothing", never chosen;
(3) the input "his intention is the enemy" (always 0 in v0.3's training) gets zero weight in the attention part's first
layer too (it had zero weight in the encoder already): the input is woken without a jump when the choice is opened.
Nothing else is touched: the holding places keep their rows (tools/targets_init.py's widen would shut them again).
`python sim/add_attention.py --same old.pt new.pt` (or this file's `same`) proves the answers unchanged.

open --from-nothing s: "the enemy" opens out of "nothing" only, as the holding places were (tools/targets_init.py open
--from-nothing): its row is the row of "nothing" plus log(s), and "nothing" keeps 1 - s of what it had: in every state
every item and place is chosen exactly as often as before at a reading, and of the readings he would have chosen nothing
at, a share s is the enemy. (CLAUDE.md: a choice opened by a bias over all his readings costs what it displaces.)
v0.3 (keep/policy_end.pt) never chooses "nothing" (0 of 18,880 sampled intentions in self-play on Blood Run, 2026-10-15: the
yellow armors 50%, the red 16%, the mega 14%, the places 0.3%): opened out of "nothing" the enemy stays unchosen.
--from NAME s does the same out of the choice NAME of duel_env.INTENTS ("YA", "MH", "H1", ...): exact in every state,
only that choice gives up the share s of its readings.

    python tools/hunt_init.py same <old.pt> <new.pt> [<obs.npy>]   the two answer alike: every output's probabilities
         on a batch of observations (the old network's own inputs: the first columns), largest difference printed

HUNT_ENV: the simulator's module (default duel_env_ffa, as the run's networks)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
NEVER = -20.0
MODULE = os.environ.get("HUNT_ENV") or "duel_env_ffa"
INPUTS = os.path.join(os.path.dirname(HERE), "docs", "INPUTS.csv")


def _env():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(k_, "1")
    for p_ in (SIM, HERE):
        if p_ not in sys.path:
            sys.path.insert(0, p_)
    import importlib
    return importlib.import_module(MODULE)


def widen(ck, E, stats=None):
    """the checkpoint with the simulator's inputs and the closed rows (see the top); returns (new inputs, new token kinds)"""
    import numpy as np
    import torch
    import targets_init as TI
    sd = ck["model"]
    old_n = sd["enc.0.weight"].shape[1]
    extra = E.OBS_DIM - old_n
    assert extra in (0, E.N_ES), "the network has {} inputs, the simulator {} (this converter adds the {} of N_ES only)".format(old_n, E.OBS_DIM, E.N_ES)
    assert [int(x) for x in ck["action_dims"]] == [int(x) for x in E.ACTION_DIMS], (ck["action_dims"], E.ACTION_DIMS)
    if extra:
        W = sd["enc.0.weight"]
        sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], extra, dtype=W.dtype)], 1)
        m_, v_ = np.zeros(extra), np.ones(extra)
        if stats is not None:                                 # (a sample of raw inputs under EN_STACK=1: their mean and spread)
            X = np.load(stats).astype(np.float64)
            assert X.shape[1] == E.OBS_DIM, (X.shape, E.OBS_DIM)
            m_ = X[:, -extra:].mean(0)
            v_ = np.maximum(X[:, -extra:].std(0), 0.02) ** 2
        ck["obs_mean"] = np.concatenate([np.asarray(ck["obs_mean"], np.float64), m_]).astype(np.asarray(ck["obs_mean"]).dtype)
        ck["obs_var"] = np.concatenate([np.asarray(ck["obs_var"], np.float64), v_]).astype(np.asarray(ck["obs_var"]).dtype)
        ck["obs_dim"] = E.OBS_DIM
    fresh = []
    if ck.get("attn") is not None and ck["attn"]["obs_dim"] != E.OBS_DIM:
        fresh = TI.widen_attn(ck, INPUTS)
        assert ck["attn"]["obs_dim"] == E.OBS_DIM and fresh == ["stack"], (ck["attn"]["obs_dim"], fresh)
    I = E.INTENT_HEAD
    o = sum(E.ACTION_DIMS[:I])
    with torch.no_grad():                                     # "the enemy": a copy of "nothing", never chosen
        sd["pi.weight"][o + E.EN_INTENT] = sd["pi.weight"][o].clone()
        sd["pi.bias"][o + E.EN_INTENT] = sd["pi.bias"][o] + NEVER
    j_ = E.OBS_DIM - getattr(E, "N_RAIM", 0) - getattr(E, "N_PREF", 0) - getattr(E, "N_EMG", 0) - E.N_ES - (E.N_B3 + E.N_B2 + E.N_V02) - 1  # the input "his intention is the enemy" (the last of N_V15)
    at = ck.get("attn")
    if at is not None:
        hit = 0
        for i, k in enumerate(at["kinds"]):
            for t in k["idx"]:
                if j_ in t:
                    with torch.no_grad():
                        sd["attn.emb.{}.weight".format(i)][:, t.index(j_)] = 0.0
                    hit += 1
        assert hit == 1, hit
    assert float(sd["enc.0.weight"][:, j_].abs().max()) == 0.0, "the input 'his intention is the enemy' has weight in the encoder"
    ck["hunt_init"] = dict(en_row="the row of 'nothing' {:+g}".format(NEVER), inputs_added=int(extra), tokens_added=fresh)
    return extra, fresh, j_


def say(what, f, ck, extra, fresh, j_):
    print("{}: {} ({} inputs, {} new, outputs {}, attention tokens {}{}); input {} 'his intention is the enemy' woken at zero weight".format(
        what, f, ck["model"]["enc.0.weight"].shape[1], extra, tuple(ck["action_dims"]),
        ck["attn"]["tokens"] - 1 if ck.get("attn") else 0, ", new and shut: " + ", ".join(fresh) if fresh else "", j_))


def main_widen(src, dst, stats=None):
    E = _env()
    import torch
    torch.set_num_threads(1)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    r = widen(ck, E, stats)
    torch.save(ck, dst)
    say("widened, 'the enemy' never chosen", dst, ck, *r)


def main_never(files):
    E = _env()
    import torch
    torch.set_num_threads(1)
    for f in files:
        ck = torch.load(f, weights_only=False, map_location="cpu")
        r = widen(ck, E)
        torch.save(ck, f)
        say("never the enemy", f, ck, *r)


def main_open(src, dst, s_, src_name="none"):
    E = _env()
    import numpy as np
    import torch
    torch.set_num_threads(1)
    assert 0.0 < s_ < 1.0, s_
    ck = torch.load(src, weights_only=False, map_location="cpu")
    if ck["model"]["enc.0.weight"].shape[1] != E.OBS_DIM or "hunt_init" not in ck:
        r = widen(ck, E)
    else:
        r = (0, [], E.OBS_DIM - getattr(E, "N_RAIM", 0) - getattr(E, "N_PREF", 0) - getattr(E, "N_EMG", 0) - E.N_ES - (E.N_B3 + E.N_B2 + E.N_V02) - 1)
    sd = ck["model"]
    o = sum(E.ACTION_DIMS[:E.INTENT_HEAD])
    c_ = E.INTENTS.index(src_name)
    assert c_ != E.EN_INTENT, "the enemy out of itself"
    with torch.no_grad():
        sd["pi.weight"][o + E.EN_INTENT] = sd["pi.weight"][o + c_].clone()
        sd["pi.bias"][o + E.EN_INTENT] = sd["pi.bias"][o + c_] + float(np.log(s_))
        sd["pi.bias"][o + c_] = sd["pi.bias"][o + c_] + float(np.log(1.0 - s_))
    ck["hunt_init"] = dict(ck.get("hunt_init") or {}, opened_from=src_name, share=s_)
    torch.save(ck, dst)
    say("'the enemy' opened out of '{}'".format(src_name), dst, ck, *r)
    print("  of the readings he would have chosen '{}' at, {:.1%} are the enemy now; every other choice's share is what it was".format(src_name, s_))


def _logits(pol, obs, h):
    """test_suite.Policy.act's sums, the logits returned (no learned cell table, no slow memory: v0.3's shape)"""
    import numpy as np
    import test_suite as T
    assert pol.cell is None and pol.slow is None
    obs = obs[:, :len(pol.mean)]
    x = np.clip((obs - pol.mean) / np.sqrt(pol.var + 1e-8), -10, 10).astype(np.float32)
    xa = x
    x = np.tanh(x @ pol.w0.T + pol.b0)
    x = np.tanh(x @ pol.w1.T + pol.b1)
    if pol.attP is not None:
        x = x + pol.attn_fwd(pol.attn, pol.attP, xa)
    gi = x @ pol.wih.T + pol.bih
    gh = h @ pol.whh.T + pol.bhh
    H = pol.H
    r = T.sig(gi[:, :H] + gh[:, :H])
    z = T.sig(gi[:, H:2 * H] + gh[:, H:2 * H])
    nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    h = ((1 - z) * nn_ + z * h).astype(np.float32)
    return h @ pol.wp.T + pol.bp, h


def main_same(a, b, obs=None):
    """every output's probabilities of the two networks on the same observations (test_suite.Policy's sums)"""
    E = _env()
    import numpy as np
    import test_suite as T
    pa, pb = T.Policy(a, seed=1), T.Policy(b, seed=1)
    if obs is None:
        rng = np.random.default_rng(5)
        X = rng.normal(0, 1, (512, len(pb.mean))) * np.sqrt(pb.var + 1e-8) + pb.mean
        X[:, E.OBS_DIM - getattr(E, "N_RAIM", 0) - getattr(E, "N_PREF", 0) - getattr(E, "N_EMG", 0) - E.N_ES - (E.N_B3 + E.N_B2 + E.N_V02) - 1] = 0.0      # (his intention is the enemy: 0 while it is never chosen)
    else:
        X = np.load(obs).astype(np.float64)
    worst, worst_lg = 0.0, 0.0
    ha, hb = pa.zeros(len(X)), pb.zeros(len(X))
    for t in range(4):                                       # a few frames, so the memory carries the inputs too
        la, ha = _logits(pa, X, ha)
        lb, hb = _logits(pb, X, hb)
        o = 0
        for k, d in enumerate(pa.dims):
            za, zb = la[:, o:o + d], lb[:, o:o + d]
            if k == E.INTENT_HEAD:                           # (the enemy's row is the one row meant to differ: at e^-20)
                keep = [c for c in range(d) if c != E.EN_INTENT]
                worst_lg = max(worst_lg, float(np.abs(za[:, keep] - zb[:, keep]).max()))
            else:
                worst_lg = max(worst_lg, float(np.abs(za - zb).max()))
            pa_ = np.exp(za - za.max(1, keepdims=True))
            pa_ /= pa_.sum(1, keepdims=True)
            pb_ = np.exp(zb - zb.max(1, keepdims=True))
            pb_ /= pb_.sum(1, keepdims=True)
            worst = max(worst, float(np.abs(pa_ - pb_).max()))
            o += d
        worst_lg = max(worst_lg, float(np.abs(ha - hb).max()))
    print("attention part: {} / {}; ".format("on" if pa.attP is not None else "off", "on" if pb.attP is not None else "off"), end="")
    print("{} observations x 4 frames: largest difference of any output's probabilities {:.3g}; of the logits (the enemy's row "
          "aside) and the memory {:.3g}".format(len(X), worst, worst_lg))
    return worst


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    stats = None
    if "--stats" in args:
        i = args.index("--stats")
        stats = args[i + 1]
        del args[i:i + 2]
    if args[0] == "widen":
        main_widen(args[1], args[2], stats)
    elif args[0] == "never":
        main_never(args[1:])
    elif args[0] == "open":
        if "--from" in args:
            i = args.index("--from")
            nm_, s_ = args[i + 1], float(args[i + 2])
            del args[i:i + 3]
        else:
            i = args.index("--from-nothing")
            nm_, s_ = "none", float(args[i + 1])
            del args[i:i + 2]
        main_open(args[1], args[2], s_, nm_)
    elif args[0] == "same":
        main_same(args[1], args[2], args[3] if len(args) > 3 else None)
    else:
        sys.exit(__doc__)

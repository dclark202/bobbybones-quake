"""2.1 (docs/runs/2.1/TRAINER_PARTS.md, piece 1; the trainer's --known-odds): the brain's question "does the enemy know where I am".
The owner, 2026-11-11: a hold, an ambush or a spam only pays if he does not; barging is only safe if he does not. The head reasons
about where the enemy is, never about what the enemy knows: this readout gives it that number.

The truth is the simulator's (KNOWN_TRUTH=1: info["aux"]'s en_knows: the enemy has him noticed in view, or his own belief of him is
within KNOWN_R units and no older than KNOWN_T seconds; en_heard: the enemy heard him within the last second), the PRESENT truth, a
label only and never an input. The readout reads the brain's state and the hands' memory beside it (as the fight odds' "both"), at
the head's ticks; its gradient reaches its own layers only.

Where it lives: a module of its own beside the network ("known" at the top of a checkpoint, as the map sense's and the scorer's),
its own Adam (cold at a start), learnt after the PPO epochs from the rollout's kept head inputs (their parts "brain" and "hands":
the same numbers, at half precision) and the truth of the same frames. Read: its first chance (knows) minus 0.5 among the head's
inputs (the part "ins", sim/head2.py INS_BQ) and written into every candidate row's column INS_FILL["known"].

Layout: {"version": 1, "bel", "mem", "width", "tick", "every", "d": 2, "outs": ["knows", "heard"], "readouts": [{"name": "both", ...}]}
(the fight odds' shape, so its lesson and its record are sim/fightodds.py's own).
"""
import numpy as np                                           # (numpy alone at the top: a game server's plugin reads np_chance)

COLS = ("en_knows", "en_heard")
OUTS = ("knows", "heard")
SEED = 4071


def layout(bel=256, mem=512, hid=64, tick=8, every=6):
    ro = [dict(name="both", src="belief+memory", inp=int(bel) + int(mem), hid=int(hid), d=len(OUTS))]
    return dict(version=1, bel=int(bel), mem=int(mem), width=int(bel) + int(mem), tick=int(tick), every=int(every), d=len(OUTS),
                outs=list(OUTS), readouts=ro)


def make_module(L):
    """Linear(width -> hid) + ReLU + Linear(hid -> 2), its last layer at zero (a chance of a half each), from a stream of its own"""
    import control as control_
    assert int(L.get("version", 0)) == 1, "knownodds: layout version 1 expected"
    return control_.make_module1(L["readouts"][0], SEED)


def chance(mod, s_brain, hands):
    """-> [n, 2] the chances (knows, heard), a number (no gradient); the inputs at half precision, as the lesson's rows are kept"""
    import torch
    with torch.no_grad():
        x = s_brain.detach().float()
        m = int(mod[0].in_features) - x.shape[1]
        x = torch.cat([x, hands.detach()[:, :m].float()], 1)
        return torch.sigmoid(mod(x.half().float()).float())


def np_params(sd):
    g = lambda k: np.asarray(sd[k].detach().cpu().numpy() if hasattr(sd[k], "detach") else sd[k], np.float32)   # noqa: E731
    return tuple(g("{}.{}".format(i, w)) for i in (0, 2) for w in ("weight", "bias"))


def np_chance(P, s_brain, hands):
    """chance() in numpy (the checks, the servers)"""
    x = np.asarray(s_brain, np.float32)
    m = int(P[0].shape[1]) - x.shape[1]
    x = np.concatenate([x, np.asarray(hands, np.float32)[:, :m]], 1).astype(np.float16).astype(np.float32)
    z = np.maximum(x @ P[0].T + P[1], 0.0) @ P[2].T + P[3]
    return (1.0 / (1.0 + np.exp(-z))).astype(np.float32)


def batch(L, U2, o_brain, o_hands, aux, ix, live=None):
    """a rollout's samples: U2 [J, N, u] the head's inputs at its ticks (the frame of tick j: (j + 1) * tick - 1), o_brain and o_hands
    the (from, to) columns of the parts "brain" and "hands" in it, aux [T + 1, N, C] the truth (row t: before frame t's step, what
    that frame's inputs show), ix: column -> index. Every `every`-th tick; a sample where the enemy is alive (and live [N], if
    given: the seats that count). -> (X [B, width] float16, Y [B, 2], M [B, 2]) on the host, or None"""
    import torch
    K, E = int(L["tick"]), max(1, int(L["every"]))
    J = U2.shape[0]
    xs, ys = [], []
    for j in range(E - 1, J, E):
        f = (j + 1) * K - 1
        if f >= aux.shape[0]:
            break
        a = aux[f].float()
        ok = a[:, ix["en_alive"]] > 0.5
        if live is not None:
            ok = ok & torch.as_tensor(live, dtype=torch.bool)
        if not bool(ok.any()):
            continue
        u = U2[j][ok]
        xs.append(torch.cat([u[:, o_brain[0]:o_brain[1]], u[:, o_hands[0]:o_hands[0] + int(L["mem"])]], 1).to(torch.float16))
        ys.append(torch.stack([a[ok][:, ix[c]] for c in COLS], -1))
    if not xs:
        return None
    X, Y = torch.cat(xs, 0), torch.cat(ys, 0)
    M = (Y >= 0).float()
    return X, (Y > 0.5).float(), M


def learn(mod, opt, L, X, Y, M, lr, dev, gen):
    """scored before it is learnt from, then one pass (sim/fightodds.py's lesson on this readout)"""
    import fightodds as fightodds_
    return fightodds_.learn({"both": mod}, {"both": opt}, L, X, Y, M, lr=lr, dev=dev, gen=gen)


def record(acc, w, L):
    """-> metrics.jsonl's "known": frames, how often the enemy knows / heard, the Brier score beside a half's and the best constant's,
    skill, AUC"""
    import fightodds as fightodds_
    rec = fightodds_.record(acc, w, L)
    if "outs" in rec:
        rec["outs"] = list(OUTS)
        nf = [max(1, int(x)) for x in rec["frames"]]
        rec["share"] = [round(int(rec["pos"][i]) / nf[i], 4) for i in range(len(nf))]      # how often the truth says yes
    return rec

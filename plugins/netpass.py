"""The network's forward pass in plain numpy, for both plugins (no torch on a game server).

The same sums as sim/test_suite.py's Policy.act, the reference: inputs normalised and cut at +-10, two layers, the
attention part of v0.2 added to what they give (sim/attn.py's forward_np; skipped while its last layer, the door, is
all zeros), one step of his memory, one sampled choice per output. Not a plugin: plugins/duelbot.py and
plugins/ffabot.py import it; a test outside a server can too (it does not need minqlx).

    P, A = load("/tmp/practice/policy.npz")      # the arrays of sim/export_duel.py; A = (layout, weights) or None
    acts, h = step(P, A, obs, h, rng)             # obs [B, inputs], h [B, memory] -> choices [B, outputs], the new memory

(v0.4) A network with a head (sim/head.py) carries the head's state at the end of h (width(P) is wider), ticks it every
eighth frame and adds its target and way to the hands' intention and way: give step() the tick's events (events=,
fetched when head_due(P, h) says the coming frame ticks) and clear a seat with clear(P, h, rows), not h[rows] = 0
(clear keeps the head's tick clock, as the trainer's global frame count does).
"""
import json
import os
import sys

import numpy as np


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def load(path):
    """policy.npz -> (its arrays as a dict, the attention part or None). The attention part is (the token layout, its
    weights by the names sim/attn.py gives them); None for a network without one or with its door still shut."""
    z = np.load(path)
    P = {k: z[k] for k in z.files}
    A = None
    if "attn" in P:
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import attn as attn_                                 # sim/attn.py: numpy only (torch is imported inside make_module alone)
        lay = json.loads(str(P["attn"]))
        W = {k[len("attn."):]: v for k, v in P.items() if k.startswith("attn.")}
        assert int(lay["obs_dim"]) == P["w0"].shape[1], "the tokens are cut from {} inputs, the network has {}".format(lay["obs_dim"], P["w0"].shape[1])
        if np.abs(W["door.weight"]).sum() > 0:
            # (the index lists as arrays once, not at every frame: forward_np takes either)
            lay = dict(lay, kinds=[dict(k_, idx=np.asarray(k_["idx"], np.int64)) for k_ in lay["kinds"]])
            A = (lay, W, attn_.forward_np)
    if "slow" in P:                                          # (--slow-mem) the slow memory: kept beside the arrays as (layout, weights, step)
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import slowmem as slowmem_                           # sim/slowmem.py: numpy only at the top
        lay = json.loads(str(P["slow"]))
        P["_slow"] = (lay, {k[len("slow."):]: np.asarray(v, np.float32) for k, v in P.items() if k.startswith("slow.")}, slowmem_.np_step,
                      slowmem_.width(lay))
    if "head" in P:                                          # (v0.4) the head: kept beside the arrays as (layout, weights, the module, the
        if "/sim" not in sys.path and os.path.isdir("/sim"):     # width of its state, where its state starts in a seat's array)
            sys.path.insert(0, "/sim")
        import head as head_                                 # sim/head.py: numpy only at the top
        lay = json.loads(str(P["head"]))
        base = P["_slow"][3] if "_slow" in P else P["whh"].shape[1]
        P["_head"] = (lay, {k[len("head."):]: np.asarray(v, np.float32) for k, v in P.items() if k.startswith("head.")}, head_,
                      head_.np_state_width(lay), base)
    P["_uni"] = None                                         # (--legs-feat, --legs-guide) (layout, door or None, guide weights or None):
    if "legs_unify" in P:                                    # None while both parts are at zero (they add nothing then)
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import legs_unify as LU_                             # sim/legs_unify.py: numpy only at the top
        lay = LU_.as_layout(P["legs_unify"])
        D = (P["legs_door_w"], P["legs_door_b"]) if "legs_door_w" in P and (np.abs(P["legs_door_w"]).sum() + np.abs(P["legs_door_b"]).sum()) > 0 else None
        G = np.asarray(P["legs_guide"], np.float32) if "legs_guide" in P and np.abs(P["legs_guide"]).sum() > 0 else None
        T = None                                             # (v0.3.4 A) the gate and the motor layer; B: the residual (skipped at zero)
        if lay.get("gate") and "legs_gate_w" in P:
            T = tuple(np.asarray(P[k_], np.float32) for k_ in ("legs_gate_w", "legs_gate_b", "legs_motor_w", "legs_motor_b"))
            T = T if sum(float(np.abs(x_).sum()) for x_ in T) > 0 else None
        if lay.get("residual") and "legs_res_w" in P:
            R_ = tuple(np.asarray(P[k_], np.float32) for k_ in ("legs_res_a_w", "legs_res_a_b", "legs_res_w", "legs_res_b"))
            P["_res"] = (R_, LU_) if sum(float(np.abs(x_).sum()) for x_ in R_) > 0 else None
        if D is not None or G is not None or T is not None:
            assert "legs_w0" in P, "a network with legs_unify has the legs' branch inside"
            P["_uni"] = (lay, D, G, LU_, T)
    return P, A


def needs_xl(P):
    """(--legs-feat, --legs-guide) step() needs the branch's inputs (xl=, the simulator's legs_prep() of the frame,
    before the step and before legs_feed)"""
    return P.get("_uni") is not None                        # (the door, the guide, the gate: open)


def width(P):
    """the width of a seat's memory array: the fast memory, or the whole state with the slow memory (sim/slowmem.py), and
    the head's state after it (v0.4, sim/head.py)"""
    w = P["_slow"][3] if "_slow" in P else P["whh"].shape[1]
    return w + (P["_head"][3] if "_head" in P else 0)


def clear(P, h, rows=None):
    """a seat's memory cleared (a death of an older run, a new game, a new opponent: the trainer's `done`), in place.
    rows: a bool mask or indices (None: all). The head's tick clock is kept (sim/head.py np_clear: the head ticks on
    the same frames whatever is cleared, as in training); everything else is zeros. For a network without a head the
    same as h[rows] = 0."""
    if "_head" not in P:
        h[slice(None) if rows is None else rows] = 0.0
        return h
    lay, _, hm, _, base = P["_head"]
    r = slice(None) if rows is None else rows
    h[r, :base] = 0.0
    hm.np_clear(lay, h[:, base:], rows)                   # (a view: cleared in place)
    return h


def head_due(P, h):
    """[B] bool: the head ticks on the coming frame for these seats (the caller then fetches its events: the simulator's
    head_events()). All False for a network without a head."""
    if "_head" not in P:
        return np.zeros(len(h), bool)
    lay, _, hm, _, base = P["_head"]
    return hm.np_due(lay, h[:, base:])


def head_slices(P):
    """(the intention's logits, the way's logits) as slices of the policy's logits: the outputs the head's target and
    way are added to (sim/duel_env.py's INTENT_HEAD 10 and WAY_HEAD 12)"""
    dims = [int(d) for d in P["action_dims"]]
    o = np.concatenate([[0], np.cumsum(dims)])
    return slice(int(o[10]), int(o[11])), (slice(int(o[12]), int(o[13])) if len(dims) > 12 else slice(0, 0))


def describe(P, A):
    """a line for the server's log: what was loaded"""
    hd = ""
    if "_head" in P:                                         # (v0.4)
        hd = ", head of {} ticking every {} frames, plan_in {}".format(P["_head"][0]["size"], P["_head"][0]["every"],
                                                                     "open" if np.abs(P["_head"][1]["plan_in.weight"]).sum() > 0 else "at zero")
    if "attn" not in P:
        return "no attention part" + hd
    lay = json.loads(str(P["attn"]))
    if A is None:
        return "attention part of {} tokens with its door shut (skipped)".format(lay["tokens"]) + hd
    return "attention part of {} tokens, door open (mean size of its weights {:.5f})".format(lay["tokens"], float(np.abs(A[1]["door.weight"]).mean())) + hd


def legs_logits(P, xl, zo=None):
    """(LEGS_IN, B-253) his legs' branch: the movement network's inputs [B, 61; 64 with LEGS_LOOK's] as legs_prep() gives them
    -> its logits [B, 17] (forward 3, sideways 3, jump 2, turn 9), which the simulator samples his legs' choices from
    (env.legs_lg before its _legs_step). None for a network without the branch (the simulator then works them out)."""
    if "legs_w0" not in P:
        return None
    x = np.asarray(xl, np.float32)
    x = x[:, :P["legs_w0"].shape[1]]                         # (a branch without the three inputs of a look point: the old inputs come first)
    lg = (np.tanh(np.tanh(x @ P["legs_w0"].T + P["legs_b0"]) @ P["legs_w1"].T + P["legs_b1"]) @ P["legs_wp"].T + P["legs_bp"]).astype(np.float32)
    if P.get("_res") is not None and zo is not None:         # (--legs-residual) (1 - a(zo)) x the branch's + W zo, zo: his memory of the frame
        R_, LU_ = P["_res"]
        lg = LU_.np_residual(*R_, lg, zo)
    return lg


def legs_feed(P, env, E, rows=None):
    """(LEGS_IN) the branch's logits handed to the simulator for its next _legs_step(): call right before it, after
    anything that changes a target (the intention). Does nothing for a network without the branch or a simulator
    without the switch. rows: (--legs-residual) the seats step() was given on this frame, in its order (their legs'
    logits read his memory of the frame)."""
    if "legs_w0" in P and getattr(env, "legs_prep", None) is not None and getattr(E, "LEGS_IN", False):
        lg = legs_logits(P, env.legs_prep())
        if P.get("_res") is not None and rows is not None and P.get("_zo") is not None:
            R_, LU_ = P["_res"]
            r_ = np.asarray(rows)
            lg[r_] = LU_.np_residual(*R_, lg[r_], P["_zo"])
        env.legs_lg = lg


def step(P, A, obs, h, rng, events=None, xl=None):
    """one frame for B players: obs [B, inputs] as the simulator's observe() gives them, h [B, memory]. Returns the
    choices [B, outputs] (sampled, as in training; one random number per player and output from rng, a numpy Generator)
    and the new memory.
    events [B, 32] (v0.4, a network with a head): what the head is told on its tick (the simulator's head_events(),
    fetched when head_due() says the coming frame ticks); None: zeros. Read on the tick frames only.
    xl [B, the branch's inputs] (--legs-feat, --legs-guide, needs_xl(P)): the simulator's legs_prep() rows of this frame."""
    dadd = gadd = None
    if P.get("_uni") is not None:                            # (--legs-feat, --legs-guide) the branch on this frame's inputs
        lay_u, D_u, G_u, LU_, T_u = P["_uni"]
        assert xl is not None, "this network's legs_door or guide is open: give step() the branch's inputs (xl=env.legs_prep())"
        ok_ = LU_.np_way(xl)
        h2_, lgl_ = LU_.np_branch(tuple(P[k_] for k_ in ("legs_w0", "legs_b0", "legs_w1", "legs_b1", "legs_wp", "legs_bp")), xl)
        dadd = LU_.np_door(D_u[0], D_u[1], h2_, ok_) if D_u is not None else None
        gadd = LU_.np_guide_add(lay_u, G_u, lgl_, ok_, int(np.sum(P["action_dims"]))) if G_u is not None else None
    hh = None
    if "_head" in P:                                         # (v0.4) the head's state at the end of the array
        hh = h[:, P["_head"][4]:]
        h = h[:, :P["_head"][4]]
    hf = h                                                   # (--slow-mem) the whole state; h its fast part
    if "_slow" in P:
        h = hf[:, :P["whh"].shape[1]]
    mean = P["obs_mean"]
    if obs.shape[1] > len(mean):                             # an older network in a simulator with more inputs: they are appended at the end
        obs = obs[:, :len(mean)]
    x = np.clip((obs - mean) / np.sqrt(P["obs_var"] + 1e-8), -10, 10).astype(np.float32)
    xa = x
    if "cell" in P:                                          # the learned map (v8): the last two inputs are cell numbers
        ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(P["cell"]) - 1)
        x = np.concatenate([x[:, :-2], P["cell"][ids[:, 0]], P["cell"][ids[:, 1]]], 1)
    x = np.tanh(x @ P["w0"].T + P["b0"])
    x = np.tanh(x @ P["w1"].T + P["b1"])
    if A is not None:                                        # (v0.2) what the door lets through of the tokens
        x = x + A[2](A[0], A[1], xa, hm=h)                    # (hm: "mem", his memory of the frame before)
    xf = x
    if hh is not None:                                       # (v0.4) the head's plan of its last tick reaches the fast GRU: e + plan_in(plan)
        hlay, hW, hm = P["_head"][:3]
        o_ = hm._np_off(hlay)["plan"]
        xf = x + hm.np_plan_in(hW, hh[:, o_[0]:o_[1]])
    if dadd is not None:                                     # (--legs-feat) only his fast GRU reads the legs' features
        xf = xf + dadd
    gi = xf @ P["wih"].T + P["bih"]
    gh = h @ P["whh"].T + P["bhh"]
    H = h.shape[1]
    r = sig(gi[:, :H] + gh[:, :H])
    z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
    nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    h = ((1 - z) * nn_ + z * h).astype(np.float32)
    hfast = h
    zo = h
    if "_slow" in P:                                         # (--slow-mem) the outputs read h + door(s); the slow GRU ticks on its frames
        zo, h = P["_slow"][2](P["_slow"][1], P["_slow"][0], x, h, hf)
    logits = zo @ P["wp"].T + P["bp"]
    if hh is not None:                                       # (v0.4) the head ticks after the fast memory's step (on its frames) and its
        _, t_add, w_add, hh = hm.np_tick(hW, hlay, x, hfast, hh, events)    # target and way are added to the hands' (held between ticks)
        si, sw = head_slices(P)
        logits[:, si] += t_add
        logits[:, sw] += w_add
        h = np.concatenate([h, hh], 1)
    if gadd is not None:                                     # (--legs-guide) the branch's choice on his movement outputs
        logits = logits + gadd
    if P.get("_uni") is not None and P["_uni"][4] is not None:     # (--legs-gate) g(zo) x the legs' choice, the motor layer
        logits = logits + LU_.np_gate_add(lay_u, *T_u, zo, h2_, lgl_, ok_, int(np.sum(P["action_dims"])))
    P["_zo"] = zo                                            # (--legs-residual: legs_feed's rows read it)
    if float(P.get("switch_fade", 0.0)) > 0:                 # (--switch-fade) off the switch's "legs" choice, as in training
        logits = logits.copy()
        logits[:, int(np.sum(P["action_dims"][:11])) + 1] -= float(P["switch_fade"])
    return draw(P, logits, rng), h


def draw(P, logits, rng):
    """one sampled choice per output (one random number per player and output from rng, drawn in the outputs' order). (v0.4,
    --ordered-heads: "ordered" in the file) the ordered outputs are drawn after the one before them, its table's row of the
    choice drawn there added to their logits (order.t<output>)"""
    dims = [int(d) for d in P["action_dims"]]
    o = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    u = [rng.random((len(logits), 1)) for _ in dims]
    out = np.zeros((len(logits), len(dims)), np.int64)

    def one(j, l):
        p = np.exp(l - l.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        out[:, j] = (p.cumsum(1) > u[j]).argmax(1)

    order = json.loads(str(P["ordered"])) if "ordered" in P else []
    later = {int(c_) for _, c_ in order}
    for j in range(len(dims)):
        if j not in later:
            one(j, logits[:, o[j]:o[j + 1]])
    for p_, c_ in order:
        one(int(c_), logits[:, o[c_]:o[c_ + 1]] + P["order.t{}.weight".format(c_)][out[:, int(p_)]])
    return out

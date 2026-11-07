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

(v0.4.1) A network whose brain token is in the file (sim/export_duel.py: "btoken", "belief", "track", "track_z" and their
weights) carries the brain's and the token's state at the very end of h (sim/btoken.py's packed layout, after the head's),
as sim/test_suite.py's Policy does. While its gate is above zero, step() needs his pose of the frame (pose=, zmap=: the
rows of pose(P, env, mapname), btoken.pose_from_env: his place and view yaw as the game gives them, the zones' map number):
the brain reads the frame's normalised inputs, ticks every eighth of its frames, its readouts' answer is kept in map
coordinates and turned to his facing every frame, and the token joins the attention part at the gate (forward_np's bt, bg).
At gate 0 the brain is not stepped and the network answers exactly as without it. NET_BTOKEN_GATE=<g> in the environment
overrides the file's gate when a plugin loads it.

(v0.4.2a) A network with the rule fade (sim/rule_fade.py; the export's "rule_fade": the columns and the gate g) reads the
rule-made input columns times (1 - g) after the scaling, in the encoder and the attention part only (the brain reads them
unfaded), as test_suite's Policy. With its readers on (BRAIN_READ in training) the brain is stepped while g is above zero
even with the token shut, and the simulator's readers (the legs' look point, the hunt's target) take the brain's answer for
a life drawn on it: brain_life() at each life's start, brain_feed() after each step(). NET_RULE_FADE_G=<g> overrides the
file's g when a plugin loads it.
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
    P["_head2"] = None                                       # (v0.4.3) the strategy head: (layout, weights, head2, its state's width, where
    if "head2" in P:                                         # its state starts, played: its gate open and its links not at zero; the readouts)
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import head2 as head2_                               # sim/head2.py: numpy only at the top
        assert "_head" not in P, "a network with both heads: not built"
        lay2 = json.loads(str(P["head2"]))
        W2 = {k[len("head2."):]: np.asarray(v, np.float32) for k, v in P.items() if k.startswith("head2.")}
        if os.environ.get("NET_HEAD2_GATE", "") != "":
            W2["gate"] = np.array(np.float32(float(os.environ["NET_HEAD2_GATE"])))
        base2 = P["_slow"][3] if "_slow" in P else P["whh"].shape[1]
        cmb_ = bool(lay2.get("cmb")) and "op_v.weight" in W2      # (1.7) the combat order: its held numbers after the head's state
        if os.environ.get("NET_CMB_G", "") != "" and cmb_:
            W2["cmb_g"] = np.array(np.float32(float(os.environ["NET_CMB_G"])))
        P["_ord"] = (base2 + head2_.np_state_width(lay2), head2_.CMB_HELD) if cmb_ else None
        cg_ = float(np.asarray(W2.get("cmb_g", 0.0))) if cmb_ else 0.0
        P["_head2"] = (lay2, W2, head2_, head2_.np_state_width(lay2) + (head2_.CMB_HELD if cmb_ else 0), base2,
                       head2_.np_open(W2) or cg_ > 0, head2_.mlp_of(P, "ahead"), head2_.np_ctrl_params(P, lay2),
                       head2_.np_fight_params(P, lay2))       # (1.7b) the fight odds readout the head's part "fight" reads (None: zeros)
        P["_pass"] = None                                    # (1.7) the brain's pass readout (sim/passodds.py): the candidates' odds
        if "passodds" in P and "passr.l1.weight" in P:
            import passodds as passodds_                     # (numpy at the top: torch inside its torch functions only)
            P["_pass"] = (json.loads(str(P["passodds"])), {k[len("passr."):]: np.asarray(v, np.float32) for k, v in P.items()
                                                           if k.startswith("passr.")}, passodds_.np_forward)
    P["_brain"] = None                                       # (v0.4.1) the brain and its token: (brain weights, token layout, btoken, where
    if "btoken" in P and "belief" in P:                      # its state starts in a seat's array, the gate); played only while the gate is open
        if "/sim" not in sys.path and os.path.isdir("/sim"):
            sys.path.insert(0, "/sim")
        import btoken as btoken_                             # sim/btoken.py: numpy only (zonemap reads /sim/zones)
        bl_ = json.loads(str(P["btoken"]))
        if os.environ.get("NET_BTOKEN_GATE", "") != "":
            bl_["gate"] = float(os.environ["NET_BTOKEN_GATE"])
        assert "attn.btok_emb.weight" in P, "the file names a brain token and has no weights for its first layer"
        assert A is not None or not float(bl_.get("gate", 0.0)) > 0, "the brain's token is open and the attention part is shut or missing"
        B_ = btoken_.numpy_brain(P, json.loads(str(P["belief"])), json.loads(str(P["track"])) if "track" in P else None,
                                 json.loads(str(P["track_z"])) if "track_z" in P else None)
        base_ = (P["_slow"][3] if "_slow" in P else P["whh"].shape[1]) + (P["_head"][3] if "_head" in P else 0) \
            + (P["_head2"][3] if P.get("_head2") is not None else 0)
        P["_brain"] = (B_, bl_, btoken_, base_, float(bl_.get("gate", 0.0)))
    P["_rfade"] = None                                       # (v0.4.2a) the rule fade: (the columns, g, the readers on the brain)
    if "rule_fade" in P:
        rf_ = json.loads(str(P["rule_fade"]))
        if os.environ.get("NET_RULE_FADE_G", "") != "":
            rf_["g"] = float(os.environ["NET_RULE_FADE_G"])
        P["_rfade"] = (np.asarray(rf_["cols"], np.int64), float(rf_.get("g", 0.0)), bool(rf_.get("readers")))
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
    w = w + (P["_head"][3] if "_head" in P else 0) + (P["_head2"][3] if P.get("_head2") is not None else 0)
    if P.get("_brain") is not None:                          # (v0.4.1) the brain's and the token's packed state at the very end
        w = P["_brain"][3] + P["_brain"][2].packed_width(P["_brain"][0]["H"])
    return w


def brain_on(P):
    """(v0.4.1) the brain is stepped: its token's gate is open, or (v0.4.2a) the rule fade is above 0 with its readers on"""
    rf = P.get("_rfade")
    return P.get("_brain") is not None and (P["_brain"][4] > 0 or (rf is not None and rf[2] and rf[1] > 0)
                                            or (P.get("_head2") is not None and P["_head2"][5]))    # (v0.4.3: the strategy head reads it)


def needs_pose(P):
    """(v0.4.1) step() needs his pose (pose=, zmap=; see pose()): the brain is stepped"""
    return brain_on(P)


def brain_answer(P, h):
    """(v0.4.2a) the brain's answer of these seats from their arrays (after step()), as the simulator's readers take it
    (btoken.answer_of); None while the brain is not stepped"""
    if not brain_on(P):
        return None
    B_, bl_, bt_, at_, _ = P["_brain"]
    an = bt_.answer_of(bt_.unpack(B_, bl_, np.asarray(h)[:, at_:])[1])
    if P.get("_fut") is not None and len(P["_fut"]) == len(h):     # (1.7) the brain's places ahead, for the simulator's order
        an["fut"] = P["_fut"].copy()
    return an


def _readers(P, env):
    rf = P.get("_rfade")
    return rf is not None and rf[2] and hasattr(env, "brain_in") and bool(getattr(sys.modules.get(type(env).__module__), "BRAIN_READ", False))


def brain_life(P, env, k):
    """(v0.4.2a) a life of seat k begins (the plugins' fresh_life): drawn on the brain's answer with chance g, as the
    simulator's _fresh does in training. Nothing for a network without the readers"""
    if _readers(P, env):
        env._brain_init()
        env.brain_g[k] = P["_rfade"][1]
        env.brain_draw(k)


def brain_feed(P, env, h, seats):
    """(v0.4.2a) after step() for these seats: their brain's answer into the simulator (env.brain_in's arrays, these rows)"""
    if not _readers(P, env):
        return
    an = brain_answer(P, h)
    if an is None:
        return
    env._brain_init()
    r = np.asarray(seats)
    env.brain_bel[r], env.brain_ok[r], env.brain_band[r], env.brain_ztop[r] = an["bel"], an["ok"], an["band"], an["ztop"]
    if "fut" in an:                                          # (1.7, COMBAT) the brain's places ahead: the order's cut off and spam
        if getattr(env, "brain_fut", None) is None or len(env.brain_fut) != env.n:
            env.brain_fut = np.zeros((env.n, 3, 3), np.float32)
        env.brain_fut[r] = an["fut"]


def pose(P, env, mapname=None):
    """(v0.4.1) his place and view yaw [n, 4] and the zones' map number [n] for every seat of a plugin's simulator, as the
    trainer reads them from info["aux"] (btoken.pose_from_env: env.state's place, env.yaw put in -180 .. 180; the map's
    number from its name when the simulator keeps none). Call after the frame's players are filled in, before step()"""
    return P["_brain"][2].pose_from_env(env, mapname)


def clear(P, h, rows=None):
    """a seat's memory cleared (a death of an older run, a new game, a new opponent: the trainer's `done`), in place.
    rows: a bool mask or indices (None: all). The head's tick clock is kept (sim/head.py np_clear: the head ticks on
    the same frames whatever is cleared, as in training); everything else is zeros. For a network without a head the
    same as h[rows] = 0."""
    r = slice(None) if rows is None else rows
    end = None
    if P.get("_brain") is not None:                          # (v0.4.1) the brain and its answer, by the same flag (the trainer's reset:
        B_, _, bt_, end, _ = P["_brain"]                     # btoken.packed_clear keeps its tick clock and the time since he noticed
        bt_.packed_clear(h[:, end:], rows, B_["H"])          # the enemy, as test_suite's Policy.clear)
    if "_head" not in P:
        h[r, :end] = 0.0
        return h
    lay, _, hm, hw, base = P["_head"]
    h[r, :base] = 0.0
    hm.np_clear(lay, h[:, base:base + hw], rows)          # (a view: cleared in place)
    return h


def head_due(P, h):
    """[B] bool: the head ticks on the coming frame for these seats (the caller then fetches its events: the simulator's
    head_events()). All False for a network without a head."""
    if "_head" not in P:
        return np.zeros(len(h), bool)
    lay, _, hm, hw, base = P["_head"]
    return hm.np_due(lay, h[:, base:base + hw])


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
    if P.get("_rfade") is not None:                          # (v0.4.2a)
        hd += ", rule fade of {} columns at g {:.4f} (readers {})".format(len(P["_rfade"][0]), P["_rfade"][1], "on the brain" if P["_rfade"][2] else "on the rule")
    if P.get("_brain") is not None:                          # (v0.4.1)
        B_, bl_, _, _, g_ = P["_brain"]
        hd += ", brain of {} ticking every {} frames (readouts {}), its token of {} numbers at gate {:.4f}{}".format(
            B_["H"], B_["K"], "+".join(k_ for k_ in ("trk", "trz") if k_ in B_) or "none", bl_["dim"], g_,
            " (shut: the brain is not stepped)" if not g_ > 0 else "")
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


def keep_g(P):
    """(1.4c) the keep choice's share of his readings in this file (0: none, the lock rule; sim/head2.py)"""
    if P.get("_head2") is None or not P["_head2"][0].get("keep") or "keep.weight" not in P["_head2"][1]:
        return 0.0
    return float(np.asarray(P["_head2"][1].get("keep_g", 0.0)))


def cmb_g(P):
    """(1.7) the combat order's share of his readings in this file (0: none; sim/head2.py)"""
    if P.get("_ord") is None:
        return 0.0
    return float(np.asarray(P["_head2"][1].get("cmb_g", 0.0)))


def column_on(P):
    """(1.4c, 1.7) step() gives the keep column (kf= needed): the keep choice or the combat order at a share above 0"""
    return keep_g(P) > 0 or cmb_g(P) > 0


def order_on(P):
    """(1.7) the order plays: asked at a share, or its adds on the targets' and the way's above 0"""
    return P.get("_ord") is not None and (cmb_g(P) > 0 or float(np.asarray(P["_head2"][1].get("padd", 0.0))) > 0)


def order_due(P):
    """(1.7) the coming frame is a keep reading for some seat: give step() ox= (the simulator's order_feat() after this frame, these rows)"""
    kr_ = P.get("_k_r")
    return order_on(P) and kr_ is not None and bool(np.asarray(kr_).any())


def step(P, A, obs, h, rng, events=None, xl=None, pose=None, zmap=None, kf=None, ox=None):
    """one frame for B players: obs [B, inputs] as the simulator's observe() gives them, h [B, memory]. Returns the
    choices [B, outputs] (sampled, as in training; one random number per player and output from rng, a numpy Generator)
    kf [B, KEEP_FEAT] (1.4c, 1.7a; keep_g(P) above 0): the simulator's keep_feat() rows after the frame before; the keep column
    of this frame (d + 2 c + 4 r: the draw, the hand-over's coin, a keep reading on the frame after the head's tick; test_suite.Policy's
    sums, its own stream P["_krng"]) is left in P["_keep"] [B] for the simulator's keep_in (None: no keep choice)
    and the new memory.
    events [B, 32] (v0.4, a network with a head): what the head is told on its tick (the simulator's head_events(),
    fetched when head_due() says the coming frame ticks); None: zeros. Read on the tick frames only.
    xl [B, the branch's inputs] (--legs-feat, --legs-guide, needs_xl(P)): the simulator's legs_prep() rows of this frame.
    pose [B, 4], zmap [B] (v0.4.1, needs_pose(P)): these rows of pose(P, env, mapname) of this frame.
    ox (1.7, order_due(P) after the frame before): (X, C) of the simulator's order_feat() for these rows; the seats with a keep reading
    make their order from it before this frame's outputs (test_suite.Policy's sums)."""
    dadd = gadd = None
    if P.get("_uni") is not None:                            # (--legs-feat, --legs-guide) the branch on this frame's inputs
        lay_u, D_u, G_u, LU_, T_u = P["_uni"]
        assert xl is not None, "this network's legs_door or guide is open: give step() the branch's inputs (xl=env.legs_prep())"
        ok_ = LU_.np_way(xl)
        h2_, lgl_ = LU_.np_branch(tuple(P[k_] for k_ in ("legs_w0", "legs_b0", "legs_w1", "legs_b1", "legs_wp", "legs_bp")), xl)
        dadd = LU_.np_door(D_u[0], D_u[1], h2_, ok_) if D_u is not None else None
        gadd = LU_.np_guide_add(lay_u, G_u, lgl_, ok_, int(np.sum(P["action_dims"]))) if G_u is not None else None
    hb = bst = bt = None
    if P.get("_brain") is not None:                          # (v0.4.1) the brain's packed state, at the very end of the array
        hb = h[:, P["_brain"][3]:]
        h = h[:, :P["_brain"][3]]
    h2s = ohs = None
    if P.get("_head2") is not None:                          # (v0.4.3) the strategy head's state, before the brain's
        h2s = h[:, P["_head2"][4]:]
        h = h[:, :P["_head2"][4]]
        if P.get("_ord") is not None:                        # (1.7) the order's held numbers after it
            w2_ = P["_head2"][2].np_state_width(P["_head2"][0])
            ohs, h2s = h2s[:, w2_:], h2s[:, :w2_]
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
    xa = x                                                   # (the brain reads these: unfaded)
    if needs_pose(P):                                        # (v0.4.1) the brain's last answer turned to his pose now (test_suite's token_pre)
        B_, bl_, bt_m, _, _ = P["_brain"]
        assert pose is not None and zmap is not None, "this network's brain token is open: give step() pose= and zmap= (netpass.pose)"
        br_, tk_ = bt_m.unpack(B_, bl_, hb)
        tk_.see(obs)
        bt = tk_.features(np.asarray(pose, np.float32), np.asarray(zmap)).astype(np.float32)
        bst = (br_, tk_)
    rf = P.get("_rfade")
    if rf is not None and rf[1] > 0 and len(rf[0]):          # (v0.4.2a) the hands' inputs: the rule-made columns times (1 - g)
        y_ = np.array(x, copy=True)                          # (sim/rule_fade.py apply_np: the same sums)
        y_[:, rf[0]] = y_[:, rf[0]] * np.float32(1.0 - float(rf[1]))
        x = y_
    xh = x                                                   # (the hands' attention reads these)
    ord_ = None
    kr0_ = P.get("_k_r")
    if ohs is not None and order_on(P) and ox is not None and kr0_ is not None and len(kr0_) == len(ohs) and np.asarray(kr0_).any():
        hm2o_ = P["_head2"][2]                               # (1.7) a keep reading: the order made from the candidates the simulator made
        r_ = np.nonzero(np.asarray(kr0_, bool))[0]           # after the head's tick, the brain's odds written in (test_suite's sums)
        X_ = np.array(np.asarray(ox[0])[r_], np.float32)
        C_ = np.asarray(ox[1], np.float32)[r_]
        if P.get("_pass") is not None and bst is not None:
            X_[..., hm2o_.CMB_PASS0:hm2o_.CMB_PASS0 + 3] = P["_pass"][2](P["_pass"][1], P["_pass"][0], bst[0].s[r_], X_)
        kl_, ps_, ta_, ya_, okc_ = hm2o_.np_order_scores(P["_head2"][1], P["_head2"][0], h2s[r_], X_, C_)   # (1.7b: okc_: ok_ is the legs' way flags)
        okf_ = okc_.astype(np.float32)[:, None]
        ohs = np.array(ohs, np.float32, copy=True)
        ohs[r_] = np.concatenate([kl_, ps_, ta_ * okf_, ya_ * okf_], 1)
        ord_ = (r_, kl_, ps_, okc_)
    if "cell" in P:                                          # the learned map (v8): the last two inputs are cell numbers
        ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(P["cell"]) - 1)
        x = np.concatenate([x[:, :-2], P["cell"][ids[:, 0]], P["cell"][ids[:, 1]]], 1)
    x = np.tanh(x @ P["w0"].T + P["b0"])
    x = np.tanh(x @ P["w1"].T + P["b1"])
    if A is not None:                                        # (v0.2) what the door lets through of the tokens
        if bt is None or not P["_brain"][4] > 0:             # (v0.4.2a: the brain stepped for the readers alone: its token stays out)
            x = x + A[2](A[0], A[1], xh, hm=h)                # (hm: "mem", his memory of the frame before)
        else:                                                # (v0.4.1) with the brain's token at its gate
            x = x + A[2](A[0], A[1], xh, hm=h, bt=bt, bg=P["_brain"][4])
    xf = x
    if hh is not None:                                       # (v0.4) the head's plan of its last tick reaches the fast GRU: e + plan_in(plan)
        hlay, hW, hm = P["_head"][:3]
        o_ = hm._np_off(hlay)["plan"]
        xf = x + hm.np_plan_in(hW, hh[:, o_[0]:o_[1]])
    if dadd is not None:                                     # (--legs-feat) only his fast GRU reads the legs' features
        xf = xf + dadd
    b2 = None
    if h2s is not None and P["_head2"][5]:                   # (v0.4.3) the strategy head's plan into his fast GRU, its bias on his intention
        g2_, b2 = P["_head2"][2].np_adds(P["_head2"][1], P["_head2"][0], h2s)
        xf = xf + g2_
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
    if b2 is not None:
        si2_ = head_slices(P)[0]                             # (b1.4a: the mix, his target choice moved toward the head's own; none at mix 0)
        logits[:, si2_] = P["_head2"][2].np_mix_in(P["_head2"][1], P["_head2"][0], h2s, logits[:, si2_]) + b2
        wa2_ = P["_head2"][2].np_wadd(P["_head2"][1], P["_head2"][0], h2s)    # (1.5a) its weapon scores on the weapon key's
        o_ = np.concatenate([[0], np.cumsum([int(d) for d in P["action_dims"]])])
        if wa2_ is not None:
            logits[:, int(o_[6]):int(o_[7])] += wa2_
        fa2_ = P["_head2"][2].np_fadd(P["_head2"][1], P["_head2"][0], h2s)    # (1.7) its fire scores on the fire key's
        if fa2_ is not None:
            logits[:, int(o_[5]):int(o_[6])] += fa2_
        pa_ = float(np.asarray(P["_head2"][1].get("padd", 0.0))) if ohs is not None else 0.0
        if pa_ > 0:                                          # (1.7) the pointer's scores held from the last reading on the targets' and the way's
            hm2a_ = P["_head2"][2]
            o0_ = hm2a_.CMB_NK + hm2a_.CMB_NEW
            logits[:, int(o_[10]):int(o_[10]) + hm2a_.CMB_T] += np.float32(pa_) * ohs[:, o0_:o0_ + hm2a_.CMB_T]
            if len(o_) > 13:
                logits[:, int(o_[12]):int(o_[12]) + hm2a_.CMB_W] += np.float32(pa_) * ohs[:, o0_ + hm2a_.CMB_T:]
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
    P["_keep"] = None
    P["_logits"] = logits                                    # (a parity check with test_suite.Policy's last_logits)
    kg_ = keep_g(P)
    if column_on(P) and kf is not None and h2s is not None:  # (1.4c) the keep choice: the head's state this frame's outputs read (before its
        hm2_ = P["_head2"][2]                                # tick), the hands' memory after the frame, its own numbers (test_suite.Policy)
        si_ = head_slices(P)[0]
        li_ = logits[:, si_] - logits[:, si_].max(1, keepdims=True)
        lsm_ = li_ - np.log(np.exp(li_).sum(1, keepdims=True))
        cur_ = np.clip(np.asarray(kf)[:, 2].astype(np.int64), 0, lsm_.shape[1] - 1)
        kx_ = hm2_.np_keep_x(kf, lsm_[np.arange(len(cur_)), cur_])
        kz_ = hm2_.np_keep_logit(P["_head2"][1], P["_head2"][0], h2s, hfast, kx_)
        if P.get("_krng") is None:
            P["_krng"] = np.random.default_rng(1414)
        kd_ = (P["_krng"].random(len(kz_)) < sig(kz_)).astype(np.int64)
        kc_ = (P["_krng"].random(len(kz_)) < kg_).astype(np.int64)
        kr_ = P.get("_k_r")
        kr_ = np.zeros(len(kz_), np.int64) if kr_ is None or len(kr_) != len(kz_) else np.asarray(kr_, np.int64)
        P["_keep"] = kd_ + 2 * kc_ + 4 * kr_                 # (1.7a) the seats whose head ticked on the frame before: a keep reading
        if ord_ is not None and cmb_g(P) > 0:                # (1.7) the order's kind and candidate drawn at the reading, asked with its
            r_, kl_, ps_, okc_ = ord_                        # share where the head has a state: + 8 k + 32 c + 256

            def pick_(z_):
                p_ = np.exp(z_ - z_.max(1, keepdims=True))
                p_ /= p_.sum(1, keepdims=True)
                return np.minimum((p_.cumsum(1) < P["_krng"].random((len(z_), 1))).sum(1), z_.shape[1] - 1).astype(np.int64)
            hm2d_ = P["_head2"][2]
            ko_ = pick_(kl_)
            co_ = np.zeros_like(ko_)
            for k_ in range(1, hm2d_.CMB_NK):
                c0_, m_ = hm2d_.CMB_C0[k_], hm2d_.CMB_SLOTS[k_]
                co_ = np.where(ko_ == k_, pick_(ps_[:, c0_:c0_ + m_]), co_)
            oq_ = ((P["_krng"].random(len(r_)) < cmb_g(P)) & okc_).astype(np.int64)
            P["_keep"][r_] = P["_keep"][r_] + (8 * ko_ + 32 * co_ + 256) * oq_
    if bst is not None:                                      # (v0.4.1) the brain reads the frame's normalised inputs; at its tick the readouts'
        br_, tk_ = bst                                       # answer is kept in map coordinates (his pose of this frame): test_suite's token_post
        tkd_ = br_.frame(xa)
        P["_k_r"] = np.asarray(tkd_, bool) & bool(h2s is not None and P["_head2"][5])   # (1.7a) whose head ticks now: their next frame a keep reading
        if tkd_.any():
            o1_, o2_ = br_.readouts(tkd_)
            tk_.answer(tkd_, o1_, o2_, np.asarray(pose, np.float32)[tkd_], np.asarray(zmap)[tkd_])
            if P.get("_ord") is not None and P["_head2"][6] is not None:     # (1.7) the readout ahead's places, kept in map coordinates
                hm2f_, ah2f_ = P["_head2"][2], P["_head2"][6]                    # at the tick, for the simulator's order (test_suite's token_post)
                if P.get("_fut") is None or len(P["_fut"]) != len(tkd_):
                    P["_fut"] = np.zeros((len(tkd_), 3, 3), np.float32)
                f_ = np.asarray(hm2f_.np_mlp(ah2f_, br_.s[tkd_]), np.float64)[:, :15].reshape(-1, 3, 5)
                pz_ = np.asarray(pose, np.float64)[tkd_]
                x_, y_ = bt_m._turn(np.repeat(pz_[:, 3:4], 3, 1), f_[..., 0] * 1000.0, f_[..., 1] * 1000.0)
                P["_fut"][tkd_] = np.stack([pz_[:, None, 0] + x_, pz_[:, None, 1] + y_, pz_[:, None, 2] + f_[..., 2] * 1000.0], -1)
            if h2s is not None and P["_head2"][5]:           # (v0.4.3) the strategy head ticks with the brain, after the frame
                lay2, W2, hm2, _, _, _, ah2, ct2, fo2 = P["_head2"]
                sb_ = br_.s[tkd_]
                u_ = hm2.np_feats(lay2, brain=sb_, trk=o1_, trz=o2_, ahead=hm2.np_mlp(ah2, sb_) if ah2 is not None else None,
                                  ctrl=hm2.np_ctrl(ct2, sb_, hfast[tkd_]), fight=hm2.np_fight(fo2, sb_, hfast[tkd_]),
                                  obs=xa[tkd_], hands=hfast[tkd_])
                h2s = h2s.copy()
                h2s[tkd_] = hm2.np_tick(W2, lay2, u_, h2s[tkd_])
        hb = P["_brain"][2].pack(br_, tk_)
    if h2s is not None:
        h = np.concatenate([h, np.asarray(h2s, np.float32)], 1)
    if ohs is not None:                                      # (1.7) the order's held numbers back after the head's state
        h = np.concatenate([h, np.asarray(ohs, np.float32)], 1)
    if float(P.get("switch_fade", 0.0)) > 0:                 # (--switch-fade) off the switch's "legs" choice, as in training
        logits = logits.copy()
        logits[:, int(np.sum(P["action_dims"][:11])) + 1] -= float(P["switch_fade"])
    wd_ = float(P.get("_wdial") or 0.0)
    if wd_ > 0:                                              # (owner, 2026-11-07, duelbot's !weapons) the weapon dial: a push on the presses
        o_ = np.concatenate([[0], np.cumsum([int(d) for d in P["action_dims"]])])    # of rockets, rail and the lightning gun
        logits = logits.copy()                               # toward the owner's table (sim/weapon_dial.py; P["_logits"] stays the network's)
        P["_wdial_add"] = _weapon_dial().push(obs, wd_)
        logits[:, int(o_[6]) + 1:int(o_[6]) + 4] += P["_wdial_add"]
    out = draw(P, logits, rng)
    if P.get("_no_switch") is None:                          # (v0.3.5, NO_SWITCH) the switch retired: drawn as before, then off
        P["_no_switch"] = str(json.loads(str(P["env_vars"])).get("NO_SWITCH", "0")) not in ("0", "", "0.0") if "env_vars" in P else False
    if P["_no_switch"] and out.shape[1] > 11:
        out[:, 11] = 0
    if P.get("_wdial_mode") == "replace":                    # (!weapons pros) the dial's replace form: the owner's table chooses his weapon
        if P.get("_wdial_rng") is None:                      # the dial's own stream: every other output drawn exactly as with it off
            P["_wdial_rng"] = np.random.default_rng(101)
        a_ = _weapon_dial().choose(obs, P.setdefault("_wdial_state", {}), P["_wdial_rng"])    # (sim/weapon_dial.py; test_suite.Policy the same)
        P["_wdial_act"] = a_
        out[:, 6] = np.where(a_ >= 0, a_, out[:, 6])        # in place of the network's weapon key where he owns one of the three
        t_ = _weapon_dial().target(obs, P["_wdial_state"], P["_wdial_rng"])    # the weapon he lacks (the rail, rocket ammunition) as his
        P["_wdial_tgt"] = t_                                 # target where the rule speaks; the simulator's readings and hold as ever
        out[:, 10] = np.where(t_ >= 0, t_, out[:, 10])
    if hb is not None:                                       # (v0.4.1) the brain's state back at the very end of the array
        h = np.concatenate([h, np.asarray(hb, np.float32)], 1)
    return out, h


def _weapon_dial():
    """sim/weapon_dial.py (on a server /sim is on the path: plugins/duelbot.py; in the repo the folder beside plugins/)"""
    try:
        import weapon_dial
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim"))
        import weapon_dial
    return weapon_dial


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

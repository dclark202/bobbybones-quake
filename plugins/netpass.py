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
        base_ = (P["_slow"][3] if "_slow" in P else P["whh"].shape[1]) + (P["_head"][3] if "_head" in P else 0)
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
    w = w + (P["_head"][3] if "_head" in P else 0)
    if P.get("_brain") is not None:                          # (v0.4.1) the brain's and the token's packed state at the very end
        w = P["_brain"][3] + P["_brain"][2].packed_width(P["_brain"][0]["H"])
    return w


def brain_on(P):
    """(v0.4.1) the brain is stepped: its token's gate is open, or (v0.4.2a) the rule fade is above 0 with its readers on"""
    rf = P.get("_rfade")
    return P.get("_brain") is not None and (P["_brain"][4] > 0 or (rf is not None and rf[2] and rf[1] > 0))


def needs_pose(P):
    """(v0.4.1) step() needs his pose (pose=, zmap=; see pose()): the brain is stepped"""
    return brain_on(P)


def brain_answer(P, h):
    """(v0.4.2a) the brain's answer of these seats from their arrays (after step()), as the simulator's readers take it
    (btoken.answer_of); None while the brain is not stepped"""
    if not brain_on(P):
        return None
    B_, bl_, bt_, at_, _ = P["_brain"]
    return bt_.answer_of(bt_.unpack(B_, bl_, np.asarray(h)[:, at_:])[1])


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


def step(P, A, obs, h, rng, events=None, xl=None, pose=None, zmap=None):
    """one frame for B players: obs [B, inputs] as the simulator's observe() gives them, h [B, memory]. Returns the
    choices [B, outputs] (sampled, as in training; one random number per player and output from rng, a numpy Generator)
    and the new memory.
    events [B, 32] (v0.4, a network with a head): what the head is told on its tick (the simulator's head_events(),
    fetched when head_due() says the coming frame ticks); None: zeros. Read on the tick frames only.
    xl [B, the branch's inputs] (--legs-feat, --legs-guide, needs_xl(P)): the simulator's legs_prep() rows of this frame.
    pose [B, 4], zmap [B] (v0.4.1, needs_pose(P)): these rows of pose(P, env, mapname) of this frame."""
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
    if bst is not None:                                      # (v0.4.1) the brain reads the frame's normalised inputs; at its tick the readouts'
        br_, tk_ = bst                                       # answer is kept in map coordinates (his pose of this frame): test_suite's token_post
        tkd_ = br_.frame(xa)
        if tkd_.any():
            o1_, o2_ = br_.readouts(tkd_)
            tk_.answer(tkd_, o1_, o2_, np.asarray(pose, np.float32)[tkd_], np.asarray(zmap)[tkd_])
        hb = P["_brain"][2].pack(br_, tk_)
    if float(P.get("switch_fade", 0.0)) > 0:                 # (--switch-fade) off the switch's "legs" choice, as in training
        logits = logits.copy()
        logits[:, int(np.sum(P["action_dims"][:11])) + 1] -= float(P["switch_fade"])
    out = draw(P, logits, rng)
    if P.get("_no_switch") is None:                          # (v0.3.5, NO_SWITCH) the switch retired: drawn as before, then off
        P["_no_switch"] = str(json.loads(str(P["env_vars"])).get("NO_SWITCH", "0")) not in ("0", "", "0.0") if "env_vars" in P else False
    if P["_no_switch"] and out.shape[1] > 11:
        out[:, 11] = 0
    if hb is not None:                                       # (v0.4.1) the brain's state back at the very end of the array
        h = np.concatenate([h, np.asarray(hb, np.float32)], 1)
    return out, h


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

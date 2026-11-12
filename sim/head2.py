"""v0.4.3: the strategy head (docs/v0.4.3/RUN_v0.4.3.md, "The strategy head"; the trainer's --head2). A small slow GRU
beside his hands that ticks with the brain (every 8 frames, 0.2 s), reads what the brain knows and what he has, and acts by
a plan into the hands' memory and a bias on the intention head's choice. Not sim/head.py (v0.4's earlier candidate, ~7 M
weights, a store read by attention, its inputs under the gradient); this one is ~0.65 M and reads only numbers.

What it reads (one vector u at each tick, all numbers: no gradient reaches anything it reads)
  brain  the brain's memory after its tick (sim/belief.py: 256)
  trk    the brain's readout of the enemy now (sim/track.py: 27; raw outputs, clipped to +-10)
  trz    the readout's second part (sim/track_z.py: 28: the zones, speed, direction)
  ahead  the readout of what comes next (sim/ahead.py: where he will be in 1/2/4 s, what he goes for, when he appears, the
         item race)
  ctrl   the slot for the "in control" readouts (B-280; sim/control.py, layout version 2: a ModuleDict `control` of readouts
         "belief" on the brain's state and "both" on the brain's state and the hands' memory). The layout's "ctrl_src" picks
         one ("belief" or "both"; the trainer's --head2-ctrl-src) or none ("none", the default: zeros, as before). What it
         reads: the readout's four chances minus 0.5 (sigmoid(logits) - 0.5: 0 for a readout whose last layer is at zero),
         its input rounded to half precision as the readouts learn it; worked out under no_grad: a number to the head, no
         gradient from the head reaches the readouts, the brain or the hands through it (the head's learning step re-reads
         the stored u in any case)
  obs    his own normalised inputs that say his stack, his item timers, score and clock (the columns of docs/INPUTS.csv named
         by OBS_SEL, kept in the layout as indices: health, armor, weapons owned and ammunition, the mega and red armor's
         place and sight, the clock and score, the round's time left, the seconds since he took each item, his intention)
  hands  the hands' fast memory after the tick's frame (512)
  Each part can be left out by the layout's "on" (zeros in its place); the vector is rounded to half precision before use,
  in the trainer (which stores it so) and in numpy alike.

What it is
  p = tanh(inp(u)); s = GRUCell(p, s) (size 256; the update gate started slow: "chrono" ticks, as sim/slowmem.py)
  plan = tanh(plan_out(s))  [64]                 bias = gate * target(s)  [the intention's choices]
  held from the frame after the tick to the next tick; zeros after a reset (death, a game's end: the hands' own flag) until
  the next tick. The hands' fast GRU reads x + gate * plan_in(plan) (x: the encoder and attention part's output); the bias is
  added to the intention head's logits. plan_in and target start at exactly zero: a network given the head answers
  exactly as it did. The gate (a buffer in the state dict, "head2.gate"; live in the trainer) scales both outputs: 0 is the
  network without the head whatever its weights.
  v = value(cat[s, hands' memory of the frame]) -> 1: the head's own two-minute value of all his pay (gamma 0.9998).
  The mix (b1.4a; a buffer, "head2.mix", 0 by default and for a save without it; live in the trainer): his target choice
  moves from the hands' to the head's own. With k = mix x valid (0 from a reset to the head's next tick: the hands' then),
  the intention's logits are (1 - k) x the hands' + k x target(s), the gate's bias added after. mix 0 is the network
  without it whatever its weights; mix 1 is the head's choice alone (when it has a state).
  The add (1.3b; a buffer, "head2.add", 0 by default and for a save without it): the head's own scores added to the hands'
  where it has a state: (1 - k) x the hands' + (k + add) x target(s) + the gate's bias. With target at zero (a new head) a
  network given add 1 answers exactly as it did; one set of logits, learnt by one lesson (the trainer's --head2-add).
  "chrono_lo" (1.3b, a new head): the update gate's time scales drawn evenly in log from chrono_lo to chrono ticks (absent:
  evenly from 1 to chrono, as before), so part of its memory can follow a fight.

How it learns (the trainer; the routing of its gradient)
  (1) its value: v against the returns of his whole pay at gamma = layout "gamma" (0.9998, about two minutes), on every
      learner frame; the gradient reaches v, the GRU and inp (the hands' memory it reads is a number).
  (2) its bias: a clipped policy-gradient term of its own on the intention head, on the frames the intention was read,
      with the head's own advantage (GAE at gamma 0.9998 from v) and the hands' logits held fixed; in the hands' loss the
      bias is a number (the hands' advantage never moves the head through it, the head's never moves the hands).
  (3) its plan: plan_in is a layer of the hands and learns from their loss; the gradient that would go on into the head
      through the plan is cut (times --head2-plan-grad, 0 by default): the plan is the head's state as the head's own
      lessons shape it, and the hands learn to read it.
  The head's sequence is re-run in the learning step from the stored u of the rollout's ticks and the state at its start
  (truncated there: 48 ticks, 9.6 s, of backpropagation through time; its state itself is carried across rollouts).

The keep choice (1.4c; 1.7a: the layout's "keep" 2, KEEP_F 7; 1.4c's "keep" 1 with three numbers is retired, never run): at
each keep reading of his target (five a second: the frame after the head's tick), keep it or re-decide (the simulator's keep
column, sim/duel_env.py). z = keep(cat[s, hands' memory (a number), f]) -> 1, the logit of re-deciding; f = keep_x(): his
target's age out of contact and arrival (s / 10, at most 2), contact (0 or 1), the held target's log-probability under the
present scores (clipped to -10, / 5; a number), arrived out of contact (0 or 1), the seconds since the arrival out of contact
(/ 10, at most 2), a sound heard and a hit taken with the enemy out of view (each exp(-seconds / KEEP_RECENT): 1 just now).
Its start (tools/keep_init.py): the lock made soft, the weights on s, the hands' memory and the last three numbers zero.
keep_g (a buffer, 0 for a save without it): the share of his seconds it decides (the coin at each lock-rule reading; the rest:
the lock rule). Learnt in the head's own term with the target (the trainer).

The weapon part (1.5a; the layout's "weapon", absent before; tools/weapon_init.py): the head informs his weapon choice. wsc(s)
-> one score per choice of the weapon key (no press and the nine weapons), held from tick to tick as the target's scores; wadd
(a buffer, 0 for a save without it) times it is added to the hands' weapon-key logits where the head has a state (the trainer,
the checks): one set of weapon-key scores, as the target's since 1.3b. Its own inputs: the part "wobs" at the end of u (the
columns of W_OBS: the weapon in his hand and whether he can fire, the enemy's weapon in view and since his last death, the hums
heard, the enemy in view and his last known place), read by a layer of their own, winp, added to inp's: tanh(inp(u before
wobs) + winp(wobs)). winp and wsc start at exactly zero: a network given the part answers exactly as it did.

The combat order (1.7, docs/runs/1.7/README.md and BUILD.md; the layout's "cmb", absent before; tools/order_init.py): a kind, then
a candidate by a pointer, then the way. At each keep reading (the frame after its tick) the head reads every candidate's numbers
(the simulator's order_feat: CMB_ROWS rows of CMB_F) and the situation's (ctx). The kind (CMB_KINDS: the target as chosen by the
hands and the head, cut off, spam, break off): ok_s(s) + ok_c(ctx), a kind with no valid candidate shut. The candidate: one scorer
for every candidate (AlphaStar's pointer), g(s, x) = op_v(tanh(op_s(s) + op_x(x))), softmax over the kind's valid candidates. The
same scorer on the 17 targets' rows and the three ways' rows: padd x those scores added to the head's target scores and to the
way's (S5: the hands' rows stay; the head's part). All held to the next keep reading. cmb_g (a buffer): the share of his readings
the order is asked at; padd (a buffer): the adds' share. Learnt in the head's own term with the target and the keep choice. At the
start ok_s, op_s and op_v are zero (the pointer's scores 0, the kind by its context's layer alone); tools/order_init.py fits ok_c,
op_x and op_v to the pros (BUILD.md part 9).
The fire push (1.7; the layout's "fire"): fsc(s) -> 2 scores held so, fadd (a buffer) x them added to the fire key's logits where the
head has a state; learnt by the hands' term on the head's state as a number (s detached). Both start at exactly zero effect.

Numpy only at the top level (the game server imports this file); torch inside the torch functions.
"""
import csv
import math
import os

import numpy as np

VERSION = 1
PARTS = ("brain", "trk", "trz", "ahead", "ctrl", "fight", "obs", "hands", "ins", "wobs")   # (1.5a) wobs: the weapon part's inputs (a layout without: 0 wide);
#                                                          (1.7b) fight: the brain's fight odds, two chances - 0.5 (sim/fightodds.py; without: 0 wide)
KEEP_F = 7                                                   # (1.7a) the keep choice's own numbers: age, contact, log p held, arrived, since arrival, sound, hit unseen
KEEP_FEAT = 7                                                # (1.7a) the simulator's keep_feat() columns (duel_env.KEEP_FEAT)
KEEP_AGE_MAX, KEEP_LP_MIN, KEEP_RECENT = 20.0, -10.0, 2.0
CMB_KINDS = ("target", "cut", "spam", "out")              # (1.7) the combat order's kinds (sim/duel_env.py COMBAT: the same numbers)
CMB_NK = len(CMB_KINDS)
CMB_SLOTS = (0, 3, 8, 8)                                   # ... each kind's candidates, and the first of each among the new ones
CMB_C0 = (0, 0, 3, 11)
CMB_NEW, CMB_T, CMB_W = 19, 17, 3                          # ... the new kinds' rows, the targets', the ways'
CMB_ROWS = CMB_T + CMB_NEW + CMB_W
CMB_F, CMB_NCTX, CMB_HID = 34, 14, 64                      # ... a row's numbers, the situation's, the pointer's width
CMB_VALID = 8                                              # ... a row's "valid" column
CMB_PASS0 = 31                                             # ... the brain's odds of his passing it within 1, 2, 4 s (three columns)
CMB_HELD = CMB_NK + CMB_NEW + CMB_T + CMB_W                # (numpy, the checks) the order's held numbers a seat: kinds, new, targets', ways' adds
CTRL_SRCS = ("none", "belief", "both")                     # (the ctrl slot's source: sim/control.py's readouts by name)
CLIP = 10.0
# (group, input) of docs/INPUTS.csv; an input of None: every row of the group
OBS_SEL = (("self", "health"), ("self", "armor"), ("weapons", "owns "), ("weapons", "ammo: "),
           ("items", "nearest mega health: "), ("items", "nearest red armor: "),
           ("clock and score", None), ("v02 game", None), ("v02 items", None), ("intention", None),
           ("b17 order", None))                             # (1.7) the order he follows and its point (a layout before: tools/order_init.py adds them)
# (1.8, owner 2026-11-11, docs/design/INPUTS_CLEANUP.md: the head at its birth) the head's own columns on a cleaned list: its job is the
# strategy, so it is given the game's state by name: as OBS_SEL without the order's ten (cut), with the weapon in his hand, the enemy
# noticed in view, and the timers of the mega, the red armor and both yellow armors
OBS_SEL_18 = tuple(x for x in OBS_SEL if x[0] != "b17 order") + (("weapons", "holding "), ("enemy", "noticed in view"),
                                                                ("memory", "mega health: "), ("memory", "red armor: "), ("b17b timers", None),
                                                                ("memory", "enemy has the mega health"), ("memory", "enemy has the red armor"))
# (1.5a) the weapon part's own inputs ("wobs"): what he holds and whether he can fire it, the enemy's weapon (in view, since his last
# death, the hums heard), the enemy in view and his last known place (exact while in view)
W_OBS = (("weapons", "holding "), ("self", "weapon not ready"), ("enemy", "enemy holds "), ("memory", "enemy seen with "),
         ("hearing", "railgun hum"), ("hearing", "lightning gun hum"), ("enemy", "noticed in view"), ("enemy", "seen or heard recently"),
         ("enemy", "last known position: "), ("b17 order", None))      # (1.7: his weapon follows the order)


def obs_cols(inputs_csv=None, sel=OBS_SEL):
    """the indices of OBS_SEL's inputs (sel: W_OBS for the weapon part's) in docs/INPUTS.csv (an input name ending in a space or ': '
    is a prefix)"""
    if inputs_csv is None:
        inputs_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUTS.csv")
    out = []
    for r in csv.DictReader(open(inputs_csv, encoding="utf-8")):
        g, n = r["group"], r["input"]
        if "believed" in n:                                  # (the old rule-made belief stays out: v0.4.2's fade)
            continue
        for sg, sn in sel:
            if g == sg and (sn is None or n == sn or (sn.endswith(" ") and n.startswith(sn))):
                out.append(int(r["index"]))
                break
    return sorted(out)


def layout(brain=256, trk=27, trz=28, ahead=0, ctrl=4, obs=None, hands=512, enc=256, size=256, inp=256, plan=64,
           n_target=17, every=8, gamma=0.9998, chrono=300, on=None, ctrl_src="none", chrono_lo=0.0, fight=0):
    """the part's shape; kept in a checkpoint as "head2" (the gate is the state dict's head2.gate). obs: the input columns
    (obs_cols()); on: {part: 0 or 1} (default all on; a part off reads zeros)"""
    obs = [int(c) for c in (obs if obs is not None else obs_cols())]
    on_ = {p: 1 for p in PARTS}
    on_.update({str(k): int(v) for k, v in (on or {}).items()})
    w = dict(brain=int(brain), trk=int(trk), trz=int(trz), ahead=int(ahead), ctrl=int(ctrl), obs=len(obs), hands=int(hands))
    if fight:
        w["fight"] = int(fight)
    assert ctrl_src in CTRL_SRCS, "ctrl_src: one of {}".format(CTRL_SRCS)
    return dict(version=VERSION, widths=w, on=on_, obs_cols=obs, enc=int(enc), size=int(size), inp=int(inp), plan=int(plan),
                n_target=int(n_target), every=int(every), gamma=float(gamma), chrono=int(chrono), ctrl_src=str(ctrl_src),
                **({"chrono_lo": float(chrono_lo)} if chrono_lo > 0 else {}))


def add_weapon(L, wobs, n):
    """(1.5a) a layout with the weapon part: n scores (the weapon key's choices), its inputs the columns wobs"""
    wobs = [int(c) for c in wobs]
    return dict(L, widths=dict(L["widths"], wobs=len(wobs)), on=dict(L["on"], wobs=1), wobs_cols=wobs, weapon=int(n))


def ctrl_src(L):
    """the ctrl slot's source ("none" for a layout made before it was wired)"""
    return str(L.get("ctrl_src", "none") or "none")


def u_width(L):
    return int(sum(int(L["widths"].get(p, 0)) for p in PARTS))


def u0_width(L):
    """(1.5a) u's width before the weapon part's inputs: what inp reads"""
    return u_width(L) - int(L["widths"].get("wobs", 0))


def n_weights(L):
    U, I, S, P, E, N, Hh = u0_width(L), L["inp"], L["size"], L["plan"], L["enc"], L["n_target"], L["widths"]["hands"]
    Wo, Nw = int(L["widths"].get("wobs", 0)), int(L.get("weapon", 0) or 0)
    return (U * I + I) + 3 * S * (I + S) + 6 * S + (S * P + P) + (P * E + E) + (S * N + N) + (S + Hh + 1) + \
        ((S + Hh + KEEP_F + 1) if L.get("keep") else 0) + ((Wo * I + I) + (S * Nw + Nw) if Nw else 0) + \
        ((S * CMB_NK + CMB_NCTX * CMB_NK + CMB_NK + S * CMB_HID + CMB_F * CMB_HID + 2 * CMB_HID + 1) if L.get("cmb") else 0) + \
        ((S * 2 + 2) if L.get("fire") else 0) + \
        ((lambda I_: 2 * (S + int(I_["xf"]) + 2) * int(I_["hid"]) + (int(I_["a"]) + 1) * int(I_["hid"]) + int(I_["hid"]) + 1
          + (int(I_["hid"]) + 1) * int(I_["nw"]) + ((int(I_["hid"]) + 1) if I_.get("quiet") else 0))(L["ins"]) if L.get("ins") else 0)


def describe(L):
    return ("strategy head (v0.4.3): GRU {} a tick every {} frames ({:.2f} s) on {} numbers ({}), plan {} into the hands' "
            "input, a bias on {} intentions, its value at gamma {} ({:.0f} s); {:,} weights").format(
        L["size"], L["every"], L["every"] * 0.025, u_width(L),
        " + ".join("{} {}{}".format(p, L["widths"].get(p, 0), "" if L["on"].get(p, 1) else " (off)") for p in PARTS if L["widths"].get(p, 0)),
        L["plan"], L["n_target"], L["gamma"], 0.025 / max(1e-9, 1.0 - L["gamma"]), n_weights(L)) + \
        ("; its weapon part: {} scores added to the weapon key's, its {} inputs read by winp".format(L["weapon"], L["widths"].get("wobs", 0))
         if L.get("weapon") else "") + \
        ("; the combat order: {} kinds ({}), a pointer of {} over {} candidates of {} numbers".format(
            CMB_NK, ", ".join(CMB_KINDS), CMB_HID, CMB_ROWS, CMB_F) if L.get("cmb") else "") + \
        ("; the fire push: 2 scores added to the fire key's" if L.get("fire") else "")


def _offs(L):
    o, out = 0, {}
    for p in PARTS:
        out[p] = (o, o + int(L["widths"].get(p, 0)))
        o += int(L["widths"].get(p, 0))
    return out


# ------------------------------------------------------------------------------------------------------------------ torch
def make_module(L, seed=4044):
    """the part: inp, gru (GRUCell), plan_out, plan_in (zeros), target (zeros), v; the buffer gate (0). From a random stream
    of its own (the global stream after it is the one without)"""
    import torch
    import torch.nn as nn

    class Head2(nn.Module):
        def __init__(self):
            super().__init__()
            S = int(L["size"])
            self.inp = nn.Linear(u0_width(L), int(L["inp"]))
            self.gru = nn.GRUCell(int(L["inp"]), S)
            self.plan_out = nn.Linear(S, int(L["plan"]))
            self.plan_in = nn.Linear(int(L["plan"]), int(L["enc"]))
            self.target = nn.Linear(S, int(L["n_target"]))
            self.v = nn.Linear(S + int(L["widths"]["hands"]), 1)
            if L.get("keep"):                                # (1.4c) the keep choice: zeros here, its start from tools/keep_init.py
                assert int(L["keep"]) == 2, "1.4c's keep choice (three numbers, once a second) is retired: tools/keep_init.py add gives 1.7a's"
                self.keep = nn.Linear(S + int(L["widths"]["hands"]) + KEEP_F, 1)
                nn.init.zeros_(self.keep.weight)
                nn.init.zeros_(self.keep.bias)
                self.register_buffer("keep_g", torch.zeros(()))
            self.register_buffer("gate", torch.zeros(()))
            self.register_buffer("mix", torch.zeros(()))     # (b1.4a) his target choice moved from the hands' to the head's
            self.register_buffer("add", torch.zeros(()))     # (1.3b) the head's own scores added to the hands'
            for l_ in (self.plan_in, self.target, self.v):
                nn.init.zeros_(l_.weight)
                nn.init.zeros_(l_.bias)
            tmax = int(L.get("chrono", 0))
            if tmax > 1:                                     # the update gate starts near 1 for long time scales (in ticks)
                with torch.no_grad():
                    lo_ = float(L.get("chrono_lo", 0) or 0)
                    if lo_ > 0:                              # (1.3b) evenly in log from lo_ to tmax ticks
                        tau = torch.exp(math.log(lo_) + torch.rand(S) * (math.log(tmax) - math.log(lo_)))
                    else:
                        tau = 1.0 + torch.rand(S) * (tmax - 1.0)
                    self.gru.bias_ih[S:2 * S] = torch.log((tau - 1.0).clamp(min=1e-3))
                    self.gru.bias_hh[S:2 * S] = 0.0
            if L.get("weapon"):                              # (1.5a) the weapon part: zeros here (after the draws above: their stream as before)
                self.winp = nn.Linear(int(L["widths"]["wobs"]), int(L["inp"]))
                self.wsc = nn.Linear(S, int(L["weapon"]))
                for l_ in (self.winp, self.wsc):
                    nn.init.zeros_(l_.weight)
                    nn.init.zeros_(l_.bias)
                self.register_buffer("wadd", torch.zeros(()))
            if L.get("cmb"):                                 # (1.7) the combat order: its start from tools/order_init.py (the pros' fit)
                self.ok_s = nn.Linear(S, CMB_NK)             # the kind: on his state (zero at the start) and the situation's numbers
                self.ok_c = nn.Linear(CMB_NCTX, CMB_NK)
                self.op_s = nn.Linear(S, CMB_HID)            # the pointer: g(s, x) = op_v(tanh(op_s(s) + op_x(x)))
                self.op_x = nn.Linear(CMB_F, CMB_HID)
                self.op_v = nn.Linear(CMB_HID, 1)
                for l_ in (self.ok_s, self.ok_c, self.op_s, self.op_v):
                    nn.init.zeros_(l_.weight)
                    nn.init.zeros_(l_.bias)
                self.register_buffer("cmb_g", torch.zeros(()))
                self.register_buffer("padd", torch.zeros(()))
            if L.get("fire"):                                # (1.7) the fire push: zeros
                self.fsc = nn.Linear(S, 2)
                nn.init.zeros_(self.fsc.weight)
                nn.init.zeros_(self.fsc.bias)
                self.register_buffer("fadd", torch.zeros(()))
            if L.get("ins"):                                 # (2.1; inside the head on the owner's word, 2026-11-11) the instruction's choice:
                I = L["ins"]                                 # the rows' scorer, the weapon's scores, the quiet logit (see "2.1: the instruction"
                Hi, Fi, Ai = int(I["hid"]), int(I["xf"]), int(I["a"])    # below). After every older draw: their stream as before.
                self.ins_is = nn.Linear(S, Hi)
                self.ins_ix = nn.Linear(Fi, Hi)
                self.ins_ia = nn.Linear(Ai, Hi)
                self.ins_iv = nn.Linear(Hi, 1)
                self.ins_ws = nn.Linear(S, Hi)
                self.ins_wx = nn.Linear(Fi, Hi)
                self.ins_wv = nn.Linear(Hi, int(I["nw"]))
                for l_ in (self.ins_iv, self.ins_wv):        # its last layers at zero: every offered row alike, every usable weapon alike
                    nn.init.zeros_(l_.weight)
                    nn.init.zeros_(l_.bias)
                if I.get("quiet"):                           # (quiet movement) one logit on the weapon's hidden layer; at the start: never
                    self.ins_qv = nn.Linear(Hi, 1)           # asked (a bias of INS_Q0, weights zero)
                    nn.init.zeros_(self.ins_qv.weight)
                    nn.init.constant_(self.ins_qv.bias, INS_Q0)
                self.ins_vv = nn.Linear(S + int(L["widths"]["hands"]), 1)    # (the owner, 2026-11-11: the head is paid by the win chance only) the head's
                nn.init.zeros_(self.ins_vv.weight)           # value of the WIN-CHANCE pay alone (no entry of the pay table), on the state its
                nn.init.zeros_(self.ins_vv.bias)             # older value reads; made last: every older layer's draw as before. At zero.
                self.register_buffer("ins_g", torch.zeros(()))    # the share of seats whose instruction is the head's

        def _load_from_state_dict(self, state_dict, prefix, *args, **kw):
            if prefix + "mix" not in state_dict:             # (a save from before b1.4a: no mix, 0)
                state_dict[prefix + "mix"] = torch.zeros(())
            if prefix + "add" not in state_dict:             # (a save from before 1.3b: no add, 0)
                state_dict[prefix + "add"] = torch.zeros(())
            if L.get("keep") and prefix + "keep_g" not in state_dict:     # (1.4c) no share in the file: 0
                state_dict[prefix + "keep_g"] = torch.zeros(())
            if L.get("weapon") and prefix + "wadd" not in state_dict:     # (1.5a) no add in the file: 0
                state_dict[prefix + "wadd"] = torch.zeros(())
            for k_, on_ in (("cmb_g", L.get("cmb")), ("padd", L.get("cmb")), ("fadd", L.get("fire"))):    # (1.7) no share, no add in the file: 0
                if on_ and prefix + k_ not in state_dict:
                    state_dict[prefix + k_] = torch.zeros(())
            if L.get("ins") and prefix + "ins_g" not in state_dict:       # (2.1) no share in the file: 0
                state_dict[prefix + "ins_g"] = torch.zeros(())
            super()._load_from_state_dict(state_dict, prefix, *args, **kw)

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return Head2()


def feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None, fight=None, ins=None):
    """u [B, u_width] (float32 holding half-precision numbers) from the parts (a part None or off: zeros). obs: his
    normalised inputs [B, all inputs] (the columns are taken here). (2.1) ins: the instruction he is on (ins_u; before wobs: what
    inp reads; a layout without the part: 0 wide)"""
    import torch
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands, wobs=obs, fight=fight, ins=ins)
    ref = next(v for v in src.values() if v is not None)
    B = ref.shape[0]
    cols = []
    for p in PARTS:
        w = int(L["widths"].get(p, 0))
        if w == 0:
            continue
        v = src[p]
        if v is None or not L["on"].get(p, 1):
            cols.append(torch.zeros(B, w, device=ref.device))
            continue
        v = v.float()
        if p in ("obs", "wobs"):                             # (1.5a: wobs, the weapon part's columns of the same inputs)
            v = v[:, torch.as_tensor(L[p + "_cols"], dtype=torch.long, device=v.device)]
        if v.shape[1] != w:                                  # (ctrl: the readout's first columns, zeros past its end)
            v = v[:, :w] if v.shape[1] > w else torch.cat([v, v.new_zeros(B, w - v.shape[1])], 1)
        if p in ("trk", "trz", "ahead", "ctrl", "fight", "ins"):
            v = v.clamp(-CLIP, CLIP)
        cols.append(v)
    return torch.cat(cols, 1).half().float()


def has_weapon(mod):
    """(1.5a) the module has the weapon part"""
    return mod is not None and hasattr(mod, "wsc")


def pre(mod, u):
    """the GRU's input from u: tanh(inp(u)); (1.5a) with the weapon part tanh(inp(u before wobs) + winp(wobs))"""
    import torch
    if not has_weapon(mod):
        return torch.tanh(mod.inp(u))
    n0 = int(mod.inp.in_features)
    return torch.tanh(mod.inp(u[..., :n0].contiguous()) + mod.winp(u[..., n0:].contiguous()))


def outs(mod, s):
    """(plan, bias) of a state s [..., size]: the plan tanh(plan_out(s)), the bias with the gate applied (the plan's is applied
    where the hands read it: gate x plan_in(plan))"""
    import torch
    return torch.tanh(mod.plan_out(s)), mod.gate * mod.target(s)


def value(mod, s, h):
    import torch
    return mod.v(torch.cat([s, h], -1)).squeeze(-1)


def value_w(mod, s, h):
    """(2.1, --ins-pay-win) the head's value of the win-chance pay alone (ins_vv): what 2.1's parts learn from"""
    import torch
    return mod.ins_vv(torch.cat([s, h], -1)).squeeze(-1)


def control_t(net, s_brain, hands=None, src="none"):
    """(the ctrl slot) the "in control" readout src ("belief": on the brain's state; "both": on the brain's state and the
    hands' memory) of the network's ModuleDict `control` -> [B, 4] its chances minus 0.5, a number (no_grad, detached);
    None (zeros in the slot) for "none" or a network without that readout"""
    import torch
    if src in (None, "none"):
        return None
    c = getattr(net, "control", None)
    if c is None or not hasattr(c, "keys") or src not in c.keys():
        return None
    with torch.no_grad():
        x = s_brain.detach().float()
        if src == "both":
            m = int(c[src][0].in_features) - x.shape[1]
            x = torch.cat([x, hands.detach()[:, :m].float()], 1)
        return (torch.sigmoid(c[src](x.half().float()).float()) - 0.5).detach()


def fight_t(net, s_brain, hands, L=None):
    """(1.7b, the part fight) the network's fight odds readout (sim/fightodds.py; a ModuleDict `fight`, "both": the brain's state and the
    hands' memory) -> [B, 2] its chances minus 0.5, a number (no_grad, detached); None (zeros in the part) for a layout without the
    part or a network without the readout"""
    import torch
    if L is not None and not int(L["widths"].get("fight", 0)):
        return None
    f = getattr(net, "fight", None)
    if f is None or not hasattr(f, "keys") or "both" not in f.keys():
        return None
    with torch.no_grad():
        x = s_brain.detach().float()
        m = int(f["both"][0].in_features) - x.shape[1]
        x = torch.cat([x, hands.detach()[:, :m].float()], 1)
        return (torch.sigmoid(f["both"](x.half().float()).float()) - 0.5).detach()


class State:
    """the head's live state for n seats (the trainer's rollout): s, valid (outputs held: no reset since the last tick), the
    held plan and bias"""

    def __init__(self, n, L, dev):
        import torch
        self.L = L
        self.s = torch.zeros(n, int(L["size"]), device=dev)
        self.valid = torch.zeros(n, device=dev)
        self.plan = torch.zeros(n, int(L["plan"]), device=dev)
        self.bias = torch.zeros(n, int(L["n_target"]), device=dev)
        self.raw = torch.zeros(n, int(L["n_target"]), device=dev)     # (b1.4a) its own target choice, held as the bias is
        self.wraw = torch.zeros(n, int(L["weapon"]), device=dev) if L.get("weapon") else None   # (1.5a) its weapon scores, held so
        cm_ = L.get("cmb")                                  # (1.7) the order's held numbers: the kind's logits, the new candidates'
        self.okl = torch.zeros(n, CMB_NK, device=dev) if cm_ else None    # scores (invalid: -inf), the targets' and the ways' adds
        self.ops = torch.zeros(n, CMB_NEW, device=dev) if cm_ else None
        self.tadd = torch.zeros(n, CMB_T, device=dev) if cm_ else None
        self.yadd = torch.zeros(n, CMB_W, device=dev) if cm_ else None
        self.fraw = torch.zeros(n, 2, device=dev) if L.get("fire") else None      # (1.7) its fire scores, held so

    def refresh(self, mod):
        """before a rollout: the held outputs made again from the state with the weights and gate it is played at (the
        learning step makes the first segment's the same way)"""
        import torch
        with torch.no_grad():
            p, b = outs(mod, self.s)
            self.plan, self.bias = p * self.valid[:, None], b * self.valid[:, None]
            self.raw = mod.target(self.s) * self.valid[:, None]
            if self.wraw is not None and has_weapon(mod):
                self.wraw = mod.wsc(self.s) * self.valid[:, None]
            if self.fraw is not None and has_fire(mod):
                self.fraw = mod.fsc(self.s) * self.valid[:, None]

    def order_tick(self, mod, x, ctx):
        """(1.7) at a keep reading: the order's numbers from the state and the candidates' x [n, CMB_ROWS, CMB_F], ctx [n, CMB_NCTX];
        held to the next"""
        import torch
        if self.okl is None or not has_cmb(mod):
            return
        with torch.no_grad():
            kl, ps, ta, ya = order_scores(mod, self.s, x, ctx)
            self.okl, self.ops = kl, ps
            self.tadd, self.yadd = ta * self.valid[:, None], ya * self.valid[:, None]

    def order(self, mod):
        """(1.7) the held order: the kind's logits [n, CMB_NK] and the new candidates' scores [n, CMB_NEW] (shut: -inf), where it has a
        state [n]; (None, None, None) without the part"""
        if self.okl is None or not has_cmb(mod):
            return None, None, None
        return self.okl, self.ops, self.valid > 0

    def adds(self, mod):
        """(what the hands' fast GRU input gets, what the intention's logits get, the mix k [n, 1], the head's own choice, the
        add [n, 1], (1.5a) what the weapon key's logits get [n, weapon] or None, (1.7) what the fire key's logits get [n, 2] or None)
        on this frame"""
        return (mod.gate * mod.plan_in(self.plan) * self.valid[:, None], self.bias, mod.mix * self.valid[:, None], self.raw,
                mod.add * self.valid[:, None],
                mod.wadd * self.valid[:, None] * self.wraw if (self.wraw is not None and has_weapon(mod)) else None,
                mod.fadd * self.valid[:, None] * self.fraw if (self.fraw is not None and has_fire(mod)) else None,
                mod.padd * self.tadd if (self.tadd is not None and has_cmb(mod)) else None,
                mod.padd * self.yadd if (self.yadd is not None and has_cmb(mod)) else None)

    def tick(self, mod, u):
        import torch
        self.s = mod.gru(pre(mod, u), self.s)
        self.valid = torch.ones_like(self.valid)
        self.plan, self.bias = outs(mod, self.s)
        self.raw = mod.target(self.s)
        if self.wraw is not None and has_weapon(mod):
            self.wraw = mod.wsc(self.s)
        if self.fraw is not None and has_fire(mod):
            self.fraw = mod.fsc(self.s)

    def reset(self, d):
        k = 1.0 - d
        self.s = self.s * k[:, None]
        self.valid = self.valid * k
        self.plan = self.plan * k[:, None]
        self.bias = self.bias * k[:, None]
        self.raw = self.raw * k[:, None]
        if self.wraw is not None:
            self.wraw = self.wraw * k[:, None]
        if self.tadd is not None:                            # (1.7: a reset clears the order's adds; its kind and scores wait for the next reading)
            self.tadd = self.tadd * k[:, None]
            self.yadd = self.yadd * k[:, None]
        if self.fraw is not None:
            self.fraw = self.fraw * k[:, None]

    def snap(self):
        return self.s.clone(), self.valid.clone()


def seq(mod, L, U, dn, s0, v0, plan_grad=0.0):
    """the learning step over a rollout's whole sequences, the same numbers as the rollout's State frame by frame:
      U   [J, B, u]  the ticks' inputs as stored (J = T / every; tick j on frame j every + every - 1)
      dn  [T, B]     1 - done (a reset after that frame)
      s0, v0         the state and its valid flag at the rollout's start (State.snap(), after the reset of the frame before)
    -> dict gin [T, B, enc] (into the fast GRU's input), bias [T, B, n_target], s_held [T, B, size] (the state each frame's
    outputs read; zeros after a reset), alive [T, B], s [J, B, size], plan [J + 1, B, plan] (the held plans: the rollout's
    own first), raw [T, B, n_target] (b1.4a: its own target choice), k [T, B, 1] (the mix where it has a state), a [T, B, 1]
    (1.3b: the add where it has a state), w [T, B, weapon] (1.5a: wadd x its weapon scores where it has a state; None without),
    f [T, B, 2] (1.7: fadd x its fire scores on the state as a number). (1.7) The order's numbers per frame come from
    order_seq() with the stored candidates."""
    import torch
    T, B = dn.shape
    K = int(L["every"])
    assert T % K == 0, (T, K)
    J = T // K
    s = s0
    S_l = [s0]
    for j in range(J):
        f0 = j * K
        keep = dn[max(f0 - 1, 0):f0 + K - 1].prod(0)       # no reset since the last tick (the rollout's start: s0 is after it)
        s = mod.gru(pre(mod, U[j]), s * keep[:, None])
        S_l.append(s)
    St = torch.stack(S_l)                                    # [J + 1, B, size]: the state each segment's frames read
    P, Bi = outs(mod, St)
    al = []
    for j in range(J):
        f0 = j * K
        g = torch.cat([(v0 if j == 0 else dn[f0 - 1])[None], dn[f0:f0 + K - 1]], 0)
        al.append(torch.cumprod(g, 0))
    alive = torch.cat(al, 0)                                 # [T, B]
    idx = torch.arange(T, device=dn.device) // K
    am = alive[..., None]
    Pf = P[idx] * am
    if plan_grad != 1.0:                                     # (the gradient into the head through the plan, times plan_grad)
        Pf = Pf.detach() + plan_grad * (Pf - Pf.detach()) if plan_grad > 0 else Pf.detach()
    gin = mod.gate * mod.plan_in(Pf) * am
    Sh = St[idx] * am
    return dict(gin=gin, bias=Bi[idx] * am, s_held=Sh, alive=alive, s=St[1:], plan=P, raw=mod.target(Sh) * am, k=mod.mix * am,
                a=mod.add * am, w=(mod.wadd * am * mod.wsc(Sh)) if has_weapon(mod) else None,
                f=(mod.fadd * am * mod.fsc(Sh.detach())) if has_fire(mod) else None)


def order_scores(mod, s, x, ctx):
    """(1.7) the order's numbers from the state s [..., size], the candidates x [..., CMB_ROWS, CMB_F] and the situation ctx [...,
    CMB_NCTX] -> the kind's logits [..., CMB_NK] (a kind without a valid candidate: -inf; the target as chosen always there), the new
    candidates' scores [..., CMB_NEW] (invalid: -inf), the targets' adds [..., CMB_T] and the ways' [..., CMB_W] (invalid: 0)"""
    import torch
    x = x.float()
    val = x[..., CMB_VALID] > 0.5
    g = mod.op_v(torch.tanh(mod.op_s(s.float())[..., None, :] + mod.op_x(x))).squeeze(-1)      # [..., CMB_ROWS]
    neg = torch.finfo(g.dtype).min / 4
    t0, n0 = CMB_T, CMB_T + CMB_NEW
    ps = torch.where(val[..., t0:n0], g[..., t0:n0], torch.full_like(g[..., t0:n0], neg))
    kl = mod.ok_s(s.float()) + mod.ok_c(ctx.float())
    has = [torch.ones_like(val[..., 0])] + [val[..., t0 + c0:t0 + c0 + k].any(-1) for c0, k in zip(CMB_C0[1:], CMB_SLOTS[1:])]
    kl = torch.where(torch.stack(has, -1), kl, torch.full_like(kl, neg))
    ta = torch.where(val[..., :t0], g[..., :t0], torch.zeros_like(g[..., :t0]))
    ya = torch.where(val[..., n0:], g[..., n0:], torch.zeros_like(g[..., n0:]))
    return kl, ps, ta, ya


def order_scores_fixed(R, x, ctx):
    """(1.7b, --ord-kl) the order's kind logits and new candidates' scores of a fixed reference R (a dict of tensors: ok_c.weight, ok_c.bias,
    op_x.weight, op_x.bias, op_v.weight, op_v.bias; its state's layers ok_s, op_s at zero, as the pros' fit starts them), from the candidates
    x [..., CMB_ROWS, CMB_F] and the situation ctx [..., CMB_NCTX], with order_scores' masks"""
    import torch
    import torch.nn.functional as F_
    x = x.float()
    val = x[..., CMB_VALID] > 0.5
    g = F_.linear(torch.tanh(F_.linear(x, R["op_x.weight"], R["op_x.bias"])), R["op_v.weight"], R["op_v.bias"]).squeeze(-1)
    neg = torch.finfo(g.dtype).min / 4
    t0, n0 = CMB_T, CMB_T + CMB_NEW
    ps = torch.where(val[..., t0:n0], g[..., t0:n0], torch.full_like(g[..., t0:n0], neg))
    kl = F_.linear(ctx.float(), R["ok_c.weight"], R["ok_c.bias"])
    has = [torch.ones_like(val[..., 0])] + [val[..., t0 + c0:t0 + c0 + k].any(-1) for c0, k in zip(CMB_C0[1:], CMB_SLOTS[1:])]
    kl = torch.where(torch.stack(has, -1), kl, torch.full_like(kl, neg))
    return kl, ps


def order_kl(R, kl, ps, x, ctx, seg):
    """(1.7b, --ord-kl; AlphaStar's KL to the human policy) KL(reference || the head's) of the order: over the kinds, and within each new
    kind over its candidates weighted by the reference's chance of that kind -> [T, n]. kl, ps: the head's (order_scores, held per frame);
    x, ctx: the candidates and the situation per segment, seg [T] each frame's segment. The reference is a number (no gradient)"""
    import torch
    with torch.no_grad():
        kr, pr = order_scores_fixed(R, x, ctx)
        kr, pr = kr[seg], pr[seg]
        lkr = torch.log_softmax(kr, -1)
        pkr = lkr.exp()
    lk = torch.log_softmax(kl, -1)
    out = (pkr * (lkr - lk)).sum(-1)
    for k_ in range(1, CMB_NK):
        c0, m = CMB_C0[k_], CMB_SLOTS[k_]
        lc = torch.log_softmax(ps[..., c0:c0 + m], -1)
        with torch.no_grad():
            lcr = torch.log_softmax(pr[..., c0:c0 + m], -1)
            pcr = lcr.exp()
        out = out + pkr[..., k_] * (pcr * (lcr - lc)).sum(-1)
    return out


def order_logp(kl, ps, kind, cand):
    """(1.7) the order's log-probability [...] of the kind [...] and (for a new kind) its candidate [...] (within the kind) under the
    kind's logits kl and the new candidates' scores ps; and the log-probabilities of the kinds [..., CMB_NK]"""
    import torch
    lk = torch.log_softmax(kl, -1)
    out = lk.gather(-1, kind[..., None]).squeeze(-1)
    for k_ in range(1, CMB_NK):
        c0, m = CMB_C0[k_], CMB_SLOTS[k_]
        lc = torch.log_softmax(ps[..., c0:c0 + m], -1)
        pick = lc.gather(-1, cand.clamp(0, m - 1)[..., None]).squeeze(-1)
        out = out + torch.where(kind == k_, pick, torch.zeros_like(pick))
    return out, lk


def has_cmb(mod):
    """(1.7) the module has the combat order"""
    return mod is not None and hasattr(mod, "op_v")


def has_fire(mod):
    """(1.7) the module has the fire push"""
    return mod is not None and hasattr(mod, "fsc")


def has_keep(mod):
    """(1.4c) the module has the keep choice"""
    return mod is not None and hasattr(mod, "keep")


def keep_x(feat, lp_held):
    """(1.4c, 1.7a) the keep choice's own numbers [..., KEEP_F] from the simulator's keep_feat [..., KEEP_FEAT] (age s, contact,
    target, arrived, since arrival s, since a sound s, since a hit unseen s) and the held target's log-probability [...]
    (numbers: no gradient)"""
    import torch
    feat = feat.float()
    c, ar = feat[..., 1], feat[..., 3] * (1.0 - feat[..., 1])
    age = (1.0 - c) * (1.0 - ar) * feat[..., 0].clamp(0.0, KEEP_AGE_MAX) / 10.0
    sa = ar * feat[..., 4].clamp(0.0, KEEP_AGE_MAX) / 10.0
    return torch.stack([age, c, lp_held.float().clamp(min=KEEP_LP_MIN) / 5.0, ar, sa, torch.exp(-feat[..., 5].clamp(min=0.0) / KEEP_RECENT),
                        torch.exp(-feat[..., 6].clamp(min=0.0) / KEEP_RECENT)], -1).detach()


def keep_logit(mod, s, h, f):
    """(1.4c) the logit of re-deciding [...] from the head's held state s, the hands' memory h (a number) and f (keep_x)"""
    import torch
    return mod.keep(torch.cat([s, h.detach().float(), f], -1)).squeeze(-1)


def gae(rew, val, done, gamma, lam):
    """the head's advantages and returns: rew, done [T, B], val [T + 1, B]"""
    import torch
    T = rew.shape[0]
    adv = torch.zeros_like(rew)
    last = torch.zeros_like(rew[0])
    for t in reversed(range(T)):
        nt = 1.0 - done[t]
        dl = rew[t] + gamma * val[t + 1] * nt - val[t]
        last = dl + gamma * lam * nt * last
        adv[t] = last
    return adv, adv + val[:T]


def add_bias(lg, bias, i0):
    """his logits with the bias added to the intention's (its choices begin at i0)"""
    import torch
    n = bias.shape[-1]
    return torch.cat([lg[..., :i0], lg[..., i0:i0 + n] + bias, lg[..., i0 + n:]], -1)


def mix_in(lg, g2, i0):
    """(b1.4a) his logits with the head's part on the intention's: (1 - k) x the hands' + k x its own choice + the bias.
    g2: (gin, bias) as before b1.4a, (gin, bias, k, raw), or (1.3b) (gin, bias, k, raw, add): (1 - k) x the hands' + (k + add)
    x its own + the bias. k and add 0 everywhere: add_bias's numbers (1 x a = a, a + 0 = a; no check of k here: that would
    wait on the card every frame)"""
    import torch
    if len(g2) < 4:
        return add_bias(lg, g2[1], i0)
    n = g2[1].shape[-1]
    k = g2[2]
    kr = k if len(g2) < 5 or g2[4] is None else k + g2[4]
    return torch.cat([lg[..., :i0], (1.0 - k) * lg[..., i0:i0 + n] + kr * g2[3] + g2[1], lg[..., i0 + n:]], -1)


# ------------------------------------------------------------------------------------------------------------------ numpy
def params_np(sd, prefix="head2."):
    out = {}
    for k, v in sd.items():
        if k.startswith(prefix):
            out[k[len(prefix):]] = np.asarray(v.cpu().numpy() if hasattr(v, "cpu") else v, np.float32)
    return out


def np_state_width(L):
    """per seat: [s (size) | valid]"""
    return int(L["size"]) + 1


def np_open(W):
    """the head acts (its gate above 0 and plan_in or target not all zero; or, b1.4a, its mix above 0 and target not all zero)"""
    tg_ = np.abs(W["target.weight"]).sum() + np.abs(W["target.bias"]).sum()
    if np_wadd_on(W):                                        # (1.5a) its weapon scores added and not all zero
        return True
    if "op_v.weight" in W and float(np.asarray(W.get("padd", 0.0))) > 0 and float(np.abs(W["op_v.weight"]).sum()) > 0:
        return True                                          # (1.7) the pointer's scores added to the targets' and the way's
    if "fsc.weight" in W and float(np.asarray(W.get("fadd", 0.0))) > 0 and \
            float(np.abs(W["fsc.weight"]).sum() + np.abs(W["fsc.bias"]).sum()) > 0:
        return True                                          # (1.7) its fire scores added
    if (float(np.asarray(W.get("mix", 0.0))) > 0 or float(np.asarray(W.get("add", 0.0))) > 0) and tg_ > 0:
        return True
    return float(np.asarray(W.get("gate", 0.0))) > 0 and (np.abs(W["plan_in.weight"]).sum() + np.abs(W["plan_in.bias"]).sum() + tg_) > 0


def np_mix_in(W, L, hs, lg):
    """(b1.4a) the intention's logits lg [B, n_target] (the hands', before the gate's bias is added) with the mix: (1 - k) x
    the hands' + k x its own choice, k = mix where it has a state (hs [B, np_state_width]); (1.3b) + add x its own where it
    has a state. Unchanged with mix and add 0"""
    m = float(np.asarray(W.get("mix", 0.0)))
    ad = float(np.asarray(W.get("add", 0.0)))
    if m <= 0 and ad <= 0:
        return lg
    S = int(L["size"])
    s, ok = hs[:, :S], hs[:, S:S + 1]
    k = np.float32(m) * ok
    raw = s @ W["target.weight"].T + W["target.bias"]
    return ((1.0 - k) * lg + (k + np.float32(ad) * ok) * raw).astype(np.float32)


def np_wadd_on(W):
    """(1.5a) the arrays have the weapon part, its add above 0 and its scores not all zero"""
    return ("wsc.weight" in W and float(np.asarray(W.get("wadd", 0.0))) > 0
            and float(np.abs(W["wsc.weight"]).sum() + np.abs(W["wsc.bias"]).sum()) > 0)


def np_wadd(W, L, hs):
    """(1.5a) what the weapon key's logits get [B, weapon] from the state hs [B, np_state_width]: wadd x its scores where it has a
    state; None without the part or at wadd 0"""
    if "wsc.weight" not in W or not float(np.asarray(W.get("wadd", 0.0))) > 0:
        return None
    S = int(L["size"])
    s, ok = hs[:, :S], hs[:, S:S + 1]
    return (np.float32(np.asarray(W["wadd"])) * ok * (s @ W["wsc.weight"].T + W["wsc.bias"])).astype(np.float32)


def np_fadd(W, L, hs):
    """(1.7) what the fire key's logits get [B, 2] from the state hs: fadd x its fire scores where it has a state; None without the
    part or at fadd 0"""
    if "fsc.weight" not in W or not float(np.asarray(W.get("fadd", 0.0))) > 0:
        return None
    S = int(L["size"])
    s, ok = hs[:, :S], hs[:, S:S + 1]
    return (np.float32(np.asarray(W["fadd"])) * ok * (s @ W["fsc.weight"].T + W["fsc.bias"])).astype(np.float32)


def np_order_scores(W, L, hs, x, ctx):
    """(1.7) order_scores() in numpy from the state hs [B, np_state_width], x [B, CMB_ROWS, CMB_F], ctx [B, CMB_NCTX] -> kind logits,
    new candidates' scores, targets' adds, ways' adds, where it has a state [B]; Nones without the part"""
    if "op_v.weight" not in W:
        return None, None, None, None, None
    S = int(L["size"])
    s, ok = hs[:, :S].astype(np.float32), hs[:, S] > 0
    x = np.asarray(x, np.float32)
    val = x[..., CMB_VALID] > 0.5
    hid = np.tanh((s @ W["op_s.weight"].T + W["op_s.bias"])[:, None, :] + x @ W["op_x.weight"].T + W["op_x.bias"])
    g = (hid @ W["op_v.weight"].T)[..., 0] + W["op_v.bias"][0]
    neg = np.float32(-1e30)
    t0, n0 = CMB_T, CMB_T + CMB_NEW
    ps = np.where(val[:, t0:n0], g[:, t0:n0], neg).astype(np.float32)
    kl = s @ W["ok_s.weight"].T + W["ok_s.bias"] + np.asarray(ctx, np.float32) @ W["ok_c.weight"].T + W["ok_c.bias"]
    has = np.stack([np.ones(len(s), bool)] + [val[:, t0 + c0:t0 + c0 + k].any(1) for c0, k in zip(CMB_C0[1:], CMB_SLOTS[1:])], 1)
    kl = np.where(has, kl, neg).astype(np.float32)
    ta = np.where(val[:, :t0], g[:, :t0], 0.0).astype(np.float32)
    ya = np.where(val[:, n0:], g[:, n0:], 0.0).astype(np.float32)
    return kl, ps, ta, ya, ok


def np_has_keep(W):
    """(1.4c) the arrays have the keep choice"""
    return "keep.weight" in W


def np_keep_x(feat, lp_held):
    """keep_x() in numpy"""
    feat = np.asarray(feat, np.float32)
    c, ar = feat[:, 1], feat[:, 3] * (1.0 - feat[:, 1])
    age = (1.0 - c) * (1.0 - ar) * np.clip(feat[:, 0], 0.0, KEEP_AGE_MAX) / 10.0
    sa = ar * np.clip(feat[:, 4], 0.0, KEEP_AGE_MAX) / 10.0
    return np.stack([age, c, np.maximum(np.asarray(lp_held, np.float32), KEEP_LP_MIN) / 5.0, ar, sa,
                     np.exp(-np.maximum(feat[:, 5], 0.0) / KEEP_RECENT), np.exp(-np.maximum(feat[:, 6], 0.0) / KEEP_RECENT)], 1).astype(np.float32)


def np_keep_logit(W, L, hs, h, f):
    """keep_logit() in numpy: hs [B, np_state_width] (the held state), h [B, hands] the hands' memory, f [B, KEEP_F]"""
    S = int(L["size"])
    x = np.concatenate([hs[:, :S], np.asarray(h, np.float32), f], 1)
    return (x @ W["keep.weight"].T + W["keep.bias"])[:, 0].astype(np.float32)


def np_adds(W, L, hs):
    """(the fast GRU input's addition [B, enc], the intention's bias [B, n_target]) from the state hs [B, np_state_width]"""
    S = int(L["size"])
    s, ok = hs[:, :S], hs[:, S:S + 1]
    g = np.float32(W.get("gate", 0.0))
    plan = np.tanh(s @ W["plan_out.weight"].T + W["plan_out.bias"]) * ok
    gin = g * (plan @ W["plan_in.weight"].T + W["plan_in.bias"]) * ok
    bias = g * (s @ W["target.weight"].T + W["target.bias"]) * ok
    return gin.astype(np.float32), bias.astype(np.float32)


def np_mlp(P, x):
    """Linear (2 arrays) or Linear-ReLU-Linear (4)"""
    if len(P) == 2:
        return x @ P[0].T + P[1]
    return np.maximum(x @ P[0].T + P[1], 0.0) @ P[2].T + P[3]


def mlp_of(sd, name):
    """a readout's arrays from a state dict: name.0/name.2 (Sequential) or name.weight (Linear); None if absent"""
    g = lambda k: np.asarray(sd[k].cpu().numpy() if hasattr(sd[k], "cpu") else sd[k], np.float32)
    if name + ".0.weight" in sd:
        return tuple(g("{}.{}.{}".format(name, i, w)) for i in (0, 2) for w in ("weight", "bias"))
    if name + ".weight" in sd:
        return (g(name + ".weight"), g(name + ".bias"))
    return None


def np_ctrl_params(sd, L):
    """(the ctrl slot, numpy) the arrays of the readout the layout names (Linear-ReLU-Linear), None for "none" or absent"""
    src = ctrl_src(L)
    if src == "none":
        return None
    return mlp_of(sd, "control." + src)


def np_ctrl(P, s_brain, hands=None):
    """control_t() in numpy: P from np_ctrl_params (None: None); hands: the hands' memory after the frame (for "both")"""
    if P is None:
        return None
    x = np.asarray(s_brain, np.float32)
    m = int(P[0].shape[1]) - x.shape[1]
    if m > 0:
        x = np.concatenate([x, np.asarray(hands, np.float32)[:, :m]], 1)
    x = x.astype(np.float16).astype(np.float32)
    return (1.0 / (1.0 + np.exp(-np_mlp(P, x))) - 0.5).astype(np.float32)


def np_fight_params(sd, L):
    """(1.7b, the part fight, numpy) the fight odds readout's arrays (sim/fightodds.py's "fight.both"), None for a layout without the
    part or a network without the readout"""
    if not int(L["widths"].get("fight", 0)):
        return None
    try:
        return mlp_of(sd, "fight.both")
    except KeyError:
        return None


def np_fight(P, s_brain, hands):
    """(1.7b) fight_t() in numpy: P from np_fight_params (None: None)"""
    if P is None:
        return None
    x = np.asarray(s_brain, np.float32)
    m = int(P[0].shape[1]) - x.shape[1]
    x = np.concatenate([x, np.asarray(hands, np.float32)[:, :m]], 1).astype(np.float16).astype(np.float32)
    return (1.0 / (1.0 + np.exp(-np_mlp(P, x))) - 0.5).astype(np.float32)


def np_feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None, fight=None, ins=None):
    """feats() in numpy"""
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands, wobs=obs, fight=fight, ins=ins)
    B = len(next(v for v in src.values() if v is not None))
    cols = []
    for p in PARTS:
        w = int(L["widths"].get(p, 0))
        if w == 0:
            continue
        v = src[p]
        if v is None or not L["on"].get(p, 1):
            cols.append(np.zeros((B, w), np.float32))
            continue
        v = np.asarray(v, np.float32)
        if p in ("obs", "wobs"):                             # (1.5a: wobs, the weapon part's columns of the same inputs)
            v = v[:, np.asarray(L[p + "_cols"], np.int64)]
        if v.shape[1] != w:
            v = v[:, :w] if v.shape[1] > w else np.concatenate([v, np.zeros((B, w - v.shape[1]), np.float32)], 1)
        if p in ("trk", "trz", "ahead", "ctrl", "fight", "ins"):
            v = np.clip(v, -CLIP, CLIP)
        cols.append(v)
    return np.concatenate(cols, 1).astype(np.float16).astype(np.float32)


def np_tick(W, L, u, hs):
    """a tick for these rows: u [m, u_width], hs [m, np_state_width] -> the state after"""
    S = int(L["size"])
    s = hs[:, :S]
    n0 = int(W["inp.weight"].shape[1])                      # (1.5a) with the weapon part: inp on u before wobs, winp on wobs
    if "winp.weight" in W and u.shape[1] > n0:
        p = np.tanh(np.ascontiguousarray(u[:, :n0]) @ W["inp.weight"].T + W["inp.bias"] +
                    (np.ascontiguousarray(u[:, n0:]) @ W["winp.weight"].T + W["winp.bias"]))
    else:
        p = np.tanh(u @ W["inp.weight"].T + W["inp.bias"])
    gi = p @ W["gru.weight_ih"].T + W["gru.bias_ih"]
    gh = s @ W["gru.weight_hh"].T + W["gru.bias_hh"]
    r = 1.0 / (1.0 + np.exp(-(gi[:, :S] + gh[:, :S])))
    z = 1.0 / (1.0 + np.exp(-(gi[:, S:2 * S] + gh[:, S:2 * S])))
    n = np.tanh(gi[:, 2 * S:] + r * gh[:, 2 * S:])
    out = np.empty_like(hs)
    out[:, :S] = (1 - z) * n + z * s
    out[:, S] = 1.0
    return out.astype(np.float32)


def np_clear(L, hs, rows=None):
    r = slice(None) if rows is None else rows
    hs[r] = 0.0
    return hs

# ------------------------------------------------------------------------------------------------------- 2.1: the instruction
# (docs/runs/2.1/DESIGN.md, TRAINER_PARTS.md; owner, 2026-11-10: "It decides between a suite of questions, recurrently, with
# instructions that feed to hand for execution") The head's choice of an instruction: every tick the simulator gives each seat
# INS_C candidate rows (sim/duel_env.py instr_feat: a verb, a place, a point, what it depends on; xf numbers a row), the appraisals
# (sim/appraise.py) forecast what each would bring (6 numbers a row), and a scorer over the rows reads the head's state, a row's
# numbers and its forecast:  g(s, x, a) = iv(tanh(is(s) + ix(x) + ia(a))),  one score a row, a row the map does not offer: never.
# The weapon of the chosen row:  gw(s, x) = wv(tanh(ws(s) + wx(x))),  one score a weapon, a weapon he cannot use: never.
# ONE learned output decides (the scorer's); the appraisals' forecast is an input of it and the target of its lesson, not a logit
# added to it (CLAUDE.md rule 11: no sum of two learned outputs here).
# Where it lives (the owner, 2026-11-11: "of course that should be moved inside. the point is that the head learns how to make
# decisions ... It has to learn from its decisions what works and doesn't work"): INSIDE the head. The scorer's layers are layers of
# the head's module (ins_is, ins_ix, ins_ia, ins_iv; ins_ws, ins_wx, ins_wv; ins_qv; the share ins_g), in the network's state dict
# and the optimizer (a group "ins" at the head's rate). The learning step re-runs the head over the rollout (seq) and scores the kept
# readings again from the re-run state: the lesson toward the appraisals' order, the game's pay on his own readings and the entropy
# bonus are terms of the head's loss, so their gradient goes into the scorer AND through the state into the head's memory and its
# input layer (ins_loss). The appraisals, the map sense and the brain's readouts stay beside the network: they are inputs, not the head.
# ONE definition of the masked log-probabilities (ins_row_logp, ins_wq_logp, ins_joint_logp) is what the rollout draws from and
# stores, and what the learning step recomputes (1.7c's false start was a reference log-probability without a mask the play used);
# the checks' player and the plugin use its numpy twin (np_ins_row_logp, np_ins_wq_logp), proved equal by tools/run/test_21_parts.py.
INS_A = 7                                                    # a row's forecast: sim/appraise.py OUTS (dv the sixth, dv over the long window the seventh)
INS_DV, INS_DVL = 5, 6
INS_SIG = 8                                                  # the simulator's instr_state(): doing, done, failed, three change signals, and (third pass)
INS_SIG_WAKE = 6                                             # THE WAKE (the enemy's pain sound heard, or his believed stack fallen by a band: sim/duel_env.py
#                                                              INS_WAKE_DROP) and how far that stack has fallen since the instruction was given. A wake ends
#                                                              the keep as "done" and "failed" do: the head draws anew at that reading (ins_end)
INS_SEED = 4066
INS_Q0 = -6.0                                                # the quiet logit's start: asked about once in 400 picks
INS_BQ = 3                                                   # (the brain's questions among the head's inputs, for every seat, under an instruction or
#                                                              not: the chance the enemy knows where he is, minus 0.5 (sim/knownodds.py); how
#                                                              spread the brain's zone odds are (0 .. 1); how far apart its places 1, 2, 4 s ahead)
INS_MS = 8                                                   # (the map sense at a candidate's place: sim/mapsense.py's eight numbers, after the row's own)


def ins_redo(age, every):
    """(2.1a; the owner, 2026-11-12: "the head makes a decision every 200ms, that's its design and what should be built"; "The head is
    forced to redecide on a new thing to do every 200ms, which will often be 'continue what I was doing'") THE one rule, torch or numpy
    (the trainer's rollout, the checks' player, the plugin): a seat under the head's instruction draws anew at EVERY reading (every
    head tick, 0.2 s). "Continue" is drawing the row he is on (it is among the rows, marked on_now). Nothing holds an instruction
    between two ticks: not the 8-second lock, not 1.7a's keep choice, not a timer. ins_end() (done, failed, a wake) is then only a
    record. age, every: kept for the callers; every reading is True"""
    return age > -1.0


def bound_mask(m, wd):
    """(1.7c, --wrule; 2.1a, INS_BIND) the weapon key's frames that count: m [...] where the key's action was his own (wd [...] under
    0: neither the pros' table nor an instruction's binding set it), zero elsewhere. THE ONE DEFINITION: the rollout's stored
    log-probability and every pass of the learning step (the reference pass, the learner's, the entropy bonus) go through it, or
    the ratio lies (1.7c's false start: the reference pass without it)"""
    return m * (wd < 0).to(m.dtype)


def ins_end(sg):
    """THE one rule of what ends a keep whatever the keep choice says (the trainer's rollout, the checks' player, the plugin): the
    instruction is done, has failed, or a wake came (sg [..., INS_SIG]: the simulator's instr_state(); torch or numpy)"""
    return (sg[..., 1] > 0.5) | (sg[..., 2] > 0.5) | (sg[..., INS_SIG_WAKE] > 0.5)


def ins_u_width(xf, bq=0):
    """the part "ins" of the head's input: the row he is on (xf), its forecast when he took it (INS_A) and now (INS_A), the simulator's
    change signals (INS_SIG), how long he has been on it and whether he is on one (2); then the brain's questions (bq: INS_BQ or 0)"""
    return int(xf) + 2 * INS_A + INS_SIG + 2 + int(bq)


def add_ins(L, xf, nw, c, hid=128, quiet=0, ms=0, bq=0):
    """a layout with the instruction: the head's input gets the part "ins"; the scorer's shape under "ins". xf: the numbers of a row
    as the SIMULATOR gives them; ms: the map sense at the row's place is read after them (INS_MS more: the scorer's and the appraisals'
    rows are xf + ms wide, "xf" in the layout; the simulator's own count is kept as "fx"); bq: the brain's questions among the head's
    inputs (INS_BQ). quiet: the third choice (the instruction asks for quiet movement: one logit beside the weapon's)"""
    ms, bq = (INS_MS if ms else 0), (INS_BQ if bq else 0)
    return dict(L, widths=dict(L["widths"], ins=ins_u_width(int(xf) + ms, bq)), on=dict(L["on"], ins=1),
                ins=dict(xf=int(xf) + ms, fx=int(xf), ms=ms, bq=bq, nw=int(nw), c=int(c), hid=int(hid), a=INS_A, size=int(L["size"]),
                         quiet=int(bool(quiet))))


def has_ins(L):
    return bool(L is not None and L.get("ins")) and int(L["widths"].get("ins", 0)) > 0


INS_LAYERS = ("ins_is", "ins_ix", "ins_ia", "ins_iv", "ins_ws", "ins_wx", "ins_wv", "ins_qv", "ins_vv")


def has_ins_layers(mod):
    """the head's module has the instruction's scorer (a layout with "ins")"""
    return mod is not None and hasattr(mod, "ins_iv")


def ins_params(mod):
    """the scorer's own parameters (the optimizer's group "ins")"""
    return [p_ for n_, p_ in mod.named_parameters() if n_.startswith("ins_")]


def _neg(x):
    import torch
    return torch.finfo(x.dtype).min / 4


def ins_scores(m, s, X, A, ok):
    """the rows' scores [..., C] from the head's state s [..., size] AS GIVEN (a number in the rollout; the re-run state with its
    gradient in the learning step), the rows X [..., C, xf], their forecasts A [..., C, INS_A] and which the map offers ok [..., C]
    (not offered: never). m: the head's module"""
    import torch
    g = m.ins_iv(torch.tanh(m.ins_is(s.float())[..., None, :] + m.ins_ix(X.float()) + m.ins_ia(A.float()))).squeeze(-1)
    return torch.where(ok, g, torch.full_like(g, _neg(g)))


def ins_wscores(m, s, x, wok):
    """the weapons' scores [..., nw] for the chosen row x [..., xf] (a weapon he cannot use: never)"""
    import torch
    g = m.ins_wv(torch.tanh(m.ins_ws(s.float()) + m.ins_wx(x.float())))
    return torch.where(wok, g, torch.full_like(g, _neg(g)))


def has_quiet(m):
    return m is not None and hasattr(m, "ins_qv")


def ins_qlogit(m, s, x):
    """the logit of asking for quiet movement [...] with the chosen row x [..., xf]"""
    import torch
    return m.ins_qv(torch.tanh(m.ins_ws(s.float()) + m.ins_wx(x.float()))).squeeze(-1)


def ins_live(ok, wok):
    """a seat's reading can be a choice: a row is offered and a weapon usable [...]"""
    return ok.any(-1) & wok.any(-1)


def ins_row_logp(m, s, X, A, ok, live):
    """THE rows' log-probabilities [..., C] (the rollout draws from them and stores the drawn row's; the learning step recomputes
    them here): log-softmax of the scores over the offered rows; a seat that is not live: every row alike (it is never his own)"""
    import torch
    z = ins_scores(m, s, X, A, ok).float()
    return torch.log_softmax(torch.where(live[..., None], z, torch.zeros_like(z)), -1)


def ins_wq_logp(m, s, x, wok, live):
    """THE weapon's log-probabilities [..., nw] for the chosen row x, and the quiet logit [...] (None for a head without it)"""
    import torch
    z = ins_wscores(m, s, x, wok).float()
    lw = torch.log_softmax(torch.where(live[..., None], z, torch.zeros_like(z)), -1)
    return lw, (ins_qlogit(m, s, x).float() if has_quiet(m) else None)


def ins_joint_logp(lr, lw, qz, c, w, q=None):
    """THE log-probability [...] of what was drawn: the row c, its weapon w and, where quiet is a choice (q given, qz the logit),
    quiet asked or not"""
    import torch
    lp = lr.gather(-1, c[..., None]).squeeze(-1) + lw.gather(-1, w[..., None]).squeeze(-1)
    if q is not None and qz is not None:
        lp = lp + torch.nn.functional.logsigmoid(torch.where(q > 0, qz, -qz))
    return lp


def ins_dv(A, long_w):
    """the lesson's number of a forecast [..., INS_A]: (1 - long_w) x dV over 8 s + long_w x dV over the long window"""
    return (1.0 - float(long_w)) * A[..., INS_DV] + float(long_w) * A[..., INS_DVL]


def ins_target(dv, ok, temp):
    """the lesson's target over the rows: softmax(the appraisals' dV / temp) over the offered rows [..., C] (a number); a seat with
    no row offered: zeros"""
    import torch
    z = torch.where(ok, dv.float() / max(1e-6, float(temp)), torch.full_like(dv.float(), _neg(dv.float())))
    p = torch.softmax(z, -1)
    return (p * ok.float()).detach() * ok.any(-1, keepdim=True).float()


def ins_u(xsel, a_then, a_now, sig, age, has, bq=None):
    """the part "ins" of the head's input [n, ins_u_width]: zeros for a seat under none; then the brain's questions bq [n, INS_BQ]
    (a layout with them), read by every seat"""
    import torch
    f = has.float()[:, None]
    u = torch.cat([xsel.float(), a_then.float(), a_now.float(), sig.float(), (age.float() / 10.0).clamp(max=2.0)[:, None],
                   torch.ones_like(f)], 1) * f
    return u if bq is None else torch.cat([u, bq.float()], 1)


def np_brain_unsure(zone=None, ah=None, n=None):
    """how sure the brain is (piece 2), from its own readouts at a tick, no lesson of its own: zone [n, Z] the odds over the map's
    zones (zeros past the map's count; None: none) -> their entropy over its largest (0: one zone holds it all, 1: every zone alike);
    ah [n, 15 or more] the readout ahead's outputs (5 numbers a horizon, the first three his place in thousands of units; None:
    none) -> the mean distance between its places 1, 2 and 4 s ahead, in thousands of units, at most 2 -> (uz [n], us [n])"""
    m = len(zone) if zone is not None else (len(ah) if ah is not None else int(n or 0))
    uz, us = np.zeros(m, np.float32), np.zeros(m, np.float32)
    if zone is not None:
        p = np.asarray(zone, np.float64)
        k = (p > 0).sum(1)
        h = -(np.where(p > 0, p * np.log(np.maximum(p, 1e-300)), 0.0)).sum(1)
        uz = np.where(k > 1, h / np.log(np.maximum(k, 2)), 0.0).astype(np.float32)
    if ah is not None:
        f = np.asarray(ah, np.float64)[:, :15].reshape(-1, 3, 5)[:, :, :3]
        d = (np.linalg.norm(f[:, 0] - f[:, 1], axis=1) + np.linalg.norm(f[:, 0] - f[:, 2], axis=1) + np.linalg.norm(f[:, 1] - f[:, 2], axis=1)) / 3.0
        us = np.minimum(d, 2.0).astype(np.float32)
    return uz, us


def np_ins_fill(X, ok, fill, known=None, unsure=None, spodds=None, cspawn=None, ms=None):
    """the candidates' rows as the scorer and the appraisals read them: X [n, C, fx] as the simulator gives them (its columns
    fill["known"], fill["unsure"], fill["spawn_odds"] left at zero), ok [n, C] the rows the map offers. Written into every offered
    row: known [n] the chance the enemy knows where he is; unsure [n] the spread of the brain's zone odds; into the spawn rows
    (cspawn [n, C] their spawn point, -1: not one) spodds [n, smax] the brain's odds of that point. ms [n, C, 8]: the map sense at
    each row's place, appended after the row's own numbers. A part None: left as it is (zeros). -> [n, C, fx (+ 8)] float16"""
    X = np.array(X, np.float32, copy=True)
    okf = np.asarray(ok, bool)
    if known is not None and "known" in fill:
        X[:, :, int(fill["known"])] = np.asarray(known, np.float32)[:, None] * okf
    if unsure is not None and "unsure" in fill:
        X[:, :, int(fill["unsure"])] = np.asarray(unsure, np.float32)[:, None] * okf
    if spodds is not None and cspawn is not None and "spawn_odds" in fill:
        cs = np.asarray(cspawn, np.int64)
        m = (cs >= 0) & okf & (cs < np.asarray(spodds).shape[1])
        r, c = np.nonzero(m)
        X[r, c, int(fill["spawn_odds"])] = np.asarray(spodds, np.float32)[r, cs[r, c]]
    if ms is not None:
        X = np.concatenate([X, np.asarray(ms, np.float32) * okf[:, :, None]], 2)
    return X.astype(np.float16)


def ins_loss(m, s, B, teach_w, pg_w, ent_w, clip=0.2):
    """the head's instruction terms at kept readings, from the head's state s [..., size] AS GIVEN: the learning step gives the
    re-run state (seq's s_held at the readings' frames) with its gradient, so the terms reach the scorer AND the head's memory and
    input layer. B (tensors with s's leading shape):
      X [..., C, xf], A [..., C, INS_A], ok [..., C], wok [..., nw], xw [..., xf] (the drawn row), c, w [...], q [...] (where quiet
      is a choice), lp [...] the log-probability as played
      ref [...]  (optional) the ratio's reference (decoupled PPO: the learner's own before the update; default: lp) and isw [...]
                 (optional) its capped importance weights
      own [...]  the reading's choice was the head's own and was played (not a drill's, not a forced branch's, not kept from before)
      adv [...]  the head's advantage at the reading's frame (a number; normalised here over his own readings)
      tq [..., C], tm [...]   the lesson's target over the rows (ins_target) and where it may teach (the appraisals warm, a live
                 seat, not a drill's nor a forced one); tw [..., nw], twm [...] the same for the weapon of the drawn row;
                 tqq [...] the chance quiet should be asked (with q)
      em [...]   (optional) where the entropy bonus counts (default: the live seats)
    teach_w x the cross-entropies toward the targets + pg_w x the PPO-clipped surrogate on his own readings (the second clip as
    the target's: a bad choice's ratio counts at most 3) - ent_w x the rows' entropy.
    -> (the loss: a plain zero without a gradient where nothing counts, a dict: lp (now, a number), lr (the rows' log-probabilities,
    a number), live, and the three terms' values)"""
    import torch
    F_ = torch.nn.functional
    ok, wok = B["ok"], B["wok"]
    live = ins_live(ok, wok)
    lr = ins_row_logp(m, s, B["X"], B["A"], ok, live)
    lw, qz = ins_wq_logp(m, s, B["xw"], wok, live)
    q = B.get("q")
    lp = ins_joint_logp(lr, lw, qz, B["c"], B["w"], q)
    lr0, lw0 = torch.where(ok, lr, torch.zeros_like(lr)), torch.where(wok, lw, torch.zeros_like(lw))
    tm, twm, own = B["tm"].float(), B["twm"].float(), B["own"].float()
    loss = lr.new_zeros(())
    out = dict(lp=lp.detach(), lr=lr.detach(), live=live, teach=0.0, pg=0.0, ent=0.0)
    if teach_w > 0 and float(tm.sum() + twm.sum()) > 0:
        t_ = (-(B["tq"] * lr0).sum(-1) * tm).sum() / tm.sum().clamp(min=1.0) + (-(B["tw"] * lw0).sum(-1) * twm).sum() / twm.sum().clamp(min=1.0)
        if qz is not None and q is not None and "tqq" in B:  # quiet: toward the chance the appraisals' two forecasts (asked, not asked) give
            t_ = t_ + (F_.binary_cross_entropy_with_logits(qz, B["tqq"].float(), reduction="none") * twm).sum() / twm.sum().clamp(min=1.0)
        loss = loss + float(teach_w) * t_
        out["teach"] = float(t_.detach())
    if pg_w > 0 and float(own.sum()) > 0:
        n_ = own.sum().clamp(min=1.0)
        ad = B["adv"].float()
        mu = (ad * own).sum() / n_
        ad = (ad - mu) / (((ad - mu).pow(2) * own).sum() / n_).sqrt().clamp(min=1e-8)
        ratio = torch.exp((lp - B.get("ref", B["lp"]).float()).clamp(-20.0, 20.0))
        sur = torch.min(ratio * ad, ratio.clamp(1.0 - clip, 1.0 + clip) * ad)
        sur = torch.where(ad < 0, torch.max(sur, 3.0 * ad), sur)
        p_ = -((B["isw"].float() if "isw" in B else 1.0) * sur * own).sum() / n_
        loss = loss + float(pg_w) * p_
        out["pg"] = float(p_.detach())
    em = B["em"].float() if "em" in B else live.float()
    if ent_w > 0 and float(em.sum()) > 0:
        e_ = ((-(lr0.exp() * lr0).sum(-1)) * em).sum() / em.sum().clamp(min=1.0)
        loss = loss - float(ent_w) * e_
        out["ent"] = float(e_.detach())
    return loss, out


def ins_counts(B, out, teachable=None):
    """the record's counters of a batch of kept readings (numbers; before a step): rows, his own, taught, the rows' entropy summed
    over the live seats and their count, the distance to the appraisals' order (KL summed, how often the best row agrees), rows offered"""
    import torch
    lr, ok = out["lr"], B["ok"]
    lr0 = torch.where(ok, lr, torch.zeros_like(lr))
    live = out["live"].float()
    tm = (B["tm"] if teachable is None else teachable).float()
    ent = -(lr0.exp() * lr0).sum(-1)
    ce = -(B["tq"] * lr0).sum(-1)
    ent_t = -(B["tq"] * torch.log(B["tq"].clamp(min=1e-12))).sum(-1)
    return dict(rows=float(live.numel()), own=float(B["own"].float().sum()), teach=float(tm.sum()), ent=float((ent * live).sum()),
                n_ok=float(live.sum()), kl=float(((ce - ent_t) * tm).sum()), agree=float(((lr.argmax(-1) == B["tq"].argmax(-1)).float() * tm).sum()),
                offered=float(ok.float().sum()))


def ins_learn(m, opt, B, lr, dev, gen, teach_w, pg_w, ent_w, clip=0.2, mb=8192, epochs=2):
    """(the unit tests and offline fits; the TRAINER does not use this: its lesson is ins_loss inside the head's own terms) the same
    terms on a flat batch B of kept readings whose head states are given as numbers B["s"] [R, size]: steps of opt on m's
    parameters. -> ins_counts() before any step"""
    import torch
    n = 0 if B is None else len(B["c"])
    if not n:
        return {}
    keys = [k_ for k_ in ("X", "A", "ok", "wok", "xw", "c", "w", "q", "lp", "ref", "isw", "own", "adv", "tq", "tm", "tw", "twm", "tqq", "em") if k_ in B]
    sub = lambda i_: {k_: B[k_][i_].to(dev) for k_ in keys}    # noqa: E731
    with torch.no_grad():
        acc = None
        for b in range(0, n, mb):
            i_ = torch.arange(b, min(n, b + mb))
            Bi = sub(i_)
            c_ = ins_counts(Bi, ins_loss(m, B["s"][i_].to(dev).float(), Bi, 0.0, 0.0, 0.0)[1])
            acc = c_ if acc is None else {k_: acc[k_] + c_[k_] for k_ in acc}
    if lr <= 0 or (teach_w <= 0 and pg_w <= 0):
        return acc
    for g_ in opt.param_groups:
        g_["lr"] = float(lr)
    for _ in range(int(epochs)):
        pm = torch.randperm(n, generator=gen)
        for b in range(0, n, mb):
            i_ = pm[b:b + mb]
            loss, _o = ins_loss(m, B["s"][i_].to(dev).float(), sub(i_), teach_w, pg_w, ent_w, clip)
            if not loss.requires_grad:
                continue
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step()
    return acc


def ins_record(acc, play, L, g, teach_w, pg_w, temp, warm):
    """-> metrics.jsonl's "ins": the share played; the lesson's counters (before the step): the rows' entropy, the distance to the
    appraisals' order (KL, and how often the best row is the same); what was played, by verb and by weapon (`play`: counters of
    the rollout: ticks by verb [8], by weapon [nw], picks, re-decisions, seat-seconds, the chosen rows' forecast dV and what the
    head's value then said they brought)"""
    rec = dict(g=round(float(g), 4), teach=round(float(teach_w), 4), pg=round(float(pg_w), 4), temp=round(float(temp), 4), warm=bool(warm))
    if acc and acc.get("rows"):
        r_, t_, k_ = float(acc["rows"]), max(1.0, float(acc["teach"])), max(1.0, float(acc["n_ok"]))
        rec.update(rows=int(r_), own=int(acc["own"]), taught=int(acc["teach"]), entropy=round(float(acc["ent"]) / k_, 4),
                   offered=round(float(acc["offered"]) / r_, 2), kl_to_appraisals=round(float(acc["kl"]) / t_, 4),
                   best_row_agrees=round(float(acc["agree"]) / t_, 4))
    if play:
        v_, w_ = np.asarray(play["verb"], np.float64), np.asarray(play["weapon"], np.float64)
        rec["verbs"] = [round(float(x), 4) for x in (v_ / max(1.0, v_.sum()))]
        rec["weapons"] = [round(float(x), 4) for x in (w_ / max(1.0, w_.sum()))]
        rec["picks"] = int(play["picks"])
        if play.get("block") is not None:                      # by the simulator's row blocks (the spawn rows apart from push and spam)
            b_ = np.asarray(play["block"], np.float64)
            rec["row_blocks"] = {str(k_): round(float(x_) / max(1.0, b_.sum()), 4) for k_, x_ in zip(play["block_names"], b_)}
        if play.get("quiet") is not None:                      # quiet asked: the share of the picks, by verb
            q_ = np.asarray(play["quiet"], np.float64)
            rec["quiet"] = round(float(q_.sum()) / max(1.0, float(play["picks"])), 4)
            rec["quiet_by_verb"] = [round(float(a_) / max(1.0, float(b_)), 4) for a_, b_ in zip(q_, v_)]
        rec["changes_a_second"] = round(float(play["picks"]) / max(1e-9, float(play["secs"])), 4)
        if play.get("cal_n", 0) > 1:                           # the chosen rows' forecast against what they brought
            n_ = float(play["cal_n"])
            mf, mg = play["cal_f"] / n_, play["cal_g"] / n_
            cov = play["cal_fg"] / n_ - mf * mg
            vf, vg = play["cal_ff"] / n_ - mf * mf, play["cal_gg"] / n_ - mg * mg
            rec["forecast_dv"], rec["brought_dv"] = round(mf, 4), round(mg, 4)
            rec["forecast_corr"] = round(cov / math.sqrt(vf * vg), 4) if vf > 0 and vg > 0 else None
    return rec


def np_ins_params(sd):
    """the scorer's weights as numpy under their short names (is_.weight, ix.weight, ia.weight, iv.weight, ws, wx, wv, qv, ins_g),
    from the head's module's state dict (ins_is.weight ...), the whole network's (head2.ins_is.weight ...) or a dict that has the
    short names already (an export's "ins.*" arrays)"""
    out = {}
    for k, v in sd.items():
        k = str(k)
        if k.startswith("head2."):
            k = k[len("head2."):]
        if k.startswith("ins_"):
            k = "ins_g" if k == "ins_g" else ("is_." + k[len("ins_is."):] if k.startswith("ins_is.") else k[len("ins_"):])
        elif not k.startswith(("is_.", "ix.", "ia.", "iv.", "ws.", "wx.", "wv.", "qv.")):
            continue
        out[k] = (v.detach().cpu().numpy() if hasattr(v, "detach") else np.asarray(v)).astype(np.float32)
    return out


def _np_log_softmax(z):
    z = np.asarray(z, np.float64)
    z = z - z.max(-1, keepdims=True)
    return z - np.log(np.exp(z).sum(-1, keepdims=True))


def np_ins_row_logp(W, s, X, A, ok, live):
    """ins_row_logp in numpy -> [m, C] float64 (the checks' player and the plugin draw from exp of it)"""
    z = np_ins_scores(W, s, X, A, ok).astype(np.float64)
    return _np_log_softmax(np.where(np.asarray(live, bool)[:, None], z, 0.0))


def np_ins_wq_logp(W, s, x, wok, live):
    """ins_wq_logp in numpy -> (the weapon's log-probabilities [m, nw] float64, the quiet logit [m] or None)"""
    z = np_ins_wscores(W, s, x, wok).astype(np.float64)
    qz = None
    if "qv.weight" in W:
        qz = (np.tanh(s @ W["ws.weight"].T + W["ws.bias"] + x @ W["wx.weight"].T + W["wx.bias"]) @ W["qv.weight"].T + W["qv.bias"])[:, 0]
    return _np_log_softmax(np.where(np.asarray(live, bool)[:, None], z, 0.0)), qz


def np_ins_scores(W, s, X, A, ok):
    """ins_scores in numpy -> [m, C] (not offered: a large negative number)"""
    g = (np.tanh((s @ W["is_.weight"].T + W["is_.bias"])[:, None, :] + X @ W["ix.weight"].T + W["ix.bias"] + A @ W["ia.weight"].T + W["ia.bias"])
         @ W["iv.weight"].T + W["iv.bias"])[..., 0]
    return np.where(ok, g, np.float32(-1e30)).astype(np.float32)


def np_ins_wscores(W, s, x, wok):
    g = np.tanh(s @ W["ws.weight"].T + W["ws.bias"] + x @ W["wx.weight"].T + W["wx.bias"]) @ W["wv.weight"].T + W["wv.bias"]
    return np.where(wok, g, np.float32(-1e30)).astype(np.float32)


def np_ins_u(xsel, a_then, a_now, sig, age, has, bq=None):
    f = np.asarray(has, np.float32)[:, None]
    u = (np.concatenate([xsel, a_then, a_now, sig, np.minimum(np.asarray(age, np.float32) / 10.0, 2.0)[:, None], np.ones_like(f)], 1) * f).astype(np.float32)
    return u if bq is None else np.concatenate([u, np.asarray(bq, np.float32)], 1)


def ins_held_width(I):
    """a seat's held numbers of his instruction (the checks' player, the plugin): the row (xf), its forecast then and now, the six
    change signals, the weapon, how long, on one, the coin; then the brain's questions (a layout with them)"""
    return int(I["xf"]) + 2 * INS_A + INS_SIG + 4 + int(I.get("bq", 0) or 0)


def np_ins_held_u(I, st):
    """the part "ins" of the head's input from the held numbers st [m, ins_held_width] (np_ins_u)"""
    F_ = int(I["xf"])
    o = F_ + 2 * INS_A + INS_SIG
    nb = int(I.get("bq", 0) or 0)
    return np_ins_u(st[:, :F_], st[:, F_:F_ + INS_A], st[:, F_ + INS_A:F_ + 2 * INS_A], st[:, F_ + 2 * INS_A:o], st[:, o + 1], st[:, o + 2] > 0.5,
                    st[:, o + 4:o + 4 + nb] if nb else None)


def np_ins_prep(ixs, fill, I, sb, hh, zone=None, ah=None, knP=None, spP=None, ms=None):
    """(the checks' player, the plugin: the trainer's ins_prep in numpy) the candidates of these seats as the scorer and the
    appraisals read them. ixs: sim/branch.py worker_feat's fields for these seats (X, ok, wok, sig, drill, row, forced, each row's
    spawn point, its place, has one, the weapon in his hand, the map's spawn points' count); sb [m, bel] the brain's state, hh
    [m, mem] the hands' memory; zone [m, Z] the brain's zone odds and ah [m, 15+] its readout ahead (None: none); knP / spP the
    readouts' arrays (sim/knownodds.py, sim/spawnodds.py np_params; None: the network has none); ms: None, or a function
    (P [m, C, 3], pk [m, C], weapon [m]) -> [m, C, 8] the map sense at the rows' places (a layout with it and no function: zeros)
    -> (X [m, C, xf] float32, bq [m, INS_BQ])"""
    ok = np.asarray(ixs[1], bool)
    m = len(ok)
    known = spo = msr = None
    bq = np.zeros((m, INS_BQ), np.float32)
    if knP is not None:
        import knownodds as knownodds_
        known = knownodds_.np_chance(knP, sb, hh)[:, 0]
        bq[:, 0] = known - 0.5
    uz, us = np_brain_unsure(zone, ah, m)
    bq[:, 1], bq[:, 2] = uz, us
    if spP is not None and len(ixs) > 11:
        import spawnodds as spawnodds_
        spo = spawnodds_.np_odds(spP, sb, hh, np.asarray(ixs[11], np.int64))
    if int(I.get("ms", 0) or 0):
        msr = np.zeros(ok.shape + (INS_MS,), np.float32)
        if ms is not None and len(ixs) > 10:
            msr = np.asarray(ms(np.asarray(ixs[8], np.float32), np.asarray(ixs[9], bool) & ok, np.asarray(ixs[10], np.int64)), np.float32)
    X = np_ins_fill(ixs[0], ok, fill or {}, known=known, unsure=uz, spodds=spo, cspawn=ixs[7] if len(ixs) > 7 else None, ms=msr)
    return X.astype(np.float32), bq


def np_ins_read(I, Wi, aprL, aprP, warm, g, none_row, every, st, s_head, sit, X, ok, wok, sg, dr, cur, frc, redo, rng, bq=None):
    """a reading of these seats in numpy (the trainer's rollout's sums; one definition for the checks' player and the plugin):
    st [m, ins_held_width] their held numbers, s_head [m, size] the head's state this frame's outputs read, sit [m, bel + mem +
    size] the appraisals' situation, X [m, C, xf] the rows (np_ins_prep), ok, wok, sg [m, 6+], dr (in a drill), cur (the row he is
    on), frc (forced), redo [m] (the keep choice says re-decide; all True without one), rng: the scorer's own stream (the draws in
    this order: the row, the weapon, quiet, the coin), bq [m, INS_BQ] or None.
    -> (the new held numbers, (c, w, who, q): the picks for env.instr_pick: c and w -1 where he is cleared or keeps his own)"""
    import appraise as appraise_
    F_, NA_ = int(I["xf"]), INS_A
    o_i = F_ + 2 * NA_ + INS_SIG
    m = len(st)
    ar_ = np.arange(m)
    X = np.asarray(X, np.float32)
    xh, ath = st[:, :F_], st[:, F_:F_ + NA_]
    wh, age, has, own = st[:, o_i].astype(np.int64), st[:, o_i + 1], st[:, o_i + 2] > 0.5, st[:, o_i + 3] > 0.5
    any_ = ok.any(1) & wok.any(1)
    A_ = appraise_.np_forecast_rows(aprP, aprL, sit, X) if warm else np.zeros(X.shape[:2] + (NA_,), np.float32)
    A_ = np.asarray(A_, np.float32).astype(np.float16).astype(np.float32)    # (read at half precision, as the trainer keeps them for its lesson)

    def pick_i(lp_):                                         # a draw from the one definition's log-probabilities
        p_ = np.exp(lp_)
        return np.minimum((p_.cumsum(1) < rng.random((len(p_), 1))).sum(1), p_.shape[1] - 1).astype(np.int64)
    cn_ = pick_i(np_ins_row_logp(Wi, s_head, X, A_, ok, any_))
    xs_ = X[ar_, cn_]
    lw_, qz_ = np_ins_wq_logp(Wi, s_head, xs_, wok, any_)
    wn_ = pick_i(lw_)
    qn_ = np.zeros(m, np.int64)                              # (quiet movement: the third draw, where the head has the logit)
    if qz_ is not None:
        qn_ = (rng.random(m) < 1.0 / (1.0 + np.exp(-qz_))).astype(np.int64)
    own = np.where(has, own, rng.random(m) < float(g))       # (the coin of a seat under none: anew at the share)
    on_ = (cur >= 0) & (cur != int(none_row))
    end_ = ins_end(sg)                                       # done, failed, or a wake (the pain sound, the believed stack fallen)
    rd_ = ~on_ | end_ | np.asarray(ins_redo(age, every), bool)     # (2.1a) drawn anew a second after its last draw (ins_redo; `redo`, the keep
    #                                                          choice's draw, is no longer read: see there)
    pk_ = own & any_ & rd_ & ~dr & ~frc
    cl_ = on_ & ~own & ~dr & ~frc
    xh, wh = np.where(pk_[:, None], xs_, xh), np.where(pk_, wn_, wh)
    ath = np.where(pk_[:, None], A_[ar_, cn_], ath)
    age = np.where(pk_, 0.0, age + float(every) * 0.025)
    has = ((pk_ & (cn_ != int(none_row))) | (has & on_ & ~pk_)) & ~cl_
    anow = np.zeros((m, NA_), np.float32)
    if warm and has.any():
        anow[has] = appraise_.np_forecast_rows(aprP, aprL, sit[has], xh[has][:, None, :], wh[has][:, None])[:, 0]
    out = [xh, ath, anow, sg[:, :INS_SIG], wh[:, None], age[:, None], has[:, None], own[:, None]]
    if int(I.get("bq", 0) or 0):
        out.append(np.zeros((m, INS_BQ), np.float32) if bq is None else np.asarray(bq, np.float32))
    return np.concatenate(out, 1).astype(np.float32), (np.where(pk_, cn_, -1), np.where(pk_, wn_, -1), pk_ | cl_, np.where(pk_, qn_, 0))


class InsState:
    """(2.1) the trainer's rollout: every seat's instruction as the head last gave it (the row's numbers, its weapon, its forecast
    then and now, how long), the simulator's change signals, and the coin (the seat's instruction is the head's)"""

    def __init__(self, n, I, dev):
        import torch
        F_ = int(I["xf"])
        self.xh = torch.zeros(n, F_, device=dev)
        self.wh = torch.zeros(n, dtype=torch.long, device=dev)
        self.qh = torch.zeros(n, dtype=torch.long, device=dev)   # (quiet movement asked with it)
        self.ath = torch.zeros(n, INS_A, device=dev)
        self.anow = torch.zeros(n, INS_A, device=dev)
        self.sig = torch.zeros(n, INS_SIG, device=dev)
        self.age = torch.zeros(n, device=dev)
        self.has = torch.zeros(n, dtype=torch.bool, device=dev)
        self.own = torch.zeros(n, dtype=torch.bool, device=dev)
        self.bq = torch.zeros(n, INS_BQ, device=dev) if int(I.get("bq", 0) or 0) else None    # (the brain's questions, as last asked)

    def u(self):
        return ins_u(self.xh, self.ath, self.anow, self.sig, self.age, self.has, self.bq)

    def reset(self, d, g, gen):
        """a round's end (d [n], 1: ended): no instruction; the seat's coin drawn anew at the share g"""
        import torch
        e = d > 0.5
        if bool(e.any()):
            self.has = self.has & ~e
            self.age = torch.where(e, torch.zeros_like(self.age), self.age)
            coin = torch.rand(len(d), generator=gen, device=d.device) < float(g)
            self.own = torch.where(e, coin, self.own)

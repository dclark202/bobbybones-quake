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
PARTS = ("brain", "trk", "trz", "ahead", "ctrl", "obs", "hands", "wobs")   # (1.5a) wobs: the weapon part's inputs (a layout without: 0 wide)
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
           n_target=17, every=8, gamma=0.9998, chrono=300, on=None, ctrl_src="none", chrono_lo=0.0):
    """the part's shape; kept in a checkpoint as "head2" (the gate is the state dict's head2.gate). obs: the input columns
    (obs_cols()); on: {part: 0 or 1} (default all on; a part off reads zeros)"""
    obs = [int(c) for c in (obs if obs is not None else obs_cols())]
    on_ = {p: 1 for p in PARTS}
    on_.update({str(k): int(v) for k, v in (on or {}).items()})
    w = dict(brain=int(brain), trk=int(trk), trz=int(trz), ahead=int(ahead), ctrl=int(ctrl), obs=len(obs), hands=int(hands))
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
        ((S * 2 + 2) if L.get("fire") else 0)


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
            super()._load_from_state_dict(state_dict, prefix, *args, **kw)

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(int(seed))
        return Head2()


def feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None):
    """u [B, u_width] (float32 holding half-precision numbers) from the parts (a part None or off: zeros). obs: his
    normalised inputs [B, all inputs] (the columns are taken here)"""
    import torch
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands, wobs=obs)
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
        if p in ("trk", "trz", "ahead", "ctrl"):
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


def np_feats(L, brain=None, trk=None, trz=None, ahead=None, ctrl=None, obs=None, hands=None):
    """feats() in numpy"""
    src = dict(brain=brain, trk=trk, trz=trz, ahead=ahead, ctrl=ctrl, obs=obs, hands=hands, wobs=obs)
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
        if p in ("trk", "trz", "ahead", "ctrl"):
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

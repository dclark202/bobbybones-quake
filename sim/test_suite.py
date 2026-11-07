"""Standard test rooms for a duel policy: the same rooms, seeds and targets every time, one scorecard.

    python sim/test_suite.py --run duel_gru_v3                      # full card, three maps
    python sim/test_suite.py --run duel_gru_v3 --compare data/sim_runs/duel_gru_v3/suite/card_0120.json
    python sim/test_suite.py --run duel_gru_v3 --quick              # one map, short rooms (smoke test)

Rooms (the subject is the even player of every match; the odd player is scripted or absent):
  aim/<weapon>/<target>      one weapon, scripted target that never shoots, 350-650 units away.
                             targets: still, slow (about 1/3 run speed), fast (full-speed strafe), jump
  aim/<weapon>/fast@close|far  the main three weapons against the fast target at 150-300 and 800-1200 units
  choice/close|mid|far       every weapon in hand, fast target at that distance: which weapon is held
  move                       no opponent: run to mega / red / yellow armor (arrivals, speed)
  solo                       alone with weapons for two minutes: items collected, firing at nothing
  ladder/<style>             duel against each scripted fighter style (allround, sniper, rusher, tracker, dodger,
                             and the deliberately bad ones: stander, jumper, spammer)
Metrics are per subject. Cards are saved as JSON + markdown in data/sim_runs/<run>/suite/.
The same room names are used by the play-test server (plugins/duelbot.py, !room) for a human baseline.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
MAPS = ("bloodrun", "aerowalk", "lostworld")
SUITE_VERSION = 1


class WeaponPush:
    """(1.7c experiments, 2026-11-07) a fixed push on the weapon key's logits toward the pros' weapon in hand, in the checks only
    (tools/duel_eval.py --wpush): the trainer's habit seats' "pro" kind (sim/train_duel_rnn.py habit_push, 1.5a part C). With the
    enemy noticed in view: p x the pros' share in hand at that distance (docs/pro_tables.json, bins of 50 units); out of view: p x
    their travelling hand (sim/pro_hand.json, the four bands weighted by their minutes); each share among rockets, rail and the
    lightning gun he owns with ammunition, on those three keys (the key: 0 keep, then 1 + the weapon's index). Nothing else moves.
      p      the push (the habit seats': 2)
      names  the network's input names, its columns in order (duel_eval's `old`)
      form   "share" (above: every press of the three raised by p x the pros' share, so in view the lightning gun's about as much as
             rockets'; it moved his hand 20 -> 22% at p 2) or "ratio" (by the weapon he holds: a press of weapon j gets
             p x (log s_j - log s_held), the pros' shares floored at 0.03; plus where they prefer j to what he holds, minus where
             less, nothing for the one in hand; holding none of the three: against the mean of the owned ones' logs) or "dial" (the
             ratio form on the owner's table instead of the pros': sim/weapon_dial.py, the servers' !weapons)"""

    def __init__(self, p, names, form="share"):
        self.p = float(p)
        assert form in ("share", "ratio", "dial"), form
        self.form = form
        if form == "dial":                                   # (owner, 2026-11-07) the owner's table: sim/weapon_dial.py, as the servers run it
            return                                           # (no module kept on self: the checks' pools pickle the policy)
        ix = {(n_[1] if isinstance(n_, (tuple, list)) else n_): i_ for i_, n_ in enumerate(names)}   # (duel_eval's names: (group, input))
        self.hold = [ix["holding " + n_] for n_ in ("rocket launcher", "railgun", "lightning gun")]
        self.inv = ix["noticed in view"]
        self.pos = [ix["last known position: " + d_] for d_ in ("forward", "left", "up")]
        self.own = [ix["owns " + n_] for n_ in ("rocket launcher", "railgun", "lightning gun")]
        self.ammo = [ix["ammo: " + n_] for n_ in ("rocket launcher", "railgun", "lightning gun")]
        pt_ = json.load(open(os.path.join(ROOT, "docs", "pro_tables.json"), encoding="utf-8"))["all"]
        self.tin = np.stack([np.asarray(pt_["in_hand_by_distance"][w_], np.float64) for w_ in ("rl", "rg", "lg")], 1)
        ph_ = json.load(open(os.path.join(HERE, "pro_hand.json"), encoding="utf-8"))
        sh_ = np.asarray(ph_["maps"]["all"]["share"][0], np.float64)[:, :3]
        mn_ = np.asarray(ph_["maps"]["all"]["minutes"][0], np.float64)
        self.tout = (sh_ * mn_[:, None]).sum(0) / mn_.sum()

    def __call__(self, obs):
        """obs [B, his inputs] raw -> [B, 3] the adds on the keys of rockets, rail, lightning"""
        if self.form == "dial":
            import weapon_dial
            return weapon_dial.push(obs, self.p)
        own_ = (obs[:, self.own] > 0.5) & (obs[:, self.ammo] > 0.0)
        d_ = 1000.0 * np.sqrt((obs[:, self.pos].astype(np.float64) ** 2).sum(1))
        bin_ = np.clip((d_ // 50.0).astype(np.int64), 0, len(self.tin) - 1)
        if self.form == "ratio":
            lp_ = np.log(np.maximum(np.where((obs[:, self.inv] > 0.5)[:, None], self.tin[bin_], self.tout[None, :]), 0.03))
            hd_ = obs[:, self.hold] > 0.5
            no_ = own_.sum(1)
            ref_ = np.where(hd_.any(1), (lp_ * hd_).sum(1), (lp_ * own_).sum(1) / np.maximum(no_, 1))
            return (self.p * (lp_ - ref_[:, None]) * own_).astype(np.float32)
        sh_ = np.where((obs[:, self.inv] > 0.5)[:, None], self.tin[bin_], self.tout[None, :]) * own_
        tot_ = sh_.sum(1)
        b_ = np.zeros((len(obs), 3), np.float32)
        ok_ = tot_ > 0
        b_[ok_] = (self.p * sh_[ok_] / tot_[ok_, None]).astype(np.float32)
        return b_


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


class Policy:
    """a trained GRU policy in plain numpy (same maths as the game-server plugin)"""

    def __init__(self, path, seed=0):
        import torch
        ck = torch.load(path, weights_only=False, map_location="cpu")
        sd = {k: v.cpu().numpy() for k, v in ck["model"].items()}
        self.w0, self.b0, self.w1, self.b1 = sd["enc.0.weight"], sd["enc.0.bias"], sd["enc.2.weight"], sd["enc.2.bias"]
        self.wih, self.whh, self.bih, self.bhh = sd["gru.weight_ih"], sd["gru.weight_hh"], sd["gru.bias_ih"], sd["gru.bias_hh"]
        self.wp, self.bp = sd["pi.weight"], sd["pi.bias"]
        self.cell = sd.get("cell.weight")                    # the learned map (v8): the last two inputs are cell numbers
        self.mean, self.var = ck["obs_mean"], ck["obs_var"]
        self.dims = [int(x) for x in ck["action_dims"]]
        self.minutes = float(ck.get("minutes", 0.0))
        self.react_ms = float(ck.get("react_ms", 100.0))      # (a checkpoint without it: !aim default; 150 until branch aim2)
        self.acquire_ms = float(ck.get("acquire_ms", 200.0))  # (B-226) the trainer's --acquire-ms; 200: the simulator's own
        self.round_secs = float(ck.get("round_secs") or 120.0)    # his clock, score and memory start over every this many seconds; 600: whole games, never (tools/duel_eval.py SeatClock)
        self.H = self.whh.shape[1]
        self.rng = np.random.default_rng(seed)
        self.attn = ck.get("attn")                           # (v0.2) the attention part: its layout and weights; skipped while its door is shut
        self.attP = None
        if self.attn is not None:
            import attn as attn_
            self.attn_fwd = attn_.forward_np
            self.attP = attn_.params_np(sd)
            if not np.abs(self.attP["door.weight"]).sum() > 0:
                self.attP = None
        self.btok = None                                     # (v0.4.1, sim/btoken.py) the brain's token: played only while its gate is open
        self.bgate = 0.0                                     # (gate 0: the network as it was, the brain not stepped)
        bt_ = ck.get("btoken")
        if bt_ is not None and self.attP is not None and "btok_emb.weight" in self.attP and ck.get("belief") is not None:
            import btoken as btoken_
            self.bgate = float(bt_.get("gate", 0.0))
            self.btok = bt_
            self.brainP = btoken_.numpy_brain(sd, ck["belief"], ck.get("track"), ck.get("track_z"))
        self.rf = ck.get("rule_fade")                        # (v0.4.2a, sim/rule_fade.py) the rule-made columns faded out of the hands
        self.rf_cols = np.asarray(self.rf["cols"], np.int64) if self.rf is not None else np.zeros(0, np.int64)
        self.rfg = float(self.rf.get("g", 0.0)) if self.rf is not None else 0.0
        self.rf_read = bool(self.rf.get("readers")) if self.rf is not None else False    # (BRAIN_READ in training: the simulator's
        #                                                      readers on the brain's answer: the checks give it, brain_answer())
        self.legsP = None                                    # (LEGS_IN, B-253) his legs' branch, if the network has it inside
        if "legs.0.weight" in sd:
            self.legsP = tuple(sd[k_] for k_ in ("legs.0.weight", "legs.0.bias", "legs.2.weight", "legs.2.bias", "legs.4.weight", "legs.4.bias"))
        self.uni = ck.get("legs_unify")                      # (--legs-feat, --legs-guide; sim/legs_unify.py) the parts, skipped while at zero
        self.uniD = self.uniG = None
        if self.uni is not None:
            assert self.legsP is not None, "a network with legs_unify has the legs' branch inside"
            if self.uni.get("feat") and "legs_door.weight" in sd and (np.abs(sd["legs_door.weight"]).sum() + np.abs(sd["legs_door.bias"]).sum()) > 0:
                self.uniD = (sd["legs_door.weight"], sd["legs_door.bias"])
            if self.uni.get("guide") and "legs_guide" in sd and np.abs(sd["legs_guide"]).sum() > 0:
                self.uniG = np.asarray(sd["legs_guide"], np.float32)
        self.uniT = self.uniR = None                         # (v0.3.4 A, B) the gate and motor layer; the residual: skipped while at zero
        if self.uni is not None and self.uni.get("gate") and "legs_gate.weight" in sd:
            t_ = tuple(sd[k_] for k_ in ("legs_gate.weight", "legs_gate.bias", "legs_motor.weight", "legs_motor.bias"))
            self.uniT = t_ if sum(float(np.abs(x_).sum()) for x_ in t_) > 0 else None
        if self.uni is not None and self.uni.get("residual") and "legs_res.weight" in sd:
            r_ = tuple(sd[k_] for k_ in ("legs_res_a.weight", "legs_res_a.bias", "legs_res.weight", "legs_res.bias"))
            self.uniR = r_ if sum(float(np.abs(x_).sum()) for x_ in r_) > 0 else None
        self.fade = float(ck.get("switch_fade", 0.0))        # (--switch-fade) taken off the switch's "legs" choice
        self.no_switch = str((ck.get("env_vars") or {}).get("NO_SWITCH", "0")) not in ("0", "", "0.0")   # (v0.3.5) the switch retired
        self.last_zo = None                                  # (--legs-residual) what his outputs read on the last act(), for legs_logits()
        self.slow = ck.get("slow")                           # (--slow-mem) the slow memory: its layout and weights; the memory array
        self.W = self.H                                      # a seat carries is wider (sim/slowmem.py: [fast | slow | sum | count | frames])
        if self.slow is not None:
            import slowmem as slowmem_
            self.slowP, self.slow_step, self.W = slowmem_.params_np(sd), slowmem_.np_step, slowmem_.width(self.slow)
        self.order = ck.get("ordered") or []                 # (v0.4, --ordered-heads) drawn in order, each with the one before
        self.orderT = {int(c_): sd["order.t{}.weight".format(c_)] for _, c_ in self.order}
        self.head = ck.get("head")                           # (v0.4) the head (sim/head.py): its state follows the rest of the array
        self.head_at = self.W
        if self.head is not None:
            import head as head_                             # (the module itself is not kept: a Policy goes to pool workers by pickle)
            self.headP = head_.params_np(sd)
            self.W = self.head_at + head_.np_state_width(self.head)
            o_ = np.concatenate([[0], np.cumsum(self.dims)])
            self.head_si = slice(int(o_[10]), int(o_[11]))  # the intention's logits and his way's (none before stage B)
            self.head_sw = slice(int(o_[12]), int(o_[13])) if len(self.dims) > 12 else slice(0, 0)
        self.h2 = ck.get("head2")                            # (v0.4.3, sim/head2.py) the strategy head: its state after the head's, before the brain's
        self.h2_at = self.W
        self.h2_live = False
        if self.h2 is not None:
            import head2 as head2_
            assert self.head is None, "a network with both heads: not built"
            assert self.btok is not None, "the strategy head reads the brain: a network with the brain's token (v0.4.1 on)"
            self.h2W = head2_.params_np(sd)
            self.h2_ah = head2_.mlp_of(sd, "ahead")         # (its inputs: the brain's readouts; the "in control" one if the network has it)
            self.h2_ct = head2_.np_ctrl_params(sd, self.h2)     # (the ctrl slot: the layout's "ctrl_src" readout, None: zeros)
            self.h2_fo = head2_.np_fight_params(sd, self.h2)    # (1.7b, the part fight: the fight odds readout, None: zeros)
            self.h2_live = head2_.np_open(self.h2W)          # (gate 0 or its links at zero: the network without it, not stepped)
            self.W = self.h2_at + head2_.np_state_width(self.h2)
        self.o_at = None                                     # (1.7) the combat order's held numbers a seat (head2.CMB_HELD), after the head's state
        if self.h2 is not None and self.h2.get("cmb") and "op_v.weight" in self.h2W:
            import head2 as head2_
            self.o_at = self.W
            self.W = self.o_at + head2_.CMB_HELD
        self.passL = self.passW = None                       # (1.7) the brain's pass readout (sim/passodds.py): the candidates' odds
        if ck.get("passodds") is not None and "passr.l1.weight" in sd:
            self.passL = ck["passodds"]
            self.passW = {k_[len("passr."):]: np.asarray(v_, np.float32) for k_, v_ in sd.items() if k_.startswith("passr.")}
        self.keep_g = 0.0                                    # (1.4c) the keep choice's share of his readings (the file's head2.keep_g)
        self.krng = np.random.default_rng(int(seed) + 1414)  # ... its draws: a stream of their own (the outputs' draws untouched)
        self.k_r = None                                      # (1.7a) the seats whose head ticked on the frame before (their keep reading)
        if self.h2 is not None and self.h2.get("keep") and "keep.weight" in self.h2W:
            self.keep_g = float(np.asarray(self.h2W.get("keep_g", 0.0)))
        self.cmb_g = 0.0                                     # (1.7) the combat order's share of his readings (the file's head2.cmb_g)
        if self.o_at is not None:
            self.cmb_g = float(np.asarray(self.h2W.get("cmb_g", 0.0)))
            self.h2_live = self.h2_live or self.cmb_g > 0    # (the order reads the head's state: it is stepped)
        self.fut = None                                      # (1.7) the brain's places ahead of these seats (kept at their ticks)
        self.h2_tick = None
        self.brain_at = None                                 # (v0.4.1) the brain's and the token's state, at the end of a seat's array
        if self.btok is not None:
            import btoken as btoken_
            self.brain_at = self.W
            self.W = self.brain_at + btoken_.packed_width(self.brainP["H"])

    @property
    def needs_xl(self):
        """(--legs-feat, --legs-guide) act() needs the branch's inputs (xl=, the simulator's legs_prep() of the frame)"""
        return self.uniD is not None or self.uniG is not None or self.uniT is not None

    def zeros(self, n):
        return np.zeros((n, self.W), np.float32)

    @property
    def hm(self):
        """(v0.4) sim/head.py's numpy side"""
        import head as head_
        return head_

    @property
    def brain_on(self):
        """(v0.4.1) the brain is stepped: its token is open, or (v0.4.2a) the simulator's readers take its answer (the rule
        fade above 0 in a network trained with BRAIN_READ)"""
        return self.btok is not None and (self.bgate > 0 or (self.rf_read and self.rfg > 0) or self.h2_live)

    @property
    def needs_pose(self):
        """(v0.4.1) act() needs his pose (pose=, zmap=: btoken.pose_from_env of the frame, these rows): the brain is stepped"""
        return self.brain_on

    def set_rule_fade(self, g):
        """(v0.4.2a, checks) play the rule fade at this gate (0: the network without the fade)"""
        assert g <= 0 or self.rf is not None, "this network has no rule fade"
        self.rfg = float(g)

    def brain_answer(self, h):
        """(v0.4.2a, BRAIN_READ) the brain's answer for these seats from their arrays (after act()), as the simulator's
        readers take it (duel_env.brain_in; btoken.answer_of); None while the brain is not stepped"""
        if not self.brain_on:
            return None
        import btoken as btoken_
        _, tk_ = btoken_.unpack(self.brainP, self.btok, h[:, self.brain_at:])
        d_ = btoken_.answer_of(tk_)
        if self.fut is not None and len(self.fut) == len(h):    # (1.7) the places ahead, as the trainer sends them (COMBAT)
            d_["fut"] = self.fut.copy()
        return d_

    def token_pre(self, obs, pose, zmap, hb):
        """(v0.4.1) before a frame: the brain's last answer turned to his pose now, as the trainer makes it ([B, F] float32, the
        numbers rounded to half precision), and the unpacked state; (None, None) while the gate is shut (the network without
        it). obs: the raw inputs; hb: the seats' packed brain state (the end of their arrays)"""
        if not self.brain_on:
            return None, None
        import btoken as btoken_
        assert pose is not None and zmap is not None, "this network's brain is stepped: give act() pose= and zmap= (btoken.pose_from_env)"
        br_, tk_ = btoken_.unpack(self.brainP, self.btok, hb)
        tk_.see(obs)
        return tk_.features(np.asarray(pose, np.float32), np.asarray(zmap)).astype(np.float32), (br_, tk_)

    def token_post(self, xa, pose, zmap, st):
        """(v0.4.1) after the frame: the brain reads the frame's normalised inputs xa; at its tick the readouts' answer is kept in
        map coordinates (his pose of this frame) -> the packed state"""
        import btoken as btoken_
        br_, tk_ = st
        tk = br_.frame(xa)
        self.h2_tick = None
        if tk.any():
            o1_, o2_ = br_.readouts(tk)
            tk_.answer(tk, o1_, o2_, np.asarray(pose, np.float32)[tk], np.asarray(zmap)[tk])
            self.h2_tick = (tk, br_.s[tk], o1_, o2_)        # (v0.4.3) what the strategy head reads at the tick
            if self.h2 is not None and self.h2.get("cmb") and self.h2_ah is not None:   # (1.7) the readout ahead's places, kept in map
                import head2 as head2_                       # coordinates at the tick (btoken.answer_fut's), for the combat order
                if self.fut is None or len(self.fut) != len(tk):
                    self.fut = np.zeros((len(tk), 3, 3), np.float32)
                f_ = np.asarray(head2_.np_mlp(self.h2_ah, br_.s[tk]), np.float64)[:, :15].reshape(-1, 3, 5)
                pz_ = np.asarray(pose, np.float64)[tk]
                x_, y_ = btoken_._turn(np.repeat(pz_[:, 3:4], 3, 1), f_[..., 0] * 1000.0, f_[..., 1] * 1000.0)
                self.fut[tk] = np.stack([pz_[:, None, 0] + x_, pz_[:, None, 1] + y_, pz_[:, None, 2] + f_[..., 2] * 1000.0], -1)
        return btoken_.pack(br_, tk_).astype(np.float32)

    def set_head2_gate(self, g):
        """(v0.4.3, checks) play the strategy head at this gate (0: the network without it)"""
        assert self.h2 is not None, "this network has no strategy head"
        import head2 as head2_
        self.h2W = dict(self.h2W, gate=np.float32(g))
        self.h2_live = head2_.np_open(self.h2W)

    def set_head2_wadd(self, w):
        """(1.5a, checks) play the strategy head's weapon scores at this add (0: blanked, the hands' weapon choice alone)"""
        assert self.h2 is not None and "wsc.weight" in self.h2W, "this network has no weapon part in its strategy head"
        import head2 as head2_
        self.h2W = dict(self.h2W, wadd=np.float32(w))
        self.h2_live = head2_.np_open(self.h2W)

    def set_head2_mix(self, m):
        """(b1.4a, checks) play his target choice moved this far from the hands' to the strategy head's (1: the head's alone)"""
        assert self.h2 is not None, "this network has no strategy head"
        import head2 as head2_
        self.h2W = dict(self.h2W, mix=np.float32(m))
        self.h2_live = head2_.np_open(self.h2W)

    def set_gate(self, g):
        """(v0.4.1, checks) play the brain's token at this gate (0: shut, the network without it)"""
        assert g <= 0 or self.btok is not None, "this network has no brain token"
        self.bgate = float(g)

    def clear(self, h, rows=None):
        """a seat's memory cleared (the trainer's `done`), in place; the head's tick clock kept (sim/head.py np_clear). For a
        network without a head the same as h[rows] = 0."""
        r = slice(None) if rows is None else rows
        if self.brain_at is not None:                        # (v0.4.1) the brain and its answer, by the same flag (its own clear)
            import btoken as btoken_
            btoken_.packed_clear(h[:, self.brain_at:], rows, self.brainP["H"])
        if self.head is None:                                # (the strategy head's state is cleared with it: zeros)
            h[r, :self.brain_at] = 0.0
            return h
        h[r, :self.head_at] = 0.0
        self.hm.np_clear(self.head, h[:, self.head_at:self.brain_at], rows)
        return h

    def head_due(self, h):
        """[B] bool: the head ticks on the coming frame (fetch the simulator's head_events() then); all False without a head"""
        if self.head is None:
            return np.zeros(len(h), bool)
        return self.hm.np_due(self.head, h[:, self.head_at:])

    def events(self, env, h):
        """the tick's events for act(): env.head_events() on a frame the head ticks (a simulator without them: None, zeros)"""
        if self.head is None or not self.head_due(h).any() or not hasattr(env, "head_events"):
            return None
        return env.head_events()

    def legs_logits(self, xl, zo=None):
        """(LEGS_IN) his legs' branch: the simulator's legs_prep() rows -> the logits [rows, 17]; None without the branch"""
        if self.legsP is None:
            return None
        w0, b0, w1, b1, wp, bp = self.legsP
        xl = np.asarray(xl, np.float32)[:, :w0.shape[1]]     # (a branch without the three inputs of a look point: the old inputs come first)
        lg = (np.tanh(np.tanh(np.asarray(xl, np.float32) @ w0.T + b0) @ w1.T + b1) @ wp.T + bp).astype(np.float32)
        if self.uniR is not None:                            # (--legs-residual) from his memory of the frame (act()'s, or zo)
            import legs_unify as LU_
            zo = self.last_zo if zo is None else zo
            assert zo is not None and len(zo) == len(lg), "the residual needs his memory of this frame (act() first)"
            lg = LU_.np_residual(*self.uniR, lg, zo)
        return lg

    @property
    def keep_on(self):
        """(1.4c, 1.7a) the keep choice decides a share of his seconds, or (1.7) the combat order is asked at a share of his readings:
        act(kf=...) gives one more column, d + 2 c + 4 r (its draw, the hand-over's coin, a keep reading: the frame after the head's
        tick; sim/duel_env.py KEEP_FEAT) + (8 kind + 32 candidate + 256) where the order is asked"""
        return self.keep_g > 0 or self.cmb_g > 0

    @property
    def order_on(self):
        """(1.7) the order plays: asked at a share, or its adds on the targets' and the way's above 0"""
        return self.o_at is not None and (self.cmb_g > 0 or float(np.asarray(self.h2W.get("padd", 0.0))) > 0)

    @property
    def order_due(self):
        """(1.7) the coming frame is a keep reading for some seat (their head ticked on this one): give its act() ox= (the simulator's
        order_feat() after this frame's step, these rows)"""
        return self.order_on and self.k_r is not None and bool(self.k_r.any())

    def set_cmb_g(self, g):
        """(1.7, the checks) the combat order's share, in place of the file's (a network without it: refused)"""
        assert self.o_at is not None, "set_cmb_g: this network has no combat order"
        self.cmb_g = float(g)
        if self.cmb_g > 0:
            self.h2_live = True

    def set_padd(self, p):
        """(1.7, the checks) the pointer's adds on the targets' and the way's at this share (0: none)"""
        assert self.o_at is not None, "set_padd: this network has no combat order"
        import head2 as head2_
        self.h2W = dict(self.h2W, padd=np.float32(p))
        self.h2_live = head2_.np_open(self.h2W) or self.cmb_g > 0

    def set_fadd(self, f):
        """(1.7, the checks) the head's push on the fire key at this add (0: none)"""
        assert self.h2 is not None and "fsc.weight" in self.h2W, "set_fadd: this network has no fire push"
        import head2 as head2_
        self.h2W = dict(self.h2W, fadd=np.float32(f))
        self.h2_live = head2_.np_open(self.h2W) or self.cmb_g > 0

    def set_keep_g(self, g):
        """(1.4c, the checks) the keep choice's share, in place of the file's (a network without it: refused)"""
        assert self.h2 is not None and self.h2.get("keep"), "set_keep_g: this network has no keep choice"
        self.keep_g = float(g)

    def act(self, obs, h, events=None, xl=None, pose=None, zmap=None, kf=None, ox=None):
        """events [B, 32]: the head's tick events (events()); None: zeros. xl [B, the branch's inputs]: (--legs-feat,
        --legs-guide, while their parts are not at zero) the simulator's legs_prep() rows of this frame. kf [B, KEEP_FEAT]: (1.4c,
        with keep_on) the simulator's keep_feat() rows after the frame before: one more column comes back, the keep choice.
        ox: (1.7, with order_due after the frame before) the simulator's order_feat() of these rows after the frame before (X, C, ...):
        the seats with a keep reading make their order from it (the trainer's order_tick) before this frame's outputs"""
        dadd = gadd = h2_ = lgl_ = ok_ = None
        if self.needs_xl:
            import legs_unify as LU_
            assert xl is not None, "this network's legs_door or guide is open: give act() the branch's inputs (xl=env.legs_prep())"
            ok_ = LU_.np_way(xl)
            h2_, lgl_ = LU_.np_branch(self.legsP, xl)
            dadd = LU_.np_door(self.uniD[0], self.uniD[1], h2_, ok_) if self.uniD is not None else None
            gadd = LU_.np_guide_add(self.uni, self.uniG, lgl_, ok_, sum(self.dims)) if self.uniG is not None else None
        hh = hb = h2s = ohs = None
        if self.brain_at is not None:                        # (v0.4.1) the brain's packed state, at the end of the array
            hb, h = h[:, self.brain_at:], h[:, :self.brain_at]
        if self.o_at is not None:                            # (1.7) the order's held numbers, after the head's state
            ohs, h = h[:, self.o_at:], h[:, :self.o_at]
        if self.h2 is not None:                              # (v0.4.3) the strategy head's state, before the brain's
            h2s, h = h[:, self.h2_at:], h[:, :self.h2_at]
        if self.head is not None:
            hh, h = h[:, self.head_at:], h[:, :self.head_at]
        hf = h                                               # (--slow-mem) the whole state; h its fast part
        if self.slow is not None:
            h = hf[:, :self.H]
        if obs.shape[1] > len(self.mean):                    # an older network in a simulator with more inputs: they are appended at the end
            obs = obs[:, :len(self.mean)]
        x = np.clip((obs - self.mean) / np.sqrt(self.var + 1e-8), -10, 10).astype(np.float32)
        xa = x                                               # (the brain reads these: unfaded)
        bt, bst = self.token_pre(obs, pose, zmap, hb)
        if self.rfg > 0 and len(self.rf_cols):               # (v0.4.2a) the hands' inputs: the rule-made columns times (1 - g)
            import rule_fade as rfade_
            x = rfade_.apply_np(x, self.rf_cols, self.rfg)
        xh = x                                               # (the hands' attention reads these)
        if self.cell is not None:
            ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(self.cell) - 1)
            x = np.concatenate([x[:, :-2], self.cell[ids[:, 0]], self.cell[ids[:, 1]]], 1)
        x = np.tanh(x @ self.w0.T + self.b0)
        x = np.tanh(x @ self.w1.T + self.b1)
        if self.attP is not None:
            bta = bt if self.bgate > 0 else None             # (v0.4.2a: the brain stepped for the readers alone: its token stays out)
            x = x + self.attn_fwd(self.attn, self.attP, xh, hm=h, bt=bta, bg=self.bgate if bta is not None else 0.0)   # (hm: "mem", his memory of the frame before)
        xf = x
        if hh is not None:                                   # (v0.4) the plan of the head's last tick: e + plan_in(plan)
            o_ = self.hm._np_off(self.head)["plan"]
            xf = x + self.hm.np_plan_in(self.headP, hh[:, o_[0]:o_[1]])
        if dadd is not None:                                 # (--legs-feat) only his fast GRU reads the legs' features
            xf = xf + dadd
        ord_ = None
        if ohs is not None and self.order_on and ox is not None and self.k_r is not None and len(self.k_r) == len(ohs) and self.k_r.any():
            import head2 as head2_                           # (1.7) a keep reading (the frame after the head's tick): the order made from
            r_ = np.nonzero(self.k_r)[0]                     # the candidates the simulator made after that frame, the brain's odds written
            X_ = np.array(np.asarray(ox[0])[r_], np.float32)    # in (its state: the tick's), held to the next reading (the trainer's order_tick)
            C_ = np.asarray(ox[1], np.float32)[r_]
            if self.passW is not None and bst is not None:
                import passodds as passodds_
                X_[..., head2_.CMB_PASS0:head2_.CMB_PASS0 + 3] = passodds_.np_forward(self.passW, self.passL, bst[0].s[r_], X_)
            kl_, ps_, ta_, ya_, okc_ = head2_.np_order_scores(self.h2W, self.h2, h2s[r_], X_, C_)   # (1.7b: okc_, not ok_: ok_ is the
            okf_ = okc_.astype(np.float32)[:, None]                                                 # legs' way flags, read by their gate below)
            ohs = ohs.copy()
            ohs[r_] = np.concatenate([kl_, ps_, ta_ * okf_, ya_ * okf_], 1)
            ord_ = (r_, kl_, ps_, okc_)
        b2 = None
        if h2s is not None and self.h2_live:                 # (v0.4.3) the plan of its last tick into his fast GRU, its bias on his intention
            import head2 as head2_
            g2_, b2 = head2_.np_adds(self.h2W, self.h2, h2s)
            xf = xf + g2_
        gi = xf @ self.wih.T + self.bih
        gh = h @ self.whh.T + self.bhh
        H = self.H
        r = sig(gi[:, :H] + gh[:, :H])
        z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
        nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
        h = ((1 - z) * nn_ + z * h).astype(np.float32)
        hfast = h
        zo = h
        if self.slow is not None:                            # (--slow-mem) the outputs read h + door(s); the slow GRU ticks on its frames
            zo, h = self.slow_step(self.slowP, self.slow, x, h, hf)
        logits = zo @ self.wp.T + self.bp
        if b2 is not None:
            si2_ = slice(int(np.sum(self.dims[:10])), int(np.sum(self.dims[:11])))
            logits[:, si2_] = head2_.np_mix_in(self.h2W, self.h2, h2s, logits[:, si2_]) + b2     # (b1.4a: the mix; none at mix 0)
            wa2_ = head2_.np_wadd(self.h2W, self.h2, h2s)    # (1.5a) its weapon scores on the weapon key's (none without the part or at wadd 0)
            if wa2_ is not None:
                logits[:, int(np.sum(self.dims[:6])):int(np.sum(self.dims[:7]))] += wa2_
            fa2_ = head2_.np_fadd(self.h2W, self.h2, h2s)    # (1.7) its fire scores on the fire key's (none without the part or at fadd 0)
            if fa2_ is not None:
                logits[:, int(np.sum(self.dims[:5])):int(np.sum(self.dims[:6]))] += fa2_
            pa_ = float(np.asarray(self.h2W.get("padd", 0.0))) if ohs is not None else 0.0
            if pa_ > 0:                                      # (1.7) the pointer's scores held from the last reading on the targets' and the way's
                o0_ = head2_.CMB_NK + head2_.CMB_NEW
                i0_ = int(np.sum(self.dims[:10]))
                logits[:, i0_:i0_ + head2_.CMB_T] += np.float32(pa_) * ohs[:, o0_:o0_ + head2_.CMB_T]
                if len(self.dims) > 12:
                    w0_ = int(np.sum(self.dims[:12]))
                    logits[:, w0_:w0_ + head2_.CMB_W] += np.float32(pa_) * ohs[:, o0_ + head2_.CMB_T:]
        if hh is not None:                                   # (v0.4) the head ticks on its frames; its target and way join the hands'
            _, t_add, w_add, hh = self.hm.np_tick(self.headP, self.head, x, hfast, hh, events)
            logits[:, self.head_si] += t_add
            logits[:, self.head_sw] += w_add
            h = np.concatenate([h, hh], 1)
        if gadd is not None:                                 # (--legs-guide) the branch's choice on his movement outputs
            logits = logits + gadd
        if self.uniT is not None:                            # (--legs-gate) g(zo) x the legs' choice, the motor layer
            import legs_unify as LU_
            logits = logits + LU_.np_gate_add(self.uni, *self.uniT, zo, h2_, lgl_, ok_, sum(self.dims))
        self.last_zo = zo
        self.last_logits = logits                            # (sim/brain_fit.py: the play effect of a brain, the distributions per output)
        if bt is not None:
            hb = self.token_post(xa, pose, zmap, bst)
        kcol = None
        if self.keep_on and kf is not None and h2s is not None:   # (1.4c) the keep choice: the head's state this frame's outputs read
            import head2 as head2_                           # (before its tick), the hands' memory after the frame, its own numbers
            si_ = slice(int(np.sum(self.dims[:10])), int(np.sum(self.dims[:11])))
            li_ = logits[:, si_]
            li_ = li_ - li_.max(1, keepdims=True)
            lsm_ = li_ - np.log(np.exp(li_).sum(1, keepdims=True))
            cur_ = np.clip(np.asarray(kf)[:, 2].astype(np.int64), 0, lsm_.shape[1] - 1)
            kx_ = head2_.np_keep_x(kf, lsm_[np.arange(len(cur_)), cur_])
            kz_ = head2_.np_keep_logit(self.h2W, self.h2, h2s, hfast, kx_)
            kd_ = (self.krng.random(len(kz_)) < sig(kz_)).astype(np.int64)
            kc_ = (self.krng.random(len(kz_)) < self.keep_g).astype(np.int64)
            if self.k_r is None or len(self.k_r) != len(kz_):
                self.k_r = np.zeros(len(kz_), bool)
            kcol = kd_ + 2 * kc_ + 4 * self.k_r.astype(np.int64)     # (1.7a) the seats whose head ticked on the frame before: a keep reading
            if ord_ is not None and self.cmb_g > 0:          # (1.7) the order's kind and candidate drawn at the reading (the keep choice's
                r_, kl_, ps_, okc_ = ord_                    # stream), asked with its share where the head has a state: + 8 k + 32 c + 256

                def pick_(z_):
                    p_ = np.exp(z_ - z_.max(1, keepdims=True))
                    p_ /= p_.sum(1, keepdims=True)
                    return np.minimum((p_.cumsum(1) < self.krng.random((len(z_), 1))).sum(1), z_.shape[1] - 1).astype(np.int64)
                ko_ = pick_(kl_)
                co_ = np.zeros_like(ko_)
                for k_ in range(1, head2_.CMB_NK):
                    c0_, m_ = head2_.CMB_C0[k_], head2_.CMB_SLOTS[k_]
                    co_ = np.where(ko_ == k_, pick_(ps_[:, c0_:c0_ + m_]), co_)
                oq_ = ((self.krng.random(len(r_)) < self.cmb_g) & okc_).astype(np.int64)
                kcol[r_] = kcol[r_] + (8 * ko_ + 32 * co_ + 256) * oq_
        if h2s is not None:                                  # (v0.4.3) the strategy head ticks with the brain, after the frame
            self.k_r = np.zeros(len(h2s), bool)              # (1.7a) whose head ticks on this frame: the next frame is their keep reading
            if self.h2_live and self.h2_tick is not None:
                import head2 as head2_
                tk_, sb_, o1_, o2_ = self.h2_tick
                self.k_r = np.asarray(tk_, bool).copy()
                u_ = head2_.np_feats(self.h2, brain=sb_, trk=o1_, trz=o2_,
                                     ahead=head2_.np_mlp(self.h2_ah, sb_) if self.h2_ah is not None else None,
                                     ctrl=head2_.np_ctrl(self.h2_ct, sb_, hfast[tk_]),
                                     fight=head2_.np_fight(self.h2_fo, sb_, hfast[tk_]),
                                     obs=xa[tk_], hands=hfast[tk_])
                h2s = h2s.copy()
                h2s[tk_] = head2_.np_tick(self.h2W, self.h2, u_, h2s[tk_])
            h = np.concatenate([h, h2s.astype(np.float32)], 1)
            if ohs is not None:                              # (1.7) the order's held numbers back after it
                h = np.concatenate([h, ohs.astype(np.float32)], 1)
        o_ = np.concatenate([[0], np.cumsum(self.dims)]).astype(int)
        if self.fade:                                        # (--switch-fade) off the switch's "legs" choice
            logits = logits.copy()
            logits[:, int(o_[11]) + 1] -= self.fade
        if getattr(self, "wpush", None) is not None:        # (1.7c experiments, checks only) the fixed push toward the pros' weapon
            logits = logits.copy()
            logits[:, int(o_[6]) + 1:int(o_[6]) + 4] += self.wpush(obs)
        u_ = [self.rng.random((len(logits), 1)) for _ in self.dims]       # (one number a player and output, in the outputs' order)
        out = np.zeros((len(logits), len(self.dims)), np.int64)

        def one(j, l):
            p = np.exp(l - l.max(1, keepdims=True))
            p /= p.sum(1, keepdims=True)
            out[:, j] = (p.cumsum(1) > u_[j]).argmax(1)                  # sampled, as in training
        later = {int(c_) for _, c_ in self.order}
        for j in range(len(self.dims)):
            if j not in later:
                one(j, logits[:, o_[j]:o_[j + 1]])
        for p_, c_ in self.order:                                        # (--ordered-heads) after the one before, its table's row added
            one(int(c_), logits[:, o_[c_]:o_[c_ + 1]] + self.orderT[int(c_)][out[:, int(p_)]])
        if self.no_switch and out.shape[1] > 11:             # (NO_SWITCH) drawn as before, then off: his own network drives
            out[:, 11] = 0
        if hb is not None:                                   # (v0.4.1) the brain's state back at the end of the array
            h = np.concatenate([h, hb.astype(np.float32)], 1)
        if kcol is not None:                                 # (1.4c) the keep column after the outputs (the simulator takes it off)
            out = np.concatenate([out, kcol[:, None]], 1)
        return out, h


def set_delays(E, env, who):
    """(B-226) the two reaction delays of a check, from the networks that play it.
      who   [(seats, react_ms, acquire_ms), ...]: the seats a network plays (indices) and the delays it was trained with
            (Policy.react_ms and Policy.acquire_ms: the trainer's --react-ms and --acquire-ms; or an override). The first
            entry is "he".
    Seats nobody names (a scripted player: the stand-in, a target, a fighter) keep what they have had in every check: his
    tracking delay and the simulator's own acquire delay (ACQUIRE_FRAMES, 200 ms), so that the yardstick does not move
    with the network it measures. Where every seat has the same, one number is set, as ever (env.react_frames,
    env.acquire_frames). Where they differ, one a seat (env.react_seat, env.acquire_seat: duel_env's SEAT_DELAYS; the two
    numbers are then the largest); a simulator module that cannot do that is refused, not played at one seat's delays.
    -> what was set, in ms: {"he": [react, acquire], "opponent": [...] (a second network), "others": [...] (unnamed seats)}"""
    n = env.n
    rf = np.full(n, int(round(float(who[0][1]) / 25)), np.int64)
    af = np.full(n, int(getattr(E, "ACQUIRE_FRAMES", 8)), np.int64)
    named = np.zeros(n, bool)
    for seats, r_ms, a_ms in who:
        rf[seats], af[seats], named[seats] = int(round(float(r_ms) / 25)), int(round(float(a_ms) / 25)), True
    for name, fr in (("react", rf), ("acquire", af)):
        if (fr == fr[0]).all():
            setattr(env, name + "_frames", int(fr[0]))
            if hasattr(env, name + "_seat"):
                setattr(env, name + "_seat", None)
        else:
            assert getattr(E, "SEAT_DELAYS", False), (
                "the seats differ in their {} delay ({} frames) and the simulator module {} has one number for all seats: play them in the "
                "current module, or give both networks one delay (--{}-ms and its --opp- twin)".format(
                    name, sorted(set(int(x) for x in fr)), E.__name__, name))
            setattr(env, name + "_frames", int(fr.max()))
            setattr(env, name + "_seat", fr.copy())
    out = {}
    for key, seats in [("he", who[0][0])] + ([("opponent", who[1][0])] if len(who) > 1 else []) + [("others", ~named)]:
        s_ = np.atleast_1d(np.arange(n)[seats])
        if len(s_):
            out[key] = [25 * int(rf[s_[0]]), 25 * int(af[s_[0]])]
    return out


def rooms(E, quick=False):
    """room list: name -> settings for the simulator"""
    W = {w: i for i, w in enumerate(E.WEAPONS)}
    out = []
    secs = 15 if quick else 40
    mid = (350.0, 650.0)
    for w in ("lg", "rg", "rl", "pg", "sg", "hmg", "mg"):
        for style in ("still", "slow", "fast", "jump"):
            if quick and style in ("slow", "jump"):
                continue
            out.append(dict(name="aim/{}/{}".format(w, style), kind=(E.AIM, 1), weapon=W[w], style=E.STYLES.index(style),
                            band=mid, secs=secs, round_len=15.0, close_p=1.0))
    for w in ("lg", "rg", "rl"):
        for tag, band in (("close", (150.0, 300.0)), ("far", (800.0, 1200.0))):
            out.append(dict(name="aim/{}/fast@{}".format(w, tag), kind=(E.AIM, 1), weapon=W[w], style=3, band=band,
                            secs=secs, round_len=15.0, close_p=1.0))
    for tag, band in (("close", (150.0, 300.0)), ("mid", (350.0, 650.0)), ("far", (800.0, 1200.0))):
        out.append(dict(name="choice/" + tag, kind=(E.NORMAL, 1), style=3, band=band, secs=secs, round_len=15.0,
                        close_p=1.0, bin=("close", "mid", "far").index(tag)))
    out.append(dict(name="move", kind=(E.MOVE, 0), secs=30 if quick else 90, round_len=30.0, close_p=0.0))
    out.append(dict(name="solo", kind=(E.SOLO, 1), style=1, secs=40 if quick else 120, round_len=1000.0, close_p=0.0))
    for j, per in enumerate(E.PERSONAS):
        if quick and j > 1:
            continue
        out.append(dict(name="ladder/" + per, kind=(E.NORMAL, 2), style=0, band=(300.0, 700.0),
                        secs=40 if quick else 90, round_len=90.0, close_p=0.2, fighter=True, persona=j))
    return out


def run_room(E, env, pol, room):
    """returns the metrics of one room on one map"""
    env.fixed_kind = room["kind"]
    env.sc_style = room.get("style", 0)
    env.close_band = room.get("band", (300.0, 700.0))
    env.close_p = room["close_p"]
    env.round_len = room["round_len"]
    env.persona_force = room.get("persona")
    env.inf_ammo = room["name"].startswith("aim/")           # aim rooms measure aim, not ammo discipline
    if "weapon" in room:
        env.aim_weapons = (room["weapon"],)
    if room["kind"][0] == E.NORMAL and not room.get("fighter"):
        env.close_p = 1.0
    env.round_t[:] = 1e9                                    # every match restarts under the room's rules
    n = env.n
    h = pol.zeros(n)
    obs, _, done, _ = env.step(np.zeros((n, len(pol.dims)), np.int64))
    env.round_t[:] = 0.0
    base = {k: np.copy(v) for k, v in env.stats.items()}
    frames = int(room["secs"] / E.DT)
    for _ in range(frames):
        act, h = pol.act(obs, h, pol.events(env, h))
        obs, _, done, _ = env.step(act)
        pol.clear(h, done)
    d = {k: env.stats[k] - base[k] for k in env.stats}
    mins = frames * E.DT / 60.0 * env.M                      # subject-minutes
    r = {}
    name = room["name"]
    if name.startswith("aim/"):
        w = E.WEAPONS[room["weapon"]]
        r["hit_rate"] = d[w + "_hits"] / max(1, d[w + "_shots"])
        r["damage_per_s"] = d["dmg_h"] / (mins * 60)
        r["kills_per_min"] = d["target_kills"] / mins
        r["aim_err_deg"] = d["aim_err"] / max(1, d["aim_frames"])
        r["on_target"] = d["on_target"] / max(1, d["aim_frames"])
        r["sees_target"] = d["aim_frames"] / max(1, frames * env.M)
    elif name.startswith("choice/"):
        row = d["w_dist"][room["bin"]]
        tot = max(1.0, row.sum())
        top = np.argsort(-row)[:3]
        r["held"] = {E.WEAPONS[i]: round(float(row[i] / tot), 2) for i in top if row[i] > 0}
        r["switches_per_min"] = d["switches"] / mins
        r["damage_per_s"] = d["dmg_h"] / (mins * 60)
        r["kills_per_min"] = d["target_kills"] / mins
    elif name == "move":
        mf = max(1, d["move_frames"]) / 2.0                  # both players of a movement match are subjects
        r["arrivals_per_min"] = d["move_arrive"] / (2 * mins)
        r["speed"] = d["move_speed"] / max(1, d["move_frames"])
        r["fast_air"] = d["move_fast"] / max(1, d["move_frames"])
    elif name == "solo":
        r["mega_per_min"] = d["pick_mega"] / mins
        r["red_armor_per_min"] = d["pick_ra"] / mins
        r["armor_per_min"] = d["pick_ar"] / mins
        r["health_per_min"] = d["pick_hp"] / mins
        r["fire"] = d["fire_frames"] / max(1, d["play_frames"])
        r["blind_fire"] = d["blind_frames"] / max(1, d["play_frames"])
        r["switches_per_min"] = d["switches"] / mins
    else:
        r["frags_per_min"] = d["frags_vs_bot"] / mins
        r["deaths_per_min"] = d["bot_frags"] / mins
        r["damage_dealt_per_min"] = d["dmg_h"] / mins
        r["damage_taken_per_min"] = d["dmg_from_script"] / mins
        r["switches_per_min"] = d["switches"] / mins
        r["blind_fire"] = d["blind_frames"] / max(1, d["play_frames"])
    return r


LAB_WEAPONS = ("mg", "sg", "rl", "lg", "rg", "pg")


def lab_rooms(E, env):
    """the rooms of the test map: the same names as on the play-test server (plugins/duelbot.py)"""
    W = {w: i for i, w in enumerate(E.WEAPONS)}
    out = []
    for w in LAB_WEAPONS:
        for t in ("walk", "jump", "env"):
            out.append(dict(name="aim/{}/{}".format(w, t), secs=45 if t == "env" else 25,
                            force=dict(kind=E.AIM, weapon=W[w], where="env" if t == "env" else "aim", jump=t == "jump")))
    for k, C in enumerate(env.courses):
        out.append(dict(name="move/" + C["key"], secs=30, force=dict(kind=E.COURSE, course=k), course=k))
    return out


def run_lab_room(E, env, pol, room):
    """one lab room: every match runs exactly this room once, for its full length"""
    env.lab_force = room["force"]
    env.lab_aim_len = env.course_len = float(room["secs"])
    env.inf_ammo = room["name"].startswith("aim/")
    env.round_t[:] = 1e9
    n = env.n
    h = pol.zeros(n)
    base = {k: np.copy(v) for k, v in env.stats.items()}     # before the step that starts the room (counts the attempts)
    obs, _, done, _ = env.step(np.zeros((n, len(pol.dims)), np.int64))
    frames = int(room["secs"] / E.DT) - 1
    for _ in range(frames):
        act, h = pol.act(obs, h, pol.events(env, h))
        obs, _, done, _ = env.step(act)
        pol.clear(h, done)
    if "course" in room:                                     # close the attempts still running
        for i in range(n):
            env._course_close(i, False)
            env.course[i] = -1
    d = {k: env.stats[k] - base[k] for k in env.stats}
    mins = frames * E.DT / 60.0 * env.M
    if "course" in room:
        r_ = d["course"][room["course"]]
        att = max(1.0, r_[0])
        return dict(finished=r_[1] / att, time=(r_[2] / r_[1]) if r_[1] else -1.0, distance=r_[3] / att,
                    top_speed=r_[4] / att, mean_speed=r_[5] / max(1.0, r_[6]), falls=r_[7] / att, height=r_[8] / att)
    w = E.WEAPONS[room["force"]["weapon"]]
    return dict(hit_rate=d[w + "_hits"] / max(1, d[w + "_shots"]), damage_per_s=d["dmg_h"] / (mins * 60),
                kills_per_min=d["target_kills"] / mins, aim_err_deg=d["aim_err"] / max(1, d["aim_frames"]),
                on_target=d["on_target"] / max(1, d["aim_frames"]), sees_target=d["aim_frames"] / max(1, frames * env.M))


def merge(cards):
    """average the per-map results of one room"""
    out = {}
    for k in cards[0]:
        if isinstance(cards[0][k], dict):
            keys = sorted({x for c in cards for x in c[k]})
            m = {x: round(float(np.mean([c[k].get(x, 0.0) for c in cards])), 2) for x in keys}
            out[k] = dict(sorted(m.items(), key=lambda kv: -kv[1])[:3])
        else:
            out[k] = round(float(np.mean([c[k] for c in cards])), 3)
    return out


def markdown(card, other=None):
    lines = ["# Test suite: {} at {} min of training (suite v{})".format(card["run"], card["minutes"], card["suite"]), ""]
    groups = {}
    for name, r in card["rooms"].items():
        groups.setdefault(name.split("/")[0], []).append((name, r))
    for g, rows in groups.items():
        cols = [k for k in rows[0][1]]
        lines += ["## " + g, "", "| room | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for name, r in rows:
            cells = []
            for k in cols:
                v = r.get(k)
                txt = json.dumps(v).replace('"', "") if isinstance(v, dict) else str(v)
                o = (other or {}).get("rooms", {}).get(name, {}).get(k)
                if o is not None and not isinstance(v, dict):
                    txt += " ({:+.3g})".format(v - o)
                cells.append(txt)
            lines.append("| {} | {} |".format(name, " | ".join(cells)))
        lines.append("")
    if other:
        lines.append("Change in brackets: against {} at {} min.".format(other.get("run"), other.get("minutes")))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default=None, help="checkpoint file (default: the run's policy.pt)")
    ap.add_argument("--env", default="duel_env")
    ap.add_argument("--matches", type=int, default=32)
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--lab", action="store_true", help="the test map's rooms (testlab), as on the play-test server")
    ap.add_argument("--compare", default=None, help="an earlier card (JSON) to show changes against")
    ap.add_argument("--react-ms", type=float, default=None, help="his tracking delay (default: the checkpoint's react_ms)")
    ap.add_argument("--acquire-ms", type=float, default=None, help="his delay before an enemy who has just come into view is noticed "
                                                                    "(default: the checkpoint's acquire_ms; B-226). The scripted "
                                                                    "players keep the simulator's own 200 ms")
    a = ap.parse_args()
    import importlib
    E = importlib.import_module(a.env)
    path = a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt")
    pol = Policy(path, seed=11)
    maps = a.maps.split(",")[:1] if a.quick else a.maps.split(",")
    if a.lab:
        maps = ["testlab"]
    per_room = {}
    t0 = time.time()
    for mp in maps:
        env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=a.matches, seed=7,
                        nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)), close_p=1.0, loadout="all")
        dl_ = set_delays(E, env, [(np.arange(0, env.n, 2), pol.react_ms if a.react_ms is None else a.react_ms,       # (the subject is the
                                   pol.acquire_ms if a.acquire_ms is None else a.acquire_ms)])                    # even player of a match)
        if a.lab:
            for room in lab_rooms(E, env):
                per_room.setdefault(room["name"], []).append(run_lab_room(E, env, pol, room))
            continue
        for room in rooms(E, a.quick):
            per_room.setdefault(room["name"], []).append(run_room(E, env, pol, room))
        print("{} done ({:.0f} s)".format(mp, time.time() - t0), flush=True)
    card = dict(suite=SUITE_VERSION, run=a.run, minutes=int(pol.minutes), maps=maps, subject="policy", delays_ms=dl_,
                rooms={k: merge(v) for k, v in per_room.items()})
    out = os.path.join(ROOT, "data", "sim_runs", a.run, "suite")
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, "{}_{:04d}{}".format("lab" if a.lab else "card", int(pol.minutes), "_quick" if a.quick else ""))
    other = json.load(open(a.compare)) if a.compare else None
    md = markdown(card, other)
    json.dump(card, open(stem + ".json", "w"), indent=1)
    open(stem + ".md", "w").write(md + "\n")
    print(md)
    print("\nsaved", stem + ".json")


if __name__ == "__main__":
    main()

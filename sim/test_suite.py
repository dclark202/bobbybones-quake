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
        self.react_ms = float(ck.get("react_ms", 150.0))
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
        self.legsP = None                                    # (LEGS_IN, B-253) his legs' branch, if the network has it inside
        if "legs.0.weight" in sd:
            self.legsP = tuple(sd[k_] for k_ in ("legs.0.weight", "legs.0.bias", "legs.2.weight", "legs.2.bias", "legs.4.weight", "legs.4.bias"))
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

    def zeros(self, n):
        return np.zeros((n, self.W), np.float32)

    @property
    def hm(self):
        """(v0.4) sim/head.py's numpy side"""
        import head as head_
        return head_

    def clear(self, h, rows=None):
        """a seat's memory cleared (the trainer's `done`), in place; the head's tick clock kept (sim/head.py np_clear). For a
        network without a head the same as h[rows] = 0."""
        r = slice(None) if rows is None else rows
        if self.head is None:
            h[r] = 0.0
            return h
        h[r, :self.head_at] = 0.0
        self.hm.np_clear(self.head, h[:, self.head_at:], rows)
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

    def legs_logits(self, xl):
        """(LEGS_IN) his legs' branch: the simulator's legs_prep() rows -> the logits [rows, 17]; None without the branch"""
        if self.legsP is None:
            return None
        w0, b0, w1, b1, wp, bp = self.legsP
        xl = np.asarray(xl, np.float32)[:, :w0.shape[1]]     # (a branch without the three inputs of a look point: the old inputs come first)
        return (np.tanh(np.tanh(np.asarray(xl, np.float32) @ w0.T + b0) @ w1.T + b1) @ wp.T + bp).astype(np.float32)

    def act(self, obs, h, events=None):
        """events [B, 32]: the head's tick events (events()); None: zeros"""
        hh = None
        if self.head is not None:
            hh, h = h[:, self.head_at:], h[:, :self.head_at]
        hf = h                                               # (--slow-mem) the whole state; h its fast part
        if self.slow is not None:
            h = hf[:, :self.H]
        if obs.shape[1] > len(self.mean):                    # an older network in a simulator with more inputs: they are appended at the end
            obs = obs[:, :len(self.mean)]
        x = np.clip((obs - self.mean) / np.sqrt(self.var + 1e-8), -10, 10).astype(np.float32)
        xa = x
        if self.cell is not None:
            ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(self.cell) - 1)
            x = np.concatenate([x[:, :-2], self.cell[ids[:, 0]], self.cell[ids[:, 1]]], 1)
        x = np.tanh(x @ self.w0.T + self.b0)
        x = np.tanh(x @ self.w1.T + self.b1)
        if self.attP is not None:
            x = x + self.attn_fwd(self.attn, self.attP, xa, hm=h)       # (hm: "mem", his memory of the frame before)
        xf = x
        if hh is not None:                                   # (v0.4) the plan of the head's last tick: e + plan_in(plan)
            o_ = self.hm._np_off(self.head)["plan"]
            xf = x + self.hm.np_plan_in(self.headP, hh[:, o_[0]:o_[1]])
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
        if hh is not None:                                   # (v0.4) the head ticks on its frames; its target and way join the hands'
            _, t_add, w_add, hh = self.hm.np_tick(self.headP, self.head, x, hfast, hh, events)
            logits[:, self.head_si] += t_add
            logits[:, self.head_sw] += w_add
            h = np.concatenate([h, hh], 1)
        o_ = np.concatenate([[0], np.cumsum(self.dims)]).astype(int)
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

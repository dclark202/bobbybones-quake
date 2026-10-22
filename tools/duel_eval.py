"""Ten-minute duels in the simulator against a fixed opponent, many at once: the check with error bars that the
real-server games cannot give (docs/RESULTS.md, audit of 2026-10-08; owner: "play 100 games; 10 minutes is standard").

    python tools/duel_eval.py --run duel_gru_v12 --inputs docs/INPUTS_v12.csv --opp nightmare --map bloodrun,aerowalk
    python tools/duel_eval.py --run duel_gru_v13 --opp policy:data/sim_runs/duel_gru_v12/policy_end_v12.pt --opp-inputs docs/INPUTS_v12.csv
    (Anaconda Python; --games 100 --minutes 10 --procs 16 by default; --set NAME=VALUE passes a simulator setting)

Opponents: "nightmare" = the stand-in for the game's Nightmare bot (the scripted item runner with the persona of that
name in sim/duel_env.py; for checks only, never a training opponent), "runner" = the plain item runner, or another
network ("policy:<file>"). Rules as on the server: the game's spawn (machine gun), spawn points away from the enemy,
one game without restarts; each seat's clock, score and memory start over as in its own training: every round_secs of its
checkpoint (120), or never for a network trained on whole games (round_secs 600: the game's clock; SeatClock). A network
trained with fewer inputs plays through its own list of input names (--inputs, --opp-inputs: docs/INPUTS_v11.csv for
v10 and v11, docs/INPUTS_v12.csv for v12).

Printed per map: the mean score of a game, his share of the frags with a 95% interval (resampled over games), games won,
and how he played: time without a big weapon, first weapon, stack, pickups, enemy in view, firing, speed (a player who
hides shows as few frags and little time in view).
"""
import argparse
import csv
import importlib
import json
import multiprocessing as mp_
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import pin  # noqa: E402  (PIN_CORES: a pool worker on a processor of its own)


def names(path):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(path, encoding="utf-8"))]


GAME_SECS = 600.0     # a seat whose round is this long or longer is a whole-games seat (the simulator's GAME_LEN)


def round_of(flag, pol, mp=""):
    """the seconds after which a seat's clock, score and memory start over: the flag when given, else his checkpoint's
    round_secs (test_suite.Policy; the trainer writes 600 for a network of whole games: never), 180 on arena1 as before"""
    if flag:
        return float(flag)
    r = float(getattr(pol, "round_secs", 0.0) or 120.0)
    return 180.0 if (mp == "arena1" and r == 120.0) else r


class SeatClock:
    """each seat of a check on the clock, score and memory of its own training (2026-10-13).
    rounds = (his, the opponent's) seconds; he, opp = the seats of the two sides (every match: one of each).
    A ROUND seat: the clock, the scores as it counts them and its memory start over every that many seconds.
    A GAME seat (GAME_SECS or more): seconds since the game's start that never wrap, the game's clock format and share
    left, one score for the game (a death by his own hand or the map: a point off him, as in training's whole games; it
    reaches his inputs a frame late), memory never reset.
    The share of the round LEFT (the v0.2 input): a round seat's runs from 1 to 0 over its round_secs and starts over with
    its clock, by the plugins' rule 1 - t / round_secs (the owner, 2026-10-13; in training it ran out over round_len times
    a factor drawn in 0.67 to 1.33 a round: after 80 to 160 s). left_full=True: the constant 1.0 the checks fed until
    then (--left-full: to reproduce older numbers). A game seat's is 1 - t / GAME_LEN either way.
    Use: before() ahead of every env.step(); after(t, events, (h, h2)) behind it (h2 None: a scripted opponent).
    A simulator module without clock_t (the frozen copies): what the tools always did, both seats on one round; the share
    left through the module's v02_left where it has one (the same rule, one clock for both seats)."""

    def __init__(self, E, env, he, opp, rounds, left_full=False):
        n = env.n
        gl = float(getattr(E, "GAME_LEN", GAME_SECS))
        self.E, self.env, self.sides, self.rounds = E, env, (np.asarray(he), np.asarray(opp)), [float(r) for r in rounds]
        self.game = [r >= gl for r in self.rounds]
        self.wrap = [max(1, int(r / E.DT)) for r in self.rounds]
        self.own = hasattr(env, "clock_t")
        self.left_full = bool(left_full)
        self.ct = np.zeros(n, np.float32)
        if not self.own:
            assert not any(self.game), "this simulator module has no clock for a whole-games network (no clock_t): use the current module"
            assert self.wrap[0] == self.wrap[1], "this simulator module keeps one clock for both seats: --round and --opp-round must be equal"
            return
        self.gs = np.zeros(n, bool)
        self.gs[self.sides[0]], self.gs[self.sides[1]] = self.game[0], self.game[1]
        self.tick = 0
        self.adj = np.zeros((n, 2), np.float32)
        self._zero(np.arange(n))
        env.clock_t, env.clock_game, env.clock_score = self.ct.copy(), self.gs, self.adj
        if not self.left_full:                               # a round seat's share left: 1 - t / round_secs (0: the simulator's own; a game seat's is the game's)
            cl_ = np.zeros(n, np.float64)
            cl_[self.sides[0]], cl_[self.sides[1]] = self.rounds[0], self.rounds[1]
            env.clock_len = np.where(self.gs, 0.0, cl_)

    def _zero(self, seats):
        """these seats count the score from here: his own and the other's stand at nothing"""
        fr = self.env.frags_r
        self.adj[seats, 0], self.adj[seats, 1] = np.float32(0) - fr[seats], np.float32(0) - fr[seats ^ 1]

    def before(self):
        if self.own:                                         # (as the simulator: a round's clock is a sum of float32 steps, a game's
            self.tick += 1                                   # is its frame count times the step)
            self.ct += self.E.DT
            tk_ = self.tick
            if getattr(self.E, "OVERTIME", False) and tk_ > self.E.GAME_FRAMES:    # (OVERTIME) a period: the last OT_LEN s again
                tk_ = int(self.env._ot_fold(tk_))
            self.env.clock_t = np.where(self.gs, np.float32(tk_ * self.E.DT), self.ct)
        elif not self.left_full and hasattr(self.env, "v02_left"):      # (a frozen module of v0.2: the same rule through its v02_left)
            self.ct += self.E.DT
            self.env.v02_left = np.clip(1.0 - self.ct.astype(np.float64) / max(self.rounds[0], 1e-3), 0.0, 1.0)

    def after(self, t, events, mem, pols=(None, None)):
        """mem: each side's memory array (None: a scripted side), pols: the Policy of each (v0.4: a head's tick clock is kept
        by Policy.clear)"""
        env = self.env

        def wipe(j, h_):
            if pols[j] is not None:
                pols[j].clear(h_)
            else:
                h_[:] = 0.0
        if not self.own:
            if (t + 1) % self.wrap[0] == 0:
                self.ct[:] = 0.0
                env.round_t[:] = 0.0
                env.frags_r[:] = 0
                for j_, h_ in enumerate(mem):
                    if h_ is not None:
                        wipe(j_, h_)
            return
        for e in events:                                     # a game seat's score: a death that is nobody's frag is a point off
            v, k = int(e["victim"]), int(e["killer"])
            if k < 0 or k == v:
                if self.gs[v]:
                    self.adj[v, 0] -= 1
                if self.gs[v ^ 1]:
                    self.adj[v ^ 1, 1] -= 1
        for s_, seats in enumerate(self.sides):
            if not self.game[s_] and (t + 1) % self.wrap[s_] == 0:
                self.ct[seats] = 0.0
                self._zero(seats)
                if mem[s_] is not None:
                    wipe(s_, mem[s_])

    def told(self):
        return dict(he=dict(round_secs=self.rounds[0], whole_game=bool(self.game[0])),
                    opponent=dict(round_secs=self.rounds[1], whole_game=bool(self.game[1])), per_seat=bool(self.own),
                    left="1.0 (--left-full)" if self.left_full else "1 - t / round_secs")


def play(job):
    (envmod, envvars, mp, games, minutes, seed, pol, idx, opp_kind, opp_pol, opp_idx, round_secs, swap, delays) = job
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    import test_suite as T_                                   # (B-226) each network's seats at the delays it was trained with; a scripted
    sw_ = int(bool(swap) and opp_pol is not None)             # opponent: his tracking delay, the simulator's own acquire delay
    set_ = T_.set_delays(E, env, [(np.arange(sw_, env.n, 2), delays[0], delays[1])]
                         + ([(np.arange(1 - sw_, env.n, 2), delays[2], delays[3])] if opp_pol is not None else []))
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0                                      # (v15: no jump runs in a check either)
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    scripted = opp_kind in ("nightmare", "runner", "holder", "lobber", "watcher")
    env.runner_p = 1.0 if scripted else 0.0
    if getattr(env, "lab", None) is not None:
        env.lab_force = dict(kind=E.NORMAL, arena=3)
        env.arena_len = 1e9
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9                          # one game, no restarts
    env.round_t[:] = 0.0
    ev, od = np.arange(0, n, 2), np.arange(1, n, 2)
    swap = bool(swap) and opp_pol is not None                # --swap: he sits on the odd seats in this job (two networks only)
    if swap:
        ev, od = od, ev
    if scripted:
        env.script[od] = 3
        env.sc_persona[od] = E.NIGHTMARE if opp_kind == "nightmare" else E.PERSONAS.index(opp_kind) if opp_kind in E.PERSONAS else 0
    else:
        env.script[od] = 0
    env.script[ev] = 0
    pol.rng = np.random.default_rng(seed)
    h = pol.zeros(len(ev))
    if opp_pol is not None:
        opp_pol.rng = np.random.default_rng(seed + 1)
        h2 = opp_pol.zeros(len(od))
    big = [E.RL, E.RG, E.LG]
    score = np.zeros(n)
    kills = np.zeros(n)
    c = {k: np.zeros(2) for k in ("alive", "bare", "over150", "vis", "fire", "speed", "wp", "mega", "red", "yellow", "lives", "restarts",
                                  "standing", "stuck", "own_deaths", "fire_vis", "both", "lower", "higher", "vis_lower", "vis_higher", "empty", "empty_fire",
                                  "legs", "at400",        # (LEGS) frames his legs carried him; frames at 400 units a second or more
                                  "unseen_hits", "unseen_dmg",    # hits he takes (10 points or more on a frame) while the other side has nobody in view
                                  "exposed", "watching")}         # the other side has him in view and he has nobody in view; the reverse
    still = np.zeros(n)                                         # seconds he has been standing (under 50 units a second)
    life, got, was = np.zeros(n), np.zeros(n, bool), np.zeros(n, bool)
    first = [[], []]
    hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), env.has[:, big].copy()
    frames = int(minutes * 60 / E.DT)
    sc_ = SeatClock(E, env, ev, od, (round_secs[0], round_secs[1] if opp_pol is not None else round_secs[0]), left_full=round_secs[2])    # (he first, as ev)
    # the simulator's own counters (they count the learner's side): damage, shots, hits and frags by weapon, the weapon in
    # hand by distance, his speed toward an enemy in view by strength, how well he knows where the enemy is, dropped weapons
    SK = [k for k in ["dmg_h", "dmg_from_script", "w_dist", "close_v", "close_n", "know", "know_frames", "drops", "pick_drop",
                      "pick_drop_new", "self_dmg", "fall_dmg", "lob", "sc_frags_w"]
          + [w + x for w in E.WEAPONS for x in ("_frags", "_shots", "_hits")] if k in env.stats]
    for k_, n_, on_ in (("big_seq", 6, bool(getattr(E, "BIG_PICK_SEQ", ()))), ("rg_far", 4, getattr(E, "RG_FAR_PRICE", 0.0) > 0)):
        if on_:                                                 # (v0.3.8) counters a simulator makes at their first use: made now
            env.stats.setdefault(k_, np.zeros(n_))
    SK += [k for k in ("rail", "big_seq", "rg_far") if k in env.stats]   # (the raw counters, every seat: --json's st_raw)
    st0 = {k: np.array(env.stats[k], np.float64).copy() for k in SK}
    side = (np.arange(n) + int(swap)) % 2                       # 0: he, 1: the opponent
    # by the kind of life (STYLE_P, STYLE_MIX; a scripted player's lives are all general): rows he / the opponent, columns
    # the styles. His frames alive, with the enemy in view, with rockets / rail / lightning in hand while in view; his
    # frags and his deaths of any kind, by the style of the life they fell in
    SN_ = list(E.STYLES) if hasattr(env, "style") else ["general"]
    NS_, SZ_ = len(SN_), np.zeros(n, np.int64)
    sty = dict(alive=np.zeros((2, NS_)), vis=np.zeros((2, NS_)), hand=np.zeros((2, NS_, 3)), frags=np.zeros((2, NS_)), deaths=np.zeros((2, NS_)),
               lives=np.zeros((2, NS_)))
    # (OVERTIME, 2026-10-22) a game level at the limit goes on in periods of OT_LEN, up to OT_CAP, as in training and the game;
    # a game decided keeps the score it had when it ended; the counters are the regulation minutes'
    OT_ = bool(getattr(E, "OVERTIME", False))
    end_ = frames
    final = None
    ot_n, reg_ = 0, None
    t = -1
    while t + 1 < end_:
        t += 1
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        hev_ = None                                                             # (v0.4) the heads' tick events: one call of the simulator for both sides
        if hasattr(env, "head_events") and (pol.head_due(h).any() or (opp_pol is not None and opp_pol.head_due(h2).any())):
            hev_ = env.head_events()
        xlu_ = None                                                             # (--legs-feat, --legs-guide) the branch's inputs of this frame
        if getattr(E, "LEGS_IN", False) and (getattr(pol, "needs_xl", False) or getattr(opp_pol, "needs_xl", False)):
            xlu_ = env.legs_prep()                                              # (nothing between here and the step changes a target)
        al, h = pol.act(obs[ev][:, idx], h, None if hev_ is None else hev_[ev], xl=None if xlu_ is None else xlu_[ev])
        a[ev, :min(al.shape[1], a.shape[1])] = al[:, :a.shape[1]]          # (a network with an output the module lacks: LEGS_TURN_ADD off)
        if opp_pol is not None:
            ao, h2 = opp_pol.act(obs[od][:, opp_idx], h2, None if hev_ is None else hev_[od], xl=None if xlu_ is None else xlu_[od])
            a[od, :min(ao.shape[1], a.shape[1])] = ao[:, :a.shape[1]]
        sty0 = np.where(env.script == 0, env.style, 0) if NS_ > 1 else SZ_      # (the style of the life a frag or a death of this step
        sc_.before()
        if getattr(E, "LEGS_IN", False) and (pol.legsP is not None or (opp_pol is not None and opp_pol.legsP is not None)):
            xl_ = env.legs_prep()                                               # (LEGS_IN, B-253) the branch of each side's network
            lg_ = None
            lgs_ = [(ev, pol)] + ([(od, opp_pol)] if opp_pol is not None else [])
            if all(p_.legsP is not None for _, p_ in lgs_) or (env.teacher is not None and not getattr(env.teacher, "c2", 0)):
                lg_ = np.zeros((n, 17), np.float32)
                for m_, p_ in lgs_:
                    if p_.legsP is not None:
                        lg_[m_] = p_.legs_logits(xl_[m_])          # (--legs-residual: from the memory of its act() above)
                    else:                                                       # (--legs-learn, B-253 stage b) a side without the branch (the
                        w0_, b0_, w1_, b1_, wp_, bp_ = env.teacher_w[:6]        # control) moves on the movement network's own sums, the other on
                        lg_[m_] = np.tanh(np.tanh(xl_[m_] @ w0_.T + b0_) @ w1_.T + b1_) @ wp_.T + bp_    # its learnt branch
            env.legs_lg = lg_                                                   # (None: the simulator's own sums for all)
        obs, r, done, info = env.step(a)                                        # falls in; a scripted seat's is never drawn: general)
        c["restarts"][0] += int(done.any())
        died = np.zeros(n, bool)                                # (a death and the respawn fall in the same step here)
        for e in info["events"]:
            v, k = int(e["victim"]), int(e["killer"])
            died[v] = True
            sty["deaths"][side[v], sty0[v]] += 1
            if k >= 0 and k != v:
                score[k] += 1
                kills[k] += 1
                sty["frags"][side[k], sty0[k]] += 1
            else:
                score[v] -= 1                                   # his own hand or the map: a point off, as in the game
                c["own_deaths"][side[v]] += 1
        alive = env.hp > 0
        nbig = env.has[:, big].sum(1)
        new = (alive & ~was) | died
        life = np.where(new, 0.0, life + E.DT)
        got &= ~new
        hit = alive & ~got & (nbig > 0)
        for s_ in (0, 1):
            first[s_] += life[hit & (side == s_)].tolist()
        got |= hit
        same = alive & was & ~died
        gain_w = (env.has[:, big] & ~has0).sum(1) * same
        dh, da = (env.hp - hp0) * same, (env.armor - ar0) * same
        vis = env.visible & alive
        sty1 = np.where(env.script == 0, env.style, 0) if NS_ > 1 else SZ_
        np.add.at(sty["lives"], (side[new], sty1[new]), 1)      # (lives begun)
        np.add.at(sty["alive"], (side[alive], sty1[alive]), 1)
        np.add.at(sty["vis"], (side[vis], sty1[vis]), 1)
        for j_, w_ in enumerate(big):
            m_ = vis & (env.weapon == w_)
            np.add.at(sty["hand"], (side[m_], sty1[m_], j_), 1)
        spd = np.hypot(env.state[:, 3], env.state[:, 4])
        still = np.where(alive & (spd < 50.0) & ~died, still + E.DT, 0.0)
        other = np.arange(len(alive)) ^ 1                         # who stands higher (B-160: he fights from below)
        both = alive & alive[other]
        up = env.state[:, 2] - env.state[other, 2]
        for s_ in (0, 1):
            m = side == s_
            c["both"][s_] += both[m].sum()
            c["lower"][s_] += (both & (up < -48.0))[m].sum()
            c["higher"][s_] += (both & (up > 48.0))[m].sum()
            c["vis_lower"][s_] += (vis & both & (up < -48.0))[m].sum()
            c["vis_higher"][s_] += (vis & both & (up > 48.0))[m].sum()
            c["alive"][s_] += alive[m].sum()
            c["bare"][s_] += (alive & (nbig == 0))[m].sum()
            c["over150"][s_] += (alive & (env.hp + env.armor >= 150))[m].sum()
            c["vis"][s_] += vis[m].sum()
            c["fire"][s_] += (env.fire_last & alive)[m].sum()        # (the button as it is after the finger limits; scripted players too)
            c["fire_vis"][s_] += (env.fire_last & vis)[m].sum()
            dry = alive & (env.weapon != E.G) & (env.ammo[np.arange(len(alive)), env.weapon] <= 0)    # a weapon with nothing left in hand ("fighting without ammo", a player's note of 2026-10-09)
            c["empty"][s_] += dry[m].sum()
            c["empty_fire"][s_] += (dry & env.fire_last)[m].sum()
            c["speed"][s_] += spd[alive & m].sum()
            c["legs"][s_] += (getattr(env, "legs_on", np.zeros(len(alive), bool)) & alive)[m].sum()
            c["at400"][s_] += (alive & (spd >= 400.0))[m].sum()
            if env.n == 2 * (env.n // 2) and getattr(env, "G", 2) == 2:      # (duels: "the other side" is one player)
                hit_ = same & ((dh + da) <= -10.0) & ~vis[other] & alive[other]
                c["unseen_hits"][s_] += hit_[m].sum()
                c["unseen_dmg"][s_] += -(dh + da)[hit_ & m].sum()
                c["exposed"][s_] += (alive & ~vis & vis[other])[m].sum()
                c["watching"][s_] += (vis & alive[other] & ~vis[other])[m].sum()
            c["standing"][s_] += (alive & (spd < 50.0))[m].sum()
            c["stuck"][s_] += (still > 3.0)[m].sum()
            c["wp"][s_] += gain_w[m].sum()
            c["mega"][s_] += (dh >= 60)[m].sum()
            c["red"][s_] += (da >= 75)[m].sum()
            c["yellow"][s_] += ((da >= 40) & (da < 75))[m].sum()
            c["lives"][s_] += new[m].sum()
        was = alive.copy()
        hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), env.has[:, big].copy()
        sc_.after(t, info["events"], (h, h2 if opp_pol is not None else None), (pol, opp_pol))    # a round seat's clock, score and memory start over; a game seat's never
        if t + 1 == end_:
            sp_ = score.reshape(-1, 2)
            if final is None:                                   # the regulation limit
                final = sp_.copy()
                import copy as _cp
                reg_ = (kills.copy(), _cp.deepcopy(c), _cp.deepcopy(sty), [list(x) for x in first],
                        {k: np.array(env.stats[k], np.float64).copy() for k in SK})
                live_ = final[:, 0] == final[:, 1]
            else:                                               # a period's end: the games still in it take its score
                final[live_] = sp_[live_]
                live_ = live_ & (sp_[:, 0] == sp_[:, 1])
            if OT_ and live_.any() and ot_n < int(getattr(E, "OT_CAP", 10)):
                ot_n += 1
                end_ += int(round(float(getattr(E, "OT_LEN", 120.0)) / E.DT))
    if reg_ is not None:
        kills, c, sty, first, st_reg = reg_
        score = final.reshape(-1)
    else:
        st_reg = {k: np.array(env.stats[k], np.float64) for k in SK}
    flip = slice(None, None, -1) if swap else slice(None)
    return dict(score=score.reshape(-1, 2)[:, flip].tolist(), kills=kills.reshape(-1, 2)[:, flip].tolist(), c={k: v.tolist() for k, v in c.items()},
                overtime_periods=ot_n,
                first=first, minutes=minutes, games=games, weapons=list(E.WEAPONS), clock=sc_.told(),
                sty={k: v.tolist() for k, v in sty.items()}, styles=SN_, delays=set_,
                st={k: (st_reg[k] - st0[k]).tolist() for k in SK})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"), help="the list of input names the network was trained with")
    ap.add_argument("--opp", default="nightmare", help="nightmare, runner, or policy:<file>")
    ap.add_argument("--opp-inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--map", default="arena1,bloodrun,aerowalk,lostworld")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=16)
    ap.add_argument("--round", type=float, default=0.0, help="his clock, score and memory start over every this many seconds; 600 or more: never, and the "
                    "whole game's clock (default: his checkpoint's round_secs: 120 for a network of two-minute rounds, 600 for one of whole games; 180 on arena1)")
    ap.add_argument("--opp-round", type=float, default=0.0, help="... of the opponent network (default: its checkpoint's)")
    ap.add_argument("--left-full", action="store_true", help="a round seat's 'time left in the round' input stays at 1.0, as the checks fed it until 2026-10-13 "
                    "(default: it runs from 1 to 0 over his round, 1 - t / round_secs, as on the server); to reproduce older numbers")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator setting (environment variable) for these games")
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--react-ms", type=float, default=None, help="his tracking delay on an enemy in view (default: his checkpoint's react_ms)")
    ap.add_argument("--acquire-ms", type=float, default=None, help="his delay before an enemy who has just come into view is noticed (default: his "
                                                                    "checkpoint's acquire_ms, the trainer's --acquire-ms; B-226)")
    ap.add_argument("--opp-react-ms", type=float, default=None, help="... of the opponent network (default: its checkpoint's). A scripted opponent "
                                                                      "always has his tracking delay and the simulator's own 200 ms")
    ap.add_argument("--opp-acquire-ms", type=float, default=None)
    ap.add_argument("--swap", action="store_true", help="two networks: every second process seats him on the odd seats (the same network on both "
                    "sides got 47 percent of the frags on the even seats: B-220); give --procs an even number")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    import test_suite as T
    path = a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt")
    pol = T.Policy(path, seed=1)
    now = names(os.path.join(ROOT, "docs", "INPUTS.csv"))
    old = names(a.inputs)
    assert len(old) == len(pol.mean), "the network has {} inputs, {} lists {}".format(len(pol.mean), a.inputs, len(old))
    idx = np.array([now.index(x) for x in old])
    opp_pol, opp_idx, kind = None, None, a.opp
    if a.opp.startswith("policy:"):
        opp_pol = T.Policy(a.opp[7:], seed=2)
        oo = names(a.opp_inputs)
        assert len(oo) == len(opp_pol.mean), "the opponent has {} inputs, {} lists {}".format(len(opp_pol.mean), a.opp_inputs, len(oo))
        opp_idx = np.array([now.index(x) for x in oo])
        kind = "policy"
    envvars = dict(x.split("=", 1) for x in a.set)
    delays = (pol.react_ms if a.react_ms is None else a.react_ms, pol.acquire_ms if a.acquire_ms is None else a.acquire_ms,
              None if opp_pol is None else (opp_pol.react_ms if a.opp_react_ms is None else a.opp_react_ms),
              None if opp_pol is None else (opp_pol.acquire_ms if a.opp_acquire_ms is None else a.opp_acquire_ms))
    dl_out = None
    out = {}
    for mp in a.map.split(","):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        jobs = [(a.env, envvars, mp, g, a.minutes, a.seed + 17 * k, pol, idx, kind, opp_pol, opp_idx,
                 (round_of(a.round, pol, mp), round_of(a.opp_round, opp_pol, mp) if opp_pol is not None else round_of(a.round, pol, mp), a.left_full),
                 a.swap and k % 2 == 1, delays) for k, g in enumerate(per) if g > 0]
        with mp_.Pool(len(jobs), initializer=pin.pin_pool_worker) as pool:
            res = pool.map(play, jobs)
        sc = np.concatenate([np.array(r["score"]) for r in res])
        kl = np.concatenate([np.array(r["kills"]) for r in res])
        c = {k: np.sum([r["c"][k] for r in res], 0) for k in res[0]["c"]}
        first = [np.concatenate([np.array(r["first"][s_]) for r in res]) if any(r["first"][s_] for r in res) else np.array([np.nan]) for s_ in (0, 1)]
        G = len(sc)
        rng = np.random.default_rng(0)
        share = lambda k_: float(k_[:, 0].sum() / max(1.0, k_.sum()))
        boot = [share(kl[rng.integers(0, G, G)]) for _ in range(1000)]
        pm = G * a.minutes                                       # player-minutes of each side
        row = {}
        dl_out = res[0].get("delays")
        sy, SN = {k: np.sum([np.array(r["sty"][k]) for r in res], 0) for k in res[0]["sty"]}, res[0]["styles"]
        for s_, who in ((0, "he"), (1, "opponent")):
            al = max(1.0, c["alive"][s_])
            row[who] = dict(score=round(float(sc[:, s_].mean()), 2), kills=round(float(kl[:, s_].mean()), 2),
                            time_bare=round(float(c["bare"][s_] / al), 3), first_weapon_s=round(float(np.nanmedian(first[s_])), 1),
                            stack_150_up=round(float(c["over150"][s_] / al), 3), in_view=round(float(c["vis"][s_] / al), 3),
                            firing=round(float(c["fire"][s_] / al), 3), speed=int(c["speed"][s_] / al),
                            firing_in_view=round(float(c["fire_vis"][s_] / max(1.0, c["vis"][s_])), 3),
                            standing=round(float(c["standing"][s_] / al), 3), standing_over_3s=round(float(c["stuck"][s_] / al), 3),
                            own_deaths=round(float(c["own_deaths"][s_] / G), 2),
                            legs=round(float(c["legs"][s_] / al), 3), at_400=round(float(c["at400"][s_] / al), 4),   # (LEGS) of his time alive: on his legs; at 400 units a second or more
                            unseen_hits_per_min=round(float(c["unseen_hits"][s_] / pm), 3), unseen_dmg_per_min=round(float(c["unseen_dmg"][s_] / pm), 2),   # taken while the other side had nobody in view
                            exposed=round(float(c["exposed"][s_] / al), 4), watching=round(float(c["watching"][s_] / al), 4),   # of his time alive: seen without seeing; seeing without being seen
                            empty_in_hand=round(float(c["empty"][s_] / al), 4), firing_empty=round(float(c["empty_fire"][s_] / max(1.0, c["fire"][s_])), 4),   # of his time alive; of his firing
                            lower=round(float(c["lower"][s_] / max(1.0, c["both"][s_])), 3), higher=round(float(c["higher"][s_] / max(1.0, c["both"][s_])), 3),   # of the time both live: lower or higher by 48 units or more
                            lower_in_view=round(float(c["vis_lower"][s_] / max(1.0, c["vis"][s_])), 3), higher_in_view=round(float(c["vis_higher"][s_] / max(1.0, c["vis"][s_])), 3),
                            weapons_per_min=round(float(c["wp"][s_] / pm), 2),
                            mega_share=round(float(c["mega"][s_] / (pm * 60 / 35.0)), 3), red_share=round(float(c["red"][s_] / (pm * 60 / 25.0)), 3),
                            yellow_per_min=round(float(c["yellow"][s_] / pm), 2), lives_per_min=round(float(c["lives"][s_] / pm), 2))
            # by the kind of life: lives begun; the share of his time alive in such lives; frags, deaths (of any kind) and frags a
            # death; of that time the share with the enemy in view; of the time in view the share with each of the three in hand
            row[who]["by_style"] = {nm: dict(lives=int(sy["lives"][s_, j]), time=round(float(sy["alive"][s_, j] / max(1.0, sy["alive"][s_].sum())), 3),
                                             frags=int(sy["frags"][s_, j]), deaths=int(sy["deaths"][s_, j]),
                                             frags_per_death=round(float(sy["frags"][s_, j] / max(1.0, sy["deaths"][s_, j])), 2),
                                             in_view=round(float(sy["vis"][s_, j] / max(1.0, sy["alive"][s_, j])), 3),
                                             in_hand_in_view={w: round(float(sy["hand"][s_, j, q] / max(1.0, sy["vis"][s_, j])), 3)
                                                              for q, w in enumerate(("rl", "rg", "lg"))})
                                    for j, nm in enumerate(SN)}
        st = {k: np.sum([np.array(r["st"][k]) for r in res], 0) for k in res[0].get("st", {})}
        if "sc_frags_w" in st:                               # (staging) the scripted opponent's frags by weapon
            row["opponent"]["frags_w"] = {w: float(x) for w, x in zip(res[0]["weapons"], np.array(st["sc_frags_w"])) if x > 0}
        row["st_raw"] = {k: np.asarray(st[k], np.float64).tolist() for k in ("rail", "big_seq", "rg_far") if k in st}
        if "lob" in st:                                      # (staging) the lobber's frames firing at a place: plasma, grenades; at an exit
            row["opponent"]["lob"] = [float(x) for x in np.array(st["lob"])]
        if st:                                               # the learner's side, from the simulator's counters
            W_ = res[0]["weapons"]
            big4 = [w for w in ("rl", "lg", "rg", "mg") if w + "_frags" in st]
            fr = max(1.0, float(sum(st[w + "_frags"] for w in W_ if w + "_frags" in st)))
            row["he"].update(
                dmg_dealt=round(float(st["dmg_h"]) / G, 0) if "dmg_h" in st else None,
                dmg_taken_from_him=round(float(st["dmg_from_script"]) / G, 0) if "dmg_from_script" in st else None,
                frags_by={w: round(float(st[w + "_frags"]) / fr, 2) for w in big4},
                hit_rate={w: round(float(st[w + "_hits"]) / max(1.0, float(st[w + "_shots"])), 3) for w in big4 if w + "_shots" in st},
                shots_per_min={w: round(float(st[w + "_shots"]) / pm, 1) for w in big4 if w + "_shots" in st})
            if "w_dist" in st:
                wd = np.array(st["w_dist"])
                row["he"]["in_hand_by_distance"] = {b: {w: round(float(wd[j, W_.index(w)] / max(1.0, wd[j].sum())), 2) for w in big4}
                                                    for j, b in enumerate(("close", "mid", "far"))}
            if "close_v" in st:
                row["he"]["closing"] = [int(v_ / max(1.0, n_)) for v_, n_ in zip(np.atleast_1d(st["close_v"]), np.atleast_1d(st["close_n"]))]
                row["he"]["in_view_by_strength"] = [round(float(n_ / max(1.0, np.sum(st["close_n"]))), 2) for n_ in np.atleast_1d(st["close_n"])]
            if "know" in st:
                row["he"]["know"] = round(float(st["know"]) / max(1.0, float(st["know_frames"])), 3)
            if "drops" in st:
                row["he"]["dropped_weapons"] = dict(fell_per_game=round(float(st["drops"]) / G, 1), taken_per_game=round(float(st["pick_drop"]) / G, 1),
                                                    new_to_taker=round(float(st["pick_drop_new"]) / max(1.0, float(st["pick_drop"])), 2))
        out[mp] = dict(games=G, minutes=a.minutes, clock=res[0].get("clock"), frag_share=round(share(kl), 3), frag_share_95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                       won=int((sc[:, 0] > sc[:, 1]).sum()), drawn=int((sc[:, 0] == sc[:, 1]).sum()), lost=int((sc[:, 0] < sc[:, 1]).sum()),
                       restarts=int(c["restarts"][0]), **row)
        o = out[mp]
        print("{} | {} against {} | {} games of {:g} min | score {:.1f} : {:.1f} | his share of the frags {:.0%} ({:.0%} to {:.0%}) | won {} drawn {} lost {}".format(
            mp, a.run or os.path.basename(path), a.opp, G, a.minutes, o["he"]["score"], o["opponent"]["score"], o["frag_share"],
            o["frag_share_95"][0], o["frag_share_95"][1], o["won"], o["drawn"], o["lost"]))
        ck_ = o.get("clock") or {}
        if any(ck_.get(w_, {}).get("round_secs", 120.0) != 120.0 for w_ in ("he", "opponent")):      # (said only where a seat is not on two-minute rounds)
            print("    clocks: " + " | ".join("{} {}".format(w_, "the whole game (clock, score and memory never start over)" if ck_[w_]["whole_game"]
                                                             else "rounds of {:g} s".format(ck_[w_]["round_secs"])) for w_ in ("he", "opponent")), flush=True)
        for who in ("he", "opponent"):
            w = o[who]
            print("    {:9s} bare {:.0%} | first weapon {} s | 150+ {:.0%} | weapons {}/min | mega {:.0%}, red {:.0%} of spawns | yellow {}/min | in view {:.0%} | firing {:.0%} ({:.0%} of the time in view) | speed {}, standing {:.0%} (over 3 s: {:.0%}) | lives {}/min, own deaths {} a game".format(
                who, w["time_bare"], w["first_weapon_s"], w["stack_150_up"], w["weapons_per_min"], w["mega_share"], w["red_share"],
                w["yellow_per_min"], w["in_view"], w["firing"], w["firing_in_view"], w["speed"], w["standing"], w["standing_over_3s"], w["lives_per_min"], w["own_deaths"]), flush=True)
        for who in ("he", "opponent"):                           # by the kind of life (nothing to say where every life is general)
            bs = o[who].get("by_style") or {}
            if sum(1 for v_ in bs.values() if v_["time"] > 0) > 1:
                print("    {:9s} by life: ".format(who) + " | ".join(
                    "{} {} lives, {:.0%} of his time, {:.2f} frags a death ({}:{}), in view with rl {:.0%} rg {:.0%} lg {:.0%}".format(
                        nm, v_["lives"], v_["time"], v_["frags_per_death"], v_["frags"], v_["deaths"], v_["in_hand_in_view"]["rl"],
                        v_["in_hand_in_view"]["rg"], v_["in_hand_in_view"]["lg"]) for nm, v_ in bs.items()), flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(run=a.run, policy=path, opp=a.opp, env=a.env, set=envvars, delays_ms=dl_out, maps=out), f, indent=1)


if __name__ == "__main__":
    main()

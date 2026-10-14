"""Counterplay, measured (the owner, 2026-10-13: "playing aggressively when stacked vs. the enemy, not picking fights when
weak, controlling/avoiding items"): ten-minute duels in the simulator as tools/duel_eval.py plays them, read by how he
stands against the enemy at each moment.

    python tools/counterplay.py --policy <a.pt> --opp policy:<b.pt> --map bloodrun,aerowalk --games 16 --swap --json out.json
    (Anaconda Python; --inputs, --opp-inputs, --set, --round, --react-ms as tools/duel_eval.py)

How he stands (the owner's choice): AHEAD = his health and armor 50 or more above the enemy's and a big weapon (rockets,
rail, lightning) in his bag; WEAK = 50 or more below, or no big weapon; EVEN = the rest. The true stacks, as a spectator
sees them: what he could know of them is his own business.

What is read, for him and for the opponent alike, by AHEAD / EVEN / WEAK:
  press / back off   his speed toward the enemy while he has him in view (units a second; minus = he opens the distance)
                     and the share of that time with the enemy in view
  fights             a fight = damage between the two after three seconds without any, to three seconds after the last or
                     a death: fights a minute of that standing, the share he started (the first damage was his), how they
                     ended (the enemy died / he died), damage dealt against damage taken
  items              the mega health and the red armor: his share of those taken while he stood so, how late after the
                     item came back (s), and how far the enemy was at any of his health and armor pickups (units)
  variety            his pickups in order, life by life (the big weapons, mega, red and yellow armor): how often the next
                     one is the commonest follower of the last ("top-1": 1 = the same round every life) and the spread
                     of the followers in bits; the first pickup by spawn place apart (an opening is meant to be fixed)
measure() takes a game as plain arrays (a trace), so the pros' demos are read by the same code (tools/counterplay_pros.py).
A trace: dt (seconds a sample; 0.125 here: every fifth frame of 25 ms), and by sample and player (he first): pos (T,2,3), hp, armor (T,2), has (T,2,3:
rockets, rail, lightning in his bag), alive, died (he died since the last sample), vis (he has the enemy in view)."""
import argparse
import importlib
import json
import math
import multiprocessing as mp_
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

BANDS = ("ahead", "even", "weak")
GAP = 50.0            # health and armor ahead of or behind the enemy
QUIET = 3.0           # seconds without damage that end a fight
MIN_DMG = 20.0        # a fight under this much damage in all is not counted
DECAY = 2.5           # a fall of his stack under this in one sample is the tick of a stack above 100, not damage
RESPAWN = dict(mega=35.0, red=25.0)
EVERY = 5             # a sample every this many simulator frames
BIGN = ("RL", "RG", "LG")
KEYS = ("time", "view", "close_sum", "close_n", "fights", "started", "won", "lost", "dealt", "taken", "big", "opp_big", "item_dist", "item_n", "late_sum", "late_n")


def bands(stack, big):
    adv = stack - stack[:, ::-1]
    b = np.ones(adv.shape, np.int64)
    b[(adv >= GAP) & big] = 0
    b[(adv <= -GAP) | ~big] = 2
    return b


def measure(tr):
    """a game's trace -> counters (KEYS: arrays [player, standing]; "trans": per player {"a>b": n}; "lives")"""
    dt = float(tr["dt"])
    pos, hp, ar = np.asarray(tr["pos"], np.float64), np.asarray(tr["hp"], np.float64), np.asarray(tr["armor"], np.float64)
    has, alive, died, vis = np.asarray(tr["has"], bool), np.asarray(tr["alive"], bool), np.asarray(tr["died"], bool), np.asarray(tr["vis"], bool)
    stack = hp + ar
    b = bands(stack, has.any(2))
    dist = np.linalg.norm(pos[:, 0] - pos[:, 1], axis=1)
    both = alive.all(1)
    same = both[1:] & both[:-1] & ~died[1:].any(1)
    close = -(dist[1:] - dist[:-1]) / dt
    c = {k: np.zeros((2, 3)) for k in KEYS}
    for p in (0, 1):
        for k in range(3):
            m = both[:-1] & (b[:-1, p] == k)
            mv = m & vis[:-1, p]
            mc = mv & same & (np.abs(close) < 2000.0)        # (a teleporter is not a step toward him)
            c["time"][p, k], c["view"][p, k] = m.sum() * dt, mv.sum() * dt
            c["close_sum"][p, k], c["close_n"][p, k] = close[mc].sum(), mc.sum()
    # ---- damage by the enemy: the victim's stack falls while the other has him in view or stands close
    d = np.zeros((len(pos) - 1, 2))
    for p in (0, 1):
        o = 1 - p
        fell = np.where(died[1:, p], stack[:-1, p], np.maximum(0.0, stack[:-1, p] - stack[1:, p]))
        fell = np.where(fell < DECAY, 0.0, fell)             # (health and armor above 100 tick down by one a second: not a hit)
        by = alive[:-1, o] & (vis[:-1, o] | vis[1:, o] | (dist[:-1] < 600.0))
        d[:, p] = fell * (alive[:-1, p] & by)
    fight, last = None, -1e9

    def end(f):
        if f is None or f["dmg"].sum() < MIN_DMG:
            return
        for p in (0, 1):
            k = f["b"][p]
            c["fights"][p, k] += 1
            c["started"][p, k] += f["starter"] == p
            c["won"][p, k] += f["dead"] == 1 - p
            c["lost"][p, k] += f["dead"] == p
            c["dealt"][p, k] += f["dmg"][1 - p]
            c["taken"][p, k] += f["dmg"][p]

    for t in np.nonzero(d.sum(1) >= 1.0)[0]:
        if fight is None or (t - last) * dt > QUIET:
            end(fight)
            fight = dict(b=(int(b[t, 0]), int(b[t, 1])), starter=int(np.argmin(d[t])), dmg=np.zeros(2), dead=-1)   # (the starter: the one who took less)
        fight["dmg"] += d[t]
        last = t
        dead = np.nonzero(died[t + 1] & (d[t] > 0))[0]
        if len(dead):
            fight["dead"] = int(dead[0])
            end(fight)
            fight = None
    end(fight)
    # ---- pickups (a jump of his health or armor inside a life) and the weapons he gains
    trans, lives = [Counter(), Counter()], [0, 0]
    took = {}                                                # (kind, place) -> the time it was last taken
    ev = []
    for p in (0, 1):
        ok = alive[1:, p] & alive[:-1, p] & ~died[1:, p]
        dh, da = (hp[1:, p] - hp[:-1, p]) * ok, (ar[1:, p] - ar[:-1, p]) * ok
        for kind, m in (("mega", dh >= 60.0), ("red", da >= 75.0), ("yellow", (da >= 40.0) & (da < 75.0))):
            ev += [(int(t), p, kind) for t in np.nonzero(m)[0]]
        gain = has[1:, p] & ~has[:-1, p] & ok[:, None]
        ev += [(int(t), p, BIGN[j]) for t, j in zip(*np.nonzero(gain))]
    life = np.cumsum(died, 0)
    prev = {}
    for t, p, kind in sorted(ev):
        o, k = 1 - p, int(b[t, p])
        q = "{}:{}:{}".format(kind, int(pos[t + 1, p, 0] // 256), int(pos[t + 1, p, 1] // 256)) if kind in ("mega", "red", "yellow") else kind
        if kind in ("mega", "red", "yellow"):
            c["item_dist"][p, k] += dist[t]
            c["item_n"][p, k] += 1
        if kind in RESPAWN:
            c["big"][p, k] += 1
            c["opp_big"][o, int(b[t, o])] += 1
            late = t * dt - took.get(q, -1e9) - RESPAWN[kind]
            if 0.0 <= late < 60.0:
                c["late_sum"][p, k] += late
                c["late_n"][p, k] += 1
            took[q] = t * dt
        key = (p, int(life[t + 1, p]))
        if prev.get(p, (None,))[0] != key:                   # the life's first pickup: by where he came into the game
            s = np.nonzero(life[:, p] == key[1])[0][0]
            a = "spawn:{}:{}".format(int(pos[s, p, 0] // 256), int(pos[s, p, 1] // 256))
            lives[p] += 1
        else:
            a = prev[p][1]
        trans[p][a + ">" + q] += 1
        prev[p] = (key, q)
    out = {k: v.tolist() for k, v in c.items()}
    out["trans"] = [dict(x) for x in trans]
    out["lives"] = lives
    return out


def add(a, b):
    if a is None:
        return b
    out = {k: (np.array(a[k]) + np.array(b[k])).tolist() for k in KEYS}
    out["trans"] = [dict(Counter(a["trans"][p]) + Counter(b["trans"][p])) for p in (0, 1)]
    out["lives"] = [a["lives"][p] + b["lives"][p] for p in (0, 1)]
    return out


def variety(tr, first):
    """top-1 share and spread (bits) of what follows what; first: the life's first pickup by spawn place, or the rest"""
    by = {}
    for k, n in tr.items():
        a, q = k.split(">")
        if a.startswith("spawn") == first:
            by.setdefault(a, Counter())[q] += n
    tot = sum(sum(v.values()) for v in by.values())
    if not tot:
        return None, None, 0
    top = sum(max(v.values()) for v in by.values()) / tot
    h = -sum(n * math.log2(n / sum(v.values())) for v in by.values() for n in v.values()) / tot
    return round(top, 3), round(h, 2), int(tot)


def summary(c):
    """the counters as the numbers a reader wants, for him (0) and the opponent (1)"""
    out = {}
    for p, who in ((0, "he"), (1, "opponent")):
        g = lambda k: np.array(c[k][p])
        div = lambda x, y, nd=2: [None if b_ <= 0 else round(float(a_ / b_), nd) for a_, b_ in zip(x, y)]
        o = dict(time_share=div(g("time"), [g("time").sum()] * 3), in_view=div(g("view"), g("time")), closing=div(g("close_sum"), g("close_n"), 0),
                 fights_per_min=div(g("fights") * 60.0, g("time")), started=div(g("started"), g("fights")), won=div(g("won"), g("fights")),
                 lost=div(g("lost"), g("fights")), dealt_per_taken=div(g("dealt"), g("taken")), fights=[int(x) for x in g("fights")],
                 big_item_share=div(g("big"), g("big") + g("opp_big")), big_items=[int(x) for x in g("big")], late_s=div(g("late_sum"), g("late_n"), 1),
                 enemy_at_pickup=div(g("item_dist"), g("item_n"), 0))
        o = {k: dict(zip(BANDS, v)) for k, v in o.items()}
        t1, h1, n1 = variety(c["trans"][p], False)
        t0, h0, n0 = variety(c["trans"][p], True)
        o["variety"] = dict(next_top1=t1, next_bits=h1, pickups=n1, opening_top1=t0, opening_bits=h0, lives=n0)
        cl, fp, st = o["closing"], o["fights_per_min"], o["started"]
        o["headline"] = dict(press=None if None in (cl["ahead"], cl["weak"]) else cl["ahead"] - cl["weak"],
                             fights_ahead_per_weak=None if None in (fp["ahead"], fp["weak"]) or not fp["weak"] else round(fp["ahead"] / fp["weak"], 2),
                             started_ahead_less_weak=None if None in (st["ahead"], st["weak"]) else round(st["ahead"] - st["weak"], 2),
                             big_item_share_ahead=o["big_item_share"]["ahead"], next_top1=t1)
        out[who] = o
    return out


def show(name, s):
    print(name)
    for who in ("he", "opponent"):
        o = s[who]
        print("  {:9s}            {:>8s} {:>8s} {:>8s}".format(who, *BANDS))
        for k, lab in (("time_share", "share of the time"), ("in_view", "enemy in view"), ("closing", "speed toward him (u/s)"), ("fights_per_min", "fights a minute"),
                       ("started", "fights he started"), ("won", "... the enemy died"), ("lost", "... he died"), ("dealt_per_taken", "damage dealt / taken"),
                       ("big_item_share", "mega + red: his share"), ("late_s", "... seconds late"), ("enemy_at_pickup", "enemy at his pickups (u)")):
            print("    {:22s} {:>8} {:>8} {:>8}".format(lab, *["-" if o[k][b_] is None else o[k][b_] for b_ in BANDS]))
        v, h = o["variety"], o["headline"]
        print("    variety: next pickup top-1 {} ({} bits, {} pickups); opening by spawn top-1 {} ({} bits, {} lives)".format(
            v["next_top1"], v["next_bits"], v["pickups"], v["opening_top1"], v["opening_bits"], v["lives"]))
        print("    headline: press {} u/s | fights ahead / weak {} | started ahead - weak {} | mega + red when ahead {}".format(
            h["press"], h["fights_ahead_per_weak"], h["started_ahead_less_weak"], h["big_item_share_ahead"]))


def play(job):
    (envmod, envvars, mp, games, minutes, seed, pol, idx, opp_pol, opp_idx, round_secs, swap, delays) = job
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    import test_suite as T_
    sw_ = int(bool(swap))
    T_.set_delays(E, env, [(np.arange(sw_, env.n, 2), delays[0], delays[1]), (np.arange(1 - sw_, env.n, 2), delays[2], delays[3])])
    env.arena_stack = False                                  # (the game as tools/duel_eval.py sets it up)
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.runner_p = 0.0
    env.round_t[:] = 1e9
    n = env.n
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    ev, od = np.arange(0, n, 2), np.arange(1, n, 2)
    if swap:
        ev, od = od, ev
    env.script[:] = 0
    pol.rng = np.random.default_rng(seed)
    opp_pol.rng = np.random.default_rng(seed + 1)
    h, h2 = pol.zeros(len(ev)), opp_pol.zeros(len(od))
    big = [E.RL, E.RG, E.LG]
    frames = int(minutes * 60 / E.DT)
    import duel_eval as D_
    sc_ = D_.SeatClock(E, env, ev, od, round_secs[:2], left_full=round_secs[2])           # each seat on the clock, score and memory of its own training (he first)
    rec = {k: [] for k in ("pos", "hp", "armor", "has", "alive", "died", "vis")}
    died = np.zeros(n, bool)
    for t in range(frames):
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        al, h = pol.act(obs[ev][:, idx], h)
        a[ev, :al.shape[1]] = al
        ao, h2 = opp_pol.act(obs[od][:, opp_idx], h2)
        a[od, :ao.shape[1]] = ao
        sc_.before()
        obs, r, done, info = env.step(a)
        for e in info["events"]:
            died[int(e["victim"])] = True
        if (t + 1) % EVERY == 0:
            for k, v in (("pos", env.state[:, :3]), ("hp", env.hp), ("armor", env.armor), ("has", env.has[:, big]), ("alive", env.hp > 0), ("died", died),
                         ("vis", env.visible)):
                rec[k].append(np.array(v, copy=True))
            died = np.zeros(n, bool)
        sc_.after(t, info["events"], (h, h2))
    rec = {k: np.array(v) for k, v in rec.items()}
    out = None
    for m in range(games):
        seats = [2 * m + sw_, 2 * m + 1 - sw_]               # he first
        out = add(out, measure(dict(dt=E.DT * EVERY, **{k: v[:, seats] for k, v in rec.items()})))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--opp", required=True, help="policy:<file>")
    ap.add_argument("--opp-inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld,sinister")
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--round", type=float, default=0.0, help="his clock, score and memory start over every this many seconds; 600 or more: never "
                    "(default: his checkpoint's round_secs, as tools/duel_eval.py)")
    ap.add_argument("--opp-round", type=float, default=0.0, help="... of the opponent network (default: its checkpoint's)")
    ap.add_argument("--left-full", action="store_true", help="a round seat's 'time left in the round' input stays at 1.0, as the checks fed it until 2026-10-13 "
                    "(default: 1 - t / round_secs, as on the server); to reproduce older numbers")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--swap", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    import duel_eval as D_
    import test_suite as T
    assert a.opp.startswith("policy:")
    pol, opp_pol = T.Policy(a.policy, seed=1), T.Policy(a.opp[7:], seed=2)
    now = D_.names(os.path.join(ROOT, "docs", "INPUTS.csv"))
    idx = np.array([now.index(x) for x in D_.names(a.inputs)])
    opp_idx = np.array([now.index(x) for x in D_.names(a.opp_inputs)])
    assert len(idx) == len(pol.mean) and len(opp_idx) == len(opp_pol.mean), "the lists of inputs do not fit the networks"
    envvars = dict(x.split("=", 1) for x in a.set)
    delays = (pol.react_ms, pol.acquire_ms, opp_pol.react_ms, opp_pol.acquire_ms)
    res, total = {}, None
    for mp in a.map.split(","):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        jobs = [(a.env, envvars, mp, g, a.minutes, a.seed + 17 * k, pol, idx, opp_pol, opp_idx, (D_.round_of(a.round, pol, mp), D_.round_of(a.opp_round, opp_pol, mp), a.left_full), a.swap and k % 2 == 1, delays) for k, g in enumerate(per) if g > 0]
        with mp_.Pool(len(jobs)) as pool:
            c = None
            for r in pool.map(play, jobs):
                c = add(c, r)
        res[mp] = dict(counters=c, summary=summary(c))
        total = add(total, c)
        show(mp, res[mp]["summary"])
        sys.stdout.flush()
    res["all"] = dict(counters=total, summary=summary(total))
    show("all maps", res["all"]["summary"])
    if a.json:
        json.dump(dict(policy=os.path.basename(a.policy), opp=os.path.basename(a.opp[7:]), games=a.games, minutes=a.minutes, round=[D_.round_of(a.round, pol), D_.round_of(a.opp_round, opp_pol)], left_full=bool(a.left_full), set=envvars,
                       gap=GAP, maps=res), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    main()

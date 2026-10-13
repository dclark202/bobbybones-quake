"""His openings beside the pros' (owner, 2026-10-13: openings from each spawn "like chess openings"): what does a
network do in the first seconds after each spawn, set beside what the pros do from the same spawn point
(sim/pro_spawn_openings/<map>.json, tools/pro_openings.py)? A measurement: nothing is trained, nothing is changed.

    python tools/opening_check.py play --policy <file.pt> --map bloodrun,aerowalk --games 16 --procs 4 --out <dir> --set NAME=VALUE ...
        the network against itself in ten-minute games (the set-up of tools/duel_eval.py: the game's spawn, spawn points
        away from the enemy, one game without restarts, his clock and memory over every --round seconds); every life of
        either seat is a row of <dir>/lives_<map>.json
    python tools/opening_check.py pros --map bloodrun,... --out <dir>
        the pros' lives of the light demo sets read once more (tools/pro_openings.read_lives: the same spawn lives and
        pickups as the json) and kept small in <dir>/pros_<map>.json: what the json does not hold (no pickup within TEN
        seconds, the median to the first pickup of all lives, second pickups beside the enemy) is counted from them
    python tools/opening_check.py report --map ... --out <dir> --md docs/design/openings/BOBBY_<name>.md [--name v0.2]

The definitions are tools/pro_openings.py's, applied to the simulator's own state frame by frame (25 ms, as the sets):
  a spawn life   from a respawn (in these games a death and the respawn fall in one step) or the game's start to the
                 death; the spawn point is the pros' spawn point of the json nearest to where he stands on that frame,
                 within SNAP units (a spawn entity the pros' sets do not show: "other")
  a big pickup   a weapon newly owned, health up by 60 or more, armor up by 20 or more (75 red, 40 yellow, 20 green),
                 given to the nearest item of that kind in plugins/duel_items.json within NEAR units; a weapon gained
                 far from every item of its kind is a dropped one (counted, no opening)
  an opening     his first big pickups within WINDOW seconds, each item once
  the enemy      where the enemy truly stood on the frame of the spawn (the pros': as the server last sent him in the
                 last second before the death), straight lines; and what he knew: the simulator's `seen_t` (zero on a
                 frame he has noticed the enemy in view or hears him), `acquired`, `known` (the believed place)
Beside it per life: his intention (env.intent) over the first ten seconds, the share of frames the movement network
carried him (env.legs_on), his style this life, his way at 0.25 s steps.
No torch in the workers (the network is plain numpy: test_suite.Policy), one World a process.
"""
import argparse
import collections
import csv
import importlib
import json
import multiprocessing as mp_
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pin  # noqa: E402
import pro_openings as P  # noqa: E402  (the pros' definitions: WINDOW, NEAR, ENEMY_NEAR, the items' labels)

SNAP = 100.0             # his spawn belongs to the pros' spawn point this near
TEN = 10.0               # "no big pickup in ten seconds"
STACK = ("MH", "RA", "YA", "GA")
MIN_SPAWN = 8            # his lives at a spawn below which the notes say nothing of it


def names(path):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(path, encoding="utf-8"))]


def is_stack(label):
    return label[:2] in STACK


# ---------------------------------------------------------------------------------------------------------- playing
def play(job):
    (envmod, envvars, mp, games, minutes, seed, pol, idx, round_secs, delays, jobk) = job
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    import test_suite as T_
    n = env.n
    T_.set_delays(E, env, [(np.arange(0, n, 2), delays[0], delays[1]), (np.arange(1, n, 2), delays[0], delays[1])])
    env.arena_stack = False                                   # (the set-up of tools/duel_eval.py, two networks)
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.runner_p = 0.0
    if getattr(env, "lab", None) is not None:
        env.lab_force = dict(kind=E.NORMAL, arena=3)
        env.arena_len = 1e9
    env.round_t[:] = 1e9
    obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    env.script[:] = 0
    pol.rng = np.random.default_rng(seed)
    h = pol.zeros(n)

    big, _small = P.map_items(mp)
    by_cls = {}
    for i, it in enumerate(big):
        by_cls.setdefault(it["cls"], []).append(i)
    ipos = np.array([it["pos"] for it in big], np.float64).reshape(-1, 3)
    wk = sorted(P.WCLASS.items(), key=lambda kv: kv[1])       # (class, the weapon's number: the sets' order is duel_env.WEAPONS)
    widx = [k for _, k in wk]
    wcls = [c for c, _ in wk]
    DT = E.DT
    win_f, ten_f, step_f = int(P.WINDOW / DT), int(TEN / DT), int(0.25 / DT)
    frames = int(minutes * 60 / DT)
    wrap = max(1, int(round_secs / DT))
    other = np.arange(n) ^ 1
    ar = np.arange(n)
    has_style = hasattr(env, "style")

    f = np.zeros(n, np.int64)                                 # frames since his spawn
    cur = [None] * n
    out = []
    hist = np.zeros((n, len(E.INTENTS)), np.int64)            # frames of his first ten seconds by intention
    legs10, vis10, heard10, n10 = (np.zeros(n, np.int64) for _ in range(4))
    spd10 = np.zeros(n)
    t_seen, t_known = np.full(n, -1.0), np.full(n, -1.0)
    track = np.zeros((n, ten_f // step_f + 1, 3), np.float32)
    etrack = np.zeros((n, ten_f // step_f + 1, 3), np.float32)
    tr_n = np.zeros(n, np.int64)
    prev_int = np.full(n, -1, np.int64)

    def pos():
        return np.asarray(env.state[:, :3], np.float64)

    def open_(i, t, start):
        p = pos()
        cur[i] = dict(map=mp, game="{}.{}".format(jobk, i // 2), seat=int(i % 2), t0=round(t * DT, 2), start=bool(start),
                      pos0=[round(float(x), 1) for x in p[i]], style=E.STYLES[int(env.style[i])] if has_style else "general",
                      enemy=None if start else [round(float(x)) for x in p[other[i]]],
                      enemy_d0=round(float(np.linalg.norm(p[i] - p[other[i]]))),
                      labels=[], times=[], picks=[], drops=0, intents=[])
        f[i] = 0
        hist[i] = 0
        legs10[i] = vis10[i] = heard10[i] = n10[i] = tr_n[i] = 0
        spd10[i] = 0.0
        t_seen[i] = t_known[i] = -1.0
        prev_int[i] = -1
        track[i, 0], etrack[i, 0] = p[i], p[other[i]]
        tr_n[i] = 1

    def close_(i, t, cut):
        c = cur[i]
        if c is None:
            return
        m = max(1, int(n10[i]))
        c.update(secs=round(float(f[i] + 1) * DT, 2), cut=bool(cut),
                 intent_share={E.INTENTS[k]: round(float(hist[i, k]) / m, 3) for k in np.nonzero(hist[i])[0]},
                 legs=round(float(legs10[i]) / m, 3), in_view=round(float(vis10[i]) / m, 3), heard=round(float(heard10[i]) / m, 3),
                 speed=round(float(spd10[i]) / m), t_seen=None if t_seen[i] < 0 else round(float(t_seen[i]), 2),
                 t_known=None if t_known[i] < 0 else round(float(t_known[i]), 2),
                 track=np.round(track[i, :tr_n[i]]).astype(int).tolist(), enemy_track=np.round(etrack[i, :tr_n[i]]).astype(int).tolist())
        out.append(c)
        cur[i] = None

    def take(i, cls, p, kn):
        idx_ = by_cls.get(cls, [])
        c = cur[i]
        if not idx_:
            c["drops"] += 1
            return
        d = np.linalg.norm(ipos[idx_] - p[i], axis=1)
        j = idx_[int(d.argmin())]
        if d.min() > P.NEAR:
            c["drops"] += 1                                   # a dropped weapon: no opening
            return
        lab = big[j]["label"]
        if lab in c["labels"]:
            return
        c["labels"].append(lab)
        c["times"].append(round(float(f[i]) * DT, 3))
        c["picks"].append(dict(item=lab, t=round(float(f[i]) * DT, 3),
                               enemy_to_item=round(float(np.linalg.norm(p[other[i]] - ipos[j]))),
                               enemy_to_him=round(float(np.linalg.norm(p[other[i]] - p[i]))),
                               seen_t=round(float(env.seen_t[i]), 2), in_view=bool(env.visible[i]),
                               believed_to_item=round(float(np.linalg.norm(kn[i] - ipos[j]))),
                               intent=E.INTENTS[int(env.intent[i])], legs=bool(env.legs_on[i]) if hasattr(env, "legs_on") else False))

    for i in range(n):
        open_(i, 0, True)
    hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), np.asarray(env.has)[:, widx].copy()
    for t in range(frames):
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        al, h = pol.act(obs[:, idx], h)
        a[:, :al.shape[1]] = al
        obs, _r, _done, info = env.step(a)
        died = np.zeros(n, bool)
        for e in info["events"]:
            died[int(e["victim"])] = True
        f += 1
        for i in np.nonzero(died)[0]:
            f[i] -= 1
            close_(i, t, False)
            open_(int(i), t + 1, False)
        p = pos()
        kn = np.asarray(env.known, np.float64)
        alive = env.hp > 0
        same = alive & ~died
        w = same & (f <= win_f)
        has1 = np.asarray(env.has)[:, widx]
        gain = has1 & ~has0 & w[:, None]
        for i, k in zip(*np.nonzero(gain)):
            take(int(i), wcls[k], p, kn)
        dh, da = (env.hp - hp0), (env.armor - ar0)
        for i in np.nonzero(w & (dh >= 60))[0]:
            take(int(i), "item_health_mega", p, kn)
        for i in np.nonzero(w & (da >= 20))[0]:
            take(int(i), "item_armor_body" if da[i] >= 75 else ("item_armor_combat" if da[i] >= 40 else "item_armor_jacket"), p, kn)
        hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), has1.copy()
        # his first ten seconds: the intention, his legs, what he sees and hears, his way
        it = np.asarray(env.intent, np.int64)
        ch = (it != prev_int) & (f <= win_f) & alive
        for i in np.nonzero(ch)[0]:
            cur[i]["intents"].append([round(float(f[i]) * DT, 2), E.INTENTS[int(it[i])]])
        prev_int = np.where(f <= win_f, it, prev_int)
        m10 = alive & (f < ten_f)
        hist[ar[m10], it[m10]] += 1
        n10 += m10
        lg = np.asarray(getattr(env, "legs_on", np.zeros(n, bool)), bool)
        vis = np.asarray(env.visible, bool)
        acq = np.asarray(env.acquired, bool)
        knows = np.asarray(env.seen_t) <= 0.0
        legs10 += m10 & lg
        vis10 += m10 & vis
        heard10 += m10 & knows & ~acq
        spd10 += np.where(m10, np.hypot(env.state[:, 3], env.state[:, 4]), 0.0)
        first = alive & (f <= win_f) & acq & (t_seen < 0)
        t_seen[first] = f[first] * DT
        first = alive & (f <= win_f) & knows & (t_known < 0)
        t_known[first] = f[first] * DT
        smp = alive & (f <= ten_f) & (f % step_f == 0)
        for i in np.nonzero(smp)[0]:
            k = int(f[i] // step_f)
            track[i, k], etrack[i, k] = p[i], p[other[i]]
            tr_n[i] = k + 1
        if (t + 1) % wrap == 0:                               # his clock, score and memory start over, as on the server
            env.round_t[:] = 0.0
            env.frags_r[:] = 0
            h[:] = 0.0
    for i in range(n):
        close_(i, frames, True)
    return out


def cmd_play(a):
    import test_suite as T
    pol = T.Policy(a.policy, seed=1)
    now = names(os.path.join(ROOT, "docs", "INPUTS.csv"))
    old = names(a.inputs)
    assert len(old) == len(pol.mean), "the network has {} inputs, {} lists {}".format(len(pol.mean), a.inputs, len(old))
    idx = np.array([now.index(x) for x in old])
    envvars = dict(x.split("=", 1) for x in a.set)
    delays = (pol.react_ms if a.react_ms is None else a.react_ms, pol.acquire_ms if a.acquire_ms is None else a.acquire_ms)
    os.makedirs(a.out, exist_ok=True)
    for mp in a.map.split(","):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        jobs = [(a.env, envvars, mp, g, a.minutes, a.seed + 17 * k, pol, idx, a.round or 120.0, delays, "{}_{}".format(a.seed, k))
                for k, g in enumerate(per) if g > 0]
        with mp_.Pool(len(jobs), initializer=pin.pin_pool_worker) as pool:
            res = pool.map(play, jobs)
        lives = [l for r in res for l in r]
        fn = os.path.join(a.out, "lives_{}.json".format(mp))
        if a.add and os.path.exists(fn):
            lives = json.load(open(fn))["lives"] + lives
        with open(fn, "w", encoding="utf-8") as fh:
            json.dump(dict(map=mp, policy=os.path.basename(a.policy), env=a.env, minutes=a.minutes, round=a.round or 120.0,
                           set={k: (os.path.basename(v) if os.sep in v or "/" in v else v) for k, v in envvars.items()},
                           delays_ms=list(delays), games=len({l["game"] for l in lives}), lives=lives), fh, separators=(",", ":"))
        print("{}: {} games, {} lives ({} a player a game)".format(mp, len({l["game"] for l in lives}), len(lives),
                                                                  round(len(lives) / max(1, 2 * len({l["game"] for l in lives})), 1)), flush=True)


# ---------------------------------------------------------------------------------------------------------- the pros
def cmd_pros(a):
    os.makedirs(a.out, exist_ok=True)
    for mp in a.map.split(","):
        _big, lives, facts = P.read_lives(mp, a.limit)
        rows = [dict(pos0=[round(float(x), 1) for x in l["pos0"]], labels=l["labels"], times=[round(float(x), 3) for x in l["times"]],
                     secs=round(float(l["secs"]), 2), enemy=l["enemy"], start=bool(l["start"])) for l in lives]
        with open(os.path.join(a.out, "pros_{}.json".format(mp)), "w", encoding="utf-8") as fh:
            json.dump(dict(map=mp, demos=facts["demos"], lives=rows), fh, separators=(",", ":"))
        print("{}: {} demos, {} lives".format(mp, facts["demos"], len(rows)), flush=True)


# ---------------------------------------------------------------------------------------------------------- the report
def snap(lives, spawns):
    """each life's spawn point: the nearest of the pros' within SNAP, else None"""
    S = np.array([s["pos"] for s in spawns], np.float64).reshape(-1, 3)
    for l in lives:
        d = np.linalg.norm(S - np.array(l["pos0"]), axis=1) if len(S) else np.array([1e9])
        l["sp"] = spawns[int(d.argmin())]["name"] if d.min() <= SNAP else None
    return lives


def facts(g):
    """a spawn's lives -> the table's numbers"""
    n = len(g)
    if not n:
        return None
    c1 = collections.Counter(l["labels"][0] for l in g if l["labels"])
    c2 = collections.Counter(" > ".join(l["labels"][:2]) for l in g if len(l["labels"]) >= 2)
    t1 = [l["times"][0] for l in g if l["labels"]]
    by = {}
    for l in g:
        if l["labels"]:
            by.setdefault(l["labels"][0], []).append(l["times"][0])
    return dict(n=n, first=c1.most_common(4), two=c2.most_common(3), t_first=float(np.median(t1)) if t1 else None,
                none10=sum(1 for l in g if not l["labels"] or l["times"][0] > TEN) / n,
                none15=sum(1 for l in g if not l["labels"]) / n,
                t_by={k: float(np.median(v)) for k, v in by.items()}, n_by={k: len(v) for k, v in by.items()})


def enemy_near(groups, cand, items, depth):
    """With the enemy within ENEMY_NEAR of a stack item that is one of the spawn's usual pickups at this depth (0: the
    first, 1: the second), how often is it the pickup at that depth; and at the rate of the same spawn's lives without
    him there. groups: {spawn: lives}, cand: {spawn: [labels]} -> (lives with him at it, taken, taken at the other rate)"""
    n_at = took = exp = 0.0
    for sp, g in groups.items():
        rows = [l for l in g if l.get("enemy") is not None]
        for x in cand.get(sp, []):
            if not is_stack(x) or x not in items:
                continue
            d = np.array([np.linalg.norm(np.array(l["enemy"], np.float64) - np.array(items[x])) for l in rows])
            tk = np.array([len(l["labels"]) > depth and l["labels"][depth] == x for l in rows], bool)
            at = d < P.ENEMY_NEAR
            if not at.sum() or not (~at).sum():
                continue
            n_at += at.sum()
            took += tk[at].sum()
            exp += tk[~at].mean() * at.sum()
    return int(n_at), (took / n_at if n_at else None), (exp / n_at if n_at else None)


def pct(x):
    return "-" if x is None else "{:.0%}".format(x)


def sec(x):
    return "-" if x is None else "{:.1f}".format(x)


def report_map(mp, out, name):
    """-> (lines of the map's section, the map's headline numbers)"""
    pj = json.load(open(os.path.join(ROOT, "sim", "pro_spawn_openings", mp + ".json")))
    d = json.load(open(os.path.join(out, "lives_{}.json".format(mp))))
    his = snap(d["lives"], pj["spawns"])
    pf = os.path.join(out, "pros_{}.json".format(mp))
    pros = snap(json.load(open(pf))["lives"], pj["spawns"]) if os.path.exists(pf) else None
    items = pj["items"]
    names_ = [s["name"] for s in pj["spawns"]]
    hg = {s: [l for l in his if l["sp"] == s] for s in names_}
    pg = {s: [l for l in pros if l["sp"] == s] for s in names_} if pros is not None else None
    L = ["### {}".format(mp), ""]
    oth = [l for l in his if l["sp"] is None]
    L += ["{} games of {:g} minutes, {} lives of his ({:.1f} a player a game; {} of them a game's start){}. The pros: {} lives in {} demos.".format(
        d["games"], d["minutes"], len(his), len(his) / max(1, 2 * d["games"]), sum(1 for l in his if l["start"]),
        "; {} at a spawn entity the pros' sets do not show (left out)".format(len(oth)) if oth else "", pj["lives"], pj["demos"]), "",
        "| spawn | his lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | to the pros' item, taken first: he | pros | none in 10 s: he | pros | his first intention | on his legs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    head = dict(lives=0, follow=0, anyof=0, gen=0, gen_follow=0, none10=0.0, none10_p=0.0, t_his=[], t_pro=[], ways=[], rows=[])
    for sp in pj["spawns"]:
        s = sp["name"]
        hf = facts(hg[s])
        pfx = facts(pg[s]) if pg is not None else None
        if pfx is not None and pfx["first"]:
            p_item, p_share, p_t, p_none, p_ti = pfx["first"][0][0], pfx["first"][0][1] / pfx["n"], pfx["t_first"], pfx["none10"], pfx["t_by"][pfx["first"][0][0]]
        elif sp["openings"]:
            o = sp["openings"][0]                             # (without the pros' lives: the json; its "none" is of 15 s)
            p_item, p_share, p_t, p_none, p_ti = o["items"][0], o["share"], None, sp["no_big_pickup"], o["seconds"][0]
        else:
            p_item, p_share, p_t, p_none, p_ti = None, None, None, sp["no_big_pickup"], None
        lead = "{} ({}, {}, {}; by {})".format(s, *sp["pos"], sp["nearest_item"])
        if hf is None:
            L.append("| {} | 0 | (he never spawned here) | {} {} | | | | | {} | | {} | | {} | | |".format(
                lead, p_item or "-", pct(p_share), sec(p_t), sec(p_ti), pct(p_none)))
            continue
        g = hg[s]
        h_item, h_cnt = hf["first"][0] if hf["first"] else (None, 0)
        follow = hf["n_by"].get(p_item, 0) if p_item else 0
        kept = [o["items"][0] for o in sp["openings"]]
        anyof = sum(hf["n_by"].get(k, 0) for k in set(kept + ([p_item] if p_item else [])))
        gen = [l for l in g if l["style"] == "general"]
        ints = collections.Counter(next((nm for _t, nm in l["intents"] if nm != "none"), "none") for l in g)
        i_top = ints.most_common(1)[0]
        legs = float(np.mean([l["legs"] for l in g]))
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            lead, hf["n"], "{} {}".format(h_item, pct(h_cnt / hf["n"])) if h_item else "nothing",
            "{} {}".format(p_item, pct(p_share)) if p_item else "-", pct(follow / hf["n"]) if p_item else "-", pct(anyof / hf["n"]) if kept else "-",
            "{} {}".format(hf["two"][0][0], pct(hf["two"][0][1] / hf["n"])) if hf["two"] else "-",
            sec(hf["t_first"]), sec(p_t), sec(hf["t_by"].get(p_item)) if p_item else "-", sec(p_ti),
            pct(hf["none10"]), pct(p_none), "{} {}".format(i_top[0], pct(i_top[1] / hf["n"])), pct(legs)))
        head["lives"] += hf["n"]
        head["follow"] += follow
        head["anyof"] += anyof
        head["gen"] += len(gen)
        head["gen_follow"] += sum(1 for l in gen if l["labels"] and l["labels"][0] == p_item)
        head["none10"] += hf["none10"] * hf["n"]
        head["none10_p"] += (p_none or 0.0) * hf["n"]
        if hf["t_first"] is not None and p_t is not None:
            head["t_his"].append((hf["t_first"], hf["n"]))
            head["t_pro"].append((p_t, hf["n"]))
        if hf["n"] >= MIN_SPAWN and p_item:
            row = dict(s=s, near=sp["nearest_item"], anyof=anyof / hf["n"], two=hf["two"][:2], first=hf["first"], intent=ints.most_common(3), legs=legs,
                       n=hf["n"], h=h_item, hs=h_cnt / hf["n"], p=p_item, ps=p_share, follow=follow / hf["n"], none=hf["none10"], pnone=p_none,
                       t=hf["t_by"].get(p_item), nt=hf["n_by"].get(p_item, 0), pt=p_ti, tf=hf["t_first"], ptf=p_t)
            head["rows"].append(row)
    L.append("")
    # his general lives alone: in a styled life (STYLE_P of his lives) the style's weapon is his first target whatever the spawn
    if any(l["style"] != "general" for l in his):
        L += ["His general lives alone (in the others his style this life, rockets, rail or lightning, names his weapon):", "",
              "| spawn | his general lives | his commonest first pickup | the pros' commonest | he takes the pros' first | one of the pros' openings | his first two | s to first pickup: he | pros | none in 10 s: he | pros |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for sp in pj["spawns"]:
            g = [l for l in hg[sp["name"]] if l["style"] == "general"]
            hf = facts(g)
            if hf is None:
                continue
            pfx = facts(pg[sp["name"]]) if pg is not None else None
            if pfx is not None and pfx["first"]:
                p_item, p_share, p_t, p_none = pfx["first"][0][0], pfx["first"][0][1] / pfx["n"], pfx["t_first"], pfx["none10"]
            elif sp["openings"]:
                p_item, p_share, p_t, p_none = sp["openings"][0]["items"][0], sp["openings"][0]["share"], None, sp["no_big_pickup"]
            else:
                p_item, p_share, p_t, p_none = None, None, None, sp["no_big_pickup"]
            kept = set([o["items"][0] for o in sp["openings"]] + ([p_item] if p_item else []))
            L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                sp["name"], hf["n"], "{} {}".format(hf["first"][0][0], pct(hf["first"][0][1] / hf["n"])) if hf["first"] else "nothing",
                "{} {}".format(p_item, pct(p_share)) if p_item else "-", pct(hf["n_by"].get(p_item, 0) / hf["n"]) if p_item else "-",
                pct(sum(hf["n_by"].get(k, 0) for k in kept) / hf["n"]) if kept else "-",
                "{} {}".format(hf["two"][0][0], pct(hf["two"][0][1] / hf["n"])) if hf["two"] else "-",
                sec(hf["t_first"]), sec(p_t), pct(hf["none10"]), pct(p_none)))
        L.append("")
    # his ways: the time to a first pickup, like for like (the same spawn, the same item taken first)
    if pg is not None:
        L += ["His ways beside theirs: the median seconds from a spawn to a first pickup, where he took it first in {} lives or more and "
              "the pros in 5 or more.".format(MIN_SPAWN), "",
              "| spawn | first pickup | his lives | his seconds | the pros' lives | the pros' seconds | he is slower by |", "|---|---|---|---|---|---|---|"]
        for sp in pj["spawns"]:
            hf, pfx = facts(hg[sp["name"]]), facts(pg[sp["name"]])
            if hf is None or pfx is None:
                continue
            for k, nk in sorted(hf["n_by"].items(), key=lambda kv: -kv[1]):
                if nk >= MIN_SPAWN and pfx["n_by"].get(k, 0) >= 5:
                    L.append("| {} | {} | {} | {:.1f} | {} | {:.1f} | {:+.1f} |".format(sp["name"], k, nk, hf["t_by"][k], pfx["n_by"][k], pfx["t_by"][k],
                                                                                 hf["t_by"][k] - pfx["t_by"][k]))
                    head["ways"].append(dict(s=sp["name"], item=k, n=nk, t=hf["t_by"][k], pn=pfx["n_by"][k], pt=pfx["t_by"][k]))
                elif nk >= MIN_SPAWN:
                    L.append("| {} | {} | {} | {:.1f} | {} | - | (the pros do not open so) |".format(sp["name"], k, nk, hf["t_by"][k], pfx["n_by"].get(k, 0)))
                    head["ways"].append(dict(s=sp["name"], item=k, n=nk, t=hf["t_by"][k], pn=pfx["n_by"].get(k, 0), pt=None))
        L.append("")
    # the enemy and the stack items
    cand1 = {sp["name"]: [o["items"][0] for o in sp["openings"]] for sp in pj["spawns"]}
    cand2 = {}
    src = pg if pg is not None else hg
    for s, g in src.items():
        c = collections.Counter(l["labels"][1] for l in g if len(l["labels"]) >= 2)
        cand2[s] = [k for k, v in c.items() if v >= 5 and v >= 0.05 * len(g)]
    en = {}
    for key, cand, depth in (("first", cand1, 0), ("second", cand2, 1)):
        en[key] = dict(he=enemy_near(hg, cand, items, depth), pros=enemy_near(pg, cand, items, depth) if pg is not None else None)
        h_, p_ = en[key]["he"], en[key]["pros"]
        L.append("The enemy within {:.0f} units of an armor or the mega that is one of the spawn's usual {} pickups: he takes it as his {} pickup "
                 "{} of the time ({} lives; {} at the rate of his lives without the enemy there){}.".format(
                     P.ENEMY_NEAR, key, key, pct(h_[1]), h_[0], pct(h_[2]),
                     "; the pros {} ({} lives; {} without him there)".format(pct(p_[1]), p_[0], pct(p_[2])) if p_ else ""))
    # his second pickup, an armor or the mega, with the enemy truly near it at the moment he takes it
    sec2 = [l["picks"][1] for l in his if l["sp"] and len(l["picks"]) >= 2 and is_stack(l["picks"][1]["item"])]
    if sec2:
        near = [q for q in sec2 if q["enemy_to_item"] < P.ENEMY_NEAR]
        knew = [q for q in near if q["seen_t"] <= 3.0]
        L.append("His second pickup is an armor or the mega in {} lives; in {} of them the enemy stood within {:.0f} units of it at the moment he "
                 "took it, and in {} of those he had seen or heard him in the three seconds before.".format(
                     len(sec2), pct(len(near) / len(sec2)), P.ENEMY_NEAR, pct(len(knew) / len(near)) if near else "-"))
    # by the kind of life
    st = collections.Counter(l["style"] for l in his if l["sp"])
    if len(st) > 1:
        parts = []
        for nm, k in st.most_common():
            g = [l for l in his if l["sp"] and l["style"] == nm]
            f1 = collections.Counter(l["labels"][0][:2] for l in g if l["labels"])
            parts.append("{} ({} lives): none in 10 s {}, first pickup {}".format(
                nm, k, pct(sum(1 for l in g if not l["labels"] or l["times"][0] > TEN) / k),
                ", ".join("{} {}".format(a_, pct(b_ / k)) for a_, b_ in f1.most_common(3))))
        L.append("By the kind of life: " + "; ".join(parts) + ".")
    L.append("")
    w = lambda rows: (sum(a_ * b_ for a_, b_ in rows) / max(1, sum(b_ for _a, b_ in rows))) if rows else None   # noqa: E731
    hd = dict(map=mp, games=d["games"], lives=len(his), at_spawns=head["lives"], follow=head["follow"] / max(1, head["lives"]),
              anyof=head["anyof"] / max(1, head["lives"]), follow_general=head["gen_follow"] / max(1, head["gen"]), general_lives=head["gen"],
              none10=head["none10"] / max(1, head["lives"]), none10_pros=head["none10_p"] / max(1, head["lives"]),
              t_first=w(head["t_his"]), t_first_pros=w(head["t_pro"]), enemy=en, rows=head["rows"], ways=head["ways"], other=len(oth),
              pros_lives=pg is not None)
    return L, hd


def cmd_report(a):
    secs, heads = [], []
    for mp in a.map.split(","):
        if not os.path.exists(os.path.join(a.out, "lives_{}.json".format(mp))):
            continue
        L, hd = report_map(mp, a.out, a.name)
        secs += L
        heads.append(hd)
    H = ["# His openings beside the pros': {}".format(a.name), "",
         "Written by `tools/opening_check.py report` from games the network played against itself in the simulator "
         "(`play`: the set-up of `tools/duel_eval.py`, ten-minute games, both seats the same network, every life of either "
         "seat counted) and the pros' lives of the demo sets (`pros`; the openings themselves: [README.md](README.md), "
         "`sim/pro_spawn_openings/<map>.json`). The definitions are the pros' (`tools/pro_openings.py`): a spawn life, a big "
         "pickup (mega MH, red RA, yellow YA, green GA, the weapons; a dropped weapon is none), the first pickups within "
         "{:.0f} s. A spawn is the pros' spawn point nearest to his start (within {:.0f} units). Shares are of the spawn's "
         "lives; times are medians in seconds from the spawn. \"He takes the pros' first\": the share of his lives whose first "
         "big pickup is the pros' commonest first pickup at that spawn; "
         "\"one of the pros' openings\": ... is the first pickup of any opening the pros' file keeps for the spawn (5 lives and 10% of "
         "the spawn's lives). \"To the pros' item, taken first\": the median time to "
         "that item in the lives that took it first, his and theirs (like for like: a route's speed). \"His first intention\": "
         "the first target his intention output names in the life. \"On his legs\": the share of the first ten seconds' frames "
         "the movement network moved him.".format(P.WINDOW, SNAP), "",
         "<!-- notes -->"]
    notes = ""
    if a.notes and os.path.exists(a.notes):
        notes = open(a.notes, encoding="utf-8").read()
    elif os.path.exists(a.md):
        old = open(a.md, encoding="utf-8").read()
        if "<!-- notes -->" in old and "<!-- tables -->" in old:
            notes = old.split("<!-- notes -->")[1].split("<!-- tables -->")[0]
    H += notes.strip().split("\n") + ["<!-- tables -->", "",
          "## The maps in one table", "",
          "| map | games | his lives at the pros' spawns | first pickup = the pros' commonest | ... in his general lives | ... = one of the pros' openings | s to first pickup: he | pros | none in 10 s: he | pros | armor or mega as FIRST pickup with the enemy at it: he (without him) | pros (without him) | ... as SECOND pickup: he (without him) | pros (without him) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for hd in heads:
        e = hd["enemy"]
        cell = lambda v: "-" if not v or v[1] is None else "{} ({}), {} lives".format(pct(v[1]), pct(v[2]), v[0])   # noqa: E731
        H.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            hd["map"], hd["games"], hd["at_spawns"], pct(hd["follow"]), pct(hd["follow_general"]), pct(hd["anyof"]), sec(hd["t_first"]), sec(hd["t_first_pros"]), pct(hd["none10"]),
            pct(hd["none10_pros"]), cell(e["first"]["he"]), cell(e["first"]["pros"]), cell(e["second"]["he"]), cell(e["second"]["pros"])))
    H += ["", "The seconds and the pros' \"none\" in this table are means over the spawns weighted by his lives there (so that the two "
          "columns are of the same mix of spawns).", ""]
    os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
    with open(a.md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(H + secs))
    with open(os.path.join(a.out, "headline.json"), "w", encoding="utf-8") as fh:
        json.dump(heads, fh, indent=1)
    for hd in heads:
        print("{}: {} games, {} lives at the pros' spawns ({} elsewhere) | first pickup = the pros' commonest {} (general lives {}, one of the pros' openings {}) | to first pickup {} s (pros {}) | "
              "none in 10 s {} (pros {})".format(hd["map"], hd["games"], hd["at_spawns"], hd["other"], pct(hd["follow"]), pct(hd["follow_general"]), pct(hd["anyof"]), sec(hd["t_first"]),
                                                 sec(hd["t_first_pros"]), pct(hd["none10"]), pct(hd["none10_pros"])), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("play", "pros", "report"))
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--out", required=True, help="the folder of the raw rows (lives_<map>.json, pros_<map>.json): not in the repo")
    ap.add_argument("--policy", default="")
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--round", type=float, default=0.0)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--add", action="store_true", help="play: add the lives to the map's file (give another --seed)")
    ap.add_argument("--react-ms", type=float, default=None)
    ap.add_argument("--acquire-ms", type=float, default=None)
    ap.add_argument("--limit", type=int, default=0, help="pros: this many demo sets a map (0: all)")
    ap.add_argument("--md", default=os.path.join(ROOT, "docs", "design", "openings", "BOBBY.md"))
    ap.add_argument("--name", default="the network")
    ap.add_argument("--notes", default="", help="report: a text file put above the tables (what stands out)")
    a = ap.parse_args()
    return dict(play=cmd_play, pros=cmd_pros, report=cmd_report)[a.what](a)


if __name__ == "__main__":
    sys.exit(main())

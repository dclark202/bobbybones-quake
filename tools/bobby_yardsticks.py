"""A network through the pros' yardsticks (tools/pro_yardsticks.py): he plays ten-minute duels in the simulator, every
game becomes the same frame-by-frame record a pro demo becomes, and the same functions measure it. One table a group
with the pros beside him.

    python tools/bobby_yardsticks.py --policy data/sim_runs/duel_gru_v15c/policy_end_v15c.pt --tag v15c
    python tools/bobby_yardsticks.py --policy data/sim_runs/duel_gru_v15f/policy.pt --tag v15f --set FIGHT_TARGET=1
    python tools/bobby_yardsticks.py --show docs/bobby_yardsticks_v15c.json
    (Anaconda Python; six maps, 12 games a map against himself and 8 against the stand-in, --procs 6 at low priority)

Two passes a map:
  self        both seats are the network; every seat is measured (the fair comparison: the pros play people)
  nightmare   the stand-in for the game's Nightmare bot in the other seat (as tools/duel_eval.py --opp nightmare); only
              the network's seat is measured
The games are set up as tools/duel_eval.py's: one ten-minute game, the game's spawn, no restarts, his clock, score and
memory starting over every 120 s as in training. A network with fewer inputs or outputs than the simulator gets the
first of the inputs and its actions go into the first columns.

What the simulator knows and a demo does not is left out of the record or made like a demo's:
  enemy in view     worked out by pro_yardsticks.see() from the positions and the map, as for the demos; the simulator's
                    own `visible` (which has his reaction time in it) is not used
  shots             a weapon's ammunition going down from one frame to the next, as in a demo
  pickups           health, armor or a weapon's ammunition rising at the item's spot, as in a demo
  hits              a frame on which the damage he has dealt rises, or he frags: a counter like the demo's
  death             the simulator puts a dead player on a spawn point within the same frame: that frame counts as his
                    one dead frame (a pro is dead for about two seconds), and the enemy is "not there" on it
  sounds            a jump, a shot or a pickup of the enemy's within 1200 units, from his own state frame by frame (a demo
                    has them as events of his entity while the server sends him)
Output: docs/bobby_yardsticks_<tag>.json: "self" and "nightmare", each with "all" and the maps, a map as in
docs/pro_yardsticks.json; `standing` (the weapons, height, distance and outcome with the enemy in view, tools/pro_places.py's
strength() on his rows), `cells` (his own cells with 30 sightings or more) and `routes` (his ways beside the pros' at the
same number of trips).
"""
import argparse
import glob
import importlib
import json
import multiprocessing as mp_
import os
import sys
import time

import numpy as np

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
sys.path.insert(0, SIM)
sys.path.insert(0, HERE)
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged"
SETS = ("AIM_LEVEL=3 ITEM_BELIEF=1 STYLE_P=0.75 INTENT_HOLD=8 KEY_RATE=8 AMMO_PACKS=0 GROUND_SENSE=1 DROPS=1 SHOT_MASK=1 LAVA=1 "
        "WALK_FIX=1 QL_MOVE=1 ITEM_DROP=1 SOLIDS=1 PRO_WAYS=1 NEAREST=1 PROJ_SEE=1 GL_QL=1 LEGS=1 LEGS_EVERY=4 AUTO_SWITCH=1 LEGS_OFF=2 "
        "LEGS_NET=" + os.path.join(ROOT, "data", "sim_runs", "move_v15n", "policy.npz").replace("\\", "/"))
WHO = (("pros", "the pros"), ("self", "he, against himself"), ("nightmare", "he, against the stand-in"))


def low_priority():
    """below normal, so that a training run on the same PC keeps its share"""
    try:
        import ctypes
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    except Exception:                                          # noqa: BLE001 (not Windows)
        try:
            os.nice(5)
        except Exception:                                      # noqa: BLE001
            pass


def play(job):
    """one map, one pass: `games` ten-minute games at once -> a tally and the rows of every measured player"""
    envmod, envvars, mp, games, minutes, seed, pol, opp, round_secs = job
    low_priority()
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    import pro_yardsticks as Y
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    # ---- the game, as tools/duel_eval.py sets it up
    env.react_frames = round(pol.react_ms / 25)
    # two delays the simulator reads from the run, not from the environment (the trainer's --react-ms and --acquire-ms):
    # here as settings of this tool (--set ACQUIRE_MS=225), for trials of his aim
    if envvars.get("REACT_MS"):
        env.react_frames = round(float(envvars["REACT_MS"]) / 25)
    if envvars.get("ACQUIRE_MS"):
        env.acquire_frames = round(float(envvars["ACQUIRE_MS"]) / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    scripted = opp == "nightmare"
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
    if scripted:
        env.script[od] = 3
        env.sc_persona[od] = E.NIGHTMARE
    else:
        env.script[od] = 0
    env.script[ev] = 0
    P = ev if scripted else np.arange(n)                         # the seats the network plays, and that are measured
    pol.rng = np.random.default_rng(seed)
    h = pol.zeros(len(P))
    ni = len(pol.mean)
    frames = int(minutes * 60 / E.DT)
    wrap = max(1, int(round_secs / E.DT))
    nw = len(E.WEAPONS)
    assert tuple(E.WEAPONS) == tuple(Y.WEAPONS), "the simulator's weapons are not in the yardsticks' order"
    B = dict(pos=np.zeros((frames, n, 3), np.float32), vel=np.zeros((frames, n, 3), np.float32), air=np.zeros((frames, n), bool),
             yaw=np.zeros((frames, n), np.float32), pitch=np.zeros((frames, n), np.float32), hp=np.zeros((frames, n), np.float32),
             ar=np.zeros((frames, n), np.float32), w=np.zeros((frames, n), np.int8), ammo=np.zeros((frames, n, nw), np.float32),
             has=np.zeros((frames, n, nw), bool), duck=np.zeros((frames, n), bool), dmg=np.zeros((frames, n), np.float32),
             score=np.zeros((frames, n), np.int32), died=np.zeros((frames, n), bool), frag=np.zeros((frames, n), bool))
    score = np.zeros(n, np.int64)
    for t in range(frames):
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        al, h = pol.act(obs[P][:, :ni], h)
        a[P, :al.shape[1]] = al
        obs, _, _, info = env.step(a)
        for e in info["events"]:
            v, k = int(e["victim"]), int(e["killer"])
            B["died"][t, v] = True
            if k >= 0 and k != v:
                score[k] += 1
                B["frag"][t, k] = True
            else:
                score[v] -= 1                                   # his own hand or the map: a point off, as in the game
        s = env.state
        B["pos"][t], B["vel"][t], B["air"][t] = s[:, :3], s[:, 3:6], s[:, 6] < 0.5
        B["yaw"][t], B["pitch"][t], B["hp"][t], B["ar"][t], B["w"][t] = env.yaw, env.pitch, env.hp, env.armor, env.weapon
        B["ammo"][t], B["has"][t], B["duck"][t], B["dmg"][t], B["score"][t] = env.ammo, env.has, env.duck, env.dmg_life, score
        if (t + 1) % wrap == 0:                                 # his clock, score and memory start over, as on the server
            env.round_t[:] = 0.0
            env.frags_r[:] = 0
            h[:] = 0.0
    # ---- every measured seat: a record as a demo gives one
    info_ = Y.map_info(env.w, mp)
    tm = (np.arange(frames) + 1) * E.DT
    T = Y.new_tally()
    rows = dict(blind=[], sight=[], view=[], fight=[])
    for p in P:
        o = p ^ 1
        dead = B["died"][:, p]
        alive = (B["hp"][:, p] > 0) & ~dead
        both = alive & np.concatenate([[False], alive[:-1]])
        shots = []
        for wq in range(nw):
            if E.WEAPONS[wq] == "g":
                continue
            dec = np.zeros(frames)
            dec[1:] = B["ammo"][:-1, p, wq] - B["ammo"][1:, p, wq]
            shots += [(int(i), wq, int(round(dec[i]))) for i in np.nonzero(both & (dec > 0.5) & (dec <= 6))[0]]
        up = np.zeros(frames, bool)
        up[1:] = B["dmg"][1:, p] > B["dmg"][:-1, p]
        enemy = B["pos"][:, o].copy()
        enemy[B["died"][:, o]] = np.nan
        oal = (B["hp"][:, o] > 0) & ~B["died"][:, o]
        oboth = oal & np.concatenate([[False], oal[:-1]])
        snd = np.zeros(frames, np.int64)                        # what the enemy does that is heard: 1 a jump, 2 a shot, 4 a pickup
        snd[1:] |= 1 * (~B["air"][:-1, o] & B["air"][1:, o] & (B["vel"][1:, o, 2] > 150.0) & oboth[1:])
        snd[1:] |= 2 * (((B["ammo"][:-1, o] - B["ammo"][1:, o]).max(1) > 0.5) & oboth[1:])
        snd[1:] |= 4 * (((B["hp"][1:, o] > B["hp"][:-1, o]) | (B["ar"][1:, o] > B["ar"][:-1, o])) & oboth[1:])
        ids = {int(p): seed * 1000 + int(p), int(o): seed * 1000 + int(o)}
        obits = [[tm[f], ids[int(v)], ids[int(k)] if B["frag"][f, k] else -1] for v, k in ((p, o), (o, p)) for f in np.nonzero(B["died"][:, v])[0]]
        od = np.where(B["died"][:, o], tm, -np.inf)
        od = np.maximum.accumulate(od)
        life = np.where(np.isfinite(od), tm - od, tm)             # seconds since the enemy last died (or since the game began)
        near = np.linalg.norm(B["pos"][:, o] - B["pos"][:, p], axis=1) <= 1200.0
        dhp, dar = np.zeros(frames), np.zeros(frames)
        dhp[1:], dar[1:] = B["hp"][1:, o] - B["hp"][:-1, o], B["ar"][1:, o] - B["ar"][:-1, o]
        picks = [[int(f), int(round(max(dhp[f], 0.0) + max(dar[f], 0.0))), int(dhp[f] >= 60 or dar[f] >= 40), int(dhp[f] > 0)]
                 for f in np.nonzero(oboth & near & ((dhp > 0) | (dar > 0)))[0]]      # what he sees or hears the enemy pick up
        kinds = np.full(frames, -1, np.int64)                   # the kind of sound the enemy makes on a frame (pro_yardsticks.SOUND_KINDS)
        up_ = np.zeros(frames, bool)
        up_[1:] = ~B["air"][:-1, o] & B["air"][1:, o] & oboth[1:]
        kinds[up_ & (B["vel"][:, o, 2] > 150.0)] = 0
        kinds[up_ & (B["vel"][:, o, 2] > 480.0)] = 1
        kinds[oboth & (dhp > 0) & (dhp < 20)] = 15
        kinds[oboth & (dar > 0) & (dar < 20)] = 15
        kinds[oboth & (dhp >= 20) & (dhp < 60)] = 14
        got = np.zeros(frames, bool)
        got[1:] = (B["has"][1:, o] & ~B["has"][:-1, o]).any(1)
        kinds[oboth & got] = 13
        kinds[oboth & (dar >= 20) & (dar < 40)] = 12
        kinds[oboth & (dar >= 40) & (dar < 90)] = 11
        kinds[oboth & (dar >= 90)] = 10
        kinds[oboth & (dhp >= 60)] = 9
        dam = np.zeros((frames, nw))
        dam[1:] = B["ammo"][:-1, o] - B["ammo"][1:, o]
        stream = {}
        for wn_, kd in (("rl", 2), ("rg", 3), ("lg", 4), ("mg", 5), ("hmg", 5), ("sg", 6), ("gl", 7), ("pg", 8)):
            for f in np.nonzero(oboth & (dam[:, list(E.WEAPONS).index(wn_)] > 0.5))[0]:
                if kd in (4, 5, 8) and tm[f] - stream.get(kd, -9.0) < 0.5:      # a stream of fire: its start only
                    stream[kd] = tm[f]
                    continue
                stream[kd] = tm[f]
                kinds[f] = kd
        jump_ = np.zeros(frames, bool)
        st_ = np.linalg.norm(B["pos"][1:, o] - B["pos"][:-1, o], axis=1)
        sp_ = np.linalg.norm(B["vel"][:, o], axis=1)
        jump_[1:] = (st_ > 100.0) & (st_ > 4.0 * np.maximum(sp_[1:], sp_[:-1]) * E.DT + 40.0) & oboth[1:]   # (a teleporter: pro_yardsticks.teleports' rule)
        kinds[jump_] = 16
        events = [[int(f), int(kinds[f]), *[float(x) for x in B["pos"][f, o]]] for f in np.nonzero((kinds >= 0) & near)[0]]
        rec = Y.make_record(t=tm, pos=B["pos"][:, p], vel=B["vel"][:, p], yaw=B["yaw"][:, p], pitch=B["pitch"][:, p], weapon=B["w"][:, p],
                            shots=shots, health=np.where(dead, 0.0, B["hp"][:, p]), armor=B["ar"][:, p], score=B["score"][:, p], enemy=enemy,
                            enemy_score=B["score"][:, o], clock=tm, alive=alive, eye_h=np.where(B["duck"][:, p], 12.0, 26.0),
                            enemy_air=B["air"][:, o].astype(np.int64), hits=np.cumsum(up | B["frag"][:, p]), ammo=B["ammo"][:, p],
                            owned=B["has"][:, p], enemy_weapon=B["w"][:, o], client=np.full(frames, seed * 1000 + int(p)),
                            ground=~B["air"][:, p], enemy_sound=snd, obits=obits, enemy_life=life, clock_exact=tm, enemy_pick=picks, enemy_events=events)
        t_, r_ = Y.measure(rec, env.w, info_)
        Y.add_tally(T, t_)
        for k in rows:
            rows[k] += r_[k]
    final = B["score"][-1].reshape(-1, 2)
    return dict(map=mp, opp=opp, tally=T, rows=rows, final=final.tolist(), players=len(P))


# ---------------------------------------------------------------------------------------------------------------------
# beside the pros
# ---------------------------------------------------------------------------------------------------------------------
def standing(rows_by_map):
    """{map: (sight, view)} -> tools/pro_places.py's strength() over all of it (the weapons, height, distance and
    outcome with the enemy in view), and by the pros' own cells: how strong the places are that his sightings begin in"""
    import pro_places as PP
    S, V, X = [], [], []
    there = dict(n=0, known=0, sum=0.0, weak=0, strong=0)
    for mp, (sight, view) in rows_by_map.items():
        sight, view = np.asarray(sight, np.int64).reshape(-1, 15), np.asarray(view, np.int64).reshape(-1, 8)
        if not len(sight):
            continue
        S.append(sight)
        V.append(view)
        X.append(PP.expected(sight))
        f = os.path.join(ROOT, "sim", "pro_places", mp + "_cells.json")
        if os.path.exists(f):                                   # the pros' strength of the cell each of his sightings begins in
            pc = json.load(open(f))
            size = np.array(pc["cell"])
            val = {tuple(c["cell"]): c.get("outcome_over_expected") for c in pc["cells"]}
            for c in np.floor(sight[:, :3] / size).astype(np.int64):
                v = val.get(tuple(int(x) for x in c))
                there["n"] += 1
                if v is not None:
                    there["known"] += 1
                    there["sum"] += v
                    there["weak"] += int(v < -0.05)
                    there["strong"] += int(v > 0.05)
    if not S:
        return {}
    sight, view, exp = np.concatenate(S), np.concatenate(V), np.concatenate(X)
    out = PP.strength(np.ones(len(sight), bool), np.ones(len(view), bool), sight, view, exp)
    if there["known"]:
        out["pros_strength_of_his_cells"] = dict(mean=round(there["sum"] / there["known"], 3), weak_cells_share=round(100.0 * there["weak"] / there["n"], 1),
                                                 strong_cells_share=round(100.0 * there["strong"] / there["n"], 1),
                                                 cells_the_pros_hardly_fight_from_share=round(100.0 * (there["n"] - there["known"]) / there["n"], 1))
    return out


def pros_standing(maps):
    """the same for the pros, from their rows (tools/pro_yardsticks.py's files in the demo root), where they are there"""
    import pro_yardsticks as Y
    rows = {}
    for mp in maps:
        fs, fv = (os.path.join(Y.demo_root(), "yardsticks", "{}_{}.npy".format(k, mp)) for k in ("sight", "view"))
        if os.path.exists(fs) and os.path.exists(fv):
            rows[mp] = (np.load(fs), np.load(fv))
    return standing(rows) if rows else {}


def pro_trips(mp):
    """the pros' trips of a map, {pair: rows}: from tools/pro_yardsticks.py's counts a demo, kept in one file a map"""
    import pro_yardsticks as Y
    keep = os.path.join(Y.demo_root(), "yardsticks", "trips_{}_v{}.json".format(mp, Y.VERSION))
    if os.path.exists(keep):
        return json.load(open(keep))
    out = {}
    for f in sorted(glob.glob(os.path.join(Y.demo_root(), "yardsticks", mp, "*.json"))):
        try:
            r = json.load(open(f))
        except ValueError:
            continue
        for k, v in r.get("tally", {}).get("trips", {}).items():
            out.setdefault(k, []).extend(v)
    if out:
        with open(keep, "w") as fh:
            json.dump(out, fh)
    return out


def routes_same_size(T, maps, draws=20):
    """his ways between the big items beside the pros' at the same number of trips: for every pair he has WAY_MIN_TRIPS
    trips of, as many of the pros' trips of that pair drawn at random (the mean of `draws` draws). The number of ways
    found grows with the number of trips, so the pros' own table (thousands of trips a pair) is no yardstick for him."""
    import pro_yardsticks as Y
    rng = np.random.default_rng(0)
    rows, ptrips = [], {}
    for k, tr in sorted(T["trips"].items()):
        mp = k.split(":")[0]
        if len(tr) < Y.WAY_MIN_TRIPS or mp not in maps:
            continue
        if mp not in ptrips:
            ptrips[mp] = pro_trips(mp)
        pt = ptrips[mp].get(k, [])
        if len(pt) < len(tr):
            continue

        def numbers(x):
            n = Y.ways(x)
            clear = [v for v in n if v >= max(3, Y.WAY_MIN_SHARE * len(x))]
            return len(clear), 100.0 * n[0] / len(x), 100.0 * (1.0 - sum(clear) / len(x))
        his = numbers(tr)
        pro = np.mean([numbers([pt[i] for i in rng.choice(len(pt), len(tr), replace=False)]) for _ in range(draws)], 0)
        rows.append(dict(pair=k, trips=len(tr), ways=his[0], commonest_share=round(his[1], 1), one_off_share=round(his[2], 1),
                         pros_ways=round(float(pro[0]), 2), pros_commonest_share=round(float(pro[1]), 1), pros_one_off_share=round(float(pro[2]), 1)))
    if not rows:
        return dict(pairs=0, by_pair=[])
    m = lambda key: round(float(np.mean([r[key] for r in rows])), 2)
    return dict(pairs=len(rows), trips=sum(r["trips"] for r in rows), ways=m("ways"), commonest_share=m("commonest_share"), one_off_share=m("one_off_share"),
                pros_ways=m("pros_ways"), pros_commonest_share=m("pros_commonest_share"), pros_one_off_share=m("pros_one_off_share"), by_pair=rows)


def fight_index(rows, model):
    """his own choices beside the pros' index (the formula of the pros' json, fitted on what they take and refuse): of
    the offers he takes or refuses, how many he takes, and how many the pros would in the same situations; by his health
    and armor and by the enemy's as he can guess it"""
    import pro_yardsticks as Y
    rows = rows[rows[:, 13] < 2]
    if not len(rows):
        return {}
    z = np.full(len(rows), model["intercept"], np.float64)
    for fi, (fname, levels) in enumerate(Y.FIGHT_FACTORS):
        z += np.array([model["effects"].get(fname, {}).get(lvl, 0.0) for lvl in levels])[rows[:, 3 + fi]]
    pro = 1.0 / (1.0 + np.exp(-z))
    he = (rows[:, 13] == 0).astype(np.float64)

    def cell(m):
        return dict(offers=int(m.sum()), he_takes_share=round(100.0 * float(he[m].mean()), 1), the_pros_would_take_share=round(100.0 * float(pro[m].mean()), 1)) if m.any() else dict(offers=0)
    out = dict(all=cell(np.ones(len(rows), bool)), by={})
    for fi in (0, 1, 3, 6, 7, 9):
        fname, levels = Y.FIGHT_FACTORS[fi]
        out["by"][fname] = {levels[lv]: cell(rows[:, 3 + fi] == lv) for lv in range(len(levels)) if (rows[:, 3 + fi] == lv).any()}
    out["his_choice_against_the_index_correlation"] = round(float(np.corrcoef(he, pro)[0, 1]), 3) if he.std() > 0 and pro.std() > 0 else None
    return out


def plans_match(tallies):
    """his lives beside the pros' plans (sim/pro_openings/<map>.json), over the spawn points the pros have 30 lives or more
    from: how many of his lives begin with the pros' commonest first item there, how many last 20 s, and of those how many
    follow the pros' commonest plan there and how many one of their three commonest (the plans of the lives that last
    20 s). tallies: {map: the rows of his lives (pro_yardsticks.SPAWN_COLS)}"""
    lives = last = f1 = top1 = top3 = 0
    pf, p1, p3, pl_, pn = 0.0, 0.0, 0.0, 0.0, 0
    for mp, rows in tallies.items():
        f = os.path.join(ROOT, "sim", "pro_openings", mp + ".json")
        if not os.path.exists(f):
            continue
        pro = json.load(open(f))
        lab = list(pro["items"].keys())
        plans = {sp["id"]: sp for sp in pro["spawns"] if sp["lives"] >= 30 and sp.get("plans_of_the_lives_that_last_20s") and sp.get("first_items")}
        for r in rows:
            sp = plans.get(int(r[0]))
            if sp is None:
                continue
            pp = sp["plans_of_the_lives_that_last_20s"]
            mine = [lab[k] for k in r[1:4] if 0 <= k < len(lab)]
            lives += 1
            f1 += int(bool(mine) and mine[0] == sp["first_items"][0]["item"])
            pf += sp["first_items"][0]["share"]
            pl_ += sp["lives_that_last_20s_share"] or 0.0
            pn += 1
            if r[9] > 0:
                last += 1
                top1 += int(mine == pp[0]["items"])
                top3 += int(any(mine == x["items"] for x in pp[:3]))
                p1 += pp[0]["share"]
                p3 += sum(x["share"] for x in pp[:3])
    if not lives:
        return {}
    return dict(lives=lives, first_item_is_the_pros_commonest_share=round(100.0 * f1 / lives, 1), the_pros_themselves_share=round(pf / pn, 1),
                lives_that_last_20s_share=round(100.0 * last / lives, 1), the_pros_lives_that_last_20s_share=round(pl_ / pn, 1), lives_that_last_20s=last,
                on_the_pros_commonest_plan_share=round(100.0 * top1 / last, 1) if last else None, on_one_of_their_three_commonest_share=round(100.0 * top3 / last, 1) if last else None,
                the_pros_themselves_on_their_commonest_share=round(p1 / last, 1) if last else None, on_their_three_commonest_share=round(p3 / last, 1) if last else None)


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")
    return "\n".join(out)


def show(res, pros):
    """one table a group: the pros (all maps), he against himself, he against the stand-in"""
    import pro_yardsticks as Y
    R = dict(pros=pros["maps"]["all"], self=res.get("self", {}).get("all"), nightmare=res.get("nightmare", {}).get("all"))
    who = [(k, lbl) for k, lbl in WHO if R.get(k)]
    head = [lbl for _, lbl in who]

    def row(label, f):
        out = [label]
        for k, _ in who:
            try:
                out.append(f(R[k]))
            except (KeyError, TypeError, IndexError):
                out.append(None)
        return out

    def three(f):                                               # one cell: the pros / himself / the stand-in
        out = []
        for k, _ in who:
            try:
                v = f(R[k])
            except (KeyError, TypeError, IndexError):
                v = None
            out.append("-" if v is None else str(v))
        return " / ".join(out)
    print("## {} through the pros' yardsticks\n".format(res.get("tag", "he")))
    g = res.get("games", {})
    print("Network {}. {} maps; against himself {} games a map (every seat measured), against the stand-in {}; games of {:g} minutes.".format(
        res.get("policy", ""), len(res.get("maps", [])), g.get("self"), g.get("nightmare"), res.get("minutes", 10.0)))
    if res.get("score"):
        print("Against the stand-in, mean score of a game, he : stand-in: " + ", ".join("{} {} : {}".format(m, v[0], v[1]) for m, v in res["score"].items()) + ".")
    print("\n" + table([row("player-games measured", lambda r: r["demos"]), row("minutes of play", lambda r: r["minutes"])], ["", *head]))
    print("\n### 1. Spam: shots with no enemy in view for a second or more\n")
    rows = []
    for wn in ("rl", "gl", "pg"):
        nm = Y.W_NAMES[wn]
        rows += [row(nm + ": shots a minute", lambda r, wn=wn: r["spam"][wn]["shots_a_minute"]),
                 row(nm + ": blind a minute", lambda r, wn=wn: r["spam"][wn]["blind_a_minute"]),
                 row(nm + ": blind, % of its shots", lambda r, wn=wn: r["spam"][wn]["blind_share"]),
                 row(nm + ": of the blind ones at his own feet, %", lambda r, wn=wn: r["spam"][wn]["at_own_feet_share"]),
                 row(nm + ": blind and away a minute", lambda r, wn=wn: r["spam"][wn]["blind_away_a_minute"]),
                 row(nm + ": away: distance to where it lands, median", lambda r, wn=wn: r["spam"][wn]["landing_distance_median"]),
                 row(nm + ": away: enemy in view near there within 2 s, %", lambda r, wn=wn: r["spam"][wn]["met_share"]),
                 row(nm + ": away: a hit as it lands, %", lambda r, wn=wn: r["spam"][wn]["hit_share"])]
    for wn in ("rg", "lg", "mg", "sg"):
        rows += [row(Y.W_NAMES[wn] + ": shots a minute", lambda r, wn=wn: r["spam"][wn]["shots_a_minute"]),
                 row(Y.W_NAMES[wn] + ": blind, % of its shots", lambda r, wn=wn: r["spam"][wn]["blind_share"])]
    print(table(rows, ["", *head]))
    print("\n### 2. Combinations\n")
    rows = []
    for nm in ("rocket then rail or lightning", "grenade then rail or lightning"):
        rows += [row(nm + ": a ten minutes", lambda r, nm=nm: r["combinations"][nm]["per_ten_minutes"]),
                 row(nm + ": enemy in the air at the second shot, %", lambda r, nm=nm: r["combinations"][nm]["enemy_in_the_air_share"]),
                 row(nm + ": the second weapon is the rail, %", lambda r, nm=nm: r["combinations"][nm]["rail_share"])]
    rows.append(row("enemy in the air, % of all his time in view (to compare)", lambda r: r["combinations"]["enemy in the air, of all the time he is in view"]))
    print(table(rows, ["", *head]))
    lead = " / ".join(head)
    print("\n### 3. By score and time (each cell: {})\n".format(lead))
    keys = (("minutes", "minutes"), ("in_view_share", "enemy in view, %"), ("toward_enemy_speed", "speed toward the enemy in view"),
            ("frags_a_minute", "frags a minute"), ("deaths_a_minute", "deaths a minute"), ("travelling_speed", "travelling speed"),
            ("stacked_share", "150+ stack, %"), ("blind_rockets_a_minute", "blind rockets away a minute"))
    names = Y.STATES + ["ahead", "level", "behind", "all", "stack under 100", "stack 100 to 149", "stack 150 or more"]
    print(table([[n] + [three(lambda r, n=n, k=k: r["by_state"][n][k]) for k, _ in keys] for n in names], ["state"] + [lbl for _, lbl in keys]))
    print("\n### 4. Item timing\n")
    rows = []
    for k in ("mega", "red", "yellow"):
        rows += [row(k + ": pickups a ten minutes", lambda r, k=k: r["items"][k]["pickups_a_ten_minutes"]),
                 row(k + ": back within 150 units, 2 s either side of its return, %", lambda r, k=k: r["items"][k]["back_at_return_share"]),
                 row(k + ": took it again within 5 s of its return, %", lambda r, k=k: r["items"][k]["took_it_again_within_5s_share"]),
                 row(k + ": died before its return, %", lambda r, k=k: r["items"][k]["died_before_return_share"]),
                 row(k + ": seconds between his pickups, median", lambda r, k=k: r["items"][k]["gap_median_s"])]
    print(table(rows, ["", *head]))
    print("\n### 6. How predictable: places, height, ways, standing\n")
    rows = [row("one player in one game: time in his 8 most-used cells, %", lambda r: r["predictability"]["position"]["per_player_top8_share"]),
            row("one player in one game: cells that hold 80% of his time", lambda r: r["predictability"]["position"]["per_player_cells_for_80"]),
            row("one player in one game: entropy of his time over cells, bits", lambda r: r["predictability"]["position"]["per_player_entropy_bits"]),
            row("enemy in view: he stands 48 units or more higher, %", lambda r: r["predictability"]["height"]["higher_share"]),
            row("enemy in view: 48 or more lower, %", lambda r: r["predictability"]["height"]["lower_share"]),
            row("enemy in view: level, %", lambda r: r["predictability"]["height"]["level_share"]),
            row("time in the lowest third of the heights the pros visit, %", lambda r: r["predictability"]["lowest_third_share"]),
            row("standing (under 50 units a second), % of his time alive", lambda r: r["predictability"]["standing"]["share"]),
            row("longest stand in a minute, seconds: mean", lambda r: r["predictability"]["standing"]["longest_a_minute_mean"]),
            row("longest stand in a minute, seconds: median", lambda r: r["predictability"]["standing"]["longest_a_minute_median"]),
            row("longest stand in a minute, seconds: 90th percentile", lambda r: r["predictability"]["standing"]["longest_a_minute_90"])]
    print(table(rows, ["", *head]))
    rt = res.get("routes", {})
    if any(rt.get(k, {}).get("pairs") for k in ("self", "nightmare")):
        print("\nHis ways between the big items, beside the pros' at the same number of trips of the same pairs (pairs he has 30 trips or more of):\n")
        print(table([[lbl, rt[k]["pairs"], rt[k]["trips"], rt[k]["ways"], rt[k]["pros_ways"], rt[k]["commonest_share"], rt[k]["pros_commonest_share"],
                      rt[k]["one_off_share"], rt[k]["pros_one_off_share"]] for k, lbl in WHO[1:] if rt.get(k, {}).get("pairs")],
                    ["", "pairs", "trips", "clear ways a pair: he", "the pros", "on the commonest way, %: he", "the pros", "on a way of their own, %: he", "the pros"]))
    print("\n### 7. Aggression by advantage: the 3 s after the enemy comes into view (each cell: {})\n".format(lead))
    keys = (("sightings", "sightings"), ("closing_speed", "closing speed"), ("push_share", "pushes, %"), ("fires_within_1s_share", "fires within 1 s, %"),
            ("view_broken_share", "view broken, %"), ("fragged_him_in_3s_share", "fragged him in 3 s, %"), ("died_in_3s_share", "died in 3 s, %"),
            ("frags_less_deaths_in_10s", "frags less deaths in 10 s"))
    for title, tab in (("his health and armor", "by_stack"), ("his health and armor, and how long ago he fragged him", "by_stack_and_last_frag"),
                       ("his health and armor, and the enemy's weapon", "by_stack_and_enemy_weapon"), ("his health and armor, and the score", "by_stack_and_score"),
                       ("his health and armor, and the distance at the sighting", "by_stack_and_distance")):
        names = list(R["pros"]["aggression"][tab].keys())
        print(table([[n] + [three(lambda r, n=n, k=k, tab=tab: r["aggression"][tab][n][k]) for k, _ in keys] for n in names], [title] + [lbl for _, lbl in keys]) + "\n")
    print("### 9. Walking and quiet (the pros' walking speed is 160; each cell: {})\n".format(lead))
    keys = (("minutes", "minutes"), ("walking_share", "walking, %"), ("crouched_moving_share", "crouched and moving, %"), ("standing_share", "standing, %"),
            ("quiet_share", "quiet in all, %"), ("in_the_air_share", "in the air, %"))
    names = list(R["pros"]["walking"]["by"].keys())
    print(table([[n] + [three(lambda r, n=n, k=k: r["walking"]["by"][n][k]) for k, _ in keys] for n in names], ["situation"] + [lbl for _, lbl in keys]))
    print("\n### 11. Combinations by hits\n")
    keys = (("rocket_hits_a_ten_minutes", "rocket hits a ten minutes"), ("rocket_hit_share", "rockets that hit, %"),
            ("rocket_hit_then_lightning_or_rail_hit_a_ten_minutes", "rocket hit, then a lightning or rail hit within 1.5 s: a ten minutes"),
            ("rocket_hits_followed_by_a_beam_hit_share", "... % of his rocket hits"),
            ("grenade_hit_then_lightning_or_rail_hit_a_ten_minutes", "grenade hit, then a lightning or rail hit within 1.5 s: a ten minutes"),
            ("rocket_hit_then_rocket_hit_a_ten_minutes", "rocket hit, then another rocket's hit within 1.2 s: a ten minutes"),
            ("frags_after_a_pair_share", "his frags within 2 s after such a pair, %"), ("frags_after_a_juggle_share", "his frags within 2 s after two rocket hits, %"))
    print(table([row(lbl, lambda r, k=k: r["hit_combinations"][k]) for k, lbl in keys], ["", *head]) + "\n")
    print("### 12. Where he looks with no enemy in view (each cell: {})\n".format(lead))
    print("(For him the enemy's place is always known; for the pros only while the server sent the enemy. The sounds are a jump, a shot, a pickup within 1200 units for both.)\n")
    nv = (("view_within_20_of_the_enemy_share", "his view within 20 degrees of the enemy's true place, % of the time with no enemy in view"),
          ("view_within_20_of_where_he_last_saw_him_share", "within 20 degrees of where he last saw him, %"),
          ("view_within_20_of_the_nearest_mega_or_armor_share", "within 20 degrees of the nearest mega or armor, %"))
    print(table([row(lbl, lambda r, k=k: r["looking"]["no_enemy_in_view"][k]) for k, lbl in nv], ["", *head]) + "\n")
    keys = (("sightings", "sightings"), ("sideways_median", "sideways off, degrees: median"), ("sideways_75", "75th"), ("sideways_under_10_share", "under 10, %"),
            ("sideways_under_20_share", "under 20, %"), ("up_down_median", "up-down off: median"), ("up_down_under_10_share", "under 10, %"))
    rows = [["all sightings, " + lbl] + [three(lambda r, lbl=lbl, k=k: r["looking"]["at_a_sighting"][lbl][k]) for k, _ in keys] for _, lbl in Y.LAGS]
    for grp in ("by_time_unseen", "by_sound"):
        for band in R["pros"]["looking"][grp]:
            rows += [[band + ", " + lbl] + [three(lambda r, grp=grp, band=band, lbl=lbl, k=k: r["looking"][grp][band][lbl][k]) for k, _ in keys] for _, lbl in Y.LAGS[::2]]
    print(table(rows, ["the angle from his view to where the enemy appears"] + [lbl for _, lbl in keys]))
    print("\n### 13. Holds and traps\n")
    keys = (("a_ten_minutes", "holds a ten minutes"), ("share_of_his_time_alive", "% of his time alive"), ("seconds_median", "seconds: median"), ("seconds_90", "seconds: 90th percentile"),
            ("enemy_in_view_within_3s_of_its_end_share", "enemy in view within 3 s of its end, %"), ("he_deals_damage_first_within_5s_share", "he deals damage first within 5 s, %"),
            ("he_takes_damage_first_within_5s_share", "he takes damage first, %"), ("a_frag_for_him_within_5s_share", "a frag for him within 5 s, %"),
            ("a_frag_of_him_within_5s_share", "a frag of him, %"), ("view_at_a_big_item_share", "his view at a big item, % of the hold"),
            ("view_at_a_teleporter_exit_share", "at a teleporter's exit, %"), ("blind_rockets_and_grenades_from_holds_a_ten_minutes", "blind rockets and grenades from holds a ten minutes"),
            ("traps_a_ten_minutes", "of them hit within 1.5 s (traps) a ten minutes"), ("holds_with_a_trap_share", "holds with a trap, %"))
    rows = [row(lbl, lambda r, k=k: r["holds"][k]) for k, lbl in keys]
    rows += [row("in hand: " + w_ + ", %", lambda r, w_=w_: r["holds"]["weapon_in_hand"][w_]) for w_ in ("rockets", "lightning", "rail")]
    print(table(rows, ["", *head]))
    print("\n### 14. His hands (each cell: {})\n".format(lead))
    keys = (("median", "median"), ("p75", "75th"), ("p90", "90th"), ("p99", "99th"), ("under_30_share", "under 30, % of the time"), ("under_300_share", "under 300, %"))
    print(table([[n] + [three(lambda r, n=n, k=k: r["hands"]["turn_speed"][n][k]) for k, _ in keys] for n in ("no enemy in view", "enemy in view")],
                ["turn speed of his view, degrees a second"] + [lbl for _, lbl in keys]))
    fl = (("off_target_at_the_sighting_median", "off target as the enemy comes into view, degrees, median"), ("off_target_0_3s_later_median", "off target 0.3 s later, median"),
          ("turn_in_0_3s_median", "his view's turn in those 0.3 s, degrees: median"), ("turn_in_0_3s_90", "90th percentile"), ("peak_speed_median", "peak turn speed in them, degrees a second: median"),
          ("peak_speed_90", "90th percentile"), ("seconds_to_the_peak_median", "seconds to the peak, median"), ("a_shot_within_3s_share", "a shot within 3 s, %"),
          ("seconds_to_the_first_shot_median", "seconds to the first shot, median"), ("a_hit_within_3s_share", "a hit within 3 s, %"), ("seconds_to_the_first_hit_median", "seconds to the first hit, median"))
    print("\n" + table([row(lbl, lambda r, k=k: r["hands"]["flick"][k]) for k, lbl in fl], ["the flick", *head]))
    bands = ("all", *Y.ACC_BANDS[:5])
    rows = []
    for wn in ("lightning", "rail", "rockets", "plasma", "machine gun", "shotgun"):
        rows.append([wn + ": hits, % of its shots"] + [three(lambda r, wn=wn, b=b: r["hands"]["accuracy"][wn][b]["hit_share"]) for b in bands])
        if wn == "rockets":
            rows.append(["rockets: direct hits, %"] + [three(lambda r, b=b: r["hands"]["accuracy"]["rockets"][b]["direct_share"]) for b in bands])
        rows.append([wn + ": shots"] + [three(lambda r, wn=wn, b=b: r["hands"]["accuracy"][wn][b]["shots"]) for b in bands])
    print("\n" + table(rows, ["accuracy by the distance to the enemy", *bands]))
    rows = [[b, three(lambda r, b=b: r["hands"]["lightning_by_crossing_speed"][b]["shots"]), three(lambda r, b=b: r["hands"]["lightning_by_crossing_speed"][b]["hit_share"])] for b in Y.CROSS_BANDS]
    rows.append(["his view's changes of turning direction a second while tracking with lightning", "", three(lambda r: r["hands"]["lightning_tracking"]["turning_direction_changes_a_second"])])
    print("\n" + table(rows, ["lightning", "cells", "hits, %"]))
    print("\n### 15. Movement in a fight: the enemy in view within 800 units (each cell: {})\n".format(lead))
    keys = (("minutes", "minutes"), ("strafe_changes_a_second", "changes of strafe direction a second"), ("in_the_air_share", "in the air, %"), ("crouched_share", "crouched, %"),
            ("jumps_a_minute", "jumps a minute"), ("speed", "speed"), ("distance_change_a_second", "change of the distance a second"))
    print(table([[n] + [three(lambda r, n=n, k=k: r["fight_movement"]["by"][n][k]) for k, _ in keys] for n in R["pros"]["fight_movement"]["by"]], ["", *[lbl for _, lbl in keys]]))
    keys = (("hits", "hits of 50 or more"), ("died_within_2s_share", "dead within 2 s, %"), ("lost_view_share", "the enemy out of view for 0.5 s within 2 s, %"), ("weapon_change_share", "weapon changed, %"),
            ("distance_change_mean", "change of the distance in 2 s"), ("farther_by_100_share", "farther by 100 or more, %"), ("nearer_by_100_share", "nearer by 100 or more, %"))
    print("\n" + table([[n] + [three(lambda r, n=n, k=k: r["fight_movement"]["after_a_big_hit"][n][k]) for k, _ in keys] for n in R["pros"]["fight_movement"]["after_a_big_hit"]],
                        ["after a hit of 50 or more that he lives through", *[lbl for _, lbl in keys]]) + "\n")
    print("### 16. Fights taken and refused (each cell: {})\n".format(lead))
    keys = (("sightings", "sightings"), ("takes_share", "takes it, %"), ("commits_share", "... and is still in it after 3 s (commits), %"),
            ("refuses_share", "refuses it, %"), ("index", "index: taken of taken and refused, %"))

    def frow(name, f):
        return [name] + [three(lambda r, k=k: f(r)[k]) for k, _ in keys] + [three(lambda r: f(r)["when_taken"]["frags_for_less_of_him"]),
                                                                           three(lambda r: f(r)["when_refused"]["frags_for_less_of_him"]), three(lambda r: f(r)["taking_pays"])]
    rows = [frow("all", lambda r: r["fights"]["all"])]
    for fname, tab in R["pros"]["fights"]["by"].items():
        rows += [frow("{}: {}".format(fname, lvl), lambda r, fname=fname, lvl=lvl: r["fights"]["by"][fname][lvl]) for lvl in tab]
    print(table(rows, ["situation"] + [lbl for _, lbl in keys] + ["taken: frags for less of him in 10 s", "refused: the same", "taking pays (frags)"]))
    fi_ = res.get("fight_index", {})
    if fi_:
        print("\nHis choices beside the pros' index (of the offers taken or refused: he takes / the pros would take in the same situations, %):\n")
        names = [("all", lambda v: v["all"])] + [("{}: {}".format(f, l_), lambda v, f=f, l_=l_: v["by"][f][l_]) for f, t_ in next(iter(fi_.values()))["by"].items() for l_ in t_]
        frs = []
        for nm, g in names:
            line = [nm]
            for k, _ in WHO[1:]:
                try:
                    c = g(fi_[k])
                    line += [c["offers"], c.get("he_takes_share"), c.get("the_pros_would_take_share")]
                except (KeyError, TypeError):
                    line += [None, None, None]
            frs.append(line)
        print(table(frs, ["", "against himself: offers", "he takes, %", "the pros would, %", "against the stand-in: offers", "he takes, %", "the pros would, %"]))
    print("\n### 17. The flick by how far off target he is as the enemy appears (each cell: {})\n".format(lead))
    keys = (("appearances", "appearances"), ("a_shot_within_3s_share", "a shot within 3 s, %"), ("seconds_to_the_first_shot_median", "seconds to the first shot, median"),
            ("a_hit_within_3s_share", "a hit within 3 s, %"), ("seconds_to_the_first_hit_median", "seconds to the first hit, median"),
            ("hits_of_the_first_half_second_of_fire_share", "hits of the first 0.5 s of fire, %"))
    rows = [[b] + [three(lambda r, b=b, k=k: r["flick_curve"]["by_angle"][b][k]) for k, _ in keys] for b in Y.ERR_BANDS]
    for wn in Y.FLICK_W[:3]:
        rows += [["{}, {}".format(wn, b)] + [three(lambda r, wn=wn, b=b, k=k: r["flick_curve"]["by_angle_and_weapon"][wn][b][k]) for k, _ in keys] for b in Y.ERR_BANDS]
    print(table(rows, ["off target as a clear line to the enemy opens"] + [lbl for _, lbl in keys]))
    tv = [row("travelling at 350 or more: his view off his direction of travel, degrees, median", lambda r: r["view_travelling"]["view_off_his_direction_of_travel"]["median"]),
          row("... within 20 degrees of it, % of that time", lambda r: r["view_travelling"]["view_off_his_direction_of_travel"]["within_20_share"]),
          row("... over 90 degrees off it, %", lambda r: r["view_travelling"]["view_off_his_direction_of_travel"]["over_90_share"])]
    for lbl in ("travelling at 350 or more, no enemy in view", "all his time with no enemy in view"):
        for k, kl in (("view_within_20_of_where_he_last_saw_him_share", "within 20 degrees of where he last saw him, %"),
                      ("view_at_one_of_the_maps_places_share", "at one of the map's places, %"),
                      ("view_at_the_doorway_the_enemy_would_come_through_share", "at the doorway the enemy would come through, %")):
            tv.append(row("{}: {}".format(lbl, kl), lambda r, lbl=lbl, k=k: r["view_travelling"][lbl][k]))
    print("\n" + table(tv, ["his view with nobody in view", *head]) + "\n")
    if R["pros"].get("openings", {}).get("known"):
        print("### 18. After a spawn and after a frag (each cell: {})\n".format(lead))
        keys = (("lives", "lives"), ("first_item_a_weapon_share", "first item a weapon, %"), ("first_item_an_armor_share", "an armor, %"), ("first_item_the_mega_share", "the mega, %"),
                ("no_item_in_15s_share", "no item in 15 s, %"), ("seconds_to_the_first_weapon_median", "seconds to the first weapon, median"),
                ("enemy_in_view_within_15s_share", "enemy in view within 15 s, %"), ("stack_20s_on_median", "stack 20 s on, median"), ("dead_within_20s_share", "dead within 20 s, %"),
                ("frag_for_him_within_30s_share", "a frag for him within 30 s, %"), ("frag_of_him_within_30s_share", "a frag of him, %"))
        print(table([[n] + [three(lambda r, n=n, k=k: r["openings"]["after_a_spawn"][n][k]) for k, _ in keys] for n in R["pros"]["openings"]["after_a_spawn"]],
                    ["after a spawn"] + [lbl for _, lbl in keys]))
        print("\n" + table([row("spawn points with 30 lives or more", lambda r: r["openings"]["plans"]["spawn_points_with_30_lives"]),
                             row("their commonest plan holds, % of a point's lives", lambda r: r["openings"]["plans"]["commonest_plan_share_mean"]),
                             row("the three commonest, %", lambda r: r["openings"]["plans"]["three_commonest_plans_share_mean"])], ["plans", *head]))
        pm_ = res.get("plans_match", {})
        lr_ = res.get("lives_rows", {})
        pm_ = {k: plans_match(lr_[k]) for k in lr_} if lr_ else pm_          # (set beside the pros' files as they are now)
        if any(pm_.get(k) for k, _ in WHO[1:]):
            cols_ = (("lives", "lives"), ("first_item_is_the_pros_commonest_share", "his first item is the pros' commonest there, %"), ("the_pros_themselves_share", "the pros themselves, %"),
                     ("lives_that_last_20s_share", "lives that last 20 s, %"), ("the_pros_lives_that_last_20s_share", "the pros', %"),
                     ("on_the_pros_commonest_plan_share", "of those: on the pros' commonest plan, %"), ("the_pros_themselves_on_their_commonest_share", "the pros themselves, %"),
                     ("on_one_of_their_three_commonest_share", "on one of their three commonest, %"), ("on_their_three_commonest_share", "the pros themselves, %"))
            print("\n" + table([[lbl] + [pm_[k].get(c) for c, _ in cols_] for k, lbl in WHO[1:] if pm_.get(k)],
                                ["his lives beside the pros' plans of the same spawn point"] + [h for _, h in cols_]))
        keys = (("frags", "frags"), ("an_item_within_15s_share", "an item within 15 s, %"), ("enemy_in_view_again_within_15s_share", "the enemy in view again within 15 s, %"),
                ("frag_for_him_within_30s_share", "a frag for him within 30 s, %"), ("frag_of_him_within_30s_share", "a frag of him, %"),
                ("view_on_a_spawn_point_2_to_6s_on_share", "his view on a spawn point 2 to 6 s on, %"))
        print("\n" + table([[n] + [three(lambda r, n=n, k=k: r["openings"]["after_a_frag"][n][k]) for k, _ in keys] for n in R["pros"]["openings"].get("after_a_frag", {})],
                            ["after a frag of his"] + [lbl for _, lbl in keys]))
        tabs = Y.openings_tables(res.get("maps", []), bot=lr_.get("self") or {})
        if tabs:
            print("\nThe openings a map (spawn points with 30 lives of the pros or more; his lives against himself beside them):\n" + tabs)
        print("\n### 19. What he does with a sound of the enemy's, the enemy out of view (each cell: {})\n".format(lead))
        keys = (("n", "heard"), ("degrees_gained_in_1s", "degrees turned toward it in 1 s"), ("degrees_gained_in_2s", "in 2 s"), ("turned_10_toward_in_1s_share", "turned 10 or more toward it in 1 s, %"),
                ("movement_turned_60_in_2s_share", "his way turned by 60 or more in 2 s, %"), ("weapon_changed_in_2s_share", "weapon changed in 2 s, %"),
                ("blind_shot_toward_it_in_2s_share", "a blind shot toward it in 2 s, %"), ("enemy_in_view_within_2s_share", "the enemy in view within 2 s, %"))
        rows = [["no sound (the baseline)"] + [three(lambda r, k=k: r["sounds"]["baseline"]["all"][k]) for k, _ in keys]]
        rows += [[nm] + [three(lambda r, nm=nm, k=k: r["sounds"]["by_kind"][nm]["all"][k]) for k, _ in keys] for nm in R["pros"]["sounds"].get("by_kind", {})]
        print(table(rows, ["the sound"] + [lbl for _, lbl in keys]))
        print("\n### 20. The weapon in his hand with nobody in view (each cell: {}); rail and lightning hum\n".format(lead))
        keys = (("minutes", "minutes"), ("humming_share", "rail or lightning, %"), ("rail_share", "rail, %"), ("lightning_share", "lightning, %"), ("rockets_share", "rockets, %"),
                ("machine_gun_share", "machine gun, %"), ("other_share", "another, %"))
        rows = []
        for mode in ("travelling", "holding"):
            rows += [["{}: {}".format(mode, n)] + [three(lambda r, mode=mode, n=n, k=k: r["weapon_in_hand"][mode][n][k]) for k, _ in keys] for n in R["pros"]["weapon_in_hand"][mode]]
        print(table(rows, [""] + [lbl for _, lbl in keys]))
        ws = ("machine gun", "shotgun", "lightning", "rail", "rockets", "grenades", "plasma")
        print("\n" + table([[n] + [three(lambda r, n=n, w_=w_: r["weapon_in_hand"]["shots_with_nobody_in_view_for_1s"][n][w_ + "_a_minute"]) for w_ in ws]
                             for n in R["pros"]["weapon_in_hand"]["shots_with_nobody_in_view_for_1s"]], ["shots a minute with nobody in view for 1 s or more", *ws]))
        print("\n### 21. Teleporters and high take-offs\n")
        keys = (("trips_a_ten_minutes", "teleporter trips a ten minutes"), ("speed_in_median", "speed going in, median"), ("speed_out_median", "speed coming out, median"),
                ("jumped_as_he_came_out_share", "jumps within 0.2 s of the exit, %"), ("in_the_air_as_he_went_in_share", "in the air as he went in, %"),
                ("plain_jumps_a_ten_minutes", "plain jumps a ten minutes"),
                ("high_take_offs_a_ten_minutes", "high take-offs without a weapon a ten minutes"), ("high_take_offs_share_of_his_jumps", "... % of his jumps"),
                ("rocket_take_offs_a_ten_minutes", "take-offs on his own rocket a ten minutes"), ("grenade_take_offs_a_ten_minutes", "... on his own grenade"),
                ("plasma_take_offs_a_ten_minutes", "... on his own plasma"),
                ("jumps_that_come_down_50_higher_a_ten_minutes", "plain jumps that come down 50 or more higher (a step in the air) a ten minutes"))
        print(table([row(lbl, lambda r, k=k: r["teleporters"][k]) for k, lbl in keys], ["", *head]) + "\n")
    st = res.get("standing", {})
    if st:
        print("### 8. With the enemy in view: weapons, distance, outcome, and the strength of where he stands\n")
        S = {k: st.get(k) for k, _ in who}
        ws = sorted({w for v in S.values() if v for w in v.get("weapon_shares", {})}, key=lambda w: -(S["pros"] or {}).get("weapon_shares", {}).get(w, 0))

        def srow(label, f):
            out = [label]
            for k, _ in who:
                try:
                    out.append(f(S[k]))
                except (KeyError, TypeError):
                    out.append(None)
            return out
        rows = [srow("sightings", lambda s: s["sightings"]), srow("frags less deaths in the 10 s after a sighting", lambda s: s["outcome"]),
                srow("frags a sighting", lambda s: s["frags_a_sighting"]), srow("deaths a sighting", lambda s: s["deaths_a_sighting"]),
                srow("distance to the enemy in view, median", lambda s: s["distance_median"]), srow("firing, % of the time in view", lambda s: s["firing_share"])]
        rows += [srow("in hand, % of the time in view: " + w, lambda s, w=w: s["weapon_shares"].get(w, 0.0)) for w in ws]
        rows += [srow("of his firing in view, %: " + w, lambda s, w=w: s["fire_shares"].get(w, 0.0)) for w in ws]
        rows += [srow("the pros' strength of the cells his sightings begin in, mean", lambda s: s["pros_strength_of_his_cells"]["mean"]),
                 srow("sightings that begin in a cell weak for the pros (under -0.05), %", lambda s: s["pros_strength_of_his_cells"]["weak_cells_share"]),
                 srow("... in a cell strong for the pros (over +0.05), %", lambda s: s["pros_strength_of_his_cells"]["strong_cells_share"]),
                 srow("... in a cell the pros hardly fight from (under 30 sightings), %", lambda s: s["pros_strength_of_his_cells"]["cells_the_pros_hardly_fight_from_share"])]
        print(table(rows, ["", *head]))


def merged(path):
    """his json with the second file's groups put back into its maps"""
    import pro_yardsticks as Y
    res = json.load(open(path, encoding="utf-8"))
    f2 = Y.second_file(path)
    if os.path.exists(f2):
        r2 = json.load(open(f2, encoding="utf-8"))
        for k in ("fight_index", "plans_match", "lives_rows"):
            if r2.get(k):
                res[k] = r2[k]
        for opp in ("self", "nightmare"):
            for m, v in r2.get(opp, {}).items():
                res.get(opp, {}).get(m, {}).update(v)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_v15c", "policy_end_v15c.pt"))
    ap.add_argument("--tag", default="v15c")
    ap.add_argument("--map", default=MAPS)
    ap.add_argument("--games-self", type=int, default=12, help="games a map against himself (two measured players a game)")
    ap.add_argument("--games-nightmare", type=int, default=8)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--round", type=float, default=120.0, help="his clock and memory start over every this many seconds, as in training")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator setting on top of the defaults (SETS)")
    ap.add_argument("--seed", type=int, default=500)
    ap.add_argument("--json", default=None)
    ap.add_argument("--pros", default=os.path.join(ROOT, "docs", "pro_yardsticks.json"))
    ap.add_argument("--show", default=None)
    a = ap.parse_args()
    import pro_yardsticks as Y0
    pros = Y0.load_both(a.pros)
    if a.show:
        return show(merged(a.show), pros)
    low_priority()
    envvars = dict(x.split("=", 1) for x in SETS.split())
    envvars.update(dict(x.split("=", 1) for x in a.set))
    os.environ.update(envvars)                                   # (before anything of the simulator is imported, here and in the workers)
    import pro_yardsticks as Y
    import pro_places as PP
    import test_suite as TS
    pol = TS.Policy(a.policy, seed=1)
    maps = a.map.split(",")
    jobs = []
    for q, mp in enumerate(maps):
        if a.games_self > 0:
            jobs.append((a.env, envvars, mp, a.games_self, a.minutes, a.seed + 17 * q, pol, "self", a.round))
        if a.games_nightmare > 0:
            jobs.append((a.env, envvars, mp, a.games_nightmare, a.minutes, a.seed + 1000 + 17 * q, pol, "nightmare", a.round))
    t0 = time.time()
    with mp_.Pool(min(a.procs, len(jobs)), maxtasksperchild=1) as pool:      # (one World a process: a new process a job)
        res = []
        for r in pool.imap_unordered(play, jobs):
            res.append(r)
            print("{} {}: {} players measured, {:.0f} s".format(r["map"], r["opp"], r["players"], time.time() - t0), file=sys.stderr, flush=True)
    zr = Y.zranges(a.pros)
    out = dict(tag=a.tag, policy=os.path.relpath(a.policy, ROOT).replace("\\", "/") if os.path.isabs(a.policy) else a.policy, env=a.env,
               settings={k: (v if k != "LEGS_NET" else os.path.relpath(v, ROOT).replace("\\", "/") if os.path.isabs(v) else v) for k, v in envvars.items()},
               maps=maps, minutes=a.minutes, games=dict(self=a.games_self, nightmare=a.games_nightmare), standing={}, cells={}, routes={}, score={})
    for opp in ("self", "nightmare"):
        rs = [r for r in res if r["opp"] == opp]
        if not rs:
            continue
        total, per, rows, frows, lives = Y.new_tally(), {}, {}, [], {}
        for r in sorted(rs, key=lambda r: maps.index(r["map"])):
            per[r["map"]] = Y.report(r["tally"], zrange=zr)
            ag = per[r["map"]]["aggression"]                    # (a map alone is too thin for the tables by two and more sides)
            per[r["map"]]["aggression"] = {k: ag[k] for k in ("all", "by_stack", "by_last_frag", "by_enemy_weapon", "by_score")}
            for k in ("ground_time_by_speed_share", "steady_ground_time_by_speed_share", "crouched_ground_time_by_speed_share"):
                per[r["map"]]["walking"].pop(k, None)           # (the histograms under "all")
            for grp, keys in (("looking", ("by_time_unseen", "by_sound")), ("hands", ("lightning_by_crossing_speed",))):
                for k in keys:
                    per[r["map"]][grp].pop(k, None)             # (a map alone is too thin for these)
            for v in per[r["map"]]["hands"]["accuracy"].values():
                for k in [k for k in v if k != "all"]:
                    v.pop(k)
            per[r["map"]].get("weapon_in_hand", {}).pop("holding_by_cell", None)
            per[r["map"]].update(Y.slim_map({k: per[r["map"]][k] for k in Y.GROUPS2 if k in per[r["map"]]}))
            ab = per[r["map"]]["fight_movement"]["after_a_big_hit"]
            per[r["map"]]["fight_movement"]["after_a_big_hit"] = {k: ab[k] for k in ("all", "enemy in view at the hit") if k in ab}
            Y.add_tally(total, r["tally"])
            rows[r["map"]] = (r["rows"]["sight"], r["rows"]["view"])
            frows.append(np.asarray(r["rows"]["fight"], np.int64).reshape(-1, len(Y.FIGHT_COLS)))
            lives[r["map"]] = r["tally"].get("openings", {}).get("spawn:" + r["map"], [])
            if opp == "nightmare":
                f = np.array(r["final"], np.float64)
                out["score"][r["map"]] = [round(float(f[:, 0].mean()), 1), round(float(f[:, 1].mean()), 1)]
        alls = Y.report(total, zrange=zr)
        for o in alls["predictability"]["maps"].values():
            o["routes"].pop("by_pair", None)
        alls["holds"].pop("top_cells", None)                    # (under the map itself)
        alls["fights"].pop("pairs", None)                       # (two sides at once: too thin on a set of games; the pros' file has them)
        if alls.get("sounds", {}).get("known"):                 # (a sound by distance: the same)
            alls["sounds"]["baseline"] = {"all": alls["sounds"]["baseline"].get("all", {})}
            alls["sounds"]["by_kind"] = {nm_: {"all": tab_["all"]} for nm_, tab_ in alls["sounds"]["by_kind"].items()}
        out[opp] = dict(all=alls, **per)
        out["standing"][opp] = standing(rows)
        out.setdefault("plans_match", {})[opp] = plans_match(lives)
        out.setdefault("lives_rows", {})[opp] = {m: [[int(x) for x in r_] for r_ in v] for m, v in lives.items()}   # (his lives as rows: SPAWN_COLS)
        md = pros["maps"]["all"].get("fights", {}).get("index_model")
        if md and frows:
            out.setdefault("fight_index", {})[opp] = fight_index(np.concatenate(frows), md)
        out["routes"][opp] = routes_same_size(total, maps)
        out["cells"][opp] = {}
        for mp, (sight, view) in rows.items():                  # his own cells with enough sightings, as the pros' table of cells
            sight, view = np.asarray(sight, np.int64).reshape(-1, 15), np.asarray(view, np.int64).reshape(-1, 8)
            if len(sight):
                out["cells"][opp][mp] = PP.cells(sight, view, PP.expected(sight), PP.map_items(mp))
    out["standing"]["pros"] = pros_standing(maps)
    path = a.json or os.path.join(ROOT, "docs", "bobby_yardsticks_{}.json".format(a.tag))
    out2 = dict(tag=out["tag"], policy=out["policy"], fight_index=out.pop("fight_index", {}), plans_match=out.pop("plans_match", {}), lives_rows=out.pop("lives_rows", {}))
    for opp in ("self", "nightmare"):
        if opp in out:
            out2[opp] = {m: {k: v.pop(k) for k in Y.GROUPS2 if k in v} for m, v in out[opp].items()}
    Y.dump_json(out, path, 5)
    Y.dump_json(out2, Y.second_file(path), 5)
    show(merged(path), pros)


if __name__ == "__main__":
    main()

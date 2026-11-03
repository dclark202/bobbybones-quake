"""The map's weights for the targeted item runs (sim/duel_env.py RUN_ITEM_SHARE; owner's go, 2026-10-25: practice for the
items he never picks up), from his own pickups in whole self-play games of a save.

    python tools/run_targets.py measure --map campgrounds --ck <policy.pt> [--matches 6] [--minutes 10] --out <rates.json>
        [--cmd <a run's .cmd: its "set NAME=VALUE" lines are the simulator's environment>]
    python tools/run_targets.py table <rates.json> ... [--floor 0.05] [--out sim/run_targets.json]

measure: the save against itself in whole games (as tools/duel_eval.py's seats: the game's clock, the save's delays), every
seat a network; per item label the pickups a player-minute (a map item counted when it goes down) and the share of his
living frames each weapon is owned. table: per map, for each item his intention can name (MH, RA, YA, YA2, RL, RG, LG; PG
and the rest have no intention), weight = 1 / (rate per item + floor), scaled so the most taken item weighs 1: an item
nobody takes weighs about (rate of the most taken + floor) / floor. YA2 is the map's second yellow armor (the rate per
yellow armor is the label's total over their number).
"""
import argparse
import importlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGETS = ("MH", "RA", "YA", "YA2", "RL", "RG", "LG")


def measure(a):
    if a.cmd:
        for line in open(a.cmd):
            m = re.match(r"^\s*set\s+([A-Z0-9_]+)=(.*)$", line.strip(), re.I)
            if m and m.group(1) != "LEARN" and "%" not in m.group(2):
                os.environ[m.group(1)] = m.group(2).strip()
    os.environ["PRO_START_P"] = "0"
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, HERE)
    import numpy as np
    import brain_data as BD
    import duel_eval as DE
    import test_suite as T_
    spec = BD.env_vars_of(a.ck)
    os.environ.update(spec["env_vars"])
    os.environ.setdefault("ROUTE_CACHE", os.path.join(ROOT, "scratch", "route_cache"))
    E = importlib.import_module(spec["env"])
    mp = a.map
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=a.matches, seed=a.seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, group=2)
    pol, opp = T_.Policy(a.ck, seed=a.seed), T_.Policy(a.ck, seed=a.seed + 1)
    n = env.n
    T_.set_delays(E, env, [(np.arange(0, n), pol.react_ms, pol.acquire_ms)])
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = env.close_p = 0.0
    env.item_run_p = env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = 0.0
    env.round_t[:] = 1e9
    BR_ = bool(getattr(E, "BRAIN_READ", False))
    if BR_:
        env.set_brain_g(np.full(n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
    obs, _, _, info = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    env.script[:] = 0
    ev, od = np.arange(0, n, 2), np.arange(1, n, 2)
    h, h2 = pol.zeros(len(ev)), opp.zeros(len(od))
    sc_ = DE.SeatClock(E, env, ev, od, (600.0, 600.0), left_full=False)
    frames = int(a.minutes * 60 / E.DT)
    labs = [d[4] or d[0] for d in env.item_def]
    picks, own, alive_f, frags = {}, np.zeros(len(E.WEAPONS)), 0, 0
    up0 = env.item_up.copy()
    t0 = time.time()
    for t in range(frames):
        act = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        hev_ = env.head_events() if hasattr(env, "head_events") and (pol.head_due(h).any() or opp.head_due(h2).any()) else None
        xlu_ = env.legs_prep() if getattr(E, "LEGS_IN", False) and (pol.needs_xl or opp.needs_xl) else None
        pz_ = zz_ = None
        if pol.needs_pose:
            import btoken as btoken_
            pz_, zz_ = btoken_.pose_from_env(env, mp)
        al, h = pol.act(obs[ev], h, None if hev_ is None else hev_[ev], xl=None if xlu_ is None else xlu_[ev],
                        **({"pose": pz_[ev], "zmap": zz_[ev]} if pol.needs_pose else {}))
        act[ev, :min(al.shape[1], act.shape[1])] = al[:, :act.shape[1]]
        ao, h2 = opp.act(obs[od], h2, None if hev_ is None else hev_[od], xl=None if xlu_ is None else xlu_[od],
                         **({"pose": pz_[od], "zmap": zz_[od]} if opp.needs_pose else {}))
        act[od, :min(ao.shape[1], act.shape[1])] = ao[:, :act.shape[1]]
        if BR_:
            ans_ = dict(bel=np.zeros((n, 3), np.float32), ok=np.zeros(n, bool), band=np.zeros((n, 4), np.float32), ztop=np.full(n, -1, np.int16))
            for m_, p_, hs_ in ((ev, pol, h), (od, opp, h2)):
                an_ = p_.brain_answer(hs_)
                if an_ is not None:
                    for k_ in ans_:
                        ans_[k_][m_] = an_[k_]
            env.brain_in(ans_)
        sc_.before()
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            xl_ = env.legs_prep()
            lg_ = np.zeros((n, 17), np.float32)
            lg_[ev] = pol.legs_logits(xl_[ev])
            lg_[od] = opp.legs_logits(xl_[od])
            env.legs_lg = lg_
        obs, r, done, info = env.step(act)
        frags += len(info["events"])
        for m, k in zip(*np.nonzero(up0 & ~env.item_up)):
            picks[labs[k]] = picks.get(labs[k], 0) + 1
        up0 = env.item_up.copy()
        al_ = env.hp > 0
        alive_f += int(al_.sum())
        own += env.has[al_].sum(0)
        for m_, p_, hs_ in ((ev, pol, h), (od, opp, h2)):
            dd = np.nonzero(np.asarray(done, bool)[m_])[0]
            if len(dd):
                p_.clear(hs_, dd)
        sc_.after(t, info["events"], (h, h2), (pol, opp))
    pm = n * a.minutes
    res = dict(map=mp, ck=os.path.basename(a.ck), matches=a.matches, minutes=a.minutes, player_minutes=pm, deaths=frags,
               items={l: labs.count(l) for l in sorted(set(labs))},
               picks_per_player_min={k: round(v / pm, 4) for k, v in sorted(picks.items())},
               owned_share={w: round(float(own[i] / max(1, alive_f)), 3) for i, w in enumerate(E.WEAPONS)},
               seconds=round(time.time() - t0))
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res))


def table(a):
    out = {}
    if os.path.exists(a.out):
        out = json.load(open(a.out, encoding="utf-8"))
    for f in a.rates:
        r = json.load(open(f, encoding="utf-8"))
        items, rate = r["items"], r["picks_per_player_min"]
        row = {}
        for lab in TARGETS:
            base = "YA" if lab == "YA2" else lab
            cnt = int(items.get(base, 0))
            if cnt == 0 or (lab == "YA2" and cnt < 2):
                continue
            row[lab] = float(rate.get(base, 0.0)) / cnt
        if not row:
            continue
        w = {k: 1.0 / (v + a.floor) for k, v in row.items()}
        lo = min(w.values())
        out[r["map"]] = {k: round(v / lo, 2) for k, v in sorted(w.items(), key=lambda x: -x[1])}
        out.setdefault("_rates", {})[r["map"]] = {k: round(v, 4) for k, v in row.items()}
    out["_note"] = ("tools/run_targets.py: weight = 1 / (pickups a player-minute of one such item + {}), the most taken item 1; "
                    "_rates: the measured pickups a player-minute per item (ck {}).").format(a.floor, ", ".join(sorted(set(
                        json.load(open(f, encoding="utf-8"))["ck"] for f in a.rates))))
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd_", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--map", required=True)
    m.add_argument("--ck", required=True)
    m.add_argument("--matches", type=int, default=6)
    m.add_argument("--minutes", type=float, default=10.0)
    m.add_argument("--seed", type=int, default=7)
    m.add_argument("--cmd", default=None)
    m.add_argument("--out", required=True)
    t = sub.add_parser("table")
    t.add_argument("rates", nargs="+")
    t.add_argument("--floor", type=float, default=0.05)
    t.add_argument("--out", default=os.path.join(ROOT, "sim", "run_targets.json"))
    a = ap.parse_args()
    measure(a) if a.cmd_ == "measure" else table(a)


if __name__ == "__main__":
    main()

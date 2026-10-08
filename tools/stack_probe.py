"""The scorecard of the seeding experiment (docs/PLAN.md, "seeding his behavior from the pro demos"): a few minutes of
self-play on one map in the simulator with the game's own spawn (machine gun only), counted the way the pro demos were
counted (tools/pro_tables.py), and printed beside the pros' numbers for that map.

    python tools/stack_probe.py --run duel_gru_v12 --map bloodrun [--env duel_env_ffa_v12] [--group 2] [--minutes 4]
    python tools/stack_probe.py --run duel_gru_v12 --map arena1,bloodrun,aerowalk,lostworld --json out.json   (Anaconda Python)

Counted per player: time alive without a big weapon (rockets, rail, lightning), seconds from a spawn to the first one,
health plus armor (under 100, 150 or more), pickups a player-minute, enemy in view and firing with no big weapon and
with two or more, the weapon fired by distance and how often it is the pros' first choice among those he owns, and the
map of where he stands (saved as .npz for tools/position_overlap.py). On arena1 the fight is held in the yard.
"""
import argparse
import importlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import test_suite as T               # noqa: E402

CELL = 32
EDGES = np.arange(0, 1550, 50)


def probe(a, mp, E, pol, pro):
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=a.groups, seed=11, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, **(dict(group=a.group) if a.group != 2 else {}))
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]                                  # the game's spawn
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.arena_len = env.round_len = 180.0
    if getattr(env, "lab", None) is not None:
        env.lab_force = dict(kind=E.NORMAL, arena=3)
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    nin = len(pol.mean)
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    lo, hi = env.lo.copy(), env.hi.copy()
    dims = (np.ceil((hi[:2] - lo[:2]) / CELL).astype(int) + 1)
    heat = np.zeros((dims[1], dims[0]), np.float64)
    big_w = [E.RL, E.RG, E.LG]
    n = env.n
    c = dict(alive=0, bare=0, under100=0, over150=0, big=0.0, vis_bare=0, fire_bare=0, fr_bare=0, vis_armed=0, fire_armed=0, fr_armed=0)
    life = np.zeros(n)                                          # seconds of this life
    got = np.zeros(n, bool)
    first_t, lives = [], 0
    was = np.zeros(n, bool)
    died = np.zeros(n, bool)
    fired = np.zeros((E.NW, len(EDGES)))
    agree = np.zeros(2)
    P = None
    if pro:
        t_ = pro.get(mp) or pro.get("all")
        if not t_["fired_frames"] or sum(t_["fired_frames"]) == 0:
            t_ = pro["all"]
        P = np.array([t_["fired_by_distance"][w] for w in ("rl", "rg", "lg")])      # (3, bins)
    pick0 = {k: env.stats[k] for k in ("pick_wp", "pick_mega", "pick_ra", "pick_ar", "frags", "suicides")}
    steps = int(a.minutes * 60 / E.DT)
    for t in range(steps):
        s = env.state
        alive = env.hp > 0
        cx = np.clip(((s[:, 0] - lo[0]) / CELL).astype(int), 0, dims[0] - 1)
        cy = np.clip(((s[:, 1] - lo[1]) / CELL).astype(int), 0, dims[1] - 1)
        np.add.at(heat, (cy[alive], cx[alive]), 1.0)
        nbig = env.has[:, big_w].sum(1)
        tot = env.hp + env.armor
        new = (alive & ~was) | died                             # (a death and the respawn fall in the same step of the simulator)
        lives += int(new.sum())
        life = np.where(new, 0.0, life + E.DT)
        got &= ~new
        hit = alive & ~got & (nbig > 0)
        first_t += life[hit].tolist()
        got |= hit
        was = alive.copy()
        c["alive"] += int(alive.sum())
        c["bare"] += int((alive & (nbig == 0)).sum())
        c["under100"] += int((alive & (tot < 100)).sum())
        c["over150"] += int((alive & (tot >= 150)).sum())
        c["big"] += float(nbig[alive].sum())
        vis = env.visible & alive
        act, h = pol.act(obs[:, :nin], h)
        fire = (act[:, 5] == 1) & alive
        for nm, m in (("bare", alive & (nbig == 0)), ("armed", alive & (nbig >= 2))):
            c["fr_" + nm] += int(m.sum())
            c["vis_" + nm] += int((vis & m).sum())
            c["fire_" + nm] += int((fire & m).sum())
        d = np.linalg.norm(env.known - s[:, :3], axis=1)
        b = np.clip(np.digitize(d, EDGES) - 1, 0, len(EDGES) - 1)
        m = vis & fire
        np.add.at(fired, (env.weapon[m], b[m]), 1)
        if P is not None and m.any():                           # is it the pros' first choice among the big weapons he owns?
            ok = env.has[m][:, big_w] & (env.ammo[m][:, big_w] > 0)
            pr = np.where(ok, P[:, b[m]].T, -1.0)
            has_any = ok.any(1)
            best = pr.max(1)
            mine = np.array([big_w.index(w) if w in big_w else -1 for w in env.weapon[m]])
            p_mine = np.where(mine >= 0, pr[np.arange(len(mine)), np.maximum(mine, 0)], -1.0)
            agree[0] += int((has_any & (p_mine >= best - 0.10)).sum())
            agree[1] += int(has_any.sum())
        obs, r, done, info = env.step(act)
        h[done] = 0.0
        died = np.zeros(n, bool)
        for e_ in info["events"]:
            died[int(e_["victim"])] = True
    pm = a.groups * a.group * a.minutes
    al = max(1, c["alive"])
    ft = np.array(first_t) if first_t else np.array([np.nan])
    out = dict(map=mp, player_minutes=round(pm, 1),
               time_bare=round(c["bare"] / al, 3), big_weapons_held=round(c["big"] / al, 2),
               first_weapon_s=[round(float(x), 1) for x in np.nanpercentile(ft, (25, 50, 75))],
               lives_with_a_weapon=round(len(first_t) / max(1, lives), 3),
               stack_under_100=round(c["under100"] / al, 3), stack_150_up=round(c["over150"] / al, 3),
               pickups_per_player_min={k[5:]: round((env.stats[k] - pick0[k]) / pm, 2) for k in ("pick_wp", "pick_mega", "pick_ra", "pick_ar")},
               frags_per_player_min=round((env.stats["frags"] - pick0["frags"]) / pm, 2),
               own_deaths_per_player_min=round((env.stats["suicides"] - pick0["suicides"]) / pm, 2),
               bare=dict(in_view=round(c["vis_bare"] / max(1, c["fr_bare"]), 3), firing=round(c["fire_bare"] / max(1, c["fr_bare"]), 3)),
               two_or_more=dict(in_view=round(c["vis_armed"] / max(1, c["fr_armed"]), 3), firing=round(c["fire_armed"] / max(1, c["fr_armed"]), 3)),
               fired_share={E.WEAPONS[k]: round(float(fired[k].sum() / max(1.0, fired.sum())), 3) for k in range(E.NW) if fired[k].sum() > 0},
               pro_weapon_agreement=round(float(agree[0] / max(1.0, agree[1])), 3) if agree[1] else None)
    folder = os.path.join(ROOT, "videos", "{}_{:04d}".format(a.run, int(pol.minutes)))
    os.makedirs(folder, exist_ok=True)
    np.savez(os.path.join(folder, "probe_heat_{}.npz".format(mp)), heat=heat, lo=lo[:2], cell=CELL)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--group", type=int, default=2)
    ap.add_argument("--groups", type=int, default=8, help="groups played at once")
    ap.add_argument("--map", default="arena1,bloodrun,aerowalk,lostworld")
    ap.add_argument("--minutes", type=float, default=4.0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=7)
    pj = os.path.join(ROOT, "docs", "pro_tables.json")
    pro = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else None
    res = {}
    for mp in a.map.split(","):                                 # one world per process: the same player count on every map
        res[mp] = probe(a, mp, E, pol, pro)
        o = res[mp]
        p = (pro or {}).get(mp)
        ps = p["spawn"] if p else None
        print("{} ({} at {} min, {} player-minutes, groups of {}):".format(mp, a.run, int(pol.minutes), o["player_minutes"], a.group))
        print("  time without a big weapon   {:5.0%}   {}".format(o["time_bare"], "pros {:.0%}".format(ps["time_without_one"]) if ps else ""))
        print("  first big weapon after      {} s (quartiles), in {:.0%} of lives   {}".format(
            " / ".join(str(x) for x in o["first_weapon_s"]), o["lives_with_a_weapon"],
            "pros {} s, {:.0%}".format(" / ".join(str(x) for x in ps["seconds"][:3]), ps["got_a_big_weapon"]) if ps else ""))
        st = p["stack_time"] if p else None
        print("  health + armor under 100    {:5.0%}, 150 or more {:.0%}   {}".format(
            o["stack_under_100"], o["stack_150_up"],
            "pros {:.0%}, {:.0%}".format(st["0-49"] + st["50-99"], 1 - st["0-49"] - st["50-99"] - st["100-149"]) if st else ""))
        print("  pickups a player-minute     weapons {wp}, mega {mega}, red {ra}, other armor {ar}".format(**o["pickups_per_player_min"]))
        print("  bare: in view {:.0%}, firing {:.0%}; two or more: in view {:.0%}, firing {:.0%}".format(
            o["bare"]["in_view"], o["bare"]["firing"], o["two_or_more"]["in_view"], o["two_or_more"]["firing"]))
        print("  fired: {}; the pros' choice of weapon for the distance in {} of the frames he had one".format(
            ", ".join("{} {:.0%}".format(k, v) for k, v in sorted(o["fired_share"].items(), key=lambda kv: -kv[1])),
            "{:.0%}".format(o["pro_weapon_agreement"]) if o["pro_weapon_agreement"] is not None else "-"))
        print("  frags {} and own deaths {} a player-minute".format(o["frags_per_player_min"], o["own_deaths_per_player_min"]), flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(run=a.run, minutes=int(pol.minutes), env=a.env, group=a.group, maps=res), f, indent=1)


if __name__ == "__main__":
    main()

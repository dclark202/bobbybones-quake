"""Ten-minute duels in the simulator against a fixed opponent, many at once: the check with error bars that the
real-server games cannot give (docs/RESULTS.md, audit of 2026-10-08; owner: "play 100 games; 10 minutes is standard").

    python tools/duel_eval.py --run duel_gru_v12 --inputs docs/INPUTS_v12.csv --opp nightmare --map bloodrun,aerowalk
    python tools/duel_eval.py --run duel_gru_v13 --opp policy:data/sim_runs/duel_gru_v12/policy_end_v12.pt --opp-inputs docs/INPUTS_v12.csv
    (Anaconda Python; --games 100 --minutes 10 --procs 16 by default; --set NAME=VALUE passes a simulator setting)

Opponents: "nightmare" = the stand-in for the game's Nightmare bot (the scripted item runner with the persona of that
name in sim/duel_env.py; for checks only, never a training opponent), "runner" = the plain item runner, or another
network ("policy:<file>"). Rules as on the server: the game's spawn (machine gun), spawn points away from the enemy,
one game without restarts; his clock, score and memory start over every --round seconds as in training. A network
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


def names(path):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(path, encoding="utf-8"))]


def play(job):
    (envmod, envvars, mp, games, minutes, seed, pol, idx, opp_kind, opp_pol, opp_idx, round_secs) = job
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    env.react_frames = round(pol.react_ms / 25)
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    scripted = opp_kind in ("nightmare", "runner")
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
        env.sc_persona[od] = E.NIGHTMARE if opp_kind == "nightmare" else 0
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
                                  "standing", "stuck", "own_deaths", "fire_vis", "both", "lower", "higher", "vis_lower", "vis_higher", "empty", "empty_fire")}
    still = np.zeros(n)                                         # seconds he has been standing (under 50 units a second)
    life, got, was = np.zeros(n), np.zeros(n, bool), np.zeros(n, bool)
    first = [[], []]
    hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), env.has[:, big].copy()
    frames = int(minutes * 60 / E.DT)
    wrap = max(1, int(round_secs / E.DT))
    # the simulator's own counters (they count the learner's side): damage, shots, hits and frags by weapon, the weapon in
    # hand by distance, his speed toward an enemy in view by strength, how well he knows where the enemy is, dropped weapons
    SK = [k for k in ["dmg_h", "dmg_from_script", "w_dist", "close_v", "close_n", "know", "know_frames", "drops", "pick_drop",
                      "pick_drop_new", "self_dmg", "fall_dmg"]
          + [w + x for w in E.WEAPONS for x in ("_frags", "_shots", "_hits")] if k in env.stats]
    st0 = {k: np.array(env.stats[k], np.float64).copy() for k in SK}
    side = np.arange(n) % 2
    for t in range(frames):
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        al, h = pol.act(obs[ev][:, idx], h)
        a[ev, :al.shape[1]] = al
        if opp_pol is not None:
            ao, h2 = opp_pol.act(obs[od][:, opp_idx], h2)
            a[od, :ao.shape[1]] = ao
        obs, r, done, info = env.step(a)
        c["restarts"][0] += int(done.any())
        died = np.zeros(n, bool)                                # (a death and the respawn fall in the same step here)
        for e in info["events"]:
            v, k = int(e["victim"]), int(e["killer"])
            died[v] = True
            if k >= 0 and k != v:
                score[k] += 1
                kills[k] += 1
            else:
                score[v] -= 1                                   # his own hand or the map: a point off, as in the game
                c["own_deaths"][v % 2] += 1
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
            c["standing"][s_] += (alive & (spd < 50.0))[m].sum()
            c["stuck"][s_] += (still > 3.0)[m].sum()
            c["wp"][s_] += gain_w[m].sum()
            c["mega"][s_] += (dh >= 60)[m].sum()
            c["red"][s_] += (da >= 75)[m].sum()
            c["yellow"][s_] += ((da >= 40) & (da < 75))[m].sum()
            c["lives"][s_] += new[m].sum()
        was = alive.copy()
        hp0, ar0, has0 = env.hp.copy(), env.armor.copy(), env.has[:, big].copy()
        if (t + 1) % wrap == 0:                                 # his clock, score and memory start over, as on the server
            env.round_t[:] = 0.0
            env.frags_r[:] = 0
            h[:] = 0.0
            if opp_pol is not None:
                h2[:] = 0.0
    return dict(score=score.reshape(-1, 2).tolist(), kills=kills.reshape(-1, 2).tolist(), c={k: v.tolist() for k, v in c.items()},
                first=first, minutes=minutes, games=games, weapons=list(E.WEAPONS),
                st={k: (np.array(env.stats[k], np.float64) - st0[k]).tolist() for k in SK})


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
    ap.add_argument("--round", type=float, default=0.0, help="his clock and memory start over every this many seconds (default: 180 on arena1, 120 elsewhere, as in training)")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: a simulator setting (environment variable) for these games")
    ap.add_argument("--seed", type=int, default=100)
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
    out = {}
    for mp in a.map.split(","):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        jobs = [(a.env, envvars, mp, g, a.minutes, a.seed + 17 * k, pol, idx, kind, opp_pol, opp_idx,
                 a.round or (180.0 if mp == "arena1" else 120.0)) for k, g in enumerate(per) if g > 0]
        with mp_.Pool(len(jobs)) as pool:
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
        for s_, who in ((0, "he"), (1, "opponent")):
            al = max(1.0, c["alive"][s_])
            row[who] = dict(score=round(float(sc[:, s_].mean()), 2), kills=round(float(kl[:, s_].mean()), 2),
                            time_bare=round(float(c["bare"][s_] / al), 3), first_weapon_s=round(float(np.nanmedian(first[s_])), 1),
                            stack_150_up=round(float(c["over150"][s_] / al), 3), in_view=round(float(c["vis"][s_] / al), 3),
                            firing=round(float(c["fire"][s_] / al), 3), speed=int(c["speed"][s_] / al),
                            firing_in_view=round(float(c["fire_vis"][s_] / max(1.0, c["vis"][s_])), 3),
                            standing=round(float(c["standing"][s_] / al), 3), standing_over_3s=round(float(c["stuck"][s_] / al), 3),
                            own_deaths=round(float(c["own_deaths"][s_] / G), 2),
                            empty_in_hand=round(float(c["empty"][s_] / al), 4), firing_empty=round(float(c["empty_fire"][s_] / max(1.0, c["fire"][s_])), 4),   # of his time alive; of his firing
                            lower=round(float(c["lower"][s_] / max(1.0, c["both"][s_])), 3), higher=round(float(c["higher"][s_] / max(1.0, c["both"][s_])), 3),   # of the time both live: lower or higher by 48 units or more
                            lower_in_view=round(float(c["vis_lower"][s_] / max(1.0, c["vis"][s_])), 3), higher_in_view=round(float(c["vis_higher"][s_] / max(1.0, c["vis"][s_])), 3),
                            weapons_per_min=round(float(c["wp"][s_] / pm), 2),
                            mega_share=round(float(c["mega"][s_] / (pm * 60 / 35.0)), 3), red_share=round(float(c["red"][s_] / (pm * 60 / 25.0)), 3),
                            yellow_per_min=round(float(c["yellow"][s_] / pm), 2), lives_per_min=round(float(c["lives"][s_] / pm), 2))
        st = {k: np.sum([np.array(r["st"][k]) for r in res], 0) for k in res[0].get("st", {})}
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
        out[mp] = dict(games=G, minutes=a.minutes, frag_share=round(share(kl), 3), frag_share_95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                       won=int((sc[:, 0] > sc[:, 1]).sum()), drawn=int((sc[:, 0] == sc[:, 1]).sum()), lost=int((sc[:, 0] < sc[:, 1]).sum()),
                       restarts=int(c["restarts"][0]), **row)
        o = out[mp]
        print("{} | {} against {} | {} games of {:g} min | score {:.1f} : {:.1f} | his share of the frags {:.0%} ({:.0%} to {:.0%}) | won {} drawn {} lost {}".format(
            mp, a.run or os.path.basename(path), a.opp, G, a.minutes, o["he"]["score"], o["opponent"]["score"], o["frag_share"],
            o["frag_share_95"][0], o["frag_share_95"][1], o["won"], o["drawn"], o["lost"]))
        for who in ("he", "opponent"):
            w = o[who]
            print("    {:9s} bare {:.0%} | first weapon {} s | 150+ {:.0%} | weapons {}/min | mega {:.0%}, red {:.0%} of spawns | yellow {}/min | in view {:.0%} | firing {:.0%} ({:.0%} of the time in view) | speed {}, standing {:.0%} (over 3 s: {:.0%}) | lives {}/min, own deaths {} a game".format(
                who, w["time_bare"], w["first_weapon_s"], w["stack_150_up"], w["weapons_per_min"], w["mega_share"], w["red_share"],
                w["yellow_per_min"], w["in_view"], w["firing"], w["firing_in_view"], w["speed"], w["standing"], w["standing_over_3s"], w["lives_per_min"], w["own_deaths"]), flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(run=a.run, policy=path, opp=a.opp, env=a.env, set=envvars, maps=out), f, indent=1)


if __name__ == "__main__":
    main()

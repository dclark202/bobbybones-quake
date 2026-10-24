"""Whole self-play games recorded frame by frame for the win-pay tools (tools/win_table.py, pay_ledger.py, pay_align.py,
value_ready.py; the owner, 2026-10-23: "Pay by win rate is the approach, that's the goal of v0.4.x").

    python tools/winpay_games.py --policy <copy of policy.pt> --run-cmd scratch/run_duel_gru_v0_4_1.cmd
        --run-dir data/sim_runs/duel_gru_v0_4_1 --map bloodrun --games 8 --seed 1 --out <dir>/games_bloodrun_1.npz
    (Anaconda Python, on the CPU; one process)

The simulator as the run trains it: every `set NAME=VALUE` of the run's .cmd, its live_settings.env and the pays in force
of its live_applied.json (read only), the trainer's own settings for the simulator (item pay by points 0, the way's pay
1.0, the item loss 0.5, damage 0.0055 / 0.75, ...), then the measurement's own: every round a whole ten-minute game from
0:00 with overtime (GAME_P=1, no late rounds, pro starts, jump or item runs, no staggered starts), PAY_SPLIT=1 and
WIN_SHADOW=1 (record only: the pay is the run's). Both seats of every match are the network (self-play, as the first half
of a trainer's matches), driven as tools/duel_eval.py drives it (the brain and its token, the legs' branch, the readers).
Every game that ends before the last match's first game ends is kept (a match goes on to a second game meanwhile).

Written (npz, per frame f and player i of the kept games' frames): pay [F, n, terms] (sim PAY_TERMS), rew [F, n] (the
frame's pay), rlong, wshadow (what WIN_PAY would pay), flat (the flat frag pay of whole games), v, v2 [F, n, 2] (the
network's value outputs: v the main one at the run's gamma, v2 the item and stack part at the fight's gamma and at
--long-gamma), frags (the game's score), hp, armor, big [F, n, 3] (rl, lg, rg held), vis, tick [F, M] (the game's frame,
-1 when no kept game), gid [F, M] (the kept game's number, -1 none); games: per kept game (match, first frame, last frame,
regulation score of each seat, final score, overtime periods); events: (frame, victim, killer).
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

SKIP = {"GPU_MEM_FRACTION", "LEARN", "BTOK_START", "PYTHONFAULTHANDLER"}
TRAINER_LIVE = {"DMG_TAKEN_W", "DMG_REWARD", "INFO_PAY", "TRACK_W", "TRACK_TRUNK", "TRACK_Z_W", "BTOK_GATE_CAP", "BTOK_GATE_OPEN",
                "BELIEF_LR", "AHEAD_W", "RJ_TEACH_W", "FADE_CAP", "FADE_OPEN"}
MEASURE = dict(GAME_P="1", LATE_P="0", PRO_START_P="0", MID_START_P="0", SPAWN_START_P="0", RAIL_START_P="0", JUMP_RUN_P="0",
               RJ_RUN_P="0", ITEM_RUN_P="0", STAGGER_START="0", OVERTIME="1", PAY_SPLIT="1", WIN_SHADOW="1", CONTEST_P="0")


def run_env(run_cmd, run_dir):
    """the run's simulator settings: the .cmd's `set` lines, live_settings.env, live_applied.json's pays in force -> (env, trainer)"""
    env, tr = {}, {}
    for line in open(run_cmd, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.lower().startswith("set ") and "=" in s:
            k, v = s[4:].split("=", 1)
            k = k.strip()
            if k and k not in SKIP and not k.startswith("\"") and "%" not in v:
                env[k] = v.strip()
    ls_ = os.path.join(run_dir, "live_settings.env")
    if os.path.exists(ls_):
        for line in open(ls_, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip()
    la_ = os.path.join(run_dir, "live_applied.json")
    if os.path.exists(la_):
        inf = json.load(open(la_, encoding="utf-8")).get("in_force", {})
        for k, v in inf.items():
            if k in TRAINER_LIVE:
                tr[k] = float(v)
                continue
            if isinstance(v, dict):
                v = ",".join("{}:{}".format(a, b) for a, b in v.items())
            elif isinstance(v, (list, tuple)):
                v = ",".join(str(x) for x in v)
            elif isinstance(v, bool):
                v = "1" if v else "0"
            env[k] = str(v)
    return env, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--games", type=int, default=8, help="matches played at once (each seat the network)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-minutes", type=float, default=40.0, help="game minutes at most (a stop for a match in a long overtime)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    envv, trv = run_env(a.run_cmd, a.run_dir)
    envv.update(MEASURE)
    envv.update(dict(x.split("=", 1) for x in a.set))
    os.environ.update(envv)
    import importlib
    import test_suite as T
    E = importlib.import_module("duel_env_ffa")
    assert E.PAY_SPLIT and E.WIN_SHADOW and E.GAME_ON and E.OVERTIME and not E.MOMENTS and not E.WIN_PAY
    import torch
    ck = torch.load(a.policy, weights_only=False, map_location="cpu")
    sd = ck["model"]
    vw, vb = sd["v.weight"].numpy(), sd["v.bias"].numpy()
    v2w, v2b = sd["v2.weight"].numpy(), sd["v2.bias"].numpy()
    del ck, sd
    pol = T.Policy(a.policy, seed=a.seed)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.games, seed=a.seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    n, M = env.n, env.M
    assert env.observe().shape[1] == len(pol.mean), "inputs: the simulator {} the network {}".format(env.observe().shape[1], len(pol.mean))
    T.set_delays(E, env, [(np.arange(n), pol.react_ms, pol.acquire_ms)])
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5         # (the run's --item-reward 0 --intent-seek 1.0 --item-loss 0.5)
    env.item_seek = float(os.environ.get("ITEM_SEEK", "0"))
    env.stack_p = env.near_item_p = 0.0
    env.drill_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w = float(trv.get("DMG_TAKEN_W", 0.75))
    env.dmg_reward = float(trv.get("DMG_REWARD", 0.0055))
    env.close_p, env.round_len = 0.0, 120.0                                 # (the curriculum's message at --close-floor 0)
    if hasattr(env, "count_even"):
        env.count_even = True
    if hasattr(env, "legs_keep_who"):
        env.legs_keep_who = np.ones(n, bool)                                  # (every seat is his)
    env.round_t[:] = 1e9
    env._teach_update()
    obs, _, done, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    pol.clear(h, done)
    K = len(E.PAY_TERMS)
    L = {k: [] for k in ("pay", "rew", "rlong", "wshadow", "flat", "v", "v2", "frags", "hp", "armor", "big", "vis", "tick", "gnum")}
    events, games = [], []
    gnum = np.full(M, -1, np.int64)          # the running game's number per match (counted from its start in this job)
    g_start = np.zeros(M, np.int64)
    reg = {}
    first_done = np.zeros(M, bool)
    big = [E.RL, E.LG, E.RG]
    ng = 0
    t0 = time.time()
    f = 0
    max_f = int(a.max_minutes * 60 / E.DT)
    for m in range(M):                                       # the games begun by the first step
        if env.game[m] > 0 and env.g_tick[m] == 0:
            gnum[m], g_start[m] = ng, 0
            ng += 1
    while True:
        hev_ = env.head_events() if (hasattr(env, "head_events") and pol.head_due(h).any()) else None
        xlu_ = env.legs_prep() if (getattr(E, "LEGS_IN", False) and pol.needs_xl) else None
        pz_ = zz_ = None
        if pol.needs_pose:
            import btoken as btoken_
            pz_, zz_ = btoken_.pose_from_env(env, a.map)
        act, h = pol.act(obs, h, hev_, xl=xlu_, **({"pose": pz_, "zmap": zz_} if pol.needs_pose else {}))
        zo = pol.last_zo
        v = (zo @ vw.T + vb)[:, 0]
        v2 = zo @ v2w.T + v2b
        if getattr(E, "BRAIN_READ", False):
            an_ = pol.brain_answer(h)
            if an_ is not None:
                env.brain_in(an_)
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        tick_before = env.g_tick.copy()
        game_before = env.game.copy()
        gnum_before = gnum.copy()
        fr_after = env.frags_r.astype(np.int64).copy()
        a_ = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a_[:, :min(act.shape[1], a_.shape[1])] = act[:, :a_.shape[1]]
        obs, rew, done, info = env.step(a_)
        for e in info["events"]:                             # the game's score after this frame's frags (before a new game's reset)
            vv_, kk_ = int(e["victim"]), int(e["killer"])
            events.append((f, vv_, kk_))
            if kk_ >= 0 and kk_ != vv_:
                fr_after[kk_] += 1
            else:
                fr_after[vv_] -= 1
        L["pay"].append(info["pay_terms"].astype(np.float32))
        L["rew"].append(rew.astype(np.float32))
        L["rlong"].append(np.asarray(info["r_long"], np.float32))
        L["wshadow"].append(np.asarray(info["win_shadow"], np.float32))
        L["flat"].append(np.asarray(info["flat_frag"], np.float32))
        L["v"].append(v.astype(np.float32))
        L["v2"].append(v2.astype(np.float32))
        L["frags"].append(fr_after.astype(np.int16))
        L["hp"].append(np.clip(env.hp, -999, 999).astype(np.int16))
        L["armor"].append(np.clip(env.armor, 0, 999).astype(np.int16))
        L["big"].append(env.has[:, big].copy())
        L["vis"].append(np.asarray(env.visible, bool)[:n].copy())
        L["tick"].append(np.where(game_before > 0, tick_before + 1, -1).astype(np.int32))
        L["gnum"].append(gnum_before.astype(np.int32))
        for m in range(M):
            q = [2 * m, 2 * m + 1]
            if game_before[m] > 0 and tick_before[m] + 1 == E.GAME_FRAMES and gnum[m] >= 0:
                reg[int(gnum[m])] = [int(x) for x in fr_after[q]]
            if game_before[m] > 0 and env.g_tick[m] <= tick_before[m]:          # its game ended on this frame (a new one began)
                if gnum[m] >= 0:
                    games.append(dict(gid=int(gnum[m]), match=m, start=int(g_start[m]), end=f, ticks=int(tick_before[m] + 1),
                                      reg=reg.get(int(gnum[m])), final=[int(x) for x in fr_after[q]],
                                      ot=int(max(0, tick_before[m] + 1 - E.GAME_FRAMES + E.OT_FRAMES - 1) // E.OT_FRAMES)))
                    first_done[m] = True
                gnum[m] = -1
            if env.game[m] > 0 and env.g_tick[m] == 0:                            # a game begins with the next frame
                gnum[m], g_start[m] = ng, f + 1
                ng += 1
        f += 1
        if f % 2000 == 0:
            print("frame {} ({:.0f} s) games done {} of {} matches, {:.1f} ms a frame".format(
                f, time.time() - t0, len(games), M, 1000 * (time.time() - t0) / f), flush=True)
        if first_done.all() or f >= max_f:
            break
    out = {k: np.stack(v_) for k, v_ in L.items()}
    out["events"] = np.array(events, np.int32).reshape(-1, 3)
    out["terms"] = np.array(E.PAY_TERMS)
    out["games"] = np.array(json.dumps(games))
    out["meta"] = np.array(json.dumps(dict(map=a.map, policy=a.policy, seed=a.seed, n=n, M=M, dt=E.DT, game_frames=E.GAME_FRAMES,
                                            ot_frames=E.OT_FRAMES, env=envv, trainer=trv, frames=f, secs=time.time() - t0)))
    np.savez_compressed(a.out, **out)
    print("wrote {}: {} frames, {} games, {:.0f} s".format(a.out, f, len(games), time.time() - t0), flush=True)


def iter_games(paths):
    """the kept games of these files, one dict a game: map, the two seats' frames (axis 1: seat 0, seat 1) of pay [F, 2,
    terms], rew, rlong, wshadow, flat, v, v2 [F, 2, 2], frags, hp, armor, big, vis; tick [F] (the game's frame); terms;
    reg and final (each seat's score at ten minutes and at the end), res_ten / res_ot (seat 0's result: 1, 0.5, 0), ot
    (periods), dt, scale (WIN_PAY's: from the pros' table)"""
    import glob as glob_
    files = sorted({x for p in paths for x in glob_.glob(p)})
    wc_ = json.load(open(os.path.join(ROOT, "sim", "win_chance.json"), encoding="utf-8"))
    scale = 1.0 / (float(wc_["p"][-1][len(wc_["diffs"]) // 2 + 1]) - 0.5)
    for p in files:
        d = np.load(p, allow_pickle=False)
        meta = json.loads(str(d["meta"]))
        gs = json.loads(str(d["games"]))
        terms = [str(x) for x in d["terms"]]
        A = {k: d[k] for k in ("pay", "rew", "rlong", "wshadow", "flat", "v", "v2", "frags", "hp", "armor", "big", "vis", "tick", "gnum")}
        for g in gs:
            m = g["match"]
            rows = np.nonzero(A["gnum"][:, m] == g["gid"])[0]
            if not len(rows) or g.get("reg") is None:
                continue
            q = [2 * m, 2 * m + 1]
            out = {k: A[k][rows][:, q] for k in ("pay", "rew", "rlong", "wshadow", "flat", "v", "v2", "frags", "hp", "armor", "big", "vis")}
            out["tick"] = A["tick"][rows, m]
            r0, f0 = g["reg"], g["final"]
            out.update(map=meta["map"], file=os.path.basename(p), match=m, gid=g["gid"], terms=terms, reg=r0, final=f0, ot=g.get("ot", 0),
                       res_ten=1.0 if r0[0] > r0[1] else 0.0 if r0[0] < r0[1] else 0.5,
                       res_ot=1.0 if f0[0] > f0[1] else 0.0 if f0[0] < f0[1] else 0.5, dt=float(meta["dt"]), scale=scale,
                       game_frames=int(meta["game_frames"]), ot_frames=int(meta["ot_frames"]))
            yield out


if __name__ == "__main__":
    main()

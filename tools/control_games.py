"""Whole self-play games of a checkpoint recorded for the "in control" probe (v0.4.3, B-280; docs/v0.4.3/RUN_v0.4.3.md):
the simulator's hindsight label (CONTROL_TRUTH=1: his share of the next two mega / red armor spawns, given CONTROL_H s late)
beside what is in his head (the brain's state, the hands' memory) on the same frames. tools/control_probe.py fits a probe.

    python tools/control_games.py --policy <copy of policy.pt> --run-cmd <run .cmd> --run-dir <run folder>
        --map bloodrun --games 8 --seed 1 --out <dir>/ctl_bloodrun_1.npz
    (Anaconda Python, on the CPU; one process)

The simulator and the driving exactly as tools/winpay_games.py (the run's .cmd, live_settings.env, live_applied.json; whole
ten-minute games from 0:00 with overtime; both seats the network), with CONTROL_TRUTH=1 and TRACK_TRUTH=1 (labels only).
The play goes on CONTROL_H seconds after the last match's first game has ended, so that every label of the kept games is
given. Written (npz): per frame f, seat i: tick [F, M], gnum [F, M] (as winpay_games), frags, hp, armor [F, n], aux [F, n,
len(cols)] (the info["aux"] columns named in cols); every --every frames (rows sf): bel [S, n, 256] (the brain's state, half
precision), mem [S, n, 512] (the hands' GRU memory), ahead [S, n, d] (the brain's readout ahead on that state, if the
network has it); games (as winpay_games), meta.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

COLS = ("mega_s", "red_s", "mega_take", "red_take", "died", "trk_on", "es_stack", "en_in_view", "en_band",
        "race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra", "ctl_lab", "ctl_one", "ctl_age", "ctl_mh", "ctl_ra")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--games", type=int, default=8, help="matches played at once (each seat the network)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--every", type=int, default=16, help="frames between the rows of his head's state")
    ap.add_argument("--max-minutes", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    import winpay_games as WG
    envv, trv = WG.run_env(a.run_cmd, a.run_dir)
    envv.update(WG.MEASURE)
    envv.update(CONTROL_TRUTH="1", TRACK_TRUTH="1")
    envv.update(dict(x.split("=", 1) for x in a.set))
    os.environ.update(envv)
    import importlib
    import test_suite as T
    import btoken as btoken_
    E = importlib.import_module("duel_env_ffa")
    assert E.CONTROL_TRUTH and E.GAME_ON and E.OVERTIME and not E.MOMENTS and not E.WIN_PAY
    import torch
    ck = torch.load(a.policy, weights_only=False, map_location="cpu")
    sd = ck["model"]
    AH = None
    if "ahead.0.weight" in sd:
        AH = tuple(sd["ahead.{}.{}".format(i, w)].float().numpy() for i in (0, 2) for w in ("weight", "bias"))
    ahL = ck.get("ahead")
    del ck, sd
    pol = T.Policy(a.policy, seed=a.seed)
    assert pol.brain_on, "the probe reads the brain: a network whose brain is stepped"
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.games, seed=a.seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None)
    n, M = env.n, env.M
    T.set_delays(E, env, [(np.arange(n), pol.react_ms, pol.acquire_ms)])
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.item_seek = float(os.environ.get("ITEM_SEEK", "0"))
    env.stack_p = env.near_item_p = 0.0
    env.drill_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w = float(trv.get("DMG_TAKEN_W", 0.75))
    env.dmg_reward = float(trv.get("DMG_REWARD", 0.0055))
    env.close_p, env.round_len = 0.0, 120.0
    if hasattr(env, "count_even"):
        env.count_even = True
    if hasattr(env, "legs_keep_who"):
        env.legs_keep_who = np.ones(n, bool)
    env.round_t[:] = 1e9
    env._teach_update()
    obs, _, done, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    h = pol.zeros(n)
    pol.clear(h, done)
    cols_ = [c for c in COLS if c in E.AUX_COLS]
    CI = [E.AUX_COLS.index(c) for c in cols_]
    L = {k: [] for k in ("frags", "hp", "armor", "aux", "tick", "gnum")}
    S = {k: [] for k in ("bel", "mem", "ahead", "sf")}
    events, games = [], []
    gnum = np.full(M, -1, np.int64)
    g_start = np.zeros(M, np.int64)
    reg = {}
    first_done = np.zeros(M, bool)
    ng = 0
    t0 = time.time()
    f = 0
    tail = -1
    max_f = int(a.max_minutes * 60 / E.DT)
    for m in range(M):
        if env.game[m] > 0 and env.g_tick[m] == 0:
            gnum[m], g_start[m] = ng, 0
            ng += 1
    while True:
        hev_ = env.head_events() if (hasattr(env, "head_events") and pol.head_due(h).any()) else None
        xlu_ = env.legs_prep() if (getattr(E, "LEGS_IN", False) and pol.needs_xl) else None
        pz_, zz_ = btoken_.pose_from_env(env, a.map)
        act, h = pol.act(obs, h, hev_, xl=xlu_, pose=pz_, zmap=zz_)
        if getattr(E, "BRAIN_READ", False):
            an_ = pol.brain_answer(h)
            if an_ is not None:
                env.brain_in(an_)
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        if f % a.every == 0:                                 # his head after this frame's act (the state the frame's choice came from)
            bs_ = h[:, pol.brain_at:pol.brain_at + pol.brainP["H"]].astype(np.float32)
            S["sf"].append(f)
            S["bel"].append(bs_.astype(np.float16))
            S["mem"].append(h[:, :pol.H].astype(np.float16))
            if AH is not None:
                S["ahead"].append(T_mlp(AH, bs_).astype(np.float16))
        tick_before = env.g_tick.copy()
        game_before = env.game.copy()
        gnum_before = gnum.copy()
        fr_after = env.frags_r.astype(np.int64).copy()
        a_ = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        a_[:, :min(act.shape[1], a_.shape[1])] = act[:, :a_.shape[1]]
        obs, rew, done, info = env.step(a_)
        if np.asarray(done).any():                           # (as the trainer: memory, brain and its answer reset at a round's end)
            pol.clear(h, np.nonzero(done)[0])
        for e in info["events"]:
            vv_, kk_ = int(e["victim"]), int(e["killer"])
            events.append((f, vv_, kk_))
            if kk_ >= 0 and kk_ != vv_:
                fr_after[kk_] += 1
            else:
                fr_after[vv_] -= 1
        L["frags"].append(fr_after.astype(np.int16))
        L["hp"].append(np.clip(env.hp, -999, 999).astype(np.int16))
        L["armor"].append(np.clip(env.armor, 0, 999).astype(np.int16))
        L["aux"].append(np.asarray(info["aux"], np.float32)[:, CI])
        L["tick"].append(np.where(game_before > 0, tick_before + 1, -1).astype(np.int32))
        L["gnum"].append(gnum_before.astype(np.int32))
        for m in range(M):
            q = [2 * m, 2 * m + 1]
            if game_before[m] > 0 and tick_before[m] + 1 == E.GAME_FRAMES and gnum[m] >= 0:
                reg[int(gnum[m])] = [int(x) for x in fr_after[q]]
            if game_before[m] > 0 and env.g_tick[m] <= tick_before[m]:
                if gnum[m] >= 0 and not first_done[m]:
                    games.append(dict(gid=int(gnum[m]), match=m, start=int(g_start[m]), end=f, ticks=int(tick_before[m] + 1),
                                      reg=reg.get(int(gnum[m])), final=[int(x) for x in fr_after[q]],
                                      ot=int(max(0, tick_before[m] + 1 - E.GAME_FRAMES + E.OT_FRAMES - 1) // E.OT_FRAMES)))
                    first_done[m] = True
                gnum[m] = -1
            if env.game[m] > 0 and env.g_tick[m] == 0:
                gnum[m], g_start[m] = ng, f + 1
                ng += 1
        f += 1
        if f % 2000 == 0:
            print("frame {} ({:.0f} s) games done {} of {} matches, {:.1f} ms a frame".format(
                f, time.time() - t0, len(games), M, 1000 * (time.time() - t0) / f), flush=True)
        if tail < 0 and (first_done.all() or f >= max_f):
            tail = f + E.CONTROL_D + 1                       # the labels of the last frames come CONTROL_H s later
        if tail >= 0 and f >= tail:
            break
    out = {k: np.stack(v_) for k, v_ in L.items()}
    for k, v_ in S.items():
        if v_:
            out[k] = np.stack(v_)
    out["events"] = np.array(events, np.int32).reshape(-1, 3)
    out["cols"] = np.array(cols_)
    out["games"] = np.array(json.dumps(games))
    out["meta"] = np.array(json.dumps(dict(map=a.map, policy=a.policy, seed=a.seed, n=n, M=M, dt=E.DT, game_frames=E.GAME_FRAMES,
                                            ot_frames=E.OT_FRAMES, control_d=E.CONTROL_D, every=a.every, ahead=ahL,
                                            env=envv, trainer=trv, frames=f, secs=time.time() - t0), default=str))
    np.savez_compressed(a.out, **out)
    print("wrote {}: {} frames, {} games, {:.0f} s".format(a.out, f, len(games), time.time() - t0), flush=True)


def T_mlp(P, s):
    w0, b0, w1, b1 = P
    return np.maximum(s @ w0.T + b0, 0.0) @ w1.T + b1


if __name__ == "__main__":
    main()

"""WIN_END's tests (v0.6.2). Each side in its own process (switches are read at import).
  ident  WE_CODE's sim/ (the code with WIN_END) with WIN_END unset against WE_REF's sim/ (the code without it), v0.6.1's settings
         (WIN_JUDGE on, WIN_W 1, FADE_V 1), the games put 10 s before their limit so that game ends and overtime are run: obs,
         reward, done, r_long, events and counters the same to the bit
  end    WIN_END=1 (and OVERTIME_CAP 1, test only, so that games end, draws too): every game that ends pays in all (its seat a's
         win part summed from the frame it was put near the limit) scale x (result - the chance then), the result read as
         _game_end is called; zero-sum; the reward on game frames = WIN_GAIN x the win part; a level limit frame that goes on
         reads OT_LEN (fix 2)
    WE_REF=<checkout> WE_CODE=<checkout> python tools/win_end_test.py [ident|end|both] [--frames 9000] [--map bloodrun,aerowalk]
    (both default to this checkout; the data folder is this checkout's data/ unless WE_DATA)"""
import json, os, subprocess, sys, tempfile
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.environ.get("WE_REF") or ROOT
WT = os.environ.get("WE_CODE") or ROOT
DATA = os.environ.get("WE_DATA") or os.path.join(ROOT, "data")
FF = 400                                                     # (frames before the limit the games are put at)


def side(code, mp, frames, out, envv, check):
    os.environ.update(envv)
    sys.path.insert(0, os.path.join(code, "sim"))
    import importlib
    E = importlib.import_module("duel_env_ffa")
    assert os.path.dirname(os.path.abspath(E.__file__)) == os.path.join(code, "sim"), E.__file__
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    g_ = env._others_arr().shape[1] + 1
    H = []
    T = dict(ends=0, sum_err=0.0, p_after_err=0.0, zero_sum=0.0, pay_err=0.0, ot_frames=0, ot_left_bad=0, big_terms=0, levels=0)
    FIN = {}                                                 # (the final score of each game, read as _game_end is called: before any reset)
    _ge = env._game_end

    def _game_end_rec(m):
        q_ = env._seats(m)
        FIN[int(m)] = float(env.frags_r[int(q_[0])] - env.frags_r[int(q_[1])])
        return _ge(m)
    env._game_end = _game_end_rec
    S = np.zeros(env.M)                                      # (seat a's win part summed since the put)
    P0 = np.full(env.M, np.nan)
    put = np.zeros(env.M, bool)
    for t in range(frames):
        if t > 5:                                            # (put every running game not yet put 10 s before its limit)
            new_ = np.nonzero((env.game > 0) & ~put & (env.g_tick < E.GAME_FRAMES - FF))[0]
            if len(new_):
                env.g_tick[new_] = E.GAME_FRAMES - FF
                env.round_t[new_] = (env.g_tick[new_] * E.DT).astype(np.float32)
                put[new_] = True
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        game_before = env.game.copy()
        tick_before = env.g_tick.copy()
        obs, rew, done, info = env.step(a)
        H.append((obs.astype(np.float32), rew.astype(np.float32), done.copy(), np.asarray(info["r_long"], np.float32),
                  [(e["victim"], e["killer"]) for e in info["events"]]))
        if not check:
            continue
        raw = env.wb_raw
        gm = np.nonzero(env.wb_gm[::g_])[0]
        if len(gm):
            a_, b_ = gm * g_, gm * g_ + 1
            T["zero_sum"] = max(T["zero_sum"], float(np.abs(raw[a_] + raw[b_]).max()))
            T["pay_err"] = max(T["pay_err"], float(np.abs(rew[a_] - E.WIN_GAIN * raw[a_]).max()))
            lim_ = (env.g_tick[gm] >= E.GAME_FRAMES) & (game_before[gm] > 0) & (env.game[gm] > 0) & ((env.g_tick[gm] - E.GAME_FRAMES) % E.OT_FRAMES == 0)
            # (a limit frame of a game that went on: the score level there, as _ot_ends decided)
            on_ = lim_ & (env.frags_r[a_] == env.frags_r[b_])
            T["ot_frames"] += int(on_.sum())
            T["ot_left_bad"] += int((on_ & (np.abs(env.wb_left[gm] - E.OT_LEN) > 1e-9)).sum())
        for m in range(env.M):
            if not put[m]:
                continue
            if np.isnan(P0[m]) and game_before[m] > 0 and tick_before[m] >= E.GAME_FRAMES - FF:
                P0[m] = env.wb_p[m] - raw[m * g_] / env.wb_scale  # (the chance before this frame's pay)
            if not np.isnan(P0[m]):
                S[m] += raw[m * g_]
            if game_before[m] > 0 and tick_before[m] >= E.GAME_FRAMES - FF and env.g_tick[m] < tick_before[m] and not np.isnan(P0[m]):   # (ended this frame; a new one may begin on it)
                d = FIN.pop(m)
                res = 1.0 if d > 0 else (0.0 if d < 0 else 0.5)
                T["ends"] += 1
                T["levels"] += int(d == 0)
                T["sum_err"] = max(T["sum_err"], abs(S[m] - env.wb_scale * (res - P0[m])))
                T["big_terms"] += int(abs(S[m] - raw[m * g_] * 0) > 0)
                put[m] = True
                P0[m], S[m] = np.nan, 0.0
                put[m] = False
    obs = np.stack([x[0] for x in H]); rew = np.stack([x[1] for x in H]); done = np.stack([x[2] for x in H]); rl = np.stack([x[3] for x in H])
    ev = json.dumps([x[4] for x in H], default=int)
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=obs, rew=rew, done=done, rl=rl, ev=np.array(ev), T=np.array(json.dumps(T)), **stv)


def run_side(code, mp, frames, envv, check):
    o_ = tempfile.mktemp(suffix=".npz", prefix="win_end_")
    subprocess.check_call([sys.executable, os.path.abspath(__file__), "_side", code, mp, str(frames), o_, json.dumps(envv), "1" if check else "0"])
    return np.load(o_)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_side":
        _, _, code, mp, frames, out, envj, c = sys.argv
        side(code, mp, int(frames), out, json.loads(envj), c == "1")
        return
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    frames = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 9000
    maps = (sys.argv[sys.argv.index("--map") + 1] if "--map" in sys.argv else "bloodrun,aerowalk").split(",")
    sys.path.insert(0, os.path.join(MAIN, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(os.path.join(MAIN, "docs", "runs", "v0.6.1", "train.cmd"), os.path.join(DATA, "sim_runs", "duel_gru_v0_6_1"))
    envv.update(STAGGER_START="1", GAME_P="1", PRO_START_P="0", MID_START_P="0", WIN_W="1", FADE_V="1", WIN_GAIN="0.33",
                WIN_JUDGE=os.path.join(DATA, "sim_runs", "judge", "judge_v060_wpn.npz"))
    envv.pop("WIN_END", None)
    ok = True
    for mp in maps:
        if what in ("ident", "both"):
            A = run_side(MAIN, mp, frames, envv, False)
            B = run_side(WT, mp, frames, envv, False)
            same = {k: bool(np.array_equal(A[k], B[k])) for k in ("obs", "rew", "done", "rl")}
            same["events"] = str(A["ev"]) == str(B["ev"])
            ka = sorted(k for k in A.files if k.startswith("st_"))
            same["counters"] = ka == sorted(k for k in B.files if k.startswith("st_")) and all(np.array_equal(A[k], B[k]) for k in ka)
            print("{} ident (WIN_END unset, worktree vs main): {} frames | {}".format(mp, frames, same), flush=True)
            ok &= all(same.values())
        if what in ("end", "both"):
            B = run_side(WT, mp, frames, dict(envv, WIN_END="1", OVERTIME_CAP="1"), True)   # (test only: one period, so games end, draws too)
            T = json.loads(str(B["T"]))
            good = (T["ends"] > 0 and T["sum_err"] < 1e-6 and T["p_after_err"] < 1e-12 and T["zero_sum"] < 1e-9 and T["pay_err"] < 1e-4
                    and T["ot_left_bad"] == 0)
            print("{} WIN_END on: {} | win_end counter {} | {}".format(mp, T, B["st_win_end"].tolist() if "st_win_end" in B.files else None,
                                                                     "OK" if good else "FAILED"), flush=True)
            ok &= good
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

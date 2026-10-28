"""WIN_JUDGE's tests (v0.6.1): fixed-seed replays of the run's simulator (its .cmd and live files, as tools/winpay_ident.py).

  ident  this checkout's sim/ with WIN_JUDGE unset against another checkout's sim/ (the code the run trains with): inputs, pay,
         round ends, r_long, events and counters the same to the bit, with the blend off and on (WIN_W 0.5, FADE_V 0.5)
  judge  WIN_JUDGE on (WIN_W 1): the blend's chance (wb_p) equals sim/win_judge.chance on the simulator's own state every frame;
         the win part is zero-sum and = WIN_SCALE x the change in the chance; a frag's frame never pays the killer's win part
         negative (nor a death's the victim's positive) with no other damage that frame; no NaN; the chance at a whole game's
         start is 0.5
    python tools/judge_ident.py ident --other <checkout> --run-cmd <.cmd> --run-dir <run folder> [--map bloodrun,aerowalk] [--frames 3000]
    python tools/judge_ident.py judge --judge <file.npz> --run-cmd <.cmd> --run-dir <run folder> [--map ...] [--frames 3000]
Each side runs in a process of its own (the switches are read at import); the data folder is --data (default: this checkout's
data/, or the other checkout's when this one has none).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def side(code, data, mp, frames, out, envv, check_judge):
    os.environ.update(envv)
    sys.path.insert(0, os.path.join(code, "sim"))
    sys.path.insert(1, os.path.join(ROOT, "sim"))            # (win_judge from this checkout if the code's has none)
    import importlib
    E = importlib.import_module("duel_env_ffa")
    nav_ = os.path.join(data, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(data, "maps", mp + ".bsp"), n_matches=12, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    env.item_reward, env.intent_seek, env.item_loss = 0.0, 1.0, 0.5
    env.kind_p, env.bot_p, env.loadout_p = (1.0, 0.0, 0.0, 0.0), 0.0, (0.0, 1.0, 0.0, 0.0)
    env.dmg_taken_w, env.dmg_reward, env.close_p, env.round_len = 1.0, 0.0055, 0.0, 120.0
    env.round_t[:] = 1e9
    rng = np.random.default_rng(3)
    dims = np.array(E.ACTION_DIMS)
    H = []
    J = dict(frames=0, parity=0.0, zero_sum=0.0, scale_err=0.0, nan=0, frag_bad=0, frags=0, start_err=0.0, starts=0)
    if check_judge:
        import win_judge as wj
        g_ = env._others_arr().shape[1] + 1
    for t in range(frames):
        a = (rng.random((env.n, len(dims))) * dims).astype(np.int64)
        p_before = env.wb_p.copy() if check_judge else None
        game_before = env.game.copy() if check_judge else None
        obs, rew, done, info = env.step(a)
        H.append((obs.astype(np.float32), rew.astype(np.float32), done.copy(), np.asarray(info["r_long"], np.float32),
                  [(e["victim"], e["killer"]) for e in info["events"]]))
        if check_judge:
            gm = np.nonzero(env.wb_gm[::g_])[0]
            J["frames"] += 1
            raw = env.wb_raw
            J["nan"] += int((~np.isfinite(raw)).sum() + (~np.isfinite(env.wb_p)).sum())
            if len(gm):
                a_, b_ = gm * g_, gm * g_ + 1
                J["zero_sum"] = max(J["zero_sum"], float(np.abs(raw[a_] + raw[b_]).max()))
                pd_ = env._wb_chance(gm, env.wb_left[gm])          # (the chance from the state as it is now)
                J["parity"] = max(J["parity"], float(np.abs(pd_ - env.wb_p[gm]).max()))
                same_ = game_before[gm] > 0
                if same_.any():
                    J["scale_err"] = max(J["scale_err"], float(np.abs(raw[a_][same_] - env.wb_scale * (env.wb_p[gm][same_] - p_before[gm][same_])).max()))
                # direct: sim/win_judge on the raw state
                dead_ = (env.hp <= 0) | (env.rsp_wait > 0)
                ea_ = wj.effective(env.hp[a_], env.armor[a_], dead_[a_])
                eb_ = wj.effective(env.hp[b_], env.armor[b_], dead_[b_])
                wa_ = np.where(dead_[a_][:, None], 0.0, env.has[a_][:, [E.RL, E.LG, E.RG]].astype(np.float64))
                wb_ = np.where(dead_[b_][:, None], 0.0, env.has[b_][:, [E.RL, E.LG, E.RG]].astype(np.float64))
                pdir_ = wj.chance(env.wb_judge, (env.frags_r[a_] - env.frags_r[b_]).astype(np.float64), env.wb_left[gm], ea_, wa_, eb_, wb_)
                J["parity"] = max(J["parity"], float(np.abs(pdir_ - env.wb_p[gm]).max()))
                st_ = gm[(game_before[gm] == 0) & (env.g_tick[gm] <= 1) & (env.game[gm] == 1)]
                for m in st_:
                    J["starts"] += 1
            for e in info["events"]:
                k_, v_ = int(e["killer"]), int(e["victim"])
                if k_ < 0 or k_ == v_ or not env.wb_gm[k_]:
                    continue
                J["frags"] += 1
                if raw[k_] < -1e-12:
                    J["frag_bad"] += 1
    obs = np.stack([x[0] for x in H])
    rew = np.stack([x[1] for x in H])
    done = np.stack([x[2] for x in H])
    rl = np.stack([x[3] for x in H])
    ev = json.dumps([x[4] for x in H], default=int)
    stv = {"st_" + k: np.asarray(v_, np.float64) for k, v_ in env.stats.items()}
    np.savez(out, obs=obs, rew=rew, done=done, rl=rl, ev=np.array(ev), J=np.array(json.dumps(J)), **stv)


def run_side(code, data, mp, frames, envv, check_judge):
    o_ = tempfile.mktemp(suffix=".npz", prefix="judge_ident_")
    subprocess.check_call([sys.executable, os.path.abspath(__file__), "_side", code, data, mp, str(frames), o_, json.dumps(envv), "1" if check_judge else "0"])
    return np.load(o_)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_side":
        _, _, code, data, mp, frames, out, envj, cj = sys.argv
        side(code, data, mp, int(frames), out, json.loads(envj), cj == "1")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("ident", "judge"))
    ap.add_argument("--other", default="")
    ap.add_argument("--judge", default="")
    ap.add_argument("--run-cmd", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--data", default="")
    ap.add_argument("--map", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=3000)
    a = ap.parse_args()
    data = a.data or (os.path.join(ROOT, "data") if os.path.isdir(os.path.join(ROOT, "data", "maps")) else os.path.join(a.other, "data"))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import winpay_games as WG
    envv, _ = WG.run_env(a.run_cmd, a.run_dir)
    envv.update(STAGGER_START="1", GAME_P="1", PRO_START_P="0", MID_START_P="0")
    envv.pop("WIN_JUDGE", None)
    ok = True
    for mp in a.map.split(","):
        if a.what == "ident":
            for blend in ((0.0, 0.0), (0.5, 0.5)):
                ev_ = dict(envv, WIN_W=str(blend[0]), FADE_V=str(blend[1]))
                A = run_side(a.other, data, mp, a.frames, ev_, False)
                B = run_side(ROOT, data, mp, a.frames, ev_, False)
                same = {k: bool(np.array_equal(A[k], B[k])) for k in ("obs", "rew", "done", "rl")}
                same["events"] = str(A["ev"]) == str(B["ev"])
                ka = sorted(k for k in A.files if k.startswith("st_"))
                same["counters"] = ka == sorted(k for k in B.files if k.startswith("st_")) and all(np.array_equal(A[k], B[k]) for k in ka)
                print("{} WIN_W {} FADE_V {}: {} frames | identical: {}".format(mp, blend[0], blend[1], a.frames, same))
                ok &= all(same.values())
        else:
            ev_ = dict(envv, WIN_W="1", FADE_V="0", WIN_JUDGE=os.path.abspath(a.judge))
            B = run_side(ROOT, data, mp, a.frames, ev_, True)
            J = json.loads(str(B["J"]))
            good = J["parity"] < 1e-9 and J["zero_sum"] < 1e-9 and J["scale_err"] < 1e-6 and J["nan"] == 0 and J["frag_bad"] == 0
            print("{} WIN_JUDGE on: {} | {}".format(mp, J, "OK" if good else "FAILED"))
            ok &= good
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
